"""Remote execution with a pinned numerical environment (review F finding 4).

The frozen :class:`brainir.compute.backend.ModalBackend` installs lower-bound package pins, so a remote result's numerical
environment was whatever pip resolved when the image was first built. :class:`PinnedModalBackend` builds the image with the EXACT
versions installed locally (which ``uv.lock`` pins), the same Python minor version, and single-threaded BLAS; every Phase 2 job
additionally returns :func:`brainir.discovery.provenance.runtime_env`, so each record carries the environment it ran in.
"""

from __future__ import annotations

import importlib.metadata as md
import platform

from ..compute.backend import ModalBackend, get_backend

PINNED = ("numpy", "scipy", "pandas", "pyarrow", "pydantic", "networkx", "duckdb", "google-crc32c", "requests")
BLAS_ENV = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}


def pinned_requirements() -> list[str]:
    out = []
    for p in PINNED:
        try:
            out.append(f"{p}=={md.version(p)}")
        except md.PackageNotFoundError:
            continue
    return out


class PinnedModalBackend(ModalBackend):
    name = "modal-pinned"

    def _image(self):
        import modal

        py = ".".join(platform.python_version_tuple()[:2])
        base = modal.Image.debian_slim(python_version=py).pip_install(*pinned_requirements()).env(BLAS_ENV)
        if hasattr(modal.Image, "add_local_python_source"):
            return base.add_local_python_source("brainir", copy=True)
        from .. import paths

        return base.add_local_dir(str(paths.repo_root() / "src" / "brainir"), "/root/brainir")


def get_discovery_backend(kind: str = "local", **kw):
    """``kind='modal'`` -> the pinned-environment Modal backend; anything else -> the frozen factory."""
    if kind == "modal":
        return PinnedModalBackend(**kw)
    return get_backend(kind, **kw)
