"""Anti-gaming checks (goal3 section 33): does a method's synthetic performance survive meaningless representation changes?

    uv run python scripts/anti_gaming.py --methods brainir_v1 greedy_reference --transforms reorder_edges resalt_tokens \
        strip_annotations add_sink_distractors widen_parameters --max-n 100 --seeds 0 1 --budget 1000 [--backend modal] --label ag_v1

For each transform a perturbed copy of the synthetic suite is written to data/cache/anti_gaming/<transform>/ (truth copied: positions
are preserved) and the tournament is run on it with the same methods, seeds and budget as on the unperturbed suite ("baseline"
row). Node-order and id permutations are covered by the `order1` networks and by scripts/reliability_sweep.py.
Output: research/phase2/tournament/<label>_<transform>.{json,md} and <label>_summary.{json,md} (paired success differences with
bootstrap CIs per method and transform).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from brainir import paths
from brainir.discovery.perturb import TRANSFORMS, perturb_suite
from brainir.discovery.remote import get_discovery_backend as get_backend
from brainir.discovery.tournament import run_tournament, select_instances

ROOT = Path(__file__).resolve().parents[1]


def _key(r: dict) -> tuple:
    return (r["method"], r["instance"], r["network"], r["seed"])


def _paired(base: list[dict], pert: list[dict], method: str, rng) -> dict:
    b = {_key(r): r["structure"]["success"] for r in base if "structure" in r and r["method"] == method}
    p = {_key(r): r["structure"]["success"] for r in pert if "structure" in r and r["method"] == method}
    keys = sorted(set(b) & set(p))
    if not keys:
        return {"n_pairs": 0}
    d = np.array([float(p[k]) - float(b[k]) for k in keys])
    boot = [rng.choice(d, len(d)).mean() for _ in range(2000)]
    return {"n_pairs": len(keys), "success_base": float(np.mean([b[k] for k in keys])), "success_perturbed": float(np.mean([p[k] for k in keys])),
            "diff_mean": float(d.mean()), "diff_ci95": [float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))],
            "n_lost": int((d < 0).sum()), "n_gained": int((d > 0).sum())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", required=True)
    ap.add_argument("--transforms", nargs="+", default=list(TRANSFORMS), choices=list(TRANSFORMS))
    ap.add_argument("--suite", type=Path, default=ROOT / "data" / "synthetic" / "mechanisms_v1")
    ap.add_argument("--max-n", type=int, default=100)
    ap.add_argument("--networks", nargs="+", default=["main"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("--config", nargs="*", default=[])
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "tournament")
    args = ap.parse_args(argv)
    configs = {}
    for c in args.config:
        m, _, js = c.partition("=")
        configs[m] = json.loads(js)
    names = select_instances(args.suite, max_n=args.max_n)
    backend = get_backend("modal", cpu=1.0, memory_mb=3072, timeout_s=7200, max_containers=args.containers) if args.backend == "modal" else None
    registry = ROOT / "benchmarks" / "dng100" / "manifests" / "experiments"
    common = {"instances": names, "networks": tuple(args.networks), "seeds": tuple(args.seeds), "budget": args.budget, "configs": configs,
              "backend": backend, "workers": args.workers, "robust": False, "out_dir": args.out, "registry_dir": registry}
    base = run_tournament(args.methods, args.suite, label=f"{args.label}_baseline", **common)
    rng = np.random.default_rng(0)
    summary: dict = {"label": args.label, "instances": names, "methods": args.methods, "budget": args.budget, "seeds": args.seeds,
                     "baseline": {m: base["summary"].get(m, {}).get("success_rate") for m in args.methods}, "transforms": {}}
    for t in args.transforms:
        proot = paths.cache_dir() / "anti_gaming" / args.label / t
        perturb_suite(args.suite, proot, t, instances=names, seed=1000)
        res = run_tournament(args.methods, proot, label=f"{args.label}_{t}", **common)
        summary["transforms"][t] = {m: _paired(base["records"], res["records"], m, rng) for m in args.methods}
    (args.out / f"{args.label}_summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    lines = [f"# Anti-gaming checks — {args.label}", "", f"{len(names)} instances x networks {args.networks} x seeds {args.seeds}; budget "
             f"{args.budget}", "", "| transform | method | pairs | success base -> perturbed | paired diff [95% CI] | lost / gained |",
             "|---|---|---|---|---|---|"]
    for t, per in summary["transforms"].items():
        for m, s in per.items():
            if s.get("n_pairs"):
                lines.append(f"| {t} | {m} | {s['n_pairs']} | {s['success_base']:.2f} -> {s['success_perturbed']:.2f} | {s['diff_mean']:+.2f} "
                             f"[{s['diff_ci95'][0]:+.2f}, {s['diff_ci95'][1]:+.2f}] | {s['n_lost']} / {s['n_gained']} |")
    (args.out / f"{args.label}_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
