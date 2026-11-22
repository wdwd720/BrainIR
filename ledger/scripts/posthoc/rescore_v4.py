"""EXPLORATORY, after unblinding (PREREG v4 Part D; RUN4_PROMPT hard limit 3): exam 1 re-scored once per fix with run 2's frozen
statistics, and exam 2 once for the robust model if it was run. Writes results/run4/EXAM1_<fix>.json and EXAM2_<fix>.json, each once
(mode "x"); never creates an unblinding flag; reads labels only through the frozen helpers and the locked tables.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/rescore_v4.py exam1 FIX     # FIX in 1 2 3a 3b 4 5a 5b 6 7 8 9
    uv run --project ledger --no-sync python ledger/scripts/posthoc/rescore_v4.py exam2 FIX
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "src"))
import forward_v1 as FW  # noqa: E402  (run 2's primary set, the robust-model loader)
import gha4  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.scoring import stats as ST  # noqa: E402

OUT = RESEARCH / "results" / "run4"
HEAD = "EXPLORATORY, after unblinding (PREREG v4 Part D): not pre-registered evidence; each variant scored once."


def _write(name: str, obj: dict) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(obj, indent=1, default=float) + "\n")
    print("wrote results/run4/" + name)


def _b1r_seeds_0_7() -> pd.Series:
    from brainir_ledger import agree as AG  # noqa: PLC0415

    rep = pd.read_parquet(RESEARCH / "predictions_v2" / "B1r" / "replicates.parquet").rename(columns={"manc_type": "type"})
    rep = rep[["type", "seed", "usable", "score"]]
    return AG.type_scores(rep, list(range(8)), sorted(rep["type"].unique()))


def exam1(fix: str) -> None:
    gha4.require_freeze("Part D exam 1")
    y = FW.primary_set()
    model = FW.robust_scores(fix)
    unfixed = _b1r_seeds_0_7()
    s2 = FW.s2_scores()
    types = [t for t in y.index if t in model.index]
    yy = y[types].to_numpy()
    res = {"marking": HEAD, "fix": fix, "primary_set": "run 2's P (labels v2, clear front-leg label, among A1's 321, not exposed)",
           "n_types": len(types), "n_yes": int(yy.sum()),
           "fixed_model": ST.bootstrap_auroc(model[types].to_numpy(), yy),
           "unfixed_B1r_seeds_0_7": ST.bootstrap_auroc(unfixed[types].to_numpy(), yy),
           "two_step_signed_S2": ST.bootstrap_auroc(s2[types].to_numpy(), yy),
           "fixed_minus_unfixed": ST.paired_bootstrap_diff(model[types].to_numpy(), unfixed[types].to_numpy(), yy),
           "fixed_minus_S2": ST.paired_bootstrap_diff(model[types].to_numpy(), s2[types].to_numpy(), yy)}
    _write(f"EXAM1_{fix}.json", res)


def exam2(fix: str) -> None:
    gha4.require_freeze("Part D exam 2")
    raise SystemExit("exam 2 re-scoring runs only for the robust model and only if 60 runner-hours remain after Part C (PREREG v4 "
                     "Part D); the full-cord campaign and this command are written if and when that condition holds")


def main() -> None:
    cmd, a = sys.argv[1:2], sys.argv[2:]
    if cmd == ["exam1"]:
        exam1(a[0])
    elif cmd == ["exam2"]:
        exam2(a[0])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
