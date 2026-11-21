"""Run 3, Stage 0 diagnosis, part 2 (RUN3_PROMPT section 4): is the T1R-T2R phase numerically fragile? DNg100 ONLY: the full-cord
G3 job (both DNg100 at 380, T = 2 s) for seeds 0..15, once at the default tolerance (rtol 2e-6, atol 5e-9, identical to run 1's
runs) and once 100x tighter (rtol 2e-8, atol 5e-11). Per seed: whether T1R and T2R are rhythmic, their phase offset, and the
active motor neurons of every leg. No hemilineage group is simulated.

    uv run --project ledger --no-sync python ledger/scripts/diag_v3_tolerance.py   # -> research/ledger/diag_v3/TOLERANCE_DIAG.json
"""

from __future__ import annotations

import json
import multiprocessing as mp
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "ledger" / "src"))
sys.path.insert(0, str(HERE))
from brainir.compute.backend import resolve_shared  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import legs as L  # noqa: E402
from brainir_ledger.jobs_v2 import run_job  # noqa: E402

_SHARED: dict = {}
SEEDS = range(16)


def _one(job):
    return run_job(resolve_shared(job, _SHARED))


def main() -> None:
    import calibrate_dng100 as CAL

    jobs, shared = CAL._full_jobs([380.0], SEEDS, 2.0, "tol")
    _SHARED.update(shared)
    all_jobs = []
    for j in jobs:
        all_jobs.append(dict(j, key=j["key"] + "|default"))
        m = dict(j["model"], rtol=2e-8, atol=5e-11)
        all_jobs.append(dict(j, key=j["key"] + "|tight", model=m))
    with mp.get_context("fork").Pool(processes=8, maxtasksperchild=1) as pool:
        res = {r["key"]: r for r in pool.imap_unordered(_one, all_jobs, chunksize=1)}
    ia, ib = L.LEGS.index("T1R"), L.LEGS.index("T2R")
    rows, same_active, offs = [], 0, {"default": [], "tight": []}
    for s in SEEDS:
        a, b = (res[k] for k in sorted(k for k in res if k.endswith(f"s{s}|default") or k.endswith(f"s{s}|tight")))
        row = {"seed": s}
        acts = {}
        for tag, r in (("default", a if a["key"].endswith("|default") else b), ("tight", b if b["key"].endswith("|tight") else a)):
            if "error" in r:
                row[tag] = {"error": r["error"][:200]}
                continue
            lg = r["extras"]["legs"]
            sig = L.unpack_traces(r["extras"]["leg_signals"])
            rhythmic = lg["T1R"]["score"] >= 0.5 and lg["T2R"]["score"] >= 0.5
            off = float(L.phase_offset(sig[:, ia], sig[:, ib])) if rhythmic else None
            if off is not None:
                offs[tag].append(off)
            acts[tag] = set(int(x) for x in r["extras"]["active_readout_positions"])
            row[tag] = {"T1R": round(lg["T1R"]["score"], 3), "T2R": round(lg["T2R"]["score"], 3), "offset_T1R_T2R": off,
                        "n_active_readout": len(acts[tag]), "digest": r.get("digest")}
        if len(acts) == 2:
            row["same_active_mns"] = acts["default"] == acts["tight"]
            same_active += row["same_active_mns"]
            if row["default"].get("offset_T1R_T2R") is not None and row["tight"].get("offset_T1R_T2R") is not None:
                d = np.angle(np.exp(1j * (row["default"]["offset_T1R_T2R"] - row["tight"]["offset_T1R_T2R"])))
                row["offset_change_rad"] = round(float(abs(d)), 4)
        rows.append(row)
    R = lambda v: float(np.abs(np.mean(np.exp(1j * np.asarray(v)))) if v else float("nan"))  # noqa: E731
    out = {"what": "DNg100 full cord, seeds 0..15: default vs 100x tighter solver tolerance", "rows": rows,
           "seeds_with_identical_active_mn_sets": same_active, "n_seeds": len(rows),
           "R_T1R_T2R": {"default": R(offs["default"]), "tight": R(offs["tight"])},
           "n_both_rhythmic": {"default": len(offs["default"]), "tight": len(offs["tight"])},
           "median_offset_change_rad": float(np.median([r["offset_change_rad"] for r in rows if "offset_change_rad" in r]))
           if any("offset_change_rad" in r for r in rows) else None}
    d = RESEARCH / "diag_v3"
    d.mkdir(parents=True, exist_ok=True)
    (d / "TOLERANCE_DIAG.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
