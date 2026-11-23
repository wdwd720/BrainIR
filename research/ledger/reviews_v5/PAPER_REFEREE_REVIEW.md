Objections: 18 (tested: 15)

**1. [Labels] Exam 1's two classes come from different kinds of experiment, so the exam cannot rank the simulation against counting.**
- *Objection.* The two classes come from different experiments:
  - the "yes" class is almost entirely one optogenetic atlas of freely walking, intact flies, coded from figure insets;
  - the "no" class comes from takeoff and flight-tethered assays, and from the consensus rule's tie-breaks.

  An exam whose classes are separated by assay and source measures which rig a descending neuron was studied in. It does not measure
  whether the neuron drives a nerve-cord rhythm. The model has no brain, and 33 of the 39 labels come from intact flies.
- *Strength.* Strong; it stands after testing. The draft concedes the atlas count (21 of 39). It does not concede the make-up of the
  negatives, the tie-breaks' role in them, or how well the source alone predicts the label.
- *Test* (`referee_tests/t2_exam1_labels`, `t7_exam1_negatives_sources`). Exam 1 has 25 "yes" and 14 "no" types.
  - Positives: 23 of the 25 "yes" types have no "yes" record from any source but the atlas (10.7554/elife.34275). Of the 48 atlas "yes"
    records behind them, 47 quote only a line ID. No atlas-only type is a "no".
  - Source alone: the indicator "atlas only" ranks the two classes at AUROC 0.92.
  - Negatives by preparation: 12 of the 14 "no" types take their "no" records from one of two kinds of preparation. Two of these
    types, DNp02 and DNp10, also have an atlas "no" record. The other two "no" types come from 10.1038/s41586-024-07523-9.

    | Kind of preparation | Source and record fields | "No" types |
    |---|---|---|
    | Takeoff recordings | 10.1038/s41586-022-05562-8: "FlyPEZ platform ... 6000 fps"; categories takeoff, posture, no visible effect; the quoted sentences report takeoff rates | 6 |
    | Flight-tethered flies | 10.64898/2025.12.13.693955: "pin-tethered (thorax), flying; only trials with continuous flight analysed"; 10.1038/s41593-019-0413-4: "tethered flight" | 6 |

  - Record categories: the 34 eligible "no" records are 10 landing or extension, 10 takeoff or jump, 8 no visible effect and 6 other.
  - Tie-breaks: the consensus tiers decide 11 of the 14 "no" labels. Without them, 10 would be "conflicting" and 1 "unclear". Ten of
    the 14 "no" types carry at least one eligible "yes" record; DNfl023 has 14 "yes" records against 2 "no".
  - On the 20 types whose label the tiers do not decide, 17 are "yes" and 3 are "no". That is below the exam's own minimum of 5 per
    class (PREREG v1 §7, "underpowered").

  Against the authors: on the 6 types labelled in headless flies, counting scores 0.78 and A1 0.33, but six types decide nothing.
- *Change wanted.*
  - In Results 6 and the abstract, state that exam 1's classes are separated by source and assay: a free-walking atlas against takeoff
    and flight preparations.
  - State that 11 of the 14 negatives are tie-break outcomes over conflicting records.
  - Conclude that exam 1 cannot rank the simulation against counting.
  - In the abstract, remove exam 1 from "no better than counting", or call it uninformative there.

**2. [Statistics] Counting's lead on exam 1 is a size effect, not a better prediction.**
- *Objection.* On exam 1, every unsigned measure of how strongly a type connects to the front-leg network predicts the label backwards.
  Signed two-step counting wins because the large takeoff and landing descending neurons among the negatives have strongly
  net-inhibitory two-step paths. Positive paths do not predict rhythm. The draft's practice advice, "compare with wiring counts, which
  in both exams did as well as the simulation", rests partly on this.
- *Strength.* Strong; it stands.
- *Test* (`t2`, `t5_exam1_size_adjusted`).
  - Unsigned baselines: S3 0.091, S4 0.114, S5 0.093, S6 0.103 (`results/run2/P.json`). Reversed, "fewer two-step paths" scores 0.909.
  - Signed two-step counting (S2): its positive part alone scores 0.503 and its negative part alone 0.709. S2 divided by S3, which
    keeps the net sign and removes size, scores 0.474. Median S2 is -361 for "yes" types and -39,163 for "no" types.
  - Stratified by S3:

    | S3 strata | A1 | S2 | A1 minus S2 (95 % interval) |
    |---|---|---|---|
    | halves | 0.644 | 0.619 | +0.03 (-0.32 to +0.46) |
    | thirds | 0.645 | 0.539 | +0.11 (-0.23 to +0.46) |

    With size removed, the draft's ordering reverses, but nothing is decided.
  - A rank-residual adjustment was tried and dropped. A1's 25 ties at zero are broken by S3, which itself separates the labels.
  - The audited re-score (0.559 against 0.713) shows the same pattern (`RESCORE_exploratory.json`: S3 0.086, S4 0.080, S6 0.074).
- *Change wanted.*
  - Report that counting's AUROC is carried by its negative values, and that unsigned wiring measures predict exam 1 in reverse.
  - For exam 1, replace "did no better than counting two-step synaptic paths" with "cannot separate the simulation from counting".
  - Temper recommendation 3.

**3. [Framing] The draft tests a use the authors disclaimed, and presents the authors' own selection rule and cross-dataset checks as
its findings.**
- *Objection.* The authors wrote that the screen "works as a discovery tool, analogous to a forward genetic screen". They wrote that "it
  likely produced false negatives; therefore, we do not interpret low scores as evidence against a DN's role in rhythm generation". They
  focused on DNg100 and DNb08 "because every DN of these two types produced among the highest rhythmicity scores across all simulation
  replicates". They also simulated DNg100 in four connectomes, and a single DNb08 neuron across "three of the four connectome datasets
  (MANC, FANC, and mCNS)". The draft conflicts with this in three places:
  - the Introduction's premise ("that list is what a laboratory would use to choose its next experiments") contradicts the stated use;
  - Results 3 (copy concordance picks out DNg100 and DNb08, and both hold across animals) and recommendation 1 restate the authors'
    criterion and checks without saying so;
  - exam 1 is decided largely by low scores: 25 of its 39 types score exactly 0 in A1 (15 "yes", 10 "no").
- *Strength.* Strong as framing; it stands. The quotations come from the cached preprint, so the printed wording may differ (see the
  closing notes).
- *Test* (`t10_authors_text_vs_draft`; the scorecard table in `t2`).
  - Every quoted passage is verbatim in the cached preprint.
  - The 25 zero scores are in the locked scorecard.
  - The draft contains none of "discovery", "false negative" or "low score", and does not report the DNb08 cross-dataset result.
- *Change wanted.*
  - In the Introduction, state the authors' disclaimer and selection rule. Say that the ledger tests the screen beyond the use its
    authors made of it.
  - In Results 3, say that the authors chose DNg100 and DNb08 by copy concordance and reported both across datasets. The ledger
    therefore reproduces that check rather than discovering it.
  - In recommendation 1, credit the practice to the authors.
  - In the exam 1 section, say that the exam mostly scores the low scores the authors disclaimed.

**4. [Procedure] The second fly's screen is a MANC-calibrated procedure patched on DNg100. Two of its three replications exist only
under the patch, and it disagrees with the authors' reported mCNS simulation of DNb08.**
- *Objection.* The procedure first registered for MaleCNS (B2) is MANC's tuner, unchanged.
  - Under it, DNg100 scored 0.059, and the only driver shared by the two flies was DNb08.
  - K was then chosen on DNg100 so that DNg100 passes in both flies. MaleCNS passes at 13 of 16 seeds, against a bar of 12.
  - The authors used dataset-specific currents: "Istim = 250 in MANC, 150 in FANC, and 400 in the two CNS datasets".
  - The ledger's single-copy MaleCNS screen finds no DNb08 copy rhythmic. The cached text says: "Activating a single DNb08 neuron in
    the full network simulation consistently produced rhythmic leg motor neuron activity across three of the four connectome datasets
    (MANC, FANC, and mCNS". It gives no mCNS current for DNb08 and does not define "full network". DNb08 currents are given only for
    MANC (65) and FANC (180).

  The MaleCNS screen is therefore not validated beyond DNg100. DNg100 is its calibration target, so DNg100's "replication" is true by
  construction.
- *Strength.* Strong for DNg100's and DNit013's replication, and for what the MaleCNS screen can be said to validate. Weak against the
  overall cross-fly gap, which survives removing the tuner.
- *Test* (`t1_procedure_vs_fly`, `t9_order_of_events`, `t10`; `reliability_v2/C.json`).
  - At K = 0, B1 and B2 share one driver, DNb08, both over all 310 types and over the 215 high-confidence ones.
  - From B2 to B2r, DNg100 goes from 0.059 to 0.674 and DNit013 from 0.204 to 0.802. DNb08 scores 0.784 in both.
  - CALIBK (MaleCNS): 13 of 16 seeds at K = 1, 16 of 16 at K = 2.
  - The ledger's single DNb08 copies in MaleCNS score 0.00, 0.00, 0.07 and 0.48.
  - Against the objection: Part C fix 1 scores each type by its best in-bounds score over a fixed 19-current grid, with no tuner
    (PREREG v4 C1). It leaves cross-fly agreement at 0.313 of the ceiling (0.316 unfixed). This is in Part C's one-sided design on seeds
    0..7, not in the B1r x B2r comparison.
- *Change wanted.*
  - In Results 3 and the abstract, say that DNg100's MaleCNS driver status was set by calibration. PREREG v2 P1 itself calls this
    positive control "tautological by construction".
  - Say that DNit013 is a MaleCNS driver only under that calibration.
  - Report the K = 0 result: one shared driver, DNb08.
  - Say that the ledger's MaleCNS single-copy result does not reproduce the authors' reported mCNS result for a single DNb08 neuron,
    whose current and network the cached text does not state.
  - Describe B2r as "a MANC-calibrated procedure applied to the MaleCNS network".

**5. [Labels] "An audit of the exam labels upheld them": upheld mainly by re-running the same procedure.**
- *Objection.* The audit did not independently test most labels:
  - 21 of the 39 census types were re-coded with exam 1's own atlas prompt, line list and map, so their 0 errors measure test-retest
    agreement;
  - on the 18 types read from papers, the error rate is above the 10 % threshold;
  - a third of the 18 exposed, best-documented types changed;
  - the audit's readers, of the same model family, mostly re-quoted the same sentences.
- *Strength.* Strong against the abstract's word "upheld". It stands, although the pre-registered rule was met as written.
- *Test* (`labels_audit_v1/ERROR_RATES.json`, `comparison_with_exam1.csv`; `t7`).
  - The census rate, 3 of 39, splits into 0 of 21 atlas-only types and 3 of 18 other types: 16.7 % (95 % CI 3.6-41.4 %; strict count
    6 of 18).
  - Exposed types: 6 errata in 18.
  - Of the audit's 63 "no" records for the 14 negatives, 47 quote a sentence that an exam 1 "no" record of the same type had already
    quoted.
  - DNp06's "no" rests, in exam 1 and in the audit, on "Only DNp04, DNp11 and combination line activation increased takeoff rates
    significantly compared to that of controls". The same sentence was overruled for DNp03 and DNp05, two of the three census errors,
    but not for DNp06.
  - Three non-clear audited labels (DNa11, DNg14, DNp13) did not count as errors. In each case a verifier shown exam 1's own quotes
    agreed with exam 1.
- *Change wanted.*
  - In the abstract, replace "upheld them" with the split rates.
  - In Results 6, give the three rates: atlas-only types 0 of 21 (re-coded by the same procedure), other types 3 of 18 (17 %), exposed
    types 6 of 18.
  - Say that the audit re-read largely the same sentences with the same model family.

**6. [Statistics] "Barely overlap" is a property of the 0.5 cut, not of the screen.**
- *Objection.* At 0.5 the overlap is at chance. At 0.3-0.4, 41-50 % of MANC's hits replicate, 2.4-2.7 times the chance expectation, and
  graded scores replicate well above chance. The tables do not show that "the thresholds matter less than the pattern". Because 0.5 is
  the authors' own driver rule, this objection targets the draft's wording, not the cut.
- *Strength.* Moderate; it partly stands. The cross-fly gap is real at every threshold; only its size changes.
- *Test* (`t4_threshold_and_graded`, `t8_replication_subsets`). High-confidence types, B1r against B2r:

  | Threshold | Shared / MANC hits | Expected | Hypergeometric p | Overlap ratio |
  |---|---|---|---|---|
  | 0.3 | 15 of 30 | 6.3 | 0.0001 | 0.56 |
  | 0.4 | 7 of 17 | 2.6 | 0.007 | 0.54 |
  | 0.5 | 2 of 11 | 1.2 | 0.33 | 0.26 |
  | 0.6 | 2 of 8 | 0.7 | 0.16 | 0.16 |

  "Overlap ratio" is the overlap coefficient across flies divided by its within-fly value.
  - On the authors' list at 0.4, 7 of 12 replicate (expected 1.8, p = 0.0005; overlap ratio 0.75).
  - Graded: MaleCNS scores separate MANC drivers from the rest at AUROC 0.71 (0.55-0.84).
  - On matched halves, though, that AUROC is 0.68 across flies against 0.97 within a fly, and top lists of equal size share only 1 of
    11.
- *Change wanted.*
  - In the abstract and Results 2, write "at the paper's 0.5 cut the overlap is at chance; at 0.3-0.4 about half replicate, still about
    half the within-fly overlap".
  - Drop "the thresholds matter less than the pattern".
  - Add the threshold curve and the graded AUROC to Fig. 2 or to a table.

**7. [Statistics] Exam 2: the simulation beat seven of eight wiring baselines. "No better than counting" names the one it tied, which
was picked after unblinding.**
- *Objection.* In exam 2 the simulation is the second-best of nine predictors. It beats three wiring baselines clearly and a fourth
  marginally; the four include the linearised network. It ties only the baseline that was chosen as best on the same labels.
- *Strength.* Moderate; it stands as a framing point. The pre-registered verdict, "does not add value beyond wiring", is correct.
- *Test* (`t3_exam2_baselines`; `results/run3/primary.json`). This is my own paired bootstrap (seed 1), with no multiplicity
  correction.

  | Baseline | Score | Model minus baseline (95 % interval) |
  |---|---|---|
  | membership | 0.420 | +0.21 (0.09 to 0.34) |
  | linearised network | 0.461 | +0.17 (0.04 to 0.30) |
  | three-step unsigned | 0.476 | +0.16 (0.02 to 0.28) |
  | two-step unsigned | 0.497 | +0.14 (0.001 to 0.27) |
  | two-step signed | 0.638 | -0.006 (-0.18 to +0.17) |

  The model scores 0.633; the eight baselines range from 0.420 to 0.638. When the best baseline is re-chosen in every resample,
  two-step signed wins 71 % of the time, and the model trails it by -0.02 (-0.18 to +0.11).
- *Change wanted.*
  - Write "indistinguishable from the best of eight wiring baselines (picked on the same labels), and better than three of them,
    including the linearised network".
  - In the section title and the abstract, do not say "no better than counting" without "the best of eight".

**8. [Framing] The title blames the connectome for what the draft shows is the simulation's sensitivity.**
- *Objection.* By the draft's own numbers, the wiring summaries agree across sides and flies at 0.71-0.98. What disagrees is the
  thresholded output of a nonlinear rate model with a per-replicate tuner. "How far can one connectome be trusted?" invites distrust of
  connectome data, which the draft never tests. It also generalises from one model and one behaviour.
- *Strength.* Moderate; it stands.
- *Test.* None. The objection rests on numbers the draft already reports (`reliability_v2/WIRING_A4.json`).
- *Change wanted.*
  - Retitle around the screen, for example "How reproducible is a connectome activation screen's hit list?".
  - Say in the abstract that wiring summaries replicate and simulated hit calls do not.

**9. [Procedure / framing] DNit013's low-confidence match was not rated "before looking".**
- *Objection.* The draft says DNit013 joins the replicated set "on a match we rated low confidence before looking". The record shows
  the opposite order:
  - RUN5_PROMPT section 1 already lists DNit013 among the three types that drive in both flies;
  - the confidence rule was defined afterwards, while the per-type tables were built (LOG L160), and L160 records seeing DNit013 rated
    low;
  - PREREG v5 Part Q lists the pattern before the rule.

  The headline "exactly DNg100 and DNb08" therefore rests on a rule written with the pattern known.
- *Strength.* Moderate. It is a factual wording error in a paper about post hoc selection, and it stands.
- *Test* (`t9_order_of_events`). The script prints these passages in order.
- *Change wanted.*
  - Write "on a match rated low confidence by a rule defined after the replication pattern was known (LOG L160)".
  - Say that the high-confidence restriction is also post hoc.

**10. [Framing] In Results 1, a type's left and right copies are two neurons, and the ceiling assumes they are one.**
- *Objection.* The ceiling is the seed noise of a single neuron. Left and right copies have different wiring (the draft's own 51 %), so
  a model that reads its wiring should score them differently. The authors listed 29 single neurons above 0.5 as candidates. They
  followed up only the two types "because every DN of these two types produced among the highest rhythmicity scores". Calling this
  "disagree ... a real gap" presents expected individuality as a defect.
- *Strength.* Moderate as framing. The data claim stands.
- *Test* (`t6_A0_left_right`). The gap is not an artefact:
  - the ratio is the same for strongly and weakly connected types (S3 halves 0.57 and 0.58; S1 halves 0.57 and 0.61);
  - removing copies with fewer than 64 usable replicates gives 0.635, with 6 and 7 drivers and 1 shared;
  - only 2 of the 13 one-sided drivers have a rarely accepted other copy: DNa07's right copy (0 of 128 usable) and DNxn167's left copy
    (14 of 128).
- *Change wanted.*
  - Call the reference "the same neuron re-run", and say that the copies are distinct neurons with different wiring.
  - Say that the authors followed up only types whose every copy scored high.
  - Note that the tuner never accepted DNa07's right copy.

**11. [Framing] "About half of the homologous connections exist on one side only" is mostly the model's 5-synapse floor.**
- *Objection.* The phrase reads as a statement about anatomy, but it mostly reflects the floor.
- *Strength.* Moderate, as a matter of accuracy. It stands.
- *Test* (`t11_floor_noise_and_g3`; `WIRING_A4.json`). Of 110,983 homologous pairs:
  - 56,421 (51 %) pass the floor on one side only;
  - of these, 38,545 (68 %) have 1-4 synapses on the other side;
  - 17,876 (16 % of all pairs) have no synapse on the other side.
- *Change wanted.* Write "pass the 5-synapse floor on one side only; 16 % have no synapse at all on the other side".

**12. [Procedure] "Reproduces their published dynamics" needs a qualification.**
- *Objection.* The ledger's own pre-registered comparison with the authors' full-cord traces failed one item, and exam 2's model is
  that full-cord build.
- *Strength.* Weak to moderate. It stands.
- *Test* (`t11`; `gates_v2/G3v2_REPORT.json`).
  - Per-leg rhythm matches the authors': items 1-3 and 5 pass.
  - The coupling comparison fails at the pre-registered alpha of 0.01. For T1R-T2R, R is 0.14 in the ledger's build against 0.60 in
    the authors', p = 0.0035, and the gate records "pass: false".
  - The same report records that the comparison passes under a Bonferroni rule.
- *Change wanted.* In Methods and Results 2, write "reproduces their published front-leg dynamics and per-leg rhythm; in the full cord,
  one of five evaluable inter-leg coupling comparisons differs at the pre-registered alpha (not after Bonferroni correction)".

**13. [Procedure] Poisson resampling with the floor re-applied is a large structural perturbation, not the weight noise of at most 10 %
that the authors tested.**
- *Objection.* Near the floor, resampling deletes and creates connections. That is a different kind of perturbation from proportional
  weight noise.
- *Strength.* Weak; mostly refuted.
- *Test* (`t11`; the preprint's Fig. 2f legend, quoted in `t10`).
  - Deletion probability: 0.44 for a 5-synapse connection, 0.29 for 6 synapses and 0.10 for 8.
  - Creation probability: 0.37 for a 4-synapse connection.
  - The coefficient of variation is 0.45 at 5 synapses, against the authors' noise of at most 10 %.
  - Refuting it: the draft claims only that noise "of this size is enough". Negative-binomial copies, whose dispersion was measured from
    real left-right pairs, gave the same result (`results/RESULTS_3.md` §3.4). DNg100 stays a driver in 16 of 16 Poisson copies
    (`replication_v1/S_report.md`), in line with the authors' robustness result for DNg100.
- *Change wanted.*
  - Say that the perturbation deletes and creates connections near the floor.
  - Say that DNg100's own stability agrees with the authors' noise test.

**14. [Statistics] Part S: an uninformative null takes space in a 200-word abstract, while the graded sensitivity analyses point the
other way.**
- *Objection.* The primary statistic, the fraction of 16 copies at or above 0.5, is coarse and has many ties. Two pre-specified graded
  sensitivity analyses gave p = 0.035 and 0.033. That fits the authors' practice of following up hits that hold across parameter
  configurations.
- *Strength.* Weak. The draft follows its rulebook: the sensitivity analyses carry no words, and only three types replicate.
- *Test.* None. The values are already in `replication_v1/S_tests.json` and in the draft.
- *Change wanted.* Either drop Part S from the abstract, or add a clause saying that two graded sensitivity analyses were nominally
  positive and carry no words.

**15. [Labels] The readers are language models of one family, and the blind is only procedural.**
- *Objection.* The readers and the auditors come from the same model family, and may have read the authors' preprint in training. An
  audit by the same family cannot catch a misreading the family shares, such as coding "no rhythmic front-leg movement" from a sentence
  about takeoff rates.
- *Strength.* Moderate.
- *Test.* None; testing it would need human coders. Objection 5 shows that the audit re-quoted the same sentences.
- *Change wanted.*
  - Say in the abstract that the labels were machine-read from papers.
  - Offer a human-coded subsample.

**16. [Procedure] The read-out: one side only in the ledger's half-fly screens, and different motor-neuron sets in the two flies.
Refuted.**
- *Objection.* The ledger's left-right and cross-fly comparisons stimulate one side and read only that side's front-leg motor neurons.
  The authors' screens read both front legs. The two flies' read-out sets also differ: 144 motor neurons in MANC (72 per side) and 130
  in MaleCNS (67 left, 63 right; PREREG v4 G2). Either difference could manufacture disagreement.
- *Strength.* Weak; refuted.
- *Test* (`t12_readout`; `reliability_v2/A0.json`, `A.json`, `C.json`).
  - With both legs read out, the authors' own screen gives a left-right ratio of 0.628. The ledger's one-sided, same-side read-out
    gives 0.587 in MANC and 0.642 in MaleCNS.
  - Whole-type screens read out on all front-leg motor neurons still agree across flies at only 0.38.
  - Summing the read-out (Part C fix 2) leaves cross-fly agreement at 0.333 (unfixed 0.316) and left-right agreement at 0.541 (0.551).
- *Change wanted.* None beyond giving the two read-out sizes in Methods. The draft already notes the one-sided read-out as a limitation.

**17. [Procedure] "Your reimplementation is not our screen": refuted for MANC.**
- *Objection.* The ledger's MANC screens use its own procedure and tuner, not the authors', so they are not the authors' screen.
- *Strength.* Weak; refuted.
- *Test* (`t1`).
  - Of A1's 11 drivers, 10 are B1r drivers (6 of 6 among high-confidence types).
  - B1r scores pick out A1's drivers at AUROC 0.99. Even at K = 0, 8 of the 11 are shared.
  - Changing the procedure within a fly leaves the hit list largely intact (overlap coefficient 0.67-1.0). Changing the fly does not
    (0.09-0.33).
  - The only weakness: B1r's extra MANC hits include DNg63, with 1 usable replicate of 16, and DNxl121, with 6 of 16.
- *Change wanted.* None for the argument. The draft should report this agreement, which strengthens Results 2, and flag DNg63 and
  DNxl121.

**18. [Procedure] Cross-fly matching, member counts, rarely accepted replicates and unequal list sizes: refuted.**
- *Objection.* The low cross-fly overlap could come from any of four sources:
  - wrong type matches;
  - unequal member counts;
  - replicates the tuner rarely accepted;
  - comparing lists of unequal size.
- *Strength.* Weak; refuted.
- *Test* (`t8`). In every subset below, the replicated set stays DNg100 and DNb08, against about 1 shared type expected by chance:
  - equal member counts (211 types);
  - equal per-side counts (178 types);
  - at least 12 usable replicates in both flies (154 types);
  - all 16 replicates usable (162 types, where DNit013 joins).

  Top lists of equal size share only 1 of 8 to 1 of 11. Three high-confidence MaleCNS hits (DNg21, DNxl067, DNxn143) were never usable
  in MANC and were scored 0 by rule.
- *Change wanted.* Mention the three never-usable types, and that the result is unchanged without them.

## What survives (points I could not rebut)

1. **Left and right copies in the authors' own screen.** In the authors' single-neuron screen, a type's left and right copies get
   different scores (ratio 0.63, interval below 1). Of the 7 left-side and 8 right-side drivers, only DNg100 is a driver on both sides.
   This holds across connectivity splits, usability filters and read-outs (objections 10 and 16). Only its interpretation can be
   contested.
2. **The reimplementation in MANC.** It reproduces the authors' hit list there (10 of 11), so the cross-fly gap is not a
   reimplementation artefact (objection 17).
3. **The cross-fly overlap at the authors' own rule.** At 0.5, the two flies' hit lists overlap at chance (2 of 11, against 1.2
   expected).
   - This holds whatever the match quality, member counts, replicate usability or list sizes (objection 18).
   - It also holds when the tuner is removed: the dose-sweep fix gives 0.31 of the ceiling.
   - With drivers defined at 0.5, graded cross-fly agreement on matched halves (AUROC 0.68) is far below within-fly agreement (0.97).
   - Some gap appears at every threshold from 0.2 to 0.6: the cross-fly overlap is 0.16-0.63 of the within-fly overlap.
   - No pre-registered fix exceeded 0.39 of the ceiling.

   Only the size of the gap, the word "barely", depends on the threshold.
4. **Count noise.** Poisson-scale noise in synapse counts reproduces the left-right gap with no fitted parameter; that test was
   pre-registered and met. Real left-right count differences are about Poisson-sized (the negative-binomial check).
5. **Wiring against simulation.** Wiring summaries replicate (0.71-0.98) and simulated hit calls do not. This supports the draft's
   discussion, though not its title.
6. **Part S and exam 2.** Part S is correctly reported as uninformative. Exam 2's pre-registered verdicts, "predicts" and "does not add
   value beyond the best wiring baseline", are correct as stated.
7. **DNg100 and the forward ledger.** DNg100's exam 1 label was wrong, and the draft says so plainly. The forward ledger is candid that
   comparison A cannot be decided with the available lines.

## Notes on the tests

- **Scripts.** Every test is under `research/ledger/reviews_v5/referee_tests/` (`t1` to `t12`, each a `.py` file with its `.out`
  output), run with `uv run --project ledger --no-sync python <script>`.
- **Inputs.** They read locked tables only, plus the cached text of the authors' preprint, and none runs a simulation. They reproduce
  the locked headline figures: the exam 1 AUROC and baselines, the replication counts, the A0 ratio 0.628 and the overlap ratio 0.26.
- **Quotations.** The authors' words are quoted from the cached bioRxiv preprint
  (`data/ledger/sources_v2/10_1101_2025_09_12_675944/text.txt`). The cached Nature text
  (`data/ledger/sources_v2/10_1038_s41586_026_11195_y/text.txt`) is abstract-only, so the printed wording may differ.
- **Room for the changes.** The abstract is 196 of its 200 words, so changes there must replace text rather than add it. The body, from
  the Introduction to the end, is about 3,400 words against the 4,500 limit, so the threshold table, the make-up of exam 1's classes and
  the authors' own words fit.
