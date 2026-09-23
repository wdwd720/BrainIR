"""CLI query commands against a synthetic dataset placed in a temporary data root."""

from __future__ import annotations

import json

import pytest

from brainir import cli
from brainir.ingest.malecns import IngestConfig, build
from brainir.testing.synthetic import write_malecns_fixture


@pytest.fixture(scope="module")
def data_root(tmp_path_factory):
    root = tmp_path_factory.mktemp("cli_data")
    raw = write_malecns_fixture(root / "raw" / "male-cns" / "v1.0")
    build(IngestConfig(raw_dir=raw, out_dir=root / "processed" / "male-cns" / "v1.0", verify_acquisition=False,
                       threads=2, duckdb_memory_limit="1GB", synapse_sample_neurons=10))
    return root


def run(monkeypatch, capsys, data_root, *argv):
    monkeypatch.setenv("BRAINIR_DATA_DIR", str(data_root))
    rc = cli.main(list(argv))
    assert rc == 0
    return capsys.readouterr().out


def test_neuron_json(monkeypatch, capsys, data_root):
    out = json.loads(run(monkeypatch, capsys, data_root, "neuron", "101"))
    assert out["cell_type"] == "DNtest" and out["neuron_uid"] == "male-cns:v1.0:101"
    assert out["sign_hypothesis"]["sign"] == 1


def test_type_and_search(monkeypatch, capsys, data_root):
    assert "INa" in run(monkeypatch, capsys, data_root, "type", "INa")
    out = json.loads(run(monkeypatch, capsys, data_root, "search", "^in", "--json"))
    assert {r["source_id"] for r in out} == {102, 103}


def test_down_up_edge(monkeypatch, capsys, data_root):
    down = json.loads(run(monkeypatch, capsys, data_root, "down", "101", "--min", "3", "--json"))
    assert {(r["post_id"], r["synapse_count"]) for r in down} == {(102, 6), (103, 3)}
    up = json.loads(run(monkeypatch, capsys, data_root, "up", "104", "--json"))
    assert [(r["pre_id"], r["synapse_count"]) for r in up] == [(102, 4)]
    edge = json.loads(run(monkeypatch, capsys, data_root, "edge", "101", "102"))
    assert edge["synapse_count"] == 6 and {n["neuropil"] for n in edge["neuropils"]} == {"LegNp(T1)(L)", "<unassigned>"}


def test_khop_and_paths(monkeypatch, capsys, data_root):
    kh = json.loads(run(monkeypatch, capsys, data_root, "khop", "101", "-k", "1", "--direction", "out", "--json"))
    assert {r["source_id"]: r["hop"] for r in kh} == {101: 0, 102: 1, 103: 1, 106: 1}
    paths = json.loads(run(monkeypatch, capsys, data_root, "paths", "105", "104", "--json"))
    assert paths == [{"path": [105, 102, 104], "types": ["SN1", "INa", "MN1"]}]
