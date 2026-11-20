# BrainIR prediction ledger: pre-registration (rulebook), version 1

Status: **version 1**, frozen by git tag `ledger-prereg-v1` together with the scoring code and the labeler kit.
Spec: `research/ledger/RUN1_PROMPT.md`. Decisions and their reasons: `research/ledger/LOG.md` (L-numbers below).
Amendments: see section 12. Nothing in this file may be changed after the tag; a change is a new version (`PREREG_v2.md`)
with a changelog entry stating which stage had produced data and whether labels existed.

This file fixes, before any new screen is run and before any literature is read for outcomes: the unit, every prediction
arm and its exact procedure, every derived quantity, the truth definition, the consensus rule, the primary statistic, the
decision rules, the secondary analyses and the gates. A stranger should be able to run the scoring from this file and the
code it names without asking a question.

---

## 1. What is measured

**Question.** When a descending-neuron (DN) type is switched on in the connectome rate model of Pugliese et al. (2026),
does the model's prediction ("this type drives rhythmic leg motor activity") agree with what happens when the same type
is switched on in a real fly?

**Primary quantity.** AUROC of the model's type-level rhythm score for the label "activation evokes rhythmic front-leg
movement", over labeled, non-exposed, excitatory DN types (section 7), compared with chance (0.5) and with anatomical
baselines (section 3.5).

**Blind.** Predictions (this file's arms) and labels (blind curation by separate sessions, section 6) are produced
separately and are never joined before both are frozen and reviewed. The scoring entry point
`brainir_ledger.scoring.pipeline.run_scoring` refuses to run unless `research/ledger/UNBLIND.json` exists and names the
SHA-256 of both lock files (`brainir_ledger.scoring.require_unblind`); run 1 never creates it.
- `UNBLIND.json` = `{"predictions_lock": "LOCK_predictions_v<k>.json", "labels_lock": "LOCK_labels_v<k>.json",
  "predictions_lock_sha256": ..., "labels_lock_sha256": ..., "authorised_by": ..., "utc": ...}`; lock names are plain file
  names in `research/ledger/` (no paths). It is created only by the person who authorises unblinding.
- `LOCK_predictions_v<k>.json` lists every locked arm's files with SHA-256 (`arms_locked`), the arms not locked and why,
  the gates and reviews; `LOCK_labels_v<k>.json` lists every label table (`labels`, at least `records.jsonl` and
  `type_labels.csv`) and the raw session outputs with SHA-256. Both are written by `ledger/scripts/lock.py`.
- Before computing anything the scoring verifies every file it reads against these locks, recomputes the type labels from
  `records.jsonl` and requires them to equal `type_labels.csv`, writes the primary result first, and reports every
  secondary analysis with a status (ok / not_locked / input_missing / error).

---

## 2. Unit and names

- **Unit**: the DN cell type under MANC naming, key `manc_type` = the `type` of the authors' MANC front-leg table
  (`wTable_20250813_DNtoMN_unsorted_withModules.csv`), which equals BrainIR's `manc:v1.2.1` `cell_type` for every DN
  (checked: 0 of 1,318 DN rows differ). Types that occur only in the full-cord network keep that table's name
  (`wTable_20251006`, `manc:v1.2.3`); where the same body has a different name in the two tables the v1.2.1 name is used.
- **Synonym map** `research/ledger/labels/synonyms.csv` (kit copy `research/ledger/kit/synonyms.csv`): MANC type ->
  MaleCNS types (bodies whose curated `mancType` is the MANC type, MaleCNS v1.0 body annotations), FlyWire and hemibrain
  types (same annotations), literature names (the annotations' `synonyms` field, e.g. "Bidaye 2020: BDN2"), plus names
  proposed by labelers (versioned). Built by `ledger/scripts/build_kit.py` from annotation files only.
- **Driver-line map** `research/ledger/labels/driver_lines.csv`: line -> DN type(s), from anatomy/line-catalogue papers
  (name and line columns only, never behaviour columns).
- **Exposed list** (LOG L8): DNg100, DNb08, DNg12, DNg97, MDN, DNa01, DNa02, DNp09, DNg13, DNp01, DNg16, DNg55, DNg75,
  plus DNg74 and DNg62 (found in the repository notes, counted as exposed although uncertain). Literature names are
  mapped to `manc_type` through the synonym map; a name that maps to several MANC types exposes all of them. Resolved
  (`kit/exposed_types.csv`): **18 MANC types**: DNa01, DNa02, DNb08, DNfl028, DNg100, DNg12, DNg13, DNg16, DNg55, DNg62,
  DNg74, DNg75, DNg97, DNp01, DNp09, DNp71, DNxl022, MDN. Exposed types are predicted and labeled but reported in a
  separate row and excluded from the headline number.

---

## 3. Prediction arms

Common to every simulated arm unless stated: BrainIR's simulator (`brainir.sim`, locked) and published score
(`brainir.metrics.rhythm`, locked), paper transmitter signs (ACh +1, GABA/Glu -1, other 0), b = 0.03, the authors'
truncated-normal parameter priors with size scaling, RK45 at rtol 2e-6 / atol 5e-9, output grid 1 ms, pulse from
0.02 s to T - 0.001 s, score window t >= 0.25 s, an MN is active when its peak rate in the window exceeds 0.01 Hz,
prominence 0.05. Parameter seeds 0..15 (16 replicates) unless stated. Backend: `brainir_ledger.backend.LedgerModalBackend`
on Modal Linux with the pinned image and numerics environment (LOG L11-L12); one platform for every locked arm.

### 3.1 A1: the authors' type-level co-activation screen (PRIMARY prediction)
- Source: authors' repository `smpuglie/Pugliese_2026` @ 10e7661, `figures/DN_Screen-hyak-run_id=32818378/scoreSummary.csv`
  and `activitySummary.csv` (321 types x 16 replicates), pinned by SHA-256 in `brainir_ledger.authors`. Run 32818378 is
  the `dns_by_type` run (its Zenodo `run_config.yaml`: `sim=DN_Screen_ByType`, `dns_by_type: true`, tuner bounds
  `n_active_lower 10`, `n_active_upper 1500`, `n_high_fr_upper 200`; LOG L13).
- Per replicate: the authors' score (138 module-labelled front-leg MNs, active after 250 ms) and nActive (neurons with
  peak rate > 0.01 Hz over the whole 1 s run).
- **Usable replicate: 5 <= nActive <= 1500** (the authors' Extended Data Figure 1 notebook, cell 27: the rule behind the
  published type-level figure). The paper's prose "lower bound of 10" is the tuner's bound in that run (see above);
  sensitivity analysis A1-lo10 uses 10 <= nActive <= 1500.
- **Type score = mean over usable replicates.** A type with no usable replicate is `never_usable`; its primary score is 0
  (section 5).

### 3.2 A0: the authors' single-neuron screen (933 neurons x 128 replicates)
- Source: `figures/DN_Screen-hyak-combined128reps/combined{Score,Activity}Summary.csv` (index = row of the authors'
  front-leg table), same usability rule. Per neuron: mean over usable replicates. Per type: maximum and mean over member
  neurons (types with no usable member: never usable). Used in secondary analyses only.

### 3.3 B0: BrainIR's saved single-neuron screen (933 x 16), frozen as it is
- `benchmarks/dng100_walking_cpg/results/dn_screen_manc_v1.2.1_nt-paper_r16.json` (copied unchanged, hash recorded).
  Usability = the BrainIR tuner's verdict. Per type: maximum and mean of member means. Secondary only.

### 3.4 B1: BrainIR type-level screen (core arm; the independent replication of A1)
- Network: MANC v1.2.1 front-leg network built by the locked helper `paper_network("manc", "v1.2.1", "paper")`
  (identical matrix to B0). Read-out: the 144 front-leg MNs (role `vnc_motor`, `sub_class` `fl`), as in B0.
- Groups: the authors' grouping, every excitatory member of a type (authors' table: class "descending neuron" and
  predictedNt "acetylcholine"), both sides, one shared current: 321 groups, 933 neurons.
- Tuner: `brainir_ledger.typescreen.screen_group`, the locked `screen_candidate` mirrored line for line with the stimulus
  set as the only change; start 128, halve/double/bisect, at most 10 runs, accept the first run with
  `n_active_lower <= active (any positive rate) <= 1500` and `<= n_high_fr_upper` neurons above 100 Hz; the accepted run is
  scored; no accepted run = unusable replicate. T = 1.0 s.
- `n_high_fr_upper = 200` (the authors' type-level configuration; the stock single-neuron value is 100; LOG L13).
- **Lower bound selection (fixed now):** B1 is run with `n_active_lower` = 5 and = 10 (everything else identical). The
  kept B1 is the one with the larger Spearman correlation with A1 over all 321 types (primary scores, never-usable = 0).
  If the two correlations differ by less than 0.01, the authors' value 10 is kept. The other run is kept as `B1-alt` and
  reported. This comparison involves no fly data.
- Type score = mean over usable replicates; never usable -> 0 with reason code.

### 3.5 S: anatomical baselines (no simulation), front-leg network, same 321 excitatory groups
Computed from the network's observed counts `C` (floor 5, autapses removed, unsigned) and signed matrix `W` (paper signs);
all sums over the type's excitatory members j; MN = the 144 front-leg MNs:
- `S1_direct_mn`: sum_j sum_{m in MN} C[m, j] (direct synapses onto front-leg MNs).
- `S2_twohop_signed`: sum_j sum_{m in MN} sum_k W[m, k] W[k, j] (signed two-hop path strength; k = any neuron).
- `S3_twohop_abs`: the same with |W|.
- `S4_total_out`: sum_j sum_i C[i, j] (all output synapses inside the network).
- `S5_out_partners`: number of distinct postsynaptic partners of the members (union).
- `S6_premotor`: sum_j sum_{k in P} C[k, j], P = neurons other than MNs with at least one floor-5 connection onto a
  front-leg MN.
- `S7_n_members`: number of excitatory members.
- `S8_informed` (clearly labelled INFORMED): sum_j sum_{k in core} C[k, j], core = the published core rhythm neurons
  of the front-leg network (the seven labelled neurons of `benchmarks/dng100/oracle/oracle.json`, network `manc_v1.2.1`).
  It uses the model's own published circuit, so it is excluded from "best anatomical baseline" and reported separately.
- Higher value = predicted more likely to drive rhythm (AUROC orientation).

### 3.6 B1-controls: null prediction sets
- Five degree-preserving rewirings (`degree_preserving_rewire`, 10 attempted swaps per edge, network seeds 101-105) and
  five class shuffles (`class_shuffle` with the authors' five classes `paper_shuffle_classes`, seeds 201-205) of the
  front-leg network (functions in `benchmarks/dng100_walking_cpg/robustness_experiments.py`, imported read-only).
- On each control network: exactly the kept B1 procedure (same groups, tuner configuration, parameter seeds 0..15).
- Expected AUROC near 0.5; reported per control and as the mean and range over the ten.

### 3.7 B3: full nerve cord, six legs (optional arm 1)
**Status in run 1: NOT LOCKED.** Gate G3 was evaluated before this freeze on DNg100 alone and failed item 4 (section 9),
so B3 is not run as a locked arm in run 1. Its definition is kept here unchanged for the record.

- Network: the authors' full-cord network exactly (23,532 neurons; their node list on `manc:v1.2.3`, paper signs, floor 5,
  their 16 autapses, their sizes; LOG L10), verified pair by pair against their matrix.
- Groups: excitatory DN members per type in the full-cord table (class "descending neuron", predictedNt "acetylcholine"),
  both sides.
- **Tuner bounds (calibrated on DNg100 only, LOG L14):** start 128, 10 runs, `n_active_upper = round(1500 x 23532/4604)
  = 7667`, `n_high_fr_upper = round(200 x 23532/4604) = 1022`, **`n_active_lower = 100`**. Size-scaled bounds alone
  (lower 26) accept two-sided DNg100 at 256, where no leg MN is active (DNg100-only sweep: 34-51 active neurons at 256,
  572-1,087 at 380, runaway above 450). With lower = 100 the tuner moves DNg100 128 -> 256 (too weak) -> 512 (too strong)
  -> 384, the authors' own full-cord operating point (their run configs: 380 per DNg100, LOG L14). Any lower bound in
  52-572 gives the same DNg100 path; 100 is a round value inside it. No other neuron was used.
- T = 1.0 s, seeds 0..15. Main score: all 329 module-labelled MNs. Per leg (T1L, T1R, T2L, T2R, T3L, T3R) and per segment
  pair (front = T1L+T1R, middle = T2, hind = T3): score, frequency, number of active MNs (section 4). Leg signals and
  inter-leg offsets for all 15 leg pairs per replicate, both versions (section 4.4). Compressed traces of active MNs, of
  the six E1 copies and of the stimulated members are stored.
- Low-confidence flag: a leg (or pair) with median active MNs < 3 over usable replicates.
- **Gate G3 (must pass before B3 is locked):** section 9.

### 3.8 B2: the second fly, MaleCNS (optional arm 2)
- Network: the authors' MaleCNS front-leg network (`W_20260210_vncRoisOnly.csv`, `wTable_20260210_vncRoisOnly.csv`,
  pinned by SHA-256 in `reproduce_manc_connectivity.EXTERNAL`): their signed matrix, their `size` column, signs from
  `consensusNt` (the paper's rule). Read-out: MaleCNS front-leg MNs (`superclass` motor class and `subclass` "fl"; if that
  selection is empty, rows with a `motor module`).
- Groups: for each MANC type t, the network's MaleCNS DNs whose curated `mancType` (MaleCNS v1.0 body annotations,
  LOG L9) equals t and whose `consensusNt` is acetylcholine.
- Procedure: exactly the kept B1 procedure (bounds unchanged: 4,310 vs 4,604 neurons). Seeds 0..15.
- Disagreements recorded per type: present in MANC but no MaleCNS member, different member count, different transmitter.

### 3.9 B4: walking-background screen (optional arm 3), all DN types including inhibitory ones
- Front-leg network, T = 2.0 s (the paper's activation runs), seeds 0..15. Background: both DNg100 at 250 each.
- For each of the 475 DN types: background plus every member of the type (all transmitters together; the 9 mixed-sign
  types are stimulated as one group, as a driver line labels all members) at 32, 128 and 512 per member, added to any
  background current. Each run is paired with the background-only run of the same seed.
- Per run: score and frequency (front-leg MNs). Calls at the middle strength (128):
  - `background_not_rhythmic` if fewer than 8 of the 16 background-only runs score >= 0.5 (no call is made);
  - `halts` if score < 0.5 in at least 75 % of the replicates whose background-only score is >= 0.5;
  - otherwise `speeds_up` / `slows_down` if the median paired relative frequency change (over replicates where both runs
    score >= 0.5) is above +15 % / below -15 %;
  - otherwise `no_effect`. Fewer than 4 replicates with both scores >= 0.5 and no halt -> `no_effect_low_n`.
  Calls at 32 and 512 are reported as secondary.

### 3.10 B5: fixed-strength grid (optional arm 4)
- B1 groups and network, no tuning: every member at 32, 64, 128, 256 and 512, T = 1.0 s, seeds 0..15.
- Per type and strength: mean score over all 16 replicates (no usability filter: an experiment cannot tune light per
  neuron), fraction >= 0.5, fraction of runs inside the activity bounds. Summary score: maximum over strengths of the mean.

### 3.11 B6: one-sided activation on the full cord (optional arm 5)
**Status in run 1: NOT LOCKED** (it depends on B3's full-cord procedure, whose gate G3 failed).

- B3 procedure with only the left members (`rootSide` LHS) or only the right members (RHS) of each type.
- A leg is predicted to move if >= 50 % of usable replicates have leg score >= 0.5 with >= 1 active MN in that leg.

---

## 4. Derived quantities (exact formulas)

All computed by `brainir_ledger.legs` / `brainir_ledger.tables`; definitions informed only by DNg100/DNb08 simulations
and by the authors' code.

4.1 **Score of a set of MNs** (a leg, a segment pair, all MNs): the published network score: mean over the set's active
MNs (peak > 0.01 Hz for t >= 0.25 s) of the per-trace autocorrelation score; 0 if none active.

4.2 **Frequency** of a run: mean over the set's active MNs with a detected autocorrelation peak of 1/(peak lag) in Hz.
Type frequency: median over usable replicates with score >= 0.5.

4.3 **Active MN count**: number of the set's MNs with peak > 0.01 Hz for t >= 0.25 s.

4.4 **Leg signals.** Version 1 (the paper's six-leg phase analysis, Extended Data Fig. 8 notebook): the rate of the leg's
copy of the published core excitatory interneuron (type IN17A001; one copy per leg by `somaNeuromere` x `somaSide`).
Version 2 (motor): summed rate of the leg's active coxa-promotor MNs (type "Tergopleural/Pleural promotor MN"); fallback 1
(declared now): the leg's active "coxa swing" module MNs (the T2/T3 legs have no promotor MN of that type); fallback 2: all
active module MNs of the leg; else no signal. The source used is recorded per leg and replicate.

4.5 **Phase offset** of leg B relative to leg A in one replicate (the authors' code): z-score both signals over
t >= 0.25 s; period P = lag of the first peak (prominence >= 0.05, `scipy.signal.find_peaks`) of the autocorrelation of
the mean-subtracted A; cross-correlate A with B; take the arg-max lag within [-P, P-1] (the authors' slicing); offset =
2 pi lag / P wrapped to [-pi, pi). Undefined if A has no period or either signal is flat.

4.6 **When coordination is reported**: only for replicates where both legs pass the rhythm threshold (leg score >= 0.5)
and the offset is defined.

4.7 **Coupling strength** of a leg pair: R = |mean(exp(i offset))| over the eligible replicates (n >= 8 required; fewer:
not reported). Null: the same pair with leg B taken from another replicate: 1,000 uniform random derangements of the
eligible replicates (rejection sampling, `numpy.random.default_rng(20261123)`), R_null computed for each; report R, the
circular mean offset, the null mean and p = (1 + #{R_null >= R}) / 1001. **Coupled** if p < 0.01 and R >= 0.5
(`brainir_ledger.legs.coupling`).

4.8 **Offsets reported**: left vs right in each segment (T1L-T1R, T2L-T2R, T3L-T3R) and neighbouring legs on the same side
(T1L-T2L, T2L-T3L, T1R-T2R, T2R-T3R): circular mean, R, n, null mean, p.

4.9 **Tripod index** of a replicate: mean of cos(offset - target) over all leg pairs (of the 15) whose legs are both
rhythmic and whose offset is defined; target 0 within a tripod ({T1L, T2R, T3L} or {T1R, T2L, T3R}), pi across; needs
>= 3 pairs. Type value: mean over replicates. Range -1 to 1.

4.10 **B4 calls**: section 3.9. Relative frequency change = (f_type - f_background) / f_background per seed.

---

## 5. Status, bands and the primary score

- `status` per type and arm: `ok` (at least one usable replicate), `never_usable_weak` (no usable replicate and at least
  half of the replicates ended too weak), `never_usable_strong` (otherwise). For A0/A1: too weak = nActive < 5, too strong
  = nActive > 1500. For BrainIR tuners: the verdict of the last tuning run.
- **Primary score** = mean over usable replicates; `never_usable_*` -> 0 (primary); excluded (sensitivity analysis).
- `band`: `driver` if score >= 0.5 (the paper's rule), `non_driver` if score < 0.05, else `indeterminate`.

---

## 6. Truth: blind labels

- Records are produced by separate headless Claude Code sessions that never see a model score (kit
  `research/ledger/kit/`, `PROTOCOL.md` sections 1-7; launcher `ledger/scripts/labels_rooms.py` with frozen flags). The orchestrator launches sessions, validates schema and runs the deterministic
  aggregator; it never writes, edits or adjudicates a label.
- A record = one experiment: a DN type or driver line activated (optogenetic or thermogenetic) in an adult fly with leg
  movement observable. Fields and vocabularies: `research/ledger/kit/record_schema.json` (validator
  `brainir_ledger.labels.schema`). Conventions: `research/ledger/kit/PROTOCOL.md` (copied from prompt §9, no neuron-
  specific content).
- "Rhythmic leg movement" = repeated cyclic movement of a leg, three or more cycles, that starts or clearly increases with
  stimulation relative to controls or the pre-stimulus period.
- **Identity.** Every pass-1 record gets a unique `exp_id` = "<session>:<record_id>" at collection; pass 2 and the
  adjudicator copy it from their input files; nothing is matched by content. The same experiment written by two pass-1
  sessions (identical DOI, locator, driver lines, name used, preparation, MANC type, effector and stimulation) is kept once,
  from the session earliest in the order atlas, catalogue, grooming, walking_stopping, steering, escape_landing,
  recent_broad, pugliese_dedicated (logged).
- **Passes.** Pass 1 finds and labels experiments (eight sessions split by source family, `kit/families.json`). Pass 2
  independently re-labels the same experiments given identifiers only (`exp_id`, DOI, locator, driver lines, name used,
  preparation, effector, stimulation; never a label, quote or MANC type) and maps the name to a MANC type itself (Phase A);
  only after Phase A is saved does it receive the pass-1 quotes and check each against the source (Phase B,
  `quote_checks.csv`); experiments it cannot find go to `not_found.csv`. Compared fields: `manc_type`, the three leg-rhythm
  fields, `effect_on_walking`, `line_specificity`. Two independent search sessions look for experiments without any list
  (capture-recapture). A third blind session adjudicates every compared field on which passes 1 and 2 disagree
  (readings in seeded random order, seed 20261125); the experiments of the dedicated family (Pugliese 2026, Sapkal 2026)
  have their own pass-2 and adjudication sessions, the only ones allowed to open those two sources.
- **Final record** = the pass-1 record (quote found by pass 2, not in `not_found.csv`) with each disputed field group
  replaced by the adjudicator's reading (groups: MANC type with mapping confidence and basis; line specificity with other
  cell types; each leg field; effect on walking); `labeler_confidence` = the lowest of the readers who contributed;
  `saw_simulation_score` = true if any reader saw a score; re-validated (invalid -> dropped). A dispute without an
  adjudicated record -> dropped. All drops are logged in `labels/merge_log.json`.
- **Search-only records** (found by the search sessions but not by pass 1, matched on normalised DOI and MANC type) are
  reported separately (`search_only_records.jsonl`) and never enter the consensus. Completeness: Chapman capture-recapture
  estimate at the (normalised DOI, MANC type) level between the de-duplicated pass-1 set and the search set; preprint and
  journal versions with different DOIs inflate the "missed" count (stated as a limitation).
- **Operating rules fixed now:** one repair round per session for schema-invalid records (the same session fixes only the
  listed lines; the error list never repeats label values); a session whose transcript audit shows a file access outside
  its room, a fetch of a banned host, or (outside the dedicated sessions) a fetch of the two dedicated sources is excluded
  (its pass-1 records, or the experiments it read as pass 2 / adjudicator); the model each session actually used (the
  launcher allows a fallback when the main model is busy) is recorded; the orchestrator looks only at validation summaries
  and aggregate counts of labels until unblinding (never at a per-type label).
- **Known weakness:** the labelers are language models that may have read the Pugliese preprint or reviews of it during
  training; the blind is procedural (no access to scores in the session), not cognitive. They are instructed not to use
  memory as evidence, and every record must rest on a quote from a source opened in the session.
- **Type consensus (per leg pair: front, middle, hind; `brainir_ledger.labels.aggregate`):** eligible records are final
  records with `saw_simulation_score` false, mapping confidence not `low` and a mapped MANC type. For a leg field, take the
  eligible records whose value is yes, no or unclear, then
  1. if any has confidence high or medium, drop the low-confidence ones;
  2. if any has line specificity other than `multi_dn`, drop the `multi_dn` ones;
  3. keep the best preparation rank (headless 0; intact_free / intact_tethered 1; other 2), then the best specificity rank
     (clean 0; minor_offtarget 1; unknown 2; multi_dn 3);
  4. all remaining `yes` -> yes; all `no` -> no; both yes and no present -> `conflicting`; otherwise (some unclear) ->
     `unclear`;
  5. no record with yes, no or unclear -> `not_assessed`.
  **Stop call** (`stop_call`): each eligible record gives `stops` (effect `stops` or category `halting`), `no_stop`
  (front-leg rhythm yes, or effect none / slows / speeds / turns) or nothing; over the records that give something, apply
  steps 1-3 above; one value -> that value, two -> `conflicting`, none -> `not_assessed`. **Walking effect**
  (`walking_effect`): the same with the record's `effect_on_walking` (not_assessed records give nothing). **Reported
  frequency** (`freq_hz`): median of the numeric `frequency_hz` of eligible records with front-leg rhythm yes. These are
  reported, never used in the primary analysis.
- Duplicate records of one experiment (same experiment key) found by two pass-1 sessions count once.
- **Primary truth** = front-leg consensus label in {yes, no}. Unclear, conflicting, not assessed: excluded.

---

## 7. Primary analysis

- **Set**: types with a front-leg consensus label in {yes, no}, that are among A1's 321 excitatory types, and are not
  exposed.
- **Statistic**: AUROC of A1's primary score (ties: average ranks; Mann-Whitney form).
- **Interval**: 95 % percentile bootstrap from 10,000 resamples of types, stratified by label (positives and negatives
  resampled separately, so every resample has both classes), seed 20261120.
- **Test**: permutation p-value from 10,000 label shuffles over the set, one-sided (AUROC > 0.5), p = (1 + #{AUROC_perm >=
  AUROC_obs}) / 10,001, seed 20261121.
- **Decision rules**:
  - "Underpowered" if the set has fewer than 20 types or fewer than 5 in either class: report descriptively, claim nothing.
  - "The model predicts" if the interval's lower bound is above 0.5 (the permutation p-value is descriptive).
  - "The simulation adds value beyond wiring" is tested only if the model predicts, and holds only if A1 beats the best
    uninformed anatomical baseline (S1-S7, the one with the highest AUROC on the same set; ties go to the first in S1..S7
    order) on a paired stratified bootstrap of the AUROC difference (10,000 resamples, seed 20261122): lower bound of the
    95 % interval of (AUROC_A1 - AUROC_best) above 0. The comparison with S8 (informed) is reported separately.
- **Also reported for the headline set**: precision of predicted drivers (band driver) = fraction labeled yes; negative
  predictive value of predicted non-drivers = fraction labeled no; numbers in each band; calibration (fraction yes per
  score bin [0, 0.05), [0.05, 0.25), [0.25, 0.5), [0.5, 0.75), [0.75, 1]; Brier score of the score read as a
  probability); the same statistics for B1.

---

## 8. Secondary analyses (all descriptive; no decision rule)

1. Headless only and intact only (consensus recomputed from records of that preparation).
2. Clean lines only (specificity clean or minor_offtarget) and non-specific only.
3. Systematic-screen sources only.
4. Exposed types included (the full labeled set).
5. Single-neuron screens summarised per type: A0 max, A0 mean, B0 max, B0 mean.
6. Authors' numbers against BrainIR's: B1 and B1-alt AUROC; A1 vs B1 rank correlation; A1-lo10.
7. Never-usable types excluded instead of scored 0.
8. MaleCNS replication (B2): AUROC on its matched types; B1 vs B2 Spearman over common types and the list and count of
   types whose band differs between the two animals.
9. Per-leg-pair predictions of B3 against front, middle and hind labels: NOT AVAILABLE in run 1 (B3 not locked, G3
   failed). B6: not available.
10. Predicted against reported frequency: B1's `median_freq_hz` (rhythmic usable replicates) against the label-side
    `freq_hz` (section 6), Spearman over non-exposed types with both (A1 carries no frequency).
11. Rewired controls: AUROC of each of the ten control sets (expected near 0.5).
12. Stop and modulation: B4's middle-strength call (`call_128`) against `stop_call` (halts vs stops; raw agreement,
    kappa, confusion table) and against `walking_effect` (halts->stops, speeds_up->speeds, slows_down->slows,
    no_effect->none; raw agreement, kappa).
13. Fixed-strength grid B5: AUROC at each strength (`score_I32` ... `score_I512`) and of the maximum over strengths
    (`primary_score`).
14. Every anatomical baseline's AUROC with interval (and S8 informed).

---

## 9. Gates before the predictions lock

- **G1 regression**: the ledger tuner in single-neuron mode on 30 randomly chosen excitatory DNs (numpy
  `default_rng(20261124).choice(933, 30, replace=False)` over the 933 candidates in table order) x 16 seeds reproduces B0:
  same usable flag, same tuned current, same score. Differences are quantified (largest score difference, flipped usable
  flags, changed currents); the cause is tested by re-running the differing jobs without the numerics environment on
  AVX-512 and non-AVX-512 hosts.
- **G2 agreement with the authors**: B1 vs A1 Spearman correlation, top-10 overlap, the ten largest rank disagreements. If
  the correlation is below 0.8 the cause is investigated before locking. Allowed remedies: a code bug demonstrated on a
  synthetic test or on DNg100/DNb08 is fixed and the arm re-run; nothing else (no model or procedure change motivated by
  named types). Otherwise B1 is locked as it is, and the disagreement is reported.
- **G3 full cord** (before B3 is locked), the authors' configuration: both DNg100 at 380, T = 2.0 s, seeds 0..63.
  Pass requires all of:
  1. every leg rhythmic in some replicates: fraction of replicates with leg score >= 0.5 at least 0.10 in each of the six
     legs (authors: 0.73, 0.58, 0.47, 0.79, 0.16, 0.78 for T1L, T1R, T2L, T2R, T3L, T3R);
  2. per leg, |our fraction >= 0.5 - authors'| <= 0.25 and |our median score - authors'| <= 0.30 (authors' medians 0.887,
     0.687, 0.452, 0.936, 0.215, 0.716);
  3. hind legs weaker: mean leg score of T3L and T3R below that of T1L and T1R;
  4. no inter-leg phase coupling: none of the seven reported pairs (section 4.8) is coupled (section 4.7) with leg signal
     version 1;
  5. the B3 procedure applied to the DNg100 type is accepted at 384 in at least 14 of 16 seeds and its front-pair score
     is >= 0.5.
  If G3 fails, B3 and B6 are not locked and the failure is reported.
  **Result (evaluated before this freeze, DNg100 only; `research/ledger/gates/G3_REPORT.md`):** items 1-3 pass (per-leg
  fraction >= 0.5 ours/authors T1L 0.84/0.73, T1R 0.61/0.58, T2L 0.48/0.47, T2R 0.83/0.79, T3L 0.20/0.16, T3R 0.81/0.78;
  hind mean 0.48 < front 0.68); **item 4 fails**: T2R-T3R (R 0.88, p 0.001), T1L-T2L (R 0.59, p 0.001) and T3L-T3R
  (R 0.60, p 0.009) are coupled. G3 therefore FAILS; B3 and B6 are not locked in run 1 (LOG L16).
- **G4 determinism**: 100 randomly chosen jobs of each locked simulated arm are re-run in a separate campaign (other
  containers); every result digest must be identical. Every output file is hashed in the lock.
- **G5 nothing broken**: the Stage S baseline checks (`research/ledger/SETUP.md`) give the same results.
- **Independent review**: a fresh reviewer that did not write the code audits this rulebook, the stimulation code and the
  aggregation for bugs and for any place where an outcome could have leaked into a modelling choice; findings are fixed
  and recorded (`research/ledger/reviews/`).

---

## 10. Data, seeds and environment fixed here

- Parameter seeds 0..15 (B1, B1-controls, B2, B3, B4, B5, B6); 0..63 for G3; control network seeds 101-105 and 201-205.
- Bootstrap 20261120; permutation 20261121; paired bootstrap 20261122; coupling null 20261123; G1 sample 20261124.
- Modal image: Debian slim, Python 3.12, numpy 2.5.3, scipy 1.18.1, pandas 3.0.6, pyarrow 25.0.1, pydantic 2.13.5,
  networkx 3.7, duckdb 1.5.5, google-crc32c 1.8.0, requests 2.34.2; `OPENBLAS_CORETYPE=Haswell`, single-threaded BLAS,
  NumPy AVX-512 dispatch disabled; image builder 2025.06.

---

## 11. Output tables (the next run joins on `manc_type`)

`research/ledger/predictions/<arm>/`: `types.csv` (`arm, network, manc_type, n_members, member_ids, n_replicates,
n_usable, mean_score, median_score, frac_ge_0_5, best_score, median_freq_hz, median_current, median_n_active_readout,
status, band, primary_score` plus arm-specific columns: A0/B0 `type_max`, `type_mean`; S `S1_direct_mn` ...
`S8_informed`; B4 `call_32`, `call_128`, `call_512` (values halts, speeds_up, slows_down, no_effect, no_effect_low_n,
background_not_rhythmic); B5 `score_I32`, `score_I64`, `score_I128`, `score_I256`,
`score_I512`), `replicates.parquet` (one row per type and seed), `legs.csv` (arms with per-leg output: `manc_type, leg,
score, frequency_hz, n_active, low_confidence`; `leg` in T1L..T3R or front/middle/hind), `config.json`,
`provenance.json`. Arm directories: `A1`, `A1-lo10`, `A0`, `B0`, `B1`, `B1-alt`, `S`, `B1-ctl-rewire-<seed>`,
`B1-ctl-classshuffle-<seed>`, `B2`, `B4`, `B5`.
Labels: `research/ledger/labels/` (`sources.csv`, `records.jsonl`, `synonyms.csv`, `driver_lines.csv`, `type_labels.csv`
with `manc_type, front, middle, hind, stop_call, walking_effect, best_preparation, best_specificity, n_records,
has_systematic, exposed, confidence, freq_hz`, `agreement.md`).

---

## 12. Amendments

An amendment is allowed only before the stage it affects has produced data, is versioned (`PREREG_v<k>.md` plus a row in
the changelog below), states its reason, and may not use information from the other side of the blind. A change to the
labeler kit after the freeze is versioned the same way (`kit_version`, `kit/CHANGELOG.md`).

| version | date | change | stage data existing at the time | labels existing |
|---|---|---|---|---|
| 1 | 2026-11-20 | initial | none (only DNg100/DNb08 pilot and calibration runs, and gate G3 on DNg100) | no |

---

## 13. Publication of the frozen tags

The pre-registration tag is pushed as soon as it exists. The predictions tag is timestamped (OpenTimestamps) when it is
created but pushed to the public repository only after the labels are frozen, so that no prediction table is reachable on
the web while labelers work (labeler web fetches to GitHub and Zenodo are also denied at tool level).
