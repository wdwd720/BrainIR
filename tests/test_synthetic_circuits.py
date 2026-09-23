"""Every synthetic circuit's ``expected`` claims must hold on the reference RK45 simulation.

The simple criteria implemented here (steady state within 2 %, sustained vs damped oscillation by amplitude
persistence, frequency by FFT peak and by inter-peak intervals) are what BrainIR's own simulator will be held
to as well. All simulations run once per module (about 2 s in total).
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from brainir.testing.circuits import (
    BEHAVIORS,
    CIRCUITS,
    DEFAULT_PARAMS,
    MODEL_PARAM_KEYS,
    SyntheticCircuit,
    get_circuit,
    rate_function,
    reference_simulate,
)

R_MAX = DEFAULT_PARAMS["r_max"]
RATE_FLOOR = -1e-2  # RK45 can undershoot 0 Hz slightly at the rectification kink; never by more than this
REQUIRED_EXPECTED_KEYS = {"behavior", "is_rhythmic", "frequency_hz", "frequency_tol_hz", "readout_neurons", "analysis_window_s"}
OSCILLATORS = sorted(n for n, c in CIRCUITS.items() if c.expected["is_rhythmic"])
NON_OSCILLATORS = sorted(n for n, c in CIRCUITS.items() if not c.expected["is_rhythmic"])
WITH_STEADY_STATE = sorted(n for n, c in CIRCUITS.items() if c.expected.get("steady_state_hz") is not None)


@pytest.fixture(scope="module")
def sims() -> dict[str, tuple[np.ndarray, np.ndarray]]:
    return {name: reference_simulate(c) for name, c in CIRCUITS.items()}


# --------------------------------------------------------------------------------------------------
# analysis helpers (deliberately simple and robust)
# --------------------------------------------------------------------------------------------------

def _window(t, r, circuit: SyntheticCircuit):
    t0, t1 = circuit.expected["analysis_window_s"]
    m = (t >= t0 - 1e-12) & (t <= t1 + 1e-12)
    return t[m], r[m]


def _fft_frequency(t, x) -> float:
    """Hann-windowed FFT peak with parabolic interpolation (ignores DC)."""
    n = len(x)
    spec = np.abs(np.fft.rfft((x - x.mean()) * np.hanning(n)))
    freqs = np.fft.rfftfreq(n, d=t[1] - t[0])
    spec[0] = 0.0
    k = int(np.argmax(spec))
    if 1 <= k < len(spec) - 1 and spec[k - 1] > 0 and spec[k + 1] > 0:
        a, b, c = np.log(spec[k - 1]), np.log(spec[k]), np.log(spec[k + 1])
        return float(freqs[k] + 0.5 * (a - c) / (a - 2 * b + c) * (freqs[1] - freqs[0]))
    return float(freqs[k])


def _peaks(x, threshold) -> np.ndarray:
    return np.flatnonzero((x[1:-1] > x[:-2]) & (x[1:-1] >= x[2:]) & (x[1:-1] > threshold)) + 1


def _interval_frequency(t, x) -> float:
    pk = _peaks(x, x.mean())
    assert len(pk) >= 3, "need at least three peaks above the mean"
    return float(1.0 / np.mean(np.diff(t[pk])))


def _is_sustained(x, min_amplitude_hz=5.0) -> bool:
    """Peak-to-trough amplitude stays put across thirds of the window and is not negligible."""
    thirds = [np.ptp(v) for v in np.array_split(x, 3)]
    return thirds[0] > min_amplitude_hz and min(thirds) >= 0.8 * max(thirds)


def _assert_close_rate(measured, expected_value, rel=0.02, abs_floor=0.5):
    assert abs(measured - expected_value) <= max(rel * abs(expected_value), abs_floor), (measured, expected_value)


# --------------------------------------------------------------------------------------------------
# registry / schema
# --------------------------------------------------------------------------------------------------

def test_registry_is_consistent():
    assert set(CIRCUITS) >= {"fixed_point_single", "feedforward_chain", "recurrent_excitation_saturating", "bistable_pair",
                             "damped_oscillator", "sustained_oscillator", "delayed_inhibitory_oscillator", "noisy_oscillator",
                             "random_recurrent"}
    assert get_circuit("bistable_pair") is CIRCUITS["bistable_pair"]
    with pytest.raises(KeyError):
        get_circuit("nope")
    for name, c in CIRCUITS.items():
        assert c.name == name
        assert c.W.dtype == np.float64 and c.W.ndim == 2 and c.W.shape[0] == c.W.shape[1] == c.n
        assert not c.W.flags.writeable
        assert np.isfinite(c.W).all()
        for j in range(c.n):  # one sign per presynaptic neuron
            col = c.W[:, j]
            assert not ((col > 0).any() and (col < 0).any()), (name, j)
        assert c.stim_neurons and all(0 <= i < c.n for i in c.stim_neurons)
        assert c.stim_current > 0 and c.t_end > c.stim_onset_s >= 0
        e = c.expected
        assert REQUIRED_EXPECTED_KEYS <= set(e), (name, set(e))
        assert e["behavior"] in BEHAVIORS
        assert all(0 <= i < c.n for i in e["readout_neurons"])
        t0, t1 = e["analysis_window_s"]
        assert c.stim_onset_s <= t0 < t1 <= c.t_end
        assert (e["frequency_hz"] is None) == (not e["is_rhythmic"]) == (e["frequency_tol_hz"] is None)
        if e["is_rhythmic"]:
            assert e["behavior"] == "sustained_oscillation" and 0 < e["frequency_tol_hz"] <= 0.15 * e["frequency_hz"]
            assert len(e["amplitude_hz"]) == len(e["readout_neurons"])
        for k in c.params:
            if k in MODEL_PARAM_KEYS:
                np.broadcast_to(np.asarray(c.params[k], dtype=float), (c.n,))
        assert c.description


def test_model_params_broadcast_and_overrides():
    c = CIRCUITS["feedforward_chain"]
    p = c.model_params()
    for k in ("tau", "a", "theta", "r_max"):
        assert p[k].shape == (5,) and np.all(p[k] == DEFAULT_PARAMS[k])
    assert p["b"] == DEFAULT_PARAMS["b"]
    custom = dataclasses.replace(c, params={"tau": np.linspace(0.01, 0.05, 5), "b": 0.05, "noise_std": 3.0})
    q = custom.model_params()
    assert np.allclose(q["tau"], np.linspace(0.01, 0.05, 5)) and q["b"] == 0.05 and "noise_std" not in q
    assert np.array_equal(c.input_current(0.0), np.zeros(5))
    assert np.array_equal(c.input_current(0.02), [250.0, 0, 0, 0, 0])


def test_rate_function_closed_forms():
    assert rate_function(-5.0) == 0.0 and rate_function(0.0) == 0.0
    assert np.isclose(rate_function(242.5), 200.0 * np.tanh(242.5 / 200.0))
    assert np.isclose(rate_function(10.0), 10.0, rtol=2e-3)  # linear regime: gain a = 1
    assert rate_function(1e3) < R_MAX <= rate_function(1e6) <= R_MAX  # tanh(5) < 1; tanh(5000) rounds to exactly 1
    assert np.isclose(rate_function(50.0, a=2.0, r_max=100.0), 100.0 * np.tanh(1.0))
    assert rate_function(np.array([-1.0, 20.0])).tolist() == [0.0, float(200.0 * np.tanh(0.1))]


# --------------------------------------------------------------------------------------------------
# generic dynamics checks
# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("name", sorted(CIRCUITS))
def test_reference_simulation_is_finite_and_bounded(name, sims):
    c = CIRCUITS[name]
    t, r = sims[name]
    assert t.shape == (int(round(c.t_end / 1e-3)) + 1,) and r.shape == (len(t), c.n)
    assert np.isclose(t[-1], c.t_end) and np.allclose(np.diff(t), 1e-3)
    assert np.isfinite(r).all()
    assert r.min() >= RATE_FLOOR, r.min()
    assert r.max() <= R_MAX * (1 + 1e-9)
    assert np.all(r[t < c.stim_onset_s] == 0.0)


@pytest.mark.parametrize("name", WITH_STEADY_STATE)
def test_steady_states_within_two_percent(name, sims):
    c = CIRCUITS[name]
    t, r = sims[name]
    tw, rw = _window(t, r, c)
    for i, ss in zip(c.expected["readout_neurons"], c.expected["steady_state_hz"]):
        _assert_close_rate(rw[-1, i], ss)
        assert np.ptp(rw[:, i]) <= max(0.01 * ss, 0.5), (name, i, np.ptp(rw[:, i]))  # settled inside the window


@pytest.mark.parametrize("name", NON_OSCILLATORS)
def test_non_rhythmic_circuits_are_not_sustained(name, sims):
    c = CIRCUITS[name]
    t, r = sims[name]
    _, rw = _window(t, r, c)
    late_max = c.expected.get("late_amplitude_max_hz", 1.0)
    for i in c.expected["readout_neurons"]:
        assert not _is_sustained(rw[:, i])
        assert np.ptp(rw[:, i]) <= late_max, (name, i, np.ptp(rw[:, i]))


@pytest.mark.parametrize("name", OSCILLATORS)
def test_sustained_oscillators(name, sims):
    c = CIRCUITS[name]
    e = c.expected
    t, r = sims[name]
    tw, rw = _window(t, r, c)
    assert (tw[-1] - tw[0]) * e["frequency_hz"] >= 6, "analysis window must hold at least six cycles"
    for k, i in enumerate(e["readout_neurons"]):
        x = rw[:, i]
        assert _is_sustained(x), (name, i)
        f_fft, f_int = _fft_frequency(tw, x), _interval_frequency(tw, x)
        assert abs(f_fft - e["frequency_hz"]) <= e["frequency_tol_hz"], (name, i, f_fft)
        assert abs(f_int - e["frequency_hz"]) <= e["frequency_tol_hz"], (name, i, f_int)
        assert abs(np.ptp(x) - e["amplitude_hz"][k]) <= e["amplitude_tol_fraction"] * e["amplitude_hz"][k], (name, i, np.ptp(x))
        assert abs(x.mean() - e["mean_rate_hz"][k]) <= e["mean_rate_tol_fraction"] * e["mean_rate_hz"][k], (name, i, x.mean())
    if "period_s" in e:
        assert abs(1.0 / _interval_frequency(tw, rw[:, e["readout_neurons"][0]]) - e["period_s"]) <= 0.003
    # the documented forward-Euler(1 ms) bias lies outside the deterministic tolerance for the fast oscillators, so the
    # tolerances are tight enough to catch a too-coarse integrator (the noisy variant deliberately loosens them)
    if "euler_1ms_frequency_hz" in e and e["frequency_hz"] > 10 and "noise_std" not in c.params:
        assert abs(e["euler_1ms_frequency_hz"] - e["frequency_hz"]) > e["frequency_tol_hz"]


# --------------------------------------------------------------------------------------------------
# circuit-specific claims
# --------------------------------------------------------------------------------------------------

def test_fixed_point_single_is_an_exact_exponential(sims):
    c = CIRCUITS["fixed_point_single"]
    e = c.expected
    t, r = sims["fixed_point_single"]
    (ss,) = e["steady_state_hz"]
    assert np.isclose(ss, R_MAX * np.tanh((c.stim_current - DEFAULT_PARAMS["theta"]) / R_MAX))
    tau = e["time_constant_s"]
    k = int(round((c.stim_onset_s + tau) / 1e-3))
    assert abs(r[k, 0] - e["rate_at_one_tau_hz"]) <= 0.01 * ss
    analytic = ss * (1 - np.exp(-(t - c.stim_onset_s) / tau)) * (t >= c.stim_onset_s)
    assert np.abs(r[:, 0] - analytic).max() < 1e-3 * ss
    assert np.all(np.diff(r[:, 0]) >= -1e-9)


def test_feedforward_chain_propagates_in_order(sims):
    c = CIRCUITS["feedforward_chain"]
    e = c.expected
    t, r = sims["feedforward_chain"]
    onsets = [t[np.argmax(r[:, i] > e["onset_threshold_hz"])] for i in e["readout_neurons"]]
    assert all(b > a for a, b in zip(onsets, onsets[1:])), onsets
    assert tuple(np.argsort(onsets)) == e["onset_order"]
    assert np.allclose(onsets, e["onset_times_s"], atol=1.5e-3)
    for i in e["readout_neurons"]:
        assert np.all(np.diff(r[:, i]) >= -1e-6), i  # monotone rise
    # closed-form chain steady states
    ss = [rate_function(c.stim_current - DEFAULT_PARAMS["theta"])]
    for _ in range(1, c.n):
        ss.append(rate_function(DEFAULT_PARAMS["b"] * 50.0 * ss[-1] - DEFAULT_PARAMS["theta"]))
    assert np.allclose(ss, e["steady_state_hz"]) and np.allclose(r[-1], ss, rtol=1e-3)


def test_recurrent_excitation_saturates(sims):
    c = CIRCUITS["recurrent_excitation_saturating"]
    t, r = sims["recurrent_excitation_saturating"]
    _, rw = _window(t, r, c)
    assert rw[-1].min() >= c.expected["saturation_fraction_min"] * R_MAX
    assert rw[-1].max() < R_MAX
    # the fixed point solves r = f(I + b W r - theta)
    i_ext = np.array([c.stim_current, 0.0])
    ss = np.asarray(c.expected["steady_state_hz"])
    assert np.allclose(rate_function(i_ext + DEFAULT_PARAMS["b"] * c.W @ ss - DEFAULT_PARAMS["theta"]), ss, atol=1e-6)


def test_bistable_pair_winner_take_all(sims):
    c = CIRCUITS["bistable_pair"]
    e = c.expected
    t, r = sims["bistable_pair"]
    assert r[-1, e["loser"]] < e["loser_max_hz"]
    _assert_close_rate(r[-1, e["winner"]], e["steady_state_hz"][0])
    _assert_close_rate(r[-1, 0], e["driver_steady_state_hz"])
    # mirrored stimulus flips the winner with identical rates
    mirror = dataclasses.replace(c, name="bistable_pair_mirror", stim_neurons=e["mirror_stim_neurons"])
    _, rm = reference_simulate(mirror)
    assert rm[-1, e["loser"]] > 100 and rm[-1, e["winner"]] < e["loser_max_hz"]
    assert np.isclose(rm[-1, e["loser"]], r[-1, e["winner"]], rtol=1e-6)
    # with symmetric input the deterministic trajectory sits on the unstable symmetric saddle (documented pitfall)
    sym = dataclasses.replace(c, name="bistable_pair_symmetric", stim_neurons=e["symmetric_stim_neurons"])
    _, rs = reference_simulate(sym)
    assert np.isclose(rs[-1, 1], rs[-1, 2], rtol=1e-6)
    _assert_close_rate(rs[-1, 1], e["symmetric_saddle_hz"])
    # both single-winner states are genuine fixed points: the loser's net input is negative under the winner's inhibition
    common = DEFAULT_PARAMS["b"] * 40.0 * e["driver_steady_state_hz"] - DEFAULT_PARAMS["theta"]
    assert common > 0 and common - DEFAULT_PARAMS["b"] * 60.0 * e["pair_alone_steady_state_hz"] < 0


def test_damped_oscillator_rings_then_settles(sims):
    c = CIRCUITS["damped_oscillator"]
    e = c.expected
    t, r = sims["damped_oscillator"]
    x = r[:, 0]
    pk = _peaks(x, 0.0)
    assert len(pk) >= 5
    assert abs(t[pk[0]] - e["first_peak_time_s"]) <= 2e-3 and abs(x[pk[0]] - e["first_peak_hz"]) <= 0.02 * e["first_peak_hz"]
    assert x[pk[0]] / e["steady_state_hz"][0] >= e["overshoot_ratio_min"]
    peak_values = x[pk[:5]]
    assert np.all(np.diff(peak_values) < 0)  # decaying peaks
    f_transient = 1.0 / np.mean(np.diff(t[pk[1:6]]))
    assert abs(f_transient - e["transient_frequency_hz"]) <= e["transient_frequency_tol_hz"], f_transient
    # decay rate of the peak envelope agrees with the eigenvalue's real part within 30 %
    excess = peak_values[1:5] - e["steady_state_hz"][0]
    rate = -np.polyfit(t[pk[1:5]], np.log(excess), 1)[0]
    assert abs(rate - e["decay_rate_per_s"]) <= 0.3 * e["decay_rate_per_s"], rate
    _, rw = _window(t, r, c)
    assert np.ptp(rw, axis=0).max() <= e["late_amplitude_max_hz"]


def test_ring_rotates_in_the_documented_order(sims):
    c = CIRCUITS["sustained_oscillator"]
    t, r = sims["sustained_oscillator"]
    tw, rw = _window(t, r, c)
    first, second, third = c.expected["peak_order"]
    t_first = tw[_peaks(rw[:, first], rw[:, first].mean())]
    ref = t_first[len(t_first) // 2]
    nxt = {i: tw[_peaks(rw[:, i], rw[:, i].mean())] for i in (second, third)}
    nxt = {i: v[v > ref][0] for i, v in nxt.items()}
    assert nxt[second] < nxt[third] < ref + c.expected["period_s"]
    assert np.isclose(rw[-1, 0], c.expected["driver_steady_state_hz"], rtol=1e-4)


def test_noisy_oscillator_documents_noise_and_matches_sustained(sims):
    noisy, clean = CIRCUITS["noisy_oscillator"], CIRCUITS["sustained_oscillator"]
    assert np.array_equal(noisy.W, clean.W) and noisy.stim_neurons == clean.stim_neurons
    assert noisy.params["noise_std"] > 0 and "noise_model" in noisy.params
    assert noisy.expected["frequency_hz"] == clean.expected["frequency_hz"]
    assert noisy.expected["frequency_tol_hz"] > clean.expected["frequency_tol_hz"]
    assert np.array_equal(sims["noisy_oscillator"][1], sims["sustained_oscillator"][1])  # reference run is deterministic


def test_delayed_inhibitory_loop_silences_the_driver_each_cycle(sims):
    c = CIRCUITS["delayed_inhibitory_oscillator"]
    t, r = sims["delayed_inhibitory_oscillator"]
    _, rw = _window(t, r, c)
    assert rw[:, 0].min() < 1.0  # the excitatory neuron is shut off by the delayed inhibition every cycle
    assert rw[:, 0].max() > 100.0
    # the relay stages peak in order 0 -> 1 -> 2 -> 3 -> 4 within one cycle
    ref = _window(t, r, c)[0][_peaks(rw[:, 0], rw[:, 0].mean())][2]
    tw = _window(t, r, c)[0]
    peak_times = [tw[_peaks(rw[:, i], rw[:, i].mean())] for i in range(c.n)]
    nxt = [ref] + [v[v > ref][0] for v in peak_times[1:]]
    assert all(b > a for a, b in zip(nxt, nxt[1:])), nxt


def test_random_recurrent_fingerprint(sims):
    c = CIRCUITS["random_recurrent"]
    e = c.expected
    t, r = sims["random_recurrent"]
    assert c.n == 30 and e["n_edges"] == int(np.count_nonzero(c.W)) and np.all(np.diag(c.W) == 0)
    assert e["n_excitatory_columns"] == int(((c.W > 0).any(axis=0)).sum())
    assert np.all(np.abs(c.W[c.W != 0]) >= 1) and np.all(np.abs(c.W) < 30)
    _, rw = _window(t, r, c)
    assert np.ptp(rw, axis=0).max() <= e["late_amplitude_max_hz"]
    for i, ss in zip(e["readout_neurons"], e["steady_state_hz"]):
        _assert_close_rate(rw[-1, i], ss, rel=0.02, abs_floor=0.05)
    assert int((rw[-1] > 1.0).sum()) == e["n_active_neurons"]
    # the reported fixed point really is one
    i_ext = np.zeros(c.n)
    i_ext[list(c.stim_neurons)] = c.stim_current
    ss = np.asarray(e["steady_state_hz"])
    assert np.allclose(rate_function(i_ext + DEFAULT_PARAMS["b"] * c.W @ ss - DEFAULT_PARAMS["theta"]), ss, atol=0.05)
