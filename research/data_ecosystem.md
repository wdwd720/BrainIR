# Fly connectome data ecosystem — condensed conclusions for BrainIR (2026-09-22)

The full survey with sources is in [`connectome_ecosystem_survey.md`](connectome_ecosystem_survey.md). This file
keeps only the conclusions that shape BrainIR's canonical model. See also [`docs/schema.md`](../docs/schema.md).

## Datasets

| dataset | specimen | coverage | native ID | version handle | primary access | license |
|---|---|---|---|---|---|---|
| **MaleCNS v1.0** (primary) | male #1 | whole CNS | neuPrint bodyId (int64) | `male-cns:v1.0` (neuPrint) + GCS generation | GCS flat files (acquired); neuPrint (token) | CC-BY |
| optic-lobe v1.1 | **same fly as MaleCNS** | right OL | bodyId, **shared with MaleCNS** | `optic-lobe:v1.1` | neuPrint, GCS | CC-BY |
| MANC v1.2.x | male #2 | VNC | bodyId (collides numerically with MaleCNS: 19,344 shared integers, *different* neurons) | `manc:v1.0`, `v1.2.1`, `v1.2.3` (annotation patch, same UUID) | neuPrint; GCS flat files (v1.0; v1.2 synapses) | CC-BY |
| FlyWire/FAFB 783 | female | brain | CAVE root_id (changes with every edit) | materialization 630 / 783 (+ timestamp); synapse set Buhmann vs Princeton | CAVE public, Zenodo, Codex | flywire.ai says CC BY-NC 4.0, Zenodo says CC-BY 4.0 (**conflict**) |
| BANC 888 | female | brain + VNC | CAVE root_id; 40% of proofread neurons changed ID 626→888 | materialization 626/850/888(/890); synapses v2 (size≥5) / v3 (size≥10) | Dataverse, GCS, Codex, CAVE | CC-BY 4.0 |
| FANC | female | VNC | CAVE root_id + supervoxel anchors | CAVE materializations (1116 used for matching; public dumps 1237, 1444) | restricted CAVE; public GCS dumps | not found |
| hemibrain v1.2.1 | female | ~½ central brain | bodyId | `hemibrain:v1.2.1` | neuPrint, GCS | CC-BY (neo4j zip carries a BSD-style text) |

## Facts that constrain the schema
1. **IDs must be namespaced by dataset *and* version.** Integer body IDs collide across datasets (MANC vs MaleCNS).
   CAVE root IDs change with proofreading, so pin the materialization version and keep stable anchors
   (supervoxel ID, nucleus ID, anchor point).
2. **Specimen ≠ dataset.** optic-lobe and MaleCNS are the same animal and share body IDs for the same neurons.
3. **The synapse detector and its filter are part of the version.** Examples:
   - FAFB 783 exists with two synapse sets;
   - BANC has v2 and v3 synapse sets;
   - Janelia exports use conf ≥ 0.5 on both sides, and neuPrint `weightHP` uses post ≥ 0.7.
4. **Edge thresholds differ by source.** FAFB uses ≥ 5. Codex uses ≥ 3 for BANC, ≥ 1 for MANC, and **≥ 5 for MCNS**
   (verified: Codex's 6,242,118 MCNS v1.0 connections equal BrainIR's count of neuron edges with ≥ 5 synapses).
   → Store edges unthresholded and apply thresholds at query time.
5. **Neuropil assignment rules differ.**
   - neuPrint assigns an edge's ROI by the **postsynaptic** site.
   - FlyWire assigns by the **presynaptic** location, with nearest-neuropil fallback.
   - The ROI vocabularies and hierarchies differ, and MaleCNS's hierarchy is a DAG.
6. **NT predictions differ in class set and aggregation.**

   | source | classes | per-neuron aggregation |
   |---|---|---|
   | MaleCNS | 7 + unclear | argmax with confusion-calibrated confidence; body, type and consensus levels |
   | FAFB | 6 | mean probability |
   | BANC | 8 | summed probability |
   | MANC | 3 + unknown | — |

   → Store the level (body/type/consensus), class set and method alongside the label.
7. **Sides.** There are soma side and root/nerve-entry side, and vocabularies differ (L/R/M, left/right/center,
   RHS/LHS/BIL/MID). FAFB image coordinates are mirrored relative to its (correct) labels.
8. **No canonical cross-dataset type ontology exists.**
   - FBbt covers a minority of types.
   - Matches are many-to-many, with method and confidence.
   - MaleCNS is a "rosetta stone": it carries `flywireType`, `hemibrainType`, `mancType` and `mancBodyid`.
9. **No dataset contains gap junctions.** Only MANC has neuron-level `transmission: electrical` labels.
10. **Access drift.**
    - neuPrint invalidated all API tokens in August 2026 (new auth system).
    - Codex needs sign-in and a token for downloads.
    - Several CAVE datastacks are restricted.
    → Keep ingestion connectors separate from the canonical store, and record the access channel in provenance.

## How the Phase 0 model accommodates them
- `neuron_uid = "<dataset>:<version>:<native_id>"`. Integers are used only within one partition.
- `DatasetVersion` records the specimen, coverage, synapse-confidence thresholds, coordinate space and voxel size,
  access URLs, checksums, citation and license.
- Anatomy (`synapse_count`), ML predictions (NT), curated annotations and rule-based hypotheses (sign) are separate
  columns with per-column `evidence` metadata. Model parameters are a separate record type.
- Per-edge neuropil counts sit in their own long table, which allows other assignment rules and ROI sets.
- Planned for multi-dataset phases (not built yet):
  - `neuron_anchors` (CAVE supervoxel/nucleus anchors per materialization);
  - `id_lineage` (old→new IDs across versions);
  - `cross_dataset_matches` (many-to-many with method and score);
  - `canonical_types` (synonyms, FBbt IDs);
  - controlled-vocabulary mapping tables (raw → canonical) with provenance.
