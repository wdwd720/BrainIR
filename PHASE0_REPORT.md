# BrainIR — Phase 0 report (data & research foundation)

**Date:** 2026-09-22 · **Spec:** [`goal1.md`](goal1.md) · **Status:** Phase 0 complete. Every completion criterion
is met; the evidence for each is in §1. One *optional* verification needs a neuPrint login (§15).

> **Answer-bearing document.** §13 names the published benchmark circuit. Never give this file to a BrainIR
> discovery system; see `benchmarks/dng100_walking_cpg/README.md`.

---

## 1. Completion criteria

| # | criterion | status | evidence |
|---|---|---|---|
| 1 | Project exists locally and is reproducible | ✅ | `C:\Dev\BrainIR` (git; `uv.lock`; Python 3.12.14 pinned). Two independent real-data builds produce byte-identical outputs (§6.4) |
| 2 | MaleCNS v1.0 structured connectome available locally | ✅ | 10 official files, 18.72 GB, every one checksum-verified against GCS and pinned by generation (`data/raw/male-cns/v1.0/_acquisition.json`) |
| 3 | Normalised into the BrainIR schema | ✅ | 6 canonical Parquet tables (`data/processed/male-cns/v1.0/`); schema in `docs/schema.md` |
| 4 | Deterministic ingestion pipeline | ✅ | `uv run brainir ingest`; byte-identical rebuilds (synthetic test + real double build) |
| 5 | Explicit provenance/versioning | ✅ | `data/manifests/male-cns_v1.0.manifest.json`: URLs, generations, SHA-256, row counts, schemas, transformations, git commit |
| 6 | Validation/tests pass | ✅ | Build validation: 53 pass, 0 fail, 1 documented warning. `pytest`: 86 passed. Independent audit: 23/23 |
| 7 | Basic graph queries work | ✅ | `brainir.graph.Connectome` + `brainir` CLI (neuron/type/search/up/down/edge/khop/paths/synapses) |
| 8 | DNg100 and the walking benchmark are locatable | ✅ | §13; `benchmarks/dng100_walking_cpg/malecns_v1.0_findings.md` |
| 9 | Literature summarised accurately | ✅ | `research/literature/`; key claims re-checked against the full text |
| 10 | A fresh session can understand the repo | ✅ | `CLAUDE.md`, `README.md`, `research/LOG.md`, this report |

## 2. Repository and environment

- **Repository:** `C:\Dev\BrainIR` (git, branch `main`).
  - Code: `src/brainir/`. Tests: `tests/`. Scripts: `scripts/`.
  - Research notes: `research/`. Benchmark (answer key): `benchmarks/`. Docs: `docs/`.
- **Machine:**
  - Windows 11 Pro 26100; AMD Ryzen 9 6900HX (8C/16T); 30 GB RAM; ~100 GB free on C: before Phase 0.
  - AMD integrated GPU only (no CUDA). WSL2 Ubuntu 22.04 and Docker are present but unused.
  - Internet: ~5–8 MB/s from GCS.
- **Toolchain:**
  - uv 0.12.18 (installed via winget for the user); uv-managed CPython 3.12.14.
  - Key packages: pandas 3.0.6, pyarrow 25.0.1, duckdb 1.5.5, numpy 2.5.3, scipy 1.18.1, neuprint-python 0.6.3,
    pydantic 2.13.5 (all pinned in `uv.lock`).
  - The system CPython 3.12 install is broken (its `Lib` is missing `encodings`). It is not used, and I did not
    modify it.
- **Existing work:** none found. `C:\Dev\BrainIR` held only `goal1.md`, and no neuroscience packages were installed.
- **Credentials:**
  - No neuPrint or CAVE tokens exist. Chrome has no neuPrint session (HTTP 401).
  - neuPrint invalidated all API tokens in August 2026.
  - Nothing secret is stored, printed or committed.

## 3. Dataset and sources

- **Dataset:** MaleCNS **v1.0**, i.e. neuPrint `male-cns:v1.0`. Released 2026-06-08; v0.9 was 2025-10-05.
  - Specimen: one adult male *Drosophila melanogaster*; whole CNS (brain, both optic lobes, VNC); 8 nm isotropic
    voxels.
  - Snapshot: DVID UUID `98d6995edd46478f896544dceaa6eab1` (bulk export); segmentation edit 2026-03-28; property
    update 2026-04-30.
- **Official sources:**
  - https://male-cns.janelia.org/ (download page and release notes snapshotted into `data/raw/.../docs/`);
  - bucket `gs://flyem-male-cns/v1.0/` (`connectome-data/flat-connectome/` and `database/neuprint-inputs/`);
  - https://neuprint.janelia.org.
  - Export semantics come from https://github.com/janelia-flyem/flyem-snapshot.
- **Acquired files** (all read-only; CRC32C/MD5 verified; GCS generation pinned in `src/brainir/sources/registry.py`):

| key | rows | size | use |
|---|---:|---:|---|
| neuprint_meta_json / _csv | 1 | 3.0 MB | ROI hierarchy, thresholds, totals |
| body_annotations | 211,577 | 14.5 MB | curated annotations |
| body_neurotransmitters | 1,835,518 | 43.3 MB | NT predictions |
| neuprint_neurons | 88,404,403 segments | 4.65 GB | node properties, per-ROI counts, `:Neuron` label |
| neuprint_connections | 151,856,684 pairs | 3.53 GB | edges (weight, weightHP, per-edge roiInfo) |
| flat_connectome_weights | 151,856,684 | 1.05 GB | independent cross-check |
| syn_partners | 311,833,243 synapses | 6.78 GB | synapse-level checks and extraction |
| tbar_neurotransmitters | 45,656,140 T-bars | 2.65 GB | per-T-bar NT (for later phases) |
| neuroglancer_scene | – | 0.06 MB | layer URLs |

- **Not acquired:**
  - EM volumes and voxel segmentation: not needed for graph work.
  - `syn-points` (13 GB): redundant.
  - `body-stats` and the traced/significant variants: derivable. Registered as optional.
- **License:** CC-BY 4.0.
- **Citation:** Berg, Beckett, Costa, Schlegel, Januszewski *et al.*, *Cell* 2026, doi:10.1016/j.cell.2026.08.015
  (preprint doi:10.1101/2025.10.09.680999).

## 4. Storage footprint

| area | size |
|---|---:|
| `data/raw` | 18.7 GB (immutable) |
| `data/processed` | ~0.21 GB |
| `data/cache` | logs only; DuckDB spill files are per-process and cleaned |
| git repo | < 1 MB of text |
| external reference (authors' MaleCNS tables, pinned) | 75 MB in `data/raw/external/` |

## 5. Canonical data model

The full reference is `docs/schema.md`, generated from code (a test fails if it is stale).

- **Evidence kinds on every column:**
  - `identifier`
  - `em_reconstruction`, `derived_anatomy`
  - `curated_annotation`
  - `ml_prediction`, `literature_label`
  - `derived_hypothesis`
  - `model_parameter`, `experimental_measurement`
  - `provenance`
- **Tables (per dataset/version partition):**
  - `neurons`: 46 columns, including IDs, types, classes, two hemilineage nomenclatures, soma/root/derived side,
    soma location, status, counts to all partners vs to neurons, five NT fields and cross-dataset matches.
  - `connections`: `synapse_count`, `synapse_count_hp`, `is_autapse`, dominant neuropil.
  - `connection_neuropils`: per-edge counts by PSD neuropil, plus `<unassigned>`.
  - `neuron_neuropils`: per-neuron pre/post counts by neuropil.
  - `neuropils`: ROI catalogue as a DAG.
  - `synapses`: on demand only.
  - `neuron_annotations_source`: verbatim typed source columns.
- **Records (pydantic):**
  - `DatasetVersion`, `Neuron`, `DirectedConnection` (no weight field), `Synapse`.
  - `SignHypothesis` (rule-versioned), `NeurotransmitterPrediction`, `ModelParameter`.
  - `Experiment` / `Trial` / `Intervention` / `Measurement` / `TimeSeries` / `TargetSpec`.
- **Key decisions:**
  - `neuron_uid = dataset:version:id`.
  - Sign hypotheses are computed, not stored (`brainir.sign.conventional-v1`: ACh +, GABA −, Glu − and histamine −
    context-dependent, monoamines none).
- **Multi-dataset accommodation:** see `research/data_ecosystem.md`. The planned tables are anchors and ID lineage
  for CAVE datasets, cross-dataset matches, NT distributions and vocabulary maps.

## 6. Ingestion process

### 6.1 Command
`uv run brainir ingest` runs `src/brainir/ingest/malecns.py`. It takes about 7 minutes with 8 threads and a 6 GB
DuckDB memory limit.

### 6.2 Steps
1. Verify acquisition: files exist with pinned sizes, checksums and generations.
2. Build the ROI catalogue.
3. Load annotations, casting float-encoded integer IDs losslessly (the build aborts otherwise).
4. Load NT predictions and check the consensus rule.
5. Scan neuPrint segments for neuron properties and per-ROI counts.
6. Scan 151.9M connections:
   - global value checks, referential anti-join and duplicate check;
   - per-neuron totals over all partners;
   - extract neuron→neuron edges and explode per-edge roiInfo.
7. Cross-check against the flat export.
8. Run synapse-level checks: a full 312M-row pass plus recomputation for 300 seeded random neurons.
9. Assemble the neuron table.
10. Check directionality (exact conservation plus biological polarity).
11. Compute graph statistics and coverage.
12. Write outputs deterministically.
13. Write the validation report, `build_info.json` and the manifest.

### 6.3 Definitions
- **Neuron:** has a superclass (the source's own definition).
- **`synapse_count`:** T-bar→PSD pairs at confidence ≥ 0.5 on both sides. This equals neuPrint `weight`.
- **HP subset:** PSD confidence ≥ 0.7, with the float32 value compared in float64. This equals neuPrint `weightHP`
  exactly.
- **Edge neuropil:** location of the PSD.
- **Autapses:** kept and flagged (101 among neurons).

### 6.4 Determinism
- The synthetic test rebuilds and compares SHA-256.
- The real-data double build compared all 6 Parquet outputs and the validation checks.
  - **All six files are byte-identical** across two independent full builds on 2026-09-22 (e.g. `connections.parquet`
    sha256 `fd2a1054…`, `neurons.parquet` `adc6b994…`; full hashes in the manifest).
  - The validation check lists are identical.
  - The final release build (§7) was compared against the same hashes.

## 7. Validation results

The final build's report is at `data/manifests/male-cns_v1.0.validation.{json,md}`.

**Summary:** 53 pass, 0 fail, 1 warn, 19 info. Highlights:

- **Provenance and versions.** All inputs match their pins, and the neuPrint meta dataset/tag equals male-cns/v1.0.
  All acquired URLs are under `.../v1.0/`.
- **IDs.** No duplicates in annotations, NT, segments, raw connection pairs or neuron edges. `:ID == bodyId` for
  88.4M segments.
- **Referential integrity.** Every endpoint of all 151.9M raw edges exists in the segment table (anti-join = 0).
  Every retained edge joins two neurons.
- **Edge values.** No nulls, negatives or zero weights; `weightHP ≤ weight`; `weightHR == weight` everywhere.
- **Conservation.**
  - Σ weight = Σ downstream = Σ upstream = 311,833,243 = totalPostCount = number of `syn-partners` rows.
  - Per neuron, the sum of edge weights over all partners equals neuPrint downstream/upstream exactly, for all
    166,700 neurons.
- **Cross-source.** The flat export and the neuPrint inputs agree exactly on all 151.9M pairs, on all annotation
  fields and on all NT fields.
- **Synapse level.** For 300 random neurons (51,437 edges), every weight, HP weight and per-neuropil count
  recomputed from individual synapses matches. Every synapse has conf_pre and conf_post ≥ 0.5.
- **Directionality and biology.**
  - 98% of descending neurons have relatively more output (T-bars) than input in the VNC. Ascending neurons show the
    reverse.
  - Sensory neurons are output-dominated (median output fraction 0.83–0.87); motor neurons are input-dominated.
- **Warning (documented source discrepancy).** `consensus_nt` differs from the Methods-stated rule for 4,420 typed
  bodies in 91 types. These are expert or literature overrides that are absent from `ground_truth`:
  - Kenyon cells: dopamine→ACh;
  - motor neurons: →Glu;
  - EN00B*: →octopamine;
  - DNg28: →serotonin.

  Untyped bodies follow a body-level rule, and that rule is verified.

## 8. Graph size

| measure | value |
|---|---|
| Neurons | **166,700**. neuPrint's broader `:Neuron` label covers 176,422; there are 88.4M synaptic segments in total |
| Neuron→neuron edges | **25,582,938**, carrying 124,177,617 synapses (39.8% of all 311.8M synaptic connections) |
| Edges with ≥ 5 synapses | 6,242,118 (equals Codex's MCNS v1.0 count) |
| Weight distribution | median 2, mean 4.85, p99 46, max 2,591; 10.3M edges have weight 1 |
| Degree | mean 153; median out 112, median in 98; max out 11,203, max in 11,526 |
| Reciprocity | 29.9% |
| Autapses | 101 edges (474 synapses) |
| Components | largest weakly connected component 166,479; largest strongly connected component 165,314; 217 isolated neurons |

## 9. Annotation coverage (fraction of 166,700 neurons)

| field | coverage | field | coverage |
|---|---|---|---|
| type | 98.7% | consensus NT present | 99.9% |
| consensus NT not "unclear" | 98.1% | literature NT label | 51.3% |
| instance | 96.0% | side | 99.7% |
| soma location | 83.8% | group | 88.5% |
| FlyWire type | 85.9% | hemibrain type | 19.8% |
| MANC type | 13.6% | Ito/Lee hemilineage | 22.6% |
| Truman hemilineage | 11.8% | traced status | 98.7% |

Per-superclass coverage is in the manifest. Notably, only 45% of VNC motor neurons have a non-"unclear" NT: they
have few T-bars inside the CNS.

## 10. Independent data-quality audit

`scripts/audit_data_quality.py` uses plain pyarrow on the raw files, not the pipeline's DuckDB code. Its report is
`research/audit/data_quality_audit_male-cns_v1.0.md`. **23/23 pass.**

- **Neuron records.**
  - The neuron ID set equals the raw superclass bodies exactly.
  - 200 sampled neurons match raw neuPrint values field by field (type, instance, class, status, NT, counts), with
    NT joined to the right bodies.
  - Integer columns are integer-typed.
- **Edge counts.**
  - 300 sampled edges match both the raw neuPrint table and the flat export.
  - Reverse-direction counts agree.
  - 25 sampled edges were recounted from individual synapses.
- **Known-biology direction checks:**

  | pathway | forward (synapses) | reverse (synapses) |
  |---|---:|---:|
  | Kenyon cells → MBONs | 463,640 | 11,181 |
  | ORNs → PNs | 487,468 | 9,049 |
  | DNs → motor neurons | 229,565 | 599 |

- **Labels.** Type prefixes are consistent (DN/IN/AN ≥ 98.5%). 112 `instance` values do not begin with their
  `type`; these are curated-label quirks, kept verbatim.
- **Isolation.** There is no cross-version mixing.

## 11. Discrepancies (documented, not hidden)

1. **Paper vs v1.0.**
   - The paper describes roughly v0.9: 166,691 neurons, and 25.6M edges among 166,391 neurons.
   - v1.0 has 166,700 neurons and 25,582,938 edges; 166,483 neurons have at least one edge.
   - Connection completeness is 40.1% in the paper vs 39.8% in v1.0.
2. **Codex vs BrainIR.** Codex reports 166,700 neurons, which is identical. Its 6,242,118 connections equal BrainIR
   edges with ≥ 5 synapses, which is Codex's display threshold.
3. **Flat export vs neuPrint inputs.** They are identical.
4. **Bulk export vs live neuPrint (unresolved).** They share the segmentation timestamp, but the live server has a
   different UUID (`4b2087c0…`) and a later property update (2026-06-08T01:31 EDT, ~25 min after the bulk upload).
   Annotations and NT on the live server may differ slightly; connectivity should not.
5. **Consensus-NT rule.** The Methods text and the released data differ (see §7).
6. **ROI hierarchy.** It is a DAG: 9 ROIs have two parents, and 4 ROIs have statistics but are absent from the
   hierarchy. Both are handled explicitly.
7. **HP threshold boundary.** Resolved (see §6.3).

## 12. Dataset limitations and caveats

- **n = 1 male animal.** Cross-individual variability is unknown until the data are compared with MANC, BANC, FANC
  and FlyWire.
- **Synapse counts are anatomical.**
  - Detection precision and recall are ~0.82/0.81.
  - Postsynaptic completeness is low (~42% in neuropils), so only 39.8% of all connections are neuron→neuron.
  - Inputs are therefore lower bounds. For example, only 33% of DNg100's output connections reach identified neurons.
- **No gap junctions, receptors, neuromodulation or physiology.**
- **NT labels.** They are ML predictions or curated literature labels. Glutamate→inhibition is an assumption.
  Octopamine and serotonin predictions are unreliable (consensus sets them to "unclear").
- **Some neurons are unreconstructable.** These include some lamina R1–R6 cells ("Out of scope" status) and some
  sensory and motor neurons.
- **The live neuPrint server may carry newer annotations** than the bulk export (§11.4).
- **Morphology.**
  - Official SWC skeletons exist; spot-checked, raw and mirrored.
  - They were generated at DVID mutation 1006540662, slightly before the connectome snapshot (1006591300), so
    recently edited neurons may have marginally stale skeletons.
  - EM and voxel segmentation were deliberately not downloaded.

## 13. DNg100 benchmark findings (ANSWER-BEARING)

Full details: `benchmarks/dng100_walking_cpg/malecns_v1.0_findings.md`. Mapping:
`malecns_v1.0_mapping.json`. Reproduce with `investigate_malecns.py`.

- **DNg100 (BDN2) neurons.** v1.0 has 2 DNg100 neurons.
  - `10045` (DNg100_L) matches MANC 10339. `10056` (DNg100_R) matches MANC 10093.
  - Both are consensus ACh (type confidence 0.95), with synonym "Sapkal 2024: BDN2".
- **Projections.** Each projects contralaterally.
  - `10056` puts 25% / 20% / 16% of its T-bars in the left T1 / T2 / T3 leg neuropils. It is the paper's stimulated
    "left DNg100" (same ID as in the paper).
  - Inputs are mainly in the GNG (53%), SAD and VES.
- **Partners of `10056`.** 1,772 downstream neurons (669 with ≥ 5 synapses) and 1,166 upstream neurons. Directly,
  it contacts 87 leg motor neurons (961 synapses).
- **Readout.** Leg motor neurons are `vnc_motor` with subclass fl/ml/hl: 135 / 116 / 130.
- **Published circuit types** (Pugliese et al.), each present in exactly **6 copies, one per leg neuropil**:
  - E1 = IN17A001, E2 = INXXX466 (ACh);
  - I1 = IN16B036 (Glu), I2 = IN19A007 (GABA);
  - E3 = IN19B012, E4 = IN03A006, E5 = INXXX464.
- **Paper IDs in v1.0.** The paper's MaleCNS body IDs come from an extraction dated 2026-02-10, before v1.0. All of
  them exist in v1.0 with unchanged types:
  - T1L: E1 800173, E2 800863, I1 801884, I2 800374.
  - The T1R copies also match.
- **Connectivity.** **All 13 published MaleCNS edge counts are reproduced exactly in v1.0**: DNg100→E1 155,
  E1→E2 465, I1→E1 526, E2→I2 215, I2→E1 328, and the rest.
  - In this circuit every synapse is inside VNC ROIs.
  - DNg100 drives E1 in all three left legs (155 / 167 / 140).
- **Recurrence around the pathway.** 334 reciprocal pairs among DNg100's 435 strong VNC targets. See `SPEC.md` §6
  for the greedy-baseline analysis.
- **How the paper maps names to connectomes.**
  - MaleCNS and BANC: the datasets' own type labels (MANC-style VNC names).
  - MANC: native types.
  - FANC: hemilineage labels plus author matching (method not stated).
  - The minimal circuit differs by dataset. MaleCNS's modal circuit is E1-E2-**I2** (655/1024); E1-E2-I1 appears in
    181/1024.
- **Status of the answer.** The circuit is a model-derived hypothesis, robust across 4 connectomes, **with no
  wet-lab test of the interneurons**.

## 14. Benchmark readiness

**Ready.** `benchmarks/dng100_walking_cpg/SPEC.md` defines:
- the question;
- the information budget: a *blind* tier A with VNC interneuron types hashed, and a labelled tier B;
- held-out interventions;
- success levels S0–S5: functional → compact → role overlap → pre-registered interventions → cross-connectome →
  biological;
- the anti-leakage protocol (freeze and hash the artefact before evaluation);
- required baselines.

The stimulus, readout and answer are verified in v1.0. The answer key is isolated, and `tests/test_leakage_guard.py`
guards `src/` and the clean docs.

**Still missing** for running the benchmark:
- a re-implementation of the paper's rhythmicity score in evaluation code;
- a second connectome (MANC v1.2.x is the easiest) for S4.

## 15. Unresolved issues

1. **Live-neuPrint parity** (§11.4). The minimal action is a one-time login at https://neuprint.janelia.org in
   Chrome. Read-only comparison queries can then run through the browser session, with no token handling.
   **Optional.** The bulk export is the official, complete, versioned source of record.
2. **The Cell (2026) version of the MaleCNS paper has not been read.** The preprint was used.
3. **Pugliese et al.**
   - Dataset versions are not stated.
   - An unreleased revision exists (repo commit 2026-09-15).
   - The FANC matching method is not stated.
4. **Per-T-bar NT probabilities are acquired but not yet used.** They could support per-edge NT evidence and sign
   uncertainty.
5. **Schema extensions for CAVE datasets are designed but not implemented.** These are anchors, ID lineage,
   cross-dataset matches and NT distributions.

## 16. Next recommended phase

**Phase 1: dynamics-ready substrate + a second connectome.** In priority order:

1. **Ingest MANC v1.2.x** through the same schema. This tests multi-dataset generality: ID namespacing, 3-class NT,
   a different ROI set.
   - Build `cross_dataset_matches` from MaleCNS `manc_body_id` / `manc_type`.
   - Verify the benchmark neurons there.
2. **Evaluation harness for B1.**
   - Implement the rhythmicity score and the frozen-artefact protocol.
   - Implement baselines (greedy/top-k, random subnetworks) and a reference rate-model simulator. This is evaluation
     tooling, kept outside `src/` discovery code.
3. **A modelling-parameter layer** (`ModelParameter` tables) that keeps sign/scale assumptions explicit, with
   sensitivity analysis over the sign rule (e.g. Glu±) and synapse thresholds.
4. **Only then** start blind (tier A) discovery experiments for compact program extraction.

## Appendix — where things are

| path | content |
|---|---|
| `src/brainir/` | library (registry, acquire, schema, ingest, graph, synapses, manifest, CLI) |
| `tests/` | 86 tests (synthetic fixture with hand-derived truth; invalid-input mutations; determinism; CLI; docs; leakage; real-data) |
| `data/manifests/` | committed manifest + validation report |
| `research/LOG.md` | decisions, discrepancies, pitfalls, performance, open questions |
| `research/literature/` | Pugliese et al. (concise + exhaustive notes), MaleCNS paper notes |
| `research/data_ecosystem.md`, `research/connectome_ecosystem_survey.md` | FlyWire/BANC/MANC/FANC/hemibrain survey |
| `research/audit/` | independent data-quality audit |
| `benchmarks/dng100_walking_cpg/` | answer key, SPEC, MaleCNS v1.0 verification |
| `docs/schema.md` | generated schema reference |
