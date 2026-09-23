"""Software sandbox for clean-room method runs (installed by run_method.py as `sitecustomize`; not imported by methods).

run_method.py copies this file to `<tmp>/sandbox_site/sitecustomize.py`, puts that directory on PYTHONPATH and sets
BRAINIR_SANDBOX_ROOTS (JSON list of allowed directories). Every interpreter started with that environment — the method
and any child process it spawns with multiprocessing — imports sitecustomize at start-up and installs a CPython audit hook
(PEP 578; hooks cannot be removed once installed). The hook refuses, by raising PermissionError:

  * opening, listing or stat-ing any absolute path outside the allowed roots (the bundle copy, the output directory,
    the Python installation and site-packages / editable-install paths, the temp directory, the method file's directory);
  * `subprocess.Popen`, `os.system`, `os.exec*`, `os.spawn*`, `os.posix_spawn`, `os.fork` (audited spawn paths);
  * socket creation/connection/name resolution (no network);
  * `ctypes` foreign calls and raw-memory access (loading libraries and resolving symbols stays allowed: ctypes and
    numpy do that at import);
  * imports of `modal`.

Reads of the repository (oracle, tier B, answer-bearing directories) and of user files (tokens) are impossible even for a
method that imports `brainir` and navigates from `brainir.paths.repo_root()`. Multiprocessing children inherit the
environment and therefore the hook. This is a defence against inadvertent and casual leakage, not OS-level isolation:
native code, `_winapi.CreateProcess` or a hand-rolled interpreter launch with a clean environment could bypass it. A
violation surfaces as `PermissionError('clean room: ...')` in the method (exit status non-zero) and is recorded in
run_record.json's stderr tail.
"""

from __future__ import annotations

import json
import os
import sys
import sysconfig

BLOCKED_EVENTS = {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "os.spawn",
                  "socket.__new__", "socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo",
                  "socket.gethostbyname", "socket.gethostbyaddr", "socket.getnameinfo",
                  # ctypes: loading/looking up symbols must stay allowed (ctypes itself resolves kernel32 at import, numpy imports
                  # ctypes); every FOREIGN CALL and raw-memory access is refused
                  "ctypes.call_function", "ctypes.cdata", "ctypes.cdata/buffer", "ctypes.addressof", "ctypes.string_at", "ctypes.wstring_at",
                  "ctypes.PyObj_FromPtr", "ctypes.set_exception", "ctypes.seh_exception", "ctypes.get_errno", "ctypes.set_errno",
                  "webbrowser.open", "os.startfile", "shutil.unpack_archive", "ftplib.connect", "smtplib.connect", "poplib.connect",
                  "imaplib.open", "nntplib.connect", "telnetlib.Telnet.open", "urllib.Request"}
PATH_EVENTS_PREFIXES = ("open", "os.", "shutil.", "glob.", "pathlib.", "io.open", "tempfile.mkstemp", "tempfile.mkdtemp")
BLOCKED_IMPORTS = {"modal"}


def _norm(p) -> str | None:
    try:
        if p is None or isinstance(p, int):
            return None
        s = os.fspath(p)
        if isinstance(s, bytes):
            s = s.decode(errors="ignore")
        if not s or not os.path.isabs(s):
            return None
        return os.path.normcase(os.path.realpath(s))
    except (TypeError, ValueError, OSError):
        return None


def make_hook(roots: list[str]):
    norm_roots = tuple(os.path.normcase(os.path.realpath(r)).rstrip("\\/") for r in roots)

    def allowed_path(p: str) -> bool:
        return any(p == r or p.startswith(r + os.sep) for r in norm_roots)

    def hook(event: str, args) -> None:
        if event in BLOCKED_EVENTS or event.startswith(("subprocess.", "socket.")):
            raise PermissionError(f"clean room: {event} is not allowed")
        if event == "import":
            top = (args[0] or "").split(".")[0]
            if top in BLOCKED_IMPORTS:
                raise PermissionError(f"clean room: import of {args[0]!r} is not allowed")
            return
        if event.startswith(PATH_EVENTS_PREFIXES):
            for a in args[:2]:
                p = _norm(a)
                if p is not None and not allowed_path(p):
                    raise PermissionError(f"clean room: {event} on {p!r} is outside the allowed roots")

    return hook


def default_roots(extra: list[str]) -> list[str]:
    py = {sysconfig.get_paths()[k] for k in ("stdlib", "platstdlib", "purelib", "platlib")}
    py |= {os.path.dirname(os.path.realpath(sys.executable)), sys.base_prefix, sys.prefix}
    py |= {e for e in sys.path if e}  # editable installs (brainir) live outside site-packages
    tmp = os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp"
    return [*extra, *sorted(py), tmp]


def install_from_env() -> bool:
    spec = os.environ.get("BRAINIR_SANDBOX_ROOTS")
    if not spec:
        return False
    sys.addaudithook(make_hook(default_roots(json.loads(spec))))
    return True


if __name__ != "__main__":  # imported as sitecustomize at interpreter start-up
    install_from_env()
