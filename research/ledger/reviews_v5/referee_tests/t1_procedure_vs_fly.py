"""Referee test 1: is the cross-fly disagreement larger than the disagreement between procedures in ONE fly?

Reads only locked per-type tables (predictions/*/types.csv, predictions_v2/*/types.csv, pertype_v1/match_confidence.csv).
For each pair of screens: driver counts, shared drivers, replication rates, overlap coefficient, Spearman of type scores,
and the AUROC with which screen Y's continuous score separates screen X's drivers from X's non-drivers (graded replication).
Pairs:
  same fly (MANC), different procedure: A1 (authors) vs B1 (ours, K=0), A1 vs B1r (ours, K=1), B1 vs B1r, B1 vs B1-alt,
  A1 vs A1-lo10;
  same fly (MaleCNS), different procedure: B2 (K=0) vs B2r (K=1);
  different fly, same procedure: B1 vs B2 (K=0), B1r vs B2r (K=1); different fly and procedure: A1 vs B2r.
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t1_procedure_vs_fly.py
"""
from __future__ import annotations

import itertools
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]  # research/ledger
OUT = Path(__file__).with_suffix(".out.json")


def load(arm: str) -> pd.Series:
    sub = "predictions_v2" if arm in ("B1r", "B2r") else "predictions"
    df = pd.read_csv(ROOT / sub / arm / "types.csv")
    return df.set_index("manc_type")["primary_score"].astype(float).fillna(0.0)


def auroc(pos: np.ndarray, neg: np.ndarray) -> float:
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def compare(x: pd.Series, y: pd.Series, types: list[str], thr: float = 0.5) -> dict:
    xs, ys = x.reindex(types), y.reindex(types)
    ok = xs.notna() & ys.notna()
    xs, ys = xs[ok], ys[ok]
    dx, dy = set(xs[xs >= thr].index), set(ys[ys >= thr].index)
    both = dx & dy
    n = len(xs)
    exp = len(dx) * len(dy) / n if n else float("nan")
    k = min(len(dx), len(dy))
    topx = set(xs.sort_values(ascending=False, kind="mergesort").index[:k]) if k else set()
    topy = set(ys.sort_values(ascending=False, kind="mergesort").index[:k]) if k else set()
    return {
        "n_types": int(n),
        "n_drivers_x": len(dx),
        "n_drivers_y": len(dy),
        "n_both": len(both),
        "expected_both_if_independent": round(exp, 2),
        "rate_x_in_y": round(len(both) / len(dx), 3) if dx else None,
        "rate_y_in_x": round(len(both) / len(dy), 3) if dy else None,
        "overlap_coefficient": round(len(both) / k, 3) if k else None,
        "spearman_scores": round(float(spearmanr(xs, ys).statistic), 3),
        "auroc_y_score_for_x_drivers": round(auroc(ys[list(dx)].to_numpy(), ys[[t for t in xs.index if t not in dx]].to_numpy()), 3),
        "auroc_x_score_for_y_drivers": round(auroc(xs[list(dy)].to_numpy(), xs[[t for t in ys.index if t not in dy]].to_numpy()), 3),
        "top_k_overlap_equal_size": f"{len(topx & topy)} of {k}",
        "shared_drivers": sorted(both),
    }


def main() -> None:
    arms = ["A1", "A1-lo10", "B1", "B1-alt", "B1r", "B2", "B2r"]
    s = {a: load(a) for a in arms}
    mc = pd.read_csv(ROOT / "pertype_v1" / "match_confidence.csv").set_index("manc_type")
    manc_types = set(s["A1"].index)
    common_all = sorted(manc_types & set(s["B2r"].index))
    common_high = sorted(t for t in common_all if mc.loc[t, "confidence"] == "high")
    manc_only = sorted(manc_types)
    pairs = [
        ("same fly MANC, authors vs ours K=0", "A1", "B1", "manc"),
        ("same fly MANC, authors vs ours K=1", "A1", "B1r", "manc"),
        ("same fly MANC, ours K=0 vs K=1", "B1", "B1r", "manc"),
        ("same fly MANC, ours lower bound 10 vs 5", "B1", "B1-alt", "manc"),
        ("same fly MANC, authors usable rule 5 vs 10", "A1", "A1-lo10", "manc"),
        ("same fly MaleCNS, ours K=0 vs K=1", "B2", "B2r", "common"),
        ("two flies, ours K=0", "B1", "B2", "common"),
        ("two flies, ours K=1 (the draft's B1r x B2r)", "B1r", "B2r", "common"),
        ("two flies and procedures, A1 x B2r", "A1", "B2r", "common"),
        ("two flies and procedures, A1 x B2 (K=0)", "A1", "B2", "common"),
    ]
    out: dict = {"inputs": "predictions/{A1,A1-lo10,B1,B1-alt,B2}/types.csv, predictions_v2/{B1r,B2r}/types.csv (primary_score), "
                 "pertype_v1/match_confidence.csv", "threshold": 0.5, "results": {}}
    for label, a, b, scope in pairs:
        if scope == "manc":
            sets = {"all_321_manc_types": manc_only,
                    "high_conf_215": common_high}
        else:
            sets = {"all_310_common": common_all, "high_conf_215": common_high}
        out["results"][f"{label}: {a} x {b}"] = {k: compare(s[a], s[b], v) for k, v in sets.items()}
    # threshold sensitivity for the draft's comparison and the same-fly procedure comparison
    thr = {}
    for t in (0.3, 0.4, 0.5, 0.6):
        thr[str(t)] = {
            "B1r x B2r high": {k: compare(s["B1r"], s["B2r"], common_high, t)[k] for k in ("n_drivers_x", "n_drivers_y", "n_both", "expected_both_if_independent", "rate_x_in_y", "overlap_coefficient")},
            "A1 x B1r high": {k: compare(s["A1"], s["B1r"], common_high, t)[k] for k in ("n_drivers_x", "n_drivers_y", "n_both", "expected_both_if_independent", "rate_x_in_y", "overlap_coefficient")},
            "B2 x B2r high": {k: compare(s["B2"], s["B2r"], common_high, t)[k] for k in ("n_drivers_x", "n_drivers_y", "n_both", "expected_both_if_independent", "rate_x_in_y", "overlap_coefficient")},
        }
    out["threshold_sensitivity"] = thr
    # DNg100 and DNb08 in every arm
    out["DNg100_DNb08"] = {a: {t: round(float(s[a].get(t, np.nan)), 3) for t in ("DNg100", "DNb08")} for a in arms}
    OUT.write_text(json.dumps(out, indent=1))
    for k, v in out["results"].items():
        for sk, r in v.items():
            print(f"{k} [{sk}]: drivers {r['n_drivers_x']}/{r['n_drivers_y']}, both {r['n_both']} (exp {r['expected_both_if_independent']}),"
                  f" rate x->y {r['rate_x_in_y']}, OC {r['overlap_coefficient']}, rho {r['spearman_scores']},"
                  f" AUROC(y|x drivers) {r['auroc_y_score_for_x_drivers']}, AUROC(x|y drivers) {r['auroc_x_score_for_y_drivers']},"
                  f" top-k {r['top_k_overlap_equal_size']}")
    print(json.dumps(out["threshold_sensitivity"], indent=1))
    print(json.dumps(out["DNg100_DNb08"]))


if __name__ == "__main__":
    main()
