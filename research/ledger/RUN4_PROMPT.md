# BrainIR Prediction Ledger: Run 4

**Scope of this run:** prove or kill the claim that the simulation disagrees with itself across the two sides of one fly, find the cause, test fixes, and lock a forward ledger of predictions a lab can test. No new labels are collected in this run.

Everything so far is on branch `ledger/v1` under `research/ledger/`. Read `HANDOFF_3.md`, `results/RESULTS_2.md`, `RELIABILITY.md`, `results/POSTMORTEM_1.md`, `LOG.md` and the three rulebooks before you design anything.

This is a long autonomous run: expect 12 to 24 hours. I will not be watching. Do not stop to ask me things. Where this prompt is silent, or wrong about the repo, make the call that best serves the goal, log the decision and the reason, and keep going. Any pause must schedule its own re-check within 10 minutes and resume by itself.

Think hard before every irreversible step. Before each lock, write a short pre-mortem in the log and check the most likely way it could be wrong.

---

## 1. Where things stand

Three results are in hand.

1. **Exam 1, descending neurons.** The authors' model did not predict front-leg rhythm: 0.577 on 39 types. Two-step synapse counting scored 0.669.
2. **Exam 2, hemilineages.** The model predicted weakly: mean percentile rank 0.633 on 27 hemilineages. Two-step signed synapse counting scored 0.638, and class-shuffled networks kept most of the score.
3. **Reliability.** The wiring agrees across the two flies (0.78 to 0.97). The simulation's output does not (0.37). Random weight noise of 20% still leaves 0.65. The two sides of one fly agree at only 0.43.

Known caveats to carry forward honestly:

- Exam 1 leans on one intact-fly atlas for its "yes" class, and most labelled types score exactly 0.
- Exam 2's two labs agree at a kappa of only 0.24, and the positive verdict fails without 15 questioned cells.
- The left-right figure has no matched ceiling yet, and it comes from our code, not the authors'.

---

## 2. The idea behind this run

**Left against right is a test with a known answer.** A neuron's left copy and right copy are built by the same genome and do the same job. Any correct model must give them matching predictions. So left-right agreement is not only a reliability number. It is a validity test that needs no experiment and no labels, and the same holds across two animals.

**Three things could be producing the gap.** This run separates them.

- **Chance:** different random parameter draws. Run 3's split-half says this is small.
- **Procedure:** the screen tunes a current for each type and scores the run it lands on. Run 1 showed that rhythm exists only inside a narrow window of drive. A tiny difference could move where the tuner lands, in or out of that window.
- **Wiring:** real differences between the two sides, which could be biology or reconstruction, and could sit in the stimulated neuron's own outputs or in the network downstream.

**The strongest version of the claim uses no code of ours.** The authors published a score for every single descending neuron, left and right copies separately, with 128 replicates each. If their own left and right copies disagree, nobody can blame our implementation. That check comes first.

This run must:

1. Freeze `PREREG_v4.md` before any new analysis or simulation.
2. **Part A0:** test left against right in the authors' own published scores.
3. **Part A:** establish the left-right and cross-fly gaps with matched ceilings.
4. **Part B:** attribute the gap to procedure, to location in the network, and to classes of wiring difference.
5. **Part C:** test a fixed list of parameter-free fixes against criteria declared in advance.
6. **Part D:** re-score both exams with each fix, marked exploratory.
7. **Part E:** lock a forward ledger of calibrated predictions, with a short list of decisive experiments.
8. **Part F:** write the results, an adversarial review, a two-page brief and an evidence map.

---

## 3. Hard limits

1. **Declare first.** Every analysis, metric and success criterion is in `PREREG_v4.md` before the data or simulations it concerns. That includes Part A0, even though it needs no simulation. Anything thought of later goes in a section marked exploratory.
2. **Calibrate on DNg100 only.** Any gain or threshold a fix needs is set from DNg100 alone. DNb08 may be reported and never tuned on. No exam label may shape a fix.
3. **Exams are closed.** Both exams are unblinded. Re-scoring them in Part D is exploratory by definition and must say so every time. Each variant is scored once.
4. **Labels may be used for one thing only:** turning scores into probabilities for the forward ledger in Part E. That is training on past results to predict future ones, and it is stated as such.
5. **Frozen things stay frozen.** Every existing lock, the BrainIR locks, the Phase 2 to 4 files and `main` are untouched. BrainIR's own methods may be imported read-only.
6. **Reviews are write-once.** A reviewer's report is committed once. Later thoughts go in an addendum file, never an edit.
7. **No paid compute.** GitHub Actions only, under the same trust gate. The Mac failed that gate and runs no prediction. Keep at most 20 jobs queued at a time, and stop at 300 runner-hours.
8. **Nothing public except my repo.** Push the branch and tags. Never push `main`. No force pushes.

---

## 4. Stage 0: housekeeping and one check

- Start `caffeinate`. Save this prompt as `research/ledger/RUN4_PROMPT.md`. Confirm the tree is clean and all locks verify. Re-run the baseline checks and the trust gate.
- Continue `LOG.md` and keep `STATE.md` current.
- **Check the dose arm.** In run 3 the fixed-current arm gave identical run classes at 128, 256 and 384. Find out whether the current was actually applied. This matters because Parts B and C rely on fixed-current runs. If it is a bug, fix it for this run and write an erratum next to the exam 2 results. Do not re-score anything.

---

## 5. Stage 1: `PREREG_v4.md`

### Fixed for the whole run

- **Screen.** The B1r procedure (tuner v2, K = 1) on the front-leg networks, unchanged. The one-sided variant is the R4 procedure: one side's members stimulated, the same side's motor neurons read out.
- **The four half-flies.** MANC left, MANC right, MaleCNS left, MaleCNS right.
- **Side and matching.** Take each neuron's side from the annotations and check it against anatomy for a sample. Match neurons across sides by the annotated bilateral groups where they exist, and by type otherwise. Record how many are matched each way and how many are unmatched.
- **Agreement, primary.** Spearman correlation of the per-type mean score over matched types, with a bootstrap interval over types.
- **Agreement, secondary.**
  - The same, restricted to types that are non-zero in at least one of the pair.
  - The same, restricted to types with equal member counts on both sides.
  - Replication rate: of the types called drivers in one half, the fraction also called drivers in the other. This is the plainest number, so always report it.
  - Kappa of the three bands, and overlap of the top 30.
- **Ceiling.** The split-half agreement of the same screen on the same half, with seeds matched to the comparison. Report the replication rate for split halves too.
- **Gap closure.** For any intervention: (agreement after minus agreement before) divided by (ceiling minus agreement before), with an interval.
- **Paired draws.** Where you can, give homologous neurons on the two sides the same random parameter draws, so comparisons are not blurred by seed noise. Say whether you did.
- **Informative set.** Types that are non-zero in at least one half in Part A. Interventions in Parts B and C may be run on this set plus a fixed random sample of 50 other types, to save compute. Say when you do.

### Part A0: the authors' own scores (no simulation)

- **Data.** The authors' single-neuron screen already locked as A0 (933 neurons, 128 replicates), and BrainIR's B0 (16 replicates).
- **Pairs.** Types with a left and a right excitatory member. The primary subset is types with exactly one member per side. For the others, average within side.
- **Test.** Agreement between the left copy's score and the right copy's score, with every secondary measure above.
- **Ceiling.** Split the replicates of each neuron into two halves and compare a neuron with itself.
- **Note.** This screen stimulates one neuron and reads out both front legs together.
- **Decision.** If left and right copies agree at the ceiling in the authors' data, say plainly that the left-right gap may be specific to our one-sided procedure, and weight everything after accordingly.

### Part A: establish the gap

- Run the one-sided screen on all four half-flies with 16 seeds, reusing locked R4 runs where they match exactly.
- Report all six pairwise agreements with matched ceilings.
- **One bad side?** Compare the two sides' score distributions, driver counts and tuner outcomes. Say whether one side is simply weaker everywhere.
- **Wiring, same comparisons.**
  - The wiring summaries from run 3.
  - Single connections: how well homologous connection weights correlate, and what fraction of connections exist on one side only because of the 5-synapse floor.
  - Across flies, the same at the level of type-to-type connections.
- Report left against right at the hemilineage level from the run 3 sensitivity groups.
- Report DNg100's own per-leg left-right asymmetry in the authors' run and in ours.

**If the matched ceilings show no real left-right gap:** say so plainly, and run Parts B and C on the cross-fly gap, applying the same classes at the level of types.

### Part B: attribute the gap

Run the three blocks in this order. Each is cheaper than the next and can change what the next means.

**Block 1: procedure.**

- **Dose sweep.** Run both sides at the same fixed grid of currents with no tuner. Fix the grid here from the distribution of tuned currents in the locked B1r arm, at least 12 log-spaced values.
- **Matched-current agreement.** Left against right at each current, and for two tuner-free scores: the best in-bounds rhythm score across the grid, and the fraction of in-bounds currents that are rhythmic.
- **Current transplant.** Run each side at the other side's tuned current.
- **Question answered:** how much of the gap is the tuner landing in a different place.

**Block 2: location.** Build two hybrid left networks from mirrored right-side values:

- only the stimulated types' own output connections replaced;
- only the rest of the network replaced.

**Question answered:** is the difference in what the descending neuron connects to, or in the pattern-generating network downstream.

**Block 3: class of wiring difference.** Hybrid left networks in which one class of feature is replaced by the mirrored right-side value:

1. weights of connections present on both sides;
2. connections present on one side only;
3. neurons with no partner on the other side;
4. neuron size, which sets excitability in this model;
5. transmitter sign.

Run each class alone, each class left out, and all five together, on MANC. Repeat the most informative ones on MaleCNS.

**Sanity checks for Blocks 2 and 3.** Transplanting left into left changes nothing. Transplanting everything reproduces the right-side screen at the ceiling. If either fails, the mirroring is wrong: fix it before reading any other number. A fresh reviewer audits the mirroring code first.

**Count noise.** Random weight noise barely hurt in run 3. Test noise that can add and remove connections:

- resample the raw synapse counts before the floor is applied, once with Poisson noise and once with the left-right dispersion measured from the data;
- repeat the screen with the floor at 1, 3, 5 and 10.

Report which noise model, if any, reproduces the left-right agreement with no fitted parameter. These experiments need counts from before the floor. If those exist only for MANC, run them on MANC only and say so.

**Reporting for Part B.**

- Gap closure with an interval for every intervention.
- **Rescue table.** Define a flipped type as one whose band differs between sides and whose fraction of rhythmic seeds differs by at least 0.5. For each flipped type, list which single intervention brings it back. Report the share of flips each intervention rescues alone.
- **Case studies, optional.** For the 20 most flipped types (ties broken by name), find a smallest set of differences that flips the prediction. Use BrainIR's budgeted search read-only if it adapts cleanly, and a plain delta-debugging search otherwise.

### Part C: fixes

The list is fixed now. No fix has a fitted parameter.

**Procedure-level**

1. **Dose-sweep scoring.** Replace the tuner with the best in-bounds rhythm score across the fixed grid.
2. **Pooled read-out (optional).** Score the rhythm of the summed motor-pool signal in place of the mean over single motor neurons.

**Network-level**

3. **Lower floor.** Floors of 1 and 3.
4. **Symmetrised.** Homologous weights averaged across the two sides.
5. **Type-pooled.** Each connection replaced by the mean over the homologous type-to-type connections. Two versions: pooled within each side, which leaves the sides distinct, and pooled across both sides.
6. **Input-normalised.** Each neuron's total incoming excitatory weight, and separately its inhibitory weight, set to the mean for its type. This is the model's version of a neuron holding its total input at a set point.
7. **Consensus annotations.** Each neuron's size and transmitter sign replaced by its type's consensus.
8. **All network-level fixes together.**

**Combined**

9. The best passing procedure-level fix with the best passing network-level fix. "Best" means highest specific reproducibility, as defined below.

**Gain.** If a fix breaks the DNg100 control, choose the smallest gain from {0.5, 0.75, 1, 1.5, 2, 3} at which DNg100 passes, using DNg100 only. If none works, the fix fails.

**A fix "restores reproducibility" only if all four hold:**

1. **Control.** DNg100 scores at least 0.5 in at least 12 of 16 seeds.
2. **Agreement.** Cross-fly agreement reaches at least 0.8 of its ceiling, and left-right agreement too where the fix leaves the sides distinct.
3. **Still informative.** The number of predicted driver types stays between half and double the unfixed screen's.
4. **Still about the wiring.** Specific reproducibility is positive with an interval that excludes zero. It is the agreement between the two flies minus the agreement between a fly and its own degree-preserving rewiring. Rewired networks must also still produce few drivers. Define "few" as a number here, from the unfixed controls.

Report every fix, pass or fail, with all four numbers.

### Part D: exams re-scored (exploratory)

For each fix, re-score exam 1 and exam 2 once with the frozen pipelines. Head every table "exploratory, after unblinding". State the comparison with the unfixed model and with two-step signed counting.

### Part E: the forward ledger

- **Types.** Every descending-neuron type that has a driver line in the kit and no clear label in exam 1.
- **Sources.** The authors' model (locked A1), two-step signed counting (locked), and the robust model: the passing fix with the highest specific reproducibility. If no fix passes, the ledger has two sources and says why.
- **Probabilities.** Turn each source's score into a probability of rhythmic front-leg stepping in a decapitated fly, by a one-variable logistic fit to the exam 1 labels. Fit on headless-labelled types if at least 15 of them cover both classes, and on all labelled types otherwise. Report leave-one-out calibration, and state the atlas caveat next to it.
- **One sentence per prediction** that a lab can test, generated by script from a locked number.
- **Stability flags.** For each type and source: do the two flies agree, and do the two sides agree.
- **Decisive experiments.** The 15 types that best separate the sources. Rank by the gap in probability between sources, counting only predictions that are stable across the half-flies. For each: driver-line IDs, which collection holds the line and whether it is listed as available, what each source predicts, and the test protocol in five lines.
- **Scoring rule.** Future results are scored by Brier score against a base-rate guesser, each source separately.
- **Honesty line.** These predictions are made after both exams were unblinded. They are clean with respect to the experiments they predict, because those have not been done.

### Freeze

Have a fresh reviewer audit the rulebook for anything that could be decided later in a self-serving way. Fix what it finds. Commit, tag `ledger-prereg-v4`, push, timestamp.

---

## 6. Stages 2 to 5: run Parts A0 to D

- **Order:** A0, A, Block 1, Block 2, Block 3 and count noise, then C, then D. Stop and think after each: say in the log what the result means for the next step.
- **Seeds:** 16 for Part A, 8 for hybrids, noise models and fixes, always compared on the same seeds.
- **Determinism:** every campaign passes on a re-run sample.
- **Lock:** `LOCK_reliability_v2.json`, tag `ledger-reliability-v2`, timestamp.

---

## 7. Stage 6: lock the forward ledger

- Build the tables under `research/ledger/forward/`.
- **Gates:** determinism; every sentence generated by script from a locked number; a fresh reviewer checks ten entries by hand against the tables.
- Write `LOCK_forward_v1.json`, tag `ledger-forward-v1`, push, timestamp.

---

## 8. Stage 7: results, adversarial review, brief, evidence map

### `results/RESULTS_3.md`

- **First line:** what causes the gap, or that the cause was not found. Do not dress it up.
- **The authors' own scores:** left against right, with the ceiling and the replication rate.
- **The gap:** six agreements with ceilings, simulation and wiring side by side.
- **Causes:** gap closure for procedure, location and each class; the count-noise result; the rescue table.
- **Fixes:** one row per fix against the four criteria.
- **Exams, exploratory:** one row per fix.
- **Alternative explanations.** One row for each, with the test that addresses it and what the test showed:
  - seed noise;
  - ties among zero scores;
  - the one-sided regime being noisier in itself;
  - mismatched homologs or wrong side labels;
  - unequal member counts;
  - one side being worse everywhere;
  - where the tuner lands;
  - our implementation.
- **Three biggest caveats.**

### Adversarial review

A fresh reviewer gets `RESULTS_3.md` and the locked tables, and one instruction: find the most plausible way the headline is an artefact, and test it if a test is cheap. Its report is committed once. Answer it in an addendum.

### `BRIEF.md`

Two pages, plain language, for a fly neuroscientist who has ten minutes.

1. What was tested and how: pre-registered, timestamped, blind scoring.
2. The three results, one short paragraph and one number each, with the main caveat attached to each.
3. Why the two sides disagree, and what fixed it or did not.
4. The decisive experiments: the table, and the ask.
5. Where everything is: the repo, the tags, the locks.

One figure: agreement across the two sides and the two flies, for the wiring, the simulation and each fix, with ceilings marked.

Rules for the brief:

- Every number comes from a locked file.
- State what the work does not show.
- No sentence may claim more than the pre-registered verdicts and the Part C criteria support.
- A fresh reviewer marks any overclaim, and you fix it.

### `EVIDENCE_MAP.md`

One row per claim in the brief: the claim, the locked file and field that supports it, the tag, and its main caveat.

---

## 9. If time runs short

- **Never drop:** the v4 rulebook, Part A0, Part A with ceilings, Block 1, Block 2, the forward ledger.
- **Drop in this order:** the case studies, pooled read-out, MaleCNS repeats of Block 3, floors other than 1 and 5, Part D, the count-noise models, fixes 6 and 7, the brief.

---

## 10. When things go wrong

| Problem | Default action |
|---|---|
| GitHub queues stall | Publish fewer jobs at a time. Do not move predictions to the Mac. |
| Side labels look unreliable | Fix them from anatomy for the types you use, record how, and show the result with and without the corrected types. |
| Bilateral groups are missing for many neurons | Match by type, record the fraction, and say which results depend on it. |
| A sanity check on the mirroring fails | Stop Blocks 2 and 3 until it passes. |
| The authors' data shows no left-right gap | Say so first. Treat the gap as specific to the one-sided procedure, and move the weight to the cross-fly gap. |
| Block 1 closes the whole gap | Then the cause is the procedure. Still run Block 2 and the network-level fixes on a reduced budget. |
| No block closes the gap | That is the result. Report the interactions and stop guessing. |
| A fix breaks DNg100 at every gain | The fix fails. Report it. |
| No fix passes | The ledger has two sources. Say so in the brief. |
| Runner-hours near the cap | Use the informative set everywhere, then drop in the order above. |
| You find a bug after a lock | Make a new version with a changelog. Never edit the locked one. |
| Your context was compacted | Re-read `STATE.md`, `LOG.md` and `RUN4_PROMPT.md`. |

---

## 11. Finish

### Done means

- `ledger-prereg-v4`, `ledger-reliability-v2` and `ledger-forward-v1` exist with hashes and timestamp proofs, or each missing one is explained.
- `RESULTS_3.md`, the adversarial review with its addendum, `BRIEF.md` and `EVIDENCE_MAP.md` exist.
- The baseline checks still pass and all locks verify.

### Handoff: `research/ledger/HANDOFF_4.md`

At most 2,200 words, plain language, printed as your final message too.

1. What exists now: tags, lock hashes, whether pushes worked.
2. Every departure from this prompt, with the reason.
3. The dose-arm check.
4. Part A0: left against right in the authors' own scores, with the ceiling and the replication rate.
5. Part A: the six agreements with ceilings, simulation and wiring side by side, and whether one side is worse everywhere.
6. Part B: the sanity checks; gap closure for procedure, location and each class; the count-noise result; the rescue table in one line per intervention.
7. Part C: one row per fix against the four criteria.
8. Part D: one row per fix, marked exploratory.
9. Part E: how many types are in the ledger, calibration quality, and the 15 decisive experiments.
10. The adversarial review: its strongest objection and your answer.
11. The brief's opening paragraph.
12. Compute and wall-clock time.
13. What worries you.
14. What you would do next.
