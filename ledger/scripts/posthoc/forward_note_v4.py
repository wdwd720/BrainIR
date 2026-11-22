"""Why the forward ledger has two sources (PREREG v4 E2: "If no fix passes, two sources, and the ledger says why"): generated from the
locked Part C result (`reliability_v2/C.json`, under LOCK_reliability_v2) into forward/SOURCES_NOTE.md, written once.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/forward_note_v4.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))
from brainir_ledger import RESEARCH  # noqa: E402

NAMES = {"1": "dose-sweep scoring", "2": "pooled read-out", "3a": "floor 1", "3b": "floor 3", "4": "symmetrised", "5a": "type-pooled within side",
         "5b": "type-pooled across sides", "6": "input-normalised", "7": "consensus annotations", "8": "all network fixes", "9": "combined"}
CRIT = {"1_control": "1 control", "2_agreement_cross_fly": "2 cross-fly agreement", "2_agreement_left_right": "2 left-right agreement",
        "3_still_informative": "3 still informative", "4_still_about_wiring": "4 still about the wiring"}


def main() -> None:
    c = json.loads((RESEARCH / "reliability_v2" / "C.json").read_text())
    if c.get("robust_model"):
        raise SystemExit("a fix passed: the ledger has three sources; no note")
    lines = ["# Why this ledger has two sources", "",
             "PREREG v4 E2 names three sources: the authors' model, two-step signed counting, and the robust model (the passing Part C fix "
             "with the highest specific reproducibility). No fix passed all four Part C criteria (`reliability_v2/C.json`, locked by "
             "`LOCK_reliability_v2.json`: `passing` is empty, `robust_model` is null), so there is no robust model and the ledger has two "
             "sources. Per fix, on the primary type set:", ""]
    for fix, r in c["primary"].items():
        if fix == "unfixed":
            continue
        name = NAMES.get(fix, fix)
        if "criteria" in r:
            failed = [CRIT[k] + (" (not evaluable: " + r["cross_fly"]["note"] + ")" if k == "2_agreement_cross_fly" and "note" in r.get("cross_fly", {})
                                 else "") for k, v in r["criteria"].items() if not v]
            lines.append(f"- Fix {fix} ({name}): fails " + "; ".join(failed) + ".")
        else:
            lines.append(f"- Fix {fix} ({name}): {r.get('note', 'not evaluated')}.")
    lines += ["", "Criterion 2 needs cross-fly agreement of at least 0.8 of its matched ceiling (and left-right where the fix keeps the sides "
              "distinct); criterion 4 needs specific reproducibility above 0 and at most 2 driver types in the rewired control. Fix 3b was "
              "dropped under the budget rule (PREREG v4 X9; LOG L122) and fix 9 needs a passing procedure-level and network-level fix.", ""]
    out = RESEARCH / "forward" / "SOURCES_NOTE.md"
    with open(out, "x", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print("wrote forward/SOURCES_NOTE.md")


if __name__ == "__main__":
    main()
