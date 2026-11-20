"""Deterministic label aggregation (LABEL SIDE: never reads predictions).

* `merge_passes`: final records = pass-1 records with every field on which pass 2 disagreed replaced by the adjudicated value;
  records whose quote pass 2 could not verify are dropped (PREREG section 6).
* `type_labels`: per-type consensus for the front / middle / hind leg pairs and the stop call (PREREG section 6).
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from pathlib import Path

import pandas as pd

from .schema import experiment_key

PREP_RANK = {"headless": 0, "intact_free": 1, "intact_tethered": 1, "other": 2}
SPEC_RANK = {"clean": 0, "minor_offtarget": 1, "unknown": 2, "multi_dn": 3}
CONF_RANK = {"high": 0, "medium": 0, "low": 1}
LEG_FIELDS = {"front": "front_leg_rhythm", "middle": "middle_leg_rhythm", "hind": "hind_leg_rhythm"}
COMPARED_FIELDS = ("front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm", "effect_on_walking", "preparation", "line_specificity")


def read_records(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def merge_passes(pass1: list[dict], pass2: list[dict], adjudicated: list[dict]) -> tuple[list[dict], dict]:
    """Final records and a log of what happened to each pass-1 record."""
    p2 = {}
    for r in pass2:
        p2.setdefault(r.get("experiment_key") or experiment_key(r), []).append(r)
    adj = {r.get("experiment_key") or experiment_key(r): r for r in adjudicated}
    final, log = [], {"no_pass2": [], "quote_unverified": [], "agreed": [], "adjudicated": [], "disagreed_unadjudicated": []}
    for r in pass1:
        k = r.get("experiment_key") or experiment_key(r)
        twins = p2.get(k)
        if not twins:
            log["no_pass2"].append(k)
            continue
        t = twins[0]
        if t.get("quote_verified") is False:
            log["quote_unverified"].append(k)
            continue
        diff = [f for f in COMPARED_FIELDS if r.get(f) != t.get(f)]
        rec = dict(r)
        rec["experiment_key"] = k
        if diff:
            a = adj.get(k)
            if a is None:
                log["disagreed_unadjudicated"].append(k)
                continue
            for f in diff:
                rec[f] = a[f]
            log["adjudicated"].append(k)
        else:
            log["agreed"].append(k)
        final.append(rec)
    return final, log


def _consensus(recs: list[dict], field: str) -> str:
    elig = [r for r in recs if r.get(field) in ("yes", "no")]
    if not elig:
        return "unclear" if any(r.get(field) == "unclear" for r in recs) else "not_assessed"
    best_p = min(PREP_RANK.get(r["preparation"], 9) for r in elig)
    elig = [r for r in elig if PREP_RANK.get(r["preparation"], 9) == best_p]
    best_s = min(SPEC_RANK.get(r["line_specificity"], 9) for r in elig)
    elig = [r for r in elig if SPEC_RANK.get(r["line_specificity"], 9) == best_s]
    if any(CONF_RANK.get(r["labeler_confidence"], 1) == 0 for r in elig):
        elig = [r for r in elig if CONF_RANK.get(r["labeler_confidence"], 1) == 0]
    vals = {r[field] for r in elig}
    return vals.pop() if len(vals) == 1 else "conflicting"


def eligible(r: dict) -> bool:
    return (not r.get("saw_simulation_score")) and r.get("mapping_confidence") != "low" and r.get("quote_verified", True) is not False \
        and r.get("manc_type") not in (None, "", "UNMAPPED")


def type_labels(records: Iterable[dict], *, flt: Callable[[dict], bool] | None = None, exposed: set[str] = frozenset(),
                type_list: Iterable[str] | None = None) -> pd.DataFrame:
    recs = [r for r in records if eligible(r) and (flt is None or flt(r))]
    by: dict[str, list[dict]] = {}
    for r in recs:
        by.setdefault(r["manc_type"], []).append(r)
    rows = []
    for t in sorted(set(by) | set(type_list or [])):
        rs = by.get(t, [])
        row = {"manc_type": t, "n_records": len(rs), "exposed": t in exposed}
        for leg, field in LEG_FIELDS.items():
            row[leg] = _consensus(rs, field) if rs else "not_assessed"
        if rs:
            best_p = min(PREP_RANK.get(r["preparation"], 9) for r in rs)
            top = [r for r in rs if PREP_RANK.get(r["preparation"], 9) == best_p]
            stop = any(r.get("effect_on_walking") == "stops" or r.get("behaviour_category") == "halting" for r in top)
            front_yes = any(r.get("front_leg_rhythm") == "yes" for r in top)
            row["stop_call"] = "stops" if (stop and not front_yes) else ("no_stop" if any(r.get("effect_on_walking") in ("none", "slows",
                                                                                                                            "speeds", "turns")
                                                                                          for r in top) or front_yes else "not_assessed")
            row["best_preparation"] = min((r["preparation"] for r in rs), key=lambda p: PREP_RANK.get(p, 9))
            row["best_specificity"] = min((r["line_specificity"] for r in rs), key=lambda s: SPEC_RANK.get(s, 9))
            row["has_systematic"] = any(r.get("source_type") == "systematic_screen" for r in rs)
            row["confidence"] = min((r["labeler_confidence"] for r in rs), key=lambda c: {"high": 0, "medium": 1, "low": 2}[c])
            fr = [r["frequency_hz"] for r in rs if isinstance(r.get("frequency_hz"), (int, float))]
            row["freq_hz"] = sorted(fr)[len(fr) // 2] if fr else None
        else:
            row.update(stop_call="not_assessed", best_preparation=None, best_specificity=None, has_systematic=False, confidence=None,
                       freq_hz=None)
        rows.append(row)
    cols = ["manc_type", "front", "middle", "hind", "stop_call", "best_preparation", "best_specificity", "n_records", "has_systematic",
            "exposed", "confidence", "freq_hz"]
    return pd.DataFrame(rows, columns=cols)
