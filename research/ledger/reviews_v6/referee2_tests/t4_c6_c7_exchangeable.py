"""t4. C7 assumes the three animals are exchangeable noisy measurements of one screen. Do the run's own numbers allow that?

Reads: the sweep replicate tables (DX, MS, BS) and the tuned ones (B1r, B2r, BT), gates_v6/TYPE_SETS_v6.json,
thirdfly_v1/C_tests.json (C6, C7). Uses thirdfly_v1's own resampling helpers. Post hoc; no words.
(1) reproduce C7's three ratios and C6's d_M, d_C; (2) paired type-resample intervals of the differences between pair ratios
(exchangeable animals predict 0) and of d_M - d_C (= rho(C,B) - rho(M,B)); (3) n* per pair and over the three pairs treated as
a sample of animal pairs; (4) the same estimate on the tuned screens.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

from _common import AG, C, H8, H16, SETS, T, screens, show, ts

S = screens()
tl = AG._type_list(SETS["three_animal_noDNg100"])


def nstar(r):
    return 1.0 if r >= 0.8 else (4 * (1 - r) / r if r > 0 else float("inf"))


def pair_ratios(m, c, b, hv, seed=20261603):
    v = T._vecs({"M": m, "C": c, "B": b}, tl, hv)
    idx = np.random.default_rng(seed).integers(0, len(tl), size=(10_000, len(tl)))
    bb = T._boot_pairs(v, [("M", "B"), ("C", "B"), ("M", "C")], idx)
    keep = bb[("M", "B")]["keep"] & bb[("C", "B")]["keep"] & bb[("M", "C")]["keep"]
    pts = {p: AG.compare(X, Y, tl, hv)["primary"]["ratio"] for p, (X, Y) in {"MB": (m, b), "CB": (c, b), "MC": (m, c)}.items()}
    diffs = {}
    for a, b2 in (("CB", "MC"), ("CB", "MB"), ("MB", "MC")):
        d = bb[(a[0], a[1])]["ratio"][keep] - bb[(b2[0], b2[1])]["ratio"][keep]
        diffs[f"{a} - {b2}"] = {"point": round(pts[a] - pts[b2], 3), "95%": [round(float(np.percentile(d, 2.5)), 3), round(float(np.percentile(d, 97.5)), 3)]}
    return pts, diffs


for label, (m, c, b, hv) in {"sweep (primary)": (S["DX"], S["MS"], S["BS"], H8), "tuned (counterfactual)": (S["B1r"], S["B2r"], S["BT"], H16)}.items():
    pts, diffs = pair_ratios(m, c, b, hv)
    r = np.array(list(pts.values()))
    rbar, sd = float(r.mean()), float(r.std(ddof=1))
    tq = stats.t.ppf(0.975, 2)
    lo, hi = rbar - tq * sd / np.sqrt(3), rbar + tq * sd / np.sqrt(3)
    show(f"C7 on the {label} screens", {
        "pair ratios (MB = MANC-BANC, CB = MaleCNS-BANC, MC = MANC-MaleCNS)": {k: round(v, 3) for k, v in pts.items()},
        "differences between pair ratios, same type resamples (exchangeable animals: 0)": diffs,
        "rbar": round(rbar, 3), "n* from rbar": round(nstar(rbar), 2), "n* per pair": {k: round(nstar(v), 2) for k, v in pts.items()},
        "rbar 95% t-interval over the 3 pairs (2 df, illustrative)": [round(lo, 3), round(hi, 3)],
        "n* at those ends": [round(nstar(hi), 1), (round(nstar(lo), 1) if lo > 0 else "infinite")]})
show("locked C7 (for comparison)", {k: C["C7"][k] for k in ("ratios", "rbar", "n_star", "interval")})

# C6: d_M - d_C = rho(C,B) - rho(M,B), with C6's own resamples (seed 20261602)
v = {k: ts(S[s], tl).to_numpy(float) for k, s in (("M", "DX"), ("C", "MS"), ("B", "BS"))}
idx = np.random.default_rng(20261602).integers(0, len(tl), size=(10_000, len(tl)))
rh = AG._resampled_rhos(v, [("M", "B"), ("C", "B"), ("M", "C")], idx)
d = rh[("C", "B")] - rh[("M", "B")]
show("C6 on the sweep: full-seed Spearman between animals, and rho(C,B) - rho(M,B) (= d_M - d_C)", {
    "rho(M,B)": round(AG.spearman(v["M"], v["B"]), 3), "rho(C,B)": round(AG.spearman(v["C"], v["B"]), 3),
    "rho(M,C)": round(AG.spearman(v["M"], v["C"]), 3),
    "rho(C,B) - rho(M,B)": {"point": round(AG.spearman(v["C"], v["B"]) - AG.spearman(v["M"], v["B"]), 3),
                            "95%": [round(float(np.nanpercentile(d, 2.5)), 3), round(float(np.nanpercentile(d, 97.5)), 3)]},
    "locked d_M, d_C": [round(C["C6"]["d_M"]["point"], 3), round(C["C6"]["d_C"]["point"], 3)]})
