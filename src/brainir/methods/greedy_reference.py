"""Reference method: simulation-guided greedy backward elimination on the generic discovery API.

This is the Phase 1 baseline's algorithm (`benchmarks/dng100/baselines/greedy_prune_sim.py`) expressed against
:class:`~brainir.discovery.BudgetedSimulator` and an arbitrary functional criterion, so that it can serve as the fair
reference on synthetic instances. Algorithm (unchanged in spirit):

1. candidate pool = the ``pool`` highest weighted-degree candidates within ``hops`` directed hops downstream of the
   stimulus; if the keep-only network of the pool does not pass the criterion (mean over ``replicates`` seeds), double
   the pool (up to ``max_pool``);
2. backward elimination: repeatedly remove the candidate whose leave-one-out keep-only network scores highest; above
   ``one_by_one_below`` candidates remove the least impactful half per round (ranked with one replicate, accepted only
   if the pool still passes with all replicates, halving the batch otherwise); at or below it, strictly one per round;
3. stop at ``k`` survivors (``k`` is a hyper-parameter of the baseline, default 3 as frozen in Phase 1) or when the
   budget is exhausted; ``essential`` = silencing the neuron alone in the FULL network fails the criterion.

The reference has no uncertainty model: inclusion probability is 1 for survivors, 0 otherwise. Node order enters
through tie-breaking (weighted degree, then position), exactly as in the frozen baseline.
"""

from __future__ import annotations

import time

import numpy as np

from ..discovery.interface import DiscoveryMethod, DiscoveryResult, MethodRegistry
from ..discovery.interventions import keep_only, silence
from ..discovery.problem import DiscoveryProblem
from ..discovery.simulator import BudgetedSimulator, BudgetExhausted


def downstream_within(problem: DiscoveryProblem, sources: list[int], hops: int) -> set[int]:
    """Positions reachable from ``sources`` within ``hops`` directed hops (edges with any synapse count)."""
    C = problem.C.tocsc()  # C[post, pre]: column pre -> rows post
    frontier, seen = set(int(s) for s in sources), set(int(s) for s in sources)
    for _ in range(hops):
        nxt = set()
        for s in frontier:
            nxt.update(int(p) for p in C.indices[C.indptr[s]:C.indptr[s + 1]])
        frontier = nxt - seen
        seen |= nxt
    return seen


def weighted_degree(problem: DiscoveryProblem) -> np.ndarray:
    C = problem.C
    return np.asarray(C.sum(axis=0)).ravel() + np.asarray(C.sum(axis=1)).ravel()


@MethodRegistry.register
class GreedyReference(DiscoveryMethod):
    name = "greedy_reference"
    version = "1.0"
    default_config = {"k": 3, "pool": 40, "max_pool": 320, "hops": 2, "replicates": 2, "one_by_one_below": 20, "t_end": None}

    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        seeds = [int(seed) * 1000 + i for i in range(int(cfg["replicates"]))]
        t_end = cfg.get("t_end")
        cand = set(int(p) for p in problem.candidate_positions())
        down = downstream_within(problem, list(problem.stim_positions), int(cfg["hops"])) & cand
        deg = weighted_degree(problem)
        order = sorted(down, key=lambda p: (-deg[p], p))
        k = int(cfg["k"])
        trace = {"pool_sizes": [], "rounds": 0, "budget_exhausted": False}

        def passes(keep: list[int], reps: list[int] | None = None) -> tuple[float, float]:
            outs = sim.evaluate(keep_only(problem, keep), reps if reps is not None else seeds, t_end=t_end)
            return float(np.mean([o.score for o in outs])), float(np.mean([o.passed for o in outs]))

        try:
            pool_n = int(cfg["pool"])
            pool = order[:pool_n]
            score, frac = passes(pool)
            trace["pool_sizes"].append(len(pool))
            while frac < 0.5 and pool_n < int(cfg["max_pool"]) and len(pool) < len(order):
                pool_n *= 2
                pool = order[:pool_n]
                score, frac = passes(pool)
                trace["pool_sizes"].append(len(pool))
            current = list(pool)
            impact: dict[int, float] = {}
            while len(current) > k:
                trace["rounds"] += 1
                reps = seeds if len(current) <= int(cfg["one_by_one_below"]) else seeds[:1]
                loo = {p: passes([q for q in current if q != p], reps)[0] for p in current}
                for p, s in loo.items():
                    impact[p] = score - s
                ranked = sorted(current, key=lambda p: (-loo[p], -deg[p], p))  # highest remaining score first = least impactful
                if len(current) <= int(cfg["one_by_one_below"]):
                    victim = ranked[0]
                    new = [q for q in current if q != victim]
                    s2, f2 = passes(new)
                    if f2 < 0.5:  # removing the least impactful breaks it: everything left is needed -> stop
                        break
                    current, score = new, s2
                else:
                    batch = ranked[: max(1, (len(current) - k) // 2)]
                    while batch:
                        new = [q for q in current if q not in set(batch)]
                        s2, f2 = passes(new)
                        if f2 >= 0.5:
                            current, score = new, s2
                            break
                        batch = batch[: len(batch) // 2]
                    if not batch:
                        break
        except BudgetExhausted:
            trace["budget_exhausted"] = True
            current = list(locals().get("current", locals().get("pool", [])))[:max(k, 1)] if "current" in locals() else []
        core = sorted(int(p) for p in current)
        essential: dict[int, bool | None] = {}
        try:
            for p in core:
                outs = sim.evaluate(silence([p]), seeds, t_end=t_end)
                essential[p] = bool(np.mean([o.passed for o in outs]) < 0.5)
        except BudgetExhausted:
            pass
        try:
            fin = sim.evaluate(keep_only(problem, core), seeds, t_end=t_end)
            fid = {"keep_only_pass_fraction": float(np.mean([o.passed for o in fin])), "keep_only_score_mean": float(np.mean([o.score for o in fin])),
                   "frequency_hz": float(np.nanmedian([o.frequency_hz if o.frequency_hz is not None else np.nan for o in fin]))
                   if any(o.frequency_hz is not None for o in fin) else None}
        except BudgetExhausted:
            fid = {}
        return DiscoveryResult(core=core, inclusion_probability={p: (1.0 if p in set(core) else 0.0) for p in order},
                               roles={}, essential=essential, alternatives=[], loop=core, predicted_frequency_hz=fid.get("frequency_hz"),
                               predicted_function_preserved=(fid.get("keep_only_pass_fraction", 0.0) >= 0.5) if fid else None, fidelity=fid,
                               budget={**sim.report(), "wall_s": round(time.time() - t0, 1)}, diagnostics=trace,
                               motif="greedy backward elimination survivors")
