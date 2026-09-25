"""Evaluation metrics for state discovery (benchmarks/state_discovery_v1/PROTOCOL.md; goal4 sections 7, 9-12, 42, 49-52).

Every family is computed and reported SEPARATELY; nothing is collapsed into one score. All normalisation constants come from PUBLIC
training data (never from test statistics). The resampling unit for confidence intervals is the trajectory (a trajectory's start
times and pairs are resampled together); across systems the unit is the system.

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
    c_windows_s: tuple[float, ...] = (0.1, 0.25, 0.5)
    primary_c_window_s: float = 0.25
    rollout_a_s: float = 0.05
    rollout_b_s: float = 0.2
    micro_future_s: float = 0.25
    ridge: float = 1e-3
    n_boot: int = 2000
    micro_match_quantile: float = 0.02
    seed: int = 0


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
    v = np.asarray(v, float)
    v = v[np.isfinite(v)]
    if len(v) == 0:
        return float("nan"), [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    b = [v[rng.integers(0, len(v), len(v))].mean() for _ in range(n_boot)]
    return float(v.mean()), [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]


def readout_scale(train: list[Trajectory]) -> np.ndarray:
    """Per-readout-dimension variance from PUBLIC training data (the fixed NMSE normaliser); floor avoids silent dimensions."""
    Y = np.concatenate([t.y for t in train], axis=0).astype(np.float64)
    var = Y.var(axis=0)
    return np.maximum(var, max(1e-6, 1e-3 * float(var.max()) if var.size else 1e-6))


def _nmse(pred: np.ndarray, true: np.ndarray, scale: np.ndarray) -> float:
    return float(np.mean((pred - true) ** 2 / scale))


# ------------------------------------------------------------------------------------------------------------ A and B
def eval_predictive(model: StateModel, sid: str, trajs: list[Trajectory], scale: np.ndarray, cfg: EvalConfig = EvalConfig()) -> dict:
    """A: window NMSE of rollouts (no events) from several start times; B: instantaneous readout NMSE."""
    per_h = {h: [] for h in cfg.horizons_s}
    units = {h: {} for h in cfg.horizons_s}
    b_err = []
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
                    rows[h].append(_nmse(yp[1: m + 1], tr.y[i0 + 1: i0 + m + 1], scale))
            b_err.append(_nmse(np.asarray(model.readout(sid, z0[None, :], tr.u[i0][None, :]), float), tr.y[i0][None, :], scale))
        for h in cfg.horizons_s:
            if rows[h]:
                per_h[h].append(float(np.mean(rows[h])))
                units[h][tr.key] = per_h[h][-1]
    res = {"n_trajectories": len(trajs)}
    for h, v in per_h.items():
        m, ci = boot_mean(np.array(v), cfg.n_boot, cfg.seed)
        res[f"A_nmse_h{int(round(h * 1000))}ms"] = {"mean": m, "ci95": ci, "n": len(v)}
    m, ci = boot_mean(np.array(b_err), cfg.n_boot, cfg.seed)
    res["B_readout_nmse"] = {"mean": m, "ci95": ci, "n": len(b_err)}
    # per-unit values (unit = trajectory) for paired comparisons between models on the same data; strip before reporting
    res["_units"] = {f"A_nmse_h{int(round(h * 1000))}ms": u for h, u in units.items()}
    return res


# ------------------------------------------------------------------------------------------------------------ C
def eval_intervention(model: StateModel, sid: str, pairs: list[tuple[Trajectory, Trajectory]], scale: np.ndarray,
                      cfg: EvalConfig = EvalConfig(), windows_s: tuple[float, ...] | None = None) -> dict:
    """C: per intervention trajectory with its counterfactual twin (same seed / state / inputs, no events): encode at the first event
    time (the pre-intervention sample), roll out with and without the events, and compare (i) the post-intervention trajectory and
    (ii) the predicted EFFECT (with - without) to the true effect (intervened - twin). Effect error = sum ||d_pred - d_true||^2 /
    sum ||d_true||^2 (1 = predicting no effect). Unsupported event kinds count as abstentions, reported apart."""
    windows_s = tuple(windows_s or cfg.c_windows_s)
    by_w = {w: {"traj_nmse": [], "eff_num": [], "eff_den": []} for w in windows_s}
    units = {w: {} for w in windows_s}
    abstained, n = 0, 0
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
            by_w[w]["traj_nmse"].append(_nmse(yi[1: m + 1], tr.y[i0 + 1: i0 + m + 1], scale))
            by_w[w]["eff_num"].append(float(((d_pred - d_true) ** 2).sum()))
            by_w[w]["eff_den"].append(float((d_true ** 2).sum()))
            units[w][tr.key] = (by_w[w]["eff_num"][-1], by_w[w]["eff_den"][-1], by_w[w]["traj_nmse"][-1])
    res = {"n_pairs": n, "n_abstained_unsupported": abstained}
    for w, d in by_w.items():
        wm = int(round(w * 1000))
        m, ci = boot_mean(np.array(d["traj_nmse"]), cfg.n_boot, cfg.seed)
        res[f"C_post_nmse_w{wm}ms"] = {"mean": m, "ci95": ci, "n": len(d["traj_nmse"])}
        r, rci = boot_ratio(np.array(d["eff_num"]), np.array(d["eff_den"]), cfg.n_boot, cfg.seed)
        res[f"C_effect_error_w{wm}ms"] = {"ratio": r, "ci95": rci, "n": len(d["eff_num"])}
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


def eval_closure(model: StateModel, sid: str, trajs: list[Trajectory], pca: tuple[np.ndarray, np.ndarray], scale: np.ndarray,
                 cfg: EvalConfig = EvalConfig()) -> dict:
    """D: does discarded microstate (or history) still predict the future? At sampled times t on non-intervention test trajectories
    collect z_t = phi(x_{<=t}), z_{t+d}, y_{t+h}, u_t and the residual microstate r_t = top PCs of x_t (PCA fitted on PUBLIC train
    data) minus their ridge prediction from z_t (cross-fitted). Two-fold cross-fitting by trajectory; linear (ridge) and nonlinear
    (random Fourier features; their number scales with the number of points, min(256, max(16, n / 8)), the same for every model)
    regressors whose ridge penalty is chosen by an inner split of the training fold by trajectory. Score = fractional error
    reduction when r_t (or z at the two history lags) is added: ~0 means closed."""
    mean_x, comps = pca
    rng = np.random.default_rng(cfg.seed)
    rows = []
    for ti, tr in enumerate(trajs):
        dt = tr.dt
        lag = idx(cfg.closure_history_lags_s[1], dt)
        dmax = max(idx(d, dt) for d in cfg.closure_deltas_s)
        hm = idx(cfg.closure_task_horizon_s, dt)
        lo, hi = idx(0.25, dt) + lag, len(tr.t) - max(dmax, hm) - 1
        if hi <= lo:
            continue
        for i in np.sort(rng.integers(lo, hi, cfg.closure_points_per_traj)):
            z = encode_at(model, sid, tr, int(i))
            zl1 = encode_at(model, sid, tr, int(i) - idx(cfg.closure_history_lags_s[0], dt))
            zl2 = encode_at(model, sid, tr, int(i) - lag)
            zf = {d: encode_at(model, sid, tr, int(i) + idx(d, dt)) for d in cfg.closure_deltas_s}
            pcs = (tr.x[int(i)].astype(np.float64) - mean_x) @ comps.T
            rows.append({"traj": ti, "z": z, "zl": np.concatenate([zl1, zl2]), "zf": zf, "u": tr.u[int(i)].astype(np.float64), "pc": pcs,
                         "y": tr.y[int(i) + hm].astype(np.float64) / np.sqrt(scale)})
    if len(rows) < 20:
        return {"n_points": len(rows), "note": "too few points"}
    tid = np.array([r["traj"] for r in rows])
    uniq = np.unique(tid)
    fold = np.isin(tid, uniq[rng.permutation(len(uniq))[: len(uniq) // 2]])
    Z = np.stack([r["z"] for r in rows]); U = np.stack([r["u"] for r in rows]); PC = np.stack([r["pc"] for r in rows])
    ZL = np.stack([r["zl"] for r in rows]); Yt = np.stack([r["y"] for r in rows])

    def crossfit(X, Y, keep_scale=None):
        pred = np.zeros_like(Y, dtype=np.float64)
        for tr_m in (fold, ~fold):
            if tr_m.sum() < 5 or (~tr_m).sum() < 5:
                return float("nan")
            pred[~tr_m] = _ridge_cv_fit_predict(X[tr_m], Y[tr_m], X[~tr_m], tid[tr_m], keep_scale, seed=cfg.seed)
        return float(np.mean((pred - Y) ** 2))

    def gain(e1, e2):
        """Fractional error reduction with an error floor of 1 % of the (standardised) target variance, clipped at -1: a
        near-perfect z-only prediction cannot turn noise into a huge ratio."""
        if not (np.isfinite(e1) and np.isfinite(e2)):
            return float("nan")
        return float(max(-1.0, (e1 - e2) / max(e1, 0.01)))

    # residual microstate: PCs not explained by z (cross-fitted). Scaled by the spread of the ORIGINAL components, never by its own
    # spread: a residual that is numerical noise must stay small (standardising it would amplify noise into spurious features)
    R = np.zeros_like(PC)
    for tr_m in (fold, ~fold):
        R[~tr_m] = PC[~tr_m] - _ridge_cv_fit_predict(np.hstack([Z, U])[tr_m], PC[tr_m], np.hstack([Z, U])[~tr_m], tid[tr_m], seed=cfg.seed)
    R = R / (PC.std(0) + 1e-9)
    res = {"n_points": len(rows)}
    targets = {f"z_d{int(round(d * 1000))}ms": np.stack([r["zf"][d] for r in rows]) for d in cfg.closure_deltas_s}
    targets[f"y_h{int(round(cfg.closure_task_horizon_s * 1000))}ms"] = Yt
    for name, Y in targets.items():
        if Y.ndim == 1:
            Y = Y[:, None]
        Ys = (Y - Y.mean(0)) / (Y.std(0) + 1e-9)
        for kind in ("linear", "rff"):
            if kind == "linear":
                f1, f2, f3 = np.hstack([Z, U]), np.hstack([Z, U, R]), np.hstack([Z, U, ZL])
                ks2 = np.r_[np.zeros(Z.shape[1] + U.shape[1], bool), np.ones(R.shape[1], bool)]
                e1, e2, e3 = crossfit(f1, Ys), crossfit(f2, Ys, ks2), crossfit(f3, Ys)
            else:
                g = np.random.default_rng(cfg.seed + 7)
                nf = int(min(256, max(16, len(rows) // 8)))
                base = np.hstack([Z, U])
                bs = (base - base.mean(0)) / (base.std(0) + 1e-9)
                f1 = np.hstack([bs, _rff(base, nf, g)])
                # the residual enters the random features at its own (pre-scaled) magnitude, next to the standardised base
                f2 = np.hstack([f1, R, _rff_raw(np.hstack([bs, R]), nf, np.random.default_rng(cfg.seed + 8))])
                zl_s = (ZL - ZL.mean(0)) / (ZL.std(0) + 1e-9)
                f3 = np.hstack([f1, zl_s, _rff(np.hstack([base, ZL]), nf, np.random.default_rng(cfg.seed + 9))])
                # capacity-matched to f2 / f3: as many extra random features as those add
                f1 = np.hstack([f1, _rff(base, nf + R.shape[1], np.random.default_rng(cfg.seed + 10))])
                e1, e2, e3 = crossfit(f1, Ys), crossfit(f2, Ys), crossfit(f3, Ys)
            res[f"D_{name}_{kind}"] = {"err_z": e1, "err_z_plus_micro": e2, "err_z_plus_history": e3,
                                       "micro_gain": gain(e1, e2), "history_gain": gain(e1, e3)}
    return res


# ------------------------------------------------------------------------------------------------------------ D (rollout checks)
def eval_rollout_checks(model: StateModel, sid: str, trajs: list[Trajectory], scale: np.ndarray, cfg: EvalConfig = EvalConfig(),
                        a_s: float | None = None, b_s: float | None = None, noise_levels: tuple[float, ...] = (0.01, 0.05, 0.1, 0.2)) -> dict:
    """Three checks from the methods review (II.5): on non-intervention test trajectories, at each start time t0,
    - closure gap: the open-loop rollout f^{a+b}(phi(x_t0)) against f^b(phi(x_{t0+a})) (re-encoding the TRUE microstate at t0+a),
      in y (NMSE) and in z (divided by the spread of z);
    - Markov rollout consistency: restarting the model's OWN rollout at step a from its predicted z_a must reproduce the continuous
      rollout (a model that carries memory beyond z fails; its k undercounts its state) - relative z discrepancy;
    - noise robustness (dimension-cheating guard): A-type NMSE over b when z0 is perturbed by Gaussian noise of sd sigma * sd(z)."""
    a_s = cfg.rollout_a_s if a_s is None else a_s
    b_s = cfg.rollout_b_s if b_s is None else b_s
    rng = np.random.default_rng(cfg.seed)
    gaps_y, gaps_z, cons, zs = [], [], [], []
    noise = {s: [] for s in noise_levels}
    base = []
    for tr in trajs:
        dt = tr.dt
        a, b = idx(a_s, dt), idx(b_s, dt)
        for t0 in cfg.start_times_s:
            i0 = idx(t0, dt)
            if i0 + a + b >= len(tr.t):
                continue
            z0 = encode_at(model, sid, tr, i0)
            u = tr.u[i0: i0 + a + b + 1]
            full = model.rollout(sid, z0, u, [], dt)
            za = encode_at(model, sid, tr, i0 + a)
            ref = model.rollout(sid, za, u[a:], [], dt)
            gaps_y.append(_nmse(np.asarray(full["y"])[a + 1:], np.asarray(ref["y"])[1:], scale))
            zf, zr = np.asarray(full["z"], float), np.asarray(ref["z"], float)
            zs.append(zf)
            gaps_z.append(float(np.mean((zf[a + 1:] - zr[1:]) ** 2)))
            again = np.asarray(model.rollout(sid, zf[a], u[a:], [], dt)["z"], float)
            cons.append(float(np.mean((zf[a + 1:] - again[1:]) ** 2)))
            y_true = tr.y[i0 + 1: i0 + b + 1]
            base.append(_nmse(np.asarray(full["y"])[1: b + 1], y_true, scale))
            sd = zf.std(0) + 1e-9
            for s in noise_levels:
                zn = z0 + s * sd * rng.standard_normal(z0.shape)
                noise[s].append(_nmse(np.asarray(model.rollout(sid, zn, u[: b + 1], [], dt)["y"])[1:], y_true, scale))
    if not gaps_y:
        return {"note": "no usable start times"}
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
            rows = [_nmse(np.repeat(tr.y[idx(t0, tr.dt)][None, :], m, 0), tr.y[idx(t0, tr.dt) + 1: idx(t0, tr.dt) + m + 1], scale)
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
def eval_microstate(model: StateModel, sid: str, pool: list[dict], scale: np.ndarray, cfg: EvalConfig = EvalConfig(),
                    pca: tuple[np.ndarray, np.ndarray] | None = None, k_match: int | None = None) -> dict:
    """E: pool = states sharing one parameter draw, each with its observed history (x_hist, u_hist, dt) and the SIMULATED future
    readout from that exact microstate under a common future input (computed once by the evaluator, independent of the model).
    Pairs whose latent distance is in the lowest `micro_match_quantile` are compared with random pairs, PCA-matched pairs (k
    components), output-matched pairs, and the numerical floor (the pool's 'floor' entries: one state simulated twice with a
    perturbed integrator). Scores: mean future divergence (NMSE between the two futures) per matching rule."""
    if len(pool) < 10:
        return {"n_states": len(pool), "note": "pool too small"}
    if getattr(model, "uses_readout", False):
        Z = np.stack([np.asarray(model.encode_with_readout(sid, p["x_hist"], p["u_hist"], p["y_hist"], p["dt"]), float) for p in pool])
    else:
        Z = np.stack([np.asarray(model.encode(sid, p["x_hist"], p["u_hist"], p["dt"]), float) for p in pool])
    F = np.stack([p["future_y"] for p in pool]).astype(np.float64) / np.sqrt(scale)
    grp = np.array([p["group"] for p in pool])
    X = np.stack([p["x_hist"][-1] for p in pool]).astype(np.float64)
    Yn = np.stack([p["y_now"] for p in pool]).astype(np.float64) / np.sqrt(scale)
    ii, jj = np.triu_indices(len(pool), 1)
    same = grp[ii] == grp[jj]
    # pairs of states from DIFFERENT pool trajectories only: temporally adjacent states of one trajectory are trivially similar
    trj = np.array([str(p.get("traj", i)) for i, p in enumerate(pool)])
    same &= trj[ii] != trj[jj]
    ii, jj = ii[same], jj[same]
    if len(ii) < 10:
        return {"n_states": len(pool), "note": "too few same-group pairs"}
    div = ((F[ii] - F[jj]) ** 2).mean(axis=(1, 2)) if F.ndim == 3 else ((F[ii] - F[jj]) ** 2).mean(axis=1)

    def matched(D):
        thr = np.quantile(D, cfg.micro_match_quantile)
        sel = D <= thr
        return boot_mean(div[sel], cfg.n_boot, cfg.seed) + (int(sel.sum()),)

    def dist(A):
        As = (A - A.mean(0)) / (A.std(0) + 1e-9)
        return np.sqrt(((As[ii] - As[jj]) ** 2).sum(axis=1))

    res = {"n_states": len(pool), "n_pairs": int(len(ii))}
    m, ci, npairs = matched(dist(Z))
    res["E_latent_matched"] = {"mean_div": m, "ci95": ci, "n_pairs": npairs}
    rm, rci = boot_mean(div, cfg.n_boot, cfg.seed)
    res["E_random_pairs"] = {"mean_div": rm, "ci95": rci, "n_pairs": int(len(div))}
    m2, ci2, n2 = matched(dist(Yn))
    res["E_output_matched"] = {"mean_div": m2, "ci95": ci2, "n_pairs": n2}
    if pca is not None:
        mean_x, comps = pca
        k = k_match or Z.shape[1]
        P = (X - mean_x) @ comps[:k].T
        m3, ci3, n3 = matched(dist(P))
        res["E_pca_matched"] = {"mean_div": m3, "ci95": ci3, "n_pairs": n3, "k": int(k)}
    floors = [p["floor_div"] for p in pool if p.get("floor_div") is not None]
    if floors:
        res["E_numerical_floor"] = {"mean_div": float(np.mean(floors)), "n": len(floors)}
    res["E_ratio_latent_to_random"] = m / rm if rm > 0 else float("nan")
    return res
