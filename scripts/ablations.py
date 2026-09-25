"""Ablations (goal3 section 41): run one method with its default configuration and with each component switched off, on the same
instances, node orders and seeds, and report paired differences.

    uv run python scripts/ablations.py --method brainir_v1 --suite data/synthetic/mechanisms_v1_heldout \
        --variant no_group_testing='{"use_group_testing": false}' --variant no_prior='{"use_structural_prior": false}' \
        --networks main order1 --seeds 0 1 --budget 1000 [--max-n 600] [--backend modal] --label ablate_v1
    uv run python scripts/ablations.py --method brainir_v1 --label ablate_v1 --resummarize   # re-analyse finished runs only

Each variant is registered under the name `<method>@<variant>` only inside this run (the method class is reused with a merged
config). Output: research/phase2/tournament/<label>_<variant>.{json,md} per variant and <label>_summary.{json,md} with, per
variant, success / causal functional success / identity consistency / calls / robust pass / role accuracy / Brier and the paired
difference to the default. The paired differences are computed by scripts/compare_tournament_methods.py: runs paired on
(instance, network, seed), 95 % bootstrap CIs that resample INSTANCES (the runs of one instance are correlated; review C
finding C7), failed runs counted as unsuccessful at the full budget.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare_tournament_methods import compare  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
# (metric in compare(), column title, sign): sign -1 turns "calls saved by the variant" into "extra calls of the variant"
COLUMNS = (("structural_success", "structural", 1), ("success_intact", "success_intact", 1), ("causal_functional_success", "causal functional", 1),
           ("adversarial_correct", "adversarial correct", 1), ("adversarial_confident_wrong", "confident-wrong", 1),
           ("essential_recall", "essential recall", 1), ("identity_jaccard", "identity Jaccard", 1), ("identical_cores", "identical cores", 1),
           ("calls", "extra calls", -1), ("robust_sd_x2", "robust sd x2", 1), ("core_size", "core size", 1))


def _load(path: Path) -> dict:
    gz = path.with_name(path.name + ".gz")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return json.loads(gzip.open(gz, "rt", encoding="utf-8").read())


def paired_vs_default(default: dict, variant: dict, name: str) -> dict:
    """Paired comparison of one variant with the default configuration (same method; records relabelled)."""
    recs = [dict(r, method="default") for r in default["records"]] + [dict(r, method=name) for r in variant["records"]]
    budgets = {"default": default.get("budget"), name: variant.get("budget")}
    res = compare(recs, budgets, name, "default")
    out = {}
    for m, _, sign in COLUMNS:
        v = res["metrics"].get(m)
        if v is not None:
            lo, hi = v["ci95"]
            out[m] = {"default": v["b"], "variant": v["a"], "diff": sign * v["diff"],
                      "ci95": [sign * lo, sign * hi] if sign > 0 else [sign * hi, sign * lo]}
    out["n_runs"], out["n_instances"] = res["n_runs"], res["n_instances"]
    return out


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
    ap.add_argument("--resummarize", action="store_true", help="no runs: re-analyse the finished <label>_<variant>.json(.gz) files")
    args = ap.parse_args(argv)
    results: dict[str, dict] = {}
    if args.resummarize:
        names = sorted({p.name.removesuffix(".gz").removesuffix(".json")[len(args.label) + 1:] for p in args.out.glob(f"{args.label}_*.json*")})
        names = [n for n in names if n and n != "summary" and not n.endswith("_summary")]  # per-variant tournament summaries too
        if "default" not in names:
            raise SystemExit(f"no {args.label}_default.json(.gz) in {args.out}")
        for n in ["default"] + [n for n in names if n != "default"]:
            results[n] = _load(args.out / f"{args.label}_{n}.json")
        variants = {n: (results[n]["records"][0].get("config") if n != "default" else {}) for n in results}
        first = results["default"]
        n_inst, budget, seeds, networks = len({r["instance"] for r in first["records"]}), first.get("budget"), first.get("seeds"), first.get("networks")
    else:
        from brainir.discovery.remote import get_discovery_backend as get_backend
        from brainir.discovery.tournament import run_tournament, select_instances

        variants = {"default": {}}
        for v in args.variant:
            name, _, js = v.partition("=")
            variants[name] = json.loads(js)
        inst = select_instances(args.suite, max_n=args.max_n)
        backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=7200, max_containers=args.containers) if args.backend == "modal" else None
        registry = ROOT / "benchmarks" / "dng100" / "manifests" / "experiments"
        for name, cfg in variants.items():
            results[name] = run_tournament([args.method], args.suite, instances=inst, networks=tuple(args.networks), seeds=tuple(args.seeds),
                                           budget=args.budget, configs={args.method: cfg}, backend=backend, workers=args.workers, robust=True,
                                           out_dir=args.out, registry_dir=registry, label=f"{args.label}_{name}")
        n_inst, budget, seeds, networks = len(inst), args.budget, args.seeds, args.networks
    summary: dict = {"label": args.label, "method": args.method, "budget": budget, "seeds": seeds, "networks": networks, "n_instances": n_inst,
                     "resampling_unit": "instance", "variants": {}}
    for name, res in results.items():
        s = res["summary"].get(args.method, {})
        entry = {"config": variants[name] if not args.resummarize or name == "default" else {k: v for k, v in (variants[name] or {}).items()
                                                                                             if (results["default"]["records"][0].get("config") or {}).get(k) != v},
                 "success": s.get("success_rate"), "causal_functional": s.get("functional_success_causal_rate"),
                 "identity": (s.get("identity_consistency") or {}).get("pairwise_jaccard_mean"), "calls_mean": s.get("calls_mean"),
                 "robust": s.get("functional_robust_mean"), "role_accuracy": s.get("role_accuracy_mean"), "brier": s.get("brier_mean")}
        if name != "default":
            entry["paired"] = paired_vs_default(results["default"], res, name)
        summary["variants"][name] = entry
    (args.out / f"{args.label}_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")

    def f(x):
        return "–" if x is None else f"{x:.3f}"

    lines = [f"# Ablations — {args.method} ({args.label})", "", f"{n_inst} instances x {networks} x seeds {seeds}; budget {budget}", "",
             "| variant | config | structural | causal functional | identity Jaccard | mean calls | robust | role acc | Brier |",
             "|---|---|---|---|---|---|---|---|---|"]
    for name, e in summary["variants"].items():
        lines.append(f"| {name} | `{json.dumps(e['config'])}` | {f(e['success'])} | {f(e['causal_functional'])} | {f(e['identity'])} | "
                     f"{f(e['calls_mean'])} | {f(e['robust'])} | {f(e['role_accuracy'])} | {f(e['brier'])} |")
    cols = [c for c in COLUMNS if any(c[0] in (e.get("paired") or {}) for e in summary["variants"].values())]
    lines += ["", "Paired differences (variant - default; calls: extra calls of the variant) [95% CI, instances resampled; failed runs count "
              "as unsuccessful at the full budget]:", "", "| variant | " + " | ".join(c[1] for c in cols) + " |", "|---|" + "---|" * len(cols)]
    for name, e in summary["variants"].items():
        if name == "default":
            continue
        cells = []
        for m, _, _ in cols:
            p = e["paired"].get(m)
            cells.append("–" if not p else f"{p['diff']:+.3f} [{p['ci95'][0]:+.3f}, {p['ci95'][1]:+.3f}]")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    (args.out / f"{args.label}_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
