"""Rhythm / activity metrics for simulated trajectories.

``rhythm`` re-implements the published rhythmicity score exactly (autocorrelation-peak based, normalised by a reference
sinusoid) and adds independent, differently-motivated measures (spectral peak, inter-peak regularity, envelope decay)
so that no single number decides whether a trace "oscillates".
"""

from .rhythm import (
    RhythmResult,
    envelope_decay,
    find_peaks_1d,
    interpeak_regularity,
    network_oscillation_score,
    neuron_oscillation_score,
    rhythm_report,
    spectral_peak,
)

__all__ = ["RhythmResult", "envelope_decay", "find_peaks_1d", "interpeak_regularity", "network_oscillation_score",
           "neuron_oscillation_score", "rhythm_report", "spectral_peak"]
