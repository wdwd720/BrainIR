# BrainIR Prediction Ledger: Run 6

**Scope of this run:** test the paper's main results in a third animal that this project has never looked at, under rules frozen first. Then rewrite the paper so a fly neuroscientist can read it, and prepare me to defend it. Nothing is sent or posted by you.

Everything so far is on branch `ledger/v1` under `research/ledger/`. Before you design anything, read `HANDOFF_5.md`, `paper/PREPRINT_v0.md`, `reviews_v5/PAPER_REFEREE_REVIEW.md` with its addendum, `PREREG_v2.md` (P1), `PREREG_v4.md` (Parts G, A, B, C) and `PREREG_v5.md`.

This is an autonomous run: expect 12 to 20 hours. I will not be watching. Do not stop to ask me things. Where this prompt is silent, or wrong about the repo, make the call that best serves the goal, log the decision and the reason, and keep going. Any pause must schedule its own re-check within 10 minutes and resume by itself.

Think hard before every irreversible step. Before each lock, write a short pre-mortem in the log and check the most likely way it could be wrong.

---

## 1. Where things stand

**What run 5's reviews changed**

1. **Half of the headline pattern was built in.** The current-setting procedure has one free setting, K, and rulebook v2 chose it so that DNg100 drives rhythm in both connectomes. So "DNg100 replicates" says nothing. The pattern rests on DNb08, and the original authors had already reported DNb08 across datasets.
2. **The second animal's screen is ours and is not validated beyond DNg100.** The authors published no screen of MaleCNS. Our single-copy screen does not reproduce their reported result for a single DNb08 neuron in that dataset.
3. **The 0.5 cut matters.** At the authors' cut the two animals' hit lists overlap at chance. At 0.3 to 0.4 about half of the hits recur, well above chance. The referee computed this, and it sits under no lock.
4. **Exam 1 cannot rank anything.** Its "yes" labels come almost entirely from one atlas of intact walking flies, and its "no" labels from takeoff and flight experiments.
5. **The stability test was null** (p = 0.11) and uninformative with three replicated types. Two graded sensitivity analyses were nominally positive.

**What still stands**

- In the authors' own published screen, left and right copies of a neuron agree at 0.63 of the screen's agreement with itself.
- In MANC, Poisson-scale noise in synapse counts reproduces that gap.
- Wiring summaries agree across sides and animals (0.71 to 0.98) where simulated hit calls do not.
- Our MANC screen shares 10 of the authors' 11 hits, so the gap between animals is not a reimplementation artefact.

**What the draft lacks**

- A reference list. It has none.
- Plain language. It is written in this project's code names.
- The related work and the authors' own framing of their screen.

**The opening this run uses**

The authors' repository holds a third connectome's front-leg network that this ledger has never screened: BANC, a female. See `research/literature/pugliese_walking_cpg_detailed_notes.md` section 2.4 and `pugliese_model_spec_from_code.md`:

- matrix `data/banc t1 premotor/W_20260217.npz` (4,963 neurons, no synapse floor) and table `wTable_20260217_fullData_consistentColumns.csv`, at the commit pinned in `ledger/src/brainir_ledger/authors.py`;
- the table carries `manc_121_cell_type` and `manc_121_match_id`, so its descending neurons can be matched to MANC types;
- the experiment configs for the authors' BANC and MaleCNS runs exist only in the Zenodo record, which `ledger/scripts/zenodo_remote_zip.py` can read without downloading whole archives.

FANC cannot support a screen: the released network is an 803-neuron path from DNg100 to the motor neurons. Check the Zenodo listing once for a FANC network that includes the descending neurons. If there is none, say so and move on.

Because nothing in BANC has been seen, every test below is a real prediction. That is what the paper is missing.

---

## 2. What this run must achieve

1. Build the BANC front-leg model and pass a build gate that uses only the authors' published DNg100 results.
2. Lock the referee's unlocked numbers as post hoc results.
3. Freeze `PREREG_v6.md` before any BANC screen runs.
4. Run the BANC screens and the eight confirmatory tests.
5. Validate our MaleCNS screen against the authors' reported results.
6. Rewrite the paper as `paper/PREPRINT_v1`, with references, a supplement, and files ready to upload.
7. Write a study guide and a hand-check kit for me.
8. Update the brief and the outreach drafts.

---

## 3. Hard limits

1. **Declare first.** Every analysis, criterion and sentence-level verdict is in `PREREG_v6.md` before the simulations it concerns.
2. **BANC stays blind until the freeze.** Before the freeze you may stimulate only DNg100 in BANC, and silence only the neurons of the authors' rhythm circuit. Reading the table's annotations to build groups and type matches is allowed. No other descending neuron is stimulated, and no wiring summary of BANC descending neurons is computed, until `ledger-prereg-v6` is tagged and pushed.
3. **K is not re-chosen.** The tuned procedure runs on BANC exactly as locked for the first two animals. Nothing is calibrated on BANC.
4. **Mark what is post hoc.** Everything about the first two animals' hit lists stays post hoc. Only tests declared in `PREREG_v6.md` are called pre-registered.
5. **Exams are closed.** No primary result is re-scored.
6. **Frozen things stay frozen.** Every existing lock (all 25 checks pass today), the Phase 2 to 4 files and `main` are untouched. Forward ledger v2 stays as locked. Corrections live in new files.
7. **Reviews are write-once.** Later thoughts go in an addendum. Tell every reviewer the length limit of what it reviews.
8. **Compute.** GitHub Actions under the trust gate, at most 20 jobs queued, at most **150 runner-hours**. Time a few jobs first and size chunks to finish in under an hour. No Modal unless I say so in chat. The Mac runs no prediction.
9. **Agent sessions.** My account is near its weekly limit, which resets on 25 November at 17:00 Pacific. Start at most 8 fresh agent sessions in this whole run, and no label-reading sessions. Keep `STATE.md` current after every stage so that a new session can resume from it alone.
10. **Nothing leaves this machine except pushes to my repo.** Do not send email. Do not post, submit or upload anything anywhere. Do not contact anyone. I do that myself.
11. **Be fair to the original authors.** Describe their work accurately and generously. Quote their own limits on the screen. Say plainly what of theirs holds up.

---

## 4. Stage 0: housekeeping

- Start `caffeinate`. Save this prompt as `research/ledger/RUN6_PROMPT.md`. Confirm the tree is clean and all 25 locks verify. Re-run the baseline checks and the trust gate.

---

## 5. Stage 1: build the third animal's model

**Sources**

- The authors' BANC matrix and table, pinned by SHA-256.
- From Zenodo, read the run configs for the authors' BANC and MaleCNS DNg100 runs and for any DNb08 run in MaleCNS: stimulated neurons, currents, removed neurons, seeds and simulation settings. Read small saved outputs too if they exist. Do not download whole archives.

**Build it the way the authors did**

- Use the released matrix as it is: all descending neurons, no synapse floor. Do not re-derive it.
- Sign from the verified transmitter, falling back to the predicted one. Size scaling from `surf_area_um2`.
- Excitatory descending neurons by the authors' rule for BANC-style tables.
- Read-out: the front-leg motor neurons, with sides.
- Log every choice the configs do not settle.

**Type matching, fixed before any screen**

- Map each BANC descending neuron to a MANC type through `manc_121_match_id`, falling back to `manc_121_cell_type`.
- Write the confidence rule now, in the same spirit as run 5's: high confidence when every member is matched by ID, no ID match conflicts with the type name, and naming is one-to-one.
- The three-animal set is the types with a high-confidence match in both MaleCNS and BANC. Report its size. If it has fewer than 100 types, say so and carry on with what there is.

**Build gate, using only the authors' published DNg100 results**

1. DNg100 at the authors' own current drives front-leg rhythm, and matches their saved outputs where those can be read.
2. Silencing each excitatory neuron of their rhythm circuit abolishes it, as they report.

Set the tolerances before running. If the gate fails after honest attempts, the BANC part is not run. Say so plainly, then do sections 6 (Parts H and V only), 8, 9 and 10 without it.

---

## 6. Stage 2: `PREREG_v6.md`

### Part Q: disclosure

List what was seen before this freeze: everything from runs 1 to 5, the referee's unlocked tables, and the BANC gate.

### Part H: post hoc numbers for the first two animals

Recompute with ledger code, from locked tables, and lock as `LOCK_posthoc_v6.json` (tag `ledger-posthoc-v6`):

- hit-list overlap between MANC and MaleCNS at cuts 0.3, 0.4, 0.5 and 0.6, with chance expectation and the within-animal reference;
- the graded version: how well one animal's score separates the other's drivers;
- the same under the original procedure (K = 0) and under the sweep procedure (rulebook v4, fix 1), so that a reader can see what does not depend on our calibration. If no whole-type sweep of MaleCNS is stored, run one now, 8 seeds, so that all three animals end up with the same companion screen. It concerns animals already seen, so it is post hoc either way;
- every count with and without DNg100.

All of it is post hoc and says so.

### Procedures for BANC

- **Tuned (primary):** the whole-type procedure of the first two animals (rulebook v2, P1), K unchanged, 16 seeds.
- **Sweep (companion):** rulebook v4's fix 1, the best in-bounds score over the fixed 19-current grid, no current-setting step, 8 seeds.
- **One-sided screens:** rulebook v4's Part A design, left and right, 8 seeds.
- **Count noise:** rulebook v4's B4.2 design, two Poisson copies of BANC's raw counts.

**Validity rule, fixed now.** A screen that fails its positive control would show "nothing replicates" for the wrong reason.

- The tuned BANC screen is valid if DNg100 scores at least 0.5 in at least 12 of 16 seeds. This is the same bar as before, and K was not chosen on BANC, so here it is a real test.
- If it is not valid, the sweep becomes primary, provided DNg100 passes the equivalent bar under the sweep: at least 6 of 8 seeds.
- If neither is valid, tests C3 to C8 are "not judged" for BANC and are reported descriptively.
- DNg100 is never counted as evidence of replication. Every count is given with and without it.

### The confirmatory tests

Write the exact statistic, the interval method and the words for each outcome. Reuse the definitions of rulebook v4 Part G (agreement across halves of the seeds, matched ceiling, "at the ceiling", "a real gap", "inconclusive"). Lead with high-confidence type matches and give all matched types beside them.

**C1. Left against right in a third animal.** BANC left against BANC right, as a fraction of the ceiling.

**C2. Count noise in a third animal.** Whether two Poisson copies of BANC disagree as much as its left and right sides do, by rulebook v4's criterion.

**C3. Agreement across animals.** MANC against BANC and MaleCNS against BANC, whole-type screens, as a fraction of the ceiling. Report the three pairs together, for the primary procedure and for the sweep.

**C4. Hit lists.** For our MANC list, the authors' own list and our MaleCNS list:

- the share that are drivers in BANC at the 0.5 cut, with its interval, the chance expectation and a hypergeometric p;
- words: "at chance at the authors' cut" if p is at least 0.05, otherwise "above chance";
- the curve at 0.3, 0.4, 0.5 and 0.6, and the graded version, as in Part H;
- the overlap as a fraction of the within-animal overlap.

**C5. Named neurons.**

- DNg100: predicted to be a driver in BANC under the unchanged tuned procedure. Report pass or fail.
- DNb08: the authors report rhythm for a single DNb08 neuron in three of their four datasets, and BANC is the fourth. We make no prediction. Report what the whole type and each single copy do.
- A table of every type that is a driver in at least one animal, with its score in all three.

**C6. Does pooling two animals predict the third?** On the three-animal set, for each animal in turn as the target: the agreement of the mean score of the other two with the target, against the mean agreement of each of the other two alone. Average the difference over the three targets, with a bootstrap interval over types. Words: "pooling helps" if the interval excludes zero on the positive side, otherwise "not shown". State the expected size of the gain from the Spearman-Brown formula before running.

**C7. How many connectomes?** From the mean agreement between animals as a fraction of the ceiling, the Spearman-Brown estimate of how many animals a pooled screen needs to reach 0.8, with an interval. Label it an extrapolation and state its assumption: animals are exchangeable noisy measurements of one screen, and differences in reconstruction count as differences between animals.

**C8. Does stability under count noise predict the third animal?** A second, independent try of run 5's idea.

- Predictor: each driver's mean score across the 16 Poisson copies of MANC, from run 5's locked file.
- Outcome: its BANC score under the primary procedure.
- Types: the 16 drivers of run 5's test that have a BANC match, without DNg100.
- Statistic: Spearman correlation, one-sided permutation test at 0.05.
- Words: "stability under count noise predicts the third animal" or "not shown".
- Secondary, without words: with DNg100; run 5's stability fraction as the predictor; whether stability adds anything beyond the type's score in the real MANC network.
- Disclose that this predictor was chosen because it was nominally positive in run 5, on another animal.

For every test, state its power or its smallest attainable p before running.

### Part V: is our MaleCNS screen the authors' model? (descriptive)

- **V1.** DNg100 in MaleCNS at the authors' configuration: does it reproduce their result?
- **V2.** Each of DNb08's four MaleCNS copies alone, at each of the 19 grid currents and at the authors' current if a config gives one, 16 seeds. If their config uses a different network from the front-leg one, log it, and run theirs too if the files exist. Fixed words: "reproduces the authors' reported result at current X" if any current gives a score of at least 0.5 in at least half the seeds, otherwise "does not reproduce it at any tested current".

Whatever V2 shows goes in the paper and in the email to the authors.

### Forward list

Forward ledger v2 does not change. Report the BANC scores of its 12 types beside it, without changing any reading.

### Freeze

One fresh reviewer audits the rulebook, and re-checks it after you revise. Commit, tag `ledger-prereg-v6`, push, timestamp. Only then run a BANC screen.

---

## 7. Stage 3: run it

- **Order:** Part H; Part V; the tuned BANC screen and its validity check; the sweep; the one-sided screens; the count-noise copies; then the tests.
- Every campaign passes determinism on a re-run sample.
- Lock Part H as `LOCK_posthoc_v6.json`, tag `ledger-posthoc-v6`. Lock the BANC results and Part V as `LOCK_thirdfly_v1.json`, tag `ledger-thirdfly-v1`. Push and timestamp both.

**`results/RESULTS_5.md`**

- **First line:** whether the gap between animals was confirmed in the third, in plain words.
- One table: each test, its pre-registered words, its numbers.
- The three-animal table of drivers.
- Part V.
- The three biggest caveats.

---

## 8. Stage 4: the paper, rewritten

`paper/PREPRINT_v1.md`, 3,500 to 5,000 words of main text, with a separate `paper/SUPPLEMENT_v1.md`.

**The reader.** A fly neuroscientist who has never seen this repository and reads it once, start to finish.

**Language rules**

- No project code names in the main text: no arm codes, no "Part S", no "rulebook v2", no "exposed", no "half-fly", no "tuner". Say what each thing is. Put a name map in the supplement.
- Define every term at first use. Short sentences. One idea per paragraph.
- A plain statement of each result first, then the number, then the caveat.

**Structure**

- **Title.** About how reproducible a screen's hit list is, not about distrusting connectomes. Give three options.
- **Author block.** Read name, affiliation and email from `paper/author.yaml`. Create that file with empty fields for me to fill.
- **Abstract.** At most 220 words. Says which results are pre-registered and which are post hoc.
- **Introduction.**
  - What the original paper showed, stated fairly.
  - The authors' own framing, briefly quoted and cited: the screen is a discovery tool, low scores are not evidence against a neuron, and they followed up the two types whose every copy scored high.
  - That they tested DNg100's circuit and DNb08 across datasets themselves. Replication of those two neurons is their result.
  - That their preprint calls the screen qualitatively similar for the left and right front legs, which is about which leg is read out. We compare left and right copies of the stimulated neuron. State the difference so nobody thinks we contradict them by mistake.
  - Related work, each checked at its source before it is cited: arXiv 2609.38665; arXiv 2610.29205; the 2026 Biomimetics review "Connectomes as Structural Priors for Embodied Control"; Shiu et al. 2024. Drop any you cannot verify.
  - What we test, and that it goes beyond the use the authors made of the screen.
- **Results, strongest first.**
  1. Left and right copies in the authors' own published screen.
  2. Count noise reproduces that gap, in MANC and, if run, in BANC.
  3. Across animals: the first two (post hoc), then the third (pre-registered). Show the curve over cuts.
  4. Which neurons recur, with the calibration caveat stated before the list, and the versions that do not depend on our calibration.
  5. Can one connectome tell you which hits to trust? Both stability tests, pooling, and how many connectomes.
  6. Against published experiments. Exam 2 in full: above chance, level with the best of eight wiring baselines, above the other seven and clearly above four of them. Exam 1 in one short paragraph: the locked verdict, then that we do not interpret it and why. Its detail goes in the supplement.
  7. Twelve predictions for experiments, briefly.
- **Discussion.** What this means for anyone simulating one connectome. What holds up in the original work. What we did not show.
- **Limitations.** Long and explicit. Include: one model and one behaviour; three animals that also differ in sex, reconstruction and annotation; the second and third animals' screens are ours, on the authors' networks; Part V's outcome; type matching; labels read by language models of one family; post hoc parts.
- **Methods.** Enough to repeat it.
- **Use of AI.** State only what happened: which parts AI agents designed, coded, ran and drafted, under whose direction, and which models, taken from the logs. Do not describe any check by me that has not happened. Leave one marked line for me to complete after my hand check.
- **Data and code.** Repository, branch, tags.
- **References.** Complete, numbered, each with a DOI or arXiv ID, each checked against its source for title, authors, year and venue.
- **Figures.** Up to six, drawn by script from locked files, with plain axis labels and full legends.

**Rules**

- Every number comes from a locked file. `paper/CLAIMS_v1.md` has one row per claim: file, field, tag, and status.
- No claim goes beyond the pre-registered words.
- Every statement about the original paper is checked against its text before it goes in, including the left and right front legs sentence above. Quotes are short.
- Post hoc results are named as such, in the abstract too.

**Files to upload**

- `paper/build.sh` produces `PREPRINT_v1.pdf`, `PREPRINT_v1.docx` and `SUPPLEMENT_v1.pdf` from the markdown and `author.yaml`.
- The build refuses to make final files while `author.yaml` has an empty field or a marked line is unfilled. A `--draft` flag builds anyway, with DRAFT printed on every page. Build the draft version in this run.
- Use tools already on the machine first. You may install pandoc with Homebrew. Do not install a full LaTeX distribution. If no PDF engine is available, print the HTML to PDF with headless Chrome.
- Open the PDF and check every page: figures placed, tables not cut, no raw markdown, references resolved.

**Four reviews, each by a fresh agent, each write-once**

1. **Hostile referee, second round.** Given the first review and its addendum. Checks whether each accepted objection is truly reflected in the new text, then attacks the BANC part. Tests any objection that is cheap to test.
2. **Numbers and references.** Every number against its locked file. Every reference against its source.
3. **Naive reader.** Told only that it is a fly neuroscientist. Lists every term, sentence and figure it could not follow.
4. **Overclaim.** Marks every sentence that says more than the evidence.

Answer each in an addendum and revise. If a provider safeguard stops a reviewer, start another and log it.

---

## 9. Stage 5: prepare me

I am the only human author and I have to be able to defend every claim.

**`paper/STUDY_GUIDE.md`**, at most 3,000 words, written for a strong programmer with no biology training.

- A glossary of every term in the paper.
- For each results section: what it says in two sentences; the two or three numbers to remember; how it was measured; its weakest point.
- The ten hardest questions the original authors could ask, each with an honest answer and the file that backs it.
- What I must never claim, and why.

**`paper/HAND_CHECK.md`**

- Twenty items drawn by a seeded random rule: ten label cells from exam 2, nine labels from exam 1, and DNg100.
- For each: the claim, a short quote of at most 25 words, the source with its DOI, where in the source to look, and boxes for agree, disagree and unsure.
- The exact sentence to add to the Methods once I have done it, with blanks for the counts.

---

## 10. Stage 6: brief and outreach

- **`BRIEF_v3.md`,** two pages. Lead with what the third animal showed.
- **`outreach/EMAIL_authors_v2.md`,** at most 200 words. Says what holds up in their work. Says what we found, with the calibration caveat. Asks two specific questions: the configuration behind their single-DNb08 result in MaleCNS, and whether they have screened any other dataset. Asks them to point out errors before anything is posted.
- **`outreach/EMAIL_lab_v2.md`** and **`outreach/ONE_PARAGRAPH_v2.md`,** updated.
- Leave recipient lines blank.

---

## 11. If time runs short

- **Never drop:** the build gate, Part H, the freeze, the tuned BANC screen with its validity check, C3 to C8, Part V, the paper with its references and upload files, the study guide.
- **Drop in this order:** a FANC attempt, C2's noise copies, the sweep on BANC, C1's one-sided screens, the hand-check kit, the brief.

---

## 12. When things go wrong

| Problem | Default action |
|---|---|
| The BANC build gate fails | Do not run BANC screens. Say so in the first line of the results and the handoff. Do the rest. |
| DNg100 fails the validity bar in BANC | Follow the validity rule. Do not change K. |
| Too few types match across three animals | Report the two-animal comparisons with BANC and say the three-way set is small. |
| A test comes out against the earlier pattern | Report it with its pre-registered words. Rewrite the paper around what is true. |
| Zenodo configs cannot be read | Use the values printed in the paper and the notes. Log which values are unconfirmed. |
| GitHub queues stall or jobs time out | Smaller chunks, fewer at a time. Do not move predictions to the Mac. |
| A reference cannot be verified | Leave it out. |
| No PDF can be built | Deliver the .docx and say what failed. |
| A reviewer is blocked by a safeguard | Start another and log it. |
| You find a bug after a lock | Make a new version with a changelog. Never edit the locked one. |
| Your context was compacted, or a new session starts | Re-read `STATE.md`, `LOG.md` and `RUN6_PROMPT.md`, then continue. |

---

## 13. Finish

### Done means

- `ledger-posthoc-v6`, `ledger-prereg-v6` and `ledger-thirdfly-v1` exist with hashes and timestamp proofs, or each missing one is explained.
- `RESULTS_5.md`, `paper/PREPRINT_v1.md` with its PDF and .docx, `SUPPLEMENT_v1`, `CLAIMS_v1.md`, the four reviews with addenda, `STUDY_GUIDE.md`, `HAND_CHECK.md`, `BRIEF_v3.md` and the outreach drafts exist.
- Nothing was sent or posted.
- The baseline checks still pass and all locks verify.

### Handoff: `research/ledger/HANDOFF_6.md`

At most 2,500 words, plain language, printed as your final message too.

1. What exists now: tags, lock hashes, whether pushes worked.
2. Every departure from this prompt, with the reason.
3. The BANC build: sources, the gate, the type matching and the size of the three-animal set.
4. One table of C1 to C8: the pre-registered words and the numbers.
5. The three-animal table of drivers, and what DNg100 and DNb08 did.
6. Part V: whether our MaleCNS screen reproduces the authors' reported results.
7. Part H in three lines.
8. The paper: the chosen title, the abstract in full, the word count and the reference count.
9. The four reviews: each one's strongest point and your answer.
10. A table of run 5's referee objections and where the new paper answers each.
11. What I must do by hand, as a numbered list.
12. The email to the authors in full.
13. Compute, agent sessions used, and wall-clock time.
14. What worries you.
