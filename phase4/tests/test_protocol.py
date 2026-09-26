import json

import pytest

from brainir_causal import protocol as P


def base(**kw):
    p = {"system": "s", "params_seed": 3, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 0.0], [0.05, 1.0]], "events": []}
    p.update(kw)
    return p


def test_canonical_defaults_and_snapping():
    q = P.validate(base(events=[{"kind": "kick", "t": 0.1234, "delta": {3: 1.0, "1": -2}}]))
    assert list(q) == list(P.TOP_KEYS)
    assert q["r0"] == {"kind": "rest"} and q["weight_noise"] is None and q["obs_noise"] is None
    ev = q["events"][0]
    assert ev["t"] == 0.12 and list(ev["delta"]) == ["1", "3"] and ev["delta"]["1"] == -2.0
    # a stimulus not starting at 0 gets a leading 0 segment; duplicate times keep the last value
    q2 = P.validate(base(stimulus=[[0.2, 1.0], [0.2, 0.7]]))
    assert q2["stimulus"] == [[0.0, 0.0], [0.2, 0.7]]
    q3 = P.validate(base(stimulus=[[0.3, [1.0, 0.5]]]))
    assert q3["stimulus"][0] == [0.0, [0.0, 0.0]]


def test_every_event_kind_validates():
    evs = [
        {"kind": "kick", "t": 0.1, "delta": {"0": 1.0}},
        {"kind": "current", "t0": 0.1, "t1": 0.2, "targets": {"1": 2.0}},
        {"kind": "current", "t0": 0.1, "t1": None, "targets": {"1": -2.0}},
        {"kind": "current_seq", "t0": 0.2, "seg": 0.05, "targets": {"2": [1, 0, 1], "3": [0, 0, 1]}},
        {"kind": "silence", "t0": 0.3, "t1": None, "targets": [4, 2, 4]},
        {"kind": "edge_scale", "t0": 0.3, "t1": 0.6, "edges": [[1, 2], [1, 2], [0, 5]], "factor": 0.5},
        {"kind": "param", "t0": 0.4, "t1": 0.5, "targets": {"5": {"gain": 1.5, "threshold": -0.2}}},
    ]
    q = P.validate(base(events=evs))
    kinds = [e["kind"] for e in q["events"]]
    assert sorted(kinds) == sorted(e["kind"] for e in evs)
    sil = next(e for e in q["events"] if e["kind"] == "silence")
    assert sil["targets"] == [2, 4]
    es = next(e for e in q["events"] if e["kind"] == "edge_scale")
    assert es["edges"] == [[0, 5], [1, 2]]
    kick = next(e for e in q["events"] if e["kind"] == "kick")
    assert P.semantics(sil) == "persistent" and P.semantics(kick) == "instantaneous"
    assert [e["kind"] for e in q["events"][:3]] == ["current", "current", "kick"]      # sorted by (start, kind, content)
    assert P.intervened_units(q) == {0, 1, 2, 3, 4, 5}


@pytest.mark.parametrize("bad, msg", [
    ({"kind": "kick", "t": 2.0, "delta": {"0": 1}}, "outside"),
    ({"kind": "current", "t0": 0.2, "t1": 0.2, "targets": {"0": 1}}, "t1 > t0"),
    ({"kind": "current_seq", "t0": 0.2, "seg": 0.02, "targets": {"0": [1, 2]}}, "seg"),
    ({"kind": "current_seq", "t0": 0.9, "seg": 0.05, "targets": {"0": [1, 2, 3]}}, "ends"),
    ({"kind": "edge_scale", "t0": 0.1, "t1": None, "edges": [[0, 1]], "factor": 3.0}, "factor"),
    ({"kind": "param", "t0": 0.1, "t1": None, "targets": {"0": {"gain": 0.0}}}, "> 0"),
    ({"kind": "param", "t0": 0.1, "t1": None, "targets": {"0": {"bias": 1.0}}}, "unknown"),
    ({"kind": "edge_remove", "t0": 0.1, "t1": None, "edges": [[0, 1]]}, "unknown event kind"),
    ({"kind": "kick", "t": 0.1, "delta": {"-1": 1}}, "non-negative"),
    ({"kind": "kick", "t": 0.1, "delta": {"0": 1}, "label": "x"}, "unknown key"),
    ({"kind": "latent_kick", "t": 0.1, "dz": [1.0]}, "truth"),
])
def test_invalid_events(bad, msg):
    with pytest.raises(P.ProtocolError, match=msg):
        P.validate(base(events=[bad]))


def test_truth_events_only_when_allowed():
    q = P.validate(base(events=[{"kind": "latent_set", "t": 0.1, "z": [1, 2]}]), allow_truth=True)
    assert q["events"][0]["z"] == [1.0, 2.0]


def test_top_level_errors_and_r0():
    with pytest.raises(P.ProtocolError, match="unknown key"):
        P.validate(base(group=3))
    with pytest.raises(P.ProtocolError, match="dt"):
        P.validate(base(dt=0.1))
    with pytest.raises(P.ProtocolError, match="lowercase hex"):
        P.validate(base(r0={"kind": "restart", "key": "XYZ", "t": 0.1}))
    q = P.validate(base(r0={"kind": "restart", "key": "ab" * 32, "t": 0.25}))
    assert q["r0"] == {"kind": "restart", "key": "ab" * 32, "t": 0.25}
    assert P.validate(base(r0={"kind": "zero"}))["r0"] == {"kind": "rest"}
    q = P.validate(base(r0={"kind": "state", "values": {"5": 1.0, 2: -0.5}}))
    assert list(q["r0"]["values"]) == ["2", "5"]


def test_hash_stability_and_microstate_key():
    p = base(events=[{"kind": "kick", "t": 0.1, "delta": {"0": 1.0}}])
    same = json.loads(json.dumps(p))
    same["events"][0]["delta"] = {0: 1}
    assert P.protocol_hash(p, system_hash="h", simulator="e") == P.protocol_hash(same, system_hash="h", simulator="e")
    assert P.protocol_hash(p, system_hash="h") != P.protocol_hash(p, system_hash="h2")
    noisy = {**p, "obs_noise": {"sd": 0.1, "seed": 4}}
    assert P.protocol_hash(noisy) != P.protocol_hash(p)
    assert P.protocol_hash(P.microstate_protocol(noisy)) == P.protocol_hash(P.microstate_protocol(p))


def test_breakpoints_include_sequence_segments_and_counterfactual():
    p = base(events=[{"kind": "current_seq", "t0": 0.2, "seg": 0.05, "targets": {"0": [1, 0, 1]}},
                     {"kind": "silence", "t0": 0.5, "t1": 0.7, "targets": [1]}])
    bp = P.breakpoints(p)
    for t in (0.0, 0.05, 0.2, 0.25, 0.3, 0.35, 0.5, 0.7, 1.0):
        assert t in bp
    tw = P.counterfactual(p)
    assert tw["events"] == [] and P.breakpoints(tw) == bp
    assert P.has_interventions(p) and not P.has_interventions(tw)


def test_from_format1():
    p3 = {"system": "s", "params_seed": 1, "t_end": 1.0, "dt": 0.01, "r0": {"kind": "zero"},
          "events": [{"kind": "edge_remove", "t0": 0.1, "t1": None, "edges": [[1, 2]]}]}
    q = P.from_format1(p3)
    assert q["events"][0] == {"kind": "edge_scale", "t0": 0.1, "t1": None, "edges": [[1, 2]], "factor": 0.0}
    assert q["r0"] == {"kind": "rest"}


def test_params_spread_and_process_noise_fields():
    q = P.validate(base())
    assert q["params_spread"] == 1.0 and q["process_noise"] is None           # always present in the canonical form
    assert list(q)[:5] == ["system", "params_seed", "params_spread", "weight_noise", "process_noise"]
    q2 = P.validate(base(params_spread=2, process_noise={"sd": 0.05, "seed": 7}))
    assert q2["params_spread"] == 2.0 and q2["process_noise"] == {"sd": 0.05, "seed": 7}
    for bad, msg in (({"params_spread": 3.5}, "params_spread"), ({"params_spread": -0.1}, "params_spread"),
                     ({"process_noise": {"sd": 0.1}}, "needs"), ({"process_noise": {"sd": 11.0, "seed": 1}}, "process_noise.sd")):
        with pytest.raises(P.ProtocolError, match=msg):
            P.validate(base(**bad))
    # both change trajectories, so both enter the content key and the microstate key (unlike observation noise)
    h = P.protocol_hash(base())
    assert P.protocol_hash(base(params_spread=1.0)) == h
    assert P.protocol_hash(base(params_spread=1.5)) != h
    assert P.protocol_hash(base(process_noise={"sd": 0.1, "seed": 1})) != h
    assert P.microstate_protocol(base(params_spread=1.5))["params_spread"] == 1.5
    assert P.microstate_protocol(base(process_noise={"sd": 0.1, "seed": 1}))["process_noise"] == {"sd": 0.1, "seed": 1}
