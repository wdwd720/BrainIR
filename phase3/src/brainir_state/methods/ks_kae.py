"""ks_kae: Koopman autoencoder with control (family C).

Mathematics
-----------
Input coordinates  q_t = (f_t - mean f) C_r (ks_core.predictive_basis, r_in coordinates; f = standardised microstate + optional lags).
Encoder            z = W_e q + MLP_e(q)                         linear + residual tanh-MLP, z in R^k
Latent operator    z_{t+1} = K z_t + B u_t + c,   K = exp(J - R),  J = S - S^T (skew), R = L L^T + eps I (PSD)
                   => every eigenvalue of J - R has non-positive real part, |eig K| <= 1: stable by construction, rotations /
                   integrators (R -> 0) representable
Readout            y = C_y z + D u + e (linear: y is an observable in the span of the Koopman coordinates)
Decoder            q^ = MLP_d(z) (anti-collapse, event handling, x decoding)
Loss over event-free windows of length h (curriculum from 8 steps to H = T/4 over the first 60 % of training):
    L = mean_j ||y^_j - y_j||^2 / var(y)  +  lambda_lat mean_j ||z_j - sg(enc(q_j))||^2 / var(z)  +  lambda_rec (||dec(z_j) - q_j||^2 + ||dec(enc(q_0)) - q_0||^2)
k: fitted for a ladder of k with a reduced budget on parameter-draw folds; the generic dimension rule (ks_core.select_dimension)
picks k; the final model is refitted with the full budget on all trajectories.
Events: kicks z' = z + enc(q^ + dq) - enc(q^) with q^ = dec(z); currents / silencing / edge removal as per-step microstate
increments of ks_core.MicroModel mapped the same way.
"""

from __future__ import annotations

import numpy as np

from ..api import StateMethod, register
from . import ks_core as C
from .ks_abstain import abstention


def _mlp_np(params, x):
    W1, b1, W2, b2 = params
    return np.tanh(x @ W1 + b1) @ W2 + b2


class KAEModel(C.KSModel):
    def _q(self, S, x_hist):
        need = (max(S["lags"]) if S["lags"] else 0) + 1
        f = C.lag_features(S["prep"].xs(x_hist[-need:]), S["lags"])[-1]
        return (f - S["f_mu"]) @ S["Cq"]

    def _enc_q(self, S, q):
        q = np.atleast_2d(q)
        return q @ S["We"] + S["be"] + _mlp_np(S["enc_mlp"], q)

    def _encode(self, sid, x_hist, u_hist):
        S = self.sys[sid]
        return self._enc_q(S, self._q(S, x_hist))[0]

    def _step(self, sid, z, u):
        S = self.sys[sid]
        return S["K"] @ z + S["B"] @ u + S["c"]

    def _apply_dq(self, sid, z, dq):
        S = self.sys[sid]
        qh = _mlp_np(S["dec_mlp"], z[None])[0]
        e = self._enc_q(S, np.vstack([qh, qh + dq]))
        return z + e[1] - e[0]

    def _decode_x(self, sid, z):
        S = self.sys[sid]
        return S["prep"].mu + S["prep"].sd * (z @ S["Dx"] + S["dx0"])

    def _readout(self, sid, Z, U):
        S = self.sys[sid]
        return Z @ S["Cy"] + U @ S["Dy"] + S["ey"]

    def eigenvalues(self, sid):
        return np.linalg.eigvals(self.sys[sid]["K"])


# ------------------------------------------------------------------------------------------------------------ training
def _qs(prep, trajs, lags, basis, r_in):
    Cq = basis["C"][:, :r_in]
    return Cq, [(C.lag_features(prep.xs(t.x), lags) - basis["f_mu"]) @ Cq for t in trajs]


def _finish_system(S, prep, micro, trajs, Qs, k):
    """Decoders to x, clipping box and parameter counts from the exported encoder of one system."""
    m = KAEModel()
    Zc = np.concatenate([m._enc_q(S, Q) for Q in Qs])
    Xc = np.concatenate([prep.xs(t.x) for t in trajs])
    Dx = C.ridge_solve(Zc - Zc.mean(0), Xc - Xc.mean(0), 1e-4)
    S["Dx"], S["dx0"] = Dx, Xc.mean(0) - Zc.mean(0) @ Dx
    lo, hi = Zc.min(0), Zc.max(0)
    S["z_lo"], S["z_hi"] = lo - (hi - lo), hi + (hi - lo)
    S["z_cov"] = np.cov(Zc.T).reshape(k, k)
    n_enc = sum(a.size for a in S["enc_mlp"]) + S["We"].size + S["be"].size + S["Cq"].size
    S["n_params"] = {"encoder": int(n_enc), "transition": int(k * k + S["B"].size + k),
                     "readout": int(S["Cy"].size + S["Dy"].size + S["ey"].size)}
    return S


def train_systems(preps, micros, trajs_l, lags, bases, r_in, k, steps, seed, hidden=64, dyn=None, train_dyn=True, z_cov=None,
                  lam_norm=0.0):
    """Train one Koopman latent law (or use a frozen one) with per-system encoders / decoders / readouts. Returns (system dicts, dyn)."""
    import torch
    from . import ks_share as SH
    C.seed_all(seed)
    n_u = preps[0].n_u
    if dyn is None:
        # warm start: least-squares DMDc on the first k predictive coordinates of the first system
        Cq0, Qs0 = _qs(preps[0], trajs_l[0], lags, bases[0], min(r_in, bases[0]["C"].shape[1]))
        Z0, Z1, U0 = [], [], []
        for Q, t in zip(Qs0, trajs_l[0]):
            kp = C.free_mask(t)
            Z0.append(Q[:-1, :k][kp]); Z1.append(Q[1:, :k][kp]); U0.append(t.u[:-1][kp].astype(np.float64))
        Z0, Z1, U0 = map(np.concatenate, (Z0, Z1, U0))
        kk = Z0.shape[1]
        init = None
        if kk == k:
            F = np.hstack([Z0, U0, np.ones((len(Z0), 1))])
            M = np.linalg.lstsq(F, Z1, rcond=None)[0]
            init = SH.stable_init(M[:k].T, M[k: k + n_u].T, M[-1])
        dyn = SH.make_koopman_dyn(k, n_u, seed, init=init)
    sys_l, qs_l = [], []
    for i, (prep, trajs, basis) in enumerate(zip(preps, trajs_l, bases)):
        Cq, Qs = _qs(prep, trajs, lags, basis, min(r_in, basis["C"].shape[1]))
        r = Cq.shape[1]
        W0 = np.zeros((r, k))
        W0[: min(r, k), : min(r, k)] = np.eye(min(r, k))
        enc = SH.make_encoder(r, k, hidden, seed + 10 * i, init_lin=(W0, np.zeros(k)) if (i == 0 and train_dyn) else None)
        dec = SH.make_decoder(k, r, hidden, seed + 10 * i)
        torch.manual_seed(seed + 10 * i + 3)
        ro = torch.nn.Linear(k + prep.n_u, prep.n_y)
        sys_l.append({"Qs": Qs, "trajs": trajs, "prep": prep, "enc": enc, "dec": dec, "ro": ro, "Cq": Cq})
    H = max(8, preps[0].T // 4)
    SH.train_latent(sys_l, dyn, steps * len(sys_l), seed, H, train_dyn=train_dyn, z_cov_target=z_cov, lam_norm=lam_norm)
    D = dyn.export()
    out = []
    for s, prep, micro, basis in zip(sys_l, preps, micros, bases):
        e = SH.enc_export(s["enc"])
        S = {"prep": prep, "micro": micro, "lags": tuple(lags), "f_mu": basis["f_mu"], "Cq": s["Cq"], "basis": s["Cq"][: prep.N],
             "silence_mode": "drive", **D, **e, "dec_mlp": SH.dec_export(s["dec"]), **SH.readout_export(s["ro"], prep, k)}
        out.append(_finish_system(S, prep, micro, s["trajs"], s["Qs"], k))
    return out, dyn


def build_system(prep, micro, trajs, lags, basis, r_in, k, steps, seed, hidden=64):
    return train_systems([prep], [micro], [trajs], lags, [basis], r_in, k, steps, seed, hidden)[0][0]


@register
class KSKae(StateMethod):
    name = "ks_kae"
    version = "1"
    default_config = {"k_grid": (1, 2, 3, 4, 6, 8), "r_in": 12, "steps_select": 500, "steps_final": 1500, "hidden": 64,
                      "lag_fracs": (), "rel_tol": 0.05, "max_val": 16, "n_folds": 2, "epochs": None, "lam_norm": 0.1}
    supported_sharing = ("auto", "independent", "shared")
    supports_adaptation = True

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        from .ks_sindy import lag_grid, make_basis
        C.set_threads(3)
        cfg = {**self.default_config, **(config or {})}
        if cfg.get("epochs"):                    # test / quick mode: one budget for selection and final fit
            cfg["steps_select"] = cfg["steps_final"] = int(cfg["epochs"])
        sharing = cfg.get("sharing", "auto") or "auto"
        if sharing not in self.supported_sharing:
            raise NotImplementedError(f"ks_kae: sharing mode {sharing!r} not supported")
        if cfg.get("adapt_from") is not None:
            return self._adapt(train, systems, cfg, seed)
        timer = C.Timer()
        model = KAEModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                "sharing": {"mode": "independent", "verdict": None}, "dim_curve": {}, "config": {}}
        n_tr = 0
        for sid in sorted({t.system_id for t in train}):
            trs = C.decimate([t for t in train if t.system_id == sid])
            entry = systems[sid]
            forced = cfg.get("k")
            k_grid = [int(forced)] if forced else list(cfg["k_grid"])
            units = {"traj": {}, "draw": {}}
            if len(k_grid) > 1:
                for kind, fi, va in C.cv_folds(trs, cfg["n_folds"], seed, cfg["max_val"]):
                    if kind == "draw":
                        continue            # a single configuration per k: only the trajectory folds (dimension) are needed
                    prep = C.SystemPrep(sid, fi, entry)
                    micro = C.MicroModel(prep, fi, seed=seed)
                    for lags in lag_grid(prep.T, cfg):
                        basis = make_basis(prep, fi, lags, cfg["r_in"], seed)
                        r_in = basis["C"].shape[1]
                        for k in k_grid:
                            model.sys[sid] = build_system(prep, micro, fi, lags, basis, r_in, k, cfg["steps_select"], seed, cfg["hidden"])
                            e = C.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True)
                            units["traj"].setdefault((k, lags), []).extend(e.tolist())
            else:
                units["traj"][(k_grid[0], ())] = [0.0]
            sel, best, table = C.two_stage_select(units["traj"], {}, lambda c: (len(c[0]) > 0,), cfg["rel_tol"])
            (best["lags"],) = best.pop("conf")
            for kk, row in table.items():
                (row["lags"],) = row.pop("conf")
            ks = sorted(table)
            prep_f = C.SystemPrep(sid, trs, entry)
            micro_f = C.MicroModel(prep_f, trs, seed=seed)
            basis_f = make_basis(prep_f, trs, best["lags"], cfg["r_in"], seed)
            S = build_system(prep_f, micro_f, trs, best["lags"], basis_f, basis_f["C"].shape[1], best["k"], cfg["steps_final"], seed,
                             cfg["hidden"])
            model.sys[sid] = S
            model.k[sid] = best["k"]
            sil = model.choose_silence_mode(sid, trs, prep_f.y_var)
            curve = [{kk: v for kk, v in table[k].items() if kk != "units"} for k in ks]
            info["k"][sid] = best["k"]
            info["k_range"][sid] = sel["range"]
            info["dim_curve"][sid] = curve
            info["abstain"][sid] = abstention(curve, sel, prep_f.N, forced=bool(forced) or len(k_grid) == 1)
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
            info["n_params"]["transition"] += S["n_params"]["transition"]
            info["config"][sid] = {"lags": best["lags"], "silence_mode": S["silence_mode"], "silence_errors": sil,
                                   "eig_abs": np.sort(np.abs(np.linalg.eigvals(S["K"])))[::-1].tolist()}
            n_tr += len(trs)
        sids = sorted(model.sys)
        if sharing == "shared" and len(sids) > 1:
            self._share(model, train, systems, cfg, seed, info)
        info["train_cost"] = {"cpu_s": timer.cpu(), "wall_s": timer.wall(), "sim_calls": 0, "n_trajectories": n_tr}
        info["lipschitz_bound"] = None
        model._info = info
        return model

    def _share(self, model, train, systems, cfg, seed, info):
        """One Koopman law for all systems: k = the largest per-system selected k (or the forced k); per-system encoders /
        decoders / readouts; latent normalisation to a common gauge (identity covariance)."""
        from .ks_sindy import make_basis
        sids = sorted(model.sys)
        if len({systems[s]["input_dim"] for s in sids}) != 1:
            raise NotImplementedError("ks_kae shared: systems have different input dimensions")
        k = int(cfg.get("k") or max(model.k[s] for s in sids))
        preps, micros, trl, bases = [], [], [], []
        for sid in sids:
            trs = C.decimate([t for t in train if t.system_id == sid])
            prep = C.SystemPrep(sid, trs, systems[sid])
            preps.append(prep); micros.append(C.MicroModel(prep, trs, seed=seed)); trl.append(trs)
            bases.append(make_basis(prep, trs, (), cfg["r_in"], seed))
        out, _ = train_systems(preps, micros, trl, (), bases, cfg["r_in"], k, cfg["steps_final"], seed, cfg["hidden"],
                               z_cov=np.eye(k), lam_norm=cfg["lam_norm"])
        for sid, S in zip(sids, out):
            model.sys[sid] = S
            model.k[sid] = k
            model.choose_silence_mode(sid, trl[sids.index(sid)], S["prep"].y_var)
            info["k"][sid] = k
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
        info["n_params"]["transition"] = out[0]["n_params"]["transition"]
        info["sharing"] = {"mode": "shared", "verdict": None, "k": k}

    def _adapt(self, train, systems, cfg, seed):
        """Encoder-only adaptation: the Koopman law (K, B, c) of `adapt_from` is frozen; new encoders / decoders / readouts are fitted
        for the systems in train with the latent normalised to the source model's latent covariance."""
        from . import ks_share as SH
        from .ks_sindy import make_basis
        src = cfg["adapt_from"]
        timer = C.Timer()
        S0 = next(iter(src.sys.values()))
        k = S0["K"].shape[0]
        z_cov = np.mean([S["z_cov"] for S in src.sys.values()], axis=0)
        dyn = SH.make_fixed_linear_dyn(S0["K"], S0["B"], S0["c"])
        model = KAEModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": S0["n_params"]["transition"], "readout": {}},
                "sharing": {"mode": "adapted", "verdict": None}, "config": {}}
        n_tr = 0
        for sid in sorted({t.system_id for t in train}):
            trs = C.decimate([t for t in train if t.system_id == sid])
            if systems[sid]["input_dim"] != S0["B"].shape[1]:
                raise NotImplementedError("ks_kae adapt: input dimension differs from the source model")
            prep = C.SystemPrep(sid, trs, systems[sid])
            micro = C.MicroModel(prep, trs, seed=seed)
            basis = make_basis(prep, trs, (), cfg["r_in"], seed)
            S = train_systems([prep], [micro], [trs], (), [basis], cfg["r_in"], k, cfg["steps_final"], seed, cfg["hidden"], dyn=dyn,
                              train_dyn=False, z_cov=z_cov, lam_norm=cfg["lam_norm"])[0][0]
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
