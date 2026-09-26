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
    # read-in of a kick is the kick itself on the current block
    rin = m.read_in("toy", z0, {"kind": "kick", "t": 0.0, "delta": {"2": 1.5}})
    assert np.allclose(rin["dz"][:5], [0, 0, 1.5, 0, 0]) and not rin["dz"][5:].any()


def test_id_shortcut_learns_seen_identities(toy):
    s, train, _truth, test, _ = toy
    m = R.fit_reference("id_shortcut", "toy", train, s.record(), cfg=FAST)
    m.register_records(test)
    assert _effect_error(m, test) < 0.6
    assert m.supports("toy", "kick") and m.info()["n_ids"] > 0


def test_true_state_native_lift_realises_requested_shifts(toy):
    s, train, truth, _, _ = toy
    m = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    cases = [{"protocol": passive_protocol(300 + i), "t": 0.7} for i in range(3)]
    res = eval_native_lift(m, "toy", cases, s.simulate_many, horizon_s=0.25, floor=0.01, truth=True, cfg=LiftConfig(n_boot=100))
    assert res["supported"] and res["n_distinct"] > 0
    assert res["miss"]["point"] < 0.2                  # K = probe + kick correction ~ C on the toy


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
