"""Regression tests for review E's ROUND-3 findings (research/phase4/reviews/E3_review.md) and the Level C driver's calibration request
(H3): N-new-2 (SUPPORTED needs a binding mediation and closure criterion), N-new-4 (small-cluster interval, never a cell fallback),
N-new-5 / N-new-8 (criterion F), N-new-6 (merge patterns), N-new-9 (one bound choice per kind), N9 (suite margins), M1 (the proposed
class condition of A, off by default) and H3 (the isolation phase order of extra models in the calibration)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from brainir_causal import calibrate as C
from brainir_causal import stats as S
from brainir_causal.verdict import (
    PARTIAL,
    SUPPORTED,
    Tolerances,
    build_primary_family,
    dimension_status,
    system_verdict,
)

ROOT = Path(__file__).resolve().parents[2]


def _e(point, lo, hi):
    return {"point": point, "ci95": [lo, hi]}


def _good():
    return {"EE": _e(0.2, 0.1, 0.3), "EE_vs_idshortcut": _e(-0.3, -0.4, -0.2), "EE_vs_fullbound": _e(0.0, -0.02, 0.02),
            "SMS": _e(0.0, -0.05, 0.05), "ICG_y": _e(0.0, -0.02, 0.02), "MEV": _e(0.05, 0.0, 0.1), "MEV_testable": True,
            "false_confidence": {"rate": 0.0, "n": 10}, "dimension": {"k": 2, "compact": True, "stable": True},
            "EE_heldout": _e(0.3, 0.2, 0.4), "EE_infamily": _e(0.25, 0.15, 0.35),
            "EE_by_class": {"moderate": {"point": 0.2}, "strong": {"point": 0.1}, "weak": {"point": 0.4}}}


TOL = Tolerances(delta_A=0.15, delta_C=0.05, tau_SMS=0.2, tau_ICG=0.1, tau_MEV=0.3, delta_H=0.1)


# ------------------------------------------------------------------------------------------------------------ N-new-2
def _vi(sms_up, icg_up, mev_up, ee=0.3):
    def e(p, u):
        return {"point": p, "ci95": [p - 0.05, u]}
    return {"EE": e(ee, ee + 0.05), "EE_vs_idshortcut": e(-0.3, -0.2), "EE_vs_fullbound": e(0.0, 0.02), "SMS": e(sms_up - 0.05, sms_up),
            "ICG_y": e(icg_up - 0.05, icg_up), "MEV": e(mev_up - 0.05, mev_up), "MEV_testable": True,
            "dimension": {"compact": True, "stable": True}, "false_confidence": {"rate": 0.0, "n": 10}, "EE_heldout": e(0.35, 0.4),
            "EE_infamily": e(0.3, 0.35), "EE_by_class": {c: {"point": ee} for c in ("weak", "moderate", "strong")}}


def _rows(rng, null_lo, null_hi, n_trap=13):
    """Review E's calib_logic rows (round 3): 46 systems, 13 trap systems, nulls uniform on [null_lo, null_hi]."""
    def ts():
        return float(rng.uniform(0.02, 0.15)) if rng.random() > 0.1 else float(rng.uniform(0.6, 0.9))
    rows = []
    for i in range(46):
        r = {"sid": f"s{i}", "compact_judged": True, "true_state": {"verdict_inputs": _vi(ts(), ts(), ts())},
             "random_k": {"verdict_inputs": _vi(*rng.uniform(null_lo, null_hi, 3))}}
        if i < n_trap:
            r["obs_shortcut"] = {"verdict_inputs": _vi(*rng.uniform(null_lo, null_hi, 3))}
        rows.append(r)
    return rows


def test_Nnew2_supported_needs_binding_mediation_and_closure():
    assert system_verdict(_good(), TOL)["category"] == SUPPORTED
    for flags in ({"sms_binds": False}, {"icg_binds": False, "mev_binds": False}):
        v = system_verdict(_good(), Tolerances(**{**TOL.as_dict(), **flags}))
        assert v["category"] == PARTIAL and v["all_binding_criteria_hold"] and "supported_blocked" in v
    # review E's scenario: nulls as good as the true state, so nothing binds; every calibration used to be "attainable"
    n_att = 0
    for rep in range(20):
        cp = C.common_percentile(_rows(np.random.default_rng(100 + rep), 0.02, 0.15))
        assert not cp["mediation_closure_binding"] and "MEDIATION" in cp["note"]
        n_att += cp["attainable"]
    assert n_att == 0


# ------------------------------------------------------------------------------------------------------------ N-new-4
def _design(n_fam, rng, dominant=False):
    cells, cls, fams, num, den = [], [], [], [], []
    for f in range(n_fam):
        for c, k in enumerate(("moderate", "weak" if f % 2 else "strong")):
            for _ in range(4):
                d = float(rng.lognormal(0, 0.5)) * (50.0 if (dominant and f == 0) else 1.0)
                cells.append(f"f{f}|c{c}"); cls.append(k); fams.append(f"f{f}"); den.append(d)
                num.append(d * float(rng.lognormal(-1, 0.4)))
    return S.CellDesign.build(cells, cls, fams), np.array(num), np.array(den)


def test_Nnew4_bell_mccaffrey_df_and_no_cell_fallback():
    assert S.bell_mccaffrey_df(np.ones((8, 1))) == pytest.approx(7.0)                    # equal family weights: F - 1
    du = np.ones((8, 1))
    du[0, 0] = 200.0
    assert S.bell_mccaffrey_df(du) < 1.5                                                 # one dominant family: about 1
    rng = np.random.default_rng(0)
    d5, n5, e5 = _design(5, rng)
    est = S.boot_class_balanced(n5, e5, d5, 500, 0)                                      # 5 families: families, never cells
    assert est.extra["jackknife_unit"] == "family" and est.extra["n_jackknife_units"] == 5 and np.isfinite(est.ci95[1])
    assert "Bell-McCaffrey" in est.extra["method"]
    d3, n3, e3 = _design(3, rng)
    est = S.boot_class_balanced(n3, e3, d3, 500, 0)                                      # 3 families: no interval at all
    assert not np.isfinite(est.ci95[1]) and "too few families" in est.extra["method"]
    d12, n12, e12 = _design(12, rng)
    w_eq = np.diff(S.boot_class_balanced(n12, e12, d12, 4000, 0).ci95)[0]
    d12d, n12d, e12d = _design(12, np.random.default_rng(0), dominant=True)
    w_dom = S.boot_class_balanced(n12d, e12d, d12d, 4000, 0)
    assert w_dom.extra["df"] < 4 and np.diff(w_dom.ci95)[0] > w_eq                     # a dominant family widens the interval
    # without family labels, every cell is its own family (explicit, recorded)
    flat = S.CellDesign.build([d12.cells[i][0] for i in d12.item_cell], [d12.cells[i][1] for i in d12.item_cell])
    est = S.boot_class_balanced(n12, e12, flat, 200, 0)
    assert est.extra["jackknife_unit"].startswith("cell (no family labels")


@pytest.mark.slow
def test_Nnew4_coverage_on_review_E_layouts():
    """Review E's jk_cov model (t3 item errors capped at 10x, family and cell log-sd 0.3-0.6) at 4-20 families: the old interval had
    P(upper < truth) 0.06-0.13 at 6-8 families and 0.18-0.29 below 6; the new one stays near 0.025 (Monte Carlo tolerance)."""
    base = {"weak": 0.7, "moderate": 0.4, "strong": 0.3, "hi": 0.5, "na": 0.6}
    scale = {"weak": 0.1, "moderate": 1, "strong": 9, "hi": 40, "na": 2}
    errs = []
    for n_fam, nhi, nna in ((4, 1, 1), (6, 1, 1), (8, 1, 2), (12, 2, 3), (20, 2, 4)):
        rng = np.random.default_rng(n_fam)
        fams, cls = [], []
        for f in range(n_fam):
            cc = ["hi", "hi"] if f < nhi else (["na", "na"] if f < nhi + nna else ["moderate", "weak" if rng.random() < 0.5 else "strong"])
            fams += [f, f]
            cls += cc
        mapping = S.merge_small_classes(cls, [f"f{f}" for f in fams])
        per = {}
        for c0 in set(cls):                          # the population value of the same statistic (same class mapping)
            z = rng.normal(0, 0.6, 400000) + rng.normal(0, 0.3, 400000) + rng.standard_t(3, 400000) * 0.3
            d = rng.lognormal(0, 0.7, 400000) * scale[c0]
            per[c0] = ((d * np.minimum(base[c0] * np.exp(z), 10)).mean(), d.mean())
        grp: dict = {}
        for c0 in set(cls):
            n_, d_ = grp.get(mapping[c0], (0.0, 0.0))
            grp[mapping[c0]] = (n_ + cls.count(c0) * per[c0][0], d_ + cls.count(c0) * per[c0][1])
        truth = float(np.mean([n_ / d_ for n_, d_ in grp.values()]))
        under, R = 0, 300
        for r in range(R):
            fe, ce = rng.normal(0, 0.6, n_fam), rng.normal(0, 0.3, len(cls))
            num, den, cell, fam, cl = [], [], [], [], []
            for c in range(len(cls)):
                dd = rng.lognormal(0, 0.7, 4) * scale[cls[c]]
                num += list(dd * np.minimum(base[cls[c]] * np.exp(fe[fams[c]] + ce[c] + rng.standard_t(3, 4) * 0.3), 10))
                den += list(dd)
                cell += [f"c{c}"] * 4
                fam += [f"f{fams[c]}"] * 4
                cl += [cls[c]] * 4
            e = S.boot_class_balanced(num, den, S.CellDesign.build(cell, cl, fam), 1000, r)
            under += e.ci95[1] < truth
        errs.append(under / R)
    assert max(errs) <= 0.08 and float(np.mean(errs)) <= 0.045, errs


# ------------------------------------------------------------------------------------------------------------ N-new-5 / N-new-8
def test_Nnew5_Nnew8_dimension_stability():
    assert dimension_status(3, 10, [3, 4, 3], (1, 40), level="B")["stable"] is False     # a wide self-reported range is ignored
    d = dimension_status(3, 10, [3, 4, 3], (3, 4), level="B")
    assert d["stable"] is True and d["range_used"] == [3, 4]
    assert dimension_status(3, 10, [3, 3, 3, 3, 40], (1, 40), level="C")["stable"] is False
    assert dimension_status(3, 10, [1, 5, 9, 20, 40], (1, 40), level="C")["stable"] is False
    assert dimension_status(3, 10, [3, 3, 3, 3, 4], (3, 4), level="C")["stable"] is True
    assert dimension_status(3, 10, [3, 3, 3, 3, 4], None, level="C")["stable"] is False
    assert dimension_status(3, 10, [3, 3, 3, 3, None], None, level="C")["stable"] is False   # a crash never buys the disagreement
    assert "range_note" in dimension_status(3, 10, [3, 3, 3], (5, 6), level="B")          # a range excluding the modal k


# ------------------------------------------------------------------------------------------------------------ N-new-9
def _tournament():
    spec = importlib.util.spec_from_file_location("p4_tournament_r3", ROOT / "scripts" / "p4" / "tournament.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["p4_tournament_r3"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_Nnew9_one_bound_choice_per_kind():
    T = _tournament()

    def res(ee):
        return {"items": {"effects": {"EE_cb_medium": {"point": ee}}}}
    systems = {f"syn{i}": {"kind": "synthetic"} for i in range(4)} | {f"real{i}": {"kind": "real"} for i in range(3)}
    ref_ee = {"syn0": 0.30, "syn1": 0.30, "syn2": 0.30, "syn3": 0.30, "real0": 0.20, "real1": 0.20, "real2": 0.20}
    refs = {s: {"full_state": res(v), "id_shortcut": res(0.9)} for s, v in ref_ee.items()}
    # the baseline beats the reference on ONE synthetic system only (the old per-system minimum picked it there); on the real systems it
    # has results on real0 only (missing systems count as EE 10)
    base = {"syn0": 0.10, "syn1": 0.50, "syn2": 0.50, "syn3": 0.50, "real0": 0.10}
    evs = {"full_state_baseline": {0: {s: {"result": res(v)} for s, v in base.items()}, 1: {s: {"result": res(v)} for s, v in base.items()}}}
    b = T.choose_bounds(refs, evs, systems)
    assert b["choice_by_kind"]["full_state"] == {"synthetic": "ref:full_state", "real": "ref:full_state"}
    assert all(b["full_state"][s] == "ref:full_state" for s in systems)
    base.update({"real1": 0.05, "real2": 0.05})
    evs = {"full_state_baseline": {0: {s: {"result": res(v)} for s, v in base.items()}}}
    b = T.choose_bounds(refs, evs, systems)
    assert b["choice_by_kind"]["full_state"]["real"] == "baseline:full_state_baseline"
    assert b["full_state"]["real0"] == b["full_state"]["real2"] == "baseline:full_state_baseline"
    del evs["full_state_baseline"][0]["real1"]                     # the chosen baseline failed on real1 (median still the baseline's)
    b = T.choose_bounds(refs, evs, systems)
    assert b["choice_by_kind"]["full_state"]["real"] == "baseline:full_state_baseline"
    assert b["full_state"]["real1"] == "ref:full_state" and b["fallbacks"]["full_state"] == ["real1"]
    # Level C: new systems get their kind's choice unchanged
    new = T.bounds_for_systems(b, {"conf0": {"kind": "synthetic"}, "real9": {"kind": "real"}})
    assert new["full_state"] == {"conf0": "ref:full_state", "real9": "baseline:full_state_baseline"}


# ------------------------------------------------------------------------------------------------------------ N9 / N-new-6
def test_N9_suite_margins_are_stricter_than_per_system_margins():
    rng = np.random.default_rng(5)
    rows = []
    for i in range(46):
        up = float(rng.uniform(0.1, 0.4))
        vi = _vi(up, 0.1, 0.1)
        vi["SMS"] = {"point": up - 0.15, "ci95": [up - 0.3, up]}
        rows.append({"sid": f"s{i}", "compact_judged": True, "true_state": {"verdict_inputs": vi}})
    tol = C.tolerance_rule(rows, 90.0)
    sm = C.suite_margins(rows, 90.0, n_outer=500)
    assert sm["n_suite"] == 46 and sm["true_state_mean_SMS"] < sm["tau_SMS_suite"] < 0.5 * tol["tau_SMS"]
    assert sm["delta_C_suite"] >= C.DELTA_C_MIN
    margins = {"delta_A": 0.1, "delta_C": 0.2, "tau_SMS": 0.4, "delta_NI": 0.05, "delta_C_suite": 0.06, "tau_SMS_suite": 0.07}
    systems = [f"s{i}" for i in range(20)]
    vals = {h: {s: 0.0 for s in systems} for h in ("H1", "H2", "H3", "H4", "H5", "H6")}
    vals["H4"] = {s: 0.2 for s in systems}                                            # mean SMS 0.2: below tau_SMS, above tau_SMS_suite
    merges = {s: ({"hi": "strong"} if i % 2 else {}) for i, s in enumerate(systems)}
    fam = build_primary_family({"systems": systems, "values": vals, "merges": merges}, {}, margins, n_boot=300)
    assert fam["thresholds_suite"]["H4"] == 0.07 and fam["thresholds"]["H4"] == 0.4
    assert not fam["tests"]["suite:H4"]["reject_holm"]
    assert fam["tests"]["suite:H1"]["class_merge_patterns"] == {"none": 10, "hi->strong": 10}


def test_Nnew6_per_class_values_and_merges():
    rng = np.random.default_rng(1)
    d, n, e = _design(8, rng)
    cv = S.class_values(n, e, d)
    est = S.boot_class_balanced(n, e, d, 200, 0)
    assert est.point == pytest.approx(np.mean([v["point"] for v in cv.values()]))
    members = sorted(c for v in cv.values() for c in v["members"])
    assert members == ["moderate", "strong", "weak"] and all(v["n_families"] >= S.MIN_CLASS_UNITS for v in cv.values())


# ------------------------------------------------------------------------------------------------------------ M1 (rule R3p)
def test_M1_class_condition_of_A_is_the_rule():
    """Review E round 3, M1, rule R3p (adopted): A also needs the POINT EE of every merged magnitude class < 1 - delta_A."""
    from brainir_causal import verdict as V
    assert V.A_EVERY_CLASS is True
    m = _good()
    m["EE_by_class"] = {"moderate": {"point": 1.0}, "strong": {"point": 0.0}, "weak": {"point": 1.0}}   # strong items only
    v = system_verdict(m, TOL)                                                        # the rule, by default
    assert v["criteria"]["A"]["pass"] is False and "moderate" in v["criteria"]["A"]["note"] and v["category"] != SUPPORTED
    assert system_verdict(m, TOL, a_every_class=False)["criteria"]["A"]["pass"] is True   # the earlier rule (diagnosis only)
    assert system_verdict(_good(), TOL)["category"] == SUPPORTED
    m.pop("EE_by_class")                                                              # per-class values missing: A's input is missing
    v = system_verdict(m, TOL)
    assert v["criteria"]["A"]["pass"] is None and "A" in v["missing"] and v["category"] != SUPPORTED


def test_M1_class_condition_enters_the_calibration_support_rate():
    """The support rate counts a system only when the true state meets criterion A INCLUDING its class condition, so a class the true
    state cannot predict lowers the support rate (and can make the calibration "not attainable") instead of passing silently."""
    rows = _rows(np.random.default_rng(7), 0.5, 0.9)
    tol = dict(C.tolerance_rule(rows, 90.0), sms_binds=True, icg_binds=True, mev_binds=True)
    base, n = C.supported_rate(rows, tol)
    assert n == 46 and base > 0
    poor = [dict(r) for r in rows]
    for r in poor[:20]:                                                               # the true state fails the weak class on 20
        vi = dict(r["true_state"]["verdict_inputs"])
        vi["EE_by_class"] = {**vi["EE_by_class"], "weak": {"point": 0.95}}
        r["true_state"] = {"verdict_inputs": vi}
    held = [bool(C._verdict(r["true_state"]["verdict_inputs"], tol, True).get("all_binding_criteria_hold")) for r in poor[:20]]
    low, _ = C.supported_rate(poor, tol)
    assert not any(held) and low < base


# ------------------------------------------------------------------------------------------------------------ H3: phase order
def test_H3_extra_models_follow_the_isolation_phase_order(monkeypatch):
    import brainir_causal.evaluate as EV
    import brainir_causal.evaluate_mediation as EM
    import brainir_causal.evaluate_micro as EMI
    log: list = []

    class Phased:
        phase = "A"

        def set_phase(self, p):
            log.append(("set_phase", p))
            self.phase = p

        def info(self):
            return {"k": {"s": 2}}

    def rec(name, ret):
        def f(first, *a, **k):
            log.append((name, getattr(first, "phase", "-")))
            return ret
        return f
    monkeypatch.setattr(EV, "predict_items", rec("predict", {}))
    monkeypatch.setattr(EV, "evaluate_items", rec("evaluate_items", {"effects": {}, "calibration": {}}))
    monkeypatch.setattr(EM, "eval_mediation", rec("mediation", {}))
    monkeypatch.setattr(EM, "eval_closure", rec("closure", {}))
    monkeypatch.setattr(EMI, "latent_whitener", rec("whitener", None))
    monkeypatch.setattr(EMI, "eval_microstate", rec("microstate", {}))
    sysc = SimpleNamespace(system_id="s")
    C.evaluate_reference(Phased(), sysc, [], object(), whiten_hists=[1], n_boot=10, seed=0)
    assert log == [("set_phase", "A"), ("predict", "A"), ("evaluate_items", "A"), ("mediation", "-"), ("whitener", "A"),
                   ("microstate", "A"), ("set_phase", "C"), ("closure", "C")]
    log.clear()
    C.evaluate_reference(SimpleNamespace(info=dict), sysc, [], object(), whiten_hists=[1], n_boot=10, seed=0)
    assert [x[0] for x in log] == ["predict", "evaluate_items", "mediation", "closure", "whitener", "microstate"]   # references unchanged


def test_H3_phase_order_with_a_real_model(monkeypatch):
    """The toy system's exact model wrapped as a phased Fresh (the RemoteFresh discipline): the closure's TRUE-FUTURE encodings run in
    phase C, the microstate in phase A, and the scores equal those of the unphased model."""
    import brainir_causal.evaluate_mediation as EM
    import brainir_causal.evaluate_micro as EMI
    from brainir_causal.fresh import Fresh
    from test_calibrate_toyinputs import toy_inputs
    from test_lift_toysys import ExactModel
    inp = toy_inputs(seed=0, n_test_kick=6, n_test_pulse=4, n_pool_src=2)

    class PhasedFresh(Fresh):
        def __init__(self, model):
            super().__init__(model)
            self.phase = "A"

        def set_phase(self, p):
            assert ("A", "lift", "C").index(p) >= ("A", "lift", "C").index(self.phase)
            self.phase = p
    seen: dict = {}
    real_future, real_micro = EM._future_encodings, EMI.eval_microstate

    def future(F, *a, **k):
        seen["future"] = getattr(F, "phase", "-")
        return real_future(F, *a, **k)

    def micro(model, *a, **k):
        seen["micro"] = getattr(model, "phase", "-")
        return real_micro(model, *a, **k)
    monkeypatch.setattr(EM, "_future_encodings", future)
    monkeypatch.setattr(EMI, "eval_microstate", micro)
    wh = C.whiten_histories_from(inp["train"])
    out_p = C.evaluate_reference(PhasedFresh(ExactModel(inp["sys"])), inp["sysc"], inp["items"], inp["pool"], whiten_hists=wh,
                                 n_boot=100, seed=0)
    assert seen == {"future": "C", "micro": "A"}
    out_r = C.evaluate_reference(ExactModel(inp["sys"]), inp["sysc"], inp["items"], inp["pool"], whiten_hists=wh, n_boot=100, seed=0)
    assert out_p["eff"]["EE_medium"]["point"] == pytest.approx(out_r["eff"]["EE_medium"]["point"])
    assert out_p["clo"]["ICG_y"]["point"] == pytest.approx(out_r["clo"]["ICG_y"]["point"])
    assert out_p["mic"]["MEV"]["point"] == pytest.approx(out_r["mic"]["MEV"]["point"], nan_ok=True)
