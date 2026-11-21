"""Exam 2: label-side code must never read a prediction file (RUN3_PROMPT section 5, "Scoring code"). A static scan of every
label-side file (run 3's label scripts, gate script, label package and kit, and run 2's label code that run 3 reuses) for any
reference to a prediction location; the only exceptions are listed lines that deny such a location. Binds every file written
later that matches the globs."""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# run 3's label code (exam 2) and run 2's label code that run 3 reuses (rooms, downloader, collector, audit, canary, aggregation)
LABEL_SIDE = ["ledger/scripts/labels3_*.py", "ledger/scripts/gate_h1.py", "ledger/src/brainir_ledger/labels_h1/**/*.py",
              "research/ledger/kit_v3/*", "ledger/scripts/labels2_*.py", "ledger/scripts/labels_*.py",
              "ledger/src/brainir_ledger/labels/*.py"]
FORBIDDEN = re.compile(r"predictions(_h1|_v2)?[/\\\"']|LOCK_predictions|predicted\.csv|data/ledger/arms|scoring_h1|score_h1", re.I)
# lines that name a prediction location in order to deny it (deny rules, planted canary files), never to read it
ALLOWED = {("ledger/scripts/labels2_canary.py", '"planted_fake_predictions": str(BASE / "planted" / "predictions_FAKE.csv"),')}


def label_side_files() -> list[Path]:
    out = []
    for g in LABEL_SIDE:
        out += [p for p in REPO.glob(g) if p.is_file()]
    return sorted(set(out))


def test_label_side_code_never_reads_predictions():
    hits = []
    for p in label_side_files():
        for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if FORBIDDEN.search(line) and (str(p.relative_to(REPO)), line.strip()) not in ALLOWED:
                hits.append(f"{p.relative_to(REPO)}:{i}: {line.strip()[:120]}")
    assert not hits, "label-side code references prediction files:\n" + "\n".join(hits)


def test_the_scan_catches_a_planted_reference(tmp_path):
    planted = 'df = pd.read_csv("research/ledger/predictions_h1/H-M/predicted.csv")'
    assert FORBIDDEN.search(planted)


def test_allow_list_is_current_and_scan_is_not_empty():
    files = {str(p.relative_to(REPO)) for p in label_side_files()}
    assert "ledger/scripts/labels2_rooms.py" in files and "ledger/scripts/labels2_collect.py" in files
    for f, line in ALLOWED:
        assert line in [x.strip() for x in (REPO / f).read_text().splitlines()], f"stale allow-list entry in {f}"
