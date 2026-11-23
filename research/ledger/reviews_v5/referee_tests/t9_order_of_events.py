"""Referee test 9 (documentary): was DNit013's low match confidence fixed before the replication pattern was known?

The draft (R3) says DNit013 joins the replicated set 'on a match we rated low confidence before looking'. This script prints, with
line numbers, the passages of RUN5_PROMPT.md section 1, LOG.md L158-L160 and PREREG_v5.md Part Q that date the replication
pattern and the match-confidence rule, and the draft's sentence. Also prints the K calibration (gates_v2/CALIBK.json) and the
DNg100 / DNit013 scores in B2 (K = 0, pre-registered first) and B2r (K = 1, chosen on DNg100).
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t9_order_of_events.py
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def show(rel, needles, width=420):
    lines = (ROOT / rel).read_text().splitlines()
    for i, l in enumerate(lines, 1):
        if any(n in l for n in needles):
            print(f"{rel}:{i}: {l[:width]}")


def main():
    print("== Draft sentence")
    show("paper/PREPRINT_v0.md", ["before looking"])
    print("== RUN5_PROMPT section 1 (the prompt that started run 5)")
    show("RUN5_PROMPT.md", ["In both flies: 3 types", "MaleCNS, our run (B2r)"])
    print("== LOG (order of rows: L158 question round, L160 match-confidence rule)")
    show("LOG.md", ["| L158 |", "| L160 |"], width=900)
    print("== PREREG v5 Part Q")
    show("PREREG_v5.md", ["The replication pattern (RUN5_PROMPT", "While building the per-type tables"], width=600)
    print("== K calibration on DNg100 (PREREG v2 P1)")
    k = json.loads((ROOT / "gates_v2/CALIBK.json").read_text())
    print({kk: v for kk, v in k["table"].items() if kk.startswith("MaleCNS")}, "k_chosen", k["k_chosen"])
    b2 = pd.read_csv(ROOT / "predictions/B2/types.csv").set_index("manc_type")["primary_score"]
    b2r = pd.read_csv(ROOT / "predictions_v2/B2r/types.csv").set_index("manc_type")["primary_score"]
    for t in ("DNg100", "DNb08", "DNit013"):
        print(f"{t}: B2 (K=0) {b2.get(t):.3f}  B2r (K=1) {b2r.get(t):.3f}")


if __name__ == "__main__":
    main()
