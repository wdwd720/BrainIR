"""Self-consistency tests for brainir.testing.signals.

Every labelled signal must build deterministically, and its ground-truth labels must agree with simple,
robust measurements (FFT peak, envelope persistence, artifact presence). The measurements here are sanity
checks for the fixture, not the rhythmicity metrics under development.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

from brainir.testing.signals import SIGNAL_KINDS, Signal, all_signals, make_signal

REQUIRED_TRUTH_KEYS = {"is_rhythmic", "frequency_hz", "is_stationary", "has_artifacts", "kind", "dt", "duration_s", "seed"}
STOCHASTIC_KINDS = {"white_noise", "pink_noise", "irregular_bursting", "sinusoid_plus_noise", "numerical_artifact_nan"}
ARTIFACT_KINDS = {"numerical_artifact_nan", "numerical_artifact_spike"}
RHYTHMIC_KINDS = {k for k in SIGNAL_KINDS if make_signal(k).truth["is_rhythmic"]}
NON_RHYTHMIC_KINDS = set(SIGNAL_KINDS) - RHYTHMIC_KINDS


def _finite(x: np.ndarray) -> np.ndarray:
    """Replace non-finite samples by the finite mean (enough for the fixture checks)."""
    ok = np.isfinite(x)
    if ok.all():
        return x
    return np.where(ok, x, x[ok].mean())


def _spectrum(sig: Signal) -> tuple[np.ndarray, np.ndarray]:
    """One-sided power spectrum of the mean-removed, Hann-windowed signal; sub-1 Hz content (drift) is zeroed."""
    x = _finite(sig.x)
    x = (x - x.mean()) * np.hanning(len(x))
    power = np.abs(np.fft.rfft(x)) ** 2
    freqs = np.fft.rfftfreq(len(x), d=sig.dt)
    power[freqs < 1.0] = 0.0
    return freqs, power


def _peak_fraction(power: np.ndarray) -> tuple[int, float]:
    total = power.sum()
    if total <= 0:
        return 0, 0.0
    k = int(np.argmax(power))
    return k, float(power[max(k - 1, 0):k + 2].sum() / total)


def _persistence(x: np.ndarray) -> float:
    """Peak-to-trough of the last quarter relative to the first quarter (1 for a stationary oscillation)."""
    quarters = np.array_split(_finite(x), 4)
    first, last = np.ptp(quarters[0]), np.ptp(quarters[-1])
    return float(last / first) if first > 0 else 0.0


def simple_rhythmicity(sig: Signal) -> tuple[bool, float | None]:
    """Rhythmic iff a narrow spectral peak carries > 50 % of the power *and* the oscillation persists to the end."""
    freqs, power = _spectrum(sig)
    k, frac = _peak_fraction(power)
    if frac == 0.0:
        return False, None
    return (frac > 0.5 and _persistence(sig.x) >= 0.5), float(freqs[k])


# --------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("kind", SIGNAL_KINDS)
def test_builds_with_defaults(kind):
    sig = make_signal(kind)
    assert sig.name == kind
    assert sig.dt == 1e-3
    assert sig.t.shape == sig.x.shape == (2000,)
    assert sig.t[0] == 0.0
    assert np.allclose(np.diff(sig.t), sig.dt)
    assert sig.x.dtype == np.float64
    assert REQUIRED_TRUTH_KEYS <= set(sig.truth)
    assert isinstance(sig.truth["is_rhythmic"], bool)
    assert isinstance(sig.truth["is_stationary"], bool)
    assert isinstance(sig.truth["has_artifacts"], bool)
    f = sig.truth["frequency_hz"]
    assert (f is None) == (not sig.truth["is_rhythmic"])
    if f is not None:
        assert 0 < f < 0.5 / sig.dt
    assert sig.truth["kind"] == kind and sig.truth["seed"] == 0 and sig.truth["duration_s"] == 2.0


def test_all_signals_covers_every_kind_once():
    sigs = all_signals()
    assert [s.name for s in sigs] == list(SIGNAL_KINDS)
    assert len(set(SIGNAL_KINDS)) == len(SIGNAL_KINDS) >= 16


def test_signal_is_frozen():
    sig = make_signal("constant_low")
    with pytest.raises(dataclasses.FrozenInstanceError):
        sig.dt = 2.0  # type: ignore[misc]


@pytest.mark.parametrize("kind", SIGNAL_KINDS)
def test_deterministic_under_seed(kind):
    a, b = make_signal(kind, seed=3), make_signal(kind, seed=3)
    assert np.array_equal(a.x, b.x, equal_nan=True)
    assert a.truth == b.truth
    c = make_signal(kind, seed=4)
    if kind in STOCHASTIC_KINDS:
        assert not np.array_equal(a.x, c.x, equal_nan=True)
    else:
        assert np.array_equal(a.x, c.x, equal_nan=True)


def test_custom_grid_and_parameters():
    # 12.5 Hz at dt = 2 ms is 40 samples per period, so the grid hits the exact peak (t = 20 ms) and trough (t = 60 ms)
    sig = make_signal("sustained_sinusoid", dt=2e-3, duration=1.0, seed=7, freq_hz=12.5, amplitude=3.0, offset=1.0)
    assert sig.t.shape == (500,) and sig.dt == 2e-3
    assert sig.truth["frequency_hz"] == 12.5 and sig.truth["amplitude"] == 3.0
    assert np.isclose(sig.x.max(), 4.0, atol=1e-9) and np.isclose(sig.x.min(), -2.0, atol=1e-9)


def test_invalid_inputs():
    with pytest.raises(ValueError, match="unknown signal kind"):
        make_signal("not_a_kind")
    with pytest.raises(TypeError):
        make_signal("constant_high", bogus=1)
    with pytest.raises(ValueError):
        make_signal("sustained_sinusoid", dt=-1e-3)
    with pytest.raises(ValueError):
        make_signal("two_frequency_mixture", secondary_amplitude=50.0, amplitude=10.0)
    with pytest.raises(ValueError):
        make_signal("sinusoid_plus_noise", snr=0.0)


@pytest.mark.parametrize("kind", sorted(RHYTHMIC_KINDS))
def test_rhythmic_kinds_have_claimed_dominant_frequency(kind):
    sig = make_signal(kind)
    is_rhythmic, f_peak = simple_rhythmicity(sig)
    assert is_rhythmic, f"{kind}: fixture should look rhythmic to the simple criterion"
    resolution = 1.0 / (len(sig.t) * sig.dt)
    assert abs(f_peak - sig.truth["frequency_hz"]) <= resolution + 1e-9, (kind, f_peak, sig.truth["frequency_hz"])


@pytest.mark.parametrize("kind", sorted(NON_RHYTHMIC_KINDS))
def test_non_rhythmic_kinds_lack_a_single_persistent_peak(kind):
    sig = make_signal(kind)
    is_rhythmic, _ = simple_rhythmicity(sig)
    assert not is_rhythmic, kind


def test_damped_and_transient_decay_within_window():
    damped = make_signal("damped_oscillation")
    assert _persistence(damped.x) < 0.05
    quarters = np.array_split(damped.x, 4)
    assert np.ptp(quarters[0]) > 50 and np.ptp(quarters[-1]) < 2
    assert abs(quarters[-1].mean() - damped.truth["settles_to"]) < 1.0
    transient = make_signal("transient_then_flat")
    assert np.ptp(transient.x[len(transient.x) // 2:]) < 1e-6
    assert transient.x.max() > transient.truth["offset"] + 0.9 * transient.truth["amplitude"]


def test_chirp_frequency_drifts():
    sig = make_signal("chirp")
    third = len(sig.x) // 3
    peaks = []
    for seg in (sig.x[:third], sig.x[-third:]):
        seg = (seg - seg.mean()) * np.hanning(len(seg))
        power = np.abs(np.fft.rfft(seg)) ** 2
        peaks.append(np.fft.rfftfreq(len(seg), d=sig.dt)[np.argmax(power)])
    assert peaks[0] < peaks[1]
    assert sig.truth["f_start_hz"] <= peaks[0] < peaks[1] <= sig.truth["f_end_hz"]


def test_irregular_bursting_has_no_stable_period():
    sig = make_signal("irregular_bursting")
    times = np.asarray(sig.truth["burst_times_s"])
    assert sig.truth["n_bursts"] == len(times) >= 4
    gaps = np.diff(times)
    assert gaps.min() >= sig.truth["refractory_s"] - 1e-9
    assert sig.truth["interval_cv"] > 0.3  # irregular
    # bursts are spread over the window rather than clustered in one half
    assert (times < 1.0).sum() >= 2 and (times >= 1.0).sum() >= 2


def test_two_frequency_mixture_has_two_peaks():
    sig = make_signal("two_frequency_mixture")
    freqs, power = _spectrum(sig)
    k1 = int(np.argmax(power))
    power2 = power.copy()
    power2[max(k1 - 2, 0):k1 + 3] = 0
    k2 = int(np.argmax(power2))
    assert {round(float(freqs[k1]), 1), round(float(freqs[k2]), 1)} == {sig.truth["frequency_hz"], sig.truth["secondary_frequency_hz"]}
    assert freqs[k1] == sig.truth["frequency_hz"]


def test_saturated_square_is_clipped():
    sig = make_signal("saturated_square")
    ceiling, floor = sig.truth["ceiling"], sig.truth["floor"]
    assert sig.x.max() == ceiling and sig.x.min() == floor
    assert np.mean(sig.x == ceiling) > 0.3 and np.mean(sig.x == floor) > 0.3
    assert sig.truth["is_saturated"] is True


def test_sinusoid_plus_noise_snr():
    sig = make_signal("sinusoid_plus_noise")
    clean = sig.truth["offset"] + sig.truth["amplitude"] * np.sin(2 * np.pi * sig.truth["frequency_hz"] * sig.t)
    noise = sig.x - clean
    assert abs(noise.std() - sig.truth["noise_std"]) < 0.1 * sig.truth["noise_std"]
    assert np.isclose(sig.truth["noise_std"], sig.truth["amplitude"] / np.sqrt(2 * sig.truth["snr"]))


def test_slow_drift_is_non_stationary_but_rhythmic():
    sig = make_signal("slow_drift_plus_rhythm")
    assert sig.truth["is_rhythmic"] and not sig.truth["is_stationary"]
    quarters = np.array_split(sig.x, 4)
    assert quarters[-1].mean() - quarters[0].mean() > 0.5 * sig.truth["drift_amplitude"]


@pytest.mark.parametrize("kind", SIGNAL_KINDS)
def test_artifact_labels_match_content(kind):
    sig = make_signal(kind)
    if kind == "numerical_artifact_nan":
        idx = np.flatnonzero(~np.isfinite(sig.x))
        assert sig.truth["has_artifacts"] and tuple(idx) == sig.truth["artifact_indices"] and len(idx) == 5
        assert np.isnan(sig.x[idx]).all()
    elif kind == "numerical_artifact_spike":
        (i,) = sig.truth["artifact_indices"]
        assert sig.truth["has_artifacts"] and sig.x[i] == sig.truth["spike_value"]
        rest = np.delete(sig.x, i)
        assert np.ptp(rest) == 0 and rest[0] == sig.truth["level"]
    else:
        assert not sig.truth["has_artifacts"]
        assert np.isfinite(sig.x).all()
        assert np.abs(sig.x).max() < 1e4


@pytest.mark.parametrize("kind", sorted(set(SIGNAL_KINDS) - ARTIFACT_KINDS))
def test_stationarity_labels_match_envelope_and_mean(kind):
    sig = make_signal(kind)
    x = sig.x
    quarters = np.array_split(x, 4)
    means = np.array([q.mean() for q in quarters])
    ptps = np.array([np.ptp(q) for q in quarters])
    std = x.std()
    if sig.truth["is_stationary"]:
        if std == 0:
            return  # constants are trivially stationary
        if kind in STOCHASTIC_KINDS:
            # a single realisation of a stationary process (1/f noise, sparse bursts) shows quarter-mean shifts of ~0.5 std
            assert np.abs(means - x.mean()).max() < 1.0 * std, (kind, means)
            assert ptps.min() > 0.3 * ptps.max(), (kind, ptps)
        else:
            assert np.abs(means - x.mean()).max() < 0.5 * std, (kind, means)
            assert ptps.min() > 0.5 * ptps.max(), (kind, ptps)
    else:
        mean_shift = np.abs(means - x.mean()).max() / std if std > 0 else 0.0
        envelope_change = 1.0 - ptps.min() / ptps.max() if ptps.max() > 0 else 0.0
        assert kind == "chirp" or mean_shift > 0.25 or envelope_change > 0.5, (kind, mean_shift, envelope_change)
