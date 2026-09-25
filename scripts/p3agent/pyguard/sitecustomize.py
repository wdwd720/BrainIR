"""Python-level guard for Phase 3 clean-room agents (goal4 section 3), loaded by every Python started with PYTHONPATH pointing here.

An audit hook refuses file-system and process events whose paths or command lines name a forbidden location (the main
repository, the Phase 2 clean room, Claude session stores, credentials, the orchestrator's temp folders, the guard's logs).
It complements the PreToolUse hook, which sees only the text of a command, not paths a program builds at run time.
"""

import os
import re
import sys

_BASE = os.path.basename(os.path.normpath(os.environ.get("P3_CLEAN_ROOT", "BrainIR_p3clean")))
_SUFFIX = re.escape(_BASE[len("brainir"):]) if _BASE.lower().startswith("brainir") and len(_BASE) > len("brainir") else "(?!)"
_FORBIDDEN = re.compile(
    rf"(?i)(dev[\\/]+brainir(?!{_SUFFIX})|brainir_p2clean|brainir_p3audit|\.claude[\\/]+projects|\.credentials|\.modal\.toml"
    rf"|\.claude\.json|c--dev-brainir(?!{_SUFFIX.replace('_', '-')})|phase2_report|hidden_eval|blind_eval|dng100_walking_cpg"
    r"|[\\/]oracle[\\/])")
_EVENTS = {"open", "os.listdir", "os.scandir", "os.chdir", "os.rename", "os.remove", "os.rmdir", "os.mkdir", "shutil.copyfile",
           "shutil.copytree", "shutil.rmtree", "os.system", "subprocess.Popen", "os.startfile", "os.exec", "os.posix_spawn",
           "os.spawn", "glob.glob", "os.walk"}


def _texts(args):
    for a in args:
        if isinstance(a, (str, bytes, os.PathLike)):
            try:
                yield os.fsdecode(a)
            except Exception:  # noqa: BLE001
                continue
        elif isinstance(a, (list, tuple)):
            yield from _texts(a)


def _hook(event, args):
    if event not in _EVENTS:
        return
    for t in _texts(args):
        if _FORBIDDEN.search(t):
            raise PermissionError(f"Phase 3 clean-room guard: {event} on a forbidden location is not allowed")


if os.environ.get("P3_CLEAN_ROOT"):
    sys.addaudithook(_hook)
