"""Pinned Modal backend for the ledger, and a resumable streaming campaign runner.

`brainir.compute.backend.ModalBackend` (locked) builds its image from lower-bound dependencies and the ``brainir`` package
only, so it can neither import ledger job functions nor guarantee the library versions. `LedgerModalBackend` subclasses it:

* the image pins the exact versions of the root ``uv.lock`` (``PINNED``) and ships both ``brainir`` and ``brainir_ledger``;
* numerics environment (``NUMERICS_ENV``): single-threaded BLAS, OpenBLAS kernels forced to one core type, and NumPy's
  AVX-512 dispatch disabled, so that the same job gives the same bits on every Modal host type (Phase 3 found host-dependent
  numerics, research/LOG.md P3-D26/P3-D27). Every job result records the host fingerprint, and gate G4 re-runs jobs on
  different containers;
* `map_stream` yields results as they complete (unordered) so a campaign can persist each one immediately and resume.

`run_campaign` is the only way the ledger launches work: it appends every result to an append-only pickle log under the data
root, skips keys that already have a result, and returns all results keyed by job key.
"""

from __future__ import annotations

import os

# The workspace default image builder (2026.10) is newer than the pinned client (modal 1.5.5, root uv.lock) supports.
# The ledger pins the builder per process instead of changing the workspace setting (ledger LOG L11). Must be set before
# modal is first imported.
IMAGE_BUILDER_VERSION = "2025.06"
os.environ.setdefault("MODAL_IMAGE_BUILDER_VERSION", IMAGE_BUILDER_VERSION)

import pickle  # noqa: E402
import time  # noqa: E402
from collections.abc import Callable, Iterable  # noqa: E402
from pathlib import Path  # noqa: E402

from brainir.compute.backend import ModalBackend, RunStats, _make_remote_wrapper, resolve_shared  # noqa: E402

PINNED = ("numpy==2.5.3", "scipy==1.18.1", "pandas==3.0.6", "pyarrow==25.0.1", "pydantic==2.13.5", "networkx==3.7",
          "duckdb==1.5.5", "google-crc32c==1.8.0", "requests==2.34.2")
NUMERICS_ENV = {
    "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1",
    "OPENBLAS_CORETYPE": "Haswell",
    "NPY_DISABLE_CPU_FEATURES": "AVX512F AVX512CD AVX512_KNL AVX512_KNM AVX512_SKX AVX512_CLX AVX512_CNL AVX512_ICL AVX512_SPR",
}
LEDGER_APP = "brainir-ledger"
LEDGER_VOLUME = "brainir-ledger-payloads"
MODAL_PYTHON = "3.12"


class LedgerModalBackend(ModalBackend):
    # Modal list prices read from `modal billing rates` on 2026-11-19 (CPU per physical core-hour, memory per GiB-hour).
    PRICE_PER_CORE_S = 0.0473 / 3600
    PRICE_PER_GIB_S = 0.008 / 3600

    def __init__(self, *, numerics: bool = True, app_name: str = LEDGER_APP, volume_name: str = LEDGER_VOLUME, batch_size: int = 1, **kw):
        super().__init__(app_name=app_name, volume_name=volume_name, **kw)
        self.numerics = numerics
        self.batch_size = int(batch_size)  # jobs per container call, run as parallel processes (jobs.run_batch)

    def image_spec(self) -> dict:
        return {"base": f"modal.Image.debian_slim(python_version={MODAL_PYTHON!r})", "pip": list(PINNED),
                "env": NUMERICS_ENV if self.numerics else {}, "local_python_sources": ["brainir", "brainir_ledger"],
                "image_builder_version": os.environ.get("MODAL_IMAGE_BUILDER_VERSION")}

    def _image(self):
        import modal

        img = modal.Image.debian_slim(python_version=MODAL_PYTHON).pip_install(*PINNED)
        if self.numerics:
            img = img.env(NUMERICS_ENV)
        return img.add_local_python_source("brainir", "brainir_ledger", copy=True)

    def map_stream(self, fn: Callable, items: list, *, shared: dict | None = None, sink: Callable[[object], None]) -> RunStats:
        import modal

        if len(items) > self.max_items:
            raise ValueError(f"refusing to launch {len(items)} Modal calls (> max_items={self.max_items})")
        key, vol, blob_size = (None, None, 0)
        volumes = {}
        if shared:
            key, vol, blob_size = self._upload_shared(shared)
            volumes = {"/shared": vol}
        app = modal.App(self.app_name, image=self._image())
        call_items = items
        if self.batch_size > 1:
            from .jobs import run_batch

            fn = run_batch
            call_items = [{"key": f"batch{i}", "items": items[i:i + self.batch_size], "workers": self.batch_size}
                          for i in range(0, len(items), self.batch_size)]
        remote = app.function(cpu=self.cpu, memory=self.memory_mb, timeout=self.timeout_s, max_containers=self.max_containers,
                              retries=self.retries, volumes=volumes, serialized=True)(_make_remote_wrapper(fn, key))
        t0 = time.time()
        n_done = 0
        with app.run():
            for res in remote.map(call_items, order_outputs=False, return_exceptions=True):
                if self.batch_size > 1 and isinstance(res, list):
                    for r in res:
                        sink(r)
                        n_done += 1
                else:
                    sink(res)
                    n_done += 1
        wall = time.time() - t0
        self.last_stats = RunStats("modal-ledger", len(items), wall,
                                   {"cpu": self.cpu, "memory_mb": self.memory_mb, "timeout_s": self.timeout_s, "max_containers": self.max_containers,
                                    "app": self.app_name, "shared_payload_key": key, "shared_payload_bytes": blob_size, "n_returned": n_done,
                                    "batch_size": self.batch_size, "image": self.image_spec()},
                                   round(wall * min(self.max_containers, max(1, len(items))) *
                                         (self.cpu * self.PRICE_PER_CORE_S + self.memory_mb / 1024 * self.PRICE_PER_GIB_S), 4))
        return self.last_stats


class LocalStreamBackend:
    """Process-pool stand-in with the same streaming interface (tests and small local checks)."""
    name = "local-ledger"

    def __init__(self, n_workers: int = 4):
        self.n_workers = n_workers
        self.last_stats = None

    def map_stream(self, fn: Callable, items: list, *, shared: dict | None = None, sink: Callable[[object], None]) -> RunStats:
        from concurrent.futures import ProcessPoolExecutor, as_completed

        from brainir.compute.backend import _call_resolved, _init_local_shared

        t0 = time.time()
        shared = shared or {}
        if self.n_workers <= 1:
            for it in items:
                sink(fn(resolve_shared(it, shared)))
        else:
            with ProcessPoolExecutor(max_workers=self.n_workers, initializer=_init_local_shared, initargs=(shared,)) as ex:
                futs = [ex.submit(_call_resolved, fn, it) for it in items]
                for f in as_completed(futs):
                    try:
                        sink(f.result())
                    except Exception as e:  # noqa: BLE001
                        sink(e)
        self.last_stats = RunStats(self.name, len(items), time.time() - t0, {"n_workers": self.n_workers}, None)
        return self.last_stats


def read_log(path: Path) -> list:
    """All complete records of an append-only pickle log (a truncated last record is ignored)."""
    out = []
    if not path.exists():
        return out
    with open(path, "rb") as fh:
        while True:
            try:
                out.append(pickle.load(fh))
            except EOFError:
                break
            except Exception:  # noqa: BLE001 - truncated tail after a crash: stop, the key will be re-run
                break
    return out


def run_campaign(run_dir: Path, jobs: list[dict], backend, fn: Callable, *, shared: dict | None = None, rerun_errors: bool = True,
                 progress_every: int = 500) -> dict[str, dict]:
    """Run ``jobs`` (dicts with unique 'key') through ``backend``, persisting every result as it arrives.

    Results already in ``run_dir/results.pkl`` are reused (resume); job-level errors are re-run when ``rerun_errors``.
    Returns {key: result} for every key that has a result (possibly an error record)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    log = run_dir / "results.pkl"
    keys = [j["key"] for j in jobs]
    if len(set(keys)) != len(keys):
        raise ValueError("job keys must be unique")
    have = {}
    for r in read_log(log):
        if isinstance(r, dict) and "key" in r:
            have[r["key"]] = r
    todo = [j for j in jobs if j["key"] not in have or (rerun_errors and "error" in have[j["key"]])]
    stats_log = run_dir / "backend_stats.jsonl"
    if todo:
        n = {"done": 0, "infra_errors": 0}
        fh = open(log, "ab")

        def sink(res):
            if isinstance(res, BaseException) or not isinstance(res, dict):
                n["infra_errors"] += 1
                if n["infra_errors"] <= 3:
                    print(f"  infrastructure error (job not attributable, will be re-run on resume): {res!r}"[:600], flush=True)
                return
            pickle.dump(res, fh, protocol=pickle.HIGHEST_PROTOCOL)
            fh.flush()
            os.fsync(fh.fileno())
            have[res["key"]] = res
            n["done"] += 1
            if n["done"] % progress_every == 0:
                print(f"  {run_dir.name}: {n['done']}/{len(todo)} results", flush=True)

        try:
            st = backend.map_stream(fn, todo, shared=shared, sink=sink)
        finally:
            fh.close()
        import json

        with open(stats_log, "a", encoding="utf-8", newline="\n") as sf:
            sf.write(json.dumps({"utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "n_submitted": len(todo),
                                 "n_results": n["done"], "infra_errors": n["infra_errors"], "stats": st.to_dict() if st else None},
                                default=str) + "\n")
    return {k: have[k] for k in keys if k in have}


def missing(results: dict, jobs: Iterable[dict]) -> list[str]:
    return [j["key"] for j in jobs if j["key"] not in results or "error" in results[j["key"]]]
