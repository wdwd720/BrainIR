"""The in-process TRIPWIRE of a model worker (research/phase4/EVAL_ARCHITECTURE.md; review F, F-B2).

This module is NOT a security boundary. Method code runs only in a model worker (`brainir_causal.worker`): a fresh OS process as an
unprivileged user, in a container without network, with a scrubbed environment and an empty private working directory, whose file
permissions let it read only the method snapshot and the public modules; the trusted driver holds every held-out array
(`brainir_causal.isolation`). Those OS-level properties are what isolate method code. The tripwire only makes the obvious violations
fail early with a clear message and counts them: an audit hook refuses file-system events under PROTECTED roots outside the ALLOWED
roots, process creation, network connections and ctypes library loading.

Its state lives in a closure (review F, F-B2: a module-level flag let method code switch the old guard off with one assignment), and
the hook is process-wide, so it also covers threads started with `exec` (the second F-B2 bypass defeated the old frame-based
evaluation guard, which is retired: `install_eval_guard` refuses). Code that walks the garbage collector can still reach the closure;
that is why nothing depends on it.

The scientific stack loads shared objects through ctypes on first import, which the hook refuses afterwards, so it is imported BEFORE
the hook (`preimport`: numpy / scipy / torch / scikit-learn and the third-party modules the method package imports, by an AST scan).
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

FS_EVENTS = {"open", "os.listdir", "os.scandir", "os.chdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.mkdir",
             "shutil.copyfile", "shutil.copytree", "shutil.rmtree", "glob.glob", "os.walk", "os.symlink", "os.link", "os.truncate",
             "os.chmod", "os.utime"}
DENY_ALWAYS = {"os.system", "subprocess.Popen", "os.startfile", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
               "socket.connect", "socket.bind", "socket.getaddrinfo", "urllib.Request", "ctypes.dlopen", "_winapi.CreateFile",
               "_winapi.CreateProcess", "winreg.OpenKey"}
TWO_PATH_EVENTS = {"os.rename", "os.replace", "os.link", "os.symlink", "shutil.copyfile", "shutil.copytree"}
LINUX_PROTECTED = ("/fitvol", "/evalvol", "/storevol", "/devvol", "/repo", "/data", "/root", "/home", "/mnt", "/tmp", "/srv", "/proc",
                   "/opt/p4jobs")
#: /proc entries a method may read (its own process and global, non-process information); other processes' entries are refused
PROC_ALLOWED = ("/proc/self", "/proc/thread-self", "/proc/cpuinfo", "/proc/meminfo", "/proc/stat", "/proc/loadavg", "/proc/sys",
                "/proc/filesystems", "/proc/version")
#: the scientific stack, imported BEFORE the tripwire is installed: these libraries load shared objects through ctypes (numpy / scipy /
#: torch / scikit-learn / threadpoolctl), which the tripwire refuses afterwards
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
    volume mounts, repository, job and home directories (Linux containers)."""
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
    """Import the scientific stack (PREIMPORT), the third-party modules the method package imports (AST scan) and `extra` BEFORE the
    tripwire is installed (best effort: a module that is not installed is skipped). Also runs threadpoolctl's library probe, which uses
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


class Tripwire:
    """What `install_tripwire` returns: the policy and a read-only view of the refused events (the list itself stays in the hook's
    closure)."""

    def __init__(self, policy: Policy, hits_view):
        self.policy = policy
        self._hits_view = hits_view

    @property
    def hits(self) -> list[tuple[str, str]]:
        return self._hits_view()


def install_tripwire(allowed: list[str], protected: list[str] | None = None, *, max_hits: int = 1000) -> Tripwire:
    """Install the tripwire for the whole process (every thread; audit hooks cannot be removed). File-system events under a protected
    root outside the allowed roots (plus the Python environment and this process's own /proc entries), process creation, network
    connections and ctypes library loading raise PermissionError. The state (policy, re-entrancy flag, refused events) is local to
    this call."""
    pol = Policy(list(allowed) + environment_roots() + _process_roots(), protected if protected is not None else default_protected())
    busy = threading.local()                 # re-entrancy flag (path resolution inside the hook must not re-enter the hook)
    hits: list[tuple[str, str]] = []

    def refuse(event: str, what: str, msg: str):
        if len(hits) < max_hits:
            hits.append((event, what[:300]))
        raise PermissionError(f"method tripwire: {msg}")

    def hook(event, args):
        if getattr(busy, "on", False):
            return
        if event in DENY_ALWAYS or event.startswith(("os.exec", "os.spawn")):
            refuse(event, "", f"{event} is not allowed in a model worker")
        if event in FS_EVENTS:
            busy.on = True
            try:
                bad = next((p for p in _paths(event, args) if not pol.permitted(p)), None)
            finally:
                busy.on = False
            if bad is not None:
                refuse(event, bad, f"{event} outside the allowed roots: {bad}")

    sys.addaudithook(hook)
    return Tripwire(pol, lambda: list(hits))


def install_fit_guard(allowed: list[str], protected: list[str] | None = None) -> Policy:
    """The former fit guard, now the tripwire (compatibility name); returns the policy."""
    return install_tripwire(allowed, protected).policy


def install_eval_guard(*_args, **_kwargs):
    """RETIRED (review F, F-B2 / F-B3): method code is never evaluated in the process that holds held-out data. Evaluations run the
    model in model workers (`brainir_causal.isolation.RemoteFresh`)."""
    raise RuntimeError("the in-process evaluation guard is retired (review F, F-B2 / F-B3): evaluate models through "
                       "brainir_causal.isolation (model workers); see research/phase4/EVAL_ARCHITECTURE.md")
