"""Cross-connectome mapping on the MaleCNS and MANC synthetic fixtures (the same seven neurons in both formats).

The MaleCNS fixture annotates ``mancBodyid = bodyId + 10000`` and ``mancType = type``, so no curated body ID exists in the
MANC fixture and the curated-type rule must take over; stripping the annotations in memory exercises the type-name,
role-only and unmatched fall-backs plus the side handling.
"""

from __future__ import annotations

import json
import shutil

import pandas as pd
import pytest

from brainir import cli
from brainir.graph import Connectome
from brainir.io import sha256_file
from brainir.mapping import (
    CONFIDENCE_LEVELS,
    MAPPING,
    MAPPING_KINDS,
    MAPPING_SCHEMA_VERSION,
    VNC_ROLES,
    MappingSpec,
    build_mapping,
    forward_lookup,
    load_mapping,
    load_summary,
    reverse_lookup,
    write_mapping,
)
from brainir.schema.evidence import EvidenceKind
from brainir.testing.synthetic_manc import build_synthetic_manc

FIXTURE_IDS = [101, 102, 103, 104, 105, 106, 107]  # 107 (CBx) is cb_intrinsic in MaleCNS, intrinsic in MANC


@pytest.fixture(scope="module")
def manc_build(tmp_path_factory) -> dict:
    return build_synthetic_manc(tmp_path_factory.mktemp("manc_map"), "v1.2.1")


@pytest.fixture(scope="module")
def mapped(synthetic_out, manc_build):
    return build_mapping(Connectome(synthetic_out), Connectome(manc_build["out_dir"]))


@pytest.fixture()
def fresh(synthetic_out, manc_build):
    """Fresh in-memory connectomes for tests that mutate annotation columns."""
    return Connectome(synthetic_out), Connectome(manc_build["out_dir"])


def _strip_curated_manc_annotations(cx_a: Connectome) -> None:
    cx_a.neurons["manc_body_id"] = pd.array([None] * len(cx_a.neurons), dtype="Int64")
    cx_a.neurons["manc_type"] = None


# ----------------------------------------------------------------------------- schema
def test_columns_vocabulary_and_uids(mapped):
    table, summary = mapped
    assert list(table.columns) == MAPPING.column_names
    assert set(table.mapping_kind) <= set(MAPPING_KINDS)
    assert set(table.evidence_kind) <= {str(e) for e in EvidenceKind}
    assert set(table.confidence) <= set(CONFIDENCE_LEVELS)
    for c in ("a_uid", "a_source_id", "mapping_kind", "method", "evidence_kind", "confidence", "ambiguity"):
        assert table[c].notna().all(), c
    assert table.a_uid.str.startswith("male-cns:v1.0:").all() and table.b_uid.str.startswith("manc:v1.2.1:").all()
    assert table.a_source_id.dtype.name == "Int64" and table.b_source_id.dtype.name == "Int64" and table.ambiguity.dtype.name == "Int32"
    assert table.a_source_id.is_monotonic_increasing
    assert summary["mapping_schema_version"] == MAPPING_SCHEMA_VERSION
    assert VNC_ROLES == {"descending", "ascending", "sensory_ascending", "sensory_descending", "efferent",
                         "vnc_intrinsic", "vnc_motor", "vnc_sensory", "vnc_unknown"}
    for c in ("manc_type_consistent", "a_type_consistent", "b_ambiguity"):
        assert c in table.columns


def test_summary_keys(mapped):
    _, s = mapped
    assert set(s) >= {"mapping_schema_version", "rules", "a", "b", "scope", "rows", "a_neurons_by_mapping_kind", "rows_by_mapping_kind",
                      "a_neurons_by_confidence", "ambiguity_by_mapping_kind", "curated_annotations", "body_match_consistency",
                      "type_name_coverage", "b_coverage"}
    assert s["a"] == {**s["a"], "dataset": "male-cns", "version": "v1.0", "n_neurons": 7}
    assert s["b"] == {**s["b"], "dataset": "manc", "version": "v1.2.1", "n_neurons": 7}
    assert set(s["a_neurons_by_mapping_kind"]) == set(MAPPING_KINDS) and set(s["a_neurons_by_confidence"]) == set(CONFIDENCE_LEVELS)
    assert set(s["body_match_consistency"]) == {"n", "side", "role", "nt", "manc_type_equals_b_cell_type", "a_cell_type_equals_b_cell_type",
                                                "both_type_annotations_contradicted_by_snapshot"}
    assert s["rules"]["a_nt_field"] == "nt_consensus" and s["rules"]["b_nt_field"] == "nt_body_prediction"
    # the committed real-data manifests exist but do not describe the fixture build: recorded, flagged, never claimed
    for side in ("a", "b"):
        assert s[side]["manifest"] is None or s[side]["manifest"]["matches_build"] is False


# ----------------------------------------------------------------------------- rules
def test_offset_body_ids_never_match_and_curated_type_rule_takes_over(mapped):
    table, s = mapped
    assert len(table) == 7 and sorted(table.a_source_id) == FIXTURE_IDS
    assert set(table.mapping_kind) == {"curated_type_match"}  # 10101..10107 are not MANC fixture bodies
    assert (table.ambiguity == 1).all() and set(table.confidence) == {"medium"}
    assert (table.b_source_id == table.a_source_id).all()  # both fixtures number the same neurons alike
    assert table.side_consistent.all() and set(table.evidence_kind) == {"curated_annotation"}
    assert set(table.method) == {"a.manc_type == b.cell_type; side filter"}
    for r in table.itertuples():
        assert f"manc_body_id {r.a_source_id + 10000} is not a neuron of B" in r.notes
    by_id = table.set_index("a_source_id")
    assert by_id.role_consistent.to_dict() == {101: True, 102: True, 103: True, 104: True, 105: True, 106: True, 107: False}
    assert "outside the VNC role set; in scope through a curated MANC annotation" in by_id.loc[107, "notes"]
    # NT comparability: both concrete classes -> bool; null / 'unclear' / 'unknown' -> null
    nt = {k: (None if pd.isna(v) else bool(v)) for k, v in by_id.nt_consistent.to_dict().items()}
    assert nt == {101: True, 102: True, 103: True, 104: None, 105: True, 106: None, 107: None}
    assert by_id.loc[106, ["a_nt", "b_nt"]].tolist() == ["unclear", "unknown"]
    assert s["a"]["n_in_scope"] == 7 and s["scope"]["out_of_scope"]["n"] == 0
    assert s["scope"]["in_scope_via_annotation_only"] == {"n": 1, "by_role_class": {"cb_intrinsic": 1}}
    assert s["curated_annotations"]["manc_body_id_not_in_b"] == 7 and s["curated_annotations"]["manc_body_id_is_b_neuron"] == 0
    assert s["a_neurons_by_mapping_kind"]["curated_type_match"] == 7 and s["a_neurons_by_confidence"]["medium"] == 7
    assert s["body_match_consistency"]["n"] == 0 and s["body_match_consistency"]["side"]["rate"] is None
    assert s["type_name_coverage"]["a_cell_types_present_in_b"] == 7 and s["b_coverage"]["b_neurons_in_any_row"] == 7


def test_curated_body_match_when_the_annotated_body_exists(fresh):
    cx_a, cx_b = fresh
    # point 101's curated body annotation at a body that exists in B (a different type on purpose: 103 INb)
    cx_a.neurons.loc[101, "manc_body_id"] = 103
    table, s = build_mapping(cx_a, cx_b)
    r = table.set_index("a_source_id").loc[101]
    assert r.mapping_kind == "curated_body_match" and r.confidence == "high" and r.ambiguity == 1 and r.b_source_id == 103
    assert r.evidence_kind == "curated_annotation" and r.method == "a.manc_body_id == b.source_id"
    assert r.side_consistent is True or bool(r.side_consistent)  # 101 R, 103 R
    assert "manc_type != b.cell_type" in r.notes and "a.cell_type != b.cell_type" in r.notes
    assert s["body_match_consistency"]["n"] == 1 and s["body_match_consistency"]["side"] == {"consistent": 1, "inconsistent": 0, "unknown": 0, "rate": 1.0}
    assert s["body_match_consistency"]["manc_type_equals_b_cell_type"]["inconsistent"] == 1
    assert s["b_coverage"]["b_neurons_with_body_match"] == 1
    # two A neurons pointing at one B body is recorded on both rows, never collapsed
    cx_a.neurons.loc[102, "manc_body_id"] = 103
    table, s = build_mapping(cx_a, cx_b)
    shared = table[(table.b_source_id == 103) & (table.mapping_kind == "curated_body_match")]
    assert sorted(shared.a_source_id) == [101, 102] and shared.notes.str.contains("manc_body_id shared by 2 A neurons").all()
    assert s["curated_annotations"]["b_bodies_referenced_by_several_a_neurons"] == 1
    assert s["b_coverage"]["b_neurons_with_several_body_matches"] == 1
    assert sorted(reverse_lookup(table, 103).a_source_id) == [101, 102, 103]  # + 103's own curated-type row


def test_type_name_fallback_side_handling_role_only_and_unmatched(fresh):
    cx_a, cx_b = fresh
    _strip_curated_manc_annotations(cx_a)
    cx_a.neurons.loc[103, "cell_type"] = "INa"                  # R neuron; the only INa in B (102) is L
    cx_b.neurons.loc[104, "side"] = None                        # candidate of unknown side
    cx_a.neurons.loc[105, "cell_type"] = "NOPE"                 # no such type in B -> role only (vnc_sensory)
    cx_a.neurons.loc[106, "cell_type"] = "NOPE2"
    cx_a.neurons.loc[106, "role_class"] = "sensory_descending"  # VNC role absent from B -> unmatched
    table, s = build_mapping(cx_a, cx_b)

    assert 107 not in set(table.a_source_id)  # cb_intrinsic without annotation: outside the VNC volume
    assert s["scope"]["out_of_scope"] == {**s["scope"]["out_of_scope"], "n": 1, "by_role_class": {"cb_intrinsic": 1}}
    assert s["a"]["n_in_scope"] == 6 and s["scope"]["in_scope_via_annotation_only"]["n"] == 0
    by_id = table.set_index("a_source_id")

    for i in (101, 102):  # clean same-type, same-side matches
        r = by_id.loc[i]
        assert (r.mapping_kind, r.confidence, r.ambiguity, r.b_source_id) == ("same_type_name", "medium", 1, i)
        assert r.evidence_kind == "derived_anatomy" and r.method == "a.cell_type == b.cell_type; side filter"
    r = by_id.loc[103]  # no same-side candidate: all candidates listed, low confidence, flagged
    assert (r.mapping_kind, r.confidence, r.ambiguity, r.b_source_id, r.side_consistent) == ("same_type_name", "low", 1, 102, False)
    assert "no same-side candidate; all 1 candidate(s) of the type listed" in r.notes
    r = by_id.loc[104]  # candidate with unknown side is kept but cannot be called same-side
    assert (r.mapping_kind, r.confidence, r.ambiguity, r.b_source_id) == ("same_type_name", "low", 1, 104)
    assert pd.isna(r.side_consistent) and "1 candidate(s) with unknown side kept" in r.notes
    r = by_id.loc[105]
    assert (r.mapping_kind, r.confidence, r.ambiguity) == ("same_role_only", "none", 1)  # one vnc_sensory neuron in B
    assert pd.isna(r.b_source_id) and pd.isna(r.b_uid) and r.b_role_class == "vnc_sensory" and bool(r.role_consistent)
    assert "cell_type is not a cell type of B" in r.notes and "1 B neurons share the role class" in r.notes
    r = by_id.loc[106]
    assert (r.mapping_kind, r.confidence, r.ambiguity) == ("unmatched", "none", 0)
    assert pd.isna(r.b_source_id) and pd.isna(r.b_role_class) and "no B neuron shares a known role class" in r.notes

    assert s["a_neurons_by_mapping_kind"] == {"curated_body_match": 0, "curated_type_match": 0, "same_type_name": 4,
                                              "same_role_only": 1, "unmatched": 1}
    assert s["a_neurons_by_confidence"] == {"high": 0, "medium": 2, "low": 2, "none": 2}
    assert s["ambiguity_by_mapping_kind"]["same_type_name"] == {"1": 4, "2": 0, "3-5": 0, ">5": 0}
    assert s["type_name_coverage"]["a_in_scope_neurons_with_cell_type_present_in_b"] == 4
    assert s["b_coverage"]["b_neurons_without_any_row_by_role_class"] == {"vnc_intrinsic": 2, "ascending": 1, "vnc_sensory": 1}

    # reverse direction: B neuron 102 is named by A 102 (same side) and A 103 (opposite side)
    rev = reverse_lookup(table, 102)
    assert rev.a_source_id.tolist() == [102, 103] and rev.side_consistent.tolist() == [True, False]
    assert reverse_lookup(table, 999).empty
    assert forward_lookup(table, 105).mapping_kind.tolist() == ["same_role_only"]


def test_ambiguous_type_matches_unknown_a_side_and_b_ambiguity(fresh):
    """Two B neurons of one type (one of unknown side) -> ambiguity 2 / low; an A neuron without side lists every candidate;
    b_ambiguity counts the A neurons naming each B candidate under the same rule; the consistency columns are structured."""
    cx_a, cx_b = fresh
    _strip_curated_manc_annotations(cx_a)
    cx_b.neurons.loc[103, "cell_type"] = "INa"                   # B now has two INa: 102 (L) and 103 (R)
    cx_a.neurons.loc[101, "cell_type"] = "INa"                    # A 101 and A 102 both look for INa
    cx_a.neurons.loc[101, "side"] = None                          # A side unknown -> all candidates listed
    cx_b.neurons.loc[103, "side"] = None                          # one candidate of unknown side
    table, s = build_mapping(cx_a, cx_b)
    by_a = table.set_index(["a_source_id", "b_source_id"])
    r101 = table[table.a_source_id == 101]
    assert sorted(r101.b_source_id.astype(int)) == [102, 103] and set(r101.confidence) == {"low"} and set(r101.ambiguity) == {2}
    assert "a side unknown" in r101.notes.iloc[0]
    r102 = table[table.a_source_id == 102]  # A 102 (L): same-side 102 + unknown-side 103 kept -> 2 candidates, low
    assert sorted(r102.b_source_id.astype(int)) == [102, 103] and set(r102.confidence) == {"low"}
    assert s["ambiguity_by_mapping_kind"]["same_type_name"]["2"] == 2
    # B 102 is named by A 101 and A 102 under same_type_name -> b_ambiguity 2 on both rows
    assert int(by_a.loc[(101, 102), "b_ambiguity"]) == 2 and int(by_a.loc[(102, 102), "b_ambiguity"]) == 2
    assert table.loc[table.mapping_kind == "same_role_only", "b_ambiguity"].isna().all()
    # structured type-consistency flags (no curated manc_type here -> null; a_type_consistent true for verbatim matches)
    assert table.loc[table.b_source_id.notna(), "manc_type_consistent"].isna().all()
    assert bool(by_a.loc[(101, 102), "a_type_consistent"]) and bool(by_a.loc[(102, 103), "a_type_consistent"])
    rev = reverse_lookup(table, 102)
    assert sorted(rev.a_source_id.astype(int)) == [101, 102]


def test_build_is_deterministic(fresh):
    cx_a, cx_b = fresh
    t1, s1 = build_mapping(cx_a, cx_b)
    t2, s2 = build_mapping(cx_a, cx_b)
    assert t1.equals(t2)
    assert {k: v for k, v in s1.items() if k not in ("a", "b")} == {k: v for k, v in s2.items() if k not in ("a", "b")}


def test_curated_body_match_type_consistency_columns(fresh):
    cx_a, cx_b = fresh
    cx_a.neurons["manc_body_id"] = pd.array(cx_a.neurons.index.to_numpy(), dtype="Int64")  # annotate every body as itself
    cx_a.neurons.loc[101, "manc_type"] = "WRONG"                                            # annotation contradicted by the snapshot
    table, s = build_mapping(cx_a, cx_b)
    body = table[table.mapping_kind == "curated_body_match"].set_index("a_source_id")
    assert body.loc[101, "confidence"] == "high" and body.loc[101, "manc_type_consistent"] is False or body.loc[101, "manc_type_consistent"] == False  # noqa: E712
    assert s["body_match_consistency"]["manc_type_equals_b_cell_type"]["inconsistent"] >= 1
    assert "both_type_annotations_contradicted_by_snapshot" in s["body_match_consistency"]


def test_a_neuron_without_type_or_role_candidate(fresh):
    cx_a, cx_b = fresh
    _strip_curated_manc_annotations(cx_a)
    cx_a.neurons.loc[104, "cell_type"] = None
    table, _ = build_mapping(cx_a, cx_b)
    r = table.set_index("a_source_id").loc[104]
    assert r.mapping_kind == "same_role_only" and "a.cell_type null" in r.notes and r.ambiguity == 1  # one vnc_motor in B


def test_spec_parsing_and_mismatch(fresh):
    cx_a, cx_b = fresh
    spec = MappingSpec.parse("male-cns:v1.0", "manc:v1.2.1")
    assert spec == MappingSpec() and spec.dir_name == "male-cns_v1.0__manc_v1.2.1"
    with pytest.raises(ValueError):
        MappingSpec.parse("male-cns", "manc:v1.2.1")
    with pytest.raises(ValueError):
        build_mapping(cx_a, cx_b, spec=MappingSpec(b_version="v1.2.3"))
    assert build_mapping(cx_a, cx_b, spec=spec)[1]["b"]["version"] == "v1.2.1"


# ----------------------------------------------------------------------------- I/O
def test_write_is_deterministic_and_round_trips(mapped, tmp_path):
    table, summary = mapped
    r1 = write_mapping(table, summary, tmp_path / "one")
    r2 = write_mapping(table, summary, tmp_path / "two")
    assert r1["table"]["sha256"] == r2["table"]["sha256"] == sha256_file(tmp_path / "one" / "neuron_mapping.parquet")
    assert r1["summary"]["sha256"] == r2["summary"]["sha256"]
    assert r1["table"]["path"] == "$EXTERNAL/neuron_mapping.parquet"  # never an absolute path
    back = load_mapping(("male-cns", "v1.0"), ("manc", "v1.2.1"), out_dir=tmp_path / "one")
    assert list(back.columns) == MAPPING.column_names and back.equals(table)
    s = load_summary(("male-cns", "v1.0"), ("manc", "v1.2.1"), out_dir=tmp_path / "one")
    assert s["table"]["sha256"] == r1["table"]["sha256"] and s["table"]["rows"] == 7 and "schema" not in s["table"]
    assert s["rows"] == 7 and s["a"]["version"] == "v1.0"
    assert (tmp_path / "one" / "summary.json").read_bytes().count(b"\r") == 0


def test_default_location_under_data_root(mapped, tmp_path, monkeypatch):
    monkeypatch.setenv("BRAINIR_DATA_DIR", str(tmp_path))
    table, summary = mapped
    rec = write_mapping(table, summary)
    assert rec["out_dir"] == tmp_path / "processed" / "mappings" / "male-cns_v1.0__manc_v1.2.1"
    assert rec["table"]["path"] == "$DATA/processed/mappings/male-cns_v1.0__manc_v1.2.1/neuron_mapping.parquet"
    assert load_mapping(("male-cns", "v1.0"), ("manc", "v1.2.1")).equals(table)


# ----------------------------------------------------------------------------- CLI
def test_cli_build_and_lookup(monkeypatch, capsys, tmp_path, synthetic_out, manc_build):
    shutil.copytree(synthetic_out, tmp_path / "processed" / "male-cns" / "v1.0")
    shutil.copytree(manc_build["out_dir"], tmp_path / "processed" / "manc" / "v1.2.1")
    monkeypatch.setenv("BRAINIR_DATA_DIR", str(tmp_path))
    assert cli.main(["mapping", "build", "--a", "male-cns:v1.0", "--b", "manc:v1.2.1", "--no-manifest"]) == 0
    out = capsys.readouterr().out
    assert "7 rows" in out and '"curated_type_match": 7' in out and "summary copy" not in out
    mdir = tmp_path / "processed" / "mappings" / "male-cns_v1.0__manc_v1.2.1"
    assert (mdir / "neuron_mapping.parquet").exists() and json.loads((mdir / "summary.json").read_text())["rows"] == 7
    assert cli.main(["mapping", "lookup", "--b-id", "102", "--json"]) == 0
    rows = json.loads(capsys.readouterr().out)
    assert [(r["a_uid"], r["mapping_kind"], r["confidence"], r["evidence_kind"]) for r in rows] == \
        [("male-cns:v1.0:102", "curated_type_match", "medium", "curated_annotation")]
    assert cli.main(["mapping", "lookup", "--a-id", "107"]) == 0
    assert "cb_intrinsic" in capsys.readouterr().out
