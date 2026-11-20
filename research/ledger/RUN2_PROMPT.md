# BrainIR Prediction Ledger: Run 2

**Scope of this run:** rebuild the labels properly, repair the prediction arms that failed, then score once if every gate passes. If any gate fails, stop without unblinding.

Everything from run 1 is on branch `ledger/v1` under `research/ledger/`. Before you design anything, read `HANDOFF_1.md`, `LOG.md` (L1 to L48), `PREREG.md`, the label review, `gates/G3_REPORT.md`, `ARM_DIAGNOSTICS.md` and `final/`.

This is a long autonomous run: expect 12 to 24 hours. I will not be watching. Do not stop to ask me things. Where this prompt is silent, or wrong about the repo, make the call that best serves the goal, log the decision and the reason, and keep going.

**Never wait for me.** In run 1 a spend guard paused the work and six hours were lost. Any pause, for any reason, must schedule its own re-check within 10 minutes and resume by itself. If something stays blocked for 30 minutes, take the fallback in section 10 and move on.

Think hard before every irreversible step: the rulebook freeze, each lock, and above all the unblinding. Before each one, write a short pre-mortem in the log and check the most likely way it could be wrong.

---

## 1. Where things stand

**Sound and locked**

- Predictions v1: 22 arms. The primary prediction is A1, the authors' own type-level scores for 321 types (11 predicted drivers, 216 predicted non-drivers, 134 scores of exactly 0).
- The scoring pipeline, tested on synthetic data and guarded by `UNBLIND.json`.
- Nothing has been joined.

**Not good enough: the labels**

- Labels v1.1 give 18 types with a clear front-leg label: 3 yes, 15 no.
- The primary set is 12 types: 1 yes, 11 no. The frozen rule needs at least 20 types and at least 5 in each class. Scoring now would waste the one unblinding.
- Why it happened:
  - The atlas, walking_stopping and search_names sessions were excluded for re-reading images their own web fetches had saved (L37). The final set has no record from the Cande 2018 atlas, Bidaye 2014 and 2020, or Sapkal 2024.
  - Sessions ended by themselves after 14 to 47 minutes.
  - About a third of web fetches failed, mostly with 429.
  - PDFs and images could not be read.
  - Search-found records were barred from the consensus by rule.
  - 15 records from six ordinary papers carry a score-sighting flag, and nobody recorded what was actually seen.
- What is reachable, by name only:
  - 49 non-exposed A1 types appear in some record collected by some run 1 session.
  - The atlas has 120 driver lines. 84 resolve to 43 types, 27 of them non-exposed A1 types. The other 36 lines are unmapped.
  - The 2025 catalogue covers 80 non-exposed A1 types with driver lines.

**Not locked or not trustworthy: three prediction arms**

- **B3 and B6 (full cord).** Per-leg rhythm reproduced the authors' run. Gate G3 failed only on item 4, "no coupling between legs". The same test finds coupling in the authors' own traces (L18), so the item encoded a claim their data do not support.
- **B2 (second fly).** The tuner accepted a current at which almost no front-leg motor neuron was active, so the DNg100 control scored 0.059 (L29).
- **B4 (walking background).** 199 of 207 "halts" calls are runaway activity, and DNg100 "halts" itself. B5 suggests why: rhythm exists only inside a window of drive.

---

## 2. What this run must achieve

1. Freeze a second rulebook, `PREREG_v2.md`, before anything else is produced.
2. Lock the repaired prediction arms as an additive predictions v2.
3. Collect and lock labels v2: a complete, fresh, blind collection with the tooling fixed.
4. Pass the unblinding gate, score once, and write the results. Or fail the gate and stop.

---

## 3. Hard limits

1. **One unblinding, through the gate in Stage 4 only.** Until then, never join labels to predictions, never compute a hit rate, never look at a score next to an outcome.
2. **Frozen things stay frozen.** Never edit anything under the v1 locks (rulebook, predictions, labels v1 and v1.1). The BrainIR locks, the Phase 2 to 4 files and `main` are untouched, as in run 1.
3. **You have seen the predictions, so you never author labels.** You launch sessions, move files, validate schemas and run deterministic scripts. Reading, coding, adjudicating and verifying labels is done only by blind sessions.
4. **No fly outcome may shape a prediction.** The repairs in Stage 2 are calibrated on DNg100 alone. DNb08 may be reported as a check and must not be tuned on.
5. **No paid compute.** Do not use Modal in this run: its credit is used up. Heavy compute runs on GitHub Actions' free hosted runners for this public repo, with the Mac as the fallback. See Stage 0.
6. **Nothing public except my repo.** Push the branch and tags to `origin`. Never push `main`. No new accounts, no emails, no posts.
7. **After unblinding, nothing moves.** No label change, no model change, no scoring-rule change in this run. Extra analyses are allowed only in a section marked exploratory.

---

## 4. Stage 0: housekeeping

- Start `caffeinate` and keep it alive.
- Save this prompt as `research/ledger/RUN2_PROMPT.md`.
- Confirm the tree is clean, all four locks pass `lock.py check`, and `UNBLIND.json` does not exist.
- Re-run the Stage S baseline from run 1. The same checks must pass at the end.
- Commit the per-control check script that was left out of git (L48).
- Continue `LOG.md` from L49 and keep `STATE.md` current.

**Compute for this run: GitHub Actions first, the Mac second**

The repo is public, so GitHub's standard hosted runners are free for it. Each Linux x64 runner has 4 CPUs and 16 GB of memory, and a free account runs 20 jobs at once. Check the current limits yourself before relying on them: the per-job time limit (6 hours as far as I know), the 256-job cap on a matrix, and artifact limits.

Set it up like this:

- **Workflow.** One workflow file on the `ledger/v1` branch only, triggered by pushes to that branch or by tags. A manual trigger would need the file on `main`, and `main` is never touched. Pin the runner image by version, not `latest`.
- **Can you push it?** Pushing a workflow file may need the `workflow` permission on the GitHub login. Test this first with a trivial workflow. If the push is refused and you cannot fix it without me, go to the Mac fallback at once.
- **Environment.** Install the same Python and the same exact library versions as the pinned Modal image from run 1 (L11, L12). Record the numerics fingerprint on the runner.
- **Inputs.** Runners rebuild the networks from the authors' pinned files through `fetch_external()`, or receive the packed payload as a release asset. Either way, verify the payload hash on the runner against the hash used in run 1.
- **Jobs.** Split each arm into chunks that finish in well under half the time limit. Each chunk uploads its results as an artifact. Make chunks safe to re-run, download them with `gh`, and verify digests.
- **Logs.** Workflow logs on a public repo are public. Print progress only, never per-type scores. No tokens or secrets in the workflow.
- **Fair use.** GitHub allows hosted runners for work on the repo's own software. Stay inside that: run only the arms in Stage 2, no speculative reruns, and stop at **300 runner-hours** in total.

**Trust gate for the new platform.** Before any new arm, re-run 100 locked run 1 jobs on a runner, spread across arms and including some full-cord DNg100 seeds.

- If the digests are identical, proceed.
- If they differ only at rounding level (same usable flags, same tuned currents, score differences under 0.001), proceed and mark the new arms "different platform" in the lock.
- If they differ more than that, do not use the platform.

**Mac fallback.** If GitHub Actions cannot be used for any reason (push refused, Actions disabled and not fixable, the trust gate fails, a queue stalls for 30 minutes), run Stage 2 locally with about 6 workers so the label sessions keep running. Apply the same trust gate against the locked Modal results, record the platform and fingerprint, and mark the arms "different platform". Locally there is time for B1r, B2r and B3. Drop B6.

Do not let compute problems hold up Stage 3. The labels need no heavy compute.

---

## 5. Stage 1: `PREREG_v2.md`

The v1 rule forbids amending a stage after it has produced data. So v1 is not amended. v2 is a new, separately pre-registered label collection plus new secondary arms, frozen before either produces data. Say this in the changelog. For every change, state whether labels existed (yes, v1) and whether any joined information existed (no).

Write the document in three parts and a disclosure.

### Part L: labels v2

- **Fresh collection.** v2 is made from scratch. No v2 room contains a v1 record. v1 and v1.1 stay as they are.
- **Unchanged from v1.** The labeling conventions, the record schema and vocabularies, the two readings plus adjudication, and the type consensus rule. List any clarification you must add, and add none that depends on a particular neuron.
- **Breach rule.** A breach is a successful access to anything outside the session's room, except files in the session's own tool-results folder that the session itself fetched from an allowed host. Reading the repo, any ledger directory, another room or a banned host is still a breach, and a breaching session is still excluded.
- **Score sighting.** A sighting is seeing a rhythm score, rank or driver call for a DN type from the Pugliese-type activation screen, wherever it is printed (the Pugliese papers, the simulation part of the 2026 Sapkal preprint, BrainIR). Another paper's own model does not count. The reader records where the sighting was.
- **Eligibility.** A record is eligible whatever session found it, reader or search, once it has passed the second reading and adjudication.
- **Session contract.** Every session returns a disposition for every source assigned to it: records, "no qualifying experiment", or "unreachable" with the reason. A source with no disposition is reassigned to a new session.
- **Recall rule.** After the first complete collection, run independent search rounds until a round adds fewer than 10% new (DOI, type) units, or three rounds have run. Report the capture-recapture estimate again and say what it assumes.
- **Line specificity.** Fill it by script from the kit's `driver_lines.csv` where the line ID matches. A line is "clean" only when a source says so. Otherwise it stays "unknown".
- **Verification sample.** A fresh blind session checks 30 random final records against their sources. An error rate above 10% on the front-leg field is a blocker.
- **Kit v2.** Version the labeler kit with these changes and freeze it together with this rulebook. The type list stays alphabetical and score-free.

### Part P: prediction additions

All are secondary. A1 stays primary and untouched.

- **Tuner v2, for the two-fly comparison.** It is B1's locked procedure plus one acceptance condition: at least K active front-leg motor neurons. Fix K on DNg100 alone: the smallest K in {1, 2, 3, 5, 10} for which the DNg100 pair scores at least 0.5 in at least 12 of 16 seeds on both the MANC and the MaleCNS front-leg networks. If no K works, anchor the current on DNg100 instead (L29) and say why. Run it on both networks, giving **B1r** and **B2r**, so the two flies are compared under one procedure.
- **B3 and B6, the full cord.** Use the procedure written in run 1 (L14), unchanged. Rewrite G3 item 4 as "coupling between legs is consistent with the authors' own traces under the same test", and state the consistency rule before re-running. It compares two simulations and involves no fly data.
- **B4 v2.** Recompute the calls from the stored replicates. No new simulations. "Halts" needs all three: a score below 0.5 in at least 75% of replicates; a median paired fall in active motor neurons of at least 25%; runs that stay inside the screen bounds. Anything over the bounds is "saturates". Report whether the direction holds across strengths 32, 128 and 512.

### Part S: scoring

- **Unchanged.** The primary prediction, the primary set, the statistic, the bands and the three decision rules.
- **Label versions.** Labels v2 is primary. Labels v1.1 is a sensitivity analysis. This choice is made now, knowing only that v1.1 is too small.
- **New arms.** B1r, B2r, B3, B6 and B4 v2 enter as secondary analyses. Extend the scoring code for them as a logged change with a new lock version, tested on synthetic data.
- **Runs.** One primary run on labels v2. Each pre-declared sensitivity run happens once. List them here.
- **The unblinding gate.** Copy the conditions from Stage 4 into the document.

### Disclosure

State plainly what informed v2: label-side counts and failure causes from v1, prediction-side counts, and no joined information. State that this protocol was drafted by someone who has seen model scores for some types, and that it contains no rule about any particular neuron.

### Freeze

Have a fresh reviewer audit `PREREG_v2.md` for leaks, loopholes and anything that could be decided later in a self-serving way. Fix what it finds. Commit, tag `ledger-prereg-v2`, push, timestamp.

---

## 6. Stage 2: prediction additions

Run this stage and Stage 3 in parallel if compute is slow. Both procedures are frozen in Stage 1 and no information flows between them. Record the real order of the locks.

One ordering rule: finish G3 v2, including its DNg100-only calibration step, before the first v2 label session starts. The rest of this stage may overlap with Stage 3.

**Gates**

- **Tuner regression.** With the new condition switched off, tuner v2 reproduces B1 exactly on a random sample of 30 types and all 16 seeds.
- **Positive control.** DNg100 scores at least 0.5 in at least 12 of 16 seeds in B1r and in B2r. Report DNb08 as well.
- **G3 v2.** Items 1 to 3 and 5 as in run 1, item 4 as rewritten.
- **Determinism.** A re-run sample gives identical digests.
- **Nothing broken.** The baseline checks still pass.
- **Independent review.** A fresh reviewer audits the new code and the calibration for any use of a neuron other than DNg100.

**Lock**

Write `LOCK_predictions_v2.json` as an addition to v1, never a replacement. Mark every arm "locked after labels v1 existed, before any unblinding". Tag `ledger-predictions-v2`, push, timestamp. An arm that fails its gate is not locked. Say why and move on.

**One thing to write down for the next run.** The paper says the six legs show no phase coupling, and its own traces show coupling under your test. Check the notes for the statistic the paper used, and record in the handoff whether the difference comes from the test, from the leg pairs examined, or from the claim itself.

---

## 7. Stage 3: labels v2

### Isolation

- Start from run 1's launch command and flags (`labels_rooms.py`, L16), in new rooms under `~/ledger_rooms/run2/`.
- Add a block on reading the repo and every ledger directory at a level the model cannot talk its way past. Try a tool-level deny rule first. If that does not hold, wrap the session in an operating-system sandbox such as `sandbox-exec` with a profile that denies reads of those paths.
- Web rules need explicit subdomains (L22).
- **Canary first.** In a throwaway room, prove all of these before launching any real session:
  - a read of a file in the repo fails;
  - a read of a planted fake predictions file outside the room fails;
  - a banned host and its subdomains cannot be fetched;
  - the room's own files and the session's own tool-results can be read;
  - a PDF and an image placed in the room can be read.
- If the outside-room block cannot be enforced, fall back to run 1's guard plus the audit, and state the weakness.

### Sources

- Build registry v2 as the union of:
  - the v1.1 registry;
  - every DOI found by any run 1 session, including the excluded ones;
  - the leads listed in `RUN1_PROMPT.md`;
  - what the new search sessions find.
- A DOI list carries no outcome, so you may assemble it.
- **Download mechanically.** A script with no model in the loop fetches each source into the rooms that need it: full text as text, figures as images, supplementary tables as text or CSV, PDFs as text plus page images. Use open-access APIs such as Europe PMC where they exist, back off on 429, and log every failure. Record a manifest with hashes.
- Do not read the downloaded papers yourself. You know the predictions, so reading outcomes would be a join in your head.
- The dedicated simulation sources go only into their own dedicated room. Types that can only be read there are exposed by nature, as in v1.

### Sessions

- **Readers.** At most 6 sources per session, already in the room. There is no time limit, and the session contract applies. Run every family again: atlas, walking and stopping, grooming, steering, escape and landing, driver-line resources, the dedicated simulation papers, and recent broad studies.
- **Atlas.**
  - One session maps all 120 lines to DN types from the atlas's own figure and tables, Namiki 2018 and the 2025 catalogue. It records names only.
  - Two independent sessions code each line's activation result by line ID, from the paper's figures and source data. They count as the two readings. They do not receive the type map. A script applies it afterwards.
- **Searches.** By type name, by behavior, by driver-line ID, and by papers that cite the atlas, Namiki 2018 or the catalogue. New DOIs go into the registry, get downloaded, and are assigned to readers.
- **Second reading and adjudication.** As frozen, for every record. With the sources already in the room, a quote that cannot be found is a real failure and not a fetch error.
- **Verification sample.** As in Part L.
- **Limits.** Use the same model as run 1. Respect the quota thresholds in L36 by slowing down, never by stopping.

### Assembly

- Produce the same tables as v1.1, in a new `labels_v2/` directory, with the consensus made by the frozen script under the v2 eligibility rule.
- Apply the line-specificity fill.
- Write `v1_vs_v2.md`: agreement between the two independent collections on the experiments they share. Labels only.
- Run the frozen transcript audit under the v2 breach rule. Exclude any breaching session.
- Have a fresh reviewer, working from labels only, give a verdict: usable, usable with caveats, or blocked.
- Redact home paths as in L40. Commit, write `LOCK_labels_v2.json`, tag `ledger-labels-v2`, push, timestamp.

### Movies

Inventory only. Unzip the Dryad archive, then report the number of clips, how filenames map to lines, the resolution, frame rate and codec. Do not watch or analyse them. A masked movie analysis may come in a later run.

---

## 8. Stage 4: the gate, the unblinding, the results

### The gate

Compute it from label files and type names only. Every condition must hold.

1. The locks for rulebook v1 and v2, predictions v1, predictions v2 if it exists, and labels v2 all pass in a clean checkout.
2. No session that contributed a record breached under the v2 rule.
3. The label review has no blocker, and the verification sample's error rate on the front-leg field is at most 10%.
4. Agreement between the two readings on the front-leg field has a kappa of at least 0.7.
5. The primary set (labels v2, clear front-leg label, among A1's 321 types, not exposed) has at least 20 types, at least 5 yes and at least 5 no.
6. A fresh reviewer signs a checklist confirming 1 to 5 and confirming that nothing has been joined.

**If any condition fails, do not unblind.** Stop, and write the handoff with label-only numbers and what it would take to pass.

### The unblinding

- Create `UNBLIND.json` naming the locks.
- Run the frozen pipeline once for the primary analysis, then each pre-declared sensitivity run once.
- If the pipeline crashes, fix only the crash, log it, and never alter a rule.
- Have a fresh subagent recompute the primary AUROC from the locked files with its own code. The two must agree.

### The results

Write `research/ledger/results/RESULTS_1.md`.

- **First line:** the pre-registered verdict in plain words. Say whether the model predicts, whether it adds value beyond wiring, or whether the analysis is underpowered. Do not soften it and do not dress it up.
- **Headline:** the primary AUROC with its interval and p-value, and the number of types in each class.
- **Bands:** precision among predicted drivers and negative predictive value among predicted non-drivers, with counts.
- **Baselines:** A1 against each anatomical baseline, and the paired comparison with the best one.
- **Controls:** the ten control networks.
- **Secondary tables:** headless against intact, line specificity, systematic sources only, exposed types included, labels v1.1, the single-neuron screens, authors against BrainIR, B1r against B2r, the full-cord leg pairs if B3 is locked, the stop calls if B4 v2 is locked, and frequency.
- **Scorecard:** one row per labeled type with its score, band, label, preparation and sources. It is allowed now.
- **Figures:** the scorecard and the ROC curve.
- **Three biggest caveats,** in plain language.
- **Exploratory:** anything you looked at that was not pre-registered, clearly marked.

Commit, tag `ledger-scorecard-v1`, push, timestamp.

---

## 9. If time runs short

- **Never drop:** the v2 rulebook, labels v2, the gate.
- **Drop in this order:** B6, B4 v2, B3, then B1r and B2r. The primary analysis needs none of them.
- Labels come before prediction repairs if you must choose.

---

## 10. When things go wrong

| Problem | Default action |
|---|---|
| GitHub Actions cannot be used, or stalls | Run locally as in Stage 0. Do not wait. |
| A guard or quota pauses you | Re-check every 10 minutes and resume. |
| The canary cannot block outside reads | Use the guard and the audit, and state the weakness. |
| A source will not download | Mark it unreachable and let a reader try a live fetch. |
| The atlas source data cannot be read | Use the paper's figures as images. If that also fails, say so plainly. The atlas matters most. |
| A session ends early | Reassign its unfinished sources to a new session. |
| An arm fails its gate | Do not lock it. Move on. |
| The gate fails on power only | Stop without unblinding. Report label-only counts. |
| You find a bug after a lock | Make a new version with a changelog. Never edit the locked one. |
| Your context was compacted | Re-read `STATE.md`, `LOG.md` and `RUN2_PROMPT.md`. |

---

## 11. Finish

### Done means

- `ledger-prereg-v2` and `ledger-labels-v2` exist with hashes and timestamp proofs.
- `ledger-predictions-v2` exists, or each failed arm is explained.
- The gate was evaluated and its result is written down.
- Either `RESULTS_1.md` and `ledger-scorecard-v1` exist, or nothing was unblinded and the reason is stated.
- The baseline checks still pass, and all locks verify.

### Handoff: `research/ledger/HANDOFF_2.md`

At most 1,800 words, plain language, printed as your final message too.

1. What exists now: tags, lock hashes, whether pushes worked.
2. Every departure from this prompt, with the reason.
3. Stage 2: which arms were locked, gate results, and the note on leg coupling.
4. Stage 3, labels only:
   - sessions run and excluded;
   - sources registered, downloaded and unreachable;
   - records collected and final;
   - types with a clear front-leg label, by class, preparation and specificity;
   - the primary-set size by class;
   - agreement, recall, the verification error rate, and v1 against v2.
5. The gate: each condition and whether it held.
6. If unblinded: the first line of `RESULTS_1.md`, the headline numbers, the baseline comparison, and the scorecard.
7. If not unblinded: a plain statement that nothing was joined, and what is needed to pass.
8. Compute platform used, the trust-gate result, runner-hours spent, and wall-clock time.
9. What worries you.
10. What you would do next.
