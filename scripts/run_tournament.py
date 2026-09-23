"""Run the synthetic method tournament (goal3 sections 6, 22).

    uv run python scripts/run_tournament.py --methods greedy_reference --budget 1000 --seeds 0 1 2 --networks main order1 \
        [--instances NAME ...] [--max-n 100] [--backend local|modal] [--workers 8] [--label smoke]

Results: research/phase2/tournament/<label>.{json,md} (+ registry record). Truth is read only by the scorer; the methods see the
public instance directories. The scorer's functional checks use fresh seeds on the true simulator.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from brainir.compute import get_backend
from brainir.discovery.tournament import run_tournament, select_instances

ROOT = Path(__file__).resolve().parents[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", required=True)
    ap.add_argument("--suite", type=Path, default=ROOT / "data" / "synthetic" / "mechanisms_v1")
    ap.add_argument("--instances", nargs="*", default=None)
    ap.add_argument("--max-n", type=int, default=None, help="only instances with at most this many neurons (from the truth spec)")
    ap.add_argument("--min-n", type=int, default=None, help="only instances with at least this many neurons")
    ap.add_argument("--families", nargs="*", default=None)
    ap.add_argument("--networks", nargs="+", default=["main"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--budget", type=int, default=1000)
    ap.add_argument("--config", nargs="*", default=[], help="method=json overrides, e.g. greedy_reference={\"k\":3}")
    ap.add_argument("--backend", choices=["local", "modal"], default="local")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--containers", type=int, default=100)
    ap.add_argument("--timeout", type=int, default=7200, help="Modal per-run timeout (s)")
    ap.add_argument("--memory-mb", type=int, default=3072)
    ap.add_argument("--no-robust", action="store_true", help="skip the robust/weight-noise/minimality functional checks (faster)")
    ap.add_argument("--label", default="tournament")
    ap.add_argument("--out", type=Path, default=ROOT / "research" / "phase2" / "tournament")
    args = ap.parse_args(argv)
    configs = {}
    for c in args.config:
        m, _, js = c.partition("=")
        configs[m] = json.loads(js)
    inst = args.instances
    if inst is None and (args.max_n or args.min_n or args.families):
        inst = select_instances(args.suite, max_n=args.max_n, min_n=args.min_n, families=args.families)
    backend = (get_backend("modal", cpu=1.0, memory_mb=args.memory_mb, timeout_s=args.timeout, max_containers=args.containers)
               if args.backend == "modal" else None)
    run_tournament(args.methods, args.suite, instances=inst, networks=tuple(args.networks), seeds=tuple(args.seeds), budget=args.budget,
                   configs=configs, backend=backend, workers=args.workers, robust=not args.no_robust, out_dir=args.out,
                   registry_dir=ROOT / "benchmarks" / "dng100" / "manifests" / "experiments", label=args.label)
    print((args.out / f"{args.label}.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
