"""Epistemic status of every field in the BrainIR schema.

BrainIR keeps *what was observed*, *what experts annotated*, *what a model
predicted*, *what a rule hypothesises* and *what a simulation assumes* in
explicitly separate categories. Every column of every canonical table carries
one of these kinds in its Arrow field metadata (key ``evidence``), so that
downstream code can refuse to treat, e.g., a predicted neurotransmitter as
measured physiology.
"""

from __future__ import annotations

from enum import StrEnum


class EvidenceKind(StrEnum):
    IDENTIFIER = "identifier"
    """Keys and namespacing (dataset, version, IDs). Not a biological claim."""

    EM_RECONSTRUCTION = "em_reconstruction"
    """Derived from the EM volume: proofread segmentation + automated synapse
    detection (with a confidence threshold). Counts and locations are
    anatomical estimates, *not* physiological synaptic strengths."""

    DERIVED_ANATOMY = "derived_anatomy"
    """Deterministic function of EM_RECONSTRUCTION fields computed by BrainIR
    (e.g. is_autapse, dominant neuropil, totals). Carries the same caveats."""

    CURATED_ANNOTATION = "curated_annotation"
    """Labels assigned by expert proofreaders/annotators (cell type, class,
    side, hemilineage, proofreading status, cross-dataset matches). Human
    judgements that can change between releases."""

    ML_PREDICTION = "ml_prediction"
    """Output of a machine-learning model (e.g. neurotransmitter predicted
    from EM ultrastructure) with a model-reported confidence."""

    LITERATURE_LABEL = "literature_label"
    """Label transferred from published experimental literature (e.g. known
    neurotransmitter of a cell type). Not measured in this animal."""

    DERIVED_HYPOTHESIS = "derived_hypothesis"
    """Biological hypothesis produced by an explicit, versioned BrainIR rule
    (e.g. excitatory/inhibitory sign inferred from a predicted
    neurotransmitter). Never ground truth."""

    MODEL_PARAMETER = "model_parameter"
    """Parameter of a computational model (effective weight, time constant,
    gain). Assumed or fitted — never stored in anatomy tables."""

    EXPERIMENTAL_MEASUREMENT = "experimental_measurement"
    """Physiological or behavioural measurement from a real experiment."""

    PROVENANCE = "provenance"
    """Metadata describing where data came from and how it was transformed."""


GROUND_TRUTH_KINDS = frozenset({EvidenceKind.EXPERIMENTAL_MEASUREMENT})
"""Kinds that may legitimately be used as ground truth for model evaluation.
Anatomy is a structural observation, not ground truth for dynamics/causality."""
