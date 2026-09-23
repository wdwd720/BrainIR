"""Rhythmicity metrics.

Section A re-implements the published score of Pugliese et al. (``src/utils/sim_utils.py`` of their repository; see
``research/literature/pugliese_model_spec_from_code.md`` section 5 for the line-referenced algorithm):

1. per trace: min-max normalise to [-1, 1] (NOT mean-subtracted; zero if range <= 1e-6), full FFT autocorrelation,
   normalise by max |ac|, keep non-negative lags, detect strict local maxima whose "prominence" (height above the higher
   of the global left/right minima) is >= 0.05, excluding lag 0; raw score = min(max height, max prominence) over the
   valid peaks (possibly two different peaks); frequency = 1 / lag of the most prominent peak (cycles per sample);
2. normalise the raw score by the same statistic of a pure sinusoid/cosine at that frequency over the same number of
   samples (max of the two), round to 1e-6, clip to [0, 1];
3. network score = mean over the masked (active motor) neurons, unmasked neurons contribute 0; mean frequency =
   nanmean over masked neurons with a detected peak.

Everything in section A is computed in float64 (the authors used float32 on GPU; agreement is expected to the 5th-6th
decimal, see spec section 5.6). ``dtype=np.float32`` reproduces their arithmetic more closely where it matters.

Section B adds independent measures used by the benchmark's metric suite.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy.signal import correlate, welch
from scipy.signal import find_peaks as sp_find_peaks

DEFAULT_PROMINENCE = 0.05
ACTIVE_RATE_HZ = 0.01
"""A neuron is 'active' when its peak rate in the analysis window exceeds this (paper convention)."""


# ---------------------------------------------------------------------------
# A. published score
# ---------------------------------------------------------------------------
def find_peaks_1d(x: np.ndarray, prominence_threshold: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Strict interior local maxima with 'global side-minima' prominence (the authors' definition, not SciPy's).

    Returns (indices, heights, prominences) of peaks whose prominence >= threshold."""
    x = np.asarray(x)
    n = len(x)
    if n < 3:
        return np.array([], int), np.array([]), np.array([])
    interior = np.arange(1, n - 1)
    is_peak = (x[1:-1] > x[:-2]) & (x[1:-1] > x[2:])
    left_min = np.minimum.accumulate(x)[:-2]            # min(x[0..i-1]) for i = 1..n-2
    right_min = np.minimum.accumulate(x[::-1])[::-1][2:]  # min(x[i+1..n-1]) for i = 1..n-2
    prom = x[1:-1] - np.maximum(left_min, right_min)
    keep = is_peak & (prom >= prominence_threshold)
    return interior[keep], x[1:-1][keep], prom[keep]


def _raw_score(x: np.ndarray, prominence: float) -> tuple[float, float]:
    x = np.asarray(x, dtype=x.dtype if np.issubdtype(np.asarray(x).dtype, np.floating) else np.float64)
    x = np.clip(np.round(x * 1e10) / 1e10, -1e6, 1e6)
    rng = x.max() - x.min()
    if rng > 1e-6:
        xn = 2.0 * (x - x.min()) / rng - 1.0
    else:
        xn = np.zeros_like(x)
    ac = correlate(xn, xn, mode="full", method="fft")
    ac = np.clip(np.round(ac * 1e10) / 1e10, -1e6, 1e6)
    m = np.abs(ac).max()
    if m > 1e-6:
        ac = ac / m
    ac = ac[(len(ac) - 1) // 2:]
    idx, height, prom = find_peaks_1d(ac, prominence)
    valid = idx > 0
    if not valid.any():
        return 0.0, 0.0
    idx, height, prom = idx[valid], height[valid], prom[valid]
    raw = float(min(height.max(), prom.max()))
    raw = float(np.clip(np.round(raw * 1e10) / 1e10, 0.0, 1e6))
    best = int(np.argmax(prom))
    f = 1.0 / float(idx[best])
    f = float(np.clip(np.round(f * 1e10) / 1e10, 1e-6, 1e6))
    return raw, f


def neuron_oscillation_score(x: np.ndarray, prominence: float = DEFAULT_PROMINENCE, dtype=np.float64) -> tuple[float, float]:
    """Published per-trace score in [0, 1] and frequency in cycles per sample (0 when no peak)."""
    x = np.asarray(x, dtype=dtype)
    raw, f = _raw_score(x, prominence)
    if raw > 1e-6 and np.isfinite(f):
        t = np.arange(len(x), dtype=dtype)
        ref_s, _ = _raw_score(np.sin(2 * np.pi * f * t).astype(dtype), prominence)
        ref_c, _ = _raw_score(np.cos(2 * np.pi * f * t).astype(dtype), prominence)
        ref = max(ref_s, ref_c)
        score = raw / ref if ref > 1e-6 else 0.0
    else:
        score = 0.0
    return float(np.clip(np.round(score * 1e6) / 1e6, 0.0, 1.0)), f


def network_oscillation_score(activity: np.ndarray, mask: np.ndarray, prominence: float = DEFAULT_PROMINENCE,
                              dtype=np.float64) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Published simulation-level score.

    ``activity``: rates with shape (T, N) over the analysis window (the authors use t >= 0.25 s); ``mask``: bool (N,) of
    neurons to average over (active motor neurons). Returns (score, mean frequency in cycles/sample, per-neuron scores,
    per-neuron frequencies)."""
    activity = np.asarray(activity, dtype=dtype)
    mask = np.asarray(mask, dtype=bool)
    n = activity.shape[1]
    scores = np.zeros(n)
    freqs = np.full(n, np.nan)
    for i in np.flatnonzero(mask):
        s, f = neuron_oscillation_score(activity[:, i], prominence, dtype)
        scores[i] = s
        freqs[i] = f
    n_act = int(mask.sum())
    if n_act == 0:
        return 0.0, 0.0, scores, freqs
    sim_score = float(scores[mask].sum() / n_act)
    fm = freqs[mask]
    fm = fm[np.isfinite(fm) & (fm != 0)]
    mean_f = float(np.mean(fm)) if len(fm) else 0.0
    return sim_score, mean_f, scores, freqs


# ---------------------------------------------------------------------------
# B. independent measures
# ---------------------------------------------------------------------------
def spectral_peak(x: np.ndarray, dt: float, f_min: float = 0.5, f_max: float | None = None) -> dict:
    """Welch PSD peak: frequency, and peak power relative to the median PSD (a crude SNR) and to total power."""
    x = np.asarray(x, dtype=np.float64)
    x = x - x.mean()
    if not np.all(np.isfinite(x)) or x.std() == 0:
        return {"frequency_hz": None, "peak_to_median": 0.0, "peak_fraction": 0.0}
    nper = min(len(x), max(64, len(x) // 2))
    f, p = welch(x, fs=1.0 / dt, nperseg=nper)
    hi = f_max if f_max is not None else f.max()
    band = (f >= f_min) & (f <= hi)
    if not band.any():
        return {"frequency_hz": None, "peak_to_median": 0.0, "peak_fraction": 0.0}
    fb, pb = f[band], p[band]
    k = int(np.argmax(pb))
    med = float(np.median(pb))
    return {"frequency_hz": float(fb[k]), "peak_to_median": float(pb[k] / med) if med > 0 else float("inf"),
            "peak_fraction": float(pb[k] / pb.sum()) if pb.sum() > 0 else 0.0}


def interpeak_regularity(x: np.ndarray, dt: float, min_rel_prominence: float = 0.2) -> dict:
    """Peaks of the trace itself (SciPy prominence >= fraction of range; plateaus/clipped tops count once): count, mean
    interval, CV of intervals."""
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        return {"n_peaks": 0, "mean_interval_s": None, "cv": None, "frequency_hz": None}
    rng = x.max() - x.min()
    if rng <= 1e-9:
        return {"n_peaks": 0, "mean_interval_s": None, "cv": None, "frequency_hz": None}
    idx, _ = sp_find_peaks(x, prominence=min_rel_prominence * rng)
    if len(idx) < 3:
        return {"n_peaks": int(len(idx)), "mean_interval_s": None, "cv": None, "frequency_hz": None}
    iv = np.diff(idx) * dt
    return {"n_peaks": int(len(idx)), "mean_interval_s": float(iv.mean()), "cv": float(iv.std() / iv.mean()),
            "frequency_hz": float(1.0 / iv.mean())}


def envelope_decay(x: np.ndarray) -> dict:
    """Peak-to-trough amplitude in the last third of the window relative to the first third (1 = sustained, ~0 = died)."""
    x = np.asarray(x, dtype=np.float64)
    if not np.all(np.isfinite(x)) or len(x) < 9:
        return {"late_over_early": None}
    k = len(x) // 3
    early, late = x[:k], x[-k:]
    a0, a1 = early.max() - early.min(), late.max() - late.min()
    return {"late_over_early": float(a1 / a0) if a0 > 1e-9 else (1.0 if a1 <= 1e-9 else float("inf"))}


@dataclass(frozen=True)
class RhythmResult:
    paper_score: float
    paper_frequency_hz: float | None
    spectral_frequency_hz: float | None
    spectral_peak_to_median: float
    interpeak_cv: float | None
    interpeak_frequency_hz: float | None
    n_peaks: int
    late_over_early: float | None
    finite: bool
    range_hz: float

    def to_dict(self) -> dict:
        return asdict(self)

    def is_sustained_rhythm(self, *, min_score: float = 0.5, min_range_hz: float = 1.0, min_late_over_early: float = 0.5,
                            max_interpeak_cv: float | None = 0.35, min_peaks: int = 3) -> bool:
        """Conservative composite decision. The published score alone is amplitude-blind (min-max normalisation) and
        cannot tell a damped transient from a sustained oscillation over a fixed window; this adds an amplitude gate,
        an envelope-persistence gate and (optionally) an inter-peak regularity gate."""
        if not self.finite or self.paper_score < min_score or self.range_hz < min_range_hz:
            return False
        if self.late_over_early is None or self.late_over_early < min_late_over_early:
            return False
        if self.n_peaks < min_peaks:
            return False
        if max_interpeak_cv is not None and (self.interpeak_cv is None or self.interpeak_cv > max_interpeak_cv):
            return False
        return True


def rhythm_report(x: np.ndarray, dt: float, prominence: float = DEFAULT_PROMINENCE) -> RhythmResult:
    """All metrics for one trace over the analysis window (already cropped by the caller)."""
    x = np.asarray(x, dtype=np.float64)
    finite = bool(np.all(np.isfinite(x)))
    xf = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    s, f = neuron_oscillation_score(xf, prominence)
    spec = spectral_peak(xf, dt)
    ipr = interpeak_regularity(xf, dt)
    env = envelope_decay(xf)
    return RhythmResult(paper_score=s, paper_frequency_hz=(f / dt) if f > 0 else None,
                        spectral_frequency_hz=spec["frequency_hz"], spectral_peak_to_median=spec["peak_to_median"],
                        interpeak_cv=ipr["cv"], interpeak_frequency_hz=ipr["frequency_hz"], n_peaks=ipr["n_peaks"],
                        late_over_early=env["late_over_early"], finite=finite, range_hz=float(xf.max() - xf.min()))
