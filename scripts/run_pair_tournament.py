"""Cross-connectome pair tournament: run `brainir.discovery.joint.discover_pair` in every mode on the synthetic pair suite and score
against the withheld truth (goal3 sections 17-18, 22).

    uv run python scripts/run_pair_tournament.py --methods greedy_reference --modes independent transfer prior joint \
        --budget-a 500 --budget-b 500 --seeds 0 1 [--max-n 200] [--backend modal] --label pairs_small

Per (method, mode, pair, seed): success on a and on b (recall 1 vs some sufficient alternative), transfer/B success, claimed
correspondence precision/recall (identity level; undefined under implementation shift), role-alignment accuracy (role level),
role-graph similarity, calls on a / b / adaptation / total. Writes research/phase2/tournament/<label>.{json,md} + registry record.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from brainir.compute import ExperimentRecord, artifact_record, get_backend, register_run
from brainir.compute.registry import content_hash
from brainir.discovery.problem import DiscoveryProblem, pack_bundle, path_basename, unpack_bundle
from brainir.discovery.tournament import score_structure
from brainir.discovery.transfer import role_graph, role_graph_similarity

ROOT = Path(__file__).resolve().parents[1]


def _score_pair(truth: dict, a: DiscoveryProblem, b: DiscoveryProblem, res) -> dict:
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
        if not claim or not xb:
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
    from brainir.discovery.joint import discover_pair

    method, mode, inst_dir, seed, budget_a, budget_b, config, truth_path, packs = args
    inst_dir, truth_path = Path(inst_dir), Path(truth_path)
    name = path_basename(inst_dir)
    if not inst_dir.exists() and packs is not None:
        import tempfile
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
           "decoy": bool(truth["spec"].get("anchor_decoy")), "result_a": res.result_a.to_dict(), "result_b": res.result_b.to_dict(),
           "correspondence": res.correspondence, "role_alignment": res.role_alignment, "diagnostics": res.diagnostics}
    rec["score"] = _score_pair(truth, a, b, res)
    return rec


def _mean_of(rs: list[dict], f) -> float | None:
    v = [x for x in (f(r) for r in rs) if x is not None]
    return float(np.mean(v)) if v else None


def summarize(records: list[dict]) -> dict:
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


def to_markdown(out: dict) -> str:
    s = out["summary"]
    lines = [f"# Pair tournament — {out['label']}", "", f"{out['n_jobs']} jobs; budgets a {out['budget_a']} / b {out['budget_b']}; seeds {out['seeds']}; "
             f"wall {out['wall_s']} s on {out['backend'].get('backend')}", "",
             "| method/mode | n | success a | success b | both [CI] | corr P/R | role align | role-graph sim | calls a/b/adapt/total |", "|---|" * 9]
    for k, v in s.items():
        def f(x):
            return "n/a" if x is None else f"{x:.2f}"
        ci = f"[{v['both_ci95'][0]:.2f}, {v['both_ci95'][1]:.2f}]"
        lines.append(f"| {k} | {v['n_runs']} | {f(v['success_a'])} | {f(v['success_b'])} | {f(v['both_success'])} {ci} | "
                     f"{f(v['corr_precision'])}/{f(v['corr_recall'])} | {f(v['role_alignment_accuracy'])} | {f(v['role_graph_similarity_ab'])} | "
                     f"{f(v['calls_a'])}/{f(v['calls_b'])}/{f(v['calls_adaptation'])}/{f(v['calls_total'])} |")
    lines += ["", "by family (both-success rate):", ""]
    for k, v in s.items():
        lines.append(f"- {k}: " + ", ".join(f"{fam} {rate:.2f}" for fam, rate in v["by_family"].items()) +
                     f"; shift {v['shift_both_success']}; decoy {v['decoy_both_success']}")
    errors = [r for r in out["records"] if "error" in r]
    if errors:
        lines += ["", f"{len(errors)} failed jobs: " + "; ".join(f"{e.get('instance')}/{e.get('mode')}: {str(e['error'])[:120]}" for e in errors[:10])]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", default=["greedy_reference"])
    ap.add_argument("--modes", nargs="+", default=["independent", "transfer", "prior", "joint"])
    ap.add_argument("--suite", type=Path, default=ROOT / "data" / "synthetic" / "pairs_v1")
    ap.add_argument("--instances", nargs="*", default=None)
    ap.add_argument("--max-n", type=int, default=None)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--budget-a", type=int, default=500)
    ap.add_argument("--budget-b", type=int, default=500)
    ap.add_argument("--config", nargs="*", default=[], help="method=json")
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "tournament")
    args = ap.parse_args(argv)
    configs = {}
    for c in args.config:
        m, _, js = c.partition("=")
        configs[m] = json.loads(js)
    inst_dirs = sorted(p for p in (args.suite / "instances").iterdir() if p.is_dir())
    if args.instances:
        inst_dirs = [p for p in inst_dirs if p.name in set(args.instances)]
    if args.max_n is not None:
        keep = []
        for d in inst_dirs:
            sizes = d.name.split("__n", 1)[1].split("__")[0].split("x")
            if max(int(x) for x in sizes) <= args.max_n:
                keep.append(d)
        inst_dirs = keep
    jobs = [(m, mode, str(d), s, args.budget_a, args.budget_b, configs.get(m, {}), str(args.suite / "truth" / f"{d.name}.json"), None)
            for m in args.methods for mode in args.modes for d in inst_dirs for s in args.seeds]
    t0 = time.time()
    backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=7200, max_containers=args.containers) if args.backend == "modal" else None
    if backend is not None:
        from brainir.compute.backend import Shared, split_failures
        packs: dict = {}
        for d in inst_dirs:
            pack = pack_bundle(d, "a")
            pack.update(pack_bundle(d, "b"))
            packs[d.name] = pack
            packs[f"truth/{d.name}"] = (args.suite / "truth" / f"{d.name}.json").read_bytes()
        remote = [(*j[:-1], Shared("packs")) for j in jobs]
        records, failed = split_failures(backend.map(pair_job, remote, shared={"packs": packs}))
        for f in failed:
            j = jobs[f["index"]]
            records.append({"method": j[0], "mode": j[1], "instance": path_basename(j[2]), "error": f["error"]})
    elif args.workers > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            records = list(ex.map(pair_job, jobs))
    else:
        records = [pair_job(j) for j in jobs]
    wall = time.time() - t0
    bstats = backend.last_stats.to_dict() if backend is not None and backend.last_stats else {"backend": "local", "n_workers": args.workers}
    out = {"label": args.label, "suite": args.suite.name, "methods": args.methods, "modes": args.modes, "n_jobs": len(jobs), "budget_a": args.budget_a,
           "budget_b": args.budget_b, "seeds": args.seeds, "wall_s": round(wall, 1), "backend": bstats, "summary": summarize(records), "records": records}
    args.out.mkdir(parents=True, exist_ok=True)
    p = args.out / f"{args.label}.json"
    p.write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    (args.out / f"{args.label}.md").write_text(to_markdown(out), encoding="utf-8", newline="\n")
    rec = ExperimentRecord(name=args.label, config={"methods": args.methods, "modes": args.modes, "budget_a": args.budget_a, "budget_b": args.budget_b,
                                                    "configs": configs, "instances": [d.name for d in inst_dirs]},
                           seeds=args.seeds, inputs={"suite": args.suite.name, "n_instances": len(inst_dirs), "jobs_hash": content_hash(jobs)},
                           backend=bstats, artifacts={"results": artifact_record(p)},
                           summary={k: {kk: vv for kk, vv in v.items() if kk != "by_family"} for k, v in out["summary"].items()})
    register_run(rec, ROOT / "benchmarks" / "dng100" / "manifests" / "experiments")
    print(to_markdown(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
