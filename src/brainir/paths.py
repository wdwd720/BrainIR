"""Filesystem layout for BrainIR data.

Layout (relative to the data root, default ``<repo>/data``)::

    raw/<dataset>/<version>/...        immutable official downloads (read-only files)
    processed/<dataset>/<version>/...  derived tables, rebuilt only by code
    cache/...                          disposable caches (API responses, temp)

Machine-readable manifests are always kept inside the repository at
``<repo>/data/manifests`` (they are small and committed to git), even when
the bulk data root is relocated with the ``BRAINIR_DATA_DIR`` environment
variable.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_DATA_DIR = "BRAINIR_DATA_DIR"


def repo_root() -> Path:
    """Return the repository root (the directory containing pyproject.toml)."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError(f"Could not locate repository root above {here}")


def data_root() -> Path:
    """Root of bulk data. Override with the BRAINIR_DATA_DIR environment variable."""
    override = os.environ.get(ENV_DATA_DIR)
    return Path(override).expanduser().resolve() if override else repo_root() / "data"


def raw_dir(dataset: str, version: str) -> Path:
    return data_root() / "raw" / dataset / version


def processed_dir(dataset: str, version: str) -> Path:
    return data_root() / "processed" / dataset / version


def cache_dir() -> Path:
    return data_root() / "cache"


def manifests_dir() -> Path:
    """Committed, machine-readable manifests (always inside the repo)."""
    return repo_root() / "data" / "manifests"


def relpath_for_record(path: Path) -> str:
    """Express a path relative to the data root (or repo root) for provenance records.

    Provenance records must never contain machine-specific absolute paths.
    """
    path = Path(path).resolve()
    for base, prefix in ((data_root(), "$DATA"), (repo_root(), "$REPO")):
        try:
            return f"{prefix}/{path.relative_to(base).as_posix()}"
        except ValueError:
            continue
    # Outside both roots (e.g. a test's temp dir): never leak the absolute path.
    return f"$EXTERNAL/{path.name}"
