"""Prepare pass-2 and adjudication inputs from collected label records (LABEL SIDE: never reads predictions).

    uv run --project ledger --no-sync python ledger/scripts/labels_prepare.py pass2          # -> labels/work/pass2_inputs/<family>/
    uv run --project ledger --no-sync python ledger/scripts/labels_prepare.py adjudication   # -> labels/work/adjudication_inputs/

pass2: for each pass-1 family, `experiments_to_label.csv` (identifiers only: experiment_key, doi, source_locator, driver_lines,
name_in_paper, manc_type; NO label fields, NO quote) and `quotes_to_verify.csv` (experiment_key, doi, source_locator, quote).
adjudication: `disagreements.csv`, one row per disputed field, readings A/B in a seeded random order (seed 20261125).
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
import sys  # noqa: E402

sys.path.insert(0, str(REPO / "ledger" / "src"))
from brainir_ledger.labels.aggregate import COMPARED_FIELDS  # noqa: E402
from brainir_ledger.labels.schema import experiment_key  # noqa: E402

LAB = REPO / "research" / "ledger" / "labels"
RAW = LAB / "raw"
WORK = LAB / "work"


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def valid_records(session_dir: Path) -> list[dict]:
    """Records that passed validation at collection time (labels_collect.py writes records.valid.jsonl)."""
    return read_jsonl(session_dir / "records.valid.jsonl")


def pass2_inputs() -> None:
    seen = set()
    for sd in sorted((RAW / "pass1").glob("pass1-*")):
        fam = sd.name.removeprefix("pass1-")
        out = WORK / "pass2_inputs" / fam
        out.mkdir(parents=True, exist_ok=True)
        rows, quotes = [], []
        for r in valid_records(sd):
            k = experiment_key(r)
            if k in seen:      # the same experiment found by two pass-1 families is labelled once
                continue
            seen.add(k)
            rows.append({"experiment_key": k, "doi": r["doi"], "source_locator": r["source_locator"],
                         "driver_lines": ";".join(r.get("driver_lines") or []), "name_in_paper": r["name_in_paper"],
                         "manc_type": r["manc_type"]})
            quotes.append({"experiment_key": k, "doi": r["doi"], "source_locator": r["source_locator"], "quote": r["quote"]})
        for name, data in (("experiments_to_label.csv", rows), ("quotes_to_verify.csv", quotes)):
            with open(out / name, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=list(data[0].keys()) if data else ["experiment_key"])
                w.writeheader()
                w.writerows(data)
        print(fam, len(rows), "experiments")


def adjudication_inputs() -> None:
    rng = np.random.default_rng(20261125)
    p1 = {}
    for sd in sorted((RAW / "pass1").glob("pass1-*")):
        for r in valid_records(sd):
            p1.setdefault(experiment_key(r), r)
    p2 = {}
    for sd in sorted((RAW / "pass2").glob("pass2-*")):
        for r in valid_records(sd):
            p2.setdefault(r.get("experiment_key") or experiment_key(r), r)
    rows = []
    for k, a in p1.items():
        b = p2.get(k)
        if b is None:
            continue
        for f in COMPARED_FIELDS:
            if a.get(f) != b.get(f):
                ra, rb = (a.get(f), b.get(f)) if rng.random() < 0.5 else (b.get(f), a.get(f))
                rows.append({"experiment_key": k, "doi": a["doi"], "source_locator": a["source_locator"],
                             "driver_lines": ";".join(a.get("driver_lines") or []), "name_in_paper": a["name_in_paper"],
                             "manc_type": a["manc_type"], "field": f, "reading_A": ra, "reading_B": rb})
    out = WORK / "adjudication_inputs"
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "disagreements.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["experiment_key", "doi", "source_locator", "driver_lines", "name_in_paper", "manc_type", "field",
                                           "reading_A", "reading_B"])
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "disputed fields in", len({r["experiment_key"] for r in rows}), "experiments")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["pass2", "adjudication"])
    a = ap.parse_args()
    pass2_inputs() if a.what == "pass2" else adjudication_inputs()


if __name__ == "__main__":
    main()
