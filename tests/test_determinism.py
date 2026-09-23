"""Deterministic outputs: identical inputs + library versions -> byte-identical Parquet."""

from __future__ import annotations

import json

import pyarrow as pa
import pyarrow.parquet as pq

from brainir.io import sha256_file, write_canonical
from brainir.schema.tables import CONNECTIONS
from brainir.testing.synthetic import build_synthetic_dataset

TABLES = ("neurons", "connections", "connection_neuropils", "neuron_neuropils", "neuropils",
          "neuron_annotations_source")


def test_rebuild_is_byte_identical(tmp_path):
    a = build_synthetic_dataset(tmp_path / "a")
    b = build_synthetic_dataset(tmp_path / "b")
    for t in TABLES:
        pa_, pb_ = a["out_dir"] / f"{t}.parquet", b["out_dir"] / f"{t}.parquet"
        assert sha256_file(pa_) == sha256_file(pb_), t
    ra = json.loads((a["out_dir"] / "validation_report.json").read_text())
    rb = json.loads((b["out_dir"] / "validation_report.json").read_text())
    assert ra["checks"] == rb["checks"]


def test_writer_is_insensitive_to_input_row_order_and_chunking(tmp_path):
    rows = dict(pre_id=[3, 1, 2, 1], post_id=[1, 2, 2, 1], synapse_count=[5, 3, 4, 1], synapse_count_hp=[5, 2, 4, 1],
                is_autapse=[False, False, True, True], dominant_neuropil=["B", "A", "A", "C"],
                dominant_neuropil_fraction=[1.0, 1.0, 1.0, 1.0], n_neuropils=[1, 1, 1, 1])
    t1 = pa.table(rows)
    perm = [2, 0, 3, 1]
    t2 = pa.concat_tables([pa.table({k: [v[i] for i in perm[:2]] for k, v in rows.items()}),
                           pa.table({k: [v[i] for i in perm[2:]] for k, v in rows.items()})])
    r1 = write_canonical(t1, CONNECTIONS, tmp_path / "x1.parquet")
    r2 = write_canonical(t2, CONNECTIONS, tmp_path / "x2.parquet")
    assert r1["sha256"] == r2["sha256"]
    got = pq.read_table(tmp_path / "x1.parquet").to_pandas()
    assert list(zip(got.pre_id, got.post_id)) == [(1, 1), (1, 2), (2, 2), (3, 1)]
