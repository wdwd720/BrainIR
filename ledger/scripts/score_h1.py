"""Exam 2 scoring runs (PREREG v3 S6): `primary`, then `secondary`, each once; refuses without `UNBLIND_h1.json`, a passing
gate (second run) and matching locks.

    uv run --project ledger --no-sync python ledger/scripts/score_h1.py --run primary
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.scoring_h1 import BlindErrorH1  # noqa: E402
from brainir_ledger.scoring_h1.pipeline_h1 import RUNS, run  # noqa: E402


def main(argv=None, research: Path = RESEARCH) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, choices=RUNS)
    a = ap.parse_args(argv)
    try:
        res = run(a.run, research, research / "UNBLIND_h1.json")
    except BlindErrorH1 as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    if a.run == "primary":
        print(json.dumps({"n": res["H-M"]["n"], "mean_pr": res["H-M"]["mean_pr"], "p": res["p"], "ci": res["ci"], "decision": res["decision"]}))
    else:
        print("secondary analyses:", ", ".join(sorted(res["secondary"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
