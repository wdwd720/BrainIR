"""t1. C4: is "our lists above chance, the authors' list at chance" a difference in recurrence or in list size?

Reads: thirdfly_v1/C_tests.json (C4, locked), the replicate tables (A1, B1r, B2r, BANC tuned and sweep, MANC/MaleCNS sweeps),
predictions/A0/types.csv (the authors' single-neuron screen per type, locked), gates_v6/TYPE_SETS_v6.json.
Post hoc and descriptive: nothing here carries pre-registered words.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from _common import C, H8, H16, LEDGER, O6, SETS, T, hyper_p, screens, show, ts

S = screens()
c4 = C["C4"]
WORD = {"MANC sweep list": "manc_banc_high_noDNg100", "A1 (the authors' list; 16-replicate halves under either procedure)":
        "manc_banc_high_noDNg100", "MaleCNS sweep list": "mcns_banc_high_noDNg100"}

# 1. reproduce the locked word-set numbers
rows = []
for name, sk in WORD.items():
    p = c4[name][sk]["cuts"]["0.5"]["overlap"]["point"]
    rows.append({"list": name.split(" (")[0], "N": p["N"], "hits": p["n_x"], "BANC hits": p["n_y"], "recur": p["k"],
                 "rate": round(p["k"] / p["n_x"], 3), "BANC base rate": round(p["n_y"] / p["N"], 3),
                 "chance": round(p["chance_expectation"], 2), "p": round(p["hypergeom_p"], 3), "types_in_both": p.get("types_in_both")})
show("locked C4 at 0.5 (word sets)", rows)

# 2. are the recurrence rates different? (Fisher exact, two-sided)
k = {r["list"]: (r["recur"], r["hits"]) for r in rows}
pairs = [("A1", "MANC sweep list"), ("A1", "MaleCNS sweep list"), ("MANC sweep list", "MaleCNS sweep list")]
show("Fisher exact tests of recurrence rates", {f"{a} vs {b}": {"table": [[k[a][0], k[a][1] - k[a][0]], [k[b][0], k[b][1] - k[b][0]]],
     "p_two_sided": round(stats.fisher_exact([[k[a][0], k[a][1] - k[a][0]], [k[b][0], k[b][1] - k[b][0]]])[1], 3)} for a, b in pairs})

# 3. power of a 6-hit list: smallest k with hypergeometric p < 0.05 at N 202, 20 BANC hits; chance of reaching it
N, ny = 202, 20
kneed = next(kk for kk in range(0, 7) if hyper_p(kk, N, ny, 6) < 0.05)
pw = {f"true share {s}": round(float(stats.binom.sf(kneed - 1, 6, s)), 3) for s in (0.10, 0.20, 0.294, 0.50)}
show("A1 (6 hits): recurrences needed for p < 0.05, and the probability of reaching them", {"k_needed": kneed, **pw})

# 4. which of the authors' six recur; DNb08 is one (the authors reported DNb08 fails in BANC)
tl = SETS["manc_banc_high_noDNg100"]
a1, bs, bt = ts(S["A1"], tl), ts(S["BS"], tl), ts(S["BT"], tl)
six = a1[a1 >= 0.5].index.tolist()
show("the authors' six (A1 >= 0.5, word set) with their BANC sweep and tuned scores",
     {t: {"A1": round(a1[t], 2), "BANC_sweep": round(bs[t], 2), "BANC_tuned": round(bt[t], 2)} for t in six})
rest = [t for t in six if t != "DNb08"]
show("without DNb08 (whose BANC failure the authors published)", {"recur": int((bs[rest] >= 0.5).sum()), "of": len(rest),
     "p": round(hyper_p(int((bs[rest] >= 0.5).sum()), N - 1, int((bs.drop('DNb08') >= 0.5).sum()), len(rest)), 3)})

# 5. post hoc: the authors' MAIN published list (single-neuron screen A0, Supp. Table 1: any copy >= 0.5) in BANC
a0 = pd.read_csv(LEDGER / "predictions" / "A0" / "types.csv").set_index("manc_type")
out = {}
for label, col in (("any copy >= 0.5 (Supp. Table 1 types)", "type_max"), ("mean of copies >= 0.5", "type_mean")):
    s = a0[col].reindex(tl).fillna(0.0)
    hits = s[s >= 0.5].index.tolist()
    kk = int((bs[hits] >= 0.5).sum())
    out[label] = {"n_hits_in_word_set": len(hits), "hits": hits, "recur_in_BANC_sweep": kk,
                  "recurring": [t for t in hits if bs[t] >= 0.5], "chance": round(len(hits) * int((bs >= 0.5).sum()) / len(tl), 2),
                  "p": round(hyper_p(kk, len(tl), int((bs >= 0.5).sum()), len(hits)), 3)}
show("POST HOC: the authors' single-neuron list (A0) against the BANC sweep, manc_banc_high_noDNg100", out)

# 6. counterfactual: C4 had the tuned BANC screen been valid (B4 missed by one DNg100 seed: 11 of 16, bar 12)
lists = {"B1r (our MANC list)": (S["B1r"], H16, ("manc_banc_high_noDNg100",)),
         "A1 (authors)": (S["A1"], H16, ("manc_banc_high_noDNg100",)),
         "B2r (our MaleCNS list)": (S["B2r"], H16, ("mcns_banc_high_noDNg100",))}
cf = T.c4(lists, S["BT"], H16)
show("COUNTERFACTUAL C4 on the tuned screens (not of record)", {n: {sk: {z: {kk: blk["cuts"][z]["overlap"]["point"][kk] for kk in
     ("n_x", "n_y", "k", "chance_expectation", "hypergeom_p", "OC_ratio")} for z in ("0.3", "0.5")} | {"words_at_0.5": blk["words_at_0.5"]}
     for sk, blk in v.items()} for n, v in cf.items() if isinstance(v, dict) and n not in ("note",)})
