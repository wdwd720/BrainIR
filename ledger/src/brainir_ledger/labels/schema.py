"""Label record schema and validator (LABEL SIDE: never reads predictions; enforced by tests/test_label_isolation.py).

One record = one experiment: a DN type or driver line activated in an adult fly (optogenetic or thermogenetic) with leg
movement observable (PREREG section 6; kit PROTOCOL.md). `validate_record` returns a list of problems (empty = valid).
`json_schema()` is the machine-readable form copied into the labeler kit.
"""

from __future__ import annotations

import json
import re

LEG_VALUES = ("yes", "no", "unclear", "not_assessed")
PREPARATION = ("intact_free", "intact_tethered", "headless", "other")
EXPRESSION = ("bilateral", "unilateral", "stochastic")
SPECIFICITY = ("clean", "minor_offtarget", "multi_dn", "unknown")
BEHAVIOUR = ("forward_walking", "backward_walking", "turning", "anterior_grooming", "posterior_grooming", "halting",
             "takeoff_or_jump", "landing_or_extension", "wing_or_flight", "posture", "no_visible_effect", "other")
EFFECT_ON_WALKING = ("stops", "slows", "speeds", "turns", "none", "not_assessed")
SOURCE_TYPE = ("systematic_screen", "targeted_study")
CONFIDENCE = ("high", "medium", "low")
MAPPING_CONFIDENCE = ("high", "medium", "low")
ACCESS = ("full_text", "abstract_only", "supplement_only", "figure_or_movie")
SEX = ("male", "female", "mixed", "unknown")
SURFACE = ("ball", "air", "slippery_surface", "other")
EFFECTOR_KIND = ("optogenetic", "thermogenetic")
PASS_IDS = ("pass1", "pass2", "search", "adjudication")

REQUIRED = {
    "record_id": str, "pass_id": str, "session": str,
    "doi": str, "source_locator": str, "quote": str, "source_type": str, "access": str,
    "name_in_paper": str, "manc_type": str, "mapping_confidence": str,
    "driver_lines": list, "effector": str, "effector_kind": str, "stimulation": str,
    "sex": str, "preparation": str, "expression": str, "line_specificity": str, "other_cell_types": list,
    "front_leg_rhythm": str, "middle_leg_rhythm": str, "hind_leg_rhythm": str,
    "behaviour_category": str, "effect_on_walking": str,
    "labeler_confidence": str, "saw_simulation_score": bool,
}
OPTIONAL = {
    "page": (str, type(None)), "type_coverage": (str, type(None)), "sensory_condition": (str, type(None)),
    "headless_surface": (str, type(None)), "frequency_hz": (int, float, type(None)), "coordination_notes": (str, type(None)),
    "penetrance": (str, type(None)), "n_flies": (int, type(None)), "secondary_behaviours": (list, type(None)),
    "mapping_basis": (str, type(None)), "notes": (str, type(None)), "experiment_key": (str, type(None)),
    "quote_verified": (bool, type(None)), "title": (str, type(None)), "year": (int, type(None)),
}
ENUMS = {"pass_id": PASS_IDS, "source_type": SOURCE_TYPE, "access": ACCESS, "mapping_confidence": MAPPING_CONFIDENCE,
         "effector_kind": EFFECTOR_KIND, "sex": SEX, "preparation": PREPARATION, "expression": EXPRESSION,
         "line_specificity": SPECIFICITY, "front_leg_rhythm": LEG_VALUES, "middle_leg_rhythm": LEG_VALUES, "hind_leg_rhythm": LEG_VALUES,
         "behaviour_category": BEHAVIOUR, "effect_on_walking": EFFECT_ON_WALKING, "labeler_confidence": CONFIDENCE,
         "headless_surface": SURFACE}
MAX_QUOTE_WORDS = 25
UNMAPPED = "UNMAPPED"


def experiment_key(rec: dict) -> str:
    """Identity of an experiment across passes: DOI + locator + sorted lines + name used (normalised)."""
    def norm(s):
        return re.sub(r"\s+", " ", str(s or "")).strip().lower()
    lines = ",".join(sorted(norm(x) for x in rec.get("driver_lines") or []))
    return f"{norm(rec.get('doi'))}|{norm(rec.get('source_locator'))}|{lines}|{norm(rec.get('name_in_paper'))}"


def validate_record(rec: dict, known_types: set[str] | None = None) -> list[str]:
    errs = []
    if not isinstance(rec, dict):
        return ["record is not an object"]
    for k, t in REQUIRED.items():
        if k not in rec:
            errs.append(f"missing field {k}")
        elif not isinstance(rec[k], t) or (t is str and not rec[k].strip()):
            errs.append(f"field {k} must be a non-empty {t.__name__}")
    for k, ts in OPTIONAL.items():
        if k in rec and not isinstance(rec[k], ts):
            errs.append(f"field {k} has wrong type {type(rec[k]).__name__}")
    extra = set(rec) - set(REQUIRED) - set(OPTIONAL)
    if extra:
        errs.append(f"unknown fields {sorted(extra)}")
    for k, vocab in ENUMS.items():
        v = rec.get(k)
        if v is not None and k in rec and v not in vocab:
            errs.append(f"field {k} = {v!r} not in {list(vocab)}")
    q = rec.get("quote")
    if isinstance(q, str) and len(q.split()) > MAX_QUOTE_WORDS:
        errs.append(f"quote has {len(q.split())} words (max {MAX_QUOTE_WORDS})")
    if rec.get("preparation") == "headless" and rec.get("headless_surface") is None:
        errs.append("headless record needs headless_surface")
    if rec.get("line_specificity") in ("multi_dn", "minor_offtarget") and not rec.get("other_cell_types"):
        errs.append("non-specific line needs other_cell_types")
    for k in ("driver_lines", "other_cell_types", "secondary_behaviours"):
        if isinstance(rec.get(k), list) and not all(isinstance(x, str) for x in rec[k]):
            errs.append(f"{k} must be a list of strings")
    if isinstance(rec.get("secondary_behaviours"), list):
        bad = [x for x in rec["secondary_behaviours"] if x not in BEHAVIOUR]
        if bad:
            errs.append(f"secondary_behaviours not in vocabulary: {bad}")
    if known_types is not None and isinstance(rec.get("manc_type"), str) and rec["manc_type"] not in known_types \
            and rec["manc_type"] != UNMAPPED:
        errs.append(f"manc_type {rec['manc_type']!r} is not in the type list (use {UNMAPPED!r} and explain in mapping_basis)")
    if isinstance(rec.get("doi"), str) and not (rec["doi"].startswith("10.") or rec["doi"].startswith("http")):
        errs.append("doi must start with '10.' (or be a URL when no DOI exists)")
    return errs


def validate_file(path, known_types: set[str] | None = None) -> tuple[list[dict], list[tuple[int, list[str]]]]:
    good, bad = [], []
    with open(path, encoding="utf-8") as fh:
        for i, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError as e:
                bad.append((i, [f"invalid JSON: {e}"]))
                continue
            e = validate_record(rec, known_types)
            (bad.append((i, e)) if e else good.append(rec))
    return good, bad


def json_schema() -> dict:
    def t(py):
        return {str: "string", list: "array", bool: "boolean", int: "integer", float: "number", type(None): "null"}[py]
    props = {}
    for k, v in REQUIRED.items():
        props[k] = {"type": t(v)}
    for k, v in OPTIONAL.items():
        props[k] = {"type": sorted({t(x) for x in v})}
    for k, vocab in ENUMS.items():
        props[k]["enum"] = list(vocab) + ([None] if k in OPTIONAL else [])
    for k in ("driver_lines", "other_cell_types", "secondary_behaviours"):
        props[k]["items"] = {"type": "string"}
    props["quote"]["description"] = f"verbatim quote from the source, at most {MAX_QUOTE_WORDS} words"
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "title": "BrainIR ledger label record v1", "type": "object",
            "required": sorted(REQUIRED), "properties": props, "additionalProperties": False}
