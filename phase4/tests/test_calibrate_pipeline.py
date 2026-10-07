"""Calibration of the verdict tolerances (brainir_causal.calibrate; PROTOCOL section 7 as rewritten after review E, M3): the tolerance
rule, the common percentile, the Fisher power rule, the power table and the CI-end verdicts on hand-made verdict inputs, and the whole
pipeline end to end on the toy synthetic system and on one real mechanism system (slow)."""

from __future__ import annotations

import json

import numpy as np
import pytest

from brainir_causal import calibrate as CAL
from brainir_causal.verdict import SUPPORTED

FAST = {"steps_one": 300, "steps_multi": 60, "readout_steps": 300}


def _vi(sms_up: float = 0.0, icg_up: float = 0.0, mev_up: float = 0.01, ee_up: float = 0.1, c_up: float = 0.0, fc_rate: float = 0.0,
        mev_testable: bool = True) -> dict:
    """Verdict inputs (the `verdict.collect_metrics` layout) of one model on one system: every criterion but the given ones passes."""
    return {"EE": {"point": 0.05, "ci95": [0.0, ee_up]}, "EE_vs_idshortcut": {"point": -0.2, "ci95": [-0.3, -0.1]},
            "EE_vs_fullbound": {"point": 0.0, "ci95": [-0.01, c_up]}, "SMS": {"point": 0.0, "ci95": [-0.05, sms_up]},
            "ICG_y": {"point": 0.0, "ci95": [-0.01, icg_up]}, "MEV": {"point": 0.005, "ci95": [0.0, mev_up]}, "MEV_testable": mev_testable,
            "false_confidence": {"rate": fc_rate, "n": 10}, "dimension": {"k": 2, "compact": True, "stable": True},
            "EE_heldout": {"point": 0.1, "ci95": [0.0, 0.2]}, "EE_infamily": {"point": 0.08, "ci95": [0.0, 0.2]},
            "EE_by_class": {c: {"point": 0.05} for c in ("weak", "moderate", "strong")},       # criterion A's class condition (M1)
            "declared_no_compact": False, "truth_noncompressible": None}


def _rows(n: int = 20, n_trap: int = 8, spread=(("sms", 0), ("icg", 1), ("mev", 2))) -> list[dict]:
    """n systems. The true state's D / ICG / MEV upper CIs are 0.01 x (rank + 1), with each criterion's two LARGEST values on distinct
    systems (so at p = 90 six systems fail one criterion each, at p = 95 three do); nulls and corruptions fail their criteria."""
    rows = []
    for i in range(n):
        vals = {"sms": 0.01 * (i + 1), "icg": 0.01 * (i + 1), "mev": 0.01 * (i + 1)}
        for name, shift in spread:                 # rotate the ranking so the top systems differ per criterion
            vals[name] = 0.01 * (((i + 2 * shift) % n) + 1)
        r = {"sid": f"s{i}", "compact_judged": True,
             "true_state": {"verdict_inputs": _vi(sms_up=vals["sms"], icg_up=vals["icg"], mev_up=vals["mev"])},
             "random_k": {"verdict_inputs": _vi(sms_up=0.9, icg_up=0.9, mev_up=0.9, ee_up=1.2)},
             "true_state_readin": {"verdict_inputs": _vi(sms_up=0.8, icg_up=vals["icg"], mev_up=vals["mev"])},
             "true_state_missing": {"verdict_inputs": _vi(sms_up=vals["sms"], icg_up=0.7, mev_up=0.8)}}
        if i < n_trap:
            r["obs_shortcut"] = {"verdict_inputs": _vi(sms_up=0.6, icg_up=0.5, mev_up=0.6)}
        rows.append(r)
    return rows


def test_tolerance_rule_is_the_protocols_percentiles():
    rows = _rows()
    for p in (90.0, 97.5):
        t = CAL.tolerance_rule(rows, p)
        v = 0.01 * np.arange(1, 21)
        assert t["tau_SMS"] == pytest.approx(np.percentile(v, p))
        assert t["tau_ICG"] == pytest.approx(np.percentile(v, p)) and t["tau_MEV"] == pytest.approx(np.percentile(v, p))
        assert t["delta_A"] == pytest.approx(max(0.1, 0.1 - 0.05))                    # upper - point = 0.05 everywhere
        assert t["delta_C"] == pytest.approx(0.05)                                     # the floor: upper CIs of the paired diff are 0
        assert t["delta_H"] == pytest.approx(0.1) and t["tau_FC"] == 0.2
    # delta_C uses the UPPER CI of the paired difference EE_truestate - EE_fullstate
    rows[0]["true_state"]["verdict_inputs"]["EE_vs_fullbound"]["ci95"][1] = 5.0
    assert CAL.tolerance_rule(rows, 99.0)["delta_C"] > 1.0


def test_power_rule_is_a_fisher_test_against_each_null_on_the_same_systems():
    rows = _rows()
    tol = CAL.tolerance_rule(rows, 95.0)
    pw = CAL.power_rule(rows, tol)
    assert pw["sms_binds"] and pw["icg_binds"] and pw["mev_binds"]
    assert pw["obs_shortcut"]["n_systems"] == 8 and pw["random_k"]["n_systems"] == 20
    assert pw["random_k"]["D"]["pass_a"] == 19 and pw["random_k"]["D"]["pass_b"] == 0 and pw["random_k"]["D"]["p_fisher"] < 1e-6
    # fewer than 6 trap systems: the power against the observational shortcut cannot be shown, nothing binds
    few = _rows(n_trap=5)
    pw2 = CAL.power_rule(few, CAL.tolerance_rule(few, 95.0))
    assert not (pw2["sms_binds"] or pw2["icg_binds"] or pw2["mev_binds"]) and "trap systems" in pw2["D_reason"]
    # a null that passes as often as the true state removes the power
    same = _rows()
    for r in same:
        r["random_k"] = {"verdict_inputs": dict(r["true_state"]["verdict_inputs"])}
    assert not CAL.power_rule(same, CAL.tolerance_rule(same, 95.0))["sms_binds"]
    assert CAL.fisher_greater(6, 6, 0, 6) < 0.01 and CAL.fisher_greater(3, 6, 3, 6) > 0.5


def test_common_percentile_is_the_smallest_reaching_80_percent():
    rows = _rows()
    cp = CAL.common_percentile(rows)
    rates = {t["p"]: t["true_state_supported_rate"] for t in cp["table"]}
    assert rates[90.0] == pytest.approx(0.7) and rates[95.0] == pytest.approx(0.85)
    assert cp["attainable"] and cp["chosen"]["p"] == 95.0 and cp["note"] is None


def test_unattainable_calibration_is_recorded():
    rows = _rows()
    for r in rows[:6]:                           # the true state is falsely confident on 30 % of the systems at every percentile
        r["true_state"]["verdict_inputs"]["false_confidence"] = {"rate": 0.5, "n": 10}
    cp = CAL.common_percentile(rows)
    assert not cp["attainable"] and cp["chosen"]["p"] == 99.0 and "not attainable" in cp["note"]


def test_calibrate_rows_records_power_table_and_ci_ends():
    rec = CAL.calibrate_rows(_rows(), n_boot=200)
    assert rec["percentile"]["chosen_p"] == 95.0 and rec["percentile"]["attainable"]
    assert rec["tolerances"]["sms_binds"] and rec["tolerances"]["mev_binds"]
    assert rec["verdicts_under_calibrated_tolerances"]["true_state"][SUPPORTED] == 17
    assert rec["verdicts_under_calibrated_tolerances"]["random_k"].get(SUPPORTED, 0) == 0
    pt = rec["power_table"]
    assert pt["true_state_readin"]["detects"]["D"] and not pt["true_state_readin"]["detects"]["E_icg"]
    assert pt["true_state_missing"]["detects"]["E_icg"] and pt["true_state_missing"]["detects"]["E"]
    assert not pt["true_state_missing"]["detects"]["D"]
    assert set(rec["verdicts_at_tolerance_ci_ends"]) >= {"tau_SMS_low", "tau_SMS_high", "delta_A_low"}
    assert rec["reference_dimension"]["stable"] is True and "asymmetry" in rec["reference_dimension"]["note"]
    assert rec["tolerance_ci_note"].startswith("descriptive")
    json.dumps(rec)


def test_readin_family_and_missing_coordinate():
    class It:
        def __init__(self, family):
            self.family = family
    pub = {"split": {"families_train": ["kick.1", "pulse.1", "sil.1"]}}
    items = [It("pulse.1")] * 3 + [It("kick.1")] * 3 + [It("sil.1")] * 9 + [It("kick.2")] * 9
    assert CAL.readin_family(pub, items) == "kick.1"                  # ties by name; silencing has no amplitude; kick.2 not trained
    assert CAL.readin_family(pub, [It("sil.1")]) is None
    z = {"a": np.column_stack([np.zeros(5), np.arange(5.0), np.ones(5)]), "b": np.column_stack([np.ones(3), np.arange(3.0), np.ones(3)])}
    assert CAL.missing_coordinate(z) == 1


def test_mde_paired():
    d = {f"s{i}": v for i, v in enumerate(np.random.default_rng(0).normal(0.0, 0.1, 50))}
    m = CAL.mde_paired(d)
    assert m["n"] == 50 and 0.02 < m["mde"] < 0.06


@pytest.mark.slow
def test_calibration_pipeline_on_toy_systems():
    from test_calibrate_toyinputs import toy_inputs

    from brainir_causal.evalio import TestItem
    rows = []
    for seed in (0, 1):
        inp = toy_inputs(seed=seed)
        it0 = inp["items"][0]
        # an item of a kind the true-state reference never trained (silencing): excluded from the calibration items, counted
        extra = TestItem(item_id="unsupported", system_id="toy", dt=it0.dt, x_hist=it0.x_hist, u_hist=it0.u_hist, u_future=it0.u_future,
                         events=[{"kind": "silence", "t0": 0.0, "t1": 0.1, "targets": [0]}], y_future=it0.y_future, y_twin=it0.y_twin,
                         family="sil.1", shift="far", group="gx")
        rows.append(CAL.calibrate_from_inputs("toy", pub=inp["pub"], sysc=inp["sysc"], train=inp["train"], items=inp["items"] + [extra],
                                              pool=inp["pool"], k_true=2, truth=inp["truth"], register=inp["register"], n_boot=200,
                                              learner=FAST))
    json.dumps(rows)                                              # JSON-serialisable rows
    for r in rows:
        assert not r["errors"], r["errors"]
        # unsupported: the silencing item (a kind never trained) and the items on units never intervened in training with that kind
        # (refs covers(): the true-state reference has no learned read-in there and abstains)
        assert r["n_supported_items"] <= r["n_verdict_items"] - 1 and r["unsupported_families"].get("sil.1") == 1
        assert r["abstention_share"] == pytest.approx(1.0 - r["n_supported_items"] / r["n_verdict_items"])
        assert r["missing_coordinate"] in (0, 1) and r["readin_family"] in ("kick.1", "pulse.1")
        ts, rk = r["true_state"]["verdict_inputs"], r["random_k"]["verdict_inputs"]
        assert ts["EE"]["point"] < 0.1 < rk["EE"]["point"]
        assert abs(r["no_effect"]["verdict_inputs"]["EE"]["point"] - 1.0) < 1e-3
        # the corruptions are fitted, scored, and actually corrupt the true state's intervention predictions (whether D / E detect
        # them is what the power table measures on the dev suite; the toy's 24 items are too few to test that here)
        for cor in ("true_state_readin", "true_state_missing"):
            assert r[cor]["verdict_inputs"]["EE"]["point"] > 10 * ts["EE"]["point"], cor
        assert r["true_state_readin"]["info"]["corrupted_family"] == r["readin_family"]
        assert r["true_state_missing"]["k"] == 1
    rec = CAL.calibrate_rows(rows, n_boot=200)
    assert rec["percentile"]["chosen_p"] in CAL.PERCENTILES and rec["n_systems"] == 2
    assert set(rec["verdicts_under_calibrated_tolerances"]) >= {"true_state", "random_k", "no_effect", "true_state_readin"}


def _real_mech_inputs(n_kick: int = 10, n_pulse: int = 6):
    """A reduced dataset of one real mechanism system simulated with the Phase 4 real engine."""
    from brainir_causal import protocol as P
    from brainir_causal import systems as SY
    from brainir_causal.evalio import Pool, PoolState, TestItem, make_eval_system
    from brainir_causal.realsim import RealEngine, observe
    pubs, ints = SY.load_real_public(), SY.load_real_internal()
    pubs, ints = pubs.get("systems", pubs), ints.get("systems", ints)
    sid = min(s for s in pubs if ":m" in s)
    pub, ir = pubs[sid], ints[sid]
    eng, sysobj = RealEngine(SY.BUNDLE, ir["network"]), SY.real_system(ir)
    tg = [int(t) for t in pub["targets_public"]]
    rng = np.random.default_rng(0)
    dt, T = 0.001, 2.0

    def sim(q):
        q = P.validate(q)
        rec = eng.run(sysobj, q)
        return rec, observe(rec, sysobj, q), q

    def base(seed):
        return {"system": sid, "params_seed": int(seed), "t_end": T, "dt": dt, "stimulus": [[0.0, 0.0], [0.02, float(rng.uniform(0.6, 1.4))]]}

    def event(kind, t0):
        u = int(rng.choice(tg))
        if kind == "kick":
            return {"kind": "kick", "t": t0, "delta": {str(u): float(rng.uniform(10, 40))}}
        if kind == "pulse":
            return {"kind": "current", "t0": t0, "t1": round(t0 + 0.1, 3), "targets": {str(u): float(rng.uniform(10, 50))}}
        a, b = rng.choice(tg, 2, replace=False)
        return {"kind": "silence", "t0": t0, "t1": round(t0 + 0.3, 3), "targets": [int(a), int(b)]}

    train = []
    for i in range(6):
        _, ob, q = sim(base(100 + i))
        train.append({"key": f"p{i}", "system_id": sid, "split": "train", "family": "obs.stim", "protocol": q, "meta": {}, **ob})
    for i in range(n_kick + n_pulse):
        q0 = dict(base(200 + i), events=[event("kick" if i < n_kick else "pulse", round(float(rng.uniform(0.3, 0.9)), 3))])
        _, ob, q = sim(q0)
        _, obt, qt = sim(P.counterfactual(q))
        train.append({"key": f"i{i}", "system_id": sid, "split": "train", "family": "", "protocol": q, "meta": {}, **ob})
        train.append({"key": f"t{i}", "system_id": sid, "split": "twin", "family": "", "protocol": qt, "meta": {"twin_of": f"i{i}"}, **obt})
    sysc = make_eval_system(sid, "real", dt, T, [r["x"] for r in train], [r["y"] for r in train], 1, compact=False)
    H = round(0.5 * T / dt)
    items, register = [], []
    for i, kind in enumerate(["kick"] * 8 + ["pulse"] * 4 + ["sil2"] * 4):
        t0 = round(float(rng.uniform(0.3, 0.9)), 3)
        _, ob, q = sim(dict(base(300 + i), events=[event(kind, t0)]))
        _, obt, _ = sim(P.counterfactual(q))
        i0 = round(t0 / dt)
        rel = [dict(e, **({"t": e["t"] - t0} if "t" in e else {"t0": e["t0"] - t0, "t1": e["t1"] - t0})) for e in q["events"]]
        items.append(TestItem(item_id=f"it{i}", system_id=sid, dt=dt, x_hist=ob["x"][: i0 + 1], u_hist=ob["u"][: i0 + 1],
                              u_future=ob["u"][i0: i0 + H + 1], events=rel, y_future=ob["y"][i0: i0 + H + 1], y_twin=obt["y"][i0: i0 + H + 1],
                              family={"kick": "kick.1", "pulse": "pulse.1", "sil2": "sil.2"}[kind],
                              shift=("near" if kind == "sil2" else "in"), group=f"g{i}", x_future=ob["x"][i0: i0 + H + 1],
                              x_twin_future=obt["x"][i0: i0 + H + 1], target_set=tuple(sorted(P.intervened_units(q)))))
        register += [{"x": ob["x"], "u": ob["u"], "y": ob["y"]}, {"x": obt["x"], "u": obt["u"], "y": obt["y"]}]
    Hf = round(0.25 * T / dt)
    seqs = {"none": [], "kick": [{"kind": "kick", "t": 0.0, "delta": {str(tg[0]): 30.0}}],
            "pulse": [{"kind": "current", "t0": 0.0, "t1": 0.1, "targets": {str(tg[-1]): 40.0}}]}
    states = []
    for j in range(3):
        rec, ob, q = sim(base(400 + j))
        register.append({"x": ob["x"], "u": ob["u"], "y": ob["y"]})
        for i in sorted(rng.choice(np.arange(400, 1400), size=4, replace=False)):
            fut, xf = {}, {}
            for name, evs in seqs.items():
                qf = {"system": sid, "params_seed": 400 + j, "t_end": Hf * dt, "dt": dt, "stimulus": [[0.0, 1.0]], "events": evs,
                      "r0": {"kind": "state", "values": {str(int(n)): float(v) for n, v in zip(rec["neurons"], rec["rates"][i])}}}
                _, of, _ = sim(qf)
                fut[name], xf[name] = of["y"].astype(float), of["x"].astype(float)
            states.append(PoolState(state_id=f"s{j}@{i}", x_hist=ob["x"][: i + 1], u_hist=ob["u"][: i + 1], y_now=ob["y"][i],
                                    traj=f"src{j}", draw=str(400 + j), futures=fut, x_futures=xf))
    pool = Pool(system_id=sid, dt=dt, states=states, sequences={n: {"events": e, "u_future": np.ones((Hf + 1, 1)), "family": n,
                                                                    "kind": (e[0]["kind"] if e else "none")} for n, e in seqs.items()})
    return sid, pub, sysc, train, items, pool, register




@pytest.mark.slow
def test_calibration_pipeline_on_a_real_mechanism_system():
    sid, pub, sysc, train, items, pool, register = _real_mech_inputs()
    row = CAL.calibrate_from_inputs(sid, pub=pub, sysc=sysc, train=train, items=items, pool=pool, k_true=2, truth=None,
                                    register=register, n_boot=200, learner=FAST)
    json.dumps(row)
    assert not row["errors"], row["errors"]
    assert "true_state" not in row and "obs_shortcut" not in row          # no truth for real systems
    assert row["n_supported_items"] == row["n_verdict_items"]             # without a true-state reference every verdict item is used
    for ref in ("full_state", "pca_k", "random_k", "no_effect", "id_shortcut"):
        ee = row[ref]["verdict_inputs"]["EE"]
        assert ee is not None and np.isfinite(ee["point"]), ref
    assert abs(row["no_effect"]["verdict_inputs"]["EE"]["point"] - 1.0) < 1e-3
