"""Referee test 5: exam 1 with the size confound removed (exploratory, post hoc).

Inputs (locked): results/run2/scorecard.csv (primary set and labels), predictions/A1/types.csv, predictions/S/types.csv.
(a) Spearman of the model score (A1) and of two-step signed counting (S2) with the type's two-step unsigned path count (S3, a
    size measure) over A1's 321 types and over the 39 exam types.
(b) Size-stratified AUROC: yes/no pairs are compared only within the same S3 stratum (halves and tertiles over the 39 types),
    pooled over strata (Mantel-Haenszel-style pair counting), for A1, S2 and S7; with a 10,000-resample bootstrap of types
    within label (default_rng(11)) for the difference A1 - S2. Strata are re-cut in every resample.
    (A rank-residual adjustment was tried and dropped: A1 has 25 ties at exactly 0 among the 39, and any residualisation
    breaks those ties by S3, which itself separates the labels; the stratified version keeps ties as ties.)
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t5_exam1_size_adjusted.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata, spearmanr

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")


def pairs(score, y):
    pos, neg = score[y == 1], score[y == 0]
    gt = (pos[:, None] > neg[None, :]).sum(); eq = (pos[:, None] == neg[None, :]).sum()
    return gt + 0.5 * eq, len(pos) * len(neg)


def strat_auroc(score, y, size, k):
    q = pd.qcut(rankdata(size, method="ordinal"), k, labels=False)
    num = den = 0.0
    for s in range(k):
        m = q == s
        a, b = pairs(score[m], y[m]); num += a; den += b
    return (num / den if den else np.nan), den, q


def main():
    sc = pd.read_csv(ROOT / "results/run2/scorecard.csv")
    ps = sc[sc["in_primary_set"]].set_index("manc_type")
    y = (ps["front"] == "yes").astype(int).to_numpy()
    S = pd.read_csv(ROOT / "predictions/S/types.csv").set_index("manc_type")
    A1 = pd.read_csv(ROOT / "predictions/A1/types.csv").set_index("manc_type")["primary_score"].astype(float)
    full = pd.DataFrame({"A1": A1, "S2": S["S2_twohop_signed"].astype(float), "S3": S["S3_twohop_abs"].astype(float),
                         "S4": S["S4_total_out"].astype(float), "S7": S["S7_n_members"].astype(float)})
    d = full.loc[ps.index]
    out = {"spearman_321": {f"A1_vs_{c}": round(float(spearmanr(full.A1, full[c]).statistic), 3) for c in ("S2", "S3", "S4")},
           "spearman_39": {f"A1_vs_{c}": round(float(spearmanr(d.A1, d[c]).statistic), 3) for c in ("S2", "S3", "S4")}}
    out["spearman_39"]["S2_vs_S3"] = round(float(spearmanr(d.S2, d.S3).statistic), 3)
    out["unadjusted_auroc"] = {c: round(pairs(d[c].to_numpy(), y)[0] / pairs(d[c].to_numpy(), y)[1], 3) for c in ("A1", "S2", "S3", "S7")}
    rng = np.random.default_rng(11)
    pos_i, neg_i = np.where(y == 1)[0], np.where(y == 0)[0]
    res = {}
    for k in (2, 3):
        row = {}
        for c in ("A1", "S2", "S7"):
            a, den, q = strat_auroc(d[c].to_numpy(), y, d.S3.to_numpy(), k)
            row[c] = round(float(a), 3)
        row["strata_composition"] = [f"{int(y[q == s].sum())} yes/{int((1 - y[q == s]).sum())} no" for s in range(k)]
        row["n_within_stratum_pairs"] = int(den)
        diffs = []
        for _ in range(10000):
            i = np.concatenate([rng.choice(pos_i, len(pos_i)), rng.choice(neg_i, len(neg_i))])
            yy, ss = y[i], d.S3.to_numpy()[i]
            a1 = strat_auroc(d.A1.to_numpy()[i], yy, ss, k)[0]
            s2 = strat_auroc(d.S2.to_numpy()[i], yy, ss, k)[0]
            diffs.append(a1 - s2)
        row["A1_minus_S2"] = round(row["A1"] - row["S2"], 3)
        row["A1_minus_S2_ci95"] = [round(float(np.nanpercentile(diffs, 2.5)), 3), round(float(np.nanpercentile(diffs, 97.5)), 3)]
        res[f"S3_{k}_strata"] = row
    out["size_stratified_auroc"] = res
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
