"""Corrupted inputs must be caught by the named validation checks (not silently absorbed)."""

from __future__ import annotations

import pytest

from brainir.ingest.malecns import IngestAborted

from brainir.testing.synthetic import build_synthetic_dataset as build_synthetic

CASES = {
    "duplicate_edge": ["duplicates.raw_connections.pair", "duplicates.connections.pair"],
    "edge_missing_segment": ["referential.raw_edges_reference_segments", "directionality.edge_sums_match_neuron_totals"],
    "negative_weight": ["edge_values.no_negative"],
    "flat_mismatch": ["cross_source.flat_vs_neuprint_neuron_edges"],
    "nt_bad_vocab": ["types.nt_vocabulary"],
}
# critical failures stop the build (report is still written)
ABORT_CASES = {
    "annotation_duplicate": "duplicates.annotations.bodyId",
    "wrong_version": "provenance.meta_dataset_tag",  # cross-version mixing
}


@pytest.mark.parametrize("mutation", sorted(CASES))
def test_mutation_is_detected(tmp_path, mutation):
    res = build_synthetic(tmp_path, mutate=mutation)
    failed = {c.check_id for c in res["report"].failures}
    for check_id in CASES[mutation]:
        assert check_id in failed, (mutation, sorted(failed))


@pytest.mark.parametrize("mutation", sorted(ABORT_CASES))
def test_critical_failures_abort_with_report(tmp_path, mutation):
    with pytest.raises(IngestAborted) as ei:
        build_synthetic(tmp_path, mutate=mutation)
    assert any(c.check_id == ABORT_CASES[mutation] for c in ei.value.report.failures)
    assert (tmp_path / "out" / "validation_report.json").exists()
    assert not (tmp_path / "out" / "connections.parquet").exists()  # nothing half-built is left behind
