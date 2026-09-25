"""Run-time guards for executing method code on the orchestrator side (tournament fits and evaluations; goal4 sections 3, 29).

Two modes, both Python audit hooks (they cannot be removed once installed):

FIT mode (`install_fit_guard`): the whole fitting process may read only allowed roots inside the protected areas. Every file-system
event whose path lies under a PROTECTED root (the development drive's project directories and the user's credential / session
stores) is refused unless it lies under an ALLOWED root (the method's code copy, the public dataset of the systems being fitted, the
output directory, the simulation-service queue, a private temp directory, the Python environment and the evaluator library). Paths
outside the protected roots (the operating system, the Python installation) stay readable. Process creation and network connections
are refused.

EVAL mode (`install_eval_guard`): the evaluator process holds hidden data in memory and calls the method's model. The same rule is
applied only while a frame of the method's code is on the call stack, so method code can never open hidden files, start processes
or connect anywhere, while the evaluator itself keeps normal access.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

FS_EVENTS = {"open", "os.listdir", "os.scandir", "os.chdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.mkdir",
             "shutil.copyfile", "shutil.copytree", "shutil.rmtree", "glob.glob", "os.walk", "os.symlink", "os.link", "os.truncate"}
DENY_ALWAYS = {"os.system", "subprocess.Popen", "os.startfile", "os.exec", "os.posix_spawn", "os.spawn", "socket.connect",
               "socket.bind", "socket.getaddrinfo", "urllib.Request"}


def _norm(p) -> str:
    try:
        s = os.fsdecode(p)
    except Exception:  # noqa: BLE001
        return ""
    try:
        return os.path.normcase(os.path.abspath(s))
    except Exception:  # noqa: BLE001
        return os.path.normcase(s)


def default_protected() -> list[str]:
    home = Path.home()
    return [_norm(p) for p in (Path("C:/Dev"), home / ".claude", home / ".claude.json", home / ".modal.toml", home / ".ssh",
                               home / "AppData" / "Local" / "Temp")]


def environment_roots() -> list[str]:
    """The Python environment and the evaluator library (read-only needs of any method)."""
    import brainir_state
    roots = {sys.prefix, sys.base_prefix, sys.exec_prefix, os.path.dirname(os.path.dirname(brainir_state.__file__))}
    for p in sys.path:
        if p and "site-packages" in p:
            roots.add(p)
    return [_norm(r) for r in roots if r]


class _Policy:
    def __init__(self, allowed: list[str], protected: list[str]):
        self.allowed = [_norm(a) for a in allowed if a]
        self.protected = [_norm(p) for p in protected if p]

    @staticmethod
    def _under(path: str, root: str) -> bool:
        return path == root or path.startswith(root.rstrip("\\/") + os.sep)

    def permitted(self, path: str) -> bool:
        if not path:
            return True
        if not any(self._under(path, r) for r in self.protected):
            return True
        return any(self._under(path, a) for a in self.allowed)


TWO_PATH_EVENTS = {"os.rename", "os.replace", "os.link", "os.symlink", "shutil.copyfile", "shutil.copytree"}


def _paths(event, args):
    """The path arguments of an audit event (the first one; the first two for copy / rename / link events). Other arguments (modes,
    flags) are never paths."""
    n = 2 if event in TWO_PATH_EVENTS else 1
    for a in args[:n]:
        if isinstance(a, (str, bytes, os.PathLike)):
            yield _norm(a)


def install_fit_guard(allowed: list[str], protected: list[str] | None = None) -> None:
    pol = _Policy(list(allowed) + environment_roots(), protected or default_protected())

    def hook(event, args):
        if event in DENY_ALWAYS:
            raise PermissionError(f"method sandbox: {event} is not allowed while fitting")
        if event in FS_EVENTS:
            for p in _paths(event, args):
                if not pol.permitted(p):
                    raise PermissionError(f"method sandbox: {event} outside the allowed roots: {p}")

    sys.addaudithook(hook)


def install_eval_guard(method_dirs: list[str], allowed: list[str], protected: list[str] | None = None) -> None:
    mdirs = [_norm(d) for d in method_dirs]
    pol = _Policy(list(allowed) + environment_roots(), protected or default_protected())

    def method_on_stack() -> bool:
        f = sys._getframe(2)
        while f is not None:
            fn = os.path.normcase(f.f_code.co_filename)
            if any(fn.startswith(d) for d in mdirs):
                return True
            f = f.f_back
        return False

    def hook(event, args):
        if event not in FS_EVENTS and event not in DENY_ALWAYS:
            return
        if not method_on_stack():
            return
        if event in DENY_ALWAYS:
            raise PermissionError(f"method sandbox: {event} is not allowed in method code during evaluation")
        for p in _paths(event, args):
            if not pol.permitted(p):
                raise PermissionError(f"method sandbox: method code may not {event} outside the allowed roots during evaluation: {p}")

    sys.addaudithook(hook)
