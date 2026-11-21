"""Exam 2 label sensitivity input (EXPLORATORY; LABEL SIDE, reads no prediction). Built before the unblinding flag, so the labels
lock hashes it; used only by an exploratory re-score. The primary truth (`consensus.csv`) is unchanged.

1. De-duplication (label review, major 1): the within-reading de-duplication of `labels3_assemble.reading()` keeps the first record of a
   key (source, name as printed, normalised driver, preparation, effector class) and drops later ones. This script lists the dropped
   records, maps them to units (U5), and counts the primary cells where a dropped record codes yes/no differently from the kept twin.
2. `consensus_sensitivity.csv`: the frozen consensus with every cell the label review questions (`review_flags.csv`, written by the
   reviewer) and every cell where a dropped record's yes/no differs from its kept twin set to `conflicting`, i.e. removed from scoring.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/labels_sensitivity.py
    -> labels_h1/consensus_sensitivity.csv, labels_h1/sensitivity_report.json (counts and record ids; written once)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.labels_h1 import core as C  # noqa: E402

LAB = RESEARCH / "labels_h1"


def main() -> None:
    plan = json.loads((LAB / "plan.json").read_text())
    units = pd.read_csv(RESEARCH / "hl_units" / "UNITS_v1.csv", dtype={"unit": str})["unit"].tolist()
    audit = {r["session"]: r for r in json.loads((LAB / "transcript_audit.json").read_text())}
    dropped, diff_cells = [], set()
    for slug, readings in sorted(plan["readings"].items()):
        for which, sessions in sorted(readings.items()):
            kept: dict = {}
            for s in sessions:
                if audit.get(s, {}).get("breach"):
                    continue
                p = LAB / "raw" / "reading" / s / "records.jsonl"
                for line in p.read_text(encoding="utf-8").splitlines():
                    if not line.strip():
                        continue
                    r = json.loads(line)
                    if C.validate(r):
                        continue
                    k = (slug, r["hemilineage_as_named"].strip().lower(), C.driver_norm(r["driver"]), r["preparation"],
                         C.effector_class(r["effector"]))
                    if k not in kept:
                        kept[k] = r
                        continue
                    twin = kept[k]
                    a, b = {**r, "d7p": C.d7p(r)}, {**twin, "d7p": C.d7p(twin)}
                    unit = C.unit_of(r, units)[0]
                    diffs = [d for d in C.PRIMARY if a[d] in ("yes", "no") and a[d] != b[d]]
                    for d in diffs:
                        if unit:
                            diff_cells.add((unit, d))
                    dropped.append({"source": slug, "reading": which, "record_id": r["record_id"], "kept_twin": twin["record_id"],
                                    "unit": unit, "record_type": r["record_type"], "n_primary_yes_no_differing_from_twin": len(diffs)})
    cons = pd.read_csv(LAB / "consensus.csv", dtype=str, keep_default_na=False).set_index("unit")
    flags = pd.read_csv(LAB / "review_flags.csv", dtype=str, keep_default_na=False)
    flagged = {(u, d) for u, d in zip(flags["unit"], flags["dim"])}
    bad = sorted(c for c in flagged if c[0] not in cons.index or c[1] not in cons.columns)
    sens = cons.copy()
    changed = 0
    for u, d in sorted(flagged | diff_cells):
        if u in sens.index and d in sens.columns:
            if sens.loc[u, d] in ("yes", "no"):
                changed += 1
            sens.loc[u, d] = "conflicting"
    out_csv = LAB / "consensus_sensitivity.csv"
    if out_csv.exists():
        raise SystemExit("consensus_sensitivity.csv exists (written once)")
    sens.reset_index().to_csv(out_csv, index=False, lineterminator="\n")
    rep = {"dropped_records": dropped, "n_dropped": len(dropped), "dedup_cells_differing": sorted(f"{u}:{d}" for u, d in diff_cells),
           "n_review_flags": len(flagged), "review_flags_not_in_consensus": [f"{u}:{d}" for u, d in bad],
           "coded_cells_removed": changed, "n_units_ge3_primary": C.n_units_ge3(cons), "n_units_ge3_primary_sensitivity": C.n_units_ge3(sens)}
    with open(LAB / "sensitivity_report.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rep, indent=1) + "\n")
    print(json.dumps({k: v for k, v in rep.items() if k not in ("dropped_records", "dedup_cells_differing")}))


if __name__ == "__main__":
    main()
