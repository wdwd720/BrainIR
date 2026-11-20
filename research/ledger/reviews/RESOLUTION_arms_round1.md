# Resolution of the arms review, round 1 (`REVIEW_arms_round1.md`)

| # | finding | resolution | where |
|---|---|---|---|
| 1 | G4 not yet run for the locked simulated campaigns | G4 run on every locked simulated campaign (B1-lo5, B1-lo10, B5, B2, B4, the ten controls; unbatched re-runs of 100 jobs each); each JSON records how many re-runs landed on the other host type. An arm is locked only if its G4 passes. | `gates/G4_*.json`; 72dd30b (crossover field) |
| 2 | `lock.py check` misses untracked locked files and empty arms | New, unhashed verifier `ledger/scripts/lock_verify.py`: lock file in the tag = working tree; every hashed file (arms, gates, reviews, code) tracked in the tag with the locked hash; every arm has `types.csv`; a clean worktree checkout of the tag passes the frozen `verify_inputs` against the real lock and a placeholder labels lock. Run on the lock commit before tagging, and on the tag after. Parquet files are added with `git add -f`. | 3e52e02; `LOCK_predictions_v1.verify.json` |
| 3 | "NumPy AVX-512 dispatch disabled" inaccurate | Logged as a correction; the environment record lists the features NumPy actually dispatched per campaign; determinism rests on the cross-host G4 evidence. | LOG L27(b) (fbd9756); `gates/ENVIRONMENT.json` |
| 4 | No environment record in the predictions lock | `ledger/scripts/environment_report.py` writes `gates/ENVIRONMENT.json` (orchestrator fingerprint, Modal image spec, and per campaign: results, errors, Python/platform/library versions, numerics environment, AVX-512 share, dispatched features, container settings incl. batch size), hashed through `gates/`. Regenerated after the last campaign. | 3e52e02 |
| 5 | A0 replicates per neuron, B0 without `manc_type` | A0 `replicates.parquet` is now the long table (933 x 128 rows: manc_type, bodyId, row, replicate, score, n_active_notebook, usable; per-neuron summary in `A0/neurons.csv`); B0 replicates carry `manc_type` and `bodyId`. | 35ba697 |
| 6 | B5 `mean_score` was a maximum | Set to None (the maximum over strengths stays in `primary_score` / `best_score`). | 35ba697 |
| 7 | B2 mapping weaknesses | No code change (the rule is pre-registered). B2 `provenance.json` records the mapping counts (1,236 DNs mapped: 1,215 by body match, 21 by the `mancType` string; 278 body matches disagree with the string; 18 groups not in A1); listed in `gates/ARM_DIAGNOSTICS.md` and the handoff. | 35ba697; dee11a0 |
| 8 | LOG L16 overstated "thresholds unchanged" | Correcting entry. | LOG L27(a) (fbd9756) |
| 9 | `B1/provenance.json` does not hash `selection.json` | Accepted: the predictions lock hashes `selection.json`; no writer is re-run. | — |
| 10 | Writers embed `written_utc` | Procedural rule: no writer runs after the lock (STATE checklist). | STATE.md |

Found after the review by the orchestrator's own pre-lock checks (prediction side only, DNg100/DNb08 by name): B2's DNg100
positive control fails under the pre-registered tuning although the network reproduces the paper's MaleCNS rhythm at the
paper's current; B4's `halts` mostly reflects over-excitation. Neither arm is changed (PREREG 12); both are documented in
`gates/ARM_DIAGNOSTICS.md` (dee11a0) and sent to the reviewer for round 2.
