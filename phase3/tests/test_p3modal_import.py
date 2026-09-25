"""The container-side Modal modules must import cleanly (a module-level error breaks every Modal job; review of re-lock 1).

p3modal.remote is imported with a stub for the optional `modal` package when it is not installed; nothing is contacted."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_container_modules_import_and_decorators_resolve():
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    for name in ("p3modal.remote", "p3modal.evaljob"):
        sys.modules.pop(name, None)
        mod = importlib.import_module(name)
        assert mod is not None
    remote = sys.modules["p3modal.remote"]
    for fn in ("run_fit", "run_eval", "run_call", "run_refs", "run_fit_real", "run_eval_real", "run_refs_real", "run_call_commit"):
        assert callable(getattr(remote, fn)), fn
    with remote.MemPeak() as mp:
        pass
    assert mp.mb is None or mp.mb >= 0


def test_orchestrator_modal_modules_import():
    sys.path.insert(0, str(ROOT / "scripts" / "p3"))
    for name in ("modal_tournament", "devrun", "generate_real_hidden"):
        sys.modules.pop(name, None)
        assert importlib.import_module(name) is not None
