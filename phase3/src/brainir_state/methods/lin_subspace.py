"""lin_subspace: canonical-variate-analysis (CVA) subspace identification with inputs, the latent dimension from the held-out
canonical-correlation spectrum against a surrogate plus the cross-validated free-run plateau, prediction-error refinement.

Mathematics (regression / CCA form of CVA, Larimore 1990; Mercere 2013):
    past     p_t = [P_r xs_t, P_r xs_{t-l1}, ...]            (P_r: top-r principal axes of the standardised microstate; no y)
    future   f_t = [ys_{t+s_1}, ..., ys_{t+s_m}]              (standardised readout at m future offsets up to T/8)
             (optionally also the top principal components of xs at the same offsets: config future='xy')
    future inputs U_t = [us over m bins of [t, t + s_m]] are projected out of both blocks (partial CCA, open-loop inputs):
             p~ = p - proj_U p,  f~ = f - proj_U f
    CCA      Sigma_pp^{-1/2} Sigma_pf Sigma_ff^{-1/2} = U S V^T;  canonical directions a_i = Sigma_pp^{-1/2} u_i,
             canonical correlations s_i (how much of the past predicts the future beyond the future inputs)
    encoder  z_t = [a_1 ... a_k]^T (p_t - mean)               (a causal regression of the state on the recent microstate)
    order    k_bound = number of canonical directions (fitted on half of the trajectories) whose correlation on the other half
             exceeds the 95th percentile of a surrogate in which held-out futures are permuted across trajectories at equal
             times (keeps input-locked structure, destroys state information); the lin_base free-run CV rule scores
             k <= k_bound first and extends the grid while it keeps selecting the largest k scored
    dynamics z_{t+1} = A z_t + B u_t + c by least squares on free transitions, then prediction-error refinement (Adam on the
             multi-step latent + readout error over horizons up to T/4, encoder fixed), spectral radius <= 1
    readout  y = G [z, u] + h (linear) or with quadratic latent terms (chosen by CV)
Events act through the model (lin_core / lin_fit): kicks through the encoder's instantaneous block, currents as input through
the same map with one fitted gain, silencing through the decoder and read-in, edge removal through the low-rank coupling.
"""

from __future__ import annotations

import time

import numpy as np

from ..api import register
from .lin_base import LinMethodBase
from .lin_core import PTraj, SysPrep, pca_basis


def _msqrt_inv(C: np.ndarray, rel_floor: float = 1e-6) -> np.ndarray:
    w, V = np.linalg.eigh((C + C.T) / 2)
    w = np.maximum(w, rel_floor * max(float(w.max()), 1e-12))
    return V @ np.diag(1 / np.sqrt(w)) @ V.T


def _residualize(X: np.ndarray, U: np.ndarray, lam: float = 1e-6) -> np.ndarray:
    if U is None or U.shape[1] == 0:
        return X - X.mean(0)
    Uc = np.hstack([U, np.ones((len(U), 1))])
    G = Uc.T @ Uc
    G[np.diag_indices_from(G)] += lam * len(U)
    return X - Uc @ np.linalg.solve(G, Uc.T @ X)


def cca(P: np.ndarray, F: np.ndarray, reg: float = 1e-4):
    """Canonical directions of P (columns of Ap) and F, correlations s (descending)."""
    Pc, Fc = P - P.mean(0), F - F.mean(0)
    n = len(P)
    Cpp = Pc.T @ Pc / n
    Cff = Fc.T @ Fc / n
    Cpf = Pc.T @ Fc / n
    Cpp += reg * np.trace(Cpp) / len(Cpp) * np.eye(len(Cpp))
    Cff += reg * np.trace(Cff) / len(Cff) * np.eye(len(Cff))
    Wp, Wf = _msqrt_inv(Cpp), _msqrt_inv(Cff)
    U, s, Vt = np.linalg.svd(Wp @ Cpf @ Wf, full_matrices=False)
    return Wp @ U, Wf @ Vt.T, s


class CVABasis:
    def __init__(self, P: SysPrep, trajs: list[PTraj], kmax: int, cfg: dict, seed: int):
        self.N = P.n_x
        lags = cfg.get("past_lags", (0,))
        if lags == "auto":        # shared / adapted fits: the lags chosen for this system (else the static past)
            lags = (cfg.get("_lags_by_sys") or {}).get(P.sid, (0,))
        lags = [int(l) for l in lags]
        self.lags = lags
        r = int(min(P.n_x, cfg.get("r_past", 64)))
        V, w = pca_basis(P, trajs, r)
        self.V = V                                         # (r, N)
        T = P.T_len
        Hf = max(2, T // 8)
        n_off = int(min(cfg.get("n_future", 16), Hf))
        offs = np.unique(np.round(np.linspace(1, Hf, n_off)).astype(int))
        self.offs = offs
        nb = max(1, min(8, Hf))
        edges = np.linspace(0, Hf + 1, nb + 1).astype(int)
        Lmax = max(lags)
        future_x = cfg.get("future", "y") == "xy"
        rng = np.random.default_rng(seed)
        rows_P, rows_F, rows_U, rows_t, rows_g = [], [], [], [], []
        tot = sum(len(t.xs) for t in trajs)
        stride = max(1, tot // int(cfg.get("cva_rows", 40000)))
        ys_mu, ys_sd = P.my, P.sy
        for gi, t in enumerate(trajs):
            n = len(t.xs)
            Xp = t.xs.astype(np.float64) @ V.T
            Ys = (t.y - ys_mu) / ys_sd
            ok = np.convolve(t.keep.astype(float), np.ones(Hf), "valid") >= Hf - 0.5
            cand = np.flatnonzero(ok)
            cand = cand[(cand >= Lmax) & (cand + Hf < n)]
            cand = cand[(cand - Lmax) % stride == 0] if stride > 1 else cand
            if len(cand) == 0:
                continue
            Pb = np.hstack([Xp[cand - l] for l in lags])
            Fb = np.hstack([Ys[cand + o] for o in offs])
            if future_x:
                kx = min(8, Xp.shape[1])
                Fb = np.hstack([Fb] + [Xp[cand + o, :kx] for o in offs[:: max(1, len(offs) // 4)]])
            Ub = np.hstack([t.us[cand[:, None] + np.arange(edges[j], max(edges[j] + 1, edges[j + 1]))[None, :]].astype(np.float64).mean(1)
                            for j in range(nb)]) if P.n_u else np.zeros((len(cand), 0))
            rows_P.append(Pb); rows_F.append(Fb); rows_U.append(Ub); rows_t.append(cand); rows_g.append(np.full(len(cand), gi))
        Pm, Fm, Um = np.concatenate(rows_P), np.concatenate(rows_F), np.concatenate(rows_U)
        tt, gg = np.concatenate(rows_t), np.concatenate(rows_g)
        self.p_mean = Pm.mean(0)
        Pr, Fr = _residualize(Pm, Um), _residualize(Fm, Um)
        Ap, Af, s = cca(Pr, Fr)
        self.Ap, self.s = Ap, s
        # held-out spectrum against a surrogate (half of the trajectories fit the directions, the other half score them)
        ug = np.unique(gg)
        half = np.isin(gg, rng.permutation(ug)[: max(1, len(ug) // 2)])
        k_bound = len(s)
        ho, null95 = [], None
        if half.sum() > 50 and (~half).sum() > 50 and len(ug) >= 4:
            Ap1, Af1, s1 = cca(Pr[half], Fr[half])
            Pa, Fa = Pr[~half], Fr[~half]
            zp, zf = (Pa - Pa.mean(0)) @ Ap1, (Fa - Fa.mean(0)) @ Af1
            m = min(zp.shape[1], zf.shape[1])
            ho = [abs(_corr(zp[:, i], zf[:, i])) for i in range(m)]
            nulls = []
            for rep in range(int(cfg.get("n_surrogate", 20))):
                perm = _perm_within_time(tt[~half], gg[~half], rng)
                zf_p = zf[perm]
                nulls.append(max(abs(_corr(zp[:, i], zf_p[:, i])) for i in range(m)))
            null95 = float(np.percentile(nulls, 95))
            k_bound = 0
            for i in range(m):
                if ho[i] > null95:
                    k_bound = i + 1
                else:
                    break
            # the future has m directions: states beyond them are only reachable through the free-run rule
            if k_bound == m:
                k_bound = len(s)
        self.k_bound = max(1, k_bound)
        self.k_max = int(min(kmax, Ap.shape[1]))
        self.diag = {"canonical_correlations": [float(x) for x in s[:32]], "heldout_cc": [float(x) for x in ho[:32]],
                     "surrogate_cc95": null95, "k_bound": int(self.k_bound), "future_offsets": [int(o) for o in offs], "past_lags": lags}

    def encoder(self, k: int) -> dict:
        k = int(min(k, self.k_max))
        A = self.Ap[:, :k].T                               # (k, r * n_lags)
        r = self.V.shape[0]
        Hx = [A[:, i * r: (i + 1) * r] @ self.V for i in range(len(self.lags))]
        # normalise every latent to unit variance on the training past (canonical variates already are); centre
        b = -A @ self.p_mean
        return {"lags": list(self.lags), "Hx": Hx, "Hu": None, "b": b}


def _corr(a, b):
    a = a - a.mean(); b = b - b.mean()
    d = np.sqrt((a @ a) * (b @ b))
    return float(a @ b / d) if d > 0 else 0.0


def _perm_within_time(t: np.ndarray, g: np.ndarray, rng) -> np.ndarray:
    """Permutation pairing each sample with a sample of ANOTHER trajectory at the same time index (where possible)."""
    idx = np.arange(len(t))
    out = idx.copy()
    for tv in np.unique(t):
        ii = idx[t == tv]
        if len(ii) > 1:
            out[ii] = np.roll(ii[rng.permutation(len(ii))], 1)
    return out


@register
class LinSubspace(LinMethodBase):
    """CVA subspace identification with inputs + prediction-error refinement (see module docstring)."""
    name = "lin_subspace"
    bound_grid = True
    version = "1"
    default_config = {**LinMethodBase.default_config, "pem": True, "readout": "auto", "past_lags": "auto", "history_gain": 0.4, "future": "y",
                      "r_past": 64, "n_future": 16, "n_surrogate": 20, "cva_rows": 40000}

    def make_basis(self, P, trajs, kmax, cfg, seed):
        return CVABasis(P, trajs, kmax, cfg, seed)

    def fit_system(self, P, cfg, seed, targets, k_forced, t_budget):
        """past_lags='auto': the static past {0} against a short causal history {0, T/400, T/200, T/100, T/50} (samples), each
        with its own dimension rule; the history variant is kept only if its cross-validated error is at least 40 % lower
        (history_gain; readout neurons outside x, synaptic filtering and other memories make the current microstate alone
        insufficient)."""
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

