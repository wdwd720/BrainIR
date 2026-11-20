"""DNg100-only calibration and gate G3 runs on the full nerve cord (allowed at any time, prompt §7).

    uv run --project ledger --no-sync python ledger/scripts/calibrate_dng100.py sweep      # bilateral DNg100, fixed currents, T = 1 s
    uv run --project ledger --no-sync python ledger/scripts/calibrate_dng100.py g3 --n 64  # authors' configuration: 380 each, T = 2 s
    uv run --project ledger --no-sync python ledger/scripts/calibrate_dng100.py front      # DNg100 type group, front-leg tuner, bounds 5/10

The authors' full-cord configuration (Zenodo 10.5281/zenodo.22260924, DNg100_Stim_fullManc, run_config.yaml of runs 30662613,
33195857, 33195876, 33195882): stimNeurons [[59, 282]] (the two DNg100), stimI 380, T 2.0, pulse 0.02-1.999, no stimulus
adjustment, 32 replicates per run. Per-leg reference scores: figures/.../scores_allLegs.csv in their GitHub repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir.compute import Shared  # noqa: E402
from brainir.sim import ModelConfig  # noqa: E402
from brainir.sim.screen import ScreenConfig  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import LedgerModalBackend, run_campaign  # noqa: E402
from brainir_ledger.jobs import run_job  # noqa: E402

OUT = RESEARCH / "calibration"


def _full_jobs(currents, seeds, t_end, tag):
    fc = N.full_cord()
    ls = N.leg_setup(fc)
    dng = [int(i) for i in fc.table.index[fc.table["type"] == "DNg100"]]
    cfg = ModelConfig(t_end=t_end)
    scale = fc.n / 4604
    scfg = ScreenConfig(n_active_upper=int(round(1500 * scale)), n_active_lower=int(round(5 * scale)), n_high_fr_upper=int(round(100 * scale)))
    shared = {"W": fc.W, "sizes": fc.sizes, "readout": fc.readout, "legs": ls}
    jobs = [{"key": f"{tag}|I{c:g}|s{s}", "kind": "fixed", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
             "stim_indices": dng, "currents": [float(c)] * len(dng), "seed": int(s), "model": cfg.to_dict(), "screen": scfg.to_dict(),
             "extras": {"legs": Shared("legs"), "readout_traces": True, "watch": dng}} for c in currents for s in seeds]
    return jobs, shared


def _rows(out):
    rows = []
    for k, r in sorted(out.items()):
        if "error" in r:
            rows.append({"key": k, "error": r["error"][:300]})
            continue
        ex = r["extras"]
        rows.append({"key": k, "verdict": r["verdict"], "n_active_all": r["n_active_all"], "n_high": r["n_high_fr"], "score_all": r["score"],
                     "n_active_mn": r["n_active_readout"], "freq": r["frequency_hz"], "wall": r["wall_time_s"],
                     "legs": {leg: (round(v["score"], 3), v["n_active"]) for leg, v in ex["legs"].items()},
                     "offsets_v1": ex["offsets_v1"], "e1_peak_hz": ex["e1_peak_hz"]})
    return rows


def cmd_sweep(args) -> None:
    currents = [194.56, 256, 320, 380, 450, 512, 640]
    jobs, shared = _full_jobs(currents, range(args.n), 1.0, "sweep")
    be = LedgerModalBackend(cpu=1.0, memory_mb=6144, max_containers=100, timeout_s=3600)
    out = run_campaign(data_dir() / "calibration" / f"full_sweep_{args.tag}", jobs, be, run_job, shared=shared)
    rows = _rows(out)
    summ = {}
    for c in currents:
        rs = [r for r in rows if r["key"].startswith(f"sweep|I{c:g}|") and "error" not in r]
        summ[f"{c:g}"] = {"n": len(rs), "median_active_all": float(np.median([r["n_active_all"] for r in rs])),
                          "median_active_mn": float(np.median([r["n_active_mn"] for r in rs])),
                          "verdicts": {v: sum(r["verdict"] == v for r in rs) for v in ("ok", "weak", "strong")},
                          "median_leg_score": {leg: float(np.median([r["legs"][leg][0] for r in rs])) for leg in rs[0]["legs"]} if rs else None,
                          "median_leg_active": {leg: float(np.median([r["legs"][leg][1] for r in rs])) for leg in rs[0]["legs"]} if rs else None}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"full_sweep_{args.tag}.json").write_text(json.dumps({"summary": summ, "rows": rows, "stats": be.last_stats.to_dict() if be.last_stats else None},
                                                                indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summ, indent=1))


def cmd_g3(args) -> None:
    jobs, shared = _full_jobs([380.0], range(args.n), 2.0, "g3")
    be = LedgerModalBackend(cpu=1.0, memory_mb=8192, max_containers=100, timeout_s=7200)
    out = run_campaign(data_dir() / "calibration" / f"g3_{args.tag}", jobs, be, run_job, shared=shared)
    rows = _rows(out)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"g3_runs_{args.tag}.json").write_text(json.dumps({"rows": rows, "stats": be.last_stats.to_dict() if be.last_stats else None},
                                                             indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    ok = [r for r in rows if "error" not in r]
    print("n", len(ok), "errors", len(rows) - len(ok))
    for leg in ("T1L", "T1R", "T2L", "T2R", "T3L", "T3R"):
        print(leg, "median score", round(float(np.median([r["legs"][leg][0] for r in ok])), 3),
              "median active MNs", float(np.median([r["legs"][leg][1] for r in ok])))


def cmd_front(args) -> None:
    fl = N.front_leg()
    dng = [int(i) for i in fl.table.index[fl.table["type"] == "DNg100"]]
    cfg = ModelConfig(t_end=1.0)
    shared = {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout}
    jobs = []
    for lower in (5, 10):
        scfg = ScreenConfig(n_active_lower=lower)
        jobs += [{"key": f"front|lo{lower}|s{s}", "kind": "group", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
                  "members": dng, "seed": s, "model": cfg.to_dict(), "screen": scfg.to_dict(), "extras": {"readout_traces": True}}
                 for s in range(16)]
    be = LedgerModalBackend(cpu=1.0, memory_mb=3072, max_containers=32, timeout_s=3600)
    out = run_campaign(data_dir() / "calibration" / f"front_dng100_{args.tag}", jobs, be, run_job, shared=shared)
    rows = [{"key": k, "usable": r.get("usable"), "score": r.get("score"), "current": r.get("current"), "n_runs": r.get("n_tuning_runs"),
             "n_active_all": r.get("n_active_all"), "n_active_notebook": (r.get("extras") or {}).get("n_active_notebook")} for k, r in sorted(out.items())]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"front_dng100_{args.tag}.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    for r in rows:
        print(r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sweep", "g3", "front"])
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--tag", default="v1")
    args = ap.parse_args()
    {"sweep": cmd_sweep, "g3": cmd_g3, "front": cmd_front}[args.cmd](args)


if __name__ == "__main__":
    main()
