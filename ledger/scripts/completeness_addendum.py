"""Addendum to the locked labels v1 (LOG L46; label review round 1, finding 2): the completeness statistic recomputed with the two
defects the reviewer found, WITHOUT changing any locked file or frozen code.

The frozen `labels_collect.norm_doi` strips the article number from unversioned eLife DOIs (it meant to strip only a version
suffix), so all eLife papers become one unit; and the breaching search session (search-search_names) is kept in the estimate
(PREREG 6 names only pass-1, pass-2 and adjudication sessions). This script reuses the frozen inputs and rules (`_read`,
`breaching_sessions`, `dedupe_pass1`, the Chapman formula, the dedicated-family exclusion) and varies only those two points.
Label side only: it reads collected label records, never a prediction, and prints counts only.

    uv run --project ledger --no-sync python ledger/scripts/completeness_addendum.py   # -> research/ledger/final/COMPLETENESS_ADDENDUM.json
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labels_collect as LC  # noqa: E402  (frozen module, used read-only)
from brainir_ledger.labels import aggregate as AGG  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "research" / "ledger" / "final" / "COMPLETENESS_ADDENDUM.json"


def norm_doi_fixed(d: str) -> str:
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://(dx\.)?doi\.org/", "", d)
    return re.sub(r"^(10\.7554/elife\.\d+)\.\d+$", r"\1", d)  # strip an eLife version suffix only


def chapman(first: list[dict], second: list[dict], nd) -> dict:
    a = {(nd(r["doi"]), r["manc_type"]) for r in first if not r["exp_id"].startswith("pass1-pugliese_dedicated:")}
    b = {(nd(r["doi"]), r["manc_type"]) for r in second}
    m, n1, n2 = len(a & b), len(a), len(b)
    n = (n1 + 1) * (n2 + 1) / (m + 1) - 1
    return {"n_first": n1, "n_search": n2, "n_both": m, "estimated_total": round(n, 1), "pass1_found_fraction": round(n1 / n, 2),
            "n_units_found_only_by_search": len(b - a)}


def main() -> None:
    breach = LC.breaching_sessions()
    p1, _ = AGG.dedupe_pass1([r for r in LC._read("pass1") if r["exp_id"].split(":", 1)[0] not in breach])
    search_all = LC._read("search")
    search_clean = [r for r in search_all if r["exp_id"].split(":", 1)[0] not in breach]
    out = {"note": "addendum; the locked labels v1 and their agreement.md are unchanged (PREREG 12; prompt section 11)",
           "frozen_as_reported": chapman(p1, search_all, LC.norm_doi),
           "doi_fixed": chapman(p1, search_all, norm_doi_fixed),
           "doi_fixed_and_breaching_search_excluded": chapman(p1, search_clean, norm_doi_fixed),
           "frozen_doi_breaching_search_excluded": chapman(p1, search_clean, LC.norm_doi)}
    p1keys_fixed = {(norm_doi_fixed(r["doi"]), r["manc_type"]) for r in p1}
    p1keys_frozen = {(LC.norm_doi(r["doi"]), r["manc_type"]) for r in p1}
    out["search_only_records"] = {
        "frozen_as_reported": sum((LC.norm_doi(r["doi"]), r["manc_type"]) not in p1keys_frozen for r in search_all),
        "doi_fixed": sum((norm_doi_fixed(r["doi"]), r["manc_type"]) not in p1keys_fixed for r in search_all),
        "doi_fixed_and_breaching_search_excluded": sum((norm_doi_fixed(r["doi"]), r["manc_type"]) not in p1keys_fixed for r in search_clean)}
    OUT.write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
