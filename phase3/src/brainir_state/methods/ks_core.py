"""Shared core of the ks_* state-discovery methods (families B / C: sparse nonlinear identification and Koopman-style models).

Everything here is generic (no system-specific constants); all statistics come from the training trajectories handed to fit().

Pieces
------
SystemPrep          per-system preprocessing: observed-column map, causal standardisation of x (training mean / sd), rest state,
                    readout normalisation, input statistics.
compile_events      protocol events -> per-step arrays (kicks, injected currents, silenced neurons, removed edges) on a rollout grid.
free_mask           transitions of a training trajectory that are free dynamics (no event acting).
MicroModel          a microscopic linear model of the observed units, dx_{t+1} - x_t = A x_t + B u_t + c + gamma * I_t, fitted by ridge
                    on free transitions (A, B, c) and on current windows (one global current gain gamma). It is the STRUCTURE through
                    which held-out event types enter a latent model: an injected current adds gamma * I to x per step, silencing
                    neuron j removes its outgoing couplings (a current -A[i, j] x_j into every other neuron i), removing edge (i, j)
                    removes -A[i, j] x_j. No per-neuron lookup table: every neuron is handled by the same fitted coupling estimate.
predictive_basis    reduced-rank ridge regression from the (standardised, optionally delay-augmented) microstate at t to the future
                    (readout and top PCs of x at a ladder of horizons), with future inputs partialled out (Frisch-Waugh). The left
                    factor is a linear encoder ordered by predictive importance (CVA-like; y is only a TARGET, never an input).
val_rollout_error   the generic validation criterion: window NMSE of the readout over rollouts (with the trajectory's own events)
                    from several start times on held-out trajectories, horizon = a quarter of the trajectory length.
select_dimension    the generic dimension rule: the smallest k whose validation error is within a tolerance of the best k.
KSModel             StateModel base class: event handling in rollouts for every subclass (through the encoder, `apply_dq`).
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from ..api import StateModel

# ------------------------------------------------------------------------------------------------------------ small helpers


def ridge_solve(X: np.ndarray, Y: np.ndarray, lam: float) -> np.ndarray:
    """argmin ||Y - X W||^2 + lam * n * ||W||^2 (X, Y already centred / scaled as the caller wants)."""
    G = X.T @ X
    n = max(1, len(X))
    return np.linalg.solve(G + lam * n * np.eye(G.shape[0]), X.T @ Y)


class Ridge:
    """Ridge regression with standardised features and an intercept (numpy only, picklable)."""

    def __init__(self, lam: float = 1e-3):
        self.lam = lam

    def fit(self, X, Y):
        X = np.asarray(X, float)
        Y = np.asarray(Y, float)
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        self.ym = Y.mean(0)
        self.W = ridge_solve((X - self.mu) / self.sd, Y - self.ym, self.lam)
        return self

    def predict(self, X):
        return ((np.asarray(X, float) - self.mu) / self.sd) @ self.W + self.ym

    @property
    def n_params(self) -> int:
        return int(self.W.size + self.ym.size)


def seed_all(seed: int):
    import torch
    torch.manual_seed(seed)
    np.random.seed(seed % (2 ** 32))


def set_threads(n: int = 3):
    try:
        import torch
        torch.set_num_threads(n)
    except Exception:  # pragma: no cover
        pass


# ------------------------------------------------------------------------------------------------------------ events
@dataclass
class EventGrid:
    """Events on a grid of n_steps transitions (step j goes from sample j to sample j + 1)."""
    kick: dict = field(default_factory=dict)            # step -> dx (N,) applied to the state at sample j before stepping
    cur: np.ndarray | None = None                       # (n_steps, N) injected current during step j
    sil: list = field(default_factory=list)             # per step: array of silenced columns (or None)
    edges: list = field(default_factory=list)           # per step: (post_cols, pre_cols) arrays (or None)
    any_cont: np.ndarray | None = None                  # (n_steps,) bool: some continuous event acts during step j

    def empty(self) -> bool:
        return not self.kick and (self.any_cont is None or not self.any_cont.any())


def compile_events(events: list[dict], n_steps: int, dt: float, col: dict[int, int], n: int) -> EventGrid:
    g = EventGrid(cur=np.zeros((n_steps, n)), sil=[None] * n_steps, edges=[None] * n_steps, any_cont=np.zeros(n_steps, bool))
    sil_sets = [set() for _ in range(n_steps)]
    edge_lists = [[] for _ in range(n_steps)]
    for e in events or []:
        kind = e["kind"]
        if kind == "kick":
            j = int(round(e["t"] / dt))
            if 0 <= j < n_steps:
                dx = g.kick.setdefault(j, np.zeros(n))
                for k, v in e["delta"].items():
                    if int(k) in col:
                        dx[col[int(k)]] += float(v)
            continue
        a = max(0, int(round(e["t0"] / dt)))
        b = n_steps if e.get("t1") is None else min(n_steps, int(round(e["t1"] / dt)))
        if b <= a:
            continue
        if kind == "current":
            for k, v in e["targets"].items():
                if int(k) in col:
                    g.cur[a:b, col[int(k)]] += float(v)
            g.any_cont[a:b] = True
        elif kind == "silence":
            cs = {col[int(k)] for k in e["targets"] if int(k) in col}
            for j in range(a, b):
                sil_sets[j] |= cs
            g.any_cont[a:b] = True
        elif kind == "edge_remove":
            ed = [(col[int(p)], col[int(q)]) for p, q in e["edges"] if int(p) in col and int(q) in col]
            for j in range(a, b):
                edge_lists[j] += ed
            g.any_cont[a:b] = True
    for j in range(n_steps):
        if sil_sets[j]:
            g.sil[j] = np.array(sorted(sil_sets[j]), int)
        if edge_lists[j]:
            ed = sorted(set(edge_lists[j]))
            g.edges[j] = (np.array([p for p, _ in ed], int), np.array([q for _, q in ed], int))
    return g


def free_mask_events(events: list[dict], T: int, dt: float, drop_current: bool = True, kinds=None) -> np.ndarray:
    """(T-1,) bool: transition i -> i+1 is free of the given events (no kick at i, no silencing / edge removal / current acting)."""
    keep = np.ones(T - 1, bool)
    for e in events:
        if kinds is not None and e["kind"] not in kinds:
            continue
        if e["kind"] == "kick":
            j = int(round(e["t"] / dt))
            if 0 <= j < T - 1:
                keep[j] = False
        else:
            a = int(round(e["t0"] / dt))
            b = T - 1 if e.get("t1") is None else int(round(e["t1"] / dt))
            if e["kind"] != "current" or drop_current:
                keep[max(0, a): max(0, b)] = False
    return keep


def free_mask(tr, drop_current: bool = True) -> np.ndarray:
    return free_mask_events(tr.events(), len(tr.t), tr.dt, drop_current)


def event_free_after(keep: np.ndarray) -> np.ndarray:
    """(T-1,) number of consecutive free transitions starting at each index."""
    n = len(keep)
    run = np.zeros(n + 1, int)
    for i in range(n - 1, -1, -1):
        run[i] = run[i + 1] + 1 if keep[i] else 0
    return run[:n]


# ------------------------------------------------------------------------------------------------------------ system preprocessing
class SystemPrep:
    """Per-system causal preprocessing, fitted on training trajectories only."""

    def __init__(self, sid: str, trajs: list, entry: dict):
        self.sid = sid
        self.observed = [int(n) for n in entry["observed"]]
        self.col = {n: i for i, n in enumerate(self.observed)}
        self.N = len(self.observed)
        X = np.concatenate([t.x for t in trajs]).astype(np.float64)
        Y = np.concatenate([t.y for t in trajs]).astype(np.float64)
        U = np.concatenate([t.u for t in trajs]).astype(np.float64)
        self.dt = float(trajs[0].dt)
        self.T = int(np.median([len(t.t) for t in trajs]))
        self.mu = X.mean(0)
        sd = X.std(0)
        self.sd = sd + 0.05 * float(np.median(sd)) + 1e-9          # floor: near-silent units are not amplified
        self.y_mu, self.y_sd = Y.mean(0), Y.std(0) + 1e-9
        self.y_var = np.maximum(Y.var(0), max(1e-6, 1e-3 * float(Y.var(0).max())))   # the evaluator's normaliser (public rule)
        self.u_mu, self.u_sd = U.mean(0), U.std(0) + 1e-9
        self.n_u, self.n_y = U.shape[1], Y.shape[1]
        self.nonneg = bool((X >= -1e-9).all())
        rows = [t.x[0] for t in trajs if (t.protocol.get("r0") or {}).get("kind", "zero") == "zero"] or [t.x[0] for t in trajs]
        self.rest = np.median(np.stack(rows).astype(np.float64), axis=0)
        self.x_lo, self.x_hi = X.min(0), X.max(0)

    def xs(self, x: np.ndarray) -> np.ndarray:
        return (np.asarray(x, np.float64) - self.mu) / self.sd


# ------------------------------------------------------------------------------------------------------------ microscopic model
class MicroModel:
    """dx = x_{t+1} - x_t = A x_t + B u_t + c + gamma I_t on observed units (ridge; A over standardised units internally)."""

    def __init__(self, prep: SystemPrep, trajs: list, lam: float = 1e-2, max_rows: int = 60000, seed: int = 0):
        N = prep.N
        Xs, Us, D, Xc, Dc, Ic, Gs = [], [], [], [], [], [], []
        for ti, tr in enumerate(trajs):
            x = tr.x.astype(np.float64)
            keep = free_mask(tr, drop_current=True)
            d = x[1:] - x[:-1]
            Xs.append(x[:-1][keep]); Us.append(tr.u[:-1][keep].astype(np.float64)); D.append(d[keep])
            Gs.append(np.full(int(keep.sum()), ti))
            cur = compile_events([e for e in tr.events() if e["kind"] == "current"], len(tr.t) - 1, tr.dt, prep.col, N).cur
            other = free_mask_events(tr.events(), len(tr.t), tr.dt, kinds=("kick", "silence", "edge_remove"))
            m = (np.abs(cur).sum(1) > 0) & other
            if m.any():
                Xc.append(np.hstack([x[:-1][m], tr.u[:-1][m].astype(np.float64)])); Dc.append(d[m]); Ic.append(cur[m])
        X = np.concatenate(Xs); U = np.concatenate(Us); Dd = np.concatenate(D); Gr = np.concatenate(Gs)
        rng = np.random.default_rng(seed)
        if len(X) > max_rows:
            sel = rng.choice(len(X), max_rows, replace=False)
            X, U, Dd, Gr = X[sel], U[sel], Dd[sel], Gr[sel]
        F = np.hstack([(X - prep.mu) / prep.sd, (U - prep.u_mu) / prep.u_sd])
        fm = F.mean(0)
        dm = Dd.mean(0)
        W = ridge_solve(F - fm, Dd - dm, lam)                   # (N + n_u, N)
        # reduced-rank coupling (RRR on the fitted increments): the rank is the smallest whose held-out one-step error (trajectory
        # split) is within 1 % of the best; only the identifiable low-dimensional part of the connectivity is used for events
        self.rank = N
        ids = np.unique(Gr)
        if len(ids) >= 4:
            va = np.isin(Gr, rng.permutation(ids)[: len(ids) // 4])
            Wt = ridge_solve(F[~va] - fm, Dd[~va] - dm, lam)
            _, _, Vt = np.linalg.svd((F[~va] - fm) @ Wt, full_matrices=False)
            cands = sorted({r for r in (1, 2, 3, 4, 6, 8, 12, 16, 24, 32) if r < N} | {N})
            errs = [float((((F[va] - fm) @ Wt @ Vt[:r].T @ Vt[:r] - (Dd[va] - dm)) ** 2).sum()) for r in cands]
            best = min(errs)
            self.rank = next(r for r, e in zip(cands, errs) if e <= best * 1.01)
        _, _, Vt = np.linalg.svd((F - fm) @ W, full_matrices=False)
        Wr = W @ Vt[: self.rank].T @ Vt[: self.rank]
        # A in raw x units: dx = (x - mu)/sd @ W_x  ->  A[i, j] = W_x[j, i] / sd[j]
        self.A = (W[:N] / prep.sd[:, None]).T                     # (N, N): row = post, column = pre
        self.Bu = (W[N:] / prep.u_sd[:, None]).T                   # (N, n_u)
        self.A_off = (Wr[:N] / prep.sd[:, None]).T
        np.fill_diagonal(self.A_off, 0.0)
        # split-half reliability of the individual coupling entries (trajectory halves): edge-removal effects rest on single
        # entries and are scaled by it (0 = entries are noise, 1 = reproducible)
        self.reliability = 0.0
        if len(ids) >= 4:
            h = np.isin(Gr, rng.permutation(ids)[: len(ids) // 2])
            W1 = ridge_solve(F[h] - F[h].mean(0), Dd[h] - Dd[h].mean(0), lam)[:N]
            W2 = ridge_solve(F[~h] - F[~h].mean(0), Dd[~h] - Dd[~h].mean(0), lam)[:N]
            off = ~np.eye(N, dtype=bool)
            a, b = W1[off], W2[off]
            if a.std() > 0 and b.std() > 0:
                self.reliability = float(np.clip(np.corrcoef(a, b)[0, 1], 0.0, 1.0))
        # global current gain gamma: residual of the free model during current windows regressed on the injected current
        self.gamma = 0.0
        if Xc:
            XcU = np.concatenate(Xc); Dcc = np.concatenate(Dc); Icc = np.concatenate(Ic)
            Fc = np.hstack([(XcU[:, :N] - prep.mu) / prep.sd, (XcU[:, N:] - prep.u_mu) / prep.u_sd])
            pred = (Fc - fm) @ W + dm
            r = Dcc - pred
            den = float((Icc ** 2).sum())
            if den > 0:
                self.gamma = float((r * Icc).sum() / den)
        # diagnostic: one-step R^2 of the free model
        pr = (F - fm) @ W + dm
        self.r2 = float(1 - ((Dd - pr) ** 2).sum() / (((Dd - Dd.mean(0)) ** 2).sum() + 1e-12))

    def event_dx(self, xh: np.ndarray, cur: np.ndarray | None, sil: np.ndarray | None, edges) -> np.ndarray:
        """Per-step microstate increment caused by continuous events, given the (decoded) microstate xh."""
        dx = np.zeros_like(xh)
        if cur is not None:
            dx += self.gamma * cur
        if sil is not None:
            dx -= self.A_off[:, sil] @ xh[sil]
        if edges is not None:
            post, pre = edges
            np.add.at(dx, post, -self.A_off[post, pre] * xh[pre])
        return dx


# ------------------------------------------------------------------------------------------------------------ features / basis
def lag_features(xs: np.ndarray, lags: tuple[int, ...]) -> np.ndarray:
    """[x_t, x_{t-l1}, x_{t-l2}, ...] with causal edge padding (the first sample repeats before t = 0)."""
    if not lags:
        return xs
    T = len(xs)
    out = [xs]
    for L in lags:
        idx = np.maximum(0, np.arange(T) - L)
        out.append(xs[idx])
    return np.hstack(out)


def horizon_ladder(H: int) -> list[int]:
    hs, h = [0], 1
    while h <= H:
        hs.append(h)
        h *= 2
    if hs[-1] != H:
        hs.append(H)
    return hs


def predictive_basis(prep: SystemPrep, trajs: list, feats: list[np.ndarray], H: int, r_max: int, n_pc: int = 16,
                     w_y: float = 1.0, lam_grid=(1e-4, 1e-3, 1e-2, 1e-1), stride: int | None = None, val_frac: float = 0.25,
                     seed: int = 0, max_rows: int = 40000):
    """Reduced-rank ridge regression from features f_t (T, p) to future targets [y_{t+h}, PC(x)_{t+h}] for h in a ladder up to H, with
    future-input summaries partialled out. Returns dict(C (p, r_max) encoder basis ordered by predictive importance, sv, err_curve
    (held-out relative error per rank 0..r_max, trajectory-split), lam)."""
    rng = np.random.default_rng(seed)
    hs = horizon_ladder(H)
    X0 = np.concatenate([prep.xs(t.x) for t in trajs])
    Xc = X0 - X0.mean(0)
    _, _, Vt = np.linalg.svd(Xc[:: max(1, len(Xc) // 20000)], full_matrices=False)
    Vpc = Vt[: min(n_pc, Vt.shape[0])].T                       # (N, n_pc)
    stride = stride or max(1, H // 16)
    rows_f, rows_y, rows_u, grp = [], [], [], []
    for ti, (tr, f) in enumerate(zip(trajs, feats)):
        keep = free_mask(tr, drop_current=True)
        run = event_free_after(keep)
        T = len(tr.t)
        xs = prep.xs(tr.x) @ Vpc
        ys = (tr.y - prep.y_mu) / prep.y_sd
        us = (tr.u - prep.u_mu) / prep.u_sd
        cu = np.vstack([np.zeros((1, us.shape[1])), np.cumsum(us, 0)])
        start = int(rng.integers(0, stride))
        for i in range(start, T - H, stride):
            if run[i] < H:
                continue
            tgt, uf = [], [us[i]]
            for h in hs:
                tgt.append(ys[i + h] * w_y)
                tgt.append(xs[i + h] / np.sqrt(max(1, xs.shape[1])) * 1.0)
                if h > 0:
                    uf.append(us[i + h])
                    uf.append((cu[i + h] - cu[i]) / h)
            rows_f.append(f[i]); rows_y.append(np.concatenate(tgt)); rows_u.append(np.concatenate(uf)); grp.append(ti)
    F = np.asarray(rows_f); Yt = np.asarray(rows_y); Uf = np.asarray(rows_u); grp = np.asarray(grp)
    if len(F) > max_rows:
        sel = np.sort(rng.choice(len(F), max_rows, replace=False))
        F, Yt, Uf, grp = F[sel], Yt[sel], Uf[sel], grp[sel]
    # partial out future inputs (Frisch-Waugh) from both sides
    Uc = np.hstack([Uf, np.ones((len(Uf), 1))])
    P = np.linalg.lstsq(Uc, np.hstack([F, Yt]), rcond=None)[0]
    R = np.hstack([F, Yt]) - Uc @ P
    Fr, Yr = R[:, : F.shape[1]], R[:, F.shape[1]:]
    fsd = Fr.std(0) + 1e-9
    Fr = Fr / fsd
    # trajectory split for the held-out curve
    ug = np.unique(grp)
    va = np.isin(grp, rng.permutation(ug)[: max(1, int(round(val_frac * len(ug))))]) if len(ug) > 3 else np.zeros(len(grp), bool)
    tr_m = ~va
    best = None
    for lam in lam_grid:
        B = ridge_solve(Fr[tr_m], Yr[tr_m], lam)
        e = float(((Yr[va] - Fr[va] @ B) ** 2).sum()) if va.any() else 0.0
        if best is None or e < best[0]:
            best = (e, lam)
    lam = best[1]
    B = ridge_solve(Fr[tr_m], Yr[tr_m], lam)
    _, sv, Vt2 = np.linalg.svd(Fr[tr_m] @ B, full_matrices=False)
    r_max = int(min(r_max, len(sv)))
    curve = []
    den = float(((Yr[va] - Yr[tr_m].mean(0)) ** 2).sum()) if va.any() else 1.0
    for r in range(0, r_max + 1):
        Br = B @ Vt2[:r].T @ Vt2[:r] if r > 0 else np.zeros_like(B)
        curve.append(float(((Yr[va] - Fr[va] @ Br) ** 2).sum()) / den if va.any() else float("nan"))
    # refit on all rows at the chosen penalty for the final basis
    B = ridge_solve(Fr, Yr, lam)
    _, sv, Vt2 = np.linalg.svd(Fr @ B, full_matrices=False)
    C = (B @ Vt2[:r_max].T) / fsd[:, None]                    # (p, r_max): z = f @ C (up to a constant offset)
    # scale every coordinate to unit variance on the training features
    Z = F @ C
    zsd = Z.std(0) + 1e-12
    C = C / zsd
    return {"C": C, "sv": sv[:r_max] / (sv[0] + 1e-12), "err_curve": curve, "lam": lam, "hs": hs, "Vpc": Vpc}


# ------------------------------------------------------------------------------------------------------------ validation / dimension
def val_rollout_error(model: StateModel, sid: str, trajs: list, H: int | None = None, n_starts: int = 4, scale=None,
                      return_units: bool = False, clip: float = 2.0):
    """Window NMSE of the readout over rollouts (with each trajectory's own events, times shifted) from n_starts start times in
    [T/8, T/2], horizon H (default T/4). Returns (mean, standard error over trajectories)."""
    from ..evaluate import shift_events
    errs = []
    for tr in trajs:
        T = len(tr.t)
        Hh = H or T // 4
        starts = np.linspace(T // 8, T // 2, n_starts).astype(int)
        e = []
        for i0 in starts:
            if i0 + Hh >= T:
                continue
            z0 = model.encode(sid, tr.x[: i0 + 1], tr.u[: i0 + 1], tr.dt)
            ev = shift_events(tr.events(), float(tr.t[i0]), Hh * tr.dt)
            out = model.rollout(sid, z0, tr.u[i0: i0 + Hh + 1], ev, tr.dt)
            yp = np.asarray(out["y"], float)
            if not np.all(np.isfinite(yp)):
                e.append(clip)
                continue
            # robust: one rollout's NMSE is capped (a rollout worse than `clip` x the readout variance has simply failed), so rare
            # extreme excursions of single trajectories cannot dominate model selection
            e.append(min(clip, float(np.mean((yp[1:] - tr.y[i0 + 1: i0 + Hh + 1]) ** 2 / scale))))
        if e:
            errs.append(float(np.mean(e)))
    errs = np.asarray(errs)
    if return_units:
        return errs
    if len(errs) == 0:
        return float("inf"), float("inf")
    return float(errs.mean()), float(errs.std(ddof=1) / np.sqrt(len(errs))) if len(errs) > 1 else float(errs.mean())


def select_dimension(ks: list[int], errs: list[float], ses: list[float], rel_tol: float = 0.05) -> dict:
    """Generic dimension rule. tol = max(SE at the best k, rel_tol x best error); k = the smallest k with err <= best + tol;
    the plausible range brackets it with the looser (2 tol) and tighter (tol / 2) versions of the same rule."""
    errs = np.asarray(errs, float)
    ses = np.asarray(ses, float)
    ok = np.isfinite(errs)
    if not ok.any():
        return {"k": ks[-1], "range": [ks[0], ks[-1]], "tol": float("nan"), "best_k": ks[-1]}
    b = int(np.nanargmin(np.where(ok, errs, np.inf)))
    tol = max(float(ses[b]) if np.isfinite(ses[b]) else 0.0, rel_tol * float(errs[b]))

    def first(t):
        for k, e in zip(ks, errs):
            if np.isfinite(e) and e <= errs[b] + t:
                return int(k)
        return int(ks[b])
    return {"k": first(tol), "range": [first(2 * tol), first(0.5 * tol)], "tol": tol, "best_k": int(ks[b]), "best_err": float(errs[b])}


# ------------------------------------------------------------------------------------------------------------ base model
class KSModel(StateModel):
    """Base class. A subclass stores per-system data in self.sys[sid] (a dict with at least 'prep', 'micro', 'basis' (p, r) for the
    current-sample block, 'silence_mode') and implements:
        _encode(sid, x_hist, u_hist) -> z
        _step(sid, z, u) -> z_next                (free dynamics, one data step)
        _apply_dq(sid, z, dq) -> z'               (microstate increment dq in basis coordinates q = xs @ basis)
        _decode_x(sid, z) -> x (N,)               (decoded microstate, raw units)
        _readout(sid, Z (n, k), U (n, n_u)) -> Y
    Events: kick -> dq through the encoder; current / silence / edge_remove -> per-step microstate increments from the fitted
    MicroModel, mapped through the encoder. silence_mode 'clamp' instead decodes x, sets the silenced units to rest and re-encodes."""

    event_kinds = ("kick", "current", "silence", "edge_remove")

    def __init__(self):
        self.sys: dict[str, dict] = {}
        self.k: dict[str, int] = {}
        self._info: dict = {}

    # --- API
    def _stride(self, sid, dt) -> int:
        """Data samples per model step (models fitted on decimated data run on the coarse grid)."""
        return max(1, int(round(self.sys[sid]["prep"].dt / float(dt)))) if dt else 1

    def encode(self, sid, x_hist, u_hist, dt):
        x_hist, u_hist = np.asarray(x_hist, np.float64), np.asarray(u_hist, np.float64)
        s = self._stride(sid, dt)
        if s > 1:                                    # history on the model grid, ending at the last (current) sample
            x_hist, u_hist = x_hist[::-1][::s][::-1], u_hist[::-1][::s][::-1]
        return np.asarray(self._encode(sid, x_hist, u_hist), float)

    def supports(self, sid, kind):
        return kind in self.event_kinds

    def readout(self, sid, z, u):
        z = np.asarray(z, float)
        u = np.asarray(u, float)
        shp = z.shape[:-1]
        Y = self._readout(sid, z.reshape(-1, z.shape[-1]), u.reshape(-1, u.shape[-1]))
        return Y.reshape(*shp, -1)

    def dx_to_dq(self, sid, dx):
        S = self.sys[sid]
        return (dx / S["prep"].sd) @ S["basis"]

    def rollout(self, sid, z0, u_future, events, dt):
        u_future = np.asarray(u_future, np.float64)
        s = self._stride(sid, dt)
        if s == 1:
            return self._rollout_grid(sid, z0, u_future, events, dt)
        # coarse model grid: run every s-th input sample, interpolate the latent back to the data grid, read out at data resolution
        n = len(u_future) - 1
        nc = int(np.ceil(n / s))
        idx = np.minimum(np.arange(nc + 1) * s, n)
        out = self._rollout_grid(sid, z0, u_future[idx], events, dt * s)
        tf = np.arange(n + 1)
        tc = np.arange(nc + 1) * s
        Zc = out["z"]
        Z = np.stack([np.interp(tf, tc, Zc[:, i]) for i in range(Zc.shape[1])], 1)
        return {"z": Z, "y": self._readout(sid, Z, u_future)}

    def _rollout_grid(self, sid, z0, u_future, events, dt):
        S = self.sys[sid]
        prep, micro = S["prep"], S["micro"]
        u_future = np.asarray(u_future, np.float64)
        n = len(u_future) - 1
        g = compile_events(events, n, dt, prep.col, prep.N) if events else None
        z = np.asarray(z0, np.float64).copy()
        Z = np.empty((n + 1, len(z)))
        Z[0] = z
        lo, hi = S.get("z_lo"), S.get("z_hi")
        mode = S.get("silence_mode", "drive")
        gain = S.get("gain") or {}
        gk, gc, gs, ge = (gain.get(x, 1.0) for x in ("kick", "current", "silence", "edge"))
        for j in range(n):
            if g is not None and j in g.kick:
                z = self._apply_dq(sid, z, gk * self.dx_to_dq(sid, g.kick[j]))
            cont = g is not None and g.any_cont[j]
            if cont:
                xh = self._decode_x(sid, z)
                dx = np.zeros_like(xh)
                if g.cur[j].any():
                    dx += gc * micro.event_dx(xh, g.cur[j], None, None)
                if mode == "drive" and g.sil[j] is not None:
                    dx += gs * micro.event_dx(xh, None, g.sil[j], None)
                if g.edges[j] is not None:
                    dx += ge * micro.event_dx(xh, None, None, g.edges[j])
            z = self._step(sid, z, u_future[j])
            if cont:
                if dx.any():
                    z = self._apply_dq(sid, z, self.dx_to_dq(sid, dx))
                if mode == "clamp" and g.sil[j] is not None:
                    xh = self._decode_x(sid, z)
                    d = np.zeros_like(xh)
                    d[g.sil[j]] = prep.rest[g.sil[j]] - xh[g.sil[j]]
                    z = self._apply_dq(sid, z, gs * self.dx_to_dq(sid, d))
            if lo is not None:
                z = np.clip(z, lo, hi)
            if not np.all(np.isfinite(z)):
                z = np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)
            Z[j + 1] = z
        return {"z": Z, "y": self._readout(sid, Z, u_future[: n + 1])}

    def info(self):
        return dict(self._info)

    # --- helpers for subclasses
    GAIN_GRID = (0.0, 0.25, 0.5, 1.0)

    def choose_silence_mode(self, sid, trajs, scale):
        return self.calibrate_events(sid, trajs, scale)

    def calibrate_events(self, sid, trajs, scale):
        """Event calibration from TRAINING event trajectories (generic, per event kind): a gain g in GAIN_GRID on the latent effect of
        kicks, injected currents and silencing, and the silencing mechanism ('drive' = removal of the unit's outgoing couplings of
        the microscopic estimate, 'clamp' = decode, set to rest, re-encode). Criterion: PAIRED post-event rollout errors (each
        rollout NMSE capped at 2) on the training trajectories carrying that event kind only; the model error without the event
        is common to all candidates, so the comparison isolates the predicted effect. Edge removal (never in training) uses the
        drive gain of silencing (same structural mechanism). Without training events of a kind its gain stays 1."""
        S = self.sys[sid]
        S["gain"] = {"kick": 1.0, "current": 1.0, "silence": 1.0, "edge": 1.0}
        S["silence_mode"] = "drive"
        report = {}
        by_kind = {k: [t for t in trajs if t.events() and {e["kind"] for e in t.events()} == {k}] for k in ("kick", "current", "silence")}
        for kind in ("kick", "current"):
            if not by_kind[kind]:
                continue
            res = {}
            for gv in self.GAIN_GRID:
                S["gain"][kind] = gv
                res[gv] = event_effect_units(self, sid, by_kind[kind], scale).mean()
            S["gain"][kind] = min(res, key=res.get)
            report[kind] = res
        if by_kind["silence"]:
            res = {}
            for mode in ("drive", "clamp"):
                S["silence_mode"] = mode
                for gv in self.GAIN_GRID:
                    if gv == 0.0 and mode == "clamp":
                        continue
                    S["gain"]["silence"] = gv
                    res[(mode, gv)] = event_effect_units(self, sid, by_kind["silence"], scale).mean()
            mode, gv = min(res, key=res.get)
            if gv == 0.0:
                mode = "drive"
            S["silence_mode"], S["gain"]["silence"] = mode, gv
            drive = {g_: v for (m_, g_), v in res.items() if m_ == "drive"}
            S["gain"]["edge"] = min(drive, key=drive.get)
            report["silence"] = {f"{m_}:{g_}": v for (m_, g_), v in res.items()}
        S["gain"]["edge"] *= getattr(S["micro"], "reliability", 1.0)
        report["chosen"] = {"mode": S["silence_mode"], **S["gain"]}
        return report


def event_effect_units(model, sid, trajs, scale, H=None, clip=2.0) -> np.ndarray:
    """Per-trajectory post-event rollout NMSE (capped at clip), rollouts started at the pre-event sample, horizon T/4."""
    from ..evaluate import first_event_time, shift_events
    errs = []
    for tr in trajs:
        te = first_event_time(tr)
        if te is None:
            continue
        T = len(tr.t)
        Hh = H or T // 4
        i0 = int(round(te / tr.dt))
        Hh = min(Hh, T - 1 - i0)
        if Hh < 2:
            continue
        z0 = model.encode(sid, tr.x[: i0 + 1], tr.u[: i0 + 1], tr.dt)
        out = model.rollout(sid, z0, tr.u[i0: i0 + Hh + 1], shift_events(tr.events(), float(tr.t[i0]), Hh * tr.dt), tr.dt)
        yp = np.asarray(out["y"], float)
        e = float(np.mean((yp[1:] - tr.y[i0 + 1: i0 + Hh + 1]) ** 2 / scale)) if np.all(np.isfinite(yp)) else clip
        errs.append(min(clip, e))
    return np.asarray(errs) if errs else np.zeros(1)


def event_effect_error(model: KSModel, sid: str, trajs: list, scale, H: int | None = None) -> float:
    """Post-event window NMSE of rollouts started at the first event (encoded from the pre-event sample), horizon H (default T/4)."""
    from ..evaluate import first_event_time, shift_events
    errs = []
    for tr in trajs:
        te = first_event_time(tr)
        if te is None:
            continue
        T = len(tr.t)
        Hh = H or T // 4
        i0 = int(round(te / tr.dt))
        if i0 + Hh >= T:
            Hh = T - 1 - i0
        if Hh < 2:
            continue
        z0 = model.encode(sid, tr.x[: i0 + 1], tr.u[: i0 + 1], tr.dt)
        out = model.rollout(sid, z0, tr.u[i0: i0 + Hh + 1], shift_events(tr.events(), float(tr.t[i0]), Hh * tr.dt), tr.dt)
        yp = np.asarray(out["y"], float)
        errs.append(float(np.mean((yp[1:] - tr.y[i0 + 1: i0 + Hh + 1]) ** 2 / scale)) if np.all(np.isfinite(yp)) else 1e3)
    return float(np.mean(errs)) if errs else float("nan")


class Timer:
    def __init__(self):
        self.t0 = time.process_time()
        self.w0 = time.time()

    def cpu(self):
        return time.process_time() - self.t0

    def wall(self):
        return time.time() - self.w0


# ------------------------------------------------------------------------------------------------------------ polynomial library
class PolyLibrary:
    """Monomials of degree <= deg in v = [1, z_1..z_k, u_1..u_m] where every input appears at most once (control-affine /
    bilinear in u). Evaluated by index products (fast for single states and batches)."""

    def __init__(self, k: int, n_u: int, deg: int):
        from itertools import combinations_with_replacement
        self.k, self.n_u, self.deg = k, n_u, deg
        nv = 1 + k + n_u
        terms = []
        for c in combinations_with_replacement(range(nv), deg):
            if sum(1 for i in c if i > k) > 1:
                continue
            terms.append(c)
        # sort by degree (number of non-constant factors), constant first
        terms = sorted(set(terms), key=lambda c: (sum(1 for i in c if i > 0), c))
        self.idx = np.array(terms, int)                     # (n_terms, deg)
        self.n_terms = len(terms)
        self.degree_of = np.array([sum(1 for i in c if i > 0) for c in terms])
        self.names = ["*".join(("1" if i == 0 else (f"z{i - 1}" if i <= k else f"u{i - 1 - k}")) for i in c if i > 0) or "1"
                      for c in terms]

    def __call__(self, Z: np.ndarray, U: np.ndarray) -> np.ndarray:
        Z = np.atleast_2d(Z)
        U = np.atleast_2d(U)
        V = np.hstack([np.ones((len(Z), 1)), Z, U])
        out = V[:, self.idx[:, 0]]
        for d in range(1, self.deg):
            out = out * V[:, self.idx[:, d]]
        return out


def stlsq(Th: np.ndarray, Y: np.ndarray, thr: float, ridge: float = 1e-5, n_iter: int = 8, always: np.ndarray | None = None):
    """Sequentially thresholded ridge least squares. Th (n, p) with standardised non-constant columns; Y (n, q) standardised.
    Coefficients with |xi| < thr are removed (columns flagged in `always` are never removed). Returns Xi (p, q)."""
    p, q = Th.shape[1], Y.shape[1]
    G = Th.T @ Th / len(Th)
    b = Th.T @ Y / len(Th)
    Xi = np.linalg.solve(G + ridge * np.eye(p), b)
    always = np.zeros(p, bool) if always is None else always
    for _ in range(n_iter):
        active = (np.abs(Xi) >= thr) | always[:, None]
        changed = False
        for j in range(q):
            a = active[:, j]
            new = np.zeros(p)
            if a.any():
                new[a] = np.linalg.solve(G[np.ix_(a, a)] + ridge * np.eye(int(a.sum())), b[a, j])
            if not np.allclose(new, Xi[:, j]):
                changed = True
            Xi[:, j] = new
        if not changed:
            break
    return Xi


# ------------------------------------------------------------------------------------------------------------ validation folds
def draw_folds(trajs: list, n_folds: int = 2, seed: int = 0, max_val: int = 16, by_draw: bool = True) -> list[tuple[list, list]]:
    """Cross-validation folds grouped by PARAMETER DRAW (protocol params_seed): each fold fits on the trajectories of some draws and
    validates on the others, which mimics generalisation to unseen draws. Falls back to trajectory folds when there are fewer
    than two draws. Validation sets are subsampled (stratified by family) to max_val trajectories."""
    rng = np.random.default_rng(seed)
    draws = sorted({int(t.protocol.get("params_seed", 0)) for t in trajs})
    if by_draw and len(draws) >= 2:
        perm = [draws[i] for i in rng.permutation(len(draws))]
        groups = [set(perm[i::n_folds]) for i in range(n_folds)]
        key = lambda t: int(t.protocol.get("params_seed", 0))  # noqa: E731
    else:
        ids = list(range(len(trajs)))
        perm = [ids[i] for i in rng.permutation(len(ids))]
        groups = [set(perm[i::n_folds]) for i in range(n_folds)]
        order = {id(t): i for i, t in enumerate(trajs)}
        key = lambda t: order[id(t)]  # noqa: E731
    folds = []
    for g in groups:
        va = [t for t in trajs if key(t) in g]
        fi = [t for t in trajs if key(t) not in g]
        if not va or not fi:
            continue
        if len(va) > max_val:
            fams = sorted({t.family for t in va})
            byf = {f: [t for t in va if t.family == f] for f in fams}
            pick = []
            i = 0
            while len(pick) < max_val:
                for f in fams:
                    if i < len(byf[f]) and len(pick) < max_val:
                        pick.append(byf[f][i])
                i += 1
            va = pick
        folds.append((fi, va))
    return folds


LOG_FLOOR = 0.01


def log_units(e) -> np.ndarray:
    """Selection statistic per validation unit: log(NMSE + 0.01). Comparisons are relative (a 10 % improvement counts the same on
    every trajectory) and robust to the few intrinsically unpredictable trajectories."""
    return np.log(np.asarray(e, float) + LOG_FLOOR)


def table_from_units(units: dict, complexity, rel_tol: float = 0.05) -> dict:
    """units: {(k, *config): [per-unit validation NMSE]}. For every k return the SIMPLEST configuration (smallest complexity(config)
    tuple) whose mean log-error is within log(1 + rel_tol) of the best configuration at that k (parsimony: no delay features,
    lower polynomial degree, sparser models are preferred unless measurably worse)."""
    by_k: dict = {}
    for key, e in units.items():
        e = np.asarray(e, float)
        le = log_units(e)
        by_k.setdefault(key[0], []).append((float(le.mean()), float(e.mean()), key[1:]))
    table = {}
    for k, rows in by_k.items():
        best = min(r[0] for r in rows)
        ok = [r for r in rows if r[0] <= best + np.log1p(rel_tol) + 1e-12]
        lm, mu, conf = min(ok, key=lambda r: (complexity(r[2]), r[0]))
        u = np.asarray(units[(k, *conf)], float)
        table[k] = {"k": k, "val_nmse": mu, "val_log": lm, "se": float(u.std(ddof=1) / np.sqrt(len(u))) if len(u) > 1 else mu,
                    "best_log_at_k": best, "conf": conf, "units": u}
    return table


def select_from_table(table: dict, rel_tol: float = 0.05) -> dict:
    ks = sorted(table)
    return select_dimension_paired(ks, [table[k]["units"] for k in ks], rel_tol)


def select_dimension_paired(ks: list[int], units: list[np.ndarray], rel_tol: float = 0.05) -> dict:
    """Generic dimension rule on PAIRED validation units (every candidate k is scored on the same units), statistic log(NMSE + 0.01).
    d_k = per-unit excess of k over the best k; k = the smallest candidate with mean(d_k) <= tol_k, tol_k = max(SE(d_k),
    log(1 + rel_tol)) (not measurably worse than the best, within a relative tolerance). The plausible range brackets it with
    2 tol_k (looser) and tol_k / 2 (tighter)."""
    U = [log_units(u) for u in units]
    means = np.array([u.mean() if len(u) else np.inf for u in U])
    b = int(np.argmin(means))
    ub = U[b]

    def first(mult):
        for k, u in zip(ks, U):
            if len(u) != len(ub):
                continue
            d = u - ub
            se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else 0.0
            if d.mean() <= mult * max(se, np.log1p(rel_tol)):
                return int(k)
        return int(ks[b])
    return {"k": first(1.0), "range": [first(2.0), first(0.5)], "tol": float(np.log1p(rel_tol)), "best_k": int(ks[b]),
            "best_err": float(np.exp(means[b]) - LOG_FLOOR)}



def cv_folds(trajs: list, n_folds: int, seed: int, max_val: int) -> list[tuple[str, list, list]]:
    """Both fold kinds used by the two-criterion selection: ('traj', ...) random trajectory folds (within the training
    distribution: the state dimension is visible there) and ('draw', ...) parameter-draw folds (generalisation to unseen draws)."""
    out = [("traj", a, b) for a, b in draw_folds(trajs, n_folds, seed, max_val, by_draw=False)]
    out += [("draw", a, b) for a, b in draw_folds(trajs, n_folds, seed + 1, max_val, by_draw=True)]
    return out


def two_stage_select(units_traj: dict, units_draw: dict, complexity, rel_tol: float = 0.05) -> tuple[dict, dict, dict]:
    """k from the trajectory-fold units (best configuration per k, paired dimension rule); then the configuration at that k from
    the draw-fold units (simplest within rel_tol of the best). Returns (dimension selection, chosen row, trajectory table)."""
    tab_t = table_from_units(units_traj, lambda c: (0,), 0.0)            # best configuration at each k (within distribution)
    sel = select_from_table(tab_t, rel_tol)
    k = sel["k"]
    sub = {key: v for key, v in units_draw.items() if key[0] == k}
    row = table_from_units(sub, complexity, rel_tol)[k] if sub else dict(tab_t[k])
    row["val_nmse_traj"] = tab_t[k]["val_nmse"]
    return sel, row, tab_t


# ------------------------------------------------------------------------------------------------------------ decimation
def model_stride(T: int, target: int = 400) -> int:
    """Samples per model step: finely sampled data (e.g. 1 ms, 2001 samples) is modelled on a grid of about `target` steps per
    trajectory; 1 for the synthetic data (401 samples)."""
    return max(1, int(round(T / target)))


def decimate(trajs: list) -> list:
    """Every s-th sample of each trajectory (s = model_stride of the median length; events keep their times in seconds)."""
    import dataclasses
    if not trajs:
        return trajs
    s = model_stride(int(np.median([len(t.t) for t in trajs])))
    if s == 1:
        return list(trajs)
    return [dataclasses.replace(t, t=t.t[::s], x=t.x[::s], u=t.u[::s], y=t.y[::s]) for t in trajs]


def stabilise(A: np.ndarray, rho: float = 1.0) -> np.ndarray:
    """Project a discrete-time operator onto spectral radius <= rho (eigenvalues scaled to the circle; real form kept). Training
    trajectories are bounded, so growing modes of a least-squares / Galerkin operator are estimation artefacts."""
    lam, V = np.linalg.eig(A)
    mag = np.abs(lam)
    if mag.max() <= rho:
        return A
    lam2 = np.where(mag > rho, lam / mag * rho, lam)
    try:
        return np.real(V @ np.diag(lam2) @ np.linalg.inv(V))
    except np.linalg.LinAlgError:
        return A / (mag.max() / rho)
