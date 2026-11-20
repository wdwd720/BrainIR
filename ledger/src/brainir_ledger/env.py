"""Host and library fingerprint, recorded with every job result and in every lock."""

from __future__ import annotations

import os
import platform
import sys

_CACHE: dict | None = None


def _cpu_info() -> dict:
    out = {"machine": platform.machine(), "processor": platform.processor()}
    try:
        with open("/proc/cpuinfo", encoding="utf-8") as fh:
            txt = fh.read()
        model = next((ln.split(":", 1)[1].strip() for ln in txt.splitlines() if ln.startswith("model name")), None)
        flags = next((ln.split(":", 1)[1].split() for ln in txt.splitlines() if ln.startswith("flags")), [])
        out.update(cpu_model=model, avx512f="avx512f" in flags, avx2="avx2" in flags, fma="fma" in flags,
                   n_logical=txt.count("processor\t:"))
    except OSError:
        try:
            import subprocess

            out["cpu_model"] = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True).stdout.strip()
        except Exception:  # noqa: BLE001
            out["cpu_model"] = None
    return out


def fingerprint() -> dict:
    """Python, platform, library versions, CPU model and the numerics-relevant environment variables (cached per process)."""
    global _CACHE
    if _CACHE is None:
        import numpy
        import pandas
        import pyarrow
        import scipy

        feats = {}
        try:
            from numpy._core._multiarray_umath import __cpu_features__ as cf  # type: ignore[attr-defined]

            feats = {k: bool(v) for k, v in cf.items() if v and (k.startswith("AVX") or k.startswith("FMA") or k.startswith("ASIMD"))}
        except Exception:  # noqa: BLE001
            pass
        _CACHE = {
            "python": sys.version.split()[0], "platform": platform.platform(), "numpy": numpy.__version__, "scipy": scipy.__version__,
            "pandas": pandas.__version__, "pyarrow": pyarrow.__version__, "cpu": _cpu_info(), "numpy_cpu_features_enabled": feats,
            "env": {k: os.environ.get(k) for k in ("NPY_DISABLE_CPU_FEATURES", "OPENBLAS_CORETYPE", "OPENBLAS_NUM_THREADS",
                                                    "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
        }
    return _CACHE
