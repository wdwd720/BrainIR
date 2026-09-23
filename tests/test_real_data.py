"""Integration smoke tests against the real processed builds (MaleCNS v1.0; MANC v1.0 / v1.2.1 / v1.2.3).

Skipped automatically when a build is absent (fresh clone without data). Rebuild with
``uv run brainir acquire ... && uv run brainir ingest --dataset <ds> --version <ver>``.
"""

from __future__ import annotations

import json

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.dataset as pads
import pytest

from brainir import paths
from brainir.sources.registry import MALECNS_V1_0, MANC_V1_0, MANC_V1_2

pytestmark = [pytest.mark.real_data]

BUILDS = [("male-cns", "v1.0"), ("manc", "v1.0"), ("manc", "v1.2.1"), ("manc", "v1.2.3")]
EXPECTED_SIZES = {  # (min neurons, max neurons, min edges, max edges)
    ("male-cns", "v1.0"): (166_000, 167_500, 24_000_000, 27_500_000),
    ("manc", "v1.0"): (23_000, 24_000, 5_000_000, 5_600_000),
    ("manc", "v1.2.1"): (23_500, 24_500, 5_000_000, 5_600_000),
    ("manc", "v1.2.3"): (23_000, 24_000, 5_000_000, 5_600_000),
}


def _built(ds, ver):
    return (paths.processed_dir(ds, ver) / "connections.parquet").exists()


def _skip_unless_built(ds, ver):
    if not _built(ds, ver):
        pytest.skip(f"real {ds}:{ver} build not present")


def _open(ds, ver):
    from brainir.graph import Connectome
    return Connectome.open(ds, ver)


@pytest.mark.parametrize("ds,ver", BUILDS)
def test_build_passed_validation(ds, ver):
    _skip_unless_built(ds, ver)
    rep = json.loads((paths.processed_dir(ds, ver) / "validation_report.json").read_text())
    assert rep["summary"]["fail"] == 0, [c["check_id"] for c in rep["checks"] if c["status"] == "fail"]


@pytest.mark.parametrize("ds,ver", BUILDS)
def test_sizes_are_plausible(ds, ver):
    _skip_unless_built(ds, ver)
    cx = _open(ds, ver)
    lo_n, hi_n, lo_e, hi_e = EXPECTED_SIZES[(ds, ver)]
    assert lo_n < cx.n_neurons < hi_n
    assert lo_e < cx.n_edges < hi_e
    assert cx.ids.dtype == np.int64 and len(np.unique(cx.ids)) == len(cx.ids)
    assert (cx.neurons["neuron_uid"] == f"{ds}:{ver}:" + cx.neurons["source_id"].astype(str)).all()


@pytest.mark.parametrize("ds,ver", BUILDS)
def test_dng100_is_locatable(ds, ver):
    """DNg100 is the benchmark's STIMULUS, not its answer; it must be findable in every dataset."""
    _skip_unless_built(ds, ver)
    cx = _open(ds, ver)
    ids = cx.ids_of_type("DNg100")
    if ds == "manc" and ver == "v1.0":
        # v1.0 predates the DNg100 name (the two bodies are typed with the older DNxl nomenclature); locate them through
        # the v1.2.1 build, which shares the segmentation lineage
        _skip_unless_built("manc", "v1.2.1")
        assert len(ids) == 0
        ids = _open("manc", "v1.2.1").ids_of_type("DNg100")
        assert len(ids) == 2 and all(cx.has(int(i)) for i in ids)
        assert len(set(cx.neurons.loc[ids, "cell_type"])) == 1  # both bodies share one (older) type name
    assert len(ids) == 2, ids
    for i in ids:
        n = cx.neuron(int(i))
        assert n["role_class"] == "descending"
        h = cx.sign_hypothesis(int(i))
        assert h is not None and h.sign == 1  # cholinergic in every dataset
        assert len(cx.downstream(int(i), min_count=5)) > 100


def test_malecns_sampled_edges_match_raw_official_connection_table():
    _skip_unless_built("male-cns", "v1.0")
    cx = _open("male-cns", "v1.0")
    rng = np.random.default_rng(7)
    idx = rng.choice(cx.n_edges, size=200, replace=False)
    pre, post, w = cx._pre[idx], cx._post[idx], cx._w[idx]
    raw = paths.raw_dir("male-cns", "v1.0") / MALECNS_V1_0.local_relpath(MALECNS_V1_0.file("neuprint_connections"))
    con = duckdb.connect()
    con.register("s", pa.table({"pre": pre, "post": post}))
    con.register("c", pads.dataset(str(raw), format="ipc"))
    got = con.execute('''SELECT c.":START_ID(Body-ID)" AS pre, c.":END_ID(Body-ID)" AS post, c."weight:int" AS w
                         FROM c SEMI JOIN s ON c.":START_ID(Body-ID)" = s.pre AND c.":END_ID(Body-ID)" = s.post''').fetchdf()
    ref = {(int(a), int(b)): int(x) for a, b, x in zip(got.pre, got.post, got.w)}
    for a, b, x in zip(pre, post, w):
        assert ref[(int(a), int(b))] == int(x)


def test_manc_v10_sampled_edges_match_raw_official_connection_table():
    _skip_unless_built("manc", "v1.0")
    cx = _open("manc", "v1.0")
    rng = np.random.default_rng(11)
    idx = rng.choice(cx.n_edges, size=200, replace=False)
    pre, post, w, whp = cx._pre[idx], cx._post[idx], cx._w[idx], cx._whp[idx]
    raw = paths.raw_dir("manc", "v1.0") / MANC_V1_0.local_relpath(MANC_V1_0.file("neuprint_connections"))
    con = duckdb.connect()
    con.register("s", pa.table({"pre": pre, "post": post}))
    con.register("c", pads.dataset(str(raw), format="ipc"))
    got = con.execute('''SELECT c.":START_ID(Body-ID)" AS pre, c.":END_ID(Body-ID)" AS post, c."weight:int" AS w, c."weightHP:int" AS hp
                         FROM c SEMI JOIN s ON c.":START_ID(Body-ID)" = s.pre AND c.":END_ID(Body-ID)" = s.post''').fetchdf()
    ref = {(int(a), int(b)): (int(x), int(h)) for a, b, x, h in zip(got.pre, got.post, got.w, got.hp)}
    for a, b, x, h in zip(pre, post, w, whp):
        assert ref[(int(a), int(b))] == (int(x), int(h))


@pytest.mark.parametrize("ver", ["v1.2.1", "v1.2.3"])
def test_manc_v12_sampled_edges_match_recount_from_raw_partners(ver):
    """The rebuilt counts must equal a direct recount of the raw partner table under the recorded count rule."""
    _skip_unless_built("manc", ver)
    cx = _open("manc", ver)
    rule = cx.build_info["count_rule"]
    rng = np.random.default_rng(13)
    idx = rng.choice(cx.n_edges, size=60, replace=False)
    pre, post, w, whp = cx._pre[idx], cx._post[idx], cx._w[idx], cx._whp[idx]
    raw = paths.raw_dir("manc", "v1.2") / MANC_V1_2.local_relpath(MANC_V1_2.file("syn_partners"))
    con = duckdb.connect()
    con.register("s", pa.table({"pre": pre, "post": post}))
    con.register("p", pads.dataset(str(raw), format="ipc"))
    got = con.execute(f'''SELECT body_pre AS pre, body_post AS post,
                                 count(*) FILTER (WHERE CAST(conf_pre AS DOUBLE) >= {rule["conf_pre_min"]!r}
                                                    AND CAST(conf_post AS DOUBLE) >= {rule["conf_post_min"]!r}) AS w,
                                 count(*) FILTER (WHERE CAST(conf_pre AS DOUBLE) >= {rule["hp_conf_pre_min"]!r}
                                                    AND CAST(conf_post AS DOUBLE) >= {rule["hp_conf_post_min"]!r}) AS hp
                          FROM p SEMI JOIN s ON p.body_pre = s.pre AND p.body_post = s.post GROUP BY 1, 2''').fetchdf()
    ref = {(int(a), int(b)): (int(x), int(h)) for a, b, x, h in zip(got.pre, got.post, got.w, got.hp)}
    for a, b, x, h in zip(pre, post, w, whp):
        assert ref[(int(a), int(b))] == (int(x), int(h))


def test_manc_versions_share_synapse_lineage():
    """v1.2.x are re-annotations of a lightly edited v1.0 segmentation: most neurons and their strongest edges persist."""
    for ver in ("v1.0", "v1.2.1", "v1.2.3"):
        _skip_unless_built("manc", ver)
    a, b = _open("manc", "v1.0"), _open("manc", "v1.2.3")
    common = np.intersect1d(a.ids, b.ids)
    assert len(common) > 0.97 * min(a.n_neurons, b.n_neurons)
    sample = np.random.default_rng(3).choice(common, 300, replace=False)
    ea = a.edges_between(sample, common, annotate=False, min_count=5)
    eb = b.edges_between(sample, common, annotate=False, min_count=5)
    m = ea.merge(eb, on=["pre_id", "post_id"], how="inner", suffixes=("_a", "_b"))
    assert len(m) > 0.95 * len(ea)
    assert (m["synapse_count_a"] == m["synapse_count_b"]).mean() > 0.95
