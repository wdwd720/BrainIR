"""On the PYTHONPATH of every GUARDED subprocess in a Phase 4 Modal container: installs the method guard
(brainir_causal.runguard, fit or eval mode) before any method code runs. Mode and roots come from P4M_* environment variables, which
brainir_causal.p4modal.remote sets only for guarded subprocesses.

Before the guard: the numerical stack is imported (and CUDA initialised on GPU hosts). The fit guard refuses ctypes.dlopen for the
whole process (native code loaded later could do file I/O without audit events), and numpy / torch load shared libraries through
ctypes when first imported; importing them here, before the guard exists, keeps that rule without breaking ordinary imports.

In addition to runguard's rules, this layer refuses every access to another process's /proc entry (/proc/<pid>/..., pid != self),
as the Phase 3 container guard did: the container's entry process holds the Modal runtime's environment.
"""

import os as _os

_mode = _os.environ.get("P4M_GUARD_MODE", "")
if _mode in ("fit", "eval"):
    import importlib as _il

    for _m in ("numpy", "scipy", "scipy.linalg", "scipy.sparse", "scipy.sparse.linalg", "scipy.integrate", "scipy.optimize",
               "scipy.signal", "scipy.stats", "scipy.special", "scipy.interpolate", "sklearn", "sklearn.linear_model",
               "sklearn.decomposition", "sklearn.cross_decomposition", "threadpoolctl", "pydantic", "torch"):
        try:
            _il.import_module(_m)
        except Exception:  # noqa: BLE001 - a library that is not installed is simply not preloaded
            pass
    try:
        import torch as _t

        if _t.cuda.is_available():
            _t.cuda.init()
            _t.zeros(1, device="cuda")          # the first CUDA context (driver / cuBLAS loading happens here, before the guard)
    except Exception:  # noqa: BLE001
        pass

    import sys as _sys
    import threading as _th

    _self_pid = str(_os.getpid())
    _tl = _th.local()

    def _proc_hook(event, args, _pid=_self_pid):
        if getattr(_tl, "busy", False) or event not in ("open", "os.listdir", "os.scandir", "os.chdir") or not args:
            return
        a = args[0]
        if not isinstance(a, (str, bytes, _os.PathLike)):
            return
        _tl.busy = True
        try:
            s = _os.path.realpath(_os.fsdecode(a))          # relative paths, '..' and /proc/self/root/... routes resolved
        except Exception:  # noqa: BLE001
            s = _os.fsdecode(a)
        finally:
            _tl.busy = False
        if s.startswith("/proc/"):
            parts = s.split("/")
            head = parts[2] if len(parts) > 2 else ""
            if head.isdigit() and head != _pid:
                raise PermissionError(f"method sandbox (modal): {event} on another process's /proc entry: {s}")

    _sys.addaudithook(_proc_hook)

    from brainir_causal.runguard import install_eval_guard as _eval
    from brainir_causal.runguard import install_fit_guard as _fit

    _allowed = [a for a in _os.environ.get("P4M_ALLOWED", "").split(_os.pathsep) if a]
    _mdirs = [a for a in _os.environ.get("P4M_METHOD_DIRS", "").split(_os.pathsep) if a]
    if _mode == "fit":
        _fit(_allowed)
    else:
        _eval(_mdirs, _allowed)
