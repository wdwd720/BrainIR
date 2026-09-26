"""ks_sindy: SINDy with control on learned predictive coordinates, E-SINDy ensembles (family B).

Mathematics
-----------
Coordinates.  f_t = [x~_t, x~_{t-l1}, ...] (standardised microstate, optional causal lags chosen by validation);
              C = predictive basis (ks_core.predictive_basis): reduced-rank ridge regression f_t -> future readout and future
              principal components at a ladder of horizons, future inputs partialled out. z_t = (f_t - mean f) C_k (first k columns).
Dynamics.     discrete-time SINDy with control,  z_{t+1} - z_t = Theta(z_t, u_t) Xi,  Theta = monomials of degree <= p in (z, u) with
              u entering at most linearly (control-affine / bilinear). Fitted in INTEGRAL form over m steps,
                  (z_{t+m} - z_t) / m = (1/m) sum_{s=t}^{t+m-1} Theta(z_s, u_s) Xi,
              which averages observation noise in the regressors; columns standardised; sequentially thresholded least squares.
Selection.    the threshold (log grid), the degree p and k are chosen by the held-out SIMULATION error (validation rollouts of
              the readout with the trajectories' own events, horizon T/4); k by the generic rule of ks_core.select_dimension.
Ensemble.     E-SINDy: B bootstrap resamples of TRAINING TRAJECTORIES, STLSQ on each; inclusion probability pi_j; final support
              {pi_j >= 0.6}, coefficients refitted on all data; coefficient s.d. across bags reported as uncertainty.
Readout.      y = ridge on monomials of (z, u) of degree 1 or 2 (chosen by validation readout error).
Events.       through the encoder (ks_core.KSModel): kicks dz = (dx / sd) C_k; currents, silencing and edge removal as per-step
              microstate increments of the shared microscopic coupling estimate, mapped through the same encoder.
"""

from __future__ import annotations

import numpy as np

from ..api import StateMethod, register
from . import ks_core as C
from .ks_abstain import abstention


class SindyModel(C.KSModel):
    def _encode(self, sid, x_hist, u_hist):
        S = self.sys[sid]
        need = (max(S["lags"]) if S["lags"] else 0) + 1
        xs = S["prep"].xs(x_hist[-need:])
        f = C.lag_features(xs, S["lags"])[-1]
        return (f - S["f_mu"]) @ S["Ck"] + S.get("z_off", 0.0)

    def _step(self, sid, z, u):
        S = self.sys[sid]
        return z + S["lib"](z, u)[0] @ S["W"] + S["w0"]

    def _apply_dq(self, sid, z, dq):
        return z + dq @ self.sys[sid]["Ck0"]

    def _decode_x(self, sid, z):
        S = self.sys[sid]
        return S["prep"].mu + S["prep"].sd * (z @ S["Dx"] + S["dx0"])

    def _readout(self, sid, Z, U):
        S = self.sys[sid]
        return S["ro"].predict(S["ro_lib"](Z, U)[:, 1:])

    def coefficients(self, sid):
        """(term names, Xi in per-step units (n_terms, k), inclusion probabilities, bootstrap s.d.)."""
        S = self.sys[sid]
        return S["lib"].names, S["Xi_raw"], S.get("incl"), S.get("xi_sd")


# ------------------------------------------------------------------------------------------------------------ fitting helpers
def _series(prep, trajs, lags, f_mu, Ck):
    return [(C.lag_features(prep.xs(t.x), lags) - f_mu) @ Ck for t in trajs]


def _integral_rows(Zs, trajs, lib, m):
    """Rows of the integral-form regression per trajectory: mean_s Theta(z_s, u_s) and (z_{t+m} - z_t) / m on event-free windows."""
    rows = []
    for Z, tr in zip(Zs, trajs):
        keep = C.free_mask(tr)
        run = C.event_free_after(keep)
        Th = lib(Z, tr.u.astype(np.float64))
        cs = np.vstack([np.zeros((1, Th.shape[1])), np.cumsum(Th, 0)])
        idx = np.flatnonzero(run[: len(Z) - m] >= m) if len(Z) > m else np.array([], int)
        if len(idx) == 0:
            rows.append((np.zeros((0, Th.shape[1])), np.zeros((0, Z.shape[1]))))
            continue
        A = (cs[idx + m] - cs[idx]) / m
        D = (Z[idx + m] - Z[idx]) / m
        rows.append((A, D))
    return rows


def _subsample_rows(rows, max_rows, seed):
    n = sum(len(a) for a, _ in rows)
    if n <= max_rows:
        return rows
    rng = np.random.default_rng(seed)
    frac = max_rows / n
    out = []
    for a, d in rows:
        m = rng.random(len(a)) < frac
        out.append((a[m], d[m]))
    return out


class _Standardiser:
    def __init__(self, A, D):
        self.m = A.mean(0)
        self.s = A.std(0)
        self.m[0], self.s[0] = 0.0, 1.0                     # constant column
        self.s[self.s < 1e-12] = 1.0
        self.ds = D.std(0) + 1e-12

    def apply(self, A, D):
        return (A - self.m) / self.s, D / self.ds

    def to_raw(self, Xi):
        """Xi on standardised columns / targets -> per-step raw coefficients W (n_terms, k) and bias w0."""
        W = Xi / self.s[:, None] * self.ds[None, :]
        w0 = -(self.m / self.s) @ Xi * self.ds
        return W, w0


def _fit_xi(rows, thr, always):
    A = np.concatenate([a for a, _ in rows])
    D = np.concatenate([d for _, d in rows])
    st = _Standardiser(A, D)
    As, Ds = st.apply(A, D)
    Xi = C.stlsq(As, Ds, thr, always=always)
    return Xi, st


def build_system(prep, micro, trajs, lags, basis, k, deg, thr, m, seed=0, ro_deg=1, ensemble=0, incl_thr=0.6):
    f_mu, Cb = basis["f_mu"], basis["C"]
    Ck = Cb[:, :k]
    Zs = _series(prep, trajs, lags, f_mu, Ck)
    lib = C.PolyLibrary(k, prep.n_u, deg)
    rows = _subsample_rows(_integral_rows(Zs, trajs, lib, m), 60000, seed)
    always = np.zeros(lib.n_terms, bool)
    always[0] = True
    Xi, st = _fit_xi(rows, thr, always)
    incl = xi_sd = None
    if ensemble:
        rng = np.random.default_rng(seed + 17)
        bags = []
        for b in range(ensemble):
            pick = rng.integers(0, len(rows), len(rows))
            Xb, _ = _fit_xi([rows[i] for i in pick], thr, always)
            bags.append(Xb)
        bags = np.stack(bags)
        incl = (np.abs(bags) > 0).mean(0)
        xi_sd = bags.std(0)
        support = (incl >= incl_thr) | always[:, None]
        A = np.concatenate([a for a, _ in rows]); D = np.concatenate([d for _, d in rows])
        As, Ds = st.apply(A, D)
        G, bb = As.T @ As / len(As), As.T @ Ds / len(As)
        Xi = np.zeros_like(Xi)
        for j in range(Xi.shape[1]):
            a = support[:, j]
            Xi[a, j] = np.linalg.solve(G[np.ix_(a, a)] + 1e-5 * np.eye(int(a.sum())), bb[a, j])
    W, w0 = st.to_raw(Xi)
    S = assemble(prep, micro, trajs, lags, f_mu, Ck, 0.0, lib, W, w0, ro_deg, np.asarray(basis["C"][: prep.N, :k]))
    S.update({"Xi_raw": W, "incl": incl, "xi_sd": xi_sd, "deg": deg, "thr": thr, "support": np.abs(Xi) > 0})
    return S


def assemble(prep, micro, trajs, lags, f_mu, Ck, z_off, lib, W, w0, ro_deg, Ck0):
    """System dict from an encoder (Ck, z_off: z = (f - f_mu) Ck + z_off; Ck0 = its current-sample block) and dynamics (lib, W, w0)."""
    k = Ck.shape[1]
    Zs = [(C.lag_features(prep.xs(t.x), lags) - f_mu) @ Ck + z_off for t in trajs]
    Zc = np.concatenate(Zs)
    Uc = np.concatenate([t.u for t in trajs]).astype(np.float64)
    Yc = np.concatenate([t.y for t in trajs]).astype(np.float64)
    Xc = np.concatenate([prep.xs(t.x) for t in trajs])
    ro_lib = C.PolyLibrary(k, prep.n_u, ro_deg)
    ro = C.Ridge(1e-4).fit(ro_lib(Zc, Uc)[:, 1:], Yc)
    Dx = C.ridge_solve(Zc - Zc.mean(0), Xc - Xc.mean(0), 1e-4)
    dx0 = Xc.mean(0) - Zc.mean(0) @ Dx
    z_lo, z_hi = Zc.min(0), Zc.max(0)
    span = z_hi - z_lo
    n_active = int((np.abs(W) > 0).sum())
    return {"prep": prep, "micro": micro, "lags": tuple(lags), "f_mu": f_mu, "Ck": Ck, "Ck0": Ck0, "z_off": z_off, "basis": np.eye(prep.N),
            "lib": lib, "W": W, "w0": w0, "Xi_raw": W, "incl": None, "xi_sd": None, "ro": ro, "ro_lib": ro_lib, "Dx": Dx, "dx0": dx0,
            "z_lo": z_lo - span, "z_hi": z_hi + span, "silence_mode": "drive", "k": k, "ro_deg": ro_deg, "z_cov": np.cov(Zc.T).reshape(k, k),
            "n_params": {"encoder": int(Ck.size + f_mu.size), "transition": n_active + k, "readout": int(ro.n_params)}}


def make_basis(prep, trajs, lags, r_max, seed=0):
    feats = [C.lag_features(prep.xs(t.x), lags) for t in trajs]
    fm = np.concatenate(feats).mean(0)
    b = C.predictive_basis(prep, trajs, feats, H=max(2, prep.T // 4), r_max=r_max, seed=seed)
    b["f_mu"] = fm
    return b


def lag_grid(T, cfg):
    out = [()]
    for fr in cfg["lag_fracs"]:
        out.append(tuple(sorted({max(1, int(round(f * T))) for f in fr})))
    return out


@register
class KSSindy(StateMethod):
    name = "ks_sindy"
    version = "1"
    default_config = {"k_grid": (1, 2, 3, 4, 5, 6, 8), "deg_grid": (1, 2, 3), "thr_grid": (0.0, 0.05, 0.2),
                      "lag_fracs": ((0.01, 0.025), (0.01, 0.025, 0.05, 0.1)), "rel_tol": 0.05, "max_val": 16, "n_folds": 2, "ensemble": 24, "incl_thr": 0.6,
                      "max_terms": 60, "lam_norm": 0.1, "share_steps": 600, "share_starts": 4, "share_probe_steps": 120}
    supported_sharing = ("auto", "independent", "shared")
    supports_adaptation = True

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        C.set_threads(3)
        C.seed_all(seed)
        cfg = {**self.default_config, **(config or {})}
        sharing = cfg.get("sharing", "auto") or "auto"
        if sharing not in self.supported_sharing:
            raise NotImplementedError(f"ks_sindy: sharing mode {sharing!r} not supported")
        if cfg.get("adapt_from") is not None:
            return self._adapt(train, systems, cfg, seed)
        tables = {}
        timer = C.Timer()
        model = SindyModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                "sharing": {"mode": "independent", "verdict": None}, "dim_curve": {}, "config": {}, "esindy": {}}
        n_tr = 0
        for sid in sorted({t.system_id for t in train}):
            trs = C.decimate([t for t in train if t.system_id == sid])
            entry = systems[sid]
            T = int(np.median([len(t.t) for t in trs]))
            m = max(1, T // 100)
            forced = cfg.get("k")
            k_grid = [int(forced)] if forced else [k for k in cfg["k_grid"]]
            r_max = max(k_grid)
            folds = C.cv_folds(trs, cfg["n_folds"], seed, cfg["max_val"])
            units = {"traj": {}, "draw": {}}

            def score(kind, fi, va, ks_):
                prep = C.SystemPrep(sid, fi, entry)
                micro = C.MicroModel(prep, fi, seed=seed)
                for lags in lag_grid(prep.T, cfg):
                    basis = make_basis(prep, fi, lags, r_max, seed)
                    for k in ks_:
                        if k > basis["C"].shape[1]:
                            continue
                        for deg in cfg["deg_grid"]:
                            if C.PolyLibrary(k, prep.n_u, deg).n_terms > cfg["max_terms"]:
                                continue
                            for thr in cfg["thr_grid"]:
                                model.sys[sid] = build_system(prep, micro, fi, lags, basis, k, deg, thr, m, seed)
                                e = C.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True)
                                units[kind].setdefault((k, lags, deg, thr), []).extend(e.tolist())
            # stage 1: every candidate on trajectory folds (dimension); stage 2: only the selected k on draw folds (configuration)
            for kind, fi, va in folds:
                if kind == "traj":
                    score(kind, fi, va, k_grid)
            k_sel = C.select_from_table(C.table_from_units(units["traj"], lambda c: (0,), 0.0), cfg["rel_tol"])["k"]
            for kind, fi, va in folds:
                if kind == "draw":
                    score(kind, fi, va, [k_sel])
            sel, best, table = C.two_stage_select(units["traj"], units["draw"], lambda c: (len(c[0]) > 0, c[1], -c[2]), cfg["rel_tol"])
            best["lags"], best["deg"], best["thr"] = best.pop("conf")
            for kk, row in table.items():
                row["lags"], row["deg"], row["thr"] = row.pop("conf")
            ks = sorted(table)
            tables[sid] = table
            folds = [(a_, b_) for kind, a_, b_ in folds if kind == "draw"]
            # readout degree by the same folds at the selected configuration
            ro_err = {}
            for rd in (1, 2):
                e = []
                for fi, va in folds:
                    prep = C.SystemPrep(sid, fi, entry)
                    micro = C.MicroModel(prep, fi, seed=seed)
                    basis = make_basis(prep, fi, best["lags"], r_max, seed)
                    model.sys[sid] = build_system(prep, micro, fi, best["lags"], basis, best["k"], best["deg"], best["thr"], m, seed,
                                                  ro_deg=rd)
                    e += C.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True).tolist()
                ro_err[rd] = float(np.mean(e))
            ro_deg = min(ro_err, key=ro_err.get)
            # final E-SINDy fit on all trajectories (train + val)
            prep_f = C.SystemPrep(sid, trs, entry)
            micro_f = C.MicroModel(prep_f, trs, seed=seed)
            basis_f = make_basis(prep_f, trs, best["lags"], r_max, seed)
            S = build_system(prep_f, micro_f, trs, best["lags"], basis_f, best["k"], best["deg"], best["thr"], m, seed, ro_deg=ro_deg,
                             ensemble=cfg["ensemble"], incl_thr=cfg["incl_thr"])
            model.sys[sid] = S
            model.k[sid] = best["k"]
            sil = model.choose_silence_mode(sid, trs, prep_f.y_var)
            curve = [{kk: v for kk, v in table[k].items() if kk != "units"} for k in ks]
            info["k"][sid] = best["k"]
            info["k_range"][sid] = sel["range"]
            info["dim_curve"][sid] = curve
            info["abstain"][sid] = abstention(curve, sel, prep_f.N, forced=bool(forced))
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
            info["n_params"]["transition"] += S["n_params"]["transition"]
            info["config"][sid] = {"lags": best["lags"], "deg": best["deg"], "thr": best["thr"], "ro_deg": ro_deg, "m": m,
                                   "silence_mode": S["silence_mode"], "silence_errors": sil, "gamma": micro_f.gamma,
                                   "micro_r2": micro_f.r2, "basis_err_curve": basis_f["err_curve"]}
            info["esindy"][sid] = {"terms": S["lib"].names, "n_active": int((np.abs(S["W"]) > 0).sum()),
                                   "inclusion": S["incl"].tolist() if S["incl"] is not None else None,
                                   "coef_sd": S["xi_sd"].tolist() if S["xi_sd"] is not None else None}
            n_tr += len(trs)
        if sharing == "shared" and len(model.sys) > 1:
            self._share(model, train, systems, cfg, seed, info, tables)
        info["train_cost"] = {"cpu_s": timer.cpu(), "wall_s": timer.wall(), "sim_calls": 0, "n_trajectories": n_tr}
        info["lipschitz_bound"] = None
        model._info = info
        return model

    # ------------------------------------------------------------------------------------------------ sharing / adaptation
    def _fit_encoders(self, entries, dyn, k, cfg, seed, train_dyn, z_cov, init_identity):
        """entries: [(sid, prep, trajs, basis)]. Per-system linear encoders q (first k predictive coordinates) -> z for the polynomial
        law `dyn`; multi-start over orthogonal initialisations for systems without a natural gauge. Returns [encoder export]."""
        import torch
        from . import ks_share as SH
        H = max(8, entries[0][1].T // 4)
        systems_l = []
        for i, (sid, prep, trs, basis) in enumerate(entries):
            Qs = [(prep.xs(t.x) - basis["f_mu"]) @ basis["C"][:, :k] for t in trs]
            inits = [np.eye(k)]
            if not init_identity[i]:
                rng = np.random.default_rng(seed + i)
                inits = [np.eye(k), -np.eye(k)] + [np.linalg.qr(rng.standard_normal((k, k)))[0] for _ in range(cfg["share_starts"] - 2)]
            best = None
            for j, W0 in enumerate(inits):
                enc = SH.make_encoder(k, k, 0, seed + i, init_lin=(W0, np.zeros(k)))
                torch.manual_seed(seed + i)
                ro = torch.nn.Linear(k + prep.n_u, prep.n_y)
                sysd = {"Qs": Qs, "trajs": trs, "prep": prep, "enc": enc, "dec": None, "ro": ro}
                if len(inits) > 1:
                    h = SH.train_latent([sysd], dyn, cfg["share_probe_steps"], seed + j, H, train_dyn=False, z_cov_target=z_cov,
                                        lam_norm=cfg["lam_norm"])
                    score = float(np.mean(h[-2:]))
                else:
                    score = 0.0
                if best is None or score < best[0]:
                    best = (score, sysd)
            systems_l.append(best[1])
        SH.train_latent(systems_l, dyn, cfg["share_steps"] * len(systems_l), seed, H, train_dyn=train_dyn, z_cov_target=z_cov,
                        lam_norm=cfg["lam_norm"])
        return [SH.enc_export(sd["enc"]) for sd in systems_l]

    def _share(self, model, train, systems, cfg, seed, info, tables):
        """One sparse polynomial law for all systems: k = the largest per-system selected k (or the forced k); the reference system's
        E-SINDy model at that k initialises the law and fixes its support; per-system linear encoders are fitted jointly with the
        law (latent normalised to the reference covariance)."""
        from . import ks_share as SH
        sids = sorted(model.sys)
        if len({systems[s]["input_dim"] for s in sids}) != 1:
            raise NotImplementedError("ks_sindy shared: systems have different input dimensions")
        k = int(cfg.get("k") or max(model.k[s] for s in sids))
        ref = next((s for s in sids if model.k[s] == k), sids[0])
        row = tables[ref].get(k) or tables[ref][min(tables[ref], key=lambda kk: abs(kk - k))]
        entries = []
        for sid in sids:
            trs = C.decimate([t for t in train if t.system_id == sid])
            prep = C.SystemPrep(sid, trs, systems[sid])
            entries.append((sid, prep, trs, make_basis(prep, trs, (), k, seed)))
        _, prep_r, trs_r, basis_r = entries[sids.index(ref)]
        micro_r = C.MicroModel(prep_r, trs_r, seed=seed)
        S_ref = build_system(prep_r, micro_r, trs_r, (), basis_r, k, row["deg"], row["thr"], max(1, prep_r.T // 100), seed,
                             ensemble=cfg["ensemble"], incl_thr=cfg["incl_thr"])
        dyn = SH.make_poly_dyn(S_ref["lib"], S_ref["W"], S_ref["w0"], (np.abs(S_ref["W"]) > 0).astype(float))
        encs = self._fit_encoders(entries, dyn, k, cfg, seed, True, S_ref["z_cov"], [s == ref for s in sids])
        D = dyn.export()
        for (sid, prep, trs, basis), e in zip(entries, encs):
            micro = C.MicroModel(prep, trs, seed=seed)
            Ck = basis["C"][:, :k] @ e["We"]
            S = assemble(prep, micro, trs, (), basis["f_mu"], Ck, e["be"], S_ref["lib"], D["W"], D["w0"], 1, Ck[: prep.N])
            model.sys[sid] = S
            model.k[sid] = k
            model.choose_silence_mode(sid, trs, prep.y_var)
            info["k"][sid] = k
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
        info["n_params"]["transition"] = int((np.abs(D["W"]) > 0).sum()) + k
        info["sharing"] = {"mode": "shared", "verdict": None, "k": k, "reference": ref}

    def _adapt(self, train, systems, cfg, seed):
        """Encoder-only adaptation: the polynomial law of `adapt_from` is frozen; linear encoders (multi-start) and ridge readouts
        are fitted for the systems in train, latent normalised to the source latent covariance."""
        from . import ks_share as SH
        src = cfg["adapt_from"]
        timer = C.Timer()
        S0 = next(iter(src.sys.values()))
        k = S0["k"]
        z_cov = np.mean([S["z_cov"] for S in src.sys.values()], axis=0)
        dyn = SH.make_poly_dyn(S0["lib"], S0["W"], S0["w0"], (np.abs(S0["W"]) > 0).astype(float))
        model = SindyModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": S0["n_params"]["transition"], "readout": {}},
                "sharing": {"mode": "adapted", "verdict": None}, "config": {}}
        n_tr = 0
        for sid in sorted({t.system_id for t in train}):
            trs = C.decimate([t for t in train if t.system_id == sid])
            if systems[sid]["input_dim"] != S0["lib"].n_u:
                raise NotImplementedError("ks_sindy adapt: input dimension differs from the source model")
            prep = C.SystemPrep(sid, trs, systems[sid])
            basis = make_basis(prep, trs, (), k, seed)
            e = self._fit_encoders([(sid, prep, trs, basis)], dyn, k, cfg, seed, False, z_cov, [False])[0]
            Ck = basis["C"][:, :k] @ e["We"]
            S = assemble(prep, C.MicroModel(prep, trs, seed=seed), trs, (), basis["f_mu"], Ck, e["be"], S0["lib"], S0["W"], S0["w0"], 1,
                         Ck[: prep.N])
            model.sys[sid] = S
            model.k[sid] = k
            model.choose_silence_mode(sid, trs, prep.y_var)
            info["k"][sid] = k
            info["k_range"][sid] = [k, k]
            info["abstain"][sid] = {"no_compact_state": False, "dimension_unresolved": None, "causal_equivalence_failed": False,
                                    "reason": "adapted: k inherited from the source model"}
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
            n_tr += len(trs)
        info["train_cost"] = {"cpu_s": timer.cpu(), "wall_s": timer.wall(), "sim_calls": 0, "n_trajectories": n_tr, "adaptation": True}
        info["lipschitz_bound"] = None
        model._info = info
        return model
