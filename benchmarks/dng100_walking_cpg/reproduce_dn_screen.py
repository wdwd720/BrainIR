"""Reproduce the paper's descending-neuron activation screen with BrainIR's simulator (ANSWER-KEY-ADJACENT for the report).

    uv run python benchmarks/dng100_walking_cpg/reproduce_dn_screen.py --dataset manc --version v1.2.1 --replicates 16 --backend modal

Candidates = every excitatory descending neuron of the network (class descending, sign +1 under the network's labels;
933 in the paper's MANC front-leg network). Each (candidate, seed) job auto-tunes the amplitude (start 128) and scores
the front-leg motor-neuron rhythm (`brainir.sim.screen`). The report ranks candidates by mean score over usable
replicates and compares with the published statements: DNg100 among the top-scoring neurons/types, 29 of 933 DNs with
mean > 0.5 (128 replicates), ~7.9% never usable. Runs are registered in benchmarks/dng100/manifests/experiments/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from brainir.compute import ExperimentRecord, Shared, artifact_record, content_hash, get_backend, register_run, split_failures
from brainir.sim import ModelConfig
from brainir.sim.screen import ScreenConfig, aggregate_screen, run_screen_job

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reproduce_dynamics import paper_network  # noqa: E402

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
REGISTRY = HERE.parent / "dng100" / "manifests" / "experiments"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="manc")
    ap.add_argument("--version", default="v1.2.1")
    ap.add_argument("--nt", choices=["paper", "brainir"], default="paper")
    ap.add_argument("--replicates", type=int, default=16)
    ap.add_argument("--seed0", type=int, default=0)
    ap.add_argument("--t-end", type=float, default=1.0)
    ap.add_argument("--max-candidates", type=int, default=None, help="debug: only the first k candidates")
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--containers", type=int, default=100)
    args = ap.parse_args(argv)
    wt, net, readout = paper_network(args.dataset, args.version, args.nt)
    tab = net.table
    cands = np.flatnonzero((tab["role_class"].to_numpy() == "descending") & (net.signs > 0))
    if args.max_candidates:
        cands = cands[: args.max_candidates]
    cfg = ModelConfig(t_end=args.t_end)
    scfg = ScreenConfig()
    seeds = list(range(args.seed0, args.seed0 + args.replicates))
    shared = {"W": net.W, "readout": readout, "sizes": net.sizes}
    jobs = [(Shared("W"), cfg, int(c), Shared("readout"), Shared("sizes"), s, scfg) for c in cands for s in seeds]
    backend = get_backend(args.backend, n_workers=args.workers, cpu=1.0, memory_mb=3072, timeout_s=3600, max_containers=args.containers)
    t0 = time.time()
    reps, failed = split_failures(backend.map(run_screen_job, jobs, shared=shared))
    wall = time.time() - t0
    if failed:
        print(f"WARNING: {len(failed)} of {len(jobs)} jobs failed; first: {failed[0]}")
    agg = aggregate_screen(reps)
    ids = net.ids
    for row in agg["candidates"]:
        row["source_id"] = int(ids[row["candidate"]])
        row["cell_type"] = tab["cell_type"].iloc[row["candidate"]]
    scores = [c["mean_score"] for c in agg["candidates"] if c["mean_score"] is not None]
    n_unusable = sum(1 for c in agg["candidates"] if c["n_usable"] == 0)
    dn_rows = [c for c in agg["candidates"] if c["cell_type"] == "DNg100"]
    # type-level ranking (mean over all replicates of all members)
    by_type: dict[str, list] = {}
    for r in reps:
        if r.usable:
            by_type.setdefault(tab["cell_type"].iloc[r.candidate], []).append(r.score)
    type_rank = sorted(((k, float(np.mean(v)), len(v)) for k, v in by_type.items() if k is not None), key=lambda x: -x[1])
    summary = {
        "dataset": args.dataset, "version": args.version, "nt": args.nt, "n_candidates": int(len(cands)), "replicates": args.replicates,
        "t_end": args.t_end, "screen_config": scfg.to_dict(), "n_jobs": len(jobs), "n_failed_jobs": len(failed), "failed_jobs": failed[:50],
        "wall_time_s": round(wall, 1), "backend": backend.last_stats.to_dict(),
        "n_candidates_with_mean_gt_0_5": int(sum(s > 0.5 for s in scores)), "n_candidates_never_usable": n_unusable,
        "fraction_never_usable": n_unusable / max(1, len(cands)),
        "dng100": [{k: row[k] for k in ("source_id", "rank", "mean_score", "median_score", "n_usable", "best_score", "median_frequency_hz")}
                   for row in dn_rows],
        "type_rank_top10": [{"type": k, "mean_score": s, "n": n, "rank": i + 1} for i, (k, s, n) in enumerate(type_rank[:10])],
        "dng100_type_rank": next((i + 1 for i, (k, _, _) in enumerate(type_rank) if k == "DNg100"), None),
        "published": {"n_dns": 933, "mean_gt_0_5": 29, "never_usable_fraction": 0.079, "dng100_neuron_ranks_128rep": [3, 4],
                      "dng100_type_rank": 1, "note": "v2 screen: 128 replicates; v1 screen (16 replicates, cap 500): DNg100 neurons ranked 1 and 2"},
    }
    RESULTS.mkdir(exist_ok=True)
    name = f"dn_screen_{args.dataset}_{args.version}_nt-{args.nt}_r{args.replicates}" + (f"_first{args.max_candidates}" if args.max_candidates else "")
    (RESULTS / f"{name}.json").write_text(json.dumps({"summary": summary, "candidates": agg["candidates"],
                                                       "replicates": [r.to_dict() for r in reps]}, indent=1, default=float) + "\n",
                                          encoding="utf-8", newline="\n")
    top = agg["candidates"][:15]
    lines = [f"# DN activation screen — {args.dataset}:{args.version} (nt={args.nt}, {len(cands)} candidates x {args.replicates} replicates)", "",
             f"wall {wall:.0f} s on {args.backend}; candidates with mean > 0.5: {summary['n_candidates_with_mean_gt_0_5']} "
             f"(paper: 29 of 933 with 128 replicates); never usable: {n_unusable} ({summary['fraction_never_usable']:.1%}; paper 7.9%).", "",
             "| rank | source_id | type | mean | median | usable | best | f (Hz) |", "|---|---|---|---|---|---|---|---|"]
    for c in top:
        f_hz = "" if c["median_frequency_hz"] is None else round(c["median_frequency_hz"], 1)
        lines.append(f"| {c['rank']} | {c['source_id']} | {c['cell_type']} | {c['mean_score']:.3f} | {c['median_score']:.3f} | "
                     f"{c['n_usable']}/{c['n_replicates']} | {c['best_score']:.3f} | {f_hz} |")
    lines += ["", f"DNg100 neurons: {summary['dng100']}", f"DNg100 type rank: {summary['dng100_type_rank']} (paper: 1)", ""]
    (RESULTS / f"{name}.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))
    rec = ExperimentRecord(name=name, config={"model": cfg.to_dict(), "screen": scfg.to_dict(), "network": net.meta, "candidates": int(len(cands))},
                           seeds=seeds, inputs={"network_hash": content_hash(net.meta)}, backend=backend.last_stats.to_dict(),
                           artifacts={"results": artifact_record(RESULTS / f"{name}.json")},
                           summary={k: summary[k] for k in ("n_candidates_with_mean_gt_0_5", "fraction_never_usable", "dng100", "dng100_type_rank")})
    print("registered", register_run(rec, REGISTRY).name)


if __name__ == "__main__":
    main()
