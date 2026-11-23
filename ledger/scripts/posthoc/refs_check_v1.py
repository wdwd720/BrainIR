"""Check every reference of PREPRINT_v1 against its source (RUN6_PROMPT section 8: title, authors, year and venue; drop what cannot be
verified). Crossref for DOIs, DataCite for the Zenodo DOI, the arXiv API for arXiv IDs, and Crossref bibliographic search for the items
whose DOI is not known in advance. Public metadata GET requests only, with a generic client name. Output: `paper/REFERENCES_CHECK_v1.json`.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/refs_check_v1.py
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brainir_ledger import RESEARCH  # noqa: E402

UA = {"User-Agent": "BrainIR-ledger-refcheck/1.0"}
DOIS = ["10.1038/s41586-026-11195-y", "10.1101/2025.09.12.675944", "10.7554/eLife.97769", "10.1038/s41586-024-07389-x",
        "10.1038/s41586-024-07763-9", "10.7554/eLife.34275", "10.7554/eLife.34272", "10.1016/j.neuron.2020.07.032",
        "10.7554/eLife.04493", "10.7554/eLife.106042", "10.7554/eLife.96084", "10.64898/2026.04.29.721658",
        "10.1111/j.2044-8295.1910.tb00206.x", "10.1111/j.2044-8295.1910.tb00207.x", "10.1177/001316446002000104",
        "10.1038/s41586-026-10735-w", "10.1101/2025.07.31.667571", "10.1016/j.cell.2026.08.015", "10.1101/2025.10.09.680999",
        "10.3390/biomimetics11110835"]
DATACITE = ["10.5281/zenodo.22260924"]
ARXIV = ["2609.38665", "2610.29205"]
SEARCH = {"BANC": "Distributed control circuits across a brain-and-cord connectome",
          "MaleCNS": "Sexual dimorphism in the complete connectome of the Drosophila male central nervous system",
          "Biomimetics review": "Connectomes as Structural Priors for Embodied Control"}


def crossref(doi: str) -> dict:
    r = requests.get(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}", headers=UA, timeout=60)
    if r.status_code != 200:
        return {"doi": doi, "ok": False, "status": r.status_code}
    m = r.json()["message"]
    date = (m.get("published-print") or m.get("published-online") or m.get("posted") or m.get("issued") or {}).get("date-parts", [[None]])[0]
    return {"doi": doi, "ok": True, "title": (m.get("title") or [""])[0], "authors": [f"{a.get('family', '')} {a.get('given', '')}".strip()
            for a in m.get("author", [])], "year": date[0] if date else None, "venue": (m.get("container-title") or [m.get("institution", [{}])[0].get("name") if m.get("institution") else m.get("publisher")])[0],
            "type": m.get("type"), "volume": m.get("volume"), "issue": m.get("issue"), "page": m.get("page") or m.get("article-number"),
            "abstract": re.sub(r"<[^>]+>", " ", m.get("abstract") or "").strip()[:3000]}


def datacite(doi: str) -> dict:
    r = requests.get(f"https://api.datacite.org/dois/{urllib.parse.quote(doi)}", headers=UA, timeout=60)
    if r.status_code != 200:
        return {"doi": doi, "ok": False, "status": r.status_code}
    a = r.json()["data"]["attributes"]
    return {"doi": doi, "ok": True, "title": (a.get("titles") or [{}])[0].get("title"), "authors": [c.get("name") for c in a.get("creators", [])],
            "year": a.get("publicationYear"), "venue": a.get("publisher")}


def arxiv(i: str) -> dict:
    r = requests.get(f"https://export.arxiv.org/api/query?id_list={i}", headers=UA, timeout=60)
    t = r.text
    entries = re.findall(r"<entry>(.*?)</entry>", t, flags=re.S)
    if r.status_code != 200 or not entries or "<title>Error</title>" in entries[0]:
        return {"arxiv": i, "ok": False, "status": r.status_code}
    e = entries[0]
    title = " ".join(re.findall(r"<title>(.*?)</title>", e, flags=re.S)[0].split())
    authors = re.findall(r"<name>(.*?)</name>", e)
    pub = re.findall(r"<published>(\d{4})", e)
    cat = re.findall(r'<arxiv:primary_category[^>]*term="([^"]+)"', e)
    abstract = " ".join(re.findall(r"<summary>(.*?)</summary>", e, flags=re.S)[0].split())
    return {"arxiv": i, "ok": True, "title": title, "authors": authors, "year": int(pub[0]) if pub else None, "venue": f"arXiv ({cat[0] if cat else '?'})",
            "abstract": abstract}


def search(q: str) -> list[dict]:
    r = requests.get("https://api.crossref.org/works", params={"query.bibliographic": q, "rows": 3}, headers=UA, timeout=60)
    if r.status_code != 200:
        return [{"ok": False, "status": r.status_code}]
    out = []
    for m in r.json()["message"]["items"]:
        date = (m.get("published-print") or m.get("published-online") or m.get("posted") or m.get("issued") or {}).get("date-parts", [[None]])[0]
        out.append({"doi": m.get("DOI"), "title": (m.get("title") or [""])[0], "authors": [f"{a.get('family', '')} {a.get('given', '')}".strip()
                    for a in m.get("author", [])][:6], "year": date[0] if date else None, "venue": (m.get("container-title") or [m.get("publisher")])[0]})
    return out


def main() -> None:
    out = {"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "crossref": {}, "datacite": {}, "arxiv": {}, "search": {}}
    for d in DOIS:
        out["crossref"][d] = crossref(d)
        time.sleep(0.5)
    for d in DATACITE:
        out["datacite"][d] = datacite(d)
    for i in ARXIV:
        out["arxiv"][i] = arxiv(i)
        time.sleep(3)
    for k, q in SEARCH.items():
        out["search"][k] = search(q)
        time.sleep(0.5)
    p = RESEARCH / "paper" / "REFERENCES_CHECK_v1.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    for sec in ("crossref", "datacite", "arxiv"):
        for k, v in out[sec].items():
            print(sec, k, "|", v.get("ok"), "|", (v.get("title") or "")[:90], "|", (v.get("authors") or [""])[0] if v.get("authors") else "", "|", v.get("year"), "|", v.get("venue"))
    for k, v in out["search"].items():
        print("search", k, "|", [(x.get("doi"), (x.get("title") or "")[:70], x.get("year")) for x in v][:2])


if __name__ == "__main__":
    main()
