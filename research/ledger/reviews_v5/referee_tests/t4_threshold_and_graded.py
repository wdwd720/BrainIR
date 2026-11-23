"""Referee test 4: does 'the hit lists barely overlap' depend on the post-hoc driver threshold of 0.5?

Inputs (locked): pertype_v1/B1r.csv, B2r.csv, A1.csv (score, score_h1, score_h2), pertype_v1/match_confidence.csv.
For thresholds 0.2-0.6 and for the high-confidence (215) and all common (310) type sets:
  drivers in each fly, shared, hypergeometric expectation and one-sided hypergeometric p (P[X >= observed]);
  replication rate of MANC hits; overlap coefficient (OC) on matched halves (B1r_h1 x B2r_h2, B1r_h2 x B2r_h1) against the
  within-fly split-half OC (the draft's ratio), computed exactly as PREREG v5 R2.2 describes (point estimates only).
Graded replication, threshold-free: AUROC with which B2r's score separates B1r's drivers from B1r's other types (and the
reverse), with a 10,000-resample bootstrap over types (default_rng(7)); and the same on matched halves against the
within-fly split-half value.
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t4_threshold_and_graded.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import hypergeom

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")


def auroc(score: np.ndarray, lab: np.ndarray) -> float:
    pos, neg = score[lab], score[~lab]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def oc(a: np.ndarray, b: np.ndarray, thr: float) -> float:
    x, y = a >= thr, b >= thr
    m = min(x.sum(), y.sum())
    return float((x & y).sum() / m) if m else float("nan")


def main() -> None:
    P = ROOT / "pertype_v1"
    mc = pd.read_csv(P / "match_confidence.csv").set_index("manc_type")
    b2 = pd.read_csv(P / "B2r.csv").set_index("manc_type")
    out: dict = {}
    for mscreen in ("B1r", "A1"):
        b1 = pd.read_csv(P / f"{mscreen}.csv").set_index("manc_type")
        common = sorted(set(b1.index) & set(b2.index))
        sets = {"high_215": [t for t in common if mc.loc[t, "confidence"] == "high"], "all_310": common}
        out[mscreen] = {}
        for sname, types in sets.items():
            x = b1.loc[types]
            y = b2.loc[types]
            res = {}
            for thr in (0.2, 0.3, 0.4, 0.5, 0.6):
                dx, dy = x.score.to_numpy() >= thr, y.score.to_numpy() >= thr
                N, K, n, k = len(types), int(dy.sum()), int(dx.sum()), int((dx & dy).sum())
                cross = np.nanmean([oc(x.score_h1.to_numpy(), y.score_h2.to_numpy(), thr), oc(x.score_h2.to_numpy(), y.score_h1.to_numpy(), thr)])
                ceil = np.nanmean([oc(x.score_h1.to_numpy(), x.score_h2.to_numpy(), thr), oc(y.score_h1.to_numpy(), y.score_h2.to_numpy(), thr)])
                res[str(thr)] = {"drivers_manc": n, "drivers_malecns": K, "both": k, "expected": round(n * K / N, 2),
                                 "hypergeom_p_ge": round(float(hypergeom.sf(k - 1, N, K, n)), 4),
                                 "replication_rate_manc_hits": round(k / n, 3) if n else None,
                                 "OC_cross_halves": round(float(cross), 3), "OC_within_fly_ceiling": round(float(ceil), 3),
                                 "OC_ratio": round(float(cross / ceil), 3) if ceil else None}
            # graded replication
            s1, s2 = x.score.to_numpy(), y.score.to_numpy()
            d1 = s1 >= 0.5
            d2 = s2 >= 0.5
            rng = np.random.default_rng(7)
            boots_a, boots_b = [], []
            for _ in range(10000):
                i = rng.integers(0, len(types), len(types))
                boots_a.append(auroc(s2[i], d1[i]))
                boots_b.append(auroc(s1[i], d2[i]))
            ga = {"auroc_malecns_score_for_manc_drivers": round(auroc(s2, d1), 3),
                  "ci95": [round(float(np.nanpercentile(boots_a, 2.5)), 3), round(float(np.nanpercentile(boots_a, 97.5)), 3)],
                  "auroc_manc_score_for_malecns_drivers": round(auroc(s1, d2), 3),
                  "ci95_reverse": [round(float(np.nanpercentile(boots_b, 2.5)), 3), round(float(np.nanpercentile(boots_b, 97.5)), 3)]}
            # matched halves: cross-fly vs within-fly graded AUROC (drivers defined on one half, scored on another half)
            def g(a, b):
                return auroc(b, a >= 0.5)
            cross = np.nanmean([g(x.score_h1.to_numpy(), y.score_h2.to_numpy()), g(x.score_h2.to_numpy(), y.score_h1.to_numpy()),
                                g(y.score_h1.to_numpy(), x.score_h2.to_numpy()), g(y.score_h2.to_numpy(), x.score_h1.to_numpy())])
            within = np.nanmean([g(x.score_h1.to_numpy(), x.score_h2.to_numpy()), g(x.score_h2.to_numpy(), x.score_h1.to_numpy()),
                                 g(y.score_h1.to_numpy(), y.score_h2.to_numpy()), g(y.score_h2.to_numpy(), y.score_h1.to_numpy())])
            ga["halves_cross_fly_auroc"] = round(float(cross), 3)
            ga["halves_within_fly_auroc"] = round(float(within), 3)
            # mean B2r score of MANC drivers vs MANC non-drivers
            ga["mean_malecns_score_manc_drivers"] = round(float(s2[d1].mean()), 3)
            ga["mean_malecns_score_manc_nondrivers"] = round(float(s2[~d1].mean()), 3)
            ga["median_malecns_score_manc_drivers"] = round(float(np.median(s2[d1])), 3)
            out[mscreen][sname] = {"thresholds": res, "graded": ga}
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
