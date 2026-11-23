"""The hand-check kit (RUN6_PROMPT section 9): twenty items drawn by a seeded random rule (`default_rng(20261691)`): ten clear label
cells of exam 2 (yes / no, its twelve primary dimensions), nine clear labels of exam 1's primary set, and DNg100. For each: the claim, a
quote of at most 25 words from the record that supports it, the source with its DOI, where to look, and boxes. Reads only frozen label
files; writes `paper/HAND_CHECK.md`.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/hand_check_v1.py
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brainir_ledger import RESEARCH  # noqa: E402

SEED = 20261691
DIMS = {"d1": "any visible movement", "d2": "front legs move", "d3": "middle legs move", "d4": "hind legs move",
        "d5": "legs flex or the body lowers, held", "d6": "legs extend or the body rises, held",
        "d7p": "repeated leg movement, coordinated or not", "d10": "a jump or takeoff", "d11": "any wing movement",
        "d13": "wing buzzing or flight-like beating", "d14": "haltere movement", "d15": "abdomen movement"}
BOX = "[ ] agree   [ ] disagree   [ ] unsure"


def q25(s: str) -> str:
    w = " ".join(str(s).split()).split(" ")
    return " ".join(w[:25]) + (" ..." if len(w) > 25 else "")


def exam2(rng) -> list[dict]:
    cons = list(csv.DictReader(open(RESEARCH / "labels_h1" / "consensus.csv")))
    cells = [(r["unit"], d, r[d]) for r in cons for d in DIMS if r.get(d) in ("yes", "no")]
    recs = list(csv.DictReader(open(RESEARCH / "labels_h1" / "records.csv")))
    out = []
    for i in rng.choice(len(cells), size=len(cells), replace=False):
        unit, d, lab = cells[i]
        sup = [r for r in recs if r["unit"] == unit and r.get(d) == lab and r.get("quote", "").strip()]
        if not sup:
            continue
        r = sorted(sup, key=lambda x: x["record_id"])[0]
        out.append({"exam": "exam 2", "claim": f"Activating hemilineage {unit}: '{DIMS[d]}' = **{lab}** (exam 2 label cell {unit} x {d})",
                    "quote": q25(r["quote"]), "doi": r["doi"], "where": r.get("locator") or "-", "record": r["record_id"],
                    "preparation": r.get("preparation", "")})
        if len(out) == 10:
            break
    return out


def exam1(rng) -> tuple[list[dict], dict]:
    sys.path.insert(0, str(HERE.parent))
    import forward_v1 as F1  # noqa: PLC0415

    prim = F1.primary_set()
    recs = [json.loads(x) for x in open(RESEARCH / "labels_v2" / "records.jsonl")]
    types = sorted(prim.index)
    out = []
    for i in rng.choice(len(types), size=len(types), replace=False):
        t = types[i]
        lab = "yes" if int(prim[t]) == 1 else "no"
        sup = [r for r in recs if r["manc_type"] == t and r.get("front_leg_rhythm") == lab and str(r.get("quote") or "").strip()]
        if not sup:
            continue
        sup.sort(key=lambda r: (not r.get("quote_verified"), {"high": 0, "medium": 1, "low": 2}.get(r.get("labeler_confidence"), 3), r["record_id"]))
        r = sup[0]
        out.append({"exam": "exam 1", "claim": f"Activating {t} {'produces' if lab == 'yes' else 'does not produce'} rhythmic front-leg movement "
                                                f"(exam 1 label: **{lab}**)", "quote": q25(r["quote"]), "doi": r["doi"],
                    "where": f"{r.get('source_locator') or '-'}; page {r.get('page') or '-'}", "record": r["record_id"],
                    "preparation": r.get("preparation", "")})
        if len(out) == 9:
            break
    dng = [r for r in recs if r["manc_type"] == "DNg100"]
    yes = sorted([r for r in dng if r.get("front_leg_rhythm") == "yes" and r.get("preparation") == "headless"] or
                 [r for r in dng if r.get("front_leg_rhythm") == "yes"], key=lambda r: r["record_id"])[0]
    no = [r for r in dng if r.get("front_leg_rhythm") == "no"][0]
    item = {"exam": "DNg100", "claim": "Activating DNg100 produces rhythmic front-leg movement in headless flies (audited label: **yes**; exam 1's "
                                       "label was 'no', from a record of DNg100 activated together with a brake neuron)",
            "quote": q25(yes["quote"]), "doi": yes["doi"], "where": f"{yes.get('source_locator') or '-'}; page {yes.get('page') or '-'}",
            "record": yes["record_id"], "preparation": yes.get("preparation", ""),
            "second": {"quote": q25(no["quote"]), "doi": no["doi"], "where": f"{no.get('source_locator') or '-'}; page {no.get('page') or '-'}",
                       "record": no["record_id"]}}
    return out, item


def main() -> None:
    rng = np.random.default_rng(SEED)
    e2 = exam2(rng)
    e1, dng = exam1(rng)
    items = e2 + e1 + [dng]
    L = ["# Hand-check kit (20 items)", "",
         "**What this is.** Twenty labels from the two exams, drawn by a fixed random rule (`ledger/scripts/posthoc/hand_check_v1.py`,",
         f"`default_rng({SEED})`): ten clear exam 2 label cells, nine clear exam 1 labels, and DNg100. Each label was read from the paper by a",
         "language-model reader. Your job: open the source, find the place, and decide whether the label is right. Tick one box per item.",
         "", "**How to judge.** Agree if the source, at the place given, says what the claim says for that neuron or hemilineage under that",
         "preparation (headless = decapitated). Disagree if it says otherwise or does not say it. Unsure if you cannot tell. The quote is the",
         "reader's own excerpt, cut to at most 25 words; check it against the source too.", ""]
    for n, it in enumerate(items, start=1):
        L += [f"## {n}. {it['exam']}", "", f"- **Claim:** {it['claim']}", f"- **Quote:** \"{it['quote']}\"",
              f"- **Source:** https://doi.org/{it['doi']}", f"- **Where to look:** {it['where']} (preparation: {it.get('preparation') or '-'}; record "
              f"`{it['record']}`)"]
        if "second" in it:
            s = it["second"]
            L += [f"- **The record behind exam 1's 'no':** \"{s['quote']}\" (https://doi.org/{s['doi']}; {s['where']}; record `{s['record']}`)"]
        L += [f"- {BOX}", ""]
    L += ["## The sentence for the Methods, once you have done it", "",
          "> The sole human author checked 20 labels drawn by a seeded random rule (ten exam 2 label cells, nine exam 1 labels and DNg100)",
          "> against their sources: ___ agreed, ___ disagreed and ___ were unsure.", ""]
    (RESEARCH / "paper" / "HAND_CHECK.md").write_text("\n".join(L) + "\n")
    print(len(e2), len(e1), "+ DNg100")


if __name__ == "__main__":
    main()
