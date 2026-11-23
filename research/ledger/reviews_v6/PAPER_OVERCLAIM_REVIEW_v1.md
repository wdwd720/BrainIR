# Overclaim review of PREPRINT_v1 and SUPPLEMENT_v1

Checked against `PREREG_v6.md`, `RESULTS_5.md`, `thirdfly_v1/`, `posthoc_v6/`, `CLAIMS_v1.md` and the literature notes. **Items: 18**,
most serious first.

**Abstract budget.** The abstract is at its cap (221 words by `wc`). The Δ replacements other than item 8's add 37 words. Recover them
by deleting the first and last sentences (-14), writing "one such hit list" and "front-leg rhythm" in sentence 2 (-4), and dropping the
stability sentence (-21); Results 5 keeps that result, with item 8's caveats.

1. **[major; fairness] Abstract; Discussion ¶1; Supplement S3.** "In the third animal, our own lists recurred above chance, while the
   authors' list recurred at chance (1 of 6)." / "The authors' own six high-confidence hits recurred in the third animal at chance."
   *Why:* a contrast no test made. The lists differ in power, not recurrence: 1 of 6 is 1.7 times chance, against 3.0 times (5 of 17)
   and 1.9 times (12 of 60) for ours. C4 requires its fixed sentence beside "at chance" "always" (power 0.26 if 30 % recur), but only
   Results 3 carries it. Their list keeps its own procedure; ours are sweep against sweep (B4). DNb08, one of the six, fails in BANC by
   the authors' own report. "High-confidence" describes the type match. The "list" is our 0.5 cut of their type-level robustness screen
   (Extended Data Fig. 1c). *Replace:* "In the third animal, our sweep lists recurred above chance; the authors' list (1 of 6) was at
   chance, a test too weak to show that its hits fail to recur." (Δ +11). Discussion: "The authors' six matched hits were at chance in
   the third animal (1 recurred), a test too weak to show that they fail to recur." S3: add the fixed sentence.

2. **[major] Abstract.** "At the authors' threshold, the first two animals' hit lists overlap at chance (post hoc)." *Why:* only under
   our current-setting procedure, which failed its positive control in BANC and missed the authors' single-DNb08 result in MaleCNS.
   Under the sweep that the validity rule made primary, 14 of MANC's 18 hits recur in MaleCNS (5.97 expected). The next sentence's lists
   are sweep lists, an unannounced switch. *Replace:* "At the authors' threshold, the first two animals' hit lists overlap at chance
   under our current-setting procedure but above chance under a current sweep (post hoc)." (Δ +11)

3. **[major] Discussion ¶1.** "For anyone simulating one connectome ... a hit list from one connectome is fragile. In three animals,
   left and right copies of the same neuron disagree, and the same cell type in different animals disagrees more." *Why:* it generalises
   from one model, one behaviour and three animals (two screened only by us), dropping the qualifier v5 accepted. "Fragile" and
   "disagree" go beyond the registered "a real gap": copies agree at 0.58-0.64 of the ceiling. "Disagrees more" was never tested. For
   BANC it compares a one-sided current-setting screen (0.58, 0.38-0.77) with whole-type sweeps (0.35; 0.50, 0.38-0.62), as Fig. 2 does.
   Only run 4's like-for-like screens of the first two animals show it, as point estimates (0.32-0.50 against 0.59-0.64). *Replace:*
   "For one model and one behaviour, our results suggest four things. First, a hit list from one connectome is only partly reproducible.
   In all three animals, left and right copies agree less than a screen agrees with itself; in the first two, the same type in different
   animals agrees less still (point estimates)."

4. **[major] Abstract; Results 3; Discussion ¶3.** "the gap was confirmed in the third animal (pre-registered), although its wiring also
   matched the others' less closely." / "rather than from the simulation" / "the wiring caveat in section 3 points to part of each"
   *Why:* C3 attaches its caveat "so that the line cannot be quoted without it", but the abstract keeps the observation and drops the
   consequence. Results 3 narrows "the build" (also floor, size measure, transmitter source) to reconstruction and adds "rather than
   from the simulation". The wiring check cannot apportion the gap. The 0.31 (MANC-MaleCNS sweep) is post hoc but unlabelled in the
   abstract, Results 3 and Fig. 2. *Replace:* "Across animals, screens agree at 0.31 (post hoc) to 0.50 of this ceiling; the gap was
   confirmed in the third animal (pre-registered), but its wiring matched less, so part may come from the build or type match." (Δ +8).
   Results 3: "Part of the gap may therefore come from the build or the type match." Discussion: "the wiring check in section 3 cannot
   separate them."

5. **[major] Results 1-2; Abstract; Limitations; Fig. 2.** "In BANC, which we did not examine before our rules were frozen, the
   pre-registered test gave 0.58 (0.38-0.77): again a real gap (Fig. 2)." *Why:* C1 and C2 ran on the current-setting procedure, whose
   whole-type positive control failed in BANC (`gha6.build_bh` and `build_bn`; LOG L184), though each DNg100 copy alone reached 0.5 in
   13 of 16 draws. The validity rule covered only C3, C4 and C6-C8. The abstract ("these tests used a current sweep") and Limitations
   imply every BANC test was rescued. *Replace:* "In BANC, which we had not screened before our rules were frozen, the pre-registered
   test gave 0.58 (0.38-0.77): again a real gap, from the current-setting procedure, whose whole-type positive control failed there
   (Fig. 2)." Abstract: "the cross-animal tests used a current sweep" (Δ +1). Limitations: append "; the BANC left-right and count-noise
   tests used it".

6. **[moderate] Introduction, last paragraph; Methods.** "Every analysis sits in a prediction ledger: rules written, frozen and
   timestamped before the data they concern." / "Each analysis was written into a rulebook before the data or simulations it concerned"
   *Why:* the first two animals' hit lists, exam 2's extra comparisons and the audited re-score used data already seen (Part Q, Part H;
   S4). *Replace:* "Every pre-registered test sits in a prediction ledger, its rules frozen and timestamped before the data it
   concerns." Methods: "Each pre-registered test was written ...".

7. **[moderate; fairness] Abstract; Results 6; Discussion "Third".** "Against published experiments, the simulation did no better than
   counting two-step synaptic paths." / "level with the best of eight" / "simple wiring counts did as well as the simulation" *Why:*
   only the second test is interpreted, yet "published experiments" pools both. That test ran the authors' full-cord model with our
   full-cord tuner (`RESULTS_2.md`, "H-M"), not the screen the abstract names; its blind was only procedural. "Level with" and "did as
   well as" claim an equivalence that an interval of -0.17 to 0.17 cannot show; the registered words are "adds nothing beyond wiring".
   One count of eight, picked on the same labels, matched it; four did clearly worse. *Replace:* "In the one interpretable literature
   test, our run of the authors' full-cord model did no better than counting two-step paths." (Δ +7). Results 6: "It added nothing
   beyond the best of eight wiring baselines, picked on these labels". Discussion: "Third, in that test the simulation added nothing
   beyond the best of eight wiring counts."

8. **[moderate] Abstract; Results 5.** "A neuron's stability under synapse-count noise predicted its score in the third animal (12
   types; p = 0.029; a second attempt)." / "It did so beyond the type's score in the real MANC network" *Why:* RESULTS_5 ranks this
   fragility among its three biggest caveats; the abstract drops it. The first test was null (p = 0.11); the predictor is one of two
   nominally positive sensitivity analyses out of four (the others, 0.13 and 0.18, unreported); 10 of 12 BANC scores are below 0.07;
   DNb08's BANC failure was foreseeable (C8 discloses it, Results 5 does not). The stability is a type's, not a neuron's. "Did so
   beyond" gives words to a secondary statistic with no test or interval. *Replace:* "In 12 types, stability under count noise predicted
   the third animal's scores (p = 0.029), a fragile result: the predictor was chosen after a nominal positive." (Δ +5). Results 5: "Its
   partial correlation given the type's score in the real MANC network was 0.56 (secondary; no test or interval)". Add the other p
   values and C8's DNb08 disclosure.

9. **[moderate] Abstract; Results 1; Methods.** "left unexamined until our rules were frozen" / "which we did not examine before our
   rules were frozen" / "The third animal stayed blind until the rulebook was frozen" *Why:* per Part Q 3, 4 and 8, BANC's annotations
   were read to build the type matches, the gate stimulated DNg100 and silenced E1, E2 and I2, and the authors' BANC results were known.
   The screens stayed blind; the animal did not. *Replace:* Abstract: "pre-registered, in a third, female connectome not screened until
   our rules were frozen" (Δ -3). Results 1: as in item 5. Methods: "No BANC screen ran before the freeze; before it, BANC's annotations
   were read to match types, only DNg100 was stimulated, only the authors' circuit neurons were silenced, and the authors' BANC results
   were known."

10. **[moderate] Results 4; Abstract.** "The earlier failure came from our current-setting procedure, not from the network." *Why:* no
    test isolated the cause: Part V changed the current, run length (2 s, not 1 s) and scoring (activity bounds ignored) at once.
    *Replace:* "So the network can produce their result; the earlier failure lies in our screening procedure (its current, 1-s runs or
    activity bounds, not separated)." Also the abstract's "Our model reproduces the authors' results for DNg100 and for a single DNb08
    neuron." omits that Part V is MaleCNS only and that our current-setting procedure, which produced the lists, had missed it.
    *Replace:* "In MaleCNS, our model reproduces the authors' DNg100 and single-DNb08 results; our current-setting procedure had missed
    the latter." (Δ +4)

11. **[moderate] Results 4; Discussion ¶2.** "DNb08 did not drive rhythm in BANC: neither the whole type (0.00) nor any of its four
    copies alone" / "our model agrees in every case we tested" *Why:* 0.00 and 0 of 16 come from the current-setting procedure, which is
    invalid in BANC; under the sweep the type scored 0.25. The copies were not run at the authors' configuration (position 2446, current
    250, 2 s), and the authors' result concerns one neuron, not the type. "Every case" passes over our MaleCNS screen's miss. *Replace:*
    "DNb08 was not a hit in BANC (whole type 0.00 under the current-setting procedure, 0.25 under the sweep; each copy alone 0 of 16
    draws)." Discussion: "and our model reproduces their single-DNb08 result in MaleCNS, which our screen had missed, and, like them,
    finds no DNb08 hit in BANC".

12. **[moderate] Discussion "Second".** "a current sweep recovers more shared hits than our current-setting procedure" *Why:* post hoc
    and unlabelled. The sweep calls three times as many hits (71 against 22 of 214 in MaleCNS), so more are shared by chance (5.97
    against 1.03 expected), and over all types it agrees no better (0.33 against 0.41). *Replace:* "Second, the answer depends on the
    procedure (post hoc): a current sweep, which calls more hits, shares more beyond chance, yet agrees no better over all types (0.33
    against 0.41)".

13. **[moderate] Results 7.** "Twelve experiments that could decide" / "Before any of these tests, we listed experiments that have not
    been done." *Why:* `forward_v2/DECISION_RULE.json` (`honesty`) says the list was "Made after both exams were unblinded and after the
    replication pattern was seen". All four of its "replicated" types are only near-replicated, three are not hits in BANC (S7), and the
    power to set replication against the single-connectome reading is 0.0. *Replace:* "Twelve experiments that could test the readings";
    "After both literature tests and the post hoc replication pattern, but before the third animal, we listed experiments that have not
    been done."

14. **[moderate; fairness] Results 1 heading; Abstract.** "Left and right copies disagree in the authors' own published screen" / "a
    neuron's left and right copies agree at 0.63" *Why:* the registered words are "a real gap". Agreement at 0.63 of the ceiling is
    partial agreement, and the statistic ranks 250 types, not neurons. For our one-sided screens, "the same gap" should read "a similar
    gap". *Replace:* "In the authors' published screen, left and right copies agree less than the screen agrees with itself"; Abstract:
    "In the authors' published screen, left and right copies agree at 0.63 of the screen's agreement with itself." (Δ -2).

15. **[moderate; fairness] Introduction ¶2-3; Discussion ¶2.** "These results hold up, and they are the authors'" / "a small circuit of
    interneurons that generates the rhythm" / "we did not re-test them" *Why:* "hold up" claims checks we did not make (pruning, FANC,
    the fly experiments), and the rhythm is generated only in the model. Conversely, "we did not re-test them" withholds credit: the
    BANC gate reproduced their E1 and E2 silencing (0.000 and 0.028; theirs 0.014 and 0.035). *Replace:* "These results are the
    authors': they tested DNg100's circuit and DNb08 across datasets themselves, and what we re-ran reproduces."; "...that generates the
    rhythm in the model"; Discussion: "our BANC gate re-ran their E1 and E2 silencing, which reproduced". Also "That sentence is about
    which leg's motor neurons are read out." states as fact our reading of a v1 sentence that the notes record without context (section
    13): write "We read that sentence as being about ...".

16. **[minor] Results 2.** "reproduced MANC's left-right gap" / "One difference may matter: the authors' BANC network has no synapse
    threshold" *Why:* MANC's verdict rests on one pre-registered pair of copies, a low draw; over six pairings, post hoc, noise
    reproduces about 86 % of the gap (`RESULTS_3.md`). The threshold explanation is post hoc, and the tests use different statistics:
    paired in MANC, cross-half in BANC. *Replace:* "...with the pre-registered pair of copies (over six pairings, post hoc, about 86 %
    of it)"; "Two differences may matter (post hoc): BANC's test used the cross-half statistic, not MANC's paired design, and ...".

17. **[minor] Results 4.** "In BANC, DNg100 was predicted to be a hit under our unchanged procedure, and it was" / "Three types are hits
    in all three animals under the sweep" *Why:* DNg100's hit was foreseeable (the gate: 64 of 64 draws at the authors' current; their
    own report), and the sweep was used only because DNg100 passed it (B4). DNa13 and DNxl092 score 0.00 in BANC under the
    current-setting procedure. "Two versions do not depend on this calibration" contradicts the Fig. 4 caption. *Replace:* "..., as the
    gate and the authors' result made likely, and it was"; "Under the sweep, DNa13 and DNxl092 are hits in all three animals (both 0.00
    in BANC under the current-setting procedure), as is DNg100, whose pass made the sweep primary (Fig. 4)."

18. **[minor] Results 3 (omission).** "our MANC hits recurred above chance: 5 of 17 are hits in BANC" *Why:* the same-name subset (G5),
    reported beside C4, changes the reading: 1 of 7 MANC hits recurs ("at chance", without words), against 7 of 30 MaleCNS hits; the
    paper omits it. *Replace:* add "On the 96 types whose BANC name equals the MANC name (no words), 1 of 7 MANC hits and 7 of 30
    MaleCNS hits recur."
