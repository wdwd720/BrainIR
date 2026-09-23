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


def score_pair(truth: dict, a: DiscoveryProblem, b: DiscoveryProblem, res) -> dict:
    ta, tb = truth["networks"]["a"], truth["networks"]["b"]
    sa, sb = score_structure(res.result_a, ta), score_structure(res.result_b, tb)
    corr_truth = {(int(x), int(y)) for x, y in truth.get("correspondence_positions", [])}
    claimed = {(int(x), int(y)) for x, y, _ in res.correspondence}
    corr = None
    if corr_truth:
        hit = len(claimed & corr_truth)
        corr = {"precision": hit / len(claimed) if claimed else None, "recall": hit / len(corr_truth), "n_claimed": len(claimed)}
    # role alignment: for every truth role present in both, does the claimed alignment put members of that role together?
    role_truth = truth.get("role_correspondence_positions", {})
    ra_hits, ra_n = 0, 0
    for role, (xa, xb) in role_truth.items():
        claim = (res.role_alignment or {}).get(role)
        if not isinstance(claim, dict) or not xb:
            continue
        ra_n += 1
        ra_hits += int(bool(set(int(p) for p in claim.get("a", [])) & set(xa)) and bool(set(int(p) for p in claim.get("b", [])) & set(xb)))
    roles_a = {int(p): (r, 1.0) for p, r in ta["roles_positions"].items()}
    roles_b = {int(p): (r, 1.0) for p, r in tb["roles_positions"].items()}
    g_truth_a, g_truth_b = role_graph(a, ta["core_positions"], roles_a), role_graph(b, tb["core_positions"], roles_b)
    g_pred_a = role_graph(a, res.result_a.core, res.result_a.roles)
    g_pred_b = role_graph(b, res.result_b.core, res.result_b.roles)
    return {"a": sa, "b": sb, "both_success": bool(sa["success"] and sb["success"]), "correspondence": corr,
            "role_alignment_accuracy": (ra_hits / ra_n) if ra_n else None,
            "role_graph_similarity_pred_ab": role_graph_similarity(g_pred_a, g_pred_b),
            "role_graph_similarity_truth_ab": role_graph_similarity(g_truth_a, g_truth_b),
            "role_graph_similarity_pred_vs_truth_b": role_graph_similarity(g_pred_b, g_truth_b), "budget": res.budget}


def pair_job(args) -> dict:
    """(method, mode, instance_dir, seed, budget_a, budget_b, config, truth_path, packs) -> scored record."""
    from .joint import discover_pair

    method, mode, inst_dir, seed, budget_a, budget_b, config, truth_path, packs = args
    inst_dir, truth_path = Path(inst_dir), Path(truth_path)
    name = path_basename(inst_dir)
    if not inst_dir.exists() and packs is not None:
        tmp = Path(tempfile.mkdtemp(prefix="brainir_pair_"))
        unpack_bundle(packs[name], tmp / name)
        inst_dir = tmp / name
        (tmp / "truth.json").write_bytes(packs[f"truth/{name}"])
        truth_path = tmp / "truth.json"
    a = DiscoveryProblem.from_bundle(inst_dir, "a")
    b = DiscoveryProblem.from_bundle(inst_dir, "b")
    t0 = time.time()
    res = discover_pair(a, b, method, budget_a=budget_a, budget_b=budget_b, seed=seed, mode=mode, config=config, workers=1)
    truth = json.loads(truth_path.read_text(encoding="utf-8"))
    rec = {"method": method, "mode": mode, "instance": name, "seed": seed, "budget_a": budget_a, "budget_b": budget_b,
           "wall_s": round(time.time() - t0, 1), "family": truth["spec"]["family"], "shift": bool(truth["spec"].get("implementation_shift")),
           "decoy": bool(truth["spec"].get("anchor_decoy")), "correspondence": res.correspondence, "role_alignment": res.role_alignment}
    rec["score"] = score_pair(truth, a, b, res)
    rec["result_a"] = compact_result(res.result_a.to_dict())
    rec["result_b"] = compact_result(res.result_b.to_dict())
    rec["diagnostics"] = compact_result({"diagnostics": res.diagnostics or {}})["diagnostics"]
    return rec


def _mean_of(rs: list[dict], f) -> float | None:
    v = [x for x in (f(r) for r in rs) if x is not None]
    return float(np.mean(v)) if v else None


def summarize_pairs(records: list[dict]) -> dict:
    out: dict = {}
    rng = np.random.default_rng(0)
    keys = sorted({(r["method"], r["mode"]) for r in records if "score" in r})
    for m, mode in keys:
        rs = [r for r in records if r.get("method") == m and r.get("mode") == mode and "score" in r]
        both = np.array([r["score"]["both_success"] for r in rs], dtype=float)
        boot = [rng.choice(both, len(both)).mean() for _ in range(2000)] if len(both) > 1 else [both.mean()]

        def mean_of(f, rs=rs):
            return _mean_of(rs, f)

        out[f"{m}/{mode}"] = {"n_runs": len(rs), "success_a": mean_of(lambda r: r["score"]["a"]["success"]),
                              "success_b": mean_of(lambda r: r["score"]["b"]["success"]), "both_success": float(both.mean()),
                              "both_ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
                              "corr_precision": mean_of(lambda r: (r["score"]["correspondence"] or {}).get("precision")),
                              "corr_recall": mean_of(lambda r: (r["score"]["correspondence"] or {}).get("recall")),
                              "role_alignment_accuracy": mean_of(lambda r: r["score"]["role_alignment_accuracy"]),
                              "role_graph_similarity_ab": mean_of(lambda r: r["score"]["role_graph_similarity_pred_ab"]),
                              "calls_a": mean_of(lambda r: (r["score"]["budget"] or {}).get("a")),
                              "calls_b": mean_of(lambda r: (r["score"]["budget"] or {}).get("b")),
                              "calls_adaptation": mean_of(lambda r: (r["score"]["budget"] or {}).get("adaptation")),
                              "calls_total": mean_of(lambda r: (r["score"]["budget"] or {}).get("total")),
                              "by_family": {f: float(np.mean([r["score"]["both_success"] for r in rs if r["family"] == f]))
                                            for f in sorted({r["family"] for r in rs})},
                              "shift_both_success": mean_of(lambda r: r["score"]["both_success"] if r["shift"] else None),
                              "decoy_both_success": mean_of(lambda r: r["score"]["both_success"] if r["decoy"] else None)}
    return out


def pairs_markdown(out: dict) -> str:
    s = out["summary"]
    lines = [f"# Pair tournament — {out['label']}", "", f"{out['n_jobs']} jobs; budgets a {out['budget_a']} / b {out['budget_b']}; seeds {out['seeds']}; "
             f"wall {out['wall_s']} s on {out['backend'].get('backend')}", "",
             "| method/mode | n | success a | success b | both [CI] | corr P/R | role align | role-graph sim | calls a/b/adapt/total |",
             "|---|---|---|---|---|---|---|---|---|"]

    def f(x):
        return "n/a" if x is None else f"{x:.2f}"

    for k, v in s.items():
        ci = f"[{v['both_ci95'][0]:.2f}, {v['both_ci95'][1]:.2f}]"
        lines.append(f"| {k} | {v['n_runs']} | {f(v['success_a'])} | {f(v['success_b'])} | {f(v['both_success'])} {ci} | "
                     f"{f(v['corr_precision'])}/{f(v['corr_recall'])} | {f(v['role_alignment_accuracy'])} | {f(v['role_graph_similarity_ab'])} | "
                     f"{f(v['calls_a'])}/{f(v['calls_b'])}/{f(v['calls_adaptation'])}/{f(v['calls_total'])} |")
    lines += ["", "by family (both-success rate):", ""]
    for k, v in s.items():
        lines.append(f"- {k}: " + ", ".join(f"{fam} {rate:.2f}" for fam, rate in v["by_family"].items()) +
                     f"; shift {f(v['shift_both_success'])}; decoy {f(v['decoy_both_success'])}")
    errors = [r for r in out["records"] if "error" in r]
    if errors:
        lines += ["", f"{len(errors)} failed jobs: " + "; ".join(f"{e.get('instance')}/{e.get('mode')}: {str(e['error'])[:120]}" for e in errors[:10])]
    return "\n".join(lines) + "\n"
