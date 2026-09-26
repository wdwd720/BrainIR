# Phase 3 self-audit (goal4 section 87)

Merged 2026-09-26T10:18:21Z from the full run (2026-09-26T10:14:48Z) and a Q19 re-run (2026-09-26T10:02:00Z) made after the last counterexample sweep finished. Each check TESTS a question; 'fail' weakens the claim and is reported; 'n/a' means its evidence does not exist. Thresholds were fixed before the post-lock evidence (SELF_AUDIT.json).

Counts: {"integrity": {"pass": 12, "fail": 3, "n/a": 0}, "science": {"pass": 16, "fail": 3, "n/a": 0}}

| id | status | check | criteria | note |
|---|---|---|---|---|
| I1 | pass | Phase 1 benchmark remains frozen (benchmarks/dng100/freeze.py --check) | 1 |  |
| I2 | pass | Phase 2 locked method unchanged (method_lock.py check; no change under src/brainir since brainir-v1-preblind) | 2, 3 |  |
| I3 | fail | Phase 3 benchmark lock, tag and salt commitment | 9, 10 | FAILS AS WRITTEN (check artefact): it compares the working benchmark lock with the copy at tag state-discovery-benchmark-v3, but the two logged execution-only re-locks rewrote the lock after that tag. The property holds: freeze_benchmark.py --check passes, tag state-discovery-benchmark-v3-relock2 ho |
| I4 | pass | Phase 3 method lock (METHOD_LOCK.json hashes, tag brainir-state-v1-preblind) | 18, 19, 46 |  |
| I5 | pass | Clean room matches its allowlist and holds no forbidden file (make_phase3_cleanroom.py --check) | 4, 5, 6, 7 | problem lines are counted by class only (matched text is never copied) |
| I6 | pass | No answer-bearing file (by content hash or name) in the rooms (hidden tier: any room; developer tier: method room) | 5, 6 | file names and paths only (never contents) |
| I7 | pass | No answer token or forbidden name in the rooms' text files (classes and counts only) | 5, 6, 7 | numeric hits shorter than 8 digits, and numeric hits in public data files, are reported as coincidences (counts, sizes); non-numeric hits, long numeric hits in code or notes, and dataset / organism / source names fail; references to file names (e.g. the hidden-evaluation log) are counted only |
| I8 | fail | Hidden-evaluation log is complete and consistent (every Level C / confirmation run logged; attempts counted) | 17, 47, 48 | FAILS AS WRITTEN (check artefact): the only problem it lists is 'Level C attempt _refcache has no log row'. _refcache is the reference-control cache directory that the frozen Level C driver creates next to its attempts, not an attempt. Attempt 01 has START and DONE rows, and all 13 confirmation part |
| I9 | pass | No hidden evaluation or hidden real data before the method lock | 17, 46 |  |
| I10 | pass | Test suites green (Phase 3 tests; root tests when requested) | 42, 43 |  |
| I11 | fail | The Modal fit volume holds only public fit views, method snapshots and fitted models |  | FAILS AS WRITTEN (check artefact): the allowlist of top-level entries lacks 'bundles'. bundles/dng100_public_blind holds exactly the 18 files of the public tier-A bundle (byte-identical, verified 2026-09-26), staged under the logged version-3 amendment of the leakage policy (section 3.1) for Level C |
| I12 | pass | Reviews A-H complete, blockers resolved before the lock; post-lock reviews after it | 44, 45 | post-lock reviews not yet present |
| I13 | pass | Compute and costs recorded (COSTS_LEDGER.md, COMPUTE_SUMMARY, per-run Modal records) | 41 | run scripts/p3/compute_summary.py to (re)write COMPUTE_SUMMARY.md |
| I14 | pass | PHASE3_REPORT.md exists, is marked answer-bearing and states one of the three conclusions | 49, 50 |  |
| I15 | pass | Phase 2 candidates regenerated from public evidence (provenance recorded) | 8 |  |
| Q1 | pass | Could time alone explain the latent state? (time-index trap C on the final suite) | 14, 28 | fooled = a compact causal state claimed while the true latent is not recovered |
| Q2 | pass | Could stimulus alone explain it? (stimulus-copy trap D; A against the input-only control) | 21, 22 |  |
| Q3 | pass | Could output history alone explain it? (output-shortcut trap B; A against the readout-history control) | 21, 22 | real systems: the readout-history control is descriptive (benchmark version 3) |
| Q4 | pass | Did future information leak into the encoder? (history slicing of the evaluator; prefix determinism of the model) | 22, 23 | the stub check always runs; the prefix probe needs a fitted locked-method model on dev systems |
| Q5 | pass | Is the latent dimension underestimated because of smoothing? (k vs true k; fast-relaxation systems) | 19, 28 |  |
| Q6 | pass | Does discarded neural state still predict future behavior? ('closed': micro / history gain, closure gap, Markov) | 24, 25 |  |
| Q7 | pass | Do two microstates with the same z actually diverge? (E, microstate equivalence) | 25 | None = untestable |
| Q8 | pass | Does intervention fidelity collapse on unseen perturbations? (held-out C; held-out vs in-distribution on real) | 23 | held-out C upper CI >= 1 = no better than predicting no effect |
| Q9 | pass | Does shared cross-connectome dynamics only work because capacity is huge? (J: parameters, capacity) | 32, 33 | no shared cross-connectome dynamics supported: nothing to attribute to capacity |
| Q10 | pass | Does alignment rely on neuron identity? (neuron-order permutation probe: same k and A) | 30, 32 | the permuted copies are under data/phase3/p3perm_* (public dev data; delete after the audit) |
| Q11 | fail | Does the latent model memorize the physical implementation? (leave-one-implementation-out adaptation) | 31, 34 |  |
| Q12 | fail | Does the representation change completely across random seeds? (G: R^2 both ways, k agreement, predictions) | 29 |  |
| Q13 | fail | Does parameter uncertainty require extra hidden state? (parameter trap H; closure on real draws; draw probe) | 35 |  |
| Q14 | pass | Does the model fail after transient perturbation? (post-intervention error vs unperturbed A; transient trap J) | 23, 36 |  |
| Q15 | pass | Is a simple linear model equally good? (paired S1-S5 against every linear method of the confirmation round) | 15, 16 | fail = some linear method is not significantly worse on any component (the added value over linear models is not supported) |
| Q16 | pass | Is PCA equally good? (the PCA-k control with the method's k: A and C per system) | 39 |  |
| Q17 | pass | Can unrelated synthetic systems be falsely aligned? (unrelated pairs must be rejected) | 33, 34 |  |
| Q18 | pass | Does the method find low-dimensional states in the non-compressible controls? (family L) | 13, 38 |  |
| Q19 | pass | Can the counterexample search break it immediately? (post-lock sweeps) | 37 |  |
