"""Cross-network transfer of a discovered mechanism, with a separately accounted adaptation budget (goal3 sections 17-18).

Given a mechanism discovered in network A (positions in A) and the public evidence of network B, a transfer proposes the
corresponding members in B through :mod:`brainir.discovery.correspondence` and tests them on B's simulator:

    transfer_core(...)    top-scored candidate per member; with an *adaptation budget* > 0, alternative candidates are
                          tried in order of decreasing correspondence score until B's keep-only passes (every simulation
                          counts against the adaptation budget, kept apart from the discovery budget)
    null_transfer(...)    the same test for random B interneurons matched on sign and anchor coverage: the reference
                          that separates "the mapping carried the mechanism" from "any few neurons of B would do"

Nothing in this module reads a truth file; scoring against synthetic truth lives in the tournament/pair scorer.
"""

from __future__ import annotations

import itertools

import numpy as np

from .correspondence import fingerprints, match_candidates, shared_anchor_types
from .interventions import keep_only
from .problem import DiscoveryProblem
from .simulator import BudgetedSimulator, BudgetExhausted


def transfer_core(a: DiscoveryProblem, b: DiscoveryProblem, core_a, sim_b: BudgetedSimulator, *, seeds, k: int = 3, adaptation_calls: int = 0,
                  min_pass: float = 0.5, weights: dict | None = None) -> dict:
    """Map ``core_a`` into B and test it. Returns the mapped core, its pass fraction, the candidates and the calls used.

    With ``adaptation_calls`` = 0 only the top-1 mapping is simulated (``len(seeds)`` calls, reported as ``evaluation_calls``);
    otherwise members are re-assigned to lower-ranked candidates, worst-distinctiveness member first, while calls remain."""
    core_a = [int(p) for p in core_a]
    anchors = shared_anchor_types(a, b)
    fa, fb = fingerprints(a, anchors), fingerprints(b, anchors)
    match = match_candidates(a, b, core_a, k=k, weights=weights, fa=fa, fb=fb)
    per = match["per_neuron"]
    choice = {p: 0 for p in core_a}

    def mapped(ch):
        out = []
        for p in core_a:
            cands = per[p]["candidates"]
            if cands:
                out.append(cands[min(ch[p], len(cands) - 1)]["position"])
        return sorted(set(out))

    calls0 = sim_b.calls
    tried = []
    core_b = mapped(choice)
    frac = sim_b.pass_fraction(keep_only(b, core_b), seeds)
    tried.append({"core_b": core_b, "pass_fraction": frac, "choice": dict(choice)})
    evaluation_calls = sim_b.calls - calls0
    adaptation_used = 0
    if frac < min_pass and adaptation_calls > 0:
        budget_cap = sim_b.calls + adaptation_calls
        order = sorted(core_a, key=lambda p: per[p]["distinctiveness"])  # least distinctive first
        # single substitutions, then pairs, in order of decreasing correspondence score
        for depth in (1, 2):
            for members in itertools.combinations(order, depth):
                for alts in itertools.product(*[range(1, min(k, len(per[p]["candidates"]))) for p in members]):
                    if frac >= min_pass or sim_b.calls + len(seeds) > budget_cap:
                        break
                    ch = dict(choice)
                    for p, alt in zip(members, alts):
                        ch[p] = alt
                    cb = mapped(ch)
                    if any(t["core_b"] == cb for t in tried):
                        continue
                    try:
                        f = sim_b.pass_fraction(keep_only(b, cb), seeds)
                    except BudgetExhausted:
                        break
                    tried.append({"core_b": cb, "pass_fraction": f, "choice": ch})
                    if f > frac:
                        frac, core_b, choice = f, cb, ch
                if frac >= min_pass:
                    break
            if frac >= min_pass:
                break
        adaptation_used = sim_b.calls - calls0 - evaluation_calls
    return {"core_a": core_a, "core_b": core_b, "pass_fraction": frac, "passed": bool(frac >= min_pass), "n_anchor_types": len(anchors),
            "candidates": {p: per[p] for p in core_a}, "evaluation_calls": evaluation_calls, "adaptation_calls": adaptation_used,
            "n_configurations_tried": len(tried), "tried": tried}


def null_transfer(a: DiscoveryProblem, b: DiscoveryProblem, core_a, sim_b: BudgetedSimulator, *, seeds, n_null: int = 20, seed: int = 0,
                  min_pass: float = 0.5) -> dict:
    """Pass fraction of random B interneuron sets of the same size, matched on sign composition (reference distribution)."""
    rng = np.random.default_rng(seed)
    core_a = [int(p) for p in core_a]
    signs_a = [int(a.signs[p]) for p in core_a]
    cand = b.candidate_positions()
    by_sign = {s: [int(p) for p in cand if int(b.signs[p]) == s] for s in (-1, 0, 1)}
    fracs = []
    for _ in range(n_null):
        pick = set()
        for s in signs_a:
            pool = by_sign.get(s) or list(map(int, cand))
            while True:
                q = int(rng.choice(pool))
                if q not in pick:
                    pick.add(q); break
        fracs.append(sim_b.pass_fraction(keep_only(b, sorted(pick)), seeds))
    fr = np.array(fracs)
    return {"n_null": n_null, "pass_rate": float(np.mean(fr >= min_pass)), "pass_fraction_mean": float(fr.mean()), "pass_fractions": fracs}


FRESH_SEEDS = (8100, 8101, 8102, 8103, 8104, 8105)


def sufficiency_check(problem: DiscoveryProblem, core: list[int], seeds=FRESH_SEEDS) -> dict:
    """Keep-only of ``core`` on fresh parameter seeds (oracle-free), plus the members removable one at a time (cores up to 20)."""
    sim = BudgetedSimulator(problem, max_calls=10 ** 9)
    seeds = list(seeds)
    if not core:
        return {"pass_fraction": 0.0, "passed": False, "removable": None, "check_calls": 0}
    frac = sim.pass_fraction(keep_only(problem, core), seeds)
    removable = None
    if frac >= 0.5 and 1 < len(core) <= 20:
        removable = [p for p in core if sim.pass_fraction(keep_only(problem, [q for q in core if q != p]), seeds[:3]) >= 0.5]
    return {"pass_fraction": frac, "passed": bool(frac >= 0.5), "removable": removable, "check_calls": sim.calls}


def transfer_experiment_job(args) -> dict:
    """One real-network transfer experiment (module-level so remote backends can import it); see scripts/transfer_experiments.py.

    ``args`` = (bundle, net_src, net_dst, method, mode, seed, budget_src, budget_dst, config, n_null, packs)."""
    import tempfile
    import time
    from pathlib import Path

    from .joint import discover_pair
    from .problem import path_basename, unpack_bundle

    bundle, net_src, net_dst, method, mode, seed, budget_src, budget_dst, config, n_null, packs = args
    bundle = Path(bundle)
    if not bundle.exists() and packs is not None:
        tmp = Path(tempfile.mkdtemp(prefix="brainir_xfer_"))
        bundle = unpack_bundle(packs["bundle"], tmp / path_basename(bundle))
    src = DiscoveryProblem.from_bundle(bundle, net_src)
    dst = DiscoveryProblem.from_bundle(bundle, net_dst)
    t0 = time.time()
    res = discover_pair(src, dst, method, budget_a=budget_src, budget_b=budget_dst, seed=seed, mode=mode, config=config, workers=1)
    wall = time.time() - t0
    core_src, core_dst = [int(p) for p in res.result_a.core], [int(p) for p in res.result_b.core]
    out = {"direction": f"{net_src}->{net_dst}", "mode": mode, "seed": seed, "method": method, "wall_s": round(wall, 1), "budget": res.budget,
           "core_src": core_src, "core_dst": core_dst, "n_src": len(core_src), "n_dst": len(core_dst),
           "check_src": sufficiency_check(src, core_src), "check_dst": sufficiency_check(dst, core_dst),
           "n_correspondence_claims": len(res.correspondence), "correspondence": res.correspondence, "role_alignment": res.role_alignment,
           "diagnostics_keys": sorted((res.diagnostics or {}).keys())}
    if mode == "transfer" and core_src:
        sim_null = BudgetedSimulator(dst, max_calls=10 ** 9)
        out["null"] = null_transfer(src, dst, core_src, sim_null, seeds=list(FRESH_SEEDS[:3]), n_null=n_null, seed=seed)
    return out


def role_graph(problem: DiscoveryProblem, core, roles: dict) -> dict:
    """The abstract mechanism: roles of the members and signed role->role interactions (from the public matrix), for cross-network
    comparison at the level of roles rather than identities."""
    core = [int(p) for p in core]
    W = problem.W
    r_of = {p: (roles.get(p, ("unknown", 0.0))[0] if isinstance(roles.get(p), tuple) else roles.get(p, "unknown")) for p in core}
    inter: dict[tuple[str, str], list[float]] = {}
    for pre in core:
        for post in core:
            w = float(W[post, pre])
            if w != 0.0:
                inter.setdefault((r_of[pre], r_of[post]), []).append(w)
    edges = [{"pre_role": k[0], "post_role": k[1], "sign": int(np.sign(np.mean(v))), "mean_weight": float(np.mean(v)), "n": len(v)}
             for k, v in inter.items()]
    return {"roles": sorted(set(r_of.values())), "members": {p: r_of[p] for p in core},
            "edges": sorted(edges, key=lambda e: (e["pre_role"], e["post_role"]))}


def role_graph_similarity(g1: dict, g2: dict) -> float:
    """Jaccard of signed role interactions (pre_role, post_role, sign) — 1.0 when the abstract mechanisms coincide."""
    e1 = {(e["pre_role"], e["post_role"], e["sign"]) for e in g1["edges"]}
    e2 = {(e["pre_role"], e["post_role"], e["sign"]) for e in g2["edges"]}
    if not (e1 | e2):
        return 1.0 if set(g1["roles"]) == set(g2["roles"]) else 0.0
    return len(e1 & e2) / len(e1 | e2)
