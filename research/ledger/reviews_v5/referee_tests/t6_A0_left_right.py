"""Referee test 6: where does the left-right gap in the authors' single-neuron screen (A0) sit?

Inputs (locked): pertype_v1/A0_copies.csv (the authors' per-copy scores, halves 0-63 / 64-127, usable counts),
predictions/S/types.csv (wiring summaries of the type, used only to split types; a cause of both copies' scores, so splitting
on it induces no collider bias), pertype_v1/A1.csv.
(a) The 13 types that are a driver on one side only: the other copy's score and usable count (a copy never accepted by the
    tuner scores 0 by rule).
(b) The draft's statistic (cross-half Spearman / split-half ceiling, over the 250 one-copy-per-side types) recomputed, then
    within halves of the types split by two-step unsigned path count (S3) and by direct motor-neuron synapses (S1), to see
    whether strongly connected types agree better.
(c) The same statistic with copies that have fewer than 64 of 128 usable replicates removed (both copies of the type).
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t6_A0_left_right.py
"""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")


def ratio(d):
    rx = np.mean([spearmanr(d.L1, d.R2).statistic, spearmanr(d.L2, d.R1).statistic])
    c = np.mean([spearmanr(d.L1, d.L2).statistic, spearmanr(d.R1, d.R2).statistic])
    return {"n": int(len(d)), "rho_x": round(float(rx), 3), "ceiling": round(float(c), 3), "ratio": round(float(rx / c), 3)}


def main():
    a = pd.read_csv(ROOT / "pertype_v1/A0_copies.csv")
    one = a[a.type_one_each_side]
    L = one[one.side == "L"].set_index("manc_type"); R = one[one.side == "R"].set_index("manc_type")
    t = sorted(set(L.index) & set(R.index))
    d = pd.DataFrame({"L": L.loc[t, "score"], "R": R.loc[t, "score"], "uL": L.loc[t, "n_usable"], "uR": R.loc[t, "n_usable"],
                      "L1": L.loc[t, "score_h1"], "L2": L.loc[t, "score_h2"], "R1": R.loc[t, "score_h1"], "R2": R.loc[t, "score_h2"]})
    S = pd.read_csv(ROOT / "predictions/S/types.csv").set_index("manc_type")
    d["S3"] = S.loc[d.index, "S3_twohop_abs"].astype(float); d["S1"] = S.loc[d.index, "S1_direct_mn"].astype(float)
    out = {"all_250": ratio(d)}
    disc = d[((d.L >= 0.5) ^ (d.R >= 0.5))]
    out["one_side_drivers"] = disc[["L", "R", "uL", "uR"]].round(3).reset_index().to_dict(orient="records")
    out["one_side_drivers_with_other_copy_under_64_usable"] = sorted(
        t for t in disc.index if (d.loc[t, "L"] >= 0.5 and d.loc[t, "uR"] < 64) or (d.loc[t, "R"] >= 0.5 and d.loc[t, "uL"] < 64))
    out["both_copies_below_0.05"] = int(((d.L < 0.05) & (d.R < 0.05)).sum())
    for col in ("S3", "S1"):
        med = d[col].median()
        out[f"{col}_above_median"] = ratio(d[d[col] > med])
        out[f"{col}_at_or_below_median"] = ratio(d[d[col] <= med])
    ok = d[(d.uL >= 64) & (d.uR >= 64)]
    out["usable_ge_64_both"] = ratio(ok)
    x, y = ok.L >= 0.5, ok.R >= 0.5
    out["usable_ge_64_both"]["drivers_L_R_both"] = [int(x.sum()), int(y.sum()), int((x & y).sum())]
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
