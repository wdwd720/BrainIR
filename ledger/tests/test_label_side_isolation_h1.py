"""Exam 2: label-side code must never read a prediction file (RUN3_PROMPT section 5, "Scoring code"). A static scan of every
label-side file of run 3 (the h1 label scripts, the gate script, the label package and the kit) for any reference to a prediction
location. Passes trivially while no label-side file exists; binds every one written later."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LABEL_SIDE = ["ledger/scripts/labels3_*.py", "ledger/scripts/gate_h1.py", "ledger/src/brainir_ledger/labels_h1/**/*.py",
              "research/ledger/kit_v3/*"]
FORBIDDEN = re.compile(r"predictions(_h1|_v2)?[/\\\"']|LOCK_predictions|predicted\.csv|data/ledger/arms|scoring_h1|score_h1", re.I)


def label_side_files() -> list[Path]:
    out = []
    for g in LABEL_SIDE:
        out += [p for p in REPO.glob(g) if p.is_file()]
    return sorted(set(out))


def test_label_side_code_never_reads_predictions():
    hits = []
    for p in label_side_files():
        for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if FORBIDDEN.search(line):
                hits.append(f"{p.relative_to(REPO)}:{i}: {line.strip()[:120]}")
    assert not hits, "label-side code references prediction files:\n" + "\n".join(hits)


def test_the_scan_catches_a_planted_reference(tmp_path):
    planted = 'df = pd.read_csv("research/ledger/predictions_h1/H-M/predicted.csv")'
    assert FORBIDDEN.search(planted)
