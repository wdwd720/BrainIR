"""Stage S pilot on Modal (DNg100 and DNb08 only, allowed before the pre-registration; prompt §7).

    uv run --project ledger --no-sync python ledger/scripts/pilot.py probe          # numerics fingerprint across hosts
    uv run --project ledger --no-sync python ledger/scripts/pilot.py frontleg       # 6 neurons x 4 seeds, single-neuron mode vs B0
    uv run --project ledger --no-sync python ledger/scripts/pilot.py fullcord       # two-sided DNg100 on the full cord, 4 seeds

Results go to <data>/ledger/pilot/<name>/ (append-only logs) and a summary JSON in research/ledger/pilot/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from brainir.compute import Shared  # noqa: E402
from brainir.sim import ModelConfig  # noqa: E402
from brainir.sim.screen import ScreenConfig  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import LedgerModalBackend, run_campaign  # noqa: E402
from brainir_ledger.jobs import probe, run_job  # noqa: E402

OUT = RESEARCH / "pilot"
B0 = N.REPO / "benchmarks" / "dng100_walking_cpg" / "results" / "dn_screen_manc_v1.2.1_nt-paper_r16.json"


def _summary(name: str, d: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(d, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in d.items() if k != "rows"}, indent=1, default=str)[:6000])


def cmd_probe(args) -> None:
    res = {}
    for numerics in (False, True):
        be = LedgerModalBackend(numerics=numerics, cpu=0.25, memory_mb=512, max_containers=60, timeout_s=300, retries=1)
        jobs = [{"key": f"probe{i}"} for i in range(120)]
        out = run_campaign(data_dir() / "pilot" / f"probe_numerics{int(numerics)}_{args.tag}", jobs, be, probe)
        by = {}
        for r in out.values():
            cpu = (r["host"]["cpu"].get("cpu_model") or "?") + (" avx512" if r["host"]["cpu"].get("avx512f") else "")
            by.setdefault(cpu, Counter())[r["numerics_digest"][:12]] += 1
        res[f"numerics_env={numerics}"] = {"by_cpu": {k: dict(v) for k, v in by.items()},
                                          "n_distinct_digests": len({r["numerics_digest"] for r in out.values()}),
                                          "numpy_features_example": next(iter(out.values()))["host"]["numpy_cpu_features_enabled"],
                                          "stats": be.last_stats.to_dict() if be.last_stats else None}
    _summary(f"probe_{args.tag}", res)


def _front_jobs(fl, seeds, tag):
    wt = fl.table
    cands = [i for i in wt.index[wt["type"].isin(["DNg100", "DNb08"])] if wt.loc[i, "predictedNt"] == "acetylcholine"]
    cfg = ModelConfig(t_end=1.0)
    scfg = ScreenConfig()
    jobs = []
    for c in cands:
        for s in seeds:
            jobs.append({"key": f"{tag}|{wt.loc[c, 'type']}|{int(c)}|s{s}", "kind": "group", "W": Shared("W"), "sizes": Shared("sizes"),
                         "readout": Shared("readout"), "members": [int(c)], "seed": int(s), "model": cfg.to_dict(),
                         "screen": scfg.to_dict(), "extras": {"readout_traces": True}})
    return jobs


def cmd_frontleg(args) -> None:
    fl = N.front_leg()
    seeds = list(range(args.seeds))
    shared = {"W": fl.W, "sizes": fl.sizes, "readout": fl.readout}
    b0 = json.loads(B0.read_text(encoding="utf-8"))
    b0rep = {(r["candidate"], r["seed"]): r for r in b0["replicates"]}
    summ = {"rows": []}
    digests = {}
    for run in ("a", "b"):  # two independent campaigns: determinism across containers
        be = LedgerModalBackend(cpu=1.0, memory_mb=3072, max_containers=50, timeout_s=3600)
        jobs = _front_jobs(fl, seeds, f"front_{run}")
        t0 = time.time()
        out = run_campaign(data_dir() / "pilot" / f"frontleg_{run}_{args.tag}", jobs, be, run_job, shared=shared)
        summ[f"campaign_{run}"] = {"wall_s": round(time.time() - t0, 1), "stats": be.last_stats.to_dict() if be.last_stats else None,
                                   "n_errors": sum("error" in r for r in out.values())}
        for k, r in out.items():
            _, typ, c, s = k.split("|")
            digests.setdefault((int(c), int(s[1:])), []).append((r.get("digest"), (r.get("host") or {}).get("cpu", {}).get("cpu_model")))
            if run == "a":
                ref = b0rep.get((int(c), int(s[1:])))
                summ["rows"].append({"type": typ, "candidate": int(c), "seed": int(s[1:]), "usable": r.get("usable"), "score": r.get("score"),
                                     "current": r.get("current"), "n_runs": r.get("n_tuning_runs"), "job_wall_s": r.get("job_wall_s"),
                                     "b0_usable": ref and ref["usable"], "b0_score": ref and ref["score"], "b0_current": ref and ref["current"],
                                     "b0_n_runs": ref and ref["n_tuning_runs"], "error": r.get("error")})
    rows = summ["rows"]
    ok = [r for r in rows if r["b0_score"] is not None and r["score"] is not None]
    summ["g1_preview"] = {
        "n": len(rows), "usable_flag_equal": sum(r["usable"] == r["b0_usable"] for r in rows),
        "current_equal": sum(r["current"] == r["b0_current"] for r in rows),
        "max_abs_score_diff": max((abs(r["score"] - r["b0_score"]) for r in ok), default=None),
        "n_score_exact": sum(r["score"] == r["b0_score"] for r in ok)}
    summ["determinism"] = {"pairs": len(digests), "identical": sum(len({d for d, _ in v}) == 1 for v in digests.values()),
                           "cpus": dict(Counter(c for v in digests.values() for _, c in v))}
    summ["mean_job_wall_s"] = float(np.mean([r["job_wall_s"] for r in rows if r["job_wall_s"]]))
    _summary(f"frontleg_{args.tag}", summ)


def cmd_fullcord(args) -> None:
    fc = N.full_cord()
    ls = N.leg_setup(fc)
    scale = fc.n / 4604
    scfg = ScreenConfig(n_active_upper=int(round(1500 * scale)), n_active_lower=int(round(args.lower * scale)),
                        n_high_fr_upper=int(round(100 * scale)))
    cfg = ModelConfig(t_end=1.0)
    dng = [int(i) for i in fc.table.index[fc.table["type"] == "DNg100"]]
    shared = {"W": fc.W, "sizes": fc.sizes, "readout": fc.readout, "legs": ls}
    jobs = [{"key": f"full|DNg100|s{s}", "kind": "group", "W": Shared("W"), "sizes": Shared("sizes"), "readout": Shared("readout"),
             "members": dng, "seed": s, "model": cfg.to_dict(), "screen": scfg.to_dict(),
             "extras": {"readout_traces": True, "legs": Shared("legs"), "watch": dng}} for s in range(args.seeds)]
    be = LedgerModalBackend(cpu=1.0, memory_mb=6144, max_containers=50, timeout_s=7200)
    t0 = time.time()
    out = run_campaign(data_dir() / "pilot" / f"fullcord_{args.tag}", jobs, be, run_job, shared=shared)
    rows = []
    for k, r in sorted(out.items()):
        if "error" in r:
            rows.append({"key": k, "error": r["error"]})
            continue
        ex = r["extras"]
        rows.append({"key": k, "usable": r["usable"], "score_all": r["score"], "current": r["current"], "n_runs": r["n_tuning_runs"],
                     "n_active_all": r["n_active_all"], "n_high": r["n_high_fr"], "job_wall_s": r["job_wall_s"],
                     "legs": {leg: (round(v["score"], 3), v["n_active"]) for leg, v in (ex.get("legs") or {}).items()}})
    _summary(f"fullcord_{args.tag}", {"screen_cfg": scfg.to_dict(), "wall_s": round(time.time() - t0, 1),
                                      "stats": be.last_stats.to_dict() if be.last_stats else None, "rows": rows})


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["probe", "frontleg", "fullcord"])
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--lower", type=float, default=5.0)
    ap.add_argument("--tag", default="v1")
    args = ap.parse_args()
    {"probe": cmd_probe, "frontleg": cmd_frontleg, "fullcord": cmd_fullcord}[args.cmd](args)


if __name__ == "__main__":
    main()
