"""Linux counterpart of brainir_state.runguard for Modal containers (orchestrator side).

The frozen runguard protects the development machine's locations (C:/Dev, the user profile). In a Modal container the protected
locations are different, so every method subprocess started by p3modal.remote also installs this hook (via sitecustomize, before any
method code runs). Rules:
- FIT mode: every file-system event on a protected root (/fitvol, /evalvol, /repo, /tmp, /root, /home, /mnt, /data) is refused
  unless its REAL path lies under an allowed root (the job's own directory, the method snapshot, the public fit view, the Python
  environment, the evaluator library). /proc entries of other processes are refused. Process creation and network are refused.
- EVAL mode: the same rule, applied only while a frame of the method's code is on the call stack (the evaluator itself keeps normal
  access to the held-out data).
Paths are resolved with realpath, so links such as /proc/self/root cannot route around the protected roots.
"""

from __future__ import annotations

import os
import sys

FS_EVENTS = {"open", "os.listdir", "os.scandir", "os.chdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.mkdir",
             "shutil.copyfile", "shutil.copytree", "shutil.rmtree", "glob.glob", "os.walk", "os.symlink", "os.link", "os.truncate",
             "os.chmod", "os.chown", "os.utime", "shutil.move", "shutil.unpack_archive", "shutil.make_archive"}
TWO_PATH_EVENTS = {"os.rename", "os.replace", "os.link", "os.symlink", "shutil.copyfile", "shutil.copytree", "shutil.move"}
DENY_ALWAYS = {"os.system", "subprocess.Popen", "os.exec", "os.posix_spawn", "os.spawn", "os.startfile", "socket.connect",
               "socket.bind", "socket.getaddrinfo", "socket.sendto", "urllib.Request", "pty.spawn"}
PROTECTED = ("/fitvol", "/evalvol", "/repo", "/tmp", "/root", "/home", "/mnt", "/data", "/var/tmp", "/dev/shm")


def _real(p) -> str:
    try:
        s = os.fsdecode(p)
    except Exception:  # noqa: BLE001
        return ""
    try:
        return os.path.realpath(s)
    except Exception:  # noqa: BLE001
        return os.path.abspath(s)


def _under(path: str, root: str) -> bool:
    return path == root or path.startswith(root.rstrip("/") + "/")


class Policy:
    def __init__(self, allowed: list[str]):
        self.pid = str(os.getpid())
        self.allowed = [_real(a) for a in allowed if a]

    def permitted(self, path: str) -> bool:
        if not path:
            return True
        if path.startswith("/proc/"):
            head = path.split("/")[2]
            return not head.isdigit() or head == self.pid
        if not any(_under(path, r) for r in PROTECTED):
            return True
        return any(_under(path, a) for a in self.allowed)


def environment_roots() -> list[str]:
    roots = {sys.prefix, sys.base_prefix, sys.exec_prefix, "/repo/phase3/src", "/repo/p3modal_site"}
    for p in sys.path:
        if p and ("site-packages" in p or "dist-packages" in p):
            roots.add(p)
    return sorted(roots)


def _paths(event, args):
    n = 2 if event in TWO_PATH_EVENTS else 1
    for a in args[:n]:
        if isinstance(a, (str, bytes, os.PathLike)):
            yield _real(a)


def install(mode: str, allowed: list[str], method_dirs: list[str] | None = None) -> None:
    pol = Policy(list(allowed) + environment_roots())
    mdirs = [_real(d) for d in (method_dirs or [])]

    def method_on_stack() -> bool:
        f = sys._getframe(2)
        while f is not None:
            fn = f.f_code.co_filename
            if fn and any(fn.startswith(d) for d in mdirs):
                return True
            f = f.f_back
        return False

    def hook(event, args):
        if event not in FS_EVENTS and event not in DENY_ALWAYS:
            return
        if mode == "eval" and not method_on_stack():
            return
        if event in DENY_ALWAYS:
            raise PermissionError(f"method sandbox (modal): {event} is not allowed")
        for p in _paths(event, args):
            if not pol.permitted(p):
                raise PermissionError(f"method sandbox (modal): {event} outside the allowed roots: {p}")

    sys.addaudithook(hook)


def install_from_env() -> None:
    mode = os.environ.get("P3M_GUARD_MODE", "")
    if mode not in ("fit", "eval"):
        return
    allowed = [a for a in os.environ.get("P3M_ALLOWED", "").split(os.pathsep) if a]
    mdirs = [a for a in os.environ.get("P3M_METHOD_DIRS", "").split(os.pathsep) if a]
    install(mode, allowed, mdirs)
