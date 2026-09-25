"""Evaluation metrics for state discovery (benchmarks/state_discovery_v1/PROTOCOL.md, benchmark version 2; goal4 sections 7, 9-12,
42, 49-52).

Every family is computed and reported SEPARATELY; nothing is collapsed into one score. Normalisation constants come from PUBLIC
training data (never from test statistics): the readout variance (robust to diverged training trajectories), the PCA basis of x and
the whitening of latent / readout / PC distances in E. The resampling unit for confidence intervals is the trajectory (a
trajectory's start times and pairs are resampled together); in E it is the pool trajectory within its parameter draw; across systems
the unit is the system.

Version 2 (early reviews E and H, research/phase3/reviews/): window errors are capped at NMSE_CAP (a non-finite prediction counts as
the cap); D is averaged over repeated cross-fits and has a trajectory-cluster bootstrap CI; D's readout targets keep the public
readout scale; E uses an affine-invariant (whitened) distance, a cluster bootstrap CI and a testability rule; the shortcut and
rollout checks use the corrected conventions described at each function.

Families implemented here (model-level, one system):
    A  predictive sufficiency     window NMSE of predicted readout after encoding at t0, per horizon, on non-intervention trajectories
    B  readout sufficiency        NMSE of g(phi(x_{<=t})) against y_t
    C  interventional fidelity    post-intervention window NMSE and the normalised EFFECT error against counterfactual twins
    D  Markov closure             cross-fitted gain from adding discarded microstate (and history) to (z_t, u_t) when predicting
                                  z_{t+d} and y_{t+h}
    E  microstate equivalence     future readout divergence of latent-matched states, against random / PCA / output-matched pairs
Families F-L (dimension, reproducibility, robustness, cross-mechanism, cross-connectome, synthetic truth, abstention) are assembled by
the harness from these and from brainir_state.evaluate_cross / evaluate_synthetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .api import StateModel
from .data import Trajectory


@dataclass(frozen=True)
class EvalConfig:
    """Time constants of the evaluation (seconds). The defaults are the REAL-circuit configuration (dt 1 ms, 2 s trajectories);
    `brainir_state.harness.SYNTH_CFG` is the pre-registered configuration of the synthetic suites (dt 10 ms, 4 s trajectories)."""
    horizons_s: tuple[float, ...] = (0.01, 0.05, 0.1, 0.25, 0.5)
    start_times_s: tuple[float, ...] = (0.3, 0.6, 0.9, 1.2)
    primary_horizon_s: float = 0.25
    closure_deltas_s: tuple[float, ...] = (0.01, 0.05)
    closure_task_horizon_s: float = 0.1
    closure_history_lags_s: tuple[float, float] = (0.01, 0.02)
    closure_points_per_traj: int = 20
    closure_pcs: int = 10
    closure_start_s: float = 0.25
    closure_repeats: int = 5
    c_windows_s: tuple[float, ...] = (0.1, 0.25, 0.5)
    primary_c_window_s: float = 0.25
    rollout_a_s: float = 0.05
    rollout_b_s: float = 0.2
    micro_future_s: float = 0.25
    ridge: float = 1e-3
    n_boot: int = 2000
    micro_match_quantile: float = 0.02
    micro_resolution_max: float = 0.2
    micro_floor_factor: float = 2.0
    whiten_eig_floor: float = 1e-8
    seed: int = 0


NMSE_CAP = 10.0            # a window NMSE above the cap (or non-finite: no usable prediction) counts as the cap
BLOWUP_FACTOR = 100.0      # a training trajectory whose max |y| exceeds this multiple of the median trajectory's is a blow-up


# ------------------------------------------------------------------------------------------------------------ helpers
def strip_units(res):
    """Copy of a result without the per-unit payloads ("_units") that paired comparisons use."""
    if isinstance(res, dict):
        return {k: strip_units(v) for k, v in res.items() if k != "_units"}
    if isinstance(res, list):
        return [strip_units(v) for v in res]
    return res


def idx(t: float, dt: float) -> int:
    return int(round(t / dt))


def encode_at(model: StateModel, sid: str, tr: Trajectory, i: int) -> np.ndarray:
    """z at sample i from the history x[0..i], u[0..i] (inclusive; never later samples). Only the evaluator's reference CONTROLS
    (the full-state ceiling, the readout-history shortcut) are given the readout history; method models never are."""
    if getattr(model, "uses_readout", False):
        return np.asarray(model.encode_with_readout(sid, tr.x[: i + 1], tr.u[: i + 1], tr.y[: i + 1], tr.dt), dtype=np.float64)
    return np.asarray(model.encode(sid, tr.x[: i + 1], tr.u[: i + 1], tr.dt), dtype=np.float64)


def shift_events(events: list[dict], t0: float, t_max: float) -> list[dict]:
    """Events relative to t0, keeping only what acts in [t0, t0 + t_max]."""
    out = []
    for e in events:
        e2 = dict(e)
        if "t" in e2:
            if not (t0 - 1e-9 <= e2["t"] <= t0 + t_max):
                continue
            e2["t"] = round(e2["t"] - t0, 9)
        else:
            if e2.get("t1") is not None and e2["t1"] <= t0:
                continue
            if e2["t0"] > t0 + t_max:
                continue
            e2["t0"] = round(max(0.0, e2["t0"] - t0), 9)
            if e2.get("t1") is not None:
                e2["t1"] = round(e2["t1"] - t0, 9)
        out.append(e2)
    return out


def first_event_time(tr: Trajectory) -> float | None:
    ts = [e.get("t", e.get("t0")) for e in tr.events()]
    return min(ts) if ts else None


def boot_ratio(num: np.ndarray, den: np.ndarray, n_boot: int, seed: int) -> tuple[float, list[float]]:
    """sum(num) / sum(den) with a bootstrap CI over units (rows)."""
    num, den = np.asarray(num, float), np.asarray(den, float)
    if len(num) == 0 or den.sum() <= 0:
        return float("nan"), [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(n_boot):
        s = rng.integers(0, len(num), len(num))
        d = den[s].sum()
        if d > 0:
            b.append(num[s].sum() / d)
    return float(num.sum() / den.sum()), [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def boot_mean(v: np.ndarray, n_boot: int, seed: int) -> tuple[float, list[float]]:
    """Mean with a bootstrap CI over units. Callers pass finite values (window errors are capped, see NMSE_CAP); a non-finite value
    is left out here, and callers report how many values entered."""
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return float("nan"), [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    b = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(n_boot)]
    return float(v.mean()), [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def blowup_mask(trajs: list[Trajectory], factor: float = BLOWUP_FACTOR) -> np.ndarray:
    """True for trajectories whose max |y| or max |x| exceeds `factor` times the median over the trajectories (finite blow-ups of the
    simulator; they are kept as data but excluded from normalisers and reference-control fits)."""
    if not trajs:
        return np.zeros(0, bool)
    my = np.array([float(np.nanmax(np.abs(t.y))) if t.y.size else 0.0 for t in trajs])
    mx = np.array([float(np.nanmax(np.abs(t.x))) if t.x.size else 0.0 for t in trajs])
    bad = ~(np.isfinite(my) & np.isfinite(mx))
    ref_y, ref_x = np.median(my[~bad]) if (~bad).any() else 0.0, np.median(mx[~bad]) if (~bad).any() else 0.0
    return bad | (my > factor * max(ref_y, 1e-12)) | (mx > factor * max(ref_x, 1e-12))


def readout_scale(train: list[Trajectory]) -> np.ndarray:
    """Per-readout-dimension variance from PUBLIC training data (the fixed NMSE normaliser), over the trajectories that are not
    blow-ups (`blowup_mask`); the floor avoids silent dimensions."""
    keep = [t for t, b in zip(train, blowup_mask(train)) if not b] or list(train)
    Y = np.concatenate([t.y for t in keep], axis=0).astype(np.float64)
    var = Y.var(axis=0)
    return np.maximum(var, max(1e-6, 1e-3 * float(var.max()) if var.size else 1e-6))


def _nmse(pred: np.ndarray, true: np.ndarray, scale: np.ndarray) -> float:
    return float(np.mean((pred - true) ** 2 / scale))


def _capped(v: float) -> tuple[float, bool, bool]:
    """(capped value, was non-finite, was capped)."""
    if not np.isfinite(v):
        return NMSE_CAP, True, True
    return (NMSE_CAP, False, True) if v > NMSE_CAP else (float(v), False, False)


# ------------------------------------------------------------------------------------------------------------ A and B
def eval_predictive(model: StateModel, sid: str, trajs: list[Trajectory], scale: np.ndarray, cfg: EvalConfig = EvalConfig()) -> dict:
    """A: window NMSE of rollouts (no events) from several start times; B: instantaneous readout NMSE. Every window error is capped
    at NMSE_CAP, and a non-finite prediction counts as the cap (it is never dropped); the counts are reported."""
    per_h = {h: [] for h in cfg.horizons_s}
    units = {h: {} for h in cfg.horizons_s}
    n_nonfinite = {h: 0 for h in cfg.horizons_s}
    n_capped = {h: 0 for h in cfg.horizons_s}
    b_err, b_bad = [], 0
    for tr in trajs:
        dt = tr.dt
        rows = {h: [] for h in cfg.horizons_s}
        for t0 in cfg.start_times_s:
            i0 = idx(t0, dt)
            hmax = max(h for h in cfg.horizons_s if i0 + idx(h, dt) < len(tr.t)) if any(i0 + idx(h, dt) < len(tr.t) for h in cfg.horizons_s) else None
            if hmax is None:
                continue
            z0 = encode_at(model, sid, tr, i0)
            n = idx(hmax, dt)
            out = model.rollout(sid, z0, tr.u[i0: i0 + n + 1], shift_events(tr.events(), tr.t[i0], hmax), dt)
            yp = np.asarray(out["y"], float)
            for h in cfg.horizons_s:
                m = idx(h, dt)
                if m <= n:
                    v, bad, cap = _capped(_nmse(yp[1: m + 1], tr.y[i0 + 1: i0 + m + 1], scale) if len(yp) > m else float("nan"))
                    rows[h].append(v)
                    n_nonfinite[h] += bad
                    n_capped[h] += cap
            v, bad, _ = _capped(_nmse(np.asarray(model.readout(sid, z0[None, :], tr.u[i0][None, :]), float), tr.y[i0][None, :], scale))
            b_err.append(v)
            b_bad += bad
        for h in cfg.horizons_s:
            if rows[h]:
                per_h[h].append(float(np.mean(rows[h])))
                units[h][tr.key] = per_h[h][-1]
    res = {"n_trajectories": len(trajs), "nmse_cap": NMSE_CAP}
    for h, v in per_h.items():
        m, ci = boot_mean(np.array(v), cfg.n_boot, cfg.seed)
        res[f"A_nmse_h{int(round(h * 1000))}ms"] = {"mean": m, "ci95": ci, "n": len(v), "n_windows_nonfinite": n_nonfinite[h],
                                                   "n_windows_capped": n_capped[h]}
    m, ci = boot_mean(np.array(b_err), cfg.n_boot, cfg.seed)
    res["B_readout_nmse"] = {"mean": m, "ci95": ci, "n": len(b_err), "n_nonfinite": b_bad}
    # per-unit values (unit = trajectory) for paired comparisons between models on the same data; strip before reporting
    res["_units"] = {f"A_nmse_h{int(round(h * 1000))}ms": u for h, u in units.items()}
    return res


# ------------------------------------------------------------------------------------------------------------ C
def eval_intervention(model: StateModel, sid: str, pairs: list[tuple[Trajectory, Trajectory]], scale: np.ndarray,
                      cfg: EvalConfig = EvalConfig(), windows_s: tuple[float, ...] | None = None) -> dict:
    """C: per intervention trajectory with its counterfactual twin (same seed / state / inputs, no events): encode at the first event
    time (the pre-intervention sample), roll out with and without the events, and compare (i) the post-intervention trajectory and
    (ii) the predicted EFFECT (with - without) to the true effect (intervened - twin). Effect error = sum ||d_pred - d_true||^2 /
    sum ||d_true||^2 (1 = predicting no effect). Unsupported event kinds count as abstentions, reported apart. A non-finite prediction
    makes the ratio non-finite (a failure); pairs whose event is too late for any window are counted as skipped. n_eff = the effective
    number of pairs carrying the denominator, (sum d)^2 / sum d^2."""
    windows_s = tuple(windows_s or cfg.c_windows_s)
    by_w = {w: {"traj_nmse": [], "eff_num": [], "eff_den": []} for w in windows_s}
    units = {w: {} for w in windows_s}
    abstained, n, skipped = 0, 0, 0
    for tr, tw in pairs:
        t_int = first_event_time(tr)
        if t_int is None:
            continue
        n += 1
        kinds = {e["kind"] for e in tr.events()}
        if not all(model.supports(sid, k) for k in kinds):
            abstained += 1
            continue
        dt = tr.dt
        i0 = idx(t_int, dt)
        wmax = max((w for w in windows_s if i0 + idx(w, dt) < len(tr.t)), default=None)
        if wmax is None:
            skipped += 1
            continue
        m_max = idx(wmax, dt)
        z0 = encode_at(model, sid, tr, i0)
        ev = shift_events(tr.events(), tr.t[i0], wmax)
        yi = np.asarray(model.rollout(sid, z0, tr.u[i0: i0 + m_max + 1], ev, dt)["y"], float)
        yc = np.asarray(model.rollout(sid, z0, tr.u[i0: i0 + m_max + 1], [], dt)["y"], float)
        for w in windows_s:
            m = idx(w, dt)
            if m > m_max:
                continue
            d_pred = (yi[1: m + 1] - yc[1: m + 1]) / np.sqrt(scale)
            d_true = (tr.y[i0 + 1: i0 + m + 1] - tw.y[i0 + 1: i0 + m + 1]) / np.sqrt(scale)
            by_w[w]["traj_nmse"].append(_capped(_nmse(yi[1: m + 1], tr.y[i0 + 1: i0 + m + 1], scale))[0])
            by_w[w]["eff_num"].append(float(((d_pred - d_true) ** 2).sum()))
            by_w[w]["eff_den"].append(float((d_true ** 2).sum()))
            units[w][tr.key] = (by_w[w]["eff_num"][-1], by_w[w]["eff_den"][-1], by_w[w]["traj_nmse"][-1], tr.family)
    res = {"n_pairs": n, "n_abstained_unsupported": abstained, "n_skipped_late": skipped}
    for w, d in by_w.items():
        wm = int(round(w * 1000))
        m, ci = boot_mean(np.array(d["traj_nmse"]), cfg.n_boot, cfg.seed)
        res[f"C_post_nmse_w{wm}ms"] = {"mean": m, "ci95": ci, "n": len(d["traj_nmse"])}
        num, den = np.array(d["eff_num"], float), np.array(d["eff_den"], float)
        r, rci = boot_ratio(num, den, cfg.n_boot, cfg.seed)
        n_eff = float(den.sum() ** 2 / (den ** 2).sum()) if len(den) and (den ** 2).sum() > 0 else 0.0
        res[f"C_effect_error_w{wm}ms"] = {"ratio": r, "ci95": rci, "n": len(num), "n_nonfinite": int((~np.isfinite(num)).sum()),
                                          "n_eff": n_eff, "max_share": float(den.max() / den.sum()) if len(den) and den.sum() > 0 else None}
    # per-unit (effect numerator, effect denominator, post NMSE) keyed by trajectory, for paired comparisons; strip before reporting
    res["_units"] = {f"C_w{int(round(w * 1000))}ms": u for w, u in units.items()}
    return res


# ------------------------------------------------------------------------------------------------------------ D
def _ridge_fit_predict(Xtr, Ytr, Xte, lam, keep_scale: np.ndarray | None = None):
    """Ridge with standardised features; columns flagged in keep_scale are centred but NOT rescaled (they are pre-scaled)."""
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-9
    if keep_scale is not None:
        sd = np.where(keep_scale, 1.0, sd)
    A = (Xtr - mu) / sd
    B = (Xte - mu) / sd
    ym = Ytr.mean(0)
    W = np.linalg.solve(A.T @ A + lam * len(A) * np.eye(A.shape[1]), A.T @ (Ytr - ym))
    return B @ W + ym


RIDGE_GRID = (1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0)


def _ridge_cv_fit_predict(Xtr, Ytr, Xte, gtr, keep_scale=None, grid=RIDGE_GRID, seed: int = 0):
    """Ridge whose penalty is chosen by an inner two-fold split of the TRAINING rows by group (trajectory), then refitted on all
    training rows. Keeps the capacity of every regressor adapted to the amount of data (few test trajectories must not produce
    overfitted, meaningless cross-fitted errors)."""
    u = np.unique(gtr)
    if len(u) >= 2:
        r = np.random.default_rng(seed)
        half = np.isin(gtr, u[r.permutation(len(u))[: len(u) // 2]])
        best, best_err = grid[0], np.inf
        for lam in grid:
            err = 0.0
            for a in (half, ~half):
                if a.sum() < 3 or (~a).sum() < 3:
                    err = np.inf
                    break
                pr = _ridge_fit_predict(Xtr[a], Ytr[a], Xtr[~a], lam, keep_scale)
                err += float(np.mean((pr - Ytr[~a]) ** 2))
            if err < best_err:
                best, best_err = lam, err
    else:
        best = 1e-2
    return _ridge_fit_predict(Xtr, Ytr, Xte, best, keep_scale)


def _rff(X: np.ndarray, n_feat: int, rng: np.random.Generator, gamma: float = 1.0) -> np.ndarray:
    sd = X.std(0) + 1e-9
    Xs = (X - X.mean(0)) / sd
    return _rff_raw(Xs, n_feat, rng, gamma)


def _rff_raw(Xs: np.ndarray, n_feat: int, rng: np.random.Generator, gamma: float = 1.0) -> np.ndarray:
    """Random Fourier features of already-scaled inputs."""
    W = rng.standard_normal((Xs.shape[1], n_feat)) * np.sqrt(2 * gamma / max(1, Xs.shape[1]))
    b = rng.uniform(0, 2 * np.pi, n_feat)
    return np.sqrt(2.0 / n_feat) * np.cos(Xs @ W + b)


def _gain(e1: float, e2: float) -> float:
    """Fractional error reduction with an error floor of 1 % of the (public-scale) target variance, clipped at -1: a near-perfect
    z-only prediction cannot turn noise into a huge ratio."""
    if not (np.isfinite(e1) and np.isfinite(e2)):
        return float("nan")
    return float(max(-1.0, (e1 - e2) / max(e1, 0.01)))


def cluster_boot_gain(e1: np.ndarray, e2: np.ndarray, groups: np.ndarray, n_boot: int, seed: int) -> list[float]:
    """95 % CI of _gain(mean e1, mean e2) by resampling the clusters (trajectories) of per-point errors."""
    ug, inv = np.unique(groups, return_inverse=True)
    s1, s2, cnt = np.bincount(inv, e1), np.bincount(inv, e2), np.bincount(inv).astype(float)
    rng = np.random.default_rng(seed)
    b = []
    for _ in range(n_boot):
        w = np.bincount(rng.integers(0, len(ug), len(ug)), minlength=len(ug)).astype(float)
        n = (w * cnt).sum()
        if n > 0:
            b.append(_gain((w * s1).sum() / n, (w * s2).sum() / n))
    b = np.array([v for v in b if np.isfinite(v)])
    return [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))] if len(b) else [float("nan")] * 2


def eval_closure(model: StateModel, sid: str, trajs: list[Trajectory], pca: tuple[np.ndarray, np.ndarray], scale: np.ndarray,
                 cfg: EvalConfig = EvalConfig()) -> dict:
    """D: does discarded microstate (or history) still predict the future? At sampled times t on non-intervention test trajectories
    collect z_t = phi(x_{<=t}), z_{t+d}, y_{t+h}, u_t, the future input over (t, t+h] (mean and last value; the same features for every
    model, so input changes inside the horizon do not dilute the gain) and the residual microstate r_t = top PCs of x_t (PCA fitted on
    PUBLIC train data) minus their cross-fitted ridge prediction from (z_t, u_t). Two-fold cross-fitting by trajectory, REPEATED
    `closure_repeats` times with different fold assignments and random features; per-point squared errors are averaged over the
    repeats. Linear (ridge) and nonlinear (random Fourier features; their number scales with the number of points, min(256, max(16,
    n / 8)), the same for every model) regressors whose ridge penalty is chosen by an inner split of the training fold by trajectory.
    Readout targets keep the PUBLIC readout scale (y / sqrt(train variance)): constant test dimensions do not become noise targets.
    Score = fractional error reduction when r_t (or z at the two history lags) is added: ~0 means closed; 95 % CI by resampling
    trajectories (clusters of points)."""
    mean_x, comps = pca
    rng = np.random.default_rng(cfg.seed)
    rows = []
    for ti, tr in enumerate(trajs):
        dt = tr.dt
        lag = idx(cfg.closure_history_lags_s[1], dt)
        dmax = max(idx(d, dt) for d in cfg.closure_deltas_s)
        hm = idx(cfg.closure_task_horizon_s, dt)
        lo, hi = idx(cfg.closure_start_s, dt) + lag, len(tr.t) - max(dmax, hm) - 1
        if hi <= lo:
            continue
        for i in np.sort(rng.integers(lo, hi, cfg.closure_points_per_traj)):
            i = int(i)
            z = encode_at(model, sid, tr, i)
            zl1 = encode_at(model, sid, tr, i - idx(cfg.closure_history_lags_s[0], dt))
            zl2 = encode_at(model, sid, tr, i - lag)
            zf = {d: encode_at(model, sid, tr, i + idx(d, dt)) for d in cfg.closure_deltas_s}
            pcs = (tr.x[i].astype(np.float64) - mean_x) @ comps.T
            uf = tr.u[i + 1: i + hm + 1].astype(np.float64)
            rows.append({"traj": ti, "z": z, "zl": np.concatenate([zl1, zl2]), "zf": zf, "u": tr.u[i].astype(np.float64), "pc": pcs,
                         "uf": np.concatenate([uf.mean(0), uf[-1]]), "y": tr.y[i + hm].astype(np.float64) / np.sqrt(scale)})
    if len(rows) < 20:
        return {"n_points": len(rows), "note": "too few points"}
    tid = np.array([r["traj"] for r in rows])
    uniq = np.unique(tid)
    Z = np.stack([r["z"] for r in rows]); PC = np.stack([r["pc"] for r in rows])
    U = np.hstack([np.stack([r["u"] for r in rows]), np.stack([r["uf"] for r in rows])])
    ZL = np.stack([r["zl"] for r in rows]); Yt = np.stack([r["y"] for r in rows])
    if not (np.isfinite(Z).all() and np.isfinite(ZL).all()):
        return {"n_points": len(rows), "note": "non-finite encodings"}
    targets = {f"z_d{int(round(d * 1000))}ms": np.stack([r["zf"][d] for r in rows]) for d in cfg.closure_deltas_s}
    targets[f"y_h{int(round(cfg.closure_task_horizon_s * 1000))}ms"] = Yt
    prepared = {}
    for name, Y in targets.items():
        Y = Y[:, None] if Y.ndim == 1 else Y
        if name.startswith("y_"):
            prepared[name] = Y - Y.mean(0)                                     # public readout scale (see docstring)
        else:
            prepared[name] = (Y - Y.mean(0)) / (Y.std(0) + 1e-9)              # the model's own latent: descriptive targets only
    acc = {(name, kind): np.zeros((3, len(rows))) for name in prepared for kind in ("linear", "rff")}
    ok = {key: True for key in acc}
    for rep in range(cfg.closure_repeats):
        rr = np.random.default_rng(cfg.seed + 1009 * (rep + 1))
        fold = np.isin(tid, uniq[rr.permutation(len(uniq))[: len(uniq) // 2]])

        def crossfit(X, Y, keep_scale=None):
            pred = np.zeros_like(Y, dtype=np.float64)
            for tr_m in (fold, ~fold):
                if tr_m.sum() < 5 or (~tr_m).sum() < 5:
                    return None
                pred[~tr_m] = _ridge_cv_fit_predict(X[tr_m], Y[tr_m], X[~tr_m], tid[tr_m], keep_scale, seed=cfg.seed + rep)
            return ((pred - Y) ** 2).mean(axis=1)

        # residual microstate: PCs not explained by (z, u) (cross-fitted). Scaled by the spread of the ORIGINAL components, never by
        # its own spread: a residual that is numerical noise must stay small
        R = np.zeros_like(PC)
        for tr_m in (fold, ~fold):
            R[~tr_m] = PC[~tr_m] - _ridge_cv_fit_predict(np.hstack([Z, U])[tr_m], PC[tr_m], np.hstack([Z, U])[~tr_m], tid[tr_m],
                                                         seed=cfg.seed + rep)
        R = R / (PC.std(0) + 1e-9)
        base = np.hstack([Z, U])
        bs = (base - base.mean(0)) / (base.std(0) + 1e-9)
        nf = int(min(256, max(16, len(rows) // 8)))
        s0 = cfg.seed + 7 + 1009 * rep
        rff1 = np.hstack([bs, _rff(base, nf, np.random.default_rng(s0))])
        feats = {
            "linear": (base, np.hstack([base, R]), np.hstack([base, ZL]),
                       np.r_[np.zeros(base.shape[1], bool), np.ones(R.shape[1], bool)]),
            # the residual enters the random features at its own (pre-scaled) magnitude, next to the standardised base; the z-only
            # set is capacity-matched (as many extra random features as the residual adds)
            "rff": (np.hstack([rff1, _rff(base, nf + R.shape[1], np.random.default_rng(s0 + 3))]),
                    np.hstack([rff1, R, _rff_raw(np.hstack([bs, R]), nf, np.random.default_rng(s0 + 1))]),
                    np.hstack([rff1, (ZL - ZL.mean(0)) / (ZL.std(0) + 1e-9), _rff(np.hstack([base, ZL]), nf, np.random.default_rng(s0 + 2))]),
                    None)}
        for name, Ys in prepared.items():
            for kind, (f1, f2, f3, ks2) in feats.items():
                e = [crossfit(f1, Ys), crossfit(f2, Ys, ks2), crossfit(f3, Ys)]
                if any(v is None for v in e):
                    ok[(name, kind)] = False
                    continue
                acc[(name, kind)] += np.stack(e) / cfg.closure_repeats
    res = {"n_points": len(rows), "n_trajectories": int(len(uniq)), "repeats": cfg.closure_repeats}
    for (name, kind), E3 in acc.items():
        if not ok[(name, kind)]:
            res[f"D_{name}_{kind}"] = {"note": "too few trajectories for two folds"}
            continue
        e1, e2, e3 = (float(E3[j].mean()) for j in range(3))
        res[f"D_{name}_{kind}"] = {"err_z": e1, "err_z_plus_micro": e2, "err_z_plus_history": e3,
                                   "micro_gain": _gain(e1, e2), "history_gain": _gain(e1, e3),
                                   "micro_gain_ci95": cluster_boot_gain(E3[0], E3[1], tid, cfg.n_boot, cfg.seed),
                                   "history_gain_ci95": cluster_boot_gain(E3[0], E3[2], tid, cfg.n_boot, cfg.seed + 1),
                                   "_units": {"traj": tid.tolist(), "e_z": E3[0].tolist(), "e_micro": E3[1].tolist()}}
    return res


# ------------------------------------------------------------------------------------------------------------ D (rollout checks)
def eval_rollout_checks(model: StateModel, sid: str, trajs: list[Trajectory], scale: np.ndarray, cfg: EvalConfig = EvalConfig(),
                        a_s: float | None = None, b_s: float | None = None, noise_levels: tuple[float, ...] = (0.01, 0.05, 0.1, 0.2)) -> dict:
    """Three checks from the methods review (II.5): on non-intervention test trajectories, at each start time t0,
    - closure gap: the open-loop rollout f^{a+b}(phi(x_t0)) against f^b(phi(x_{t0+a})) (re-encoding the TRUE microstate at t0+a),
      in y (NMSE) and in z (divided by the spread of z);
    - Markov rollout consistency: restarting the model's OWN rollout at step a from its predicted z_a must reproduce the continuous
      rollout (a model that carries memory beyond z fails; its k undercounts its state) - relative z discrepancy;
    - noise robustness (dimension-cheating guard): A-type NMSE over b when z0 is perturbed by Gaussian noise of sd sigma * sd(z), sd(z)
      = the spread of z over all encodings of these test trajectories (per coordinate)."""
    a_s = cfg.rollout_a_s if a_s is None else a_s
    b_s = cfg.rollout_b_s if b_s is None else b_s
    rng = np.random.default_rng(cfg.seed)
    gaps_y, gaps_z, cons, zs = [], [], [], []
    noise = {s: [] for s in noise_levels}
    base = []
    starts = []
    for tr in trajs:
        a, b = idx(a_s, tr.dt), idx(b_s, tr.dt)
        for t0 in cfg.start_times_s:
            i0 = idx(t0, tr.dt)
            if i0 + a + b < len(tr.t):
                starts.append((tr, i0, encode_at(model, sid, tr, i0)))
    if not starts:
        return {"note": "no usable start times"}
    sd_z = np.stack([s[2] for s in starts]).std(0) + 1e-9
    for tr, i0, z0 in starts:
        dt = tr.dt
        a, b = idx(a_s, dt), idx(b_s, dt)
        u = tr.u[i0: i0 + a + b + 1]
        full = model.rollout(sid, z0, u, [], dt)
        za = encode_at(model, sid, tr, i0 + a)
        ref = model.rollout(sid, za, u[a:], [], dt)
        gaps_y.append(_capped(_nmse(np.asarray(full["y"])[a + 1:], np.asarray(ref["y"])[1:], scale))[0])
        zf, zr = np.asarray(full["z"], float), np.asarray(ref["z"], float)
        zs.append(zf)
        gaps_z.append(float(np.mean((zf[a + 1:] - zr[1:]) ** 2)))
        again = np.asarray(model.rollout(sid, zf[a], u[a:], [], dt)["z"], float)
        cons.append(float(np.mean((zf[a + 1:] - again[1:]) ** 2)))
        y_true = tr.y[i0 + 1: i0 + b + 1]
        base.append(_capped(_nmse(np.asarray(full["y"])[1: b + 1], y_true, scale))[0])
        for s in noise_levels:
            zn = z0 + s * sd_z * rng.standard_normal(z0.shape)
            noise[s].append(_capped(_nmse(np.asarray(model.rollout(sid, zn, u[: b + 1], [], dt)["y"])[1:], y_true, scale))[0])
    spread = float(np.var(np.concatenate(zs), axis=0).sum()) + 1e-12
    res = {"closure_gap_y_nmse": boot_mean(np.array(gaps_y), cfg.n_boot, cfg.seed)[0],
           "closure_gap_z_rel": float(np.mean(gaps_z) / spread),
           "markov_rollout_inconsistency_rel": float(np.mean(cons) / spread),
           "noise_curve": {"0": float(np.mean(base)), **{str(s): float(np.mean(v)) for s, v in noise.items()}}}
    return res


def eval_persistence(sid: str, trajs: list[Trajectory], scale: np.ndarray, cfg: EvalConfig = EvalConfig()) -> dict:
    """Persistence floor: y(t0 + h) predicted as y(t0)."""
    out = {}
    for h in cfg.horizons_s:
        v = []
        for tr in trajs:
            m = idx(h, tr.dt)
            rows = [_capped(_nmse(np.repeat(tr.y[idx(t0, tr.dt)][None, :], m, 0), tr.y[idx(t0, tr.dt) + 1: idx(t0, tr.dt) + m + 1],
                                  scale))[0]
                    for t0 in cfg.start_times_s if idx(t0, tr.dt) + m < len(tr.t)]
            if rows:
                v.append(float(np.mean(rows)))
        out[f"A_nmse_h{int(round(h * 1000))}ms"] = boot_mean(np.array(v), cfg.n_boot, cfg.seed)[0]
    return out


def eval_param_probe(model: StateModel, sid: str, pool: list[dict], cfg: EvalConfig = EvalConfig()) -> dict:
    """Parameter-identity leakage probe (methods review II.6): cross-validated accuracy of decoding the parameter draw (pool group)
    from z with a linear classifier, against chance. High decodability flags a latent that may encode the draw rather than state."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import cross_val_score
    if len(pool) < 20:
        return {"note": "pool too small"}
    if getattr(model, "uses_readout", False):
        Z = np.stack([np.asarray(model.encode_with_readout(sid, p["x_hist"], p["u_hist"], p["y_hist"], p["dt"]), float) for p in pool])
    else:
        Z = np.stack([np.asarray(model.encode(sid, p["x_hist"], p["u_hist"], p["dt"]), float) for p in pool])
    g = np.array([p["group"] for p in pool])
    if len(np.unique(g)) < 2:
        return {"note": "one group"}
    Zs = (Z - Z.mean(0)) / (Z.std(0) + 1e-9)
    acc = cross_val_score(LogisticRegression(max_iter=2000), Zs, g, cv=min(5, int(np.bincount(np.unique(g, return_inverse=True)[1]).min())))
    return {"accuracy": float(acc.mean()), "chance": float(np.max(np.bincount(np.unique(g, return_inverse=True)[1])) / len(g))}


# ------------------------------------------------------------------------------------------------------------ E
def whitener(A: np.ndarray, eig_floor: float = 1e-8) -> tuple[np.ndarray, np.ndarray]:
    """(mean, W) such that (a - mean) @ W is whitened with the FULL covariance of A; eigenvalues below eig_floor x the largest are
    floored (dead directions stay small instead of being amplified). Distances after whitening are invariant to invertible linear
    maps of the coordinates."""
    A = np.atleast_2d(np.asarray(A, np.float64))
    mu = A.mean(0)
    C = np.atleast_2d(np.cov((A - mu).T)) if A.shape[1] > 1 else np.array([[float(np.var(A[:, 0]))]])
    lam, V = np.linalg.eigh(C)
    lam = np.maximum(lam, max(float(lam.max()), 1e-300) * eig_floor)
    return mu, V @ np.diag(1.0 / np.sqrt(lam)) @ V.T


def _weighted_threshold(d_sorted: np.ndarray, w_sorted: np.ndarray, q: float) -> float:
    cw = np.cumsum(w_sorted)
    k = int(np.searchsorted(cw, q * cw[-1] - 1e-12))
    return float(d_sorted[min(k, len(d_sorted) - 1)])


def _matched_ratio(div: np.ndarray, d: np.ndarray, w: np.ndarray, q: float, order: np.ndarray) -> float:
    """Weighted mean divergence of the pairs within the q-quantile of distance, over the weighted mean of all pairs."""
    tot = w.sum()
    if tot <= 0:
        return float("nan")
    thr = _weighted_threshold(d[order], w[order], q)
    sel = d <= thr
    rm = (w * div).sum() / tot
    return float(((w[sel] * div[sel]).sum() / w[sel].sum()) / rm) if rm > 0 and w[sel].sum() > 0 else float("nan")


def e_cluster_boot(div: np.ndarray, dists: list[np.ndarray], ti: np.ndarray, tj: np.ndarray, traj_draw: np.ndarray, q: float,
                   n_boot: int, seed: int) -> np.ndarray:
    """Bootstrap replicates of the matched / random ratio for one or more distance vectors (the same resamples for all: paired). The
    resampling unit is the pool trajectory within its parameter draw; a pair's weight is the product of its trajectories' counts."""
    rng = np.random.default_rng(seed)
    orders = [np.argsort(d, kind="stable") for d in dists]
    draws = {g: np.flatnonzero(traj_draw == g) for g in np.unique(traj_draw)}
    out = np.full((n_boot, len(dists)), np.nan)
    for b in range(n_boot):
        c = np.zeros(len(traj_draw))
        for members in draws.values():
            np.add.at(c, members[rng.integers(0, len(members), len(members))], 1.0)
        w = c[ti] * c[tj]
        for j, (d, o) in enumerate(zip(dists, orders)):
            out[b, j] = _matched_ratio(div, d, w, q, o)
    return out


def encodings_for_whitening(model: StateModel, sid: str, train: list[Trajectory], cfg: EvalConfig, max_traj: int = 64) -> np.ndarray:
    """The model's encodings of PUBLIC training trajectories at the encoding times (the source of E's latent whitening)."""
    Z = []
    for tr in train[:max_traj]:
        for t0 in cfg.start_times_s:
            i = idx(t0, tr.dt)
            if i < len(tr.t):
                Z.append(encode_at(model, sid, tr, i))
    return np.stack(Z) if Z else np.zeros((0, 0))


def eval_microstate(model: StateModel, sid: str, pool: list[dict], scale: np.ndarray, cfg: EvalConfig = EvalConfig(),
                    pca: tuple[np.ndarray, np.ndarray] | None = None, k_match: int | None = None, whiten: dict | None = None) -> dict:
    """E: pool = states sharing one parameter draw, each with its observed history (x_hist, u_hist, dt) and the SIMULATED future
    readout from that exact microstate under a common future input (computed once by the evaluator, independent of the model).
    Pairs (same draw, different pool trajectories) whose WHITENED latent distance is in the lowest `micro_match_quantile` are
    compared with random pairs, PCA-matched pairs (k components) and output-matched pairs; the numerical floor is the pool's 'floor'
    entries. Score: ratio of the matched pairs' mean future divergence to the random pairs', with a 95 % CI by resampling pool
    trajectories within draw.

    Whitening (`whiten`: {"z" | "y" | "pc": (mean, W)}) comes from PUBLIC training data (harness.e_whiteners); without it, the pool's
    own covariance is used (development fallback, reported). Either way the distance is invariant to invertible linear maps of z.
    Testability: E is `untestable` when the matched pairs are not close (median matched / median random distance above
    `micro_resolution_max`: the pool is too sparse for the latent's dimension) or when random pairs diverge less than
    `micro_floor_factor` x the numerical floor."""
    if len(pool) < 10:
        return {"n_states": len(pool), "note": "pool too small", "E_testable": False, "E_untestable_reason": "pool too small"}
    if getattr(model, "uses_readout", False):
        Z = np.stack([np.asarray(model.encode_with_readout(sid, p["x_hist"], p["u_hist"], p["y_hist"], p["dt"]), float) for p in pool])
    else:
        Z = np.stack([np.asarray(model.encode(sid, p["x_hist"], p["u_hist"], p["dt"]), float) for p in pool])
    F = np.stack([p["future_y"] for p in pool]).astype(np.float64) / np.sqrt(scale)
    grp = np.array([p["group"] for p in pool])
    X = np.stack([p["x_hist"][-1] for p in pool]).astype(np.float64)
    Yn = np.stack([p["y_now"] for p in pool]).astype(np.float64) / np.sqrt(scale)
    trj_name = np.array([str(p.get("traj", i)) for i, p in enumerate(pool)])
    names, tix = np.unique(trj_name, return_inverse=True)
    traj_draw = np.array([grp[np.flatnonzero(tix == t)[0]] for t in range(len(names))])
    ii, jj = np.triu_indices(len(pool), 1)
    # pairs of states from the same draw and DIFFERENT pool trajectories: temporally adjacent states of one trajectory are trivially
    # similar
    same = (grp[ii] == grp[jj]) & (tix[ii] != tix[jj])
    ii, jj = ii[same], jj[same]
    if len(ii) < 10:
        return {"n_states": len(pool), "note": "too few same-group pairs", "E_testable": False, "E_untestable_reason": "too few pairs"}
    if not np.isfinite(Z).all():
        return {"n_states": len(pool), "note": "non-finite encodings", "E_testable": True, "E_ratio_latent_to_random": float("nan"),
                "E_ratio_ci95": [float("nan")] * 2}
    div = ((F[ii] - F[jj]) ** 2).mean(axis=(1, 2)) if F.ndim == 3 else ((F[ii] - F[jj]) ** 2).mean(axis=1)
    whiten = dict(whiten or {})
    src = "train" if "z" in whiten else "pool"

    def dist(A, key):
        mu, W = whiten.get(key) or whitener(A, cfg.whiten_eig_floor)
        Aw = (A - mu) @ W
        return np.sqrt(((Aw[ii] - Aw[jj]) ** 2).sum(axis=1))

    ones = np.ones(len(div))
    q = cfg.micro_match_quantile
    dz = dist(Z, "z")
    oz = np.argsort(dz, kind="stable")
    rm = float(div.mean())
    ratio = _matched_ratio(div, dz, ones, q, oz)
    thr = _weighted_threshold(dz[oz], ones, q)
    sel = dz <= thr
    rho = float(np.median(dz[sel]) / np.median(dz)) if np.median(dz) > 0 else float("inf")
    res = {"n_states": len(pool), "n_pairs": int(len(ii)), "whiten_source": src,
           "E_latent_matched": {"mean_div": float(div[sel].mean()), "n_pairs": int(sel.sum()), "median_dist_ratio": rho},
           "E_random_pairs": {"mean_div": rm, "n_pairs": int(len(div))}}
    floors = [p["floor_div"] for p in pool if p.get("floor_div") is not None]
    floor = float(np.mean(floors)) if floors else 0.0
    if floors:
        res["E_numerical_floor"] = {"mean_div": floor, "n": len(floors)}
    dists = [dz]
    dy = dist(Yn, "y")
    dists.append(dy)
    if pca is not None:
        mean_x, comps = pca
        k_eff = int(min(k_match or Z.shape[1], comps.shape[0]))
        dists.append(dist((X - mean_x) @ comps[:k_eff].T, "pc"))
    boots = e_cluster_boot(div, dists, tix[ii], tix[jj], traj_draw, q, cfg.n_boot, cfg.seed)

    def ci(col):
        v = boots[:, col]
        v = v[np.isfinite(v)]
        return [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))] if len(v) else [float("nan")] * 2

    def matched_mean(d):
        s = d <= _weighted_threshold(np.sort(d, kind="stable"), ones, q)
        return float(div[s].mean())

    res["E_ratio_latent_to_random"] = ratio
    res["E_ratio_ci95"] = ci(0)
    res["E_output_matched"] = {"ratio": _matched_ratio(div, dy, ones, q, np.argsort(dy, kind="stable")), "ci95": ci(1),
                               "mean_div": matched_mean(dy)}
    if pca is not None:
        res["E_pca_matched"] = {"ratio": _matched_ratio(div, dists[2], ones, q, np.argsort(dists[2], kind="stable")), "ci95": ci(2),
                                "mean_div": matched_mean(dists[2]), "k": int(k_eff), "k_requested": int(k_match or Z.shape[1])}
    reasons = []
    if not rho <= cfg.micro_resolution_max:
        reasons.append(f"matched pairs not close (median distance ratio {rho:.3g} > {cfg.micro_resolution_max})")
    if floors and not rm >= cfg.micro_floor_factor * floor:
        reasons.append(f"random-pair divergence {rm:.3g} < {cfg.micro_floor_factor} x floor {floor:.3g}")
    res["E_resolution"] = rho
    res["E_testable"] = not reasons
    res["E_untestable_reason"] = "; ".join(reasons) or None
    res["_units"] = {"div": div.tolist(), "d": dz.tolist(), "ti": tix[ii].tolist(), "tj": tix[jj].tolist(), "traj_draw": traj_draw.tolist()}
    return res
