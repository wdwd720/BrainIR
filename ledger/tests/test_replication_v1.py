"""PREREG v5 Part R on a synthetic per-type directory with hand-derived categories and overlaps."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import replication_v1 as R  # noqa: E402


def _whole(rows):
    return pd.DataFrame([{"manc_type": t, "screen": "x", "n_members": 2, "members_L": 1, "members_R": 1, "members_other": 0, "n_replicates": 16,
                          "n_usable": 16, "score": s, "score_h1": h1, "score_h2": h2, "frac_rhythmic": s, "band": "", "cross_fly_match": ""}
                         for t, s, h1, h2 in rows])


def _fixture(tmp: Path) -> Path:
    # types: A replicated, B near (B1r driver, B2r 0.4), C single MANC, D single MaleCNS, E stable non-driver, F neither,
    # G missing from one half-fly table (cannot be stable), H B1r only, I B2r only
    b1 = [("A", .9, .9, .9), ("B", .8, .8, .8), ("C", .7, .7, .1), ("D", .1, .1, .1), ("E", .0, .0, .0), ("F", .2, .2, .2), ("G", .0, .0, .0), ("H", .9, .9, .9)]
    b2 = [("A", .6, .6, .6), ("B", .4, .4, .4), ("C", .2, .2, .2), ("D", .9, .9, .1), ("E", .01, .0, .0), ("F", .1, .1, .1), ("G", .0, .0, .0), ("I", .9, .9, .9)]
    a1 = [("A", .9, .9, .9), ("B", .1, .1, .1), ("C", .6, .6, .6), ("D", .0, .0, .0), ("E", .0, .0, .0), ("F", .0, .0, .0), ("G", .0, .0, .0), ("H", .0, .0, .0)]
    _whole(b1).to_csv(tmp / "B1r.csv", index=False)
    _whole(b2).to_csv(tmp / "B2r.csv", index=False)
    _whole(a1).to_csv(tmp / "A1.csv", index=False)
    for h in R.HALF_FLY:
        types = ["A", "B", "C", "D", "E", "F"] + (["G"] if h != "MaleCNS_R" else [])
        pd.DataFrame([{"manc_type": t, "screen": h, "members_L": 1, "members_R": 0, "n_seeds": 16, "n_usable": 16, "score": 0.0 if t in "EG" else .5,
                       "score_h1": 0, "score_h2": 0, "frac_rhythmic": 0, "band": "", "primary_run4": True, "cross_fly_match": ""} for t in types]).to_csv(tmp / f"{h}.csv", index=False)
    conf = {"A": "high", "B": "high", "C": "low", "D": "medium", "E": "high", "F": "high", "G": "high", "I": "high"}
    pd.DataFrame([{"manc_type": t, "confidence": c} for t, c in conf.items()]).to_csv(tmp / "match_confidence.csv", index=False)
    pd.DataFrame([{"manc_type": "A", "bodyId": 1, "side": "L", "members_L": 1, "members_R": 1, "score": .8, "type_one_each_side": True},
                  {"manc_type": "A", "bodyId": 2, "side": "R", "members_L": 1, "members_R": 1, "score": .7, "type_one_each_side": True},
                  {"manc_type": "C", "bodyId": 3, "side": "L", "members_L": 1, "members_R": 1, "score": .8, "type_one_each_side": True},
                  {"manc_type": "C", "bodyId": 4, "side": "R", "members_L": 1, "members_R": 1, "score": .1, "type_one_each_side": True}]).to_csv(tmp / "A0_copies.csv", index=False)
    return tmp


def test_categories_and_overlap(tmp_path):
    T = R.tables(_fixture(tmp_path))
    c = R.categories(T, "B1r").set_index("manc_type")["category"].to_dict()
    assert c == {"A": "replicated", "B": "near_replicated", "C": "single_fly_manc", "D": "single_fly_malecns", "E": "stable_non_driver",
                 "F": "neither", "G": "neither"}
    o = R.overlap(T, "B1r")
    # common types A..G; B1r drivers {A,B,C}, B2r drivers {A,D}: J = 1/4
    assert o["n_types"] == 7 and o["n_both"] == 1 and abs(o["point"]["J_full"] - 0.25) < 1e-12
    assert abs(o["point"]["OC_full"] - 0.5) < 1e-12 and abs(o["point"]["rate_x_in_y"] - 1 / 3) < 1e-12 and abs(o["point"]["rate_y_in_x"] - 0.5) < 1e-12
    assert abs(o["J_max_for_these_sizes"] - 2 / 3) < 1e-12
    assert abs(o["expected_both_if_independent"] - 3 * 2 / 7) < 1e-12
    # halves: x1 {A,B,C}, x2 {A,B}; y1 {A,D}, y2 {A}: cross = (J(x1,y2)=1/3 + J(x2,y1)=1/3)/2; ceiling = (2/3 + 1/2)/2
    assert abs(o["point"]["J_cross_half"] - 1 / 3) < 1e-12 and abs(o["point"]["J_ceiling"] - 7 / 12) < 1e-12
    assert abs(o["point"]["J_ratio"] - (1 / 3) / (7 / 12)) < 1e-12
    # OC: x1 {A,B,C}, x2 {A,B}, y1 {A,D}, y2 {A}: OC(x1,y2) = 1/1, OC(x2,y1) = 1/2 -> 0.75; ceiling (OC(x1,x2) = 2/2 + OC(y1,y2) = 1/1)/2 = 1
    assert abs(o["point"]["OC_cross_half"] - 0.75) < 1e-12 and abs(o["point"]["OC_ceiling"] - 1.0) < 1e-12
    hi = R.categories(T, "B1r", ("high",))
    assert set(hi["manc_type"]) == {"A", "B", "E", "F", "G"}
    ca = R.categories(T, "A1").set_index("manc_type")["category"].to_dict()
    assert ca["A"] == "replicated" and ca["C"] == "single_fly_manc" and ca["D"] == "single_fly_malecns" and ca["B"] == "neither"
    assert R.one_fly_only(T)["B1r_only"] == [["H", 0.9]] and R.one_fly_only(T)["B2r_only"] == [["I", 0.9]]


def test_a0_concordance_and_bootstrap_is_seeded(tmp_path):
    T = R.tables(_fixture(tmp_path))
    a = R.a0_concordance(T)["copies_on_both_sides"]
    assert a["n_types"] == 2 and a["n_with_a_driver_copy"] == 2 and a["n_all_copies_drivers"] == 1
    assert [r["manc_type"] for r in a["concordant_types"]] == ["A"]
    o1, o2 = R.overlap(T, "B1r"), R.overlap(T, "B1r")
    assert o1["bootstrap_95"] == o2["bootstrap_95"]
    res = R.analyse(T)
    assert res["B1r_x_B2r"]["flagged_low_or_medium_match"] == {"single_fly_malecns": ["D"], "single_fly_manc": ["C"]}
    assert "POST HOC" in R.report_md(res).splitlines()[0]
    assert np.isfinite(res["B1r_x_B2r"]["all"]["overlap"]["point"]["J_ratio"])
