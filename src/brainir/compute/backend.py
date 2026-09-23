"""Execution backends for embarrassingly parallel simulation jobs: local process pool or Modal.

    from brainir.compute import Shared, get_backend
    backend = get_backend("local", n_workers=6)        # or get_backend("modal", cpu=2, memory_mb=4096)
    results = backend.map(fn, items)                   # order preserved; fn must be importable (module-level)

Large arguments that every job needs (the weight matrix, the readout mask ...) are passed once as a *shared payload*:
``backend.map(fn, items, shared={"W": W})`` with ``Shared("W")`` markers inside the items. Workers resolve the markers
from a per-process cache, so a 4604x4604 matrix is shipped once per worker/container instead of once per job.

Modal jobs run the same `brainir` code that is installed here: the image is built from the repository source, so a result
produced on Modal is attributable to the same commit as a local result. Cost control: every Modal map records the number
of items, the wall time and the container settings; `max_items` refuses to launch oversized batches by mistake.
"""

from __future__ import annotations

import functools
import hashlib
import os
import pickle
import time
import zlib
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import paths

DEFAULT_MODAL_APP = "brainir-phase1"
DEFAULT_MODAL_VOLUME = "brainir-shared-payloads"
MODAL_PYTHON = "3.12"
MODAL_DEPS = ("numpy>=2.0", "scipy>=1.13", "pandas>=2.2", "pyarrow>=17", "pydantic>=2.8", "networkx>=3.3", "duckdb>=1.1",
              "google-crc32c>=1.5", "requests>=2.32")


class Shared:
    """Marker for an argument that lives in the map's shared payload (``shared[key]``)."""
    __slots__ = ("key",)

    def __init__(self, key: str):
        self.key = key

    def __repr__(self) -> str:
        return f"Shared({self.key!r})"


def resolve_shared(item, shared: dict):
    """Replace every :class:`Shared` marker inside ``item`` (tuples/lists/dicts, any depth) by the payload value."""
    if isinstance(item, Shared):
        return shared[item.key]
    if isinstance(item, tuple):
        return tuple(resolve_shared(x, shared) for x in item)
    if isinstance(item, list):
        return [resolve_shared(x, shared) for x in item]
    if isinstance(item, dict):
        return {k: resolve_shared(v, shared) for k, v in item.items()}
    return item


def pack_shared(shared: dict) -> tuple[bytes, str]:
    """Pickle + zlib a shared payload; returns (blob, content key)."""
    blob = zlib.compress(pickle.dumps(shared, protocol=pickle.HIGHEST_PROTOCOL), 6)
    return blob, hashlib.sha256(blob).hexdigest()[:32]


def unpack_shared(blob: bytes) -> dict:
    return pickle.loads(zlib.decompress(blob))


_LOCAL_SHARED: dict = {}


def _init_local_shared(shared: dict) -> None:
    _LOCAL_SHARED.clear()
    _LOCAL_SHARED.update(shared)


def _call_resolved(fn: Callable, item):
    return fn(resolve_shared(item, _LOCAL_SHARED))


@dataclass
class RunStats:
    backend: str
    n_items: int
    wall_time_s: float
    settings: dict = field(default_factory=dict)
    estimated_cost_usd: float | None = None

    def to_dict(self) -> dict:
        return {"backend": self.backend, "n_items": self.n_items, "wall_time_s": round(self.wall_time_s, 1), "settings": self.settings,
                "estimated_cost_usd": self.estimated_cost_usd}


class LocalBackend:
    name = "local"

    def __init__(self, n_workers: int | None = None):
        self.n_workers = int(n_workers or max(1, (os.cpu_count() or 2) - 1))
        self.last_stats: RunStats | None = None

    def map(self, fn: Callable[[Any], Any], items: Iterable[Any], *, chunksize: int = 1, shared: dict | None = None) -> list:
        items = list(items)
        shared = shared or {}
        t0 = time.time()
        if self.n_workers > 1 and len(items) > 1:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=self.n_workers, initializer=_init_local_shared, initargs=(shared,)) as ex:
                out = list(ex.map(functools.partial(_call_resolved, fn), items, chunksize=chunksize))
        else:
            out = [fn(resolve_shared(x, shared)) for x in items]
        self.last_stats = RunStats(self.name, len(items), time.time() - t0, {"n_workers": self.n_workers})
        return out


class ModalBackend:
    """Runs ``fn`` on Modal containers (one item per call, concurrency up to ``max_containers``).

    ``fn`` must be a module-level function of an importable module in the repository; it and its arguments are
    serialised by Modal. The container image installs the pinned scientific stack and the ``brainir`` source tree. A
    shared payload is uploaded once to a Modal Volume (content-addressed) and cached per container."""
    name = "modal"
    # Modal list prices (2026) for the CPU-only tier used here, per core-second and per GiB-second; used ONLY for the
    # approximate cost note in run records.
    PRICE_PER_CORE_S = 0.192 / 3600
    PRICE_PER_GIB_S = 0.024 / 3600

    def __init__(self, *, cpu: float = 1.0, memory_mb: int = 2048, timeout_s: int = 1800, max_containers: int = 100,
                 max_items: int = 200_000, app_name: str = DEFAULT_MODAL_APP, volume_name: str = DEFAULT_MODAL_VOLUME, retries: int = 2):
        self.cpu, self.memory_mb, self.timeout_s = cpu, memory_mb, timeout_s
        self.max_containers, self.max_items, self.app_name = max_containers, max_items, app_name
        self.volume_name, self.retries = volume_name, retries
        self.last_stats: RunStats | None = None

    def _image(self):
        import modal

        src = paths.repo_root() / "src" / "brainir"
        base = modal.Image.debian_slim(python_version=MODAL_PYTHON).pip_install(*MODAL_DEPS)
        if hasattr(modal.Image, "add_local_python_source"):
            return base.add_local_python_source("brainir", copy=True)
        return base.add_local_dir(str(src), "/root/brainir")

    def _upload_shared(self, shared: dict) -> tuple[str, Any, int]:
        """Upload the packed payload to the Volume unless a blob with the same content key is already there."""
        import modal

        blob, key = pack_shared(shared)
        vol = modal.Volume.from_name(self.volume_name, create_if_missing=True)
        fname = f"{key}.pkl.z"
        try:
            present = {Path(e.path).name for e in vol.listdir("/")}
        except Exception:  # noqa: BLE001 - empty/new volume
            present = set()
        if fname not in present:
            cache = paths.cache_dir() / "modal_shared"
            cache.mkdir(parents=True, exist_ok=True)
            local = cache / fname
            local.write_bytes(blob)
            with vol.batch_upload() as b:
                b.put_file(str(local), f"/{fname}")
        return key, vol, len(blob)

    def map(self, fn: Callable[[Any], Any], items: Iterable[Any], *, chunksize: int = 1, shared: dict | None = None) -> list:
        import modal

        items = list(items)
        if len(items) > self.max_items:
            raise ValueError(f"refusing to launch {len(items)} Modal calls (> max_items={self.max_items}); raise max_items deliberately")
        key, vol, blob_size = (None, None, 0)
        volumes = {}
        if shared:
            key, vol, blob_size = self._upload_shared(shared)
            volumes = {"/shared": vol}
        app = modal.App(self.app_name, image=self._image())
        # serialized=True: the wrapper is a closure (not a global), so Modal ships it by value; it imports ``fn`` by module path
        remote = app.function(cpu=self.cpu, memory=self.memory_mb, timeout=self.timeout_s, max_containers=self.max_containers,
                              retries=self.retries, volumes=volumes, serialized=True)(_make_remote_wrapper(fn, key))
        t0 = time.time()
        with app.run():
            # return_exceptions: one failed item must not discard an hour of finished work; callers use split_failures()
            out = list(remote.map(items, order_outputs=True, return_exceptions=True))
        wall = time.time() - t0
        n_failed = sum(isinstance(x, BaseException) for x in out)
        cost = None
        try:  # rough upper bound: every item ran for wall/containers seconds on cpu cores + memory
            per_item_s = wall * min(self.max_containers, max(1, len(items))) / max(1, len(items))
            cost = round(len(items) * per_item_s * (self.cpu * self.PRICE_PER_CORE_S + self.memory_mb / 1024 * self.PRICE_PER_GIB_S), 4)
        except Exception:  # noqa: BLE001
            cost = None
        self.last_stats = RunStats(self.name, len(items), wall, {"cpu": self.cpu, "memory_mb": self.memory_mb, "timeout_s": self.timeout_s,
                                                                 "max_containers": self.max_containers, "app": self.app_name,
                                                                 "shared_payload_key": key, "shared_payload_bytes": blob_size,
                                                                 "n_failed": n_failed}, cost)
        return out


def split_failures(results: list) -> tuple[list, list[dict]]:
    """Separate successful results from exception objects returned by a backend map (index + repr for the record)."""
    ok, failed = [], []
    for i, r in enumerate(results):
        if isinstance(r, BaseException):
            failed.append({"index": i, "error": repr(r)[:500]})
        else:
            ok.append(r)
    return ok, failed


def _make_remote_wrapper(fn: Callable, shared_key: str | None):
    """Modal needs a function defined at import time; we forward to ``fn`` by module path so the container imports it.

    The shared payload (if any) is read from the mounted Volume on first use and kept in the closure for the life of the
    container."""
    mod, name = fn.__module__, fn.__qualname__
    cache: dict = {}

    def remote_call(item):
        import importlib
        import pickle
        import zlib

        f = getattr(importlib.import_module(mod), name)
        if shared_key is not None:
            if "shared" not in cache:
                with open(f"/shared/{shared_key}.pkl.z", "rb") as fh:
                    cache["shared"] = pickle.loads(zlib.decompress(fh.read()))
            item = _resolve(item, cache["shared"])
        return f(item)

    def _resolve(item, shared):
        from brainir.compute.backend import resolve_shared
        return resolve_shared(item, shared)

    remote_call.__name__ = f"remote_{name}"
    return remote_call


def get_backend(kind: str = "local", **kw):
    if kind == "local":
        return LocalBackend(kw.get("n_workers"))
    if kind == "modal":
        return ModalBackend(**{k: v for k, v in kw.items() if k != "n_workers"})
    raise ValueError(f"unknown backend {kind!r}")


def modal_available() -> bool:
    try:
        import modal  # noqa: F401
    except ImportError:
        return False
    cfg = Path.home() / ".modal.toml"
    return cfg.exists() or bool(os.environ.get("MODAL_TOKEN_ID"))
