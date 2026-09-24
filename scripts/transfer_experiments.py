"""Cross-connectome transfer experiments on two public networks (goal3 sections 17-18), scored WITHOUT the oracle.

    uv run python scripts/transfer_experiments.py --method brainir_v1 --a male-cns_v1.0 --b manc_v1.2.1 \
        --budget-a 1000 --budget-b 1000 --seeds 0 1 2 --modes independent transfer prior joint --backend modal --label xfer_v1

For each seed and each direction (a -> b and b -> a) and each mode, `brainir.discovery.joint.discover_pair` runs with the given
budgets (adaptation calls reported separately). Every discovered mechanism is then checked on the TRUE simulator of its own
network with fresh parameter seeds (keep-only sufficiency; 1-minimality), and the destination core of `transfer` is compared with
a sign-matched null (random interneuron sets of the same size and signs). Reported per mode and direction: sufficiency pass rate
in source and destination, calls (source / destination / adaptation / total), core sizes, null pass rate, and — when both runs
exist — the overlap between the transferred destination core and the independently discovered one.
Hidden-oracle scoring of cross-connectome claims is NOT done here (it happens once, in scripts/blind_eval.py, after the lock).
Output: research/phase2/transfer/<label>.{json,md} + registry record.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from brainir.compute import ExperimentRecord, artifact_record, register_run
from brainir.discovery.problem import pack_bundle
from brainir.discovery.remote import get_discovery_backend as get_backend
from brainir.discovery.transfer import transfer_experiment_job

ROOT = Path(__file__).resolve().parents[1]


def _summ(rows: list[dict]) -> dict:
    def mean(f):
        v = [f(r) for r in rows]
        v = [x for x in v if x is not None]
        return float(np.mean(v)) if v else None

    return {"n": len(rows), "src_pass_rate": mean(lambda r: float(r["check_src"]["passed"])),
            "dst_pass_rate": mean(lambda r: float(r["check_dst"]["passed"])),
            "dst_pass_fraction_mean": mean(lambda r: r["check_dst"]["pass_fraction"]),
            "calls_src": mean(lambda r: (r["budget"] or {}).get("a")), "calls_dst": mean(lambda r: (r["budget"] or {}).get("b")),
            "calls_adaptation": mean(lambda r: (r["budget"] or {}).get("adaptation")), "calls_total": mean(lambda r: (r["budget"] or {}).get("total")),
            "size_src": mean(lambda r: r["n_src"]), "size_dst": mean(lambda r: r["n_dst"]),
            "null_pass_rate": mean(lambda r: (r.get("null") or {}).get("pass_rate"))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True)
    ap.add_argument("--bundle", type=Path, default=ROOT / "benchmarks" / "dng100" / "public_blind")
    ap.add_argument("--a", default="male-cns_v1.0")
    ap.add_argument("--b", default="manc_v1.2.1")
    ap.add_argument("--modes", nargs="+", default=["independent", "transfer", "prior", "joint"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
    ap.add_argument("--budget-a", type=int, default=1000)
    ap.add_argument("--budget-b", type=int, default=1000)
    ap.add_argument("--config", default="{}")
    ap.add_argument("--n-null", type=int, default=20)
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--containers", type=int, default=60)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "transfer")
    args = ap.parse_args(argv)
    config = json.loads(args.config)
    dirs = [(args.a, args.b), (args.b, args.a)]
    jobs = [(str(args.bundle), s_, d_, args.method, mode, seed, args.budget_a if s_ == args.a else args.budget_b,
             args.budget_b if d_ == args.b else args.budget_a, config, args.n_null, None)
            for s_, d_ in dirs for mode in args.modes for seed in args.seeds]
    t0 = time.time()
    backend = get_backend("modal", cpu=1.0, memory_mb=4096, timeout_s=7200, max_containers=args.containers) if args.backend == "modal" else None
    if backend is not None:
        from brainir.compute.backend import Shared, split_failures
        pack = pack_bundle(args.bundle, args.a)
        pack.update(pack_bundle(args.bundle, args.b))
        remote = [(*j[:-1], Shared("packs")) for j in jobs]
        rows, failed = split_failures(backend.map(transfer_experiment_job, remote, shared={"packs": {"bundle": pack}}))
        rows += [{"error": f["error"], "job": list(jobs[f["index"]][1:6])} for f in failed]
    elif args.workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            rows = list(ex.map(transfer_experiment_job, jobs))
    else:
        rows = [transfer_experiment_job(j) for j in jobs]
    ok = [r for r in rows if "check_src" in r]
    summary: dict = {}
    for s_, d_ in dirs:
        for mode in args.modes:
            rs = [r for r in ok if r["direction"] == f"{s_}->{d_}" and r["mode"] == mode]
            if rs:
                summary[f"{s_}->{d_}/{mode}"] = _summ(rs)
        ind = {r["seed"]: set(r["core_dst"]) for r in ok if r["direction"] == f"{s_}->{d_}" and r["mode"] == "independent"}
        tr = {r["seed"]: set(r["core_dst"]) for r in ok if r["direction"] == f"{s_}->{d_}" and r["mode"] == "transfer"}
        common = sorted(set(ind) & set(tr))
        if common:
            summary[f"{s_}->{d_}/transfer_vs_independent_jaccard"] = float(np.mean([len(ind[s] & tr[s]) / len(ind[s] | tr[s]) if (ind[s] | tr[s]) else 1.0
                                                                                 for s in common]))
    args.out.mkdir(parents=True, exist_ok=True)
    bstats = backend.last_stats.to_dict() if backend is not None and backend.last_stats else {"backend": "local", "n_workers": args.workers}
    payload = {"label": args.label, "method": args.method, "a": args.a, "b": args.b, "modes": args.modes, "seeds": args.seeds,
               "budget_a": args.budget_a, "budget_b": args.budget_b, "config": config, "wall_s": round(time.time() - t0, 1), "backend": bstats,
               "summary": summary, "rows": rows}
    p = args.out / f"{args.label}.json"
    p.write_text(json.dumps(payload, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")

    def f(x):
        return "n/a" if x is None else (f"{x:.2f}" if isinstance(x, float) else str(x))

    lines = [f"# Cross-connectome transfer experiments — {args.label}", "", f"method `{args.method}`; networks `{args.a}` <-> `{args.b}`; seeds "
             f"{args.seeds}; budgets {args.budget_a}/{args.budget_b}; {len(ok)} runs ({len(rows) - len(ok)} failed); oracle-free", "",
             "| direction / mode | n | source sufficient | destination sufficient | dest. pass fraction | calls src / dst / adapt / total | "
             "size src / dst | null pass |", "|---|---|---|---|---|---|---|---|"]
    for k, v in summary.items():
        if isinstance(v, dict):
            lines.append(f"| {k} | {v['n']} | {f(v['src_pass_rate'])} | {f(v['dst_pass_rate'])} | {f(v['dst_pass_fraction_mean'])} | "
                         f"{f(v['calls_src'])} / {f(v['calls_dst'])} / {f(v['calls_adaptation'])} / {f(v['calls_total'])} | "
                         f"{f(v['size_src'])} / {f(v['size_dst'])} | {f(v['null_pass_rate'])} |")
    for k, v in summary.items():
        if not isinstance(v, dict):
            lines.append(f"- {k}: {v:.2f}")
    (args.out / f"{args.label}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    rec = ExperimentRecord(name=f"transfer_{args.label}", config={k: payload[k] for k in ("method", "a", "b", "modes", "budget_a", "budget_b", "config")},
                           seeds=args.seeds, inputs={"bundle": args.bundle.name}, backend=bstats, artifacts={"results": artifact_record(p)},
                           summary={k: v for k, v in summary.items() if isinstance(v, dict)})
    register_run(rec, ROOT / "benchmarks" / "dng100" / "manifests" / "experiments")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
