"""Package interface, protocol handling, determinism and records (contract section 4)."""

import os

import numpy as np
import pytest

from conftest import ROOM, const_input, mid_state, one_per_type
from p4synth import ENGINE_ID, build_suite, protocol as P
from ref import families as F


def test_vendored_protocol_identical_to_reference():
    a = open(os.path.join(ROOM, "src", "p4synth", "protocol.py")).read().split("\n", 1)[1]
    b = open(os.path.join(ROOM, "ref", "protocol.py")).read()
    assert a == b


def test_suite_sizes_and_determinism(suite):
    assert len(suite) == 50
    types = [s.info["type"] for s in suite.values()]
    assert sorted(set(types)) == list(range(1, 26)) and all(types.count(t) == 2 for t in range(1, 26))
    seed = next(iter(suite.values())).info["suite_seed"]
    again = build_suite("dev", seed)
    assert list(again) == list(suite)
    assert all(again[k].content_hash() == suite[k].content_hash() for k in suite)
    other = build_suite("dev", seed + 1, n_per_type=1)
    assert len(other) == 25 and not set(other) & set(suite)


def test_ids_are_opaque(suite):
    for sid, s in suite.items():
        assert sid.startswith("syn-") and len(sid) == 16
        assert s.info["variant"] not in sid and s.engine_id == ENGINE_ID
        rec = s.public_record()
        blob = repr(rec)
        for word in ("type", "trap", "variant", "latent", "core", "follower"):
            assert f"'{word}'" not in blob


def test_public_record_and_capability(suite):
    for s in one_per_type(suite):
        rec = s.public_record()
        for key in ("system_id", "kind", "dt", "t_end_default", "n_units", "observed", "readout_dim", "input_dim", "targets",
                    "edges", "obs_scale", "capability", "cost_units"):
            assert key in rec, key
        assert rec["kind"] == "synthetic" and "split" not in rec
        cap = rec["capability"]
        for kind in ("kick", "current", "current_seq", "silence", "edge_scale", "param"):
            assert kind in cap
        assert cap["kick"]["max"] == pytest.approx(3 * cap["kick"]["moderate"])
        assert cap["current"]["pulse_max_duration"] <= cap["current"]["sustained_min_duration"]
        assert cap["process_noise"]["supported"] and cap["params"]["nominal_seed"] == 0
        assert rec["obs_scale"]["x"] > 0 and rec["obs_scale"]["y"] > 0
        assert set(rec["targets"]) <= set(range(s.n_units)) and rec["targets"]
        assert all(0 <= a < s.n_units and 0 <= b < s.n_units for a, b in rec["edges"])
        fams = F.supported_families(cap)
        assert "pulse.1" in fams and "sil.1" in fams and "param.1" in fams
        # review v3.3 (N7): edge scaling is not published (inert in almost every system), for EVERY system: a rotation that
        # trains edge.w is reduced by the benchmark (the reduced split is valid)
        assert not cap["edge_scale"]["supported"] and "edge.w" not in fams and "edge.rm" not in fams
        assert cap["param"]["fields"] == ["threshold"]
        for rot in F.ROTATIONS:
            F.split_record(list(F.OBS) + [f for f in F.ROTATIONS[rot] if f in fams], fams, rotation=rot)


def test_simulate_shapes_and_fields(suite):
    for s in one_per_type(suite):
        p = s.base_protocol()
        o = s.simulate(p)
        T = int(round(s.t_end_default / s.dt)) + 1
        assert o["t"].shape == (T,) and o["x"].shape == (T, len(s.observed))
        assert o["u"].shape == (T, s.input_dim) and o["y"].shape == (T, s.readout_dim)
        assert "state" not in o
        of = s.simulate(p, full=True)
        assert of["state"].shape == (T, s.n_state) and of["z"].shape[0] == T
        np.testing.assert_allclose(of["state"][:, s.n_units:], of["z"], rtol=0, atol=0)     # internal copy of z
        np.testing.assert_array_equal(of["x"], o["x"])
        np.testing.assert_allclose(s.true_state(of["state"]), of["z"], atol=1e-9)
        if s.spec.latent.zobs(of["z"]) is not None:
            assert "z_obs" in of
        assert np.all(np.isfinite(of["state"]))


def test_obs_noise_ignored_and_system_checked(suite):
    s = next(iter(suite.values()))
    p = s.base_protocol(t_end=0.3)
    a = s.simulate(p)
    b = s.simulate(dict(p, obs_noise={"sd": 0.5, "seed": 3}))
    np.testing.assert_array_equal(a["x"], b["x"])
    with pytest.raises(P.ProtocolError):
        s.simulate(dict(p, system="syn-000000000000"))


def test_determinism_and_seeds(suite):
    s = one_per_type(suite)[1]
    p = s.base_protocol(params_seed=17)
    a, b = s.simulate(p), s.simulate(p)
    np.testing.assert_array_equal(a["y"], b["y"])
    c = s.simulate(s.base_protocol(params_seed=18))
    assert np.abs(c["y"] - a["y"]).max() > 1e-6
    # params_spread 0: every seed gives the nominal draw
    d0 = s.simulate(s.base_protocol(params_seed=0))
    d1 = s.simulate(s.base_protocol(params_seed=5, params_spread=0.0))
    np.testing.assert_array_equal(d0["y"], d1["y"])
    # weight noise and process noise are deterministic in their seeds
    for key in ("weight_noise", "process_noise"):
        w1 = s.simulate(dict(p, **{key: {"sd": 0.1, "seed": 2}}))
        w2 = s.simulate(dict(p, **{key: {"sd": 0.1, "seed": 2}}))
        w3 = s.simulate(dict(p, **{key: {"sd": 0.1, "seed": 3}}))
        w0 = s.simulate(dict(p, **{key: {"sd": 0.0, "seed": 3}}))
        np.testing.assert_array_equal(w1["y"], w2["y"])
        assert np.abs(w1["x"] - w3["x"]).max() > 1e-6
        np.testing.assert_array_equal(w0["y"], a["y"])


def test_rest_is_a_fixed_point(suite):
    for s in one_per_type(suite):
        for seed in (0, 7):
            o = s.simulate(s.base_protocol(t_end=0.5, params_seed=seed, stimulus=[[0.0, 0.0]] if s.input_dim == 1 else
                                           [[0.0, [0.0] * s.input_dim]]), full=True)
            np.testing.assert_allclose(o["state"], np.broadcast_to(s.rest_state(), o["state"].shape), atol=1e-10)


def continuation(p, ti):
    """The remainder of protocol p from time ti as a restart protocol (events shifted; windows active at ti clipped to start at 0;
    the stimulus in force at ti; r0 = restart at ti, which also sets the absolute step of the process-noise stream)."""
    q = P.validate(p, allow_truth=True)
    st = [[0.0, [v for t, v in q["stimulus"] if t <= ti + 1e-12][-1]]] + [[round(t - ti, 9), v] for t, v in q["stimulus"]
                                                                           if t > ti + 1e-12]
    evs = []
    for e in q["events"]:
        e = dict(e)
        if "t" in e:
            if e["t"] >= ti - 1e-12:
                e["t"] = round(e["t"] - ti, 9)
                evs.append(e)
            continue
        if e.get("t1") is not None and e["t1"] <= ti + 1e-12:
            continue
        e["t0"] = round(max(e["t0"] - ti, 0.0), 9)
        if e.get("t1") is not None:
            e["t1"] = round(e["t1"] - ti, 9)
        evs.append(e)
    return dict(q, t_end=round(q["t_end"] - ti, 9), stimulus=st, events=evs, r0={"kind": "restart", "key": "0" * 16, "t": ti})


def test_restart_bit_for_bit(suite):
    """Addendum 8 (and 3): a restart from the state recorded at sample i reproduces the original trajectory from sample i on, bit for
    bit, without and with process noise (counter-based stream keyed by the absolute step), for events before, during and after i.
    The microstate and z are identical from sample i, x and y from sample i + 1: by the pre-event rule the outputs at the restart
    sample itself do not yet show a window that the continuation restarts at t = 0 (every event is invisible at its onset sample)."""
    for s in suite.values():
        tg = s.core_targets()
        cap = s.capability()
        mk = cap["kick"]["moderate"]
        ev = [{"kind": "kick", "t": 0.3, "delta": {str(tg[0]): mk}},
              {"kind": "silence", "t0": 0.5, "t1": 0.9, "targets": [int(tg[1 % len(tg)])]},
              {"kind": "current", "t0": 0.8, "t1": 1.3, "targets": {str(tg[2 % len(tg)]): cap["current"]["moderate"]}},
              {"kind": "kick", "t": 1.2, "delta": {str(tg[-1]): -mk}},
              {"kind": "param", "t0": 1.1, "t1": 1.5, "targets": {str(tg[len(tg) // 2]): {"gain": 1.5}}}]
        for pn in (None, {"sd": 0.05, "seed": 7}):
            p = s.base_protocol(params_seed=4, events=ev, process_noise=pn, stimulus=s.nominal_stimulus()[:2] + [[1.4, 0.7]]
                                if s.input_dim == 1 else s.nominal_stimulus())
            o = s.simulate(p, full=True)
            for ti in (0.6, 1.25):
                i = int(round(ti / s.dt))
                o2 = s.simulate(continuation(p, ti), full=True, restart_state=o["state"][i])
                for key in ("state", "z"):
                    assert np.array_equal(o[key][i:], o2[key]), (s.info["type"], s.info["variant"], pn is not None, ti, key)
                for key in ("x", "y"):
                    assert np.array_equal(o[key][i + 1:], o2[key][1:]), (s.info["type"], s.info["variant"], pn is not None, ti, key)
    # a restart from a float32-rounded state stays close (the benchmark's stored real states are float32)
    s = one_per_type(suite)[1]
    o = s.simulate(s.base_protocol(), full=True)
    i = int(round(1.0 / s.dt))
    o3 = s.simulate(continuation(s.base_protocol(), 1.0), full=True, restart_state=o["state"][i].astype(np.float32))
    assert o3["info"]["success"] and np.abs(o3["y"] - o["y"][i:]).max() < 1e-3 * s.obs_scale()["y"]
    # without events active across the restart time the outputs agree from sample i itself
    p = s.base_protocol()
    o4 = s.simulate(continuation(p, 1.0), full=True, restart_state=o["state"][i])
    assert np.array_equal(o4["y"], o["y"][i:]) and np.array_equal(o4["x"], o["x"][i:])


def test_noise_stream_is_counter_based(suite):
    """Addendum 3: process noise keyed by (seed, absolute step): a trajectory split into two pieces reproduces the uninterrupted one."""
    s = one_per_type(suite)[4]
    p = s.base_protocol(params_seed=1, process_noise={"sd": 0.1, "seed": 11})
    o = s.simulate(p, full=True)
    i = int(round(0.7 / s.dt))
    o2 = s.simulate(continuation(p, 0.7), full=True, restart_state=o["state"][i])
    assert np.array_equal(o["state"][i:], o2["state"])
    o3 = s.simulate(dict(p, process_noise={"sd": 0.1, "seed": 12}), full=True)
    assert not np.array_equal(o["state"], o3["state"])


def test_hashes_and_engine_id(suite):
    """Addendum 7: the content hash covers everything that changes a trajectory; the engine id is the hash of the simulation code."""
    import hashlib
    import copy as _copy
    from p4synth import engine as _eng
    h = hashlib.sha256()
    for fn in _eng.SIM_SOURCES:
        with open(os.path.join(ROOM, "src", "p4synth", fn), "rb") as fh:
            h.update(fn.encode() + b"\0" + fh.read())
    assert ENGINE_ID == "p4synth-2.0+" + h.hexdigest()[:16]
    s = one_per_type(suite)[2]
    base = s.content_hash()
    assert s.content_hash() == base and len({x.content_hash() for x in suite.values()}) == len(suite)
    for mutate in (lambda sp: sp.E.__setitem__((0, 0), sp.E[0, 0] * 1.01),
                   lambda sp: sp.obs_s.__setitem__(0, sp.obs_s[0] * 1.01),
                   lambda sp: sp.b.__setitem__(0, sp.b[0] + 0.01),
                   lambda sp: setattr(sp.latent, "z_scale", tuple(1.01 * a for a in sp.latent.z_scale)),
                   lambda sp: sp.latent.params.__setitem__(sorted(sp.latent.params)[0],
                                                           (1.01 * sp.latent.params[sorted(sp.latent.params)[0]][0],) +
                                                           tuple(sp.latent.params[sorted(sp.latent.params)[0]][1:])),
                   lambda sp: setattr(sp, "tau_c", sp.tau_c * 1.01),
                   lambda sp: sp.gen.__setitem__("W", sp.gen["W"] * 1.01) if sp.gen else setattr(sp, "h_max", sp.h_max / 2)):
        s2 = _copy.deepcopy(s)
        s2._hash = None
        mutate(s2.spec)
        assert s2.content_hash() != base


def test_r0_state_values(suite):
    s = one_per_type(suite)[2]
    u = s.targetable[0]
    sv = s.units()["v"]                                      # r0 values are public; microstates internal
    val = float(s.rest_state()[u] * sv + 1.5)
    o = s.simulate(s.base_protocol(t_end=0.1, r0={"kind": "state", "values": {str(u): val}}), full=True)
    assert o["state"][0, u] == pytest.approx(val / sv)
    others = np.delete(np.arange(s.n_units), u)
    np.testing.assert_allclose(o["state"][0, others], s.rest_state()[others])


def test_twin_identical_before_first_event(suite):
    for s in one_per_type(suite)[::4]:
        u = s.targetable[0]
        p = s.base_protocol(params_seed=4, events=[{"kind": "current", "t0": 0.6, "t1": 0.7, "targets": {str(u): 3.0}}])
        tw = P.counterfactual(p)
        a, b = s.simulate(p, full=True), s.simulate(tw, full=True)
        j = int(round(0.6 / s.dt))
        np.testing.assert_array_equal(a["state"][:j + 1], b["state"][:j + 1])


def test_truth_events_and_latent_set(suite):
    for s in one_per_type(suite)[::5]:
        k = s.spec.k
        z_star = [0.1 * (i + 1) for i in range(k)]
        o = s.simulate(s.base_protocol(t_end=0.4, stimulus=const_input(s), events=[{"kind": "latent_set", "t": 0.2, "z": z_star}]),
                       full=True)
        j = int(round(0.2 / s.dt))
        # the simulated do(z := z*) equals a restart from the exact microscopic realisation of the do()
        o2 = s.simulate(s.base_protocol(t_end=0.2, stimulus=const_input(s)), full=True, restart_state=s._set_z(o["state"][j], z_star))
        assert np.all(np.isfinite(o["state"])) and np.all(np.isfinite(o2["state"]))
        np.testing.assert_allclose(o2["z"][0], z_star, atol=1e-10)
        np.testing.assert_allclose(o["state"][j + 1:], o2["state"][1:], rtol=1e-8, atol=1e-8)
        st = mid_state(s)
        dz = np.full(k, 0.05)
        np.testing.assert_allclose(s.true_latent_effect(st, {"kind": "latent_kick", "t": 0, "dz": dz.tolist()}), dz)
        new = s._set_z(st, np.array(z_star))
        np.testing.assert_allclose(s.true_state(new), z_star, atol=1e-12)


def test_truth_record(suite):
    for s in suite.values():
        t = s.truth(include_draw=False)          # the draw analysis ("d_draw", "draw") is tested in test_draws.py
        for key in ("type", "type_name", "variant", "trap", "k", "latent", "observation_map", "implementation",
                    "z_obs", "exposing_families", "expected_verdict", "closure", "readin", "observability", "controllability"):
            assert key in t, key
        if t["type"] in (20, 21):
            assert t["k"] == "none" and t["k_full"] > len(s.observed) / 5
        else:
            assert isinstance(t["k"], int) and t["k"] <= max(1, len(s.observed) / 5), (t["type"], t["k"], len(s.observed))


def test_construction_independent_of_blas_threads(suite):
    """Review round 3, B6: the suite is constructed with single-threaded BLAS whatever the environment, so construction (all systems)
    and the content hashes (3 systems, incl. the public-unit probe) are bit-identical at 1 and 8 BLAS threads."""
    import json as _json
    import os as _os
    import subprocess
    import sys as _sys
    seed = next(iter(suite.values())).info["suite_seed"]
    code = ("import json, sys; sys.path.insert(0, %r); from p4synth import build_suite; S = build_suite('dev', %d); "
            "ids = sorted(S); print(json.dumps({'c': {i: S[i].construction_hash() for i in ids}, "
            "'h': {i: S[i].content_hash() for i in ids[:3]}}))") % (_os.path.join(ROOM, "src"), seed)
    res = {}
    for n in (1, 8):
        env = dict(_os.environ, OPENBLAS_NUM_THREADS=str(n), OMP_NUM_THREADS=str(n), MKL_NUM_THREADS=str(n))
        out = subprocess.run([_sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True).stdout
        res[n] = _json.loads(out.strip().splitlines()[-1])
    assert res[1] == res[8]
    assert res[1]["c"] == {i: s.construction_hash() for i, s in suite.items()}
