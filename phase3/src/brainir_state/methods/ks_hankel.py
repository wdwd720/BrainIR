"""ks_hankel: Hankel / delay DMD with control (baseline of family C).

Mathematics
-----------
    p_t = V_r^T (x_t - mu) / sd                          top-r PCA scores of the standardised microstate (training PCA)
    h_t = [p_t, p_{t-d}, ..., p_{t-(L-1)d}]              causal delay (Hankel) vector; edge-padded before t = 0
    z_t = T_k^T h_t                                      top-k right singular vectors of the training Hankel matrix (POD of h)
    z_{t+1} = A z_t + B u_t + c                          DMDc: ridge least squares on free (event-free) transitions
    y_t = C z_t + D u_t + e                              ridge readout
Events enter through the encoder: a microstate increment dx at the current sample changes the newest delay block only,
dz = T_k[block 0]^T V_r^T (dx / sd); currents / silencing / edge removal are per-step increments from the shared microscopic
coupling estimate (ks_core.MicroModel). k is everything carried between steps (the delays are inside z).

Selection (generic): delay configurations (L, d) and k in a ladder are compared by the validation rollout error; k is the smallest
within tolerance of the best (ks_core.select_dimension).
"""

from __future__ import annotations

import numpy as np

from ..api import StateMethod, register
from . import ks_core as C
from .ks_abstain import abstention


class HankelModel(C.KSModel):
    def _feat(self, S, xs_hist):
        """Hankel vector of the last sample from a standardised history (T, N)."""
        P = S["V"]
        T = len(xs_hist)
        blocks = [xs_hist[max(0, T - 1 - l * S["d"])] @ P for l in range(S["L"])]
        return np.concatenate(blocks)

    def _encode(self, sid, x_hist, u_hist):
        S = self.sys[sid]
        need = (S["L"] - 1) * S["d"] + 1
        xs = S["prep"].xs(x_hist[-need:])
        return (self._feat(S, xs) - S["h_mu"]) @ S["Tk"]

    def _step(self, sid, z, u):
        S = self.sys[sid]
        return S["A"] @ z + S["B"] @ u + S["c"]

    def _apply_dq(self, sid, z, dq):
        return z + dq @ self.sys[sid]["T0"]

    def _decode_x(self, sid, z):
        S = self.sys[sid]
        return S["prep"].mu + S["prep"].sd * (z @ S["Dx"] + S["dx0"])

    def _readout(self, sid, Z, U):
        return self.sys[sid]["ro"].predict(np.hstack([Z, U]))


def _hankel_series(prep, V, L, d, tr):
    xs = prep.xs(tr.x) @ V
    T = len(xs)
    return np.hstack([xs[np.maximum(0, np.arange(T) - l * d)] for l in range(L)])


def fit_hankel_system(sid, trajs, entry, L, d, k_list, r_pca, lam=1e-4, seed=0, prep=None, micro=None):
    """Fit Hankel-DMDc models for several k at once (shared POD). Returns {k: system dict}."""
    prep = prep or C.SystemPrep(sid, trajs, entry)
    micro = micro or C.MicroModel(prep, trajs, seed=seed)
    Xs = np.concatenate([prep.xs(t.x) for t in trajs])
    _, _, Vt = np.linalg.svd(Xs[:: max(1, len(Xs) // 20000)] - Xs.mean(0), full_matrices=False)
    V = Vt[: min(r_pca, Vt.shape[0])].T
    Hs = [_hankel_series(prep, V, L, d, t) for t in trajs]
    Hall = np.concatenate(Hs)
    h_mu = Hall.mean(0)
    _, sv, Wt = np.linalg.svd(Hall[:: max(1, len(Hall) // 20000)] - h_mu, full_matrices=False)
    out = {}
    for k in k_list:
        k = int(min(k, Wt.shape[0]))
        Tk = Wt[:k].T
        Z0, Z1, U0, Zall, Uall, Yall, Xall = [], [], [], [], [], [], []
        for t, h in zip(trajs, Hs):
            z = (h - h_mu) @ Tk
            keep = C.free_mask(t)
            Z0.append(z[:-1][keep]); Z1.append(z[1:][keep]); U0.append(t.u[:-1][keep])
            Zall.append(z); Uall.append(t.u); Yall.append(t.y); Xall.append(prep.xs(t.x))
        Z0, Z1, U0 = map(np.concatenate, (Z0, Z1, U0))
        F = np.hstack([Z0, U0, np.ones((len(Z0), 1))])
        G = F.T @ F
        reg = lam * len(F) * np.eye(G.shape[0])
        reg[-1, -1] = 0.0
        M = np.linalg.solve(G + reg, F.T @ Z1)
        A, B, c = C.stabilise(M[:k].T), M[k: k + prep.n_u].T, M[-1]
        Zc, Uc, Yc, Xc = map(np.concatenate, (Zall, Uall, Yall, Xall))
        ro = C.Ridge(1e-4).fit(np.hstack([Zc, Uc]), Yc)
        Dx = C.ridge_solve(Zc - Zc.mean(0), Xc - Xc.mean(0), 1e-4)
        dx0 = Xc.mean(0) - Zc.mean(0) @ Dx
        z_lo, z_hi = Zc.min(0), Zc.max(0)
        span = z_hi - z_lo
        out[k] = {"prep": prep, "micro": micro, "V": V, "L": L, "d": d, "h_mu": h_mu, "Tk": Tk, "T0": Tk[: V.shape[1]],
                  "basis": V, "A": A, "B": B, "c": c, "ro": ro, "Dx": Dx, "dx0": dx0, "z_lo": z_lo - span, "z_hi": z_hi + span,
                  "hsv": sv / (sv[0] + 1e-12), "silence_mode": "drive",
                  "n_params": {"encoder": int(V.size + Tk.size + h_mu.size), "transition": int(A.size + B.size + c.size),
                               "readout": int(ro.n_params)}}
    return out


@register
class KSHankel(StateMethod):
    name = "ks_hankel"
    version = "1"
    default_config = {"k_grid": (1, 2, 3, 4, 5, 6, 8, 10, 12), "L_grid": (1, 2, 4), "span_frac": (0.02, 0.06), "r_pca": 24,
                      "rel_tol": 0.05, "max_val": 16, "n_folds": 2}
    supported_sharing = ("auto", "independent")
    supports_adaptation = False

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        C.set_threads(3)
        cfg = {**self.default_config, **(config or {})}
        if cfg.get("sharing", "auto") not in self.supported_sharing:
            raise NotImplementedError("ks_hankel fits independent models only")
        if cfg.get("adapt_from") is not None:
            raise NotImplementedError("ks_hankel does not support encoder-only adaptation")
        timer = C.Timer()
        model = HankelModel()
        info = {"k": {}, "k_range": {}, "abstain": {}, "n_params": {"encoder": {}, "transition": 0, "readout": {}},
                "sharing": {"mode": "independent", "verdict": None}, "dim_curve": {}, "config": {}}
        n_tr = 0
        for sid in sorted({t.system_id for t in train}):
            trs = C.decimate([t for t in train if t.system_id == sid])
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
            units: dict = {}
            for fi, va in C.draw_folds(trs, cfg["n_folds"], seed, cfg["max_val"]):
                prep = C.SystemPrep(sid, fi, entry)
                micro = C.MicroModel(prep, fi, seed=seed)
                for (L, d) in configs:
                    fits = fit_hankel_system(sid, fi, entry, L, d, k_grid, cfg["r_pca"], seed=seed, prep=prep, micro=micro)
                    for k, S in fits.items():
                        model.sys[sid] = S
                        e = C.val_rollout_error(model, sid, va, scale=prep.y_var, return_units=True)
                        units.setdefault((k, L, d), []).extend(e.tolist())
            table = C.table_from_units(units, lambda c: (c[0], c[0] * c[1]), cfg["rel_tol"])
            ks = sorted(table)
            sel = C.select_from_table(table, cfg["rel_tol"])
            k = sel["k"]
            L, d = table[k]["conf"]
            # final fit on all trajectories at the selected configuration
            prep_f = C.SystemPrep(sid, trs, entry)
            micro_f = C.MicroModel(prep_f, trs, seed=seed)
            S = fit_hankel_system(sid, trs, entry, L, d, [k], cfg["r_pca"], seed=seed, prep=prep_f, micro=micro_f)[k]
            model.sys[sid] = S
            model.k[sid] = int(S["Tk"].shape[1])
            sil_res = model.choose_silence_mode(sid, trs, prep_f.y_var)
            curve = [{"k": kk, "val_nmse": table[kk]["val_nmse"], "se": table[kk]["se"], "L": table[kk]["conf"][0],
                      "d": table[kk]["conf"][1]} for kk in ks]
            info["k"][sid] = model.k[sid]
            info["k_range"][sid] = sel["range"]
            info["dim_curve"][sid] = curve
            info["abstain"][sid] = abstention(curve, sel, prep_f.N, forced=bool(forced))
            info["n_params"]["encoder"][sid] = S["n_params"]["encoder"]
            info["n_params"]["readout"][sid] = S["n_params"]["readout"]
            info["n_params"]["transition"] += S["n_params"]["transition"]
            info["config"][sid] = {"L": L, "d": d, "silence_mode": S["silence_mode"], "silence_errors": sil_res,
                                   "gamma": micro_f.gamma, "micro_r2": micro_f.r2}
            n_tr += len(trs)
        info["train_cost"] = {"cpu_s": timer.cpu(), "wall_s": timer.wall(), "sim_calls": 0, "n_trajectories": n_tr}
        info["lipschitz_bound"] = None
        model._info = info
        return model
