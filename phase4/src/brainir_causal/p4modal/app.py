"""Orchestrator side of the Phase 4 Modal backend (goal5 sections 62-65, 97). Never imported inside a method room.

    from brainir_causal.p4modal.app import Backend
    with Backend() as be:                                   # an ephemeral app for the duration of the block
        res = be.simulate(items)                            # host-gated real-engine batches, content-addressed volume store
        out = be.call("pkg.mod:function", [[arg1], [arg2]])  # orchestrator functions in fresh subprocesses
        out = be.run_methods(payloads, cls="fit_s")         # guarded method jobs (fit / eval mode), optional per-job simulator
    svc = SimServer(..., remote_backend=be.remote_backend())  # full-network simulations of the local simulation service on Modal

Worker classes (`CLASSES`): each is one Modal function with fixed resources, mounted volumes and host-gate setting; payloads carry
their job kind (`remote.dispatch`). The workspace runs at most about 100 containers at once (measured in Phase 3), so the default
`max_containers` per class is 100 and heavy simulation classes use large containers with a process pool inside.

Isolation (the Phase 3 design, Phase 4 names): the fit volume (`brainir-p4-fit`: fit views, method snapshots) and the store volume
(`brainir-p4-store`: PUBLIC / development trajectory records) are the only volumes fit classes mount; held-out and hidden data live on
the eval volume (`brainir-p4-eval`), which only eval / sim_eval / util classes mount. Every method subprocess installs the guard
(brainir_causal.runguard) before any method code runs. No brainir-p3-* volume is ever mounted.

Reproducibility: CPU classes are host-gated (no AVX-512; the development machine's kernels; gate.py) unless a payload asks otherwise;
refused inputs are re-submitted until they land on an admissible host. GPU classes are not gated (their results are compared with CPU
runs by brainir_causal.equiv).
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import time
import uuid
from pathlib import Path

from . import images

APP_NAME = "brainir-p4"
VOLUMES = {"fit": "brainir-p4-fit", "eval": "brainir-p4-eval", "store": "brainir-p4-store"}
MOUNT = {"fit": "/fitvol", "eval": "/evalvol", "store": "/storevol"}
MAX_CONTAINERS = 100

# Modal list prices (modal.com/pricing, read 2026-09-26; standard, preemptible), USD per second; for approximate job records only
CORE_S, GIB_S = 0.0000131, 0.00000222
GPU_S = {"B300": 0.001972, "B200": 0.001736, "H200": 0.001261, "H100": 0.001097, "RTX-PRO-6000": 0.000842, "A100-80GB": 0.000694,
         "A100-40GB": 0.000583, "L40S": 0.000542, "A10": 0.000306, "L4": 0.000222, "T4": 0.000164}

CLASSES = {
    # name: cpu = physical cores, memory in MiB, gpu, volumes, host gate, timeout (s)
    "sim":      {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("store",), "gated": True, "timeout": 3 * 3600},
    "sim_eval": {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("eval",), "gated": True, "timeout": 3 * 3600},
    "fit_s":    {"cpu": 4.0, "memory": 16384, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 4 * 3600},
    "fit_m":    {"cpu": 8.0, "memory": 32768, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 6 * 3600},
    "fit_l":    {"cpu": 16.0, "memory": 65536, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 8 * 3600},
    "fit_xl":   {"cpu": 32.0, "memory": 131072, "gpu": None, "volumes": ("fit", "store"), "gated": True, "timeout": 8 * 3600},
    "eval_s":   {"cpu": 4.0, "memory": 32768, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 4 * 3600},
    "eval_l":   {"cpu": 8.0, "memory": 65536, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": True, "timeout": 6 * 3600},
    "util":     {"cpu": 2.0, "memory": 8192, "gpu": None, "volumes": ("fit", "eval", "store"), "gated": False, "timeout": 2 * 3600},
    # GPU classes (research/phase4/GPU_BENCHMARK.md): RTX-PRO-6000 and B200 were the fastest for latency-bound sequential rollouts,
    # H100 / H200 / B200 for large-batch throughput-bound training; L4 is the cheap small class
    "gpu_rtx6000": {"cpu": 8.0, "memory": 65536, "gpu": "RTX-PRO-6000", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_l4":   {"cpu": 4.0, "memory": 32768, "gpu": "L4", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_l40s": {"cpu": 4.0, "memory": 32768, "gpu": "L40S", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_a100": {"cpu": 8.0, "memory": 65536, "gpu": "A100-80GB", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_h100": {"cpu": 8.0, "memory": 65536, "gpu": "H100", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_h200": {"cpu": 8.0, "memory": 65536, "gpu": "H200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
    "gpu_b200": {"cpu": 8.0, "memory": 65536, "gpu": "B200", "volumes": ("fit", "store"), "gated": False, "timeout": 6 * 3600},
}
MAX_REFUSALS = 400            # per input; a refusal costs a few seconds of a warm container
MAX_WAVES = 60


def usd_per_s(cls: str) -> float:
    c = CLASSES[cls]
    return c["cpu"] * CORE_S + c["memory"] / 1024 * GIB_S + (GPU_S[c["gpu"]] if c["gpu"] else 0.0)


def _container_callable(gated: bool):
    """The function Modal runs, created as a closure so that it is serialised BY VALUE (a module-level function would be pickled by
    reference to a module the container may not have). Tags travel through so results can be matched in unordered maps."""
    def p4_job(payload):
        tag = payload.get("__tag")
        from brainir_causal.p4modal import gate
        h = gate.host_cpu()
        if gated and not payload.get("ungated") and not gate.admissible(h):
            r = gate.refusal(h)
            r["__tag"] = tag
            return r
        from brainir_causal.p4modal import remote
        try:
            r = remote.dispatch(payload)
        except Exception as e:  # noqa: BLE001 - a deterministic job error is a RESULT (Modal's retries are for infrastructure faults)
            import traceback
            r = {"error": f"{type(e).__name__}: {e}"[:2000], "traceback": traceback.format_exc()[-6000:]}
        if isinstance(r, dict):
            r["__tag"] = tag
            r["__host__"] = h
        return r
    return p4_job


def volume(name: str, create: bool = True):
    """A Phase 4 volume (created as a VolumeFS v2 volume on first use: concurrent writers of distinct files, no size limit)."""
    import modal
    try:
        return modal.Volume.from_name(VOLUMES[name], create_if_missing=create, version=2)
    except Exception:  # noqa: BLE001 - an existing v1 volume
        return modal.Volume.from_name(VOLUMES[name], create_if_missing=create)


def make_app(classes: list[str] | None = None, max_containers: int = MAX_CONTAINERS, extra_dirs: dict[str, str] | None = None,
             app_name: str = APP_NAME):
    import modal
    app = modal.App(app_name)
    vols = {k: volume(k) for k in VOLUMES}
    retries = modal.Retries(max_retries=3, initial_delay=2.0, backoff_coefficient=1.0)
    cpu_img, gpu_img = None, None
    fns = {}
    for name in classes or list(CLASSES):
        c = CLASSES[name]
        if c["gpu"]:
            gpu_img = gpu_img or images.full_image(gpu=True, extra_dirs=extra_dirs)
            img = gpu_img
        else:
            cpu_img = cpu_img or images.full_image(gpu=False, extra_dirs=extra_dirs)
            img = cpu_img
        kw = {"cpu": c["cpu"], "memory": c["memory"], "timeout": c["timeout"], "max_containers": max_containers, "retries": retries,
              "volumes": {MOUNT[v]: vols[v] for v in c["volumes"]}, "serialized": True, "name": f"p4_{name}", "image": img}
        if c["gpu"]:
            kw["gpu"] = c["gpu"]
        fns[name] = app.function(**kw)(_container_callable(c["gated"]))
    return app, fns, vols


class Backend:
    """Submits payloads to the worker classes, re-submits host-gate refusals, records approximate costs. Use as a context manager
    (an ephemeral app for the block), or `Backend.deployed()` for the functions of a deployed app (`modal_p4.py deploy`)."""

    def __init__(self, classes: list[str] | None = None, max_containers: int = MAX_CONTAINERS, extra_dirs: dict[str, str] | None = None,
                 app_name: str = APP_NAME, verbose: bool = True):
        self.classes = classes or list(CLASSES)
        self.app, self.fns, self.vols = make_app(self.classes, max_containers, extra_dirs, app_name)
        self.costs: list[dict] = []
        self.refusals: dict[str, int] = {}
        self.hosts: dict[str, int] = {}
        self.verbose = verbose
        self._ctx = None
        self.app_id = None

    @classmethod
    def deployed(cls, app_name: str = APP_NAME, classes: list[str] | None = None, verbose: bool = True) -> Backend:
        import modal
        self = cls.__new__(cls)
        self.classes = classes or list(CLASSES)
        self.app, self.vols = None, {k: volume(k) for k in VOLUMES}
        self.fns = {n: modal.Function.from_name(app_name, f"p4_{n}") for n in self.classes}
        self.costs, self.refusals, self.hosts, self.verbose, self._ctx, self.app_id = [], {}, {}, verbose, None, None
        return self

    def __enter__(self):
        import modal
        self._out = modal.enable_output() if self.verbose else None
        if self._out is not None:
            self._out.__enter__()
        self._ctx = self.app.run()
        run = self._ctx.__enter__()
        self.app_id = getattr(run, "app_id", None)
        return self

    def __exit__(self, *exc):
        try:
            self._ctx.__exit__(*exc)
        finally:
            if self._out is not None:
                self._out.__exit__(*exc)
        return False

    # ---------------------------------------------------------------- generic submission
    def run(self, payloads: list[dict], cls: str, label: str = "") -> list:
        """Results in input order (an Exception for a failed call). All inputs go out as one map (results as they complete); refused
        inputs are re-submitted in further waves."""
        fn = self.fns[cls]
        n = len(payloads)
        out: list = [None] * n
        todo = list(range(n))
        attempts = [0] * n
        t0 = time.time()
        recs = []
        wave = 0
        while todo:
            wave += 1
            if wave > MAX_WAVES:
                for i in todo:
                    out[i] = RuntimeError(f"not completed after {MAX_WAVES} waves")
                break
            batch = []
            for i in todo:
                attempts[i] += 1
                batch.append(dict(payloads[i], __tag=i, job_id=uuid.uuid4().hex))
            nxt = []
            for r in fn.map(batch, order_outputs=False, return_exceptions=True):
                if isinstance(r, BaseException):
                    # which input failed is unknown here (the exception carries no tag): collected after the wave
                    recs.append({"error": repr(r)[:500]})
                    continue
                i = int(r.get("__tag"))
                if r.get("__refused__"):
                    self.refusals[cls] = self.refusals.get(cls, 0) + 1
                    if attempts[i] >= MAX_REFUSALS:
                        out[i] = RuntimeError(f"no admissible host after {attempts[i]} attempts")
                    else:
                        nxt.append(i)
                    continue
                out[i] = r
                recs.append(r)
                host = (r.get("__host__") or {}).get("model")
                if host:
                    self.hosts[host] = self.hosts.get(host, 0) + 1
            missing = [i for i in todo if out[i] is None and i not in nxt]
            for i in missing:                       # failed calls (exceptions after Modal's own retries): one more wave each
                if attempts[i] >= 4:
                    out[i] = RuntimeError("call failed repeatedly on Modal")
                else:
                    nxt.append(i)
            todo = sorted(set(nxt))
            if self.verbose and todo:
                print(f"  p4modal {label or cls}: wave {wave} left {len(todo)} to re-submit ({time.time() - t0:.0f} s)", flush=True)
        self._cost(recs, cls, label)
        if self.verbose:
            print(f"  p4modal {label or cls}: {n} jobs in {time.time() - t0:.0f} s (refusals {self.refusals.get(cls, 0)})", flush=True)
        return out

    def _cost(self, recs: list, cls: str, label: str) -> None:
        s = sum(float(r.get("container_wall_s") or 0.0) for r in recs if isinstance(r, dict))
        peaks = [float(r["peak_container_mb"]) for r in recs if isinstance(r, dict) and r.get("peak_container_mb") is not None]
        self.costs.append({"label": label or cls, "class": cls, "calls": len(recs), "container_s": round(s, 1),
                           "peak_container_mb_max": max(peaks) if peaks else None, "usd_approx": round(s * usd_per_s(cls), 4)})

    # ---------------------------------------------------------------- simulation
    def simulate(self, items: list[dict], *, mode: str = "full", store: str | None = "store", batch: int = 8, cls: str | None = None,
                 workers: int | None = None, label: str = "sim", store_sub: str = "store") -> list:
        """items: [{"sysdef": INTERNAL real record, "protocol": dict, "restart_src": {store key: record bytes}?, "meta": {}?}].
        mode 'full' returns each record's bytes (brainir_causal.p4modal.remote.record_from_bytes), 'observed' the observed arrays
        (t, x, u, y) only, 'digest' only keys and array hashes. store: 'store' (public / development records), 'eval' (hidden records:
        class sim_eval) or None (no volume store). Results in item order; each has key, computed, sha (per array) and sim_wall_s."""
        cls = cls or ("sim_eval" if store == "eval" else "sim")
        w = workers or int(CLASSES[cls]["cpu"])
        payloads = [{"kind": "sim", "items": items[i: i + batch], "store": store, "store_sub": store_sub, "mode": mode, "workers": w,
                     "threads": 1} for i in range(0, len(items), batch)]
        res = self.run(payloads, cls, label)
        out = []
        for p, r in zip(payloads, res, strict=True):
            if isinstance(r, BaseException) or not isinstance(r, dict) or "results" not in r:
                err = r if isinstance(r, BaseException) else RuntimeError(f"simulation batch failed: {str(r)[:500]}")
                out += [err] * len(p["items"])
            else:
                out += [RuntimeError(x["error"]) if "error" in x else x for x in r["results"]]
        return out

    def remote_backend(self, *, batch: int = 4, cls: str = "sim"):
        """The `remote_backend` of brainir_causal.simservice.SimServer: jobs -> [finish_remote_job(job, record) | Exception]. The
        record is computed on a gated host (or served from the volume store), checked against the locally computed store key, stored
        in the local store, and its observed arrays are returned."""
        from brainir_causal.simservice import finish_remote_job, real_store_key
        from brainir_causal.store import TrajectoryStore

        from .remote import record_from_bytes

        def backend(jobs: list[dict]) -> list:
            items = []
            for job in jobs:
                q = job["protocol"]
                src = None
                if q.get("r0", {}).get("kind") == "restart":
                    p = TrajectoryStore(job["store_root"]).path(q["r0"]["key"])
                    if p.exists():
                        src = {q["r0"]["key"]: p.read_bytes()}
                items.append({"sysdef": job["sysdef"], "protocol": q, "restart_src": src, "meta": {"source": "simservice-remote"}})
            res = self.simulate(items, mode="full", store="store", batch=batch, cls=cls, workers=min(batch, int(CLASSES[cls]["cpu"])),
                                label="simservice")
            out = []
            for job, r in zip(jobs, res, strict=True):
                if isinstance(r, BaseException):
                    out.append(r)
                    continue
                if r["key"] != real_store_key(job):
                    out.append(RuntimeError(f"remote key {r['key'][:12]} != local key {real_store_key(job)[:12]}"))
                    continue
                out.append(finish_remote_job(job, record_from_bytes(r["record"])))
            return out
        return backend

    def fetch(self, keys: list[str], volume_name: str = "store") -> dict:
        """Record bytes of store keys from a store volume (None when absent)."""
        res = self.run([{"kind": "fetch", "keys": keys[i: i + 16], "volume": volume_name} for i in range(0, len(keys), 16)], "util", "fetch")
        out = {}
        for r in res:
            if isinstance(r, dict):
                out.update(r.get("records") or {})
        return out

    # ---------------------------------------------------------------- orchestrator calls and method jobs
    def call(self, target: str, arg_lists: list[list], cls: str = "util", timeout_s: float = 7200, threads: int = 2, **extra) -> list:
        payloads = [dict({"kind": "call", "target": target, "args": list(a), "timeout_s": timeout_s, "threads": threads}, **extra)
                    for a in arg_lists]
        return self.run(payloads, cls, f"call:{target}")

    def run_methods(self, payloads: list[dict], cls: str = "fit_s", label: str = "methods") -> list:
        """Guarded method jobs (remote.run_method payloads; `kind` is set here)."""
        return self.run([dict(p, kind="method") for p in payloads], cls, label)

    # ---------------------------------------------------------------- uploads
    def methods_key(self, mdir: Path) -> str:
        """Deterministic tar of a method snapshot directory, uploaded once to the fit volume (/methods/<key>.tar); key = sha256[:16]."""
        blob = tar_bytes(Path(mdir))
        key = hashlib.sha256(blob).hexdigest()[:16]
        vol = self.vols["fit"]
        try:
            present = {Path(e.path).name for e in vol.listdir("/methods")}
        except Exception:  # noqa: BLE001
            present = set()
        if f"{key}.tar" not in present:
            with vol.batch_upload(force=True) as b:
                b.put_file(io.BytesIO(blob), f"/methods/{key}.tar")
        return key

    def upload_dir(self, volume_name: str, base: Path, dest: str, files: list[Path] | None = None) -> dict:
        """Pack `files` (default: every file under base) as ONE tar, upload it to /<volume>/_incoming and unpack it in Modal (per-file
        uploads are dominated by round trips on a slow uplink). Returns {n_files, tar_bytes, sha256: {relative path: hash}}."""
        base = Path(base)
        files = sorted(files if files is not None else [q for q in base.rglob("*") if q.is_file()])
        name = dest.strip("/").replace("/", "_") + f"_{uuid.uuid4().hex[:8]}.tar"
        buf = io.BytesIO()
        sha = {}
        with tarfile.open(fileobj=buf, mode="w") as tf:
            for q in files:
                data = q.read_bytes()
                rel = q.relative_to(base).as_posix()
                sha[rel] = hashlib.sha256(data).hexdigest()
                ti = tarfile.TarInfo(rel)
                ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
                tf.addfile(ti, io.BytesIO(data))
        blob = buf.getvalue()
        with self.vols[volume_name].batch_upload(force=True) as b:
            b.put_file(io.BytesIO(blob), f"/_incoming/{name}")
        r = self.run([{"kind": "extract", "volume": volume_name, "name": name, "dest": dest}], "util", "extract")[0]
        if isinstance(r, BaseException) or r.get("extracted_files") != len(files):
            raise RuntimeError(f"extraction of {dest} failed or incomplete: {r!r}"[:1000])
        return {"n_files": len(files), "tar_bytes": len(blob), "sha256": sha}

    def cost_summary(self) -> dict:
        return {"app_id": self.app_id, "calls": self.costs, "usd_approx_total": round(sum(c["usd_approx"] for c in self.costs), 4),
                "refusals": self.refusals, "hosts": self.hosts}


def tar_bytes(d: Path, prefix: str = "") -> bytes:
    """A deterministic tar of a directory (sorted names, zero mtimes; no __pycache__ / .pyc)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        for p in sorted(q for q in Path(d).rglob("*") if q.is_file() and "__pycache__" not in q.parts and q.suffix != ".pyc"):
            data = p.read_bytes()
            ti = tarfile.TarInfo(prefix + p.relative_to(d).as_posix())
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            tf.addfile(ti, io.BytesIO(data))
    return buf.getvalue()


def write_cost_record(path: Path, be: Backend, extra: dict | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(be.cost_summary(), **(extra or {})), indent=1) + "\n", encoding="utf-8", newline="\n")
