# Review E — MaleCNS <-> MANC cross-connectome mapping layer and its use

Date: 2026-09-23. Reviewer: independent (read-only). Scope: `src/brainir/mapping.py`, `src/brainir/schema/vocab.py`
(`brainir.role.v1`), `src/brainir/cli.py` (`mapping build|lookup`), `tests/test_mapping.py`, the two committed summaries,
`research/cross_connectome_mapping.md`, LOG D27/D35/D39, `benchmarks/dng100_walking_cpg/cross_connectome_eval.py` (+ its
n = 8 results) and the `cross_connectome` family of `benchmarks/dng100/evaluator/evaluate.py`. This report names no
published interneuron type or body id.

## 1. Verdict

The mapping layer does what `goal2.md` WS4 asks at the level of a candidate table: one row per (MaleCNS neuron, MANC
candidate) keyed by `neuron_uid`, five method-based `mapping_kind`s in a fixed priority, a two-valued `evidence_kind`,
a uniqueness `confidence`, an integer `ambiguity`, per-field consistency flags, dataset manifests with `matches_build`,
and a deterministic canonical writer. No row asserts identity, the impossibility of "exact identity" across two animals
is stated in code, summary and report, and the code has no special case for the benchmark circuit (the rules are
population-wide and the leakage guard passes). Every number in the two committed summaries equals what I recomputed
from the parquets, and all but three figures in the prose reconcile. The weaknesses are semantic rather than
structural: `confidence = high` is attached to 4,028 body matches (21.7 %) whose annotated MANC type and MaleCNS type
both differ from the body's current type in the snapshot (six of them are now classed glia) and that disagreement is
only recoverable from free-text `notes`; the reverse direction reuses forward-only `confidence`/`ambiguity` and has no
"unmatched" representation; the evaluator's `cross_connectome` family scores every correspondence claim outside the
oracle core as wrong; the role rule sends 26 VNC neurons (`vnc_tbc`) out of scope while the report calls them
brain-only; and the report's side-semantics explanation for descending neurons is an untested inference presented as
checked. None of this is a blocker for Phase 1; the fixes below are small.

## 2. Findings (ranked)

### Major

**E-1. `confidence = "high"` is a uniqueness label, but readers (and `cross_connectome_eval.py`) use it as a
correctness label.** `src/brainir/mapping.py:77-78` defines confidence as "Uniqueness label", and `:283` assigns `high`
to every `curated_body_match` regardless of what else the row says. On the real tables 4,028 (v1.2.1) / 4,009 (v1.2.3)
of the 18,555 / 18,542 `high` rows have `manc_type != b.cell_type`, and in 4,022 / 4,003 of those the MaleCNS
`cell_type` differs as well; 21 / 12 point at bodies whose MANC class is TBD and 6 / 4 at bodies classed `glia`
(`role_consistent = false`). Those facts live only in the free-text `notes` column (`:278-282`), which `_summary` then
re-parses by substring (`:366-371`). A consumer filtering `confidence == "high"` (what `cross_connectome_eval.py:117-118`
does) cannot tell a corroborated body match from one the snapshot contradicts. *Fix:* add two structured boolean
columns (`manc_type_consistent`, `a_type_consistent`, three-valued like the existing flags) and compute the summary from
them instead of the notes; either (a) rename `confidence` to `uniqueness`, or (b) keep the name and demote body matches
whose B candidate is glia/TBD, or whose annotated and own types both disagree with the snapshot, to `medium`, recording
the reason. Document in `research/cross_connectome_mapping.md` §1 that `confidence` does not encode agreement.

**E-2. Evaluator `cross_connectome`: claims about neurons outside the oracle core are scored as wrong, and the claim
`basis` is ignored.** `benchmarks/dng100/evaluator/evaluate.py:281` sets `consistent = (la is not None and la == lb)`
and `:286` divides by all claims, so a method that correctly pairs, say, 40 non-core neurons (curated body pairs it
found by structure) plus the 7 core ones gets accuracy 7/47. `CrossConnectomeClaim.basis`
(`src/brainir/benchmark/prediction.py:62`) is never read. Should the evaluator use the mapping table? *Recommendation:*
not the live parquet (git-ignored, 450 k rows, not in `BENCHMARK_LOCK.json`, and it would make the frozen evaluator
depend on a rebuildable artefact). Instead: (1) grade `claimed_correspondence_accuracy` only over claims whose two
endpoints both carry oracle labels and report `n_ungradeable_by_oracle` separately; (2) at freeze time export a small
`cross_connectome_reference.json` restricted to the bundles' node lists (both directions; `mapping_kind`,
`confidence`, `evidence_kind`, `side_consistent`, `role_consistent` per pair), hash it into the lock, and report a
second, clearly separate number, `agreement_with_curated_pairs`, never merged with the oracle metric (agreement with
curation is not agreement with the paper); (3) report both numbers per `basis`. Note the tier-A limit: tokens are per
neuron (`src/brainir/benchmark/bundle.py:94-95`), so a tier-A method can only claim correspondences structurally; the
reference file would have to be keyed by positional ids through `public_to_real` exactly as `evaluate.py:327-336`
already does for claims.

### Minor

**E-3. Reverse direction (B -> A) is served by the forward table but its semantics are not symmetric.**
`reverse_lookup` (`mapping.py:466-469`) returns forward rows, so `confidence`/`ambiguity` describe the A neuron, not the
B neuron: the 412 MANC bodies named by two MaleCNS neurons each appear in two rows both saying `ambiguity = 1, high`.
A B neuron with no row (1,132 in v1.2.1) is indistinguishable from a non-existent id, and there is no B-side
`same_role_only`/`unmatched`. `cross_connectome_eval.py:75,78` works around the first point with
`unique_high_confidence`. *Fix:* add `b_ambiguity` (number of A rows of the same kind naming this B neuron) at build
time, state in the schema descriptions (`:77-80`) that `confidence`/`ambiguity` are A -> B, and have `reverse_lookup`
return a typed "no row" result (or add B-side unmatched rows) so `goal2.md` item 21 ("both directions") holds with the
same vocabulary in both directions.

**E-4. Role rule: `vnc_tbc` -> `unknown` removes 26 VNC neurons from scope, and the report mislabels them.**
`vocab.py:166-168` strips `_tbc` and looks up `vnc`, which is absent from `_ROLE_MAP`, so all 38 MaleCNS `vnc_tbc`
neurons become `unknown`; 12 stay in scope only through a curated annotation, 26 are counted in
`summary.scope.out_of_scope`. `research/cross_connectome_mapping.md:54-57` then says the 142,564 out-of-scope neurons
"are brain-only and cannot have a counterpart in a VNC volume" — false for those 26 (the release places them in the
VNC). *Fix:* map `vnc` (base of `vnc_tbc`) to a VNC role — cleanest is a new `vnc_unknown` in `ROLE_CLASSES` and
`VNC_ROLES` — and correct the sentence. Related, lower priority: MANC `Sensory_TBD` (58 in v1.2.1) and
`Interneuron_TBD` also collapse to `unknown` although the class word is known; consider `Sensory_TBD -> vnc_sensory`
(a judgement call — record it in `_ROLE_MAP` either way). Otherwise the normalisation is correct on the real builds:
every MaleCNS superclass and every MANC class label in v1.0/v1.2.1/v1.2.3 lands where the rule intends (`vnc_motor` and
`motor_neuron` both -> `vnc_motor`; `neck_motor_neuron` in the map is unused, MANC neck MNs are `motor_neuron`).

**E-5. Three prose figures in `research/cross_connectome_mapping.md` do not reproduce from the tables.**
(a) `:80-81` "only 113 of these pairs share an A cell type": the table gives 88 pairs with equal non-null
`a_cell_type`, 103 with equal `manc_type`, 104 with either — 113 matches none. (b) `:127-129` "in 661 the name exists
in neither snapshot": 661 is the number absent from v1.2.1; 21 of those exist in v1.2.3, so 640 are absent from both.
(c) `:119-120` and caveat 4 (`:147-149`) "MANC ... has no `sensory_descending` class": true for v1.2.1, false for
v1.2.3, which has 6 such neurons; 6 of the 12 MaleCNS `sensory_descending` neurons are body-matched to them with
`role_consistent = true`, the other 6 to `descending`. *Fix:* correct the three sentences (and D35's "side agreement
97 %" should say "97 % of the 15,558 comparable; v1.2.1 has no root side at all, so all 1,315 descending and 1,128
sensory matches are not comparable there").

**E-6. The side-semantics explanation for descending neurons is an inference, presented as checked.** `:108` says
"each point was checked on the tables, not assumed", then `:113-117` asserts that the 583 descending disagreements in
v1.2.3 arise because MaleCNS reports the brain soma side and MANC the root side, "so neurons that cross the midline
before entering the VNC carry opposite labels" and "`side_consistent = false` is therefore not an error flag". The
table can show the first half (MaleCNS descending `side_basis` is soma for 1,314/1,316; MANC v1.2.3 is root for all
1,322) but not the second: MaleCNS has no `root_side` for any of the 1,285 body-matched descending neurons, so
midline crossing was not tested. 583/1,285 = 45 % is high enough to deserve a test. *Fix:* reword to "consistent
with"; test it with what BrainIR has — the side of each matched DN's VNC synapses in the MaleCNS synapse table versus
the MANC root side — and only then call the flag non-diagnostic. Positive evidence that the L/R conventions agree
between datasets exists and should be cited: soma-bearing intrinsic neurons agree on side in 97.8 % of body matches.

**E-7. Tests never exercise `ambiguity >= 2`, `a_side` unknown, `matches_build = true`, or rebuild determinism.**
The fixtures have one neuron per type, so every `curated_type_match`/`same_type_name` row in
`tests/test_mapping.py` has `ambiguity == 1`; the multi-row `low` branch of `emit_candidates` (`mapping.py:262-267`),
the `ambiguity_by_mapping_kind` buckets 2 / 3–5 / >5, and a reverse lookup with several same-kind candidates are
untested. `_side_filter`'s `a_side is None` branch (`:198-199`) is untested (`:145` nulls a B side, not an A side).
`test_write_is_deterministic_and_round_trips` (`:209-221`) writes the same in-memory table twice, so it tests the
writer, not the claim in the report (`:178-180`) that "a rebuild from the same inputs is byte-identical".
*Fix:* add a second neuron of an existing type to the MANC fixture (same side and unknown side), null one A side,
assert `build_mapping` twice gives `.equals`, and cover `--limit`/`--out-dir` in the CLI test.

**E-8. `cross_connectome_eval.py` outputs and the D39 wording.** The claim "curated evidence restated, not derived"
is made in LOG D39 (`research/LOG.md:50`) and `PHASE1_REPORT.md:178-181`, and the JSON carries the summary's caveat
string, but the Markdown result (`results/cross_connectome_eval_n8.md`) has no such sentence — a reader of the table
sees eight `curated_body_match/high/1` rows and no statement of what that means. The functional-transfer test itself is
sound in design (source modal circuit -> mapped ids -> keep-only in the destination with the destination's own modal
circuit and intact network as references; the mapped and own circuits differ in their inhibitory member in both
directions, so the test is not a tautology), but: it has no null (keep-only of a role-matched random triple), so
"rhythm survives" is not yet attributable to the mapping; the destination stimulus is taken from the oracle
(`:105`), not mapped, which should be stated; n = 8 replicates while the script default is 32 and the report says
"[PENDING: final n]"; "different animals" appears only as "across animals/datasets" in the docstring. *Fix:* print the
caveat line and the mapping-table sha into the .md, add the role-matched null, map the stimulus through the table
(it maps 1:1, so the result is unchanged but the test becomes self-contained), and run the final n.

**E-9. CLI `mapping lookup` hides the epistemic columns and prints bare integer ids.** `cli.py:188-189` emits
`a_source_id`/`b_source_id` and omits `evidence_kind`, `method`, `a_uid`/`b_uid`, contrary to the module's own rule
that raw ids are not comparable across datasets (`mapping.py:71-72`). *Fix:* emit `a_uid`, `b_uid`, `evidence_kind`
(and `method` under `--json`, which already returns the selected columns only).

**E-10. The mapping table is not in the generated schema documentation.** `MAPPING` is a `TableSpec`
(`mapping.py:62-94`) but `scripts/gen_schema_docs.py` and `docs/schema.md` do not know it, so the columns, evidence
kinds and `mapping_schema_version` are documented only in the module docstring and the report. *Fix:* register it in
`gen_schema_docs.py` (rule 6 of `CLAUDE.md`).

**E-11. `research/cross_connectome_mapping.md` is not covered by the leakage guard.** It states (`:8-9`) that it
names no cell types or ids — I confirmed that by reading it — but `tests/test_leakage_guard.py:42-43` does not list it
(nor `data/manifests/mapping_*.summary.json`). *Fix:* add both to `CLEAN_DOCS`; the summaries contain only counts.

### Notes

- `evidence_kind = curated_annotation` for `curated_type_match` (`mapping.py:103-106`) is right at the type level but
  the (A neuron, B neuron) pairing of such a row is BrainIR's enumeration plus side filter; say so in the schema
  description (`:75-76`) so a row with `ambiguity = 30` is not read as a curated neuron pair.
- `a_side`/`b_side` carry `derived_anatomy` (`:83-84`), matching the neurons table where `side` is derived from
  `soma_side`/`root_side`; `a_role_class`/`b_role_class` carry `curated_annotation`, matching `vocab.py:123-125`
  ("relabeling, same evidence kind"); `a_nt` (`nt_consensus`) carries `ml_prediction`, matching `docs/schema.md:92`.
  Consistent.
- `soma_neuromere` is populated for 21,799 MaleCNS and ~15.8 k MANC neurons and is unused; a `neuromere_consistent`
  flag is cheap and would separate many same-type candidates of intrinsic/motor/ascending neurons (`goal2.md:422`
  asks for leg/body-region metadata).
- Duplicate note text `b.cell_type null; b.cell_type null` on 17 / 8 rows (`mapping.py:278-281` emits it twice).
- `MAPPING.primary_key` includes a nullable column; uniqueness holds by construction (one null-candidate row per A
  neuron) but is not asserted by a test.
- Integer-id coincidences: 0 rows have `a_source_id == b_source_id` in either table (the VNC-side MaleCNS ids and
  MANC ids do not overlap), so the documented hazard (`docs/schema.md:9`) does not bite here; the uid keys are still
  the right design.
- `cross_connectome_eval.py:5` calls the table "public"; it is derived, git-ignored data outside the bundles (tier B
  neurons carry no `manc_body_id`/`manc_type`: `bundle.py:137`). "Non-answer-bearing" is the accurate word.
- The uncommitted modification of `benchmarks/dng100/oracle/oracle.json` parses identically to HEAD at every key
  (formatting only); the cross-connectome pairs used by the eval are unchanged.

## 3. `goal2.md` WS4 / WS16 checklist

| requirement (`goal2.md`) | status | where / why |
|---|---|---|
| 1. exact neuron identity when meaningful | pass (explicitly not representable) | two animals: `mapping.py:3-4`, summary `rules.caveat`, report §1. Within-MANC identity (v1.2.1 <-> v1.2.3 same body ids) is handled by id stability (LOG D25), not by this table — worth one sentence in the report |
| 2. homologous neuron | pass with caveat | `curated_body_match` is the release's per-neuron match, labelled by method; the word "homologous" and a crosswalk from the five goal2 categories to `mapping_kind`/`confidence` are absent — add the crosswalk table to report §2 |
| 3. same named cell type | pass | `curated_type_match` (release's cross-dataset type) and `same_type_name` (verbatim, derived; fired 0 times on real data, exercised by tests) |
| 4. same inferred functional role | pass (coarse) | `same_role_only` on `brainir.role.v1`; NT/sign agreement only as a flag |
| 5. uncertain correspondence | pass | `confidence` low/none, `unmatched`; see E-1 for what `confidence` does not encode |
| do not collapse the categories | pass | `mapping_kind`, `confidence`, `evidence_kind`, `ambiguity` are separate columns; one kind per A neuron (verified: 0 neurons with two kinds) |
| record source / destination neuron | pass | `a_uid`, `b_uid` (`dataset:version:id`) |
| record cell type, method, evidence, confidence, ambiguity | pass | `a_/b_cell_type`, `method`, `evidence_kind`, `confidence`, `ambiguity` |
| record provenance | pass | parquet metadata (`a`, `b`, schema version), summary manifests with sha256 and `matches_build = true` for both builds, table sha256 |
| use official annotations | pass | `manc_body_id`, `manc_type`, `cell_type`, class, side |
| use published cross-dataset mappings | partial, deliberate | the release's annotations yes; the paper's own correspondence is answer-bearing and is kept in the oracle, compared only by `cross_connectome_eval.py` |
| use morphology when necessary | not used | stated as not provided (report §5.1); no morphology in BrainIR |
| use neuropil / arborization | not used | `soma_neuromere` available in both builds, unused (note above) |
| use connectivity signatures | not used | explicitly deferred (report §5.1) |
| use side / leg / body-region metadata | partial | side yes; neuromere / leg no |
| do not invent mappings from similar names | pass | verbatim equality only, lowest per-neuron rule, `derived_anatomy`, medium only when one same-side candidate |
| investigate official-vs-paper disagreements | pass | 22 % `manc_type` disagreement analysed (§4.2); all published pairs are among the candidates (eval) |
| machine-readable table + human-readable report | pass | parquet + `summary.json`; `research/cross_connectome_mapping.md` (three figures wrong, E-5) |
| item 21: MaleCNS -> MANC and MANC -> MaleCNS evaluation | pass with caveat | both directions run in `cross_connectome_eval.py`; reverse semantics asymmetric (E-3) |
| self-audit: "the MANC mapping is incorrect" | partially tested | correctness is checked only by annotation agreement (side/role/NT/type); no independent signal (connectivity); which MANC snapshot the release matched against is unverifiable and is stated as such |
| self-audit: "cross-connectome mapping is cherry-picked" | pass | rules are population-wide with no benchmark special case (code read; leakage guard passes); the core's 1:1 result is explained as curated, not derived (D39) |

## 4. What I ran

- `uv run --no-sync pytest -m "not real_data" -q`: 358 passed, 18 deselected, 66 s (includes `tests/test_mapping.py`,
  `tests/test_leakage_guard.py`).
- Two read-only scripts over `data/processed/mappings/male-cns_v1.0__manc_v1.2.{1,3}/neuron_mapping.parquet`, the
  committed and processed `summary.json`s and the `neurons.parquet` of `male-cns:v1.0`, `manc:v1.0/v1.2.1/v1.2.3`:
  sha256 of both parquets equals `summary.table.sha256`; committed summaries byte-equal the processed ones; rows and
  A-neurons per kind, confidence counts, ambiguity buckets, `curated_annotations`, `body_match_consistency` (side
  15,093/465/2,997; role 17,819/736; NT 16,139/1,500/916; type flags 13,940/4,028 and 12,287/5,941, and the v1.2.3
  counterparts), `type_name_coverage` and `b_coverage` all recomputed exactly; invariants (one kind per A neuron, body
  rows `ambiguity = 1`/`high`, medium rows `ambiguity = 1` and same side, uid prefixes, 0 integer-id coincidences, 412
  doubly-referenced bodies, max 2); prose figures 17/30, 4,399, 3,867/2,693, 1,060, 19,032, 197/190/78, 583, 1 body
  with a different known side across snapshots, 2,981/2,353/626, 3,367, 1,655, 3, and the role-disagreement
  composition — all reproduced; 113 and 661 not reproduced (E-5); `super_class -> role_class` tabulated for all four
  builds (E-4); `side_basis` per role (E-6); `soma_neuromere` coverage.
- Key-level comparison of the working-copy `oracle.json` against `HEAD` (no values printed): identical.
- No dataset or mapping rebuild, no simulation on real data, no file outside this report written.
