"""Canonical BrainIR table schemas (Apache Arrow).

Every column carries field metadata:

* ``evidence``    — an :class:`~brainir.schema.evidence.EvidenceKind`
* ``description`` — what the value means (including caveats)
* ``unit``        — optional physical/count unit

Tables are stored per (dataset, version) partition; within a partition the
integer ``source_id``/``pre_id``/``post_id`` columns are the dataset-native
IDs (e.g. neuPrint bodyId). The globally unique, stable identifier of a
neuron is ``neuron_uid = "<dataset>:<version>:<source_id>"`` — IDs are only
stable *within* a release (proofreading merges/splits bodies between
releases), which is why the version is part of the key.
"""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa

from .evidence import EvidenceKind as E

SCHEMA_VERSION = "0.1.0"


@dataclass(frozen=True)
class Col:
    name: str
    type: pa.DataType
    evidence: E
    description: str
    nullable: bool = True
    unit: str | None = None

    def to_field(self) -> pa.Field:
        md = {"evidence": str(self.evidence), "description": self.description}
        if self.unit:
            md["unit"] = self.unit
        return pa.field(self.name, self.type, nullable=self.nullable, metadata=md)


@dataclass(frozen=True)
class TableSpec:
    name: str
    description: str
    columns: tuple[Col, ...]
    primary_key: tuple[str, ...]
    sort_by: tuple[str, ...]

    @property
    def schema(self) -> pa.Schema:
        return pa.schema([c.to_field() for c in self.columns],
                         metadata={"brainir_table": self.name, "brainir_schema_version": SCHEMA_VERSION})

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]

    def col(self, name: str) -> Col:
        for c in self.columns:
            if c.name == name:
                return c
        raise KeyError(name)


STR = pa.string()
DSTR = pa.dictionary(pa.int32(), pa.string())  # low-cardinality strings

NEURONS = TableSpec(
    name="neurons",
    description="One row per neuron as defined by the source. MaleCNS: 'Bodies in the dataset are defined as "
                "neurons if they have a superclass' (Berg et al., Methods). Other synaptic bodies are fragments.",
    primary_key=("source_id",),
    sort_by=("source_id",),
    columns=(
        Col("neuron_uid", STR, E.IDENTIFIER, "Globally unique stable ID '<dataset>:<version>:<source_id>'.", False),
        Col("dataset", DSTR, E.IDENTIFIER, "Dataset name (e.g. 'male-cns').", False),
        Col("dataset_version", DSTR, E.IDENTIFIER, "Release/version (e.g. 'v1.0').", False),
        Col("source_id", pa.int64(), E.IDENTIFIER, "Dataset-native neuron ID (neuPrint bodyId). Stable only within this version.", False),
        Col("cell_type", STR, E.CURATED_ANNOTATION, "Primary cell type label from the source ('type')."),
        Col("instance", STR, E.CURATED_ANNOTATION, "Source instance label (usually type + side, e.g. 'DNp01(GF)_R')."),
        Col("super_class", DSTR, E.CURATED_ANNOTATION, "Coarse class (e.g. descending_neuron, vnc_intrinsic)."),
        Col("cell_class", STR, E.CURATED_ANNOTATION, "Intermediate class ('class' in MaleCNS)."),
        Col("sub_class", STR, E.CURATED_ANNOTATION, "Finer class ('subclass' in MaleCNS)."),
        Col("hemilineage_ito_lee", DSTR, E.CURATED_ANNOTATION, "Hemilineage in Ito/Lee (brain) nomenclature ('itoleeHl')."),
        Col("hemilineage_truman", DSTR, E.CURATED_ANNOTATION,
            "Hemilineage in Truman (VNC/SEZ) nomenclature, e.g. '17A' ('trumanHl'). Parallel to, not "
            "exclusive of, hemilineage_ito_lee (SEZ/descending neurons often carry both)."),
        Col("soma_side", DSTR, E.CURATED_ANNOTATION, "Side of the soma: L, R or M (midline)."),
        Col("root_side", DSTR, E.CURATED_ANNOTATION, "Side of entry root (sensory/afferent neurons without soma in volume)."),
        Col("side", DSTR, E.DERIVED_ANATOMY, "soma_side if known, else root_side."),
        Col("side_basis", DSTR, E.DERIVED_ANATOMY, "'soma' or 'root' — which field 'side' came from."),
        Col("soma_neuromere", DSTR, E.CURATED_ANNOTATION, "Neuromere containing the soma (e.g. T1, T2, T3, A1, CG)."),
        Col("soma_x", pa.int64(), E.CURATED_ANNOTATION, "Soma location x.", unit="voxel(8nm), dataset EM space"),
        Col("soma_y", pa.int64(), E.CURATED_ANNOTATION, "Soma location y.", unit="voxel(8nm), dataset EM space"),
        Col("soma_z", pa.int64(), E.CURATED_ANNOTATION, "Soma location z.", unit="voxel(8nm), dataset EM space"),
        Col("animal_sex", DSTR, E.PROVENANCE, "Sex of the imaged animal (dataset-level fact).", False),
        Col("status", DSTR, E.CURATED_ANNOTATION, "neuPrint proofreading status (Traced/Anchor/Orphan/Assign/...)."),
        Col("status_label", DSTR, E.CURATED_ANNOTATION, "Fine-grained DVID status label (e.g. 'Roughly traced')."),
        Col("is_traced", pa.bool_(), E.DERIVED_ANATOMY, "status == 'Traced' (statusLabel >= 'Leaves').", False),
        Col("neuprint_neuron_label", pa.bool_(), E.CURATED_ANNOTATION,
            "Body carries the neuPrint :Neuron label (neuPrint's own, broader node criterion).", False),
        Col("n_pre", pa.int32(), E.EM_RECONSTRUCTION, "Presynaptic sites (T-bars) with confidence >= threshold.", unit="count"),
        Col("n_post", pa.int32(), E.EM_RECONSTRUCTION, "Postsynaptic densities (PSDs) with confidence >= threshold.", unit="count"),
        Col("n_downstream", pa.int64(), E.EM_RECONSTRUCTION, "Outgoing synaptic connections (T-bar->PSD pairs) to ANY segment.", unit="count"),
        Col("n_upstream", pa.int64(), E.EM_RECONSTRUCTION, "Incoming synaptic connections from ANY segment.", unit="count"),
        Col("n_downstream_to_neurons", pa.int64(), E.DERIVED_ANATOMY, "Outgoing connections whose partner is in this neuron table.", unit="count"),
        Col("n_upstream_from_neurons", pa.int64(), E.DERIVED_ANATOMY, "Incoming connections whose partner is in this neuron table.", unit="count"),
        Col("size_voxels", pa.int64(), E.EM_RECONSTRUCTION, "Segment size.", unit="voxel(8nm)^3"),
        Col("nt_consensus", DSTR, E.ML_PREDICTION,
            "Source 'consensusNt' (recommended by the source): cell-type prediction (untyped bodies: body prediction), "
            "overridden by literature/expert labels, with model octopamine/serotonin calls set to 'unclear'. "
            "Mixes ML output with curation; not physiology."),
        Col("nt_body_prediction", DSTR, E.ML_PREDICTION, "Neurotransmitter predicted from this body's T-bars."),
        Col("nt_body_confidence", pa.float64(), E.ML_PREDICTION, "Model confidence for nt_body_prediction.", unit="probability"),
        Col("nt_body_n_tbars", pa.int32(), E.ML_PREDICTION, "Number of T-bar predictions aggregated for this body.", unit="count"),
        Col("nt_type_prediction", DSTR, E.ML_PREDICTION, "Neurotransmitter predicted by aggregating all bodies of the cell type."),
        Col("nt_type_confidence", pa.float64(), E.ML_PREDICTION, "Model confidence for nt_type_prediction.", unit="probability"),
        Col("nt_type_n_tbars", pa.int32(), E.ML_PREDICTION, "Number of T-bar predictions aggregated for the cell type.", unit="count"),
        Col("nt_literature_label", DSTR, E.LITERATURE_LABEL, "Known neurotransmitter of the cell type from literature ('ground_truth' in source)."),
        Col("group_id", pa.int64(), E.CURATED_ANNOTATION, "Source homolog group ID (bilateral/serial partners share a group)."),
        Col("synonyms", STR, E.CURATED_ANNOTATION, "Alternative names from the literature."),
        Col("flywire_type", STR, E.CURATED_ANNOTATION, "Matched FlyWire (FAFB) cell type."),
        Col("hemibrain_type", STR, E.CURATED_ANNOTATION, "Matched hemibrain cell type."),
        Col("manc_type", STR, E.CURATED_ANNOTATION, "Matched MANC cell type."),
        Col("manc_body_id", pa.int64(), E.CURATED_ANNOTATION, "Matched MANC bodyId."),
        Col("dimorphism", DSTR, E.CURATED_ANNOTATION, "Sexual dimorphism annotation."),
        Col("fru_dsx", DSTR, E.CURATED_ANNOTATION, "fruitless/doublesex expression annotation."),
    ),
)

NEURON_ANNOTATIONS_SOURCE = "neuron_annotations_source"
"""Name of the verbatim (typed) copy of all source annotation columns; its
schema is source-specific and recorded in the manifest."""

CONNECTIONS = TableSpec(
    name="connections",
    description="Directed neuron->neuron connections aggregated from synapses (both endpoints in NEURONS).",
    primary_key=("pre_id", "post_id"),
    sort_by=("pre_id", "post_id"),
    columns=(
        Col("pre_id", pa.int64(), E.IDENTIFIER, "Presynaptic neuron source_id.", False),
        Col("post_id", pa.int64(), E.IDENTIFIER, "Postsynaptic neuron source_id.", False),
        Col("synapse_count", pa.int32(), E.EM_RECONSTRUCTION,
            "Number of synaptic connections = T-bar->PSD pairs (polyadic synapses: one T-bar may contribute "
            "several pairs) with confidence >= threshold (neuPrint 'weight'). Anatomical, NOT a physiological strength.",
            False, unit="count"),
        Col("synapse_count_hp", pa.int32(), E.EM_RECONSTRUCTION,
            "High-precision subset: pairs whose PSD confidence >= the HP threshold (0.7 for MaleCNS; neuPrint "
            "'weightHP'). Boundary: confidences are stored as float32 and compared in float64, so a PSD stored as "
            "float32(0.7)=0.69999999 is excluded.", False, unit="count"),
        Col("is_autapse", pa.bool_(), E.DERIVED_ANATOMY, "pre_id == post_id (self-connection kept intentionally).", False),
        Col("dominant_neuropil", DSTR, E.DERIVED_ANATOMY, "Primary neuropil holding the most PSDs of this connection (ties: lexicographic)."),
        Col("dominant_neuropil_fraction", pa.float32(), E.DERIVED_ANATOMY, "Fraction of synapse_count in dominant_neuropil.", unit="fraction"),
        Col("n_neuropils", pa.int16(), E.DERIVED_ANATOMY, "Number of distinct neuropils (incl. unassigned) the connection spans.", False, unit="count"),
    ),
)

CONNECTION_NEUROPILS = TableSpec(
    name="connection_neuropils",
    description="Per-connection synapse counts by primary neuropil of the POSTsynaptic site (neuPrint convention). "
                "Counts sum exactly to connections.synapse_count; remainder outside primary ROIs uses '<unassigned>'.",
    primary_key=("pre_id", "post_id", "neuropil"),
    sort_by=("pre_id", "post_id", "neuropil"),
    columns=(
        Col("pre_id", pa.int64(), E.IDENTIFIER, "Presynaptic neuron source_id.", False),
        Col("post_id", pa.int64(), E.IDENTIFIER, "Postsynaptic neuron source_id.", False),
        Col("neuropil", DSTR, E.EM_RECONSTRUCTION, "Primary neuropil ROI (or '<unassigned>').", False),
        Col("synapse_count", pa.int32(), E.EM_RECONSTRUCTION, "Synaptic connections of this pair located in this neuropil.", False, unit="count"),
    ),
)

NEURON_NEUROPILS = TableSpec(
    name="neuron_neuropils",
    description="Per-neuron pre/post synapse counts by primary neuropil (from neuPrint roiInfo); "
                "remainder outside primary ROIs uses '<unassigned>'.",
    primary_key=("source_id", "neuropil"),
    sort_by=("source_id", "neuropil"),
    columns=(
        Col("source_id", pa.int64(), E.IDENTIFIER, "Neuron source_id.", False),
        Col("neuropil", DSTR, E.EM_RECONSTRUCTION, "Primary neuropil ROI (or '<unassigned>').", False),
        Col("n_pre", pa.int32(), E.EM_RECONSTRUCTION, "T-bars of this neuron in this neuropil.", False, unit="count"),
        Col("n_post", pa.int32(), E.EM_RECONSTRUCTION, "PSDs of this neuron in this neuropil.", False, unit="count"),
    ),
)

NEUROPILS = TableSpec(
    name="neuropils",
    description="Neuropil ROI catalogue (all ROIs defined by the source). The source hierarchy is a DAG: some ROIs "
                "(e.g. CA(L) under both CentralBrain and MB(L)) have several parents.",
    primary_key=("name",),
    sort_by=("name",),
    columns=(
        Col("name", STR, E.IDENTIFIER, "ROI name as used by the source.", False),
        Col("parent", STR, E.CURATED_ANNOTATION, "Authoritative single parent (source roiInfo 'parent'; else first "
                                                   "hierarchy parent)."),
        Col("all_parents", pa.list_(pa.string()), E.CURATED_ANNOTATION, "Every parent of the ROI in the hierarchy DAG."),
        Col("depth", pa.int16(), E.CURATED_ANNOTATION, "Minimum depth in the hierarchy (root = 0); null if absent."),
        Col("in_hierarchy", pa.bool_(), E.CURATED_ANNOTATION, "ROI appears in the source hierarchy (some have "
                                                             "statistics only).", False),
        Col("top_level_region", DSTR, E.CURATED_ANNOTATION, "Depth-1 ancestor (e.g. CentralBrain, Optic(L), CV, VNC)."),
        Col("is_primary", pa.bool_(), E.CURATED_ANNOTATION, "Member of the non-overlapping primary ROI partition.", False),
        Col("is_nerve", pa.bool_(), E.CURATED_ANNOTATION, "ROI is a nerve (not neuropil).", False),
        Col("side", DSTR, E.DERIVED_ANATOMY, "Side parsed from the name suffix '(L)'/'(R)'; null if unpaired."),
        Col("n_pre_total", pa.int64(), E.EM_RECONSTRUCTION, "All T-bars in the ROI.", unit="count"),
        Col("n_post_total", pa.int64(), E.EM_RECONSTRUCTION, "All PSDs in the ROI.", unit="count"),
    ),
)

SYNAPSES = TableSpec(
    name="synapses",
    description="Individual synaptic connections (T-bar -> PSD pairs). Stored for subsets only in Phase 0.",
    primary_key=("x_pre", "y_pre", "z_pre", "x_post", "y_post", "z_post"),
    sort_by=("pre_id", "post_id", "z_post", "y_post", "x_post"),
    columns=(
        Col("pre_id", pa.int64(), E.IDENTIFIER, "Presynaptic body source_id.", False),
        Col("post_id", pa.int64(), E.IDENTIFIER, "Postsynaptic body source_id.", False),
        Col("x_pre", pa.int32(), E.EM_RECONSTRUCTION, "T-bar x.", False, unit="voxel(8nm)"),
        Col("y_pre", pa.int32(), E.EM_RECONSTRUCTION, "T-bar y.", False, unit="voxel(8nm)"),
        Col("z_pre", pa.int32(), E.EM_RECONSTRUCTION, "T-bar z.", False, unit="voxel(8nm)"),
        Col("x_post", pa.int32(), E.EM_RECONSTRUCTION, "PSD x.", False, unit="voxel(8nm)"),
        Col("y_post", pa.int32(), E.EM_RECONSTRUCTION, "PSD y.", False, unit="voxel(8nm)"),
        Col("z_post", pa.int32(), E.EM_RECONSTRUCTION, "PSD z.", False, unit="voxel(8nm)"),
        Col("conf_pre", pa.float32(), E.ML_PREDICTION, "Synapse detector confidence of the T-bar.", False, unit="probability"),
        Col("conf_post", pa.float32(), E.ML_PREDICTION, "Synapse detector confidence of the PSD.", False, unit="probability"),
        Col("neuropil", DSTR, E.EM_RECONSTRUCTION, "Primary neuropil of the PSD (or '<unassigned>').", False),
    ),
)

CANONICAL_TABLES: dict[str, TableSpec] = {t.name: t for t in (
    NEURONS, CONNECTIONS, CONNECTION_NEUROPILS, NEURON_NEUROPILS, NEUROPILS, SYNAPSES)}


def conform(table: pa.Table, spec: TableSpec) -> pa.Table:
    """Cast/reorder a table to the canonical schema, failing loudly on problems.

    * missing or extra columns -> ValueError
    * unsafe casts (overflow, lossy float->int) -> pyarrow error
    * nulls in non-nullable columns -> ValueError
    """
    names = set(table.column_names)
    expected = set(spec.column_names)
    if names != expected:
        raise ValueError(f"{spec.name}: missing={sorted(expected - names)} extra={sorted(names - expected)}")
    arrays = []
    for c in spec.columns:
        arr = table.column(c.name)
        if not c.nullable and arr.null_count:
            raise ValueError(f"{spec.name}.{c.name}: {arr.null_count} nulls in non-nullable column")
        arrays.append(_cast(arr, c.type))
    return pa.Table.from_arrays(arrays, schema=spec.schema)


def _cast(arr: pa.ChunkedArray, target: pa.DataType) -> pa.ChunkedArray:
    """Safe cast; dictionary targets are built by explicit dictionary encoding."""
    if pa.types.is_dictionary(target):
        if pa.types.is_dictionary(arr.type):
            arr = arr.cast(arr.type.value_type)
        values = arr.cast(target.value_type, safe=True)
        return values.dictionary_encode().cast(target)
    if pa.types.is_floating(target) and pa.types.is_floating(arr.type):
        return arr.cast(target, safe=False)  # float64 -> float32 rounding is intended
    return arr.cast(target, safe=True)
