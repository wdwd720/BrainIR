"""Container side of the post-lock Modal jobs (scripts/p3/counterexamples.py; ORCHESTRATOR SIDE, runs in the Modal image of
scripts/p3/modal_tournament.py).

    counterexample search   one search job (system x strategy x seed) of scripts/p3/counterexamples.py

Each job runs in a FRESH Python subprocess with the Linux method guard in EVAL mode (p3modal.guard via sitecustomize, the same rule as
the frozen evaluation workers): while a frame of the method's code is on the call stack, file events outside the job's own roots,
process creation and network are refused. The orchestrator's simulator and search code run normally. The method snapshot comes from
the fit volume (/fitvol/methods/<key>.tar, shared with the tournament) and the fitted model from /fitvol/models/<key>.pkl (uploaded
once, content-addressed). Nothing hidden is stored on a volume: synthetic suite seeds and real system definitions travel in the job
payload and live only in the job's memory.

    python -m p3modal.postlock cex <job.json> <result.pkl>      (the subprocess entry point)
"""

from __future__ import annotations

import json
import os
import pickle
import shutil
import subprocess
import sys
import time
from pathlib import Path

# the method subprocess's import path: the guard's sitecustomize, the evaluator library, this package, the orchestrator scripts and
# the frozen Phase 1-2 library (the real engine composes the frozen simulator)
EXTRA_PATH = ["/repo/scripts/p3", "/repo/src"]


def _model_dir(key: str, dest: Path) -> Path:
    from p3modal import remote as R
    src = R.FITVOL / "models" / f"{key}.pkl"
    if not src.exists():
        R._reload_fitvol()
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest / "m0.pkl")
    side = src.with_suffix(".json")
    if side.exists():
        shutil.copy2(side, dest / "m0.json")
    return dest / "m0.pkl"


def run_cex(p: dict) -> dict:
    """One counterexample search: {job_id, methods_key, model_key, job, timeout_s, threads} -> the worker's result dict."""
    from p3modal import remote as R
    t0 = time.time()
    jd = R.WORK / "jobs" / p["job_id"]
    shutil.rmtree(jd, ignore_errors=True)
    (jd / "tmp").mkdir(parents=True)
    mdir = R.methods_dir(p["methods_key"])
    model_path = _model_dir(p["model_key"], jd / "model")
    job = dict(p["job"])
    job.update(method_dir=str(mdir), model_path=str(model_path), guard="none")     # the guard is installed by sitecustomize
    env = R._sub_env("eval", [jd / "model", mdir.parent, jd / "tmp"], [mdir], jd / "tmp", threads=int(p.get("threads", 2)))
    env["PYTHONPATH"] = os.pathsep.join([R.SUB_PYTHONPATH, *EXTRA_PATH])
    jf, of = jd / "job.json", jd / "result.pkl"
    jf.write_text(json.dumps(job), encoding="utf-8")
    try:
        pr = subprocess.run([sys.executable, "-m", "p3modal.postlock", "cex", str(jf), str(of)], env=env, capture_output=True, text=True,
                            timeout=float(p.get("timeout_s", 3600)), cwd=str(jd))
        if pr.returncode != 0 or not of.exists():
            res = {"error": f"counterexample worker exit {pr.returncode}", "stderr": pr.stderr[-4000:]}
        else:
            with open(of, "rb") as fh:
                res = pickle.load(fh)
    except subprocess.TimeoutExpired:
        res = {"error": f"counterexample search timeout after {float(p.get('timeout_s', 3600)):.0f} s"}
    res["container_wall_s"] = round(time.time() - t0, 1)
    shutil.rmtree(jd, ignore_errors=True)
    return res


def run_sim(p: dict) -> dict:
    """Simulator-only numerical-equivalence probe (no method code): {job, protocols} -> the readout of every protocol."""
    t0 = time.time()
    for extra in reversed(EXTRA_PATH):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    import counterexamples as CX
    import numpy as np
    sim = CX.make_simulator(p["job"])
    ys = [np.asarray(sim(q)["y"], np.float64) for q in p["protocols"]]
    return {"y": ys, "container_wall_s": round(time.time() - t0, 1)}


def main() -> int:
    kind, job_file, out_file = sys.argv[1:4]
    job = json.loads(Path(job_file).read_text(encoding="utf-8"))
    if kind != "cex":
        raise SystemExit(f"unknown kind {kind}")
    for extra in reversed(EXTRA_PATH):
        if extra not in sys.path:
            sys.path.insert(0, extra)
    import counterexamples as CX
    res = CX.cex_worker(job)
    with open(out_file, "wb") as fh:
        pickle.dump(res, fh)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
