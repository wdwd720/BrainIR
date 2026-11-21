# PREREG v3: re-check of the audit fixes (fresh agent, 2026-11-21)

Verdict: freeze after fixes

Scope: `lock3.py`, S1-S3 against `scoring_h1`, `gate_h1.py` condition 1. Read at 8565495 and re-read at HEAD f5814fe (d0793a7
committed the centring change). Probes called `row_problem3` directly. Tests: 200 passed. I opened no banned location.

## Findings

1. **Blocker. A false `unblinded: true` unlocks the scoring code** (`lock3.py:136-145`, 223).
   - The time check rejects only flags recorded *false*. A row with `unblinded: true, crash_fix: true` on `scoring_h1/*.py` is
     honoured although no flag exists.
   - Probe: scoring code changed after the predictions lock and the first session. The row is HONOURED.
   - `amend` writes such a row itself if an empty `UNBLIND_h1.json` (or the retired copy's path) merely exists, uncommitted.
   - Every v3 lock and condition 1 then pass.

   *Fix:* honour `unblinded`/`crash_fix` only after the flag's commit. `amend` should require the flag to be committed.

2. **Blocker. The checker can amend itself** (`lock3.py:42-44, 146-149`).
   - `lock3.py` is in no frozen class. Probe: an amendment of it after the predictions lock and sessions is HONOURED.
   - The gate runs the checkout's `lock3.py`, so the amended checker judges every row, including its own.
   - Status counts the scoring tests as frozen, yet `test_scoring_h1.py`, `test_h1_end_to_end.py` and
     `test_label_side_isolation_h1.py` stay amendable until the flag.

   *Fix:* refuse every row for `lock3.py` and its tests; a checker change is a new version. Add the scoring and isolation tests to
   `SCORING_H1`.

3. **Major. A row's time is self-declared** (`lock3.py:137-142, 194`).
   - The time is the row's own `utc`, and `AMENDMENTS_v3.jsonl` is hashed by no lock.
   - Probes: a later row with a back-dated `utc` and false flags is HONOURED for `groups_h1.py` and for `gate_h1.py`.
   - Part X's "with the commit times" therefore binds only honest rows.

   *Fix:*
   - Time each row by the git commit that first contains its line, and use max(utc, that commit time).
   - Do not honour uncommitted rows.
   - Hash and list the v3 rows in the condition-1 report, as run 2 did for v2.
   - Add "each honoured row is a bug fix" to the S5.6 checklist.

4. **Major. Run 3 locks can be edited and recommitted** (`gate_h1.py:60-90`).
   - Condition 1 runs only `lock3.py check` plus the first-add times (`--diff-filter=A`).
   - Run 2's exactly-once commit test (`GV._lock_commits`) is not applied, and Part X no longer says that a lock is never edited.
   - So `LOCK_predictions_h1.json` and `_h1b.json` can be rewritten after the labels lock and recommitted; no lock chains h1b. Every
     check still passes, and the order checks still see the original times.

   *Fix:* require `_lock_commits` to pass for every h1 lock, and state the rule in Part X. Also say "never rebase lock commits":
   `%ct` is the committer time, and a rebase changes it.

5. **Minor. Session times** (`gate_h1.py:76-82`, `lock3.py:159-172`).
   - A run with a missing or unparseable `start_utc` is skipped silently; run 2 counted it as a problem.
   - Manifests are not reconciled with the audited sessions, so a missing earliest manifest moves "first session" later.
   - `check` also reads `~/ledger_rooms/run3/_manifests`, so its result depends on the machine.

   *Fix:* fail on a bad time, require a manifest for every audited session, and use only the repository's manifests in `check`.

6. **Minor. The S3 tie order is not honoured** (`pipeline_h1.py:132`).
   - `max` compares float means, and equal mean ranks often differ by 1 ulp (2,579 of 20,000 synthetic equal-sum pairs).
   - A later arm can therefore win a true tie.

   *Fix:* take the first arm with mean_pr >= max - 1e-12, and state that in S3.

7. **Minor. Recomputing from the text alone.**
   - Mean rank, top-1 and top-3 match. The centring over the analysed units now agrees with S1.
   - p, both intervals and the chance band cannot be reproduced. The text fixes none of:
     - the unit order (the unit-list order, but sorted names in the paired bootstrap, `__init__.py:112`);
     - the draw calls;
     - the percentile method;
     - the 1e-12 tolerance in "#{perm >= observed}" (`:94`).
   - S1's "units of that source" should read "with at least 3 coded primary dimensions".
   - S2's "#{ties}" should say k != h.

   *Fix:* state all of these, or declare that p, the intervals and the chance band come only from the frozen pipeline.

8. **Minor. Lock-tool traps.**
   - `lock_labels` (`lock3.py:320`) does not require both prediction locks to be committed. If it runs first, h1b can never be written
     and condition 1 never passes.
   - `amend` sets `h1_sessions_started` from the home manifests only (`:222`). On another machine it refuses a valid S6 crash fix.

   *Fix:* make `lock_labels` require both prediction locks committed. Have `amend` use `_first_session_utc() is not None`.

## Confirmed sound

- **v1/v2 locks:** `check` gives run 2's output (original `_chains`); the patch is restored in `finally`.
- **Rows:** the other run's ledger never counts; v1/v2-hashed paths are refused; a late `lock2.py amend` is caught by the v3 prereg
  lock.
- **Scoring:** standardisation, ranks and ties, top-k, p, the "predicts" and "beyond wiring" rules, the eight-arm requirement and the
  reader refusals match the text.
