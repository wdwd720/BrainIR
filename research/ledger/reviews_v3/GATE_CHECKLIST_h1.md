# Gate checklist, exam 2 (h1): PREREG v3 S5.6

This is a fresh reviewer session, run on 2026-11-21 between about 18:10 and 18:45 UTC. It checks
`gates_v3/UNBLINDING_GATE_h1_run1.json` (sha256 32d397d9...79fc, committed in 9f8cfa2) against the working tree at HEAD
9f8cfa28022a.
- The tree is clean. Nothing under `research/` is untracked or git-ignored, and under `ledger/` only caches and `.venv` are ignored.
- I wrote no file except this one and committed nothing.
- I opened no predicted value: not `predictions_h1/*/predicted.csv`, not `pools.csv`, not `data/ledger/arms_h1/`, and not
  `results/run3/`, which does not exist. I did not open `reviews_v3/STAGE2_REVIEW*.md`. The lock tools and my hash scans read
  prediction files only to hash them.
- The recomputations use my own scripts. They live in a scratch directory, are not committed, and print aggregates only. This
  checklist names no label cell value.

All 187 input hashes in the run 1 report (the `inputs_sha256` of every condition) equal the current files. The recomputations
below therefore use the same bytes as gate run 1.

## 1. Every lock verifies, and each run 3 lock is touched by exactly one commit: confirmed

- **Run 3 locks.** `lock3.py check` exits 0 for all five, with `changed` and `missing` empty and `amendment_rows_ignored` empty:

  | lock | files checked |
  |---|---|
  | LOCK_prereg_v3 | 142 |
  | LOCK_labelcode_h1 | 41 |
  | LOCK_predictions_h1 | 154 |
  | LOCK_predictions_h1b | 77 |
  | LOCK_labels_h1 | 144 |

  The only amended file is `ledger/scripts/reliability_v1.py` in LOCK_predictions_h1. It is the v3 row of item 8.
- **v1 and v2 locks.** `lock2.py check` exits 0 for all nine, with `changed` and `missing` empty:

  | lock | files checked |
  |---|---|
  | LOCK_prereg_v1 | 81 |
  | LOCK_predictions_v1 | 183 |
  | LOCK_labels_v1 | 254 |
  | LOCK_labels_v1_1 | 222 |
  | LOCK_prereg_v2 | 114 |
  | LOCK_labelcode_v2 | 45 |
  | LOCK_scoring_v2 | 17 |
  | LOCK_predictions_v2 | 93 |
  | LOCK_labels_v2 | 698 |

  - Through run 2's ledger only two files are amended: `ledger/scripts/b4v2.py` (prereg v2) and
    `ledger/scripts/labels2_rooms.py` (labelcode v2).
  - Fourteen files in snapshot sections are reported only: 4 in prereg v1 and 10 in prereg v2. These sections are not binding by
    design, and the count equals gate run 1's.
  - The frozen `lock.py check` also exits 0 on the four v1 locks (S5.1).
- **One commit per lock.** `git log --all -- <lock>` shows exactly one commit for each of the 14 lock files. The run 3 lock commits
  are the same as in the gate report: prereg_v3 554222a, labelcode_h1 a175625, predictions_h1 7056028, predictions_h1b 07ed4c0,
  labels_h1 4bc7330.
  - With `--follow`, three locks list a second commit. That comes from git's copy detection (C074, C081, C055 from an earlier lock
    file), not from a second change to the path.
  - `LOCK_reliability_v1.json` does not exist yet, and it is optional for the gate.
- **Order from commit times.** These are committer-clock times; author time equals committer time on each lock commit.
  - labelcode_h1 (10:23:18Z) and predictions_h1 (12:49:14Z) both precede the first h1 label session (12:49:29Z). That start time is
    the earliest `runs[].start_utc` among the 16 manifests in `labels_h1/sessions/`.
  - The live room manifests on this machine cover the same 16 sessions with the same start times, and no other run 3 room exists.
  - predictions_h1b (18:25:07Z) precedes labels_h1 (18:25:19Z).

## 2. No session that contributed a final record breached, and every audited session has a manifest: confirmed

- **Contributing sessions.** The `source_sessions` column of `records.csv` (79 final records) names 10 sessions: R1- and
  R2-harris-a/b, R1- and R2-soffers-a/b, ADJ-harris and ADJ-soffers.
  - All 10 are in `transcript_audit.json` with `breach: false` and no issues.
  - That audit covers 14 sessions and the verifier audit covers 2 more (verify-1, verify-2). None of the 16 breached.
  - `saw_model_prediction` is false on all 79 final records and on every paired raw record.
- **Manifests.** All 16 audited sessions have a manifest in `labels_h1/sessions/` with a parseable start time. There are 16 manifests
  and no extra ones.
- **Transcript spot check.** I read the tool inputs only of the 16 session transcripts (`~/ledger_rooms/run3/*.main.stream.jsonl`).
  - The tool-call counts equal the audit's for every session.
  - No tool input names an absolute path outside the session's own room, apart from its own tool results.
  - No tool input names this repository, a prediction location, run 2's rooms, GitHub or Zenodo.
  - The search sessions, which contributed no record, fetched only literature hosts.

## 3. The label review has no blocker, and the verification error rate is at most 10 %: confirmed

- **Review.** `reviews_v3/LABEL_REVIEW_h1.md` (sha256 dbc90533...b074, the bytes gate run 1 hashed) has exactly one verdict line,
  line 6. It reads "usable with caveats".
  - The review's findings are 2 majors and 6 minors. The word "blocker" does not occur in it.
  - The two majors are caveats under the frozen label code (LOG L91) and are reported with the results. One is that within-reading
    de-duplication dropped 5 Soffers records; the other is that one Harris figure was read at low resolution.
- **Verification sample.** I recomputed it with my own code. Drawing with `default_rng(20261313).choice(..., 30, replace=False)` from
  the 60 eligible `whole_two_sided` final records, sorted by id, gives exactly the 30 ids in `verify/to_verify.jsonl`.
  - The verifier's input carries no dimension field.
  - verify-2 returned all 30 records.
  - Of the 148 cells that the sampled records code yes or no, 6 differ from the verifier; none is `cannot_verify`. The error rate is
    0.0405, below the 0.10 limit.
  - verify-1 produced no output because a safety classifier stopped it (LOG L88). Both verifier sessions are audited and neither
    breached.

## 4. Kappa between the two readings is at least 0.7: confirmed

- **Inputs.** I used my own code on `pairs.csv` and the eight `raw/reading/*/records.jsonl` files (157 records).
  - There are 73 pairs, all R1 against R2. Every id is found in the raw readings, and no id is used twice.
  - No pair involves a breaching session.
- **Cells.** The 12 primary dimensions are used, with d7p derived per record from d7 and d8 as specified. 271 cells are coded yes or
  no by both readings.
- **Result.** Observed agreement is 0.99262 and chance agreement 0.70374, so Cohen's kappa is 0.9750896222. The gate reports
  0.9750896222079235 over 271 cells and 73 pairs.
- **Per source** (descriptive only): Harris 0.924 over 90 cells, Soffers 1.000 over 181 cells.

## 5. At least 20 units have at least 3 coded primary dimensions: confirmed

- `consensus.csv` has 28 unit rows. Every name is in `hl_units/UNITS_v1.csv` (43 units), and the columns are `d1` to `d15` plus
  `d7p`.
- 27 units have at least 3 primary cells coded yes or no; one unit has fewer. There are 193 coded primary cells in all.
- The count of 27 matches the gate, LOG L87 and the label review.

## 6. Nothing has been joined: confirmed

- **Label-side code.** These files name no prediction location: `ledger/scripts/labels3_*.py`, `gate_h1.py`,
  `ledger/src/brainir_ledger/labels_h1/` and `posthoc/labels_sensitivity.py`.
  - "Prediction location" here means `predictions_h1/`, `predicted.csv`, `pools.csv`, `arms_h1`, `results/run3`, or a scoring or
    prediction module.
  - The only hits are the lock file names whose commit times the gate reads, and the canary's planted fake file.
  - `test_label_side_isolation_h1.py` passes 4 of 4, run without caches.
- **The gate.** `gate_h1.py` reads label files, the unit list, session manifests, the audits, the review and the amendment ledger.
  - It runs the lock checkers as subprocesses. They only SHA-256 the bytes of the files they hash (`lock2.sha`) and print paths.
  - The helper it imports from `gate_v2.py` reads a v2 prediction table only in run 2's own condition 5, which `gate_h1.py` does not
    call.
- **Label data.** I scanned the 156 files under `labels_h1/`, `reviews_v3/`, `gates_v3/`, `kit_v3/` and `hl_units/`.
  - None has the SHA-256 of any of the 85 prediction files recorded in LOCK_predictions_h1 and LOCK_predictions_h1b.
  - No `labels_h1` CSV has a column that looks like a prediction, and no `labels_h1` file names a prediction location.
  - Prediction values are fractions. The only decimals of the form d.ddd in `labels_h1` are the agreement and error-rate statistics
    in `agreement.json` and `verification.json`.
  - LOCK_labels_h1 names no `predictions_h1/` path, and the prediction locks name no `labels_h1/` path.
- **No joined file.**
  - Neither `UNBLIND_h1.json` nor `results/run3/` exists, on disk or in any commit on any ref. There is no stash and only one
    worktree.
  - The tracked files that name both a prediction table and a label table fall into four kinds:
    - code that joins only after the flag: `scoring_h1/pipeline_h1.py`, and `posthoc/results_h1.py`, which refuses without
      `results/run3/primary.json`;
    - synthetic tests;
    - `lock3.py`, which only hashes;
    - prose (PREREG_v3, LOG, STATE, PREREG_AUDIT), which mentions paths only.
  - Outside `labels_h1/`, a pattern scan finds (unit, dimension, value) triples only in `LABEL_REVIEW_h1.md` and in label-test
    fixtures. `STAGE2_REVIEW*.md` was not part of that scan.
  - The `UNBLIND_h1.json` files under the pytest temporary directory are synthetic fixtures. None of the 10,244 files there equals a
    locked prediction file or any real `labels_h1` file.
- **Disclosed, not a join.** After the primary predictions lock, the orchestrator was twice exposed to a few consensus cells
  (LOG L91, L92). That is not a file join under S5.6.
- **Reviewer's disclosure.** My join scan read every tracked text file with a regex, including `STAGE2_REVIEW*.md`, and printed
  file names only. Nothing from those files was shown to me.

## 7. No hemilineage simulation predates the freeze: confirmed

- **Freeze time.** `git log -1 --format=%cI ledger-prereg-v3` gives 2026-11-21T02:23:18-08:00 (10:23:18Z), commit a175625.
- **Campaign manifests.** The `utc` of every hemilineage campaign in `data/ledger/gha/<campaign>/manifest.json` is after the freeze:

  | campaign | manifest utc |
  |---|---|
  | hm-run3 | 10:24:42Z |
  | hmdet-run3 | 10:24:57Z |
  | hc-101 to hc-105, hc-201 to hc-205 | 10:25:23Z to 10:28:27Z |
  | hsens-run3 | 10:28:39Z |
  | hd-run3 | 10:28:57Z |

  - Their `git_head` commits (d636200, 5a87662, b40814f) all descend from the freeze commit.
  - The r3 and r4 campaigns, which simulate descending-neuron types, are also after the freeze (10:29:12Z to 10:31:14Z).
- **Tags.** The `gha3-run-*` tags are lightweight, so `creatordate` is the tagged commit's date.
  - The earliest hemilineage campaign tag is dated 02:24:08-08:00.
  - 47 of the 48 gha3 tags point at descendants of the freeze commit, so none of them can predate it.
  - The exception is `gha3-run-p7-run3` (01:15:53-08:00). It is the P7 pipeline test of DNg100, DNb08 and random groups, and none
    of its 54 job keys names a hemilineage unit. Part D.3 allows it.
- **Registry before the freeze.** `gates_v3/REGISTRY_BEFORE_FREEZE.json` was committed in f5814fe (02:06:09-08:00), before the
  freeze. It records 55 result files, 129,854 result keys, 9 campaign manifests (11,558 keys), and 0 hemilineage or run 3 arm keys.
- **My recheck of the registry.**
  - The 9 pre-freeze manifests hold no key that names a hemilineage unit.
  - Exactly 55 `results.pkl` files have an mtime before the freeze, all in exam 1, run 2, trust or P7 directories.
  - No file under `data/ledger/arms_h1/` or a hemilineage campaign directory predates the freeze. The earliest mtime under
    `arms_h1` is 04:44:31-08:00, read with stat only.

## 8. Every honoured row of AMENDMENTS_v3.jsonl is a code bug fix, and its new hash first appears on its own line: confirmed

- **One row, honoured.** `AMENDMENTS_v3.jsonl` (sha256 a15f9ef8...ddc9, the bytes gate run 1 hashed) has one row. It was added in
  1ade311, the only commit that touches the file.
  - The row is honoured: `lock3.py check LOCK_predictions_h1.json` lists `ledger/scripts/reliability_v1.py` as amended, and no lock
    ignores a row.
- **Hashes.** `old` dea1e403... is the file at `old_rev` 064bb51. `new` 73c51807... is the file at 1ade311, and the file is unchanged
  since.
- **A bug fix.** The diff changes 7 lines in `r3()`.
  - Before: an `except FileNotFoundError` that could not fire, because run 2's `read_log` returns an empty log for a missing file;
    the analysis then raised KeyError.
  - After: an explicit check that the results file exists, and a skip for empty results.
  - No rule, label, prediction or threshold changes, so the row is a code bug fix.
- **Allowed.**
  - The file was first committed after the freeze (b40814f), so no v1 or v2 lock hashes it.
  - It is not in lock3's prediction-side or scoring list, and no ledger module imports it.
  - It is not label code, kit or the lock tool.
- **Flags match the commit times.** The row's utc is 14:38:20Z and its commit 14:38:33Z; the row is timed at the later of the two.
  - It comes after the predictions lock (12:49:14Z) and the first session (12:49:29Z), so `predictions_locked` and
    `h1_sessions_started` are correctly true.
  - `unblinded` is false, and no flag exists on any ref.
  - `crash_fix` is false.
- **First appearance.** `git log -S 73c518071b0d28f54fc1b5235a0b22794c76a9477fafdb6c4ec18a5bc5ef58b0 --format='%h %cI' --
  research/ledger/AMENDMENTS_v3.jsonl` returns only `1ade311 2026-11-21T06:38:33-08:00`, the commit that adds this row as line 1.
  - Across all refs and files, the hash first appears in that same commit, and there is no earlier row.

Verdict: confirmed
