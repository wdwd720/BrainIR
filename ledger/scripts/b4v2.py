"""B4 v2 calls (PREREG v2 P3): recomputed from the stored, locked B4 replicates (`data/ledger/arms/B4/results.pkl`, whose
digests are the ones of predictions v1); NO new simulation. PREDICTION SIDE.

For type t at strength s: R = seeds whose background-only run scores >= 0.5 (< 8 -> background_not_rhythmic); L = seeds in R
where t's run scores < 0.5. If |L| >= 0.75 |R|: in bounds = the run's screen verdict is not
`strong` (B4's configuration: <= 1,500 active, <= 100 high-firing); fall = (background active MNs - t's active MNs) /
max(background active MNs, 1) per seed; `halts` if every run in L is in bounds and the median fall over L is >= 0.25;
`saturates` if more than half of L is out of bounds; otherwise `rhythm_lost_other`. If |L| < 0.75 |R|: as v1 (speeds_up / slows_down / no_effect / no_effect_low_n).

    uv run --project ledger --no-sync python ledger/scripts/b4v2.py   # -> research/ledger/predictions_v2/B4v2/
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "src"))
from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import arms as AR  # noqa: E402
from brainir_ledger.backend import read_log  # noqa: E402

OUT = RESEARCH / "predictions_v2" / "B4v2"


def call_v2(bg: list[dict], tr: list[dict]) -> tuple[str, dict]:
    R = [i for i, b in enumerate(bg) if b["score"] >= 0.5]
    info = {"n_base_rhythmic": len(R)}
    if len(R) < AR.B4_MIN_BASE_RHYTHMIC:
        return "background_not_rhythmic", info
    L = [i for i in R if tr[i]["score"] < 0.5]
    info["n_lost"] = len(L)
    if len(L) >= 0.75 * len(R):
        inb = [i for i in L if tr[i]["verdict"] != "strong"]  # in bounds = screen verdict not "strong" (PREREG v2 P3)
        fall = [(bg[i]["n_active_readout"] - tr[i]["n_active_readout"]) / max(bg[i]["n_active_readout"], 1) for i in L]
        info.update({"frac_lost_in_bounds": len(inb) / len(L), "median_mn_fall": float(np.median(fall))})
        if len(inb) == len(L) and np.median(fall) >= 0.25:
            return "halts", info
        if len(L) - len(inb) > 0.5 * len(L):
            return "saturates", info
        return "rhythm_lost_other", info
    call, v1info = AR.b4_call(bg, tr)
    info.update({k: v for k, v in v1info.items() if k not in info})
    return call, info


def main() -> None:
    log = data_dir() / "arms" / "B4" / "results.pkl"
    res = {r["key"]: r for r in read_log(log) if "error" not in r}
    types = pd.read_csv(RESEARCH / "predictions" / "B4" / "types.csv")
    reps_v1 = pd.read_parquet(RESEARCH / "predictions" / "B4" / "replicates.parquet")
    # the stored results must be exactly the locked ones
    dig = {f"B4|{t}|I{c:g}|s{s}" if t != "__background__" else f"B4|__background__|I0|s{s}": d
           for t, c, s, d in zip(reps_v1["manc_type"], reps_v1["current"], reps_v1["seed"], reps_v1["digest"])}
    bad = [k for k, d in dig.items() if res[k]["digest"] != d]
    if bad:
        raise SystemExit(f"{len(bad)} stored results differ from the locked digests")
    bg = [res[f"B4|__background__|I0|s{s}"] for s in AR.SEEDS]
    rows = []
    for t in types["manc_type"]:
        row = {"manc_type": t}
        for c in AR.B4_STRENGTHS:
            tr = [res[f"B4|{t}|I{c:g}|s{s}"] for s in AR.SEEDS]
            call, info = call_v2(bg, tr)
            row[f"call_{c:g}"] = call
            for k, v in info.items():
                row[f"{k}_{c:g}"] = v
        rows.append(row)
    df = pd.DataFrame(rows)
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT / "types.csv", index=False, lineterminator="\n")
    cross = {"128_vs_512": pd.crosstab(df["call_128"], df["call_512"]).to_dict(), "32_vs_128": pd.crosstab(df["call_32"], df["call_128"]).to_dict()}
    counts = {f"call_{c:g}": df[f"call_{c:g}"].value_counts().to_dict() for c in AR.B4_STRENGTHS}
    prov = {"source_log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(), "n_types": len(df), "digests_checked": len(dig),
            "rule": "PREREG v2 P3", "counts": counts, "crosstabs": cross}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=1, default=str) + "\n")
    print(json.dumps({"counts": counts}, indent=1, default=str))


if __name__ == "__main__":
    main()
