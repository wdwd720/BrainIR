Verdict: usable with caveats

# Blind review of labels v2

Scope: `research/ledger/labels_v2/` (416 final records), PREREG v2 Part L and S5.2-5, the kit v2 protocol and prompts, `IMPLEMENTATION_v2.md`, LOG L49-L61. I opened no prediction, gate, results or arms file and no dedicated source, and I changed nothing in the repository. Reproductions ran read-only with the locked code.

## Process findings

- **Audit (L3).** 62 rooms, 62 manifests and 62 audit rows. The audit (18:23:33) is newer than the newest session log (18:23:08). Every session ended `success` on Opus 5.5 only. My own scan of all transcripts (909 fetches, 2,546 file-tool calls) found no banned host, no forbidden token and no successful access outside a room, apart from the known breach.
- **Breach.** `search-bydriverline-r2` is kind 3: an `esummary` request whose ID list contains the dedicated PMC number. Its leads were dropped: round 2 recomputes to 18 new units without them, and its one unique DOI is not registered. It is not a contributing session.
- **Reassignment and replacement.** None was needed. Every assigned source of every task kind has a valid disposition, and no `-a`, `-r` or `-w` specs exist.
- **Recall (L9).** Round 1 added 34 new units of 151 (22.5 %), round 2 added 18 of 187 (9.6 %), so the searches stopped. Both figures reproduce.
- **Second reading.** No word from the L8 list remains in `source_locator` or `stimulation` in any of the 291 input rows. Inflected forms such as "steered" are outside the fixed list. Each Phase A snapshot is stamped at its Phase B start, the code copies quotes after the snapshot, and `phase_a_changed_after_quotes` is empty for all 13 second readings.
- **Adjudication and dedupe.** Every disagreement was adjudicated (`disagreed_unadjudicated` = 0). Dedupe dropped nothing, because each source was assigned once.
- **Atlas path.**
  - Map: 120 rows, 117 mapped.
  - Coder rooms had no type map, and each coder produced 120 keys, all `intact`. The atlas reports no headless test.
  - 16 two-type lines expand to 32 `multi_dn` records.
  - Coder B confirmed all 120 of coder A's quotes.
  - 16 map rows I checked against the Fig. S5 headings all match.
- **L10 and L6.** The 0 fills reproduce: 122 `unknown` records match kit line IDs, none with `other_cells`. The two exposed-by-nature types reproduce and were already kit-exposed.
- **Full rebuild.** `labels2_collect.merged` plus the L10 fill reproduce `records.jsonl` exactly. Front-leg kappa over all values is 0.932 on 422 pairs (S5.4).

## Spot check: 42 non-dedicated final records

The sample: the 19 non-dedicated rows of `spot_check_sample.csv`, all 4 `reader_web` final records, 15 random picks across the other sessions and 4 random eligible picks. It includes 6 atlas records.

- **Quotes: 42 of 42 found.**
  - The 36 text quotes occur verbatim. Beyond the sample, all 240 non-atlas, non-dedicated final quotes occur in the local text.
  - The 6 atlas panel labels and their inset regions match on rendered Fig. S5 pages.
- **Field errors: none** in `front_leg_rhythm`, `middle_leg_rhythm`, `hind_leg_rhythm`, `preparation`, `manc_type` or `mapping_confidence`.
- **`line_specificity`: three lenient `clean` codings** where the paper only names the line's target: `pass1-grooming-r0-01-0022`, `pass1-escape_landing-r0-01-0010` and `-0014`.
- **Defensible calls, not counted as errors:**
  - `pass1-recent_broad-r2-01-0001`: the paper's name and line ID disagree; the reader followed the line ID.
  - `pass1-escape_landing-r0-02-0006`: the partner type comes from the kit only.
  - `pass1-grooming-r0-01-0003`: trials were pre-selected for walking.
  - `pass1-steering-r0-03-0001`: abstract only, low confidence, exposed type.

## Type level

`type_labels(records, exposed = kit_v2/exposed_types.csv ∪ exposed_v2.csv, type_list = kit_v2/type_list.csv)` is byte-identical to `type_labels.csv` (477 rows). All 416 records validate.

66 types have a clear front-leg label, 53 of them outside the exposed set (36 yes, 17 no). I did not open A1's type list, so 53 is only an upper bound for S5.5.

## Blockers

None.

## Caveats the report must carry

1. **Atlas concentration.**
   - 34 of the 53 candidate types rest only on atlas records in the consensus tier, including 33 of the 36 yes types. For 7 of the 34, every tier record has low confidence.
   - Their outcomes come from behaviour-map inset regions with no leg tracking. Their types come from a single map reading.
   - The atlas's null lines are never identified, so the atlas contributes no null records. Label class and source method are therefore confounded.
   - 40 % of the L11 verification frame (133 of 336) are atlas rows.
2. **Co-activation coding.** Co-activations with a non-DN partner become `minor_offtarget` and survive the tier. `pass1-walking_stopping-r0-01-0037` turns one non-exposed type to `conflicting`.
3. **Lost `reader_web` records.**
   - Phase B checks only the local copy, which for these sources is an abstract. Six records were dropped as `quote_unverified`, four of them non-dedicated (`pass1-escape_landing-r0-03-0001` and `pass1-escape_landing-r2-02-0001` to `-0003`).
   - Their quotes had been matched on the web in Phase A. No type label changes, because every affected type has high-confidence records elsewhere.
4. **Recall.**
   - 14 of 95 assigned sources stayed unreachable.
   - The round-2 stop is marginal: with the breaching session's dropped leads it would be 20/187 = 10.7 %, which would have required a third round. The stop is still conformant, because L3 drops those leads.
5. **Chapman estimate.** The logged figure (186.8) uses all first readings, including round-1 and round-2 readers. With round-0 readings only, L9's "first reading", it is 175.7. This affects reporting only.
6. **Sightings list.** The 29 `sightings_without_flagged_records` rows are a keying artefact, because the check matches only the first reader's session. The sightings name only kit-exposed types. Five search sessions saw second-hand simulation summaries; these are not breaches.
