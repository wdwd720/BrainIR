"""Content-addressed trajectory store (goal5 section 61; ORCHESTRATOR SIDE).

Key = sha256 of {protocol format, the canonical protocol WITHOUT observation noise, the system's content hash, the engine and
simulator versions} (`protocol.protocol_hash(protocol.microstate_protocol(p), ...)`). Together these cover the system hash,
the simulator version, the initial state, the parameters, the input, the interventions, the seeds, dt and the duration.
Observation noise is excluded because it never changes the simulated microstate: observed arrays with noise are derived from the
stored record (`realsim.observe`), so a noisy repeat never re-simulates. Identical trajectories are never simulated twice: a key
is claimed with an exclusive lock file while it is computed, and other processes wait for the record instead of recomputing.

A record is a dict of numpy arrays plus an `info` dict: real engine records hold the sparse FULL microstate (`t`, `neurons`,
`rates`, `u`), so any population can be derived and any sampled state restarted; synthetic records hold whatever the generator
returns (`t`, `x`, `u`, `y`, optionally the full state). One compressed NPZ per record under rec/<key[:2]>/, plus an append-only
JSONL index (appends are serialised by a lock file, so concurrent writers never interleave lines).

    store = TrajectoryStore(root)                       # root: data/phase4/store (git-ignored)
    key = store.key(protocol, system_hash, engine_id)   # engine_id e.g. f"{realsim.ENGINE_VERSION}|{brainir MODEL_ID}"
    key, rec, computed = store.get_or_compute(key, compute_fn, meta)
    key, rec, computed = store.get_or_run(real_engine, real_system, protocol, system_hash, meta)   # real systems

VALIDITY (review H, M4 / M5): `put` refuses a record whose info says `success: false` or whose simulated arrays (x, y, rates, state,
z, z_obs) hold a non-finite value (`InvalidRecord`; nothing is written, so the key stays free), and adds the host fingerprint of the
writing process (`p4modal.gate.host_fingerprint`) to the info of a record that carries none (records computed elsewhere keep theirs).
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from . import protocol as P

_LOCK = threading.Lock()
LOCK_STALE_S = 1800.0           # a claim older than this is considered abandoned (a crashed worker)
INDEX_LOCK_STALE_S = 30.0


def _acquire(path: Path, stale_s: float, poll: float = 0.01, timeout: float | None = None) -> bool:
    """Create `path` exclusively (a lock); break it when older than stale_s. False on timeout."""
    t0 = time.time()
    while True:
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except (FileExistsError, PermissionError):     # Windows: PermissionError while another process deletes the lock file
            try:
                if time.time() - path.stat().st_mtime > stale_s:
                    path.unlink(missing_ok=True)
                    continue
            except (FileNotFoundError, PermissionError):
                continue
            if timeout is not None and time.time() - t0 > timeout:
                return False
            time.sleep(poll)


class InvalidRecord(RuntimeError):
    """A simulation result that must not be stored (failed or non-finite; review H, M4)."""


CHECKED_ARRAYS = ("x", "y", "rates", "state", "z", "z_obs")


def check_record(rec: dict) -> None:
    """Raise InvalidRecord when a record is not a successful, finite simulation."""
    info = rec.get("info") or {}
    if info.get("success") is False:
        raise InvalidRecord("the simulation failed (info.success is false)")
    for k in CHECKED_ARRAYS:
        if k in rec and rec[k] is not None:
            a = np.asarray(rec[k])
            if a.dtype.kind in "fc" and not np.isfinite(a).all():
                raise InvalidRecord(f"the simulation produced non-finite values in {k!r}")


class TrajectoryStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        (self.root / "rec").mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.jsonl"

    # ---------------------------------------------------------------- keys and paths
    @staticmethod
    def key(proto: dict, system_hash: str, engine: str, *, allow_truth: bool = False) -> str:
        return P.protocol_hash(P.microstate_protocol(proto, allow_truth=allow_truth), system_hash=system_hash, simulator=engine,
                               allow_truth=allow_truth)

    def path(self, key: str) -> Path:
        return self.root / "rec" / key[:2] / f"{key}.npz"

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    # ---------------------------------------------------------------- read / write
    def get(self, key: str) -> dict | None:
        p = self.path(key)
        if not p.exists():
            return None
        with np.load(p, allow_pickle=False) as z:
            rec = {k: z[k] for k in z.files if k != "info"}
            rec["info"] = json.loads(str(z["info"])) if "info" in z.files else {}
        return rec

    def put(self, key: str, rec: dict, meta: dict) -> None:
        check_record(rec)
        info = dict(rec.get("info") or {})
        if "host" not in info:
            from .p4modal.gate import host_fingerprint
            info["host"] = host_fingerprint()
            rec["info"] = info
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_name(f"{key}.{os.getpid()}.{threading.get_ident()}.tmp.npz")
        arrays = {k: np.asarray(v) for k, v in rec.items() if k != "info"}
        np.savez_compressed(tmp, info=np.array(json.dumps(info, sort_keys=True)), **arrays)
        os.replace(tmp, p)
        self._append_index({"key": key, **meta})

    def _append_index(self, row: dict) -> None:
        line = json.dumps(row, sort_keys=True) + "\n"
        lock = self.root / "index.lock"
        with _LOCK:
            _acquire(lock, INDEX_LOCK_STALE_S)
            try:
                with open(self.index_path, "a", encoding="utf-8", newline="\n") as fh:
                    fh.write(line)
            finally:
                lock.unlink(missing_ok=True)

    def index(self) -> list[dict]:
        if not self.index_path.exists():
            return []
        out = []
        for line in self.index_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # ---------------------------------------------------------------- compute once
    def get_or_compute(self, key: str, compute: Callable[[], dict], meta: dict, wait_s: float = LOCK_STALE_S) -> tuple[str, dict, bool]:
        """(key, record, computed?): computes only when the key is not stored yet; concurrent callers of the same key wait."""
        rec = self.get(key)
        if rec is not None:
            return key, rec, False
        claim = self.path(key).with_suffix(".claim")
        claim.parent.mkdir(parents=True, exist_ok=True)
        if not _acquire(claim, LOCK_STALE_S, poll=0.05, timeout=wait_s):
            raise TimeoutError(f"store key {key[:12]} is claimed by another worker")
        try:
            rec = self.get(key)                      # computed by the previous holder of the claim
            if rec is not None:
                return key, rec, False
            rec = compute()
            self.put(key, rec, meta)
            return key, rec, True
        finally:
            claim.unlink(missing_ok=True)

    def get_or_run(self, engine, system, proto: dict, system_hash: str, meta: dict | None = None) -> tuple[str, dict, bool]:
        """Real systems: run `engine.run(system, proto, store=self)` only when the microstate is not stored yet."""
        from brainir.sim.model import MODEL_ID

        from .realsim import ENGINE_VERSION
        q = P.validate(proto)
        key = self.key(q, system_hash, f"{ENGINE_VERSION}|{MODEL_ID}")
        return self.get_or_compute(key, lambda: engine.run(system, q, store=self),
                                   {"system_id": system.system_id, "system_hash": system_hash, "protocol": P.microstate_protocol(q),
                                    **(meta or {})})
