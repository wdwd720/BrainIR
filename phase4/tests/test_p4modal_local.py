"""The Phase 4 Modal backend's local parts (no Modal call): record serialisation in the store format, the volume store's layout and
its compatibility with brainir_causal.store.TrajectoryStore, content-addressed caching of real-engine records, restarts from
provided records, the SimServer remote_backend adapter (with a local stand-in for the Modal call), the gate and the subprocess
entry point. The Modal half is the smoke test `scripts/p4/modal_p4.py smoke-sim` (research/phase4/MODAL_RUNS.md)."""

import json
import pickle
import subprocess
import sys

import numpy as np
import pytest

from brainir_causal.p4modal import gate, remote
from brainir_causal.store import TrajectoryStore
from brainir_causal.systems import NAME_MAP, load_real_internal

needs_systems = pytest.mark.skipif(not NAME_MAP.exists(), reason="real systems not built")


def _mech_sysdef():
    internal = load_real_internal()
    sid = sorted(s for s, d in internal.items() if d["mode"] == "mech")[0]
    return internal[sid]


def _proto(sysdef, **kw):
    a = sysdef["targets_public"][0]
    p = {"system": sysdef["system_id"], "params_seed": 11, "t_end": 0.2, "dt": 0.001, "stimulus": [[0.0, 0.0], [0.02, 1.0]],
         "events": [{"kind": "kick", "t": 0.08, "delta": {str(a): 15.0}}]}
    p.update(kw)
    return p


def test_record_bytes_round_trip_and_store_format(tmp_path):
    rec = {"t": np.linspace(0, 1, 5), "neurons": np.array([1, 4], dtype=np.int32), "rates": np.ones((5, 2), dtype=np.float32),
           "u": np.zeros((5, 1), dtype=np.float32), "info": {"engine": "x", "n": 3}}
    back = remote.record_from_bytes(remote.record_to_bytes(rec))
    assert back["info"] == rec["info"] and all(np.array_equal(back[k], rec[k]) for k in ("t", "neurons", "rates", "u"))
    assert back["rates"].dtype == np.float32
    vs = remote.VolumeStore(tmp_path / "store", "store")
    vs.put("ab" * 32, rec, {"system_id": "s"})
    ts = TrajectoryStore(tmp_path / "store")               # the same layout: TrajectoryStore reads what VolumeStore wrote
    got = ts.get("ab" * 32)
    assert got is not None and got["info"] == rec["info"] and np.array_equal(got["rates"], rec["rates"])
    assert (tmp_path / "store" / "index_shards").exists() and not (tmp_path / "store" / "index.jsonl").exists()
    assert remote.array_digest(rec) == remote.array_digest(got)


@needs_systems
def test_sim_record_matches_engine_and_is_cached(tmp_path, monkeypatch):
    from brainir_causal.realsim import RealEngine, RealSystem
    from brainir_causal.systems import BUNDLE
    monkeypatch.setattr(remote, "BUNDLE", BUNDLE)          # the container path does not exist locally
    monkeypatch.setattr(remote, "_ENGINES", {})
    d = _mech_sysdef()
    q = _proto(d)
    vs = remote.VolumeStore(tmp_path / "vs", "store")
    k1, r1, c1 = remote.sim_record(d, q, vs)
    k2, r2, c2 = remote.sim_record(d, q, vs)
    assert c1 and not c2 and k1 == k2
    ref = RealEngine(BUNDLE, d["network"]).run(RealSystem.from_record(d), q)
    for k in ("t", "neurons", "rates", "u"):
        assert np.array_equal(np.asarray(r1[k]), np.asarray(ref[k])) and np.array_equal(np.asarray(r2[k]), np.asarray(ref[k]))
    ts = TrajectoryStore(tmp_path / "local")
    assert k1 == ts.key(q, d["system_hash"], f"{ref['info']['engine']}|{ref['info']['simulator']}")


@needs_systems
def test_restart_from_a_provided_record(tmp_path, monkeypatch):
    from brainir_causal.systems import BUNDLE
    monkeypatch.setattr(remote, "BUNDLE", BUNDLE)
    monkeypatch.setattr(remote, "_ENGINES", {})
    d = _mech_sysdef()
    k_src, src, _ = remote.sim_record(d, _proto(d), None)
    q = _proto(d, r0={"kind": "restart", "key": k_src, "t": 0.1}, events=[])
    k, rec, computed = remote.sim_record(d, q, None, provided={k_src: remote.record_to_bytes(src)})
    assert computed
    i = int(round(0.1 / 0.001))
    pos = {int(n): j for j, n in enumerate(src["neurons"])}
    first = {int(n): float(rec["rates"][0, j]) for j, n in enumerate(rec["neurons"])}
    for n, j in pos.items():
        assert abs(first.get(n, 0.0) - float(src["rates"][i, j])) < 1e-6


@needs_systems
def test_remote_backend_adapter_with_a_local_stand_in(tmp_path, monkeypatch):
    """Backend.remote_backend() with Backend.simulate replaced by local sim_record: the SimServer contract (finish_remote_job) holds
    and the observed arrays equal those of the service's local path (simservice.run_job)."""
    from brainir_causal import protocol as P
    from brainir_causal.p4modal import app as A
    from brainir_causal.simservice import run_job
    from brainir_causal.p4modal import gate as G
    from brainir_causal.systems import BUNDLE
    monkeypatch.setattr(remote, "BUNDLE", BUNDLE)
    monkeypatch.setattr(remote, "_ENGINES", {})
    monkeypatch.setattr(G, "reference_platform_problems", lambda fp=None: [])   # the adapter's contract here; the gate: its own test
    d = _mech_sysdef()
    q = P.validate(_proto(d))
    be = A.Backend.__new__(A.Backend)

    def fake_simulate(items, **kw):
        out = []
        for it in items:
            k, rec, c = remote.sim_record(it["sysdef"], it["protocol"], None, provided=it.get("restart_src"))
            out.append({"key": k, "computed": c, "record": remote.record_to_bytes(rec), "sha": remote.array_digest(rec)})
        return out

    monkeypatch.setattr(be, "simulate", fake_simulate, raising=False)
    backend = A.Backend.remote_backend(be)
    job = {"sysdef": d, "protocol": q, "store_root": str(tmp_path / "svc_store"), "bundle": str(BUNDLE)}
    out = backend([job])[0]
    assert not isinstance(out, Exception), out
    loc = run_job({**job, "store_root": str(tmp_path / "loc_store")})
    for k in ("t", "x", "u", "y"):
        assert np.array_equal(out[k], loc[k])
    assert out["store_key"] == loc["store_key"] and TrajectoryStore(tmp_path / "svc_store").has(out["store_key"])


def test_gate_rule_is_the_phase3_rule():
    avx2_only = "vendor_id : AuthenticAMD\nmodel name : EPYC\nflags : sse avx avx2 fma\n"
    avx512 = "vendor_id : GenuineIntel\nmodel name : Xeon\nflags : sse avx avx2 fma avx512f\n"
    old = "vendor_id : GenuineIntel\nmodel name : Old\nflags : sse avx\n"
    assert gate.admissible(gate.host_cpu(avx2_only))
    assert not gate.admissible(gate.host_cpu(avx512))
    assert not gate.admissible(gate.host_cpu(old))
    assert gate.is_refusal({gate.REFUSED: True}) and not gate.is_refusal({"x": 1})


def test_jobproc_runs_a_target_in_a_fresh_interpreter(tmp_path):
    job = {"target": "json:dumps", "args": [{"a": [1, 2]}], "kwargs": {"sort_keys": True}, "threads": 1}
    (tmp_path / "job.json").write_text(json.dumps(job), encoding="utf-8")
    pr = subprocess.run([sys.executable, "-m", "brainir_causal.p4modal.jobproc", str(tmp_path / "job.json"), str(tmp_path / "r.pkl")],
                        capture_output=True, text=True, timeout=120)
    assert pr.returncode == 0, pr.stderr
    assert pickle.loads((tmp_path / "r.pkl").read_bytes()) == {"result": '{"a": [1, 2]}'}


def test_subst_and_worker_classes():
    assert remote._subst({"a": ["$JOB/x", 3], "b": "$METHODS"}, {"$JOB": "/j", "$METHODS": "/m"}) == {"a": ["/j/x", 3], "b": "/m"}
    from brainir_causal.p4modal import app as A
    for name, c in A.CLASSES.items():
        assert c["volumes"] and all(v in A.VOLUMES for v in c["volumes"])
        if name.startswith(("fit", "gpu")):
            assert "eval" not in c["volumes"], f"{name}: fit / GPU classes must never mount the eval volume"
        assert (c["gpu"] is None) or not c["gated"]
    assert all(not v.startswith("brainir-p3") for v in A.VOLUMES.values())
