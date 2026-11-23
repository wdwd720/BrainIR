"""PREREG v5 Part F: the decision rule, the clean-line rule and the short-list order on hand-made inputs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import forward_v2 as FV  # noqa: E402


def test_decision_rule_and_power():
    assert FV.q_of(4) is None and FV.q_of(5) == 5 and FV.q_of(8) == 7 and FV.q_of(12) == 10
    assert FV.decide(4, 4, "replication", "single-connectome") == "inconclusive"
    assert FV.decide(8, 7, "replication", "counting") == "supports the replication reading over the counting reading"
    assert FV.decide(8, 1, "replication", "counting") == "supports the counting reading over the replication reading"
    assert FV.decide(8, 5) == "inconclusive"
    assert abs(FV.power(8, 0.8) - 0.503) < 1e-3 and FV.power(4, 0.9) == 0.0


def test_clean_lines_count_ambiguous_candidates():
    dl = pd.DataFrame([{"line_id": "L1", "manc_type": "DNa", "candidate_types": "DNa", "other_cells": ""},
                       {"line_id": "L1", "manc_type": "AMBIGUOUS", "candidate_types": "DNa;DNb", "other_cells": ""},
                       {"line_id": "L2", "manc_type": "DNa", "candidate_types": "DNa", "other_cells": "also DNc neurons"},
                       {"line_id": "L3", "manc_type": "DNa", "candidate_types": "DNa", "other_cells": "some VNC neurons"}])
    import re
    pats = {t: re.compile(r"(?<![A-Za-z0-9])" + t + r"(?![A-Za-z0-9])", re.I) for t in ("DNa", "DNb", "DNc")}
    got = {r["line"]: (r["clean"], r["other_dn_types"]) for r in FV.lines_for("DNa", dl, pats)}
    assert got == {"L1": (False, ["DNb"]), "L2": (False, ["DNc"]), "L3": (True, [])}


def test_shortlist_order_and_availability():
    def row(t, cat, b1, b2, a1yes, s2, lines, clean=1):
        return {"manc_type": t, "category": cat, "replication_reading": "yes" if cat in FV.GROUP1 else "no",
                "single_connectome_reading": a1yes, "counting_reading": "no", "B1r": b1, "B2r": b2, "A1": 0.0, "S2_twohop_signed": s2,
                "match_confidence": "high", "n_lines": len(lines.split(";")), "n_clean_lines": clean, "lines": lines,
                "already_tested_headless": "", "eligible_F1": True}
    cand = pd.DataFrame([row("R1", "replicated", 0.9, 0.6, "yes", 0, "a"), row("N1", "near_replicated", 0.6, 0.4, "no", 0, "b"),
                         row("N2", "near_replicated", 0.7, 0.35, "no", 0, "c"), row("S1", "single_fly_manc", 0.8, 0.1, "no", 0, "d"),
                         row("S2", "single_fly_manc", 0.6, 0.1, "yes", 0, "e"), row("M1", "single_fly_malecns", 0.1, 0.9, "no", 0, "f"),
                         row("C1", "stable_non_driver", 0, 0, "no", 50, "g"), row("C2", "stable_non_driver", 0, 0, "no", 90, "h"),
                         row("X1", "single_fly_manc", 0.9, 0.0, "yes", 0, "z")])
    avail = {k: "yes" for k in "abcdefgh"}  # X1's only line is not available
    short, why = FV.shortlist(cand, avail)
    assert list(short["manc_type"]) == ["R1", "N1", "N2", "S2", "S1", "M1", "C2", "C1"]
    assert why.set_index("manc_type").loc["X1", "not_listed_because"] == "no line listed as available"
    cmp_ = FV.comparisons(short)
    assert cmp_["A_replication_vs_single_connectome"]["types"] == ["N1", "N2", "S2"]
