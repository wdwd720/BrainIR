"""Run-time guards for executing method code on the orchestrator side (tournament fits, experiment loops and evaluations; goal5
sections 4-5, 51). Phase 4 version of the Phase 3 sandbox (phase3 `brainir_state.runguard`), with Phase 4 roots.

Two modes, both Python audit hooks (they cannot be removed once installed):

FIT mode (`install_fit_guard`): the whole fitting / experiment-loop process may touch only ALLOWED roots inside the PROTECTED areas.
Every file-system event whose path lies under a protected root (the development drive's project directories, the user's credential
and session stores, the temp directory; on Linux containers the Modal volumes and the repository mount) is refused unless it lies
under an allowed root (the method's code copy, the public data of the systems being fitted, the output directory, the simulation-
service queue, a private temp directory, the Python environment and the evaluation libraries). Paths outside the protected roots
(the operating system, the Python installation) stay readable. Process creation, network connections and ctypes library loading
are refused, so the scientific stack is imported BEFORE the guard (`preimport`: numpy / scipy / torch / scikit-learn load shared
objects through ctypes on first import); on Linux other processes' /proc entries are refused. The experiment
loop runs inside this process: its simulations go through the service's file queue, served by ANOTHER process (the synthetic
generator and the real engine never live in the method's process).

EVAL mode (`install_eval_guard`): the evaluator process holds held-out data in memory and calls the method's model. The same rule is
applied only while a frame of the method's code is on the call stack, so method code can never open held-out files, start processes
or connect anywhere, while the evaluator itself keeps normal access. (In-memory introspection is not blocked by an audit hook; the
locked method's code is audited instead, as in Phase 3.)
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

_TL = threading.local()          # re-entrancy flag: path resolution inside a hook must not re-enter the hook

FS_EVENTS = {"open", "os.listdir", "os.scandir", "os.chdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.mkdir",
             "shutil.copyfile", "shutil.copytree", "shutil.rmtree", "glob.glob", "os.walk", "os.symlink", "os.link", "os.truncate",
             "os.chmod", "os.utime"}
DENY_ALWAYS = {"os.system", "subprocess.Popen", "os.startfile", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
               "socket.connect", "socket.bind", "socket.getaddrinfo", "urllib.Request", "ctypes.dlopen", "_winapi.CreateFile",
               "_winapi.CreateProcess", "winreg.OpenKey"}
TWO_PATH_EVENTS = {"os.rename", "os.replace", "os.link", "os.symlink", "shutil.copyfile", "shutil.copytree"}
LINUX_PROTECTED = ("/fitvol", "/evalvol", "/storevol", "/devvol", "/repo", "/data", "/root", "/home", "/mnt", "/tmp", "/srv", "/proc")
#: /proc entries a method may read (its own process and global, non-process information); other processes' entries are refused
PROC_ALLOWED = ("/proc/self", "/proc/thread-self", "/proc/cpuinfo", "/proc/meminfo", "/proc/stat", "/proc/loadavg", "/proc/sys",
                "/proc/filesystems", "/proc/version")
#: the scientific stack, imported BEFORE a guard is installed: these libraries load shared objects through ctypes (numpy / scipy /
#: torch / scikit-learn / threadpoolctl), which the guards refuse afterwards (ctypes could bypass the audit hook)
PREIMPORT = ("numpy", "numpy.linalg", "numpy.fft", "numpy.random", "scipy", "scipy.linalg", "scipy.sparse", "scipy.sparse.linalg",
             "scipy.integrate", "scipy.optimize", "scipy.special", "scipy.stats", "scipy.signal", "scipy.interpolate", "scipy.spatial",
             "sklearn", "sklearn.linear_model", "sklearn.decomposition", "sklearn.cross_decomposition", "sklearn.neighbors",
             "sklearn.kernel_ridge", "sklearn.gaussian_process", "sklearn.preprocessing", "sklearn.model_selection", "sklearn.utils",
             "sklearn.metrics", "sklearn.cluster", "sklearn.manifold", "torch", "torch.nn", "torch.optim", "torch.linalg", "torch.func",
             "torch.distributions", "pandas", "pyarrow", "pydantic", "threadpoolctl", "joblib")


def _norm(p) -> str:
    try:
        s = os.fsdecode(p)
    except Exception:  # noqa: BLE001
        return ""
    try:
        return os.path.normcase(os.path.realpath(os.path.abspath(s)))
    except Exception:  # noqa: BLE001
        return os.path.normcase(s)


def default_protected() -> list[str]:
    """Protected roots of the platform: the development drive's projects, credential / session stores and temp (Windows); the
    volume mounts, repository and home directories (Linux containers)."""
    home = Path.home()
    out = [home / ".claude", home / ".claude.json", home / ".modal.toml", home / ".ssh", home / ".config" / "modal"]
    if os.name == "nt":
        out += [Path("C:/Dev"), home / "AppData" / "Local" / "Temp", home / "AppData" / "Roaming" / "uv"]
    else:
        out += [Path(p) for p in LINUX_PROTECTED]
    return [_norm(p) for p in out]


def _process_roots() -> list[str]:
    """Linux: this process's own /proc entries and the global ones (allowed); other processes' /proc entries stay protected."""
    if os.name == "nt":
        return []
    return [*PROC_ALLOWED, f"/proc/{os.getpid()}"]


def _method_imports(method_dir) -> list[str]:
    """Top-level third-party modules imported by the method package's files (an AST scan; relative and brainir_causal imports and
    modules of the package itself are skipped)."""
    import ast
    if not method_dir or not os.path.isdir(method_dir):
        return []
    own = {os.path.splitext(f)[0] for f in os.listdir(method_dir) if f.endswith(".py")}
    mods: set[str] = set()
    for f in sorted(os.listdir(method_dir)):
        if not f.endswith(".py"):
            continue
        try:
            with open(os.path.join(method_dir, f), encoding="utf-8") as fh:
                tree = ast.parse(fh.read())
        except (OSError, SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
                names = [node.module]
            else:
                continue
            for n in names:
                top = n.split(".")[0]
                if top in own or top == "brainir_causal":
                    continue
                mods.add(n)
    return sorted(mods)


def preimport(method_dir=None, extra: tuple[str, ...] = ()) -> dict:
    """Import the scientific stack (PREIMPORT), the third-party modules the method package imports (AST scan) and `extra` BEFORE a
    guard is installed (best effort: a module that is not installed is skipped). Also runs threadpoolctl's library probe, which uses
    ctypes. Returns {"imported": [...], "failed": [...]}."""
    import importlib
    import importlib.util
    done, failed = [], []
    for name in [*PREIMPORT, *_method_imports(method_dir), *extra]:
        try:
            if importlib.util.find_spec(name.split(".")[0]) is None:
                continue
            importlib.import_module(name)
            done.append(name)
        except Exception:  # noqa: BLE001 - an optional module that fails to import is recorded, never fatal
            failed.append(name)
    try:
        import threadpoolctl
        threadpoolctl.threadpool_info()
    except Exception:  # noqa: BLE001, S110 - the probe is an optimisation only
        pass
    return {"imported": done, "failed": failed}


def environment_roots() -> list[str]:
    """The Python environment and the evaluation libraries (read-only needs of any method): brainir_causal (the API), brainir_state
    (the frozen Phase 3 code, whose locked method is a Phase 4 baseline) and brainir (the frozen Phase 1 library)."""
    roots = {sys.prefix, sys.base_prefix, sys.exec_prefix}
    for mod in ("brainir_causal", "brainir_state", "brainir"):
        try:
            m = __import__(mod)
            roots.add(os.path.dirname(os.path.dirname(os.path.abspath(m.__file__))))
        except Exception:  # noqa: BLE001, S112 - a library that is not installed is simply not allowed
            continue
    for p in sys.path:
        if p and ("site-packages" in p or "dist-packages" in p):
            roots.add(p)
    return [_norm(r) for r in roots if r]


class Policy:
    def __init__(self, allowed: list[str], protected: list[str]):
        self.allowed = [_norm(a) for a in allowed if a]
        self.protected = [_norm(p) for p in protected if p]

    @staticmethod
    def under(path: str, root: str) -> bool:
        return path == root or path.startswith(root.rstrip("\\/") + os.sep)

    def permitted(self, path: str) -> bool:
        if not path:
            return True
        if not any(self.under(path, r) for r in self.protected):
            return True
        return any(self.under(path, a) for a in self.allowed)


def _paths(event, args):
    """The path arguments of an audit event (the first one; the first two for copy / rename / link events). Other arguments (modes,
    flags) are never paths."""
    n = 2 if event in TWO_PATH_EVENTS else 1
    for a in args[:n]:
        if isinstance(a, (str, bytes, os.PathLike)):
            yield _norm(a)


def install_fit_guard(allowed: list[str], protected: list[str] | None = None) -> Policy:
    pol = Policy(list(allowed) + environment_roots() + _process_roots(), protected if protected is not None else default_protected())

    def hook(event, args):
        if getattr(_TL, "busy", False):
            return
        if event in DENY_ALWAYS or event.startswith(("os.exec", "os.spawn")):
            raise PermissionError(f"method sandbox: {event} is not allowed while fitting")
        if event in FS_EVENTS:
            _TL.busy = True
            try:
                bad = next((p for p in _paths(event, args) if not pol.permitted(p)), None)
            finally:
                _TL.busy = False
            if bad is not None:
                raise PermissionError(f"method sandbox: {event} outside the allowed roots: {bad}")

    sys.addaudithook(hook)
    return pol


def install_eval_guard(method_dirs: list[str], allowed: list[str], protected: list[str] | None = None) -> Policy:
    # method directories in both spellings (resolved and plain absolute): frame file names are matched without touching the disk
    mdirs = sorted({_norm(d) for d in method_dirs} | {os.path.normcase(os.path.abspath(os.fsdecode(d))) for d in method_dirs})
    pol = Policy(list(allowed) + environment_roots() + _process_roots(), protected if protected is not None else default_protected())
    _seen: dict[str, bool] = {}

    def _is_method_file(fn: str) -> bool:
        hit = _seen.get(fn)
        if hit is None:
            n = os.path.normcase(os.path.abspath(fn)) if fn and not fn.startswith("<") else ""
            hit = bool(n) and any(n == d or n.startswith(d.rstrip("\\/") + os.sep) for d in mdirs)
            _seen[fn] = hit
        return hit

    def method_on_stack() -> bool:
        f = sys._getframe(2)
        while f is not None:
            if _is_method_file(f.f_code.co_filename):
                return True
            f = f.f_back
        return False

    def hook(event, args):
        if getattr(_TL, "busy", False):
            return
        is_fs = event in FS_EVENTS
        is_deny = event in DENY_ALWAYS or event.startswith(("os.exec", "os.spawn"))
        if not (is_fs or is_deny):
            return
        _TL.busy = True
        try:
            on_stack = method_on_stack()
            bad = None
            if on_stack and is_fs:
                bad = next((p for p in _paths(event, args) if not pol.permitted(p)), None)
        finally:
            _TL.busy = False
        if not on_stack:
            return
        if is_deny:
            raise PermissionError(f"method sandbox: {event} is not allowed in method code during evaluation")
        if bad is not None:
            raise PermissionError(f"method sandbox: method code may not {event} outside the allowed roots during evaluation: {bad}")

    sys.addaudithook(hook)
    return pol
