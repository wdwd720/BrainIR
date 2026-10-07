"""Host gate for bit-reproducible CPU numerics on Modal (container side; LOG P3-D26 / P3-D27).

Modal CPU hosts are heterogeneous. On hosts with AVX-512, numpy / OpenBLAS / torch dispatch other kernels than on the development
machine, and the real engine's trajectories and the locked fits are then not bit-identical (Phase 3 found 13 of 20 records
differing). Hosts without AVX-512 (and with AVX2 + FMA) run the development machine's kernels. `check()` reads /proc/cpuinfo;
a job refuses BEFORE computing anything when the host is not admissible, stops fetching further inputs (so the container exits and
its slot goes to a fresh host) and returns a refusal marker; the orchestrator re-submits the input (brainir_causal.p4modal.app).
Self-contained: imported in the container's main process, no dependencies (numpy / scipy / threadpoolctl are imported lazily by
`host_fingerprint` only).

LOCAL PATHS (review H, M5): the same rule applies to every real-system simulation outside Modal (`require_admissible`, called by the
real engine); on Windows the flags come from `IsProcessorFeaturePresent`. `host_fingerprint` is the numerics-relevant description of
the host (CPU and SIMD flags, numpy / scipy / BLAS / torch versions, the pins in force) that every stored record carries.
"""

from __future__ import annotations

import os
import platform
import sys
import threading

REFUSED = "__refused__"
PIN_VARS = ("NPY_DISABLE_CPU_FEATURES", "ATEN_CPU_CAPABILITY", "OPENBLAS_CORETYPE", "MKL_ENABLE_INSTRUCTIONS", "OMP_NUM_THREADS")
_HOST: dict | None = None
_FINGERPRINT: dict | None = None


def _windows_cpu() -> dict:
    """The gate's flags on Windows (no /proc/cpuinfo): IsProcessorFeaturePresent (40 = AVX2, 41 = AVX512F); FMA3 from numpy's own
    hardware detection (the pins disable AVX-512 groups only)."""
    import ctypes
    k32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    fma = False
    try:
        try:
            from numpy._core._multiarray_umath import __cpu_features__ as cf
        except ImportError:  # numpy < 2
            from numpy.core._multiarray_umath import __cpu_features__ as cf  # type: ignore[no-redef]
        fma = bool(cf.get("FMA3"))
    except Exception:  # noqa: BLE001, S110 - FMA is informative only (not part of the rule)
        pass
    proc = platform.processor()
    return {"model": proc, "vendor": proc.rsplit(",", 1)[-1].strip() if "," in proc else "", "avx512f": bool(k32.IsProcessorFeaturePresent(41)),
            "avx2": bool(k32.IsProcessorFeaturePresent(40)), "fma": fma}


def host_cpu(cpuinfo: str | None = None) -> dict:
    """Model name, vendor and the SIMD flags that decide the BLAS kernels, from /proc/cpuinfo (or the given text; on Windows from
    the OS when no text is given)."""
    if cpuinfo is None:
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
                cpuinfo = fh.read()
        except OSError:
            cpuinfo = ""
            if os.name == "nt":
                try:
                    return _windows_cpu()
                except Exception:  # noqa: BLE001, S110 - falls through to "no flags" (not admissible)
                    pass
    model, vendor, flags = "", "", set()
    for line in cpuinfo.splitlines():
        key, _, val = line.partition(":")
        key = key.strip()
        if key == "model name" and not model:
            model = val.strip()
        elif key == "vendor_id" and not vendor:
            vendor = val.strip()
        elif key == "flags" and not flags:
            flags = set(val.split())
    return {"model": model, "vendor": vendor, "avx512f": "avx512f" in flags, "avx2": "avx2" in flags, "fma": "fma" in flags}


def host_class(cpuinfo: str | None = None) -> dict:
    """The host's CPU CLASS as the host-gate study names it (research/phase4/HOST_GATE_STUDY.md: vendor / cpu family / cpuid model /
    ISA): gVisor reports no model name ("unknown"), so the numeric family and model identify the class, e.g.
    "AuthenticAMD/fam25/model1/avx2". Informational (the numerics self-test records it); the gate's rule is `admissible`."""
    if cpuinfo is None:
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
                cpuinfo = fh.read()
        except OSError:
            cpuinfo = ""
    f: dict = {}
    for line in cpuinfo.splitlines():
        key, _, val = line.partition(":")
        key = key.strip()
        if key in ("vendor_id", "cpu family", "model", "stepping") and key not in f:
            f[key] = val.strip()
    h = host_cpu(cpuinfo)
    isa = "avx512" if h["avx512f"] else ("avx2" if h["avx2"] else "no-avx2")
    return {"vendor": f.get("vendor_id", ""), "family": f.get("cpu family", ""), "model": f.get("model", ""),
            "stepping": f.get("stepping", ""), "isa": isa,
            "key": f"{f.get('vendor_id', '?')}/fam{f.get('cpu family', '?')}/model{f.get('model', '?')}/{isa}"}


def admissible(h: dict | None = None) -> bool:
    """The Phase 3 host rule unchanged (LOG P3-D26 / P3-D27): no AVX-512, AVX2 present."""
    h = this_host() if h is None else h
    return (not h["avx512f"]) and h["avx2"]


def this_host() -> dict:
    """`host_cpu()` of this process (cached)."""
    global _HOST
    if _HOST is None:
        _HOST = host_cpu()
    return dict(_HOST)


def require_admissible(what: str) -> None:
    """Refuse `what` (a real-system simulation) on a host outside the gate (review H, M5: records from other kernels would mix
    silently under one store key). The pins alone are not enough: OpenBLAS dispatches its own kernels."""
    h = this_host()
    if not admissible(h):
        raise RuntimeError(f"{what} runs only on gated hosts (no AVX-512, AVX2 present; review H M5); this host: "
                           f"avx512f={h['avx512f']} avx2={h['avx2']}")


#: the reference platform (LOG P4-D32): the pinned numerical stack of docker/p4sandbox/image.json (python by major.minor, torch by its
#: base version: the Modal images use debian_slim's 3.12 and PyPI's CUDA build of the same torch) and the numerics pins of
#: p4modal.images.CPU_PINS. tests/test_reference_platform.py keeps these equal to the image record and to CPU_PINS.
REFERENCE_STACK = {"python": "3.12", "numpy": "2.5.3", "scipy": "1.18.1", "torch": "2.14.0"}
REFERENCE_PINS = {"NPY_DISABLE_CPU_FEATURES": "X86_V4 AVX512_ICL AVX512_SPR", "ATEN_CPU_CAPABILITY": "avx2"}


def reference_platform_problems(fp: dict | None = None) -> list[str]:
    """Why this process (or the fingerprint `fp`) is not the reference platform: [] when it is Linux on a gated host with the CPU pins
    in force and the pinned stack."""
    fp = host_fingerprint() if fp is None else fp
    out = []
    if fp.get("os") != "Linux":
        out.append(f"os {fp.get('os')} (reference: Linux)")
    if not fp.get("admissible"):
        out.append("host outside the gate (AVX-512 present or AVX2 missing)")
    pins = fp.get("pins") or {}
    out += [f"pin {k} not {v!r}" for k, v in REFERENCE_PINS.items() if pins.get(k) != v]
    py = ".".join(str(fp.get("python") or "").split(".")[:2])
    if py != REFERENCE_STACK["python"]:
        out.append(f"python {fp.get('python')} (reference {REFERENCE_STACK['python']})")
    for k in ("numpy", "scipy"):
        if str(fp.get(k)) != REFERENCE_STACK[k]:
            out.append(f"{k} {fp.get(k)} (reference {REFERENCE_STACK[k]})")
    tv = fp.get("torch")
    if tv is not None and str(tv).split("+")[0] != REFERENCE_STACK["torch"]:
        out.append(f"torch {tv} (reference {REFERENCE_STACK['torch']})")
    return out


def require_reference_platform(what: str) -> None:
    """Refuse `what` (a simulation of a benchmark system) outside the reference platform: a record computed elsewhere could carry the
    same store key with different numbers (review H round 3, NEW-1; LOG P4-D32)."""
    bad = reference_platform_problems()
    if bad:
        raise RuntimeError(f"{what} runs only on the reference platform (the pinned Linux image on a gated host; LOG P4-D32): "
                           + "; ".join(bad))


def host_fingerprint() -> dict:
    """The numerics-relevant description of this process's host (cached): CPU model / vendor / gate flags, whether the host is
    admissible, the numpy SIMD extensions in force, numpy / scipy / BLAS (library, version, kernel architecture, threads) / torch
    versions and the pin variables. Never a path."""
    global _FINGERPRINT
    if _FINGERPRINT is None:
        h = this_host()
        fp: dict = {"cpu": h, "admissible": admissible(h), "os": platform.system(), "machine": platform.machine(),
                    "python": platform.python_version(), "pins": {k: os.environ.get(k) for k in PIN_VARS if os.environ.get(k) is not None}}
        try:
            import numpy
            fp["numpy"] = numpy.__version__
            try:
                from numpy._core._multiarray_umath import __cpu_features__ as cf
            except ImportError:  # numpy < 2
                from numpy.core._multiarray_umath import __cpu_features__ as cf  # type: ignore[no-redef]
            fp["numpy_simd"] = sorted(k for k in ("AVX2", "FMA3", "AVX512F", "AVX512_SKX", "AVX512_ICL", "AVX512_SPR") if cf.get(k))
        except Exception:  # noqa: BLE001, S110
            pass
        try:
            import scipy
            fp["scipy"] = scipy.__version__
        except Exception:  # noqa: BLE001, S110
            pass
        try:
            import threadpoolctl
            fp["blas"] = [{k: d.get(k) for k in ("internal_api", "version", "architecture", "threading_layer", "num_threads")}
                          for d in threadpoolctl.threadpool_info()]
        except Exception:  # noqa: BLE001, S110
            pass
        tv = getattr(sys.modules.get("torch"), "__version__", None)
        if tv is None:
            try:
                from importlib.metadata import version
                tv = version("torch")
            except Exception:  # noqa: BLE001
                tv = None
        fp["torch"] = str(tv) if tv is not None else None
        _FINGERPRINT = fp
    return json_copy(_FINGERPRINT)


def json_copy(d: dict) -> dict:
    import json
    return json.loads(json.dumps(d))


_SELFTEST: dict | None = None
_SELFTEST_LOCK = threading.Lock()


def numerics_selftest(timeout_s: float = 180.0) -> dict:
    """The container-start NUMERICS SELF-TEST's verdict (p4modal.selftest; research/phase4/HOST_GATE_STUDY.md "Hardening"): the fixed
    micro battery run ONCE per container in fresh processes and compared with the recorded reference. Cached; concurrent inputs of a
    packed container wait for the first. {"ok", "stale", "mismatch", "errors", "s", "wall_s", "absent", "host_class", "reference_class",
    "cached"} (+ "fingerprint" on a mismatch). stale = the reference was not built by this battery / library stack (a configuration
    fault, never a host verdict). reference_class: the host's class is one the reference was built on (informational: a new class that
    reproduces the reference passes)."""
    global _SELFTEST
    with _SELFTEST_LOCK:
        if _SELFTEST is None:
            _SELFTEST = _numerics_verdict(timeout_s)
            return dict(_SELFTEST, cached=False)
        return dict(_SELFTEST, cached=True)


def _numerics_verdict(timeout_s: float) -> dict:
    from . import selftest as S
    try:
        ref = S.load_reference()
    except Exception as e:  # noqa: BLE001 - no reference: nothing can be verified (a configuration fault)
        return {"ok": False, "stale": f"no numerics reference ({type(e).__name__}: {str(e)[:200]})"}
    run = S.run_battery(timeout_s)
    v = S.compare(run, ref)
    hc = host_class()["key"]
    v.update({"s": run.get("s"), "wall_s": run.get("wall_s"), "absent": run.get("absent"), "host_class": hc,
              "reference_class": hc in {h.get("class") for h in ref.get("reference_hosts") or []}})
    if not v["ok"] and not v.get("stale"):
        v["fingerprint"] = host_fingerprint()
    return v


def refusal(h: dict) -> dict:
    """Stop this container from taking more inputs (its slot then goes to a fresh host) and return the refusal marker."""
    try:
        import modal.experimental as E
        E.stop_fetching_inputs()
    except Exception:  # noqa: BLE001, S110 - outside Modal, or an older client
        pass
    return {REFUSED: True, "host": h}


def gated(fn):
    """Wrap a container callable: run it only on an admissible host (else return the refusal marker); the host description is added
    to a dict result under '__host__'."""
    def wrapper(payload):
        h = host_cpu()
        if not admissible(h):
            return refusal(h)
        r = fn(payload)
        if isinstance(r, dict):
            r["__host__"] = h
        return r
    wrapper.__name__ = getattr(fn, "__name__", "gated")
    return wrapper


def is_refusal(r) -> bool:
    return isinstance(r, dict) and bool(r.get(REFUSED))
