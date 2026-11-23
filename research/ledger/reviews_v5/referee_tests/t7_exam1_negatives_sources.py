"""Referee test 7: what evidence decides exam 1's 14 'no' labels, and is the audit independent of it?

Inputs (locked): results/run2/scorecard.csv (primary set, labels), labels_v2/records.jsonl (exam 1 final records),
labels_audit_v1/final_records.jsonl (the audit's final records), labels_audit_v1/comparison_with_exam1.csv.
Eligibility as exam 1's consensus rule: no sighting, mapping confidence not low.
Reports, from record fields only (DOI, preparation, line_specificity, behaviour_category, quote):
 (a) per 'no' type: eligible records by front-leg value; the DOIs and behaviour categories of its 'no' records;
 (b) per DOI: how many of the 14 'no' types have a 'no' record from it;
 (c) behaviour categories of all eligible 'no' records of the 14 types;
 (d) for the 25 'yes' types: how many rest only on atlas records (DOI 10.7554/elife.34275) and how those records' quotes look
     (a line ID instead of text);
 (e) the audit: for each 'no' type, the audited label and the share of the audit's 'no' records whose normalised quote equals a
     quote of an exam 1 'no' record of the same type (same sentence read again).
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t7_exam1_negatives_sources.py
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")
ATLAS = "10.7554/elife.34275"


def norm(q: str) -> str:
    q = unicodedata.normalize("NFKC", q or "").lower()
    return re.sub(r"[^a-z0-9]+", " ", q).strip()


def load(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


def main() -> None:
    sc = pd.read_csv(ROOT / "results/run2/scorecard.csv")
    ps = sc[sc["in_primary_set"]].set_index("manc_type")
    no_types = sorted(ps.index[ps.front == "no"])
    yes_types = sorted(ps.index[ps.front == "yes"])
    ex = [r for r in load(ROOT / "labels_v2/records.jsonl")
          if not r.get("saw_simulation_score") and r.get("mapping_confidence") != "low"]
    au = load(ROOT / "labels_audit_v1/final_records.jsonl")
    comp = pd.read_csv(ROOT / "labels_audit_v1/comparison_with_exam1.csv").set_index("manc_type")
    by_type = defaultdict(list)
    for r in ex:
        by_type[r.get("manc_type")].append(r)
    out: dict = {"no_types": {}, "doi_counts_over_no_types": {}, "behaviour_of_no_records": {}, "yes_types": {}, "audit": {}}
    doi_types = defaultdict(set)
    beh = Counter()
    for t in no_types:
        rs = by_type[t]
        vals = Counter(r["front_leg_rhythm"] for r in rs)
        nos = [r for r in rs if r["front_leg_rhythm"] == "no"]
        for r in nos:
            doi_types[r["doi"]].add(t)
            beh[r.get("behaviour_category")] += 1
        out["no_types"][t] = {
            "exam1_best_preparation": ps.loc[t, "best_preparation"],
            "eligible_records_by_front_value": dict(vals),
            "no_records": sorted({(r["doi"], r["preparation"], r["line_specificity"], r.get("behaviour_category")) for r in nos}),
            "yes_records_dois": sorted({r["doi"] for r in rs if r["front_leg_rhythm"] == "yes"}),
        }
    out["doi_counts_over_no_types"] = {d: sorted(v) for d, v in sorted(doi_types.items(), key=lambda kv: -len(kv[1]))}
    out["behaviour_of_no_records"] = dict(beh.most_common())
    # (d) yes types resting on the atlas only
    atlas_only, quote_is_line_id = [], 0
    n_atlas_yes = 0
    for t in yes_types:
        dois = {r["doi"] for r in by_type[t] if r["front_leg_rhythm"] == "yes"}
        if dois == {ATLAS}:
            atlas_only.append(t)
        for r in by_type[t]:
            if r["doi"] == ATLAS and r["front_leg_rhythm"] == "yes":
                n_atlas_yes += 1
                if re.fullmatch(r"\s*[A-Z]{1,3}\d{3,6}.*", r.get("quote") or "") and len(r.get("quote") or "") < 40:
                    quote_is_line_id += 1
    out["yes_types"] = {"n": len(yes_types), "yes_from_atlas_records_only": atlas_only, "n_atlas_only": len(atlas_only),
                        "atlas_yes_records": n_atlas_yes, "atlas_yes_records_whose_quote_is_a_line_id": quote_is_line_id,
                        "best_preparation": dict(Counter(ps.loc[yes_types, "best_preparation"]))}
    # (e) the audit re-reads the same sentences
    for t in no_types:
        ex_q = {norm(r.get("quote")) for r in by_type[t] if r["front_leg_rhythm"] == "no"}
        a_no = [r for r in au if r.get("manc_type") == t and r.get("front_leg_rhythm") == "no"]
        same = sum(1 for r in a_no if norm(r.get("quote")) in ex_q or any(norm(r.get("quote")) and norm(r.get("quote")) in q or q in norm(r.get("quote")) for q in ex_q if q))
        out["audit"][t] = {"audited_label": comp.loc[t, "audited"] if t in comp.index else None,
                           "audit_no_records": len(a_no), "audit_no_records_quoting_an_exam1_no_sentence": same,
                           "audit_no_dois": sorted({r.get("doi") for r in a_no})}
    tot = sum(v["audit_no_records"] for v in out["audit"].values())
    same = sum(v["audit_no_records_quoting_an_exam1_no_sentence"] for v in out["audit"].values())
    out["audit_summary"] = {"audit_no_records": tot, "quoting_an_exam1_no_sentence": same,
                            "types_still_no_after_audit": sorted(t for t, v in out["audit"].items() if v["audited_label"] == "no")}
    OUT.write_text(json.dumps(out, indent=1, default=str))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
