"""The simulation service's worker pool on the REFERENCE PLATFORM (ORCHESTRATOR SIDE; LOG P4-D32, P4-D33).

The synthetic generator (like every numerics-sensitive engine) is bit-identical across Linux environments with the pinned stack (the
Modal containers and the local sandbox image `brainir-p4-sandbox:1`: 50 / 50 dev content hashes equal) but not on the Windows host
(11 / 50). The developers' simulation service therefore keeps its TRUSTED HOST PART on the host (`simservice.SimServer`: the queue,
identity tokens, the public policy, budgets, ledgers, served-key mapping, public restart sources and the Modal client for real FULL
networks) and runs every LOCAL simulation (synthetic systems, real mechanisms) in ONE container of the pinned image:

    pool = DockerPool(store_root=..., bridge_dir=..., bundle=systems.BUNDLE, warm=[(tier, seed), ...]).start()
    SimServer(room, systems, store_root, pool=pool, ...)          # pool.submit(simservice.run_job, job) -> Future

The image: `brainir-p4-simsvc:1` (docker/p4simservice: the pinned agent sandbox image plus duckdb, which the real engine's graph
loader imports, at the Modal images' pinned version; installed --no-deps, the numerical stack unchanged; `worker_image`).
The container: `--network none`, read-only root filesystem with a private /tmp, all capabilities dropped, no new privileges, an
unprivileged user, CPU / memory caps, the host gate's numerics pins (`p4modal.images.CPU_PINS`, one BLAS thread), the repository code
READ-ONLY (phase4/src, src/brainir, the previous public bundle at its repository-relative path, the hash-locked generator at
`suites.GENERATOR_CONTAINER`) and exactly two read-write mounts, both outside every room: the service store and the bridge directory.
It never sees a room, a queue, a token table or a ledger. Jobs and results cross as FILES in the bridge directory:

    jobs/<id>.json        run_job's argument, host paths replaced by container paths (store root, bundle)
    results/<id>.json     {"store_key", "computed"} or {"error"}            results/<id>.npz   t, x, u, y (allow_pickle=False)
    heartbeat             rewritten by the host every HEARTBEAT_S with a new counter; the container exits when its content has not
                          changed for HEARTBEAT_STALE_S of the CONTAINER's monotonic clock (host and VM clocks may drift)
    ready.json            written by the container once its worker processes are up (generators registered, suites warmed)
    docker_run.json       the exact command and mounts the host used (for launch records)

Only `simservice.run_job` runs in the container (any other callable submitted is executed in-process: warm-up no-ops). A job error
comes back as its message and ends as the service's generic "simulation failed (reference ...)"; the details stay in the service's
error log, outside the room.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import uuid
from concurrent.futures import Future
from pathlib import Path

import numpy as np

CONTAINER_STORE = "/svc/store"
CONTAINER_BRIDGE = "/svc/bridge"
REPO = "/repo"
HEARTBEAT_S = 5.0
HEARTBEAT_STALE_S = 90.0
RESULT_ARRAYS = ("t", "x", "u", "y")
READ_RETRIES = 1000                    # x 20 ms: a result file that stays unreadable for 20 s fails its job
ROOT = Path(__file__).resolve().parents[3]


def worker_image() -> str:
    """The pinned id of the service worker image (docker/p4simservice/image.json; `scripts/p4/simservice_docker.py build-image`)."""
    p = ROOT / "docker" / "p4simservice" / "image.json"
    if not p.exists():
        raise RuntimeError("the simulation-service worker image is not built (scripts/p4/simservice_docker.py build-image)")
    return json.loads(p.read_text(encoding="utf-8"))["id"]


def is_run_job(fn) -> bool:
    """True for `simservice.run_job` under any module name (the package module or a `__main__` copy of the file)."""
    code = getattr(fn, "__code__", None)
    return getattr(fn, "__name__", None) == "run_job" and code is not None and \
        str(code.co_filename).replace("\\", "/").endswith("brainir_causal/simservice.py")


def _atomic_write(path: Path, data: bytes) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex[:8]}.tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


# ================================================================================================================ host side
class DockerPool:
    """An executor-like pool whose `run_job` calls run in a container of the pinned image (module docstring). `warm`: (tier, seed)
    synthetic suites every worker builds at start (so the first requests do not pay for it)."""

    def __init__(self, *, store_root: Path | str, bridge_dir: Path | str, bundle: Path | str | None = None, workers: int = 4,
                 cpus: float = 4.0, mem_gb: int = 8, image: str | None = None, warm: list | tuple = (), name: str | None = None,
                 generator_dir: Path | str | None = None, start_timeout_s: float = 900.0):
        from . import suites as SU
        self.store_root, self.bridge = Path(store_root).resolve(), Path(bridge_dir).resolve()
        self.bundle = Path(bundle).resolve() if bundle else None
        self.generator_dir = Path(generator_dir).resolve() if generator_dir else (ROOT / SU.GENERATOR_REL).resolve()
        self.generator_container = SU.GENERATOR_CONTAINER
        self.workers, self.cpus, self.mem_gb = int(workers), float(cpus), int(mem_gb)
        self.image = image
        self.warm = [(str(t), int(s)) for t, s in warm]
        self.name = name or f"p4simsvc-{uuid.uuid4().hex[:10]}"
        self.start_timeout_s = float(start_timeout_s)
        self._futures: dict[str, Future] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._beat = 0
        self._retries: dict[str, int] = {}
        self.command: list[str] | None = None

    # ------------------------------------------------------------------------ container
    def bundle_container(self) -> str | None:
        if self.bundle is None:
            return None
        try:
            rel = self.bundle.relative_to(ROOT).as_posix()
        except ValueError:
            rel = "benchmarks/_bundle/" + self.bundle.name
        return f"{REPO}/{rel}"

    def mounts(self) -> list[tuple[Path, str, str]]:
        m = [(ROOT / "phase4" / "src", f"{REPO}/phase4/src", "ro"), (ROOT / "src", f"{REPO}/src", "ro"),
             (self.generator_dir, self.generator_container, "ro"), (self.store_root, CONTAINER_STORE, "rw"), (self.bridge, CONTAINER_BRIDGE, "rw")]
        if self.bundle is not None:
            m.insert(2, (self.bundle, self.bundle_container(), "ro"))
        return m

    def docker_command(self) -> list[str]:
        from .isolation import docker_exe
        from .p4modal.images import CPU_PINS
        env = {"PYTHONPATH": f"{REPO}/phase4/src:{REPO}/src", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "HOME": "/tmp",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1", "MKL_NUM_THREADS": "1", **CPU_PINS}
        cmd = [docker_exe(), "run", "-d", "--rm", "--pull", "never", "--name", self.name, "--network", "none", "--read-only",
               "--tmpfs", "/tmp:rw,nosuid,size=2g", "--cap-drop", "ALL", "--security-opt", "no-new-privileges", "--pids-limit", "512",
               "--user", "1000:1000", "--cpus", f"{self.cpus:g}", "--memory", f"{self.mem_gb}g", "--memory-swap", f"{self.mem_gb}g",
               "--label", "brainir.p4.role=simservice-workers"]
        for k, v in sorted(env.items()):
            cmd += ["-e", f"{k}={v}"]
        for src, dst, mode in self.mounts():
            cmd += ["-v", f"{str(src).replace(chr(92), '/')}:{dst}:{mode}"]
        cmd += [self.image or worker_image(), "python", "-m", "brainir_causal.simdocker", "worker", "--bridge", CONTAINER_BRIDGE,
                "--workers", str(self.workers), "--generator-dir", self.generator_container]
        for t, s in self.warm:
            cmd += ["--warm", f"{t}:{s}"]
        return cmd

    def start(self) -> DockerPool:
        for d in ("jobs", "results"):
            (self.bridge / d).mkdir(parents=True, exist_ok=True)
            for f in (self.bridge / d).iterdir():                   # a fresh bridge: stale jobs / results of an earlier run removed
                if f.is_file():
                    f.unlink()
        for f in ("ready.json", "worker_error.txt"):
            (self.bridge / f).unlink(missing_ok=True)
        self.store_root.mkdir(parents=True, exist_ok=True)
        self._touch()
        self.command = self.docker_command()
        _atomic_write(self.bridge / "docker_run.json", json.dumps({"name": self.name, "command": self.command,
                                                                   "mounts": [[str(a), b, c] for a, b, c in self.mounts()],
                                                                   "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                                                                  indent=1).encode())
        r = subprocess.run(self.command, capture_output=True, text=True, timeout=300, check=False)
        if r.returncode != 0:
            raise RuntimeError(f"docker run failed: {r.stderr[-2000:]}")
        t0 = time.time()
        while not (self.bridge / "ready.json").exists():
            if (self.bridge / "worker_error.txt").exists():
                raise RuntimeError("the simulation worker container failed: " + (self.bridge / "worker_error.txt").read_text(encoding="utf-8")[-3000:])
            if not self.running():
                raise RuntimeError(f"the simulation worker container {self.name} exited during start: {self.logs()[-3000:]}")
            if time.time() - t0 > self.start_timeout_s:
                self.shutdown()
                raise TimeoutError("the simulation worker container did not become ready")
            self._touch()
            time.sleep(0.5)
        for fn in (self._poll, self._heartbeat):
            th = threading.Thread(target=fn, daemon=True)
            th.start()
            self._threads.append(th)
        return self

    def running(self) -> bool:
        from .isolation import docker_exe
        r = subprocess.run([docker_exe(), "inspect", "-f", "{{.State.Running}}", self.name], capture_output=True, text=True, timeout=60, check=False)
        return r.returncode == 0 and r.stdout.strip() == "true"

    def logs(self) -> str:
        from .isolation import docker_exe
        r = subprocess.run([docker_exe(), "logs", "--tail", "200", self.name], capture_output=True, text=True, timeout=60, check=False)
        return (r.stdout or "") + (r.stderr or "")

    def _touch(self) -> None:
        self._beat += 1
        _atomic_write(self.bridge / "heartbeat", f"{self.name}:{self._beat}".encode())

    def _heartbeat(self) -> None:
        while not self._stop.wait(HEARTBEAT_S):
            try:
                self._touch()
            except OSError:
                pass

    # ------------------------------------------------------------------------ jobs
    def translate(self, job: dict) -> dict:
        """run_job's argument with host paths replaced by container paths (a store namespace below the pool's store root keeps its
        relative path: simservice.SimServer.store_for; any other store is refused)."""
        j = dict(job)
        rel = Path(job["store_root"]).resolve().relative_to(self.store_root)       # ValueError outside the mounted store
        j["store_root"] = CONTAINER_STORE + "".join("/" + part for part in rel.parts)
        if j.get("bundle"):
            j["bundle"] = self.bundle_container()
        return j

    def submit(self, fn, *args, **kwargs) -> Future:
        """`simservice.run_job` runs in the container; a builtin no-op (warm-up, e.g. submit(int, 0)) runs here; anything else is refused
        (never a silent simulation on the host)."""
        if not is_run_job(fn):
            if getattr(fn, "__module__", None) != "builtins":
                raise TypeError(f"DockerPool runs only simservice.run_job, not {fn!r}")
            f: Future = Future()
            try:
                f.set_result(fn(*args, **kwargs))
            except Exception as e:  # noqa: BLE001
                f.set_exception(e)
            return f
        job = args[0] if args else kwargs["job"]
        jid = uuid.uuid4().hex
        f = Future()
        with self._lock:
            self._futures[jid] = f
        _atomic_write(self.bridge / "jobs" / f"{jid}.json", json.dumps({"op": "run", "job": self.translate(job)}).encode())
        return f

    def call(self, op: dict, timeout_s: float = 900.0) -> dict:
        """A synchronous bridge operation (e.g. {"op": "describe", "systems": [...]}); returns its JSON result."""
        jid = uuid.uuid4().hex
        f: Future = Future()
        with self._lock:
            self._futures[jid] = f
        _atomic_write(self.bridge / "jobs" / f"{jid}.json", json.dumps(op).encode())
        return f.result(timeout=timeout_s)

    def describe(self, sysdefs: list[dict]) -> dict:
        """{system_id: engine_id} of synthetic systems, computed in the container (the host never builds generator systems)."""
        return self.call({"op": "describe", "systems": sysdefs})["engines"]

    def _poll(self) -> None:
        last_check = time.time()
        while not self._stop.is_set():
            with self._lock:
                ids = list(self._futures)
            for jid in ids:
                meta_p = self.bridge / "results" / f"{jid}.json"
                if not meta_p.exists():
                    continue
                npz = self.bridge / "results" / f"{jid}.npz"
                try:
                    meta = json.loads(meta_p.read_text(encoding="utf-8"))
                    arrays = {}
                    if npz.exists():
                        with np.load(npz, allow_pickle=False) as z:
                            arrays = {k: np.array(z[k]) for k in z.files}
                except Exception as e:  # noqa: BLE001 - a sharing violation while the VM side renames, or a file not yet complete
                    self._retries[jid] = self._retries.get(jid, 0) + 1
                    if self._retries[jid] < READ_RETRIES:
                        continue
                    with self._lock:
                        f = self._futures.pop(jid, None)
                    if f is not None:
                        f.set_exception(e)
                    continue
                self._retries.pop(jid, None)
                for q in (npz, meta_p):
                    try:
                        q.unlink(missing_ok=True)
                    except OSError:
                        pass                                          # removed at the next start of the bridge
                with self._lock:
                    f = self._futures.pop(jid, None)
                if f is None:
                    continue
                if meta.get("error"):
                    f.set_exception(RuntimeError(str(meta["error"])))
                else:
                    f.set_result({**{k: v for k, v in meta.items() if k != "op"}, **arrays})
            if time.time() - last_check > 15.0:
                last_check = time.time()
                with self._lock:
                    pending = bool(self._futures)
                if pending and not self.running():
                    err = RuntimeError(f"the simulation worker container {self.name} is not running")
                    with self._lock:
                        futs, self._futures = list(self._futures.values()), {}
                    for f in futs:
                        f.set_exception(err)
            time.sleep(0.02)

    def shutdown(self, wait: bool = False, cancel_futures: bool = True) -> None:
        from .isolation import docker_exe
        self._stop.set()
        subprocess.run([docker_exe(), "stop", "-t", "5", self.name], capture_output=True, text=True, timeout=120, check=False)
        if cancel_futures:
            with self._lock:
                futs, self._futures = list(self._futures.values()), {}
            for f in futs:
                f.cancel() or (f.done() or f.set_exception(RuntimeError("the pool was shut down")))


# ================================================================================================================ container side
_GEN = "default"


def _worker_init(generator_dir: str, warm: list) -> None:
    from .simservice import worker_init
    worker_init({_GEN: (generator_dir, "p4synth")}, 1)
    from .synthadapter import suite_systems
    for tier, seed in warm:
        suite_systems(str(tier), int(seed), _GEN)


def _write_result(bridge: Path, jid: str, meta: dict, arrays: dict | None = None) -> None:
    res = bridge / "results"
    if arrays:
        tmp = res / f".{jid}.tmp.npz"
        np.savez(tmp, **{k: np.asarray(v) for k, v in arrays.items()})
        os.replace(tmp, res / f"{jid}.npz")
    _atomic_write(res / f"{jid}.json", json.dumps(meta, default=str).encode())


def _run_one(job: dict) -> dict:
    from .simservice import run_job
    return run_job(job)


def worker_main(bridge: Path, workers: int, generator_dir: str, warm: list) -> int:
    from concurrent.futures import ProcessPoolExecutor
    try:
        _worker_init(generator_dir, warm)                            # this process: describe / engine ids
        pool = ProcessPoolExecutor(max_workers=int(workers), initializer=_worker_init, initargs=(generator_dir, warm))
        for f in [pool.submit(time.sleep, 0.2) for _ in range(int(workers))]:     # start (and warm) every worker process now
            f.result()
    except Exception:  # noqa: BLE001
        _atomic_write(bridge / "worker_error.txt", traceback.format_exc().encode())
        return 1
    _atomic_write(bridge / "ready.json", json.dumps({"workers": int(workers), "warm": warm, "python": sys.version,
                                                     "time": time.time()}).encode())
    running: dict = {}
    jobs = bridge / "jobs"
    beat, beat_seen = None, time.monotonic()
    while True:
        try:
            b = (bridge / "heartbeat").read_text(encoding="utf-8")
        except OSError:
            b = beat
        if b != beat:
            beat, beat_seen = b, time.monotonic()
        elif time.monotonic() - beat_seen > HEARTBEAT_STALE_S:
            print("simdocker: host heartbeat stale; exiting", flush=True)
            pool.shutdown(wait=False, cancel_futures=True)
            return 0
        for p in sorted(jobs.glob("*.json")):
            jid = p.stem
            try:
                req = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue                                              # still being written (atomic rename makes this rare)
            p.unlink(missing_ok=True)
            op = req.get("op")
            if op == "run":
                running[jid] = pool.submit(_run_one, req["job"])
            elif op == "describe":
                try:
                    from .synthadapter import suite_systems
                    eng = {}
                    for s in req.get("systems") or []:
                        eng[s["system_id"]] = str(suite_systems(s["tier"], int(s["suite_seed"]), _GEN)[s["system_id"]].engine_id)
                    _write_result(bridge, jid, {"op": "describe", "engines": eng})
                except Exception as e:  # noqa: BLE001
                    _write_result(bridge, jid, {"error": f"{type(e).__name__}: {e}"})
            else:
                _write_result(bridge, jid, {"error": f"unknown op {op!r}"})
        for jid, fut in list(running.items()):
            if not fut.done():
                continue
            del running[jid]
            try:
                out = fut.result()
                _write_result(bridge, jid, {"store_key": out["store_key"], "computed": bool(out.get("computed"))},
                              {k: out[k] for k in RESULT_ARRAYS})
            except Exception as e:  # noqa: BLE001
                _write_result(bridge, jid, {"error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-3000:]})
        time.sleep(0.01)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("worker")
    w.add_argument("--bridge", type=Path, required=True)
    w.add_argument("--workers", type=int, default=4)
    w.add_argument("--generator-dir", required=True)
    w.add_argument("--warm", action="append", default=[])
    args = ap.parse_args(argv)
    warm = [(x.rsplit(":", 1)[0], int(x.rsplit(":", 1)[1])) for x in args.warm]
    return worker_main(args.bridge, args.workers, args.generator_dir, warm)


if __name__ == "__main__":
    raise SystemExit(main())
