"""Canonical BrainIR schema: evidence kinds, vocabularies, Arrow tables, record models."""

from .evidence import EvidenceKind
from .tables import CANONICAL_TABLES, SCHEMA_VERSION, TableSpec, conform

__all__ = ["EvidenceKind", "CANONICAL_TABLES", "SCHEMA_VERSION", "TableSpec", "conform"]
