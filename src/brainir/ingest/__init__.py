"""Raw official files -> canonical BrainIR tables, one adapter per dataset lineage.

    from brainir.ingest import build_dataset
    from brainir.ingest.common import IngestConfig
    from brainir.sources.registry import resolve_build

    source, build_version = resolve_build("manc", "v1.2.1")
    build_dataset(IngestConfig(source=source, build_version=build_version))
"""

from __future__ import annotations

from .common import IngestAborted, IngestConfig


def build_dataset(cfg: IngestConfig) -> dict:
    """Dispatch to the adapter registered for ``cfg.source.dataset``."""
    if cfg.source.dataset == "male-cns":
        from .malecns import build
    elif cfg.source.dataset == "manc":
        from .manc import build
    else:
        raise ValueError(f"no ingestion adapter registered for dataset {cfg.source.dataset!r}")
    return build(cfg)


__all__ = ["IngestAborted", "IngestConfig", "build_dataset"]
