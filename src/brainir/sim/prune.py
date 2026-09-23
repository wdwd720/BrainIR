"""Stochastic pruning search for a minimal rhythm-sufficient subnetwork (independent re-implementation of the published
"computational sufficiency screen"; see research/literature/pugliese_model_spec_from_code.md section 7 for the
line-referenced original).

Algorithm (one screen = one parameter replicate, parameters frozen for all iterations)::

    state: removed (bool[N]), removed_by_draw, put_back, prev_put_back, level (round), last_good_*
    loop until converged or iteration cap:
        simulate with W masked to the active neurons (~removed | put_back); score = readout rhythmicity
        ACCEPT (score >= threshold): keep the previous draw; additionally prune every prunable neuron that was silent
            (peak rate <= 0 after the analysis start); draw the next candidate with p ~ 1 / max(rate, 1) among
            prunable & ~removed & ~put_back; if none is left -> new round (put_back := {} , level += 1)
        REJECT: restore the last drawn neuron (silent-pruned ones stay removed), add it to put_back, draw another
            candidate from the failed simulation's rates; if none is left -> new round
        converged := a round ended AND put_back == prev_put_back (nothing new could be removed) -> revert to the
            last accepted configuration

Differences from the original are deliberate and recorded in :data:`PRUNE_ALGORITHM_ID` notes: the stimulated neurons
are protected by default (``protect_stimulus=True``; the original could prune them), the RNG is NumPy's Generator seeded
per screen, and the reported circuit is BOTH the structural set (kept neurons) and the activity set (kept neurons active
in the final simulation) so that either published convention can be compared.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp

from ..metrics.rhythm import ACTIVE_RATE_HZ, DEFAULT_PROMINENCE, network_oscillation_score
from .model import Intervention, ModelConfig, NeuronParams, Stimulus, sample_neuron_params, simulate

PRUNE_ALGORITHM_ID = "brainir.sim.prune.stochastic_sufficiency_v1"


@dataclass
class PruneConfig:
    threshold: float = 0.5
    max_iterations: int = 200
    analysis_start_s: float = 0.25
    active_rate_hz: float = ACTIVE_RATE_HZ
    prominence: float = DEFAULT_PROMINENCE
    protect_stimulus: bool = True
    silent_prune: bool = True
    """Prune every prunable neuron whose peak rate is <= 0 in an accepted iteration (as in the original)."""

    def to_dict(self) -> dict:
        return {"algorithm": PRUNE_ALGORITHM_ID, **self.__dict__}


@dataclass
class PruneResult:
    seed: int
    converged: bool
    iterations: int
    n_simulations: int
    kept_positions: list[int]
    """Structural circuit: neurons never removed (or put back) at the end, excluding readout neurons."""
    active_kept_positions: list[int]
    """Activity circuit: kept neurons with peak rate > active_rate_hz in the final simulation, excluding readout."""
    final_score: float
    final_frequency_hz: float | None
    level: int
    history: list[dict] = field(default_factory=list)
    wall_time_s: float = 0.0

    def to_dict(self, *, history: bool = False) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "history"}
        if history:
            d["history"] = self.history
        return d


def _score(traj, readout_mask, cfg: PruneConfig, dt: float) -> tuple[float, float | None, np.ndarray]:
    win = traj.window(cfg.analysis_start_s)
    peak = win.max(axis=0)
    mask = (peak > cfg.active_rate_hz) & readout_mask
    score, f, _, _ = network_oscillation_score(win, mask, cfg.prominence)
    return score, (f / dt if f > 0 else None), peak


def _draw(rng: np.random.Generator, peak: np.ndarray, eligible: np.ndarray) -> int | None:
    """Removal probability ~ 1 / max(peak rate, 1) among eligible neurons (silent neurons weigh 1)."""
    if not eligible.any():
        return None
    w = 1.0 / np.where(peak > 0, peak, 1.0)
    w[~np.isfinite(w)] = 0.0
    w = np.where(eligible, w, 0.0)
    if w.sum() <= 0:
        return None
    return int(rng.choice(len(w), p=w / w.sum()))


def prune_screen(W: sp.csr_matrix, params: NeuronParams, model_cfg: ModelConfig, stimulus: Stimulus, readout_mask: np.ndarray,
                 prunable_mask: np.ndarray, *, seed: int, cfg: PruneConfig | None = None) -> PruneResult:
    """One pruning screen. ``prunable_mask`` marks neurons that may be removed (typically all non-readout neurons)."""
    cfg = cfg or PruneConfig()
    t0 = time.time()
    n = W.shape[0]
    rng = np.random.default_rng(seed)
    prunable = np.asarray(prunable_mask, bool).copy()
    prunable &= ~np.asarray(readout_mask, bool)
    if cfg.protect_stimulus:
        prunable[list(stimulus.indices)] = False
    removed = np.zeros(n, bool)
    removed_by_draw = np.zeros(n, bool)
    put_back = np.zeros(n, bool)
    prev_put_back = np.zeros(n, bool)
    last_removed = np.zeros(n, bool)
    level = 0
    last_good = None
    history = []
    converged = False
    n_sims = 0
    dt = model_cfg.dt_out
    for it in range(cfg.max_iterations):
        active = ~removed | put_back
        iv = Intervention(keep_only=tuple(np.flatnonzero(active)), always_keep=tuple(np.flatnonzero(readout_mask)))
        traj = simulate(W, params, model_cfg, stimulus, iv)
        n_sims += 1
        score, freq, peak = _score(traj, readout_mask, cfg, dt)
        eligible_now = prunable & ~removed & ~put_back
        need_new_round = not eligible_now.any()
        converged_now = need_new_round and np.array_equal(put_back, prev_put_back) and (level > 0 or put_back.any() or removed.any())
        good = score >= cfg.threshold and np.isfinite(score)
        rec = {"iteration": it, "score": round(float(score), 6), "frequency_hz": freq, "n_removed": int(removed.sum()),
               "n_put_back": int(put_back.sum()), "level": level, "accepted": bool(good)}
        if good:
            last_good = {"removed": removed.copy(), "put_back": put_back.copy(), "score": score, "freq": freq, "peak": peak.copy()}
            if cfg.silent_prune:
                newly_silent = prunable & (peak <= 0) & ~removed & ~put_back
                removed |= newly_silent
            eligible = prunable & ~removed & ~put_back
            j = _draw(rng, peak, eligible)
            last_removed = newly_silent.copy() if cfg.silent_prune else np.zeros(n, bool)
            if j is not None:
                removed[j] = True
                removed_by_draw[j] = True
                last_removed[j] = True
                rec["drawn"] = int(j)
            else:
                prev_put_back = put_back.copy()
                put_back = np.zeros(n, bool)
                level += 1
                rec["new_round"] = True
        else:
            restore = last_removed & removed_by_draw
            put_back_before = put_back.copy()
            removed &= ~restore
            removed_by_draw &= ~restore
            put_back |= restore
            eligible = prunable & ~removed & ~put_back
            j = _draw(rng, peak, eligible)
            last_removed = np.zeros(n, bool)
            if j is not None:
                removed[j] = True
                removed_by_draw[j] = True
                last_removed[j] = True
                rec["drawn"] = int(j)
            else:
                # round over: remember the put-back set WITHOUT the neuron restored in this step, so that the next round
                # is recognised as identical when it again fails on exactly the same neurons (original semantics)
                prev_put_back = put_back_before
                put_back = np.zeros(n, bool)
                level += 1
                rec["new_round"] = True
        history.append(rec)
        if converged_now:
            converged = True
            break
    # final configuration: the last accepted one (or the current state if nothing was ever accepted)
    if last_good is not None:
        removed, put_back = last_good["removed"], last_good["put_back"]
    active = ~removed | put_back
    iv = Intervention(keep_only=tuple(np.flatnonzero(active)), always_keep=tuple(np.flatnonzero(readout_mask)))
    traj = simulate(W, params, model_cfg, stimulus, iv)
    n_sims += 1
    score, freq, peak = _score(traj, readout_mask, cfg, dt)
    kept = np.flatnonzero(active & ~np.asarray(readout_mask, bool))
    active_kept = [int(i) for i in kept if peak[i] > cfg.active_rate_hz]
    return PruneResult(seed=int(seed), converged=converged, iterations=len(history), n_simulations=n_sims,
                       kept_positions=[int(i) for i in kept], active_kept_positions=active_kept, final_score=float(score),
                       final_frequency_hz=freq, level=level, history=history, wall_time_s=round(time.time() - t0, 2))


def run_prune_job(args) -> PruneResult:
    """Backend-friendly entry point: args = (W, model_cfg, stimulus, readout_mask, prunable_mask, sizes, seed, prune_cfg)."""
    W, model_cfg, stimulus, readout_mask, prunable_mask, sizes, seed, prune_cfg = args
    params = sample_neuron_params(model_cfg, W.shape[0], int(seed), sizes)
    return prune_screen(W, params, model_cfg, stimulus, readout_mask, prunable_mask, seed=int(seed), cfg=prune_cfg)
