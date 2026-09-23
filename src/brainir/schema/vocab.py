"""Controlled vocabularies and versioned rules.

Anything here that encodes a *biological assumption* (notably the
neurotransmitter -> sign rule) is versioned and must be cited by ID wherever
it is used, so results can always be traced back to the assumption set.
"""

from __future__ import annotations

from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Neurotransmitters
# ---------------------------------------------------------------------------
NT_CLASSES: tuple[str, ...] = (
    "acetylcholine", "gaba", "glutamate", "dopamine", "serotonin", "octopamine", "histamine",
)
NT_UNCLEAR = "unclear"
"""Source reports a prediction but it is ambiguous. Distinct from null (= no prediction)."""
NT_UNKNOWN = "unknown"
"""The classifier's explicit 'unknown/other' class won (MANC predictedNt). Distinct from 'unclear' and from null."""
NT_VALUES: frozenset[str] = frozenset((*NT_CLASSES, NT_UNCLEAR, NT_UNKNOWN))


@dataclass(frozen=True)
class SignRule:
    nt: str
    sign: int | None
    """+1 excitatory, -1 inhibitory, None = no defensible fast sign."""
    rule_class: str
    """'conventional_fast' | 'context_dependent' | 'modulatory' | 'unknown'."""
    rationale: str


SIGN_RULE_ID = "brainir.sign.conventional-v1"
"""Identifier of the NT->sign rule set below. Cite it with every sign value."""

SIGN_RULES: dict[str, SignRule] = {r.nt: r for r in (
    SignRule("acetylcholine", +1, "conventional_fast",
             "Fast cholinergic transmission in the fly CNS is predominantly nicotinic (excitatory); "
             "muscarinic receptors (mAChR-A/B) can mediate inhibitory/modulatory effects."),
    SignRule("gaba", -1, "conventional_fast",
             "GABA-A (Rdl) chloride channels and GABA-B receptors are inhibitory."),
    SignRule("glutamate", -1, "context_dependent",
             "Central glutamatergic inhibition via GluCl-alpha chloride channels is common in flies, "
             "but ionotropic (excitatory) glutamate receptors also exist (e.g. NMJ, some central synapses)."),
    SignRule("histamine", -1, "context_dependent",
             "Histamine-gated chloride channels (HisCl1, ort) are inhibitory; mostly visual system."),
    SignRule("dopamine", None, "modulatory", "Metabotropic neuromodulator; no fast sign."),
    SignRule("serotonin", None, "modulatory", "Metabotropic neuromodulator (5-HT7 etc. aside); no fast sign."),
    SignRule("octopamine", None, "modulatory", "Metabotropic neuromodulator; no fast sign."),
    SignRule(NT_UNCLEAR, None, "unknown", "Neurotransmitter prediction ambiguous."),
    SignRule(NT_UNKNOWN, None, "unknown", "Classifier assigned the 'unknown' class."),
)}


def sign_for_nt(nt: str | None) -> SignRule | None:
    """Apply SIGN_RULE_ID. Returns None when there is no NT at all."""
    if nt is None:
        return None
    return SIGN_RULES.get(nt)


# ---------------------------------------------------------------------------
# Proofreading status (Janelia DVID/neuPrint conventions)
# Ordered from least to most complete; copied from flyem-snapshot
# (flyem_snapshot/outputs/neuprint/annotations.py, NEUPRINT_STATUSLABEL_TO_STATUS),
# whose key order equals neuclease DEFAULT_BODY_STATUS_CATEGORIES.
# ---------------------------------------------------------------------------
STATUS_LABEL_TO_NEUPRINT_STATUS: dict[str, str] = {
    "Unimportant": "Unimportant", "Glia": "Glia", "Hard to trace": "Orphan",
    "Orphan-artifact": "Orphan", "Orphan": "Orphan", "Orphan hotknife": "Orphan",
    "Putative Leaves": "", "Out of scope": "", "Not examined": "", "": "",
    "0.5assign": "Assign",
    "Anchor": "Anchor", "Cleaved Anchor": "Anchor", "Will be merged": "Anchor",
    "Partially traced": "Anchor", "Sensory Anchor": "Anchor", "Cervical Anchor": "Anchor",
    "Soma Anchor": "Anchor", "Examined Soma Anchor": "Anchor", "Primary Anchor": "Anchor",
    "Leaves": "Traced", "PRT Orphan": "Traced", "Reviewed": "Traced",
    "Prelim Roughly traced": "Traced", "RT Hard to trace": "Traced", "RT Orphan": "Traced",
    "Roughly traced": "Traced", "Traced in ROI": "Traced", "Traced": "Traced", "Finalized": "Traced",
}
STATUS_LABEL_ORDER: tuple[str, ...] = tuple(STATUS_LABEL_TO_NEUPRINT_STATUS)
MIN_SIGNIFICANT_STATUS_LABEL = "Sensory Anchor"  # flyem-snapshot 'significant' flat exports
MIN_TRACED_STATUS_LABEL = "Leaves"                # flyem-snapshot 'traced' flat exports
NEUPRINT_STATUSES = frozenset({"Traced", "Anchor", "Orphan", "Assign", "Unimportant", "Glia"})


def status_label_rank(label: str | None) -> int | None:
    if label is None:
        return None
    try:
        return STATUS_LABEL_ORDER.index(label)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Sides / hemispheres
# ---------------------------------------------------------------------------
SIDES = frozenset({"L", "R", "M", "B"})
"""L/R = left/right from the animal's perspective; M = midline (unpaired); B = bilateral (MANC root side 'BIL')."""


def normalize_side(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if v in SIDES:
        return v
    # MaleCNS uses L/R/M; MANC uses LHS/RHS/Midline (and BIL/MID for bilateral/midline sensory roots)
    return {"left": "L", "right": "R", "center": "M", "centre": "M", "midline": "M",
            "lhs": "L", "rhs": "R", "mid": "M", "bil": "B"}.get(v.lower())


UNASSIGNED_NEUROPIL = "<unassigned>"
"""Synapses that fall outside every primary neuropil ROI."""


# ---------------------------------------------------------------------------
# Coarse functional role (cross-dataset normalisation of the source's superclass / class vocabulary)
# ---------------------------------------------------------------------------
ROLE_RULE_ID = "brainir.role.v1"
"""Identifier of the superclass -> role_class mapping below. Roles are a *relabeling* of curated source
classes (same evidence kind), used so that datasets with different vocabularies (MaleCNS 'superclass',
MANC 'class') can be compared and checked with one set of rules."""

ROLE_CLASSES: tuple[str, ...] = (
    "descending", "ascending", "sensory_ascending", "sensory_descending", "efferent", "endocrine",
    "vnc_intrinsic", "vnc_motor", "vnc_sensory",
    "cb_intrinsic", "cb_motor", "cb_sensory", "ol_intrinsic", "ol_sensory", "visual_projection", "visual_centrifugal",
    "glia", "unknown",
)

_ROLE_MAP: dict[str, str] = {
    # MaleCNS superclass vocabulary
    "descending_neuron": "descending", "ascending_neuron": "ascending",
    "sensory_ascending": "sensory_ascending", "sensory_descending": "sensory_descending",
    "vnc_intrinsic": "vnc_intrinsic", "vnc_motor": "vnc_motor", "vnc_sensory": "vnc_sensory",
    "vnc_efferent": "efferent", "cb_efferent": "efferent", "efferent_ascending": "efferent",
    "efferent_descending": "efferent", "vnc_endocrine": "endocrine", "cb_endocrine": "endocrine", "ENS": "endocrine",
    "cb_intrinsic": "cb_intrinsic", "cb_motor": "cb_motor", "cb_sensory": "cb_sensory",
    "ol_intrinsic": "ol_intrinsic", "ol_sensory": "ol_sensory",
    "visual_projection": "visual_projection", "visual_centrifugal": "visual_centrifugal",
    # MANC class vocabulary (v1.0 uses spaces, v1.2.x tags use underscores; both normalised to underscores)
    "intrinsic_neuron": "vnc_intrinsic", "motor_neuron": "vnc_motor", "neck_motor_neuron": "vnc_motor",
    "sensory_neuron": "vnc_sensory", "efferent_neuron": "efferent",
    "glia": "glia", "interneuron_tbd": "unknown", "sensory_tbd": "unknown", "tbd": "unknown",
}


def normalize_class_label(value: str | None) -> str | None:
    """Source class label with spaces -> underscores (MANC v1.0 'descending neuron' == v1.2.x 'descending_neuron')."""
    if value is None or (isinstance(value, float) and value != value):
        return None
    v = str(value).strip().replace(" ", "_")
    return v or None


def role_class_for(super_class: str | None) -> str | None:
    """Apply ROLE_RULE_ID. Returns None when the source has no class; 'unknown' for TBD-style labels.
    MaleCNS '<class>_tbc' ('to be confirmed') labels map like their base class."""
    v = normalize_class_label(super_class)
    if v is None:
        return None
    key = v.lower() if v != "ENS" else v
    if key.endswith("_tbc"):
        key = key[:-4]
    return _ROLE_MAP.get(key, "unknown")
