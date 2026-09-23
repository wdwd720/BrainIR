# Review A — data acquisition, ingestion, validation, provenance (Phase 1, MANC)

Date: 2026-09-23. Reviewer: independent read-only review (Fable 5.1 session). Scope as briefed: `src/brainir/sources/registry.py`,
`src/brainir/acquire.py`, `src/brainir/ingest/{__init__,common,manc,malecns}.py`, `src/brainir/manifest.py`, the committed MANC
manifests and validation reports, evidence separation (schema), and the MANC fixture/tests. Nothing outside this file was modified.
Repository state reviewed: HEAD `8df59ad` (moved from `4da40a8` during the review); `src/` clean at the time of the fingerprint check.

## 1. Verdict

The MANC acquisition/ingestion layer is sound in substance: every raw object is pinned by size + CRC32C + MD5 + GCS generation and the
acquisition logs show `pin_problems: []` for all 29 MANC files; the count rule (conf_post >= 0.4 / 0.7, weightHR = all pairs, float64
comparison of float32 confidences) is inferred on v1.0 where only conf_post 0.4 is exact and applied to v1.2 where the pre-threshold is
moot (min conf_pre = 0.75 in both partner tables); HR-only rows are counted and dropped (739,081 neuron pairs in v1.0); the processed
tables carry consistent `(dataset, version, id)` labels, no zero-weight edges, `hp <= weight`, edge sums equal per-neuron totals, and
the v1.2.3 snapshot's own per-neuron counts are reproduced for 23,665/23,665 bodies; evidence kinds are separated (NT = ML prediction,
consensus/literature null for MANC, sign computed on demand, no model parameters in anatomy tables); no absolute paths or secrets
appear in manifests or logs; 358 fast tests pass. Nothing I found invalidates the processed data. What is not yet defensible is the
*attribution and guarding* around it: (i) the committed `manc:v1.0` (and `male-cns:v1.0`) manifests were produced by a `manc.py`
/`registry.py` that differs from the committed code and record a commit that predates the MANC adapter, so those two builds are not
reproducible-by-fingerprint from HEAD until rebuilt; (ii) the programmatic ingest API lets a build be labelled with a foreign version
(verified on the fixture: v1.0 content written as `manc:v1.2.1` with 0 validation failures) — the CLI path is safe; (iii) the
synthetic fixture cannot distinguish the MANC threshold 0.4 from the hemibrain 0.5 (no synapse in [0.4, 0.5)), so the fixture test
protects the value only through the Meta's declared threshold, not through data; (iv) the v1.2.x manifests present the v1.0 neuPrint
Meta identity under `release.neuprint_snapshot` and state the neuPrint-v1.2.x correspondence as fact although it is an inference
(login-gated). All four are cheap to fix (a 40 s rebuild, a guard of a few lines, two fixture synapses, manifest field renames).

## 2. Findings (ranked)

Severity: blocker (data cannot be trusted) / major (a stated guarantee does not hold or is unverifiable) / minor (gap, cheap fix) /
note (observation, no action required).

### Blockers

None.

### Major

**A1. Committed `manc:v1.0` and `male-cns:v1.0` manifests are not attributable to any committed code state (dirty builds).**
- Evidence: all four committed manifests record `build.git.commit = b5d9565` with `src_dirty: true`
  (`data/manifests/*.manifest.json`, `build.git`). `b5d9565` ("Log: order decision entries D19/D20") predates `b671f42`, the commit
  that introduced `src/brainir/ingest/manc.py`, so the recorded commit is not the code that built the MANC data. The pipeline
  fingerprint saves the v1.2.x builds: their `pipeline_code.combined_sha256` (`022fa608…`) equals `_code_fingerprint()` of the current
  source. The `manc_v1.0` and `male-cns_v1.0` manifests carry `85ce8c98…`, whose `ingest/manc.py` and `sources/registry.py` hashes
  differ from HEAD. Whether the current `manc.py` would produce byte-identical `manc:v1.0` parquet is unknown (I did not rebuild).
- Where: `src/brainir/ingest/common.py:141-149` (`_git_state` records dirtiness but nothing acts on it); `src/brainir/manifest.py:226-228`;
  `tests/test_provenance.py:140` (asserts only that a commit string exists).
- Why it matters: goal2 WS2 "All transformations must remain reproducible", WS3 "confirm deterministic output", acceptance criterion 1.
  The LOG's "second builds byte-identical" claim (§10) cannot be tied to committed code for these two builds.
- Fix: (1) rebuild `manc:v1.0` (~40 s) and `male-cns:v1.0` (~8 min) from HEAD; compare `processed_outputs[*].sha256` with the committed
  manifests (expect identical parquet; if not, document what changed) and commit the regenerated manifests. (2) Make `brainir ingest`
  refuse to write `data/manifests/` when `src_dirty` unless `--allow-dirty`, and record `git diff --stat -- src` in `build.git` when
  allowed. (3) Add a fast test: for every committed manifest, `build.git.pipeline_code.files == _code_fingerprint()["files"]`. Longer
  term, fingerprint the *registry entry* (`asdict(source)`) and the adapter module used, not `registry.py`/other adapters' bytes, so
  pinning a new dataset does not invalidate unrelated builds.

**A2. The programmatic ingest API can label a build with a foreign version (silent substitution; CLI path is safe).**
- Evidence (run on the synthetic fixture in a temp dir): `IngestConfig(source=MANC_V1_0, build_version="v1.2.1")` →
  `build_dataset` succeeds with 0 failures, writes `neuron_uid = manc:v1.2.1:…`, parquet metadata `brainir_dataset_version = v1.2.1`,
  `build_info.version = v1.2.1`, `source_version = v1.0`. `IngestConfig(source=MALECNS_V1_0, build_version="v9.9")` → succeeds with
  `neuron_uid = male-cns:v1.0:…` and `dataset_version = v1.0` in the rows but `brainir_dataset_version = v9.9` in the parquet
  metadata and `build_info.version = v9.9` (rows and metadata disagree).
- Where: `src/brainir/ingest/manc.py:135-144` (`build()` dispatches on `cfg.source.version`, never checks `cfg.build_version` for v1.0);
  `src/brainir/ingest/__init__.py:16-24` (`build_dataset` has no consistency check against `BUILD_VERSIONS`);
  `src/brainir/ingest/common.py:75-77, 657, 689-690` (label = `cfg.version`); `src/brainir/ingest/malecns.py:386, 404`
  (`assemble_neurons` uses `cfg.source.version` while `write_outputs`/`finalize` use `cfg.version`).
  `src/brainir/cli.py:52` uses `resolve_build`, so `brainir ingest` cannot hit this.
- Why it matters: goal2 WS1 "NEVER silently substitute one dataset version for another"; tests/scripts/notebooks build through the API.
- Fix: in `build_dataset` (or `BuildRun.__init__`): `src, bv = resolve_build(cfg.source.dataset, cfg.version)`; raise unless
  `src is cfg.source and bv == cfg.version`. Use `cfg.version` in `malecns.assemble_neurons`. Add a test that a foreign
  `build_version` is refused (goal2 WS29 "dataset version isolation").

**A3. The MANC fixture does not exercise the boundary that defines the MANC count rule (0.4 vs 0.5), nor conf_pre.**
- Evidence: `src/brainir/testing/synthetic_manc.py:32` adds only conf_post 0.30 and 0.35 (`LOWCONF`); the base synapse list
  (`src/brainir/testing/synthetic.py:77-94`) has no PSD with conf_post in [0.4, 0.5). Under the fixture, weight rules with
  conf_post_min 0.4 *and* 0.5 are both exact; `tests/test_ingest_manc_synthetic.py:102-106` passes because `infer_count_rule`
  prefers the Meta's declared threshold (`src/brainir/ingest/manc.py:431-438`), i.e. the value is protected by the fixture's Meta, not
  by the data. Every fixture T-bar has conf_pre >= 0.70, so all pre grid values are exact and `conf_pre_min = 0.0` is untested. (Real
  data does discriminate: the v1.0 manifest's `inferred_count_rule.exact.weight` lists only conf_post_min 0.4; min conf_pre = 0.75 in
  both partner tables, so the pre threshold is moot for MANC.)
- Why it matters: 0.4 vs 0.5 is the MANC-specific deviation the whole v1.2 rebuild rests on (LOG D24: 0.5 misses 18,537 pairs); the
  fixture currently cannot catch a regression that swaps the fixture Meta and the default to 0.5 together.
- Fix: add one counted synapse with conf_post 0.45 (and one T-bar with conf_pre 0.35 that neuPrint counts) to `LOWCONF`-style lists with
  MANC-specific expected edges; assert `{0.0, 0.5} not in exact["weight"]` and that the chosen rule is data-determined when the Meta
  threshold is removed from the fixture.

**A4. v1.2.x manifests present inferred neuPrint correspondence as fact and label the v1.0 Meta identity as the build's neuPrint snapshot.**
- Evidence: `data/manifests/manc_v1.2.1.manifest.json` and `manc_v1.2.3` → `release.neuprint_snapshot = {uuid 59b37970…,
  lastDatabaseEdit 2023-05-02 …}` — that is the **v1.0** Meta (used only for the ROI catalogue), filled by the fallback in
  `src/brainir/manifest.py:190`. The real neuPrint manc:v1.2.1/v1.2.3 identity (uuid `7b5e8f7f…`, last-mod 2024-02-01 /
  2024-08-31) is public without a token (`research/manc_release_notes.md` §3.1) but recorded nowhere machine-readable.
  `src/brainir/sources/registry.py:466-467` ("the annotation state served by neuPrint manc:v1.2.1"), `manifest.neuprint_dataset =
  manc:v1.2.1` and `DEFINITIONS_V12["neuron"]` (`src/brainir/ingest/manc.py:910-912`, "the bodies neuPrint manc:v1.2.x exposes") state
  a correspondence that `research/manc_release_notes.md` §4.1/§9 marks UNVERIFIED (login required) and that LOG D21 supports only
  approximately (types agree with the paper's v1.2.1 table for 4600/4604 bodies; the 4 disagreements are unexplained).
- Why it matters: the manifest is the provenance record of record; a reader will take `release.neuprint_snapshot` as the v1.2.1 snapshot
  identity and the correspondence as verified. Acceptance criterion 4 ("checksums/provenance recorded") should not contain mislabelled
  identities.
- Fix: rename the field to `roi_catalogue_source_meta` (with `"role": "ROI catalogue only"`); fetch and store the public
  `/api/dbmeta/datasets` record for the matching neuPrint dataset at acquisition time (uuid, last-mod, ROI list); word the registry
  description and `DEFINITIONS_V12["neuron"]` as "public snapshot inferred to correspond to neuPrint manc:v1.2.x (unverified without
  login; paper table agreement 4600/4604)"; explain or list the 4 disagreeing bodies in LOG.

### Minor

**M1. Raw bytes are not re-verified at build time; the manifest's SHA-256 values are copied from the acquisition log.**
`src/brainir/ingest/common.py:172-216` checks existence + on-disk size and compares the *recorded* digests with the registry pins;
`common.py:698` and `manifest.py:163` copy `local_digests.sha256` from the log. `decompressed_partners_v10` (`manc.py:379`) does hash
the bz2 input but never compares it with the log, and its check text ("which the acquisition check verified", `manc.py:389-390`)
overstates. A same-size modification of a raw file after acquisition would go unnoticed and be recorded under the original hash.
Fix: compare `snapshot_sha256(src)` with `acq["syn_partners"]["local_digests"]["sha256"]`; add `IngestConfig.rehash_inputs` (default
on; ~10 s per GB) that fails `provenance.raw_inputs_verified` on mismatch; add `brainir verify` that re-hashes raw files against the
log/registry and processed files against the committed manifest (`processed_outputs[*].sha256`). Only `brainir acquire` currently
re-hashes (existing files are verified against remote CRC32C/MD5, `acquire.py:187-191`), which is good but not part of `ingest`.

**M2. `directionality.edge_sums_match_neuron_totals` is tautological for v1.2.x builds.** `src/brainir/ingest/manc.py:886-887, 898` set
`n_downstream`/`n_upstream` and `out_all`/`in_all` from the same query, so `common.py:528-533` compares a quantity with itself. The
real cross-check, `cross_source.snapshot_synapse_counts` (`manc.py:823-840`), is INFO-only although it is exact for v1.2.3
(23,665/23,665 on syn_pre/syn_post/syn_downstream) and for v1.2.1 on the unfiltered PreSyn/PostSyn. Fix: for v1.2.x make the
applicable snapshot comparison a PASS/WARN check with expected fraction 1.0 and skip (or relabel as "derived consistency") the
edge-sum check.

**M3. No duplicate-synapse check on the v1.2 partner table.** goal2 WS3 lists "duplicate synapses". `scan_partners_v12`
(`manc.py:740-747`) counts rows but never checks `count(*) - count(DISTINCT (x_pre, y_pre, z_pre, x_post, y_post, z_post)) = 0`;
duplicated rows would double-count. v1.0 is covered indirectly by `synapses.total_pairs_equal_weight_hr`. Fix: add the DISTINCT check
(cheap in DuckDB) as a FAIL-level check.

**M4. NT carry-over by body ID has no in-pipeline "same body" check.** `assemble_neurons_v12` (`manc.py:848-855`) reports only
`absent_from_v1_0` (0) and body-vs-celltype agreement (91.5 %). A v1.2 body that kept its ID through a merge/split would inherit a
stale prediction. External evidence exists (LOG D25: the paper's v1.2.1 table has `predictedNtProb` identical to v1.0 for all 4604
bodies) but the build does not know it. Fix: compare the v1.0 property export's `pre`/`post` with the recomputed v1.2 counts per body
and report the fraction changing by > 10 % (quantifies "light edit"); longer term, recompute body-level NT for v1.2 bodies from the
per-T-bar probabilities in `Neuprint_Synapses_manc_v1.ftr` (registered as optional `neuprint_synapses`,
`registry.py:413-419`) matched by T-bar coordinate, turning a carried label into a recomputed prediction.

**M5. `release.date` of the v1.2.x builds is the segmentation date.** `manifest.py:191` uses `facts.release_date` = 2024-03-11
(`registry.py:308`) for both v1.2.1 (annotations 2024-09-27) and v1.2.3 (2025-10-26); `DatasetVersion.release_date` inherits it.
Fix: per-build date = annotation snapshot date; keep the segmentation date as `segmentation_release_date`.

**M6. WARN explanations live only in the LOG.** The two v1.0 synapse WARNs (`synapses.recomputed_edge_neuropils` 1/1 pair,
`synapses.recomputed_neuron_totals` upstream 2) are explained in `research/LOG.md` §3.16 but neither the validation report nor the
manifest's `fail_and_warn_checks` carries the explanation or an "unresolved" marker. The stale-hierarchy WARN is self-explaining.
Fix: add `known_issues: [{check_id, explanation, status}]` to build_info/manifest.

**M7. goal2 WS1 record items missing from the manifest.** "Relationship to the version used in the paper" and "known caveats" are in
LOG §3.11–3.16 and the benchmark docs, not in `data/manifests/*.manifest.json`; raw JSON snapshots are profiled as `{"format": "json"}`
only (`manifest.py:142-143`; body counts/property lists are in the validation report). Fix: add `release.relationship_to_publications`
to the registry facts (e.g. Marin et al. 2024 = manc:v1.2.1, Cheong et al. VOR = manc:v1.2.3, the benchmark paper's networks =
v1.2.1 / v1.2.3 per LOG D21) and a snapshot profile (ids, properties).

**M8. Placeholder 'TBD' handled differently across MANC builds.** v1.0 nulls class 'TBD' (`manc.py:226`, 61 bodies) while
`load_snapshot` applies `NULL_STRINGS` to label/string properties only, not to tags (`manc.py:695-700` vs `:704`), so v1.2.x keep
`super_class` 'TBD' (83) / 'Sensory_TBD' (58) → `role_class` 'unknown' vs None. Fix: keep 'TBD' verbatim in both (a curated
"to be determined" is information, distinct from absent) and let `role_class_for` map it; document in DEFINITIONS.

**M9. `n_pre` semantics differ by build and disagree with the column description.** v1.0 `n_pre` = neuPrint `pre` (T-bars above the
detector threshold, partner-independent); v1.2.x `n_pre` = T-bars with >= 1 counted PSD (`manc.py:766`), which equals the v1.2.3
snapshot's `syn_pre` but not `tables.py:108` ("T-bars with confidence >= threshold"). `neuron_neuropils.n_pre` sums exceed
`neurons.n_pre` for 9,189 (v1.2.1) / 9,140 (v1.2.3) neurons by design (T-bar counted once per PSD ROI), documented in
`DEFINITIONS_V12["neuron_neuropils.n_pre"]` but not in the column metadata (`tables.py:187`). Fix: mention per-build semantics in the
column descriptions or add `column_caveats` to the manifest.

**M10. Citation drift.** `registry.py:275-277` (`paper_premotor`) carries the 2024 reviewed-preprint title with the 2026 VOR date; the
VOR title differs (`research/manc_release_notes.md` §1.3 already recommends the update).

**M11. Test gaps (fixture/tests).** No MANC invalid-input tests (`tests/test_invalid_inputs.py` is MaleCNS-only): duplicate snapshot
bodyId (critical abort), unknown `roi_post` (should FAIL `referential.partner_rois_are_primary`), snapshot body absent from the partner
table, v1.0 Meta tag mismatch inside a v1.2 build. Synthetic determinism covers v1.2.3 only (`tests/test_ingest_manc_synthetic.py:173-177`).
The fixture never exercises: a v1.2 body absent from v1.0 (`absent_from_v1_0` is always 0, so the null carry-over path is untested),
the export's `<unspecified>` string marker (fixture uses null), multi-valued tags ('|' join), side 'BIL', v1.2.1-vs-v1.2.3 membership
differences, or the v1.2.1 PreSyn/PostSyn "unfiltered == 1.0 / rule < 1.0" assertion (only v1.2.3 asserted, `:157-158`).

**M12. Leakage hygiene (location only; Review D's domain, recorded because I hit it).** `PHASE0_REPORT.md` contains 11 distinct
answer-key tokens. Its DNg100 section is declared answer-bearing in `benchmarks/dng100_walking_cpg/README.md:26`, but `CLAUDE.md:4,105`
and `README.md:7` direct every new session to the file without that warning, and `tests/test_leakage_guard.py:42-43` (`CLEAN_DOCS`)
deliberately excludes it. `PHASE1_REPORT.md`, `research/manc_release_notes.md`, `research/cross_connectome_mapping.md`, `docs/`,
`data/manifests/`, `src/` and the acquisition logs are clean. Fix: move the answer-bearing section into the benchmark directory or
add the warning next to the pointers.

### Notes

- N1. `tests/test_provenance.py:32` asserts `remote_path.startswith(version_prefix)`; `MANC_V1_2.version_prefix == ""`
  (`registry.py:447`), so the "no cross-version mixing" assertion is vacuous for that entry — by design it mixes objects from 2024-03,
  2024-09 and 2025-10. Consider asserting the explicit object list instead.
- N2. `brainir acquire --dataset manc --version v1.2.1` resolves through `get_source` to raw `manc:v1.2` (`cli.py:36-38`) without
  printing the resolution; the log correctly says `v1.2`. Not a substitution (correct raw), but say so on stdout.
- N3. Raw immutability is the Windows read-only attribute (`acquire.py:203`): a guard against accidents, not tampering (see M1).
- N4. `is_traced` and `side` are labelled `derived_anatomy` although derived from curated annotations (`tables.py:93, 102`); the
  `EvidenceKind` set has no "derived from curated" kind. Harmless, but a `DERIVED_ANNOTATION` kind would be more honest.
- N5. The v1.2.1 neuron table contains 337 bodies with class 'glia' (15 in v1.2.3; 7 'Glia' in v1.0) under "neuron = body in the
  snapshot". Consistent with the stated definition; downstream analyses must filter `role_class == 'glia'`.
- N6. Numbers reconciled while reviewing: LOG §3.15 says "22 bodies typed only in v1.2.3", `research/manc_release_notes.md` §3.7 says
  "119 typed only in v1.2.3", and my recount over the processed tables gives 29 bodies present only in v1.2.3 and 0 bodies typed only
  in v1.2.3 among the 23,636 shared bodies ('~' → null). Three different statements for one fact; pick one definition and state it.
- N7. Positive cross-checks not in the validation reports but worth recording: v1.2.1 build class counts 1328 DN / 5927 SN / 535 SA /
  13,060 IN / 1862 AN vs Marin et al. 1328 / 5927 / 535 / 13,060 / 1865; motor neurons 737 (v1.2.1) and 733 (v1.2.3) — exactly the
  two counts Cheong et al. print; `super_class == motor_neuron & sub_class == 'fl'` = 144 in v1.2.1 (CLAUDE.md fact confirmed), 142 in
  v1.2.3.

## 3. Checklist — goal2 requirements in scope

| Requirement (goal2) | Status | Evidence / gap |
|---|---|---|
| WS1 identify the paper's MANC version; releases differ; IDs/annotations changed | pass | LOG D21/§3.11–3.15; release notes §3.7; membership and type diffs recounted here (N6) |
| WS1 exact release used when obtainable; else labelled reconstruction | pass (caveat) | No bulk export for v1.2.x; rebuild from the public partner table + snapshot; neuPrint state identity unverifiable without login (A4) |
| WS1 never silently substitute versions | fail (API) / pass (CLI) | A2: `IngestConfig(source=MANC_V1_0, build_version="v1.2.1")` builds and labels without error |
| WS1 record: official name, exact version, official source, acquisition method, checksums, raw sizes | pass | manifests `acquisition.files[*]` (generation, CRC32C, MD5, SHA-256, size, `$DATA/` paths) |
| WS1 record: release date | partial | v1.2.x `release.date` = segmentation date (M5) |
| WS1 record: schemas | partial | feather inputs profiled; JSON snapshots not (M7); processed schemas complete |
| WS1 record: neuron/connection/synapse counts, annotation version | pass | `graph_statistics`, `release.annotation_snapshot` |
| WS1 record: known caveats; relationship to the paper's version | partial | in LOG/benchmark docs, not in the manifest (M6, M7) |
| WS1 record: citation/license | pass (minor) | CC-BY statement verified; one stale paper title (M10) |
| WS1 reuse Phase 0 schema; adapter architecture; no fork | pass | schema 0.2.0, `ingest/common.py` + two adapters, MaleCNS content unchanged (LOG D22) |
| WS1 `(dataset, version, source_id)` identity; source IDs preserved | pass | verified in parquet: 0 uid mismatches, int64 IDs, version uniform per build |
| WS1 do not normalise away annotations | pass (minor) | verbatim copy in `neuron_annotations_source`; class spaces→underscores documented; 'TBD' handled inconsistently (M8) |
| WS2 field audit (map / transform / absent / prediction vs observation) | pass | `DEFINITIONS_V10/V12`, `coverage.annotation_fields`, `docs/schema.md` |
| WS2 explicit evidence typing; no silent conversion | pass (note) | column `evidence` metadata; NT = ML; sign on demand; model params absent; N4 |
| WS2 general schema extension; versioning | pass | nullable `is_traced`, NT 'unknown', side 'B', `brainir.role.v1`; schema bumped 0.2.0 |
| WS2 transformations reproducible | pass (v1.2.x) / unverifiable (v1.0 builds) | A1: fingerprints of `manc:v1.0` and `male-cns:v1.0` manifests ≠ HEAD; not rebuilt here |
| WS3 source checksums | pass (acquisition) / partial (ingest) | M1: ingest checks recorded digests + size only |
| WS3 row counts, uniqueness, neuron IDs, edge endpoints, duplicate edges | pass | validation reports; v1.2 edges unique by construction (GROUP BY) |
| WS3 duplicate synapses | partial | v1.0 indirect (pairs == weightHR); v1.2 unchecked (M3) |
| WS3 null handling, annotation joins, data types, impossible values, referential integrity | pass | placeholders counted; cross_source checks; schema conformance; no negative / hp>weight |
| WS3 directionality | pass (v1.0) / vacuous (v1.2.x) | M2 |
| WS3 synapse aggregation | pass | v1.0 sampled recount incl. HP float32 semantics; v1.2 recount tests (`tests/test_real_data.py:121-141`) |
| WS3 autapses, neuropil labels, NT fields, evidence provenance | pass | flagged/kept (3 / 36 / 36 edges); `partner_rois_are_primary`; vocab/range/argmax checks |
| WS3 sample records vs official source | pass | `tests/test_real_data.py` (200 sampled edges per build vs raw tables); 300-neuron synapse recount |
| WS3 reconstruct published statistics | pass | Meta totals; class counts (N7); paper matrices reproduced exactly (LOG §3.11, not re-run here) |
| WS3 multiple independent builds; determinism; non-semantic metadata separated | pass (partly unverified) | LOG §10 second builds byte-identical (not re-verified); synthetic determinism v1.2.3 only (M11); timings kept out of parquet |
| WS29 MANC tests: schema, ingestion, checksums, determinism, query API | pass | 13 MANC fixture tests; offline pin/verify tests; graph test |
| WS29 dataset version isolation | partial | uid/version checks exist; no refusal test for foreign `build_version` (A2) |
| Acceptance 1 Phase 0 reproducible | pass (caveat) | tests pass; `male-cns:v1.0` manifest fingerprint ≠ HEAD (A1) |
| Acceptance 2 exact benchmark version identified | pass | v1.2.1 (front leg) / v1.2.3 (full VNC), LOG D21 |
| Acceptance 3 acquired automatically | pass | `brainir acquire`, 29 MANC files, `pin_problems: []` |
| Acceptance 4 checksums/provenance recorded | pass (minor) | complete; two mislabelled/inferred fields (A4) |
| Acceptance 5 canonical schema | pass | schema conformance PASS for all five tables in all builds |
| Acceptance 6 validation passes | pass | 0 FAIL in all three builds; 3 + 1 + 1 WARN, all explained (two only in LOG, M6) |
| Rule 1 evidence separation; `synapse_count` not strength | pass | column metadata and descriptions; `nt_consensus`/`nt_literature_label` null for MANC (no source consensus) |
| Rule 4 no absolute paths / tokens in provenance | pass | grep of manifests, validation reports, acquisition logs, build_info: none (`$DATA/`, `$REPO/` placeholders) |

## 4. What I ran, and what I could not verify

Ran (all read-only with respect to the repository and `data/`):
- `uv run --no-sync pytest -m "not real_data" -q` → 358 passed, 18 deselected, 73 s (includes the leakage guard and the MANC fixture tests).
- A dump of the three MANC manifests and both acquisition logs (schema version, definitions, count_rule, acquisition records,
  secondary sources, warn/fail lists, git/fingerprint, environment) and a grep of manifests/logs/build_info for absolute paths and
  secrets (none; the only match for "modal" was the annotation column `modality`).
- A parquet sanity script over `data/processed/manc/{v1.0,v1.2.1,v1.2.3}` (version labels, uid consistency, zero-weight edges, hp <= w,
  edge sums vs per-neuron totals, neuron_neuropils sums vs `n_pre`/`n_post`, NT column consistency, class distributions, sub_class 'fl'
  counts, v1.2.1 vs v1.2.3 membership/type diffs, v1.2.x bodies absent from the v1.0 neuron table: 706 / 221 — all present in the
  v1.0 property export).
- A version-label probe on the synthetic fixture in a temporary directory (A2), a code-fingerprint comparison of the committed manifests
  against `_code_fingerprint()` of the working tree (A1), `git log` of the pipeline files, and a token scan of non-answer locations
  using the guard's token list (M12; only locations reported).

Not run / could not verify:
- No acquisition, no ingestion, no real-data tests, no answer-key reproduction scripts (per brief; data directory shared with running
  jobs). Therefore: byte-identity of second builds (LOG §10), exact reproduction of the paper's matrices (LOG §3.11) and whether the
  current `manc.py` reproduces the committed `manc:v1.0` parquet (A1) are taken from the LOG, not re-verified.
- The neuPrint manc:v1.2.1 / v1.2.3 Meta thresholds and annotation state (login required) — the correspondence of the public
  snapshots to the neuPrint datasets remains an inference (A4), supported by flyem-snapshot's documentation and the paper-table
  agreement recorded in LOG D21.
- Correctness of the NT carry-over for bodies edited between v1.0 and v1.2 beyond the evidence in LOG D25 (M4).
- The four bodies whose types disagree between the paper's v1.2.1 table and the v1.2.1 snapshot (LOG D21) — unexplained in the LOG.
