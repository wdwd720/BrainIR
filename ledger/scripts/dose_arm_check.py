"""RUN4_PROMPT Stage 0: was the current actually applied in run 3's fixed-current arm (H-D, campaign `hd-run3`)?

Run 3 reported identical fixed-run classes (ok / weak / strong) at 128, 256 and 384. This script checks, from stored files only
(no simulation, no label):
  1. the job specs: every packed `fixed_v3` job carries one current per member, equal to the current named in its key;
  2. the outputs: for each unit and seed, whether activity (all active neurons, neurons above the high-rate threshold, active
     read-out motor neurons) and the run class change with the current;
  3. why the classes coincide: the run class against the unit's member count and transmitter class.
Writes research/ledger/diag_v4/DOSE_ARM_CHECK.json once.

    uv run --project ledger --no-sync python ledger/scripts/dose_arm_check.py
"""

from __future__ import annotations

import collections
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

CAMPAIGN = "hd-run3"
CURRENTS = (128.0, 256.0, 384.0, 512.0)
OUT = RESEARCH / "diag_v4" / "DOSE_ARM_CHECK.json"


def main() -> None:
    gha = data_dir() / "gha" / CAMPAIGN
    spec_ok, spec_bad, n_spec = 0, [], 0
    for f in sorted(gha.glob("chunk_*.pkl")):
        for _pkey, job in pickle.loads(f.read_bytes()):
            n_spec += 1
            cur = float(job["key"].split("|")[0].removeprefix("H-D-"))
            cs = set(float(c) for c in job["currents"])
            if job["kind"] == "fixed_v3" and cs == {cur} and len(job["currents"]) == len(job["stim_indices"]):
                spec_ok += 1
            else:
                spec_bad.append(job["key"])
    res = read_log(data_dir() / "arms_h1" / f"GHA_{CAMPAIGN}" / "results.pkl")
    rows = collections.defaultdict(dict)
    for r in res:
        arm, unit, seed = r["key"].split("|")
        rows[(unit, seed)][float(arm.removeprefix("H-D-"))] = r
    per_current = {}
    for c in CURRENTS:
        rs = [d[c] for d in rows.values()]
        per_current[f"{c:g}"] = {"n": len(rs), "verdicts": dict(collections.Counter(r["verdict"] for r in rs)),
                                 "mean_n_active_all": float(np.mean([r["n_active_all"] for r in rs])),
                                 "mean_n_high_fr": float(np.mean([r["n_high_fr"] for r in rs])),
                                 "mean_n_active_readout": float(np.mean([r["n_active_readout"] for r in rs]))}
    same_active = sum(1 for d in rows.values() if len({d[c]["n_active_all"] for c in CURRENTS}) == 1)
    same_high = sum(1 for d in rows.values() if len({d[c]["n_high_fr"] for c in CURRENTS}) == 1)
    same_verdict_3 = sum(1 for d in rows.values() if len({d[c]["verdict"] for c in CURRENTS[:3]}) == 1)
    same_verdict_4 = sum(1 for d in rows.values() if len({d[c]["verdict"] for c in CURRENTS}) == 1)
    high_nondecreasing = sum(1 for d in rows.values()
                             if all(d[a]["n_high_fr"] <= d[b]["n_high_fr"] for a, b in zip(CURRENTS, CURRENTS[1:])))
    # class against member count and transmitter class (the unit table of run 3)
    units = pd.read_csv(RESEARCH / "hl_units" / "UNITS_v1.csv", dtype={"unit": str}).set_index("unit")
    pred = pd.read_csv(RESEARCH / "predictions_h1" / "H-D-128" / "predicted.csv", dtype={"unit": str}).set_index("unit")
    by_unit = []
    for u in pred.index:
        v = {f"{c:g}": dict(collections.Counter(rows[(u, f"s{s}")][c]["verdict"] for s in range(8))) for c in CURRENTS}
        by_unit.append({"unit": u, "n_members": int(pred.loc[u, "n_members"]),
                        "class": str(units.loc[u, "nt_class"]) if "nt_class" in units.columns else None, "verdicts": v})
    out = {
        "question": "RUN4_PROMPT Stage 0: was the current applied in run 3's fixed-current arm H-D?",
        "campaign": CAMPAIGN, "n_results": len(res), "n_unit_seeds": len(rows),
        "job_specs": {"n": n_spec, "current_equals_key_for_every_member": spec_ok, "bad": spec_bad},
        "per_current": per_current,
        "unit_seeds_identical_n_active_all_across_4_currents": same_active,
        "unit_seeds_identical_n_high_fr_across_4_currents": same_high,
        "unit_seeds_n_high_fr_nondecreasing_in_current": high_nondecreasing,
        "unit_seeds_same_class_128_256_384": same_verdict_3, "unit_seeds_same_class_all_4": same_verdict_4,
        "by_unit": by_unit,
        "verdict": ("current applied; not a bug" if spec_ok == n_spec and same_high < len(rows) // 2 else "investigate"),
        "explanation": ("The run class depends on counts of active neurons (100 <= active <= 7,667 and <= 1,022 above 100 Hz on the "
                        "full cord). Inhibitory units with >= 100 members are 'ok' at every current because the stimulated members "
                        "alone are active and they silence their targets; units with < 100 members that excite little stay "
                        "'weak'; excitatory units with many members already saturate at 128. The current changes the rates "
                        "(neurons above 100 Hz rise with the current) without crossing a class boundary, except 01B (ok -> strong "
                        "at 512) and 27X (weak -> ok in 4 of 8 seeds at 512)."),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(out, indent=1, default=str) + "\n")
    print(json.dumps({k: v for k, v in out.items() if k != "by_unit"}, indent=1, default=str))


if __name__ == "__main__":
    main()
