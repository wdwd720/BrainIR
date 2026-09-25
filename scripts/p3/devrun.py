"""Remote runner for CLEAN-ROOM development experiments on Modal (orchestrator side; LEAKAGE_POLICY.md section 3.2).

    uv run --project phase3 --no-sync python scripts/p3/devrun.py sync-data        # build / verify the dev-data volume (once)
    uv run --project phase3 --no-sync python scripts/p3/devrun.py daemon           # serve the room's request queue (background)
    uv run --project phase3 --no-sync python scripts/p3/devrun.py install-client   # put the client and its notes into the room

Clean-room agents have no Modal access and no credentials. They drop a request (a Python script of their own work area, its
arguments and a resource class) into runs/_remote/queue/requests/ with the client runs/_remote/remote_run.py. This daemon, run by
the orchestrator, validates the request and runs it on Modal:
- the image has the room's pinned numerical stack and NO repository code (the job brings the room's src/ and the requesting
  developer's runs/<prefix>/ as a tar);
- the only volume is `brainir-p3-devdata`, an exact copy of the room's data/ directory (public development data; built server-side
  from the staged public dev suite and public real fit view, the missing public twin files uploaded; every file verified by sha256
  against the room);
- the job's own processes cannot use the network or start other programs (an audit-hook guard, scripts/p3/devrun_site);
- no held-out, hidden or truth data, no orchestrator module, no simulation service.
New or changed files under the developer's runs/<prefix>/ come back into the room under runs/<prefix>/remote/<job id>/ (size capped).
Every job is recorded outside the room (C:\\Dev\\BrainIR_p3audit\\remote_runner.jsonl: request, code-tar hash, result hash, exit
code, peak memory, wall time).
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import shutil
import sys
import tarfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROOM = Path(r"C:\Dev\BrainIR_p3clean")
AUDIT = Path(r"C:\Dev\BrainIR_p3audit") / "remote_runner.jsonl"
QUEUE = ROOM / "runs" / "_remote" / "queue"
APP_NAME = "brainir-p3-devrun"
DEV_VOLUME = "brainir-p3-devdata"
EVAL_VOLUME, FIT_VOLUME = "brainir-p3-eval", "brainir-p3-fit"
# resource classes: (cpu cores, memory MB); concurrency is capped by the total memory of the running jobs
CLASSES = {"small": (2.0, 8192), "medium": (4.0, 16384), "large": (8.0, 32768), "xlarge": (8.0, 65536)}
MAX_TOTAL_MEM_MB = 1024 * 1024       # 1 TB across all running jobs
MAX_RUNNING = 48
MAX_CODE_TAR = 300 * 1024 * 1024
MAX_RESULT_TAR = 500 * 1024 * 1024
MAX_FILE_IN_CODE = 25 * 1024 * 1024
SAFE_ARG = re.compile(r"^[\w.,:=+\-/@% ]*$")


# ------------------------------------------------------------------------------------------------ Modal definitions
def image():
    import modal
    return (modal.Image.debian_slim(python_version="3.12")
            .pip_install("numpy==2.5.3", "scipy==1.18.1", "pandas==3.0.6", "pyarrow==25.0.1", "pydantic==2.13.5", "scikit-learn==1.9.1",
                         "threadpoolctl==3.7.0", "pytest>=8,<10")
            .pip_install("torch==2.14.0", index_url="https://download.pytorch.org/whl/cpu")
            .env({"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1",
                  # the same numerics pinning as the evaluation image (PROTOCOL.md section 10)
                  "NPY_DISABLE_CPU_FEATURES": "X86_V4 AVX512_ICL AVX512_SPR", "ATEN_CPU_CAPABILITY": "avx2"})
            # the job guard (network and program starts refused inside the job's own Python processes)
            .add_local_dir(str(Path(__file__).resolve().parent / "devrun_site"), "/opt/devguard"))


def _run_job(payload: dict) -> dict:
    """Container side: unpack the room code, link the data, run the script, return the new / changed files of the work area."""
    import resource
    import subprocess
    t0 = time.time()
    room = Path("/room")
    shutil.rmtree(room, ignore_errors=True)
    room.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(payload["code_tar"])) as tf:
        tf.extractall(room, filter="data")
    (room / "data").symlink_to("/devdata")
    prefix = payload["prefix"]
    work = room / "runs" / prefix

    def hashes():
        out = {}
        if work.exists():
            for p in work.rglob("*"):
                if p.is_file():
                    out[p.relative_to(room).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    before = hashes()
    cpu = int(payload["cpu"])
    env = {"PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"), "HOME": "/tmp",
           "PYTHONPATH": "/opt/devguard" + os.pathsep + str(room / "src"),
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": str(cpu), "MKL_NUM_THREADS": str(cpu),
           "OPENBLAS_NUM_THREADS": str(cpu), "P3_REMOTE_JOB": payload["job_id"], "P3_REMOTE_CPUS": str(cpu),
           "NPY_DISABLE_CPU_FEATURES": os.environ.get("NPY_DISABLE_CPU_FEATURES", ""),
           "ATEN_CPU_CAPABILITY": os.environ.get("ATEN_CPU_CAPABILITY", ""), "PYTHONFAULTHANDLER": "1"}
    try:
        pr = subprocess.run([sys.executable, payload["script"], *payload["args"]], cwd=str(room), env=env, capture_output=True,
                            text=True, timeout=float(payload["timeout_s"]))
        code, out, err = pr.returncode, pr.stdout, pr.stderr
    except subprocess.TimeoutExpired as e:
        code, out, err = "timeout", (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or ""), \
            (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
    after = hashes()
    changed = sorted(p for p, h in after.items() if before.get(p) != h)
    buf = io.BytesIO()
    size, dropped = 0, []
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for rel in changed:
            p = room / rel
            s = p.stat().st_size
            if size + s > MAX_RESULT_TAR:
                dropped.append(rel)
                continue
            tf.add(p, arcname=rel)
            size += s
    peak_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0
    return {"exit_code": code, "stdout_tail": out[-20000:], "stderr_tail": err[-20000:], "result_tar": buf.getvalue(),
            "changed": changed, "dropped_for_size": dropped, "peak_rss_mb": round(peak_mb, 1),
            "container_wall_s": round(time.time() - t0, 1)}


def make_app():
    import modal
    app = modal.App(APP_NAME, image=image())
    dev = modal.Volume.from_name(DEV_VOLUME, create_if_missing=True)

    def run_job(payload):
        return _run_job(payload)

    fns = {}
    for name, (cpu, mem) in CLASSES.items():
        # the container's own runtime keeps its network (Modal fetches large inputs and stores large outputs through blob storage);
        # the JOB's processes are guarded by /opt/devguard/sitecustomize.py (no network, no other programs)
        fns[name] = app.function(cpu=cpu, memory=mem, timeout=6 * 3600, max_containers=64,
                                 volumes={"/devdata": dev}, serialized=True, name=f"devrun_{name}")(run_job)
    return app, fns


# ------------------------------------------------------------------------------------------------ dev-data volume
def _local_data_hashes() -> dict:
    base = ROOM / "data"
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.rglob("*")) if p.is_file()}


def sync_data() -> int:
    """Build the dev-data volume server-side (public dev suite from the eval volume, public real fit view from the fit volume), upload
    only what is missing, then verify every file by sha256 against the room's data/ directory."""
    import modal
    local = _local_data_hashes()
    print(f"room data/: {len(local)} files", flush=True)
    app = modal.App("brainir-p3-devdata-sync", image=image())
    ev, fv = modal.Volume.from_name(EVAL_VOLUME), modal.Volume.from_name(FIT_VOLUME)
    dev = modal.Volume.from_name(DEV_VOLUME, create_if_missing=True)

    def build_and_hash(extra_tar: bytes | None) -> dict:
        import hashlib as H
        import shutil as S
        import tarfile as T
        from pathlib import Path as P
        d = P("/devdata")
        src_dev = P("/evalvol/suites/dev/public")
        if not (d / "synthetic_dev" / "manifest.json").exists():
            S.copytree(src_dev, d / "synthetic_dev", dirs_exist_ok=True)
        rv = P("/fitvol/views/real")
        (d / "real_public" / "traj").mkdir(parents=True, exist_ok=True)
        for p in (rv / "traj").iterdir():
            q = d / "real_public" / "traj" / p.name
            if not q.exists():
                S.copyfile(p, q)
        if extra_tar:
            with T.open(fileobj=__import__("io").BytesIO(extra_tar)) as tf:
                tf.extractall(d, filter="data")
        import modal as M
        M.Volume.from_name("brainir-p3-devdata").commit()
        return {p.relative_to(d).as_posix(): H.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}

    fn = app.function(cpu=2.0, memory=8192, timeout=3600, volumes={"/devdata": dev, "/evalvol": ev, "/fitvol": fv}, serialized=True,
                      name="devdata_build")(build_and_hash)
    with app.run():
        remote = fn.remote(None)
        missing = sorted(k for k in local if remote.get(k) != local[k])
        extra = sorted(k for k in remote if k not in local)
        print(f"after server-side copy: {len(remote)} files; {len(missing)} missing or different; {len(extra)} extra", flush=True)
        if missing:
            buf = io.BytesIO()
            with tarfile.open(fileobj=buf, mode="w") as tf:
                for k in missing:
                    tf.add(ROOM / "data" / k, arcname=k)
            print(f"uploading {len(missing)} files ({buf.tell() / 1e6:.0f} MB)", flush=True)
            remote = fn.remote(buf.getvalue())
    bad = sorted(k for k in local if remote.get(k) != local[k])
    extra = sorted(k for k in remote if k not in local)
    rec = {"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_files": len(local), "mismatch": bad[:20],
           "n_mismatch": len(bad), "extra": extra[:20], "n_extra": len(extra)}
    out = ROOT / "research" / "phase3" / "devrun_volume_check.json"
    out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec), flush=True)
    return 0 if not bad and not extra else 1


# ------------------------------------------------------------------------------------------------ daemon
def _validate(req: dict) -> tuple[str, str, list[str], str, float]:
    script = str(req.get("script", "")).replace("\\", "/")
    m = re.match(r"^runs/([A-Za-z0-9_]+)/[\w./\-]+\.py$", script)
    if not m or ".." in script.split("/") or m.group(1).startswith("_"):
        raise ValueError("script must be a .py file inside runs/<your prefix>/")
    prefix = m.group(1)
    if not (ROOM / script).is_file():
        raise ValueError(f"script not found: {script}")
    args = req.get("args") or []
    if not isinstance(args, list) or not all(isinstance(a, str) and SAFE_ARG.match(a) and ".." not in a for a in args):
        raise ValueError("args must be a list of plain strings (letters, digits and . , : = + - / @ % _ space; no '..')")
    klass = str(req.get("class", "small"))
    if klass not in CLASSES:
        raise ValueError(f"class must be one of {sorted(CLASSES)}")
    timeout = float(req.get("timeout_s", 3600))
    if not (10 <= timeout <= 6 * 3600):
        raise ValueError("timeout_s must be within [10, 21600]")
    return script, prefix, [str(a) for a in args], klass, timeout


def _code_tar(prefix: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for top in (ROOM / "src", ROOM / "runs" / prefix):
            for p in sorted(top.rglob("*")):
                rel = p.relative_to(ROOM).as_posix()
                if not p.is_file() or "__pycache__" in p.parts or p.suffix == ".pyc":
                    continue
                if rel.startswith(f"runs/{prefix}/remote/") or p.stat().st_size > MAX_FILE_IN_CODE:
                    continue
                tf.add(p, arcname=rel)
                if buf.tell() > MAX_CODE_TAR:
                    raise ValueError("code tar too large (runs/<prefix>/ holds too much data; move large outputs or delete them)")
    return buf.getvalue()


def _audit(rec: dict) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec, sort_keys=True) + "\n")


def _write_result(job_id: str, res: dict) -> None:
    (QUEUE / "results").mkdir(parents=True, exist_ok=True)
    tmp = QUEUE / "results" / f".{job_id}.tmp"
    tmp.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, QUEUE / "results" / f"{job_id}.json")


def daemon(poll_s: float = 3.0) -> int:
    app, fns = make_app()
    running: dict[str, dict] = {}
    (QUEUE / "requests").mkdir(parents=True, exist_ok=True)
    print(f"devrun daemon: queue {QUEUE}", flush=True)
    with app.run():
        while True:
            # finished jobs
            for job_id, j in list(running.items()):
                try:
                    res = j["call"].get(timeout=0)
                except Exception as e:  # noqa: BLE001
                    if "timeout" in type(e).__name__.lower():            # not finished yet (Modal's own TimeoutError class)
                        continue
                    res = {"exit_code": "infrastructure_error", "stderr_tail": repr(e)[-4000:], "result_tar": b"", "changed": []}
                out_dir = ROOM / "runs" / j["prefix"] / "remote" / job_id
                out_dir.mkdir(parents=True, exist_ok=True)
                tar_bytes = res.pop("result_tar", b"") or b""
                n_files = 0
                if tar_bytes:
                    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
                        for m in tf.getmembers():
                            name = m.name.replace("\\", "/")
                            if not m.isfile() or name.startswith("/") or ".." in name.split("/") or not name.startswith(f"runs/{j['prefix']}/"):
                                continue
                            dst = out_dir / name
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            with tf.extractfile(m) as src, open(dst, "wb") as fh:
                                shutil.copyfileobj(src, fh)
                            n_files += 1
                summary = {k: v for k, v in res.items() if k != "result_tar"}
                summary.update({"job_id": job_id, "status": "done", "outputs_dir": f"runs/{j['prefix']}/remote/{job_id}/",
                                "n_output_files": n_files, "class": j["class"], "wall_s": round(time.time() - j["t0"], 1)})
                _write_result(job_id, summary)
                _audit({"event": "done", "job_id": job_id, "prefix": j["prefix"], "script": j["script"], "exit_code": res.get("exit_code"),
                        "result_sha256": hashlib.sha256(tar_bytes).hexdigest(), "n_output_files": n_files,
                        "peak_rss_mb": res.get("peak_rss_mb"), "container_wall_s": res.get("container_wall_s"),
                        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
                del running[job_id]
            # new requests
            used = sum(CLASSES[j["class"]][1] for j in running.values())
            for f in sorted((QUEUE / "requests").glob("*.json")):
                job_id = f.stem
                if job_id in running or (QUEUE / "results" / f"{job_id}.json").exists():
                    continue
                try:
                    req = json.loads(f.read_text(encoding="utf-8"))
                    script, prefix, args, klass, timeout = _validate(req)
                except Exception as e:  # noqa: BLE001
                    _write_result(job_id, {"job_id": job_id, "status": "rejected", "reason": str(e)[:1000]})
                    _audit({"event": "rejected", "job_id": job_id, "reason": str(e)[:1000]})
                    continue
                mem = CLASSES[klass][1]
                if len(running) >= MAX_RUNNING or used + mem > MAX_TOTAL_MEM_MB:
                    break                                          # wait for capacity (first come, first served)
                try:
                    code = _code_tar(prefix)
                except Exception as e:  # noqa: BLE001
                    _write_result(job_id, {"job_id": job_id, "status": "rejected", "reason": str(e)[:1000]})
                    _audit({"event": "rejected", "job_id": job_id, "reason": str(e)[:1000]})
                    continue
                payload = {"job_id": job_id, "code_tar": code, "prefix": prefix, "script": script, "args": args,
                           "cpu": CLASSES[klass][0], "timeout_s": timeout}
                call = fns[klass].spawn(payload)
                running[job_id] = {"call": call, "prefix": prefix, "script": script, "class": klass, "t0": time.time()}
                used += mem
                (QUEUE / "status").mkdir(parents=True, exist_ok=True)
                (QUEUE / "status" / f"{job_id}.json").write_text(json.dumps({"job_id": job_id, "status": "running", "class": klass}) + "\n",
                                                                 encoding="utf-8")
                _audit({"event": "start", "job_id": job_id, "prefix": prefix, "script": script, "args": args, "class": klass,
                        "code_sha256": hashlib.sha256(code).hexdigest(), "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            time.sleep(poll_s)


# ------------------------------------------------------------------------------------------------ client install
CLIENT = '''"""Remote runner client (clean room): run one of YOUR scripts on a Modal container with more memory / CPUs.

    uv run python runs/_remote/remote_run.py submit runs/<prefix>/my_exp.py --class medium [--timeout 3600] -- --arg1 v1 --arg2 v2
    uv run python runs/_remote/remote_run.py wait <job_id> [<job_id> ...]      # polls until done; prints the result summaries
    uv run python runs/_remote/remote_run.py status <job_id>

See notes/_remote_runner.md. Standard library only; it only writes a request file and reads the result file.
"""
import json
import sys
import time
import uuid
from pathlib import Path

Q = Path(__file__).resolve().parent / "queue"


def submit(argv):
    script = argv[0]
    klass, timeout, rest = "small", 3600, []
    i = 1
    while i < len(argv):
        if argv[i] == "--class":
            klass = argv[i + 1]; i += 2
        elif argv[i] == "--timeout":
            timeout = int(argv[i + 1]); i += 2
        elif argv[i] == "--":
            rest = argv[i + 1:]; break
        else:
            raise SystemExit(f"unknown option {argv[i]} (put the script's own arguments after --)")
    job_id = time.strftime("%Y%m%dT%H%M%S") + "_" + uuid.uuid4().hex[:8]
    (Q / "requests").mkdir(parents=True, exist_ok=True)
    tmp = Q / "requests" / f".{job_id}.tmp"
    tmp.write_text(json.dumps({"script": script, "args": rest, "class": klass, "timeout_s": timeout}) + "\\n", encoding="utf-8")
    tmp.replace(Q / "requests" / f"{job_id}.json")
    print(job_id)


def status(job_id):
    r = Q / "results" / f"{job_id}.json"
    if r.exists():
        return json.loads(r.read_text(encoding="utf-8"))
    s = Q / "status" / f"{job_id}.json"
    return json.loads(s.read_text(encoding="utf-8")) if s.exists() else {"job_id": job_id, "status": "queued"}


def main():
    cmd, argv = sys.argv[1], sys.argv[2:]
    if cmd == "submit":
        submit(argv)
    elif cmd == "status":
        print(json.dumps(status(argv[0]), indent=1)[:4000])
    elif cmd == "wait":
        pending = list(argv)
        while pending:
            for j in list(pending):
                s = status(j)
                if s.get("status") in ("done", "rejected"):
                    print(json.dumps({k: v for k, v in s.items() if k not in ("stdout_tail", "stderr_tail")}, indent=1))
                    print("--- stdout (tail) ---\\n" + (s.get("stdout_tail") or "")[-3000:])
                    print("--- stderr (tail) ---\\n" + (s.get("stderr_tail") or "")[-3000:])
                    pending.remove(j)
            if pending:
                time.sleep(10)
    else:
        raise SystemExit("commands: submit, status, wait")


if __name__ == "__main__":
    main()
'''

NOTES = '''# Remote runner for development experiments (from the orchestrator)

Heavy development experiments (sweeps over many systems or seeds, real full systems) can run on remote containers instead of
this machine. The runner exists because the local machine ran out of memory.

What a remote job is:
- ONE of your Python scripts in your work area (`runs/<your prefix>/...py`), run with `python <script> <args>` from the room root;
- the room's `src/` and your `runs/<prefix>/` are copied in (files over 25 MB and your `runs/<prefix>/remote/` are left out);
- `data/` is an exact copy of this room's `data/` (the same public development data; nothing else);
- the network is blocked; the budgeted simulation service is NOT available (scripts that use SimClient must run locally);
- numerics: the same pinned numerical stack as the evaluation (last-digit differences from this machine are possible in dense
  linear algebra).

Resource classes (`--class`): small = 2 CPUs / 8 GB, medium = 4 CPUs / 16 GB, large = 8 CPUs / 32 GB, xlarge = 8 CPUs / 64 GB.
Inside the job, `P3_REMOTE_CPUS` holds the CPU count; threads (OMP / MKL / OpenBLAS) are set to it. The one-process-and-3-threads
rule of this room does not apply to remote jobs: use the container's CPUs. Several jobs may run in parallel (split a sweep into one
job per system or seed).

Usage:

    uv run python runs/_remote/remote_run.py submit runs/<prefix>/exp.py --class medium --timeout 3600 -- --system syn-xxx --seed 1
    uv run python runs/_remote/remote_run.py wait <job_id> [<job_id> ...]
    uv run python runs/_remote/remote_run.py status <job_id>

Results: every new or changed file under your `runs/<prefix>/` comes back under `runs/<prefix>/remote/<job_id>/runs/<prefix>/...`,
next to the job's exit code, the tails of stdout / stderr, the peak memory and the wall time (`runs/_remote/queue/results/`).
Write your outputs under `runs/<prefix>/` so that they come back. Never end your turn to wait for a job: poll with `wait` (it blocks
in the foreground).
'''


def install_client() -> int:
    tools = ROOT / "research" / "phase3" / "review_contracts"
    (tools / "remote_run_client.py").write_text(CLIENT, encoding="utf-8", newline="\n")
    (tools / "remote_runner_notes.md").write_text(NOTES, encoding="utf-8", newline="\n")
    import subprocess
    for src, dest, reason in ((tools / "remote_run_client.py", "runs/_remote/remote_run.py", "remote runner client (writes request files)"),
                              (tools / "remote_runner_notes.md", "notes/_remote_runner.md", "remote runner instructions")):
        subprocess.run([sys.executable, str(ROOT / "scripts" / "p3" / "room_addendum.py"), "--src", str(src), "--dest", dest,
                        "--reason", reason, "--leakage-class", "generic-public"], check=True)
    (QUEUE / "requests").mkdir(parents=True, exist_ok=True)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("sync-data", "daemon", "install-client"))
    args = ap.parse_args(argv)
    if args.cmd == "sync-data":
        return sync_data()
    if args.cmd == "install-client":
        return install_client()
    return daemon()


if __name__ == "__main__":
    raise SystemExit(main())
