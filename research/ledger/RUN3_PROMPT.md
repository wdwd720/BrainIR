# BrainIR Prediction Ledger: Run 3

**Scope of this run:** the main exam. Lock predictions for what happens when each developmental family of nerve-cord neurons (each hemilineage) is switched on, collect the published headless-fly results blind, and score once if every gate passes. Alongside it: a reliability study that needs no labels, and a post-mortem of exam 1.

Everything so far is on branch `ledger/v1` under `research/ledger/`. Read `HANDOFF_2.md`, `results/RESULTS_1.md`, `LOG.md`, `PREREG.md`, `PREREG_v2.md` and the run 2 label review before you design anything.

This is a long autonomous run: expect 12 to 24 hours. I will not be watching. Do not stop to ask me things. Where this prompt is silent, or wrong about the repo, make the call that best serves the goal, log the decision and the reason, and keep going. Any pause must schedule its own re-check within 10 minutes and resume by itself.

Think hard before every irreversible step: the rulebook freeze, each lock, and the unblinding. Before each one, write a short pre-mortem in the log and check the most likely way it could be wrong.

---

## 1. Where things stand

**Exam 1 is done.** The authors' own type-level scores did not predict which descending neurons evoke front-leg rhythm in real flies.

- AUROC 0.577 (0.417 to 0.724) on 39 types.
- The best wiring baseline, two-hop signed, scored 0.669.
- Control networks averaged 0.50.

**Its weak spots are known.**

- 21 of the 25 "yes" types come from one atlas of intact flies, and that atlas supplied no "no" type.
- 25 of the 39 types have a model score of exactly 0, so the result rests on 14 types.
- Leg rhythm was inferred from reported behavior, not measured.

**The two flies disagree.** The same procedure on MANC and MaleCNS gives a rank agreement of 0.37 (B1r against B2r). Run 1 put the within-fly split-half agreement near 0.93.

**The six-leg arm is still not locked.** Per-leg rhythm reproduces the authors' run. Coupling on one same-side leg pair does not: T1R to T2R is 0.14 in our build and 0.60 in theirs.

---

## 2. Why hemilineages, and what this run must achieve

Exam 1 was limited by its data: few types, mostly intact flies, mostly positive reports. Two published studies remove all three limits.

- **Harris et al. 2015 (eLife).** Each hemilineage was activated with a heat-sensitive channel in decapitated flies, and the movements were described and filmed.
- **Soffers et al. 2025 (eLife).** A new driver library for almost every hemilineage, with light-driven activation in decapitated and intact flies and a lineage-to-behavior map.

Hemilineages make up most of the nerve cord, the flies are headless like the model, both studies report every family including the odd ones, and the connectome annotates every neuron with its hemilineage. Two labs measured the same thing with different tools, so the labels can be checked against each other.

This run must:

1. Freeze a third rulebook, `PREREG_v3.md`, before any hemilineage simulation exists and before any hemilineage result is read.
2. Lock the hemilineage predictions: the authors' model, wiring baselines and controls.
3. Collect and lock the hemilineage labels, blind.
4. Pass the gate and score once. Or fail the gate and stop.
5. Run and lock the reliability study.
6. Write the exam 1 post-mortem, marked exploratory.

---

## 3. Hard limits

1. **One unblinding for exam 2, through the gate in Stage 5 only.** Until then, never put a hemilineage prediction next to a hemilineage outcome.
2. **No hemilineage simulation before the freeze.** Not one, not a pilot, not "just to see if it runs". Until `ledger-prereg-v3` is tagged, the only groups you may simulate are DNg100, DNb08 and synthetic test groups chosen by a random number generator. This is what makes the exam clean, because the published results are public knowledge.
3. **You never author labels.** You launch sessions, move files, validate schemas and run deterministic scripts. Do not read the hemilineage papers' results yourself.
4. **Frozen things stay frozen.** Every existing lock, the BrainIR locks, the Phase 2 to 4 files and `main` are untouched.
5. **No paid compute.** GitHub Actions first under the same trust gate as run 2, the Mac second. No Modal. Stop at 300 runner-hours.
6. **Nothing public except my repo.** Push the branch and tags. Never push `main`. No force pushes: leave the old commit that contains my user name alone.
7. **After unblinding, nothing moves.** Extra analyses go in a section marked exploratory.

---

## 4. Stage 0: housekeeping and one diagnosis

- Start `caffeinate`. Save this prompt as `research/ledger/RUN3_PROMPT.md`. Confirm the tree is clean and all locks verify. Re-run the baseline checks.
- Continue `LOG.md` and keep `STATE.md` current.
- Re-run the GitHub Actions trust gate before any new campaign.

**Diagnose the build difference first, in at most 90 minutes.** Exam 2 runs on the full-cord build, so find out why T1R to T2R coupling differs from the authors' run before the freeze. Use DNg100 only. Check the obvious candidates: number of replicates, how replicate parameters are drawn, solver and tolerance, number precision, and which neurons define each leg's signal.

- If you find a build error that changes which motor neurons become active, fix it as a new locked version and repeat the full-cord checks before going on.
- If the difference is confined to phase relationships, record it and go on. No exam 2 prediction uses coupling between legs.

---

## 5. Stage 1: `PREREG_v3.md`

Write it so a stranger could run the exam without asking a question. Where I give a default you may change it for a stated reason, but only before the freeze.

### Disclosure

- The published hemilineage results are public. You may know some from training, and the repo's notes may mention some. I have read published outcomes for about six hemilineages (9A, 12A, 8A, 21A, 5B, 6B) and I am not repeating them here.
- So the blind is procedural. Every definition is frozen before the first hemilineage simulation, and nothing is tuned afterwards.
- Search the repo for any hemilineage activation outcome already written down, and list what you find.

### Units and groups

- **Unit.** The hemilineage, as annotated in the connectome.
- **Primary group.** Every neuron annotated with that hemilineage in the three thoracic segments, both sides.
- **Stimulation.** Every member receives the same current, whatever its transmitter. Its outputs keep the sign the model already assigns. This mirrors an experiment that depolarises every labelled cell.
- **Sensitivity groups, declared now.** All segments including abdominal; postembryonic neurons only, if the annotation supports it; one segment at a time; one side only.
- List every hemilineage with its neuron count and transmitter make-up from the annotations alone, and fix the list of units here.

### Prediction arms

- **H-M, the authors' model.** The full-cord procedure already written in L14, unchanged, on the authors' exact full-cord network, 16 seeds. This is the primary arm.
- **H-D, dose.** The same model at a fixed grid of strengths with no auto-tuning.
- **H-S, wiring only.** For each group: direct signed drive onto each motor pool; two-hop signed; three-hop signed; unsigned versions; and the steady state of the linearised model using the model's own coupling constant. No fitted parameter anywhere.
- **H-C, controls.** H-M on five degree-preserving rewirings and five class shuffles of the full cord.
- **H-X, other animals (optional).** The same arms on any other nerve-cord connectome you can obtain and verify: MaleCNS, the female nerve cord, the female brain-and-cord dataset on Harvard Dataverse (doi 10.7910/DVN/7WTH1N).

### The shared vocabulary

Predictions and labels use the same fixed list of phenotype dimensions. Start from this list and finalise it here:

1. any visible movement
2. front legs move
3. middle legs move
4. hind legs move
5. legs flex or the body lowers, held
6. legs extend or the body rises, held
7. repeated leg movement without coordination
8. coordinated walking
9. grooming-like leg rubbing
10. jump or takeoff
11. any wing movement
12. wings raised or opened, held
13. wing buzzing or flight-like beating
14. haltere movement
15. abdomen movement

### From model output to the vocabulary

- **Motor map first.** Build a table from every motor neuron in the full-cord network to body part, segment, side and action (for example tibia flexor, wing power muscle, jump muscle), from the annotations and the anatomical literature. Names only, no activation outcomes. Have a fresh reviewer check it. Freeze it.
- **Rules.** For each dimension, write an exact formula that turns motor-pool activity into a continuous predicted value: which pools, what counts as active, how held and rhythmic movement are told apart, how flexion and extension are compared.
- **Calibration.** Thresholds may be set only from DNg100 and DNb08 simulations, from random synthetic groups, and from criteria that do not depend on which group is stimulated.
- **Declared gaps.** If a dimension cannot be predicted from the motor map, say so now and drop it from the primary analysis. A wiring baseline cannot tell rhythmic from held, so it contributes nothing on those dimensions. That is intended.

### Truth

- **Sources.** Harris 2015 and Soffers 2025, plus any other study that activates a whole hemilineage, found by blind search.
- **Coding.** Each (hemilineage, dimension) cell is `yes`, `no`, `unclear` or `not_assessed`, with preparation, effector, penetrance where given, and a locator with a short quote. Readers also record what the driver labels when the source says it covers only part of a hemilineage or includes other cells, and may add a free-text "other" observation.
- **Record type.** Whole-hemilineage, two-sided activation is the primary record type. Clonal or one-sided activation is recorded and kept for secondary analysis.
- **Consensus.** Decapitated observations outrank intact ones. If the two labs both report a cell and disagree, it is `conflicting` and leaves the primary analysis. If only one reports it, use that one.
- **External check.** The published summary of Harris 2015 in the MANC premotor paper (Cheong et al. 2024) is used only to measure how well our coding of Harris agrees with someone else's. It is never truth.

### Primary statistic

Identification: does the model's predicted pattern pick out the right hemilineage?

- A coded dimension is one whose consensus cell is `yes` or `no`. Code yes as 1 and no as 0.
- Standardise each predicted dimension across hemilineages. Centre each observed dimension.
- For hemilineage h, score every candidate k by the sum over h's coded dimensions of predicted(k) times observed(h). Record the percentile rank of the true match, where 1 means the true match scored highest.
- The statistic is the mean percentile rank over hemilineages. Chance is 0.5.
- A p-value from 10,000 permutations of hemilineage labels, a 95% bootstrap interval over hemilineages, and a fixed seed.
- Also report top-1 and top-3 accuracy.

### Decision rules, declared now

- **"The model predicts"** if the one-sided p is below 0.05 and the interval's lower bound is above 0.5.
- **"The simulation adds value beyond wiring"** only if H-M beats the best H-S baseline on a paired bootstrap.
- **"Underpowered"** if fewer than 20 hemilineages have at least 3 coded dimensions. Then report descriptively and claim nothing.

### Secondary analyses, all descriptive

- The ceiling: how well one lab's results identify the other's.
- Each lab separately.
- Per-dimension AUROC and a pooled AUROC.
- Excitatory against inhibitory hemilineages. The model is silent at rest, so say in advance what it can and cannot predict for inhibitory ones.
- Dose, controls, sensitivity groups and other animals.

### Scoring code, the gate and the freeze

- Implement the exam 2 scoring now and test it on synthetic data with known answers. Give it its own unblinding flag, separate from exam 1's retired one.
- Add a test that fails if any label-side code reads a prediction file.
- Copy the gate from Stage 5 into the document.
- Have a fresh reviewer audit the rulebook for leaks, loopholes and anything that could be decided later in a self-serving way. Fix what it finds.
- Commit, tag `ledger-prereg-v3`, push, timestamp.

---

## 6. Stage 2: hemilineage predictions

Only after the freeze.

**Gates**

- **Full cord accepted.** The run 2 checks that passed (per-leg rhythm, active motor-neuron counts, the DNg100-only calibration) still pass on the build you use.
- **Procedure unchanged.** The code that stimulates a group is the L14 procedure with only the member list changed. Show this with a regression on DNg100.
- **Determinism.** A re-run sample gives identical digests.
- **Trust gate.** The compute platform reproduces locked jobs.
- **Independent review.** A fresh reviewer audits the group builder, the motor map and the prediction rules, and confirms that no hemilineage simulation ran before the freeze. The run registry and the git history must show it.

**Outputs**

For each arm, one tidy table: one row per hemilineage and one column per dimension, plus the raw motor-pool table and compressed motor-neuron traces. Record for every group how the tuner ended: accepted, too weak, or saturating.

**Lock**

Write `LOCK_predictions_h1.json`, tag `ledger-predictions-h1`, timestamp. Keep it local until the labels lock, as in run 2. An arm that fails its gate is not locked. Say why and move on.

---

## 7. Stage 3: hemilineage labels

Use the run 2 machinery as it stands: the room launcher, the outside-read block, the canary, the mechanical downloader, the session contract, two readings plus adjudication, the verification sample, the transcript audit and the label review. Re-run the canary once, because the deny rules were extended after the last one.

Changes for this exam:

- **Kit.** The dimension list from the rulebook, the cell vocabulary, and a hemilineage name list with synonyms, alphabetical and prediction-free.
- **Sources into rooms.** Full text, tables, figure images and figure legends for each source. Supplementary videos may be given to readers as frame montages with their legends, made by a script. Do not look at the montages yourself. The papers' own words are the primary evidence.
- **Sessions.**
  - Two independent readers per source, working hemilineage by hemilineage.
  - One session that codes the Cheong 2024 summary, for the external check only.
  - Searches for other whole-hemilineage activation studies: by hemilineage name, by driver, and by papers citing the two main sources.
- **Banned content.** Readers must not open connectome-simulation papers or this repo. A score sighting here means seeing any model prediction for a hemilineage.
- **Limits.** Use the same model as run 2. Respect the quota thresholds by slowing down, never by stopping.
- **Assembly.** The consensus matrix by script, with per-lab matrices beside it. Agreement between the two readings, between our Harris coding and the published summary, and between the two labs. Labels only.

Commit, write `LOCK_labels_h1.json`, tag `ledger-labels-h1`, push both locks, timestamp.

---

## 8. Stage 4: reliability study (no labels needed)

Run this while the label sessions work. It is descriptive, and its plan goes into `PREREG_v3.md` before any new simulation.

The question: when the same procedure gives different answers for two flies, is that the animals, the reconstruction, or the simulation?

- **R1, what we already have.** Break down B1r against B2r:
  - all types;
  - types that are non-zero in at least one fly;
  - types whose cross-fly match is high-confidence;
  - agreement of bands and of the top 10 and top 30;
  - the within-fly split-half agreement for each fly, as the ceiling.
- **R2, wiring against simulation.** Compute every wiring baseline for the same types on both flies. Compare how well the two flies agree on wiring with how well they agree on simulation output.
- **R3, noise equivalence.** Re-run the B1r screen on MANC with small random changes to connection weights, at 5%, 10% and 20%, three noise seeds each. Report the agreement with the unperturbed screen at each level, and the noise level that matches the cross-fly agreement.
- **R4, left against right in one animal.** Run the screen with only the left members of each type, then only the right, reading out the same-side motor neurons. The two sides of one fly are two copies built from the same genome, so this separates differences between animals from instability inside one animal. If the side annotation for descending neurons cannot be trusted, skip R4 and say so.

Lock the outputs as `LOCK_reliability_v1.json` and tag `ledger-reliability-v1`.

---

## 9. Stage 5: the gate, the unblinding, the results

### The gate

Compute it from label files and hemilineage names only. Every condition must hold.

1. All locks verify in a clean checkout.
2. No session that contributed a record breached.
3. The label review has no blocker, and the verification sample's error rate is at most 10%.
4. Agreement between the two readings has a kappa of at least 0.7 over coded cells.
5. At least 20 hemilineages have at least 3 coded dimensions.
6. A fresh reviewer signs a checklist confirming 1 to 5, confirming that nothing has been joined, and confirming that no hemilineage simulation predates the freeze.

**If any condition fails, do not unblind.** Stop and write the handoff with label-only numbers.

### The unblinding

- Create the exam 2 flag naming the locks.
- Run the frozen pipeline once for the primary analysis, then each pre-declared secondary run once.
- If the pipeline crashes, fix only the crash and log it.
- Have a fresh subagent recompute the primary statistic with its own code. The two must agree.
- Retire the flag afterwards, as in run 2.

### The results

Write `research/ledger/results/RESULTS_2.md`.

- **First line:** the pre-registered verdict in plain words. Do not soften it and do not dress it up.
- **Headline:** mean percentile rank, interval, p-value, top-1 and top-3 accuracy, number of hemilineages.
- **Ceiling:** the lab-against-lab identification, so the headline has a scale.
- **Wiring:** each baseline, and the paired comparison with the best one.
- **Controls:** the ten control networks.
- **By class:** excitatory and inhibitory hemilineages separately.
- **Scorecard:** one row per hemilineage with its rank, what was predicted and what was observed.
- **Figures:** the scorecard, and the predicted-against-observed matrix.
- **Three biggest caveats,** in plain language.
- **Exploratory:** clearly marked.

Commit, tag `ledger-scorecard-h1`, push, timestamp.

---

## 10. Stage 6: exam 1 post-mortem (exploratory)

Exam 1 is unblinded, so everything here is exploratory and must say so. Write `results/POSTMORTEM_1.md`.

- **The full secondary tables** from `RESULTS_1.md` in one place: headless against intact, systematic sources only, exposed types included, every baseline, every arm.
- **Why so many zeros.** For the labelled types that score 0, separate "the screen could not drive the type at all" from "it drove the network and the read-out stayed silent". Say what that implies about what the screen can test.
- **The source confound.** How the picture changes when the atlas is removed, and when only headless records are used. Give counts with every number.
- **Wiring.** Which wiring features carried the two-hop baseline.
- **No new claims.** This section explains exam 1. It does not rescue it.

---

## 11. If time runs short

- **Never drop:** the v3 rulebook, H-M and H-S predictions, the hemilineage labels, the gate.
- **Drop in this order:** H-X, R3, H-D, R4, H-C, the post-mortem, R2.
- The exam comes before the reliability study if you must choose.

---

## 12. When things go wrong

| Problem | Default action |
|---|---|
| GitHub Actions cannot be used, or stalls | Run locally under the same trust gate. Do not wait. |
| The motor map cannot cover a body part | Drop that dimension before the freeze and say so. |
| The tuner saturates or stays too weak for a group | Record it as the model's answer. Do not adjust the procedure. |
| A source's results are only in figures | Give readers the figure images and legends. |
| The two labs disagree widely | That is a finding. Report it, and score against each lab separately. |
| A session ends early | Reassign its unfinished work to a new session. |
| An arm fails its gate | Do not lock it. Move on. |
| The gate fails | Stop without unblinding. Report label-only numbers. |
| You find a bug after a lock | Make a new version with a changelog. Never edit the locked one. |
| Your context was compacted | Re-read `STATE.md`, `LOG.md` and `RUN3_PROMPT.md`. |

---

## 13. Finish

### Done means

- `ledger-prereg-v3`, `ledger-predictions-h1`, `ledger-labels-h1` and `ledger-reliability-v1` exist with hashes and timestamp proofs, or each missing one is explained.
- The gate was evaluated and its result is written down.
- Either `RESULTS_2.md` and `ledger-scorecard-h1` exist, or nothing was unblinded and the reason is stated.
- `POSTMORTEM_1.md` exists.
- The baseline checks still pass and all locks verify.

### Handoff: `research/ledger/HANDOFF_3.md`

At most 2,000 words, plain language, printed as your final message too.

1. What exists now: tags, lock hashes, whether pushes worked.
2. Every departure from this prompt, with the reason.
3. The build diagnosis from Stage 0.
4. The rulebook in ten lines: units, the final dimension list, dropped dimensions, the statistic and the decision rules.
5. Predictions only: for each arm, how many groups the tuner accepted, found too weak, or found saturating.
6. Labels only: sessions, sources, coded cells, hemilineages with at least 3 coded dimensions, agreement between readings, agreement with the published summary, agreement between the two labs.
7. The gate: each condition and whether it held.
8. If unblinded: the first line of `RESULTS_2.md`, the headline, the ceiling, the wiring comparison, the controls and the scorecard.
9. The reliability study: R1 to R4 in one short table, and what it says about why the two flies disagree.
10. The post-mortem in five lines.
11. Compute and wall-clock time.
12. What worries you.
13. What you would do next.
