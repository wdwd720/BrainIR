"""Generic fitting pipeline shared by every lin_ method.

A concrete method supplies `make_basis(P, trajs, kmax, cfg, seed)`: an object whose `encoder(k)` returns the causal encoder of
dimension k (and optional diagnostics such as a singular-value spectrum and a spectral order bound `k_bound`). The pipeline:

1. prepare each system (standardisation from its training trajectories; free-transition masks; events);
2. DIMENSION RULE (generic, data only): cross-validated multi-horizon readout NMSE of event-free rollouts, by trajectory (the
   `val` split when it holds >= 30 trajectories, else 4-fold CV over train + val), for the k of a grid up to min(64, N).
   k = the smallest k whose paired excess over the best k is <= max(1 SE, 1 % of the best) and <= 5 % of the best score
   (`lin_fit.one_se_rule`, a practical-equivalence one-standard-error rule); k_range = the contiguous range within 2 SE / 10 %.
   Methods with a spectral order bound (`bound_grid`: CVA canonical correlations, Hankel singular values) score k <= bound first
   and extend the grid while the rule keeps choosing the largest k scored;
3. final fit on all trajectories at the selected k: least-squares transition (stabilised), decoder, readout, optional
   prediction-error refinement / closure (method hook `refine`), event operators;
4. ABSTENTION RULE ("no compact state under current evidence") when (a) N >= 10 and k > max(1, N / 5); or (b) the rule chose the
   largest k tried while that is below N (no plateau); or (c) the CV error at k exceeds 0.25 AND is not below 0.5 x the CV error of
   the input-history control (refmodels.DirectHorizonModel 'input_only', refitted per fold).

Sharing (config 'sharing'): 'independent'; 'shared' (one transition A, c and, when input dimensions agree, B for all systems,
with system-specific encoders / decoders / readouts; latents aligned to a reference system by the similarity transform that best
conjugates each system's own dynamics to the reference, then jointly refined); 'partial' (shared A only; B, c per system);
'auto' (independent vs shared compared by cross-validated error: shared when non-inferior within 10 % on every system).
Adaptation (config 'adapt_from'): the transition of a fitted model is frozen; each new system gets its own basis at the
model's k, aligned to the frozen dynamics, then only its readout (and input map if dimensions differ) is refitted.
"""

from __future__ import annotations

import copy
import time

import numpy as np

from ..api import StateMethod
from .lin_core import LinStateModel, PTraj, SysPrep, fit_readout, prepare_system, ridge_solve, thread_limit
from .lin_fit import (burn_in, eval_grid, fit_decoder, fit_dynamics_ls, fit_event_operators, free_windows, k_range_from_curve,
                      latent_series, one_se_rule, pem_refine, readout_data, score_windows, stabilise, transition_pairs, y_scale)

K_GRID = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16, 20, 24, 28, 32, 40, 48, 56, 64]


def make_folds(P: SysPrep, n_folds: int, seed: int) -> list[tuple[list[PTraj], list[PTraj]]]:
    val = [t for t in P.trajs if t.split == "val"]
    tr = [t for t in P.trajs if t.split != "val"]
    if len(val) >= 30 and len(tr) >= 10:
        return [(tr, val)]
    rng = np.random.default_rng(seed)
    perm = rng.permutation(len(P.trajs))
    folds = []
    for f in range(n_folds):
        va = set(perm[f::n_folds].tolist())
        folds.append(([t for i, t in enumerate(P.trajs) if i not in va], [t for i, t in enumerate(P.trajs) if i in va]))
    return folds


class LinMethodBase(StateMethod):
    name = "lin_base"
    version = "1"
    default_config: dict = {"k_max": 64, "n_folds": 4, "rel_tol": 0.05, "readout": "linear", "pem": False, "pem_steps": 300,
                            "pem_horizon_frac": 0.25, "closure": False, "ridge_dyn": 1e-6, "ridge_ro": 1e-4, "abstain_gain": 0.5,
                            "abstain_nmse": 0.25, "sim_units": 250, "sim_max_twins": 24, "time_budget_s": 1200.0}
    supported_sharing = ("auto", "independent", "shared", "partial")
    supports_adaptation = True
    bound_grid = False

    # ------------------------------------------------------------------------------------------------ hooks
    def make_basis(self, P: SysPrep, trajs: list[PTraj], kmax: int, cfg: dict, seed: int):
        raise NotImplementedError

    def refine(self, model: LinStateModel, sid: str, P: SysPrep, trajs: list[PTraj], cfg: dict, seed: int, budget_s: float) -> dict:
        """Final-fit refinement (prediction-error / closure). Default: PEM when cfg['pem']."""
        if not cfg.get("pem"):
            return {}
        H = max(2, int(round(cfg["pem_horizon_frac"] * P.T_len)))
        return pem_refine(model, [sid], {sid: P}, {sid: trajs}, H=min(H, 128), steps=cfg["pem_steps"], seed=seed,
                          time_budget_s=budget_s)

    def shared_refine(self, model: LinStateModel, sids: list[str], preps: dict, cfg: dict, seed: int) -> dict:
        """Joint refinement of a shared transition (default: joint prediction-error refinement when cfg['pem'])."""
        if not cfg.get("pem"):
            return {}
        H = max(2, int(round(cfg["pem_horizon_frac"] * min(preps[s].T_len for s in sids))))
        return pem_refine(model, sids, preps, {s: preps[s].trajs for s in sids}, H=min(H, 128), steps=cfg["pem_steps"], seed=seed,
                          time_budget_s=cfg["time_budget_s"] / 2)

    def k_grid(self, kmax: int) -> list[int]:
        return [k for k in K_GRID if k <= kmax] or [1]

    # ------------------------------------------------------------------------------------------------ building blocks
    def build_single(self, P: SysPrep, trajs: list[PTraj], enc: dict, cfg: dict, seed: int, readout: str | None = None) -> LinStateModel:
        """Least-squares model of one system for a given encoder (no refinement): transition, decoder, readout."""
        sid = P.sid
        m = LinStateModel(self.name, self.version)
        Zt, Ut, Zn = transition_pairs(enc, trajs)
        A, B, c = fit_dynamics_ls(Zt, Ut, Zn, cfg["ridge_dyn"])
        A = stabilise(A, 1.0)
        C, d, xres = fit_decoder(enc, trajs)
        Z, U, Y = readout_data(enc, trajs)
        ro = fit_readout(Z, U, Y, readout or cfg["readout"], cfg["ridge_ro"], seed)
        m.sys[sid] = self._sys_entry(P, enc, B, C, d, xres, ro)
        m.dyn[sid] = {"A": A, "c": c, "nl": None}
        m.k[sid] = enc["Hx"][0].shape[0]
        return m

    @staticmethod
    def _sys_entry(P: SysPrep, enc, Bs, C, d, xres, ro, targets=None) -> dict:
        return {"mx": P.mx, "sx": P.sx, "mu": P.mu, "su": P.su, "col": dict(P.col), "obs": list(P.obs), "nonneg": P.nonneg,
                "enc": enc, "Bs": Bs, "C": C, "d": d, "xres": xres, "ro": ro, "targets": list(targets or []),
                "ev": {"kinds": ()}}

    def input_only_scores(self, P: SysPrep, folds, horizons, starts, scale, cfg) -> dict:
        """k = 0 control inside the dimension curve: the evaluator's input-history predictor (refmodels.DirectHorizonModel
        'input_only', y(t+h) from lagged inputs and time since input onset), fitted on each fold's training trajectories and
        scored on the same held-out windows as the latent models."""
        from types import SimpleNamespace

        from ..refmodels import DirectHorizonModel

        def raw(t):
            u = t.us.astype(np.float64) * P.su + P.mu
            return SimpleNamespace(t=np.arange(len(u)) * P.dt, u=u, y=t.y, dt=P.dt, key=t.key)

        out = {}
        H = max(horizons)
        for tr, va in folds:
            try:
                m = DirectHorizonModel("input_only", horizons_s=(H * P.dt,)).fit(P.sid, [raw(t) for t in tr])
            except Exception:
                continue
            for t in va:
                ws = free_windows(t, H, starts, 0)
                if not ws:
                    continue
                r = raw(t)
                errs = []
                for i0 in ws:
                    z0 = m.encode(P.sid, None, r.u[: i0 + 1], P.dt)
                    yp = np.asarray(m.rollout(P.sid, z0, r.u[i0: i0 + H + 1], [], P.dt)["y"], float)
                    e = (yp - t.y[i0: i0 + H + 1]) ** 2 / scale
                    errs.append([float(e[1: h + 1].mean()) for h in horizons])
                out[t.key] = float(np.mean(errs))
        return out

    def cv_curve(self, P: SysPrep, cfg: dict, seed: int, k_forced: int | None = None) -> dict:
        """Cross-validated free-run scores per k. Methods with a spectral order bound (bound_grid) score k <= bound first and
        extend the grid while the selection rule keeps choosing the largest k scored (the bound starts the search; it does not
        cap it)."""
        folds = make_folds(P, cfg["n_folds"], seed)
        horizons, starts = eval_grid(P)
        scale = y_scale(P, P.trajs)
        # the grid is capped by each basis' own maximum (N for instantaneous bases, N x lags for history encoders)
        kmax = int(cfg["k_max"])
        bases, k_bounds, diag = [], [], {}
        for fi, (tr, va) in enumerate(folds):
            basis = self.make_basis(P, tr, kmax, {**cfg, "_in_cv": True}, seed + fi)
            bases.append(basis)
            k_bounds.append(max(1, int(getattr(basis, "k_bound", kmax))))
            if fi == 0:
                diag = dict(getattr(basis, "diag", {}) or {})
        kb_all = int(min([kmax] + [int(getattr(b, "k_max", kmax)) for b in bases]))
        full_grid = self.k_grid(kb_all)
        grid_top = max(full_grid)
        k_bound = int(np.median(k_bounds)) if k_bounds else kmax
        scores: dict[int, dict] = {}

        def score(k):
            for fi, (tr, va) in enumerate(folds):
                m = self.build_single(P, tr, bases[fi].encoder(k), cfg, seed)
                scores.setdefault(k, {}).update(score_windows(m, P.sid, P, va, horizons, starts, scale))

        deadline = cfg.get("_deadline_cv")

        def late():
            # time budget: at least two k are always scored, then the sweep stops when the CV share of the budget is spent
            return deadline is not None and len(scores) >= 2 and time.time() > deadline

        if k_forced:
            score(int(k_forced))
        elif self.bound_grid:
            for k in [k for k in full_grid if k <= k_bound] or [full_grid[0]]:
                if late():
                    break
                score(k)
            rest = [k for k in full_grid if k > max(scores)]
            while rest and not late():
                k_sel, _, _ = one_se_rule(scores, cfg["rel_tol"])
                if k_sel < max(scores):
                    break
                score(rest.pop(0))
        else:
            for k in full_grid:
                if late():
                    break
                score(k)
        return {"scores": scores, "diag": diag, "k_bound": k_bound, "horizons": horizons, "starts": starts, "scale": scale,
                "folds": folds, "grid_top": grid_top, "k_possible": kb_all}

    # ------------------------------------------------------------------------------------------------ independent fit
    def fit_system(self, P: SysPrep, cfg: dict, seed: int, targets, k_forced: int | None, t_budget: float) -> tuple[LinStateModel, dict]:
        t0 = time.time()
        cfg = {**cfg, "_deadline_cv": t0 + 0.55 * t_budget}
        cv = self.cv_curve(P, cfg, seed, k_forced)
        scores = cv["scores"]
        if k_forced:
            k_sel = k_best = int(k_forced)
            curve = {k_sel: {"score": float(np.mean(list(scores[k_sel].values()))) if scores.get(k_sel) else float("nan")}}
            k_lo = k_hi = k_sel
        else:
            k_sel, k_best, curve = one_se_rule(scores, cfg["rel_tol"])
            k_lo, k_hi = k_range_from_curve(curve, k_sel, k_best, cfg["rel_tol"])
        s0 = self.input_only_scores(P, cv["folds"], cv["horizons"], cv["starts"], cv["scale"], cfg)
        # readout class (method option 'auto': linear vs quadratic by the same CV at the selected k)
        ro_kind = cfg["readout"]
        if ro_kind == "auto" and time.time() > cfg["_deadline_cv"]:
            ro_kind = "linear"                   # out of CV time: the simpler readout
        if ro_kind == "auto":
            ro_err = {}
            for kind in ("linear", "quad"):
                sc = {}
                for fi, (tr, va) in enumerate(cv["folds"]):
                    basis = self.make_basis(P, tr, int(cfg["k_max"]), cfg, seed + fi)
                    m = self.build_single(P, tr, basis.encoder(k_sel), cfg, seed, readout=kind)
                    sc.update(score_windows(m, P.sid, P, va, cv["horizons"], cv["starts"], cv["scale"]))
                ro_err[kind] = float(np.mean(list(sc.values()))) if sc else np.inf
            # the quadratic readout must beat the linear one by 3 %
            ro_kind = "quad" if ro_err["quad"] < 0.97 * ro_err["linear"] else "linear"
        # final fit on all trajectories
        basis = self.make_basis(P, P.trajs, int(cfg["k_max"]), cfg, seed)
        enc = basis.encoder(k_sel)
        model = self.build_single(P, P.trajs, enc, cfg, seed, readout=ro_kind)
        model.sys[P.sid]["targets"] = list(targets or [])
        ref = self.refine(model, P.sid, P, P.trajs, cfg, seed, max(30.0, t_budget - (time.time() - t0)))
        fit_event_operators(model, P.sid, P, P.trajs, seed)
        # abstention
        keys = sorted(set(s0) & set(scores.get(k_sel, {})))
        s0m = float(np.mean([s0[u] for u in keys])) if keys else np.nan
        sk = float(np.mean([scores[k_sel][u] for u in keys])) if keys else np.nan
        grid_top = cv.get("grid_top", max(scores) if scores else k_sel)
        reasons = []
        if P.n_x >= 10 and k_sel > max(1, P.n_x / 5):
            reasons.append(f"selected k={k_sel} exceeds N/5={P.n_x / 5:.1f}")
        if not k_forced and k_sel == grid_top and grid_top < cv.get("k_possible", P.n_x) and len(scores) > 1:
            reasons.append("no plateau: the rule selected the largest k tried (below the basis dimension)")
        if np.isfinite(s0m) and np.isfinite(sk) and sk > (1 - cfg["abstain_gain"]) * s0m and sk > cfg["abstain_nmse"]:
            reasons.append(f"latent model error {sk:.3g} not below {(1 - cfg['abstain_gain']):.2f} x input-only {s0m:.3g}")
        diag = {"k_selected": int(k_sel), "k_best": int(k_best), "k_range": [int(k_lo), int(k_hi)], "curve": {int(k): v for k, v in curve.items()},
                "input_only_score": s0m, "selected_score": sk, "k_bound": int(cv["k_bound"]), "readout": ro_kind,
                "abstain_reasons": reasons, "basis": cv["diag"], "refine": ref, "n_units": len(keys),
                "fit_seconds": time.time() - t0, "events": {kk: (float(v) if np.isscalar(v) else None) for kk, v in model.sys[P.sid]["ev"].items()
                                                             if kk in ("gamma", "sil_w", "alpha_sil", "R_gain", "kick_scale", "rel_scale", "cpl_scale")}}
        return model, diag

    # ------------------------------------------------------------------------------------------------ fit
    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        with thread_limit(3):
            np.random.seed(seed % (2 ** 32))
            by_sys: dict[str, list] = {}
            for tr in train:
                by_sys.setdefault(tr.system_id, []).append(tr)
            sids = sorted(by_sys)
            preps = {sid: prepare_system(sid, by_sys[sid], systems[sid]) for sid in sids}
            sim_info = request_twins(preps, by_sys, systems, sim, cfg)
            targets = {sid: [int(n) for n in (systems[sid].get("targets_public") or [])] for sid in sids}
            sharing = cfg.get("sharing", "auto") or "auto"
            if cfg.get("adapt_from") is not None:
                model, diags = self.adapt(cfg["adapt_from"], preps, targets, cfg, seed)
                mode = "adapted"
            elif len(sids) == 1 or sharing == "independent":
                model, diags = self.fit_independent(preps, targets, cfg, seed)
                mode = "independent"
            elif sharing in ("shared", "partial"):
                model, diags = self.fit_shared(preps, targets, cfg, seed, partial=(sharing == "partial"))
                mode = sharing
            elif sharing == "auto":
                model, diags, mode = self.fit_auto(preps, targets, cfg, seed)
            else:
                raise NotImplementedError(f"sharing={sharing!r}")
            self.finish_info(model, preps, diags, mode, cfg, time.time() - t0)
            model._info["train_cost"].update(sim_info)
        return model

    def fit_independent(self, preps, targets, cfg, seed):
        model = LinStateModel(self.name, self.version)
        diags = {}
        n = len(preps)
        for i, (sid, P) in enumerate(preps.items()):
            m, dg = self.fit_system(P, cfg, seed, targets[sid], cfg.get("k"), cfg["time_budget_s"] / n)
            model.sys[sid] = m.sys[sid]; model.dyn[sid] = m.dyn[sid]; model.k[sid] = m.k[sid]
            diags[sid] = dg
        return model, diags

    # ------------------------------------------------------------------------------------------------ sharing
    def fit_shared(self, preps, targets, cfg, seed, partial: bool = False, k_common: int | None = None, indep=None):
        """One transition for all systems (see module docstring)."""
        if indep is None:
            indep_model, indep_diag = self.fit_independent(preps, targets, cfg, seed)
        else:
            indep_model, indep_diag = indep
        sids = sorted(preps)
        k = int(k_common or cfg.get("k") or int(np.max([indep_model.k[s] for s in sids])))
        k = int(min(k, min(preps[s].n_x for s in sids)))
        cfg = {**cfg, "_lags_by_sys": {s: tuple(indep_model.sys[s]["enc"]["lags"]) for s in sids if s in indep_model.sys}}
        # per-system models at the common k
        ms = {}
        for sid in sids:
            P = preps[sid]
            basis = self.make_basis(P, P.trajs, int(min(cfg["k_max"], P.n_x)), cfg, seed)
            ms[sid] = self.build_single(P, P.trajs, basis.encoder(min(k, P.n_x)), cfg, seed, readout=indep_diag[sid]["readout"])
        # reference: the system with the most training samples
        ref = max(sids, key=lambda s: sum(len(t.xs) for t in preps[s].trajs))
        if ms[ref].k[ref] < k:
            k = ms[ref].k[ref]
        Aref, Bref = ms[ref].dyn[ref]["A"], ms[ref].sys[ref]["Bs"]
        model = LinStateModel(self.name, self.version)
        shared_dyn = {"A": Aref.copy(), "c": ms[ref].dyn[ref]["c"].copy(), "nl": None}
        same_u = len({preps[s].n_u for s in sids}) == 1
        for sid in sids:
            m = ms[sid]
            e = m.sys[sid]
            if sid != ref and e["enc"]["Hx"][0].shape[0] == k:
                T = align_similarity(m.dyn[sid]["A"], e["Bs"], Aref, Bref if same_u else None, latent_cov(e["enc"], preps[sid].trajs),
                                     latent_cov(ms[ref].sys[ref]["enc"], preps[ref].trajs))
                e = transform_entry(e, T)
            model.sys[sid] = e
            model.dyn[sid] = shared_dyn
            model.k[sid] = k
        # pooled least squares of the shared transition on the aligned latents
        Zs, Us, Zn, S = [], [], [], []
        for i, sid in enumerate(sids):
            zt, ut, zn = transition_pairs(model.sys[sid]["enc"], preps[sid].trajs)
            Zs.append(zt); Us.append(ut); Zn.append(zn); S.append(np.full(len(zt), i))
        Zt, Ut, Znn, S = np.concatenate(Zs), np.concatenate(Us) if same_u else None, np.concatenate(Zn), np.concatenate(S)
        onehot = np.eye(len(sids))[S]
        if same_u and not partial:
            F = np.hstack([Zt, Ut, np.ones((len(Zt), 1))])
            W = ridge_solve(F, Znn, cfg["ridge_dyn"])
            shared_dyn["A"] = stabilise(W[:k].T.copy()); shared_dyn["c"] = W[-1].copy()
            for sid in sids:
                model.sys[sid]["Bs"] = W[k:-1].T.copy()
                model.sys[sid]["B_shared"] = True
        else:
            # shared A; per-system B and c
            Ulist = [transition_pairs(model.sys[sid]["enc"], preps[sid].trajs)[1] for sid in sids]
            nus = [u.shape[1] for u in Ulist]
            Ublk = np.zeros((len(Zt), sum(nus)))
            off = 0
            for i, u in enumerate(Ulist):
                Ublk[S == i, off: off + nus[i]] = u
                off += nus[i]
            F = np.hstack([Zt, Ublk, onehot])
            W = np.linalg.lstsq(F, Znn, rcond=None)[0]
            shared_dyn["A"] = stabilise(W[:k].T.copy())
            off = k
            per_c = {}
            for i, sid in enumerate(sids):
                model.sys[sid]["Bs"] = W[off: off + nus[i]].T.copy(); off += nus[i]
            for i, sid in enumerate(sids):
                per_c[sid] = W[off + i].copy()
            # system-specific offsets live in the per-system dict (the shared dict keeps c = 0)
            shared_dyn["c"] = np.zeros(k)
            for sid in sids:
                model.sys[sid]["c_sys"] = per_c[sid]
            model.partial = True
        # readouts refitted on the aligned latents; joint refinement
        for sid in sids:
            P = preps[sid]
            e = model.sys[sid]
            Z, U, Y = readout_data(e["enc"], P.trajs)
            e["ro"] = fit_readout(Z, U, Y, e["ro"].get("kind", "linear"), cfg["ridge_ro"], seed)
            e["targets"] = targets[sid]
        if not partial:
            self.shared_refine(model, sids, preps, cfg, seed)
        for sid in sids:
            fit_event_operators(model, sid, preps[sid], preps[sid].trajs, seed)
        diags = {}
        for sid in sids:
            lo, hi = (indep_diag[sid].get("k_range") or [k, k])
            diags[sid] = {**indep_diag[sid], "k_selected": k, "k_range": [int(min(lo, k)), int(max(hi, k))], "shared_reference": ref}
        return model, diags

    def fit_auto(self, preps, targets, cfg, seed):
        """Independent vs shared by cross-validated error on each system's held-out trajectories (shared fits use the same
        folds): 'shared' if its error is within 10 % of the independent error on every system."""
        indep = self.fit_independent(preps, targets, cfg, seed)
        sids = sorted(preps)
        k = int(np.max([indep[0].k[s] for s in sids]))
        # held-out comparison: refit both on each system's first fold
        worse = {}
        folds = {sid: make_folds(preps[sid], cfg["n_folds"], seed)[0] for sid in sids}
        sub = {sid: _sub_prep(preps[sid], folds[sid][0]) for sid in sids}
        cfg_nopem = {**cfg, "pem": False}
        mi, _ = self.fit_independent(sub, targets, {**cfg_nopem, "k": None}, seed)
        msh, _ = self.fit_shared(sub, targets, cfg_nopem, seed, k_common=k, indep=(mi, {s: {"readout": indep[1][s]["readout"]} for s in sids}))
        for sid in sids:
            P = preps[sid]
            horizons, starts = eval_grid(P)
            scale = y_scale(P, P.trajs)
            a = score_windows(mi, sid, P, folds[sid][1], horizons, starts, scale)
            b = score_windows(msh, sid, P, folds[sid][1], horizons, starts, scale)
            keys = sorted(set(a) & set(b))
            worse[sid] = (float(np.mean([b[u] for u in keys])) / max(1e-12, float(np.mean([a[u] for u in keys])))) if keys else np.inf
        if all(v <= 1.10 for v in worse.values()):
            model, diags = self.fit_shared(preps, targets, cfg, seed, k_common=k, indep=indep)
            for sid in sids:
                diags[sid]["sharing_ratio"] = worse[sid]
            return model, diags, "shared"
        model, diags = indep
        for sid in sids:
            diags[sid]["sharing_ratio"] = worse[sid]
        return model, diags, "independent"

    # ------------------------------------------------------------------------------------------------ adaptation
    def adapt(self, src: LinStateModel, preps, targets, cfg, seed):
        """Encoder-only adaptation: the source model's transition (A, c, closure, and B when input dimensions agree) is frozen."""
        ref_sid = sorted(src.sys)[0]
        dyn = src.dyn[ref_sid]
        k = int(src.k[ref_sid])
        Bref = src.sys[ref_sid]["Bs"]
        ref_cov = (getattr(src, "latent_cov", None) or {}).get(ref_sid)
        model = LinStateModel(self.name, self.version)
        diags = {}
        cfg = {**cfg, "_lags_by_sys": {sid: tuple(src.sys[ref_sid]["enc"]["lags"]) for sid in preps}}
        for sid, P in preps.items():
            basis = self.make_basis(P, P.trajs, int(min(cfg["k_max"], P.n_x)), cfg, seed)
            kk = min(k, P.n_x)
            m = self.build_single(P, P.trajs, basis.encoder(kk), cfg, seed)
            e = m.sys[sid]
            if kk == k:
                same_u = P.n_u == Bref.shape[1]
                T = align_similarity(m.dyn[sid]["A"], e["Bs"], dyn["A"], Bref if same_u else None, latent_cov(e["enc"], P.trajs), ref_cov)
                e = transform_entry(e, T)
                if same_u:
                    e["Bs"] = Bref.copy()
                else:
                    e["B_free"] = True
            model.sys[sid] = e
            model.dyn[sid] = dyn
            model.k[sid] = k
            Z, U, Y = readout_data(e["enc"], P.trajs)
            e["ro"] = fit_readout(Z, U, Y, src.sys[ref_sid]["ro"].get("kind", "linear"), cfg["ridge_ro"], seed)
            e["targets"] = targets[sid]
            H = max(2, int(round(cfg["pem_horizon_frac"] * P.T_len)))
            pem_refine(model, [sid], {sid: P}, {sid: P.trajs}, H=min(H, 128), steps=min(150, cfg["pem_steps"]), seed=seed,
                       freeze_dyn=True, time_budget_s=cfg["time_budget_s"] / max(1, len(preps)))
            fit_event_operators(model, sid, P, P.trajs, seed)
            diags[sid] = {"k_selected": k, "k_range": [k, k], "abstain_reasons": [], "adapted_from": ref_sid, "readout": e["ro"]["kind"]}
        return model, diags

    # ------------------------------------------------------------------------------------------------ info
    def finish_info(self, model: LinStateModel, preps, diags, mode, cfg, seconds):
        enc_p, ro_p, ks, kr, ab = {}, {}, {}, {}, {}
        seen = {}
        tr_p = 0
        lip = 0.0
        for sid, e in model.sys.items():
            k = int(model.k[sid])
            ks[sid] = k
            dg = diags.get(sid, {})
            kr[sid] = [int(x) for x in dg.get("k_range", [k, k])]
            enc_p[sid] = int(sum(h.size for h in e["enc"]["Hx"]) + (sum(h.size for h in e["enc"]["Hu"]) if e["enc"].get("Hu") is not None else 0) + k)
            ro_p[sid] = int(e["ro"]["G"].size + e["ro"]["h"].size)
            d = model.dyn[sid]
            if id(d) not in seen:
                seen[id(d)] = True
                tr_p += int(d["A"].size + d["c"].size)
                if d.get("nl") is not None:
                    tr_p += int(sum(v.size for kk, v in d["nl"].items() if kk in ("W1", "b1", "W2", "b2", "W3", "b3")))
                lip = max(lip, float(np.linalg.norm(d["A"], 2)))
            if not e.get("B_shared") or ("B", id(d)) not in seen:
                tr_p += int(e["Bs"].size)
                if e.get("B_shared"):
                    seen[("B", id(d))] = True
            reasons = dg.get("abstain_reasons", [])
            ab[sid] = {"no_compact_state": bool(reasons), "dimension_unresolved": None, "causal_equivalence_failed": False,
                       "reason": "; ".join(reasons) if reasons else ""}
        model._info = {"k": ks, "k_range": kr, "abstain": ab,
                       "n_params": {"encoder": enc_p, "transition": tr_p, "readout": ro_p},
                       "sharing": {"mode": mode, "verdict": ("supported" if mode == "shared" else ("rejected" if mode == "independent" and len(model.sys) > 1 else None))},
                       "train_cost": {"cpu_s": float(seconds), "sim_calls": 0, "adaptation": mode == "adapted"},
                       "lipschitz_bound": lip,
                       "diagnostics": _jsonable(diags)}
        model.latent_cov = {sid: latent_cov(model.sys[sid]["enc"], preps[sid].trajs) for sid in model.sys if sid in preps}


# ==================================================================================================================== simulation
def _unit_cost(sysinfo: dict) -> int:
    if sysinfo.get("kind") == "real":
        return 3 if sysinfo.get("mode") == "mech" else 10
    return 1


def request_twins(preps: dict, by_sys: dict, systems: dict, sim, cfg: dict) -> dict:
    """With a simulation client: request the event-free counterfactual twin (same protocol and noise seed, events removed) of
    training intervention trajectories, within cfg['sim_units'] budget units (spread over the systems; single-kind event
    trajectories first, in a deterministic order). Twins give the event-scale calibration the TRUE effect. Any refusal / error
    leaves the fit data-only."""
    info = {"sim_calls": 0, "sim_units": 0, "sim_twins": 0}
    if sim is None or float(cfg.get("sim_units", 250)) <= 0:
        return info
    budget = float(cfg.get("sim_units", 250))
    per_sys = budget / max(1, len(preps))
    reqs, owners = [], []
    for sid, P in preps.items():
        cost = _unit_cost(systems[sid])
        n_max = int(min(per_sys // cost, cfg.get("sim_max_twins", 24)))
        raw = {tr.key: tr for tr in by_sys[sid]}
        cands = [t for t in P.trajs if t.events and len({e["kind"] for e in t.events}) == 1
                 and t.events[0]["kind"] in ("kick", "current", "silence")]
        cands.sort(key=lambda t: (t.events[0]["kind"], t.key))
        # round-robin over kinds so every calibrated operator gets twins
        by_kind: dict = {}
        for t in cands:
            by_kind.setdefault(t.events[0]["kind"], []).append(t)
        order = []
        while any(by_kind.values()) and len(order) < n_max:
            for kd in sorted(by_kind):
                if by_kind[kd] and len(order) < n_max:
                    order.append(by_kind[kd].pop(0))
        for t in order:
            p = dict(raw[t.key].protocol)
            p["events"] = []
            reqs.append(p); owners.append((sid, t))
    if not reqs:
        return info
    try:
        out = sim.run(reqs)
        info["sim_calls"] = 1
    except Exception as ex:  # budget exhausted, service unavailable, refused protocols
        info["sim_error"] = repr(ex)[:200]
        return info
    for (sid, t), o in zip(owners, out or []):
        if not o or not o.get("ok"):
            continue
        y = np.asarray(o.get("y"), np.float64)
        if y.shape == t.y.shape and np.isfinite(y).all():
            t.twin_y = y
            info["sim_twins"] += 1
            info["sim_units"] += _unit_cost(systems[sid])
    return info


# ==================================================================================================================== alignment
def latent_cov(enc: dict, trajs: list[PTraj], max_rows: int = 50000) -> np.ndarray:
    Zs = []
    tot = sum(len(t.xs) for t in trajs)
    stride = max(1, tot // max_rows)
    for t in trajs:
        Zs.append(latent_series(enc, t)[::stride])
    Z = np.concatenate(Zs)
    return np.cov(Z.T).reshape(Z.shape[1], Z.shape[1])


def align_similarity(A_s, B_s, A_r, B_r, cov_s=None, cov_r=None, lam: float = 1.0) -> np.ndarray:
    """T (k x k) with z_ref ~ T z_s: least squares on T A_s - A_r T = 0 (conjugacy) and T B_s - B_r = 0 (input response; fixes
    scale), plus, when no input map is shared, T cov_s T^T ~ cov_r through a whitening initialisation. Solved as a linear system
    in vec(T) (Kronecker form)."""
    k = A_s.shape[0]
    I = np.eye(k)
    rows, rhs = [], []
    # vec(T A_s) = (A_s^T kron I) vec(T); vec(A_r T) = (I kron A_r) vec(T)  (column-major vec)
    rows.append(np.kron(A_s.T, I) - np.kron(I, A_r)); rhs.append(np.zeros(k * k))
    if B_r is not None and B_s is not None and B_s.shape == B_r.shape and np.linalg.norm(B_r) > 1e-9:
        nb = B_s.shape[1]
        w = lam * np.linalg.norm(rows[0]) / max(1e-9, np.linalg.norm(np.kron(B_s.T, I)))
        rows.append(w * np.kron(B_s.T, I)); rhs.append(w * B_r.reshape(-1, order="F"))
        M = np.vstack(rows); r = np.concatenate(rhs)
        vt = np.linalg.lstsq(M, r, rcond=None)[0]
        T = vt.reshape(k, k, order="F")
    else:
        T = None
    if T is None or not np.isfinite(T).all() or abs(np.linalg.det(T)) < 1e-10:
        # covariance matching: T = cov_r^{1/2} Q cov_s^{-1/2}, Q orthogonal chosen to best conjugate the whitened dynamics
        if cov_s is None or cov_r is None:
            return np.eye(k)
        Ws, Wr_inv = _msqrt_inv(cov_s), _msqrt(cov_r)
        As = Ws @ A_s @ np.linalg.inv(Ws)            # whitened source dynamics
        Ar = np.linalg.inv(Wr_inv) @ A_r @ Wr_inv    # whitened reference dynamics
        # Procrustes on the dynamics (Q As ~ Ar Q): iterate a few alternating Procrustes steps
        Q = np.eye(k)
        for _ in range(50):
            M = Ar.T @ Q @ As + Ar @ Q @ As.T + np.eye(k) * 1e-9
            U, _, Vt = np.linalg.svd(M)
            Q = U @ Vt
        T = Wr_inv @ Q @ Ws
    return T


def _msqrt(C):
    w, V = np.linalg.eigh((C + C.T) / 2)
    return V @ np.diag(np.sqrt(np.maximum(w, 1e-12))) @ V.T


def _msqrt_inv(C):
    w, V = np.linalg.eigh((C + C.T) / 2)
    return V @ np.diag(1 / np.sqrt(np.maximum(w, 1e-12))) @ V.T


def transform_entry(e: dict, T: np.ndarray) -> dict:
    """New latent z' = T z: encoder rows, decoder, input map and readout transformed consistently."""
    e = copy.deepcopy(e)
    Ti = np.linalg.inv(T)
    enc = e["enc"]
    enc["Hx"] = [T @ h for h in enc["Hx"]]
    if enc.get("Hu") is not None:
        enc["Hu"] = [T @ h for h in enc["Hu"]]
    enc["b"] = T @ enc["b"]
    e["C"] = e["C"] @ Ti
    e["Bs"] = T @ e["Bs"]
    ro = e["ro"]
    k = T.shape[0]
    if ro.get("kind", "linear") == "linear":
        ro["G"] = np.vstack([Ti.T @ ro["G"][:k], ro["G"][k:]])
    # nonlinear-feature readouts are refitted by the callers on the transformed latents
    return e


def _sub_prep(P: SysPrep, trajs: list[PTraj]) -> SysPrep:
    Q = copy.copy(P)
    Q.trajs = list(trajs)
    return Q


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist() if o.size <= 64 else f"array{o.shape}"
    return o
