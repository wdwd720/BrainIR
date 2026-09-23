"""Compute layer: local/Modal backends for parallel simulations and an experiment registry with content-addressed records."""

from .backend import LocalBackend, ModalBackend, RunStats, get_backend, modal_available
from .registry import ExperimentRecord, content_hash, register_run

__all__ = ["ExperimentRecord", "LocalBackend", "ModalBackend", "RunStats", "content_hash", "get_backend", "modal_available",
           "register_run"]
