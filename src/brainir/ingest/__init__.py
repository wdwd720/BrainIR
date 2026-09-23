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
    """Dispatch to the adapter registered for ``cfg.source.dataset``.

    Refuses a (source, build_version) pair that the registry does not define, so raw files of one version can never be
    written under another version's label (``registry.BUILD_VERSIONS`` is the only place that pairs them)."""
    from ..sources.registry import BUILD_VERSIONS

    key = (cfg.source.dataset, cfg.version)
    registered = BUILD_VERSIONS.get(key)
    if registered is None or registered[0] is not cfg.source:
        valid = sorted(f"{d}:{v}" for (d, v), (src, _) in BUILD_VERSIONS.items() if src is cfg.source)
        raise ValueError(f"build {key[0]}:{key[1]} is not a registered build of raw source {cfg.source.dataset}:{cfg.source.version}; "
                         f"valid builds of this source: {valid}")
    if cfg.source.dataset == "male-cns":
        from .malecns import build
    elif cfg.source.dataset == "manc":
        from .manc import build
    else:
        raise ValueError(f"no ingestion adapter registered for dataset {cfg.source.dataset!r}")
    return build(cfg)


__all__ = ["IngestAborted", "IngestConfig", "build_dataset"]
