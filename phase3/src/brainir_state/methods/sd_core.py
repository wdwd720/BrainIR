"""Shared machinery of the "sd" family (shared cross-implementation state models): data preparation, event parsing at the
sample resolution, window sampling, simple numerics. Used by sd_shared (multi-encoder latent model with one transition law) and
sd_lowrank (unit-space low-rank RNN).

Conventions (identical in training and in rollout):
    step j maps the state at sample j to sample j+1;
    a kick at time t (step j = round(t / dt)) is added to the state at sample j BEFORE step j;
    a current / silence / edge removal over [t0, t1) acts on steps round(t0/dt) .. round(t1/dt) - 1 (t1 None = to the end).
Events on neurons outside the observed population are ignored (the model has no variable for them).
"""

from __future__ import annotations

import numpy as np

EPS = 1e-6


def set_threads(n: int = 3) -> None:
    import torch
    torch.set_num_threads(n)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass


# ------------------------------------------------------------------------------------------------------------ events
def parse_events(events: list[dict], dt: float, col: dict[int, int], n_steps: int) -> list[tuple]:
    """Protocol events -> compact list of (kind, a, b, payload) at step resolution.
    kick: payload (idx, vals); current: (idx, vals); silence: idx; edge: (post_idx, pre_idx)."""
    out = []
    for e in events or []:
        k = e["kind"]
        if k == "kick":
            ids = [(col[int(n)], float(v)) for n, v in e["delta"].items() if int(n) in col]
            if ids:
                j = int(round(float(e["t"]) / dt))
                out.append(("kick", j, j + 1, (np.array([i for i, _ in ids]), np.array([v for _, v in ids]))))
            continue
        a = int(round(float(e["t0"]) / dt))
        b = n_steps if e.get("t1") is None else int(round(float(e["t1"]) / dt))
        if k == "current":
            ids = [(col[int(n)], float(v)) for n, v in e["targets"].items() if int(n) in col]
            if ids:
                out.append(("current", a, b, (np.array([i for i, _ in ids]), np.array([v for _, v in ids]))))
        elif k == "silence":
            ids = np.array([col[int(n)] for n in e["targets"] if int(n) in col], dtype=int)
            if len(ids):
                out.append(("silence", a, b, ids))
        elif k == "edge_remove":
            pairs = [(col[int(p)], col[int(q)]) for p, q in e["edges"] if int(p) in col and int(q) in col]
            if pairs:
                out.append(("edge", a, b, (np.array([p for p, _ in pairs]), np.array([q for _, q in pairs]))))
    return out


def dense_events(parsed: list[tuple], i0: int, H: int, N: int):
    """Dense per-step arrays over steps i0 .. i0+H-1: kick (H, N), current (H, N), silence mask (H, N) and, per step, the list of
    removed edges (post, pre) (None when there are none)."""
    kick = np.zeros((H, N), np.float32)
    cur = np.zeros((H, N), np.float32)
    sil = np.zeros((H, N), np.float32)
    edges = None
    for kind, a, b, p in parsed:
        lo, hi = max(a, i0), min(b, i0 + H)
        if hi <= lo:
            continue
        if kind == "kick":
            kick[lo - i0, p[0]] += p[1]
        elif kind == "current":
            cur[lo - i0: hi - i0][:, p[0]] += p[1][None, :]
        elif kind == "silence":
            sil[lo - i0: hi - i0][:, p] = 1.0
        elif kind == "edge":
            if edges is None:
                edges = [[] for _ in range(H)]
            for j in range(lo - i0, hi - i0):
                edges[j].extend(zip(p[0].tolist(), p[1].tolist()))
    return kick, cur, sil, edges


def event_steps_mask(parsed: list[tuple], T: int) -> np.ndarray:
    """(T,) bool: samples at which some event acts (for excluding windows from free-dynamics statistics)."""
    m = np.zeros(T, bool)
    for kind, a, b, _ in parsed:
        m[max(0, a): min(T, b)] = True
    return m


# ------------------------------------------------------------------------------------------------------------ data
class SysData:
    """The training trajectories of one system in array form, plus the normalisers (training statistics only)."""

    def __init__(self, sid: str, trajs: list, entry: dict, max_samples: int = 400_000, seed: int = 0):
        self.sid = sid
        self.entry = {k: v for k, v in entry.items() if k in ("local_graph", "signs", "observed", "targets_public", "input_dim")}
        self.obs = [int(n) for n in entry["observed"]]
        self.col = {n: i for i, n in enumerate(self.obs)}
        self.N = len(self.obs)
        trajs = sorted(trajs, key=lambda t: t.key)
        self.dt = float(trajs[0].dt)
        # cap the number of samples (deterministic, stratified by split and family); memory: <= ~40M floats of x per system
        max_samples = int(min(max_samples, 40_000_000 / max(1, len(entry["observed"]))))
        tot = sum(len(t.t) for t in trajs)
        if tot > max_samples:
            rng = np.random.default_rng(seed)
            keep_frac = max_samples / tot
            groups: dict = {}
            for t in trajs:
                groups.setdefault((t.split, t.family), []).append(t)
            sel = []
            for g in sorted(groups):
                lst = groups[g]
                n = max(1, int(round(len(lst) * keep_frac)))
                idx = np.sort(rng.permutation(len(lst))[:n])
                sel += [lst[i] for i in idx]
            trajs = sorted(sel, key=lambda t: t.key)
        self.trajs_meta = [(t.key, t.split, t.family) for t in trajs]
        self.X = [np.asarray(t.x, np.float32) for t in trajs]
        self.U = [np.asarray(t.u, np.float32) for t in trajs]
        self.Y = [np.asarray(t.y, np.float32) for t in trajs]
        self.EV = [parse_events(t.events(), self.dt, self.col, len(t.t)) for t in trajs]
        self.split = np.array([t.split for t in trajs])
        if not (self.split == "val").any() and len(trajs) >= 5:
            # no validation split given: hold out every 5th trajectory (deterministic) for model selection
            self.split = np.array(["val" if i % 5 == 4 else sp for i, sp in enumerate(self.split)])
        self.r0zero = np.array([(t.protocol.get("r0") or {}).get("kind", "zero") == "zero" for t in trajs])
        self.n_u = self.U[0].shape[1]
        self.n_y = self.Y[0].shape[1]
        tr = [i for i in range(len(self.X)) if self.split[i] != "val"] or list(range(len(self.X)))
        Xa = np.concatenate([self.X[i] for i in tr]).astype(np.float64)
        finite = np.isfinite(Xa).all(1)
        Xa = Xa[finite]
        self.mu = Xa.mean(0)
        sd = Xa.std(0)
        self.sd = np.maximum(sd, max(1e-3, 1e-2 * float(np.median(sd)) if sd.size else 1e-3))
        Ua = np.concatenate([self.U[i] for i in tr]).astype(np.float64)
        self.u_mu = Ua.mean(0)
        self.u_sd = np.maximum(Ua.std(0), 1e-6)
        Ya = np.concatenate([self.Y[i] for i in tr]).astype(np.float64)
        self.y_mu = Ya.mean(0)
        self.y_var = np.maximum(Ya.var(0), max(1e-6, 1e-3 * float(Ya.var(0).max())))
        self.y_sd = np.sqrt(self.y_var)
        rows = [self.X[i][0] for i in range(len(self.X)) if self.r0zero[i]] or [x[0] for x in self.X]
        self.rest = np.median(np.stack(rows).astype(np.float64), axis=0)
        self.nonneg = bool(min(float(np.nanmin(x)) for x in self.X) >= -1e-9)
        self.train_idx = np.array(tr)
        self.val_idx = np.array([i for i in range(len(self.X)) if self.split[i] == "val"])
        self.finite = np.array([bool(np.isfinite(x).all() and np.abs(x).max() < 1e6) for x in self.X])

    def xs(self, x):
        return (np.asarray(x, np.float64) - self.mu) / self.sd

    def pca(self, n: int = 10, idx=None):
        idx = self.train_idx if idx is None else idx
        Xs = np.concatenate([self.xs(self.X[i][::2]) for i in idx if self.finite[i]])
        _, s, Vt = np.linalg.svd(Xs - Xs.mean(0), full_matrices=False)
        return Xs.mean(0), Vt[: min(n, Vt.shape[0])], s[: min(n, len(s))] ** 2 / len(Xs)

    def timescale(self) -> float:
        """Characteristic time of the dominant population signal: sd(p) / sd(dp/dt) of the leading PCs of the standardised x,
        with the derivative taken over a lag (robust to per-sample noise)."""
        m, V, _ = self.pca(3)
        lag = max(1, int(round(0.05 / self.dt))) if self.dt >= 0.005 else max(1, int(round(0.01 / self.dt)))
        ts = []
        for i in self.train_idx:
            if not self.finite[i]:
                continue
            P = (self.xs(self.X[i]) - m) @ V.T
            if len(P) <= lag + 1:
                continue
            d = (P[lag:] - P[:-lag]) / (lag * self.dt)
            ts.append(P.std(0) / (d.std(0) + 1e-9))
        if not ts:
            return 0.1
        return float(np.clip(np.median(np.stack(ts)), 5 * self.dt, 5.0))


def current_gain(sd: SysData, win_s: float = 0.03) -> tuple[float | None, int]:
    """Direct estimate of the unit response to injected current: at each training current onset on an observed unit j,
    (mean dx_j/dt over the first win_s of the pulse - mean dx_j/dt over the win_s before) / I_j. Returns the |I|-weighted median
    over events (raw units: dx_j/dt per unit of current) and the number of events (None if there are none)."""
    m = max(1, min(3, int(round(win_s / sd.dt))))
    vals, wts = [], []
    for i in sd.train_idx:
        X = sd.X[i]
        for kind, a, b, p in sd.EV[i]:
            if kind != "current" or a - m < 1 or a + m >= len(X) or b - a < 1:
                continue
            mm = min(m, b - a)
            for j, I in zip(p[0], p[1]):
                if abs(I) < 1e-9:
                    continue
                d_in = (X[a + mm, j] - X[a, j]) / (mm * sd.dt)
                d_pre = (X[a, j] - X[a - m, j]) / (m * sd.dt)
                vals.append(float((d_in - d_pre) / I))
                wts.append(abs(float(I)))
    if not vals:
        return None, 0
    o = np.argsort(vals)
    v, w = np.array(vals)[o], np.array(wts)[o]
    c = np.cumsum(w)
    return float(max(v[np.searchsorted(c, 0.5 * c[-1])], 0.0)), len(vals)


def predictive_encoder(sd: SysData, k: int, lags_s=(0.05, 0.1, 0.2, 0.4), ridge: float = 1e-3, max_rows: int = 60_000,
                       seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Reduced-rank regression of the future standardised microstate (several lags) on the present one (plus the input at both
    times, so input-driven responses are not attributed to the state): the rank-k predictive subspace. Returns (E, D, m): encoder
    rows E (k x N; z = E xs, whitened on the training data), a least-squares decoder D (N x k) and the mean m of xs.
    Why: with process noise in every direction, the directions of x that predict the future are the dynamically relevant
    (oblique) projection onto the slow manifold, which is what an intervention on a unit is transmitted through; PCA instead
    returns the high-variance directions."""
    rng = np.random.default_rng(seed)
    lags = sorted({max(1, int(round(l / sd.dt))) for l in lags_s})
    Lmax = lags[-1]
    Xr, Fr, Ur = [], [], []
    for i in sd.train_idx:
        if not sd.finite[i]:
            continue
        X = sd.xs(sd.X[i])
        U = (np.asarray(sd.U[i], np.float64) - sd.u_mu) / sd.u_sd
        ev = event_steps_mask(sd.EV[i], len(X))
        T = len(X)
        if T <= Lmax + 1:
            continue
        ok = np.ones(T - Lmax, bool)
        if ev.any():
            c = np.concatenate([[0], np.cumsum(ev)])
            ok = (c[np.arange(T - Lmax) + Lmax + 1] - c[np.arange(T - Lmax)]) == 0
        t = np.flatnonzero(ok)
        if len(t) == 0:
            continue
        Xr.append(X[t])
        Fr.append(np.hstack([X[t + L] for L in lags]))
        Ur.append(np.hstack([U[t]] + [U[t + L] for L in lags]))
    X = np.concatenate(Xr)
    F = np.concatenate(Fr)
    Uf = np.concatenate(Ur)
    if len(X) > max_rows:
        sel = np.sort(rng.permutation(len(X))[:max_rows])
        X, F, Uf = X[sel], F[sel], Uf[sel]
    m = X.mean(0)
    A = np.hstack([X - m, Uf - Uf.mean(0)])
    Fc = F - F.mean(0)
    G = A.T @ A
    lam = ridge * np.trace(G) / G.shape[0]
    B = np.linalg.solve(G + lam * np.eye(G.shape[0]), A.T @ Fc)
    Bx = B[: X.shape[1]]
    Fhat = (X - m) @ Bx
    _, _, Vt = np.linalg.svd(Fhat, full_matrices=False)
    kk = min(k, Vt.shape[0])
    E = (Bx @ Vt[:kk].T).T                     # k x N: projection of the predicted future on its top directions
    Z = (X - m) @ E.T
    C = np.cov(Z.T) if kk > 1 else np.array([[np.var(Z[:, 0])]])
    w, V = np.linalg.eigh(np.atleast_2d(C))
    Wh = V @ np.diag(1.0 / np.sqrt(np.maximum(w, 1e-9))) @ V.T
    E = Wh @ E
    if kk < k:
        E = np.vstack([E, rng.standard_normal((k - kk, E.shape[1])) * 0.01])
    Z = (X - m) @ E.T
    D = np.linalg.lstsq(Z, X - m, rcond=None)[0].T          # N x k
    return E.astype(np.float32), D.astype(np.float32), m.astype(np.float32)


def graph_prior(sd: SysData):
    """Public structural prior of a real circuit restricted to the observed units: (sign of each unit as a presynaptic partner:
    +1 / -1 / 0 unknown, adjacency A[post, pre] = 1 where the local graph has an edge). None when the entry has no graph."""
    import json as _json
    g, sg = sd.entry.get("local_graph"), sd.entry.get("signs")
    if not g or not sg:
        return None
    g = _json.loads(g) if isinstance(g, str) else g
    sg = _json.loads(sg) if isinstance(sg, str) else sg
    sign = np.array([float(sg.get(str(n), sg.get(n, 0)) or 0) for n in sd.obs])
    A = np.zeros((sd.N, sd.N), np.float32)
    for post, pre, _ in g.get("edges_post_pre_signed_count", []):
        if int(post) in sd.col and int(pre) in sd.col:
            A[sd.col[int(post)], sd.col[int(pre)]] = 1.0
    return sign.astype(np.float32), A


def window_starts(sd: SysData, idx: np.ndarray, H: int) -> list[tuple[int, int]]:
    out = []
    for i in idx:
        if not sd.finite[i]:
            continue
        T = len(sd.X[i])
        for t0 in range(0, T - H - 1):
            out.append((int(i), t0))
    return out


def batch_windows(sd: SysData, starts: list[tuple[int, int]], H: int, need_events: bool = True):
    """Arrays for a batch of windows: x (B, H+1, N), u (B, H+1, n_u), y (B, H+1, n_y), kick / cur / sil (B, H, N)."""
    B = len(starts)
    x = np.stack([sd.X[i][t0: t0 + H + 1] for i, t0 in starts])
    u = np.stack([sd.U[i][t0: t0 + H + 1] for i, t0 in starts])
    y = np.stack([sd.Y[i][t0: t0 + H + 1] for i, t0 in starts])
    kick = np.zeros((B, H, sd.N), np.float32)
    cur = np.zeros((B, H, sd.N), np.float32)
    sil = np.zeros((B, H, sd.N), np.float32)
    has = False
    if need_events:
        for b, (i, t0) in enumerate(starts):
            if sd.EV[i]:
                k, c, s, _ = dense_events(sd.EV[i], t0, H, sd.N)
                kick[b], cur[b], sil[b] = k, c, s
                has = True
    return x, u, y, kick, cur, sil, has


def se_mean(v) -> tuple[float, float]:
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return float("nan"), float("nan")
    return float(v.mean()), float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else 0.0


def choose_dimension(curve: list[dict], key: str = "score") -> tuple[int | None, dict]:
    """The generic dimension rule shared by the sd methods. curve: [{"k", score, "se", optional "per": per-validation-trajectory
    scores}] in increasing k. With per-trajectory scores (paired over the same validation trajectories):
        k acceptable  <=>  mean_i (score_k,i - score_best,i) <= max(1.645 SE of that paired difference, 5 % of the best, 0.002)
    (one-sided 95 %: k is not significantly worse than the best, or within 5 %); without them the unpaired SE of the best is
    used. k* = the smallest acceptable k. 'plateau_reached' = the best is not at the largest k tried, or the last two k are
    within tolerance of each other."""
    ok = [c for c in curve if np.isfinite(c[key])]
    if not ok:
        return None, {"plateau_reached": False, "acceptable": []}
    best = min(ok, key=lambda c: c[key])

    def tol_of(c):
        pa, pb = c.get("per"), best.get("per")
        if pa is not None and pb is not None and len(pa) == len(pb) and len(pa) > 1:
            d = np.asarray(pa, float) - np.asarray(pb, float)
            return float(max(1.645 * d.std(ddof=1) / np.sqrt(len(d)), 0.05 * best[key], 0.002)), float(d.mean())
        return float(max(best.get("se", 0.0), 0.05 * best[key], 0.002)), float(c[key] - best[key])

    acc, tols = [], {}
    for c in ok:
        t, d = tol_of(c)
        tols[c["k"]] = t
        if d <= t:
            acc.append(c["k"])
    k_sel = min(acc)
    last = ok[-1]
    flat = len(ok) >= 2 and abs(ok[-1][key] - ok[-2][key]) <= tols[ok[-1]["k"]]
    plateau = bool(best["k"] < last["k"] or flat or k_sel < last["k"])
    return int(k_sel), {"plateau_reached": plateau, "tol": float(tols[best["k"]]), "best_k": int(best["k"]), "best": float(best[key]),
                        "acceptable": [int(k) for k in acc]}
