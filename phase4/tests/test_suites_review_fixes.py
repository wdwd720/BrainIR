"""The dataset fixes of the early reviews F (leakage), H (numerics) and E (statistics) in `brainir_causal.suites` and the store:
F-B1 / minor 7 (public whitelists, pool truth outside the public part), F-M6 / minor 8 (salted seeds and streams), minor 2 (own
read-only arrays), H-B1 (floor futures), H-M3 (nominal dt; temporal-sampling items), H-M4 (failed / non-finite records refused and
replaced), H-M5 (host fingerprint), H-M6 (restart checks), H minor 2 (stored pool input), H minor 9 (obs_scale in noisy keys),
E-M2 (identity-cell groups)."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from brainir_causal import protocol as P
from brainir_causal import suites as S
from brainir_causal.store import InvalidRecord, TrajectoryStore, check_record
from brainir_causal.synthadapter import ToySystem

TINY = {"B_MAIN": {"synthetic": 3, "full": 3, "mech": 3}, "D0_DESIGN": {"obs.nominal": 2, "obs.stim": 1, "obs.init": 1, "obs.wnoise": 1},
        "POOL_DRAWS": 2, "POOL_TRAJ": 6, "POOL_STATES": 2, "POOL_FLOOR_STATES": 2, "N_PASSIVE_TEST": 4, "CELLS_PER_FAMILY": 1,
        "STATES_PER_CELL": 2, "ITEMS_PER_CATEGORY": 1, "N_EQUIV_STATES": 1, "N_LIFT_CASES": 2}


@pytest.fixture()
def temp_salt(tmp_path, monkeypatch):
    salt = "cd" * 32
    sf = tmp_path / "salt.txt"
    sf.write_text(salt + "\n", encoding="utf-8")
    cf = tmp_path / "salt_commitment.json"
    cf.write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt.encode()).hexdigest()}), encoding="utf-8")
    monkeypatch.setattr(S, "SALT_FILE", sf)
    monkeypatch.setattr(S, "COMMITMENT", cf)
    return salt


def _tiny_build(tmp_path_factory, parts):
    root = tmp_path_factory.mktemp("rf")
    salt = "ef" * 32
    (root / "salt.txt").write_text(salt, encoding="utf-8")
    (root / "commit.json").write_text(json.dumps({"sha256_of_salt": hashlib.sha256(salt.encode()).hexdigest()}), encoding="utf-8")
    saved = {k: getattr(S, k) for k in list(TINY) + ["SALT_FILE", "COMMITMENT"]}
    for k, v in TINY.items():
        setattr(S, k, v)
    S.SALT_FILE, S.COMMITMENT = root / "salt.txt", root / "commit.json"
    try:
        summ = S.build_tier("toy", workers=1, systems=["syn:toy:0"], root=root / "suites", store_root=root / "store", parts=parts)
    finally:
        for k, v in saved.items():
            setattr(S, k, v)
    return root, summ


@pytest.fixture(scope="module")
def tiny_public(tmp_path_factory):
    """The PUBLIC part of one toy system, tiny (fast)."""
    return _tiny_build(tmp_path_factory, S.TIER_PARTS["toy"][:1])


@pytest.fixture(scope="module")
def tiny_both(tmp_path_factory):
    """Both parts of one toy system, tiny (slow: the eval part holds every held-out family)."""
    return _tiny_build(tmp_path_factory, S.TIER_PARTS["toy"])


# ------------------------------------------------------------------------------------------------ F-B1 / minor 7
def test_public_part_holds_no_truth_and_passes_the_whitelists(tiny_public):
    root, summ = tiny_public
    dirs = S.tier_dirs("toy", root / "suites")
    d = dirs["public"] / "syn_toy_0"
    assert summ["systems"]["syn:toy:0"]["public"]["public_check"]["rows"] > 0
    S.assert_public_part(d)
    with np.load(d / "pools" / "futures.npz") as z:
        keys = list(z.files)
    assert keys and all(S.PUBLIC_FUTURE_KEY.match(k) for k in keys) and not any(k.endswith("_z") for k in keys)
    # the true latents of the pool futures live in the truth directory only
    with np.load(dirs["truth"] / "syn_toy_0" / "pools" / "public_futures_truth.npz") as z:
        assert z.files and all(k.endswith("_z") for k in z.files)
    rows = [json.loads(line) for line in (d / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    assert all(set(r["info"]) <= set(S.SYNTHETIC_INFO_KEYS) for r in rows) and all("host" in r["info"] for r in rows)
    assert all("engine" not in r["info"] and "system_id" not in r["info"] for r in rows)


def test_public_part_check_refuses_truth_and_extra_fields(tiny_public, tmp_path):
    import shutil
    root, _ = tiny_public
    src = S.tier_dirs("toy", root / "suites")["public"] / "syn_toy_0"
    d = tmp_path / "copy"
    shutil.copytree(src, d)
    with np.load(d / "pools" / "futures.npz") as z:
        arr = {k: z[k] for k in z.files}
    np.savez_compressed(d / "pools" / "futures.npz", **arr, s0_none_z=np.zeros((3, 2), np.float32))
    with pytest.raises(AssertionError, match="non-public arrays"):
        S.assert_public_part(d)
    np.savez_compressed(d / "pools" / "futures.npz", **arr)
    lines = (d / "index.jsonl").read_text(encoding="utf-8").splitlines()
    row = json.loads(lines[0])
    row["info"]["network"] = "leak"
    (d / "index.jsonl").write_text("\n".join([json.dumps(row)] + lines[1:]) + "\n", encoding="utf-8")
    with pytest.raises(AssertionError, match="info.network"):
        S.assert_public_part(d)


def test_generator_pass_through_is_a_whitelist():
    pub = ToySystem(3, 0).public_record()
    pub = {**pub, "type": "bistable", "variant": "v2", "k": 3, "trap": "x"}
    rot = {"rotation": "R4", "reduced": False, "families_train": ["kick.1", "pulse.1", "sil.1", "sil.2"]}
    public, _internal = S.synthetic_records(pub, tier="toy", seed=S.DEV_SEED, rotation=rot, system_hash="h", engine_id="e")
    assert not {"type", "variant", "k", "trap", "targetable", "edges"} & set(public)
    assert set(public) <= S.PUBLIC_RECORD_KEYS


def test_dataset_info_drops_names_sizes_and_bundles():
    info = {"engine": "p4-realsim-1", "simulator": "m", "n": 12345, "network": "net", "bundle_sha256": "b", "system_id": "real:A:m1",
            "success": True, "n_calls": 3, "host": {"cpu": {}}}
    assert S.dataset_info(info, "real") == {"engine": "p4-realsim-1", "success": True, "n_calls": 3, "host": {"cpu": {}}}   # never the model id (P4-D26)
    assert "engine" not in S.dataset_info(info, "synthetic")


# ------------------------------------------------------------------------------------------------ F-M6 / minor 8
def test_hidden_tier_seeds_are_128_bit_hmacs(temp_salt):
    import hmac
    v = S.tier_seed("val")
    assert v == int(hmac.new(temp_salt.encode(), b"synthetic-tier|val", hashlib.sha256).hexdigest()[:32], 16)
    assert v.bit_length() > 64 and v != S.tier_seed("conf") and S.tier_seed("dev") == S.DEV_SEED
    assert S.real_stream_seed("public") == 0 and S.real_stream_seed("B").bit_length() > 64
    assert 0 <= S.salted_public_seed("x", 1) < S.HIDDEN_SEED_BASE <= S.hidden_seed("x", 1) < 2 * S.HIDDEN_SEED_BASE


def test_public_part_seeds_of_hidden_tiers_are_salted(temp_salt):
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    salted = S.plan_system(pubs[sid], ints[sid], tier="val", seed=12345, level="B", sets=("public",), policy="public")
    plain = S.plan_system(pubs[sid], ints[sid], tier="dev", seed=12345, level="B", sets=("public",), policy="public")
    seeds_s = [x.protocol["params_seed"] for x in salted if x.protocol["params_seed"] >= 8]
    seeds_p = [x.protocol["params_seed"] for x in plain if x.protocol["params_seed"] >= 8]
    assert seeds_s and all(s < S.HIDDEN_SEED_BASE for s in seeds_s)
    fn = S.seed_counter(False, "pub", "val", 12345, sid)                 # the unsalted derivation a developer could compute
    assert not set(seeds_s) & {fn() for _ in range(2000)} and set(seeds_p) != set(seeds_s)


@pytest.mark.slow
def test_eval_pool_sequences_are_salted(tiny_both):
    root, _ = tiny_both
    dirs = S.tier_dirs("toy", root / "suites")
    pub_seq = json.loads((dirs["public"] / "syn_toy_0" / "pools" / "pool.json").read_text(encoding="utf-8"))["sequences"]
    ev_seq = json.loads((dirs["eval"] / "syn_toy_0" / "pools" / "pool.json").read_text(encoding="utf-8"))["sequences"]
    common = set(pub_seq) & set(ev_seq)
    assert common and any(pub_seq[k]["events"] != ev_seq[k]["events"] for k in common)


def test_spare_seeds_follow_the_planned_range(temp_salt):
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    specs = S.plan_system(pubs[sid], ints[sid], tier="val", seed=7, level="B", sets=("tests", "pool_src"))
    for x in specs:
        if x.split == "pool_src" or x.meta.get("restart_from") or x.meta.get("carrier_from"):
            assert x.spares == []            # fixed draw structure / the restart source's draw (LOG P4-D36)
        else:
            assert len(x.spares) == S.N_SPARE_SEEDS
            hid = x.protocol["params_seed"] >= S.HIDDEN_SEED_BASE
            assert all((s >= S.HIDDEN_SEED_BASE) == hid for s in x.spares)


# ------------------------------------------------------------------------------------------------ minor 2 / E-M2 / H minor 2 / H-B1
@pytest.mark.slow
def test_eval_inputs_own_read_only_arrays_grouped_by_identity_cell(tiny_both):
    root, _ = tiny_both
    dirs = S.tier_dirs("toy", root / "suites")
    inp = S.load_eval_inputs("syn:toy:0", heldout_dirs=dirs, part="eval")
    items = inp["items"]
    assert items
    for it in items:
        for a in (it.x_hist, it.u_hist, it.u_future, it.y_future):
            assert not a.flags.writeable and (a.base is None or a.base.base is None)
            with pytest.raises(ValueError):
                a[...] = 0.0
    iv = [it for it in items if not it.is_passive]
    assert iv and all(it.group.startswith("cell:") and it.group == "cell:" + it.meta["identity_cell"] for it in iv)
    assert all(json.loads(it.meta["identity_cell"])[0] == it.family for it in iv)
    pool = inp["pool"]
    u = pool.sequences["none"]["u_future"]
    assert not u.flags.writeable and all(sq["u_future"] is u for sq in pool.sequences.values())
    fl = [s for s in pool.states if s.floor_futures]
    assert len(fl) == TINY["POOL_FLOOR_STATES"]
    for s in fl:
        ff = s.floor_futures
        assert set(ff) == {"noop", "f32"} and all(len(v) == 2 for v in ff.values())
        assert all(a.shape == s.futures["none"].shape for v in ff.values() for a in v)
        # the toy integrator is fixed-step: the repeat and the float64 continuation coincide with the restart bit for bit
        assert np.array_equal(ff["noop"][0], ff["noop"][1]) and np.array_equal(ff["f32"][0], s.futures["none"])
    assert pool.floor_div is None and all(s.floor_div is None for s in pool.states)
    eq = [s for s in pool.states if s.meta.get("truth_only")]
    assert all(s.z_true is not None for s in eq)                     # read from truth/<system>/pools/eval_futures_truth.npz


# ------------------------------------------------------------------------------------------------ H-M4 / H-M5 / H-M6
def test_store_refuses_failed_and_non_finite_records(tmp_path):
    st = TrajectoryStore(tmp_path)
    good = {"t": np.arange(3.0), "x": np.ones((3, 2)), "y": np.ones((3, 1)), "info": {"success": True}}
    st.put("a" * 64, dict(good), {})
    assert "host" in st.get("a" * 64)["info"] and "cpu" in st.get("a" * 64)["info"]["host"]
    with pytest.raises(InvalidRecord):
        st.put("b" * 64, {**good, "info": {"success": False}}, {})
    with pytest.raises(InvalidRecord):
        check_record({**good, "y": np.array([[1.0], [np.nan], [0.0]])})
    assert not st.has("b" * 64)


def test_failed_simulations_are_replaced_from_the_spare_stream():
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    specs = S.plan_system(pubs[sid], ints[sid], tier="toy", seed=S.DEV_SEED, level="B", sets=("public",), policy="public")[:6]
    bad_seed = specs[-1].protocol["params_seed"]
    calls = []

    def run(jobs):
        out = []
        for _, q, _m in jobs:
            calls.append(q["params_seed"])
            if q["params_seed"] == bad_seed:
                out.append({"error": "InvalidRecord: the simulation produced non-finite values in 'y'"})
            else:
                n = round(q["t_end"] / q["dt"]) + 1
                out.append({"key": P.protocol_hash(P.validate(q)), "store_key": "s" * 64, "t": np.arange(n) * q["dt"],
                            "x": np.zeros((n, 5), np.float32), "u": np.zeros((n, 1), np.float32), "y": np.zeros((n, 1), np.float32),
                            "truth": {}, "info": {"success": True}})
        return out
    got = []
    res = S.run_specs(specs, pubs[sid], run, lambda tr, truth: got.append(tr))
    assert res["replaced"] == 1 and res["dropped"] == 0 and sum(res["failures_by_family"].values()) == 1
    rep = [tr for tr in got if (tr.meta.get("replaced") or {}).get("attempt") == 1]
    assert rep and all(tr.protocol["params_seed"] == specs[-1].spares[0] for tr in rep)


def _toy_ctx(tmp_path, j=0):
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = f"syn:toy:{j}"
    syn = S._synthetic_systems("toy", S.DEV_SEED, None)[sid]
    return pubs[sid], S.SimContext(ints[sid], store_root=tmp_path / "store", synthetic_system=syn)


def test_synthetic_restarts_are_checked(tmp_path):
    pub0, c0 = _toy_ctx(tmp_path, 0)
    pub1, c1 = _toy_ctx(tmp_path, 1)
    base = {"system": pub0["system_id"], "params_seed": 0, "t_end": 1.0, "dt": pub0["dt"], "stimulus": [[0.0, 1.0]]}
    r = c0.run(base)
    assert "host" in c0.store.get(r["store_key"])["info"]
    ok = c0.run({**base, "t_end": 0.5, "r0": {"kind": "restart", "key": r["store_key"], "t": 0.5}}, {"no_store": True})
    assert np.array_equal(ok["y"], r["y"][50: 101])                  # a restart continues the stored trajectory exactly
    r32 = c0.run({**base, "t_end": 0.5, "r0": {"kind": "restart", "key": r["store_key"], "t": 0.5}}, {"no_store": True, "restart_round": "float32"})
    assert r32["y"].shape == ok["y"].shape
    with pytest.raises(P.ProtocolError, match="same system"):
        c1.run({**base, "system": pub1["system_id"], "t_end": 0.5, "r0": {"kind": "restart", "key": r["store_key"], "t": 0.5}})
    src = c0.store.get(r["store_key"])
    with pytest.raises(P.ProtocolError, match="sample time"):
        S.restart_index(src, 0.505)


# ------------------------------------------------------------------------------------------------ H-M3 / H minor 9
def test_development_dt_is_the_nominal_dt_and_sampling_items_are_subsampled():
    cap = S.normalize_capability({"timing": {"dt_allowed": [0.01, 0.02, 0.05]}}, t_end=4.0, dt=0.01)
    assert cap["timing"]["dt_allowed"] == [0.01]
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    specs = S.plan_system(pubs[sid], ints[sid], tier="toy", seed=S.DEV_SEED, level="C", sets=("tests",))
    samp = [x for x in specs if x.role == "ood:sampling"]
    assert samp
    for x in samp:
        q = P.validate(x.protocol)
        assert x.meta.get("subsample") == 2 and q["dt"] == pubs[sid]["dt"]
        told = S.told_protocol(q, 2)
        assert told["dt"] == 2 * q["dt"] and told["events"] == q["events"] and told["stimulus"] == q["stimulus"]


def test_obs_scale_enters_noisy_dataset_keys_only():
    q = P.validate({"system": "s", "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]})
    qn = P.validate({**q, "obs_noise": {"sd": 0.1, "seed": 1}})
    assert S.dataset_key(q, "h", "e", {"x": 1.0, "y": 1.0}) == S.dataset_key(q, "h", "e")
    assert S.dataset_key(qn, "h", "e", {"x": 1.0, "y": 1.0}) != S.dataset_key(qn, "h", "e", {"x": 2.0, "y": 1.0})


# ------------------------------------------------------------------------------------------------ state carriers (LOG P4-D31)
def test_carrier_records_are_content_addressed(tmp_path):
    v = np.array([0.5, -1.25, 0.0, 3.0])
    r0, car = S.carrier_r0("h1", 0.25, v)
    assert r0 == {"kind": "restart", "key": car["key"], "t": 0.25} and car["key"] == S.carrier_key("h1", 0.25, v)
    assert S.carrier_key("h2", 0.25, v) != car["key"] and S.carrier_key("h1", 0.5, v) != car["key"]
    S.put_carrier(tmp_path, "sys", "h1", car)
    S.put_carrier(tmp_path, "sys", "h1", car)                      # idempotent
    rec = TrajectoryStore(tmp_path).get(car["key"])
    assert np.array_equal(rec["state"][0], v) and rec["t"].tolist() == [0.25] and rec["info"]["system_hash"] == "h1"
    assert S.restart_index(rec, 0.25) == 0
    with pytest.raises(ValueError):
        S.put_carrier(tmp_path, "sys", "h1", dict(car, state=[9.0, 9.0, 9.0, 9.0]))


def test_a_carrier_restart_equals_the_direct_restart(tmp_path):
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    backend = S.LocalBackend({sid: ints[sid]}, tier="toy", seed=S.DEV_SEED, generator=None, store_root=tmp_path, workers=1)
    try:
        base = {"system": sid, "params_seed": 3, "t_end": 1.0, "dt": float(pubs[sid]["dt"]), "stimulus": [[0.0, 1.0]]}
        src = backend.run([(sid, base, {"role": "src"})])[0]
        rec = TrajectoryStore(tmp_path).get(src["store_key"])
        t = float(rec["t"][40])
        fut = dict(base, t_end=0.5, r0={"kind": "restart", "key": src["store_key"], "t": t},
                   events=[{"kind": "kick", "t": 0.1, "delta": {"1": 0.5}}])
        r0, car = S.carrier_r0(ints[sid]["system_hash"], t, rec["state"][40])
        S.put_carrier(tmp_path, sid, ints[sid]["system_hash"], car)
        a, b = backend.run([(sid, fut, {"role": "f", "no_store": True}), (sid, dict(fut, r0=r0), {"role": "f", "no_store": True})])
    finally:
        backend.close()
    assert np.array_equal(a["x"], b["x"]) and np.array_equal(a["y"], b["y"])


@pytest.mark.slow
def test_eval_pool_sources_and_equivalents_start_from_carriers(tiny_both):
    root, summ = tiny_both
    assert summ["systems"]["syn:toy:0"]["eval"]["errors"] == 0
    dirs = S.tier_dirs("toy", root / "suites")
    rows = [json.loads(x) for x in (dirs["eval"] / "syn_toy_0" / "index.jsonl").read_text(encoding="utf-8").splitlines() if x.strip()]
    gen_src = [r for r in rows if r["split"] == "pool_src" and r["meta"].get("source") == "pool_state"]
    assert gen_src and all("carrier" not in r["meta"] for r in rows)
    store = TrajectoryStore(root / "store")
    for r in gen_src:
        assert r["protocol"]["r0"]["kind"] == "restart" and store.get(r["protocol"]["r0"]["key"])["info"]["carrier"] == S.CARRIER_FORMAT
    pool = json.loads((dirs["eval"] / "syn_toy_0" / "pools" / "pool.json").read_text(encoding="utf-8"))
    assert pool.get("equivalents")
    with np.load(dirs["eval"] / "syn_toy_0" / "pools" / "futures.npz") as z:
        assert any(k.startswith("e") and k.endswith("_none_y") for k in z.files)
