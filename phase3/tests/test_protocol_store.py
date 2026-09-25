"""Protocol canonicalisation, trajectory-store keys (goal4 section 71 'TRAJECTORY STORE') and the service's public policy."""

from __future__ import annotations

import numpy as np
import pytest

from brainir_state import protocol as P
from brainir_state.simservice import check_public
from brainir_state.store import TrajectoryStore

BASE = {"system": "real:net1:full", "params_seed": 3, "t_end": 1.0, "dt": 0.001, "stimulus": [[0.02, 1.0]]}


def test_canonical_form_and_hash_are_deterministic():
    a = dict(BASE, events=[{"kind": "kick", "t": 0.5004, "delta": {12: 5.0, 3: -2.0}}])
    b = dict(BASE, events=[{"kind": "kick", "t": 0.5, "delta": {"3": -2.0, "12": 5.0}}])
    assert P.canonical_json(a) == P.canonical_json(b)
    assert P.protocol_hash(a, system_hash="s", simulator="e") == P.protocol_hash(b, system_hash="s", simulator="e")


def test_hash_separates_systems_simulators_and_protocols():
    h = P.protocol_hash(BASE, system_hash="s1", simulator="e")
    assert h != P.protocol_hash(BASE, system_hash="s2", simulator="e")
    assert h != P.protocol_hash(BASE, system_hash="s1", simulator="e2")
    assert h != P.protocol_hash(dict(BASE, params_seed=4), system_hash="s1", simulator="e")


def test_invalid_protocols_rejected():
    with pytest.raises(P.ProtocolError):
        P.validate(dict(BASE, dt=1.0))
    with pytest.raises(P.ProtocolError):
        P.validate(dict(BASE, events=[{"kind": "teleport", "t": 0.1}]))
    with pytest.raises(P.ProtocolError):
        P.validate(dict(BASE, events=[{"kind": "current", "t0": 0.5, "t1": 0.4, "targets": {1: 3.0}}]))


def test_breakpoints_and_intervened():
    p = dict(BASE, events=[{"kind": "current", "t0": 0.3, "t1": 0.35, "targets": {7: 3.0}}, {"kind": "silence", "t0": 0.6, "t1": None, "targets": [8, 9]}])
    assert P.breakpoints(p) == [0.0, 0.02, 0.3, 0.35, 0.6, 1.0]
    assert P.intervened_neurons(p) == {7, 8, 9}


def test_store_roundtrip_and_no_collisions(tmp_path):
    st = TrajectoryStore(tmp_path)
    rec = {"t": np.arange(3) * 0.001, "neurons": np.array([1, 5], np.int32), "rates": np.ones((3, 2), np.float32), "u": np.zeros((3, 1), np.float32),
           "info": {"engine": "x"}}
    k1 = st.key(BASE, "sysA", "eng")
    k2 = st.key(BASE, "sysB", "eng")
    assert k1 != k2
    st.put(k1, rec, {"system_id": "a"})
    got = st.get(k1)
    assert got is not None and np.array_equal(got["neurons"], rec["neurons"]) and got["info"]["engine"] == "x"
    assert st.get(k2) is None


SYS = {"observed": [1, 2, 3, 4], "targets_public": [1, 2]}


@pytest.mark.parametrize("proto,allowed", [
    (BASE, True),
    (dict(BASE, params_seed=10**9 + 5), False),                                               # hidden seed range
    (dict(BASE, stimulus=[[0.0, 1.7]]), False),                                               # OOD stimulus
    (dict(BASE, stimulus=[[0.0, 0.4]]), False),
    (dict(BASE, events=[{"kind": "kick", "t": 0.5, "delta": {"1": 10.0}}]), True),
    (dict(BASE, events=[{"kind": "kick", "t": 0.5, "delta": {"3": 10.0}}]), False),           # held-out target
    (dict(BASE, events=[{"kind": "silence", "t0": 0.5, "t1": None, "targets": [1, 2]}]), False),   # group silencing
    (dict(BASE, events=[{"kind": "silence", "t0": 0.5, "t1": 0.8, "targets": [1]},
                        {"kind": "silence", "t0": 0.6, "t1": 0.9, "targets": [2]}]), False),  # overlapping windows = group
    (dict(BASE, events=[{"kind": "silence", "t0": 0.5, "t1": 0.6, "targets": [1]},
                        {"kind": "silence", "t0": 0.7, "t1": 0.9, "targets": [2]}]), True),
    (dict(BASE, events=[{"kind": "edge_remove", "t0": 0.5, "t1": None, "edges": [[1, 2]]}]), False),
    (dict(BASE, weight_noise={"sd": 0.2, "seed": 1}), False),
    (dict(BASE, r0={"kind": "state", "values": {"9": 1.0}}), False),                          # unobserved neuron
])
def test_public_policy(proto, allowed):
    q = P.validate(proto)
    assert (check_public(q, SYS) is None) == allowed, check_public(q, SYS)
