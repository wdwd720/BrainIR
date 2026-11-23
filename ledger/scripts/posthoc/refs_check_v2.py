"""Check every reference of PREPRINT_v1 against the metadata fetched from Crossref, DataCite and arXiv (stored in
`paper/REFERENCES_CHECK_v1.json`): the full normalised title, the first author's family name, the year and the DOI or arXiv ID.
Successor of `refs_check_v1.py` (hashed by the run-6 locks, so not edited), which accepted two shortened titles. No network.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/refs_check_v2.py      # writes paper/REFERENCES_CHECK_v2.json
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PAPER = ROOT / "research" / "ledger" / "paper"


def norm(s: str) -> str:
    s = re.sub(r"<sup>.*?</sup>", "", s, flags=re.S)       # Crossref footnote markers
    s = re.sub(r"<[^>]+>", "", s)
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def main() -> int:
    meta = json.loads((PAPER / "REFERENCES_CHECK_v1.json").read_text(encoding="utf-8"))
    by_id = {k.lower(): v for k, v in meta["crossref"].items()}
    by_id.update({k.lower(): v for k, v in meta["datacite"].items()})
    by_id.update({("arxiv:" + k).lower(): v for k, v in meta["arxiv"].items()})
    text = (PAPER / "PREPRINT_v1.md").read_text(encoding="utf-8")
    refs = text.split("## References", 1)[1]
    entries = re.findall(r"^\s*(\d+)\.\s+(.+?)(?=^\s*\d+\.\s|\Z)", refs, flags=re.M | re.S)
    out, bad = [], 0
    for num, body in entries:
        body = " ".join(body.split())
        m = re.search(r"doi:(\S+?)\.?$", body) or re.search(r"(arXiv:\S+?)\.?$", body)
        ident = m.group(1) if m else None
        key = ident.lower() if ident else None
        md = by_id.get(key) if key else None
        row = {"n": int(num), "id": ident, "found": md is not None}
        if md:
            title = md.get("title") or ""
            authors = md.get("authors") or []
            toks = authors[0].split() if authors else []
            fam = [t for t in (toks[:1] + toks[-1:]) if len(t) > 1]   # Crossref lists family name first, arXiv given name first
            row.update({"title_full": norm(title) in norm(body.replace("*", "")),
                        "first_author": any(norm(t) and norm(t) in norm(body.split(".")[0] + body) for t in fam) and
                        any(norm(t) in norm(body[:60]) for t in fam),
                        "year": str(md.get("year")) in body if md.get("year") else None, "stored_title": title})
            ok = row["title_full"] and row["first_author"] and row["year"] is not False
        else:
            ok = False
        row["ok"] = bool(ok)
        bad += not ok
        out.append(row)
    cited = sorted({int(x) for grp in re.findall(r"\[(\d+(?:[-,]\s?\d+)*)\]", text.split("## References")[0]) for x in
                    re.sub(r"(\d+)-(\d+)", lambda mm: ",".join(str(i) for i in range(int(mm.group(1)), int(mm.group(2)) + 1)), grp).split(",")})
    order = []
    for grp in re.findall(r"\[(\d+(?:[-,]\s?\d+)*)\]", text.split("## References")[0]):
        for x in re.sub(r"(\d+)-(\d+)", lambda mm: ",".join(str(i) for i in range(int(mm.group(1)), int(mm.group(2)) + 1)), grp).split(","):
            if int(x) not in order:
                order.append(int(x))
    res = {"n_refs": len(out), "n_ok": len(out) - bad, "all_cited": cited == list(range(1, len(out) + 1)),
           "numbered_in_order_of_first_citation": order == list(range(1, len(out) + 1)), "first_citation_order": order, "refs": out}
    (PAPER / "REFERENCES_CHECK_v2.json").write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{res['n_ok']} of {res['n_refs']} references match their metadata; all cited: {res['all_cited']}; in order of first citation: "
          f"{res['numbered_in_order_of_first_citation']}")
    for r in out:
        if not r["ok"]:
            print("  FAIL", r)
    return 0 if bad == 0 and res["all_cited"] and res["numbered_in_order_of_first_citation"] else 1


if __name__ == "__main__":
    sys.exit(main())
