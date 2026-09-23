"""Record-level BrainIR data model (pydantic).

These models are the object API returned by the graph access layer and the
contract for future datasets (FlyWire/FAFB, BANC, MANC, FANC, ...). Bulk
storage uses the Arrow schemas in :mod:`brainir.schema.tables`; the two are
kept consistent by tests.

Design rules
------------
* Anatomy (synapse counts) and model parameters (effective weights) live in
  different types. ``DirectedConnection`` has *no* weight/strength field.
* Predictions carry their confidence and provenance; hypotheses carry the
  rule ID that produced them.
* Everything is namespaced by (dataset, dataset_version).
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .evidence import EvidenceKind


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# ---------------------------------------------------------------------------
# Provenance & dataset versions
# ---------------------------------------------------------------------------
class FileChecksum(_Model):
    path: str = Field(description="Path relative to $DATA or $REPO (never absolute).")
    size_bytes: int
    sha256: str
    crc32c_b64: str | None = None
    md5_b64: str | None = None


class Transformation(_Model):
    step: str
    description: str
    code_ref: str = Field(description="Module/function implementing the step.")
    parameters: dict = Field(default_factory=dict)


class Provenance(_Model):
    source_dataset: str
    source_version: str
    source_files: list[str] = Field(default_factory=list, description="Registry keys of raw inputs.")
    pipeline: str | None = None
    pipeline_version: str | None = None
    git_commit: str | None = None
    build_id: str | None = None
    notes: str | None = None


class DatasetVersion(_Model):
    dataset: str = Field(examples=["male-cns"])
    version: str = Field(examples=["v1.0"])
    release_date: str | None = None
    animal_sex: Literal["male", "female", "unknown"]
    n_animals: int = 1
    cns_coverage: str = Field(description="e.g. 'brain + VNC', 'brain', 'VNC'.")
    acquisition_source: str
    acquisition_method: str
    acquired_at_utc: str | None = None
    access_urls: dict[str, str] = Field(default_factory=dict)
    checksums: list[FileChecksum] = Field(default_factory=list)
    transformations: list[Transformation] = Field(default_factory=list)
    synapse_confidence_threshold: float | None = None
    synapse_confidence_threshold_hp: float | None = None
    coordinate_space: str | None = None
    voxel_size_nm: tuple[float, float, float] | None = None
    citation: dict = Field(default_factory=dict)
    license: dict = Field(default_factory=dict)
    documentation_urls: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.dataset}:{self.version}"


# ---------------------------------------------------------------------------
# Neurons
# ---------------------------------------------------------------------------
class NeurotransmitterPrediction(_Model):
    """ML prediction (EvidenceKind.ML_PREDICTION) — never physiology."""
    evidence: Literal[EvidenceKind.ML_PREDICTION] = EvidenceKind.ML_PREDICTION
    consensus: str | None = None
    body_prediction: str | None = None
    body_confidence: float | None = None
    body_n_tbars: int | None = None
    type_prediction: str | None = None
    type_confidence: float | None = None
    type_n_tbars: int | None = None
    literature_label: str | None = Field(None, description="EvidenceKind.LITERATURE_LABEL for the cell type.")


class SignHypothesis(_Model):
    """Rule-derived excitatory/inhibitory hypothesis (EvidenceKind.DERIVED_HYPOTHESIS)."""
    evidence: Literal[EvidenceKind.DERIVED_HYPOTHESIS] = EvidenceKind.DERIVED_HYPOTHESIS
    sign: Literal[-1, 1] | None = Field(description="+1 excitatory, -1 inhibitory, None undefined.")
    rule_id: str
    rule_class: str
    based_on_nt: str | None
    based_on_field: str
    nt_confidence: float | None = Field(description="Confidence of the NT prediction the sign is based on.")


class NeuropilCount(_Model):
    neuropil: str
    n_pre: int = 0
    n_post: int = 0


class MorphologyRef(_Model):
    kind: Literal["skeleton_swc", "skeleton_precomputed", "mesh_precomputed", "segmentation"]
    uri: str
    coordinate_space: str
    units: str
    verified_exists: bool = False


class Neuron(_Model):
    neuron_uid: str
    dataset: str
    dataset_version: str
    source_id: int
    cell_type: str | None = None
    instance: str | None = None
    super_class: str | None = None
    cell_class: str | None = None
    sub_class: str | None = None
    hemilineage_ito_lee: str | None = None
    hemilineage_truman: str | None = None
    animal_sex: str
    soma_side: str | None = None
    root_side: str | None = None
    side: str | None = None
    soma_neuromere: str | None = None
    soma_location_voxels: tuple[int, int, int] | None = None
    status: str | None = None
    status_label: str | None = None
    is_traced: bool = False
    neuprint_neuron_label: bool | None = None
    n_pre: int | None = None
    n_post: int | None = None
    n_downstream: int | None = None
    n_upstream: int | None = None
    neurotransmitter: NeurotransmitterPrediction = Field(default_factory=NeurotransmitterPrediction)
    sign_hypothesis: SignHypothesis | None = None
    neuropils: list[NeuropilCount] = Field(default_factory=list)
    annotations: dict[str, object] = Field(default_factory=dict, description="Verbatim source annotations.")
    morphology: list[MorphologyRef] = Field(default_factory=list)
    provenance: Provenance

    @model_validator(mode="after")
    def _uid_consistent(self) -> "Neuron":
        expected = make_neuron_uid(self.dataset, self.dataset_version, self.source_id)
        if self.neuron_uid != expected:
            raise ValueError(f"neuron_uid {self.neuron_uid!r} != {expected!r}")
        return self


def make_neuron_uid(dataset: str, version: str, source_id: int) -> str:
    if ":" in dataset or ":" in version:
        raise ValueError("dataset/version must not contain ':'")
    return f"{dataset}:{version}:{int(source_id)}"


def parse_neuron_uid(uid: str) -> tuple[str, str, int]:
    dataset, version, sid = uid.split(":")
    return dataset, version, int(sid)


# ---------------------------------------------------------------------------
# Connectivity
# ---------------------------------------------------------------------------
class DirectedConnection(_Model):
    """Anatomical connection. Deliberately has NO 'weight'/'strength' field:
    physiological efficacy is a model parameter (see ModelParameter)."""
    dataset: str
    dataset_version: str
    pre_id: int
    post_id: int
    synapse_count: int = Field(ge=1, description="T-bar->PSD pairs (EvidenceKind.EM_RECONSTRUCTION).")
    synapse_count_hp: int | None = Field(None, ge=0)
    is_autapse: bool
    neuropils: list[NeuropilCount] = Field(default_factory=list, description="n_post = PSD counts per neuropil.")
    predicted_sign: SignHypothesis | None = Field(
        None, description="Presynaptic neuron's sign hypothesis (Dale's principle assumed).")
    provenance: Provenance

    @model_validator(mode="after")
    def _check(self) -> "DirectedConnection":
        if self.is_autapse != (self.pre_id == self.post_id):
            raise ValueError("is_autapse inconsistent with pre_id/post_id")
        if self.synapse_count_hp is not None and self.synapse_count_hp > self.synapse_count:
            raise ValueError("synapse_count_hp exceeds synapse_count")
        if self.neuropils and sum(n.n_post for n in self.neuropils) != self.synapse_count:
            raise ValueError("neuropil counts do not sum to synapse_count")
        return self


class Synapse(_Model):
    dataset: str
    dataset_version: str
    pre_id: int
    post_id: int
    pre_location_voxels: tuple[int, int, int]
    post_location_voxels: tuple[int, int, int]
    conf_pre: float
    conf_post: float
    neuropil: str | None
    coordinate_space: str
    provenance: Provenance


# ---------------------------------------------------------------------------
# Modelling (kept strictly apart from anatomy)
# ---------------------------------------------------------------------------
class ModelParameter(_Model):
    """A parameter of a computational model, e.g. an effective synaptic weight.

    Must reference the model and how it was obtained. Never written into
    anatomy tables."""
    evidence: Literal[EvidenceKind.MODEL_PARAMETER] = EvidenceKind.MODEL_PARAMETER
    model_id: str
    name: str = Field(examples=["effective_weight", "tau_m", "gain"])
    target: str = Field(description="neuron_uid, 'pre_uid->post_uid', or a population label.")
    value: float
    unit: str | None = None
    origin: Literal["assumed", "fitted", "derived_from_anatomy"]
    derivation: str = Field(description="e.g. 'synapse_count * sign * scale (scale=0.01)'.")


# ---------------------------------------------------------------------------
# Experiments / trials (future use; no data in Phase 0)
# ---------------------------------------------------------------------------
class InterventionType(StrEnum):
    OPTOGENETIC_ACTIVATION = "optogenetic_activation"
    OPTOGENETIC_SILENCING = "optogenetic_silencing"
    THERMOGENETIC_ACTIVATION = "thermogenetic_activation"
    THERMOGENETIC_SILENCING = "thermogenetic_silencing"
    CHRONIC_SILENCING = "chronic_silencing"          # e.g. Kir2.1, TNT
    GENETIC_ABLATION = "genetic_ablation"
    PHARMACOLOGICAL = "pharmacological"
    ELECTRICAL_STIMULATION = "electrical_stimulation"
    SENSORY_STIMULUS = "sensory_stimulus"
    IN_SILICO_ACTIVATION = "in_silico_activation"
    IN_SILICO_SILENCING = "in_silico_silencing"
    IN_SILICO_LESION = "in_silico_lesion"
    NONE = "none"


class TimeSeries(_Model):
    name: str
    unit: str
    t0_s: float = 0.0
    sampling_rate_hz: float | None = None
    timestamps_s: list[float] | None = None
    values: list[float] | list[list[float]]
    channel_labels: list[str] | None = None

    @model_validator(mode="after")
    def _time_axis(self) -> "TimeSeries":
        if (self.sampling_rate_hz is None) == (self.timestamps_s is None):
            raise ValueError("provide exactly one of sampling_rate_hz or timestamps_s")
        return self


class TargetSpec(_Model):
    """What an intervention/measurement targets. Genetic lines target sets of
    cells only approximately; record both the line and the mapped neurons."""
    cell_types: list[str] = Field(default_factory=list)
    neuron_uids: list[str] = Field(default_factory=list)
    driver_line: str | None = None
    mapping_confidence: str | None = Field(None, description="How the driver line was mapped to connectome neurons.")


class Intervention(_Model):
    intervention_type: InterventionType
    targets: TargetSpec
    onset_s: float | None = None
    duration_s: float | None = None
    amplitude: float | None = None
    amplitude_unit: str | None = None
    waveform: TimeSeries | None = None
    notes: str | None = None


class Measurement(_Model):
    kind: Literal["neural", "behavioral"]
    modality: str = Field(examples=["calcium_imaging", "electrophysiology", "leg_kinematics", "walking_speed"])
    targets: TargetSpec | None = None
    data: TimeSeries
    evidence: Literal[EvidenceKind.EXPERIMENTAL_MEASUREMENT, EvidenceKind.MODEL_PARAMETER] = \
        EvidenceKind.EXPERIMENTAL_MEASUREMENT


class Trial(_Model):
    trial_id: str
    experiment_id: str
    stimulus: list[TimeSeries] = Field(default_factory=list)
    interventions: list[Intervention] = Field(default_factory=list)
    neural_measurements: list[Measurement] = Field(default_factory=list)
    behavioral_measurements: list[Measurement] = Field(default_factory=list)
    start_time_utc: datetime | None = None
    provenance: Provenance


class Experiment(_Model):
    experiment_id: str
    description: str
    organism: str = "Drosophila melanogaster"
    genotype: str | None = None
    sex: Literal["male", "female", "mixed", "unknown"] = "unknown"
    is_in_silico: bool = False
    connectome_refs: list[str] = Field(default_factory=list, description="DatasetVersion keys used, if any.")
    publication: str | None = None
    trials: list[Trial] = Field(default_factory=list)
    provenance: Provenance
