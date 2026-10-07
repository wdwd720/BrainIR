# Post-lock drivers: ablations, counterexample search, robustness sweeps, counterfactual API, self-audit

Fork P3 of the critical-path plan (research/phase4/CRITICAL_PATH_PLAN.md, P3 / L3-L7). Everything here was built and dry-run BEFORE
the method lock with stand-in models: at small scale on the development tier, at FULL scale on the val tier (the constrained val
dry-run allowance, section 2, while the dev tier was rebuilt), the packed path on toyC and the real-system paths on 3 public real
systems (section 6). After the lock the same scripts run once on the confirmation tier and the real Level C sets, reusing the Level C
fits, and their summaries are ANSWER-BEARING. The method lock hashes the drivers (section 8
lists the files; `scripts/p4/method_lock_p4.py` must be updated to name all of them).

## 1. Files

| file | role |
|---|---|
| `scripts/p4/ablations_p4.py` | ablations (goal5 87-89), incl. the two critical ablations (Q20, Q21) |
| `scripts/p4/counterexamples_p4.py` | adversarial counterexample search (goal5 84, 91; Q19) |
| `scripts/p4/robustness_p4.py` | robustness dose-response sweeps (goal5 75; PROTOCOL 4.2 / 5.12 on finer grids) |
| `scripts/p4/counterfactual_p4.py` | counterfactual API evaluation (goal5 90) |
| `scripts/p4/self_audit_p4.py` | self-audit executor (goal5 91; SELF_AUDIT_PLAN.md Q1-Q21) -> research/phase4/SELF_AUDIT.{json,md} |
| `scripts/p4/p4post_iso.py` | entry points of the trusted iso "call" jobs (container side) |
| `scripts/p4/p4post/common.py` | hidden-data guard, run ledger, START / DONE log, system resolution, margins, Modal helpers |
| `scripts/p4/p4post/declare.py` | the ablation contract of `brainir_causal.api` (fails loudly) |
| `scripts/p4/p4post/pairstats.py` | paired statistics (PROTOCOL 11 conventions) and metric extraction from full evaluation results |
| `scripts/p4/p4post/execute.py` | fits / evaluations / custom jobs on the packed iso classes, results persisted as they arrive |
| `scripts/p4/p4post/isojob.py` | the trusted custom roles run in the iso container driver (method code only in model workers) |
| `scripts/p4/p4post/itemsets.py` | custom item sets (counterexample candidates, robustness grids) planned here, built by `suites.build_system_job` |
| `scripts/p4/p4post/levelc_io.py` | read access to the Level C run (P2's RunStore layout) and to LEVEL_B_FIXED.json |
| `scripts/p4/standin_methods/p3stand/refstand.py` | DRY-RUN stand-ins only (never a candidate, never in a room, not hashed) |
| `phase4/tests/test_postlock_drivers.py` | 37 tests (no Modal, no hidden data; one marked slow) |

## 2. Guards: nothing touches hidden data before the lock

- `common.guard(tier, real_level)` (the OFFICIAL rule, unchanged): before `research/phase4/METHOD_LOCK.json` exists AND
  `method_lock_p4.py --check` passes, the only admissible data are the dev tier, the toy tiers and the PUBLIC real data. The confirmation
  tier (`conf`) and the real hidden test (`real_level C`) require the lock; the Level B selection tier `val` is refused.
- VAL DRY-RUN ALLOWANCE (`common.val_dry_run_guard`, CLI `--dry-run-on-val`, self-audit config `"dry_run_on_val": true`; authorised
  by the orchestrator on 2026-09-27 while the dev tier's evaluation part is rebuilt), every condition enforced in code and tested:
  (1) pre-lock only (refused once METHOD_LOCK.json exists); (2) stand-in methods only: every method of the run must be registered in
  scripts/p4/standin_methods or scripts/p4/levelc_standin/methods (parsed, never imported) or be the frozen Phase 3 baseline, and the
  methods directory must BE a stand-in package or a byte-identical snapshot of one (the locked package phase4/src/brainir_causal/methods,
  a room or any modified copy is refused); (3) the val tier only, no real level (conf, real_levelc and every other hidden tier stay
  behind the lock exactly as before); (4) outputs marked dry-run (`dry_run`, a banner "not a result; never released, never used for any
  decision") and written only under research/phase4/postlock_dryrun/ and C:/Dev/BrainIR_p4run/postlock_dryrun/ (`RunDirs` refuses any
  other location for a dry run; the self-audit refuses a dry-run output outside them); (5) every run record carries `dry_run`,
  `dry_run_on_val`, the tier and the stand-in (`common.run_marks`); every summary repeats them (`marks_of`) under a DRY RUN banner
  (`dry_banner`). Tests: test_guard_refuses_hidden_tiers_before_the_lock (official run pre-lock refused; val refused without the flag,
  even for stand-ins), test_val_dry_run_allowance_is_narrow (stand-in allowed; non-stand-in, locked package, room directory, modified
  snapshot, other tiers, real levels and post-lock all refused), test_dry_runs_write_only_dry_run_locations_and_record_their_marks,
  test_self_audit_dry_run_output_must_be_a_dry_location, and END TO END per driver (each CLI up to its first Modal call, the backend
  replaced by a stop): test_every_driver_applies_the_val_allowance_and_records_its_marks[ablations / counterexamples / robustness /
  counterfactual] (official conf run pre-lock refused; val without the flag refused; a developer's method, the locked package, conf,
  dev and real C with the flag refused; nothing written by a refused run; the allowed run's RUN.json lies under the dry-run roots with
  the flag, the tier, the stand-in and the not-a-result mark; after the lock the flag refused) and
  test_self_audit_commands_apply_the_val_allowance_and_record_their_marks (prep / probes / run: the same refusals, official output
  locations refused for a dry run, SELF_AUDIT.{json,md} with the marks and the banner).
- Hidden-range parameter seeds of custom item sets come only from `itemsets.seed_function(hidden=True)`, which calls
  `suites.require_lock` and derives them from the salt exactly like the hidden test sets; dry runs use public-range seeds.
- Custom item sets are built into custom tiers `pl_<study>_<run>_<part>` on the EVAL volume (orchestrator-held, never public).
- Every hidden run writes a START row before anything is submitted and a DONE / FAILED row after, in
  research/phase4/HIDDEN_EVALUATIONS.md (the Level C driver's table: time | phase | run | what | detail), and claims its study in
  research/phase4/postlock/LEDGER.json: a second official run of a study is refused unless a reason is given and logged (goal5 70).
- Outputs: dry runs -> research/phase4/postlock_dryrun/<study>/<run>/ and C:/Dev/BrainIR_p4run/postlock_dryrun/<study>/<run>/ (bulky);
  post-lock -> research/phase4/postlock/<study>/<run>/ (ANSWER-BEARING, never into a room) and C:/Dev/BrainIR_p4run/postlock/ (bulky
  model bytes and full evaluations; not in git). A dry run can never write the official locations (`RunDirs`).
- Persisted failures: a job's own failure is a RESULT (never retried on resume, charged downstream); only infrastructure failures
  (`execute.INFRA_PATTERNS`, as the Level C driver's) are resubmitted when a run is resumed.
- Method code runs ONLY in unprivileged model workers of the isolated classes: fits through the iso role "fit", evaluations through the
  unchanged `harness.evaluate_job` (iso role "eval"), the custom per-item jobs through the iso role "call" (`isolation.resolve_iso_target`
  admits only modules of /repo/scripts/p4, i.e. `p4post_iso.py`), which run in the container's trusted driver and talk to workers only
  through `RemoteFresh` / `WorkerClient` / `fit_records` (safe codec; phase order A -> lift -> C). The driver never loads model bytes.

## 3. Execution (Modal)

- PACKED by default (`execute`): `Backend.run_iso_packed` on `iso_pack_fit` / `iso_pack_eval` (32 CPU, 8 slots each), one queue per
  class, longest expected first (real full networks, real mechanisms, synthetic; state-bottleneck variants first). Results are
  persisted as they arrive (`on_result`), so an interrupted wave resumes without recomputation; `--unpacked` falls back to one job
  per container.
- Packed-class rules (P1, 2026-09-27): a packed container reloads its volumes once, when its first input arrives, and never writes
  or commits. The drivers upload the method tar (`methods_key`) and build every custom item set (unpacked `build` class, committed)
  BEFORE the wave that reads it starts; the counterexample search opens a NEW app per round so no warm container of the previous round
  serves stale volume state. Custom item sets are built one system per `build` container (`suites.build_system_job`, host-gated).
- Every driver takes `--max-containers` (per class; default 40) so post-lock studies can share the ~100-container workspace with the
  Level C run.
- UNPACKED submission is EAGER (`execute.run_eager`, found in the val dry runs): one single-job `Backend.run` per job from a thread pool
  (at most the class cap + 4 in flight). `Backend.run` re-submits host-gate refusals only when its whole wave has ended, and a refusing
  container stops taking inputs, so in one large map every refused input waited for the slowest job of the wave (audit encodings: 20 of
  50 inputs refused in wave 1, re-submitted after 1,243 s; the counterexample round 1: 27 of 50 waiting behind one running job for
  over 30 min). A wave of one job re-submits at once. Unpacked fits are ONE tier (they may write the fit volume, so they carry
  `model_dir` from the start; a model within the inline limit still returns inline); a packed fit found too large leaves a
  `<fit>.too_large` mark so a resumed or repeated run sends it straight to the volume-writing tier.
- SIZE LIMITS (found in the dry run, app ap-PgsFEskiMNuKqxF1br5u7F): Modal sends a function input or output larger than 2 MiB as a
  blob that the container up- / downloads over the network, which the isolated classes block (block_network=True). Such a job fails
  AFTER its work, at output time (`ClientConnectorDNSError ... r2.cloudflarestorage.com`), and Modal's retries repeat the whole job. A
  full-state stand-in model is ~1.9 MB and an evaluation result of one small dev system 1.85 MB (1.6 MB of it the microstate
  equivalence per-pair units), so both cross the limit on larger systems. The drivers therefore run every job as an iso "call" of
  `p4post_iso.py` around the UNCHANGED benchmark functions (`isolation.fit_job`, `harness.evaluate_job`, `p4post.isojob`):
  - models larger than 1.5 MB never travel inline: a packed fit returns {"too_large"} (packed jobs never write volumes), the driver
    re-fits it on the UNPACKED class with `model_dir`, where the fit writes `/fitvol/p4post/models/<sha256>.bin` (committed) and returns
    the reference; the driver downloads it (sha256-checked). Evaluations and custom jobs read large models from that path
    (`ModelStager`: uploaded in ONE batch before the wave's containers start, content-addressed, never overwriting other files);
  - outputs larger than 1.5 MB are returned as an lzma-compressed pickle (the 1.85 MB evaluation compresses to 0.59 MB); if still too
    large, the microstate / bisimulation / lift per-unit payloads (never read by these studies) are dropped and listed; beyond that the
    job returns an error, never a truncated result.
  The same limit applies to the tournament and the Level C driver (section 8, first item). P1 (2026-09-27, after these drivers were
  built) keeps `block_network` on EVERY iso class, packed and unpacked, and is adding a platform-level staging of data above about
  1.5 MiB through a mounted volume by the trusted driver (`Backend.stage_put` / `stage_get`, `isolation.stage_blob`; workers never
  touch it). The drivers' own staging above is compatible with it (every payload they hand to the backend stays below the backend's
  pre-submission check; input models above 0.5 MB go by the fit volume, section 8 item 1) and can be retired once the platform staging
  covers the iso "call" role; until then a job with data above 2 MiB that bypasses both is expected to fail and is reported, not
  worked around.
- Uploads: `methods_key` (one file), `ModelStager` (single files under /p4post/models) and the custom item sets (the benchmark's builder
  writes only its own system directories of a `pl_*` tier) never replace a directory that holds other data.
- The dev tier's evaluation part was removed from the eval volume by an unrelated tier upload during these dry runs (2026-09-27; the
  orchestrator rebuilt the dev tier on the round-2 generator; interim tier released 2026-09-27 ~11:15 UTC, final rebuild announced).
  The full-scale dry runs therefore ran on the Level B val tier with stand-in models (`--dry-run-on-val`: admissible BEFORE the lock
  only, stand-ins only, outputs under postlock_dryrun; the guard refuses val at every other time). No run read the dev tier while it
  was being rebuilt; after its release only the family probe of section 8 item 11 read it.

## 4. Designs

### 4.1 Ablations (goal5 87-89; `ablations_p4.py`)

- Contract (`api.ABLATION_SWITCHES`, config `ablate`, info `ablation_switches` / `ablated`; `declare.py`): every switch of the
  vocabulary must be declared honoured or not applicable WITH a reason; unknown names, missing names, reasonless declarations and an
  ablated fit whose `info()["ablated"]` differs from the request stop the study (exit 3, nothing summarised). A fit that crashes is a
  method failure: recorded and charged in the statistics, never dropped.
- One wave of fits: the full fits (reused from the Level C run when `--levelc-run` is given: the same model bytes the confirmatory
  evaluation scored) plus a SPECULATIVE fit of every switch except `active_design` (declarations are only known from a fitted model;
  a speculative fit of a switch the system declares not applicable is discarded and counted, never evaluated), plus the comparators:
  the frozen Phase 3 method (`frozen_brainir_state_v1`, section 88: "should approximately recover the Phase 3-style regime") and the
  Level B best full-state baseline (section 89). Then one wave of full evaluations (every metric family, lift on).
- THE CRITICAL ABLATION (interventional training, section 88) is enforced at the DATA level too: the trusted driver hands the fit
  worker only the passive training records (every record with events and every twin dropped; `isojob.fit_passive` records the kept /
  dropped counts, the kept families and a sha256 of the kept keys), so the ablation holds whatever the method's own switch does; the
  switch is set as well and must be reported applied.
- `active_design` is loop-level (own designer vs the benchmark's random designer at equal budgets, PROTOCOL 5.17): taken from the Level C
  loops (self-audit Q10), not refitted.
- Statistics (`pairstats`): per switch and metric (EE verdict / held-out / target, post-intervention and passive NMSE, SMS, ICG_y, MEV,
  lift success and consistency, false confidence, coverage, k) the paired suite mean of (ablated - full) over the compressible synthetic
  systems (unstratified system bootstrap, 2,000 resamples; a missing value on one side is charged NEUTRALLY there, so a crashed ablated
  fit cannot make a component look important; counted), per real network the paired identity-cell EE difference; one-sided p "the
  ablation is worse", Holm across switches per metric. DESCRIPTIVE (not in the primary family).
- Q20 (critical; PASS rule fixed before the lock): removing interventional training worsens the verdict EE significantly: suite
  one-sided p <= 0.05 for mean(EE_ablated - EE_full) > 0. Missing values are charged AGAINST the claim: a crashed or missing ablated
  value neutrally (no evidence), a missing full-method value at its worst; no compressible synthetic system = NOT TESTABLE (never
  FAIL). FAIL = "Phase 4's core hypothesis fails". Abstentions count as "no effect" (PROTOCOL 5.1), so a passive-only model that
  abstains everywhere scores about as well as no effect: the interventionally trained method must beat that, which is the intended
  test (an abstaining passive-only model is exactly this case).
- Q21 (critical; operationalisation fixed here): DIRECT predicts = one-sided 95 % upper bound of the suite mean EE of the
  no-bottleneck variant < 1 - delta_A; COMPACT predicts near it = the same bound for the locked method AND the upper bound of
  mean(EE_M - EE_direct) < delta_C_suite (suite means charge a missing value at its worst; in the difference a missing value of the
  locked method is at its worst, a missing direct value neutral). Report "intervention outcomes are predictable, but compact causal abstraction unsupported"
  when DIRECT predicts and COMPACT does not; "the compact state suffices" when both; "not predictable even without the bottleneck
  (excitation / data; goal5 94 B)" when DIRECT does not. The same with the Level B full-state baseline in place of the direct variant
  is reported beside (section 89's comparison with the tournament's best full-state model).

### 4.2 Counterexample search (goal5 84, 91; Q19; `counterexamples_p4.py`)

- A COUNTEREXAMPLE: detectable true effect (ES_i >= 1), inside the model's claimed validity domain (`validity()["in_domain"]`; no
  validity reported = the model claims everything), not abstained, EE_i > 1 at the primary horizon (a failed prediction counts).
- Search per system, 50 evaluations: round 1 = 20 random genomes, rounds 2-3 = 15 children each of the 5 fittest so far (fitness =
  EE_i when eligible, else 0.5 min(EE_i, 1)); genome = family (supported: trained, held-out, hidden-only), targets / edges (public +
  held-out), magnitude 0.1-3 x moderate (the development range; clipped to the capability), onset 10-60 %, stimulus level, trajectory
  draw; realised by the benchmark's `FamilySampler.make` (valid protocols, development conventions). Gradient-free by design (the model
  is a black box in its workers).
- Per round: plan here -> build on Modal (twins, truth, onset states) -> `p4post_iso:predict_detail` (the benchmark's item scoring, per
  item EE_i / ES_i / validity / abstention). PASS (fixed before the lock): counterexamples on at most 50 % of the compressible
  confirmation systems. Systems whose search had fewer evaluations than the budget (build / evaluation failures) are listed.
- Review G's new trap families (section 84) are new SYSTEMS: once built as a tier, the same driver searches them (`--tier`); their
  standard evaluation belongs to the Level C / tournament drivers.

### 4.3 Robustness sweeps (goal5 75; `robustness_p4.py`; descriptive)

- The Level C evaluation reports every PROTOCOL 4.2 condition at two levels (5.12). This study adds dose-response curves on finer grids:
  parameter noise (spread 1.25-2.5), weight noise (sd 0.025-0.15), process (trajectory) noise (0.025-0.2, where supported), observation noise
  (0.025-0.2), untold intervention-amplitude jitter (+-10-50 %), untold timing jitter (+-1-8 samples), plus a nominal anchor; 8 in-family items
  per (condition, level) and system. A condition a system's capability does not support is skipped and recorded (process noise on
  the real systems). On the real systems the builder clips many kick magnitudes to the capability and relabels their class
  (real:A:full: 15 of 23 kick items clipped in the dry run), so amplitude jitter is partly absorbed there; the build counts
  (`kick_clipping`) are kept in the run record.
- Per (condition, level): suite means (system bootstrap) of pooled EE, abstention, predicted sd and realised RMS error (readout-sd
  units), validity score, false-confidence rate; per condition the sd and error ratios to nominal, their log-log slope and the flag
  UNCERTAINTY FLAT (error up > 50 % at the largest level while sd up < 10 %, or no sd reported): "uncertainty should increase
  appropriately".

### 4.4 Counterfactual API (goal5 90; `counterfactual_p4.py`)

- On every intervention item of the tier (verdict, OOD, robustness roles) the model's `intervention_effect` is called in workers
  (histories up to the onset only) and scored against the simulator; phase C re-encodes the true futures for the latent trajectory.
- COMPLETENESS (per field, share of probed items well formed; complete = >= 95 % on every system): future under a (y_int), y_base,
  effect == y_int - y_base, uncertainty (y_sd or an uncertainty record), validity (in_domain + score), latent trajectories z_int /
  z_base (shape, finite), the abstention flag.
- ACCURACY (suite means, system bootstrap; descriptive): EE (verdict, pooled), post-intervention NMSE, realised RMS error, sign
  accuracy; 90 % interval coverage and calibration error per horizon, Brier scores, rank correlation of predicted sd with error;
  validity AUC and EE inside vs outside the claimed domain; ICG_y (the latent trajectory against re-encoded true futures); coverage and
  false confidence.

### 4.5 Self-audit (goal5 91; `self_audit_p4.py`)

`probes` runs the custom probes on the method's fits (memo_probe on 8 synthetic systems + the real networks: Q4 a / b; encodings on
every system: Q5; readin_probe on synthetic systems: Q7; lift_jitter on every system: Q8 / Q9); `run` evaluates Q1-Q21 with the pass
rules of SELF_AUDIT_PLAN.md (operationalisations fixed in the script's docstring) from the Level C run, the post-lock studies and the
probes, and writes SELF_AUDIT.{json,md}. A missing input makes a check NOT_TESTABLE (never PASS); an untestable sub-condition makes it
PARTIAL. `prep` (dry runs, or documented gaps post-lock) fits / evaluates missing roles and the method's bootstrap refits.

| Q | inputs |
|---|---|
| Q1-Q3, Q14 | the method's and the ID / input-only / readout-history / linear-controlled comparators' Level C evaluations (roles) |
| Q4 | memo_probe (a, b), the fit / evaluation isolation records (c: tripwire hits, fatal workers), an AST audit of the locked source (d) |
| Q5, Q7, Q8, Q9 | the probes (encodings, readin_probe, lift_jitter) |
| Q6, Q11, Q12, Q13, Q15, Q17 | the Level C evaluations (SMS_x_res / ICG_y; per-item scores; far / in EE; refit k; the full-state bound; verdicts) |
| Q10 | the PROTOCOL 5.17 loops summary (designer vs magnitude-matched random) |
| Q16 | the calibstats compare of the confirmation suite |
| Q18 | the PROTOCOL 5.14 sharing results on unrelated pairs |
| Q19, Q20, Q21 | the counterexample and ablation studies |

## 5. Stand-ins (dry runs only)

`scripts/p4/standin_methods/p3stand/refstand.py`: `p3stand_ref` = the benchmark's PCA-k reference learner (small training budget)
wrapped as a method with contract-following FAKE switches: honoured interventional_training (passive records only), mediation_loss
(the effect-calibration term off), closure_loss (the paired multi-step phase off), native_lift (no lift), multiple_lift_consistency
(one lift candidate), dimension_penalty (k from 99.9 % instead of 95 % explained variance), state_bottleneck (the FULL-STATE learner);
not applicable with reasons: active_design, history_delay, uncertainty_ensemble, shared_dynamics. `p3stand_broken` declares the same
but applies nothing (negative test). Baseline stand-ins: `p3stand_fullstate`, `p3stand_idshortcut` (the ID-shortcut reference, which
reads the readout history only when the harness registers it, so as a worker-side "method" it is a weak stand-in), `p3stand_noeffect`.
The frozen Phase 3 method (`frozen_brainir_state_v1`) is the Phase 3 comparator and the second negative test (it declares no
switches).

## 6. Dry-run results

Operational numbers only. The val runs used the VAL DRY-RUN ALLOWANCE (section 2): stand-in methods, before the lock, outputs under
research/phase4/postlock_dryrun and C:/Dev/BrainIR_p4run/postlock_dryrun only; their metric values are not results, are never released
and are used for no decision, so none is quoted here or anywhere else. Costs: "billed" = the workspace billing report (complete hours);
"list" = the drivers' own estimate from container seconds (for PACKED classes it prices every slot at the whole 32-CPU container's rate,
up to 8 x too high). Every app is listed in research/phase4/MODAL_RUNS.md (rows P3-1 to P3-45).

Development tier (before the dev evaluation part was lost), unit and negative tests at small scale:

| run | tier / scale | app id(s) | wall | cost | outcome |
|---|---|---|---|---|---|
| ablations smoke1 (unpacked, pre-refactor) | dev, 1 system: full + 3 switches + full-state baseline | ap-GZmsBYBW9RU0SuSoTZOulJ | 1,920 s | $0.54 list | 5 fits + 5 full evaluations, 0 failures; one host refusal delayed an evaluation by 865 s (wave re-submission) |
| ablations neg_broken | dev, 2 systems, `p3stand_broken` | ap-uGP4E2Fqlf6dTrUVK7EmSw | 302 s | $0.68 list | exit 3: "requested but not applied" for every honoured switch (as designed) |
| ablations neg_frozen | dev, 2 systems, `frozen_brainir_state_v1` | ap-Av0MsL2cWsBixqIXm3qnBs | 563 s | $1.52 list | exit 3: "info()['ablation_switches'] is missing" (as designed) |
| ablations dry1 / dry1b, audit prep (stopped) | dev, 50 systems | ap-PgsFEskiMNuKqxF1br5u7F, ap-Yc18pAUqXllGBjrzMOt55c, ap-9PXB0vQsYwKAtypvtcSkxs, ap-yiKrOmicWfU5VkRheum0Ye | minutes | billed in MODAL_RUNS.md | found the 2 MiB limit (section 3); then the dev evaluation part vanished from the eval volume; moved to val |

FULL SCALE on the val tier (50 synthetic systems; the val tier has no real systems) and the packed path on toyC:

| study (run) | scale | final app id(s) (earlier attempts in MODAL_RUNS.md) | wall of the final run | cost | outcome |
|---|---|---|---|---|---|
| ablations (val1) | 50 systems x (10 speculative switch fits + full + 2 comparators) = 650 fit jobs (150 not-applicable fits discarded, as designed), 500 full evaluations (10 variants, lift on) | fits: ap-rMBvYdY8tMn16V2GWCDRB3 (attempt 1), ap-ltAWM55pBzukSTrx9MUzDK (the 98 large-model fits, 937 s); evaluations: ap-QwQU4NVOfQMdIlRzehoMVf | 6,070 s for the final run (500 evaluations in 5,962 s on 56 containers, 102 host refusals); the fits ran in P3-8 (packed) and P3-29 (the 98 large-model fits, 937 s) | $36.99 billed (final run; $36.05 list) + $13.28 (P3-8) + $3.81 (P3-29); all attempts $56.80 billed | 0 fit, 0 evaluation failures, 0 contract problems; the 150 not-applicable speculative fits (history_delay, shared_dynamics, uncertainty_ensemble, as the stand-in declares) discarded; ABLATIONS.{json,md} with the DRY RUN banner (summary 24 s after the read cache; 3.5 min before) |
| counterexample search (val1) | 50 systems x 50 candidates (rounds 20 / 15 / 15) = 2,500 built and scored candidates | ap-s7LypHqSttav9fMdof6jrE, ap-5O1WsU0S8r2QK00jieswBE, ap-arBhdX0y9wj8AGEKT6w24Q (one app per round) | 1,343 s (rounds: build 109 / 79 / 80 s, scoring 290 / 364 / 371 s; round 1 reused 23 scorings of attempt 3) | $4.55 billed ($2.88 list); all attempts $8.14 | 0 plan, build, simulation or scoring errors; summary written with the DRY RUN banner |
| robustness sweeps (val1) | 50 systems x 27 condition-levels x 8 items = 10,800 items (6 conditions of goal5 75 + nominal) | ap-P5RvGY6MVLO0tlvfnLvEk0 (wave-based, 8 containers per class) | 4,152 s (builds 1,731 s, 7 refusals; scoring 2,402 s) | $6.99 billed ($6.46 list); all attempts $8.68 | 0 build errors, 0 scoring errors |
| counterfactual API (val1) | 50 systems, every intervention item + phase C closure | ap-QJzxoi0bKsmOzm4Xe3KOjZ (40 jobs, packed, attempt 1), ap-6kAVvmwdCeM6Wo3L8Bto2B (the last 10) | 489 s (the last 10 jobs) | $0.36 billed (the last 10) + $2.92 (P3-10); all attempts $3.91 | 0 errors |
| self-audit probes (val1) | memo_probe 8, encodings 50, readin_probe 50, lift_jitter 50 | ap-VHOVX4c0kQQyTLV4rJLkp9 (memo), ap-yJIuqpDGpdjI6KGuBhlDlK (encodings, 2,755 s wave-based), ap-UwPbD4qwVgPti6KXz2cnV5 (readin 722 s, lift_jitter 1,523 s) | 2,245 s (final run) | $2.56 billed (final run; $2.33 list); all attempts $6.83 | 1 error in lift_jitter: the benchmark's own lift family fails on val system syn-0963ac95e081 for every method (section 8 item 13) |
| self-audit prep (val1) | 100 role fits (ID-shortcut and no-effect stand-ins), 250 method bootstrap refits, 100 role evaluations | ap-WZb7498CXpN2PwJFgpJLmM (attempt 1: 90 fits), ap-PpzyfIdhwd5cF47Kj02mdL (refits), ap-OkuAZNjcWoCgJRwaNE4uvj (55 fits + 100 evaluations) | 4,740 s (fits 884 s: 55 new, 9,243 container-s; evaluations 3,845 s: 100, 41,145 container-s; 12 containers) | $6.21 billed ($5.89 list); all attempts $15.71 | 0 fit and 0 evaluation failures (100 + 100); the 250 refits of attempt 3 reused |
| self-audit run (val1) | Q1-Q21 from the studies, the probes and the role evaluations | local | 14.7 s | - | 19 of 21 checks evaluated with all their inputs present; Q10 and Q18 NOT_APPLICABLE by the stand-in's declarations (no designer; shared dynamics not applicable); no check crashed; SELF_AUDIT.{json,md} under postlock_dryrun with the marks and the banner |
| PACKED path (toyC_packed1; not val) | toyC, 2 systems: full + interventional_training + state_bottleneck + both comparators (10 fits, 10 full evaluations) | ap-8bEo6FhGPFVr7srD4L4dUM (describe + 10 packed fits, 389 s, 0 refusals), ap-qipudRDExf1OEoUytdcT7w (10 packed evaluations) | 1,333 s | $0.58 + $2.28 billed ($11.15 recorded list: the packed overcount, section 8 item 15) | 0 failures: describe, packed fits, models > 0.5 MB by the fit volume, packed full evaluations, summary |
| REAL-SYSTEM paths (realpub1; not val) | 3 public real systems (real:A:full, real:A:m1, real:B:m1): ablations (the two critical switches + both comparators: 15 fits, 15 evaluations), counterexamples (budget 20: 60 candidates), robustness (46 items per system; process noise not supported by the real capability: skipped and recorded), counterfactual (3), probes (memo_probe on the full network, encodings 3, lift_jitter 3), self-audit run | ap-EBGPl47wecESUw3efQUWmd, ap-uOrS66FiRPiSdnbD9zvKdw, ap-cKEi3CU5OlgsGIwbCYpiRw / ap-FZbI1zbK8PuXXrccfZPEXp / ap-9UpBcnGT4KFYoTPReKgyt4, ap-2Jx9VWYdE3gWE75mqmVx35, ap-6JPe93rHUqIpotR6h5IfJc | ablations 2,957 s (fits 870 s on iso_fit_m, evaluations 1,968 s on iso_eval_l, mean 856 container-s); counterexamples 1,768 s; robustness 1,150 s; counterfactual 465 s; probes 2,611 s; audit < 1 s | $6.55 billed together | 0 failures in every study: iso_fit_m / iso_eval_l, real builds (the full network's 92 records in 484 s), the passive-only data rule and the full-state model on real data |
| family probe on the INTERIM dev tier (round-2 generator; after the coordinator's release) | 4 dev systems x 21 supported families, one item per build | ap-rH7r2rMsmx6JJ5fvOh7JHz | 87 s | not yet billed (11:00Z hour) | 84 of 84 builds pass, including the silence families, param.1 and the compositions: section 8 item 11 is resolved by the round-2 generator |

Measured per-job container time (val, stand-in `p3stand_ref`, 4-CPU slots): full evaluation with lift (ablations) median 481 s, p90
578 s, max 852 s harness wall, 584 s mean container time (500 jobs); real (realpub1, iso_eval_l) 856 s mean container time; counterexample scoring (15-20 items) median 48 s, mean
138 s; robustness scoring (216 items) mean 331 s; counterfactual job mean 304 s; probes: encodings 223 s, memo_probe 454 s, readin_probe
133 s, lift_jitter 271 s (means); custom item-set builds 251 s per system (216 items), 17-24 s (15-20 items). Host-gate refusals: up to
192 per 98 jobs in one burst (eager fits); the eager submission re-submits each at once.

## 7. Projected post-lock wall time

Post-lock scale: the confirmation tier (about 75 synthetic systems) plus the real Level C systems (10: 3 full networks, 7 mechanisms),
about 85 systems. The studies start when the Level C primary fits exist (they reuse them, and the Level C evaluations of the full method
and of the baselines), and run concurrently with the rest of Level C inside the ~100-container workspace. Per-job times below are the
stand-in's (val) and, for the real systems, the Level C dry runs' (full network evaluation about 1,500 s, mechanism about 1,100 s);
the locked method's own fit / evaluation times scale every figure about linearly.

| study | jobs | container time | wall, PACKED (40 packed containers = 320 slots) | wall, unpacked (56 containers) |
|---|---|---|---|---|
| ablations | up to 850 speculative fits + 7-10 honoured switches x 85 evaluations (600-850) | 145-220 h | 45-55 min (the long pole; real full networks first) | about 3.5-4 h |
| counterexamples | 3 rounds x 85 systems (builds + scoring) | about 11 h | about 25 min (3 sequential rounds of ~8 min) | about 25-30 min |
| robustness | 85 builds (216 items each) + 85 scorings | about 14 h | about 20-25 min | about 25-30 min |
| counterfactual | 85 jobs | about 7 h | about 10 min | about 10-15 min |
| self-audit | probes about 330 jobs (4 roles in sequence); run: local, minutes | about 16 h | about 25 min | about 30 min |

Total about 195-270 container-hours (about $90-125 at the val run's billed rate of $0.46 per 4-CPU / 32 GiB container-hour, with
stand-in-like job costs; the val ablation run: 81 container-hours, $36.99 billed). WALL: about 1 h after the Level C
primary fits exist when the studies get about 40 packed containers (the ablation evaluations are the long pole; the other four studies
fit inside it), about 4 h if they must run unpacked on about 56 containers. The critical-path plan's "L3-L7 concurrently with L2"
therefore holds only on the PACKED classes; the drivers default to them (`--unpacked` only for small runs or when the packed path is
unavailable). Margins: host-gate refusals (the admissible pool can be scarce, section 8 item 7) and the packed wave tail (item 7).

## 8. Hooks, gaps and interfaces (for the orchestrator)

1. PIPELINE-WIDE size limit (P1's area; status 2026-09-27 ~09:10 UTC). Every iso class is block_network, so a function input or output
   above 2 MiB cannot move. P1 is adding platform staging (`Backend.stage_put` / `stage_get`, `isolation.stage_blob`) and a
   pre-submission check (`p4modal.app._check_inline`). Two points found by the toyC packed smoke (ap-8bEo6FhGPFVr7srD4L4dUM), for P1:
   (a) `_payload_bytes` sizes the iso "call" role's `models` bytes through `json.dumps(default=str)`, i.e. by their repr (about 3.6 x
   their length): a 1.14 MB full-state model was refused as "4076497 bytes inline", and any model above about 0.56 MB in a call
   payload is refused although the payload is well below 2 MiB. Bytes at any depth should count by their length. (b) The staging
   covers the roles fit / eval / loop (`model_ref`, `result_ref`, `file_refs`); the "call" role still takes its models inline only.
   The drivers therefore keep their own staging for call jobs: input models above `common.MODEL_INLINE_MAX` (0.5 MB, below the
   estimate's threshold; raise it once (a) is fixed) go through the fit volume (`ModelStager`, `job["model_path"]`, read by the
   trusted container side only), fitted models above 1.5 MB come back through the fit volume, outputs above 1.5 MB lzma-compressed
   (below `isolation.MAX_INLINE_OUTPUT`). Until the platform staging covers everything, a job carrying more than 2 MiB that bypasses
   both is expected to fail and is reported, not worked around.
2. `scripts/p4/method_lock_p4.py` POSTLOCK_SCRIPTS names `scripts/p4/self_audit.py` (the executor is `self_audit_p4.py`, as in
   SELF_AUDIT_PLAN.md) and silently skips missing files. It must hash `scripts/p4/ablations_p4.py`, `counterexamples_p4.py`,
   `robustness_p4.py`, `counterfactual_p4.py`, `self_audit_p4.py`, `p4post_iso.py` and every `scripts/p4/p4post/*.py`, and fail when a
   listed driver is missing. (Still open.)
3. LEVEL_B_FIXED.json has two locations: `method_lock_p4.py` reads research/phase4/tournament/LEVEL_B_FIXED.json, the Level C driver
   (`levelc_lib.LEVEL_B_FIXED`) and `p4post.levelc_io` research/phase4/LEVEL_B_FIXED.json. One must be chosen before the lock. (Open.)
4. Level C interface (P2's RunStore, read by `p4post.levelc_io`): results/<job id>.pkl and models/<job id>.bin with the ids
   fit__<sid>__s<seed>, refit__<sid>__b<b>, eval__<sid>, bfit__/beval__<sid>__<baseline>, refs__<sid> (levelc_lib.build_plan as of
   2026-09-27); a rename there must be mirrored. The Level C run must include as baselines the self-audit's comparator roles (the best
   ID baseline, an input-only, a readout-history and the best linear controlled baseline, the full-state baseline) and the frozen
   Phase 3 method (section 88's comparison), or Q1-Q3 / Q14 and the Phase 3 regime row are NOT_TESTABLE. The ablation study reuses the
   Level C primary fits and evaluations (`--levelc-run`), so its full-method rows are the confirmatory ones.
5. research/phase4/SELF_AUDIT_CONFIG.json must be written at the lock (roles -> Level B names or `fixed:` choices; the Level C loops
   summary (Q10), sharing results (Q18) and the confirmation suite's calibration compare (Q16) paths; the post-lock study directories).
   `research/phase4/postlock_dryrun/self_audit/val1/CONFIG.json` is the dry-run template (directory roles instead of Level C roles).
6. Q8 exactness hook (pre-freeze, evaluator code): `evaluate_lift.eval_native_lift` keeps request-level units only; with per-lift
   records (events and success) in `res["_units"]["lifts"]`, Q8's saturation share would be computed over successful lifts exactly
   (`isojob.lift_jitter` reads it when present). Until then it uses every simulated candidate (a conservative proxy; labelled).
7. HOST GATE x WAVES (P1's `Backend.run` / `run_packed`). A refusing container stops taking inputs, but `Backend.run` re-submits refused
   inputs only after its whole wave, so a large map loses most of its throughput to the wave tail when many hosts are refused (val dry
   runs: audit encodings 20 of 50 refused in wave 1, re-submitted after 1,243 s; readin_probe 46 of 50 refused in wave 1; the
   counterexample round 1 had 27 of 50 inputs waiting behind one running job for over 30 min). The drivers' UNPACKED path submits
   eagerly (`execute.run_eager`: one single-job map per job; round 1's 27 waiting evaluations then took 290 s). The PACKED path
   (`run_iso_packed` -> `run_packed` -> `run`) still has the wave tail; an eager `run_packed` would remove it (P1). Refusal rates were
   high on 2026-09-27 around 09:00 UTC (the eager ablation fits: 192 refusals before the 8th of 98 fits completed): the admissible host
   pool (no AVX-512) is a capacity risk for every post-lock campaign and belongs in the schedule's margins.
7b. Packed isolation failed closed from P1's network change until P1 restored block_network on every iso class (apps
   ap-YorY01QBjnMs8Q4LydeNyd, ap-Nw2ucHqpaMT5mAXet3mvBN refused every packed job: "packed isolation needs per-worker
   user/network/IPC namespaces ... worker_interfaces 'eth0,lo'; refusing to run model workers"). Since the restore the packed path
   works for these drivers: the toyC packed smoke ran describe (3 jobs, 76 s) and 10 packed fits (389 s, 0 refusals) on iso_pack_fit.
8. A packed container bills all 32 CPUs: small runs are expensive when packed (the 2-system negative runs cost $0.68 and $1.52); use
   `--unpacked` for runs of a few jobs.
9. `active_design` is ablated through the Level C loops (Q10: own designer vs random and magnitude-matched random), not re-run here.
   Review G's new trap families are new systems: once built as a tier, the counterexample driver searches them (`--tier`).
10. Answer-bearing outputs: research/phase4/postlock/** and the post-lock SELF_AUDIT.{json,md} belong on the room builder's
    refuse-list with the rest of research/phase4 (the dry-run outputs under postlock_dryrun stay out as well; the val dry runs' outputs
    are never released and never used for any decision). A dry run's custom item sets are built into their own tiers (`pl_dry_*` from
    this version on; the val dry run's tiers are `pl_ce_val1_*` / `pl_rb_val1_grid`), so an official run never reads items a dry run
    built.
11. GENERATOR: with the generator in the repository before its round-2 revision, the benchmark's own builder
    (`suites.build_system_job`, host-gated build class) REFUSED new items of the silence families (sil.1, sil.2, sil.g, sil.1p), of
    param.1 and of some compositions on the val systems: "x / y differs from the twin at sample i (onset sample i): the sample at an
    event's time must be the pre-event state" (a per-family probe, 4 val systems x every supported family, app
    ap-rb641don00Oe9y00sJqAZ8: sil.1 0/4, sil.g 0/4, sil.2 1/4, sil.1p 1/4, param.1 0/4, comp.seq 3/4, comp.sim 3/4). The val dry runs
    therefore excluded those families (`--exclude-families`, recorded in each run record). RESOLVED by the round-2 generator: the same
    probe on the INTERIM dev tier (app ap-rH7r2rMsmx6JJ5fvOh7JHz) passes 84 of 84 builds (21 families x 4 systems). The post-lock runs
    (conf built with the final generator) must not need the flag; the final dev tier should be probed once more (the probe script is
    fork P3's scratch helper, and a counterexample run without `--exclude-families` does the same at scale).
12. Windows client: the eager submission holds about 3 TCP connections per job in flight (Modal's input plane opens a channel per map;
    the "Unclosed connection" warnings are Modal's); six concurrent wave-based drivers exhausted the socket buffers once (WinError
    10055, the counterfactual val attempt). Run at most four drivers from one Windows client at once, or run them from a Linux host.
13. VAL DATA (Level B's selection tier; for the orchestrator): on val system syn-0963ac95e081 the benchmark's own lift family fails
    for EVERY method: "ProtocolError: r0 'restart' must come from a trajectory of the same system" (`suites.check_restart_source`: the
    stored restart-source record of a lift case carries another system hash or system id than the system's current internal record;
    the val internal records hold no duplicate system hash, so a stale store record from an earlier build of this system is the
    likely cause). Seen in every ablation variant's evaluation of that system and in the lift_jitter probe. The harness records it as
    the lift family's error, so Level B's lift metrics on val silently lack this system unless the eval part of this system is
    rebuilt (or its lift cases' store records checked) before Level B uses lift.
14. Review G's trap tier (goal5 84): the guard admits only the tiers it knows (`PRELOCK_TIERS` dev / toy / toyC, `HIDDEN_SYN_TIERS`
    conf). A new trap tier must be added to one of them (hidden, i.e. after the lock; or a pre-lock review tier if review G runs the
    counterexample search itself before the lock: the orchestrator's decision), or every driver refuses it as an unknown tier. It must
    follow the suites layout (data/phase4/suites/<tier>/_plan/jobs.json with the reference-platform records; eval part on the eval
    volume), as `plan_records` reads it.
15. Cost records (P1's `Backend._cost`): on packed classes every job's container seconds are priced at the whole 32-CPU container's
    rate, so a packed run's recorded list estimate overstates its cost by up to the slot count (toyC packed smoke: $11.15 recorded;
    MODAL_RUNS.md P3-33 has the billed figure). P2's Level C records divide by the slots; the Backend should do the same (or record the
    container's wall once per container).
