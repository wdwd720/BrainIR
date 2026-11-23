"""POST HOC, exploratory (RUN6_PROMPT section 8 asks the paper to say how exam 2's model compares with each of its eight wiring
baselines; only the comparison with the best one was pre-registered and locked). The paired bootstrap of the locked comparison
(`results/run3/primary.json` `vs_best_H-S`: mean over the 27 hemilineages of the model's percentile rank minus the baseline's, 10,000
resamples of hemilineages, seed 20261303) is repeated for every baseline. "Clearly above" = the 95 % interval lies above zero.
Output: `research/ledger/thirdfly_v1/POSTHOC_exam2_pairs.json` (hashed by LOCK_thirdfly_v1).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/exam2_pairs_v1.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from brainir_ledger import RESEARCH  # noqa: E402


def main() -> None:
    P = json.loads((RESEARCH / "results" / "run3" / "primary.json").read_text())
    units = list(P["H-M"]["units"])
    hm = np.array([P["H-M"]["pr"][u] for u in units], float)
    out = {"marking": "POST HOC, exploratory: not pre-registered; the locked comparison is with the best baseline only (vs_best_H-S)",
           "n_units": len(units), "model_mean_pr": float(hm.mean()), "seed": 20261303, "n_boot": 10_000, "baselines": {}}
    for b, d in P["H-S"].items():
        x = np.array([d["pr"][u] for u in units], float)
        diff = hm - x
        rng = np.random.default_rng(20261303)
        idx = rng.integers(0, len(units), size=(10_000, len(units)))
        bm = diff[idx].mean(axis=1)
        lo, hi = float(np.percentile(bm, 2.5)), float(np.percentile(bm, 97.5))
        out["baselines"][b] = {"baseline_mean_pr": float(x.mean()), "difference": float(diff.mean()), "interval": [lo, hi],
                               "clearly_above": bool(lo > 0)}
    out["n_clearly_above"] = sum(v["clearly_above"] for v in out["baselines"].values())
    best = out["baselines"]["H-S-k2-signed"]
    out["check_against_locked_vs_best"] = {"locked": P["vs_best_H-S"], "recomputed": best}
    (RESEARCH / "thirdfly_v1").mkdir(exist_ok=True)
    (RESEARCH / "thirdfly_v1" / "POSTHOC_exam2_pairs.json").write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps({b: (round(v["difference"], 3), [round(x, 3) for x in v["interval"]], v["clearly_above"]) for b, v in out["baselines"].items()}))
    print("clearly above:", out["n_clearly_above"], "| locked vs best:", P["vs_best_H-S"]["diff"], P["vs_best_H-S"]["lo"], P["vs_best_H-S"]["hi"])


if __name__ == "__main__":
    main()
