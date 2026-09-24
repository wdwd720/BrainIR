"""Cross-connectome pair tournament scorer (goal3 sections 17-18, 22): run `joint.discover_pair` on synthetic pairs and score against
the withheld truth. Truth files are read ONLY here. Module-level job functions so remote backends can import them.

Per (method, mode, pair, seed): success on a and on b (recall 1 vs some sufficient alternative), claimed correspondence
precision/recall (identity level; undefined under implementation shift), role-alignment accuracy (role level), role-graph
similarity, calls on a / b / adaptation / total.
"""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

import numpy as np

from .problem import DiscoveryProblem, path_basename, unpack_bundle
from .tournament import compact_result, score_structure
from .transfer import role_graph, role_graph_similarity


def identity_truth(truth: dict) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    """(identities, homologs) of a pair truth, as (position in a, position in b).

    Identities are the same neuron in both networks: every corresponding mechanism member, and under an implementation shift the
    members of the alternative both networks retain (review E finding 1: a claim that pairs different implementations is false).
    Null pairs have none. Truth files written before ``identity_positions`` existed are handled through the stored permutations
    (motif node j is canonical node 1 + j in both networks). Homologs are distractors built with shared anchor profiles."""
    spec = truth.get("spec") or {}
    if "identity_positions" in truth:
        ids = {(int(x), int(y)) for x, y in truth["identity_positions"]}
    else:
        ids = {(int(x), int(y)) for x, y in truth.get("correspondence_positions", [])}
        if not ids and spec.get("implementation_shift") and not spec.get("null_family"):
            inv_a = {int(c): i for i, c in enumerate(truth["networks"]["a"]["perm"])}
            perm_b = truth["networks"]["b"]["perm"]
            for pos in truth["networks"]["b"]["core_positions"]:
                c = int(perm_b[int(pos)])
                if c in inv_a:
                    ids.add((inv_a[c], int(pos)))
    hom = {(int(x), int(y)) for x, y in truth.get("homolog_positions", [])}
    return ids, hom


def score_identity_claims(claims, identities: set, homologs: set | None = None, *, core_a=None) -> dict:
    """Identity claims ``(position in a, position in b, confidence)`` against identity truth.

    precision = correct / claimed (a homolog claim counts as correct and is reported apart); recall = identities claimed / all
    identities; recall_core = the same over identities whose a-member is in ``core_a``; brier = mean (confidence - correct)^2 over
    claims with a confidence. ``items`` keeps (confidence, correct) for pooled reliability diagrams."""
    homologs = homologs or set()
    items, seen = [], set()
    for x, y, conf in claims:
        key = (int(x), int(y))
        if key in seen:
            continue
        seen.add(key)
        items.append((None if conf is None else float(conf), key in identities or key in homologs, key in homologs))
    n = len(items)
    correct = sum(1 for _c, ok, _h in items if ok)
    confs = [(c, ok) for c, ok, _h in items if c is not None]
    core_ids = {p for p in identities if core_a is None or p[0] in set(int(v) for v in core_a)}
    return {"n_claimed": n, "n_correct": correct, "n_false": n - correct, "n_homolog": sum(1 for *_x, h in items if h),
            "precision": (correct / n) if n else None, "recall": (len(seen & identities) / len(identities)) if identities else None,
            "recall_core": (len(seen & core_ids) / len(core_ids)) if core_ids else None,
            "brier": float(np.mean([(c - float(ok)) ** 2 for c, ok in confs])) if confs else None,
            "mean_confidence": float(np.mean([c for c, _ok in confs])) if confs else None,
            "items": [[c, bool(ok)] for c, ok, _h in items]}


def reliability_bins(items: list, n_bins: int = 5) -> list[dict]:
    """Pooled (confidence, correct) items -> per-bin mean confidence, observed frequency and count (a reliability diagram)."""
    out = []
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = [(c, ok) for c, ok in items if c is not None and (lo <= c < hi or (hi == 1.0 and c == 1.0))]
        if sel:
            out.append({"bin": [round(float(lo), 2), round(float(hi), 2)], "n": len(sel), "mean_confidence": float(np.mean([c for c, _ in sel])),
                        "observed": float(np.mean([float(ok) for _, ok in sel]))})
    return out


def _jaccard(x: set, y: set) -> float:
    return len(x & y) / len(x | y) if (x or y) else 1.0


def score_pair(truth: dict, a: DiscoveryProblem, b: DiscoveryProblem, res, *, budget_a: int | None = None, budget_b: int | None = None) -> dict:
    ta, tb = truth["networks"]["a"], truth["networks"]["b"]
    sa, sb = score_structure(res.result_a, ta), score_structure(res.result_b, tb)
    ids, hom = identity_truth(truth)
    claims = [(int(x), int(y), float(c)) for x, y, c in res.correspondence]
    # identity claims are scored on EVERY pair, including shifts (cross-implementation claims are false) and null pairs (every claim
    # is false) — review E finding 1
    corr = score_identity_claims(claims, ids, hom, core_a=res.result_a.core)
    # role alignment: every truth role present in both networks counts; a role the method never names is a miss (review E finding 10)
    role_truth = truth.get("role_correspondence_positions", {})
    ra_hits, ra_n, ra_jac = 0, 0, []
    for role, (xa, xb) in role_truth.items():
        if not xa or not xb:
            continue
        ra_n += 1
        claim = (res.role_alignment or {}).get(role)
        if not isinstance(claim, dict):
            ra_jac.append(0.0)
            continue
        ja = _jaccard(set(int(p) for p in claim.get("a", [])), set(int(p) for p in xa))
        jb = _jaccard(set(int(p) for p in claim.get("b", [])), set(int(p) for p in xb))
        ra_jac.append((ja + jb) / 2)
        ra_hits += int(ja >= 0.5 and jb >= 0.5)
    roles_a = {int(p): (r, 1.0) for p, r in ta["roles_positions"].items()}
    roles_b = {int(p): (r, 1.0) for p, r in tb["roles_positions"].items()}
    g_truth_a, g_truth_b = role_graph(a, ta["core_positions"], roles_a), role_graph(b, tb["core_positions"], roles_b)
    g_pred_a = role_graph(a, res.result_a.core, res.result_a.roles)
    g_pred_b = role_graph(b, res.result_b.core, res.result_b.roles)
    bud = dict(res.budget or {})
    net_calls = {"a": int(bud.get("a", 0)) + int(bud.get("adaptation_a", 0)), "b": int(bud.get("b", 0)) + int(bud.get("adaptation_b", 0))}
    caps = {"a": budget_a, "b": budget_b}
    pooled = {net: bool(caps[net] is not None and any(p.get("net") == net and p.get("kind") == "discovery" and int(p.get("allowance", 0)) > caps[net]
                                                       for p in bud.get("phases", [])))
              for net in ("a", "b")}
    return {"a": sa, "b": sb, "both_success": bool(sa["success"] and sb["success"]), "correspondence": corr,
            "role_alignment_accuracy": (ra_hits / ra_n) if ra_n else None,
            "role_alignment_jaccard": float(np.mean(ra_jac)) if ra_jac else None,
            # self-agreement between the method's own two outputs: NOT evidence of a shared mechanism (review E finding 2)
            "role_graph_similarity_pred_ab": role_graph_similarity(g_pred_a, g_pred_b),
            "role_graph_similarity_truth_ab": role_graph_similarity(g_truth_a, g_truth_b),
            "role_graph_similarity_pred_vs_truth_a": role_graph_similarity(g_pred_a, g_truth_a),
            "role_graph_similarity_pred_vs_truth_b": role_graph_similarity(g_pred_b, g_truth_b),
            "network_calls": net_calls, "pooled_allowance": pooled, "budget": res.budget}


def pair_job(args) -> dict:
    """(method, mode, instance_dir, seed, budget_a, budget_b, config, truth_path, packs) -> scored record (or a failure record)."""
    method, mode, inst_dir, seed, budget_a, budget_b, config, truth_path, packs = args
    name = path_basename(inst_dir)
    try:
        return _pair_job(method, mode, inst_dir, seed, budget_a, budget_b, config, truth_path, packs)
    except Exception as e:  # noqa: BLE001 - scored as a failure, identical locally and remotely (review F finding 1)
        import traceback
        return {"method": method, "mode": mode, "instance": name, "seed": seed, "error": f"{type(e).__name__}: {e}"[:500],
                "traceback": traceback.format_exc()[-2000:]}


def _pair_job(method, mode, inst_dir, seed, budget_a, budget_b, config, truth_path, packs) -> dict:
    from .guard import truth_guard
    from .joint import discover_pair
    from .provenance import runtime_env
    from .simulator import count_real_simulations

    inst_dir, truth_path = Path(inst_dir), Path(truth_path)
    name = path_basename(inst_dir)
    truth_bytes = None
    if not inst_dir.exists() and packs is not None:
        # only the instance goes to disk; the truth stays in memory until the result exists (review E finding 7)
        tmp = Path(tempfile.mkdtemp(prefix="brainir_pair_"))
        unpack_bundle(packs[name], tmp / "inst" / name)
        inst_dir = tmp / "inst" / name
        truth_bytes = packs[f"truth/{name}"]
    a = DiscoveryProblem.from_bundle(inst_dir, "a")
    b = DiscoveryProblem.from_bundle(inst_dir, "b")
    base_mode = mode
    if mode.endswith("_null"):  # the same arm with every cross-network cue destroyed and every simulation unchanged (review E)
        from .perturb import null_correspondence

        base_mode = mode[: -len("_null")]
        b = null_correspondence(b, a, seed=int(seed) + 99)
    t0 = time.time()
    # remotely the truth is only in memory; the local truth path means nothing on the worker (a Windows path parsed on Linux has
    # parent ".", i.e. the worker's working directory, which holds the package itself)
    guard_root = None if truth_bytes is not None else truth_path.parent
    with count_real_simulations() as counter, truth_guard(guard_root):
        if base_mode == "independent_pooled":
            res = independent_pooled(a, b, method, budget_a=budget_a, budget_b=budget_b, seed=seed, config=config)
        else:
            res = discover_pair(a, b, method, budget_a=budget_a, budget_b=budget_b, seed=seed, mode=base_mode, config=config, workers=1)
    total = int((res.budget or {}).get("total", -1))
    rec = {"method": method, "mode": mode, "instance": name, "seed": seed, "budget_a": budget_a, "budget_b": budget_b,
           "wall_s": round(time.time() - t0, 1), "integrity": {"real_simulations": counter["n"], "ledger_total": total}, "env": runtime_env()}
    if counter["n"] != total or total > budget_a + budget_b:
        rec["error"] = f"budget integrity: {counter['n']} real simulations, ledger {total}, limit {budget_a + budget_b}"
        return rec
    truth = json.loads(truth_bytes.decode("utf-8") if truth_bytes is not None else truth_path.read_text(encoding="utf-8"))
    spec = truth["spec"]
    rec.update({"family": spec["family"], "shift": bool(spec.get("implementation_shift")), "decoy": bool(spec.get("anchor_decoy")),
                "null_pair": bool(spec.get("null_family")), "structural_decoy": bool(spec.get("structural_decoy")),
                "suite": truth.get("suite"), "correspondence": res.correspondence, "role_alignment": res.role_alignment})
    rec["score"] = score_pair(truth, a, b, res, budget_a=budget_a, budget_b=budget_b)
    rec["result_a"] = compact_result(res.result_a.to_dict())
    rec["result_b"] = compact_result(res.result_b.to_dict())
    rec["diagnostics"] = compact_result({"diagnostics": res.diagnostics or {}})["diagnostics"]
    return rec


def independent_pooled(a: DiscoveryProblem, b: DiscoveryProblem, method: str, *, budget_a: int, budget_b: int, seed: int,
                       config: dict | None = None):
    """The independent arm with pooled budgets (review E finding 4): the base method runs on a with ``budget_a``, then on b with
    ``budget_b`` plus a's unused calls — the pooling joint discovery enjoys, without any cross-network information. No claims."""
    from .interface import DiscoveryResult
    from .joint import DEFAULT_CONFIG, PairResult, get_method
    from .simulator import BudgetedSimulator, BudgetExhausted

    cfg = {**DEFAULT_CONFIG, **(config or {})}
    m = get_method(method)
    out, phases = {}, []
    left = int(budget_a) + int(budget_b)
    for net, prob, cap in (("a", a, int(budget_a)), ("b", b, None)):
        allowance = cap if cap is not None else left
        sim = BudgetedSimulator(prob, max_calls=allowance, workers=1)
        mcfg = {**m.default_config, **dict(cfg.get("method_config") or {}), **dict(cfg.get(f"method_config_{net}") or {})}
        try:
            res = m.discover(prob, sim, seed=seed, config=mcfg)
        except BudgetExhausted:
            res = DiscoveryResult(core=[], diagnostics={"error": "budget exhausted before a result"})
        res.budget = sim.report()
        out[net] = res
        phases.append({"net": net, "kind": "discovery", "allowance": allowance, "calls": sim.total_calls()})
        left -= sim.total_calls()
    ca, cb = phases[0]["calls"], phases[1]["calls"]
    budget = {"a": ca, "b": cb, "adaptation": 0, "adaptation_a": 0, "adaptation_b": 0, "total": ca + cb, "limit": int(budget_a) + int(budget_b),
              "phases": phases}
    return PairResult(result_a=out["a"], result_b=out["b"], correspondence=[], role_alignment={}, budget=budget,
                      diagnostics={"mode": "independent_pooled"})


def _mean_of(rs: list[dict], f) -> float | None:
    v = [x for x in (f(r) for r in rs) if x is not None]
    return float(np.mean(v)) if v else None


def _claims(r: dict) -> dict:
    return (r.get("score") or {}).get("correspondence") or {}


def summarize_pairs(records: list[dict]) -> dict:
    """Per (method, mode): success; identity-claim quality on every pair type, pooled over claims (precision, false claims on
    shift / null / structural-decoy pairs, Brier score, reliability diagram); role alignment; role graphs against the TRUTH; calls
    per network (a network's calls include its adaptation calls) and the pooled-allowance rate (review E findings 1, 2, 4, 12)."""
    out: dict = {}
    rng = np.random.default_rng(0)
    keys = sorted({(r["method"], r["mode"]) for r in records if "method" in r and "mode" in r})
    for m, mode in keys:
        rs = [r for r in records if r.get("method") == m and r.get("mode") == mode and "score" in r]
        failed = [r for r in records if r.get("method") == m and r.get("mode") == mode and "score" not in r]
        zeros = [0.0] * len(failed)  # failed runs are unsuccessful on both networks (review F finding 1)
        both = np.array([r["score"]["both_success"] for r in rs] + zeros, dtype=float)
        boot = [rng.choice(both, len(both)).mean() for _ in range(2000)] if len(both) > 1 else [both.mean()]

        def mean_of(f, rs=rs):
            return _mean_of(rs, f)

        def claim_sum(key, pred=lambda r: True, rs=rs):
            return int(sum(int(_claims(r).get(key) or 0) for r in rs if pred(r)))

        confs = [(c, ok) for r in rs for c, ok in (_claims(r).get("items") or []) if c is not None]
        n_claimed = claim_sum("n_claimed")
        succ_a = float(np.mean([float(r["score"]["a"]["success"]) for r in rs] + zeros)) if (rs or failed) else None
        succ_b = float(np.mean([float(r["score"]["b"]["success"]) for r in rs] + zeros)) if (rs or failed) else None
        out[f"{m}/{mode}"] = {
            "n_runs": len(rs) + len(failed), "n_failed": len(failed), "success_a": succ_a, "success_b": succ_b, "both_success": float(both.mean()),
            "both_ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "claims_total": n_claimed, "claims_correct": claim_sum("n_correct"),
            "claims_precision_pooled": (claim_sum("n_correct") / n_claimed) if n_claimed else None,
            "false_claims_shift": claim_sum("n_false", lambda r: r.get("shift")),
            "false_claims_null": claim_sum("n_false", lambda r: r.get("null_pair")),
            "false_claims_structural_decoy": claim_sum("n_false", lambda r: r.get("structural_decoy")),
            "claims_null_pairs": claim_sum("n_claimed", lambda r: r.get("null_pair")),
            "claims_brier_pooled": float(np.mean([(c - float(ok)) ** 2 for c, ok in confs])) if confs else None,
            "claims_reliability": reliability_bins(confs),
            "corr_precision": mean_of(lambda r: _claims(r).get("precision")),
            "corr_recall": mean_of(lambda r: _claims(r).get("recall")),
            "role_alignment_accuracy": mean_of(lambda r: r["score"].get("role_alignment_accuracy")),
            "role_alignment_jaccard": mean_of(lambda r: r["score"].get("role_alignment_jaccard")),
            "role_graph_vs_truth_a": mean_of(lambda r: r["score"].get("role_graph_similarity_pred_vs_truth_a")),
            "role_graph_vs_truth_b": mean_of(lambda r: r["score"].get("role_graph_similarity_pred_vs_truth_b")),
            "role_graph_self_agreement_ab": mean_of(lambda r: r["score"].get("role_graph_similarity_pred_ab")),  # not evidence (finding 2)
            "calls_a": mean_of(lambda r: (r["score"].get("network_calls") or {}).get("a", (r["score"]["budget"] or {}).get("a"))),
            "calls_b": mean_of(lambda r: (r["score"].get("network_calls") or {}).get("b", (r["score"]["budget"] or {}).get("b"))),
            "calls_adaptation": mean_of(lambda r: (r["score"]["budget"] or {}).get("adaptation")),
            "calls_total": mean_of(lambda r: (r["score"]["budget"] or {}).get("total")),
            "pooled_allowance_rate": mean_of(lambda r: float(any((r["score"].get("pooled_allowance") or {}).values()))
                                             if r["score"].get("pooled_allowance") is not None else None),
            "by_family": {f: float(np.mean([r["score"]["both_success"] for r in rs if r["family"] == f])) for f in sorted({r["family"] for r in rs})},
            "shift_both_success": mean_of(lambda r: r["score"]["both_success"] if r["shift"] else None),
            "decoy_both_success": mean_of(lambda r: r["score"]["both_success"] if r["decoy"] else None),
            "null_both_success": mean_of(lambda r: r["score"]["both_success"] if r.get("null_pair") else None),
            "structural_decoy_both_success": mean_of(lambda r: r["score"]["both_success"] if r.get("structural_decoy") else None)}
    return out


def pairs_markdown(out: dict) -> str:
    s = out["summary"]
    lines = [f"# Pair tournament — {out['label']}", "", f"{out['n_jobs']} jobs; budgets a {out['budget_a']} / b {out['budget_b']}; seeds {out['seeds']}; "
             f"wall {out['wall_s']} s on {out['backend'].get('backend')}", "",
             "Calls per network include that network's adaptation calls. Identity claims are scored on every pair: under an implementation "
             "shift a claim across implementations is false, and on a null pair every claim is false. Role graphs are compared with the "
             "truth; the similarity of a method's two outputs to each other is self-agreement and is not evidence (review E).", "",
             "| method/mode | n | success a | success b | both [CI] | calls a/b (adapt) /total | pooled | claims (correct) | "
             "false shift/null/sdecoy | Brier | role align | role graph vs truth a/b |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]

    def f(x):
        return "n/a" if x is None else f"{x:.2f}"

    for k, v in s.items():
        ci = f"[{v['both_ci95'][0]:.2f}, {v['both_ci95'][1]:.2f}]"
        runs = f"{v['n_runs']}" + (f" ({v['n_failed']} failed)" if v.get("n_failed") else "")
        lines.append(f"| {k} | {runs} | {f(v['success_a'])} | {f(v['success_b'])} | {f(v['both_success'])} {ci} | "
                     f"{f(v['calls_a'])}/{f(v['calls_b'])} ({f(v['calls_adaptation'])}) /{f(v['calls_total'])} | {f(v.get('pooled_allowance_rate'))} | "
                     f"{v.get('claims_total', 0)} ({v.get('claims_correct', 0)}) | {v.get('false_claims_shift', 0)}/{v.get('false_claims_null', 0)}/"
                     f"{v.get('false_claims_structural_decoy', 0)} | {f(v.get('claims_brier_pooled'))} | {f(v['role_alignment_accuracy'])} | "
                     f"{f(v.get('role_graph_vs_truth_a'))}/{f(v.get('role_graph_vs_truth_b'))} |")
    lines += ["", "by family (both-success rate):", ""]
    for k, v in s.items():
        lines.append(f"- {k}: " + ", ".join(f"{fam} {rate:.2f}" for fam, rate in v["by_family"].items()) +
                     f"; shift {f(v['shift_both_success'])}; decoy {f(v['decoy_both_success'])}; null {f(v.get('null_both_success'))}; "
                     f"structural decoy {f(v.get('structural_decoy_both_success'))}")
    errors = [r for r in out["records"] if "error" in r]
    if errors:
        lines += ["", f"{len(errors)} failed jobs: " + "; ".join(f"{e.get('instance')}/{e.get('mode')}: {str(e['error'])[:120]}" for e in errors[:10])]
    return "\n".join(lines) + "\n"
