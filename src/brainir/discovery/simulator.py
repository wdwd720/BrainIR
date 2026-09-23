"""The budgeted, cached simulator oracle every discovery method must go through.

* Every simulation is one **call**; the budget (``max_calls``) is hard — exceeding it raises :class:`BudgetExhausted`.
  Cache hits do not count. Accounting also records simulated biological seconds and wall time.
* Results are cached by a content hash of (network hash, model config, parameter seed, canonical intervention,
  stimulus, t_end, criterion spec) so identical queries — within a run or across methods on the same problem — are
  never re-simulated and never reused across a different parameter ensemble.
* Batched execution: :meth:`run_many` deduplicates queries, serves cache hits, and runs the rest on a
  :mod:`brainir.compute` backend (local pool or Modal) with the network as a shared payload.

The oracle returns :class:`Outcome` records: the criterion's score/pass verdict plus a compact activity fingerprint
(which neurons were active, readout statistics). No oracle information of any kind is available here.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field

import numpy as np

from ..sim.model import Intervention, ModelConfig, Stimulus, sample_neuron_params, simulate
from .criteria import criterion_from_spec
from .interventions import canonical
from .problem import DiscoveryProblem


class BudgetExhausted(RuntimeError):
    pass


@dataclass(frozen=True)
class SimQuery:
    intervention: Intervention | None
    seed: int
    """Parameter-replicate seed (draws the per-neuron parameters from the model's distributions)."""
    stimulus: Stimulus | None = None
    """None = the problem's stimulus."""
    t_end: float | None = None
    """None = the model config's t_end."""
    cfg_override: dict = field(default_factory=dict)
    """Optional ModelConfig field overrides (e.g. widened parameter sds for robustness probes)."""

    def key(self, problem_hash: str, criterion_spec: dict) -> str:
        payload = {"net": problem_hash, "seed": int(self.seed), "iv": canonical(self.intervention),
                   "stim": None if self.stimulus is None else [list(self.stimulus.indices), list(self.stimulus.currents), self.stimulus.pulse_start,
                                                               self.stimulus.pulse_end],
                   "t_end": self.t_end, "cfg": dict(sorted(self.cfg_override.items())), "criterion": criterion_spec}
        return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


@dataclass
class Outcome:
    score: float
    passed: bool
    frequency_hz: float | None
    n_active_readout: int
    n_active_all: int
    active_positions: np.ndarray
    readout_peak_median_hz: float
    solver_success: bool
    wall_s: float
    extra: dict = field(default_factory=dict)
    cached: bool = False

    def to_dict(self) -> dict:
        return {"score": self.score, "passed": self.passed, "frequency_hz": self.frequency_hz, "n_active_readout": self.n_active_readout,
                "n_active_all": self.n_active_all, "readout_peak_median_hz": self.readout_peak_median_hz, "solver_success": self.solver_success,
                "wall_s": self.wall_s, "cached": self.cached, **{k: v for k, v in self.extra.items() if not isinstance(v, np.ndarray)}}


def _simulate_query(args) -> dict:
    """Worker: (W, sizes, cfg_dict, stim, iv, seed, t_end, cfg_override, criterion_spec, readout_mask) -> outcome dict."""
    W, sizes, cfg_dict, stim, iv, seed, t_end, cfg_override, criterion_spec, readout_mask = args
    cfg = ModelConfig(**{**cfg_dict, **cfg_override, **({"t_end": t_end} if t_end is not None else {})})
    t0 = time.time()
    params = sample_neuron_params(cfg, W.shape[0], int(seed), sizes)
    traj = simulate(W, params, cfg, stim, iv)
    res = criterion_from_spec(criterion_spec).evaluate(traj, readout_mask)
    res["wall_s"] = time.time() - t0
    res["simulated_s"] = float(cfg.t_end)
    return res


class BudgetedSimulator:
    def __init__(self, problem: DiscoveryProblem, max_calls: int, *, workers: int = 1, backend=None, cache: dict | None = None,
                 log: list | None = None):
        self.problem = problem
        self.max_calls = int(max_calls)
        self.workers = int(workers)
        self.backend = backend
        self.cache: dict[str, Outcome] = cache if cache is not None else {}
        self.log = log
        self.calls = 0
        self.cache_hits = 0
        self.simulated_seconds = 0.0
        self.wall_seconds = 0.0
        self.n_batches = 0
        self._hash = problem.network_hash()
        self._crit = dict(problem.criterion_spec)

    # ------------------------------------------------------------------ accounting
    @property
    def remaining(self) -> int:
        return self.max_calls - self.calls

    def report(self) -> dict:
        return {"max_calls": self.max_calls, "calls": self.calls, "cache_hits": self.cache_hits, "simulated_seconds": round(self.simulated_seconds, 3),
                "wall_seconds": round(self.wall_seconds, 3), "batches": self.n_batches, "network_hash": self._hash[:16]}

    # ------------------------------------------------------------------ execution
    def run(self, query: SimQuery) -> Outcome:
        return self.run_many([query])[0]

    def run_many(self, queries: list[SimQuery]) -> list[Outcome]:
        keys = [q.key(self._hash, self._crit) for q in queries]
        todo: dict[str, SimQuery] = {}
        for k, q in zip(keys, queries):
            if k not in self.cache and k not in todo:
                todo[k] = q
        if self.calls + len(todo) > self.max_calls:
            raise BudgetExhausted(f"{len(todo)} new simulations requested with {self.remaining} of {self.max_calls} calls left")
        if todo:
            t0 = time.time()
            jobs = [self._job(q) for q in todo.values()]
            if self.backend is not None:
                from ..compute.backend import Shared, split_failures
                shared = {"W": self.problem.W, "sizes": self.problem.sizes, "readout": self.problem.readout_mask}
                sjobs = [(Shared("W"), Shared("sizes"), *j[2:9], Shared("readout")) for j in jobs]
                results, failed = split_failures(self.backend.map(_simulate_query, sjobs, shared=shared))
                if failed:
                    raise RuntimeError(f"{len(failed)} simulations failed on {self.backend.name}: {failed[0]}")
            elif self.workers > 1 and len(jobs) > 1:
                from concurrent.futures import ProcessPoolExecutor
                with ProcessPoolExecutor(max_workers=self.workers) as ex:
                    results = list(ex.map(_simulate_query, jobs))
            else:
                results = [_simulate_query(j) for j in jobs]
            for (k, q), res in zip(todo.items(), results):
                self.cache[k] = self._outcome(res)
                self.calls += 1
                self.simulated_seconds += float(res.get("simulated_s", 0.0))
                if self.log is not None:
                    self.log.append({"key": k[:16], "seed": q.seed, "intervention": canonical(q.intervention), "score": res["score"],
                                     "passed": res["passed"]})
            self.wall_seconds += time.time() - t0
            self.n_batches += 1
        out = []
        for k in keys:
            o = self.cache[k]
            if k not in todo:
                self.cache_hits += 1
                o = Outcome(**{**o.__dict__, "cached": True})
            out.append(o)
        return out

    def _job(self, q: SimQuery):
        stim = q.stimulus if q.stimulus is not None else self.problem.stimulus()
        return (self.problem.W, self.problem.sizes, self.problem.model_cfg.to_dict(), stim, q.intervention, int(q.seed), q.t_end,
                dict(q.cfg_override), self._crit, self.problem.readout_mask)

    @staticmethod
    def _outcome(res: dict) -> Outcome:
        known = {"score", "passed", "frequency_hz", "n_active_readout", "n_active_all", "active_positions", "readout_peak_median_hz",
                 "solver_success", "wall_s"}
        return Outcome(score=float(res["score"]), passed=bool(res["passed"]), frequency_hz=res.get("frequency_hz"),
                       n_active_readout=int(res["n_active_readout"]), n_active_all=int(res["n_active_all"]),
                       active_positions=np.asarray(res["active_positions"], dtype=np.int32), readout_peak_median_hz=float(res["readout_peak_median_hz"]),
                       solver_success=bool(res["solver_success"]), wall_s=float(res["wall_s"]), extra={k: v for k, v in res.items() if k not in known})

    # ------------------------------------------------------------------ convenience
    def evaluate(self, intervention: Intervention | None, seeds: list[int], **kw) -> list[Outcome]:
        return self.run_many([SimQuery(intervention, int(s), **kw) for s in seeds])

    def pass_fraction(self, intervention: Intervention | None, seeds: list[int], **kw) -> float:
        outs = self.evaluate(intervention, seeds, **kw)
        return float(np.mean([o.passed for o in outs])) if outs else 0.0
