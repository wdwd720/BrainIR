"""Tuner v2: choose K on DNg100 alone (PREREG v2 P1). PREDICTION SIDE; reads only the calibration campaign `calibk` (the DNg100
pair, K in {1, 2, 3, 5, 10}, seeds 0..15, MANC and MaleCNS front-leg networks); no other neuron, no fly data.

Rule: the smallest K for which the DNg100 pair scores >= 0.5 in at least 12 of 16 seeds (an unusable seed counts as < 0.5) on
BOTH networks. If none: the fallback of P1 (fixed-current start; separate campaign), recorded here as `k_chosen: null`.

    uv run --project ledger --no-sync python ledger/scripts/calibk_choose.py   # -> research/ledger/gates_v2/CALIBK.json
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

KS = (1, 2, 3, 5, 10)
NETS = ("MANC", "MaleCNS")
SEEDS = range(16)
NEED = 12


def main() -> None:
    src = data_dir() / "calibration" / "GHA_calibk" / "results.pkl"
    res = {r["key"]: r for r in read_log(src)}
    table, missing = {}, []
    for net in NETS:
        for k in KS:
            ok, usable = 0, 0
            for s in SEEDS:
                r = res.get(f"calibK|{net}|K{k}|DNg100|s{s}")
                if r is None or "error" in r:
                    missing.append(f"{net}|K{k}|s{s}")
                    continue
                usable += bool(r.get("usable"))
                ok += bool(r.get("usable")) and float(r.get("score") or 0.0) >= 0.5
            table[f"{net}|K{k}"] = {"n_seeds_score_ge_0_5": ok, "n_usable": usable}
    if missing:
        raise SystemExit(f"{len(missing)} calibration results missing or in error: {missing[:5]}")
    chosen = next((k for k in KS if all(table[f"{n}|K{k}"]["n_seeds_score_ge_0_5"] >= NEED for n in NETS)), None)
    out = {"rule": "PREREG v2 P1: smallest K in {1,2,3,5,10} with DNg100 >= 0.5 in >= 12 of 16 seeds on both networks",
           "source": "$DATA/ledger/calibration/GHA_calibk/results.pkl", "source_sha256": hashlib.sha256(src.read_bytes()).hexdigest(),
           "table": table, "k_chosen": chosen, "fallback_needed": chosen is None}
    d = RESEARCH / "gates_v2"
    d.mkdir(parents=True, exist_ok=True)
    (d / "CALIBK.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
