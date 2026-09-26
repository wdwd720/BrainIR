"""Classical linear baselines of family A (declared BASELINES in notes/lin_methods.md):

lin_pcadyn   PCA of the standardised microstate (optionally delay-embedded [x_t, x_{t-d}]) + linear latent dynamics
             z_{t+1} = A z_t + B u_t + c by least squares; the latent dimension (and, with delays='auto', the delay variant) is
             selected by the cross-validated FREE-RUN multi-horizon readout error (lin_base dimension rule).
lin_dmdc     DMD with control (Proctor, Brunton & Kutz 2016): truncated SVD of the stacked snapshot matrix [X; U] (rank p) and of
             the shifted snapshots X' (rank r = k); reduced operators A~ = U_r^T X' V_p S_p^-1 U_p1^T U_r, B~ = U_r^T X' V_p S_p^-1
             U_p2^T; encoder z = U_r^T x; r by the same free-run rule, p = r + n_u + 1 (input rank) capped by the snapshot rank.
lin_falds    factor analysis (heteroscedastic per-neuron noise, EM) for the observation model x = C z + d + e, e ~ N(0, Psi), then a
             linear dynamical system with inputs fitted by EM (Kalman smoother E-step; M-step for A, B, c, Q; C and Psi kept from FA
             refined in the M-step) and a CAUSAL steady-state Kalman filter as encoder (truncated FIR form).
"""

from __future__ import annotations

import time

import numpy as np

from ..api import register
from .lin_base import LinMethodBase
from .lin_core import PTraj, SysPrep, ridge_solve
from .lin_fit import burn_in, fit_dynamics_ls, latent_series, stabilise, static_encoder


# ==================================================================================================================== PCA + dynamics
class PCABasis:
    def __init__(self, V: np.ndarray, w: np.ndarray, N: int, lags=(0,)):
        self.V, self.w, self.N, self.lags = V, w, N, list(lags)
        self.k_max = V.shape[0]
        tot = max(float(w.sum()), 1e-12)
        self.diag = {"explained": [float(x) for x in np.cumsum(w[: min(len(w), 64)]) / tot], "lags": self.lags}

    def encoder(self, k: int) -> dict:
        k = min(k, self.k_max)
        Vk = self.V[:k]
        return {"lags": self.lags, "Hx": [Vk[:, i * self.N: (i + 1) * self.N].copy() for i in range(len(self.lags))], "Hu": None,
                "b": np.zeros(k)}


def delay_pca(P: SysPrep, trajs: list[PTraj], lags, r: int, max_rows: int = 150000) -> tuple[np.ndarray, np.ndarray]:
    """PCA of the causal delay embedding [x_t, x_{t-l1}, ...] (standardised units)."""
    N = P.n_x
    D = N * len(lags)
    tot = sum(len(t.xs) for t in trajs)
    stride = max(1, tot // max_rows)
    Cm = np.zeros((D, D)); m = np.zeros(D); n = 0
    L = max(lags)
    for t in trajs:
        idx = np.arange(L, len(t.xs), stride)
        E = np.hstack([t.xs[idx - l].astype(np.float64) for l in lags])
        Cm += E.T @ E; m += E.sum(0); n += len(E)
    m /= n
    Cm = Cm / n - np.outer(m, m)
    w, V = np.linalg.eigh(Cm)
    o = np.argsort(w)[::-1]
    return V[:, o[:r]].T.copy(), np.maximum(w[o], 0)


@register
class LinPCADyn(LinMethodBase):
    """PCA + linear dynamics baseline (delay variant: delays='auto' compares no delay with one delay of T/32 by CV)."""
    name = "lin_pcadyn"
    version = "1"
    default_config = {**LinMethodBase.default_config, "delays": "auto", "pem": False}

    def make_basis(self, P, trajs, kmax, cfg, seed):
        lags = cfg.get("_lags", (0,))
        V, w = delay_pca(P, trajs, lags, min(kmax, P.n_x * len(lags)))
        return PCABasis(V, w, P.n_x, lags)

    def fit_system(self, P, cfg, seed, targets, k_forced, t_budget):
        mode = cfg.get("delays", "auto")
        if mode in (None, 0, "none", (0,)):
            return super().fit_system(P, {**cfg, "_lags": (0,)}, seed, targets, k_forced, t_budget)
        d = max(1, P.T_len // 32)
        cands = [(0,), (0, d)] if mode == "auto" else [tuple(mode)]
        best = None
        t_start = time.time()
        for lags in cands:
            if best is not None and time.time() - t_start > 0.45 * t_budget:
                break
            m, dg = super().fit_system(P, {**cfg, "_lags": lags}, seed, targets, k_forced, t_budget / len(cands))
            sc = dg.get("selected_score", np.inf)
            dg["delay_lags"] = list(lags)
            # the delay variant must be clearly better (5 %) to be preferred over the instantaneous one
            if best is None or sc < best[2] * 0.95:
                best = (m, dg, sc)
        return best[0], best[1]


# ==================================================================================================================== DMDc
class DMDcBasis:
    """Proctor et al. DMDc: the latent basis is the output-space POD basis U_r of X' (shifted snapshots); A~, B~ from the
    truncated pseudo-inverse of [X; U]. The encoder is z = U_r^T x; the reduced operators are stored for build_single."""

    def __init__(self, P: SysPrep, trajs: list[PTraj], kmax: int, max_rows: int = 150000):
        X, Xp, U = [], [], []
        tot = sum(int(t.keep.sum()) for t in trajs)
        stride = max(1, tot // max_rows)
        for t in trajs:
            ii = np.flatnonzero(t.keep)[::stride]
            X.append(t.xs[ii].astype(np.float64)); Xp.append(t.xs[ii + 1].astype(np.float64)); U.append(t.us[ii].astype(np.float64))
        X, Xp, U = np.concatenate(X).T, np.concatenate(Xp).T, np.concatenate(U).T        # (N, m), (N, m), (n_u, m)
        self.mx = X.mean(1, keepdims=True)      # centre (standardised data are ~ centred already)
        Om = np.vstack([X - self.mx, U, np.ones((1, X.shape[1]))])
        self.Uo, self.So, self.Vo = np.linalg.svd(Om, full_matrices=False)
        self.Ur, sr, _ = np.linalg.svd(Xp - self.mx, full_matrices=False)
        self.Xp, self.N, self.n_u = Xp - self.mx, X.shape[0], U.shape[0]
        self.k_max = int(min(kmax, np.sum(sr > sr[0] * 1e-8), self.N))
        tot = max(float((sr ** 2).sum()), 1e-12)
        self.diag = {"explained": [float(x) for x in np.cumsum(sr[:64] ** 2) / tot]}
        self.srank = int(np.sum(self.So > self.So[0] * 1e-10))

    def encoder(self, k: int) -> dict:
        k = min(k, self.k_max)
        enc = static_encoder(self.Ur[:, :k].T.copy(), -self.Ur[:, :k].T @ self.mx[:, 0])
        p = int(min(self.srank, k + self.n_u + 1 + max(2, k // 2)))
        Up, Sp, Vp = self.Uo[:, :p], self.So[:p], self.Vo[:p]
        Ur = self.Ur[:, :k]
        G = (Ur.T @ self.Xp) @ Vp.T / Sp                     # (k, p)
        Up1, Up2, Up3 = Up[: self.N], Up[self.N: self.N + self.n_u], Up[self.N + self.n_u:]
        enc["_dmdc"] = {"A": G @ Up1.T @ Ur, "B": G @ Up2.T, "c": (G @ Up3.T)[:, 0]}
        return enc


@register
class LinDMDc(LinMethodBase):
    """DMD with control (exact reduced operators; rank by the free-run rule)."""
    name = "lin_dmdc"
    version = "1"
    default_config = {**LinMethodBase.default_config, "pem": False}

    def make_basis(self, P, trajs, kmax, cfg, seed):
        return DMDcBasis(P, trajs, kmax)

    def build_single(self, P, trajs, enc, cfg, seed, readout=None):
        m = super().build_single(P, trajs, enc, cfg, seed, readout)
        op = enc.get("_dmdc")
        if op is not None:
            # DMDc operators act on centred coordinates z~ = U_r^T (x - mx); the encoder already subtracts the mean
            m.dyn[P.sid]["A"] = stabilise(op["A"], 1.0)
            m.sys[P.sid]["Bs"] = op["B"]
            m.dyn[P.sid]["c"] = op["c"]
        return m


# ==================================================================================================================== FA + LDS (EM)
def factor_analysis(X: np.ndarray, k: int, iters: int = 200, tol: float = 1e-6, seed: int = 0):
    """ML factor analysis x = C z + d + e, z ~ N(0, I), e ~ N(0, diag(psi)) by EM. Returns C (N, k), d (N,), psi (N,)."""
    d = X.mean(0)
    Xc = X - d
    S = Xc.T @ Xc / len(Xc)
    w, V = np.linalg.eigh(S)
    o = np.argsort(w)[::-1]
    C = V[:, o[:k]] * np.sqrt(np.maximum(w[o[:k]] - np.median(w), 1e-3))
    psi = np.maximum(np.diag(S) - (C ** 2).sum(1), 1e-3 * np.diag(S).mean() + 1e-6)
    ll_old = -np.inf
    N = X.shape[1]
    for it in range(iters):
        Pi = 1.0 / psi
        M = np.eye(k) + (C.T * Pi) @ C
        Mi = np.linalg.inv(M)
        beta = Mi @ (C.T * Pi)                       # E[z|x] = beta (x - d)
        Ezz = Mi + beta @ S @ beta.T                 # average E[zz^T]
        C = S @ beta.T @ np.linalg.inv(Ezz)
        psi = np.maximum(np.diag(S) - np.einsum("ij,ji->i", C, beta @ S), 1e-4 * np.diag(S).mean() + 1e-8)
        if it % 10 == 0:
            Sig = C @ C.T + np.diag(psi)
            sign, logdet = np.linalg.slogdet(Sig)
            ll = -0.5 * (logdet + np.trace(np.linalg.solve(Sig, S)))
            if ll - ll_old < tol * abs(ll):
                break
            ll_old = ll
    return C, d, psi


def kalman_steady(A, C, Q, R, iters: int = 2000, tol: float = 1e-10):
    """Steady-state prediction covariance P and filter gain Kf (x-measurement update) for z' = A z + w, x = C z + e."""
    k = A.shape[0]
    Pm = np.eye(k)
    for _ in range(iters):
        S = C @ Pm @ C.T + R
        Kf = np.linalg.solve(S, C @ Pm).T                   # (k, N)
        Pf = Pm - Kf @ C @ Pm
        Pn = A @ Pf @ A.T + Q
        if np.max(np.abs(Pn - Pm)) < tol * (1 + np.max(np.abs(Pm))):
            Pm = Pn
            break
        Pm = (Pn + Pn.T) / 2
    S = C @ Pm @ C.T + R
    Kf = np.linalg.solve(S, C @ Pm).T
    return Pm, Kf


def kalman_fir(A, B, c, C, d, Kf, tol: float = 1e-4, max_len: int = 400) -> dict:
    """Causal steady-state filter z_t|t = F z_{t-1|t-1} + (I - Kf C)(B u_{t-1} + c) + Kf (x_t - d), F = (I - Kf C) A, written as a
    truncated FIR encoder over lags 0..L-1 (L: until ||F^L|| < tol); the truncated tail is dropped (its weight < tol)."""
    k = A.shape[0]
    IKC = np.eye(k) - Kf @ C
    F = IKC @ A
    Hx, Hu, lags = [], [], []
    Fl = np.eye(k)
    b = np.zeros(k)
    for L in range(max_len):
        Hx.append(Fl @ Kf); lags.append(L)
        Hu.append(Fl @ IKC @ B)                             # u_{t-1-L} enters through lag L + 1 on u; stored at lag L+1 below
        b += Fl @ (IKC @ c - Kf @ d)
        Fl = F @ Fl
        if np.linalg.norm(Fl, 2) < tol:
            break
    # u lags are shifted by one: rebuild as lags 0..L with Hu[0] = 0
    L = len(lags)
    lags_all = list(range(L + 1))
    Hx_all = Hx + [np.zeros_like(Hx[0])]
    Hu_all = [np.zeros_like(Hu[0])] + Hu
    return {"lags": lags_all, "Hx": Hx_all, "Hu": Hu_all, "b": b,
            "_rec": {"F": F, "Kx": Kf, "Ku": IKC @ B, "b1": IKC @ c - Kf @ d}}


def lds_em(Zinit_trajs, Xs_trajs, Us_trajs, C, d, psi, A, B, c, iters: int = 10, max_T: int = 400):
    """EM for x_t = C z_t + d + e, z_{t+1} = A z_t + B u_t + c + w (Q), with a Kalman smoother per trajectory segment. Segments
    longer than max_T are subsampled in time windows (for speed). Returns (A, B, c, Q, C, d, psi)."""
    k = A.shape[0]
    Q = np.eye(k) * 0.1
    for _ in range(iters):
        Szz = np.zeros((k, k)); Sz1z = np.zeros((k, k)); Szu = np.zeros((k, B.shape[1])); Sz1u = np.zeros((k, B.shape[1]))
        Suu = np.zeros((B.shape[1], B.shape[1])); Sz = np.zeros(k); Sz1 = np.zeros(k); Su = np.zeros(B.shape[1]); n = 0
        Sz1z1 = np.zeros((k, k))
        Sxz = np.zeros((C.shape[0], k)); Szz_all = np.zeros((k, k)); Sx = np.zeros(C.shape[0]); Sz_all = np.zeros(k); Sxx = np.zeros(C.shape[0]); m = 0
        R = np.diag(psi)
        for X, U in zip(Xs_trajs, Us_trajs):
            T = len(X)
            mu, V, Vc = rts_smoother(X, U, A, B, c, C, d, R, Q)
            Ez = mu
            Ezz = V + np.einsum("ti,tj->tij", mu, mu)
            Ez1z = Vc + np.einsum("ti,tj->tij", mu[1:], mu[:-1])        # E[z_{t+1} z_t^T]
            Szz += Ezz[:-1].sum(0); Sz1z += Ez1z.sum(0); Sz1z1 += Ezz[1:].sum(0)
            Szu += Ez[:-1].T @ U[:-1]; Sz1u += Ez[1:].T @ U[:-1]; Suu += U[:-1].T @ U[:-1]
            Sz += Ez[:-1].sum(0); Sz1 += Ez[1:].sum(0); Su += U[:-1].sum(0); n += T - 1
            Sxz += X.T @ Ez; Szz_all += Ezz.sum(0); Sx += X.sum(0); Sz_all += Ez.sum(0); Sxx += (X ** 2).sum(0); m += T
        # M-step dynamics: [A B c] = [Sz1z Sz1u Sz1] [[Szz Szu Sz],[Szu^T Suu Su],[Sz^T Su^T n]]^-1
        nu = B.shape[1]
        M = np.zeros((k + nu + 1, k + nu + 1))
        M[:k, :k] = Szz; M[:k, k:k + nu] = Szu; M[:k, -1] = Sz
        M[k:k + nu, :k] = Szu.T; M[k:k + nu, k:k + nu] = Suu; M[k:k + nu, -1] = Su
        M[-1, :k] = Sz; M[-1, k:k + nu] = Su; M[-1, -1] = n
        Rhs = np.hstack([Sz1z, Sz1u, Sz1[:, None]])
        W = np.linalg.solve(M + 1e-8 * np.trace(M) / len(M) * np.eye(len(M)), Rhs.T).T
        A, B, c = stabilise(W[:, :k], 0.9999), W[:, k:k + nu], W[:, -1]
        Q = (Sz1z1 - W @ Rhs.T) / n
        Q = (Q + Q.T) / 2 + 1e-6 * np.trace(Q) / k * np.eye(k)
        w_, V_ = np.linalg.eigh(Q)
        Q = V_ @ np.diag(np.maximum(w_, 1e-6 * max(w_.max(), 1e-12))) @ V_.T
        # M-step observation
        Mz = np.zeros((k + 1, k + 1)); Mz[:k, :k] = Szz_all; Mz[:k, -1] = Sz_all; Mz[-1, :k] = Sz_all; Mz[-1, -1] = m
        Wo = np.linalg.solve(Mz + 1e-8 * np.eye(k + 1), np.hstack([Sxz, Sx[:, None]]).T).T
        C, d = Wo[:, :k], Wo[:, -1]
        psi = np.maximum((Sxx - np.einsum("ij,ij->i", Wo, np.hstack([Sxz, Sx[:, None]]))) / m, 1e-4 * np.mean(Sxx / m) + 1e-8)
    return A, B, c, Q, C, d, psi


def rts_smoother(X, U, A, B, c, C, d, R, Q):
    """Kalman filter + RTS smoother for one sequence (information-form update: N >> k)."""
    T, k = len(X), A.shape[0]
    Ri = 1.0 / np.diag(R)
    CtRi = (C * Ri[:, None]).T                    # (k, N)
    CtRiC = CtRi @ C
    mu_p = np.zeros((T, k)); P_p = np.zeros((T, k, k)); mu_f = np.zeros((T, k)); P_f = np.zeros((T, k, k))
    m, Pm = np.zeros(k), np.eye(k) * 10.0
    # initial prior: least-squares state of the first sample
    m = np.linalg.solve(CtRiC + 1e-6 * np.eye(k), CtRi @ (X[0] - d))
    Pm = np.linalg.inv(CtRiC + 1e-6 * np.eye(k)) + np.eye(k) * 1e-3
    for t in range(T):
        mu_p[t], P_p[t] = m, Pm
        Pi = np.linalg.inv(Pm)
        Pf = np.linalg.inv(Pi + CtRiC)
        mf = Pf @ (Pi @ m + CtRi @ (X[t] - d))
        mu_f[t], P_f[t] = mf, Pf
        m = A @ mf + B @ U[t] + c
        Pm = A @ Pf @ A.T + Q
    mu_s = mu_f.copy(); P_s = P_f.copy(); Pc = np.zeros((T - 1, k, k))
    for t in range(T - 2, -1, -1):
        J = P_f[t] @ A.T @ np.linalg.inv(P_p[t + 1])
        mu_s[t] = mu_f[t] + J @ (mu_s[t + 1] - mu_p[t + 1])
        P_s[t] = P_f[t] + J @ (P_s[t + 1] - P_p[t + 1]) @ J.T
        Pc[t] = P_s[t + 1] @ J.T                  # Cov(z_{t+1}, z_t)
    return mu_s, P_s, Pc


class FALDSBasis:
    """FA observation model for every k (nested EM fits are cheap); the LDS / Kalman encoder is built per k in encoder()."""

    def __init__(self, P: SysPrep, trajs: list[PTraj], kmax: int, cfg: dict, seed: int, max_rows: int = 60000):
        tot = sum(len(t.xs) for t in trajs)
        stride = max(1, tot // max_rows)
        self.X = np.concatenate([t.xs[::stride].astype(np.float64) for t in trajs])
        self.trajs = trajs
        self.k_max = int(min(kmax, P.n_x - 1 if P.n_x > 2 else P.n_x))
        self.cfg, self.seed = cfg, seed
        self.diag = {}
        self._cache = {}

    def encoder(self, k: int) -> dict:
        if k in self._cache:
            return self._cache[k]
        C, d, psi = factor_analysis(self.X, k, seed=self.seed)
        # initial latent series by the FA posterior mean; LS dynamics; then a few EM iterations on segments
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
        # EM refinement on (at most) 24 event-free segments of <= 200 samples
        segs_x, segs_u = [], []
        rng = np.random.default_rng(self.seed)
        order = rng.permutation(len(self.trajs))
        for i in order:
            t = self.trajs[i]
            free = np.flatnonzero(~t.keep)
            end = int(free[0]) if len(free) else len(t.xs) - 1
            L = min(end, 200)
            if L >= 20:
                segs_x.append(t.xs[:L].astype(np.float64)); segs_u.append(t.us[:L].astype(np.float64))
            if len(segs_x) >= int(self.cfg.get("em_segments", 24)):
                break
        iters = int(self.cfg.get("em_iters_cv", 2) if self.cfg.get("_in_cv") else self.cfg.get("em_iters", 8))
        if segs_x and iters > 0:
            A, B, c, Q, C, d, psi = lds_em(None, segs_x, segs_u, C, d, psi, A, B, c, iters=iters)
        else:
            Q = np.cov((np.concatenate(Zn) - np.concatenate(Zt) @ A.T - np.concatenate(Ut) @ B.T - c).T).reshape(k, k)
        _, Kf = kalman_steady(A, C, Q, np.diag(psi))
        enc = kalman_fir(A, B, c, C, d, Kf)
        enc["_lds"] = {"A": A, "B": B, "c": c, "C": C, "d": d, "psi": psi, "Q": Q, "Kf": Kf}
        self._cache[k] = enc
        return enc


@register
class LinFALDS(LinMethodBase):
    """Factor analysis + linear dynamical system (EM), causal Kalman-filter encoder."""
    name = "lin_falds"
    version = "1"
    default_config = {**LinMethodBase.default_config, "pem": False, "em_iters": 8, "em_iters_cv": 2, "em_segments": 24, "k_max": 32}

    def make_basis(self, P, trajs, kmax, cfg, seed):
        return FALDSBasis(P, trajs, kmax, cfg, seed)

    def build_single(self, P, trajs, enc, cfg, seed, readout=None):
        m = super().build_single(P, trajs, enc, cfg, seed, readout)
        op = enc.get("_lds")
        if op is not None:
            # the LDS transition is the model's transition (the filter state is the LDS state)
            m.dyn[P.sid]["A"], m.sys[P.sid]["Bs"], m.dyn[P.sid]["c"] = op["A"], op["B"], op["c"]
            m.sys[P.sid]["C"], m.sys[P.sid]["d"], m.sys[P.sid]["xres"] = op["C"], op["d"], op["psi"]
        return m
