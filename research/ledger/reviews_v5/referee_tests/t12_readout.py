"""Referee test 12: is the left-right or cross-fly gap a product of the read-out?

The ledger's half-fly screens read out only the stimulated side's front-leg motor neurons (its design, PREREG v4 G1); the authors'
single-neuron screen reads out both front legs; the two flies' read-out sets differ (PREREG v4 G2: 144 MANC, 130 MaleCNS motor
neurons). Prints, from locked files: the authors' both-legs left-right ratio (reliability_v2/A0.json), the ledger's one-sided
same-side ratios and cross-fly ratios (reliability_v2/A.json), the whole-type cross-fly ratio (both sides' members, all front-leg
motor neurons; A.json reference_R1), and Part C fix 2, the pooled (summed) read-out, against the unfixed screen
(reliability_v2/C.json, primary; one-sided Part C design, seeds 0..7).
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t12_readout.py
"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")


def find_ratio(x):
    """first 'ratio' under a 'primary' key, depth-first"""
    if isinstance(x, dict):
        if "primary" in x and isinstance(x["primary"], dict) and "ratio" in x["primary"]:
            return x["primary"]["ratio"]
        for v in x.values():
            r = find_ratio(v)
            if r is not None:
                return r
    return None


def main():
    a0 = json.loads((ROOT / "reliability_v2/A0.json").read_text())
    a = json.loads((ROOT / "reliability_v2/A.json").read_text())
    c = json.loads((ROOT / "reliability_v2/C.json").read_text())
    out = {"authors_A0_both_legs_left_vs_right_ratio_250_types": round(find_ratio(a0["A0"]), 3),
           "ledger_one_sided_same_side": {k: round(v["primary"]["ratio"], 3) for k, v in a["six_agreements_primary_homolog_consistent"].items() if isinstance(v, dict) and "primary" in v},
           "ledger_whole_type_cross_fly_ratio_310": round(a["reference_R1_whole_type_cross_fly"]["primary"]["ratio"], 3),
           "partC_unfixed": {k: round(c["primary"]["unfixed"][k]["ratio"], 3) for k in ("cross_fly", "left_right")},
           "partC_fix2_pooled_readout": {k: round(c["primary"]["2"][k]["ratio"], 3) for k in ("cross_fly", "left_right")},
           "partC_fix1_dose_sweep_no_tuner": {k: round(c["primary"]["1"][k]["ratio"], 3) for k in ("cross_fly", "left_right")}}
    g2 = [l for l in (ROOT / "PREREG_v4.md").read_text().splitlines() if "front-leg motor" in l and ("144" in l or "130" in l or "67 left" in l)]
    out["readout_sizes_PREREG_v4_G2"] = g2
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
