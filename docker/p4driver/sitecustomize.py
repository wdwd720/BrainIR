"""Guard of the ORCHESTRATOR DRIVER image (scripts/p4/linux_driver.py; never an agent image).

On Linux a Windows drive path is a RELATIVE path ('C:/Dev/BrainIR_p4run' -> '<cwd>/C:/Dev/BrainIR_p4run'), so a driver that still
hard-codes a Windows root would silently create a directory named 'C:' inside the mounted repository. Every directory creation and
every file opened for writing through such a path is refused loudly here; such a driver must take its root from the environment
override the wrapper sets (P4_RUN_ROOT and the like)."""

import builtins
import io
import os
import re

_WIN = re.compile(r"^[A-Za-z]:[\\/]")


def _windows_path(p) -> bool:
    try:
        s = os.fspath(p)
    except TypeError:
        return False
    if isinstance(s, bytes):
        s = s.decode("utf-8", errors="replace")
    return bool(_WIN.match(s))


def _refuse(p):
    raise RuntimeError(f"Windows path {os.fspath(p)!r} used inside the Linux driver container (it would resolve relative to the "
                       "working directory): give the driver its Linux root through the environment (scripts/p4/linux_driver.py)")


_mkdir, _makedirs, _open = os.mkdir, os.makedirs, io.open


def _guarded_mkdir(path, *args, **kwargs):
    if _windows_path(path):
        _refuse(path)
    return _mkdir(path, *args, **kwargs)


def _guarded_makedirs(name, *args, **kwargs):
    if _windows_path(name):
        _refuse(name)
    return _makedirs(name, *args, **kwargs)


def _guarded_open(file, mode="r", *args, **kwargs):
    if isinstance(file, (str, bytes, os.PathLike)) and any(c in str(mode) for c in "wax+") and _windows_path(file):
        _refuse(file)
    return _open(file, mode, *args, **kwargs)


os.mkdir = _guarded_mkdir
os.makedirs = _guarded_makedirs
builtins.open = _guarded_open
io.open = _guarded_open
