"""Query-efficiency curves: run methods on the synthetic suite at several simulator budgets (goal3 section 19).

    uv run python scripts/budget_curve.py --methods greedy_reference brainir_v1 --budgets 100 250 500 1000 2000 --max-n 100 \
        --seeds 0 1 --networks main order1 [--backend modal] --label curve_small

Writes research/phase2/tournament/<label>_b<budget>.{json,md} per budget plus <label>_curve.{json,md} with success rate and
functional pass rate versus budget and the area under the (log-budget, success) curve.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from brainir.compute import get_backend
from brainir.discovery.tournament import run_tournament, select_instances

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", required=True)
    ap.add_argument("--budgets", nargs="+", type=int, default=[100, 250, 500, 1000, 2000])
    ap.add_argument("--suite", type=Path, default=ROOT / "data" / "synthetic" / "mechanisms_v1")
    ap.add_argument("--max-n", type=int, default=None)
    ap.add_argument("--families", nargs="*", default=None)
    ap.add_argument("--networks", nargs="+", default=["main"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--config", nargs="*", default=[])
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--label", default="curve")
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "tournament")
    args = ap.parse_args(argv)
    configs = {}
    for c in args.config:
        m, _, js = c.partition("=")
        configs[m] = json.loads(js)
    inst = select_instances(args.suite, max_n=args.max_n, families=args.families)
    backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=7200, max_containers=args.containers) if args.backend == "modal" else None
    curve: dict[str, dict] = {m: {"budgets": [], "success": [], "functional": [], "calls": []} for m in args.methods}
    for b in args.budgets:
        res = run_tournament(args.methods, args.suite, instances=inst, networks=tuple(args.networks), seeds=tuple(args.seeds), budget=b, configs=configs,
                             backend=backend, workers=args.workers, robust=False, out_dir=args.out,
                             registry_dir=ROOT / "benchmarks" / "dng100" / "manifests" / "experiments", label=f"{args.label}_b{b}")
        for m in args.methods:
            s = res["summary"].get(m)
            if s:
                curve[m]["budgets"].append(b); curve[m]["success"].append(s["success_rate"])
                curve[m]["functional"].append(s["functional_nominal_mean"]); curve[m]["calls"].append(s["calls_mean"])
    for c in curve.values():
        if len(c["budgets"]) > 1:
            x = np.log10(c["budgets"]); y = np.array(c["success"])
            c["auc_log_budget"] = float(np.trapz(y, x) / (x[-1] - x[0]))
    (args.out / f"{args.label}_curve.json").write_text(json.dumps({"label": args.label, "instances": inst, "curve": curve}, indent=1) + "\n",
                                                        encoding="utf-8", newline="\n")
    lines = [f"# Query-efficiency curve — {args.label}", "", f"{len(inst)} instances x networks {args.networks} x seeds {args.seeds}", "",
             "| method | " + " | ".join(f"b={b}" for b in args.budgets) + " | AUC(log budget) |", "|---|" + "---|" * (len(args.budgets) + 1)]
    for m, c in curve.items():
        cells = [f"{s:.2f} / {f if f is None else round(f, 2)}" for s, f in zip(c["success"], c["functional"])]
        lines.append(f"| {m} | " + " | ".join(cells) + f" | {c.get('auc_log_budget', float('nan')):.3f} |")
    lines += ["", "cells: success rate / mean functional pass fraction (nominal)"]
    (args.out / f"{args.label}_curve.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
