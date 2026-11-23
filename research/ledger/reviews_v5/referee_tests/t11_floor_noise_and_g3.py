"""Referee test 11: three small checks on locked files and on arithmetic.

(a) 'About half of the homologous connections exist on one side only' (draft R2): how many of those one-sided pairs have 1-4
    synapses on the other side (below the model's 5-synapse floor) and how many have none (reliability_v2/WIRING_A4.json).
(b) Poisson resampling with the floor re-applied (draft R4, Part S): the probability that a connection of w synapses falls
    below the floor (is deleted) or that one of w < 5 rises to it (is created), next to the coefficient of variation 1/sqrt(w);
    the authors' own weight-noise test went up to 10 % (preprint Fig. 2f legend, see t10).
(c) The draft says the reimplementation 'reproduces their published dynamics'; the full-cord gate G3 v2 compared inter-leg
    coupling with the authors' traces (gates_v2/G3v2_REPORT.json): per-pair p values and the verdict.
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t11_floor_noise_and_g3.py
"""
from __future__ import annotations
import json
from pathlib import Path
from scipy.stats import poisson

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")


def main():
    w = json.loads((ROOT / "reliability_v2/WIRING_A4.json").read_text())["single_connections"]["MANC"]
    a = {k: w[k] for k in ("pairs", "present_both", "present_one_side_only", "share_one_side_only",
                           "one_sided_absent_partner_raw_1_to_4", "one_sided_absent_partner_raw_0",
                           "share_one_sided_only_because_of_floor")}
    a["share_of_all_pairs_with_no_synapse_on_one_side"] = round(w["one_sided_absent_partner_raw_0"] / w["pairs"], 3)
    b = {f"w={k}": {"P_deleted_(Poisson<5)" if k >= 5 else "P_created_(Poisson>=5)":
                    round(float(poisson.cdf(4, k)) if k >= 5 else float(poisson.sf(4, k)), 3),
                    "cv": round(k ** -0.5, 3)} for k in (2, 3, 4, 5, 6, 8, 10, 20, 50, 100)}
    g = json.loads((ROOT / "gates_v2/G3v2_REPORT.json").read_text())
    c = {"pairs": {p: {k: (round(v, 4) if isinstance(v, float) else v) for k, v in d.items() if k in ("R_ours", "R_authors", "p", "evaluable")}
                   for p, d in g["formal_run_coupling_consistency_reported"].items()},
         "criteria": g["criteria"], "pass": g["pass"]}
    out = {"a_one_sided_connections_MANC": a, "b_poisson_floor": b, "c_G3v2": c}
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
