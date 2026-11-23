"""t6. C3: what the whole-ranking agreement measures, and how much it depends on the fixed seed split.

Reads: the sweep replicate tables (DX, MS, BS), gates_v6/TYPE_SETS_v6.json, thirdfly_v1/C_tests.json (C3, C3_wiring).
Post hoc and descriptive.
(1) reproduce C3's sweep ratios; (2) the share of the 181 types near zero in each animal; (3) the ratio when every score below
0.05 (the rulebook's non-driver band) is set to 0, so that the order among non-drivers no longer counts; (4) the ratio over
all 35 ways of splitting the 8 sweep seeds into two halves of 4 (C3 uses seeds 0-3 / 4-7 only); (5) wiring against simulation.
"""

from __future__ import annotations

import itertools

import numpy as np

from _common import AG, C, SETS, screens, show, ts

S = screens()
tl = AG._type_list(SETS["three_animal_noDNg100"])
PAIRS = {"MANC-BANC": ("DX", "BS"), "MaleCNS-BANC": ("MS", "BS"), "MANC-MaleCNS": ("DX", "MS")}
SEEDS = list(range(8))


def vec(k, seeds=None):
    return ts(S[k], tl, seeds).to_numpy(float)


def ratio(x1, x2, y1, y2):
    rx = (AG.spearman(x1, y2) + AG.spearman(x2, y1)) / 2
    c = (AG.spearman(x1, x2) + AG.spearman(y1, y2)) / 2
    return rx / c, rx, c


h = ([0, 1, 2, 3], [4, 5, 6, 7])
rep = {p: round(ratio(vec(a, h[0]), vec(a, h[1]), vec(b, h[0]), vec(b, h[1]))[0], 3) for p, (a, b) in PAIRS.items()}
show("(1) C3 sweep ratios reproduced (181 types, halves 0-3 / 4-7)", {"reproduced": rep, "locked": {
    "MANC-BANC": round(C["C3"]["sweep"]["MANC-BANC"]["three_animal_noDNg100"]["primary"]["ratio"], 3),
    "MaleCNS-BANC": round(C["C3"]["sweep"]["MaleCNS-BANC"]["three_animal_noDNg100"]["primary"]["ratio"], 3),
    "MANC-MaleCNS": round(C["C3"]["sweep"]["MANC-MaleCNS (reference, post hoc)"]["three_animal_noDNg100"]["primary"]["ratio"], 3)}})

show("(2) share of the 181 types per animal (sweep, all 8 seeds)", {k: {"score == 0": round(float((vec(k) == 0).mean()), 3),
     "score < 0.05": round(float((vec(k) < 0.05).mean()), 3), "score >= 0.5": round(float((vec(k) >= 0.5).mean()), 3)}
     for k in ("DX", "MS", "BS")})


def cens(v, z=0.05):
    return np.where(v < z, 0.0, v)


out = {}
for p, (a, b) in PAIRS.items():
    r0 = ratio(vec(a, h[0]), vec(a, h[1]), vec(b, h[0]), vec(b, h[1]))
    r1 = ratio(cens(vec(a, h[0])), cens(vec(a, h[1])), cens(vec(b, h[0])), cens(vec(b, h[1])))
    out[p] = {"ratio as locked": round(r0[0], 3), "rho_x, ceiling": [round(r0[1], 3), round(r0[2], 3)],
              "ratio with scores < 0.05 set to 0": round(r1[0], 3), "rho_x, ceiling (censored)": [round(r1[1], 3), round(r1[2], 3)]}
show("(3) does the gap live in the order of non-drivers?", out)

splits = [s for s in itertools.combinations(SEEDS, 4) if 0 in s]        # 35 unordered splits
spl = {}
for p, (a, b) in PAIRS.items():
    rs = []
    for s in splits:
        s1, s2 = list(s), [x for x in SEEDS if x not in s]
        rs.append(ratio(vec(a, s1), vec(a, s2), vec(b, s1), vec(b, s2))[0])
    rs = np.array(rs)
    spl[p] = {"n_splits": len(rs), "min": round(float(rs.min()), 3), "median": round(float(np.median(rs)), 3), "max": round(float(rs.max()), 3)}
rank = {}
for s in splits:
    s1, s2 = list(s), [x for x in SEEDS if x not in s]
    r = {p: ratio(vec(a, s1), vec(a, s2), vec(b, s1), vec(b, s2))[0] for p, (a, b) in PAIRS.items()}
    rank.setdefault(max(r, key=r.get), 0)
    rank[max(r, key=r.get)] += 1
show("(4) C3 sweep ratio over all 35 splits of the 8 seeds into 4 + 4", {"per pair": spl, "splits in which each pair agrees best": rank})

wr = C["C3_wiring"]["spearman"]
show("(5) wiring agreement (two-step signed counts, 5-synapse floor) against simulated agreement (sweep ratio)", {
    "MANC-MaleCNS": {"wiring": round(wr["MANC-MaleCNS"], 3), "simulation": rep["MANC-MaleCNS"]},
    "MANC-BANC": {"wiring": round(wr["MANC-BANC_floor5"], 3), "simulation": rep["MANC-BANC"]},
    "MaleCNS-BANC": {"wiring": round(wr["MaleCNS-BANC_floor5"], 3), "simulation": rep["MaleCNS-BANC"]}})
