<!--
Provenance: compiled 2026-09-22 by a Claude research agent for BrainIR Phase 0 from the primary sources linked
inline ("observed" = checked against a public file that day). Condensed conclusions and the schema decisions
derived from it are in research/data_ecosystem.md and docs/schema.md. Facts may drift (Codex/BANC files are
regenerated); re-verify before relying on a number.
-->

# The Drosophila connectome ecosystem outside MaleCNS: a data-model survey for BrainIR

Prepared 2026-09-22 to inform the canonical multi-dataset schema. MaleCNS v1.0 (`male-cns:v1.0`) is researched separately and is covered here only where other datasets link to it.

**How to read this report**
- Every fact carries a link to its source. Most sources are primary: papers, Janelia, FlyWire and Codex pages, Zenodo and Harvard Dataverse records, and the projects' own GitHub repositories and GCS buckets. A few community or derivative sources are used, and they are labelled as such.
- **"Observed"** means I checked the fact directly against a public file on 2026-09-22. I read headers or small samples, used HTTP range reads for large files, and downloaded nothing larger than about 32 MB.
- **"Not found"** means I looked and found no authoritative statement.
- I used no credentials. Codex's download UI, neuPrint queries and restricted CAVE datastacks were not accessed.

---

## 1. At-a-glance comparison

### 1a. Dataset matrix

| | FlyWire / FAFB | BANC | MANC | FANC | Hemibrain | Optic lobe (MAOL) |
|---|---|---|---|---|---|---|
| **Sex / specimen** | Female, one fly (FAFB EM volume) | Female, one fly | Male, one fly | Female, one fly | Female, one fly | Male: the right optic lobe of the MaleCNS specimen |
| **CNS coverage** | Whole brain with both optic lobes (including lamina and ocelli); no VNC | Brain, SEZ, neck connective and whole VNC. The laminae are not in the dataset. | VNC (with the neck-connective stub) | VNC | About half the central brain, right-biased; heavily truncated | Right optic lobe, with ROIs across the whole CNS |
| **Official scale** | 139,255 proofread neurons (v783). About 130M filtered synapses in total, 54.5M of them between neurons. 2,700,513 connections of 5 or more synapses among 134,181 neurons. | 150,841 proofread neurons. 155,916 proofread plus roughly proofread. 175,096 neuron segments. synapses_v2 holds 218,460,852 detections. | About 23k neurons, 10M presynaptic sites and 74M PSDs. v1.0 Meta: 10,343,391 pre / 74,456,993 post. | About 14,600 neuronal cell bodies and about 45M synapses. Roughly half proofread as of April 2024. | About 25k neurons and about 20M synapses. neuPrint: about 22k fully reconstructed and about 76k truncated. v1.2 Meta: 9,496,606 pre / 64,139,744 post. | More than 50,000 neurons of more than 700 types. v1.1 Meta: 7,335,616 pre / 49,508,904 post. |
| **Native neuron ID** | CAVE `root_id` (18 digits, `7205759406…`). Also `supervoxel_id` and `nucleus_id`. | CAVE `root_id` (`7205759414…`, some `…940…`). Also `supervoxel_id` and `nucleus_id`. | neuPrint `bodyId` (10000 to about 5.4e10) | CAVE `root_id` (`6485183464…`) | neuPrint `bodyId` (2.0e8 to 7.1e9) | neuPrint `bodyId`, shared with MaleCNS |
| **Version handle** | CAVE materialization 630 (2023-03-21) and 783 (2023-09-30) | CAVE materialization 626 (2025-07-21), 850 (interim), 888 (2026-04-16/17) | `manc:v1.0`, `manc:v1.2.1`, `manc:v1.2.3` | CAVE materializations. 1116 is used for BANC matching; the public dumps are 1237 and 1444. | `hemibrain:v1.2.1` | `optic-lobe:v1.0.1`, `optic-lobe:v1.1` |
| **Access** | Public CAVE (`flywire_fafb_public`), Codex, Zenodo, GitHub | CAVE (`brain_and_nerve_cord` is restricted; `brain_and_nerve_cord_public`), Codex, Dataverse, GCS | neuPrint, Clio, GCS flat files | Restricted CAVE (`fanc_production_mar2021`); public GCS dumps | neuPrint, GCS | neuPrint, GCS |
| **License (as stated)** | flywire.ai says **CC BY-NC 4.0**, but the Zenodo dumps say **CC-BY 4.0** (conflict) | CC BY 4.0 | CC-BY | Not found for data (code is GPL-3.0) | CC-BY on the Janelia page. The neo4j bundle carries a BSD-style HHMI license text. | CC-BY |

Sources for the scale row:
- FAFB: [Dorkenwald 2024](https://europepmc.org/articles/PMC11446842)
- BANC: [BANC numbers.csv](https://dataverse.harvard.edu/api/access/datafile/13954582) and [Bates 2026](https://europepmc.org/articles/PMC13518251)
- MANC: [Janelia MANC page](https://www.janelia.org/project-team/flyem/manc-connectome) and [MANC v1.0 Meta](https://storage.googleapis.com/flyem-manc-exports/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/Neuprint_Meta_manc_v1.ftr)
- FANC: [Azevedo 2024 abstract](https://europepmc.org/articles/PMC11348827) and [FANC wiki](https://github.com/htem/FANC_auto_recon/wiki)
- Hemibrain: [Scheffer 2020](https://europepmc.org/articles/PMC7546738), [neuPrint datasets](https://neuprint.janelia.org/api/dbmeta/datasets) and the hemibrain v1.2 Meta inside [hemibrain_v1.2_neo4j_inputs.zip](https://storage.googleapis.com/hemibrain-release/neuprint/hemibrain_v1.2_neo4j_inputs.zip)
- Optic lobe: [Janelia optic-lobe page](https://www.janelia.org/project-team/flyem/optic-lobe) and [OL v1.1 Meta](https://storage.googleapis.com/flyem-optic-lobe/v1.1/optic-lobe-v1.1-neuprint-tables/Neuprint_Meta.csv)

The Codex home page currently lists these counts ([codex.flywire.ai](https://codex.flywire.ai/)):

| Codex dataset | Version | Neurons | Connections |
|---|---|---|---|
| FAFB | v783 | 139,255 | 3,732,460 |
| BANC | v888 | 158,262 | 3,037,361 |
| MANC | v1.2.1 | 23,665 | 5,305,638 |
| MAOL | v1.1 | 52,445 | 6,484,936 |
| MCNS | v1.0 | 166,700 | 6,242,118 |

These are Codex's counts at Codex's own per-dataset thresholds (see 1b).

### 1b. Thresholds, NT schemes and laterality at a glance

**FAFB**
- **Synapse detector and quality field:** Buhmann et al. 2021 predictions scored with Heinrich et al. cleft segmentation. Links with **`cleft_score` ≤ 50 are removed** (so kept means > 50), and duplicates within 100 nm are removed. `connection_score` is not used. Since July 2025 Codex uses **"Princeton" synapses** ([Yu et al. 2025](https://www.biorxiv.org/content/10.1101/2025.07.11.664377v1)), which have a `size` field.
- **Customary edge threshold:** 5 or more synapses per neuron pair ([paper](https://europepmc.org/articles/PMC11446842), [Codex FAQ](https://codex.flywire.ai/faq)). Two or more is used in the optic lobes (Matsliah et al.).
- **NT classes:** 6 (ACh, Glu, GABA, 5-HT, DA, OA).
- **Neuron-level NT:** `top_nt` and `top_nt_conf` (mean over presynapses) in the annotations. Codex has `nt_type` and `nt_type_score` plus per-class `*_avg` columns.
- **Neuron side:** `side` is left, right, center or na. It is the soma side, or the nerve-entry side for sensory and ascending neurons. Labels are corrected for the left/right inversion of the FAFB images; the image and coordinate data remain mirrored.

**BANC**
- **Synapse detector and quality field:** Zetta.ai detector. Uses postsynaptic **`size` ≥ 5 voxels** for v2 and ≥ 10 for v3. v3 also has `mean_score` and `median_score`. There is **no cleft score**.
- **Customary edge threshold:** the paper applies no count threshold except 5 or more for influence scores. Codex uses 3 or more.
- **NT classes:** 8 (the FAFB six plus histamine and tyramine).
- **Neuron-level NT:** `neurotransmitter_predicted` and `neurotransmitter_score`, computed as the argmax of summed probabilities. Also `neurotransmitter_verified`.
- **Neuron side:** `side` from the soma anchor (left or right; the README also lists center). There is also a synapse-level `side` and an `input_side_index` / `output_side_index` in [-1, 1].

**MANC**
- **Synapse detector and quality field:** T-bar and PSD confidences (`conf_pre`, `conf_post`). The v1.0 Meta sets `preHPThreshold` 0.7, `postHPThreshold` 0.7 and `postHighAccuracyThreshold` 0.4.
- **Customary edge threshold:** none by convention; Codex uses 1 or more.
- **NT classes:** 3 (ACh, GABA, Glu) plus "unknown".
- **Neuron-level NT:** `predictedNt` and `predictedNtProb`, plus `nt{Acetylcholine,Gaba,Glutamate,Unknown}Prob`. Each is the mean of per-synapse probabilities.
- **Neuron side:** `somaSide` (RHS, LHS, Midline) and `rootSide` (RHS, LHS, BIL, MID). The instance suffix is `_R`, `_L` or `_M`.

**FANC**
- **Synapse detector and quality field:** automated detector. The paper reports that more than 80% of partners with more than three synapses are true.
- **Customary edge threshold:** the public exports are thresholded at 3 or more (`countthresh3`).
- **NT classes:** no EM-based prediction was published (not found). Some neurons carry hemilineage-derived tags.
- **Neuron-level NT:** only the `neuron_information` tags ("cholinergic" and so on).
- **Neuron side:** free-text tags ("left soma", "neck connective (right)", "left T1 leg nerve").

**Hemibrain**
- **Synapse detector and quality field:** per-synapse `confidence`. The v1.2 Meta sets pre-HP 0.0, post-HP 0.7 and postHighAccuracy 0.5.
- **Customary edge threshold:** none by convention. neuPrint provides `weight` and `weightHP`.
- **NT classes:** 6 plus "neither", in separate Eckstein files only.
- **Neuron-level NT:** none in neuPrint. There is a separate body-mean file.
- **Neuron side:** instance suffix `_L` / `_R`. The ROI suffixes `(L)` / `(R)` refer to the brain side.

**Optic lobe**
- **Synapse detector and quality field:** flat files are filtered at `minconf-0.5`. The Meta sets pre-HP 0.0, post-HP 0.7 and postHighAccuracy 0.5.
- **Customary edge threshold:** none by convention; Codex uses 1 or more.
- **NT classes:** 7 plus "unclear".
- **Neuron-level NT:** `predictedNt` and `predictedNtConfidence`, cell-type-level NT, and `consensusNt` with literature references.
- **Neuron side:** instance suffix.

**Electrical synapses:** no dataset contains gap junctions. MANC is the only one that carries a neuron-level `transmission` annotation (electrical or putative electrical). See §4.9.

---

## 2. FlyWire / FAFB (Female Adult Fly Brain)

### 2.1 Specimen, coverage, scale
- **Specimen and resolution.** Adult female *D. melanogaster* brain imaged in the FAFB EM volume at 4 × 4 × 40 nm voxels ([Codex FAQ](https://codex.flywire.ai/faq)). Synapses were transformed from FAFB14 into the FlyWire FAFB14.1 space ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842)).
- **Coverage.** Whole brain including both optic lobes, the lamina and the ocellar ganglion; no VNC ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842)).
- **Neurons.** 139,255 proofread neurons at v783 ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842); [Zenodo 10676866](https://zenodo.org/records/10676866)).
- **Synapses.** About 130M synapses after filtering from about 244M putative ones. 54.5M synapses are between proofread neurons ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842)).
- **Connections.** "We observed 2,700,513 such connections [5 or more synapses] between 134,181 identified neurons" ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842)).
- **Cell types.** 8,453 annotated cell types, of which 3,643 were previously proposed in the hemibrain ([Schlegel 2024](https://europepmc.org/articles/PMC11446831)). The current annotation file (v3.1) has 139,248 rows and 8,840 distinct `cell_type` values (observed in [Supplemental_file1](https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/Supplemental_file1_neuron_annotations.tsv)).

### 2.2 IDs, stability, versioning
- **`root_id`.** A 64-bit CAVE ChunkedGraph ID for the agglomerated neuron. Codex describes it as "unique across data versions but might get replaced if altered by proofreading" ([Codex FAQ](https://codex.flywire.ai/faq)). Every merge or split creates new root IDs; supervoxels keep their identity ([CAVE/MICrONs versioning tutorial](https://tutorial.microns-explorer.org/materialization-version.html), [CAVEclient ChunkedGraph guide](https://caveclient.readthedocs.io/en/latest/guide/chunkedgraph.html)).
- **Stable anchors.**
  - `supervoxel_id` plus an anchor position (`pos_x/y/z` in 4 × 4 × 40 nm voxels, placed on the neuron backbone) and `nucleus_id` ([annotation README](https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/README.md)).
  - Zenodo NBLAST files key neurons as `"{root_id},{supervoxel_id}"`, where "the supervoxel ID represents an anchor that can be used to map this neuron to different materialization versions" ([Zenodo 10877326](https://zenodo.org/records/10877326)).
  - In `nuclei_v1`, about 6,000 intrinsic neurons whose segmentation does not reach the soma have `pt_root_id = 0` ([FlyWire CAVE tutorial](https://github.com/seung-lab/FlyConnectome/blob/main/CAVE%20tutorial.ipynb)).
- **Materializations in the public datastack `flywire_fafb_public`:**
  - Version 630: 2023-03-21 08:10 UTC.
  - Version 783: 2023-09-30 05:10 UTC ([CAVE tutorial output](https://github.com/seung-lab/FlyConnectome/blob/main/CAVE%20tutorial.ipynb)).
  - "FlyWire's latest public release is version 783 which corresponds to a snapshot of the data from October 2023." Newer "classification" and "community labels" annotations "are automatically part of the public release regardless of when they were created" ([flywire.ai/guidelines](https://flywire.ai/guidelines)).
- **Other datastacks and static segmentations.** Restricted: `flywire_fafb_production` and `flywire_fafb_sandbox`. Static per-release segmentations: `precomputed://gs://flywire_v141_m783` and `gs://flywire_v141_m630` ([fafbseg utils.py](https://github.com/flyconnectome/fafbseg-py/blob/master/fafbseg/flywire/utils.py)).
- **Mapping IDs across versions.**
  - Eckstein Supplemental Data 4 carries both `root_id_630` and `root_id_783` ([Zenodo 10593546](https://zenodo.org/records/10593546)).
  - Codex has a "Map Root IDs" tool that needs a CAVE token ([Codex FAQ](https://codex.flywire.ai/faq)).
  - fafbseg's `materialization='auto'` finds the version in which all queried IDs co-exist ([fafbseg docs](https://fafbseg-py.readthedocs.io/en/latest/source/generated/fafbseg.flywire.synapses.get_synapses.html)).
- **Collision risk.** FAFB root IDs span 720575940596125868 to 720575940661339777 (observed in Codex classification). They share a numeric prefix space with BANC IDs (§3.2), so **the prefix does not identify the dataset**.

### 2.3 Access methods (exact locations)

**CAVE (public).** Datastack `flywire_fafb_public`, which needs a free CAVE account and token ([CAVE tutorial](https://github.com/seung-lab/FlyConnectome/blob/main/CAVE%20tutorial.ipynb)).
- Tables: `hierarchical_neuron_annotations`, `neuron_information_v2` (community labels), `synapses_nt_v1`, `nuclei_v1`, `proofread_neurons`, `fly_synapses_neuropil_v6`.
- Filtered synapse views: `valid_synapses_nt_np` (from v630) and `valid_synapses_nt_np_v6` (v783 and later; improved optic-lobe neuropil assignment).
- Queries are capped at 500,000 rows. The tutorial says the view holds about 110M synapses.

**Zenodo 10676866** ("FlyWire Whole-brain Connectome Connectivity Data", version 783.0, 2024-06-02, CC-BY-4.0; [record](https://zenodo.org/records/10676866)):
- `flywire_synapses_783.feather` (9.49 GB). Columns: `id, pre_pt_root_id, post_pt_root_id, connection_score, cleft_score, gaba, ach, glut, oct, ser, da, neuropil, post_pt_position_{x,y,z}, pre_pt_position_{x,y,z}`. Coordinates are in nm.
- `proofread_connections_783.feather` (852 MB). Columns: `pre_pt_root_id, post_pt_root_id, neuropil, syn_count, gaba_avg, ach_avg, glut_avg, oct_avg, ser_avg, da_avg`. There is one row per (pair, neuropil) with at least 1 synapse, so **it is unthresholded**.
- `proofread_root_ids_783.npy`, `per_neuron_neuropil_count_{pre,post}_783.feather`.

**Other Zenodo records:**
- Skeletons and NBLAST scores: [10877326](https://zenodo.org/records/10877326).
- Information-flow ranks: [12588557](https://zenodo.org/records/12588557).
- NT supplement: [10593546](https://zenodo.org/records/10593546).

**GitHub annotations.** [flyconnectome/flywire_annotations](https://github.com/flyconnectome/flywire_annotations), with tagged releases v1.0.0 through v3.1.0. Versions 1.x are based on segmentation 630 and versions 2.x and later on 783. Version 3.0.0 added MaleCNS cross-validation (Berg et al. 2025).

**Codex** ([codex.flywire.ai](https://codex.flywire.ai/)):
- Google sign-in is required for the apps. Downloads are for FlyWire datasets (FAFB, BANC) only ([Codex FAQ](https://codex.flywire.ai/faq)).
- Programmatic pattern: list products at `https://codex.flywire.ai/api/download?dataset=fafb`, then fetch `https://codex.flywire.ai/api/download_resource?data_product=...&dataset=fafb&api_token=...`. "Codex intentionally does not provide a general programmatic live-query API for bulk access" ([Codex FAQ](https://codex.flywire.ai/faq)).
- "Files in the Codex portal are synchronized with the current Codex data, so they may differ from original publication-time archives."
- **Undocumented public mirror (observed).** The files Codex serves also sit in a publicly listable bucket, `gs://flywire-data/codex/data/{fafb/630, fafb/783, banc/305…888, manc/1.2.1, maol/1.1, mcns/0.9, mcns/1.0}` ([listing](https://storage.googleapis.com/storage/v1/b/flywire-data/o?prefix=codex/data/&delimiter=/)). This is not an advertised channel, so BrainIR should use the official download route and respect the FlyWire terms. Headers observed in `fafb/783`:
  - `neurons.csv.gz`: `root_id, group, nt_type, nt_type_score, da_avg, ser_avg, gaba_avg, glut_avg, ach_avg, oct_avg`
  - `classification.csv.gz`: `root_id, flow, super_class, class, sub_class, hemilineage, side, nerve`
  - `consolidated_cell_types.csv.gz`: `root_id, primary_type, additional_type(s)`
  - `connections.csv.gz` and `connections_princeton.csv.gz`, plus `*_no_threshold`, `*_5_ol_2`, `connections_buhmann*` variants: `pre_root_id, post_root_id, neuropil, syn_count, nt_type`
  - `labels.csv.gz`: `root_id, label, user_id, position, supervoxel_id, label_id, date_created, user_name, user_affiliation`. This file contains contributor names.
  - `coordinates.csv.gz`: `root_id, position, supervoxel_id`. **Positions are in nm here**, whereas the annotation repository uses 4 × 4 × 40 voxels (observed: 437536 = 109384 × 4, and 81960 = 2049 × 40).
  - `names.csv.gz`: `root_id, name, group` (automatic neuropil-based names such as `LO.LOP.561`).
  - `cell_stats.csv.gz`: `root_id, length_nm, area_nm, size_nm`
  - `neuropil_synapse_table.csv.gz`: wide per-neuropil input/output counts.
  - `visual_neuron_types.csv.gz`: `root_id, type, family, subsystem, category, side`
  - `column_assignment.csv.gz`: `root_id, hemisphere, type, column_id, x, y, p, q`
  - `connectivity_tags.csv.gz`, `processed_labels.csv.gz` (labels with FBbt IDs), `nblast.csv.gz`, `dsx_fru_types.csv.gz`, `synapse_coordinates.csv.gz`
  - `fafb_v783_princeton_synapse_table.csv.gz` (2.7 GB): `pre_x…post_z, ctr_x.., size, pre_root_id_720575940, post_root_id_720575940, neuropil`. **The root columns drop the constant prefix**: full ID = 720575940·10⁹ + value.

**Other access.** CATMAID Spaces ([fafb-flywire.catmaid.org](https://fafb-flywire.catmaid.org/)), braincircuits.io, and the libraries fafbseg-py, fafbseg (R) and navis ([Dorkenwald data availability](https://europepmc.org/articles/PMC11446842); [flywire_annotations README](https://github.com/flyconnectome/flywire_annotations)).

### 2.4 Annotation fields and naming conventions (Schlegel et al. 2024; Berg et al. 2025 additions)
From the [supplemental README](https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/README.md), with value sets observed in the v3.1 file.

**The hierarchy** is `flow → super_class → cell_class → cell_sub_class → cell_type`, plus `hemibrain_type`.
- `flow`: `intrinsic`, `afferent`, `efferent`.
- `super_class`: `optic`, `central`, `sensory`, `visual_projection`, `ascending`, `descending`, `sensory_ascending`, `visual_centrifugal`, `motor`, `endocrine`.
- In CAVE the hierarchy is stored long-form: one row per (neuron, `classification_system`), with the value in a column confusingly named `cell_type` ([CAVE tutorial](https://github.com/seung-lab/FlyConnectome/blob/main/CAVE%20tutorial.ipynb)).

**Type-name conventions** ([Schlegel 2024 Methods](https://europepmc.org/articles/PMC11446831); observed):
- Many-to-one hemibrain matches are written comma-joined, e.g. `SIP078,SIP080`.
- Splits get lower-case suffixes, e.g. `PS090a` / `PS090b`.
- Hemibrain connectivity types use `_a` / `_b`.
- An untyped hemibrain match is recorded as `hb<bodyId>` (340 rows), paired with a `CBxxxx` FlyWire type.

**Hemilineages.** `ito_lee_hemilineage` and `hartenstein_hemilineage` give two parallel nomenclatures, and not every label exists in both.

**`side`.** Soma side for brain-intrinsic neurons; nerve-entry side for sensory and ascending neurons. Values are `left`, `right`, `center` (e.g. VUM neurons) and `na` (30 neurons). Soma side was defined in JRC2018F space, with manual review near the midline ([Schlegel 2024](https://europepmc.org/articles/PMC11446831)).

**Neurotransmitter and ontology columns.**
- `top_nt` and `top_nt_conf`, plus literature `known_nt` and `known_nt_source`. `known_nt` is free text, e.g. `gaba, nitric oxide`, `gaba-negative`, `acetylcholine; sNPF; …`.
- `fbbt_id` is an ontology term, present for 28,905 neurons covering 2,527 distinct FBbt terms. `vfb_id` identifies the individual neuron (`fw000001`…).

**Other columns.**
- `status`: `outlier_seg`, `outlier_bio`.
- Added in v3.0: `dimorphism` (isomorphic, sexually dimorphic, female-specific, plus "potentially" variants), `matching_notes`, `fru_dsx`, `synonyms` and `supertype`. `supertype` is the MaleCNS neuPrint supertype, stored as numeric-looking strings such as `12693.0`.

**Codex layers.**
- Codex consolidates types from several sources and picks a "primary/resolved" type, so it "likely diverge[s] from the systematic and cross-checked annotations" in the GitHub repository ([flywire_annotations README](https://github.com/flyconnectome/flywire_annotations); [Codex FAQ](https://codex.flywire.ai/faq)).
- Search attributes include `side`, `neuromere`, `input/output_hemisphere`, `nt_type_verified`, `neuropeptide_verified`, `mirror_twin_root_id`, `resolved_type`, `connectivity_tag`, and more.

### 2.5 Neurotransmitter predictions (Eckstein, Bates et al. 2024)
- **Per synapse.** The six probabilities `gaba, ach, glut, oct, ser, da` sum to about 1 ([Zenodo 10676866](https://zenodo.org/records/10676866)). The reported accuracy is 87% per synapse and 94% per neuron by majority vote. The ground truth was 3,025 neurons, assuming Dale's law ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842)). The raw model outputs also include a "neither" class (`nts_11.*`; [Zenodo 10593546](https://zenodo.org/records/10593546)).
- **Per neuron, in the annotation file.** `top_nt` is "calculated by averaging confidences over the transmitter predictions for all presynapses … and choosing the most confident transmitter", and `top_nt_conf` is that mean ([supp README](https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/README.md)).
- **Per neuron, in Eckstein's supplement.** It provides `conf_nt` / `conf_nt_p` (a confidence calibrated with synapse-level confusion metrics and synapse filtering) alongside `top_nt` / `top_nt_p` ([Zenodo 10593546](https://zenodo.org/records/10593546)).
- **Per neuron, in Codex (observed).**
  - `nt_type` is the argmax of the six `*_avg` columns and `nt_type_score` is that maximum; this held for 100% of non-empty rows.
  - `nt_type` is **empty for 19,658 neurons** (score 0). Codex's blanking rule is not documented.
  - Codex agrees with Schlegel's `top_nt` for 94.9% of neurons where both are present.
  - Codex separates predicted from verified NT: "treat verified fields as curated annotations and predicted fields as model output" ([Codex FAQ](https://codex.flywire.ai/faq)).

### 2.6 Synapses, confidence and thresholds
- **Filtering of the Buhmann et al. 2021 predictions** ([Dorkenwald 2024 Methods](https://europepmc.org/articles/PMC11446842)):
  - Links are removed if either end is unassigned or the Heinrich **cleft score is ≤ 50**.
  - Duplicate links between the same partners within 100 nm (by presynaptic coordinate) are removed.
  - `connection_score` is "not use[d] … to threshold synapses" ([Zenodo](https://zenodo.org/records/10676866)). The CAVE tutorial phrases the rule as `cleft_score > 50`.
  - fafbseg's `clean=True` additionally drops autapses and background ID 0 ([fafbseg docs](https://fafbseg-py.readthedocs.io/en/latest/source/generated/fafbseg.flywire.synapses.get_synapses.html)).
  - Note that the brief said "≥ 50", but the official sources say **> 50**.
- **Neuron-pair threshold.** The paper uses "a consistent threshold of >4", i.e. 5 or more ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842)). The Codex default for FAFB is 5 or more, and "Connection tables can contain multiple rows for the same pair when synapses occur in multiple regions/neuropils" ([Codex FAQ](https://codex.flywire.ai/faq)). Matsliah et al. found 2 or more appropriate in the optic lobes (Dorkenwald), which is why Codex also ships `*_5_ol_2` files.
- **Princeton synapses (detector change).** A new FAFB-wide detector ([Yu et al. 2025](https://www.biorxiv.org/content/10.1101/2025.07.11.664377v1)) has been the Codex default since July 2025; "originally released synapses (prior to July 2025) were predicted with Buhmann et al." ([About FlyWire](https://codex.flywire.ai/about_flywire); [citation table](https://docs.google.com/spreadsheets/d/1eOPxOYoalArVDIhzVis3CsKjETzkdFkRtXSHHY3XdSU)). **The same materialization (783) therefore exists with two synapse sets**: Buhmann and Princeton. Princeton links carry a `size` field. I did not find a documented quality threshold for them, or how NT is assigned to them.
- **Neuropil assignment.** Each synapse is assigned by its **presynaptic location**. Synapses outside all neuropils go to the nearest neuropil if it is within 10 µm ([CAVE tutorial](https://github.com/seung-lab/FlyConnectome/blob/main/CAVE%20tutorial.ipynb)).

### 2.7 Neuropils and laterality
- **Neuropil set (observed).** 78 FlyWire neuropils plus `UNASGD`: `AL, AME, AMMC, AOTU, ATL, AVLP, BU, CAN, CRE, EPA, FLA, GA, GOR, IB, ICL, IPS, LA, LAL, LH, LO, LOP, MB_CA, MB_ML, MB_PED, MB_VL, ME, PLP, PVLP, SCL, SIP, SLP, SMP, SPS, VES, WED` each with `_L`/`_R`, plus the unpaired `EB, FB, GNG, NO, OCG, PB, PRW, SAD` ([Codex neuropil_synapse_table header](https://storage.googleapis.com/flywire-data/codex/data/fafb/783/neuropil_synapse_table.csv.gz); [neuropil_stats.csv](https://storage.googleapis.com/flywire-data/codex/data/fafb/783/neuropil_stats.csv)). "Symmetric neuropils contain a hemisphere annotation after '_'" ([Zenodo](https://zenodo.org/records/10676866)). The set is flat; there is no hierarchy.
- **Differences from the hemibrain.** The mushroom body is coarser (`MB_CA/PED/VL/ML` rather than per-lobe compartments). `IB` is split into `IB_L`/`IB_R` (single `IB` in the hemibrain). `LA` and `OCG` are present.
- **Left/right inversion.** "The FAFB dataset used in FlyWire was left/right inverted during image acquisition … addressed by inverting the left/right orientation of all annotations and labels in both CAVE and Codex. However, we decided not to change the imagery or segmentation data" ([Codex FAQ](https://codex.flywire.ai/faq)). "All side labels are biologically correct"; tools such as `navis.mirror_brain()` correct the coordinates ([Schlegel 2024](https://europepmc.org/articles/PMC11446831)). **Coordinate handedness is therefore opposite to label handedness.**

### 2.8 Electrical synapses
None. Only chemical synapses were detected ([Dorkenwald 2024](https://europepmc.org/articles/PMC11446842): "5 × 10⁷ chemical synapses").

### 2.9 License and citation
- **License conflict (needs a decision).** flywire.ai says: "FlyWire's public release data is made available under license CC BY-NC 4.0" ([flywire.ai/guidelines](https://flywire.ai/guidelines)). The Zenodo dumps (10676866, 10877326, 12588557, 10593546) are labelled CC-BY-4.0 ([Zenodo](https://zenodo.org/records/10676866)). The ToS makes user edits and annotations CC-BY-NC 4.0 ([flywire.ai/tos](https://flywire.ai/tos)).
- **Citation.** "Please co-cite the Dorkenwald et al. and Schlegel et al. manuscripts", then add per-component citations from the [citation table](https://docs.google.com/spreadsheets/d/1eOPxOYoalArVDIhzVis3CsKjETzkdFkRtXSHHY3XdSU):
  - Zheng et al. 2018 (imagery)
  - Buhmann 2021 and Heinrich 2018 (synapses before July 2025)
  - Yu et al. 2025 (synapses from July 2025)
  - Eckstein, Bates et al. 2024 (NT)
  - Matsliah, Yu et al. 2024 (cell types)
  - Lin et al. 2024 (connectivity tags)
  - Deutsch et al. 2025 (genes)
- **Annotations v3.0.0 and later** should also cite Berg et al. 2025 and Matsliah 2024 ([README](https://github.com/flyconnectome/flywire_annotations)).
- **Codex** citation: `http://dx.doi.org/10.13140/RG.2.2.35928.67844` ([About FlyWire](https://codex.flywire.ai/about_flywire)).

---

## 3. BANC (Brain And Nerve Cord)
Authorship note: BANC is Bates, Phelps, Kim, Yang et al. (*Nature* 2026). Azevedo et al. is the FANC paper.

### 3.1 Specimen, coverage, scale
- **Specimen and imaging.** One adult female. GridTape TEM at 4 × 4 × 45 nm (the public instance is downscaled to 8 × 8 × 45) ([Bates 2026](https://europepmc.org/articles/PMC13518251)).
- **Coverage.** Brain, SEZ, cervical connective and the entire VNC ([BANC-project](https://github.com/htem/BANC-project)). The laminae are absent (about 9,390 neurons of R1–R6 and Lai missing), and both antennal nerves are damaged ([Bates 2026](https://europepmc.org/articles/PMC13518251); [meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md)).
- **Counts at v888** ([numbers.csv](https://dataverse.harvard.edu/api/access/datafile/13954582)):

  | Measure | Count |
  |---|---|
  | Proofread (strict) | 150,841 |
  | Proofread plus roughly proofread | 155,916 |
  | Identified entities (including fragments and glia) | 171,512 |
  | Total neuron segments | 175,096 |
  | Cell-typed neurons | 147,846 |
  | Unique cell types | 11,502 |
  | Ascending neurons (1,768 matched to MANC) | 1,849 |
  | Descending neurons (1,304 matched to FAFB) | 1,316 |

  The README headline is "approximately 188,000 neurons and 199 million predicted synapses" ([BANC-project](https://github.com/htem/BANC-project)). The meta table has 188,162 rows, which includes non-neuronal and unproofread segments.
- **Synapses.** The `synapses_v2` table "lists 218,460,852 synaptic links". About 74% of presynaptic ends and 23% of postsynaptic ends attach to proofread neurons, and 18% of links have a proofread neuron at both ends ([Bates 2026](https://europepmc.org/articles/PMC13518251)).

### 3.2 IDs, stability, versioning
- **Versions.** CAVE materialization **v626** (21 July 2025, preprint) and **v888** (17 April 2026, print) ([Bates 2026](https://europepmc.org/articles/PMC13518251)). The bucket CHANGELOG gives the v888 timestamp as 2026-04-16 ([CHANGELOG](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/CHANGELOG.md)). Codex lists "v888 – May 20, 2026" and "v626 – Jul 20, 2025", which are its own import dates ([Codex FAQ](https://codex.flywire.ai/faq)).
- **Root ID churn.** The meta table carries `root_626`, `root_850` and `root_888`, and now also `root_890` (observed in the current feather schema) ([meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md)). **40.2% (62,773) of proofread or roughly-proofread neurons changed root ID between v626 and v888** ([numbers.csv](https://dataverse.harvard.edu/api/access/datafile/13954582)). Of the 115,151 v626 IDs in Codex, only 86,403 persist in Codex v888 (observed).
- **Stable handles.**
  - bancr: "This ID changes each time a neuron is edited … use `nucleus_id` … or `banc_latestid()`" ([bancr](https://natverse.org/bancr/)).
  - `supervoxel_id` is kept "for resolving annotations to the current root".
  - The master annotation table attaches labels to a **representative-point row** (`target_id` → `cell_representative_point.id`), not to a root ID ([codex_annotations doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/codex_annotations.md)).
- **Types.** Compiled tables store identifiers as **strings**, not int64 ([meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md); observed Arrow schemas). BANC root IDs occupy the same `72057594…` space as FAFB. There was no actual overlap between FAFB v783 and BANC v888 IDs (observed), but none is guaranteed.

### 3.3 Access methods
- **CAVE datastacks.** Production `brain_and_nerve_cord` (authorized users only) and public `brain_and_nerve_cord_public` (any CAVE-registered Google account) ([bancr](https://natverse.org/bancr/); [bancr partners.R](https://github.com/natverse/bancr/blob/main/R/partners.R); [codex_annotations doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/codex_annotations.md)).
- **Codex.** [codex.flywire.ai/banc](https://codex.flywire.ai/banc) hosts v626 and v888. It is "the most up-to-date version … (continues to evolve past the snapshot)" ([BANC-project](https://github.com/htem/BANC-project)).
- **Harvard Dataverse.** The v888 deposit is **10.7910/DVN/7WTH1N**. Dataset version 3.0 (released 2026-07-01) has 379 files and a CC BY 4.0 license ([Dataverse API](https://dataverse.harvard.edu/api/datasets/:persistentId/?persistentId=doi:10.7910/DVN/7WTH1N)). It supersedes the v626 deposit 10.7910/DVN/8TFGGB ([Bates 2026](https://europepmc.org/articles/PMC13518251)).
- **GCS bucket** `gs://lee-lab_brain-and-nerve-cord-fly-connectome/` ([README.txt](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt); per-product docs under `documentation/`):
  - `compiled_data/banc_888/`: `banc_888_meta.feather`, `banc_888_metrics.feather`, `banc_888_edgelist_simple_v2/v3.feather`, `banc_888_edgelist_split_v2/v3.feather`, `banc_888_synapses_v2/v3_enriched.parquet` (17–20 GB), `banc_888_neurotransmitter_prediction_v2.csv`, and influence parquets (about 287 GB).
  - `neuron_annotations/v888/`: `codex_annotations`, `cell_info`, `backbone_proofread`, `cell_representative_point`, `proofreading_notes`, `somas_v1`, `peripheral_nerves`, `neck_connective_y92500` (parquet).
  - `synapses/v2.0/`: `banc_nt_prediction_w_sizethresh_5_11102025.parquet`, `synapse_neuropil_lookup_v2.parquet`. There is an equivalent `v3.0/`.
  - `nblast/`: BANC against FAFB 783, MANC v1.2.1, hemibrain v1.2.1, MaleCNS v0.9 and FANC 1116, plus self and mirror comparisons.
  - Compiled tables for other datasets in "BANC framework" columns: `compiled_data/{fafb_783, manc_121, hemibrain_121, malecns_09, fanc_1116}`.
- **BossDB** holds the image, cell, nucleus and mitochondria segmentation (DOI 10.60533/boss-2025-941r) ([Bates 2026](https://europepmc.org/articles/PMC13518251)).
- **Other tools.** Neuroglancer at [ng.banc.community](https://ng.banc.community/view). Clients: `bancr` (R) and `banc` (PyPI).
- **Living data (observed).** Compiled files are revised after publication. There are backups named `…pre_sidefill_2026-06-26` and `pre_l2patch`, and the v2 enriched parquet now has 155,247,357 rows versus 168,951,110 in older docs. **Pin by checksum and date.**

### 3.4 Annotation fields and naming
From the [meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md) and observed schema.
- **Hierarchy.** `flow` → `super_class` → `cell_class` → `cell_sub_class` → `cell_type`.
- **Anatomical columns.** `region`, `hemilineage` (both VNC forms such as `00A` and brain forms such as `ALad1`, `LB7`), `nerve` (e.g. `left_antennal_nerve`), `tract`, `neuromere` (`T1`–`T3`, `A1`–`A8`, `GNG`), and `root_region` (atlas-prefixed, e.g. `ITO_midbrain_AL_R`, `MANC_vnc_NTct_UTct_T1_L`).
- **Cell-type names.** "Inherited from FAFB for brain neurons and DNs, and from MANC for VNC neurons and ANs", with a few further splits such as `ORN_DM6` ([meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md)).
- **`super_class` vocabulary is inconsistent across BANC's own docs.**
  - The meta doc and Codex (observed) list `central_brain_intrinsic`, `optic_lobe_intrinsic`, `ventral_nerve_cord_intrinsic`, `ascending`, `descending`, `sensory`, `sensory_ascending`, `sensory_descending`, `motor`, `visual_projection`, `visual_centrifugal`, `visceral_circulatory`, `ascending_visceral_circulatory`, `glia`, `trachea` and `not_a_neuron`.
  - The bucket README instead lists `…, intrinsic, …, optic` ([README.txt](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt)).
- **Cross-dataset columns.** `fafb_cell_type`, `manc_cell_type`, `malecns_cell_type`, `hemibrain_cell_type` and `fanc_cell_type`, each with matching `*_match` and `*_nblast_match` columns, plus `fafb_alignment_cell_type`.
- **Functional columns.** `sexually_dimorphic`, `cluster` / `super_cluster` (AN/DN behavioural clusters), `cns_network`, `body_part_sensory` / `body_part_effector`, `peripheral_target_type`, `cell_function`, `cell_function_detailed`.
- **Status and quality.**
  - `proofread` and `roughly_proofread` are the strings "TRUE"/"FALSE" and are mutually exclusive.
  - `status` holds comma-joined curation flags.
  - `seed_01` to `seed_14` record provenance.
- **Morphology metrics.** `l2_cable_length_um`, `volume_nm3`, `segregation_index`, and others.

### 3.5 Neurotransmitter predictions
- **Model.** A 3D ResNet-18 classifies presynapses into **8 classes**: acetylcholine, dopamine, GABA, glutamate, histamine, octopamine, serotonin and tyramine. Ground truth came from FAFB, MANC and hemibrain ([Bates 2026](https://europepmc.org/articles/PMC13518251)).
- **Per-synapse output.** The parquet has eight probability columns plus `predicted_nt` and `probability`, as half-float values. It is restricted to v2 synapses with postsynaptic size of 5 or more ([doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_nt_prediction_w_sizethresh_5_11102025.md)).
- **Per-neuron output.** The neuron-level call is made "by summing the classification probabilities for each predicted class across all presynaptic detections and selecting the class with the highest total confidence" ([Bates 2026](https://europepmc.org/articles/PMC13518251)). The meta columns are `neurotransmitter_predicted`, which includes `none`, and `neurotransmitter_score` in [0, 1].
- **Aggregation descriptions disagree.** A secondary tutorial describes the per-neuron CSV as argmax **counts** ([SJCABS doc](https://github.com/sjcabs/fly_connectome_data_tutorial/blob/main/data/dataset_documentation/banc_data.md)), which differs from the paper's summed probabilities.
- **Known failure modes.** "Serotonin predictions should be treated with caution", and Kenyon cells are mostly predicted as dopaminergic, as in FAFB and hemibrain ([Bates 2026](https://europepmc.org/articles/PMC13518251)).
- **Verified NT.** `neurotransmitter_verified` is multi-valued, e.g. `gaba,nitric_oxide` or `acetylcholine,histamine` (observed in Codex).

### 3.6 Synapses, confidence and thresholds
- **v2 detector.** The detector does "not provide a synaptic cleft size estimation". The rule is to "use a postsynapse size threshold of ≥5 for including a pre-post synaptic link" ([Bates 2026](https://europepmc.org/articles/PMC13518251)).
- **The size cut is stated inconsistently.** The paper's review numbers are labelled "size > 5" ([numbers.csv](https://dataverse.harvard.edu/api/access/datafile/13954582)), and `bancr` filters with `size > size.threshold` with a default of 5 ([bancr synapses.R](https://github.com/natverse/bancr/blob/main/R/synapses.R)). Record the exact rule per file.
- **v3 detector.** Uses a size cut of 10 or more and finds about 8–18% more synapses. It carries `mean_score` / `median_score`. Its coordinates are in **16 × 16 × 45 nm voxels**, whereas v2 coordinates are in nm ([v3 doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_synapses_v3_human_readable.md); [v2 doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_synapses_v2_human_readable.md)). The paper uses v2 throughout.
- **Edgelists.** `pre, post, count, norm (= count/post_count), post_count, pre_count`. Autapses are excluded, and no global count threshold is applied ([edgelist doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_edgelist_simple_v2.md); [SJCABS doc](https://github.com/sjcabs/fly_connectome_data_tutorial/blob/main/data/dataset_documentation/banc_data.md)).
- **Thresholds in practice.** The paper applied no connectivity threshold except 5 or more for influence. Codex uses 3 or more ([Codex FAQ](https://codex.flywire.ai/faq)).

### 3.7 Neuropils and regions
- **Synapse-level labels** ([neuropil lookup doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/synapse_neuropil_lookup_v2.md); observed in the v3 parquet):
  - `neuropil` is a short **unsided** code: brain `ME, LO, AVLP, GNG…`; VNC `ProNM-T1, MesoNM-T2, MetaNM-T3, ABDNM, IntTct, HTct…`.
  - `side` is a separate column.
  - `neuropil_detailed` is atlas-prefixed, sided and **comma-joined when a synapse falls in several meshes**, e.g. `ITO_optic_ME_R`, `ITO_midbrain_AVLP_R,ITO_midbrain_PVLP_R`, `COURT_vnc_MetaNM-T3,MANC_vnc_LNp_T3_R`.
  - `region` is not normalized; values include `central_brain`, `optic_lobe`/`optic_lobes`, `ventral_nerve_cord`/`vnc`, `neck`, `brain` and `outside`.
- **Meshes.** They come from Ito et al. 2014 (brain) and Court et al. 2020 (VNC) ([README.txt](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt)).
- **Codex region codes.** Codex's "Top in/out region" uses its own uppercase codes such as `T3_METANM`, `ABDNM`, `HTCT` and `NO_CONS` (observed).

### 3.8 Laterality
- **Neuron `side`** is computed from the soma anchor by `bancr:::banc_lr_position()` and takes the values left and right ([meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md)). The README says left, right or center ([README.txt](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt)).
- **Synapse `side`** has "positive = right" ([lookup doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/synapse_neuropil_lookup_v2.md)).
- **Laterality indices.** `input_side_index` / `output_side_index` run from -1 (left) to +1 (right).
- **`flow` is CNS-relative.** In BANC, ascending and descending neurons are `intrinsic` (observed; contrast §4.4).

### 3.9 Electrical synapses
Not detected; only synapse detections exist ([Bates 2026](https://europepmc.org/articles/PMC13518251)). Not found.

### 3.10 License and citation
- **License.** CC BY 4.0 for the Dataverse data and the repository code ([BANC-project](https://github.com/htem/BANC-project); [Dataverse](https://doi.org/10.7910/DVN/7WTH1N)).
- **Citation.** "Please cite both the paper and the Dataverse deposit": Bates AS, Phelps JS, Kim M, Yang HHJ, … (2026) *Nature* [10.1038/s41586-026-10735-w](https://doi.org/10.1038/s41586-026-10735-w), and doi:10.7910/DVN/7WTH1N. Software components have their own Zenodo DOIs ([README.txt](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt)).

---

## 4. MANC (Male Adult Nerve Cord, Janelia FlyEM / Cambridge / Google)

### 4.1 Specimen, coverage, scale
- **Specimen and coverage.** An adult male VNC, "about 25% of the fly's overall central nervous system" ([Janelia MANC](https://www.janelia.org/project-team/flyem/manc-connectome)). Voxels are 8 nm isotropic ([v1.0 Meta](https://storage.googleapis.com/flyem-manc-exports/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/Neuprint_Meta_manc_v1.ftr)).
- **Scale.** "About 23,000 neurons, 10 million pre-synaptic sites, and 74 million post-synaptic densities" ([Janelia MANC](https://www.janelia.org/project-team/flyem/manc-connectome)). The v1.0 Meta gives totalPreCount 10,343,391 and totalPostCount 74,456,993.
- **Class counts** ([Cheong et al.](https://europepmc.org/articles/PMC13384506)):

  | Class | Count |
  |---|---|
  | Intrinsic neurons (IN) | 13,066 |
  | Descending neurons (DN) | 1,328 |
  | Ascending neurons (AN) | 1,862 |
  | Motor neurons (MN) | 733 |
  | Efferent neurons (EN) | 92 |
  | Efferent ascending (EA) | 9 |
  | Sensory neurons (SN) | 5,927 |
  | Sensory ascending (SA) | 535 |

### 4.2 IDs, stability, versioning
- **`bodyId`.** An int64; the maximum observed is 53,613,193,093. "Barring major proofreading corrections, bodyids are stable and the best way to track particular neurons of interest" ([Marin et al.](https://elifesciences.org/reviewed-preprints/97766)).
- **neuPrint datasets** ([neuPrint /api/dbmeta/datasets](https://neuprint.janelia.org/api/dbmeta/datasets)):
  - `manc:v1.0`: last-mod 2023-05-31; 61 ROIs, including `GF(L)` and `GF(R)`.
  - `manc:v1.2.1`: last-mod 2024-02-01; 59 ROIs.
  - `manc:v1.2.3`: **the same UUID as v1.2.1**, marked "segment property update 2024-08-31", i.e. an annotation-only patch.
  - There is no public `manc:v1.2` or `v1.2.2` (not found).
- **Release history.** Janelia news: "2023-06-06: MANC v1.0 released; 2024-03-11: MANC v1.2 released" ([Janelia MANC](https://www.janelia.org/project-team/flyem/manc-connectome)). The systematic types changed substantially between v1.0 and v1.2.1 ([Marin et al.](https://elifesciences.org/reviewed-preprints/97766)). For example, the `INXXX…` names do not exist in v1.0 (observed in [v1.0 properties](https://storage.googleapis.com/flyem-manc-exports/v1.0/manc-v1.0-neuron-properties.feather)) but appear in v1.2.1 (observed in Codex).
- **Collisions with MaleCNS.** **MANC bodyIds collide numerically with MaleCNS bodyIds.** 19,344 identical integers appear in both, and they refer to different neurons: only 0.02% have the same type (observed from Codex [MANC](https://storage.googleapis.com/flywire-data/codex/data/manc/1.2.1/neurons.csv.gz) and [MCNS](https://storage.googleapis.com/flywire-data/codex/data/mcns/1.0/neurons.csv.gz) tables).

### 4.3 Access methods
- **neuPrint.** [neuprint.janelia.org](https://neuprint.janelia.org/?dataset=manc:v1.2.1), through neuprint-python, neuprintr and natverse [malevnc](https://natverse.org/malevnc/). neuPrint moved to a new authorization system in August 2026: "Existing API tokens no longer work" ([neuPrint serverinfo](https://neuprint.janelia.org/api/serverinfo)).
- **Clio.** [clio.janelia.org](https://clio.janelia.org). Clio uses snake_case field names (`entry_nerve`), whereas neuPrint uses camelCase (`entryNerve`) ([Marin et al.](https://elifesciences.org/reviewed-preprints/97766)).
- **Flat files, v1.0 only** ([bucket](https://console.cloud.google.com/storage/browser/flyem-manc-exports); "The complete MANC connectome can be downloaded as flat files", [Janelia MANC](https://www.janelia.org/project-team/flyem/manc-connectome)):
  - `gs://flyem-manc-exports/v1.0/manc-v1.0-neuron-properties.feather` (17 MB; 102,369 bodies × 56 columns, observed).
  - `…/v1.0/manc-synapse-partners-2023-05-03-215e08-minconf-0.0.feather.bz2` (1.1 GB).
  - `…/v1.0/manc-traced-adjacencies-v1.0/`:
    - `traced-neurons.csv`: `bodyId,type,instance`
    - `traced-connections.csv`: `bodyId_pre,bodyId_post,weight`
    - `traced-connections-per-roi.csv`: `bodyId_pre,bodyId_post,roi,weight`, with "NotPrimary" for synapses outside the primary ROIs ([README](https://storage.googleapis.com/flyem-manc-exports/v1.0/manc-traced-adjacencies-v1.0/README)).
  - `…/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_csv.tar.gz` (neo4j import) and `neuprint_manc_v1.0_ftr/*.ftr` (all nodes and relationships, including per-synapse `Neuprint_Synapses_manc_v1.ftr` with NT probabilities).
- **v1.2 synapses.** `gs://manc-seg-v1p2/manc-v1.2-synapse-partners-minconf-0.0.feather` (1.9 GB). Observed schema: `x_pre, y_pre, z_pre, conf_pre, body_pre, x_post, y_post, z_post, conf_post, body_post, roi_post`.
- **v1.2.3 Neuroglancer layers** with segment properties: [manc-v1.2.3-neuprint-layers.json](https://storage.googleapis.com/manc-seg-v1p2/manc-v1.2.3-neuprint-layers.json).
- **Codex.** MANC v1.2.1 can be browsed with a threshold of 1 or more. Codex points users to the project homepage for downloads ([Codex FAQ](https://codex.flywire.ai/faq)).

### 4.4 Annotation fields
The neuron properties below come from the v1.0 Meta `neuronProperties`, with value sets observed in the v1.0 export ([Meta](https://storage.googleapis.com/flyem-manc-exports/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/Neuprint_Meta_manc_v1.ftr)):

- **Identity:** `bodyId`, `instance`, `type`, `systematicType`, `synonyms`, `description`, `namingUser`.
- **Status:** `status` (Traced, Orphan, Anchor, …), `statusLabel` ("Roughly traced", "Prelim Roughly traced").
- **Class:**
  - `class`: `intrinsic neuron`, `sensory neuron`, `ascending neuron`, `descending neuron`, `motor neuron`, `sensory ascending`, `efferent neuron`, `efferent ascending`, `Glia`, `TBD` / `Sensory TBD` / `Interneuron TBD`.
  - `subclass`: see the codes below.
- **Development:** `hemilineage` (e.g. `20A.22A`, `17X`, `27X`, `TBD`), `birthtime` (primary, early secondary, secondary).
- **Serial and group structure:** `group` (left/right homologue group ID, typically the bodyId of one member), `serial` (serial-homologue set ID), `serialMotif` (independent leg, complex, ascending, …).
- **Location:** `somaSide` (RHS, LHS, Midline), `rootSide` (RHS, LHS, BIL, MID), `somaNeuromere` (T1–T3, A1–A10), `somaLocation`, `rootPosition`, `positionType`.
- **Periphery:** `entryNerve` / `exitNerve` (e.g. `ProLN_R`, `CvC`, `ADMN_R`, `AbNT_R AbNT_L`), `longTract`, `modality` (tactile, proprioceptive, chemosensory, unknown), `receptorType`.
- **Projection:** `origin` / `target` (neuropil strings such as `LegNpT1_R`, `UTct_R.UTct_L`, `multi`), `neuropilsAxonal` / `neuropilsDendritic`.
- **Transmission:** `transmission` (electrical, putative electrical, neurosecretory, putative neurosecretory).
- **Counts and ROIs:** `pre`, `post`, `upstream`, `downstream`, `synweight`, `roiInfo`, and per-ROI boolean properties.
- **`flow`.** MANC's native properties have no `flow` field. When a harmonized `flow` is derived for a VNC-only dataset, DNs become **afferent** and ANs become **efferent**. In Codex MANC (observed), DN = afferent, AN = efferent and even `sensory_ascending` = efferent, whereas FAFB has DN = efferent and AN = afferent, and BANC has both = intrinsic.

**Naming conventions** ([Marin et al. Fig. 3](https://elifesciences.org/reviewed-preprints/97766); [Cheong et al.](https://europepmc.org/articles/PMC13384506); verified against data):

- **General rule.** "The systematic type name begins with a two-letter, class-specific prefix (e.g., DN, MN, AN) and ends with a number defined by hierarchical clustering on the basis of morphology and connectivity." `type` may carry a literature name instead of the systematic name, e.g. `type` DNp01 with `systematicType` DNlt002. In v1.0, 90% of traced neurons had `type == systematicType`.
- **IN / AN.** "Intrinsic neurons and ascending neurons are assigned a systematic type composed of the prefix 'IN' or 'AN' followed by their assigned hemilineage and a number consistent for members of their connectivity cluster. Their soma neuromere and side are used to denote the instance."
  - `IN13B025` is hemilineage 13B, cluster 025.
  - `IN06B065` is hemilineage 06B.
  - Combined hemilineages are kept, e.g. `IN20A.22A067`.
  - An **`X` hemilineage letter** (`17X`, `18X`, `21X`, `26X`, `27X`) is used when "we could not confidently assign them to 'A' vs 'B'".
  - **`XXX`** (e.g. `INXXX###`, `ANXXX002`) stands in for an **undetermined hemilineage**. "Neurons that could not be assigned to a specific hemilineage were annotated as hemilineage 'TBD'". In Codex MANC v1.2.1 all 1,306 neurons with `XXX` types have an empty hemilineage, while every other IN/AN type's hemilineage prefix matches its hemilineage field (observed). The exact phrase "XXX = unknown hemilineage" was not found verbatim in the papers.
- **EN / EA.** Efferent types use `EN` or `EA` (ascending) plus hemilineage plus number, e.g. `EN00B001`.
- **SN / SA.** Sensory types use `SN` or `SA` plus a modality abbreviation plus a number, with the entry nerve as the instance, e.g. `SNta24_ProLN_L`. Lower-case `xx`/`xxxx` placeholders (`SNxxxx`, `SAppxx`) mark unassigned modality or number (observed).
- **DN.** Descending types use `DN` plus a subclass code for the VNC target plus a number. The instance is "entry nerve (CvC) and root side", e.g. `DNlt002_CvC_R` (observed). The DN subclass codes are ([Cheong et al.](https://europepmc.org/articles/PMC13384506)):
  - `nt`, `wt`, `ht`, `it`, `lt`: NTct, WTct, HTct, IntTct, LTct.
  - `fl`, `ml`, `hl`: LegNpT1, T2, T3.
  - `ad`: ANm.
  - `xl`: several leg neuropils.
  - `ut`: upper-tectulum combination.
  - `xn`: multiple neuropils.
- **MN.** Motor types use `MN` plus the target-muscle category plus a number (e.g. `MNwm03`, `MNhm43`), with the exit nerve as the instance.
- **Instances for IN/AN/EN.** `<type>_<neuromere>_<L|R|M>`, e.g. `IN13B025_T2_L`, `EN00B001_A9_M` (observed).
- **Two-letter `subclass` for IN/AN.** "The first letter refers to the laterality and the second if a neuron is ascending, restricted to one neuropil or interconnecting VNC neuropils." The first letter is I (ipsilateral), C (contralateral) or B (bilateral); the second is R (restricted), I (interconnecting) or A (ascending). This gives `IR, CR, BR, II, CI, BI, IA, CA, BA` ([Marin et al.](https://elifesciences.org/reviewed-preprints/97766)).

### 4.5 Neurotransmitter predictions
- **Scheme.** "For the three most common neurotransmitters - acetylcholine, GABA, and glutamate". The model includes "an additional class to indicate non-synaptic or unrecognized structures". Ground truth was 187 neurons.
- **Per synapse.** Each T-bar carries `ntAcetylcholineProb`, `ntGabaProb`, `ntGlutamateProb` and `ntUnknownProb`. These "sum to 1 and should be interpreted as relative probabilities, as other transmitters are possible."
- **Per neuron.** Predictions are "aggregated … as the mean of probabilities of all presynaptic sites. The maximum likelihood predicted probability … was annotated as the predicted neurotransmitter" ([Takemura et al.](https://elifesciences.org/reviewed-preprints/97769)). The neuron fields are `predictedNt` (acetylcholine, gaba, glutamate, unknown) and `predictedNtProb`, plus the four per-class means.

### 4.6 Synapses, confidence and thresholds
- **Detection.** Synapses were predicted as in the hemibrain, with a single T-bar network and PSD partner assignment ([Takemura et al.](https://elifesciences.org/reviewed-preprints/97769)).
- **v1.0 Meta thresholds.** `preHPThreshold` 0.7, `postHPThreshold` 0.7, `postHighAccuracyThreshold` 0.4 ([Meta](https://storage.googleapis.com/flyem-manc-exports/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/Neuprint_Meta_manc_v1.ftr)). In neuPrint, `weightHP` is the "high confidence number of connections", i.e. synapses above the HP thresholds stored in Meta ([neuPrint user guide](https://neuprint.janelia.org/public/neuprintuserguide.pdf)).
- **Not found.** I found no exact definition of how `postHighAccuracyThreshold` enters `weight`, and no statement of the minimum confidence used to load synapses into neuPrint.
- **Flat synapse files.** These are exported at `minconf-0.0`, i.e. unfiltered.
- **Codex.** Uses a threshold of 1 or more ([Codex FAQ](https://codex.flywire.ai/faq)).

### 4.7 ROIs / neuropils
- **ROI set.** 59 ROIs in v1.2.x ([neuPrint datasets](https://neuprint.janelia.org/api/dbmeta/datasets)), split into:
  - **Neuropils:** `LegNp(T1)(L)`, … `LegNp(T3)(R)`, `mVAC(T1–T3)(L/R)`, `Ov(L/R)`, `ANm`, `NTct(UTct-T1)(L/R)`, `WTct(UTct-T2)(L/R)`, `HTct(UTct-T3)(L/R)`, `IntTct`, `LTct`.
  - **Nerves and connective:** `CV` (cervical connective), `ADMN`, `PDMN`, `CvN`, `PrN`, `DProN`, `VProN`, `ProAN`, `ProCN`, `ProLN`, `MesoLN`, `MesoAN`, `DMetaN`, `MetaLN`, `AbN1–4`, each with `(L)`/`(R)`, plus `AbNT` ([v1.0 Meta](https://storage.googleapis.com/flyem-manc-exports/v1.0/neuprint_manc_v1.0/neuprint_manc_v1.0_ftr/Neuprint_Meta_manc_v1.ftr)).
- **Nomenclature.** Court et al. 2020 ([Takemura et al.](https://elifesciences.org/reviewed-preprints/97769)).
- **Hierarchy.** Essentially flat: everything is a child of "ventral nerve cord".
- **Laterality formats.** ROIs use a `(L)`/`(R)` suffix and nest parentheses (`HTct(UTct-T3)(R)`). Annotation fields use underscores instead (`entryNerve = ProLN_R`, `origin = LegNpT1_R`), so **two laterality syntaxes coexist inside MANC**.

### 4.8 Laterality
- **Two side fields.** `somaSide` is the soma hemisphere. `rootSide` is where the neurite enters or exits, used for DNs, SNs and ANs; its extra values are BIL and MID.
- **What the instance encodes.** The instance "reflect[s] the nerve entry side for descending neurons and sensory neurons or soma side and neuromere for all other neurons" ([Takemura et al.](https://elifesciences.org/reviewed-preprints/97769)).
- **Codex mixes the two.** Codex fills "Soma side" from `rootSide` when no soma exists: DNp01 (bodyId 10000) has no `somaSide` but shows `right` in Codex (observed).

### 4.9 Electrical synapses
- **Not in the data.** "Gap junctions were not included in MANC segmentation or annotation."
- **Neuron-level substitute.** 48 neurons matched to known electrical neurons were annotated `transmission: electrical`, and 189 others `putative electrical` ([Marin et al.](https://elifesciences.org/reviewed-preprints/97766)). The v1.0 export has 52 / 173, plus 59 neurosecretory and 169 putative neurosecretory (observed).

### 4.10 License and citation
- **License.** "The MANC is licensed under CC-BY" ([Janelia MANC](https://www.janelia.org/project-team/flyem/manc-connectome)).
- **Citations listed by neuPrint:**
  - Takemura et al. (2024) [10.7554/eLife.97769.1](https://doi.org/10.7554/eLife.97769.1)
  - Marin et al. (2024) [10.7554/eLife.97766.1](https://doi.org/10.7554/eLife.97766.1)
  - Cheong et al. (2025) [10.7554/eLife.96084.2](https://doi.org/10.7554/eLife.96084.2) ([neuPrint datasets](https://neuprint.janelia.org/api/dbmeta/datasets))
- **NT predictions.** Also cite Eckstein et al. 2024.

---

## 5. FANC (Female Adult Nerve Cord)

### 5.1 Specimen, coverage, scale
- **Specimen and imaging.** Adult female VNC, GridTape TEM (Phelps, Hildebrand, Graham et al. 2021) ([FANC README](https://github.com/htem/FANC_auto_recon)). Voxels are 4.3 × 4.3 × 45 nm ([fanc statebuilder.py](https://github.com/htem/FANC_auto_recon/blob/main/fanc/statebuilder.py)).
- **Scale.** "Roughly 45 million synapses and 14,600 neuronal cell bodies" ([Azevedo et al. 2024 abstract](https://europepmc.org/articles/PMC11348827)). "As of April 2024, about half of the neurons in FANC have been proofread" ([FANC wiki](https://github.com/htem/FANC_auto_recon/wiki)).

### 5.2 IDs and versioning
- **IDs.** CAVE root IDs, observed range 648518346459409412 to 648518346531666970, with supervoxel IDs and a nucleus table `somas_dec2022`.
- **Datastacks.** Production `fanc_production_mar2021` and `fanc_sandbox` ([fanc/auth.py](https://github.com/htem/FANC_auto_recon/blob/main/fanc/auth.py)). The aligned volume is `fanc_v4` ([annotation wiki](https://github.com/htem/FANC_auto_recon/wiki/Neuron-annotations)).
- **Materializations in use:**
  - **1116**, used for BANC cross-matching (`fanc_1116`, "FANC v1.116") ([meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md)).
  - **1237** and **1444**, the public dumps dated 2025-08-15 and 2025-10-09 ([bucket listing](https://storage.googleapis.com/storage/v1/b/lee-lab_female-adult-nerve-cord/o?prefix=CAVE/)).
- **Cross-dataset keys.** Matching files carry `supervoxel_id` next to `root_id` for robustness ([neck connective repo](https://github.com/flyconnectome/2023neckconnective)).

### 5.3 Access
- **Live CAVE is restricted.** "Access to the latest reconstruction of FANC is restricted to authorized users"; access comes through joining the community ([FANC README](https://github.com/htem/FANC_auto_recon)). coconatfly marks FANC as "Restricted" ([coconatfly](https://natverse.org/coconatfly/)).
- **Public dumps** in `gs://lee-lab_female-adult-nerve-cord/CAVE/v1444/` (observed):
  - `cell_ids_v2.parquet`, `neck_connective.parquet`, `peripheral_nerves.parquet`, `proofread_first_pass.parquet` (7,001 roots), `proofread_second_pass.parquet` (1,766 roots), `somas_dec2022.parquet` (16,784).
  - `synapses_nov2022_human_readable_id_size_prerootid_postrootid_prex_prey_prez_neuropil.parquet` (769 MB).
  - `…connectioncounts_countthresh3.parquet`: `pre_root_id, post_root_id, num_synapses`; 1,878,659 edges.
  - `…connectioncountsperneuropil(_countthresh3).parquet`.
- **Other public data.** Neuroglancer "published neurons" views ([FANC wiki](https://github.com/htem/FANC_auto_recon/wiki)), and manual CATMAID reconstructions from 2021–22 hosted by VFB.
- **Clients.** `fanc-fly` (Python) and `fancr` (R).

### 5.4 Annotations and cell typing
- **CAVE annotation tables.**
  - `neuron_information` holds hierarchical free-text tags: primary class; hemilineage (e.g. `0A, 1A, …, 20A.22A, 24B.25B, 26X, 27X`, **without the leading zero** that MANC uses as `00A`); "fast neurotransmitter"; soma side ("left soma" / "midline soma" / "right soma"); soma segment; projection patterns; body part and muscle innervated; publication; free-text "neuron identity".
  - Dedicated tables: `peripheral_nerves`, `neck_connective` (at y = 75200), `leg_mn_cell_type_table_v0`, `wing_motor_neuron_table_v0`, `nerve_bundle_fibers_v0`, `neurotransmitter_hemilineage_table` ([annotation wiki](https://github.com/htem/FANC_auto_recon/wiki/Neuron-annotations)).
- **Typing status and matching to MANC.** There is no dataset-wide systematic typing (not found). Stürner, Brooks et al. 2025 (*Nature*) typed the neck-connective DNs, ANs and SAs across FAFB, FANC and MANC. Their Supplemental_file13 gives MANC-matched types for 736 intrinsic neurons, 2 EAs and 64 MNs in FANC.
  - Columns include `manc_match_id`, `manc_group`, `confidence_manc_match_1_5`, `systematic_type` and `dimorphic` ([2023neckconnective](https://github.com/flyconnectome/2023neckconnective)).
  - BANC's meta carries `fanc_cell_type` / `fanc_match`.
- **Neurotransmitters.** No EM-based NT prediction for FANC was found. The only NT information is hemilineage-derived tags ("cholinergic", "GABAergic", "glutamatergic").

### 5.5 Synapses and thresholds
- Automated detection; "over 80% of predicted partners with more than three synapses are true partners" ([PMC page summary](https://pmc.ncbi.nlm.nih.gov/articles/PMC11348827/)). Public count tables are exported at 3 or more synapses.
- Neither a synapse score semantic nor a license was found.

### 5.6 Neuropils and laterality
- **Neuropil names in the public tables (observed):**
  - Neuromeres: `ProNm_L/R`, `MesoNm_L/R`, `MetaNm_L/R`, `ANm_L/R`.
  - Tectulum: `NTct_*`, `WTct_*`, `HTct_*`, `IntTct_*`, `LTct_*`.
  - Others: `AMNp_*`, `mVAC_*`.
  - Tracts: `DLT_*`, `DLV_*`, `DMT_*`, `ITD_*`, `ITD_HC_*`, `ITD_HT_*`, `MDT_*`, `VLT_*`, `VTV_*`, `CFF_*`.
  - `unassigned`.
- These differ from MANC's `LegNp(T1)(L)` style **and** from BANC's `ProNM-T1`. Even `IntTct` and `LTct` are sided in FANC.

### 5.7 License and citation
- **License.** Data license not found. The `FANC_auto_recon` code is GPL-3.0 (GitHub metadata).
- **Citation.** Azevedo, Lesser, Phelps, Mark et al. 2024 *Nature* [10.1038/s41586-024-07389-x](https://doi.org/10.1038/s41586-024-07389-x); Phelps et al. 2021 *Cell*.

---

## 6. Hemibrain v1.2.1 (brief)
- **Dataset string.** `hemibrain:v1.2.1`, last-mod 2020-12-05. Female; "roughly half of the brain, with ~22k fully reconstructed neurons and ~76k truncated neurons" ([neuPrint datasets](https://neuprint.janelia.org/api/dbmeta/datasets)). Voxels are 8 nm. The v1.2 totals are 9,496,606 pre and 64,139,744 post ([v1.2 Meta in the neo4j zip](https://storage.googleapis.com/hemibrain-release/neuprint/hemibrain_v1.2_neo4j_inputs.zip)).
- **IDs.** `bodyId`, observed range 200,326,126 to 7,112,622,044. "What will not change are the unique body ID numbers … we strongly advise that such body IDs be included in any publications" ([Scheffer 2020](https://europepmc.org/articles/PMC7546738)).
- **Neuron properties (v1.2).** `bodyId, pre, post, upstream, downstream, mito, status, statusLabel, cropped, instance, synonym, type, cellBodyFiber, somaLocation, somaRadius, size, roiInfo` ([v1.2 Meta](https://storage.googleapis.com/hemibrain-release/neuprint/hemibrain_v1.2_neo4j_inputs.zip)). **There is no NT property.** Eckstein et al. hemibrain predictions are separate files: `gs://hemibrain/v1.2/hemibrain-v1.2-tbar-neurotransmitters.feather.bz2` and `…-body-mean-neurotransmitters.feather` (6 classes plus `neither`, and `predicted_nt`) (observed; [Zenodo 10593546](https://zenodo.org/records/10593546)).
- **Laterality.** The instance suffix `_L`/`_R` usually encodes soma side, but Schlegel et al. made "a sizeable number of manual adjustments" ([supp README](https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/README.md)). Morphology types carry connectivity-type suffixes `_a`, `_b`.
- **ROI hierarchy.** There are 230 ROIs, 63 of them primary/super-level, plus `nonHierarchicalROIs` `dACA(R); lACA(R); vACA(R); MB(+ACA)(R); FB-column3`. The root is `hemibrain`, with parents such as:
  - `OL(R)`, `MB(+ACA)(R)` → `MB(R)` → `CA(R)`, `PED(R)`, `aL(R)` → `a1(R)`…
  - `CX` → `FB` → `FBl1–9`; `EB` → `EBr*`; `PB` → `PB(L1–9/R1–9)`; `NO` → `NO(L)`, `NO(R)`
  - `LX(R)`, `VLNP(R)`, `SNP(R/L)`, `INP`, `AL(R)` → 58 glomeruli `AL-DA1(R)`…, `VMNP`, `PENP` → `SAD` → `AMMC`, `SAD(-AMMC)`
  - `GNG`, and tracts `AOT(R)`, `GC`, `GF(R)`, `mALT`, `POC`
  - Names use set-difference and union syntax: `LAL(-GA)(R)`, `CRE(-ROB,-RUB)(R)`, `MB(+ACA)(R)` (observed in the [v1.2 Meta](https://storage.googleapis.com/hemibrain-release/neuprint/hemibrain_v1.2_neo4j_inputs.zip)).
  - "(L)/(R)" follows Ito et al. 2014 "with the addition of (R) and (L) to specify the side of the soma for that region" ([Scheffer 2020](https://europepmc.org/articles/PMC7546738)).
- **Synapse thresholds.** Per-synapse `confidence`. Meta: `preHPThreshold` 0.0, `postHPThreshold` 0.7, `postHighAccuracyThreshold` 0.5. `ConnectsTo` edges carry `weight`, `weightHP` and `roiInfo` ([neuPrint user guide](https://neuprint.janelia.org/public/neuprintuserguide.pdf)). The `cropped` flag marks neurons truncated at the volume boundary.
- **Downloads.**
  - [exported-traced-adjacencies-v1.2.tar.gz](https://storage.cloud.google.com/hemibrain/v1.2/exported-traced-adjacencies-v1.2.tar.gz)
  - `gs://hemibrain/v1.2/` synapse feathers
  - `gs://hemibrain-release/neuprint/hemibrain_v1.2_neo4j_inputs.zip`
- **Electrical synapses.** "Gap junctions … are difficult to reliably detect by FIB-SEM" and were not included ([Scheffer 2020](https://europepmc.org/articles/PMC7546738)).
- **License and citation.** "Hemibrain is licensed under CC-BY" ([Janelia](https://www.janelia.org/project-team/flyem/hemibrain)). The `LICENSE.txt` inside the neo4j zip, however, is a BSD-3-style HHMI 2020 text (observed). Cite Scheffer et al. 2020, *eLife* 9:e57443.

## 7. Optic lobe (`optic-lobe:v1.0.1`, `optic-lobe:v1.1`) (brief)
- **Scope.** The right optic lobe of the **same male specimen as MaleCNS**. v1.0 was released 2024-04-18 (neuPrint string `optic-lobe:v1.0.1`) and v1.1 on 2025-03-10. "More than 50,000 individual neurons of over 700 distinct types" ([Janelia optic lobe](https://www.janelia.org/project-team/flyem/optic-lobe)). neuPrint's description: "For new analyses, use the full MaleCNS connectome" ([neuPrint datasets](https://neuprint.janelia.org/api/dbmeta/datasets)).
- **IDs.** BodyIds overlap MaleCNS for **52,336 IDs, and 99.6% of typed overlaps have the same type**. The same IDs therefore denote the same neurons, because the segmentation lineage is shared (observed from Codex MAOL v1.1 and MCNS v1.0). Contrast MANC and MCNS in §4.2.
- **NT fields** ([OL v1.1 Meta](https://storage.googleapis.com/flyem-optic-lobe/v1.1/optic-lobe-v1.1-neuprint-tables/Neuprint_Meta.csv)):
  - `predictedNt` and `predictedNtConfidence`.
  - `celltypePredictedNt` and `celltypePredictedNtConfidence`.
  - `consensusNt`, with `ntReference`.
  - `otherNt` and `otherNtReference`.
  - The class set is acetylcholine, dopamine, gaba, glutamate, histamine, octopamine, serotonin, unclear.
  - Cross-links: `flywireType`, `mancGroup`, `mcnsSerial`, `itoleeHl`, `trumanHl`, `dimorphism`, `matchingNotes`.
  - Column/hex coordinates: `assignedOlHex1/2`.
- **ROIs.** CNS-wide `(L)/(R)` ROIs plus `vnc-shell`, and layer ROIs such as `ME_R_layer_01…10`, `LO_R_layer_1…7`, `LOP_R_layer_1…4`.
- **Thresholds.** Meta: pre-HP 0.0, post-HP 0.7, postHighAccuracy 0.5.
- **Flat connectome** in `gs://flyem-optic-lobe/v1.1/optic-lobe-v1.1-flat-connectome/`, filtered at **`minconf-0.5`**. Files include `connectome-weights…` (`body_pre, body_post, weight`) and `syn-partners…` (`x_pre…conf_pre…body_post, conf_post, primary_post`) (observed).
- **License and citation.** CC-BY; Nern et al. 2025 *Nature* [10.1038/s41586-025-08746-0](https://doi.org/10.1038/s41586-025-08746-0) ([Janelia](https://www.janelia.org/project-team/flyem/optic-lobe)).

---

## 8. Cross-dataset matching resources, and is there a canonical type ontology?

**Resources that exist:**

1. **FlyWire ↔ hemibrain.** Schlegel et al. 2024 matched nearly all hemibrain neurons morphologically, but about one-third of hemibrain cell types "could not be reliably reidentified". They proposed that a cell type is defined across brains. The link lives in the `hemibrain_type` column ([Schlegel 2024](https://europepmc.org/articles/PMC11446831)). NBLAST matrices are on [Zenodo 10877326](https://zenodo.org/records/10877326).
2. **FlyWire ↔ MaleCNS.** Berg et al. 2025/2026 added `supertype`, `dimorphism` and `matching_notes` to FlyWire annotations v3.x ([flywire_annotations](https://github.com/flyconnectome/flywire_annotations)). MaleCNS in turn carries `flywireType`, `hemibrainType`, `mancType`, `mancBodyid` and `supertype` (observed as Codex MCNS label keys).
3. **FAFB ↔ FANC ↔ MANC for neck-connective neurons.** Stürner, Brooks et al. 2025 matched DNs, ANs and SAs across the three datasets, with 1–5 match confidences and dimorphism files ([2023neckconnective](https://github.com/flyconnectome/2023neckconnective)).
4. **BANC ↔ everything.** BANC's meta has per-dataset `*_cell_type`, `*_match` and `*_nblast_match` columns for FAFB 783, MANC 1.2.1, MaleCNS 0.9, hemibrain 1.2.1 and FANC 1116. There are curated `banc_*_reviewed_matches.csv` files and NBLAST feathers ([README.txt](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt)). BANC names are **inherited** from FAFB (brain and DNs) and MANC (VNC and ANs). The BANC team also re-harmonized FAFB and MANC typology in the paper's Supplementary Data 1–5 ([Bates 2026](https://europepmc.org/articles/PMC13518251)).
5. **The "BANC framework" compiled tables.** `compiled_data/{banc_888, fafb_783, manc_121, hemibrain_121, malecns_09}` use unified column names: `root_id`, `super_class`, `cell_class`, `cell_sub_class`, `cell_type`, `hemilineage`, `region`, `side`, `flow`, and edgelists `pre, post, count, norm` ([README.txt](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt)). This is the closest existing analogue of BrainIR's goal. Limitations:
   - It is a derived product, with some documentation inconsistencies.
   - Its `super_class` vocabularies still differ per dataset.
   - IDs are strings.
6. **natverse coconatfly and coconat (R).** Namespaced keys of the form `"<dataset>:<id>"`: "Neurons within a dataset will be identified by numeric ids but these may not be unique across datasets" ([keys](https://natverse.org/coconatfly/reference/keys.html)).
   - Registered short names: `fw` (FlyWire, F), `hb` (hemibrain, F), `ol` (opticlobe, M), `mc` (malecns, M), `mv` (manc, M), `fv` (fanc, F), `bc` (banc, F), `yv` (yakubavnc, M) ([zzz.R](https://github.com/natverse/coconatfly/blob/master/R/zzz.R)).
   - `cf_meta` harmonizes top-level classes "to malecns-style values", with domain prefixes (`cb_`, `vnc_`, `ol_`), and normalizes side to L/R/M ([meta.R](https://github.com/natverse/coconatfly/blob/master/R/meta.R)).
   - The Python analogue is `cocoa`.
7. **Codex.** Cross-dataset search with `@` (e.g. `@ T4a`), a "Cell Types" count comparison across datasets, and a common `neurons.csv` layout for all five datasets (observed): `Root ID, Top in/out region, Community labels, Predicted NT type, Predicted NT confidence, Verified NT type, Verified Neuropeptide, Body Part, Function, Flow, Super Class, Class, Sub Class, Hemilineage, Nerve, Soma side, Primary Cell Type, Alternative Cell Type(s), …` ([Codex FAQ](https://codex.flywire.ai/faq)).
8. **flytable.** The Cambridge SeaTable (`flytable.mrc-lmb.cam.ac.uk`) is the working annotation store for FlyWire, MaleCNS and related projects. It needs a user account and token ([fafbseg flytable_login](https://natverse.org/fafbseg/reference/flytable_login.html)). BANC has its own SeaTable ([meta doc](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/documentation/banc_888_meta.md)).
9. **Virtual Fly Brain and FBbt (Drosophila Anatomy Ontology).** FlyWire provides `fbbt_id`, "used for ontology terms (like cell types)", and `vfb_id`, "an identifier for individual neurons" ([supp README](https://github.com/flyconnectome/flywire_annotations/blob/main/supplemental_files/README.md)). MANC carries `vfbId` (e.g. `VFB_jrcv07ps`, observed in Codex labels). Codex's `processed_labels` pair names with FBbt IDs.

**Verdict.** **No source provides an authoritative, complete, cross-dataset cell-type ontology with stable identifiers.**
- FBbt is the only formal ontology. It covers a minority of connectome types: 2,527 FBbt terms across 28,905 of about 139k FlyWire neurons (observed).
- In practice, "canonical" names are **conventions**: FlyWire/Schlegel names for the brain, MANC systematic types for the VNC, and MaleCNS `supertype` as a cross-sex grouping.
- Matches are many-to-many and carry method and confidence metadata.

---

## 9. Implications for a canonical cross-dataset schema (BrainIR requirements)

1. **Namespaced neuron identity; never bare integers.**
   - Use a composite key `(dataset, release, native_id)` and a derived string key in the coconatfly style (e.g. `mv:10000@manc:v1.2.1`).
   - Evidence: MANC and MaleCNS share 19,344 integer IDs that are *different* neurons (§4.2). FAFB and BANC root IDs share the `72057594…` space (§3.2).
   - All observed native IDs fit in **int64**; the maximum is about 7.2e17. Sources deliver them variously as int64, uint64 (Janelia synapse feathers) or **strings** (BANC compiled tables, `supertype` as `"12693.0"`), so normalize on ingest and keep the raw form.
2. **Model the specimen separately from the dataset release.**
   - optic-lobe:v1.1 and MaleCNS are the same fly and share bodyIds for the same neurons (99.6% type agreement, §7). BANC, FAFB, FANC, MANC and hemibrain are each distinct individuals.
   - Add `specimen` (sex, individual, CNS coverage) and `segmentation_lineage` entities, so that same-specimen ID reuse can be expressed explicitly rather than assumed.
3. **Treat versioning semantics as a per-dataset type.**
   - **neuPrint** releases (`manc:v1.2.1`, `v1.2.3`): bodyIds are stable "barring major proofreading". Annotation-only patches can share a UUID; v1.2.1 and v1.2.3 are the same UUID with a property update.
   - **CAVE** releases: pin `materialization_version` **and** its timestamp (630 = 2023-03-21, 783 = 2023-09-30; BANC 626 / 850 / 888 / 890). Root IDs churn: 40.2% of BANC proofread neurons changed between v626 and v888.
   - Store per neuron the stable anchors (`supervoxel_id`, `nucleus_id`, anchor position with units, and for BANC the representative-point ID). Keep an **ID-lineage table** `(dataset, id_old, version_old, id_new, version_new, method)`. Record the static segmentation source used, e.g. `gs://flywire_v141_m783`.
4. **Treat a synapse detector as part of the version.**
   - FAFB v783 exists with **Buhmann** synapses (cleft score > 50) and **Princeton** synapses (Codex default since July 2025).
   - BANC has **v2** (size ≥ 5, or > 5 depending on the source) and **v3** (size ≥ 10) for the same materialization.
   - Every edge and synapse row needs `synapse_table_id` (detector plus version), `filter_params` (e.g. `cleft_score_min`, `size_min`, `conf_pre_min`, `conf_post_min`, dedup radius, autapse policy) and `count_threshold`.
5. **Store edges unthresholded where possible, and make thresholds query-time parameters with explicit provenance.** Defaults differ:
   - FAFB: 5 or more (optic lobes 2 or more).
   - BANC in Codex: 3 or more.
   - MANC and MAOL in Codex: 1 or more.
   - FANC public exports: 3 or more.
   - BANC paper: none.
   - neuPrint: `weight` versus `weightHP`.

   Also:
   - Allow **per-ROI edge splits**. Codex FAFB rows are (pair, neuropil), so single rows can be below the pair threshold.
   - Define `n_synapses` as the number of pre→post links (polyadic), distinct from presynaptic-site (T-bar) counts.
   - Normalized weights (`norm = count / total_input`) must declare their denominator. BANC's `post_count` differs from other datasets' `total_input`, and the hemibrain compiled table has no total.
6. **Keep both `type` and `systematic_type`, plus group structure.**
   - MANC separates literature `type` from `systematicType`. Hemibrain separates morphology types from connectivity types (`_a`/`_b`). FlyWire has `cell_type` plus `hemibrain_type` (which can be composite, e.g. `SIP078,SIP080`) plus `supertype`. Codex has a primary `resolved_type` plus alternative types.
   - Required fields: `type`, `systematic_type`, `type_source`, `alternative_types[]`, `instance`, `group_id` (left/right homologues), `serial_id` (serial homologues, VNC), `supertype`.
   - Treat placeholders as first-class "unresolved" markers: `CBxxxx`, `hb<bodyId>`, `SNxxxx`, `INXXX###` (hemilineage unknown), `TBD`.
7. **Store controlled vocabularies as data, never as enums baked into code.**
   - `super_class` and `class` values differ between FlyWire, BANC (two conflicting BANC doc versions), MANC (`intrinsic neuron` in neuPrint versus Codex snake_case) and hemibrain.
   - Keep `(dataset, field, raw_value)` → `canonical_value` mapping tables with provenance. coconatfly's mapping to MaleCNS-style values is a useful starting point, and it fits BrainIR's primary dataset.
8. **`flow` is relative to the imaged volume.** For DNs it is efferent in FAFB, afferent in MANC and intrinsic in BANC; ANs flip the other way (§4.4). Store `flow_raw` and derive a **CNS-relative** direction from class plus specimen coverage.
9. **Split laterality into several fields with a canonical enum.**
   - Fields: `soma_side`; `root_side` / nerve-entry side (MANC `rootSide`, FlyWire sensory `side`); `side_source`; synapse-level side; and optional laterality indices (BANC `*_side_index`).
   - Canonical enum: {left, right, midline, bilateral, unknown}.
   - Raw vocabularies to map: left/right/center/na, L/R/M, RHS/LHS/Midline/BIL/MID, and "left soma" tags.
   - Record dataset-level **coordinate handedness**. FAFB images and coordinates are mirror-inverted while labels are biologically correct.
   - Do not rely on Codex "Soma side" for neurons without a soma in the volume; it is filled from root side.
10. **ROIs need a dataset-scoped, hierarchical ROI table plus a cross-dataset ROI map.**
    - ROI table fields: `(dataset_release, roi_name, parent, is_primary, kind ∈ {neuropil, nerve, tract, layer, column, region}, side, atlas_source ∈ {Ito2014, Court2020, …})`.
    - The source structures differ:

      | Dataset | ROI structure |
      |---|---|
      | FAFB | Flat: 78 plus `UNASGD`, with a `_L`/`_R` suffix |
      | Hemibrain | 230 ROIs in a hierarchy; `(L)`/`(R)` plus set-difference names such as `LAL(-GA)(R)`; non-hierarchical ROIs |
      | MANC | 59 ROIs, neuropils plus nerves, nested parentheses (`HTct(UTct-T3)(R)`); annotation fields use `_R` |
      | FANC | `ProNm_L`… plus tracts |
      | BANC | Unsided `neuropil` plus `side`, and atlas-prefixed comma-joined `neuropil_detailed`; unnormalized `region` |

    - Synapse→ROI assignment must record its rule: presynaptic point with nearest-within-10 µm (FlyWire), alpha-shape with nearest fallback (BANC), or postsynaptic `roi_post` (MANC flat file). Allow **multi-membership**.
11. **Store neurotransmitter predictions as distributions with explicit class sets and aggregation methods.**
    - Class sets: FAFB 6 (+neither); MANC 3 + unknown; BANC 8 (+`none`); OL 7 + unclear; hemibrain 6 + neither.
    - Aggregation methods:
      - FlyWire: mean probability, argmax; the confidence is the mean.
      - Codex: argmax of means, sometimes blanked.
      - MANC: mean probabilities, with an explicit unknown class.
      - BANC: summed probabilities, argmax; score = top share.
      - Eckstein `conf_nt_p`: a confusion-calibrated confidence.
      - OL: neuron-level, cell-type-level and consensus with literature.
    - Proposed table: `nt_prediction(neuron_key, level ∈ {synapse, neuron, cell_type}, class_set_id, class, prob, method, model_id, source)`.
    - Keep **verified NT/neuropeptides** separately, multi-valued and with sources. They include negative evidence (`gaba-negative`) and co-transmission strings (`gaba, nitric oxide`).
12. **Carry spatial units and spaces on every coordinate.**
    - Resolutions: FAFB 4 × 4 × 40 nm voxels, while Codex positions and Zenodo synapse coordinates are in nm; FANC 4.3 × 4.3 × 45; BANC 4 × 4 × 45 (synapses v2 in nm, v3 in 16 × 16 × 45 voxels); MANC, hemibrain, OL and MCNS 8 nm isotropic.
    - Store `(x, y, z, unit, space_id)`, and keep transforms and template spaces (JRC2018F, JRC2018VNC, BANC space) as separate entities.
13. **Normalize proofreading and completeness status with the raw value alongside.**
    - Raw values to handle:
      - FlyWire `proofread_neurons` membership.
      - BANC `proofread` vs `roughly_proofread`, which are disjoint string "TRUE"/"FALSE" flags.
      - neuPrint `status` / `statusLabel`.
      - Hemibrain `cropped`.
      - FANC first-pass and second-pass tables.
    - Add an `entity_kind` field (neuron, glia, trachea, not_a_neuron, fragment) so non-neuronal objects can be filtered.
14. **Provide an electrical-synapse edge type, but mark it unavailable.** No dataset detects gap junctions. MANC provides only a neuron-level `transmission` label (electrical, putative electrical, neurosecretory), so store that as a neuron attribute with provenance.
15. **Make matches a first-class, many-to-many table.**
    - Schema: `(key_a, key_b, level ∈ {neuron, type, group}, method ∈ {NBLAST, connectivity, manual, alignment}, score, confidence_scale, validated, source, source_version)`.
    - Do not assume name equality means type equality. Composite matches, splits, sex-specific and dimorphic flags, and 1–5 confidence scales all occur in the sources.
16. **Canonical type ontology.** Because none exists (§8), BrainIR needs its own `canonical_type` table with synonyms and FBbt cross-references where available, populated from Schlegel, Berg, BANC and MANC mappings. Record **which dataset's naming is authoritative per CNS region**, following BANC's policy: FAFB for the brain and DNs, MANC for the VNC and ANs.
17. **Keep developmental annotations with their nomenclature system.**
    - Hemilineage systems: ItoLee versus Hartenstein (brain); Truman-style (VNC) with combined (`20A.22A`), ambiguous (`17X`) and unknown (`TBD`) values; zero-padding differences (FANC `0A` versus MANC `00A`).
    - VNC-specific fields (`soma_neuromere`, `birthtime`, `serial_motif`, `long_tract`, `modality`) belong in an extension table.
18. **Pin files by checksum and retrieval date.**
    - Codex files are regenerated; for example, FAFB 783 `classification.csv.gz` was updated 2026-02-24. BANC compiled files change after publication, and MANC has annotation patches.
    - Record the GCS `md5Hash` / `crc32c` / `generation`, or the DOI and version (Zenodo; Dataverse v3.0), for every ingested artifact.
19. **Store license and citation per data product and propagate them to derived outputs.**
    - Licenses: FlyWire is CC BY-NC 4.0 according to flywire.ai, but the Zenodo dumps say CC-BY 4.0; BANC, MANC, OL and hemibrain are CC-BY; FANC is unknown; the hemibrain neo4j bundle carries a BSD-style text.
    - Keep multi-part citation requirements (FlyWire's per-component table; BANC's paper plus Dataverse).
    - Codex's `labels.csv` contains contributor names and affiliations. Avoid redistributing them unless required.
20. **Plan for access and auth drift.**
    - neuPrint tokens were invalidated in August 2026.
    - Codex requires Google sign-in and `api_token` for downloads.
    - The FANC, BANC-production and FlyWire-production CAVE datastacks are restricted.
    - Keep ingestion connectors separate from the canonical store, and record the access channel in provenance.

---

## 10. Not found / open questions
- **FANC:** no explicit data license and no public CAVE datastack found; only GCS dumps exist. No published EM-based NT predictions found.
- **Princeton FAFB synapses:** no documented score or size threshold found, and no description of how `nt_type` is assigned in `connections_princeton`.
- **Codex rule for blank FAFB `nt_type`:** found in 19,658 neurons, but the rule is not documented.
- **MANC and hemibrain neuPrint:** the minimum synapse confidence used at ingestion, and the exact role of `postHighAccuracyThreshold` in `weight`, are not found. The Meta values are reported above.
- **MANC v1.2.x neuron-property vocabulary:** the neuPrint property values could not be checked without a token. v1.0 values are reported, and v1.2.1 is seen only through Codex's harmonized view.
- **BANC size cut** (≥ 5 versus > 5) and **BANC `side` "center"** appear inconsistently across BANC sources.
- **"XXX" meaning in MANC types:** inferred (undetermined hemilineage) from data plus the paper's TBD rule. No verbatim definition was found.

---

## Appendix A: primary URLs by dataset
- **FlyWire / FAFB:**
  - [Codex FAQ](https://codex.flywire.ai/faq) · [About FlyWire](https://codex.flywire.ai/about_flywire) · [flywire.ai guidelines](https://flywire.ai/guidelines) · [ToS](https://flywire.ai/tos) · [citation table](https://docs.google.com/spreadsheets/d/1eOPxOYoalArVDIhzVis3CsKjETzkdFkRtXSHHY3XdSU)
  - Zenodo: [10676866](https://zenodo.org/records/10676866) · [10877326](https://zenodo.org/records/10877326) · [10593546](https://zenodo.org/records/10593546) · [12588557](https://zenodo.org/records/12588557)
  - [flywire_annotations](https://github.com/flyconnectome/flywire_annotations) · [FlyConnectome CAVE tutorial](https://github.com/seung-lab/FlyConnectome) · [fafbseg-py](https://github.com/flyconnectome/fafbseg-py)
  - Papers: [Dorkenwald 2024](https://doi.org/10.1038/s41586-024-07558-y) · [Schlegel 2024](https://doi.org/10.1038/s41586-024-07686-5) · [Eckstein 2024](https://doi.org/10.1016/j.cell.2024.03.016) · [Matsliah 2024](https://doi.org/10.1038/s41586-024-07981-1) · [Yu 2025](https://www.biorxiv.org/content/10.1101/2025.07.11.664377v1)
- **BANC:**
  - [BANC-project](https://github.com/htem/BANC-project) · [Nature 2026](https://doi.org/10.1038/s41586-026-10735-w) · [Dataverse](https://doi.org/10.7910/DVN/7WTH1N)
  - [bucket README](https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/README.txt) · [bancr](https://natverse.org/bancr/) · [Codex BANC](https://codex.flywire.ai/banc)
- **MANC:**
  - [Janelia MANC](https://www.janelia.org/project-team/flyem/manc-connectome) · [neuPrint datasets JSON](https://neuprint.janelia.org/api/dbmeta/datasets) · [flyem-manc-exports](https://console.cloud.google.com/storage/browser/flyem-manc-exports)
  - Papers: [Takemura](https://elifesciences.org/reviewed-preprints/97769) · [Marin](https://elifesciences.org/reviewed-preprints/97766) · [Cheong](https://elifesciences.org/reviewed-preprints/96084)
- **FANC:**
  - [FANC_auto_recon](https://github.com/htem/FANC_auto_recon) · [wiki](https://github.com/htem/FANC_auto_recon/wiki) · [Azevedo 2024](https://doi.org/10.1038/s41586-024-07389-x) · [2023neckconnective](https://github.com/flyconnectome/2023neckconnective)
- **Hemibrain:**
  - [Janelia hemibrain](https://www.janelia.org/project-team/flyem/hemibrain) · [Scheffer 2020](https://doi.org/10.7554/eLife.57443)
- **Optic lobe:**
  - [Janelia optic lobe](https://www.janelia.org/project-team/flyem/optic-lobe) · [Nern 2025](https://doi.org/10.1038/s41586-025-08746-0)
- **Cross-dataset:**
  - [coconatfly](https://natverse.org/coconatfly/) · [Virtual Fly Brain](https://www.virtualflybrain.org/) · [SJCABS fly_connectome_data_tutorial](https://github.com/sjcabs/fly_connectome_data_tutorial), a secondary source written by the BANC first author
