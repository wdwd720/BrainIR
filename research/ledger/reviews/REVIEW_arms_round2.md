# Independent review of the prediction arms, round 2 (delta, before the predictions lock)

Reviewer: the same fresh subagent as round 1, resumed with the diff since its review (48edd9a..HEAD), the new outputs (B2,
B4, B5, the finished controls, G4 files, ENVIRONMENT, G5, ARM_DIAGNOSTICS, B2_DNG100_CHECK) and seven questions. Read-only;
no Modal jobs; no `UNBLIND.json` created in round 2 (it discloses that its round-1 dry run created a synthetic one inside its
own scratch directory and deleted it); no score shown next to an outcome. Returned 2026-11-20 ~00:55 PST. Report condensed;
every finding kept. Resolution: `RESOLUTION_arms_round2.md`.

**Verdict: LOCK**, provided the remaining eight controls each pass its control check (log complete, 5,136 records = unique
keys = expected, 0 errors, payload key = the control's own matrix, one replicate row per key with the log's digest,
byte-identical re-aggregation, `results_log_sha256` matches, 321 types without NaN, **G4 100/100**); `ENVIRONMENT.json` and
`PREDICTIONS_SUMMARY.json` are regenerated and everything is committed before `lock.py`; the lock command names all ten
controls explicitly; `lock_verify` passes on HEAD before tagging and on the tag after; the dry run is repeated with all ten
controls. Agrees with locking B2 and B4 exactly as pre-registered.

## Findings

1. **major (procedural)**, the planned lock command; `lock.py` argument parsing; `lock_verify.py` default tag.
   `B1-ctl-rewire-101..105` is not shell expansion: `lock.py` would lock one arm literally named so, with no files, and the
   frozen `verify_inputs` then refuses the whole scoring run. `lock_verify.py` defaults to `--tag ledger-predictions-v1`,
   which does not exist before tagging. Fix: name the ten controls explicitly; commit everything `lock.py` hashes first;
   run `lock_verify.py --tag HEAD` on the lock commit, tag, run it again on the tag.
2. **minor**, `backend.py` NUMERICS_ENV, PREREG 10 ("single-threaded BLAS"), LOG L28 ("same environment"), `jobs.py`
   run_batch. Batched containers ran with `OPENBLAS_NUM_THREADS` / `OMP_NUM_THREADS` / `MKL_NUM_THREADS` = 4, not 1 (all of
   B2, 22,382 of B4's results, 1,467 of rewire-101's, all of rewire-102/103); the `setdefault` in `run_batch` changes
   nothing. 252 job pairs run with 4 threads against 1 thread (G4 B2 100, G4 B4 100, G4 rewire-101 36, the batched B1-lo10
   test 16) all have identical digests. Fix: a LOG correction; make each remaining control's G4 (its 4-versus-1 test) a hard
   lock condition.
3. **minor** (tested), `jobs.py` run_batch. If a worker process dies, `multiprocessing.Pool.map` hangs; on Modal the batch
   would run to its timeout and be retried twice before its 4 keys count as missing and `run_campaign` re-runs them.
   Malformed items return error records with their key; no partial or duplicate results are possible; the finished batched
   campaigns had 0 infrastructure errors. Fix: none for the lock; a `ProcessPoolExecutor` or a per-job timeout for later
   campaigns.
4. **minor**, `gates/ARM_DIAGNOSTICS.md`. Every number reproduces, but the cited `PREDICTIONS_SUMMARY.json` did not exist
   yet; no committed script computed the mapping split, the zero-MN / start-current fractions, the 199/8 split or the
   2,787; "2,787 exceed the screen's upper bounds" uses B4's stock verdict bounds (cap 100); under B1's cap 200 it is 2,757,
   and 899 replicates exceed 1,500 active neurons. Fix: commit the code, state the bounds, generate the summary after the
   last control.
5. **minor**, `b2_dng100_check.py`, `B2_DNG100_CHECK.json`: computed on the Mac (arm64), not on the locked Modal platform,
   and not recorded. The reviewer's re-implementation matched all 16 values; the pair-at-256 counts equal B2's Modal
   replicates for seeds 0-3. Fix: record the platform.
6. **minor**, `RESOLUTION_arms_round1.md`: row 1 claimed G4 on all ten controls (2 of 10 at the time); row 2 cited the
   verify report that can exist only after the tag. Fix: make row 1 true before locking; word row 2 as "written after the
   tag".
7. **minor**, `gates/ENVIRONMENT.json` stale (generated 00:06); the stopped first segments of rewire-101 (3,669 results) and
   B4 (434) have no `backend_stats` line. Fix: regenerate after the last campaign; the per-result thread setting tells the
   segments apart.
8. **minor**, `lock_verify.py`: covers the only prediction-side way scoring can refuse, but imports `verify_inputs` from the
   working tree rather than the tag, does not exercise the analyses (the dry run does), and cannot cover label-side
   refusals or a run 2 that uses modified scoring code. Fix (optional): import from the checkout; in run 2, run
   `lock.py check LOCK_prereg_v1.json` in the tag checkout before scoring.
- Nit: `A0/provenance.json` does not hash `A0/neurons.csv` (written after `write_arm`); the predictions lock will.

## Item 7 (B2 and B4): agree, lock as pre-registered

PREREG 12 forbids amending a stage with data; the G2 precedent (PREREG 9) is "locked as it is, and the disagreement is
reported"; the prompt's "do not lock B3" is tied to a pre-registered gate, and B2/B4 have none. B2 passed G4 and the
network check at the paper's current (reproduced); DNb08 is a driver in B2 (0.78); the failure is the pre-registered tuning
rule transferred to MaleCNS, not a broken arm. B4's calls recompute exactly. Dropping either arm now would be a
data-dependent choice. Required: a LOG decision entry before the lock and both weaknesses prominent in the handoff.
Optional: freeze the per-type B4 halts split and the B2 mapping split in `gates/` before the lock.

## Verified, no finding (condensed)

- Batched execution: nested shared-payload resolution and attribution by key; B5, B4, B2, rewire-101/102/103 logs read to
  the end, records = unique keys = expected (25,680; 22,816; 5,248; 5,136 each), 0 errors, 0 duplicates; the resumed
  segments are complete; one replicate row per key with the log's digest; `types.csv` and `replicates.parquet`
  byte-identical to a fresh re-aggregation (B5, B4, B2, rewire-101/102); `results_log_sha256` matches; each campaign's
  shared-payload key equals that of its own matrix.
- Writer changes: A0 long table (119,424 rows) matches every raw cell; B0 replicates unchanged apart from correct keys; B5
  `mean_score` empty, primary = `best_score`; B2 mapping counts confirmed; A1, A1-lo10, A0, B0, S, B1 `types.csv`
  byte-identical to round 1; PREREG 11 consistent.
- New tables: B2 328 types, B4 475, B5 321, controls 321 each, no NaN primary scores; B4 calls recomputed independently,
  0 mismatches over 1,425; `n_base_rhythmic_128` = 16; 0 solver failures in B4/B5; B5 = B1 on 7,091 of 7,091 shared runs;
  B2 DNg100 group 2 members (10045, 10056), status ok; controls vs B1 Spearman -0.015 and 0.015, shared primaries all 0.
- ARM_DIAGNOSTICS claims all reproduced (B2 DNg100 0.059 etc.; acceptance fractions; B1-B2 agreement and mapping split;
  B4 halts 199/8 under three definitions, 3,239 losing replicates; B5 DNg100 per strength).
- `lock.py check LOCK_prereg_v1.json` clean at HEAD. Status-only scoring dry run (verify_inputs, primary, secondary called
  directly, no flag file) on copies of all 14 real arms present: 59 files verified, primary ok, 25 analyses ok, 2 not locked
  (B3, B6).
- Leakage: none; only DNg100/DNb08 examined by name; no arm changed; Stage 2 (incl. the movies session) not started.
