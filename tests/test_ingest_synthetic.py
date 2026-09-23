"""End-to-end ingestion of the synthetic MaleCNS-shaped fixture against hand-derived truth."""

from __future__ import annotations

import json

import pyarrow.parquet as pq
import pytest

from brainir.schema.tables import CANONICAL_TABLES
from brainir.testing import synthetic as S


def test_clean_fixture_has_no_failures_or_warnings(synthetic_build):
    s = synthetic_build["report"].summary()
    assert s["fail"] == 0, [c.check_id for c in synthetic_build["report"].failures]
    assert s["warn"] == 0
    assert s["pass"] >= 40


def test_neuron_set_is_superclass_bodies_only(synthetic_out):
    n = pq.read_table(synthetic_out / "neurons.parquet").to_pandas()
    assert n["source_id"].tolist() == S.EXPECTED_NEURONS  # fragments 900/901 and glia 950 excluded
    assert n["neuron_uid"].tolist() == [f"male-cns:v1.0:{i}" for i in S.EXPECTED_NEURONS]
    assert set(n["animal_sex"]) == {"male"}


def test_edges_match_hand_derived_truth(synthetic_out):
    c = pq.read_table(synthetic_out / "connections.parquet").to_pandas()
    got = {(r.pre_id, r.post_id): (r.synapse_count, r.synapse_count_hp) for r in c.itertuples()}
    assert got == S.EXPECTED_EDGES


def test_edge_neuropils_match_and_sum_to_counts(synthetic_out):
    cn = pq.read_table(synthetic_out / "connection_neuropils.parquet").to_pandas()
    got: dict = {}
    for r in cn.itertuples():
        got.setdefault((r.pre_id, r.post_id), {})[r.neuropil] = r.synapse_count
    assert got == S.EXPECTED_EDGE_NEUROPILS
    for k, v in got.items():
        assert sum(v.values()) == S.EXPECTED_EDGES[k][0]


def test_neuron_totals_all_partners_vs_neuron_partners(synthetic_out):
    n = pq.read_table(synthetic_out / "neurons.parquet").to_pandas()
    got = {r.source_id: (r.n_downstream, r.n_upstream, r.n_downstream_to_neurons, r.n_upstream_from_neurons)
           for r in n.itertuples()}
    assert got == S.EXPECTED_TOTALS


def test_autapse_is_kept_and_flagged(synthetic_out):
    c = pq.read_table(synthetic_out / "connections.parquet").to_pandas()
    aut = c[c.is_autapse]
    assert aut[["pre_id", "post_id", "synapse_count"]].values.tolist() == [[102, 102, 1]]
    assert (c.is_autapse == (c.pre_id == c.post_id)).all()


def test_derived_edge_columns(synthetic_out):
    c = pq.read_table(synthetic_out / "connections.parquet").to_pandas().set_index(["pre_id", "post_id"])
    r = c.loc[(101, 102)]
    assert r.dominant_neuropil == "LegNp(T1)(L)" and r.n_neuropils == 2
    assert abs(r.dominant_neuropil_fraction - 4 / 6) < 1e-6


def test_neuron_annotations_mapped(synthetic_out):
    n = pq.read_table(synthetic_out / "neurons.parquet").to_pandas().set_index("source_id")
    assert n.loc[101, "hemilineage_truman"] == "17A" and n.loc[101, "hemilineage_ito_lee"] == "SMPpv2"
    assert n.loc[105, "side"] == "L" and n.loc[105, "side_basis"] == "root"
    assert n.loc[101, "side_basis"] == "soma"
    assert n.loc[104, "nt_consensus"] is None or n.loc[104, "nt_consensus"] != n.loc[104, "nt_consensus"]
    assert n.loc[103, "nt_literature_label"] == "glutamate"
    assert bool(n.loc[107, "is_traced"]) is False and n.loc[107, "status"] == "Anchor"
    assert int(n.loc[101, "group_id"]) == 101 and int(n.loc[101, "manc_body_id"]) == 10101
    assert (int(n.loc[101, "soma_x"]), int(n.loc[101, "soma_y"]), int(n.loc[101, "soma_z"])) == (100, 100, 10)


def test_neuron_neuropils_include_unassigned_remainder(synthetic_out):
    nn = pq.read_table(synthetic_out / "neuron_neuropils.parquet").to_pandas()
    d = nn[nn.source_id == 102].set_index("neuropil")
    # 102 receives 2 PSDs outside primary ROIs (from 101's second T-bar)
    assert int(d.loc["<unassigned>", "n_post"]) == 2
    n = pq.read_table(synthetic_out / "neurons.parquet").to_pandas().set_index("source_id")
    assert int(nn[nn.source_id == 102].n_post.sum()) == int(n.loc[102, "n_post"])


@pytest.mark.parametrize("name", sorted(CANONICAL_TABLES))
def test_outputs_conform_to_canonical_schema(synthetic_out, name):
    p = synthetic_out / f"{name}.parquet"
    if name == "synapses":
        assert not p.exists()  # synapse subsets are produced on demand, not by the core build
        return
    sch = pq.read_schema(p)
    assert sch.remove_metadata().equals(CANONICAL_TABLES[name].schema.remove_metadata())


def test_neuropils_hierarchy(synthetic_out):
    t = pq.read_table(synthetic_out / "neuropils.parquet").to_pandas().set_index("name")
    assert t.loc["SMP-sub(R)", "top_level_region"] == "CentralBrain"
    assert t.loc["LegNp(T1)(L)", "top_level_region"] == "VNC" and t.loc["LegNp(T1)(L)", "side"] == "L"
    assert bool(t.loc["SMP(R)", "is_primary"]) and not bool(t.loc["SMP-sub(R)", "is_primary"])
    # DAG: two parents merged into one row; authoritative parent from roiInfo; minimum depth
    assert list(t.loc["SMP-sub(R)", "all_parents"]) == ["CentralBrain", "SMP(R)"]
    assert t.loc["SMP-sub(R)", "parent"] == "SMP(R)" and int(t.loc["SMP-sub(R)", "depth"]) == 2
    assert not bool(t.loc["AL-unspecified(L)", "in_hierarchy"]) and bool(t.loc["GNG", "in_hierarchy"])
    assert t.index.is_unique


def test_report_and_build_info_written(synthetic_out):
    rep = json.loads((synthetic_out / "validation_report.json").read_text())
    cats = {c["category"] for c in rep["checks"]}
    for needed in ("ids", "uniqueness", "duplicates", "referential", "edge_values", "types", "coverage",
                   "directionality", "graph_stats", "provenance", "cross_source", "synapses", "autapses"):
        assert needed in cats, needed
    md = (synthetic_out / "validation_report.md").read_text()
    assert md.startswith("# BrainIR ingestion validation")
    info = json.loads((synthetic_out / "build_info.json").read_text())
    assert info["graph_statistics"]["n_edges"] == len(S.EXPECTED_EDGES)
    for rec in info["outputs"].values():
        assert len(rec["sha256"]) == 64 and rec["rows"] >= 0
        assert not rec["path"].startswith(("C:", "/"))  # never absolute paths in provenance
