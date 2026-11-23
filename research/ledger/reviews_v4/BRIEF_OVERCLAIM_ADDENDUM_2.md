# Addendum: answer to the second overclaim review of the brief (`BRIEF_OVERCLAIM_REVIEW_2.md`)

The review was written by a fresh reviewer on the default model: a newly started agent, not a fork of the orchestrating session, given
only the files to read, a read-only instruction and one report file to write. It reviewed the brief as revised after the first
overclaim review (`BRIEF.md` at e1ff547). The report is committed once, unchanged (343125e). That commit was made while the reviewer was
still checking its report. The reviewer then edited its file, reverted those edits so that the file matches the commit (RUN4_PROMPT
hard limit 6), and put four corrections in its final message. After it finished, the file was checked byte-identical to 343125e. The
reviewer's final message refers to the orchestrating session as "another session". This file records those corrections (section 1) and
how each item was resolved (section 2); it is the answer, not an edit of the review.

## 1. The reviewer's corrections to its own report, as given in its final message

> - **Item 10, scoring bullet: wrong.** The rule (E7) compares each source with a guesser that always says 0.641. So a "no" for a
>   zero-score type scores in the model's favour (0.589² = 0.347 against 0.641² = 0.411), not against it. The correct point is that
>   the fit turns the screen's "no rhythm" into 0.59, so the Brier comparison tests the calibration, not the screen's own call.
> - **Item 8 evidence:** `C.json` `primary` has 12 keys, `unfixed` plus 11 fix entries, not 11.
> - **Item 12:** the kit's records conflict. SS01553 also has a DNp26 row with no other cells, and SS01588 is only assigned to DNg30,
>   without an other-cells entry. The wording should be "in at least one kit record", and "possibly joint activation" rather than
>   "joint activation". The in-progress brief revision already uses the original item 12 wording.
> - **Determinism note:** read "every result-bearing campaign". The trust-gate, R4-reproduction and pipeline-test campaigns have no
>   determinism sample.

All four are accepted. On item 12, one detail checked: `kit_v2/driver_lines.csv` has, for SS01588, two DNg30 records, one DNp26 record
and one record with no type, none with an other-cells entry, so it is not assigned to DNg30 only. The brief's rule (a line counts if at
least one of its kit records names another descending-neuron type) covers it either way.

## 2. Resolution, item by item

| item | resolution in `BRIEF.md` | also changed |
|---|---|---|
| 1 premise | The DNg100 parenthetical is deleted (not expanded, to keep the brief short). The connectomes' differences in reconstruction and annotation are added: MaleCNS's descending-neuron sides were reassigned from their outputs (G3), and its neurons carry MANC types by matching (G2). | HANDOFF section 11; evidence rows 3-4 |
| 2 frozen | "Frozen before any simulation of this run". Both gaps had been seen in an earlier run, whose MANC seeds 0-3 Part A reuses (Part Q), and result 1 had not been computed. The earlier run's values are not quoted: they are raw correlations and would read as ratios next to result 2. | RESULTS_3 header; evidence rows 5-6 |
| 3 post-hoc figures | Both unlocked figures (about 86 % of the gap; about a third of the connections) are removed from the brief, because its rules require every number to come from a locked file (RUN4_PROMPT section 8). The qualification stays in words, with its source named and marked as under no lock. The second pre-registered noise model (negative binomial, 0.45, locked) is added, and the tag line names what is under no lock. For the brief, this supersedes change 2 of `ADVERSARIAL_ADDENDUM_v4.md`; RESULTS_3 and the evidence map keep the six-pair figure, marked post hoc. The third is now described as connections present in one copy only. | RESULTS_3 header (the exception named); HANDOFF section 10; evidence row 20 |
| 4 labels | Reworded as suggested, without a count of re-scores (five of the six are under no lock). | evidence row 9 |
| 5 same gap | Heading and text now say "a similar gap, not the same one", citing same-side minus opposite-side -0.04 (-0.10 to +0.02). | evidence row 15 |
| 6 Block 1 | The after-pair ceilings and own-ceiling ratios are added (G7). | RESULTS_3 section 3.1, table and reading. The table's MANC "before" ceiling is corrected from 0.78 to 0.77 (the file has 0.7747), a rounding slip found while checking. HANDOFF section 6; evidence row 23 |
| 7 Block 3 | Size gets its pre-registered verdict (contributes in combination); sign does not. | RESULTS_3 section 3.3; HANDOFF section 6; evidence row 27 |
| 8 fix count | Now reads: "Of the ten variants of fixes 1-8, eight kept the DNg100 control and six were judged on all four criteria". Floors 1 and 3 and fixes 6, 8 and 9 are accounted for. | evidence rows 28-30 |
| 9 scope | Excitatory types whose left and right copies are annotated homologs: 307 of 321 and 219 of 328, 215 in both; Parts B-C use 261 and 203. "Members on both sides" is not used, because MaleCNS has 250 such types, of which 219 are primary. | evidence row 33 |
| 10 model column | The screen score is added to the table, with a note using the reviewer's corrected point (calibration, not the screen's call). The withdrawn scoring bullet is not used. | RESULTS_3 section 6; evidence row 41 |
| 11 decisive | The gap range (0.05-0.28) and what it implies are added. | RESULTS_3 already had it; evidence row 40 |
| 12 lines | Added with the corrected wording ("at least one kit record", "possibly joint activation"). The count and list are generated by script from `kit_v2/driver_lines.csv` and `forward/AVAILABILITY.csv`. SS01556's record with no type names no other type, so it does not count. In the table, each type's type-specific lines are listed first. | RESULTS_3 section 6; evidence row 43 |
| 13 evidence map | Rebuilt with one row per claim of the revised brief (46 rows); "none" marks the claims under no lock. | |
| correction 4 (determinism) | Now reads "every result-bearing campaign". | evidence row 8; HANDOFF section 13 |

Also found while answering:
- **Amendments count.** `AMENDMENTS_v4.jsonl` is committed but hashed by no lock, so the brief no longer gives the number of departures (evidence row 7).
- **Length.** The fixes added about 350 words, and about 270 were cut elsewhere. The brief's prose (without the table) grew from 1,335 to 1,426 words.

## 3. Follow-up: check against the first overclaim review

A final check of the brief against the 15 items of `BRIEF_OVERCLAIM_REVIEW.md` found five of its fixes weakened by the length cuts made
in this round, and restored them:
- item 1: the premise is again a conditional ("if the screen captures function shared by copies built by the same genome");
- item 2: the kinds of departure are named again, without a count, since the amendments file is under no lock;
- item 6: the ratios to the ceiling (0.48 and 0.47) stand beside 0.40 and 0.37 again, with a note that result 2's 0.59 comes from
  another design;
- item 12: "set on another regime";
- item 13: "below chance" and "training on past results".

Also restored or corrected:
- the trust-gate sentence;
- "not distinguishable from 0" for MANC's Block 1 closure;
- "close less" instead of "close little" for the alone-closures (the first review's point that wide intervals are inconclusive, not
  small).

Result 3 now says that the negative-binomial model's dispersion was estimated from homologous connection pairs, so "no fitted
parameter" applies to the Poisson copies only. The fix-9 sentence names the fix. The rewired-driver range in the handoff and the
evidence map (2-20) was checked against `reliability_v2/C.json` (`rewired_drivers.n`). The earlier "4-20" left out fix 1, which
reached 2. A sentence in RESULTS_3 section 3.3 was corrected to "the only classes whose alone-closure intervals exclude 0". The
brief's prose is now 1,514 words, so it runs past the two pages asked for (handoff section 2).

