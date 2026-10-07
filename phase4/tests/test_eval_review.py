"""Regression tests for the early reviews E (statistics) and H (numerics) of the evaluator core, one or more per finding, on the
reviewers' own layout: the toy linear system with a known causal state (`test_lift_toysys.ToyLinear`), identity cells x 4 states per
family, the exact model and controlled corruptions of it."""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest
from brainir_causal import protocol as P
from brainir_causal.evalio import Pool, PoolState, TestItem, make_eval_system
from brainir_causal.evaluate import Prediction, ee_cb, eval_composition, eval_effects, predict_items
from brainir_causal.evaluate_mediation import (
    _lag_rows,
    eval_closure,
    eval_mediation,
    id_features,
    ridge_fit_predict,
    select_items,
)
from brainir_causal.evaluate_micro import EIG_FLOOR, eval_microstate, floor_statistic, whitener
from brainir_causal.evaluate_truth import attach_truth
from brainir_causal.verdict import Tolerances, collect_metrics, system_verdict
from test_lift_toysys import DT, T_END, ExactModel, ToyLinear, make_records, passive_protocol

NB = 200
NS = 5                        # cross-fitting seeds in tests (the protocol's 20 are the default)
H = round(0.5 * T_END / DT)


@pytest.fixture(scope="module")
def toy():
    s = ToyLinear(seed=0)
    train, _ = make_records(s, seed=0)
    sysc = make_eval_system("toy", "synthetic", DT, T_END, [r["x"] for r in train if r["split"] == "train"],
                            [r["y"] for r in train if r["split"] == "train"], 1)
    return s, sysc


def build(s, n_cells=8, states=4, pulse_amp=40.0, seed=1, shifts=("in", "near")):
    """Benchmark-like test items: families kick.1 / pulse.1, n_cells identity cells (one unit x one magnitude class) x `states`
    distinct states (review E's layout)."""
    rng = np.random.default_rng(seed)
    items, k = [], 0
    for fam, shift in zip(("kick.1", "pulse.1"), shifts):
        for c in range(n_cells):
            unit = int(rng.integers(0, s.n))
            sign = float(rng.choice([-1, 1]))
            mag = rng.choice([0.3, 1.0, 3.0]) if c else 1.0
            mclass = {0.3: "weak", 1.0: "moderate", 3.0: "strong"}[float(mag)]
            for st in range(states):
                base = passive_protocol(5000 + k + 1000 * seed, stim=float(rng.uniform(0.6, 1.4)), t_on=0.1)
                t_ev = round(float(rng.uniform(0.4, 0.9)), 2)
                if fam == "kick.1":
                    ev = {"kind": "kick", "t": t_ev, "delta": {str(unit): sign * mag * float(rng.uniform(0.8, 1.25))}}
                else:
                    ev = {"kind": "current", "t0": t_ev, "t1": round(t_ev + 0.1, 2),
                          "targets": {str(unit): sign * mag * pulse_amp / 3 * float(rng.uniform(0.8, 1.25))}}
                q = P.validate(dict(base, events=[ev]))
                ri, rt = s.simulate(q, full=True), s.simulate(P.counterfactual(q), full=True)
                i0 = round(t_ev / DT)
                rel = [dict(e, **({"t": e["t"] - t_ev} if "t" in e else {"t0": e["t0"] - t_ev, "t1": e["t1"] - t_ev})) for e in q["events"]]
                items.append(TestItem(item_id=f"it{seed}_{k}", system_id="toy", dt=DT, x_hist=ri["x"][: i0 + 1], u_hist=ri["u"][: i0 + 1],
                                      u_future=ri["u"][i0: i0 + H + 1], events=rel, y_future=ri["y"][i0: i0 + H + 1],
                                      y_twin=rt["y"][i0: i0 + H + 1], family=fam, shift=shift, magnitude_class=mclass,
                                      target_set=(unit,), onset=t_ev, group=f"g{k}", x_future=ri["x"][i0: i0 + H + 1],
                                      x_twin_future=rt["x"][i0: i0 + H + 1], z_true=ri["z"][i0], meta={"cell": f"{fam}|c{c}"}))
                k += 1
    return items


def variant(items, base, kind):
    """Controlled corruptions of the exact model's predictions (review E, med_demo2)."""
    out = {}
    for it in items:
        p = base[it.item_id]
        q = Prediction(item_id=it.item_id, y_int=p.y_int, y_base=p.y_base, abstain=p.abstain, z0=p.z0, z_int=p.z_int, z_base=p.z_base)
        if it.family == "pulse.1":
            if kind == "abstain_pulse":
                q.abstain = True
            elif kind.startswith("half_pulse"):
                q.y_int = p.y_base + 0.5 * (p.y_int - p.y_base)
            if kind == "half_pulse_hide":
                q.z0 = np.full_like(p.z0, np.nan)
        out[it.item_id] = q
    return out


class Trunc(ExactModel):
    """Encodes only the first of the two true state coordinates (a missing state; review E, B2)."""

    def encode(self, sid, x_hist, u_hist, dt):
        return super().encode(sid, x_hist, u_hist, dt)[:1]

    def rollout(self, sid, z0, u_future, events, dt):
        r = super().rollout(sid, np.r_[np.asarray(z0)[:1], 0.0], u_future, events, dt)
        r["z"] = r["z"][:, :1]
        return r


# ------------------------------------------------------------------------------------------------------------ E-B1
def test_E_B1_constant_training_column_does_not_change_predictions():
    """A column that is constant in the training rows (e.g. floating-point residue of a global standardisation, sd ~1e-16) is dropped
    in training AND test rows; it can never be divided by a tiny sd into huge test values."""
    rng = np.random.default_rng(0)
    Xtr, Xte = rng.normal(size=(60, 4)), rng.normal(size=(20, 4))
    y = Xtr @ np.array([1.0, -2.0, 0.5, 0.0]) + 0.1 * rng.normal(size=60)
    col = np.r_[np.zeros(60), np.ones(20)]
    col = (col - col.mean()) / col.std()                     # the review's mechanism: train values equal up to residue
    base = ridge_fit_predict(Xtr, y, Xte, 1e-3)
    with_col = ridge_fit_predict(np.c_[Xtr, col[:60]], y, np.c_[Xte, col[60:]], 1e-3)
    assert np.max(np.abs(base - with_col)) < 1e-10


def test_E_B1_sms_detects_readin_errors_on_the_benchmark_layout(toy):
    """Review E's table: with identity keys specific to a cell, SMS as implemented before was -1 for gross read-in errors."""
    s, sysc = toy
    items = build(s, n_cells=8)
    pe = predict_items(ExactModel(s), sysc, items)
    sms = {name: eval_mediation(sysc, items, pr, n_boot=NB, n_seeds=NS)["SMS"]
           for name, pr in (("exact", pe), ("abstain_pulse", variant(items, pe, "abstain_pulse")),
                            ("half_pulse", variant(items, pe, "half_pulse")))}
    assert abs(sms["exact"]["point"]) < 0.05
    for name in ("abstain_pulse", "half_pulse"):
        assert sms[name]["point"] > 0.5 and sms[name]["ci95"][0] > 0.3, (name, sms[name])


def test_E_B1_identity_columns_built_inside_the_fold(toy):
    s, _ = toy
    items = build(s, n_cells=2)
    tr = np.array([it.family == "kick.1" for it in items])
    _, names = id_features(items, 0.25, tr)
    assert not any(n.startswith("has:current|") or n == "family:pulse.1" for n in names)   # test-fold-only keys carry no column


# ------------------------------------------------------------------------------------------------------------ E-B2
def test_E_B2_missing_state_detected_by_linear_icg_and_sms_x_res_on_every_seed(toy):
    """The verdict consequence must not depend on the cross-fitting seed: the model missing a state coordinate fails E's ICG part
    (upper CI far above any small tau) and is flagged by SMS_x_res on every seed; the exact model passes (upper CI ~ 0)."""
    s, sysc = toy
    items = build(s, n_cells=15, seed=1)
    pr = predict_items(Trunc(s), sysc, items)
    pe = predict_items(ExactModel(s), sysc, items)
    for seed in (0, 11, 33):
        c = eval_closure(Trunc(s), sysc, items, pr, n_boot=NB, seed=seed, n_seeds=NS)
        m = eval_mediation(sysc, items, pr, n_boot=NB, seed=seed, n_seeds=NS)
        assert c["ICG_y"]["regressor"] == "linear"
        assert c["ICG_y"]["point"] > 0.15 and c["ICG_y"]["ci95"][1] > 0.3, (seed, c["ICG_y"])
        assert m["SMS_x_res"]["point"] > 0.3 and m["SMS_x_res"]["ci95"][0] > 0.0, (seed, m["SMS_x_res"])
        ce = eval_closure(ExactModel(s), sysc, items, pe, n_boot=NB, seed=seed, n_seeds=NS)
        assert ce["ICG_y"]["ci95"][1] < 0.02, (seed, ce["ICG_y"])
    assert "seed_sd" in c["ICG_y"] and c["ICG_y"]["n_seeds"] == NS


def test_E_B2_ci_contains_the_cross_fitting_variability(toy):
    """The CI replicates redraw the cross-fitting seed: the CI is at least as wide as the spread of the per-seed gains."""
    s, sysc = toy
    items = build(s, n_cells=10, seed=2)
    pr = predict_items(Trunc(s), sysc, items)
    m = eval_mediation(sysc, items, pr, n_boot=400, n_seeds=8)
    est = m["_estimates"]["SMS"]
    assert est.extra["n_seeds"] == 8
    assert (m["SMS"]["ci95"][1] - m["SMS"]["ci95"][0]) >= 2 * m["SMS"]["seed_sd"]


# ------------------------------------------------------------------------------------------------------------ E-B3
def test_E_B3_unusable_items_fail_sms_and_icg(toy):
    """Review E, B3 / N3. NaN latents exactly where the read-in is wrong cannot hide the error: such items are LATENT-MISSING and stay
    in both regressions (their residual microstate from u alone), so SMS still sees the read-in error; failed PREDICTIONS are
    unusable, and more than 1 % of them fail D and E."""
    s, sysc = toy
    items = build(s, n_cells=8)
    pe = predict_items(ExactModel(s), sysc, items)
    half = eval_mediation(sysc, items, variant(items, pe, "half_pulse"), n_boot=NB, n_seeds=NS)
    hide = variant(items, pe, "half_pulse_hide")
    m = eval_mediation(sysc, items, hide, n_boot=NB, n_seeds=NS)
    assert not m.get("failed_unusable") and m["n_unusable"] == 0 and m["n_latent_missing"] == 32 and m["n_items"] == 64
    assert m["SMS"]["point"] > 0.5 and m["SMS"]["ci95"][0] > 0.0                    # the read-in error is still detected
    assert abs(m["SMS"]["point"] - half["SMS"]["point"]) < 0.2                        # hiding the latents buys nothing
    c = eval_closure(ExactModel(s), sysc, items, hide, n_boot=NB, n_seeds=NS)
    assert not c.get("failed_unusable") and c["ICG_y"]["point"] > 0.1                 # the missing latents are charged to closure
    failed = dict(pe)
    for it in items[:2]:                                                              # 2 of 64 predictions fail (3 % > 1 %)
        failed[it.item_id] = dataclasses.replace(pe[it.item_id], y_int=np.full_like(pe[it.item_id].y_int, np.nan))
    mf = eval_mediation(sysc, items, failed, n_boot=NB, n_seeds=NS)
    assert mf["failed_unusable"] and mf["SMS"]["point"] == 1.0 and mf["n_unusable"] == 2
    cf = eval_closure(ExactModel(s), sysc, items, failed, n_boot=NB, n_seeds=NS)
    assert cf["failed_unusable"] and cf["ICG_y"]["point"] == 1.0
    one = dict(pe)
    first = items[0].item_id
    one[first] = dataclasses.replace(pe[first], z0=np.full_like(pe[first].z0, np.nan))
    m1 = eval_mediation(sysc, items, one, n_boot=NB, n_seeds=NS)
    assert not m1.get("failed_unusable") and m1["n_unusable"] == 0 and m1["n_latent_missing"] == 1 and m1["n_items"] == 64


# ------------------------------------------------------------------------------------------------------------ E-B4 / H-B1
def _pool(s, sysc, n_draws=2, n_traj=8, per=5, seed=4, floor_eps=0.0):
    rng = np.random.default_rng(seed)
    seqs = {"none": {"events": [], "kind": "none"},
            "kick": {"events": [{"kind": "kick", "t": 0.0, "delta": {"0": 1.5}}], "kind": "kick"}}
    states = []
    Hp = round(0.25 * T_END / DT)
    for d in range(n_draws):
        for tr in range(n_traj):
            q = P.validate(passive_protocol(9000 + 100 * d + tr, stim=float(rng.uniform(0.6, 1.4)), t_on=0.1))
            r = s.simulate(q, full=True)
            for j in range(per):
                i = int(rng.integers(40, 150))
                fut = {}
                for name, sq in seqs.items():
                    st = {str(u): float(v) for u, v in enumerate(r["state"][i])}
                    qq = P.validate({"system": "toy", "params_seed": 9000 + 100 * d + tr, "t_end": Hp * DT, "dt": DT,
                                     "stimulus": [[0.0, 0.0]], "events": sq["events"], "r0": {"kind": "state", "values": st}})
                    fut[name] = s.simulate(qq)["y"]
                ff = {"noop": [fut["none"], fut["none"] + floor_eps], "f32": [fut["none"], fut["none"].astype(np.float32).astype(float)]}
                states.append(PoolState(state_id=f"d{d}t{tr}s{j}", x_hist=r["x"][: i + 1], u_hist=r["u"][: i + 1], y_now=r["y"][i],
                                        traj=f"d{d}t{tr}", draw=f"d{d}", futures=fut, floor_futures=ff if (tr + j) % 4 == 0 else None))
    for sq in seqs.values():
        sq["u_future"] = np.zeros((Hp + 1, 1))
    return Pool(system_id="toy", dt=DT, states=states, sequences=seqs)


def _scaled(pool, sysc, c):
    st = [dataclasses.replace(p, y_now=p.y_now * c, futures={k: v * c for k, v in p.futures.items()},
                              floor_futures=None if p.floor_futures is None else {k: [a * c, b * c] for k, (a, b) in p.floor_futures.items()})
          for p in pool.states]
    return dataclasses.replace(pool, states=st), dataclasses.replace(sysc, y_sd=sysc.y_sd * c)


def test_H_B1_scaling_y_does_not_change_testability_or_mev(toy):
    s, sysc = toy
    pool = _pool(s, sysc, floor_eps=0.02)
    a = eval_microstate(ExactModel(s), sysc, pool, n_boot=NB)
    for c in (0.1, 10.0):
        pc, sc = _scaled(pool, sysc, c)
        b = eval_microstate(ExactModel(s), sc, pc, n_boot=NB)
        assert b["testable"] == a["testable"]
        assert b["numerical_floor"] == pytest.approx(a["numerical_floor"], rel=1e-9)
        assert b["MEV"]["point"] == pytest.approx(a["MEV"]["point"], rel=1e-9)


def test_H_B1_floor_uses_the_divergence_statistic(toy):
    """floor = mean over floor states of the mean squared difference in readout-sd units over rows 1..m, max over the two kinds."""
    s, sysc = toy
    pool = _pool(s, sysc, floor_eps=0.05)
    fl = floor_statistic(pool, sysc)
    assert fl["source"] == "floor_futures" and set(fl["per_kind"]) == {"noop", "f32"}
    assert fl["per_kind"]["noop"] == pytest.approx((0.05 / sysc.y_sd) ** 2, rel=1e-9)
    assert fl["floor"] == max(fl["per_kind"].values())


def test_H_B1_detection_floor_makes_a_nondiverging_pool_untestable(toy):
    """With a deterministic generator the numerical floor is 0; a pool whose random pairs diverge less than (2 f_s / y_sd)^2 = 0.01
    is still untestable."""
    s, sysc = toy
    pool = _pool(s, sysc)
    tiny = dataclasses.replace(pool, states=[dataclasses.replace(p, futures={k: v * 1e-3 for k, v in p.futures.items()}, floor_futures=None)
                                             for p in pool.states])
    r = eval_microstate(ExactModel(s), sysc, tiny, n_boot=NB)
    assert r["numerical_floor"] == 0.0 and not r["testable"] and "detection floor" in r["untestable_reason"]


def test_H_minor11_whitening_floor():
    A = np.random.default_rng(0).normal(size=(200, 3))
    A[:, 2] *= 1e-9                                          # a near-degenerate latent coordinate
    _, W = whitener(A)
    assert EIG_FLOOR == 1e-6 and np.abs(W).max() < 1.1 / np.sqrt(1e-6 * np.var(A[:, 0]))


# ------------------------------------------------------------------------------------------------------------ E-M1 / E-M2
def test_E_M1_class_balanced_ee_is_not_dominated_by_strong_items(toy):
    """A model exact on strong items and predicting no effect elsewhere passes a pooled EE; the class-balanced verdict EE fails A.
    The toy has 2 families; the benchmark has 12-24, so every cell is given its own family here (classes are merged by FAMILIES,
    review E round 3, N-new-4). With the toy's own 2 families there is no interval at all (too few families): A cannot pass."""
    s, sysc = toy
    items = build(s, n_cells=15, seed=3)
    pe = predict_items(ExactModel(s), sysc, items)
    pr = {k: Prediction(item_id=k, y_int=(p.y_int if it.magnitude_class == "strong" else p.y_base), y_base=p.y_base, z0=p.z0)
          for (k, p), it in zip(pe.items(), items)}
    eff2 = eval_effects(sysc, items, pr, n_boot=NB)
    two = ee_cb(eff2["_units"], n_boot=NB)
    assert not np.isfinite(two.ci95[1]) and "too few families" in two.extra["method"]
    for it in items:
        it.family = it.meta["cell"]
    eff = eval_effects(sysc, items, pr, n_boot=NB)
    cb = ee_cb(eff["_units"], n_boot=NB)
    assert eff["EE_medium"]["point"] < 0.6 < cb.point
    m = collect_metrics(eff, n_boot=NB)
    assert m["EE"]["point"] == pytest.approx(cb.point) and m["EE"]["n_cells"] == 30


def test_E_M2_identity_cells_are_the_resampling_unit(toy):
    s, sysc = toy
    items = build(s, n_cells=8)
    eff = eval_effects(sysc, items, predict_items(Trunc(s), sysc, items), n_boot=NB)
    assert eff["EE_medium"]["n_cells"] == 16 and eff["n_cells"] == 16
    assert eff["EE_cb_medium"]["n_cells"] == 16


def test_verdict_items_exclude_ood_and_robustness(toy):
    """PROTOCOL 9: OOD / robustness items never enter a verdict criterion."""
    s, sysc = toy
    items = build(s, n_cells=6)
    pe = predict_items(ExactModel(s), sysc, items)
    ood = [dataclasses.replace(it, item_id=it.item_id + "o", shift="ood:timing", meta={"cell": "ood|" + it.meta["cell"]}) for it in items]
    pr = {**pe, **{it.item_id: dataclasses.replace(pe[it.item_id[:-1]], y_int=pe[it.item_id[:-1]].y_base * np.nan) for it in ood}}
    eff = eval_effects(sysc, items + ood, pr, n_boot=NB)
    m = collect_metrics(eff, n_boot=NB)
    plain = collect_metrics(eval_effects(sysc, items, pe, n_boot=NB), n_boot=NB)
    assert m["EE"]["point"] == pytest.approx(plain["EE"]["point"], rel=1e-12)   # the failed OOD items change nothing
    assert m["EE"]["point"] < 0.01 and eff["EE_medium"]["point"] > 1.0         # while the pooled descriptive EE counts them


def test_M1_true_state_passes_A_and_a_strong_only_model_fails_its_class_condition(toy):
    """Review E round 3, M1 (rule R3p): criterion A also needs the POINT EE of every merged magnitude class < 1 - delta_A. On the toy
    (every cell its own family, as in the benchmark's 12-24 families): the exact true-state model passes A; a model exact on the strong
    items only fails A by the class condition at a threshold where its class-balanced interval alone would pass."""
    s, sysc = toy
    items = build(s, n_cells=15, seed=3)
    for it in items:
        it.family = it.meta["cell"]
    pe = predict_items(ExactModel(s), sysc, items)
    pr = {k: Prediction(item_id=k, y_int=(p.y_int if it.magnitude_class == "strong" else p.y_base), y_base=p.y_base, z0=p.z0)
          for (k, p), it in zip(pe.items(), items)}
    m_strong = collect_metrics(eval_effects(sysc, items, pr, n_boot=NB), n_boot=NB)
    ub, worst = m_strong["EE"]["ci95"][1], max(v["point"] for v in m_strong["EE_by_class"].values())
    assert ub < worst                                                   # the strong class pulls the balanced mean below its worst class
    thr = 0.5 * (ub + worst)
    tol = Tolerances(delta_A=1.0 - thr, delta_C=0.05, tau_SMS=0.1, tau_ICG=0.1, tau_MEV=0.3, delta_H=0.1)
    a = system_verdict(m_strong, tol)["criteria"]["A"]
    assert a["pass"] is False and "class condition of A" in a["note"]
    assert system_verdict(m_strong, tol, a_every_class=False)["criteria"]["A"]["pass"] is True     # the interval alone passes
    m_exact = collect_metrics(eval_effects(sysc, items, pe, n_boot=NB), n_boot=NB)
    assert all(v["point"] < 1.0 - tol.delta_A for v in m_exact["EE_by_class"].values())
    assert system_verdict(m_exact, tol)["criteria"]["A"]["pass"] is True
    assert system_verdict(m_exact, Tolerances(delta_A=0.1, delta_C=0.05, tau_SMS=0.1, tau_ICG=0.1, tau_MEV=0.3,
                                              delta_H=0.1))["criteria"]["A"]["pass"] is True


# ------------------------------------------------------------------------------------------------------------ E-M5
def test_E_M5_verdict_path_computes_F_from_seeds_or_refits(toy):
    s, sysc = toy
    items = build(s, n_cells=4)
    eff = eval_effects(sysc, items, predict_items(ExactModel(s), sysc, items), n_boot=NB)
    m = collect_metrics(eff, n_boot=NB, k=2, compact_limit=1, k_values=[2, 2, 2], k_range=(2, 2), level="B")
    assert m["dimension"]["stable"] is True and m["dimension"]["compact"] is False
    tol = Tolerances(delta_A=0.1, delta_C=0.05, tau_SMS=0.1, tau_ICG=0.1, tau_MEV=0.3, delta_H=0.1)
    assert system_verdict(m, tol)["criteria"]["F"]["pass"] is False
    m2 = collect_metrics(eff, n_boot=NB, k=2, compact_limit=5, k_values=[2, 2, 2, 2, 2], level="C")
    assert system_verdict(m2, tol)["criteria"]["F"]["pass"] is True


# ------------------------------------------------------------------------------------------------------------ E-M7
def test_E_M7_paired_item_comparison_charges_missing_items(toy):
    from brainir_causal.evaluate import ee_cb_diff
    s, sysc = toy
    items = build(s, n_cells=4)
    pe = predict_items(ExactModel(s), sysc, items)
    ea = eval_effects(sysc, items, pe, n_boot=NB)
    eb = eval_effects(sysc, items[:-4], pe, n_boot=NB)                # model b did not score the last cell
    d = ee_cb_diff(ea["_units"], eb["_units"], n_boot=NB)
    assert d.n_charged == 4 and d.point < 0


# ------------------------------------------------------------------------------------------------------------ H-M1 / H-M4
def test_H_M1_horizons_per_item_dt(toy):
    s, sysc = toy
    items = build(s, n_cells=2)
    it2 = dataclasses.replace(items[0], dt=2 * DT)
    _, _, rL, rf = _lag_rows([items[0], it2], sysc)
    m1, m2 = sysc.horizon_steps("medium", DT), sysc.horizon_steps("medium", 2 * DT)
    assert m2 == m1 // 2 + (m1 % 2 > 0) or m2 == round(m1 / 2)
    assert list(rL[:5]) == [max(1, round(m1 * j / 5)) for j in range(1, 6)]
    assert list(rL[5:]) == [max(1, round(m2 * j / 5)) for j in range(1, 6)]
    assert np.allclose(rf[4], 1.0) and np.allclose(rf[9], 1.0)


def test_H_M4_nonfinite_truth_is_dropped_and_counted(toy):
    s, sysc = toy
    items = build(s, n_cells=4)
    pe = predict_items(ExactModel(s), sysc, items)
    bad = items[3]
    y = bad.y_future.copy()
    y[10:] = np.nan
    items2 = items[:3] + [dataclasses.replace(bad, y_future=y)] + items[4:]
    eff = eval_effects(sysc, items2, pe, n_boot=NB)
    assert eff["n_dropped_nonfinite_truth"] == 1 and eff["n_items"] == len(items) - 1
    ref = eval_effects(sysc, items[:3] + items[4:], pe, n_boot=NB)
    assert np.isfinite(eff["EE_long"]["point"]) and eff["EE_long"]["point"] == pytest.approx(ref["EE_long"]["point"], rel=1e-12)
    sel = select_items(sysc, items2, pe)
    assert sel["n_dropped_nonfinite_truth"] == 1
    comp = eval_composition(ExactModel(s), sysc, items2, pe, eff, n_boot=NB)
    assert comp["n_items"] == 0


# ------------------------------------------------------------------------------------------------------------ minors
def test_H_minor6_attach_truth_uses_the_true_events(toy):
    """dz_true of an amplitude-jitter item uses the simulated event, not the told one; a timing-jitter item acting after the onset gets
    no dz_true."""
    s, _ = toy

    class Sys:
        def true_state(self, st):
            return s.C @ np.asarray(st)

        def obs_shortcut_state(self, st):
            return None

        def true_latent_effect(self, st, ev):
            dx = np.zeros(s.n)
            for u, v in ev["delta"].items():
                dx[int(u)] += float(v)
            return s.C @ dx

    it = build(s, n_cells=1, states=1)[0]
    told = {"kind": "kick", "t": 0.0, "delta": {"0": 1.0}}
    true = {"kind": "kick", "t": 0.0, "delta": {"0": 1.2}}
    a = dataclasses.replace(it, events=[told], true_events=[true], dz_true=None, meta={"state": np.ones(s.n)})
    attach_truth(Sys(), [a])
    assert np.allclose(a.dz_true, Sys().true_latent_effect(None, true))
    b = dataclasses.replace(it, events=[told], true_events=[dict(true, t=2 * DT)], dz_true=None, meta={"state": np.ones(s.n)})
    attach_truth(Sys(), [b])
    assert b.dz_true is None


def test_untestable_mev_is_nan_with_its_reason_and_testable_bounds_are_finite(toy):
    """An untestable MEV reports NaN (never +-inf) with the reason (its descriptive value is reported apart); non-finite bootstrap
    replicates of a testable MEV are charged the worst admissible value, so its bounds stay finite (PROTOCOL 11)."""
    s, sysc = toy
    pool = _pool(s, sysc)
    tiny = dataclasses.replace(pool, states=[dataclasses.replace(p, futures={k: v * 1e-3 for k, v in p.futures.items()}, floor_futures=None)
                                             for p in pool.states])
    r = eval_microstate(ExactModel(s), sysc, tiny, n_boot=NB)
    assert not r["testable"] and np.isnan(r["MEV"]["point"]) and all(np.isnan(r["MEV"]["ci95"])) and r["MEV"]["untestable"]
    assert np.all(np.isfinite(r["MEV_descriptive"]["ci95"]) | np.isnan(r["MEV_descriptive"]["ci95"]))
    t = eval_microstate(ExactModel(s), sysc, pool, n_boot=NB)
    assert t["testable"] and np.all(np.isfinite(t["MEV"]["ci95"]))
    from brainir_causal.stats import make_estimate
    e = make_estimate(0.1, np.r_[np.linspace(0.0, 0.2, 90), [np.nan] * 10], 5, worst=10.0)
    assert np.all(np.isfinite(e.ci95)) and e.ci95[1] == 10.0 and e.n_nonfinite_reps == 10
