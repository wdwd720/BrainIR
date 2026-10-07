# Active-design success rule: minimum detectable effect on the dev suite (pre-freeze)

STATUS: READY, NOT RUN. The pipeline is built, tested and profiled. The full run starts, on the orchestrator's signal, once the dev tier
has been rebuilt from the revised generator (the eval part of the current tier was removed from the eval volume on 2026-09-27; the
run's readiness check refuses a partial, failed or older-than-the-generator build). The full run regenerates this file and writes
`ACTIVE_MDE.json`.

PROTOCOL.md section 5.17 requires the minimum detectable effect (MDE) of the active-design success rule to be computed by simulation
on the dev suite before the freeze. Code: `brainir_causal.active_mde` (reference-learner adapter, packed loops, checkpoint EE, summary)
and `scripts/p4/active_mde.py` (Modal driver). Tests: `phase4/tests/test_active_mde.py` (21 tests; all pass on Modal, E11-15).

The single command:

    uv run --no-sync --project phase4 python scripts/p4/active_mde.py run

It runs the draw preflight first (see Draw context). That check alone costs about a cent and can be run on the rebuilt tier
beforehand:

    uv run --no-sync --project phase4 python scripts/p4/active_mde.py preflight

## What the run does

- Tier: synthetic dev, all systems; the TRUE-STATE learner on the compressible ones (integer k in the tier's truth summaries).
- Learners: the benchmark references FULL-STATE and TRUE-STATE (`brainir_causal.refs`, learner v2; no method exists before the
  freeze). Each checkpoint model is the reference refitted from scratch on D0 + all of the loop's data at that checkpoint, seed = the
  loop seed.
- Designers: `random` and `fixed` (`brainir_causal.designers`); loop seeds 0, 1, 2; budget 200 experiments; checkpoints 10, 25, 50,
  100, 200; batch 5 (`loop.run_loop`, the loop of the tournament's driver; `DirectSim` on the system's simulator). 576 loops.
- Quality per checkpoint: the class-balanced EE at the primary horizon on the verdict items (in, target, near, far, hidden) of the
  system's dev eval part, through the verdict's EE code path (`evaluate.predict_items` -> `eval_effects` ->
  `ee_cb(units, PRIMARY, VERDICT_KINDS, "class")`); abstentions scored as no effect. TRUE-STATE first gets every held-out
  history registered with its true state, dt and effective draw (as in the calibration; see Draw context).
- MDE per learner: `loop.mde_by_simulation` with E15's rules (rule (i): one intersection-union test on the mean over budgets per
  comparator; rule (ii): the log-ratio delta-method bound), alpha 0.025 per rule, power target 0.8, efficiencies 1, 1.1, 1.25, 1.5,
  1.75, 2, 2.5, 3, 4, 1,000 simulated suites per scenario, plus the size under nulls whose fixed design is weaker by 0.05 and 0.10
  EE. Reported per learner: the MDE of rule (i), rule (ii) and the union; the false-positive rates at e = 1 and under the
  weaker-fixed nulls; the noise medians; the excluded systems with the reason; the cost.

## Draw context (TRUE-STATE)

In reference learner v2, the TRUE-STATE state is [z, draw]. z is the true latent state. draw is the trajectory's effective parameter
draw: the generator's `draw_effective`, stored as `truth['draw']` by the tier build and returned by the simulator for the loop's new
trajectories. Every trajectory has its own draw, so z alone, or the training-mean draw, leaves an error floor. The rebuilt dev tier
carries the draws. The current hash-locked generator has no `draw_effective`.

- Fits: every TRUE-STATE fit gets the draw of each training record. D0's draws come from the tier's truth store (the arrays
  `calibrate.py` loads) and the new trajectories' draws from the simulator. A missing draw is an error, not a fallback.
- Held-out histories are registered with their dt and draw (`register_truth(x, u, z, dt, draw)`).
- Preflight, before any pack: one util job per system with TRUE-STATE loops (`draw_preflight`, `draw_verdict`). The run is refused
  (exit code 2, a MODAL_RUNS row, no pack started) in these cases:
  - the tier's truth has draws, but a system lacks one for some D0 record or for some held-out record with a true state;
  - a system's D0 draws differ in length or contain a non-finite value;
  - the container's generator has no `draw_effective`.

  A tier with no draws at all is refused unless `--allow-no-draw` is given (smoke tiers only; TRUE-STATE is then z alone). A system
  whose draws are constant over D0 gets a note only (see Constant draws). E11-12 ran the preflight alone on toyC, which has no
  draws. It refused as expected (2 util jobs, 33 s).
- In the run, these raise when draws are required:
  - a TRUE-STATE fit whose training draws VARY but which reports `info()['draw_context']` False (`check_draw_context`);
  - a loop record without a draw, and draws of different lengths or with a non-finite value;
  - a held-out registration without a draw.

  After the packs, `draw_violations` collects them. Any violation refuses the MDE: no summary and no report are produced, the rows
  are kept in ACTIVE_MDE.json, and the exit code is 2.
- Constant draws (the orchestrator's decision, 2026-09-27): when every draw coordinate is constant over a fit's training records
  (the learner's own criterion), z alone is exact given that draw and there is no error floor. The context is then legitimately
  off. The row records draw_context False with draw_context_reason "constant draws", and the run is not refused.
- Recorded:
  - every TRUE-STATE row: draw_required, draw_context, draw_context_reason (none with the context, "constant draws", or "no draws"
    on a tier without draws), training_draws ("varying" or "constant"), n_registered_without_draw, n_probe_encodes and the
    learner's static_context note (coordinates, kept, dropped as constant);
  - ACTIVE_MDE.json: the preflight per system (`draw_preflight`: counts, D0 draw lengths, finiteness, D0 coordinates that vary)
    and the tally over all fits (`draw_context`, with the number of constant-draw fits);
  - the report: one line.
- Tests (`test_active_mde.py`): toy generators whose trajectories carry their time constant as the draw, per trajectory or shared
  by all.
  - The preflight passes, and a generator without `draw_effective` fails it. The driver's `draw_check` refuses when a
    preflight container fails.
  - Packed equals unpacked bit for bit. Every TRUE-STATE fit uses the context, and no registration lacks a draw.
  - A simulator without draws is refused in phase 1.
  - Shared (constant) draws: a whole loop runs, every fit is off with the reason "constant draws", and nothing is refused.
  - Varying draws with a fit that drops them are refused.
  - The verdict, violation and loop-draw rules hold.
- Cost: the profile below predates the draw context and was not repeated. Each TRUE-STATE fit now carries the kept draw coordinates
  as extra static inputs. The run records every task's wall time.

## Execution (minimum wall time, identical results)

A reference fit depends only on (its records, the seed, the thread count), and the random and fixed designers never query the model.
So each loop splits into phase 1 (design and simulation with every fit deferred, run once per data stream: both learners of a
(system, designer, seed) run identical experiments) and phase 2 (one fit + evaluation task per checkpoint).
- 96 containers of `eval_xl_np` (32 cores, 128 GiB, NON-PREEMPTIBLE), each with 16 worker processes x 2 threads. `--cls eval_xl`
  selects the preemptible class (same resources, a third of the price, see Preemption).
- Loops are assigned to containers longest first, then refined by a local search of moves and swaps on a cost model of the container
  schedule; predicted slowest container 24.7 min.
- Inside a container one pool runs the phase-1 jobs first and each stream's tasks as soon as its own phase 1 ends, longest predicted
  first, within a memory budget.
- Preemption: the default class is non-preemptible (P1's `eval_xl_np`), so no pack is preempted. On the preemptible `eval_xl`
  (`--cls eval_xl`), Modal would restart a preempted container with the same input and the pack would rerun ALL its tasks (up to
  about 25 min extra for that container; the profile saw 3 preemptions in one container). The packs also write every finished task
  to a progress store (a modal.Dict) for resume, but P1's run_call starts job subprocesses without the Modal client or credentials, so
  the store is unavailable in the containers (toyC smoke: `progress_error` "No module named 'modal'"); the packs run normally without
  it. The summary stays on the preemptible `eval_xl` (about a minute; a preempted summary container just reruns its input).
- Beside the packs, two loops of the run are also run unpacked, one per container at the same thread count, and their checkpoint
  rows must equal the packed rows bit for bit: both learners of the random-design stream, loop seed 0, on the compressible system of
  median size, at budget 10. That takes about 13 min, so the check never outlasts the packs. Because the designers ignore the
  remaining budget, these rows equal the full-budget loop's first checkpoint (tested). This is recorded in the run's record and in
  this file.
- The summary's independent calls (learner x scenario x chunk of 100 simulated suites, each with its own seed) are spread over up to
  8 containers and merged exactly (size-weighted rates).

Why this and not P1's `Backend.call_packed` (one fresh subprocess per job):
- The checkpoint tasks depend on their loop's phase-1 data. Per-task jobs would each redo the loop's design and simulation up to
  their checkpoint and start a fresh process. Phase 1 took 97 s (66 units) and 265 s (230 units) per stream at budget 200, so
  redoing it per checkpoint adds about 18-49 s per task on average, plus the process start. This design runs phase 1 once per
  stream. The evaluation context (12-73 s per load in the profile) is loaded about once per task in BOTH designs, because the
  per-worker cache rarely meets the same system twice.
- `run_packed` resubmits host-gate refusals only in the next wave, after the current wave's longest job (about 25 min here). The eager
  per-container submission used here resubmits a refused container at once. Earlier runs saw up to 151 refusals in about 576 spawns.
- `pack_xl` has 8 slots per 32-core container, while the profile's best packing needs 16 two-thread slots.
- What `call_packed` does better: its global pull queue balances containers dynamically and Modal retries a single task after a
  preemption. Here the assignment is static: the predicted slowest container is 24.7 min against a median of 22.0 min, so imbalance
  costs a few minutes. Preemption is removed by the non-preemptible default class (above).

## Profile (E11-7, research/phase4/ACTIVE_MDE_PROFILE.json)

The same work (4 loops on dev systems with 66 and 230 observed units at budget 200, plus 2 verification loops at budget 25) was run
under three packings of one `eval_xl` container:

| packing | pack wall | verification vs unpacked | container peak memory |
|---|---|---|---|
| 16 workers x 2 threads | 1,327 s | bit-identical, 4 / 4 rows | 54 GB |
| 8 workers x 4 threads | 2,052 s | bit-identical, 4 / 4 rows | 37 GB |
| 4 workers x 8 threads | invalid (see below) | infrastructure failure | 26 GB |

- Task walls at 2 threads: FULL-STATE 640-724 s (66 units) and 892-1,067 s (230 units); TRUE-STATE 333-431 s and 428-467 s.
- Four threads were only 10-20 % faster per task than two, so 16 x 2 has about 1.7 times the throughput per core of 8 x 4.
- Calibrated cost model (16 x 2; `active_mde.py analyze-profile`): task seconds = 569 + 1.91 x n_obs (FULL-STATE) and 380 + 0.33 x
  n_obs (TRUE-STATE); phase 1 of a stream at budget 200 = 97 s (66 units) to 265 s (230 units).
- Predicted full run on 96 containers: phase-2 makespan 1,483 s (24.7 min) with 16 x 2, against 2,360 s with 8 x 4; about 29 min in
  total including phase 1; 909 task core-hours; about 39 container-hours, so about $297 for the packs on the non-preemptible default
  `eval_xl_np` (billed at 3 x the list rate; `usd_per_s`), or about $99 on `eval_xl`, plus about $1 for the summary and the
  verification loops.
- Memory: the 16 x 2 container peaked at 54 GB (cgroup, page cache included) with 16 concurrent tasks of both systems. The per-task
  peak is now sampled from the resident set (`RssPeak`, added after the profile), so the full run records it for every task.
- 4 x 8 is invalid: its container was preempted and restarted, and the dev eval part was deleted from the eval volume mid-run. Its
  median-system tasks failed with FileNotFoundError, which is not a value difference.

## Smoke tests

- E11-6: the whole `run` path (packs, the summary on Modal, this report) on 2 small dev systems, 16 loops at budget 100, 2
  containers: 0 failed loops, 0 checkpoint errors; 1,640 s wall; about $2.26 (before phase 1 per stream, the in-run verification and
  the distributed summary existed).
- E11-10: the current `run` path on the toyC tier (the dev eval part was gone), 16 loops at budget 100 on 2 containers of 16 x 2:
  0 failed loops, 0 checkpoint errors; in-run verification bit-identical (2 of 2 rows); summary spread over 2 containers (10 s);
  per-task peak memory recorded (0.77 GiB for the toy tasks); progress store unavailable in the containers (see Preemption);
  590 s wall; about $0.84.
- E11-2 / E11-5: the unpacked path on 1-2 systems (earlier version of the learner).

## Why an earlier run was stopped (E11-4)

With the version-1 reference learner, the references predicted intervention effects worse than NO-EFFECT on most dev systems
(FULL-STATE class-balanced EE 1.09-2.29, TRUE-STATE 0.57-6.78 on 8 systems, against NO-EFFECT 0.72-0.99), which would have made the
MDE meaningless. The learner was replaced (version 2, fork E13) before this pipeline was finished.
