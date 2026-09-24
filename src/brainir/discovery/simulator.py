"""The budgeted, cached simulator every discovery method must go through.

* Every simulation is one **call**; the budget (``max_calls``) is hard — exceeding it raises :class:`BudgetExhausted`.
  Simulators spawned for other networks (:meth:`BudgetedSimulator.spawn`) draw from the same budget: one pool per run.
  Repeating a query already answered in the same run is free (in-run memo). Accounting also records simulated
  biological seconds, CPU seconds, wall time, the number of distinct interventions and of distinct candidate
  mechanisms (keep-only sets) queried (goal3 section 19).
* Results are keyed by a content hash of (network hash — matrix, sizes, stimulus incl. pulse timing, readout, model
  config, criterion — parameter seed, canonical intervention, stimulus override, t_end, config overrides, simulator /
  criterion code version), so an outcome is never reused across a different network, parameter ensemble or code.
* Optional persistent **causal-effect cache** (:class:`CausalEffectCache`, goal3 section 38): outcomes shared across
  runs and methods. A query served from the store is still CHARGED to the method as a call — the store saves compute,
  never budget — so a method's accounting and behaviour do not depend on how warm the cache is.
* Batched execution: :meth:`run_many` deduplicates queries, serves memo/store hits, and runs the rest on a
  :mod:`brainir.compute` backend (local pool or Modal) with the network as a shared payload.

It returns :class:`Outcome` records: the criterion's score/pass verdict plus an activity fingerprint (which neurons were
active, graded per-neuron mean and peak rates in the analysis window, readout statistics). Queries may also remove individual
synapses (``SimQuery.remove_edges``). No hidden-benchmark (oracle) information of any kind is available here.
"""

from __future__ import annotations

import contextlib
import datetime as _dt
import functools
import hashlib
import json
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..sim.model import Intervention, ModelConfig, Stimulus, sample_neuron_params, simulate
from .criteria import criterion_from_spec
from .interventions import canonical
from .problem import DiscoveryProblem


class BudgetExhausted(RuntimeError):
    pass


SIM_CODE_FILES = ("sim/model.py", "discovery/criteria.py", "metrics/rhythm.py", "discovery/simulator.py", "discovery/problem.py",
                  "discovery/interventions.py")


@functools.lru_cache(maxsize=1)
def sim_code_version() -> str:
    """Short hash of the code that turns a query into an outcome (simulator, criteria, rhythm metric)."""
    base = Path(__file__).resolve().parents[1]
    h = hashlib.sha256()
    for rel in SIM_CODE_FILES:
        p = base / rel
        h.update(rel.encode())
        h.update(p.read_bytes().replace(b"\r\n", b"\n") if p.exists() else b"<missing>")
    return h.hexdigest()[:16]


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
    remove_edges: tuple = ()
    """Synapses removed for this simulation, as (post, pre) position pairs (an edge-removal intervention: the entry W[post, pre]
    is zeroed; applied on top of ``intervention``). One call per replicate, like any query (review G finding 5)."""

    def key(self, problem_hash: str, criterion_spec: dict) -> str:
        payload = {"net": problem_hash, "seed": int(self.seed), "iv": canonical(self.intervention),
                   "stim": None if self.stimulus is None else [list(self.stimulus.indices), list(self.stimulus.currents), self.stimulus.pulse_start,
                                                               self.stimulus.pulse_end],
                   "t_end": self.t_end, "cfg": dict(sorted(self.cfg_override.items())), "criterion": criterion_spec, "code": sim_code_version()}
        if self.remove_edges:
            payload["removed_edges"] = [list(e) for e in self.remove_edges]
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
    mean_rate_hz: np.ndarray | None = None
    """Per-neuron mean rate in the criterion's analysis window (read-only; graded participation, review G finding 8)."""
    peak_rate_hz: np.ndarray | None = None
    """Per-neuron peak rate in the analysis window (read-only; ``active_positions`` = peak above the criterion's threshold)."""

    def to_dict(self) -> dict:
        return {"score": self.score, "passed": self.passed, "frequency_hz": self.frequency_hz, "n_active_readout": self.n_active_readout,
                "n_active_all": self.n_active_all, "readout_peak_median_hz": self.readout_peak_median_hz, "solver_success": self.solver_success,
                "wall_s": self.wall_s, "cached": self.cached, **{k: v for k, v in self.extra.items() if not isinstance(v, np.ndarray)}}


def _simulate_query(args) -> dict:
    """Worker: (W, sizes, cfg_dict, stim, iv, seed, t_end, cfg_override, criterion_spec, readout_mask) -> outcome dict."""
    W, sizes, cfg_dict, stim, iv, seed, t_end, cfg_override, criterion_spec, readout_mask = args
    cfg = ModelConfig(**{**cfg_dict, **cfg_override, **({"t_end": t_end} if t_end is not None else {})})
    t0, c0 = time.time(), time.process_time()
    params = sample_neuron_params(cfg, W.shape[0], int(seed), sizes)
    traj = simulate(W, params, cfg, stim, iv)
    res = criterion_from_spec(criterion_spec).evaluate(traj, readout_mask)
    res["wall_s"] = time.time() - t0
    res["cpu_s"] = time.process_time() - c0
    res["simulated_s"] = float(cfg.t_end)
    return res


def _jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


class CausalEffectCache:
    """Persistent content-addressed store of simulation outcomes (SQLite), shared across runs and methods (goal3 section 38).

    Keys are :meth:`SimQuery.key` values, which already bind the network content, parameter seed, intervention, protocol and
    simulator/criterion code version; a stored outcome can therefore only answer the identical query. Local use only (remote
    workers keep their in-run memo)."""

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._con = sqlite3.connect(str(self.path))
        self._con.execute("CREATE TABLE IF NOT EXISTS outcome (key TEXT PRIMARY KEY, network TEXT, code TEXT, payload TEXT, created_utc TEXT)")
        self._con.commit()
        self.hits = 0
        self.writes = 0

    def get_many(self, keys: list[str]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for i in range(0, len(keys), 500):
            chunk = keys[i:i + 500]
            q = f"SELECT key, payload FROM outcome WHERE key IN ({','.join('?' * len(chunk))})"
            for k, payload in self._con.execute(q, chunk):
                out[k] = json.loads(payload)
        self.hits += len(out)
        return out

    def put_many(self, rows: list[tuple[str, str, dict]]) -> None:
        stamp = _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self._con.executemany("INSERT OR IGNORE INTO outcome (key, network, code, payload, created_utc) VALUES (?, ?, ?, ?, ?)",
                              [(k, net, sim_code_version(), json.dumps(res, default=_jsonable), stamp) for k, net, res in rows])
        self._con.commit()
        self.writes += len(rows)

    def __len__(self) -> int:
        return int(self._con.execute("SELECT COUNT(*) FROM outcome").fetchone()[0])

    def close(self) -> None:
        self._con.close()


ALLOWED_CFG_OVERRIDES = frozenset({"tau_sd", "a_sd", "theta_sd", "r_max_sd"})
RESERVED_SEED_FLOOR = 5000
"""Parameter seeds >= this value are reserved for independent scoring / validation (tournament 5000-5003, weight-noise probes
6000+, reliability fidelity 7000-7007, transfer checks 8100-8105, nulls 9100-9201); methods must query seeds below it. The frozen
evaluator draws 1000-1015, so the blind run's seed must keep a method's seeds below 1000 as well (seed 0 does for every method
that derives seeds as ``seed * 1000 + offset`` with offset < 1000)."""


class BudgetViolation(RuntimeError):
    """A run used simulations it was not charged for, or more calls than its budget."""


@contextlib.contextmanager
def count_real_simulations():
    """Count every call of ``brainir.sim.model.simulate`` made in this process while the context is active (the budget-integrity
    guard: the harness compares the count with the calls charged by the BudgetedSimulator(s) of the run). Methods that import the
    simulator function at module import time are not seen here; a static test forbids such imports in method modules."""
    from ..sim import model as _model

    this = sys.modules[__name__]
    orig_model, orig_here = _model.simulate, this.simulate
    counter = {"n": 0}

    def counting(*a, **k):
        counter["n"] += 1
        return orig_model(*a, **k)

    _model.simulate = counting
    this.simulate = counting
    try:
        yield counter
    finally:
        _model.simulate = orig_model
        this.simulate = orig_here


class BudgetedSimulator:
    """The only path from a discovery method to the simulator. Accounting attributes are read-only; the budget can only be
    tightened (:meth:`close`); simulations of another network go through :meth:`spawn` so that the harness sees them."""

    def __init__(self, problem: DiscoveryProblem, max_calls: int, *, workers: int = 1, backend=None, cache: dict | None = None,
                 log: list | None = None, store: CausalEffectCache | None = None):
        self.problem = problem
        self._max_calls = int(max_calls)
        self.workers = int(workers)
        self.backend = backend
        self.cache: dict[str, Outcome] = cache if cache is not None else {}
        self.log = log
        self.store = store
        self._calls = 0
        self._cache_hits = 0
        self._store_hits = 0
        self._computed_calls = 0
        self._simulated_seconds = 0.0
        self._cpu_seconds = 0.0
        self._wall_seconds = 0.0
        self._n_batches = 0
        self._interventions: set[str] = set()
        self._keep_only_sets: set[tuple[int, ...]] = set()
        self._param_seeds: set[int] = set()
        self._children: list[tuple[str, BudgetedSimulator]] = []
        self._parent: BudgetedSimulator | None = None  # set only by spawn(): a child draws from its parent's budget
        self._hash = problem.network_hash()
        self._crit = dict(problem.criterion_spec)
        self._t_end_default = float(problem.model_cfg.t_end)

    # ------------------------------------------------------------------ accounting (read-only)
    @property
    def max_calls(self) -> int:
        return self._max_calls

    @property
    def calls(self) -> int:
        return self._calls

    @property
    def cache_hits(self) -> int:
        return self._cache_hits

    @property
    def store_hits(self) -> int:
        return self._store_hits

    @property
    def computed_calls(self) -> int:
        return self._computed_calls

    @property
    def simulated_seconds(self) -> float:
        return self._simulated_seconds

    @property
    def cpu_seconds(self) -> float:
        return self._cpu_seconds

    @property
    def wall_seconds(self) -> float:
        return self._wall_seconds

    @property
    def n_batches(self) -> int:
        return self._n_batches

    @property
    def remaining(self) -> int:
        """Calls still available: this simulator's cap minus everything charged to it (its children included), and never more
        than its parent has left (one budget pool per run)."""
        own = self._max_calls - self.total_calls()
        return own if self._parent is None else min(own, self._parent.remaining)

    def close(self) -> None:
        """No further calls: the budget becomes what was spent (used by ledgers that hand out successive allowances)."""
        self._max_calls = self.total_calls()

    def spawn(self, problem: DiscoveryProblem, max_calls: int, *, kind: str = "auxiliary", cache: dict | None = None) -> BudgetedSimulator:
        """A simulator for ANOTHER network (e.g. the other connectome of a bundle), capped at ``max_calls``.

        Its calls are drawn from THIS simulator's budget (review E finding 6): a run declared at budget B performs at most B
        simulations in total, on every network. The child can never spend more than this simulator has left, and every child
        call reduces this simulator's ``remaining``. Child calls are reported under ``report()["children"]`` and counted by the
        harness's integrity check."""
        child = BudgetedSimulator(problem, max_calls, workers=self.workers, backend=self.backend, cache=cache, log=self.log)
        child._parent = self
        self._children.append((str(kind), child))
        return child

    def param_seeds(self) -> list[int]:
        """Parameter seeds queried by this simulator and its children (for the harness's seed-namespace check)."""
        out = set(self._param_seeds)
        for _k, c in self._children:
            out |= set(c.param_seeds())
        return sorted(out)

    def total_computed_calls(self) -> int:
        return self._computed_calls + sum(c.total_computed_calls() for _k, c in self._children)

    def total_calls(self) -> int:
        return self._calls + sum(c.total_calls() for _k, c in self._children)

    def total_simulated_seconds(self) -> float:
        return self._simulated_seconds + sum(c.total_simulated_seconds() for _k, c in self._children)

    def report(self) -> dict:
        """Budget accounting. ``calls`` = queries charged to the method (computed + served from the persistent store);
        ``cache_hits`` = repeats answered by the in-run memo (free); ``children`` = simulators spawned for other networks."""
        seeds = self.param_seeds()
        out = {"max_calls": self._max_calls, "calls": self._calls, "cache_hits": self._cache_hits, "store_hits": self._store_hits,
               "computed_calls": self._computed_calls, "simulated_seconds": round(self._simulated_seconds, 3),
               "cpu_seconds": round(self._cpu_seconds, 3), "wall_seconds": round(self._wall_seconds, 3), "batches": self._n_batches,
               "n_distinct_interventions": len(self._interventions), "n_candidate_mechanisms": len(self._keep_only_sets),
               "param_seeds": {"n": len(seeds), "min": seeds[0] if seeds else None, "max": seeds[-1] if seeds else None},
               "network_hash": self._hash[:16], "code_version": sim_code_version()}
        out["total_calls"] = self.total_calls()  # every call charged to this run's budget, children included (compare on this)
        if self._parent is not None:
            out["pooled_with_parent"] = True
        if self._children:
            out["children"] = [{"kind": k, **c.report()} for k, c in self._children]
            out["total_calls_incl_children"] = self.total_calls()
        return out

    # ------------------------------------------------------------------ execution
    def run(self, query: SimQuery) -> Outcome:
        return self.run_many([query])[0]

    def _normalize(self, q: SimQuery) -> SimQuery:
        """Validate a query and give equivalent queries one key (effective t_end, default stimulus, no-op overrides)."""
        iv = q.intervention
        if iv is not None:
            if float(iv.weight_noise_sd or 0.0) > 0.0 and iv.weight_noise_seed is None:
                raise ValueError("weight noise needs an explicit weight_noise_seed (an unseeded draw would be cached under one key)")
            if iv.scale_by_nt:
                raise ValueError("Intervention.scale_by_nt is not supported by the discovery simulator")
            if not iv.silence and iv.keep_only is None and not float(iv.weight_noise_sd or 0.0) > 0.0:
                iv = None
        bad = set(q.cfg_override) - ALLOWED_CFG_OVERRIDES
        if bad:
            raise ValueError(f"cfg_override may only set {sorted(ALLOWED_CFG_OVERRIDES)}; got {sorted(bad)}")
        cfg = self.problem.model_cfg
        override = {k: float(v) for k, v in q.cfg_override.items() if float(v) != float(getattr(cfg, k))}
        t_end = self._t_end_default if q.t_end is None else float(q.t_end)
        if t_end > self._t_end_default + 1e-12 or t_end <= 0:
            raise ValueError(f"t_end must be in (0, {self._t_end_default}]")
        stim = q.stimulus
        if stim is not None and stim == self.problem.stimulus():
            stim = None
        edges: tuple = ()
        if q.remove_edges:
            n = self.problem.n
            pairs = set()
            for e in q.remove_edges:
                post, pre = (int(x) for x in e)
                if not (0 <= post < n and 0 <= pre < n):
                    raise ValueError(f"remove_edges: ({post}, {pre}) is outside the network")
                if self.problem.W[post, pre] != 0:  # removing an absent synapse is a no-op: the query is the unmodified one
                    pairs.add((post, pre))
            edges = tuple(sorted(pairs))
        return SimQuery(iv, int(q.seed), stim, t_end, override, edges)

    def run_many(self, queries: list[SimQuery]) -> list[Outcome]:
        queries = [self._normalize(q) for q in queries]
        keys = [q.key(self._hash, self._crit) for q in queries]
        todo: dict[str, SimQuery] = {}
        for k, q in zip(keys, queries):
            if k not in self.cache and k not in todo:
                todo[k] = q
        if len(todo) > self.remaining:
            raise BudgetExhausted(f"{len(todo)} new simulations requested with {self.remaining} of {self._max_calls} calls left"
                                  + (" (pooled with the parent run)" if self._parent is not None else ""))
        for q in queries:
            c = canonical(q.intervention)
            self._interventions.add(json.dumps({**c, "removed_edges": [list(e) for e in q.remove_edges]} if q.remove_edges else c, sort_keys=True))
            self._param_seeds.add(int(q.seed))
            if c.get("keep_only") is not None:
                self._keep_only_sets.add(tuple(sorted(int(x) for x in c["keep_only"])))
        if todo:
            t0 = time.time()
            stored = self.store.get_many(list(todo)) if self.store is not None else {}
            compute = {k: q for k, q in todo.items() if k not in stored}
            computed: dict[str, dict] = {}
            if compute:
                jobs = [self._job(q) for q in compute.values()]
                if self.backend is not None:
                    from ..compute.backend import Shared, split_failures
                    shared = {"W": self.problem.W, "sizes": self.problem.sizes, "readout": self.problem.readout_mask}
                    # a query with removed synapses carries its own matrix; every other query shares the network's
                    sjobs = [((j[0] if q.remove_edges else Shared("W")), Shared("sizes"), *j[2:9], Shared("readout"))
                             for j, q in zip(jobs, compute.values())]
                    results, failed = split_failures(self.backend.map(_simulate_query, sjobs, shared=shared))
                    if failed:
                        raise RuntimeError(f"{len(failed)} simulations failed on {self.backend.name}: {failed[0]}")
                elif self.workers > 1 and len(jobs) > 1:
                    from concurrent.futures import ProcessPoolExecutor
                    with ProcessPoolExecutor(max_workers=self.workers) as ex:
                        results = list(ex.map(_simulate_query, jobs))
                else:
                    results = [_simulate_query(j) for j in jobs]
                computed = dict(zip(compute, results))
                if self.store is not None:
                    self.store.put_many([(k, self._hash, res) for k, res in computed.items()])
            for k, q in todo.items():
                res = computed[k] if k in computed else stored[k]
                self.cache[k] = self._outcome(res)
                self._calls += 1
                self._simulated_seconds += float(res.get("simulated_s", 0.0))
                if k in computed:
                    self._computed_calls += 1
                    self._cpu_seconds += float(res.get("cpu_s", 0.0))
                else:
                    self._store_hits += 1
                if self.log is not None:
                    self.log.append({"key": k[:16], "seed": q.seed, "intervention": canonical(q.intervention), "score": res["score"],
                                     "passed": res["passed"], "from_store": k not in computed,
                                     **({"removed_edges": [list(e) for e in q.remove_edges]} if q.remove_edges else {})})
            self._wall_seconds += time.time() - t0
            self._n_batches += 1
        out = []
        for k in keys:
            o = self.cache[k]
            if k not in todo:
                self._cache_hits += 1
                o = Outcome(**{**o.__dict__, "cached": True})
            out.append(o)
        return out

    def _job(self, q: SimQuery):
        stim = q.stimulus if q.stimulus is not None else self.problem.stimulus()
        W = self.problem.W
        if q.remove_edges:
            W = W.tolil(copy=True)
            for post, pre in q.remove_edges:
                W[post, pre] = 0.0
            W = W.tocsr()
            W.eliminate_zeros()
        return (W, self.problem.sizes, self.problem.model_cfg.to_dict(), stim, q.intervention, int(q.seed), q.t_end,
                dict(q.cfg_override), self._crit, self.problem.readout_mask)

    @staticmethod
    def _outcome(res: dict) -> Outcome:
        known = {"score", "passed", "frequency_hz", "n_active_readout", "n_active_all", "active_positions", "readout_peak_median_hz",
                 "solver_success", "wall_s", "cpu_s", "mean_rate_hz", "peak_rate_hz"}
        active = np.array(res["active_positions"], dtype=np.int32)
        active.setflags(write=False)  # memo hits share this array: callers must not be able to alter later answers
        rates = {}
        for k in ("mean_rate_hz", "peak_rate_hz"):
            if res.get(k) is not None:
                a = np.array(res[k], dtype=np.float32)
                a.setflags(write=False)
                rates[k] = a
        return Outcome(score=float(res["score"]), passed=bool(res["passed"]), frequency_hz=res.get("frequency_hz"),
                       n_active_readout=int(res["n_active_readout"]), n_active_all=int(res["n_active_all"]),
                       active_positions=active, readout_peak_median_hz=float(res["readout_peak_median_hz"]),
                       solver_success=bool(res["solver_success"]), wall_s=float(res["wall_s"]), extra={k: v for k, v in res.items() if k not in known},
                       **rates)

    # ------------------------------------------------------------------ convenience
    def evaluate(self, intervention: Intervention | None, seeds: list[int], **kw) -> list[Outcome]:
        return self.run_many([SimQuery(intervention, int(s), **kw) for s in seeds])

    def pass_fraction(self, intervention: Intervention | None, seeds: list[int], **kw) -> float:
        outs = self.evaluate(intervention, seeds, **kw)
        return float(np.mean([o.passed for o in outs])) if outs else 0.0
