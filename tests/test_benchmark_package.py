"""Prediction schema, bundle integrity and clean-room contract of the DNg100 benchmark package."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from brainir import paths
from brainir.benchmark.bundle import BENCHMARK_ID, _blind_token, verify_bundle
from brainir.benchmark.prediction import (
    PREDICTION_SCHEMA_VERSION,
    BrainIRMechanismPrediction,
    CrossConnectomeClaim,
    DynamicsClaim,
    MethodInfo,
    NeuronClaim,
)

BUNDLES = [paths.repo_root() / "benchmarks" / "dng100" / "public", paths.repo_root() / "benchmarks" / "dng100" / "public_blind"]


def _pred(core=(1, 2, 3), stim=(99,), **kw):
    return BrainIRMechanismPrediction(
        benchmark_id=BENCHMARK_ID, dataset="manc", dataset_version="v1.2.1", stimulus_source_ids=list(stim),
        core_neurons=[NeuronClaim(source_id=i, role="excitatory", essential=(i == 1)) for i in core],
        method=MethodInfo(name="unit-test"), **kw)


def test_prediction_roundtrip_and_digest_are_stable():
    p = _pred(dynamics=DynamicsClaim(frequency_hz=11.0, rhythmic=True))
    q = BrainIRMechanismPrediction.from_json(p.to_json())
    assert q == p and q.digest() == p.digest() and p.schema_version == PREDICTION_SCHEMA_VERSION == "1.0.0"
    assert p.core_ids() == [1, 2, 3]
    assert json.loads(p.to_json())["core_neurons"][0]["essential"] is True


def test_prediction_rejects_duplicates_stimulus_and_unknown_fields():
    with pytest.raises(ValidationError):
        _pred(core=(1, 1, 2))
    with pytest.raises(ValidationError):
        _pred(core=(99, 1))  # the stimulated neuron cannot be part of the mechanism
    with pytest.raises(ValidationError):
        NeuronClaim(source_id=1, role="modulatory")
    with pytest.raises(ValidationError):
        BrainIRMechanismPrediction.model_validate({**json.loads(_pred().to_json()), "answer": "copied"})
    with pytest.raises(ValidationError):
        NeuronClaim(source_id=1, confidence=1.5)
    CrossConnectomeClaim(source_id=1, other_dataset="male-cns", other_version="v1.0", other_source_id=5, basis="type_name")


def test_blind_tokens_are_deterministic_per_salt_and_not_invertible_by_id_pattern():
    a = _blind_token("salt-1", "manc", "v1.2.1", 12345)
    assert a == _blind_token("salt-1", "manc", "v1.2.1", 12345) and a.startswith("T#") and len(a) == 12
    assert a != _blind_token("salt-2", "manc", "v1.2.1", 12345)
    assert a != _blind_token("salt-1", "manc", "v1.2.3", 12345)  # tokens are not comparable across networks
    assert "12345" not in a


@pytest.mark.parametrize("root", BUNDLES, ids=lambda p: p.name)
def test_exported_bundle_verifies_and_is_answer_free(root: Path):
    if not (root / "manifest.json").exists():
        pytest.skip("bundle not exported")
    v = verify_bundle(root)
    assert v["ok"], v
    m = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert m["benchmark_id"] == BENCHMARK_ID and m["tier"] in ("A", "B") and m["code_commit"]
    names = {n["name"] for n in m["networks"]}
    assert {"manc_v1.2.1", "male-cns_v1.0"} <= names
    for n in m["networks"]:
        d = root / "networks" / n["name"]
        stim = json.loads((d / "stimulus.json").read_text())
        ro = json.loads((d / "readout.json").read_text())
        assert stim["cell_type"] == "DNg100" and len(stim["source_ids"]) >= 1 and ro["n"] > 100
        txt = (d / "network.json").read_text() + (root / "README.md").read_text()
        assert "C:\\" not in txt and "Users/" not in txt
    # the oracle's label vocabulary must not occur in the bundle prose
    readme = (root / "README.md").read_text(encoding="utf-8")
    for tok in ("E1", "E2", "I1", "I2", "answer", "oracle"):
        assert f" {tok} " not in readme


@pytest.mark.real_data
def test_blind_bundle_hides_interneuron_types():
    import pandas as pd

    root = BUNDLES[1]
    if not (root / "manifest.json").exists():
        pytest.skip("blind bundle not exported")
    df = pd.read_parquet(root / "networks" / "manc_v1.2.1" / "neurons.parquet")
    inter = df[df["role_class"] == "vnc_intrinsic"]
    assert inter["cell_type"].str.startswith("T#").all() and inter["instance"].isna().all()
    assert (df.loc[df["is_stimulus"], "cell_type"] == "DNg100").all()  # stimulus keeps its label
    assert df.loc[df["is_readout"], "cell_type"].str.startswith("T#").sum() == 0
    assert (df["source_id"].to_numpy() == df["position"].to_numpy()).all()  # positional ids: body IDs are not visible
    e = pd.read_parquet(root / "networks" / "manc_v1.2.1" / "edges.parquet")
    assert e["pre_id"].max() < len(df) and e["post_id"].max() < len(df)
    labelled = pd.read_parquet(BUNDLES[0] / "networks" / "manc_v1.2.1" / "neurons.parquet")
    assert (labelled["source_id"] != labelled["position"]).any()  # tier B keeps dataset body IDs
