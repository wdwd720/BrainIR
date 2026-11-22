"""EXPLORATORY (LOG L122; not pre-registered evidence): what X9's cut of the analysed set (random part 41 -> 25 types) changes.

Block 1 and the unfixed rewired control (`crw-run4`) were run on G9's full analysed set (278 types) before the cut; every pre-registered
Part B/C analysis uses the cut set (262). This script re-computes, on the full set, (1) Block 1's headline numbers for both flies and
(2) the unfixed screen's Part C record (control, agreements, drivers, specific reproducibility, rewired drivers), with the pre-registered
code unchanged (only `gha4.analysed_set` is pointed at the full set), and writes them beside the cut-set values from the locked outputs.
Blocks 2-3, the count-noise models and the fixes ran on the cut set only, so they have no full-set version.

    uv run --project ledger --no-sync python ledger/scripts/posthoc/x9_fullset_v4.py     # -> results/run4/EXPLORATORY_X9_FULLSET.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parents[1] / "src"))
import gha4  # noqa: E402
import reliability_v2_bc as RB  # noqa: E402

from brainir_ledger import RESEARCH  # noqa: E402

OUT = RESEARCH / "results" / "run4" / "EXPLORATORY_X9_FULLSET.json"
REL2 = RESEARCH / "reliability_v2"


def _b1_head(b: dict) -> dict:
    bi, fr = b["tuner_free"]["best_in_bounds"], b["tuner_free"]["fraction_rhythmic_in_bounds"]
    return {"n_types": b["n_types"], "best_in_bounds_ratio": bi["left_vs_right"]["primary"]["ratio"],
            "best_in_bounds_closure": bi["closure_vs_tuned"].get("closure"), "best_in_bounds_closure_interval": bi["closure_vs_tuned"].get("closure_interval"),
            "fraction_rhythmic_closure": fr["closure_vs_tuned"].get("closure"),
            "transplant_closures": {k: v["closure_vs_tuned"].get("closure") for k, v in b["transplant"].items() if isinstance(v, dict)},
            "n_flips": len(b["flips"])}


def _c_head(r: dict) -> dict:
    sr = r.get("specific_reproducibility") or {}
    return {"n_types": r.get("n_types"), "cross_fly_ratio": (r.get("cross_fly") or {}).get("ratio"),
            "left_right_ratio": (r.get("left_right") or {}).get("ratio"), "drivers_mean": (r.get("drivers") or {}).get("mean"),
            "SR": sr.get("SR"), "SR_ci95": sr.get("ci95"), "rewired_drivers": (r.get("rewired_drivers") or {}).get("n")}


def main() -> None:
    cut = gha4.analysed_set()
    full = json.loads((REL2 / "ANALYSED_SET.json").read_text())
    if cut.get("n_analysed") == full.get("n_analysed"):
        raise SystemExit("no X9 cut in force: nothing to compare")
    out = {"marking": "EXPLORATORY (LOG L122): the X9 cut's effect; not pre-registered evidence",
           "full_set": {"n_analysed": full["n_analysed"]}, "cut_set": {"n_analysed": cut["n_analysed"]}, "block1": {}, "part_c_unfixed": {}}
    official = {fly: json.loads((REL2 / f"B1_{fly}.json").read_text()) for fly in ("MANC", "MaleCNS")}
    c_off = json.loads((REL2 / "C_FIXES_1_TO_8.json").read_text()) if (REL2 / "C_FIXES_1_TO_8.json").is_file() else None
    gha4.analysed_set = lambda: full  # the only change: the full G9 set
    for fly in ("MANC", "MaleCNS"):
        res = RB._both_sets(fly, lambda ts, f=fly: RB._b1(f, ts))
        out["block1"][fly] = {lab: {"full_set": _b1_head(res[lab]), "cut_set_locked": _b1_head(official[fly][lab])} for lab in res}
    gains = json.loads((gha4.GATES4 / "C_GAINS.json").read_text())["fixes"]
    for lab, primary in (("primary", True), ("secondary_all_analysed_types", False)):
        rec = RB._evaluate_fix("0", None, gains, primary)
        out["part_c_unfixed"][lab] = {"full_set": _c_head(rec), "cut_set_locked": _c_head(c_off[lab]["unfixed"]) if c_off else None}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(RB.R2._clean(out), indent=1) + "\n")
    print("wrote", OUT.relative_to(RESEARCH))


if __name__ == "__main__":
    main()
