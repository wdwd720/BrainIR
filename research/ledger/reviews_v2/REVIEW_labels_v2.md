Verdict: usable with caveats

# Blind review of labels v2

Scope: everything under `research/ledger/labels_v2/` (416 final records), the rulebook (PREREG v2 Part L, S5.2-5), `kit_v2/PROTOCOL.md` and prompts, `IMPLEMENTATION_v2.md`, LOG L49-L61. I opened no prediction, gate, results or arms file and no dedicated source, and I made no repository change. All reproductions ran read-only with the locked code.

## Process findings

- **Audit (L3).** There are 62 rooms, 62 manifests and 62 rows in `transcript_audit.json`. The audit (18:23:33) is newer than the newest session log (18:23:08). Every session ended `success` on Opus 5.5 only (`sessions/_status.json`). My own scan of all transcripts (909 fetches, 2,546 file-tool calls) found no banned host, no forbidden token and no successful access outside a room, apart from the known breach.
- **Breach.** `search-bydriverline-r2` is kind 3: an E-utilities `esummary` request whose ID list includes the dedicated PMC number. Its leads were dropped: round 2 recomputes to 18 new units from the other three sessions, and its one unique DOI is not in `work/registry.csv`. It is not a contributing session (S5.2).
- **Reassignment and replacement.** None was needed. Every assigned source of every task kind has a valid disposition, no file-only reader marked a source unreachable, and there are no `-a`, `-r` or `-w` specs.
- **Recall (L9).** Round 1 added 34 new units of 151 (22.5 %) and round 2 added 18 of 187 (9.6 %), so the searches stopped. I reproduced both figures.
- **Second reading.** No word from the L8 list remains in `source_locator` or `stimulation` in any of the 291 `experiments_to_label.csv` rows. Inflected forms outside the fixed list remain, such as "steered" and "flying". Each Phase A snapshot is stamped at its Phase B start, and the code copies the quotes only after the snapshot. `phase_a_changed_after_quotes` is empty for all 12 second readers and for atlas coder B.
- **Adjudication.** `disagreed_unadjudicated` = 0, and every decision cites a locator.
- **Dedupe.** Nothing was dropped. Each source was assigned once, and no record cites a source outside its session's assignment.
- **Atlas path.**
  - Map: 120 rows, 117 mapped. The other 3 lines name types that are not in the type list.
  - Coder rooms had no type map, and each coder produced 120 keys, all `intact`. The atlas text contains no headless or decapitated test.
  - The 16 two-type lines expand to 32 `multi_dn` records, and adjudication made 3 more `multi_dn` with partners named by the paper.
  - Coder B confirmed 120 of 120 of coder A's quotes.
  - I checked 16 map rows against the Fig. S5 headings on rendered pages, and all match. SS01067, printed under a different heading, is resolved by the Namiki/2025 annotation and the Fig. 6B counts (`medium`), which is a defensible call.
- **L10.** The 0 fills reproduce: 122 `unknown` records match a kit line ID, and none of the matching rows has non-empty `other_cells`.
- **L6.** The exposed-by-nature set reproduces: two types, both already in the kit list.
- **Full rebuild.** `labels2_collect.merged` plus `line_spec_fill` (breach set = the one search session) reproduce `records.jsonl` record for record. Front-leg kappa over all values is 0.932 on 422 pairs (S5.4).

## Spot check (42 non-dedicated final records)

The sample is the 19 non-dedicated rows of `spot_check_sample.csv` (the dedicated row was skipped), all 4 `reader_web` final records, 15 random picks across the other sessions (3 of them atlas) and 4 random picks among eligible records of non-exposed types. It includes 6 atlas records in total.

- **Quotes:** 42 of 42 found.
  - The 36 text quotes occur verbatim. Beyond the sample, all 240 non-atlas, non-dedicated final quotes occur in the local source text after whitespace and punctuation normalisation.
  - The 6 atlas quotes are panel labels, which I checked on rendered Fig. S5 pages. Each inset region matches its coded category.
- **Field errors:** none in `front_leg_rhythm`, `middle_leg_rhythm`, `hind_leg_rhythm`, `preparation`, `manc_type` or `mapping_confidence`.
- **`line_specificity`:** no clear errors. Three `clean` codings are lenient, because the paper only names the line's target: `pass1-grooming-r0-01-0022`, `pass1-escape_landing-r0-01-0010` and `-0014`.
- **Judgement calls, not counted as errors:**
  - `pass1-recent_broad-r2-01-0001`: the paper's name and line ID disagree; the reader followed the line ID and coded `medium`.
  - `pass1-escape_landing-r0-02-0006`: the second type comes from the kit's line annotation only (`multi_dn`).
  - `pass1-grooming-r0-01-0003`: the trials were pre-selected for walking before stimulation, and the walking convention was applied.
  - `pass1-steering-r0-03-0001`: abstract only, outcome inferred from a hypothesis sentence, low confidence, exposed type.

## Type level

`aggregate.type_labels(records, exposed = kit_v2/exposed_types.csv ∪ exposed_v2.csv, type_list = kit_v2/type_list.csv)` is byte-identical to `type_labels.csv` (477 rows). The `exposed` flags match, and all 416 records pass the frozen validator.

66 types have a clear front-leg label; 53 of them are outside the exposed set (36 yes, 17 no). The primary set also needs A1's type list, which I did not open, so 53 is only an upper bound for S5.5.

## Blockers

None.

## Caveats the report must carry

1. **Atlas concentration.**
   - 34 of the 53 candidate types rest only on atlas records in the consensus tier. These include 33 of the 36 yes types, and 7 of the 34 have only low-confidence records.
   - Their outcomes come from reading inset regions of a behaviour map, with no leg tracking, under the "increased locomotion" convention. Their types come from a single map reading.
   - The atlas lines without a phenotype are never identified, so the atlas contributes no null records. Label class and source method are therefore confounded.
   - About 40 % of the L11 verification frame are atlas rows that must be read from figure insets.
2. **Co-activation coding.** Deliberate co-activations are coded as records of each partner. When the partner is not a DN, the record becomes `minor_offtarget` and survives the tier. `pass1-walking_stopping-r0-01-0037` turns one non-exposed type's front-leg consensus to `conflicting`, which removes that type from the clear set.
3. **Lost `reader_web` records.**
   - `PROMPT_PHASEB.md` checks quotes in the local copy only, and for web-read sources that copy is an abstract. As a result, 6 records were dropped as `quote_unverified`.
   - 4 of the 6 are non-dedicated: `pass1-escape_landing-r0-03-0001` and `pass1-escape_landing-r2-02-0001` to `-0003`. The second readers had matched these quotes on the web in Phase A. Every affected type has high-confidence records elsewhere, so no type label changes.
   - 5 more records were lost to schema-invalid second readings (`no_pass2`).
4. **Recall.**
   - 14 of 95 assigned sources stayed unreachable, and only 4 `reader_web` records reached the final set.
   - The round-2 stop is marginal: with the breaching session's dropped leads it would be 20/187 = 10.7 %, which would have required a third round. Stopping is still conformant, because L3 drops those leads.
5. **Chapman estimate.** The `merge_log.json` estimate (186.8 units in total, 8.8 missed) uses all first readings, including round-1 and round-2 readers whose sources came from search leads. With round-0 readings only, L9's "first reading", it is 175.7 (7.7 missed). This affects reporting only.
6. **Sightings list.** The 29 `sightings_without_flagged_records` rows are a keying artefact: `_sightings_check` matches only the first reader's session. The sightings name only kit-exposed types, whose dedicated records are flagged where a score was seen. Five search sessions saw second-hand simulation summaries in WebSearch results. This is not a breach, and their leads carry no outcome.
7. **Cosmetic.** Some adjudicated records keep the first reader's `notes`, which contradict the final field. Example: `pass1-recent_broad-r0-01-0002` (`line_specificity`).
