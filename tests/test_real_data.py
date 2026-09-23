"""Integration smoke tests against the real processed MaleCNS v1.0 build.

Skipped automatically when data/processed/male-cns/v1.0 has not been built
(fresh clone without data). Rebuild with:  uv run brainir acquire && uv run brainir ingest
"""

from __future__ import annotations

import json

import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.dataset as pads
import pytest

from brainir import paths
from brainir.sources.registry import MALECNS_V1_0

PROC = paths.processed_dir("male-cns", "v1.0")
RAW = paths.raw_dir("male-cns", "v1.0")
pytestmark = [pytest.mark.real_data,
              pytest.mark.skipif(not (PROC / "connections.parquet").exists(), reason="real MaleCNS build not present")]


@pytest.fixture(scope="module")
def real():
    from brainir.graph import Connectome
    return Connectome.open("male-cns", "v1.0")


def test_build_passed_validation():
    rep = json.loads((PROC / "validation_report.json").read_text())
    assert rep["summary"]["fail"] == 0, [c["check_id"] for c in rep["checks"] if c["status"] == "fail"]


def test_sizes_are_plausible(real):
    # Berg et al. report 166,691 neurons (v0.9 era); v1.0 annotations give 166,700 bodies with a superclass.
    assert 166_000 < real.n_neurons < 167_500
    # Berg et al.: 25.6M edges between 166,391 neurons (traced-only graph)
    assert 24_000_000 < real.n_edges < 27_500_000


def test_dng100_is_locatable(real):
    ids = real.ids_of_type("DNg100")
    assert len(ids) == 2
    for i in ids:
        n = real.neuron(int(i))
        assert n["super_class"] == "descending_neuron" and n["nt_consensus"] == "acetylcholine"
        d = real.downstream(int(i), min_count=5)
        assert len(d) > 100  # DNg100 contacts >1,400 VNC cells (Pugliese et al.)


def test_sampled_edges_match_raw_official_connection_table(real):
    rng = np.random.default_rng(7)
    idx = rng.choice(real.n_edges, size=200, replace=False)
    pre, post, w = real._pre[idx], real._post[idx], real._w[idx]
    raw = RAW / MALECNS_V1_0.local_relpath(MALECNS_V1_0.file("neuprint_connections"))
    con = duckdb.connect()
    con.register("s", pa.table({"pre": pre, "post": post}))
    con.register("c", pads.dataset(str(raw), format="ipc"))
    got = con.execute('''SELECT c.":START_ID(Body-ID)" AS pre, c.":END_ID(Body-ID)" AS post, c."weight:int" AS w
                         FROM c SEMI JOIN s ON c.":START_ID(Body-ID)" = s.pre AND c.":END_ID(Body-ID)" = s.post''').fetchdf()
    ref = {(int(a), int(b)): int(x) for a, b, x in zip(got.pre, got.post, got.w)}
    for a, b, x in zip(pre, post, w):
        assert ref[(int(a), int(b))] == int(x)


def test_neuron_ids_are_int64_and_unique(real):
    assert real.ids.dtype == np.int64
    assert len(np.unique(real.ids)) == len(real.ids)
    assert (real.neurons["neuron_uid"] == "male-cns:v1.0:" + real.neurons["source_id"].astype(str)).all()
