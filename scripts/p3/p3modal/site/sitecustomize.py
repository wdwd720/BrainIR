"""Installed on the PYTHONPATH of every method subprocess in a Modal container: installs the Linux method guard before any other code
runs (p3modal.guard; the mode and roots come from P3M_* environment variables, set only for method subprocesses)."""

import os as _os

if _os.environ.get("P3M_GUARD_MODE"):
    import sys as _sys
    _sys.path.insert(0, "/repo/p3modal")
    from p3modal.guard import install_from_env as _install

    _install()
    del _sys.path[0]
