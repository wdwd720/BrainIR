# Label review, exam 2 (h1), PREREG v3 T8

Fresh session; no prediction, arm, result or simulation file opened. Read `labels_h1/`, PREREG v3 U/V/T, kit v3, the label code,
Harris 2015 and Soffers 2025 (Cheong: session notes only). Numbers come from the reviewer's own scratch scripts.

Verdict: usable with caveats

## Reproduced

- **Schema and vocabulary.** All 79 final records are valid. Every quote is verbatim in its source; 15 of 15 sampled quotes sit
  at their locator. `d7p` and the `d1` rule hold per record. No sightings; all 16 sessions audited, none breached.
- **U5.** Every mapping is correct: `20A/22A` → 20A.22A, `24B` → 24B.25B, `0A` → 00A, `11 A` → 11A. The 2 unmapped `11A/B`
  records span 11A and 11B, as U5(c) requires.
- **Raw readings → final records.**
  - Over 73 pairs × 16 fields (1,168), every final value equals the agreed value or the adjudicated one, with 0 mismatches.
  - The 6 adjudicated-unmatched finals equal their adjudicated records.
  - All 19 Harris and 45 Soffers disputes were adjudicated, with field sets equal to the disputes, and all 6 unmatched records
    were ruled to exist.
  - 8 cells got a value that neither reading gave (D0001 d11, D0018 d3, Soffers D0008 ×6). T3 allows this.
- **T4.** An independent implementation reproduces cell for cell `consensus.csv` (28 units), both `lab_*.csv` and
  `consensus_secondary.csv`. 27 units have at least 3 coded primary dimensions.
  - Traced by hand: 01A d6/d8 (decapitated vs decapitated, so conflicting), 05B d2 (Harris decapitated outranks Soffers intact)
    and d6 (fallback to all records), 13B d5/d8, 19A d2/d5, 20A.22A d5/`d7p`, 10B d5/d15.
- **Agreement** (all reproduced). Readings: kappa 0.975, n = 271 (0.814 full vocabulary). Harris vs Cheong: 1.0, n = 38.
  Between sources: 0.238, n = 33; 5 of its 7 disagreements set Harris decapitated against Soffers intact (05B d2-d4, 19A d2/d4).
- **Verification.** The 30-record draw and its 148 coded cells reproduce; the room input held no recorded values; 6/148 =
  4.05 %. verify-1's `out/` is empty and its stream contains the tool error "stopped by a safety classifier"; verify-2 is the
  effective verification.

## Findings

1. **Major. De-duplication drops distinct experiments (departs from T2/T3).**
   - `reading()` keys duplicates on (name, driver, preparation, effector *class*). It silently dropped 5 records, each against
     a same-session twin:
     - 11A high light intensity, decapitated and intact, in both readings: R1-soffers-a-0033/0034, R2-soffers-a-0032/0033.
     - 5B tethered flight: R1-soffers-a-0012.
   - Both readers coded high-intensity decapitated 11A with d13 = `yes` ("high intensity activation drove wing buzzing ... in
     intact and decapitated animals"). Restoring those records turns consensus 11A d13, and the matching Soffers per-source
     cell, from `not_assessed` to `yes`.
   - R1's 5B feeding record was then paired with R2's tethered-flight record. The final R1-soffers-a-0011 carries the feeding
     locator with the flight cells (d13 `no`; ADJ-soffers D0009). No consensus cell changes.
   - Part X forbids amending the label code now, so this can only be carried as a documented caveat.

2. **Major. Harris Figure 9A was read at too low a resolution.**
   - Readers, ADJ-harris and verify-2 all coded "no bar" as `no`, and ADJ-harris asked for a sharper copy. I rendered
     `article.pdf` p. 26 at 14x and compared every row.
   - Wrong, with the text silent:
     - 12B d13 = `no` despite a wing-buzz bar. The adjudicator placed 12B's marks one column left.
     - 13B d11/d13 = `no` despite a wing-buzz bar.
   - Text and figure disagree:
     - 05B d11 = `no` (text: "no ... wing associated behaviors"; figure: a wing-wave bar).
     - 06B d13 = `no` (text: "no wing movements except ... grooming"; figure: a wing-buzz bar).
   - All five are Harris-only primary consensus cells.
   - Every other Harris d5/d6/d7/d10/d11/d13 `no` matches the sharp figure, and the figure confirms 01A d11 = `yes`. One
     non-primary exception: 6A d8 = `no` despite a walking mark.
   - verify-2 also coded 12B d13 `no` (V009). Counting that cell as an error gives 7/148 = 4.7 %.

3. **Minor. A d5/d6 "opposite posture = `no`" convention (ADJ-soffers rule, not in V1).**
   - It is the sole basis of 04B d5, 08A d6 and 10B d5 = `no`. Similar inferences give 05B d6, 12B d5 and 20A.22A d5.
   - verify-2 applied it unevenly: it rejected it for 10B and 13B (2 of the 6 errors) but used it for V009, V011 and V029.
   - The 13B d5 `conflicting` cell is an artefact. R1 coded `unclear` ("unspecified postural change"), and R2 and the
     adjudicator coded `no`, yet Harris shows extension with the body lowered ("resting on their coxae").

4. **Minor. 23B d5/d6 = `yes`.** Both rest on "sustained flexion *or* extension", copied to the decapitated record because the
   source reports "similar responses". verify-2 coded both `unclear` (V030).

5. **Minor. "Uncoordinated leg movements" is coded differently by scope half.** Half a coded d7 `unclear` (13B intact, both
   readers); half b coded `yes` (14A, 23B). Kappa cannot see this. Under half b's convention, 13B `d7p` would be `yes`.

6. **Minor. Agreement figures overstate independence.**
   - The Cheong coding has 0 `no` cells ("-" = <50 % → `unclear`). All 38 shared cells are therefore yes/yes, 18 of them d1,
     and kappa = 1 only by the pe = 1 rule.
   - Of the 193 coded consensus cells, 52 rest on one reading plus the adjudicator, and 01A d11 rests on the adjudicator alone.
   - These include 32 of the 61 `no` cells. 28 of those are Harris cells, 25 of them coded only by R1, whose notes cite
     Figure 9A. None of these cells enter the reading kappa.

7. **Minor. Record-type judgement is uneven.**
   - Readers split on `record_type` in 18 of the 40 Soffers cell disputes, so primary membership follows ADJ-soffers' "specific,
     good coverage" rule.
   - 08B intact is `partial_or_mixed` because of brain clusters, while 17A intact is whole despite "a medial brain cluster".
     This has no consensus effect.
   - 16B was demoted for a Supp. file 5 genotype mismatch, but 4B, 7B and 10B, with similar mismatches, were not.

8. **Minor. Bookkeeping.**
   - Duplicate finals that the adjudicators asked to merge were kept: ADJ-harris-0001 = R1-harris-a-0012 (unmapped), and
     ADJ-soffers-0001 = 0004 and 0002 = 0005 (secondary). Their cells are identical, but the count of 79 includes 3 duplicates.
   - ADJ-soffers-0002/0005 code 12A clones that were "not dissect[ed]".
   - 00A's 12 `no` cells rest on one Table 2 sentence, with no video and no stated preparation.

## Records checked against the sources

Each record was checked for quote, locator, cells, record type, preparation and own experiment.

- **Correct:**
  - Harris: R1-harris-a-0001 (01A), R1-harris-b-0002 (19A), R1-harris-b-0006 (24B; the source's Video 22 legend names R22G11).
  - Soffers: R1-soffers-a-0001 (00A, by the "no phenotype" rule), R1-soffers-a-0021 (08B).
  - Secondary or adjudicated-unmatched: ADJ-soffers-0003 (21A, `partial_or_mixed`), R1-soffers-a-0007 (02A).
- **Correct except the flagged cells:**
  - Harris: R1-harris-a-0004 (05B d11), R1-harris-a-0007 (06B d13), R1-harris-a-0014 (12B d13), R1-harris-a-0015 (13B d11/d13).
  - Soffers: R1-soffers-a-0042 (13B d5), R1-soffers-b-0016 (23B d5/d6).
- **Inference:** R1-soffers-a-0002 (01A): d8/d9 = `no` is inferred from "Our observation differed".
- **Chimera:** R1-soffers-a-0011 (finding 1).

No record codes a result that the source only cites.

## Effect and recommendation

The consensus is an exact T4 computation over records that are mostly well supported.

- **Sensitivity cell set.**
  - Set to `yes`: 11A d13 and 13B d5.
  - Set to `unclear`: 12B d13, 13B d11, 13B d13, 05B d11, 06B d13, 10B d5, 23B d5 and 23B d6. These become `unclear` rather
    than `yes` because ADJ-harris's own rule for small marks next to silent text is `unclear`.
- **Effect.** 27 units still have at least 3 coded primary dimensions, and coded cells go from 193 to 187. The gate's error-rate
  condition still holds.
- **Before the labels lock.** Record findings 1-2 in the LOG. Report this set as an exploratory sensitivity variant, and do not
  edit the labels.
