"""BrainIR's rate-model simulator against the independent reference integrator and closed-form fixtures."""

from __future__ import annotations

import numpy as np
import pytest
import scipy.sparse as sp

from brainir.metrics.rhythm import network_oscillation_score
from brainir.sim import (
    Intervention,
    ModelConfig,
    NeuronParams,
    Stimulus,
    sample_neuron_params,
    sample_trunc_normal,
    simulate,
    size_scaling,
)
from brainir.sim.model import apply_intervention, mean_neuron_params, scaled_weights
from brainir.testing.circuits import CIRCUITS, reference_simulate


def _params(circuit) -> NeuronParams:
    p = circuit.model_params()
    return NeuronParams(tau=p["tau"], a=p["a"], theta=p["theta"], r_max=p["r_max"])


def _config(circuit, **over) -> ModelConfig:
    b = circuit.model_params()["b"]
    return ModelConfig(b_exc=b, b_inh=b, t_end=circuit.t_end, pulse_start=circuit.stim_onset_s, pulse_end=circuit.t_end,
                       size_scaling=False, **over)


@pytest.mark.parametrize("name", sorted(CIRCUITS))
def test_simulate_matches_reference_integrator(name):
    c = CIRCUITS[name]
    t_ref, r_ref = reference_simulate(c)
    traj = simulate(c.W, _params(c), _config(c), Stimulus(c.stim_neurons, (c.stim_current,)))
    assert traj.r.shape == r_ref.shape and np.allclose(traj.t, t_ref)
    assert traj.info["success"]
    assert np.all(np.isfinite(traj.r)) and traj.r.min() >= 0
    tol = 0.02 * max(1.0, r_ref.max())  # two independent RK45 runs of the same ODE at rtol 2e-6
    assert np.abs(traj.r - r_ref).max() < tol, np.abs(traj.r - r_ref).max()


@pytest.mark.parametrize("name", [n for n, c in CIRCUITS.items() if c.expected.get("steady_state_hz") is not None])
def test_fixed_point_circuits_reach_their_closed_form_steady_states(name):
    c = CIRCUITS[name]
    traj = simulate(c.W, _params(c), _config(c), Stimulus(c.stim_neurons, (c.stim_current,)))
    t0, t1 = c.expected["analysis_window_s"]
    late = traj.window(t0, t1)[-1]
    for k, ss in zip(c.expected["readout_neurons"], c.expected["steady_state_hz"]):
        assert abs(late[k] - ss) <= 0.02 * max(1.0, abs(ss)), (k, late[k], ss)


@pytest.mark.parametrize("name", [n for n, c in CIRCUITS.items() if c.expected.get("is_rhythmic")])
def test_sustained_oscillators_have_the_expected_frequency(name):
    c = CIRCUITS[name]
    traj = simulate(c.W, _params(c), _config(c), Stimulus(c.stim_neurons, (c.stim_current,)))
    t0, t1 = c.expected["analysis_window_s"]
    m = (traj.t >= t0 - 1e-9) & (traj.t <= t1 + 1e-9)
    mask = np.zeros(c.n, bool)
    mask[list(c.expected["readout_neurons"])] = True
    score, f, _, _ = network_oscillation_score(traj.r[m], mask)
    assert score >= 0.9
    assert abs(f / 1e-3 - c.expected["frequency_hz"]) <= c.expected["frequency_tol_hz"]


def test_single_and_segment_integration_agree_and_rk4_converges():
    c = CIRCUITS["sustained_oscillator"]
    stim = Stimulus(c.stim_neurons, (c.stim_current,))
    a = simulate(c.W, _params(c), _config(c), stim)
    b = simulate(c.W, _params(c), _config(c, integration="single"), stim)
    assert np.abs(a.r - b.r).max() < 2.0
    fine = simulate(c.W, _params(c), _config(c, method="rk4", dt=1e-4), stim)
    coarse = simulate(c.W, _params(c), _config(c, method="rk4", dt=1e-3), stim)
    assert np.abs(fine.r - a.r).max() < np.abs(coarse.r - a.r).max()  # halving/finer steps move towards the adaptive solution
    assert np.abs(fine.r - a.r).max() < 1.0


def test_simulation_is_deterministic_and_seeded_params_are_reproducible():
    c = CIRCUITS["ei_pair_oscillator"]
    cfg = _config(c)
    p1 = sample_neuron_params(cfg, c.n, seed=5)
    p2 = sample_neuron_params(cfg, c.n, seed=5)
    p3 = sample_neuron_params(cfg, c.n, seed=6)
    assert np.array_equal(p1.tau, p2.tau) and not np.array_equal(p1.tau, p3.tau)
    stim = Stimulus(c.stim_neurons, (c.stim_current,))
    assert np.array_equal(simulate(c.W, p1, cfg, stim).r, simulate(c.W, p2, cfg, stim).r)


def test_trunc_normal_respects_bounds_and_moments():
    rng = np.random.default_rng(0)
    x = sample_trunc_normal(rng, 7.5, 0.6, (200_000,))
    assert x.min() >= 7.5 - 10 * 0.6 and x.max() <= 7.5 + 10 * 0.6
    assert abs(x.mean() - 7.5) < 0.01 and abs(x.std() - 0.6) < 0.01
    tau = sample_trunc_normal(rng, 0.02, 0.002, (200_000,))
    assert tau.min() >= 0.0 and abs(tau.mean() - 0.02) < 1e-4
    eta = sample_trunc_normal(rng, 0.0, 0.5, (100_000,), lower=-1.0)
    assert eta.min() >= -1.0  # weight noise can zero a synapse but never flips its sign
    assert np.all(sample_trunc_normal(rng, 1.0, 0.0, (5,)) == 1.0)


def test_size_scaling_divides_gain_and_multiplies_threshold():
    sizes = np.array([1.0, 2.0, 4.0, np.nan, 0.0])
    s = size_scaling(sizes, 5)
    # the authors take the nanmedian BEFORE replacing zeros (median of [0, 1, 2, 4] = 1.5); NaN and 0 -> median (s = 1)
    assert np.allclose(s, [1 / 1.5, 2 / 1.5, 4 / 1.5, 1.0, 1.0])
    cfg = ModelConfig()
    p = mean_neuron_params(cfg, 5, sizes)
    assert np.allclose(p.a, cfg.a_mean / s) and np.allclose(p.theta, cfg.theta_mean * s)


def test_interventions_mask_rows_and_columns_before_scaling():
    W = sp.csr_matrix(np.array([[0, 10, -5], [4, 0, 0], [0, 7, 0]], dtype=float))
    M = apply_intervention(W, Intervention(silence=(1,))).toarray()
    assert M[1].sum() == 0 and M[:, 1].sum() == 0 and M[0, 2] == -5 and M[2].sum() == 0
    K = apply_intervention(W, Intervention(keep_only=(0,), always_keep=(2,))).toarray()
    assert K[0, 2] == -5 and K[0, 1] == 0 and K[1].sum() == 0
    cfg = ModelConfig(b_exc=0.03, b_inh=0.03)
    Wb = scaled_weights(W, cfg).toarray()
    assert Wb[0, 1] == pytest.approx(0.3) and Wb[0, 2] == pytest.approx(-0.15)
    noisy = apply_intervention(W, Intervention(weight_noise_sd=0.2, weight_noise_seed=1)).toarray()
    assert np.all(np.sign(noisy) == np.sign(W.toarray())) and not np.allclose(noisy, W.toarray())
    assert np.array_equal(apply_intervention(W, None).toarray(), W.toarray())


def test_silencing_changes_dynamics_and_zero_input_network_stays_silent():
    c = CIRCUITS["sustained_oscillator"]
    stim = Stimulus(c.stim_neurons, (c.stim_current,))
    base = simulate(c.W, _params(c), _config(c), stim)
    cut = simulate(c.W, _params(c), _config(c), stim, Intervention(silence=(1,)))
    assert cut.r[:, 1].max() == 0.0 and np.abs(cut.r - base.r).max() > 10
    quiet = simulate(c.W, _params(c), _config(c), Stimulus(c.stim_neurons, (0.0,)))
    assert quiet.r.max() == 0.0


def test_fixed_step_schemes_keep_their_order_across_a_mid_step_pulse_edge():
    """One uncoupled neuron with a constant input has the closed form r(t) = r_inf (1 - exp(-(t - t_on)/tau)).

    With the pulse edge inside a step (t_on = 20.5 ms on a 1 ms grid) a naive RK4 whose k4 stage sees the other side
    of the switch is first-order accurate (~0.1 Hz error); the segment-wise scheme must stay far below that."""
    tau, a, theta, r_max, current = 0.02, 1.0, 7.5, 200.0, 40.0
    p = NeuronParams(tau=np.array([tau]), a=np.array([a]), theta=np.array([theta]), r_max=np.array([r_max]))
    W = sp.csr_matrix((1, 1))
    t_on = 0.0205
    cfg = ModelConfig(t_end=0.2, pulse_start=t_on, pulse_end=0.2, size_scaling=False, method="rk4", dt=1e-3)
    traj = simulate(W, p, cfg, Stimulus((0,), (current,)))
    r_inf = r_max * np.tanh((a / r_max) * (current - theta))
    exact = np.where(traj.t >= t_on, r_inf * (1 - np.exp(-(np.maximum(traj.t - t_on, 0.0)) / tau)), 0.0)
    assert np.abs(traj.r[:, 0] - exact).max() < 2e-3
    e = simulate(W, p, ModelConfig(**{**cfg.to_dict(), "method": "euler", "dt": 1e-4}), Stimulus((0,), (current,)))
    assert np.abs(e.r[:, 0] - exact).max() < 0.2


def test_stimulus_validation():
    with pytest.raises(ValueError):
        Stimulus((0, 1), (1.0, 2.0, 3.0))
    with pytest.raises(IndexError):
        Stimulus((5,), (1.0,)).vector(3)
    assert Stimulus((0, 2), (10.0,)).vector(3).tolist() == [10.0, 0.0, 10.0]
