"""Benchmark references (brainir_causal.refs; PROTOCOL section 8) on the toy linear system with a known causal state."""

from __future__ import annotations

import numpy as np
import pytest
from test_lift_toysys import DT, ToyLinear, make_records, passive_protocol

from brainir_causal import protocol as P
from brainir_causal import refs as R
from brainir_causal.evaluate_lift import LiftConfig, eval_native_lift

FAST = R.LearnerConfig(steps_one=400, steps_multi=60, readout_steps=400)


@pytest.fixture(scope="module")
def toy():
    s = ToyLinear()
    train, truth = make_records(s, seed=0)
    test, ttruth = make_records(s, n_passive=4, n_kick=10, n_pulse=4, seed=5)
    return s, train, truth, test, ttruth


def _effect_error(m, test, h: int = 25) -> float:
    by = {r["key"]: r for r in test}
    num = den = 0.0
    for r in test:
        tw = r["meta"].get("twin_of")
        if not tw:
            continue
        ri = by[tw]
        ev = ri["protocol"]["events"]
        t0 = min(P.event_start(e) for e in ev)
        i0 = round(t0 / DT)
        rel = [dict(e, **({"t": e["t"] - t0} if "t" in e else {"t0": e["t0"] - t0, "t1": e["t1"] - t0})) for e in ev]
        out = m.intervention_effect("toy", ri["x"][: i0 + 1], ri["u"][: i0 + 1], ri["u"][i0: i0 + h + 1], rel, DT)
        true = ri["y"][i0 + 1: i0 + h + 1] - r["y"][i0 + 1: i0 + h + 1]
        num += float(np.sum((out["effect"][1: h + 1] - true) ** 2))
        den += float(np.sum(true ** 2))
    return num / den


def test_true_state_reference_recovers_the_toy(toy):
    s, train, truth, test, ttruth = toy
    m = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    m.register_records(test, ttruth["z"])
    assert _effect_error(m, test) < 0.05
    assert m.info()["k"]["toy"] == 2 and m.info()["fit_notes"]["kick_pairs"] == 24
    # registered histories encode exactly; an unregistered history falls back to the probe (counted)
    r = test[0]
    assert np.allclose(m.encode("toy", r["x"][:51], r["u"][:51], DT), ttruth["z"][r["key"]][50])
    before = m.n_probe_encodes
    m.encode("toy", r["x"][:51] + 1e-3, r["u"][:51], DT)
    assert m.n_probe_encodes == before + 1


def test_random_projection_is_worse_than_pca_and_no_effect_is_one(toy):
    s, train, _truth, test, _ = toy
    pca = R.fit_reference("pca_k", "toy", train, s.record(), k=2, cfg=FAST)
    rnd = R.fit_reference("random_k", "toy", train, s.record(), k=2, cfg=FAST)
    e_pca, e_rnd = _effect_error(pca, test), _effect_error(rnd, test)
    assert e_pca < 0.1 < e_rnd
    ne = R.NoEffectModel(pca)
    assert abs(_effect_error(ne, test) - 1.0) < 1e-12


def test_full_state_reference_is_informative(toy):
    s, train, _truth, test, _ = toy
    m = R.fit_reference("full_state", "toy", train, s.record(), cfg=FAST)
    assert _effect_error(m, test) < 0.5
    z0 = m.encode("toy", test[0]["x"][:41], test[0]["u"][:41], DT)
    assert z0.shape == (5 * (1 + len(FAST.trace_fracs)),)
    # read-in of a kick: the identity prior plus the correction learned from the training kicks' one-step effect (one step of the
    # toy's dynamics, a few percent): close to the kick itself on the current block, nothing on the traces
    rin = m.read_in("toy", z0, {"kind": "kick", "t": 0.0, "delta": {"2": 1.5}})
    assert np.allclose(rin["dz"][:5], [0, 0, 1.5, 0, 0], atol=0.25) and not rin["dz"][5:].any()


def test_id_shortcut_learns_seen_identities(toy):
    s, train, _truth, test, _ = toy
    m = R.fit_reference("id_shortcut", "toy", train, s.record(), cfg=FAST)
    m.register_records(test)
    assert _effect_error(m, test) < 0.6
    assert m.supports("toy", "kick") and m.info()["n_ids"] > 0


def test_true_state_native_lift_realises_requested_shifts(toy):
    s, train, truth, _, _ = toy
    m = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    cases = []
    for i in range(3):
        q = passive_protocol(300 + i)
        x = s.simulate(q)["x"][70]
        cases.append({"protocol": q, "t": 0.7, "r0": {"kind": "state", "values": {str(u): float(v) for u, v in enumerate(x)}}})
    hists = [(r["x"][: i + 1], r["u"][: i + 1], DT) for r in train[:12] for i in (60, 120)]     # public training histories
    res = eval_native_lift(m, "toy", cases, s.simulate_many, horizon_s=0.25, floor=0.01, truth=True, cfg=LiftConfig(n_boot=100),
                           whiten_histories=hists)
    assert res["supported"] and res["n_distinct"] > 0
    assert res["miss"]["point"] < 0.2                  # K = the kick read-in learned from the training kick pairs ~ C on the toy


def test_history_index_exact_prefix_lookup():
    idx = R.HistoryIndex()
    x = np.arange(30, dtype=float).reshape(10, 3)
    u = np.ones((10, 1))
    idx.add(x, u, np.arange(10.0)[:, None])
    assert idx.get(x[:4], u[:4])[0] == 3.0
    x2 = x.copy()
    x2[0] += 1.0                                        # same last row, different history: no false match
    assert idx.get(x2[:4], u[:4]) is None
    assert idx.get(x[:4] + 0.5, u[:4]) is None


def test_timeline_descriptors():
    col = {10: 0, 11: 1, 12: 2}
    ev = [{"kind": "kick", "t": 0.02, "delta": {"10": 2.0, "99": 1.0}},
          {"kind": "current_seq", "t0": 0.05, "seg": 0.05, "targets": {"11": [1.0, -1.0]}},
          {"kind": "silence", "t0": 0.1, "t1": None, "targets": [12]},
          {"kind": "edge_scale", "t0": 0.0, "t1": 0.05, "edges": [[10, 11]], "factor": 0.5},
          {"kind": "param", "t0": 0.0, "t1": 0.03, "targets": {"11": {"gain": 1.5, "threshold": 0.2}}}]
    tl = R.Timeline(ev, 20, 0.01, col)
    assert tl.kicks == {2: {0: 2.0}}                     # the unobserved unit 99 is dropped
    st = tl.static_at(6)
    assert st["cur"] == {1: 1.0}
    assert tl.static_at(12)["cur"] == {1: -1.0} and tl.static_at(12)["sil"] == [2]
    st0 = tl.static_at(1)
    assert st0["edges"] == [(0, 1, 0.5)] and st0["gain"] == {1: 1.5} and st0["thr"] == {1: 0.2}
    m = R.ProjectionStateModel("pca", 2)
    m.N, m.d_dyn, m.K = 3, 3, np.eye(3)
    m._exact_readin = True
    units, A = m._seg_channels(st0, np.array([[1.0, 2.0, 3.0]]))
    assert units == [0, 1]
    assert A[0, 0, 3] == pytest.approx(-0.5 * 2.0)       # edge drive into unit 10 from unit 11: (0.5 - 1) x x_hat[11]
    assert A[0, 1, 4] == pytest.approx(0.5 * 2.0)        # gain drive (1.5 - 1) x x_hat
    assert A[0, 1, 5] == pytest.approx(0.2)


def test_blowups_are_left_out(toy):
    _s, train, _truth, _, _ = toy
    bad = dict(train[0], key="blowup", x=train[0]["x"] * 1e6)
    mask = R.blowup_mask(train[:10] + [bad])
    assert mask[-1] and not mask[:-1].any()


# ------------------------------------------------------------------------------------------------------------ learner v2
def _without_unit(records, unit: int):
    """Training records without the intervention trajectories (and their twins) that touch `unit`."""
    drop = set()
    for r in records:
        for e in r["protocol"].get("events") or []:
            tg = e.get("delta") or e.get("targets") or {}
            if str(unit) in {str(k) for k in tg}:
                drop.add(r["key"])
    return [r for r in records if r["key"] not in drop and (r["meta"] or {}).get("twin_of") not in drop]


def test_units_never_intervened_are_abstained_on(toy):
    s, train, truth, test, _ttruth = toy
    tr = _without_unit(train, 4)
    m = R.fit_reference("true_state", "toy", tr, s.record(), truth={"z": {r["key"]: truth["z"][r["key"]] for r in tr}}, cfg=FAST)
    assert 4 not in m.kick_units and m.covers("toy", [{"kind": "kick", "t": 0.0, "delta": {"2": 1.0}}]) is (2 in m.kick_units)
    ev = [{"kind": "kick", "t": 0.1, "delta": {"4": 1.0}}]
    assert not m.covers("toy", ev)
    r = test[0]
    out = m.intervention_effect("toy", r["x"][:51], r["u"][:51], r["u"][50:76], ev, DT)
    assert out["abstain"]
    # a compact state never uses a correlational probe as its read-in: an unkicked unit's kick read-in is exactly zero
    assert not np.any(m.read_in("toy", m.encode("toy", r["x"][:51], r["u"][:51], DT), ev[0])["dz"])


def test_effect_calibration_factors_are_in_the_unit_interval(toy):
    s, train, truth, _test, _ = toy
    m = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    assert m.beta is not None and m.beta[0] == 1.0 and np.all((m.beta >= 0.0) & (m.beta <= 1.0))
    off = R.fit_reference("true_state", "toy", train, s.record(), truth=truth,
                          cfg=R.LearnerConfig(steps_one=400, steps_multi=60, readout_steps=400, effect_shrinkage=False))
    assert off.beta is None


def test_readin_gain_corruption_goes_through_the_base_prediction(toy):
    s, train, truth, test, ttruth = toy
    m = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    m.register_records(test, ttruth["z"])
    r = next(q for q in test if q["protocol"].get("events"))
    ev = r["protocol"]["events"]
    t0 = min(P.event_start(e) for e in ev)
    i0 = round(t0 / DT)
    rel = [dict(e, **({"t": e["t"] - t0} if "t" in e else {"t0": e["t0"] - t0, "t1": e["t1"] - t0})) for e in ev]
    fam = "kick.1" if ev[0]["kind"] == "kick" else "pulse.1"
    bad = R.ReadinGainModel(m, fam, dict(s.record(), capability=s.record()["capability"]), gain=0.5)
    scaled = bad._events("toy", rel, 26, DT)
    a = bad.intervention_effect("toy", r["x"][: i0 + 1], r["u"][: i0 + 1], r["u"][i0: i0 + 26], rel, DT)
    b = m.intervention_effect("toy", r["x"][: i0 + 1], r["u"][: i0 + 1], r["u"][i0: i0 + 26], scaled, DT)
    assert np.allclose(a["effect"], b["effect"])


def test_paired_windows_cover_the_whole_horizon_after_the_onset(toy):
    # unit rule: from a start st <= j0 through m steps AFTER the onset j0, clipped at the trajectory's end (reviewer H, NEW-2)
    j0, st, nn, m = np.array([50, 50, 50, 10, 195]), np.array([40, 50, 45, 0, 190]), np.array([201, 201, 201, 201, 201]), 25
    Li = R._LearnedStateModel._paired_lengths(j0, st, nn, m)
    assert Li.tolist() == [35, 25, 30, 35, 10]                  # the last pair is clipped at its end (200 - 190)
    assert all((Li - (j0 - st))[(nn - 1 - j0) >= m] == m)
    # in a fit: every sampled window of a long-enough trajectory covered exactly m steps after its onset
    s, train, truth, _test, _ = toy
    mdl = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    po = mdl.fit_notes["paired_post_onset"]
    assert po["window"] == mdl.fit_notes["window"] and po["min_steps_long_pairs"] == po["window"]


def test_references_never_write_their_inputs(toy):
    # evaluation items hand out read-only arrays (review F, minor 2): every reference must work on them without copying requests
    s, train, truth, test, ttruth = toy
    ts = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    ts.register_records(test, ttruth["z"])
    models = [ts, R.fit_reference("full_state", "toy", train, s.record(), cfg=FAST), R.fit_reference("id_shortcut", "toy", train, s.record())]
    models[2].register_records(test)
    models.append(R.NoEffectModel(models[1]))
    r = next(q for q in test if q["protocol"].get("events"))
    x, u = r["x"][:51].copy(), r["u"][:51].copy()
    uf = r["u"][50:76].copy()
    for a in (x, u, uf):
        a.setflags(write=False)
    ev = [{"kind": "kick", "t": 0.05, "delta": {"1": 1.0}}]
    for m in models:
        out = m.intervention_effect("toy", x, u, uf, ev, DT)
        assert np.isfinite(out["effect"]).all()
        m.encode("toy", x, u, DT)
