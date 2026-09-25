"""Merge per-developer tournament runs of one Level B round into one ranked aggregate (orchestrator; PROTOCOL.md section 9).

    uv run --project phase3 python scripts/p3/merge_rounds.py --parts r1_lin,r1_ks,... --out r1

Each part is a tournament.py run with the same suite and design on a subset of the candidates, so candidates can be scored as their
developers finish. The merge re-ranks all eligible candidates with the rule of tournament.py (mean rank over S1-S8; lower is better
for S1-S4, higher for S5-S8; non-finite values rank last) and writes research/phase3/tournament/<out>/AGGREGATE_developer_facing.json
plus links to the parts' per-candidate files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
T = ROOT / "research" / "phase3" / "tournament"
KEYS = ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff", "S6_dim_rate", "S7_abstention", "S8_sharing_correct")
LOW = {"S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio"}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    profiles, verdicts, eligible, files, suites = {}, {}, {}, {}, set()
    for part in [p for p in args.parts.split(",") if p]:
        agg = json.loads((T / part / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8"))
        suites.add(agg.get("suite"))
        for m, prof in agg["profiles"].items():
            if m in profiles:
                raise SystemExit(f"candidate {m} appears in two parts")
            profiles[m], verdicts[m], eligible[m] = prof, agg["verdict_counts"].get(m, {}), agg["eligible"].get(m)
            files[m] = f"research/phase3/tournament/{part}/{m}.json"
    if len(suites) != 1:
        raise SystemExit(f"parts come from different suites: {suites}")
    elig = [m for m in profiles if eligible[m]]
    ranks = {m: [] for m in elig}
    for key in KEYS:
        vals = {m: profiles[m].get(key, float("nan")) for m in elig}
        order = sorted(elig, key=lambda m: (np.inf if not np.isfinite(vals[m]) else (vals[m] if key in LOW else -vals[m])))
        for r, m in enumerate(order):
            ranks[m].append(r + 1)
    out = {"round": args.out, "suite": suites.pop(), "parts": args.parts.split(","), "profiles": profiles, "verdict_counts": verdicts,
           "eligible": eligible, "mean_rank": {m: float(np.mean(v)) for m, v in ranks.items()}, "per_candidate_files": files}
    (T / args.out).mkdir(parents=True, exist_ok=True)
    (T / args.out / "AGGREGATE_developer_facing.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    for m, r in sorted(out["mean_rank"].items(), key=lambda kv: kv[1]):
        print(f"{r:5.2f}  {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
