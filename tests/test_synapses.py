"""Synapse-level extraction on the synthetic fixture."""

from __future__ import annotations

from collections import Counter

import pyarrow.parquet as pq
import pytest

from brainir.schema.tables import SYNAPSES
from brainir.synapses import extract_synapses, write_synapse_subset
from brainir.testing import synthetic as S


@pytest.fixture(scope="module")
def raw_dir(tmp_path_factory):
    return S.write_malecns_fixture(tmp_path_factory.mktemp("syn") / "raw")


def test_outgoing_synapses_match_edge_counts(raw_dir):
    t = extract_synapses(pre_ids=[101], raw_dir=raw_dir).to_pandas()
    per_edge = Counter(zip(t.pre_id, t.post_id))
    assert per_edge == {(101, 102): 6, (101, 103): 3, (101, 106): 1}
    np_101_102 = Counter(t[t.post_id == 102].neuropil)
    assert np_101_102 == {"LegNp(T1)(L)": 4, "<unassigned>": 2}  # '<unspecified>' mapped to canonical '<unassigned>'


def test_and_or_modes(raw_dir):
    both = extract_synapses(pre_ids=[101], post_ids=[103], raw_dir=raw_dir)
    assert both.num_rows == 3
    either = extract_synapses(pre_ids=[105], post_ids=[104], mode="or", raw_dir=raw_dir)
    assert either.num_rows == 3 + 4  # 105->102 (3) plus everything onto 104 (4)
    with pytest.raises(ValueError):
        extract_synapses(raw_dir=raw_dir)


def test_written_subset_is_canonical(raw_dir, tmp_path):
    t = extract_synapses(post_ids=[101], raw_dir=raw_dir)
    rec = write_synapse_subset(t, "into_101", out_dir=tmp_path)
    sch = pq.read_schema(tmp_path / "into_101.parquet")
    assert sch.remove_metadata().equals(SYNAPSES.schema.remove_metadata())
    assert rec["rows"] == 6  # 106->101 (2) + 107->101 (4)
