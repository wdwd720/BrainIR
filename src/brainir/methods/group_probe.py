"""Active causal probing with group tests and a Bernoulli membership posterior (``group_probe``).

Hypothesis under test: choosing interventions that maximally reduce the uncertainty about mechanism membership finds
the mechanism with far fewer simulations than one-neuron-at-a-time deletion. Almost every call is a cheap keep-only
probe of a small set; the expensive full-network silencing is used only to establish essentiality and redundancy.

Reduction to classical group testing
------------------------------------
Let ``pass(S)`` mean "keep-only S satisfies the criterion" and M an unknown minimal sufficient set. Once a pool P with
``pass(P) = 1`` is known, the *removal probe* ``T(G) := pass(P \\ G)`` for ``G ⊆ P`` answers "does G contain a member
of the sufficient set inside P?" (fail ⇔ G ∩ M ≠ ∅ under monotonicity): a classical OR-type pooled test on G.
Adaptive splitting therefore localises the d members of P with about ``d·log2(|P|/d) + O(d)`` probes instead of the
``|P|`` leave-one-out probes of a single-deletion screen (Hwang's generalized binary splitting; the information bound
is ``log2 C(|P|, d)``). Non-monotone effects and parameter-seed noise are absorbed by (i) requiring every "pass" on all
working seeds, (ii) a noisy-test likelihood in the posterior, (iii) singleton confirmation of every member, (iv) a
discrete cleanup / add-back stage and (v) conditional searches for backups.

Algorithm (K working parameter seeds per decision; a probe *passes* only if it passes on all of them)
  0. baseline: intact network on K+1 seeds (the K passing seeds with the best score are the working seeds); keep-only
     of nothing (stimulus + readout alone): if that passes, the direct pathway is the mechanism and the core is empty.
  1. prior: candidates that cannot be members under the model get p = 0 (unknown sign ⇒ zero output column; not
     reachable from the stimulus through positive edges ⇒ provably silent from rest); the others are ordered with the
     neurons active in the intact runs first (activity fingerprint), then by a bounded-hop stimulus→i and i→readout
     influence score.
  2. localisation: keep-only of prior-ranked prefixes, doubling until one passes (the pool P).
  3. group elimination = adaptive group testing on P with independent Bernoulli marginals q_i: probe the removal of the
     group G of lowest-q open items whose pass probability Π(1-q_i) is closest to 1/2 (maximal outcome entropy, i.e.
     the expected information gain of a noiseless test); pass → discard G, fail → Bayesian update (G holds a member);
     a singleton that fails is a confirmed member. Neurons silent in a passing probe are down-weighted for free.
  4. discrete minimality cleanup (leave-one-out inside the confirmed set), fidelity on fresh seeds and add-back of the
     best-supported discarded neurons when the mechanism is not robust (an add-back that breaks the working seeds is
     recorded as an antagonist: a non-monotone effect).
  5. essentiality: full-network single silencing of every member.
  5b. necessity screen (bounded share of the remaining budget): neurons active in the intact network but outside the
     core can be necessary in context without being needed in isolation (a keep-only removes the competitor they
     suppress, so no sufficiency probe can see them); the most context-relevant ones are silenced one at a time, the
     rest in small same-sign pools with adaptive splitting. Confirmed ones join the core as context members.
  6. redundancy: for every non-essential member m, search a sufficient set that avoids m (steps 2–4 with the other
     members forced in) → backups / alternative implementations, reported as ``alternatives``.
  7. roles from sign, induced-cycle membership, connectivity to stimulus/readout and the criterion type; loop = cycle
     members; inclusion probabilities = posterior marginals.
"""

from __future__ import annotations

import math
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from ..discovery.interface import GENERIC_ROLES, DiscoveryMethod, DiscoveryResult, MethodRegistry
from ..discovery.interventions import keep_only, silence
from ..discovery.problem import DiscoveryProblem
from ..discovery.simulator import BudgetedSimulator, BudgetExhausted, Outcome

_Q_MIN, _Q_MAX = 1e-6, 1.0 - 1e-6


# ---------------------------------------------------------------------------- probes
@dataclass
class Verdict:
    passed: bool
    """True only if the criterion passed on every seed of the probe."""
    frac: float
    score: float
    conf: float
    """1.0 when the seeds agree, 0.5 when they disagree (weak evidence)."""
    outs: list[Outcome]
    active: set[int]
    """Union over seeds of the neurons active in the probe (the activity fingerprint)."""
    n_active_readout: float
    frequency_hz: float | None


class Prober:
    """Every simulation of the method goes through here (and hence through the budgeted simulator)."""

    def __init__(self, problem: DiscoveryProblem, sim: BudgetedSimulator, seeds: list[int]):
        self.problem, self.sim, self.seeds = problem, sim, list(seeds)
        self.n_keep = 0
        self.n_silence = 0
        self.n_intact = 0
        self.keep_sizes: list[int] = []

    @staticmethod
    def verdict(outs: list[Outcome]) -> Verdict:
        passed = [bool(o.passed) for o in outs]
        freqs = [o.frequency_hz for o in outs if o.frequency_hz is not None]
        active: set[int] = set()
        for o in outs:
            active.update(int(p) for p in o.active_positions)
        return Verdict(passed=all(passed), frac=float(np.mean(passed)) if passed else 0.0, score=float(np.mean([o.score for o in outs])) if outs else 0.0,
                       conf=1.0 if len(set(passed)) <= 1 else 0.5, outs=outs, active=active,
                       n_active_readout=float(np.median([o.n_active_readout for o in outs])) if outs else 0.0,
                       frequency_hz=float(np.median(freqs)) if freqs else None)

    def keep(self, S: Iterable[int], seeds: list[int] | None = None, **kw) -> Verdict:
        S = sorted({int(p) for p in S})
        before = self.sim.calls
        outs = self.sim.evaluate(keep_only(self.problem, S), seeds if seeds is not None else self.seeds, **kw)
        self.n_keep += self.sim.calls - before
        self.keep_sizes.append(len(S))
        return self.verdict(outs)

    def sil(self, G: Iterable[int], seeds: list[int] | None = None) -> Verdict:
        before = self.sim.calls
        outs = self.sim.evaluate(silence(G), seeds if seeds is not None else self.seeds)
        self.n_silence += self.sim.calls - before
        return self.verdict(outs)

    def intact(self, seeds: list[int]) -> list[Outcome]:
        before = self.sim.calls
        outs = self.sim.evaluate(None, seeds)
        self.n_intact += self.sim.calls - before
        return outs


# ---------------------------------------------------------------------------- posterior
class Posterior:
    """Independent Bernoulli marginals q_i = p(z_i = 1) with sequential noisy-group-test updates (mean-field).

    A removal probe of group G is modelled as an OR-type pooled test: it fails when G contains a member. With
    ``false_pass`` = P(pass | G holds a member) and ``false_fail`` = P(fail | G holds no member), the marginal update of
    item i uses r_i = P(no *other* member in G) under the current marginals (the exact marginal update for independent
    priors, applied sequentially)."""

    def __init__(self, q: dict[int, float], rank: dict[int, int], false_pass: float, false_fail: float):
        self.q = {int(k): float(min(_Q_MAX, max(_Q_MIN, v))) for k, v in q.items()}
        self.rank = rank
        self.false_pass, self.false_fail = float(false_pass), float(false_fail)

    def _noise(self, conf: float) -> tuple[float, float]:
        if conf >= 1.0:
            return self.false_pass, self.false_fail
        return max(self.false_pass, 0.3), max(self.false_fail, 0.3)

    def update(self, group: Iterable[int], passed: bool, conf: float = 1.0) -> None:
        group = [int(i) for i in group]
        if not group:
            return
        fp, ff = self._noise(conf)
        qs = np.array([self.q[i] for i in group])
        log1m = np.log1p(-qs)
        r = np.exp(log1m.sum() - log1m)  # P(no other member in the group)
        if passed:
            l1, l0 = fp, r * (1.0 - ff) + (1.0 - r) * fp
        else:
            l1, l0 = 1.0 - fp, r * ff + (1.0 - r) * (1.0 - fp)
        post = qs * l1 / (qs * l1 + (1.0 - qs) * l0)
        for i, p in zip(group, post):
            self.q[i] = float(min(_Q_MAX, max(_Q_MIN, p)))

    def scale(self, items: Iterable[int], factor: float) -> None:
        for i in items:
            self.q[int(i)] = float(min(_Q_MAX, max(_Q_MIN, self.q[int(i)] * factor)))

    def pick_group(self, open_items: Iterable[int], target: float = 0.5) -> list[int]:
        """The group of lowest-q items whose pass probability Π(1 - q_i) is closest to ``target`` (max outcome entropy)."""
        items = sorted(open_items, key=lambda i: (self.q[i], self.rank.get(i, 0), i))
        if not items:
            return []
        log_t = math.log(target)
        best_k, best_d, acc = 1, float("inf"), 0.0
        for k, i in enumerate(items, 1):
            acc += math.log1p(-self.q[i])
            d = abs(acc - log_t)
            if d < best_d:
                best_k, best_d = k, d
            if acc < log_t:
                break
        return items[:best_k]

    def mass(self, items: Iterable[int]) -> float:
        return float(sum(self.q[int(i)] for i in items))


# ---------------------------------------------------------------------------- structural prior
@dataclass
class Prior:
    order: list[int]
    """Candidates that can be members, most promising first."""
    impossible: list[int]
    """Candidates that cannot influence the readout under the model (zero output column or unreachable from rest)."""
    score: dict[int, float]
    rank: dict[int, int]
    active_intact: set[int]
    external: dict[int, float] | None = None
    """Optional external prior inclusion probabilities (``config["prior"]``), e.g. transferred from another network."""


def _bfs_positive(problem: DiscoveryProblem, sources: Iterable[int]) -> np.ndarray:
    """Neurons reachable from ``sources`` through positive (excitatory) edges; the others stay silent from rest."""
    Wpos = problem.W.maximum(0).tocsc()  # column j: rows = post-synaptic targets of pre j
    n = problem.n
    seen = np.zeros(n, dtype=bool)
    frontier = [int(s) for s in sources]
    seen[frontier] = True
    while frontier:
        nxt = []
        for j in frontier:
            for i in Wpos.indices[Wpos.indptr[j]:Wpos.indptr[j + 1]]:
                if not seen[i]:
                    seen[i] = True
                    nxt.append(int(i))
        frontier = nxt
    return seen


def structural_prior(problem: DiscoveryProblem, active_intact: set[int], *, hops: int, decay: float, inactive_factor: float,
                     external: dict[int, float] | None = None, external_weight: float = 1.0) -> Prior:
    """Candidate ordering and structural impossibility. ``external`` (optional) biases the ordering by
    ``external_weight · log((p_i + 1e-3) / (p_default + 1e-3))``; positions it does not mention get ``p_default`` =
    min(0.05, smallest given value). Its absence means a uniform external prior (pure structural ordering)."""
    n = problem.n
    ext_default = min(0.05, min(external.values())) if external else 0.05
    W = problem.W.tocsr()
    cand = [int(p) for p in problem.candidate_positions()]
    reach = _bfs_positive(problem, problem.stim_positions)
    # forward influence: fraction of each neuron's excitatory input that traces back to the stimulus within `hops`
    Wpos = W.maximum(0).tocsr()
    rs = np.asarray(Wpos.sum(axis=1)).ravel()
    A = sp.diags(np.where(rs > 0, 1.0 / np.maximum(rs, 1e-12), 0.0)) @ Wpos
    x = np.zeros(n)
    x[list(problem.stim_positions)] = 1.0
    f = np.zeros(n)
    for h in range(hops):
        x = A @ x
        f += (decay ** h) * x
    # backward influence: fraction of each neuron's output that reaches the readout within `hops` (any sign)
    Wabs = abs(W).tocsr()
    cs = np.asarray(Wabs.sum(axis=0)).ravel()
    B = (Wabs @ sp.diags(np.where(cs > 0, 1.0 / np.maximum(cs, 1e-12), 0.0))).tocsr()
    y = problem.readout_mask.astype(np.float64)
    b = np.zeros(n)
    for h in range(hops):
        y = B.T @ y
        b += (decay ** h) * y
    signs = problem.signs
    score, impossible, possible = {}, [], []
    for p in cand:
        s = math.log(f[p] + 1e-9) + math.log(b[p] + 1e-9)
        if p not in active_intact:
            s += math.log(inactive_factor)
        if external is not None:
            s += float(external_weight) * (math.log(external.get(p, ext_default) + 1e-3) - math.log(ext_default + 1e-3))
        score[p] = s
        if signs[p] == 0 or not reach[p]:
            impossible.append(p)
        else:
            possible.append(p)
    # strict tiers: neurons active in the intact runs first (a silent neuron cannot contribute), then by influence score
    order = sorted(possible, key=lambda p: (p not in active_intact, -score[p], p))
    impossible.sort(key=lambda p: (-score[p], p))
    rank = {p: r for r, p in enumerate(order + impossible)}
    return Prior(order=order, impossible=impossible, score=score, rank=rank, active_intact=set(active_intact), external=external)


# ---------------------------------------------------------------------------- search engine
@dataclass
class SearchState:
    pool: list[int] | None = None
    verdict: Verdict | None = None
    confirmed: list[int] = field(default_factory=list)
    members: list[int] = field(default_factory=list)
    best_sufficient: set[int] | None = None
    """A set whose keep-only passed on the working seeds (always a valid, if not minimal, answer)."""
    removal_info: dict[int, dict] = field(default_factory=dict)
    n_elim_tests: int = 0


class Engine:
    def __init__(self, prober: Prober, post: Posterior, cfg: dict, trace: dict):
        self.prober, self.post, self.cfg, self.trace = prober, post, cfg, trace

    def _log(self, **rec) -> None:
        self.trace.setdefault("tests", []).append(rec)

    def _downweight_silent(self, items: Iterable[int], active: set[int]) -> int:
        silent = [i for i in items if i not in active]
        self.post.scale(silent, float(self.cfg["inactive_factor"]))
        return len(silent)

    def localise(self, order: list[int], forced: set[int], excluded: set[int], st: SearchState, tag: str) -> bool:
        """Keep-only of prior-ranked prefixes (plus ``forced``), doubling until one passes. Fills st.pool / st.verdict."""
        cands = [i for i in order if i not in forced and i not in excluded]
        if not cands:
            v = self.prober.keep(forced)
            self._log(stage=f"{tag}:localise", prefix=0, passed=v.passed, score=round(v.score, 3))
            if v.passed:
                st.pool, st.verdict, st.best_sufficient = [], v, set(forced)
            return v.passed
        k = min(int(self.cfg["pool_start"]), len(cands))
        prev = 0
        while True:
            S = set(forced) | set(cands[:k])
            v = self.prober.keep(S)
            self._log(stage=f"{tag}:localise", prefix=k, passed=v.passed, frac=v.frac, score=round(v.score, 3), n_active=len(v.active))
            if v.passed:
                if prev > 0:  # the slice added since the last failing prefix holds a member (given the rest of the pool)
                    self.post.update(cands[prev:k], passed=False, conf=1.0)
                self.post.scale(cands[k:], float(self.cfg["outside_pool_factor"]))
                st.pool, st.verdict, st.best_sufficient = list(cands[:k]), v, set(S)
                return True
            if k >= len(cands):
                return False
            prev = k
            k = min(len(cands), max(k + 1, int(round(k * float(self.cfg["pool_growth"])))))

    def eliminate(self, forced: set[int], st: SearchState, tag: str) -> None:
        """Adaptive group testing on the pool: removal probes of maximally uncertain groups; fills st.confirmed."""
        assert st.pool is not None and st.verdict is not None
        P = set(st.pool) | set(forced)
        open_items = [i for i in st.pool if i not in forced]
        confirmed: list[int] = []
        self._downweight_silent(open_items, st.verdict.active)
        while open_items:
            G = self.post.pick_group(open_items)
            v = self.prober.keep(P - set(G))
            st.n_elim_tests += 1
            self._log(stage=f"{tag}:eliminate", group=len(G), pool=len(P), passed=v.passed, frac=v.frac, score=round(v.score, 3),
                      mass=round(self.post.mass(open_items), 2))
            self.post.update(G, passed=v.passed, conf=v.conf)
            if v.passed:
                P -= set(G)
                gs = set(G)
                open_items = [i for i in open_items if i not in gs]
                st.best_sufficient = set(P)
                self._downweight_silent(open_items, v.active)
            elif len(G) == 1:
                confirmed.append(G[0])
                open_items.remove(G[0])
        st.confirmed = confirmed
        st.members = sorted(P)

    def necessity_screen(self, cands: list[int], relevance: dict[int, float], signs: np.ndarray, budget_calls: int, K: int,
                         tag: str = "necessity") -> tuple[list[int], list[int], list[int], list[int]]:
        """Which neurons outside the core are necessary in the FULL network (silencing them alone breaks the function)?
        Sufficiency probes cannot see them (a keep-only removes the competitor they suppress), so this stage pays
        full-network prices: single silencing for the most context-relevant candidates, then OR-type adaptive splitting
        on small same-sign silencing pools (a pass clears the pool; a fail is split) until ``budget_calls`` are spent.
        Returns (necessary, cleared, ambiguous, untested)."""
        spent0 = self.prober.sim.calls
        order = sorted(cands, key=lambda i: (-relevance.get(i, 0.0), i))
        necessary, cleared, ambiguous = [], [], []
        ess_max = float(self.cfg["essential_pass_max"])
        n_single = len(order) if K * len(order) <= budget_calls else min(len(order), int(self.cfg["necessity_singles"]))

        def probe(G: list[int]) -> Verdict | None:
            if self.prober.sim.calls - spent0 + K > budget_calls or self.prober.sim.remaining < K:
                return None
            v = self.prober.sil(G)
            self._log(stage=tag, group=len(G), passed=v.passed, frac=v.frac, score=round(v.score, 3))
            return v

        def untested() -> list[int]:
            seen = set(necessary) | set(cleared) | set(ambiguous)
            return [i for i in order if i not in seen]

        for i in order[:n_single]:
            v = probe([i])
            if v is None:
                return necessary, cleared, ambiguous, untested()
            (cleared if v.passed else necessary if v.frac <= ess_max else ambiguous).append(i)
        rest = sorted(order[n_single:], key=lambda i: (int(signs[i]), -relevance.get(i, 0.0), i))
        gmax = max(1, int(self.cfg["necessity_group_max"]))
        stack: list[list[int]] = []
        for s in sorted({int(signs[i]) for i in rest}):
            same = [i for i in rest if int(signs[i]) == s]
            stack += [same[k:k + gmax] for k in range(0, len(same), gmax)]
        while stack:
            G = stack.pop(0)
            v = probe(G)
            if v is None:
                break
            if v.passed:
                cleared += G
            elif len(G) == 1:
                (necessary if v.frac <= ess_max else ambiguous).append(G[0])
            else:
                h = len(G) // 2
                stack = [G[:h], G[h:]] + stack
        return necessary, cleared, ambiguous, untested()

    def cleanup(self, members: list[int], st: SearchState, tag: str, *, keep_fixed: set[int] = frozenset()) -> list[int]:
        """Leave-one-out inside the current set (least certain first); removable members are dropped. Records the
        ablation signature of every kept member (score / readout activity without it)."""
        M = list(members)
        for i in sorted(members, key=lambda i: (self.post.q.get(i, 0.5), i)):
            if i in keep_fixed or i not in M:
                continue
            v = self.prober.keep(set(M) - {i})
            self._log(stage=f"{tag}:cleanup", member=i, passed=v.passed, frac=v.frac, score=round(v.score, 3))
            self.post.update([i], passed=v.passed, conf=v.conf)
            if v.passed:
                M.remove(i)
                st.best_sufficient = set(M)
            else:
                st.removal_info[i] = {"score_without": round(v.score, 4), "pass_fraction_without": v.frac,
                                      "n_active_readout_without": v.n_active_readout}
        return M


# ---------------------------------------------------------------------------- roles
def _induced_cycles(problem: DiscoveryProblem, nodes: list[int]) -> tuple[set[int], list[int]]:
    """Members of the induced subgraph that lie on a directed cycle (strongly connected component of size >= 2 or a
    self-loop) and the largest such component."""
    if not nodes:
        return set(), []
    idx = np.array(nodes, dtype=np.int64)
    sub = problem.W[idx][:, idx].tocsr()
    n_comp, labels = connected_components(sub, directed=True, connection="strong")
    sizes = np.bincount(labels, minlength=n_comp)
    diag = sub.diagonal()
    in_cycle = {int(nodes[k]) for k in range(len(nodes)) if sizes[labels[k]] >= 2 or diag[k] != 0}
    big = int(np.argmax(sizes)) if n_comp else 0
    loop = [int(nodes[k]) for k in range(len(nodes)) if labels[k] == big] if sizes[big] >= 2 else sorted(in_cycle)
    return in_cycle, sorted(loop)


def generic_roles(problem: DiscoveryProblem, core: list[int], backups: Iterable[int], crit_type: str) -> tuple[dict[int, tuple[str, float]], list[int]]:
    """Criterion-aware roles from sign and induced connectivity (no simulation). Returns (roles, loop)."""
    W = problem.W.tocsr()
    stim = list(problem.stim_positions)
    ro = problem.readout_positions
    crit = problem.criterion_spec
    ga = [int(p) for p in crit.get("group_a_positions", [])]
    gb = [int(p) for p in crit.get("group_b_positions", [])]
    in_cycle, loop = _induced_cycles(problem, core)
    roles: dict[int, tuple[str, float]] = {}
    for p in core:
        s = int(problem.signs[p])
        out_ro = float(abs(W[ro, p]).sum()) if len(ro) else 0.0
        drives_ro = out_ro > 0
        gets_stim = float(W[p, stim].sum()) > 0 if stim else False
        cyc = p in in_cycle
        conf = 0.7
        if s == 0:
            role, conf = "unknown", 0.5
        elif s > 0:
            if crit_type == "selectivity" and gb and ga:
                to_a, to_b = float(abs(W[ga, p]).sum()), float(abs(W[gb, p]).sum())
                if to_b > 0 and to_a == 0:
                    role = "competitor"
                elif drives_ro:
                    role = "output_driver"
                else:
                    role = "input_relay"
            elif crit_type in ("ramp", "persistence"):
                role = "state_memory" if cyc else ("output_driver" if drives_ro else "input_relay")
            elif crit_type == "rhythm":
                if cyc:
                    role = "recurrent_excitatory_core" if (drives_ro or gets_stim) else "input_relay"
                else:
                    role = "output_driver" if drives_ro else "input_relay"
            else:  # activity_band and anything else: feed-forward drive with optional feedback
                role = "output_driver" if drives_ro else "input_relay"
            if not cyc and not drives_ro and not gets_stim:
                conf = 0.55
        else:
            if crit_type == "selectivity":
                role = "lateral_inhibition"
            elif crit_type == "rhythm":
                role = "inhibitory_feedback"
            else:
                role = "gain_control"
            if not cyc and crit_type == "rhythm":
                conf = 0.6
        roles[p] = (role, conf)
    for p in backups:
        if p not in roles:
            roles[int(p)] = ("redundant_backup", 0.6)
    assert all(r in GENERIC_ROLES for r, _ in roles.values())
    return roles, loop


# ---------------------------------------------------------------------------- the method
@MethodRegistry.register
class GroupProbe(DiscoveryMethod):
    """Active causal probing with group tests (adaptive group testing on keep-only pools with a Bernoulli membership
    posterior, max-entropy group acquisition, singleton confirmation, cleanup / add-back, full-network essentiality and
    conditional searches for backups). See the module docstring for the algorithm."""

    name = "group_probe"
    version = "1.0"
    default_config = {
        "replicates": 2,            # K working parameter seeds per decision
        "fresh_seeds": 3,           # fresh seeds for the final fidelity estimate (and add-back)
        "pool_start": 16,           # first keep-only prefix size
        "pool_growth": 2.0,         # prefix doubling factor
        "prior_members": 4.0,       # prior expected number of members inside the pool (sets the initial group sizes)
        "prior_rank_offset": 4.0,   # q0 ∝ 1 / (rank + offset)
        "q_max": 0.5,
        "hops": 5, "hop_decay": 0.5,
        "inactive_factor": 0.05,    # multiplicative down-weight for neurons silent in a passing probe
        "outside_pool_factor": 0.05,
        "false_pass": 0.02, "false_fail": 0.05,   # noisy-test likelihood (unanimous seeds); 0.3 when seeds disagree
        "max_addback": 6,
        "necessity_share": 0.35,    # fraction of the calls left after the primary search spent on the full-network necessity screen
        "necessity_singles": 8,     # most context-relevant candidates silenced one at a time before pooled silencing
        "necessity_group_max": 4,   # pool size of the pooled silencing (small: pooled silencing can hide a necessary neuron)
        "essential_pass_max": 0.2,  # a member is essential when silencing it alone passes on at most this fraction of the tested seeds
        "essential_extra_seeds": 2, # spend-down: extra seeds for every essentiality claim when budget is left
        "spend_down_share": 0.5,    # spend-down: fraction of the calls left spent on single silencing of untested active neurons
        "max_alternatives": 3,
        "alt_weight": 0.3,          # inclusion probability of a backup = alt_weight * its posterior in the backup search
        "alt_min_calls": 30,        # do not start a backup search with fewer calls left
        "robust_check": True,       # keep-only of the core with widened parameter sds on the fresh seeds (when affordable)
        "prior": None,              # optional {position: prior inclusion probability}; absent = uniform (structural ordering only)
        "prior_weight": 1.0,        # weight of log(prior odds) in the candidate ordering
    }

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def _q0(prior: Prior, items: list[int], cfg: dict) -> dict[int, float]:
        off = float(cfg["prior_rank_offset"])
        w = {i: (1.0 / (prior.rank[i] + off)) * (float(cfg["inactive_factor"]) if i not in prior.active_intact else 1.0) for i in items}
        tot = sum(w.values()) or 1.0
        scale = float(cfg["prior_members"]) / tot
        q0 = {i: min(float(cfg["q_max"]), max(_Q_MIN, v * scale)) for i, v in w.items()}
        if prior.external:  # an external inclusion probability lifts the initial marginal (never below the structural one)
            for i in items:
                if i in prior.external and i in prior.active_intact:
                    q0[i] = max(q0[i], min(0.95, float(prior.external[i])))
        return q0

    def discover(self, problem: DiscoveryProblem, sim: BudgetedSimulator, *, seed: int, config: dict | None = None) -> DiscoveryResult:
        cfg = {**self.default_config, **(config or {})}
        t0 = time.time()
        K = max(1, int(cfg["replicates"]))
        base = int(seed) * 1000
        trace: dict = {"stages": [], "tests": [], "budget_exhausted": False, "antagonists": [], "non_monotone_events": []}
        cand = [int(p) for p in problem.candidate_positions()]
        crit_type = str(problem.criterion_spec.get("type", "rhythm"))
        prober = Prober(problem, sim, [])
        st = SearchState()
        alternatives: list[list[int]] = []
        alt_probs: dict[int, float] = {}
        essential: dict[int, bool | None] = {}
        essential_frac: dict[int, float] = {}
        fidelity: dict = {}
        intact_outs: list[Outcome] = []
        added_back: list[int] = []
        context_members: list[int] = []
        ctx_untested: list[int] = []
        rel: dict[int, float] = {}
        direct = False
        post: Posterior | None = None
        prior: Prior | None = None
        engine: Engine | None = None
        try:
            # ---------------------------------------------------------- stage 0: working seeds and baselines
            probe_seeds = [base + k for k in range(K + 1)]
            intact_outs = prober.intact(probe_seeds)
            passing = [(s, o) for s, o in zip(probe_seeds, intact_outs) if o.passed]
            extra = K + 1
            while len(passing) < K and extra < 2 * K + 4:
                s = base + extra
                o = prober.intact([s])[0]
                intact_outs.append(o)
                if o.passed:
                    passing.append((s, o))
                extra += 1
            passing.sort(key=lambda so: (-so[1].score, so[0]))
            working = [s for s, _ in passing[:K]]
            trace["working_seeds"] = working
            trace["intact_pass_fraction"] = float(np.mean([o.passed for o in intact_outs]))
            if not working:
                trace["stages"].append("intact network never passes on the probed seeds: no mechanism to find")
                raise BudgetExhausted("no passing seed")  # handled below as an empty result
            prober.seeds = working
            active_intact: set[int] = set()
            for _, o in passing[:K]:
                active_intact.update(int(p) for p in o.active_positions)
            trace["n_active_intact"] = len(active_intact)
            v0 = prober.keep([])
            trace["tests"].append({"stage": "baseline:keep_nothing", "passed": v0.passed, "score": round(v0.score, 3)})
            if v0.passed:
                direct = True
                st.members, st.best_sufficient = [], set()
                trace["stages"].append("stimulus + readout alone satisfy the criterion: direct pathway, empty core")
            # ---------------------------------------------------------- stage 1: structural prior and posterior
            external = None
            if cfg.get("prior"):
                external = {int(k): float(min(1.0, max(0.0, v))) for k, v in dict(cfg["prior"]).items()}
                trace["external_prior"] = {"n_given": len(external), "n_candidates_covered": sum(1 for p in cand if p in external),
                                           "mass": round(sum(external.values()), 3)}
            prior = structural_prior(problem, active_intact, hops=int(cfg["hops"]), decay=float(cfg["hop_decay"]),
                                     inactive_factor=float(cfg["inactive_factor"]), external=external, external_weight=float(cfg["prior_weight"]))
            trace["n_candidates"] = len(cand)
            trace["n_possible"] = len(prior.order)
            trace["n_impossible"] = len(prior.impossible)
            order = prior.order + prior.impossible  # impossible ones last: only reached if nothing else passes
            q0 = self._q0(prior, order, cfg)
            post = Posterior(q0, prior.rank, float(cfg["false_pass"]), float(cfg["false_fail"]))
            engine = Engine(prober, post, cfg, trace)
            if not direct:
                # ------------------------------------------------------ stage 2-4: localise, eliminate, clean up
                if not engine.localise(order, set(), set(), st, "primary"):
                    trace["stages"].append("no keep-only prefix passed (non-monotone: the full candidate set does not pass as keep-only)")
                    raise BudgetExhausted("localisation failed")
                trace["pool_size"] = len(st.pool or [])
                trace["stages"].append(f"pool of {len(st.pool or [])} localised")
                engine.eliminate(set(), st, "primary")
                trace["stages"].append(f"elimination: {len(st.confirmed)} confirmed with {st.n_elim_tests} group probes")
                st.members = engine.cleanup(st.members, st, "primary")
                trace["stages"].append(f"cleanup: {len(st.members)} members")
            # ---------------------------------------------------------- stage 5: fresh-seed fidelity and add-back
            fresh = [base + 500 + j for j in range(int(cfg["fresh_seeds"]))]
            vf = prober.keep(st.members, seeds=fresh) if fresh else None
            if vf is not None:
                fidelity["keep_only_pass_fraction_fresh"] = vf.frac
                fidelity["keep_only_score_fresh"] = round(vf.score, 4)
                if not vf.passed and not direct and st.pool:
                    failing = [s for s, o in zip(fresh, vf.outs) if not o.passed]
                    discarded = [i for i in st.pool if i not in set(st.members)]
                    order_add = sorted(discarded, key=lambda i: (-post.q[i], prior.rank[i]))[: int(cfg["max_addback"])]
                    for j in order_add:
                        vj = prober.keep(set(st.members) | {j}, seeds=failing)
                        trace["tests"].append({"stage": "addback", "member": j, "passed_on_failing_fresh": vj.passed, "score": round(vj.score, 3)})
                        if vj.passed:
                            vw = prober.keep(set(st.members) | {j})
                            if vw.passed:
                                st.members = sorted(set(st.members) | {j})
                                added_back.append(j)
                                post.q[j] = max(post.q[j], 0.5)
                                vf2 = prober.keep(st.members, seeds=fresh)
                                fidelity["keep_only_pass_fraction_fresh"] = vf2.frac
                                fidelity["keep_only_score_fresh"] = round(vf2.score, 4)
                                if vf2.passed:
                                    break
                                failing = [s for s, o in zip(fresh, vf2.outs) if not o.passed]
                            else:
                                trace["antagonists"].append(j)
                                trace["non_monotone_events"].append({"kind": "addback_breaks_working_seeds", "neuron": j})
            # ---------------------------------------------------------- stage 6: essentiality (full-network silencing)
            ess_max = float(cfg["essential_pass_max"])
            n_ess_seeds: dict[int, int] = {}
            for i in sorted(st.members, key=lambda i: -post.q[i]):
                vs = prober.sil([i])
                essential_frac[i], n_ess_seeds[i] = vs.frac, K
                essential[i] = bool(vs.frac <= ess_max)
                trace["tests"].append({"stage": "essential", "member": i, "pass_fraction_silenced": vs.frac, "score": round(vs.score, 3)})

            def absorb_context(nec: list[int], clr: list[int], amb: list[int], label: str) -> None:
                """Bookkeeping shared by the necessity screen and the spend-down: cleared / ambiguous / new context members."""
                for i in clr:
                    post.scale([i], 0.2)
                for i in amb:
                    post.q[i] = max(post.q[i], 0.4)
                if not nec:
                    trace["stages"].append(f"{label}: no context member among {len(clr)} cleared, {len(amb)} ambiguous")
                    return
                context_members.extend(i for i in nec if i not in context_members)
                for i in nec:
                    post.q[i] = max(post.q[i], 0.9)
                    essential[i], essential_frac[i], n_ess_seeds[i] = True, 0.0, K
                st.members = sorted(set(st.members) | set(nec))  # first: a budget stop in the checks below must not lose them
                trace["stages"].append(f"{label}: {len(nec)} context member(s) added, {len(clr)} cleared, {len(amb)} ambiguous")
                if sim.remaining >= K:
                    vk = prober.keep(st.members)
                    if not vk.passed:
                        trace["non_monotone_events"].append({"kind": "context_members_break_keep_only", "neurons": list(nec)})
                if fresh and sim.remaining >= len(fresh):
                    vf3 = prober.keep(st.members, seeds=fresh)
                    fidelity["keep_only_pass_fraction_fresh"] = vf3.frac
                    fidelity["keep_only_score_fresh"] = round(vf3.score, 4)
                    fidelity["n_fresh_seeds"] = len(fresh)

            # ---------------------------------------------------------- stage 6b: necessity screen outside the core
            if not direct and st.members and float(cfg["necessity_share"]) > 0:
                share = int(float(cfg["necessity_share"]) * sim.remaining)
                core_now = set(st.members)
                ctx = [i for i in prior.order if i in active_intact and i not in core_now and i not in essential_frac]
                Wc = problem.W.tocsr()
                ro = problem.readout_positions
                for i in ctx:
                    conn = float(abs(Wc[list(core_now), i]).sum() + abs(Wc[i, list(core_now)]).sum()) if core_now else 0.0
                    conn += float(abs(Wc[ro, i]).sum()) if len(ro) else 0.0
                    rel[i] = prior.score[i] + math.log1p(conn)
                nec, clr, amb, ctx_untested = engine.necessity_screen(ctx, rel, problem.signs, share, K)
                trace["necessity_screen"] = {"n_candidates": len(ctx), "share_calls": share, "necessary": nec, "n_cleared": len(clr), "ambiguous": amb,
                                             "n_untested": len(ctx_untested)}
                absorb_context(nec, clr, amb, "necessity screen")
            # ---------------------------------------------------------- stage 7: backups / alternative implementations
            if not direct and st.members:
                order_alt = [i for i in order if i not in set(st.members)]
                for m in sorted(st.members, key=lambda i: (essential_frac.get(i, 0.0) < 1.0, i)):
                    if len(alternatives) >= int(cfg["max_alternatives"]) or sim.remaining < int(cfg["alt_min_calls"]):
                        break
                    if essential_frac.get(m, 0.0) < 1.0:
                        continue  # silencing m alone does not keep the function on every working seed: no backup to find
                    if any(m not in a for a in alternatives):
                        continue  # an alternative that avoids m is already known
                    forced = set(st.members) - {m}
                    st_alt = SearchState()
                    post_alt = Posterior({**self._q0(prior, order_alt, cfg), **{i: 0.9 for i in forced}}, prior.rank, float(cfg["false_pass"]),
                                         float(cfg["false_fail"]))
                    eng_alt = Engine(prober, post_alt, cfg, trace)
                    if not eng_alt.localise(order_alt, forced, {m}, st_alt, f"alt[{m}]"):
                        trace["non_monotone_events"].append({"kind": "no_backup_pool_although_silencing_passes", "neuron": m})
                        continue
                    eng_alt.eliminate(forced, st_alt, f"alt[{m}]")
                    alt = eng_alt.cleanup(sorted(forced) + st_alt.confirmed, st_alt, f"alt[{m}]")
                    alt = sorted(alt)
                    if alt and set(alt) != set(st.members) and alt not in alternatives:
                        alternatives.append(alt)
                        for i in alt:
                            if i not in set(st.members):
                                alt_probs[i] = max(alt_probs.get(i, 0.0), float(cfg["alt_weight"]) * post_alt.q[i])
                    trace["stages"].append(f"backup search for {m}: {'found ' + str(alt) if alt else 'nothing'}")
            # ---------------------------------------------------------- stage 8: robust fidelity (widened parameter sds)
            if cfg.get("robust_check") and fresh and st.members and sim.remaining >= len(fresh):
                mc = problem.model_cfg
                wide = {"tau_sd": mc.tau_sd * 2, "a_sd": mc.a_sd * 2, "theta_sd": mc.theta_sd * 2, "r_max_sd": mc.r_max_sd * 2}
                vr = prober.keep(st.members, seeds=fresh, cfg_override=wide)
                fidelity["keep_only_pass_fraction_robust_sd_x2"] = vr.frac
            # ---------------------------------------------------------- stage 9: spend-down of leftover budget on calibration
            if not direct and st.members and sim.remaining > 0:
                extra_seeds = [base + 200 + j for j in range(int(cfg["essential_extra_seeds"]))]
                if extra_seeds and sim.remaining >= len(extra_seeds) * (len(st.members) + 1) + 2 * len(fresh):
                    # essentiality is only defined on seeds where the intact network passes
                    ok_seeds = [s for s, o in zip(extra_seeds, prober.intact(extra_seeds)) if o.passed]
                    for i in list(st.members) if ok_seeds else []:
                        vs2 = prober.sil([i], seeds=ok_seeds)
                        n_old = n_ess_seeds.get(i, K)
                        essential_frac[i] = (essential_frac.get(i, 0.0) * n_old + vs2.frac * len(ok_seeds)) / (n_old + len(ok_seeds))
                        n_ess_seeds[i] = n_old + len(ok_seeds)
                        essential[i] = bool(essential_frac[i] <= ess_max)
                    trace["stages"].append(f"spend-down: essentiality re-checked on {len(ok_seeds)} extra passing seed(s) of {len(extra_seeds)}")
                more = [base + 600 + j for j in range(int(cfg["fresh_seeds"]))]
                if more and sim.remaining >= len(more) + 2:
                    vf4 = prober.keep(st.members, seeds=more)
                    n_old = fidelity.get("n_fresh_seeds", len(fresh))
                    f_old = fidelity.get("keep_only_pass_fraction_fresh", vf4.frac)
                    fidelity["keep_only_pass_fraction_fresh"] = (f_old * n_old + vf4.frac * len(more)) / (n_old + len(more))
                    fidelity["n_fresh_seeds"] = n_old + len(more)
                if ctx_untested and float(cfg["spend_down_share"]) > 0:
                    share2 = int(float(cfg["spend_down_share"]) * sim.remaining)
                    todo = [i for i in ctx_untested if i not in set(st.members)]
                    nec2, clr2, amb2, ctx_untested = engine.necessity_screen(todo, rel, problem.signs, share2, K, tag="spend_down_necessity")
                    trace["spend_down_necessity"] = {"n_candidates": len(todo), "share_calls": share2, "necessary": nec2, "n_cleared": len(clr2),
                                                     "ambiguous": amb2, "n_untested": len(ctx_untested)}
                    absorb_context(nec2, clr2, amb2, "spend-down necessity")
        except BudgetExhausted as e:
            trace["budget_exhausted"] = True
            trace["stages"].append(f"stopped: {e}")
        # -------------------------------------------------------------- assembly
        if st.members:
            core = sorted(int(p) for p in st.members)
        elif st.best_sufficient is not None:
            core = sorted(int(p) for p in st.best_sufficient)
        elif st.pool:
            core = sorted(int(p) for p in st.pool)
        else:
            core = []
        core_set = set(core)
        incl: dict[int, float] = {}
        for p in cand:
            if post is not None and p in post.q:
                incl[p] = post.q[p]
            else:
                incl[p] = 0.0
        if prior is not None:
            for p in prior.impossible:
                incl[p] = 0.0
        for p, q in alt_probs.items():
            incl[p] = max(incl.get(p, 0.0), q)
        if not st.members and core:  # unverified fallback (budget ran out before a minimal set was reached)
            for p in core:
                incl[p] = min(incl.get(p, 0.5), 0.5)
        roles, loop = generic_roles(problem, core, [p for a in alternatives for p in a if p not in core_set], crit_type)
        for p in added_back:
            roles[p] = ("modulatory_supporting", 0.6)
        for p in context_members:  # necessary in the full network but not needed in isolation: keeps the context in check
            if problem.signs[p] < 0:
                roles[p] = ("lateral_inhibition" if crit_type == "selectivity" else "gain_control", 0.6)
            elif problem.signs[p] > 0:
                roles[p] = ("modulatory_supporting", 0.55)
        ess_out: dict[int, bool | None] = {p: essential.get(p) for p in core}
        # working-seed fidelity of the reported core (cache hit when it was probed already)
        try:
            if core_set == set(st.members) and st.members:
                vw = prober.keep(core)
                fidelity["keep_only_pass_fraction_working"] = vw.frac
                fidelity["keep_only_score_working"] = round(vw.score, 4)
                fidelity["keep_only_frequency_hz"] = vw.frequency_hz
                fidelity["keep_only_n_active_readout"] = vw.n_active_readout
        except BudgetExhausted:
            pass
        freqs = [o.frequency_hz for o in intact_outs if o.frequency_hz is not None and o.passed]
        f_hz = float(np.median(freqs)) if freqs else fidelity.get("keep_only_frequency_hz")
        n_ro = [o.n_active_readout for o in intact_outs if o.passed]
        preserved = fidelity.get("keep_only_pass_fraction_fresh", fidelity.get("keep_only_pass_fraction_working"))
        n_e = sum(1 for p in core if problem.signs[p] > 0)
        n_i = sum(1 for p in core if problem.signs[p] < 0)
        motif = (f"{n_e} excitatory + {n_i} inhibitory members; loop of {len(loop)}; {len(alternatives)} alternative(s); "
                 f"criterion {crit_type}; found by adaptive group testing on keep-only pools")
        n_single = len(cand) * K
        trace.update({"n_keep_only_calls": prober.n_keep, "n_silence_calls": prober.n_silence, "n_intact_calls": prober.n_intact,
                      "keep_only_sizes_mean": round(float(np.mean(prober.keep_sizes)), 1) if prober.keep_sizes else None,
                      "single_deletion_equivalent_calls": n_single, "pool_single_deletion_calls": (len(st.pool) if st.pool else 0) * K,
                      "elimination_group_probes": st.n_elim_tests, "confirmed_by_elimination": st.confirmed, "added_back": added_back,
                      "essential_pass_fraction_silenced": essential_frac, "removal_signature": st.removal_info, "direct_pathway": direct,
                      "context_members": context_members, "n_context_untested": len(ctx_untested),
                      "posterior_mass_total": round(sum(incl.values()), 3) if incl else 0.0, "n_alternatives": len(alternatives)})
        return DiscoveryResult(core=core, inclusion_probability=incl, roles=roles, essential=ess_out, alternatives=alternatives, loop=loop,
                               predicted_frequency_hz=f_hz, predicted_n_active_readout=int(np.median(n_ro)) if n_ro else None,
                               predicted_function_preserved=(preserved >= 0.5) if preserved is not None else None, fidelity=fidelity,
                               budget={**sim.report(), "wall_s": round(time.time() - t0, 2)}, diagnostics=trace, motif=motif)
