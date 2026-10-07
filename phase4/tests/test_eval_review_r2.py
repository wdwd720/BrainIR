"""Regression tests for review E's ROUND-2 findings (research/phase4/reviews/E2_review.md), one or more per finding, on the reviewer's
own layouts where they exist (the toy linear system with a known causal state; E's synthetic calibration rows; E's active-design
curve simulator). N1 (the tournament's decide step) is in test_tournament_decide.py."""

from __future__ import annotations

import numpy as np
import pytest
from brainir_causal import calibrate as C
from brainir_causal import stats as S
from brainir_causal.evalio import make_eval_system
from brainir_causal.evaluate import Prediction, predict_items
from brainir_causal.evaluate_mediation import eval_mediation
from brainir_causal.loop import CHECKPOINTS, active_success
from brainir_causal.verdict import DECLARED, SUPPORTED, UNSUPPORTED, dimension_status, phase4_conclusion
from test_eval_review import build
from test_lift_toysys import DT, T_END, ExactModel, ToyLinear, make_records


# ------------------------------------------------------------------------------------------------------------ N2 / M2
def test_N2_small_classes_merge_toward_moderate():
    cls = ["moderate"] * 6 + ["weak"] * 4 + ["strong"] * 4 + ["hi"] * 2 + ["na"] * 4
    fam = [f"f{i}" for i in range(6)] + ["f0", "f1", "f2", "f3"] + ["f4", "f5", "f6", "f7"] + ["f8", "f8"] + ["f9", "f9", "f10", "f10"]
    m = S.merge_small_classes(cls, fam)
    assert m["hi"] == "strong" and m["na"] == "moderate" and m["weak"] == "weak" and m["strong"] == "strong"
    # 'strong' (1 unit) goes toward 'moderate'; absent, it joins the class with the most units
    assert S.merge_small_classes(["weak", "weak", "strong"], ["a", "b", "c"]) == {"strong": "weak", "weak": "weak"}


def test_N2_a_class_without_signal_is_merged_and_charged():
    """A class whose truth denominators are all zero used to drop out of the class-balanced mean (with the method's errors on it);
    it is now merged into its neighbour, where those errors are charged."""
    cells, cls, fams, num, den = [], [], [], [], []
    for f in range(8):
        for c, k in enumerate(("moderate", "weak", "below")):
            for _ in range(4):
                cells.append(f"f{f}|c{c}"); cls.append(k); fams.append(f"f{f}")
                den.append(0.0 if k == "below" else 1.0); num.append(5.0 if k == "below" else 0.2)
    e = S.boot_class_balanced(num, den, S.CellDesign.build(cells, cls, fams), n_boot=500, seed=0)
    assert e.extra["classes_merged"] == {"below": "weak"} and e.point == pytest.approx((0.2 + (0.2 + 5.0)) / 2)
    assert np.isfinite(e.ci95).all()


def test_N2_family_units_and_t_replicates():
    """With >= 6 families the jackknife unit is the family (cells nested in families); the Estimate's replicates reproduce the
    t-interval, so boot_pvalue / one_sided_upper work as for a bootstrap."""
    rng = np.random.default_rng(0)
    cells, cls, fams, num, den = [], [], [], [], []
    for f in range(8):
        for c, k in enumerate(("moderate", "weak" if f % 2 else "strong")):
            for _ in range(4):
                d = float(rng.lognormal(0, 0.5))
                cells.append(f"f{f}|c{c}"); cls.append(k); fams.append(f"f{f}"); den.append(d); num.append(d * float(rng.lognormal(-1, 0.5)))
    e = S.boot_class_balanced(num, den, S.CellDesign.build(cells, cls, fams), n_boot=4000, seed=1)
    assert e.extra["jackknife_unit"] == "family" and e.extra["n_jackknife_units"] == 8 and e.ci95[0] < e.point < e.ci95[1]
    assert abs(np.log(e.ci95[1] / e.point) - np.log(e.point / e.ci95[0])) < 0.05     # symmetric on the log scale
    assert S.boot_pvalue(e.reps, e.ci95[1], "less") == pytest.approx(0.025, abs=0.01)


@pytest.mark.slow
def test_N2_coverage_on_review_E_layouts():
    """Review E's cb_cov layouts (cells of 2-14 per class, cell log-sd 0.5): the old within-class bootstrap covered 0.77-0.85 with
    P(upper CI < truth) 0.11-0.16; the family-jackknife-t interval must cover ~0.95 with a one-sided error near 0.025."""
    rng = np.random.default_rng(0)
    base = {"moderate": 0.4, "weak": 0.7, "strong": 0.3, "hi": 0.5, "na": 0.6}
    for layout in ({"moderate": 14, "weak": 7, "strong": 7, "hi": 2, "na": 6}, {"moderate": 6, "weak": 3, "strong": 3, "hi": 2, "na": 2}):
        cls = [c for c, n in layout.items() for _ in range(n)]
        cells = np.repeat(np.arange(len(cls)), 4)
        icls = [cls[c] for c in cells]
        design = S.CellDesign.build([str(c) for c in cells], icls, [str(c) for c in cells])
        mapping = S.merge_small_classes(icls, [str(c) for c in cells])
        pops = {}
        for c in layout:
            ce, d = rng.normal(0, 0.5, 200000), rng.lognormal(0, 0.7, 200000)
            pops[c] = ((d * np.minimum(np.exp(np.log(base[c]) + ce + rng.normal(0, 0.3, 200000)), 10)).sum(), d.sum())
        merged = sorted(set(mapping.values()))
        pop = float(np.mean([sum(pops[c][0] * layout[c] for c in layout if mapping[c] == k) /
                             sum(pops[c][1] * layout[c] for c in layout if mapping[c] == k) for k in merged]))
        R, cov, under = 300, 0, 0
        for r in range(R):
            ce = rng.normal(0, 0.5, len(cls))
            rr = np.exp(np.log([base[c] for c in icls]) + ce[cells] + rng.normal(0, 0.3, len(cells)))
            den = rng.lognormal(0, 0.7, len(cells))
            e = S.boot_class_balanced(den * np.minimum(rr, 10), den, design, 1000, r)
            cov += e.ci95[0] <= pop <= e.ci95[1]
            under += e.ci95[1] < pop
        assert cov / R >= 0.90 and under / R <= 0.06, (layout, cov / R, under / R)


# ------------------------------------------------------------------------------------------------------------ N3
def test_N3_hidden_latents_do_not_hide_a_readin_error():
    """Review E's hide5: a read-in error on 2 cells (8 of 120 items); giving 6 of those items a NaN latent used to move SMS from 0.75
    to 0.00. Latent-missing items now stay in the score (residual from u alone): SMS does not move."""
    s = ToyLinear(n=20, seed=0)
    train, _ = make_records(s, seed=0)
    sysc = make_eval_system("toy", "synthetic", DT, T_END, [r["x"] for r in train if r["split"] == "train"],
                            [r["y"] for r in train if r["split"] == "train"], 1)
    items = build(s, n_cells=15, seed=2)
    pe = predict_items(ExactModel(s), sysc, items)
    cells = sorted({it.cell() for it in items})
    bad = {it.item_id for it in items if it.cell() in set(cells[:2])}
    out = {}
    for hide in (0, 6):
        hid = set(sorted(bad)[:hide])
        pr = {}
        for it in items:
            p = pe[it.item_id]
            g = 0.2 if it.item_id in bad else 1.0
            pr[it.item_id] = Prediction(item_id=it.item_id, y_int=p.y_base + g * (p.y_int - p.y_base), y_base=p.y_base,
                                        z0=np.full_like(p.z0, np.nan) if it.item_id in hid else p.z0)
        out[hide] = eval_mediation(sysc, items, pr, n_boot=300, n_seeds=8)
    assert out[6]["n_latent_missing"] == 6 and out[6]["n_unusable"] == 0
    assert abs(out[6]["SMS"]["point"] - out[0]["SMS"]["point"]) < 0.05 and out[0]["SMS"]["point"] > 0.3


# ------------------------------------------------------------------------------------------------------------ N4
def _vi(sms_up, icg_up, mev_up, ee=0.3):
    def e(p, u):
        return {"point": p, "ci95": [p - 0.05, u]}
    return {"EE": e(ee, ee + 0.05), "EE_vs_idshortcut": e(-0.3, -0.2), "EE_vs_fullbound": e(0.0, 0.02), "SMS": e(sms_up - 0.05, sms_up),
            "ICG_y": e(icg_up - 0.05, icg_up), "MEV": e(mev_up - 0.05, mev_up), "MEV_testable": True,
            "dimension": {"compact": True, "stable": True}, "false_confidence": {"rate": 0.0, "n": 10}, "EE_heldout": e(0.35, 0.4),
            "EE_infamily": e(0.3, 0.35), "EE_by_class": {c: {"point": ee} for c in ("weak", "moderate", "strong")}}


def _rows(rng):
    def ts():
        return float(rng.uniform(0.02, 0.15)) if rng.random() > 0.1 else float(rng.uniform(0.6, 0.9))
    rows = []
    for i in range(46):
        r = {"sid": f"s{i}", "compact_judged": True, "true_state": {"verdict_inputs": _vi(ts(), ts(), ts())},
             "random_k": {"verdict_inputs": _vi(*rng.uniform(0.25, 0.7, 3))}}
        if i < 10:
            r["obs_shortcut"] = {"verdict_inputs": _vi(*rng.uniform(0.25, 0.7, 3))}
        rows.append(r)
    return rows


def test_N4_binding_flags_are_fixed_at_the_base_percentile():
    """Review E's calib_logic rows: raising p used to switch D / E off (101 of 200 calibrations). The flags are now decided at p = 90
    and kept; a criterion that binds at 90 and loses its power at the chosen p makes the calibration NOT ATTAINABLE."""
    dropped_silently = 0
    for rep in range(40):
        cp = C.common_percentile(_rows(np.random.default_rng(100 + rep)))
        base = cp["binding_flags_fixed_at_base"]
        assert all(t["binds"] == base for t in cp["table"])                  # the same flags at every p
        chosen = cp["chosen"]["tolerances"]
        assert all(chosen[f] == base[f] for f in base)
        if cp["attainable"] and any(base[f] and not cp["chosen"]["power_flags_at_p"][f] for f in base):
            dropped_silently += 1
        if cp["binding_lost_at_chosen"]:
            assert not cp["attainable"]
        if not cp["mediation_closure_binding"]:                      # review E round 3, N-new-2
            assert not cp["attainable"] and "MEDIATION" in cp["note"]
        elif cp["binding_lost_at_chosen"]:
            assert "no power" in cp["note"]
    assert dropped_silently == 0


# ------------------------------------------------------------------------------------------------------------ N5 / N10
def test_N5_true_state_categories_come_from_the_supported_item_rows():
    rows = [{"sid": "a", "compact_judged": True, "true_state": {"verdict_inputs": _vi(0.05, 0.05, 0.05)}},
            {"sid": "b", "compact_judged": True, "true_state": {"verdict_inputs": _vi(0.9, 0.9, 0.9)}},
            {"sid": "c", "skipped": "not compressible"}]
    tol = {"delta_A": 0.1, "delta_C": 0.05, "tau_SMS": 0.2, "tau_ICG": 0.2, "tau_MEV": 0.2, "delta_H": 0.1, "tau_FC": 0.2,
           "sms_binds": True, "icg_binds": True, "mev_binds": True}
    cats = C.true_state_categories(rows, tol)
    assert cats == {"a": SUPPORTED, "b": cats["b"]} and cats["b"] != SUPPORTED
    # the method scored on the same rows (calibrate_from_inputs(extra_models=...)) gives its verdicts on P_t's item set
    rows[0]["method"] = {"verdict_inputs": _vi(0.9, 0.9, 0.9)}
    rows[1]["method"] = {"verdict_inputs": _vi(0.05, 0.05, 0.05)}
    assert C.model_categories(rows, tol, "method") == {"a": cats["b"], "b": SUPPORTED}


@pytest.mark.slow
def test_N5_method_scored_on_the_true_states_items():
    """calibrate_from_inputs(extra_models=...) scores a method on exactly the items the true-state reference supports, with the
    method's own dimension criterion (P_m on P_t's item set)."""
    from test_calibrate_pipeline import FAST
    from test_calibrate_toyinputs import toy_inputs
    inp = toy_inputs(seed=0)
    dim = {"k": 3, "compact": True, "stable": True}
    row = C.calibrate_from_inputs("toy", pub=inp["pub"], sysc=inp["sysc"], train=inp["train"], items=inp["items"], pool=inp["pool"],
                                  k_true=2, truth=inp["truth"], register=inp["register"], n_boot=200, learner=FAST,
                                  refs=("true_state", "full_state", "no_effect", "id_shortcut"), corruptions=False,
                                  extra_models={"method": (ExactModel(inp["sys"]), dim)})
    assert not row["errors"], row["errors"]
    assert row["method"]["n_items"] == row["true_state"]["n_items"] == row["n_supported_items"]
    assert row["method"]["verdict_inputs"]["dimension"]["stable"] is True
    assert row["method"]["verdict_inputs"]["EE"]["point"] < 0.05


def test_N5_difference_on_one_item_set():
    """P_m - P_t on ONE item set: with the method's verdicts on the true state's supported items the difference uses them; without,
    it falls back to the all-items verdicts and says so."""
    comp = {f"s{i}": True for i in range(20)} | {"n0": False, "n1": False, "n2": False}
    truth = {s: SUPPORTED for s in comp if comp[s]}
    method_all = {s: (SUPPORTED if i < 10 else UNSUPPORTED) for i, s in enumerate(truth)} | {"n0": DECLARED, "n1": DECLARED, "n2": DECLARED}
    same = {s: SUPPORTED for s in truth}
    base = {"method": method_all, "truestate": truth, "compressible": comp}
    r_all = phase4_conclusion(base, None, n_boot=500)["synthetic"]
    r_same = phase4_conclusion(base | {"method_same_items": same}, None, n_boot=500)["synthetic"]
    assert r_all["P_m_minus_P_t"]["point"] == pytest.approx(-0.5) and "superset" in r_all["item_sets"]["P_m_minus_P_t"]
    assert r_same["P_m_minus_P_t"]["point"] == pytest.approx(0.0) and r_same["P_m_same_items"] == 1.0
    assert r_same["P_m"] == pytest.approx(0.5) and "both" in r_same["item_sets"]["P_m_minus_P_t"]


def test_N10_conclusion_charges_missing_results_against_the_claim():
    comp = {f"s{i}": True for i in range(24)} | {"n0": False, "n1": False, "n2": False}
    method = {s: SUPPORTED for s in comp if comp[s]} | {"n0": DECLARED, "n1": DECLARED, "n2": DECLARED}
    truth_all = {s: SUPPORTED for s in comp if comp[s]}
    full = phase4_conclusion({"method": method, "truestate": truth_all, "compressible": comp}, None, n_boot=500)["synthetic"]
    assert full["status"] == "SUPPORTED" and full["charged"] == {"method_verdict_missing": 0, "truestate_verdict_missing": 0,
                                                                 "method_same_items_missing": None}
    # a missing METHOD verdict counts as not supported (it used to be dropped from P_m)
    m2 = {k: v for k, v in method.items() if k not in ("s0", "s1", "s2", "s3", "s4")}
    r2 = phase4_conclusion({"method": m2, "truestate": truth_all, "compressible": comp}, None, n_boot=500)["synthetic"]
    assert r2["n_compressible"] == 24 and r2["n_supported"] == 19 and r2["charged"]["method_verdict_missing"] == 5
    # a missing TRUE-STATE verdict counts against attainability (not supported) and against the method in P_m - P_t (supported)
    t3 = {k: v for k, v in truth_all.items() if k not in [f"s{i}" for i in range(14)]}
    r3 = phase4_conclusion({"method": method, "truestate": t3, "compressible": comp}, None, n_boot=500)["synthetic"]
    assert r3["P_t"] < 0.5 and not r3["criteria_attainable_with_true_state"] and r3["status"] != "SUPPORTED"
    assert r3["charged"]["truestate_verdict_missing"] == 14
    m4 = {k: (UNSUPPORTED if k in [f"s{i}" for i in range(10)] else v) for k, v in method.items()}
    t4 = {k: v for k, v in truth_all.items() if k not in [f"s{i}" for i in range(10)]}
    r4 = phase4_conclusion({"method": m4, "truestate": t4, "compressible": comp}, None, n_boot=500)["synthetic"]
    assert r4["P_m_minus_P_t"]["point"] == pytest.approx(-10 / 24)                     # charged as supported for the difference


# ------------------------------------------------------------------------------------------------------------ N6
def _curves(rng, eff=1.0, n_sys=25, n_seeds=3, sd_seed=0.05, sd_ck=0.03, fixed_shift=0.0):
    """Review E's active.py curve simulator."""
    rows = []
    for s in range(n_sys):
        a, c = rng.uniform(0.2, 0.6), rng.uniform(0.3, 0.8)
        for d in ("own", "random", "fixed"):
            f = eff if d == "own" else 1.0
            for ls in range(n_seeds):
                se = rng.normal(0, sd_seed)
                for b in CHECKPOINTS:
                    rows.append({"system": f"s{s}", "designer": d, "loop_seed": ls, "budget": b,
                                 "EE": a + c * (f * b / 10.0) ** -0.5 + se + rng.normal(0, sd_ck) + (fixed_shift if d == "fixed" else 0)})
    return rows


def test_N6_rule_i_is_one_test_per_comparator():
    res = active_success(_curves(np.random.default_rng(1), eff=2.0), own="own", n_boot=400, seed=0)
    fb = res["fixed_budget"]
    assert set(fb["tests"]) == {"random", "fixed"} and all(v["better"] for v in fb["tests"].values()) and fb["success"]
    assert res["budget_ratio"]["interval"].startswith("log-ratio") and "conservative" in res["budget_ratio"]["interpretation"]


@pytest.mark.slow
def test_N6_union_size_under_a_weaker_fixed_design():
    """E's worst null (own = random, fixed worse by 0.10, 25 systems): the union was 0.069; it must now stay at or below 0.05
    (Monte Carlo tolerance)."""
    rng = np.random.default_rng(7)
    R, s = 300, 0
    for r in range(R):
        s += active_success(_curves(rng, fixed_shift=0.10), own="own", n_boot=300, seed=r)["success"]
    assert s / R <= 0.065


# ------------------------------------------------------------------------------------------------------------ N7
def test_N7_missing_refits_count_as_disagreeing():
    assert dimension_status(3, 10, [3], level="B")["stable"] is False                  # one seed of the required 3
    assert dimension_status(3, 10, [3, 3, None], level="B")["stable"] is False         # a failed seed
    assert dimension_status(3, 10, [3, 3, 3], level="B")["stable"] is True
    assert dimension_status(3, 10, [3], (3, 4), level="C")["stable"] is False          # 1 of 5 refits
    d = dimension_status(3, 10, [3, 3, 3, 3, None], (3, 3), level="C")
    assert d["stable"] is False and d["n_missing"] == 1 and "unresolved" in d
    assert dimension_status(3, 10, [3, 3, 3, 3, 3], None, level="C")["stable"] is True
