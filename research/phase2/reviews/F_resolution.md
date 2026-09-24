# Review F (computational): resolution

Review: `research/phase2/reviews/F_computational.md` (1 blocker, 7 major, 11 minor). All findings were resolved or
documented before the confirmation run and the method lock. Tests: `tests/test_budget_integrity.py` (new) and updated
`tests/test_discovery_infra.py`.

| # | severity | resolution |
|---|---|---|
| 1 | blocker | Failed runs stay in every success denominator: `run_one_job`, `pair_job`, `sweep_job` and `transfer_experiment_job` return failure records instead of raising, and remote failures carry method, instance, network and seed. `summarize` and `summarize_pairs` count failures as unsuccessful and report `n_failed` (markdown too). Reliability sweeps report consistency and pass rate with and without failures. Test: two failed jobs halve the success rate. |
| 2 | major | Runtime integrity guard (`count_real_simulations`) in `run_one`, `run_method` and pair/transfer jobs. A run fails if its real simulations differ from the calls charged, or its calls exceed the budget. Accounting attributes are read-only properties; budgets can only be tightened (`close()`); other networks are simulated via `sim.spawn()`, whose children are counted. Static test: method modules may not import `brainir.sim.{model,prune,screen,experiments}` or `scipy.integrate`, construct `BudgetedSimulator`, or assign `sim.<attr>`. |
| 3 | major | `run_many` rejects weight noise without an explicit `weight_noise_seed`. |
| 4 | major | `PinnedModalBackend` (`brainir.discovery.remote`) builds the image with the exact local package versions and Python minor version, with single-threaded BLAS; all Phase 2 scripts use it. Every job returns `runtime_env()`, and tournament results list the distinct environments. `method_lock.check()` compares installed package and Python versions with the lock. |
| 5 | major | `launch_provenance()` (commit, dirty flags, diff hash, source-tree hash, simulator code version, launch time) is passed as the registry record's `code` and stored in the results. Remote campaigns with uncommitted `src/` changes are refused unless `--allow-dirty` is given. Tournament records also carry score seeds, `robust` and the suite hash. |
| 6 | major | Documented and renamed rather than engineered away. Identity consistency is consistency across node orders × parameter draws × internal randomness, because the position-indexed sampler re-assigns draws under a permutation. Paired comparisons stay fair: the frozen baseline and BrainIR v1 face the same confound on the same variants and seeds, and the frozen baseline's sampler cannot be changed. The earlier LOG wording ("order sensitivity") is corrected in the LOG. |
| 7 | major | The hidden-evaluation gate in `reliability_sweep.py` checks four things: lock and tag; method ∈ {locked method, frozen baseline}; the sweep's recorded locked-tree hash, configuration hash and budget equal the lock's (or the baseline script hash equals BENCHMARK_LOCK's); and a per-(method, network) ledger that refuses repeats unless `--new-attempt` is given. |
| 8 | major | `np.argsort(-score, kind="stable")` in `correspondence.py`. |
| 9 | minor | `network_hash` includes n. The code version covers `discovery/{simulator,problem,interventions}.py`. `scale_by_nt` is rejected. Queries are normalised (explicit default `t_end`, default stimulus, no-op overrides, empty interventions). |
| 10 | minor | Memoised `active_positions` arrays are read-only. |
| 11 | minor | One `BudgetExhausted` policy on every path: an empty result flagged `budget_exhausted` (`run_method` records it in `method.compute`). |
| 12 | minor | `cfg_override` is limited to the four `*_sd` fields; `t_end` may not exceed the model's. |
| 13 | minor | Parameter seeds queried are recorded in the simulator report. `run_one` fails a run that queries a reserved seed (≥ 5000 or a score seed). Blind seed 0 keeps every current method below the frozen evaluator's 1000–1015. |
| 14 | minor | The permutation seed is no longer written into the variant (`network.json` / manifest). Permutations and run outputs live in separate `<variants>__private` / `__runs` trees, and remote truth is unpacked beside, not above, the instance. The test scans file contents. |
| 15 | minor | Documented: ids inside `mechanism.notes` stay in the variant frame (the evaluator does not read notes). The fallback fidelity now maps ids to positions. |
| 16 | minor | Empty cores agree with nothing (Jaccard 0); `n_empty_cores` is reported. |
| 17 | minor | Per-run discover wall/CPU and scoring wall are recorded. The registry estimate is labelled an upper bound in the report. |
| 18 | minor | Documented (profile in the review). The per-batch process pool is left as is; all harness paths use `workers=1` inside a job. |
| 19 | minor | `blind_eval.py` runs `freeze.py --check`, the lock records and checks the BENCHMARK_LOCK hash, the lock hashes the gatekeeper scripts themselves, the FROZEN.json and prediction hashes are logged before the evaluator runs, and `run_method` writes the source-tree hash and integrity counts into `method.compute`. |
