"""The SAFE worker->driver codec (brainir_causal.worker.encode_safe / decode_safe): round-trips of the values a model call returns,
and the refusals that stop a malicious worker from reaching the driver's unpickler (research/phase4/EVAL_ARCHITECTURE.md; review F,
F-B3). The driver decodes worker output with json + np.load(allow_pickle=False) only, so a worker can never execute code in the driver.
"""

from __future__ import annotations

import io
import struct
import zipfile

import numpy as np
import pytest

from brainir_causal import worker as W


def rt(obj):
    return W.decode_safe(W.encode_safe(obj))


def test_scalars_and_containers_round_trip():
    for v in (None, True, False, 0, -5, 3.5, "hi", float("nan"), float("inf"), 2 ** 70):
        r = rt(v)
        if isinstance(v, float) and v != v:
            assert r != r
        else:
            assert r == v


def test_nested_structures_and_numpy():
    obj = {"a": [1, 2, {"z": np.arange(6.0).reshape(2, 3)}], "b": {"c": np.array([1, 2, 3], np.int64)}, "t": (1, "x", None),
           "s": {3, 1, 2}, "y_sd": np.float32(0.5)}
    r = rt(obj)
    assert r["a"][0] == 1 and r["a"][2]["z"].shape == (2, 3)
    assert np.allclose(r["a"][2]["z"], np.arange(6.0).reshape(2, 3))
    assert r["b"]["c"].dtype.kind in "iu" and list(r["b"]["c"]) == [1, 2, 3]
    assert r["t"] == [1, "x", None] and sorted(r["s"]) == [1, 2, 3]


def test_rollout_like_dict_and_bytes():
    out = {"z": np.zeros((5, 2)), "y": np.ones((5, 3)), "y_sd": np.full((5, 3), 0.1), "blob": b"\x00\x01model"}
    r = rt(out)
    assert r["z"].shape == (5, 2) and np.allclose(r["y"], 1.0) and r["blob"] == b"\x00\x01model"


def test_object_arrays_and_unknown_objects_are_not_smuggled():
    # an object-dtype array is the pickle vector: encoding it is REFUSED (never encoded, never round-tripped as an object)
    with pytest.raises(TypeError):
        W.encode_safe({"bad": np.array([object()], dtype=object)})

    class C:
        pass
    assert "__repr__" in rt(C())          # an ordinary unknown object degrades to its repr, never to a live object


def test_pydantic_and_dataclass_models():
    from dataclasses import dataclass
    from brainir_causal.api import LatentDimension

    @dataclass
    class D:
        a: int
        b: np.ndarray
    r = rt(D(3, np.array([1.0, 2.0])))
    assert r["a"] == 3 and np.allclose(r["b"], [1.0, 2.0])
    ld = rt(LatentDimension(selected=2, rule="x"))
    assert ld["selected"] == 2 and ld["rule"] == "x"


def test_decode_refuses_non_magic_and_truncation():
    with pytest.raises(ValueError):
        W.decode_safe(b"nope")
    with pytest.raises(ValueError):
        W.decode_safe(W.MAGIC + struct.pack(">Q", 10) + b"{}")


def test_decode_refuses_compressed_members():
    # a hand-built reply whose npz uses DEFLATE (a decompression-bomb vector) must be refused
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("a0.npy", b"\x00" * 4096)
    head = b'{"__nd__":0}'
    blob = W.MAGIC + struct.pack(">Q", len(head)) + head + buf.getvalue()
    with pytest.raises(ValueError):
        W.decode_safe(blob)


def test_decode_refuses_oversized_arrays():
    big = {"a": np.zeros(1000, np.float64)}
    blob = W.encode_safe(big)
    with pytest.raises(ValueError):
        W.decode_safe(blob, max_array_bytes=16)


def test_decode_refuses_object_array_member():
    # even a STORED npz member of object dtype must not be unpickled by the driver
    buf = io.BytesIO()
    np.save(_tmp := io.BytesIO(), np.array([1, 2, 3]))
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        obj = io.BytesIO()
        np.save(obj, np.array([object()], dtype=object), allow_pickle=True)
        zf.writestr("a0.npy", obj.getvalue())
    head = b'{"__nd__":0}'
    blob = W.MAGIC + struct.pack(">Q", len(head)) + head + buf.getvalue()
    with pytest.raises(ValueError):
        W.decode_safe(blob)


def test_deep_nesting_is_refused():
    obj = cur = {}
    for _ in range(W.MAX_DEPTH + 5):
        cur["x"] = {}
        cur = cur["x"]
    with pytest.raises(ValueError):
        W.encode_safe(obj)


def test_frames_round_trip_over_a_pipe():
    b = io.BytesIO()
    W.write_frame(b, b"abc")
    W.write_frame(b, b"")
    b.seek(0)
    assert W.read_frame(b) == b"abc"
    assert W.read_frame(b) == b""
    assert W.read_frame(b) is None
