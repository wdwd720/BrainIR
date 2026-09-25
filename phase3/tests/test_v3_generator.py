"""Benchmark version 3: the hidden real data generator's backend-independent pieces (scripts/p3/generate_real_hidden.py).

The Modal path itself is checked end to end on PUBLIC protocols by `generate_real_hidden.py smoke-public` (record:
research/phase3/level_c/hidden_generator_modal_smoke.json, 30 of 30 trajectories bit-identical to the stored public records)."""

from __future__ import annotations

import hashlib
import sys
import tarfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
import generate_real_hidden as G  # noqa: E402


def _rec(T=2001, n=5, seed=0):
    rng = np.random.default_rng(seed)
    return {"t": np.round(np.arange(T) * 0.001, 9), "neurons": np.arange(n, dtype=np.int32),
            "rates": rng.random((T, n)).astype(np.float32), "u": np.ones((T, 1), np.float32), "info": {}}


def test_micro_states_are_deterministic_in_the_key():
    rec = _rec()
    m = {"system_id": "real:x:full", "group": 3, "params_seed": 10**9 + 7}
    a = G.micro_states("abcdef0123456789", rec, m, {"system_id": "real:x:full"})
    b = G.micro_states("abcdef0123456789", rec, m, {"system_id": "real:x:full"})
    c = G.micro_states("0123456789abcdef", rec, m, {"system_id": "real:x:full"})
    assert len(a) == G.MICRO_STATES_PER_TRAJ
    assert [mm["index"] for _, mm in a] == [mm["index"] for _, mm in b] != [mm["index"] for _, mm in c]
    assert all(300 <= mm["index"] < len(rec["t"]) - 1 and mm["group"] == 3 for _, mm in a)
    idx = sorted(mm["index"] for _, mm in a)
    assert [mm["index"] for _, mm in a] == idx                                  # sorted, like the local path


def test_row_info_records_applied_kicks_only_for_kick_trajectories():
    rec = _rec()
    rec["info"] = {"kicks_applied": [{"t": 0.5, "requested": {"1": -20.0}, "applied": {"1": -0.3}}]}
    kick = {"events": [{"kind": "kick", "t": 0.5, "delta": {"1": -20.0}}]}
    info = G.row_info({"system_id": "s", "family": "H_kick_B", "role": "test", "pair": "H_kick_B:0"}, rec, kick)
    assert info["pair"] == "H_kick_B:0" and info["kicks_applied"][0]["applied"]["1"] == -0.3
    assert "kicks_applied" not in G.row_info({"pair": "p"}, rec, {"events": []})


def test_write_all_and_tar_round_trip(tmp_path):
    items = [({"key": f"k{i}", "system_id": "real:x:full", "split": "test", "family": "H_nominal", "protocol": {}, "info": {}},
              {"t": np.arange(3.0), "x": np.ones((3, 2)), "u": np.zeros((3, 1)), "y": np.ones((3, 1))}) for i in range(3)]
    fut = [(np.ones((4, 1)), np.ones((4, 1)) * 2)]
    out = tmp_path / "hidden"
    hashes = G.write_all(out, {"dataset_id": "t", "systems": {}}, items, fut, [{"key": "k0", "index": 1}])
    assert set(hashes) == {"index.jsonl", "manifest.json", "micro_index.json"} and len(list((out / "traj").glob("*.npz"))) == 3
    rep = G.remote_tar(str(out).replace("\\", "/"), str(tmp_path / "d.tar"))
    assert rep["bytes"] > 0 and rep["sha256"] == hashlib.sha256((tmp_path / "d.tar").read_bytes()).hexdigest()
    with tarfile.open(tmp_path / "d.tar") as tf:
        names = tf.getnames()
    assert "hidden/index.jsonl" in names and "hidden/micro_futures.npz" in names


def test_remote_paths_are_posix():
    assert G.REMOTE_STORE.startswith("/evalvol/") and G.REMOTE_DATASET == "/evalvol/suites/real/hidden"
    assert "\\" not in G.posixpath.dirname(G.REMOTE_STORE)
