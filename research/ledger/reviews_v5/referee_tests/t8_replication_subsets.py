"""Referee test 8: is the cross-fly overlap (B1r x B2r, driver >= 0.5) an artefact of unequal member counts, rarely accepted
replicates or unequal list sizes?

Inputs (locked): pertype_v1/B1r.csv, B2r.csv, match_confidence.csv. For each subset of common types: drivers in each fly, shared
drivers, hypergeometric expectation; plus the top-k overlap with k = the smaller driver count (equal list sizes), and the MaleCNS
hits whose MANC screen was never usable (n_usable = 0, scored 0 by rule).
Usage: uv run --project ledger --no-sync python research/ledger/reviews_v5/referee_tests/t8_replication_subsets.py
"""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).with_suffix(".out.json")


def main():
    P = ROOT / "pertype_v1"
    mc = pd.read_csv(P / "match_confidence.csv").set_index("manc_type")
    b1 = pd.read_csv(P / "B1r.csv").set_index("manc_type"); b2 = pd.read_csv(P / "B2r.csv").set_index("manc_type")
    c = sorted(set(b1.index) & set(b2.index))
    d = pd.DataFrame({"b1": b1.loc[c, "score"], "b2": b2.loc[c, "score"], "n1": b1.loc[c, "n_members"], "n2": b2.loc[c, "n_members"],
                      "u1": b1.loc[c, "n_usable"], "u2": b2.loc[c, "n_usable"], "conf": mc.loc[c, "confidence"],
                      "eqside": mc.loc[c, "per_side_counts_equal"].astype(bool)})
    subsets = {
        "high_215": d.conf == "high",
        "all_310": d.conf.notna(),
        "high_and_equal_member_counts": (d.conf == "high") & (d.n1 == d.n2),
        "high_and_equal_per_side_counts": (d.conf == "high") & d.eqside,
        "high_and_usable_ge_12_both": (d.conf == "high") & (d.u1 >= 12) & (d.u2 >= 12),
        "all_and_usable_16_both": (d.u1 == 16) & (d.u2 == 16),
    }
    out = {}
    for name, m in subsets.items():
        s = d[m]
        x = set(s[s.b1 >= 0.5].index); y = set(s[s.b2 >= 0.5].index)
        k = min(len(x), len(y))
        tx = set(s.b1.sort_values(ascending=False, kind="mergesort").index[:k]); ty = set(s.b2.sort_values(ascending=False, kind="mergesort").index[:k])
        out[name] = {"n_types": int(len(s)), "drivers_manc": len(x), "drivers_malecns": len(y), "shared": sorted(x & y),
                     "expected_if_independent": round(len(x) * len(y) / len(s), 2), "top_k_equal_size_overlap": f"{len(tx & ty)} of {k}",
                     "top_k_shared": sorted(tx & ty)}
    h = d[d.conf == "high"]
    out["malecns_hits_never_usable_in_manc_high"] = sorted(h[(h.b2 >= 0.5) & (h.u1 == 0)].index)
    out["manc_hits_with_under_12_usable_high"] = {t: int(h.loc[t, "u1"]) for t in h[(h.b1 >= 0.5) & (h.u1 < 12)].index}
    OUT.write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
