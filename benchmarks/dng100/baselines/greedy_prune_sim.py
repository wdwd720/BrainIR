"""Baseline: simulation-guided backward elimination (greedy pruning) of the stimulus's downstream interneurons.

Uses ``brainir.sim`` (the bundle's rate model) as a black box. Candidates are the interneurons (role_class ``vnc_intrinsic``)
within two directed hops downstream of the stimulated neuron(s), ranked by weighted degree (total synapse count). The
method keeps only a candidate pool (plus stimulus and readout neurons; ``Intervention(keep_only=...)``) and scores the
readout population's rhythmicity with the bundle's metric, averaged over parameter replicates:

1. pool: the ``--pool`` (40) highest-degree candidates; if the keep-only network of that pool is not rhythmic (mean score
   below the metric's threshold) the pool is doubled (80, 160, ... up to ``--max-pool``) until it is — the 40-neuron pool is
   silent in both connectomes of this benchmark, so the expansion is what makes the elimination informative;
2. elimination: repeatedly remove the candidate whose individual removal (leave-one-out keep-only simulation) leaves the
   highest score. Above ``ONE_BY_ONE_BELOW`` (20) candidates the least impactful half is removed per round — the ranking
   uses ``BATCH_REPLICATES`` (1) parameter replicate and the batch is accepted only if the pool stays rhythmic under all
   replicates (halving the batch otherwise); at or below 20 the removal is strictly one neuron per round with all replicates;
3. output: the k survivors, ranked by their leave-one-out impact within the final core. ``essential`` = silencing the neuron
   alone in the FULL network (rows and columns zeroed) drops the mean score below the threshold, over the same replicates.

Budget: ``--budget-s`` (300 s per network) — when exceeded, the k most impactful candidates by the last leave-one-out
ranking are kept and the prediction says so. ``--replicates`` (2), ``--t-end`` (1.0 s; the bundle model's 2.0 s is shortened
for cost), ``--workers`` (5 processes, each holding one copy of the network). Cost reductions relative to a strict
one-at-a-time elimination from 40 candidates with 2 replicates (about 1600 simulations, ~11 min per network on the
development laptop): the coarse phase and the 20-candidate strict phase (about 650-1000 simulations). Everything is
deterministic given BRAINIR_SEED.

Clean-room contract (benchmarks/dng100/cleanroom/run_method.py): reads only the public bundle named by BRAINIR_BUNDLE /
BRAINIR_NETWORK, writes BRAINIR_OUT (plus a small ``greedy_trace_<network>.json`` next to it), imports only brainir and the allowed
scientific libraries. ``--k`` (or BRAINIR_TOPK) sets the core size.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from brainir.benchmark.prediction import BrainIRMechanismPrediction, DynamicsClaim, MechanismClaim, MethodInfo, NeuronClaim
from brainir.metrics.rhythm import ACTIVE_RATE_HZ, DEFAULT_PROMINENCE, network_oscillation_score
from brainir.sim.model import Intervention, ModelConfig, Stimulus, sample_neuron_params, simulate

METHOD_NAME = "baseline_greedy_prune_sim"
METHOD_VERSION = "1.0"
DESCRIPTION = ("simulation-guided backward elimination: keep-only pool of the highest-degree 2-hop downstream interneurons (expanded "
               "until rhythmic), leave-one-out greedy removal (halving batches ranked with 1 replicate above 20 candidates, one at a time "
               "with all replicates below) down to k, ranks by leave-one-out impact; essential = single-neuron silencing in the full "
               "network abolishes the rhythm.")
DEFAULT_K = 3
DEFAULT_POOL = 40
DEFAULT_MAX_POOL = 320
DEFAULT_REPLICATES = 2
DEFAULT_T_END = 1.0
DEFAULT_WORKERS = 5
DEFAULT_BUDGET_S = 300.0
ONE_BY_ONE_BELOW = 20
BATCH_FRACTION = 0.5
BATCH_REPLICATES = 1
DEFAULT_ANALYSIS_START_S = 0.25
DEFAULT_RHYTHMIC = 0.5
INTERNEURON_ROLE = "vnc_intrinsic"


# ----------------------------------------------------------------------------- bundle access (public files only)
def _read_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8"))


def load_bundle_network(bundle: Path, net: str) -> dict:
    d = bundle / "networks" / net
    return {"neurons": pd.read_parquet(d / "neurons.parquet"), "edges": pd.read_parquet(d / "edges.parquet"),
            "stimulus": _read_json(d / "stimulus.json"), "readout": _read_json(d / "readout.json"),
            "info": _read_json(d / "network.json"), "manifest": _read_json(bundle / "manifest.json"),
            "model_config": _read_json(bundle / "model_config.json") if (bundle / "model_config.json").exists() else {}}


def role_of(sign) -> str:
    s = int(sign)
    return "excitatory" if s > 0 else "inhibitory" if s < 0 else "unknown"


def interneuron_ids(neurons: pd.DataFrame, exclude: set[int]) -> list[int]:
    m = (neurons["role_class"] == INTERNEURON_ROLE) & ~neurons["is_stimulus"].astype(bool) & ~neurons["is_readout"].astype(bool)
    return sorted(int(i) for i in neurons.loc[m, "source_id"] if int(i) not in exclude)


def downstream_within(edges: pd.DataFrame, sources: list[int], hops: int) -> set[int]:
    """Neurons reachable from ``sources`` in 1..hops directed steps (sources excluded)."""
    src = {int(s) for s in sources}
    frontier, seen = set(src), set()
    for _ in range(hops):
        nxt = {int(i) for i in edges.loc[edges["pre_id"].isin(frontier), "post_id"]} - seen - src
        seen |= nxt
        frontier = nxt
    return seen


def weighted_degree(edges: pd.DataFrame) -> pd.Series:
    """Total synapse count in + out per neuron id."""
    return edges.groupby("pre_id")["synapse_count"].sum().add(edges.groupby("post_id")["synapse_count"].sum(), fill_value=0)


# ----------------------------------------------------------------------------- simulation scorer (bundle model, bundle metric)
def sim_state(data: dict, t_end: float) -> dict:
    """Everything one process needs to score keep-only / silencing simulations of this network."""
    neurons, edges = data["neurons"], data["edges"]
    n = len(neurons)
    ids = neurons["source_id"].to_numpy().astype(np.int64)
    w = sp.csr_matrix((edges["signed_weight"].to_numpy(dtype=np.float64),
                       (edges["post_position"].to_numpy(), edges["pre_position"].to_numpy())), shape=(n, n))
    w.eliminate_zeros()  # pairs whose presynaptic sign is unknown carry signed_weight 0: anatomy without a model effect
    mc = data.get("model_config") or {}
    cfg = ModelConfig(**{**mc.get("config", {}), "t_end": float(t_end)})
    metric = mc.get("metric", {})
    readout = neurons["is_readout"].to_numpy(dtype=bool)
    stim_pos = tuple(int(p) for p in data["stimulus"]["positions"])
    return {"n": n, "pos": {int(i): k for k, i in enumerate(ids)}, "W": w, "cfg": cfg, "sizes": neurons["size_voxels"].to_numpy(dtype=np.float64),
            "readout": readout, "stim": Stimulus(stim_pos, (float(data["stimulus"]["current"]),)),
            "always": stim_pos + tuple(int(p) for p in np.flatnonzero(readout)),
            "analysis_start": float(metric.get("analysis_start_s", DEFAULT_ANALYSIS_START_S)),
            "active_rate": float(metric.get("active_rate_hz", ACTIVE_RATE_HZ)), "prominence": float(metric.get("prominence", DEFAULT_PROMINENCE)),
            "rhythmic": float(metric.get("rhythmic_threshold", DEFAULT_RHYTHMIC))}


_SIM: dict = {}


def _init_worker(bundle: str, net: str, t_end: float) -> None:
    _SIM.update(sim_state(load_bundle_network(Path(bundle), net), t_end))


def score_simulation(st: dict, kind: str, ids: tuple[int, ...], seed: int) -> float:
    """Rhythmicity score (bundle metric) of one replicate with the given keep-only set or silenced set (ids)."""
    positions = tuple(st["pos"][int(i)] for i in ids)
    iv = Intervention(keep_only=positions, always_keep=st["always"]) if kind == "keep" else Intervention(silence=positions)
    params = sample_neuron_params(st["cfg"], st["n"], int(seed), st["sizes"])
    traj = simulate(st["W"], params, st["cfg"], st["stim"], iv)
    win = traj.window(st["analysis_start"])
    mask = (win.max(axis=0) > st["active_rate"]) & st["readout"]
    score, _, _, _ = network_oscillation_score(win, mask, st["prominence"])
    return float(score)


def _score_task(task: tuple[str, tuple[int, ...], int]) -> float:
    return score_simulation(_SIM, *task)


class SimScorer:
    """Mean rhythmicity score over parameter replicates, evaluated in a process pool (deterministic: seeds fixed, order kept)."""

    def __init__(self, bundle: Path, net: str, *, t_end: float, seeds: list[int], workers: int):
        self.seeds, self.n_sims, self.wall_s = [int(s) for s in seeds], 0, 0.0
        self.workers = max(1, int(workers))
        if self.workers > 1:
            self.pool = ProcessPoolExecutor(max_workers=self.workers, initializer=_init_worker, initargs=(str(bundle), net, float(t_end)))
        else:
            self.pool = None
            _init_worker(str(bundle), net, float(t_end))
        self.rhythmic = float(sim_state(load_bundle_network(bundle, net), t_end)["rhythmic"])

    def _scores(self, kind: str, sets: list[tuple[int, ...]], n_replicates: int | None = None) -> list[float]:
        if not sets:
            return []
        seeds = self.seeds if n_replicates is None else self.seeds[:max(1, int(n_replicates))]
        t0 = time.time()
        jobs = [(kind, tuple(int(i) for i in s), sd) for s in sets for sd in seeds]
        if self.pool is not None:
            res = list(self.pool.map(_score_task, jobs, chunksize=max(1, len(jobs) // (self.workers * 4))))
        else:
            res = [_score_task(j) for j in jobs]
        self.n_sims += len(jobs)
        self.wall_s += time.time() - t0
        r = len(seeds)
        return [float(np.mean(res[i * r:(i + 1) * r])) for i in range(len(sets))]

    def keep_scores(self, keep_sets: list[tuple[int, ...]], n_replicates: int | None = None) -> list[float]:
        return self._scores("keep", keep_sets, n_replicates)

    def silence_scores(self, silence_sets: list[tuple[int, ...]], n_replicates: int | None = None) -> list[float]:
        return self._scores("silence", silence_sets, n_replicates)

    def close(self) -> None:
        if self.pool is not None:
            self.pool.shutdown(wait=True)


# ----------------------------------------------------------------------------- the method (pure parts are testable with a stub scorer)
def candidate_pool(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int]) -> list[int]:
    """Interneurons within two hops downstream of the stimulus, highest weighted degree first."""
    exclude = set(map(int, stimulus_ids)) | set(map(int, readout_ids))
    inter = set(interneuron_ids(neurons, exclude))
    deg = weighted_degree(edges)
    return sorted(downstream_within(edges, stimulus_ids, 2) & inter, key=lambda v: (-float(deg.get(v, 0)), v))


def greedy_prune(pool: list[int], k: int, keep_scores: Callable[..., list[float]], tiebreak: dict[int, float], *,
                 rhythmic: float = DEFAULT_RHYTHMIC, one_by_one_below: int = ONE_BY_ONE_BELOW, batch_fraction: float = BATCH_FRACTION,
                 batch_replicates: int | None = BATCH_REPLICATES, deadline: float | None = None) -> tuple[list[int], list[dict]]:
    """Backward elimination by leave-one-out keep-only score. Ties: remove the lower-``tiebreak`` (degree) candidate first.

    ``keep_scores(sets, n_replicates=None)`` returns one mean score per id tuple; the coarse (batch) phase ranks with
    ``batch_replicates`` replicates, every rhythm check and the one-at-a-time phase use all of them."""
    current = [int(v) for v in pool]
    trace: list[dict] = []
    last_loo: dict[int, float] = {}
    while len(current) > k:
        if deadline is not None and time.time() > deadline:
            ranked = sorted(current, key=lambda v: (last_loo.get(v, 1.0), -tiebreak.get(v, 0.0), v))
            trace.append({"pool_size_before": len(current), "budget_exhausted": True, "kept_by_last_loo": ranked[:k]})
            return ranked[:k], trace
        batch_phase = len(current) > one_by_one_below
        loo_sets = [tuple(c for c in current if c != r) for r in current]
        loo = keep_scores(loo_sets, n_replicates=batch_replicates) if batch_phase else keep_scores(loo_sets)
        last_loo = dict(zip(current, loo))
        order = sorted(current, key=lambda v: (-last_loo[v], tiebreak.get(v, 0.0), v))  # least impactful first
        if batch_phase:
            n_remove = max(1, min(int(len(current) * batch_fraction), len(current) - one_by_one_below))
        else:
            n_remove = 1
        n_remove = min(n_remove, len(current) - k)
        checks = 0
        while n_remove > 1:
            drop = set(order[:n_remove])
            checks += 1
            if keep_scores([tuple(c for c in current if c not in drop)])[0] >= rhythmic:
                break
            n_remove = max(1, n_remove // 2)
        removed = order[:n_remove]
        current = [c for c in current if c not in set(removed)]
        trace.append({"pool_size_before": len(current) + n_remove, "removed": removed, "loo_score_of_removed": [round(last_loo[r], 4) for r in removed],
                      "loo_score_range": [round(min(loo), 4), round(max(loo), 4)], "batch_checks": checks,
                      "ranking_replicates": (batch_replicates if batch_phase else None)})
    return current, trace


def select_core(neurons: pd.DataFrame, edges: pd.DataFrame, stimulus_ids: list[int], readout_ids: list[int], k: int, seed: int = 0, *,
                scorer, pool_cap: int = DEFAULT_POOL, max_pool: int = DEFAULT_MAX_POOL, deadline: float | None = None) -> tuple[list[int], dict]:
    """``scorer`` provides ``keep_scores``/``silence_scores`` (lists of id tuples -> mean scores) and ``rhythmic`` (threshold)."""
    rhythmic = float(getattr(scorer, "rhythmic", DEFAULT_RHYTHMIC))
    ranked = candidate_pool(neurons, edges, stimulus_ids, readout_ids)
    deg = weighted_degree(edges)
    if not ranked:
        return [], {"pool_expansion": [], "pool_rhythmic": False, "essential": {}, "note": "no downstream interneuron"}
    cap = max(1, min(pool_cap, len(ranked)))
    expansion = []
    while True:
        pool = ranked[:cap]
        s = scorer.keep_scores([tuple(pool)])[0]
        expansion.append({"pool_size": cap, "keep_only_score": round(s, 4)})
        if s >= rhythmic or cap >= min(max_pool, len(ranked)):
            break
        cap = min(cap * 2, max_pool, len(ranked))
    tiebreak = {v: float(deg.get(v, 0)) for v in pool}
    core, trace = greedy_prune(pool, k, scorer.keep_scores, tiebreak, rhythmic=rhythmic, deadline=deadline)
    core_score = scorer.keep_scores([tuple(core)])[0] if core else 0.0
    loo_final = scorer.keep_scores([tuple(c for c in core if c != r) for r in core]) if len(core) > 1 else [0.0] * len(core)
    silenced = scorer.silence_scores([(r,) for r in core])
    order = sorted(range(len(core)), key=lambda i: (loo_final[i], -tiebreak.get(core[i], 0.0), core[i]))  # most impactful first
    core_ranked = [core[i] for i in order]
    detail = {"pool_expansion": expansion, "pool_rhythmic": bool(expansion[-1]["keep_only_score"] >= rhythmic), "rhythmic_threshold": rhythmic,
              "n_rounds": len(trace), "budget_exhausted": any(t.get("budget_exhausted") for t in trace),
              "core_keep_only_score": round(core_score, 4), "core_sufficient": bool(core_score >= rhythmic),
              "leave_one_out_in_core": {core[i]: round(loo_final[i], 4) for i in order},
              "silenced_in_full_network": {core[i]: round(silenced[i], 4) for i in order},
              "essential": {core[i]: bool(silenced[i] < rhythmic) for i in order}, "trace": trace}
    return core_ranked, detail


# ----------------------------------------------------------------------------- prediction
def build_prediction(data: dict, core: list[int], *, seed: int, compute: dict, essential: dict[int, bool | None] | None = None,
                     motif: str | None = None, loop: list[int] = (), notes: str | None = None) -> BrainIRMechanismPrediction:
    neurons = data["neurons"].set_index("source_id")
    net = data["info"]["name"]
    claims = [NeuronClaim(source_id=int(i), role=role_of(neurons.loc[int(i), "sign"]), rank=r + 1, essential=(essential or {}).get(int(i)))
              for r, i in enumerate(core)]
    inputs = [f"networks/{net}/{f}" for f in ("neurons.parquet", "edges.parquet", "stimulus.json", "readout.json", "network.json")]
    inputs += ["manifest.json", "model_config.json"]
    return BrainIRMechanismPrediction(
        benchmark_id=data["manifest"]["benchmark_id"], dataset=data["info"]["dataset"], dataset_version=data["info"]["version"],
        stimulus_source_ids=[int(i) for i in data["stimulus"]["source_ids"]], core_neurons=claims,
        dynamics=DynamicsClaim(rhythmic=True), mechanism=MechanismClaim(motif=motif, loop_neurons=[int(i) for i in loop], notes=notes),
        method=MethodInfo(name=METHOD_NAME, version=METHOD_VERSION, description=DESCRIPTION, inputs_used=inputs, compute=compute,
                          random_seed=int(seed)),
        created_utc=_dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"))


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--k", type=int, default=int(os.environ.get("BRAINIR_TOPK", DEFAULT_K)))
    ap.add_argument("--pool", type=int, default=DEFAULT_POOL)
    ap.add_argument("--max-pool", type=int, default=DEFAULT_MAX_POOL)
    ap.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    ap.add_argument("--t-end", type=float, default=DEFAULT_T_END)
    ap.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    ap.add_argument("--budget-s", type=float, default=DEFAULT_BUDGET_S)
    args = ap.parse_args(argv)
    t0 = time.time()
    bundle, net, out = Path(os.environ["BRAINIR_BUNDLE"]), os.environ["BRAINIR_NETWORK"], Path(os.environ["BRAINIR_OUT"])
    seed = int(os.environ.get("BRAINIR_SEED", "0"))
    seeds = [7919 * (seed + 1) + i for i in range(args.replicates)]
    data = load_bundle_network(bundle, net)
    stim = [int(i) for i in data["stimulus"]["source_ids"]]
    readout = [int(i) for i in data["readout"]["source_ids"]]
    scorer = SimScorer(bundle, net, t_end=args.t_end, seeds=seeds, workers=args.workers)
    try:
        core, detail = select_core(data["neurons"], data["edges"], stim, readout, args.k, seed=seed, scorer=scorer, pool_cap=args.pool,
                                   max_pool=args.max_pool, deadline=t0 + args.budget_s)
    finally:
        scorer.close()
    trace = detail.pop("trace", [])
    compute = {"wall_time_s": round(time.time() - t0, 1), "simulations": scorer.n_sims, "simulation_wall_s": round(scorer.wall_s, 1),
               "replicates": args.replicates, "replicate_seeds": seeds, "t_end_s": args.t_end, "workers": args.workers,
               "pool_sizes": [e["pool_size"] for e in detail["pool_expansion"]], "budget_s": args.budget_s,
               "budget_exhausted": detail["budget_exhausted"], "backend": "brainir.sim (RK45, float64)"}
    notes = json.dumps({k_: v for k_, v in detail.items() if k_ != "essential"})[:2000]
    pred = build_prediction(data, core, seed=seed, essential=detail["essential"], notes=notes, compute=compute,
                            motif="survivors of simulation-guided backward elimination (keep-only sufficiency)")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(pred.to_json(), encoding="utf-8", newline="\n")
    trace_name = out.name.replace("prediction_", "greedy_trace_", 1) if out.name.startswith("prediction_") else "greedy_trace_" + out.name
    out.with_name(trace_name).write_text(json.dumps({"network": net, "seed": seed, "compute": compute, "detail": detail, "trace": trace},
                                                    indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{METHOD_NAME}: wrote {out.name} with {len(core)} core neurons; {scorer.n_sims} simulations in {compute['wall_time_s']} s; "
          f"pool {compute['pool_sizes']}; core keep-only score {detail['core_keep_only_score']}; essential {detail['essential']}")


if __name__ == "__main__":
    main()
