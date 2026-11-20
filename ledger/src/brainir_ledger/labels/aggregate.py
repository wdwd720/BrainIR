"""Deterministic label aggregation (LABEL SIDE: never reads predictions). PREREG section 6.

Identity: every pass-1 record gets a unique experiment id `exp_id` = "<session>:<record_id>" when it is collected; pass 2
and the adjudicator copy it from their input files. Nothing is matched by content keys.

* `dedupe_pass1`: the same experiment written by two pass-1 sessions (identical DOI, locator, driver lines, name used,
  preparation, MANC type, effector and stimulation) is kept once, from the session earliest in FAMILY_ORDER (logged).
* `merge_passes`: final records = pass-1 records whose quote pass 2 found, with every disputed field group replaced by the
  adjudicator's reading; confidence = the lowest of the readers that contributed; `saw_simulation_score` = any reader's;
  re-validated (invalid -> dropped, logged).
* `type_labels`: per-type consensus for the front / middle / hind leg pairs, the stop call and the walking effect.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from pathlib import Path

import pandas as pd

from .schema import validate_record

PREP_RANK = {"headless": 0, "intact_free": 1, "intact_tethered": 1, "other": 2}
SPEC_RANK = {"clean": 0, "minor_offtarget": 1, "unknown": 2, "multi_dn": 3}
CONF_ORDER = {"high": 0, "medium": 1, "low": 2}
LEG_FIELDS = {"front": "front_leg_rhythm", "middle": "middle_leg_rhythm", "hind": "hind_leg_rhythm"}
COMPARED_FIELDS = ("manc_type", "front_leg_rhythm", "middle_leg_rhythm", "hind_leg_rhythm", "effect_on_walking", "line_specificity")
# fields that are copied together from the adjudicator when any of them is disputed
FIELD_GROUPS = (("manc_type", "mapping_confidence", "mapping_basis"), ("line_specificity", "other_cell_types"),
                ("effect_on_walking",), ("front_leg_rhythm",), ("middle_leg_rhythm",), ("hind_leg_rhythm",))
FAMILY_ORDER = ("atlas", "catalogue", "grooming", "walking_stopping", "steering", "escape_landing", "recent_broad", "pugliese_dedicated")


def read_records(path: Path) -> list[dict]:
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                out.append(json.loads(line))
    return out


def _norm(s) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()


def content_signature(r: dict) -> str:
    lines = ",".join(sorted(_norm(x) for x in r.get("driver_lines") or []))
    return "|".join([_norm(r.get("doi")), _norm(r.get("source_locator")), lines, _norm(r.get("name_in_paper")), _norm(r.get("preparation")),
                     _norm(r.get("manc_type")), _norm(r.get("effector")), _norm(r.get("stimulation"))])


def _family_rank(exp_id: str) -> int:
    sess = exp_id.split(":", 1)[0]
    fam = sess.split("-", 1)[-1]
    return FAMILY_ORDER.index(fam) if fam in FAMILY_ORDER else len(FAMILY_ORDER)


def dedupe_pass1(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """(kept, dropped-log). Records must carry exp_id."""
    best: dict[str, dict] = {}
    dropped = []
    for r in sorted(records, key=lambda r: (_family_rank(r["exp_id"]), r["exp_id"])):
        sig = content_signature(r)
        if sig in best:
            dropped.append({"exp_id": r["exp_id"], "duplicate_of": best[sig]["exp_id"]})
        else:
            best[sig] = r
    kept = sorted(best.values(), key=lambda r: r["exp_id"])
    return kept, dropped


def _lowest_conf(*vals) -> str:
    v = [x for x in vals if x in CONF_ORDER]
    return max(v, key=lambda c: CONF_ORDER[c]) if v else "low"


def merge_passes(pass1: list[dict], pass2: list[dict], adjudicated: list[dict], quote_checks: dict[str, bool],
                 not_found: Iterable[str] = ()) -> tuple[list[dict], dict]:
    """Final records and a log keyed by outcome. Every record must carry `exp_id`."""
    for recs, name in ((pass1, "pass1"), (pass2, "pass2"), (adjudicated, "adjudication")):
        if any(r.get("exp_id") is None for r in recs):
            raise ValueError(f"{name} records without exp_id")
    if len({r["exp_id"] for r in pass1}) != len(pass1):
        raise ValueError("pass-1 exp_id values are not unique")
    log = {"not_found_by_pass2": [], "no_pass2": [], "quote_unverified": [], "agreed": [], "adjudicated": [],
           "disagreed_unadjudicated": [], "invalid_after_merge": [], "duplicate_pass2": [], "duplicate_adjudication": []}
    p2: dict[str, dict] = {}
    for r in pass2:
        if r["exp_id"] in p2:
            log["duplicate_pass2"].append(r["exp_id"])
            continue
        p2[r["exp_id"]] = r
    adj: dict[str, dict] = {}
    for r in adjudicated:
        if r["exp_id"] in adj:
            log["duplicate_adjudication"].append(r["exp_id"])
            continue
        adj[r["exp_id"]] = r
    nf = set(not_found)
    final = []
    for r in pass1:
        k = r["exp_id"]
        if k in nf:
            log["not_found_by_pass2"].append(k)
            continue
        t = p2.get(k)
        if t is None:
            log["no_pass2"].append(k)
            continue
        if quote_checks.get(k) is not True:
            log["quote_unverified"].append(k)
            continue
        diff = [f for f in COMPARED_FIELDS if r.get(f) != t.get(f)]
        rec = dict(r)
        readers = [r.get("labeler_confidence"), t.get("labeler_confidence")]
        saw = bool(r.get("saw_simulation_score")) or bool(t.get("saw_simulation_score"))
        outcome = "agreed"
        if diff:
            a = adj.get(k)
            if a is None:
                log["disagreed_unadjudicated"].append(k)
                continue
            for grp in FIELD_GROUPS:
                if any(f in diff for f in grp):
                    for f in grp:
                        if f in a:
                            rec[f] = a[f]
                        else:
                            rec.pop(f, None)
            readers.append(a.get("labeler_confidence"))
            saw = saw or bool(a.get("saw_simulation_score"))
            outcome = "adjudicated"
        rec["labeler_confidence"] = _lowest_conf(*readers)
        rec["saw_simulation_score"] = saw
        rec["quote_verified"] = True
        errs = validate_record(rec)
        if errs:
            log["invalid_after_merge"].append({"exp_id": k, "n_errors": len(errs)})
            continue
        log[outcome].append(k)
        final.append(rec)
    return final, log


def eligible(r: dict) -> bool:
    return (not r.get("saw_simulation_score")) and r.get("mapping_confidence") != "low" and r.get("quote_verified") is True \
        and r.get("manc_type") not in (None, "", "UNMAPPED")


def _tier(recs: list[dict]) -> list[dict]:
    """Consensus order (PREREG section 6): drop low confidence if better exists; drop multi-DN lines if other records
    exist; keep the best preparation, then the best specificity."""
    if any(CONF_ORDER.get(r["labeler_confidence"], 2) <= 1 for r in recs):
        recs = [r for r in recs if CONF_ORDER.get(r["labeler_confidence"], 2) <= 1]
    if any(r["line_specificity"] != "multi_dn" for r in recs):
        recs = [r for r in recs if r["line_specificity"] != "multi_dn"]
    bp = min(PREP_RANK.get(r["preparation"], 9) for r in recs)
    recs = [r for r in recs if PREP_RANK.get(r["preparation"], 9) == bp]
    bs = min(SPEC_RANK.get(r["line_specificity"], 9) for r in recs)
    return [r for r in recs if SPEC_RANK.get(r["line_specificity"], 9) == bs]


def _leg_consensus(recs: list[dict], field: str) -> str:
    elig = [r for r in recs if r.get(field) in ("yes", "no", "unclear")]
    if not elig:
        return "not_assessed"
    vals = {r[field] for r in _tier(elig)}
    if vals == {"yes"}:
        return "yes"
    if vals == {"no"}:
        return "no"
    if {"yes", "no"} <= vals:
        return "conflicting"
    return "unclear"


def _stop_value(r: dict) -> str | None:
    if r.get("effect_on_walking") == "stops" or r.get("behaviour_category") == "halting":
        return "stops"
    if r.get("front_leg_rhythm") == "yes" or r.get("effect_on_walking") in ("none", "slows", "speeds", "turns"):
        return "no_stop"
    return None


def _walk_value(r: dict) -> str | None:
    v = r.get("effect_on_walking")
    return v if v not in (None, "not_assessed") else None


def _value_consensus(recs: list[dict], value: Callable[[dict], str | None]) -> str:
    elig = [r for r in recs if value(r) is not None]
    if not elig:
        return "not_assessed"
    vals = {value(r) for r in _tier(elig)}
    return vals.pop() if len(vals) == 1 else "conflicting"


def _median(v: list[float]) -> float | None:
    if not v:
        return None
    v = sorted(v)
    return (v[(len(v) - 1) // 2] + v[len(v) // 2]) / 2


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
            row[leg] = _leg_consensus(rs, field)
        row["stop_call"] = _value_consensus(rs, _stop_value)
        row["walking_effect"] = _value_consensus(rs, _walk_value)
        if rs:
            row["best_preparation"] = min((r["preparation"] for r in rs), key=lambda p: PREP_RANK.get(p, 9))
            row["best_specificity"] = min((r["line_specificity"] for r in rs), key=lambda s: SPEC_RANK.get(s, 9))
            row["has_systematic"] = any(r.get("source_type") == "systematic_screen" for r in rs)
            row["confidence"] = min((r["labeler_confidence"] for r in rs), key=lambda c: CONF_ORDER.get(c, 2))
            row["freq_hz"] = _median([float(r["frequency_hz"]) for r in rs if isinstance(r.get("frequency_hz"), (int, float))
                                      and not isinstance(r.get("frequency_hz"), bool) and r.get("front_leg_rhythm") == "yes"])
        else:
            row.update(best_preparation=None, best_specificity=None, has_systematic=False, confidence=None, freq_hz=None)
        rows.append(row)
    cols = ["manc_type", "front", "middle", "hind", "stop_call", "walking_effect", "best_preparation", "best_specificity", "n_records",
            "has_systematic", "exposed", "confidence", "freq_hz"]
    return pd.DataFrame(rows, columns=cols)
