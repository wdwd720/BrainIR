"""lin_balanced: balanced reduction from interventional (empirical) gramians of the permitted perturbations, with a learned
nonlinear closure of the reduced dynamics.

Mathematics.
1. High-order linear surrogate of the microstate in its principal subspace (r <= 64 axes of the standardised x):
       w_{t+1} = F w_t + E u_t + e,      y_t ~ Gw w_t + Gu u_t + h                       (least squares, ridge; rho(F) <= 1)
2. Interventional controllability gramian over the horizon H = T/4 (steps), from the perturbations the system permits:
       Wc = sum_{t<H} F^t [ Pi Pi^T / tr + Pk Pk^T / tr + Sigma_w / tr ] (F^t)^T
   Pi: input impulses (E, one column per input channel, 1 sd); Pk: unit (1 sd) kicks / currents on every public target neuron
   j, projected into the principal subspace (V[:, j]); Sigma_w: covariance of the visited states (natural variability).
   Each ensemble is normalised to unit trace, so none dominates by units.
   Observability gramian through the readout (outputs normalised by their training sd):
       Wo = sum_{t<H} (F^t)^T Gw^T S_y^-1 Gw F^t
   (for the linear surrogate these are exactly the empirical gramians of +-eps impulses / offsets; eps-independent).
3. Square-root balancing: Wc = Lc Lc^T, Wo = Lo Lo^T, Lo^T Lc = U S V^T; Hankel singular values sigma = diag(S);
       encoder z = S_k^{-1/2} U_k^T Lo^T w = T_k V x_s   (static, linear),  reconstruction w ~ Lc V_k S_k^{-1/2} z.
   Order bound k_bound = smallest k with sum_{i>k} sigma_i <= 1 % of sum sigma (a tail bound on the H-infinity error of the
   surrogate, 2 sum_{i>k} sigma_i); the dimension rule of lin_base then chooses k <= min(k_bound, 16) by the cross-validated
   free-run plateau OF THE FULL MODEL CLASS (reduced linear part + closure).
4. Closure: z_{t+1} = A z_t + B u_t + c + N(z_t, u_t), N = tanh MLP (one hidden layer, 32 units, output initialised at 0), trained
   jointly with A, B, c and the readout by the multi-step prediction-error objective (latent + readout, horizons up to T/4) with
   held-out acceptance: if the closure does not improve held-out multi-step error the linear reduced model is kept.
Events as for every lin_ model (lin_core): kicks and currents through the encoder, silencing / edge removal through the decoder and
the read-in map. Deterministic given the seed.
"""

from __future__ import annotations

import time

import numpy as np

from ..api import register
from .lin_base import LinMethodBase
from .lin_baselines import delay_pca
from .lin_core import PTraj, SysPrep, pca_basis, ridge_solve
from .lin_fit import pem_refine, stabilise


def _chol_psd(W: np.ndarray, rel: float = 1e-10) -> np.ndarray:
    w, V = np.linalg.eigh((W + W.T) / 2)
    w = np.maximum(w, rel * max(float(w.max()), 1e-300))
    return V * np.sqrt(w)


class BalancedBasis:
    def __init__(self, P: SysPrep, trajs: list[PTraj], kmax: int, cfg: dict, seed: int, targets=None):
        lags = cfg.get("past_lags", (0,))
        if lags == "auto":
            lags = (cfg.get("_lags_by_sys") or {}).get(P.sid, (0,))
        self.lags = [int(l) for l in lags]
        L = max(self.lags)
        r = int(min(P.n_x * len(self.lags), cfg.get("r_full", 64)))
        if self.lags == [0]:
            V, wv = pca_basis(P, trajs, r)
        else:
            V, wv = delay_pca(P, trajs, self.lags, r)
        self.V, self.N = V, P.n_x
        # surrogate fit (delay coordinates w_t = V [xs_t, xs_{t-l1}, ...])
        Wt, Ut, Wn, Ws, Ys, Us = [], [], [], [], [], []
        tot = sum(len(t.xs) for t in trajs)
        stride = max(1, tot // 200000)
        for t in trajs:
            idx = np.arange(len(t.xs))
            W = sum(t.xs[np.maximum(0, idx - l)].astype(np.float64) @ V[:, i * P.n_x: (i + 1) * P.n_x].T for i, l in enumerate(self.lags))
            ii = np.flatnonzero(t.keep)[::stride]
            ii = ii[ii >= L]
            Wt.append(W[ii]); Ut.append(t.us[ii].astype(np.float64)); Wn.append(W[ii + 1])
            Ws.append(W[L::stride]); Ys.append(t.y[L::stride]); Us.append(t.us[L::stride].astype(np.float64))
        Wt, Ut, Wn = np.concatenate(Wt), np.concatenate(Ut), np.concatenate(Wn)
        Fm = np.hstack([Wt, Ut, np.ones((len(Wt), 1))])
        M = ridge_solve(Fm, Wn, float(cfg.get("ridge_full", 1e-4)))
        F = stabilise(M[:r].T.copy(), 1.0)
        E = M[r:r + P.n_u].T.copy()
        Wa, Ya, Ua = np.concatenate(Ws), np.concatenate(Ys), np.concatenate(Us)
        Rm = ridge_solve(np.hstack([Wa, Ua, np.ones((len(Wa), 1))]), (Ya - P.my) / P.sy, 1e-4)
        Gw = Rm[:r].T                                             # (n_y, r), normalised outputs
        H = max(2, P.T_len // 4)
        # perturbation ensembles
        ens = []
        if P.n_u and np.linalg.norm(E) > 0:
            ens.append(E)
        cols = [P.col[n] for n in (targets or []) if n in P.col] or list(range(P.n_x))
        ens.append(V[:, cols])                                    # unit kicks / currents act on the lag-0 block only
        Sw = np.cov(Wa.T).reshape(r, r)
        S0 = sum(e @ e.T / max(np.trace(e @ e.T), 1e-12) for e in ens) + Sw / max(np.trace(Sw), 1e-12)
        Wc = np.zeros((r, r)); Wo = np.zeros((r, r))
        Ft = np.eye(r)
        Q0 = Gw.T @ Gw
        for _ in range(H):
            Wc += Ft @ S0 @ Ft.T
            Wo += Ft.T @ Q0 @ Ft
            Ft = F @ Ft
        Lc, Lo = _chol_psd(Wc), _chol_psd(Wo)
        U, s, Vt = np.linalg.svd(Lo.T @ Lc)
        self.U, self.s, self.Vt, self.Lc, self.Lo = U, s, Vt, Lc, Lo
        tail = np.cumsum(s[::-1])[::-1] / max(s.sum(), 1e-300)          # tail[i] = sum_{j>=i} s_j / sum s
        kb = int(np.argmax(np.r_[tail[1:], 0.0] <= float(cfg.get("hsv_tail", 0.01)))) + 1
        self.k_bound = int(max(1, min(kb, cfg.get("k_closure_max", 16))))
        self.k_max = int(min(kmax, len(s), cfg.get("k_closure_max", 16)))
        self.diag = {"hsv": [float(x) for x in s[:32]], "hsv_rel_tail": [float(x) for x in tail[:32]], "k_bound": self.k_bound, "r_full": r,
                     "past_lags": self.lags}

    def encoder(self, k: int) -> dict:
        k = int(min(k, self.k_max))
        s = np.maximum(self.s[:k], 1e-300)
        T = (self.U[:, :k] / np.sqrt(s)).T @ self.Lo.T               # (k, r)
        TV = T @ self.V
        return {"lags": list(self.lags), "Hx": [TV[:, i * self.N: (i + 1) * self.N].copy() for i in range(len(self.lags))], "Hu": None,
                "b": np.zeros(k)}


def init_closure(k: int, n_u: int, hidden: int, Z: np.ndarray, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    zs = Z.std(0) + 1e-9
    return {"zm": Z.mean(0), "zs": zs, "W1": rng.standard_normal((k + n_u, hidden)) / np.sqrt(k + n_u),
            "b1": rng.uniform(-1, 1, hidden) * 0.5, "W2": np.zeros((hidden, k)), "b2": np.zeros(k), "scale": zs.copy()}


@register
class LinBalanced(LinMethodBase):
    """Interventional-gramian balanced truncation + nonlinear closure (see module docstring)."""
    name = "lin_balanced"
    bound_grid = True
    version = "1"
    default_config = {**LinMethodBase.default_config, "pem": True, "closure": True, "readout": "linear", "r_full": 64,
                      "hsv_tail": 0.01, "k_closure_max": 16, "past_lags": "auto", "history_gain": 0.4, "closure_hidden": 32, "closure_steps": 300, "cv_closure_steps": 100, "cv_folds_closure": 2, "pem_h_max": 96,
                      "pem_steps": 300}

    def make_basis(self, P, trajs, kmax, cfg, seed):
        return BalancedBasis(P, trajs, kmax, cfg, seed, targets=cfg.get("_targets"))

    def k_grid(self, kmax):
        return [k for k in (1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 14, 16) if k <= kmax] or [1]

    def cv_curve(self, P, cfg, seed, k_forced=None):
        # the closure is trained inside the CV: 2 folds keep the cost bounded
        return super().cv_curve(P, {**cfg, "_in_cv": True, "n_folds": int(cfg.get("cv_folds_closure", 2))}, seed, k_forced)

    def build_single(self, P, trajs, enc, cfg, seed, readout=None):
        m = super().build_single(P, trajs, enc, cfg, seed, readout)
        if cfg.get("closure") and cfg.get("_in_cv"):
            self._train_closure(m, P, trajs, cfg, seed, steps=int(cfg["cv_closure_steps"]))
        return m

    def _train_closure(self, m, P, trajs, cfg, seed, steps):
        from .lin_fit import latent_series
        sid = P.sid
        k = m.k[sid]
        Z = np.concatenate([latent_series(m.sys[sid]["enc"], t)[:: max(1, len(t.xs) // 100)] for t in trajs])
        m.dyn[sid]["nl"] = init_closure(k, P.n_u, int(cfg["closure_hidden"]), Z, seed)
        H = max(2, int(round(cfg["pem_horizon_frac"] * P.T_len)))
        return pem_refine(m, [sid], {sid: P}, {sid: trajs}, H=min(H, int(cfg.get("pem_h_max", 96))), steps=steps, seed=seed, train_nl=True,
                          time_budget_s=float(cfg.get("time_budget_s", 900)) / 4)

    def refine(self, model, sid, P, trajs, cfg, seed, budget_s):
        if cfg.get("closure"):
            return self._train_closure(model, P, trajs, cfg, seed, steps=int(cfg["closure_steps"]))
        return super().refine(model, sid, P, trajs, cfg, seed, budget_s)

    def shared_refine(self, model, sids, preps, cfg, seed):
        """Shared closure: one N(z, u) trained jointly with the shared transition on all systems (input dimensions must agree;
        otherwise the shared transition stays linear)."""
        if not cfg.get("closure") or len({preps[s].n_u for s in sids}) != 1:
            return super().shared_refine(model, sids, preps, cfg, seed)
        from .lin_fit import latent_series
        k = model.k[sids[0]]
        Z = np.concatenate([latent_series(model.sys[s]["enc"], t)[:: max(1, len(t.xs) // 100)] for s in sids for t in preps[s].trajs])
        model.dyn[sids[0]]["nl"] = init_closure(k, preps[sids[0]].n_u, int(cfg["closure_hidden"]), Z, seed)
        H = max(2, int(round(cfg["pem_horizon_frac"] * min(preps[s].T_len for s in sids))))
        return pem_refine(model, sids, preps, {s: preps[s].trajs for s in sids}, H=min(H, int(cfg.get("pem_h_max", 96))),
                          steps=int(cfg["closure_steps"]), seed=seed, train_nl=True, time_budget_s=float(cfg.get("time_budget_s", 900)) / 2)

    def fit_system(self, P, cfg, seed, targets, k_forced, t_budget):
        """past_lags='auto': static microstate against a short causal delay embedding (as lin_subspace), each with its own
        dimension rule; the delay variant is kept only if its cross-validated error is at least 40 % lower (history_gain)."""
        cfg = {**cfg, "_targets": list(targets or [])}
        mode = cfg.get("past_lags", "auto")
        if mode != "auto":
            return super().fit_system(P, {**cfg, "past_lags": tuple(mode)}, seed, targets, k_forced, t_budget)
        T = P.T_len
        hist = tuple(sorted({0} | {max(1, T // d) for d in (400, 200, 100, 50)}))
        best = None
        variants = {}
        t_start = time.time()
        for lags in ((0,), hist):
            if best is not None and time.time() - t_start > 0.45 * t_budget:
                best[1]["past_lags_note"] = "history variant skipped (time budget)"
                break
            m, dg = super().fit_system(P, {**cfg, "past_lags": lags}, seed, targets, k_forced, t_budget / 2)
            sc = dg.get("selected_score", np.inf)
            dg["past_lags"] = list(lags)
            variants[str(list(lags))] = {"score": float(sc), "k": int(dg.get("k_selected", 0))}
            dg["lag_variants"] = variants
            # the history encoder must remove >= history_gain of the static model's CV error: strong evidence that the current
            # microstate misses state (real circuits: readout neurons outside x), not mere denoising (synthetic systems, whose
            # state is a function of x_t; there the history variant's larger k hurt intervention fidelity)
            if best is None or sc < best[2] * (1.0 - float(cfg.get("history_gain", 0.4))):
                best = (m, dg, sc)
        return best[0], best[1]
