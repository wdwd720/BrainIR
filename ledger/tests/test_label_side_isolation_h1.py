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
# the two exam 2 prediction lock files may be named (the gate verifies locks and their commit times; it never opens a prediction table)
FORBIDDEN = re.compile(r"predictions(_h1|_v2)?[/\\\"']|LOCK_predictions(?!_h1b?\.json)|predicted\.csv|data/ledger/arms|scoring_h1|score_h1|groups_h1|"
                       r"predict_h1|\bgha3|jobs_v3|typescreen_v3|arms_h1|results\.pkl", re.I)
# the reverse direction: prediction-side code never names a label location (the scoring code reads labels by design, after the flag)
PREDICTION_SIDE = ["ledger/src/brainir_ledger/groups_h1.py", "ledger/scripts/predict_h1.py", "ledger/scripts/gha3.py", "ledger/scripts/gha3r.py",
                   "ledger/src/brainir_ledger/jobs_v3.py", "ledger/src/brainir_ledger/typescreen_v3.py", "ledger/scripts/gha_runner3.py",
                   "ledger/scripts/hl_units_v3.py", "ledger/scripts/motor_map_v3.py", "ledger/scripts/diag_v3_linear.py"]
LABEL_WORDS = re.compile(r"(?<!LOCK_)labels_h1|kit_v3|sources_h1|consensus", re.I)  # the labels lock file may be tested for existence
# lines that name a prediction location in order to deny it (deny rules, planted canary files), never to read it
ALLOWED = {("ledger/scripts/labels2_canary.py", '"planted_fake_predictions": str(BASE / "planted" / "predictions_FAKE.csv"),'),
           ("ledger/scripts/labels3_canary.py", '"planted_fake_predictions": str(BASE / "planted" / "predictions_FAKE.csv"),'),
}


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


def test_prediction_side_code_never_names_labels():
    hits = []
    for rel in PREDICTION_SIDE:
        p = REPO / rel
        assert p.is_file(), rel
        for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
            if LABEL_WORDS.search(line):
                hits.append(f"{rel}:{i}: {line.strip()[:120]}")
    assert not hits, "prediction-side code names a label location:\n" + "\n".join(hits)
