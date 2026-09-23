"""Synthetic 1-D test signals with ground-truth labels for validating rhythmicity metrics.

Every signal is generated from a closed-form recipe plus a seeded ``numpy.random.Generator``,
so the *truth* labels are known by construction rather than measured. The module depends on
numpy only. Nothing here is anatomy or model output: these are analysis fixtures.

Truth dictionary (every kind)::

    is_rhythmic    bool          sustained, roughly periodic oscillation over the whole window
    frequency_hz   float | None  dominant frequency when rhythmic, else None
    is_stationary  bool          statistics (mean, envelope) do not drift over the window
    has_artifacts  bool          the samples contain NaN/inf or an implausible outlier

plus kind-specific keys (amplitude, offset, noise_std, burst_times, artifact_indices, ...) named
in the generator docstrings. Labelling conventions worth knowing:

* ``damped_oscillation`` decays to a constant inside the window, so it is *not* rhythmic even
  though its spectrum has a narrow peak; ``transient_frequency_hz`` records the ringing frequency.
* ``two_frequency_mixture`` is rhythmic with ``frequency_hz`` = the stronger component and
  ``secondary_frequency_hz`` = the weaker one.
* ``chirp`` drifts in frequency and is therefore not a stable rhythm (``frequency_hz`` is None;
  ``f_start_hz``/``f_end_hz`` are given).
* ``numerical_artifact_nan`` is a rhythmic sinusoid with a few NaN samples; the underlying rhythm
  is labelled, and ``has_artifacts`` is True.
* ``pink_noise`` is labelled stationary (it is a stationary process) although its low-frequency
  power can look like drift over a short window.

The default grid is ``dt = 1 ms`` over ``2 s`` (2000 samples); the default frequencies are
multiples of 0.5 Hz so that they sit exactly on the FFT bins of the default window.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

__all__ = ["SIGNAL_KINDS", "Signal", "all_signals", "make_signal"]


@dataclass(frozen=True)
class Signal:
    name: str
    t: np.ndarray  # seconds, uniform grid starting at 0
    x: np.ndarray  # same length as t (NaN/inf only for the 'numerical_artifact_*' kinds)
    dt: float
    truth: dict


def _time_grid(dt: float, duration: float) -> np.ndarray:
    if dt <= 0 or duration <= 0:
        raise ValueError("dt and duration must be positive")
    n = int(round(duration / dt))
    if n < 8:
        raise ValueError("duration/dt must give at least 8 samples")
    return np.arange(n, dtype=np.float64) * dt


def _truth(is_rhythmic: bool, frequency_hz: float | None, is_stationary: bool, has_artifacts: bool, **extra) -> dict:
    d = {"is_rhythmic": bool(is_rhythmic), "frequency_hz": None if frequency_hz is None else float(frequency_hz),
         "is_stationary": bool(is_stationary), "has_artifacts": bool(has_artifacts)}
    d.update(extra)
    return d


# --------------------------------------------------------------------------------------------------
# generators: (t, rng, **kw) -> (x, truth)
# --------------------------------------------------------------------------------------------------

def _sustained_sinusoid(t, rng, *, freq_hz: float = 8.0, amplitude: float = 20.0, offset: float = 40.0):
    """offset + amplitude * sin(2 pi f t)."""
    x = offset + amplitude * np.sin(2 * np.pi * freq_hz * t)
    return x, _truth(True, freq_hz, True, False, amplitude=amplitude, offset=offset, waveform="sinusoid")


def _sustained_nonsinusoidal(t, rng, *, freq_hz: float = 5.0, amplitude: float = 60.0, offset: float = 5.0, sharpness: float = 3.0):
    """Periodic bursts: offset + amplitude * max(sin(2 pi f t), 0) ** sharpness (half-wave rectified, peaky)."""
    x = offset + amplitude * np.maximum(np.sin(2 * np.pi * freq_hz * t), 0.0) ** sharpness
    return x, _truth(True, freq_hz, True, False, amplitude=amplitude, offset=offset, sharpness=sharpness,
                     waveform="half_wave_rectified_power", has_harmonics=True)


def _damped_oscillation(t, rng, *, freq_hz: float = 12.0, amplitude: float = 40.0, offset: float = 30.0, decay_fraction: float = 1 / 6):
    """offset + amplitude * exp(-t / tau) * sin(2 pi f t) with tau = decay_fraction * window; ~e^-6 of the amplitude is left at the end."""
    tau = decay_fraction * (t[-1] + (t[1] - t[0]))
    x = offset + amplitude * np.exp(-t / tau) * np.sin(2 * np.pi * freq_hz * t)
    return x, _truth(False, None, False, False, transient_frequency_hz=freq_hz, amplitude=amplitude, offset=offset,
                     decay_time_s=float(tau), settles_to=offset)


def _transient_then_flat(t, rng, *, amplitude: float = 80.0, offset: float = 10.0, center_fraction: float = 0.25, width_fraction: float = 0.03):
    """A single Gaussian bump centred at center_fraction of the window, then flat at offset."""
    duration = t[-1] + (t[1] - t[0])
    c, w = center_fraction * duration, width_fraction * duration
    x = offset + amplitude * np.exp(-0.5 * ((t - c) / w) ** 2)
    return x, _truth(False, None, False, False, amplitude=amplitude, offset=offset, bump_center_s=float(c), bump_width_s=float(w))


def _constant_high(t, rng, *, level: float = 150.0):
    x = np.full_like(t, level)
    return x, _truth(False, None, True, False, level=level)


def _constant_low(t, rng, *, level: float = 0.0):
    x = np.full_like(t, level)
    return x, _truth(False, None, True, False, level=level)


def _white_noise(t, rng, *, std: float = 10.0, offset: float = 50.0):
    x = offset + std * rng.standard_normal(t.shape)
    return x, _truth(False, None, True, False, noise_std=std, offset=offset, spectrum="white")


def _pink_noise(t, rng, *, std: float = 10.0, offset: float = 50.0):
    """1/f (pink) noise: white noise shaped in the frequency domain by 1/sqrt(f), scaled to the requested std."""
    n = len(t)
    white = rng.standard_normal(n)
    spec = np.fft.rfft(white)
    f = np.fft.rfftfreq(n, d=t[1] - t[0])
    shape = np.zeros_like(f)
    shape[1:] = 1.0 / np.sqrt(f[1:])
    pink = np.fft.irfft(spec * shape, n=n)
    pink = pink - pink.mean()
    pink *= std / pink.std()
    return offset + pink, _truth(False, None, True, False, noise_std=std, offset=offset, spectrum="pink_1_over_f")


def _irregular_bursting(t, rng, *, burst_rate_hz: float = 3.0, refractory_s: float = 0.1, burst_width_s: float = 0.03, amplitude: float = 60.0,
                        offset: float = 5.0, amplitude_jitter: float = 0.3):
    """Gaussian bursts at the events of a refractory renewal process (gap = refractory + exponential) with jittered amplitudes.

    The inter-burst intervals have a coefficient of variation around 0.5-1, so there is no stable period; the refractory
    period keeps the bursts spread over the window instead of clustering.
    """
    if refractory_s * burst_rate_hz >= 1.0:
        raise ValueError("refractory_s must be shorter than the mean inter-burst interval 1 / burst_rate_hz")
    duration = t[-1] + (t[1] - t[0])
    mean_gap = 1.0 / burst_rate_hz
    times = []
    cur = float(rng.uniform(0.0, mean_gap))
    while cur < duration:
        times.append(cur)
        cur += refractory_s + float(rng.exponential(mean_gap - refractory_s))
    times_arr = np.asarray(times)
    amps = amplitude * (1.0 + amplitude_jitter * rng.uniform(-1.0, 1.0, size=len(times_arr)))
    x = np.full_like(t, offset)
    for c, a in zip(times_arr, amps):
        x += a * np.exp(-0.5 * ((t - c) / burst_width_s) ** 2)
    gaps = np.diff(times_arr)
    cv = float(gaps.std() / gaps.mean()) if len(gaps) > 1 else float("nan")
    return x, _truth(False, None, True, False, burst_rate_hz=burst_rate_hz, refractory_s=refractory_s, burst_width_s=burst_width_s,
                     amplitude=amplitude, offset=offset, burst_times_s=tuple(float(v) for v in times_arr), n_bursts=int(len(times_arr)),
                     interval_cv=cv)


def _two_frequency_mixture(t, rng, *, freq_hz: float = 6.0, secondary_freq_hz: float = 14.0, amplitude: float = 20.0,
                           secondary_amplitude: float = 12.0, offset: float = 50.0):
    """Sum of two incommensurate sinusoids; the first (larger) one is the dominant frequency."""
    if secondary_amplitude >= amplitude:
        raise ValueError("secondary_amplitude must be smaller than amplitude so that freq_hz is dominant")
    x = offset + amplitude * np.sin(2 * np.pi * freq_hz * t) + secondary_amplitude * np.sin(2 * np.pi * secondary_freq_hz * t + 1.0)
    return x, _truth(True, freq_hz, True, False, secondary_frequency_hz=secondary_freq_hz, amplitude=amplitude,
                     secondary_amplitude=secondary_amplitude, offset=offset, n_frequencies=2)


def _chirp(t, rng, *, f_start_hz: float = 3.0, f_end_hz: float = 15.0, amplitude: float = 20.0, offset: float = 40.0):
    """Linear chirp: instantaneous frequency sweeps from f_start_hz to f_end_hz across the window."""
    duration = t[-1] + (t[1] - t[0])
    phase = 2 * np.pi * (f_start_hz * t + 0.5 * (f_end_hz - f_start_hz) * t**2 / duration)
    x = offset + amplitude * np.sin(phase)
    return x, _truth(False, None, False, False, f_start_hz=f_start_hz, f_end_hz=f_end_hz, amplitude=amplitude, offset=offset)


def _sinusoid_plus_noise(t, rng, *, freq_hz: float = 10.0, amplitude: float = 20.0, offset: float = 40.0, snr: float = 4.0):
    """Sinusoid plus white noise. ``snr`` is the power ratio (sinusoid power A^2/2 over noise variance)."""
    if snr <= 0:
        raise ValueError("snr must be positive")
    noise_std = amplitude / np.sqrt(2.0 * snr)
    x = offset + amplitude * np.sin(2 * np.pi * freq_hz * t) + noise_std * rng.standard_normal(t.shape)
    return x, _truth(True, freq_hz, True, False, amplitude=amplitude, offset=offset, snr=snr, noise_std=float(noise_std))


def _slow_drift_plus_rhythm(t, rng, *, freq_hz: float = 7.0, amplitude: float = 20.0, offset: float = 40.0, drift_amplitude: float = 30.0):
    """Sinusoid riding on a slow mean drift (a linear ramp plus a half-cosine over the window)."""
    duration = t[-1] + (t[1] - t[0])
    drift = drift_amplitude * (t / duration) + 0.5 * drift_amplitude * (1 - np.cos(np.pi * t / duration))
    x = offset + drift + amplitude * np.sin(2 * np.pi * freq_hz * t)
    return x, _truth(True, freq_hz, False, False, amplitude=amplitude, offset=offset, drift_amplitude=drift_amplitude,
                     drift_total=float(drift[-1] - drift[0]))


def _numerical_artifact_nan(t, rng, *, freq_hz: float = 9.0, amplitude: float = 20.0, offset: float = 40.0, n_nan: int = 5):
    """A rhythmic sinusoid with ``n_nan`` NaN samples at seeded positions."""
    x = offset + amplitude * np.sin(2 * np.pi * freq_hz * t)
    idx = np.sort(rng.choice(len(t), size=int(n_nan), replace=False))
    x[idx] = np.nan
    return x, _truth(True, freq_hz, True, True, amplitude=amplitude, offset=offset, artifact_kind="nan",
                     artifact_indices=tuple(int(i) for i in idx))


def _numerical_artifact_spike(t, rng, *, level: float = 30.0, spike_value: float = 1e6, spike_fraction: float = 0.6):
    """A constant signal with one implausible outlier sample."""
    x = np.full_like(t, level)
    i = int(round(spike_fraction * (len(t) - 1)))
    x[i] = spike_value
    return x, _truth(False, None, True, True, level=level, artifact_kind="spike", artifact_indices=(i,), spike_value=spike_value)


def _saturated_square(t, rng, *, freq_hz: float = 4.0, ceiling: float = 200.0, drive_amplitude: float = 600.0, floor: float = 0.0):
    """A sinusoidal drive clipped to [floor, ceiling]: a nearly square, saturated oscillation."""
    x = np.clip(0.5 * (ceiling + floor) + drive_amplitude * np.sin(2 * np.pi * freq_hz * t), floor, ceiling)
    return x, _truth(True, freq_hz, True, False, ceiling=ceiling, floor=floor, drive_amplitude=drive_amplitude, is_saturated=True,
                     has_harmonics=True)


_GENERATORS: dict[str, Callable[..., tuple[np.ndarray, dict]]] = {
    "sustained_sinusoid": _sustained_sinusoid,
    "sustained_nonsinusoidal": _sustained_nonsinusoidal,
    "damped_oscillation": _damped_oscillation,
    "transient_then_flat": _transient_then_flat,
    "constant_high": _constant_high,
    "constant_low": _constant_low,
    "white_noise": _white_noise,
    "pink_noise": _pink_noise,
    "irregular_bursting": _irregular_bursting,
    "two_frequency_mixture": _two_frequency_mixture,
    "chirp": _chirp,
    "sinusoid_plus_noise": _sinusoid_plus_noise,
    "slow_drift_plus_rhythm": _slow_drift_plus_rhythm,
    "numerical_artifact_nan": _numerical_artifact_nan,
    "numerical_artifact_spike": _numerical_artifact_spike,
    "saturated_square": _saturated_square,
}

SIGNAL_KINDS: tuple[str, ...] = tuple(_GENERATORS)


def make_signal(kind: str, *, dt: float = 1e-3, duration: float = 2.0, seed: int = 0, **kw) -> Signal:
    """Build one labelled test signal. ``kw`` are the kind-specific parameters of the generator."""
    try:
        gen = _GENERATORS[kind]
    except KeyError:
        raise ValueError(f"unknown signal kind {kind!r}; choose from {SIGNAL_KINDS}") from None
    t = _time_grid(dt, duration)
    rng = np.random.default_rng(seed)
    x, truth = gen(t, rng, **kw)
    x = np.asarray(x, dtype=np.float64)
    if x.shape != t.shape:
        raise RuntimeError(f"generator {kind} returned shape {x.shape}, expected {t.shape}")
    truth = dict(truth, kind=kind, dt=float(dt), duration_s=float(len(t) * dt), seed=int(seed))
    return Signal(name=kind, t=t, x=x, dt=float(dt), truth=truth)


def all_signals(*, dt: float = 1e-3, duration: float = 2.0, seed: int = 0) -> list[Signal]:
    """One signal of every kind with default parameters."""
    return [make_signal(kind, dt=dt, duration=duration, seed=seed) for kind in SIGNAL_KINDS]
