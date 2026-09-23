"""Activation screen: stimulate candidate neurons one at a time and score the readout rhythm (independent re-implementation
of the published DN screen; see research/literature/pugliese_model_spec_from_code.md sections 4.1 and 6).

For each candidate and parameter replicate the stimulus amplitude is auto-tuned by bisection: a run is *too strong*
when more than ``n_active_upper`` neurons are active or more than ``n_high_fr_upper`` neurons exceed
``high_fr_threshold`` Hz, *too weak* when fewer than ``n_active_lower`` neurons are active; the amplitude is halved,
doubled or set to the midpoint of the bracket, for at most ``max_adjustment_iters`` iterations. The last tested
amplitude that satisfied the bounds is scored; replicates that never satisfied them are reported as unusable (the
original left them in and filtered afterwards).

"Active" during tuning means any positive rate anywhere in the trace (the original's ``sum_t R > 0``); the score uses
the readout neurons with peak rate > ``active_rate_hz`` after the analysis start.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from ..metrics.rhythm import ACTIVE_RATE_HZ, DEFAULT_PROMINENCE, network_oscillation_score
from .model import ModelConfig, NeuronParams, Stimulus, sample_neuron_params, simulate

SCREEN_ALGORITHM_ID = "brainir.sim.screen.autotuned_activation_v1"


@dataclass
class ScreenConfig:
    initial_current: float = 128.0
    max_adjustment_iters: int = 10
    n_active_upper: int = 1500
    n_active_lower: int = 5
    n_high_fr_upper: int = 100
    high_fr_threshold: float = 100.0
    analysis_start_s: float = 0.25
    active_rate_hz: float = ACTIVE_RATE_HZ
    prominence: float = DEFAULT_PROMINENCE

    def to_dict(self) -> dict:
        return {"algorithm": SCREEN_ALGORITHM_ID, **self.__dict__}


@dataclass
class ScreenReplicate:
    candidate: int
    seed: int
    usable: bool
    score: float | None
    frequency_hz: float | None
    n_active_readout: int | None
    current: float
    n_tuning_runs: int
    n_active_all: int
    n_high_fr: int
    wall_time_s: float

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _classify(traj, cfg: ScreenConfig) -> tuple[str, int, int]:
    any_pos = (traj.r > 0).any(axis=0)
    n_active = int(any_pos.sum())
    n_high = int((traj.r.max(axis=0) > cfg.high_fr_threshold).sum())
    if n_active > cfg.n_active_upper or n_high > cfg.n_high_fr_upper:
        return "strong", n_active, n_high
    if n_active < cfg.n_active_lower:
        return "weak", n_active, n_high
    return "ok", n_active, n_high


def screen_candidate(W: sp.csr_matrix, params: NeuronParams, model_cfg: ModelConfig, candidate: int, readout_mask: np.ndarray,
                     *, seed: int, cfg: ScreenConfig | None = None) -> ScreenReplicate:
    cfg = cfg or ScreenConfig()
    t0 = time.time()
    cur = cfg.initial_current
    lo, hi = None, None  # bracket: last too-weak / too-strong amplitudes
    best = None
    n_runs = 0
    dt = model_cfg.dt_out
    for _ in range(cfg.max_adjustment_iters):
        traj = simulate(W, params, model_cfg, Stimulus((int(candidate),), (float(cur),)))
        n_runs += 1
        verdict, n_active, n_high = _classify(traj, cfg)
        if verdict == "ok":
            best = (traj, cur, n_active, n_high)
            break
        if verdict == "strong":
            hi = cur
            cur = cur / 2 if lo is None else (cur + lo) / 2
        else:
            lo = cur
            cur = cur * 2 if hi is None else (cur + hi) / 2
    if best is None:
        return ScreenReplicate(int(candidate), int(seed), False, None, None, None, float(cur), n_runs, n_active, n_high,
                               round(time.time() - t0, 2))
    traj, cur, n_active, n_high = best
    win = traj.window(cfg.analysis_start_s)
    peak = win.max(axis=0)
    mask = (peak > cfg.active_rate_hz) & np.asarray(readout_mask, bool)
    score, f, _, _ = network_oscillation_score(win, mask, cfg.prominence)
    return ScreenReplicate(int(candidate), int(seed), True, float(score), (f / dt if f > 0 else None), int(mask.sum()), float(cur),
                           n_runs, n_active, n_high, round(time.time() - t0, 2))


def run_screen_job(args) -> ScreenReplicate:
    """Backend-friendly entry point: args = (W, model_cfg, candidate, readout_mask, sizes, seed, screen_cfg)."""
    W, model_cfg, candidate, readout_mask, sizes, seed, screen_cfg = args
    params = sample_neuron_params(model_cfg, W.shape[0], int(seed), sizes)
    return screen_candidate(W, params, model_cfg, candidate, readout_mask, seed=int(seed), cfg=screen_cfg)


def aggregate_screen(reps: list[ScreenReplicate]) -> dict:
    """Per-candidate mean score over usable replicates (the published ranking statistic) plus counts."""
    out: dict[int, dict] = {}
    for r in reps:
        d = out.setdefault(r.candidate, {"scores": [], "freqs": [], "n_replicates": 0, "n_usable": 0})
        d["n_replicates"] += 1
        if r.usable:
            d["n_usable"] += 1
            d["scores"].append(r.score)
            if r.frequency_hz is not None:
                d["freqs"].append(r.frequency_hz)
    table = []
    for cand, d in out.items():
        s = np.array(d["scores"])
        table.append({"candidate": cand, "n_replicates": d["n_replicates"], "n_usable": d["n_usable"],
                      "mean_score": float(s.mean()) if len(s) else None, "median_score": float(np.median(s)) if len(s) else None,
                      "fraction_ge_0_5": float((s >= 0.5).mean()) if len(s) else None,
                      "best_score": float(s.max()) if len(s) else None,
                      "median_frequency_hz": float(np.median(d["freqs"])) if d["freqs"] else None})
    table.sort(key=lambda x: (-(x["mean_score"] if x["mean_score"] is not None else -1), x["candidate"]))
    for rank, row in enumerate(table, start=1):
        row["rank"] = rank
    return {"algorithm": SCREEN_ALGORITHM_ID, "candidates": table}
