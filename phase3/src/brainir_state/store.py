"""Content-addressed trajectory store (goal4 section 60; ORCHESTRATOR SIDE).

Key = sha256 of {protocol format version, canonical protocol, system content hash (bundle hash + system definition), engine +
simulator versions}. A stored record holds the sparse FULL microstate (every neuron ever non-zero), the input and the engine info,
so any population can be derived later and any sampled state can be restarted exactly. Identical trajectories are never
simulated twice. Format chosen by profiling (research/phase3/LOG notes): one compressed NPZ per trajectory (~0.7 MB for 2,001 x
130 float32; write 84 ms, read 26 ms; parquet was slower and larger) plus an append-only JSONL index for queries.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import numpy as np

from . import protocol as P

_LOCK = threading.Lock()


class TrajectoryStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)
        (self.root / "rec").mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "index.jsonl"

    def key(self, proto: dict, system_hash: str, engine: str) -> str:
        return P.protocol_hash(proto, system_hash=system_hash, simulator=engine)

    def path(self, key: str) -> Path:
        return self.root / "rec" / key[:2] / f"{key}.npz"

    def has(self, key: str) -> bool:
        return self.path(key).exists()

    def get(self, key: str) -> dict | None:
        p = self.path(key)
        if not p.exists():
            return None
        with np.load(p, allow_pickle=False) as z:
            rec = {k: z[k] for k in ("t", "neurons", "rates", "u")}
            rec["info"] = json.loads(str(z["info"]))
        return rec

    def put(self, key: str, rec: dict, meta: dict) -> None:
        p = self.path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, t=rec["t"], neurons=rec["neurons"], rates=rec["rates"], u=rec["u"], info=np.array(json.dumps(rec["info"])))
        os.replace(tmp, p)
        with _LOCK, open(self.index_path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps({"key": key, **meta}, sort_keys=True) + "\n")

    def get_or_run(self, engine, system, proto: dict, system_hash: str, meta: dict | None = None) -> tuple[str, dict, bool]:
        """(key, record, computed?) - runs the engine only when the key is not stored yet."""
        from .realsim import ENGINE_VERSION
        from brainir.sim.model import MODEL_ID
        key = self.key(proto, system_hash, f"{ENGINE_VERSION}|{MODEL_ID}")
        rec = self.get(key)
        if rec is not None:
            return key, rec, False
        rec = engine.run(system, proto)
        self.put(key, rec, {"system_id": system.system_id, "system_hash": system_hash, "protocol": P.validate(proto), **(meta or {})})
        return key, rec, True
