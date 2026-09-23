"""Schema tests: evidence metadata, conformance casting, record-model invariants."""

from __future__ import annotations

import pyarrow as pa
import pytest
from pydantic import ValidationError

from brainir.schema import CANONICAL_TABLES, EvidenceKind, conform
from brainir.schema import models as M
from brainir.schema.tables import CONNECTIONS, NEURONS
from brainir.schema.vocab import NT_VALUES, SIGN_RULES, normalize_side, sign_for_nt, status_label_rank


@pytest.mark.parametrize("name", sorted(CANONICAL_TABLES))
def test_every_column_declares_evidence_and_description(name):
    spec = CANONICAL_TABLES[name]
    kinds = {k.value for k in EvidenceKind}
    for field in spec.schema:
        md = {k.decode(): v.decode() for k, v in (field.metadata or {}).items()}
        assert md.get("evidence") in kinds, (name, field.name)
        assert md.get("description"), (name, field.name)
    assert set(spec.primary_key) <= set(spec.column_names)
    assert set(spec.sort_by) <= set(spec.column_names)


def test_anatomy_tables_contain_no_model_parameters():
    for spec in CANONICAL_TABLES.values():
        for c in spec.columns:
            assert c.evidence is not EvidenceKind.MODEL_PARAMETER, (spec.name, c.name)
            assert "weight" not in c.name, (spec.name, c.name)


def test_neuron_table_keeps_predictions_separate_from_annotations():
    ev = {c.name: c.evidence for c in NEURONS.columns}
    assert ev["nt_consensus"] is EvidenceKind.ML_PREDICTION
    assert ev["nt_literature_label"] is EvidenceKind.LITERATURE_LABEL
    assert ev["cell_type"] is EvidenceKind.CURATED_ANNOTATION
    assert ev["n_pre"] is EvidenceKind.EM_RECONSTRUCTION


def _edges(**over):
    d = dict(pre_id=[1, 2], post_id=[2, 2], synapse_count=[3, 4], synapse_count_hp=[1, 2], is_autapse=[False, True],
             dominant_neuropil=["GNG", "GNG"], dominant_neuropil_fraction=[1.0, 1.0], n_neuropils=[1, 1])
    d.update(over)
    return pa.table(d)


def test_conform_casts_and_orders():
    t = conform(_edges(), CONNECTIONS)
    assert t.schema.equals(CONNECTIONS.schema, check_metadata=False)
    assert t.column("synapse_count").type == pa.int32()
    assert pa.types.is_dictionary(t.column("dominant_neuropil").type)


def test_conform_rejects_missing_and_extra_columns():
    with pytest.raises(ValueError, match="missing"):
        conform(_edges().drop(["n_neuropils"]), CONNECTIONS)
    with pytest.raises(ValueError, match="extra"):
        conform(_edges().append_column("weight", pa.array([1.0, 2.0])), CONNECTIONS)


def test_conform_rejects_nulls_in_required_columns():
    with pytest.raises(ValueError, match="nulls"):
        conform(_edges(pre_id=pa.array([1, None], pa.int64())), CONNECTIONS)


def test_conform_refuses_lossy_integer_cast():
    with pytest.raises(pa.ArrowInvalid):
        conform(_edges(synapse_count=pa.array([3.5, 4.0])), CONNECTIONS)
    with pytest.raises(pa.ArrowInvalid):
        conform(_edges(synapse_count=pa.array([2**40, 4], pa.int64())), CONNECTIONS)


def _prov():
    return M.Provenance(source_dataset="male-cns", source_version="v1.0")


def test_directed_connection_invariants():
    ok = M.DirectedConnection(dataset="d", dataset_version="v", pre_id=1, post_id=2, synapse_count=3,
                              synapse_count_hp=2, is_autapse=False,
                              neuropils=[M.NeuropilCount(neuropil="A", n_post=2), M.NeuropilCount(neuropil="B", n_post=1)],
                              provenance=_prov())
    assert ok.synapse_count == 3
    assert "weight" not in M.DirectedConnection.model_fields
    with pytest.raises(ValidationError):  # autapse flag inconsistent
        M.DirectedConnection(dataset="d", dataset_version="v", pre_id=1, post_id=1, synapse_count=3, is_autapse=False,
                             provenance=_prov())
    with pytest.raises(ValidationError):  # HP subset larger than total
        M.DirectedConnection(dataset="d", dataset_version="v", pre_id=1, post_id=2, synapse_count=3, synapse_count_hp=4,
                             is_autapse=False, provenance=_prov())
    with pytest.raises(ValidationError):  # neuropil counts must sum to total
        M.DirectedConnection(dataset="d", dataset_version="v", pre_id=1, post_id=2, synapse_count=3, is_autapse=False,
                             neuropils=[M.NeuropilCount(neuropil="A", n_post=1)], provenance=_prov())
    with pytest.raises(ValidationError):  # connections have >= 1 synapse
        M.DirectedConnection(dataset="d", dataset_version="v", pre_id=1, post_id=2, synapse_count=0, is_autapse=False,
                             provenance=_prov())


def test_neuron_uid_roundtrip_and_validation():
    uid = M.make_neuron_uid("male-cns", "v1.0", 10001)
    assert uid == "male-cns:v1.0:10001"
    assert M.parse_neuron_uid(uid) == ("male-cns", "v1.0", 10001)
    with pytest.raises(ValueError):
        M.make_neuron_uid("bad:name", "v1.0", 1)
    with pytest.raises(ValidationError):
        M.Neuron(neuron_uid="male-cns:v1.0:2", dataset="male-cns", dataset_version="v1.0", source_id=1,
                 animal_sex="male", provenance=_prov())


def test_neuron_model_fields_cover_core_neuron_columns():
    fields = set(M.Neuron.model_fields)
    for col in ("neuron_uid", "dataset", "dataset_version", "source_id", "cell_type", "instance", "super_class",
                "hemilineage_ito_lee", "hemilineage_truman", "soma_side", "root_side", "side", "status", "is_traced",
                "animal_sex", "n_pre", "n_post", "neuprint_neuron_label"):
        assert col in NEURONS.column_names and col in fields, col


def test_timeseries_requires_exactly_one_time_axis():
    M.TimeSeries(name="x", unit="Hz", sampling_rate_hz=100.0, values=[1.0, 2.0])
    M.TimeSeries(name="x", unit="Hz", timestamps_s=[0.0, 0.01], values=[1.0, 2.0])
    with pytest.raises(ValidationError):
        M.TimeSeries(name="x", unit="Hz", values=[1.0])
    with pytest.raises(ValidationError):
        M.TimeSeries(name="x", unit="Hz", sampling_rate_hz=1.0, timestamps_s=[0.0], values=[1.0])


def test_experiment_trial_models_compose():
    ts = M.TimeSeries(name="stim", unit="mW/mm2", sampling_rate_hz=1000.0, values=[0.0, 0.3, 0.3, 0.0])
    tr = M.Trial(trial_id="t1", experiment_id="e1", stimulus=[ts],
                 interventions=[M.Intervention(intervention_type=M.InterventionType.OPTOGENETIC_ACTIVATION,
                                               targets=M.TargetSpec(cell_types=["DNx"], driver_line="SS00000"),
                                               onset_s=0.0, duration_s=5.0, amplitude=0.33, amplitude_unit="mW/mm2")],
                 behavioral_measurements=[M.Measurement(kind="behavioral", modality="walking_speed", data=ts)],
                 provenance=_prov())
    ex = M.Experiment(experiment_id="e1", description="test", trials=[tr], provenance=_prov())
    assert ex.trials[0].interventions[0].intervention_type == "optogenetic_activation"


def test_model_parameter_is_explicitly_not_anatomy():
    p = M.ModelParameter(model_id="m", name="effective_weight", target="a->b", value=0.03, origin="assumed",
                         derivation="synapse_count * sign * 0.03")
    assert p.evidence is EvidenceKind.MODEL_PARAMETER


def test_sign_rules():
    assert sign_for_nt("acetylcholine").sign == 1
    assert sign_for_nt("gaba").sign == -1
    g = sign_for_nt("glutamate")
    assert g.sign == -1 and g.rule_class == "context_dependent"
    for nt in ("dopamine", "serotonin", "octopamine"):
        assert sign_for_nt(nt).sign is None and sign_for_nt(nt).rule_class == "modulatory"
    assert sign_for_nt("unclear").sign is None
    assert sign_for_nt(None) is None
    assert set(SIGN_RULES) == set(NT_VALUES)


def test_vocab_helpers():
    assert normalize_side("L") == "L" and normalize_side("left") == "L" and normalize_side("unknown") is None
    assert status_label_rank("Leaves") > status_label_rank("Sensory Anchor") > status_label_rank("Orphan")
    assert status_label_rank("nonsense") is None
