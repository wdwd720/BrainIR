"""Container side of the Modal tournament backend (runs in the Modal image; see scripts/p3/modal_tournament.py).

Three job kinds, each run in a FRESH Python subprocess, so method packages of different rounds never share an interpreter:
- fit: the frozen sandboxed fit (brainir_state.suite_eval.fit_sandboxed) on a public fit view. The container that fits never mounts
  the held-out data (only the fit-data volume: fit views + method snapshots). If the round gives fits a simulator, a simulation service
  with the round's per-fit budget runs in this process; the system definitions stay in memory.
- eval / repro: the frozen evaluation workers (evaluate_model_job / reproducibility_job) with the held-out suite on the eval volume.
- refs: the frozen reference controls (reference_results) of one (system, k); no method code.
Every method subprocess also installs the Linux guard (p3modal.guard via sitecustomize).
"""

from __future__ import annotations

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
from pathlib import Path

WORK = Path("/tmp/p3m")
FITVOL = Path("/fitvol")
EVALVOL = Path("/evalvol")
SUB_PYTHONPATH = os.pathsep.join(["/repo/p3modal_site", "/repo/phase3/src", "/repo/p3modal"])
FIT_VOLUME_NAME = "brainir-p3-fit"


class MemPeak:
    """Peak memory of the CONTAINER while a job runs (cgroup counters sampled every 0.25 s): the per-job-kind sizing input of the
    Modal resource classes (the orchestrator's request: containers sized from measured needs)."""

    FILES = ("/sys/fs/cgroup/memory.current", "/sys/fs/cgroup/memory/memory.usage_in_bytes")

    def __init__(self):
        import threading
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
    """Decorator: run a job function under MemPeak and add peak_container_mb to its dict result."""
    import functools

    @functools.wraps(fn)
    def wrapped(p):
        with MemPeak() as mp:
            res = fn(p)
        if isinstance(res, dict):
            res["peak_container_mb"] = mp.mb
        return res
    return wrapped


def _reload_fitvol() -> None:
    try:
        import modal
        modal.Volume.from_name(FIT_VOLUME_NAME).reload()
    except Exception:  # noqa: BLE001
        pass


def methods_dir(key: str) -> Path:
    """The method snapshot `key` (a tar on the fit volume), extracted once per container."""
    d = WORK / "methods" / key
    if not (d / ".complete").exists():
        tarp = FITVOL / "methods" / f"{key}.tar"
        if not tarp.exists():
            _reload_fitvol()
        if d.exists():
            shutil.rmtree(d)
        d.mkdir(parents=True)
        with tarfile.open(tarp) as tf:
            tf.extractall(d, filter="data")
        (d / ".complete").write_text("ok", encoding="utf-8")
    return d / "methods"


def _untar_bytes(blob: bytes, dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob)) as tf:
        tf.extractall(dest, filter="data")
    return dest


def _write_model(files: dict, dest_dir: Path, name: str) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    p = dest_dir / f"{name}.pkl"
    p.write_bytes(files["pkl"])
    if files.get("json") is not None:
        p.with_suffix(".json").write_bytes(files["json"])
    return p


def _sub_env(mode: str, allowed: list[Path], method_dirs: list[Path], tmp: Path, threads: int = 3) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MODAL", "P3M_"))}
    env.update({"PYTHONPATH": SUB_PYTHONPATH, "P3M_GUARD_MODE": mode, "P3M_ALLOWED": os.pathsep.join(str(a) for a in allowed),
                "P3M_METHOD_DIRS": os.pathsep.join(str(m) for m in method_dirs), "TMPDIR": str(tmp), "TEMP": str(tmp), "TMP": str(tmp),
                "OMP_NUM_THREADS": str(threads), "MKL_NUM_THREADS": str(threads), "OPENBLAS_NUM_THREADS": str(threads),
                "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    return env


def _suite_spec(spec: dict) -> dict:
    tier = spec["tier"]
    out = dict(spec)
    out["public_dir"] = str(EVALVOL / "suites" / tier / "public")
    out["truth_dir"] = str(EVALVOL / "suites" / tier / "truth") if spec.get("truth_dir") else None
    return out


# ------------------------------------------------------------------------------------------------ simulation service (fits)
class _Sim:
    """The frozen simulation service (brainir_state.simservice.SimServer) on a private queue, served from a thread; stopped after
    the fit."""

    def __init__(self, root: Path, systems: dict, budget: int):
        from brainir_state.simservice import SimServer
        (root / "store").mkdir(parents=True, exist_ok=True)
        self.server = SimServer(root, systems, Path("/nonexistent-bundle"), root / "store", {}, int(budget), 2)
        # start the worker processes now (fork), before the fit's guard variables are set in this process's environment
        self.server.pool.submit(int, 0).result()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def _loop(self):
        q = self.server.q / "requests"
        while not self.stop.is_set():
            for p in sorted(q.glob("*.json")):
                try:
                    self.server.handle(p)
                except Exception:  # noqa: BLE001
                    import traceback
                    traceback.print_exc()
            time.sleep(0.2)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=10)
        self.server.pool.shutdown(wait=False, cancel_futures=True)


# ------------------------------------------------------------------------------------------------ job kinds
@with_mem
def run_fit(p: dict) -> dict:
    from brainir_state.suite_eval import fit_sandboxed
    t0 = time.time()
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "tmp").mkdir(parents=True)
    mdir = methods_dir(p["methods_key"])
    datasets, allowed = [], [jd, mdir.parent]
    for i, d in enumerate(p["datasets"]):
        if d["kind"] == "view":
            v = FITVOL / "views" / d["tier"]
            if not (v / "manifest.json").exists():
                _reload_fitvol()
            datasets.append(v)
            allowed.append(v)
        else:
            datasets.append(_untar_bytes(d["tar"], jd / f"ds{i}"))
    adapt = _write_model(p["adapt_from"], jd / "base", "base") if p.get("adapt_from") else None
    sim = None
    if p.get("sim"):
        sim = _Sim(jd / "sim", p["sim"]["systems"], p["sim"]["budget"])
    out = jd / "out" / f"{p['stem']}.pkl"
    # fit_sandboxed passes this process's environment (minus MODAL* keys) to the fit subprocess: set the guard's keys for the call
    # only, without touching the rest (the Modal runtime of this process keeps its own variables)
    extra = {k: v for k, v in _sub_env("fit", allowed, [mdir], jd / "tmp").items() if k not in os.environ or os.environ[k] != v}
    extra["PYTHONFAULTHANDLER"] = "1"
    saved = {k: os.environ.get(k) for k in extra}
    crashes = []
    try:
        os.environ.update(extra)
        for _attempt in range(1 + SIGNAL_RETRIES):
            rec = fit_sandboxed(mdir, p["method"], datasets, p["systems"], out, config=p.get("config"), seed=int(p["seed"]),
                                sim_queue=(sim.server.q if sim else None), adapt_from=adapt, threads=3, timeout_s=float(p["timeout_s"]))
            err = str(rec.get("error", "")) if isinstance(rec, dict) else ""
            if err.startswith("exit -"):
                # the fit process was killed by a signal (an infrastructure fault): recorded, re-run with a fresh budget
                crashes.append({"error": err, "stderr_tail": str(rec.get("stderr", ""))[-3000:]})
                for q in (out, out.with_suffix(".json"), out.with_suffix(".error.json")):
                    if q.exists():
                        q.unlink()
                if sim is not None:
                    sim.close()
                    sim = _Sim(jd / f"sim{len(crashes)}", p["sim"]["systems"], p["sim"]["budget"])
                continue
            break
        else:
            _leave_host(crashes, "fit process")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if sim is not None:
            sim.close()
    if crashes and isinstance(rec, dict):
        rec["signal_crashes"] = crashes
    res = {"rec": rec, "pkl": out.read_bytes() if out.exists() else None,
           "json": out.with_suffix(".json").read_bytes() if out.with_suffix(".json").exists() else None,
           "error_json": out.with_suffix(".error.json").read_bytes() if out.with_suffix(".error.json").exists() else None,
           "container_wall_s": round(time.time() - t0, 1)}
    shutil.rmtree(jd, ignore_errors=True)
    return res


SIGNAL_RETRIES = 1      # a worker killed by a signal (an infrastructure fault) is re-run once in the container; crashes follow the
#                         host (research/phase3/level_c/modal_pinning_crash_experiment.json), so the input then moves to another
#                         container through Modal's retry policy (modal_tournament.make_app, max_retries 3)


class WorkerCrashed(RuntimeError):
    """A worker kept crashing in this container (kept for callers that catch it)."""


def _leave_host(crashes: list, what: str) -> None:
    """Crashes follow the host: end this CONTAINER (not only the input), so that Modal re-runs the input in a fresh container
    (retry policy, modal_tournament.make_app). The crash record goes to the container log."""
    print(f"[p3modal] {what} killed by a signal {len(crashes)} times in this container; leaving the host: "
          + json.dumps(crashes)[-3000:], file=sys.stderr, flush=True)
    os._exit(75)


def _run_worker(kind: str, job: dict, jd: Path, env: dict, timeout_s: float) -> dict:
    jf, of = jd / "job.json", jd / "result.pkl"
    jf.write_text(json.dumps(job), encoding="utf-8")
    env = dict(env, PYTHONFAULTHANDLER="1")     # a native crash (e.g. SIGSEGV) prints the Python stack to stderr (diagnostics only)
    cmd = [sys.executable, "-m", "p3modal.evaljob", kind, str(jf), str(of)]
    crashes = []
    for _attempt in range(1 + SIGNAL_RETRIES):
        if of.exists():
            of.unlink()
        try:
            pr = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout_s, cwd=str(jd))
        except subprocess.TimeoutExpired:
            return {"error": f"evaluation timeout after {timeout_s:.0f} s"}
        if pr.returncode < 0:
            # killed by a signal (the computation is deterministic, so a re-run gives the same result): recorded, re-run
            crashes.append({"returncode": pr.returncode, "stderr_tail": pr.stderr[-3000:]})
            print(f"[p3modal] worker killed by signal {-pr.returncode}; re-running ({len(crashes)})", file=sys.stderr, flush=True)
            continue
        if pr.returncode != 0 or not of.exists():
            return {"error": f"evaluation worker exit {pr.returncode}", "stderr": pr.stderr[-4000:], "signal_crashes": crashes}
        with open(of, "rb") as fh:
            res = pickle.load(fh)
        if crashes and isinstance(res, dict):
            res["signal_crashes"] = crashes
        return res
    _leave_host(crashes, "worker")
    return {"error": "unreachable"}


@with_mem
def run_eval(p: dict) -> dict:
    """kind eval (one model) or repro (several models of one method); the result of the frozen worker, unchanged."""
    t0 = time.time()
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "tmp").mkdir(parents=True)
    mdir = methods_dir(p["methods_key"])
    job = dict(p["job"])
    job["suite"] = _suite_spec(job["suite"])
    job["method_dir"] = str(mdir)
    mdl = jd / "model"
    if p["kind"] == "eval":
        job["model_path"] = str(_write_model(p["models"][0], mdl, "m0"))
    else:
        job["model_paths"] = [str(_write_model(m, mdl, f"m{i}")) for i, m in enumerate(p["models"])]
    env = _sub_env("eval", [mdl, mdir.parent, jd / "tmp"], [mdir], jd / "tmp", threads=int(p.get("threads", 3)))
    env["PYTHONPATH"] = SUB_PYTHONPATH
    res = _run_worker(p["kind"], job, jd, env, float(p.get("timeout_s", 5400)))
    res["container_wall_s"] = round(time.time() - t0, 1)
    shutil.rmtree(jd, ignore_errors=True)
    return res


@with_mem
def run_call(p: dict) -> dict:
    """An orchestrator function (no method code) in a fresh subprocess: module.func(*args), with /repo/scripts/p3 importable and the
    requested data links (e.g. /repo/data/phase3/synthetic_dev -> the eval volume's dev suite)."""
    t0 = time.time()
    for dst, src in (p.get("links") or {}).items():
        d = Path(dst)
        d.parent.mkdir(parents=True, exist_ok=True)
        if not d.exists() and not d.is_symlink():
            d.symlink_to(src)
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    jd.mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MODAL", "P3M_"))}
    # orchestrator functions only (no method code): the frozen library /repo/src is importable (the real engine needs it)
    env.update({"PYTHONPATH": SUB_PYTHONPATH + os.pathsep + "/repo/scripts/p3" + os.pathsep + "/repo/src", "OMP_NUM_THREADS": "3", "MKL_NUM_THREADS": "3",
                "OPENBLAS_NUM_THREADS": "3"})
    for k in p.get("env_drop") or []:             # diagnostics only (the numerics-pinning experiment of benchmark version 3)
        env.pop(k, None)
    res = _run_worker("call", {"module": p["module"], "func": p["func"], "args": p.get("args") or []}, jd, env, float(p.get("timeout_s", 7200)))
    shutil.rmtree(jd, ignore_errors=True)
    if "error" in res and "result" not in res:
        return {"error": res["error"], "stderr": res.get("stderr"), "container_wall_s": round(time.time() - t0, 1)}
    return {"result": res.get("result"), "signal_crashes": res.get("signal_crashes"), "container_wall_s": round(time.time() - t0, 1)}


def run_call_commit(p: dict) -> dict:
    """run_call for orchestrator functions that WRITE to the eval volume (the hidden real data generator, benchmark version 3): the
    volume is reloaded before the call (to see other containers' commits) and committed after it."""
    import modal
    vol = modal.Volume.from_name("brainir-p3-eval")
    vol.reload()
    res = run_call(p)
    vol.commit()
    return res


def run_extract(p: dict) -> dict:
    """Unpack an uploaded tar (/evalvol/_incoming/<name>) into its destination on the eval volume and commit the volume (a tar upload
    is much faster than thousands of small files over a slow uplink)."""
    import modal
    t0 = time.time()
    src, dest = EVALVOL / "_incoming" / p["name"], EVALVOL / p["dest"]
    vol = modal.Volume.from_name("brainir-p3-eval")
    vol.reload()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(src) as tf:
        tf.extractall(dest, filter="data")
    n = sum(1 for q in dest.rglob("*") if q.is_file())
    src.unlink()
    vol.commit()
    return {"extracted_files": n, "dest": str(dest), "container_wall_s": round(time.time() - t0, 1)}


@with_mem
def run_refs(p: dict) -> dict:
    """The frozen reference controls of one (system, k) on the held-out suite; returns the cache files written."""
    t0 = time.time()
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "cache").mkdir(parents=True)
    # already computed cache files of this system (the k-independent controls), so that a (system, k) job computes only what is
    # missing (the frozen reference_results reads its cache first)
    for name, data in (p.get("seed_files") or {}).items():
        (jd / "cache" / Path(name).name).write_bytes(data)
    job = {"suite": _suite_spec(p["suite"]), "sid": p["sid"], "k": int(p["k"]), "cache_dir": str(jd / "cache"), "seed": int(p.get("seed", 0))}
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MODAL", "P3M_"))}
    env.update({"PYTHONPATH": SUB_PYTHONPATH, "OMP_NUM_THREADS": "3", "MKL_NUM_THREADS": "3", "OPENBLAS_NUM_THREADS": "3"})
    res = _run_worker("refs", job, jd, env, float(p.get("timeout_s", 5400)))
    seeded = set((p.get("seed_files") or {}).keys())
    files = {f.name: f.read_bytes() for f in (jd / "cache").glob("*.json") if f.name not in seeded}
    out = {"files": files, "error": res.get("error"), "stderr": res.get("stderr"), "container_wall_s": round(time.time() - t0, 1)}
    shutil.rmtree(jd, ignore_errors=True)
    return out


# ================================================================================================================================
# Level C on Modal (benchmark version 3). Real-circuit variants of the job kinds above; everything above is unchanged.
# - Fits read the PUBLIC real fit view on the FIT volume (/fitvol/views/real). Limited and half-sample views are SUBVIEWS: lists of
#   trajectory keys of that view, linked into the job directory, so no trajectory data travels with the call. The simulation service
#   of a fit uses the public blind bundle on the fit volume (/fitvol/bundles/dng100_public_blind); its system definitions come in the
#   payload without the held-out target lists.
# - Evaluations read the public view (train / val rows: normalisers, G alignment) and the HIDDEN real data, which live only on the
#   EVAL volume (/evalvol/suites/<name>/hidden, /evalvol/suites/real_internal/systems_internal.json). Fit containers never mount it.
# ================================================================================================================================
BUNDLE_DIR = FITVOL / "bundles" / "dng100_public_blind"
REAL_INTERNAL = EVALVOL / "suites" / "real_internal" / "systems_internal.json"


def run_extract_any(p: dict) -> dict:
    """Unpack /<volume>/_incoming/<name> into /<volume>/<dest> (volume 'fit' or 'eval') and commit that volume."""
    import modal
    t0 = time.time()
    root, vname = (FITVOL, FIT_VOLUME_NAME) if p["volume"] == "fit" else (EVALVOL, "brainir-p3-eval")
    vol = modal.Volume.from_name(vname)
    vol.reload()
    src, dest = root / "_incoming" / p["name"], root / p["dest"]
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    with tarfile.open(src) as tf:
        tf.extractall(dest, filter="data")
    n = sum(1 for q in dest.rglob("*") if q.is_file())
    src.unlink()
    vol.commit()
    return {"extracted_files": n, "dest": str(dest), "container_wall_s": round(time.time() - t0, 1)}


class _SimBundle(_Sim):
    """_Sim with the real engine's bundle (real-circuit simulations need the network files)."""

    def __init__(self, root: Path, systems: dict, budget: int, bundle: Path):
        from brainir_state.simservice import SimServer
        (root / "store").mkdir(parents=True, exist_ok=True)
        self.server = SimServer(root, systems, bundle, root / "store", {}, int(budget), 2)
        self.server.pool.submit(int, 0).result()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()


def _subview(d: dict, dest: Path) -> tuple[Path, Path]:
    """A fit view made of some rows of a view on the fit volume: index and manifest from the payload, trajectory files as symlinks into
    the base view. Returns (view directory, base view directory); the guard must allow both (links resolve to their targets)."""
    base = FITVOL / "views" / d["base"]
    if not (base / "manifest.json").exists():
        _reload_fitvol()
    (dest / "traj").mkdir(parents=True, exist_ok=True)
    for key in d["keys"]:
        (dest / "traj" / f"{key}.npz").symlink_to(base / "traj" / f"{key}.npz")
    (dest / "index.jsonl").write_text(d["index"], encoding="utf-8")
    (dest / "manifest.json").write_text(d["manifest"], encoding="utf-8")
    return dest, base


@with_mem
def run_fit_real(p: dict) -> dict:
    """run_fit for the real suite: datasets of kind view / tar / subview, and a simulation service with the bundle."""
    from brainir_state.suite_eval import fit_sandboxed
    t0 = time.time()
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "tmp").mkdir(parents=True)
    mdir = methods_dir(p["methods_key"])
    datasets, allowed = [], [jd, mdir.parent]
    for i, d in enumerate(p["datasets"]):
        if d["kind"] == "view":
            v = FITVOL / "views" / d["tier"]
            if not (v / "manifest.json").exists():
                _reload_fitvol()
            datasets.append(v)
            allowed.append(v)
        elif d["kind"] == "subview":
            v, base = _subview(d, jd / f"ds{i}")
            datasets.append(v)
            allowed.append(base)
        else:
            datasets.append(_untar_bytes(d["tar"], jd / f"ds{i}"))
    adapt = _write_model(p["adapt_from"], jd / "base", "base") if p.get("adapt_from") else None
    sim = None
    if p.get("sim"):
        if not (BUNDLE_DIR / "manifest.json").exists():
            _reload_fitvol()
        sim = _SimBundle(jd / "sim", p["sim"]["systems"], p["sim"]["budget"], BUNDLE_DIR)
    out = jd / "out" / f"{p['stem']}.pkl"
    extra = {k: v for k, v in _sub_env("fit", allowed, [mdir], jd / "tmp").items() if k not in os.environ or os.environ[k] != v}
    extra["PYTHONFAULTHANDLER"] = "1"
    saved = {k: os.environ.get(k) for k in extra}
    crashes = []
    try:
        os.environ.update(extra)
        for _attempt in range(1 + SIGNAL_RETRIES):
            rec = fit_sandboxed(mdir, p["method"], datasets, p["systems"], out, config=p.get("config"), seed=int(p["seed"]),
                                sim_queue=(sim.server.q if sim else None), adapt_from=adapt, threads=3, timeout_s=float(p["timeout_s"]))
            err = str(rec.get("error", "")) if isinstance(rec, dict) else ""
            if err.startswith("exit -"):
                # killed by a signal (an infrastructure fault): recorded, re-run with a fresh simulation budget
                crashes.append({"error": err, "stderr_tail": str(rec.get("stderr", ""))[-3000:]})
                for q in (out, out.with_suffix(".json"), out.with_suffix(".error.json")):
                    if q.exists():
                        q.unlink()
                if sim is not None:
                    sim.close()
                    sim = _SimBundle(jd / f"sim{len(crashes)}", p["sim"]["systems"], p["sim"]["budget"], BUNDLE_DIR)
                continue
            break
        else:
            _leave_host(crashes, "fit process")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if sim is not None:
            sim.close()
    if crashes and isinstance(rec, dict):
        rec["signal_crashes"] = crashes
    res = {"rec": rec, "pkl": out.read_bytes() if out.exists() else None,
           "json": out.with_suffix(".json").read_bytes() if out.with_suffix(".json").exists() else None,
           "error_json": out.with_suffix(".error.json").read_bytes() if out.with_suffix(".error.json").exists() else None,
           "container_wall_s": round(time.time() - t0, 1)}
    shutil.rmtree(jd, ignore_errors=True)
    return res


def _suite_spec_real(spec: dict) -> dict:
    """The real suite spec with container paths: public_dir = the public fit view (its train / val rows are all the evaluator reads from
    the public data), hidden / micro = the hidden data on the eval volume, the internal system definitions and the bundle."""
    out = dict(spec)
    view = FITVOL / "views" / spec.get("modal_view", "real")
    hid = EVALVOL / "suites" / spec.get("modal_hidden", "real") / "hidden"
    if not (view / "manifest.json").exists():
        _reload_fitvol()
    out.update(public_dir=str(view), hidden_dir=str(hid), micro_dir=str(hid), systems_internal=str(REAL_INTERNAL), bundle=str(BUNDLE_DIR))
    return out


def _code_tag() -> str | None:
    try:
        from brainir_state.suite_eval import evaluator_code_tag
        return evaluator_code_tag()
    except Exception:  # noqa: BLE001
        return None


def eval_real_inproc(kind: str, job: dict) -> dict:
    """Worker body (fresh subprocess with the EVAL guard): imports the real engine's library chain BEFORE any method code runs (the
    import system must list /repo/src while no method frame is on the stack; lifting on real systems simulates through it), then runs
    the frozen worker unchanged."""
    import brainir_state.realsim  # noqa: F401
    from brainir_state.suite_eval import evaluate_model_job, limit_threads, reproducibility_job
    limit_threads(3)
    return evaluate_model_job(job) if kind == "eval_real" else reproducibility_job(job)


@with_mem
def run_eval_real(p: dict) -> dict:
    """kind eval_real / repro_real: the frozen worker on the real suite (hidden data from the eval volume)."""
    t0 = time.time()
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "tmp").mkdir(parents=True)
    mdir = methods_dir(p["methods_key"])
    job = dict(p["job"])
    job["suite"] = _suite_spec_real(job["suite"])
    job["method_dir"] = str(mdir)
    mdl = jd / "model"
    if p["kind"] == "eval_real":
        job["model_path"] = str(_write_model(p["models"][0], mdl, "m0"))
    else:
        job["model_paths"] = [str(_write_model(m, mdl, f"m{i}")) for i, m in enumerate(p["models"])]
    env = _sub_env("eval", [mdl, mdir.parent, jd / "tmp"], [mdir], jd / "tmp", threads=int(p.get("threads", 3)))
    env["PYTHONPATH"] = SUB_PYTHONPATH + os.pathsep + "/repo/src"
    w = _run_worker("call", {"module": "p3modal.remote", "func": "eval_real_inproc", "args": [p["kind"], job]}, jd, env,
                    float(p.get("timeout_s", 5400)))
    res = w["result"] if isinstance(w.get("result"), dict) else {"sid": job.get("sid"), "error": w.get("error", "no result"),
                                                                  "stderr": w.get("stderr")}
    res["container_wall_s"] = round(time.time() - t0, 1)
    res["evaluator_code_tag"] = _code_tag()
    shutil.rmtree(jd, ignore_errors=True)
    return res


def refs_real_inproc(spec: dict, sid: str, k: int, cache_dir: str, seed: int = 0) -> dict:
    """Worker body (fresh subprocess, no method code): the frozen reference controls of one real (system, k) into cache_dir."""
    from brainir_state.suite_eval import SuiteData, evaluator_code_tag, reference_results
    s = _suite_spec_real(spec)
    sd = SuiteData(s["public_dir"], kind="real", hidden_dir=s["hidden_dir"], micro_dir=s["micro_dir"])
    reference_results(sd, sid, int(k), Path(cache_dir), seed=int(seed))
    return {"ok": True, "evaluator_code_tag": evaluator_code_tag()}


@with_mem
def run_refs_real(p: dict) -> dict:
    """kind refs_real: reference controls of one real (system, k); returns the cache files written."""
    t0 = time.time()
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "cache").mkdir(parents=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MODAL", "P3M_"))}
    env.update({"PYTHONPATH": SUB_PYTHONPATH, "OMP_NUM_THREADS": "3", "MKL_NUM_THREADS": "3", "OPENBLAS_NUM_THREADS": "3"})
    res = _run_worker("call", {"module": "p3modal.remote", "func": "refs_real_inproc",
                               "args": [p["suite"], p["sid"], int(p["k"]), str(jd / "cache"), int(p.get("seed", 0))]}, jd, env,
                      float(p.get("timeout_s", 5400)))
    files = {f.name: f.read_bytes() for f in (jd / "cache").glob("*.json")}
    out = {"files": files, "error": res.get("error"), "stderr": res.get("stderr"), "result": res.get("result"),
           "container_wall_s": round(time.time() - t0, 1)}
    shutil.rmtree(jd, ignore_errors=True)
    return out
