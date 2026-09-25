"""Developer-facing tournament feedback (PROTOCOL.md section 9): aggregate profiles only, never per-system values.

    uv run --project phase3 python scripts/p3/feedback.py --rounds r1[,r2,...] --out <file.md>

Reads research/phase3/tournament/<round>/AGGREGATE_developer_facing.json and writes a markdown table per round: for every candidate
the profile S1-S8, the eligibility, the verdict counts over the compressible held-out systems and the mean rank. The file is copied
into the clean room as docs/TOURNAMENT_FEEDBACK.md.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KEYS = ("S1_A_over_full", "S2_C_heldout", "S3_D_micro_gain", "S4_E_ratio", "S5_K_r2_rff", "S6_dim_rate", "S7_abstention", "S8_sharing_correct")
EXPLAIN = {
    "S1_A_over_full": "median multi-step prediction error relative to the full-state ceiling (lower is better; 1 = ceiling)",
    "S2_C_heldout": "median effect error on held-out intervention types / targets (lower is better; 1 = predicting no effect)",
    "S3_D_micro_gain": "median closure gain from discarded microstate (lower is better; ~0 = closed)",
    "S4_E_ratio": "median microstate-equivalence ratio, latent-matched vs random pairs (lower is better)",
    "S5_K_r2_rff": "median recovery of the true latent from z (R^2; higher is better)",
    "S6_dim_rate": "fraction of compressible systems where the selected dimension equals the true one or lies in the reported range",
    "S7_abstention": "abstention quality: mean of recall on non-compressible controls and 1 - false-alarm rate (higher is better)",
    "S8_sharing_correct": "fraction of correct sharing verdicts (implementation groups supported, unrelated pairs rejected)",
}


def fmt(v) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "-"
    return f"{v:.3g}" if isinstance(v, float) else str(v)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    lines = ["# Tournament feedback (aggregate held-out profiles; PROTOCOL.md section 9)", "",
             "Every value is an aggregate over held-out synthetic systems you have never seen. Per-system results are not released.", ""]
    lines += [f"- **{k}**: {v}" for k, v in EXPLAIN.items()] + [""]
    for rnd in [r for r in args.rounds.split(",") if r]:
        agg = json.loads((ROOT / "research" / "phase3" / "tournament" / rnd / "AGGREGATE_developer_facing.json").read_text(encoding="utf-8"))
        lines += [f"## Round {rnd} ({agg.get('suite')})", "",
                  "| candidate | eligible | " + " | ".join(k.split("_")[0] for k in KEYS) + " | mean rank | verdicts (compressible systems) |",
                  "|---|---|" + "---|" * len(KEYS) + "---|---|"]
        ranks = agg.get("mean_rank", {})
        for m, prof in sorted(agg["profiles"].items(), key=lambda kv: ranks.get(kv[0], 99)):
            vc = agg.get("verdict_counts", {}).get(m, {})
            vtxt = ", ".join(f"{k}: {v}" for k, v in sorted(vc.items()))
            lines.append(f"| {m} | {agg.get('eligible', {}).get(m)} | " + " | ".join(fmt(prof.get(k)) for k in KEYS)
                         + f" | {fmt(ranks.get(m))} | {vtxt} |")
        lines.append("")
    Path(args.out).write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
