# Notes — MaleCNS dataset paper (Berg, Beckett, Costa, Schlegel, Januszewski, … Rubin, Jefferis)

- **Preprint:** "Sexual dimorphism in the complete connectome of the *Drosophila* male central nervous system",
  bioRxiv 10.1101/2025.10.09.680999 (v2, 2025-10-30), CC-BY 4.0.
- **Journal version:** "Sexual dimorphism in the complete *Drosophila* male central nervous system connectome", *Cell*
  (2026), doi:10.1016/j.cell.2026.08.015, PMID 42691995. First published 2026-09-01; announced on
  male-cns.janelia.org on 2026-09-03.

Quotes below come from the **preprint v2** full text (bioRxiv HTML, retrieved 2026-09-22). The preprint predates
the v1.0 data release (2026-06-08), so the counts it reports describe roughly v0.9. **The Cell version was not read**
(it may be paywalled; to do). Its numbers may differ slightly.

## Scale and definitions (as reported)
- "46 million presynapses connected to 312 million PSDs were automatically detected with an average
  precision/recall of 0.82/0.81."
  - v1.0 neuPrint :Meta gives totalPreCount 45,656,140 and totalPostCount 311,833,243.
- "we identified, proofread and annotated 166,691 neurons (including sensory axons)".
  - v1.0: 166,700 bodies with a superclass. Codex lists MCNS v1.0 with 166,700 neurons.
- **Neuron definition** (Methods, *Superclass*): "Bodies in the dataset are defined as neurons if they have a
  superclass. Bodies without one are fragments of neurons."
  - BrainIR adopts this definition for its `neurons` table.
- "The neuron segmentation and synaptic connections jointly define a connectome graph containing 25.6M edges between
  166,391 neurons."
  - v1.0 BrainIR build: 25,582,938 edges among 166,700 neurons, of which 166,483 have ≥ 1 edge.
- **Completeness**
  - "94% pre- and 42% postsynaptic completion rates in neuropils".
  - "the fraction of synaptic connections for which both pre- and postsynaptic sites belong to a proofread neuron …
    is 40.1%".
  - v1.0 BrainIR: 124,177,617 of 311,833,243 connections are neuron→neuron (39.8%).
- **Proofreading coverage**
  - "We proofread all fragments from the initial segmentation with > 100 synaptic connections"; 98.9% of 141,780
    neuron-associated nuclei are part of a proofread neuron.
  - 84.6 million orphan fragments remain; 5,329 of them have ≥ 100 synaptic partners.
- **Typing:** "we defined 11,691 unique cell types"; 97.5% of neurons are matched to FAFB/FlyWire, hemibrain and/or MANC.

## Synapse detection
- The optic-lobe networks were fine-tuned for the CNS. Validation used 114 cubes of 300³ voxels (81 ROIs), and a
  lamina-specific T-bar detector was added.
- "generally above 0.8 recall for T-bars alone and 0.7 recall for synapses".
- The paper text does not state the confidence thresholds. The neuPrint :Meta does:
  - postHighAccuracyThreshold = 0.5, which defines `weight`;
  - postHPThreshold = 0.7, which defines `weightHP`.
- The flat files are pre-filtered at conf ≥ 0.5 on **both** the T-bar and the PSD (flyem-snapshot
  `_filter_for_confidence`).

## Neurotransmitters (Methods, verbatim)
- **Ground truth:** "data from the literature, as well as experiments run at Janelia … ternary form … The cell types
  from the resource were matched to male CNS cell types according to the flywireType and mancType neuprint columns".
- **Model:** "a ResNet50 … predict neurotransmitter identity of a pre-synapse … 7 neurotransmitters".
- **Neuron-level rule:** "Neurons or fragments with fewer than 50 presynaptic sites or those whose
  predictedNtConfidence is below 0.5 are given predictedNt of unclear. Similarly, cell types with fewer than 100
  presynapses … or … celltypePredictedNtConfidence is below 0.5 are given a celltypePredictedNt of unclear."
- **Consensus:** "the consensusNt property is a copy of celltypePredictedNt, except in cases where experimental
  ground truth for the cell type is available to override the model prediction. Additionally, all octopamine and
  serotonin results are set to unclear in consensusNt … The consensusNt is the recommended property to use in most
  analyses."
- **Observed deviation in the v1.0 release** (BrainIR check `consistency.nt_consensus_rule_*`):
  - (i) Untyped bodies take the *body-level* prediction, with octopamine/serotonin set to unclear. This holds for
    all 1,671,072 untyped bodies.
  - (ii) 4,420 typed bodies across 91 types carry expert overrides that are **absent from the `ground_truth`
    column**:
    - Kenyon cells: model says dopamine, consensus says acetylcholine (4,053 bodies);
    - motor neurons: unclear → glutamate;
    - `EN00B*` efferents: → octopamine;
    - DNg28: → serotonin.
  - Consensus is therefore partly a curated literature label, not purely a model output. BrainIR stores it as
    `nt_consensus` (ML prediction plus curation) and keeps body-level, type-level and literature labels separate.

## Annotations
- **Superclass prefixes:** `ol_`, `cb_`, `vnc_`.
- **Hemilineage:** transferred from FAFB/FlyWire, hemibrain and MANC. There are two nomenclatures:
  - `itoleeHl` (brain);
  - `trumanHl` (VNC). SEZ and descending neurons often carry both.
- **Cross-dataset types:** `flywireType`, `hemibrainType`, `mancType`, `mancGroup`. The primary `type` "represents
  the consensus type across all matched types".
- **`group`:** a finer grouping than type. It usually groups left/right homologues. For the VNC, "serially
  homologous neurons may have the same type but different groups".
- **`instance`:** type + somaSide, or rootSide for sensory neurons.

## Data availability
- **Bulk data:** `gs://flyem-male-cns` (landing page https://male-cns.janelia.org). The paper's derived products are
  at https://github.com/flyconnectome/2025malecns.
- **License:** CC-BY (male-cns.janelia.org).
