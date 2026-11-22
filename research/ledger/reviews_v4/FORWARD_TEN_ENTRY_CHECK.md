Verdict: ten of ten agree

# Forward ledger v1: ten-entry check (PREREG v4 E9)

A fresh reviewer checked these entries on 2026-11-22 on branch `ledger/v1`. Nothing was simulated. `ledger/scripts/forward_v1.py`
was read, not run. Every checked value was recomputed with the reviewer's own code. Project code was reused only to load inputs:
`brainir_ledger.mirror.fly` (networks W, read-out, type groups, G3 sides, dropped members) and `brainir_ledger.data_dir` (location
of the git-ignored Part A results).

**Files checked.** The forward files were last changed at commit 51eb386 and are identical at HEAD 8b987da. The two commits in
between touch only `research/ledger/LOG.md` and `ledger/scripts/posthoc/modal4b_v4.py`. The sha256 of the checked files:

| file | sha256 |
|---|---|
| `research/ledger/forward/LEDGER.csv` | f53f1e743980815d291efa1e224f6069173efedabc42cddae023ab6723fc1607 |
| `research/ledger/forward/CALIBRATION.json` | d4178f761c351b867c0b11bb2c3b075781a1c3d86adbd3f3a4002d2ec0f70974 |
| `research/ledger/forward/SENTENCES.md` | df1548b13be5211e17ae25fd4d7b55ff4a14176e1dddad4d51a4c0120716245a |

## The ten sampled rows

Rule (LOG L135): sort `research/ledger/forward/LEDGER.csv` (126 rows = 63 types x 2 sources) by type, then by source (the file is
already in that order). Then `numpy.random.default_rng(20261461).choice(126, size=10, replace=False)` = [18, 73, 110, 41, 32, 45, 99,
10, 40, 121].

| draw | row index | type | source |
|---|---|---|---|
| 1 | 18 | DNg107 | authors_model |
| 2 | 73 | DNp14 | two_step_count |
| 3 | 110 | DNp57 | authors_model |
| 4 | 41 | DNg45 | two_step_count |
| 5 | 32 | DNg35 | authors_model |
| 6 | 45 | DNg50 | two_step_count |
| 7 | 99 | DNp44 | two_step_count |
| 8 | 10 | DNa15 | authors_model |
| 9 | 40 | DNg45 | authors_model |
| 10 | 121 | DNx01 | two_step_count |

## Checks 1, 2, 3 and 5

The tolerances were fixed before any value was compared:
- score: exact;
- x and p: within 1e-12;
- flags, lines and sentence: exact string equality.

Every recomputed score, x and p is identical to the ledger value (difference 0).

How each value was recomputed:
- **Score:** taken from `predictions/A1/types.csv` `primary_score` (authors_model) or `predictions/S/types.csv` `S2_twohop_signed`
  (two_step_count).
- **x:** (number of the source's 321 types with a lower score + half the number with an equal score, the type itself included) / 321.
- **p:** 1 / (1 + exp(-(a + b x))), with a and b from `CALIBRATION.json`:
  - authors_model: a = 0.07364816882947109, b = 1.3670312975569272;
  - two_step_count: a = -0.25301829358883027, b = 1.9223593164686588.

| row | type | source | (1) score | (2) below / equal -> x | (3) p (100 p) | (5) % in sentence; kit lines | result |
|---|---|---|---|---|---|---|---|
| 18 | DNg107 | authors_model | 0.0 | 0 / 134 -> 0.2087227414 | 0.5887931810 (58.88) | 59 %; SS39271 | all agree |
| 73 | DNp14 | two_step_count | 212255 | 307 / 1 -> 0.9579439252 | 0.8304041330 (83.04) | 83 %; SS57757, SS64605, SS72989, SS73011, SS74396, VT014647 | all agree |
| 110 | DNp57 | authors_model | 0.2265615237 | 283 / 1 -> 0.8831775701 | 0.7826164711 (78.26) | 78 %; SS01553, SS74386 | all agree |
| 41 | DNg45 | two_step_count | 6987 | 230 / 1 -> 0.7180685358 | 0.7553527435 (75.54) | 76 %; SS53380, SS64037, SS64584, SS64640, SS64641, SS64642, SS70544, SS81824, SS81829, SS81914, SS90832 | all agree |
| 32 | DNg35 | authors_model | 0.1431420711 | 259 / 1 -> 0.8084112150 | 0.7647268625 (76.47) | 76 %; R38C08, SS57828, SS63217, SS63264, SS63305, SS74458 | all agree |
| 45 | DNg50 | two_step_count | -33540 | 75 / 1 -> 0.2352024922 | 0.5496175120 (54.96) | 55 %; SS64577, SS67148, SS83468, SS95552, SS95555 | all agree |
| 99 | DNp44 | two_step_count | 2958 | 211 / 1 -> 0.6588785047 | 0.7337207504 (73.37) | 73 %; SS64688, SS66153 | all agree |
| 10 | DNa15 | authors_model | 0.0 | 0 / 134 -> 0.2087227414 | 0.5887931810 (58.88) | 59 %; DNae014-splitGal4, SS27191 | all agree |
| 40 | DNg45 | authors_model | 0.0 | 0 / 134 -> 0.2087227414 | 0.5887931810 (58.88) | 59 %; the 11 lines of row 41 | all agree |
| 121 | DNx01 | two_step_count | 40126 | 269 / 1 -> 0.8395638629 | 0.7959100128 (79.59) | 80 %; R55H04, SS72185, SS73430 | all agree |

**The sentences (check 5).** Each of the ten sentences was rebuilt from the recomputed values with this template:

`Activating <type> (lines: <kit lines, sorted, comma-separated>) in a decapitated fly: <source name> gives a <round(100 p)> % chance of rhythmic front-leg stepping.`

The source names are "the authors' model (A1)" and "two-step signed synapse counting (S2)". The lines come from
`kit_v2/driver_lines.csv` (rows whose `manc_type` is the type). For each entry:
- the rebuilt sentence equals the bullet character for character;
- it occurs exactly once among SENTENCES.md's 126 bullets, at the position equal to its sorted row index;
- it equals the LEDGER `sentence` column;
- the LEDGER `lines` column equals the kit's lines.

No 100 p lies at a rounding half; the closest is 76.47.

**The sentences only restate locked numbers.** A sentence has four variable parts:
- the type name, from the A1 table (LOCK_predictions_v1.json);
- the line IDs, from `kit_v2/driver_lines.csv` (LOCK_labels_v2.json);
- the source name, which is fixed text;
- the rounded probability. It is a function of the locked score (LOCK_predictions_v1.json) and of a and b from `CALIBRATION.json`.
  That file is not yet under a lock: LOCK_forward_v1.json follows this check. a and b were verified against locked inputs (see
  "Integrity of the inputs").

Nothing else in a sentence is written by hand.

## Check 4: stability flags (E5), recomputed

**Authors' model.** The two flags are recomputed as follows:
- **Two flies:** the band of B1r vs the band of B2r, from `primary_score` in `predictions_v2/B1r/types.csv` and
  `predictions_v2/B2r/types.csv`. Recomputing it from the locked `replicates.parquet` gives the same values.
- **Two sides:** the band of the Part A MANC-L vs the MANC-R type score. The type score is the mean over usable replicates of seeds
  0..15, or 0 if there are none (G5).

Bands: nd = non-driver (< 0.05), ind = indeterminate, drv = driver (>= 0.5).

| row | type | two flies: B1r vs B2r | two sides: MANC-L vs MANC-R (usable of 16) | recomputed | ledger |
|---|---|---|---|---|---|
| 18 | DNg107 | 0.04917 nd vs 0 nd | 0.02592 nd (9) vs 0 nd (16) | agree, agree | agree, agree |
| 110 | DNp57 | 0.26464 ind vs 0 nd | 0.26719 ind (16) vs 0.18592 ind (16) | disagree, agree | disagree, agree |
| 32 | DNg35 | 0.03971 nd vs 0.05331 ind | 0 nd (1) vs 0 nd (16) | disagree, agree | disagree, agree |
| 10 | DNa15 | 0 nd vs 0 nd | 0 nd (0) vs 0.03124 nd (9) | agree, agree | agree, agree |
| 40 | DNg45 | 0.01043 nd vs 0 nd | 0.10719 ind (16) vs 0 nd (16) | agree, disagree | agree, disagree |

**Two-step count.** S2 = 1_MN' W W 1_members, computed here through the explicit two-hop matrix W W. The two flags are:
- **Two flies:** the type's S2 tercile among the 310 types in both the MANC and the MaleCNS groups, each fly with its whole front-leg
  read-out.
- **Two sides:** the S2 tercile among MANC's 308 matched types, each half with its members and that side's 72 front-leg motor
  neurons.

The tercile comes from the type's average rank r (ascending) among n types: lower if 3r <= n, middle if 3r <= 2n, else upper. The
boundaries are 103.3 and 206.7 of 310, and 102.7 and 205.3 of 308.

| row | type | two flies: MANC vs MaleCNS S2 (rank of 310) | two sides: MANC-L vs MANC-R S2 (rank of 308) | recomputed | ledger |
|---|---|---|---|---|---|
| 73 | DNp14 | 212255 (297) upper vs 99137 (282) upper | 49184 (288) upper vs 94788 (292) upper | agree, agree | agree, agree |
| 41 | DNg45 | 6987 (223) upper vs 5162 (192) middle | 2365 (237) upper vs 2216 (230) upper | disagree, agree | disagree, agree |
| 45 | DNg50 | -33540 (75) lower vs -1870 (104) middle | -9021 (84) lower vs -22963 (74) lower | disagree, agree | disagree, agree |
| 99 | DNp44 | 2958 (204) middle vs 4121 (184) middle | 1434 (226) upper vs 2259 (231) upper | agree, agree | agree, agree |
| 121 | DNx01 | not computed: DNx01 is not among the MaleCNS groups (nor in B2r) | 7843 (259) upper vs 11487 (262) upper | not computed, agree | not computed, agree |

All ten pairs of flags could be recomputed.

## Mismatches

None.

## Integrity of the inputs

**Locked files.** The sha256 of each of these files equals the hash its lock records:

| lock | files |
|---|---|
| LOCK_predictions_v1.json | `predictions/A1/types.csv`, `predictions/S/types.csv` |
| LOCK_predictions_v2.json | `predictions_v2/B1r/types.csv`, `predictions_v2/B2r/types.csv`, both `replicates.parquet` |
| LOCK_labels_v2.json | `kit_v2/driver_lines.csv`, `kit_v2/exposed_types.csv`, `labels_v2/type_labels.csv`, `labels_v2/exposed_v2.csv` |
| LOCK_reliability_v2.json | `gates_v4/TYPE_SETS.json`, `gates_v4/TRUST_GATE_v4_modal.json`, `reliability_v2/A.json`, `reliability_v2/WIRING_A4.json` |
| LOCK_reliability_v1.json | `reliability_v1/R2.json` |

The S table has exactly A1's 321 types and no missing value.

**Git-ignored inputs that no lock hashes.** These were anchored to locked numbers before any flag was read from them.
- **Part A MANC results.** Seeds 0..3 come from `$DATA/ledger/reliability/GHA_r4-run3` and seeds 4..15 from
  `$DATA/ledger/reliability_v2/MODAL_pa-manc-run4`. `GHA_pa-manc-run4` is absent locally, so seeds 4..15 come from the Modal copy
  only. The Modal trust gate is "identical". The results hold 16 seeds x 308 types per side, and the 308 types are TYPE_SETS.json's MANC matched set. The
  recomputed type scores reproduce three numbers of A.json:
  - the full-seed MANC-L vs MANC-R Spearman 0.5097444979536535, exactly;
  - the band kappa 0.30730478589420657, to 2e-16;
  - the driver counts 16 / 18, with 3 in both.
- **Networks.** The recomputed S2 values reproduce the locked numbers:
  - the whole-fly MANC S2 equals the locked S table for all 321 types;
  - cross-fly, n = 310 and Spearman 0.780130715885039, as in R2.json;
  - per side, n = 308 and Spearman 0.8401511921952839, as in WIRING_A4.json (to 1e-16);
  - MANC's matched halves equal TYPE_SETS.json.

**Calibration (not one of the five checks).**
- The fit set was rebuilt from the locked label and exposed-set files: 39 types, 25 "yes", 6 headless. With fewer than 15 headless
  types, E3 uses all labelled types, as the file says.
- At CALIBRATION's (a, b), the log-likelihood gradient is below 2e-15 for both sources.
- An independent Newton fit reproduces a and b to 1.4e-15, so they are the maximum-likelihood fit.

## Notes (not mismatches)

1. **Percentile convention.** The ledger uses (below + equal/2) / 321, which equals scipy's `percentileofscore` with kind "mean". E3
   says only "average ties". The other usual reading, average rank / 321, adds exactly 1/642 to every x. A refit absorbs this in the
   intercept (a' = a - b/642, b' = b, checked to 1e-15), so no p and no sentence would change.
2. **Flags on edges.** These flags are correct under the rules as written, but they sit on edges:
   - DNa15's MANC-L has no usable replicate of 16. Its score of 0, and so its "two sides: agree", rest on G5's score of 0 when no
     replicate is usable.
   - DNg35's MANC-L score of 0 rests on a single usable replicate of 16, which scored 0.
   - DNg107's B1r score, 0.0492, is just under the 0.05 non-driver edge.
   - DNg35's B1r score (0.0397) and B2r score (0.0533) straddle that edge.
   - DNg50's MaleCNS S2 rank, 104 of 310, is one rank above the lower-tercile boundary (103.3).
3. **Lines that label another DN type.** Per the kit's `other_cells`, two of the named lines also label another DN type: SS01553
   (DNp57's sentence) also labels DNp26, and SS27191 (DNa15's sentence) also labels DNa04. The sentences give the lines as the kit
   lists them.
4. **Wording.** The template writes "a 83 %" and "a 80 %" where English needs "an". This happens in 21 of the 126 sentences.
