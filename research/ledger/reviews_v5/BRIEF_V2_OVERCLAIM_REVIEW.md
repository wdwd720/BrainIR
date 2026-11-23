Items: 17

1. **[major] Result 1 footnote: false as worded.**
   - Text: "In the authors' own single-neuron screen, DNg100 and DNb08 are also the only types with a driver copy whose every copy is a driver."
   - Problem: the locked count is restricted to types with copies on both sides. Across the authors' whole single-neuron screen,
     DNit011 and DNit013 (one copy each) also have every copy a driver, and the rulebook itself lists four "authors-concordant types".
     Coming right after the DNit013 asterisk, the sentence implies that DNit013 lacks a property it has. (Post hoc, Part R.)
   - Evidence: `replication_v1/R_replication.json` `A0_copy_concordance.copies_on_both_sides` (`n_types` 308, `n_with_a_driver_copy` 18,
     `concordant_types` DNb08, DNg100); `pertype_v1/A0_copies.csv` rows DNit011 (bodyId 44321, side L, `members_R` 0, `score` 0.777) and
     DNit013 (37139, R, `members_L` 0, 0.677); `PREREG_v5.md` Part Q ("authors-concordant types (every A0 copy >= 0.5): DNg100, DNb08,
     DNit011, DNit013"). The qualifier is kept in `results/RESULTS_4.md` §1 ("among 308 types with copies on both sides") and in
     `paper/CLAIMS.md` row 14 ("among 308").
   - Replacement (118 characters, was 131): "In the authors' single-neuron screen, DNg100 and DNb08 are also the only two-sided types whose every copy is a driver."
     If item 5 is accepted, use its text instead, which includes this fix.

2. **[major] Summary: our screen's hits presented as the published model's (unfair to the authors).**
   - Text: "its hits mostly do not recur: of 11 hits with a confidently matched counterpart, 2 are hits again,"
   - Problem: "its hits" are the published model's, but the 11 are from our own MANC screen B1r (BrainIR's tuner v2, K chosen on DNg100), not
     from the authors' published list A1. The authors' list has 6 confidently matched hits, and the same 2 recur: 0.33 (0.00-0.80), against
     our screen's 0.18. Because the summary says "its hits" and the parenthetical in "What was tested" singles out the MaleCNS screen as
     ours, readers will take the 11 MANC hits, and the table's "MANC" rows, to be the authors'. The error runs against the authors.
   - Evidence: `replication_v1/R_tables.md`, "B1r (our MANC screen) x B2r" ("high: 11 drivers in B1r, 23 in B2r, 2 in both") and "A1 (the
     authors' MANC list) x B2r" ("high: 6 drivers in A1, 23 in B2r, 2 in both"; replication rate 0.33 [0.00, 0.80]), the same in
     `R_replication.json` `A1_x_B2r.high.overlap`; `PREREG_v5.md` Part Q (drivers: B1r 15, A1 11); `gates_v2/PREDICTIONS_v2_NOTES.md`
     (B1r and B2r: tuner v2, K = 1); `gates_v2/CALIBK.json` (`k_chosen` 1, calibrated on DNg100 alone).
   - Replacement (97, was 98): "its hits mostly do not recur: of our MANC screen's 11 confidently matched hits, 2 are hits again,"
     Item 6 fixes the matching sentence in "What was tested". If space is found elsewhere, the fair companion figure is "(authors' list:
     2 of 6)".

3. **[major] What was tested: the pre-registration claim is false for the lead result.**
   - Text: "Every analysis was frozen, hashed and timestamped before the data or simulations it concerned (rulebook v5, tag `ledger-prereg-v5`)."
   - Problem:
     - The claim does not hold for result 1, the brief's headline. Part R's thresholds and categories were chosen after the replication
       pattern, the B1r, B2r and A1 driver lists and the per-type scores had been seen. The brief's own summary calls the result post hoc,
       so this sentence contradicts it.
     - "Rulebook v5" is too narrow. Result 3 and both exams in result 4 fall under rulebooks v1 to v4; only the audit falls under v5.
     - Run 4's gaps had been seen in an earlier run whose seeds Part A reuses.
   - Evidence: `PREREG_v5.md`, "What is confirmatory" ("Part R is descriptive and **post hoc**") and Part Q (replication pattern, per-type
     scores and DNg100's exam 1 label seen before the freeze); `replication_v1/R_replication.json` `label` ("POST HOC (PREREG v5 Part R:
     thresholds and categories chosen after the replication pattern was seen)"); `results/RESULTS_1.md`, Provenance (PREREG.md,
     PREREG_v2.md); `results/RESULTS_2.md` (rulebook v3); `paper/CLAIMS.md` rows 1, 15 and 18 (PREREG v4); `BRIEF.md` lines 11-12 ("both
     gaps had been seen in an earlier run whose MANC seeds Part A reuses").
   - Replacement (130, was 132): "Each analysis was frozen, hashed and timestamped before it ran (rulebooks v1-v5), some after data were seen; result 1 is post hoc."

4. **[major] Result 3 heading and last clause: a cause claimed where only sufficiency in one animal was shown.**
   - Text: "**3. Why matched neurons disagree.**" and "noise of this size is enough to produce the gap."
   - Problem:
     - The pre-registered test shows only that two Poisson copies of MANC agree about as poorly as MANC's left and right copies, in the
       same paired one-sided design. The heading offers this as the reason matched neurons disagree.
     - Elsewhere in the brief "matched" means the cross-animal matches of result 1, which the noise test never touched; cross-animal
       agreement is lower, 0.32-0.50 of the ceiling.
     - "The gap" follows directly on the authors' 0.63, which was measured in another design (item 11).
     - The first brief's caveats are gone: "noise of this size suffices, which does not make the real differences count noise; MANC
       only", and the post-hoc "most of the gap, not demonstrably all".
   - Evidence: `reliability_v2/NOISE.json`:
     - `marking` ("MANC only (pre-floor counts), paired draws, seeds 0..7");
     - `primary_homolog_consistent.poisson.copy_vs_copy.primary.ratio` 0.484 [0.358, 0.602];
     - `primary_homolog_consistent.observed_left_right_paired_design.primary.ratio` 0.469;
     - `primary_homolog_consistent.poisson.reproduces_left_right` true.
     Also `PREREG_v4.md` B4.5 (verdict words "Reproduces the left-right agreement with no fitted parameter"); `results/RESULTS_3.md`
     line 135 ("about 86 % of the gap (0.66-1.14), not demonstrably all"); `paper/CLAIMS.md` rows 4 (across flies 0.32-0.50) and 16
     (post hoc); `BRIEF.md`, result 3 caveat.
   - Replacement: heading "**3. Noise can mimic the side gap.**" (36, was 36); clause "noise of this size can produce such a gap." (42,
     was 48).

5. **[moderate] Result 1 footnote: the copy-level result that favours DNb08 is cited, the one against it is not (post hoc).**
   - Text: "*DNit013's cross-animal match is low confidence. In the authors' own single-neuron screen, DNg100 and DNb08 are also the only types with a driver copy whose every copy is a driver."
   - Problem: the run's own single-copy screen (Part T) found that, stimulated alone in MaleCNS, none of DNb08's four copies is a driver
     (0.00, 0.00, 0.07, 0.48), although its whole type is (0.78). DNit013's single copy is a driver in both animals. On copy-level
     evidence DNb08's replication is the weakest of the three.
   - Evidence: `replication_v1/T_singlecopy.json` `focus.DNb08.MCNS` (`n_driver_copies` 0; copies 0.0, 0.0, 0.066, 0.476) and
     `focus.DNb08.MANC` (`all` true); `concordance.MANC.DNit013` (0.72) and `concordance.MCNS.DNit013` (0.80); `results/RESULTS_4.md` §3.
   - Replacement (177, was 180; includes item 1's fix): "*DNit013's match is low confidence. In the authors' single-neuron screen only DNg100 and DNb08 of two-sided types have every copy a driver; in our MaleCNS runs no DNb08 copy is."

6. **[moderate] What was tested: a reproduction claim broader than the locked checks support, and unclear about whose screen is whose.**
   - Text: "Our screens reimplement the authors' model, which reproduces their published dynamics; MANC is the first animal, MaleCNS the second (the authors' network; the screen of it is ours)."
   - Problem: "reproduces their published dynamics" says more than the ledger's locked checks support. DNg100's dynamics match: the
     full-cord build matches the authors on every per-leg statistic, and the coupling item failed for the authors' own traces too. The
     screens do not match:
     - BrainIR's first type-level screen (B1) against the authors' A1: Spearman 0.792, just under G2's 0.8 investigation threshold,
       with 23 types usable only in theirs;
     - our MANC hit list B1r against theirs: 15 drivers against 11;
     - our single-copy MANC scores against their single-neuron screen: Spearman 0.65.
     Under `research/ledger/` the phrase appears only in this brief and the unlocked preprint, and `paper/CLAIMS.md` has no row for it.
     The parenthetical singles out the MaleCNS screen as ours ("the screen of it is ours"), which invites reading the MANC screen as the
     authors' (item 2).
   - Evidence: `gates/G3_REPORT.md` ("matches the authors on every per-leg statistic"; items 1-3 pass, item 4 fails, and the authors'
     traces fail it too); `results/RESULTS_1.md` ("A1 against its replication B1: Spearman 0.792 over 321 types"); `gates/G2_REPORT.md`;
     `PREREG_v5.md` Part Q (B1r 15, A1 11); `replication_v1/T_singlecopy.json` `manc_single_copy_vs_A0_spearman` 0.654
     (`n_manc_copies_compared` 120); `PREREG.md` §3.8 (B2 runs on the authors' MaleCNS network).
   - Replacement (159, was 181): "Both screens are ours, reimplementing the authors' model (our MANC hit list differs from theirs); MANC is the first animal, MaleCNS (their network) the second."

7. **[moderate] What this does not show: a number about the authors' work with no locked source.**
   - Text: "which they tested across four connectomes;"
   - Problem: "four" may be right, but it breaks rule 1 (every number from a locked file). Under `research/ledger/` it appears only in this
     brief and the unlocked preprint, and `paper/CLAIMS.md` has no row for it. Keep the credit to the authors (X8) and drop the number,
     or lock its source (the paper's locator) as a CLAIMS row.
   - Evidence: a search of `research/ledger/` finds "four connectome" only in `BRIEF_v2.md` and `paper/PREPRINT_v0.md` (lines 29 and 160).
     `paper/CLAIMS.md` has 33 rows and none for this claim.
   - Replacement (37, was 42): "which they tested across connectomes;" If item 12 is accepted, use its text instead, which includes this fix.

8. **[moderate] Summary: "orderable" lines.**
   - Text: "We pre-registered 12 experiments with orderable driver lines,"
   - Problem: no line was ordered or confirmed orderable; each was only listed as available on a public catalogue page. The
     availability note says "Listed is not the same as shippable", and the 14 FlyBank-only rows are "the weakest" (ordering there needs an
     account and was not tried). For two of the 12 types, DNa03 and DNp41, no listed line is clean, so those experiments cannot isolate
     the type.
   - Evidence: `forward_v2/AVAILABILITY_NOTE.md`, Limits; `forward_v2/NOTES.md`; `PREREG_v5.md` F4 ("only `yes` counts as available");
     `forward_v2/SHORTLIST_LINES.csv` (DNa03 SS01592, DNp41 SS67050 and SS82242: `clean` False).
   - Replacement (58, was 61): "We pre-registered 12 experiments with listed driver lines,"

9. **[moderate] Result 4, audit: "blind" and "corrected" overstate.**
   - Text: "A pre-registered audit by fresh blind readers upheld exam 1 (3 errors in 39 types, under the 10 % threshold) and corrected six types that were never in its headline,"
   - Problem:
     - (a) The readers were blind to exam 1, not to the simulations. They could read the dedicated simulation papers, a sighting did not
       exclude a record, and the DNg100 forensic sessions had exam 1's records. Under the heading "Blind exams", "blind" reads as the
       exams' blinding to simulation scores.
     - (b) "Corrected" overstates the erratum. Only DNg100 got a definite new label; DNa01, DNa02, DNg13 and DNg62 became "unclear" and
       MDN "conflicting".
   - Evidence: `PREREG_v5.md` L1 ("sessions may read every source, including the dedicated simulation papers; a sighting does not make a
     record ineligible in this audit"; "this audit's sessions may read everything about the simulations"); `LABEL_AUDIT_v1.md` §1 (F1
     and F2 had "all 28 exam 1 records of DNg100") and §2 ("blind to exam 1"); `labels_audit_v1/ERROR_RATES.json` `errata_exposed`
     (audited: yes 1, unclear 4, conflicting 1).
   - Replacement (161, was 165): "A pre-registered audit by readers blind to exam 1 upheld it (3 errors in 39 types, under the 10 % threshold) with an erratum for six types never in its headline,"

10. **[moderate] Result 4, exam 1: context that bears on the authors' model has been dropped (fairness).**
    - Text: "The simulation ranked types that drive front-leg rhythm in flies no better than chance (AUROC 0.577, 0.417-0.724) and no better than counting two-step synaptic paths (0.669);"
    - Problem: the numbers and the verdict ("the model does not predict") are right. The first brief said the labels were "mostly from
      intact flies"; without that, a test of a nerve-cord-only model reads as a clean failure. Of the 39 types, 33 have an intact best
      preparation, and 21 of the 25 "yes" types rest on one atlas read from figures with no leg tracking. X8 asks for an accurate and
      generous description.
    - Evidence: `results/run2/scorecard.csv`, primary-set `best_preparation` (intact_free 27, intact_tethered 6, headless 6);
      `results/RESULTS_1.md` caveat 1 and secondary table (intact only, 38 types; headless only, 3 types, none "yes"); `BRIEF.md`
      ("mostly from intact flies"); `PREREG_v5.md` X8.
    - Replacement (165, was 174): "The simulation ranked types that drive front-leg rhythm in mostly intact flies no better than chance (AUROC 0.577, 0.417-0.724) or than two-step path counts (0.669);"

11. **[minor] Result 3: the authors' screen design is not stated (fairness).**
    - Text: "In the authors' published screen, a neuron's left and right copies agree at 0.63 of the screen's agreement with itself (0.53-0.72)."
    - Problem: the authors' screen stimulates one neuron and reads out both front legs together, unlike our side-specific design. The
      first brief carried this caveat. Here the 0.63 sits directly before our noise result "in the same design", which invites comparing
      the two as if they were measured alike.
    - Evidence: `reliability_v2/A0.json` `note` ("this screen stimulates one neuron and reads out both front legs together, unlike Part
      A"); `A0.primary_one_member_each_side.primary.ratio` 0.628 [0.531, 0.718]; `BRIEF.md`, result 1 caveat.
    - Replacement (127, was 131): "In the authors' published screen, which reads both legs, left and right copies agree at 0.63 of its self-agreement (0.53-0.72)."

12. **[moderate] What this does not show: the main non-result is missing.**
    - Text: "That a real fly's sides behave differently; that the model is wrong about DNg100's own circuit or the authors' three-neuron rhythm generator, which they tested across four connectomes; anything about other behaviours or models."
    - Problem: the summary pairs replication with the two experimentally supported drivers, but this section never says the work does
      not show that replicated hits are real drivers. That pairing rests on two neurons chosen post hoc, both known in advance. The
      forward test has not been done, and with the available lines it cannot decide replication against the published list. The first
      brief's rules require the brief to say what the work does not show, and the preprint's own list of non-results includes this one.
    - Evidence: `replication_v1/R_tables.md` (selection caveats); `PREREG_v5.md` F5 ("A can only be inconclusive") and F6;
      `forward_v2/README.md` ("experiments it predicts, which have not been done"); `paper/PREPRINT_v0.md`, "What this work does not
      show".
    - Replacement (227, was 227; includes item 7's fix): "That replicated hits are real; that a real fly's sides behave differently; that the model errs on DNg100's circuit or the authors' three-neuron rhythm generator, which they tested across connectomes; other behaviours or models."

13. **[minor] Summary: one of the four pre-registered selection caveats is missing.**
    - Text: "(**post hoc**: the pattern was seen before the rule that describes it; DNg100 is the neuron the model was calibrated on, the authors chose DNb08, and two neurons are a tiny sample)."
    - Problem: R2.6 requires the claim about the two confirmed drivers to carry four selection caveats beside it. The brief gives three
      and omits "both are exposed types": both model scores and real-fly outcomes had been seen before the exams, so neither was a blind
      test.
    - Evidence: `PREREG_v5.md` R2.6; `replication_v1/R_tables.md` last line ("Both are exposed types."); `RUN1_PROMPT.md` "Exposed list"
      ("already had both their model score and their real-fly outcome seen").
    - Replacement (168, was 181): "(**post hoc**: the pattern was seen before its rule; the model was calibrated on DNg100, the authors chose DNb08, both were known in advance, and two is a tiny sample)."

14. **[minor] Result 4, exam 2: "identified", and a different statistic printed beside an AUROC.**
    - Text: "it identified activated hemilineages better than chance (0.633) but no better than counting (0.638)."
    - Problem: 0.633 is a mean percentile rank, not an AUROC like the 0.577 printed just before it. The model never named the activated
      hemilineage: top-1 was 0 of 27, and top-3 was at chance. The verdict text does say "identify", but `RESULTS_2.md` caveat 3 says "It
      never names the right hemilineage".
    - Evidence: `results/RESULTS_2.md`, headline table (mean percentile rank 0.633 [0.533, 0.724]; top-1 0 of 27; top-3 2 of 27 against
      chance 0.068) and caveat 3.
    - Replacement (98, was 100): "it ranked activated hemilineages above chance (percentile 0.633), no better than counting (0.638)."

15. **[minor] Result 3: "No pre-registered fix closed it."**
    - Text: "No pre-registered fix closed it."
    - Problem: not every fix was run. Fix 3b produced no results, and fix 9 (combined) was not run. The fixes were judged on
      cross-animal agreement; left-right agreement was not a required criterion, so "it" (the left-right gap in this paragraph) is not
      what they were tested against.
    - Evidence: `reliability_v2/C.json` `passing` []; `primary["3b"].note` ("not evaluated: cx-3b-run4: no results collected");
      `primary["9"].note` ("not run (C3 ...)"); `primary.unfixed.left_right.required` false; `BRIEF.md` ("fix 9 (combined) was not run").
    - Replacement (23, was 32): "No fix that ran passed."

16. **[minor] Decision rule: "can decide" hides the power.**
    - Text: "Replication against counting can decide on up to 10 types (9 right needed); single-connectome against counting on up to 8 (7 right needed)."
    - Problem: even if the right reading is 80 % accurate per type, a decision comes with probability 0.38 for replication against
      counting and 0.50 for single-connectome against counting. With fewer clear outcomes it is lower.
    - Evidence: `forward_v2/DECISION_RULE.json` `comparisons.B_replication_vs_counting` (`max_n` 10, `q` 9, `power_a0.8` 0.376) and
      `comparisons.C_single_connectome_vs_counting` (`max_n` 8, `q` 7, `power_a0.8` 0.503).
    - Replacement (136, was 139): "Replication against counting needs 9 right of up to 10 types, single-connectome 7 of 8 (power 0.38 and 0.50 if a reading is 80 % right)."

17. **[minor] What to test next: the post hoc groups are not named as such.**
    - Text: "R = replication reading, S = single-connectome reading, C = counting reading (yes / no)."
    - Problem: the table's groups are Part R's post hoc categories, and so is the replication reading built on them (near-replicated =
      yes uses the post hoc 0.3 cut-off). The short list was also made after both exams were unblinded. The brief does not say so here.
    - Evidence: `forward_v2/README.md`, first line ("Made after both exams were unblinded and after the replication pattern was seen
      (post hoc categories, PREREG v5 Part R)"); `PREREG_v5.md` F2 and F6.
    - Replacement (88, was 88): "R, S, C = replication (post hoc groups), single-connectome, counting reading (yes / no)."

---

**About this review.** This is an overclaim review of `research/ledger/BRIEF_v2.md` (run 5) by a fresh reviewer. The reviewer worked
read-only and confined to `research/ledger/` and `ledger/`. The reviewed text has sha256
d04bb6525193371ebaf5db329b4186516c3dadc294719d378f27bf25df7a63fb. The rules applied are:
- the first brief's rules as restated in `PREREG_v5.md` Part B: every number from a locked file; say what the work does not show; no
  claim beyond the pre-registered verdicts; post hoc results named as such;
- Part R, including the R2.6 caveats;
- X8, fairness to Pugliese et al.

Severity: **major** means false as written or misattributed; **moderate** means beyond the evidence or unsourced; **minor** means
imprecise or a dropped caveat. Quotes are the brief's text with line breaks joined, each checked by script to occur exactly once.

**Length.** Every replacement is no longer, in characters, than the text it replaces. `ledger/scripts/posthoc/brief_pages_v4.py` (headless
Chrome) prints the brief at 2 pages:
- with each replacement applied alone;
- with all of them applied together (item 5 in place of item 1 and item 12 in place of item 7, since those pairs share text).

Overlaps: items 1 and 5 share a sentence, and items 7 and 12 share a span; if both items of a pair are accepted, use the second's text.

**Checked and found correct (no item).** Every other number in the brief matches its locked field:
- table 1;
- result 2: 16, 12 and 7 of 16 copies; p = 0.114; the rulebook stated in advance that a null is uninformative;
- 0.48 and 0.47;
- exam 1: 0.577, 0.417-0.724 and 0.669; exam 2: 0.638;
- the audit's 3 of 39;
- the forward table's twelve rows: readings, lines listed and clean lines;
- q(10) = 9, q(8) = 7, and the four types on which R and S disagree.

The 0.5 driver threshold is the paper's rule (`PREREG.md` §5). DNg100 and DNb08 have audited headless labels "yes"
(`labels_audit_v1/audited_type_labels.csv`). "As stable as DNit013" was not raised: two non-replicating hits were more stable, so the
phrase understates rather than overclaims.
