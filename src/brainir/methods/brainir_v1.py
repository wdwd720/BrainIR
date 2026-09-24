"""brainir_v1 — order-invariant canonical group elimination with enumerated alternatives and a causal selection rule.

BrainIR v1 is ONE algorithm (research/phase2/BRAINIR_V1_METHOD.md has the formulation, the evidence behind every component and
the experiments). Objective: return a mechanism M that is (i) sufficient — keep-only of M passes the functional criterion on a
strict majority of parameter replicates, fresh ones included; (ii) 1-minimal — no member can be removed without losing the
function, with evidence, except context members that are necessary in the intact network; (iii) causally used — among the
functionally equivalent sufficient sets it finds, the one the intact network relies on decisively more, else the simplest
(fewest neurons), else the most robust, else the structurally canonical one; and (iv) independent of the node order and of
arbitrary search choices: the same mechanism is returned from any node order, and equally supported alternatives are reported
with shared probability instead of being silently picked.

Pipeline (every simulation goes through the given BudgetedSimulator; ``default_config`` switches every component):

 1. Working seeds: parameter replicates on which the intact network performs the function.
 2. Restriction (exact under the rate model): candidates must be reachable from the stimulus through excitatory edges (a
    neuron without excitatory drive never leaves rest) and must reach the readout; neurons silent in every intact run are
    removed as one group, verified by one decision.
 3. Canonical order: a permutation-equivariant structural relevance (forward excitatory random-walk mass from the stimulus x
    backward mass from the readout, synapse counts), ties broken by weighted degree. Removal goes least relevant first, so the
    search converges to the same minimal set from any node order (no random order anywhere).
 4. Group elimination over keep-only sets (adaptive group testing, ~k log2(n/k) decisions): remove a chunk, keep it removed if the
    rest passes (chunk doubles), bisect a failing chunk to isolate a necessary neuron (chunk halves); neurons silent in passing
    probes are queued first; then 1-minimality rounds. Every decision is a sequential strict majority over the working seeds,
    extended to more seeds when the first ones disagree (adaptive replication).
 5. Fresh-seed validation; if a majority of fresh seeds fails, the failing seed joins the decision seeds and the elimination is
    re-run from the pool (add-back).
 6. Necessity in the full network: single silencing of every member (essential claims) and a group-silencing screen with
    bisection of the other active candidates; neurons essential in the intact network join the core (context members).
 7. Alternatives, enumerated deterministically: disjoint sufficient sets in the complement, and for every non-essential member a
    replacement search that excludes it and then every filler already found (hitting-set enumeration of each slot).
 8. Selection: the canonical set is replaced only by a set that is decisively better on the first key that separates them —
    fresh-seed validation; then Occam (fewer neurons), unless the intact network relies decisively more, per distinctive member
    and paired over the working seeds, on the larger set; between equal sizes stress robustness (doubled parameter sds /
    weight noise 0.2, 4/4 vs 0/4 probes); otherwise the canonical order.
 9. Minimality certificate on fresh seeds (removable members are dropped), size-error curve, fidelity.
10. Uncertainty: inclusion probabilities from evidence classes mixed over the candidate mechanisms (tied mechanisms share mass,
    decisively worse ones keep a small weight); essential claims; generic roles from sign, the core's own wiring and the
    criterion; pre-registered intervention predictions.
11. Cross-connectome (bundle with a network of another dataset): after the core is final and validated, it is carried to the
    other network from the same budget pool (sim.spawn; allowance min(left, 25 % of the budget, 60 x (|core| + 2))) and verified
    there (brainir.discovery.joint: validated on >= 2 fresh seeds, completely minimised, essential structure reproduced, relied
    on by the other intact network). Identity claims only for a verified transfer that pairs up both cores one to one, only
    for matched pairs whose anchor fingerprints beat 'none' in both directions, with a calibrated probability; otherwise v1's
    own discovery of the other network gives a role-level alignment only. It never changes the core.

The optional ``config["prior"]`` ({position: p}) only biases the canonical order and the screen order; it never decides.
No mechanism size, neuron id, cell type, dataset name or instance-specific threshold appears anywhere.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from ..discovery.interface import GENERIC_ROLES, DiscoveryMethod, DiscoveryResult, MethodRegistry
from ..discovery.interventions import intact, keep_only, silence
from ..discovery.problem import DiscoveryProblem, same_animal
from ..discovery.simulator import BudgetedSimulator, BudgetExhausted, Outcome, SimQuery

# evidence classes -> inclusion probability (greedy_plus's calibration: Brier 0.0009 on the held-out selection suite)
P_ESSENTIAL = 0.97       # member of the mechanism whose single silencing in the full network fails the function
P_NECESSARY = 0.90       # member whose removal from the sufficient set fails the function (certified)
P_UNTESTED = 0.60        # member of a passing set never tested individually (budget ran out)
P_CLEARED = 0.03         # removed by a passing group / leave-one-out decision
P_SILENT = 0.01          # silent in every passing intact run (verified group removal)
P_STRUCTURAL = 0.002     # cannot influence the readout under the model
POINT_MODEL = "point"
SEED_BLOCK = 300
"""Parameter-replicate seeds of one run live in a block of 300 seeds: working replicates block+17.., fresh validation replicates
block+150.., stress probes block+250.. . Blocks are (seed mod 16) x 300, so every seed the method queries stays below 5,000 (seeds
5,000 and above are reserved for independent scoring)."""
SEED_BLOCKS = 16
MAX_SEED_TRIALS = 120
MAX_VALIDATION_SEEDS = 40
MAX_STRESS_PROBES = 40


class _OutOfBudget(Exception):
    """The next simulation would exceed the budget (or dip into the calls reserved for later phases)."""


@contextmanager
def guarded(diag: dict, name: str) -> Iterator[None]:
    """Finishing phases: budget exhaustion ends the phase; any other failure is recorded and never loses the mechanism."""
    try:
        yield
    except _OutOfBudget:
        diag.setdefault("out_of_budget_phases", []).append(name)
    except Exception as e:  # noqa: BLE001 - a late-phase failure must not discard the mechanism already found
        diag.setdefault("errors", []).append(f"{name}: {type(e).__name__}: {e}")


def parse_prior(raw, universe: frozenset[int]) -> dict[int, float] | None:
    """``config['prior']`` -> {position: p} restricted to candidates; None when absent or empty (uniform)."""
    if not raw or not isinstance(raw, dict):
        return None
    out: dict[int, float] = {}
    for k, v in raw.items():
        try:
            p, q = int(k), float(v)
        except (TypeError, ValueError):
            continue
        if p in universe and np.isfinite(q):
            out[p] = float(min(1.0, max(0.0, q)))
    return out or None


# ---------------------------------------------------------------------------- decisions (every simulation of the method)
@dataclass
class Decision:
    passed: bool
    n_pass: int
    n_fail: int
    outcomes: list[Outcome]
    seeds: tuple[int, ...]
    extended: bool = False

    @property
    def pass_fraction(self) -> float:
        n = self.n_pass + self.n_fail
        return self.n_pass / n if n else 0.0

    @property
    def active_union(self) -> set[int]:
        """Positions active in at least one PASSING outcome (the activity fingerprint of the function)."""
        act: set[int] = set()
        for o in self.outcomes:
            if o.passed:
                act.update(int(p) for p in o.active_positions.tolist())
        return act


class Prober:
    """Sequential strict-majority decisions on kept candidate sets over parameter replicates, with adaptive replication.

    A kept set ``S`` (subset of the candidate universe ``U``) is simulated as ``keep_only(S)`` (``silence(U - S)`` when that is
    the shorter description of the same network); ``S == U`` is the intact network, ``U - A`` is ``A`` silenced in the full
    network. A decision runs the decision seeds one at a time and stops once the strict majority is determined; when the seeds
    disagree and ``max_seeds`` exceeds their number, further working seeds are added until the strict majority of the larger
    set is determined (a split verdict is the one a few replicates cannot be trusted with)."""

    def __init__(self, problem: DiscoveryProblem, sim: BudgetedSimulator, universe: frozenset[int], *, base_seed: int, max_seed_trials: int,
                 t_end: float | None = None):
        self.problem = problem
        self.sim = sim
        self.U = universe
        self.t_end = t_end
        self.reserve = 0
        self.phase = "init"
        self.calls_by_phase: dict[str, int] = {}
        self.outcomes: dict[tuple, Outcome] = {}
        self.decisions: dict[tuple, Decision] = {}
        self.n_tests = 0
        self.n_extended = 0
        self.base_seed = int(base_seed)
        self.max_seed_trials = int(max_seed_trials)
        self.tried: list[int] = []
        self.working: list[int] = []
        self.intact_outcomes: dict[int, Outcome] = {}

    # ------------------------------------------------------------------ simulation
    def intervention(self, kept: frozenset[int], noise_sd: float = 0.0, noise_seed: int | None = None):
        removed = self.U - kept
        if not removed:
            return intact(weight_noise_sd=noise_sd, weight_noise_seed=noise_seed)
        if len(removed) <= len(kept):
            return silence(sorted(removed), weight_noise_sd=noise_sd, weight_noise_seed=noise_seed)
        return keep_only(self.problem, sorted(kept), weight_noise_sd=noise_sd, weight_noise_seed=noise_seed)

    def run(self, kept: frozenset[int], seed: int, cfg_override: dict | None = None, noise_sd: float = 0.0) -> Outcome:
        key = (kept, int(seed), tuple(sorted((cfg_override or {}).items())), float(noise_sd))
        if key in self.outcomes:
            return self.outcomes[key]
        if self.sim.remaining - 1 < self.reserve:
            raise _OutOfBudget(f"{self.sim.remaining} calls left, {self.reserve} reserved")
        iv = self.intervention(kept, noise_sd, int(seed) if noise_sd > 0 else None)
        try:
            out = self.sim.run(SimQuery(iv, int(seed), t_end=self.t_end, cfg_override=dict(cfg_override or {})))
        except BudgetExhausted as e:  # pragma: no cover - the pre-check above normally prevents this
            raise _OutOfBudget(str(e)) from e
        if not out.cached:
            self.calls_by_phase[self.phase] = self.calls_by_phase.get(self.phase, 0) + 1
        self.outcomes[key] = out
        return out

    # ------------------------------------------------------------------ working seeds (intact network passes)
    def collect_working(self, k: int) -> list[int]:
        """Try further seeds (base, base+1, ...) on the intact network until ``k`` working seeds exist or the trials run out."""
        while len(self.working) < k and len(self.tried) < self.max_seed_trials:
            s = self.base_seed + len(self.tried)
            o = self.run(self.U, s)
            self.tried.append(s)
            self.intact_outcomes[s] = o
            if o.passed:
                self.working.append(s)
        return list(self.working[:k])

    # ------------------------------------------------------------------ decisions
    def decide(self, kept: frozenset[int], seeds: tuple[int, ...], max_seeds: int = 0, min_seeds: int = 0) -> Decision:
        """``min_seeds``: replicates evaluated before an early stop is allowed (single-neuron necessity claims use all decision
        replicates, so a unanimous pair of replicates cannot settle them)."""
        key = (kept, tuple(seeds), int(max_seeds), int(min_seeds))
        if key in self.decisions:
            return self.decisions[key]
        outs: list[Outcome] = []
        n_pass = n_fail = 0
        used: list[int] = []

        def tally(seq: Iterable[int], need: int, total: int) -> bool | None:
            nonlocal n_pass, n_fail
            for s in seq:
                o = self.run(kept, s)
                outs.append(o)
                used.append(int(s))
                if o.passed:
                    n_pass += 1
                else:
                    n_fail += 1
                if len(used) < min_seeds:
                    continue
                if n_pass >= need:
                    return True
                if n_fail > total - need:
                    return False
            return None

        m = len(seeds)
        need = m // 2 + 1
        verdict = tally(seeds, need, m)
        extended = False
        if max_seeds > m and n_pass > 0 and n_fail > 0:
            # the replicates disagree: add working seeds until the strict majority of the larger set is determined
            n_extra = max_seeds - m
            try:
                in_seeds = sum(1 for s in self.working if s in set(seeds))
                more = [s for s in self.collect_working(in_seeds + n_extra) if s not in set(seeds)]
            except _OutOfBudget:
                more = [s for s in self.working if s not in set(seeds)]
            rest = [s for s in seeds if s not in set(used)] + more[:n_extra]
            if rest:
                total = len(used) + len(rest)
                need2 = total // 2 + 1
                extended = True
                self.n_extended += 1
                v2 = tally(rest, need2, total)
                verdict = v2 if v2 is not None else n_pass >= need2
        if verdict is None:
            verdict = n_pass >= need
        dec = Decision(bool(verdict), n_pass, n_fail, outs, tuple(used), extended)
        self.decisions[key] = dec
        self.n_tests += 1
        return dec


READOUT_STATS = ("score", "readout_peak_median_hz", "n_active_readout", "frequency_hz", "readout_range_median_hz", "readout_mean_hz",
                 "group_a_mean_hz", "group_b_mean_hz", "readout_during_hz", "readout_after_hz", "relative_slope_per_s")
"""Readout statistics an outcome carries (criterion score, readout activity, rhythm frequency / amplitude, criterion-specific means)."""


def readout_change(o0: Outcome, o1: Outcome) -> float:
    """Mean relative change (each term in [0, 1]) of the readout statistics between two outcomes; statistics absent or zero in both
    are skipped. Used to measure how much the intact network relies on a set (silencing it changes what the readout does)."""
    terms = []
    for k in READOUT_STATS:
        a = getattr(o0, k, None) if k in Outcome.__dataclass_fields__ else o0.extra.get(k)
        b = getattr(o1, k, None) if k in Outcome.__dataclass_fields__ else o1.extra.get(k)
        if a is None and b is None:
            continue
        a = 0.0 if a is None else float(a)
        b = 0.0 if b is None else float(b)
        den = max(abs(a), abs(b))
        if not np.isfinite(den) or den <= 1e-12:
            continue
        terms.append(min(1.0, abs(a - b) / den))
    return float(np.mean(terms)) if terms else 0.0


# ---------------------------------------------------------------------------- structure (zero simulator calls)
def _reach(adj_csr: sp.csr_matrix, sources: Iterable[int]) -> np.ndarray:
    """Nodes reachable from ``sources`` along ``adj_csr[i, j] != 0`` meaning i -> j."""
    n = adj_csr.shape[0]
    seen = np.zeros(n, dtype=bool)
    src = [int(s) for s in sources]
    if not src:
        return seen
    seen[src] = True
    frontier = np.zeros(n, dtype=bool)
    frontier[src] = True
    A = adj_csr.copy()
    A.data = np.ones_like(A.data)
    AT = A.T.tocsr()
    while frontier.any():
        nxt = (AT @ frontier.astype(np.float64)) > 0
        nxt &= ~seen
        seen |= nxt
        frontier = nxt
    return seen


def structural_candidates(problem: DiscoveryProblem) -> tuple[frozenset[int], frozenset[int]]:
    """(candidates that can shape the readout's response, candidates that cannot) — exact statements about the model.

    From rest (r = 0, thresholds >= 0) a neuron becomes active only through excitatory input from an active neuron, so a
    neuron not reachable from the stimulus through excitatory edges never fires; a neuron from which no readout neuron is
    reachable (any sign) cannot change the readout; a neuron with an unknown sign has a zero output column."""
    cand = frozenset(int(p) for p in problem.candidate_positions())
    W = problem.W.tocsr()
    exc_pre = W.multiply(W > 0).tocsr()           # post x pre, excitatory edges only
    down = _reach(exc_pre.T.tocsr(), problem.stim_positions)   # pre -> post adjacency
    up = _reach(W.tocsr(), problem.readout_positions)         # post -> pre adjacency (walk backwards from the readout)
    ok = frozenset(p for p in cand if down[p] and up[p] and int(problem.signs[p]) != 0)
    return ok, cand - ok


def relevance(problem: DiscoveryProblem, *, hops: int = 6, damping: float = 0.6, keep: np.ndarray | None = None) -> np.ndarray:
    """Permutation-equivariant structural relevance: sqrt(forward x backward) random-walk mass over synapse counts.

    Forward: mass leaves the stimulus and every EXCITATORY neuron split over its targets in proportion to the counts (the
    stimulus' drive); backward: mass leaves the readout split over each neuron's presynaptic partners in proportion to the
    counts (influence on the readout). Absolute counts matter (a half-weight copy of a neuron gets about half of its mass).
    ``keep`` (boolean mask) restricts the walk to the neurons that can shape the readout (plus stimulus and readout), so
    neurons that can never matter — e.g. sink-only distractors appended to a bundle — do not absorb mass or reorder the rest."""
    C = problem.C.tocsr().astype(np.float64)
    n = problem.n
    if keep is not None:
        d = sp.diags(np.asarray(keep, dtype=np.float64))
        C = (d @ C @ d).tocsr()
    exc = (np.asarray(problem.signs) > 0).astype(np.float64)
    Cf = (C @ sp.diags(exc)).tocsr()
    out_sum = np.asarray(Cf.sum(axis=0)).ravel()
    Pf = (Cf @ sp.diags(np.where(out_sum > 0, 1.0 / np.maximum(out_sum, 1e-12), 0.0))).tocsr()
    in_sum = np.asarray(C.sum(axis=1)).ravel()
    Pb = (sp.diags(np.where(in_sum > 0, 1.0 / np.maximum(in_sum, 1e-12), 0.0)) @ C).T.tocsr()
    f = np.zeros(n)
    f[list(problem.stim_positions)] = 1.0 / max(1, len(problem.stim_positions))
    g = problem.readout_mask.astype(np.float64)
    g /= max(1.0, g.sum())
    acc_f, acc_g = np.zeros(n), np.zeros(n)
    for h in range(int(hops)):
        f = Pf @ f
        g = Pb @ g
        acc_f += (damping ** h) * f
        acc_g += (damping ** h) * g
    return np.sqrt(acc_f * acc_g)


def weighted_degree(problem: DiscoveryProblem, keep: np.ndarray | None = None) -> np.ndarray:
    C = problem.C.tocsr().astype(np.float64)
    if keep is not None:
        d = sp.diags(np.asarray(keep, dtype=np.float64))
        C = (d @ C @ d).tocsr()
    return np.asarray(C.sum(axis=0)).ravel() + np.asarray(C.sum(axis=1)).ravel()


def canonical_order(nodes: Iterable[int], key: dict[int, tuple]) -> list[int]:
    """Least relevant first; ``key`` is permutation-equivariant up to exact ties (the position is only the last resort)."""
    return sorted((int(p) for p in nodes), key=lambda p: (*key[p], p))


# ---------------------------------------------------------------------------- group elimination (sufficiency)
@dataclass
class Elimination:
    kept: frozenset[int]
    necessary: dict[int, Decision] = field(default_factory=dict)
    """final members -> the failed decision on kept minus the member."""
    cleared: list[tuple[list[int], str]] = field(default_factory=list)
    complete: bool = True
    trace: list[tuple[str, int, int]] = field(default_factory=list)
    path: list[frozenset[int]] = field(default_factory=list)
    """passing kept sets along the search (for the size-error curve)."""
    n_decisions: int = 0


def eliminate(prober: Prober, kept: frozenset[int], seeds: tuple[int, ...], order: list[int], *, max_seeds: int = 0,
              protected: frozenset[int] = frozenset(), initial_chunk_fraction: float = 0.25, group: bool = True, adaptive: bool = True,
              minimality_rounds: int = 3) -> Elimination:
    """Adaptive group elimination from a passing set ``kept`` to a 1-minimal passing set, in the given (canonical) order.

    ``group=False``: one candidate per probe (backward elimination). ``adaptive=False``: fixed chunk size and no activity queue.
    ``protected`` members skip the group phase (they are believed necessary) but are tested in the 1-minimality rounds.
    Never raises on budget exhaustion: returns the current passing set with ``complete=False``."""
    res = Elimination(kept=kept, path=[kept])
    rank = {p: i for i, p in enumerate(order)}
    unresolved = [p for p in order if p in kept and p not in protected]
    unresolved += sorted(p for p in kept - protected if p not in rank)
    chunk = max(1, int(round(len(unresolved) * initial_chunk_fraction))) if group else 1

    def decide(S: frozenset[int]) -> Decision:
        res.n_decisions += 1
        return prober.decide(S, seeds, max_seeds)

    def queue_silent(dec: Decision) -> None:
        nonlocal unresolved, chunk
        if not (adaptive and group and dec.passed):
            return
        active = dec.active_union
        silent = [p for p in unresolved if p not in active]
        if len(silent) >= 2:
            unresolved = silent + [p for p in unresolved if p in active]
            chunk = max(chunk, len(silent))

    try:
        while unresolved:
            take = min(chunk, len(unresolved))
            X = unresolved[:take]
            unresolved = unresolved[take:]
            dec = decide(res.kept - frozenset(X))
            if dec.passed:
                res.kept = res.kept - frozenset(X)
                res.cleared.append((sorted(X), "group" if len(X) > 1 else "singleton"))
                res.trace.append(("clear", len(X), len(res.kept)))
                res.path.append(res.kept)
                if adaptive and group:
                    chunk = min(max(1, len(unresolved)), chunk * 2)
                queue_silent(dec)
                continue
            res.trace.append(("fail", len(X), len(res.kept)))
            leftovers: list[int] = []
            while len(X) > 1:  # bisect: isolate one neuron whose removal breaks the function; passing halves are cleared
                h = len(X) // 2
                X1, X2 = X[:h], X[h:]
                d1 = decide(res.kept - frozenset(X1))
                if d1.passed:
                    res.kept = res.kept - frozenset(X1)
                    res.cleared.append((sorted(X1), "bisect"))
                    res.trace.append(("clear", len(X1), len(res.kept)))
                    res.path.append(res.kept)
                    X = X2  # (kept - X1) - X2 == kept - X failed: X2 holds a necessary neuron
                    queue_silent(d1)
                else:
                    res.trace.append(("fail", len(X1), len(res.kept)))
                    leftovers = X2 + leftovers
                    X = X1
            res.trace.append(("necessary", 1, len(res.kept)))
            unresolved = leftovers + unresolved
            if adaptive and group:
                chunk = max(1, chunk // 2)
        # 1-minimality: every member (protected ones included) must be individually necessary in the final set
        for _round in range(max(0, int(minimality_rounds))):
            removed_any = False
            for v in [p for p in order if p in res.kept] + sorted(p for p in res.kept if p not in rank):
                if v not in res.kept:
                    continue
                d = decide(res.kept - {v})
                if d.passed:  # non-monotone context effect: v is no longer needed
                    res.kept = res.kept - {v}
                    res.cleared.append(([v], "singleton"))
                    res.trace.append(("clear", 1, len(res.kept)))
                    res.path.append(res.kept)
                    res.necessary.pop(v, None)
                    removed_any = True
                else:
                    res.necessary[v] = d
            if not removed_any:
                break
        res.necessary = {v: d for v, d in res.necessary.items() if v in res.kept}
    except (_OutOfBudget, MemoryError) as e:  # budget, or a resource failure: keep the current passing set
        res.complete = False
        if isinstance(e, MemoryError):
            res.trace.append(("memory_error", 0, len(res.kept)))
        res.necessary = {v: d for v, d in res.necessary.items() if v in res.kept}
    return res


# ---------------------------------------------------------------------------- necessity screen (full network)
@dataclass
class Screen:
    essential: dict[int, Decision] = field(default_factory=dict)
    cleared: list[list[int]] = field(default_factory=list)
    unscreened: list[int] = field(default_factory=list)
    complete: bool = True
    n_tests: int = 0
    confirmations: dict[int, dict] = field(default_factory=dict)


def necessity_screen(prober: Prober, pool: list[int], seeds: tuple[int, ...], *, max_seeds: int = 0, initial_chunk_fraction: float = 0.25,
                     max_calls: int | None = None, confirm=None) -> Screen:
    """Group silencing in the FULL network (non-cumulative), in the given order: a passing group holds no neuron that is
    essential alone (monotone case); a failing group is bisected, both halves tested, down to single neurons whose
    silencing alone fails. Finds neurons necessary only in context (e.g. an inhibitor that keeps a competitor silent). ``confirm``
    (position -> (necessary, info)) re-tests an isolated neuron with more replicates before it is accepted."""
    res = Screen()
    U = prober.U
    unresolved = list(pool)
    chunk = max(1, int(round(len(unresolved) * initial_chunk_fraction)))
    calls0 = prober.calls_by_phase.get(prober.phase, 0)

    def spent() -> int:
        return prober.calls_by_phase.get(prober.phase, 0) - calls0

    def decide(X: list[int]) -> Decision:
        res.n_tests += 1
        return prober.decide(U - frozenset(X), seeds, max_seeds)

    try:
        while unresolved:
            if max_calls is not None and spent() >= max_calls:
                raise _OutOfBudget("necessity screen call cap")
            take = min(chunk, len(unresolved))
            X = unresolved[:take]
            unresolved = unresolved[take:]
            if decide(X).passed:
                res.cleared.append(sorted(X))
                chunk = min(max(1, len(unresolved)), chunk * 2)
                continue
            while len(X) > 1:
                h = len(X) // 2
                X1, X2 = X[:h], X[h:]
                if not decide(X1).passed:
                    unresolved = X2 + unresolved
                    X = X1
                    continue
                res.cleared.append(sorted(X1))
                if not decide(X2).passed:
                    X = X2
                    continue
                res.cleared.append(sorted(X2))  # synergy only: neither half alone breaks the function
                X = []
                break
            if len(X) == 1:
                d = decide(X)
                necessary = not d.passed
                if necessary and confirm is not None:
                    necessary, info = confirm(X[0])
                    res.confirmations[X[0]] = info
                if necessary:
                    res.essential[X[0]] = d
                else:
                    res.cleared.append([X[0]])
            chunk = max(1, chunk // 2)
    except _OutOfBudget:
        res.complete = False
        res.unscreened = list(unresolved)
    return res


# ---------------------------------------------------------------------------- roles, loop, motif (zero calls)
def infer_roles(problem: DiscoveryProblem, core: list[int], *, extra: dict[int, str] | None = None) -> tuple[dict[int, tuple[str, float]], list[int], str]:
    """Generic roles from sign, the core's own wiring and the criterion type (greedy_plus's rules: role accuracy 0.95 on the
    held-out selection suite); the core's recurrent loop; a motif string."""
    core = sorted(int(p) for p in core)
    roles: dict[int, tuple[str, float]] = {}
    if not core:
        return roles, [], "no mechanism found"
    W = problem.W.tocsr()
    signs = problem.signs
    crit = str(problem.criterion_spec.get("type", "rhythm"))
    readout = problem.readout_positions
    stim = list(problem.stim_positions)
    idx = {p: i for i, p in enumerate(core)}
    sub = W[core, :][:, core].toarray()  # sub[a, b] = weight of core[b] -> core[a]
    adj = sp.csr_matrix((np.abs(sub) > 0).astype(np.int8))
    n_comp, labels = connected_components(adj, directed=True, connection="strong")
    comp_size = np.bincount(labels, minlength=n_comp)
    self_loop = np.diag(sub) > 0
    in_cycle = np.array([comp_size[labels[i]] >= 2 or self_loop[i] for i in range(len(core))])
    exc = np.array([signs[p] > 0 for p in core])
    exc_idx = [i for i in range(len(core)) if exc[i]]
    exc_cycle = np.zeros(len(core), dtype=bool)
    if exc_idx:
        adj_e = sp.csr_matrix((np.abs(sub[np.ix_(exc_idx, exc_idx)]) > 0).astype(np.int8))
        ne, le = connected_components(adj_e, directed=True, connection="strong")
        se = np.bincount(le, minlength=ne)
        for j, i in enumerate(exc_idx):
            exc_cycle[i] = se[le[j]] >= 2 or self_loop[i]
    Wc = W.tocsc()
    out_readout = np.zeros(len(core))
    for p in core:
        col = Wc.indices[Wc.indptr[p]:Wc.indptr[p + 1]]
        out_readout[idx[p]] = np.isin(readout, col).mean() if len(readout) else 0.0
    group_a = [int(x) for x in problem.criterion_spec.get("group_a_positions", [])]
    group_b = [int(x) for x in problem.criterion_spec.get("group_b_positions", [])]

    def drives(p: int, targets: list[int]) -> bool:
        col = Wc.indices[Wc.indptr[p]:Wc.indptr[p + 1]]
        return bool(np.isin(targets, col).any()) if targets else False

    for p in core:
        i = idx[p]
        s = int(signs[p])
        out_core = bool((np.abs(sub[:, i]) > 0).sum() - (1 if self_loop[i] else 0))
        in_stim = any(W[p, q] != 0 for q in stim)
        if s == 0:
            roles[p] = ("unknown", 0.5)
            continue
        if crit == "selectivity":
            if s < 0:
                roles[p] = ("lateral_inhibition", 0.75)
            elif drives(p, group_a):
                roles[p] = ("output_driver", 0.7)
            elif drives(p, group_b):
                roles[p] = ("competitor", 0.6)
            else:
                roles[p] = ("input_relay", 0.5)
            continue
        if s < 0:
            roles[p] = ("inhibitory_feedback", 0.75 if in_cycle[i] else 0.55) if crit == "rhythm" else ("gain_control", 0.7)
            continue
        if exc_cycle[i]:
            roles[p] = ("state_memory", 0.75) if crit in ("persistence", "ramp") else ("recurrent_excitatory_core", 0.75)
        elif in_cycle[i] and out_readout[i] > 0:
            roles[p] = ("recurrent_excitatory_core", 0.65) if crit == "rhythm" else ("output_driver", 0.65)
        elif out_readout[i] > 0:
            roles[p] = ("output_driver", 0.7)
        elif out_core:
            roles[p] = ("input_relay", 0.7 if in_stim else 0.55)
        else:
            roles[p] = ("input_relay", 0.4)
    for p, r in (extra or {}).items():
        if p not in roles and r in GENERIC_ROLES:
            roles[p] = (r, 0.5)
    loop: list[int] = []
    if n_comp:
        big = int(np.argmax(comp_size))
        if comp_size[big] >= 2:
            loop = [core[i] for i in range(len(core)) if labels[i] == big]
        else:
            loop = [core[i] for i in range(len(core)) if self_loop[i]][:1]
    n_exc, n_inh = int(exc.sum()), int((~exc).sum())
    if loop:
        loop_exc = sum(1 for p in loop if signs[p] > 0)
        if loop_exc == len(loop):
            motif = "recurrent excitation" + (" + inhibitory members" if n_inh else "")
        elif loop_exc == 0:
            motif = "inhibitory ring/loop" + (" + excitatory relay" if n_exc else "")
        else:
            motif = "recurrent excitation + inhibitory feedback loop"
    else:
        motif = "feedforward relay" + (" with inhibitory gain control" if n_inh else "")
    motif += f" ({n_exc} excitatory, {n_inh} inhibitory; criterion {crit})"
    return roles, sorted(loop), motif


def edge_predictions(problem: DiscoveryProblem, core: list[int], essential: dict[int, bool | None], necessary: set[int],
                     silencing: dict[int, dict]) -> list[dict]:
    """Pre-registered intervention predictions for every core member (no calls): the effect of silencing it alone in the intact
    network (from the silencing runs) and of removing its strongest in-core edge (from the core's wiring and the leave-one-out
    evidence: an edge whose removal leaves its presynaptic member with no in-core route to the readout, or takes it off every
    recurrent loop of the core under a criterion that needs recurrence, is predicted to break the function)."""
    core = sorted(int(p) for p in core)
    if not core:
        return []
    W = problem.W.tocsr()
    crit = str(problem.criterion_spec.get("type", "rhythm"))
    recurrent_criterion = crit in ("rhythm", "persistence", "ramp")
    readout = set(int(r) for r in problem.readout_positions)
    idx = {p: i for i, p in enumerate(core)}
    sub = W[core, :][:, core].toarray()  # post x pre
    Wc = W.tocsc()

    def reaches_readout(adj: np.ndarray, start: int) -> bool:
        seen, stack = {start}, [start]
        while stack:
            j = stack.pop()
            p = core[j]
            col = set(int(x) for x in Wc.indices[Wc.indptr[p]:Wc.indptr[p + 1]])
            if col & readout:
                return True
            for i in np.flatnonzero(adj[:, j] != 0):
                if int(i) not in seen:
                    seen.add(int(i))
                    stack.append(int(i))
        return False

    def on_cycle(adj: np.ndarray, j: int) -> bool:
        if adj[j, j] != 0:
            return True
        n_comp, lab = connected_components(sp.csr_matrix((adj != 0).astype(np.int8)), directed=True, connection="strong")
        return int(np.sum(lab == lab[j])) >= 2

    out = []
    for p in core:
        j = idx[p]
        rec: dict = {"position": int(p), "silence_alone": {"predicted_function_preserved": None if essential.get(p) is None else not essential[p],
                                                           **silencing.get(p, {})}}
        col = sub[:, j].copy()
        row = sub[j, :].copy()
        best = None
        for i in range(len(core)):  # outgoing in-core edges (self-loop included)
            if col[i] != 0 and (best is None or abs(col[i]) > abs(best[2])):
                best = (p, core[i], float(col[i]))
        if best is None:
            for i in range(len(core)):
                if i != j and row[i] != 0 and (best is None or abs(row[i]) > abs(best[2])):
                    best = (core[i], p, float(row[i]))
        if best is None:
            rec["strongest_in_core_edge"] = None
            out.append(rec)
            continue
        pre, post = best[0], best[1]
        adj2 = sub.copy()
        adj2[idx[post], idx[pre]] = 0.0
        lost_route = not reaches_readout(adj2, idx[pre]) and reaches_readout(sub, idx[pre])
        lost_loop = recurrent_criterion and on_cycle(sub, idx[pre]) and not on_cycle(adj2, idx[pre])
        cut = bool(lost_route or lost_loop)
        # intact network: only an edge of an ESSENTIAL member that is its only in-core route / loop is predicted to matter (a member with a
        # backup is compensated); keep-only core: the same for a member that is necessary within the core
        breaks_intact = bool(essential.get(pre)) and cut
        breaks_core = (pre in necessary or bool(essential.get(pre))) and cut
        rec["strongest_in_core_edge"] = {"pre": int(pre), "post": int(post), "signed_count": best[2],
                                         "predicted_function_preserved": not breaks_intact, "confidence": 0.75 if breaks_intact else 0.6,
                                         "predicted_function_preserved_in_core": not breaks_core,
                                         "basis": ("loop" if lost_loop else "route" if lost_route else "redundant_route"),
                                         "note": "structural prediction from the core's wiring and its silencing / leave-one-out evidence (not simulated)"}
        out.append(rec)
    return out


# ---------------------------------------------------------------------------- the method
@MethodRegistry.register
class BrainIRv1(DiscoveryMethod):
    """BrainIR v1: order-invariant canonical group elimination with enumerated alternatives, a causal selection rule, full-network
    necessity, calibrated uncertainty and verified cross-connectome transfer. See the module docstring."""

    name = "brainir_v1"
    version = "1.0"
    default_config = {
        # decisions
        "n_seeds_per_decision": 3,        # working seeds per accept/reject decision (sequential strict majority)
        "adaptive_replication": True,     # disagreeing seeds -> extend the decision to max_decision_seeds working seeds
        "max_decision_seeds": 5,
        "max_seed_trials": 10,            # intact runs tried to collect working seeds
        "validation_seeds": 3,            # fresh seeds for validating candidate mechanisms (common to all candidates)
        # restriction and order
        "structural_pruning": True,       # exact reachability / sign restriction
        "activity_pruning": True,         # remove neurons silent in the intact runs (verified by one decision)
        "use_structural_prior": True,     # canonical structural order (False: seeded random order)
        "relevance_hops": 6,
        "relevance_damping": 0.6,
        "prior_weight": 1.0,              # weight of logit(prior) in the canonical order (only with config["prior"])
        # search
        "use_group_testing": True,        # chunked removal with bisection (False: one candidate per probe)
        "use_active_selection": True,     # adaptive chunk sizes + activity-guided queue (False: fixed chunk size)
        "initial_chunk_fraction": 0.25,
        "minimality_cleanup": True,       # 1-minimality rounds + fresh-seed minimality certificate
        # necessity in the full network
        "member_essentiality": True,      # silence every member alone (essential claims)
        "necessity_screen": True,         # group-silencing screen of the other active candidates (context members)
        "necessity_screen_fraction": 0.3,
        # alternatives and selection
        "max_alternatives": 4,
        "max_fillers_per_member": 2,
        "alternatives_budget_fraction": 0.5,
        "robust_objective": True,         # stress probes (sd x2 / weight noise) enter the selection and fidelity
        "stress_probes": 4,
        "stress_noise_sd": 0.2,
        "stress_sd_factor": 2.0,
        "reliance_tiebreak": True,        # the intact network's reliance on each set's distinctive members enters the selection
        "reliance_margin": 0.05,          # decisive reliance: same sign on every seed, mean difference >= max(margin, rel_margin x larger)
        "reliance_rel_margin": 0.25,
        "validation_margin": 0.5,         # decisive validation difference (fresh-seed pass fractions)
        "stress_margin": 1.0,             # decisive stress difference: 4/4 vs 0/4 probes (weaker differences are replicate noise)
        # uncertainty and reporting
        "uncertainty_model": "posterior",  # "posterior" (evidence classes mixed over candidate mechanisms) or "point"
        "loser_weight": 0.15,
        "size_error_points": 3,
        # cross-connectome (a network of another dataset in the same bundle)
        "use_cross_connectome": True,
        "aux_budget_fraction": 0.25,      # the step spends from the SAME budget pool, after the core is final: at most this share of
        "aux_calls_per_member": 60,       # ... the declared budget, at most this many calls per core member (+2), never more than is left
        "aux_min_calls": 30,              # skipped when fewer calls than this are affordable
        "cross_fallback_discovery": True,  # transfer not verified: own discovery on the other network -> role-level alignment only
        "cross_fallback_min_calls": 60,
        # identity-claim probability sigmoid(a + b logit(dual-softmax fingerprint p) + c reproduced edges), fitted on my dev pairs
        # (b, c >= 0; research/phase2/BRAINIR_V1_METHOD.md section 12.6) and checked on held-out pairs
        "joint_config": {"identity_calibration": [1.2988, 0.2166, 1.8127]},
        "t_end": None,
        # "prior": {position: p}      optional, orders the search only
    }

    # ------------------------------------------------------------------ entry point
    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        result = _Run(problem, sim, int(seed), cfg).execute()
        if cfg.get("use_cross_connectome") and float(cfg.get("aux_budget_fraction") or 0) > 0:
            with guarded(result.diagnostics, "cross_connectome"):
                _cross_connectome(self, problem, sim, result, int(seed), cfg)
        result.budget = {**sim.report(), "wall_s": round(time.time() - t0, 1)}
        return result


# ---------------------------------------------------------------------------- one single-network run
class _Run:
    def __init__(self, problem: DiscoveryProblem, sim: BudgetedSimulator, seed: int, cfg: dict):
        self.problem, self.sim, self.seed, self.cfg = problem, sim, seed, cfg
        self.t0 = time.time()
        self.U = frozenset(int(p) for p in problem.candidate_positions())
        self.prior = parse_prior(cfg.get("prior"), self.U)
        block = (int(seed) % SEED_BLOCKS) * SEED_BLOCK
        self.base = block + 17
        self.budget0 = int(sim.remaining)
        self.m = max(1, int(cfg["n_seeds_per_decision"]))
        self.M = max(self.m, int(cfg["max_decision_seeds"])) if cfg.get("adaptive_replication") else 0
        self.n_val = min(MAX_VALIDATION_SEEDS, max(1, int(cfg["validation_seeds"])))
        self.prober = Prober(problem, sim, self.U, base_seed=self.base,
                             max_seed_trials=min(MAX_SEED_TRIALS, max(int(cfg["max_seed_trials"]), self.m, self.M)), t_end=cfg.get("t_end"))
        self.diag: dict = {"phases": [], "n_candidates": len(self.U), "seed": seed, "budget": self.budget0, "prior_used": self.prior is not None,
                           "config": {k: v for k, v in cfg.items() if k != "prior"}}
        self.prob: dict[int, float] = {}
        self.val_first = block + 150
        self.stress_first = block + 250

    # ------------------------------------------------------------------ helpers
    def phase(self, name: str, reserve: int) -> None:
        self.prober.phase = name
        self.prober.reserve = max(0, min(int(reserve), max(0, self.sim.remaining - 1)))
        self.diag["phases"].append({"name": name, "remaining_at_start": int(self.sim.remaining), "reserve": self.prober.reserve})

    def decide(self, S: frozenset[int], seeds: tuple[int, ...] | None = None) -> Decision:
        return self.prober.decide(S, self.seeds if seeds is None else seeds, self.M)

    def necessity(self, x: int) -> tuple[bool, dict]:
        """Is silencing ``x`` alone in the intact network destructive (sigma({x}) < 1/2)? Every working replicate is run (no early
        stop at two), a split is extended (adaptive replication), and the verdict pools these replicates with the fresh validation
        replicates on which the intact network passes: necessary iff more than half of the pooled replicates fail."""
        d = self.prober.decide(self.U - {x}, self.seeds, self.M, min_seeds=len(self.seeds))
        n_fail, n = d.n_fail, d.n_pass + d.n_fail
        s, fresh = self.val_first, 0
        try:
            while fresh < self.n_val and s < self.val_first + 2 * self.n_val + 1:
                if self.prober.run(self.U, s).passed:  # a replicate on which the intact network fails cannot tell
                    o = self.prober.run(self.U - {x}, s)
                    n += 1
                    n_fail += int(not o.passed)
                    fresh += 1
                s += 1
        except _OutOfBudget:
            pass
        frac_pass = 1.0 - n_fail / n if n else None
        return bool(n and n_fail * 2 > n), {"pass_fraction_silenced": None if frac_pass is None else round(frac_pass, 3), "n_seeds": n,
                                            "n_fresh": fresh}

    def validate(self, S: frozenset[int], n: int | None = None) -> dict:
        """Keep-only of ``S`` on fresh seeds (common to all candidates); a failing seed counts only if the intact network passes."""
        n = self.n_val if n is None else n
        res: dict = {"seeds": [], "passed": [], "pass_fraction": None, "failing_seeds": [], "discarded_seeds": [], "outcomes": []}
        s = self.val_first
        extra = 0
        try:
            while len(res["seeds"]) < n and extra <= n:
                o = self.prober.run(S, s)
                if o.passed:
                    res["seeds"].append(s); res["passed"].append(True); res["outcomes"].append(o)
                else:
                    oi = self.prober.run(self.U, s)
                    if oi.passed:
                        res["seeds"].append(s); res["passed"].append(False); res["failing_seeds"].append(s); res["outcomes"].append(o)
                    else:
                        res["discarded_seeds"].append(s)
                        extra += 1
                s += 1
        except _OutOfBudget:
            pass
        if res["seeds"]:
            res["pass_fraction"] = float(np.mean(res["passed"]))
        return res

    def stress(self, S: frozenset[int]) -> dict:
        """Keep-only of ``S`` under a stress ensemble: half the probes with all parameter sds widened, half with weight noise."""
        n = min(MAX_STRESS_PROBES, int(self.cfg["stress_probes"]))
        mc = self.problem.model_cfg
        f = float(self.cfg["stress_sd_factor"])
        wide = {"tau_sd": mc.tau_sd * f, "a_sd": mc.a_sd * f, "theta_sd": mc.theta_sd * f, "r_max_sd": mc.r_max_sd * f}
        outs_w, outs_n = [], []
        try:
            for j in range(n):
                s = self.stress_first + j
                if j % 2 == 0:
                    outs_w.append(self.prober.run(S, s, cfg_override=wide))
                else:
                    outs_n.append(self.prober.run(S, s, noise_sd=float(self.cfg["stress_noise_sd"])))
        except _OutOfBudget:
            pass
        allo = outs_w + outs_n
        return {"pass_fraction": float(np.mean([o.passed for o in allo])) if allo else None,
                "wide_pass_fraction": float(np.mean([o.passed for o in outs_w])) if outs_w else None,
                "noise_pass_fraction": float(np.mean([o.passed for o in outs_n])) if outs_n else None, "n": len(allo)}

    # ------------------------------------------------------------------ the pipeline
    def execute(self) -> DiscoveryResult:
        cfg, prober, diag, U = self.cfg, self.prober, self.diag, self.U
        # ---------------------------------------------------------------- 1. working seeds
        self.phase("seeds", min(self.n_val + 2, self.budget0 // 3))
        try:
            prober.collect_working(self.m)
        except _OutOfBudget:
            pass
        diag["seeds"] = {"tried": list(prober.tried), "working": list(prober.working)}
        if not prober.working:
            return self.empty("the intact network did not perform the function on any tried seed")
        self.seeds = tuple(prober.working[: self.m])
        self.intact_outs = [prober.intact_outcomes[s] for s in prober.tried]
        for p in U:
            self.prob[p] = P_UNTESTED
        # ---------------------------------------------------------------- 2. restriction
        self.phase("restriction", self.n_val + 2)
        if cfg["structural_pruning"]:
            K_struct, dropped = structural_candidates(self.problem)
        else:
            K_struct, dropped = U, frozenset()
        for p in dropped:
            self.prob[p] = P_STRUCTURAL
        active: set[int] = set()
        for s in self.seeds:
            active.update(int(p) for p in prober.intact_outcomes[s].active_positions.tolist())
        silent = frozenset(p for p in K_struct if p not in active)
        K0 = K_struct
        diag["restriction"] = {"structural_dropped": len(dropped), "silent_in_intact": len(silent), "activity_pruning_verified": None}
        if cfg["activity_pruning"] and silent and K_struct - silent != K_struct:
            try:
                d = self.decide(K_struct - silent)
                diag["restriction"]["activity_pruning_verified"] = bool(d.passed)
                if d.passed:
                    K0 = K_struct - silent
                    for p in silent:
                        self.prob[p] = P_SILENT
            except _OutOfBudget:
                pass
        self.K0 = K0
        diag["restriction"]["candidates_after"] = len(K0)
        # ---------------------------------------------------------------- 3. canonical order
        keep_mask = np.zeros(self.problem.n, dtype=bool)
        keep_mask[sorted(K_struct)] = True
        keep_mask[list(self.problem.always_keep())] = True
        rel = relevance(self.problem, hops=int(cfg["relevance_hops"]), damping=float(cfg["relevance_damping"]), keep=keep_mask)
        wdeg = weighted_degree(self.problem, keep=keep_mask)
        if cfg["use_structural_prior"]:
            key = {}
            for p in U:
                s = math.log(float(rel[p]) + 1e-300)
                if self.prior is not None:
                    q = min(0.99, max(0.01, self.prior.get(p, 0.5)))
                    s += float(cfg["prior_weight"]) * math.log(q / (1.0 - q))
                key[p] = (round(s, 9), round(float(wdeg[p]), 6))
        else:  # ablation: a seeded random order (the reference/greedy_plus style)
            rng = np.random.default_rng(self.seed)
            perm = rng.permutation(sorted(U))
            key = {int(p): (i,) for i, p in enumerate(perm)}
        self.key = key
        self.rel = rel
        order = canonical_order(K0, key)
        self.order = order
        # ---------------------------------------------------------------- 4. canonical group elimination
        elim_kw = {"max_seeds": self.M, "initial_chunk_fraction": float(cfg["initial_chunk_fraction"]), "group": bool(cfg["use_group_testing"]),
                   "adaptive": bool(cfg["use_active_selection"]), "minimality_rounds": 3 if cfg["minimality_cleanup"] else 0}
        self.elim_kw = elim_kw
        self.phase("elimination", self.n_val + 4)
        elim = eliminate(prober, K0, self.seeds, order, **elim_kw)
        diag["elimination"] = self.elim_summary(elim)
        # ---------------------------------------------------------------- 5. validation and add-back
        self.phase("validation", 2)
        val = self.validate(elim.kept)
        diag["validation"] = _val_diag(val)
        if (val["pass_fraction"] is not None and val["pass_fraction"] < 0.5 and val["failing_seeds"] and elim.complete
                and self.sim.remaining > 0.2 * self.budget0):
            self.phase("add_back", self.n_val + 4)
            seeds2 = tuple(list(self.seeds) + val["failing_seeds"][:1])
            elim2 = eliminate(prober, K0, seeds2, order, **elim_kw)
            diag["add_back"] = {"seeds": list(seeds2), "before": sorted(elim.kept), "after": sorted(elim2.kept), **self.elim_summary(elim2)}
            if elim2.kept != elim.kept and elim2.complete:
                elim, self.seeds = elim2, seeds2
                self.phase("validation", 2)
                val = self.validate(elim.kept)
                diag["validation_after_add_back"] = _val_diag(val)
        self.elim = elim
        M1 = elim.kept
        # ---------------------------------------------------------------- 6. necessity in the full network
        essential: dict[int, bool | None] = {}
        silencing: dict[int, dict] = {}
        if cfg["member_essentiality"]:
            self.phase("essentiality", 0)
            with guarded(diag, "essentiality"):
                for p in sorted(M1, key=lambda q: key[q], reverse=True):
                    essential[p], silencing[p] = self.necessity(p)
        E: frozenset[int] = frozenset()
        if cfg["necessity_screen"] and M1:
            self.phase("necessity_screen", 2)
            pool = sorted(K0 - M1, key=lambda q: (key[q], q), reverse=True)  # most relevant first (covered under the cap)
            screen = Screen()
            with guarded(diag, "necessity_screen"):
                screen = necessity_screen(prober, pool, self.seeds, max_seeds=self.M, initial_chunk_fraction=float(cfg["initial_chunk_fraction"]),
                                          max_calls=int(float(cfg["necessity_screen_fraction"]) * self.budget0), confirm=self.necessity)
            for p in screen.essential:
                essential[p] = True
                silencing[p] = screen.confirmations.get(p, {})
            E = frozenset(screen.essential)
            diag["necessity_screen"] = {"pool": len(pool), "found": sorted(E), "n_cleared_groups": len(screen.cleared),
                                        "confirmations": {int(k): v for k, v in screen.confirmations.items()},
                                        "unscreened": len(screen.unscreened), "complete": screen.complete, "tests": screen.n_tests,
                                        "calls": int(prober.calls_by_phase.get("necessity_screen", 0))}
        self.E = E
        # ---------------------------------------------------------------- 7. alternatives (deterministic enumeration)
        alts, alt_info = self.alternatives(M1, essential)
        diag["alternatives"] = alt_info
        # ---------------------------------------------------------------- 8. selection among the equivalent sets
        cands: list[frozenset[int]] = [M1 | E]
        kinds: list[str] = ["canonical"]
        for a, info in zip(alts, alt_info):
            c = a | E
            if c not in cands:
                cands.append(c)
                kinds.append(info["kind"])
        self.phase("selection", 0)
        ev, core_set, tied, losers, sel_trace = self.select(cands)
        diag["selection"] = {"candidates": [{"members": sorted(c), "kind": k, **{kk: vv for kk, vv in ev.get(c, {}).items() if kk != "val"}}
                                            for c, k in zip(cands, kinds)], "chosen": sorted(core_set), "trace": sel_trace,
                             "tied": [sorted(c) for c in tied], "decisively_worse": [sorted(c) for c in losers],
                             "dropped_not_minimal_or_invalid": [sorted(c) for c in getattr(self, "dropped", [])]}
        if core_set != cands[0]:
            with guarded(diag, "essentiality_of_selected_core"):
                self.phase("essentiality", 0)
                for p in sorted(core_set, key=lambda q: key[q], reverse=True):
                    if p not in essential and cfg["member_essentiality"]:
                        essential[p], silencing[p] = self.necessity(p)
        # ---------------------------------------------------------------- 9. minimality certificate on fresh seeds
        certified: set[int] = set()
        cert_info: dict = {}
        if cfg["minimality_cleanup"] and core_set:
            self.phase("minimality", 0)
            with guarded(diag, "minimality"):
                core_set, certified, cert_info = self.certify(core_set, ev)
        diag["minimality_certificate"] = cert_info
        core = sorted(core_set)
        necessary = set(certified) | {p for p in core if p in self.elim.necessary}
        # ---------------------------------------------------------------- 10. size-error curve, fidelity
        self.phase("fidelity", 0)
        curve: list[dict] = []
        with guarded(diag, "size_error_curve"):
            curve = self.size_error_curve(core_set, ev, cert_info)
        diag["size_error_curve"] = curve
        fid: dict = {}
        with guarded(diag, "fidelity"):
            fid = self.fidelity(core_set, ev)
        if not fid:
            fid = {"core_size": len(core)}
        # ---------------------------------------------------------------- 11. probabilities, roles, predictions
        alt_out = [sorted(c) for c in (tied + losers) if c != core_set]
        self.probabilities(core_set, tied, losers, essential, necessary, cands)
        diag["posterior"] = getattr(self, "weights", None)
        extra_roles = {p: "redundant_backup" for a in alt_out for p in a if p not in core_set}
        roles, loop, motif = infer_roles(self.problem, core, extra=extra_roles)
        essential_out = {p: essential.get(p) for p in core}
        diag["intervention_predictions"] = edge_predictions(self.problem, core, essential_out, necessary, silencing)
        diag["prober"] = {"tests": prober.n_tests, "extended_decisions": prober.n_extended, "calls_by_phase": dict(prober.calls_by_phase),
                          "budget_exhausted": not self.elim.complete, "working_seeds": list(self.seeds)}
        intact_outs = [prober.intact_outcomes[s] for s in prober.tried]  # every seed tried in order (unbiased), extensions included
        passing = [o for o in intact_outs if o.passed]
        freqs = [o.frequency_hz for o in passing if o.frequency_hz is not None]
        intact_frac = float(np.mean([o.passed for o in intact_outs])) if intact_outs else None
        diag["intact"] = {"n_seeds": len(intact_outs), "pass_fraction": intact_frac,
                          "frequency_hz_per_seed": [None if o.frequency_hz is None else round(float(o.frequency_hz), 3) for o in intact_outs]}
        return DiscoveryResult(core=core, inclusion_probability={int(p): float(q) for p, q in self.prob.items()}, roles=roles, essential=essential_out,
                               alternatives=alt_out, loop=loop, predicted_frequency_hz=float(np.median(freqs)) if freqs else fid.get("core_frequency_hz"),
                               predicted_n_active_readout=int(np.median([o.n_active_readout for o in passing])) if passing else None,
                               predicted_function_preserved=None if intact_frac is None else bool(intact_frac >= 0.5), fidelity=fid,
                               budget={**self.sim.report(), "wall_s": round(time.time() - self.t0, 1)}, diagnostics=diag, motif=motif)

    # ------------------------------------------------------------------ 7. alternatives
    def alternatives(self, M1: frozenset[int], essential: dict[int, bool | None]) -> tuple[list[frozenset[int]], list[dict]]:
        cfg, prober, U, K0 = self.cfg, self.prober, self.U, self.K0
        n_max = int(cfg["max_alternatives"])
        found: list[frozenset[int]] = []
        info: list[dict] = []
        if n_max <= 0 or not M1 or not self.elim.complete:
            return found, info
        n_stress = int(cfg["stress_probes"]) if cfg["robust_objective"] else 0
        eval_reserve = (n_max + 1) * (self.n_val + n_stress + self.m) + 2
        self.phase("alternatives", eval_reserve + int(self.sim.remaining * (1.0 - float(cfg["alternatives_budget_fraction"]))))

        def run_elim(start: frozenset[int], protected: frozenset[int] = frozenset()) -> Elimination | None:
            e = eliminate(prober, start, self.seeds, canonical_order(start, self.key), protected=protected, **self.elim_kw)
            return e if e.complete else None

        with guarded(self.diag, "alternatives"):
            # disjoint sufficient sets in the complement of everything found so far
            rest = K0 - M1
            while len(found) < n_max and rest:
                if not self.decide(rest).passed:
                    break
                e = run_elim(rest)
                if e is None or not e.kept:
                    break
                if e.kept != M1 and e.kept not in found:
                    found.append(e.kept)
                    info.append({"kind": "disjoint", "members": sorted(e.kept), "calls": self.sim.calls})
                rest = rest - e.kept
            # replacement fillers of every non-essential member (hitting-set enumeration of the slot)
            for p in sorted(M1, key=lambda q: self.key[q], reverse=True):
                if essential.get(p) is not False:
                    continue
                excluded = {p}
                for _k in range(int(cfg["max_fillers_per_member"])):
                    if len(found) >= n_max:
                        break
                    start = K0 - frozenset(excluded)
                    if not self.decide(start).passed:
                        start = U - frozenset(excluded)  # a filler may be silent in the intact network
                        if not self.decide(start).passed:
                            break
                    e = run_elim(start, protected=M1 - frozenset(excluded))
                    if e is None or not e.kept:
                        break
                    new = e.kept - M1
                    if e.kept != M1 and e.kept not in found:
                        found.append(e.kept)
                        info.append({"kind": f"replacement_for_{p}", "members": sorted(e.kept), "calls": self.sim.calls})
                    if not new:
                        break
                    excluded |= set(new)
        return found, info

    # ------------------------------------------------------------------ 8. selection
    def select(self, cands: list[frozenset[int]]):
        """Evaluate every candidate on the same fresh seeds (validation) and stress probes, and — when their sizes differ — the intact
        network's reliance on them; keep the canonical set unless a challenger is decisively better (validation; Occam unless the
        larger set is decisively more relied on; robustness between equal sizes)."""
        cfg = self.cfg
        ev: dict[frozenset[int], dict] = {}
        trace: list[dict] = []
        if not cands:
            return ev, frozenset(), [], [], trace

        def is_valid(c) -> bool:  # validated on fresh replicates (a candidate the budget did not let us validate is not)
            v = ev.get(c, {}).get("validation")
            return v is not None and v >= 0.5

        with guarded(self.diag, "selection_evaluation"):
            for c in cands:
                v = self.validate(c)
                ev[c] = {"validation": v["pass_fraction"], "val": v}
            if cfg["robust_objective"]:
                for c in cands:
                    st = self.stress(c)
                    ev[c].update(stress=st["pass_fraction"], stress_wide=st["wide_pass_fraction"], stress_noise=st["noise_pass_fraction"])
            valid0 = [c for c in cands if is_valid(c)]
            if cfg["reliance_tiebreak"] and len({len(c) for c in valid0}) >= 2:  # only used to let a larger set override Occam
                self.phase("reliance", 0)
                common = frozenset.intersection(*valid0)
                # reliance is measured on all working seeds up to max_decision_seeds (paired across candidates: same parameter draws)
                rseeds = list(self.seeds)
                if self.M > len(rseeds):
                    try:
                        rseeds += [s for s in self.prober.collect_working(self.M) if s not in set(rseeds)][: self.M - len(rseeds)]
                    except _OutOfBudget:
                        pass
                for c in valid0:
                    D = c - common
                    if not D:
                        continue
                    vals = []
                    for s in rseeds:
                        o0 = self.prober.run(self.U, s)
                        o = self.prober.run(self.U - D, s)
                        # per distinctive member: a larger set must change the intact readout proportionally more (Occam-neutral)
                        vals.append(((0.0 if o.passed else 1.0) + readout_change(o0, o)) / len(D))
                    ev[c]["reliance_per_seed"] = [round(x, 4) for x in vals]
                    ev[c]["reliance"] = round(float(np.mean(vals)), 4)
        valid = [c for c in cands if is_valid(c)] or [cands[0]]  # nothing validated: the canonical set (flagged by its fidelity)

        def st(c):
            return ev.get(c, {}).get("stress")

        def val(c):
            return ev.get(c, {}).get("validation")

        def no_worse(o, c) -> bool:
            vo, vc = val(o), val(c)
            if vo is not None and vc is not None and vo < vc:
                return False
            so, sc = st(o), st(c)
            return not (so is not None and sc is not None and so < sc)

        # a candidate that strictly contains an at-least-as-good candidate is not minimal
        pool = [c for c in valid if not any(o < c and no_worse(o, c) for o in valid)] or valid

        def relied_more(x: frozenset[int], y: frozenset[int]) -> bool:
            """The intact network relies decisively more (per distinctive member) on x than on y: paired over the same working
            replicates, every replicate agrees on the sign and the mean difference is >= max(margin, rel_margin x the larger)."""
            rx, ry = ev.get(x, {}).get("reliance_per_seed"), ev.get(y, {}).get("reliance_per_seed")
            if not rx or not ry or len(rx) != len(ry):
                return False
            d = np.array(rx) - np.array(ry)
            thr = max(float(cfg["reliance_margin"]), float(cfg["reliance_rel_margin"]) * max(float(np.mean(rx)), float(np.mean(ry))))
            return bool((d > 0).all() and d.mean() >= thr)

        def compare(a: frozenset[int], b: frozenset[int]) -> tuple[int, str]:
            """+1: a decisively better than b; -1: b decisively better; 0: tied (only the canonical order separates them).

            Validation first; then Occam — the smaller set wins unless the intact network relies decisively more (per member) on
            the larger one; equal sizes: decisive robustness, else the canonical (noise-free structural) order."""
            va, vb = val(a), val(b)
            if va is not None and vb is not None and abs(va - vb) >= float(cfg["validation_margin"]) - 1e-9:
                return (1 if va > vb else -1), "validation"
            if len(a) != len(b):
                small, large = (a, b) if len(a) < len(b) else (b, a)
                if cfg["reliance_tiebreak"] and relied_more(large, small):
                    return (1 if large == a else -1), "reliance"
                return (1 if small == a else -1), "size"
            sa, sb = st(a), st(b)
            if sa is not None and sb is not None and abs(sa - sb) >= float(cfg["stress_margin"]) - 1e-9:
                return (1 if sa > sb else -1), "stress"
            return 0, "tie"

        inc = pool[0]
        for c in pool[1:]:
            r, why = compare(c, inc)
            trace.append({"challenger": sorted(c), "incumbent": sorted(inc), "result": r, "key": why})
            if r > 0:
                inc = c
        tied, losers = [], []
        for c in pool:  # candidates outside the pool (not minimal, or not valid) are dropped, not reported
            if c == inc:
                continue
            r, _why = compare(inc, c)
            (tied if r == 0 else losers).append(c)
        self.dropped = [c for c in cands if c not in pool]
        return ev, inc, tied, losers, trace

    # ------------------------------------------------------------------ 9. minimality certificate
    def certify(self, core: frozenset[int], ev: dict) -> tuple[frozenset[int], set[int], dict]:
        """Every non-context member must be necessary on the pooled evidence of the working seeds and fresh seeds; a member whose
        removal passes on at least half of the pooled replicates is removed (the reduced set must itself pass) and the check repeats."""
        info: dict = {"members": {}, "removed": []}
        certified: set[int] = set()
        for _round in range(max(1, len(core))):
            changed = False
            for x in sorted(core - self.E, key=lambda q: self.key[q]):
                d = self.decide(core - {x})
                v = self.validate(core - {x})
                n_pass = d.n_pass + sum(v["passed"])
                n = d.n_pass + d.n_fail + len(v["passed"])
                frac = n_pass / n if n else 0.0
                info["members"][int(x)] = {"pass_fraction_without": round(frac, 3), "n": n, "fresh_pass_fraction_without": v["pass_fraction"]}
                if frac >= 0.5 and n:
                    reduced = core - {x}
                    ok_now = d.passed or (v["pass_fraction"] or 0.0) >= 0.5
                    if ok_now and reduced:
                        core = reduced
                        info["removed"].append(int(x))
                        certified.discard(x)
                        changed = True
                        break
                else:
                    certified.add(x)
            if not changed:
                break
        certified &= set(core)
        info["certified"] = sorted(certified)
        return core, certified, info

    # ------------------------------------------------------------------ 10. size-error curve and fidelity
    def size_error_curve(self, core: frozenset[int], ev: dict, cert: dict) -> list[dict]:
        pts: list[dict] = []
        path = [s for s in dict.fromkeys(self.elim.path) if s != core]  # passing sets along the canonical search, largest first
        want = max(0, int(self.cfg["size_error_points"]))
        chosen: list[frozenset[int]] = []
        if path and want:
            idx = sorted({int(round(i * (len(path) - 1) / max(1, want - 1))) for i in range(min(want, len(path)))})
            chosen = [path[i] for i in idx]
        for s in chosen:
            v = self.validate(s)
            if v["pass_fraction"] is not None:
                pts.append({"size": len(s), "error": round(1.0 - v["pass_fraction"], 3), "source": "search path", "returned": False})
        vc = ev.get(core, {}).get("validation")
        if vc is None:
            vc = self.validate(core)["pass_fraction"]
        if vc is not None:
            pts.append({"size": len(core), "error": round(1.0 - vc, 3), "source": "returned core", "returned": True,
                        "why": "smallest set on the path whose fresh-seed error is below 0.5 and from which no member can be removed without "
                               "losing the function (every leave-one-out point below has error >= 0.5)"})
        for x, m in (cert.get("members") or {}).items():
            if int(x) in core and m.get("fresh_pass_fraction_without") is not None:
                pts.append({"size": len(core) - 1, "error": round(1.0 - m["fresh_pass_fraction_without"], 3), "source": f"core without {x}",
                            "returned": False})
        return sorted(pts, key=lambda d: (-d["size"], d["error"]))

    def fidelity(self, core: frozenset[int], ev: dict) -> dict:
        v = ev.get(core, {}).get("val") or self.validate(core)
        outs = list(v.get("outcomes") or [])
        work = []
        for s in self.seeds:
            try:
                work.append(self.prober.run(core, s))
            except _OutOfBudget:
                break
        e = ev.get(core, {})
        if self.cfg["robust_objective"] and "stress" not in e and core:
            st = self.stress(core)
            e = {**e, "stress": st["pass_fraction"], "stress_wide": st["wide_pass_fraction"], "stress_noise": st["noise_pass_fraction"]}
        passing = [o for o in outs + work if o.passed]
        freqs = [o.frequency_hz for o in passing if o.frequency_hz is not None]
        return {"keep_only_pass_fraction": v.get("pass_fraction"), "n_fresh_seeds": len(v.get("seeds") or []),
                "keep_only_pass_fraction_working": float(np.mean([o.passed for o in work])) if work else None,
                "stress_pass_fraction": e.get("stress"), "robust_sd_x2_pass_fraction": e.get("stress_wide"),
                "weight_noise_pass_fraction": e.get("stress_noise"), "reliance": e.get("reliance"),
                "core_frequency_hz": float(np.median(freqs)) if freqs else None,
                "core_n_active_readout": int(np.median([o.n_active_readout for o in passing])) if passing else None, "core_size": len(core)}

    # ------------------------------------------------------------------ 11. probabilities
    def probabilities(self, core: frozenset[int], tied: list[frozenset[int]], losers: list[frozenset[int]], essential: dict,
                      necessary: set[int], cands: list[frozenset[int]]) -> None:
        """Evidence-class probability of every candidate, mixed over the candidate mechanisms: the chosen core and the mechanisms
        tied with it share the mass equally; a decisively worse mechanism keeps ``loser_weight``. A member's class inside a
        mechanism is P_ESSENTIAL (its single silencing fails), else P_NECESSARY (its removal fails / completed elimination), else
        P_UNTESTED (budget ran out before it was tested); outside it, P_CLEARED."""
        prob = self.prob
        for group, _tag in self.elim.cleared:
            for p in group:
                prob[p] = min(prob.get(p, 1.0), P_CLEARED)
        for c in [*cands, *getattr(self, "dropped", [])]:  # members of every set seen: cleared unless a mechanism below claims them
            for p in c:
                prob[p] = P_CLEARED
        if self.cfg.get("uncertainty_model") == POINT_MODEL:
            for p in list(prob):
                prob[p] = 1.0 if p in core else 0.0
            return

        def member_p(p: int, c: frozenset[int]) -> float:
            if essential.get(p):
                return P_ESSENTIAL
            if c != core or p in necessary or p in self.E:
                return P_NECESSARY
            return P_NECESSARY if self.elim.complete else P_UNTESTED

        # mixture over the mechanisms the evidence cannot separate: the chosen core and every mechanism tied with it get an equal
        # share; a member's probability is its evidence class times the summed share of the tied mechanisms containing it; a member
        # of a decisively worse mechanism keeps at least loser_weight (greedy_plus's calibrated value for alternative-only members)
        mech = [core, *tied]
        share = 1.0 / len(mech)
        for p in set().union(*mech, *losers):
            holders = [c for c in mech if p in c]
            q = share * len(holders) * member_p(p, core if p in core else holders[0]) if holders else 0.0
            if any(p in c for c in losers):
                q = max(q, float(self.cfg["loser_weight"]))
            prob[p] = max(q, P_CLEARED)
        self.weights = {"tied_share": round(share, 4), "n_tied": len(tied), "n_decisively_worse": len(losers)}

    # ------------------------------------------------------------------ misc
    def elim_summary(self, elim: Elimination) -> dict:
        counts: dict[str, int] = {}
        for _g, tag in elim.cleared:
            counts[tag] = counts.get(tag, 0) + 1
        return {"final_size": len(elim.kept), "final": sorted(elim.kept), "complete": elim.complete, "n_cleared_groups": counts,
                "n_necessary_confirmed": len(elim.necessary), "decisions": elim.n_decisions,
                "calls": int(self.prober.calls_by_phase.get(self.prober.phase, 0)),
                "trace_head": [list(t) for t in elim.trace[:40]]}

    def empty(self, reason: str) -> DiscoveryResult:
        self.diag["error"] = reason
        intact_outs = [self.prober.intact_outcomes[s] for s in self.prober.tried]
        frac = float(np.mean([o.passed for o in intact_outs])) if intact_outs else None
        return DiscoveryResult(core=[], inclusion_probability={int(p): 0.0 for p in self.U}, roles={}, essential={}, alternatives=[], loop=[],
                               predicted_function_preserved=None if frac is None else bool(frac >= 0.5), fidelity={},
                               budget={**self.sim.report(), "wall_s": round(time.time() - self.t0, 1)}, diagnostics=self.diag, motif=None)


def _val_diag(v: dict) -> dict:
    return {k: val for k, val in v.items() if k != "outcomes"}


# ---------------------------------------------------------------------------- cross-connectome (auxiliary budget, never changes the core)
def other_network(problem: DiscoveryProblem) -> str | None:
    """The first network (by name) of the same bundle that comes from ANOTHER dataset (another animal), or None. Networks of the
    same dataset (e.g. two versions of one connectome, or node-order variants) are never partners: a correspondence between
    them is not a cross-connectome result (review E finding 8). The bundle is read by the library, not by the method."""
    nets = problem.other_dataset_networks()
    return nets[0] if nets else None


def _cross_connectome(method: BrainIRv1, problem: DiscoveryProblem, sim: BudgetedSimulator, result: DiscoveryResult, seed: int,
                      cfg: dict) -> None:
    """Carry the final, validated core to a network of another dataset in the bundle and verify it there; emit calibrated identity
    claims only for a verified transfer, and a separate role-level alignment.

    Budget (one pool per run, review E finding 6): the step runs only after the core is final and validated, from the calls left,
    with an allowance of min(left, aux_budget_fraction x declared budget, aux_calls_per_member x (|core| + 2)); it is skipped when
    fewer than aux_min_calls are affordable. Its simulator is spawned from the primary one, so every call counts against the same
    budget. Transfer (joint.py's verified transfer): structural image from anchor fingerprints plus reproduced signed member edges,
    keep-only probes, minimisation that keeps full-network-essential members, counterparts of essential members, validation on at
    least two fresh replicates — verified only if validated, completely minimised (review E finding 3), every essential member
    has an essential counterpart and the other intact network relies on the image. Identity claims
    (``diagnostics["cross_connectome"]``) come only from a verified transfer whose matched pairs pair up both cores one to one,
    and only for matched pairs whose fingerprint evidence beats the 'none' option in both directions, with a calibrated identity
    probability (finding 1). If the transfer does not verify, v1 runs on the other network (with the transported prior unless
    the image was rejected on causal grounds); that gives a role-level alignment (``diagnostics["role_alignment"]``) but never
    identity claims. The primary core is never changed."""
    from ..discovery import joint
    from ..discovery.simulator import BudgetExhausted as _Exhausted

    diag = result.diagnostics
    diag["cross_connectome"] = []
    name = other_network(problem)
    if name is None:
        diag["auxiliary_budget"] = {"used": False, "reason": "no network of another dataset in the bundle", "calls": 0}
        return
    fid = (result.fidelity or {}).get("keep_only_pass_fraction")
    if not result.core or fid is None or fid < 0.5:
        diag["auxiliary_budget"] = {"used": False, "reason": "no validated core", "calls": 0, "network": name}
        return
    spawn = getattr(sim, "spawn", None)
    if spawn is None:
        diag["auxiliary_budget"] = {"used": False, "reason": "the simulator offers no auxiliary simulator (sim.spawn)", "calls": 0, "network": name}
        return
    allowance = int(min(sim.remaining, float(cfg["aux_budget_fraction"]) * sim.max_calls, int(cfg["aux_calls_per_member"]) * (len(result.core) + 2)))
    if allowance < int(cfg["aux_min_calls"]):
        diag["auxiliary_budget"] = {"used": False, "reason": f"unaffordable: {allowance} calls", "calls": 0, "network": name}
        return
    B = problem.load_network(name)
    if same_animal(problem, B):  # never claim identities within one animal
        diag["auxiliary_budget"] = {"used": False, "reason": "same dataset", "calls": 0, "network": name}
        return
    for f in B.files_read:
        if f not in problem.files_read:
            problem.files_read.append(f)
    aux = spawn(B, max_calls=allowance, kind="auxiliary")
    jcfg = {**joint.DEFAULT_CONFIG, **dict(cfg.get("joint_config") or {})}
    jseed = int(seed) % 4  # joint's probe / validation seeds are jseed*1000 + 600.. / 800..: below 5,000 (below 1,000 at seed 0)
    run = joint._PairRun(problem, B, method, 0, allowance, jseed, jcfg, 1)
    t0 = time.time()
    rec: dict = {"used": True, "network": name, "dataset": B.dataset, "version": B.version, "allowance": allowance,
                 "rule": "after the validated core; min(left, aux_budget_fraction x budget, aux_calls_per_member x (|core| + 2))"}
    try:
        tr = run.verified_transfer("a", "b", result, aux)
    except _Exhausted:
        tr = {"accepted": False, "probes": [], "reason": "auxiliary allowance exhausted"}
    rec["transfer"] = {"verified": bool(tr.get("accepted")), "probes": tr.get("probes"), "core_other": tr.get("core"),
                       "validation": tr.get("validation"), "n_validation_seeds": tr.get("n_validation_seeds"),
                       "superset": tr.get("superset"), "unmatched_essential": tr.get("unmatched_essential"), "rejected": tr.get("rejected"),
                       "calls": int(aux.calls)}
    res_b, source = None, None
    if tr.get("accepted"):
        res_b = run.result_from_transfer("b", tr)
        source = "verified_transfer"
    elif cfg.get("cross_fallback_discovery") and aux.remaining >= int(cfg["cross_fallback_min_calls"]):
        sub_cfg = {**cfg, "use_cross_connectome": False}
        sub_cfg.pop("prior", None)
        if tr.get("rejected") in joint.CAUSAL_REJECTIONS:  # the image was shown not to be the mechanism: no prior pointing at it
            summary = {"skipped": f"verified transfer rejected: {tr['rejected']}"}
        else:
            sub_cfg["prior"], summary = run.corr.transport("a", "b", result, rho=jcfg["prior_rho"] * jcfg["prior_damp_failed_transfer"],
                                                           base=jcfg["prior_base"], min_q=jcfg["prior_min_q"],
                                                           max_members=jcfg["prior_max_members"])
        calls0 = int(aux.calls)
        res_b = _Run(B, aux, seed, sub_cfg).execute()  # v1 itself on the other network, within what is left of the allowance
        rec["fallback"] = {"calls": int(aux.calls) - calls0, "core_other": sorted(int(p) for p in res_b.core), "prior": summary,
                           "budget_exhausted": bool((res_b.diagnostics.get("prober") or {}).get("budget_exhausted"))}
        source = "own_discovery_with_transported_prior" if "prior" in sub_cfg else "own_discovery"
    claims: list[dict] = []
    if res_b is not None and res_b.core:
        if source == "verified_transfer":
            ids = B.public_ids
            # only member pairs the verified transfer matched (a member and a candidate image of it that survived in the verified set)
            details = run.claim_details(result, res_b, include_ineligible=True, restrict=run.link_pairs(tr))
            for pa, pb, conf, _ev in details:
                if conf is not None:  # only matched pairs whose fingerprint evidence beats 'none' in both directions are claimed
                    claims.append({"source_position": int(pa), "other_dataset": B.dataset, "other_version": B.version,
                                   "other_source_id": int(ids[int(pb)]), "confidence": float(conf), "basis": "connectivity"})
            # compact evidence of every aligned pair: [position in a, position in b, w_ab, w_ba, none_ab, none_ba, dual-softmax p,
            # reproduced edges, claimed, matched by the transfer, complete one-to-one image]
            diag["identity_evidence"] = [[int(pa), int(pb), round(ev["w_ab"], 4), round(ev["w_ba"], 4), round(ev["none_ab"], 4),
                                          round(ev["none_ba"], 4), round(ev["p_fp"], 4), int(ev["edges"]), c is not None, bool(ev["linked"]),
                                          bool(ev["complete"])] for pa, pb, c, ev in details]
        al, graphs = run.alignment(result, res_b)
        diag["role_alignment"] = {"source": source, "other_network": name, "other_core": sorted(int(p) for p in res_b.core),
                                  "alignment": {k: v for k, v in al.items() if k != "role_graph_similarity"},
                                  "role_graph_similarity": al.get("role_graph_similarity"), "role_graphs": graphs,
                                  "note": "role-level alignment (roles and signed role interactions); not an identity claim"}
    rec.update(calls=int(aux.calls), simulated_seconds=round(float(aux.simulated_seconds), 3), wall_s=round(time.time() - t0, 1), source=source,
               n_claims=len(claims))
    diag["cross_connectome"] = claims
    diag["auxiliary_budget"] = rec
