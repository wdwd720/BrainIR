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
    saved = {k: os.environ.get(k) for k in extra}
    try:
        os.environ.update(extra)
        rec = fit_sandboxed(mdir, p["method"], datasets, p["systems"], out, config=p.get("config"), seed=int(p["seed"]),
                            sim_queue=(sim.server.q if sim else None), adapt_from=adapt, threads=3, timeout_s=float(p["timeout_s"]))
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        if sim is not None:
            sim.close()
    res = {"rec": rec, "pkl": out.read_bytes() if out.exists() else None,
           "json": out.with_suffix(".json").read_bytes() if out.with_suffix(".json").exists() else None,
           "error_json": out.with_suffix(".error.json").read_bytes() if out.with_suffix(".error.json").exists() else None,
           "container_wall_s": round(time.time() - t0, 1)}
    shutil.rmtree(jd, ignore_errors=True)
    return res


def _run_worker(kind: str, job: dict, jd: Path, env: dict, timeout_s: float) -> dict:
    jf, of = jd / "job.json", jd / "result.pkl"
    jf.write_text(json.dumps(job), encoding="utf-8")
    cmd = [sys.executable, "-m", "p3modal.evaljob", kind, str(jf), str(of)]
    try:
        pr = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=timeout_s, cwd=str(jd))
    except subprocess.TimeoutExpired:
        return {"error": f"evaluation timeout after {timeout_s:.0f} s"}
    if pr.returncode != 0 or not of.exists():
        return {"error": f"evaluation worker exit {pr.returncode}", "stderr": pr.stderr[-4000:]}
    with open(of, "rb") as fh:
        return pickle.load(fh)


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
    env.update({"PYTHONPATH": SUB_PYTHONPATH + os.pathsep + "/repo/scripts/p3", "OMP_NUM_THREADS": "3", "MKL_NUM_THREADS": "3",
                "OPENBLAS_NUM_THREADS": "3"})
    res = _run_worker("call", {"module": p["module"], "func": p["func"], "args": p.get("args") or []}, jd, env, float(p.get("timeout_s", 7200)))
    shutil.rmtree(jd, ignore_errors=True)
    if "error" in res and "result" not in res:
        return {"error": res["error"], "stderr": res.get("stderr"), "container_wall_s": round(time.time() - t0, 1)}
    return {"result": res.get("result"), "container_wall_s": round(time.time() - t0, 1)}


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


def run_refs(p: dict) -> dict:
    """The frozen reference controls of one (system, k) on the held-out suite; returns the cache files written."""
    t0 = time.time()
    jd = WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "cache").mkdir(parents=True)
    job = {"suite": _suite_spec(p["suite"]), "sid": p["sid"], "k": int(p["k"]), "cache_dir": str(jd / "cache"), "seed": int(p.get("seed", 0))}
    env = {k: v for k, v in os.environ.items() if not k.startswith(("MODAL", "P3M_"))}
    env.update({"PYTHONPATH": SUB_PYTHONPATH, "OMP_NUM_THREADS": "3", "MKL_NUM_THREADS": "3", "OPENBLAS_NUM_THREADS": "3"})
    res = _run_worker("refs", job, jd, env, float(p.get("timeout_s", 5400)))
    files = {f.name: f.read_bytes() for f in (jd / "cache").glob("*.json")}
    out = {"files": files, "error": res.get("error"), "stderr": res.get("stderr"), "container_wall_s": round(time.time() - t0, 1)}
    shutil.rmtree(jd, ignore_errors=True)
    return out
