# Label review, exam 2 (h1), PREREG v3 T8

Reviewer: a fresh session that opened no prediction, arm, result or simulation file. It read `labels_h1/`, PREREG v3 Parts U, V
and T, kit v3 `PROTOCOL.md`, the label code and the Harris 2015 and Soffers 2025 sources. For Cheong 2024 it read only the
session notes. All checks below were recomputed with the reviewer's own scratch scripts, without the project's core.

Verdict: usable with caveats

## Reproduced

- **Schema and vocabulary.** All 79 final records are valid in cells, record types, preparations, flags and quotes of at most
  25 words. Every quote is verbatim in its source (4 are truncated), and 14 of 14 sampled quotes sit at their locator. `d7p` is
  correct for every record. `d1` is `yes` wherever any other dimension is `yes`. All records are eligible: there are no
  sightings, and all 16 sessions were audited as non-breaching.
- **U5 mapping.** Every mapping is correct (`20A/22A` → 20A.22A, `24B` → 24B.25B, `0A` → 00A, `11 A` → 11A). The 2 unmapped
  `11A/B` records span 11A and 11B, as U5(c) requires.
- **T4 consensus.** An independent implementation reproduces `consensus.csv` (28 units), both `lab_*.csv` and
  `consensus_secondary.csv` cell for cell. 27 units have at least 3 coded dimensions.
  - Hand traces checked these cells: 01A d6/d8 (decapitated vs decapitated, so conflicting); 05B d2 (Harris decapitated
    outranks Soffers intact) and d6 (fallback to all records); 13B d5/d8; 19A d2/d5; 20A.22A d5/`d7p`; 10B d5/d15.
- **Agreement.** Readings: kappa 0.975 over 271 cells, 0.814 over the full vocabulary. Harris vs Cheong: kappa 1.0 over 38
  cells. Between sources: kappa 0.238 over 33 cells. Of the 7 between-source disagreements, 5 set a Harris decapitated record
  against a Soffers intact one (05B d2-d4, 19A d2/d4).
- **Verification.** The 30-record draw reproduces. The verifier's room input held no recorded values. Error rate 6/148 =
  4.05 %. verify-1's `out/` is empty and its stream ends "stopped by a safety classifier", so verify-2 is the effective
  verification.

## Findings

1. **Major. De-duplication drops distinct experiments (departure from T2/T3).**
   - `reading()` keys duplicates on (name, driver, preparation, effector *class*). That silently removed 5 records written
     within one session:
     - the 11A high-light-intensity records in both readings (R1-soffers-a-0033/0034, R2-soffers-a-0032/0033);
     - 5B tethered flight (R1-soffers-a-0012).
   - Both readers coded decapitated high-intensity 11A with d13 = `yes` ("high intensity activation drove wing buzzing ... in
     intact and decapitated animals"). Restoring those records changes exactly one cell: 11A d13 goes from `not_assessed` to
     `yes`.
   - R1's 5B feeding record was then paired with R2's tethered-flight record. The final R1-soffers-a-0011 carries the feeding
     locator but the flight cells (d13 `no`; ADJ-soffers D0009). This changes no consensus cell.
   - Part X forbids amending the label code now, so this can only be carried as a documented caveat.

2. **Major. Harris Figure 9A was read at too low a resolution.**
   - Readers, ADJ-harris and verify-2 all read "no bar" as `no`, and ADJ-harris asked for a sharper copy. I rendered
     `article.pdf` p. 26 at 14x and compared it with every Harris row.
   - **Wrong (text silent):**
     - 12B d13 = `no`, but the figure has a wing-buzz bar. The adjudicator placed 12B's two marks one column too far left.
     - 13B d11 and d13 = `no`, but the figure has a wing-buzz bar.
   - **Source conflict:**
     - 05B d11 = `no`: the figure has a wing-wave bar, while the text says "no ... wing associated behaviors".
     - 06B d13 = `no`: the figure has a wing-buzz bar, while the text says "no wing movements except ... grooming".
   - All 5 are Harris-only primary consensus cells. Every other Harris `no` in d5/d6/d7/d10/d11/d13 matches the sharp figure,
     and the figure supports 01A d11 = `yes`.
   - verify-2 shared the same image and also coded 12B d13 `no` (V009). Re-scoring that cell gives 7/148 = 4.7 %.

3. **Minor. An "opposite posture = `no`" convention for d5/d6 (ADJ-soffers rule, not in V1).**
   - It is the sole basis of 04B d5, 08A d6 and 10B d5 = `no`. Similar inferences produce 05B d6, 12B d5 and 20A.22A d5.
   - verify-2 rejected it in both Soffers cases it saw (10B d5, 13B d5).
   - The 13B d5 `conflicting` cell is an artefact. R1 coded `unclear` ("unspecified postural change"), and R2 and the
     adjudicator coded `no`. Harris shows that extension can coexist with the body lowered ("resting on their coxae").

4. **Minor.** 23B d5 and d6 = `yes` rest on "sustained flexion *or* extension of the leg segments", copied to the decapitated
   record because the source reports "similar responses". verify-2 coded both `unclear` (V030).

5. **Minor. The two scope halves read "uncoordinated leg movements" differently.**
   - Half a coded d7 `unclear` (13B intact, both readers); half b coded `yes` (14A, 23B).
   - Kappa cannot detect this. Under half b's convention, 13B `d7p` would be `yes` rather than `unclear`.

6. **Minor. The agreement figures overstate independence.**
   - The Cheong coding has 0 `no` cells: "-" (under 50 %) was coded `unclear`. All 38 shared cells are therefore yes/yes, 18 of
     them d1, and kappa is 1 only by the pe = 1 rule.
   - Of the 193 coded consensus cells, 52 rest on one reading plus the adjudicator, and 01A d11 rests on the adjudicator alone.
     That includes 32 of the 61 `no` cells, mostly Figure 9A cells that R2 left `not_assessed`. None of these cells are in the
     reading kappa.

7. **Minor. Record-type judgement is uneven.**
   - Readers split on `record_type` in 18 of 40 Soffers cell disputes, so primary membership follows ADJ-soffers' "specific,
     good coverage" rule.
   - 08B intact is `partial_or_mixed` because of brain clusters, but 17A intact is whole despite "a medial brain cluster". This
     has no effect on the consensus.
   - 16B was demoted for a Supp. file 5 genotype mismatch, but 4B, 7B and 10B, with similar mismatches, were not.

8. **Minor. Bookkeeping and weak evidence.**
   - Duplicates that the adjudicators asked to merge were kept: ADJ-harris-0001 = R1-harris-a-0012 (unmapped), and
     ADJ-soffers-0001 = 0004 and 0002 = 0005 (secondary). Their cells are identical, but 79 counts 3 duplicates.
   - ADJ-soffers-0002/0005 code 12A clones that were "not dissect[ed]".
   - The 12 `no` cells for 00A rest on one Table 2 sentence, with no video and no stated preparation.
   - 06B d11 = `yes` rests on grooming-associated wing movement, which controls also show.

## Records checked against the sources (quote, locator, cells, type, preparation, own experiment)

| record | verdict |
|---|---|
| R1-harris-a-0001 (01A) | correct, including d11 |
| R1-harris-a-0004 (05B) | correct except d11 |
| R1-harris-a-0007 (06B) | correct except d13 |
| R1-harris-a-0014 (12B) | d3/d4/d6 correct; d13 wrong |
| R1-harris-a-0015 (13B) | d2-d6 correct; d11/d13 wrong |
| R1-harris-b-0002 (19A) | correct |
| R1-harris-b-0006 (24B) | correct (Video 22 legend names R22G11: a source error) |
| R1-soffers-a-0001 (00A) | correct by the "no phenotype" rule |
| R1-soffers-a-0002 (01A) | d6 correct; d8/d9 inferred from "observation differed" |
| R1-soffers-a-0042 (13B) | d6 correct; d5 unsupported |
| R1-soffers-b-0016 (23B) | d7/d9/d11/d13 correct; d5/d6 doubtful |
| R1-soffers-a-0011 (05B, other) | chimera (finding 1) |
| ADJ-soffers-0003 (21A, adjudicated-unmatched) | correct, `partial_or_mixed` |
| R1-soffers-a-0007 (02A, secondary) | correct |
| R1-soffers-a-0021 (08B) | correct |

No record codes a result the source only cites.

## Effect and recommendation

The consensus is an exact T4 computation over records that are mostly well supported.

- **Corrected cell set.** Set 11A d13 and 13B d5 to `yes`. Set 12B d13, 13B d11, 13B d13, 05B d11, 06B d13, 10B d5, 23B d5 and
  23B d6 to `unclear`.
- **Effect.** 27 units still have at least 3 coded dimensions, and coded cells go from 193 to 187. The gate's error-rate
  condition still holds.
- **Before the labels lock.** Record findings 1-2 in the LOG. Report the corrected cell set as an exploratory sensitivity
  variant, and leave the labels as they are.
