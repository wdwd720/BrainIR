"""Publish developer-facing tournament feedback into the clean room (orchestrator; PROTOCOL.md section 9).

    uv run --project phase3 --no-sync python scripts/p3/publish_feedback.py --rounds r1[,r2] [--room C:\\Dev\\BrainIR_p3clean]

Runs the frozen scripts/p3/feedback.py (aggregate profiles, eligibility, mean ranks, verdict counts; never per-system values), brings
two explanations to benchmark version 2 wording (S8 is a balanced accuracy; S1-S5 use a fixed system list with failures as the
worst value, S4 leaves out untestable E), and adds the file through scripts/p3/room_addendum.py (content scan, audited record) as
notes/_tournament_feedback.md.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "research" / "phase3" / "review_contracts" / "tournament_feedback_published.md"

V2_NOTE = ("- Profiles (benchmark version 2): S1-S6 are taken over the same fixed list of compressible held-out systems for every "
           "candidate; a failed fit or evaluation counts as the worst value. S4 leaves out systems where the candidate's E is untestable. "
           "Ranks average ties and do not depend on the order of the candidates; a component that is missing for every candidate (S8 in "
           "the pilot, which has no shared fits) is left out.")
S8_OLD = "- **S8_sharing_correct**: fraction of correct sharing verdicts (implementation groups supported, unrelated pairs rejected)"
S8_NEW = ("- **S8_sharing_correct**: balanced accuracy of the sharing verdicts: mean of the correct rates over the implementation groups "
          "(supported) and over the unrelated pairs (rejected)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", required=True)
    ap.add_argument("--room", default=r"C:\Dev\BrainIR_p3clean")
    args = ap.parse_args(argv)
    py = sys.executable
    subprocess.run([py, str(ROOT / "scripts" / "p3" / "feedback.py"), "--rounds", args.rounds, "--out", str(OUT)], check=True)
    text = OUT.read_text(encoding="utf-8")
    if S8_OLD not in text:
        raise SystemExit("unexpected feedback format (S8 line)")
    text = text.replace(S8_OLD, S8_NEW + "\n" + V2_NOTE)
    OUT.write_text(text, encoding="utf-8", newline="\n")
    subprocess.run([py, str(ROOT / "scripts" / "p3" / "room_addendum.py"), "--src", str(OUT), "--dest", "notes/_tournament_feedback.md",
                    "--reason", f"aggregate held-out tournament feedback, rounds {args.rounds} (profiles, ranks, verdict counts only)",
                    "--leakage-class", "aggregate-feedback", "--room", args.room], check=True)
    print(f"published rounds {args.rounds} to {args.room}/notes/_tournament_feedback.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
