"""Truth isolation while a discovery method runs inside a Phase 2 harness job (review E finding 7).

Synthetic evaluations keep their answers on disk: a suite's ``truth/`` tree, the private permutations of node-order variants.
While a method's ``discover`` runs, the harness wraps it in :func:`truth_guard`. A CPython audit hook (PEP 578; installed once
per process and inert when no guard is active) then refuses to open, list or glob:

* anything under the roots the harness passes (the suite's truth directory, a variant tree's private directory);
* any path with a component starting with ``truth`` (every Phase 2 suite keeps its answers under ``truth/``) or ending with
  ``__private`` (node-order permutations), and any build or audit report.

The refusal raises :class:`PermissionError`, so the run fails and is counted as a failure. Remote jobs keep the truth in
memory and score only after the method's result exists; no truth file is on the worker's disk while the method runs.

This is a guard against inadvertent leakage inside this repository's harness, not OS isolation (native readers such as
pyarrow's C++ file system are not audited). The hidden benchmark keeps its own sandbox (the frozen clean-room runner). Static
rules in ``tests/test_budget_integrity.py`` forbid method modules to import truth-bearing modules, to read files themselves or
to introspect the interpreter's frames and heap.
"""

from __future__ import annotations

import contextlib
import os
import sys
import threading
from collections.abc import Iterator
from pathlib import Path

GUARDED_EVENTS = frozenset({"open", "os.listdir", "os.scandir", "glob.glob", "glob.glob/2", "shutil.copyfile", "shutil.copytree",
                            "shutil.move", "os.rename"})
DENIED_COMPONENT = "truth"
DENIED_FILE_PREFIXES = ("build_report", "audit_report")

_LOCK = threading.Lock()
_STATE: dict = {"installed": False, "depth": 0, "roots": []}
_LOCAL = threading.local()


def _norm(p) -> str | None:
    try:
        if p is None or isinstance(p, int):
            return None
        s = os.fspath(p)
        if isinstance(s, bytes):
            s = s.decode(errors="ignore")
        if not s:
            return None
        return os.path.normcase(os.path.abspath(s))
    except (TypeError, ValueError, OSError):
        return None


def is_denied(path) -> bool:
    """Whether ``path`` lies under a guarded root, has a component starting with ``truth`` or ending with ``__private``, or is a
    build / audit report (only meaningful while a guard is active)."""
    p = _norm(path)
    if p is None:
        return False
    parts = [x.lower() for x in p.replace("\\", "/").split("/") if x]
    if any(x.startswith(DENIED_COMPONENT) or x.endswith("__private") for x in parts):
        return True
    if parts and parts[-1].startswith(DENIED_FILE_PREFIXES):
        return True
    return any(p == r or p.startswith(r + os.sep) for r in _STATE["roots"])


def _hook(event: str, args: tuple) -> None:
    if not _STATE["depth"] or event not in GUARDED_EVENTS or not args:
        return
    if getattr(_LOCAL, "busy", False):
        return
    _LOCAL.busy = True
    try:
        if is_denied(args[0]) or (event.startswith("shutil.") and len(args) > 1 and is_denied(args[1])):
            raise PermissionError(f"truth guard: {event} of {args[0]!r} refused while a discovery method runs")
    finally:
        _LOCAL.busy = False


def _install() -> None:
    with _LOCK:
        if not _STATE["installed"]:
            sys.addaudithook(_hook)
            _STATE["installed"] = True


@contextlib.contextmanager
def truth_guard(*roots: Path | str | None) -> Iterator[None]:
    """Refuse file access to ``roots`` (and to any ``truth`` directory) inside the ``with`` block."""
    _install()
    added = [r for r in (_norm(x) for x in roots if x is not None) if r]
    with _LOCK:
        _STATE["roots"] = list(_STATE["roots"]) + added
        _STATE["depth"] += 1
    try:
        yield
    finally:
        with _LOCK:
            _STATE["depth"] -= 1
            rest = list(_STATE["roots"])
            for r in added:
                rest.remove(r)
            _STATE["roots"] = rest


def guard_active() -> bool:
    return bool(_STATE["depth"])
