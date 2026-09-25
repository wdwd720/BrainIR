"""Public dataset writing in the format of data_format.md (same on-disk layout as reference/data.py).

This module only ever receives public arrays (t, x, u, y) and public index rows; it never sees truth.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

DATASET_FORMAT = "p3-dataset-1"
PUBLIC_ARRAYS = ("t", "x", "u", "y")


def write_traj(root: Path | str, key: str, arr: dict) -> None:
    root = Path(root)
    (root / "traj").mkdir(parents=True, exist_ok=True)
    np.savez_compressed(root / "traj" / f"{key}.npz", t=np.asarray(arr["t"], dtype=np.float64),
                        x=np.asarray(arr["x"], dtype=np.float32), u=np.asarray(arr["u"], dtype=np.float32),
                        y=np.asarray(arr["y"], dtype=np.float32))


def write_index_and_manifest(root: Path | str, manifest: dict, rows: list[dict]) -> None:
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "index.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
    manifest = {"format": DATASET_FORMAT, **manifest}
    (root / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
