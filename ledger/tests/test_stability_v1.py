"""PREREG v5 Part S statistics on hand-derived examples (no simulation)."""

from __future__ import annotations

import sys
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import stability_v1 as S  # noqa: E402


def test_exact_test_counts_ties():
    vals = {"a": 1.0, "b": 1.0, "c": 1.0, "d": 0.5, "e": 0.0}
    r = S.exact_test(vals, ["a", "b", "c"])
    assert r["n_subsets"] == comb(5, 3) and r["n_subsets_ge"] == 1 and abs(r["p"] - 1 / 10) < 1e-12
    vals["d"] = 1.0  # four tied at the top (midrank 3.5 each): C(4,3) subsets reach the observed rank sum
    r = S.exact_test(vals, ["a", "b", "c"])
    assert r["n_subsets_ge"] == 4 and abs(r["p"] - 4 / 10) < 1e-12 and abs(r["observed_rank_sum"] - 10.5) < 1e-12
    assert S.exact_test(vals, [])["p"] is None


def test_rank_test_differs_from_mean_test_when_values_skewed():
    # R = {a, e}: values 1.0 and 0.0; ranks 5 and 1 -> rank sum 6; subsets of size 2 with rank sum >= 6: (5,4),(5,3),(5,2),(5,1),(4,3),(4,2) = 6 of 10
    vals = {"a": 1.0, "b": 0.3, "c": 0.2, "d": 0.1, "e": 0.0}
    r = S.exact_test(vals, ["a", "e"])
    assert r["n_subsets_ge"] == 6 and abs(r["p"] - 0.6) < 1e-12


def test_min_p_table_matches_prereg():
    t = S.min_p_table(15, 3)
    assert abs(t["3"] - 1 / 455) < 1e-12 and abs(t["6"] - 20 / 455) < 1e-12 and t["7"] > 0.05 > t["6"]
    assert abs(S.min_p_table(11, 3)["3"] - 1 / 165) < 1e-12


def test_copy_scores_and_stability():
    res = []
    for c in (1, 2):
        for s in range(8):
            res.append({"key": f"PS-c{c:02d}|X|s{s}", "usable": True, "score": 0.9 if c == 1 else 0.2})
            res.append({"key": f"PS-c{c:02d}|Y|s{s}", "usable": s < 4, "score": 0.8})
    d = S.copy_scores(res, n_copies=2)
    st = S.stability(d)
    assert st.loc["X", "stability"] == 0.5 and abs(st.loc["X", "mean_copy_score"] - 0.55) < 1e-12
    assert st.loc["Y", "stability"] == 1.0 and abs(st.loc["Y", "mean_copy_score"] - 0.8) < 1e-12


def test_clopper_pearson_bounds():
    lo, hi = S.clopper_pearson(0, 40)
    assert lo == 0.0 and 0.08 < hi < 0.09
    lo, hi = S.clopper_pearson(40, 40)
    assert hi == 1.0 and 0.91 < lo < 0.92


def test_copy_scores_errors_and_fraction_rhythmic():
    res = [{"key": f"PS-c01|X|s{s}", "usable": True, "score": 0.9} for s in range(6)]
    res += [{"key": "PS-c01|X|s6", "error": "boom"}, {"key": "PS-c01|X|s7", "usable": False, "score": 0.9}]
    d = S.copy_scores(res, n_copies=1)
    r = d.iloc[0]
    assert r["n_errors"] == 1 and r["n_usable"] == 6 and abs(r["copy_score"] - 0.9) < 1e-12 and abs(r["frac_rhythmic"] - 6 / 8) < 1e-12
