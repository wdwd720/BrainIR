"""Provenance for Phase 2 experiments (goal3 section 43; review F findings 4-5).

* :func:`source_tree_hash` — SHA-256 over every ``brainir`` source file (relative path + LF-normalised content): identifies the
  code that actually ran, locally or inside a remote container (whose image is built from the working tree at launch).
* :func:`runtime_env` — Python, platform, the numerical package versions, BLAS thread settings, the simulator code version and
  the source-tree hash; every remote job returns it so the numerical environment of each result is recorded.
* :func:`launch_provenance` — git commit and dirty state of ``src/`` and ``scripts/`` at LAUNCH time (registry records are written
  when a campaign finishes; this is what the campaign actually launched with).
"""

from __future__ import annotations

import datetime as _dt
import functools
import hashlib
import importlib.metadata as md
import os
import platform
import subprocess
import sys
from pathlib import Path

PACKAGES = ("numpy", "scipy", "pandas", "pyarrow", "pydantic", "networkx")
BLAS_ENV = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")


@functools.lru_cache(maxsize=1)
def source_tree_hash() -> str:
    root = Path(__file__).resolve().parents[1]  # .../brainir
    h = hashlib.sha256()
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        h.update(p.relative_to(root).as_posix().encode())
        h.update(b"\0")
        h.update(p.read_bytes().replace(b"\r\n", b"\n"))
        h.update(b"\0")
    return h.hexdigest()


def package_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for p in PACKAGES:
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = None
    return out


def runtime_env() -> dict:
    from .simulator import sim_code_version

    return {"python": platform.python_version(), "implementation": sys.implementation.name, "platform": platform.platform(),
            "machine": platform.machine(), "packages": package_versions(), "blas_env": {k: os.environ.get(k) for k in BLAS_ENV},
            "sim_code_version": sim_code_version(), "source_tree_sha256": source_tree_hash()}


def _git(repo: Path, *args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def launch_provenance(repo: Path | str | None = None) -> dict:
    """Code state at launch: commit, whether src/ or scripts/ differ from it (and a hash of that difference), source-tree hash."""
    from .simulator import sim_code_version

    repo = Path(repo) if repo is not None else Path(__file__).resolve().parents[3]
    status_src = _git(repo, "status", "--porcelain", "--", "src") or ""
    status_scripts = _git(repo, "status", "--porcelain", "--", "scripts") or ""
    diff = _git(repo, "diff", "HEAD", "--", "src", "scripts") or ""
    return {"commit": _git(repo, "rev-parse", "HEAD"), "dirty_src": bool(status_src.strip()), "dirty_scripts": bool(status_scripts.strip()),
            "diff_sha256": hashlib.sha256(diff.encode()).hexdigest() if diff else None, "source_tree_sha256": source_tree_hash(),
            "sim_code_version": sim_code_version(),
            "launched_utc": _dt.datetime.now(_dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")}
