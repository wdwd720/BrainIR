"""Statistics helpers, per-system verdicts, the Phase 4 conclusion rule and the primary family (PROTOCOL sections 9 and 11), with
hand-derived cases and the regression tests of the early reviews E / H that concern these modules."""

from __future__ import annotations

import numpy as np
import pytest

from brainir_causal import stats as S
from brainir_causal.verdict import (
    CATEGORY_ORDER,
    DECLARED,
    PARTIAL,
    SUPPORTED,
    UNSUPPORTED,
    Tolerances,
    build_primary_family,
    category_rank,
    diagnose,
    dimension_status,
    phase4_conclusion,
    primary_family,
    system_verdict,
)

TOL = Tolerances(delta_A=0.1, delta_C=0.05, tau_SMS=0.1, tau_ICG=0.1, tau_MEV=0.3, delta_H=0.1, tau_FC=0.2)


def _e(point, lo, hi):
    return {"point": point, "ci95": [lo, hi]}


def _good():
    return {"EE": _e(0.2, 0.15, 0.25), "EE_vs_idshortcut": _e(-0.3, -0.4, -0.2), "EE_vs_fullbound": _e(0.0, -0.02, 0.03),
            "SMS": _e(0.02, 0.0, 0.05), "ICG_y": _e(0.01, 0.0, 0.04), "MEV": _e(0.1, 0.05, 0.2), "MEV_testable": True, "MEV_rho": 0.05,
            "MEV_k": 3, "dimension": {"compact": True, "stable": True}, "false_confidence": {"rate": 0.05, "n": 40},
            "EE_heldout": _e(0.3, 0.2, 0.4), "EE_infamily": _e(0.25, 0.2, 0.3),
            "EE_by_class": {"moderate": {"point": 0.2}, "strong": {"point": 0.15}, "weak": {"point": 0.25}}}   # A's class condition


# ------------------------------------------------------------------------------------------------------------ stats
def test_holm_matches_hand_computation():
    h = S.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h["adjusted"] == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})
    assert h["reject"] == {"a": True, "b": False, "c": False}
    assert S.holm([0.2, None])["adjusted"][1] == 1.0          # a missing test stays in the family with p = 1


def test_ratio_of_sums_and_cluster_invariance():
    num, den = np.array([1.0, 2.0, 3.0, 4.0]), np.array([2.0, 2.0, 2.0, 2.0])
    assert S.boot_ratio(num, den, n_boot=50).point == pytest.approx(10.0 / 8.0)
    e1 = S.boot_mean(np.arange(10.0), groups=np.arange(10), n_boot=500, seed=1)
    e2 = S.boot_mean(np.repeat(np.arange(10.0), 3), groups=np.repeat(np.arange(10), 3), n_boot=500, seed=1)
    assert e1.point == pytest.approx(e2.point) and e1.n_units == e2.n_units == 10
    assert e2.ci95 == pytest.approx(e1.ci95)


def test_one_sided_noninferiority_uses_one_alpha_convention():
    """Review E, B7: the decision is the one-sided p <= alpha, and the reported bound is the one-sided 95 % bound."""
    d = S.boot_mean_diff(np.full(30, 0.0), np.full(30, 1.0), n_boot=200)
    r = S.noninferiority(d, 0.1)
    assert r["pass"] and r["p"] == pytest.approx(1 / 201) and r["upper_one_sided"] == pytest.approx(-1.0)
    rng = np.random.default_rng(3)
    for mu in (-0.2, -0.1, 0.0, 0.1):
        est = S.boot_mean(rng.normal(mu, 1.0, 60), n_boot=1000, seed=2)
        r = S.noninferiority(est, 0.05)
        assert r["pass"] == (r["p"] <= 0.05)
        assert r["pass"] == (r["upper_one_sided"] < 0.05) or abs(r["upper_one_sided"] - 0.05) < 0.02


def test_nonfinite_replicates_count_against_the_claim():
    """Review E minor / H minor 7: percentile_ci never drops non-finite replicates silently."""
    reps = np.r_[np.linspace(0.0, 1.0, 95), [np.nan] * 5]
    lo, hi = S.percentile_ci(reps)
    assert lo == -np.inf and hi == np.inf
    assert S.one_sided_upper(np.r_[np.zeros(99), np.nan], 0.95) == 0.0
    assert S.one_sided_upper(np.r_[np.zeros(90), [np.nan] * 10], 0.95) == np.inf
    est = S.make_estimate(0.5, reps, 10)
    assert est.n_nonfinite_reps == 5


def test_rescaled_stratified_bootstrap_is_not_anticonservative():
    """Review E, B6: with 2 systems per stratum, plain within-stratum resampling shrinks the variance by 1/2; the rescaled bootstrap
    restores the unbiased stratum variance."""
    rng = np.random.default_rng(0)
    vals = {f"s{i}": float(rng.normal()) for i in range(40)}
    strata = {f"s{i}": f"t{i // 2}" for i in range(40)}
    resc = S.stratified_system_boot(vals, strata, np.mean, 4000, 1)
    v = np.array([vals[f"s{i}"] for i in range(40)])
    within = np.array([np.var(v[2 * t: 2 * t + 2], ddof=1) for t in range(20)])
    expected_sd = np.sqrt((4.0 * within.sum() / 2.0) / 1600.0)          # sum_h n_h^2 s_h^2 / n_h / n^2 with n_h = 2, n = 40
    assert np.std(resc.reps) == pytest.approx(expected_sd, rel=0.08)


def test_singleton_strata_are_merged():
    assert S.merge_small_strata(["a", "a", "b", "c"]) == ["a", "a", "~merged", "~merged"]
    assert S.merge_small_strata(["a", "a", "a", "b"]) == ["a", "a", "a", "a"]
    e = S.stratified_system_boot({"x": 1.0, "y": 0.0, "z": 1.0}, {"x": "p", "y": "q", "z": "r"}, n_boot=200)
    assert e.ci95[1] > e.ci95[0]                                   # never a zero-width CI from strata of size 1


def test_paired_system_boot_charges_failures():
    """Review E, M7: a failed or missing system is charged the worst admissible value, never dropped."""
    a = {"s1": 0.2, "s2": float("nan"), "s3": 0.3}
    b = {"s1": 0.4, "s2": 0.4, "s3": 0.4, "s4": 0.4}
    e = S.paired_system_boot(a, b, None, 200, 0, worst=10.0)
    assert e.n_charged == 2 and e.point == pytest.approx(np.mean([-0.2, 9.6, -0.1, 9.6]))
    e0 = S.paired_system_boot(a, b, None, 200, 0)
    assert e0.n_units == 2 and e0.n_dropped == 2


def test_clopper_pearson_one_sided():
    from scipy.stats import beta
    assert S.clopper_pearson_lower(18, 30, 0.975) == pytest.approx(beta.ppf(0.025, 18, 13))
    assert S.clopper_pearson_lower(0, 30) == 0.0


def test_class_balanced_ratio_and_two_stage_weights():
    """Class-balanced EE (review E, M1) and the two-stage family -> cell design (review E, M2)."""
    design = S.CellDesign.build(["c1", "c1", "c2", "c3"], ["strong", "strong", "weak", "weak"], ["f1", "f1", "f1", "f2"])
    num, den = np.array([1.0, 1.0, 9.0, 1.0]), np.array([10.0, 10.0, 10.0, 10.0])
    e = S.boot_class_balanced(num, den, design, n_boot=300)
    assert e.point == pytest.approx(np.mean([2 / 20, 10 / 20])) and e.n_units == 3
    W = design.weights(500, 1, "family_cell")
    assert W.shape == (500, 3) and np.all(W.sum(1) > 0)
    Wc = design.weights(500, 1, "class")
    assert np.all(Wc[:, design.cell_class == design.classes.index("strong")].sum(1) == 1)


# ------------------------------------------------------------------------------------------------------------ verdicts
def test_all_criteria_pass():
    v = system_verdict(_good(), TOL)
    assert v["category"] == SUPPORTED
    assert all(c["pass"] for c in v["criteria"].values())


def test_untestable_mev_does_not_satisfy_E():
    """Review E, B4: an untestable MEV is not "supported (E untested)"; E fails and the model is at most PARTIAL."""
    m = _good()
    m["MEV_testable"], m["MEV_rho"], m["MEV_k"] = False, 0.24, 6
    v = system_verdict(m, TOL)
    assert v["criteria"]["E"]["pass"] is False and "E untestable" in v["criteria"]["E"]["note"]
    assert v["category"] == PARTIAL and v["untestable"] == ["E"]
    failing = system_verdict({**_good(), "MEV": _e(0.5, 0.4, 0.6)}, TOL)
    assert category_rank(v["category"]) == category_rank(failing["category"])     # never better than a failing MEV


def test_partial_and_unsupported():
    m = _good()
    m["EE_vs_fullbound"] = _e(0.3, 0.2, 0.4)
    assert system_verdict(m, TOL)["category"] == PARTIAL
    m["SMS"], m["ICG_y"], m["EE_heldout"] = _e(0.5, 0.4, 0.6), _e(0.5, 0.4, 0.6), _e(0.95, 0.9, 1.0)
    assert system_verdict(m, TOL)["category"] == UNSUPPORTED
    m = _good()
    m["EE"] = _e(0.95, 0.9, 1.0)
    assert system_verdict(m, TOL)["category"] == UNSUPPORTED


def test_non_binding_criteria_do_not_block():
    # a non-binding ICG part does not block (D and the MEV part of E bind)
    tol = Tolerances(**{**TOL.as_dict(), "icg_binds": False})
    m = _good()
    m["ICG_y"] = _e(0.5, 0.4, 0.6)
    v = system_verdict(m, tol)
    assert v["category"] == SUPPORTED and v["criteria"]["E"]["icg_binding"] is False and v["not_binding"] == []
    # review E round 3, N-new-2: without a binding mediation criterion D, "causal state supported" cannot be issued
    tol = Tolerances(**{**TOL.as_dict(), "sms_binds": False, "icg_binds": False})
    m["SMS"] = _e(0.5, 0.4, 0.6)
    v = system_verdict(m, tol)
    assert v["category"] == PARTIAL and v["all_binding_criteria_hold"] and "N-new-2" in v["supported_blocked"]
    assert v["criteria"]["D"]["binding"] is False and v["not_binding"] == ["D"]
    # ... nor without a binding closure part of E
    v = system_verdict(_good(), Tolerances(**{**TOL.as_dict(), "icg_binds": False, "mev_binds": False}))
    assert v["category"] == PARTIAL and v["all_binding_criteria_hold"]


def test_missing_inputs_block_supported():
    m = _good()
    del m["EE_vs_idshortcut"]
    v = system_verdict(m, TOL)
    assert v["criteria"]["B"]["pass"] is None and v["category"] == PARTIAL and v["missing"] == ["B"]
    m = _good()
    del m["ICG_y"]
    assert system_verdict(m, TOL)["criteria"]["E"]["pass"] is None
    m = _good()
    del m["MEV"], m["MEV_testable"]
    v = system_verdict(m, TOL)
    assert v["criteria"]["E"]["mev_state"] == "missing" and v["category"] == PARTIAL
    m = _good()
    del m["EE_infamily"]
    assert system_verdict(m, TOL)["criteria"]["H"]["pass"] is None
    m = _good()
    del m["EE"]
    assert system_verdict(m, TOL)["category"] == UNSUPPORTED


def test_unusable_items_fail_D_and_E():
    """Review E, B3: a mediation / closure result that failed on unusable items fails D / E."""
    m = _good()
    m["SMS"] = {"point": 1.0, "ci95": [1.0, 1.0], "failed": True}
    v = system_verdict(m, TOL)
    assert v["criteria"]["D"]["pass"] is False and v["category"] == PARTIAL
    m = _good()
    m["ICG_y"] = {"point": 1.0, "ci95": [1.0, 1.0], "failed": True}
    assert system_verdict(m, TOL)["criteria"]["E"]["pass"] is False


def test_declared_no_compact_state_is_recorded():
    m = _good()
    m["declared_no_compact"], m["truth_noncompressible"] = True, True
    v = system_verdict(m, TOL)
    assert v["category"] == DECLARED and v["declaration_correct"] is True
    m["truth_noncompressible"] = False
    assert system_verdict(m, TOL)["declaration_correct"] is False
    assert category_rank(DECLARED) == category_rank(UNSUPPORTED)


def test_category_order():
    assert CATEGORY_ORDER == (SUPPORTED, PARTIAL, UNSUPPORTED)
    assert category_rank(SUPPORTED) > category_rank(PARTIAL) > category_rank(UNSUPPORTED)


def test_false_confidence_without_claims_passes():
    m = _good()
    m["false_confidence"] = {"rate": float("nan"), "n": 0}
    assert system_verdict(m, TOL)["criteria"]["G"]["pass"] is True


def test_mechanism_systems_judged_on_stability_only():
    m = _good()
    m["dimension"] = {"compact": None, "stable": True}
    assert system_verdict(m, TOL, compact_judged=False)["category"] == SUPPORTED
    assert system_verdict(m, TOL, compact_judged=True)["criteria"]["F"]["pass"] is None


def test_dimension_status_levels():
    """PROTOCOL 5.10 (review E, M5): Level B over the 3 fit seeds, Level C over the 5 refits; F is computable on both paths."""
    d = dimension_status(3, 10, [3, 3, 3, 3, 4], (3, 4), level="C")
    assert d["compact"] and d["stable"] and d["modal_k"] == 3
    d = dimension_status(3, 10, [2, 3, 4, 3, 2], (2, 4), level="C")
    assert d["stable"] is False and d["unresolved"] == [2, 4]
    assert dimension_status(3, 10, [3, 3, 3, 3, 4], None, level="C")["stable"] is False     # no range: every refit equal
    assert dimension_status(3, 10, [3, 3, 3], None, level="B")["stable"] is True
    assert dimension_status(3, 10, [3, 4, 3], (3, 4), level="B")["stable"] is True
    assert dimension_status(3, 10, [3, 4, 3], None, level="B")["stable"] is False
    assert dimension_status(3, None)["compact"] is None and dimension_status(3, 10)["stable"] is None
    v = system_verdict({**_good(), "dimension": dimension_status(3, 10, [3, 3, 3], (3, 3), level="B")}, TOL)
    assert v["criteria"]["F"]["pass"] is True and v["category"] == SUPPORTED


# ------------------------------------------------------------------------------------------------------------ conclusion
def _syn(n_comp=24, frac_m=1.0, frac_t=1.0, nc_declared=True):
    method, true, comp = {}, {}, {}
    for i in range(n_comp):
        s = f"c{i}"
        method[s] = SUPPORTED if i < frac_m * n_comp else UNSUPPORTED
        true[s] = SUPPORTED if i < frac_t * n_comp else UNSUPPORTED
        comp[s] = True
    for i in range(3):
        s = f"n{i}"
        method[s] = DECLARED if nc_declared else UNSUPPORTED
        true[s] = UNSUPPORTED
        comp[s] = False
    return {"method": method, "truestate": true, "compressible": comp}


def test_conclusion_supported_partial_unsupported():
    real_ok = {"full": {"rA": SUPPORTED, "rB": SUPPORTED, "rC": SUPPORTED}, "lineage": {"rA": "L1", "rB": "L1", "rC": "L2"}}
    c = phase4_conclusion(_syn(), real_ok, n_boot=300)
    assert c["phase4"] == "compact causal state supported"
    c = phase4_conclusion(_syn(), {"full": {"rA": SUPPORTED, "rB": UNSUPPORTED, "rC": UNSUPPORTED}}, n_boot=300)
    assert c["real"]["status"] == "PARTIAL" and c["phase4"] == "partially supported"
    c = phase4_conclusion(_syn(frac_m=0.0), {"full": {"rA": UNSUPPORTED}}, n_boot=300)
    assert c["phase4"] == "unsupported"


def test_conclusion_uses_clopper_pearson_lower_bound():
    """Review E, B6: P_m's lower bound is the one-sided 97.5 % Clopper-Pearson bound (not a stratified bootstrap)."""
    syn = _syn(n_comp=30, frac_m=0.7)
    c = phase4_conclusion(syn, None, n_boot=300)
    assert c["synthetic"]["P_m_lower_cp975"] == pytest.approx(S.clopper_pearson_lower(21, 30, 0.975))
    assert c["synthetic"]["status"] == "PARTIAL"                  # 21/30 supported: CP lower bound 0.51 >= 0.5 but P_m - P_t < -0.2
    syn2 = _syn(n_comp=30, frac_m=0.7, frac_t=0.7)
    c2 = phase4_conclusion(syn2, None, n_boot=300)
    assert c2["synthetic"]["status"] == "SUPPORTED"


def test_conclusion_not_attainable_and_calibration_cap():
    c = phase4_conclusion(_syn(frac_m=1.0, frac_t=0.25), None, n_boot=300)
    assert c["synthetic"]["criteria_attainable_with_true_state"] is False and c["synthetic"]["status"] != "SUPPORTED"
    c = phase4_conclusion(_syn(), None, n_boot=300, synthetic_capped_at_partial=True)
    assert c["synthetic"]["status"] == "PARTIAL"


def test_conclusion_requires_correct_abstention_on_controls():
    c = phase4_conclusion(_syn(nc_declared=False), None, n_boot=300)
    assert c["synthetic"]["status"] == "PARTIAL"


# ------------------------------------------------------------------------------------------------------------ primary family
def _net_estimates(good: bool, n_boot: int = 400):
    rng = np.random.default_rng(1 if good else 2)
    out = {}
    for h, (c, sd) in {"H1": (0.3, 0.05), "H2": (-0.3, 0.05), "H3": (0.0, 0.01), "H4": (0.02, 0.01), "H5": (0.4, 0.05),
                       "H6": (-0.1, 0.02)}.items():
        c = c if good else c + 1.0
        out[h] = S.Estimate(c, [c - 2 * sd, c + 2 * sd], 40, rng.normal(c, sd, n_boot))
    return out


def test_build_primary_family_has_24_tests_and_holm():
    """Review E, B7: the 24-test table of PROTOCOL 11 (6 hypotheses x (suite + 3 real full networks)), one-sided, Holm."""
    margins = {"delta_A": 0.1, "delta_C": 0.05, "tau_SMS": 0.1, "delta_NI": 0.05, "delta_C_suite": 0.05, "tau_SMS_suite": 0.05}
    with pytest.raises(ValueError, match="suite margins"):           # review E, N9: the suite tests need the suite margins
        build_primary_family({"systems": ["s0"], "values": {}}, {}, {k: v for k, v in margins.items() if "suite" not in k}, n_boot=50)
    systems = [f"s{i}" for i in range(20)]
    rng = np.random.default_rng(0)
    values = {"H1": {s: float(rng.uniform(0.1, 0.4)) for s in systems}, "H2": {s: -0.2 for s in systems},
              "H3": {s: 0.0 for s in systems}, "H4": {s: 0.01 for s in systems}, "H5": {s: 0.4 for s in systems},
              "H6": {s: -0.1 for s in systems}}
    values["H1"]["s3"] = float("nan")                             # a failed system: charged the worst value (EE 10)
    fam = build_primary_family({"systems": systems, "values": values}, {"netA": _net_estimates(True), "netB": _net_estimates(True),
                                                                        "netC": _net_estimates(False)}, margins, n_boot=500)
    assert fam["m"] == 24 == fam["expected_m"]
    assert fam["tests"]["suite:H1"]["n_charged"] == 1
    assert all(fam["tests"][f"netA:{h}"]["reject_holm"] for h in ("H1", "H2", "H3", "H4", "H5", "H6"))
    assert not any(fam["tests"][f"netC:{h}"]["reject_holm"] for h in ("H1", "H2", "H3", "H4", "H5", "H6"))
    assert fam["tests"]["suite:H2"]["reject_holm"] and fam["tests"]["suite:H1"]["p_holm"] >= fam["tests"]["suite:H1"]["p"]
    fam2 = build_primary_family(None, {"netA": {}}, margins, n_boot=200)
    assert fam2["m"] == 6 and all(r["p"] == 1.0 for r in fam2["tests"].values())


def test_primary_family_generic_and_diagnosis():
    d_good = S.boot_mean_diff(np.zeros(40), np.ones(40), n_boot=200)
    d_bad = S.boot_mean_diff(np.ones(40), np.zeros(40), n_boot=200)
    fam = primary_family({"A": {"diff": d_good, "margin": 0.1}, "B": {"diff": d_bad, "margin": 0.1}, "C": {"diff": None}})
    assert fam["tests"]["A"]["reject_holm"] and not fam["tests"]["B"]["reject_holm"] and fam["tests"]["C"]["p"] == 1.0
    assert diagnose({"fullstate_predicts": True, "compact_predicts": False})[0].startswith("A:")


def test_the_compactness_limit_carries_the_draw_allowance_on_synthetic_systems():
    """PROTOCOL 5.10 / LOG P4-D62: compact = k <= max(1, N_obs / 5) + d_draw on synthetic systems (a draw-closed state carries up to
    d_draw static coordinates); the true state [z, draw] is compact iff k_true <= the bound. Real systems and systems without a
    recorded d_draw keep the limit; mechanisms are never judged."""
    from brainir_causal.verdict import compact_limit_given_truth
    lim, note = compact_limit_given_truth(4, "synthetic", 2, 3)
    assert lim == 7 and "allowance 3" in note                                              # true state 2 + 3 <= 7: compact
    assert compact_limit_given_truth(4, "synthetic", "none", 9)[0] == 13                  # the allowance applies to every type
    assert compact_limit_given_truth(4, "real", 2, 9) == (4, None)                        # real systems: no truth rule
    assert compact_limit_given_truth(4, "synthetic", 2, None) == (4, None)                # no draw dimension recorded
    assert compact_limit_given_truth(None, "synthetic", 2, 3) == (None, None)            # mechanisms: never judged
