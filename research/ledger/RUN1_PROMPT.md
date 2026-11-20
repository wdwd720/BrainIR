# BrainIR Prediction Ledger: Run 1

**Scope of this run:** set up this machine, write the pre-registration, lock the predictions, collect blind real-fly labels. It stops before any scoring.

You are working in my BrainIR repo, freshly cloned on this Mac. This is a long autonomous run: expect 12 to 24 hours. I will not be watching, so do not stop to ask me things. Where this prompt is silent, or wrong about the repo, make the call that best serves the goal, write the decision and the reason in the log, and keep going.

Take your time. Think hard before every irreversible step (the rulebook freeze and each lock), and review your own work before you lock it. Before each lock, write a short pre-mortem in the log: if this lock later turned out to be wrong, what is the most likely reason? Then go and check that reason. A careful lock matters more than finishing every optional arm.

I wrote this from the public GitHub snapshot at commit `242e472`. If the repo disagrees with anything below, trust the repo and log the discrepancy.

---

## 1. Why this exists

Connectome simulations are the main bet for turning wiring diagrams into predictions about behavior. For fly walking, the evidence is thin. Pugliese et al. (Nature 2026, doi 10.1038/s41586-026-11195-y) screened 933 excitatory descending neurons (DNs) in a rate model of the nerve cord, found DNg100 near the top, predicted that DNb08 drives leg rhythms, and confirmed that one prediction in decapitated flies. One confirmed prediction cannot separate skill from luck. Critics have shown that convincing behavior can come out of a model for the wrong reasons.

Nobody has measured the hit rate. This project measures it:

1. Lock the model's predictions for every DN type (which ones evoke rhythmic leg movement, which legs, what frequency), together with baselines and controls.
2. Collect, blind, every published experiment where a DN type was switched on in a real fly and the legs were observed.
3. Score the predictions against the experiments once, with a rule fixed in advance. (Not in this run.)
4. Publish forward predictions for types nobody has tested yet. (Not in this run.)

The end product is one calibrated number: the fraction of the model's predictions that hold in real animals, compared with chance and with simply counting synapses. A low number is as publishable as a high one. I want the honest result, not a flattering one.

**This run does steps 1 and 2 and then stops.** Unblinding is one-shot and cannot be redone, so I want to inspect the locked predictions and the labels before anything is joined.

---

## 2. Hard limits

There are only a few, and each has a reason.

1. **No unblinding.** Never join labels to predictions, never compute a hit rate, never look at a score next to an outcome, not even for one neuron and not informally. If predictions and outcomes meet before both are frozen and reviewed, the result is worthless. The scoring entry point must refuse to run unless `research/ledger/UNBLIND.json` exists. Do not create that file.
2. **Do not touch frozen work.** Nothing hashed by `benchmarks/dng100/BENCHMARK_LOCK.json` may change. At the snapshot its `code_files` cover `pyproject.toml`, `uv.lock`, `src/brainir/{sim,metrics,benchmark,compute}`, `graph.py`, `mapping.py` and one file under `schema/`. The same goes for the Phase 2 and 3 locks, and for everything Phase 4 in the repo: `phase4/`, `benchmarks/causal_state_v1/`, `research/phase4/`, `scripts/p4*`. Import the simulator and metrics read-only.
3. **Keep this work out of discovery code.** This project is allowed to read `benchmarks/dng100_walking_cpg/` and `research/literature/`, because it is not discovery code. Nothing from it may flow into `src/brainir/methods` or `src/brainir/discovery`. Work on a new branch and do not merge to `main`.
4. **Budget.** Modal spend for this run is capped at **$300**. Run a small pilot before each campaign and estimate its cost first.
5. **Nothing public except my own repo.** You may push the new branch and its tags to `origin`. Never push `main`: my PC has unpushed work on it. Do not create accounts, email anyone, or post anywhere else. No force pushes, no rewriting existing branches or tags.
6. **Locked means locked.** Once a prediction set is tagged, never edit it. A fix is a new version with a changelog entry that says whether labels existed at the time.

---

## 3. This machine

BrainIR was built on a Windows PC that I cannot reach right now. This Mac has only what GitHub has.

- `CLAUDE.md` describes the Windows machine. Its environment notes, its `C:\Dev\...` paths, the clean rooms and the agent launchers do not exist here. Do not try to recreate them and do not edit `CLAUDE.md`. Write what you learn about this machine in `research/ledger/SETUP.md`.
- There is no bulk data here. All of it is a public download that the repo's own commands rebuild. See Stage S.
- The hidden test sets for Phases 2 to 4, and any unpushed Phase 4 work, exist only on the PC. This project needs neither. Some lock checks and tests may be unable to run here for that reason. That is expected.
- Modal on this Mac is logged into a different account from the one the PC used, and it has no BrainIR storage yet. The repo's backend creates its storage volume on first use and runs short-lived apps, so no earlier setup should be needed.
- Other Claude Code sessions may be running on this Mac. Use Modal for heavy compute and keep local work light.
- The Mac must stay awake for the whole run. Start `caffeinate` at the beginning and keep it alive.

---

## 4. What I verified in the repo (re-check before relying on it)

**The saved screen**

- It is `benchmarks/dng100_walking_cpg/results/dn_screen_manc_v1.2.1_nt-paper_r16.json`.
- It covers 933 excitatory DNs, **one neuron at a time**, 16 replicates (seeds 0 to 15), `t_end` 1.0 s, on the MANC v1.2.1 front-leg network (4,604 neurons), reading out the 144 front-leg motor neurons.
- It ran on Modal and cost $18.55 and 47 CPU-hours.
- The script that made it is `benchmarks/dng100_walking_cpg/reproduce_dn_screen.py`. It builds the network through `paper_network()` in `reproduce_dynamics.py`.

**The simulator**

- `src/brainir/sim/screen.py::screen_candidate` accepts a single candidate index and auto-tunes the current by bisection: start 128, activity bounds 5 to 1500, at most 100 neurons above 100 Hz, up to 10 iterations. It scores the last tested amplitude that satisfied the bounds.
- `Stimulus` already accepts several indices sharing one current.
- Both files are locked.

**The paper's type-level screen**

- `dns_by_type` gives every excitatory member of a type the same current, for 321 type groups.
- The paper text says the lower activity bound was raised to 10 for that screen. The authors' code and notebook show 5. See `research/literature/pugliese_model_spec_from_code.md` §6.

**The networks**

- The MANC front-leg network has 1,318 DNs in 475 types: 933 excitatory neurons (321 types have at least one, with 1 to 30 each) and 385 inhibitory neurons (163 types have at least one). So 9 types are mixed. The paper's single-neuron screen skipped the inhibitory neurons.
- In the public benchmark bundle, `side` is null for MANC DNs. The processed tables have a `root_side` column; check that it is populated for DNs.
- MANC and MaleCNS each have 475 DN type names in their front-leg networks, and only 195 names are shared. MaleCNS carries a curated `manc_type` column, and `brainir mapping build` exists. The ingest code also has `synonyms`, `flywire_type` and `hemibrain_type` columns that can seed a name map.
- The authors' full nerve-cord network (23,532 neurons, floor 5, 1,372,404 connections) equals the `manc:v1.2.3` build.

**The paper's full-cord result, from the repo's notes**

- Two-sided DNg100 gave median per-leg scores of T1L 0.887, T1R 0.687, T2L 0.452, T2R 0.936, T3L 0.215, T3R 0.716.
- The median number of active motor neurons per leg was only 1 to 13.
- There was no phase coupling between legs.
- The paper's phase definition is the cross-correlation peak within one period, normalised to the period and wrapped to [−π, π], with a replicate-shuffled control. Its antagonist pair is the coxa promotor ("Tergopleural/Pleural promotor MN") against the coxa remotor ("Pleural remotor/abductor MN").

**The authors' files**

- Their repository is `smpuglie/Pugliese_2026`, pinned by commit in `reproduce_manc_connectivity.py` (`EXTERNAL`, `REPO`, `COMMIT`). `fetch_external()` downloads their front-leg, full-cord and MaleCNS matrices into `data/raw/external/` and checks each SHA-256.
- Their simulation outputs are on Zenodo (10.5281/zenodo.22260924, about 170 GB in 27 archives, never downloaded).
- The repo's notes say the per-neuron and type-level screen scores were recomputed from the authors' repository data.

**The Modal backend**

- `src/brainir/compute/backend.py` builds its container image from a slim Debian base, a list of dependencies given only as lower bounds, and the `brainir` package alone.
- A job function must be importable inside the container.
- The storage volume is created if missing.

**Other**

- Rewiring controls (`degree_preserving_rewire`, `class_shuffle`) live in `benchmarks/dng100_walking_cpg/robustness_experiments.py`.
- `phase3/` and `phase4/` each have their own `pyproject.toml` and `uv.lock`. That is the precedent for adding a package without touching the root project.
- `data/manifests/` holds committed manifests for all four processed builds.

Read `CLAUDE.md`, `research/LOG.md`, `PHASE1_REPORT.md` and the Pugliese notes before you design anything.

---

## 5. How to work

- **This prompt.** Save it as `research/ledger/RUN1_PROMPT.md` first, so it survives a context compaction.
- **Branch.** Create `ledger/v1` from the current `main` in this clone.
- **Layout.** Put code in a new top-level package (suggested: `ledger/`, package `brainir_ledger`, own `pyproject.toml`, depending on `brainir`). Put documents, the rulebook, logs, prediction tables and label tables in `research/ledger/`. Small result tables are committed, following the precedent of `benchmarks/dng100_walking_cpg/results/`. Bulk traces go under the data root, with hashes recorded in the lock. No absolute paths in committed files.
- **State.** Keep `research/ledger/STATE.md` current (done, in progress, next, open problems) so you can resume after a context compaction. Keep `research/ledger/LOG.md` as a numbered decision log: what you decided, why, what you rejected. Do not write into the main `research/LOG.md`.
- **Commits.** Commit small and often.
- **Run registry.** Register ledger runs in the ledger's own registry, not in `benchmarks/dng100/manifests/experiments/`.
- **Time.** Reserve at least a third of the run for Stage 2. The labels are half the project.
- **Verification.** Nothing gets locked on the strength of "it ran". Every arm needs a check that could have failed.
- **Delegation.** Use subagents freely for code review and independent re-implementation checks. For the blind labeling in Stage 2, follow the stricter rule given there.

---

## 6. Stage S: set up this machine

1. **Stay awake and get the tools.** Start `caffeinate`. Make sure `uv` is installed, then run `uv sync`.
2. **Baseline.** Run `uv run pytest -m "not real_data"`, `benchmarks/dng100/freeze.py --check` and every other lock check you can find. Record in `SETUP.md` which pass and which cannot run on this machine. At the end of the run the same set must still pass.
3. **Disk.** MANC raw data is about 5 GB and MaleCNS raw data is 18.7 GB. Processed tables, caches and traces come on top. If there is less than about 60 GB free, skip MaleCNS (arm B2) and say so.
4. **Data, MANC first.** Use the `brainir acquire` and `brainir ingest` commands in `CLAUDE.md` and `data/README.md`. Get MANC v1.0 and v1.2, then build the processed tables for v1.0, v1.2.1 and v1.2.3. That is all the core arms need. Start the MaleCNS download and ingest in the background. Only B2 and the real-data tests need it.
5. **Gate G0: the rebuild is right.**
   - The rebuilt tables agree with the committed manifests in `data/manifests/`. If file hashes differ across platforms, show that row counts and contents agree and document it.
   - `reproduce_manc_connectivity.py` shows every connection equal to the authors' matrices, for both the front-leg and the full-cord networks. Its MaleCNS part can wait for that download.
   - Do not run any arm on data that fails G0.
6. **Modal.** Confirm the login works. Check the account for a spending limit and remaining credit. Run a smoke test of about 20 screen jobs and measure the cost per job. The existing screen script registers its runs in the benchmark's registry, so if you use it for the smoke test, remove the smoke record afterwards as `CLAUDE.md` says. If Modal cannot be made to work, run the core arms locally, drop the optional arms, and log it.
7. **Backend for new code.** Your new job functions live outside the `brainir` package, so the stock image cannot import them. Subclass the backend inside the ledger package: add your package to the image and pin exact library versions, taken from `uv.lock`. Do not edit the locked file.
8. **One platform.** Produce every locked arm on the same backend, and record platform, Python and library versions in the lock. The saved screen came from Modal on Linux, so that is the natural choice.
9. **Pushing.** Check whether pushing works from this Mac (`git push --dry-run`, `gh auth status`). If it does not, keep everything local, rely on the timestamp proofs, and tell me in the handoff.

---

## 7. Stage 0: rulebook, scoring code, labeler kit

Everything in this stage is written and tagged **before** any new screen is run and before any literature is read for outcomes. DNg100 and DNb08 simulations that you need in order to define or validate a metric are allowed at any time.

**Amendments.** The rulebook may be amended only before the stage it affects has produced data. Every amendment is versioned and logged with its reason, and none may use information from the other side of the blind.

### Exposed list

Some DN types have already had both their model score and their real-fly outcome seen by me or recorded in this repo. Start the list with: DNg100, DNb08, DNg12, DNg97, MDN, DNa01, DNa02, DNp09, DNg13, DNp01, DNg16, DNg55, DNg75. Search the repo's notes and reports for any other DN type whose real-fly activation outcome is stated, and add it. These types are still predicted and labeled, but they are reported in a separate row and excluded from the headline number.

### The rulebook: `research/ledger/PREREG.md`

Write it so that a stranger could run the scoring without asking a question. It must fix at least the following. Where I give a default, you may change it for a stated reason, but only now.

- **Unit.** The DN cell type under MANC naming, with a synonym map to MaleCNS, FlyWire and literature names.
- **Primary prediction.** The type-level co-activation rhythm score on the MANC front-leg network: mean over usable replicates. If a complete per-type table for all 321 types can be rebuilt from the authors' released files by a documented script, the authors' own numbers are primary and the BrainIR run is the independent replication. Otherwise BrainIR's run is primary. Report both either way.
- **Never-usable types.** Score 0 in the primary analysis, with a reason code (too weak or saturating). Excluded in a sensitivity analysis.
- **Primary truth.** A per-type consensus label, "activation evokes rhythmic front-leg movement: yes or no", from the blind curation. Unclear, conflicting or not-assessed types are excluded.
- **Primary statistic.** AUROC over labeled, non-exposed, excitatory types. Defaults: ties get average ranks; a 95% percentile bootstrap interval from 10,000 resamples of types; a permutation p-value from 10,000 label shuffles; a fixed random seed.
- **Decision rules, declared now.**
  - "The model predicts" if the interval's lower bound is above 0.5.
  - "The simulation adds value beyond wiring" only if it beats the best pre-registered anatomical baseline on a paired bootstrap.
  - "Underpowered" if fewer than 20 labeled types or fewer than 5 in either class. In that case report descriptively and claim nothing.
- **Bands.** Predicted driver: score ≥ 0.5 (the paper's rule). Predicted non-driver: score < 0.05. Report precision for drivers and negative predictive value for non-drivers.
- **Secondary analyses, all descriptive.**
  - Headless and intact flies separately. The model has no brain, so headless is the fair test.
  - Clean and non-specific driver lines separately.
  - Systematic-screen sources only, to limit positive-result bias.
  - With the exposed types included.
  - Single-neuron screens summarised per type (maximum and mean).
  - Authors' numbers against BrainIR's.
  - The MaleCNS replication.
  - Per-leg-pair predictions from the full nerve cord against front, middle and hind labels.
  - Predicted against reported frequency.
  - Rewired controls (expected near 0.5).
  - The stop and modulation predictions.
- **Derived quantities.** Exact formulas for every derived quantity you will lock: per-leg rhythm, frequency, phase offsets, coordination indices, halt and speed-change calls. Definitions may be informed only by DNg100 and DNb08 simulations and by criteria that do not depend on which neuron is being tested. Suggested defaults are in Stage 1.
- **Type consensus rule.** How conflicting records for one type are combined. A suggested rule is in Stage 2 under Quality.

### Scoring code

Implement the full scoring pipeline now and test it on synthetic data with known answers: AUROC, intervals, permutation test, precision and negative predictive value, calibration, paired comparison against baselines, and the stratified tables. Add the `UNBLIND.json` guard. Add a test that fails if any label-side code reads a prediction file.

### Labeler kit

- Write the labeling protocol, the record schema with a validator, and the exact prompt text the labelers will receive. The conventions and fields are specified in Stage 2.
- Build the list of DN types the labelers will work from. It contains names and synonyms only, in **alphabetical order**, with no scores, ranks or ordering that could leak a prediction.
- Build the synonym map (MANC type, MaleCNS type, FlyWire and hemibrain names, older literature names) and the driver-line-to-type map from the connectome annotations and the annotation papers, without reference to outcomes.
- Use the kit exactly as frozen. If it has to change later, version it and log why.

### Freeze

Commit and tag `ledger-prereg-v1`. Push the branch and tag if pushing works. Create an OpenTimestamps proof of the rulebook if you can do it without an account (for example `uvx --from opentimestamps-client ots stamp <file>`). If pushing or stamping fails, log it and continue.

---

## 8. Stage 1: the predictions

Build these arms in priority order. Everything that is going to be locked must be locked **before Stage 2 begins**. An arm added later has to be marked "added after labels existed", which makes it weaker evidence.

### Arms

1. **A0, A1: the authors' own numbers.** Rebuild their per-neuron scores (933 neurons, 128 replicates) and their type-level scores (321 types, 16 replicates) from their released files, by script, with provenance. Look in their repository first. If the per-replicate results are only on Zenodo, download just the archives that hold them, up to about 20 GB. If that is not possible, BrainIR's numbers become primary.
2. **B0: the saved screen**, frozen exactly as it is.
3. **B1: BrainIR type-level screen (core arm).**
   - MANC v1.2.1 front-leg network, built through the same `paper_network()` helper so the matrix is identical to B0's.
   - Paper transmitter signs.
   - Every excitatory member of a type on both sides at the same current (the authors' grouping).
   - 16 replicates with the same seeds as B0.
   - Write the type-level tuner as new code in the ledger package. Mirror the locked `screen_candidate` line for line and change only the set of stimulated neurons.
   - Run both lower bounds (5 and 10) and keep as B1 whichever reproduces the authors' type-level scores better. That comparison involves no fly data, so it is allowed.
4. **S: anatomical baselines, no simulation.** Per type, at minimum: direct synapses onto front-leg motor neurons; two-hop path strength onto them (signed and absolute); total output synapses inside the network. Add one clearly labelled "informed" baseline: synapses onto the published core rhythm neurons. Add anything else you think a skeptical reviewer would try.
5. **B1-controls.** The B1 screen on five degree-preserving rewirings and five class shuffles. These are the null prediction sets.
6. **B3: the full nerve cord, six legs.**
   - Type-level screen on the 23,532-neuron network with a separate readout per leg.
   - Scale the activity bounds by network size, unless the authors' own full-cord configuration says otherwise.
   - Per type, save rhythm score, frequency and number of active motor neurons for each leg and each leg pair, plus the phase and coordination statistics defined in the rulebook.
   - Save compressed motor-neuron traces so later metrics need no re-run.
   - Because so few motor neurons are active per leg, always store the count next to the score and flag legs with fewer than 3.
7. **B2: the second fly.** B1 on the MaleCNS front-leg network, with types matched through `manc_type` and the mapping table. Record which types disagree between the two animals.
8. **B4: walking-background screen.** For all 475 types, including the inhibitory neurons the paper skipped: drive DNg100 on both sides at the paper's activation current, add the type at a few fixed strengths, and compare with DNg100 alone using the same seed. Decide in the rulebook how the 9 mixed-sign types are grouped. Lock a call for each type: halts the rhythm, speeds it up, slows it down, or no effect.
9. **B5: fixed-strength grid** for B1 with no auto-tuning. A real experiment cannot tune light per neuron.
10. **B6: one-sided activation** on the full cord, left members only and right members only, giving which legs move.

### Suggested defaults for derived quantities

Refine these in the rulebook before the lock.

- **Leg signal.** Lock two versions. The first follows the paper's own choice for its six-leg phase analysis; check the notes, since it may use each leg's copy of the core rhythm neurons instead of motor neurons. The second is a motor-neuron version, because real flies are scored on leg movement: the summed rate of the leg's active coxa promotor motor neurons (the paper's swing marker), with a fallback group declared in advance for legs that have none active.
- **Phase offset between two legs.** The paper's cross-correlation definition, per replicate.
- **Coupling strength.** Length of the mean resultant vector of the offsets across replicates, compared with the replicate-shuffled null.
- **Offsets reported.** Left against right in each segment, and neighbouring legs on the same side.
- **Tripod index.** Mean of cos(offset − target) over leg pairs, where the target is 0 within a tripod (L1, R2, L3 and R1, L2, R3) and π across tripods. It runs from −1 to 1.
- **When to report coordination.** Only when both legs pass the rhythm threshold.
- **B4 strengths.** 32, 128 and 512, with the run length the paper used for its activation runs.
- **B4 calls.** "Halts" if the rhythm score falls below 0.5 in at least 75% of the replicates whose DNg100-alone score was 0.5 or more, at the middle strength. "Speeds up" or "slows down" if the median paired frequency change exceeds 15%. Otherwise "no effect".

### Table layout

I will write the next prompt against these tables, so keep them tidy and stable. Every arm writes to `research/ledger/predictions/<arm>/`:

- `types.csv`, one row per type, with at least: `arm`, `network`, `manc_type`, `n_members`, `member_ids`, `n_replicates`, `n_usable`, `mean_score`, `median_score`, `frac_ge_0_5`, `best_score`, `median_freq_hz`, `median_current`, `median_n_active_readout`, `status`, `band`.
  - `status` is `ok`, `never_usable_weak` or `never_usable_strong`.
  - `band` is `driver`, `indeterminate` or `non_driver`.
- `replicates.parquet`, one row per type and seed.
- `legs.csv` for arms with per-leg output, one row per type and leg or leg pair: score, frequency, active motor-neuron count, low-confidence flag.
- `config.json` and `provenance.json`.

The key `manc_type` must be spelled identically in the prediction tables and the label tables, because the next run joins on it.

### Gates before the lock

- **G1, regression.** Your new screen code, run in single-neuron mode on at least 30 randomly chosen neurons with all 16 seeds, reproduces B0: same usable flag, same tuned current, same score. The stock backend lists its libraries only as lower bounds, so the versions installed today may be newer than when B0 was made. The target is still exact reproduction. If you see small differences, quantify them (largest score difference, any flipped usable flag, any changed current), find the cause if you can, and record whether B0 remains a fair stand-in.
- **G2, agreement with the authors.** Compare B1 with A1 (rank correlation, top-10 overlap, largest disagreements). If the rank correlation is below about 0.8, find out why before locking. If A1 cannot be rebuilt, compare against the type-level values recorded in the Pugliese notes.
- **G3, full cord.** Two-sided DNg100 on the full-cord build reproduces the pattern in the notes: rhythm in all six legs, weaker in the hind legs, no phase coupling between legs. If the full cord cannot be validated on DNg100 without tuning against other neurons, do not lock B3. Report it as failed and say why.
- **G4, determinism.** Re-running a sample gives identical output, and every output is hashed.
- **G5, nothing broken.** Every check that passed in the Stage S baseline still passes.
- **Independent review.** Before locking, have a fresh reviewer that did not write the code audit the rulebook, the stimulation code and the aggregation for bugs and for any place where an outcome could have leaked into a modeling choice. Fix what it finds and record the review.

### The one rule for this stage

No modeling choice may be made by looking at how any neuron with a known real-fly phenotype behaves, except DNg100 and DNb08. You know a lot of fly neuroscience from training. Do not use it to shape the model. If you catch yourself doing so, write it in the log.

### Lock

Write `research/ledger/LOCK_predictions_v1.json` with every prediction file, its SHA-256, the code commit, configurations, seeds, environment and a UTC time. Tag `ledger-predictions-v1`, push if you can, and timestamp the lock file. List any arm that was not completed as "not locked".

---

## 9. Stage 2: blind real-fly labels

### Who labels

Labelers must never see a model score. A subagent inherits this repo's `CLAUDE.md` and your scratchpad, so subagents are not blind enough.

- Run labelers as **separate headless Claude Code sessions**, started from a room directory outside the repo. `claude -p` is the usual way; check `claude --help` for the current flags.
- The room contains only the labeler kit. The sessions need web search and web fetch.
- Split the work across several sessions by source family.
- You, the orchestrator, launch the sessions, collect their files, validate the schema and run the deterministic aggregator. You do not write, edit or adjudicate labels yourself, because you have seen the predictions.
- Tell labelers not to open simulation score tables. If they see a simulation score for a type by accident, they mark that record as exposed.
- Afterwards, audit the labeler session transcripts for any read of the repo, a prediction file or a simulation score table. Report what you find.
- If a true separate session is impossible, use the strongest isolation you can, and state plainly in the log and the handoff how the blind was weakened.

### What counts

A record is one experiment: a DN type or driver line switched on in an adult fly (optogenetic or thermogenetic) with leg movement observable.

"Rhythmic leg movement" means repeated cyclic movement of a leg, three or more cycles, that starts or clearly increases with stimulation relative to controls or the pre-stimulus period.

### Labeling conventions

These go into the kit. They say how to code a kind of observation and carry no information about any particular neuron.

- **Walking, forward or backward:** yes for all three leg pairs.
- **"Increased locomotion" scored without leg tracking:** yes for all pairs, medium confidence.
- **Grooming:** yes only for the legs doing the rubbing or sweeping. The other legs are "no" if the fly is described as standing still, otherwise "unclear".
- **Single movements** (jump, takeoff, leg extension, posture change, reaching): no.
- **Turning or a speed change in a fly that was already walking:** recorded under "effect on ongoing walking". The leg rhythm fields are "not assessed" unless standing flies were also stimulated.
- **Stopping or freezing:** no for every pair observed, and recorded as a stop.
- **Wing, flight, song or abdomen behaviors:** legs "not assessed" unless the legs are described.
- **"No visible effect" in a systematic screen:** no for all pairs, with confidence set by how carefully the screen scored behavior.
- **Headless flies:** record the surface (ball, air, slippery surface, other).
- **A line that labels more than one DN type:** one record per type, marked as non-specific.

### Record fields

Design the final schema yourself. It must capture the following, with fixed vocabularies where I list them.

- Source: DOI, figure or table, page, and a quote of at most 25 words.
- The name used in the paper and the mapped `manc_type`, with mapping confidence.
- Driver line IDs, effector, and stimulation details.
- How much of the type the line covers, if stated.
- Sex.
- Preparation: `intact_free`, `intact_tethered`, `headless`, `other`. Also the sensory condition.
- Expression: `bilateral`, `unilateral`, `stochastic`.
- Line specificity: `clean`, `minor_offtarget`, `multi_dn`, `unknown`, with the other cell types named.
- Front, middle and hind leg rhythm, each `yes`, `no`, `unclear` or `not_assessed`.
- Behavior category: `forward_walking`, `backward_walking`, `turning`, `anterior_grooming`, `posterior_grooming`, `halting`, `takeoff_or_jump`, `landing_or_extension`, `wing_or_flight`, `posture`, `no_visible_effect`, `other`.
- Frequency, if reported.
- Coordination notes.
- Effect on ongoing walking: `stops`, `slows`, `speeds`, `turns`, `none`, `not_assessed`.
- Penetrance and number of flies.
- Source type: `systematic_screen` (every line reported) or `targeted_study`.
- Labeler confidence: `high`, `medium`, `low`.
- Whether the labeler saw a simulation score for this type.

### Sources

Start from a source registry, then search beyond it. These leads are from my memory and the details may be wrong, so verify each one. I name sources only, with no outcomes.

- Cande et al. 2018 (eLife), the optogenetic DN behavior atlas, with its supplementary tables and public movies. It is the backbone because it tested lines systematically, including ones that did little, which limits positive-result bias.
- Namiki et al. 2018 (eLife) for the line-to-type map.
- The 2025 Janelia split-GAL4 DN driver catalogue (about 806 lines, 190 types).
- Guo, Zhang and Simpson 2022 and other Simpson-lab grooming papers; Hampel et al. 2015.
- Bidaye et al. 2014 and 2020.
- Sapkal et al. 2024 (Nature, halting).
- Sapkal et al. 2026 (bioRxiv 10.64898/2026.04.29.721658).
- Braun et al. 2024 (Nature, Ramdya lab).
- Rayshubskiy et al. and Yang et al. 2024 (steering).
- Ache et al. 2019 and the escape and takeoff literature.
- Lillvis et al. 2024.
- Pugliese et al. 2026.
- Any 2024 to 2026 paper or preprint that activates a named DN type.
- For names: Cheong et al. 2024, Stürner et al. 2025 and the MaleCNS paper.

Labelers may propose additions to the synonym and driver-line maps. Additions are versioned like any other kit change.

### Quality

- Every record needs a locator and a short quote. The second pass confirms that the quote really is in the source. Records that cannot be verified are dropped, and paywalled sources read only from the abstract are marked low confidence.
- Run two independent labeling passes over the same experiments. Report agreement on the primary field (Cohen's kappa and raw agreement).
- Run an independent search to estimate what the first pass missed.
- Resolve disagreements with a third blind session.
- Produce the per-type consensus labels with a script, using the rule in the rulebook. Suggested rule: headless outranks intact, clean lines outrank non-specific ones, and unresolved conflicts become "conflicting".
- Draw a random sample of 20 records with locators so I can spot-check them by hand.

### Label tables

Write to `research/ledger/labels/`:

- `sources.csv`, the registry.
- `records.jsonl`, one experiment per line.
- `synonyms.csv` and `driver_lines.csv`.
- `type_labels.csv`, one row per `manc_type`: front, middle and hind leg consensus, stop call, best preparation, best line specificity, number of records, whether a systematic source exists, exposed flag, confidence.
- `agreement.md`.

### Movies

Do not analyse the atlas movies in this run. Report whether they are downloadable, how large they are, and whether pose tracking on them looks feasible.

### Freeze

Commit the label tables. Tag `ledger-labels-v1`, push if you can, timestamp.

---

## 10. If time or money runs short

- **Core, in this order:** setup and G0; rulebook and scoring code; A0, A1 and B0; B1; baselines; B1-controls.
- **Optional, in this order:** B3, B2, B4, B5, B6.
- **Then** the predictions lock, **then** the labels.

Decide what to drop before the lock, because an arm that is not locked before labeling starts is weaker evidence. It is better to lock fewer arms properly than more arms carelessly.

---

## 11. When things go wrong

| Problem | Default action |
|---|---|
| A download stalls or fails | Retry and resume. MANC is essential. MaleCNS is optional. |
| G0 fails and you cannot fix the rebuild | Build the networks from the authors' own matrices, which are pinned by hash. Say so in the lock and the handoff. |
| Modal is unavailable or out of credit | Run the core arms locally and drop the optional arms. |
| The authors' per-type table cannot be rebuilt | BrainIR's B1 becomes primary. |
| The full cord fails G3 | Do not lock B3. |
| Separate labeler sessions cannot be launched | Use the strongest isolation available and state the weakness. |
| A source is paywalled | Label from the abstract only, low confidence. |
| Pushing is denied | Keep tags local, rely on the timestamp proofs, tell me. |
| Disk is nearly full | Drop bulk traces first and keep the summaries. Then drop MaleCNS. |
| You find a bug after a lock | Make a new version with a changelog. Never edit the locked one. |
| Your context was compacted | Re-read `STATE.md`, `LOG.md` and `RUN1_PROMPT.md` before continuing. |

---

## 12. Finish

### Done means

- G0 passed, or the fallback is documented.
- `ledger-prereg-v1`, `ledger-predictions-v1` and `ledger-labels-v1` exist, each with hashes and a timestamp proof where possible.
- Every locked arm passed its gates and the independent review.
- The label tables validate against the schema, and the agreement report exists.
- The baseline checks still pass.
- No label was joined to any prediction.

### Handoff: `research/ledger/HANDOFF_1.md`

Write a report I can paste into another conversation, 1,800 words at most, in plain language. It must contain:

1. This machine: platform, versions, the G0 result, what could not run here, and whether pushing worked.
2. What exists now and where: branch, commits, tags, lock hashes, timestamps.
3. The rulebook in ten lines, and every decision where you departed from this prompt, with the reason.
4. Gate results G1 to G5 and the independent review's findings.
5. **Predictions only:** for each arm, the number of types, usable types, predicted drivers and predicted non-drivers; the agreement between the authors' numbers and BrainIR's; the agreement between the two flies.
6. **Labels only:** the number of sources, records and types with a clear front-leg label, split by preparation and by line specificity; agreement statistics; the transcript audit; the final exposed list; how many labeled types also appear in the prediction tables, matched by name only.
7. Money and wall-clock time spent.
8. Anything that worries you: weak blinds, shaky mappings, arms you would not trust.
9. What you would do next.
10. A plain statement that no label was joined to any prediction.

Sections 5 and 6 must never put a score and an outcome for the same type side by side. Print the handoff as your final message as well.
