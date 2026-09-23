"""Versioned schema of what a circuit-discovery method must output for the DNg100 benchmark.

A prediction is a *claim about mechanism*: which neurons implement the stimulus->motor-rhythm transformation, in which
roles, which of them are essential, how they map across connectomes, and what the resulting dynamics look like. It is
evaluated by the frozen evaluator against an oracle the discovery method never sees. The schema deliberately carries
no field that could be filled by copying published results (no free-text "paper says" fields), and the evaluator
ignores everything it does not understand.

Schema version history
----------------------
1.0.0  first frozen version (Phase 1).
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PREDICTION_SCHEMA_VERSION = "1.0.0"

Role = Literal["excitatory", "inhibitory", "unknown"]


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class NeuronClaim(_Model):
    """One neuron of the predicted mechanism, identified by dataset-native ID."""
    source_id: int
    role: Role = "unknown"
    """Predicted functional sign of the neuron's output within the mechanism."""
    essential: bool | None = None
    """Predicted: silencing this neuron alone abolishes the rhythm (True), does not (False), unknown (None)."""
    rank: int | None = Field(None, ge=1, description="Optional importance rank (1 = most important).")
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    cell_type_claim: str | None = Field(None, description="Optional: the cell type the method attributes to the neuron.")


class DynamicsClaim(_Model):
    frequency_hz: float | None = Field(None, ge=0.0, description="Predicted motor rhythm frequency under the benchmark stimulus.")
    frequency_range_hz: tuple[float, float] | None = None
    n_active_readout: int | None = Field(None, ge=0, description="Predicted number of active readout (motor) neurons.")
    rhythmic: bool | None = Field(None, description="Predicted: the benchmark stimulus produces a sustained motor rhythm.")


class MechanismClaim(_Model):
    motif: str | None = Field(None, description="Short structural description, e.g. 'recurrent excitation + feedback inhibition'.")
    loop_neurons: list[int] = Field(default_factory=list, description="Neurons forming the predicted rhythm-generating loop.")
    notes: str | None = Field(None, max_length=2000)


class CrossConnectomeClaim(_Model):
    """A predicted correspondence between a neuron of this prediction's dataset and a neuron of another dataset."""
    source_id: int
    other_dataset: str
    other_version: str
    other_source_id: int
    basis: Literal["curated_match", "type_name", "connectivity", "morphology", "other"] = "other"
    confidence: float | None = Field(None, ge=0.0, le=1.0)


class MethodInfo(_Model):
    name: str
    version: str | None = None
    description: str | None = Field(None, max_length=4000)
    code_commit: str | None = None
    inputs_used: list[str] = Field(default_factory=list, description="Public-bundle files the method read (relative paths).")
    compute: dict = Field(default_factory=dict, description="Wall time, simulations run, backend, approximate cost.")
    random_seed: int | None = None


class BrainIRMechanismPrediction(_Model):
    schema_version: Literal["1.0.0"] = PREDICTION_SCHEMA_VERSION
    benchmark_id: str = Field(description="e.g. 'dng100-benchmark-v1'.")
    dataset: str
    dataset_version: str
    stimulus_source_ids: list[int] = Field(description="The stimulated neurons the prediction refers to (from the public bundle).")
    core_neurons: list[NeuronClaim] = Field(description="The predicted mechanism: interneurons between stimulus and readout.")
    dynamics: DynamicsClaim = Field(default_factory=DynamicsClaim)
    mechanism: MechanismClaim = Field(default_factory=MechanismClaim)
    cross_connectome: list[CrossConnectomeClaim] = Field(default_factory=list)
    method: MethodInfo
    created_utc: str | None = None

    @model_validator(mode="after")
    def _unique_ids(self) -> BrainIRMechanismPrediction:
        ids = [c.source_id for c in self.core_neurons]
        if len(ids) != len(set(ids)):
            raise ValueError("core_neurons contains duplicate source_ids")
        if any(i in self.stimulus_source_ids for i in ids):
            raise ValueError("stimulus neurons cannot be part of the predicted mechanism")
        return self

    def core_ids(self) -> list[int]:
        return [c.source_id for c in self.core_neurons]

    def to_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), indent=1, sort_keys=True) + "\n"

    def digest(self) -> str:
        return hashlib.sha256(self.to_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, text: str) -> BrainIRMechanismPrediction:
        return cls.model_validate(json.loads(text))
