"""Experiment registry: every simulation campaign gets a content-addressed record.

A record captures what is needed to reproduce or audit a run without the Python objects: the configuration (model,
stimulus, intervention, metric settings), the code commit and pipeline fingerprint, the hashes of the input tables or
bundle, the seeds, the environment, the backend stats (wall time, approximate cost) and the artefact hashes. Records are
small JSON files; the campaign outputs themselves live next to them or in the caller's results directory.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .. import __version__, paths


def content_hash(obj) -> str:
    """SHA-256 of the canonical JSON form of a configuration object (sorted keys, default=str)."""
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str, separators=(",", ":")).encode()).hexdigest()


def _git() -> dict:
    root = paths.repo_root()
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, check=True).stdout.strip()
        dirty = bool(subprocess.run(["git", "status", "--porcelain", "--", "src"], cwd=root, capture_output=True, text=True,
                                    check=True).stdout.strip())
        return {"commit": commit, "src_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "src_dirty": None}


@dataclass
class ExperimentRecord:
    name: str
    config: dict
    """Everything that determines the result (model config, stimulus, intervention, metric settings, network provenance)."""
    seeds: list[int]
    inputs: dict = field(default_factory=dict)
    """Hashes of inputs: dataset manifests, bundle sha256, node lists ..."""
    backend: dict = field(default_factory=dict)
    artifacts: dict = field(default_factory=dict)
    """name -> {'path': $REPO/... or $DATA/..., 'sha256': ...}"""
    summary: dict = field(default_factory=dict)
    notes: str = ""
    run_id: str = ""
    created_utc: str = ""
    code: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)

    def finalize(self) -> ExperimentRecord:
        self.created_utc = self.created_utc or _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        self.code = self.code or {**_git(), "brainir_version": __version__}
        self.environment = self.environment or {"python": sys.version.split()[0], "platform": platform.platform()}
        self.run_id = self.run_id or content_hash({"name": self.name, "config": self.config, "seeds": self.seeds, "inputs": self.inputs})[:16]
        return self

    def to_dict(self) -> dict:
        return asdict(self)


def register_run(record: ExperimentRecord, registry_dir: Path) -> Path:
    """Write the record as registry_dir/<run_id>.json and append one line to registry_dir/index.jsonl."""
    record.finalize()
    registry_dir = Path(registry_dir)
    registry_dir.mkdir(parents=True, exist_ok=True)
    path = registry_dir / f"{record.run_id}.json"
    path.write_text(json.dumps(record.to_dict(), indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    line = {"run_id": record.run_id, "name": record.name, "created_utc": record.created_utc, "n_seeds": len(record.seeds),
            "backend": record.backend.get("backend"), "wall_time_s": record.backend.get("wall_time_s"),
            "estimated_cost_usd": record.backend.get("estimated_cost_usd"), "commit": record.code.get("commit")}
    with open(registry_dir / "index.jsonl", "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(line, default=str) + "\n")
    return path


def artifact_record(path: Path) -> dict:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for b in iter(lambda: fh.read(1 << 24), b""):
            h.update(b)
    return {"path": paths.relpath_for_record(path), "sha256": h.hexdigest(), "size_bytes": path.stat().st_size}
