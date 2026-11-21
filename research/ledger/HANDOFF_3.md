# HANDOFF 3: run 3, exam 2 on hemilineages

## 1. What exists now

| tag | commit | time (PST, 2026-11-21) |
|---|---|---|
| `ledger-prereg-v3` | a175625 | 02:23 |
| `ledger-predictions-h1` | 7056028 | 04:49 |
| `ledger-labels-h1` | 4bc7330 | 10:25 |
| `ledger-scorecard-h1` | ff63619 | 11:13 |
| `ledger-reliability-v1` | d14b710 | 11:14 |

Locks (sha256, files hashed):
- `LOCK_prereg_v3`: 8c674fd0...f085 (142)
- `LOCK_labelcode_h1`: c4437386...7e30 (41)
- `LOCK_predictions_h1`: 732aca14...5b63 (154; one honoured amendment, a bug fix in the R3 script)
- `LOCK_predictions_h1b`: 50ffb5ee...d02b (77)
- `LOCK_labels_h1`: d0d3ec2e...c380 (144)
- `LOCK_reliability_v1`: 7d5f172e...2b80 (122)

All verify, and each was committed exactly once. Pushes worked: origin `ledger/v1` equals local HEAD, all five tags are on
origin, `main` is untouched, and nothing was force-pushed. OpenTimestamps: proofs are complete for the prereg, label-code and predictions locks, and pending (stamped 10:25-11:15) for the other three locks, `RESULTS_2.md` and `primary.json`.

## 2. Departures from the prompt

1. Added a membership baseline (k = 0): hemilineages that contain motor neurons move them directly.
2. Kept the linearised steady state although it is unstable (spectral radius 34.3). The audit showed that dropping it was
   wrong.
3. Controls and sensitivity groups used 4 seeds, not 16, to save runner hours. They are compared with H-M on the same seeds.
4. H-X was not run: no verified full-cord network of another animal exists.
5. Walking merged into repeated leg movement (7'). Grooming and held wing posture are coded but not primary.
6. A hemilineage needs at least 3 coded primary dimensions. Decapitated observations outrank intact ones across labs.
7. The decision rules are stricter than the prompt. "Predicts" must also clear the null mean, and "beyond wiring" requires
   "predicts".
8. There are two prediction locks: primary before the first label session, descriptive before the labels lock.
9. The label code was locked at the freeze. Dimension 1 is the maximum over the body-part pools.
10. GitHub stalled with about 270 queued jobs, so campaigns were re-published a few at a time. The Mac failed the trust check
    and ran no prediction.
11. A safety classifier blocked the first verifier's write, so a second verifier checked the same sample.
12. The frozen de-duplication dropped 5 distinct Soffers records. This is reported as a caveat, with an exploratory re-score.
13. Two reviewers edited their reports after committing them. The locked version was restored and the edit kept as an
    addendum (L90, L92).
14. After the predictions lock I saw about ten label cells, in a review heading and a reviewer's message (L91, L92).
15. After the unblinding, these were done (L100):
    - R3 and `RELIABILITY.md` were written; they use no labels.
    - The figure colours changed; no number changed.
    - The exploratory script was committed, though it was drafted before the flag.
    - The `RESULTS_2.md` wording was corrected before the tag.

## 3. Build diagnosis (Stage 0)

The authors' DNg100 run and ours activate the same leg motor neurons: per-neuron activation frequency r = 0.98, with identical
per-leg medians. A 100 times tighter tolerance changed nothing, so no build error alters which motor neurons fire. The T1R-T2R
coupling gap is in phase only and noisy (0.42 on 16 seeds, 0.14 on 64). No exam 2 prediction uses coupling.

## 4. Rulebook in ten lines

1. **Units:** 43 annotated hemilineages. A unit's group is every thoracic member, both sides, at equal current.
2. **Arms:**
   - H-M: L14 procedure, full cord, 16 seeds.
   - H-S: 8 wiring baselines.
   - H-C: 10 controls.
   - H-D: 4 currents.
   - 7 sensitivity groups.
3. **Primary dimensions:** 1-6, 7' (7 or 8), 10, 11, 13, 14 and 15. Dropped: 8 alone, 9 and 12.
4. **Model to vocabulary:**
   - Each dimension is the fraction of a motor pool that is active.
   - Held flexion and extension are weighted by 1 minus rhythm.
   - 7' is the most rhythmic leg.
5. **Truth:** Harris 2015 and Soffers 2025, read twice and adjudicated. Decapitated preparations come first; cross-lab
   conflicts are removed.
6. **Statistic:** the mean percentile rank of the true hemilineage among 43, over units with at least 3 coded dimensions.
7. **Uncertainty:** 10,000 permutations, a bootstrap interval, top-1 and top-3.
8. **"Predicts":** p < 0.05, and the lower bound above both 0.5 and the null mean.
9. **"Beyond wiring":** "predicts", and the paired lower bound above 0 against the best of the 8 H-S baselines.
10. **"Underpowered":** fewer than 20 units.

## 5. Predictions only (replicates: accepted / too weak / saturating)

| arm | replicates | accepted / too weak / saturating |
|---|---|---|
| H-M | 688 | 424 / 205 / 59 |
| H-M, seeds 0-3 | 172 | 108 / 52 / 12 |
| Rewiring 101-105 | 172 each | 115/42/15, 115/44/13, 107/51/14, 99/56/17, 110/49/13 |
| Class shuffle 201-205 | 172 each | 72/70/30, 72/66/34, 78/68/26, 81/63/28, 75/65/32 |

Sensitivity groups:
- all: 107/53/12
- post: 104/36/12
- T1: 107/51/10
- T2: 89/57/22
- T3: 88/59/13
- L: 96/53/15
- R: 99/53/12

H-D runs fixed currents with no tuner. Its run classes are recorded for information, 344 replicates each: 120/80/144 at 128,
256 and 384, and 117/76/151 at 512.

H-S is wiring only. The determinism sample was 50 of 50 identical.

## 6. Labels only

- **Sessions:** 14 label sessions and 2 verifiers, all audited, none breached. 10 contributed final records.
- **Sources:** Harris 2015 and Soffers 2025, with the Cheong summary as an outside check. The searches found 51 leads, none
  qualifying.
- **Records:** 79 final records, 60 of them eligible. They give 193 coded primary cells over 28 hemilineages, 27 with at least
  3 coded dimensions.
- **Between readings:** kappa 0.975 over 271 cells. Full-vocabulary agreement 0.81.
- **With the published summary:** kappa 1.0 over 38 cells.
- **Between labs:** 79 % agreement over 33 cells, kappa 0.24.
- **Verification:** 6 errors in 148 cells (4.1 %). Review: usable with caveats.

## 7. The gate

| condition | result |
|---|---|
| 1. Locks verify (clean checkout) | held |
| 2. No contributing session breached | held |
| 3. No review blocker; verification error at most 10 % | held (4.1 %) |
| 4. Kappa at least 0.7 | held (0.975) |
| 5. At least 20 hemilineages | held (27) |
| 6. Fresh reviewer's checklist | confirmed (8 of 8) |

Run 1 held conditions 1-5, with 6 pending. Run 2 held all six, and conditions 1-5 were identical in both runs.

## 8. Results

First line of `RESULTS_2.md`: **"Pre-registered verdict: the model predicts, but it adds nothing beyond wiring."**

- **Headline:** mean percentile rank 0.633 (0.533-0.724), p = 0.0076, 27 hemilineages. Top-1 is 0 of 27 and top-3 is 2 of
  27; chance is 0.02 and 0.07.
- **Ceiling:** Harris identifying Soffers scores 0.481, Soffers identifying Harris 0.692 (10 hemilineages). Each lab as
  truth: Harris 0.662, Soffers 0.556.
- **Wiring:** H-M minus k2-signed is -0.006 (-0.172 to +0.166).

  | baseline | signed | unsigned |
  |---|---|---|
  | k0 | 0.420 | |
  | k1 | 0.557 | 0.551 |
  | k2 | **0.638 (best)** | 0.497 |
  | k3 | 0.506 | 0.476 |
  | lin | 0.461 | |

- **Controls:** all ten score below H-M on seeds 0-3 (0.616):
  - rewired: 0.451-0.597, mean 0.513
  - class shuffles: 0.535-0.614, mean 0.580
- **By class:** excitatory 0.641 (11), inhibitory 0.432 (15). Scores are re-centred within each class.
- **Scorecard (percentile rank):** 07B .95, 12A .95, 04B .93, 10B .90, 08A .90, 20A.22A .88, 17A .83, 18B .81, 01A .81,
  00A .80, 23B .76, 03B .74, 06B .73, 21A .67, 05B .65, 24B.25B .64, 09A .58, 13B .58, 12B .56, 08B .56, 11A .43, 06A .37,
  19A .36, 11B .20, 14A .20, 01B .20, 02A .07.
- **Exploratory:** without the questioned cells, the score is 0.595 (0.489-0.696), so "predicts" would fail.

## 9. Reliability study

| test | compared | Spearman |
|---|---|---|
| R1 ceiling | same fly, seeds 0-7 vs 8-15 (MANC / MaleCNS) | 0.86 / 0.93 |
| R1 | MANC vs MaleCNS, 310 types | 0.37 |
| R2 | wiring summaries, MANC vs MaleCNS | 0.78-0.97 |
| R3 | weight noise of 5 / 10 / 20 % | 0.82 / 0.76 / 0.65 |
| R4 | left vs right, one fly, 308 types | 0.43 |

The wiring agrees across flies, and the screen agrees with itself and survives random count noise. Yet the two sides of one
fly disagree almost as much as the two flies. So the cross-fly gap needs no difference between animals, and random
reconstruction noise is too small to explain it.

There are two limits. R4 has no matched ceiling, and R3 tests only independent noise. That "structured differences" cause
the gap is a hypothesis.

## 10. Post-mortem in five lines

1. **Zeros:** 25 of 39 exam 1 types scored 0: 2 never usable and 23 usable. For those 23, the replication's read-out was
   silent (14), not rhythmic (8) or never usable (1).
2. **Why zeros:** the tuner accepts runs on network-wide activity, never on front-leg motor neurons. A zero mostly means
   activity never reached the read-out.
3. **Ties:** AUROC 0.577 is mostly ties, (100 + 75 + 27) / 350. The 14 non-zero types alone give 0.675 (underpowered).
4. **The atlas:** it supplies 21 "yes" types and no "no". The model is above 0 for 10 of them and for none of the other 4
   "yes" types. Without the atlas, the AUROC is 0.367.
5. **Wiring:** the two-hop baseline worked through magnitude, not sign; the "no" types' sums are about 80 times larger.
   Magnitude follows the source too, so the two cannot be separated.

## 11. Compute and wall-clock

- **Runner time:** about 161 runner-hours, under the 300 limit: 160.5 h for 685 GitHub jobs in 48 run 3 workflow runs.
- **Why job timestamps sum to 368 h:** 187 jobs queued during the stall were cancelled before any step ran. Their timestamps
  include queue time, but they never ran on a runner.
- **Other compute:** none paid, no Modal. The Mac only orchestrated, built tables, scored and checked.
- **Wall-clock:** 00:32 to 11:30 PST (11 hours). Most of the waiting was GitHub's stall.
- **Baseline checks at the end match the start:** the BrainIR suite gives 532 passed with the known arm64 failure. The
  Phase 1-3 locks and the ledger suite (201 passed) are green.

## 12. What worries me

- **The positive verdict is fragile.** The lower bound is 0.533, and removing the 15 questioned cells drops it below 0.5. The
  labs agree at a kappa of only 0.24.
- **The identification is coarse.**
  - A two-step synapse count does as well, and class shuffles keep most of the score.
  - The ranking mostly separates excitatory movers from silent inhibitory hemilineages.
  - Top-1 is 0.
- **18 hemilineages are predicted silent.** They include 08B, which is excitatory, and 06A, which has 4 motor neurons. A 1 s
  window with a 0.01 Hz threshold may miss slower effects.
- **H-D's run classes are identical at 128, 256 and 384.** I have not examined why.
- **The audit trail has dents:**
  - reviewers edited their reports after committing them;
  - I saw about ten label cells;
  - git cannot show that the exploratory script came before the flag.

## 13. What I would do next

1. **Locate the cross-fly gap.** Give R4 a ceiling with a one-sided split-half, and test the structured-differences
   hypothesis by dropping or adding edges and members.
2. **Exam 3 with a richer read-out:** time-resolved, longer windows, with the k2 baseline as the bar to beat.
3. **A new label-code version:** fix the de-duplication key, re-read Harris Figure 9A at full resolution, and add a third
   source.
4. **Score top-k naming alongside rank,** so a model must single out the hemilineage.
