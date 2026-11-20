"""Tuner v2 (PREREG v2 P1): B1's locked type-level tuner (`typescreen.screen_group`, imported unchanged) plus ONE acceptance
condition, at least `k_min` active front-leg MNs in the accepted run. A run inside the activity bounds with fewer than
`k_min` active read-out neurons counts as too weak (the current goes up exactly as for a too-weak run). With `k_min = 0` the
procedure is line for line B1's (the tuner-regression gate checks digests). New module: nothing locked by run 1 is edited.
"""

from __future__ import annotations

import time
from typing import Callable, Sequence

import numpy as np
import scipy.sparse as sp
from brainir.metrics.rhythm import network_oscillation_score
from brainir.sim.model import ModelConfig, NeuronParams, Stimulus, Trajectory, simulate
from brainir.sim.screen import ScreenConfig

from .typescreen import GroupReplicate, _classify


def _n_active_readout(traj: Trajectory, cfg: ScreenConfig, readout_mask: np.ndarray) -> int:
    win = traj.window(cfg.analysis_start_s)
    peak = win.max(axis=0)
    return int(((peak > cfg.active_rate_hz) & np.asarray(readout_mask, bool)).sum())


def screen_group_v2(W: sp.csr_matrix, params: NeuronParams, model_cfg: ModelConfig, members: Sequence[int], readout_mask: np.ndarray,
                    *, seed: int, k_min: int, cfg: ScreenConfig | None = None,
                    extras: Callable[[Trajectory], dict] | None = None) -> GroupReplicate:
    cfg = cfg or ScreenConfig()
    t0 = time.time()
    cur = cfg.initial_current
    lo, hi = None, None
    best = None
    n_runs = 0
    dt = model_cfg.dt_out
    members = tuple(int(m) for m in members)
    if not members:
        raise ValueError("a group needs at least one member")
    for _ in range(cfg.max_adjustment_iters):
        traj = simulate(W, params, model_cfg, Stimulus(members, (float(cur),)))
        n_runs += 1
        verdict, n_active, n_high = _classify(traj, cfg)
        if verdict == "ok" and k_min > 0 and _n_active_readout(traj, cfg, readout_mask) < k_min:
            verdict = "weak"  # V2: inside the activity bounds but fewer than k_min active front-leg MNs
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
        return GroupReplicate(members, int(seed), False, None, None, None, float(cur), n_runs, n_active, n_high,
                              round(time.time() - t0, 2))
    traj, cur, n_active, n_high = best
    win = traj.window(cfg.analysis_start_s)
    peak = win.max(axis=0)
    mask = (peak > cfg.active_rate_hz) & np.asarray(readout_mask, bool)
    score, f, _, _ = network_oscillation_score(win, mask, cfg.prominence)
    rep = GroupReplicate(members, int(seed), True, float(score), (f / dt if f > 0 else None), int(mask.sum()), float(cur),
                         n_runs, n_active, n_high, round(time.time() - t0, 2))
    if extras is not None:
        rep.extras = extras(traj)
    return rep
