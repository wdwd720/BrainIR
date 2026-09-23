"""Documentation that is generated from code must be up to date."""

from __future__ import annotations

import importlib.util

from brainir import paths
from brainir.schema.evidence import EVIDENCE_DESCRIPTIONS, EvidenceKind


def _generator():
    p = paths.repo_root() / "scripts" / "gen_schema_docs.py"
    spec = importlib.util.spec_from_file_location("gen_schema_docs", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_evidence_kind_is_described():
    assert set(EVIDENCE_DESCRIPTIONS) == set(EvidenceKind)


def test_schema_doc_is_current():
    gen = _generator()
    current = (paths.repo_root() / "docs" / "schema.md").read_text(encoding="utf-8")
    assert current == gen.render(), "docs/schema.md is stale: run `uv run python scripts/gen_schema_docs.py`"
