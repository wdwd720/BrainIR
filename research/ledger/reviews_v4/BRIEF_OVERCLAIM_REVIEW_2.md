Verdict: 13 items marked

1. **(a, c) The premise paragraph: a simulation offered as evidence about animals.**
   - Quoted: "Real animals can differ between sides and individuals (DNg100 itself drives its legs asymmetrically, in the authors' runs and ours), so a gap is a warning about the screen, not proof of an error."
   - Problem:
     - The parenthetical is offered as an example of real animals differing. Both of its cases are simulations of the same connectome model: the authors' full-cord runs and ours. They show that the model's DNg100 output is asymmetric on this wiring, not that flies are. A reader can take it for an observation in flies. The evidence map has no row for this claim.
     - For the cross-fly comparison the sentence names only biological differences. The two connectomes also differ in reconstruction and annotation, and bridging them took choices:
       - MaleCNS DN sides were re-derived from anatomy.
       - Its neurons carry MANC type names through a curated match.
       - Its matrix is published floored at 5.

       So part of a cross-fly gap can be a dataset difference, which is neither biology nor a flaw of the screen.
   - Evidence:
     - `reliability_v2/A5.json` `dng100_per_leg_asymmetry`: `authors_33195857` has 128 simulated replicates (T1 median L 0.887, R 0.687); `ours_g3_v1` has 64 (T1 0.942, 0.780). PREREG A5 names both as model runs ("the authors' full-cord replicates (run 33195857 ...) and ours (run 1's G3 runs ...)").
     - MaleCNS sides: PREREG Part Q and G3. MaleCNS's DN soma side agrees with the output side for 517 of 858 (60.3 %), so its DN sides are output sides.
     - Type names: G2 (MaleCNS DNs mapped to MANC types); `reliability_v2/WIRING_A4.json` `type_to_type_across_flies.malecns_neurons_with_manc_type` 4,278 of 4,310.
     - Floor: PREREG B4 (MaleCNS floored at 5).
   - Suggested: "Real animals can differ between sides and individuals, and the two connectomes also differ in reconstruction and annotation (MaleCNS DN sides had to be re-derived from anatomy, and its neurons carry MANC types through a match), so a gap is a warning about the screen, not proof of an error. (In simulation, DNg100 itself drives the left and right legs unequally, in the authors' runs and ours; that is the model on this wiring, not an observation in flies.)"

2. **(c) "Frozen before the data existed".**
   - Quoted: "The analyses, thresholds and pass/fail criteria were frozen before the data existed (`PREREG_v4.md`, tag `ledger-prereg-v4`, timestamped in the Bitcoin blockchain)."
   - Problem: this holds for run 4's own simulations, not for everything result 2 rests on. The rulebook's Part Q lists what was seen before the freeze:
     - Run 3 had already measured both gaps.
     - Part A reuses run 3's MANC runs as its seeds 0..3.
     - The share of one-sided connections was seen while testing code.
     - G3's 90 % side threshold was written after MANC's 92.4 % was seen.

     A reader will take result 2's left-right and cross-fly gaps for blind findings. They were known beforehand, and run 4 was designed to explain them. The first overclaim review's item 2 covered the amendments, not this.
   - Evidence:
     - `PREREG_v4.md` Part Q: "left vs right 0.43 (R4: MANC, seeds 0..3)"; "cross-fly 0.37 (whole type, 16 seeds)"; "about half of the homologous connection pairs between matched neurons exist on one side only (the share A4(b) reports)"; "The reliability threshold of G3 (90 %) was written after these numbers were seen".
     - A1: "MANC seeds 0..3 are R4's locked runs, reused".
     - What does hold: the freeze commit badc4d7 (2026-11-21 18:24:32 -08:00) precedes the first run 4 outputs, `reliability_v2/A0.json` (f68a3fa, 18:27:14) and `A.json` (f338e3e, 18:53:51). Part Q also states that no A0 or B0 left-right comparison had been computed, so result 1 is blind.
   - Suggested: "The analyses, thresholds and pass/fail criteria were frozen before any run 4 simulation (`PREREG_v4.md`, ...). Both gaps were known beforehand: run 3 had found left-right 0.43 on MANC seeds 0..3 (runs that Part A reuses) and cross-fly 0.37 (Part Q of the rulebook lists everything seen before the freeze); result 1 had not been computed."

3. **(b, c) A second post-hoc figure, unmarked and outside both locks.**
   - Quoted: "*Caveat:* this shows that noise of this size (a third of the connections change between two copies) suffices, not that the real left-right differences are count noise; MANC only, because MaleCNS is published already floored."
     - Also: "some planned analyses were dropped under the pre-registered budget rule, and the one post-hoc figure below is marked."
     - Also: "`ledger-reliability-v2` (every result above except the six-copy noise figure, which comes from the unlocked adversarial review `reviews_v4/ADVERSARIAL_REVIEW_v4.md`; `LOCK_reliability_v2.json`)".
   - Problem:
     - "A third of the connections" is in no locked file. It comes from the adversarial review's post-hoc wiring check, the same unlocked source as the 86 %. So the brief has two post-hoc figures but marks only one.
     - The tag line wrongly places this figure under `ledger-reliability-v2`. Read literally, it also places the forward-ledger results there, although they belong to the next tag.
     - The 0.35 is the share of connections present in only one of the two copies, after the floor. It is not the share whose count changes: under Poisson resampling, most counts differ between two copies.
   - Evidence:
     - Source of the figure: `reviews_v4/ADVERSARIAL_REVIEW_v4.md` section 2, table row "copy vs copy (6)": share present in one network only 0.35-0.36 (P1-P2 0.349). `ADVERSARIAL_ADDENDUM_v4.md`: "changes about a third of the connections between two copies".
     - Not in any locked file: `reliability_v2/NOISE.json` has no wiring-distance field (its keys are `marking`, `nb_dispersion`, `primary_homolog_consistent`, `secondary_all_analysed_types`). A search of `reliability_v2/`, `gates_v4/`, `results/run4/` and `forward/` finds no such value.
     - Lock status: the review was committed (6b32514) after both locks (d81668b, c3ffcfa), and neither lock's `reviews_v4` list hashes it.
     - The left-right counterpart is locked: `WIRING_A4.json` `single_connections.MANC.share_one_side_only` 0.508.
   - Suggested:
     - Caveat: "...noise of this size suffices (in the adversarial review's post-hoc wiring check, about a third of the connections are present in only one of two copies, against half between left and right), not that ..."
     - Departures sentence: "...and the two post-hoc figures below (both from the adversarial review) are marked."
     - Tag line: "`ledger-reliability-v2` (every result above except the two figures from the unlocked adversarial review and the forward ledger below; `LOCK_reliability_v2.json`)".

4. **(b, c; minor) "Labels were used once".**
   - Quoted: "No experimental label entered the analyses of the screen; labels were used once, to turn scores into probabilities for the forward ledger."
   - Problem:
     - Exam 1's labels were also used in Part D's exploratory re-scores, where six fixes were scored against them: one re-score is under the reliability lock and five came after it. A reader would conclude the fixes were never scored against labels.
     - The first clause is right for Parts A-C, with one exception worth stating: every fix was gated on DNg100's known role as a walking driver, and its gain was chosen on DNg100.
   - Evidence:
     - `results/run4/EXAM1_2.json` (hashed by `LOCK_reliability_v2.json`): `marking` "EXPLORATORY, after unblinding (PREREG v4 Part D)", `n_types` 39, `n_yes` 25, `fixed_model.auroc` 0.503.
     - Five post-lock re-scores: `results/run4_postlock/EXAM1_1.json`, `EXAM1_4.json`, `EXAM1_5a.json`, `EXAM1_5b.json`, `EXAM1_7.json`.
     - Rules: `RUN4_PROMPT.md` hard limits 2-4; PREREG C4.
   - Suggested: "No exam label entered Parts A-C (the fixes' only experimental anchor was DNg100, their positive control); labels were used to turn scores into probabilities for the forward ledger and, exploratorily, to re-score exam 1 for six fixes (`RESULTS_3.md` section 5; nothing here rests on it)."

5. **(a, c) "The same gap in both flies".**
   - Quoted: "**2. Our simulation shows the same gap in both flies, and a larger one for the same side across flies.**"
   - Problem:
     - The brief's own source says the opposite: "it is not the same gap in both flies".
     - The gaps are similar in size, but the two flies' left-right differences are not shared. If they were, same-side cross-fly pairs would agree better than opposite-side pairs, and they do not.
     - "The same gap" reads as the same left-right difference, for example one side behaving differently in both flies.
   - Evidence:
     - `reliability_v2/A.json` `same_side_minus_opposite_side_cross_fly`: same 0.316, opposite 0.357, `difference` -0.040, `ci95` [-0.103, 0.019].
     - `results/RESULTS_3.md` section 2: "The left-right difference is not shared across flies"; "it is not the same gap in both flies".
   - Suggested: "Our simulation shows a gap of similar size in both flies, but not the same one (the flies' left-right differences are not shared: same-side minus opposite-side cross-fly agreement -0.04, -0.10 to +0.02), and a larger gap for the same side across flies."

6. **(c) Block 1: a closure quoted without the after-pair's ceiling, which G7 requires.**
   - Quoted: "Scoring the best of a fixed grid of currents instead of the tuner closes about a third of the gap in MaleCNS (0.36, interval 0.08-0.61) and an amount not distinguishable from 0 in MANC (0.17, -0.07 to 0.38)."
   - Problem:
     - The closures are the pre-registered measure and are quoted correctly. But G7 requires the after-pair's own ceiling beside each closure, and here that ceiling moves.
     - The grid score is less noisy than the tuned score, so its split-half ceiling rises. Part of the rise in agreement is therefore lower seed noise, not the two sides coming together.
     - Against its own ceiling, left-right agreement moves only from 0.58 to 0.65 in MaleCNS and from 0.52 to 0.55 in MANC. The distance to the ceiling shrinks from 0.359 to 0.330 in MaleCNS and does not shrink in MANC (0.372 to 0.380). These distances are my arithmetic from the fields below.
     - Without this caveat, a reader concludes that the tuner's choice of current accounts for a third of MaleCNS's left-right disagreement.
   - Evidence:
     - `reliability_v2/B1_MaleCNS.json` `primary_homolog_consistent.tuner_free.best_in_bounds.closure_vs_tuned`:

       | | rho_x | c | ratio |
       |---|---|---|---|
       | `before` | 0.494 | 0.852 | 0.579 |
       | `after` | 0.624 | 0.953 | 0.654 |

       `closure` 0.363, `closure_interval` [0.079, 0.608].
     - `B1_MANC.json`, same path:

       | | rho_x | c | ratio |
       |---|---|---|---|
       | `before` | 0.403 | 0.775 | 0.520 |
       | `after` | 0.465 | 0.844 | 0.550 |

       `closure` 0.166, `closure_interval` [-0.069, 0.378].
     - `PREREG_v4.md` G7: "the after-pair's own ceiling c(X', Y) is reported beside it".
   - Suggested: append "; the grid score is also less noisy (its ceiling rises from 0.85 to 0.95 in MaleCNS and from 0.77 to 0.84 in MANC), and against its own ceiling left-right agreement rises only from 0.58 to 0.65 (MaleCNS) and from 0.52 to 0.55 (MANC)."

7. **(a) Block 3: size gets the same pre-registered verdict as the weights.**
   - Quoted: "Homologous weights, size and sign alone close less (0.09, 0.03, -0.05) with wide intervals; the weights matter in combination, and the classes interact."
   - Problem:
     - The sentence singles out the weights as mattering in combination and groups size with sign.
     - B3.3's reading rule gives size the same verdict as the weights. Size "contributes": leaving size alone un-mirrored leaves a part of the gap, and that closure's interval stays below 1. Its alone and left-out readings also "disagree". Only sign does not contribute.
     - Size's part is small (mirroring everything but size closes 0.81), but the rule counts it. A reader should not conclude that size does not matter.
     - By B3.3 every class is also "needed", because every left-out hybrid is still a real gap.
     - RESULTS_3 section 3.3 ("size and sign barely matter") has the same problem.
   - Evidence:
     - `reliability_v2/B3_MANC.json` `primary_homolog_consistent.reading`: `per_class["4"]` contributes true, needed true, alone_and_left_out_disagree true; `classes_where_alone_and_left_out_disagree` [1, 4]; `per_class["5"]` contributes false.
     - Left-out closures: `O1.closure` 0.546 [0.332, 0.724]; `O4.closure` 0.812 [0.657, 0.951]; `O5.closure` 0.877 [0.734, 1.005].
     - The same verdicts hold on `secondary_all_analysed_types`. Rule: `PREREG_v4.md` B3.3.
   - Suggested: "Homologous weights, size and sign alone close little (0.09, 0.03, -0.05; every interval includes 0); by the pre-registered reading, weights and size still contribute in combination (mirroring everything except weights closes 0.55 of the gap, everything except size 0.81, both intervals below 1), sign does not, and the classes interact."

8. **(b) The fix count mixes units.**
   - Quoted: "Of the eight pre-registered fixes, six kept the DNg100 control and were judged on all four criteria (a dose sweep instead of the tuner, a pooled read-out, symmetrised weights, two type-pooled variants, consensus annotations); all failed, with the two flies at only 0.31-0.39 of the ceiling against 0.8 required."
   - Problem:
     - Read strictly, the sentence is true: exactly six variants both kept the control and were judged on all four criteria.
     - But "eight" counts fix numbers (1-8) while "six" counts variants:
       - Fixes 3 and 5 have two variants each, and fix 5 supplies two of the six.
       - A ninth pre-registered fix (9, the combination) exists.
     - Read naturally, the sentence says two of eight fixes were not fully judged, and that only six kept the control. In fact:
       - Eight of the ten variants of fixes 1-8 kept the control. Floors 1 and 3 passed it too; floor 3 was dropped for budget after passing.
       - Four variants were not judged on all four criteria (3a, 3b, 6, 8), and fix 9 was not run.
   - Evidence:
     - `PREREG_v4.md` C1-C3 list the fixes and variants.
     - `reliability_v2/C.json` `primary` has 11 entries (1, 2, 3a, 3b, 4, 5a, 5b, 6, 7, 8, 9).
     - `gates_v4/C_GAINS.json` `fixes[*].verdict`: "pass" at gain 1 for 1, 2, 3a, 3b, 4, 5a, 5b and 7; "fails" for 6 and 8.
     - `C.json` notes: `primary["3b"].note` "not evaluated: cx-3b-run4: no results collected"; `primary["9"].note` "not run (C3: ...)".
   - Suggested: "Fixes 1-8 come in ten variants (floors 1 and 3, two type-pooled variants). Eight kept the DNg100 control, and six of these (a dose sweep instead of the tuner, a pooled read-out, symmetrised weights, two type-pooled variants, consensus annotations) were judged on all four criteria; all failed, with the two flies at only 0.31-0.39 of the ceiling against 0.8 required. A lower floor could be tested only on MANC's left-right agreement (floor 1; floor 3 was dropped for budget), input normalisation and the combination of network fixes broke the control, and the combined procedure-plus-network fix (9) was not run."

9. **(b, c) "All descending-neuron types".**
   - Quoted: "It does not show that the two sides of a real fly behave differently, nor that the model is wrong about DNg100's own walking circuit: it tests the model's screen of all descending-neuron types."
   - Problem:
     - The screen covers excitatory DN types only.
     - Every agreement is computed over types with members on both sides. In MaleCNS, 72 of 328 types exist on one side only and drop out; that left-right difference is invisible to the agreement measure.
     - A reader would take the result to cover every DN type and every type's left-right behaviour.
   - Evidence:
     - `PREREG_v4.md` G2 ("excitatory DNs by MANC type") and A0 ("933 excitatory DNs").
     - `reliability_v2/A.json` `type_counts`:
       - MANC: 321 types, 308 matched (8 left-only, 5 right-only), 307 homolog-consistent.
       - MaleCNS: 328 types, 250 matched (49 left-only, 23 right-only), 219 homolog-consistent.
       - 215 types are primary in both flies.
     - Parts B-C: `reliability_v2/ANALYSED_SET_X9.json`, primary 261 (MANC) and 203 (MaleCNS).
   - Suggested: "...it tests the model's screen of excitatory descending-neuron types that have members on both sides (MANC 307 of 321 types; MaleCNS 219 of 328; 215 in both flies)."

10. **(c) The "authors' model" probabilities are not that model's prediction.**
    - Quoted: "The forward ledger (tag `ledger-forward-v1`) gives, for 63 descending-neuron types with a driver line and no clear label yet, the probability of rhythmic front-leg stepping in a decapitated fly from two sources: the authors' model and two-step signed synapse counting (no fix passed, so no third source)." Also the table header "P(rhythmic): authors' model".
    - Problem:
      - For 9 of the 15 decisive types, the authors' screen gives a score of exactly 0: no rhythm. The fit maps that 0 to 0.59, near the base rate of 0.64. None of the 15 is a driver in that screen.
      - An experimenter reading "authors' model 0.59" would conclude that the published model leans towards rhythm for DNg32, DNp34 and the rest. In fact it predicts none; the 0.59 mostly restates the training labels' base rate.
      - This also affects the scoring: a "no" result for such a type counts against the "authors' model", although its screen predicted exactly that.
    - Evidence:
      - `forward/LEDGER.csv`, rows with `source` = authors_model: DNg32, DNp34, DNp45, DNp35, DNad006, DNg91, DNp31, DNg78 and DNp15 each have `score` 0.0, `percentile_rank` 0.209 and `p_rhythmic` 0.589.
      - The highest score among the 15 is DNp56's 0.130 (p 0.761). The driver threshold is 0.5 (PREREG G5).
      - 27 of the 63 authors_model rows sit at 0.589; the range is 0.589-0.805.
      - `forward/CALIBRATION.json` `sources.authors_model.fit`: a 0.074, b 1.367, fitted on the percentile rank; `base_rate` 0.641.
    - Suggested: add under the table: "The authors' model column is its screen score passed through the fit: the screen gives 9 of these 15 types a score of 0 (no rhythm), which the fit maps to 0.59, near the base rate (0.64); none of the 15 is a driver in the screen (highest score 0.13)."

11. **(c) "Decisive" without the size of the disagreement.**
    - Quoted: "## The decisive experiments, and the ask", read with "Each source will be scored by its Brier score against a base-rate guesser."
    - Problem:
      - "Decisive" is the rulebook's name for the 15 types on which the sources disagree most (E6).
      - The brief leaves out how small that disagreement is: the two probabilities differ by 0.05-0.28, and by at most 0.09 in the last five rows. The evidence map's own caveat for this row says so, and RESULTS_3 section 6 states it too.
      - A reader would expect each experiment to decide between the sources. A single outcome barely separates 0.59 from 0.54.
    - Evidence:
      - `forward/DECISIVE.csv` `gap`: from 0.280 (DNg43) down to 0.049 (DNp15); the last five rows are 0.091, 0.064, 0.058, 0.051 and 0.049.
      - `EVIDENCE_MAP.md` row 23 caveat: "the sources differ by 0.05-0.28 only".
      - Also `results/RESULTS_3.md` section 6 and `PREREG_v4.md` E6.
    - Suggested: after the table, "These are the 15 types on which the two sources disagree most (the rulebook's 'decisive experiments'), but they differ by only 0.05-0.28 in probability, so one experiment per type separates them weakly."

12. **(c) "The ask" without line specificity.**
    - Quoted: "**The ask.** Express CsChrimson under these lines (LexAop-CsChrimson for a LexA line), decapitate, feed all-trans-retinal, give 1-s light pulses, and score rhythmic front-leg stepping blind to genotype."
    - Problem:
      - In the kit's own map, 7 of the 34 lines listed as available also label another DN type. Six of them are named in the table, and DNg91's two such lines also carry "ambiguous" rows.
      - A positive result with such a line cannot be credited to the listed type alone. For DNg91, two of the three listed lines do not isolate the type; for DNp15, one of the two does not.
      - The ten-entry check flagged one of these lines (SS01553); the brief does not mention the issue.
    - Evidence: `kit_v2/driver_lines.csv` (hashed by `LOCK_labels_v2.json`), fields `manc_type` and `other_cells`:

      | type | line | also labels |
      |---|---|---|
      | DNp26 | SS01553 | DNp57 |
      | DNp26 | SS01588 | DNg30 (two of its rows give that `manc_type`) |
      | DNp26 | SS82228 | DNg13 |
      | DNg91 | SS58304 | DNg01; also an AMBIGUOUS row |
      | DNg91 | SS95034 | DNg82; also an AMBIGUOUS row |
      | DNg78 | SS88264 | DNg14 |
      | DNp15 | SS12653 | DNp19 |

      `forward/AVAILABILITY.csv` has `listed_available` = yes for all seven. See also `reviews_v4/FORWARD_TEN_ENTRY_CHECK.md` note 3.
    - Suggested: add "Seven of the available lines also label another DN type (SS01553, SS01588 and SS82228 for DNp26; SS58304 and SS95034 for DNg91; SS88264 for DNg78; SS12653 for DNp15; `kit_v2/driver_lines.csv`): prefer the type-specific lines, and read a positive result from the others as joint activation."

13. **(b; minor) "Every claim here is traced".**
    - Quoted: "every claim here is traced to its file in `EVIDENCE_MAP.md`"
    - Problem: several claims in the brief have no evidence-map row, or a row that names a different field.
    - Evidence: `EVIDENCE_MAP.md` has 26 rows. Gaps:
      - No row for the DNg100 asymmetry (`reliability_v2/A5.json`).
      - No row for the copies' one-third wiring difference, which has no locked source (item 3).
      - Row 1's caveat mentions the cut but names no file (`reliability_v2/ANALYSED_SET.json` `n_analysed` 278; `ANALYSED_SET_X9.json` `n_analysed` 262).
      - Row 8 names only the same-side pairs, not the opposite-side 0.317 and 0.496 (`A.json`).
      - Row 10 names `reproduces_left_right`, not the difference the brief quotes (`NOISE.json` `primary_homolog_consistent.poisson.observed_minus_copy_vs_copy`: -0.029, [-0.162, 0.102]).
    - Suggested: add these rows to `EVIDENCE_MAP.md`, marking the one-third figure as unlocked. Until then: "the brief's claims are traced to their files in `EVIDENCE_MAP.md`, except the DNg100 asymmetry and the copies' wiring difference".

## Checked, not marked

Paths are relative to `research/ledger/`. JSON was read with python3. Every number not listed above matches its source file:

| claim | source value |
|---|---|
| 0.63 (0.53-0.72); 7 and 8 drivers, 1 shared (`A0.json`) | 0.628 [0.531, 0.718] |
| 0.59, 0.64, 0.32-0.41, opposite 0.32 and 0.50 (`A.json`) | 0.587, 0.642, 0.317-0.410, 0.317 and 0.496 |
| 0.71-0.98 (`WIRING_A4.json`) | 0.713-0.980 |
| "about half" | 0.508 and 0.515 |
| "most" with 1-4 synapses | 0.683 |
| 0.40 / 0.48 and 0.37 / 0.47 (`NOISE.json`) | 0.400 / 0.484 and 0.372 / 0.469 |
| -0.03 (-0.16 to +0.10) | -0.029 [-0.162, 0.102] |
| 86 % (0.66-1.14), adversarial review | 0.858 [0.657, 1.139] |
| 0.36 and 0.17 with intervals (`B1_*.json`) | as quoted |
| 19 MANC and 12 MaleCNS real-gap currents | 19 real gap; 12 real gap, 2 inconclusive, 5 not judged |
| 0.23, 0.34, 0.17, 0.21 with intervals (`B2_*.json`) | as quoted |
| 0.29, 0.25, 0.09, 0.03, -0.05 (`B3_MANC.json`) | as quoted |
| 0.31-0.39 (`C.json`) | 0.313-0.392 |
| Brier and AUROC (`CALIBRATION.json`) | 0.248, 0.242, 0.239; 0.334, 0.611 |
| 39 fit types, 21 of 25 | as quoted |
| 63 types (`LEDGER.csv`) | 63 |
| table rows (`DECISIVE.csv`, `AVAILABILITY.csv`) | all 15 match, incl. every "k of n" and the order |
| availability totals | 34 yes, 24 no, 1 not found; 10 FlyBank-only; checked 2026-11-22 |
| 278 to 262 (`ANALYSED_SET*.json`) | 278 and 262 |

Observations that do not meet the marking tests:

- **Departures and gates.**
  - "Seven departures": `AMENDMENTS_v4.jsonl` has seven rows. Three are code fixes made before the affected outputs (rows 1, 5, 6), two are Modal cost settings (2, 7), one is a timeout (3) and one is the X9 cut (4).
  - Trust gates: 100 of 100 identical on GitHub and on Modal.
  - Determinism: stages 1-4 (and stage 5, post-lock) have 20 of 20 identical per campaign, covering every simulation campaign in `results/run4/COMPUTE_v4.json`.
  - Locks: all 202 and 179 files hashed by `LOCK_reliability_v2.json` and `LOCK_forward_v1.json` match. All four relevant `.ots` proofs carry Bitcoin attestations.
- **"About 0.57"**: 0.2267 + 0.3358 = 0.562, which rounds to 0.56. "About" covers it, but 0.56 would be exact.
- **Result 3 heading, "about as much"**: the B4.5 verdict "reproduces" supports it (`NOISE.json` `poisson.reproduces_left_right` true). The six-pair interval (0.66-1.14) includes 1, and the next sentences say "most of the gap, not demonstrably all". "Almost as much" would match RESULTS_3's first line.
- **"The pre-registered test was met (left-right minus copy-copy -0.03, ...)"**: B4.5's test is that 0.372 lies inside the Poisson copy-vs-copy interval [0.291, 0.505], which holds. The parenthetical gives the difference that B4.5 says to read.
- **"The ceilings come from 8-16 random seeds"**: result 1's ceiling comes from the authors' 128 replicates (c 0.951, [0.931, 0.967]), which is more precise. The caveat errs on the safe side.
- **"Counting only slightly better (0.239)"**: `CALIBRATION.json` gives no interval, and the brief already calls the probabilities weak.
- **Figure caption**: the figure plots raw rho_x for the Part C design (seeds 0-7, cut set), so its model left-right point (0.448 against a ceiling of 0.813, ratio 0.55) is not result 2's 0.59 and 0.64. The wiring correlations share the axis, although the text says they are on another scale. The figure's title states the design and the text states the scale caveat, so this is not marked.
- **"Most labelled in intact flies"**: rebuilding run 2's primary set from `labels_v2/type_labels.csv` gives 39 types: 27 intact-free, 6 intact-tethered and 6 headless. This matches `CALIBRATION.json` (`n_fit` 39, `n_yes` 25, `n_headless` 6).
- **Fix verdicts**: "No fix worked", "broke the control" (fixes 6 and 8 fail at every gain) and "every fix fails the agreement criterion" are supported (`C.json` `passing` = []).

Read for this review: `BRIEF.md`; `EVIDENCE_MAP.md`; `results/RESULTS_3.md`; `PREREG_v4.md` (G, Q, A0-A7, B1-B6, C1-C6, D, E, F, X); `AMENDMENTS_v4.jsonl`; `RUN4_PROMPT.md` (hard limits); `reviews_v4/ADVERSARIAL_REVIEW_v4.md` and `ADVERSARIAL_ADDENDUM_v4.md`; `reviews_v4/BRIEF_OVERCLAIM_REVIEW.md`; the JSON under `reliability_v2/`, `gates_v4/`, `results/run4/` and `results/run4_postlock/`; `forward/` (README, notes, CSVs, `CALIBRATION.json`); `kit_v2/driver_lines.csv`; `labels_v2/type_labels.csv`; LOG rows L120-L153. Nothing was edited except this file.
