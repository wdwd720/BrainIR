"""EXPLORATORY re-scores after the exam 2 unblinding (RUN3_PROMPT hard limit 7: "Extra analyses go in a section marked
exploratory"). Uses the frozen scoring functions (`scoring_h1.identification`, `permutation_null`, `bootstrap_ci`) on files locked
before the flag:
  - S-sens: the label-review sensitivity consensus (`labels_h1/consensus_sensitivity.csv`: questioned and de-duplication-affected
    cells removed), H-M predictions;
  - per-dimension view: the mean percentile rank when each primary dimension is left out in turn (H-M, primary consensus).
Refuses unless results/run3/primary.json exists (the frozen primary run happened). Writes results/run3/exploratory.json once.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/rescore_sensitivity.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger.scoring_h1 import DIMS, bootstrap_ci, identification, observed, permutation_null, standardise  # noqa: E402

OUT = RESEARCH / "results" / "run3"


def main() -> None:
    if not (OUT / "primary.json").is_file():
        raise SystemExit("primary.json missing: nothing is unblinded; refused")
    units = pd.read_csv(RESEARCH / "hl_units" / "UNITS_v1.csv", dtype={"unit": str})["unit"].tolist()
    P = pd.read_csv(RESEARCH / "predictions_h1" / "H-M" / "predicted.csv", dtype={"unit": str}).set_index("unit").loc[units]
    Z = standardise(P)
    res = {"marking": "EXPLORATORY (after unblinding; not pre-registered)"}
    for name, rel in (("primary_consensus", "consensus.csv"), ("sensitivity_consensus", "consensus_sensitivity.csv")):
        c = pd.read_csv(RESEARCH / "labels_h1" / rel, dtype=str, keep_default_na=False).set_index("unit").reindex(units)
        O = observed(c)
        r = identification(Z, O)
        if r["n"]:
            nl = permutation_null(r)
            ci = bootstrap_ci(r["pr"].values())
            res[name] = {"n": r["n"], "mean_pr": r["mean_pr"], "top1": r["top1"], "top3": r["top3"], "p": nl["p"],
                         "null_mean_pr": nl["null_mean_pr"], "ci": ci}
        if name == "primary_consensus":
            loo = {}
            for d in DIMS:
                O2 = O.copy()
                O2[d] = float("nan")
                r2 = identification(Z, O2)
                loo[d] = {"n": r2["n"], "mean_pr": r2["mean_pr"]}
            res["leave_one_dimension_out"] = loo
    with open(OUT / "exploratory.json", "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(res, indent=1, default=str) + "\n")
    print(json.dumps({k: (v if not isinstance(v, dict) else {kk: vv for kk, vv in v.items() if kk in ("n", "mean_pr", "p")})
                      for k, v in res.items() if k != "leave_one_dimension_out"}, default=str))


if __name__ == "__main__":
    main()
