# Addendum to the numbers and references review (PAPER_NUMBERS_REFS_REVIEW.md)

Written by the orchestrating session after the review was committed unchanged (7d85be3). Each decision was made before the revision and
recorded here first. R1-R7 refer to the revised `paper/PREPRINT_v1.md`, and S1-S8 to the revised supplement.

| Problem | Decision | Change |
|---|---|---|
| **P1** four types, not three; Fig. 4 drew on the wrong table | **Accepted; the most important.** | <ul><li>A new post hoc lock (`LOCK_paper_posthoc_v1.json`, tag `ledger-paper-posthoc-v1`) holds the per-type sweep scores of the 182 three-animal types in all three animals. Its script asserts that it reproduces the locked `C5.driver_table` sweep scores, and that its all-three set equals the intersection of the locked C4 `types_in_both` lists.</li><li>R4 names four types: DNg100, DNxl092, DNa13 and DNxl134.</li><li>Fig. 4 is redrawn from the sweep screens. It shows the 22 types that are hits in at least two animals, with scores printed and hits marked; the caption gives 71 types that are hits in at least one.</li><li>CLAIMS row 18 is re-sourced.</li></ul> |
| **P2** abstract mixes procedures | **Accepted.** | The abstract names the procedure: the first two animals' lists overlap at chance under the current-setting procedure but above chance under the sweep (post hoc). |
| **P3** -0.21 is a difference of rho_x | **Accepted.** | R2: "the difference in raw cross-half correlation was -0.21 (-0.37 to -0.05)". |
| **P4** DNb08 sweep score | **Accepted.** | R4 gives 0.00 under the current-setting procedure and 0.25 under the sweep. It also says that the single-copy runs used the current-setting procedure. |
| **P5** sets | **Accepted.** | <ul><li>R3 states the set of each count: 202 MANC-BANC types, 182 MaleCNS-BANC types, 214 MANC-MaleCNS types, all matched with high confidence, without DNg100.</li><li>Table 2's caption and the text name the set of every count. (An earlier draft of this addendum said "Table 1 lists every set"; Table 1 gives each result's status instead.)</li><li>Fig. 4 uses the 182 three-animal types with DNg100, and says so.</li><li>The Limitations' "60 of 182" names its set.</li></ul> |
| **P6** wiring floor and the 0.71 | **Accepted.** | R3: "with BANC cut at the same 5-synapse threshold, 0.61 and 0.63 (0.63 and 0.63 without it)", and "the lowest value seen in any earlier comparison of one side of one animal with a side of the other (0.71)". |
| **P7** "6 of its 11" | **Accepted.** | <ul><li>R3: "6 of its 11 hits have a high-confidence BANC match once DNg100 is left out; 1 of them recurred".</li><li>The Discussion drops "the authors' own six high-confidence hits".</li></ul> |
| **P8** 14 without DNg100 | **Accepted.** | R4: "14 types besides DNg100". |
| **P9** status wording | **Accepted, all three parts.** | <ul><li>(a) "Not screened until our rules were frozen"; the Methods list what was known before the freeze.</li><li>(b) "Every pre-registered test ..." in the Introduction and Methods.</li><li>(c) Table 1 gives every result's status; the Limitations say "in this analysis" and name the earlier pre-registered tests.</li></ul> |
| **P10** Modal | **Accepted.** | The Methods say that this analysis's simulations ran on GitHub Actions, and that two earlier screens it uses ran on Modal under their own trust gate: MANC's one-sided screen for draws 4-15, and MANC's current sweep. |
| **P11** 0.13 to 0.21 | **Accepted.** | "0.14 to 0.21". |
| **P12** 0.98 against 0.985 | **Accepted.** | "0.985; theirs 0.985". |
| **P13** timing of the forward list | **Accepted.** | <ul><li>R7: "After both literature tests, and after the post hoc replication pattern was seen, but before the third animal, we listed ...".</li><li>The heading becomes "Twelve experiments that could test the readings".</li></ul> |
| **P14** Fig. 2 and the 0.47 | **Accepted.** | <ul><li>Fig. 2 is redrawn in three panels: left against right; resampled networks, each beside the left-right value of its own design (MANC 0.48 beside 0.47, BANC 0.78 beside 0.58); and across animals under both procedures.</li><li>Every bar names its procedure and status.</li></ul> |
| **P15** minor | **Accepted.** | <ul><li>The Methods say the ratio divides by the mean of the two screens' self-agreements (G1).</li><li>S2 gives 180 as the left-right test's set.</li><li>R6: kappa over the 33 hemilineage-by-phenotype cells that both papers code, and "two source papers".</li><li>The hand-check line stays open: it is the author's to fill, and the build refuses final files until then.</li></ul> |
| **P16** CLAIMS | **Accepted.** | <ul><li>Row 12 cites the locked curve fields (Fig. 3 now draws the authors' list).</li><li>Row 18 is re-sourced to the new lock.</li><li>Row 24 cites the kappa field and `H-M.top1`. Row 27 cites `comparison_with_exam1.csv`. Row 35 cites `results/run2/P.json` `exposed_set.n_types`. Row 37 adds notes §1. Row 39 adds LOG L25.</li><li>New rows cover the Methods parameters, the 10,000 resamples and 95 % intervals, MANC's floor, the 20-job determinism samples, the animals' sexes and the 20 hand-check labels.</li></ul> |

## References

| # | Decision | Change |
|---|---|---|
| 14 | **Accepted.** | The title now ends "... to behavior in the *Drosophila* ventral nerve cord". |
| 15 | **Accepted.** | <ul><li>The title now ends "... in the *Drosophila* male adult nerve cord connectome".</li><li>R6 cites [13, 14] as the label sources, and [15] only for the summary used as a cross-check.</li></ul> |
| all | **Accepted.** | <ul><li>The references are renumbered in order of first citation; the Introduction now cites the original paper first.</li><li>A new script, `ledger/scripts/posthoc/refs_check_v2.py`, compares full normalised titles, authors, years and venues against the fetched metadata. The version-1 checker is hashed by the run-6 locks and is not edited.</li></ul> |
| 1 | Noted. | Statements cited to [1] alone are also in [2], which is public; where a statement rests on the preprint, [2] is cited with it. |

**Verified after the revision** (commits 32ffbf8 and the one after it). Every change above is in the revised `PREPRINT_v1.md`, `SUPPLEMENT_v1.md`, `CLAIMS_v1.md` or figures. `claims_check_v1.py` passes all 81 numeric checks and `refs_check_v2.py` passes all 18 references. Logged in LOG L190-L191.
