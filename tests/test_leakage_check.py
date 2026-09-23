"""Run the benchmark's automated leakage checks (bundles, oracle reachability, node lists) as a test.

The checks need the exported bundles under benchmarks/dng100/public*/ (committed) and the oracle; no dataset is read.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from brainir import paths

CHECK = paths.repo_root() / "benchmarks" / "dng100" / "cleanroom" / "leakage_check.py"


def _load():
    spec = importlib.util.spec_from_file_location("dng100_leakage_check", CHECK)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not CHECK.exists(), reason="benchmark package not present")
def test_benchmark_leakage_checks_pass():
    mod = _load()
    res = mod.run_checks()
    problems = {name: b for name, b in res["bundles"].items()
                if b.get("missing") or not b["manifest_verifies"]["ok"] or b["text_hits"] or b["parquet_hits"]}
    assert not problems, problems
    assert not res["library_import_scan"], res["library_import_scan"]
    assert res["library_leakage_guard_pytest"]["passed"], res["library_leakage_guard_pytest"]
    assert res["ok"]


def test_audit_document_is_current():
    audit = Path(CHECK).parent.parent / "LEAKAGE_AUDIT.md"
    text = audit.read_text(encoding="utf-8")
    assert "Overall: **PASS**" in text
