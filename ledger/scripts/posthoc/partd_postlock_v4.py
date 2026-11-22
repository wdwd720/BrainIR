"""Post-lock Part D (LOG L145): exam 1 re-scores of the fixes whose whole-type screens ran after LOCK_reliability_v2, with the frozen
`rescore_v4.exam1` (unchanged), output redirected to results/run4_postlock/. EXPLORATORY, after unblinding; each variant scored once
(the output is written once). Refuses unless the fix's whole-type screen is complete (GitHub and Modal merged by key).

    uv run --project ledger --no-sync python ledger/scripts/posthoc/partd_postlock_v4.py FIX [FIX ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import gha4  # noqa: E402
import rescore_v4 as RS  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402

RS.OUT = RESEARCH / "results" / "run4_postlock"

if __name__ == "__main__":
    for fix in sys.argv[1:]:
        name = f"dx-{fix}-run4"
        man = json.loads((gha4.G.GHA / name / "manifest.json").read_text())
        have = {r["key"] for r in gha4.load_results(name)}
        missing = len(set(man["keys"]) - have)
        if missing:
            raise SystemExit(f"{name}: {missing} of {man['n_jobs']} results missing; not scored")
        RS.exam1(fix)
