# Level C driver (causal_state_v1; post-lock confirmation): design, guards, dry runs, projected wall time

Orchestrator side; P2 of research/phase4/CRITICAL_PATH_PLAN.md (L1-L2).

## Files
The method lock hashes these three scripts, plus LEVEL_B_FIXED.json and SELF_AUDIT_CONFIG.json:
- `scripts/p4/level_c.py`: the command-line interface;
- `scripts/p4/levelc_lib.py`: the job graph, the executor, Stage D and the guards;
- `scripts/p4/levelc_remote.py`: container-side functions, run through the iso role "call".

Also:
- dry-run stand-in method: `scripts/p4/levelc_standin/` (`levelc_standin_pca`);
- dry-run DUMMY trap catalog: `scripts/p4/levelc_standin/dummy_trap_catalog/review_g.py`. It relabels two public generator types and is
  NOT review G's catalog. Review G's catalog is `research/phase4/review_g/review_g.py`: hashed by the method lock and baked only into
  official runs;
- tests: `phase4/tests/test_level_c_driver.py` (45 tests, no Modal; a HOST_ONLY file, run locally and alone).

Dry runs use the dev tier, the public real data and the toy tiers only (section 6).

## 1. Commands

    # before the lock (never touches hidden data; --dry-run-dev maps conf -> dev, real Level C -> the real public evaluation subset)
    level_c.py plan --dry-run-dev [--sample smoke|ten|full] [--systems ...] [--no-toy] [--no-loops]     # job graph, no Modal
    level_c.py run --dry-run-dev --run-id D1 [--sample ...] [--with-audit-roles] [--unpacked] [--max-containers N]
    level_c.py claims|report|project --dry-run-dev --run-id D1 [--also-runs S2,S3] [--target official]
    level_c.py run|claims --dry-run-dev ... --trap-standins <dev ids>    # dev systems as the trap set (claims: a claims_traps/ variant)
    level_c.py trap-probe                                                # the trap tier's image path with the DUMMY catalog (Modal)
    level_c.py run ... --auto-resume 2                                   # relaunch (same run id) when the Modal client dies (exit 75)
    level_c.py prewarm                                                   # build every Modal image (before the lock)
    level_c.py fixed-from-levelb --round <final Level B round>           # research/phase4/LEVEL_B_FIXED.json
    level_c.py self-audit-config --method <locked name> --run-id C1 --role id_baseline=<n> --role input_only=<n> \
        --role readout_history=<n> --role linear_controlled=<n>        # research/phase4/SELF_AUDIT_CONFIG.json
    # after the lock (refused before; START / DONE rows in research/phase4/HIDDEN_EVALUATIONS.md; LEDGER.json run-once)
    level_c.py run --official --run-id C1
    level_c.py claims --official --run-id C1 --levelb-round <final round dir>

(Every command is `uv run --no-sync --project phase4 python scripts/p4/level_c.py ...`.)

The run is one resumable process:
- every finished job is stored under $P4_RUN_BASE/levelc[_dry]/<run>/ (default C:/Dev/BrainIR_p4run; results/, models/, loops/,
  refs.json, jobs.jsonl, interruptions.jsonl);
- a restart with the same run id skips finished jobs and re-runs stored infrastructure failures only;
- a dead Modal client stops the process at once with exit code 75, and nothing in flight is stored (section 5). `--auto-resume N` is a
  supervisor process without a Modal client: it relaunches the run at most N times, only on exit code 75, after `--resume-wait-s`
  (default 120 s);
- claims (Stage D) runs locally from the stored results and can be repeated without Modal.

## 2. Stages

### Stage A: hidden data (official only; after the lock)
- **Confirmation tier:** 25 types x 3, salted. Planned on the reference platform: `build_on_modal.plan_on_reference_platform("conf")`, the pinned image with the salt read-only.
- **Review G's trap tier** (goal5 sections 41 / 84, criterion 33; LOG P4-D50): salted, built only after the lock (`suites.LOCKED_TIERS`).
  - It is planned on the reference platform with `plan_on_reference_platform("trap")`, which also mounts review G's catalog.
  - Its tier files go to `data/suites/trap` on the eval volume, and a trap id that clashes with a confirmation id is refused.
  - Its systems are built in the same job graph.
  - The catalog FILE alone (`research/phase4/review_g/review_g.py`) is staged and baked at `/repo/research/phase4/review_g`, the path
    `synthadapter.trap_catalog_path()` resolves in every image. It is root-only in the iso images, into which the build, reference
    and evaluation images all load it. `official_guard` requires the lock to hash the catalog and the catalog to match that hash.
- **Real Level C sets:** hidden test, family shift, OOD and robustness, planned with `suites.plan_remote_job("real", sid, level="C")`.
- **Tier files:** uploaded to the eval volume (merging, never replacing).
- **Builds:** one `build` job per system (`suites.build_system_job`) inside the job graph. The build manifests (`research/phase4/build_manifests/syn_conf_*.json`, `syn_trap_*.json`, `real_C_*.json`) and the build records are written at the end.
- **OOD families (4.1) and robustness conditions (4.2):** part of the level-C build design. This covers:
  - the state-carrier altered initial conditions;
  - the sampling shift.
- **Barrier:** on the packed classes every Stage B / C job waits for every build, because a packed container reloads the volumes once, at start.
- Both planners refuse before the lock (`suites.require_lock`, tested).

### Stage B: fits (model bytes return to the orchestrator and are never loaded there)
| job | count | notes |
|---|---|---|
| fit | 5 per system (seeds 0-4) | seed 0 = the primary fit; seeds 0-4 for 5.11 (METHOD_LOCK "seeds") |
| refit | 5 per system (bootstrap b = 0-4, seed 0) | 5.10, criterion F (`isolation.bootstrap_interventions`) |
| bfit / beval | 1 per baseline and system | See the list below. |
| loio_fit | 1 per trained intervention family | 5.13 (`evaluate_transfer.loio_datasets` in `levelc_remote.fit_records`) |
| limpo_shared / adapt / scratch | per implementation group x held-out member | 5.14. Shared fit on the others (sharing "shared"). Adaptation (adapt_from) and scratch fits use 25 % of the held-out member (`limpo_subsample`, seed 0). |
| share_fit | per group x shared model (B "shared", C "partial") | 5.14. Model A = the per-system fits. Model D has no CONFIG_KEYS value. |
| refs | 1 per system (trusted) | all references incl. TRUE-STATE; RANDOM-k / PCA-k with the primary fit's k |

The baselines of the run:
- S;
- a full-state or ID baseline when one is the Level B-fixed bound or comparator;
- every "baseline:<name>" role of SELF_AUDIT_CONFIG.json (the ID, input-only, readout-history and linear-controlled comparators);
- the frozen v1 (the Phase 3 comparator).

The 5.14 units are every implementation group with at least 2 members, plus one unrelated-pair NULL per group. The null's correct sharing verdict is "rejected". The hard gate is applied in Stage D.

TRAP systems (set "trap") run the verdict stages only (`levelc_lib.TRAP_STAGES`):
- the primary fit (seed 0), the 5 bootstrap refits (criterion F), the baselines, the references, the evaluation and the same-items row;
- 5.11 stability, 5.13 LOIO, 5.14 sharing and the 5.17 loops are defined on the confirmation suite and the real systems, so a trap
  system is never a 5.14 unit or a null partner and has no loops.

### Stage C: evaluation
| job | count | what |
|---|---|---|
| eval | 1 per system | every metric family (`harness.evaluate_job`): items with OOD, robustness, composition and calibration; mediation, micro, truth with k-consistency and d_draw, capacity, lift, closure |
| beval | 1 per baseline and system | the same for each baseline |
| stability | 1 per system | 5.11 over the 10 models (`levelc_remote.stability`) |
| calib | 1 per compressible synthetic system | P_t and P_m - P_t on ONE item set: `calibrate_from_inputs(extra_models={"method": RemoteFresh})`, with the method's Level C dimension (5 refits) |
| loio_eval / limpo_eval / share_eval | per unit | item-subset EE (and SMS) of the models concerned (`levelc_remote.eval_items`) |
| loop | systems x 9 designers x 3 loop seeds | 5.17: own, random, uniform, magnitude_sweep, greedy_error, structural, passive, fixed, random_matched. Budget 200 (real full networks 100). random_matched waits for the own loop of the same seed. |
| ckpt | 1 per loop checkpoint | EE, SMS, k-consistency, lift success (families items, mediation, truth, lift) |

### Stage D: claims (local; frozen functions only)
- **Per-system verdicts:** `harness.assemble_verdict` / `system_verdict_for`, with:
  - the frozen tolerances (provisional ones are flagged);
  - the Level B-fixed bound and comparator (LEVEL_B_FIXED.json, including the per-system real overrides);
  - the 5 refits' k.
- **Primary family:** `verdict.primary_estimates` and `verdict.build_primary_family`, with the margins delta_A, delta_C, tau_SMS, the suite margins delta_C_suite and tau_SMS_suite (calibration.json), and delta_NI (LEVEL_B_FIXED.json).
- **Conclusion:** `verdict.phase4_conclusion`, with:
  - P_t from `calibrate.true_state_categories`;
  - method_same_items from `calibrate.model_categories`;
  - synthetic_capped_at_partial = not calibration.json's "attainable".

  Missing results are charged:
  - a compressible system without a method verdict counts as not supported;
  - a real full network without a verdict counts as UNSUPPORTED.
- **Real verdicts by lineage.**
- **Sensitivity table:** every tolerance at both CI ends; the categories are re-judged and the conclusion recomputed.
- **5.17** (the rule pre-registered in PROTOCOL 5.17, P4-D56):
  - `loop.curves` (EE, SMS, lift success) and `loop.active_success` (own vs random / fixed, with the magnitude-matched control
    beside) run on the rule's system set, every synthetic confirmation-suite system with review G's traps excluded;
  - the real systems are reported beside, with the same statistics, descriptively;
  - failed or missing loops are charged BEFORE the frozen functions by `charge_loop_rows`, per cell (system, budget, loop seed):
    - a failed own cell gets the worse (higher-EE) of the two arms' comparator values (random, fixed);
    - a failed comparator cell gets the lower of the other arms' values, so it never favours the method;
    - a cell where every arm failed gets MISSING_EE for every arm.

    No system is dropped. The frozen `active_success` alone would EXCLUDE a system with a charged comparator (test
    `test_loop_charging_follows_protocol_5_17`), and charges an own failure at MISSING_EE = 10. Both cases were confirmed by the
    orchestrator on 2026-09-27 and are written verbatim into PROTOCOL 5.17: a failed own cell gets the HIGHER of random / fixed,
    and a failed comparator cell the LOWER of the other arms' values (never favouring the method).
- **5.13 / 5.14:** `loio_summary`, `limpo_comparison` and `sharing_comparison`, with the hard gate.
- **Level B -> C drop** (`--levelb-round`).
- **Review G's traps** (`trap_evaluation`; criterion 33). The trap systems are never pooled into P_m, P_t, the primary family, the
  sensitivity table, 5.14 or 5.17. The section is DESCRIPTIVE and sets no new threshold. For each trap it reports:
  - the method's verdict and failed criteria;
  - k against the truth (k consistency, k = k_true);
  - latent recovery and z_obs capture;
  - the true-state reference's category on the items it supports;
  - the baselines' categories and the references' EE;
  - the truth's expected verdict and an outcome.

  The outcomes (`trap_outcome`):
  - **handled:** SUPPORTED with k consistent;
  - **declared_correct:** "no compact causal state" declared where there is none;
  - **claim_partial:** PARTIAL, or SUPPORTED with unknown k consistency;
  - **no_claim:** UNSUPPORTED;
  - **false_alarm:** a declaration where a compact state exists;
  - **fooled:** a SUPPORTED or PARTIAL claim where there is no compact state, or with k inconsistent;
  - **missing:** charged, and listed under "charged".

  Counts are given by outcome and by trap label.
- **Outputs:**
  - research/phase4/level_c/<run>/RESULTS.json (the bundle);
  - CLAIMS.json;
  - LOOPS_SUMMARY.json and SHARING_SUMMARY.json (the self-audit's Q10 / Q18 inputs, in self_audit_p4's shapes);
  - TRAPS.json (the trap section).

## 3. Guards (nothing weakens a barrier)
- **`official_guard`** requires:
  - research/phase4/METHOD_LOCK.json present;
  - `method_lock_p4.py --check` clean;
  - the tag `brainir-causal-state-v1-preblind` an ancestor of HEAD;
  - LEVEL_B_FIXED.json present;
  - the Level C scripts, LEVEL_B_FIXED.json and review G's trap catalog equal to the lock's hashes (inputs or after-lock drivers);
  - the lock hashing the trap catalog at all (otherwise the trap tier cannot run).

  The official run also refuses a `levelc_remote.py` whose sha256 differs from the lock's, and a missing SELF_AUDIT_CONFIG.json.
- **Stage A refuses before the lock** twice: `suites.require_lock` in both planners (tested), plus the guard.
- **Dry run:**
  - `assert_dry_payloads` refuses any job with a hidden tier (conf, val, trap, real_levelb, real_levelc) in a tier field or a path
    segment, or with "salt" in any key or string;
  - dry runs take stand-in methods and never the locked package;
  - dry runs never build or read the trap tier. `--trap-standins` relabels dev systems, and `trap-probe` bakes the DUMMY catalog
    only: it refuses review G's file and uses a public seed.
- **Logging and run-once:**
  - every official run and every official Stage D gets START / DONE rows in HIDDEN_EVALUATIONS.md;
  - `LEDGER.json` refuses a second official run id per stage unless a reason is given and logged (goal5 section 70);
  - a resume recomputes nothing that finished.
- **Retries:** only infrastructure failures are retried: client exceptions, host refusals, stale-staging refusals (bounded by P1's MAX_STALE = 8), and the container patterns of `INFRA_PATTERNS`. Every attempt is recorded. A job's own error is its result, charged downstream.
- **Isolation:**
  - method code runs only in model workers: iso roles fit, eval and loop, and "call" for the four `levelc_remote` functions, which drive `RemoteFresh` / `fit_records`;
  - the iso image bakes a staging directory holding only `levelc_remote.py` (at `isolation.ISO_SCRIPT_DIRS`);
  - staged model refs are resolved by the driver (`isolation.read_staged`), never by a worker.
- **Uploads into shared directories merge** (`upload_dir(replace=False)`). The default replace=True deleted a tier's eval and truth parts twice on 2026-09-27.

## 4. Changes requested of hashed code during this work, and their status
| item | owner | status |
|---|---|---|
| iso role "call" (targets from /repo/scripts/p4; method modules refused) | P1 | done; used by every levelc_remote job |
| harness passes d_draw to eval_dimension_truth | orchestrator | done |
| calibrate_system(extra_models=) + phase-ordered scoring of a RemoteFresh extra model | E15 | done; S3 and D1 used it (every same-items row reports loader `calibrate.calibrate_system`). levelc_remote keeps a copy of the loader as a fallback for code without the parameter. |
| representation_stability call order | accepted | descriptive metric; protected by the digest rule |
| evaluate_stability.latent_flows NaN rows of width 1 for k > 1 (5.11 crashed) | orchestrator | fixed after dry run S2 |
| packed classes: per-input reload remounted volumes (lockdown failed, tars vanished) | P1 | fixed after dry run S1 |
| volume staging above ~1.5 MiB (block_network), total-size staging, call-role "staged" propagation, stale-staging refusals | P1 | done; the driver consumes model_ref / result_ref / file_refs and lists input_refs |
| tier-file uploads deleting eval / truth parts | orchestrator, P2 | fixed (merge) |
| generator construction depends on the BLAS thread count (hash mismatch; LOG P4-D50) | P6 | fixed (`SingleThreadedSystem`). The one hit in P2's runs: S2's evaluation of syn-01f497d7f752 on the OLD dev tier, whose lift family failed with "r0 'restart' must come from a trajectory of the same system" (S2's dev results were discarded anyway). D1 evaluated the same system on the interim tier with no such error; no "hash differs" in any P2 log or result. |
| review G's trap tier + the lock hashing its catalog | P6, orchestrator | done; the driver plans, builds and evaluates the tier (sections 2-3) |
| found by P2's dry runs and fixed in the driver (tests in brackets) | P2 | (1) Stage D read the verdict category one level too high, so every category was None [`test_category_of_...`]; (2) real lineage was null for every system [`test_real_lineage_...`]; (3) a dead Modal client burnt retries and stored in-flight jobs as failures [`test_a_dead_client_...`, `test_the_supervisor_...`]; (4) a result-storage failure was recorded as the job's own failure [`test_a_collect_failure_...`]; (5) the projection's scheduler was quadratic (over 15 min on 16,000 jobs) [`test_simulate_makespan_matches_...`]; (6) 5.11 stability: the models of one job shared a worker uid, so each model's worker start killed the others' and 5.11 ran on silently reduced samples; and the digest-rule restart storm on the real mechanism systems (section 9) [`test_stability_replay_equals_...`, `test_a_replay_mismatch_...`, `test_models_of_one_job_share_...`]; (7) no per-job time limit [`test_time_limit_formula`, `test_a_job_over_its_time_limit_...`, `test_a_second_timeout_...`, `test_a_hung_method_call_...`]; (8) 5.17 failed loops were charged by the frozen `active_success`, which drops a system with a charged comparator [`test_loop_charging_follows_protocol_5_17`] |

## 5. Execution
### Classes
Default: the PACKED iso classes.

| class | shape | jobs |
|---|---|---|
| iso_pack_fit | 32 CPU / 128 GB, 8 slots | fits |
| iso_pack_eval | 32 CPU / 256 GB, 8 slots | evaluations and the call jobs |
| iso_pack_loop | 32 CPU / 128 GB, 8 slots | loops |
| pack_xl | trusted, 8 slots | references |
| build | 16 CPU | Stage A |
| iso_pack_gpu_rtx6000 | GPU, 4 slots | fits of a cuda method |

- **Unpacked fallback:** `--unpacked` maps the classes to iso_fit_s / iso_eval_l / iso_loop / eval_l. It is for small models only, because block_network containers move at most 2 MiB inline. `Plan.class_map` is a driver input.
- **Container caps:** the official default is 25 containers per class. Dry runs used 7 (S3) and 2-5 (D1), within the 30-container dry-run cap.

### Executor
- **Scheduling:** dependency-driven, longest expected job first, with per-class caps on jobs in flight.
- **Per-job time limit** (`time_limit_s`): each attempt of a job gets an outer wall
  `max(1,800 s, 4 x p95(stage, system class) x scale) + the job's inner limit`.
  - The p95s are measured in the packed dry runs S3 + D1 (`PROFILE_P95_S`, queueing included). The scale is 1 for dry runs; for
    official runs it is LEVEL_B_FIXED.json's "time_limit_scale" when the orchestrator fixes it before the lock, else 3. It is
    recorded in plan.json.
  - **The inner limit is the method's own limit, enforced inside the container by trusted code:** one model call or model load
    (900 s / 600 s) for evaluation-type jobs, the fit's timeout_s, the loop's timeout_s; 0 for trusted jobs without method code
    (references, builds).
  - **How a method hang is told apart from infrastructure:** a method call that hangs is killed INSIDE the job by its per-call,
    fit or loop timeout. The job then returns with that failure recorded, which is the method's failure, charged per PROTOCOL (a
    failed prediction, fit or loop); it is never retried. Because the outer wall adds one inner limit, one hung method call cannot
    trip it. An attempt that exceeds the outer wall therefore spent its time outside any single method call (trusted code, the
    transport, the container, Modal): INFRASTRUCTURE.
  - **Action:** the first timeout cancels the call and resubmits it once. The second is final: the result
    `{"error": "time limit ...", "time_limit": {"final": true, "attribution": "infrastructure", "timeouts": [...]}}`, charged as
    missing by Stage D (listed under `charged.time_limit_final`), and not re-run on a resume unless `--retry-timeouts`.
  - **Records:** every timeout goes to `<run>/timeouts.jsonl` and to the job's row (`timeouts`, `limit_s`, `time_limit_final`).
  - **Two limits of the rule:**
    - a method that is slow on every call but never hangs can make a large evaluation job exceed the outer wall. No call of it
      hangs, so the rule attributes the timeout to infrastructure; the missing result is charged as missing either way (never in
      the method's favour). The scale exists for this: the orchestrator sets it from the locked method's measured Level B costs;
    - the wall counts from submission, so time in Modal's queue counts. The p95s include queueing, and the executor submits at most
      the class capacity.
- **Submission:** each job is ONE synchronous invocation (`Function.remote.aio`) on a single event-loop thread. The scheduler polls local futures only.
- **Two earlier designs failed in S3:**
  - one Modal map plus one thread per job exhausted the Windows socket buffers at about 170 calls in flight (WinError 10055);
  - `Function.spawn` is an ASYNC invocation, whose inline limit is 8 KiB (modal MAX_ASYNC_OBJECT_SIZE_BYTES), so block_network containers failed every output above 8 KiB.
- **Staged artefacts:**
  - outputs with model_ref, result_ref or file_refs are fetched with Backend.stage_get; the refs are kept and passed on;
  - an eval payload carries model_ref;
  - "call" payloads carry refs in "models" and list them under "input_refs";
  - a model set above the inline limit is staged first.
- **Machine limit (12:02 and 12:41 UTC):**
  - a machine-wide WSAENOBUFS (WinError 10055) killed the Modal client of two driver processes at once at 12:02 (about 110 and 26
    calls in flight), and of S3 alone at 12:41 (36 in flight) with the Windows non-paged pool at 2.9 GB. After a Docker Desktop
    restart the pool was at 1.9 GB. A leak probe of stage_get showed no leak in the driver;
  - before the fix, each in-flight job burnt its 2 infrastructure retries in seconds against the dead client and was stored as an
    infrastructure failure (S3: 82 checkpoint evaluations, 4 loops, 2 stability jobs); the resume re-ran them;
  - **FIX (`client_dead` / `ClientDied`):** the first call that fails with a dead-client signature ("Synchronizer thread unexpectedly
    died", ClientClosed, WinError 10055, anywhere in the exception chain) stops the executor at once. No retry is spent and nothing in
    flight is stored, so nothing is charged. `interruptions.jsonl` lists the calls in flight, an official run logs an INTERRUPTED row,
    and the process leaves with exit code 75 WITHOUT stopping the app through the dead client (Modal stops the ephemeral app).
    `run --auto-resume N` relaunches it. A fetch failure while storing a result is recorded as infrastructure (re-run on resume),
    never as the job's own failure;
  - keep at most two long driver processes on this host. For the official run (up to about 800 packed slots), keep one driver
    process below about 100 calls in flight, shard the graph by system component, or move the driver into a Linux container
    (section 10).

## 6. Dry runs
Systems:
- dev (stand-in for conf), with the dev tier's rebuilds noted in each run;
- the real public evaluation subset (stand-in for real Level C);
- toyC (the Level C design, built in each run).

Methods:
- the locked method: the stand-in `levelc_standin_pca`;
- baselines: the frozen v1 as S and as the 5.14 method (shared + adapt_from), plus, in D1, P3's stand-in comparators for the self-audit roles (`p3stand_idshortcut`, `p3stand_noeffect`, `p3stand_fullstate`).

No hidden data: every payload was audited.

| run | systems | classes | jobs | status | list cost |
|---|---|---|---|---|---|
| S1 | 5 dev + real:A:full + real:A:m1 + toyC x2 | packed | - | stopped: P1's packed reload bug (fixed) | ~$0.01 |
| S2 / S2b | the same | unpacked | 156 ok | stopped: dev eval part deleted by an upload; results discarded | ~$6.4 |
| S3 | real:A:full, real:B:full, real:A:m1, real:C:m2 + toyC x2 (the ~10 % sample) | packed, 4 containers per class | 1,048 of 1,050 ok | incomplete: the 5.11 stability of the two real mechanism systems never finished (section 9) | ~$42.8 |
| DIAG1 | stability_diag on real:A:m1 + real:C:m2 (S3's models), in P8's Linux driver container | iso_pack_eval (one container, 2 slots) | 2 of 2 | cause found and fix measured (section 9) | ~$2.1 |
| D1 | 5 dev systems (the 5.14 group + null, types 21 / 23) + P3's stand-ins for the self-audit roles | packed, 5 containers per class | 975 of 975 ok | complete | ~$30.6 |
| T1 | trap-probe (DUMMY catalog) | iso_pack_eval | 1 | all checks passed | ~$0.24 |

## 7. Projected post-lock wall time
`level_c.py project --dry-run-dev --run-id S3 --also-runs S2,D1 --target official` gives a longest-first list schedule over the packed
slots with the measured job wall times (median or p95 per stage and system class). The official system set is modelled as 75
confirmation + 16 trap (review G: 12-20) + 10 real systems = 101 systems and 15,884 jobs (11,394 checkpoint evaluations, 2,295
loops, 505 refits, 441 fits, 254 + 254 LOIO jobs). Stage A builds take 1,728 s each (the val tier's measured build) and precede
every packed job. The locked method's fit and loop costs are unknown, so the stand-in's are scaled x1 / x3 / x10.

| scenario | 100 containers | 50 containers | slot-hours | list cost |
|---|---|---|---|---|
| median, x1 | 3.5 h | 6.4 h | 1,382 | ~$593 |
| median, x3 | 5.4 h | 9.7 h | 2,192 | ~$849 |
| median, x10 | 15.6 h | 28.8 h | 5,024 | ~$1,746 |
| p95, x1 | 6.9 h | 12.9 h | 3,423 | ~$1,384 |
| p95, x3 | 16.0 h | 29.1 h | 6,019 | ~$2,206 |
| p95, x10 | 50.0 h | 93.2 h | 15,103 | ~$5,081 |

Checkpoint evaluations are 40 % of the slot-hours at x1. The loops dominate from x3 on (1,070 of 2,192 slot-hours).

Measured job walls include queueing: other agents kept the workspace near its 100-container limit. The projection does NOT include
the mechanism-stability problem (section 9): it prices those jobs at the measured stability walls.

## 8. What is left for after the lock (in order; nothing hidden runs before it)

### Before the lock (orchestrator)
1. `level_c.py fixed-from-levelb --round <final>`. It writes LEVEL_B_FIXED.json: the suite-level full-state bound and ID comparator, the real per-system choices, S, and delta_NI as a NUMBER.
2. `level_c.py self-audit-config ...`, with the final round's baseline names for the comparator roles. It writes SELF_AUDIT_CONFIG.json (the official run id, Q10 / Q18 summary paths, study directories).
3. Review G's catalog `research/phase4/review_g/review_g.py` must exist. `method_lock_p4.py` hashes it with both files and every
   post-lock driver, and `official_guard` refuses an official run whose lock does not hash the catalog.
4. **Diagnose the 5.11 stability of the real mechanism systems (section 9)** with one bounded diagnostic job before the lock. The
   official run has 7 real mechanism systems.
5. Confirm the real LINEAGE rule (`levelc_lib.real_lineage`: the reconstruction of the internal network; the public records carry
   lineage null), or give the benchmark explicit lineages.
6. `level_c.py prewarm`, which builds every image including the GPU one, IN THE LINUX DRIVER CONTAINER that will run C1 (section 10).
7. For the rule system set (below), decide in PROTOCOL 5.17 which systems enter the active-design rule. The driver analyses the confirmation suite as primary and reports the real systems beside it.

### After the lock
1. Run `level_c.py run --official --run-id C1 --auto-resume 2` in P8's Linux driver container (section 10). It runs:
   - the guard, the ledger and the START row;
   - Stage A: the conf and trap plans in the pinned image, the real Level C plans, about 101 builds;
   - Stages B-C: about 15,900 jobs, 11,400 of them checkpoint evaluations;
   - the DONE row.

   A dead client leaves an INTERRUPTED row and a RESUME row.
2. Criterion 11 on the confirmation suite. It needs a remote variant, because the conf public parts stay on the fit volume: reuse N4's per-system Modal check with tier conf; the result goes to research/phase4/CALIBRATION_CHECK_conf.json, which SELF_AUDIT_CONFIG names.
3. `level_c.py claims --official --run-id C1 --levelb-round <final round dir>`: START / DONE rows, and research/phase4/level_c/C1/{RESULTS,CLAIMS,LOOPS_SUMMARY,SHARING_SUMMARY,TRAPS}.json.
4. P3's post-lock studies reuse the Level C fits and evaluations (`--levelc-run`) and share the workspace (projection: 100 and 50 containers).

### Caveats that remain
- The executor has no per-job wall bound: a hung job holds the end of the run. The fallback is to stop the driver and run claims;
  Stage D charges the missing result.
- The projection's costs are list estimates with packed slots priced per slot. The workspace billing is the reference.

## 9. Dry-run results
Runs: S3 (the real + toy sample, 6 launches) and D1 (the dev part on the INTERIM dev tier, 2 launches). Stage D ran on both, D1
also with the two trap-type dev systems as trap stand-ins (`claims_traps/`) and with a STAND-IN calibration record
(`claims_traps_calstandin/`: exercises the sensitivity table; not a calibration). Outputs: C:/Dev/BrainIR_p4run/levelc_dry/<run>/
(REPORT.json, claims*/, PROJECTION_official.json) and levelc_dry/TRAP_PROBE.json. The stand-in's metric values mean nothing and are
not reported.

### Stage status
| stage | S3 (packed; median / p95 job wall, s) | D1 (packed; median / p95, s) |
|---|---|---|
| build (toyC) | ok 2 / 2 (533) | - |
| fit / refit | ok 30 + 30 (159 / 210; 155 / 193) | ok 25 + 25 (81 / 243; 75 / 87) |
| bfit / beval | ok 6 + 6 (466; 574 / 799) | ok 20 + 20 (305 / 656; 1,553 / 1,895): frozen v1 and 3 audit-role stand-ins |
| refs | ok 6 (1,306 / 2,214) | ok 5 (2,741 / 3,205) |
| eval | ok 6 (1,095 / 1,493) | ok 5 (1,646 / 1,732) |
| calib (same items) | ok 2 of 2 toy (1,072) | ok 4 of 4 (3,658 / 4,108) |
| stability (5.11) | ok 4 of 6 (882 / 2,712); the 2 real mechanism systems never finished (a restart storm of about 95 min, cause and fix below); every result on reduced samples (shared-uid kills, fixed) | ok 5 of 5 (1,891), on reduced samples (the same defect) |
| loio_fit / loio_eval (5.13) | ok 19 + 19 (171; 275 / 634) | ok 17 + 17 (201; 1,196) |
| limpo / share (5.14) | - (no group) | ok: shared 4, adapt 4, scratch 4, eval 4, share_fit 2, share_eval 4 |
| loop (5.17) | ok 162 of 162 (881 / 1,799; real full networks at budget 100) | ok 135 of 135 (587 / 1,973) |
| ckpt | ok 756 of 756 (223 / 1,412) | ok 675 of 675 (166 / 490) |
| Stage D | ok (24 s): primary family 18 of 24 tests (suite + 2 full networks), 5.17 on the suite and the real part, real verdicts by lineage | ok (5 s): 6 tests (suite), 5.14 group + null with the gate, trap section on the stand-ins, 14 sensitivity rows with the stand-in record |

Totals: S3 1,606 job rows, about $42.8 list estimate (packed: container seconds / slots); D1 1,037 rows, about $30.6.
Infrastructure failures and their reruns are in the rows (S3: 267 checkpoint evaluations, 8 loops and 4 stability jobs over the
Function.spawn launches and the two client deaths; D1: 31 jobs at 12:02 UTC). Jobs in flight when a client died are not in any row.

### What the dry runs show
- **Every Level C stage runs end to end on the packed classes:** Stage A builds (toyC); every fit kind; every evaluation kind; the
  4 levelc_remote call kinds; 9 designers x 3 loop seeds with the magnitude-matched control; checkpoint evaluations; Stage D.
- **toyC:** the OOD / robustness categories, validity AUC, uncertainty ratio, truth k-consistency, lift, composition and calibration
  are produced.
- **The self-audit roles are produced as baselines (D1):** P3's stand-ins `p3stand_idshortcut`, `p3stand_noeffect` and
  `p3stand_fullstate` for id_baseline / input_only / readout_history / linear_controlled, and the frozen v1 for the phase3 role. Each
  role gets a fit and an evaluation per system and a baseline category in Stage D.
- **SELF_AUDIT_CONFIG.json is written before the lock** by `level_c.py self-audit-config` (section 8).
- **Review G's trap tier:**
  - the plan (verdict stages only) and Stage D's trap section ran on stand-ins (D1: two trap-type dev systems);
  - `trap-probe` (T1) baked the DUMMY catalog at /repo/research/phase4/review_g in an iso image. `synthadapter.trap_catalog_path()`
    resolved it there; it was root-only (0o600, /repo 0o700), and a worker uid got "Permission denied";
  - `suite_systems("trap", 7)` built its 2 systems as SingleThreadedSystem in 0.22 s;
  - locally, the same catalog builds through the same path (test).
- **Real lineage:** the public records' lineage is null. Stage D now derives it from the internal network (`real_lineage`): S3
  groups real:A:* and real:B:full as "manc" (two builds of one reconstruction) and real:C:m2 as "male-cns". **The orchestrator must
  confirm this rule.**

### 5.11 stability on the real mechanism systems: cause and fix (diagnostic P2-DIAG1)
In S3, real:A:m1 and real:C:m2 never finished (attempts of 50, 30 and over 70 min, stopped by the client deaths and the session's
memory guard). One bounded diagnostic in P8's Linux driver container settled it. It ran `level_c.py diag-stability`: two
`levelc_remote.stability_diag` calls in parallel on iso_pack_eval, a 35-min container deadline, a 300 s per-call timeout and a 45-min
client wall, on S3's own stand-in models and public data. App ap-kuS6FeR9tgcCHld4VpH8Ek; record
`levelc_dry/S3/STABILITY_DIAG.json`.

**Cause 1: a digest-rule restart storm, not a hang.**
- RemoteFresh restarts a model's worker process whenever a history's last row has already appeared, followed by more samples, in
  another history sent to that process (the history-digest rule, review F: the process might hold the continuation).
- The mechanisms' records sit on exact float64 fixed points. Replaying the rule over the 5.11 call sequence (records only, no model)
  gives about 105 restarts per model on the mechanisms, against 22 / 7 on the full networks. S3 recorded 21 / 6 for those, so the
  replay reproduces the rule.
- Measured restart cost in a packed iso slot: 5.1-5.5 s (0.4 s close + 4.8-5.1 s spawn, init and model load), against 0.6 ms for a
  warm call.
- Per model: 2,272 calls with 102-105 restarts take 558-574 s, about 97 % of it restarts. The whole 10-model job needs about 93-96
  min. No call stalled; the slowest calls, about 6 s, are all restart calls.

**Cause 2: shared-uid kills, a silent correctness defect in every 5.11 result of the dry runs.**
- The frozen `representation_stability` interleaves its models, and all RemoteFresh of one job start role-A workers under the SAME
  uid of their slot. `LinuxUidTransport.start` SIGKILLs every process of that uid, so each model's worker start killed the previous
  model's idle worker.
- The diagnostic reproduced it: after model B's start, model A's next call failed in 2 ms with
  `WorkerDied: ... cannot send (BrokenPipeError)`.
- The killed model's calls failed silently (`safe_call`) until its next digest restart. The same call positions failed for every
  model, so every pair saw a uniform but reduced sample:
  - real:A:full: 14 of 24 effect items, 492 of 512 flow states;
  - real:B:full: 440 flow states;
  - toyC: 1,664 of 3,456.

  An offline prediction under this mechanism matches S3's counts: 14 items and 505 states for real:A:full, 24 items and 442
  states for real:B:full.

**Fix (`levelc_remote.stability`).**
- Each model's calls run to completion in its OWN RemoteFresh, one model at a time, so no two RemoteFresh of the job are alive
  together, and are recorded (`recording`).
- The FROZEN `representation_stability` then computes every metric on replays of the recordings (`replay`): the same calls in the
  same per-model order, and no metric code duplicated.
- A replay that differs from its recording raises `ReplayMismatch` (a BaseException, so `safe_call` cannot swallow it).
- The digest rule is unchanged.
- Verified:
  - bit-identical to the frozen function on the models directly (real:A:m1 x 3 models and real:B:full x 2 locally; unit test);
  - in the diagnostic: 0 call errors, all 24 effect items and all 512 flow states in every pair; the replayed metrics take 0.35 s,
    each pair under 4 ms.
- The mechanisms' stability job now takes about 95 min with the stand-in, and its time limit uses that projection
  (`PROFILE_P95_S["stability"]["mech"]` = 5,732 s).

**Not done (options).** Both would cut the time without weakening the rule:
- (a) one job per model across slots, so the models' restarts run in parallel: about 10x less wall, the same CPU;
- (b) in isolation.py (P1): a pre-started spare worker, so a restart becomes a swap of about 0.4 s. The restart storm slows every

The shared-uid kill is assigned to P1, to be fixed at its root in isolation.py: one uid per model worker, and a worker death raised as an
infrastructure error that `safe_call` cannot swallow. The record-and-replay orchestration of `stability` stays (bit-identical to the
frozen function, with loud failures).
  evaluation of the 7 real mechanism systems (evaluations and checkpoints too), not only 5.11.

With the locked method's worker start (its imports and model load), a mechanism stability job could take hours. Measure one restart
at the lock.

## 10. Running the official Level C in a Linux container (P8's driver image)
Long Modal clients on the Windows host die of machine-wide socket-buffer exhaustion. The Modal clients of the official run should
therefore live in P8's Linux driver container `brainir-p4-driver:1` (docker/p4driver; LOG P4-D54), whose sockets are the Docker VM's.
P8 validated 1,500 concurrent calls with no errors and a peak of 7 sockets.

`level_c.py` reads P4_RUN_BASE, which the wrapper exports, so it runs there unchanged. Checked in the container on 2026-09-27:
- `plan --dry-run-dev --sample smoke --trap-standins ...` produces the plan;
- `plan --official` reaches `official_guard` (git, `method_lock_p4.check`) and refuses without a lock.

    # after the lock; wrapper options come BEFORE the script
    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py start --name levelc-C1 --memory-gb 8 \
        scripts/p4/level_c.py run --official --run-id C1 --auto-resume 2
    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py status
    uv run --no-sync --project phase4 python scripts/p4/linux_driver.py logs levelc-C1 --tail 50
    # Stage D needs no Modal: on the Windows host (more memory), or in the container with --memory-gb 16
    uv run --no-sync --project phase4 python scripts/p4/level_c.py claims --official --run-id C1 --levelb-round <final round dir>

What the container provides, and what it needs:
- **Repository:** mounted read-write at the Docker daemon's path of C:\Dev\BrainIR, so the driver's ROOT is a path the daemon
  resolves. That makes Stage A's nested `docker run` of the pinned planning image (`plan_on_reference_platform`, through the mounted
  Docker socket) mount the right host directories. Also under the repository: the salt (data/phase4/hidden, for the real Level C
  plans), LEDGER.json, HIDDEN_EVALUATIONS.md and the build manifests.
- **Run area:** C:\Dev\BrainIR_p4run, mounted the same way, as P4_RUN_BASE. Run directories, `_iso_scripts` and `_trap_catalog`
  land there.
- **Modal credentials:** ~/.modal.toml, read-only (never read or printed by the wrapper).
- **git:** in the image, with `safe.directory '*'`.
- **Resources:** a 4 GB memory cap by default. `--memory-gb 8` is suggested for the 16,000-job plan; the dry-run drivers used
  100-120 MB.
- **Images:** the Modal images are built from the same file contents. Run `level_c.py prewarm` in the same container before the lock,
  so any mount-hash difference costs nothing on the day.
- **Resume:** `--auto-resume 2` stays useful (a client can die for other reasons). Its supervisor relaunches the same command inside
  the container.
