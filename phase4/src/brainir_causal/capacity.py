"""Capacity and compute accounting (benchmarks/causal_state_v1/PROTOCOL.md section 5.15; goal5 section 19).

Reported next to every comparison, never folded into a score:

    param_counts(model, sids)        the model's SELF-REPORTED parameter counts (info()["n_params"]): encoder, transition, read-in and
                                     readout of the given systems, their total and a "reported" flag
    introspect_params(model)         an independent COUNT of the numeric arrays / torch parameters reachable from the model object
                                     (depth-limited walk of attributes, lists, tuples and dicts; shared arrays counted once). Reported
                                     beside the self-report as a plausibility check, never in its place
    ComputeMeter                     context manager measuring wall seconds, process CPU seconds (all threads of this process), and GPU
                                     wall seconds / peak GPU memory when CUDA was used inside the block
    CountingSimulator                wraps a simulator callback: calls, trajectories, simulated seconds, and cache hits when the records
                                     say so ("cached": True)
    capacity_record(model, sids, meter=..., sim=...)   the section 5.15 record: parameters (reported and counted), history length,
                                     training FLOPs / CPU / GPU seconds as reported by the method, measured compute, simulator use

A fit that runs in a sandboxed subprocess is measured inside that subprocess by its runner; `ComputeMeter.as_dict()` is the record
format either way.
"""

from __future__ import annotations

import contextlib
import os
import time
from collections.abc import Callable
from typing import Any, Self

import numpy as np


# ------------------------------------------------------------------------------------------------------------ parameters
def param_counts(model_or_info: Any, sids: list[str] | tuple[str, ...]) -> dict:
    """Self-reported parameter counts for the systems `sids`: encoder / read-in / readout summed over them, the transition law once.
    Per-system values may be ints or dicts {sid: int}; a missing component counts 0; `reported` is False when the model reports
    nothing."""
    info = model_or_info if isinstance(model_or_info, dict) else (model_or_info.info() or {})
    npar = info.get("n_params") or {}

    def comp(name: str) -> int:
        v = npar.get(name)
        if v is None:
            return 0
        if isinstance(v, dict):
            return int(sum(int(v.get(s, 0) or 0) for s in sids))
        return int(v)

    enc, rin, ro = comp("encoder"), comp("read_in"), comp("readout")
    tr = npar.get("transition", 0)
    tr = int(sum(int(x or 0) for x in tr.values())) if isinstance(tr, dict) else int(tr or 0)
    hist = info.get("history") or {}
    return {"encoder": enc, "transition": tr, "read_in": rin, "readout": ro, "total": enc + tr + rin + ro, "reported": bool(npar),
            "history": {s: hist.get(s) for s in sids} if isinstance(hist, dict) else hist}


def introspect_params(model: Any, max_depth: int = 6, max_objects: int = 20000) -> dict:
    """Count numbers held in numpy arrays (float / int / complex) and torch tensors / parameters reachable from `model` (attributes,
    __dict__, lists, tuples, dicts, torch Modules). Each array object is counted once. Returns {"n_numbers", "n_arrays",
    "torch_parameters", "truncated"}."""
    seen: set[int] = set()
    n_num = n_arr = n_torch = 0
    truncated = False
    stack: list[tuple[Any, int]] = [(model, 0)]
    try:
        import torch
    except Exception:  # noqa: BLE001
        torch = None
    visited = 0
    while stack:
        obj, depth = stack.pop()
        if id(obj) in seen:
            continue
        seen.add(id(obj))
        visited += 1
        if visited > max_objects:
            truncated = True
            break
        if isinstance(obj, np.ndarray):
            if obj.dtype.kind in "fiuc":
                n_num += int(obj.size)
                n_arr += 1
            continue
        if torch is not None and isinstance(obj, torch.nn.Module):
            for p in obj.parameters():
                if id(p) not in seen:
                    seen.add(id(p))
                    n_torch += int(p.numel())
            continue
        if torch is not None and isinstance(obj, torch.Tensor):
            n_torch += int(obj.numel())
            continue
        if depth >= max_depth or isinstance(obj, (str, bytes, int, float, bool, type(None))):
            continue
        if isinstance(obj, dict):
            stack.extend((v, depth + 1) for v in obj.values())
        elif isinstance(obj, (list, tuple, set, frozenset)):
            stack.extend((v, depth + 1) for v in obj)
        elif hasattr(obj, "__dict__") and not isinstance(obj, type):
            stack.extend((v, depth + 1) for v in vars(obj).values())
    return {"n_numbers": int(n_num), "n_arrays": int(n_arr), "torch_parameters": int(n_torch), "truncated": truncated}


# ------------------------------------------------------------------------------------------------------------ compute
class ComputeMeter:
    """with ComputeMeter() as m: ...  ->  m.as_dict() = {"wall_s", "cpu_s", "gpu_s", "gpu_peak_mb", "cuda_used", "threads"}.
    cpu_s = process CPU time (user + system of all threads of this process; children are not included on Windows). gpu_s = wall time
    of the block when CUDA was initialised during or before it and a device was used (synchronised at exit); 0 otherwise."""

    def __init__(self):
        self.wall_s = self.cpu_s = self.gpu_s = 0.0
        self.gpu_peak_mb = 0.0
        self.cuda_used = False

    def __enter__(self) -> Self:
        self._t0 = time.perf_counter()
        self._c0 = time.process_time()
        self._cuda0 = self._cuda_state()
        if self._cuda0:
            with contextlib.suppress(Exception):
                import torch
                torch.cuda.reset_peak_memory_stats()
        return self

    @staticmethod
    def _cuda_state() -> bool:
        try:
            import torch
            return bool(torch.cuda.is_available() and torch.cuda.is_initialized())
        except Exception:  # noqa: BLE001
            return False

    def __exit__(self, *exc) -> None:
        cuda = self._cuda_state()
        if cuda:
            with contextlib.suppress(Exception):
                import torch
                torch.cuda.synchronize()
                self.gpu_peak_mb = float(torch.cuda.max_memory_allocated() / 2**20)
        self.wall_s = float(time.perf_counter() - self._t0)
        self.cpu_s = float(time.process_time() - self._c0)
        self.cuda_used = bool(cuda and self.gpu_peak_mb > 0)
        self.gpu_s = self.wall_s if self.cuda_used else 0.0

    def as_dict(self) -> dict:
        return {"wall_s": self.wall_s, "cpu_s": self.cpu_s, "gpu_s": self.gpu_s, "gpu_peak_mb": self.gpu_peak_mb,
                "cuda_used": self.cuda_used, "cpu_count": os.cpu_count()}


def measure(fn: Callable, *args, **kwargs) -> tuple[Any, dict]:
    """(fn(*args, **kwargs), compute record)."""
    with ComputeMeter() as m:
        out = fn(*args, **kwargs)
    return out, m.as_dict()


class CountingSimulator:
    """Wraps `simulate(protocol, **kw) -> record` or `simulate_many(protocols, **kw) -> [records]` (set many=True). Counts calls,
    trajectories, simulated seconds (the protocols' t_end) and cache hits (records carrying "cached": True)."""

    def __init__(self, fn: Callable, many: bool = False):
        self.fn, self.many = fn, many
        self.calls = self.trajectories = self.cached = 0
        self.simulated_s = 0.0

    def _count(self, protocols: list[dict], recs: list) -> None:
        self.trajectories += len(protocols)
        self.simulated_s += float(sum(float(p.get("t_end", 0.0)) for p in protocols))
        self.cached += int(sum(1 for r in recs if isinstance(r, dict) and r.get("cached")))

    def __call__(self, arg, **kw):
        self.calls += 1
        if self.many:
            recs = self.fn(arg, **kw)
            self._count(list(arg), list(recs))
            return recs
        rec = self.fn(arg, **kw)
        self._count([arg], [rec])
        return rec

    def as_dict(self) -> dict:
        return {"sim_calls": self.calls, "trajectories": self.trajectories, "simulated_s": self.simulated_s, "cached": self.cached}


def capacity_record(model: Any, sids: list[str] | tuple[str, ...], *, meter: ComputeMeter | dict | None = None,
                    sim: CountingSimulator | dict | None = None, introspect: bool = True) -> dict:
    """The PROTOCOL 5.15 record of one fitted model: self-reported parameters per component, the independent count, history length,
    the method's reported training cost (FLOPs, CPU / GPU seconds, simulator calls, experiments), the harness-measured compute of the
    fit, and the harness-measured simulator use."""
    info = model.info() or {}
    rec = {"params": param_counts(info, sids), "reported_train_cost": dict(info.get("train_cost") or {})}
    if introspect:
        try:
            rec["params_counted"] = introspect_params(model)
        except Exception as exc:  # noqa: BLE001
            rec["params_counted"] = {"error": f"{type(exc).__name__}: {exc}"[:200]}
    if meter is not None:
        rec["measured"] = meter.as_dict() if isinstance(meter, ComputeMeter) else dict(meter)
    if sim is not None:
        rec["simulator"] = sim.as_dict() if isinstance(sim, CountingSimulator) else dict(sim)
    return rec
