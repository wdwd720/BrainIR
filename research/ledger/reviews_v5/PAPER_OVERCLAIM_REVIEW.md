Items: 47

1. **[moderate] Title.**
   - Quoted: "How far can one connectome be trusted? Left-right, cross-animal and blind experimental tests of a simulated walking screen in *Drosophila*"
   - Overclaim: "blind experimental tests" reads as new, blinded experiments. In fact both exams scored frozen predictions against labels read from published papers, and no experiment was run. "Can one connectome be trusted" also places the doubt on the wiring. The wiring summaries agree well across sides and connectomes; what proved fragile is one model's thresholded hit list.
   - Evidence: `results/RESULTS_1.md` caveat 3 ("Front-leg rhythm is read from the literature, not measured"); `LABEL_AUDIT_v1.md` section 7; `reliability_v2/WIRING_A4.json` `summaries_S1_S7_full_spearman` (0.71-0.98; CLAIMS row 6).
   - Replacement: "How far can a simulation of one connectome be trusted? Left-right, cross-animal and blind literature tests of a walking screen in *Drosophila*" (+2 words)

2. **[moderate] Title option (2).**
   - Quoted: "A connectome activation screen replicates across animals mainly for its experimentally supported hits."
   - Overclaim: it states a post hoc result without "post hoc" and generalises from one model to "a connectome activation screen". "Across animals" here means two simulated connectomes. It rests on n = 2, and one of the two is the neuron our tuner was calibrated on. It also ignores DNa07, an A1 hit with literature support for front-leg rhythm, which does not replicate.
   - Evidence: `replication_v1/R_replication.json` `label` ("POST HOC ...") and `B1r_x_B2r.high.categories.replicated`; `replication_v1/R_tables.md` selection caveats ("the tuner's K was chosen on it"); `pertype_v1/A1.csv` DNa07 0.84 and `pertype_v1/B2r.csv` DNa07 0.42; `labels_audit_v1/audited_type_labels.csv` DNa07 `front_intact` = yes.
   - Replacement: "In one model's activation screen, the two experimentally supported hits replicate across two connectomes (post hoc)." (+3)

3. **[moderate] Title option (3).**
   - Quoted: "Synapse-count noise limits what a single-connectome activation screen can predict."
   - Overclaim: it draws a causal claim from a sufficiency result. Count noise was shown to reproduce most of the left-right gap, in MANC only. It was never linked to predictive accuracy, and stability under noise was not shown to predict replication.
   - Evidence: `reliability_v2/NOISE.json` `primary_homolog_consistent.poisson.reproduces_left_right`; `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md` ("count noise reproduces most of the gap"); `replication_v1/S_tests.json` `verdict_words` = "not shown"; the paper's own Limitations ("does not identify the gap's cause").
   - Replacement: "Poisson-scale synapse-count noise reproduces most of a simulated screen's left-right gap." (+1)

4. **[minor] Status line.**
   - Quoted: "Every number comes from a file frozen by a lock (git tag, SHA-256, OpenTimestamps); `CLAIMS.md` lists each claim with its file, field, tag and status."
   - Overclaim: three parts of this do not hold.
     - The exam results (CLAIMS rows 25-27) are frozen by a tagged commit plus an OpenTimestamps proof, not by a lock file.
     - Row 16 rests on a reviewer addendum that is under no lock.
     - Several printed claims have no CLAIMS row: the A0 band kappa 0.47 (Results 1); A1's "2 of its 6" (Results 2); the Part T single-copy results (Results 3); "reproduced the authors' published dynamics" and "identical to the authors' network" (Results 2, Methods, Limitations); and "a rule fixed before the replication analysis" (Methods).
   - Evidence: `paper/CLAIMS.md` rows 16 and 25-27; `results/RESULTS_3.md` preamble (the six-pair noise figures are "under no lock").
   - Replacement: "Every number comes from a file frozen by a lock (git tag, SHA-256, OpenTimestamps) or, for the exam results, by a tagged and timestamped commit; `CLAIMS.md` lists each claim with its file, field, tag and status." (+11). Also add the missing CLAIMS rows.

5. **[minor] Abstract, sentence 1.**
   - Quoted: "Connectome-constrained simulations are increasingly used to choose which neurons to test."
   - Overclaim: a claim about a trend in the field, with no source in the ledger, no citation and no CLAIMS row.
   - Evidence: `paper/CLAIMS.md` (no row); `PREREG_v5.md` Part P ("no claim beyond the pre-registered verdicts").
   - Replacement: "Connectome-constrained simulations can suggest which neurons to test." (-3)

6. **[major] Abstract, sentence 4.**
   - Quoted: "Re-run on a second animal's connectome, hit lists barely overlap: of 11 hits with a confidently matched counterpart, 2 are hits in the second animal, and those two are the paper's experimentally supported drivers, DNg100 and DNb08 (post hoc)."
   - Overclaim: the sentence follows "the published rate-model screen", so "Re-run" reads as the authors' screen run again.
     - The 11 hits and the second-animal hits both come from our reimplementation (B1r, B2r). The authors' own list gives 2 of 6.
     - It omits that DNg100 is the neuron our tuner was calibrated on. That makes the match with "experimentally supported drivers" weak evidence for replication as a filter.
     - "In the second animal" means in a simulation of a second connectome.
   - Evidence: `replication_v1/R_replication.json` `B1r_x_B2r.high.overlap.{n_drivers_x,n_both}` (11, 2) and `A1_x_B2r` (2 of 6, `results/RESULTS_4.md` section 1); `replication_v1/R_tables.md` ("the tuner's K was chosen on it").
   - Replacement: "With our reimplementation, hit lists from two animals' connectomes barely overlap (post hoc): of 11 confidently matched hits in the first, 2 are hits in the second, the paper's experimentally supported drivers DNg100 (our calibration neuron) and DNb08." (-1)

7. **[major] Abstract, sentence 5.**
   - Quoted: "Poisson-scale noise in synapse counts alone reproduces a left-right gap of the observed size."
   - Overclaim: this rests on the single pre-registered pair of noise copies, which the adversarial review showed to be a low draw.
     - Pooled over all six pairings, noise reproduces most of the gap, "not demonstrably all".
     - The project accepted that review and replaced "enough to produce the gap" with "produces most of the gap".
     - The result holds in MANC only, because raw counts exist only for MANC.
   - Evidence: `reliability_v2/NOISE.json` `primary_homolog_consistent.poisson.copy_vs_copy.primary.ratio` 0.484 against `observed_left_right_paired_design.primary.ratio` 0.469 (one pair); `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md` (objection accepted; change 2); `results/RESULTS_3.md` section 3.4 ("The raw synapse counts exist for MANC only").
   - Replacement: "In the first connectome, Poisson-scale noise in synapse counts reproduces most of the left-right gap." (+1)

8. **[moderate; fairness] Abstract, sentence 7.**
   - Quoted: "In two blind exams against published experiments, the screen did no better than counting two-step synaptic paths; an audit of the exam labels upheld them, apart from an erratum for six excluded types, DNg100 among them."
   - Overclaim: two problems.
     - Exam 2 did not test the screen the abstract named. It ran the authors' full-cord model with our tuner (L14) on hemilineage activation, in an exam the ledger designed. Crediting that result to their published screen is unfair to them.
     - The audit covered exam 1's descending-neuron labels only. Exam 2's hemilineage labels were not audited.
   - Evidence: `results/RESULTS_2.md` headline table ("H-M: the authors' full-cord model, L14 procedure"); `LOG.md` L14; `RUN3_PROMPT.md` section 2; `LABEL_AUDIT_v1.md` section 2 ("Audited types: 73", all of them descending-neuron types).
   - Replacement: "In two blind exams against published experiments, the model did no better than counting two-step synaptic paths; an audit of exam 1's labels upheld them, apart from an erratum for six excluded types, DNg100 among them." (+0). If items 5-8 are all adopted, the abstract goes from 196 to 193 words.

9. **[moderate] Introduction, paragraph 2.**
   - Quoted: "A hit should be robust to differences the genome does not specify: a neuron's left and right copies are built by the same program."
   - Overclaim: it states an assumption of the test as a biological fact: that left-right differences are unspecified noise. The paper itself says it did not show this. The brief once made the same claim; a review flagged it, and the brief was changed back to a conditional. The paper returns to the unconditional form.
   - Evidence: `reviews_v4/BRIEF_OVERCLAIM_REVIEW.md` item 1; `reviews_v4/BRIEF_OVERCLAIM_ADDENDUM_2.md` section 3 ("the premise is again a conditional"); the paper's Results 4 and Limitations ("does not identify the gap's cause").
   - Replacement: "If the screen captures function shared by a neuron's left and right copies, which are built by the same program, a hit should hold on both sides." (+3)

10. **[major] Introduction, paragraph 2.**
    - Quoted: "every analysis and criterion was written and frozen before the data or simulations it concerned"
    - Overclaim: this is false as a description of the study.
      - Part R (the hit-list categories, their thresholds and the high-confidence lead) was written after the replication pattern was seen.
      - "Most of the gap" rests on a reviewer's post hoc analysis.
      - The re-score with audited labels is exploratory.
      - The left-right gap (0.43 on MANC seeds 0..3, which Part A reuses) and the cross-fly gap had been seen before PREREG v4 was frozen.
      - The brief made the same claim; it was flagged twice and corrected.
    - Evidence: `PREREG_v5.md` "What is confirmatory" and Part Q; `PREREG_v4.md` Part Q; `results/RESULTS_3.md` preamble; `labels_audit_v1/RESCORE_exploratory.json`; `reviews_v4/BRIEF_OVERCLAIM_REVIEW.md` item 2, `BRIEF_OVERCLAIM_REVIEW_2.md` item 2, and `BRIEF_OVERCLAIM_ADDENDUM_2.md` item 2 ("Frozen before any simulation of this run").
    - Replacement: "most analyses and criteria were frozen before the data or simulations they concerned, and the rest are marked post hoc or exploratory" (+7)

11. **[moderate] Introduction, paragraph 2.**
    - Quoted: "the labels for two blind exams were collected from the literature by separate readers who never saw a simulation score"
    - Overclaim: exam 1's readers did see simulation scores printed in their sources (the Pugliese papers, the Sapkal preprint). The sighting rule made those records ineligible; DNg100 lost 23 records this way. What the readers never saw was the ledger's predictions.
    - Evidence: `PREREG_v2.md` L4 ("Score sighting ... Records with a sighting are not eligible"); `LABEL_AUDIT_v1.md` section 1(c); `PREREG.md` section 6 ("never see a model score").
    - Replacement: "the labels for two blind exams were collected from the literature by separate readers who never saw our predictions, with records beside a printed simulation score set aside" (+8)

12. **[moderate] Introduction, last sentence.**
    - Quoted: "The aim is to measure how reliable a single-connectome screen is, not to judge the original work, whose two experimentally supported drivers, as shown below, are the hits that replicate."
    - Overclaim: it states a Part R result without "post hoc", although the rules require every such sentence to say so. "Are the hits that replicate" also holds only for confidently matched types: over all matched types, DNit013 replicates too.
    - Evidence: `PREREG_v5.md` Part R ("Every table and sentence of Part R says 'post hoc'") and Part P; `replication_v1/R_replication.json` `B1r_x_B2r.all.categories.replicated` (DNg100, DNb08, DNit013).
    - Replacement: "The aim is to measure how reliable a single-connectome screen is, not to judge the original work, whose two experimentally supported drivers are, post hoc, the hits that replicate among confidently matched types." (+3)

13. **[minor; fairness] Results 1, heading.**
    - Quoted: "Left and right copies disagree in the authors' own published screen"
    - Overclaim: the copies' scores correlate at 0.60 (0.63 of the ceiling), and their bands agree at a kappa of 0.47. That is partial agreement. "Disagree" without qualification reads as a defect in the authors' published work, when the ledger's own measure shows partial agreement.
    - Evidence: `reliability_v2/A0.json` `A0.primary_one_member_each_side.primary.{rho_x,ratio}`; `results/RESULTS_3.md` section 1 (band kappa 0.47).
    - Replacement: "Left and right copies agree only partly in the authors' own published screen" (+2)

14. **[minor] Results 2, heading; Results 3, single copies.**
    - Quoted (a): "Two flies' hit lists barely overlap, though their wiring summaries agree"
    - Quoted (b): "DNg100's copies drive rhythm in both flies"
    - Overclaim: (a) states a Part R (post hoc) result in a heading without "post hoc". Both (a) and (b) call two simulated connectomes "flies", so (b) reads as an observation in living flies.
    - Evidence: `paper/CLAIMS.md` rows 8-11 (status post hoc); `replication_v1/T_singlecopy.json` (a simulation).
    - Replacement (a): "Simulated hit lists of two connectomes barely overlap (post hoc), though their wiring summaries agree" (+4)
    - Replacement (b): "DNg100's copies drive rhythm in both connectomes' simulations" (+1)

15. **[moderate] Results 2; Limitations.**
    - Quoted (a): "We reimplemented the screen, reproduced the authors' published dynamics, and ran it on two male connectomes"
    - Quoted (b): "our reimplementation reproduces the authors' published dynamics, but any procedure is one choice among several"
    - Overclaim: no CLAIMS row and no ledger file supports "reproduced". At the level of the screen, the ledger shows partial agreement:
      - On the same MANC network, our B1r shares 10 of the authors' 11 drivers and adds 5. One of the additions is DNp63, at 0.79 against their 0.00.
      - B1 agrees with A1 at Spearman 0.792, and Part T's single copies agree with A0 at 0.65.
      - Procedure alone changes the hit list on one connectome. Readers need this to judge the cross-fly overlap.
    - Evidence: `pertype_v1/A1.csv` and `pertype_v1/B1r.csv` `score` (driver = score >= 0.5); `results/RESULTS_1.md` ("A1 against its replication B1: Spearman 0.792"); `results/RESULTS_4.md` section 3 (0.65). A reviewer's check, not to be printed unless it is locked: the Spearman correlation of A1 and B1r scores over 321 types is 0.62.
    - Replacement (a): "We reimplemented the screen (on MANC it shares 10 of the authors' 11 hits and adds 5, such as DNp63 at 0.79 against their 0.00) and ran it on two male connectomes" (+16)
    - Replacement (b): "our reimplementation shares 10 of the authors' 11 MANC hits but adds 5, and any procedure is one choice among several" (+6). Add a CLAIMS row for these counts.

16. **[moderate] Results 2.**
    - Quoted: "Stimulating one side of each type and reading the same side (pre-registered), left agreed with right at 0.59 of the ceiling in MANC (0.48-0.68) and 0.64 in MaleCNS (0.53-0.74)."
    - Overclaim: it says "pre-registered" without saying that both gaps had been seen in run 3, before PREREG v4 was frozen, on MANC seeds that Part A reuses. The brief carries this caveat; the paper drops it.
    - Evidence: `PREREG_v4.md` Part Q ("left vs right 0.43 (R4: MANC, seeds 0..3)"; cross-fly 0.37); `results/RESULTS_3.md` preamble; `reviews_v4/BRIEF_OVERCLAIM_ADDENDUM_2.md` item 2.
    - Replacement: "Stimulating one side of each type and reading the same side (pre-registered, though run 3 had already seen the left-right and cross-fly gaps), left agreed with right at 0.59 of the ceiling in MANC (0.48-0.68) and 0.64 in MaleCNS (0.53-0.74)." (+11)

17. **[moderate] Results 2.**
    - Quoted: "although about half of the homologous neuron-to-neuron connections exist on one side only (51 % in MANC) and 58 % of type-to-type connections in one fly only"
    - Overclaim: "exist on one side only" overstates the asymmetry. 68 % of MANC's one-sided connections do exist on the other side, with 1-4 synapses, and are removed only by the 5-synapse floor.
    - Evidence: `reliability_v2/WIRING_A4.json` `single_connections.MANC.share_one_sided_only_because_of_floor` = 0.683 (`one_sided_absent_partner_raw_1_to_4` 38,545 of 56,421); `results/RESULTS_3.md` section 2 (A4).
    - Replacement: "although about half of the homologous neuron-to-neuron connections pass the 5-synapse floor on one side only (51 % in MANC; 68 % of these have 1-4 synapses on the other side) and 58 % of type-to-type connections appear in one fly only" (+15)

18. **[moderate] Results 2.**
    - Quoted: "The thresholds matter less than the pattern: the authors' own list (A1) gives the same picture (2 of its 6 high-confidence hits replicate)."
    - Overclaim: it claims robustness to the thresholds, but no threshold was varied.
      - A1 uses the same 0.5 / 0.3 / 0.05 cut-offs, so it varies the screen, not the threshold.
      - A1's replication rate (2 of 6, 0.33) is nearly double B1r's (0.18), so "the same picture" also overstates.
      - Near-misses show the threshold matters: DNa07 scores 0.42 and DNxl053 0.46 in B2r, and in A0 DNa13 misses on one copy at 0.459.
    - Evidence: `replication_v1/R_replication.json` (versions `all`, `high`, `high_medium`, `flagged_low_or_medium_match`, `one_fly_only`; no threshold sweep); `results/RESULTS_4.md` section 1 (10 near-replicated types); `pertype_v1/B2r.csv`; `R_replication.json` `A0_copy_concordance.copies_on_both_sides.discordant_types` (DNa13).
    - Replacement: "At the same thresholds, the authors' own list (A1) gives a similar picture (2 of its 6 high-confidence hits replicate); we did not vary the thresholds." (+3)

19. **[major] Results 3; Methods.**
    - Quoted (a): "on a match we rated low confidence before looking"
    - Quoted (b): "(a rule fixed before the replication analysis)"
    - Overclaim: the confidence rule was defined while the per-type tables were being built. By then RUN5_PROMPT had already reported the replication pattern, with DNit013 as one of three hits in both flies. LOG L160 records DNit013's low rating as "seen while doing this". The high-confidence restriction is exactly what makes the replicated set "exactly DNg100 and DNb08".
    - Evidence: `RUN5_PROMPT.md` section 1 ("In both flies: 3 types. DNg100, DNb08 and DNit013"); `LOG.md` L160; `PREREG_v5.md` Part Q (third and fourth bullets).
    - Replacement (a): "on a match rated low confidence by a rule written after the replication pattern was known" (+7)
    - Replacement (b): "(a rule fixed before the replication analysis but after its pattern, DNit013 included, was known)" (+8)

20. **[moderate] Results 3.**
    - Quoted: "In the authors' single-neuron screen, DNg100 and DNb08 are also the only two of 18 types with a driver copy, among 308 types with copies on both sides, in which every copy is a driver."
    - Overclaim: "the only two" depends on how MANC names its types.
      - Every A0 copy is also a driver for DNit011 and DNit013. These are single-neuron MANC types on opposite sides, and MaleCNS names them as one left-right pair (DNpe023). Joined, they would be a third concordant type.
      - DNa13 misses on one copy, at 0.459.
    - Evidence: `PREREG_v5.md` Part Q ("authors-concordant types ...: DNg100, DNb08, DNit011, DNit013"); `LOG.md` L160; `replication_v1/R_replication.json` `A0_copy_concordance.copies_on_both_sides.discordant_types`.
    - Replacement: "In the authors' single-neuron screen, DNg100 and DNb08 are the only two of 308 types with copies on both sides whose every copy is a driver; DNit011 and DNit013, single-copy MANC types that MaleCNS names as one left-right pair, would also qualify if joined." (+9)

21. **[moderate] Results 3.**
    - Quoted: "This is fair to the original paper: its two experimentally supported drivers hold up across animals."
    - Overclaim: "hold up across animals" means only that both remain whole-type hits in our simulation of a second connectome.
      - DNb08's single copies do not drive rhythm in MaleCNS.
      - DNa07, an A1 driver with a literature "yes" for front-leg rhythm, does not replicate.
      - "This is fair to the original paper" is a self-assessment, not a result.
    - Evidence: `replication_v1/T_singlecopy.json` (DNb08's MaleCNS copies score 0.00, 0.00, 0.07 and 0.48); `pertype_v1/A1.csv` DNa07 0.84 and `pertype_v1/B2r.csv` DNa07 0.42; `labels_audit_v1/audited_type_labels.csv` DNa07 `front_intact` yes; `results/RESULTS_1.md` scorecard (DNa07: yes, driver).
    - Replacement: "For the original paper, its two experimentally supported drivers remain whole-type hits in the second connectome; DNa07, an A1 hit with a literature "yes", does not." (+10)

22. **[minor; fairness] Results 3.**
    - Quoted: "DNg100 is the neuron the model was calibrated on and built around"
    - Overclaim: the calibration was ours: the tuner's K was chosen on DNg100. The authors' full-cord runs used a fixed current with no tuning, and no ledger file shows that the authors calibrated their model on DNg100. Coming right after a discussion of the authors' screen, the clause reads as a criticism of their model.
    - Evidence: `replication_v1/R_tables.md` and `PREREG_v5.md` R2.6 ("the tuner's K was chosen on it"); `LOG.md` L14 ("used both DNg100 at 380 each, T = 2 s, no tuning").
    - Replacement: "DNg100 is the neuron our tuner was calibrated on and the authors' model was built around" (+4)

23. **[major] Results 4, heading.**
    - Quoted: "Synapse-count noise is enough to produce the gap; no simple fix closes it"
    - Overclaim: it restores the exact wording the project withdrew after the adversarial review ("'enough to produce the gap' becomes 'produces most of the gap'"), and the result holds for MANC only.
    - Evidence: `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md` "Changes made", item 2; `results/RESULTS_3.md` section 3.4.
    - Replacement: "In MANC, synapse-count noise reproduces most of the gap; no tested fix closes it" (+1)

24. **[moderate] Results 4.**
    - Quoted: "a post-hoc look at all pairings of the stored copies suggests it explains most of the gap, not demonstrably all"
    - Overclaim: "explains" is causal, but the evidence is a matching level of agreement. The next sentence and the Limitations disclaim a causal reading. The addendum also says the pooled interval is too narrow.
    - Evidence: `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md` ("count noise reproduces most of the gap"; its interval "should be read as too narrow"); `paper/CLAIMS.md` row 16 (post hoc, under no lock).
    - Replacement: "a post-hoc look at all six pairings of the stored copies suggests it reproduces most of the gap, not demonstrably all" (+1)

25. **[minor] Results 4; Limitations.**
    - Quoted (a): "It does not show that real left-right differences are counting noise, only that noise of this size is enough."
    - Quoted (b): "Count noise sufficing to produce the gap does not identify the gap's cause."
    - Overclaim: "counting noise" suggests EM reconstruction error, which was not tested; the project replaced the term with "Poisson-scale noise in synapse counts". "Enough" and "sufficing" restore the withdrawn sufficiency claim.
    - Evidence: `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md`, "Other points" point 8, and change 2.
    - Replacement (a): "It does not show that real left-right differences are count noise, only that Poisson-scale noise can produce most of them." (+1)
    - Replacement (b): "Count noise reproducing most of the gap does not identify the gap's cause." (+0)

26. **[moderate] Results 4.**
    - Quoted: "Transplanting the rest of the network from one side into the other closed more of the gap (0.34 of it in MANC) than transplanting a type's own outputs (0.23), and no class of difference closed it alone; the classes interact."
    - Overclaim: "closed more ... than" compares two point estimates whose intervals overlap, and the difference was never tested. In MaleCNS, neither closure is distinguishable from 0.
    - Evidence: `reliability_v2/B2_MANC.json` `primary_homolog_consistent.H_rest.closure.{closure,closure_interval}` 0.336 [0.103, 0.534] and `H_own.closure` 0.227 [-0.013, 0.419]; `results/RESULTS_3.md` section 3.2 (MaleCNS: 0.21, -0.08 to 0.46; and 0.17, -0.13 to 0.40).
    - Replacement: "In MANC, transplanting the rest of the network from one side into the other closed 0.34 of the gap (0.10-0.53) and a type's own outputs 0.23 (-0.01 to 0.42), a difference not tested; no class of difference closed it alone, and the classes interact." (+4)

27. **[minor] Results 4.**
    - Quoted: "Eight pre-registered fixes to the procedure or network (dose sweeps, pooled read-outs, symmetrised or consensus networks, lower synapse floors) were judged on agreement across flies, sides and hits; none passed"
    - Overclaim: it implies "lower synapse floors" were judged. Floor 3 was dropped under the budget rule, and floor 1 could not be judged across flies because there are no pre-floor MaleCNS counts. Criterion 3 is also a driver count, not agreement on hits.
    - Evidence: `results/RESULTS_3.md` section 4 table (3a "not evaluable", 3b "dropped under the budget rule"); `reviews_v4/BRIEF_OVERCLAIM_ADDENDUM_2.md` item 8.
    - Replacement: "Eight pre-registered fixes to the procedure or network (dose sweeps, pooled read-outs, symmetrised or consensus networks, a floor of 1 that could not be judged across flies; a floor of 3 was dropped for budget) were judged on agreement across flies and sides and on driver counts; none passed" (+19)

28. **[moderate] Results 5.**
    - Quoted: "Two sensitivity analyses on the mean score across copies fell below 0.05 (0.035 and 0.033); they were pre-specified without words and are not a result."
    - Overclaim: it reports only the two sensitivity analyses that fell below 0.05. The other two pre-specified ones gave 0.127 and 0.182, and the reference test gave 0.317-0.367, so this selection invites a "nearly significant" reading. Also, analysis (iii) uses the mean fraction rhythmic, not the mean score.
    - Evidence: `replication_v1/S_tests.json` `tests.b1r_drivers.sensitivity_{i,ii,iii,iv}.p` and `reference_v_*.p`; `replication_v1/S_report.md` table.
    - Replacement: "Of four pre-specified sensitivity analyses, the two on mean copy score and mean fraction rhythmic fell below 0.05 (0.035, 0.033) and two did not (0.13, 0.18); none carries words or is a result." (+8)

29. **[moderate] Results 5.**
    - Quoted: "Noise rarely creates hits from nothing: of 40 sampled types that are drivers in neither screen, 7 became drivers in at least one copy (26 of 640 type-copies, mostly types already near the threshold), and none in half the copies."
    - Overclaim: S2 carries no pre-registered words, so "rarely" is an unregistered gloss.
      - 7 of 40 types (95 % interval 7-33 %) is not rare.
      - "Near the threshold" glosses the whole 0.05-0.5 band, which supplied 5 of the 7 types and 22 of the 26 copies.
      - "Neither screen" means neither MANC screen (B1r and A1), not the two flies.
    - Evidence: `PREREG_v5.md` S6 (no words) and S2 (the sampling frame); `replication_v1/S_tests.json` `S2_false_hits` (`types_with_any_driver_copy` 7, `types_with_any_driver_copy_ci95` [0.073, 0.328]; by band 2 of 31 and 5 of 9 types).
    - Replacement: "Noise sometimes creates hits: of 40 sampled types that are drivers in neither MANC screen, 7 (95 % interval 7-33 %) became drivers in at least one copy, 5 of them from the 0.05-0.5 band (26 of 640 type-copies), and none in half the copies." (+5)

30. **[minor] Results 6.**
    - Quoted: "Both exams compared frozen predictions with labels collected blind from the literature, and both included pre-registered wiring baselines"
    - Overclaim: exam 2's blind was only procedural. Its outcomes were public and may be in the models' training, and the author had read the outcomes for about six hemilineages.
    - Evidence: `PREREG_v3.md` Part D.1 ("The blind is therefore procedural").
    - Replacement: "Both exams compared frozen predictions with labels collected blind from the literature (for exam 2 only procedurally: its outcomes were public and partly known to the author), and both included pre-registered wiring baselines" (+15)

31. **[moderate] Results 6, exam 1.**
    - Quoted: "and counting signed two-step paths from the type to the front-leg motor neurons, with no simulation, reached 0.669"
    - Overclaim: it omits three things.
      - This was the best of eight wiring baselines, picked on the same labels. Six of the eight scored 0.09-0.31, ranking the wrong way; unsigned two-step counts scored 0.091.
      - Counting's own interval includes 0.5.
      - The paired difference from A1, -0.091 (-0.320 to 0.150), is not reported.
    - Evidence: `results/RESULTS_1.md` baselines table and "Paired comparison"; `results/run4/EXAM1_2.json` `two_step_signed_S2` (0.669, 0.443-0.871); `results/RESULTS_2.md` ("The best of the eight baselines is picked on these same labels").
    - Replacement: "and the best of eight wiring baselines, picked on these labels, counting signed two-step paths with no simulation, reached 0.669 (0.44-0.87), itself not clearly above chance" (+8)

32. **[moderate; partly fairness] Results 6, exam 2.**
    - Quoted: "Exam 2 asked whether the model identifies which hemilineage was activated from the published movement phenotypes: it did better than chance (mean percentile rank 0.633, 0.533-0.724, p = 0.008) but no better than two-step signed paths (0.638; difference -0.006, -0.172 to 0.166)."
    - Overclaim: "identifies" overstates the result.
      - Top-1 accuracy was 0 of 27 and top-3 was 2 of 27, both at chance.
      - The excitatory hemilineages carry the result (exploratory split).
      - The sentence does not say that "the model" here is the authors' full-cord model run with our tuner, on an exam the ledger designed, not their published screen.
    - Evidence: `results/RESULTS_2.md` headline table (top-1 0.000, top-3 0.074), caveat 3 ("It never names the right hemilineage"), the exploratory class split, and "H-M: the authors' full-cord model, L14 procedure"; `RUN3_PROMPT.md` section 2.
    - Replacement: "Exam 2, our extension of the model, asked whether the authors' full-cord model, run with our tuner, ranks the activated hemilineage high from published movement phenotypes: it did better than chance (mean percentile rank 0.633, 0.533-0.724, p = 0.008), never ranked it first (0 of 27), and did no better than two-step signed paths (0.638; difference -0.006, -0.172 to 0.166)." (+18)

33. **[minor] Results 6.**
    - Quoted: "Exam 2's two source laboratories agree with each other only moderately (kappa 0.24 where both code a cell)."
    - Overclaim: a kappa of 0.24, with chance agreement at 0.72, is weak. The results file calls it "only 0.24" and says "the two labs disagree", as does the paper's own Limitations. "Moderately" overstates how reliable exam 2's labels are.
    - Evidence: `results/RESULTS_2.md` "Ceiling" paragraph and caveat 2.
    - Replacement: "Exam 2's two source laboratories agree with each other poorly (kappa 0.24 where both code a cell), so its ceiling is low." (+4)

34. **[moderate; fairness] Results 6, exam 1 labels.**
    - Quoted: "21 of the 39 types rest on a single intact-fly optogenetic atlas"
    - Overclaim: it omits two caveats that change how exam 1 reads.
      - All 21 atlas types are "yes", and all 14 "no" types come from other papers, so label and source are confounded. In an exploratory check, A1's AUROC on the non-atlas types is 0.357.
      - Most labels describe intact flies, a hard test for a model of the nerve cord alone. The ledger itself chose headless flies for exam 2 and the forward list because they are "headless like the model".
    - Evidence: `results/RESULTS_1.md` caveat 1 and "Exploratory"; `results/RESULTS_1.md` secondary table (headless-only subset: 3 types, 0 yes); `RUN3_PROMPT.md` section 2.
    - Replacement: "21 of the 39 types, all "yes", rest on a single intact-fly optogenetic atlas while every "no" comes from other papers, and most labels describe intact flies, whereas the model is of the nerve cord alone" (+24)

35. **[moderate] Results 6.**
    - Quoted: "types the readers had seen discussed alongside simulation scores were excluded ("exposed")"
    - Overclaim: this misdescribes the rule, and it contradicts the Introduction's claim about blind readers.
      - "Exposed" types are those whose model score and real-fly outcome the ledger's author had already seen or the repository recorded.
      - They also include "exposed by nature" types, whose eligible records all came from dedicated sessions.
      - Scores that readers saw are handled by a different rule: such sightings make individual records ineligible.
    - Evidence: `RUN1_PROMPT.md` "Exposed list"; `LOG.md` L8; `PREREG.md` exposed list (18 MANC types); `PREREG_v2.md` L6 and `labels_v2/exposed_v2.csv`; `PREREG_v2.md` L4.
    - Replacement: "18 types whose model score and fly outcome were already known to the author or the repository were excluded ("exposed")" (+8)

36. **[minor] Results 6.**
    - Quoted: "A pre-registered audit re-read every source with fresh blind readers."
    - Overclaim: the audit re-read exam 1's source cache (64 reader sources plus the atlas), not every source. Nine audited types have no cached source, and the atlas line map was held fixed.
    - Evidence: `LABEL_AUDIT_v1.md` section 2 ("Sources: 64 reader sources ...") and section 7.
    - Replacement: "A pre-registered audit re-read exam 1's cached sources (64 and the atlas) with fresh blind readers." (+6)

37. **[moderate] Results 6.**
    - Quoted: "Across all 39 exam types the audit found 3 errors (7.7 %; sample of 15: 1 error), below the 10 % threshold fixed in advance, and no systematic fault, so exam 1 stands, with an erratum for six exposed types."
    - Overclaim: the point estimate is below 10 %, but its interval reaches 20.9 %.
      - All three errors fall among the 18 types not read from the atlas alone: 3 of 18, or 16.7 % (interval 3.6-41.4 %). Those 18 types hold all 14 "no" labels.
      - The 21 atlas types were re-coded with exam 1's own procedure and line map, so their 0 errors test the coding, not the line map.
    - Evidence: `labels_audit_v1/ERROR_RATES.json` `census_39.all.ci95` [0.016, 0.209], `census_39.atlas_only` (0 of 21), `census_39.other` (3 of 18, `ci95` [0.036, 0.414]); `LABEL_AUDIT_v1.md` sections 2 and 7; `results/RESULTS_1.md` caveat 1.
    - Replacement: "Across all 39 exam types the audit found 3 errors (7.7 %, interval 1.6-20.9 %; sample of 15: 1 error), below the 10 % threshold fixed in advance, all among the 18 types not read from the atlas alone (3 of 18), and no systematic fault, so exam 1 stands, with an erratum for six exposed types." (+17)

38. **[moderate] Results 7.**
    - Quoted: "We locked a forward ledger of experiments that have not been done, built on replication status."
    - Overclaim: it omits the honesty line the rulebook requires: the list was made after both exams were unblinded, and on post hoc categories.
    - Evidence: `PREREG_v5.md` F6; `forward_v2/README.md` and `forward_v2/DECISION_RULE.json` `honesty`.
    - Replacement: "After both exams were unblinded, we locked a forward ledger of experiments that have not been done, built on the post hoc replication categories." (+8)

39. **[major] Discussion, paragraph 1.**
    - Quoted: "A single-connectome activation screen carries a real signal: the model's strongest hit is a known walking command neuron, its novel prediction was confirmed in flies, and both replicate across animals."
    - Overclaim: it generalises from one model to any single-connectome screen, and states a post hoc result without "post hoc".
      - The "signal" rests on two neurons. One of them is the neuron the model was built around and our tuner was calibrated on, so its being the top hit is not independent evidence.
      - DNg100 is the top hit only in the authors' MANC list. It is second in B1r, and in MaleCNS it scores 0.67 while many types score 0.8-0.9.
      - Exam 1 found no signal above chance, and counting matched exam 2's above-chance result.
    - Evidence: `PREREG_v5.md` Part R; `replication_v1/R_tables.md` selection caveats; `pertype_v1/A1.csv` (DNg100 0.90, the top score), `pertype_v1/B1r.csv` (DNa07 0.86, DNg100 0.83), `pertype_v1/B2r.csv` (DNg100 0.67); `results/run2/P.json` `primary.result.auroc` 0.577 (`boot` 0.417-0.724).
    - Replacement: "In this model, post hoc, the screen's two experimentally supported hits, DNg100, around which the model was built, and DNb08, its confirmed prediction, also replicate across two connectomes." (-2)

40. **[moderate] Discussion, paragraph 1.**
    - Quoted: "Copies of a neuron on two sides of one animal disagree; the same type in two animals disagrees more; and resampling synapse counts at Poisson scale moves the screen about as much as the left-right difference does."
    - Overclaim: it reads as a statement about animals, but it concerns simulated scores, as the paper itself says later ("What this work does not show").
      - The cross-animal comparison mixes biology with dataset differences in reconstruction and annotation.
      - The noise result is MANC only, and covers most of the gap, not all of it.
    - Evidence: `reviews_v4/BRIEF_OVERCLAIM_REVIEW_2.md` item 1, accepted in `BRIEF_OVERCLAIM_ADDENDUM_2.md` item 1; `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md`; `results/RESULTS_3.md` section 3.4.
    - Replacement: "In the model, copies of a neuron on two sides of one connectome disagree; the same type in two connectomes, which also differ in reconstruction, disagrees more; and in MANC, Poisson-scale count noise moves the screen nearly as much as the left-right difference does." (+7)

41. **[major] Discussion, paragraph 2.**
    - Quoted: "The fragility we measured sits in which of many weakly driving types cross a threshold, where small differences in wiring move a type from one side of the line to the other."
    - Overclaim: this is an untested mechanism, and the locked tables contradict it.
      - Strong MANC hits with high-confidence matches lose their hit status in MaleCNS. DNp41 scores 0.73 in our MANC screen and 0.65 in the authors', but 0.00 in MaleCNS. DNa07 falls from 0.86 to 0.42.
      - The pre-registered disagreement is measured on the continuous scores of all types, not only near the threshold, and is lower among types with non-zero scores.
      - The cross-fly wiring differences are not small: 58 % of type-to-type connections appear in one fly only.
      - No analysis tested which wiring differences move a type across the line between flies.
    - Evidence: `pertype_v1/B1r.csv`, `pertype_v1/A1.csv` and `pertype_v1/B2r.csv` (`score`, `cross_fly_match` = high); `results/RESULTS_3.md` sections 2 and 7 (G6a); `reliability_v2/WIRING_A4.json` `type_to_type_across_flies.pooled_sides.share_one_side_only`.
    - Replacement: "The fragility is not confined to weak drivers near the threshold: on high-confidence matches, DNp41 (0.73 and 0.65 in the two MANC screens) scores 0.00 in MaleCNS and DNa07 falls from 0.86 to 0.42 (post hoc)." (+4)

42. **[moderate] Discussion, paragraph 3.**
    - Quoted: "For anyone simulating a single connectome, three practices follow."
    - Overclaim: it generalises beyond one rate model, one behaviour and two male connectomes. The paper's own "What this work does not show" rules out other behaviours and models.
    - Evidence: the paper's Limitations, bullets 1-2; Discussion paragraph 4.
    - Replacement: "For anyone simulating a single connectome, our results, from one model and one behaviour, suggest three practices." (+8)

43. **[moderate] Discussion, paragraph 3.**
    - Quoted: "Report its stability under synapse-count noise; our test could not show that stability predicts replication, so it is a cheap screen for fragility, not a substitute for a second connectome."
    - Overclaim: it draws a positive recommendation ("so it is a ... screen") from a null that the rulebook itself calls uninformative. In the data, stability would flag DNb08, a confirmed driver that does replicate, as fragile (0.44). It would pass the non-replicating DNxl133 (0.88) and DNxl102 (0.81).
    - Evidence: `replication_v1/S_tests.json` `verdict_words` "not shown" and `tests.b1r_drivers.primary_stability.p` 0.114; `PREREG_v5.md` S7; `replication_v1/S_report.md` stability table.
    - Replacement: "Stability under synapse-count noise is cheap to report, but our test could not show that it predicts replication, so its value as a screen is unproven; it is no substitute for a second connectome." (+4)

44. **[moderate] Discussion, paragraph 3.**
    - Quoted: "And compare with wiring counts, which in both exams did as well as the simulation."
    - Overclaim: one count did as well: signed two-step paths, the best of eight, picked on the same labels. Most wiring counts did worse: six of eight scored 0.09-0.31 in exam 1, and in exam 2 the others scored 0.42-0.56 against the model's 0.633.
    - Evidence: `results/RESULTS_1.md` baselines table; `results/RESULTS_2.md` "Wiring" table and its note on picking the best baseline.
    - Replacement: "And compare with wiring counts: signed two-step path counts, the best of eight in each exam, did as well as the simulation." (+7)

45. **[moderate] Discussion, paragraph 4.**
    - Quoted: "Whether replication across connectomes picks out real drivers is the question the forward list is built to answer; as designed, it can say whether replication or the single-connectome list beats wiring counts, but not, with the available lines, which of the two is better."
    - Overclaim: the short list contains no replicated type. Its four replication-"yes" types are all near-replicated, so it cannot answer whether replication picks out real drivers. "Can say" also ignores the power: 0.38-0.81, and only if the better reading is right on 80-90 % of types and every listed type gives a clear outcome.
    - Evidence: `forward_v2/SHORTLIST.csv` `category` (4 near-replicated, 5 single-fly hits, 3 stable non-drivers); `forward_v2/DECISION_RULE.json` `comparisons.B_replication_vs_counting` and `C_single_connectome_vs_counting` (`power_a0.8`, `power_a0.9`), and `power_table`.
    - Replacement: "The forward list's replication-yes types are all near-replicated, not replicated; as designed, it can test with modest power (0.38-0.81) whether the replication or single-connectome reading beats wiring counts, but not, with the available lines, which of the two is better." (-4)

46. **[moderate] Limitations.**
    - Quoted: "Two animals, both male; the MaleCNS screen is our run of our reimplementation on the authors' MaleCNS network (the authors published none), and the MANC network is our rebuild (identical to theirs)."
    - Overclaim: it omits a caveat that changes the reading of every cross-animal result. The two connectomes also differ in reconstruction and annotation:
      - MaleCNS is published already floored at 5 synapses.
      - Its descending-neuron sides were re-derived from their outputs.
      - Its neurons carry MANC types by matching.
      - So a cross-animal gap is not only biology. The brief added this caveat after review; the paper drops it.
    - Evidence: `reviews_v4/BRIEF_OVERCLAIM_REVIEW_2.md` item 1 and `BRIEF_OVERCLAIM_ADDENDUM_2.md` item 1; `PREREG_v4.md` Part Q side QA (MaleCNS soma side agrees with output side for 60.3 %); `results/RESULTS_3.md` section 3.4.
    - Replacement: "Two animals, both male, whose connectomes also differ in reconstruction and annotation (MaleCNS is floored at 5, its DN sides were re-derived, its types come by matching); the MaleCNS screen is ours (the authors published none), and the MANC network is our rebuild (identical to theirs)." (+14)

47. **[moderate] Methods, Ledger.**
    - Quoted: "Five runs (19-23 November 2026), each governed by a rulebook frozen before the data or simulations it concerned (PREREG v1-v5)."
    - Overclaim: the sentence hides what had been seen before two of the freezes. PREREG v4 was frozen after run 3 had shown both gaps that Part A measures. PREREG v5 was frozen after the replication pattern, the match-confidence table and the audit report's reference test had been seen. The rulebooks disclose this; the sentence does not.
    - Evidence: `PREREG_v4.md` Part Q; `PREREG_v5.md` Part Q; `PREREG_v3.md` Part D.
    - Replacement: "Five runs (19-23 November 2026), each governed by a rulebook frozen before the simulations it governed (PREREG v1-v5); v3 to v5 disclose what had been seen before each freeze." (+9)

**Overall judgement.** Much of the draft's core is careful. Results 2-3 carry post hoc flags, Part S's null is honestly called "not shown" and uninformative, the re-score with audited labels is marked exploratory, and the authors' pruning result is described generously and accurately. The overclaims cluster in four places:

1. **Framing.** The Introduction and Methods say everything was frozen before the data, and the Discussion opens with a general "real signal". Together they present a post hoc pattern of two neurons, one of them the model's calibration neuron, as a property of single-connectome screens. The mechanism offered for the fragility (weak drivers near a threshold) is contradicted by the locked tables.
2. **Count noise.** The abstract, the Results 4 heading and two sentences restore the "enough to produce the gap" wording the project withdrew after the adversarial review, and they drop "MANC only".
3. **Attribution and provenance.** Results of our reimplementation (B1r and B2r) and of our hemilineage exam are credited to "the screen". The match-confidence rule is said to come before a pattern it in fact followed. The "exposed" rule and the blind readers are misdescribed.
4. **Dropped caveats in the exams and the audit.** Missing are: the best-of-eight baseline, the confound between label and source, audit errors concentrated in the non-atlas types, exam 2's procedural blind, and its 0-of-27 top-1 result.

Several items undo fixes already accepted for the brief: the conditional premise, "frozen before", the dataset differences between the connectomes, and "most of the gap". The treatment of Pugliese et al. is mostly fair. The exceptions are the unqualified "disagree" heading, "the model was calibrated on" DNg100 (it was our tuner), crediting exam 2 to their screen, and not saying that exam 1 tests a nerve-cord model mainly against labels from intact flies.

Conventions: quotes are verbatim from `paper/PREPRINT_v0.md` with line breaks and bold markers removed, and each was checked against the file. Word changes are whitespace counts.

Word budget:

| Count | Draft now | All replacements adopted |
|---|---|---|
| Whole file | 3,725 | about 4,050 |
| From the Introduction on | 3,413 (below the 3,500 minimum on this count) | about 3,724 |
| Abstract | 196 | 193 |

Adopting every replacement keeps the paper within both limits on either count.
