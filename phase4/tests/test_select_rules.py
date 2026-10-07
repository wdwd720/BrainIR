"""Level B selection (brainir_causal.select): THE RULE of PROTOCOL section 10 (review E, B5 / M7), the rescaled bootstrap, the pilot."""

from __future__ import annotations

import math

import numpy as np
import pytest

from brainir_causal import select as S


def vals(kind="synthetic", *, A=True, D=True, E=True, EE=0.3, SMS=0.0, ICG=0.0, comp=1.0, obs=1.0, eff=None, params=100.0, compute=10.0):
    return {"kind": kind, "failed": False, "A": A, "B": True, "C": True, "D": D, "E": E, "F": True, "G": True, "H": True, "EE": EE,
            "SMS": SMS, "ICG": ICG, "compression": comp, "observational": obs, "efficiency": eff, "simplicity": params, "compute": compute,
            "category": "x", "charged": []}


def table(n_syn=20, n_real=0, *, rate_A=1.0, rate_D=1.0, rate_E=1.0, noise=0.01, seed=0, **kw):
    """{system: values} with the given pass rates (first fraction of the systems pass)."""
    rng = np.random.default_rng(seed)
    out = {}
    for i in range(n_syn):
        f = (i + 0.5) / n_syn
        out[f"syn{i:02d}"] = vals(A=f < rate_A, D=f < rate_D, E=f < rate_E, **{k: (v + noise * rng.standard_normal()
                                                                                   if isinstance(v, float) and k in ("obs",) else v)
                                                                                for k, v in kw.items()})
    for i in range(n_real):
        f = (i + 0.5) / n_real
        out[f"real:A:m{i}"] = vals("real", A=f < rate_A, **{k: v for k, v in kw.items()})
    return out


# ------------------------------------------------------------------------------------------------------------ gates
def test_gates_are_relative_to_the_true_state_reference():
    cand = table(rate_A=0.8, rate_D=0.3, rate_E=0.3)
    weak_ref = table(rate_A=0.9, rate_D=0.6, rate_E=0.6)
    strong_ref = table(rate_A=0.9, rate_D=0.8, rate_E=0.8)
    assert S.gates(cand, weak_ref, None)["eligible"]                      # 0.3 >= 0.5 x 0.6
    g = S.gates(cand, strong_ref, None)
    assert not g["eligible"] and g["kinds"]["synthetic"]["passes"] == {"A": True, "D": False, "E": False}


def test_real_gate_is_relative_to_the_full_state_bound():
    cand = table(n_syn=0, n_real=6, rate_A=0.34)
    assert S.gates(cand, None, table(n_syn=0, n_real=6, rate_A=0.67))["eligible"]
    assert not S.gates(cand, None, table(n_syn=0, n_real=6, rate_A=1.0))["eligible"]


def test_gates_need_reference_results_and_skip_systems_without_one():
    cand = table(rate_A=1.0)
    with pytest.raises(ValueError):
        S.gates(cand, {}, None)
    ref = table(rate_A=1.0)
    del ref["syn00"], ref["syn01"]
    g = S.gates(cand, ref, None)
    assert g["kinds"]["synthetic"]["n_reference_missing"] == 2 and g["kinds"]["synthetic"]["n_gate_systems"] == 18


def test_missing_and_failed_systems_count_as_not_passing():
    ref = table(rate_A=1.0, rate_D=1.0, rate_E=1.0)
    cand = table(rate_A=1.0)
    for i in range(12):
        cand[f"syn{i:02d}"] = S.failed_system_values("synthetic")
    assert not S.gates(cand, ref, None)["eligible"]
    partial = {k: v for i, (k, v) in enumerate(table(rate_A=1.0).items()) if i >= 12}
    r = S.rank({"partial": partial}, true_state=ref, systems={k: "synthetic" for k in ref})
    assert not r["gates"]["partial"]["eligible"] and r["charged"]["partial"]["systems_without_result"] == 12


# ------------------------------------------------------------------------------------------------------------ ordering
def test_no_eligible_candidate_orders_by_the_gate_metrics():
    ref = table(rate_A=1.0, rate_D=1.0, rate_E=1.0)
    c = {"b": table(rate_A=0.2, EE=0.5, SMS=0.1), "a": table(rate_A=0.2, EE=0.5, SMS=0.05), "c": table(rate_A=0.2, EE=0.4, SMS=0.9)}
    r = S.rank(c, true_state=ref)
    assert not r["any_eligible"] and r["note"] == S.NO_GATE_NOTE
    assert r["order"] == ["c", "a", "b"]                                # median EE, then median SMS
    d = S.halve(r["order"], set(), eligible=r["eligible_order"])
    assert d["keep"] == ["c", "a"]


def test_eligible_candidates_always_rank_above_ineligible_ones():
    ref = table(rate_A=1.0, rate_D=1.0, rate_E=1.0)
    c = {"elig_bad": table(EE=0.9, obs=5.0, comp=0.0), "inelig_good": table(rate_A=0.0, EE=0.01, obs=0.1)}
    r = S.rank(c, true_state=ref)
    assert r["order"] == ["elig_bad", "inelig_good"] and r["any_eligible"]


def test_lexicographic_criteria_with_tie_bands():
    ref = table(rate_A=1.0, rate_D=1.0, rate_E=1.0)
    rng = np.random.default_rng(1)
    better_obs = table()
    worse_obs = table()
    for s in better_obs:
        better_obs[s]["observational"] = 0.5 + 0.05 * rng.standard_normal()
        worse_obs[s]["observational"] = 1.0 + 0.05 * rng.standard_normal()
    r = S.rank({"w": worse_obs, "b": better_obs}, true_state=ref, n_boot=500)
    assert r["order"] == ["b", "w"] and r["pairwise"]["b"]["w"]["criterion"] == "observational"
    comp = table(comp=1.0)
    nocomp = table(comp=0.0)
    for s in nocomp:
        nocomp[s]["observational"] = 0.1
    r = S.rank({"nocomp": nocomp, "comp": comp}, true_state=ref, n_boot=500)
    assert r["order"] == ["comp", "nocomp"] and r["pairwise"]["comp"]["nocomp"]["criterion"] == "compression"


def test_efficiency_ties_until_loops_have_run_and_failures_are_charged():
    ref = table(rate_A=1.0, rate_D=1.0, rate_E=1.0)
    a, b = table(), table()
    r = S.rank({"a": a, "b": b}, true_state=ref, n_boot=300)
    assert not r["loops_ran"]
    assert any(d["criterion"] == "efficiency" and d["tie"] for d in r["pairwise"]["a"]["b"]["details"])
    for s in a:
        a[s]["efficiency"] = 0.3
    r = S.rank({"a": a, "b": b}, true_state=ref, n_boot=300)
    assert r["loops_ran"] and r["pairwise"]["a"]["b"]["winner"] == "a" and r["pairwise"]["a"]["b"]["criterion"] == "efficiency"
    assert r["charged"]["b"]["values"]["efficiency"] == len(b)


def test_simplicity_of_a_failed_fit_is_charged_the_worst_value_on_the_system():
    ref = table(rate_A=1.0, rate_D=1.0, rate_E=1.0)
    a, b = table(params=10.0), table(params=50.0)
    for s in list(a)[:3]:
        a[s]["simplicity"] = None
    filled = {"a": a, "b": b}
    tab, charged = S._criterion_table(filled, {s: "synthetic" for s in a}, loops_ran=False)
    assert charged["a"]["simplicity"] == 3 and all(tab["simplicity"]["a"][s] == 50.0 for s in list(a)[:3])
    r = S.rank(filled, true_state=ref, n_boot=300)
    assert r["order"][0] == "a"


def test_seed_average():
    s0 = {"x": vals(A=True, D=False, EE=0.2, obs=1.0), "y": vals(A=True)}
    s1 = {"x": vals(A=False, D=False, EE=0.4, obs=3.0)}
    avg = S.seed_average({0: s0, 1: s1})
    assert avg["x"]["A"] == 0.5 and avg["x"]["D"] == 0.0 and math.isclose(avg["x"]["EE"], 0.3) and math.isclose(avg["x"]["observational"], 2.0)
    assert avg["y"]["n_failed_seeds"] == 1 and avg["y"]["A"] == 0.5 and avg["y"]["EE"] == (0.3 + S.WORST["EE"]) / 2


def test_per_system_values_from_a_verdict():
    ver = {"metrics": {"EE": {"point": 0.3, "ci95": [0.2, 0.4]}, "SMS": {"point": 0.05}, "dimension": {"compact": True}},
           "verdict": {"criteria": {"A": {"pass": True}, "D": {"pass": False}, "E": {"pass": None}}, "category": "partially supported"}}
    res = {"k": 2, "compact_judged": True, "items": {"observational": {"obs_nmse_medium": {"point": 0.7}}},
           "capacity": {"params": {"reported": True, "total": 42}}}
    v = S.per_system_values(ver, res, truth_k=2, fit_compute={"cpu_s": 3.0, "gpu_s": 1.0})
    assert v["A"] is True and v["D"] is False and v["E"] is None and v["EE"] == 0.3 and v["SMS"] == 0.05
    assert v["ICG"] == S.WORST["ICG"] and "ICG" in v["charged"]
    assert v["compression"] == 1.0 and v["observational"] == 0.7 and v["simplicity"] == 42.0 and v["compute"] == 4.0
    assert S.per_system_values(ver, res, truth_k=3)["compression"] == 0.0
    f = S.per_system_values(None, None)
    assert f["failed"] and f["EE"] == 10.0 and f["compression"] == 0.0 and f["A"] is False


def test_halving_keeps_the_better_half_and_the_carried_baseline():
    d = S.halve(["m1", "m2", "b1", "m3", "m4"], {"b1"}, eligible=["m1", "m2", "b1", "m3", "m4"])
    assert d["keep"] == ["m1", "m2", "b1"] and d["carried_baseline"] == "b1" and d["carried_eligible"]
    d = S.halve(["m1", "m2", "m3", "m4", "b1"], {"b1"}, eligible=["m1", "m2", "m3", "m4", "b1"])
    assert d["keep"] == ["m1", "m2", "m3", "b1"]
    d = S.halve(["m1", "m2", "m3", "b1", "b2"], {"b1", "b2"}, eligible=["m1", "m2", "m3", "b2"])
    assert d["carried_baseline"] == "b2" and "b2" in d["keep"]
    d = S.halve(["m1", "m2", "m3", "m4"], {"b1"}, carried_baseline="b1", finalists=3)
    assert d["keep"] == ["m1", "m2", "m3"]


# ------------------------------------------------------------------------------------------------------------ bootstrap
def test_rescaled_bootstrap_corrects_the_small_sample_shrinkage():
    rng = np.random.default_rng(0)
    v = {f"s{i}": float(x) for i, x in enumerate(rng.standard_normal(4))}
    naive = np.array([np.mean(rng.choice(list(v.values()), 4)) for _ in range(20000)]).std()
    est = S.rescaled_boot_mean(v, None, n_boot=20000, seed=1)
    assert 1.1 < est.reps.std() / naive < 1.25                           # ~ sqrt(4 / 3) = 1.155
    sample_sd = np.std(list(v.values()), ddof=1) / math.sqrt(4)
    assert abs(est.reps.std() / sample_sd - 1) < 0.05


def test_rescaled_bootstrap_never_uses_strata_of_size_one():
    v = {"a": 0.0, "b": 1.0, "c": 2.0, "r": 5.0}
    strata = {"a": "synthetic", "b": "synthetic", "c": "synthetic", "r": "real"}
    est = S.rescaled_boot_mean(v, strata, n_boot=4000, seed=0)
    assert est.ci95[1] - est.ci95[0] > 1.0                               # the lone real system is resampled (unstratified)
    assert math.isnan(S.rescaled_boot_mean({"a": 1.0}, None).ci95[0])


# ------------------------------------------------------------------------------------------------------------ pilot
def test_pilot_rule_is_deterministic():
    real = ["real:A:full", "real:A:m1", "real:A:m2", "real:B:full", "real:B:m1", "real:C:m1", "real:C:m2", "real:C:m3"]
    p = S.pilot_real(real)
    assert p == S.pilot_real(list(reversed(real))) and len(p) == 3 and all(":m" in s for s in p)
    types = {f"syn:{i:03d}": f"type{i // 2}" for i in range(50)}
    ps = S.pilot_synthetic(types)
    assert len(ps) == 25 and ps == S.pilot_synthetic(dict(reversed(list(types.items()))))
    assert len({types[s] for s in ps}) == 25


def test_compression_counts_k_consistent_with_the_draw_dimension():
    """LOG P4-D43: with per-trajectory parameter draws, k_true <= k <= k_true + d_draw counts as consistent."""
    ver = {"metrics": {"EE": {"point": 0.3}, "SMS": {"point": 0.05}, "ICG_y": {"point": 0.02}, "dimension": {"compact": True}},
           "verdict": {"criteria": {"A": {"pass": True}}, "category": "partially supported"}}
    res = {"k": 3, "compact_judged": True}
    assert S.per_system_values(ver, res, truth_k=2)["compression"] == 0.0                      # no draw dimension reported
    assert S.per_system_values(ver, res, truth_k=2, truth_d_draw=1)["compression"] == 1.0
    assert S.per_system_values(ver, res, truth_k=2, truth_d_draw=0)["compression"] == 0.0
    assert S.per_system_values(ver, {"k": 1, "compact_judged": True}, truth_k=2, truth_d_draw=3)["compression"] == 0.0   # k < k_true


def test_dimension_truth_reports_k_consistency():
    from brainir_causal.evaluate_truth import eval_dimension_truth
    d = eval_dimension_truth(3, (2, 4), {"k": 2, "d_draw": 2}, declared_no_compact=False)
    assert d["k_consistent"] is True and d["k_correct"] is False and d["d_draw"] == 2 and d["k_true_in_range"] is True
    assert eval_dimension_truth(5, None, {"k": 2, "d_draw": 2}, declared_no_compact=False)["k_consistent"] is False
    assert eval_dimension_truth(2, None, {"k": 2}, declared_no_compact=False)["k_consistent"] is True
