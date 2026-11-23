"""t5. C1 and C2 in BANC: the procedure they ran on, the side rule, and what a Poisson copy of BANC removes.

Reads: thirdfly_v1/banc_dn_sides.csv (locked), the one-sided and copy replicate tables (BH-L, BH-R, BN-c1, BN-c2), the
BANC tuned and sweep logs, thirdfly_v1/C_tests.json. Section (d) ALSO READS A NETWORK MATRIX, not a result file: the authors'
released BANC matrix W_20260217.npz (pinned by SHA-256 in banc.py, checked on load) and, for comparison, the ledger's MANC
raw-count build (fixes.manc_raw_counts, checked against B1r's matrix on load). No simulation. Post hoc and descriptive.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from _common import AG, BN, C, H8, LEDGER, c1_sets_from_csv, screens, show, ts

S = screens()
sets = c1_sets_from_csv()
W = sets["label_consistent_noDNg100"]
cmp0 = AG.compare(S["BHL"], S["BHR"], W, H8)
show("(0) C1 reproduced from the locked side table", {"n_types": len(W), "ratio": round(cmp0["primary"]["ratio"], 3),
     "interval": [round(v, 3) for v in cmp0["bootstrap"]["interval"]["ratio"]],
     "locked": round(C["C1"]["label_consistent_noDNg100"]["primary"]["ratio"], 3)})

# (a) the procedure under C1/C2 is the tuned one that failed B4; its own positive control, and usability
dn = {}
for k in ("BHL", "BHR", "BN1", "BN2"):
    d = S[k][S[k]["type"] == "DNg100"]
    dn[k] = {"seeds_ge_0_5": int((d["usable"] & (d["score"] >= 0.5)).sum()), "of": int(len(d)),
             "type_score": round(float(ts(S[k], ["DNg100"]).iloc[0]), 3)} if len(d) else "not in screen"
use = {k: round(float(S[k]["usable"].mean()), 3) for k in ("BHL", "BHR", "BN1", "BN2", "BT")}
show("(a) DNg100 in the one-sided and copy screens (tuned procedure, 8 seeds; B4's bar would be 6 of 8)", {"DNg100": dn, "usable share of replicates": use})
# (a2) comparators: run 4's one-sided screens of MANC and MaleCNS (pertype_v1, locked), on run 4's primary type set
cmpd = {}
for f in ("MANC_L", "MANC_R", "MaleCNS_L", "MaleCNS_R"):
    t = pd.read_csv(LEDGER / "pertype_v1" / f"{f}.csv")
    t = t[t["primary_run4"].astype(bool)]
    cmpd[f] = {"types": int(len(t)), "usable share": round(float(t["n_usable"].sum() / t["n_seeds"].sum()), 3),
               "share of types scoring exactly 0": round(float((t["score"] == 0).mean()), 3)}
cmpd["BANC (C1 set)"] = {k: {"usable share": round(float(S[k][S[k]["type"].isin(W)]["usable"].mean()), 3),
                             "share of types scoring exactly 0": round(float((ts(S[k], W) == 0).mean()), 3)} for k in ("BHL", "BHR")}
show("(a2) one-sided screens: usable share and share of exact zeros, BANC against MANC and MaleCNS (run 4)", cmpd)

# (b) the side rule: how lateralised are the members of the C1 types, and is the gap the same for weakly lateralised types?
sd = pd.read_csv(LEDGER / "thirdfly_v1" / "banc_dn_sides.csv")
sd["share"] = sd[["out_L", "out_R"]].max(axis=1) / (sd["out_L"] + sd["out_R"]).replace(0, np.nan)
defined = sd["output_side"].notna() & sd["annotated"].isin(["L", "R"])
dis = sd[defined & (sd["annotated"] != sd["output_side"])]
show("(b1) annotated side vs output side", {"members with both defined": int(defined.sum()),
     "agree": round(float((sd.loc[defined, "annotated"] == sd.loc[defined, "output_side"]).mean()), 3),
     "disagreeing members": int(len(dis)), "their output share on the output side (median, IQR)":
     [round(float(dis["share"].median()), 2), round(float(dis["share"].quantile(0.25)), 2), round(float(dis["share"].quantile(0.75)), 2)],
     "disagreeing members with >= 80 % of output on one side": int((dis["share"] >= 0.8).sum())})
tmin = sd[sd["manc_type"].isin(W)].groupby("manc_type")["share"].min().reindex(W)
med = float(tmin.median())
strong = [t for t in W if tmin[t] >= med]
weak = [t for t in W if tmin[t] < med]
res = {"types": len(W), "median of the least lateralised member's output share": round(med, 3),
       "members with < 60 % of output on their assigned side": int((sd[sd["manc_type"].isin(W)]["share"] < 0.6).sum()),
       "of members": int(sd["manc_type"].isin(W).sum())}
for lab, tl in (("strongly lateralised half", strong), ("weakly lateralised half", weak)):
    cc = AG.compare(S["BHL"], S["BHR"], tl, H8, n_boot=2000)
    res[lab] = {"n": len(tl), "ratio": None if cc["primary"]["ratio"] is None else round(cc["primary"]["ratio"], 3),
                "interval": [None if v is None else round(v, 3) for v in cc["bootstrap"]["interval"]["ratio"]],
                "ceiling": round(cc["primary"]["c"], 3),
                "drivers L/R": [int((ts(S["BHL"], tl) >= 0.5).sum()), int((ts(S["BHR"], tl) >= 0.5).sum())]}
show("(b2) C1's ratio split by how lateralised the types' members are (2,000 resamples)", res)
zero = {k: round(float((ts(S[k], W) == 0).mean()), 3) for k in ("BHL", "BHR")}
show("(b3) share of C1's 180 types scoring exactly 0", zero)

# (d) what a Poisson copy removes (reads network matrices)
Cb = BN.raw_counts()
c = Cb.data
tot = c.sum()
pdel = np.exp(-c)
show("(d1) BANC as released (no floor): connections and the Poisson copy (count c -> Poisson(c), zeros dropped)", {
    "connections": int(len(c)), "share with count 1 / 2 / <=4": [round(float((c == 1).mean()), 3), round(float((c == 2).mean()), 3),
                                                                 round(float((c <= 4).mean()), 3)],
    "expected share of connections removed per copy": round(float(pdel.mean()), 3),
    "expected share of synapses (|weight|) in removed connections": round(float((pdel * c).sum() / tot), 4),
    "connections added": 0})
try:
    from brainir_ledger import fixes as FX

    m = FX.manc_raw_counts().data
    kept = m >= 5
    p_del = stats.poisson.cdf(4, m[kept])            # a kept connection drops below the floor
    p_add = stats.poisson.sf(4, m[~kept])            # a sub-floor connection rises to >= 5
    show("(d2) MANC at the 5-synapse floor (raw counts from the ledger's build): one Poisson copy", {
        "connections kept at floor 5": int(kept.sum()), "sub-floor connections (1-4)": int((~kept).sum()),
        "expected share of kept connections removed": round(float(p_del.mean()), 3),
        "expected connections added, as a share of kept ones": round(float(p_add.sum() / kept.sum()), 3),
        "expected share of synapses (|weight|) in removed connections": round(float((p_del * m[kept]).sum() / m[kept].sum()), 4),
        # E[X 1(X >= 5)] = c P(Poisson(c) >= 4) for X ~ Poisson(c)
        "expected synapses in added connections, as a share of kept synapses":
            round(float((m[~kept] * stats.poisson.sf(3, m[~kept])).sum() / m[kept].sum()), 4)})
except Exception as e:  # noqa: BLE001
    show("(d2) MANC raw counts unavailable", repr(e))
