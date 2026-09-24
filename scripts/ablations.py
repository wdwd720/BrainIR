"""Ablations (goal3 section 41): run one method with its default configuration and with each component switched off, on the same
instances, node orders and seeds, and report paired differences.

    uv run python scripts/ablations.py --method brainir_v1 --suite data/synthetic/mechanisms_v1_heldout \
        --variant no_group_testing='{"use_group_testing": false}' --variant no_prior='{"use_structural_prior": false}' \
        --networks main order1 --seeds 0 1 --budget 1000 [--max-n 600] [--backend modal] --label ablate_v1

Each variant is registered under the name `<method>@<variant>` only inside this run (the method class is reused with a merged
config). Output: research/phase2/tournament/<label>_<variant>.{json,md} per variant and <label>_summary.{json,md} with, per
variant, success / causal functional success / identity consistency / calls / robust pass / role accuracy / Brier and the paired
difference to the default (bootstrap 95 % CI over (instance, network, seed) triples).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from brainir.discovery.remote import get_discovery_backend as get_backend
from brainir.discovery.tournament import run_tournament, select_instances

ROOT = Path(__file__).resolve().parents[1]
METRICS = {
    "structural_success": lambda r: float(r["structure"]["success"]),
    "causal_functional": lambda r: (None if "functional_success_causal" not in (r.get("function") or {})
                                    else float(r["function"]["functional_success_causal"])),
    "calls": lambda r: float(r["result"]["budget"].get("calls", 0)),
    "robust_pass": lambda r: (r.get("function") or {}).get("robust_sd_x2"),
    "size": lambda r: float(len(r["result"]["core"])),
}


def _key(r: dict) -> tuple:
    return (r["instance"], r["network"], r["seed"])


def _paired(base: list[dict], var: list[dict], f, rng) -> dict | None:
    b = {_key(r): f(r) for r in base if "structure" in r}
    v = {_key(r): f(r) for r in var if "structure" in r}
    keys = [k for k in sorted(set(b) & set(v)) if b[k] is not None and v[k] is not None]
    if not keys:
        return None
    d = np.array([v[k] - b[k] for k in keys], dtype=float)
    boot = [d[rng.integers(0, len(d), len(d))].mean() for _ in range(2000)]
    return {"n": len(keys), "default": float(np.mean([b[k] for k in keys])), "variant": float(np.mean([v[k] for k in keys])),
            "diff": float(d.mean()), "ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", required=True)
    ap.add_argument("--variant", action="append", default=[], help="name=JSON config override (repeatable)")
    ap.add_argument("--suite", type=Path, default=ROOT / "data" / "synthetic" / "mechanisms_v1_heldout")
    ap.add_argument("--max-n", type=int, default=None)
    ap.add_argument("--networks", nargs="+", default=["main", "order1"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1])
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "tournament")
    args = ap.parse_args(argv)
    variants = {"default": {}}
    for v in args.variant:
        name, _, js = v.partition("=")
        variants[name] = json.loads(js)
    inst = select_instances(args.suite, max_n=args.max_n)
    backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=7200, max_containers=args.containers) if args.backend == "modal" else None
    registry = ROOT / "benchmarks" / "dng100" / "manifests" / "experiments"
    results = {}
    for name, cfg in variants.items():
        res = run_tournament([args.method], args.suite, instances=inst, networks=tuple(args.networks), seeds=tuple(args.seeds), budget=args.budget,
                             configs={args.method: cfg}, backend=backend, workers=args.workers, robust=True, out_dir=args.out,
                             registry_dir=registry, label=f"{args.label}_{name}")
        results[name] = res
    rng = np.random.default_rng(0)
    base = results["default"]["records"]
    summary: dict = {"label": args.label, "method": args.method, "budget": args.budget, "seeds": args.seeds, "networks": args.networks,
                     "n_instances": len(inst), "variants": {}}
    for name, res in results.items():
        s = res["summary"].get(args.method, {})
        entry = {"config": variants[name], "success": s.get("success_rate"), "causal_functional": s.get("functional_success_causal_rate"),
                 "identity": (s.get("identity_consistency") or {}).get("pairwise_jaccard_mean"), "calls_mean": s.get("calls_mean"),
                 "robust": s.get("functional_robust_mean"), "role_accuracy": s.get("role_accuracy_mean"), "brier": s.get("brier_mean")}
        if name != "default":
            entry["paired"] = {m: _paired(base, res["records"], f, rng) for m, f in METRICS.items()}
        summary["variants"][name] = entry
    (args.out / f"{args.label}_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")

    def f(x):
        return "–" if x is None else f"{x:.3f}"

    lines = [f"# Ablations — {args.method} ({args.label})", "", f"{len(inst)} instances x {args.networks} x seeds {args.seeds}; budget {args.budget}", "",
             "| variant | config | structural | causal functional | identity Jaccard | mean calls | robust | role acc | Brier |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, e in summary["variants"].items():
        lines.append(f"| {name} | `{json.dumps(e['config'])}` | {f(e['success'])} | {f(e['causal_functional'])} | {f(e['identity'])} | "
                     f"{f(e['calls_mean'])} | {f(e['robust'])} | {f(e['role_accuracy'])} | {f(e['brier'])} |")
    lines += ["", "Paired differences (variant - default) [95% CI]:", "", "| variant | " + " | ".join(METRICS) + " |", "|---|" + "---|" * len(METRICS)]
    for name, e in summary["variants"].items():
        if name == "default":
            continue
        cells = []
        for m in METRICS:
            p = e["paired"].get(m)
            cells.append("–" if not p else f"{p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    (args.out / f"{args.label}_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
