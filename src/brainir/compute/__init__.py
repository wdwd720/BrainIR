"""Compute layer: local/Modal backends for parallel simulations and an experiment registry with content-addressed records."""

from .backend import LocalBackend, ModalBackend, RunStats, Shared, get_backend, modal_available, resolve_shared, split_failures
from .registry import ExperimentRecord, artifact_record, content_hash, register_run

__all__ = ["ExperimentRecord", "LocalBackend", "ModalBackend", "RunStats", "Shared", "artifact_record", "content_hash", "get_backend",
           "modal_available", "register_run", "resolve_shared", "split_failures"]
