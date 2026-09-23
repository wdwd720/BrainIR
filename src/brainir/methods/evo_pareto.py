"""Evolutionary multi-objective structured search for causal mechanisms (``evo_pareto``).

A population of candidate keep-only neuron subsets evolves under NSGA-II selection on three objectives, all measured on the
true (budgeted) simulator with common random numbers (every individual sees the same parameter seeds):

    F1 = 1 - nominal pass fraction  (mean criterion score as a 1e-3 tie-breaker)          sufficiency
    F2 = |S|                                                                                 compactness
    F3 = 1 - robust pass fraction (widened parameter sds x2, multiplicative weight noise;   robustness / stability
         0.5 = not measured yet)

Insufficient individuals are ranked behind every sufficient one (constrained domination), so selection pressure goes to
"sufficient and small"; failing offspring stay available for one generation as parents of the repair operator.

Stages
1. Pre-screen. Two intact simulations give the baseline verdict, frequency and the activity fingerprint; a graph flow prior
   (forward influence from the stimulus x backward attribution from the readout, rank-normalised) scores every candidate.
   The pool = neurons active in the intact runs + the top structural nodes. Structure is a proposal prior only.
2. Evolution. Operators are structured by the public graph and by accumulated evidence (per-node dispensability counts,
   size-weighted inclusion frequency among sufficient sets): prune (weighted batch removal), silent-prune (drop members that
   were silent in a passing simulation), leave-one-out probe (single removal from small sufficient sets), repair (add back a
   weighted half of the difference to a known sufficient superset: delta debugging), add (pool neighbours of the current
   set), swap, intersection crossover (A & B of two sufficient parents) and uniform crossover. Evaluation is raced: one
   nominal seed first, the remaining nominal seeds only if it passes, robust probes only for sufficient individuals no
   larger than the smallest fully robust sufficient set found so far (+1), with a per-generation cap.
3. Redundancy probes (when the front stalls, budget permitting). Level 1: for each member m of the smallest sufficient set
   the network minus m (= silencing m) is evaluated with m tabooed for its descendants, so alternative implementations
   without m are found and pruned to minimal sets; level 2+: the network minus the union of all minimal sets found so far
   (hitting-set style enumeration of further implementations).
4. Confirmation and necessity. The smallest compact minimal sufficient sets receive extra fresh seeds and the full robust
   ensemble; the knee of those candidates is reduced by evidence-based leave-one-out (a member is dropped only when the
   reduced set, on the same seeds and probes, wins the knee comparison). A single-neuron silencing screen in the FULL network
   (at most ``screen_max`` neurons: the candidates' members, then pool neighbours) measures in-situ necessity. The core is
   the knee of {reduced set, other candidates} on phi = 0.5 nominal + 0.2 robust + 0.3 in-situ relevance (fraction of
   essential members) against an absolute per-member size cost (reduced again if it changed); essential neurons outside it
   (gatekeepers, e.g. lateral inhibition that only matters in the presence of a competitor) join it when the union is still
   sufficient; every leave-one-out child of the final core is evaluated (minimality with evidence).
5. Reporting: essential per core member (from the screen); leave-one-out inside the core = necessity within the core;
   alternatives = compact minimal sufficient sets that are not supersets of the core; inclusion probabilities = size- and
   robustness-weighted frequency across minimal sufficient sets (0.9) and all sufficient sets (0.1), adjusted by
   leave-one-out and essentiality evidence; generic roles from sign, cycle membership, stimulus input / readout output,
   the criterion type and the evidence.

Budget: the search stops when the remaining calls reach the reserve for stages 4-5, when the front stalls (after the
redundancy levels), or at the generation cap; every phase is guarded by ``sim.remaining`` and a partial result is returned
when the budget runs out. Nothing here refers to any dataset, cell type, neuron id or expected mechanism size.

Optional prior: ``config["prior"] = {position: p}`` (e.g. transported from another network) shifts the per-node
keep/add preference by +-0.2, adds favoured nodes to the pool and seeds the initial population with them; absent = uniform.
The reported probabilities remain evidence-based (the prior only steers proposals).
"""

from __future__ import annotations

import math
import sys
import time
from dataclasses import dataclass, field

import numpy as np
from scipy.sparse.csgraph import connected_components

from brainir.discovery.interface import DiscoveryMethod, DiscoveryResult, MethodRegistry
from brainir.discovery.interventions import keep_only, silence
from brainir.discovery.problem import DiscoveryProblem
from brainir.discovery.simulator import BudgetedSimulator, BudgetExhausted, Outcome, SimQuery

TIE = 1e-3
"""Score tie-breaker weight inside the pass-fraction objectives (pass fractions are multiples of 1/n_seeds >= 1/16)."""
UNKNOWN_ROBUST = 0.5
"""F3 of a sufficient individual whose robustness has not been measured yet."""
INFEASIBLE = 1.0e6
"""Size offset that ranks every insufficient individual behind every sufficient one (constrained domination)."""
SIZE_COST = 0.35
"""Knee: distance cost of one extra member (one robust failure out of four costs 0.2 -> 0.2, one nominal failure out of
five costs 0.4, half the members essential instead of none costs 0.6)."""


# ---------------------------------------------------------------------------------------------------------------- individuals
@dataclass
class Individual:
    members: tuple[int, ...]
    born: int = 0
    op: str = "init"
    taboo: frozenset = frozenset()
    """Positions this lineage must never contain (redundancy probes: 'a mechanism without these')."""
    parent_pass: tuple[int, ...] | None = None
    """A known sufficient superset (for the repair operator)."""
    removed: tuple[int, ...] = ()
    """What the operator removed from a sufficient parent (dispensability bookkeeping)."""
    nominal: dict = field(default_factory=dict)
    """seed -> Outcome (nominal ensemble)."""
    robust: dict = field(default_factory=dict)
    """probe key -> Outcome (widened-parameter and weight-noise ensembles)."""
    n_nominal_total: int = 1

    @property
    def size(self) -> int:
        return len(self.members)

    def pass_nominal(self) -> float:
        """Pass fraction over the nominal ensemble; seeds not simulated (racing) count as failures."""
        if not self.nominal:
            return 0.0
        return sum(1 for o in self.nominal.values() if o.passed) / max(self.n_nominal_total, len(self.nominal))

    def sufficient(self) -> bool:
        return len(self.nominal) >= self.n_nominal_total and all(o.passed for o in self.nominal.values())

    def score_nominal(self) -> float:
        return float(np.mean([o.score for o in self.nominal.values()])) if self.nominal else 0.0

    def pass_robust(self) -> float | None:
        if not self.robust:
            return None
        return sum(1 for o in self.robust.values() if o.passed) / len(self.robust)

    def score_robust(self) -> float:
        return float(np.mean([o.score for o in self.robust.values()])) if self.robust else 0.0

    def objectives(self) -> tuple[float, float, float]:
        pn = self.pass_nominal()
        f1 = 1.0 - pn - TIE * self.score_nominal()
        if not self.sufficient():
            return (f1, float(self.size) + INFEASIBLE, 1.0 + (1.0 - pn))
        pr = self.pass_robust()
        f3 = UNKNOWN_ROBUST if pr is None else (1.0 - pr - TIE * self.score_robust())
        return (f1, float(self.size), f3)

    def active_union(self) -> set[int]:
        out: set[int] = set()
        for o in self.nominal.values():
            if o.passed:
                out.update(int(x) for x in o.active_positions)
        return out

    def frequency(self) -> float | None:
        f = [o.frequency_hz for o in self.nominal.values() if o.frequency_hz is not None]
        return float(np.median(f)) if f else None

    def n_active_readout(self) -> int | None:
        v = [o.n_active_readout for o in self.nominal.values() if o.passed]
        return int(np.median(v)) if v else None


# ---------------------------------------------------------------------------------------------------------- NSGA-II utilities
def non_dominated_sort(F: np.ndarray) -> list[list[int]]:
    """Fast non-dominated sorting (minimisation). Returns fronts as lists of row indices (deterministic order)."""
    n = len(F)
    if n == 0:
        return []
    le = (F[:, None, :] <= F[None, :, :]).all(-1)
    lt = (F[:, None, :] < F[None, :, :]).any(-1)
    dom = le & lt  # dom[p, q]: p dominates q
    n_dom = dom.sum(axis=0)
    fronts: list[list[int]] = []
    remaining = np.ones(n, dtype=bool)
    while remaining.any():
        cur = [int(i) for i in np.flatnonzero(remaining & (n_dom == 0))]
        if not cur:  # numerical safety: cannot happen with a strict partial order
            cur = [int(i) for i in np.flatnonzero(remaining)]
        fronts.append(cur)
        for p in cur:
            remaining[p] = False
            n_dom[dom[p]] -= 1
    return fronts


def crowding_distance(F: np.ndarray, front: list[int]) -> np.ndarray:
    d = np.zeros(len(front))
    if len(front) <= 2:
        d[:] = np.inf
        return d
    sub = F[front]
    for m in range(F.shape[1]):
        order = np.argsort(sub[:, m], kind="stable")
        rng_m = sub[order[-1], m] - sub[order[0], m]
        d[order[0]] = d[order[-1]] = np.inf
        if rng_m <= 0:
            continue
        for k in range(1, len(front) - 1):
            d[order[k]] += (sub[order[k + 1], m] - sub[order[k - 1], m]) / rng_m
    return d


def _jaccard(a: set[int], b: set[int]) -> float:
    u = len(a | b)
    return (len(a & b) / u) if u else 1.0


# ------------------------------------------------------------------------------------------------------- structural features
def _bfs_hops(indptr: np.ndarray, indices: np.ndarray, sources: list[int], n: int) -> np.ndarray:
    hops = np.full(n, np.inf)
    frontier = [int(s) for s in sources]
    for s in frontier:
        hops[s] = 0
    k = 0
    while frontier:
        k += 1
        nxt = []
        for s in frontier:
            for t in indices[indptr[s]:indptr[s + 1]]:
                if hops[t] == np.inf:
                    hops[t] = k
                    nxt.append(int(t))
        frontier = nxt
    return hops


def structural_features(problem: DiscoveryProblem, *, hops: int = 4, decay: float = 0.7) -> dict:
    """Public-graph features (no simulation): hop distances, direct stimulus input / readout output, and a stimulus->readout
    flow prior = sqrt(forward influence of the stimulus x backward attribution of the readout), rank-normalised over candidates."""
    C = problem.C.tocsr().astype(np.float64)
    n = problem.n
    stim = [int(s) for s in problem.stim_positions]
    ro = [int(r) for r in problem.readout_positions]
    csc = C.tocsc()
    d_fwd = _bfs_hops(csc.indptr, csc.indices, stim, n)          # successors of j = rows of column j
    d_bwd = _bfs_hops(C.indptr, C.indices, ro, n)                 # predecessors of i = columns of row i
    out_sum = np.asarray(C.sum(axis=0)).ravel()
    in_sum = np.asarray(C.sum(axis=1)).ravel()
    x = np.zeros(n); cur = np.zeros(n); cur[stim] = 1.0
    for k in range(hops):
        cur = C @ (cur / np.maximum(out_sum, 1e-12))
        cur[stim] = 0.0
        x += decay ** k * cur
    y = np.zeros(n); cur = np.zeros(n); cur[ro] = 1.0 / max(len(ro), 1)
    for k in range(hops):
        cur = C.T @ (cur / np.maximum(in_sum, 1e-12))
        cur[ro] = 0.0
        y += decay ** k * cur
    raw = np.sqrt(np.maximum(x, 0) * np.maximum(y, 0))
    cand = problem.candidate_positions()
    struct = np.zeros(n)
    pos = cand[raw[cand] > 0]
    if len(pos):
        order = np.argsort(raw[pos], kind="stable")
        ranks = np.empty(len(pos)); ranks[order] = np.arange(1, len(pos) + 1)
        struct[pos] = ranks / len(pos)
    stim_in = np.asarray(C[:, stim].sum(axis=1)).ravel()
    ro_out = np.asarray(C[ro, :].sum(axis=0)).ravel()
    return {"struct": struct, "d_fwd": d_fwd, "d_bwd": d_bwd, "stim_in": stim_in, "ro_out": ro_out, "flow_fwd": x, "flow_bwd": y}


# -------------------------------------------------------------------------------------------------------------------- search
class _Search:
    def __init__(self, problem: DiscoveryProblem, sim: BudgetedSimulator, seed: int, cfg: dict):
        self.p = problem
        self.sim = sim
        self.cfg = cfg
        self.seed = int(seed)
        self.rng = np.random.default_rng(self.seed)
        self.t_end = cfg.get("t_end")
        budget = sim.remaining
        self.budget0 = budget
        n_nom = int(cfg["n_nominal"]) if cfg.get("n_nominal") else (3 if budget >= 600 else 2)
        base = self.seed * 1000
        self.nominal_seeds = [base + i for i in range(n_nom)]
        self.confirm_seeds = [base + 500 + i for i in range(int(cfg["n_confirm_seeds"]))]
        self.essential_seeds = self.nominal_seeds[: max(1, int(cfg["n_essential_seeds"]))]
        self.intact_seeds = self.nominal_seeds[: max(1, int(cfg["n_intact_seeds"]))]
        mc = problem.model_cfg
        wf = float(cfg["widen_factor"])
        self.wide = {"tau_sd": mc.tau_sd * wf, "a_sd": mc.a_sd * wf, "theta_sd": mc.theta_sd * wf, "r_max_sd": mc.r_max_sd * wf}
        self.probes: list[tuple[str, int, dict, int | None]] = []
        for i in range(int(cfg["n_robust_final"])):
            j = i // 2
            if i % 2 == 0:
                self.probes.append((f"wide{j}", base + 100 + j, self.wide, None))
            else:
                self.probes.append((f"noise{j}", self.nominal_seeds[j % n_nom], {}, base + 200 + j))
        self.probes_ga = self.probes[: max(0, int(cfg["n_robust_ga"]))]
        self.reserve_conf = int(min(cfg["reserve_max"], max(cfg["reserve_min"], cfg["reserve_frac"] * budget)))
        self.screen_reserve = int(min(int(cfg["screen_max"]), float(cfg["screen_frac"]) * budget))
        self.reserve = self.reserve_conf + self.screen_reserve
        self.tail = 2 * len(self.essential_seeds) + 4
        """Calls kept for the very end: the gatekeeper union on the nominal seeds, leave-one-out children, group silencing."""
        self.confirm_extra = list(self.confirm_seeds)
        self.cand = [int(x) for x in problem.candidate_positions()]
        self.cand_set = set(self.cand)
        self.n = problem.n
        self.C = problem.C.tocsr()
        # optional prior {position: p(z_i = 1)} (e.g. transported from another network); absent = uniform (0.5 everywhere = no bias)
        self.prior = np.full(self.n, 0.5)
        self.has_prior = False
        raw_prior = cfg.get("prior")
        if isinstance(raw_prior, dict) and raw_prior:
            for k, v in raw_prior.items():
                try:
                    pos, val = int(k), float(v)
                except (TypeError, ValueError):
                    continue
                if 0 <= pos < self.n and np.isfinite(val):
                    self.prior[pos] = min(1.0, max(0.0, val))
                    self.has_prior = True
        self.feat = structural_features(problem, hops=int(cfg["flow_hops"]), decay=float(cfg["flow_decay"]))
        self.struct = self.feat["struct"]
        self.act = np.zeros(self.n)
        self.succ = np.zeros(self.n)
        self.fail = np.zeros(self.n)
        self.freq = np.zeros(self.n)
        self.freq_min = np.zeros(self.n)
        self.pending: list[Individual] = []
        self.recent_failing: list[Individual] = []
        self.archive: dict[tuple[int, ...], Individual] = {}
        self.population: list[Individual] = []
        self.pool: list[int] = []
        self.pool_arr = np.zeros(0, dtype=np.int64)
        self.intact: list[Outcome] = []
        self.all_ind: Individual | None = None
        self.ess: dict[int, bool | None] = {}
        self.exhausted = False
        self.calls_by_phase: dict[str, int] = {}
        self.op_stats: dict[str, list[int]] = {}
        self.trace: list[dict] = []
        self.n_intersection_fail = 0
        self.redundancy: dict[str, bool | None] = {}
        self.probed_taboos: set[frozenset] = set()
        self.stop_reason = ""
        self.generation = 0
        self._hash = getattr(sim, "_hash", None) or problem.network_hash()
        self._crit = dict(problem.criterion_spec)

    # ------------------------------------------------------------------------------------------------ simulator access
    def _fits(self, n_new: int) -> bool:
        return self.sim.remaining >= n_new

    def _log(self, msg: str) -> None:
        if self.cfg.get("verbose"):
            print(f"[evo_pareto {self.sim.calls}/{self.sim.max_calls} calls] {msg}", file=sys.stderr, flush=True)

    def _q_keep(self, members, seed: int, cfg_override: dict | None = None, noise_seed: int | None = None) -> SimQuery:
        """Keep-only query for a member set; a set that is every candidate but a few is expressed as silencing those few
        (identical dynamics), so that redundancy probes and full-network essentiality tests share the cache."""
        sd = float(self.cfg["weight_noise_sd"]) if noise_seed is not None else 0.0
        missing = len(self.cand) - len(members)
        if 0 < missing <= 8 and set(members) <= self.cand_set:
            iv = silence(self.cand_set - set(members), weight_noise_sd=sd, weight_noise_seed=noise_seed)
        else:
            iv = keep_only(self.p, members, weight_noise_sd=sd, weight_noise_seed=noise_seed)
        return SimQuery(iv, int(seed), t_end=self.t_end, cfg_override=dict(cfg_override or {}))

    def _q_silence(self, positions, seed: int) -> SimQuery:
        return SimQuery(silence(positions), int(seed), t_end=self.t_end)

    def run(self, queries: list[SimQuery], phase: str, *, floor: int = 0) -> list[Outcome | None]:
        """Run as many queries as the budget allows above ``floor`` (in order; cache hits are free). None = not run."""
        out: list[Outcome | None] = [None] * len(queries)
        if not queries:
            return out
        keys = [q.key(self._hash, self._crit) for q in queries]
        new_keys: set[str] = set()
        take = 0
        allowed = max(0, self.sim.remaining - floor)
        for k in keys:
            if k not in self.sim.cache and k not in new_keys:
                if len(new_keys) + 1 > allowed:
                    break
                new_keys.add(k)
            take += 1
        if take < len(queries) and floor == 0:
            self.exhausted = True
        if take == 0:
            return out
        before = self.sim.calls
        try:
            res = self.sim.run_many(queries[:take])
        except BudgetExhausted:
            self.exhausted = True
            return out
        self.calls_by_phase[phase] = self.calls_by_phase.get(phase, 0) + (self.sim.calls - before)
        for i, o in enumerate(res):
            out[i] = o
        return out

    # ------------------------------------------------------------------------------------------------- evaluation (racing)
    def evaluate(self, inds: list[Individual], *, phase: str = "ga", robust: bool = True, robust_cap: int | None = None, floor: int = 0) -> None:
        inds = [ind for ind in inds if ind.members not in self.archive]
        if not inds:
            return
        for ind in inds:
            ind.n_nominal_total = max(ind.n_nominal_total, len(self.nominal_seeds))
        # stage A: the first nominal seed for everybody
        s0 = self.nominal_seeds[0]
        outs = self.run([self._q_keep(ind.members, s0) for ind in inds], phase, floor=floor)
        alive = []
        for ind, o in zip(inds, outs):
            if o is None:
                continue
            ind.nominal[s0] = o
            self.archive[ind.members] = ind
            if o.passed:
                alive.append(ind)
        # stage B: the remaining nominal seeds for those that passed
        rest = self.nominal_seeds[1:]
        if alive and rest:
            qs, owners = [], []
            for ind in alive:
                for s in rest:
                    qs.append(self._q_keep(ind.members, s)); owners.append((ind, s))
            outs = self.run(qs, phase, floor=floor)
            for (ind, s), o in zip(owners, outs):
                if o is not None:
                    ind.nominal[s] = o
        # bookkeeping: dispensability evidence from prune-type operators
        for ind in inds:
            if ind.members in self.archive:
                self._book(ind)
        # stage C: robust probes for sufficient individuals near the smallest robust size
        if robust and self.probes_ga:
            s_star = self.smallest_robust_size()
            elig = [ind for ind in alive if ind.sufficient() and ind.size <= s_star + 1]
            elig.sort(key=lambda i: (i.size, -i.score_nominal(), i.members))
            if robust_cap is not None:
                elig = elig[:robust_cap]
            self.measure_robust(elig, self.probes_ga, phase, floor=floor)

    def measure_robust(self, inds: list[Individual], probes, phase: str, *, floor: int = 0) -> None:
        qs, owners = [], []
        for ind in inds:
            for key, seed, override, noise in probes:
                if key in ind.robust:
                    continue
                qs.append(self._q_keep(ind.members, seed, override, noise)); owners.append((ind, key))
        if not qs:
            return
        outs = self.run(qs, phase, floor=floor)
        for (ind, key), o in zip(owners, outs):
            if o is not None:
                ind.robust[key] = o

    def add_seeds(self, inds: list[Individual], seeds: list[int], phase: str, *, floor: int = 0) -> None:
        """Extra fresh nominal seeds (confirmation); they enter the nominal ensemble of those individuals."""
        qs, owners = [], []
        for ind in inds:
            for s in seeds:
                if s not in ind.nominal:
                    qs.append(self._q_keep(ind.members, s)); owners.append((ind, s))
        outs = self.run(qs, phase, floor=floor)
        for (ind, s), o in zip(owners, outs):
            if o is not None:
                ind.nominal[s] = o
        for ind in inds:
            ind.n_nominal_total = max(ind.n_nominal_total, len(set(self.nominal_seeds) | set(seeds)))

    def _book(self, ind: Individual) -> None:
        st = self.op_stats.setdefault(ind.op, [0, 0])
        st[0] += 1
        if ind.sufficient():
            st[1] += 1
        if ind.removed:
            rem = np.fromiter(ind.removed, dtype=np.int64)
            if ind.sufficient():
                self.succ[rem] += 1.0
            elif len(ind.nominal) and not next(iter(ind.nominal.values())).passed:
                self.fail[rem] += 1.0 / len(rem)
        if ind.op == "cross_intersection" and not ind.sufficient() and ind.nominal:
            self.n_intersection_fail += 1

    # ------------------------------------------------------------------------------------------------------ statistics
    def sufficient_sets(self) -> list[Individual]:
        return [ind for ind in self.archive.values() if ind.sufficient()]

    @staticmethod
    def _key(i: Individual):
        return (i.size, -(i.pass_robust() if i.pass_robust() is not None else 0.0), -i.score_nominal(), i.members)

    def smallest_sufficient(self) -> Individual | None:
        suff = self.sufficient_sets()
        return min(suff, key=self._key) if suff else None

    def smallest_robust_size(self) -> float:
        sizes = [ind.size for ind in self.archive.values() if ind.sufficient() and ind.pass_robust() == 1.0]
        return min(sizes) if sizes else math.inf

    def minimal_sufficient(self) -> list[Individual]:
        """Sufficient sets with no sufficient proper subset in the archive (the Rashomon set of minimal mechanisms found so far)."""
        suff = sorted(self.sufficient_sets(), key=lambda i: (i.size, i.members))
        minimal: list[Individual] = []
        sets = [set(i.members) for i in suff]
        for k, ind in enumerate(suff):
            s = sets[k]
            if any(sets[j] < s for j in range(k) if suff[j].size < ind.size):
                continue
            minimal.append(ind)
        return minimal

    @staticmethod
    def _weight(ind: Individual, s_min: int) -> float:
        pr = ind.pass_robust()
        return 2.0 ** (-(ind.size - s_min)) * (0.25 + 0.75 * (0.5 if pr is None else pr))

    def update_frequency(self) -> None:
        """Size- and robustness-weighted inclusion frequencies: over minimal sufficient sets (reporting: members of non-minimal
        supersets are removable and carry no evidence) and over all sufficient sets (a broader signal for the operators)."""
        suff = self.sufficient_sets()
        self.freq[:] = 0.0
        self.freq_min = np.zeros(self.n)
        if not suff:
            return
        s_min = min(i.size for i in suff)
        total = 0.0
        for ind in suff:
            w = self._weight(ind, s_min)
            self.freq[list(ind.members)] += w
            total += w
        if total > 0:
            self.freq /= total
        minimal = self.minimal_sufficient()
        total = 0.0
        for ind in minimal:
            w = self._weight(ind, s_min)
            self.freq_min[list(ind.members)] += w
            total += w
        if total > 0:
            self.freq_min /= total

    # ------------------------------------------------------------------------------------------------------ operators
    def keep_pref(self) -> np.ndarray:
        """Per-node preference to keep/add: structure, intact activity, inclusion frequencies and the optional prior (+-0.2)."""
        kp = 0.1 + 0.3 * self.struct + 0.2 * self.act + 0.2 * self.freq + 0.2 * self.freq_min + 0.4 * (self.prior - 0.5)
        return np.maximum(kp, 0.02)

    def remove_weights(self, members: np.ndarray) -> np.ndarray:
        kp = self.keep_pref()[members]
        disp = (1.0 + self.succ[members]) / (1.0 + self.fail[members])
        w = np.maximum(1.1 - kp, 0.02) * disp
        return np.maximum(w, 1e-9)

    def adjacent(self, nodes: set[int]) -> np.ndarray:
        adj = np.zeros(self.n, dtype=bool)
        if nodes:
            cur = np.fromiter(sorted(nodes), dtype=np.int64)
            adj |= np.asarray(self.C[:, cur].sum(axis=1)).ravel() > 0   # successors
            adj |= np.asarray(self.C[cur, :].sum(axis=0)).ravel() > 0   # predecessors
        return adj

    def add_weights(self, current: set[int], taboo: frozenset, candidates: np.ndarray) -> np.ndarray:
        if len(candidates) == 0:
            return np.zeros(0)
        kp = self.keep_pref()[candidates]
        adj = self.adjacent(current)
        w = kp * (1.0 + 2.0 * adj[candidates])
        w[[i for i, c in enumerate(candidates) if int(c) in taboo or int(c) in current]] = 0.0
        return np.maximum(w, 0.0)

    def _choose(self, items: np.ndarray, k: int, w: np.ndarray) -> list[int]:
        """Weighted sampling without replacement (at most as many as there are positive weights)."""
        k = int(min(k, len(items), int((w > 0).sum())))
        if k <= 0:
            return []
        return [int(x) for x in self.rng.choice(items, size=k, replace=False, p=w / w.sum())]

    def _prune_k(self, m: int) -> int:
        if m <= 1:
            return 0
        if m <= 6:
            return 1 if (m < 4 or self.rng.random() < 0.7) else 2
        r = self.rng.uniform(0.08, 0.35) if m <= 30 else self.rng.uniform(0.1, 0.5)
        return int(min(m - 1, max(1, round(m * r))))

    def op_prune(self, parent: Individual, k: int | None = None) -> Individual | None:
        mem = np.fromiter(parent.members, dtype=np.int64)
        k = self._prune_k(len(mem)) if k is None else k
        if k <= 0:
            return None
        victims = self._choose(mem, k, self.remove_weights(mem))
        child = tuple(sorted(set(parent.members) - set(victims)))
        return Individual(child, op="prune", taboo=parent.taboo, parent_pass=parent.members, removed=tuple(sorted(victims)))

    def op_loo(self, parent: Individual) -> Individual | None:
        """Single removal of a member whose removal has not been tested yet (systematic minimality evidence)."""
        untested = [m for m in parent.members if tuple(sorted(set(parent.members) - {m})) not in self.archive]
        if not untested:
            return None
        mem = np.fromiter(untested, dtype=np.int64)
        victim = self._choose(mem, 1, self.remove_weights(mem))
        if not victim:
            return None
        child = tuple(sorted(set(parent.members) - set(victim)))
        return Individual(child, op="loo", taboo=parent.taboo, parent_pass=parent.members, removed=tuple(victim))

    def op_silent_prune(self, parent: Individual) -> Individual | None:
        active = parent.active_union()
        if not active:
            return None
        child = tuple(sorted(set(parent.members) & active))
        if not child or child == parent.members:
            return None
        return Individual(child, op="silent_prune", taboo=parent.taboo, parent_pass=parent.members,
                          removed=tuple(sorted(set(parent.members) - set(child))))

    def op_repair(self, parent: Individual) -> Individual | None:
        if parent.parent_pass is None:
            return None
        missing = np.fromiter(sorted((set(parent.parent_pass) - set(parent.members)) - parent.taboo), dtype=np.int64)
        if len(missing) == 0:
            return None
        k = max(1, len(missing) // 2)
        add = self._choose(missing, k, self.keep_pref()[missing])
        child = tuple(sorted(set(parent.members) | set(add)))
        return Individual(child, op="repair", taboo=parent.taboo, parent_pass=parent.parent_pass)

    def op_add(self, parent: Individual, k: int | None = None) -> Individual | None:
        cur = set(parent.members)
        w = self.add_weights(cur, parent.taboo, self.pool_arr)
        if w.sum() <= 0:
            return None
        if k is None:
            k = 1 if self.rng.random() < 0.6 else int(self.rng.integers(2, 5))
        add = self._choose(self.pool_arr, k, w)
        if not add:
            return None
        child = tuple(sorted(cur | set(add)))
        return Individual(child, op="add", taboo=parent.taboo, parent_pass=parent.parent_pass)

    def op_swap(self, parent: Individual) -> Individual | None:
        mem = np.fromiter(parent.members, dtype=np.int64)
        if len(mem) == 0:
            return None
        victim = self._choose(mem, 1, self.remove_weights(mem))
        cur = set(parent.members) - set(victim)
        w = self.add_weights(cur, parent.taboo | frozenset(victim), self.pool_arr)
        if w.sum() <= 0:
            return None
        add = self._choose(self.pool_arr, 1, w)
        child = tuple(sorted(cur | set(add)))
        return Individual(child, op="swap", taboo=parent.taboo, parent_pass=parent.members if parent.sufficient() else parent.parent_pass)

    def op_cross(self, a: Individual, b: Individual) -> Individual | None:
        sa, sb = set(a.members), set(b.members)
        if sa == sb:
            return None
        taboo = a.taboo | b.taboo
        if a.sufficient() and b.sufficient() and self.rng.random() < 0.6:
            child = tuple(sorted(sa & sb))
            op = "cross_intersection"
            pp = a.members if a.size <= b.size else b.members
        else:
            diff = np.fromiter(sorted(sa ^ sb), dtype=np.int64)
            take = diff[self.rng.random(len(diff)) < 0.5]
            child = tuple(sorted((sa & sb) | set(int(x) for x in take)))
            op = "cross_uniform"
            pp = None
            for par in (a, b):
                if par.sufficient() and set(child) <= set(par.members):
                    pp = par.members
        if not child:
            return None
        if set(child) & taboo:
            taboo = frozenset()
        return Individual(child, op=op, taboo=taboo, parent_pass=pp)

    # ------------------------------------------------------------------------------------------------------ population
    def _rank(self, inds: list[Individual]) -> tuple[list[list[int]], np.ndarray, np.ndarray]:
        F = np.array([ind.objectives() for ind in inds], dtype=np.float64)
        fronts = non_dominated_sort(F)
        rank = np.zeros(len(inds), dtype=int)
        crowd = np.zeros(len(inds))
        for r, fr in enumerate(fronts):
            rank[fr] = r
            crowd[fr] = crowding_distance(F, fr)
        return fronts, rank, crowd

    def select(self, inds: list[Individual], mu: int) -> list[Individual]:
        if len(inds) <= mu:
            return list(inds)
        fronts, rank, crowd = self._rank(inds)
        chosen: list[int] = []
        for fr in fronts:
            if len(chosen) + len(fr) <= mu:
                chosen.extend(fr)
                continue
            need = mu - len(chosen)
            # last front: crowding distance first, then novelty in member space (min Jaccard distance to the chosen)
            chosen_sets = [set(inds[i].members) for i in chosen]

            def novelty(i: int, chosen_sets=chosen_sets) -> float:
                s = set(inds[i].members)
                return min((1.0 - _jaccard(s, c) for c in chosen_sets), default=1.0)

            order = sorted(fr, key=lambda i: (-crowd[i], -novelty(i), i))
            chosen.extend(order[:need])
            break
        return [inds[i] for i in chosen]

    def tournament(self, inds: list[Individual], rank: np.ndarray, crowd: np.ndarray) -> Individual:
        i, j = self.rng.integers(0, len(inds), size=2)
        if (rank[i], -crowd[i]) <= (rank[j], -crowd[j]):
            return inds[i]
        return inds[j]

    def make_offspring(self, lam: int, pending: list[Individual]) -> list[Individual]:
        pop = self.population
        fronts, rank, crowd = self._rank(pop)
        offspring: list[Individual] = []
        seen: set[tuple[int, ...]] = set(self.archive)
        for ind in pending:
            if ind.members not in seen and ind.members:
                offspring.append(ind); seen.add(ind.members)
        repairable = [f for f in self.recent_failing if f.parent_pass is not None]
        attempts = 0
        while len(offspring) < lam and attempts < 40 * lam:
            attempts += 1
            u = self.rng.random()
            child = None
            if repairable and self.rng.random() < 0.3:
                a = repairable[int(self.rng.integers(0, len(repairable)))]
                child = self.op_repair(a) if self.rng.random() < 0.7 else self.op_add(a)
            else:
                a = self.tournament(pop, rank, crowd)
                if a.sufficient():
                    if u < 0.5:
                        child = self.op_prune(a)
                    elif u < 0.7 and a.size <= 16:
                        child = self.op_loo(a)
                    elif u < 0.8:
                        child = self.op_swap(a)
                    else:
                        child = self.op_cross(a, self.tournament(pop, rank, crowd))
                else:
                    if u < 0.6 and a.parent_pass is not None:
                        child = self.op_repair(a)
                    elif u < 0.85:
                        child = self.op_add(a)
                    else:
                        child = self.op_cross(a, self.tournament(pop, rank, crowd))
            if child is None or not child.members or child.members in seen:
                continue
            if set(child.members) & child.taboo:
                continue
            child.born = self.generation + 1
            offspring.append(child); seen.add(child.members)
        return offspring

    # ------------------------------------------------------------------------------------------------------ phases
    def prescreen(self) -> None:
        outs = self.run([SimQuery(None, int(s), t_end=self.t_end) for s in self.intact_seeds], "intact")
        self.intact = [o for o in outs if o is not None]
        act = np.zeros(self.n)
        for o in self.intact:
            act[np.asarray(o.active_positions, dtype=np.int64)] += 1.0 / max(len(self.intact), 1)
        self.act = act
        active = [i for i in self.cand if act[i] > 0]
        order = sorted(self.cand, key=lambda i: (-self.struct[i], i))
        k_struct = max(int(self.cfg["pool_struct_min"]), int(round(float(self.cfg["pool_struct_frac"]) * len(active))))
        extra = [i for i in order if act[i] == 0 and self.struct[i] > 0][:k_struct]
        pool = sorted(set(active) | set(extra))
        if self.has_prior:  # nodes the prior believes in join the pool even when silent/unstructured (the simulator still decides)
            favoured = sorted((i for i in self.cand if self.prior[i] > 0.5), key=lambda i: (-self.prior[i], i))[: max(k_struct, 16)]
            pool = sorted(set(pool) | set(favoured))
        pool_max = self.cfg.get("pool_max")
        if pool_max and len(pool) > int(pool_max):
            pool = sorted(sorted(pool, key=lambda i: (-(0.5 * self.act[i] + 0.5 * self.struct[i]), i))[: int(pool_max)])
        if not pool:  # nothing active and no structure: fall back to the strongest stimulus targets by count
            pool = sorted(self.cand, key=lambda i: (-self.feat["stim_in"][i], i))[: max(8, k_struct)]
        self.pool = pool
        self.pool_arr = np.fromiter(pool, dtype=np.int64)
        # the intact network = keep-only of every candidate: a sufficient superset that cost nothing extra
        if self.intact:
            all_ind = Individual(tuple(self.cand), op="intact", n_nominal_total=len(self.nominal_seeds))
            for s, o in zip(self.intact_seeds, self.intact):
                all_ind.nominal[s] = o
            self.all_ind = all_ind
            self.archive[all_ind.members] = all_ind
            if len(self.intact) < len(self.nominal_seeds) and all(o.passed for o in self.intact):
                # complete its nominal ensemble (intact queries) so that it is comparable to the others
                todo = [s for s in self.nominal_seeds if s not in all_ind.nominal]
                outs = self.run([SimQuery(None, int(s), t_end=self.t_end) for s in todo], "intact")
                for s, o in zip(todo, outs):
                    if o is not None:
                        all_ind.nominal[s] = o

    def initial_population(self) -> None:
        pool = self.pool
        order = sorted(pool, key=lambda i: (-self.struct[i], i))
        inds = [Individual(tuple(pool), op="pool")]
        for k in (3, 5, 8, 12, 20, 32):
            if k < len(order):
                inds.append(Individual(tuple(sorted(order[:k])), op="struct_top"))
        direct = [i for i in order if self.feat["stim_in"][i] > 0]
        drivers = [i for i in order if self.feat["ro_out"][i] > 0]
        if direct:
            inds.append(Individual(tuple(sorted(direct)), op="stim_targets"))
        if drivers and direct:
            inds.append(Individual(tuple(sorted(set(direct) | set(drivers))), op="stim_targets+ro_drivers"))
        for q in (0.75, 0.5, 0.5, 0.25):
            m = self.rng.random(len(pool)) < q
            sel = tuple(int(x) for x in np.fromiter(pool, dtype=np.int64)[m])
            if sel:
                inds.append(Individual(sel, op="random_subset"))
        if self.has_prior:  # prior-guided seeds: the favoured nodes (prior > 0.5, strongest first), and a Bernoulli(prior) draw
            pa = np.fromiter(pool, dtype=np.int64)
            fav = sorted((int(x) for x in pa if self.prior[x] > 0.5), key=lambda i: (-self.prior[i], i))[:64]
            if fav:
                inds.append(Individual(tuple(sorted(fav)), op="prior_top"))
            m = self.rng.random(len(pa)) < self.prior[pa]
            sel = tuple(int(x) for x in pa[m])
            if sel:
                inds.append(Individual(sel, op="prior_sample"))
        inds.append(Individual((), op="null"))  # the null mechanism: does the readout meet the criterion with no interneuron?
        uniq: dict[tuple[int, ...], Individual] = {}
        for ind in inds:
            if (ind.members or ind.op == "null") and ind.members not in uniq and ind.members not in self.archive:
                if self.all_ind is not None and ind.op != "null":
                    ind.parent_pass = self.all_ind.members
                uniq[ind.members] = ind
        inds = list(uniq.values())
        self.evaluate(inds, phase="init", robust_cap=3, floor=self.reserve)
        pool_ind = self.archive.get(tuple(pool))
        if pool_ind is not None and not pool_ind.sufficient() and self.all_ind is not None and self.all_ind.sufficient():
            # the active/structural pool is not sufficient although the intact network is: widen the pool to every candidate;
            # the repair operator (delta debugging against the intact superset) locates the missing members
            self.pool = list(self.cand)
            self.pool_arr = np.fromiter(self.pool, dtype=np.int64)
        self.pending = [c for c in (self.op_silent_prune(i) for i in inds if i.sufficient()) if c is not None]
        pop = [ind for ind in inds if ind.members in self.archive]
        if self.all_ind is not None:
            pop.append(self.all_ind)
        self.population = pop
        self.recent_failing = [ind for ind in pop if not ind.sufficient()]
        self.update_frequency()
        s = self.smallest_sufficient()
        self._log(f"pool {len(self.pool)} (active in intact {int((self.act[self.cand] > 0).sum())}); initial population {len(pop)}, "
                  f"smallest sufficient {None if s is None else s.size}")

    def evolve(self) -> None:
        cfg = self.cfg
        mu = int(cfg["mu"])
        ga_budget = max(0, self.sim.remaining - self.reserve)
        lam = int(cfg["lam"]) if cfg.get("lam") else int(min(mu, max(6, round(ga_budget / (2.6 * 16)))))
        patience = int(cfg["patience"])
        state, stall, level = None, 0, 0
        pending = list(self.pending)
        while self.generation < int(cfg["max_generations"]):
            if self.exhausted or self.sim.remaining <= self.reserve:
                self.stop_reason = "budget reserve reached"
                break
            offspring = self.make_offspring(lam, pending)
            pending = []
            if not offspring:
                self.stop_reason = "no new offspring"
                break
            self.evaluate(offspring, phase="ga", robust_cap=max(2, lam // 2), floor=self.reserve)
            evaluated = [c for c in offspring if c.members in self.archive]
            for c in evaluated:
                if c.sufficient():
                    sp_ = self.op_silent_prune(c)
                    if sp_ is not None and sp_.members not in self.archive:
                        pending.append(sp_)
            self.recent_failing = [c for c in evaluated if not c.sufficient()]
            self.population = self.select(self.population + evaluated, mu)
            self.update_frequency()
            self.generation += 1
            s = self.smallest_sufficient()
            suff = self.sufficient_sets()
            # progress = the small end of the front moved: smaller sufficient set, smaller fully robust set, or a new sufficient
            # set of the smallest size (an alternative); growth of the front at larger sizes is not progress
            n_min = sum(1 for i in suff if s is not None and i.size == s.size)
            new_state = (None if s is None else s.size, self.smallest_robust_size(), n_min)
            stall = 0 if new_state != state else stall + 1
            state = new_state
            self.trace.append({"generation": self.generation, "calls": self.sim.calls, "smallest_sufficient": new_state[0],
                               "smallest_robust": None if new_state[1] == math.inf else new_state[1], "n_sufficient": len(suff), "stall": stall})
            self._log(f"generation {self.generation}: smallest sufficient {new_state[0]}, smallest fully robust "
                      f"{None if new_state[1] == math.inf else new_state[1]}, sufficient sets {len(suff)}, stall {stall}")
            if stall >= patience:
                if s is not None and level < int(cfg["redundancy_levels"]):
                    level += 1
                    added = self.redundancy_probes(level)
                    if added:
                        self.population = self.select(self.population + added, mu)
                        stall = 0
                        continue
                self.stop_reason = "front stalled"
                break
        else:
            self.stop_reason = "generation cap"

    def redundancy_probes(self, level: int) -> list[Individual]:
        """Level 1: for each member m of the smallest sufficient set, the largest sufficient set minus m (= silencing m) with m
        tabooed; level 2+: minus the union of all compact minimal sufficient sets found so far (another implementation?)."""
        suff = self.sufficient_sets()
        s = self.smallest_sufficient()
        if s is None:
            return []
        big = max(suff, key=lambda i: (i.size, i.members))
        if level == 1:
            taboos = [frozenset({m}) for m in s.members]
        else:
            cap = max(2 * s.size, s.size + 3)
            union = frozenset(m for ind in self.minimal_sufficient() if ind.size <= cap for m in ind.members)
            taboos = [union] if union and union not in self.probed_taboos else []
        taboos = [t for t in taboos if t not in self.probed_taboos and set(big.members) - t]
        need = len(taboos) * len(self.nominal_seeds)
        if not taboos or self.sim.remaining - self.reserve < need:
            return []
        probes = []
        for t in taboos:
            self.probed_taboos.add(t)
            child = tuple(sorted(set(big.members) - t))
            if child and child not in self.archive:
                probes.append(Individual(child, op="exclude", taboo=t, born=self.generation))
        self._log(f"redundancy probes level {level}: {len(probes)} exclusion set(s)")
        self.evaluate(probes, phase="redundancy", robust=False, floor=self.reserve)
        added = []
        for pr in probes:
            label = ",".join(str(m) for m in sorted(pr.taboo))
            if pr.members in self.archive:
                self.redundancy[label] = pr.sufficient()
                if pr.sufficient():
                    added.append(pr)
                    sp_ = self.op_silent_prune(pr)
                    if sp_ is not None:
                        added.append(sp_)
            else:
                self.redundancy[label] = None
        for a in added:
            if a.members not in self.archive:
                self.evaluate([a], phase="redundancy", robust=False, floor=self.reserve)
        return [a for a in added if a.members in self.archive]

    # ------------------------------------------------------------------------------------------------------ final stage
    def confirm(self) -> list[Individual]:
        """Extra fresh seeds and the full robust ensemble for the smallest COMPACT minimal sufficient sets (size <= max(2 s_min,
        s_min + 3)) + the most robust small superset of the smallest one (a 'supported' variant the knee may prefer when the
        minimal set is fragile). The intact network itself is never a candidate."""
        everything = tuple(self.cand)
        suff = [i for i in self.sufficient_sets() if i.members != everything]
        if not suff:
            return []
        minimal = sorted((i for i in self.minimal_sufficient() if i.members != everything), key=self._key) or sorted(suff, key=self._key)
        cap = max(2 * minimal[0].size, minimal[0].size + 3)
        cands = [i for i in minimal if i.size <= cap][: int(self.cfg["n_confirm"])]
        base = cands[0]
        sup = [i for i in suff if set(base.members) < set(i.members) and i.size <= base.size + 2 and i.pass_robust() is not None
               and i.pass_robust() > (base.pass_robust() or 0.0)]
        if sup:
            cands.append(min(sup, key=lambda i: (-(i.pass_robust() or 0.0), i.size, -i.score_nominal(), i.members)))
        extra = list(self.confirm_seeds)
        if self.sim.remaining - self.screen_reserve > 4 * len(cands) * (len(extra) + len(self.probes)) + 8:
            extra = extra + [self.seed * 1000 + 600 + i for i in range(2)]
        self.confirm_extra = extra
        floor = self.screen_reserve + self.tail
        self.add_seeds(cands, extra, "confirm", floor=floor)
        self.measure_robust(cands, self.probes, "confirm", floor=floor)
        return cands

    def necessity_screen(self, cands: list[Individual], floor: int) -> dict:
        """Single-neuron silencing in the full network for at most ``screen_max`` neurons: the candidates' members (smallest
        candidate first), then pool neighbours of those members (adjacent first, then keep preference), as the budget allows above
        ``floor``. A neuron is essential when the function fails on the first seed and again on the second (one passing seed
        settles 'not essential'; a first-seed failure the budget cannot confirm counts as essential)."""
        cap = int(self.cfg["screen_max"])
        members: list[int] = []
        for c in sorted(cands, key=lambda c: (c.size, c.members)):
            for m in c.members:
                if m not in members:
                    members.append(m)
        members = members[:cap]
        mset = set(members)
        adj = self.adjacent(mset)
        kp = self.keep_pref()
        extra = sorted((i for i in self.pool if i not in mset and i in self.cand_set), key=lambda i: (-int(adj[i]), -kp[i], i))
        order = [p for p in members + extra[: max(0, cap - len(members))] if p not in self.ess]
        s0 = self.essential_seeds[0]
        outs = self.run([self._q_silence([p], s0) for p in order], "screen", floor=floor)
        first: dict[int, Outcome] = {p: o for p, o in zip(order, outs) if o is not None}
        for p in order:
            if p not in first:
                self.ess.setdefault(p, None)
            elif first[p].passed:
                self.ess[p] = False
        failing = [p for p, o in first.items() if not o.passed]
        if len(self.essential_seeds) > 1 and failing:
            outs2 = self.run([self._q_silence([p], self.essential_seeds[1]) for p in failing], "screen", floor=floor)
            for p, o in zip(failing, outs2):
                self.ess[p] = True if o is None or not o.passed else False
        else:
            for p in failing:
                self.ess[p] = True
        return {"n_screened": len(first), "n_ordered": len(order), "essential": sorted(p for p in order if self.ess.get(p) is True)}

    def relevance(self, members) -> float:
        """In-situ relevance: fraction of members whose single silencing destroys the function (unknown counts 0.5)."""
        vals = [1.0 if self.ess.get(m) is True else 0.0 if self.ess.get(m) is False else 0.5 for m in members]
        return float(np.mean(vals)) if vals else 0.0

    def phi(self, ind: Individual) -> float:
        pn = ind.pass_nominal()
        pr = ind.pass_robust()
        return 0.5 * pn + 0.2 * (0.5 * pn if pr is None else pr) + 0.3 * self.relevance(ind.members)

    def knee(self, cands: list[Individual]) -> Individual | None:
        """Closest candidate to the ideal (phi maximal, size minimal) with an absolute per-member size cost; candidates that fail
        more than a quarter of their nominal seeds are excluded unless nothing better exists."""
        if not cands:
            return None
        pn = [c.pass_nominal() for c in cands]
        thr = 0.75 if max(pn) >= 0.75 else max(pn)
        ok = [c for c, p in zip(cands, pn) if p >= thr]
        phis = np.array([self.phi(c) for c in ok]); sizes = np.array([c.size for c in ok], dtype=float)
        dist = np.sqrt(((phis.max() - phis) / 0.25) ** 2 + (SIZE_COST * (sizes - sizes.min())) ** 2)
        order = sorted(range(len(ok)), key=lambda i: (round(float(dist[i]), 9), ok[i].size, -phis[i], ok[i].members))
        return ok[order[0]]

    def reduce(self, core: Individual, floor: int) -> tuple[Individual, list[int]]:
        """Evidence-based leave-one-out reduction: a member is dropped only when the reduced set (evaluated on the same seeds and
        robust probes) wins the knee comparison against the current core. Non-essential, rarely included members go first."""
        sizes = [core.size]
        cur = core
        while cur.size > 1 and self.sim.remaining > floor:
            order = sorted(cur.members, key=lambda m: (self.ess.get(m) is True, self.freq_min[m], self.struct[m], m))
            improved = False
            for m in order:
                if self.sim.remaining <= floor:
                    break
                child_members = tuple(sorted(set(cur.members) - {m}))
                child = self.archive.get(child_members)
                if child is None:
                    child = Individual(child_members, op="loo_final", taboo=cur.taboo, parent_pass=cur.members, removed=(m,), born=self.generation)
                    self.evaluate([child], phase="reduce", robust=False, floor=floor)
                    child = self.archive.get(child_members)
                if child is None or not child.sufficient():
                    continue
                self.add_seeds([child], self.confirm_extra, "reduce", floor=floor)
                self.measure_robust([child], self.probes, "reduce", floor=floor)
                if self.knee([cur, child]) is child:
                    cur = child
                    sizes.append(cur.size)
                    improved = True
                    break
            if not improved:
                break
        return cur, sizes

    def integrate_gatekeepers(self, core: Individual, floor: int) -> tuple[Individual, list[int], bool | None]:
        """Essential neurons outside the core (single silencing destroys the function in situ although keep-only never needed
        them) join the core when the union is still sufficient on the nominal seeds."""
        gate = sorted(p for p, v in self.ess.items() if v is True and p not in set(core.members) and p in self.cand_set)
        if not gate:
            return core, [], None
        union_members = tuple(sorted(set(core.members) | set(gate)))
        union = self.archive.get(union_members)
        if union is None:
            union = Individual(union_members, op="gatekeepers", parent_pass=None, born=self.generation)
            self.evaluate([union], phase="gatekeepers", robust=False, floor=floor)
            union = self.archive.get(union_members)
        if union is None:
            return core, gate, None
        if union.sufficient():
            self.add_seeds([union], self.confirm_extra, "gatekeepers", floor=floor)
            self.measure_robust([union], self.probes, "gatekeepers", floor=floor)
            return union, gate, True
        return core, gate, False

    def ensure_essential(self, members, floor: int) -> None:
        for p in members:
            if self.ess.get(p) is not None:
                continue
            outs = self.run([self._q_silence([p], s) for s in self.essential_seeds], "essential", floor=floor)
            got = [o for o in outs if o is not None]
            self.ess[p] = bool(np.mean([o.passed for o in got]) < 0.5) if got else None

    def ensure_loo(self, core: Individual, floor: int) -> None:
        """Evaluate every leave-one-out child of the final core that is not in the archive yet (the empty set for a single member)."""
        kids = []
        for m in core.members:
            cm = tuple(sorted(set(core.members) - {m}))
            if cm not in self.archive:
                kids.append(Individual(cm, op="loo_final", taboo=core.taboo, parent_pass=core.members, removed=(m,), born=self.generation))
        self.evaluate(kids, phase="loo", robust=False, floor=floor)

    def finalize(self) -> dict:
        out: dict = {"core": None, "confirmed": [], "screen": {}, "reduction": [], "knee0": None, "knee": None, "gatekeepers": [],
                     "gatekeepers_integrated": None, "group": None}
        self._log(f"search stopped ({self.stop_reason}); confirmation")
        cands = self.confirm()
        out["confirmed"] = cands
        if not cands:
            return out
        # 1. cheap first: leave-one-out reduction of the knee (keep-only calls) before the expensive full-network screen
        knee0 = self.knee(cands)
        out["knee0"] = knee0
        red0, sizes = self.reduce(knee0, floor=self.screen_reserve + self.tail)
        out["reduction"].append(sizes)
        pool_c = [red0] + [c for c in cands if c.members not in (knee0.members, red0.members)]
        # 2. in-situ necessity (single silencing in the full network), then the knee with in-situ relevance
        self._log(f"reduced knee {knee0.size} -> {red0.size}; necessity screen")
        out["screen"] = self.necessity_screen(pool_c, floor=self.tail)
        knee = self.knee(pool_c)
        if knee is not red0:
            knee, sizes = self.reduce(knee, floor=self.tail)
            out["reduction"].append(sizes)
        out["knee"] = knee
        # 3. gatekeepers, leave-one-out certificate of the final core, essentiality of new members, group silencing
        core, gate, integrated = self.integrate_gatekeepers(knee, floor=1)
        out["gatekeepers"], out["gatekeepers_integrated"] = gate, integrated
        self.ensure_loo(core, floor=1)
        self.ensure_essential(core.members, floor=1)
        if core.size > 1:
            outs = self.run([self._q_silence(list(core.members), self.essential_seeds[0])], "essential")
            out["group"] = None if outs[0] is None else bool(outs[0].passed)
        out["core"] = core
        self._log(f"core of {core.size}: {list(core.members)}")
        return out

    # ------------------------------------------------------------------------------------------------------ reporting
    def alternatives(self, core: tuple[int, ...]) -> list[Individual]:
        """Minimal sufficient sets that are neither the core nor supersets of it, compact enough to be a mechanism claim."""
        core_set = set(core)
        cap = max(2 * len(core), len(core) + 3)
        out = [ind for ind in self.minimal_sufficient() if not core_set <= set(ind.members) and ind.size <= cap]
        out.sort(key=self._key)
        return out

    def inclusion_probability(self, core: tuple[int, ...], loo: dict[int, bool | None]) -> dict[int, float]:
        """p(z_i = 1): weighted frequency across minimal sufficient sets (0.9) and across all sufficient sets (0.1), adjusted by the
        core's leave-one-out evidence (necessary within the core -> >= 0.9; removable -> <= 0.6) and by in-situ essentiality."""
        assessed: set[int] = set(self.pool) | set(core) | set(self.ess)
        for ind in self.archive.values():
            if ind.members != tuple(self.cand) and ind.size <= max(len(self.pool), 64):
                assessed.update(ind.members)
        probs: dict[int, float] = {}
        for i in sorted(assessed & self.cand_set):
            p = 0.9 * float(self.freq_min[i]) + 0.1 * float(self.freq[i])
            if i in core:
                nec = loo.get(i)
                if nec is True:
                    p = max(p, 0.9)
                elif nec is False:
                    p = min(max(p, 0.35), 0.6)
                else:
                    p = max(p, 0.75)
                if self.ess.get(i) is True:
                    p = max(p, 0.85)
            elif self.ess.get(i) is True:
                p = max(p, 0.6)
            probs[i] = float(min(0.99, max(0.01, p)))
        return probs

    def roles(self, core: list[int], loo: dict[int, bool | None], alts: list[Individual]) -> tuple[dict, list[int], str]:
        crit = str(self.p.criterion_spec.get("type", "rhythm"))
        if not core:
            return {}, [], "no sufficient mechanism found"
        idx = np.fromiter(core, dtype=np.int64)
        sub = self.C[idx][:, idx].tocsr()
        n_comp, labels = connected_components(sub, directed=True, connection="strong")
        comp_size = np.bincount(labels, minlength=n_comp)
        self_loop = np.asarray(sub.diagonal()).ravel() > 0
        on_cycle = {int(p): bool(comp_size[labels[k]] > 1 or self_loop[k]) for k, p in enumerate(core)}
        big = int(np.argmax(comp_size)) if n_comp else -1
        loop = sorted(int(p) for k, p in enumerate(core) if (labels[k] == big and comp_size[big] > 1) or self_loop[k])
        ro = self.p.readout_positions
        stim = list(self.p.stim_positions)
        drives_ro = {int(p): bool(self.C[ro, p].sum() > 0) for p in core}
        stim_in = {int(p): bool(self.C[p, stim].sum() > 0) for p in core}
        roles: dict[int, tuple[str, float]] = {}
        n_exc = n_inh = 0
        for p in core:
            s = int(self.p.signs[p])
            removable = loo.get(p) is False
            essential = self.ess.get(p) is True
            backup = removable and self.ess.get(p) is False and alts and any(p not in set(a.members) for a in alts)
            if s == 0:
                roles[p] = ("unknown", 0.5)
                continue
            if s > 0:
                n_exc += 1
                if backup:
                    role, q = "redundant_backup", 0.55
                elif on_cycle[p] and (drives_ro[p] or stim_in[p]):
                    if crit == "rhythm":
                        role, q = "recurrent_excitatory_core", 0.7
                    elif crit in ("persistence", "ramp"):
                        role, q = "state_memory", 0.7
                    else:
                        role, q = ("output_driver", 0.65) if drives_ro[p] else ("input_relay", 0.55)
                elif on_cycle[p]:
                    role, q = ("state_memory", 0.6) if crit in ("persistence", "ramp") else ("input_relay", 0.6)
                elif drives_ro[p]:
                    role, q = "output_driver", 0.65
                elif stim_in[p]:
                    role, q = "input_relay", 0.6
                else:
                    role, q = ("modulatory_supporting", 0.5) if removable and not essential else ("input_relay", 0.5)
            else:
                n_inh += 1
                if backup:
                    role, q = "redundant_backup", 0.55
                elif crit == "rhythm":
                    role, q = ("inhibitory_feedback", 0.7) if on_cycle[p] else ("gain_control", 0.55)
                elif crit == "selectivity":
                    role, q = "lateral_inhibition", 0.6
                else:
                    role, q = "gain_control", 0.65
            if removable and not essential and role not in ("redundant_backup", "modulatory_supporting"):
                q = min(q, 0.5)
            roles[p] = (role, float(q))
        parts = [f"{n_exc}E/{n_inh}I core of {len(core)}"]
        if loop:
            parts.append(f"cycle through {len(loop)} member(s)" + (" incl. self-excitation" if any(self_loop) else ""))
        else:
            parts.append("feedforward (no cycle among members)")
        parts.append(f"{sum(drives_ro.values())} drive the readout directly, {sum(stim_in.values())} receive the stimulus directly")
        n_ess = sum(1 for p in core if self.ess.get(p) is True)
        parts.append(f"{n_ess} essential in situ")
        if alts:
            parts.append(f"{len(alts)} alternative implementation(s) found")
        return roles, loop, "; ".join(parts)


# -------------------------------------------------------------------------------------------------------------------- method
@MethodRegistry.register
class EvoPareto(DiscoveryMethod):
    """Evolutionary multi-objective structured search over keep-only subsets (NSGA-II on sufficiency, size and robustness with
    common random numbers, constrained domination and raced evaluation); structured mutation/crossover/repair operators guided
    by the public graph; redundancy probes for alternative implementations; a single-neuron silencing screen for in-situ
    necessity; core = knee of the confirmed candidates (function, robustness, in-situ relevance vs size), reduced by evidence-
    based leave-one-out and completed with essential gatekeepers."""

    name = "evo_pareto"
    version = "1.2"
    default_config = {
        "n_nominal": None, "n_robust_ga": 2, "n_robust_final": 4, "n_confirm_seeds": 2, "n_confirm": 3, "n_essential_seeds": 2,
        "n_intact_seeds": 2, "mu": 20, "lam": None, "max_generations": 400, "patience": 8, "redundancy_levels": 3,
        "reserve_frac": 0.12, "reserve_min": 16, "reserve_max": 80, "screen_max": 40, "screen_frac": 0.15,
        "pool_max": None, "pool_struct_min": 8, "pool_struct_frac": 0.25,
        "widen_factor": 2.0, "weight_noise_sd": 0.2, "flow_hops": 4, "flow_decay": 0.7, "t_end": None,
        "prior": None, "verbose": False,
    }

    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        S = _Search(problem, sim, seed, cfg)
        try:
            S.prescreen()
            S.initial_population()
            S.evolve()
        except BudgetExhausted:  # safety net: every phase already checks sim.remaining
            S.exhausted = True
            S.stop_reason = S.stop_reason or "budget exhausted"
        fin: dict = {"core": None, "confirmed": [], "screen": {}, "reduction": [], "gatekeepers": [], "gatekeepers_integrated": None, "group": None}
        try:
            fin = S.finalize()
        except BudgetExhausted:
            S.exhausted = True
        core_ind: Individual | None = fin.get("core")
        if core_ind is None:  # no sufficient proper subset: report the best-scoring one with its (failing) function estimates
            everything = tuple(S.cand)
            core_ind = max((i for i in S.archive.values() if i.members != everything and i.members),
                           key=lambda i: (i.pass_nominal(), i.score_nominal(), -i.size, i.members), default=None)
        core = list(core_ind.members) if core_ind is not None else []
        loo: dict[int, bool | None] = {}
        for m in core:
            child = S.archive.get(tuple(sorted(set(core) - {m})))
            loo[m] = None if child is None else (not child.sufficient())  # True = necessary within the core
        ess = {int(p): S.ess.get(p) for p in core}
        alts = S.alternatives(tuple(core)) if core else []
        S.update_frequency()
        probs = S.inclusion_probability(tuple(core), loo)
        roles, loop, motif = S.roles(core, loo, alts)
        if not core and core_ind is not None and core_ind.sufficient():
            motif = "no interneuron needed: the readout meets the criterion with the stimulus alone"
        fid: dict = {}
        if core_ind is not None:
            pr = core_ind.pass_robust()
            fid = {"keep_only_pass_fraction": core_ind.pass_nominal(), "keep_only_pass_robust": pr, "keep_only_score_mean": core_ind.score_nominal(),
                   "keep_only_robust_score_mean": core_ind.score_robust() if pr is not None else None, "frequency_hz": core_ind.frequency(),
                   "n_nominal_seeds": len(core_ind.nominal), "n_robust_probes": len(core_ind.robust), "sufficient": core_ind.sufficient(),
                   "in_situ_relevance": S.relevance(core_ind.members)}
        intact_pass = float(np.mean([o.passed for o in S.intact])) if S.intact else None
        intact_f = [o.frequency_hz for o in S.intact if o.frequency_hz is not None]
        fid.update(intact_pass_fraction=intact_pass, intact_frequency_hz=float(np.median(intact_f)) if intact_f else None,
                   intact_n_active_readout=int(np.median([o.n_active_readout for o in S.intact])) if S.intact else None)
        arch = list(S.archive.values())
        fronts = S._rank(arch)[0] if arch else []
        front = [arch[i] for i in fronts[0]] if fronts else []
        suff = S.sufficient_sets()
        smallest = min((i.size for i in suff), default=None)
        same_size = [set(i.members) for i in suff if i.size == smallest] if smallest is not None else []
        stability = {"n_minimal_size_sets": len(same_size),
                     "minimal_size_mean_jaccard": float(np.mean([_jaccard(a, b) for k, a in enumerate(same_size) for b in same_size[k + 1:]]))
                     if len(same_size) > 1 else None,
                     "core_score_std": float(np.std([o.score for o in core_ind.nominal.values()])) if core_ind is not None and core_ind.nominal else None,
                     "inclusion_entropy_bits": float(-sum(p * math.log2(p) + (1 - p) * math.log2(1 - p) for p in probs.values())) if probs else None}
        knee, knee0 = fin.get("knee"), fin.get("knee0")
        diag = {"pool_size": len(S.pool), "n_candidates": len(S.cand), "n_active_intact": int((S.act[S.cand] > 0).sum()) if len(S.cand) else 0,
                "nominal_seeds": S.nominal_seeds, "confirm_seeds": list(getattr(S, "confirm_extra", [])), "robust_probes": [p[0] for p in S.probes],
                "reserve": {"confirmation": S.reserve_conf, "screen": S.screen_reserve}, "generations": S.generation, "archive_size": len(S.archive),
                "n_sufficient": len(suff), "smallest_sufficient_size": smallest, "stopping_reason": S.stop_reason, "budget_exhausted": S.exhausted,
                "calls_by_phase": S.calls_by_phase, "operators": {k: {"tried": v[0], "sufficient": v[1]} for k, v in sorted(S.op_stats.items())},
                "n_intersection_failures": S.n_intersection_fail, "redundancy_probes": dict(S.redundancy),
                "screen": fin.get("screen", {}), "essential_screened": {int(k): v for k, v in sorted(S.ess.items())},
                "knee_before_screen": None if knee0 is None else list(knee0.members), "knee": None if knee is None else list(knee.members),
                "reduction_sizes": fin.get("reduction", []),
                "gatekeepers": [int(g) for g in fin.get("gatekeepers", [])], "gatekeepers_integrated": fin.get("gatekeepers_integrated"),
                "core_group_silenced_pass": fin.get("group"), "loo_necessary_within_core": {int(k): v for k, v in loo.items()},
                "front": [{"members": list(i.members), "size": i.size, "pass_nominal": i.pass_nominal(), "pass_robust": i.pass_robust(),
                           "score": round(i.score_nominal(), 4)} for i in sorted(front, key=lambda i: (i.size, i.members))[:40]],
                "confirmed": [{"members": list(i.members), "pass_nominal": i.pass_nominal(), "pass_robust": i.pass_robust(), "phi": round(S.phi(i), 4),
                               "relevance": round(S.relevance(i.members), 3)} for i in fin.get("confirmed", [])],
                "stability": stability, "trace": S.trace[-60:]}
        return DiscoveryResult(core=sorted(int(p) for p in core), inclusion_probability=probs, roles=roles, essential=ess,
                               alternatives=[list(a.members) for a in alts[:5]], loop=loop, predicted_frequency_hz=fid.get("frequency_hz"),
                               predicted_n_active_readout=core_ind.n_active_readout() if core_ind is not None else None,
                               predicted_function_preserved=(core_ind.pass_nominal() >= 0.5) if core_ind is not None else None, fidelity=fid,
                               budget={**sim.report(), "wall_s": round(time.time() - t0, 2)}, diagnostics=diag, motif=motif)


def main(argv: list[str] | None = None) -> int:
    """Run this method through the generic entry point (also the clean-room method file: reads BRAINIR_* variables)."""
    from brainir.discovery.run import main as run_main
    return run_main(["--method", EvoPareto.name, *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    sys.exit(main())
