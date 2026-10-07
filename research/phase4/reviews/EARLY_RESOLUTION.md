# Early pre-freeze reviews: findings and resolution (orchestrator)

Reviews run in C:\Dev\BrainIR_p4review before the benchmark freeze and before any method exists. Every blocker and major is fixed
before the freeze; each fix names its owner and evidence. Status is updated as fixes land.

## Review F (leakage), research/phase4/reviews/F_early_review.md — 5 blockers, 7 majors, 9 minors

| id | finding | owner | status |
|---|---|---|---|
| F-B1 | true latent z written into PUBLIC pool futures | E8 (suites) | FIXED (E8: truth to truth/, key whitelist assertion; toy rebuilt) |
| F-B2 | in-process fit / eval guard can be switched off (`_TL.busy`; thread + exec); fits run from the main repository with the full environment | E10 (evaluation architecture: OS-level isolation, per-job containers, unprivileged child, scrubbed environment, no network) | FIXED (E10, P4-D22; Docker + Modal adversarial tests) |
| F-B3 | evaluation runs method code in the process holding the held-out answers (gc lookup 24 / 24) | E10 (model process / container separated from the scorer; fresh process per job) | FIXED (E10, P4-D22) |
| F-B4 | protected room files rewritable with allow-listed host tools; `./sbx` replaceable -> unsandboxed host execution | E9 (NTFS deny ACEs, guard refuses ./sbx and write-capable options, hash check of the outside wrapper, canary) | in progress |
| F-B5 | in-room manifest carried the refusal list (names) and was exempt from the scan | orchestrator | FIXED 2026-09-26 19:58 UTC: in-room manifest = paths / hashes / sizes; scan exemption removed; bench and review rooms synced. The synthetic author read only the first 80 lines of its manifest (the refusal list began at line 147); its transcript contains none of the names |
| F-M1 | redaction reversible via source hashes; names survive inside regex sources | E9 (names moved to one non-copied config; no source hashes in any room) | in progress |
| F-M2 | guard messages echo patterns / names | E9 | in progress |
| F-M3 | container can write src/, __pycache__, tests/, room root, nested CLAUDE.md, sitecustomize, forged .pyc | E9 (room root read-only, explicit work areas, no bytecode writes, scan for planted files) | in progress |
| F-M4 | simulation-service identity self-declared (unlimited budget, cache oracle, readable ledgers) | E8 (per-agent tokens outside the request; no `cached` flag) | FIXED (E8: launcher token P4_SIM_TOKEN; launcher wiring by E9) |
| F-M5 | tournament feedback as covert channel | E10 (fixed system sets, caps, boolean failures, coarsened medians, validation-only) | FIXED (E10: check_release, coarsening; 7 tests) |
| F-M6 | public keys / seeds brute-forceable; 32-bit tier seed | E8 (>= 128-bit HMAC seeds, salted public-part seeds of hidden tiers) | FIXED (E8: 128-bit HMAC seeds, salted streams) |
| F-M7 | remote runner job guard unreviewable; job keeps network | E9 (block_network, read-only data, scrubbed credentials, reviewable) | in progress |
| minors 1-9 | remote client crash; array views; glob bypass; shared .tmp; error echo; target complement; whitelists; eval-pool rng; frozen exemption | E8 (2, 5, 6, 7, 8), E9 (1, 3, 4, 9) | in progress |

## Review E (statistics), research/phase4/reviews/E_early_review.md — 7 blockers, 7 majors

PROTOCOL.md rewritten first (sections 5.1, 5.3, 5.4, 5.5, 5.10, 5.17, 7, 9, 10, 11 and the conclusion rule), then implemented:

| id | finding | decision (PROTOCOL) | owner | status |
|---|---|---|---|---|
| E-B1 | SMS explodes on constant-in-train identity columns | columns built in folds, near-constant dropped, no +1e-9 divisor (5.3) | E5 | FIXED (E5; tests in test_eval_review.py) |
| E-B2 | x_res / random-feature ICG without power; CI omits fitting variability | x_res map per outer fold; 20 seeds; CI with redrawn folds; verdict = LINEAR ICG; power table before the freeze (5.3, 5.4, 7) | E5, E6 | in progress |
| E-B3 | failed / non-finite latents dropped from D / E | fail when > 5 % unusable; counts reported (5.3) | E5 | FIXED (E5; tests in test_eval_review.py) |
| E-B4 | MEV testability depends on the model's k (escapable) | untestable MEV does not satisfy E; no "supported (E untested)" category (5.5, 9) | E5 | FIXED (E5; tests in test_eval_review.py) |
| E-B5 | selection code differs from the protocol | one unambiguous rule; relative gates; ordering when none eligible; seeds averaged; kind strata (10) | E7 | FIXED (select.py; 15 tests); wiring in E10 |
| E-B6 | stratified bootstrap anti-conservative at 1-3 per type | Clopper-Pearson for P_m; paired unstratified for P_m - P_t; rescaled stratified for tie bands (9, 10, 11) | E5 | FIXED (E5) |
| E-B7 | primary Holm family undefined | 24-test table with statistic, null, margin; one-sided alpha 0.05 (11) | E5 | FIXED (E5: build_primary_family) |
| E-M1 | EE dominated by strong items | verdict EE class-balanced over magnitude classes (5.1) | E5 | FIXED (E5) |
| E-M2 | item-level clustering ignores identity cells | identity-cell clustering; two-stage for held-out (5.1, 11) | E5, E8 | in progress |
| E-M3 | calibration absorbs reference abstention; conjunction; power rule | supported items only; common percentile for >= 80 % joint pass; Fisher power rule (7) | E6 | in progress |
| E-M4 | budget ratio biased | same estimator for random (LOO seeds), censoring, ratio of sums, magnitude-matched control, MDE by simulation (5.17) | E7 | FIXED (loop.py; null ratio 1.00; alpha split P4-D20) |
| E-M5 | criterion F never computed | Level B from seeds, Level C from refits; reference asymmetry stated (5.10) | E5, E10 | in progress |
| E-M6 | selection optimism, reuse of real systems | report statements (11); rounds capped at 4 (10) | report | planned |
| E-M7 | failures dropped from paired comparisons | worst admissible value, counts reported (10) | E5, E7 | in progress |

## Review H (numerics), research/phase4/reviews/H_early_review.md — 1 blocker, 6 majors

| id | finding | decision | owner | status |
|---|---|---|---|---|
| H-B1 | MEV floor in wrong units, measured outside the window | floor = same statistic as the divergence; floor states inside the window incl. float32 restart; absolute floor 0.01 (5.5) | E5, E8 | in progress |
| H-M1 | D / E / composition use the system dt for 2-dt items | per-item horizons (5.1); OOD / robustness excluded from verdict items (9) | E5, E10 | in progress |
| H-M2 | references dt-blind | sub-stepping per unit time or abstention (8) | E6 | in progress |
| H-M3 | sampling shift not OOD for real; confounded with integration | development dt nominal only; OOD by subsampling (4, 4.1) | E8 | in progress |
| H-M4 | failed / non-finite simulations stored and scored silently | refused at build, replaced; evaluator drops non-finite truth with counts (4, 5.1) | E8, E5 | in progress |
| H-M5 | host / ISA dependence outside provenance | host fingerprint in every record; pinned / gated path for real systems everywhere; replay before freeze (4) | E8 | in progress |
| H-M6 | synthetic restarts unchecked; process-noise restarts undefined | sample-time and same-system checks; counter-based noise stream (contract addendum 8) | E8, author | in progress |
| minors | lift whitening on test data, pool u, kick cost, no-op events at t_end, greedy floor, jitter truth, bootstrap replicates, served key, stale files, pool active events, whitening floor, lift restarts | distributed (E5, E6, E7, E8, E10, orchestrator: protocol.py no-op events) | various | in progress |
