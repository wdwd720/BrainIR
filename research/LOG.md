# BrainIR research & engineering log

Purpose: stop future sessions from repeating work or re-making settled decisions. Newest entries at the bottom of
each section. Dates are absolute. "Phase 0" = the data/research foundation (spec: `goal1.md`).

---

## 1. Decision register

| id | date | decision | rationale / evidence |
|---|---|---|---|
| D1 | 2026-09-22 | Repo at `C:\Dev\BrainIR`; bulk data under `data/` (git-ignored), relocatable via `BRAINIR_DATA_DIR`; manifests committed under `data/manifests/` | Keeps code and data together while never committing data |
| D2 | 2026-09-22 | **uv** + uv-managed CPython 3.12.14 (`python-preference = "only-managed"`), `uv.lock` committed | The system CPython 3.12 at `%LOCALAPPDATA%\Programs\Python\Python312` is broken (its `Lib` lacks `os.py`/`encodings`); uv would otherwise try to use it |
| D3 | 2026-09-22 | Primary source = official GCS bulk files (`gs://flyem-male-cns/v1.0/`), not the neuPrint API | Bulk files are complete, official, versioned (GCS generation) and need no credentials. neuPrint tokens were invalidated in Aug 2026 and no session was available |
| D4 | 2026-09-22 | Acquire `Neuprint_Neurons.feather` + `Neuprint_Neuron_Connections.feather` (the exact neuPrint inputs) as the canonical node/edge sources; flat `connectome-weights` only for cross-checking; `syn-partners` + `tbar-neurotransmitters` for synapse level. Skip `syn-points` (13 GB, redundant) and `body-stats` (redundant with the neuPrint neuron table) | Gives neuPrint parity (weight, weightHP, per-edge roiInfo, :Neuron labels) plus independent cross-checks |
| D5 | 2026-09-22 | Pin every remote file by size + CRC32C (+ MD5 when present) + **GCS generation**; acquisition refuses a changed object | Guards against silent re-uploads under the same "v1.0" name (the NT files were re-uploaded on the release day) |
| D6 | 2026-09-22 | **Neuron = body with a superclass** (166,700). Edges kept only neuron→neuron (25,582,938). Totals over *all* partners are kept per neuron | This is the source paper's definition. It matches Codex (166,700). neuPrint's `:Neuron` label is broader (176,422) and is kept as the flag `neuprint_neuron_label` |
| D7 | 2026-09-22 | Autapses kept and flagged (`is_autapse`): 101 edges / 474 synapses among neurons (123 rows / 542 synapses in the raw table) | The task requires intentional handling; they may be real or artefacts, and analyses decide |
| D8 | 2026-09-22 | Per-edge neuropil = neuPrint convention (**postsynaptic** location), restricted to the 144 primary ROIs plus an explicit `<unassigned>` remainder, so counts always sum to `synapse_count` | Primary ROIs cover 99.95% of PSDs; the remainder is small but not dropped |
| D9 | 2026-09-22 | `weightHR` not stored | Validated equal to `weight` for all 151,856,684 rows: the flat/neuPrint inputs are pre-filtered at conf ≥ 0.5 on both sides, and a flyem-snapshot comment calls weightHR "a failed experiment" |
| D10 | 2026-09-22 | Sign is **not stored**; it is computed on demand under the versioned rule `brainir.sign.conventional-v1` (ACh +1; GABA −1; Glu −1 context-dependent; histamine −1 context-dependent; DA/5-HT/OA none) | Keeps anatomy, ML predictions and hypotheses separate |
| D11 | 2026-09-22 | Two hemilineage columns (`hemilineage_ito_lee`, `hemilineage_truman`) instead of one merged column | 3,902 neurons carry both parallel nomenclatures |
| D12 | 2026-09-22 | ROI table keyed by name, with `parent` (authoritative, from roiInfo) + `all_parents` | The neuPrint ROI hierarchy is a DAG (e.g. CA(L) sits under both CentralBrain and MB(L)) |
| D13 | 2026-09-22 | Parquet zstd-3, 1M-row groups, rows sorted by primary key, dictionaries normalised → byte-identical rebuilds; all text artefacts written with LF newlines | The determinism test compares SHA-256 across rebuilds |
| D14 | 2026-09-22 | DuckDB for heavy joins/JSON over the Arrow IPC files (memory limit, per-process spill dir) | 152M-edge and 312M-synapse tables do not fit comfortably in pandas with ~12 GB free RAM |
| D15 | 2026-09-22 | Benchmark answer key isolated in `benchmarks/dng100_walking_cpg/`; a leakage-guard test forbids answer-key tokens in `src/` | Required by the goal: never bake the published solution into discovery code |
| D16 | 2026-09-22 | HP semantics = float32 confidence compared **in float64** against 0.7 | Found by the synapse-level check: a PSD stored as float32(0.7) = 0.69999999 is *not* counted in neuPrint's `weightHP`. DuckDB's default FLOAT comparison would count it. Now encoded in the pipeline and the fixture |
| D17 | 2026-09-22 | NT confidences stored as float64 (not float32) | No storage reason to downcast 166,700 rows; avoids silent precision loss |
| D18 | 2026-09-22 | Individual synapses are extracted on demand (`brainir synapses`, `brainir.synapses`) rather than materialised (312M rows) | The raw Arrow file is the store; pyarrow predicate scans take ~20–60 s |
| D19 | 2026-09-22 | Leakage guard extended to "clean docs" (README, CLAUDE.md, docs/, research ecosystem notes, LOG) | The guard caught an answer-key body ID in a CLI docstring example written by me. Scrubbed, and the answer-bearing files are now listed in the benchmark README |
| D20 | 2026-09-22 | Graph layer loads nullable integer columns as pandas `Int*` dtypes | pyarrow's default `to_pandas()` turned integer columns containing nulls (IDs, counts, soma coordinates) into float64. No value was corrupted (all < 2^53), but APIs returned float IDs. Regression test added |
| D21 | 2026-09-22 | **MANC comes in two raw lineages and three processed builds.** Raw `manc:v1.0` = the complete neuPrint bulk export (`gs://flyem-manc-exports/v1.0/`); raw `manc:v1.2` = the v1.2 segmentation's synapse-partner table + neuroglancer annotation snapshots (`gs://manc-seg-v1p2/`). Processed builds: `manc:v1.0`, `manc:v1.2.1` (v1.2 synapses + the 2024-09-27 annotation snapshot) and `manc:v1.2.3` (+ the 2025-10-26 snapshot). Build version ≠ raw version (`registry.BUILD_VERSIONS`). | No neuPrint bulk export exists for v1.2.x; the paper's MANC front-leg network is neuPrint `manc:v1.2.1` (types agree with the v1.2.1 snapshot for 4600/4604 bodies, 4593 with v1.2.3; its full-VNC table is v1.2.3). Rebuilding from the public partner table reproduced the authors' matrices exactly (see §3.11) |
| D22 | 2026-09-22 | Dataset **adapter architecture**: `ingest/common.py` (generic steps, validation, deterministic writing), `ingest/malecns.py`, `ingest/manc.py`; `ingest.build_dataset()` dispatches | MaleCNS outputs unchanged in content (graph statistics, coverage and every check identical after the refactor; bytes differ only through the schema-version metadata) |
| D23 | 2026-09-22 | **MANC v1.0 neuron = neuPrint :Neuron body with status `Traced`** in the neuPrint neuron table (23,514). **MANC v1.2.x neuron = body listed in the annotation snapshot** (24,143 / 23,665); status/is_traced/neuprint_neuron_label are null there | The per-body property export (2023-06-05) labels 314 of the Traced bodies `RT Orphan`; the 2023-06-12 database maps them to Traced. The traced-adjacency export (2023-06-02) has 23,188. All three are recorded as cross-source checks |
| D24 | 2026-09-22 | **Count rule for MANC = conf_post ≥ 0.4 (weight), conf_post ≥ 0.7 (weightHP), every pair (weightHR)**, inferred on v1.0 from the raw minconf-0.0 partner table against the neuPrint weights (exact for all sampled pairs) and applied unchanged to the v1.2 partner table | Confirmed independently by flyem-snapshot's docstring ("for MANC we used 0.4") and by the v1.2.3 snapshot's per-neuron `syn_pre/syn_post/syn_downstream`, which the rule reproduces for 23,665/23,665 neurons. neuPrint keeps rows with weight 0 (HR-only pairs: 5,666,874 in v1.0); they are dropped and counted |
| D25 | 2026-09-22 | v1.2.x builds **carry body-level NT predictions (and nothing else) from the v1.0 property export by body ID**; type-level NT from the v1.2.3 `celltypePredictedNt` tag; sizes are NOT carried (null) | Every v1.2.x neuron exists in v1.0 by ID; the paper's own v1.2.1 table has `predictedNtProb` identical to v1.0 for all 4604/23,532 bodies. Its `predictedNt` *labels* differ for 72/4604 (398/23,532) bodies (§3.12) |
| D26 | 2026-09-22 | ROI catalogue for MANC taken from roiInfo/primaryRois (61 ROIs); the Meta `roiHierarchy` is not authoritative; `top_level_region` = VNC for every ROI; T-bar ROIs in v1.2.x approximated by the ROI of their PSDs | The v1.0 Meta hierarchy lists `IntNp(T*)`/`AMNp` instead of `LegNp(T*)`/`Ov` and misspells the root as "ventral nerve core"; the v1.2 partner table carries `roi_post` only. 0.54% of sampled T-bars have PSDs in >1 primary ROI |
| D27 | 2026-09-22 | Schema 0.2.0: `is_traced` and `neuprint_neuron_label` nullable; NT vocabulary gains `unknown` (the classifier's own class, distinct from `unclear`); sides gain `B` (MANC `BIL`); cross-dataset `role_class` (rule `brainir.role.v1`) derived on load, not stored; `sign_hypothesis(basis="auto")` = consensus → type-level → body-level | MANC publishes no status for v1.2.x, no consensus NT, and uses a different class vocabulary |
| D28 | 2026-09-22 | Directionality sanity checks are expressed in role classes; in VNC-only volumes only descending neurons carry an expectation (output-dominated) | MANC ascending neurons are output-dominated *inside the VNC* (median output fraction 0.60), so the MaleCNS-style AN expectation is wrong there |
| D29 | 2026-09-23 | Simulator = independent NumPy/SciPy re-implementation of the published rate model (`brainir.sim`), float64, RK45 at the authors' tolerances, integrated segment-wise at pulse edges; model parameters never enter anatomy tables | The authors' JAX/Diffrax float32 GPU runs cannot be reproduced bit-exactly (their own code comments say so); distributional reproduction is the target |
| D30 | 2026-09-23 | Rhythm metric suite = the published score reproduced exactly + amplitude gate + envelope-persistence gate + inter-peak regularity (`RhythmResult.is_sustained_rhythm`) | The published score is min-max normalised (amplitude-blind: a 2e-4 Hz ripple scores 1.0) and cannot separate a damped transient from a sustained oscillation over the window (damped test signal scores 0.83) |
| D31 | 2026-09-23 | Benchmark package `benchmarks/dng100/` = `public/` (tier B, labelled), `public_blind/` (tier A), `oracle/`, `evaluator/`, `cleanroom/`, `baselines/`, `nodes/`, `manifests/`. Network membership = the published front-leg node lists (bodies only); everything else (counts, signs, sizes, stimulus, readout) is derived from BrainIR builds | The paper's node-selection rule is not stated; the node lists carry no information about which neurons matter. Stimulus chosen by a data rule (the DNg100 body with the most output into LegNp(T1)(L)) — it selects the paper's neuron in both datasets |
| D32 | 2026-09-23 | **Tier A blinds two things**: interneuron types/instances → salted tokens, AND neuron identifiers → positional indices (body IDs live only in `oracle/tier_a_ids/`) | Body IDs of the published circuit appear in the paper's supplementary tables, so a literature-aware method could look them up; positional ids remove that channel. The evaluator translates positional predictions back |
| D33 | 2026-09-23 | Evaluator reports metric families separately (structural, type/role, functional-by-simulation, mechanism, cross-connectome, robustness); the functional family is oracle-free (sufficiency of the predicted core by keep-only simulation; necessity by silencing) | No single number can rank mechanism claims; the oracle is model-derived, so an oracle-free simulated check is the strongest evidence available |
| D34 | 2026-09-23 | Compute: `brainir.compute` local pool / Modal backends with a content-addressed experiment registry; Modal image is built from the repository source so remote results are attributable to the same commit | Modal smoke test passed (3 remote simulations, ~40 s incl. image build, ≈ $0.007) |
| D35 | 2026-09-23 | Cross-connectome mapping (`brainir.mapping`, schema 1.0.0): one row per (MaleCNS neuron, MANC candidate) with `mapping_kind` ∈ {curated_body_match, curated_type_match, same_type_name, same_role_only, unmatched}, method, evidence kind, confidence, ambiguity and per-field consistency flags; **no row asserts identity** (different animals). Scope = MaleCNS VNC roles (+ neurons carrying a curated MANC annotation); 142,564 brain-only neurons are a summary count | 18,555 curated body matches exist in `manc:v1.2.1` (side agreement 97%, role 96%, NT 91.5%); `manc_type` equals the body's v1.2.x type for only 77.6% → the MaleCNS release matched against a MANC snapshot that is neither v1.2.1 nor v1.2.3 (which one is not stated). Report: `research/cross_connectome_mapping.md` |
| D36 | 2026-09-23 | Pruning search (`brainir.sim.prune`) and activation screen (`brainir.sim.screen`) re-implemented from the code spec as generic procedures (no answer knowledge). Deviations recorded in their docstrings: stimulus protected by default; NumPy RNG; both the structural and the activity-based circuit are reported; round convergence compares the put-back set *before* the last restore | Tested on synthetic circuits (the embedded 4-neuron oscillator is recovered, distractors pruned, deterministic per seed) |
| D37 | 2026-09-23 | Compute backends take a **shared payload** (`backend.map(fn, items, shared={...})` with `Shared("key")` markers inside the items): the local pool ships it once per worker (initializer), Modal uploads it once to a content-addressed Volume blob (`brainir-shared-payloads`, zlib-pickled) and each container resolves markers from an in-closure cache. Modal maps return exceptions per item (`split_failures`) instead of aborting the campaign | The 4604×4604 float32 weight matrix is 85 MB; the DN screen has 14,928 jobs (1.3 TB of arguments the naive way). Smoke: identical results local vs Modal (3 candidates × 2 replicates, $0.008) |
| D38 | 2026-09-23 | Benchmark freeze = `benchmarks/dng100/BENCHMARK_LOCK.json` (SHA-256 of every file under public/, public_blind/, oracle/, evaluator/, cleanroom/, baselines/, nodes/ + PROTOCOL.md, LEAKAGE_AUDIT.md, build script; dataset manifest hashes; code commit) written by `freeze.py`, verified by `freeze.py --check`, marked by git tag `dng100-benchmark-v1`; `PROTOCOL.md` fixes the information budget (tier A/B), the run procedure and what may be claimed | Results are comparable only within one lock; the protocol makes the tier-A (blind) setting the only one that can support an "independent recovery" claim |
| D40 | 2026-09-23 | **Review-driven changes before the freeze** (reviews A–E, `research/audit/phase1_reviews/`): (a) tier-A positions are a salted random permutation (the node lists follow the paper's tables, so raw positions identified bodies; review C B1); (b) the clean room runs methods under a CPython audit-hook sandbox (`cleanroom/_sandbox.py`: file access confined to the bundle copy/out/Python/temp, no subprocess/socket/ctypes; review C B3) and records method args + sandbox hash; the evaluator verifies run-record hashes (`--run-record`); (c) evaluator 1.1.0: real cell types for tier A from the private id map (type-level family was always 0 in tier A; reviews C/D), `sustained` = score ≥ 0.5 AND median readout peak-to-trough ≥ 0.25 Hz as the pass rule (published score is amplitude-blind; a first 1 Hz gate rejected the intact MANC network in 2/8 replicates and the published MaleCNS core in 5/8 — intact ranges are 1.4/4.0 Hz, isolated cores 0.8–1.2 Hz — so it was calibrated to 0.25 Hz), precision vs DNg100-circuit labels (E4/E5 are DNb08-pathway neurons), cross-connectome graded per dataset lineage (the two MANC networks share one synapse table), claims graded vs the oracle only where both endpoints are labelled and separately vs frozen curated pairs (`oracle/cross_connectome_reference.json`), oracle-free transfer sub-family (source core → curated pairs → keep-only in the other dataset), t_end default 2.0 s (published); (d) mapping schema 1.1.0 (`manc_type_consistent`, `a_type_consistent`, `b_ambiguity`; confidence documented as A→B uniqueness), role `vnc_unknown` for MaleCNS `vnc_tbc`, MANC `Sensory TBD` → `vnc_sensory`; (e) `build_dataset` refuses (source, build_version) pairs the registry does not define (review A A2); v1.2.x manifests no longer present the v1.0 Meta as their neuPrint snapshot (A4); (f) leakage-guard tokens read from the oracle at test time (C M6); PROTOCOL states what tier A does not hide (structure fingerprints) and how baselines set the bar family by family | Each item traces to a numbered finding in the review files; blockers C-B1/B3/B4 and D-B1/B2 are closed by (a)–(c) plus the freeze |
| D42 | 2026-09-23 | **Review F closure**: the lock hashes `baselines/results/**` (the protocol's normative baseline evaluations and null distributions), the library code the evaluator executes (`src/brainir/{sim,metrics,benchmark,compute}`, `graph.py`, `mapping.py`, `vocab.py`) and `uv.lock`/`pyproject.toml`; `freeze.py --check` verifies files, code and dataset manifests (`tests/test_freeze.py` runs it once a lock exists). Bundles are re-exported at the final code state before freezing so their manifests attribute them to the exporter that produced them. Local reproduction/robustness runs received retroactive registry records (marked as such; drivers register from now on). The evaluator's amplitude gate was calibrated (0.25 Hz). Leakage guard scans .json/.csv/.txt as well as .md in clean-doc directories; sandbox tests (`tests/test_cleanroom_sandbox.py`) exercise an escape, a subprocess attempt and a legitimate method | Findings F-B1/B2, F-M1–M6, F-m3/m4/m8/m9 in `research/audit/phase1_reviews/review_F_reproducibility_report.md` |
| D41 | 2026-09-23 | The MaleCNS "recruitment discrepancy" (§8.8, first version) was a stimulus-selection error in `reproduce_dynamics.py` (first DNg100 in the authors' table order, which in MaleCNS is not the benchmark's neuron); found by review D. The driver now uses the benchmark's stimulus rule (`brainir.benchmark.bundle.choose_stimulus`) | At the correct neuron BrainIR recruits a median of 8 active MNs, as the paper reports (interventions run and the corrected n = 128 run) |
| D39 | 2026-09-23 | Cross-connectome evaluation (`benchmarks/dng100_walking_cpg/cross_connectome_eval.py`) uses the public mapping table in both directions plus a functional transfer test (map one network's modal circuit into the other and simulate it keep-only there) | Every published core neuron maps 1:1 with `curated_body_match`/high in both directions — because the MaleCNS release carries curated `manc_body_id`/`manc_type` annotations. The correspondence is therefore *curated* evidence restated, not derived by BrainIR; the functional transfer is the derived part |

## 2. Performance measurements (this machine: Ryzen 9 6900HX 8C/16T, 30 GB RAM, NVMe, ~7 MB/s internet)
- **Downloads.** Single-stream GCS runs at ~4.6 MB/s. Parallel ranged downloads barely help (5–8 MB/s), so the link
  is the bottleneck. The full acquisition (18.72 GB) took ~45 min.
- **Ingestion** (8 threads, DuckDB 6 GB), total ~6.5 min without synapse checks:

  | step | time |
  |---|---|
  | neuPrint neuron scan (88.4M segments) | 14–17 s |
  | global stats over 151.9M edges | ~4 s |
  | referential anti-join over 151.9M edges | 27 s |
  | full duplicate-pair GROUP BY | 23 s |
  | edge extraction + roiInfo explosion | ~4 min |
  | flat cross-check | 56 s |
  | write outputs | 42 s |

- **Graph API.** `Connectome.open()` loads the 166,700 × 25.58M graph as CSR in ~6.5 s.
- **Processed footprint:** ~206 MB (connections 106 MB, connection_neuropils 94 MB).

## 3. Version / source discrepancies (documented, not hidden)

1. **Paper (preprint, ~v0.9) vs v1.0.**
   - Neurons: 166,691 in the paper vs 166,700 superclass bodies in v1.0.
   - Graph: the paper reports "25.6M edges between 166,391 neurons"; v1.0 has 25,582,938 edges and 166,483
     non-isolated neurons (217 isolated).
   - Connection completeness: 40.1% in the paper vs 39.8% neuron→neuron in v1.0.
   - The v1.0 release notes say "minor proofreading changes; refinement of neuron annotations".
2. **Codex vs BrainIR.** Codex MCNS v1.0 reports 6,242,118 connections. This equals **exactly** the number of v1.0
   neuron edges with ≥ 5 synapses, so Codex applies a ≥ 5 threshold.
3. **Flat export (2026-06-03) vs neuPrint inputs (2026-06-08).**
   - Edge sets and weights are identical for all 151,856,684 pairs.
   - Annotations and NT fields are identical for all 166,700 neurons.
4. **Bulk neuPrint inputs vs *live* neuPrint `male-cns:v1.0` (UNRESOLVED).**
   - Both carry the same segmentation timestamp (2026-03-28 11:56:30).
   - The bulk Meta has UUID `98d6995e…` and a property update dated 2026-04-30. The live server
     (`/api/dbmeta/datasets`, 2026-09-22) reports UUID `4b2087c0…` and a property update dated
     **2026-06-08T01:31:39-04:00**, ~25 min after the bulk export was uploaded.
   - Connectivity should therefore be identical, but live annotations/NT may differ slightly from our tables.
   - Resolving this needs a logged-in neuPrint query. No session was available and old tokens are dead.
5. **The consensus-NT rule in the Methods vs the released data.**
   - Untyped bodies use the *body-level* prediction.
   - 4,420 typed bodies in 91 types carry expert overrides that are **not** in `ground_truth`: Kenyon cells DA→ACh
     (4,053), motor neurons →Glu, EN00B* →octopamine, DNg28 →serotonin.
   - Both behaviours are recorded as WARN checks with details.
6. **Paper MaleCNS extraction (2026-02-10) vs v1.0 for the benchmark circuit.**
   - All 16 published IDs (DNg100, E1–E5, I1, I2, T1L and T1R) exist in v1.0 with the same types.
   - All 13 published edge counts are identical.
7. **Synapse-level vs neuPrint `weightHP` (resolved).** In a 300-neuron sample (51,437 edges), synapse recounts
   matched every `weight`. One `weightHP` differed until the float32/float64 boundary semantics were matched (D16).
   Now all match.
8. **Curated-label quirks.** 112 typed neurons have an `instance` that does not start with their `type`
   (e.g. `CB4248` / `CB4175_R`; `PEN_a(PEN1)` / `PEN_a(PB06a)_L3`). The source's curated labels are kept verbatim.
9. **Skeletons vs connectome snapshot.**
   - Official SWC skeletons exist; checked for 10056, 10045 and 10001, both raw and mirrored, uploaded 2026-05-05.
   - Their headers name DVID node `86f3689d…` at mutation 1006540662. The connectome snapshot is at mutation
     1006591300.
   - Skeletons of recently edited neurons may therefore lag the connectivity slightly. `MorphologyRef.verified_exists`
     is False until checked per neuron.
10. **ROI metadata.**
   - The hierarchy is a DAG: 9 ROIs have two parents (CA, IB, ICL, PED, SCL).
   - 4 ROIs have statistics but are absent from the hierarchy (`AL-unspecified(L/R)`, `gL-unspecified(L/R)`).
11. **Pugliese et al. MANC matrices vs BrainIR rebuilds** (`benchmarks/dng100_walking_cpg/manc_reproduction.md`).
    Front-leg network (4604 neurons, 2025-08-13) vs `manc:v1.2.1`: all 196,535 pairs present with identical counts
    (3,817,772 synapses); the single extra pair in ours is an autapse (the authors zeroed the diagonal). Full-VNC
    network (23,532 neurons, 2025-10-06) vs `manc:v1.2.3`: all 1,372,404 pairs identical; 8 extra autapses in ours.
    Recounting the front-leg network from the raw v1.2 partner table matches only at `conf_post ≥ 0.4` (0.5 misses
    18,537 pairs). Against `manc:v1.0`: 22 of the 4604 bodies do not exist and 515 pairs are missing.
11b. **Pugliese et al. MaleCNS matrix (4310 neurons, VNC ROIs only, 2026-02-10) vs `male-cns:v1.0`.** Counting only
    synapses whose PSD lies in a VNC primary ROI, flooring at 5, removing autapses and zeroing the output rows of
    neurons whose consensusNt is not ACh/GABA/Glu (77 `unclear`, 4 histamine, 2 serotonin) reproduces every pair
    and count among the bodies that were NOT proofread between the authors' extraction and the release
    (116,424/116,424 exact). 30 bodies changed (size differs, e.g. IN21A004_L 800802 lost 60% of its volume; one body
    no longer exists): the paper's MaleCNS network comes from a pre-release neuPrint state of 2026-02-10, not v1.0.
12. **MANC NT labels changed between v1.0 and neuPrint v1.2.x.** `predictedNtProb` is identical, but `predictedNt`
    differs for 72/4604 front-leg neurons (mostly `unknown`/`gaba`/`acetylcholine` → `glutamate`, 31 of them motor
    neurons) and 398/23,532 full-VNC neurons; the changed labels are not the argmax of the published probabilities,
    so the rule that produced them is unknown. Using the v1.0 labels reproduces the paper's row signs for 99.44% of
    presynaptic rows; the paper's own labels are available for a "faithful" network variant (nt_override).
13. **Two official MANC v1.0 exports disagree on status**: 314 bodies are `RT Orphan` in the property export and
    `Traced` in the neuPrint database; the traced-adjacency export lists 23,188 traced neurons, the database 23,514.
14. **MANC v1.0 Meta roiHierarchy is stale** (`IntNp(T*)`, `AMNp` vs `LegNp(T*)`, `Ov` everywhere else; root misspelt
    "ventral nerve core"). Documented in `research/manc_release_notes.md` §7.
15. **v1.2.1 vs v1.2.3 annotation snapshots**: 24,143 vs 23,665 bodies; 22 bodies typed only in v1.2.3; 29 retyped
    (incl. `MNfl10` → `INXXX471`, `IN19A006` → `IN19A018`); v1.2.1 counts are unfiltered synapse counts, v1.2.3
    counts are the threshold-filtered neuPrint counts. Motor-neuron class: the paper's Aug-2025 table distinguishes 4
    `neck motor neuron`s that both snapshots label `motor_neuron`.
16. **Residual synapse-level mismatches in MANC v1.0** (300 sampled neurons): 2 neurons have one more counted PSD in
    the raw partner table than neuPrint `upstream`; 1 of ~70k sampled edges has a PSD in `GF(R)` per neuPrint but
    `<unspecified>` in the partner table. Recorded as WARN, not resolved.

### 3.17 Pruning-screen reproduction (2026-09-23)
1,024 stochastic sufficiency screens of the DNg100-driven front-leg network (`manc:v1.2.1`, authors' NT labels, T = 1 s,
BrainIR's generic `brainir.sim.prune`) on Modal (200 containers, 17.6 min, ≈ $15.5; 0 failed, 1,018 converged; median
101 simulations per screen). Circuit prevalence (activity-based kept set, stimulus excluded): the published modal
three-neuron circuit 68.1 % (paper 62.1 %), the published four-neuron alternative 16.5 % (paper 15.2 % incl. a variant
with one motor neuron), the published alternative with the other inhibitory partner 8.1 % (paper 10.0 %); both
excitatory core neurons kept in 99.5 % of screens. The isolated three-neuron circuit runs faster (median 16.7 Hz) than
the intact network (10.75 Hz). Files: `benchmarks/dng100_walking_cpg/results/pruning_manc_v1.2.1_nt-paper_n1024_seed0.*`,
registry run `5abf1fd8732d5ebb`. Integrator sensitivity (review B-2): the first 64 seeds re-screened with DOP853 at
rtol 2e-7 / atol 5e-10 give the identical circuit in 59/64 screens and the same prevalence (76.6 % vs 78.1 % on those
seeds); registry run `e6c3f46ed826f4c7`, $3.0.

### 3.18 Two defects found and fixed before the freeze (2026-09-23)
- `reproduce_dynamics.paper_network` selected the readout by MANC's `super_class == 'motor_neuron'`; MaleCNS spells it
  `vnc_motor`, so the MaleCNS front-leg network had an EMPTY readout and scored 0 everywhere. Fixed by selecting on the
  cross-dataset `role_class == 'vnc_motor'` (144 MNs in MANC, 135 in MaleCNS) and raising when the readout is empty.
  The bundle exporter had handled both spellings all along.
- The public bundles' `edges.parquet` was derived from the signed matrix, so the 177 (MANC) / 1,232 (MaleCNS) observed
  pairs whose presynaptic neuron has sign 0 (unknown NT) were missing — anatomy filtered by a hypothesis. `Network`
  now carries the observed count matrix `C` next to the signed `W`; the bundles list every observed pair with
  `synapse_count` and `signed_weight` (0 for unknown-NT presynaptic neurons); the evaluator drops zero weights when it
  builds W. Bundle hashes changed (tier B `2653245c…`, tier A `4880e986…`); the leakage audit was re-run (PASS).

## 4. Biological caveats (carry into every analysis)
- **`synapse_count` is not strength.**
  - It counts T-bar→PSD pairs. Fly synapses are polyadic: one T-bar gives several pairs.
  - Detection has ~0.8 precision/recall.
  - Nothing is known about receptors, dendritic location or plasticity.
- **Completeness.**
  - Postsynaptic completeness is low (~42% in neuropils). Only 33% of DNg100's output connections reach identified
    neurons.
  - Any neuron's in-degree is a lower bound.
- **NT predictions.**
  - They come from EM texture (ML), with confidences.
  - `consensus` mixes model output with curated literature.
  - Glutamate→inhibitory is an assumption: GluCl is common, but excitatory GluRs exist.
  - DA/5-HT/OA have no fast sign.
- **No gap junctions** anywhere; electrical coupling is invisible.
- **n = 1 animal.** MaleCNS is one male. Cross-individual variability (e.g. vs MANC, FANC, BANC, FlyWire) must be
  assessed before generalising.
- **Autapses** are rare (101 edges) and may be segmentation or synapse-assignment artefacts.

## 5. Technical caveats / pitfalls hit
- **Broken system Python.** The system Python 3.12 is broken (see D2). Always use `uv run`.
- **Windows file names.** `:` is illegal in names (e.g. remote `male-cns:v1.0.json`), so the registry maps `:` → `_`
  for local names.
- **Console encoding.** Windows consoles default to cp1252, and printing Unicode crashed Python. The CLI reconfigures
  stdout to UTF-8, and scripts set `PYTHONIOENCODING=utf-8`.
- **Line endings.**
  - The user's global git config has `core.autocrlf=true`, so files from a git checkout have CRLF and **different
    hashes** than the canonical bytes. Pin raw GitHub content, not local clones.
  - The repo uses `.gitattributes eol=lf` and writes all text artefacts with `newline="\n"`.
- **Shell escapes.** The Claude Code Bash tool collapses `\\n` inside heredocs. Never patch code containing escape
  sequences via inline Python in bash; use the Edit/Write tools.
- **Locked executable.** `uv run` re-syncs (and fails on a locked `brainir.exe`) while another `brainir` process is
  running; use `uv run --no-sync` for concurrent commands.
- **Float-encoded IDs.** Several annotation ID columns (`group`, `mancBodyid`, …) are float64 in the source. They are
  cast to int64 only after asserting integrality and < 2^53.
- **pandas 3.** The default string dtype is Arrow-backed, and Copy-on-Write is on.
- **DuckDB 1.5** reads Arrow IPC via `pyarrow.dataset`. `json_transform(x, '"MAP(VARCHAR, STRUCT(...))"')` +
  `map_entries` explodes dynamic-key roiInfo JSON; missing keys come back NULL, so COALESCE them.
- **Hook noise.** A PostToolUse hook from the Render plugin errors on every Write/Edit (path with a space). It is
  harmless; files are written.

- **DuckDB extensions.** The Python wheel statically links the `json` and `parquet` extensions, so there is no
  hidden runtime download.
- **Benchmark difficulty.** A greedy-baseline analysis exists in `benchmarks/dng100_walking_cpg/SPEC.md` §6. That
  file is answer-bearing: do not copy its specifics into clean docs.
- **Cache keys must be content-addressed.** The MANC bz2 partner table is decompressed into `data/cache`; a
  synthetic fixture with the same file name silently picked up the *real* 87M-row table until the cache path was
  keyed by the input's SHA-256.
- **Set iteration order is not deterministic across processes** (hash randomisation): exploding tag prefixes into
  columns via `set()` produced different column orders in two builds of the same data (caught by the byte-identity
  check). Always sort.
- **Bash heredocs mangle backslashes** (again): a patch script containing `\'` failed to parse. Write patch scripts
  with the Write tool.
- pandas 3 string columns hold `NaN`, not `None`, for nulls: tests must use `pd.isna`.
- The paper's `set_sizes` takes the median *before* replacing zero sizes; a test written from the description
  (median without zeros) was wrong, the code was right.

- **Fixed-step integrators and the pulse edge (2026-09-23).** `brainir.sim.model._fixed_step` evaluated the pulse
  indicator at every Runge–Kutta stage time, so the k4 stage of the step ending at `pulse_start` (and k1 at
  `pulse_end`) saw the other side of the switch: an O(dt) error of ≈ (dt/6)·activation/τ (0.15 Hz at dt = 1 ms on the
  stimulated neuron) that made RK4 look first-order in the standard protocol. Found by the robustness agent's
  dt-convergence study. Fixed: sub-steps are split at the switch times and the indicator is evaluated once per
  sub-step (regression test against the closed-form single-neuron response). The adaptive path was never affected
  (it integrates segment-wise).

## 6. Failed / abandoned approaches
- Remote column-projected reads over GCS (`IpcReadOptions(included_fields)`) work, but at ~1.5 s per batch they
  would take ~34 min for `Neuprint_Neurons.feather`. Downloading was faster.
- Europe PMC `fullTextXML` for the MaleCNS preprint returned HTTP 500. The bioRxiv full HTML downloaded fine with a
  browser User-Agent.
- WebFetch summaries truncate long papers. Download the full text instead.
- The `ids.neuropils.unique` check initially failed: the tree assumption was wrong because the hierarchy is a DAG.

## 7. Useful documentation (verified 2026-09-22)
- MaleCNS: https://male-cns.janelia.org/ (download page, release notes); bucket listing via
  `https://storage.googleapis.com/storage/v1/b/flyem-male-cns/o?prefix=v1.0/...`.
- flyem-snapshot (how the exports and neuPrint are built; statuses; the `:Neuron` criteria):
  https://github.com/janelia-flyem/flyem-snapshot
- neuPrint: public `/api/serverinfo` and `/api/dbmeta/datasets` (no token needed); Cypher needs a token.
- Papers: MaleCNS (bioRxiv 10.1101/2025.10.09.680999; Cell doi:10.1016/j.cell.2026.08.015). Pugliese et al.
  (10.1101/2025.09.12.675944). Notes are in `research/literature/`.

## 8. Unresolved questions
1. What changed in the live neuPrint `male-cns:v1.0` property update of 2026-06-08T01:31 EDT (see §3.4)? Resolve
   with a logged-in neuPrint session: compare types and consensusNt for all neurons.
2. The Cell (2026) version of the MaleCNS paper was not read. Check whether its reported numbers or definitions
   changed from the preprint.
3. Which synapse-confidence threshold does the **live** neuPrint use for `weight`? The Meta says post ≥ 0.5, and
   the bulk inputs are pre-filtered at 0.5 on both sides. Presumably identical.
4. Pugliese et al.:
   - dataset versions are not stated;
   - FANC→MANC matching method not stated;
   - an unreleased revision exists (repo commit 10e7661 "new revision", 2026-09-15).
5. The per-synapse NT table (`tbar-neurotransmitters`) is acquired but not yet used. Per-edge NT evidence could
   refine sign hypotheses later.
6. **MANC (Phase 1).** Which rule produced the changed `predictedNt` labels in neuPrint v1.2.x (§3.12)? Which
   confidence rule the live `manc:v1.2.x` Meta declares (login needed)? Whether v1.1 / v1.2.2 ever existed (no
   public trace). Origin of the one `GF(R)` / `<unspecified>` ROI disagreement and the two +1 PSD counts (§3.16).
8. **MaleCNS recruitment discrepancy — RESOLVED (2026-09-23, D41).** The first n = 128 run stimulated the first DNg100 in
   the authors' table order (not the benchmark's neuron) and recruited 4 active MNs; with the benchmark's stimulus the
   run gives mean score 0.983 (paper 0.985) and a median of 8 (6–12) active front-leg MNs (paper 8 (6–16)). Nothing
   remains open here; the paper's mCNS experiment configuration is still not in its repository, but the benchmark rule
   (most output into LegNp(T1)(L)) selects a neuron that reproduces its statistics.
9. **Pugliese et al. procedures not determinable from their repository** (see
   `research/literature/pugliese_model_spec_from_code.md` §12): engine (sync vs streaming) and code revision per
   published run; how the 13 `unknown`/`unclear` rows kept zero outputs; the Dirichlet screen (no code); the
   "lower bound of 10 active neurons" for the type-level screen.

## 9. Important assumptions made in Phase 0
- The flat and neuPrint-input files published under `v1.0/` constitute "MaleCNS v1.0". They were verified to be
  internally consistent.
- The source's definition of "neuron" (has superclass) is the right default node set for modelling; fragments are
  excluded but accounted for.
- Leg motor neurons are defined as `super_class=vnc_motor` and `sub_class ∈ {fl, ml, hl}` (MANC convention).

## 10. Chronological log
- **2026-09-22 ~21:00–23:00 (session 1, Phase 0).**
  - Machine discovery; uv setup.
  - Researched MaleCNS bulk layout and flyem-snapshot semantics.
  - Built the registry, acquisition, schema, ingestion, validation, graph API and tests.
  - Acquired 18.72 GB; ran the builds (pass 1 without synapse checks, then the final build).
  - Two research agents surveyed the walking-CPG paper (with code and data) and the connectome ecosystem.
  - Verified the DNg100 benchmark in v1.0: exact reproduction of the paper's MaleCNS circuit counts.
- **2026-09-22 23:00 – 2026-09-23 01:30 (session 2, Phase 1 start).**
  - Re-verified Phase 0 (86 tests; every raw/processed file re-hashed against the manifests).
  - Pinned the MANC version question by comparing the authors' tables with the v1.0 export and the v1.2.1/v1.2.3
    annotation snapshots (D21); registered `manc:v1.0` (14 files) and `manc:v1.2` (18 files); acquired 5 GB.
  - Refactored ingestion into adapters (D22); wrote the MANC v1.0 and v1.2.x adapters, a MANC synthetic fixture
    derived from the MaleCNS fixture, and 13 MANC fixture tests; rebuilt MaleCNS under schema 0.2.0 (content
    identical).
  - Built `manc:v1.0`, `manc:v1.2.1`, `manc:v1.2.3` (0 validation failures; second builds byte-identical).
  - Reproduced the paper's MANC connectivity matrices exactly from the rebuilt datasets (§3.11).
  - Delegated: model-spec extraction from the authors' code (`research/literature/pugliese_model_spec_from_code.md`),
    MANC provenance verification (`research/manc_release_notes.md`), synthetic signals/circuits fixtures.
  - Implemented the simulator (`brainir.sim`) and rhythm metrics (`brainir.metrics`); 47 tests against the
    independent reference integrator and labelled signals. First 4 DNg100 replicates on the rebuilt MANC network:
    scores 0.89–1.00, 2–3 active front-leg MNs, 10–12 Hz (paper: mean 0.974, median 3 MNs, ~11 Hz).
- **2026-09-23 01:30 – 03:00 (session 2, continued).**
  - 1,024-replicate dynamics reproductions (authors' NT and BrainIR NT: identical statistics), MaleCNS n = 128
    (rhythm reproduced, recruitment discrepancy §8.8); benchmark package (D31–D33), mapping layer (D35), pruning and
    screen procedures (D36) committed.
  - Compute: shared-payload backends (D37); Modal campaigns: 1,024 pruning screens (§3.17, $15.5), DN activation
    screen 933 × 16, interventions (MANC, MaleCNS), cross-connectome functional transfer n = 64.
  - Two defects found and fixed before the freeze (§3.18): MaleCNS readout selector, bundle edges filtered by sign.
    A third from the robustness agent's dt study: fixed-step pulse-edge stage error (§5). Bundles re-exported, audit PASS.
  - Delegated: robustness/dt/negative-control suite (`robustness_experiments.py`), nine baselines + null
    distributions (`benchmarks/dng100/baselines/`), reviews A–F (`research/audit/phase1_reviews/`).
  - PROTOCOL.md, freeze.py, cross-connectome evaluation (D38, D39); PHASE1_REPORT.md drafted.
- **2026-09-23 03:00 – 04:00 (session 2, reviews and freeze).**
  - Reviews A–E returned (`research/audit/phase1_reviews/`); their blockers and majors were closed in one pass (D40,
    D41): permuted tier-A positions, audit-hook clean-room sandbox, evaluator 1.1.0 (tier-A type-level family, amplitude
    gate, curated-pair grading, transfer sub-family), mapping schema 1.1.0, ingest version guard, corrected MaleCNS
    stimulus (the "recruitment discrepancy" retracted). All four datasets rebuilt with the final code; mapping tables
    rebuilt; `oracle/cross_connectome_reference.json` frozen; bundles re-exported (audit PASS); baselines re-run on the
    final blind bundle at the published 2 s protocol; DOP853 integrator-sensitivity run of the pruning prevalence.
  - Review F (reproducibility, report consistency) ran on the near-final tree and its blockers were closed (D42);
    final baseline campaign (2 s protocol, calibrated amplitude gate) and nulls; bundles re-exported at the frozen code
    state (hashes unchanged); `BENCHMARK_LOCK.json` written (lock `bcaa8ee46e23dc29…`, 131 benchmark files + 19 code
    files) and the tree tagged `dng100-benchmark-v1` at commit `29694f9`; PHASE1_REPORT.md finalised. Modal spend
    ≈ $38 (registry).
- **2026-09-23 17:00 – 20:00 (session 3, Phase 2 kickoff — `goal3.md`).**
  - Anti-leakage architecture: the orchestrator (this session, which has seen the oracle) builds only generic
    infrastructure; method design happens in fresh agents inside the oracle-free clean directory
    `C:\Dev\BrainIR_p2clean` (`scripts/make_phase2_cleanroom.py`: library, public bundles, clean-room runner,
    baseline scripts without results, synthetic suites without truth, safe tests). Feedback to agents = aggregate
    per-family metrics only.
  - Infrastructure committed (399dfdd, e65c648, c0c7b0c): `brainir.discovery` (problem loader, budgeted cached
    simulator with hard call budget, criteria, interventions, result→prediction, registry, `run.py`), synthetic
    mechanism suite (10 families × complications × sizes; simulation-verified truth stored apart; 58 instances built,
    8 dropped as unverifiable), tournament scorer with bootstrap CIs, reliability sweeps over salted node-order
    variants (`scripts/reliability_sweep.py`), budget curves, remote bundle packing for Modal, synthetic
    cross-connectome PAIR suite (26 pairs built, 6 dropped: hub-distractor variants of negative_feedback_controller,
    winner_take_all, integrator), blind-tier correspondence (anchor fingerprints + annotation agreement), transfer
    harness with separately accounted adaptation budget, role graphs. Methods-only literature review
    (`research/phase2/methods_review.md`, 55 entries).
  - Method development delegated to five clean-room agents (greedy_plus, cem_search, group_probe, surrogate_search,
    evo_pareto) under `research/phase2/METHOD_DEV_CONTRACT.md`, plus a sixth for the cross-connectome component
    (`CROSS_CONNECTOME_CONTRACT.md`: `joint.py`, modes independent/transfer/prior/joint).
  - Frozen `greedy_prune_sim` reliability sweep launched on Modal (3 blind networks × 8 node orders × 3 seeds,
    `--budget-s 1500 --workers 1`); oracle scoring of its predictions deferred until the method lock. A Modal probe
    (2 runs) already showed order sensitivity without any oracle: the two cores shared 1 of 3 neurons and one failed
    keep-only on fresh seeds.
  - Pitfalls: a stray `re.py` in `%TEMP%` shadows the stdlib for scripts run from there (use the scratchpad);
    Modal workers are Linux, so Windows paths lose their basename (`path_basename`); the greedy-reference smoke
    tournament (`research/phase2/tournament/greedy_reference_small_smoke.md`) showed the fixed-k weakness
    (delayed_inhibitory_oscillator, 5-node mechanism: 0 % success).
- **2026-09-23 15:30 – 16:20 (session 3, continued; model switched to Opus 5.5 after the Fable credit limit).**
  - All six clean-room developers delivered (greedy_plus, cem_search, group_probe, surrogate_search, evo_pareto, joint);
    each was code-reviewed (no path/manifest/label/dataset access; criterion type used only for role naming), imported
    with its tests and documentation. Three developers and the joint developer disclosed a one-time glance at a
    truth-bearing development-suite build report that had been copied into the clean room by mistake (deleted, all
    agents notified); none used it. Consequence: selection and confirmation use NEW anonymised suites built with fresh
    salts that never entered the clean room (`mechanisms_v1_heldout`: 57 instances; `pairs_v1_heldout`: 26 pairs;
    `mechanisms_v1_final`: 57; `pairs_v1_final`: 27).
  - Truth-completeness audit (`suite_audit.py`): complications create unplanted sufficient sets (hub-driven activity
    bands, keep-only winner-take-all, backup substitutions); they are now part of the truth (35 in the held-out mechanism
    suite). Clarified metric `functional_success_causal` added next to the pre-registered keep-only 1-minimality (which
    marks every correct winner-take-all core as non-minimal because its lateral inhibitor is a context member).
  - Pre-registered selection tournament (`research/phase2/SELECTION_PROTOCOL.md`), held-out suite, 1,000 calls,
    2 node orders x 3 seeds (342 runs per method, 0 errors): structural success 1.00 for all five tournament candidates
    vs 0.74 for greedy_reference; causal functional success greedy_plus 0.997, cem_search 0.997, surrogate_search 0.991,
    evo_pareto 0.962, group_probe 0.953, greedy_reference 0.215; identity consistency (pairwise Jaccard / identical)
    group_probe 0.95/0.86, cem_search 0.91/0.81, greedy_plus 0.88/0.75, surrogate_search 0.85/0.63, evo_pareto
    0.86/0.68, greedy_reference 0.83/0.63; mean calls ~96-142 for the leaders, 745 evo_pareto, 304 greedy_reference.
    Budget curve: the leaders saturate at 250 calls; a labelled 50/100-call extension separates them (at 50 calls
    group_probe keeps 0.95 causal functional success and 0.91 identical cores; surrogate_search collapses to 0.32).
  - Frozen greedy_prune_sim reliability sweeps completed on all three blind networks (24 runs each, oracle-free):
    Jaccard 0.63 / 0.87 / 0.65 and keep-only pass rate 0.67 / 0.92 / 0.67 (manc_v1.2.1 / male-cns_v1.0 / manc_v1.2.3).
  - Composer of BrainIR v1 started in the clean room with aggregate-only selection results; reviews E (cross-connectome,
    clean room) and F (computational, main repo without answer-bearing files) started.
  - Pitfalls: job functions defined in a script's `__main__` cannot run on Modal (first pair tournament failed 1,040/1,040;
    jobs now live in the library); numpy 2 removed `np.trapz`; bulk results are committed gzipped (`archive_results.py`).
- **2026-09-23 16:30 – 17:15 (session 3, review F fixes).** Review F (computational) found 1 blocker, 7 majors, 11 minors;
  all resolved before the confirmation run (`research/phase2/reviews/F_resolution.md`): failures now count in every success
  denominator; runtime budget-integrity guard (real simulations == charged), read-only accounting, `sim.spawn()` for other
  networks, seeded weight noise, override whitelist, reserved parameter-seed namespace; pinned Modal image
  (`PinnedModalBackend`) and a runtime environment block on every job; launch-time provenance in registry records; the
  hidden-evaluation gate bound to the locked method/frozen baseline with a per-network ledger; stable correspondence
  ranking. **Correction:** "order sensitivity" of the frozen baseline (entries above) is sensitivity to node order AND the
  parameter draw that goes with it (the position-indexed sampler re-assigns draws under a permutation); reliability numbers
  in Phase 2 are consistency across node orders x parameter draws, applied identically to every compared method.
- **2026-09-23 17:30 – 19:20 (session 3, review E fixes).** Review E (cross-connectome, oracle-free, clean room) found 1
  blocker, 6 majors and 5 minors (`research/phase2/reviews/E_cross_connectome.md`, resolution in `E_resolution.md`).
  - **What it confirmed.** The transfer uses only public evidence and every simulation is charged.
  - **What it found.** Identity claims were not identity evidence: their confidence came from structural alignment, and
    under implementation shifts v1 claimed non-homologous neurons. The pair design made correspondence nearly free, and
    the joint advantage is an efficiency gain on that design.
  - **Harness fixes, orchestrator:**
    - one budget pool per run: `spawn` children draw from the parent, and runs are judged on `total_calls()`;
    - the truth guard (`discovery/guard.py`), in-memory truth for remote jobs, and static rules on method logic;
    - `load_network` restricted to other datasets;
    - identity scoring on every pair type, with `independent_pooled` and `*_null` control arms;
    - the harder `synthetic-pairs-v2` design, with the v1 design reproduced bit for bit;
    - `pairs_v2_heldout` and `pairs_v2_final` built with secret salts and 40-bit seed offsets;
    - the tier-B copy removed from the clean room;
    - protocol amendment §7, written before any method ran on the new suites.
  - **Method fixes** (calibrated identity claims, validated transfers only, budget inside the pool) were assigned to the
    oracle-free composer.
  - **Real-network transfer with greedy_reference** (oracle-free): the carried-over core is sufficient in the other
    connectome in 3 of 3 runs per direction, with 2 destination calls, and the matched null passes 0. Joint discovery
    takes 405 total calls against 1,040–1,069 for independent discovery.
  - **Pitfall:** bash heredocs that contain some quoted Python fail with "unexpected EOF"; use Write/Edit for code.
- **2026-09-23 22:00 – 2026-09-24 01:10 (session 3, reviews A and G).** BrainIR v1.0 imported, commit 691c0d6:
  - composed oracle-free;
  - the query object was renamed `Oracle` → `Prober` (no logic change);
  - held-out selection: structural 1.00, causal functional 1.00, identity Jaccard 0.97 / identical 0.95, 106 calls;
  - anti-gaming invariant;
  - ablations: group testing saves 105 calls, the canonical order raises consistency, the minimality cleanup is needed.
  Joint discovery against its controls (protocol §7.4) saves calls only on easy pairs and never raises success.
  - **Reviews A (causal) and G (adversarial), found independently.** v1.0 returns keep-only-sufficient sets that the
    intact network does not use (latent backups behind inhibitory gates, backup copies) and demotes neurons it measured as
    essential. Its group-silencing screen clears essential inhibitors masked by what they gate. Its probabilities are
    evidence-class constants whose calibration evidence was circular. Its edge predictions are topological guesses.
  - **The tournament metrics scored all of these as successes.** Structural success accepted audited latent backups.
    Causal-functional success checked only returned members. The Brier score used a best-overlap target and was dominated
    by trivially excluded neurons.
  - **Response (orchestrator):**
    - graded activity in `Outcome` and `SimQuery.remove_edges`;
    - a participation-aware audit (the six held-out and final suites were re-audited: only 2 latent backups among them,
      so the generator families rarely contain these structures);
    - `success_intact`, essential recall and a contested-neuron Brier score against a non-circular target;
    - protocol amendment §8, written before any confirmation run;
    - a third-party adversarial generator and scorer from review G's author (21 trap variants), wired into the harness,
      with held-out and final adversarial suites built with secret seeds.
  - **Method fixes (v1.1)** were assigned to the oracle-free composer.
  - **Pitfalls:**
    - on a Modal worker, a Windows truth path parses as a bare file name, so the truth guard blocked the worker's
      package directory (fixed, with a guard invariant);
    - a Git Bash path passed into `python -c` is resolved under `C:\c\...` (use Windows paths).
- **2026-09-24 01:10 – 2026-09-25 (session 3 continued: v1.1, v1.2, confirmation, lock, hidden evaluation, reviews B–D).**
  - **v1.1** (commit e22db1f, composed oracle-free) answered reviews A and G: admissibility-first selection, single-silencing
    evidence, a masking-proof screen, degeneracy and union repair. The adversarial truth definition was fixed by its third-party
    author after the composer reported an inconsistency (d6dc789); every held-out file was re-scored under the new definition.
    Held-out: adversarial correct 0.98 (v1.0 0.41), mechanisms success 1.00, pairs 0.96.
  - **Review B** (optimisation, on v1.1): 0 blockers, 1 major (B2: a real-network choice decided at the threshold edge by a t test).
    **v1.2.0** (c3362c0): paired discordant counts with a factor-2 tie band, round-robin selection, minimality closure, budget
    reserve. Held-out results identical to v1.1.
  - **Confirmation** (used once, after the freeze): mechanisms rule passes (structural +0.25, success_intact +0.42, 140 fewer calls);
    pairs 1.00 with all identity claims correct; adversarial correct 0.98, 99.1 % of confident runs correct.
  - **Lock** 959d689, tag `brainir-v1-preblind` (tree 911625b9, lock b4c0a9cb). Oracle-free real-network sweeps ran on the locked
    tree before the lock.
  - **Hidden evaluations (logged):**
    - six sweep scorings: v1.2 meets the frozen structural criterion in 20/24, 24/24 and 21/24 runs, greedy in 16/24, 22/24 and
      16/24;
    - blind attempt 01, one draw at the locked seed: published core on manc_v1.2.3 and male-cns_v1.0; on manc_v1.2.1 a sufficient
      4-neuron core with full excitatory recall but no inhibitory member.
  - **Review C** (statistics): 0 blockers, 5 majors (report framing: strong comparators, in-distribution traps, truth-definition
    change, k = 3, thin identity evidence). All resolved in the report and the analysis scripts; ablations and sweep comparisons
    now resample instances and order clusters.
  - **Review D** (leakage): 0 blockers, 4 majors. No answer identity reached the method. The answer's structure was in the clean
    room and in every agent's CLAUDE.md; isolation was procedural; tier B sat in the clean room for 8 h; the real-bundle amplitude
    gate came from the evaluator. Disclosed; the builder was hardened; the leakage guard was extended; gate sensitivity was run
    oracle-free. The reviewer's own post-lock oracle labelling of development cores was logged as an audit comparison.
  - **Lesson (process):** clean-room agents must run as separate sessions whose project directory is the clean room, with a
    private temp directory. A subagent inherits the answer-aware session's CLAUDE.md and scratchpad (review D, D2).
  - **Pitfalls:**
    - in a bash line `A && B && (C) & (D) &`, the `&&` chain including the first subshell becomes one background job, so a
      variable assigned in it is invisible to `(D)`: assign variables on their own lines;
    - a runner record that captures stdout keeps absolute paths: commit a redacted copy, because the frozen hash covers the
      original;
    - a directory named `truth_backup_pre_audit` escaped a skip rule that matched only `truth`: match `truth*`.

---

## 11. Phase 3 (state discovery; spec goal4.md) — decisions, pitfalls, chronology

### 11.1 Decisions

| id | date | decision | rationale / evidence |
|---|---|---|---|
| P3-D1 | 2026-09-24 | Phase 3 code lives in a separate uv project `phase3/` (package `brainir_state`), numerical stack pinned to the root's versions | The root pyproject / uv.lock and `src/brainir/**` are hashed by the Phase 1 benchmark lock and the Phase 2 method lock (a new source file would fail the Phase 2 check) |
| P3-D2 | 2026-09-24 | Isolation of every oracle-free agent = separate headless Claude Code session whose project directory is its room + PreToolUse guard (`python -I`) + Python audit hook (PYTHONPATH) + permission deny rules + no MCP + private TEMP + cross-session tools blocked (`scripts/p3agent/`); Docker rejected | The OAuth access token expires in ~0.19 h and sharing the refresh token would risk the host's auth; there is no API key. Canary test passed (LEAKAGE_POLICY.md) |
| P3-D3 | 2026-09-24 | Phase 2 candidates regenerated in `C:\Dev\BrainIR_p3regen` by the locked v1.2 (hash-verified sources), public tier-A bundle, public NO-GATE rhythm criterion, seed 0, budget 1000; kept if keep-only passes on >= 4 of 8 fresh public seeds | goal4 section 5. Result: 7 candidates (net1: 4, 3 neurons; net2: 3, 3, 6; net3: 3, 4), all 8/8. No candidate chosen by hand |
| P3-D4 | 2026-09-24 | Real systems = 3 full + 7 keep-only mechanism systems; populations by a public probe rule; networks anonymised net1-3; A/B target split by a public seeded permutation; hidden families generated only after the method lock from a salt committed by sha256 | PROTOCOL.md sections 2-3 |
| P3-D5 | 2026-09-24 | The synthetic benchmark (48 systems, 20 families, traps A-L, 2 implementation groups, 3 unrelated pairs, 2 non-compressible controls) was written by an oracle-free author; `noise_seed`, twins and `targets_public` added on request; suites dev (public seed 20260924) / heldout / final (seeds from the salt) | goal4 section 20. The author's 237 tests pass from the locked copy |
| P3-D6 | 2026-09-24 | Regression-based metrics (D closure, K latent recovery) use a data-adapted number of random features, min(256, max(16, n/8)), plus the linear features, with the ridge penalty chosen by an inner split by trajectory | With 256 fixed features and 4 test trajectories the cross-fitted R^2 of a correct 1-D latent was -11 (overfitting), not a property of the model |
| P3-D7 | 2026-09-24 | Synthetic non-intervention roles include the event-free pool trajectories (held-out parameter draws and initial states) | The suites' own test split has only 4 / 8 / 12 non-intervention trajectories per system (dev / heldout / final) |
| P3-D8 | 2026-09-24 | Tolerances tau_A, tau_C, tau_D, tau_E calibrated on the dev suite with a TRUE-LATENT reference (exact true latent as encoder, learned MLP transition / readout, events through a learned probe) before any method exists | goal4 section 7 ("from baseline distributions and synthetic calibration") |
| P3-D9 | 2026-09-24 | Method code runs on the orchestrator side only in the sandbox (`brainir_state.runguard`): fits in subprocesses restricted to their inputs; evaluation refuses file / process / network events from method frames | Technological rather than procedural isolation of hidden data from method code (tested) |
| P3-D10 | 2026-09-24 | Level B by successive halving with a pilot subset of 16 heldout systems fixed before any candidate existed | goal4 section 58; the full design (48 systems + G + I) costs ~85 fits per candidate |
| P3-D11 | 2026-09-24 | Simulation budgets in units (real full 10, real mechanism 3, synthetic 1 per trajectory); fits get 250 units | A real full-network trajectory costs 10-30 CPU-s, a synthetic one ~0.1 s |
| P3-D12 | 2026-09-24 | Clean-room ML stack pinned to the evaluation environment (torch 2.14.0, scikit-learn 1.9.1) | Fitted models are pickled and loaded by the orchestrator |
| P3-D13 | 2026-09-25 | Reviews E (statistics) and H (numerics) run in an EARLY round on the evaluation machinery, while the methods are still in development; A-D (and E's ranking follow-up) run on the composed candidate. Room `C:\Dev\BrainIR_p3review` = clean-room snapshot + `extra/` (orchestrator code, generator, public calibration, frozen integrator; dataset / paper / bundle names redacted, counts in `extra/README.md`); `make_review_room.py --extras eh`, later `--update` | Both questions are method-independent. A blocker in the evaluator found after the tournament would invalidate its rounds; found now, it costs a benchmark version before any candidate is scored |
| P3-D14 | 2026-09-25 | BENCHMARK VERSION 2 (tag `state-discovery-benchmark-v2`, same directory): the fixes of the early reviews E (5 blockers, 6 majors) and H (1 blocker, 7 majors), recalibrated tolerances, synced into the clean room with a generic notice to the developers | Found before any held-out or hidden evaluation; v1 was never used for one. Details: `research/phase3/reviews/EH_early_resolution.md`, PROTOCOL.md section 10.1. Acceptance criterion 9 is reported as "v1 frozen before development, corrected to v2 before any held-out use" |
| P3-D16 | 2026-09-25 | Operational reading of PROTOCOL section 9, fixed BEFORE any round: baselines are candidates in round 1 like any other; the best-ranked ELIGIBLE baseline of round 1 is carried into every later round as the Level C comparator even if halving would eliminate it (so that "the strongest baseline of the last round" exists); if a later round ranks another carried or surviving baseline higher, that one is the comparator | The frozen text presupposes a baseline in the last round; successive halving could remove all of them. No hashed file changes |
| P3-D15 | 2026-09-25 | Level B fits, evaluations, reference controls and the calibration run on Modal (`scripts/p3/modal_tournament.py`, container side `scripts/p3/p3modal/`) with the FROZEN workers unchanged: the tournament driver's three execution functions are swapped; every job runs in a fresh interpreter; a Linux guard (p3modal.guard via sitecustomize) protects the container's data roots from method frames; fit containers never mount the held-out volume | goal4 section 58. Round 2 alone is ~1,000 fits of 5-20 min each; the local machine (16 threads, shared with 5 agents) would need days. A dev calibration system gives the same numbers on Linux as on Windows to ~1e-9 |

| P3-D17 | 2026-09-25 | BENCHMARK VERSION 3 (tag `state-discovery-benchmark-v3`, same directory): the evaluation fixes of the pre-lock reviews A-D (7 blockers, 19 majors), recalibrated on the dev suite (Modal); synced into the clean room with a generic notice. Method findings relayed as generic requirements only | Found before the method lock, before any use of the FINAL suite and before any hidden real data existed. Mapping: `research/phase3/reviews/ABCD_prelock_resolution.md`; PROTOCOL.md section 10.1 |
| P3-D18 | 2026-09-25 | The D (closure) regressions fit the base (z, u, future input) WITHOUT shrinkage (guard: at most 1 base column per 4 fitted rows); the residual microstate is computed inside each training fold | Found while fixing review A B2: the ridge penalty shrank the base, so extra columns that merely repeat z "helped" — on the toy with the exact 2-D state the v2 history gain was 0.74 and the proper (leak-free) micro-gain 0.73; with the fix both are ~0. The v2 D null (tau_D 0.40) was largely this artefact: v3 tau_D = 0.092, and random-k passes 'closed' on 24 % of dev systems instead of 56 % |
| P3-D19 | 2026-09-25 | The closure gap stays DESCRIPTIVE (pre-registered power rule of calibrate.py: it would enter 'closed' only if random-k passed it >= 20 points less often than the true latent; both pass it on 100 %) | A model whose rollouts forget their initial state has a small gap whatever its latent; on the first calibration system random-k had a gap of 0.017 against the true latent's 0.30 |
| P3-D20 | 2026-09-25 | The evaluator's reference controls (`refmodels`) are not copied by the rollout isolation (`evaluate.Fresh`) | They are orchestrator code; the true-latent reference carries a lookup of every recorded state (tens of MB), which a per-rollout copy would make prohibitively slow. Method models are always copied |
| P3-D21 | 2026-09-25 | An independent BASELINE TUNER (fresh clean-room agent, no competing candidate, ~3 h budget, dev data only, `<baseline>_t` variants) before the version-3 round 3; the Level C comparator is ranked on S1-S5 among markov-valid baselines only | Review C M2: baselines were smoke-tested only; the round-2 comparator was chosen on components the Level C family does not test |
| P3-D22 | 2026-09-25 | Parallel orchestration (the user's acceleration directive): forks of the orchestrator implement disjoint parts of version 3 and the post-lock infrastructure (files owned per fork); clean-room agents (composer, baseline tuner) run concurrently; every Modal job runs in parallel apps | Serial barriers kept: v3 fixes and recalibration before the round-3 re-run; the method lock before the FINAL suite and before hidden data exist; hidden data never on the fit volume |
| P3-D23 | 2026-09-25 | REMOTE RUNNER for clean-room development experiments (`scripts/p3/devrun.py`): agents queue their own scripts; the orchestrator runs them on network-blocked Modal containers (up to 8 CPUs / 64 GB) with no repository code and only a hash-verified copy of the room's public `data/`; outputs come back into the requester's `runs/<prefix>/remote/` | The user asked not to throttle scientifically independent work because of local RAM; agents have no Modal access, so the orchestrator mediates (LEAKAGE_POLICY.md section 3.2) |
| P3-D24 | 2026-09-25 | Execution-only re-lock of version 3 (`state-discovery-benchmark-v3-relock1`): per-job container memory recording, per-run container sizing, the room builder's interrupted-sync recovery | Made while the version-3 round 3 was running; no evaluation module changed (same evaluator code tag), so no computation or result depends on it; the version-3 tag stays on the commit the round started from |
| P3-D25 | 2026-09-25 | The hidden real data are generated with the LOCAL backend (`generate_real_hidden.py --backend local`), not on Modal | Decided after the method lock and BEFORE any hidden data existed. The post-lock re-check of the Modal code path (`verify-public`, 20 stored public protocols of all 10 systems) found 13 of 20 records not bit-identical: without the dropped OpenBLAS core-type pin, AVX-512 hosts run other BLAS kernels (the pre-lock smoke test's 30 of 30 most likely ran on AVX2 hosts only). The same 20 protocols through the local backend's code path are 20 of 20 bit-identical (`research/phase3/level_c/hidden_generator_{modal_verification,local_verification}.json`). Host-dependent numerics would put a test trajectory, its counterfactual twin and the microstate restarts on possibly different kernels; the local backend keeps every hidden trajectory on the platform that produced the public training data (PROTOCOL.md section 10: 'the local backend remains available'; POSTLOCK_RUNBOOK 'generated on one platform'). The data are then staged on the eval volume for the Modal evaluation (`modal_tournament.py upload-real --what hidden`). Also found: the store index had two orphaned line fragments from concurrent appends on 2026-09-24 (records intact); removed after a backup |
| P3-D26 | 2026-09-25 | The hidden real data are generated ON MODAL after all, by the FROZEN generator on hosts without AVX-512 (`scripts/p3/hidden_gen_gate.py`), in 32 GiB containers; supersedes P3-D25 | The user asked to keep the local machine for light orchestration (the local generation's parent process holds every trajectory in memory, about 4-7 GB at the end, and a first local run was stopped by the host for low memory). The wrapper changes NO hashed file: every call of `generate_real_hidden.run_modal` goes through a gate that, on a host with AVX-512, ends its own worker before any computation, so that the frozen crash handling moves the input to another host; inputs that exhaust Modal's retries are re-submitted. A benchmark re-lock was therefore not needed, and would have broken the method lock, which records the benchmark-lock hash. Validity checks: the gated path must reproduce 60 stored PUBLIC records bit for bit before use (`hidden_generator_modal_gated_verification.json`); after the run, every generated trajectory that the stopped local run had also simulated is compared array by array (`hidden_generation_crosscheck.json`) |
| P3-D27 | 2026-09-26 | Level C runs the FROZEN driver through `scripts/p3/level_c_fast.py`, which changes placement only: host-gated (no AVX-512) fits and evaluations; per-size worker classes (mechanism 16 GiB, one full network 32 GiB, joint fits 128 GiB, all with 4 physical cores for the locked 3 threads; non-preemptible for the long classes); all independent fits submitted at once, longest first; the frozen payloads, container callables, evaluation / reference / reproducibility functions and output files | The user asked for the fastest scientifically identical execution. Measured first, on PUBLIC data: (1) the workspace runs at most about 100 containers at once, whatever their memory (quota probe: 99); (2) the locked fits are single-configuration only on one kind of host: the same public fit run through the frozen app twice gave the same k but a different delay configuration (480 parameters differ, up to 55 % relative), whereas two runs on gated hosts are identical apart from timing fields (`research/phase3/level_c/levelc_fast_validation.json`); gated Modal fits still differ from the development machine's (Windows) fits, so one platform must produce all fits of a run, as the runbook requires. Threads per fit stay at the locked 3 (more threads would change the locked compute budget), so more cores cannot speed up one fit; GPUs cannot help (the only torch code is ks_share's joint training on k x k CPU tensors without device handling). No hashed file changed, so no re-lock |
| P3-D28 | 2026-09-26 | The real counterexample searches with HIDDEN parameter draws stay LOCAL, run at low process priority | PROTOCOL.md section 10 (hashed) pre-registers them as local ('searches with hidden real draws run after Level C, locally'). Modal would not expose the salt (the jobs carry only draws derived locally), but changing a pre-registered execution rule needs a benchmark re-lock, and a re-lock would break the method lock, which records the benchmark-lock hash |
| P3-D29 | 2026-09-26 | The post-lock reviews (S, C, Y, R in the post-lock room; L answer-aware) are resolved at the REPORTING level only: every corrected number is re-derived by `scripts/p3/postlock_numbers.py` (`research/phase3/reviews/POSTLOCK_NUMBERS.json`); reviewer numbers that do not reproduce are not adopted (listed in `reviews/POSTLOCK_RESOLUTION.md`); the hashed self-audit is not edited: each check keeps its computed status, with orchestrator notes and a `reported_status` (Q9 n/a; Q16's real evidence void) via `scripts/p3/merge_self_audit.py` | The method is locked, so no finding may change it. Four reviewers independently found the same first-draft error (PCA-k 'better on 9 of 10', a horizon mismatch inside self-audit Q16), one reviewer (C) repeated the mismatch in its own correction, and two others made small arithmetic slips; re-deriving every number from the result files is the only way to keep the corrections themselves correct |
| P3-D30 | 2026-09-26 | The headline Modal cost is the BILLED amount (Modal workspace billing report, hourly per app, `scripts/p3/modal_billing.py` -> `research/phase3/MODAL_BILLING.json`); the job-record list-price estimate is kept for per-task attribution, corrected for a double count by `scripts/p3/compute_summary_postlock.py` (the hashed `compute_summary.py` is run unchanged except its LEDGER_COVERED table) | Review R found three ledger rows counted twice ($312 -> $272). The billing report gives $136 for the Phase 3 window (through the 11:00 UTC hour of 2026-09-26): the estimate prices every container as 2 cores + 6 GiB at list price, while Modal bills measured usage (and it includes the 1,713 host-gate refusals the records do not price) |
| P3-D31 | 2026-09-26 | Synthetic family H (the pre-registered `noise_heldout` robustness readout) is recovered by re-evaluating the STORED seed-0 FINAL fits of the locked method and the comparator (`scripts/p3/final_h_family.py`, 92 evaluations on Modal, logged START / DONE as a post-hoc extraction; no refit) | The frozen tournament summariser keeps only verdicts, K, dimension and lifting per system, so the evaluator's `res['H_ood']` was never stored (review R M10). The re-evaluated in-distribution A reproduces the stored verdict A exactly (max relative difference 9e-16), which also confirms the determinism of the evaluation on stored fits. The first run read the real-system horizon keys (the synthetic primary horizon is 1 s); its summary was discarded and the run repeated |
| P3-D32 | 2026-09-26 | Phase 3 is reported but NOT declared complete: 49 of 50 acceptance criteria are met; criterion 26 (lifting exists or a rigorous reason is documented) is only partly met, because the locked v1 has no `lift()` (lifting exists in the benchmark and 8 baselines lift). The final tag `brainir-state-v1-phase3-final` marks the evaluated and reported state | goal4 section 85: do not declare Phase 3 complete until all criteria are satisfied. Adding `lift()` now would be a post-hidden change to v1 (criterion 48); it needs a new clean-room method version, lock and hidden test |
| P3-D33 | 2026-09-26 | Review L's process findings: the 126 fake-salt dry-run records are moved from `data/phase3/store` to `data/phase3/store_quarantine_fakesalt/` (index backup kept); the hidden real data stay on the eval volume `brainir-p3-eval` for reproducibility, marked answer-bearing, never to be mounted by a later phase's fit or development containers; stale passages of LEAKAGE_POLICY.md 3.1 and POSTLOCK_RUNBOOK.md are annotated (errata appended, not rewritten); snapshot provenance of every post-lock run is recorded (`scripts/p3/postlock_provenance.py`) | The dry run's spawn workers re-imported the generator module, so its redirected DATA path did not reach them and they wrote into the production store (0 of 126 match the committed salt; none is in the dataset). An orchestrator reference-control precompute also touched 2 FINAL systems on 2026-09-25 08:32-08:58 UTC before the lock (4 cache files, a superseded key, never read, no method involved): the report's 'the FINAL suite had never been used' is corrected to 'no method had been fitted or evaluated on it' |
| P3-D34 | 2026-09-26 | A verification reviewer V (a separate session in the post-lock room; task `research/phase3/review_contracts/POSTLOCK_V_TASK.txt`; the room builder gained an optional fifth reviewer) checks the corrections of the post-lock reviews against the result files before the final tag | Correcting four reviews by hand can introduce new errors. V confirmed every blocker fix and found four new problems in the corrections: a false G10 statement adopted from review C without checking (the method DID declare no compact state on G10), Y's nn_dim_rule S3 interval rejected by a script that used the point D estimate instead of the pre-registered S3, the permitted claim still calling the net2-full latent 'sufficient', and lineage missing from most Level C tables. All were fixed before the final tag |
| P3-D35 | 2026-09-26 | Phase 3 is complete AT THE LEVEL AT WHICH THE ACCEPTANCE CRITERIA ARE STATED (supersedes the status part of P3-D32): criterion 26 is met at the benchmark level (the lifting test exists and ran on 8 baselines); for the locked method, which has no native lift(), latent interventions were tested only post hoc, by an evaluator-side lift through its encoder (`scripts/p3/lift_v1_encoder.py`; minimum-norm solution of goal4 section 13's lifting problem; logged START with the design before any result, and DONE) | Criterion 26 sits among the benchmark's measurement items (20-27) and, unlike 18-19, does not name the final method. The first report versions read it at the method level. Review V's second pass: the status change is a change of reading, not new evidence, and must carry the qualification in the same sentence; v1's lift must not be compared with the baselines' on the encoder-measured shift (favourable by construction), and the true-latent spread (v1 0.54, baselines 0.30-0.68) must be reported. Result (46 systems): achieved-shift error 0.25, readout NMSE after do(z) 0.17 against 0.079 on the twin, invariance ratio 0.16. v1 is unchanged (criterion 48) |

### 11.2 Pitfalls hit

- The real engine costs 10-30 CPU-s per full-network trajectory (adaptive RK45 over n ~ 4,500 and one restart per breakpoint),
  not the 4-5 s measured on a nominal trajectory. The 3,005 public trajectories took ~40 min on 12 workers.
- Evaluation workers without thread limits oversubscribed the CPU (numpy BLAS and torch default to all cores): worker
  initialisers call `threadpoolctl.threadpool_limits(2)` and `torch.set_num_threads(2)`.
- The fit guard first treated the `mode` argument of the `open` audit event ("r") as a path and refused every import: only the path
  arguments of an audit event are checked now.
- Long inline Python patches in bash heredocs failed with "unexpected EOF while looking for matching quote": write patch scripts to
  the scratchpad with the Write tool.
- Windows Python needs `C:/...` paths; `/c/...` works only in bash.
- Real readout populations are small (9, 20 and 10 active readout neurons on net1-3), and the observed populations are 197-213
  neurons (full) or 3-6 (mechanisms).

### 11.3 Chronology

- **2026-09-24 20:00-22:50 (Phase 3 start).** Isolation stack; literature review (oracle-free agent, filtered web); synthetic
  benchmark (oracle-free author, 237 tests); candidate regeneration (7 candidates); real public data (3,005 trajectories);
  synthetic suites and pools; screen (1 diverged heldout trajectory removed); smoke tournament with a toy PCA method (pipeline end
  to end: sandboxed fits, shared / leave-one-out fits, evaluation, lifting, G, verdicts, profile); calibration (45 dev systems,
  75 min on 7 workers).
- **Benchmark lock, then an immediate re-lock before any use.** The first lock (commit 186b1d3, tag moved) was superseded ~15 min
  later. No agent had started, and nothing had been evaluated. The clean-room builder refused PROTOCOL.md because the Phase 3
  hidden-evaluation log was named like the Phase 2 answer file (`HIDDEN_EVAL_LOG.md`), which is on the builder's forbidden-phrase
  list. The Phase 3 log is now `research/phase3/HIDDEN_EVALUATIONS.md`. The protocol, level_c.py and LEAKAGE_POLICY.md were renamed
  accordingly and the benchmark was re-locked. The tag `state-discovery-benchmark-v1` points to the re-lock commit.
- The clean room was built from the allowlist: 7,542 files, scan clean (`research/phase3/CLEANROOM_MANIFEST.json`).
- **Pitfall (lock hygiene).** `freeze_benchmark.py --check` also fails on NEW files in hashed directories (research/phase3/contracts/*.md,
  benchmarks/state_discovery_v1/**) and on edits of hashed scripts (even docstrings). Post-freeze documents go elsewhere, e.g.
  research/phase3/review_contracts/. Run the check after touching anything under those paths.
- **2026-09-24 23:40-00:10: review F (leakage) and guard version 2.**
  - Findings: 2 blockers (the Bash and Python guards were substring blocklists with demonstrated bypasses), 3 majors (answer
    material in the shared account's ~/.claude; the uv cache names the datasets; synthetic suite seeds in cleartext), 4 minors.
  - No leak had occurred: 0 answer tokens anywhere, and a replay of every executed tool call through the new guard finds no escape.
  - Both guards were rewritten with resolve-and-contain while the agents were running (see `research/phase3/reviews/F_resolution.md`).
    Version 2.0 briefly produced false denials (review G's own room name, dict literals, `$tag/` in scripts); v2.1 fixed them within
    minutes.
  - Lesson: test a live guard against a replay of real agent traffic BEFORE swapping it in; write the new version to a staging path
    and move it over only after the replay is clean.
- **2026-09-25 01:40-03:30: early reviews E and H, benchmark version 2, Modal backend.** Both reviews ran in 25 min on the redacted
  review room and found real errors (rank by list order, NaN units dropped, medians over own subsets, missing Level C family, seed-
  decided D / E, coordinate-dependent E, handicapped shortcut control, diverged-trajectory normaliser, lifting noise mismatch).
  Fixed as benchmark v2 before any held-out use (P3-D14). Pitfalls:
  - Modal `serialized=True` pickles a MODULE-LEVEL function by reference: the container crash-loops with "module ... not available".
    Build the remote functions as closures (Phase 1's `_make_remote_wrapper` did this).
  - A whitening eigenvalue floor of 1e-4 x lambda_max breaks the invariance of E for legitimately anisotropic latents (a PCA latent
    had a 3000:1 variance ratio): 1e-8.
  - Local calibration of one dev system took 850 s under agent load; Modal ran 3 in 390 s wall (~$0.14).
- **Version 2 re-locked once before any use (2026-09-25 03:55).** The uplink is about 1 MB/s; per-file uploads of a suite ran at
  0.2 MB/s. A tar upload with extraction inside Modal (`modal_tournament.py upload --tar`) was added to two hashed backend files
  (`modal_tournament.py`, `p3modal/remote.py`). It is an upload utility, and nothing had run under v2. The lock was rewritten and the
  tag `state-discovery-benchmark-v2` moved to the re-lock commit. The heldout suite went up as 790 MB + 70 MB (the truth subset the
  evaluator reads) in 7 min.
- **Version 2 re-locked a second time before any use (2026-09-25 04:40).** A dev-suite smoke tournament on Modal found two
  execution bugs, both fixed before any held-out run:
  - the container lacked the frozen `brainir` package: the simulation service imports the real engine, although synthetic runs never
    call it;
  - `runner.import_method` only found methods registered in a module of the same name. This would have failed every baseline that
    shares a file (`lin_pcadyn` in `lin_baselines.py`), in Level B and in Level C. The method is now looked up across the package's
    modules (test `test_import_method_finds_methods_registered_in_a_module_with_another_name`).

  The smoke on the dev suite then ran end to end (lin_pcadyn: 94 fits, 84 evaluations, 66 reference prefetches, G, shared and
  leave-one-out fits, profile and ranks; 4 fits failed inside the developer's in-progress shared-fit code). The lock was rewritten
  and the tag moved.
- **Milestone transcript audit (2026-09-25 05:00, after the v2 sync).** All 10 agent streams were audited, about 22,000 events:
  - 0 forbidden-path inputs;
  - 0 web use outside the literature agent;
  - 0 tool calls that the current guard would deny beyond the ones denied at the time.

  One "answer token" hit in m_lin was a false positive. A 5-digit file size in an `ls -la` listing equals a numeric body id of the
  answer. The audit now reports the CLASS of each hit (numeric length / non-numeric), never the value. There are no non-numeric
  hits anywhere.
- **2026-09-25 08:35: developers asked to wrap up.** After 9.5 h the five method agents had settled their code but planned 2-12 h of
  further validation runs for their notes (one chain was "about 12 h of sequential jobs" on the loaded machine). Each session was
  stopped and resumed (`launch.py --resume`) with a generic wrap-up note:
  - stop your own long jobs by process id;
  - freeze the code (bug fixes only);
  - make the tests pass;
  - finish the notes with the results you have, marking missing numbers "not run";
  - declare candidates vs baselines;
  - report within about 45 min.

  The note carried no evaluation information.
- **2026-09-25 08:45-09:55: Level B round 1 (pilot).** 19 methods (12 candidates, 7 baselines) on the 16 pre-registered pilot systems
  of the heldout suite. Five parts on Modal (74 min wall; about $11.3), merged with the design check. Every candidate was eligible.
  - Mean ranks (S1-S7; S8 left out as all-missing): nn_closed 5.57, lin_falds 6.07, ks_sindy 6.29 (the highest P(rank 1), 0.52),
    lin_subspace 6.57, lin_balanced 7.07, lin_dmdc 8.36, ks_edmd 8.79, nn_aelin 8.93, ks_hankel 9.21, cb_cegar 9.50, then cb_psr, lin_pcadyn,
    cb_interchange, nn_seqbottleneck, ks_kae, sd_shared, sd_lowrank, nn_rssm, nn_pred_bottleneck.
  - The top 10 survive (`research/phase3/tournament/r1/ROUND_DECISION.json`). The comparator baseline is lin_falds (P3-D16).
  - Caveat: the pilot has no shared fits (pre-registered), so the sharing-specialised candidates (sd_*) got no credit for sharing.

  The aggregate feedback was published to the room (`publish_feedback.py`: the frozen feedback.py, with the S8 wording brought to v2).
  The composer was launched in parallel with round 2.
- **2026-09-25 10:00-11:15: Level B round 2.** The 10 survivors on all 48 heldout systems, with G seeds, shared fits (2 groups, 3
  unrelated pairs) and leave-one-out fits. Ten parts on Modal (70 min wall; about $26.4).
  - Primary ranking under the literal eligibility rule, 7 eligible: lin_subspace 3.31 (P(rank 1) 0.57), lin_falds 3.69, nn_closed 3.88,
    lin_dmdc 3.94, ks_sindy 4.12, nn_aelin 4.38, lin_balanced 4.69.
  - ks_edmd, ks_hankel and cb_cegar are independent-only by design. Their 18 shared / leave-one-out fits count as failures, just above
    10 % of 172. This conflicts with the "untestable" provision of section 7.
  - Sensitivity with all 10 eligible: lin_subspace is still first (3.94) and lin_falds is still the best baseline. The contested three
    rank 7th, 9th and 10th. The selection does not depend on the reading.
  - Finding: NO candidate obtains sharing support for either implementation group. Shared models are measurably worse than independent
    ones (A differences +0.02 to +0.15 NMSE with CIs above 0), and encoder-only adaptation rarely beats from-scratch fits. The unrelated
    pairs are correctly rejected (S8 = 0.5 for every sharing-capable method).
  - Round-2 feedback was published. The composer had been resumed at 10:18 (it had ended its turn waiting for a monitor, the headless
    pitfall).
- **2026-09-25 11:20-11:55: review G trap suite on the round-2 top five** (`research/phase3/review_g/results_r2top.json`; Modal, about
  $1.6). Every candidate is CONFIDENTLY WRONG on at least one new trap, i.e. it gets "compact causal state discovered" where the
  truth disagrees:
  - G4, a 9-stage delay chain: 4 methods claim a compact state with k = 3-4, or 14 with E untestable;
  - G10, non-compressible: lin_falds claims a compact state, k = 10, E untestable; only lin_dmdc abstains;
  - G7, local validity: ks_sindy claims a compact state with k = 1 against k = 3;
  - G9, parameter drift: the dimension is right, but the drift is not reported (a milder overclaim).

  On G1 (the symmetry-hidden mode) most methods choose k = 2 against 4, as designed, but none claims a compact state there. Lesson for
  the report: the verdict conditions (A, C, D, E) cannot certify minimality, or even correctness, of k on designed traps.
  Decision: nothing is relayed to the composer before brainir_state_v1 is scored on the G suite, so the suite stays an independent test
  of v1.
- **Pitfall (headless agents).** A headless `claude -p` agent that starts a background job and ends its turn "to wait for the
  notification" terminates, because nothing can wake it. Resume such sessions (`launch.py --resume <session id>`) with the note
  `scratchpad/resume_note.txt`: poll in the foreground and never end a turn to wait. Check every finished agent for complete
  deliverables before accepting it as done.
- **2026-09-25 14:00-15:20: pre-lock reviews A-D resolved in BENCHMARK VERSION 3.** The four reviews (A system identification, B
  causal inference, C representation learning, D computational neuroscience) found 7 blockers in the evaluation of brainir_state_v1
  and benchmark v2 (no enforced Markov / hidden-memory test; a powerless closure condition; C unable to show a causal STATE and
  including non-held-out and unobservable pairs; S6 rewarding wide k ranges; real readout NMSE dominated by near-silent neurons; an
  unattainable real predictive condition). Resolution: `research/phase3/reviews/ABCD_prelock_resolution.md`. Round 3 attempt 1 (v2,
  brainir_state_v1: mean rank 3.62, P(rank 1) 0.56) is recorded and superseded: the selection re-runs round 3 under v3.
  Calibration v3 on Modal (45 dev systems, 486 s wall, $1.97): tau_D 0.092 (was 0.40), tau_H 0.234, tau_gap descriptive, tau_E and
  tau_A unchanged; random-k passes 'closed' on 24 % of the dev systems (v2: 56 %), the true latent on 80 %.
- **2026-09-25 ~16:00: design of Level B round 3 under version 3 (fixed before any version-3 held-out result).** Participants:
  - the 10 round-2 finalists (lin_subspace, lin_falds, lin_dmdc, lin_balanced, ks_sindy, ks_edmd, ks_hankel, cb_cegar, nn_closed,
    nn_aelin). Their round-2 fits are RE-SCORED (not refitted): version 3 changed the evaluation only, their code is byte-identical
    to the round-2 snapshot (checked by `scripts/p3/stage_round_fits.py`), and the design (seeds, simulation budget 250, time limit
    1800 s, systems, G systems, shared / LOIO fits) is unchanged. Failed fits are attempted again;
  - the declared baselines eliminated in the pilot (lin_pcadyn, nn_rssm, nn_seqbottleneck): pilot fits re-scored, the remaining
    fits made now;
  - the independently tuned baseline variants (`<baseline>_t`), fitted in full;
  - brainir_state_v1 after the composer's response to the generic requirements, fitted in full.
  Each part runs as its own Modal app (parallel); `merge_rounds.py --decide` applies the pre-registered decision rule and the
  comparator rule (PROTOCOL.md section 9). The shared reference cache of version 3 is filled once before the apps start.
- **Pitfall: forcing OpenBLAS kernels on Modal crashed workers (SIGSEGV).** After the numerics pinning of the Modal image
  (`NPY_DISABLE_CPU_FEATURES`, `OPENBLAS_CORETYPE=Haswell`, `ATEN_CPU_CAPABILITY=avx2`), 2 then 4 of 45 calibration systems died with
  exit -11 and an EMPTY stderr even with PYTHONFAULTHANDLER=1; no such crash appears in the ~3,000 unpinned jobs of rounds 1-3. Every
  re-run inside the same container crashed again (the crash follows the host). Experiment (`research/phase3/level_c/
  modal_pinning_crash_experiment.json`, 4 crash-prone dev systems x 5 repeats x 4 variants, $3.3): inputs lost after all retries only
  with the OpenBLAS pin present (all pins 2, without the torch pin 2, without the OpenBLAS pin 0, without the numpy pin 0).
  Decision: OpenBLAS kernels are no longer forced (numpy and torch stay pinned: the real engine needs them for bit-identity with the
  local trajectories, re-checked by `generate_real_hidden.py smoke-public`); a worker killed by a signal is re-run once in its
  container, then the container exits so that Modal re-runs the input on another host (up to 3 retries), all recorded. Consequence:
  dense linear algebra, hence fits and evaluation statistics, may differ between Modal hosts in the last digits (documented tolerance
  in PROTOCOL.md section 10). The first v3 calibration run had no crash (whether its image already carried the pins was not
  recorded); the calibration of record is the run made with the final image.
- **2026-09-25 ~16:20-17:00: memory incident and execution changes.** Claude Code stopped every background shell for low memory
  (13 local tournament drivers each with a local simulation service, two clean-room agents' experiments and a room sync ran together
  on 28.7 GB). With the user's approval the work restarted memory-capped: the idle local simulation services of the Modal-backed
  drivers were stopped (Modal fits run their own), the composer and the baseline tuner were resumed from their sessions (the
  composer with both requirement batches), the interrupted room sync was completed (a builder bug: an interrupted sync left files
  copied but unrecorded; fixed), and `lin_dmdc`'s round-3 part was re-run after a Modal client SSL crash (fits cached). The user then
  asked to move memory-heavy work to sized Modal containers instead of throttling: every Modal job now records its container's peak
  memory, container size is set per run (`P3_MODAL_CPU`, `P3_MODAL_MEM_MB`), and clean-room agents get a remote runner (P3-D23).
  These execution-only changes were re-locked (`state-discovery-benchmark-v3-relock1`); no evaluation module changed (evaluator code
  tag 365f7ad6d9 before and after).
- **Pitfall: a transient network failure kills a tournament driver.** A DNS blip on the development machine (`getaddrinfo failed`)
  crashed two Level B drivers mid-fit, and their completed fits were lost because `modal_run_fits` writes fits only after the whole
  map returns. Remedy used: re-run the driver (idempotent over cached fits); the launcher now retries a crashed driver up to 3 times
  and keeps every attempt's log. Two parts that ran under the broken re-lock 1 (`r3v3_lin_dmdc` attempt 2, `r3v3_nn_aelin_t` first
  launch) are archived as invalid under `research/phase3/tournament/_failed/` and annotated in LEVELB_LOG.md.
- **2026-09-25 17:58: composer finished its version-3 work** (session resumed 16:58 with the corrected remote-runner path; $17.2, 66
  turns). Both requirement batches were answered in code, notes (section 10: every change since the tournament version and why) and
  37 passing tests; no local process left running. Transcript audit of all streams after it: 0 forbidden-path inputs, 0 answer-token
  outputs in the composer's streams, 0 web use. The guard denied 7 of the composer's calls, all false positives of a conservative rule
  (a hexadecimal system id read as encoded text; `\.` in grep patterns read as a `/./` path component); the replay through the
  current guard denies nothing else. The remote runner served 192 of its jobs (190 exit 0, 2 infrastructure errors) and refused 12
  requests whose arguments failed the character whitelist; 13.4 container-hours, about $14.3.
- **Memory profile for container sizing (remote-runner records):** synthetic development jobs peak at about 1.1 GB (p95); the six
  largest jobs, fits on the real full networks, peaked at 6.9-8.2 GB. Level B keeps the default 2 CPU / 6 GiB containers (tournament
  records: fits at most 2.1 GB, evaluations at most 1.1 GB); Level C fits need containers of 16 GiB.
- **Pitfall: a driver can survive a failed Modal heartbeat without finishing.** The second attempt of `r3v3_lin_falds_t` hit the DNS
  failure in the client's heartbeat and then idled for 45 min (0 CPU) while its relaunch completed; it was killed at 18:04. Check for
  duplicate drivers of a round before merging, because two drivers write to the same round directory.
- **2026-09-25 16:40-18:30: Level B round 3 under version 3 and the round decision** (`research/phase3/tournament/r3v3/`, 19 parts,
  one Modal app each; design hash identical across parts). brainir_state_v1 (fresh fits: 1,292 s wall, $3.7) has 7 failed fits,
  ALL leave-one-implementation-out ADAPTATION fits of the two implementation groups: a deterministic ValueError in the method's own
  adaptation code (inhomogeneous latent covariance shapes across the source model's systems). They count as failures and were not
  retried or fixed: a fix after seeing this held-out round would be a second chance no other participant had. For both groups its
  "shared" model equals its independent fits (identical parameters), so its sharing verdict is "untestable" there. One evaluation
  failed (a descriptive leave-one-out row of an unrelated pair). 8 of 204 units fail: eligible.
  - Ineligible (18 failed shared / leave-one-out fits each, i.e. no sharing by design): cb_cegar, ks_edmd, ks_hankel, ks_hankel_t,
    nn_rssm, nn_seqbottleneck.
  - Primary ranking (S1-S8, 13 eligible): brainir_state_v1 5.00 (P(rank 1) 0.519, 90 % rank interval [1, 5]), lin_dmdc_t 5.50,
    lin_subspace 5.81, lin_dmdc 5.88, lin_falds 5.88, nn_closed 6.62, lin_pcadyn 6.88, lin_pcadyn_t 7.00, lin_balanced 7.25,
    ks_sindy 7.62, nn_aelin 7.75, nn_aelin_t 8.31, lin_falds_t 11.50.
  - Decision (pre-registered rule, `ROUND_DECISION.json`): brainir_state_v1 selected by the primary rule (P(rank 1) = 0.519 >= 0.5; a
    narrow margin, reported as such). Comparator: lin_dmdc_t, the best of the 8 eligible baselines on S1-S5 (nn_aelin, nn_aelin_t,
    nn_rssm and nn_seqbottleneck fail the Markov criterion on more than 10 % of the systems). lin_dmdc_t is lin_dmdc without its
    wall-clock branch (the tuner's "determinism only" variant): identical k and verdicts on all 46 systems and profiles equal to
    ~1e-14, so the order between the two was set by float-level differences and is immaterial; the deterministic variant is the
    one the protocol's determinism rule asks for.
  - The tuned lin_falds_t ranks last (S2 1.27, S6 0.09): the tuner's dev-suite gain did not carry to the heldout suite.
  - The v3 ablation pipeline was smoke-tested after the re-lock (dev suite, 2 systems; v3 verdicts, 0 failures, $0.05).
- **2026-09-25 18:35-19:05: method lock done; post-lock stage started; second memory stop.** After the lock (bce6dbf, tag
  `brainir-state-v1-preblind`): the Level B confirmation started as 13 parallel parts on the FINAL suite (`final_b_<method>`, 12 GiB
  containers, HIDDEN_EVALUATIONS.md row written at the start), and the dev-suite ablations started on Modal. The hidden real-data
  generation switched to the local backend (P3-D25); a first 5-worker start was stopped by the orchestrator after 2 minutes and
  restarted with 12 workers (the store reuses every record already simulated, bit-identically). At about 19:00 Claude Code stopped
  the background shells for low memory: 12 real-engine workers (300-700 MB each: every worker caches the engines of the networks it
  touched), 13 confirmation drivers (about 350 MB each), the ablation driver, plus the WSL VM and memory compression (about 4 GB) on
  28.7 GB. The 13 confirmation drivers survived (only their launcher shell was stopped, so they finish without the automatic retry);
  the generation (1,390 of about 3,360 trajectories simulated, records intact, no dataset written) and the dev ablations were
  stopped. With the user's approval the work continues sequentially and memory-capped: the confirmation drivers first, then the
  generation alone with at most 10 workers and at least 4 GB free, with Modal jobs (light local drivers) alongside.
- **2026-09-25 23:13 - 2026-09-26 00:30: hidden real data generated on Modal (host-gated), then Level C launched.**
  - Stages: 420 simulation batches in 1,049 s (2,022 refusals by AVX-512 hosts, 0 failed calls); 60 microstate batches in 177 s;
    assembly in 780 s. 3,360 trajectories and 1,920 microstate restarts, 1.59 GB.
  - The final gated tar call, a single input, kept landing on one warm AVX-512 container. In refuse mode that container never stops
    taking inputs, so it refused 400 times and the run stopped. `hidden_gen_gate.py finish` then ran the frozen tar (a byte copy,
    ungated), downloaded it, and checked it: tar sha256 end to end, the text files against hashes computed on the volume, and the
    trajectory count.
  - Cross-platform check against the stopped local run's records of the same keys: 1,727 of 1,764 identical. 37 differ, by up to
    0.77 (mostly net1 full), because the adaptive solver's step sequence differs between Windows and Linux on a few protocols (the
    documented real-engine behaviour). Every hidden trajectory, twin and restart comes from the one gated Modal platform; its
    internal determinism is checked by re-simulation (`hidden_generation_resim_check.json`).
  - Pitfall: a refusal gate needs the refusing container to stop taking inputs (`modal.experimental.stop_fetching_inputs`, callable
    only in the container's main process), or a single input can loop on one warm container. Level C's gate does this.
- **2026-09-26 00:30-10:35: Level C, post-lock analyses, report draft, post-lock reviews.**
  - Level C (attempt 01, the only one) ran 07:30-09:04 UTC through `level_c_fast.py` (P3-D27): 163 fits (8 failures in the
    method's own code: 2 partial-sharing NotImplementedError, 6 leave-one-out adaptation crashes), 128 evaluations, about $42 at
    the real container sizes.
    - Verdicts: brainir_state_v1 not supported on 9 of 10 real systems, partially supported on net3 full.
    - Predictive on the three full networks (better than input-only and persistence). [Corrected after the post-lock reviews: the
      first draft's 'a PCA latent of the same k predicts better on 9 of 10 systems' was an artefact of self-audit Q16, which
      compared PCA at 10 ms with the method at 250 ms; at the matched primary horizon PCA-k is significantly better on 2 of 10
      systems (both net2) and the method on 6 (P3-D29).]
    - Held-out C >= 1 on every full network (no interventional claim). No sharing across mechanisms or reconstructions.
  - FINAL-suite ablations (re-run after the scheduling abort): only event_calibration matters on S1-S5 (S2 +0.30 [0.13, 0.47]); the
    dev-suite dimension-rule effect does not replicate.
  - Counterexample sweeps: synthetic FINAL (effect and post, method and comparator, Modal), real public draws (Modal) and real
    HIDDEN draws (locally, below-normal priority, 56 min, as pre-registered, P3-D28). Q19 passes (0.17 < 0.5), but worst cases are
    extreme.
  - Review G's traps on the LOCKED method (descriptive): no full compact claim; k wrong on 5 of 9 compressible traps; no abstention
    on the non-compressible G10.
  - Self-audit (merged full run + Q19 / I14 re-runs): science 16 pass / 3 fail (Q11 implementation memorisation, Q12 seed
    stability, Q13 parameter uncertainty); integrity 12 pass / 3 fail (I3, I8, I11: check artefacts whose properties were
    verified; the checks are hashed and were not edited). Tests: phase3 194 passed; root 534 passed, 1 skipped.
  - The salt was revealed after Level C (`research/phase3/level_c/SALT_REVEAL.json`; matches its commitment).
  - PHASE3_REPORT.md was assembled from the working draft (conclusion: NOT SUPPORTED for the real circuits; partially supported on
    synthetic systems). The post-lock review room was built and checked (answer scan clean); reviewers S, C, Y and R run as
    separate sessions, and L as an answer-aware subagent.
- **Pitfalls (post-lock).**
  - The Modal workspace runs at most about 100 containers at once, whatever their size. Cap concurrent apps (the ablations at 30
    containers) so that the critical path keeps its slots.
  - Pricing records use the default container size: re-price runs made with other sizes (Level C, +$31).
  - A self-audit check can fail on the layout it was written for (I8's `_refcache`, I11's `bundles`): verify the property, report
    the failure, and do not edit hashed checks.
  - Select metric keys by the configured primary horizon (`harness.key_a(cfg)`), never by position: self-audit Q16 took the first A
    key (10 ms) and compared it with the verdict's 250 ms A, and a reviewer repeated the error. The synthetic primary horizon is 1 s,
    the real one 250 ms.
  - Summaries that drop the evaluator's per-family results lose pre-registered readouts (synthetic family H was never stored):
    keep the full `res` next to every summary.
  - Ledger de-duplication by name is fragile (three Level B rows were counted twice); take totals from Modal's billing report.
  - Spawn workers re-import modules: monkeypatching a module constant (a data path) in the parent does not reach them. Run dry runs
    in a separate data root chosen by environment variable or command-line option.
  - Post-lock records must name the method snapshot they ran (methods key, raw and LF-normalised hashes); the working tree has CRLF
    line endings, so raw hashes differ from METHOD_LOCK's LF hashes while the code is identical.
- **2026-09-26 10:30-12:10 UTC: post-lock reviews and their resolution (reporting only; P3-D29 to P3-D33).**
  - Reviews S (statistics; 4 blockers / 8 majors), C (claims; 3 / 11), Y (dynamics; 3 / 9) and R (report accuracy; 2 / 11) ran as
    separate sessions in the post-lock room (transcript audit: 0 inputs outside the room, 0 answer tokens); L (leakage and process,
    answer-aware subagent) found no blocker and 1 major (the FINAL reference-control precompute before the lock, no method).
  - Main corrections: the PCA claim retracted (matched horizons: PCA-k better on 2 of 10, the method on 6); the E-untestable verdicts
    split (17 + 2); the method's own abstentions reported (no compact state on 8 of 10 real systems; every kick and current pair
    abstained on the full networks; C covers silencing only and is not state-mediated); lineage-based counts; robustness at the
    primary horizon (net1 OOD 235-fold); the counterexample mechanism (near-null true effects, inside and outside the families);
    paired FINAL comparisons (only S1 and S6 significant); K distribution; self-audit readings (Q9 n/a; Q16 real evidence void).
  - Completed items: the 18 real-data root tests (18 passed; the root suite is 552 passed, 1 opt-in skipped); billed Modal cost $136
    (estimate $272 after the de-duplication); synthetic family H (P3-D31); retrospective log rows and errata; snapshot provenance; the
    fake-salt records quarantined; Phase 3 status stated as not declared complete (P3-D32).
  - Verification review V (P3-D34) re-derived the corrections: all original blockers resolved, 35 of 39 majors resolved; its 1
    blocker, 3 majors and 14 minors on the corrections were fixed (G10 wording, section 10.1 from the stored ablation CIs, the
    permitted claim split by reconstruction, lineage columns). Transcript audit of the five room sessions: 0 inputs outside the room,
    0 answer tokens.
  - Pitfall: never adopt a reviewer's factual statement without re-deriving it (C's G10 sentence was false); and re-derive
    pre-registered components by their registered definition (S3 = max(0, upper CI of the D micro-gain), not the point estimate).

## 12. Phase 4 (causal state models trained with interventions + active experiment design; spec goal5.md) — decisions, pitfalls, chronology

Plan: `research/phase4/PLAN.md` (orchestrator only). Generic interfaces: `research/phase4/INTERFACES.md`.

### 12.1 Decisions

| id | date | decision | rationale / evidence |
|---|---|---|---|
| P4-D1 | 2026-09-26 | Phase 4 code lives in a new uv project `phase4/` (package `brainir_causal`) with editable path dependencies on the root `brainir` and on `phase3`'s `brainir-state`, and the numerical stack pinned to Phase 3's versions | The root project and `src/brainir/**` are hashed by the Phase 1 / 2 locks, `phase3/**` by the Phase 3 locks; the frozen Phase 3 v1 must run unchanged as a baseline (same numpy / scipy / torch / scikit-learn) |
| P4-D2 | 2026-09-26 | Isolation of every clean agent = separate headless session (guard v2, Python audit hook, deny rules, no MCP, private TEMP) PLUS a Docker sandbox for all agent code execution (`brainir-p4-sandbox`, `--network none`, only the room mounted, CPU / memory caps; host interpreters refused by the guard) and a Modal remote runner (network-blocked containers with only the room's public data; CPU and GPU classes) | goal5 section 5 prefers a container sandbox and "do not rely only on instructions". Docker Desktop is available (29.6.1, WSL2). The Claude sessions themselves stay on the host: an OAuth refresh inside a container would rotate the host's refresh token (P3-D2); stated as a residual risk |
| P4-D3 | 2026-09-26 | Real systems = the ten Phase 3 real systems (three full networks, seven Phase 2-generated mechanisms), re-anonymised with new ids; the same public / hidden target partition; NEW hidden data from a new salt after the Phase 4 method lock | The mechanisms are the "multiple Phase 2-generated physical mechanisms" of goal5 section 55 and the three networks carry the cross-connectome comparison of section 56. Phase 3 hidden data and the eval volume `brainir-p3-eval` are never used (answer-bearing) |
| P4-D4 | 2026-09-26 | The synthetic systems are written by a fresh author agent in room `C:\Dev\BrainIR_p4bench` from a generic contract (`research/phase4/contracts/SYNTHETIC_BENCHMARK_CONTRACT.md`); the official datasets are generated by benchmark code from the frozen protocol families, not by the author | The orchestrator knows Phase 3's hidden outcomes; family definitions and truth written by an agent without that knowledge cannot encode them. Central, uniform family / split rules for synthetic and real systems |
| P4-D5 | 2026-09-26 | The methods literature review starts before the benchmark freeze (agent `p4lit`, filtered web, methods only) | It designs no method and sees no data; its review enters the clean room only after the freeze |
| P4-D6 | 2026-09-26 | Active experiment design is evaluated by a harness-driven loop (learner and designer are separate components; reference designers are benchmark code); the main model comparisons use identical benchmark data for every method | goal5 sections 25, 60 and 73 require matched budgets and a fair random / fixed baseline; separating the two keeps the model comparison independent of the design comparison |
| P4-D7 | 2026-09-26 | Protocol v2 gains two optional fields before any freeze: `params_spread` (multiplies the spread of the per-trajectory parameter draw; development 1.0 only) and `process_noise` (only where a system's capability supports it; the real engine refuses it) | goal5 sections 74-75 ask for OOD parameter spread and parameter / trajectory noise; without the fields the suite builder had to use weight-noise proxies (found by fork E7). Real systems: the frozen integrator is deterministic, so real trajectories get no process noise (stated) |
| P4-D8 | 2026-09-26 | The synthetic generator interface = the author contract section 4 (the adapter's build_suite / content_hash / restart_state design plus explicit truth methods: true_state, obs_shortcut_state, true_latent_effect, lift_latent, equivalent_states, pool_states); observation noise is added by the benchmark, never by the generator | One binding interface for the author, the adapter, the evaluator's truth metrics, the references and the suite builder |
| P4-D9 | 2026-09-26 | The frozen Phase 3 baseline runs through an orchestrator adapter (`brainir_causal.p3v1`): source hashes verified against the Phase 3 locks (9 files, all match); default configuration; no simulator, no designer; events translated (kick, current, current_seq, silence, edge_scale factor 0); param and other edge scalings have no counterpart: such training records are left out and such predictions abstained on; no native lift | goal5 section 20 (unchanged, untuned). The adapter embeds only file hashes, nothing else of the Phase 3 method lock (which names answer-bearing selection records) |
| P4-D10 | 2026-09-26 | The literature review (`p4lit`, 170 KB, 10 areas, 10 recommended families, 7 acquisition functions) is copied to research/phase4/METHODS_REVIEW.md with ONE wording change: its own curriculum steps 'Phase 1-3' renamed 'Stage 1-3' (lines 1983-1985) so that no room file carries phase numbers | Avoids false hits of the rooms' content scanner and any suggestion of project history; the original stays in C:\Dev\BrainIR_p4lit |
| P4-D11 | 2026-09-26 | Real MECHANISM systems (3-6 units) keep every member as a public target, as before; they have no target-shift test (family shift, hidden-only, OOD and robustness only). PROTOCOL.md section 3 amended before the freeze | A split would leave one to three trainable targets per mechanism, too few to learn a read-in; the full networks carry the target-shift test (found by fork E1) |
| P4-D12 | 2026-09-26 | Real unit ids stay the public-bundle positions (only system ids are re-anonymised) | Relabelling units would add engine risk for no protection: clean agents have no earlier-phase files, and earlier PUBLIC data are not answer-bearing |
| P4-D13 | 2026-09-26 | The store keeps microstates as float32 (Phase 3 format); restarts are exact to float32 precision (largest mechanism: continuation drift at most ~0.2 % of scale after 0.3 s from the rounding, amplified by the dynamics) | Storage size and bit-identity with the earlier engine's records; every pool future is simulated from the SAME stored state, so pair comparisons are consistent; the rounding acts like tiny state noise; review H checks it |
| P4-D14 | 2026-09-26 | Microstate equivalence (MEV) uses a FIXED number of matched pairs (the 20 closest cross-trajectory pairs within a parameter draw) on pools of 600 states (8 draws x 15 source trajectories x 5 times), instead of the draft's 2 % closest pairs on 200 states; MEV = mean of the per-sequence ratios | A fixed quantile does not tighten with pool size (the q-quantile of pairwise latent distance is a property of the distribution, ~0.27 of the random distance for k = 3), so MEV would be untestable for k >= 3 by construction (fork E5: an exact 3-D latent gave 0.225 > 0.2 on 200 states). With a fixed count the matched distance shrinks as the pool grows; testable up to k of about 5 |
| P4-D15 | 2026-09-26 | Mediation / closure regressions (PROTOCOL 5.3-5.4) as resolved by fork E5 before any method existed: additive decomposition of the intervention identity (per action key presence and signed dose, family, magnitude class, duration, count, onset); a PERMUTATION-MATCHED capacity null (arm A gets random features of the same extra features with items permuted within fold) plus an unpenalised per-lag bias in both arms; x_res with near-zero-variance components dropped and one common scale | With the draft's literal one-hot a target-dependent read-in error went undetected; feature-count capacity matching left seed-dependent spurious gains up to 0.33 for an exact model; per-column standardisation of x_res turned numerical noise into O(1) features. Validated: exact model SMS = ICG = 0 over 4 seeds; missing state SMS 0.57-0.72, ICG 0.80-0.89; wrong read-in / intervention-ignoring SMS 0.58-0.75 through identity |
| P4-D16 | 2026-09-26 | GPU policy (goal5 section 63) from the measured benchmark (16 devices x 4 workload kinds x 8 shapes, research/phase4/GPU_BENCHMARK.md): default GPU class for neural training = RTX-PRO-6000 (fastest or within 5 % on every workload; 55-60 % of B200's cost per epoch), fallback B200; H100 / H200 / B200 for large-batch throughput; CPU (4-8 cores) for small latency-bound jobs, where it is cheapest; gated CPU classes of <= 16 cores | GRU filters gain ~120x on GPUs, sequential rollouts / neural ODEs / ensembles 2-6x; CPU never wins on speed. CPU / GPU equivalence (criterion 39) passes on L4, A10, A100-80GB, H100, B200, RTX-PRO-6000: float64 GPU vs CPU 2e-16 to 2e-15, float32 1e-7 to 2e-6, repeated GPU runs bitwise identical |
| P4-D17 | 2026-09-26 | All official fits of one evaluation run on ONE platform (Modal Linux, host-gated CPU) and, for GPU methods, ONE GPU class, with the device recorded per fit | float32 results differ between Windows and Linux at ~1e-7 (float32 initialiser rounding; float64 initialisation agrees to 1e-16) and a GPU class can map to different hardware (A100-80GB SXM4 vs PCIe) |

### 12.2 Pitfalls hit

- Docker Desktop on Windows materialises a symbolic link created INSIDE a container on a bind-mounted directory as an NTFS junction
  on the host; a link pointing outside the room made the main repository listable from the host (fork E3, demonstrated on a scratch
  room). Fix: seccomp profile without symlink / symlinkat (`docker/p4sandbox/seccomp_nolinks.json`), realpath resolution of every
  path token in the guard, Glob / Grep refuse roots with links, the room audit reports links.
- Container code could plant `.claude/settings.local.json`, `CLAUDE.local.md` or `.mcp.json` in a room for the host session to load:
  the builder now creates read-only placeholders for them.
- Rebuilding a Docker image under the same tag DELETES the previous image; rooms reference the sandbox image by id, so their `sbx`
  broke until re-synced (10:52-10:56 local, no failed agent call). Rule: build a new tag, then `--sync` every room.
- A fixed-quantile matching rule (2 % closest pairs) cannot tighten with pool size; for k >= 3 it made microstate equivalence
  untestable by construction (P4-D14).

### 12.3 Chronology

- **2026-09-26 17:00 UTC (Phase 4 start).** goal5.md read in full; plan and interfaces written. The literature agent `p4lit` started
  (17:06). Four orchestrator forks started: E1 engine (protocol v2, real engine v2, re-anonymised systems, store, service), E2
  calibration statistics from public real data, E3 rooms and the Docker sandbox, E4 Modal backend and GPU benchmark.
- **2026-09-26 17:44 UTC.** Literature agent done (research/phase4/METHODS_REVIEW.md, REFERENCES.md). E2 done: calibration targets
  from public real data only (305 statistics, 35 checked; research/phase4/CALIBRATION_TARGETS.md). Bench room built by the Phase 4
  builder (13 files, scan clean; Docker sandbox brainir-p4-sandbox:1, allowlisted paths read-only) and the synthetic author
  `p4bench_author` launched as a separate session (4 CPUs / 12 GB sandbox caps).
- **2026-09-26 19:05 UTC.** E1 (engine) done: protocol v2 with params_spread / process_noise, real engine v2 bit-identical to the
  earlier engine on every mechanism system and a full-network trajectory, re-anonymised systems, store, service; 53 tests. E5
  (evaluator core) done: 36 tests; protocol resolutions P4-D14 / P4-D15. E3 (isolation) done: sandbox image, guard with host-command
  allowlist, builder, remote runner (CPU + GPU smoke), canary passed (research/phase4/CANARY_TEST.md), 117 tests; leakage policy
  drafted (research/phase4/LEAKAGE_POLICY.md). The synthetic author is designing its package.
- **2026-09-26 19:30 UTC.** E4 (Modal backend, GPU benchmark) done: simulation on host-gated Modal workers bit-identical to the local
  engine for every event kind and restarts (full network 2.1 s per 0.5 s trajectory on Modal); fit / eval guards block every
  probed forbidden access; GPU policy P4-D16 / P4-D17. Modal billed so far $15.56 (runs 1-9).
