"""Type-level activation screen: the locked single-candidate tuner, mirrored line for line.

`brainir.sim.screen.screen_candidate` (locked by the Phase 1 benchmark lock) stimulates ONE candidate neuron and auto-tunes
its current by bisection. `screen_group` below is the same procedure, statement for statement, with exactly one change:
the stimulus is a *set* of neurons (every member of a cell type) sharing one current. The lines that differ are marked
``# CHANGED``. With a single member it is the locked procedure (`tests/test_typescreen.py` checks equality on a synthetic
network and gate G1 checks it against the saved screen B0).

Everything after the tuning (the score of the accepted run) is computed exactly as in the locked code. Optional extra
read-outs (per-leg scores, phases, traces) are computed afterwards from the same accepted trajectory by a caller-supplied
function and never influence tuning or the main score.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
from brainir.metrics.rhythm import network_oscillation_score
from brainir.sim.model import ModelConfig, NeuronParams, Stimulus, Trajectory, simulate
from brainir.sim.screen import ScreenConfig, _classify

TYPESCREEN_ALGORITHM_ID = "brainir_ledger.typescreen.group_autotuned_v1 (mirror of brainir.sim.screen.autotuned_activation_v1)"


@dataclass
class GroupReplicate:
    members: tuple[int, ...]
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
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["members"] = list(self.members)
        return d


def screen_group(W: sp.csr_matrix, params: NeuronParams, model_cfg: ModelConfig, members: Sequence[int], readout_mask: np.ndarray,
                 *, seed: int, cfg: ScreenConfig | None = None,
                 extras: Callable[[Trajectory], dict] | None = None) -> GroupReplicate:
    cfg = cfg or ScreenConfig()
    t0 = time.time()
    cur = cfg.initial_current
    lo, hi = None, None  # bracket: last too-weak / too-strong amplitudes
    best = None
    n_runs = 0
    dt = model_cfg.dt_out
    members = tuple(int(m) for m in members)  # CHANGED: a set of neurons instead of one candidate index
    if not members:
        raise ValueError("a group needs at least one member")
    for _ in range(cfg.max_adjustment_iters):
        traj = simulate(W, params, model_cfg, Stimulus(members, (float(cur),)))  # CHANGED: every member at the same current
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
        return GroupReplicate(members, int(seed), False, None, None, None, float(cur), n_runs, n_active, n_high,
                              round(time.time() - t0, 2))
    traj, cur, n_active, n_high = best
    win = traj.window(cfg.analysis_start_s)
    peak = win.max(axis=0)
    mask = (peak > cfg.active_rate_hz) & np.asarray(readout_mask, bool)
    score, f, _, _ = network_oscillation_score(win, mask, cfg.prominence)
    rep = GroupReplicate(members, int(seed), True, float(score), (f / dt if f > 0 else None), int(mask.sum()), float(cur),
                         n_runs, n_active, n_high, round(time.time() - t0, 2))
    if extras is not None:  # read-outs of the accepted run only; they never feed back into tuning or the main score
        rep.extras = extras(traj)
    return rep


def fixed_run(W: sp.csr_matrix, params: NeuronParams, model_cfg: ModelConfig, stim_indices: Sequence[int], currents: Sequence[float],
              readout_mask: np.ndarray, *, cfg: ScreenConfig | None = None, extras: Callable[[Trajectory], dict] | None = None) -> dict:
    """One simulation at fixed currents (no tuning): the B4/B5 primitive. The score is computed exactly as for an accepted
    tuning run; the activity verdict is the tuner's classification, recorded for information."""
    cfg = cfg or ScreenConfig()
    t0 = time.time()
    traj = simulate(W, params, model_cfg, Stimulus(tuple(int(i) for i in stim_indices), tuple(float(c) for c in currents)))
    verdict, n_active, n_high = _classify(traj, cfg)
    win = traj.window(cfg.analysis_start_s)
    peak = win.max(axis=0)
    mask = (peak > cfg.active_rate_hz) & np.asarray(readout_mask, bool)
    score, f, _, _ = network_oscillation_score(win, mask, cfg.prominence)
    out = {"verdict": verdict, "n_active_all": n_active, "n_high_fr": n_high, "score": float(score),
           "frequency_hz": (f / model_cfg.dt_out if f > 0 else None), "n_active_readout": int(mask.sum()),
           "solver_success": bool(traj.info.get("success", True)), "wall_time_s": round(time.time() - t0, 2)}
    if extras is not None:
        out["extras"] = extras(traj)
    return out
