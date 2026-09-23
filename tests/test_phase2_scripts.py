"""Static guards for the Phase 2 scripts.

* Functions handed to a remote backend (`backend.map(fn, ...)`) must be importable on the worker: defined in the `brainir`
  package, never in the script itself (a script's functions live in `__main__`, which a Modal worker cannot import — this cost one
  full pair tournament once).
* Hidden-oracle access in Phase 2 scripts is confined to the post-lock tools.
"""

from __future__ import annotations

import ast
from pathlib import Path

from brainir import paths

SCRIPTS = paths.repo_root() / "scripts"
POST_LOCK_TOOLS = {"blind_eval.py", "reliability_sweep.py", "compare_reliability.py", "method_lock.py"}
EXCLUDERS = {"make_phase2_cleanroom.py"}  # names the oracle only to keep it OUT of the clean room


def _phase2_scripts() -> list[Path]:
    return sorted(p for p in SCRIPTS.glob("*.py") if "discovery" in p.read_text(encoding="utf-8") or "phase2" in p.read_text(encoding="utf-8"))


def test_remote_job_functions_come_from_the_library():
    bad = []
    for path in _phase2_scripts():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported_from_brainir = set()
        defined_here = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("brainir"):
                imported_from_brainir |= {a.asname or a.name for a in node.names}
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "map"
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == "backend" and node.args):
                fn = node.args[0]
                name = fn.id if isinstance(fn, ast.Name) else None
                if name is None or name in defined_here or name not in imported_from_brainir:
                    bad.append(f"{path.name}: backend.map({ast.unparse(fn)})")
    assert not bad, bad


def test_oracle_paths_only_in_post_lock_tools():
    offenders = []
    for path in _phase2_scripts():
        text = path.read_text(encoding="utf-8")
        if ("evaluator" in text and "evaluate.py" in text) or "oracle/" in text:
            if path.name not in POST_LOCK_TOOLS | EXCLUDERS:
                offenders.append(path.name)
    assert not offenders, offenders
