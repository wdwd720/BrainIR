"""brainir_causal.suites: seeds, rotations, partitions, magnitudes, protocol generation per family (fast; no simulation)."""

from __future__ import annotations

import collections
import hashlib
import json

import numpy as np
import pytest

from brainir_causal import families as F
from brainir_causal import protocol as P
from brainir_causal import suites as S
from brainir_causal.synthadapter import TOY_CAPABILITY, ToySystem


@pytest.fixture()
def temp_salt(tmp_path, monkeypatch):
    salt = "ab" * 32
    sf = tmp_path / "salt.txt"
    sf.write_text(salt + "\n", encoding="utf-8")
    cf = tmp_path / "salt_commitment.json"
    cf.write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt.encode()).hexdigest()}), encoding="utf-8")
    monkeypatch.setattr(S, "SALT_FILE", sf)
    monkeypatch.setattr(S, "COMMITMENT", cf)
    monkeypatch.setattr(S, "METHOD_LOCK", tmp_path / "METHOD_LOCK.json")
    return salt


def toy_records(tier="toy"):
    pubs, ints, _ = S.synthetic_tier_records(tier, S.DEV_SEED)
    return pubs, ints


def test_salt_commitment_and_seed_ranges(temp_salt):
    assert S.read_salt() == temp_salt
    assert S.HIDDEN_SEED_BASE <= S.hidden_seed("x", 1) < 2 * S.HIDDEN_SEED_BASE
    assert 0 <= S.public_seed_of("x", 1) < S.HIDDEN_SEED_BASE
    assert S.tier_seed("val") != S.tier_seed("conf")
    assert S.tier_seed("dev") == S.DEV_SEED
    fn_pub, fn_hid = S.seed_counter(False, "a"), S.seed_counter(True, "a")
    assert all(s < S.HIDDEN_SEED_BASE for s in (fn_pub() for _ in range(5)))
    assert all(s >= S.HIDDEN_SEED_BASE for s in (fn_hid() for _ in range(5)))


def test_wrong_salt_is_refused(temp_salt):
    S.SALT_FILE.write_text("cd" * 32, encoding="utf-8")
    with pytest.raises(RuntimeError):
        S.read_salt()


def test_confirmation_tier_requires_the_lock(temp_salt):
    with pytest.raises(PermissionError):
        S.build_tier("conf")
    with pytest.raises(PermissionError):
        S.build_real("C")


def test_rotations_are_balanced_and_distinct_within_type():
    cap = S.normalize_capability(TOY_CAPABILITY, t_end=4.0, dt=0.01)
    systems = {f"s{t}_{j}": {"type": f"type{t}", "capability": cap} for t in range(25) for j in range(2)}
    rot = S.assign_rotations(systems, 123)
    for t in range(25):
        assert rot[f"s{t}_0"]["rotation"] != rot[f"s{t}_1"]["rotation"]
    counts = collections.Counter(r["rotation"] for r in rot.values())
    assert max(counts.values()) - min(counts.values()) <= 1
    assert rot == S.assign_rotations(systems, 123)


def test_rotation_falls_back_when_a_family_is_not_producible():
    cap = S.normalize_capability({**TOY_CAPABILITY, "edge_scale": {"supported": False}, "param": {"supported": False}}, t_end=4.0, dt=0.01)
    rot = S.assign_rotations({f"a{j}": {"type": "t", "capability": cap} for j in range(4)}, 7)
    assert all(r["rotation"] in ("R1", "R4") and not r["reduced"] for r in rot.values())


def test_partition_is_deterministic_and_disjoint():
    pub, hid = S.partition(list(range(10)), "targets", "dev", 1, "sys")
    assert (pub, hid) == S.partition(list(range(10)), "targets", "dev", 1, "sys")
    assert set(pub).isdisjoint(hid) and sorted(pub + hid) == list(range(10)) and len(pub) == 5
    assert S.partition([3], "t")[0] == [3]


def test_public_record_hides_hidden_targets_and_full_sets():
    pubs, ints = toy_records()
    for sid, p in pubs.items():
        assert "targetable" not in p and "edges" not in p and "targets_heldout" not in p
        assert set(p["targets_public"]).isdisjoint(ints[sid]["targets_heldout"])
        assert p["split"]["families_train"] and p["split"]["rotation"] in F.ROTATIONS


def test_magnitude_classes_are_ordered_and_bounded():
    cap = S.normalize_capability(TOY_CAPABILITY, t_end=4.0, dt=0.01)
    rng = np.random.default_rng(0)
    for kind in ("kick", "current", "edge_scale"):
        vals = {c: [S.class_value(cap, kind, c, rng) for _ in range(200)] for c in S.MAG_CLASSES}
        for lo, hi in zip(S.MAG_CLASSES, S.MAG_CLASSES[1:]):
            assert max(vals[lo]) < min(vals[hi])
        assert max(vals["strong"]) <= cap[kind]["max"] + 1e-12
    hi = [S.class_value(cap, "kick", "hi", rng) for _ in range(100)]
    assert min(hi) >= cap["kick"]["hi_range"][0] and max(hi) <= cap["kick"]["hi_range"][1]


@pytest.mark.parametrize("family", [f for f in F.INTERVENTION_FAMILIES] + list(F.OBS))
def test_every_family_round_trips_through_family_of(family):
    pubs, _ = toy_records()
    pub = pubs[min(pubs)]
    rng = np.random.default_rng(11)
    s = S.FamilySampler(pub, rng, S.seed_counter(False, "t"), targets=[0, 1, 2, 3, 4, 5], edges=[[0, 1], [1, 2], [2, 3]])
    for _ in range(12):
        p, _info = s.make(family, mclass="moderate") if family not in F.OBS else (s.obs(family), {"family": family})
        q = P.validate(p)
        got = F.family_of(q, pub)
        if family == "obs.nominal":
            assert got in ("obs.nominal", "obs.param")
        elif family == "obs.param":
            assert got in ("obs.param", "obs.nominal")
        else:
            assert got == family, (family, got, q["events"])
        if q["events"]:
            P.validate(P.counterfactual(q))


def test_plans_are_deterministic_and_seed_ranges_follow_the_tier(temp_salt):
    pubs, ints = toy_records()
    sid = min(pubs)
    a = S.plan_system(pubs[sid], ints[sid], tier="toy", seed=S.DEV_SEED, level="C", sets=("public", "tests", "pool_src"))
    b = S.plan_system(pubs[sid], ints[sid], tier="toy", seed=S.DEV_SEED, level="C", sets=("public", "tests", "pool_src"))
    assert [json.dumps(x.protocol, sort_keys=True) for x in a] == [json.dumps(x.protocol, sort_keys=True) for x in b]
    assert all(x.protocol["params_seed"] < S.HIDDEN_SEED_BASE for x in a)
    roles = collections.Counter(x.role.split(":")[0] for x in a)
    for r in ("d0", "d1", "in", "target", "near", "far", "hidden", "passive", "ood", "robust", "pool_src"):
        assert roles[r] > 0, r
    hid = S.plan_system(pubs[sid], ints[sid], tier="val", seed=S.DEV_SEED, level="B", sets=("tests",))
    assert all(x.protocol["params_seed"] >= S.HIDDEN_SEED_BASE for x in hid)


def test_test_items_are_arranged_in_identity_cells():
    pubs, ints = toy_records()
    sid = min(pubs)
    specs = S.plan_system(pubs[sid], ints[sid], tier="toy", seed=S.DEV_SEED, level="B", sets=("tests",))
    cells = collections.Counter(x.cell for x in specs if x.role in ("in", "near", "far", "hidden", "target"))
    assert cells and min(cells.values()) >= S.STATES_PER_CELL
    for x in specs:
        if x.role in ("in", "near", "far") and x.family not in ("edge.w", "edge.rm"):
            assert set(P.intervened_units(x.protocol)) <= set(pubs[sid]["targets_public"])
        if x.role == "target" and x.family not in ("edge.w", "edge.rm"):
            assert set(P.intervened_units(x.protocol)) <= set(ints[sid]["targets_heldout"])


def test_robustness_jitter_keeps_the_told_events_and_ood_uses_params_spread():
    pubs, ints = toy_records()
    sid = min(pubs)
    specs = S.plan_system(pubs[sid], ints[sid], tier="toy", seed=S.DEV_SEED, level="C", sets=("tests",))
    jit = [x for x in specs if x.role in ("robust:amplitude_jitter", "robust:timing_jitter")]
    assert jit and all("model_events" in x.meta for x in jit)
    assert any(x.meta["model_events"] != x.protocol["events"] for x in jit)
    spread = [x for x in specs if x.role == "ood:param_spread"]
    if S.protocol_has("params_spread"):
        assert spread and all(x.protocol.get("params_spread") == S.PARAMS_SPREAD_OOD and not x.meta.get("proxy") for x in spread)
    proc = [x for x in specs if x.role.startswith("robust:process_noise")]
    if S.protocol_has("process_noise") and TOY_CAPABILITY["process_noise"]["supported"]:
        assert proc and all(x.protocol.get("process_noise") for x in proc)


def test_real_mechanism_plans_validate_against_family_labels():
    from brainir_causal.systems import load_real_internal, public_view
    ints = load_real_internal()
    sid = min(s for s in ints if ":m" in s)
    pub = public_view(ints[sid])
    specs = S.plan_system(pub, ints[sid], tier="real_public", seed=0, level="B", sets=("public",))
    assert specs
    for x in specs:
        q = P.validate(x.protocol)
        assert F.family_of(q, pub) in pub["split"]["families_train"]


def test_toy_system_has_the_contract_methods():
    s = ToySystem(1, 0)
    assert callable(getattr(s, "pool_states", None)) and callable(getattr(s, "equivalent_states", None))
