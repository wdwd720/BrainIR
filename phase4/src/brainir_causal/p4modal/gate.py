"""Host gate for bit-reproducible CPU numerics on Modal (container side; LOG P3-D26 / P3-D27).

Modal CPU hosts are heterogeneous. On hosts with AVX-512, numpy / OpenBLAS / torch dispatch other kernels than on the development
machine, and the real engine's trajectories and the locked fits are then not bit-identical (Phase 3 found 13 of 20 records
differing). Hosts without AVX-512 (and with AVX2 + FMA) run the development machine's kernels. `check()` reads /proc/cpuinfo;
a job refuses BEFORE computing anything when the host is not admissible, stops fetching further inputs (so the container exits and
its slot goes to a fresh host) and returns a refusal marker; the orchestrator re-submits the input (brainir_causal.p4modal.app).
Self-contained: imported in the container's main process, no dependencies.
"""

from __future__ import annotations

REFUSED = "__refused__"


def host_cpu(cpuinfo: str | None = None) -> dict:
    """Model name, vendor and the SIMD flags that decide the BLAS kernels, from /proc/cpuinfo (or the given text)."""
    if cpuinfo is None:
        try:
            with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as fh:
                cpuinfo = fh.read()
        except OSError:
            cpuinfo = ""
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


def admissible(h: dict | None = None) -> bool:
    """The Phase 3 rule unchanged (scripts/p3/hidden_gen_gate.py, level_c_fast.py): no AVX-512, AVX2 present."""
    h = host_cpu() if h is None else h
    return (not h["avx512f"]) and h["avx2"]


def refusal(h: dict) -> dict:
    """Stop this container from taking more inputs (its slot then goes to a fresh host) and return the refusal marker."""
    try:
        import modal.experimental as E
        E.stop_fetching_inputs()
    except Exception:  # noqa: BLE001 - outside Modal, or an older client
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
