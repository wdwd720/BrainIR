"""Remote runner v4 for Phase 4 room development experiments on Modal, CPU and GPU (orchestrator side; LEAKAGE_POLICY.md section 2.6).

    uv run --no-sync --project phase4 python scripts/p4/devrun4.py sync-data [--room ROOM]     # build / verify the dev-data volume
    uv run --no-sync --project phase4 python scripts/p4/devrun4.py daemon [--room ROOM]        # serve the room's request queue (background)
    uv run --no-sync --project phase4 python scripts/p4/devrun4.py install-client               # write the client + notes (for the builder)
    uv run --no-sync --project phase4 python scripts/p4/devrun4.py smoke --room ROOM --class small|gpu-t4 [--script runs/smoke/x.py]

Room agents have no Modal access, no credentials and no network. From the Docker sandbox they drop a request (a Python script of their
own work area, its arguments, a resource class) into runs/_remote/queue/requests/ with the room's client (tools/remote_run.py). This
daemon validates the request and runs it on Modal:
- the images hold the room's pinned numerical stack (the local sandbox image's requirements, the same python:3.12-slim base) and NO
  repository code; CPU images carry the development machine's numerics pins; GPU images use PyPI's CUDA build of torch 2.14.0;
- the job brings the room's src/, baselines/ and the requesting developer's runs/<prefix>/ as a tar;
- the only volume is `brainir-p4-devdata`, an exact copy of the room's data/ directory (every file verified by sha256); no Phase 3
  volume (brainir-p3-*) is ever mounted, no hidden / truth data, no orchestrator module, no simulation service;
- the job's own processes cannot use the network or start other programs (audit-hook guard scripts/p4/devrun4_site);
- new or changed files under runs/<prefix>/ come back into the room under runs/<prefix>/remote/<job id>/ (size capped).
Every job is recorded outside the room (C:\\Dev\\BrainIR_p4audit\\remote_runner.jsonl: request, code-tar hash, result hash, exit code,
peak memory, wall time, class, GPU).
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOM = Path(r"C:\Dev\BrainIR_p4clean")
AUDIT = Path(r"C:\Dev\BrainIR_p4audit") / "remote_runner.jsonl"
APP_NAME = "brainir-p4-devrun"
DEV_VOLUME = "brainir-p4-devdata"
REQUIREMENTS = ROOT / "docker" / "p4sandbox" / "requirements.txt"
BASE_IMAGE = "python:3.12-slim@sha256:f77ac9e44ae96ef2c90b8053ea08c31f8be030f824196b0ae4db6d462c84e51f"
CPU_PINS = {"NPY_DISABLE_CPU_FEATURES": "X86_V4 AVX512_ICL AVX512_SPR", "ATEN_CPU_CAPABILITY": "avx2"}
# resource classes: (cpu cores, memory MB, gpu type or None); GPU strings verified by research/phase4/GPU_BENCHMARK.json (probe)
CLASSES = {
    "small": (2.0, 8192, None), "medium": (4.0, 16384, None), "large": (8.0, 32768, None), "xlarge": (8.0, 65536, None),
    "xxlarge": (16.0, 131072, None),
    "gpu-t4": (4.0, 32768, "T4"), "gpu-l4": (4.0, 32768, "L4"), "gpu-a10g": (4.0, 32768, "A10G"), "gpu-l40s": (8.0, 65536, "L40S"),
    "gpu-a100-40gb": (8.0, 65536, "A100-40GB"), "gpu-a100-80gb": (8.0, 65536, "A100-80GB"), "gpu-h100": (8.0, 65536, "H100"),
    "gpu-h200": (8.0, 131072, "H200"), "gpu-b200": (8.0, 131072, "B200"),
}
MAX_TOTAL_MEM_MB = 2 * 1024 * 1024
MAX_RUNNING = 48
MAX_RUNNING_GPU = 16
MAX_CODE_TAR = 300 * 1024 * 1024
MAX_RESULT_TAR = 500 * 1024 * 1024
MAX_FILE_IN_CODE = 25 * 1024 * 1024
SAFE_ARG = re.compile(r"^[\w.,:=+\-/@% ]*$")


def _queue(room: Path) -> Path:
    return room / "runs" / "_remote" / "queue"


# ------------------------------------------------------------------------------------------------ Modal definitions
def image(gpu: bool):
    import modal
    img = modal.Image.from_registry(BASE_IMAGE).pip_install_from_requirements(str(REQUIREMENTS))
    if gpu:
        img = img.pip_install("torch==2.14.0")                                      # PyPI's Linux wheel = the CUDA build
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    else:
        img = img.pip_install("torch==2.14.0", index_url="https://download.pytorch.org/whl/cpu", extra_options="--no-deps")
        env = {"PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", **CPU_PINS}
    return img.env(env).add_local_dir(str(Path(__file__).resolve().parent / "devrun4_site"), "/opt/devguard")


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
    if Path("/devdata").exists():
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
           "PYTHONPATH": "/opt/devguard" + os.pathsep + str(room / "src") + os.pathsep + str(room / "baselines"),
           "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1", "OMP_NUM_THREADS": str(cpu), "MKL_NUM_THREADS": str(cpu),
           "OPENBLAS_NUM_THREADS": str(cpu), "P4_REMOTE_JOB": payload["job_id"], "P4_REMOTE_CPUS": str(cpu),
           "P4_REMOTE_GPU": payload.get("gpu") or "", "PYTHONFAULTHANDLER": "1", "MPLBACKEND": "Agg", "MPLCONFIGDIR": "/tmp/mpl"}
    for k in ("NPY_DISABLE_CPU_FEATURES", "ATEN_CPU_CAPABILITY", "NVIDIA_VISIBLE_DEVICES", "CUDA_VISIBLE_DEVICES", "LD_LIBRARY_PATH"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    try:
        pr = subprocess.run([sys.executable, payload["script"], *payload["args"]], cwd=str(room), env=env, capture_output=True,
                            text=True, timeout=float(payload["timeout_s"]))
        code, out, err = pr.returncode, pr.stdout, pr.stderr
    except subprocess.TimeoutExpired as e:
        code = "timeout"
        out = (e.stdout or b"").decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = (e.stderr or b"").decode("utf-8", "replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
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


def make_app(classes: list[str] | None = None, with_volume: bool = True, volume: str = DEV_VOLUME):
    import modal
    app = modal.App(APP_NAME)
    vols = {}
    if with_volume:
        if volume.startswith("brainir-p3") or not volume.startswith("brainir-p4-devdata"):
            raise SystemExit(f"refusing to mount volume {volume!r}: only brainir-p4-devdata* volumes (never Phase 3 volumes)")
        vols = {"/devdata": modal.Volume.from_name(volume, create_if_missing=True)}
    imgs = {False: image(False), True: image(True)}

    def run_job(payload):
        return _run_job(payload)

    fns = {}
    for name in classes or list(CLASSES):
        cpu, mem, gpu = CLASSES[name]
        # the container's own runtime keeps its network (Modal transfers large inputs / outputs through blob storage); the JOB's
        # processes are guarded by /opt/devguard/sitecustomize.py (no network, no other programs)
        kw = {"cpu": cpu, "memory": mem, "timeout": 6 * 3600, "max_containers": 64, "volumes": vols, "serialized": True,
              "name": f"devrun_{name.replace('-', '_')}", "image": imgs[gpu is not None]}
        if gpu:
            kw["gpu"] = gpu
        fns[name] = app.function(**kw)(run_job)
    return app, fns


# ------------------------------------------------------------------------------------------------ dev-data volume
def _local_data_hashes(room: Path) -> dict:
    base = room / "data"
    return {p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(base.rglob("*")) if p.is_file()}


def sync_data(room: Path, chunk_mb: int = 256, volume: str = DEV_VOLUME) -> int:
    """Make the dev-data volume an exact copy of the room's data/: upload what is missing or different (tar chunks, extracted inside
    Modal), delete extras, then verify every file by sha256."""
    import modal
    local = _local_data_hashes(room)
    print(f"room data/: {len(local)} files", flush=True)
    if volume.startswith("brainir-p3") or not volume.startswith("brainir-p4-devdata"):
        raise SystemExit(f"refusing volume {volume!r}")
    app = modal.App("brainir-p4-devdata-sync")
    dev = modal.Volume.from_name(volume, create_if_missing=True)
    vol_name = volume

    def apply_and_hash(tar_bytes: bytes | None, delete: list[str]) -> dict:
        import hashlib as H
        import io as I
        import tarfile as T
        from pathlib import Path as P
        d = P("/devdata")
        for rel in delete:
            q = d / rel
            if q.is_file():
                q.unlink()
        if tar_bytes:
            with T.open(fileobj=I.BytesIO(tar_bytes)) as tf:
                tf.extractall(d, filter="data")
        import modal as M
        M.Volume.from_name(vol_name).commit()
        return {p.relative_to(d).as_posix(): H.sha256(p.read_bytes()).hexdigest() for p in sorted(d.rglob("*")) if p.is_file()}

    fn = app.function(cpu=2.0, memory=8192, timeout=3600, volumes={"/devdata": dev}, serialized=True, name="devdata_apply",
                      image=modal.Image.debian_slim(python_version="3.12"))(apply_and_hash)
    with app.run():
        remote = fn.remote(None, [])
        extra = sorted(k for k in remote if k not in local)
        missing = sorted(k for k in local if remote.get(k) != local[k])
        print(f"volume: {len(remote)} files; {len(missing)} missing or different; {len(extra)} extra", flush=True)
        batch, size = [], 0
        for k in missing + [None]:
            if k is not None:
                batch.append(k)
                size += (room / "data" / k).stat().st_size
            if batch and (k is None or size > chunk_mb * 1e6):
                buf = io.BytesIO()
                with tarfile.open(fileobj=buf, mode="w") as tf:
                    for rel in batch:
                        tf.add(room / "data" / rel, arcname=rel)
                print(f"uploading {len(batch)} files ({buf.tell() / 1e6:.0f} MB)", flush=True)
                remote = fn.remote(buf.getvalue(), extra)
                extra, batch, size = [], [], 0
        if extra:
            remote = fn.remote(None, extra)
    bad = sorted(k for k in local if remote.get(k) != local[k])
    extra = sorted(k for k in remote if k not in local)
    rec = {"time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "room": room.name, "volume": volume, "n_files": len(local),
           "mismatch": bad[:20],
           "n_mismatch": len(bad), "extra": extra[:20], "n_extra": len(extra)}
    out = ROOT / "research" / "phase4" / f"devrun4_volume_check_{room.name}.json"
    out.write_text(json.dumps(rec, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(rec), flush=True)
    return 0 if not bad and not extra else 1


# ------------------------------------------------------------------------------------------------ daemon
def _validate(room: Path, req: dict) -> tuple[str, str, list[str], str, float]:
    script = str(req.get("script", "")).replace("\\", "/")
    m = re.match(r"^runs/([A-Za-z0-9_]+)/[\w./\-]+\.py$", script)
    if not m or ".." in script.split("/") or m.group(1).startswith("_"):
        raise ValueError("script must be a .py file inside runs/<your prefix>/")
    prefix = m.group(1)
    if not (room / script).is_file():
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


def _code_tar(room: Path, prefix: str) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for top in (room / "src", room / "baselines", room / "runs" / prefix):
            if not top.exists():
                continue
            for p in sorted(top.rglob("*")):
                rel = p.relative_to(room).as_posix()
                if not p.is_file() or p.is_symlink() or "__pycache__" in p.parts or p.suffix == ".pyc":
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


def _write_result(q: Path, job_id: str, res: dict) -> None:
    (q / "results").mkdir(parents=True, exist_ok=True)
    tmp = q / "results" / f".{job_id}.tmp"
    tmp.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, q / "results" / f"{job_id}.json")


def _unpack_result(room: Path, prefix: str, job_id: str, tar_bytes: bytes) -> int:
    out_dir = room / "runs" / prefix / "remote" / job_id
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    if tar_bytes:
        with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tf:
            for m in tf.getmembers():
                name = m.name.replace("\\", "/")
                if not m.isfile() or name.startswith("/") or ".." in name.split("/") or not name.startswith(f"runs/{prefix}/"):
                    continue
                dst = out_dir / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(m) as src, open(dst, "wb") as fh:
                    shutil.copyfileobj(src, fh)
                n += 1
    return n


def daemon(room: Path, poll_s: float = 3.0, volume: str = DEV_VOLUME) -> int:
    app, fns = make_app(volume=volume)
    running: dict[str, dict] = {}
    q = _queue(room)
    (q / "requests").mkdir(parents=True, exist_ok=True)
    print(f"devrun4 daemon: queue {q}", flush=True)
    with app.run():
        while True:
            for job_id, j in list(running.items()):
                try:
                    res = j["call"].get(timeout=0)
                except Exception as e:  # noqa: BLE001
                    if "timeout" in type(e).__name__.lower():
                        continue
                    res = {"exit_code": "infrastructure_error", "stderr_tail": repr(e)[-4000:], "result_tar": b"", "changed": []}
                tar_bytes = res.pop("result_tar", b"") or b""
                n_files = _unpack_result(room, j["prefix"], job_id, tar_bytes)
                summary = {k: v for k, v in res.items() if k != "result_tar"}
                summary.update({"job_id": job_id, "status": "done", "outputs_dir": f"runs/{j['prefix']}/remote/{job_id}/",
                                "n_output_files": n_files, "class": j["class"], "wall_s": round(time.time() - j["t0"], 1)})
                _write_result(q, job_id, summary)
                _audit({"event": "done", "room": room.name, "job_id": job_id, "prefix": j["prefix"], "script": j["script"],
                        "exit_code": res.get("exit_code"), "result_sha256": hashlib.sha256(tar_bytes).hexdigest(), "n_output_files": n_files,
                        "peak_rss_mb": res.get("peak_rss_mb"), "container_wall_s": res.get("container_wall_s"), "class": j["class"],
                        "gpu": CLASSES[j["class"]][2], "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
                del running[job_id]
            used = sum(CLASSES[j["class"]][1] for j in running.values())
            n_gpu = sum(1 for j in running.values() if CLASSES[j["class"]][2])
            for f in sorted((q / "requests").glob("*.json")):
                job_id = f.stem
                if job_id in running or (q / "results" / f"{job_id}.json").exists():
                    continue
                try:
                    req = json.loads(f.read_text(encoding="utf-8"))
                    script, prefix, args, klass, timeout = _validate(room, req)
                except Exception as e:  # noqa: BLE001
                    _write_result(q, job_id, {"job_id": job_id, "status": "rejected", "reason": str(e)[:1000]})
                    _audit({"event": "rejected", "room": room.name, "job_id": job_id, "reason": str(e)[:1000]})
                    continue
                cpu, mem, gpu = CLASSES[klass]
                if len(running) >= MAX_RUNNING or used + mem > MAX_TOTAL_MEM_MB or (gpu and n_gpu >= MAX_RUNNING_GPU):
                    break
                try:
                    code = _code_tar(room, prefix)
                except Exception as e:  # noqa: BLE001
                    _write_result(q, job_id, {"job_id": job_id, "status": "rejected", "reason": str(e)[:1000]})
                    _audit({"event": "rejected", "room": room.name, "job_id": job_id, "reason": str(e)[:1000]})
                    continue
                payload = {"job_id": job_id, "code_tar": code, "prefix": prefix, "script": script, "args": args, "cpu": cpu,
                           "gpu": gpu, "timeout_s": timeout}
                call = fns[klass].spawn(payload)
                running[job_id] = {"call": call, "prefix": prefix, "script": script, "class": klass, "t0": time.time()}
                used += mem
                n_gpu += 1 if gpu else 0
                (q / "status").mkdir(parents=True, exist_ok=True)
                (q / "status" / f"{job_id}.json").write_text(json.dumps({"job_id": job_id, "status": "running", "class": klass}) + "\n",
                                                             encoding="utf-8")
                _audit({"event": "start", "room": room.name, "job_id": job_id, "prefix": prefix, "script": script, "args": args,
                        "class": klass, "gpu": gpu, "code_sha256": hashlib.sha256(code).hexdigest(),
                        "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
            time.sleep(poll_s)


def smoke(room: Path, klass: str, script: str, with_volume: bool, volume: str = DEV_VOLUME) -> int:
    """Run ONE job synchronously (the daemon's code path without the queue); record the result."""
    prefix = script.split("/")[1]
    app, fns = make_app([klass], with_volume=with_volume, volume=volume)
    job_id = time.strftime("%Y%m%dT%H%M%S") + "_smoke"
    code = _code_tar(room, prefix)
    cpu, mem, gpu = CLASSES[klass]
    t0 = time.time()
    with app.run():
        res = fns[klass].remote({"job_id": job_id, "code_tar": code, "prefix": prefix, "script": script, "args": [], "cpu": cpu,
                                 "gpu": gpu, "timeout_s": 1800})
    tar_bytes = res.pop("result_tar", b"") or b""
    n = _unpack_result(room, prefix, job_id, tar_bytes)
    rec = {k: v for k, v in res.items()}
    rec.update({"class": klass, "gpu": gpu, "job_id": job_id, "n_output_files": n, "wall_s": round(time.time() - t0, 1),
                "time_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    _audit({"event": "smoke", **{k: v for k, v in rec.items() if k not in ("stdout_tail", "stderr_tail")},
            "result_sha256": hashlib.sha256(tar_bytes).hexdigest()})
    out = ROOT / "research" / "phase4" / "devrun4_smoke.json"
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    prev[f"{klass}:{script}"] = {k: (v[-3000:] if isinstance(v, str) else v) for k, v in rec.items()}
    out.write_text(json.dumps(prev, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in rec.items() if k not in ("stderr_tail",)}, indent=1)[:4000])
    return 0 if rec.get("exit_code") == 0 else 1


# ------------------------------------------------------------------------------------------------ client install
CLIENT = '''"""Remote runner client (Phase 4 room): run one of YOUR scripts on a Modal container (more CPUs / memory, or a GPU).

    sbx python tools/remote_run.py submit runs/<prefix>/my_exp.py --class medium [--timeout 3600] -- --arg1 v1 --arg2 v2
    sbx python tools/remote_run.py wait <job_id> [<job_id> ...]      # polls until done; prints the result summaries
    sbx python tools/remote_run.py status <job_id>
    sbx python tools/remote_run.py classes

See docs/REMOTE_RUNNER.md. Standard library only; it only writes a request file and reads the result file.
"""
import json
import sys
import time
import uuid
from pathlib import Path

Q = Path(__file__).resolve().parents[1] / "runs" / "_remote" / "queue"
CLASSES = %s


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
    if klass not in CLASSES:
        raise SystemExit(f"--class must be one of {sorted(CLASSES)}")
    job_id = time.strftime("%%Y%%m%%dT%%H%%M%%S") + "_" + uuid.uuid4().hex[:8]
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
    elif cmd == "classes":
        for k, v in CLASSES.items():
            print(k, v)
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
        raise SystemExit("commands: submit, status, wait, classes")


if __name__ == "__main__":
    main()
'''

NOTES = '''# Remote runner for development experiments (CPU and GPU)

Heavy development experiments (sweeps over many systems or seeds, large neural models, anything that needs a GPU) run on remote
containers instead of this machine.

What a remote job is:
- ONE of your Python scripts in your work area (`runs/<your prefix>/...py`), run with `python <script> <args>` from the room root;
- the room's `src/` and `baselines/` and your `runs/<prefix>/` are copied in (files over 25 MB and your `runs/<prefix>/remote/` are
  left out); `PYTHONPATH` contains `src/` and `baselines/`;
- `data/` is an exact copy of this room's `data/` (the same public development data; nothing else);
- the network is blocked and no other program may be started; the simulation service is NOT available (scripts that use SimClient
  must run in the sandbox here);
- numerics: the same pinned numerical stack as the sandbox; CPU classes use the development machine's kernel settings; GPU classes
  run PyPI's CUDA build of the same torch version (GPU results can differ from CPU results in the last digits; seed and report).

Resource classes (`--class`): %s.
Inside the job, `P4_REMOTE_CPUS` holds the CPU count (threads are set to it) and `P4_REMOTE_GPU` the GPU type (empty on CPU classes).

Usage (from the room root, through the sandbox):

    sbx python tools/remote_run.py submit runs/<prefix>/exp.py --class gpu-l4 --timeout 3600 -- --system s1 --seed 1
    sbx python tools/remote_run.py wait <job_id> [<job_id> ...]
    sbx python tools/remote_run.py status <job_id>

Results: every new or changed file under your `runs/<prefix>/` comes back under `runs/<prefix>/remote/<job_id>/runs/<prefix>/...`,
with the job's exit code, stdout / stderr tails, peak memory and wall time (`runs/_remote/queue/results/`). Write outputs under
`runs/<prefix>/`. Never end your turn to wait for a job: poll with `wait`.
'''


def install_client() -> int:
    tools = ROOT / "research" / "phase4" / "review_contracts"
    tools.mkdir(parents=True, exist_ok=True)
    classes = {k: {"cpu": v[0], "memory_gb": v[1] // 1024, "gpu": v[2]} for k, v in CLASSES.items()}
    (tools / "remote_run_client.py").write_text(CLIENT % json.dumps(classes), encoding="utf-8", newline="\n")
    desc = "; ".join(f"{k} = {v[0]:g} CPUs / {v[1] // 1024} GB" + (f" + 1 {v[2]}" if v[2] else "") for k, v in CLASSES.items())
    (tools / "remote_runner_notes.md").write_text(NOTES % desc, encoding="utf-8", newline="\n")
    print("wrote", tools / "remote_run_client.py", tools / "remote_runner_notes.md")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("sync-data", "daemon", "install-client", "smoke"))
    ap.add_argument("--room", type=Path, default=DEFAULT_ROOM)
    ap.add_argument("--class", dest="klass", default="small")
    ap.add_argument("--script", default="runs/smoke/smoke_job.py")
    ap.add_argument("--no-volume", action="store_true", help="smoke only: run without the dev-data volume")
    ap.add_argument("--volume", default=DEV_VOLUME, help="dev-data volume (brainir-p4-devdata*; tests use a separate one)")
    args = ap.parse_args(argv)
    if args.cmd == "sync-data":
        return sync_data(args.room, volume=args.volume)
    if args.cmd == "install-client":
        return install_client()
    if args.cmd == "smoke":
        return smoke(args.room, args.klass, args.script, with_volume=not args.no_volume, volume=args.volume)
    return daemon(args.room, volume=args.volume)


if __name__ == "__main__":
    raise SystemExit(main())
