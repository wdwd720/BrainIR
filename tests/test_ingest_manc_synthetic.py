"""End-to-end ingestion of the MANC-shaped fixtures (v1.0 neuPrint export; v1.2.1 / v1.2.3 synapse rebuilds)."""

from __future__ import annotations

import json

import pandas as pd
import pyarrow.parquet as pq
import pytest

from brainir.io import sha256_file
from brainir.testing import synthetic as S
from brainir.testing import synthetic_manc as M


@pytest.fixture(scope="module")
def v10(tmp_path_factory):
    return M.build_synthetic_manc(tmp_path_factory.mktemp("manc10"), "v1.0")


@pytest.fixture(scope="module")
def v121(tmp_path_factory):
    return M.build_synthetic_manc(tmp_path_factory.mktemp("manc121"), "v1.2.1")


@pytest.fixture(scope="module")
def v123(tmp_path_factory):
    return M.build_synthetic_manc(tmp_path_factory.mktemp("manc123"), "v1.2.3")


def _checks(res):
    return {c.check_id: c for c in res["report"].checks}


def _edges(out):
    c = pq.read_table(out / "connections.parquet").to_pandas()
    return {(r.pre_id, r.post_id): (r.synapse_count, r.synapse_count_hp) for r in c.itertuples()}


def _edge_neuropils(out):
    cn = pq.read_table(out / "connection_neuropils.parquet").to_pandas()
    got: dict = {}
    for r in cn.itertuples():
        got.setdefault((r.pre_id, r.post_id), {})[r.neuropil] = r.synapse_count
    return got


# ----------------------------------------------------------------------------- v1.0
def test_v10_validation_status(v10):
    s = v10["report"].summary()
    assert s["fail"] == 0, [c.check_id for c in v10["report"].failures]
    warns = {c.check_id for c in v10["report"].checks if c.status == "warn"}
    # the only expected warning is the deliberately stale ROI hierarchy of the fixture (as in the real v1.0 Meta)
    assert warns == {"referential.primary_rois_in_hierarchy"}, warns


def test_v10_edges_and_neuropils_match_truth_and_hr_only_pairs_are_dropped(v10):
    out = v10["out_dir"]
    assert _edges(out) == S.EXPECTED_EDGES  # low-confidence synapses do not count; (104, 105) never becomes an edge
    assert _edge_neuropils(out) == S.EXPECTED_EDGE_NEUROPILS
    ch = _checks(v10)
    assert ch["rows.connections_zero_weight_dropped"].observed == M.EXPECTED_HR_ONLY_PAIRS
    assert ch["edge_values.weight_hr_ge_weight"].status == "pass"


def test_v10_neurons(v10):
    n = pq.read_table(v10["out_dir"] / "neurons.parquet").to_pandas().set_index("source_id")
    assert n.index.tolist() == S.EXPECTED_NEURONS  # 107 is Traced in neuPrint (RT Orphan in the property export); 900 is not
    assert n.loc[101, "super_class"] == "descending_neuron" and n.loc[104, "super_class"] == "motor_neuron"
    assert n.loc[101, "hemilineage_truman"] == "17A" and pd.isna(n.loc[104, "hemilineage_truman"])  # 'None' placeholder -> null
    assert n.loc[101, "soma_side"] == "R" and n.loc[105, "side"] == "L" and n.loc[105, "side_basis"] == "root"
    assert n.loc[107, "status"] == "Traced" and n.loc[107, "status_label"] == "RT Orphan" and bool(n.loc[107, "is_traced"])
    assert n.loc[101, "nt_body_prediction"] == "acetylcholine" and abs(n.loc[101, "nt_body_confidence"] - 0.90) < 1e-9
    assert n.loc[106, "nt_body_prediction"] == "unknown" and pd.isna(n.loc[107, "nt_body_prediction"])
    assert n["nt_consensus"].isna().all() and n["nt_type_prediction"].isna().all()
    assert {int(i): int(v) for i, v in n["n_pre"].items()} == M.EXPECTED_N_PRE_V10
    got = {int(i): (int(r.n_downstream), int(r.n_upstream), int(r.n_downstream_to_neurons), int(r.n_upstream_from_neurons))
           for i, r in n.iterrows()}
    assert got == S.EXPECTED_TOTALS
    assert set(n["animal_sex"]) == {"male"} and n["neuron_uid"].tolist() == [f"manc:v1.0:{i}" for i in S.EXPECTED_NEURONS]


def test_v10_source_discrepancies_are_recorded(v10):
    ch = _checks(v10)
    remap = ch["cross_source.status_remap_between_exports"].observed
    assert remap == [{"properties_status": "RT Orphan", "neuprint_status": "Traced", "bodies": 1}]
    assert ch["neuropils.roiinfo_parent_aliases"].observed == {"ventral nerve core": "ventral nerve cord"}
    obs = ch["referential.primary_rois_in_hierarchy"].observed
    assert obs["primary_not_in_hierarchy"] == ["LegNp(T1)(L)"] and obs["hierarchy_only"] == ["IntNp(T1)(L)"]
    np_ = pq.read_table(v10["out_dir"] / "neuropils.parquet").to_pandas().set_index("name")
    assert "IntNp(T1)(L)" not in np_.index and not bool(np_.loc["LegNp(T1)(L)", "in_hierarchy"])
    assert set(np_["top_level_region"].dropna()) == {"VNC"} and bool(np_.loc["GNG", "is_nerve"])
    assert ch["cross_source.traced_connections_csv"].status == "pass"
    assert ch["cross_source.traced_connections_per_roi_csv"].status == "pass"


def test_v10_count_rule_is_inferred_from_raw_synapses(v10):
    ch = _checks(v10)
    inf = ch["synapses.inferred_count_rule"]
    assert inf.status == "pass"
    exact = inf.observed["exact_rules"]
    assert {"conf_pre_min": 0.0, "conf_post_min": 0.4} in exact["weight"]
    assert {"conf_pre_min": 0.0, "conf_post_min": 0.7} in exact["weightHP"]
    assert {"conf_pre_min": 0.0, "conf_post_min": 0.0} in exact["weightHR"]
    assert {"conf_pre_min": 0.0, "conf_post_min": 0.3} not in exact["weight"]  # the 0.35 synapse would be counted
    assert inf.observed["chosen"]["conf_post_min"] == 0.4 and inf.observed["chosen"]["hp_conf_post_min"] == 0.7
    assert ch["synapses.count_rule_matches_default"].status == "pass"
    assert ch["synapses.total_pairs_equal_weight_hr"].status == "pass"
    assert ch["synapses.recomputed_neuron_totals"].status == "pass"
    assert ch["synapses.recomputed_edge_neuropils"].status == "pass"
    assert v10["build_info"]["inferred_count_rule"]["exact"]["weight"]


def test_v10_manifest_ready_build_info(v10):
    bi = v10["build_info"]
    assert bi["dataset"] == "manc" and bi["version"] == "v1.0" and bi["definitions"]["neuron"].startswith("body carrying")
    assert bi["schema_version"] == "0.2.0"
    txt = json.dumps(bi)
    assert "C:\\" not in txt and "/Users/" not in txt


# ----------------------------------------------------------------------------- v1.2.x
@pytest.mark.parametrize("which", ["v121", "v123"])
def test_v12_edges_match_truth(which, request):
    res = request.getfixturevalue(which)
    assert res["report"].summary()["fail"] == 0, [c.check_id for c in res["report"].failures]
    assert _edges(res["out_dir"]) == S.EXPECTED_EDGES
    assert _edge_neuropils(res["out_dir"]) == S.EXPECTED_EDGE_NEUROPILS
    ch = _checks(res)
    assert ch["consistency.connection_neuropils_sum_to_weight"].status == "pass"
    assert ch["referential.partner_rois_are_primary"].status == "pass"


def test_v121_neurons_from_snapshot_and_carried_nt(v121):
    n = pq.read_table(v121["out_dir"] / "neurons.parquet").to_pandas().set_index("source_id")
    assert n.index.tolist() == S.EXPECTED_NEURONS
    assert n["neuron_uid"].tolist() == [f"manc:v1.2.1:{i}" for i in S.EXPECTED_NEURONS]
    assert n["status"].isna().all() and n["is_traced"].isna().all() and n["neuprint_neuron_label"].isna().all()
    assert n.loc[101, "super_class"] == "descending_neuron" and n.loc[102, "hemilineage_truman"] == "17A"
    assert n.loc[101, "soma_side"] == "R" and n.loc[105, "root_side"] == "L"
    assert n.loc[101, "nt_body_prediction"] == "acetylcholine"  # carried from v1.0 by body ID
    assert n["nt_type_prediction"].isna().all()                # v1.2.1 snapshot has no NT tags
    assert {int(i): int(v) for i, v in n["n_pre"].items()} == M.EXPECTED_N_PRE_V12
    got = {int(i): (int(r.n_downstream), int(r.n_upstream), int(r.n_downstream_to_neurons), int(r.n_upstream_from_neurons))
           for i, r in n.iterrows()}
    assert got == S.EXPECTED_TOTALS
    assert n.loc[104, "cell_type"] == "MN1"


def test_v123_snapshot_specifics(v123):
    n = pq.read_table(v123["out_dir"] / "neurons.parquet").to_pandas().set_index("source_id")
    assert pd.isna(n.loc[M.EXPECTED_V123_TYPE_PLACEHOLDER, "cell_type"])  # '~' placeholder
    assert n.loc[101, "cell_type"] == "DNtest" and n.loc[101, "instance"].startswith("DNtest_")
    assert n.loc[101, "nt_type_prediction"] == "acetylcholine" and pd.isna(n.loc[106, "nt_type_prediction"])
    assert int(n.loc[101, "group_id"]) == 101
    ch = _checks(v123)
    counts = ch["cross_source.snapshot_synapse_counts"].observed
    assert counts["syn_post == PSDs (rule)"]["fraction"] == 1.0 and counts["syn_downstream == downstream (rule)"]["fraction"] == 1.0
    assert ch["cross_source.snapshot_duplicate_property.type"].status == "pass"
    bi = v123["build_info"]
    assert bi["version"] == "v1.2.3" and bi["source_version"] == "v1.2" and bi["count_rule"]["conf_post_min"] == 0.4
    assert bi["annotation_snapshot"]["neuprint_dataset"] == "manc:v1.2.3"


def test_v12_neuropil_totals_and_definitions(v123):
    np_ = pq.read_table(v123["out_dir"] / "neuropils.parquet").to_pandas().set_index("name")
    assert np_["n_pre_total"].isna().all()
    assert int(np_.loc["LegNp(T1)(L)", "n_post_total"]) == sum(
        1 for s in M._all_synapses() if M._counted(s) and S.primary_of(s["proi"]) == "LegNp(T1)(L)")
    assert "APPROXIMATION" in v123["build_info"]["definitions"]["neuron_neuropils.n_pre"]


def test_v12_rebuild_is_byte_identical(tmp_path):
    a = M.build_synthetic_manc(tmp_path / "a", "v1.2.3")
    b = M.build_synthetic_manc(tmp_path / "b", "v1.2.3")
    for t in ("neurons", "connections", "connection_neuropils", "neuron_neuropils", "neuropils", "neuron_annotations_source"):
        assert sha256_file(a["out_dir"] / f"{t}.parquet") == sha256_file(b["out_dir"] / f"{t}.parquet"), t


def test_graph_layer_reads_manc_builds(v10, v123):
    from brainir.graph import Connectome

    for res, ver in ((v10, "v1.0"), (v123, "v1.2.3")):
        cx = Connectome(res["out_dir"])
        assert cx.dataset == "manc" and cx.version == ver and cx.n_edges == len(S.EXPECTED_EDGES)
        assert cx.neurons.loc[101, "role_class"] == "descending" and cx.neurons.loc[104, "role_class"] == "vnc_motor"
        h = cx.sign_hypothesis(101)
        assert h.sign == 1 and h.based_on_field == ("nt_body_prediction" if ver == "v1.0" else "nt_type_prediction")
        assert cx.sign_hypothesis(106) is not None and cx.sign_hypothesis(106).sign is None  # 'unknown' -> no sign
        m = cx.neuron_model(107)
        assert m.is_traced == (True if ver == "v1.0" else None) and m.role_class == "vnc_intrinsic"  # MANC class 'intrinsic neuron'
        assert cx.connection_model(101, 102).synapse_count == 6
