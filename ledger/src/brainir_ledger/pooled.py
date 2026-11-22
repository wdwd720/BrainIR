"""PREREG v4 A6 / C1 fix 2: the rhythm score of the summed read-out signal of an accepted run, from its stored traces.

The stored `readout_traces` (run 1's `legs.pack_traces`, float32) hold the full-run traces (1 ms grid from t = 0) of the run's active
read-out motor neurons; inactive motor neurons (peak <= 0.01 Hz after 0.25 s) are not stored and are left out of the sum. The score is
the published per-trace autocorrelation score (`network_oscillation_score` on the single summed trace, t >= 0.25 s, prominence 0.05);
0 for an unusable replicate or when no motor neuron is active.
"""

from __future__ import annotations

import numpy as np
from brainir.metrics.rhythm import network_oscillation_score

from .legs import unpack_traces


def pooled_score(r: dict, prominence: float = 0.05, start_s: float = 0.25, dt: float = 0.001) -> float:
    ex = r.get("extras") or {}
    if not r.get("usable") or "readout_traces" not in ex:
        return 0.0
    tr = unpack_traces(ex["readout_traces"]).astype(np.float64)
    if tr.ndim != 2 or tr.shape[1] == 0:
        return 0.0
    s = tr.sum(axis=1)
    t = np.arange(len(s)) * dt
    w = s[t >= start_s - 1e-12][:, None]
    score, _f, _s, _fr = network_oscillation_score(w, np.array([True]), prominence)
    return float(score)
