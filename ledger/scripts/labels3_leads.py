"""Search leads -> registry of new sources (LABEL SIDE; PREREG v3 T6). By script, so the orchestrator never reads titles to decide.

A lead from a non-breaching search session qualifies when it has a DOI, `adult_activation` is `yes` and `whole_hemilineage` is `yes`
or `unclear` (whether a record is whole-hemilineage is decided by the two readers, T2), and the DOI is neither a known source
(`known_sources.csv`) nor a banned simulation source (run 2's audit tokens) nor a code host. Leads are de-duplicated by
normalised DOI. Output: `labels_h1/registry_search.csv` (doi, n_sessions_naming_it) and `labels_h1/leads_summary.json` (counts
only). Prints counts only.

    uv run --project ledger --no-sync python ledger/scripts/labels3_leads.py
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import labels3_rooms as R3  # noqa: E402

LAB = R3.REPO / "research" / "ledger" / "labels_h1"
BANNED_PREFIXES = ("10.5281/",)  # Zenodo


def norm_doi(d: str) -> str | None:
    s = (d or "").strip().lower()
    s = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", s)
    s = s.removeprefix("doi:").strip()
    return s if re.fullmatch(r"10\.\d{4,9}/\S+", s) else None


def qualifies(row: dict) -> bool:
    return (str(row.get("adult_activation", "")).strip().lower() == "yes"
            and str(row.get("whole_hemilineage", "")).strip().lower() in ("yes", "unclear"))


def main() -> None:
    plan = json.loads((LAB / "plan.json").read_text())
    audit = {r["session"]: r for r in json.loads((LAB / "transcript_audit.json").read_text())}
    known = {norm_doi(r["doi"]) for r in csv.DictReader(open(LAB / "known_sources.csv", encoding="utf-8"))}
    seen: dict[str, set] = {}
    counts = {"rows": 0, "no_doi": 0, "not_qualifying": 0, "known": 0, "banned": 0, "breached_session_rows": 0}
    for s in plan.get("search", []):
        p = LAB / "raw" / "search" / s / "leads.csv"
        if not p.is_file():
            continue
        rows = list(csv.DictReader(open(p, encoding="utf-8", errors="replace")))
        if audit.get(s, {"breach": True})["breach"]:
            counts["breached_session_rows"] += len(rows)
            continue
        for r in rows:
            counts["rows"] += 1
            d = norm_doi(r.get("doi", ""))
            if not d:
                counts["no_doi"] += 1
            elif not qualifies(r):
                counts["not_qualifying"] += 1
            elif d in known:
                counts["known"] += 1
            elif d.startswith(BANNED_PREFIXES) or R3.R2.is_dedicated(d):
                counts["banned"] += 1
            else:
                seen.setdefault(d, set()).add(s)
    with open(LAB / "registry_search.csv", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("doi,n_sessions_naming_it\n")
        for d in sorted(seen):
            fh.write(f"{d},{len(seen[d])}\n")
    out = {**counts, "qualifying_dois": len(seen)}
    (LAB / "leads_summary.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out))


if __name__ == "__main__":
    main()
