"""Cross-connectome neuron mapping: candidate counterparts of A neurons in B (default A = male-cns:v1.0, B = manc:v1.2.1).

Two connectomes are two animals. **No row of the mapping table asserts identity.** Each row records which fields were
compared (``method``), the epistemic status of that comparison (``evidence_kind``), a coarse category
(``mapping_kind``), a uniqueness label (``confidence``) and how many B candidates the rule produced (``ambiguity``).
``confidence`` and ``ambiguity`` describe the A -> B direction (how uniquely the A neuron's rule singled out B
candidates); ``b_ambiguity`` gives the B -> A count (how many A neurons name the same B candidate under the same
rule). **Neither encodes agreement**: whether the candidate's own annotations agree with A's lives in the
``*_consistent`` columns (``manc_type_consistent``, ``a_type_consistent``, ``side_consistent``, ``role_consistent``,
``nt_consistent``); a ``high`` body match whose current snapshot type contradicts the annotation is still ``high``.

Rules, applied in priority order to every A neuron in scope (the first rule that yields candidates wins):

1. ``curated_body_match``  A's ``manc_body_id`` (the A release's own cross-dataset annotation) is a neuron of B.
   ``confidence='high'`` — still an annotation made by the A release, not an observation of identity.
2. ``curated_type_match``  no body match, but A's ``manc_type`` names a B cell type: one row per B neuron of that type,
   filtered to A's side when both sides are known (candidates with unknown side are kept).
3. ``same_type_name``      A's ``cell_type`` equals a B ``cell_type`` verbatim (BrainIR-derived comparison; same side
   handling). A shared name is a curation convention, not evidence of homology.
4. ``same_role_only``      only the coarse role class (rule ``brainir.role.v1``) is shared; no per-neuron candidate
   (``b_source_id`` null, ``ambiguity`` = number of B neurons with that role).
5. ``unmatched``           nothing above.

For rules 2 and 3 ``confidence='medium'`` when exactly one same-side candidate remains, else ``'low'``.

Scope of A: neurons whose ``role_class`` is a VNC role (:data:`VNC_ROLES`) plus neurons carrying a curated MANC
annotation whatever their role (the annotation is evidence that the release matched them; a role inconsistency is
flagged in ``role_consistent``, never hidden). All other A neurons (brain-only classes) cannot have a counterpart in a
VNC-only volume; they are counted in the summary (``scope.out_of_scope``) and not enumerated as rows.

The same table serves the reverse direction B -> A (:func:`reverse_lookup`): a B neuron may appear in several rows.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from . import paths
from .graph import Connectome
from .io import sha256_file, write_canonical
from .schema.evidence import EvidenceKind as E
from .schema.tables import DSTR, STR, Col, TableSpec, conform
from .schema.vocab import NT_CLASSES, ROLE_RULE_ID

MAPPING_SCHEMA_VERSION = "1.1.0"
"""1.1.0 (2026-09-23): + manc_type_consistent, a_type_consistent, b_ambiguity; confidence documented as A -> B uniqueness."""
MAPPING_KINDS = ("curated_body_match", "curated_type_match", "same_type_name", "same_role_only", "unmatched")
CONFIDENCE_LEVELS = ("high", "medium", "low", "none")
VNC_ROLES = frozenset({"descending", "ascending", "sensory_ascending", "sensory_descending", "efferent",
                       "vnc_intrinsic", "vnc_motor", "vnc_sensory", "vnc_unknown"})
"""Role classes (rule brainir.role.v1) whose neurons have arbor in the VNC and can therefore exist in a VNC connectome."""
A_NT_FIELD = "nt_consensus"
"""NT label compared on the A side (MaleCNS publishes a consensus label)."""
B_NT_FIELD = "nt_body_prediction"
"""NT label compared on the B side (MANC publishes body-level predictions only)."""
TABLE_FILENAME = "neuron_mapping.parquet"
SUMMARY_FILENAME = "summary.json"

MAPPING = TableSpec(
    name="neuron_mapping",
    description="Candidate counterparts of A neurons in B. One row per (A neuron, B candidate) plus one row per A neuron "
                "without a candidate. Never identity: two animals, compared on annotations.",
    primary_key=("a_source_id", "b_source_id"),
    sort_by=("a_source_id", "b_source_id"),
    columns=(
        Col("a_uid", STR, E.IDENTIFIER, "neuron_uid of the A neuron ('<dataset>:<version>:<source_id>').", False),
        Col("b_uid", STR, E.IDENTIFIER, "neuron_uid of the B candidate; null for same_role_only / unmatched rows."),
        Col("a_source_id", pa.int64(), E.IDENTIFIER, "A dataset-native ID (meaningful only with the A dataset:version).", False),
        Col("b_source_id", pa.int64(), E.IDENTIFIER, "B dataset-native ID; null when the row has no per-neuron candidate."),
        Col("mapping_kind", DSTR, E.PROVENANCE, "Rule that produced the row: " + ", ".join(MAPPING_KINDS) + ".", False),
        Col("method", DSTR, E.PROVENANCE, "Which fields were compared.", False),
        Col("evidence_kind", DSTR, E.PROVENANCE, "Epistemic status of the comparison: curated_annotation (the A release's "
                                                 "own cross-dataset annotation) or derived_anatomy (BrainIR comparison of labels).", False),
        Col("confidence", DSTR, E.PROVENANCE, "Uniqueness label for the A -> B direction, NOT agreement: high (curated body match), "
                                              "medium (one same-side candidate), low (several / side unknown), none (no per-neuron "
                                              "candidate). Agreement of the candidate's annotations is in the *_consistent columns.", False),
        Col("ambiguity", pa.int32(), E.PROVENANCE, "Number of B candidates this rule produced for the A neuron (A -> B; 0 = unmatched).",
            False, unit="count"),
        Col("b_ambiguity", pa.int32(), E.PROVENANCE, "Number of A neurons whose rows of the same mapping_kind name this B candidate "
                                                     "(B -> A direction); null without a candidate.", unit="count"),
        Col("a_cell_type", STR, E.CURATED_ANNOTATION, "A cell_type."),
        Col("b_cell_type", STR, E.CURATED_ANNOTATION, "B cell_type of the candidate."),
        Col("a_side", DSTR, E.DERIVED_ANATOMY, "A side (soma side, else root side)."),
        Col("b_side", DSTR, E.DERIVED_ANATOMY, "B side of the candidate."),
        Col("side_consistent", pa.bool_(), E.DERIVED_ANATOMY, "a_side == b_side; null when either is unknown."),
        Col("a_role_class", DSTR, E.CURATED_ANNOTATION, f"A role class (rule {ROLE_RULE_ID})."),
        Col("b_role_class", DSTR, E.CURATED_ANNOTATION, "B role class of the candidate (same_role_only rows: the shared role)."),
        Col("role_consistent", pa.bool_(), E.DERIVED_ANATOMY, "a_role_class == b_role_class; null when either is unknown."),
        Col("a_nt", DSTR, E.ML_PREDICTION, f"A neurotransmitter label ({A_NT_FIELD}); prediction/curation mix, not physiology."),
        Col("b_nt", DSTR, E.ML_PREDICTION, f"B neurotransmitter label ({B_NT_FIELD}); ML prediction, not physiology."),
        Col("nt_consistent", pa.bool_(), E.DERIVED_ANATOMY, "a_nt == b_nt; null when either is missing, 'unclear' or 'unknown'."),
        Col("manc_type_consistent", pa.bool_(), E.DERIVED_ANATOMY, "A's curated manc_type == the B candidate's current cell_type; null "
                                                                   "when either is missing or the row has no candidate."),
        Col("a_type_consistent", pa.bool_(), E.DERIVED_ANATOMY, "A cell_type == the B candidate's cell_type (verbatim names); null when "
                                                                "either is missing or the row has no candidate."),
        Col("notes", STR, E.PROVENANCE, "Free-text details of the rule application (side filtering, annotation disagreements)."),
    ),
)

_METHOD = {
    "curated_body_match": "a.manc_body_id == b.source_id",
    "curated_type_match": "a.manc_type == b.cell_type; side filter",
    "same_type_name": "a.cell_type == b.cell_type; side filter",
    "same_role_only": "a.role_class == b.role_class (no per-neuron candidate)",
    "unmatched": "no rule matched",
}
_EVIDENCE = {
    "curated_body_match": str(E.CURATED_ANNOTATION), "curated_type_match": str(E.CURATED_ANNOTATION),
    "same_type_name": str(E.DERIVED_ANATOMY), "same_role_only": str(E.DERIVED_ANATOMY), "unmatched": str(E.DERIVED_ANATOMY),
}
_PANDAS_TYPES = {pa.int64(): pd.Int64Dtype(), pa.int32(): pd.Int32Dtype(), pa.bool_(): pd.BooleanDtype()}


@dataclass(frozen=True)
class MappingSpec:
    a_dataset: str = "male-cns"
    a_version: str = "v1.0"
    b_dataset: str = "manc"
    b_version: str = "v1.2.1"

    @property
    def a_key(self) -> str:
        return f"{self.a_dataset}_{self.a_version}"

    @property
    def b_key(self) -> str:
        return f"{self.b_dataset}_{self.b_version}"

    @property
    def dir_name(self) -> str:
        """Directory name under data/processed/mappings ('<a>__<b>'; ':' is illegal in Windows file names)."""
        return f"{self.a_key}__{self.b_key}"

    @classmethod
    def parse(cls, a: str, b: str) -> MappingSpec:
        """From 'dataset:version' strings."""
        (ad, av), (bd, bv) = _split_build(a), _split_build(b)
        return cls(ad, av, bd, bv)


def _split_build(s: str) -> tuple[str, str]:
    if ":" not in s:
        raise ValueError(f"expected 'dataset:version', got {s!r}")
    d, v = s.split(":", 1)
    return d, v


def default_mapping_dir(spec: MappingSpec) -> Path:
    return paths.data_root() / "processed" / "mappings" / spec.dir_name


# ----------------------------------------------------------------------------- helpers
def _val(x):
    """Python scalar or None for any pandas/numpy null flavour."""
    if x is None or x is pd.NA:
        return None
    if isinstance(x, float) and math.isnan(x):
        return None
    if isinstance(x, np.generic):
        return x.item()
    return x


def _objs(series: pd.Series) -> list:
    return [_val(x) for x in series.tolist()]


def _consistent(a, b) -> bool | None:
    return None if a is None or b is None else bool(a == b)


def _nt_consistent(a, b) -> bool | None:
    """Comparable only when both labels are concrete transmitter classes ('unclear'/'unknown'/null -> None)."""
    if a not in NT_CLASSES or b not in NT_CLASSES:
        return None
    return bool(a == b)


class _Lookup:
    """Per-neuron scalar lookups of one connectome (ids ascending)."""

    def __init__(self, cx: Connectome):
        n = cx.neurons
        self.ids: list[int] = [int(i) for i in cx.ids]

        def col(name):
            return dict(zip(self.ids, _objs(n[name]))) if name in n.columns else dict.fromkeys(self.ids)

        self.uid, self.cell_type, self.side = col("neuron_uid"), col("cell_type"), col("side")
        self.role, self.manc_body_id, self.manc_type = col("role_class"), col("manc_body_id"), col("manc_type")
        self.nt_a, self.nt_b = col(A_NT_FIELD), col(B_NT_FIELD)
        self.by_type: dict[str, list[int]] = {}
        for i in self.ids:  # ascending ids -> ascending candidate lists
            t = self.cell_type[i]
            if t is not None:
                self.by_type.setdefault(t, []).append(i)
        self.role_counts = Counter(r for r in self.role.values() if r is not None)


def _side_filter(a_side, cands: list[int], b: _Lookup) -> tuple[list[int], str | None]:
    """Keep same-side candidates (and candidates of unknown side); fall back to all when none is same-side."""
    if a_side is None:
        return cands, f"a side unknown; all {len(cands)} candidate(s) of the type listed"
    same = [c for c in cands if b.side[c] == a_side]
    unknown = [c for c in cands if b.side[c] is None]
    if same or unknown:
        kept = sorted(same + unknown)
        return kept, (f"{len(unknown)} candidate(s) with unknown side kept" if unknown else None)
    return cands, f"no same-side candidate; all {len(cands)} candidate(s) of the type listed"


def _resolve_spec(spec: MappingSpec | None, cx_a: Connectome, cx_b: Connectome) -> MappingSpec:
    actual = MappingSpec(cx_a.dataset, cx_a.version, cx_b.dataset, cx_b.version)
    if spec is None:
        return actual
    if spec != actual:
        raise ValueError(f"spec {spec} does not match the connectomes {actual}")
    return spec


def _manifest_record(cx: Connectome) -> dict | None:
    """Committed manifest of the build, with a check that it describes exactly this neurons.parquet."""
    p = paths.manifests_dir() / f"{cx.dataset}_{cx.version}.manifest.json"
    if not p.exists():
        return None
    man = json.loads(p.read_text(encoding="utf-8"))
    expected = ((man.get("processed_outputs") or {}).get("neurons") or {}).get("sha256")
    actual = sha256_file(cx.dir / "neurons.parquet")
    return {"path": paths.relpath_for_record(p), "sha256": sha256_file(p), "matches_build": bool(expected == actual),
            "neurons_parquet_sha256": actual}


# ----------------------------------------------------------------------------- build
def build_mapping(cx_a: Connectome, cx_b: Connectome, *, spec: MappingSpec | None = None) -> tuple[pd.DataFrame, dict]:
    """Map every in-scope A neuron to its B candidates under the documented rules. Returns (table, summary)."""
    spec = _resolve_spec(spec, cx_a, cx_b)
    a, b = _Lookup(cx_a), _Lookup(cx_b)
    b_ids = set(b.ids)

    in_scope = [i for i in a.ids if a.role[i] in VNC_ROLES or a.manc_body_id[i] is not None or a.manc_type[i] is not None]
    out_scope = [i for i in a.ids if not (a.role[i] in VNC_ROLES or a.manc_body_id[i] is not None or a.manc_type[i] is not None)]
    shared_body = Counter(a.manc_body_id[i] for i in in_scope if a.manc_body_id[i] is not None)

    rows: list[dict] = []
    per_a: list[tuple[int, str, str, int]] = []  # (a_id, kind, confidence, ambiguity)

    def emit(a_id: int, b_id: int | None, kind: str, confidence: str, ambiguity: int, notes: list[str],
             shared_role: str | None = None) -> None:
        a_side, a_role, a_nt = a.side[a_id], a.role[a_id], a.nt_a[a_id]
        if b_id is not None:
            b_type, b_side, b_role, b_nt, b_uid = b.cell_type[b_id], b.side[b_id], b.role[b_id], b.nt_b[b_id], b.uid[b_id]
        else:
            b_type, b_side, b_nt, b_uid = None, None, None, None
            b_role = shared_role
        rows.append({
            "a_uid": a.uid[a_id], "b_uid": b_uid, "a_source_id": a_id, "b_source_id": b_id,
            "mapping_kind": kind, "method": _METHOD[kind], "evidence_kind": _EVIDENCE[kind],
            "confidence": confidence, "ambiguity": ambiguity, "b_ambiguity": None,  # filled once all rows exist
            "a_cell_type": a.cell_type[a_id], "b_cell_type": b_type,
            "a_side": a_side, "b_side": b_side, "side_consistent": _consistent(a_side, b_side),
            "a_role_class": a_role, "b_role_class": b_role, "role_consistent": _consistent(a_role, b_role),
            "a_nt": a_nt, "b_nt": b_nt, "nt_consistent": _nt_consistent(a_nt, b_nt),
            "manc_type_consistent": _consistent(a.manc_type[a_id], b_type) if b_id is not None else None,
            "a_type_consistent": _consistent(a.cell_type[a_id], b_type) if b_id is not None else None,
            "notes": "; ".join(n for n in notes if n) or None,
        })

    def emit_candidates(a_id: int, kind: str, cands: list[int], notes: list[str]) -> None:
        kept, side_note = _side_filter(a.side[a_id], cands, b)
        conf = "medium" if len(kept) == 1 and _consistent(a.side[a_id], b.side[kept[0]]) is True else "low"
        for c in kept:
            emit(a_id, c, kind, conf, len(kept), [*notes, side_note])
        per_a.append((a_id, kind, conf, len(kept)))

    for a_id in in_scope:
        notes: list[str] = []
        if a.role[a_id] not in VNC_ROLES:
            notes.append(f"role_class {a.role[a_id]!r} outside the VNC role set; in scope through a curated MANC annotation")
        mbid, mtype, a_type = a.manc_body_id[a_id], a.manc_type[a_id], a.cell_type[a_id]
        # rule 1: curated body match
        if mbid is not None:
            if mbid in b_ids:
                bt = b.cell_type[mbid]
                n1 = "manc_type null" if mtype is None else "b.cell_type null" if bt is None else \
                    f"manc_type {'==' if mtype == bt else '!='} b.cell_type"
                n2 = "a.cell_type null" if a_type is None else "b.cell_type null" if bt is None else \
                    f"a.cell_type {'==' if a_type == bt else '!='} b.cell_type"
                n3 = f"manc_body_id shared by {shared_body[mbid]} A neurons" if shared_body[mbid] > 1 else None
                emit(a_id, mbid, "curated_body_match", "high", 1, [*notes, n1, n2, n3])
                per_a.append((a_id, "curated_body_match", "high", 1))
                continue
            notes.append(f"manc_body_id {mbid} is not a neuron of B")
        # rule 2: curated type match
        if mtype is not None:
            cands = b.by_type.get(mtype)
            if cands:
                emit_candidates(a_id, "curated_type_match", cands, notes)
                continue
            notes.append("manc_type is not a cell type of B")
        # rule 3: same type name
        if a_type is not None:
            cands = b.by_type.get(a_type)
            if cands:
                emit_candidates(a_id, "same_type_name", cands, notes)
                continue
            notes.append("cell_type is not a cell type of B")
        else:
            notes.append("a.cell_type null")
        # rule 4 / 5
        role = a.role[a_id]
        if role is not None and role != "unknown" and b.role_counts.get(role, 0) > 0:
            n_role = b.role_counts[role]
            emit(a_id, None, "same_role_only", "none", n_role, [*notes, f"{n_role} B neurons share the role class"], shared_role=role)
            per_a.append((a_id, "same_role_only", "none", n_role))
        else:
            emit(a_id, None, "unmatched", "none", 0, [*notes, "no B neuron shares a known role class"])
            per_a.append((a_id, "unmatched", "none", 0))

    named = Counter((r["mapping_kind"], r["b_source_id"]) for r in rows if r["b_source_id"] is not None)
    for r in rows:  # B -> A direction: how many A neurons name this candidate under the same rule
        if r["b_source_id"] is not None:
            r["b_ambiguity"] = named[(r["mapping_kind"], r["b_source_id"])]
    table = _to_pandas(_to_arrow(rows))
    summary = _summary(spec, cx_a, cx_b, a, b, in_scope, out_scope, shared_body, rows, per_a)
    return table, summary


def _to_arrow(rows: list[dict]) -> pa.Table:
    arrays = {}
    for c in MAPPING.columns:
        typ = c.type.value_type if pa.types.is_dictionary(c.type) else c.type
        arrays[c.name] = pa.array([r[c.name] for r in rows], type=typ)
    return conform(pa.table(arrays), MAPPING)


def _to_pandas(table: pa.Table) -> pd.DataFrame:
    df = table.to_pandas(types_mapper=_PANDAS_TYPES.get)
    for c in df.columns:
        if isinstance(df[c].dtype, pd.CategoricalDtype) or df[c].dtype == object:
            df[c] = df[c].astype(object).where(df[c].notna(), None)
    return df


def _counts(values) -> dict:
    c = Counter(values)
    return {str(k): int(v) for k, v in sorted(c.items(), key=lambda kv: (-kv[1], str(kv[0])))}


def _agreement(flags: list[bool | None]) -> dict:
    t, f = sum(1 for x in flags if x is True), sum(1 for x in flags if x is False)
    u = len(flags) - t - f
    return {"consistent": t, "inconsistent": f, "unknown": u, "rate": (round(t / (t + f), 4) if t + f else None)}


def _ambiguity_buckets(values: list[int]) -> dict:
    out = {"1": 0, "2": 0, "3-5": 0, ">5": 0}
    for v in values:
        out["1" if v == 1 else "2" if v == 2 else "3-5" if v <= 5 else ">5"] += 1
    return out


def _summary(spec, cx_a, cx_b, a: _Lookup, b: _Lookup, in_scope, out_scope, shared_body, rows, per_a) -> dict:
    body_rows = [r for r in rows if r["mapping_kind"] == "curated_body_match"]
    kinds = {k: sum(1 for _, kind, _, _ in per_a if kind == k) for k in MAPPING_KINDS}
    conf = {c: sum(1 for _, _, cf, _ in per_a if cf == c) for c in CONFIDENCE_LEVELS}
    a_types = {a.cell_type[i] for i in in_scope if a.cell_type[i] is not None}
    a_types_in_b = {t for t in a_types if t in b.by_type}
    b_types = set(b.by_type)
    ann_body = [i for i in in_scope if a.manc_body_id[i] is not None]
    ann_type = [i for i in in_scope if a.manc_type[i] is not None]
    b_ids = set(b.ids)
    b_any = {r["b_source_id"] for r in rows if r["b_source_id"] is not None}
    b_body = Counter(r["b_source_id"] for r in body_rows)
    via_ann = [i for i in in_scope if a.role[i] not in VNC_ROLES]
    contradicted = [r for r in body_rows if r["manc_type_consistent"] is False and r["a_type_consistent"] is False]

    return {
        "mapping_schema_version": MAPPING_SCHEMA_VERSION,
        "rules": {"role_class": ROLE_RULE_ID, "priority": list(MAPPING_KINDS), "a_nt_field": A_NT_FIELD, "b_nt_field": B_NT_FIELD,
                  "caveat": "Two animals: no row asserts identity. curated_* rows restate the A release's cross-dataset "
                            "annotations; same_type_name rows compare curated names only."},
        "a": {"dataset": spec.a_dataset, "version": spec.a_version, "n_neurons": len(a.ids), "n_in_scope": len(in_scope),
              "n_out_of_scope": len(out_scope), "manifest": _manifest_record(cx_a)},
        "b": {"dataset": spec.b_dataset, "version": spec.b_version, "n_neurons": len(b.ids), "n_cell_types": len(b_types),
              "manifest": _manifest_record(cx_b)},
        "scope": {
            "rule": "role_class in vnc_roles OR manc_body_id/manc_type annotated",
            "vnc_roles": sorted(VNC_ROLES),
            "in_scope_by_role_class": _counts(a.role[i] for i in in_scope),
            "in_scope_via_annotation_only": {"n": len(via_ann), "by_role_class": _counts(a.role[i] for i in via_ann)},
            "out_of_scope": {"n": len(out_scope), "by_role_class": _counts(a.role[i] for i in out_scope),
                             "note": "outside MANC volume (brain-only role class, or no VNC role and no curated MANC annotation); "
                                     "counted here, not enumerated as rows"},
        },
        "rows": len(rows),
        "a_neurons_by_mapping_kind": kinds,
        "rows_by_mapping_kind": {k: sum(1 for r in rows if r["mapping_kind"] == k) for k in MAPPING_KINDS},
        "a_neurons_by_confidence": conf,
        "ambiguity_by_mapping_kind": {k: _ambiguity_buckets([amb for _, kind, _, amb in per_a if kind == k])
                                      for k in ("curated_type_match", "same_type_name")},
        "curated_annotations": {
            "a_in_scope_with_manc_body_id": len(ann_body),
            "manc_body_id_is_b_neuron": sum(1 for i in ann_body if a.manc_body_id[i] in b_ids),
            "manc_body_id_not_in_b": sum(1 for i in ann_body if a.manc_body_id[i] not in b_ids),
            "b_bodies_referenced_by_several_a_neurons": sum(1 for v in shared_body.values() if v > 1),
            "a_in_scope_with_manc_type": len(ann_type),
            "a_in_scope_whose_manc_type_is_b_type": sum(1 for i in ann_type if a.manc_type[i] in b.by_type),
        },
        "body_match_consistency": {
            "n": len(body_rows),
            "side": _agreement([r["side_consistent"] for r in body_rows]),
            "role": _agreement([r["role_consistent"] for r in body_rows]),
            "nt": _agreement([r["nt_consistent"] for r in body_rows]),
            "manc_type_equals_b_cell_type": _agreement([r["manc_type_consistent"] for r in body_rows]),
            "a_cell_type_equals_b_cell_type": _agreement([r["a_type_consistent"] for r in body_rows]),
            "both_type_annotations_contradicted_by_snapshot": {
                "n": len(contradicted), "b_role_class": _counts(r["b_role_class"] for r in contradicted),
                "note": "confidence stays 'high' (uniqueness of the curated body match); readers wanting corroborated matches "
                        "filter on manc_type_consistent / a_type_consistent"},
        },
        "type_name_coverage": {
            "a_in_scope_cell_types": len(a_types), "a_cell_types_present_in_b": len(a_types_in_b),
            "a_in_scope_neurons_with_cell_type_present_in_b": sum(1 for i in in_scope if a.cell_type[i] in b.by_type),
            "a_in_scope_neurons_without_cell_type": sum(1 for i in in_scope if a.cell_type[i] is None),
            "b_cell_types": len(b_types), "b_cell_types_present_in_a_in_scope": len(b_types & a_types),
        },
        "b_coverage": {
            "b_neurons": len(b.ids), "b_neurons_in_any_row": len(b_any), "b_neurons_with_body_match": len(b_body),
            "b_neurons_with_several_body_matches": sum(1 for v in b_body.values() if v > 1),
            "b_neurons_without_any_row_by_role_class": _counts(b.role[i] for i in b.ids if i not in b_any),
        },
    }


# ----------------------------------------------------------------------------- I/O
def write_mapping(table: pd.DataFrame, summary: dict, out_dir: Path | None = None) -> dict:
    """Write neuron_mapping.parquet (deterministic) + summary.json under out_dir (default data/processed/mappings/<a>__<b>).

    The table's sha256 is written into the summary; returns records with relative paths and checksums."""
    spec = MappingSpec(summary["a"]["dataset"], summary["a"]["version"], summary["b"]["dataset"], summary["b"]["version"])
    out_dir = Path(out_dir) if out_dir is not None else default_mapping_dir(spec)
    out_dir.mkdir(parents=True, exist_ok=True)
    arrow = conform(pa.Table.from_pandas(table, preserve_index=False), MAPPING)
    rec = write_canonical(arrow, MAPPING, out_dir / TABLE_FILENAME,
                          extra_metadata={"brainir_mapping_schema_version": MAPPING_SCHEMA_VERSION,
                                          "a": f"{spec.a_dataset}:{spec.a_version}", "b": f"{spec.b_dataset}:{spec.b_version}"})
    rec.pop("schema", None)
    summary = {**summary, "table": rec}
    spath = out_dir / SUMMARY_FILENAME
    spath.write_text(json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    return {"out_dir": out_dir, "table": rec, "summary": {"path": paths.relpath_for_record(spath), "sha256": sha256_file(spath)}}


def load_mapping(a: tuple[str, str], b: tuple[str, str], out_dir: Path | None = None) -> pd.DataFrame:
    """Read a written mapping table ((dataset, version) pairs) back as a DataFrame with nullable dtypes."""
    spec = MappingSpec(a[0], a[1], b[0], b[1])
    path = (Path(out_dir) if out_dir is not None else default_mapping_dir(spec)) / TABLE_FILENAME
    return _to_pandas(pq.read_table(path))


def load_summary(a: tuple[str, str], b: tuple[str, str], out_dir: Path | None = None) -> dict:
    spec = MappingSpec(a[0], a[1], b[0], b[1])
    path = (Path(out_dir) if out_dir is not None else default_mapping_dir(spec)) / SUMMARY_FILENAME
    return json.loads(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- lookups
def _ordered(df: pd.DataFrame) -> pd.DataFrame:
    order = {k: i for i, k in enumerate(MAPPING_KINDS)}
    return (df.assign(_k=df["mapping_kind"].map(order)).sort_values(["_k", "a_source_id", "b_source_id"])
            .drop(columns="_k").reset_index(drop=True))


def reverse_lookup(table: pd.DataFrame, b_source_id: int) -> pd.DataFrame:
    """All rows naming a B neuron as candidate (B -> A direction), strongest mapping_kind first.

    The rows are the forward rows: ``confidence``/``ambiguity`` still describe the A neuron's rule; ``b_ambiguity`` is
    the B-side count. An empty result means no in-scope A neuron names this B neuron under any rule (or the id is not a
    B neuron) — there are no B-side 'unmatched' rows."""
    m = table["b_source_id"].eq(int(b_source_id)).fillna(False).to_numpy(bool)
    return _ordered(table[m])


def forward_lookup(table: pd.DataFrame, a_source_id: int) -> pd.DataFrame:
    """All rows of one A neuron (A -> B direction)."""
    m = table["a_source_id"].eq(int(a_source_id)).to_numpy(bool)
    return _ordered(table[m])
