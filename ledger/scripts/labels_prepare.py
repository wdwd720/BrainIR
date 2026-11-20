"""Prepare pass-2 and adjudication inputs from collected label records (LABEL SIDE: never reads predictions).

    uv run --project ledger --no-sync python ledger/scripts/labels_prepare.py pass2          # -> labels/work/pass2_inputs/<family>/
    uv run --project ledger --no-sync python ledger/scripts/labels_prepare.py adjudication   # -> labels/work/adjudication_inputs/<group>/

pass2: pass-1 records are de-duplicated across sessions (`aggregate.dedupe_pass1`, logged), then for each family
`experiments_to_label.csv` holds IDENTIFIERS ONLY (exp_id, doi, source_locator, driver_lines, name_in_paper, preparation,
effector, stimulation: no label field, no MANC type, no quote) and `quotes_to_verify.csv` (exp_id, doi, source_locator,
quote) is kept aside for Phase B, which starts only after Phase A is saved.
adjudication: `disagreements.csv`, one row per disputed field, readings A/B in a seeded random order (seed 20261125); the
experiments of the dedicated family go to their own group (only its session may open those sources).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "ledger" / "src"))
from brainir_ledger.labels.aggregate import COMPARED_FIELDS, dedupe_pass1  # noqa: E402

LAB = REPO / "research" / "ledger" / "labels"
RAW = LAB / "raw"
WORK = LAB / "work"
DEDICATED = "pugliese_dedicated"
ID_FIELDS = ["exp_id", "doi", "source_locator", "driver_lines", "name_in_paper", "preparation", "effector", "stimulation",
             "sibling_index", "n_siblings"]
AUDIT = LAB / "transcript_audit.json"
BREACH_KINDS = ("file_outside_room", "banned_host_fetch", "dedicated_source_outside_dedicated_session", "no_transcript")


def breaching_sessions() -> set[str]:
    """Sessions whose transcript audit shows a breach. The audit must exist and cover every pass-1 session."""
    if not AUDIT.exists():
        raise SystemExit("run ledger/scripts/labels_audit.py first: pass-2 inputs are built only from audited pass-1 sessions")
    rows = json.loads(AUDIT.read_text(encoding="utf-8"))
    audited = {r["session"] for r in rows}
    missing = [sd.name for sd in (RAW / "pass1").glob("pass1-*") if sd.name not in audited]
    if missing:
        raise SystemExit(f"transcript audit does not cover {missing}")
    return {r["session"] for r in rows if any(i["kind"] in BREACH_KINDS for i in r["issues"])}


def add_siblings(rows: list[dict], p1_type: dict[str, str]) -> list[dict]:
    """Rows with identical identifiers (a line that labels several DN types, recorded once per type) get sibling_index k of
    n_siblings, in alphabetical order of the pass-1 MANC type; pass 2 assigns the types it finds in the same order."""
    groups: dict[tuple, list[dict]] = {}
    for r in rows:
        key = tuple(str(r[k]).strip().lower() for k in ("doi", "source_locator", "driver_lines", "name_in_paper", "preparation", "effector",
                                                        "stimulation"))
        groups.setdefault(key, []).append(r)
    for g in groups.values():
        g.sort(key=lambda r: (p1_type[r["exp_id"]].lower(), r["exp_id"]))
        for k, r in enumerate(g, start=1):
            r["sibling_index"], r["n_siblings"] = k, len(g)
    return rows


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def pass1_records() -> list[dict]:
    recs = []
    for sd in sorted((RAW / "pass1").glob("pass1-*")):
        recs += read_jsonl(sd / "records.valid.jsonl")
    return recs


def family_of(exp_id: str) -> str:
    return exp_id.split(":", 1)[0].removeprefix("pass1-")


def _write(path: Path, rows: list[dict], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def pass2_inputs() -> None:
    breach = breaching_sessions()
    recs = [r for r in pass1_records() if r["exp_id"].split(":", 1)[0] not in breach]
    kept, dropped = dedupe_pass1(recs)
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "pass1_dedupe_log.json").write_text(json.dumps({"n_kept": len(kept), "dropped": dropped, "excluded_breaching_sessions": sorted(breach)},
                                                           indent=1) + "\n", encoding="utf-8")
    by: dict[str, list[dict]] = {}
    for r in kept:
        by.setdefault(family_of(r["exp_id"]), []).append(r)
    for fam, recs in sorted(by.items()):
        rows = [{"exp_id": r["exp_id"], "doi": r["doi"], "source_locator": r["source_locator"], "driver_lines": ";".join(r.get("driver_lines") or []),
                 "name_in_paper": r["name_in_paper"], "preparation": r["preparation"], "effector": r["effector"], "stimulation": r["stimulation"]}
                for r in recs]
        rows = add_siblings(rows, {r["exp_id"]: r["manc_type"] for r in recs})
        quotes = [{"exp_id": r["exp_id"], "doi": r["doi"], "source_locator": r["source_locator"], "quote": r["quote"]} for r in recs]
        out = WORK / "pass2_inputs" / fam
        _write(out / "experiments_to_label.csv", rows, ID_FIELDS)
        _write(out / "quotes_to_verify.csv", quotes, ["exp_id", "doi", "source_locator", "quote"])
        print(fam, len(rows), "experiments")
    print("dropped as cross-session duplicates:", len(dropped))


def adjudication_inputs() -> None:
    rng = np.random.default_rng(20261125)
    breach = breaching_sessions()
    kept, _ = dedupe_pass1([r for r in pass1_records() if r["exp_id"].split(":", 1)[0] not in breach])
    sib = {}
    for fam_dir in sorted((WORK / "pass2_inputs").glob("*")):
        f = fam_dir / "experiments_to_label.csv"
        if f.exists():
            for row in csv.DictReader(open(f, encoding="utf-8")):
                sib[row["exp_id"]] = row
    p2 = {}
    for sd in sorted((RAW / "pass2").glob("pass2-*")):
        for r in read_jsonl(sd / "records.valid.jsonl"):
            p2.setdefault(r["exp_id"], r)
    groups: dict[str, list[dict]] = {}
    for a in kept:
        b = p2.get(a["exp_id"])
        if b is None:
            continue
        g = "dedicated" if family_of(a["exp_id"]) == DEDICATED else "general"
        for f in COMPARED_FIELDS:
            if a.get(f) != b.get(f):
                ra, rb = (a.get(f), b.get(f)) if rng.random() < 0.5 else (b.get(f), a.get(f))
                s = sib.get(a["exp_id"], {})
                groups.setdefault(g, []).append({"exp_id": a["exp_id"], "doi": a["doi"], "source_locator": a["source_locator"],
                                                 "driver_lines": ";".join(a.get("driver_lines") or []), "name_in_paper": a["name_in_paper"],
                                                 "preparation": a["preparation"], "effector": a["effector"], "stimulation": a["stimulation"],
                                                 "sibling_index": s.get("sibling_index", 1), "n_siblings": s.get("n_siblings", 1),
                                                 "field": f, "reading_A": json.dumps(ra), "reading_B": json.dumps(rb)})
    for g, rows in sorted(groups.items()):
        _write(WORK / "adjudication_inputs" / g / "disagreements.csv", rows, ID_FIELDS + ["field", "reading_A", "reading_B"])
        print(g, len(rows), "disputed fields in", len({r["exp_id"] for r in rows}), "experiments")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["pass2", "adjudication"])
    a = ap.parse_args()
    pass2_inputs() if a.what == "pass2" else adjudication_inputs()


if __name__ == "__main__":
    main()
