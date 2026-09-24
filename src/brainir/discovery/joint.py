"""Cross-connectome shared-mechanism discovery (component F): discover one abstract mechanism in two networks and align it.

    pair = discover_pair(a, b, "greedy_reference", budget_a=400, budget_b=400, seed=0, mode="joint")
    python -m brainir.discovery.joint --pair <instance dir> --method NAME --mode joint --budget-a 400 --budget-b 400 --seed 0 --out r.json

Two networks (two connectomes, or the two halves of a synthetic pair) may implement the same abstract mechanism with
different neurons. Only PUBLIC evidence crosses between them: the anchor-fingerprint correspondence candidates of
:mod:`brainir.discovery.correspondence` (ranked hypotheses with z-scores, never identities) and the public wiring (role
graphs of :mod:`brainir.discovery.transfer`). Every simulation goes through a :class:`BudgetedSimulator` of the network it
runs on (one cache per network, one simulator per phase, only one phase open at a time), calls spent testing a mechanism
carried over from the other network are reported separately as ``adaptation``, and the total never exceeds
``budget_a + budget_b``.

Modes
    independent  base method on A (budget_a) and on B (budget_b); nothing is shared (the baseline).
    transfer     base method on A; B's mechanism = ``transfer_core`` of A's core with adaptation budget budget_b (no discovery on B).
    prior        base method on A; base method on B (budget_b) with ``config["prior"]`` = A's inclusion probabilities carried
                 through the correspondence (spread over the top-k candidates with a 'none of these' option).
    joint        cross-verified discovery (research/phase2/methods/joint.md):
                   1. the lead network (fewer candidates) is solved by the base method with its own budget;
                   2. its mechanism is carried to the follower and VERIFIED there with cheap keep-only probes (the structural
                      image — anchor-fingerprint z-scores plus reproduced signed member edges, beam search — then the top-1
                      image, then the union of the top-k images), minimised by group elimination that keeps members whose
                      silencing in the full network breaks the function, completed with counterparts of the lead's essential
                      members, and validated on fresh seeds (adaptation calls). It counts as verified only if it is validated on
                      at least two fresh seeds, completely minimised, every member essential in the lead has an essential
                      counterpart in the image, and the follower's intact network relies on the image (a member, or else the
                      whole image, is necessary there) — the causal structure is reproduced, not only sufficiency: a network
                      usually has sufficient sets near any image (a hub that could drive the readout alone, a silent copy, the
                      mechanism of another family), but not ones it relies on whose essential members correspond; the lead's
                      core is then consistency-pruned;
                   3. only when that fails is the base method run on the follower, with the transported prior and every call
                      the pool has left (never less than the follower's own budget while the pool allows it);
                   4. alternating verified transfers, follower -> lead first: the receiving network keeps its own mechanism
                      unless its OWN evidence prefers the carried-over one — its own mechanism is empty or fails validation, or
                      the carried-over set is a strict subset of it, or its intact network relies decisively more (silencing,
                      per distinctive member) on the carried-over set; a set that drops a member it found essential is never
                      adopted, and agreement with the other network (role graphs, correspondence) is never evidence; the
                      carried-over set otherwise becomes an alternative; stop when the two mechanisms are linked by a
                      verified transfer (no calls);
                   5. consistency pruning: a core is shrunk to the members whose counterparts survived in the verified image,
                      if its keep-only still passes and silencing the pruned members does not break the function.

Identity claims (``PairResult.correspondence``) are made only between two cores that a verified transfer links (one is the
other's verified image), only for member pairs that the transfer matched, and only when the anchor-fingerprint evidence beats
'none' in both directions; independent, prior and transfer modes make none. Nothing here reads a truth file; the pair scorer
lives elsewhere.
"""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from scipy.sparse.csgraph import connected_components

from .correspondence import fingerprints, match_candidates, null_match_scores, shared_anchor_types
from .interface import DiscoveryMethod, DiscoveryResult, MethodRegistry
from .interventions import keep_only, silence
from .problem import DiscoveryProblem, path_basename
from .simulator import BudgetedSimulator, BudgetExhausted, SimQuery
from .transfer import role_graph, role_graph_similarity, transfer_core

MODES = ("independent", "transfer", "prior", "joint")
REJECT_ESSENTIAL = "essential structure not reproduced"
REJECT_RELIANCE = "the intact network does not rely on the image"
CAUSAL_REJECTIONS = (REJECT_ESSENTIAL, REJECT_RELIANCE)
"""Reasons a sufficient, minimised image is not a verified transfer: the destination's own simulations show it is not the mechanism."""
KINDS = ("discovery", "evaluation", "adaptation", "validation")
"""Ledger categories: base-method discovery, transfer mode's top-1 evaluation, adaptation (testing a mechanism carried over
from the other network: probes, minimisation, essentiality of its members, its validation) and validation of a network's
own mechanism (fresh-seed check, consistency pruning)."""

DEFAULT_CONFIG: dict = {
    "method_config": {},        # passed to the base method on both networks (merged over its default_config)
    "method_config_a": {},      # per-network overrides
    "method_config_b": {},
    "k": 3,                     # correspondence candidates per member: prior spread, union probe, transfer_core's k
    "assign_k": 6,              # candidates per member in the structural alignment (beam search)
    "edge_bonus": 2.0,          # structural alignment: bonus (in z units) per reproduced signed edge among the members
    "beam": 64,                 # beam width of the structural alignment
    "temperature": 1.0,         # softmax temperature over candidate z-scores
    "n_null": 50,               # random interneurons whose best-match z sets the 'none of these' logit
    "corr_weights": None,       # correspondence feature weights (None = correspondence.DEFAULT_WEIGHTS)
    "prior_rho": 0.8,           # P(a source member's counterpart is among its top-k candidates)
    "prior_base": 0.02,         # prior inclusion probability of candidates the correspondence does not point to
    "prior_min_q": 0.1,         # source positions below this inclusion probability are not transported
    "prior_max_members": 64,    # at most this many source positions are transported (highest probability first)
    "prior_damp_failed_transfer": 0.5,  # joint: rho multiplier after the verified transfer failed
    "probe_seeds": 3,           # seeds per keep-only / silencing decision (strict majority, sequential early stop)
    "validation_seeds": 2,      # fresh seeds for validating a core (accepted at pass fraction >= 0.5)
    "transfer_seeds": 2,        # transfer mode: seeds of transfer_core's pass fraction
    "adapt_min_fraction": 0.1,  # joint: adaptation allowance on the follower >= this fraction of its budget ...
    "adapt_max_fraction": 0.3,  # ... and <= this fraction; in between it is funded by the lead's unused calls
    "lead": "auto",             # joint: "auto" (fewer candidates leads; tie -> a), "a" or "b"
    "max_rounds": 3,            # joint: alternating verified transfers after the follower's own discovery (0 = none)
    "consistency_prune": True,  # joint: shrink a core to the members whose counterparts survived (verified by simulation)
    "claim_min_confidence": 0.1,  # identity claims below this calibrated probability are not emitted
    "min_validation_seeds": 2,  # a transfer is verified only if its keep-only passes on >= half of at least this many fresh seeds
    "require_essential_structure": True,  # ... and only if every member essential in the source has an essential counterpart in the image
    "require_reliance": True,   # ... and only if the destination's intact network relies on the image (a member, or all of it, is necessary)
    # identity probability p = sigmoid(a + b * logit(dual-softmax fingerprint probability) + c * reproduced signed member edges), fitted
    # (b, c >= 0) on verified-transfer pairs of synthetic pairs and checked on held-out pairs (research/phase2/BRAINIR_V1_METHOD.md 12.6)
    "identity_calibration": [1.2988, 0.2166, 1.8127],
    "claim_k": 5,               # fingerprint candidates per member (plus 'none') in the identity probability of a claim
    "claims_require_verified_link": True,  # identity claims only between cores linked by a verified transfer (False: any two cores)
    "claims_require_complete_image": True,  # ... and only if the link pairs up all members of both cores one to one
    "adoption": "own_evidence",  # joint rounds: "own_evidence" (see prefer_shared) or "never" (a validated own mechanism is kept)
    "reliance_margin": 0.05,    # decisive reliance difference per distinctive member (absolute) ...
    "reliance_rel_margin": 0.25,  # ... and relative to the larger reliance; every replicate must agree on the sign
}


# ---------------------------------------------------------------------------- result type
@dataclass
class PairResult:
    result_a: DiscoveryResult
    result_b: DiscoveryResult
    correspondence: list[tuple[int, int, float]]
    """(pos_a, pos_b, confidence) for members claimed to correspond (mutual best within the two cores)."""
    role_alignment: dict
    """{role: {"a": [positions], "b": [positions]}} plus "role_graph_similarity": float."""
    budget: dict
    """{"a": calls, "b": calls, "adaptation": calls, "total": calls, ...}; total = a + b + adaptation <= budget_a + budget_b."""
    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"result_a": self.result_a.to_dict(), "result_b": self.result_b.to_dict(),
                "correspondence": [[int(x), int(y), float(c)] for x, y, c in self.correspondence], "role_alignment": self.role_alignment,
                "budget": self.budget, "diagnostics": self.diagnostics}


def get_method(name: str) -> DiscoveryMethod:
    """A registered method; a module ``brainir.methods.<name>`` that registers itself on import is loaded on demand."""
    try:
        return MethodRegistry.get(name)
    except KeyError:
        if not name.isidentifier():
            raise
        try:
            importlib.import_module(f"brainir.methods.{name}")
        except ImportError:
            raise KeyError(f"unknown discovery method {name!r}") from None
        return MethodRegistry.get(name)


# ---------------------------------------------------------------------------- budget ledger
class _Ledger:
    """Hard cap over both networks. Each phase gets a FRESH simulator (a base method always starts at calls == 0 with
    remaining == its allowance) that shares its network's cache (a query is paid once); opening a phase closes the previous
    one, so the total can never exceed the cap."""

    def __init__(self, problems: dict[str, DiscoveryProblem], total: int, workers: int):
        self.problems = problems
        self.total = int(total)
        self.workers = int(workers)
        self.cache: dict[str, dict] = {net: {} for net in problems}
        self.entries: list[dict] = []

    def spent(self, net: str | None = None, kind: str | None = None) -> int:
        tot = 0
        for e in self.entries:
            if net is not None and e["net"] != net:
                continue
            for k, v in (e["split"] or {e["kind"]: e["sim"].calls}).items():
                if kind is None or k == kind:
                    tot += int(v)
        return tot

    def left(self) -> int:
        return self.total - self.spent()

    def open(self, net: str, kind: str, cap: float) -> BudgetedSimulator:
        for e in self.entries:
            e["sim"].close()
        allowance = int(max(0, min(int(cap), self.left())))
        sim = BudgetedSimulator(self.problems[net], max_calls=allowance, workers=self.workers, cache=self.cache[net])
        self.entries.append({"net": net, "kind": kind, "sim": sim, "split": None, "allowance": allowance})
        return sim

    def split_last(self, split: dict[str, int]) -> None:
        e = self.entries[-1]
        assert sum(split.values()) == e["sim"].calls, (split, e["sim"].calls)
        e["split"] = {k: int(v) for k, v in split.items()}

    def report(self) -> dict:
        by = {net: {k: self.spent(net, k) for k in KINDS} for net in self.problems}
        out = {net: sum(v for k, v in by[net].items() if k != "adaptation") for net in self.problems}
        out |= {"adaptation": by["a"]["adaptation"] + by["b"]["adaptation"], "adaptation_a": by["a"]["adaptation"],
                "adaptation_b": by["b"]["adaptation"], "total": self.spent(), "limit": self.total, "by_kind": by,
                "cache_hits": {net: sum(e["sim"].cache_hits for e in self.entries if e["net"] == net) for net in self.problems},
                "phases": [{"net": e["net"], "kind": e["kind"], "allowance": e["allowance"], "calls": e["sim"].calls,
                            **({"split": e["split"]} if e["split"] else {})} for e in self.entries]}
        assert out["total"] == out["a"] + out["b"] + out["adaptation"] <= self.total
        return out


# ---------------------------------------------------------------------------- simulation decisions
class _Prober:
    """Strict-majority keep-only / silencing decisions over a few parameter seeds, run one seed at a time with early stopping.
    ``None`` = the phase ran out of calls before the decision was made."""

    def __init__(self, problem: DiscoveryProblem, sim: BudgetedSimulator, seeds: list[int]):
        self.problem, self.sim, self.seeds = problem, sim, [int(s) for s in seeds]
        self.n_decisions = 0

    def decide(self, iv) -> bool | None:
        need = len(self.seeds) // 2 + 1
        n_pass = n_fail = 0
        self.n_decisions += 1
        for s in self.seeds:
            try:
                o = self.sim.run(SimQuery(iv, s))
            except BudgetExhausted:
                return None
            if o.passed:
                n_pass += 1
            else:
                n_fail += 1
            if n_pass >= need:
                return True
            if n_fail > len(self.seeds) - need:
                return False
        return n_pass >= need

    def keep(self, positions) -> bool | None:
        return self.decide(keep_only(self.problem, positions))

    def silenced(self, positions) -> bool | None:
        return self.decide(silence(positions))

    def fraction(self, positions, seeds: list[int]) -> tuple[float | None, list]:
        outs = []
        for s in seeds:
            try:
                outs.append(self.sim.run(SimQuery(keep_only(self.problem, positions), int(s))))
            except BudgetExhausted:
                break
        return (float(np.mean([o.passed for o in outs])) if outs else None), outs


READOUT_STATS = ("score", "readout_peak_median_hz", "n_active_readout", "frequency_hz", "readout_range_median_hz", "readout_mean_hz",
                 "group_a_mean_hz", "group_b_mean_hz", "readout_during_hz", "readout_after_hz", "relative_slope_per_s")


def _readout_change(o0, o1) -> float:
    """Mean relative change (each term in [0, 1]) of the readout statistics an outcome carries (criterion score, readout activity,
    rhythm frequency, criterion-specific means) between two outcomes; statistics absent or zero in both are skipped."""
    terms = []
    for k in READOUT_STATS:
        a = getattr(o0, k) if hasattr(o0, k) else (o0.extra or {}).get(k)
        b = getattr(o1, k) if hasattr(o1, k) else (o1.extra or {}).get(k)
        if a is None and b is None:
            continue
        a, b = (0.0 if a is None else float(a)), (0.0 if b is None else float(b))
        den = max(abs(a), abs(b))
        if np.isfinite(den) and den > 1e-12:
            terms.append(min(1.0, abs(a - b) / den))
    return float(np.mean(terms)) if terms else 0.0


def _minimize(pr: _Prober, members: list[int], order: list[int], *, check_essential: bool = True) -> dict:
    """1-minimal passing subset of a passing keep-only set by adaptive group elimination (groups of low-support members first,
    doubling after a success, halving after a failure). A group is removed only if keep-only of the rest still passes AND (with
    ``check_essential``) silencing the group in the FULL network keeps the function — so a member that is essential in the full
    network but redundant under keep-only (e.g. an inhibitor that keeps a competitor silent) is kept."""
    S = [int(q) for q in members]
    queue = [int(q) for q in order if q in set(S)]
    necessary: set[int] = set()
    essential: dict[int, bool] = {}
    removed: list[int] = []
    chunk = max(1, len(queue) // 2)
    complete = True
    while queue:
        X = queue[: max(1, min(chunk, len(queue)))]
        rest = [q for q in S if q not in set(X)]
        if not rest:  # never empty the set
            if len(X) == 1:
                necessary.add(X[0])
                queue = queue[1:]
            else:
                chunk = max(1, len(X) // 2)
            continue
        r = pr.keep(rest)
        if r and check_essential:
            r = pr.silenced(X)
            if r is False and len(X) == 1:
                essential[X[0]] = True
        if r is None:
            complete = False
            break
        if r:
            S = rest
            removed.extend(X)
            queue = queue[len(X):]
            chunk *= 2
            for q in X:
                essential.setdefault(q, False)
        elif len(X) > 1:
            chunk = max(1, len(X) // 2)
        else:
            if X[0] not in essential:
                necessary.add(X[0])
            queue = queue[1:]
    return {"core": sorted(S), "necessary": sorted(necessary), "essential": essential, "removed": sorted(removed), "complete": complete}


# ---------------------------------------------------------------------------- roles (public wiring only, no calls)
def infer_roles(problem: DiscoveryProblem, core) -> dict[int, tuple[str, float]]:
    """Generic roles from each member's sign, its place in the core's own wiring (self-loop, strongly connected component,
    all-excitatory cycle, projection onto the readout / other members / readout groups) and the criterion type."""
    core = sorted({int(p) for p in core})
    if not core:
        return {}
    sub = problem.W[core][:, core].toarray()  # post x pre among members
    _, lab = connected_components(sub != 0, directed=True, connection="strong")
    Wc = problem.W.tocsc()
    crit = str(problem.criterion_spec.get("type", ""))
    ro = problem.readout_mask
    ga = {int(x) for x in problem.criterion_spec.get("group_a_positions") or []}
    gb = {int(x) for x in problem.criterion_spec.get("group_b_positions") or []}
    out: dict[int, tuple[str, float]] = {}
    for i, p in enumerate(core):
        s = int(problem.signs[p])
        rows = Wc.indices[Wc.indptr[p]:Wc.indptr[p + 1]]
        vals = np.abs(Wc.data[Wc.indptr[p]:Wc.indptr[p + 1]])
        to_ro = float(vals[ro[rows]].sum()) if len(rows) else 0.0
        to_a = float(sum(v for r, v in zip(rows, vals) if int(r) in ga))
        to_b = float(sum(v for r, v in zip(rows, vals) if int(r) in gb))
        comp = [j for j in range(len(core)) if lab[j] == lab[i]]
        self_loop = sub[i, i] != 0
        in_cycle = len(comp) > 1 or self_loop
        exc_cycle = in_cycle and all(int(problem.signs[core[j]]) > 0 for j in comp)
        to_members = any(sub[j, i] != 0 for j in range(len(core)) if j != i)
        if s == 0:
            role = ("unknown", 0.3)
        elif crit == "selectivity":
            if s < 0:
                role = ("lateral_inhibition", 0.7)
            elif to_a > 0 and to_a >= to_b:
                role = ("output_driver", 0.7)
            elif to_b > 0:
                role = ("competitor", 0.6)
            else:
                role = ("input_relay", 0.5)
        elif s < 0:
            role = ("inhibitory_feedback", 0.7) if crit == "rhythm" else ("gain_control", 0.6)
        elif self_loop or exc_cycle:
            role = ("state_memory", 0.7) if crit in ("persistence", "ramp") else ("recurrent_excitatory_core", 0.6)
        elif in_cycle and to_ro > 0:
            role = ("recurrent_excitatory_core", 0.6) if crit == "rhythm" else ("output_driver", 0.6)
        elif to_ro > 0:
            role = ("output_driver", 0.6)
        elif to_members:
            role = ("input_relay", 0.5)
        else:
            role = ("modulatory_supporting", 0.3)
        out[p] = role
    return out


def core_loop(problem: DiscoveryProblem, core) -> list[int]:
    """Members on a recurrent loop of the core's own wiring (non-trivial strongly connected components and self-loops)."""
    core = sorted({int(p) for p in core})
    if not core:
        return []
    sub = problem.W[core][:, core].toarray()
    _, lab = connected_components(sub != 0, directed=True, connection="strong")
    sizes = np.bincount(lab)
    return [p for i, p in enumerate(core) if sizes[lab[i]] > 1 or sub[i, i] != 0]


def _fill_roles(problem: DiscoveryProblem, res: DiscoveryResult) -> int:
    """Give every core member without a (known) role the inferred generic role; the base method's roles are kept."""
    inferred = infer_roles(problem, res.core)
    n = 0
    for p in res.core:
        r = res.roles.get(p)
        if r is None or r[0] == "unknown":
            res.roles[int(p)] = inferred[int(p)]
            n += 1
    return n


# ---------------------------------------------------------------------------- correspondence with uncertainty
class _Corr:
    """Anchor-fingerprint correspondence in both directions, fingerprints computed once. Candidate probabilities: softmax of
    z / temperature over the top-k candidates plus a 'none of these' option whose logit is the typical best-match z of random
    interneurons (so an indistinct favourite gets little mass and two look-alikes, e.g. a member and its decoy, share it)."""

    def __init__(self, problems: dict[str, DiscoveryProblem], cfg: dict, seed: int):
        self.P = problems
        self.k = int(cfg["k"])
        self.temperature = float(cfg["temperature"])
        self.n_null = int(cfg["n_null"])
        self.weights = cfg.get("corr_weights")
        self.seed = int(seed)
        self.anchors = shared_anchor_types(problems["a"], problems["b"])
        self.fp = {net: fingerprints(p, self.anchors) for net, p in problems.items()}
        self._null: dict[tuple[str, str], float] = {}

    def match(self, src: str, dst: str, positions, *, k: int | None = None) -> dict:
        pos = sorted({int(p) for p in positions})
        if not pos:
            return {}
        return match_candidates(self.P[src], self.P[dst], pos, k=int(k or self.k), weights=self.weights, fa=self.fp[src],
                                fb=self.fp[dst])["per_neuron"]

    def null_z(self, src: str, dst: str) -> float:
        if (src, dst) not in self._null:
            z = 0.0
            try:
                z = float(null_match_scores(self.P[src], self.P[dst], [], n_null=self.n_null, seed=self.seed, weights=self.weights,
                                            fa=self.fp[src], fb=self.fp[dst])["z_mean"])
            except (ValueError, IndexError):  # no interneurons to sample
                pass
            self._null[(src, dst)] = z
        return self._null[(src, dst)]

    def spread(self, src: str, dst: str, info: dict, *, k: int | None = None) -> list[tuple[int, float]]:
        cands = (info or {}).get("candidates", [])[: int(k or self.k)]
        if not cands:
            return []
        logits = np.array([c["z"] for c in cands] + [self.null_z(src, dst)], dtype=float) / max(self.temperature, 1e-6)
        w = np.exp(logits - logits.max())
        w /= w.sum()
        if float(info.get("coverage", 1.0)) <= 0.0:  # no anchor contact: only annotations speak for the match
            w = w * 0.25
        return [(int(c["position"]), float(x)) for c, x in zip(cands, w[:-1])]

    def identity(self, src: str, dst: str, pa: int, pb: int, *, k: int) -> dict:
        """Fingerprint evidence that ``pa`` (in src) and ``pb`` (in dst) are the same neuron, in both directions and against the
        'none of these' option: w_ab = softmax weight of pb among pa's top-k candidates plus 'none' (logit = the null best-match z of
        tokenised interneurons), w_ba likewise; ``eligible`` iff each direction ranks the partner above 'none'; ``p_fp`` = w_ab x w_ba
        (dual softmax: high only when both directions agree)."""
        out = {}
        for tag, (s_, d_, q, r) in (("ab", (src, dst, pa, pb)), ("ba", (dst, src, pb, pa))):
            info = self.match(s_, d_, [q], k=k).get(int(q), {})
            w = dict(self.spread(s_, d_, info, k=k))
            out[f"w_{tag}"] = float(w.get(int(r), 0.0))
            out[f"none_{tag}"] = float(max(0.0, 1.0 - sum(w.values())))
        out["eligible"] = bool(out["w_ab"] > out["none_ab"] and out["w_ba"] > out["none_ba"])
        out["p_fp"] = float(out["w_ab"] * out["w_ba"])
        return out

    def assign(self, src: str, dst: str, members, *, K: int, lam: float, beam: int = 64, allowed=None) -> tuple[dict[int, int | None], dict]:
        """Structural alignment: beam search for the injective member -> candidate assignment maximising the sum of candidate z-scores
        plus ``lam`` per signed edge among the members (self-loops included) that is reproduced between the assigned candidates. A member
        may stay unassigned at the 'none of these' z. Candidates = each member's top-K by anchor fingerprint (restricted to ``allowed``)."""
        members = sorted({int(p) for p in members})
        if not members:
            return {}, {"score": 0.0}
        nz = self.null_z(src, dst)
        n_dst = len(self.P[dst].candidate_positions())
        per = self.match(src, dst, members, k=n_dst if allowed is not None else K)
        allow = None if allowed is None else {int(q) for q in allowed}
        cands = {p: [(int(c["position"]), float(c["z"])) for c in per.get(p, {}).get("candidates", []) if allow is None or c["position"] in allow][:K]
                 for p in members}
        pool = sorted({q for lst in cands.values() for q, _ in lst})
        idx = {q: j for j, q in enumerate(pool)}
        ss = np.sign(self.P[src].W[members][:, members].toarray())  # post x pre
        sd = np.sign(self.P[dst].W[pool][:, pool].toarray()) if pool else np.zeros((0, 0))
        order = sorted(range(len(members)), key=lambda i: (-max([z for _, z in cands[members[i]]], default=nz), members[i]))
        states: list[tuple[tuple[tuple[int, int], ...], float, int]] = [((), 0.0, 0)]
        for i in order:
            nxt = []
            for assign, sc, ne in states:
                used = {j for _, j in assign if j >= 0}
                for j, z in [(idx[q], z) for q, z in cands[members[i]] if idx[q] not in used] + [(-1, nz)]:
                    e = 0
                    if j >= 0:
                        if ss[i, i] != 0 and sd[j, j] == ss[i, i]:
                            e += 1
                        for i2, j2 in assign:
                            if j2 >= 0:
                                e += int(ss[i, i2] != 0 and sd[j, j2] == ss[i, i2]) + int(ss[i2, i] != 0 and sd[j2, j] == ss[i2, i])
                    nxt.append((assign + ((i, j),), sc + z + lam * e, ne + e))
            nxt.sort(key=lambda t: (-t[1], t[0]))
            states = nxt[:beam]
        best, score, n_edges = states[0]
        n_src_edges = int(np.count_nonzero(ss))
        return ({members[i]: (pool[j] if j >= 0 else None) for i, j in best},
                {"score": round(float(score), 4), "edges_reproduced": int(n_edges), "edges_source": n_src_edges, "null_z": round(nz, 4)})

    def transport(self, src: str, dst: str, result: DiscoveryResult, *, rho: float, base: float, min_q: float,
                  max_members: int) -> tuple[dict[int, float], dict]:
        """Prior inclusion probabilities over ALL candidates of ``dst`` from ``result`` (a mechanism of ``src``): noisy-OR over the
        source positions p of rho * q_p * w(p -> c), on top of a base rate (absent evidence stays below the neutral 0.5)."""
        probs = result.inclusion_probability or {}
        q = {int(p): float(v) for p, v in probs.items() if float(v) >= min_q}
        for p in result.core:
            q.setdefault(int(p), float(probs.get(p, 1.0)))
        members = sorted(q, key=lambda p: (-q[p], p))[: int(max_members)]
        cand = [int(c) for c in self.P[dst].candidate_positions()]
        stay = dict.fromkeys(cand, 1.0 - float(base))
        per = self.match(src, dst, members)
        for p in members:
            for c, w in self.spread(src, dst, per.get(p, {})):
                if c in stay:
                    stay[c] *= 1.0 - float(rho) * min(1.0, q[p]) * w
        prior = {c: float(1.0 - stay[c]) for c in cand}
        boosted = {c: v for c, v in prior.items() if v > float(base) + 1e-9}
        return prior, {"n_source_positions": len(members), "n_boosted": len(boosted), "expected_members": round(float(sum(prior.values())), 3),
                       "max": round(max(prior.values(), default=0.0), 4), "rho": float(rho), "base": float(base),
                       "top": sorted(((int(c), round(v, 4)) for c, v in boosted.items()), key=lambda t: -t[1])[:10]}


def transport_prior(src: DiscoveryProblem, dst: DiscoveryProblem, result: DiscoveryResult, *, seed: int = 0,
                    config: dict | None = None) -> dict[int, float]:
    """Public helper: the prior ``discover_pair`` hands to the base method on ``dst`` given ``result`` on ``src``."""
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    corr = _Corr({"a": src, "b": dst}, cfg, seed)
    prior, _ = corr.transport("a", "b", result, rho=cfg["prior_rho"], base=cfg["prior_base"], min_q=cfg["prior_min_q"],
                              max_members=cfg["prior_max_members"])
    return prior


# ---------------------------------------------------------------------------- one pair run
class _PairRun:
    def __init__(self, a: DiscoveryProblem, b: DiscoveryProblem, method: DiscoveryMethod, budget_a: int, budget_b: int, seed: int, cfg: dict,
                 workers: int):
        self.P = {"a": a, "b": b}
        self.B = {"a": int(budget_a), "b": int(budget_b)}
        self.method = method
        self.seed = int(seed)
        self.cfg = cfg
        self.ledger = _Ledger(self.P, self.B["a"] + self.B["b"], workers)
        self.corr = _Corr(self.P, cfg, seed)
        self.probe_seeds = [self.seed * 1000 + 600 + i for i in range(int(cfg["probe_seeds"]))]
        self.val_seeds = [self.seed * 1000 + 800 + i for i in range(int(cfg["validation_seeds"]))]
        self.diag: dict = {"n_anchor_types": len(self.corr.anchors), "probe_seeds": self.probe_seeds, "validation_seeds": self.val_seeds,
                           "steps": []}
        self._val: dict[tuple[str, tuple[int, ...]], float | None] = {}
        self.links: list[dict] = []  # accepted verified transfers (source core -> verified image): the only basis of identity claims

    @staticmethod
    def other(net: str) -> str:
        return "b" if net == "a" else "a"

    def step(self, **kw) -> None:
        self.diag["steps"].append({**kw, "total_calls": self.ledger.spent()})

    # ------------------------------------------------------------------ base method
    def discover(self, net: str, cap: float, prior: dict | None = None) -> DiscoveryResult:
        sim = self.ledger.open(net, "discovery", cap)
        mcfg = {**self.method.default_config, **dict(self.cfg.get("method_config") or {}), **dict(self.cfg.get(f"method_config_{net}") or {})}
        if prior is not None:
            mcfg["prior"] = prior
        t0 = time.time()
        exhausted = False
        try:
            res = self.method.discover(self.P[net], sim, seed=self.seed, config=mcfg)
        except BudgetExhausted:
            exhausted = True
            res = DiscoveryResult(core=[], diagnostics={"error": "budget exhausted before a result"})
        res.budget = {**sim.report(), "wall_s": round(time.time() - t0, 2)}
        self.step(step="discovery", net=net, allowance=sim.max_calls, calls=sim.calls, prior=prior is not None, exhausted=exhausted,
                  core=[int(p) for p in res.core])
        return res

    # ------------------------------------------------------------------ verified transfer (joint)
    def verified_transfer(self, src: str, dst: str, src_res: DiscoveryResult, sim: BudgetedSimulator) -> dict:
        P = self.P[dst]
        core_src = sorted({int(p) for p in src_res.core})
        per = self.corr.match(src, dst, core_src)
        spread = {p: self.corr.spread(src, dst, per.get(p, {})) for p in core_src}
        amap, ainfo = self.corr.assign(src, dst, core_src, K=int(self.cfg["assign_k"]), lam=float(self.cfg["edge_bonus"]), beam=int(self.cfg["beam"]))
        support: dict[int, float] = {}
        for lst in spread.values():
            for q, w in lst:
                support[q] = max(support.get(q, 0.0), w)
        for q in amap.values():  # the structural image is removed last
            if q is not None:
                support[q] = support.get(q, 0.0) + 1.0
        cands = {p: ([amap[p]] if amap.get(p) is not None else []) + [q for q, _ in spread[p] if q != amap.get(p)] for p in core_src}
        pr = _Prober(P, sim, self.probe_seeds)
        out: dict = {"src": src, "dst": dst, "accepted": False, "source_core": core_src, "candidates": cands, "support": support, "probes": [],
                     "assessed": sorted(support), "assignment": {p: q for p, q in amap.items()}, "assignment_info": ainfo}
        struct = sorted({q for q in amap.values() if q is not None})
        top1 = sorted({lst[0][0] for lst in spread.values() if lst})
        union = sorted({q for p in core_src for q in cands[p]})
        S = None
        tried: set[tuple[int, ...]] = set()
        for name, cset in (("structural", struct), ("top1", top1), ("union_topk", union)):
            if not cset or tuple(cset) in tried:
                continue
            tried.add(tuple(cset))
            r = pr.keep(cset)
            out["probes"].append({"probe": name, "size": len(cset), "passed": r})
            if r is None:
                break
            if r:
                S = cset
                break
        if S is None:
            out["calls"] = sim.calls
            return out
        mini = _minimize(pr, S, sorted(S, key=lambda q: (support.get(q, 0.0), q)))
        core = list(mini["core"])
        essential: dict[int, bool | None] = dict(mini["essential"])
        added: list[int] = []
        unmatched: list[int] = []
        strict = bool(self.cfg.get("require_essential_structure", True))
        ess_src = {int(p): v for p, v in (src_res.essential or {}).items()}
        for p in core_src:  # a counterpart of each source member that is essential there should be essential here
            if ess_src.get(p) is not True or any(essential.get(q) is True for q in cands[p] if q in core):
                continue
            found = False
            for q in sorted(cands[p], key=lambda x: (x not in core, -support.get(x, 0.0), x)):
                if q in essential:
                    continue
                r = pr.silenced([q])
                if r is None:
                    break
                essential[q] = not r
                if not r:
                    if q not in core:
                        core.append(q)
                        added.append(q)
                    found = True
                    break
            if not found:
                unmatched.append(p)
                if strict:  # the transfer can no longer verify: stop spending
                    break
        matched = {p: [q for q in cands[p] if q in core] for p in core_src}
        out.update({"core": sorted(core), "minimize": mini, "added_essential": added, "necessary": mini["necessary"],
                    "unmatched_essential": unmatched, "superset": not bool(mini["complete"]), "matched_source": matched})
        if unmatched and strict:
            # a member essential in the source has no essential counterpart here: the image is at best some sufficient set of this
            # network, not the source's mechanism (e.g. a network that implements another mechanism) — not verified, no validation spent
            out.update({"essential": {q: essential.get(q) for q in sorted(core)}, "validation": None, "validation_outcomes": [],
                        "n_validation_seeds": 0, "accepted": False, "rejected": REJECT_ESSENTIAL,
                        "decisions": pr.n_decisions, "calls": sim.calls})
            return out
        for q in sorted(core):
            if q not in essential:
                r = pr.silenced([q])
                essential[q] = None if r is None else (not r)
        out["essential"] = {q: essential.get(q) for q in sorted(core)}
        if self.cfg.get("require_reliance", True) and not any(essential.get(q) is True for q in core):
            # no member is essential alone: the intact network must still rely on the image as a whole (silencing all of it breaks
            # the function) — otherwise it is a sufficient set the network does not use (a hub that could drive the readout alone,
            # a silent copy), not its mechanism
            r = pr.silenced(sorted(core))
            out["image_silencing_passed"] = r
            if r is not False:
                out.update({"validation": None, "validation_outcomes": [], "n_validation_seeds": 0, "accepted": False,
                            "rejected": REJECT_RELIANCE if r else "allowance exhausted",
                            "decisions": pr.n_decisions, "calls": sim.calls})
                return out
        frac, outs = pr.fraction(sorted(core), self.val_seeds)
        # verified only if validated on enough fresh seeds (None = the allowance ran out: unverified) and completely minimised (an
        # incomplete minimisation is a sufficient SUPERSET, not a mechanism) — review E finding 3
        validated = frac is not None and len(outs) >= int(self.cfg["min_validation_seeds"]) and frac >= 0.5
        accepted = bool(validated and mini["complete"] and not (unmatched and strict))
        out.update({"validation": frac, "validation_outcomes": outs, "n_validation_seeds": len(outs), "accepted": accepted,
                    "decisions": pr.n_decisions, "calls": sim.calls})
        if not accepted:
            out["rejected"] = "not validated" if not validated else "minimisation incomplete (superset)"
        return out

    @staticmethod
    def link_pairs(tr: dict) -> set[tuple[int, int]]:
        """Member pairs (position in a, position in b) that a verified transfer matched (a source member and a candidate image of it
        that survived in the verified core)."""
        pairs = {(int(p), int(q)) for p, qs in (tr.get("matched_source") or {}).items() for q in qs}
        return pairs if tr.get("src", "a") == "a" else {(q, p) for p, q in pairs}

    def link(self, res_a: DiscoveryResult, res_b: DiscoveryResult) -> dict | None:
        """The latest accepted verified transfer whose verified image is exactly the destination's current core and whose source is
        the source's current core — as transferred, or consistency-pruned to the members whose counterparts survived — if any."""
        cores = {"a": sorted(int(p) for p in res_a.core), "b": sorted(int(p) for p in res_b.core)}
        for tr in reversed(self.links):
            src = cores[tr["src"]]
            pruned = sorted(int(p) for p, qs in (tr.get("matched_source") or {}).items() if qs)
            if src and src in (sorted(tr["source_core"]), pruned) and sorted(tr["core"]) == cores[tr["dst"]]:
                return tr
        return None

    def result_from_transfer(self, dst: str, tr: dict, own: DiscoveryResult | None = None) -> DiscoveryResult:
        P = self.P[dst]
        core = sorted(tr["core"])
        probs: dict[int, float] = {}
        alts: list[list[int]] = []
        if own is not None:
            probs.update({int(p): float(v) for p, v in own.inclusion_probability.items()})
            for p in own.core:
                if p not in set(core):
                    probs[int(p)] = min(probs.get(int(p), 1.0), 0.3)
            for alt in [sorted(int(p) for p in own.core)] + [sorted(int(p) for p in x) for x in own.alternatives]:
                if alt and alt != core and alt not in alts:
                    alts.append(alt)
        for q in tr["assessed"]:
            if q not in set(core):
                probs[int(q)] = min(probs.get(int(q), 1.0), 0.05)
        for q in core:
            e = tr["essential"].get(q)
            probs[q] = 0.97 if e else 0.9 if q in set(tr["necessary"]) else 0.75
        outs = [o for o in tr.get("validation_outcomes") or [] if o.passed]
        freqs = [o.frequency_hz for o in outs if o.frequency_hz is not None]
        frac = tr.get("validation")
        return DiscoveryResult(
            core=core, inclusion_probability=probs, roles=infer_roles(P, core), essential={q: tr["essential"].get(q) for q in core},
            alternatives=alts, loop=core_loop(P, core), predicted_frequency_hz=float(np.median(freqs)) if freqs else None,
            predicted_n_active_readout=int(np.median([o.n_active_readout for o in outs])) if outs else None,
            predicted_function_preserved=None if frac is None else bool(frac >= 0.5),
            fidelity={"keep_only_pass_fraction": frac, "validation_seeds": self.val_seeds, "probe_seeds": self.probe_seeds},
            diagnostics={"source": f"verified transfer from network {tr['src']}", "probes": tr["probes"], "added_essential": tr["added_essential"],
                         "superset": bool(tr.get("superset")), "n_validation_seeds": tr.get("n_validation_seeds"),
                         "removed": tr["minimize"]["removed"], "decisions": tr["decisions"], "own_core": None if own is None else sorted(own.core)},
            motif=(own.motif if own is not None else None) or f"mechanism carried over from network {tr['src']} and verified")

    def consistency_prune(self, net: str, res: DiscoveryResult, tr: dict) -> DiscoveryResult:
        """Shrink ``res`` (the SOURCE of a verified transfer) to the members whose counterparts survived the minimisation, when
        keep-only of the rest still passes and silencing the pruned members keeps the function (validation calls)."""
        kept = sorted(p for p, qs in tr["matched_source"].items() if qs)
        drop = sorted(set(int(p) for p in res.core) - set(kept))
        if not kept or not drop:
            return res
        sim = self.ledger.open(net, "validation", 4 * len(self.probe_seeds))
        pr = _Prober(self.P[net], sim, self.probe_seeds)
        r1 = pr.keep(kept)
        r2 = pr.silenced(drop) if r1 else None
        self.step(step="consistency_prune", net=net, kept=kept, drop=drop, keep_passed=r1, silence_passed=r2, calls=sim.calls)
        if not (r1 and r2):
            return res
        self.diag.setdefault("switches", []).append({"net": net, "kind": "consistency_prune", "own": sorted(int(p) for p in res.core),
                                                    "adopted": kept})
        res.core = kept
        for p in drop:
            res.inclusion_probability[p] = min(float(res.inclusion_probability.get(p, 1.0)), 0.1)
            res.essential[p] = False
            res.roles.pop(p, None)
        res.essential = {p: v for p, v in res.essential.items() if p in set(kept)}
        res.loop = core_loop(self.P[net], kept)
        res.diagnostics = {**res.diagnostics, "consistency_pruned": drop}
        return res

    # ------------------------------------------------------------------ alignment
    def claims(self, res_a: DiscoveryResult, res_b: DiscoveryResult) -> list[tuple[int, int, float]]:
        """IDENTITY claims between the two cores (review E finding 1). Only between two cores that a verified transfer links (one is
        the other's verified image — simulation evidence that they are one mechanism; independent, prior and transfer modes, and
        cores that were changed after the transfer, make no claim), and only for member pairs that transfer matched. Candidate pairs
        are the members that the structural alignment assigns to each other in both directions; a pair is claimed only if the
        anchor-fingerprint evidence ranks the partner above the 'none of these' option in BOTH directions (``_Corr.identity``). Its
        confidence is the calibrated identity probability sigmoid(a + b * logit(w_ab * w_ba) + c * e), where e counts the signed
        member edges the pair reproduces — edges can raise the confidence only of a pair the fingerprints already support. Roles play
        no part (they are sign and wiring descriptors)."""
        return self.claims_with_evidence(res_a, res_b)[0]

    def claims_with_evidence(self, res_a: DiscoveryResult, res_b: DiscoveryResult) -> tuple[list[tuple[int, int, float]], list[list]]:
        """(claims, evidence): the claims of ``claims`` and the compact evidence of every aligned pair between two linked cores,
        [pos_a, pos_b, w_ab, w_ba, none_ab, none_ba, dual-softmax p, reproduced edges, claimed, matched by the transfer, complete image]."""
        restrict = None
        if self.cfg.get("claims_require_verified_link", True):
            tr = self.link(res_a, res_b)
            if tr is None:
                return [], []
            restrict = self.link_pairs(tr)
        details = self.claim_details(res_a, res_b, include_ineligible=True, restrict=restrict)
        claims = [(pa, pb, c) for pa, pb, c, _ in details if c is not None]
        evidence = [[int(pa), int(pb), round(ev["w_ab"], 4), round(ev["w_ba"], 4), round(ev["none_ab"], 4), round(ev["none_ba"], 4),
                     round(ev["p_fp"], 4), int(ev["edges"]), c is not None, bool(ev["linked"]), bool(ev["complete"])] for pa, pb, c, ev in details]
        return claims, evidence

    def claim_details(self, res_a: DiscoveryResult, res_b: DiscoveryResult, *, include_ineligible: bool = False,
                      restrict: set[tuple[int, int]] | None = None) -> list[tuple[int, int, float, dict]]:
        """(pos_a, pos_b, confidence, evidence) of the claimable pairs; with ``include_ineligible`` also the aligned pairs whose
        fingerprint evidence does not beat 'none' in both directions or that are outside ``restrict`` (the pairs a verified transfer
        matched) — confidence None: never claimed; kept for calibration studies. With ``claims_require_complete_image`` no pair is
        claimable unless the matched, mutually aligned pairs pair up ALL members of both cores one to one (a partial image — the
        other network's mechanism corresponds to only part of this one — supports no member identity)."""
        ca, cb = sorted(int(p) for p in res_a.core), sorted(int(p) for p in res_b.core)
        if not ca or not cb:
            return []
        lam, beam = float(self.cfg["edge_bonus"]), int(self.cfg["beam"])
        amap, _ = self.corr.assign("a", "b", ca, K=len(cb), lam=lam, beam=beam, allowed=cb)
        bmap, _ = self.corr.assign("b", "a", cb, K=len(ca), lam=lam, beam=beam, allowed=ca)
        kk = max(int(self.cfg.get("claim_k", 5)), self.corr.k)
        mutual = [(pa, pb) for pa, pb in amap.items() if pb is not None and bmap.get(pb) == pa]
        n_linked = sum(1 for pa, pb in mutual if restrict is None or (int(pa), int(pb)) in restrict)
        complete = n_linked == len(ca) == len(cb)
        need_complete = bool(self.cfg.get("claims_require_complete_image", True))
        Wa, Wb = self.P["a"].W, self.P["b"].W
        a0, b0, c0 = (float(x) for x in self.cfg.get("identity_calibration", (0.0, 1.0, 0.0)))
        out = []
        for pa, pb in mutual:
            ev = self.corr.identity("a", "b", pa, pb, k=kk)
            edges = 0
            for pa2, pb2 in mutual:
                s1 = np.sign(Wa[pa, pa2])
                edges += int(s1 != 0 and np.sign(Wb[pb, pb2]) == s1)
                if pa2 != pa:
                    s2 = np.sign(Wa[pa2, pa])
                    edges += int(s2 != 0 and np.sign(Wb[pb2, pb]) == s2)
            ev["edges"] = int(edges)
            ev["linked"] = restrict is None or (int(pa), int(pb)) in restrict
            ev["complete"] = bool(complete)
            if not (ev["eligible"] and ev["linked"] and (complete or not need_complete)):
                if include_ineligible:
                    out.append((pa, pb, None, ev))
                continue
            q = min(max(ev["p_fp"], 1e-6), 1.0 - 1e-6)
            conf = float(1.0 / (1.0 + np.exp(-(a0 + b0 * np.log(q / (1.0 - q)) + c0 * edges))))
            if conf >= float(self.cfg["claim_min_confidence"]):
                out.append((pa, pb, round(conf, 4), ev))
            elif include_ineligible:
                out.append((pa, pb, None, ev))
        return sorted(out, key=lambda t: (t[0], t[1]))

    def alignment(self, res_a: DiscoveryResult, res_b: DiscoveryResult) -> tuple[dict, dict]:
        ra = {int(p): res_a.roles.get(p, ("unknown", 0.0))[0] for p in res_a.core}
        rb = {int(p): res_b.roles.get(p, ("unknown", 0.0))[0] for p in res_b.core}
        out: dict = {}
        for role in sorted(set(ra.values()) | set(rb.values())):
            out[role] = {"a": sorted(p for p, r in ra.items() if r == role), "b": sorted(p for p, r in rb.items() if r == role)}
        ga, gb = role_graph(self.P["a"], res_a.core, res_a.roles), role_graph(self.P["b"], res_b.core, res_b.roles)
        out["role_graph_similarity"] = float(role_graph_similarity(ga, gb)) if (res_a.core and res_b.core) else 0.0
        return out, {"a": ga, "b": gb}

    # ------------------------------------------------------------------ modes
    def mode_independent(self) -> tuple[DiscoveryResult, DiscoveryResult]:
        return self.discover("a", self.B["a"]), self.discover("b", self.B["b"])

    def mode_prior(self) -> tuple[DiscoveryResult, DiscoveryResult]:
        res_a = self.discover("a", self.B["a"])
        prior = None
        if res_a.core:
            prior, summary = self.corr.transport("a", "b", res_a, rho=self.cfg["prior_rho"], base=self.cfg["prior_base"],
                                                 min_q=self.cfg["prior_min_q"], max_members=self.cfg["prior_max_members"])
            self.diag["prior"] = summary
        return res_a, self.discover("b", self.B["b"], prior=prior)

    def mode_transfer(self) -> tuple[DiscoveryResult, DiscoveryResult]:
        res_a = self.discover("a", self.B["a"])
        sim = self.ledger.open("b", "evaluation", self.B["b"])
        seeds = [self.seed * 1000 + 700 + i for i in range(int(self.cfg["transfer_seeds"]))]
        core_a = sorted(int(p) for p in res_a.core)
        tr = None
        if core_a and sim.max_calls >= len(seeds):
            tr = transfer_core(self.P["a"], self.P["b"], core_a, sim, seeds=seeds, k=self.corr.k, adaptation_calls=sim.max_calls - len(seeds),
                               weights=self.corr.weights)
            self.ledger.split_last({"evaluation": tr["evaluation_calls"], "adaptation": tr["adaptation_calls"]})
        per = tr["candidates"] if tr is not None else self.corr.match("a", "b", core_a)
        probs: dict[int, float] = {}
        for p in core_a:
            for q, w in self.corr.spread("a", "b", per.get(p, {})):
                probs[q] = max(probs.get(q, 0.0), round(w, 4))
        if tr is not None:
            core_b = sorted(int(q) for q in tr["core_b"])
            frac, passed = float(tr["pass_fraction"]), bool(tr["passed"])
        else:  # no calls available: the untested top-1 mapping
            core_b = sorted({per[p]["candidates"][0]["position"] for p in core_a if per.get(p, {}).get("candidates")})
            frac, passed = None, None
        for q in core_b:  # tested members: by the keep-only verdict; untested: their correspondence probability
            if passed is None:
                probs[q] = probs.get(q, 0.5)
            else:
                probs[q] = 0.8 if passed else 0.3
        res_b = DiscoveryResult(core=core_b, inclusion_probability=probs, roles=infer_roles(self.P["b"], core_b), essential=dict.fromkeys(core_b),
                                loop=core_loop(self.P["b"], core_b), predicted_function_preserved=passed,
                                fidelity={"keep_only_pass_fraction": frac, "seeds": seeds},
                                diagnostics={"source": "transfer_core of A's core (no discovery on B)",
                                             "n_configurations_tried": None if tr is None else tr["n_configurations_tried"]},
                                motif="mechanism transferred from network a")
        self.step(step="transfer", core_b=core_b, pass_fraction=frac, calls=sim.calls)
        return res_a, res_b

    def transfer_step(self, src: str, dst: str, src_res: DiscoveryResult, cap: float, **kw) -> dict:
        sim = self.ledger.open(dst, "adaptation", cap)
        tr = self.verified_transfer(src, dst, src_res, sim)
        if tr["accepted"]:
            self._val[(dst, tuple(tr["core"]))] = tr["validation"]
            self.links.append(tr)
        self.step(step="transfer", src=src, dst=dst, allowance=sim.max_calls, calls=sim.calls, probes=tr["probes"], accepted=tr["accepted"],
                  core=tr.get("core"), **({"rejected": tr["rejected"]} if tr.get("rejected") else {}),
                  **({"unmatched_essential": tr["unmatched_essential"]} if tr.get("unmatched_essential") else {}), **kw)
        return tr

    def validation(self, net: str, core) -> float | None:
        """Keep-only pass fraction of ``core`` on the fresh validation seeds (validation calls; cached per core)."""
        key = (net, tuple(sorted(int(p) for p in core)))
        if key not in self._val:
            frac = None
            if key[1]:
                sim = self.ledger.open(net, "validation", len(self.val_seeds))
                frac, _ = _Prober(self.P[net], sim, self.probe_seeds).fraction(list(key[1]), self.val_seeds)
            self._val[key] = frac
        return self._val[key]

    def consistent(self, res_a: DiscoveryResult, res_b: DiscoveryResult) -> bool:
        """The two cores are linked by a verified transfer: one is the other's verified image (no calls)."""
        return bool(res_a.core and res_b.core) and self.link(res_a, res_b) is not None

    def reliance(self, net: str, own_core, shared_core) -> dict:
        """How much the intact network ``net`` relies on each of two mechanisms — the destination's OWN causal evidence: on every
        probe seed on which the intact network passes, silence the distinctive members of each set in the full network; reliance
        per seed = (1[function fails] + mean relative change of the readout statistics vs the intact run) / |distinctive members|.
        Decisive for the carried-over set iff every usable seed (at least two) favours it and the mean difference is at least
        max(reliance_margin, reliance_rel_margin x the larger reliance). Validation calls of ``net``."""
        d_own = sorted(set(int(p) for p in own_core) - set(int(p) for p in shared_core))
        d_sh = sorted(set(int(p) for p in shared_core) - set(int(p) for p in own_core))
        out: dict = {"own_distinctive": d_own, "shared_distinctive": d_sh, "decisive": False}
        if not d_own or not d_sh:
            return out
        sim = self.ledger.open(net, "validation", 3 * len(self.probe_seeds))
        rows: list[tuple[float, float]] = []
        for s in self.probe_seeds:
            try:
                o0 = sim.run(SimQuery(None, int(s)))
                if not o0.passed:  # the intact network fails on this replicate: nothing can be told apart
                    continue
                oo, osh = sim.run(SimQuery(silence(d_own), int(s))), sim.run(SimQuery(silence(d_sh), int(s)))
            except BudgetExhausted:
                break
            rows.append(((float(not oo.passed) + _readout_change(o0, oo)) / len(d_own), (float(not osh.passed) + _readout_change(o0, osh)) / len(d_sh)))
        out["per_seed"] = [[round(a, 4), round(b, 4)] for a, b in rows]
        out["calls"] = sim.calls
        if len(rows) >= 2:
            r_own, r_sh = float(np.mean([a for a, _ in rows])), float(np.mean([b for _, b in rows]))
            margin = max(float(self.cfg["reliance_margin"]), float(self.cfg["reliance_rel_margin"]) * max(r_own, r_sh))
            out.update(own=round(r_own, 4), shared=round(r_sh, 4), decisive=bool(all(b > a for a, b in rows) and r_sh - r_own >= margin))
        return out

    def prefer_shared(self, dst: str, own: DiscoveryResult, shared: DiscoveryResult, other: DiscoveryResult) -> tuple[bool, dict]:
        """Whether ``dst`` replaces its own mechanism by ``shared`` (a verified transfer from the other network: validated, minimised,
        its essential structure reproduced). Only the destination's OWN evidence decides — never agreement with the other network's
        mechanism (role graphs, correspondence: self-agreement, review E finding 2; a null pair, whose networks share no mechanism,
        must keep its own): (1) an own mechanism that is empty or fails its fresh-seed validation is replaced; (2) a carried-over set
        that drops a member the destination found essential is never adopted; (3) a strict subset of the own mechanism is adopted
        (the own set was not minimal); (4) otherwise it is adopted only if the destination's intact network relies decisively more
        on it, per distinctive member (``reliance``). With ``adoption = "never"`` only (1) applies. ``other`` is not used."""
        own_core = sorted(int(p) for p in own.core)
        sh = sorted(int(p) for p in shared.core)
        own_frac = self.validation(dst, own_core) if own_core else None
        info: dict = {"own_validation": own_frac}
        if not own_core or (own_frac is not None and own_frac < 0.5):
            return True, {**info, "rule": "own mechanism missing or not validated"}
        if self.cfg.get("adoption", "own_evidence") == "never":
            return False, {**info, "rule": "adoption never"}
        missing = sorted(int(p) for p, e in own.essential.items() if e is True and int(p) not in set(sh))
        info["own_essential_missing"] = missing
        if missing:
            return False, {**info, "rule": "the carried-over set drops members found essential here"}
        if set(sh) < set(own_core):
            return True, {**info, "rule": "strict subset of the own mechanism"}
        rel = self.reliance(dst, own_core, sh)
        return bool(rel["decisive"]), {**info, "rule": "reliance", "reliance": rel}

    def mode_joint(self) -> tuple[DiscoveryResult, DiscoveryResult]:
        cfg = self.cfg
        if cfg["lead"] in ("a", "b"):
            L = cfg["lead"]
        else:
            L = "a" if len(self.P["a"].candidate_positions()) <= len(self.P["b"].candidate_positions()) else "b"
        F = self.other(L)
        self.diag["lead"] = L
        # 1. the lead, with its own budget
        res = {L: self.discover(L, self.B[L])}
        # 2. verified transfer lead -> follower (adaptation), funded by the lead's unused calls within [min, max] of the follower's budget
        tr_F = None
        if res[L].core:
            leftover = max(0, self.B[L] - self.ledger.spent(L))
            tr_F = self.transfer_step(L, F, res[L], min(max(leftover, cfg["adapt_min_fraction"] * self.B[F]), cfg["adapt_max_fraction"] * self.B[F]))
        round_cost = len(self.probe_seeds) * (4 + 3 * max(2, len(res[L].core))) + 2 * len(self.val_seeds)
        if tr_F is not None and tr_F["accepted"]:
            res[F] = self.result_from_transfer(F, tr_F)
            if cfg["consistency_prune"]:
                res[L] = self.consistency_prune(L, res[L], tr_F)
            self.diag["follower_source"] = "transfer"
        else:
            # 3. the follower's own discovery with the transported prior (damped when the verified transfer failed; none when the
            #    image was rejected on causal grounds — the check showed it is not the mechanism, so pointing the search at it again
            #    would re-introduce what the check rejected)
            prior = None
            if res[L].core and tr_F is not None and tr_F.get("rejected") in CAUSAL_REJECTIONS:
                self.diag["prior"] = {"skipped": f"verified transfer rejected: {tr_F['rejected']}"}
            elif res[L].core:
                damp = cfg["prior_damp_failed_transfer"] if tr_F is not None else 1.0
                prior, summary = self.corr.transport(L, F, res[L], rho=cfg["prior_rho"] * damp, base=cfg["prior_base"], min_q=cfg["prior_min_q"],
                                                     max_members=cfg["prior_max_members"])
                self.diag["prior"] = summary
            left = self.ledger.left()
            reserve = min(round_cost, max(0, left - self.B[F])) if int(cfg["max_rounds"]) > 0 else 0
            res[F] = self.discover(F, left - reserve, prior=prior)
            self.diag["follower_source"] = "discovery"
        # 4. alternating verified transfers (follower -> lead first) until the two mechanisms are linked by a verified transfer; the
        #    receiving network keeps its own mechanism unless its own evidence prefers the carried-over one (prefer_shared; after a
        #    verified lead -> follower transfer this carries the verified, minimised follower mechanism back to the lead)
        src, dst, last = F, L, None
        for rnd in range(int(cfg["max_rounds"])):
            if not res[src].core or self.ledger.left() <= 0 or self.consistent(res["a"], res["b"]):
                break
            tr = self.transfer_step(src, dst, res[src], min(self.ledger.left(), max(round_cost, cfg["adapt_max_fraction"] * self.B[dst])),
                                    round=rnd + 1)
            if not tr["accepted"]:
                break
            if sorted(tr["core"]) != sorted(int(p) for p in res[dst].core):
                shared = self.result_from_transfer(dst, tr, own=res[dst])
                choose, info = self.prefer_shared(dst, res[dst], shared, res[src])
                self.step(step="selection", net=dst, chose="shared" if choose else "own", **info)
                if not choose:
                    res[dst].alternatives = list(res[dst].alternatives) + [sorted(shared.core)]
                    break
                # a switch: the destination's own mechanism is replaced by the carried-over one — reported, never hidden (finding 2)
                self.diag.setdefault("switches", []).append({"net": dst, "round": rnd + 1, "own": sorted(int(p) for p in res[dst].core),
                                                            "adopted": sorted(int(p) for p in shared.core), "from": src})
                res[dst] = shared
            last = (src, dst, tr)
            src, dst = dst, src
        if last is not None and cfg["consistency_prune"]:
            s, d, tr = last
            if sorted(int(p) for p in res[d].core) == sorted(tr["core"]):
                res[s] = self.consistency_prune(s, res[s], tr)
        return res["a"], res["b"]

    # ------------------------------------------------------------------ finish
    def finish(self, res_a: DiscoveryResult, res_b: DiscoveryResult, mode: str, method_name: str, wall: float) -> PairResult:
        filled = {net: _fill_roles(self.P[net], r) for net, r in (("a", res_a), ("b", res_b))}
        align, graphs = self.alignment(res_a, res_b)
        claims, evidence = self.claims_with_evidence(res_a, res_b)
        if evidence:
            self.diag["identity_evidence"] = evidence
        budget = self.ledger.report()
        for net, r in (("a", res_a), ("b", res_b)):
            r.budget = {**(r.budget or {}), "network_calls": self.ledger.spent(net), "network_adaptation_calls": self.ledger.spent(net, "adaptation")}
        diag = {"mode": mode, "method": method_name, "method_version": getattr(self.method, "version", None), "seed": self.seed,
                "budget_a": self.B["a"], "budget_b": self.B["b"], "roles_inferred": filled, "role_graphs": graphs, "wall_s": round(wall, 2),
                "config": {k: v for k, v in self.cfg.items() if k not in ("method_config_a", "method_config_b")}, **self.diag}
        return PairResult(res_a, res_b, claims, align, budget, diag)


def discover_pair(a: DiscoveryProblem, b: DiscoveryProblem, method_name: str, *, budget_a: int, budget_b: int, seed: int, mode: str,
                  config: dict | None = None, workers: int = 1) -> PairResult:
    """Discover the mechanism of ``a`` and ``b`` with the base method ``method_name`` in one of :data:`MODES` (module docstring)."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; one of {MODES}")
    cfg = {**DEFAULT_CONFIG, **(config or {})}
    run = _PairRun(a, b, get_method(method_name), budget_a, budget_b, seed, cfg, workers)
    t0 = time.time()
    res_a, res_b = getattr(run, f"mode_{mode}")()
    return run.finish(res_a, res_b, mode, method_name, time.time() - t0)


# ---------------------------------------------------------------------------- CLI
def _parse_kv(items: list[str]) -> dict:
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        try:
            out[k] = json.loads(v)
        except json.JSONDecodeError:
            out[k] = v
    return out


def _json_default(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (set, frozenset)):
        return sorted(o)
    return str(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pair", type=Path, required=True, help="pair instance directory (model_config.json, networks/<a>, networks/<b>)")
    ap.add_argument("--method", required=True, help="registered base discovery method")
    ap.add_argument("--mode", required=True, choices=MODES)
    ap.add_argument("--budget-a", type=int, required=True)
    ap.add_argument("--budget-b", type=int, required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--net-a", default="a")
    ap.add_argument("--net-b", default="b")
    ap.add_argument("--config", nargs="*", default=[], help="key=value overrides of the pair configuration (JSON values)")
    ap.add_argument("--method-config", nargs="*", default=[], help="key=value overrides passed to the base method on both networks")
    ap.add_argument("--workers", type=int, default=1)
    args = ap.parse_args(argv)
    a = DiscoveryProblem.from_bundle(args.pair, args.net_a)
    b = DiscoveryProblem.from_bundle(args.pair, args.net_b)
    cfg = _parse_kv(args.config)
    if args.method_config:
        cfg["method_config"] = {**dict(cfg.get("method_config") or {}), **_parse_kv(args.method_config)}
    t0 = time.time()
    pr = discover_pair(a, b, args.method, budget_a=args.budget_a, budget_b=args.budget_b, seed=args.seed, mode=args.mode, config=cfg,
                       workers=args.workers)
    rec = {"pair": path_basename(args.pair), "networks": {"a": args.net_a, "b": args.net_b}, "method": args.method, "mode": args.mode,
           "seed": args.seed, "budget_a": args.budget_a, "budget_b": args.budget_b, "wall_s": round(time.time() - t0, 2),
           "problems": {"a": a.public_summary(), "b": b.public_summary()}, **pr.to_dict()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(rec, indent=1, default=_json_default) + "\n", encoding="utf-8", newline="\n")
    bud = pr.budget
    print(f"{args.mode}/{args.method}: core_a {pr.result_a.core} core_b {pr.result_b.core} calls a={bud['a']} b={bud['b']} "
          f"adaptation={bud['adaptation']} total={bud['total']}/{bud['limit']} -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
