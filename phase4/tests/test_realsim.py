"""Real engine version 2: bit-identity with the frozen Phase 3 engine on protocols both formats express, and the semantics of the
new event kinds (orchestrator-side test; reads the hidden system definitions, never prints them)."""

import json

import numpy as np
import pytest

from brainir_causal import protocol as P
from brainir_causal.realsim import RealEngine, RealSystem, dense, observe
from brainir_causal.store import TrajectoryStore
from brainir_causal.systems import BUNDLE, NAME_MAP, P3_INTERNAL, load_real_internal

pytestmark = pytest.mark.skipif(not NAME_MAP.exists(), reason="real systems not built")

_ENG4: dict = {}
_ENG3: dict = {}


@pytest.fixture(scope="module")
def systems():
    internal = load_real_internal()
    names = json.loads(NAME_MAP.read_text(encoding="utf-8"))["map"]
    p3 = json.loads(P3_INTERNAL.read_text(encoding="utf-8"))
    return internal, names, p3


def eng4(net):
    if net not in _ENG4:
        _ENG4[net] = RealEngine(BUNDLE, net)
    return _ENG4[net]


def eng3(net):
    from brainir_state.realsim import RealEngine as E3
    if net not in _ENG3:
        _ENG3[net] = E3(BUNDLE, net)
    return _ENG3[net]


def p3_protocols(sid3, targets, edges, t_end=0.3):
    b = {"system": sid3, "params_seed": 17, "t_end": t_end, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]]}
    a, c = targets[0], targets[-1]
    out = [dict(b),
           {**b, "events": [{"kind": "kick", "t": 0.1, "delta": {str(a): 20.0}}, {"kind": "kick", "t": 0.2, "delta": {str(c): -500.0}}]},
           {**b, "events": [{"kind": "current", "t0": 0.05, "t1": 0.12, "targets": {str(a): 30.0}}]},
           {**b, "events": [{"kind": "silence", "t0": 0.1, "t1": 0.2, "targets": [a]}]},
           {**b, "events": [{"kind": "silence", "t0": 0.1, "t1": None, "targets": [c]}]},
           {**b, "weight_noise": {"sd": 0.05, "seed": 3}, "stimulus": [[0.0, 0.0], [0.02, 1.3], [0.15, 0.7]]},
           {**b, "r0": {"kind": "state", "values": {str(a): 12.0, str(c): 4.0}}}]
    if edges:
        out.append({**b, "events": [{"kind": "edge_remove", "t0": 0.05, "t1": 0.25, "edges": [edges[0]]}]})
    return out


def compare(sid4, internal, names, p3, protos3):
    from brainir_state.realsim import RealSystem as S3
    d4 = internal[sid4]
    sid3 = names[sid4]
    d3 = p3[sid3]
    s3 = S3(system_id=sid3, network=d3["network"], mode=d3["mode"], keep=tuple(d3["keep"]), observed=tuple(d3["observed"]),
            readout=tuple(d3["readout"]), stimulus=tuple(d3["stimulus"]))
    s4 = RealSystem.from_record(d4)
    for p3p in protos3:
        r3 = eng3(d3["network"]).run(s3, p3p)
        p4 = P.from_format1({**p3p, "system": sid4})
        r4 = eng4(d4["network"]).run(s4, p4)
        assert np.array_equal(r3["neurons"], r4["neurons"])
        assert np.array_equal(r3["rates"], r4["rates"]), (sid4, p3p.get("events"))
        assert np.array_equal(r3["u"], r4["u"])
        assert np.array_equal(r3["t"], r4["t"])


def test_bit_identical_to_phase3_on_every_mechanism_system(systems):
    internal, names, p3 = systems
    mechs = [s for s, d in internal.items() if d["mode"] == "mech"]
    assert len(mechs) == 7
    for sid in mechs:
        d = internal[sid]
        members = sorted(d["keep"])
        edges = [[int(post), int(pre)] for post, pre, v in d["public_graph"]["edges_post_pre_signed_count"]
                 if int(post) in members and int(pre) in members and v != 0]
        compare(sid, internal, names, p3, p3_protocols(names[sid], members, edges))


def test_bit_identical_to_phase3_on_one_short_full_network_trajectory(systems):
    internal, names, p3 = systems
    sid = "real:A:full"
    tg = internal[sid]["targets_public"]
    b = {"system": names[sid], "params_seed": 23, "t_end": 0.15, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]],
         "events": [{"kind": "kick", "t": 0.05, "delta": {str(tg[0]): 25.0}}, {"kind": "silence", "t0": 0.08, "t1": 0.12, "targets": [tg[1]]},
                    {"kind": "current", "t0": 0.03, "t1": 0.1, "targets": {str(tg[2]): 40.0}}]}
    compare(sid, internal, names, p3, [b])


@pytest.fixture(scope="module")
def mech(systems):
    internal = systems[0]
    sid = max((s for s, d in internal.items() if d["mode"] == "mech"), key=lambda s: (len(internal[s]["keep"]), s))
    d = internal[sid]
    return sid, d, RealSystem.from_record(d), eng4(d["network"])


def _base(sid, **kw):
    p = {"system": sid, "params_seed": 5, "t_end": 0.4, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]]}
    p.update(kw)
    return p


def test_current_seq_equals_the_same_current_events(mech):
    sid, d, s, eng = mech
    a = str(d["keep"][0])
    seq = _base(sid, events=[{"kind": "current_seq", "t0": 0.1, "seg": 0.02, "targets": {a: [10.0, 0.0, 25.0, 0.0, -5.0]}}])
    evs = [{"kind": "current", "t0": 0.1, "t1": 0.12, "targets": {a: 10.0}}, {"kind": "current", "t0": 0.14, "t1": 0.16, "targets": {a: 25.0}},
           {"kind": "current", "t0": 0.18, "t1": 0.2, "targets": {a: -5.0}}]
    # the separate events miss the zero-valued segment boundaries (0.12-0.14, 0.16-0.18 have no event), so add them as no-op
    # stimulus steps: then both protocols have the same pieces and the same currents
    extra = [[0.12, 1.0], [0.14, 1.0], [0.16, 1.0], [0.18, 1.0]]
    sep = _base(sid, events=evs, stimulus=[[0.0, 0.0], [0.02, 1.0]] + extra)
    r1, r2 = eng.run(s, seq), eng.run(s, sep)
    assert P.breakpoints(seq) == P.breakpoints(sep)
    assert np.array_equal(r1["rates"], r2["rates"])


def test_noop_edge_scale_and_param_equal_the_twin(mech):
    sid, d, s, eng = mech
    a, b_ = d["keep"][0], d["keep"][1]
    for ev in ({"kind": "edge_scale", "t0": 0.1, "t1": 0.3, "edges": [[a, b_]], "factor": 1.0},
               {"kind": "param", "t0": 0.1, "t1": 0.3, "targets": {str(a): {"gain": 1.0, "tau": 1.0, "threshold": 0.0}}}):
        p = _base(sid, events=[ev])
        r1, r2 = eng.run(s, p), eng.run(s, P.counterfactual(p))
        assert np.array_equal(r1["rates"], r2["rates"])


def test_edge_scale_param_and_persistence_act(mech):
    sid, d, s, eng = mech
    members = d["keep"]
    edges = [[int(post), int(pre)] for post, pre, v in d["public_graph"]["edges_post_pre_signed_count"]
             if int(post) in members and int(pre) in members and v != 0]
    twin = eng.run(s, _base(sid))
    for ev in ({"kind": "edge_scale", "t0": 0.1, "t1": None, "edges": edges[:2], "factor": 0.3},
               {"kind": "param", "t0": 0.1, "t1": None, "targets": {str(members[0]): {"gain": 1.8}}},
               {"kind": "param", "t0": 0.1, "t1": 0.2, "targets": {str(members[0]): {"threshold": -3.0, "tau": 2.0}}}):
        p = _base(sid, events=[ev])
        r = eng.run(s, p)
        tw = eng.run(s, P.counterfactual(p))
        i0 = round(0.1 / 0.001)
        assert np.array_equal(r["rates"][: i0 + 1], tw["rates"][: i0 + 1])      # identical before the event
        assert not np.array_equal(r["rates"], tw["rates"])                          # and different after it
    assert twin["info"]["system_id"] == sid


def test_restart_continues_the_trajectory_and_obs_noise_is_observation_only(mech, tmp_path):
    sid, d, s, eng = mech
    store = TrajectoryStore(tmp_path)
    full = _base(sid, t_end=0.6, stimulus=[[0.0, 1.0]])
    key, rec, computed = store.get_or_run(eng, s, full, internal_hash(d))
    assert computed
    key2, _, computed2 = store.get_or_run(eng, s, full, internal_hash(d))
    assert key2 == key and not computed2                                   # never recomputed
    # restart at 0.3 s and run 0.3 s more: it starts from exactly the stored (float32) state and follows the second half of the long
    # run; the float32 rounding of the restart state (~1e-7 relative) is amplified by the (oscillatory) dynamics and the fresh
    # adaptive step sequence to at most ~0.2 % of the trajectory's scale over 0.3 s on this system (probe: 0.107 Hz at 65 Hz)
    rs = _base(sid, t_end=0.3, stimulus=[[0.0, 1.0]], r0={"kind": "restart", "key": key, "t": 0.3})
    r2 = eng.run(s, rs, store=store)
    ref = rec["rates"][300:].astype(np.float64)
    got = dense(r2, list(rec["neurons"])).astype(np.float64)
    assert np.array_equal(got[0], ref[0])
    assert np.abs(got - ref).max() <= 1e-2 * np.abs(ref).max()
    assert np.abs(got[:20] - ref[:20]).max() <= 1e-4 * np.abs(ref).max()
    with pytest.raises(P.ProtocolError, match="sample time"):
        eng.run(s, _base(sid, r0={"kind": "restart", "key": key, "t": 0.9}), store=store)
    # observation noise: same microstate key, noisy observed arrays with the requested scale, reproducible by seed
    noisy = {**full, "obs_noise": {"sd": 0.2, "seed": 9}}
    assert store.key(noisy, internal_hash(d), "e") == store.key(full, internal_hash(d), "e")
    o0 = observe(rec, s, full, d["obs_scale"])
    o1 = observe(rec, s, noisy, d["obs_scale"])
    o2 = observe(rec, s, noisy, d["obs_scale"])
    assert np.array_equal(o1["x"], o2["x"]) and not np.array_equal(o0["x"], o1["x"])
    sd = float(np.std(o1["x"].astype(np.float64) - o0["x"]))
    assert abs(sd / (0.2 * d["obs_scale"]["x"]) - 1.0) < 0.1


def internal_hash(d):
    return d["system_hash"]


def test_invalid_units_and_initial_rates(mech):
    sid, d, s, eng = mech
    with pytest.raises(P.ProtocolError, match="outside the network"):
        eng.run(s, _base(sid, events=[{"kind": "kick", "t": 0.1, "delta": {"999999": 1.0}}]))
    with pytest.raises(P.ProtocolError, match="rates must be"):
        eng.run(s, _base(sid, r0={"kind": "state", "values": {str(d["observed"][0]): -1.0}}))


def test_params_spread_and_process_noise_in_the_real_engine(mech):
    sid, _, s, eng = mech
    base = _base(sid, t_end=0.2)
    r1 = eng.run(s, base)
    assert np.array_equal(r1["rates"], eng.run(s, {**base, "params_spread": 1.0})["rates"])
    p1, p2 = eng.params(5), eng.params(5, 2.0)
    assert np.array_equal(p1.tau, eng.params(5, 1.0).tau) and not np.array_equal(p1.tau, p2.tau)
    # the same uniforms, twice the spread: the deviations from the mean double (up to truncation), the mean is unchanged
    dev1, dev2 = p1.tau - eng.problem.model_cfg.tau_mean, p2.tau - eng.problem.model_cfg.tau_mean
    assert np.corrcoef(dev1, dev2)[0, 1] > 0.99 and 1.8 < np.std(dev2) / np.std(dev1) < 2.2
    assert not np.array_equal(r1["rates"], eng.run(s, {**base, "params_spread": 2.0})["rates"])
    with pytest.raises(P.ProtocolError, match="process noise"):
        eng.run(s, {**base, "process_noise": {"sd": 0.1, "seed": 1}})
