"""Execution backends for embarrassingly parallel simulation jobs: local process pool or Modal.

    from brainir.compute import get_backend
    backend = get_backend("local", n_workers=6)        # or get_backend("modal", cpu=2, memory_mb=4096)
    results = backend.map(fn, items)                   # order preserved; fn must be importable (module-level)

Modal jobs run the same `brainir` code that is installed here: the image is built from the repository source, so a result
produced on Modal is attributable to the same commit as a local result. Cost control: every Modal map records the number
of items, the wall time and the container settings; `max_items` refuses to launch oversized batches by mistake.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import paths

DEFAULT_MODAL_APP = "brainir-phase1"
MODAL_PYTHON = "3.12"
MODAL_DEPS = ("numpy>=2.0", "scipy>=1.13", "pandas>=2.2", "pyarrow>=17", "pydantic>=2.8", "networkx>=3.3", "duckdb>=1.1",
              "google-crc32c>=1.5", "requests>=2.32")


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

    def map(self, fn: Callable[[Any], Any], items: Iterable[Any], *, chunksize: int = 1) -> list:
        items = list(items)
        t0 = time.time()
        if self.n_workers > 1 and len(items) > 1:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=self.n_workers) as ex:
                out = list(ex.map(fn, items, chunksize=chunksize))
        else:
            out = [fn(x) for x in items]
        self.last_stats = RunStats(self.name, len(items), time.time() - t0, {"n_workers": self.n_workers})
        return out


class ModalBackend:
    """Runs ``fn`` on Modal containers (one item per call, concurrency up to ``max_containers``).

    ``fn`` must be a module-level function of an importable module in the repository; it and its arguments are
    serialised by Modal. The container image installs the pinned scientific stack and the ``brainir`` source tree."""
    name = "modal"
    # Modal list prices (2026) for the CPU-only tier used here, per core-second and per GiB-second; used ONLY for the
    # approximate cost note in run records.
    PRICE_PER_CORE_S = 0.192 / 3600
    PRICE_PER_GIB_S = 0.024 / 3600

    def __init__(self, *, cpu: float = 1.0, memory_mb: int = 2048, timeout_s: int = 1800, max_containers: int = 100,
                 max_items: int = 200_000, app_name: str = DEFAULT_MODAL_APP):
        self.cpu, self.memory_mb, self.timeout_s = cpu, memory_mb, timeout_s
        self.max_containers, self.max_items, self.app_name = max_containers, max_items, app_name
        self.last_stats: RunStats | None = None

    def _app_and_function(self, fn: Callable):
        import modal

        src = paths.repo_root() / "src" / "brainir"
        image = (modal.Image.debian_slim(python_version=MODAL_PYTHON)
                 .pip_install(*MODAL_DEPS)
                 .add_local_python_source("brainir", copy=True) if hasattr(modal.Image, "add_local_python_source")
                 else modal.Image.debian_slim(python_version=MODAL_PYTHON).pip_install(*MODAL_DEPS).add_local_dir(str(src), "/root/brainir"))
        app = modal.App(self.app_name, image=image)
        # serialized=True: the wrapper is a closure (not a global), so Modal ships it by value; it imports ``fn`` by module path
        remote = app.function(cpu=self.cpu, memory=self.memory_mb, timeout=self.timeout_s, max_containers=self.max_containers,
                              serialized=True)(_make_remote_wrapper(fn))
        return app, remote

    def map(self, fn: Callable[[Any], Any], items: Iterable[Any], *, chunksize: int = 1) -> list:
        items = list(items)
        if len(items) > self.max_items:
            raise ValueError(f"refusing to launch {len(items)} Modal calls (> max_items={self.max_items}); raise max_items deliberately")
        app, remote = self._app_and_function(fn)
        t0 = time.time()
        with app.run():
            out = list(remote.map(items, order_outputs=True))
        wall = time.time() - t0
        cost = None
        try:  # rough upper bound: every item ran for wall/containers seconds on cpu cores + memory
            per_item_s = wall * min(self.max_containers, max(1, len(items))) / max(1, len(items))
            cost = round(len(items) * per_item_s * (self.cpu * self.PRICE_PER_CORE_S + self.memory_mb / 1024 * self.PRICE_PER_GIB_S), 4)
        except Exception:  # noqa: BLE001
            cost = None
        self.last_stats = RunStats(self.name, len(items), wall, {"cpu": self.cpu, "memory_mb": self.memory_mb, "timeout_s": self.timeout_s,
                                                                 "max_containers": self.max_containers, "app": self.app_name}, cost)
        return out


def _make_remote_wrapper(fn: Callable):
    """Modal needs a function defined at import time; we forward to ``fn`` by module path so the container imports it."""
    mod, name = fn.__module__, fn.__qualname__

    def remote_call(item):
        import importlib
        f = getattr(importlib.import_module(mod), name)
        return f(item)

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
