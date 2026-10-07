"""LOCAL execution of the Modal backend's payloads (ORCHESTRATOR SIDE; the user's directive of 2026-09-28: no further Modal spend;
research/phase4/LOCAL_EXECUTION_PLAN.md).

`LocalBackend` has the interface of `p4modal.app.Backend` and runs THE SAME container-side entry point (`p4modal.remote.dispatch`) in
worker threads of this process, which must be the pinned Linux image (scripts/p4/linux_driver.py --local): the host gate and the
numerics self-test run first (a host that is not on the reference platform, or computes the recorded reference differently, is
refused: the run stops), the three volumes are LOCAL directories mounted at the containers' paths (/fitvol, /evalvol, /storevol;
reload and commit are no-ops, remote.LOCAL_VOLUMES), and a `call` payload runs in a fresh job subprocess exactly as in a Modal
container. So a driver computes the same records locally that it would compute on Modal. Selected by the environment
(P4_BACKEND=local rebinds `app.Backend` to this class), so drivers need no change.

Memory safety (the machine is shared with the user's own work): at most P4_LOCAL_WORKERS payloads run at once; a new payload starts
only while the host has at least P4_LOCAL_MIN_FREE_MB free (default 6144); below P4_LOCAL_KILL_FREE_MB (default 3072) the YOUNGEST
running job subprocess and its children are stopped and its payload is run again once memory is back (payloads are units that
drivers make idempotent: resume directories, done files, per-unit results). The host's free memory is not visible inside the Docker VM:
a host-side feeder (scripts/p4/local_memfeed.sh) writes it to P4_LOCAL_GUARD_FILE every 2 s; a missing or stale reading pauses new
payloads (never guesses). Cost records say $0 (no Modal container is started)."""

from __future__ import annotations

import concurrent.futures as cf
import hashlib
import io
import json
import os
import shutil
import signal
import tarfile
import threading
import time
import traceback
import uuid
from pathlib import Path

from . import app as _app

MOUNTS = {"fit": Path("/fitvol"), "eval": Path("/evalvol"), "store": Path("/storevol")}
GUARD_STALE_S = 30.0
MAX_INFRA_RETRIES = 5


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def host_free_mb(path: str | None) -> int | None:
    """The host's free memory in MB from the feeder's file ("<mb> <unix time>"); None when missing, unreadable or stale."""
    if not path:
        return None
    try:
        parts = Path(path).read_text(encoding="utf-8").split()
        mb, ts = int(parts[0]), float(parts[1])
    except (OSError, ValueError, IndexError):
        return None
    return mb if time.time() - ts <= GUARD_STALE_S else None


def _children(pid: int) -> list[int]:
    out = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            ppid = int((d / "stat").read_text().rsplit(")", 1)[1].split()[1])
        except (OSError, ValueError, IndexError):
            continue
        if ppid == pid:
            out.append(int(d.name))
    return out


def _tree(pid: int) -> list[int]:
    todo, seen = [pid], []
    while todo:
        p = todo.pop()
        seen.append(p)
        todo += _children(p)
    return seen


def job_processes() -> list[tuple[float, int]]:
    """(start time in clock ticks, pid) of the running job subprocesses (`python -m brainir_causal.p4modal.jobproc ...`)."""
    out = []
    for d in Path("/proc").iterdir():
        if not d.name.isdigit():
            continue
        try:
            cmd = (d / "cmdline").read_bytes().split(b"\0")
            if b"brainir_causal.p4modal.jobproc" not in cmd:
                continue
            start = float((d / "stat").read_text().rsplit(")", 1)[1].split()[19])
        except (OSError, ValueError, IndexError):
            continue
        out.append((start, int(d.name)))
    return sorted(out)


class LocalBackend(_app.Backend):
    """p4modal.app.Backend's interface, executed locally (module docstring)."""

    def __init__(self, classes: list[str] | None = None, max_containers: int | None = None, extra_dirs: dict | None = None,
                 app_name: str = "brainir-p4-local", verbose: bool = True, *, workers: int | None = None):
        self.classes = classes or list(_app.CLASSES)
        self.app, self.fns = None, {}
        self.vols = dict(MOUNTS)
        self.costs: list[dict] = []
        self.refusals: dict = {}
        self.infra_faults: dict = {}
        self.hosts: dict = {}
        self.verbose = verbose
        self._ctx = None
        self.app_id = f"local-{uuid.uuid4().hex[:8]}"
        self.workers = max(1, int(workers or _env_int("P4_LOCAL_WORKERS", 1)))
        self.guard_file = os.environ.get("P4_LOCAL_GUARD_FILE")
        self.min_free_mb = _env_int("P4_LOCAL_MIN_FREE_MB", 6144)
        self.kill_free_mb = _env_int("P4_LOCAL_KILL_FREE_MB", 3072)
        self.memory_kills = 0
        self.memory_waits_s = 0.0
        self.host: dict = {}
        self._stop = threading.Event()
        self._guard = None

    # ------------------------------------------------------------------------ lifecycle: the reference platform or nothing
    def __enter__(self):
        if os.environ.get("P4_LOCAL_VOLUMES") != "1":
            raise SystemExit("the local backend needs the local volume mounts (run the driver with scripts/p4/linux_driver.py --local)")
        missing = [str(m) for m in MOUNTS.values() if not m.is_dir()]
        if missing:
            raise SystemExit(f"local volume mounts missing: {missing}")
        from . import gate
        h = gate.host_cpu()
        if not gate.admissible(h):
            raise SystemExit(f"this host is not on the reference platform (host gate): {h}")
        st = gate.numerics_selftest()
        if st.get("stale") or not st.get("ok"):
            raise SystemExit(f"numerics self-test failed on this host: {json.dumps({k: st.get(k) for k in ('stale', 'mismatch', 'errors')})}"[:2000])
        self.host = h
        self.selftest = {k: st.get(k) for k in ("ok", "s", "wall_s", "host_class", "reference_class")}
        if self.verbose:
            print(f"[local backend] {h.get('model')}: gate ok, numerics self-test ok; {self.workers} worker(s), new work only with >= "
                  f"{self.min_free_mb} MB free (feeder {'on' if self.guard_file else 'OFF'})", flush=True)
        self._guard = threading.Thread(target=self._guard_loop, daemon=True)
        self._guard.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        return False

    # ------------------------------------------------------------------------ memory guard
    def _free(self) -> int | None:
        return host_free_mb(self.guard_file) if self.guard_file else None

    def _wait_memory(self) -> None:
        if not self.guard_file:
            return
        said, t0 = False, time.time()
        while not self._stop.is_set():
            f = self._free()
            if f is not None and f >= self.min_free_mb:
                break
            if not said and self.verbose:
                print(f"[local backend] waiting: host free memory {f if f is not None else 'unknown'} MB < {self.min_free_mb} MB", flush=True)
                said = True
            time.sleep(5.0)
        self.memory_waits_s += time.time() - t0

    def _guard_loop(self) -> None:
        while not self._stop.is_set():
            f = self._free()
            if f is not None and f < self.kill_free_mb:
                procs = job_processes()
                if procs:
                    _start, pid = procs[-1]                           # the youngest job loses the least work
                    for q in reversed(_tree(pid)):
                        try:
                            os.kill(q, signal.SIGKILL)
                        except OSError:
                            pass
                    self.memory_kills += 1
                    if self.verbose:
                        print(f"[local backend] host free memory {f} MB < {self.kill_free_mb} MB: stopped job process {pid}; its "
                              "payload runs again when memory is back", flush=True)
                    time.sleep(10.0)
            time.sleep(2.0)

    # ------------------------------------------------------------------------ execution
    def run(self, payloads: list[dict], cls: str, label: str = "", on_result=None, poll_s: float = 5.0,
            batch_s: float | None = None) -> list:
        """Results in input order, as the Modal backend returns them (a job's own error is a result dict with "error"; an
        infrastructure fault of the isolation layer, or a job stopped by the memory guard, is run again)."""
        from . import remote
        n = len(payloads)
        out: list = [None] * n
        lock = threading.Lock()
        t_run = time.time()

        def one(i: int) -> None:
            p = dict(payloads[i])
            tries = 0
            while True:
                self._wait_memory()
                kills0 = self.memory_kills
                t0 = time.time()
                try:
                    r = remote.dispatch(p)
                except Exception as e:  # noqa: BLE001 - a deterministic job error is a RESULT (as in the Modal function)
                    r = {"error": f"{type(e).__name__}: {e}"[:2000], "traceback": traceback.format_exc()[-6000:]}
                except BaseException as e:
                    if not any(c.__name__ == "InfraFault" for c in type(e).__mro__):
                        raise
                    r = {"__infra__": True, "error": f"InfraFault ({type(e).__name__}): {e}"[:2000]}
                killed = self.memory_kills > kills0 and isinstance(r, dict) and (
                    r.get("__infra__") or "signal_crashes" in r or str(r.get("error", "")).startswith("job exit -"))
                if isinstance(r, dict) and (r.get("__infra__") or killed) and tries < MAX_INFRA_RETRIES:
                    tries += 1
                    with lock:
                        self.infra_faults[cls] = self.infra_faults.get(cls, 0) + 1
                    continue
                if isinstance(r, dict):
                    r["__tag"] = p.get("__tag")
                    r["__host__"] = self.host
                    r["__span"] = [round(t0, 3), round(time.time(), 3)]
                    r["__local"] = True
                with lock:
                    out[i] = r
                    model = (self.host or {}).get("model")
                    if model:
                        self.hosts[model] = self.hosts.get(model, 0) + 1
                    if on_result is not None:
                        on_result(i, r)
                return

        with cf.ThreadPoolExecutor(max_workers=min(self.workers, max(1, n))) as ex:
            list(ex.map(one, range(n)))
        self.costs.append({"label": label, "cls": cls, "n": n, "usd_approx": 0.0, "wall_s": round(time.time() - t_run, 1), "local": True})
        return out

    def run_eager(self, payloads: list[dict], cls: str, label: str = "", poll_s: float = 2.0) -> list:
        return self.run(payloads, cls, label)

    # ------------------------------------------------------------------------ volumes are local directories
    def stage_put(self, data: bytes, vol: str = "store") -> dict:
        if vol not in ("store", "eval"):
            raise ValueError(f"no staging area on volume {vol!r}")
        sha = hashlib.sha256(data).hexdigest()
        p = MOUNTS[vol] / "_staged" / sha[:2] / f"{sha}.bin"
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(f".{uuid.uuid4().hex[:8]}.tmp")
            tmp.write_bytes(data)
            os.replace(tmp, p)
        return {"stage": sha, "size": len(data), "vol": vol}

    def stage_get(self, ref: dict) -> bytes:
        sha = str(ref["stage"])
        if len(sha) != 64 or any(c not in "0123456789abcdef" for c in sha):
            raise ValueError(f"malformed staged ref {sha!r}")
        data = (MOUNTS[ref.get("vol", "store")] / "_staged" / sha[:2] / f"{sha}.bin").read_bytes()
        if hashlib.sha256(data).hexdigest() != sha:
            raise RuntimeError(f"staged blob {sha} is corrupt")
        return data

    def stage_clear(self, refs) -> int:
        n = 0
        for ref in refs or []:
            if isinstance(ref, dict) and ref.get("stage"):
                sha = ref["stage"]
                p = MOUNTS[ref.get("vol", "store")] / "_staged" / sha[:2] / f"{sha}.bin"
                if p.exists():
                    p.unlink()
                    n += 1
        return n

    def methods_key(self, mdir: Path) -> str:
        blob = _app.tar_bytes(Path(mdir))
        key = hashlib.sha256(blob).hexdigest()[:16]
        p = MOUNTS["fit"] / "methods" / f"{key}.tar"
        if not p.exists():
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_bytes(blob)
            os.replace(tmp, p)
        return key

    def upload_dir(self, volume_name: str, base: Path, dest: str, files: list[Path] | None = None, *, replace: bool = True) -> dict:
        base = Path(base)
        files = sorted(files if files is not None else [q for q in base.rglob("*") if q.is_file()])
        target = MOUNTS[volume_name] / dest.strip("/")
        if replace and target.exists():
            shutil.rmtree(target)
        sha, total = {}, 0
        for q in files:
            data = q.read_bytes()
            rel = q.relative_to(base).as_posix()
            sha[rel] = hashlib.sha256(data).hexdigest()
            total += len(data)
            t = target / rel
            t.parent.mkdir(parents=True, exist_ok=True)
            t.write_bytes(data)
        return {"n_files": len(files), "tar_bytes": total, "sha256": sha}

    def download_dir(self, volume_name: str, remote_dir: str, local_dir: Path, *, replace: bool = True) -> dict:
        src = MOUNTS[volume_name] / remote_dir.strip("/")
        if not src.is_dir():
            raise RuntimeError(f"{volume_name}:{remote_dir} does not exist on the local volume")
        local_dir = Path(local_dir)
        t0 = time.time()
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w") as tf:                 # the same bytes the Modal path hashes (a tar of the directory)
            for q in sorted(p for p in src.rglob("*") if p.is_file()):
                tf.add(q, arcname=q.relative_to(src).as_posix())
        blob = buf.getvalue()
        if replace and local_dir.exists():
            shutil.rmtree(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        n = 0
        for q in sorted(p for p in src.rglob("*") if p.is_file()):
            t = local_dir / q.relative_to(src)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(q, t)
            n += 1
        return {"volume": volume_name, "dir": remote_dir, "n_files": n, "bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest(),
                "download_s": round(time.time() - t0, 1)}

    def cost_summary(self) -> dict:
        return {"app_id": self.app_id, "calls": self.costs, "usd_approx_total": 0.0, "local": True, "refusals": {},
                "infra_faults": dict(self.infra_faults), "memory_kills": self.memory_kills,
                "memory_waits_s": round(self.memory_waits_s, 1), "selftest_refusals": [], "selftest_counts": {}, "hosts": self.hosts}
