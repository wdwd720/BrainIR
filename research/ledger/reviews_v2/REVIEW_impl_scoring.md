ready after these fixes

Reviewed at 356fa14 (crash change included). Ledger suite: 80 pass. Probes on synthetic data, cited below: `~/ledger_rooms_review_impl_b/tests/test_probes.py` (13 pass).

Disclosures:
- I read no label or prediction content. Running `lock.py`/`lock2.py check` on the real locks hashed files under `labels/`, `labels_v1_1/` and `predictions/`; the output was file names and counts only.
- One file, `git ls-files` output only, was written to and read from the session scratchpad under `/private/tmp/`. It is deleted.

## Blockers

**B1. Re-running the gate can turn a failed gate into a pass** (`gate_v2.py:476-495`). L14: "the gate (its script twice, S5.6), runs once. A failed gate ends the collection". `main` compares each run only with the output just before it, then overwrites that output.
- Probe A: run 1 fails condition 3; the review is rewritten; run 2 reports "differ"; run 3 matches run 2; after the checklist, run 4 exits 0 (`all_conditions_hold: true`). The last two reports look like a clean pair.
- Probe A2: a checklist signed before any gate run passes on run 1.

Fix:
- Write run 1 and run 2 to separate files that are never overwritten.
- Refuse run 1 if the checklist exists.
- Refuse run 2 unless run 1 had conditions 1-5 passing and condition 6 pending.
- Refuse a third run.
- Compare the whole condition 1-5 dicts.

**B2. Lock files can be rewritten without anything noticing** (`lock2.py:147-208`). L12: locked "before the first v2 label session", and "the lock file is never edited". Every writer overwrites its file unconditionally. Nothing chains `LOCK_scoring_v2.json` or `LOCK_labels_v2.json`. `labels2_collect.finalize` does not refuse to run after the labels lock.
- Probe H: a label is changed after the lock and `lock2.py labels` is re-run; condition 1 passes and condition 5's counts change.
- Re-locking edited scoring code works the same way and records no amendment.

Fix:
- Each writer refuses when its lock file exists.
- The gate requires one commit per lock (true for every lock today).
- The gate requires the label-code and scoring locks' `utc` to precede the earliest `runs[].start_utc` in `labels_v2/sessions/`.
- The labels lock records `scoring_v2_lock_sha256`.

## Major

**M1. `lock2.py check` accepts an amendment of any file** (`lock2.py:61-69, 231`). L12: "Rules, records, labels and predictions are never amended." Only `amend` filters paths, but anyone can append a row to `AMENDMENTS_v2.jsonl`. Probe C: `labels_v2/type_labels.csv` was edited and a hand-written row added; the file is listed as `amended` and condition 1 passes. Fix: `_chain_ok` honours only:
- paths `amend` accepts and no v1 lock hashes;
- rows allowed when written: kit files before the first session; after `UNBLIND.json`, only `crash_fix` rows for scoring v2.

**M2. Git-ignored files that a lock hashes make condition 1 fail, and the gate's clean-tree check cannot see them** (`lock2.py:42-43, 186, 201-204`; `gate_v2.py:104-109`). `.gitignore` ignores `*.parquet` and `*.log`, yet:
- the frozen `write_arm` writes `predictions_v2/B1r|B2r/replicates.parquet`;
- the frozen collector copies every file a session leaves in `out/`.

A plain `git add` leaves such files out, `git status --porcelain` hides them, and the clean checkout lacks them. Probe B: condition 1 fails with the parquet listed as `missing`, which ends the collection (L14). Run 1 hit this (`lock_verify.py`: "a git-ignored parquet"); lock2 dropped the guard. Fix:
- `predictions` and `labels` refuse a dirty tree and any untracked or ignored file.
- The gate exits 2 if an ignored file exists under `research/ledger/` (`git status --ignored`).

**M3. Scoring runs without a passing gate and without checking its own lock** (`pipeline_v2.py:98-126, 360-401`). S5: "If any condition fails, nothing is unblinded". L12 makes `LOCK_scoring_v2.json` binding. `run`:
- never reads the gate report;
- never checks its code against the scoring lock; it records three hashes, without `score_v2.py` or `aggregate.py`;
- accepts S-a, S-b or S-c before P (RUN2_PROMPT Stage 4: primary first).

Probe F: S-b ran with no gate report and no P. Fix: in `run_flag`:
- Require the run-2 gate report (B1) with `all_conditions_hold`, and record its SHA-256.
- Refuse unless `lock2.check(LOCK_scoring_v2.json)` passes.
- Require P to have ended (`P.json`, or its second crash) before any other run.

## Minor

- `pipeline_v2.py:88-90, 297-316`: S3 says "B3 and B6 are not analysed in run 2", yet B3 is analysed if it is ever locked. Put B3 in `NOT_ANALYSED_S3`.
- `gate_v2.py:285-309, 386`: verdicts are prefix-matched on the first "Verdict" line (probe E).
  - "usable only after the two blockers are fixed" passes.
  - A template line "Verdict: confirmed / not confirmed" counts as signed.
  - "signed" is accepted, though S5.6 says `confirmed`.

  Require one verdict line whose whole phrase is an allowed value.
- `gate_v2.py:17-22` and S5.1: neither tool checks archive members (`authors_zenodo_configs_pinned`). The frozen `lock.py check` does not walk that section and skips paths that do not exist.
- `gate_v2.py:312-341`: condition 3 trusts `verification.json`. Recompute the errors from `verify_truth.json` and the verifier's `verification.csv`, and check `n` against the sample.
- `score_v2.py:36-57`: an interruption (Ctrl-C, kill, sleep) leaves the marker. `amend` refuses an unchanged file, so the run can never repeat (probe G). The check also compares file mtime instead of the marker's own `utc`.
- Two texts contradict S4 after the crash change:
  - `pipeline_v2.py:30`: "one failure never stops another".
  - `score_v2.py:29`: "re-run a run whose output records an error".
- No suite test covers `--after-crash-fix` or `lock2.py amend` (probes J and J2 do).
- `IMPLEMENTATION_v2.md` has no rows for S1-S3, S6 or L14.

## Checked and correct

- The crash change: with one yes, zero yes or no clear label, S-a returns `ok` and underpowered, not a crash (probe I). The crash path allows exactly one repeat (probes J, J2).
- S4 locks, hashes and folders.
- Exposed sets from hashed files, and type-label equality.
- The primary set equals condition 5.
- S3 directions and seeds.
- Condition 2's roles match the collector.
