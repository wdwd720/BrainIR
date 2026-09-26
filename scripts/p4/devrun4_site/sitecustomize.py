"""Guard for Phase 4 room jobs on the remote runner (scripts/p4/devrun4.py; research/phase4/LEAKAGE_POLICY.md section 2.6).

Loaded (via PYTHONPATH) into the job's Python process tree only, never into the container's Modal runtime. An audit hook refuses:
- network: IP sockets (connect / bind / sendto) and name resolution; local (AF_UNIX) sockets and pipes stay allowed, so
  multiprocessing keeps working;
- starting programs other than this Python interpreter (subprocess / exec / spawn), so a job cannot reach the network through
  another binary.
The job's data directory is the public copy of the room's data/ and nothing else is mounted, so file access needs no guard.
"""
import os
import sys

_PY = os.path.realpath(sys.executable)
_NET = {"socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg", "socket.getaddrinfo", "socket.gethostbyname",
        "socket.gethostbyname_ex", "socket.gethostbyaddr", "socket.getnameinfo"}
_EXEC = {"subprocess.Popen", "os.exec", "os.posix_spawn", "os.spawn", "os.system", "os.startfile"}


def _is_local(address) -> bool:
    return isinstance(address, (str, bytes)) or address is None


def _hook(event, args):
    if event in _NET:
        if event in ("socket.connect", "socket.bind", "socket.sendto") and len(args) >= 2 and _is_local(args[1]):
            return
        raise PermissionError(f"remote runner: network access is not allowed ({event})")
    if event in _EXEC:
        exe = args[0] if args else None
        if exe is None and event == "subprocess.Popen" and len(args) > 1:     # (executable, args, cwd, env): program in args
            a = args[1]
            exe = (a[0] if a else None) if isinstance(a, (list, tuple)) else (a.split()[0] if isinstance(a, (str, bytes)) and a else None)
        if isinstance(exe, (list, tuple)):
            exe = exe[0] if exe else None
        if event == "os.system" or exe is None:
            raise PermissionError(f"remote runner: starting programs is not allowed ({event})")
        try:
            path = os.fsdecode(exe)
        except Exception:  # noqa: BLE001
            raise PermissionError(f"remote runner: starting programs is not allowed ({event})") from None
        name = os.path.splitext(os.path.basename(path))[0].lower()
        if os.path.realpath(path) != _PY and name not in ("python", "python3", "python3.12"):
            raise PermissionError(f"remote runner: only the Python interpreter may be started ({event}: {path})")


sys.addaudithook(_hook)
