"""The post-lock drivers' run-artefact roots (scripts/p4/p4post/common.py) follow P4_RUN_BASE, the variable the Linux driver container
exports (scripts/p4/linux_driver.py) and levelc_lib / tournament read; without it the Windows defaults are unchanged."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _load(tag: str):
    sys.path.insert(0, str(REPO / "scripts" / "p4"))
    try:
        spec = importlib.util.spec_from_file_location(f"p4post_common_{tag}", REPO / "scripts" / "p4" / "p4post" / "common.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(REPO / "scripts" / "p4"))


def test_defaults_are_unchanged_without_the_variable(monkeypatch):
    monkeypatch.delenv("P4_RUN_BASE", raising=False)
    C = _load("default")
    base = Path("C:/Dev/BrainIR_p4run")
    assert C.RUN_BASE == base
    assert (C.RUN_ROOT, C.RUN_DRY_ROOT, C.ISO_STAGE_ROOT) == (base / "postlock", base / "postlock_dryrun", base / "_iso_stage")
    assert C.RUN_DRY_ROOT in C.DRY_ROOTS


def test_the_variable_moves_every_run_root(monkeypatch, tmp_path):
    monkeypatch.setenv("P4_RUN_BASE", str(tmp_path / "runs"))
    C = _load("override")
    base = tmp_path / "runs"
    assert (C.RUN_ROOT, C.RUN_DRY_ROOT, C.ISO_STAGE_ROOT) == (base / "postlock", base / "postlock_dryrun", base / "_iso_stage")
    assert C.RUN_DRY_ROOT in C.DRY_ROOTS
    assert C.OUT_ROOT == REPO / "research" / "phase4" / "postlock"          # the research-side summaries stay in the repository
