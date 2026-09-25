"""state_discovery_v1 Level C: generate the REAL HIDDEN TEST (orchestrator; run ONLY after research/phase3/METHOD_LOCK.json exists).

    uv run --project phase3 python scripts/p3/generate_real_hidden.py [--workers 12] [--per-family 30] [--backend local|modal]
    uv run --project phase3 python scripts/p3/generate_real_hidden.py verify-public [--n 24]      # Modal vs stored PUBLIC records

Locked with the benchmark (its hash is in BENCHMARK_LOCK.json) and run once after the method lock. Seeds derive from the secret salt
(data/phase3/hidden/salt.txt, committed by sha256 before development). Produces data/phase3/real_hidden/ (never in any clean room):
    test trajectories of every hidden family of PROTOCOL.md section 3, a counterfactual twin (no events) for every intervention
    trajectory, and the H_micro pools: states sampled from pool trajectories, each restarted from its FULL microstate under the
    common nominal input for 250 ms (the future readout the evaluator compares), plus a numerical-floor twin per state (the same
    restart split at an extra breakpoint).

Benchmark version 3 (pre-lock review D, M1): every trajectory with kicks carries index info["kicks_applied"] = [{"t", "requested":
{neuron: offset}, "applied": {neuron: offset}}, ...], the offsets the engine actually applied (rates are clipped at 0), next to the
requested ones. The event dicts themselves are unchanged (methods see the public event format); the evaluator reports clipped and
null kicks per family (brainir_state.realgen.applied_kick_totals).

Backends (benchmark version 3, logged pre-use re-lock). The protocols are built LOCALLY in both (the salt never leaves the machine;
the protocols carry the derived hidden seeds). `local` simulates on a local process pool. `modal` simulates on the pinned Modal image
(PROTOCOL.md section 10: AVX2 kernels, under which Modal reproduces the stored public records bit for bit; `verify-public` re-checks
this on this code path) and writes the records and the assembled dataset to the EVAL volume only (/evalvol/suites/real/hidden, where
the Level C evaluation reads it; fit containers never mount that volume); the local copy data/phase3/real_hidden is then downloaded
and its text files are checked against the hashes computed at write time. Every trajectory of the test set, its twin and every
microstate restart is simulated on ONE platform. Both backends use the same job construction, the same record keys and the same
microstate selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import posixpath
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from brainir_state import data as D
from brainir_state import protocol as P
from brainir_state.realgen import HIDDEN_FAMILIES, INTERVENTION_FAMILIES, Sampler, counterfactual, family_protocol, hidden_seed, micro_pool_protocols
from brainir_state.realsim import RealEngine, RealSystem, dense, kicks_applied_from_record
from brainir_state.store import TrajectoryStore

ROOT = Path(__file__).resolve().parents[2]
BUNDLE = ROOT / "benchmarks" / "dng100" / "public_blind"
BENCH = ROOT / "benchmarks" / "state_discovery_v1"
DATA = ROOT / "data" / "phase3"
MICRO_STATES_PER_TRAJ, MICRO_FUTURE_S = 4, 0.25
# Modal (eval volume only)
REMOTE_STORE = "/evalvol/real_hidden_build/store"
REMOTE_DATASET = "/evalvol/suites/real/hidden"
REMOTE_LINKS = {"/repo/benchmarks/dng100/public_blind": "/fitvol/bundles/dng100_public_blind"}
BATCH = 8


def _sys(d: dict) -> RealSystem:
    return RealSystem(system_id=d["system_id"], network=d["network"], mode=d["mode"], keep=tuple(d["keep"]), observed=tuple(d["observed"]),
                      readout=tuple(d["readout"]), stimulus=tuple(d["stimulus"]))


_ENG: dict = {}


def _engine(net):
    if net not in _ENG:
        _ENG[net] = RealEngine(BUNDLE, net)
    return _ENG[net]


def _run(args):
    d, proto = args
    key, rec, _ = TrajectoryStore(DATA / "store").get_or_run(_engine(d["network"]), _sys(d), proto, d["system_hash"], meta={"source": "hidden"})
    return key, rec


def row_info(meta: dict, rec: dict, proto: dict) -> dict:
    """The index info of one hidden trajectory: the bookkeeping of `meta` (pair id, group, params seed) and, for trajectories with
    kicks, the applied kick offsets (from the engine record; reconstructed from the stored rates for a record stored before the
    engine recorded them)."""
    info = {k: v for k, v in meta.items() if k not in ("system_id", "family", "role")}
    if any(e.get("kind") == "kick" for e in proto.get("events") or []):
        ka = (rec.get("info") or {}).get("kicks_applied")
        info["kicks_applied"] = ka if ka is not None else kicks_applied_from_record(rec, proto)
    return info


def micro_states(key: str, rec: dict, m: dict, d: dict) -> list[tuple]:
    """The MICRO_STATES_PER_TRAJ states sampled from one pool trajectory (deterministic in its key): [(job, micro_meta)]."""
    rng = np.random.default_rng(int(key[:8], 16))
    out = []
    for i in sorted(rng.choice(np.arange(300, len(rec["t"]) - 1), MICRO_STATES_PER_TRAJ, replace=False)):
        full = {int(n): float(v) for n, v in zip(rec["neurons"], rec["rates"][i])}
        out.append(((d, full, m["params_seed"], float(rec["t"][i])),
                    {"key": key, "index": int(i), "group": m["group"], "system_id": m["system_id"]}))
    return out


def _micro_future(args):
    """Restart one sampled FULL microstate under the common input; also the numerical-floor twin (extra breakpoint)."""
    d, state, seed, t_s = args
    s = _sys(d)
    vals = {str(int(n)): float(v) for n, v in state.items() if v > 0}
    base = {"system": d["system_id"], "params_seed": seed, "t_end": MICRO_FUTURE_S, "dt": 0.001, "stimulus": [[0.0, 1.0]],
            "r0": {"kind": "state", "values": vals}}
    rec = _engine(d["network"]).run(s, base)
    twin = _engine(d["network"]).run(s, dict(base, stimulus=[[0.0, 1.0], [round(MICRO_FUTURE_S / 2 + 0.0005, 3), 1.0]]))
    return dense(rec, list(s.readout)), dense(twin, list(s.readout))


def build_jobs(per_family: int) -> tuple[dict, dict, list, list]:
    """(systems, public definitions, jobs [(sysdef, protocol)], meta) - the hidden test set, from the salt (local only)."""
    salt = (DATA / "hidden" / "salt.txt").read_text(encoding="utf-8").strip()
    commit = json.loads((BENCH / "hidden" / "salt_commitment.json").read_text(encoding="utf-8"))["sha256_of_salt"]
    if hashlib.sha256(salt.encode()).hexdigest() != commit:
        raise SystemExit("salt does not match its commitment")
    systems = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    public = json.loads((BENCH / "public" / "systems_public.json").read_text(encoding="utf-8"))
    pub_ds = D.Dataset(DATA / "real_public")
    jobs, meta = [], []
    for sid, d in systems.items():
        A, B = d["targets_public"], d["targets_heldout"]
        s = _sys(d)
        pool = []   # state pool for init_state from PUBLIC nominal trajectories of this system (observed neurons only)
        for tr in list(pub_ds.iter(system_id=sid, split="train", family="nominal"))[:10]:
            for i in range(300, len(tr.t), 400):
                pool.append({str(n): float(v) for n, v in zip(d["observed"], tr.x[i]) if v > 0})
        n_fam = per_family if d["mode"] == "full" else max(10, per_family // 2)
        for fam in HIDDEN_FAMILIES:
            if fam in ("H_kick_B", "H_pulse_B", "H_silence1_B") and not B:
                continue
            for j in range(n_fam):
                seed = hidden_seed(salt, sid, fam, j)
                rng = np.random.default_rng(seed % (2**32))
                smp = Sampler(s, rng, seed_fn=lambda sd=seed: sd, state_pool=pool)
                proto = P.validate(family_protocol(fam, smp, A, B))
                jobs.append((d, proto)); meta.append({"system_id": sid, "family": fam, "role": "test", "pair": f"{fam}:{j}"})
                if fam in INTERVENTION_FAMILIES:
                    jobs.append((d, P.validate(counterfactual(proto)))); meta.append({"system_id": sid, "family": fam, "role": "twin", "pair": f"{fam}:{j}"})
        for p in micro_pool_protocols(s, salt, A, pool):
            g = p.pop("group")
            jobs.append((d, P.validate(p))); meta.append({"system_id": sid, "family": "H_micro", "role": "pool", "group": g,
                                                            "params_seed": p["params_seed"]})
    return systems, public, jobs, meta


def manifest_for(public: dict) -> dict:
    return {"dataset_id": "state_discovery_v1/real_hidden", "version": "1", "dt": 0.001,
            "systems": {sid: {k: v for k, v in public[sid].items() if k not in ("local_graph", "signs")} | {"kind": "real"} for sid in public},
            "splits": ["test", "twin", "pool"], "families": list(HIDDEN_FAMILIES) + ["H_micro"],
            "info_keys": {"kicks_applied": "per kick event: requested and applied (rates clipped at 0) offsets per neuron (version 3)"}}


def write_all(out: Path, manifest: dict, items: list, futures: list, micro_meta: list) -> dict:
    """Write the dataset and the microstate files; returns the sha256 of every text file (for the transfer check)."""
    D.write_dataset(out, manifest, items)
    # per restart (readout dimensions differ between networks): future_<i>, floor_<i> (brainir_state.harness._micro_files)
    np.savez_compressed(out / "micro_futures.npz", **{f"future_{i}": f for i, (f, _) in enumerate(futures)},
                        **{f"floor_{i}": t for i, (_, t) in enumerate(futures)})
    (out / "micro_index.json").write_text(json.dumps(micro_meta) + "\n", encoding="utf-8")
    return {n: hashlib.sha256((out / n).read_bytes()).hexdigest() for n in ("index.jsonl", "manifest.json", "micro_index.json")}


# ------------------------------------------------------------------------------------------------ container side (Modal backend)
def remote_sim_batch(items: list, store_root: str = REMOTE_STORE, with_hash: bool = False) -> list:
    """Simulate [(sysdef, protocol, meta)] on the real engine and store each record under store_root (the eval volume; content-
    addressed like the local store). Returns per item: the key, the index info and, for pool trajectories, the sampled microstates."""
    st = TrajectoryStore(store_root)
    out = []
    for d, proto, m in items:
        key, rec, _ = st.get_or_run(_engine(d["network"]), _sys(d), proto, d["system_hash"], meta={"source": "hidden"})
        r = {"key": key, "info": row_info(m, rec, proto) if m else None}
        if m and m.get("family") == "H_micro":
            r["micro"] = [(job[1], job[2], job[3], mm) for job, mm in micro_states(key, rec, m, d)]
        if with_hash:
            r["sha"] = {k: hashlib.sha256(np.ascontiguousarray(rec[k]).tobytes()).hexdigest() for k in ("t", "neurons", "rates", "u")}
        out.append(r)
    return out


def remote_micro_batch(items: list, out_path: str) -> dict:
    """Microstate restarts of one batch, written to the volume (future_<j>, floor_<j>, j local to the batch)."""
    futures = [_micro_future(tuple(it)) for it in items]
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **{f"future_{j}": f for j, (f, _) in enumerate(futures)}, **{f"floor_{j}": t for j, (_, t) in enumerate(futures)})
    return {"path": str(p), "n": len(futures)}


def remote_assemble(rows: list, systems_by_id: dict, public: dict, micro_parts: list, micro_meta: list,
                    store_root: str = REMOTE_STORE, out: str = REMOTE_DATASET) -> dict:
    """Build the dataset on the eval volume from the stored records. rows: [(key, system_id, role, family, protocol, info)] in job order;
    micro_parts: the batch files of remote_micro_batch in order ({"path", "n"})."""
    import shutil
    st = TrajectoryStore(store_root)
    items = []
    for key, sid, role, fam, proto, info in rows:
        rec = st.get(key)
        d = systems_by_id[sid]
        arr = {"t": rec["t"], "x": dense(rec, d["observed"]), "u": rec["u"], "y": dense(rec, d["readout"])}
        items.append(({"key": key, "system_id": sid, "split": role, "family": fam, "protocol": proto, "info": info}, arr))
    futures = []
    for part in micro_parts:
        with np.load(part["path"]) as z:
            futures += [(z[f"future_{j}"], z[f"floor_{j}"]) for j in range(int(part["n"]))]
    if len(futures) != len(micro_meta):
        raise SystemExit(f"{len(futures)} microstate futures for {len(micro_meta)} states")
    o = Path(out)
    if o.exists():
        shutil.rmtree(o)
    o.mkdir(parents=True)
    hashes = write_all(o, manifest_for(public), items, futures, micro_meta)
    return {"n_items": len(items), "n_micro": len(futures), "sha256": hashes}


def remote_tar(src_dir: str, tar_path: str) -> dict:
    """One uncompressed tar of a directory on the volume (a single file downloads much faster than thousands of small ones)."""
    import tarfile
    t = Path(tar_path)
    t.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(t, "w") as tf:
        tf.add(src_dir, arcname=posixpath.basename(src_dir.rstrip("/")))
    h = hashlib.sha256()
    with open(t, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return {"path": str(t), "bytes": t.stat().st_size, "sha256": h.hexdigest()}


def _download(remote_path: str, local_file: Path) -> str:
    """Stream one file of the eval volume to disk (Modal SDK); returns its sha256."""
    import modal
    vol = modal.Volume.from_name("brainir-p3-eval")
    h = hashlib.sha256()
    local_file.parent.mkdir(parents=True, exist_ok=True)
    with open(local_file, "wb") as fh:
        for chunk in vol.read_file(remote_path):
            fh.write(chunk)
            h.update(chunk)
    return h.hexdigest()


# ------------------------------------------------------------------------------------------------ orchestration
def _modal_calls(module_func: str, arg_lists: list, commit: bool) -> list:
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    import modal_tournament as MT
    func = module_func
    payloads = [{"job_id": __import__("uuid").uuid4().hex, "kind": "call_commit" if commit else "call", "module": "generate_real_hidden",
                 "func": func, "args": list(a), "links": REMOTE_LINKS, "timeout_s": 7200} for a in arg_lists]
    res = MT._eval_map(payloads, f"call:{func}")
    out = []
    for r in res:
        if isinstance(r, BaseException) or (isinstance(r, dict) and "result" not in r):
            raise SystemExit(f"remote {func} failed: {r if isinstance(r, BaseException) else (r.get('error'), (r.get('stderr') or '')[-2000:])}")
        out.append(r["result"])
    return out


def run_modal(systems: dict, public: dict, jobs: list, meta: list, containers: int, *, store_root: str = REMOTE_STORE,
              remote_out: str = REMOTE_DATASET, local_out: Path | None = None) -> dict:
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    import shutil
    import subprocess

    import modal_tournament as MT
    app = MT._open_app(containers)
    build = posixpath.dirname(store_root)          # a path on the Linux volume (never built with the local Path class)
    batches = [[(d, proto, m) for (d, proto), m in zip(jobs[i: i + BATCH], meta[i: i + BATCH])] for i in range(0, len(jobs), BATCH)]
    with MT._output(), app.run():
        res = [r for b in _modal_calls("remote_sim_batch", [[b, store_root] for b in batches], commit=True) for r in b]
        rows, micro_jobs, micro_meta = [], [], []
        for r, m, (d, proto) in zip(res, meta, jobs):
            rows.append((r["key"], m["system_id"], m["role"], m["family"], proto, r["info"]))
            for state, seed, t_s, mm in r.get("micro") or []:
                micro_jobs.append((d, {int(k): v for k, v in state.items()}, seed, t_s))
                micro_meta.append(mm)
        mb = [micro_jobs[i: i + 4 * BATCH] for i in range(0, len(micro_jobs), 4 * BATCH)]
        parts = _modal_calls("remote_micro_batch", [[b, f"{build}/micro/part_{i:05d}.npz"] for i, b in enumerate(mb)], commit=True)
        sysmap = {sid: d for sid, d in systems.items()}
        rep = _modal_calls("remote_assemble", [[rows, sysmap, public, parts, micro_meta, store_root, remote_out]], commit=True)[0]
        tar = _modal_calls("remote_tar", [[remote_out, f"{build}/dataset.tar"]], commit=True)[0]
        costs = list(MT._STATE["costs"])
    print(f"assembled on the eval volume: {rep['n_items']} trajectories, {rep['n_micro']} microstate restarts; "
          f"tar {tar['bytes'] / 1e6:.0f} MB", flush=True)
    # the local copy (downlink), checked against the hashes computed at write time
    import tarfile
    out = local_out or (DATA / "real_hidden")
    out.parent.mkdir(parents=True, exist_ok=True)
    dl = out.parent / f"_{out.name}_dl"
    shutil.rmtree(dl, ignore_errors=True)
    dl.mkdir(parents=True)
    got = _download(tar["path"].replace("/evalvol/", "", 1), dl / "dataset.tar")
    if got != tar["sha256"]:
        raise SystemExit("transfer check failed: the downloaded tar differs from the one written on the volume")
    with tarfile.open(dl / "dataset.tar") as tf:
        tf.extractall(dl, filter="data")
    (dl / "dataset.tar").unlink()
    src = dl / posixpath.basename(remote_out.rstrip("/"))
    for n, h in rep["sha256"].items():
        if hashlib.sha256((src / n).read_bytes()).hexdigest() != h:
            raise SystemExit(f"transfer check failed for {n}")
    n_traj = len(list((src / "traj").glob("*.npz")))
    if n_traj != rep["n_items"]:
        raise SystemExit(f"transfer check failed: {n_traj} trajectory files for {rep['n_items']} rows")
    if out.exists():
        shutil.rmtree(out)
    shutil.move(str(src), str(out))
    shutil.rmtree(dl, ignore_errors=True)
    rep = dict(rep, costs=costs, tar_sha256=tar["sha256"], tar_bytes=tar["bytes"])
    (out / "GENERATION.json").write_text(json.dumps({"backend": "modal", "remote": remote_out, **rep}, indent=1) + "\n",
                                         encoding="utf-8", newline="\n")
    print(f"downloaded and verified {out}", flush=True)
    return rep


def run_local(systems: dict, public: dict, jobs: list, meta: list, workers: int) -> None:
    items, micro_jobs, micro_meta = [], [], []
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for (key, rec), m, (d, proto) in zip(ex.map(_run, jobs, chunksize=4), meta, jobs):
            arr = {"t": rec["t"], "x": dense(rec, d["observed"]), "u": rec["u"], "y": dense(rec, d["readout"])}
            items.append(({"key": key, "system_id": m["system_id"], "split": m["role"], "family": m["family"], "protocol": proto,
                           "info": row_info(m, rec, proto)}, arr))
            if m["family"] == "H_micro":
                for job, mm in micro_states(key, rec, m, d):
                    micro_jobs.append(job)
                    micro_meta.append(mm)
        futures = list(ex.map(_micro_future, micro_jobs, chunksize=4))
    out = DATA / "real_hidden"
    hashes = write_all(out, manifest_for(public), items, futures, micro_meta)
    (out / "GENERATION.json").write_text(json.dumps({"backend": "local", "n_items": len(items), "n_micro": len(futures), "sha256": hashes},
                                                    indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {len(items)} hidden trajectories and {len(futures)} microstate restarts")


def verify_public(n: int, containers: int) -> int:
    """Simulate n PUBLIC real protocols (stored in data/phase3/store) on the Modal backend's code path and compare every array bit for
    bit with the stored records. Development data only."""
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    import modal_tournament as MT
    systems = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    store = TrajectoryStore(DATA / "store")
    rows = [json.loads(line) for line in open(store.index_path, encoding="utf-8")]
    rng = np.random.default_rng(0)
    picked, seen_sys = [], {}
    for r in [rows[i] for i in rng.permutation(len(rows))]:
        if r.get("system_id") not in systems or not store.has(r["key"]):
            continue
        if seen_sys.get(r["system_id"], 0) >= max(2, n // len(systems)):
            continue
        seen_sys[r["system_id"]] = seen_sys.get(r["system_id"], 0) + 1
        picked.append(r)
        if len(picked) >= n:
            break
    items = [(systems[r["system_id"]], r["protocol"], {}) for r in picked]
    app = MT._open_app(containers)
    with MT._output(), app.run():
        res = [x for b in _modal_calls("remote_sim_batch", [[[it], "/tmp/verify_store", True] for it in items], commit=False) for x in b]
    bad = []
    for r, row in zip(res, picked):
        rec = store.get(row["key"])
        local = {k: hashlib.sha256(np.ascontiguousarray(rec[k]).tobytes()).hexdigest() for k in ("t", "neurons", "rates", "u")}
        if r["key"] != row["key"] or r["sha"] != local:
            bad.append({"system_id": row["system_id"], "key": row["key"], "remote_key": r["key"]})
    rep = {"n": len(picked), "systems": sorted(seen_sys), "n_mismatch": len(bad), "mismatches": bad, "costs": MT._STATE["costs"]}
    p = ROOT / "research" / "phase3" / "level_c" / "hidden_generator_modal_verification.json"
    p.write_text(json.dumps(rep, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rep.items() if k != "mismatches"}, indent=1))
    return 0 if not bad else 1


def smoke_public(n: int, containers: int) -> int:
    """The whole Modal pipeline (simulate, store, microstate restarts, assemble, download, transfer check) on n PUBLIC validation
    protocols of each real system (the first of each system stands in as a pool trajectory), into scratch paths on the eval volume and
    data/phase3/_smoke_real_hidden. Development data only."""
    systems = json.loads((BENCH / "hidden" / "systems_internal.json").read_text(encoding="utf-8"))
    public = json.loads((BENCH / "public" / "systems_public.json").read_text(encoding="utf-8"))
    pub = D.Dataset(DATA / "real_public")
    jobs, meta = [], []
    for sid, d in systems.items():
        rows = [r for r in pub.select(system_id=sid) if r["split"] == "val"][:n]
        for j, r in enumerate(rows):
            m = {"system_id": sid, "family": "H_micro" if j == 0 else r["family"], "role": "pool" if j == 0 else "test", "pair": f"smoke:{j}"}
            if j == 0:
                m.update(group=0, params_seed=int(r["protocol"]["params_seed"]))
            jobs.append((d, P.validate(r["protocol"])))
            meta.append(m)
    rep = run_modal(systems, public, jobs, meta, containers, store_root="/evalvol/_smoke/real_hidden_build/store",
                    remote_out="/evalvol/_smoke/real_hidden", local_out=DATA / "_smoke_real_hidden")
    # the simulated records must equal the stored PUBLIC records (same keys, bit-identical arrays)
    store = TrajectoryStore(DATA / "store")
    smoke = D.Dataset(DATA / "_smoke_real_hidden")
    n_same = 0
    for r in smoke.index:
        rec = store.get(r["key"])
        tr = smoke.load(r)
        d = systems[r["system_id"]]
        if rec is not None and np.array_equal(dense(rec, d["observed"]), tr.x) and np.array_equal(dense(rec, d["readout"]), tr.y):
            n_same += 1
    out = ROOT / "research" / "phase3" / "level_c" / "hidden_generator_modal_smoke.json"
    out.write_text(json.dumps({"n_jobs": len(jobs), "n_identical_to_stored_public": n_same, **rep}, indent=1, default=str) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"smoke: {n_same} of {len(smoke.index)} trajectories identical to the stored public records", flush=True)
    return 0 if n_same == len(smoke.index) else 1


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "smoke-public":
        ap = argparse.ArgumentParser()
        ap.add_argument("--n", type=int, default=3)
        ap.add_argument("--containers", type=int, default=50)
        a = ap.parse_args(argv[1:])
        return smoke_public(a.n, a.containers)
    if argv and argv[0] == "verify-public":
        ap = argparse.ArgumentParser()
        ap.add_argument("--n", type=int, default=24)
        ap.add_argument("--containers", type=int, default=50)
        a = ap.parse_args(argv[1:])
        return verify_public(a.n, a.containers)
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--per-family", type=int, default=30)
    ap.add_argument("--backend", choices=("local", "modal"), default="local")
    ap.add_argument("--containers", type=int, default=300)
    args = ap.parse_args(argv)
    if not (ROOT / "research" / "phase3" / "METHOD_LOCK.json").exists():
        raise SystemExit("refusing: the Level C hidden test is generated only after research/phase3/METHOD_LOCK.json exists")
    systems, public, jobs, meta = build_jobs(args.per_family)
    print(f"{len(systems)} systems; {len(jobs)} hidden trajectories ({args.backend})", flush=True)
    if args.backend == "modal":
        run_modal(systems, public, jobs, meta, args.containers)
    else:
        run_local(systems, public, jobs, meta, args.workers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
