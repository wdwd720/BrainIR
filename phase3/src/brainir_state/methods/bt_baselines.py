"""Tuned BASELINE variants (independent baseline tuner, prefix bt; see notes/bt_baselines.md).

These are the declared baselines of PROTOCOL.md section 9 with the SAME model class as their authors' versions (lin_pcadyn, lin_dmdc,
lin_falds: notes/lin_methods.md; ks_hankel: notes/ks_methods.md; nn_aelin, nn_rssm, nn_seqbottleneck: notes/nn_baselines.md). Tuning
changes hyper-parameters, convergence, numerical robustness and generic selection rules only; every variant is a subclass or a
configured wrapper of the original and is a BASELINE, not a candidate method.

Common to every variant:
- no wall-clock-dependent branch: the originals' time budgets / deadlines are disabled (time_budget_s = inf); the amount of work is
  fixed by iteration counts, grids and convergence tolerances, so a fit is a deterministic function of (data, config, seed);
- the dimension rule of the original (generic, training / validation data only), with the tuned settings below;
- info() as in the original (k, k_range, abstain, n_params, train_cost) plus info()["tuning"][sid] (what the variant chose).

lin_falds_t   factor analysis + LDS (EM) with a causal steady-state Kalman encoder, as lin_falds, but the LDS EM runs TO CONVERGENCE
              (marginal log-likelihood gain per sample < em_tol, at most em_max_iters) in the dimension sweep AND the final fit
              (the original: 2 EM iterations in the sweep, 8 in the final fit), on all event-free windows of fixed length (not 24
              prefixes of <= 200 samples), and the Kalman FIR encoder is truncated at a 1e-6 tail (not 1e-4 / 400 lags). The EM
              E-step is batched over windows (equal-length windows share the filter / smoother covariances exactly), which is what
              makes convergence affordable; the estimator is unchanged.
ks_hankel_t   ks_hankel fitted at the data resolution (no decimation of finely sampled data), so its rollout is an exact Markov
              recursion on the data grid (benchmark v3 restart check); original selection space and rule. Identical to ks_hankel on
              the synthetic suites (stride 1).
lin_pcadyn_t, lin_dmdc_t, nn_aelin_t  DETERMINISM-ONLY variants (benchmark v3 enforces deterministic fits): the original method and
              settings with the wall-clock time budget / deadlines disabled. Identical to the original whenever the original's budget
              does not bind (every synthetic dev fit measured); on the real full circuits the original lin_pcadyn's CV deadline DID
              bind (fits of 740-760 s against a 660 s CV deadline), so the original is not deterministic there. No hyper-parameter
              was changed: the tried searches did not give a clear held-out gain (notes/bt_baselines.md; runs/bt/bt_explore.py).
nn_rssm and nn_seqbottleneck have NO variant (not tuned; both fail the v3 markov_ok check, which is a property of their model class).
"""

from __future__ import annotations

import numpy as np

from ..api import register
from .lin_baselines import (FALDSBasis, LinDMDc, LinFALDS, LinPCADyn, factor_analysis, kalman_fir, kalman_steady,  # noqa: F401
                            stabilise)
from .lin_fit import fit_dynamics_ls, latent_series, static_encoder

INF = float("inf")


# ==================================================================================================================== LDS EM (batched)
def free_windows_fixed(trajs, W: int, max_windows: int, seed: int):
    """Non-overlapping windows of W samples whose W - 1 transitions are all free (no event acting), from every trajectory (event-free
    stretches after an event count too). A seeded subset of at most max_windows windows. Returns X (S, W, N), U (S, W, n_u)."""
    Xs, Us = [], []
    for t in trajs:
        keep = np.asarray(t.keep, bool)
        n = len(t.xs)
        i = 0
        while i + W <= n:
            if keep[i: i + W - 1].all():
                Xs.append(t.xs[i: i + W]); Us.append(t.us[i: i + W])
                i += W
            else:
                bad = np.flatnonzero(~keep[i: i + W - 1])
                i += int(bad[-1]) + 1
    if not Xs:
        return None, None
    if len(Xs) > max_windows:
        sel = np.sort(np.random.default_rng(seed).choice(len(Xs), size=max_windows, replace=False))
        Xs = [Xs[j] for j in sel]; Us = [Us[j] for j in sel]
    return np.stack(Xs).astype(np.float64), np.stack(Us).astype(np.float64)


def lds_em_batched(X, U, C, d, psi, A, B, c, max_iters: int = 200, tol: float = 1e-5):
    """EM for x_t = C z_t + d + e (e ~ N(0, diag psi)), z_{t+1} = A z_t + B u_t + c + w (w ~ N(0, Q)) on S windows of equal length W
    (X (S, W, N), U (S, W, n_u)). Same model and M-step as lin_baselines.lds_em; the E-step (Kalman filter + RTS smoother) is batched
    over windows: the initial covariance is common, so every filter / smoother covariance is common to all windows. Iterates until
    the marginal log-likelihood gain per observed sample is below tol (or max_iters). Returns (A, B, c, Q, C, d, psi, report)."""
    S, W, N = X.shape
    k, nu = A.shape[0], B.shape[1]
    Q = np.eye(k) * 0.1
    ll_hist = []
    n_obs = S * W
    for it in range(max_iters):
        Ri = 1.0 / psi
        CtRi = (C * Ri[:, None]).T                          # (k, N)
        CtRiC = CtRi @ C
        Pinit = np.linalg.inv(CtRiC + 1e-6 * np.eye(k)) + np.eye(k) * 1e-3
        m = np.linalg.solve(CtRiC + 1e-6 * np.eye(k), CtRi @ (X[:, 0] - d).T).T        # (S, k)
        Pm = Pinit
        mu_p = np.zeros((W, S, k)); mu_f = np.zeros((W, S, k))
        P_p = np.zeros((W, k, k)); P_f = np.zeros((W, k, k))
        ll = 0.0
        logdetR = float(np.sum(np.log(psi)))
        for t in range(W):
            mu_p[t], P_p[t] = m, Pm
            Pi = np.linalg.inv(Pm)
            M = Pi + CtRiC
            Pf = np.linalg.inv(M)
            e = X[:, t] - d - m @ C.T                        # innovation (S, N)
            a = e @ CtRi.T                                   # C^T R^-1 e (S, k)
            # log N(e; 0, C Pm C^T + R) by the matrix determinant lemma / Woodbury identity
            _, ld_P = np.linalg.slogdet(Pm)
            _, ld_M = np.linalg.slogdet(M)
            quad = np.einsum("sn,n,sn->s", e, Ri, e) - np.einsum("sk,kl,sl->s", a, Pf, a)
            ll += float(-0.5 * (S * (logdetR + ld_P + ld_M + N * np.log(2 * np.pi)) + quad.sum()))
            # information-form update: mf = Pf (Pi m + C^T R^-1 (x - d)) = m + Pf C^T R^-1 (x - d - C m)
            mf = m + a @ Pf.T
            mu_f[t], P_f[t] = mf, Pf
            m = mf @ A.T + U[:, t] @ B.T + c
            Pm = A @ Pf @ A.T + Q
        ll_hist.append(ll / n_obs)
        # RTS smoother (common gains)
        mu_s = mu_f.copy(); P_s = P_f.copy(); Pc = np.zeros((W - 1, k, k))
        for t in range(W - 2, -1, -1):
            J = P_f[t] @ A.T @ np.linalg.inv(P_p[t + 1])
            mu_s[t] = mu_f[t] + (mu_s[t + 1] - mu_p[t + 1]) @ J.T
            P_s[t] = P_f[t] + J @ (P_s[t + 1] - P_p[t + 1]) @ J.T
            Pc[t] = P_s[t + 1] @ J.T
        # sufficient statistics
        Ez = mu_s                                           # (W, S, k)
        Z0, Z1 = Ez[:-1].reshape(-1, k), Ez[1:].reshape(-1, k)
        U0 = np.transpose(U[:, :-1], (1, 0, 2)).reshape(-1, nu)
        Szz = Z0.T @ Z0 + S * P_s[:-1].sum(0)
        Sz1z = Z1.T @ Z0 + S * Pc.sum(0)
        Sz1z1 = Z1.T @ Z1 + S * P_s[1:].sum(0)
        Szu, Sz1u, Suu = Z0.T @ U0, Z1.T @ U0, U0.T @ U0
        Sz, Sz1, Su = Z0.sum(0), Z1.sum(0), U0.sum(0)
        n = len(Z0)
        Zall = Ez.reshape(-1, k)
        Xall = np.transpose(X, (1, 0, 2)).reshape(-1, N)
        Szz_all = Zall.T @ Zall + S * P_s.sum(0)
        Sxz, Sx, Sz_all, Sxx = Xall.T @ Zall, Xall.sum(0), Zall.sum(0), (Xall ** 2).sum(0)
        mm = len(Zall)
        # M-step (as lin_baselines.lds_em)
        Mx = np.zeros((k + nu + 1, k + nu + 1))
        Mx[:k, :k] = Szz; Mx[:k, k:k + nu] = Szu; Mx[:k, -1] = Sz
        Mx[k:k + nu, :k] = Szu.T; Mx[k:k + nu, k:k + nu] = Suu; Mx[k:k + nu, -1] = Su
        Mx[-1, :k] = Sz; Mx[-1, k:k + nu] = Su; Mx[-1, -1] = n
        Rhs = np.hstack([Sz1z, Sz1u, Sz1[:, None]])
        Wd = np.linalg.solve(Mx + 1e-8 * np.trace(Mx) / len(Mx) * np.eye(len(Mx)), Rhs.T).T
        A, B, c = stabilise(Wd[:, :k], 0.9999), Wd[:, k:k + nu], Wd[:, -1]
        Q = (Sz1z1 - Wd @ Rhs.T) / n
        Q = (Q + Q.T) / 2 + 1e-6 * np.trace(Q) / k * np.eye(k)
        w_, V_ = np.linalg.eigh(Q)
        Q = V_ @ np.diag(np.maximum(w_, 1e-6 * max(w_.max(), 1e-12))) @ V_.T
        Mz = np.zeros((k + 1, k + 1)); Mz[:k, :k] = Szz_all; Mz[:k, -1] = Sz_all; Mz[-1, :k] = Sz_all; Mz[-1, -1] = mm
        Wo = np.linalg.solve(Mz + 1e-8 * np.eye(k + 1), np.hstack([Sxz, Sx[:, None]]).T).T
        C, d = Wo[:, :k], Wo[:, -1]
        psi = np.maximum((Sxx - np.einsum("ij,ij->i", Wo, np.hstack([Sxz, Sx[:, None]]))) / mm, 1e-4 * np.mean(Sxx / mm) + 1e-8)
        if len(ll_hist) >= 2 and abs(ll_hist[-1] - ll_hist[-2]) < tol:
            break
    rep = {"em_iters": len(ll_hist), "ll_per_sample": ll_hist[-1] if ll_hist else None,
           "converged": bool(len(ll_hist) >= 2 and abs(ll_hist[-1] - ll_hist[-2]) < tol), "n_windows": int(S), "window": int(W)}
    return A, B, c, Q, C, d, psi, rep


class FALDSBasisT(FALDSBasis):
    """FALDSBasis with the LDS EM run to convergence on all free fixed-length windows (same estimator, same encoder form)."""

    def encoder(self, k: int) -> dict:
        if k in self._cache:
            return self._cache[k]
        cfg = self.cfg
        C, d, psi = factor_analysis(self.X, k, seed=self.seed)
        Pi = 1 / psi
        beta = np.linalg.solve(np.eye(k) + (C.T * Pi) @ C, (C.T * Pi))
        enc0 = static_encoder(beta, -beta @ d)
        Zt, Ut, Zn = [], [], []
        for t in self.trajs:
            Z = latent_series(enc0, t)
            ii = np.flatnonzero(t.keep)
            Zt.append(Z[ii]); Ut.append(t.us[ii].astype(np.float64)); Zn.append(Z[ii + 1])
        A, B, c = fit_dynamics_ls(np.concatenate(Zt), np.concatenate(Ut), np.concatenate(Zn), 1e-6)
        A = stabilise(A, 0.9999)
        T_len = int(np.median([len(t.xs) for t in self.trajs]))
        W = max(20, int(round(cfg.get("em_window_frac", 0.25) * T_len)))
        X, U = free_windows_fixed(self.trajs, W, int(cfg.get("em_max_windows", 256)), self.seed)
        rep = {"em_iters": 0}
        if X is not None and int(cfg.get("em_max_iters", 200)) > 0:
            A, B, c, Q, C, d, psi, rep = lds_em_batched(X, U, C, d, psi, A, B, c, max_iters=int(cfg.get("em_max_iters", 200)),
                                                        tol=float(cfg.get("em_tol", 1e-5)))
        else:
            R_ = np.concatenate(Zn) - np.concatenate(Zt) @ A.T - np.concatenate(Ut) @ B.T - c
            Q = np.cov(R_.T).reshape(k, k)
        _, Kf = kalman_steady(A, C, Q, np.diag(psi))
        enc = kalman_fir(A, B, c, C, d, Kf, tol=float(cfg.get("fir_tol", 1e-6)), max_len=int(cfg.get("fir_max_len", 4000)))
        enc["_lds"] = {"A": A, "B": B, "c": c, "C": C, "d": d, "psi": psi, "Q": Q, "Kf": Kf, "em": rep}
        self._cache[k] = enc
        return enc


class _NoClockLin:
    """Mixin: the lin pipeline's CV / refinement deadlines are disabled (no wall-clock-dependent branch)."""

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        cfg = {**(config or {}), "time_budget_s": INF}
        model = super().fit(train, systems=systems, config=cfg, sim=sim, seed=seed)
        tun = {}
        for sid, dg in (model._info.get("diagnostics") or {}).items():
            tun[sid] = {"k_selected": dg.get("k_selected"), "curve_len": len(dg.get("curve") or {}), "selected_score": dg.get("selected_score")}
        model._info["tuning"] = tun
        return model


@register
class LinFALDST(_NoClockLin, LinFALDS):
    """lin_falds with the LDS EM run to convergence (sweep and final fit); see the module docstring."""
    name = "lin_falds_t"
    version = "1"
    default_config = {**LinFALDS.default_config, "em_max_iters": 200, "em_tol": 1e-5, "em_window_frac": 0.25, "em_max_windows": 256,
                      "fir_tol": 1e-6, "fir_max_len": 4000}

    def make_basis(self, P, trajs, kmax, cfg, seed):
        return FALDSBasisT(P, trajs, kmax, cfg, seed)

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        model = super().fit(train, systems=systems, config=config, sim=sim, seed=seed)
        for sid, e in model.sys.items():
            em = (e["enc"].get("_lds") or {}).get("em")
            if em is not None:
                model._info["tuning"].setdefault(sid, {})["em_final"] = em
        return model


# ==================================================================================================================== ks_hankel_t
from . import ks_core as KC  # noqa: E402
from .ks_abstain import abstention as ks_abstention  # noqa: E402
from .ks_hankel import HankelModel, KSHankel, fit_hankel_system  # noqa: E402


@register
class KSHankelT(KSHankel):
    """ks_hankel fitted at the DATA resolution (decimate: False). The original decimates finely sampled data (real: 1 ms -> 5 ms model
    grid) and linearly interpolates the latent between grid points, so a restart from a predicted z between grid points does not
    reproduce its rollout; at the data resolution the rollout is an exact Markov recursion z_{t+1} = A z_t + B u_t + c (+ events)
    on the data grid (benchmark v3 check). Synthetic data (stride 1) are unaffected: identical to ks_hankel.
    The selection space and rule are the ORIGINAL ones by default. The fit loop also accepts a wider search (lam_grid, r_grid,
    extended k_grid, max_val): it was tried on the dev subset (notes/bt_baselines.md, 'ks_hankel_x') and NOT adopted.
    No wall-clock-dependent branch exists in ks_hankel (none added)."""
    name = "ks_hankel_t"
    version = "1"
    default_config = {**KSHankel.default_config, "lam_grid": (1e-4,), "r_grid": (24,), "decimate": False}

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        KC.set_threads(3)
        cfg = {**self.default_config, **(config or {})}
        if cfg.get("sharing", "auto") not in self.supported_sharing:
            raise NotImplementedError("ks_hankel_t fits independent models only")
        if cfg.get("adapt_from") is not None:
            raise NotImplementedError("ks_hankel_t does not support encoder-only adaptation")
        timer = KC.Timer()
        model = HankelModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                "sharing": {"mode": "independent", "verdict": None}, "dim_curve": {}, "config": {}, "tuning": {}}
        n_tr = 0
        for sid in sorted({t.system_id for t in train}):
            trs0 = [t for t in train if t.system_id == sid]
            trs = KC.decimate(trs0) if cfg["decimate"] else list(trs0)
            entry = systems[sid]
            T = int(np.median([len(t.t) for t in trs]))
            configs = []
            for L in cfg["L_grid"]:
                if L == 1:
                    configs.append((1, 1))
                    continue
                for sf in cfg["span_frac"]:
                    configs.append((L, max(1, int(round(sf * T / (L - 1))))))
            configs = sorted(set(configs))
            forced = cfg.get("k")
            k_grid = [int(forced)] if forced else list(cfg["k_grid"])
            lam_rank = {lam: i for i, lam in enumerate(sorted(cfg["lam_grid"], reverse=True))}     # larger ridge = simpler
            units: dict = {}
            for fi, va in KC.draw_folds(trs, cfg["n_folds"], seed, cfg["max_val"]):
                prep = KC.SystemPrep(sid, fi, entry)
                micro = KC.MicroModel(prep, fi, seed=seed)
                for (L, d) in configs:
                    for r in cfg["r_grid"]:
                        for lam in cfg["lam_grid"]:
                            fits = fit_hankel_system(sid, fi, entry, L, d, k_grid, r, lam=lam, seed=seed, prep=prep, micro=micro)
                            for k, S in fits.items():
                                model.sys[sid] = S
                                e = KC.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True)
                                units.setdefault((k, L, d, r, lam), []).extend(e.tolist())
            table = KC.table_from_units(units, lambda c: (c[0], c[0] * c[1], c[2], lam_rank[c[3]]), cfg["rel_tol"])
            ks = sorted(table)
            sel = KC.select_from_table(table, cfg["rel_tol"])
            k = sel["k"]
            L, d, r, lam = table[k]["conf"]
            prep_f = KC.SystemPrep(sid, trs, entry)
            micro_f = KC.MicroModel(prep_f, trs, seed=seed)
            S = fit_hankel_system(sid, trs, entry, L, d, [k], r, lam=lam, seed=seed, prep=prep_f, micro=micro_f)[k]
            model.sys[sid] = S
            model.k[sid] = int(S["Tk"].shape[1])
            sil_res = model.choose_silence_mode(sid, trs, prep_f.y_var)
            curve = [{"k": kk, "val_nmse": table[kk]["val_nmse"], "se": table[kk]["se"], "L": table[kk]["conf"][0],
                      "d": table[kk]["conf"][1], "r": table[kk]["conf"][2], "lam": table[kk]["conf"][3]} for kk in ks]
            info["k"][sid] = model.k[sid]
            info["k_range"][sid] = sel["range"]
            info["dim_curve"][sid] = curve
            info["abstain"][sid] = ks_abstention(curve, sel, prep_f.N, forced=bool(forced))
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
            info["n_params"]["transition"] += S["n_params"]["transition"]
            info["config"][sid] = {"L": L, "d": d, "r_pca": r, "lam": lam, "silence_mode": S["silence_mode"], "silence_errors": sil_res,
                                   "gamma": micro_f.gamma, "micro_r2": micro_f.r2, "decimated": bool(cfg["decimate"])}
            info["tuning"][sid] = {"k": int(k), "L": int(L), "d": int(d), "r_pca": int(r), "lam": float(lam), "gain": S.get("gain")}
            n_tr += len(trs)
        info["train_cost"] = {"cpu_s": timer.cpu(), "wall_s": timer.wall(), "sim_calls": 0, "n_trajectories": n_tr}
        info["lipschitz_bound"] = None
        model._info = info
        return model


# ==================================================================================================================== determinism-only
@register
class LinPCADynT(_NoClockLin, LinPCADyn):
    """lin_pcadyn with no wall-clock-dependent branch (original settings)."""
    name = "lin_pcadyn_t"
    version = "1"


@register
class LinDMDcT(_NoClockLin, LinDMDc):
    """lin_dmdc with no wall-clock-dependent branch (original settings)."""
    name = "lin_dmdc_t"
    version = "1"


from .nn_baselines import NNAELin  # noqa: E402

NO_CLOCK = 1e12      # the nn pipeline's time budget / deadlines pushed out of reach: the iteration counts fix the work


@register
class NNAELinT(NNAELin):
    """nn_aelin with no wall-clock-dependent branch (original schedule: 250 x batch 256 per k, 100 refinement iterations)."""
    name = "nn_aelin_t"
    version = "1"
    model_name = "nn_aelin_t"
    default_config = dict(NNAELin.default_config, time_budget_s=NO_CLOCK)

    def fit(self, train, *, systems, config=None, sim=None, seed=0, log=None):
        cfg = {**self.default_config, **(config or {})}
        m = super().fit(train, systems=systems, config=cfg, sim=sim, seed=seed, log=log)
        m.meta["tuning"] = {s_: {"time_budget_s": cfg["time_budget_s"], "iters": cfg["iters"], "sweep_iters": cfg.get("sweep_iters"),
                                 "refine_iters": cfg.get("refine_iters"), "val_nmse": (m.meta.get("val_nmse") or {}).get(s_)}
                            for s_ in (m.meta.get("k") or {})}
        return m
