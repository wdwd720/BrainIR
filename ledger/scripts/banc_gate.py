"""Evaluate the BANC build gate (`gates_v6/BANC_GATE_SPEC.md`, written before the gate ran) -> `gates_v6/BANC_GATE.json` (written once).

    uv run --project ledger --no-sync python ledger/scripts/banc_gate.py bg-banc-run6
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import gha6 as G6  # noqa: E402

from brainir_ledger import banc as B  # noqa: E402

AUTHORS = {"intact": {"mean": 0.984, "frac_ge_0_5": 0.993, "median_active_mn": 6, "range_active_mn": [1, 13]},
           "E1": {"mean": 0.014}, "E2": {"mean": 0.035}, "I2": {"mean": 0.993}}


def evaluate(name: str) -> dict:
    res = G6.results(name)
    left, right = B.readout_side("L"), B.readout_side("R")
    out = {}
    for cond in ("intact", "E1", "E2", "I2"):
        rs = [res[k] for k in sorted(res) if k.startswith(f"BG|{cond}|")]
        sc = np.array([r["score"] if (r.get("solver_success") and r.get("score") is not None) else 0.0 for r in rs], float)
        act = np.array([r["n_active_readout"] for r in rs], int)
        pos = [r["extras"]["active_readout_positions"] for r in rs]
        nl = np.array([int(left[p].sum()) for p in pos]) if pos else np.array([])
        nr = np.array([int(right[p].sum()) for p in pos]) if pos else np.array([])
        out[cond] = {"n": len(rs), "n_solver_failed": int(sum(not r.get("solver_success") for r in rs)), "mean": float(sc.mean()),
                     "median": float(np.median(sc)), "frac_ge_0_5": float((sc >= 0.5).mean()),
                     "active_mn_median": float(np.median(act)), "active_mn_range": [int(act.min()), int(act.max())],
                     "active_mn_left_median": float(np.median(nl)), "active_mn_right_median": float(np.median(nr)),
                     "median_frequency_hz": float(np.nanmedian([r["frequency_hz"] if r["frequency_hz"] is not None else np.nan for r in rs])),
                     "wall_s_mean": float(np.mean([r["wall_time_s"] for r in rs])), "wall_s_max": float(np.max([r["wall_time_s"] for r in rs])),
                     "authors": AUTHORS[cond]}
    c1 = out["intact"]["mean"] >= 0.90 and out["intact"]["frac_ge_0_5"] >= 0.90
    c2 = out["E1"]["mean"] <= 0.10 and out["E1"]["frac_ge_0_5"] <= 0.10
    c3 = out["E2"]["mean"] <= 0.10 and out["E2"]["frac_ge_0_5"] <= 0.10
    gate = {"campaign": name, "spec": "research/ledger/gates_v6/BANC_GATE_SPEC.md", "conditions": out,
            "criteria": {"1_dng100_drives_rhythm": bool(c1), "2_E1_silencing_abolishes": bool(c2), "3_E2_silencing_abolishes": bool(c3)},
            "verdict": "pass" if (c1 and c2 and c3) else "fail"}
    G6._write_once(G6.GATES6 / "BANC_GATE.json", gate)
    return gate


if __name__ == "__main__":
    import json

    g = evaluate(sys.argv[1])
    print(json.dumps({"verdict": g["verdict"], "criteria": g["criteria"],
                      "conditions": {c: {k: v for k, v in d.items() if k != "authors"} for c, d in g["conditions"].items()}}, indent=1))
