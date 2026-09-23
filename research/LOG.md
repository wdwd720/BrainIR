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
7. **Pugliese et al. procedures not determinable from their repository** (see
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
