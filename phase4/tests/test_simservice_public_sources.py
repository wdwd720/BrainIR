"""Public restart sources of the simulation service and its reference-platform worker pool (LOG P4-D32 / P4-D33): the public-keys
table built from dataset rows, on-demand recomputation of a public source missing from the service store (key verified, recursive,
not charged), refusal of a source that does not reproduce, and the Docker pool answering `run_job` like the image itself."""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
import pytest

from brainir_causal import families as F
from brainir_causal import protocol as P
from brainir_causal import suites as SU
from brainir_causal.simservice import PUBLIC_KEYS_FORMAT, SimServer, build_public_keys, expand_public_keys, run_job
from brainir_causal.synthadapter import ToySystem

SID = "syn:toy:0"


def toy_sysdef(seed=3, j=0):
    rec = ToySystem(seed, j).public_record()
    rec.update({"tier": "toy", "suite_seed": seed, "targets_public": [0, 1, 2], "edges_public": [[0, 1], [1, 0]],
                "split": F.rotation_split("R4", rec["capability"])})
    return rec


def base(**kw):
    p = {"system": SID, "params_seed": 0, "t_end": 1.0, "dt": 0.01, "stimulus": [[0.0, 1.0]]}
    p.update(kw)
    return p


#: the observed arrays of every simulated public row (trajectory key -> t / x / u / y): `_table` publishes them like a dataset
_ARRAYS: dict[str, dict] = {}
_PUBDIR = Path(tempfile.mkdtemp(prefix="p4pubsrc_"))


def _simulate(store, sysrec, proto):
    q = P.validate(proto)
    out = run_job({"sysdef": sysrec, "protocol": q, "store_root": str(store), "bundle": None})
    tk = SU.dataset_key(q, "toy-public", "toy-engine", sysrec.get("obs_scale"))
    _ARRAYS[tk] = {k: np.asarray(out[k]) for k in ("t", "x", "u", "y")}
    return q, out["store_key"], tk


def _row(q, sk, tk):
    return {"key": tk, "system_id": SID, "split": "train", "family": "obs.nominal", "protocol": q, "meta": {"store_key": sk}}


def _table(rows):
    """The public-keys table of `rows`, each with its public trajectory file (the arrays a recomputed source must reproduce)."""
    entries = {}
    for r in rows:
        f = _PUBDIR / f"{r['key']}.npz"
        np.savez_compressed(f, **_ARRAYS[r["key"]])
        entries[r["key"]] = {"store_key": r["meta"]["store_key"], "system": SID, "dt": r["protocol"]["dt"], "t_end": r["protocol"]["t_end"],
                             "protocol": r["protocol"], "traj": str(f)}
    return {"format": PUBLIC_KEYS_FORMAT, "entries": entries, "aliases": {r["meta"]["store_key"]: r["key"] for r in rows}}


def _server(tmp_path, name, sysrec, table):
    return SimServer(tmp_path / name / "room", {SID: sysrec}, tmp_path / name / "store", pool="inline", ledger_dir=tmp_path / name / "ledger",
                     public_keys=table, budgets={"a": 100})


def test_build_public_keys_reads_rows_and_aliases_store_keys(tmp_path):
    sysrec = toy_sysdef()
    q1, sk1, tk1 = _simulate(tmp_path / "bench", sysrec, base())
    q2, sk2, tk2 = _simulate(tmp_path / "bench", sysrec, base(params_seed=5))
    d = tmp_path / "public" / "syn_toy_0"
    d.mkdir(parents=True)
    (d / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in (_row(q1, sk1, tk1), _row(q2, sk2, tk2))), encoding="utf-8")
    t = build_public_keys([d, tmp_path / "missing"], systems={SID})
    assert t["format"] == PUBLIC_KEYS_FORMAT and set(t["entries"]) == {tk1, tk2} and t["aliases"] == {sk1: tk1, sk2: tk2}
    assert t["entries"][tk1]["protocol"] == q1 and t["entries"][tk1]["store_key"] == sk1 and t["entries"][tk1]["dt"] == 0.01
    flat = expand_public_keys(t)
    assert flat[sk1] is flat[tk1] and len(flat) == 4
    assert build_public_keys([d], systems={"other"})["entries"] == {}
    assert expand_public_keys({"k": "s"}) == {"k": "s"}                    # a legacy flat table is used as it is


def test_a_missing_public_source_is_recomputed_and_serves_the_same_restart(tmp_path):
    sysrec = toy_sysdef()
    q1, sk1, tk1 = _simulate(tmp_path / "bench", sysrec, base())
    table = _table([_row(q1, sk1, tk1)])
    ask = base(t_end=0.5, r0={"kind": "restart", "key": tk1, "t": 0.3}, events=[{"kind": "kick", "t": 0.1, "delta": {"1": 0.5}}])
    ref = _server(tmp_path, "ref", sysrec, table)
    shutil.copytree(tmp_path / "bench", tmp_path / "ref" / "store", dirs_exist_ok=True)   # the reference HAS the benchmark's record
    a_ref, m_ref = ref.handle_request({"protocols": [ask]}, agent="a")
    assert m_ref["items"][0]["ok"] and ref.n_sources_recomputed == 0
    svc = _server(tmp_path, "svc", sysrec, table)                          # an empty store: the source must be recomputed
    a, m = svc.handle_request({"protocols": [ask]}, agent="a")
    assert m["items"][0]["ok"] and svc.n_sources_recomputed == 1
    for k in ("t", "x", "u", "y"):
        assert np.array_equal(a[f"i0_{k}"], a_ref[f"i0_{k}"])
    # the store key of the public row is an accepted alias; the recomputed source is not charged (1 experiment for 1 request)
    a2, m2 = svc.handle_request({"protocols": [dict(ask, r0={"kind": "restart", "key": sk1, "t": 0.3})]}, agent="a")
    assert m2["items"][0]["ok"] and np.array_equal(a2["i0_y"], a_ref["i0_y"]) and svc.n_sources_recomputed == 1
    assert svc.ledgers["a"].to_dict()["trajectories"] == m_ref["ledger"]["trajectories"] * 2
    log = [json.loads(x) for x in (tmp_path / "svc" / "ledger" / "requests.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [x["public_sources_recomputed"] for x in log] == [1, 0]


def test_a_public_source_that_does_not_reproduce_is_refused(tmp_path):
    sysrec = toy_sysdef()
    q1, sk1, tk1 = _simulate(tmp_path / "bench", sysrec, base())
    bad = _row(dict(q1, params_seed=7), sk1, tk1)                           # the row's protocol no longer produces its store key
    svc = _server(tmp_path, "svc", sysrec, _table([bad]))
    a, m = svc.handle_request({"protocols": [base(t_end=0.5, r0={"kind": "restart", "key": tk1, "t": 0.3})]}, agent="a")
    it = m["items"][0]
    assert not it["ok"] and it["error"].startswith("simulation failed (reference ") and not a
    logged = (tmp_path / "svc" / "ledger" / "errors.jsonl").read_text(encoding="utf-8")
    assert "not reproduced" in logged and svc.n_sources_recomputed == 0
    assert "trajectories" not in m["ledger"] or m["ledger"]["trajectories"] == 0


def test_public_sources_are_recomputed_recursively(tmp_path):
    sysrec = toy_sysdef()
    q1, sk1, tk1 = _simulate(tmp_path / "bench", sysrec, base())
    q2, sk2, tk2 = _simulate(tmp_path / "bench", sysrec, base(t_end=0.6, r0={"kind": "restart", "key": sk1, "t": 0.4},
                                                              events=[{"kind": "kick", "t": 0.1, "delta": {"2": 0.3}}]))
    table = _table([_row(q1, sk1, tk1), _row(q2, sk2, tk2)])
    ask = base(t_end=0.3, r0={"kind": "restart", "key": tk2, "t": 0.2})
    ref = _server(tmp_path, "ref", sysrec, table)
    shutil.copytree(tmp_path / "bench", tmp_path / "ref" / "store", dirs_exist_ok=True)
    a_ref, m_ref = ref.handle_request({"protocols": [ask]}, agent="a")
    svc = _server(tmp_path, "svc", sysrec, table)
    a, m = svc.handle_request({"protocols": [ask]}, agent="a")
    assert m_ref["items"][0]["ok"] and m["items"][0]["ok"] and svc.n_sources_recomputed == 2
    assert np.array_equal(a["i0_x"], a_ref["i0_x"]) and np.array_equal(a["i0_y"], a_ref["i0_y"])


# ------------------------------------------------------------------------------------------------ the reference-platform pool
def test_the_pool_recognises_run_job_under_any_module_name_and_refuses_other_callables(tmp_path):
    import importlib.util

    from brainir_causal.simdocker import DockerPool, is_run_job
    spec = importlib.util.spec_from_file_location("brainir_causal._main_copy", SU.__file__.replace("suites.py", "simservice.py"))
    copy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copy)                                           # what `python -m brainir_causal.simservice` creates
    assert is_run_job(run_job) and is_run_job(copy.run_job) and copy.run_job is not run_job
    assert not is_run_job(_simulate) and not is_run_job(int)
    pool = DockerPool(store_root=tmp_path / "s", bridge_dir=tmp_path / "b")    # never started: nothing reaches a container
    assert pool.submit(int, 3).result() == 3
    with pytest.raises(TypeError):
        pool.submit(_simulate, tmp_path, {}, {})


def _docker_ok() -> bool:
    try:
        from brainir_causal.isolation import docker_exe
        from brainir_causal.simdocker import worker_image
        r = subprocess.run([docker_exe(), "image", "inspect", worker_image()], capture_output=True, timeout=60, check=False)
        return r.returncode == 0
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.slow
@pytest.mark.skipif(not _docker_ok(), reason="docker or the p4 sandbox image is unavailable")
def test_the_docker_pool_answers_run_job_like_the_image_itself(tmp_path):
    from brainir_causal.isolation import docker_exe
    from brainir_causal.simdocker import CONTAINER_STORE, ROOT, DockerPool, worker_image
    sysrec = toy_sysdef()
    q = P.validate(base(events=[{"kind": "current", "t0": 0.2, "t1": 0.3, "targets": {"2": 1.0}}]))
    pool = DockerPool(store_root=tmp_path / "store", bridge_dir=tmp_path / "bridge", workers=2, cpus=2, mem_gb=2).start()
    try:
        svc = SimServer(tmp_path / "room", {SID: sysrec}, tmp_path / "store", pool=pool, ledger_dir=tmp_path / "ledger", budgets={"a": 10})
        assert svc._engines[SID] == ToySystem(3, 0).engine_id                  # engine ids read from the container
        a, m = svc.handle_request({"protocols": [q]}, agent="a")
        assert m["items"][0]["ok"]
        fut = pool.submit(run_job, {"sysdef": sysrec, "protocol": q, "store_root": str(tmp_path / "store"), "bundle": None}).result()
    finally:
        pool.shutdown()
    assert not pool.running()
    # the same job run directly in the image (a separate container, a separate store)
    code = ("import json, sys, numpy as np; from brainir_causal.simservice import run_job; job = json.loads(sys.argv[1]); "
            "o = run_job(job); np.savez('/svc/store/direct.npz', **{k: o[k] for k in ('t', 'x', 'u', 'y')}); print(o['store_key'])")
    job = {"sysdef": sysrec, "protocol": q, "store_root": CONTAINER_STORE, "bundle": None}
    (tmp_path / "direct").mkdir()
    r = subprocess.run([docker_exe(), "run", "--rm", "--network", "none", "--pull", "never", "--user", "1000:1000", "-e",
                        "PYTHONPATH=/repo/phase4/src:/repo/src", "-e", "PYTHONDONTWRITEBYTECODE=1", "-e", "NPY_DISABLE_CPU_FEATURES=X86_V4 AVX512_ICL AVX512_SPR",
                        "-e", "OMP_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1", "-v", f"{ROOT / 'phase4' / 'src'}:/repo/phase4/src:ro",
                        "-v", f"{ROOT / 'src'}:/repo/src:ro", "-v", f"{tmp_path / 'direct'}:/svc/store:rw", worker_image(), "python", "-c", code,
                        json.dumps(job)], capture_output=True, text=True, timeout=600, check=False)
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stdout.strip().splitlines()[-1] == fut["store_key"]
    with np.load(tmp_path / "direct" / "direct.npz") as z:
        for k in ("t", "x", "u", "y"):
            assert np.array_equal(z[k], fut[k]), k
    assert np.array_equal(a["i0_y"], fut["y"])


def _public_dir(root, rows_arrays):
    """A public dataset directory (p4-dataset-1 layout) with the given rows and their observed arrays."""
    (root / "traj").mkdir(parents=True, exist_ok=True)
    with open(root / "index.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for row, arrs in rows_arrays:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
            np.savez_compressed(root / "traj" / f"{row['key']}.npz", **arrs)
    return root


def test_a_recomputed_public_source_must_reproduce_the_public_arrays_not_only_the_key(tmp_path):
    """Review H round 3, NEW-1: the store key hashes the protocol, so a misconfigured engine could reproduce the key with different
    numbers. The service compares the recomputed observed arrays with the public dataset's, bit for bit."""
    sysrec = toy_sysdef()
    q1 = P.validate(base())
    out = run_job({"sysdef": sysrec, "protocol": q1, "store_root": str(tmp_path / "bench"), "bundle": None})
    sk1 = out["store_key"]
    tk1 = SU.dataset_key(q1, "toy-public", "toy-engine", sysrec.get("obs_scale"))
    arrs = {k: np.asarray(out[k]) for k in ("t", "x", "u", "y")}
    good = _public_dir(tmp_path / "pub_good", [(_row(q1, sk1, tk1), arrs)])
    table = build_public_keys([good], systems={SID})
    assert table["entries"][tk1]["traj"].endswith(f"{tk1}.npz")
    ask = base(t_end=0.5, r0={"kind": "restart", "key": tk1, "t": 0.3})
    svc = _server(tmp_path, "svc", sysrec, table)
    a, m = svc.handle_request({"protocols": [ask]}, agent="a")
    assert m["items"][0]["ok"] and svc.n_sources_recomputed == 1 and svc.n_sources_verified == 1
    tampered = dict(arrs, y=arrs["y"] + np.float32(1e-6))                  # same protocol, same store key, different numbers
    bad = _public_dir(tmp_path / "pub_bad", [(_row(q1, sk1, tk1), tampered)])
    svc2 = _server(tmp_path, "svc2", sysrec, build_public_keys([bad], systems={SID}))
    a2, m2 = svc2.handle_request({"protocols": [ask]}, agent="a")
    assert not m2["items"][0]["ok"] and not a2 and svc2.n_sources_recomputed == 0
    logged = (tmp_path / "svc2" / "ledger" / "errors.jsonl").read_text(encoding="utf-8")
    assert "differs from the public data" in logged


def test_a_public_source_without_readable_public_arrays_is_refused(tmp_path):
    """Review H round 3b, NEW-6: the reproduction check fails CLOSED. A source whose public trajectory file is missing (or was never
    recorded) is refused and its recomputed record removed, never served unverified."""
    sysrec = toy_sysdef()
    q1, sk1, tk1 = _simulate(tmp_path / "bench", sysrec, base())
    table = _table([_row(q1, sk1, tk1)])
    Path(table["entries"][tk1]["traj"]).unlink()
    svc = _server(tmp_path, "svc", sysrec, table)
    a, m = svc.handle_request({"protocols": [base(t_end=0.5, r0={"kind": "restart", "key": tk1, "t": 0.3})]}, agent="a")
    assert not m["items"][0]["ok"] and not a and svc.n_sources_recomputed == 0
    assert "no public arrays to verify against" in (tmp_path / "svc" / "ledger" / "errors.jsonl").read_text(encoding="utf-8")
    del table["entries"][tk1]["traj"]
    svc2 = _server(tmp_path, "svc2", sysrec, table)
    _, m2 = svc2.handle_request({"protocols": [base(t_end=0.5, r0={"kind": "restart", "key": tk1, "t": 0.3})]}, agent="a")
    assert not m2["items"][0]["ok"] and svc2.n_sources_verified == 0
