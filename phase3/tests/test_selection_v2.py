"""Selection and statistics of benchmark version 2 (review E B1, B3, B4, M4, M5)."""

from __future__ import annotations

import itertools

import numpy as np

from brainir_state.evaluate_cross import (holm, ni_p, paired_ratio_diff, profile_from_systems, rank_profiles, selection_bootstrap,
                                          sharing_comparison)


def _prof(**kw):
    base = {"S1_A_over_full": 1.0, "S2_C_heldout": 1.0, "S3_D_micro_gain": 0.0, "S4_E_ratio": 0.01, "S5_K_r2_rff": 0.9, "S6_dim_rate": 0.5,
            "S7_abstention": 0.5, "S8_sharing_correct": float("nan")}
    base.update(kw)
    return base


def test_ranks_do_not_depend_on_the_order_of_the_candidates():
    profs = {"a": _prof(), "b": _prof(), "c": _prof(S1_A_over_full=0.5), "d": _prof(S5_K_r2_rff=float("nan"))}
    ref = rank_profiles(profs)
    for perm in itertools.permutations(profs):
        r = rank_profiles({m: profs[m] for m in perm})
        assert r["mean_rank"] == ref["mean_rank"] and r["order"] == ref["order"]
    assert ref["mean_rank"]["a"] == ref["mean_rank"]["b"]              # identical profiles tie exactly
    assert "S8_sharing_correct" not in ref["components_used"]          # non-finite for every candidate: dropped
    assert ref["order"][0] == "c"


def test_strictly_better_candidate_wins_regardless_of_listing():
    x = _prof()
    y = _prof(S1_A_over_full=0.9, S2_C_heldout=0.9, S3_D_micro_gain=-0.1)
    for profs in ({"x": x, "y": y}, {"y": y, "x": x}):
        assert rank_profiles(profs)["order"][0] == "y"


def test_tie_break_by_fewer_transition_parameters():
    profs = {"big": _prof(), "small": _prof()}
    assert rank_profiles(profs, {"big": 1000, "small": 10})["order"] == ["small", "big"]


def _ok(c=0.5, a=1.1, k=0.9):
    return {"k": 2, "verdict": {"C": c, "D_micro_gain": 0.0, "E_ratio": 0.001, "E_testable": True}, "A_over_full": a,
            "K": {"r2_true_from_model_rff": k}, "K_dim": {"in_range": True}}


def test_failed_systems_count_as_worst_values():
    p = profile_from_systems({"s1": _ok(), "s2": _ok(), "s3": {"error": "timeout"}}, ["s1", "s2", "s3"],
                             {"abstention_recall": 1.0, "false_alarm_rate": 0.0}, [])
    q = profile_from_systems({"s1": _ok(), "s2": _ok()}, ["s1", "s2"], {"abstention_recall": 1.0, "false_alarm_rate": 0.0}, [])
    assert p["n_systems"] == 3 and p["S6_dim_rate"] < q["S6_dim_rate"]
    assert p["S1_A_over_full"] == 1.1                       # median of (1.1, 1.1, inf)
    bad = profile_from_systems({"s1": _ok(), "s2": {"error": "x"}, "s3": {"error": "x"}}, ["s1", "s2", "s3"], {}, [])
    assert np.isinf(bad["S1_A_over_full"]) and np.isinf(bad["S2_C_heldout"]) and bad["S5_K_r2_rff"] == -np.inf


def test_s8_is_balanced_between_groups_and_pairs():
    rows = [{"kind": "group", "correct": False}, {"kind": "group", "correct": False}] + [{"kind": "pair", "correct": True}] * 3
    assert profile_from_systems({}, [], {}, rows)["S8_sharing_correct"] == 0.5     # always rejecting earns 0.5, not 0.6


def test_holm_keeps_uncomputable_tests_and_ni_p_has_a_floor():
    h = holm({"a": 0.001, "b": float("nan")})
    assert h["b"] == 1.0 and abs(h["a"] - 0.002) < 1e-12
    assert ni_p(np.full(1999, -1.0), 0.1) == 1 / 2000      # (1 + 0) / (1 + B)
    assert ni_p(np.zeros(0), 0.1) == 1.0


def test_sharing_margins_are_on_the_scale_of_the_quantities():
    ua = {f"t{i}": 1.0 + 0.01 * i for i in range(20)}
    worse = {k: 1.5 * v for k, v in ua.items()}             # 50 % worse: not non-inferior at a 20 % margin (version 1 allowed 131 %)
    res = {"s": {"A": {"_units": {"A": worse}, "A": {"mean": 1.5}}, "C": {}}}
    ind = {"s": {"A": {"_units": {"A": ua}, "A": {"mean": 1.1}}, "C": {}}}
    comp = sharing_comparison(res, ind, {"total": 1, "reported": True}, {"total": 2, "reported": True}, 1.31, a_key="A", c_key="C")
    assert comp["per_system"]["s"]["A_noninferior"] is False
    assert paired_ratio_diff({"x": (1.0, 2.0, 0.0, "f")}, {"x": (1.0, 2.0, 0.0, "f")}, 50, 0)["diff"] == 0.0


def test_selection_bootstrap_reports_probabilities():
    rng = np.random.default_rng(0)
    per = {}
    sids = [f"s{i}" for i in range(12)]
    for m, shift in (("good", 0.0), ("bad", 0.5)):
        ps = {s: _ok(c=0.5 + shift + 0.1 * rng.standard_normal(), a=1.0 + shift, k=0.9 - shift) for s in sids}
        per[m] = {"per_system": ps, "profile": profile_from_systems(ps, sids, {"abstention_recall": 1.0, "false_alarm_rate": 0.0}, [])}
    b = selection_bootstrap(per, sids, n_boot=200, eliminate_fraction=0.5)
    assert b["good"]["p_rank1"] > 0.9 and b["bad"]["p_eliminated"] > 0.9
