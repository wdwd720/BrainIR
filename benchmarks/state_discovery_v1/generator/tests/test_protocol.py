import pytest

from p3synth.protocol import ProtocolError, intervened_neurons, validate


def base(**kw):
    p = {"system": "syn-x", "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.2, 1.0]], "events": []}
    p.update(kw)
    return p


def test_canonical_form_and_snapping():
    q = validate(base(events=[{"kind": "kick", "t": 0.1234, "delta": {3: 0.5, "1": -1}}]))
    assert q["stimulus"] == [[0.0, 0.0], [0.2, 1.0]]
    assert q["events"][0]["t"] == 0.12 and list(q["events"][0]["delta"]) == ["1", "3"]
    assert q["r0"] == {"kind": "zero"} and q["weight_noise"] is None


def test_negative_r0_and_vector_stimulus_allowed():
    q = validate(base(r0={"kind": "state", "values": {"0": -1.5}}, stimulus=[[0, [1, 0]]]), input_dim=2)
    assert q["r0"]["values"]["0"] == -1.5 and q["stimulus"][0][1] == [1.0, 0.0]
    with pytest.raises(ProtocolError):
        validate(base(stimulus=[[0, [1, 0, 0]]]), input_dim=2)


def test_latent_events_are_evaluator_only():
    p = base(events=[{"kind": "latent_set", "t": 0.5, "values": {"0": 1.0}}])
    assert validate(p, k=2)["events"][0]["values"] == {"0": 1.0}
    with pytest.raises(ProtocolError):
        validate(p, allow_latent=False)
    with pytest.raises(ProtocolError):
        validate(base(events=[{"kind": "latent_impulse", "t": 0.5, "delta": {"3": 1.0}}]), k=2)


def test_ranges_and_neuron_ids():
    with pytest.raises(ProtocolError):
        validate(base(events=[{"kind": "kick", "t": 0.5, "delta": {"12": 1.0}}]), n=10)
    with pytest.raises(ProtocolError):
        validate(base(events=[{"kind": "current", "t0": 0.5, "t1": 0.5, "targets": {"1": 1.0}}]))
    with pytest.raises(ProtocolError):
        validate(base(t_end=30.0))
    ev = [{"kind": "edge_remove", "t0": 0.1, "t1": None, "edges": [[1, 2], [1, 2]]},
          {"kind": "silence", "t0": 0.1, "t1": 0.3, "targets": [5, 4]}]
    q = validate(base(events=ev))
    assert q["events"][0]["edges"] == [[1, 2]] or q["events"][1]["edges"] == [[1, 2]]
    assert intervened_neurons(q) == {1, 2, 4, 5}


def test_noise_seed_field():
    assert "noise_seed" not in validate(base())                      # unchanged canonical form without the field
    q = validate(base(noise_seed=7))
    assert q["noise_seed"] == 7
    from p3synth.protocol import canonical_json, protocol_hash
    assert '"noise_seed":7' in canonical_json(base(noise_seed=7))
    assert protocol_hash(base(noise_seed=7)) != protocol_hash(base(noise_seed=8)) != protocol_hash(base())
    for bad in (-1, 1.5, "3", True):
        with pytest.raises(ProtocolError):
            validate(base(noise_seed=bad))
