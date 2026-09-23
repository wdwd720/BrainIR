"""The budgeted, cached simulator oracle every discovery method must go through.

* Every simulation is one **call**; the budget (``max_calls``) is hard — exceeding it raises :class:`BudgetExhausted`.
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

The oracle returns :class:`Outcome` records: the criterion's score/pass verdict plus a compact activity fingerprint
(which neurons were active, readout statistics). No oracle information of any kind is available here.
"""

from __future__ import annotations

import datetime as _dt
import functools
import hashlib
import json
import sqlite3
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


SIM_CODE_FILES = ("sim/model.py", "discovery/criteria.py", "metrics/rhythm.py")


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

    def key(self, problem_hash: str, criterion_spec: dict) -> str:
        payload = {"net": problem_hash, "seed": int(self.seed), "iv": canonical(self.intervention),
                   "stim": None if self.stimulus is None else [list(self.stimulus.indices), list(self.stimulus.currents), self.stimulus.pulse_start,
                                                               self.stimulus.pulse_end],
                   "t_end": self.t_end, "cfg": dict(sorted(self.cfg_override.items())), "criterion": criterion_spec, "code": sim_code_version()}
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


class BudgetedSimulator:
    def __init__(self, problem: DiscoveryProblem, max_calls: int, *, workers: int = 1, backend=None, cache: dict | None = None,
                 log: list | None = None, store: CausalEffectCache | None = None):
        self.problem = problem
        self.max_calls = int(max_calls)
        self.workers = int(workers)
        self.backend = backend
        self.cache: dict[str, Outcome] = cache if cache is not None else {}
        self.log = log
        self.store = store
        self.calls = 0
        self.cache_hits = 0
        self.store_hits = 0
        self.computed_calls = 0
        self.simulated_seconds = 0.0
        self.cpu_seconds = 0.0
        self.wall_seconds = 0.0
        self.n_batches = 0
        self._interventions: set[str] = set()
        self._keep_only_sets: set[tuple[int, ...]] = set()
        self._hash = problem.network_hash()
        self._crit = dict(problem.criterion_spec)

    # ------------------------------------------------------------------ accounting
    @property
    def remaining(self) -> int:
        return self.max_calls - self.calls

    def report(self) -> dict:
        """Budget accounting. ``calls`` = queries charged to the method (computed + served from the persistent store);
        ``cache_hits`` = repeats answered by the in-run memo (free)."""
        return {"max_calls": self.max_calls, "calls": self.calls, "cache_hits": self.cache_hits, "store_hits": self.store_hits,
                "computed_calls": self.computed_calls, "simulated_seconds": round(self.simulated_seconds, 3),
                "cpu_seconds": round(self.cpu_seconds, 3), "wall_seconds": round(self.wall_seconds, 3), "batches": self.n_batches,
                "n_distinct_interventions": len(self._interventions), "n_candidate_mechanisms": len(self._keep_only_sets),
                "network_hash": self._hash[:16], "code_version": sim_code_version()}

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
        for q in queries:
            c = canonical(q.intervention)
            self._interventions.add(json.dumps(c, sort_keys=True))
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
                computed = dict(zip(compute, results))
                if self.store is not None:
                    self.store.put_many([(k, self._hash, res) for k, res in computed.items()])
            for k, q in todo.items():
                res = computed[k] if k in computed else stored[k]
                self.cache[k] = self._outcome(res)
                self.calls += 1
                self.simulated_seconds += float(res.get("simulated_s", 0.0))
                if k in computed:
                    self.computed_calls += 1
                    self.cpu_seconds += float(res.get("cpu_s", 0.0))
                else:
                    self.store_hits += 1
                if self.log is not None:
                    self.log.append({"key": k[:16], "seed": q.seed, "intervention": canonical(q.intervention), "score": res["score"],
                                     "passed": res["passed"], "from_store": k not in computed})
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
                 "solver_success", "wall_s", "cpu_s"}
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
