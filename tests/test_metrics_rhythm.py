"""Rhythm metrics on labelled synthetic signals and circuits.

The published score is reproduced as specified; these tests also pin down its documented limitations (amplitude
blindness, no damped/sustained distinction) and check that the composite decision handles them.
"""

from __future__ import annotations

import numpy as np
import pytest

from brainir.metrics.rhythm import (
    find_peaks_1d,
    interpeak_regularity,
    network_oscillation_score,
    neuron_oscillation_score,
    rhythm_report,
    spectral_peak,
)
from brainir.testing.circuits import CIRCUITS, reference_simulate
from brainir.testing.signals import all_signals, make_signal

DT = 1e-3
WINDOW = 250  # samples: the paper analyses t >= 0.25 s


def _reports():
    return {s.name: (s, rhythm_report(s.x[WINDOW:], s.dt)) for s in all_signals(dt=DT, duration=2.0, seed=0)}


def test_find_peaks_uses_global_side_minima_prominence():
    x = np.array([0.0, 1.0, 0.2, 0.9, 0.1, 0.95, 0.0])
    idx, h, p = find_peaks_1d(x, 0.05)
    assert idx.tolist() == [1, 3, 5]
    assert p[1] == pytest.approx(0.9 - max(min(x[:3]), min(x[4:])))  # height above the higher of the two side minima
    assert find_peaks_1d(np.zeros(10), 0.05)[0].size == 0
    assert find_peaks_1d(np.array([0.0, 1.0]), 0.05)[0].size == 0


def test_paper_score_is_one_for_a_pure_sinusoid_and_zero_for_constants():
    t = np.arange(1751) * DT
    s, f = neuron_oscillation_score(40 + 20 * np.sin(2 * np.pi * 8 * t))
    assert s > 0.999 and abs(f / DT - 8.0) < 0.1  # < 1 only because the window holds a non-integer number of cycles
    assert neuron_oscillation_score(np.full(1751, 150.0)) == (0.0, 0.0)
    assert neuron_oscillation_score(np.zeros(1751)) == (0.0, 0.0)


def test_paper_score_float32_agrees_with_float64_to_five_decimals():
    s = make_signal("sinusoid_plus_noise", dt=DT, duration=2.0, seed=1)
    a, fa = neuron_oscillation_score(s.x[WINDOW:], dtype=np.float64)
    b, fb = neuron_oscillation_score(s.x[WINDOW:], dtype=np.float32)
    assert abs(a - b) < 2e-5 and fa == pytest.approx(fb, rel=1e-6)


def test_rhythmic_signals_are_detected_with_the_right_frequency():
    for name, (s, r) in _reports().items():
        if s.truth["is_rhythmic"] and not s.truth["has_artifacts"]:
            assert r.paper_score >= 0.7, (name, r.paper_score)
            f_true = s.truth["frequency_hz"]
            assert r.paper_frequency_hz is not None and abs(r.paper_frequency_hz - f_true) <= max(0.7, 0.12 * f_true), (name, r)
            assert r.is_sustained_rhythm(max_interpeak_cv=None), (name, r)


def test_constants_noise_and_transients_score_low():
    rep = _reports()
    for name in ("constant_high", "constant_low", "white_noise", "pink_noise", "irregular_bursting", "chirp", "transient_then_flat"):
        s, r = rep[name]
        assert r.paper_score < 0.5, (name, r.paper_score)
        assert not r.is_sustained_rhythm(), name


def test_published_score_cannot_separate_damped_from_sustained_but_the_composite_can():
    """Documented limitation: the min-max normalised autocorrelation of a decaying oscillation still has a prominent
    first peak, so the published score stays high; the envelope gate rejects it."""
    s, r = _reports()["damped_oscillation"]
    assert not s.truth["is_rhythmic"]
    assert r.paper_score > 0.5  # the limitation
    assert r.late_over_early is not None and r.late_over_early < 0.1
    assert not r.is_sustained_rhythm()


def test_published_score_is_amplitude_blind_and_the_range_gate_catches_it():
    t = np.arange(1751) * DT
    tiny = 50.0 + 1e-4 * np.sin(2 * np.pi * 8 * t)  # 0.0002 Hz peak-to-trough ripple on a 50 Hz plateau
    s, _ = neuron_oscillation_score(tiny)
    assert s > 0.99  # the limitation: scores like a full-amplitude oscillation
    r = rhythm_report(tiny, DT)
    assert r.range_hz < 1e-3 and not r.is_sustained_rhythm()


def test_artifacts_are_flagged_not_crashed():
    rep = _reports()
    s, r = rep["numerical_artifact_nan"]
    assert not r.finite
    assert not r.is_sustained_rhythm()  # non-finite traces never count as rhythmic
    s2, r2 = rep["numerical_artifact_spike"]
    assert r2.paper_score == 0.0 and not r2.is_sustained_rhythm()


def test_network_score_is_mean_over_mask_and_frequency_over_detected_peaks():
    t = np.arange(1751) * DT
    R = np.stack([40 + 20 * np.sin(2 * np.pi * 8 * t), np.full(1751, 30.0), np.zeros(1751)], axis=1)
    score, f, per, freqs = network_oscillation_score(R, np.array([True, True, False]))
    assert score == pytest.approx(0.5, abs=1e-3) and abs(f / DT - 8.0) < 0.1  # (~1 + 0) / 2
    assert per.tolist()[2] == 0.0 and np.isnan(freqs[2])
    assert network_oscillation_score(R, np.zeros(3, bool))[0] == 0.0


def test_supporting_metrics_on_clean_signals():
    t = np.arange(1751) * DT
    x = 40 + 20 * np.sin(2 * np.pi * 8 * t)
    assert abs(spectral_peak(x, DT)["frequency_hz"] - 8.0) < 0.6
    ipr = interpeak_regularity(x, DT)
    assert ipr["n_peaks"] >= 13 and ipr["cv"] < 0.01 and abs(ipr["frequency_hz"] - 8.0) < 0.1
    assert spectral_peak(np.full(100, 3.0), DT)["frequency_hz"] is None


@pytest.mark.parametrize("name", sorted(CIRCUITS))
def test_circuit_fixtures_are_classified_as_labelled(name):
    c = CIRCUITS[name]
    t, r = reference_simulate(c)
    t0, t1 = c.expected["analysis_window_s"]
    m = (t >= t0 - 1e-9) & (t <= t1 + 1e-9)
    k = c.expected["readout_neurons"][0]
    rep = rhythm_report(r[m][:, k], DT)
    if c.expected["is_rhythmic"]:
        assert rep.is_sustained_rhythm(), (name, rep)
        assert abs(rep.paper_frequency_hz - c.expected["frequency_hz"]) <= c.expected["frequency_tol_hz"]
    else:
        assert not rep.is_sustained_rhythm(), (name, rep)
