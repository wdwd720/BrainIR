"""truth() is complete and JSON-serialisable for every system; lifting is exact under weight noise too."""
import json

import numpy as np
import pytest

from p3synth.systems import catalog

from conftest import sim

NAMES = [d.name for d in catalog()]


@pytest.mark.parametrize("name", NAMES)
def test_truth_fields(systems, name):
    s = systems[name]
    t = json.loads(json.dumps(s.truth()))
    assert t["system_id"] == s.system_id and t["family_no"] in range(1, 21)
    if t["family_no"] == 20:
        assert t["k"] == "none" and t["K_total_coordinates"] >= 60
    else:
        assert 1 <= t["k"] <= 6
    assert len(t["neuron_roles"]) == s.n and t["observation_map"]["code"]
    assert t["observability"]["z_linearly_decodable_from_observed_activations"] in (True, False)
    assert t["f"] and t["g"]


def test_every_family_and_trap_present(systems):
    fams = {s.meta["family_no"] for s in systems.values()}
    traps = {s.meta["trap"] for s in systems.values()} - {None}
    assert fams == set(range(1, 21)) and traps == set("ABCDEFGHIJKL")
    codes = {s.impl.spec.get("code") for s in systems.values()}
    phis = {s.impl.spec.get("phi") for s in systems.values()}
    assert {"dense", "sparse", "redundant", "distributed"} <= codes and {"identity", "tanh", "logistic"} <= phis
    assert any(len(s.observed) < s.n for s in systems.values())
    ns = [s.n for s in systems.values()]
    assert min(ns) <= 12 and max(ns) >= 300


def test_latent_impulse_exact_under_weight_noise(systems):
    s = systems["hopf"]
    wn = {"sd": 0.1, "seed": 11}
    a, _ = sim(s, t_end=1.0, weight_noise=wn)
    b, _ = sim(s, t_end=1.0, weight_noise=wn, events=[{"kind": "latent_impulse", "t": 0.5, "delta": {"0": 0.2}}])
    # the recorded latent (population signal through the perturbed synapses) jumps by exactly (0.2, 0) at t = 0.5+
    ca, cb = a["info"]["truth"]["coords"], b["info"]["truth"]["coords"]
    assert np.allclose(ca[:51], cb[:51])
    x_pre = sim(s, t_end=1.0, weight_noise=wn, full=True)[0]["x_full"][50]
    dx = s.lift_latent([0.2, 0.0], x_pre, weight_noise=wn)
    c = sim(s, t_end=1.0, weight_noise=wn, events=[{"kind": "kick", "t": 0.5, "delta": {str(j): float(v) for j, v in enumerate(dx)}}])[0]
    assert np.abs(c["z"] - b["z"]).max() < 1e-6
    D = s.synaptic_readout(wn)
    v_pre = s.impl.phi.inv(x_pre)
    v_post = s.impl.phi.inv(x_pre + dx)
    assert np.allclose(D @ (v_post - v_pre), [0.2, 0.0], atol=1e-9)
