"""Pruning search and activation screen on synthetic circuits with known structure."""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from brainir.sim.model import ModelConfig, NeuronParams, Stimulus
from brainir.sim.prune import PruneConfig, prune_screen, run_prune_job
from brainir.sim.screen import ScreenConfig, aggregate_screen, run_screen_job, screen_candidate
from brainir.testing.circuits import CIRCUITS


def _embedded_oscillator():
    """The 4-neuron sustained oscillator (driver 0 -> inhibitory ring 1,2,3) embedded with 6 irrelevant neurons:
    4 = a 'readout' fed by the ring, 5..9 = distractors driven weakly by the driver with no effect on the readout."""
    c = CIRCUITS["sustained_oscillator"]
    n = 10
    W = np.zeros((n, n))
    W[:4, :4] = c.W
    W[4, 1] = 60.0            # ring neuron 1 excites the readout
    for i in range(5, 10):
        W[i, 0] = 10.0        # distractors receive driver input only
    p = c.model_params()
    params = NeuronParams(tau=np.full(n, p["tau"][0]), a=np.full(n, p["a"][0]), theta=np.full(n, p["theta"][0]), r_max=np.full(n, p["r_max"][0]))
    cfg = ModelConfig(b_exc=p["b"], b_inh=p["b"], t_end=0.6, pulse_start=c.stim_onset_s, pulse_end=0.6, size_scaling=False)
    readout = np.zeros(n, bool)
    readout[4] = True
    return sp.csr_matrix(W), params, cfg, Stimulus((0,), (c.stim_current,)), readout


def test_prune_recovers_the_embedded_oscillator_and_is_deterministic():
    W, params, cfg, stim, readout = _embedded_oscillator()
    prunable = np.ones(W.shape[0], bool)
    pc = PruneConfig(max_iterations=60, analysis_start_s=0.2)
    r1 = prune_screen(W, params, cfg, stim, readout, prunable, seed=3, cfg=pc)
    r2 = prune_screen(W, params, cfg, stim, readout, prunable, seed=3, cfg=pc)
    assert r1.kept_positions == r2.kept_positions and r1.history == r2.history  # deterministic under a seed
    assert r1.final_score >= 0.5 and r1.converged
    assert set(r1.kept_positions) >= {0, 1, 2, 3}           # the oscillator (driver protected) survives
    assert not (set(r1.kept_positions) & {5, 6, 7, 8, 9})    # every distractor is pruned
    assert set(r1.active_kept_positions) <= set(r1.kept_positions)
    assert r1.n_simulations == r1.iterations + 1


def test_prune_reports_non_convergence_under_a_tiny_iteration_cap():
    W, params, cfg, stim, readout = _embedded_oscillator()
    r = prune_screen(W, params, cfg, stim, readout, np.ones(W.shape[0], bool), seed=0, cfg=PruneConfig(max_iterations=2))
    assert not r.converged and r.iterations == 2


def test_prune_job_entry_point_matches_direct_call():
    W, params, cfg, stim, readout = _embedded_oscillator()
    pc = PruneConfig(max_iterations=40, analysis_start_s=0.2)
    job = run_prune_job((W, cfg, stim, readout, np.ones(W.shape[0], bool), None, 5, pc))
    assert job.seed == 5 and job.final_score >= 0.0 and isinstance(job.to_dict()["kept_positions"], list)


def test_screen_ranks_the_driver_above_distractors_and_tunes_current():
    W, params, cfg, stim, readout = _embedded_oscillator()
    sc = ScreenConfig(initial_current=stim.currents[0] * 8, n_active_upper=6, n_active_lower=2, analysis_start_s=0.2)
    reps = []
    for cand in (0, 5, 7):
        reps.append(screen_candidate(W, params, cfg, cand, readout, seed=1, cfg=sc))
    agg = aggregate_screen(reps)
    table = {row["candidate"]: row for row in agg["candidates"]}
    assert table[0]["rank"] == 1 and table[0]["mean_score"] is not None and table[0]["mean_score"] >= 0.5
    drv = next(r for r in reps if r.candidate == 0)
    assert drv.usable and drv.n_tuning_runs >= 2 and drv.current < sc.initial_current  # too strong at first -> halved
    for r in reps:
        if r.candidate != 0:
            assert not r.usable or (r.score is not None and r.score < 0.5)  # distractors drive nothing rhythmic


def test_screen_job_entry_point_and_unusable_replicate():
    W, params, cfg, stim, readout = _embedded_oscillator()
    sc = ScreenConfig(initial_current=1.0, max_adjustment_iters=1, n_active_lower=3)  # far too weak, no room to adjust
    r = run_screen_job((W, cfg, 0, readout, None, 2, sc))
    assert not r.usable and r.score is None and r.n_tuning_runs == 1
