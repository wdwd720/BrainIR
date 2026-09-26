"""ks_edmd: extended DMD with control on reduced coordinates, residual-based mode filtering and balanced truncation (family C).

Mathematics
-----------
Reduced coordinates  q_t = (x~_t - mean) C_r   (ks_core.predictive_basis; r = the plateau of the basis' held-out curve, capped).
Dictionary           psi(q) = [q, exp(-||q - c_j||^2 / (2 s^2)), j = 1..M]   (k-means centres c_j, s = bandwidth factor x median
                     centre spacing). The constant is handled as an input channel.
EDMDc                psi_{t+1} = K psi_t + B u_t + b          ridge least squares on free transitions (Korda-Mezic).
ResDMD filter        eigenpairs (lambda, g) of K (psi g = eigenfunction), residual on the data with the input part removed
                         res^2 = ||(Psi_y - U B^T - b) g - lambda Psi_x g||^2 / ||Psi_x g||^2
                     eigenfunctions with res > eps are discarded (spectral pollution); the kept ones span phi = psi G_R (real form).
Balanced truncation  phi_{t+1} = Lambda phi + B_phi u + b_phi, outputs [y / sd_y, q] = C_phi phi (least squares). Controllability
                     side = the empirical covariance of phi on training data (balanced POD with data snapshots); observability =
                     finite-horizon gramian sum_{i<H} Lambda^i' C' C Lambda^i (H = T/4). Square-root balancing; z = T_k' phi.
The state is z (k-dim, the encoder output); the lifted dimension M + r is NOT the state dimension. Reduced dynamics either the
balanced-truncation Galerkin model or a least-squares refit on z (chosen by validation), readout y = ridge(z, u).
Events: kicks through the encoder, z' = z + E [psi(q^ + dq) - psi(q^)] with q^ = D_q z the decoded coordinates; currents,
silencing and edge removal as per-step microstate increments of ks_core.MicroModel mapped the same way.
"""

from __future__ import annotations

import numpy as np

from ..api import StateMethod, register
from . import ks_core as C
from .ks_abstain import abstention


def kmeans(X, M, seed=0, n_iter=30):
    rng = np.random.default_rng(seed)
    M = min(M, len(X))
    Cn = X[rng.choice(len(X), M, replace=False)].copy()
    for _ in range(n_iter):
        d = ((X[:, None, :] - Cn[None]) ** 2).sum(-1) if len(X) * M < 4e6 else None
        if d is None:
            lab = np.concatenate([(((xb[:, None, :] - Cn[None]) ** 2).sum(-1)).argmin(1) for xb in np.array_split(X, 20)])
        else:
            lab = d.argmin(1)
        new = np.stack([X[lab == j].mean(0) if (lab == j).any() else Cn[j] for j in range(M)])
        if np.allclose(new, Cn):
            break
        Cn = new
    return Cn


class RBFDict:
    def __init__(self, Q, M, bw_factor, seed=0):
        self.c = kmeans(Q[:: max(1, len(Q) // 8000)], M, seed)
        d = np.sqrt(((self.c[:, None] - self.c[None]) ** 2).sum(-1))
        np.fill_diagonal(d, np.inf)
        self.s = float(np.median(d.min(1))) * bw_factor + 1e-9
        self.r = Q.shape[1]
        self.n = self.r + len(self.c)

    def __call__(self, Q):
        Q = np.atleast_2d(Q)
        d2 = (Q * Q).sum(1)[:, None] - 2 * Q @ self.c.T + (self.c * self.c).sum(1)[None]
        return np.hstack([Q, np.exp(-np.maximum(d2, 0) / (2 * self.s ** 2))])


class EDMDModel(C.KSModel):
    def _q(self, S, x_hist):
        need = (max(S["lags"]) if S["lags"] else 0) + 1
        f = C.lag_features(S["prep"].xs(x_hist[-need:]), S["lags"])[-1]
        return (f - S["f_mu"]) @ S["Cq"]

    def _encode(self, sid, x_hist, u_hist):
        S = self.sys[sid]
        return (S["dict"](self._q(S, x_hist))[0] - S["psi_mu"]) @ S["E"]

    def _step(self, sid, z, u):
        S = self.sys[sid]
        return S["A"] @ z + S["B"] @ u + S["c"]

    def _apply_dq(self, sid, z, dq):
        S = self.sys[sid]
        qh = z @ S["Dq"] + S["dq0"]
        P = S["dict"](np.vstack([qh, qh + dq]))
        return z + (P[1] - P[0]) @ S["E"]

    def _decode_x(self, sid, z):
        S = self.sys[sid]
        return S["prep"].mu + S["prep"].sd * (z @ S["Dx"] + S["dx0"])

    def _readout(self, sid, Z, U):
        return self.sys[sid]["ro"].predict(np.hstack([Z, U]))


def _real_basis(G, lam):
    """Complex eigenvectors -> real basis (real / imaginary parts of each conjugate pair) and the exact real block dynamics
    (phi_re, phi_im)' = [[a, -b], [b, a]] (phi_re, phi_im) for lambda = a + ib."""
    order = np.argsort(-np.abs(lam))
    lam, G = lam[order], G[:, order]
    n = len(lam)
    used = np.zeros(n, bool)
    cols, blocks = [], []
    for i in range(n):
        if used[i]:
            continue
        used[i] = True
        if abs(lam[i].imag) < 1e-10:
            cols.append(G[:, i].real)
            blocks.append(np.array([[lam[i].real]]))
        else:
            j = next((j for j in range(i + 1, n) if not used[j] and abs(lam[j] - np.conj(lam[i])) < 1e-8), None)
            if j is not None:
                used[j] = True
            a_, b_ = lam[i].real, lam[i].imag
            cols += [G[:, i].real, G[:, i].imag]
            blocks.append(np.array([[a_, -b_], [b_, a_]]))
    m = sum(len(bl) for bl in blocks)
    Lam = np.zeros((m, m))
    o = 0
    for bl in blocks:
        Lam[o: o + len(bl), o: o + len(bl)] = bl
        o += len(bl)
    return np.stack(cols, 1), Lam


def fit_lifted(prep, trajs, lags, basis, r, M, bw, eps, seed=0, H=None):
    """EDMDc + ResDMD filter + balanced coordinates. Returns a dict with the full balanced system (all coordinates, ordered by
    Hankel singular value) from which k-truncations are cut."""
    f_mu = basis["f_mu"]
    Cq = basis["C"][:, :r]
    Qs = [(C.lag_features(prep.xs(t.x), lags) - f_mu) @ Cq for t in trajs]
    Qall = np.concatenate(Qs)
    dic = RBFDict(Qall, M, bw, seed)
    Ps = [dic(Q) for Q in Qs]
    psi_mu = np.concatenate(Ps).mean(0)
    X0, X1, U0 = [], [], []
    for P, t in zip(Ps, trajs):
        keep = C.free_mask(t)
        X0.append(P[:-1][keep] - psi_mu); X1.append(P[1:][keep] - psi_mu); U0.append(t.u[:-1][keep].astype(np.float64))
    X0, X1, U0 = map(np.concatenate, (X0, X1, U0))
    F = np.hstack([X0, U0, np.ones((len(X0), 1))])
    G = F.T @ F / len(F)
    reg = 1e-6 * np.trace(G) / G.shape[0] * np.eye(G.shape[0])
    Mx = np.linalg.solve(G + reg, F.T @ X1 / len(F))                 # (p + n_u + 1, p): psi_{t+1} = psi_t K + u Bt + b
    p = X0.shape[1]
    K, Bt, b = Mx[:p], Mx[p: p + prep.n_u], Mx[-1]
    lam, Gv = np.linalg.eig(K)                                        # K g = lambda g  (row convention: phi = Psi g)
    Y1 = X1 - U0 @ Bt - b
    num = np.linalg.norm(Y1 @ Gv - (X0 @ Gv) * lam[None, :], axis=0)
    den = np.linalg.norm(X0 @ Gv, axis=0) + 1e-12
    res = num / den
    keep = (res <= eps) & (np.abs(lam) <= 1.05)          # growing modes cannot be supported by bounded training data
    if keep.sum() < 2:
        keep = res <= np.sort(res)[min(len(res) - 1, 1)]
    Gr, Lam = _real_basis(Gv[:, keep], lam[keep])                      # (p, m) real eigen-coordinates, exact block dynamics
    # exact dynamics of the kept eigenfunctions phi = psi Gr: phi_{t+1} = Lam phi_t + Gr' (B u + b)
    Phi = [(P - psi_mu) @ Gr for P in Ps]
    m = Gr.shape[1]
    Ap = C.stabilise(Lam)
    Mp = np.vstack([np.zeros((m, m)), Bt @ Gr, (b @ Gr)[None, :]])
    Pall = np.concatenate(Phi)
    Yall = np.concatenate([(t.y - prep.y_mu) / prep.y_sd for t in trajs])
    Out = np.hstack([Yall, Qall / np.sqrt(max(1, r))])
    Cp = np.linalg.lstsq(np.hstack([Pall, np.ones((len(Pall), 1))]), Out, rcond=None)[0][:m].T      # (n_out, m)
    # balanced coordinates: Wc = data covariance, Wo = finite-horizon observability gramian
    H = H or max(2, prep.T // 4)
    Wc = np.cov(Pall.T)
    Wc += 1e-8 * np.trace(Wc) / m * np.eye(m)
    Wo = np.zeros((m, m))
    Ai = np.eye(m)
    for _ in range(H):
        CA = Cp @ Ai
        Wo += CA.T @ CA
        Ai = Ap @ Ai
        if not np.all(np.isfinite(Ai)) or np.abs(Ai).max() > 1e8:
            break
    Wo += 1e-9 * np.trace(Wo) / m * np.eye(m)
    Lc = np.linalg.cholesky(Wc)
    Lo = np.linalg.cholesky(Wo)
    U_, hsv, Vt_ = np.linalg.svd(Lo.T @ Lc)
    Tb = Lc @ Vt_.T / np.sqrt(hsv)[None, :]                           # phi = z Tb^T ... (column convention: phi = Tb z)
    Tinv = (U_ / np.sqrt(hsv)[None, :]).T @ Lo.T                       # z = Tinv phi
    return {"dict": dic, "psi_mu": psi_mu, "Gr": Gr, "Tinv": Tinv, "Tb": Tb, "hsv": hsv / hsv[0], "Cq": Cq, "f_mu": f_mu,
            "Qs": Qs, "Ps": Ps, "res": res, "n_kept": int(keep.sum()), "p": p, "Ap": Ap, "Bp": Mp[m: m + prep.n_u].T, "cp": Mp[-1]}


def build_system(prep, micro, trajs, lags, L, k, refit, seed=0):
    k = int(min(k, L["Tinv"].shape[0]))
    E = L["Gr"] @ L["Tinv"][:k].T                                      # psi -> z
    Zs = [(P - L["psi_mu"]) @ E for P in L["Ps"]]
    if refit == "ls":
        Z0, Z1, U0 = [], [], []
        for Z, t in zip(Zs, trajs):
            kp = C.free_mask(t)
            Z0.append(Z[:-1][kp]); Z1.append(Z[1:][kp]); U0.append(t.u[:-1][kp].astype(np.float64))
        Z0, Z1, U0 = map(np.concatenate, (Z0, Z1, U0))
        F = np.hstack([Z0, U0, np.ones((len(Z0), 1))])
        G = F.T @ F
        reg = 1e-6 * len(F) * np.eye(G.shape[0])
        reg[-1, -1] = 0
        Mz = np.linalg.solve(G + reg, F.T @ Z1)
        A, B, c = Mz[:k].T, Mz[k: k + prep.n_u].T, Mz[-1]
    else:
        Ti, Tb = L["Tinv"][:k], L["Tb"][:, :k]
        A, B, c = Ti @ L["Ap"] @ Tb, Ti @ L["Bp"], Ti @ L["cp"]
    A = C.stabilise(A)
    Zc = np.concatenate(Zs)
    Uc = np.concatenate([t.u for t in trajs]).astype(np.float64)
    Yc = np.concatenate([t.y for t in trajs]).astype(np.float64)
    Xc = np.concatenate([prep.xs(t.x) for t in trajs])
    Qc = np.concatenate(L["Qs"])
    ro = C.Ridge(1e-4).fit(np.hstack([Zc, Uc]), Yc)
    Dq = C.ridge_solve(Zc - Zc.mean(0), Qc - Qc.mean(0), 1e-5)
    dq0 = Qc.mean(0) - Zc.mean(0) @ Dq
    Dx = C.ridge_solve(Zc - Zc.mean(0), Xc - Xc.mean(0), 1e-4)
    dx0 = Xc.mean(0) - Zc.mean(0) @ Dx
    z_lo, z_hi = Zc.min(0), Zc.max(0)
    span = z_hi - z_lo
    Cq = L["Cq"]
    return {"prep": prep, "micro": micro, "lags": tuple(lags), "f_mu": L["f_mu"], "Cq": Cq, "basis": Cq[: prep.N],
            "dict": L["dict"], "psi_mu": L["psi_mu"], "E": E, "A": A, "B": B, "c": c, "ro": ro, "Dq": Dq, "dq0": dq0, "Dx": Dx,
            "dx0": dx0, "z_lo": z_lo - span, "z_hi": z_hi + span, "silence_mode": "drive", "hsv": L["hsv"],
            "n_params": {"encoder": int(Cq.size + L["dict"].c.size + E.size), "transition": int(A.size + B.size + c.size),
                         "readout": int(ro.n_params)}}


def choose_r(curve, r_cap):
    """Reduced-coordinate count: the smallest r whose held-out basis error is within 0.01 (absolute, relative-error units) of the
    curve's minimum, plus one guard coordinate, capped."""
    e = np.asarray(curve[1:], float)
    r = int(np.argmax(e <= np.nanmin(e) + 0.01)) + 1
    return int(min(r_cap, r + 1, len(e)))


@register
class KSEdmd(StateMethod):
    name = "ks_edmd"
    version = "1"
    default_config = {"k_grid": (1, 2, 3, 4, 5, 6, 8, 10), "r_cap": 8, "M": 100, "bw_grid": (1.5,), "eps_grid": (0.3, 10.0),
                      "refit_grid": ("bt", "ls"), "lag_fracs": ((0.01, 0.025), (0.01, 0.025, 0.05, 0.1)), "rel_tol": 0.05, "max_val": 16, "n_folds": 2}
    supported_sharing = ("auto", "independent")
    supports_adaptation = False

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        from .ks_sindy import lag_grid, make_basis
        C.set_threads(3)
        C.seed_all(seed)
        cfg = {**self.default_config, **(config or {})}
        if cfg.get("sharing", "auto") not in self.supported_sharing:
            raise NotImplementedError("ks_edmd: sharing mode not supported")
        if cfg.get("adapt_from") is not None:
            raise NotImplementedError("ks_edmd does not support encoder-only adaptation")
        timer = C.Timer()
        model = EDMDModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                "sharing": {"mode": "independent", "verdict": None}, "dim_curve": {}, "config": {}}
        n_tr = 0
        for sid in sorted({t.system_id for t in train}):
            trs = C.decimate([t for t in train if t.system_id == sid])
            entry = systems[sid]
            forced = cfg.get("k")
            k_grid = [int(forced)] if forced else list(cfg["k_grid"])
            units = {"traj": {}, "draw": {}}

            def score(kind, fi, va, ks_):
                prep = C.SystemPrep(sid, fi, entry)
                micro = C.MicroModel(prep, fi, seed=seed)
                for lags in lag_grid(prep.T, cfg):
                    basis = make_basis(prep, fi, lags, max(cfg["r_cap"], 2), seed)
                    r = choose_r(basis["err_curve"], cfg["r_cap"])
                    for bw in cfg["bw_grid"]:
                        for eps in cfg["eps_grid"]:
                            L = fit_lifted(prep, fi, lags, basis, r, cfg["M"], bw, eps, seed)
                            for k in ks_:
                                for refit in cfg["refit_grid"]:
                                    model.sys[sid] = build_system(prep, micro, fi, lags, L, k, refit, seed)
                                    e = C.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True)
                                    units[kind].setdefault((k, lags, bw, eps, refit), []).extend(e.tolist())
            folds = C.cv_folds(trs, cfg["n_folds"], seed, cfg["max_val"])
            for kind, fi, va in folds:
                if kind == "traj":
                    score(kind, fi, va, k_grid)
            k_sel = C.select_from_table(C.table_from_units(units["traj"], lambda c: (0,), 0.0), cfg["rel_tol"])["k"]
            for kind, fi, va in folds:
                if kind == "draw":
                    score(kind, fi, va, [k_sel])
            sel, best, table = C.two_stage_select(units["traj"], units["draw"], lambda c: (len(c[0]) > 0, c[3] != "bt", -c[2], c[1]),
                                                  cfg["rel_tol"])
            best["lags"], best["bw"], best["eps"], best["refit"] = best.pop("conf")
            for kk, row in table.items():
                row["lags"], row["bw"], row["eps"], row["refit"] = row.pop("conf")
            ks = sorted(table)
            prep_f = C.SystemPrep(sid, trs, entry)
            micro_f = C.MicroModel(prep_f, trs, seed=seed)
            basis_f = make_basis(prep_f, trs, best["lags"], max(cfg["r_cap"], 2), seed)
            r = choose_r(basis_f["err_curve"], cfg["r_cap"])
            L = fit_lifted(prep_f, trs, best["lags"], basis_f, r, cfg["M"], best["bw"], best["eps"], seed)
            S = build_system(prep_f, micro_f, trs, best["lags"], L, best["k"], best["refit"], seed)
            model.sys[sid] = S
            model.k[sid] = int(S["A"].shape[0])
            sil = model.choose_silence_mode(sid, trs, prep_f.y_var)
            curve = [{kk: v for kk, v in table[k].items() if kk != "units"} for k in ks]
            info["k"][sid] = model.k[sid]
            info["k_range"][sid] = sel["range"]
            info["dim_curve"][sid] = curve
            info["abstain"][sid] = abstention(curve, sel, prep_f.N, forced=bool(forced))
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
            info["n_params"]["transition"] += S["n_params"]["transition"]
            info["config"][sid] = {"lags": best["lags"], "r": r, "M": cfg["M"], "bw": best["bw"], "eps": best["eps"], "refit": best["refit"],
                                   "n_modes_kept": L["n_kept"], "lifted_dim": L["p"], "hsv": L["hsv"][:12].tolist(),
                                   "silence_mode": S["silence_mode"], "silence_errors": sil}
            n_tr += len(trs)
        info["train_cost"] = {"cpu_s": timer.cpu(), "wall_s": timer.wall(), "sim_calls": 0, "n_trajectories": n_tr}
        info["lipschitz_bound"] = None
        model._info = info
        return model
