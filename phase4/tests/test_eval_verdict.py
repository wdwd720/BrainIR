"""Statistics helpers, per-system verdicts and the Phase 4 conclusion rule (PROTOCOL sections 9 and 11), with hand-derived cases."""

from __future__ import annotations

import numpy as np
import pytest

from brainir_causal import stats as S
from brainir_causal.verdict import (
    DECLARED,
    PARTIAL,
    SUPPORTED,
    SUPPORTED_E_UNTESTED,
    UNSUPPORTED,
    Tolerances,
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
            "SMS": _e(0.02, 0.0, 0.05), "ICG_y": _e(0.01, 0.0, 0.04), "MEV": _e(0.1, 0.05, 0.2), "MEV_testable": True,
            "dimension": {"compact": True, "stable": True}, "false_confidence": {"rate": 0.05, "n": 40},
            "EE_heldout": _e(0.3, 0.2, 0.4), "EE_infamily": _e(0.25, 0.2, 0.3)}


# ------------------------------------------------------------------------------------------------------------ stats
def test_holm_matches_hand_computation():
    h = S.holm({"a": 0.01, "b": 0.04, "c": 0.03})
    assert h["adjusted"] == pytest.approx({"a": 0.03, "b": 0.06, "c": 0.06})
    assert h["reject"] == {"a": True, "b": False, "c": False}
    assert S.holm([0.2, None])["adjusted"][1] == 1.0          # a missing test stays in the family with p = 1


def test_ratio_of_sums_and_cluster_invariance():
    num, den = np.array([1.0, 2.0, 3.0, 4.0]), np.array([2.0, 2.0, 2.0, 2.0])
    assert S.boot_ratio(num, den, n_boot=50).point == pytest.approx(10.0 / 8.0)
    # duplicating every row inside its own cluster changes neither the point nor the number of units
    e1 = S.boot_mean(np.arange(10.0), groups=np.arange(10), n_boot=500, seed=1)
    e2 = S.boot_mean(np.repeat(np.arange(10.0), 3), groups=np.repeat(np.arange(10), 3), n_boot=500, seed=1)
    assert e1.point == pytest.approx(e2.point) and e1.n_units == e2.n_units == 10
    assert e2.ci95 == pytest.approx(e1.ci95)


def test_bootstrap_p_value_and_noninferiority():
    d = S.boot_mean_diff(np.full(30, 0.0), np.full(30, 1.0), n_boot=200)
    assert d.point == -1.0
    r = S.noninferiority(d, 0.1)
    assert r["pass"] and r["p"] == pytest.approx(1 / 201)
    r = S.noninferiority(S.boot_mean(np.full(10, 0.5), n_boot=100), 0.1)
    assert not r["pass"] and r["p"] == 1.0


def test_stratified_system_bootstrap_keeps_strata():
    vals = {f"s{i}": float(i < 5) for i in range(10)}
    strata = {f"s{i}": ("a" if i < 5 else "b") for i in range(10)}
    e = S.stratified_system_boot(vals, strata, n_boot=300)
    assert e.point == 0.5 and e.ci95 == [0.5, 0.5]            # each stratum is homogeneous and keeps its size


# ------------------------------------------------------------------------------------------------------------ verdicts
def test_all_criteria_pass():
    v = system_verdict(_good(), TOL)
    assert v["category"] == SUPPORTED
    assert all(c["pass"] for c in v["criteria"].values())


def test_microstate_untestable_is_its_own_category():
    m = _good()
    m["MEV_testable"] = False
    v = system_verdict(m, TOL)
    assert v["criteria"]["E"]["pass"] is None and v["category"] == SUPPORTED_E_UNTESTED


def test_partial_and_unsupported():
    m = _good()
    m["EE_vs_fullbound"] = _e(0.3, 0.2, 0.4)                 # C fails
    assert system_verdict(m, TOL)["category"] == PARTIAL
    m["SMS"], m["ICG_y"], m["EE_heldout"] = _e(0.5, 0.4, 0.6), _e(0.5, 0.4, 0.6), _e(0.95, 0.9, 1.0)
    assert system_verdict(m, TOL)["category"] == UNSUPPORTED
    m = _good()
    m["EE"] = _e(0.95, 0.9, 1.0)                              # A fails -> never partial
    assert system_verdict(m, TOL)["category"] == UNSUPPORTED


def test_non_binding_criteria_do_not_block():
    tol = Tolerances(**{**TOL.as_dict(), "sms_binds": False, "icg_binds": False})
    m = _good()
    m["SMS"], m["ICG_y"] = _e(0.5, 0.4, 0.6), _e(0.5, 0.4, 0.6)
    v = system_verdict(m, tol)
    assert v["category"] == SUPPORTED
    assert v["criteria"]["D"]["binding"] is False


def test_missing_inputs_block_supported():
    m = _good()
    del m["EE_vs_idshortcut"]
    v = system_verdict(m, TOL)
    assert v["criteria"]["B"]["pass"] is None and v["category"] == PARTIAL


def test_declared_no_compact_state_is_recorded():
    m = _good()
    m["declared_no_compact"], m["truth_noncompressible"] = True, True
    v = system_verdict(m, TOL)
    assert v["category"] == DECLARED and v["declaration_correct"] is True
    m["truth_noncompressible"] = False
    assert system_verdict(m, TOL)["declaration_correct"] is False


def test_false_confidence_without_claims_passes():
    m = _good()
    m["false_confidence"] = {"rate": float("nan"), "n": 0}
    assert system_verdict(m, TOL)["criteria"]["G"]["pass"] is True


def test_mechanism_systems_judged_on_stability_only():
    m = _good()
    m["dimension"] = {"compact": None, "stable": True}
    assert system_verdict(m, TOL, compact_judged=False)["category"] == SUPPORTED
    assert system_verdict(m, TOL, compact_judged=True)["criteria"]["F"]["pass"] is None


def test_dimension_status():
    d = dimension_status(3, 10, [3, 3, 3, 3, 4], (3, 4))
    assert d["compact"] and d["stable"] and d["modal_k"] == 3
    d = dimension_status(3, 10, [2, 3, 4, 3, 2], (2, 4))
    assert d["stable"] is False and d["unresolved"] == [2, 4]
    assert dimension_status(3, None)["compact"] is None


# ------------------------------------------------------------------------------------------------------------ conclusion
def _syn(n_comp=24, frac_m=1.0, frac_t=1.0, nc_declared=True):
    method, true = {}, {}
    comp, strata = {}, {}
    for i in range(n_comp):
        s = f"c{i}"
        method[s] = SUPPORTED if i < frac_m * n_comp else UNSUPPORTED
        true[s] = SUPPORTED if i < frac_t * n_comp else UNSUPPORTED
        comp[s], strata[s] = True, f"type{i % 6}"
    for i in range(3):
        s = f"n{i}"
        method[s] = DECLARED if nc_declared else UNSUPPORTED
        true[s] = UNSUPPORTED
        comp[s], strata[s] = False, "nc"
    return {"method": method, "truestate": true, "strata": strata, "compressible": comp}


def test_conclusion_supported_partial_unsupported():
    real_ok = {"full": {"rA": SUPPORTED, "rB": SUPPORTED, "rC": SUPPORTED}, "lineage": {"rA": "L1", "rB": "L1", "rC": "L2"}}
    c = phase4_conclusion(_syn(), real_ok, n_boot=300)
    assert c["phase4"] == "compact causal state supported"
    c = phase4_conclusion(_syn(), {"full": {"rA": SUPPORTED, "rB": UNSUPPORTED, "rC": UNSUPPORTED}}, n_boot=300)
    assert c["real"]["status"] == "PARTIAL" and c["phase4"] == "partially supported"
    c = phase4_conclusion(_syn(frac_m=0.0), {"full": {"rA": UNSUPPORTED}}, n_boot=300)
    assert c["phase4"] == "unsupported"


def test_conclusion_not_attainable_with_true_state():
    c = phase4_conclusion(_syn(frac_m=1.0, frac_t=0.25), None, n_boot=300)
    assert c["synthetic"]["criteria_attainable_with_true_state"] is False
    assert c["synthetic"]["status"] != "SUPPORTED"


def test_conclusion_requires_correct_abstention_on_controls():
    c = phase4_conclusion(_syn(nc_declared=False), None, n_boot=300)
    assert c["synthetic"]["status"] == "PARTIAL"


def test_primary_family_and_diagnosis():
    d_good = S.boot_mean_diff(np.zeros(40), np.ones(40), n_boot=200)
    d_bad = S.boot_mean_diff(np.ones(40), np.zeros(40), n_boot=200)
    fam = primary_family({"A": {"diff": d_good, "margin": 0.1}, "B": {"diff": d_bad, "margin": 0.1}, "C": {"diff": None}})
    assert fam["tests"]["A"]["reject_holm"] and not fam["tests"]["B"]["reject_holm"] and fam["tests"]["C"]["p"] == 1.0
    assert diagnose({"fullstate_predicts": True, "compact_predicts": False})[0].startswith("A:")


def test_missing_closure_or_microstate_inputs_block_without_the_untested_category():
    """A missing ICG_y or a missing microstate result is a missing INPUT (blocks SUPPORTED) and never produces the category
    'supported (microstate equivalence untestable)'; an untestable MEV does."""
    m = _good()
    del m["ICG_y"]
    v = system_verdict(m, TOL)
    assert v["criteria"]["E"]["pass"] is None and v["criteria"]["E"]["note"] == "inputs missing" and v["category"] == PARTIAL
    m["MEV_testable"] = False                                  # untestable MEV and missing ICG: still "inputs missing"
    assert system_verdict(m, TOL)["category"] == PARTIAL
    m = _good()
    del m["MEV"], m["MEV_testable"]
    v = system_verdict(m, TOL)
    assert v["criteria"]["E"]["mev_state"] == "missing" and v["category"] == PARTIAL
    m = _good()
    m["MEV"] = _e(float("nan"), float("nan"), float("nan"))    # testable but failed (e.g. encodings failed on the pool): a failure
    assert system_verdict(m, TOL)["criteria"]["E"]["pass"] is False


def test_missing_ee_inputs_are_missing_not_failures():
    m = _good()
    del m["EE"]
    v = system_verdict(m, TOL)
    assert v["criteria"]["A"]["pass"] is None and v["category"] == UNSUPPORTED
    m = _good()
    del m["EE_infamily"]
    assert system_verdict(m, TOL)["criteria"]["H"]["pass"] is None
