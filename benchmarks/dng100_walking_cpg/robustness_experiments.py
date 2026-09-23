"""Numerical-convergence, robustness and negative-control experiments for the DNg100 activation protocol.

ANSWER-KEY-ADJACENT benchmark tooling: lives only under ``benchmarks/dng100_walking_cpg/`` and is never imported by
``src/``. The scripts need no circuit identity at all: the stimulus is the DNg100 used by ``reproduce_dynamics.py``
(the benchmark's *input*), the readout is the front-leg motor-neuron population, and every manipulation acts on the
whole signed count matrix. Anatomy (synapse counts), ML predictions (neurotransmitter labels -> signs) and model
parameters are kept apart in every output: ``network`` blocks describe counts and sign rows, ``model_config`` blocks
describe the assumed parameters, and no count is ever called a strength.

    uv run python benchmarks/dng100_walking_cpg/robustness_experiments.py dt-convergence --n 8 --workers 6
    uv run python benchmarks/dng100_walking_cpg/robustness_experiments.py param-sweep --n 24
    uv run python benchmarks/dng100_walking_cpg/robustness_experiments.py input-sweep --n 32
    uv run python benchmarks/dng100_walking_cpg/robustness_experiments.py weight-noise --n 24
    uv run python benchmarks/dng100_walking_cpg/robustness_experiments.py negative-controls --n 24

Every subcommand writes ``results/<name>.json`` (configuration, per-condition summaries, per-replicate scalars, seeds;
never trajectories) and ``results/<name>.md`` (a compact table, also printed); ``resummarize results/x.json`` recomputes
the summaries and the table from the stored scalars without simulating. Default network: ``manc:v1.2.1`` with
the authors' neurotransmitter labels (``--nt paper``), built by ``reproduce_dynamics.paper_network``. Replicate ``k``
of every condition uses parameter seed ``seed0 + k`` (and the same seed for any per-replicate randomness: weight noise,
control-network construction), so conditions are paired.

Subcommands
-----------
``dt-convergence`` (workstream 18, numerical correctness). The same replicate (same seed, W, stimulus) is integrated
with several schemes and compared with RK45 at rtol 1e-8 / atol 1e-11 (the reference; its own error is estimated as
|RK45 default - reference| x (1e-8 / 2e-6), the usual proportionality of adaptive-solver error to the tolerance).
  Part A, order study: RK45 at the authors' tolerances (rtol 2e-6, atol 5e-9), DOP853 at the same tolerances,
  fixed-step RK4 at dt = 1e-3, 5e-4, 2.5e-4, 1.25e-4 s and forward Euler at 1e-3 and 1e-4 s, with the pulse on for the
  whole run (``pulse_start = 0``, ``pulse_end = t_end``). This is the standard replicate shifted by 20 ms: r = 0 is an
  exact fixed point of the unstimulated network, so the standard protocol's first 20 ms are identically zero and the
  trajectory from the pulse onset is the same. Keeping the pulse edges out of the run matters for fixed-step schemes:
  ``_fixed_step`` in ``brainir.sim.model`` evaluates the pulse indicator at the stage times, so the k4 stage of the step
  that ends exactly at pulse_start (and the k1 stage of the step that starts at pulse_end) sees the other side of the
  switch; that is an O(dt) error of about (dt / 6) x (activation / tau) ~ 0.13 Hz at dt = 1 ms on the stimulated neuron,
  which propagates into the oscillation phase and hides the scheme's order. Reported per method: max |dr| and RMS dr
  over the whole run, over the analysis window (t >= 0.25 s) and over the first 0.3 s (before the accumulated phase
  drift of the oscillation dominates the difference), the published score, the mean MN frequency, RHS evaluations and
  wall time; plus the empirical convergence order from successive halvings of dt (RK4) and from the decade
  1e-3 -> 1e-4 (Euler). ``--reference-rtol/--reference-atol`` tighten the reference (the standard 1e-8 / 1e-11 RK45
  is then included as a compared method, which measures its own error).
  Part B, protocol edges: the standard protocol (pulse 0.02 s -> t_end - 1 ms) integrated segment-wise and as a single
  interval with RK45 (``integration="segments"`` vs ``"single"``), plus RK4 at 1e-3 and 5e-4 s to quantify the
  edge artefact above (the error at the onset sample and at the final sample are reported separately). Differences are
  taken over t <= pulse_end.

``param-sweep`` (workstream 17, robustness). Model-parameter conditions, n = 24 replicates each, all against the same
stimulus. Ranges are anchored on the authors' defaults (``configs/neuron_params/default.yaml``, spec section 3.2:
tau = 20 +/- 2 ms, a = 1 +/- 0.1, theta = 7.5 +/- 0.6, r_max = 200 +/- 10, b = 0.03 for both signs):
  * ``widen``: all four standard deviations scaled jointly by 0, 0.5, 1, 1.5, 2, 3. The paper's Extended Data Fig. 2a-c
    widened all distributions up to 3x SD (DNg100 at 3x: mean score 0.669, 70.8 % >= 0.5; restoring one parameter's SD:
    gain 0.862, threshold 0.754, tau 0.703, r_max 0.669) and called the gain the most sensitive parameter. Factor 0
    makes every replicate identical (parameters at their means, still size-scaled), so it is run with 2 seeds only.
  * ``a`` (gain mean) in {0.5, 0.75, 1, 1.25, 1.5}: +/- 50 % of the default initial slope of the nonlinearity; the
    per-neuron sd stays 0.1 and the size scaling (a / s) is kept.
  * ``theta`` (threshold mean) in {5, 6.5, 7.5, 8.5, 10}: about +/- 1/3 of the default (sd 0.6 kept, theta * s kept).
  * ``r_max`` in {100, 150, 200, 300}: exactly the +/- 10 sd truncation range of the default distribution (spec 3.2).
  * ``tau`` in {10, 15, 20, 30, 40} ms: halving to doubling of the only time scale of the model (sd 2 ms kept); the
    oscillation frequency is expected to scale roughly with 1 / tau.
  * ``b`` in {0.015, 0.02, 0.03, 0.04, 0.06} (b_exc = b_inh): 0.5x to 2x. The paper's Extended Data Fig. 2e found
    b_ACh = 0.045 still viable and larger deviations giving runaway activity or insufficient recruitment.
  The default configuration is shared by all families and simulated once.

``input-sweep``: stimulus amplitude in {180, 220, 250, 260, 300, 340} (the paper's Fig. 2g sweep 180-340 plus the
standard 250). The paper reports median MN frequencies 9.6 Hz (220), 11.0 (260), 12.0 (300), 12.7 (340) and mostly no
active MN at 180; its sweep stimulated both DNg100 axons, this script stimulates the single DNg100 of the standard
protocol unless ``--stim-positions`` says otherwise. Default n = 32.

``weight-noise``: multiplicative count noise w (1 + eta), eta ~ truncated normal(0, sigma), eta >= -1, drawn per
replicate (``Intervention(weight_noise_sd=sigma, weight_noise_seed=seed)``), sigma in {0, 0.05, 0.1, 0.15, 0.2, 0.3,
0.5}. Paper (Fig. 2f, n = 512): mean scores 0.974, 0.965, 0.954, 0.884, 0.814, 0.669, 0.435. n = 24.

``negative-controls`` (workstream 27): for seed k a control matrix is built from the same signed count matrix with
seed k and simulated with parameter seed k; controls are
  (a) ``class_shuffle``: the paper's simulation-time ``full_shuffle`` (spec 9.1). Within each of the five postsynaptic
      classes (excitatory DNs, non-excitatory DNs, excitatory interneurons = everything that is neither DN nor MN,
      non-excitatory interneurons, motor neurons; excitatory = sign +1, i.e. predicted cholinergic) the complete input
      vectors are reassigned among the class members. In the authors' pre x post orientation that is a permutation of
      columns; our W is post x pre, so it is a permutation of rows within each class. Preserved exactly: every column
      (each presynaptic neuron's outputs, hence its sign and out-degree), each class's multiset of input vectors (in-degree
      and in-count distributions), class membership. Destroyed: which neuron of a class receives a given input vector.
      As in the authors' code the diagonal is not re-zeroed afterwards (a neuron may inherit a synapse from itself).
  (b) ``degree_rewire``: degree-preserving rewiring of the whole graph, 10 x E attempted target swaps
      (a->b, c->d) -> (a->d, c->b), rejected when it would create a self-loop or a duplicate edge. Each count stays with
      its presynaptic neuron, so in-degree and out-degree sequences and the sign of every neuron's outputs are preserved.
  (c) ``sign_shuffle``: the +1 / -1 signs are permuted among the presynaptic neurons that have outputs (counts of each
      sign preserved); the stimulated neuron keeps its sign so that the control is not trivially silent.
  (d) ``weight_permute``: same sparsity pattern and signs, the multiset of synapse counts permuted among the edges.
  (e) ``intact``: the unmodified network (positive control).
  Reported per control: score distribution, fraction >= 0.5, fraction of replicates with at least one readout MN that
  passes the stricter sustained-rhythm gate (``RhythmResult.is_sustained_rhythm``: amplitude, persistence and
  regularity gates, LOG D30), median MN frequency, median active MNs and active neurons overall.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import scipy.sparse as sp

from brainir.metrics.rhythm import ACTIVE_RATE_HZ, rhythm_report
from brainir.sim.experiments import ANALYSIS_START_S, _run_replicate, score_trajectory
from brainir.sim.model import MODEL_ID, Intervention, ModelConfig, Stimulus, sample_neuron_params, simulate

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE))

SCORE_THRESHOLD = 0.5
CONTROLS: tuple[str, ...] = ("intact", "class_shuffle", "degree_rewire", "sign_shuffle", "weight_permute")

# published comparison values (distributional; the paper used n = 512-1024 replicates)
PAPER_INPUT_SWEEP_FREQ_HZ = {220: 9.6, 260: 11.0, 300: 12.0, 340: 12.7}
PAPER_INPUT_SWEEP_NOTE = {180: "mostly no active MN"}
PAPER_WEIGHT_NOISE_MEAN = {0.0: 0.974, 0.05: 0.965, 0.1: 0.954, 0.15: 0.884, 0.2: 0.814, 0.3: 0.669, 0.5: 0.435}
PAPER_WIDEN = {3.0: {"mean": 0.669, "fraction_ge_0_5": 0.708}}
PAPER_WIDEN_RESTORE = {"a": 0.862, "theta": 0.754, "tau": 0.703, "r_max": 0.669}

# dt-convergence conditions: (label, family, ModelConfig overrides). The reference is the tight-tolerance RK45.
REFERENCE_METHOD = ("RK45 rtol 1e-8 atol 1e-11 (reference)", "reference", {"rtol": 1e-8, "atol": 1e-11})
ORDER_STUDY_METHODS: list[tuple[str, str, dict]] = [  # part A: pulse on throughout, no discontinuity inside the run
    ("RK45 rtol 2e-6 atol 5e-9 (default)", "adaptive", {}),
    ("DOP853 rtol 2e-6 atol 5e-9", "adaptive", {"method": "DOP853"}),
    ("RK4 dt 1e-3", "rk4", {"method": "rk4", "dt": 1e-3}),
    ("RK4 dt 5e-4", "rk4", {"method": "rk4", "dt": 5e-4}),
    ("RK4 dt 2.5e-4", "rk4", {"method": "rk4", "dt": 2.5e-4}),
    ("RK4 dt 1.25e-4", "rk4", {"method": "rk4", "dt": 1.25e-4}),
    ("Euler dt 1e-3", "euler", {"method": "euler", "dt": 1e-3}),
    ("Euler dt 1e-4", "euler", {"method": "euler", "dt": 1e-4}),
]
PROTOCOL_METHODS: list[tuple[str, str, dict]] = [  # part B: the standard protocol with its pulse edges at 0.02 s and T - 1 ms
    ("RK45 default, segments", "adaptive", {}),
    ("RK45 default, single interval", "adaptive", {"integration": "single"}),
    ("RK4 dt 1e-3", "rk4", {"method": "rk4", "dt": 1e-3}),
    ("RK4 dt 5e-4", "rk4", {"method": "rk4", "dt": 5e-4}),
]

PARAM_FAMILIES: dict[str, list[float]] = {
    "widen": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0],
    "a": [0.5, 0.75, 1.0, 1.25, 1.5],
    "theta": [5.0, 6.5, 7.5, 8.5, 10.0],
    "r_max": [100.0, 150.0, 200.0, 300.0],
    "tau": [0.010, 0.015, 0.020, 0.030, 0.040],
    "b": [0.015, 0.02, 0.03, 0.04, 0.06],
}
INPUT_CURRENTS = [180.0, 220.0, 250.0, 260.0, 300.0, 340.0]
NOISE_SIGMAS = [0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]


# ---------------------------------------------------------------------------
# control-network generators (pure functions of (W, seed); all return CSR, never mutate the input)
# ---------------------------------------------------------------------------
def paper_shuffle_classes(super_class: np.ndarray, signs: np.ndarray) -> np.ndarray:
    """The five postsynaptic classes of the authors' ``extract_shuffle_indices`` (spec 9.1) as a label per neuron:
    ``exc_dn`` / ``inh_dn`` (descending neurons by sign +1 vs anything else), ``exc_in`` / ``inh_in`` (every neuron
    that is neither descending nor motor), ``mn`` (motor neurons)."""
    sc = np.asarray(super_class).astype(str)
    exc = np.asarray(signs) > 0
    labels = np.where(exc, "exc_in", "inh_in").astype(object)
    dn = sc == "descending_neuron"
    labels[dn & exc] = "exc_dn"
    labels[dn & ~exc] = "inh_dn"
    labels[sc == "motor_neuron"] = "mn"
    return labels.astype(str)


def class_shuffle(W: sp.spmatrix | np.ndarray, labels: np.ndarray, seed: int) -> sp.csr_matrix:
    """Permute the rows (postsynaptic input vectors) of the post x pre matrix within each label group.

    Equivalent to the authors' ``full_shuffle`` (which permutes columns of their pre x post matrix within the groups).
    Groups are processed in sorted label order with one ``numpy.random.default_rng(seed)`` stream."""
    W = sp.csr_matrix(W)
    n = W.shape[0]
    labels = np.asarray(labels).astype(str)
    if labels.shape != (n,):
        raise ValueError(f"labels has shape {labels.shape}, expected ({n},)")
    rng = np.random.default_rng(seed)
    perm = np.arange(n)
    for lab in np.unique(labels):
        idx = np.flatnonzero(labels == lab)
        perm[idx] = rng.permutation(idx)  # row i takes the input vector of row perm[i] (same class)
    out = W[perm, :].tocsr()
    out.sort_indices()
    return out


def degree_preserving_rewire(W: sp.spmatrix | np.ndarray, seed: int, swaps_per_edge: float = 10.0,
                             return_stats: bool = False) -> sp.csr_matrix | tuple[sp.csr_matrix, dict]:
    """Directed degree-preserving rewiring by target swaps: (a->b, c->d) -> (a->d, c->b).

    ``round(swaps_per_edge * E)`` swaps are attempted; a swap is rejected when the two edges share an endpoint role that
    would make it a no-op (a == c or b == d), would create a self-loop (a == d or c == b) or a duplicate edge. Each
    count keeps its presynaptic neuron, so out-degree, in-degree and every column's sign are preserved exactly (the
    in-count of a neuron changes, its in-degree does not)."""
    C = sp.coo_matrix(W)
    n = C.shape[0]
    pre = C.col.astype(np.int64).tolist()
    post = C.row.astype(np.int64).tolist()
    vals = C.data.copy()
    n_edges = len(vals)
    rng = np.random.default_rng(seed)
    n_attempts = int(round(swaps_per_edge * n_edges))
    edges = {a * n + b for a, b in zip(pre, post)}
    if len(edges) != n_edges:
        raise ValueError("duplicate entries in W")
    n_ok = 0
    if n_edges >= 2 and n_attempts > 0:
        picks = rng.integers(0, n_edges, size=(n_attempts, 2)).tolist()
        for i, j in picks:
            a, b, c, d = pre[i], post[i], pre[j], post[j]
            if a == c or b == d or a == d or c == b:
                continue
            k1, k2 = a * n + d, c * n + b
            if k1 in edges or k2 in edges:
                continue
            edges.remove(a * n + b)
            edges.remove(c * n + d)
            edges.add(k1)
            edges.add(k2)
            post[i], post[j] = d, b
            n_ok += 1
    out = sp.csr_matrix((vals, (np.asarray(post, dtype=np.int64), np.asarray(pre, dtype=np.int64))), shape=(n, n))
    out.sort_indices()
    stats = {"n_edges": int(n_edges), "n_attempted": int(n_attempts), "n_swapped": int(n_ok)}
    return (out, stats) if return_stats else out


def column_signs(W: sp.spmatrix | np.ndarray) -> np.ndarray:
    """Sign (+1 / -1 / 0) of each presynaptic column; raises if a column mixes signs."""
    C = sp.csc_matrix(W)
    n = C.shape[1]
    signs = np.zeros(n, dtype=np.int8)
    s = np.sign(C.data)
    for j in range(n):
        seg = s[C.indptr[j]:C.indptr[j + 1]]
        if len(seg) == 0:
            continue
        if seg.min() != seg.max():
            raise ValueError(f"presynaptic column {j} mixes signs")
        signs[j] = int(seg[0])
    return signs


def sign_shuffle(W: sp.spmatrix | np.ndarray, seed: int, fixed: tuple[int, ...] = ()) -> sp.csr_matrix:
    """Permute the +1 / -1 output signs among the presynaptic neurons that have outputs (``fixed`` keep theirs).

    Magnitudes and the sparsity pattern are untouched, so the counts of positive and negative columns are preserved."""
    C = sp.csc_matrix(W)
    signs = column_signs(C).astype(np.float64)
    movable = np.flatnonzero(signs != 0)
    if len(fixed):
        movable = movable[~np.isin(movable, np.asarray(fixed, dtype=np.int64))]
    rng = np.random.default_rng(seed)
    new = signs.copy()
    new[movable] = signs[rng.permutation(movable)]
    out = (abs(C) @ sp.diags(new)).tocsr()
    out.eliminate_zeros()
    out.sort_indices()
    return out


def permute_weights(W: sp.spmatrix | np.ndarray, seed: int) -> sp.csr_matrix:
    """Same sparsity pattern and signs; the multiset of synapse counts is permuted among the existing edges."""
    C = sp.csr_matrix(W, copy=True)
    C.sort_indices()
    rng = np.random.default_rng(seed)
    C.data = rng.permutation(np.abs(C.data)) * np.sign(C.data)
    return C


def build_control(W: sp.spmatrix, kind: str, seed: int, *, labels: np.ndarray | None = None, swaps_per_edge: float = 10.0,
                  fixed: tuple[int, ...] = ()) -> tuple[sp.csr_matrix, dict]:
    """Dispatch to the generators; returns (matrix, construction statistics)."""
    W = sp.csr_matrix(W)
    if kind == "intact":
        return W, {}
    if kind == "class_shuffle":
        if labels is None:
            raise ValueError("class_shuffle needs labels")
        out = class_shuffle(W, labels, seed)
        return out, {"n_diagonal_entries": int(np.count_nonzero(out.diagonal()))}
    if kind == "degree_rewire":
        return degree_preserving_rewire(W, seed, swaps_per_edge, return_stats=True)
    if kind == "sign_shuffle":
        out = sign_shuffle(W, seed, fixed)
        cs = column_signs(out)
        return out, {"n_positive_columns": int((cs > 0).sum()), "n_negative_columns": int((cs < 0).sum())}
    if kind == "weight_permute":
        return permute_weights(W, seed), {}
    raise ValueError(f"unknown control {kind!r}; choose from {CONTROLS}")


# ---------------------------------------------------------------------------
# replicate runner (process pool; the base matrix is shipped once per worker)
# ---------------------------------------------------------------------------
_WORKER: dict = {}


def _init_worker(W, sizes, readout_mask) -> None:
    _WORKER["W"] = sp.csr_matrix(W)
    _WORKER["sizes"] = sizes
    _WORKER["readout"] = np.asarray(readout_mask, dtype=bool)


def readout_persistence(traj, readout_mask: np.ndarray) -> dict:
    """Stricter, amplitude-aware view of the readout (LOG D30): how many active readout neurons pass
    ``RhythmResult.is_sustained_rhythm`` and the largest peak-to-trough range among them."""
    win = traj.window(ANALYSIS_START_S)
    dt = float(traj.t[1] - traj.t[0])
    active = (win.max(axis=0) > ACTIVE_RATE_HZ) & np.asarray(readout_mask, dtype=bool)
    n_sust, ranges = 0, []
    for i in np.flatnonzero(active):
        rr = rhythm_report(win[:, i], dt)
        n_sust += int(rr.is_sustained_rhythm())
        ranges.append(rr.range_hz)
    return {"n_sustained_readout": int(n_sust), "readout_range_hz_max": float(max(ranges)) if ranges else 0.0}


def _replicate_job(job: dict) -> dict:
    W, sizes, readout = _WORKER["W"], _WORKER["sizes"], _WORKER["readout"]
    stats = {}
    if job.get("control") is not None:
        W, stats = build_control(W, job["control"], int(job["seed"]), **job.get("control_kwargs", {}))
    rep, traj = _run_replicate((W, job["cfg"], job["stim"], job.get("intervention"), sizes, readout, int(job["seed"]), True))
    out = rep.to_dict()
    out.update(readout_persistence(traj, readout))
    out["condition"] = job["condition"]
    if stats:
        out["control_stats"] = stats
    return out


def run_jobs(jobs: list[dict], W, sizes, readout_mask, n_workers: int, label: str = "") -> list[dict]:
    t0 = time.time()
    out: list[dict] = []
    if n_workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=int(n_workers), initializer=_init_worker, initargs=(W, sizes, readout_mask)) as ex:
            for k, r in enumerate(ex.map(_replicate_job, jobs, chunksize=1), 1):
                out.append(r)
                if k % 24 == 0 or k == len(jobs):
                    print(f"  [{label}] {k}/{len(jobs)} replicates, {time.time() - t0:.0f} s", flush=True)
    else:
        _init_worker(W, sizes, readout_mask)
        for k, j in enumerate(jobs, 1):
            out.append(_replicate_job(j))
            if k % 8 == 0 or k == len(jobs):
                print(f"  [{label}] {k}/{len(jobs)} replicates, {time.time() - t0:.0f} s", flush=True)
    return out


def summarize(reps: list[dict], threshold: float = SCORE_THRESHOLD) -> dict:
    """Condition summary (mirrors ``ExperimentResult.summary`` and adds the sustained-rhythm and recruitment views)."""
    s = np.array([r["score"] for r in reps], dtype=float)
    f = np.array([np.nan if r["mean_frequency_hz"] is None else r["mean_frequency_hz"] for r in reps], dtype=float)
    act = np.array([r["n_active_readout"] for r in reps])
    act_all = np.array([r["n_active_all"] for r in reps])
    sust = np.array([r["n_sustained_readout"] for r in reps])
    return {"n_replicates": int(len(s)), "score_mean": float(s.mean()), "score_median": float(np.median(s)),
            "score_min": float(s.min()), "fraction_ge_threshold": float((s >= threshold).mean()), "threshold": threshold,
            "fraction_any_sustained": float((sust > 0).mean()), "sustained_readout_median": float(np.median(sust)),
            "sustained_fraction_median": float(np.median(sust / np.maximum(act, 1))),
            "frequency_median_hz": float(np.nanmedian(f)) if np.isfinite(f).any() else None,
            "frequency_iqr_hz": [float(np.nanpercentile(f, 25)), float(np.nanpercentile(f, 75))] if np.isfinite(f).any() else None,
            "active_readout_median": float(np.median(act)), "active_readout_range": [int(act.min()), int(act.max())],
            "active_all_median": float(np.median(act_all)), "active_all_range": [int(act_all.min()), int(act_all.max())],
            "solver_failures": int(sum(not r["solver_success"] for r in reps)),
            "wall_time_s": float(sum(r["wall_time_s"] for r in reps))}


def group_by_condition(results: list[dict], conditions: list[dict]) -> list[dict]:
    out = []
    for c in conditions:
        reps = [r for r in results if r["condition"] == c["label"]]
        out.append({**c, "summary": summarize(reps), "replicates": [{k: v for k, v in r.items() if k != "condition"} for r in reps]})
    return out


def _fmt(x, nd=3, none="-") -> str:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return none
    return f"{x:.{nd}f}"


def condition_row(label: str, s: dict, extra: str = "") -> str:
    rng_ = s["active_readout_range"]
    return (f"| {label} | {s['n_replicates']} | {_fmt(s['score_mean'])} | {_fmt(s['score_median'])} | {_fmt(s['fraction_ge_threshold'])} | "
            f"{_fmt(s.get('sustained_fraction_median'), 2)} | {_fmt(s['frequency_median_hz'], 2)} | {_fmt(s['active_readout_median'], 0)} "
            f"({rng_[0]}-{rng_[1]}) | {_fmt(s['active_all_median'], 0)} | {extra} |")


CONDITION_HEADER = ["| condition | n | mean score | median score | frac >= 0.5 | sustained / active MNs (median) | median MN f (Hz) | "
                    "median active MNs (range) | median active neurons | paper |", "|---|---|---|---|---|---|---|---|---|---|"]
TITLES = {"dt-convergence": "Integrator and step-size convergence on the same replicate",
          "param-sweep": "Model-parameter sweep (DNg100 activation)", "input-sweep": "Stimulus-amplitude sweep (DNg100 activation)",
          "weight-noise": "Multiplicative synapse-count noise (DNg100 activation)",
          "negative-controls": "Negative controls (DNg100 activation on manipulated networks)"}


def paper_note(experiment: str, g: dict) -> str:
    """Published comparison value for a condition (distributional; the paper used n = 512-1024 replicates)."""
    if experiment == "param-sweep":
        if g.get("family") == "widen" and g.get("value") in PAPER_WIDEN:
            p = PAPER_WIDEN[g["value"]]
            return f"3x SD: mean {p['mean']}, {p['fraction_ge_0_5']:.1%} >= 0.5"
        if g.get("family") == "widen" and g.get("value") == 1.0:
            return "default: mean 0.974, 99.8 % >= 0.5"
    elif experiment == "input-sweep":
        c = int(round(g["current"]))
        if c in PAPER_INPUT_SWEEP_FREQ_HZ:
            return f"median MN f {PAPER_INPUT_SWEEP_FREQ_HZ[c]} Hz (both DNg100s, n = 512)"
        return PAPER_INPUT_SWEEP_NOTE.get(c, "")
    elif experiment == "weight-noise":
        p = PAPER_WEIGHT_NOISE_MEAN.get(round(g["weight_noise_sd"], 3))
        return f"mean score {p}" if p is not None else ""
    elif experiment == "negative-controls":
        return construction_note(g)
    return ""


def construction_note(g: dict) -> str:
    c = g.get("construction", {})
    if g.get("control") == "degree_rewire":
        return f"{c.get('n_swapped_mean', 0):.0f} of {c.get('n_attempted', 0)} swaps accepted"
    if g.get("control") == "class_shuffle":
        return f"{c.get('n_diagonal_entries_mean', 0):.0f} diagonal entries created"
    if g.get("control") == "sign_shuffle":
        return f"{c.get('n_positive_columns', 0)} + / {c.get('n_negative_columns', 0)} - columns"
    return ""


def header_from(data: dict) -> list[str]:
    net, st, seeds = data["network"], data["stimulus"], data["seeds"]
    nt = data.get("nt") or ("paper" if net.get("nt_overrides", 0) > 0 else "brainir")
    return [f"# {data.get('title') or TITLES.get(data['experiment'], data['experiment'])}", "",
            f"Network {net['dataset']}:{net['version']} nt={nt} (N = {net['n']}, {net['n_pairs']} pairs), stimulus = {st['cell_type']} at "
            f"position(s) {st['positions']} with I = {st['current']}, T = {data['model_config_base']['t_end']} s, readout = {net['readout_n']} "
            f"front-leg motor neurons; seeds {seeds[0]}..{seeds[-1]}; wall {data['wall_time_s_total']:.0f} s on {data['workers']} workers.", ""]


def render_markdown(data: dict) -> list[str]:
    """Markdown summary of a sweep / control result built from the JSON payload alone (so it can be regenerated)."""
    exp = data["experiment"]
    md = header_from(data)
    if exp == "negative-controls":
        md += ["Control network for seed k is built with seed k and simulated with parameter seed k. Classes for the class shuffle: "
               f"{data.get('control_classes')}.", ""]
    last_col = "construction" if exp == "negative-controls" else "paper"
    md += [CONDITION_HEADER[0].replace("| paper |", f"| {last_col} |"), CONDITION_HEADER[1]]
    for g in data["conditions"]:
        label = g["label"] + (f" (= {', '.join(g['aliases'])})" if g.get("aliases") else "")
        md.append(condition_row(label, g["summary"], paper_note(exp, g)))
    return md


# ---------------------------------------------------------------------------
# network loading and shared bookkeeping
# ---------------------------------------------------------------------------
def load_network(dataset: str, version: str, nt: str):
    from reproduce_dynamics import STIM_CURRENT, paper_network  # answer-key-adjacent helper (same directory)

    _, net, readout = paper_network(dataset, version, nt)
    return net, readout, STIM_CURRENT[dataset]


def stim_positions(net, args) -> list[int]:
    if args.stim_positions:
        return [int(p) for p in args.stim_positions]
    return [int(net.positions_of_type("DNg100")[0])]


def make_stimulus(pos, current) -> Stimulus:
    return Stimulus(tuple(int(p) for p in pos), (float(current),))


def network_block(net, readout) -> dict:
    t = net.table
    return {**net.meta, "readout_n": int(readout.sum()), "readout_description": "motor neurons with sub_class 'fl' (front leg)",
            "n_pairs": int(net.W.nnz), "total_synapses": int(np.abs(net.W.data).sum()),
            "sign_rows": {"positive": int((net.signs > 0).sum()), "negative": int((net.signs < 0).sum()), "zero": int((net.signs == 0).sum())},
            "super_class_counts": {str(k): int(v) for k, v in t["super_class"].value_counts(dropna=False).items()},
            "evidence_note": "counts and sign rows are anatomy + NT predictions; nothing here is a model parameter"}


def payload(args, net, readout, pos, current, cfg: ModelConfig, seeds: list[int], conditions: list[dict], wall: float, **extra) -> dict:
    return {"experiment": args.cmd, "title": TITLES.get(args.cmd, args.cmd), "nt": args.nt, "created_utc": now_utc(), "model_id": MODEL_ID,
            "network": network_block(net, readout),
            "stimulus": {"positions": pos, "source_ids": [int(net.ids[p]) for p in pos], "cell_type": "DNg100", "current": current},
            "model_config_base": cfg.to_dict(), "seeds": seeds, "workers": args.workers, "wall_time_s_total": round(wall, 1),
            **extra, "conditions": conditions}


def write_results(name: str, data: dict, md: list[str]) -> None:
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / f"{name}.json").write_text(json.dumps(data, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
    (RESULTS / f"{name}.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(md))
    print(f"\nwrote results/{name}.json and results/{name}.md")


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def default_name(args, n: int) -> str:
    return args.name or f"robust_{args.cmd.replace('-', '_')}_{args.dataset}_{args.version}_nt-{args.nt}_n{n}"


def now_utc() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def cmd_resummarize(args) -> None:
    """Recompute the condition summaries from the stored per-replicate scalars and regenerate the markdown (no simulation)."""
    for path in args.paths:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if data.get("experiment") == "dt-convergence":
            raise SystemExit(f"{p.name}: dt-convergence tables are only rebuilt by a run")
        for g in data["conditions"]:
            g["summary"] = summarize(g["replicates"])
        data["resummarized_utc"] = now_utc()
        p.with_suffix(".json").write_text(json.dumps(data, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
        p.with_suffix(".md").write_text("\n".join(render_markdown(data)) + "\n", encoding="utf-8", newline="\n")
        print(f"re-summarised {p.with_suffix('.json').name} and {p.with_suffix('.md').name}")


# ---------------------------------------------------------------------------
# 1. dt-convergence
# ---------------------------------------------------------------------------
EARLY_WINDOW_S = 0.3
"""Errors are also taken over t <= 0.3 s (about three cycles): over a 2 s run the max / RMS differences are dominated by the
accumulated phase drift of the oscillation, which saturates and hides a scheme's order."""
ERR_METRICS = ("err_max_all_hz", "err_rms_all_hz", "err_max_window_hz", "err_rms_window_hz", "err_max_early_hz", "err_rms_early_hz",
               "err_onset_sample_hz", "err_last_sample_hz")
ERR_KEYS = ERR_METRICS + ("wall_time_s", "n_rhs_evaluations")
ORDER_KEYS = ("err_max_all_hz", "err_rms_all_hz", "err_max_window_hz", "err_rms_window_hz", "err_max_early_hz", "err_rms_early_hz")


def _compare_methods(W, sizes, readout, base: dict, stim, seed: int, methods: list[tuple[str, str, dict]], *, exclude_last: bool,
                     reference: tuple[str, str, dict] = REFERENCE_METHOD) -> list[dict]:
    """Integrate one replicate with the reference and with ``methods``; scalar comparisons per method (no trajectories)."""
    n = W.shape[0]
    cfg0 = ModelConfig(**base)

    def run(over: dict):
        cfg = ModelConfig(**{**base, **over})
        params = sample_neuron_params(cfg, n, int(seed), sizes)
        t0 = time.time()
        traj = simulate(W, params, cfg, stim)
        return traj, time.time() - t0, score_trajectory(traj, readout)

    def row(label: str, family: str, traj, wall: float, sc: dict, d: np.ndarray | None) -> dict:
        keep = np.ones(len(traj.t), dtype=bool)
        if exclude_last:
            keep[-1] = False
        win = keep & (traj.t >= ANALYSIS_START_S - 1e-12)
        early = keep & (traj.t <= EARLY_WINDOW_S + 1e-12)
        k_on = int(np.argmin(np.abs(traj.t - cfg0.pulse_start)))
        err = {k: 0.0 for k in ERR_METRICS}
        if d is not None:
            err = {"err_max_all_hz": float(np.abs(d[keep]).max()), "err_rms_all_hz": float(np.sqrt(np.mean(d[keep] ** 2))),
                   "err_max_window_hz": float(np.abs(d[win]).max()), "err_rms_window_hz": float(np.sqrt(np.mean(d[win] ** 2))),
                   "err_max_early_hz": float(np.abs(d[early]).max()), "err_rms_early_hz": float(np.sqrt(np.mean(d[early] ** 2))),
                   "err_onset_sample_hz": float(np.abs(d[k_on]).max()), "err_last_sample_hz": float(np.abs(d[-1]).max())}
        return {"seed": int(seed), "method": label, "family": family, "wall_time_s": round(wall, 3), "n_rhs_evaluations": traj.info.get("n_steps"),
                "success": bool(traj.info.get("success", True)), "score": sc["score"], "mean_frequency_hz": sc["mean_frequency_hz"],
                "n_active_readout": sc["n_active_readout"], "n_active_all": sc["n_active_all"], "max_rate_hz": sc["max_rate_hz"], **err}

    ref_label, ref_family, ref_over = reference
    ref, ref_wall, ref_sc = run(ref_over)
    rows = [{**row(ref_label, ref_family, ref, ref_wall, ref_sc, None), "score_diff": 0.0}]
    for label, family, over in methods:
        traj, wall, sc = run(over)
        rows.append({**row(label, family, traj, wall, sc, traj.r - ref.r), "score_diff": float(sc["score"] - ref_sc["score"])})
    return rows


def reference_method(rtol: float, atol: float) -> tuple[str, str, dict]:
    return (f"RK45 rtol {rtol:g} atol {atol:g} (reference)", "reference", {"rtol": rtol, "atol": atol})


def _convergence_job(args) -> dict:
    """One seed: part A (order study, pulse on throughout) and part B (standard protocol with its pulse edges)."""
    W, sizes, readout, base, stim, seed, reference, extra = args
    base_a = {**base, "pulse_start": 0.0, "pulse_end": base["t_end"]}
    return {"seed": int(seed),
            "order_study": _compare_methods(W, sizes, readout, base_a, stim, seed, ORDER_STUDY_METHODS + extra, exclude_last=False,
                                            reference=reference),
            "protocol_edges": _compare_methods(W, sizes, readout, base, stim, seed, PROTOCOL_METHODS + extra, exclude_last=True,
                                               reference=reference)}


def convergence_orders(rows: list[dict], family: str, key: str) -> dict:
    """Empirical order p = log(e1/e2) / log(dt1/dt2) for consecutive members of a fixed-step family (sorted by dt)."""
    fam = sorted([r for r in rows if r["family"] == family], key=lambda r: -float(r["method"].split("dt ")[1]))
    out = {"dts": [], "errors": [], "orders": []}
    for r in fam:
        out["dts"].append(float(r["method"].split("dt ")[1]))
        out["errors"].append(r[key])
    for (d1, e1), (d2, e2) in zip(zip(out["dts"][:-1], out["errors"][:-1]), zip(out["dts"][1:], out["errors"][1:])):
        out["orders"].append(float(np.log(e1 / e2) / np.log(d1 / d2)) if e1 > 0 and e2 > 0 else None)
    return out


def aggregate_methods(rows: list[dict], labels: list[str]) -> list[dict]:
    out = []
    for m in labels:
        rs = [r for r in rows if r["method"] == m]
        agg = {"method": m, "family": rs[0]["family"], "n_seeds": len(rs)}
        for k in ERR_KEYS:
            v = np.array([r[k] for r in rs], dtype=float)
            agg[k + "_mean"] = float(v.mean())
            agg[k + "_max"] = float(v.max())
        agg["score_mean"] = float(np.mean([r["score"] for r in rs]))
        agg["score_diff_max_abs"] = float(np.max(np.abs([r["score_diff"] for r in rs])))
        f = np.array([np.nan if r["mean_frequency_hz"] is None else r["mean_frequency_hz"] for r in rs], dtype=float)
        agg["frequency_mean_hz"] = float(np.nanmean(f)) if np.isfinite(f).any() else None
        agg["n_active_readout"] = sorted({int(r["n_active_readout"]) for r in rs})
        agg["all_success"] = all(r["success"] for r in rs)
        out.append(agg)
    return out


def aggregate_orders(rows_by_seed: list[list[dict]], families: tuple[str, ...] = ("rk4", "euler")) -> dict:
    orders = {}
    for fam in families:
        for key in ORDER_KEYS:
            per = [convergence_orders(rs, fam, key) for rs in rows_by_seed]
            if not per or len(per[0]["dts"]) < 2:
                continue
            ords = np.array([[o if o is not None else np.nan for o in p["orders"]] for p in per], dtype=float)
            orders[f"{fam}:{key}"] = {"dts": per[0]["dts"], "per_seed_orders": ords.tolist(), "mean_orders": np.nanmean(ords, axis=0).tolist(),
                                       "errors_mean": np.mean([p["errors"] for p in per], axis=0).tolist()}
    return orders


def method_table(aggs: list[dict]) -> list[str]:
    md = ["| method | max abs dr (Hz) | RMS dr (Hz) | max abs dr, window | RMS dr, window | max abs dr, t <= 0.3 s | RMS dr, t <= 0.3 s | "
          "dr at onset sample | dr at last sample | max abs dscore | mean score | mean MN f (Hz) | active MNs | RHS evals | wall (s) |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for a in aggs:
        md.append(f"| {a['method']} | {a['err_max_all_hz_mean']:.2e} | {a['err_rms_all_hz_mean']:.2e} | {a['err_max_window_hz_mean']:.2e} | "
                  f"{a['err_rms_window_hz_mean']:.2e} | {a['err_max_early_hz_mean']:.2e} | {a['err_rms_early_hz_mean']:.2e} | "
                  f"{a['err_onset_sample_hz_mean']:.2e} | {a['err_last_sample_hz_mean']:.2e} | "
                  f"{a['score_diff_max_abs']:.1e} | {a['score_mean']:.4f} | {_fmt(a['frequency_mean_hz'], 2)} | "
                  f"{','.join(map(str, a['n_active_readout']))} | {a['n_rhs_evaluations_mean']:.0f} | {a['wall_time_s_mean']:.1f} |")
    return md


def orders_table(orders: dict) -> list[str]:
    md = ["| family | error measure | dt sequence (s) | mean errors (Hz) | orders between successive dts |", "|---|---|---|---|---|"]
    for k, o in orders.items():
        fam, key = k.split(":")
        md.append(f"| {fam} | {key} | {', '.join(f'{d:g}' for d in o['dts'])} | {', '.join(f'{e:.2e}' for e in o['errors_mean'])} | "
                  f"{', '.join(_fmt(v, 2) for v in o['mean_orders'])} |")
    return md


def cmd_dt_convergence(args) -> None:
    net, readout, default_current = load_network(args.dataset, args.version, args.nt)
    current = args.current if args.current is not None else default_current
    pos = stim_positions(net, args)
    cfg = ModelConfig(t_end=args.t_end)
    stim = make_stimulus(pos, current)
    seeds = list(range(args.seed0, args.seed0 + args.n))
    reference = reference_method(args.reference_rtol, args.reference_atol)
    # with a tighter reference the standard tight RK45 becomes a compared method, so its own error is measured
    extra = [] if reference[2] == REFERENCE_METHOD[2] else [(REFERENCE_METHOD[0].replace(" (reference)", ""), "adaptive", REFERENCE_METHOD[2])]
    jobs = [(net.W, net.sizes, readout, cfg.to_dict(), stim, s, reference, extra) for s in seeds]
    print(f"dt-convergence: {len(seeds)} seeds x ({len(ORDER_STUDY_METHODS) + len(PROTOCOL_METHODS) + 2 * len(extra) + 2} integrations) on "
          f"{min(args.workers, len(jobs))} workers", flush=True)
    t0 = time.time()
    if args.workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=min(args.workers, len(jobs))) as ex:
            per_seed = list(ex.map(_convergence_job, jobs))
    else:
        per_seed = [_convergence_job(j) for j in jobs]
    wall = time.time() - t0
    cfg_a = ModelConfig(**{**cfg.to_dict(), "pulse_start": 0.0, "pulse_end": cfg.t_end})
    parts = {}
    for part, methods, part_cfg, samples in (("order_study", ORDER_STUDY_METHODS + extra, cfg_a, "all samples"),
                                             ("protocol_edges", PROTOCOL_METHODS + extra, cfg, "t <= pulse_end (final sample reported separately)")):
        rows_by_seed = [p[part] for p in per_seed]
        rows = [r for rs in rows_by_seed for r in rs]
        labels = [reference[0]] + [m[0] for m in methods]
        parts[part] = {"model_config": part_cfg.to_dict(), "comparison_samples": samples, "methods": aggregate_methods(rows, labels),
                       "convergence_orders": aggregate_orders(rows_by_seed), "rows": rows}
    default_err = next(a for a in parts["order_study"]["methods"] if a["method"].startswith("RK45 rtol 2e-6"))["err_max_all_hz_mean"]
    ref_floor = default_err * (args.reference_rtol / 2e-6)
    conditions = [{"label": f"{part}: {a['method']}", "part": part, **a} for part in parts for a in parts[part]["methods"]]
    data = payload(args, net, readout, pos, current, cfg, seeds, conditions, wall, reference=reference[0],
                   reference_error_estimate_hz=ref_floor, early_window_s=EARLY_WINDOW_S, parts=parts)
    md = header_from(data)
    md += [f"Reference: {reference[0]}; its own error is estimated at ~{ref_floor:.1e} Hz (default-RK45 error x tolerance ratio). "
           f"Wall times were measured with up to {min(args.workers, len(jobs))} concurrent processes. Mean over seeds; per-seed rows in the JSON. "
           f"'window' = t >= {ANALYSIS_START_S} s (the scored interval); 't <= {EARLY_WINDOW_S} s' = before phase drift accumulates.", "",
           "## Part A: order study (pulse on for the whole run = the standard replicate shifted by 20 ms; no pulse edge inside the run)", ""]
    md += method_table(parts["order_study"]["methods"])
    md += ["", "Empirical convergence orders (expected: RK4 -> 4, Euler -> 1 for a smooth right-hand side):", ""]
    md += orders_table(parts["order_study"]["convergence_orders"])
    md += ["", "## Part B: standard protocol with its pulse edges (on at 0.02 s, off at T - 1 ms); differences over t <= pulse_end", ""]
    md += method_table(parts["protocol_edges"]["methods"])
    md += ["", "Fixed-step RK4 in part B (orders from the two dts):", ""]
    md += orders_table(parts["protocol_edges"]["convergence_orders"])
    md += ["", "Notes: the rate equation's right-hand side has a C0 kink (max(., 0)) at every threshold crossing, which lowers the order any "
           "fixed-step scheme can show; the reference's own error bounds what is measurable at the smallest dt. In part B the fixed-step "
           "schemes evaluate the pulse indicator at the stage times, so the k4 stage of the step ending at pulse_start and the k1 stage of the "
           "step starting at pulse_end see the other side of the switch: an O(dt) discrepancy of ~(dt/6) x activation/tau on the stimulated "
           "neuron (0.13 Hz at dt = 1 ms) that propagates into the oscillation phase (see 'dr at onset sample' and 'dr at last sample')."]
    write_results(default_name(args, args.n), data, md)


# ---------------------------------------------------------------------------
# 2-4. parameter, input and weight-noise sweeps
# ---------------------------------------------------------------------------
def param_conditions(base: ModelConfig, families: dict[str, list[float]]) -> list[dict]:
    """Conditions of the parameter sweep; identical configurations are merged (the default appears in every family)."""
    conds: list[dict] = []
    seen: dict[ModelConfig, dict] = {}
    for fam, values in families.items():
        for v in values:
            if fam == "widen":
                cfg = ModelConfig(**{**base.to_dict(), "tau_sd": base.tau_sd * v, "a_sd": base.a_sd * v, "theta_sd": base.theta_sd * v,
                                     "r_max_sd": base.r_max_sd * v})
            elif fam == "a":
                cfg = ModelConfig(**{**base.to_dict(), "a_mean": v})
            elif fam == "theta":
                cfg = ModelConfig(**{**base.to_dict(), "theta_mean": v})
            elif fam == "r_max":
                cfg = ModelConfig(**{**base.to_dict(), "r_max_mean": v})
            elif fam == "tau":
                cfg = ModelConfig(**{**base.to_dict(), "tau_mean": v})
            elif fam == "b":
                cfg = ModelConfig(**{**base.to_dict(), "b_exc": v, "b_inh": v})
            else:
                raise ValueError(fam)
            label = f"{fam}={v:g}"
            if cfg in seen:
                seen[cfg]["aliases"].append(label)
                continue
            c = {"label": label, "family": fam, "value": v, "aliases": [], "model_config": cfg.to_dict(), "_cfg": cfg}
            seen[cfg] = c
            conds.append(c)
    return conds


def _sweep(args, conditions: list[dict], make_job, extra_payload: dict) -> None:
    net, readout, default_current = load_network(args.dataset, args.version, args.nt)
    current = args.current if args.current is not None else default_current
    pos = stim_positions(net, args)
    base = ModelConfig(t_end=args.t_end)
    seeds = list(range(args.seed0, args.seed0 + args.n))
    jobs = []
    for c in conditions:
        c_seeds = seeds[: c.get("n_override", len(seeds))]
        c["seeds"] = c_seeds
        jobs += [make_job(c, s, pos, current, base) for s in c_seeds]
    print(f"{args.cmd}: {len(conditions)} conditions, {len(jobs)} replicates on {args.workers} workers", flush=True)
    t0 = time.time()
    results = run_jobs(jobs, net.W, net.sizes, readout, args.workers, label=args.cmd)
    wall = time.time() - t0
    grouped = group_by_condition(results, [{k: v for k, v in c.items() if not k.startswith("_")} for c in conditions])
    data = payload(args, net, readout, pos, current, base, seeds, grouped, wall, **extra_payload)
    write_results(default_name(args, args.n), data, render_markdown(data))


def cmd_param_sweep(args) -> None:
    base = ModelConfig(t_end=args.t_end)
    conds = param_conditions(base, PARAM_FAMILIES)
    for c in conds:
        if c["family"] == "widen" and c["value"] == 0:
            c["n_override"] = 2  # sd = 0: every replicate is identical; two seeds demonstrate it
            c["note"] = "sd = 0 -> parameters at their (size-scaled) means; replicates coincide"

    def make_job(c, s, pos, current, _base):
        return {"condition": c["label"], "seed": s, "cfg": c["_cfg"], "stim": make_stimulus(pos, current)}

    _sweep(args, conds, make_job, {"paper_reference": {"widen": PAPER_WIDEN, "widen_3x_restore_one_parameter": PAPER_WIDEN_RESTORE,
                                                       "default": {"mean": 0.974, "median": 0.999, "fraction_ge_0_5": 0.998}},
                                   "families": PARAM_FAMILIES})


def cmd_input_sweep(args) -> None:
    currents = [float(c) for c in (args.currents or INPUT_CURRENTS)]
    conds = [{"label": f"I={c:g}", "current": c} for c in currents]
    base = ModelConfig(t_end=args.t_end)

    def make_job(c, s, pos, _current, _base):
        return {"condition": c["label"], "seed": s, "cfg": base, "stim": make_stimulus(pos, c["current"])}

    _sweep(args, conds, make_job, {"paper_reference": {"median_frequency_hz": PAPER_INPUT_SWEEP_FREQ_HZ, "notes": PAPER_INPUT_SWEEP_NOTE,
                                                       "paper_stimulated": "both DNg100 axons (indices 31 and 132 of the authors' table)"}})


def cmd_weight_noise(args) -> None:
    sigmas = [float(s) for s in (args.sigmas or NOISE_SIGMAS)]
    conds = [{"label": f"sigma={s:g}", "weight_noise_sd": s} for s in sigmas]
    base = ModelConfig(t_end=args.t_end)

    def make_job(c, s, pos, current, _base):
        iv = Intervention(weight_noise_sd=c["weight_noise_sd"], weight_noise_seed=int(s)) if c["weight_noise_sd"] > 0 else None
        return {"condition": c["label"], "seed": s, "cfg": base, "stim": make_stimulus(pos, current), "intervention": iv}

    _sweep(args, conds, make_job, {"paper_reference": {"mean_score_by_sigma": {str(k): v for k, v in PAPER_WEIGHT_NOISE_MEAN.items()}},
                                   "noise_model": "w (1 + eta), eta ~ truncated normal(0, sigma), eta >= -1, drawn per replicate with "
                                                  "weight_noise_seed = seed"})


# ---------------------------------------------------------------------------
# 5. negative controls
# ---------------------------------------------------------------------------
def cmd_negative_controls(args) -> None:
    net, readout, default_current = load_network(args.dataset, args.version, args.nt)
    current = args.current if args.current is not None else default_current
    pos = stim_positions(net, args)
    base = ModelConfig(t_end=args.t_end)
    seeds = list(range(args.seed0, args.seed0 + args.n))
    labels = paper_shuffle_classes(net.table["super_class"].to_numpy(), net.signs)
    class_counts = {str(k): int(v) for k, v in zip(*np.unique(labels, return_counts=True))}
    controls = [c for c in (args.controls or CONTROLS)]
    kwargs = {"class_shuffle": {"labels": labels}, "degree_rewire": {"swaps_per_edge": args.swaps_per_edge}, "sign_shuffle": {"fixed": tuple(pos)}}
    conds = [{"label": c, "control": c, "control_kwargs": {k: (v if k != "labels" else "paper five classes") for k, v in kwargs.get(c, {}).items()}}
             for c in controls]
    jobs = [{"condition": c["control"], "seed": s, "cfg": base, "stim": make_stimulus(pos, current), "control": c["control"],
             "control_kwargs": kwargs.get(c["control"], {})} for c in conds for s in seeds]
    print(f"negative-controls: {len(conds)} controls x {len(seeds)} seeds on {args.workers} workers", flush=True)
    t0 = time.time()
    results = run_jobs(jobs, net.W, net.sizes, readout, args.workers, label="controls")
    wall = time.time() - t0
    grouped = group_by_condition(results, conds)
    for g in grouped:
        st = [r.get("control_stats", {}) for r in g["replicates"]]
        if g["control"] == "degree_rewire" and st and st[0]:
            g["construction"] = {"n_edges": st[0]["n_edges"], "n_attempted": st[0]["n_attempted"],
                                 "n_swapped_mean": float(np.mean([s["n_swapped"] for s in st]))}
        elif g["control"] == "class_shuffle" and st and st[0]:
            g["construction"] = {"n_diagonal_entries_mean": float(np.mean([s["n_diagonal_entries"] for s in st])), "class_counts": class_counts}
        elif g["control"] == "sign_shuffle" and st and st[0]:
            g["construction"] = {"n_positive_columns": st[0]["n_positive_columns"], "n_negative_columns": st[0]["n_negative_columns"],
                                 "fixed_positions": list(pos)}
    data = payload(args, net, readout, pos, current, base, seeds, grouped, wall, control_classes=class_counts,
                   control_definitions={"class_shuffle": "rows (input vectors) permuted within the paper's five classes; diagonal not re-zeroed",
                                        "degree_rewire": f"{args.swaps_per_edge:g} x E attempted target swaps; in/out degrees and column signs preserved",
                                        "sign_shuffle": "output signs permuted among presynaptic neurons with outputs; stimulated neuron fixed",
                                        "weight_permute": "synapse counts permuted among existing edges; pattern and signs preserved",
                                        "intact": "unmodified network"})
    write_results(default_name(args, args.n), data, render_markdown(data))


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _common(p: argparse.ArgumentParser, n_default: int) -> None:
    p.add_argument("--dataset", default="manc")
    p.add_argument("--version", default="v1.2.1")
    p.add_argument("--nt", choices=["paper", "brainir"], default="paper")
    p.add_argument("--n", type=int, default=n_default, help="replicates (seeds seed0..seed0+n-1) per condition")
    p.add_argument("--seed0", type=int, default=0)
    p.add_argument("--t-end", type=float, default=2.0)
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--current", type=float, default=None, help="stimulus amplitude (default: the paper's per-dataset value)")
    p.add_argument("--stim-positions", type=int, nargs="*", default=None, help="positional indices to stimulate (default: first DNg100)")
    p.add_argument("--name", default=None, help="output stem under results/ (default: robust_<cmd>_<dataset>_<version>_nt-<nt>_n<n>)")


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("dt-convergence", help="integrator / step-size convergence on the same replicate")
    _common(s, 8)
    s.add_argument("--reference-rtol", type=float, default=REFERENCE_METHOD[2]["rtol"], help="RK45 reference rtol (default 1e-8)")
    s.add_argument("--reference-atol", type=float, default=REFERENCE_METHOD[2]["atol"], help="RK45 reference atol (default 1e-11)")
    s.set_defaults(func=cmd_dt_convergence)
    s = sub.add_parser("param-sweep", help="model-parameter robustness sweep")
    _common(s, 24)
    s.set_defaults(func=cmd_param_sweep)
    s = sub.add_parser("input-sweep", help="stimulus-amplitude sweep")
    _common(s, 32)
    s.add_argument("--currents", type=float, nargs="*", default=None)
    s.set_defaults(func=cmd_input_sweep)
    s = sub.add_parser("weight-noise", help="multiplicative synapse-count noise")
    _common(s, 24)
    s.add_argument("--sigmas", type=float, nargs="*", default=None)
    s.set_defaults(func=cmd_weight_noise)
    s = sub.add_parser("negative-controls", help="shuffled / rewired / re-signed / re-weighted control networks")
    _common(s, 24)
    s.add_argument("--controls", nargs="*", choices=list(CONTROLS), default=None)
    s.add_argument("--swaps-per-edge", type=float, default=10.0)
    s.set_defaults(func=cmd_negative_controls)
    s = sub.add_parser("resummarize", help="recompute summaries and markdown of existing result JSONs from their per-replicate scalars")
    s.add_argument("paths", nargs="+", help="results/*.json files")
    s.set_defaults(func=cmd_resummarize)
    args = ap.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
