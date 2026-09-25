"""Trajectory datasets for state discovery (shared by the orchestrator, the evaluator and methods).

On disk a dataset is a directory:

    manifest.json     {"dataset_id", "version", "dt", "systems": {system_id: {"observed": [ids], "readout": [ids],
                       "input_dim": int, "kind": "real" | "synthetic", "network": str | null, "group": str | null, ...}},
                       "splits": [...], "families": {...}}
    index.jsonl       one line per trajectory: {"key", "system_id", "split", "family", "protocol": {...}, "info": {...}}
    traj/<key>.npz    t (T,), x (T, N_obs) float32, u (T, n_u) float32, y (T, n_y) float32

x holds the system's OBSERVED population (the encoder input; never the readout), y its readout, u its external input. Protocol
events name neurons by public id; `observed_index(system)` maps ids to columns of x. Nothing here reads truth: synthetic truth
lives in a separate directory that never enters the clean room.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

import numpy as np

DATASET_FORMAT = "p3-dataset-1"


@dataclass
class Trajectory:
    key: str
    system_id: str
    split: str
    family: str
    protocol: dict
    t: np.ndarray
    x: np.ndarray
    u: np.ndarray
    y: np.ndarray
    info: dict = field(default_factory=dict)

    @property
    def dt(self) -> float:
        return float(self.t[1] - self.t[0]) if len(self.t) > 1 else float(self.protocol.get("dt", 0.0))

    def events(self) -> list[dict]:
        return list(self.protocol.get("events") or [])


class Dataset:
    """Read access to a dataset directory (lazy: trajectories are loaded on demand)."""

    def __init__(self, root: Path | str):
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        self.index = [json.loads(line) for line in (self.root / "index.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]

    @property
    def systems(self) -> dict:
        return self.manifest["systems"]

    def observed_index(self, system_id: str) -> dict[int, int]:
        return {int(n): i for i, n in enumerate(self.systems[system_id]["observed"])}

    def select(self, *, system_id: str | None = None, split: str | None = None, family: str | None = None) -> list[dict]:
        return [r for r in self.index if (system_id is None or r["system_id"] == system_id) and (split is None or r["split"] == split)
                and (family is None or r["family"] == family)]

    def load(self, row: dict) -> Trajectory:
        with np.load(self.root / "traj" / f"{row['key']}.npz") as z:
            return Trajectory(key=row["key"], system_id=row["system_id"], split=row["split"], family=row["family"], protocol=row["protocol"],
                              t=z["t"], x=z["x"], u=z["u"], y=z["y"], info=row.get("info") or {})

    def iter(self, **kw) -> Iterator[Trajectory]:
        for row in self.select(**kw):
            yield self.load(row)


def write_dataset(root: Path | str, manifest: dict, items: list[tuple[dict, dict]]) -> None:
    """Write a dataset. items: (index row without 'key' collisions, arrays {t, x, u, y}); the row must carry 'key'."""
    root = Path(root)
    (root / "traj").mkdir(parents=True, exist_ok=True)
    manifest = {"format": DATASET_FORMAT, **manifest}
    with open(root / "index.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for row, arr in items:
            np.savez_compressed(root / "traj" / f"{row['key']}.npz", t=np.asarray(arr["t"], dtype=np.float64),
                                x=np.asarray(arr["x"], dtype=np.float32), u=np.asarray(arr["u"], dtype=np.float32),
                                y=np.asarray(arr["y"], dtype=np.float32))
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def append_rows(root: Path | str, items: list[tuple[dict, dict]]) -> None:
    root = Path(root)
    (root / "traj").mkdir(parents=True, exist_ok=True)
    with open(root / "index.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        for row, arr in items:
            np.savez_compressed(root / "traj" / f"{row['key']}.npz", t=np.asarray(arr["t"], dtype=np.float64),
                                x=np.asarray(arr["x"], dtype=np.float32), u=np.asarray(arr["u"], dtype=np.float32),
                                y=np.asarray(arr["y"], dtype=np.float32))
            fh.write(json.dumps(row, sort_keys=True) + "\n")
