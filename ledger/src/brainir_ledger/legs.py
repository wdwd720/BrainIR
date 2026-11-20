"""Per-leg read-outs, leg signals and inter-leg phase for the full nerve cord (arm B3/B6) and the front-leg network.

Definitions follow the authors' own analysis code where it exists (repository smpuglie/Pugliese_2026 @ 10e7661):

* per-leg motor read-out (Figure 4 notebook, cell 7): motor neurons with a non-empty ``motor module`` in the leg's
  ``somaNeuromere`` (T1/T2/T3) and ``somaSide`` (LHS/RHS); score = the published network score over that leg's MNs that
  are active (peak > 0.01 Hz) after 250 ms;
* inter-leg phase (Extended Data Figure 8 notebook, cell 11): z-scored traces from sample 250 on; period of x1 = lag of the
  first autocorrelation peak with prominence >= 0.05 (``scipy.signal.find_peaks`` on the raw autocorrelation of the
  mean-subtracted signal); cross-correlation searched within +-1 period; offset / period * 2 pi wrapped to [-pi, pi);
  leg signal = each leg's copy of the published core excitatory interneuron (type looked up by the caller);
* the motor leg signal (version 2, pre-registered in PREREG.md): summed rate of the leg's active coxa-promotor MNs, with
  declared fallbacks.

Everything here is a deterministic function of a trajectory; nothing reads labels.
"""

from __future__ import annotations

import itertools
import zlib

import numpy as np
from brainir.metrics.rhythm import network_oscillation_score
from scipy import signal

LEGS = ("T1L", "T1R", "T2L", "T2R", "T3L", "T3R")
SEGMENT_PAIRS = {"front": ("T1L", "T1R"), "middle": ("T2L", "T2R"), "hind": ("T3L", "T3R")}
LEG_PAIRS = list(itertools.combinations(LEGS, 2))  # 15 unordered pairs, LEGS order
TRIPOD_A = {"T1L", "T2R", "T3L"}
TRIPOD_B = {"T1R", "T2L", "T3R"}
REPORTED_PAIRS = [("T1L", "T1R"), ("T2L", "T2R"), ("T3L", "T3R"), ("T1L", "T2L"), ("T2L", "T3L"), ("T1R", "T2R"), ("T2R", "T3R")]
PROMOTOR_TYPE = "Tergopleural/Pleural promotor MN"
SWING_MODULE = "coxa swing"


def leg_of(neuromere: str | None, side: str | None) -> str | None:
    if neuromere not in ("T1", "T2", "T3") or side not in ("LHS", "RHS"):
        return None
    return f"{neuromere}{side[0]}"


def leg_masks(table, n: int) -> dict[str, np.ndarray]:
    """Module-labelled MNs per leg from an authors'-style table (columns ``motor module``, ``somaNeuromere``, ``somaSide``)
    whose row order equals the network's positional order."""
    mod = table["motor module"].fillna("").astype(str).to_numpy()
    legs = np.array([leg_of(a, b) for a, b in zip(table["somaNeuromere"], table["somaSide"])], dtype=object)
    out = {}
    for leg in LEGS:
        m = (mod != "") & (legs == leg)
        out[leg] = m
    if len(mod) != n:
        raise ValueError("table rows must equal network size")
    return out


def leg_signal_groups(table) -> dict[str, dict[str, np.ndarray]]:
    """Per leg: the promotor MNs, the coxa-swing module MNs and all module MNs (positions)."""
    mod = table["motor module"].fillna("").astype(str).to_numpy()
    typ = table["type"].fillna("").astype(str).to_numpy()
    legs = np.array([leg_of(a, b) for a, b in zip(table["somaNeuromere"], table["somaSide"])], dtype=object)
    out = {}
    for leg in LEGS:
        inleg = (legs == leg) & (mod != "")
        out[leg] = {"promotor": np.flatnonzero(inleg & (typ == PROMOTOR_TYPE)),
                    "swing": np.flatnonzero(inleg & (mod == SWING_MODULE)),
                    "all": np.flatnonzero(inleg)}
    return out


def per_leg_scores(win: np.ndarray, masks: dict[str, np.ndarray], *, active_rate_hz: float, prominence: float, dt: float) -> dict:
    """Score, frequency and number of active MNs per leg and per segment pair (union of the two legs' MNs)."""
    peak = win.max(axis=0)
    act = peak > active_rate_hz
    out = {}
    groups = {leg: masks[leg] for leg in LEGS}
    groups.update({seg: masks[a] | masks[b] for seg, (a, b) in SEGMENT_PAIRS.items()})
    for name, m in groups.items():
        mk = act & m
        s, f, _, _ = network_oscillation_score(win, mk, prominence)
        out[name] = {"score": float(s), "frequency_hz": (f / dt if f > 0 else None), "n_active": int(mk.sum()), "n_mns": int(m.sum())}
    return out


def motor_leg_signal(win: np.ndarray, groups: dict[str, np.ndarray], *, active_rate_hz: float) -> tuple[np.ndarray, str]:
    """Version-2 leg signal: summed rate of the active promotor MNs; fallback 1: active coxa-swing module MNs; fallback 2:
    all active module MNs of the leg; else a zero signal ('none')."""
    peak = win.max(axis=0)
    for name in ("promotor", "swing", "all"):
        idx = groups[name]
        idx = idx[peak[idx] > active_rate_hz] if len(idx) else idx
        if len(idx):
            return win[:, idx].sum(axis=1), name
    return np.zeros(win.shape[0]), "none"


def estimate_period_autocorr(x: np.ndarray) -> float:
    """Authors' period estimator: first autocorrelation peak (lag > 0) with prominence >= 0.05; NaN if none."""
    norm_x = x - x.mean()
    ac = np.correlate(norm_x, norm_x, mode="full")
    ac = ac[len(ac) // 2:]
    peaks, _ = signal.find_peaks(ac, prominence=0.05)
    return float(peaks[0]) if len(peaks) > 0 else float("nan")


def _z(x: np.ndarray) -> np.ndarray | None:
    sd = float(np.std(x))
    if not np.isfinite(sd) or sd <= 0:
        return None
    return (x - np.mean(x)) / sd


def phase_offset(x1: np.ndarray, x2: np.ndarray) -> float:
    """Authors' phase offset of x2 relative to x1 in radians, wrapped to [-pi, pi); NaN when x1 has no period or either
    signal is flat."""
    a, b = _z(np.asarray(x1, float)), _z(np.asarray(x2, float))
    if a is None or b is None:
        return float("nan")
    per = estimate_period_autocorr(a)
    if not np.isfinite(per):
        return float("nan")
    per_i = int(per)
    xc = np.correlate(a, b, mode="full")
    center = len(a) - 1
    win = xc[center - per_i: center + per_i]
    if len(win) == 0:
        return float("nan")
    off = int(np.argmax(win)) - per_i
    ph = off / per_i * 2 * np.pi
    return float((ph + np.pi) % (2 * np.pi) - np.pi)


def pairwise_offsets(signals: dict[str, np.ndarray]) -> dict[str, float]:
    """Offsets for all 15 unordered leg pairs, keyed 'A-B' (offset of B relative to A)."""
    return {f"{a}-{b}": phase_offset(signals[a], signals[b]) for a, b in LEG_PAIRS}


def tripod_target(a: str, b: str) -> float:
    same = ({a, b} <= TRIPOD_A) or ({a, b} <= TRIPOD_B)
    return 0.0 if same else float(np.pi)


def tripod_index(offsets: dict[str, float], rhythmic: dict[str, bool], min_pairs: int = 3) -> float | None:
    """Mean of cos(offset - target) over the leg pairs whose legs both pass the rhythm threshold; None if fewer than
    ``min_pairs`` such pairs have a defined offset."""
    vals = []
    for a, b in LEG_PAIRS:
        o = offsets.get(f"{a}-{b}")
        if o is None or not np.isfinite(o) or not (rhythmic.get(a) and rhythmic.get(b)):
            continue
        vals.append(np.cos(o - tripod_target(a, b)))
    return float(np.mean(vals)) if len(vals) >= min_pairs else None


def resultant_length(angles) -> float | None:
    a = np.asarray([x for x in angles if x is not None and np.isfinite(x)], float)
    if len(a) == 0:
        return None
    return float(np.abs(np.mean(np.exp(1j * a))))


def random_derangement(n: int, rng: np.random.Generator) -> np.ndarray:
    """Uniform random permutation without fixed points (rejection sampling; n >= 2)."""
    while True:
        p = rng.permutation(n)
        if not np.any(p == np.arange(n)):
            return p


MIN_COUPLING_N = 8


def coupling(sig_a: list[np.ndarray], sig_b: list[np.ndarray], *, n_null: int = 1000, seed: int = 20261123) -> dict:
    """Coupling of a leg pair over eligible replicates (PREREG 4.7): R of the per-replicate offsets of leg B relative to leg A,
    against a replicate-shuffled null (leg B from another replicate, uniform random derangements). Needs n >= 8.

    ``sig_a[i]``, ``sig_b[i]``: leg-A / leg-B signals of eligible replicate i (both legs rhythmic)."""
    n = len(sig_a)
    out = {"n": n, "R": None, "circ_mean": None, "null_mean_R": None, "p": None, "coupled": None}
    if n < MIN_COUPLING_N:
        return out
    O = np.array([[phase_offset(sig_a[i], sig_b[j]) for j in range(n)] for i in range(n)])
    obs = np.array([O[i, i] for i in range(n)])
    ok = np.isfinite(obs)
    if ok.sum() < MIN_COUPLING_N:
        out["n"] = int(ok.sum())
        return out
    z = np.exp(1j * obs[ok]).mean()
    R = float(np.abs(z))
    rng = np.random.default_rng(seed)
    nulls = []
    idx = np.arange(n)
    for _ in range(n_null):
        p = random_derangement(n, rng)
        v = O[idx, p]
        v = v[np.isfinite(v)]
        nulls.append(float(np.abs(np.exp(1j * v).mean())) if len(v) else 0.0)
    nulls = np.array(nulls)
    pval = (1 + int((nulls >= R - 1e-12).sum())) / (1 + n_null)
    out.update(n=int(ok.sum()), R=R, circ_mean=float(np.angle(z)), null_mean_R=float(nulls.mean()), p=float(pval),
               coupled=bool(pval < 0.01 and R >= 0.5))
    return out


def pack_traces(arr: np.ndarray) -> dict:
    """float32 + zlib for storing traces in job results (columns = neurons)."""
    a = np.ascontiguousarray(arr, dtype=np.float32)
    return {"shape": list(a.shape), "dtype": "float32", "zlib": zlib.compress(a.tobytes(), 6)}


def unpack_traces(d: dict) -> np.ndarray:
    return np.frombuffer(zlib.decompress(d["zlib"]), dtype=np.float32).reshape(d["shape"])
