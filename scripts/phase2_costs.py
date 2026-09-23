"""Total Phase 2 compute from the experiment registry (goal3 sections 19, 43): Modal cost estimates, wall time, runs, per experiment kind.

    uv run python scripts/phase2_costs.py [--since 2026-09-23T17:00:00Z]

Costs are the registry's upper-bound estimates (every item billed for wall/containers seconds at list price); runs deleted from the
registry (smoke tests, failed launches) are listed separately in research/LOG.md.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KINDS = (("sel_pairs", "pair tournament"), ("sel_curve", "budget curves"), ("sel_mech", "selection tournament"), ("ag_", "anti-gaming"),
         ("reliability_", "reliability sweeps"), ("transfer_", "transfer experiments"), ("conf_", "confirmation"), ("abl", "ablations"))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2026-09-23T17:00:00Z")
    args = ap.parse_args(argv)
    idx = ROOT / "benchmarks" / "dng100" / "manifests" / "experiments" / "index.jsonl"
    by = defaultdict(lambda: {"runs": 0, "cost": 0.0, "wall_s": 0.0})
    total = {"runs": 0, "cost": 0.0, "wall_s": 0.0}
    for line in idx.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["created_utc"] < args.since:
            continue
        kind = next((k for p, k in KINDS if r["name"].startswith(p)), "other")
        for agg in (by[kind], total):
            agg["runs"] += 1
            agg["cost"] += float(r.get("estimated_cost_usd") or 0.0)
            agg["wall_s"] += float(r.get("wall_time_s") or 0.0)
    print(f"Phase 2 registry since {args.since}:")
    for k, v in sorted(by.items(), key=lambda kv: -kv[1]["cost"]):
        print(f"  {k:22s} runs {v['runs']:3d}  est. cost ${v['cost']:7.2f}  wall {v['wall_s'] / 3600:6.2f} h")
    print(f"  {'TOTAL':22s} runs {total['runs']:3d}  est. cost ${total['cost']:7.2f}  wall {total['wall_s'] / 3600:6.2f} h")
    return 0


if __name__ == "__main__":
    sys.exit(main())
