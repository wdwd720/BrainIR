"""Functional criteria: what "the target computation is preserved" means for a trajectory.

Every criterion maps a simulated trajectory (rates over time, post-transient window) and the readout mask to a score in
[0, 1] and a pass/fail verdict. They are specified by a JSON-able dict so that a worker process (or a Modal container)
can rebuild them; ``criterion.json`` inside a synthetic instance selects one. The dng100 bundle has no criterion file
and uses ``rhythm`` with the frozen evaluator's settings.

    rhythm          published autocorrelation score of the active readout neurons + an amplitude gate
    activity_band   mean readout rate in the window inside [lo, hi] Hz (drivers, controllers)
    persistence     readout activity after stimulus offset stays >= frac x activity during the stimulus (memory, switches)
    selectivity     one readout group active, the other silent (winner-take-all / comparator)
    ramp            readout rate keeps rising through the window (integrator) — slope over mean >= threshold
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..metrics.rhythm import network_oscillation_score


def _window(traj, t0: float, t1: float | None = None):
    m = traj.t >= t0 - 1e-12
    if t1 is not None:
        m &= traj.t <= t1 + 1e-12
    return traj.r[m], traj.t[m]


@dataclass(frozen=True)
class Criterion:
    spec: dict

    @property
    def type(self) -> str:
        return self.spec["type"]

    def evaluate(self, traj, readout_mask: np.ndarray) -> dict:
        t = self.type
        if t == "rhythm":
            return _rhythm(traj, readout_mask, self.spec)
        if t == "activity_band":
            return _activity_band(traj, readout_mask, self.spec)
        if t == "persistence":
            return _persistence(traj, readout_mask, self.spec)
        if t == "selectivity":
            return _selectivity(traj, readout_mask, self.spec)
        if t == "ramp":
            return _ramp(traj, readout_mask, self.spec)
        raise ValueError(f"unknown criterion type {t!r}")


def criterion_from_spec(spec: dict) -> Criterion:
    if spec.get("type") not in CRITERIA:
        raise ValueError(f"unknown criterion {spec.get('type')!r}; known: {sorted(CRITERIA)}")
    return Criterion(dict(spec))


def _common(traj, readout_mask, t0: float, active_rate_hz: float) -> dict:
    win, _ = _window(traj, t0)
    peak = win.max(axis=0) if len(win) else np.zeros(traj.r.shape[1])
    active_all = peak > active_rate_hz
    return {"n_active_all": int(active_all.sum()), "n_active_readout": int((active_all & readout_mask).sum()),
            "active_positions": np.flatnonzero(active_all).astype(np.int32),
            "readout_peak_median_hz": float(np.median(peak[readout_mask])) if readout_mask.any() else 0.0,
            "solver_success": bool(traj.info.get("success", True)) and not traj.info.get("non_finite_samples")}


def _rhythm(traj, readout_mask, spec) -> dict:
    t0 = float(spec.get("analysis_start_s", 0.25))
    active_rate = float(spec.get("active_rate_hz", 0.01))
    win, t = _window(traj, t0)
    peak = win.max(axis=0)
    mask = (peak > active_rate) & readout_mask
    score, f, _, _ = network_oscillation_score(win, mask, float(spec.get("prominence", 0.05)))
    dt = float(traj.t[1] - traj.t[0])
    rng = float(np.median(win[:, mask].max(axis=0) - win[:, mask].min(axis=0))) if mask.any() else 0.0
    amp_min = float(spec.get("amplitude_min_hz", 0.25))
    thr = float(spec.get("score_threshold", 0.5))
    out = _common(traj, readout_mask, t0, active_rate)
    out.update(score=float(score), passed=bool(score >= thr and rng >= amp_min), frequency_hz=(f / dt) if f > 0 else None,
               readout_range_median_hz=rng, criterion="rhythm")
    return out


def _activity_band(traj, readout_mask, spec) -> dict:
    t0 = float(spec.get("analysis_start_s", 0.25))
    win, _ = _window(traj, t0)
    mean_rate = float(win[:, readout_mask].mean()) if readout_mask.any() else 0.0
    lo, hi = float(spec.get("lo_hz", 1.0)), float(spec.get("hi_hz", 1e9))
    # score: 1 inside the band, decaying linearly to 0 at 0 Hz / 2*hi outside
    if lo <= mean_rate <= hi:
        score = 1.0
    elif mean_rate < lo:
        score = mean_rate / lo if lo > 0 else 0.0
    else:
        score = max(0.0, 1.0 - (mean_rate - hi) / max(hi, 1e-9))
    out = _common(traj, readout_mask, t0, float(spec.get("active_rate_hz", 0.01)))
    out.update(score=float(score), passed=bool(lo <= mean_rate <= hi), readout_mean_hz=mean_rate, frequency_hz=None, criterion="activity_band")
    return out


def _persistence(traj, readout_mask, spec) -> dict:
    """Activity during [during_t0, off] vs after the stimulus is switched off ([off + settle, end])."""
    off = float(spec["stimulus_off_s"])
    settle = float(spec.get("settle_s", 0.1))
    during, _ = _window(traj, float(spec.get("during_start_s", 0.1)), off)
    after, _ = _window(traj, off + settle)
    d = float(during[:, readout_mask].mean()) if len(during) and readout_mask.any() else 0.0
    a = float(after[:, readout_mask].mean()) if len(after) and readout_mask.any() else 0.0
    frac = float(spec.get("min_fraction", 0.5))
    min_rate = float(spec.get("min_rate_hz", 1.0))
    ratio = (a / d) if d > 0 else 0.0
    score = float(min(1.0, ratio / frac)) if d >= min_rate else 0.0
    out = _common(traj, readout_mask, float(spec.get("during_start_s", 0.1)), float(spec.get("active_rate_hz", 0.01)))
    out.update(score=score, passed=bool(d >= min_rate and a >= frac * d and a >= min_rate), readout_during_hz=d, readout_after_hz=a,
               frequency_hz=None, criterion="persistence")
    return out


def _selectivity(traj, readout_mask, spec) -> dict:
    """Group A (positions) should be active, group B silent: score = (mean_A - mean_B) / (mean_A + mean_B)."""
    t0 = float(spec.get("analysis_start_s", 0.25))
    win, _ = _window(traj, t0)
    a_pos = [int(p) for p in spec["group_a_positions"]]
    b_pos = [int(p) for p in spec["group_b_positions"]]
    ma = float(win[:, a_pos].mean()) if a_pos else 0.0
    mb = float(win[:, b_pos].mean()) if b_pos else 0.0
    min_rate = float(spec.get("min_rate_hz", 1.0))
    sel = (ma - mb) / (ma + mb) if (ma + mb) > 0 else 0.0
    thr = float(spec.get("min_selectivity", 0.8))
    out = _common(traj, readout_mask, t0, float(spec.get("active_rate_hz", 0.01)))
    out.update(score=float(max(0.0, sel)), passed=bool(ma >= min_rate and sel >= thr), group_a_mean_hz=ma, group_b_mean_hz=mb,
               frequency_hz=None, criterion="selectivity")
    return out


def _ramp(traj, readout_mask, spec) -> dict:
    """Integrator: the readout keeps rising through the window; relative slope (per second, over the mean) >= threshold."""
    t0, t1 = float(spec.get("window_start_s", 0.1)), spec.get("window_end_s")
    win, t = _window(traj, t0, None if t1 is None else float(t1))
    y = win[:, readout_mask].mean(axis=1) if readout_mask.any() else np.zeros(len(win))
    if len(y) < 3 or y.mean() <= 0:
        rel = 0.0
    else:
        slope = np.polyfit(t, y, 1)[0]
        rel = float(slope / y.mean())
    thr = float(spec.get("min_relative_slope", 0.5))
    min_rate = float(spec.get("min_rate_hz", 0.5))
    out = _common(traj, readout_mask, t0, float(spec.get("active_rate_hz", 0.01)))
    out.update(score=float(min(1.0, max(0.0, rel / thr))), passed=bool(rel >= thr and (y.mean() if len(y) else 0.0) >= min_rate),
               relative_slope_per_s=rel, frequency_hz=None, criterion="ramp")
    return out


CRITERIA = {"rhythm": _rhythm, "activity_band": _activity_band, "persistence": _persistence, "selectivity": _selectivity, "ramp": _ramp}
