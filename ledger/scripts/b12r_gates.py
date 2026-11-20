"""Tuner v2 arms B1r / B2r (PREREG v2 P1): tables and gates from the GitHub campaigns. PREDICTION SIDE (no fly data).

    uv run --project ledger --no-sync python ledger/scripts/b12r_gates.py regress    # K = 0 vs B1's locked digests -> gates_v2/REGRESSION_v2.json
    uv run --project ledger --no-sync python ledger/scripts/b12r_gates.py tables     # -> research/ledger/predictions_v2/B1r, B2r
    uv run --project ledger --no-sync python ledger/scripts/b12r_gates.py controls   # positive control + DNb08 -> gates_v2/B12R_CONTROLS.json

The tables use run 1's frozen table builder (`arms.aggregate_group_arm`, `arms.write_arm`) unchanged, writing to
`predictions_v2/` instead of `predictions/`.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir.sim.model import ModelConfig  # noqa: E402

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import arms as AR  # noqa: E402
from brainir_ledger import networks as N  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

G = RESEARCH / "gates_v2"
PLATFORM = "GitHub Actions hosted runners (ubuntu-24.04, Linux x64), run 1's Python/library pins and numerics environment"


def _log(name: str) -> tuple[dict, Path]:
    p = data_dir() / "arms" / f"GHA_{name}" / "results.pkl"
    return {r["key"]: r for r in read_log(p)}, p


def regress() -> None:
    """P1 tuner regression: K = 0 on 30 random types (seed 20261204) x 16 seeds reproduces B1's locked digests."""
    res, p = _log("regress")
    reps = pd.read_parquet(RESEARCH / "predictions" / "B1" / "replicates.parquet")
    locked = {f"B1-lo10|{t}|s{int(s)}": d for t, s, d in zip(reps["manc_type"], reps["seed"], reps["digest"])}
    rows = {"n_results": len(res), "errors": sorted(k for k, r in res.items() if "error" in r), "identical": 0, "different": [],
            "not_in_B1": []}
    for k, r in sorted(res.items()):
        if "error" in r:
            continue
        if k not in locked:
            rows["not_in_B1"].append(k)
        elif r["digest"] == locked[k]:
            rows["identical"] += 1
        else:
            rows["different"].append(k)
    rows["n_types"] = len({k.split("|")[1] for k in res})
    rows["pass"] = rows["n_results"] == 480 and rows["identical"] == 480
    rows.update({"rule": "PREREG v2 P1: K = 0 reproduces B1's digests on 30 random types (seed 20261204) x 16 seeds",
                 "source_sha256": hashlib.sha256(p.read_bytes()).hexdigest()})
    G.mkdir(parents=True, exist_ok=True)
    (G / "REGRESSION_v2.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in rows.items()}))


def _arms():
    fl = N.front_leg()
    g1 = N.type_groups(fl.table)
    net2, g2, _info = AR.malecns_network()
    return (("B1r", fl, g1, "b1r"), ("B2r", net2, g2, "b2r"))


def tables() -> None:
    k = json.loads((G / "CALIBK.json").read_text())["k_chosen"]
    if k is None:
        raise SystemExit("no K was chosen (P1 fallback needed)")
    scfg, mcfg = AR.b1_screen_cfg(10), ModelConfig(t_end=1.0)
    AR.PREDICTIONS = RESEARCH / "predictions_v2"  # the frozen writer, pointed at the v2 folder
    for arm, net, groups, camp in _arms():
        res, p = _log(camp)
        types, reps = AR.aggregate_group_arm(arm, net.name, net, groups, res, scfg)
        AR.write_arm(arm, types, reps, {"model": mcfg.to_dict(), "screen": scfg.to_dict(), "seeds": AR.SEEDS, "k_min": int(k),
                                        "tuner": "tuner v2 (PREREG v2 P1): B1's procedure plus >= K active front-leg MNs in the accepted run",
                                        "groups": "B1's groups" if arm == "B1r" else "B2's groups and mapping"},
                     {"results_log_sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "platform": PLATFORM, "network_meta": net.meta,
                      "calibration": "gates_v2/CALIBK.json (DNg100 only)"})
        print(arm, len(types), "types; usable", int((types["status"] == "ok").sum()), "; drivers", int((types["band"] == "driver").sum()))


def controls() -> None:
    """P1: positive control DNg100 >= 0.5 in >= 12 of 16 seeds in B1r and B2r (tautological by construction, reported) and
    DNb08 reported as the non-tautological check (not a gate, never tuned on)."""
    out = {}
    for arm in ("B1r", "B2r"):
        t = pd.read_csv(RESEARCH / "predictions_v2" / arm / "types.csv").set_index("manc_type")
        reps = pd.read_parquet(RESEARCH / "predictions_v2" / arm / "replicates.parquet")
        row = {}
        for typ in ("DNg100", "DNb08"):
            r = reps[reps["manc_type"] == typ]
            row[typ] = {"n_seeds": int(len(r)), "n_seeds_score_ge_0_5": int((r["usable"] & (r["score"] >= 0.5)).sum()),
                        "band": None if typ not in t.index else t.loc[typ, "band"],
                        "primary_score": None if typ not in t.index else float(t.loc[typ, "primary_score"])}
        row["positive_control_pass"] = row["DNg100"]["n_seeds_score_ge_0_5"] >= 12
        out[arm] = row
    out["pass"] = all(out[a]["positive_control_pass"] for a in ("B1r", "B2r"))
    out["note"] = "DNg100 is the calibration neuron (tautological); DNb08 is reported, not a gate, and was never tuned on."
    (G / "B12R_CONTROLS.json").write_text(json.dumps(out, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    {"regress": regress, "tables": tables, "controls": controls}[sys.argv[1]]()
