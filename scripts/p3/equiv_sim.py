"""Simulation-service check for the Modal Level C backend (orchestrator; PUBLIC data only).

simulate_public(sid) runs one PUBLIC validation protocol of a real system through the frozen simulation service (SimServer with the
public blind bundle; the same code path a fit container's simulator uses) and compares the result with the stored public trajectory.
It runs locally and, through the 'call' job kind, in a Modal container (scripts/p3/modal_tournament.py equiv-real); the two summaries
are compared there.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[2]          # the repository root (C:/Dev/BrainIR, or /repo in a Modal container)
IN_MODAL = Path("/fitvol").exists()
if IN_MODAL and "/repo/src" not in sys.path:
    sys.path.insert(0, "/repo/src")                 # the frozen Phase 1-2 library used by the real engine


def numeric_env() -> dict:
    """numpy's CPU dispatch and the BLAS kernels in this process (to explain hardware-dependent floating-point results)."""
    import os
    import numpy as np
    from numpy._core._multiarray_umath import __cpu_baseline__, __cpu_dispatch__, __cpu_features__
    info = {"numpy": np.__version__, "baseline": list(__cpu_baseline__), "dispatch": list(__cpu_dispatch__),
            "enabled": sorted(k for k, v in __cpu_features__.items() if v),
            "env": {k: os.environ.get(k) for k in ("NPY_DISABLE_CPU_FEATURES", "NPY_ENABLE_CPU_FEATURES", "OPENBLAS_CORETYPE")}}
    try:
        from threadpoolctl import threadpool_info
        info["blas"] = [{k: d.get(k) for k in ("internal_api", "version", "architecture", "num_threads")} for d in threadpool_info()]
    except Exception as e:  # noqa: BLE001
        info["blas"] = repr(e)
    return info


def simulate_public(sid: str) -> dict:
    import numpy as np
    from brainir_state.data import Dataset
    from brainir_state.simservice import SimServer
    bundle = Path("/fitvol/bundles/dng100_public_blind") if IN_MODAL else HERE / "benchmarks" / "dng100" / "public_blind"
    internal = (Path("/evalvol/suites/real_internal/systems_internal.json") if IN_MODAL
                else HERE / "benchmarks" / "state_discovery_v1" / "hidden" / "systems_internal.json")
    pub = HERE / "data" / "phase3" / "real_public"
    ds = Dataset(pub)
    row = next(r for r in ds.select(system_id=sid) if r["split"] == "val" and r["family"] == "kick_A")
    sysdef = {k: v for k, v in json.loads(internal.read_text(encoding="utf-8"))[sid].items() if k not in ("targets_heldout", "meta")}
    sysdef["cost"] = 3
    with tempfile.TemporaryDirectory() as td:
        (Path(td) / "store").mkdir(parents=True, exist_ok=True)
        srv = SimServer(Path(td), {sid: sysdef}, bundle, Path(td) / "store", {}, 100, 1)
        try:
            req = srv.q / "requests" / "r1.json"
            req.write_text(json.dumps({"agent": "equiv", "protocols": [row["protocol"]]}), encoding="utf-8")
            srv.handle(req)
            meta = json.loads((srv.q / "results" / "r1.json").read_text(encoding="utf-8"))
            with np.load(srv.q / "results" / "r1.npz") as z:
                x, y = z["i0_x"].astype(np.float64), z["i0_y"].astype(np.float64)
        finally:
            srv.pool.shutdown(wait=True)
    tr = ds.load(row)
    cpu = None
    try:
        cpu = next((ln.split(":", 1)[1].strip() for ln in Path("/proc/cpuinfo").read_text().splitlines() if ln.startswith("model name")), None)
    except OSError:
        import platform
        cpu = platform.processor()
    return {"system": sid, "protocol_key": row["key"], "items": meta["items"], "cpu": cpu,
            "summary": [float(x.sum()), float(y.sum()), float(np.abs(x).max()), float(np.abs(y).max()), float((x ** 2).sum())],
            "max_abs_diff_x_vs_stored": float(np.max(np.abs(x - tr.x.astype(np.float64)))) if x.shape == tr.x.shape else None,
            "max_abs_diff_y_vs_stored": float(np.max(np.abs(y - tr.y.astype(np.float64)))) if y.shape == tr.y.shape else None}
