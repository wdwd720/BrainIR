Verdict: 15 items marked

# Overclaim review of BRIEF.md (run 4)

Fresh reviewer, read-only. I read `BRIEF.md`, `EVIDENCE_MAP.md`, `results/RESULTS_3.md`, `PREREG_v4.md` (G7, B4.5, C6, Part E, Part Q), `AMENDMENTS_v4.jsonl`,
`reviews_v4/ADVERSARIAL_REVIEW_v4.md` and `ADVERSARIAL_ADDENDUM_v4.md`, and opened the JSON files under `reliability_v2/`, `gates_v4/`
and `forward/` with python3. These numbers in the brief match their source files and need no change:

- 0.63 (0.53-0.72) and the 1-of-7 / 1-of-8 drivers (`A0.json`).
- 0.59 and 0.64 left against right, and 0.32-0.41 for the same side across flies (`A.json`).
- The wiring range 0.71-0.98 (`WIRING_A4.json`; minimum 0.713, maximum 0.98).
- The noise pair 0.40 and 0.37 (`NOISE.json`).
- 0.17 and 0.36 for the tuner (`B1_*.json`).
- 0.23 and 0.34 for own outputs and the rest of the network (`B2_MANC.json`).
- 0.29 and 0.25 (`B3_MANC.json`).
- 0.31-0.39 cross-fly (`C.json`: 0.313 to 0.392).
- Brier 0.248, 0.239 and 0.242 (`CALIBRATION.json`).
- All 15 table rows (`DECISIVE.csv`, `AVAILABILITY.csv`), including every "X of N" count.
- 100 of 100 identical in both trust gates.
- Determinism stages 1-4 identical.

The items below are the exceptions.

## Items

**1. (a, c) The premise.**
Quoted: "A neuron's left copy and right copy are built by the same genome and do the same job, so a correct screen must give them the same prediction, and the same in two different flies (the MANC and MaleCNS connectomes)."

Problem: this is stated as a fact. It is an assumption of the test.
- Real left-right and fly-to-fly differences exist.
- Fly-to-fly disagreement also includes differences in reconstruction, annotation and individual wiring.
- RESULTS_3 section 2 reports a strong per-leg asymmetry of DNg100 itself, the same in the authors' runs and ours (median leg scores L/R, T1 0.89/0.69 against 0.94/0.78).
- The brief's later "does not show..." paragraph says the real sides may differ. The premise sentence contradicts it.

Evidence: RESULTS_3 section 2, last bullet; PREREG G-section ("expected agreement").

Suggested: "We treated left-right and fly-to-fly agreement of type scores as a consistency check: if the model captured only shared function, the two should agree about as well as the screen agrees with itself. Real animals may differ, so a gap is a warning about the screen, not proof of an error."

**2. (c) "Frozen before the data existed".**
Quoted: "Every analysis, threshold and pass/fail criterion was written down and frozen before the data existed (`PREREG_v4.md`, ...)."

Problem: the brief leaves out that this is not true of everything it reports, and the reader cannot tell which numbers are pre-registered.
- Seven recorded amendments (`AMENDMENTS_v4.jsonl`): three code fixes, two Modal cost settings, a timeout, and the X9 cut of the random part of the analysed set from 41 to 25 types.
- Block 3 MaleCNS repeats, floors 3 and 10, fix 3b and the Part D screens were dropped under the budget rule.
- The 86 % six-pair figure is post hoc (reviewer's analysis, unlocked).
- PREREG v4 Part D and RESULTS_3 section 5 are exploratory and post-lock (not mentioned in the brief at all).

Evidence: `AMENDMENTS_v4.jsonl` (7 rows; the X9 row: "random part cut from 41 to 25 types"); EVIDENCE_MAP row 1 caveat; RESULTS_3 section 8 caveat 2.

Suggested: add "Seven departures (code fixes, cost settings, and a cut of the analysed set from 41 to 25 types forced by budget) are recorded in `AMENDMENTS_v4.jsonl`; the six-copy noise figure below and the exam re-scores are post hoc and marked as such."

**3. (c) "No experimental label shaped any analysis".**
Problem: the brief itself fits the forward probabilities to exam 1's 39 labels (`CALIBRATION.json`: `fit_set` "all labelled types", `n_fit` 39). Part D (not in the brief) re-scores exams against labels. The claim is true only for Parts A-C and the screen.

Evidence: `forward/CALIBRATION.json`: `n_fit` = 39; PREREG hard limit 4 (labels used once, for Part E probabilities).

Suggested: "No experimental label entered Parts A-C; labels were used once, to turn scores into probabilities for the forward ledger."

**4. (c) The "one driver in seven or eight" figure.**
Quoted: "only about one driver in seven or eight is a driver on both sides."

Problem: this rests on 7 and 8 drivers and exactly one driver shared, with no uncertainty interval. RESULTS_3 gives it as "1 of 7; 1 of 8". The brief hides how small the counts are.

Evidence: `reliability_v2/A0.json` `A0.primary_one_member_each_side.secondary.replication.full`: `n_drivers_a` 7, `n_drivers_b` 8, `n_drivers_both` 1 (a_to_b 0.143, b_to_a 0.125).

Suggested: "of 7 and 8 driver types on the two sides, exactly one is a driver on both."

**5. (a, c) "...while the wiring agrees".**
Quoted: "Our simulation shows the same gap on both sides of both flies, and a larger one between flies, while the wiring agrees." (the later sentence says "Summaries of the wiring itself ... agree at 0.71-0.98").

Problem:
- The 0.71-0.98 figures are Spearman correlations of type-level summaries with a deterministic ceiling of 1. They are not on the same scale as the screen ratio (0.32-0.64). The brief puts them side by side as if they were.
- The headline clause "the wiring agrees" says more than the summaries show. The brief's own third bullet says about half of single connections exist on one side only.
- "A larger one between flies" holds for the same-side pairs the brief quotes. The pair MANC-R vs MaleCNS-L reaches 0.496, above MANC-L vs MaleCNS-L (0.410), and the left-right gap in MANC is 0.587.

Evidence: `WIRING_A4.json` `summaries_S1_S7_full_spearman` (0.713 to 0.98); `single_connections.MANC.share_one_side_only` 0.508 (MaleCNS 0.515); `A.json` MANC-R vs MaleCNS-L ratio 0.4957.

Suggested: "...while type-level summaries of the wiring (not single connections) agree at 0.71-0.98; those correlations are not measured against a seed-noise ceiling and are not on the same scale."

**6. (b, c) Mixed units in result 3.**
Quoted: "Agreement is always measured against a matched ceiling" (methods paragraph) and "agree with each other at **0.40**, almost as poorly as the left and right sides (0.37)".

Problem: 0.40 and 0.37 are raw cross-half rho_x, not ratios to the ceiling. In the same brief, left-right MANC is 0.59 (a ratio). A reader sees 0.59 and 0.37 for the same left-right comparison with no explanation. The two differ because of a different design (paired draws, seeds 0..7, cut analysed set: ratio 0.47) and because one is a ratio and the other a raw correlation. The "always" claim is false for this sentence.

Evidence: `NOISE.json` `primary_homolog_consistent.observed_left_right_paired_design.primary`: `rho_x` 0.3717, `ratio` 0.4693; Poisson copy-vs-copy `rho_x` 0.4003, `ratio` 0.4838; `A.json` MANC left-right `ratio` 0.5866.

Suggested: "agree with each other at 0.40 (a ratio of 0.48 to the ceiling), almost as poorly as the left and right sides in the same paired design (0.37, ratio 0.47; the 0.59 above is from the unpaired 16-seed design)."

**7. (a, c) Result 3: "Noise ... produces most of the gap", and the 86 % sentence.**
Quoted: the heading "Noise in synapse counts produces most of the gap." and "noise reproduces about 86 % of the gap."

Problems:
- (a) "Produces" reads as a cause of the real gap. The test shows only sufficiency: noise of that scale in a copy of the network moves the screen as much. The brief's caveat says so but the heading does not. RESULTS_3's own first line is "Cause found in part".
- (c) The 86 % is a post-hoc figure from the adversarial review, not locked and not pre-registered. The brief does not say that. Its interval (0.66-1.14) includes 1 and the review says that interval is too narrow because it omits between-copy variance.
- (c) The six pairings include two negative-binomial copies (N1, N2), whose dispersion was measured from the left-right pairs. The brief says "Poisson noise" and "no parameter was fitted" and then speaks of "four stored noise copies" without saying two are not Poisson. Only one pair (P1-P2, 0.40) is pure Poisson.
- (c) The pre-registered rule B4.5 ("reproduces") was met as written. The 0.37 sits inside the Poisson copy-vs-copy interval and `reproduces_left_right` is true. The brief omits the difference to read: observed minus Poisson -0.03 (-0.16 to +0.10).

Evidence: `reviews_v4/ADVERSARIAL_REVIEW_v4.md` section 2 ("share of L-R gap 0.858 (0.657 to 1.139)"; copies 0.38-0.54, mean 0.456; "exploratory, post hoc"); ADDENDUM ("not demonstrably all of it ... should be read as too narrow"); `NOISE.json` `poisson.reproduces_left_right` true; EVIDENCE_MAP row 10.

Suggested: "Poisson-scale noise in the raw counts is enough to move the screen about as much as the left-right difference does (0.40 against 0.37 for the pre-registered pair; in a post-hoc reviewer check over all six pairings of two Poisson and two negative-binomial copies, about 86 % of the gap, interval 0.66-1.14, which is too narrow because it ignores variation between copies)."

**8. (a, b) "explains at most about a third".**
Quoted: "Where the current tuner lands explains at most about a third of the gap (MaleCNS 0.36; MANC 0.17, not distinguishable from 0)".

Problem: "at most" is an upper bound, but 0.36 is a point estimate. Its interval is 0.08 to 0.61. The MANC interval is -0.07 to 0.38. The data allow up to about 0.6.

Evidence: `B1_MaleCNS.json` `procedure_share_of_gap`: closure 0.363, interval [0.079, 0.608]; `B1_MANC.json`: 0.166, [-0.069, 0.378].

Suggested: "explains about a third in MaleCNS (0.36, interval 0.08-0.61) and an amount not distinguishable from 0 in MANC (0.17, -0.07 to 0.38)."

**9. (b) "the sides disagree at every fixed current".**
Quoted: "...and the sides disagree at every fixed current."

Problem: this is not true for MaleCNS. Of the 19 fixed currents, 12 give "a real gap". Currents 22.6 and 32 are "inconclusive" (ratio 0.57 and 0.62, intervals reach 1) and the five lowest currents (4 to 16) are "not judged" (c < 0.2 or too few runs in bounds). Only MANC has a real gap at all 19. RESULTS_3 (section 3.1) has the same overstatement ("at every current with enough in-bounds runs (0.34-0.69)").

Evidence: `B1_MaleCNS.json` `matched_current[current].words`: "not judged" x5, "inconclusive" x2 (22.6274, 32), "a real gap" x12; `B1_MANC.json`: "a real gap" x19.

Suggested: "in MANC the sides disagree at all 19 fixed currents; in MaleCNS at the 12 currents where the comparison could be judged and was conclusive (the lowest 7 were not judged or inconclusive)."

**10. (c) "together they close all of it, so the parts interact".**
Quoted: "Mirroring only the stimulated neurons' own outputs closes 0.23 of the MANC gap, only the downstream network 0.34; together they close all of it, so the parts interact."

Problem:
- "Together they close all of it" is true by construction. Mirroring both parts gives the right-side network, so closure 1 is the sanity check (`sanity.ii_full_transplant`), not a finding.
- The 0.23 has an interval that includes 0 (-0.01 to 0.42).
- The brief omits that MaleCNS shows 0.17 and 0.21, both intervals include 0, and "not one place" rests on MANC.

Evidence: `B2_MANC.json` `H_own.closure` 0.227, `H_rest.closure` 0.336; `sanity.ii_full_transplant` (full seed rho 0.9999); EVIDENCE_MAP row 14 caveat.

Suggested: "...(MANC; the first interval includes 0, and MaleCNS gives 0.17 and 0.21, both with intervals that include 0). Mirroring both gives the other side's network, so it closes the gap by construction; that the two parts sum to 0.57 shows they interact."

**11. (a, c) "Mostly small, one-sided connections" and "weights, size and sign matter little on their own".**
Problems:
- The heading says the gap is mostly in these connections. The closures are 0.29 (0.06-0.49) for one-sided connections and 0.25 (0.06-0.42) for neurons without a partner, and the alone-closures sum to 0.61. RESULTS_3 itself says "No single class closes the gap ... the classes interact".
- "Weights ... matter little on their own": closure 0.09 with interval -0.11 to 0.26 is inconclusive, not small. Mirroring everything except weights closes only 0.55 (0.33-0.72), so the weights matter in combination (RESULTS_3: "matter only in combination").
- The bullet does not say the closures are MANC only and rest on MANC's pre-floor counts. The "most with 1-4 synapses" share (68 %) is MANC only. MaleCNS has 52 % one-sided but no pre-floor counts.

Evidence: `B3_MANC.json` `A1` 0.089, `A2` 0.289, `A3` 0.250, `A4` 0.032, `A5` -0.046; `O1` 0.546; `reading.sum_alone` 0.614, `interact` true; `WIRING_A4.json` `single_connections.MANC.share_one_sided_only_because_of_floor` 0.683; MaleCNS has no such field.

Suggested: heading "Partly small one-sided connections and unpartnered neurons (MANC)"; "mirroring one-sided connections alone closes 0.29 and unpartnered neurons 0.25; homologous weights, size and sign alone close less (0.09, 0.03, -0.05) with wide intervals, and weights matter in combination."

**12. (a, b) The fix list and "No fix worked".**
Quoted: "Eight parameter-free fixes, fixed in advance, were tested against four pre-registered criteria (a lower floor, symmetrised or type-pooled weights, input normalisation, consensus annotations, all of these together, a dose sweep instead of the tuner, a pooled read-out). None restores reproducibility: whenever the DNg100 control still works, the two flies agree at only 0.31-0.39 of the ceiling".

Problems:
- Not all fixes met all four criteria. PREREG C2 item 3: fixes 3a and 3b "cannot pass" (MANC only), so criterion 2's cross-fly part and criterion 4 were not evaluable for 3a (`C.json` cross_fly "na"). Floor 3 (3b) was dropped under the budget rule and never tested. Fixes 6 and 8 failed criterion 1 (the DNg100 control) and were not evaluated further. Fix 9 (combined) was not run. So "a lower floor" was tested against two criteria at most, and no lower-floor result can support "no fix works for the flies".
- "All of these together" is wrong. Fix 8 is the network-level fixes 7, 4, 5b and 6 only (floors, dose sweep and pooled read-out are excluded, PREREG C2.8). It failed the control, so no combination of working fixes was tested.
- "Eight" counts fix numbers 1-8, which cover ten variants (3a, 3b, 5a, 5b). Only six (1, 2, 4, 5a, 5b, 7) were fully evaluated.
- The 0.31-0.39 range is over those six only (0.313-0.392).
- The brief does not say that criterion 4's "few" (at most 2 rewired-control drivers) was set on another regime and that the one-sided rewired controls give 4-20. This does not change the verdict, because every fix fails criterion 2.

Evidence: `C.json` `passing` = []; `P["3a"].cross_fly` na; `P["3b"].note`; `P["6"]`, `P["8"]` (control fails); `P["9"]` not run; `gates_v4/C_GAINS.json` fixes 6 and 8 "fails"; `C.json` cross_fly ratios 0.313, 0.333, 0.392, 0.391, 0.378, 0.322; PREREG C2 items 3 and 8, C6.

Suggested: "Of the eight numbered fixes, six (dose sweep, pooled read-out, symmetrised, two type-pooled variants, consensus annotations) kept the DNg100 control and were evaluated against all four criteria; all failed (cross-fly agreement 0.31-0.39 of the ceiling against 0.8 required). A lower floor could be tested only on MANC left-right (floor 1; floor 3 was dropped), input normalisation and the combination of network fixes broke the control, and the combined fix was not run."

**13. (c) The forward calibration is described as better than it is.**
Quoted: "in leave-one-out tests the model is no better than guessing the base rate (Brier 0.248 against 0.242) and counting only slightly better (0.239)."

Problem:
- Omitted: the authors' model's leave-one-out AUROC is 0.33, worse than chance. Its ranking runs against the labels. The brief's table then shows its probabilities (0.59-0.76) beside counting's as if both carried information.
- Omitted: counting's AUROC is 0.61 with a Brier gain of 0.003, within noise.
- Omitted: the fit set is all 39 labelled types of exam 1 (only 6 headless), and 21 of the 25 "yes" labels rest on the intact-fly atlas alone, which gives no "no". Yet the predictions are for decapitated flies.

Evidence: `forward/CALIBRATION.json` `sources.authors_model.auroc_loo` 0.334; `two_step_count.auroc_loo` 0.611; `n_fit` 39; `n_headless` 6; `atlas_caveat`; EVIDENCE_MAP rows 21 and 23.

Suggested: add "The model's leave-one-out AUROC is 0.33 (below chance) and counting's 0.61. The fit set is 39 labelled types, most labelled from the intact fly (21 of 25 'yes' from one atlas), so the probabilities for decapitated flies are extrapolations."

**14. (c) "The ask" and the availability column.**
Quoted: "Express CsChrimson under these lines ..." and the column "driver lines (listed as available)".

Problem:
- Four of the 15 decisive types (DNp34, DNp35, DNg87, DNad006) have 0 listed-available lines, so the stated protocol cannot be run for them as written.
- The ten "yes" rows that rest on FlyBank's status alone (ordering needs an account and was not tried) are the weakest.
- "Available" means "listed by a catalogue's page on one date by one agent", not tested.
- The brief does not say that the VT lines of DNp34 and DNp35 are listed as discarded stocks in VDRC (only hemidriver halves exist).

Evidence: `forward/AVAILABILITY.csv` (34 yes, 24 no, 1 not found); `forward/AVAILABILITY_NOTE.md` ("The ten 'yes' rows that rest on FlyBank's status alone ... are the weakest"; VT lines "deceased"); `forward/DECISIVE.csv`.

Suggested: add "For four of the 15 types no line is listed as available; ten of the 'available' entries rest on a FlyBank status page that was not tested by ordering."

**15. (b) "Where everything is".**
Quoted: "`ledger-reliability-v2` (all results above; `LOCK_reliability_v2.json`)".

Problem: the tag covers results that sit under the reliability lock. It does not cover the post-hoc six-pair 86 % (`reviews_v4/ADVERSARIAL_REVIEW_v4.md`, unlocked; EVIDENCE_MAP row 10 says so), nor the forward numbers (tag `ledger-forward-v1`, which the brief lists separately). "All results above" is therefore false for the 86 %.

Evidence: EVIDENCE_MAP row 10 caveat ("the six-pair figure ... is post hoc, ... (unlocked)"); RESULTS_3 header ("Every number below is read from a file under the reliability lock ... the Part D rows marked post-lock are exploratory and outside both").

Suggested: "`ledger-reliability-v2` (every result above except the six-copy noise figure, which comes from the unlocked adversarial review `reviews_v4/ADVERSARIAL_REVIEW_v4.md`)."

## Checked and left unmarked

- The brief's claim that no fix passed C6 is supported (`C.json` `passing` = []).
- "Two fixes broke the DNg100 control": `C_GAINS.json` fixes 6 and 8 "fails" at every gain. Fixes that passed ran at gain 1, so "parameter-free" holds in practice.
- The 100 of 100 trust gates and determinism stages 1-4 (20 jobs per campaign) match. The brief says "samples of every campaign". Stage 5 is post-lock, which the evidence map notes.
- The scoring rule (Brier against a base-rate guesser, 0.641) matches `forward/README.md`.
