"""Compute layer: shared-payload resolution, local backend equivalence, experiment records."""

from __future__ import annotations

import json

import numpy as np

from brainir.compute import ExperimentRecord, LocalBackend, Shared, content_hash, register_run, resolve_shared
from brainir.compute.backend import pack_shared, unpack_shared


def _dot(args):
    W, v, k = args
    return float(W[k] @ v)


def test_resolve_shared_nested():
    shared = {"W": np.eye(3), "v": [1, 2, 3]}
    item = (Shared("W"), {"x": [Shared("v"), 5]}, 7)
    out = resolve_shared(item, shared)
    assert out[2] == 7 and out[1]["x"][1] == 5
    assert np.array_equal(out[0], np.eye(3)) and out[1]["x"][0] == [1, 2, 3]


def test_pack_unpack_roundtrip_is_content_addressed():
    shared = {"W": np.arange(12, dtype=np.float32).reshape(3, 4), "mask": np.array([True, False, True])}
    blob, key = pack_shared(shared)
    blob2, key2 = pack_shared(shared)
    assert key == key2 and len(key) == 32
    back = unpack_shared(blob2)
    assert np.array_equal(back["W"], shared["W"]) and np.array_equal(back["mask"], shared["mask"])


def test_local_backend_serial_and_pool_agree_with_shared():
    rng = np.random.default_rng(0)
    W = rng.normal(size=(6, 6))
    v = rng.normal(size=6)
    items = [(Shared("W"), Shared("v"), k) for k in range(6)]
    serial = LocalBackend(1).map(_dot, items, shared={"W": W, "v": v})
    pool = LocalBackend(2).map(_dot, items, shared={"W": W, "v": v})
    assert serial == pool == [float(W[k] @ v) for k in range(6)]


def test_experiment_record_registry(tmp_path):
    rec = ExperimentRecord(name="t", config={"a": 1}, seeds=[0, 1], inputs={"h": content_hash({"x": 1})}, backend={"backend": "local", "wall_time_s": 1.0})
    p = register_run(rec, tmp_path)
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["run_id"] == rec.run_id and len(rec.run_id) == 16 and d["code"]["brainir_version"]
    idx = (tmp_path / "index.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(idx) == 1 and json.loads(idx[0])["run_id"] == rec.run_id
    # same name/config/seeds/inputs -> same run_id (content-addressed)
    assert ExperimentRecord(name="t", config={"a": 1}, seeds=[0, 1], inputs=rec.inputs).finalize().run_id == rec.run_id
