"""Calibration of the verdict tolerances (brainir_causal.calibrate; PROTOCOL section 7): the tolerance and power rules on hand-made
rows, and the whole pipeline end to end on the toy synthetic system and on one real mechanism system."""

from __future__ import annotations

import json

import numpy as np
import pytest

from brainir_causal import calibrate as CAL

FAST = {"steps_one": 300, "steps_multi": 60, "readout_steps": 300}


def _row(i: int, trap: bool = True) -> dict:
    """A hand-made per-system row: true-state EE point 0.01 i with CI width 0.02 i, full-state EE 0.005 i, SMS upper 0.01 i, ICG
    upper 0.002 i, MEV upper 0.03 i (testable on even i), EE held-out 0.1 + 0.02 i vs in-family 0.1."""
    t = {"EE": {"point": 0.01 * i, "ci95": [0.0, 0.03 * i]}, "SMS": {"point": 0.0, "ci95": [-0.01, 0.01 * i]},
         "ICG_y": {"point": 0.0, "ci95": [-0.01, 0.002 * i]}, "MEV": {"point": 0.01, "ci95": [0.0, 0.03 * i]}, "MEV_testable": i % 2 == 0,
         "EE_heldout": {"point": 0.1 + 0.02 * i, "ci95": [0, 1]}, "EE_infamily": {"point": 0.1, "ci95": [0, 1]}}
    r = {"sid": f"s{i}", "true_state": t, "full_state": {"EE": {"point": 0.005 * i, "ci95": [0, 1]}},
         "random_k": {"SMS": {"point": 0.5, "ci95": [0.3, 0.7]}, "ICG_y": {"point": 0.0, "ci95": [-0.01, 0.002 * i]}}}
    if trap:
        r["obs_shortcut"] = {"SMS": {"point": 0.4, "ci95": [0.2, 0.6]}, "ICG_y": {"point": 0.0, "ci95": [-0.01, 0.0]}}
    return r


def test_tolerance_rule_is_the_protocols_percentiles():
    rows = [_row(i) for i in range(1, 11)]
    t = CAL.tolerance_rule(rows)
    i = np.arange(1, 11)
    assert t["delta_A"] == pytest.approx(max(0.1, np.percentile(0.02 * i, 90)))
    assert t["delta_C"] == pytest.approx(max(0.05, np.percentile(0.005 * i, 90)))
    assert t["tau_SMS"] == pytest.approx(np.percentile(0.01 * i, 90))
    assert t["tau_ICG"] == pytest.approx(np.percentile(0.002 * i, 90))
    assert t["tau_MEV"] == pytest.approx(np.percentile(0.03 * i[i % 2 == 0], 90))
    assert t["delta_H"] == pytest.approx(max(0.1, np.percentile(0.02 * i, 90)))
    ci = CAL.tolerance_cis(rows, n_boot=200)
    assert all(ci[k][0] <= ci[k][1] for k in CAL.TOL_KEYS)


def test_power_rule_binds_only_with_both_nulls_well_below():
    rows = [_row(i) for i in range(1, 11)]
    tau = CAL.tolerance_rule(rows)["tau_SMS"]
    pw = CAL.power_rule(rows, "SMS", tau)
    assert pw["pass_rate"]["true_state"] == pytest.approx(0.9) and pw["pass_rate"]["random_k"] == 0.0 and pw["binds"]
    # ICG: random-k passes as often as the true state -> no power -> not binding
    assert not CAL.power_rule(rows, "ICG_y", CAL.tolerance_rule(rows)["tau_ICG"])["binds"]
    # no trap system -> the observational null is missing -> not binding (conservative)
    assert not CAL.power_rule([_row(i, trap=False) for i in range(1, 11)], "SMS", tau)["binds"]


def _vi(ee_up: float, sms_up: float = 0.0) -> dict:
    return {"EE": {"point": ee_up / 2, "ci95": [0, ee_up]}, "EE_vs_idshortcut": {"point": -0.2, "ci95": [-0.3, -0.1]},
            "EE_vs_fullbound": {"point": 0.0, "ci95": [-0.01, 0.01]}, "SMS": {"point": 0.0, "ci95": [-0.02, sms_up]},
            "ICG_y": {"point": 0.0, "ci95": [-0.01, 0.0]}, "MEV": {"point": 0.01, "ci95": [0, 0.02]}, "MEV_testable": True,
            "false_confidence": {"rate": 0.0, "n": 5}, "dimension": {"k": 2, "compact": True, "stable": True},
            "EE_heldout": {"point": 0.1, "ci95": [0, 0.2]}, "EE_infamily": {"point": 0.08, "ci95": [0, 0.2]},
            "declared_no_compact": False, "truth_noncompressible": None}


def test_judge_counts_verdict_categories():
    tol = {"delta_A": 0.1, "delta_C": 0.05, "tau_SMS": 0.05, "tau_ICG": 0.05, "tau_MEV": 0.05, "delta_H": 0.1, "tau_FC": 0.2,
           "sms_binds": True, "icg_binds": True}
    rows = [{"true_state": {"verdict_inputs": _vi(0.2)}}, {"true_state": {"verdict_inputs": _vi(0.2, sms_up=0.3)}},
            {"true_state": {"verdict_inputs": _vi(1.5)}}]
    counts = CAL.judge(rows, tol)["true_state"]
    assert counts == {"causal state supported": 1, "partially supported": 1, "unsupported": 1}


def test_mde_paired():
    d = {f"s{i}": v for i, v in enumerate(np.random.default_rng(0).normal(0.0, 0.1, 50))}
    m = CAL.mde_paired(d)
    assert m["n"] == 50 and 0.02 < m["mde"] < 0.06


@pytest.mark.slow
def test_calibration_pipeline_on_toy_systems():
    from test_calibrate_toyinputs import toy_inputs
    rows = []
    for seed in (0, 1):
        inp = toy_inputs(seed=seed)
        rows.append(CAL.calibrate_from_inputs("toy", pub=inp["pub"], sysc=inp["sysc"], train=inp["train"], items=inp["items"],
                                              pool=inp["pool"], k_true=2, truth=inp["truth"], register=inp["register"], n_boot=200,
                                              learner=FAST))
    json.dumps(rows)                                              # JSON-serialisable rows
    for r in rows:
        assert not r["errors"], r["errors"]
        assert r["true_state"]["EE"]["point"] < 0.1 < r["random_k"]["EE"]["point"]
        assert abs(r["no_effect"]["EE"]["point"] - 1.0) < 1e-3
        assert r["true_state"]["SMS"]["point"] < r["obs_shortcut"]["SMS"]["point"]      # the wrong latent leaves intervention info
    rec = CAL.tolerances_from_rows(rows, n_boot=200)
    tol = rec["tolerances"]
    assert all(np.isfinite(tol[k]) for k in ("delta_A", "delta_C", "tau_SMS", "tau_ICG", "delta_H"))
    assert set(rec["verdicts_under_calibrated_tolerances"]) >= {"true_state", "random_k", "no_effect"}


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
    for ref in ("full_state", "pca_k", "random_k", "no_effect", "id_shortcut"):
        assert row[ref]["EE"] is not None and np.isfinite(row[ref]["EE"]["point"]), ref
    assert abs(row["no_effect"]["EE"]["point"] - 1.0) < 1e-3
    assert row["full_state"]["EE"]["point"] < 1.0                         # the full state predicts intervention effects
