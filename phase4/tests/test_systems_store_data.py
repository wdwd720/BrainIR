import json

import numpy as np
import pytest

from brainir_causal import families as F
from brainir_causal import protocol as P
from brainir_causal.data import ExperimentSet, Trajectory
from brainir_causal.store import TrajectoryStore
from brainir_causal.synthadapter import ToySystem, observe_synthetic, suite_systems
from brainir_causal.systems import NAME_MAP, P3_INTERNAL, PUBLIC_REAL, load_real_internal, load_real_public, public_view

FORBIDDEN_TOKENS = ("manc", "male-cns", "malecns", "net1", "net2", "net3", ":mech:", "targets_heldout", "system_hash", "\"network\"")


@pytest.mark.skipif(not PUBLIC_REAL.exists(), reason="real systems not built")
def test_public_real_records_carry_no_hidden_information():
    pub = load_real_public()
    internal = load_real_internal()
    assert sorted(pub) == sorted(internal) and len(pub) == 10
    text = PUBLIC_REAL.read_text(encoding="utf-8").lower()
    for tok in FORBIDDEN_TOKENS:
        assert tok not in text, tok
    names = json.loads(NAME_MAP.read_text(encoding="utf-8"))["map"]
    p3 = json.loads(P3_INTERNAL.read_text(encoding="utf-8"))
    for sid, rec in pub.items():
        assert sid.startswith("real:") and sid.split(":")[1] in "ABC" and ("full" in sid or ":m" in sid)
        assert rec == public_view(internal[sid])
        old = p3[names[sid]]
        # populations unchanged; public targets = the old public targets; hidden targets stay internal
        assert rec["observed"] == old["observed"] and rec["readout"] == old["readout"] and rec["stimulus"] == old["stimulus"]
        assert rec["targets_public"] == sorted(old["targets_public"])
        assert internal[sid]["targets_heldout"] == sorted(old["targets_heldout"])
        assert not set(rec["targets_public"]) & set(internal[sid]["targets_heldout"])
        assert rec["split"]["families_train"] == list(F.REAL_TRAIN) and rec["edges_public"] == []
        assert rec["obs_scale"]["x"] > 0 and rec["obs_scale"]["y"] > 0
        assert set(rec["horizons_s"]) == {"short", "medium", "long"} and rec["horizons_s"]["medium"] == 0.25
    # one full network per letter, mechanisms numbered from 1
    letters = {sid.split(":")[1] for sid in pub}
    assert letters == {"A", "B", "C"} and all(f"real:{L}:full" in pub for L in letters)


def test_store_generic_records_and_single_computation(tmp_path):
    store = TrajectoryStore(tmp_path)
    calls = []
    p = {"system": "syn:toy:0", "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]],
         "events": [{"kind": "kick", "t": 0.3, "delta": {"1": 0.5}}]}
    toy = ToySystem(1, 0)

    def compute():
        calls.append(1)
        return toy.simulate(p, full=True)

    key = store.key(p, toy.content_hash(), toy.engine_id)
    k1, r1, c1 = store.get_or_compute(key, compute, {"system_id": toy.system_id})
    k2, r2, c2 = store.get_or_compute(key, compute, {"system_id": toy.system_id})
    assert c1 and not c2 and len(calls) == 1 and k1 == k2
    assert np.array_equal(r1["x"], r2["x"]) and np.array_equal(r1["state"], r2["state"]) and r2["info"]["engine"] == toy.engine_id
    noisy = {**p, "obs_noise": {"sd": 0.1, "seed": 1}}
    assert store.key(noisy, toy.content_hash(), toy.engine_id) == key          # same microstate key
    assert [r["key"] for r in store.index()] == [key]


def test_toy_system_semantics():
    toy = suite_systems("toy", 3)["syn:toy:0"]
    base = {"system": toy.system_id, "params_seed": 0, "t_end": 2.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]}
    r0 = toy.simulate(base, full=True)
    rk = toy.simulate({**base, "events": [{"kind": "latent_kick", "t": 1.0, "dz": [1.0, 0.0]}]}, full=True)
    i = 100
    assert np.allclose(rk["z"][i + 1] - r0["z"][i + 1], [1.0, 0.0], atol=0.05)         # the truth event moves z by dz
    assert np.array_equal(rk["z"][: i + 1], r0["z"][: i + 1])
    # restart from the stored full state continues the trajectory exactly (float64 state)
    rr = toy.simulate({**base, "t_end": 1.0}, full=True, restart_state=r0["state"][100])
    assert np.allclose(rr["state"], r0["state"][100:], atol=1e-12)
    obs = observe_synthetic(r0, toy.public_record(), {**base, "obs_noise": {"sd": 0.1, "seed": 3}})
    assert obs["x"].shape == r0["x"].shape and not np.array_equal(obs["x"], r0["x"])
    for kind_ev in ({"kind": "silence", "t0": 0.5, "t1": None, "targets": [0]},
                    {"kind": "edge_scale", "t0": 0.5, "t1": 1.5, "edges": [[0, 1]], "factor": 0.0},
                    {"kind": "param", "t0": 0.5, "t1": 1.0, "targets": {"0": {"gain": 1.5}}},
                    {"kind": "current_seq", "t0": 0.5, "seg": 0.05, "targets": {"2": [1.0, 0.0, 1.0]}}):
        r = toy.simulate({**base, "events": [kind_ev]})
        assert np.array_equal(r["x"][:51], r0["x"][:51]) and not np.array_equal(r["x"], r0["x"])


def test_experiment_set_roundtrip(tmp_path):
    toy = ToySystem(0, 0)
    base = {"system": toy.system_id, "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]}
    iv = {**base, "events": [{"kind": "kick", "t": 0.5, "delta": {"0": 0.5}}]}
    es = ExperimentSet(systems={toy.system_id: toy.public_record()}, dataset_id="t")
    for p, split, meta in ((iv, "train", {}), (P.counterfactual(iv), "twin", {"twin_of": P.protocol_hash(iv)})):
        r = toy.simulate(p)
        q = P.validate(p)
        es.add(Trajectory(key=P.protocol_hash(q), system_id=toy.system_id, split=split, family=F.family_of(q, toy.public_record()),
                          protocol=q, t=r["t"], x=r["x"], u=r["u"], y=r["y"], meta=meta, provenance="benchmark"))
    es.save(tmp_path / "set")
    back = ExperimentSet.load(tmp_path / "set")
    assert len(back) == 2 and back.twins()[P.protocol_hash(iv)].split == "twin"
    assert back[0].family == "kick.1" and back[1].family == "obs.nominal" and back[0].is_intervention
    assert np.array_equal(back[0].x, es[0].x)
    lazy = ExperimentSet.load(tmp_path / "set", lazy=True)
    assert len(lazy.select(split="twin")) == 1 and lazy.materialise()[1].meta["twin_of"] == P.protocol_hash(iv)


def test_toy_truth_interface_is_exact_under_additive_interventions():
    from brainir_causal.synthadapter import SyntheticSystem
    toy = ToySystem(5, 1)
    assert isinstance(toy, SyntheticSystem) and toy.n_units == 6 and toy.readout_dim == 1 and toy.capability()["latent"]["supported"]
    rng = np.random.default_rng(0)
    x0 = toy.pool_states(1, rng)[0]
    base = {"system": toy.system_id, "params_seed": 2, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]}
    fut = [{"kind": "kick", "t": 0.2, "delta": {"4": 0.7}}, {"kind": "current", "t0": 0.4, "t1": 0.6, "targets": {"1": -0.8}},
           {"kind": "current_seq", "t0": 0.6, "seg": 0.05, "targets": {"3": [0.5, 0.0, 0.5]}}]
    # equivalent microstates (same z, different microscopic detail) have the same readout future under additive interventions
    r_ref = toy.simulate({**base, "events": fut}, full=True, restart_state=x0)
    for xe in toy.equivalent_states(x0, 3, rng):
        assert np.allclose(toy.true_state(xe), toy.true_state(x0), atol=1e-12) and not np.allclose(xe, x0)
        r = toy.simulate({**base, "events": fut}, full=True, restart_state=xe)
        assert np.allclose(r["y"], r_ref["y"], atol=1e-5) and np.allclose(r["z"], r_ref["z"], atol=1e-9)
    # the kick's true latent effect equals the simulated jump of z
    ev = {"kind": "kick", "t": 0.3, "delta": {"0": 0.4, "5": -0.2}}
    r0 = toy.simulate(base, full=True, restart_state=x0)
    rk = toy.simulate({**base, "events": [ev]}, full=True, restart_state=x0)
    i = 30
    jump = (rk["z"][i + 1] - r0["z"][i + 1])
    assert np.allclose(jump, toy.true_latent_effect(rk["state"][i], ev), atol=2e-3)
    assert np.allclose(toy.true_latent_effect(x0, {"kind": "latent_kick", "t": 0.0, "dz": [0.1, -0.2]}), [0.1, -0.2])
    # lifts: distinct microscopic interventions, each realising z + dz exactly, with equal readout futures
    dz = np.array([0.3, -0.5])
    lifts = toy.lift_latent(x0, dz, 3)
    assert len(lifts) == 3 and len({json.dumps(lf, sort_keys=True) for lf in lifts}) == 3
    ys = []
    r_do = toy.simulate({**base, "events": [{"kind": "latent_kick", "t": 0.0, "dz": dz.tolist()}]}, full=True, restart_state=x0)
    for lf in lifts:
        assert np.allclose(toy.true_latent_effect(x0, lf[0]), dz, atol=1e-10)
        r = toy.simulate({**base, "events": lf}, full=True, restart_state=x0)
        assert np.allclose(r["z"], r_do["z"], atol=1e-9)          # the lift realises do(z := z + dz) exactly
        ys.append(r["y"])
    assert np.allclose(ys[0], ys[1], atol=1e-5) and np.allclose(ys[0], ys[2], atol=1e-5)
    t = toy.truth()
    assert t["k"] == 2 and "silence" in t["approximate_for"] and toy.obs_shortcut_state(x0) is None
    assert np.array_equal(toy.rest_state(), np.zeros(6))

