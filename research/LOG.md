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
