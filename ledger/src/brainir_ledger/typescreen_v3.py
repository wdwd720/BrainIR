"""Run 3 group screen (PREREG v3 P1): run 1's frozen `typescreen.screen_group` (the LOG L14 procedure), copied line for line,
with read-out additions only. Nothing added here feeds back into tuning, acceptance, the score or any field of run 1's result:

- every replicate records the current of its last simulated run (`final_current`) and that run's classification
  (`final_verdict`: `ok`, `weak` or `strong`); run 1's `current` field is unchanged (for a replicate that is never accepted it is
  the next, untried current, as before);
- a replicate that is never accepted also stores the read-outs of its last simulated run (`final_run_extras`, same read-out
  function as an accepted run), outside run 1's `extras` field, so run 1's digest is unchanged.

Tested against the frozen function on accepted, too-weak and saturating synthetic circuits (`tests/test_typescreen_v3.py`).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
import scipy.sparse as sp
from brainir.metrics.rhythm import network_oscillation_score
from brainir.sim.model import ModelConfig, NeuronParams, Stimulus, Trajectory, simulate
from brainir.sim.screen import ScreenConfig

from .typescreen import GroupReplicate, _classify


@dataclass
class GroupReplicateV3(GroupReplicate):
    final_current: float | None = None
    final_verdict: str | None = None
    final_run_extras: dict | None = None


def screen_group_v3(W: sp.csr_matrix, params: NeuronParams, model_cfg: ModelConfig, members: Sequence[int], readout_mask: np.ndarray,
                    *, seed: int, cfg: ScreenConfig | None = None,
                    extras: Callable[[Trajectory], dict] | None = None) -> GroupReplicateV3:
    cfg = cfg or ScreenConfig()
    t0 = time.time()
    cur = cfg.initial_current
    lo, hi = None, None  # bracket: last too-weak / too-strong amplitudes
    best = None
    n_runs = 0
    dt = model_cfg.dt_out
    members = tuple(int(m) for m in members)
    if not members:
        raise ValueError("a group needs at least one member")
    traj, last_cur, verdict = None, None, None  # ADDED (v3): the last simulated run
    for _ in range(cfg.max_adjustment_iters):
        traj = simulate(W, params, model_cfg, Stimulus(members, (float(cur),)))
        last_cur = float(cur)  # ADDED (v3)
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
        rep = GroupReplicateV3(members, int(seed), False, None, None, None, float(cur), n_runs, n_active, n_high,
                               round(time.time() - t0, 2))
        rep.final_current, rep.final_verdict = last_cur, verdict  # ADDED (v3)
        if extras is not None:  # ADDED (v3): read-outs of the last simulated run, outside run 1's `extras`
            rep.final_run_extras = extras(traj)
        return rep
    traj, cur, n_active, n_high = best
    win = traj.window(cfg.analysis_start_s)
    peak = win.max(axis=0)
    mask = (peak > cfg.active_rate_hz) & np.asarray(readout_mask, bool)
    score, f, _, _ = network_oscillation_score(win, mask, cfg.prominence)
    rep = GroupReplicateV3(members, int(seed), True, float(score), (f / dt if f > 0 else None), int(mask.sum()), float(cur),
                           n_runs, n_active, n_high, round(time.time() - t0, 2))
    rep.final_current, rep.final_verdict = float(cur), "ok"  # ADDED (v3)
    if extras is not None:  # read-outs of the accepted run only; they never feed back into tuning or the main score
        rep.extras = extras(traj)
    return rep
