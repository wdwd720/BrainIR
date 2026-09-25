"""Python-level guard for Phase 3 clean-room agents (goal4 section 3), loaded by every Python started with PYTHONPATH pointing here.

Version 2 (after review F, finding F-B2). An audit hook applies RESOLVE-AND-CONTAIN to every file-system event:
- the path is resolved with realpath (relative paths against the current directory; 8.3 names, '.', '..' and links resolved);
- it is refused when it lies under a PROTECTED root and outside every ALLOWED root.

| roots | contents |
|---|---|
| PROTECTED | the development drive's project directory `C:\\Dev` and the user's profile (which holds `~/.claude`, the uv cache, ...) |
| ALLOWED | the room (P3_CLEAN_ROOT), the Python installation of this interpreter (base and venv prefixes), this guard's own directory |

It also:
- checks the file names of native `_winapi.CreateFile` calls;
- refuses to resolve native file / process / shell functions through ctypes (CreateFileW, NtCreateFile, _wopen, ShellExecuteW, ...);
- refuses network access (socket.connect / getaddrinfo / bind, urllib);
- checks child processes: their working directory and path arguments must resolve inside the allowed roots; Python children must keep
  this guard (no -I / -S / -E, no environment without PYTHONPATH / P3_CLEAN_ROOT).

It is active only when P3_CLEAN_ROOT is set. It complements the PreToolUse hook, which sees only the text of a command, and the
transcript audit. A native program (not Python) started by an allowed command is outside this hook's reach; the PreToolUse hook
restricts which programs may run.
"""

import os
import sys
import threading

_ROOT_ENV = os.environ.get("P3_CLEAN_ROOT")

if _ROOT_ENV:
    def _rp(p):
        try:
            return os.path.normcase(os.path.realpath(os.fsdecode(p)))
        except Exception:  # noqa: BLE001
            return os.path.normcase(os.path.abspath(os.fsdecode(p)))

    _ROOM = _rp(_ROOT_ENV)
    _HOME = _rp(os.path.expanduser("~"))
    _SELF = _rp(os.path.dirname(os.path.abspath(__file__)))
    _PROTECTED = [_rp("C:/Dev"), _HOME]
    _ALLOWED = [_ROOM, _SELF] + [_rp(p) for p in {sys.base_prefix, sys.exec_prefix, sys.prefix} if p]
    if os.environ.get("APPDATA"):
        _ALLOWED.append(_rp(os.path.join(os.environ["APPDATA"], "uv", "python")))
    _TLS = threading.local()
    _FS = {"open", "os.listdir", "os.scandir", "os.chdir", "os.rename", "os.replace", "os.remove", "os.rmdir", "os.mkdir", "os.walk",
           "os.fwalk", "shutil.copyfile", "shutil.copytree", "shutil.rmtree", "shutil.move", "os.symlink", "os.link", "os.truncate",
           "os.utime", "os.chmod", "os.startfile", "shutil.make_archive", "shutil.unpack_archive", "os.add_dll_directory"}
    _TWO = {"os.rename", "os.replace", "os.symlink", "os.link", "shutil.copyfile", "shutil.copytree", "shutil.move"}
    _NET = {"socket.connect", "socket.getaddrinfo", "socket.bind", "socket.gethostbyname", "socket.gethostbyaddr", "urllib.Request",
            "socket.sendto", "http.client.connect", "ftplib.connect", "smtplib.connect", "webbrowser.open"}
    _PROC = {"subprocess.Popen", "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.popen"}
    _NATIVE = {"createfilew", "createfilea", "createfile2", "createfiletransactedw", "createfiletransacteda", "ntcreatefile",
               "zwcreatefile", "ntopenfile", "zwopenfile", "openfile", "_lopen", "_lcreat", "findfirstfilew", "findfirstfilea",
               "findfirstfileexw", "findfirstfileexa", "copyfilew", "copyfilea", "copyfileexw", "movefilew", "movefilea", "movefileexw",
               "replacefilew", "createsymboliclinkw", "createhardlinkw", "_open", "_wopen", "fopen", "_wfopen", "_fsopen", "_wfsopen",
               "_sopen", "_wsopen", "shellexecutew", "shellexecutea", "shellexecuteexw", "createprocessw", "createprocessa", "winexec",
               "system", "_wsystem", "urldownloadtofilew", "urldownloadtofilea", "getfinalpathnamebyhandlew", "createdirectoryw"}

    def _under(p, r):
        return p == r or p.startswith(r.rstrip("\\/") + os.sep)

    def _permitted(p) -> bool:
        if isinstance(p, int) or p is None:
            return True
        s = os.fsdecode(p) if isinstance(p, (str, bytes, os.PathLike)) else None
        if s is None:
            return True
        if s.startswith(("\\\\.\\pipe\\", "\\\\?\\pipe\\")) or s.lower() in ("nul", "con", "/dev/null"):
            return True
        r = _rp(s)
        if not any(_under(r, pr) for pr in _PROTECTED):
            return True
        return any(_under(r, a) for a in _ALLOWED)

    def _deny(what):
        raise PermissionError(f"Phase 3 clean-room guard: {what} outside the room is not allowed")

    def _check_proc(event, args):
        if event == "subprocess.Popen":
            executable, argv, cwd, env = (list(args) + [None] * 4)[:4]
        elif event in ("os.system", "os.popen"):
            executable, argv, cwd, env = None, str(args[0]) if args else "", None, None
        else:
            executable, argv, cwd, env = (args[0] if args else None), (args[1] if len(args) > 1 else None), None, \
                (args[2] if len(args) > 2 else None)
        if cwd is not None and not _permitted(cwd):
            _deny("a child process working directory")
        toks = argv.split() if isinstance(argv, (str, bytes)) else [os.fsdecode(a) if isinstance(a, (bytes, os.PathLike)) else str(a)
                                                                      for a in (argv or [])]
        if isinstance(argv, bytes):
            toks = os.fsdecode(argv).split()
        if executable is not None:
            toks = [os.fsdecode(executable)] + toks
        base = os.path.basename(toks[0]).lower() if toks else ""
        for t in toks:
            t = t.strip("\"'")
            if ".." in t.replace("...", "") or t.startswith("~"):
                _deny("a child process argument with '..' or '~'")
            if ("\\" in t or "/" in t or (len(t) > 1 and t[1] == ":")) and not t.startswith("-") and not _permitted(t):
                _deny("a child process path argument")
        if base.startswith(("python", "py")) and any(t in ("-I", "-S", "-E", "-s") or (t.startswith("-") and not t.startswith("--")
                                                                                             and set(t[1:]) & set("ISE")) for t in toks[1:4]):
            _deny("a Python child without the guard (-I / -S / -E)")
        if env is not None:
            e = {os.fsdecode(k).upper(): os.fsdecode(v) for k, v in dict(env).items()}
            if "P3_CLEAN_ROOT" not in e or os.path.normcase(os.path.dirname(os.path.abspath(__file__))) not in \
                    os.path.normcase(e.get("PYTHONPATH", "")):
                _deny("a child process environment without the guard")

    def _hook(event, args):
        if getattr(_TLS, "busy", False):
            return
        if event not in _FS and event not in _NET and event not in _PROC and event not in ("_winapi.CreateFile", "ctypes.dlsym"):
            return
        _TLS.busy = True
        try:
            if event in _FS:
                n = 2 if event in _TWO else 1
                for a in args[:n]:
                    if not _permitted(a):
                        _deny(f"{event}")
            elif event == "_winapi.CreateFile":
                if args and not _permitted(args[0]):
                    _deny("a native file open")
            elif event == "ctypes.dlsym":
                name = args[1] if len(args) > 1 else None
                if isinstance(name, (str, bytes)) and os.fsdecode(name).lower() in _NATIVE:
                    raise PermissionError(f"Phase 3 clean-room guard: native file / process function {os.fsdecode(name)} is not allowed")
            elif event in _NET:
                raise PermissionError("Phase 3 clean-room guard: network access is not allowed")
            elif event in _PROC:
                _check_proc(event, args)
        finally:
            _TLS.busy = False

    sys.addaudithook(_hook)
