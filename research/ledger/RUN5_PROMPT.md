# BrainIR Prediction Ledger: Run 5

**Scope of this run:** the last compute run. Pin down which predictions replicate, test whether noise inside one fly can tell you which will, audit the labels that look wrong, lock a sharper list of experiments, and write the paper, the brief and the emails. Nothing is sent or posted by you.

Everything so far is on branch `ledger/v1` under `research/ledger/`. Read `HANDOFF_4.md`, `results/RESULTS_3.md`, `BRIEF.md`, LOG entry L158 with the question-round answer that followed it, and the four rulebooks before you design anything.

This is an autonomous run: expect 8 to 16 hours. I will not be watching. Do not stop to ask me things. Where this prompt is silent, or wrong about the repo, make the call that best serves the goal, log the decision and the reason, and keep going. Any pause must schedule its own re-check within 10 minutes and resume by itself.

Think hard before every irreversible step. Before each lock, write a short pre-mortem in the log and check the most likely way it could be wrong.

---

## 1. Where things stand

**What the last question round showed**

Whole-type screens, drivers scoring at least 0.5:

- MANC, our run (B1r): 15 types.
- MANC, the authors' own list (A1): 11 types.
- MaleCNS, our run (B2r): 30 types.
- **In both flies: 3 types.** DNg100, DNb08 and DNit013.

Of the authors' 11 hits, 3 are still hits in the second fly. Two of those three are the two drivers the original paper reported and confirmed in flies. In the authors' single-neuron screen, DNg100 and DNb08 are also the only types with copies on both sides where every copy scores at least 0.5.

**How to read that**

- It suggests the screen carries a small real signal, and that replication across animals is what finds it.
- It is fair to the original paper: its two headline neurons hold up. The rest of the hit list does not replicate.
- It is post hoc. I saw this pattern in a table after both exams were unblinded. Two confirmed neurons is a tiny sample. DNg100 is the neuron the model was built around, and the authors chose DNb08 themselves.

**Two problems to fix**

1. **A label that looks wrong.** Exam 1 records DNg100 as "no" for front-leg rhythm in headless flies, from 5 records. The published work reports the opposite. DNg100 is an exposed type, so the exam 1 headline does not use it, but it is the first thing a reader will check.
2. **The current list of experiments is weak.** None of the 15 "decisive" types is a predicted driver, the two sources differ by only 0.05 to 0.28, and "stable" was defined loosely.

Also still open: the per-type tables behind the last question round sit under no lock.

---

## 2. What this run must achieve

1. Lock the per-type tables.
2. Freeze `PREREG_v5.md`.
3. **Part R:** describe replication properly, marked post hoc where it is.
4. **Part S:** a clean, pre-registered test of whether stability under synapse-count noise inside one fly picks out the hits that replicate in the other.
5. **Part L:** audit the labels, starting with DNg100.
6. **Part F:** lock a second forward ledger built on replication status, with a short list of orderable lines and a decision rule.
7. **Part P:** write the paper draft, with three independent reviews.
8. **Part B:** write the brief and the outreach drafts.

---

## 3. Hard limits

1. **Declare first.** Every analysis and criterion is in `PREREG_v5.md` before the data or simulations it concerns.
2. **Mark what is post hoc.** The replication pattern was seen before this rulebook. Every table, figure and sentence that rests on it says "post hoc". Part S is the only new confirmatory test in this run.
3. **Exams are closed.** No primary result is re-scored. An audited-labels re-score of exam 1 may be reported once, marked exploratory.
4. **You never author labels.** The audit is done by fresh reader sessions. Both exams are unblinded, so these readers may read every source, including the papers that report simulations.
5. **Frozen things stay frozen.** Every existing lock, the BrainIR locks, the Phase 2 to 4 files and `main` are untouched. Corrections live in new files beside the old ones.
6. **Reviews are write-once.** Later thoughts go in an addendum. Tell every reviewer the length limit of what it reviews.
7. **Compute.** GitHub Actions under the trust gate, at most 20 jobs queued, and at most **100 runner-hours**. Time a few jobs first and size chunks to finish in under an hour. No Modal unless I say so in chat. The Mac runs no prediction.
8. **Nothing leaves this machine except pushes to my repo.** Do not send email. Do not post, submit or upload anything anywhere. Do not contact anyone. I do that myself.
9. **Be fair to the original authors.** Describe their work accurately and generously. This is about how reliable a method is, not about anyone's competence. Say plainly what of theirs holds up.

---

## 4. Stage 0: housekeeping and the per-type lock

- Start `caffeinate`. Save this prompt as `research/ledger/RUN5_PROMPT.md`. Confirm the tree is clean and all locks verify. Re-run the baseline checks and the trust gate.
- **Lock the per-type tables.** One tidy table per screen: the authors' single-neuron screen by copy, the four half-fly screens, B1r, B2r and A1. Include side, member counts per side, and the confidence of each cross-fly type match. Show that each table reproduces the locked aggregate it came from, then write `LOCK_pertype_v1.json` and tag `ledger-pertype-v1`.

---

## 5. Stage 1: `PREREG_v5.md`

### Part R: replication (descriptive, post hoc where marked)

**Definitions for whole-type screens.** These thresholds were chosen after seeing the table. Say so.

- **Driver:** mean score of at least 0.5.
- **Replicated:** a driver in both B1r and B2r.
- **Near-replicated:** a driver in one, and between 0.3 and 0.5 in the other.
- **Single-fly hit:** a driver in one, and below 0.3 in the other.
- **Stable non-driver:** below 0.05 in both, and in all four half-flies.

**Report**

- Counts and lists for each category.
- Overlap of the two flies' hit lists, next to its ceiling: the overlap of each fly's own hit list between two halves of the seeds.
- The same using the authors' A1 list for MANC.
- Everything again restricted to types whose cross-fly match is high-confidence. A hit that fails to replicate because two names were wrongly matched is not a finding.
- Copy concordance in the authors' single-neuron screen.
- Where the two experimentally confirmed drivers fall, with the selection caveats from section 1 stated beside them.

### Part S: does noise inside one fly predict replication? (pre-registered, confirmatory)

The idea: if a hit flickers when synapse counts are re-rolled, it should not be expected to replicate in another animal. If that holds, anyone with a single connectome can tell which of their hits to trust.

- **Copies.** 16 Poisson copies of the MANC raw counts, floor applied after resampling, as in run 4.
- **Types.** Every type that is a driver in B1r or in A1, plus a fixed random sample of 40 types that are drivers in neither.
- **Procedure.** The whole-type B1r screen, 8 seeds per copy.
- **Stability score.** The fraction of copies in which the type's mean score is at least 0.5. The mean score across copies is secondary.
- **Test S1, primary.** Among the B1r drivers, are the replicated ones more stable than the rest? An exact one-sided rank test, with the replicated set fixed from the locked B2r table. Repeat for the A1 list.
- **Test S2.** How often does noise turn one of the 40 non-drivers into a driver?
- **Words.** "Stability predicts replication" if the exact p is below 0.05. Otherwise "not shown".
- **Power, stated in advance.** There are only three replicated types. A null result here is uninformative, and the rulebook must say so before the test runs.

### Part T: single-neuron screen in the second fly (optional)

Run the single-neuron procedure on MaleCNS for every copy of every type that is a driver in any whole-type screen. Report copy concordance in the second fly, especially for DNg100 and DNb08.

### Part L: label audit

- **Who.** Fresh reader sessions with the sources in the room, including the papers that report simulations.
- **DNg100 first.** List the five records behind its "no", with quotes. Say which sources describe DNg100 activation in headless flies and what they report. Explain the label: a mapping error, the consensus rule, sources set aside by the blind rule, or a correct reading of a narrower experiment.
- **Every exposed type, and every labelled type in the Part R table.** Re-read and record front-leg rhythm in headless flies and in intact flies separately.
- **A random sample of 15 non-exposed labelled types,** to estimate the error rate when no source is set aside.
- **Outputs.** `LABEL_AUDIT_v1.md` and an audited table in a new directory. Labels v2 is not touched.
- **Consequence, fixed now.** If the sampled error rate on the front-leg field is above 10%, or the audit finds a systematic fault, exam 1 is described everywhere as compromised, with the audited exploratory re-score beside it. Otherwise exam 1 stands as reported, with DNg100's entry corrected in an erratum.

### Part F: forward ledger v2

- **Types.** Every type in the Part R categories that has a driver line in the kit and has not already been tested in headless flies according to the audit.
- **Three readings, each giving yes or no** for rhythmic front-leg stepping in a decapitated fly with the type switched on both sides:
  - **Replication reading:** replicated and near-replicated types yes, single-fly hits no, stable non-drivers no.
  - **Single-connectome reading:** every A1 driver yes, everything else no.
  - **Counting reading:** top third of two-step signed counting yes, the rest no.
- **The short list.** At most 12 types:
  - every replicated and near-replicated type with a line;
  - single-fly hits with lines, MANC ones first, because the published model is MANC;
  - three stable non-drivers with the highest counting scores, as controls.
  - Within a group, prefer types with more available lines and cleaner lines.
- **For each type:** the three readings, line IDs, which collection holds each line, whether it is listed as available today, and any note that the line also labels another descending-neuron type.
- **Decision rule for the lab result, fixed now.** State exactly what outcome supports the replication reading, what supports the single-connectome reading, and what is inconclusive. Give a small power table for the number of types in each group.
- **Honesty line.** Made after both exams were unblinded and after the replication pattern was seen. Clean with respect to the experiments it predicts.
- Forward ledger v1 stays, marked superseded for the ask.

### Part P: the paper

`paper/PREPRINT_v0.md`, 3,500 to 4,500 words, with figures made by script from locked files.

- **Three title options** and an abstract of at most 200 words.
- **Introduction.** The question, and what the original paper showed, stated fairly.
- **Results, in this order.**
  1. Left and right copies disagree in the authors' own published screen.
  2. Two flies' hit lists barely overlap, though their wiring summaries agree.
  3. The hits that replicate include both experimentally confirmed drivers (post hoc).
  4. Synapse-count noise is enough to produce the gap; where it comes from; no simple fix.
  5. Whether stability under count noise predicts replication (Part S, whatever it shows).
  6. Two blind exams: the simulation does no better than two-step synapse counting. Exam 1 with its caveats and the audit.
  7. The forward predictions.
- **Discussion.** What this means for anyone simulating a single connectome. What it does not show.
- **Limitations.** Long and explicit. Include at least: one model and one behaviour; two animals, both male; our rebuild for the second fly; cross-fly type matching; labels inferred from papers, largely by one model family; exam 2's two labs disagreeing; everything in Part R being post hoc; the audit's findings.
- **Methods.** Pre-registration, locks, timestamps, blind labelling, the gates.
- **Disclosure.** State plainly that the analyses were designed with, and run by, AI agents under my direction, and name the model.
- **Claims table.** `paper/CLAIMS.md`: one row per claim, with the locked file and field, the tag, and its status: pre-registered and blind, pre-registered and label-free, or post hoc.

**Rules for the paper**

- Every number comes from a locked file.
- No claim goes beyond the pre-registered verdicts and the Part S criterion.
- Post hoc results are named as such in the abstract too.

**Three reviews, each by a fresh agent, each write-once**

1. **Overclaim review:** mark every sentence that says more than the evidence.
2. **Hostile referee:** read it as the original paper's authors would, and write the strongest rebuttal. Test any objection that is cheap to test.
3. **Numbers review:** check every number against its locked file.

Answer each in an addendum and revise. If a provider safeguard stops a reviewer, start another, on another model if needed, and log it.

### Part B: brief and outreach drafts

- **`BRIEF_v2.md`,** two pages. Lead with the replication result and the short list. Keep the rules from the first brief.
- **`outreach/EMAIL_authors.md`,** at most 180 words, to the original paper's corresponding authors. Courteous. Says what was found, says their two confirmed drivers hold up, links the repo, and asks them to point out errors before anything is posted.
- **`outreach/EMAIL_lab.md`,** at most 150 words, to a lab that already runs headless-fly optogenetics. The ask is the short list.
- **`outreach/ONE_PARAGRAPH.md`:** the whole project in 120 words for a non-specialist.
- These are drafts for me. Leave the recipient lines blank.

### Freeze

Have a fresh reviewer audit the rulebook. Commit, tag `ledger-prereg-v5`, push, timestamp.

---

## 6. Stages 2 to 6: run it

- **Order:** Part R from the locked tables; launch Part S; the label audit while Part S runs; Part T if budget allows; Part F; then write `results/RESULTS_4.md`; then the paper, the reviews, the brief and the drafts.
- Every campaign passes determinism on a re-run sample.
- Lock Parts R, S, T and L as `LOCK_replication_v1.json`, tag `ledger-replication-v1`. Lock Part F as `LOCK_forward_v2.json`, tag `ledger-forward-v2`. Push and timestamp both.

**`results/RESULTS_4.md`**

- **First line:** whether stability under count noise predicts replication, in plain words.
- The replication table, post hoc parts marked.
- Part S in full, including the power statement.
- The label audit in one paragraph, and what it does to exam 1.
- Three biggest caveats.

---

## 7. If time runs short

- **Never drop:** the per-type lock, Part R, the DNg100 and exposed-type audit, Part F, the paper, the brief.
- **Drop in this order:** Part T, the random-sample audit, the hostile-referee tests, copies beyond 8 in Part S, the outreach drafts.

---

## 8. When things go wrong

| Problem | Default action |
|---|---|
| GitHub queues stall or jobs time out | Smaller chunks, fewer at a time. Do not move predictions to the Mac. |
| Cross-fly matches are low-confidence for many types | Report both versions and lead with the high-confidence one. |
| The audit shows DNg100's label is wrong | Write the erratum, apply the consequence rule from Part L, and carry it into the paper. |
| The audit shows exam 1 is compromised | Say so in the first paragraph of the exam 1 section and in the limitations. Do not bury it. |
| Part S is null | Report "not shown" with the power statement. Do not reinterpret it. |
| Fewer than 6 types qualify for the short list | Lock what there is and say why it is short. |
| A reviewer is blocked by a safeguard | Start another and log it. |
| You find a bug after a lock | Make a new version with a changelog. Never edit the locked one. |
| Your context was compacted | Re-read `STATE.md`, `LOG.md` and `RUN5_PROMPT.md`. |

---

## 9. Finish

### Done means

- `ledger-pertype-v1`, `ledger-prereg-v5`, `ledger-replication-v1` and `ledger-forward-v2` exist with hashes and timestamp proofs, or each missing one is explained.
- `RESULTS_4.md`, `LABEL_AUDIT_v1.md`, `paper/PREPRINT_v0.md` with its figures, `paper/CLAIMS.md`, the three reviews with addenda, `BRIEF_v2.md` and the outreach drafts exist.
- Nothing was sent or posted.
- The baseline checks still pass and all locks verify.

### Handoff: `research/ledger/HANDOFF_5.md`

At most 2,500 words, plain language, printed as your final message too.

1. What exists now: tags, lock hashes, whether pushes worked.
2. Every departure from this prompt, with the reason.
3. Part R: the counts, the lists, the overlap with its ceiling, and the high-confidence version.
4. Part S: the stability of each driver, the exact p, the false-hit rate, and the verdict.
5. Part T, if run.
6. Part L: the explanation of DNg100's label, the discrepancies found, the sampled error rate, and what it does to exam 1.
7. Part F: the short list in full, with the three readings, lines and availability, and the decision rule.
8. The paper: the chosen title and the abstract in full.
9. The three reviews: each one's strongest point and your answer.
10. The brief's first paragraph, and both email drafts in full.
11. Compute and wall-clock time.
12. What worries you.
13. What you would do next.
