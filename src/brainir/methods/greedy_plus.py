"""greedy_plus: intervention-guided group elimination with multi-seed decisions (improved simulation-guided elimination).

The reference method (``greedy_reference``) ranks candidates by weighted degree, keeps a degree-ranked pool and removes
the least impactful neuron per round with one parameter seed until a preset size ``k`` is reached. ``greedy_plus`` keeps
the idea "find a compact set whose keep-only network still performs the function" but replaces every order- and
size-dependent ingredient by intervention evidence:

1. **Working seeds.** Parameter seeds on which the intact network performs the function (a seed on which the intact
   network fails cannot tell necessary from unnecessary neurons).
2. **Exact pruning (no assumptions about the mechanism).** Neurons that are not reachable from the stimulus, or from which
   the readout is not reachable in the signed model matrix, cannot influence the readout's response in this rate model
   (no baseline activity) and are excluded. Neurons that were silent (peak rate below the criterion's activity threshold)
   in every intact run are removed as a group and the removal is verified by simulation; if the verification fails, the
   pruning is undone.
3. **Group elimination (adaptive group testing over keep-only sets).** The remaining set ``K`` passes by construction. A
   random chunk ``X`` is removed: if ``keep_only(K \\ X)`` still passes, ``X`` is unnecessary and the chunk size doubles;
   otherwise the chunk is bisected to isolate one neuron whose removal breaks the function (the halves that pass are
   cleared on the way) and the chunk size halves. Neurons that fall silent in a passing keep-only run are queued for the
   next chunk. This is Hwang-style binary splitting / ddmin with keep-only tests: about ``k log2(n/k)`` tests for a
   mechanism of ``k`` neurons among ``n`` candidates, independent of any degree ranking or node order (the order is a
   seeded random permutation; different seeds are different restarts).
4. **Every accept/reject decision uses several seeds.** A set passes iff a strict majority of the working seeds pass
   (sequential evaluation with early stopping: with three seeds, 2 passes accept and 2 failures reject).
5. **Stopping rule without a size prior.** The elimination ends when every remaining neuron has been tested individually
   and none can be removed without losing the function (1-minimality, re-checked after each removal for non-monotone
   effects). There is no target size.
6. **Validation and add-back.** The final set is validated on fresh seeds on which the intact network passes; when a
   strict majority of them fails, the first failing seed joins the decision seeds and the elimination is re-run from the
   pruned set (cached probes make this cheap), which adds back whatever the extra seed needs.
7. **Essentiality** = silencing the neuron alone in the FULL network fails the criterion (majority of the working seeds).
   Besides the members of the sufficient set, the other active candidates are screened by group silencing in the full
   network with bisection (a neuron that is essential without being sufficiency-necessary, e.g. an inhibitor that keeps
   a competitor silent, is part of the mechanism and is added to the core).
8. **Alternatives.** If the pruned set minus the core still performs the function, a disjoint alternative is searched by
   the same elimination; for every non-essential core member the replacement mechanism is searched in the pruned set
   without that member. Budget permitting, a randomized restart (different chunk order) re-derives the core. Among the
   functionally equivalent sets found, non-minimal ones (strict supersets of an at least equally robust set) are dropped
   and the reported core is the most robust one: first by the nominal pass fraction on fresh validation seeds, then under
   a stress ensemble (widened parameter distributions + multiplicative weight noise); ties are broken by how much the
   intact network relies on the set (silencing it in the full network: failure, then relative change of the readout),
   then by size. The others are reported as alternatives;
   the stability of the core across randomized elimination orders enters the inclusion probabilities.
9. **Inclusion probabilities** combine the evidence class of each neuron (necessary in the final set, essential in the
   full network, member of an alternative only, cleared by a passing group test, silent in the intact network,
   structurally irrelevant, untested because the budget ran out) with the membership frequency across restarts.
10. **Generic roles** (``GENERIC_ROLES``) from the sign, the position in the core's own wiring (self-excitation, cycles,
    projection onto the readout / other core members) and the criterion type; ``loop`` = the core's largest strongly
    connected component.

**Optional prior** (``config["prior"]``, a dict position -> prior inclusion probability in [0, 1], e.g. transferred from
another network): it only orders the search — low-prior neurons are removed first in the group elimination, high-prior
neurons are screened first for essentiality — and it sets the probability of members that could not be tested when the
budget ran out. It is never required and never decides membership; absent, the order is uniform.

The method respects ``sim.remaining`` at every step: each phase reserves the calls the later phases need and, when the
budget is tight, the current passing set (a superset of a mechanism) is returned with lower inclusion probabilities for
untested members. Unexpected failures in the finishing phases are recorded in ``diagnostics.errors`` and do not lose the
mechanism already found. No mechanism size, neuron id, cell type or dataset-specific threshold appears anywhere.
"""

from __future__ import annotations

import time
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from ..discovery.interface import GENERIC_ROLES, DiscoveryMethod, DiscoveryResult, MethodRegistry
from ..discovery.interventions import intact, keep_only, silence
from ..discovery.problem import DiscoveryProblem
from ..discovery.simulator import BudgetedSimulator, BudgetExhausted, Outcome, SimQuery

# evidence classes -> inclusion probability (see research/phase2/methods/greedy_plus.md for the calibration runs)
P_NECESSARY_ESSENTIAL = 0.97
P_NECESSARY = 0.90
P_UNTESTED_IN_CORE = 0.60
P_ALTERNATIVE_ONLY = 0.15
P_CLEARED_GROUP = 0.03
P_SILENT = 0.01
P_STRUCTURAL = 0.002


class _OutOfBudget(Exception):
    """The next simulation would exceed the budget (or the calls reserved for the finishing phases)."""


def majority_rule(m: int) -> tuple[int, int]:
    """(passes needed, failures allowed) for a strict majority of ``m`` seeds: m=1 -> (1,0), 2 -> (2,0), 3 -> (2,1), 4 -> (3,1), 5 -> (3,2)."""
    need = (m + 2) // 2
    return need, m - need


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


def ordered(nodes: Iterable[int], rng: np.random.Generator, prior: dict[int, float] | None, *, descending: bool = False,
            jitter: float = 0.25) -> list[int]:
    """Seeded random order; with a prior, sort by prior + U(0, jitter) noise (ascending = low prior first)."""
    nodes = sorted(int(p) for p in nodes)
    if not nodes:
        return []
    if prior is None:
        return [int(p) for p in rng.permutation(nodes)]
    keys = np.array([prior.get(p, 0.5) for p in nodes]) + rng.uniform(0.0, jitter, size=len(nodes))
    idx = np.argsort(-keys if descending else keys, kind="stable")
    return [nodes[i] for i in idx]


@contextmanager
def guarded(diag: dict, name: str) -> Iterator[None]:
    """Finishing phases: budget exhaustion ends the phase; any other failure is recorded and must not lose the result."""
    try:
        yield
    except _OutOfBudget:
        diag.setdefault("out_of_budget_phases", []).append(name)
    except Exception as e:  # noqa: BLE001 - deliberately broad: a late-phase failure must not discard the mechanism found
        diag.setdefault("errors", []).append(f"{name}: {type(e).__name__}: {e}")


@dataclass
class Decision:
    passed: bool
    n_pass: int
    n_fail: int
    outcomes: list[Outcome]
    seeds: tuple[int, ...]

    @property
    def score(self) -> float:
        return float(np.mean([o.score for o in self.outcomes])) if self.outcomes else 0.0

    @property
    def active_union(self) -> set[int]:
        """Positions active in at least one PASSING outcome (activity fingerprint of the function)."""
        act: set[int] = set()
        for o in self.outcomes:
            if o.passed:
                act.update(int(p) for p in o.active_positions.tolist())
        return act


class Oracle:
    """Multi-seed sequential-majority decisions on kept candidate sets. Every simulation goes through the BudgetedSimulator.

    A kept set ``S`` (subset of the candidate universe ``U``) is simulated as ``keep_only(S)`` when it is small and as
    ``silence(U \\ S)`` when it is large (identical network, cheaper canonical form); ``S == U`` is the intact network.
    """

    def __init__(self, problem: DiscoveryProblem, sim: BudgetedSimulator, universe: frozenset[int], *, t_end: float | None = None):
        self.problem = problem
        self.sim = sim
        self.U = universe
        self.t_end = t_end
        self.reserve = 0
        self.phase = "init"
        self.calls_by_phase: dict[str, int] = {}
        self.outcomes: dict[tuple, Outcome] = {}
        self.decisions: dict[tuple[frozenset[int], tuple[int, ...]], Decision] = {}
        self.n_tests = 0

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

    def decide(self, kept: frozenset[int], seeds: tuple[int, ...]) -> Decision:
        """Sequential strict-majority decision: stop as soon as the verdict is determined."""
        key = (kept, tuple(seeds))
        if key in self.decisions:
            return self.decisions[key]
        need, allowed = majority_rule(len(seeds))
        n_pass = n_fail = 0
        outs: list[Outcome] = []
        passed = False
        for s in seeds:
            o = self.run(kept, s)
            outs.append(o)
            if o.passed:
                n_pass += 1
            else:
                n_fail += 1
            if n_pass >= need:
                passed = True
                break
            if n_fail > allowed:
                passed = False
                break
        dec = Decision(passed, n_pass, n_fail, outs, tuple(seeds))
        self.decisions[key] = dec
        self.n_tests += 1
        return dec


# ---------------------------------------------------------------------------- structural pruning (zero simulator calls)
def reachable(A: sp.spmatrix, sources: Iterable[int]) -> np.ndarray:
    """Boolean mask of nodes reachable from ``sources`` following edges ``i -> j`` where ``A[i, j] != 0``."""
    A = sp.csr_matrix(A)
    n = A.shape[0]
    reach = np.zeros(n, dtype=bool)
    src = [int(s) for s in sources]
    if not src:
        return reach
    reach[src] = True
    frontier = reach.copy()
    AT = A.T.tocsr()
    AT.data[:] = 1.0
    while frontier.any():
        nxt = (AT @ frontier.astype(np.float64)) > 0
        nxt &= ~reach
        reach |= nxt
        frontier = nxt
    return reach


def structural_candidates(problem: DiscoveryProblem) -> tuple[frozenset[int], frozenset[int]]:
    """(candidates that can influence the readout's response, candidates that cannot).

    Under the rate model a neuron without input above threshold is silent, so a neuron the stimulus cannot reach (through
    non-zero signed weights) never fires, and a neuron from which no readout neuron is reachable never changes the readout.
    Both are exact statements about the model, not heuristics.
    """
    cand = frozenset(int(p) for p in problem.candidate_positions())
    W = problem.W
    down = reachable(W.T, problem.stim_positions)  # W[post, pre]: W.T[pre, post] is pre -> post
    up = reachable(W, problem.readout_positions)  # follow edges backwards from the readout
    ok = frozenset(p for p in cand if down[p] and up[p])
    return ok, cand - ok


# ---------------------------------------------------------------------------- elimination (sufficiency)
@dataclass
class Elimination:
    kept: frozenset[int]
    necessary: dict[int, Decision] = field(default_factory=dict)
    """final members -> the (failed) decision on kept \\ {member}."""
    cleared: list[tuple[list[int], str]] = field(default_factory=list)
    """groups removed with a passing decision, in order, with the evidence tag (group / bisect / singleton)."""
    complete: bool = True
    trace: list[tuple[str, int, int]] = field(default_factory=list)
    """(action, chunk size, |kept| afterwards) for diagnostics."""


def eliminate(oracle: Oracle, kept: frozenset[int], seeds: tuple[int, ...], rng: np.random.Generator, *, protected: frozenset[int] = frozenset(),
              initial_chunk_fraction: float = 0.25, activity_pruning: bool = True, max_minimality_rounds: int = 3,
              prior: dict[int, float] | None = None) -> Elimination:
    """Adaptive group elimination from a passing set ``kept`` to a 1-minimal passing set (see the module docstring).

    ``protected`` members are not part of the group phase (they are believed necessary) but are tested individually in the
    final 1-minimality rounds. With a ``prior``, low-prior neurons are queued first (removed first). Never raises on budget
    exhaustion: returns the current passing set with ``complete=False``.
    """
    res = Elimination(kept=kept)
    unresolved = ordered(kept - protected, rng, prior)
    necessary: set[int] = set()
    chunk = max(1, int(round(len(unresolved) * initial_chunk_fraction)))
    activity_ok = activity_pruning

    def queue_silent(dec: Decision) -> None:
        """Neurons of the kept set that were silent in every passing outcome: move them to the front of the queue."""
        nonlocal unresolved, chunk
        if not activity_ok or not dec.passed:
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
            dec = oracle.decide(res.kept - frozenset(X), seeds)
            if dec.passed:
                res.kept = res.kept - frozenset(X)
                res.cleared.append((sorted(X), "group"))
                res.trace.append(("clear", len(X), len(res.kept)))
                chunk = min(max(1, len(unresolved)), chunk * 2)
                queue_silent(dec)
            else:
                res.trace.append(("fail", len(X), len(res.kept)))
                # bisect X to isolate one neuron whose removal breaks the function; passing halves are cleared on the way
                leftovers: list[int] = []
                while len(X) > 1:
                    h = len(X) // 2
                    X1, X2 = X[:h], X[h:]
                    d1 = oracle.decide(res.kept - frozenset(X1), seeds)
                    if d1.passed:
                        res.kept = res.kept - frozenset(X1)
                        res.cleared.append((sorted(X1), "bisect"))
                        res.trace.append(("clear", len(X1), len(res.kept)))
                        X = X2  # (kept \ X1) \ X2 == kept \ X failed: X2 holds a necessary neuron
                        queue_silent(d1)
                    else:
                        res.trace.append(("fail", len(X1), len(res.kept)))
                        leftovers = X2 + leftovers
                        X = X1
                necessary.add(X[0])
                res.trace.append(("necessary", 1, len(res.kept)))
                unresolved = leftovers + unresolved
                chunk = max(1, chunk // 2)
        # 1-minimality: every remaining member (including protected ones) must be individually necessary in the final set
        for _round in range(max_minimality_rounds):
            removed_any = False
            for v in ordered(res.kept, rng, None):
                if v not in res.kept:
                    continue
                d = oracle.decide(res.kept - {v}, seeds)
                if d.passed:  # non-monotone context effect: v is no longer needed
                    res.kept = res.kept - {v}
                    res.cleared.append(([v], "singleton"))
                    res.trace.append(("clear", 1, len(res.kept)))
                    res.necessary.pop(v, None)
                    removed_any = True
                else:
                    res.necessary[v] = d
            if not removed_any:
                break
        res.necessary = {v: d for v, d in res.necessary.items() if v in res.kept}
    except (_OutOfBudget, MemoryError) as e:  # budget, or a resource failure of the simulator: keep the current passing set
        res.complete = False
        if isinstance(e, MemoryError):
            res.trace.append(("memory_error", 0, len(res.kept)))
        res.necessary = {v: d for v, d in res.necessary.items() if v in res.kept}
        for v in necessary:
            if v in res.kept and v not in res.necessary:
                d = oracle.decisions.get((res.kept - {v}, tuple(seeds)))
                if d is not None and not d.passed:
                    res.necessary[v] = d
    return res


# ---------------------------------------------------------------------------- essential screen (necessity in the full network)
@dataclass
class Screen:
    essential: dict[int, Decision] = field(default_factory=dict)
    """neurons whose silencing ALONE in the full network fails the criterion (the failed decision)."""
    cleared: list[list[int]] = field(default_factory=list)
    """groups whose joint silencing keeps the function (members individually non-essential under monotonicity)."""
    unscreened: list[int] = field(default_factory=list)
    complete: bool = True
    n_tests: int = 0


def essential_screen(oracle: Oracle, pool: list[int], seeds: tuple[int, ...], rng: np.random.Generator, *, initial_chunk_fraction: float = 0.25,
                     max_calls: int | None = None, prior: dict[int, float] | None = None) -> Screen:
    """Group silencing in the FULL network (non-cumulative): silence a chunk; if the function survives, no member is essential;
    otherwise bisect, testing both halves, down to single neurons whose silencing alone fails (exact essentiality).
    With a ``prior``, high-prior neurons are screened first."""
    res = Screen()
    U = oracle.U
    unresolved = ordered(set(pool), rng, prior, descending=True)
    chunk = max(1, int(round(len(unresolved) * initial_chunk_fraction)))
    calls0 = oracle.calls_by_phase.get(oracle.phase, 0)

    def spent() -> int:
        return oracle.calls_by_phase.get(oracle.phase, 0) - calls0

    try:
        while unresolved:
            if max_calls is not None and spent() >= max_calls:
                raise _OutOfBudget("essential screen call cap")
            take = min(chunk, len(unresolved))
            X = unresolved[:take]
            unresolved = unresolved[take:]
            dec = oracle.decide(U - frozenset(X), seeds)
            res.n_tests += 1
            if dec.passed:
                res.cleared.append(sorted(X))
                chunk = min(max(1, len(unresolved)), chunk * 2)
                continue
            while len(X) > 1:
                h = len(X) // 2
                X1, X2 = X[:h], X[h:]
                d1 = oracle.decide(U - frozenset(X1), seeds)
                res.n_tests += 1
                if not d1.passed:
                    unresolved = X2 + unresolved
                    X = X1
                    continue
                res.cleared.append(sorted(X1))
                d2 = oracle.decide(U - frozenset(X2), seeds)
                res.n_tests += 1
                if not d2.passed:
                    X = X2
                    continue
                res.cleared.append(sorted(X2))  # synergy only: neither half alone breaks the function
                X = []
                break
            if len(X) == 1:
                d = oracle.decide(U - frozenset(X), seeds)
                if not d.passed:
                    res.essential[X[0]] = d
                else:
                    res.cleared.append([X[0]])
            chunk = max(1, chunk // 2)
    except _OutOfBudget:
        res.complete = False
        res.unscreened = list(unresolved)
    return res


# ---------------------------------------------------------------------------- roles, loop, motif (zero simulator calls)
def infer_roles(problem: DiscoveryProblem, core: list[int], *, extra: dict[int, str] | None = None) -> tuple[dict[int, tuple[str, float]], list[int], str]:
    """Generic roles from sign, the core's own wiring and the criterion type; the core's recurrent loop; a motif string."""
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
            if crit == "rhythm":
                roles[p] = ("inhibitory_feedback", 0.75 if in_cycle[i] else 0.55)
            else:
                roles[p] = ("gain_control", 0.7)
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


# ---------------------------------------------------------------------------- the method
@MethodRegistry.register
class GreedyPlus(DiscoveryMethod):
    name = "greedy_plus"
    version = "1.2"
    default_config = {
        "seeds_per_decision": 3,        # working seeds per accept/reject decision (strict majority, sequential)
        "max_seed_trials": 8,           # intact runs tried to find the working seeds
        "validation_seeds": 3,          # fresh seeds for the keep-only validation of the core and of every alternative
        "initial_chunk_fraction": 0.25, # first group size as a fraction of the unresolved candidates
        "activity_pruning": True,       # queue neurons silent in passing runs for group removal
        "structural_pruning": True,     # exclude neurons that cannot influence the readout (exact under the model)
        "essential_screen": True,       # group silencing in the full network to find essential neurons outside the sufficient set
        "essential_screen_fraction": 0.3,   # at most this fraction of the initial budget goes to the screen
        "max_alternatives": 3,
        "alternatives_budget_fraction": 0.5,  # at most this fraction of the calls remaining after the screen goes to alternatives
        "restarts": 1,                  # randomized re-derivations of the core, budget permitting
        "restart_budget_fraction": 0.35,    # at most this fraction of the calls remaining after the alternatives
        "stress_probes": 3,             # widened-parameter + weight-noise probes used to rank equivalent sets / report robustness
        "stress_noise_sd": 0.2,
        "t_end": None,
        # "prior": {position: p}      optional, see the module docstring
    }

    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        rng = np.random.default_rng(int(seed))
        m = max(1, int(cfg["seeds_per_decision"]))
        base = int(seed) * 1000 + 17
        budget0 = int(sim.remaining)
        U = frozenset(int(p) for p in problem.candidate_positions())
        prior = parse_prior(cfg.get("prior"), U)
        diag: dict = {"phases": [], "n_candidates": len(U), "seed": int(seed), "budget": budget0, "prior_used": prior is not None}
        oracle = Oracle(problem, sim, U, t_end=cfg.get("t_end"))
        untested_p = (lambda p: P_UNTESTED_IN_CORE) if prior is None else (lambda p: 0.5 * P_UNTESTED_IN_CORE + 0.5 * prior.get(p, 0.5))
        prob: dict[int, float] = {p: untested_p(p) for p in U}
        n_val = int(cfg["validation_seeds"])
        n_alt = int(cfg["max_alternatives"])
        frac = float(cfg["initial_chunk_fraction"])
        act = bool(cfg["activity_pruning"])
        stress_reserve = int(cfg["stress_probes"]) * (1 + n_alt) + n_val * n_alt + 2
        elim_kw = {"initial_chunk_fraction": frac, "activity_pruning": act, "prior": prior}

        def phase(name: str, reserve: int) -> None:
            oracle.phase = name
            oracle.reserve = max(0, int(reserve))
            diag["phases"].append({"name": name, "remaining_at_start": int(sim.remaining), "reserve": oracle.reserve})

        def sub_rng() -> np.random.Generator:
            return np.random.default_rng(int(rng.integers(2**31)))

        # ---------------------------------------------------------------- 1. working seeds (intact network must pass)
        phase("seeds", n_val + 2)
        working: list[int] = []
        tried: list[int] = []
        intact_outs: list[Outcome] = []
        try:
            for i in range(int(cfg["max_seed_trials"])):
                if len(working) >= m:
                    break
                s = base + i
                o = oracle.run(U, s)
                tried.append(s)
                if o.passed:
                    working.append(s)
                    intact_outs.append(o)
        except _OutOfBudget:
            pass
        diag["seeds"] = {"tried": tried, "working": list(working)}
        if not working:
            return self._empty(problem, sim, t0, diag, "the intact network did not perform the function on any tried seed", U)
        seeds = tuple(working)

        # ---------------------------------------------------------------- 2. exact pruning
        phase("pruning", n_val + 2)
        if cfg["structural_pruning"]:
            K_struct, dropped = structural_candidates(problem)
        else:
            K_struct, dropped = U, frozenset()
        for p in dropped:
            prob[p] = P_STRUCTURAL
        K0 = K_struct
        active: set[int] = set()
        for o in intact_outs:
            active.update(int(p) for p in o.active_positions.tolist())
        silent = frozenset(p for p in K_struct if p not in active)
        diag["pruning"] = {"structural_dropped": len(dropped), "silent_in_intact": len(silent), "activity_pruning_verified": None}
        if act and silent:
            try:
                d = oracle.decide(K_struct - silent, seeds)
                diag["pruning"]["activity_pruning_verified"] = bool(d.passed)
                if d.passed:
                    K0 = K_struct - silent
                    for p in silent:
                        prob[p] = P_SILENT
            except _OutOfBudget:
                pass
        diag["pruning"]["candidates_after"] = len(K0)

        # ---------------------------------------------------------------- 3. group elimination (sufficiency)
        phase("elimination", n_val + 4)
        elim = eliminate(oracle, K0, seeds, sub_rng(), **elim_kw)
        diag["elimination"] = self._elim_summary(elim, oracle)
        suff = elim.kept

        # ---------------------------------------------------------------- 4. validation on fresh seeds (+ add-back re-run)
        phase("validation", 2)
        val_seed0 = base + 500
        val = self._validate(oracle, U, suff, val_seed0, n_val)
        diag["validation"] = val
        if val["genuine"] and 2 * sum(val["passed"]) < val["genuine"] and val["failing_seeds"] and sim.remaining > 0.2 * budget0:
            phase("add_back", n_val + 4)
            seeds2 = tuple(list(seeds) + val["failing_seeds"][:1])
            elim2 = eliminate(oracle, K0, seeds2, np.random.default_rng(int(seed) + 1), **elim_kw)
            diag["add_back"] = {"seeds": list(seeds2), "before": sorted(suff), "after": sorted(elim2.kept), **self._elim_summary(elim2, oracle)}
            if elim2.kept != suff:
                elim, suff, seeds = elim2, elim2.kept, seeds2
                val_seed0 = base + 600
                phase("validation", 2)
                val = self._validate(oracle, U, suff, val_seed0, n_val)
                diag["validation_after_add_back"] = val

        # ---------------------------------------------------------------- 5. essentiality: members, then the screen of the other candidates
        phase("essential", 0)
        essential: dict[int, bool | None] = {}
        with guarded(diag, "essential"):
            for p in sorted(suff, key=lambda q: (q not in elim.necessary, q)):
                essential[p] = not oracle.decide(U - {p}, seeds).passed
        screen = Screen()
        if cfg["essential_screen"]:
            phase("essential_screen", 2)
            pool = sorted(K0 - suff)
            with guarded(diag, "essential_screen"):
                screen = essential_screen(oracle, pool, seeds, sub_rng(), initial_chunk_fraction=frac, prior=prior,
                                          max_calls=int(float(cfg["essential_screen_fraction"]) * budget0))
            for p in screen.essential:
                essential[p] = True
            diag["essential_screen"] = {"pool": len(pool), "found": sorted(screen.essential), "n_cleared_groups": len(screen.cleared),
                                        "unscreened": len(screen.unscreened), "complete": screen.complete, "tests": screen.n_tests,
                                        "calls": int(oracle.calls_by_phase.get("essential_screen", 0))}
        E = frozenset(screen.essential)

        # ---------------------------------------------------------------- 6. alternatives (sufficient sets) and restarts, both capped
        alternatives: list[frozenset[int]] = []
        alt_info: list[dict] = []
        phase("alternatives", stress_reserve + int(sim.remaining * (1.0 - float(cfg["alternatives_budget_fraction"]))))
        with guarded(diag, "alternatives"):
            rest = K0 - suff
            for _ in range(n_alt):
                if not rest or not oracle.decide(rest, seeds).passed:
                    break
                e = eliminate(oracle, rest, seeds, sub_rng(), **elim_kw)
                if not e.complete:
                    break
                if e.kept and e.kept != suff and e.kept not in alternatives:
                    alternatives.append(e.kept)
                    alt_info.append({"kind": "disjoint", "members": sorted(e.kept)})
                rest = rest - e.kept
            for p in sorted(suff):
                if essential.get(p) is not False or len(alternatives) >= n_alt:
                    continue
                start = K0 - {p}
                if not oracle.decide(start, seeds).passed:
                    start = U - {p}  # the replacement was silent in the intact network: search the whole candidate set
                e = eliminate(oracle, start, seeds, sub_rng(), protected=suff - {p}, **elim_kw)
                if e.complete and e.kept and e.kept != suff and e.kept not in alternatives:
                    alternatives.append(e.kept)
                    alt_info.append({"kind": f"replacement_for_{p}", "members": sorted(e.kept)})
        phase("restarts", stress_reserve + int(sim.remaining * (1.0 - float(cfg["restart_budget_fraction"]))))
        restart_sets: list[frozenset[int]] = []
        first_cost = diag["elimination"]["calls"]
        with guarded(diag, "restarts"):
            for r in range(int(cfg["restarts"])):
                if sim.remaining - oracle.reserve < max(4, first_cost):
                    break
                e = eliminate(oracle, K0, seeds, np.random.default_rng(int(seed) * 7919 + 101 + r), **elim_kw)
                if not e.complete:
                    break
                restart_sets.append(e.kept)
                if e.kept != suff and e.kept not in alternatives and len(alternatives) < n_alt:
                    alternatives.append(e.kept)
                    alt_info.append({"kind": "restart", "members": sorted(e.kept)})
        diag["alternatives"] = alt_info
        diag["restarts"] = {"sets": [sorted(s) for s in restart_sets], "same_as_core": [s == suff for s in restart_sets]}

        # ---------------------------------------------------------------- 7. rank the equivalent sets by robustness; the best is the core
        phase("stress", 0)
        candidates = [suff | E]
        for a in alternatives:
            if (a | E) not in candidates:
                candidates.append(a | E)
        robust: dict[frozenset[int], dict] = {}
        with guarded(diag, "stress"):
            for cset in candidates:
                st = self._stress(oracle, cset, seeds, int(cfg["stress_probes"]), float(cfg["stress_noise_sd"]))
                vv = self._validate(oracle, U, cset, val_seed0, n_val)
                comb = 0.5 * (st["pass_fraction"] + vv["pass_fraction"]) if vv["genuine"] else st["pass_fraction"]
                robust[cset] = {"stress": st, "validation": vv, "combined": float(comb)}
        def rb_of(c: frozenset[int]) -> tuple[float, float]:
            """(nominal pass fraction on the fresh validation seeds, stress pass fraction); the nominal function is the target."""
            r = robust.get(c)
            if not r:
                return (-1.0, -1.0)
            v = r["validation"]["pass_fraction"]
            return (round(v if v is not None else r["stress"]["pass_fraction"], 2), round(r["stress"]["pass_fraction"], 2))

        def dominates(o: frozenset[int], c: frozenset[int]) -> bool:
            a, b = rb_of(o), rb_of(c)
            return a[0] >= b[0] and a[1] >= b[1]

        # a candidate that strictly contains another candidate that is at least as robust (nominal and stress) is not minimal
        minimal = [c for c in candidates if not any(o < c and dominates(o, c) for o in candidates)] or list(candidates)
        # reliance (only to break ties among equally robust sets): how much the INTACT network relies on the set's DISTINCTIVE members
        # (members shared by all tied sets are left in place, otherwise their own effect confounds the comparison) = 1 if silencing
        # them in the full network fails the criterion, plus the relative change of the readout's peak rate (working seeds; the
        # intact runs are cached). A weaker copy or an incidental hub that could implement the function alone is relied on less.
        reliance: dict[frozenset[int], float] = {}
        top = max(rb_of(c) for c in minimal)
        tied = [c for c in minimal if rb_of(c) == top]
        if len(tied) >= 2:
            phase("reliance", 0)
            common = frozenset.intersection(*tied)
            with guarded(diag, "reliance"):
                for c in tied:
                    vals = []
                    for s in seeds:
                        r0 = oracle.run(U, s).readout_peak_median_hz
                        o = oracle.run(U - (c - common), s)
                        r1 = o.readout_peak_median_hz
                        vals.append((0.0 if o.passed else 1.0) + abs(r1 - r0) / max(r0, r1, 1e-9))
                    reliance[c] = round(float(np.mean(vals)), 2)
        # rank: nominal fresh-seed pass fraction, stress pass fraction, reliance of the intact network, size (Occam), stress score,
        # then the anatomical strength of the members (mean absolute weighted degree) as the last tie-breaker among functionally
        # indistinguishable sets, then order of discovery
        absW = abs(problem.W)
        wdeg = np.asarray(absW.sum(axis=0)).ravel() + np.asarray(absW.sum(axis=1)).ravel()
        order0 = {c: i for i, c in enumerate(candidates)}

        def rank_key(c: frozenset[int]) -> tuple:
            r = robust.get(c)
            nominal, stressed = rb_of(c)
            return (-nominal, -stressed, -reliance.get(c, 0.0), len(c), -(round(r["stress"]["score"], 2) if r else 0.0),
                    -float(np.mean([wdeg[p] for p in c])) if c else 0.0, order0[c])

        ranked = sorted(minimal, key=rank_key)
        core_set = ranked[0] if ranked else suff | E
        if core_set != candidates[0]:
            diag["core_switched_to_more_robust_alternative"] = {"from": sorted(candidates[0]), "to": sorted(core_set)}
            with guarded(diag, "essential_of_switched_core"):
                for p in sorted(core_set):
                    if p not in essential:
                        essential[p] = not oracle.decide(U - {p}, seeds).passed
        alt_out = [sorted(c) for c in ranked if c != core_set]
        diag["robustness"] = {str(sorted(c)): {"stress": v["stress"], "validation_pass_fraction": v["validation"]["pass_fraction"],
                                                "combined": v["combined"], "reliance": reliance.get(c), "minimal": c in minimal}
                              for c, v in robust.items()}
        core = sorted(core_set)
        essential = {p: essential.get(p) for p in core}

        # ---------------------------------------------------------------- 8. fidelity of the reported core
        phase("fidelity", 0)
        rob_core = robust.get(core_set)
        val_core = rob_core["validation"] if rob_core else (val if core_set == suff else {"seeds": [], "pass_fraction": None})
        fid: dict = {}
        with guarded(diag, "fidelity"):
            fid = self._fidelity(oracle, core_set, seeds, val_core, rob_core["stress"] if rob_core else None)
        if not fid:
            fid = {"core_size": len(core), "keep_only_pass_fraction": val_core.get("pass_fraction")}

        # ---------------------------------------------------------------- 9. inclusion probabilities
        for group, _tag in elim.cleared:
            for p in group:
                prob[p] = min(prob.get(p, 1.0), P_CLEARED_GROUP)
        listed = {q for a in alt_out for q in a}
        for c in candidates:  # members of sufficient sets that are not in the core: alternative-only, or superseded (non-minimal)
            for p in c - core_set:
                prob[p] = P_ALTERNATIVE_ONLY if p in listed else P_CLEARED_GROUP
        for p in core:
            if p in elim.necessary or p in E or essential.get(p):
                prob[p] = P_NECESSARY_ESSENTIAL if essential.get(p) else P_NECESSARY
            elif core_set != suff | E:
                prob[p] = P_NECESSARY  # member of a completed, validated alternative elimination
            else:
                prob[p] = untested_p(p)
        # stability of the SAME mechanism across randomized elimination orders (runs that share members with the core; runs that
        # found a disjoint set found another mechanism and are reported as alternatives instead)
        # (members found by the essential screen keep their evidence-class probability: they are core by full-network silencing)
        same = [s for s in [suff] + restart_sets if s & core_set]
        if len(same) >= 2:
            for p in (set().union(*same) | core_set) - E:
                freq = sum(1 for s in same if p in s) / len(same)
                prob[p] = 0.5 * prob.get(p, 0.5) + 0.5 * (0.02 + 0.93 * freq)
        prob = {int(p): float(min(1.0, max(0.0, q))) for p, q in prob.items()}

        # ---------------------------------------------------------------- 10. roles, loop, motif, predictions
        extra_roles = {p: "redundant_backup" for alt in alt_out for p in alt if p not in core_set}
        roles, loop, motif = infer_roles(problem, core, extra=extra_roles)
        preserved = fid.get("keep_only_pass_fraction")
        if preserved is None:
            preserved = fid.get("keep_only_pass_fraction_search_seeds")
        diag["oracle"] = {"tests": oracle.n_tests, "calls_by_phase": oracle.calls_by_phase, "budget_exhausted": not elim.complete}
        return DiscoveryResult(core=core, inclusion_probability=prob, roles=roles, essential=essential, alternatives=alt_out, loop=loop,
                               predicted_frequency_hz=fid.get("frequency_hz"), predicted_n_active_readout=fid.get("n_active_readout"),
                               predicted_function_preserved=None if preserved is None else bool(preserved >= 0.5), fidelity=fid,
                               budget={**sim.report(), "wall_s": round(time.time() - t0, 1)}, diagnostics=diag, motif=motif)

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _elim_summary(elim: Elimination, oracle: Oracle) -> dict:
        counts: dict[str, int] = {}
        for _g, tag in elim.cleared:
            counts[tag] = counts.get(tag, 0) + 1
        return {"final_size": len(elim.kept), "complete": elim.complete, "n_cleared_groups": counts, "n_necessary_confirmed": len(elim.necessary),
                "calls": int(oracle.calls_by_phase.get(oracle.phase, 0)), "trace_len": len(elim.trace),
                "trace_head": [list(t) for t in elim.trace[:40]]}

    @staticmethod
    def _validate(oracle: Oracle, U: frozenset[int], core: frozenset[int], first_seed: int, n_val: int) -> dict:
        """Keep-only of the core on fresh seeds; a failing seed only counts when the intact network passes on it."""
        res: dict = {"seeds": [], "passed": [], "genuine": 0, "pass_fraction": None, "failing_seeds": [], "discarded_seeds": []}
        try:
            s = first_seed
            extra = 0
            while len(res["seeds"]) < n_val and extra <= n_val:
                o = oracle.run(core, s)
                if o.passed:
                    res["seeds"].append(s)
                    res["passed"].append(True)
                else:
                    oi = oracle.run(U, s)
                    if oi.passed:
                        res["seeds"].append(s)
                        res["passed"].append(False)
                        res["failing_seeds"].append(s)
                    else:
                        res["discarded_seeds"].append(s)
                        extra += 1
                s += 1
        except _OutOfBudget:
            pass
        res["genuine"] = len(res["seeds"])
        if res["genuine"]:
            res["pass_fraction"] = float(np.mean(res["passed"]))
        return res

    @staticmethod
    def _stress(oracle: Oracle, core: frozenset[int], seeds: tuple[int, ...], n_probes: int, noise_sd: float) -> dict:
        """Keep-only of ``core`` under widened parameter distributions (sd x2) and multiplicative weight noise."""
        cfg = oracle.problem.model_cfg
        wide = {"tau_sd": cfg.tau_sd * 2, "a_sd": cfg.a_sd * 2, "theta_sd": cfg.theta_sd * 2, "r_max_sd": cfg.r_max_sd * 2}
        outs = [oracle.run(core, s, cfg_override=wide, noise_sd=noise_sd) for s in list(seeds)[:max(1, n_probes)]]
        return {"pass_fraction": float(np.mean([o.passed for o in outs])), "score": float(np.mean([o.score for o in outs])), "n": len(outs)}

    @staticmethod
    def _fidelity(oracle: Oracle, core: frozenset[int], seeds: tuple[int, ...], val: dict, stress: dict | None) -> dict:
        outs: list[Outcome] = []
        search_outs: list[Outcome] = []
        for s in list(seeds) + list(val.get("seeds", [])):
            o = oracle.outcomes.get((core, int(s), (), 0.0))
            if o is None:
                try:
                    o = oracle.run(core, s)
                except _OutOfBudget:
                    continue
            outs.append(o)
            if s in seeds:
                search_outs.append(o)
        fid: dict = {"keep_only_pass_fraction": val.get("pass_fraction"),
                     "keep_only_pass_fraction_search_seeds": float(np.mean([o.passed for o in search_outs])) if search_outs else None,
                     "keep_only_score_mean": float(np.mean([o.score for o in outs])) if outs else None,
                     "stress_pass_fraction": None if stress is None else stress["pass_fraction"], "n_seeds": len(outs), "core_size": len(core)}
        freqs = [o.frequency_hz for o in outs if o.passed and o.frequency_hz is not None]
        fid["frequency_hz"] = float(np.median(freqs)) if freqs else None
        nar = [o.n_active_readout for o in outs if o.passed]
        fid["n_active_readout"] = int(np.median(nar)) if nar else None
        return fid

    def _empty(self, problem: DiscoveryProblem, sim: BudgetedSimulator, t0: float, diag: dict, reason: str, U: frozenset[int]) -> DiscoveryResult:
        diag["error"] = reason
        return DiscoveryResult(core=[], inclusion_probability={int(p): 0.0 for p in U}, roles={}, essential={}, alternatives=[], loop=[],
                               predicted_function_preserved=False, fidelity={}, budget={**sim.report(), "wall_s": round(time.time() - t0, 1)},
                               diagnostics=diag, motif=None)
