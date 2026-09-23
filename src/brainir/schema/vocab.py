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
NT_VALUES: frozenset[str] = frozenset((*NT_CLASSES, NT_UNCLEAR))


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
SIDES = frozenset({"L", "R", "M"})
"""L/R = left/right from the animal's perspective; M = midline (unpaired)."""


def normalize_side(value: str | None) -> str | None:
    if value is None:
        return None
    v = str(value).strip()
    if v in SIDES:
        return v
    return {"left": "L", "right": "R", "center": "M", "centre": "M", "midline": "M"}.get(v.lower())


UNASSIGNED_NEUROPIL = "<unassigned>"
"""Synapses that fall outside every primary neuropil ROI."""
