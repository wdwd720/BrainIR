# Second-round referee report on PREPRINT_v1 (with SUPPLEMENT_v1 and CLAIMS_v1)

Objections: 14, of which 13 cite a test. For four of them (10, 12, 13, 14) the test is only a text or table check in `t7`.

Read as the original authors would read it: "we" and "our" below are Pugliese et al.; "the paper" is the preprint under review.

All tests are in `reviews_v6/referee2_tests/` (`t1`-`t7`, each a `.py` file with its `.out.txt` output; shared loaders in
`_common.py`). They use locked tables and the collected result logs, through the ledger's own loaders. Each first reproduces the
locked number it perturbs (C1 0.582; C3 0.349 / 0.505 / 0.314; C8 0.571, p = 0.0286; C7 6.27). No simulation was run. Only `t5` (d)
reads network matrices: the authors' BANC matrix (pinned by SHA-256) and the ledger's MANC raw counts.

## 1. First-round objections the addendum accepted

| # | Objection | Reflected? | Where in v1 | What is missing |
|---|---|---|---|---|
| 1 | Exam 1's classes come from different experiments | partly | R6 ("confounded with its source"), Limitations, S4 | The abstract still counts exam 1 in "no better than counting". Its takeoff and flight sources appear only in S4. The tie-breaks (11 of 14 negatives) appear nowhere. |
| 2 | Counting's exam-1 lead is a size effect | partly | R6 ("We do not interpret") | 0.669 is printed beside 0.577 without the size caveat. Discussion point 3 is not tempered. |
| 3 | The draft tests a use the authors disclaimed | partly | Introduction (quotes), Discussion (selection rule) | The point that exam 1 scores low scores is absent. The Discussion now reads low BANC scores of our hits as fragility. |
| 4 | The MaleCNS screen was calibrated on DNg100 | yes | R4, Limitations, Fig. 4 | A new error: "chosen, before any other neuron was run" is wrong, and Fig. 4 applies the caveat to the sweep, which has no K (objection 9). |
| 5 | The audit "upheld" the labels by re-running | partly | Methods (7.7 %); the split in S4 | The main text lacks 0 of 21 against 3 of 18 (17 %, above the 10 % bar), and the re-quoting. |
| 6 | "Barely overlap" is a property of the 0.5 cut | partly | R3, Fig. 3, S5 | The body is fixed. The abstract omits "under our procedure" and the sweep's 14 of 18 (objection 1). |
| 7 | Exam 2: the simulation beat seven of eight baselines | partly | R6 | The abstract and the Discussion still say "no better than counting". "Picked on the same labels" is absent. |
| 8 | The title blames the connectome | yes | Title | (none) |
| 9 | DNit013's match was not rated "before looking" | partly | The sentence is removed | The paper does not say that the high-confidence rule behind every first-two-animal number was written after the pattern was known (L160). |
| 11 | The 51 % is the 5-synapse floor | yes | The sentence is removed | (none) |
| 12 | "Reproduces their published dynamics" | no | Methods | Still unqualified. The failed full-cord coupling item (G3v2) is unmentioned, and the addendum answered a different point. |
| 13 | Poisson copies with the floor are a structural perturbation | partly | R2 ("keeping ... threshold"), Limitations | Deletion and creation at the floor are not stated, and the new BANC contrast is wrong (objection 8). |
| 16 | The read-outs differ | yes | Methods (144, 130, 139) | (none) |
| 17 | (refuted) The MANC screen shares 10 of 11 hits | yes | Discussion | DNg63 (1 usable draw) and DNxl121 (6) are not flagged, and DNg63 is now a proposed experiment (objection 13). |
| 18 | (refuted) Matching and list sizes | partly | S3, S5 (OC ratio) | The three never-usable MaleCNS types are not mentioned. |
| 15 | (kept) Readers from one model family | partly | Limitations, Use of AI | The abstract is silent, and the hand-check result is still a placeholder. |

Objections 10 and 14 were answered, not changed. Objection 14 has since reversed: Part S is now a positive result in the abstract
(objection 5).

## 2. Objections, strongest first

**1. [Procedure, framing] The answer to the title depends on the procedure. The abstract gives the first two animals only under the
procedure that failed, and BANC only under the fallback. Strong.**
- *Objection.* "Overlap at chance" (the first two animals) comes from the current-setting procedure, and "our own lists recurred above
  chance" (BANC) from the sweep. The paper's own data show that the current-setting procedure under-drives DNg100 in BANC and DNb08 in
  MaleCNS (Part V). Without its motor-neuron setting, the same tuner accepted DNg100 in MaleCNS at 256 with 0-1 active motor neurons
  (LOG L29). We drove DNg100 at 400 in both CNS datasets.
- *Tests.*
  - `t2` (b): 15 of DNg100's 16 tuned BANC draws were accepted at 256, the first in-bounds current. Three of the five failures had
    one active motor neuron.
  - `t2` (d), the sweep log for the same neuron, network, 1-s runs and seeds: 5 of 8 draws reach 0.5 at 256, against 7 of 8 at 362 and
    at 512. The two failed tuned draws among these seeds reach 0.89 and 0.74 at 362.
  - `t2` (a), chance-corrected overlap at 0.5, (k - E) / (min - E), current-setting procedure → sweep:
    - MANC→MaleCNS: 0.00 → 0.67 (14 of 18; OC ratio 0.81, 0.59-0.99);
    - MaleCNS→BANC: 0.26 → 0.45 (0.82 on same-name types; OC ratio 0.93);
    - MANC→BANC: 0.06 → 0.22.
  - `t1` (6): had DNg100 cleared one more draw, the MANC list would be "at chance" in BANC (1 of 9, p = 0.37).
- *Change.*
  - Tabulate every pair under both procedures, and lead with the sweep, which is the primary procedure and has no calibrated
    setting.
  - Say in the abstract that the current-setting procedure accounts for much of the first two animals' disagreement.
  - Reword Discussion point 1 to "partly reproducible; strongly procedure-dependent".

**2. [Fairness, statistics] "The authors' list recurred at chance" is a difference in list size. Strong.**
- *Objection.* The abstract sets our six hits against your 17 and 60.
- *Test* (`t1`).
  - Recurrence rates are 1 of 6 (17 %) for A1, 12 of 60 (20 %) for the MaleCNS list called "above chance", and 5 of 17 (29 %) for
    MANC. A Fisher test gives p = 1.0 for both comparisons with A1.
  - Six hits need 3 recurrences for p < 0.05. At the paper's own rates, that happens with probability 0.10-0.25.
  - One of the six is DNb08, whose BANC failure we published.
  - A1 is our 16-replicate robustness panel (ED Fig. 1c), and it is compared across procedures. Our published list is Supplementary
    Table 1: 3 of its 13 matched types recur in BANC (23 %; 1.3 expected; p = 0.13, post hoc).
  - "The authors' own six high-confidence hits" reads as our confidence, not the match's.
- *Change.*
  - Delete the contrast from the abstract, and compare recurrence rates, with the test's power.
  - Name DNb08.
  - Call A1 "the authors' whole-type robustness screen", and give Supplementary Table 1 beside it.

**3. [Framing, fairness] "Confirmed in the third animal" could not fail informatively, and the wiring caveat does not fit the data.
Moderate to strong.**
- *Objection.*
  - C3 says "not confirmed" only if BANC agrees "at the ceiling" with another animal. No cross-animal pair in this ledger has exceeded
    0.59.
  - We reported cross-dataset differences ourselves (DNb08 in BANC; the motor neurons recruited), and attributed them to "variation
    in motor neuron reconstruction fidelity and synapse detection". The paper does not cite this.
- *Test* (`t6`, `t4`). Wiring similarity does not track screen similarity.
  - The most similarly wired pair (MANC-MaleCNS, 0.82) agrees at 0.31. That is no better than MANC-BANC (0.35, wiring 0.61; difference
    0.04, -0.13 to 0.20).
  - MaleCNS-BANC (wiring 0.63) agrees best in all 35 seed splits.
- *Also unlisted.* BANC's sizes are surface areas, whereas MANC's and MaleCNS's are volumes. MANC's descending neurons are truncated at
  the neck.
- *Change.*
  - Drop "confirmed" from the abstract, and say that the BANC agreements are no lower than the first two animals'.
  - Cite our Limitations.
  - List the size and truncation asymmetries.

**4. [Statistics] "About 7 animals (4.3 to 9.7)" assumes something the run's own data question. Moderate to strong.**
- *Objection.* Spearman-Brown needs exchangeable animals, but the interval resamples cell types only.
- *Test* (`t4`).
  - n* per pair is 7.4 (MANC-BANC), 3.9 (MaleCNS-BANC) and 8.8 (MANC-MaleCNS).
  - On the same resamples, the MaleCNS-BANC ratio exceeds MANC-MaleCNS by 0.19 (0.01 to 0.37). This is one of three contrasts, and a
    second touches zero, so the evidence is borderline.
  - In C6's own data, MaleCNS predicts BANC better than MANC does, by 0.18 (0.03 to 0.33).
  - A t-interval over the three pairs gives n* from 2.2 to 25. This is illustrative, since the pairs share animals.
  - The two CNS datasets, whose descending neurons keep their brain arbors, resemble each other most.
- *Change.* Remove the estimate from the main text, or give it as "about 2 to 25, assuming exchangeable animals".

**5. [Statistics] C8 sits in the abstract without its fragility. Moderate.**
- *Test* (`t3`).
  - The result survives tying the scores below 0.05 (p = 0.038) and band coding (p = 0.032).
  - It rests on three "indeterminate" BANC scores of 0.051-0.067. With the scores below 0.10 tied, rho is 0.26 and p = 0.21.
  - One DNg100 draw decided it. Had the tuned screen passed B4, C8 would read "not shown" (rho 0.39, p = 0.10).
  - Two of the 12 MANC "hits" rest on 1 and 6 usable draws (DNg63, DNxl121).
- *Change.* Drop C8 from the abstract, or call it "a fragile second-attempt correlation".

**6. [Pre-registration] Three of PREREG v6's reporting rules are not followed. Moderate.**
- *Rules* (`t7`, `t2`).
  - C4's fixed sentence must stand beside "at chance" "always". The abstract and the Discussion omit it, and the Discussion uses "at
    chance" as evidence.
  - G5's same-name subset is to be "reported beside C3 and C4", but it is absent. On same-name types, MaleCNS's hits recur in BANC at
    0.93 of the within-animal overlap, MANC's at 1 of 7 and A1's at 0 of 3.
  - X7 asks for "every count with and without DNg100", but only the counts without it are given. With DNg100, A1 is 2 of 7.
- *Change.* Add the sentence, both subsets and the counts with DNg100.

**7. [Procedure] C1 and C2 ran on the procedure that failed its positive control, and the paper does not say so. Moderate.**
- *Objection.* B4 moved only C3, C4 and C6-C8 to the sweep. The left-right test (0.58) and the count-noise test use one-sided screens
  run with the current-setting procedure.
- *Test* (`t5`).
  - DNg100's one-sided copies pass 6 of 8 (exactly B4's 75 % bar) and 8 of 8.
  - 73-76 % of the 180 types score exactly 0 on each side, against 43-52 % in MANC's and MaleCNS's one-sided screens, so the ratio
    rests on about 45 types.
  - BANC's side annotation of descending neurons appears to follow the soma: DNg100's soma is on the right, but it innervates the left
    leg, as we noted. The 313 neurons whose annotation disagrees with their output side put a median 74 % of their output on the
    other side. Crossing axons look like this; unreliable annotation does not.
- *Change.* Say which procedure C1 and C2 used, give DNg100's one-sided control and the share of zeros, and reword the side rule.

**8. [Accuracy] The explanation offered for C2 is wrong. Moderate.**
- *Objection.* The paper says that BANC's copies, unlike MANC's, do "not add or remove the many weak connections".
- *Test* (`t5` (d), which reads both networks).
  - Half of BANC's connections are single synapses. A Poisson copy removes an expected 21.5 % of all its connections (5.6 % of
    synapses) and adds none.
  - MANC's copy at the floor removes 12.6 % of the kept connections (3.8 % of synapses). It also adds new connections equal to 19 %
    of them (5.7 % of synapses), so it changes 9.5 % of synapses in all.
  - The difference is creation at the floor, not an absence of removal in BANC.
- *Change.* Correct the sentence, and say that MANC's result may depend on the floor.

**9. [Accuracy, credit] The calibration history is told inaccurately, and DNg100 loses credit under the sweep. Moderate.**
- *Objection.* "It was chosen, before any other neuron was run" contradicts LOG L29 and L55. Every neuron of both animals had already
  been screened and locked under the original procedure, with DNg100 at 0.059 in MaleCNS. Only the calibration ran DNg100 alone.
- *Test* (`t2` (c)).
  - Fig. 4 says DNg100's recurrence "is built into our calibration". Recomputing all 7,664 sweep draws without the motor-neuron
    requirement changes none of them.
  - Under the sweep, DNg100 scores 0.81, 0.98 and 0.92, which reproduces our four-dataset result. The BANC build was gated on
    DNg100, so this is not an independent test.
- *Change.* Correct both sentences, and credit the reproduction.

**10. [Literature tests] The abstract and the Discussion still fold exam 1 into "no better than counting". Moderate.**
- *Objection* (`t7`). First-round objections 1, 2 and 7 were "accepted". The abstract still says "did no better than counting", and
  Discussion point 3 says "simple wiring counts did as well ... in published experiments".
  - By Results 6, exam 1 is uninterpretable.
  - In exam 2 the simulation tied the best of eight baselines (picked on the same labels) and scored above the other seven (clearly
    above four).
- *Change.* "In the one interpretable test, the simulation matched the best of eight wiring baselines, picked on the same labels."

**11. [Validation] The gate, the type match and Part V validate less than the text implies. Minor to moderate.**
- *The gate* tests one neuron, and the circuit it drives, at one fixed current. It cannot catch errors in other descending neurons'
  wiring, sizes or signs; 13 rows with mixed or modulatory transmitter labels carry outputs.
- *BANC's "high" matches* have zero ID-name conflicts by construction, so "high" adds little to the ID match. The only check on this,
  the same-name subset, is not reported (objection 6).
- *Part V's* "all four DNb08 copies reach the bar at some fixed current" is the best of 20 currents against a bar of 8 of 16.
  - S6 shows how strongly a single neuron's status depends on the current. Copy 345 reaches 11 of 16 at 512 and 1 of 16 at 1,024;
    copies 328 and 330 need at least 362 and 724.
  - This supports fixed, dataset-specific currents more than any tuned hit list.
- *Change.* Say what the gate cannot test, and give the per-copy current ranges.

**12. [Blinding] "Left unexamined" overstates the blind. Minor to moderate.**
- *Objection* (`t7`). Before the freeze (Part Q 3, 4 and 8):
  - BANC's annotations were read, and its groups and type sets built;
  - its network was sign-checked;
  - DNg100 was simulated, intact and with E1, E2 or I2 silenced;
  - our DNb08 result in BANC was known.
- *Change.* "Not screened before our rules were frozen."

**13. [Forward list] One of the twelve proposed experiments rests on a single usable draw. Minor.**
- *Test* (`t7`). DNg63's "single-fly hit, MANC" reading is a score of 0.79 from 1 usable replicate of 16. Its MANC sweep score is 0.00,
  and its A1 score is 0.13.
- *Change.* Flag it in S7, or replace it.

**14. [Form] Minor.**
- *Length* (`t7`). The abstract is 221 whitespace tokens, or 220 without "=". The main text reaches 3,500 words only with the Methods
  (Introduction to Limitations: 2,822).
- *Leftovers.* "Title options" and the hand-check placeholder remain.
- *DNb08.* R4 gives its tuned BANC score (0.00) but omits its sweep score (0.25), the primary one, which C8 uses.
- *Change.* Fix these before submission.

## 3. What survives

1. **The left-right gap.**
   - It holds in our single-neuron screen (0.63) and in the one-sided screens of all three animals (0.58-0.64).
   - In BANC it is not count noise: each copy agrees with the real left screen at 0.89.
   - There is no evidence that it comes from the side rule. The strongly and the weakly lateralised halves give 0.63 (0.34-0.88) and
     0.51 (0.18-0.78) (`t5`).
2. **The whole-ranking gap across animals.**
   - It is stable over all 35 seed splits (`t6`).
   - It does not come from the order of non-drivers: with the scores below 0.05 set to 0, the agreements are 0.37, 0.38 and 0.31.
   - It is present under both procedures (current-setting procedure: 0.32, 0.44, 0.40).
3. **The BANC gate and Part V.**
   - The reimplementation reproduces DNg100 (BANC 0.994, MaleCNS 0.98) and our single-DNb08 result (15 of 16) at our
     configurations.
   - DNb08 fails in BANC, as we reported.
   - This corrects the earlier draft's discrepancy and is a real service.
4. **Pooling.** "Not shown" (C6) is reported correctly.
5. **The machinery.** The locks, the validity rule as written, and the hedges in Results (C4's power, C8's fragility) are sound. My
   objections concern what reaches the abstract and the Discussion.
