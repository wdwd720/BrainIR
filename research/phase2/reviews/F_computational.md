# Review F — computational: budgets, cache safety, remote reproducibility, where the time goes

Reviewer: independent agent (review F of `research/phase2/REVIEW_PLAN.md`), 2026-09-23. Pre-lock, main repository, no
oracle. Code reviewed at `8f44eeb`. Re-checked at `d0b5c4b`: of the files in scope, only `scripts/reliability_sweep.py`
had changed (`81650d8` added the lock gate), and it was re-read. No repository file was modified. The experiments below ran
locally (at most 3 processes, no Modal) from throw-away scripts in the session scratchpad, which are not committed. Their
synthetic instances were built with the public generators, so their truth was generated here.

## What was read (and what was not)

- **Read in full:** `CLAUDE.md`, `research/phase2/SELECTION_PROTOCOL.md`, `research/phase2/REVIEW_PLAN.md`,
  `src/brainir/discovery/{simulator,interventions,problem,criteria,tournament,reliability,pair_tournament,transfer,joint,correspondence,run,interface}.py`,
  `src/brainir/compute/{backend,registry}.py` (frozen; read only), `src/brainir/sim/model.py` (frozen; read only),
  `scripts/{run_tournament,reliability_sweep,budget_curve,method_lock,blind_eval,rescore_causal_minimality,archive_results}.py`,
  `scripts/cleanroom_entry/brainir_discovery_entry.py`,
  `tests/{test_discovery_infra,test_method_lock,test_modal_consistency}.py`, and the commit `28fdee7` test file.
- **Grepped only** (targeted lines, no answers): `src/brainir/methods/*.py` for simulator, seed, sort, file and environment
  use; `benchmarks/dng100/evaluator/evaluate.py` for seeds and the prediction fields it reads;
  `benchmarks/dng100/baselines/greedy_prune_sim.py` for its budget/deadline logic;
  `benchmarks/dng100/cleanroom/run_method.py` for its environment and bundle verification; `benchmarks/dng100/BENCHMARK_LOCK.json`
  for hashed paths; `research/LOG.md` §10 for Phase 2 compute notes.
- **Data inspected:** the aggregate compute fields of `research/phase2/tournament/sel_*.json` (walls, calls, CPU, errors; no
  per-instance truth is reproduced here), the compute fields of `research/phase2/reliability/greedy_frozen_*.json`, and
  `benchmarks/dng100/manifests/experiments/{index.jsonl,<id>.json}`.
- **Not opened:** `benchmarks/dng100/oracle/`, `benchmarks/dng100_walking_cpg/`, `benchmarks/dng100/baselines/results/`,
  `research/literature/`, `research/audit/`, `goal1-3.md`, `PHASE0/1_REPORT.md`, `research/phase2/HIDDEN_EVAL_LOG.md`.

## Short answers to the nine questions

1. **Can anything simulate without being charged?** Yes, four ways, all demonstrated (finding 2). None of them is used by
   the current candidates, and no production path shares a memo or cache across runs. The persistent `CausalEffectCache` is
   wired only into a test. The joint ledger's shared per-network memo is intended: a query is paid once per pair run.
   Keep-only and silence keys cannot collide, and seed, `cfg_override`, `t_end`, the stimulus (including pulse timing), the
   criterion and the code version are all in the key. The one unsafe key is unseeded weight noise (finding 3). Latent gaps
   are listed in finding 9.
2. **Budget before running, batches, `BudgetExhausted`?** `run_many` checks the whole deduplicated batch *before* any
   store lookup or computation (`simulator.py:206-212`), and a batch either runs completely or not at all. Store hits are
   charged. `run_one` records exhausted runs but discards the method's partial result, and the blind and sweep paths do not
   catch the exception at all (finding 11). Every method catches it internally, and 0 of 3,132 stored selection runs
   exhausted their budget or exceeded it.
3. **Cache-key completeness.** The key covers everything that reaches the simulator except the network size when `sizes`
   is None (demonstrated collision), `scale_by_nt` (ignored by the simulator anyway) and randomness when
   `weight_noise_seed` is None (demonstrated). The code version covers 3 files and no package versions, which matters only
   if the store is enabled (findings 3 and 9).
4. **Joint ledger.** Exact. In 48 configurations (2 pairs × 2 base methods × 3 budget splits × 4 modes), the number of
   real `simulate()` invocations equalled the ledger total, and the total never exceeded `budget_a + budget_b`. Adaptation
   and validation calls are counted and reported separately. In joint mode one network may use more than its own budget,
   by design, because the cap is on the pool.
5. **Reliability sweeps.** Predictions are mapped back correctly for every field the evaluator reads. Functional
   fidelity is computed in the variant's own frame, which is correct. However, the permutation is **not** hidden, because
   its seed is written into the variant (finding 14). More importantly, node-order variants re-draw every neuron's model
   parameters, so "order" consistency is confounded with the parameter draw (finding 6).
6. **Scoring.** Scoring always uses a fresh simulator and is never charged to the method. Score seeds are disjoint from
   the method seeds under the pre-registered seeds (0–2), but only by convention (finding 13). `compact_result` cannot
   change any score: scores are computed before compaction, and summaries read only uncompacted fields. The only loss is
   that Brier scores can no longer be recomputed from stored records that assessed more than 100 candidates.
7. **Modal reproducibility.** Packs and `Shared` payloads are resolved by name and content, and nothing in the methods
   depends on local paths, clocks, the legacy global RNG or string-set order. All method argsorts are stable. The gaps are
   these:
   - the remote image is unpinned and its package versions are not recorded (finding 4);
   - registry records carry the commit at *registration*, while the image is built from the working tree at *launch*
     (finding 5);
   - one unstable argsort in the correspondence ranking decides exact ties in 10–16 % of real-network queries (finding 8).

   The frozen baseline's wall-clock deadline never bound in the three sweeps (runs took 90–581 s against a 1,500 s limit),
   so its sweep results depend on calls, not on container speed.
8. **Cost and time.** Every Phase 2 Modal campaign is in the registry with `estimated_cost_usd` (28 records, $61.7 in
   total). The estimate is a crude upper bound, and the scorer's time is not recorded (finding 17). Simulation takes 97–98 %
   of every run's time, and harness overhead is below 1 ms per query. For the 4,604-neuron network, the sparse
   matrix-vector product (full network) and the per-neuron activation over all 4,604 neurons (keep-only) dominate. The
   profile is in finding 18.
9. **Method lock and blind evaluation.**
   - What is covered: the lock hashes all of `src/brainir/**/*.py`, the entry script, `pyproject.toml`, `uv.lock`, the
     effective configuration, the run protocol, the bundles, the documentation, the evidence and the test log. Methods read
     no other files or environment variables. Inside `blind_eval.py`, freeze-before-evaluate is enforced.
   - What is not checked: installed package versions and the Python version (finding 4); the benchmark-lock integrity at
     evaluation time and the gatekeeper scripts themselves (finding 19).
   - The new hidden-evaluation gate in `reliability_sweep.py` checks only that *a* lock exists. It does not check that the
     scored predictions come from the locked method or code (finding 7).

## Findings

### 1. BLOCKER (before the confirmation run): failed or timed-out runs silently drop out of every success denominator

- **Evidence:**
  - With the Modal backend, a failed job (exception, timeout, out-of-memory) becomes
    `{"method", "instance", "error"}` (`tournament.py:354-356`). `summarize` then keeps only records with `"structure"`
    (`tournament.py:228`). This affects `success_rate`, the functional rates, `n_runs`, the identity consistency and the
    per-family tables. `to_markdown` shows no failure count.
  - `summarize_pairs` does the same (`pair_tournament.py:89-91`).
  - Experiment E6 (2 scored successes + 2 failed jobs) gives `n_runs 2, success_rate 1.0, functional 1.0`.
  - On the local path, the same exception instead aborts the whole tournament (`tournament.py:357-362`, no try). The two
    backends therefore have different failure semantics.
  - The selection runs so far have 0 errors (5 result files, 3,132 runs), so no current number is affected.
  - The confirmation suite is used exactly once. A heavier `brainir_v1` could time out (7,200 s limit) or exceed the
    3 GB memory limit on the 3,000-neuron instances. Its success rate would then be computed on its survivors, which
    biases decision-rule condition (a).
- **Fix:**
  - Score every attempted job: a failure counts as `success=False` and `functional_success=False`.
  - Report `n_failed` per method in the summary and in the markdown.
  - Do the same in `summarize_pairs`. For the reliability sweeps, report consistency and fidelity both with failures
    counted as empty cores and without them.
  - Wrap `run_one_job`, `sweep_job` and `pair_job` in try/except so that local and Modal runs behave identically.
  - Add a test that two failed jobs lower the success rate.

### 2. MAJOR: the call budget is honour-based; a method can simulate uncharged in four ways

- **Evidence:** experiment E1, run through `run_one` with `budget=10`:

  | method body | reported `calls` | real `simulate()` invocations | flagged? |
  |---|---|---|---|
  | `from brainir.sim.model import simulate` and call it directly | 1 | 31 | no |
  | builds a second `BudgetedSimulator(problem, max_calls=10**9)` | 0 | 30 | no |
  | `sim.max_calls = 10**9` | 30 (> budget 10) | 30 | no (`budget_exhausted` False) |
  | `sim.calls = 0` at the end | 0 | 8 | no |

  - `calls` and `max_calls` are plain mutable attributes (`simulator.py:168,174`). The joint ledger itself relies on
    mutating `max_calls` (`joint.py:153`).
  - `run_one`, `run_method` and `joint.discover` never cross-check the report against real work.
  - Library helpers (`brainir.sim.prune`, `screen`, `experiments`) call `simulate` internally, so a composer could bypass
    the budget without meaning to.
  - Current candidates: `grep` finds no bypass. Methods only read `sim.cache` membership (`cem_search.py:105`,
    `evo_pareto.py:355`, `surrogate_search.py:497`) and `sim.max_calls` (`surrogate_search.py:430`).
  - Efficiency is one of the three "advantage" axes in decision-rule condition (b).
- **Fix:**
  - (a) Runtime guard in `run_one`, `run_method` and `_PairRun.discover`: while `discover` runs, wrap `brainir.sim.model.simulate`
    and `brainir.discovery.simulator.simulate` with a counter. Fail the run if the count ≠ `sim.computed_calls` (with
    workers = 1; for joint, compare with the ledger).
  - (b) Make `calls`, `max_calls`, `computed_calls` and `simulated_seconds` read-only properties, and give the ledger a
    private `_close()`.
  - (c) Static test: methods may not import `brainir.sim.{model,prune,screen,experiments}` or `scipy.integrate`, may not
    construct `BudgetedSimulator`, and may not assign to `sim.*`.
  - (d) `run_one` marks `calls > budget` as a failed run.

### 3. MAJOR: unseeded weight noise is served from one cache key although every draw differs

- **Evidence:**
  - `silence`, `keep_only` and `intact` default to `weight_noise_seed=None` (`interventions.py:13-26`).
  - `apply_intervention` then draws from OS entropy (`model.py:226`, `default_rng(None)`).
  - `canonical()` records `None`, so every such query shares one key.
  - E2: two identical unseeded `keep_only(..., weight_noise_sd=0.8)` queries have identical keys. Four direct simulations
    give scores `[0.0, 0.032, 0.998, 0.998]` (the verdict flips). Through the simulator the method receives
    `[0.9994, 0.9994, 0.9994]` with `calls=1, cache_hits=2`: one random draw, memoised and charged once.
  - With the persistent store enabled, that single draw would be served to every later run. It is also irreproducible
    between runs and machines.
  - Every current caller passes a seed (`greedy_plus.py:192`, `evo_pareto.py:334-339`, the scorer at
    `tournament.py:126`). The trap is in the default API that the `brainir_v1` composer will use.
- **Fix:** `run_many` raises `ValueError` for `weight_noise_sd > 0` with `weight_noise_seed is None`, or derives the seed
  deterministically from `(query seed, intervention)`. Make the seed a required keyword argument whenever
  `weight_noise_sd > 0`, and add a test.

### 4. MAJOR: the remote numerical environment is unpinned and unrecorded, and the lock records but never checks package versions

- **Evidence:**
  - `MODAL_DEPS` contains only lower bounds (`backend.py:34-35`: `numpy>=2.0`, `scipy>=1.13`, `pandas>=2.2`, `pyarrow>=17`).
    Locally, `uv.lock` pins numpy 2.5.3, scipy 1.18.1, pandas 3.0.6 and pyarrow 25.0.1.
  - Modal caches the image by its definition, so remote versions are whatever pip resolved at the first build. Neither
    `RunStats` (`backend.py:193-196`) nor any job result records them.
  - `method_lock.py:128` records the *local* versions. `check()` (`method_lock.py:148-175`) never compares installed
    versions or the Python version, and `uv run --no-sync` can leave the venv stale.
  - Yet the lock's `synthetic_results` evidence was produced on Modal.
  - The selection tables mix environments: `rescore_causal_minimality.py` recomputed `functional_success_causal` locally
    (Windows) for all three `sel_mech_b1000` parts (`rescored` flag set, 300/43/31 records rechecked). The pre-registered
    metrics were computed remotely (Linux).
  - Numerics: BLAS results depend on the kernel and the thread count.
    - With `OPENBLAS_CORETYPE` set to default/Haswell versus Sandybridge/Prescott, the `gemv` digests differ and `ddot`
      differs in its last bits for Prescott.
    - A 200,000-element `ddot` differs in its last bits between 1, 2 and 8 threads.
    - The coarse outcomes (score, pass, frequency, active count) of a full-network and a keep-only simulation were
      identical across all four kernels. The practical risk is therefore version skew (for example, changes to scipy's
      RK45), not ULP noise.
  - `test_modal_consistency.py:16-33` compares the simulator on one 40-neuron instance (2 seeds × 2 interventions,
    `rtol=1e-6`) and never a whole method run. It is opt-in and "passed once".
- **Fix (outside the frozen `compute/` package):**
  - A discovery-side Modal image factory or backend subclass that pins exact versions from `uv.lock` (`uv export --frozen`
    → exact `pip_install`) and sets `OPENBLAS_NUM_THREADS=OMP_NUM_THREADS=1`.
  - Every remote job (`run_one_job`, `sweep_job`, `pair_job`, `transfer_experiment_job`) returns an `env` block with the
    Python and package versions, platform, numpy CPU features, `sim_code_version()` and the source-tree hash; store it in
    the records.
  - `method_lock.check()` compares installed versions and Python with the lock.
  - Extend the Modal consistency test to one full `run_one_job` per method on a small instance: identical core, calls and
    scores.

### 5. MAJOR: registry provenance captures the commit when the record is written, not when the job was launched

- **Evidence:**
  - `ExperimentRecord.finalize()` calls `_git()` inside `register_run` (`registry.py:57-62`), i.e. after the campaign
    finishes.
  - The Modal image copies the working tree at launch (`backend.py:141-144`, `add_local_python_source(..., copy=True)`),
    including uncommitted changes.
  - `src_dirty` looks only at `src/`, and only at the end (`registry.py:32`).
  - Launch times reconstructed as `created_utc − wall`:

    | campaign | launched (≈) | commit recorded | recorded commit's time |
    |---|---|---|---|
    | `sel_mech_b1000_part1` (4 methods) | 22:39:54Z | `0538702` | 22:59:05Z (adds `joint.py` and `evo_pareto.py` after launch) |
    | `sel_mech_b1000_part2` (`evo_pareto`) | 22:54:54Z | `ab1992d` | 23:05:51Z |
    | `sel_mech_b1000_part3` (`cem_search`) | 23:05:06Z | `c6310ce` | 23:10:32Z |

  - I checked the files that determine outcomes. `simulator.py`, `criteria.py`, `interventions.py` and `problem.py` last
    changed at `7dd89a0`/`399dfdd`, `sim/model.py` at `ee68aac`, and each method run was committed before its launch. So
    no result is attributed to different numerics. The defect is the audit trail, which the protocol ("identical code
    commit for all methods") depends on.
  - Also: `run_id` hashes only name, config, seeds and inputs (`registry.py:61`), so a re-run with changed code
    overwrites `<run_id>.json` (`registry.py:73-74`). Tournament records omit `score_seeds`, `robust` and a content hash
    of the suite (`tournament.py:375-377`).
- **Fix:**
  - At launch, compute `{commit, dirty(src, scripts), source_tree_sha256 (method_lock.source_hashes), sim_code_version}`
    and pass `code=` to `ExperimentRecord`; `finalize` keeps a pre-set value, so no frozen file changes.
  - Refuse Modal launches with a dirty `src/` unless `--allow-dirty`, and then record a diff hash.
  - Put the launch time and code hash into `inputs` so that run_ids differ between runs.
  - Record `score_seeds`, `robust` and the suite's bundle and truth hashes.

### 6. MAJOR: node-order variants re-draw every neuron's parameters, so "order" reliability is confounded with the parameter draw

- **Evidence:**
  - `sample_neuron_params` draws by position (`model.py:138-150`), so permuting positions re-assigns the parameter draws.
  - E5 (synthetic, same neurons, same seed, `main` versus `order1`): per-neuron `tau` differs, and the keep-only score
    differs on 9 of 12 seeds.
  - Real network (`manc_v1.2.1`, intact, seeds 0–3, original order versus `make_permuted_bundle` seed 1003):
    - frequency 9.90/11.11, 11.63/9.71, 10.99/10.00 and 10.64/9.62 Hz;
    - active neurons 73/81, 93/78, 71/77 and 78/70;
    - active-set Jaccard 0.78–0.81.
  - So two runs that differ "only" in node order already see different dynamics, and no pair of runs in the protocol
    isolates ordering.
  - `research/LOG.md` §10 already attributes the frozen-greedy probe difference to "order sensitivity".
  - Paired method comparisons stay fair (same variants, same seeds). The metric is consistency across (order × parameter
    draw), not node-order invariance.
- **Fix:** either
  - (a) make the draws permutation-equivariant in the harness: the job functions know `perm`, so draw in the source frame
    and permute into the variant frame through a harness-held hook in `_simulate_query`, never exposed to the method. This
    gives a clean order-only contrast. Or
  - (b) add controls (same order with different seeds; different order with the same parameter realisation) and rename
    the metric.

  In both cases, correct the LOG wording.

### 7. MAJOR: the post-lock hidden-evaluation gate of the reliability sweeps is not bound to the locked method or code

- **Evidence:**
  - `reliability_sweep.py:87-89` refuses only when `_lock_ok()` fails, i.e. when no lock verifies or the tag does not
    match (`reliability_sweep.py:168-176`).
  - After a lock exists, `--hidden-eval` accepts any `--method`.
  - `--score-existing` scores any existing sweep JSON. The payload carries no source-tree hash, method version or commit,
    so a candidate's sweep made before the lock (or an edited file) scores as easily as the locked method's.
  - "One logged hidden evaluation per method and network" (`SELECTION_PROTOCOL` §6.3) is enforced only per file, via the
    "already carries a hidden evaluation" check.
  - The frozen baseline's source is read from the working tree (`reliability_sweep.py:107`) without checking its
    `BENCHMARK_LOCK` hash, and it is not recorded in the sweep.
- **Fix:**
  - Require `method ∈ {lock.method.name, FROZEN_NAME}`.
  - Write `source_tree_sha256`, the config hash, the budget and the baseline script sha256 into every sweep payload at
    run time. Require them to equal the lock's values, or `BENCHMARK_LOCK`'s entry for `baselines/greedy_prune_sim.py`.
  - Keep a ledger of hidden evaluations per (method, network) and refuse repeats without a logged `--new-attempt`.

### 8. MAJOR: an unstable argsort in the correspondence ranking makes transfer and joint results depend on the numpy build and CPU

- **Evidence:**
  - `correspondence.py:126` uses `np.argsort(-score)[:k]`. This is the only non-stable sort in `discovery/` and
    `methods/`; every method uses `kind="stable"`.
  - On the real public networks (`male-cns_v1.0` → `manc_v1.2.1`, 367 shared anchor types, 300 random candidates),
    39/300 queries have an exact tie at the top-1 cutoff.
  - The default top-k differs from the stable top-k for 31/300 queries (k=1), 38/300 (k=3) and 48/300 (k=6).
  - Default argsort tie order is implementation-defined. Numpy dispatches 64-bit argsort to CPU-specific SIMD sorts, and
    the Modal numpy version is unpinned (finding 4).
  - `match_candidates` feeds `transfer_core`, the joint prior, the structural alignment and the claims. These run on
    Modal (pair tournament, real transfer experiments), so local reproduction of claimed correspondences is not
    guaranteed. This was not observed directly, because this review used no Modal.
- **Fix:** `np.argsort(-score, kind="stable")` (ties broken by position), plus a test that ties rank by position.

### 9. minor: cache-key hygiene (latent, because the persistent store is not wired into any production path)

- **Evidence:**
  - (a) `network_hash` omits `n`/`W.shape` (`problem.py:123-134`). With `sizes=None`, adding one isolated neuron leaves
    the hash unchanged while the outcome changes (E4: 0.9966 vs 0.9999).
  - (b) `scale_by_nt` is absent from `canonical()` (E3: equal keys). This is harmless today because `simulate` ignores
    it, but a method that sets it gets a silent no-op.
  - (c) `SIM_CODE_FILES` (`simulator.py:43`) omits `discovery/simulator.py` (the config merge in `_simulate_query`),
    `problem.py` (stimulus and W construction), `interventions.py` and the package versions.
  - (d) Non-canonical duplicates get distinct keys and are charged twice (never answered wrongly):
    - `t_end=None` versus the explicit default;
    - a stimulus override equal to the problem's stimulus;
    - `cfg_override` values equal to the defaults;
    - `silence([])` versus `None`.
- **Fix:** hash the shape; include or reject `scale_by_nt`; extend the code version (and add package versions) before
  the store is enabled; normalise queries (the effective `t_end`, stimulus and config) before hashing.

### 10. minor: memo hits alias mutable arrays

- **Evidence:** the first delivery of a query returns the memo object itself, and later hits are shallow copies
  (`simulator.py:256-263`). E8: writing into `outcome.active_positions` changes later memo hits (arrays are writeable).
- **Fix:** store the arrays read-only (`setflags(write=False)`), or return copies.

### 11. minor: `BudgetExhausted` handling differs between harness paths

- **Evidence:**
  - `run_one` (`tournament.py:141-145`) and `_PairRun.discover` (`joint.py:493-497`) replace the result with an empty
    core, discarding everything the method found.
  - `run_method` (`run.py:184-195`), which serves the blind run and the sweeps, does not catch the exception. The result
    is a traceback and a failed network; `sweep_job` (`reliability.py:178`) has no try, so a local sweep crashes
    entirely.
  - All six methods catch the exception themselves (1–3 handlers each). The stored runs show `budget_exhausted` 0 and
    calls ≤ budget.
- **Fix:** one policy on every path: catch the exception, emit an empty prediction and record `budget_exhausted: true` in
  `method.compute`.

### 12. minor: a "call" has no cost cap

- **Evidence:** `cfg_override` accepts any `ModelConfig` field (`t_end`, `rtol`, `method`, `b_exc`, …), so one call can
  be arbitrarily long or can simulate a different model. `simulated_seconds` does reveal the cost. Current methods use
  only the widened standard deviations and the default `t_end`.
- **Fix:** whitelist the override keys in `run_many` (the four `*_sd`, `t_end ≤` the model's `t_end`), and report mean
  and median simulated seconds next to calls in every summary.

### 13. minor: seed namespaces are disjoint only by convention

- **Evidence:**
  - Methods use `seed*1000 + offset`: `greedy_reference.py:59`, `cem_search.py:176`, `evo_pareto.py:256-258` and
    `joint.py:472-473`.
  - Evaluators use fixed ranges:
    - synthetic scorer: 5000–5003, plus noise seeds 6000–6003;
    - reliability fidelity: 7000–7007;
    - transfer checks: 8100–8105;
    - frozen evaluator: 1000–1015 (`evaluate.py:438`).
  - With the pre-registered run seeds (0–2) and the locked blind seed (0), these sets are disjoint. A run seed of 1, 5, 7
    or 8 would put the corresponding evaluation in-sample. Seed 1 with order 0 reproduces the frozen evaluator's exact
    functional-family draws.
- **Fix:** have the simulator record the set of parameter seeds queried, and assert disjointness from the scorer's seeds
  in `run_one`, `sweep_job` and `blind_eval`. Alternatively, reserve a range the simulator refuses for method queries.

### 14. minor: the variant permutation is not hidden, and sibling directories are readable

- **Evidence:**
  - `make_permuted_bundle` writes `order_variant_seed` into `network.json` (`reliability.py:87`) and into the manifest
    (`reliability.py:97-98`).
  - `np.random.default_rng(problem.extra["network_info"]["order_variant_seed"]).permutation(n)` reproduces the private
    permutation exactly, and the sweep seeds are predictable (1000+k).
  - `_private/` (permutations) and `_runs/` (other runs' predictions) are siblings of the variant
    (`reliability.py:101-104,161`).
  - Tournament truth files sit next to the instances before `discover` runs, both locally (`suite/truth`) and remotely
    (`tournament.py:198-203`, `pair_tournament.py:60-65`).
  - `test_discovery_infra.py:256-269` checks file *names* only, so it passes.
  - The impact is limited. Unique public per-neuron attributes (`size_voxels`; per-neuron `cell_type` tokens in the
    synthetic suites) already permit canonicalisation, and no method opens files (grep).
- **Fix:** keep the seed only in `_private`; use unpredictable salted seeds; place `_private`, `_runs` and `truth`
  outside every ancestor of the method's bundle; make the test scan file contents. (Cross-reference for review D.)

### 15. minor: reliability frame details

- **Evidence:**
  - `prediction_to_common_frame` maps the core, stimulus, loop and cross-connectome ids (`reliability.py:108-123`), but
    not the ids inside `mechanism.notes` (generic roles, top inclusion probabilities, alternatives). The evaluator does
    not read notes, but other consumers see mixed frames.
  - The fallback fidelity at `reliability_sweep.py:135-137` treats `core_common` as positions. That is wrong for tier-B
    body ids, but the code is dead today because fidelity is computed inside the job.
- **Fix:** map or drop the note ids; map ids to positions in the fallback.

### 16. minor: identity consistency rewards empty cores

- **Evidence:** `tournament.py:274` and `reliability.py:208` score empty-versus-empty as 1.0. E7: three empty cores give
  pairwise Jaccard 1.0 and identical fraction 1.0.
- **Fix:** score empty pairs as 0 (or exclude them) and report `n_empty`.

### 17. minor: the cost estimate is a crude upper bound, and scoring time is not recorded

- **Evidence:**
  - All 28 Phase 2 Modal campaigns in the registry carry `estimated_cost_usd` (sum $61.7).
  - The estimate is wall time × `max_containers` × price (`backend.py:187-192`). The job-level figures below come from
    the stored results:

    | campaign | runs | Modal wall | estimate | Σ per-run discover wall (max / median) | discover-only cost | simulation CPU / discover wall | scorer verification calls |
    |---|---|---|---|---|---|---|---|
    | sel_mech_b1000_part1 | 1,368 | 1,201 s | $8.81 | 51,663 s (1,081 / 7.2) | $3.79 (43 %) | 98 % | +13 % |
    | sel_mech_b1000_part2 | 342 | 758 s | $5.56 | 23,880 s (542 / 47.9) | $1.75 (31 %) | 97 % | +3 % |
    | sel_mech_b1000_part3 | 342 | 331 s | $2.43 | 4,258 s (283 / 4.1) | $0.31 (13 %) | 97 % | +18 % |
    | sel_curve_part1_b250 | 432 | 482 s | $3.54 | 4,097 s (72 / 5.3) | $0.30 (8 %) | 97 % | +11 % |
    | sel_curve_ext_b50 | 648 | 237 s | $1.73 | 2,158 s (16 / 2.8) | $0.16 (9 %) | 97 % | +57 % |

  - The scorer's time is not recorded anywhere. `audit_suite_truth.py` Modal runs are not registered.
  - The Modal wall is set by the slowest job (part 1: 1,081 s against a 7 s median).
- **Fix:**
  - Record per-job discover and scoring wall and CPU separately, and derive the cost from them.
  - Register the audit runs.
  - Submit jobs longest-expected-first (for example by instance size × budget) to cut the tail.

### 18. minor: where the time goes, and two harness inefficiencies

Profile (`cProfile`) of `manc_v1.2.1` from `public_blind` (n = 4,604, 196,359 synapse pairs):

| query | wall | notes |
|---|---|---|
| load + `network_hash` | 0.05 s + 5 ms | |
| full network, 1 s simulated | 2.67 s | 10,422 right-hand-side (RHS) evaluations; 945 accepted steps of 1,736 attempts (46 % rejected); `csr_matvec` 51 %, `tanh` activation 24 %, solver and wrapper overhead ≈ 25 % |
| full network, 2 s (bundle default) | 4.87 s | the same cost as any silencing query in the full network |
| keep-only, core falls silent | 0.19 s | 136 step attempts |
| keep-only, 70 active candidates (oscillates, passes), 1 s | 1.28 s | activation over all 4,604 neurons 49 %, `csr_matvec` 5 % |
| `SimQuery.key`, keep-only of 4,458 positions | 0.4 ms | harness overhead negligible |

- Simulation is 97–98 % of every run's time (finding 17), so a 1,000-call run on this network costs roughly 3–80 min of
  CPU, depending on the query mix.
- Integrating only the kept subnetwork is 3× faster (0.40 s versus 1.25 s for 215 kept neurons; the removed neurons are
  exactly 0), but it is **not** equivalent. RK45's error norm is a root-mean-square over all n components, so silent
  neurons loosen the effective tolerance: the subnetwork needs 15,744 RHS evaluations against 10,062, and max
  |Δr| = 0.012 Hz. Do not use this shortcut unless the frozen evaluator's semantics are re-validated.
- Harness inefficiencies:
  - `BudgetedSimulator(workers>1)` spawns a new process pool per batch and pickles W into every job (2.42 MB). A 6-query
    batch took 4.42 s with 3 workers against 1.79 s sequentially (`simulator.py:232-235,265-268`).
  - With a Modal `backend=`, each batch starts a Modal app. The harness does not use this path.
- **Fix:** a persistent pool with W in the initializer (as `LocalBackend` does), or drop the option; keep one remote job
  per run.

### 19. minor: gaps in the lock and in blind evaluation

- **Evidence:**
  - `blind_eval.py:72-78` neither runs `freeze.py --check` nor compares `BENCHMARK_LOCK`'s `lock_sha256` with the
    METHOD_LOCK entry. The integrity of the runner, sandbox and evaluator is enforced only by the test suite.
  - `method_lock.py` and `blind_eval.py` themselves are not hashed.
  - The HIDDEN_EVAL_LOG row (`blind_eval.py:133-135`) holds neither the `FROZEN.json` hash nor the prediction hashes, so
    the freeze is not tamper-evident.
  - `run.main` passes no `code_commit` (`run.py:214`), so predictions do not identify their own code.
  - The evaluator can still be invoked directly, so logging is by policy only.
- **Fix:**
  - In step 1 of `blind_eval.py`, run `freeze.py --check` and compare the lock hashes.
  - Hash the gatekeeper scripts into the lock.
  - Log (and commit) the `FROZEN.json` sha256 *before* the evaluator runs.
  - Let the entry script put the source-tree hash into `method.compute`.

## Verdict

**Sound as designed:**
- Charged calls equal the simulations actually run on every honest path: charged = computed calls in all 3,132 stored
  runs, and charged = real `simulate()` invocations in all 48 configurations of the ledger audit.
- The joint ledger is exact and capped.
- Scoring is never charged, and compaction never changes a score.
- The in-run memo cannot answer a different query.
- Methods themselves are deterministic, with no clock, global-RNG or unordered-iteration dependence.

**Not yet trustworthy enough for the one-shot confirmation and the lock:**
- Failures silently leave the denominators (blocker).
- The budget is not enforced against bypass.
- Unseeded weight noise is cached under one key.
- The remote environment is unpinned and unrecorded, and records carry the wrong commit.
- Node-order reliability is confounded with parameter re-draws.
- The hidden-evaluation gate is not bound to the locked method.
- An unstable argsort breaks exact ties in the correspondence ranking.

All fixes are small and outside the frozen benchmark files. Findings 1–3 and 8 are one-to-twenty-line changes with tests;
findings 4, 5 and 7 are harness bookkeeping; finding 6 is a design decision (make the draws equivariant, or rename the
metric). With these fixed, I have no computational objection to running the confirmation suite and writing the lock.
