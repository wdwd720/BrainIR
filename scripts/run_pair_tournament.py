"""Cross-connectome pair tournament: run `brainir.discovery.joint.discover_pair` in every mode on a synthetic pair suite and score
against the withheld truth (goal3 sections 17-18, 22; scoring in brainir.discovery.pair_tournament).

    uv run python scripts/run_pair_tournament.py --methods greedy_reference --modes independent transfer prior joint \
        --budget-a 500 --budget-b 500 --seeds 0 1 [--max-n 200] [--backend modal] --label pairs_small

Writes research/phase2/tournament/<label>.{json,md} + registry record.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from brainir.compute import ExperimentRecord, artifact_record, register_run
from brainir.compute.registry import content_hash
from brainir.discovery.pair_tournament import pair_job, pairs_markdown, summarize_pairs
from brainir.discovery.problem import pack_bundle, path_basename
from brainir.discovery.provenance import launch_provenance
from brainir.discovery.remote import get_discovery_backend as get_backend
from brainir.discovery.tournament import select_instances, suite_hash

ROOT = Path(__file__).resolve().parents[1]


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
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--timeout", type=int, default=7200)
    ap.add_argument("--allow-dirty", action="store_true")
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
        keep = set(select_instances(args.suite, max_n=args.max_n))
        inst_dirs = [d for d in inst_dirs if d.name in keep]
    jobs = [(m, mode, str(d), s, args.budget_a, args.budget_b, configs.get(m, {}), str(args.suite / "truth" / f"{d.name}.json"), None)
            for m in args.methods for mode in args.modes for d in inst_dirs for s in args.seeds]
    code = launch_provenance()
    if args.backend == "modal" and code["dirty_src"] and not args.allow_dirty:
        print("refusing a remote campaign with uncommitted changes in src/; commit first or pass --allow-dirty")
        return 1
    t0 = time.time()
    backend = (get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=args.timeout, max_containers=args.containers)
               if args.backend == "modal" else None)
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
            records.append({"method": j[0], "mode": j[1], "instance": path_basename(j[2]), "seed": j[3], "error": f["error"]})
    elif args.workers > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            records = list(ex.map(pair_job, jobs))
    else:
        records = [pair_job(j) for j in jobs]
    wall = time.time() - t0
    bstats = backend.last_stats.to_dict() if backend is not None and backend.last_stats else {"backend": "local", "n_workers": args.workers}
    out = {"label": args.label, "suite": args.suite.name, "methods": args.methods, "modes": args.modes, "n_jobs": len(jobs), "budget_a": args.budget_a,
           "budget_b": args.budget_b, "seeds": args.seeds, "wall_s": round(wall, 1), "backend": bstats, "summary": summarize_pairs(records),
           "records": records}
    args.out.mkdir(parents=True, exist_ok=True)
    p = args.out / f"{args.label}.json"
    p.write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    (args.out / f"{args.label}.md").write_text(pairs_markdown(out), encoding="utf-8", newline="\n")
    rec = ExperimentRecord(name=args.label, config={"methods": args.methods, "modes": args.modes, "budget_a": args.budget_a, "budget_b": args.budget_b,
                                                    "configs": configs, "instances": [d.name for d in inst_dirs]},
                           seeds=args.seeds, inputs={"suite": args.suite.name, "suite_sha256": suite_hash(args.suite, inst_dirs),
                                                     "n_instances": len(inst_dirs), "jobs_hash": content_hash(jobs),
                                                     "source_tree_sha256": code["source_tree_sha256"], "launched_utc": code["launched_utc"]},
                           backend=bstats, artifacts={"results": artifact_record(p)}, code=code,
                           summary={k: {kk: vv for kk, vv in v.items() if kk != "by_family"} for k, v in out["summary"].items()})
    register_run(rec, ROOT / "benchmarks" / "dng100" / "manifests" / "experiments")
    print(pairs_markdown(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
