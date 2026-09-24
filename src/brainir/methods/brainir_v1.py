"""brainir_v1 — order-invariant canonical group elimination, enumerated alternatives and an admissibility-first causal selection
(version 1.1).

BrainIR v1 is ONE algorithm (research/phase2/BRAINIR_V1_METHOD.md has the formulation, the evidence behind every component, the
experiments, and what version 1.1 changed after reviews A and G). Objective: return the mechanism the INTACT network uses — a set
M that is

 (i)   sufficient: keep-only of M passes the functional criterion on the parameter replicates on which the intact network passes,
       validated sequentially until the posterior of that pass rate is decisive about 1/2 (else "undecided");
 (ii)  admissible: every member participates in the intact network (graded activity in the analysis window above a threshold
       relative to the network's own mechanism, or a positive necessity verdict), and M contains every neuron whose single
       silencing breaks the intact function, wherever in the run it was measured (measured necessity is a hard constraint);
 (iii) faithful: its keep-only dynamics reproduce the intact network's readout statistics on the same replicates as well as any
       other admissible candidate, within noise (paired test) — checked before size;
 (iv)  used: no other remaining candidate is relied on decisively more by the intact network (paired test on the readout change
       caused by silencing each candidate's distinctive members, per member, at every size); then the simplest; then the most
       robust; a key inside its noise band is a tie and the tied sets share the probability mass;
 (v)   independent of the node order and of arbitrary search choices.

Pipeline (every simulation goes through the given BudgetedSimulator; ``default_config`` switches every component):

 1. Working seeds: parameter replicates on which the intact network performs the function; graded activity profile of the
    intact network (mean / peak rate of every neuron in the analysis window).
 2. Restriction (exact under the rate model): candidates must be reachable from the stimulus through excitatory edges and must
    reach the readout; neurons silent in every intact run are removed as one group, verified by one decision.
 3. Canonical order: a permutation-equivariant structural relevance, ties broken by weighted degree; no random order anywhere.
 4. Group elimination over keep-only sets (adaptive group testing, bisection, activity queue, 1-minimality rounds); every decision
    is a sequential strict majority over the working seeds, extended when they disagree (adaptive replication).
 5. Sequential validation on fresh seeds; add-back re-run if it fails.
 6. Necessity in the full network: a pooled single-silencing test of every canonical member; a screen of the other active
    candidates that cannot be fooled by masking — single silencing of the flagged gates (active inhibitory candidates that project
    onto the core, or onto a silent neuron with a path to the readout that their inhibition holds down against active excitation) and
    of the most relevant ones, then group silencing in two independent partitions (a neuron is cleared only if both of its groups pass).
 7. Alternatives, enumerated deterministically (disjoint sets, per-member replacements); every member of every alternative gets
    the pooled single-silencing test. Every candidate is completed with every neuron found essential anywhere.
 8. Admissibility-first selection (validated, participating, faithful), then reliance, Occam and robustness with paired tests;
    exchangeable copies that are each only marginally sufficient are merged when their union validates decisively better.
 9. Minimality certificate; degeneracy (no compact mechanism) and jointly necessary groups; final fidelity on reserved fresh
    seeds that the selection never saw (unconditional and conditional sufficiency, intact pass rate).
10. Uncertainty from the evidence counts: candidate weights from validation posteriors, participation and the confidence of the
    deciding comparison; member probabilities averaged over the candidates, with measured necessity as a floor and silent /
    cleared evidence as a ceiling; roles conditioned on the interventions; intervention predictions backed by simulations
    (single silencing, and removal of each member's strongest in-core edge), or abstention.
11. Cross-connectome (bundle with a network of another dataset): after the core is final and validated, it is carried to the
    other network from the same budget pool and verified there (brainir.discovery.joint); calibrated identity claims only for a
    verified, complete transfer; otherwise a role-level alignment only. It never changes the core.

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
from scipy.stats import beta as _beta_dist
from scipy.stats import t as _t_dist

from ..discovery.interface import GENERIC_ROLES, DiscoveryMethod, DiscoveryResult, MethodRegistry
from ..discovery.interventions import intact, keep_only, silence
from ..discovery.problem import DiscoveryProblem, same_animal
from ..discovery.simulator import BudgetedSimulator, BudgetExhausted, Outcome, SimQuery

P_MAX = 0.99             # no inclusion probability reaches 1: every verdict rests on finitely many replicates
P_UNTESTED = 0.60        # member of a passing set never tested individually (the budget ran out)
P_CLEARED = 0.03         # removed by a passing group / leave-one-out decision
P_SILENT = 0.01          # silent in every passing intact run (verified group removal)
P_STRUCTURAL = 0.002     # cannot influence the readout under the model
P_LATENT = 0.01          # weight factor of a candidate with a member that does not participate in the intact network
POINT_MODEL = "point"
PARTICIPATION_MIN_HZ = 0.05   # participation threshold: max(0.05 Hz, 1 % of the median rate of the canonical mechanism)
PARTICIPATION_REL = 0.01
PARTICIPATION_PEAK_FACTOR = 10.0  # ... or a peak rate in the analysis window of at least 10x that threshold (a transient member)
SEED_BLOCK = 300
SEED_BLOCKS = 16
WORK_OFF, MAX_SEED_TRIALS = 17, 80           # working replicates b+17 .. b+96
VAL_OFF, MAX_VALIDATION_SEEDS = 120, 80      # selection validation b+120 .. b+199 (also pooled into the necessity tests)
FID_OFF, MAX_FIDELITY_SEEDS = 200, 30        # final fidelity b+200 .. b+229 (never used by the selection)
STRESS_OFF, MAX_STRESS_PROBES = 230, 40      # stress probes b+230 .. b+269
"""Parameter-replicate seeds of one run live in a block of 300 seeds, b = (seed mod 16) x 300, with the offsets above: every seed the
method queries is below 5,000 (5,000 and above are reserved for independent scoring), below 1,000 at seed 0, and never in 1000-1015
(block 900 skips its offsets 100-119)."""


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


# ---------------------------------------------------------------------------- statistics of the evidence counts
def p_above_half(k: int, n: int) -> float:
    """Posterior probability that a pass (or fail) rate exceeds 1/2 after ``k`` of ``n`` replicates (uniform prior)."""
    return float(_beta_dist.sf(0.5, 1 + int(k), 1 + int(n) - int(k)))


def beta_interval(k: int, n: int, level: float = 0.9) -> list[float]:
    a, b = 1 + int(k), 1 + int(n) - int(k)
    return [round(float(_beta_dist.ppf((1 - level) / 2, a, b)), 4), round(float(_beta_dist.ppf(1 - (1 - level) / 2, a, b)), 4)]


def paired_confidence(diffs: Iterable[float], band: float = 0.0) -> tuple[float, float, int]:
    """(mean paired difference d, P(d > band), n) under a t model of the paired differences with n - 1 df; P(d < -band) = the same
    call on the negated differences. ``band`` is the noise band: a difference inside it is no evidence either way."""
    d = np.asarray([float(x) for x in diffs if x is not None and np.isfinite(x)], dtype=float)
    n = len(d)
    if n == 0:
        return 0.0, 0.5 if band <= 0 else 0.0, 0
    m = float(d.mean())
    if n < 2:
        return m, 0.5 if band <= 0 else 0.0, n
    sd = float(d.std(ddof=1))
    if sd <= 1e-12:
        return m, (1.0 if m - band > 1e-12 else 0.0 if m - band < -1e-12 else 0.5), n
    return m, float(_t_dist.cdf((m - band) / (sd / math.sqrt(n)), df=n - 1)), n


def binomial_confidence(ka: int, na: int, kb: int, nb: int) -> float:
    """P(rate_a > rate_b) for independent Beta(1 + k, 1 + n - k) posteriors (numerical, on a grid)."""
    x = np.linspace(0.0, 1.0, 2001)
    fa = _beta_dist.pdf(x, 1 + ka, 1 + na - ka)
    cb = _beta_dist.cdf(x, 1 + kb, 1 + nb - kb)
    y = fa * cb
    return float(min(1.0, max(0.0, np.sum((y[1:] + y[:-1]) * 0.5) * (x[1] - x[0]))))


def activity_profile(outs: list[Outcome], n: int) -> tuple[np.ndarray, np.ndarray]:
    """Mean over the given intact runs of every neuron's mean and peak rate in the analysis window (graded participation); runs
    without graded activity fall back to the binary activity (1 Hz where active)."""
    means, peaks = [], []
    for o in outs:
        if getattr(o, "mean_rate_hz", None) is not None:
            m = np.asarray(o.mean_rate_hz, dtype=float)
            pk = np.asarray(o.peak_rate_hz if getattr(o, "peak_rate_hz", None) is not None else o.mean_rate_hz, dtype=float)
        else:
            m = np.zeros(n)
            m[np.asarray(o.active_positions, dtype=np.int64)] = 1.0
            pk = m
        means.append(m)
        peaks.append(pk)
    if not means:
        return np.zeros(n), np.zeros(n)
    return np.mean(means, axis=0), np.mean(peaks, axis=0)


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

    def run(self, kept: frozenset[int], seed: int, cfg_override: dict | None = None, noise_sd: float = 0.0,
            remove_edges: tuple = ()) -> Outcome:
        """One simulation of the network ``kept`` (``remove_edges``: synapses (post, pre) removed on top, an edge intervention)."""
        edges = tuple(sorted((int(a), int(b)) for a, b in remove_edges))
        key = (kept, int(seed), tuple(sorted((cfg_override or {}).items())), float(noise_sd), edges)
        if key in self.outcomes:
            return self.outcomes[key]
        if self.sim.remaining - 1 < self.reserve:
            raise _OutOfBudget(f"{self.sim.remaining} calls left, {self.reserve} reserved")
        iv = self.intervention(kept, noise_sd, int(seed) if noise_sd > 0 else None)
        try:
            out = self.sim.run(SimQuery(iv, int(seed), t_end=self.t_end, cfg_override=dict(cfg_override or {}), remove_edges=edges))
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


# ---------------------------------------------------------------------------- the method
@MethodRegistry.register
class BrainIRv1(DiscoveryMethod):
    """BrainIR v1: order-invariant canonical group elimination with enumerated alternatives, admissibility-first causal selection
    (participation, measured necessity, dynamics fidelity; then reliance, Occam and robustness with paired tests), evidence-based
    uncertainty, simulated intervention predictions and verified cross-connectome transfer. See the module docstring."""

    name = "brainir_v1"
    version = "1.1"
    default_config = {
        # decisions
        "n_seeds_per_decision": 3,        # working seeds per accept/reject decision (sequential strict majority)
        "adaptive_replication": True,     # disagreeing seeds -> extend the decision to max_decision_seeds working seeds
        "max_decision_seeds": 5,
        "max_seed_trials": 10,            # intact runs tried to collect working seeds
        # validation: sequential until the posterior of the conditional pass rate is decisive about 1/2
        "validation_seeds": 3,            # intact-passing fresh seeds before a validation verdict is allowed
        "max_validation_seeds": 12,       # ... and at most this many (then "undecided")
        "fidelity_seeds": 4,              # intact-passing RESERVED fresh seeds for the final fidelity (never used by the selection)
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
        "member_essentiality": True,      # pooled single-silencing test of every canonical member (essential claims)
        "necessity_screen": True,         # screen of the other active candidates (context members)
        "necessity_screen_fraction": 0.4,  # call cap of the screen (share of the budget)
        "screen_singles": True,           # single silencing of flagged inhibitory and most relevant candidates before the group screen
        "screen_singles_fraction": 0.15,  # single silencing of the most relevant active candidates (share of the pool) ...
        "screen_min_singles": 4,          # ... at least this many, at most screen_singles_per_member per canonical member,
        "screen_singles_per_member": 4,   # ... plus every flagged gate
        "second_partition": True,         # members of passing groups are re-tested in an interleaved second partition
        "necessity_of_alternatives": True,  # pooled single-silencing test of every member of every alternative
        # alternatives and selection
        "max_alternatives": 4,
        "max_fillers_per_member": 2,
        "alternatives_budget_fraction": 0.5,
        "participation_check": True,      # a candidate with a member that does not participate in the intact network is a latent backup
        "fidelity_check": True,           # dynamics fidelity (paired, keep-only vs intact readout statistics) before size
        "reliance_tiebreak": True,        # the intact network's reliance on each candidate's distinctive members enters the selection
        "robust_objective": True,         # stress probes (sd x2 / weight noise) enter the selection
        "stress_probes": 4,
        "stress_noise_sd": 0.2,
        "stress_sd_factor": 2.0,
        "decisive": 0.95,                 # posterior probability that makes a paired key (fidelity, reliance, validation) decisive
        "decisive_stress": 0.99,          # stress probes are high-variance: only 4/4 against 0/4 is decisive
        "occam_factor": 0.5,              # prior odds per extra member when the evidence keys cannot separate two admissible sets
        "union_repair": True,             # exchangeable copies, each marginally sufficient, are merged when their union validates better
        "degeneracy_detection": True,     # no compact mechanism: all members replaceable one by one -> flagged, membership = frequency
        "joint_necessity": True,          # groups {member, its fillers} whose joint silencing breaks the function are reported
        # uncertainty and reporting
        "uncertainty_model": "posterior",  # "posterior" (evidence counts mixed over candidate mechanisms) or "point"
        "size_error_points": 3,
        "simulate_edge_predictions": True,  # edge-removal predictions backed by simulations (else abstain)
        "edge_prediction_members": 8,     # at most this many members (most relevant first) get a simulated edge prediction
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
@dataclass
class Screen:
    essential: dict[int, dict] = field(default_factory=dict)
    """neurons whose pooled single-silencing test failed (context members) -> the test."""
    singles: dict[int, bool] = field(default_factory=dict)
    """flagged / most relevant candidates silenced alone -> their first decision passed."""
    flagged: list[int] = field(default_factory=list)
    groups: list[list[int]] = field(default_factory=list)
    """passing groups of partition 1."""
    groups2: list[list[int]] = field(default_factory=list)
    """passing groups of partition 2 (members of partition-1 groups re-tested, interleaved by relevance rank)."""
    cleared: list[int] = field(default_factory=list)
    unscreened: list[int] = field(default_factory=list)
    complete: bool = True
    n_tests: int = 0


class _Run:
    def __init__(self, problem: DiscoveryProblem, sim: BudgetedSimulator, seed: int, cfg: dict):
        self.problem, self.sim, self.seed, self.cfg = problem, sim, seed, cfg
        self.t0 = time.time()
        self.U = frozenset(int(p) for p in problem.candidate_positions())
        self.prior = parse_prior(cfg.get("prior"), self.U)
        block = (int(seed) % SEED_BLOCKS) * SEED_BLOCK
        self.base = block + WORK_OFF
        self.val_first = block + VAL_OFF
        self.fid_first = block + FID_OFF
        self.stress_first = block + STRESS_OFF
        self.budget0 = int(sim.remaining)
        self.m = max(1, int(cfg["n_seeds_per_decision"]))
        self.M = max(self.m, int(cfg["max_decision_seeds"])) if cfg.get("adaptive_replication") else 0
        self.n_val = min(MAX_VALIDATION_SEEDS, max(1, int(cfg["validation_seeds"])))
        self.n_val_max = min(MAX_VALIDATION_SEEDS, max(self.n_val, int(cfg.get("max_validation_seeds", self.n_val))))
        self.n_fid = min(MAX_FIDELITY_SEEDS, max(1, int(cfg.get("fidelity_seeds", 4))))
        self.D = float(cfg.get("decisive", 0.95))
        self.DS = float(cfg.get("decisive_stress", 0.99))
        self.fin_reserve = int(min(2 * self.n_fid + 2, max(0, self.budget0 // 10)))
        self.prober = Prober(problem, sim, self.U, base_seed=self.base,
                             max_seed_trials=min(MAX_SEED_TRIALS, max(int(cfg["max_seed_trials"]), self.m, self.M)), t_end=cfg.get("t_end"))
        self.diag: dict = {"phases": [], "n_candidates": len(self.U), "seed": seed, "budget": self.budget0, "prior_used": self.prior is not None,
                           "config": {k: v for k, v in cfg.items() if k != "prior"}, "flags": []}
        self.prob: dict[int, float] = {}
        self.ess_tests: dict[int, dict] = {}
        self.cleared_all: set[int] = set()
        self.silent_set: frozenset[int] = frozenset()
        self.structural_out: frozenset[int] = frozenset()
        self.elims: dict[frozenset[int], Elimination] = {}
        self.repl_tried: set[int] = set()
        self.part_thr = PARTICIPATION_MIN_HZ
        n = int(problem.n)
        self.rates, self.peaks = np.zeros(n), np.zeros(n)

    # ------------------------------------------------------------------ helpers
    def phase(self, name: str, reserve: int) -> None:
        self.prober.phase = name
        self.prober.reserve = max(0, min(int(reserve), max(0, self.sim.remaining - 1)))
        self.diag["phases"].append({"name": name, "remaining_at_start": int(self.sim.remaining), "reserve": self.prober.reserve})

    def decide(self, S: frozenset[int], seeds: tuple[int, ...] | None = None) -> Decision:
        return self.prober.decide(S, self.seeds if seeds is None else seeds, self.M)

    def flag(self, name: str) -> None:
        if name not in self.diag["flags"]:
            self.diag["flags"].append(name)

    def necessity(self, x: int) -> tuple[bool, dict]:
        """Pooled single-silencing test: is silencing ``x`` alone in the intact network destructive (sigma({x}) < 1/2)? Every working
        replicate is run (no early stop), a split is extended (adaptive replication), and the verdict pools these replicates with the
        fresh validation replicates on which the intact network passes: essential iff more than half of the pooled replicates fail.
        The posterior probability that the failure rate exceeds 1/2 is kept as the evidence (a floor of the inclusion probability)."""
        if x in self.ess_tests:
            t = self.ess_tests[x]
            return bool(t["essential"]), t
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
        info = {"essential": bool(n and n_fail * 2 > n), "pass_fraction_silenced": round(1.0 - n_fail / n, 3) if n else None, "n_seeds": int(n),
                "n_fail": int(n_fail), "n_fresh": int(fresh), "p_essential": round(p_above_half(n_fail, n), 4) if n else None}
        self.ess_tests[x] = info
        return bool(info["essential"]), info

    def essential_set(self) -> frozenset[int]:
        return frozenset(p for p, t in self.ess_tests.items() if t["essential"])

    def participates(self, p: int) -> bool:
        """Graded participation in the intact network: mean rate in the analysis window above the threshold, or a transient peak of
        at least 10x the threshold, or a positive necessity verdict (a member whose silencing breaks the function is used, whatever
        its rate in the window)."""
        t = self.ess_tests.get(p)
        if t and t["essential"]:
            return True
        return bool(self.rates[p] >= self.part_thr or self.peaks[p] >= PARTICIPATION_PEAK_FACTOR * self.part_thr)

    def validate(self, S: frozenset[int], *, adaptive: bool = True, n_min: int | None = None) -> dict:
        """Keep-only of ``S`` on the selection's fresh validation seeds on which the intact network passes (the intact run of each seed is
        shared by every candidate; a seed on which the intact network fails cannot tell and is only counted in the intact pass rate).
        Sequential: after ``n_min`` intact-passing seeds, stop once the posterior of the conditional pass rate (keep-only passes given
        that the intact network passes) is decisive about 1/2, or at ``max_validation_seeds`` (then "undecided"). The unconditional
        sufficiency is measured by the final fidelity on reserved seeds."""
        n_min = self.n_val if n_min is None else int(n_min)
        n_max = self.n_val_max if adaptive else n_min
        recs: list[tuple[int, bool, bool | None]] = []
        outs: dict[int, Outcome] = {}
        iouts: dict[int, Outcome] = {}
        k_c = n_c = 0
        s = self.val_first
        try:
            while s < self.val_first + MAX_VALIDATION_SEEDS:
                if n_c >= n_min:
                    pv = p_above_half(k_c, n_c)
                    if pv >= self.D or pv <= 1.0 - self.D or n_c >= n_max:
                        break
                oi = self.prober.run(self.U, s)
                iouts[s] = oi
                if oi.passed:
                    o = oi if S == self.U else self.prober.run(S, s)
                    outs[s] = o
                    recs.append((s, True, bool(o.passed)))
                    n_c += 1
                    k_c += int(o.passed)
                else:
                    recs.append((s, False, None))
                s += 1
        except _OutOfBudget:
            pass
        n_all = len(recs)
        pv = p_above_half(k_c, n_c) if n_c else 0.5
        status = "validated" if n_c and pv >= self.D else "failed" if n_c and pv <= 1.0 - self.D else "undecided"
        return {"seeds": [r[0] for r in recs], "intact_passed": [r[1] for r in recs], "passed": [r[2] for r in recs],
                "k": k_c, "n": n_c, "pass_fraction": (k_c / n_c) if n_c else None,
                "intact_pass_fraction": (sum(1 for r in recs if r[1]) / n_all) if n_all else None,
                "p_valid": round(pv, 4), "status": status, "ci90": beta_interval(k_c, n_c) if n_c else None,
                "failing_seeds": [r[0] for r in recs if r[1] and not r[2]], "outcomes": outs, "intact_outcomes": iouts}

    def mismatch(self, v: dict) -> dict[int, float]:
        """Per validation replicate on which both the intact network and keep-only of the candidate pass: the mean relative difference of
        the readout statistics (criterion score, rates, frequency, criterion-specific means) between them (dynamics fidelity)."""
        out = {}
        for s, ip, kp in zip(v.get("seeds", []), v.get("intact_passed", []), v.get("passed", [])):
            if ip and kp:
                out[s] = readout_change(v["intact_outcomes"][s], v["outcomes"][s])
        return out

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
        return {"stress": float(np.mean([o.passed for o in allo])) if allo else None, "stress_k": int(sum(o.passed for o in allo)), "stress_n": len(allo),
                "stress_wide": float(np.mean([o.passed for o in outs_w])) if outs_w else None,
                "stress_noise": float(np.mean([o.passed for o in outs_n])) if outs_n else None}

    def intact_passing_validation_seeds(self, k: int, exclude: Iterable[int] = ()) -> list[int]:
        """The first ``k`` validation seeds on which the intact network passes (intact runs shared with the validations), skipping
        ``exclude``; at most the first 2 x max_validation_seeds validation seeds are tried."""
        out: list[int] = []
        ex = set(int(x) for x in exclude)
        s = self.val_first
        try:
            while len(out) < k and s < self.val_first + min(MAX_VALIDATION_SEEDS, 2 * self.n_val_max):
                if s not in ex and self.prober.run(self.U, s).passed:
                    out.append(s)
                s += 1
        except _OutOfBudget:
            pass
        return out

    def noise_band(self) -> float:
        """The noise band of a paired difference of two readout-change statistics: sqrt(2) x the intact network's own between-draw
        variability of the readout statistics (the median relative readout change between two intact-passing parameter replicates, over
        12 of them: the working seeds and intact-passing validation seeds, simulated if needed). Each candidate's dynamics mismatch or
        reliance varies from draw to draw on that scale, their difference on sqrt(2) times it; a difference inside the band is a tie,
        not a decision."""
        if getattr(self, "_band", None) is None:
            n_band = 12
            outs: list[Outcome] = []
            try:  # the working seeds' intact runs are cached (an add-back seed is a validation seed: also cached)
                outs = [o for o in (self.prober.run(self.U, s) for s in self.seeds) if o.passed]
            except _OutOfBudget:
                pass
            for s in self.intact_passing_validation_seeds(n_band - len(outs), exclude=self.seeds):
                outs.append(self.prober.run(self.U, s))
            outs = outs[:n_band]
            d = [readout_change(a, b) for i, a in enumerate(outs) for b in outs[i + 1:]]
            between = float(np.median(d)) if len(d) >= 3 else 0.0
            self._band = math.sqrt(2.0) * between
            self.diag["noise_band"] = {"readout_change_between_draws": round(between, 4), "band": round(self._band, 4), "n_intact_outcomes": len(outs)}
        return self._band

    def gray(self, conf: float) -> bool:
        """A paired key whose posterior is neither decisive for nor decisive against: more replicates are needed."""
        return 1.0 - self.D < conf < self.D

    def cand_rank(self, c: frozenset[int]) -> tuple:
        """Canonical tie-break between candidate sets (node-order independent up to exact automorphisms)."""
        return tuple(sorted((self.key[p] for p in c), reverse=True))

    # ------------------------------------------------------------------ the pipeline
    def execute(self) -> DiscoveryResult:
        cfg, prober, diag, U = self.cfg, self.prober, self.diag, self.U
        # ---------------------------------------------------------------- 1. working seeds, graded activity
        self.phase("seeds", min(self.n_val + 2, self.budget0 // 3))
        try:
            prober.collect_working(self.m)
        except _OutOfBudget:
            pass
        diag["seeds"] = {"tried": list(prober.tried), "working": list(prober.working)}
        if not prober.working:
            return self.empty("the intact network did not perform the function on any tried seed")
        self.seeds = tuple(prober.working[: self.m])
        self.rates, self.peaks = activity_profile([prober.intact_outcomes[s] for s in prober.working], int(self.problem.n))
        for p in U:
            self.prob[p] = P_UNTESTED
        # ---------------------------------------------------------------- 2. restriction
        self.phase("restriction", self.n_val + 2)
        if cfg["structural_pruning"]:
            K_struct, dropped = structural_candidates(self.problem)
        else:
            K_struct, dropped = U, frozenset()
        self.structural_out = frozenset(dropped)
        for p in dropped:
            self.prob[p] = P_STRUCTURAL
        self.up = _reach(self.problem.W.tocsr(), self.problem.readout_positions)
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
                    self.silent_set = silent
                    for p in silent:
                        self.prob[p] = P_SILENT
            except _OutOfBudget:
                pass
        self.K0 = K0
        self.K_struct = K_struct
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
        if (val["status"] == "failed" and val["failing_seeds"] and elim.complete and self.sim.remaining > 0.2 * self.budget0):
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
        self.elims[M1] = elim
        for group, _tag in elim.cleared:
            self.cleared_all.update(group)
        # participation threshold relative to the network's own (canonical) mechanism
        ref = [float(self.rates[p]) for p in M1 if self.rates[p] >= PARTICIPATION_MIN_HZ]
        if not ref:
            ref = [float(self.rates[p]) for p in K0 if self.rates[p] >= PARTICIPATION_MIN_HZ]
        self.part_thr = max(PARTICIPATION_MIN_HZ, PARTICIPATION_REL * (float(np.median(ref)) if ref else 0.0))
        diag["participation"] = {"threshold_hz": round(self.part_thr, 4), "reference": "median intact mean rate of the canonical mechanism",
                                 "canonical_member_rates_hz": {int(p): round(float(self.rates[p]), 4) for p in sorted(M1)}}
        # ---------------------------------------------------------------- 6. necessity in the full network
        if cfg["member_essentiality"]:
            self.phase("essentiality", self.fin_reserve)
            with guarded(diag, "essentiality"):
                for p in sorted(M1, key=lambda q: key[q], reverse=True):
                    self.necessity(p)
        screen = Screen()
        if cfg["necessity_screen"] and M1:
            self.phase("necessity_screen", self.fin_reserve + 2)
            pool = sorted(K0 - M1, key=lambda q: (key[q], q), reverse=True)  # most relevant first
            with guarded(diag, "necessity_screen"):
                screen = self.screen(pool, M1)
            diag["necessity_screen"] = {"pool": len(pool), "found": sorted(screen.essential), "flagged_inhibitory": sorted(screen.flagged),
                                        "singles": {int(k): v for k, v in screen.singles.items()},
                                        "partition1_groups": screen.groups, "partition2_groups": screen.groups2,
                                        "cleared": sorted(screen.cleared), "unscreened": sorted(screen.unscreened), "complete": screen.complete,
                                        "tests": screen.n_tests, "calls": int(prober.calls_by_phase.get("necessity_screen", 0))}
        self.screen_res = screen
        # ---------------------------------------------------------------- 7. alternatives (deterministic enumeration) + their necessity
        alts, alt_info = self.alternatives(M1)
        diag["alternatives"] = alt_info
        if cfg["necessity_of_alternatives"] and cfg["member_essentiality"] and alts:
            self.phase("essentiality_alternatives", self.fin_reserve + 2)
            with guarded(diag, "essentiality_alternatives"):
                todo = sorted({p for a in alts for p in a if p not in self.ess_tests}, key=lambda q: (not self.participates(q), tuple(-x for x in key[q])))
                for p in todo:
                    self.necessity(p)
        Ess = self.essential_set()
        # ---------------------------------------------------------------- 8. candidates, admissibility-first selection
        cands: list[frozenset[int]] = [M1 | Ess]
        kinds: list[str] = ["canonical"]
        self.alt_of: dict[frozenset[int], frozenset[int]] = {M1 | Ess: M1}
        for a, info in zip(alts, alt_info):
            c = a | Ess
            if c not in cands:
                cands.append(c)
                kinds.append(info["kind"])
                self.alt_of[c] = a
        self.phase("selection", self.fin_reserve)
        sel = None
        with guarded(diag, "selection"):  # an unexpected failure of the selection must not discard the canonical mechanism
            sel = self.select(cands, kinds)
        if sel is None:
            self.flag("selection_failed")
            sel = {"ev": {c: {"kind": k} for c, k in zip(cands, kinds)}, "winner": cands[0], "tied": [], "losers": [], "filtered": {},
                   "not_minimal": [], "trace": [], "mode": "selection_failed"}
        winner = sel["winner"]
        # exchangeable copies, each only marginally sufficient: their union (subset of parameter draws)
        self.union_members: frozenset[int] = frozenset()
        if winner is not None and cfg["union_repair"]:
            with guarded(diag, "union_repair"):
                self.phase("union_repair", self.fin_reserve)
                winner = self.union_repair(winner, cands, kinds, sel)
        if winner is not None and cfg["member_essentiality"]:
            with guarded(diag, "essentiality_of_selected_core"):
                self.phase("essentiality", self.fin_reserve)
                for p in sorted(winner, key=lambda q: key[q], reverse=True):
                    self.necessity(p)
        # no compact mechanism (distributed drive)
        degenerate = None
        if winner is not None and cfg["degeneracy_detection"]:
            degenerate = self.degeneracy(winner, cands, kinds)
            if degenerate:
                diag["degenerate"] = degenerate
                for f in ("degenerate", "distributed", "no_compact_mechanism"):
                    self.flag(f)
        diag["selection"] = self.selection_diag(cands, kinds, sel, winner)
        core_set = winner if winner is not None else frozenset()
        # ---------------------------------------------------------------- 9. minimality certificate, joint necessity
        cert_info: dict = {}
        if cfg["minimality_cleanup"] and core_set and not degenerate:
            self.phase("minimality", self.fin_reserve)
            with guarded(diag, "minimality"):
                core_set, cert_info = self.certify(core_set)
        diag["minimality_certificate"] = cert_info
        self.cert_info = cert_info
        core = sorted(core_set)
        diag["participation"].update(core_member_rates_hz={int(p): round(float(self.rates[p]), 4) for p in core},
                                     core_participates=bool(all(self.participates(p) for p in core)))
        joint_groups: list[dict] = []
        if cfg["joint_necessity"] and core_set and not degenerate:
            with guarded(diag, "joint_necessity"):
                self.phase("joint_necessity", self.fin_reserve)
                joint_groups = self.joint_necessity(core_set, cands, kinds)
        diag["jointly_necessary"] = joint_groups
        # ---------------------------------------------------------------- 10. final fidelity (reserved seeds), size-error curve
        self.phase("fidelity", 0)
        fid: dict = {}
        with guarded(diag, "fidelity"):
            fid = self.final_fidelity(core_set, sel)
        if not fid:
            fid = {"core_size": len(core)}
        curve: list[dict] = []
        with guarded(diag, "size_error_curve"):
            curve = self.size_error_curve(core_set, sel, cert_info)
        diag["size_error_curve"] = curve
        # ---------------------------------------------------------------- 11. probabilities, roles, predictions
        self.probabilities(core_set, cands, sel, degenerate)
        diag["posterior"] = getattr(self, "weights", None)
        ev = sel["ev"]
        comp_alts = [c for c in sel["tied"]] + [c for c, _k, _c in sel["losers"]]
        alt_out = [sorted(c) for c in comp_alts if c != core_set]
        extra_roles: dict[int, str] = {}
        for c in comp_alts:
            if c == core_set or not ev.get(c, {}).get("participating", True):
                continue
            for p in sorted(c - core_set):
                t = self.ess_tests.get(p)
                if not (t and t["essential"]):
                    extra_roles[p] = "redundant_backup"  # a non-essential member of a validated, participating replacement
        roles, loop, motif = infer_roles(self.problem, core, extra=extra_roles)
        roles = {p: (r, round(float(min(q, self.prob.get(p, q))), 4)) for p, (r, q) in roles.items()}
        essential_out: dict[int, bool | None] = {p: (self.ess_tests[p]["essential"] if p in self.ess_tests else None) for p in core}
        for p, t in sorted(self.ess_tests.items()):
            essential_out.setdefault(int(p), bool(t["essential"]))
        diag["essential_tests"] = {int(p): {k: v for k, v in t.items()} for p, t in sorted(self.ess_tests.items())}
        with guarded(diag, "intervention_predictions"):
            self.phase("edge_predictions", 0)
            diag["intervention_predictions"] = self.edge_predictions(core_set)
        diag.setdefault("intervention_predictions", [])
        diag["latent_backups"] = [{"members": sorted(c), "silent_members": ev[c].get("silent_members", []), "kind": k}
                                  for c, k in zip(cands, kinds) if not ev.get(c, {}).get("participating", True)]
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

    # ------------------------------------------------------------------ 6. necessity screen (robust to masking)
    def priority_singles(self, pool: list[int], M1: frozenset[int]) -> tuple[list[int], list[int]]:
        """(flagged gates, singles to test in relevance order). Flagged: an active inhibitory candidate q with an edge onto a canonical
        member, or onto a HELD-DOWN neuron x — silent in the intact network, with a path to the readout (or a readout neuron), whose
        mean input from the active network (intact mean rates, the model's synaptic scale) is below its mean firing threshold but would
        exceed it without q's inhibition: the signature of a gate whose silencing releases something (a group that also silences what
        drives x would mask it). Plus the most relevant active candidates: 15 % of the pool, at least 4, at most 4 per canonical member
        (the neighbourhood of a compact mechanism does not grow with the network)."""
        if not self.cfg.get("screen_singles", True):
            return [], []
        W = self.problem.W.tocsr()   # row x = inputs of x
        Wc = self.problem.W.tocsc()  # column q = outputs of q
        signs = self.problem.signs
        core = set(int(p) for p in M1)
        r = np.asarray(self.rates, dtype=float)
        mc = self.problem.model_cfg
        b_exc, b_inh = float(mc.b_exc), float(mc.b_inh)
        scale = np.ones(int(self.problem.n))
        sizes = getattr(self.problem, "sizes", None)
        if getattr(mc, "size_scaling", False) and sizes is not None:  # the model's threshold scaling by relative neuron size
            sz = np.asarray(sizes, dtype=float).copy()
            med = float(np.nanmedian(sz)) if np.isfinite(sz).any() else 1.0
            sz[~np.isfinite(sz) | (sz == 0)] = med
            scale = sz / med if med > 0 else scale
        theta = float(mc.theta_mean) * scale
        stim = {int(s) for s in self.problem.stim_positions}
        readout = {int(x) for x in self.problem.readout_positions}
        # silent neurons that act directly on the mechanism: readout neurons, or neurons with an edge onto a canonical member or a readout neuron
        silent = {int(x) for x in np.flatnonzero(r < self.part_thr) if int(x) not in stim
                  and (int(x) in readout or ({int(y) for y in Wc.indices[Wc.indptr[x]:Wc.indptr[x + 1]]} - {int(x)}) & (core | readout))}
        held: dict[int, float] = {}
        for x in silent:  # mean input of each silent neuron from the active network, below its mean threshold
            w = W.data[W.indptr[x]:W.indptr[x + 1]]
            u = float(np.sum(np.where(w > 0, b_exc, b_inh) * w * r[W.indices[W.indptr[x]:W.indptr[x + 1]]]))
            if u <= theta[x] and np.any(w < 0):
                held[x] = u
        flagged = []
        for q in pool:
            if int(signs[q]) >= 0 or not self.participates(q):
                continue
            for x, w in zip(Wc.indices[Wc.indptr[q]:Wc.indptr[q + 1]], Wc.data[Wc.indptr[q]:Wc.indptr[q + 1]]):
                x = int(x)
                if x == q:
                    continue
                u = held.get(x)
                if x in core or (u is not None and w < 0 and u + b_inh * abs(float(w)) * r[q] > theta[x]):
                    flagged.append(int(q))
                    break
        k = max(int(self.cfg["screen_min_singles"]), min(int(math.ceil(float(self.cfg["screen_singles_fraction"]) * len(pool))),
                                                         int(self.cfg.get("screen_singles_per_member", 4)) * len(M1)))
        top = [q for q in pool if self.participates(q)][:min(len(pool), k)]
        rank = {q: i for i, q in enumerate(pool)}
        self.diag["screen_held_down"] = len(held)
        return flagged, sorted(set(flagged) | set(top), key=lambda q: rank[q])

    def screen(self, pool: list[int], M1: frozenset[int]) -> Screen:
        """Necessity screen of the active candidates outside the canonical set. A passing group silenced together does not prove that
        each member is individually unnecessary (a gate silenced with the excitation it gates, a competitor silenced with its
        suppressor): (1) the flagged and the most relevant candidates are silenced alone; (2) the rest is group-silenced (failing groups
        bisected down to single neurons, confirmed by the pooled test); (3) the members of every passing group of more than one neuron
        are re-tested in a second partition interleaved by relevance rank, so that neighbours in the structural order (a gate and its
        drivers) fall into different groups; a neuron is cleared only if both of its groups passed."""
        res = Screen()
        prober = self.prober
        cap = int(float(self.cfg["necessity_screen_fraction"]) * self.budget0)
        calls0 = prober.calls_by_phase.get(prober.phase, 0)

        def check() -> None:
            if prober.calls_by_phase.get(prober.phase, 0) - calls0 >= cap:
                raise _OutOfBudget("necessity screen call cap")

        flagged, singles = self.priority_singles(pool, M1)
        res.flagged = flagged
        pending = list(pool)
        try:
            for q in singles:
                check()
                res.n_tests += 1
                d = prober.decide(self.U - {q}, self.seeds, self.M)
                if not d.passed:
                    ok, info = self.necessity(q)
                    if ok:
                        res.essential[q] = info
                res.singles[q] = bool(d.passed)
                pending.remove(q)
            rest = list(pending)
            groups1 = self._group_screen(rest, res, check)
            res.groups = groups1
            multi = [g for g in groups1 if len(g) > 1]
            if self.cfg["second_partition"] and multi:
                rank = {q: i for i, q in enumerate(pool)}
                tent = sorted({p for g in multi for p in g}, key=lambda q: rank[q])
                g = max(2, len(multi))
                order2 = [tent[i] for r in range(g) for i in range(r, len(tent), g)]
                groups2 = self._group_screen(order2, res, check)
                res.groups2 = groups2
                cleared2 = {p for grp in groups2 for p in grp}
                res.cleared = sorted({p for grp in groups1 if len(grp) == 1 for p in grp} | cleared2)
            else:
                res.cleared = sorted({p for grp in groups1 for p in grp})
            pending = []
        except _OutOfBudget:
            res.complete = False
        tested = set(res.singles) | set(res.essential) | set(res.cleared)
        res.unscreened = [q for q in pool if q not in tested]
        self.cleared_all.update(q for q, passed in res.singles.items() if passed)
        self.cleared_all.update(res.cleared)
        return res

    def _group_screen(self, items: list[int], res: Screen, check) -> list[list[int]]:
        """Adaptive group silencing (non-cumulative) in the given order; failing groups are bisected, both halves tested, down to single
        neurons whose pooled test decides; returns the passing groups."""
        U, prober = self.U, self.prober
        unresolved = list(items)
        chunk = max(1, int(round(len(unresolved) * float(self.cfg["initial_chunk_fraction"]))))
        passed: list[list[int]] = []

        def dec(X: list[int]) -> Decision:
            res.n_tests += 1
            return prober.decide(U - frozenset(X), self.seeds, self.M)

        while unresolved:
            check()
            take = min(chunk, len(unresolved))
            X = unresolved[:take]
            unresolved = unresolved[take:]
            if dec(X).passed:
                passed.append(sorted(X))
                chunk = min(max(1, len(unresolved)), chunk * 2)
                continue
            while len(X) > 1:
                check()
                h = len(X) // 2
                X1, X2 = X[:h], X[h:]
                if not dec(X1).passed:
                    unresolved = X2 + unresolved
                    X = X1
                    continue
                passed.append(sorted(X1))
                if not dec(X2).passed:
                    X = X2
                    continue
                passed.append(sorted(X2))  # synergy only: neither half alone breaks the function
                X = []
                break
            if len(X) == 1:
                ok, info = self.necessity(X[0])
                if ok:
                    res.essential[X[0]] = info
                else:
                    passed.append([X[0]])
            chunk = max(1, chunk // 2)
        return passed

    # ------------------------------------------------------------------ 7. alternatives
    def alternatives(self, M1: frozenset[int]) -> tuple[list[frozenset[int]], list[dict]]:
        cfg, prober, U, K0 = self.cfg, self.prober, self.U, self.K0
        n_max = int(cfg["max_alternatives"])
        found: list[frozenset[int]] = []
        info: list[dict] = []
        if n_max <= 0 or not M1 or not self.elim.complete:
            return found, info
        n_stress = int(cfg["stress_probes"]) if cfg["robust_objective"] else 0
        eval_reserve = (n_max + 1) * (self.n_val + n_stress + self.m) + 2 + self.fin_reserve
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
                    self.elims[e.kept] = e
                    info.append({"kind": "disjoint", "members": sorted(e.kept), "calls": self.sim.calls})
                rest = rest - e.kept
            # replacement fillers of every non-essential member (hitting-set enumeration of the slot); a filler may be silent in the
            # intact network (then the set does not participate and is reported as a latent backup, never as the mechanism)
            for p in sorted(M1, key=lambda q: self.key[q], reverse=True):
                t = self.ess_tests.get(p)
                if not t or t["essential"]:
                    continue
                self.repl_tried.add(p)
                excluded = {p}
                for _k in range(int(cfg["max_fillers_per_member"])):
                    if len(found) >= n_max:
                        break
                    start = K0 - frozenset(excluded)
                    if not self.decide(start).passed:
                        start = U - frozenset(excluded)
                        if not self.decide(start).passed:
                            break
                    e = run_elim(start, protected=M1 - frozenset(excluded))
                    if e is None or not e.kept:
                        break
                    new = e.kept - M1
                    if e.kept != M1 and e.kept not in found:
                        found.append(e.kept)
                        self.elims[e.kept] = e
                        info.append({"kind": f"replacement_for_{p}", "members": sorted(e.kept), "calls": self.sim.calls})
                    if not new:
                        break
                    excluded |= set(new)
        for e in list(self.elims.values()):
            for group, _tag in e.cleared:
                self.cleared_all.update(group)
        return found, info

    # ------------------------------------------------------------------ 8. selection
    def select(self, cands: list[frozenset[int]], kinds: list[str]) -> dict:
        """Admissibility before optimality. Every candidate is validated sequentially on the same fresh seeds and checked for
        participation. Admissible: validated and participating (if none is, the undecided participating ones, flagged; if none of those,
        no validated mechanism). Among the admissible minimal sets: dynamics fidelity (paired, keep-only against the intact network on
        the same seeds; candidates decisively worse than the best drop out); then pairwise, the canonical candidate first, a challenger
        replaces the incumbent only if it is decisively better on the first key that separates them — reliance of the intact network on
        the distinctive members (paired t, per member, every size), Occam, stress robustness; otherwise they tie."""
        cfg = self.cfg
        ev: dict[frozenset[int], dict] = {c: {"kind": k} for c, k in zip(cands, kinds)}
        out: dict = {"ev": ev, "winner": None, "tied": [], "losers": [], "filtered": {}, "not_minimal": [], "trace": [], "mode": "none"}
        if not cands:
            return out
        with guarded(self.diag, "selection_validation"):
            for c in cands:
                ev[c]["val"] = self.validate(c)
        use_part = bool(cfg["participation_check"])
        for c in cands:
            silent = sorted(p for p in c if not self.participates(p))
            ev[c]["silent_members"] = silent
            ev[c]["participating"] = (not silent) or not use_part

        def status(c: frozenset[int]) -> str:
            return (ev[c].get("val") or {}).get("status", "unvalidated")

        adm = [c for c in cands if status(c) == "validated" and ev[c]["participating"]]
        if len(adm) >= 2:  # paired keys need common replicates: every admissible candidate is validated on the same number of seeds
            n_eq = max(int(ev[c]["val"]["n"]) for c in adm)
            with guarded(self.diag, "selection_validation"):
                for c in adm:
                    if int(ev[c]["val"]["n"]) < n_eq:
                        ev[c]["val"] = self.validate(c, n_min=n_eq)
            adm = [c for c in cands if status(c) == "validated" and ev[c]["participating"]]
        mode = "validated"
        if not adm:
            adm = [c for c in cands if status(c) == "undecided" and ev[c]["participating"]]
            mode = "undecided" if adm else "none"
        out["mode"] = mode
        if mode == "undecided":
            self.flag("undecided")
        if not adm:
            self.flag("no_validated_mechanism")
            self.diag["no_validated_mechanism"] = True
            # the best available set is reported at low probability: participating first, then by validation evidence
            pool = sorted(cands, key=lambda c: (not ev[c]["participating"], -(ev[c].get("val") or {}).get("p_valid", 0.0), cands.index(c)))
            out["winner"] = pool[0]
            return out
        minimal = [c for c in adm if not any(o < c for o in adm)]
        out["not_minimal"] = [c for c in adm if c not in minimal]
        comp = minimal
        # fidelity before size: (1) conditional sufficiency on the same replicates (discordant replicates) and (2) dynamics — the relative
        # difference of the readout statistics from the intact network on the replicates where both candidates reproduce the function.
        # Sequential: while a comparison is neither decisive for nor against (gray), the best candidate and the gray ones are validated on
        # 4 more common replicates, up to the validation cap.
        if cfg["fidelity_check"] and len(comp) >= 2:
            for _round in range(4):
                mism = {c: self.mismatch(ev[c]["val"]) for c in comp}
                for c in comp:
                    ev[c]["mismatch"] = round(float(np.mean(list(mism[c].values()))), 4) if mism[c] else None
                    ev[c]["mismatch_per_seed"] = {int(x): round(float(v), 4) for x, v in mism[c].items()}
                best = min(comp, key=lambda c: (-(ev[c]["val"].get("pass_fraction") or 0.0), ev[c]["mismatch"] if ev[c]["mismatch"] is not None else 1.0,
                                                len(c), comp.index(c)))
                out["filtered"] = {}
                gray: list[frozenset[int]] = []
                for c in comp:
                    ev[c].pop("fidelity_vs_best", None)
                    if c == best:
                        continue
                    conf_s, n10, n01 = self.paired_validation(ev[best]["val"], ev[c]["val"])
                    common = sorted(set(mism[c]) & set(mism[best]))
                    m, conf_d, n = paired_confidence([mism[c][x] - mism[best][x] for x in common], band=self.noise_band())
                    ev[c]["fidelity_vs_best"] = {"sufficiency_discordant": [n10, n01], "confidence_less_sufficient": round(conf_s, 4),
                                                 "dynamics_mean_difference": round(m, 4), "confidence_worse_dynamics": round(conf_d, 4), "n": n,
                                                 "band": round(self.noise_band(), 4)}
                    conf = max(conf_s, conf_d if n >= 3 else 0.0)
                    if conf >= self.D:
                        out["filtered"][c] = conf
                    elif (n >= 3 and self.gray(conf_d)) or (n10 + n01 >= 1 and self.gray(conf_s)):
                        gray.append(c)
                n_now = max(int(ev[x]["val"]["n"]) for x in [best, *gray]) if gray else self.n_val_max
                if not gray or n_now >= self.n_val_max:
                    break
                n_next = min(self.n_val_max, n_now + 4)
                self.diag.setdefault("sequential_extensions", []).append({"key": "fidelity", "to_n": n_next, "candidates": 1 + len(gray)})
                with guarded(self.diag, "selection_validation"):
                    for x in [best, *gray]:
                        ev[x]["val"] = self.validate(x, n_min=n_next)
            comp = [c for c in comp if c not in out["filtered"]]
        # reliance and robustness among the remaining candidates
        if len(comp) >= 2:
            if cfg["reliance_tiebreak"]:
                with guarded(self.diag, "reliance"):
                    self.reliance(comp, ev)
            if cfg["robust_objective"]:
                with guarded(self.diag, "stress"):
                    for c in comp:
                        ev[c].update(self.stress(c))
        inc = comp[0]
        for c in comp[1:]:
            r, keyname, conf = self.compare(c, inc, ev)
            out["trace"].append({"challenger": sorted(c), "incumbent": sorted(inc), "result": r, "key": keyname,
                                 "confidence": None if conf is None else round(conf, 4)})
            if r > 0:
                inc = c
        for c in comp:
            if c == inc:
                continue
            r, keyname, conf = self.compare(inc, c, ev)
            if r > 0:
                out["losers"].append((c, keyname, conf))
            else:
                out["tied"].append(c)
        out["winner"] = inc
        # the winner is validated on the replicates of every participating candidate (paired weights), and on the full validation cap when
        # the intact network itself fails on some draws (the replicates on which the winner fails although the intact network works are
        # the union repair's evidence)
        intact_fails = any(not o.passed for o in self.prober.intact_outcomes.values()) or any(
            not ip for c in cands for ip in ((ev[c].get("val") or {}).get("intact_passed") or []))
        n_all = max([int((ev[c].get("val") or {}).get("n", 0)) for c in cands if ev[c]["participating"]]
                    + ([self.n_val_max] if intact_fails else []))
        if int(ev[inc]["val"]["n"]) < n_all:
            with guarded(self.diag, "selection_validation"):
                ev[inc]["val"] = self.validate(inc, n_min=n_all)
        return out

    def reliance(self, comp: list[frozenset[int]], ev: dict) -> None:
        """Per working replicate: (1[the function fails] + relative readout change) when the candidate's distinctive members (those not
        in every competing candidate) are silenced together in the intact network, per distinctive member (Occam-neutral), paired across
        candidates on the same replicates."""
        self.phase("reliance", self.fin_reserve)
        common = frozenset.intersection(*comp)
        rseeds = list(self.seeds)
        if self.M > len(rseeds):
            try:
                rseeds += [s for s in self.prober.collect_working(self.M) if s not in set(rseeds)][: self.M - len(rseeds)]
            except _OutOfBudget:
                pass
        dist = {c: c - common for c in comp if c - common}
        vals: dict[frozenset[int], list[float]] = {c: [] for c in dist}

        def measure(seeds: list[int]) -> None:  # replicate-major, so an exhausted budget leaves equal-length lists
            for s in seeds:
                row = {}
                for c, D in dist.items():
                    o0 = self.prober.run(self.U, s)
                    o = self.prober.run(self.U - D, s)
                    row[c] = ((0.0 if o.passed else 1.0) + readout_change(o0, o)) / len(D)
                for c, x in row.items():
                    vals[c].append(x)

        def any_gray() -> bool:
            cs = list(vals)
            for i, a in enumerate(cs):
                for b in cs[i + 1:]:
                    d = [x - y for x, y in zip(vals[a], vals[b])]
                    if len(d) >= 3 and (self.gray(paired_confidence(d, band=self.noise_band())[1])
                                        or self.gray(paired_confidence([-x for x in d], band=self.noise_band())[1])):
                        return True
            return False

        try:
            measure(rseeds)
            # sequential: while a pairwise reliance comparison is neither decisive for nor against, add intact-passing validation
            # replicates (4, then up to the validation cap)
            while len(rseeds) < self.n_val_max and any_gray():
                add = self.intact_passing_validation_seeds(min(4, self.n_val_max - len(rseeds)), exclude=rseeds)
                if not add:
                    break
                self.diag.setdefault("sequential_extensions", []).append({"key": "reliance", "to_n": len(rseeds) + len(add), "candidates": len(dist)})
                measure(add)
                rseeds += add
        except _OutOfBudget:
            pass
        n_eq = min((len(v) for v in vals.values()), default=0)
        for c, v in vals.items():
            v = v[:n_eq]
            if not v:
                continue
            ev[c]["reliance_per_seed"] = [round(x, 4) for x in v]
            ev[c]["reliance"] = round(float(np.mean(v)), 4)

    def compare(self, a: frozenset[int], b: frozenset[int], ev: dict) -> tuple[int, str, float | None]:
        """+1: a decisively better than b; -1: b decisively better; 0: tied. Keys in order: reliance (paired t over the working
        replicates, every size), Occam (fewer neurons), stress (independent binomials); a key inside its noise band does not decide."""
        ra, rb = ev[a].get("reliance_per_seed"), ev[b].get("reliance_per_seed")
        if self.cfg["reliance_tiebreak"] and ra and rb and len(ra) == len(rb):
            band = self.noise_band()
            _m, conf_a, n = paired_confidence([x - y for x, y in zip(ra, rb)], band=band)
            _m, conf_b, _n = paired_confidence([y - x for x, y in zip(ra, rb)], band=band)
            if n >= 3 and conf_a >= self.D:
                return 1, "reliance", conf_a
            if n >= 3 and conf_b >= self.D:
                return -1, "reliance", conf_b
        if len(a) != len(b):
            return (1 if len(a) < len(b) else -1), "size", None
        if ev[a].get("stress_n") and ev[b].get("stress_n"):
            conf = binomial_confidence(ev[a]["stress_k"], ev[a]["stress_n"], ev[b]["stress_k"], ev[b]["stress_n"])
            if conf >= self.DS:
                return 1, "stress", conf
            if conf <= 1.0 - self.DS:
                return -1, "stress", 1.0 - conf
        return 0, "tie", None

    def local_swaps(self, W: frozenset[int], cands: list[frozenset[int]], kinds: list[str]) -> dict[int, frozenset[int]]:
        """member -> fillers, for every replacement candidate that swaps that member (and at most one other) for at most two neurons."""
        out: dict[int, frozenset[int]] = {}
        for c, k in zip(cands, kinds):
            if not k.startswith("replacement_for_"):
                continue
            x = int(k.split("_")[-1])
            a = self.alt_of.get(c, c)
            if x in W and x not in a and len(W - a) <= 2 and 1 <= len(a - W) <= 2:
                out.setdefault(x, frozenset())
                out[x] = out[x] | (a - W)
        return out

    def paired_validation(self, va: dict, vb: dict) -> tuple[float, int, int]:
        """(P(a's conditional pass rate > b's), n10, n01) from the replicates both were validated on (discordant pairs)."""
        a = dict(zip(va.get("seeds", []), zip(va.get("intact_passed", []), va.get("passed", []))))
        b = dict(zip(vb.get("seeds", []), zip(vb.get("intact_passed", []), vb.get("passed", []))))
        common = [x for x in a if x in b and a[x][0] and b[x][0]]
        n10 = sum(1 for x in common if a[x][1] and not b[x][1])
        n01 = sum(1 for x in common if b[x][1] and not a[x][1])
        return p_above_half(n10, n10 + n01), n10, n01

    def union_repair(self, W: frozenset[int], cands: list[frozenset[int]], kinds: list[str], sel: dict) -> frozenset[int]:
        """Function carried by different copies on different parameter draws (exchangeable copies, each sufficient on only part of the
        draws). If the winner fails on validation replicates on which the intact network works, the intact network uses something else
        there: the same group elimination, run on those replicates with the current set protected, finds it (up to three rounds);
        together with the winner's one-for-one replacements this gives a union. The union replaces the winner only if it validates,
        participates and validates decisively better on the same replicates (paired, discordant replicates; the comparison is extended
        to twice the validation cap while it is close)."""
        info: dict = {"tried": False, "rounds": []}
        self.diag["union_repair"] = info
        vW = sel["ev"].get(W, {}).get("val") or self.validate(W)
        n0 = max(self.n_val, int(vW.get("n") or 0))
        swaps = self.local_swaps(W, cands, kinds)
        U = W | (frozenset().union(*swaps.values()) if swaps else frozenset())
        vU = vW if U == W else self.validate(U, n_min=n0)
        for _r in range(3):
            fails = list(vU.get("failing_seeds") or [])
            if not fails or not self.elim.complete:
                break
            seeds_f = tuple(fails[: self.m])
            e = eliminate(self.prober, self.K0, seeds_f, canonical_order(self.K0, self.key), protected=U, **{**self.elim_kw, "max_seeds": 0})
            info["rounds"].append({"seeds": list(seeds_f), "found": sorted(e.kept), "complete": e.complete})
            extra = (e.kept - U) if e.complete else frozenset()
            if not extra:
                break
            U = U | extra
            vU = self.validate(U, n_min=n0)
        if U == W:
            return W
        conf, n10, n01 = self.paired_validation(vU, vW)
        if 0.8 <= conf < self.D:  # close: extend both on the same replicates (sequential paired test)
            n_ext = 2 * self.n_val_max
            vU = self.validate(U, n_min=n_ext)
            vW = self.validate(W, n_min=n_ext)
            sel["ev"].setdefault(W, {})["val"] = vW
            conf, n10, n01 = self.paired_validation(vU, vW)
        info.update(tried=True, union=sorted(U), swaps={int(x): sorted(f) for x, f in swaps.items()}, union_status=vU["status"],
                    union_k_n=[vU["k"], vU["n"]], winner_k_n=[vW["k"], vW["n"]], discordant=[n10, n01], confidence=round(conf, 4))
        silent = sorted(p for p in U if not self.participates(p))
        if vU["status"] == "validated" and conf >= self.D and (not silent or not self.cfg["participation_check"]):
            sel["ev"][U] = {"kind": "union_of_exchangeable", "val": vU, "silent_members": silent, "participating": True}
            sel["tied"] = []
            sel["losers"] = [(W, "union", conf)] + [(c, k, cf) for c, k, cf in sel["losers"]]
            sel["winner"] = U
            sel["mode"] = "validated"
            self.union_members = U  # justified as a whole: each copy is needed on some of the draws, not on most (no leave-one-out)
            info["adopted"] = True
            self.flag("exchangeable_union")
            for f in ("undecided", "no_validated_mechanism"):
                if f in self.diag["flags"]:
                    self.diag["flags"].remove(f)
            self.diag.pop("no_validated_mechanism", None)
            return U
        info["adopted"] = False
        if vU["status"] == "validated" and conf > 0.5 and not silent:  # no evidence against it: a larger alternative (Occam)
            sel["ev"][U] = {"kind": "union_of_exchangeable", "val": vU, "silent_members": silent, "participating": True}
            sel["losers"].append((U, "size", None))
        return W

    def degeneracy(self, W: frozenset[int], cands: list[frozenset[int]], kinds: list[str]) -> dict | None:
        """No compact mechanism (distributed drive): the winner has at least three members and none is essential, and its members are
        exchangeable — either at least half of them share a structural signature (the same presynaptic and postsynaptic partner sets) with
        other core members AND with active candidates outside the core, or every canonical member whose replacement was searched (at
        least two) has a one-for-one filler. The exchangeable pool = those equivalent active candidates, the members and their fillers;
        its membership probability is the fraction of the pool the core uses."""
        base = self.elim.kept
        if len(W) < 3 or any(self.ess_tests.get(p, {}).get("essential") for p in W | base):
            return None
        Wm = self.problem.W.tocsr()
        Wc = self.problem.W.tocsc()

        def sig(p: int) -> tuple[frozenset[int], frozenset[int]]:
            return (frozenset(int(x) for x in Wm.indices[Wm.indptr[p]:Wm.indptr[p + 1]]),
                    frozenset(int(x) for x in Wc.indices[Wc.indptr[p]:Wc.indptr[p + 1]]))

        by_sig: dict[tuple, list[int]] = {}
        for p in W:
            by_sig.setdefault(sig(p), []).append(int(p))
        pool: set[int] = set()
        for sg, members in by_sig.items():
            if len(members) < 2:
                continue
            eq = {int(q) for q in self.K0 if self.participates(q) and sig(q) == sg}
            if len(eq) > len(members):  # equivalents exist outside the core
                pool |= eq
        structural = len(pool & set(W)) >= 0.5 * len(W)
        swaps = self.local_swaps(base, cands, kinds)
        tried = [p for p in base if p in self.repl_tried]
        causal = len(swaps) >= 2 and not any(p not in swaps for p in tried)
        if not (structural or causal):
            return None
        pool |= set(W) | {p for f in swaps.values() for p in f}
        frac = len(pool & set(W)) / max(1, len(pool))
        return {"flag": True, "core_size": len(W), "pool": sorted(pool), "pool_size": len(pool), "fraction_needed": round(frac, 4),
                "basis": [b for b, ok in (("structurally equivalent members", structural), ("one-for-one fillers", causal)) if ok],
                "one_for_one_fillers": {int(x): sorted(f) for x, f in swaps.items()}, "members_searched": sorted(tried),
                "note": "no member is essential and the members are exchangeable: the returned core is one arbitrary subset"}

    # ------------------------------------------------------------------ 9. minimality certificate, joint necessity
    def certify(self, core: frozenset[int]) -> tuple[frozenset[int], dict]:
        """Minimality with evidence, paired and sequential: for every member that is neither essential nor part of an adopted union, the core
        and the core without it are compared on the same replicates — the working seeds, then fresh validation seeds on which the intact
        network passes, one at a time (up to the validation cap). The member is kept as soon as the core passes decisively more often
        (discordant replicates: a member needed on only part of the draws is kept); it is removed only when all fresh replicates show no
        decisive disadvantage and the reduced set passes on at least half of the replicates (Occam); the check repeats after a removal."""
        info: dict = {"members": {}, "removed": []}
        exempt = self.essential_set() | self.union_members

        def fresh_seeds():  # intact-passing validation seeds, simulated lazily (shared with every other validation)
            s, k = self.val_first, 0
            while s < self.val_first + MAX_VALIDATION_SEEDS and k < self.n_val_max:
                if self.prober.run(self.U, s).passed:
                    k += 1
                    yield s
                s += 1

        for _round in range(max(1, len(core))):
            changed = False
            for x in sorted(core - exempt, key=lambda q: self.key[q]):
                R = core - {x}
                if not R:
                    continue
                d10 = d01 = n = kR = nf = 0
                for s in [*self.seeds, *fresh_seeds()]:
                    if nf >= self.n_val and p_above_half(d10, d10 + d01) >= self.D:
                        break  # needed: kept as soon as the core is decisively better; a removal is decided on all fresh replicates
                    oc, orr = self.prober.run(core, s), self.prober.run(R, s)
                    d10 += int(oc.passed and not orr.passed)
                    d01 += int(orr.passed and not oc.passed)
                    n += 1
                    kR += int(orr.passed)
                    nf += int(s not in self.seeds)
                conf = p_above_half(d10, d10 + d01)
                info["members"][int(x)] = {"pass_fraction_without": round(kR / n, 3) if n else None, "n": n, "n_fail_without": n - kR,
                                           "discordant": [d10, d01], "p_needed": round(conf, 4), "members_without": sorted(R)}
                if conf < self.D and n and kR / n >= 0.5:
                    core = R
                    info["removed"].append(int(x))
                    changed = True
                    break
            if not changed:
                break
        info["members"] = {k: m for k, m in info["members"].items() if k in core}
        info["certified"] = sorted(int(k) for k, m in info["members"].items() if m["p_needed"] >= self.D)
        return core, info

    def joint_necessity(self, core: frozenset[int], cands: list[frozenset[int]], kinds: list[str]) -> list[dict]:
        """Groups whose joint silencing breaks the function although no member is essential alone: a non-essential core member together
        with its one-for-one fillers ("at least one of these is necessary")."""
        out = []
        for x, F in sorted(self.local_swaps(core, cands, kinds).items()):
            if self.ess_tests.get(x, {}).get("essential"):
                continue
            G = frozenset({x}) | F
            d = self.prober.decide(self.U - G, self.seeds, self.M, min_seeds=len(self.seeds))
            rec = {"group": sorted(G), "pass_fraction_silenced": round(d.pass_fraction, 3), "n": d.n_pass + d.n_fail,
                   "jointly_necessary": not d.passed, "p_jointly_necessary": round(p_above_half(d.n_fail, d.n_pass + d.n_fail), 4)}
            if not d.passed:
                rec["note"] = "at least one of these neurons is necessary"
            out.append(rec)
        return out

    # ------------------------------------------------------------------ 10. fidelity and size-error curve
    def final_fidelity(self, core: frozenset[int], sel: dict) -> dict:
        """Keep-only of the returned core and the intact network on RESERVED fresh seeds that no selection step used (no winner's curse):
        unconditional sufficiency, conditional sufficiency (given that the intact network passes), the intact pass rate, their 90 %
        intervals and frequencies; plus the selection's own validation, reliance and stress of the core."""
        if not core:
            return {}
        ko: list[Outcome] = []
        it: list[Outcome] = []
        s = self.fid_first
        try:
            while s < self.fid_first + MAX_FIDELITY_SEEDS and sum(o.passed for o in it) < self.n_fid:
                oi = self.prober.run(self.U, s)
                o = self.prober.run(core, s)
                it.append(oi)
                ko.append(o)
                s += 1
        except _OutOfBudget:
            pass
        n = len(ko)
        k_all = sum(o.passed for o in ko)
        cond = [(o, oi) for o, oi in zip(ko, it) if oi.passed]
        k_c = sum(o.passed for o, _ in cond)
        fk = [o.frequency_hz for o in ko if o.passed and o.frequency_hz is not None]
        fi = [oi.frequency_hz for oi in it if oi.passed and oi.frequency_hz is not None]
        e = sel["ev"].get(core, {})
        v = e.get("val") or {}
        return {"keep_only_pass_fraction": (k_all / n) if n else None, "keep_only_pass_fraction_ci90": beta_interval(k_all, n) if n else None,
                "keep_only_pass_fraction_conditional": (k_c / len(cond)) if cond else None,
                "intact_pass_fraction": (sum(o.passed for o in it) / n) if n else None, "n_fresh_seeds": n,
                "fresh_seeds": "reserved (never used by the selection)",
                "selection_validation": v.get("pass_fraction"), "selection_validation_status": v.get("status"),
                "stress_pass_fraction": e.get("stress"), "robust_sd_x2_pass_fraction": e.get("stress_wide"),
                "weight_noise_pass_fraction": e.get("stress_noise"),
                "reliance": e.get("reliance"), "mismatch": e.get("mismatch"),
                "core_frequency_hz": float(np.median(fk)) if fk else None, "intact_frequency_hz": float(np.median(fi)) if fi else None,
                "core_n_active_readout": int(np.median([o.n_active_readout for o in ko if o.passed])) if k_all else None, "core_size": len(core)}

    def size_error_curve(self, core: frozenset[int], sel: dict, cert: dict) -> list[dict]:
        pts: list[dict] = []
        path = [s for s in dict.fromkeys(self.elim.path) if s != core]  # passing sets along the canonical search, largest first
        want = max(0, int(self.cfg["size_error_points"]))
        chosen: list[frozenset[int]] = []
        if path and want:
            idx = sorted({int(round(i * (len(path) - 1) / max(1, want - 1))) for i in range(min(want, len(path)))})
            chosen = [path[i] for i in idx]
        for s in chosen:
            v = self.validate(s, adaptive=False)
            if v["pass_fraction"] is not None:
                pts.append({"size": len(s), "error": round(1.0 - v["pass_fraction"], 3), "source": "search path", "returned": False,
                            "members": sorted(s) if len(s) <= 64 else None})
        ev = sel["ev"]
        for c, e in ev.items():
            v = e.get("val") or {}
            if c == core or v.get("pass_fraction") is None:
                continue
            pts.append({"size": len(c), "error": round(1.0 - v["pass_fraction"], 3), "source": f"candidate ({e.get('kind')})", "returned": False,
                        "members": sorted(c), "status": v.get("status"), "participating": e.get("participating")})
        vc = (ev.get(core, {}).get("val") or {}).get("pass_fraction")
        if vc is None and core:
            vc = self.validate(core, adaptive=False)["pass_fraction"]
        if vc is not None:
            pts.append({"size": len(core), "error": round(1.0 - vc, 3), "source": "returned core", "returned": True, "members": sorted(core),
                        "why": self.why(core, sel)})
        for x, m in (cert.get("members") or {}).items():
            if int(x) in core and m.get("pass_fraction_without") is not None:
                pts.append({"size": len(core) - 1, "error": round(1.0 - m["pass_fraction_without"], 3), "source": f"core without {x}",
                            "returned": False, "members": m.get("members_without")})
        return sorted(pts, key=lambda d: (-d["size"], d["error"]))

    def why(self, core: frozenset[int], sel: dict) -> str:
        """The actual reason the returned core was chosen (from the selection record)."""
        parts = []
        if sel.get("mode") == "none":
            return "no validated, participating candidate: the best available set is reported at low probability"
        if sel.get("mode") == "undecided":
            parts.append("no candidate validated decisively; the undecided participating candidates competed")
        W = sel.get("winner") or core
        ctx = sorted((self.essential_set() & core) - self.alt_of.get(W, W)) if core else []
        if ctx:
            parts.append(f"members {ctx} added because their single silencing breaks the intact function")
        latent = [sorted(c) for c, e in sel["ev"].items() if not e.get("participating", True)]
        if latent:
            parts.append(f"{len(latent)} sufficient set(s) excluded as latent backups (a member does not participate in the intact network)")
        if sel.get("filtered"):
            parts.append(f"{len(sel['filtered'])} candidate(s) excluded for worse dynamics fidelity")
        keys = sorted({k for _c, k, _cf in sel.get("losers", [])})
        if keys:
            parts.append("preferred over the other admissible candidates by " + ", ".join(keys))
        if sel.get("tied"):
            parts.append(f"tied with {len(sel['tied'])} candidate(s) (probability shared)")
        if self.union_members:
            parts.append("union of exchangeable copies, each only marginally sufficient")
        if not parts:
            parts.append("the only admissible candidate")
        return "; ".join(parts)

    # ------------------------------------------------------------------ 11. probabilities
    def probabilities(self, core: frozenset[int], cands: list[frozenset[int]], sel: dict, degenerate: dict | None) -> None:
        """Inclusion probabilities from the evidence counts. Candidate c's weight = P(valid) (posterior of its conditional pass rate being
        above 1/2; x P_LATENT if a member does not participate) x its preference against the winner (1 for the winner and ties; 1 minus
        the confidence of the deciding paired comparison for a decisively worse candidate; occam_factor per extra member when only Occam
        separated them), normalised when the weights sum above 1. A neuron's probability = sum over candidates of weight x P(it is
        needed in that candidate) (its leave-one-out / necessity counts); floors: a positive necessity verdict keeps at least the
        posterior of its failure rate; ceilings: silent, cleared and structurally excluded neurons keep their class values."""
        prob = self.prob
        for p in self.cleared_all:
            prob[p] = min(prob.get(p, 1.0), P_CLEARED)
        for c in cands:
            for p in c:
                prob[p] = min(prob.get(p, 1.0), P_CLEARED)
        if self.cfg.get("uncertainty_model") == POINT_MODEL:
            for p in list(prob):
                prob[p] = 1.0 if p in core else 0.0
            return
        ev = sel["ev"]
        W = sel.get("winner")
        occam = float(self.cfg.get("occam_factor", 0.5))
        use_part = bool(self.cfg["participation_check"])
        pool = [x for x in ev if x in set(cands) or x == W]
        valid: dict[frozenset[int], float] = {}
        for c in pool:
            valid[c] = float((ev[c].get("val") or {}).get("p_valid", 0.0))
            ev[c]["weight_validity"] = round(valid[c], 4)
        part = [c for c in pool if ev[c].get("participating", True) or not use_part]
        pref: dict[frozenset[int], float] = {}
        if W is not None:
            pref[W] = 1.0
            for c in sel.get("tied", []):
                pref[c] = 1.0
            for c, keyname, conf in sel.get("losers", []):
                pref[c] = occam ** max(1, len(c) - len(W)) if keyname == "size" else max(0.0, 1.0 - float(conf or 0.0))
            for c, conf in sel.get("filtered", {}).items():
                pref[c] = max(0.0, 1.0 - float(conf))
            for c in sel.get("not_minimal", []):
                pref[c] = occam ** max(1, len(c) - len(W))
            # a participating candidate outside the competition (not validated while the winner is, or failed) is compared with the
            # winner on the same replicates: its preference is 1 minus the confidence that the winner validates better
            vw = ev.get(W, {}).get("val") or {}
            for c in part:
                if c not in pref:
                    pref[c] = 1.0 - self.paired_validation(vw, ev[c].get("val") or {})[0]
        # P(c is the mechanism) = P(c valid) x its share of the preference among the participating candidates; a candidate with a
        # member that does not participate in the intact network (a latent backup) keeps only P_LATENT of its validity
        tot = sum(pref.get(c, 1.0) for c in part) or 1.0
        P = {c: (valid[c] * pref.get(c, 1.0) / tot) if c in part else valid[c] * P_LATENT for c in pool}
        self.cand_weights = P
        acc: dict[int, float] = {}
        for c, w in P.items():
            if w <= 0:
                continue
            for p in c:
                acc[p] = acc.get(p, 0.0) + w * self.member_need(p, c, W)
        for p, q in acc.items():
            prob[p] = max(min(q, P_MAX), 0.0)
        # floors from measured necessity, ceilings from silence / structure
        for p, t in self.ess_tests.items():
            if t["essential"] and t.get("p_essential") is not None:
                prob[p] = max(prob.get(p, 0.0), min(P_MAX, float(t["p_essential"])))
        for p in self.silent_set:  # silent in every passing intact run and cleared by the verified activity filter: a ceiling
            if not self.ess_tests.get(p, {}).get("essential") and (W is None or p not in W):
                prob[p] = min(prob.get(p, P_SILENT), P_SILENT)
        for p in self.structural_out:
            prob[p] = P_STRUCTURAL
        if degenerate:
            vw = float(((ev.get(W) or {}).get("val") or {}).get("p_valid", 0.0)) if W is not None else 0.0
            q = round(min(P_MAX, degenerate["fraction_needed"] * max(vw, 0.5)), 4)
            for p in degenerate["pool"]:
                prob[int(p)] = q
        self.weights = {"candidates": [{"members": sorted(c) if len(c) <= 64 else f"{len(c)} neurons", "weight": round(w, 4),
                                        "p_valid": ev[c].get("weight_validity")} for c, w in sorted(P.items(), key=lambda kv: -kv[1])],
                        "preference_total": round(tot, 4)}

    def member_need(self, p: int, c: frozenset[int], W: frozenset[int] | None) -> float:
        """P(member p is needed in candidate c): its leave-one-out counts (certificate for the returned core, the elimination's
        1-minimality decisions otherwise), or its necessity posterior, whichever is larger; exchangeable-union members count as needed."""
        q = None
        t = self.ess_tests.get(p)
        if c == W and p in self.union_members:
            return 1.0
        m = (getattr(self, "cert_info", {}) or {}).get("members", {}).get(int(p)) if c == W else None
        if m is not None and m.get("p_needed") is not None:
            q = float(m["p_needed"])
        else:
            e = self.elims.get(self.alt_of.get(c, c))
            d = e.necessary.get(p) if e is not None else None
            if d is not None:
                q = p_above_half(d.n_fail, d.n_pass + d.n_fail)
        if t and t.get("p_essential") is not None and t["essential"]:
            q = max(q or 0.0, float(t["p_essential"]))
        if q is None:
            q = 1.0 if (c == W and self.elim.complete) else P_UNTESTED
        return float(q)

    # ------------------------------------------------------------------ diagnostics, predictions
    def selection_diag(self, cands: list[frozenset[int]], kinds: list[str], sel: dict, winner: frozenset[int] | None) -> dict:
        ev = sel["ev"]
        rows = []
        for c in list(dict.fromkeys([*cands, *([winner] if winner is not None else [])])):
            e = ev.get(c, {})
            v = e.get("val") or {}
            rows.append({"members": sorted(c) if len(c) <= 64 else f"{len(c)} neurons", "kind": e.get("kind"), "status": v.get("status"),
                         "validation": v.get("pass_fraction"), "validation_k_n": [v.get("k"), v.get("n")], "p_valid": v.get("p_valid"),
                         "intact_pass": v.get("intact_pass_fraction"),
                         "participating": e.get("participating"), "silent_members": e.get("silent_members"), "mismatch": e.get("mismatch"),
                         "mismatch_per_seed": e.get("mismatch_per_seed"),
                         "fidelity_vs_best": e.get("fidelity_vs_best"), "reliance": e.get("reliance"), "reliance_per_seed": e.get("reliance_per_seed"),
                         "stress": e.get("stress"), "stress_k_n": [e.get("stress_k"), e.get("stress_n")]})
        return {"candidates": rows, "mode": sel.get("mode"), "chosen": sorted(winner) if winner is not None else [], "trace": sel.get("trace"),
                "tied": [sorted(c) for c in sel.get("tied", [])],
                "decisively_worse": [{"members": sorted(c), "key": k, "confidence": None if cf is None else round(cf, 4)}
                                     for c, k, cf in sel.get("losers", [])],
                "fidelity_excluded": [{"members": sorted(c), "confidence": round(cf, 4)} for c, cf in sel.get("filtered", {}).items()],
                "not_minimal": [sorted(c) for c in sel.get("not_minimal", [])]}

    def strongest_edge(self, p: int, core: frozenset[int]) -> tuple[int, int, float] | None:
        """(post, pre, signed count) of member p's strongest outgoing in-core edge (self-loop included), else its strongest incoming one;
        ties broken by the canonical key of the other end (node-order independent up to exact automorphisms)."""
        W = self.problem.W.tocsc()
        col = W.indices[W.indptr[p]:W.indptr[p + 1]]
        vals = W.data[W.indptr[p]:W.indptr[p + 1]]
        outs = [(int(q), float(w)) for q, w in zip(col, vals) if int(q) in core and w != 0]
        if outs:
            q, w = max(outs, key=lambda t: (abs(t[1]), self.key[t[0]], -t[0]))
            return q, p, w
        Wr = self.problem.W.tocsr()
        row = Wr.indices[Wr.indptr[p]:Wr.indptr[p + 1]]
        rv = Wr.data[Wr.indptr[p]:Wr.indptr[p + 1]]
        ins = [(int(q), float(w)) for q, w in zip(row, rv) if int(q) in core and int(q) != p and w != 0]
        if ins:
            q, w = max(ins, key=lambda t: (abs(t[1]), self.key[t[0]], -t[0]))
            return p, q, w
        return None

    def edge_decision(self, kept: frozenset[int], edge: tuple[int, int]) -> tuple[bool | None, int, int]:
        """Sequential strict majority over the working seeds of the network ``kept`` with one synapse removed: (passed, k, n)."""
        need = len(self.seeds) // 2 + 1
        k = n = 0
        try:
            for s in self.seeds:
                o = self.prober.run(kept, s, remove_edges=(edge,))
                n += 1
                k += int(o.passed)
                if k >= need or (n - k) > len(self.seeds) - need:
                    break
        except _OutOfBudget:
            return None, k, n
        return bool(k >= need), k, n

    def edge_predictions(self, core: frozenset[int]) -> list[dict]:
        """Intervention predictions for every core member, each backed by the simulations it states: silencing the member alone (its pooled
        necessity test) and removing its strongest in-core edge in the intact network and in the keep-only core (a synapse-removal
        simulation on the working seeds, a few calls per member); a prediction the budget did not allow is None (abstention). The stated
        confidence is the posterior probability of the predicted side of 1/2."""
        out = []
        members = sorted(core, key=lambda q: self.key[q], reverse=True)[: max(0, int(self.cfg["edge_prediction_members"]))]
        simulate = bool(self.cfg.get("simulate_edge_predictions", True))
        for p in sorted(core):
            t = self.ess_tests.get(p)
            sil = {"predicted_function_preserved": None if t is None else not t["essential"],
                   "pass_fraction_silenced": None if t is None else t["pass_fraction_silenced"], "n": None if t is None else t["n_seeds"],
                   "confidence": None if t is None or t.get("p_essential") is None else round(max(t["p_essential"], 1.0 - t["p_essential"]), 4)}
            rec: dict = {"position": int(p), "silence_alone": sil}
            e = self.strongest_edge(p, core)
            if e is None:
                rec["strongest_in_core_edge"] = None
                out.append(rec)
                continue
            post, pre, w = e
            er: dict = {"pre": int(pre), "post": int(post), "signed_count": w}
            if not simulate or p not in members:
                er.update(predicted_function_preserved=None, predicted_function_preserved_in_core=None,
                          note="abstained: not simulated" + ("" if simulate else " (switched off)"))
            else:
                ri, ki, ni = self.edge_decision(self.U, (post, pre))
                rc, kc, nc = self.edge_decision(core, (post, pre))
                er.update(predicted_function_preserved=ri, n=ni, pass_fraction=None if not ni else round(ki / ni, 3),
                          confidence=None if ri is None or not ni else round(p_above_half(ki, ni) if ri else 1.0 - p_above_half(ki, ni), 4),
                          predicted_function_preserved_in_core=rc, n_in_core=nc, pass_fraction_in_core=None if not nc else round(kc / nc, 3),
                          confidence_in_core=None if rc is None or not nc else round(p_above_half(kc, nc) if rc else 1.0 - p_above_half(kc, nc), 4),
                          note="simulated: synapse removed (SimQuery.remove_edges) on the working replicates")
            rec["strongest_in_core_edge"] = er
            out.append(rec)
        return out

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
        self.flag("no_validated_mechanism")
        intact_outs = [self.prober.intact_outcomes[s] for s in self.prober.tried]
        frac = float(np.mean([o.passed for o in intact_outs])) if intact_outs else None
        return DiscoveryResult(core=[], inclusion_probability={int(p): 0.0 for p in self.U}, roles={}, essential={}, alternatives=[], loop=[],
                               predicted_function_preserved=None if frac is None else bool(frac >= 0.5), fidelity={},
                               budget={**self.sim.report(), "wall_s": round(time.time() - self.t0, 1)}, diagnostics=self.diag, motif=None)


def _val_diag(v: dict) -> dict:
    return {k: val for k, val in v.items() if k not in ("outcomes", "intact_outcomes")}



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
    fid = (result.fidelity or {}).get("keep_only_pass_fraction_conditional", (result.fidelity or {}).get("keep_only_pass_fraction"))
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
