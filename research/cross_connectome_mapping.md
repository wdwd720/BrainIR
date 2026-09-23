# Cross-connectome neuron mapping: MaleCNS v1.0 → MANC v1.2.1 / v1.2.3

Date: 2026-09-23. Code: `src/brainir/mapping.py` (mapping schema 1.0.0); CLI `brainir mapping build|lookup`; tests
`tests/test_mapping.py` (synthetic fixtures only). Outputs (git-ignored): `data/processed/mappings/<a>__<b>/neuron_mapping.parquet`
+ `summary.json`; committed copies of the two summaries: `data/manifests/mapping_male-cns_v1.0__manc_v1.2.1.summary.json`
and `data/manifests/mapping_male-cns_v1.0__manc_v1.2.3.summary.json`.

This note describes the method and the numbers. It deliberately names no cell types and no neuron IDs: the mapping is
generic and must stay usable as an input to discovery code.

## 1. What the table is, and what it is not

MaleCNS (A) and MANC (B) are two different male flies. **No row of the table asserts that two neurons are the same
neuron.** A row states that one explicit comparison of annotations succeeded, and carries the epistemic status of that
comparison:

| column | meaning |
|---|---|
| `mapping_kind` | which rule produced the row (one of five categories, §2) |
| `method` | which fields were compared (short text, e.g. `a.manc_body_id == b.source_id`) |
| `evidence_kind` | `curated_annotation` when the row restates the A release's own cross-dataset annotation; `derived_anatomy` when BrainIR compared labels itself |
| `confidence` | `high` (curated body), `medium` (exactly one same-side candidate), `low` (several candidates or side unknown), `none` (no per-neuron candidate) |
| `ambiguity` | number of B candidates the rule produced for this A neuron (0 = unmatched) |
| `a_*` / `b_*`, `*_consistent` | the compared annotations side by side (cell type, side, role class, NT label) with a three-valued agreement flag (true / false / null = not comparable) |
| `notes` | rule details: side filtering, annotation disagreements, bodies referenced twice |

One row per (A neuron, B candidate) plus one row per in-scope A neuron without a candidate. Keys are `neuron_uid`s
(`dataset:version:id`); raw integer IDs are never comparable across datasets (MANC and MaleCNS share 19,344 integer
body IDs that denote different neurons, `docs/schema.md`). The same table serves the reverse direction B → A
(`reverse_lookup`, `brainir mapping lookup --b-id`): a B neuron may appear in several rows.

## 2. Rules (priority order per A neuron; the first rule with candidates wins)

| # | `mapping_kind` | condition | evidence | confidence |
|---|---|---|---|---|
| 1 | `curated_body_match` | A's `manc_body_id` is a neuron of B | curated_annotation | high |
| 2 | `curated_type_match` | A's `manc_type` is a B cell type; one row per B neuron of that type, same side when both sides known (unknown-side candidates kept) | curated_annotation | medium if exactly one same-side candidate, else low |
| 3 | `same_type_name` | A's `cell_type` equals a B `cell_type` verbatim (same side handling) | derived_anatomy | medium / low |
| 4 | `same_role_only` | only the role class (rule `brainir.role.v1`) is shared; `b_source_id` null, `ambiguity` = B neurons of that role | derived_anatomy | none |
| 5 | `unmatched` | nothing above (no B neuron shares even the role class) | derived_anatomy | none |

Side filtering: when A's side is known, candidates of the opposite side are dropped and candidates of unknown side are
kept; when nothing is left on the same side, all candidates are listed and the row says so. `nt_consistent` compares
MaleCNS `nt_consensus` with MANC `nt_body_prediction` and is null when either label is missing, `unclear` or `unknown`.

## 3. Scope

A neuron of A is in scope when its `role_class` is a VNC role (`descending`, `ascending`, `sensory_ascending`,
`sensory_descending`, `efferent`, `vnc_intrinsic`, `vnc_motor`, `vnc_sensory`) **or** it carries a curated MANC
annotation (`manc_body_id` or `manc_type`) whatever its role. The second clause keeps 38 neurons (22 endocrine,
12 unknown, 4 cb_intrinsic): the release's own annotation is evidence that they were matched, and a role
inconsistency is flagged in `role_consistent` rather than hidden.

Everything else (142,564 neurons: ol_intrinsic 89,403; cb_intrinsic 32,160; visual_projection 9,203; ol_sensory 6,098;
cb_sensory 4,882; visual_centrifugal 563; endocrine 122; cb_motor 107; unknown 26) is brain-only and cannot have a
counterpart in a VNC volume. **Choice:** these are counted in `summary.scope.out_of_scope` and not written as rows
(they would add 142k information-free rows to a 450k-row table). In scope: 24,136 A neurons.

## 4. Results

Both runs: A = `male-cns:v1.0` (166,700 neurons). B = `manc:v1.2.1` (24,143) and `manc:v1.2.3` (23,665). ~15 s each.

### 4.1 Coverage by rule (A neurons; rows in brackets where they differ)

| `mapping_kind` | vs v1.2.1 | vs v1.2.3 |
|---|---|---|
| curated_body_match | 18,555 | 18,542 |
| curated_type_match | 4,414 (430,236 rows) | 4,425 (223,667 rows) |
| same_type_name | 0 | 0 |
| same_role_only | 1,165 | 1,167 |
| unmatched | 2 | 2 |
| confidence high / medium / low / none | 18,555 / 78 / 4,336 / 1,167 | 18,542 / 95 / 4,330 / 1,169 |

Per role class (vs v1.2.1; body / type / role-only): vnc_intrinsic 12,603 / 494 / 64; vnc_sensory 1,507 / 3,839 /
1,060; ascending 1,827 / 18 / 1; descending 1,285 / 19 / 12; vnc_motor 673 / 29 / 6; sensory_ascending 517 / 10 / 12;
efferent 95 / 5 / 10; sensory_descending 12 / 0 / 0; endocrine 20 / 0 / 0 (+ 2 unmatched); unknown 12; cb_intrinsic 4.

- **Curated body annotations.** 18,572 in-scope A neurons carry a `manc_body_id`; 18,555 of those bodies are
  neurons of v1.2.1 and 18,542 of v1.2.3 (17 / 30 are absent: 12 / 21 sensory, 3 / 7 intrinsic, 2 / 2 ascending; they
  fall through to the type rule). 412 MANC bodies are referenced by two A neurons each (never more); only 113 of these
  pairs share an A cell type. The table keeps both rows and says so in `notes`.
- **Curated type matches** are dominated by sensory neurons (3,839 of 4,414). 4,399 of the 4,414 have no
  `manc_body_id` at all: the release matched them at type level only. Ambiguity is large (1 candidate: 83; 2: 126;
  3–5: 246; >5: 3,959), so only 78 reach `medium`. Against v1.2.1, 3,867 of these neurons had candidates of unknown
  side (that snapshot has no side for most sensory bodies); against v1.2.3, 2,693.
- **`same_type_name` fired for no neuron:** every in-scope A neuron whose `cell_type` exists verbatim in B (19,032)
  also carries a `manc_type` or `manc_body_id`. The release's annotation covers the shared name space completely; the
  rule stays as the fall-back for datasets without curated cross-references (exercised by the tests).
- **Role-only / unmatched.** 1,060 of the 1,165 role-only neurons are sensory (untyped, or typed with names absent
  from MANC); the 2 unmatched neurons are endocrine cells whose annotated MANC type exists in neither snapshot.
- **Type names.** In-scope A neurons use 4,202 cell types, of which 3,395 (v1.2.1) / 3,404 (v1.2.3) exist verbatim
  in B; B has 4,076 / 4,081 types. 1,053 in-scope A neurons are untyped.
- **B coverage (reverse direction).** v1.2.1: 23,011 of 24,143 B neurons appear in at least one row and 18,143 have a
  body match; 1,132 appear in no row (glia 331, intrinsic 279, sensory 198, unknown 177, descending 51, ascending 50,
  motor 38, sensory_ascending 6, efferent 2). v1.2.3: 22,867 of 23,665 in a row, 18,130 with a body match, 798 in none.

### 4.2 Consistency among curated body matches

| agreement (n = 18,555 / 18,542) | consistent | inconsistent | not comparable | rate |
|---|---|---|---|---|
| side, vs v1.2.1 | 15,093 | 465 | 2,997 | 97.0 % |
| side, vs v1.2.3 | 17,437 | 1,089 | 16 | 94.1 % |
| role class, vs v1.2.1 / v1.2.3 | 17,819 / 17,825 | 736 / 717 | 0 | 96.0 % / 96.1 % |
| NT label, vs v1.2.1 / v1.2.3 | 16,139 / 16,138 | 1,500 / 1,494 | 916 / 910 | 91.5 % |
| `manc_type` == B `cell_type` | 13,940 / 13,957 | 4,028 / 4,009 | 587 / 576 | 77.6 % / 77.7 % |
| A `cell_type` == B `cell_type` | 12,287 / 12,304 | 5,941 / 5,922 | 327 / 316 | 67.4 % / 67.5 % |

Interpretation (each point was checked on the tables, not assumed):

- **Side.** The v1.2.1 snapshot has no side for 2,985 matched bodies (1,315 descending, 1,128 sensory, 538
  sensory-ascending). v1.2.3 supplies sides for 2,981 of them: 2,353 agree with MaleCNS, 626 do not, and 583 of the
  1,089 v1.2.3 inconsistencies are descending neurons. Only **one** body has a different known side in the two MANC
  snapshots. So the drop from 97.0 % to 94.1 % is not annotation churn but a **semantic difference**: MaleCNS `side`
  of a descending neuron is its (brain) soma side; MANC has no soma for these cells and reports the entry/root side,
  so neurons that cross the midline before entering the VNC carry opposite labels. `side_consistent = false` is
  therefore not an error flag for descending neurons. Among inconsistencies L↔R dominate (v1.2.1: 197 + 190;
  midline vs lateral: 78).
- **Role class.** 295 disagreements are sensory in MaleCNS vs intrinsic in MANC; intrinsic↔motor 102,
  intrinsic↔ascending 85, sensory→ascending 35, sensory→sensory_ascending 23. All 12 MaleCNS `sensory_descending`
  neurons are `descending` in MANC, whose class vocabulary has no such class (vocabulary, not disagreement).
- **NT.** The two labels come from different classifiers at different levels: MaleCNS `nt_consensus` is a
  type-level prediction with expert overrides; MANC `nt_body_prediction` is the body-level v1.0 label carried into the
  v1.2.x builds (LOG D25, §3.12). Disagreements: ACh→Glu 452, GABA→Glu 447, ACh→GABA 302, GABA→ACh 122, Glu→GABA 65,
  Glu→ACh 54, plus modulatory MaleCNS labels (octopamine 37, serotonin 9) against fast-transmitter MANC labels. Not
  comparable: 808 MaleCNS `unclear`/null, 164 MANC `unknown`/null. A 91.5 % agreement between independent predictors is
  informative about both, not a validation of either.
- **Type names.** `manc_type` disagrees with the v1.2.x type of the annotated body for 22 % of body matches. In
  3,367 of the 4,028 cases the annotated name still exists as a type in B, i.e. *the body* carries a different type
  in v1.2.x; in 661 the name exists in neither snapshot (renamed or retired). Conversely, in 1,655 body matches
  `manc_type` equals the B type but MaleCNS's own consensus `cell_type` differs (MaleCNS renamed relative to MANC).
  Only 3 body matches have `manc_type` ≠ B type while A `cell_type` = B type. Between the two MANC snapshots, 28 matched
  bodies change type.

## 5. Caveats

1. **Different animals.** Every row compares annotations; homology is a hypothesis the table helps form, and
   connectivity-based validation (partner profiles of matched pairs) is the natural next step, not something the
   table provides.
2. **Provenance of `manc_body_id` / `manc_type`.** They are the MaleCNS v1.0 release's own annotation columns
   (`mancBodyid`, `mancType`; evidence kind `curated_annotation`, `docs/schema.md`). The release documents the matching
   only as cross-dataset type matching for the NT ground-truth transfer; **which MANC version or snapshot the bodies
   were matched against is not stated and remains unverified.** The 22 % `manc_type` disagreement and the 17 / 30
   absent bodies say it was neither v1.2.1 nor v1.2.3 exactly. MANC body IDs are stable within the v1.x segmentation
   lineage (every v1.2.x neuron exists in v1.0 by ID, LOG D25), so an ID refers to the same segment across MANC
   builds; whether it is still a neuron in a given snapshot is what rule 1 checks.
3. **Integer IDs never cross datasets.** Use `a_uid` / `b_uid`; `a_source_id == b_source_id` is a coincidence.
4. **Side semantics differ** for neurons without a soma in the VNC (§4.2). **Class vocabularies differ**
   (`role_class` is a relabeling; MANC has no `sensory_descending`). **NT labels differ in origin, level and
   version** (§4.2).
5. **Sensory populations are ambiguous by construction**: many neurons per type and per side; a `curated_type_match`
   with `ambiguity` 30 is a population statement, and the v1.2.1 snapshot's missing sides make it worse there.
6. **Snapshot dependence.** v1.2.1 and v1.2.3 differ in membership (24,143 vs 23,665), types (28 matched bodies
   retyped) and side coverage; run the mapping against the build you analyse.
7. **Scope rule.** 38 non-VNC-role neurons are in scope through annotations only; brain-only neurons are a summary
   count, not rows (§3).

## 6. Reproduction and checksums

```
uv run brainir mapping build --a male-cns:v1.0 --b manc:v1.2.1
uv run brainir mapping build --a male-cns:v1.0 --b manc:v1.2.3
uv run brainir mapping lookup --a-id <A id>            # candidates of one A neuron
uv run brainir mapping lookup --b-id <B id> --b manc:v1.2.3   # reverse direction
uv run pytest tests/test_mapping.py -q                 # 10 tests, synthetic fixtures, ~10 s
```

Both builds were verified against their committed manifests before mapping (`summary.a.manifest.matches_build` and
`summary.b.manifest.matches_build` are true: the manifest's `neurons.parquet` sha256 equals the build's).

| artefact | rows | sha256 |
|---|---|---|
| `$DATA/processed/mappings/male-cns_v1.0__manc_v1.2.1/neuron_mapping.parquet` | 449,958 | `e0e18526d45f3960b7c48757beedab1e00ddaca2fd145e44e83e8734c49cc541` |
| `$DATA/processed/mappings/male-cns_v1.0__manc_v1.2.3/neuron_mapping.parquet` | 243,378 | `67d513525581631132441c48d12605db562cef4e551d05c4d650ea341811846b` |
| `$REPO/data/manifests/male-cns_v1.0.manifest.json` (A build) | | `84ccb2413bda05bd59b92043a7cddfb68dd7524c910ebd7c5f298b0434d7370a` |
| `$REPO/data/manifests/manc_v1.2.1.manifest.json` (B build) | | `cea1472cfecc8196475316c9f7e1559b175a57abfad00e81d5c28ee4f1e0a580` |
| `$REPO/data/manifests/manc_v1.2.3.manifest.json` (B build) | | `ca8962d5ed1153ff0916ddb8813c4bc8fe828c9b75fd6365617b7bea0a1466f4` |

The Parquet files are written with the canonical writer (sorted by `(a_source_id, b_source_id)`, zstd-3, normalised
dictionaries), so a rebuild from the same inputs is byte-identical (tested on the fixtures); each file's metadata
records `brainir_mapping_schema_version`, `a` and `b`.
