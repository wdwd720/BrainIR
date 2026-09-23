"""Pure functions of the benchmark's robustness / negative-control script (benchmarks/dng100_walking_cpg/robustness_experiments.py).

Real-data-free: the control generators are exercised on small synthetic circuits from ``brainir.testing.circuits`` and on a
seeded random signed matrix; ``paper_network`` is never called.
"""

from __future__ import annotations

import sys
from collections import Counter

import numpy as np
import pytest
import scipy.sparse as sp

from brainir import paths
from brainir.sim import ModelConfig, NeuronParams, Stimulus, simulate
from brainir.sim.experiments import score_trajectory
from brainir.testing.circuits import CIRCUITS

sys.path.insert(0, str(paths.repo_root() / "benchmarks" / "dng100_walking_cpg"))
import robustness_experiments as rx  # noqa: E402


def _random_signed(n: int = 40, density: float = 0.15, seed: int = 3) -> sp.csr_matrix:
    rng = np.random.default_rng(seed)
    sign = np.where(rng.random(n) < 0.6, 1.0, -1.0)
    mask = rng.random((n, n)) < density
    np.fill_diagonal(mask, False)
    counts = rng.integers(5, 60, size=(n, n))
    W = sp.csr_matrix(mask * counts * sign[None, :])
    W.eliminate_zeros()
    return W


def _in_deg(W):
    return np.diff(sp.csr_matrix(W).indptr)


def _out_deg(W):
    return np.diff(sp.csc_matrix(W).indptr)


def _labels(n: int, signs: np.ndarray) -> np.ndarray:
    lab = np.where(signs > 0, "exc_in", "inh_in").astype(object)
    lab[0] = "exc_dn"
    lab[-2:] = "mn"
    return lab.astype(str)


def test_paper_shuffle_classes_follow_the_five_group_rule():
    sc = np.array(["descending_neuron", "descending_neuron", "intrinsic_neuron", "ascending_neuron", "motor_neuron", "sensory_neuron"])
    signs = np.array([1, -1, 1, 0, -1, -1])
    lab = rx.paper_shuffle_classes(sc, signs)
    assert lab.tolist() == ["exc_dn", "inh_dn", "exc_in", "inh_in", "mn", "inh_in"]


def test_class_shuffle_preserves_per_class_in_degree_multisets_columns_and_values():
    W = _random_signed()
    n = W.shape[0]
    labels = _labels(n, rx.column_signs(W))
    S = rx.class_shuffle(W, labels, seed=7)
    assert S.shape == W.shape and S.nnz == W.nnz
    for lab in np.unique(labels):
        idx = labels == lab
        assert Counter(_in_deg(W)[idx].tolist()) == Counter(_in_deg(S)[idx].tolist()), lab
        # the multiset of complete input vectors within the class is preserved (rows are moved as units)
        rows_w = sorted(tuple(r) for r in W[np.flatnonzero(idx)].toarray().tolist())
        rows_s = sorted(tuple(r) for r in S[np.flatnonzero(idx)].toarray().tolist())
        assert rows_w == rows_s, lab
    # every presynaptic column keeps its out-degree, sign and count multiset
    assert np.array_equal(_out_deg(W), _out_deg(S))
    assert np.array_equal(rx.column_signs(W), rx.column_signs(S))
    Wc, Sc = sp.csc_matrix(W), sp.csc_matrix(S)
    for j in range(n):
        assert Counter(Wc.data[Wc.indptr[j]:Wc.indptr[j + 1]].tolist()) == Counter(Sc.data[Sc.indptr[j]:Sc.indptr[j + 1]].tolist())
    assert (S != W).nnz > 0  # it did change something


def test_degree_preserving_rewire_preserves_degree_sequences_signs_and_counts():
    W = _random_signed()
    R, stats = rx.degree_preserving_rewire(W, seed=11, swaps_per_edge=10.0, return_stats=True)
    assert R.shape == W.shape and R.nnz == W.nnz
    assert np.array_equal(_in_deg(W), _in_deg(R))
    assert np.array_equal(_out_deg(W), _out_deg(R))
    assert np.array_equal(rx.column_signs(W), rx.column_signs(R))
    assert Counter(np.abs(W.data).tolist()) == Counter(np.abs(R.data).tolist())
    assert np.count_nonzero(R.diagonal()) == 0
    assert stats["n_edges"] == W.nnz and stats["n_attempted"] == 10 * W.nnz and 0 < stats["n_swapped"] <= stats["n_attempted"]
    assert (R != W).nnz > 0
    # each count stays with its presynaptic neuron: per-column count multisets are unchanged
    Wc, Rc = sp.csc_matrix(W), sp.csc_matrix(R)
    for j in range(W.shape[0]):
        assert Counter(Wc.data[Wc.indptr[j]:Wc.indptr[j + 1]].tolist()) == Counter(Rc.data[Rc.indptr[j]:Rc.indptr[j + 1]].tolist())


def test_sign_shuffle_preserves_sign_counts_magnitudes_and_fixed_columns():
    W = _random_signed()
    cs = rx.column_signs(W)
    S = rx.sign_shuffle(W, seed=5, fixed=(0,))
    ns = rx.column_signs(S)
    assert Counter(cs.tolist()) == Counter(ns.tolist())
    assert ns[0] == cs[0]
    assert (abs(S) != abs(W)).nnz == 0  # same pattern, same counts
    assert (ns != cs).any()
    # every column single-signed (column_signs raises otherwise) and zero columns stay zero
    assert np.array_equal(ns == 0, cs == 0)


def test_permute_weights_preserves_pattern_signs_and_count_multiset():
    W = _random_signed()
    P = rx.permute_weights(W, seed=2)
    W.sort_indices()
    assert np.array_equal(P.indices, W.indices) and np.array_equal(P.indptr, W.indptr)
    assert np.array_equal(np.sign(P.data), np.sign(W.data))
    assert Counter(np.abs(P.data).tolist()) == Counter(np.abs(W.data).tolist())
    assert not np.array_equal(P.data, W.data)


@pytest.mark.parametrize("kind", [k for k in rx.CONTROLS if k != "intact"])
def test_controls_are_deterministic_under_a_seed_and_never_mutate_the_input(kind):
    W = _random_signed()
    before = W.copy()
    labels = _labels(W.shape[0], rx.column_signs(W))
    kw = {"labels": labels} if kind == "class_shuffle" else {}
    A, _ = rx.build_control(W, kind, 42, **kw)
    B, _ = rx.build_control(W, kind, 42, **kw)
    C, _ = rx.build_control(W, kind, 43, **kw)
    assert (A != B).nnz == 0
    assert (A != C).nnz > 0
    assert (W != before).nnz == 0


@pytest.mark.parametrize("kind", rx.CONTROLS)
@pytest.mark.parametrize("name", ["sustained_oscillator", "delayed_inhibitory_oscillator", "feedforward_chain"])
def test_tiny_synthetic_networks_run_through_every_control(kind, name):
    c = CIRCUITS[name]
    assert c.n <= 10
    W = sp.csr_matrix(c.W)
    labels = np.array(["exc_dn"] + ["inh_in" if s < 0 else "exc_in" for s in rx.column_signs(W)[1:-1]] + ["mn"])
    kw = {"class_shuffle": {"labels": labels}, "sign_shuffle": {"fixed": tuple(c.stim_neurons)}}.get(kind, {})
    Wc, _ = rx.build_control(W, kind, 1, **kw)
    p = c.model_params()
    params = NeuronParams(tau=p["tau"], a=p["a"], theta=p["theta"], r_max=p["r_max"], seed=1)
    cfg = ModelConfig(b_exc=p["b"], b_inh=p["b"], t_end=0.3, pulse_start=c.stim_onset_s, size_scaling=False)
    traj = simulate(Wc, params, cfg, Stimulus(c.stim_neurons, (c.stim_current,)))
    assert traj.info["success"] and np.all(np.isfinite(traj.r))
    readout = np.zeros(c.n, dtype=bool)
    readout[-1] = True
    sc = score_trajectory(traj, readout)
    ext = rx.readout_persistence(traj, readout)
    assert 0.0 <= sc["score"] <= 1.0 and ext["n_sustained_readout"] in (0, 1)
    rep = {**{k: v for k, v in sc.items() if k not in ("peak_rates", "readout_scores", "readout_frequencies_hz")}, **ext,
           "seed": 1, "solver_success": True, "wall_time_s": 0.0}
    s = rx.summarize([rep, rep])
    assert s["n_replicates"] == 2 and 0.0 <= s["fraction_ge_threshold"] <= 1.0


def test_convergence_orders_recover_a_known_power_law():
    rows = [{"family": "rk4", "method": f"RK4 dt {dt:g}", "e": 3.0 * dt**4} for dt in (1e-3, 5e-4, 2.5e-4)]
    o = rx.convergence_orders(rows, "rk4", "e")
    assert o["dts"] == [1e-3, 5e-4, 2.5e-4]
    assert np.allclose(o["orders"], [4.0, 4.0])
    rows = [{"family": "euler", "method": f"Euler dt {dt:g}", "e": 0.7 * dt} for dt in (1e-3, 1e-4)]
    assert np.allclose(rx.convergence_orders(rows, "euler", "e")["orders"], [1.0])


def test_param_conditions_merge_the_shared_default_and_scale_all_sds():
    base = ModelConfig()
    conds = rx.param_conditions(base, rx.PARAM_FAMILIES)
    labels = [c["label"] for c in conds]
    assert len(labels) == len(set(labels))
    default = [c for c in conds if c["_cfg"] == base]
    assert len(default) == 1 and set(default[0]["aliases"]) == {"a=1", "theta=7.5", "r_max=200", "tau=0.02", "b=0.03"}
    w3 = next(c for c in conds if c["label"] == "widen=3")
    assert np.allclose((w3["_cfg"].tau_sd, w3["_cfg"].a_sd, w3["_cfg"].theta_sd, w3["_cfg"].r_max_sd), (0.006, 0.3, 1.8, 30.0))
    assert sum(len(v) for v in rx.PARAM_FAMILIES.values()) - 5 == len(conds)
