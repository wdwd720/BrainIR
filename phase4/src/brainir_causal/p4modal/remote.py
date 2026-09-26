"""Container side of the Phase 4 Modal backend (runs in the Modal image; the orchestrator side is brainir_causal.p4modal.app).

Job kinds (each is a function of one payload dict; the app wraps simulation and, on request, CPU jobs with the host gate):
- `run_sim`      a batch of real-engine simulations (brainir_causal.realsim, the frozen Phase 1 simulator underneath) in a spawn
                 process pool, served from / written to a content-addressed store on a VOLUME (`VolumeStore`: the key of
                 brainir_causal.store, the record format of TrajectoryStore, atomic writes, no lock files, per-container index
                 shards). Public / development records live on the store volume; records of hidden data are written to the EVAL
                 volume only (payload store='eval'), which fit containers never mount. Returns full records (compressed bytes) or
                 only the observed arrays.
- `run_call`     an orchestrator function (no method code) in a fresh subprocess.
- `run_method`   a function in a fresh GUARDED subprocess (brainir_causal.runguard via sitecustomize; mode 'fit': the whole process
                 may touch only its allowed roots, no processes, no network; mode 'eval': the same while a method frame is on the
                 stack). Optional per-job simulation service (brainir_causal.simservice.SimServer) in THIS process on a queue in the
                 job directory: the method's process never holds the simulator or truth; real full networks go through
                 `VolumeStoreBackend` (volume cache, else computed here).
- `run_extract`  unpack an uploaded tar on a volume; `run_hashes` sha256 of volume files (transfer checks).
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pickle
import shutil
import subprocess
import sys
import tarfile
import threading
import time
import uuid
from pathlib import Path

WORK = Path("/tmp/p4m")
MOUNTS = {"fit": Path("/fitvol"), "eval": Path("/evalvol"), "store": Path("/storevol")}
VOLUME_NAMES = {"fit": "brainir-p4-fit", "eval": "brainir-p4-eval", "store": "brainir-p4-store"}
BUNDLE = Path("/repo/benchmarks/dng100/public_blind")
SITE = "/repo/p4modal_site"
BASE_PYTHONPATH = os.pathsep.join(["/repo/phase4/src", "/repo/phase3/src", "/repo/src"])
SIGNAL_RETRIES = 1
CONTAINER_ID = os.environ.get("MODAL_TASK_ID") or uuid.uuid4().hex[:12]


# ------------------------------------------------------------------------------------------------ bookkeeping
class MemPeak:
    """Peak memory of the container while a job runs (cgroup counters, sampled every 0.25 s)."""

    FILES = ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes")

    def __init__(self):
        self.peak = 0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._file = next((f for f in self.FILES if os.path.exists(f)), None)

    def _read(self) -> int:
        try:
            with open(self._file) as fh:
                return int(fh.read().strip())
        except Exception:  # noqa: BLE001
            return 0

    def _loop(self):
        while not self._stop.is_set():
            self.peak = max(self.peak, self._read())
            self._stop.wait(0.25)

    def __enter__(self):
        if self._file:
            self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        if self._file:
            self._thread.join(timeout=2)
            self.peak = max(self.peak, self._read())
        return False

    @property
    def mb(self) -> float | None:
        return round(self.peak / 2**20, 1) if self._file else None


def with_mem(fn):
    import functools

    @functools.wraps(fn)
    def wrapped(p):
        t0 = time.time()
        with MemPeak() as mp:
            res = fn(p)
        if isinstance(res, dict):
            res["peak_container_mb"] = mp.mb
            res.setdefault("container_wall_s", round(time.time() - t0, 2))
        return res
    return wrapped


def _volume(name: str):
    import modal
    return modal.Volume.from_name(VOLUME_NAMES[name])


def _reload(name: str) -> None:
    try:
        _volume(name).reload()
    except Exception:  # noqa: BLE001 - not mounted in this function, or nothing to reload
        pass


def _commit(name: str) -> None:
    _volume(name).commit()


# ------------------------------------------------------------------------------------------------ records
def record_to_bytes(rec: dict) -> bytes:
    """The TrajectoryStore file format (compressed NPZ, `info` as a JSON string) in memory."""
    import numpy as np
    buf = io.BytesIO()
    arrays = {k: np.asarray(v) for k, v in rec.items() if k != "info"}
    np.savez_compressed(buf, info=np.array(json.dumps(rec.get("info") or {}, sort_keys=True)), **arrays)
    return buf.getvalue()


def record_from_bytes(blob: bytes) -> dict:
    import numpy as np
    with np.load(io.BytesIO(blob), allow_pickle=False) as z:
        rec = {k: z[k] for k in z.files if k != "info"}
        rec["info"] = json.loads(str(z["info"])) if "info" in z.files else {}
    return rec


def array_digest(rec: dict) -> dict:
    import numpy as np
    return {k: hashlib.sha256(np.ascontiguousarray(v).tobytes()).hexdigest() for k, v in rec.items() if k != "info"}


class VolumeStore:
    """A content-addressed store on a Modal volume, compatible with brainir_causal.store.TrajectoryStore (same keys, same file layout
    and format), without lock files: records are written atomically (tmp + rename); two containers computing the same key write the
    same arrays (deterministic engine on gated hosts). Index lines go to one shard per container (index_shards/<container>.jsonl), so
    concurrent containers never write the same file. Call `commit()` after writing."""

    def __init__(self, root: Path, volume: str):
        self.root, self.volume = Path(root), volume
        (self.root / "rec").mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        return self.root / "rec" / key[:2] / f"{key}.npz"

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    def get(self, key: str) -> dict | None:
        p = self.path(key)
        if not p.exists():
            return None
        return record_from_bytes(p.read_bytes())

    def get_bytes(self, key: str) -> bytes | None:
        p = self.path(key)
        return p.read_bytes() if p.exists() else None

    def put(self, key: str, rec: dict, meta: dict) -> None:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{key}.{CONTAINER_ID}.{os.getpid()}.tmp")
        tmp.write_bytes(record_to_bytes(rec))
        os.replace(tmp, p)
        shard = self.root / "index_shards" / f"{CONTAINER_ID}.jsonl"
        shard.parent.mkdir(parents=True, exist_ok=True)
        with open(shard, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"key": key, **meta}, sort_keys=True) + "\n")

    def commit(self) -> None:
        _commit(self.volume)


class _RestartSources:
    """Where the engine looks up the record of an r0 'restart': payload-provided records, then a local TrajectoryStore (the job's), then
    the volume store."""

    def __init__(self, provided: dict | None, local_root: str | None, vstore: VolumeStore | None):
        self.provided = dict(provided or {})
        self.local = None
        if local_root:
            from brainir_causal.store import TrajectoryStore
            self.local = TrajectoryStore(local_root)
        self.vstore = vstore

    def get(self, key: str) -> dict | None:
        if key in self.provided:
            return record_from_bytes(self.provided[key])
        if self.local is not None:
            rec = self.local.get(key)
            if rec is not None:
                return rec
        return self.vstore.get(key) if self.vstore is not None else None


_ENGINES: dict = {}


def _engine(network: str):
    from brainir_causal.realsim import RealEngine
    if network not in _ENGINES:
        _ENGINES[network] = RealEngine(BUNDLE, network)
    return _ENGINES[network]


def real_key(sysdef: dict, protocol: dict) -> str:
    from brainir.sim.model import MODEL_ID

    from brainir_causal import protocol as P
    from brainir_causal.realsim import ENGINE_VERSION
    from brainir_causal.store import TrajectoryStore
    return TrajectoryStore.key(P.validate(protocol), sysdef["system_hash"], f"{ENGINE_VERSION}|{MODEL_ID}")


def sim_record(sysdef: dict, protocol: dict, vstore: VolumeStore | None, *, provided: dict | None = None, local_root: str | None = None,
               meta: dict | None = None) -> tuple[str, dict, bool]:
    """(key, full engine record, computed?) of one real protocol: from the volume store when present, else simulated here and written
    to the volume store (not committed here)."""
    from brainir_causal import protocol as P
    from brainir_causal.realsim import RealSystem
    q = P.validate(protocol)
    key = real_key(sysdef, q)
    if vstore is not None:
        rec = vstore.get(key)
        if rec is not None:
            return key, rec, False
    rec = _engine(sysdef["network"]).run(RealSystem.from_record(sysdef), q, store=_RestartSources(provided, local_root, vstore))
    if vstore is not None:
        vstore.put(key, rec, {"system_id": sysdef["system_id"], "system_hash": sysdef["system_hash"], "protocol": P.microstate_protocol(q),
                              "source": (meta or {}).get("source", "p4modal"), **{k: v for k, v in (meta or {}).items() if k != "source"}})
    return key, rec, True


def _sim_worker_init(threads: int) -> None:
    os.environ.update(OMP_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS=str(threads), MKL_NUM_THREADS=str(threads))
    try:
        from threadpoolctl import threadpool_limits
        threadpool_limits(threads)
    except Exception:  # noqa: BLE001
        pass


def _sim_item(args: tuple) -> dict:
    item, store_name, store_sub, mode = args
    vstore = VolumeStore(MOUNTS[store_name] / store_sub, store_name) if store_name else None
    t0 = time.time()
    try:
        key, rec, computed = sim_record(item["sysdef"], item["protocol"], vstore, provided=item.get("restart_src"),
                                        meta=item.get("meta"))
    except Exception as e:  # noqa: BLE001
        import traceback
        return {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]}
    out = {"key": key, "computed": computed, "sha": array_digest(rec), "info": rec.get("info"), "sim_wall_s": round(time.time() - t0, 3)}
    if mode == "full":
        out["record"] = record_to_bytes(rec)
    elif mode == "observed":
        from brainir_causal.realsim import RealSystem, observe
        obs = observe(rec, RealSystem.from_record(item["sysdef"]), item["protocol"], item["sysdef"].get("obs_scale"))
        out.update({k: obs[k] for k in ("t", "x", "u", "y")})
    return out


@with_mem
def run_sim(p: dict) -> dict:
    """payload: {"items": [{"sysdef": INTERNAL record, "protocol": dict, "restart_src": {key: record bytes}?, "meta": {}?}],
    "store": "store" | "eval" | None, "store_sub": "store", "mode": "full" | "observed" | "digest", "workers": int, "threads": int}.
    Results in item order; the volume is reloaded first (other containers' records) and committed after the batch."""
    import multiprocessing as mp
    from concurrent.futures import ProcessPoolExecutor
    store_name, sub, mode = p.get("store", "store"), p.get("store_sub", "store"), p.get("mode", "full")
    if store_name:
        _reload(store_name)
    items = p["items"]
    # the payload says how many workers (the class's physical cores): os.cpu_count() in a container reports the HOST's CPUs
    workers = max(1, min(int(p.get("workers") or 1), len(items)))
    t0 = time.time()
    for net in sorted({it["sysdef"]["network"] for it in items}):
        _engine(net)                          # built once here; forked workers inherit it
    if workers == 1:
        _sim_worker_init(int(p.get("threads", 1)))
        results = [_sim_item((it, store_name, sub, mode)) for it in items]
    else:
        # fork (the Phase 3 containers' pools did the same): the children inherit the imported engine code; they end with os._exit
        with ProcessPoolExecutor(max_workers=workers, mp_context=mp.get_context("fork"), initializer=_sim_worker_init,
                                 initargs=(int(p.get("threads", 1)),)) as ex:
            results = list(ex.map(_sim_item, [(it, store_name, sub, mode) for it in items]))
    if store_name and any(r.get("computed") for r in results):
        _commit(store_name)
    return {"results": results, "n": len(items), "workers": workers, "batch_wall_s": round(time.time() - t0, 2)}


# ------------------------------------------------------------------------------------------------ subprocess jobs
def _subst(obj, table: dict):
    if isinstance(obj, str):
        for k, v in table.items():
            obj = obj.replace(k, v)
        return obj
    if isinstance(obj, list):
        return [_subst(x, table) for x in obj]
    if isinstance(obj, dict):
        return {k: _subst(v, table) for k, v in obj.items()}
    return obj


def methods_dir(key: str) -> Path:
    """The method snapshot `key` (a tar on the fit volume at /fitvol/methods/<key>.tar), extracted once per container; returns the
    directory that contains the snapshot's top-level package(s)."""
    d = WORK / "methods" / key
    if not (d / ".complete").exists():
        tarp = MOUNTS["fit"] / "methods" / f"{key}.tar"
        if not tarp.exists():
            _reload("fit")
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        with tarfile.open(tarp) as tf:
            tf.extractall(d / "pkg", filter="data")
        (d / ".complete").write_text("ok", encoding="utf-8")
    return d / "pkg"


def _leave_host(crashes: list, what: str) -> None:
    """Crashes follow the host: end this container, so that Modal's retry policy re-runs the input in a fresh one."""
    print(f"[p4modal] {what} killed by a signal {len(crashes)} times in this container; leaving the host: "
          + json.dumps(crashes)[-3000:], file=sys.stderr, flush=True)
    os._exit(75)


def _subprocess(job: dict, jd: Path, env: dict, timeout_s: float) -> dict:
    jf, of = jd / "job.json", jd / "result.pkl"
    jf.write_text(json.dumps(job), encoding="utf-8")
    env = dict(env, PYTHONFAULTHANDLER="1")
    cmd = [sys.executable, "-m", "brainir_causal.p4modal.jobproc", str(jf), str(of)]
    crashes = []
    for _attempt in range(1 + SIGNAL_RETRIES):
        if of.exists():
            of.unlink()
        try:
            pr = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout_s, cwd=str(jd))
        except subprocess.TimeoutExpired as e:
            return {"error": f"timeout after {timeout_s:.0f} s", "stderr_tail": (e.stderr or "")[-4000:] if isinstance(e.stderr, str) else ""}
        if pr.returncode < 0:
            crashes.append({"returncode": pr.returncode, "stderr_tail": pr.stderr[-3000:]})
            continue
        if pr.returncode != 0 or not of.exists():
            return {"error": f"job exit {pr.returncode}", "stderr_tail": pr.stderr[-6000:], "stdout_tail": pr.stdout[-2000:],
                    "signal_crashes": crashes}
        with open(of, "rb") as fh:
            res = pickle.load(fh)
        res["stdout_tail"] = pr.stdout[-2000:]
        res["stderr_tail"] = pr.stderr[-2000:]
        if crashes:
            res["signal_crashes"] = crashes
        return res
    _leave_host(crashes, "job process")
    return {"error": "unreachable"}


def _base_env(threads: int, tmp: Path, pythonpath: str) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MODAL", "P4M_"))}
    env.update({"PYTHONPATH": pythonpath, "TMPDIR": str(tmp), "TEMP": str(tmp), "TMP": str(tmp), "OMP_NUM_THREADS": str(threads),
                "MKL_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads), "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def _collect(jd: Path, patterns: list[str], cap: int = 1024 * 1024 * 1024) -> dict:
    out, total = {}, 0
    for pat in patterns or []:
        for f in sorted(jd.glob(pat)):
            if f.is_file():
                b = f.read_bytes()
                total += len(b)
                if total > cap:
                    raise RuntimeError(f"job outputs exceed {cap} bytes")
                out[f.relative_to(jd).as_posix()] = b
    return out


@with_mem
def run_call(p: dict) -> dict:
    """payload: {"target": "module:function", "args", "kwargs", "threads", "timeout_s", "inputs": {rel: bytes}, "outputs": [globs],
    "links": {container path: container path}, "reload": [volume names], "commit": [volume names]}. No guard (orchestrator code only)."""
    for v in p.get("reload") or []:
        _reload(v)
    for dst, src in (p.get("links") or {}).items():
        d = Path(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        if not d.exists() and not d.is_symlink():
            d.symlink_to(src)
    jd = WORK / "jobs" / (p.get("job_id") or uuid.uuid4().hex)
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "tmp").mkdir(parents=True)
    for rel, blob in (p.get("inputs") or {}).items():
        (jd / rel).parent.mkdir(parents=True, exist_ok=True)
        (jd / rel).write_bytes(blob)
    table = {"$JOB": str(jd)}
    job = {"target": p["target"], "args": _subst(p.get("args") or [], table), "kwargs": _subst(p.get("kwargs") or {}, table),
           "threads": int(p.get("threads", 2))}
    res = _subprocess(job, jd, _base_env(int(p.get("threads", 2)), jd / "tmp", BASE_PYTHONPATH), float(p.get("timeout_s", 7200)))
    res["files"] = _collect(jd, p.get("outputs") or [])
    for v in p.get("commit") or []:
        _commit(v)
    shutil.rmtree(jd, ignore_errors=True)
    return res


class VolumeStoreBackend:
    """The `remote_backend` of a per-job brainir_causal.simservice.SimServer inside a container: real FULL-network jobs are served from
    the volume store, else simulated in this process and written to it (committed by the caller after the job). Returns what
    simservice.finish_remote_job returns (one per job, or the exception)."""

    def __init__(self, vstore: VolumeStore):
        self.vstore = vstore
        self.n_computed = 0

    def __call__(self, jobs: list[dict]) -> list:
        from brainir_causal.simservice import finish_remote_job
        out = []
        for job in jobs:
            try:
                _, rec, computed = sim_record(job["sysdef"], job["protocol"], self.vstore, local_root=job.get("store_root"),
                                              meta={"source": "fit-simservice"})
                self.n_computed += int(computed)
                out.append(finish_remote_job(job, rec))
            except Exception as e:  # noqa: BLE001
                out.append(e)
        return out


class _JobSim:
    """A per-job simulation service (brainir_causal.simservice.SimServer) on a queue inside the job directory, served from a thread of
    THIS process; worker processes are started before the guard variables exist."""

    def __init__(self, root: Path, spec: dict, vstore: VolumeStore | None):
        from brainir_causal.simservice import SimServer
        self.backend = VolumeStoreBackend(vstore) if vstore is not None else None
        self.server = SimServer(root, spec["systems"], root / "store", bundle=BUNDLE, budgets=spec.get("budgets"),
                                default_budget=int(spec.get("budget", 0)), workers=int(spec.get("workers", 2)),
                                public_keys=spec.get("public_keys"), remote_backend=self.backend, ledger_dir=root / "ledger")
        if hasattr(self.server.pool, "submit"):
            self.server.pool.submit(int, 0).result()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        q = self.server.q / "requests"
        while not self.stop.is_set():
            for f in sorted(q.glob("*.json")):
                try:
                    self.server.handle(f)
                except Exception:  # noqa: BLE001
                    import traceback
                    traceback.print_exc()
            time.sleep(0.1)

    def close(self) -> dict:
        self.stop.set()
        self.thread.join(timeout=10)
        try:
            self.server.pool.shutdown(wait=False, cancel_futures=True)
        except Exception:  # noqa: BLE001
            pass
        led = self.server.ledger_path
        return {"ledger": json.loads(led.read_text(encoding="utf-8")) if led.exists() else {},
                "remote_computed": self.backend.n_computed if self.backend else 0}


@with_mem
def run_method(p: dict) -> dict:
    """A guarded subprocess job. payload:
      target "module:function" (orchestrator code that imports and runs the method), args / kwargs (strings may use $JOB, $METHODS,
      $SIMQ), guard "fit" | "eval", methods_key (snapshot tar on the fit volume; its directory is put on the PYTHONPATH and, in eval
      mode, is the method code the guard watches), allowed [container paths the job may read / write besides its own directory and the
      snapshot], links {container path: container path} (made before the guard, e.g. fit views), inputs {rel: bytes}, tars {rel: bytes}
      (extracted into the job directory), outputs [globs relative to the job directory], sim {"systems", "budget" | "budgets",
      "public_keys", "workers", "store": "store" | None} (a per-job simulation service), threads, timeout_s."""
    t0 = time.time()
    jd = WORK / "jobs" / (p.get("job_id") or uuid.uuid4().hex)
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "tmp").mkdir(parents=True)
    for rel, blob in (p.get("inputs") or {}).items():
        (jd / rel).parent.mkdir(parents=True, exist_ok=True)
        (jd / rel).write_bytes(blob)
    for rel, blob in (p.get("tars") or {}).items():
        (jd / rel).mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
            tf.extractall(jd / rel, filter="data")
    for dst, src in (p.get("links") or {}).items():
        d = Path(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        if not d.exists() and not d.is_symlink():
            d.symlink_to(src)
    for v in p.get("reload") or ["fit"]:
        _reload(v)
    mdir = methods_dir(p["methods_key"]) if p.get("methods_key") else None
    sim, sim_rec = None, None
    if p.get("sim"):
        vs = None
        if p["sim"].get("store"):
            _reload(p["sim"]["store"])
            vs = VolumeStore(MOUNTS[p["sim"]["store"]] / "store", p["sim"]["store"])
        sim = _JobSim(jd / "simroom", p["sim"], vs)
    table = {"$JOB": str(jd), "$METHODS": str(mdir) if mdir else "", "$SIMQ": str(sim.server.q) if sim else ""}
    job = {"target": p["target"], "args": _subst(p.get("args") or [], table), "kwargs": _subst(p.get("kwargs") or {}, table),
           "threads": int(p.get("threads", 3))}
    threads = int(p.get("threads", 3))
    mode = p.get("guard")
    pypath = BASE_PYTHONPATH + (os.pathsep + str(mdir) if mdir else "")
    if mode in ("fit", "eval"):
        pypath = SITE + os.pathsep + pypath
    env = _base_env(threads, jd / "tmp", pypath)
    if mode in ("fit", "eval"):
        allowed = [str(jd)] + ([str(mdir.parent)] if mdir else []) + [str(a) for a in _subst(p.get("allowed") or [], table)]
        if sim is not None:
            allowed.append(str(sim.server.q))
        mdirs = ([str(mdir)] if mdir else []) + [str(x) for x in _subst(p.get("method_dirs") or [], table)]
        env.update({"P4M_GUARD_MODE": mode, "P4M_ALLOWED": os.pathsep.join(allowed), "P4M_METHOD_DIRS": os.pathsep.join(mdirs)})
    try:
        res = _subprocess(job, jd, env, float(p.get("timeout_s", 3600)))
    finally:
        if sim is not None:
            sim_rec = sim.close()
            if p["sim"].get("store") and sim_rec.get("remote_computed"):
                _commit(p["sim"]["store"])
    res["files"] = _collect(jd, p.get("outputs") or [])
    if sim_rec is not None:
        res["sim"] = sim_rec
    res["job_wall_s"] = round(time.time() - t0, 2)
    shutil.rmtree(jd, ignore_errors=True)
    return res


# ------------------------------------------------------------------------------------------------ volume utilities
def run_extract(p: dict) -> dict:
    """Unpack /<volume>/_incoming/<name> into /<volume>/<dest> and commit that volume."""
    t0 = time.time()
    root = MOUNTS[p["volume"]]
    _reload(p["volume"])
    src, dest = root / "_incoming" / p["name"], root / p["dest"]
    if dest.exists() and p.get("replace", True):
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(src) as tf:
        tf.extractall(dest, filter="data")
    n = sum(1 for q in dest.rglob("*") if q.is_file())
    src.unlink()
    _commit(p["volume"])
    return {"extracted_files": n, "dest": str(dest), "container_wall_s": round(time.time() - t0, 1)}


def run_hashes(p: dict) -> dict:
    """sha256 and size of the listed files under /<volume>/<dir> (transfer checks)."""
    _reload(p["volume"])
    base = MOUNTS[p["volume"]] / p["dir"]
    out = {}
    for n in p["names"]:
        f = base / n
        h = hashlib.sha256()
        with open(f, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        out[n] = {"sha256": h.hexdigest(), "bytes": f.stat().st_size}
    return {"hashes": out}


def run_fetch(p: dict) -> dict:
    """Record bytes of the given store keys from a store volume (keys that are absent map to None)."""
    _reload(p.get("volume", "store"))
    vs = VolumeStore(MOUNTS[p.get("volume", "store")] / p.get("store_sub", "store"), p.get("volume", "store"))
    return {"records": {k: vs.get_bytes(k) for k in p["keys"]}}


def dispatch(p: dict) -> dict:
    kind = p.get("kind")
    fn = {"sim": run_sim, "call": run_call, "method": run_method, "extract": run_extract, "hashes": run_hashes, "fetch": run_fetch}.get(kind)
    if fn is None:
        raise ValueError(f"unknown job kind {kind!r}")
    return fn(p)
