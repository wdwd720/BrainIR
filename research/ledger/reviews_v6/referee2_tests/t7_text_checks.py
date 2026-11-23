"""t7. Text checks of PREPRINT_v1 / SUPPLEMENT_v1 against the rulebook, the LOG and the first-round requests (string searches).

Reads: paper/PREPRINT_v1.md, paper/SUPPLEMENT_v1.md, PREREG_v6.md, LOG.md, forward_v2/SHORTLIST.csv, pertype_v1/B1r.csv,
thirdfly_v1/C_tests.json. No numbers are computed beyond word counts.
"""

from __future__ import annotations

import re

import pandas as pd

from _common import C, LEDGER, show

P = (LEDGER / "paper" / "PREPRINT_v1.md").read_text()
SUP = (LEDGER / "paper" / "SUPPLEMENT_v1.md").read_text()
PRE = (LEDGER / "PREREG_v6.md").read_text()
LOG = (LEDGER / "LOG.md").read_text()


def sec(t, a, b=None):
    i = t.index(a) + len(a)
    return t[i:t.index(b, i)] if b else t[i:]


ab = sec(P, "## Abstract", "## Introduction")
words_ws = len(ab.split())
words_alnum = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9.,'%*/-]*", ab))
show("abstract length (limit 220)", {"whitespace tokens": words_ws, "tokens starting with a letter or digit (drops '=')": words_alnum})
show("main-text length (limit 3,500-5,000)", {"Introduction-Discussion": len(sec(P, "## Introduction", "## Limitations").split()),
     "Introduction-Limitations": len(sec(P, "## Introduction", "## Methods").split()),
     "Introduction-Methods": len(sec(P, "## Introduction", "## Use of AI").split()),
     "figures": len(re.findall(r"!\[\*\*Figure", P))})


def find(text, pat, w=160):
    return [text[max(0, m.start() - w):m.end() + w].replace("\n", " ") for m in re.finditer(pat, text)]


disc = sec(P, "## Discussion", "## Limitations")
show("C4's fixed sentence ('... does not show that the hits fail to recur') required beside 'at chance' (PREREG v6 C4)", {
    "rule": find(PRE, r"Beside\s+the\s+words,\s+always", 60),
    "abstract: 'at chance' contexts": find(ab, r"at chance", 80),
    "abstract contains 'does not show'": "does not show" in ab,
    "Discussion: 'at chance' contexts": find(disc, r"at chance", 120),
    "Discussion contains 'does not show'": "does not show" in disc})
show("same-name subset (G5: 'reported beside C3 and C4 without words')", {
    "rule": find(PRE, r"same-name subset", 60)[:1], "in paper": "same-name" in P or "same name" in P,
    "in supplement (beyond the departures list)": find(SUP, r"same-name", 80)})
show("'left unexamined' / 'did not examine' versus Part Q 4 (what was read before the freeze)", {
    "paper": find(P, r"left unexamined|did not examine|stayed blind", 120),
    "Part Q 4 (first sentences)": find(PRE, r"BANC itself, before this freeze", 400)[:1],
    "Part Q 3": find(PRE, r"The authors' paper on BANC", 300)[:1]})
show("'chosen, before any other neuron was run' versus the record", {
    "paper": find(P, r"before any other neuron was run", 150),
    "LOG L29 (run 1: MaleCNS screen B2 under the original procedure, locked)": find(LOG, r"\| L29 \|", 420)[:1],
    "LOG L55 (run 2: K chosen)": find(LOG, r"K = 1 \(smallest K", 200)[:1]})
show("Fig. 4 legend on DNg100 (the sweep has no K: see t2 (c))", find(P, r"DNg100's recurrence is built into", 200))
show("C2's explanation (see t5 (d))", find(P, r"does not add or\s+remove", 200))
show("does the paper say C1 and C2 ran on the tuned procedure that failed B4?", {
    "Results 1 BANC sentence": find(P, r"pre-registered test gave 0\.58", 200),
    "mentions of 'one-sided' with 'current-setting' or 'tuned' nearby": [s for s in find(P, r"[Oo]ne-sided", 200) if "current-setting" in s or "tuned" in s]})
show("the authors' own statement on cross-dataset differences (notes 9) cited?", {
    "'fidelity' in paper": "fidelity" in P, "'synapse detection' in paper": find(P, r"synapse detection", 100),
    "'surface area' or 'volume' (size measure differs between datasets)": ("surface area" in P) or ("volume" in P)})
first = {"tie-break": r"tie-break", "takeoff/flight (exam 1 negatives)": r"takeoff|flight", "3 of 18 / 17 % (audit split)": r"3 of 18|17 %|16\.7",
         "audit re-quoted the same sentences": r"same sentences|re-quot", "full-cord coupling (G3)": r"coupling",
         "best of eight 'picked on the same labels'": r"picked on|chosen on the same|same labels", "DNg63 / DNxl121 flagged": r"DNg63|DNxl121",
         "never-usable types": r"never[- ]usable", "confidence rule post hoc": r"rule (was )?(written|defined) after|post hoc.{0,40}confidence"}
show("first-round requests: occurrences in the paper / supplement", {k: {"paper": len(re.findall(v, P)), "supplement": len(re.findall(v, SUP))}
                                                                     for k, v in first.items()})
show("abstract and Discussion on counting", {"abstract": find(ab, r"counting", 120), "Discussion": find(disc, r"wiring counts", 120)})
show("Methods on reproducing the authors' dynamics", find(P, r"reproduced their published dynamical results", 150))
sl = pd.read_csv(LEDGER / "forward_v2" / "SHORTLIST.csv")
b1r = pd.read_csv(LEDGER / "pertype_v1" / "B1r.csv").set_index("manc_type")
dt = {r["manc_type"]: r for r in C["C5"]["driver_table"]}
show("forward list: the MANC-hit basis of the single-fly MANC hits", {t: {"B1r score": round(float(b1r.loc[t, "score"]), 2),
     "usable B1r replicates": int(b1r.loc[t, "n_usable"]), "MANC sweep": round(dt[t]["MANC_sweep"], 2) if t in dt else None,
     "A1": round(dt[t]["A1"], 2) if t in dt else None} for t in sl["manc_type"] if t in ("DNg63", "DNp02", "DNp41")})
show("placeholders left in the draft", find(P, r"\[\[AUTHOR TO COMPLETE", 60) + find(P, r"Title options", 40))
