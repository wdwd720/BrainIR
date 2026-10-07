"""Dataset design v2 (LOG P4-D36; round-2 reviews T B2 / B3 / M1 / M4, H N1 / N5 / N6): no explicit initial states in any
development / public-policy protocol, 'obs.init' as a restart from a same-draw nominal passive trajectory, no per-unit capability
field in public records, the onset / twin check, realized kick classes, the synthetic host gate, carrier-started OOD initial
conditions."""

from __future__ import annotations

import copy
import hashlib
import json

import numpy as np
import pytest

from brainir_causal import protocol as P
from brainir_causal import suites as S
from brainir_causal import systems as SY
from brainir_causal.synthadapter import TOY_CAPABILITY


def toy():
    pubs, ints, _ = S.synthetic_tier_records("toy", S.DEV_SEED)
    sid = min(pubs)
    return sid, pubs[sid], ints[sid], S._synthetic_systems("toy", S.DEV_SEED, None)[sid]


GEN_LIKE = {
    **copy.deepcopy(TOY_CAPABILITY),
    "init": {"state": True, "restart": True, "units": list(range(10)), "max_value": 140.0, "min_value": -140.0},
    "admissible_range": {"lo": [-50.0] * 4 + [-120.0] * 6, "hi": [50.0] * 4 + [120.0] * 6},
    "process_noise": {"supported": True, "unit_sd_per_sqrt_s": [0.4] * 4 + [0.9] * 6,
                      "units": "sd * unit_sd_per_sqrt_s[i] * sqrt(h) * xi"},
}


# ------------------------------------------------------------------------------------------------ capability (review T, B3 / M1)
def test_capability_refuses_explicit_states_and_carries_no_per_unit_field():
    c = S.normalize_capability(GEN_LIKE, t_end=2.0, dt=0.01)
    assert c["init"]["state"] is False and c["init"]["restart"] is True and c["init"]["units"] == "observed"
    assert c["admissible_range"] == {"lo": -120.0, "hi": 120.0}
    assert "unit_sd_per_sqrt_s" not in c["process_noise"] and c["process_noise"]["sd_per_sqrt_s"] == pytest.approx(0.9)
    assert S.per_unit_lists(c) == []
    # role cannot be predicted from public fields: permuting which units carry which role leaves the public capability unchanged
    perm = json.loads(json.dumps(GEN_LIKE))
    order = [9, 3, 7, 0, 5, 1, 8, 2, 6, 4]
    perm["admissible_range"] = {k: [GEN_LIKE["admissible_range"][k][i] for i in order] for k in ("lo", "hi")}
    perm["process_noise"]["unit_sd_per_sqrt_s"] = [GEN_LIKE["process_noise"]["unit_sd_per_sqrt_s"][i] for i in order]
    assert S.normalize_capability(perm, t_end=2.0, dt=0.01) == c


def test_public_record_check_refuses_per_unit_capability_fields():
    _, pub, _, _ = toy()
    S.assert_public_record(pub)
    bad = json.loads(json.dumps(pub))
    bad["capability"]["admissible_range"] = {"lo": [0.0, 1.0, 2.0], "hi": [3.0, 4.0, 5.0]}
    with pytest.raises(AssertionError, match="per-unit"):
        S.assert_public_record(bad)


def test_no_explicit_initial_state_is_a_development_protocol():
    from brainir_causal.simservice import check_public
    sid, pub, _, _ = toy()
    assert pub["capability"]["init"]["state"] is False
    q = P.validate({"system": sid, "params_seed": 0, "t_end": 1.0, "dt": float(pub["dt"]), "stimulus": [[0.0, 1.0]],
                    "r0": {"kind": "state", "values": {str(pub["observed"][0]): 1.0}}})
    assert "initial states" in (check_public(q, pub) or "")
    assert SY.REAL_CAPABILITY["init"]["state"] is False
    if SY.INTERNAL_REAL.exists():
        rec = SY.load_real_public()["real:A:m1"]
        qr = P.validate({"system": "real:A:m1", "params_seed": 1, "t_end": 1.0, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.05, 1.0]],
                         "r0": {"kind": "state", "values": {str(rec["observed"][0]): 5.0}}})
        assert "initial states" in (check_public(qr, rec) or "")


# ------------------------------------------------------------------------------------------------ obs.init (review T, B2)
def test_obs_init_restarts_from_a_same_draw_nominal_source():
    sid, pub, _, _ = toy()
    s = S.FamilySampler(pub, np.random.default_rng(3), S.seed_counter(False, "t"), targets=pub["targets_public"])
    specs = S.design_passive(s, S.D0_DESIGN, "train", "d0", seed_parts=("d0", "toy", S.DEV_SEED, sid))
    src = {sp.meta["src_id"]: sp for sp in specs if sp.meta.get("src_id")}
    inits = [sp for sp in specs if sp.family == "obs.init"]
    assert len(inits) == S.D0_DESIGN["obs.init"] and len(src) == S.D0_DESIGN["obs.nominal"]
    for sp in inits:
        dep = sp.meta["restart_from"]
        assert dep["src"] in src and S.INIT_T_FRAC[0] <= dep["t_frac"] <= S.INIT_T_FRAC[1]
        assert sp.protocol["r0"] == {"kind": "rest"} and not sp.spares
        source = src[dep["src"]].protocol
        done = S.resolve_restart(sp, "ab" * 32, source)
        q = P.validate(done.protocol)
        assert q["r0"]["kind"] == "restart" and q["r0"]["key"] == "ab" * 32
        assert q["params_seed"] == source["params_seed"] and q["weight_noise"] == source["weight_noise"]
        i = round(q["r0"]["t"] / float(pub["dt"]))
        assert abs(i * float(pub["dt"]) - q["r0"]["t"]) < 1e-9 and 0 < q["r0"]["t"] < float(source["t_end"])
        assert S.F.family_of(q, pub) == "obs.init"
    with pytest.raises(ValueError, match="restart"):
        s.obs("obs.init")


def _fake_run(fail_keys=()):
    """A stand-in simulator: deterministic arrays from the protocol; protocols whose params_seed is in fail_keys fail."""
    seen = []

    def run(jobs):
        out = []
        for sid, proto, meta in jobs:
            q = P.validate(proto)
            seen.append(q)
            if int(q["params_seed"]) in fail_keys:
                out.append({"error": "boom"})
                continue
            h = hashlib.sha256(json.dumps(q, sort_keys=True).encode()).hexdigest()
            n = round(q["t_end"] / q["dt"]) + 1
            base = np.linspace(0.0, 1.0, n)[:, None] * (1 + int(q["params_seed"]) % 5)
            x = np.repeat(base, 3, axis=1)
            for e in q["events"]:
                i = round(P.event_start(e) / q["dt"])
                x[i + 1:] += 1.0                                  # the effect starts AFTER the onset sample
            out.append({"key": h[:32], "store_key": h[32:], "t": np.arange(n) * q["dt"], "x": x.astype(np.float32),
                        "u": np.zeros((n, 1), np.float32), "y": x[:, :1].astype(np.float32), "truth": {}, "info": {}})
        return out
    return run, seen


def test_dependent_trajectories_follow_their_sources_and_drop_with_them():
    _, pub, _, _ = toy()
    s = S.FamilySampler(pub, np.random.default_rng(5), S.seed_counter(False, "u"), targets=pub["targets_public"])
    specs = S.design_passive(s, {"obs.nominal": 2, "obs.init": 2}, "train", "d0", seed_parts=("x",))
    rows = []
    run, _ = _fake_run()
    res = S.run_specs(specs, pub, run, lambda tr, truth: rows.append(tr))
    assert res["ok"] == 4 and res["dropped"] == 0
    by_store = {r.meta["store_key"]: r for r in rows}
    inits = [r for r in rows if r.family == "obs.init"]
    assert len(inits) == 2 and all(by_store[r.protocol["r0"]["key"]].family in ("obs.nominal", "obs.param") for r in inits)
    assert all(k not in r.meta for r in rows for k in S.PLAN_ONLY_META)
    # a failed source drops its dependents (no spares for dependents)
    bad_seed = specs[0].protocol["params_seed"]
    for sp in specs:
        sp.spares = [] if sp.meta.get("restart_from") else sp.spares
    run2, _ = _fake_run(fail_keys={bad_seed} | set(specs[0].spares))
    rows2 = []
    res2 = S.run_specs(specs, pub, run2, lambda tr, truth: rows2.append(tr))
    assert res2["dropped"] >= 2 and not any(r.protocol["r0"]["kind"] == "restart" and r.protocol["params_seed"] == bad_seed for r in rows2)


# ------------------------------------------------------------------------------------------------ onset / twin (review H, N1)
def test_an_intervention_visible_at_its_onset_sample_aborts_the_build():
    _, pub, _, _ = toy()
    s = S.FamilySampler(pub, np.random.default_rng(7), S.seed_counter(False, "v"), targets=pub["targets_public"])
    p, info = s.make("kick.1", mclass="moderate", onset=0.4)
    item = {"x": np.zeros((101, 2)), "y": np.zeros((101, 1))}
    twin = {"x": np.zeros((101, 2)), "y": np.zeros((101, 1))}
    item["x"][41:] = 1.0
    assert S.onset_mismatch(p, None, item, twin) is None
    item["x"][40] = 0.5                                           # visible AT the onset sample
    assert "sample 40" in S.onset_mismatch(p, None, item, twin)
    spec = S._spec(p, info, "test", "in", twin=True)

    def leaky(jobs):
        run, _ = _fake_run()
        out = run(jobs)
        for (sid_, proto, meta), r in zip(jobs, out):
            if P.validate(proto)["events"]:
                r["y"] = r["y"].copy()
                r["y"][round(0.4 / float(pub["dt"]))] += 1.0
        return out
    with pytest.raises(RuntimeError, match="pre-event state"):
        S.run_specs([spec], pub, leaky, lambda tr, truth: None)


# ------------------------------------------------------------------------------------------------ realized kick classes (review H, N5)
def test_realized_kick_class_rules():
    cap = S.normalize_capability(copy.deepcopy(SY.REAL_CAPABILITY), t_end=2.0, dt=0.001)
    m = float(cap["kick"]["moderate"])
    spec = S.Spec(protocol={}, split="test", role="in", family="kick.1", mclass="strong")
    proto = {"system": "x", "params_seed": 0, "t_end": 1.0, "dt": 0.001, "events": [{"kind": "kick", "t": 0.3, "delta": {"7": 3.0 * m}}]}
    same = {"kicks_applied": [{"t": 0.3, "requested": {"7": 3.0 * m}, "applied": {"7": 3.0 * m}}]}
    assert S.realized_kick_class(spec, proto, same, cap)["mclass"] == "strong"
    weak = {"kicks_applied": [{"t": 0.3, "requested": {"7": 3.0 * m}, "applied": {"7": 0.3 * m}}]}
    r = S.realized_kick_class(spec, proto, weak, cap)
    assert r["mclass"] == "weak" and r["clipped"] == 1 and r["median_ratio"] == pytest.approx(0.1)
    zero = {"kicks_applied": [{"t": 0.3, "requested": {"7": -3.0 * m}, "applied": {"7": 0.0}}]}
    assert S.realized_kick_class(spec, dict(proto, events=[{"kind": "kick", "t": 0.3, "delta": {"7": -3.0 * m}}]), zero, cap)["mclass"] == "below"
    hi_spec = S.Spec(protocol={}, split="test", role="near", family="kick.hi", mclass="hi")
    hi_p = dict(proto, events=[{"kind": "kick", "t": 0.3, "delta": {"7": 140.0}}])
    hi_i = {"kicks_applied": [{"t": 0.3, "requested": {"7": 140.0}, "applied": {"7": 100.0}}]}
    assert S.realized_kick_class(hi_spec, hi_p, hi_i, cap)["mclass"] == "hi"
    unk = S.realized_kick_class(spec, proto, {"clipped_kicks": [[7, 300]]}, cap)
    assert unk["unknown"] and unk["mclass"] == "strong"
    assert S.realized_kick_class(spec, proto, {}, cap) is None
    na = S.Spec(protocol={}, split="test", role="in", family="sil.1", mclass="na")
    assert S.realized_kick_class(na, proto, same, cap) is None


def test_realized_kick_class_reads_the_generators_format():
    """Review H round 3c, NEW-7: the synthetic generator reports kicks_applied as {"t", "event_index", "units": {unit: realized},
    "requested": {...}} with int (or str) unit keys; a clipped kick is relabelled, and an entry without a realized size for a kicked
    unit is flagged unknown instead of being read as unclipped."""
    cap = S.normalize_capability(copy.deepcopy(SY.REAL_CAPABILITY), t_end=2.0, dt=0.001)
    m = float(cap["kick"]["moderate"])
    spec = S.Spec(protocol={}, split="test", role="in", family="kick.1", mclass="strong")
    proto = {"system": "x", "params_seed": 0, "t_end": 1.0, "dt": 0.001, "events": [{"kind": "kick", "t": 0.3, "delta": {"7": -3.0 * m}}]}
    for key in (7, "7"):
        gen = {"kicks_applied": [{"t": 0.3, "event_index": 0, "units": {key: -0.3 * m}, "requested": {key: -3.0 * m}}]}
        r = S.realized_kick_class(spec, proto, gen, cap)
        assert r["clipped"] == 1 and r["mclass"] == "weak", key
        full = {"kicks_applied": [{"t": 0.3, "event_index": 0, "units": {key: -3.0 * m}, "requested": {key: -3.0 * m}}]}
        assert S.realized_kick_class(spec, proto, full, cap)["mclass"] == "strong"
    other_unit = {"kicks_applied": [{"t": 0.3, "event_index": 0, "units": {8: -0.3 * m}, "requested": {8: -3.0 * m}}]}
    r = S.realized_kick_class(spec, proto, other_unit, cap)
    assert r["unknown"] and r["mclass"] == "strong"
    other_time = {"kicks_applied": [{"t": 0.4, "event_index": 0, "units": {7: -0.3 * m}}]}
    assert S.realized_kick_class(spec, proto, other_time, cap)["unknown"]
    # two kick events at one time (two entries): each unit is found in its own entry
    two = dict(proto, events=[{"kind": "kick", "t": 0.3, "delta": {"7": -3.0 * m}}, {"kind": "kick", "t": 0.3, "delta": {"9": -3.0 * m}}])
    sp2 = S.Spec(protocol={}, split="test", role="in", family="kick.2", mclass="strong")
    ents = {"kicks_applied": [{"t": 0.3, "event_index": 0, "units": {7: -3.0 * m}}, {"t": 0.3, "event_index": 1, "units": {9: -3.0 * m}}]}
    r2 = S.realized_kick_class(sp2, two, ents, cap)
    assert not r2.get("unknown") and r2["clipped"] == 0 and r2["mclass"] == "strong" and r2["n"] == 2


def test_synthetic_rows_never_carry_realized_kicks():
    info = {"kicks_applied": [{"t": 0.1, "requested": {"1": 1.0}, "applied": {"1": 0.5}}], "n_calls": 2, "success": True}
    assert "kicks_applied" not in S.dataset_info(info, "synthetic")
    assert "kicks_applied" in S.dataset_info(info, "real")


# ------------------------------------------------------------------------------------------------ host gate (review H, N6)
def test_synthetic_simulation_is_host_gated(tmp_path, monkeypatch):
    from brainir_causal.p4modal import gate
    sid, pub, internal, sysobj = toy()
    ctx = S.SimContext(internal, store_root=tmp_path, synthetic_system=sysobj)
    q = {"system": sid, "params_seed": 1, "t_end": 0.5, "dt": float(pub["dt"]), "stimulus": [[0.0, 1.0]]}
    assert ctx.run(q)["x"].shape[0] == 51
    monkeypatch.setattr(gate, "this_host", lambda: {"avx512f": True, "avx2": True, "model": "x", "vendor": "x"})
    with pytest.raises(RuntimeError, match="gated hosts"):
        ctx.run(dict(q, params_seed=2))


def test_host_summary_counts_admissible_fingerprints(tmp_path):
    ok = {"admissible": True, "cpu": {"avx2": True, "avx512f": False, "vendor": "V", "model": "m"}, "machine": "x86_64", "os": "Linux"}
    bad = {**ok, "cpu": {**ok["cpu"], "avx512f": True}}
    rows = [{"key": "a", "info": {"host": ok}}, {"key": "b", "info": {"host": bad}}, {"key": "c", "info": {}}]
    (tmp_path / "index.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    h = S.host_summary(str(tmp_path))
    assert (h["rows"], h["with_host"], h["admissible"]) == (3, 2, 1) and set(h["not_admissible_or_missing"]) == {"b", "c"}
    assert h["hosts"] == {"V|m|x86_64|Linux": 2}
    assert S.host_summary(str(tmp_path / "none")) == {"_missing": True}


# ------------------------------------------------------------------------------------------------ OOD initial conditions (carriers)
def test_ood_initial_conditions_start_from_displaced_carriers(tmp_path, monkeypatch):
    from brainir_causal.store import TrajectoryStore
    sid, pub, internal, sysobj = toy()
    monkeypatch.setattr(S, "ITEMS_PER_CATEGORY", 2)
    s = S.FamilySampler(pub, np.random.default_rng(9), S.seed_counter(False, "w"), targets=pub["targets_public"])
    ood = S.design_ood(s, pub, [list(e) for e in pub.get("edges_public") or []], S.seed_counter(False, "w2"))
    specs = [sp for sp in ood if sp.role in ("ood_src", "ood:initial_condition")]
    assert len(specs) == 4 and all(sp.meta.get("carrier_from") for sp in specs if sp.role == "ood:initial_condition")
    backend = S.LocalBackend({sid: internal}, tier="toy", seed=S.DEV_SEED, generator=None, store_root=tmp_path, workers=1)
    rows = []
    try:
        res = S.run_specs(specs, pub, backend.run, lambda tr, truth: rows.append(tr),
                          resolver=lambda sp, k, q: S.resolve_carrier_start(sp, k, q, pub=pub, internal=internal, store_root=tmp_path,
                                                                            truth_system=sysobj))
    finally:
        backend.close()
    assert res["dropped"] == 0
    store = TrajectoryStore(tmp_path)
    items = [r for r in rows if r.meta["role"] == "ood:initial_condition" and r.split == "test"]
    assert len(items) == 2
    for it in items:
        car = store.get(it.protocol["r0"]["key"])
        assert car["info"]["carrier"] == S.CARRIER_FORMAT
        twin = next(r for r in rows if r.meta.get("twin_of") == it.key)
        assert twin.protocol["r0"] == it.protocol["r0"]
        assert not any(r.protocol["r0"]["kind"] == "state" for r in rows)


def test_real_carrier_is_the_engine_restart_format(tmp_path):
    from brainir_causal.store import TrajectoryStore
    k1 = S.put_real_carrier(tmp_path, "real:X:m1", "h", 0.25, [3, 7], [1.5, 20.0])
    k2 = S.put_real_carrier(tmp_path, "real:X:m1", "h", 0.25, [3, 7], [1.5, 20.0])
    assert k1 == k2 and k1 != S.put_real_carrier(tmp_path, "real:X:m1", "h", 0.25, [3, 7], [1.5, 21.0])
    rec = TrajectoryStore(tmp_path).get(k1)
    assert rec["neurons"].tolist() == [3, 7] and rec["rates"].shape == (1, 2) and rec["rates"].dtype == np.float32
    assert rec["t"].tolist() == [0.25] and rec["info"]["system_id"] == "real:X:m1"


@pytest.mark.skipif(not SY.INTERNAL_REAL.exists(), reason="real systems not built")
def test_a_real_restart_from_a_carrier_starts_at_its_rates(tmp_path):
    from brainir_causal.realsim import RealEngine
    from brainir_causal.store import TrajectoryStore
    internal = SY.load_real_internal()["real:A:m1"]
    eng = RealEngine(SY.BUNDLE, internal["network"])
    sysobj = SY.real_system(internal)
    u = int(internal["observed"][0])
    key = S.put_real_carrier(tmp_path, "real:A:m1", internal["system_hash"], 0.0, [u], [12.5])
    rec = eng.run(sysobj, {"system": "real:A:m1", "params_seed": 1, "t_end": 0.02, "dt": 0.001, "stimulus": [[0.0, 0.0]],
                           "r0": {"kind": "restart", "key": key, "t": 0.0}}, store=TrajectoryStore(tmp_path))
    j = list(rec["neurons"]).index(u)
    assert float(rec["rates"][0, j]) == pytest.approx(12.5)
