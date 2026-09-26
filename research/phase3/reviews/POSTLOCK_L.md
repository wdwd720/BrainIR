# Post-lock review L: leakage and process integrity (answer-aware)

Reviewer L, the post-lock counterpart of review F. I ran as an answer-aware subagent in the main repository. This report goes to the
orchestrator only.

**Snapshot.** Evidence was collected between about 10:40 and 11:25 UTC on 2026-09-26, at HEAD `95fd31f` plus the orchestrator's
uncommitted edits made during the review (the retrospective rows of HIDDEN_EVALUATIONS.md and the `final_b_H` START row).

**What I wrote.** This file only. Running the transcript audit rewrote `research/phase3/reviews/transcript_audit.json`, as expected; a
copy of the previous version is in the orchestrator scratchpad under `postlock_L/`. The self-audit re-runs wrote their JSON and
Markdown into the same scratch directory (`--out-dir`), so the merged `SELF_AUDIT.{json,md}` is untouched. I copied nothing into any
room and printed no secret. The salt value never appears in any output: only its sha256, which is already public, is used.

## Summary verdict

**No blocker.** The process holds on every point of the contract:
- **Lock ordering.** The method lock was written, committed and tagged before every hidden evaluation and before any salt-derived
  hidden data existed.
- **No post-hidden tuning.** Every hidden result was produced by the locked bytes, the locked default configuration, and the locked
  seeds and budgets. Nothing was folded into v1 after a hidden evaluation.
- **Locks.** All four locks verify.
- **Salt.** It was revealed only after Level C and the hidden-draw search, and it matches its commitment.
- **Rooms and sessions.** The rooms and every agent stream are clean. After the lock, the only agent sessions were post-lock
  reviewers S, C, Y and R, and none of them touched a forbidden path.
- **Modal fit volume.** It holds public fit views (train / val only), method snapshots, fitted models, and the public tier-A bundle,
  which the version-3 amendment permits.
- **Hidden data on Modal.** The real hidden data went to Modal under a policy amendment made about 2.5 h before any salt-derived
  data existed.
- **Self-audit.** The three failures (I3, I8, I11) are check artefacts. I verified each property independently.
- **Execution wrappers.** The post-lock wrappers (`hidden_gen_gate.py`, `level_c_fast.py`) change no hashed file, no job and no
  computation code; they only change where and in what order jobs run. Both were decided before the results they affect existed.

**One MAJOR finding: a statement in the report must be corrected.** The claim that the FINAL suite "had never been used" at the lock
is not literally true. An orchestrator-side precompute of reference controls touched 2 FINAL systems before the lock; it was
aborted, and its output is unused. The remaining findings are MINOR: documentation, wording and provenance.

## BLOCKERS

None.

## MAJOR issues

**M1. The FINAL suite was touched before the lock by an undocumented reference-control precompute. The "never used" statements must
be qualified.**

Evidence:
- **Launch.** Orchestrator transcript, 2026-09-25T08:32:36Z: "All 48 heldout reference sets are precomputed. Starting the same for
  the final suite at low priority". Command at 08:32:40Z: `scripts/p3/precompute_refs.py --suite final --workers 2`.
- **Stop.** At 08:58:46Z the precompute was stopped as "wasted work" (TaskStop 08:58:49Z), because the evaluator revision
  (benchmark v2) would change the reference controls.
- **Output: 4 files for 2 of the 48 FINAL systems,** written 08:56:27Z-08:57:08Z in `research/phase3/tournament/_refcache/final/`:
  - `refs_syn-0cf4f43f95_s0.json`, `refs_syn-0cf4f43f95_k1_s0.json`;
  - `refs_syn-00d5084cf9_s0.json`, `refs_syn-00d5084cf9_k1_s0.json`.
- **Content.** The k-independent reference controls (`full_state`, `input_only`, `persistence`, `readout_hist`), fitted on the
  public part and evaluated on the FINAL held-out material. The frozen `precompute_refs.py` calls `suite_eval.reference_results`.

Impact:
- No method was fitted or evaluated, nothing was selected, and nothing reached any developer.
- No later run ever reads these files. They use the pre-version-2 cache name without the evaluator code tag, while
  `suite_eval.reference_results` reads only `refs_<sid>_s<seed>_<codetag>.json` (lines 217-219). They are 4 of the 377 files in that
  directory; the other 373 were written from 02:08 UTC on 2026-09-26, during the confirmation.
- No result is affected.

The statement is inaccurate in three places:
- PHASE3_REPORT.md section 4.2 (line ~246: "the FINAL suite had never been used");
- PHASE3_REPORT.md section 7 (line 454: "At the lock, the FINAL synthetic suite had never been used ... (self-audit I9)");
- the hashed PROTOCOL.md header and `BENCHMARK_LOCK.json` `supersedes.reason`, which cannot be edited.

Self-audit I9 cannot support the claim: it reads only the HIDDEN_EVALUATIONS rows and the mtime of the hidden manifest. The LOG does
not mention the precompute.

Correction: reword both report sentences as "no method had been fitted or evaluated on the FINAL suite", and add a LOG entry and a
footnote. Suggested footnote: "An orchestrator precompute of k-independent reference controls ran on 2 of the 48 FINAL systems on
2026-09-25 (08:32-08:58 UTC) and was aborted; its 4 cache files use a superseded cache key and are never read."

## Minor issues

**m1. A fake-salt dry run left 126 `"source": "hidden"` records in the production store.**
- The records are in `data/phase3/store`, written 2026-09-25T06:13:54Z-06:14:41Z, all for `real:net1:mech:02fa13b8`.
- Their origin is `scratchpad/dryrun_hidden.py` (salt `FAKE-SALT-for-a-dry-run`; log: "126 hidden trajectories"). The script
  redirected `generate_real_hidden.DATA` to a scratch directory. Its spawn workers re-imported the module, so `_run` wrote to the real
  store.
- 0 of 126 params seeds match `hidden_seed(committed salt, ...)`, whereas all 1,761 post-lock local records do. None of the 126 is
  in the final dataset. **This is not real hidden data and not a leak.**
- It is undocumented, and it corrupts any count by `source`. The orchestrator's own check at 2026-09-26T05:49:50Z counted 1,525
  "hidden" records, 126 of which are fake.
- Fix: document it, and delete or relabel the 126 index rows and files. The keys are listed by the record mtimes above.

**m2. Hidden-data generation: three local starts, and one inaccurate amendment sentence.**

Three post-lock LOCAL runs of `generate_real_hidden.py --backend local` preceded the Modal dataset:

| start (UTC) | workers | how it ended |
|---|---|---|
| 01:46:43Z | 5 | stopped by the orchestrator at 01:48:02Z |
| 01:48:14Z | 12 | stopped with the host's memory stop, about 02:05Z |
| 05:46:54Z | 8 | stopped by the orchestrator at 05:56:05Z |

Together they left 1,761 salt-derived trajectories in the local store, from 01:46:57Z to 05:56:07Z. No dataset was written.

What the record says:
- The LOG chronology describes the first two starts. P3-D26 mentions "a first local run". The report (section 11) speaks of "a
  stopped local (Windows) run". The third start is recorded nowhere.
- LEAKAGE_POLICY.md §3.1 says the host-gated amendment was made "before the hidden data existed". In fact the text was edited at
  05:59:43Z (transcript; file mtime 22:59:43 PDT), after those 1,761 local trajectories, and was committed at 06:19:44Z, 3 minutes
  after `hidden_gen_gate.py generate` was launched (06:16:27Z).

The substance is fine:
- The permission to generate on Modal is the version-3 amendment (commit d056d35, 2026-09-25T23:19:47Z), made before any
  salt-derived data existed.
- The gate is only a restriction.
- No hidden data existed on Modal before 06:17Z (the eval volume's `/real_hidden_build/store` is dated 06:17Z).

Fix:
- reword the amendment as "before any hidden data existed on Modal (partial local records existed)";
- list the three local starts in the LOG and in report section 11 ("generated once" is true of the dataset only).

**m3. Hidden-evaluation log: complete now, but partly retrospective. The report should say so.**
- At the start of this review the log had no DONE rows for the four synthetic FINAL counterexample sweeps or for the FINAL
  ablation re-run.
- It had no row at all for:
  - the review-G run on the locked method (`review_g_locked_v3`, launched 09:58:24Z, results 10:07:20Z), which ran on secret-seed
    trap material;
  - the real-public sweeps, which ran on post-lock fits.
- The orchestrator appended 10 rows at about 11:10Z, marked "[retrospective row]", after post-lock review R (M6).
- I verified every retrospective time against the run's own SUMMARY write time: all match to the second, for example
  `final_brainir_state_v1_effect` at 06:13:53Z and `ablations_final` at 09:33:23Z.
- The failure counts match `ablations_final/SUMMARY.json`: full fits 4, sharing_test evaluations 3.
- Report line 43 ("Every hidden evaluation is logged") should add that 10 rows were appended retrospectively on 2026-09-26.

Two further wording points in the log:
- **The ABORTED row** (06:23:08Z) says "nothing was written or read back". The aborted attempt did write `fitview_final/` and 48
  staged copies of the confirmation's full-method fits (`--full-from`), byte-identical: 98 files, all at 06:17:13Z. It computed no
  result, so the substance holds.
- **The Level B DONE row** says the launcher shell "was stopped by the host ... at about 02:00 UTC". Yet `final_b_launch.log` says
  "all done" at 02:49:45Z, so the launcher script itself completed. There are no `.try*.log` files, so there was no retry either way.

**m4. Snapshot provenance is incomplete in the run records, and two hash conventions coexist.**

Hash conventions:
- `tournament.py` records RAW sha256 of the snapshot. METHOD_LOCK.json records LF-normalised sha256.
- 19 of the 30 locked files have CRLF line endings in the working tree; the git blobs are LF.
- The `method_hashes` of all 13 FINAL parts therefore do not string-match the lock. They do equal the raw hashes of the locked files,
  30 of 30 in every part, and each part's snapshot has Modal methods key `2f4ad2d3ddf2df33`, the same as the locked directory.
- A fresh checkout of the tag produces LF files with a different methods key. The code is identical.

Records without any snapshot identity:
- Level C (`level_c_results.json`, `modal_costs.json`), the ablations, the counterexample sweeps and review G's run record neither
  the method directory nor its hash.
- I had to reconstruct them from the orchestrator transcript: every command used `--method-dir phase3/src/brainir_state/methods`
  (Level C at 07:29:51Z, `run_l4b.cmd`, the sweeps, review G) and the fits of the `final_b_*` or `level_c_01` runs.
- The fit volume confirms it: its newest methods tar is the locked key, uploaded 2026-09-26T01:04:41Z by round 3, and nothing was
  uploaded after the lock.

Fix: record `methods_key`, the raw and LF hashes and the tag commit in every post-lock record.

**m5. Timing and disclosure of the execution decisions P3-D26 and P3-D27 (substance verified; see "What I verified", item 8).**
- **P3-D27** was committed (2d251ad, 07:35:02Z) after Level C was launched (07:29:51Z). The scheduler file is final since 07:28:26Z
  (mtime) and byte-identical to the committed version.
- **Platform choice after the confirmation results.** Both gate decisions were made after the orchestrator had read the Level B
  confirmation results: exact-k 27 of 46 against 16 of 46 at 05:50:57Z. The evidence behind them is public only:
  - 13 of 20 public protocols not bit-identical on the ungated path;
  - 60 of 60 identical on the gated path;
  - public-fit repeats in `levelc_fast_validation.json`.
- **Numerical effect of the gate.** It restricts fits to non-AVX-512 hosts. P3-D27 shows that host class changes the locked method's
  delay configuration, whereas PROTOCOL §10 pre-registered last-digit differences only. Report §12 discloses the reproducibility
  finding.
- Recommendation: also state that the platform choice was made after the confirmation results were known, on public evidence only.

**m6. Stale or contradictory documentation, and hidden data retained on Modal.**
- LEAKAGE_POLICY §3.1, "Volumes" bullet: "No real hidden data ... is uploaded". The later amendments in the same section contradict
  it.
- POSTLOCK_RUNBOOK L3c and its "Numerical equivalence" item 2, as at the tag, state three things that the hashed PROTOCOL §10 and
  the version-3 amendment contradict:
  - evaluations run locally because §3.1 keeps real hidden data off Modal;
  - the hidden data are generated locally;
  - any Modal move uses a separate volume `brainir-p3-hidden`, deleted after Level C.
  This is why report §12 calls the Modal generation a "deviation from the runbook".
- The hidden data are still on `brainir-p3-eval`:
  - `/suites/real/hidden`;
  - `/real_hidden_build/{store, micro, dataset.tar}`;
  - `/_smoke` (public protocols).
  No rule requires deletion, but a retention decision should be recorded before any later phase reuses the account.

**m7. Check and tool weaknesses (no property violated).**
- **BENCHMARK_LOCK.json** still carries `git_tag: state-discovery-benchmark-v3` although the file is the re-lock-2 version. This is
  the root cause of the I3 failure.
- **`method_lock_p3.py --check`** silently skips a missing input file (`if (ROOT / k).exists() and ...`). It checks neither the
  tag nor the environment hashes. I checked both by hand; all match.
- **I6 and I7** scan only `BrainIR_p3clean` and `BrainIR_p3review`. The post-lock room, review G's room and the bench and lit rooms
  are not covered. I scanned them myself; they are clean (item 6 below).
- **`make_postlock_review_room.py --check`** fails only on 7 `src/brainir_state/__pycache__/*.pyc` files. The reviewers' own
  `uv run` created them. They are harmless; the builder should treat `__pycache__` as a work area.

**m8. Hidden-material work is still in progress after this snapshot.**
- `final_b_H`, a re-evaluation of the stored seed-0 FINAL fits on Modal to extract family H (post-lock review R, M10), was logged
  START at 11:18:51Z.
- It needs a DONE row, a reason for the repeat evaluation (already stated), and a reproduction check against the stored verdict A,
  which the script includes.
- The same applies to any further post-review extraction.

## What I verified and found correct

### 1. Lock ordering

| UTC, 2026-09-26 | event | evidence |
|---|---|---|
| 01:31:52 | `method_lock_p3.py --lock ...` run (`locked_utc` 01:31:55Z) | transcript; METHOD_LOCK.json |
| 01:32:22 | commit `bce6dbf` "Method lock ..."; tag `brainir-state-v1-preblind` (lightweight) -> bce6dbf; ref file mtime 01:32:22.66Z | git; `.git/refs/tags/` |
| 01:34:41 | Level B confirmation START row written (then launch at 01:34:51, first FINAL fit view 01:35:02) | transcript; HIDDEN_EVALUATIONS; p3run mtimes |
| 01:46:43 / 01:46:57 | first local hidden-generation start / first salt-derived hidden record | transcript; store record mtimes |
| 02:08:53-02:49:43 | 13 confirmation parts finish (one LEVELB_LOG row each) | LEVELB_LOG.md |
| 05:49:57 | first FINAL counterexample sweeps START | HIDDEN_EVALUATIONS |
| 06:16:27 / 06:17 | gated Modal generation launched / eval-volume store created | transcript; volume listing |
| 07:29:25 | hidden dataset downloaded and verified (GENERATION.json `finished_utc`) | data/phase3/real_hidden |
| 07:29:51 / 07:30:02 | Level C launched / START row | transcript; HIDDEN_EVALUATIONS |
| 09:04:08 | Level C DONE (`wall_s` 5647) | HIDDEN_EVALUATIONS; results mtime |
| 09:05:36-10:01:31 | real hidden-draw counterexample search (local) | `run_l4b.cmd`; SUMMARY mtime |
| 10:33:25 | salt revealed (commit `95fd31f`) | git |

Nothing hidden precedes the lock, apart from M1 (reference controls, no method) and m1 (fake salt). `level_c.py` and
`generate_real_hidden.py` refuse to run without METHOD_LOCK.json. `data/phase3/real_hidden` first existed at 07:29:25Z.

### 2. Lock checks, all re-run now

| check | result |
|---|---|
| `scripts/p3/method_lock_p3.py --check` | `method lock ok (brainir_state_v1, 30 source files)` |
| `scripts/p3/freeze_benchmark.py --check` | `benchmark lock ok (97 files, 27 dataset entries)` |
| `benchmarks/dng100/freeze.py --check` | `"ok": true` (lock sha `bcaa8ee4...`) |
| `scripts/method_lock.py check` | `METHOD_LOCK check: OK` |

Checked by hand:
- **METHOD_LOCK inputs.** All 7 `inputs_sha256` entries exist and match.
- **Environment.** `phase3/uv.lock` and `pyproject.toml` hashes match; the installed numpy, scipy, torch, scikit-learn, pandas,
  pyarrow and pydantic versions match; Python is 3.12.14.
- **Changes committed since the tag.** Only three files are new: `scripts/p3/hidden_gen_gate.py`, `scripts/p3/level_c_fast.py` and
  `phase3/tests/test_hidden_gen_gate.py`. None is hashed. METHOD_LOCK.json, METHOD_NOTES.md, `phase3/src/**`, `benchmarks/**` and
  every hashed script are unchanged.
- **Uncommitted during the review.** The orchestrator added four scripts: `compute_summary_postlock.py`, `final_h_family.py`,
  `modal_billing.py` and `postlock_numbers.py`. None is hashed, and they write analysis outputs only. None modifies the locked
  methods. `final_h_family.py` loads the confirmation parts' raw-identical snapshots `final_b_<m>/methods` to re-evaluate stored
  fits (m8).

### 3. Hidden-evaluation log

| run | attempts | evidence |
|---|---|---|
| Level B confirmation | once | 13 parts, one Modal app each, no `.try*.log`, 13 LEVELB_LOG rows, one design across all parts; the merged `final_b/<m>.json` files are byte-identical to the parts |
| Level C | once | attempt `01`; `research/phase3/level_c/01/`; `p3run` has no other `level_c_*` |
| FINAL counterexamples | once each | 4 sweeps; the effect sweeps' app ids match the transcript, and there was no duplicate launch |
| real hidden-draw counterexample | once | backend `local` |
| FINAL ablations | aborted once, re-run | the abort and the re-run are both logged with reasons |
| review G on the locked method | once | logged retrospectively |

- Every output directory named in a row exists. The rows' times agree with file times.
- No hidden result directory lacks a row. The only unlogged result directories are the dev-suite ablations
  (`ablations_dev`, `ablations_smoke_dev`), which are development data.
- The fit log's 163 entries are 153 distinct stems: each seed-0 stem appears for both methods, so no fit ran twice.
- The 1,713 gate refusals all happen before any computation. The gate reads `/proc/cpuinfo` before calling the frozen callable.

### 4. No post-hidden tuning

- **Sources.** The locked directory matches the lock, 30 of 30 LF hashes. Its newest file mtime is 2026-09-26T00:20:47Z, and the
  directory is dated 01:31:52Z, so nothing changed after the lock. The clean room's methods package still equals the lock. No file
  of any room or agent store changed after 01:32:22Z, except the post-lock review room, which was created after the lock.
  - Level B used snapshots `C:\Dev\BrainIR_p3run\final_b_<m>\methods` taken from `--room C:\Dev\BrainIR\phase3`. All are
    raw-identical to the locked files (m4).
  - Level C, the ablations, the counterexample sweeps and review G used the locked directory directly.
- **Configuration.**
  - Level C: `{}` (the default) on 132 fits. The design adds `{"sharing": "shared"}` on 19 fits and the J common-k fits
    `{"k": 2|3, "sharing": "independent"}` on 4.
  - Level B, locked method: `{}` on 86 fits and `{"sharing": "shared"}` on 18 (plus 4 failed fits). The comparator's fits have
    the same pattern.
  - Ablations: `{"ablate": [switch]}`.
  - No other configuration was used.
- **Seeds.** They match the lock:
  - Level C: the locked method with seeds 0-4 on 10 systems (50 fits), the comparator with seed 0 (10 fits), and the resample arm
    of 5 half-samples per system (50 fits, seeds from `sha256(half:sid:h)`);
  - Level B: seed 0 on 48 systems and seeds 1-2 on 8.
- **Budgets.** The simulation budget is 250. The fit timeout is 3,600 s real and 1,800 s synthetic, doubled for shared fits. Fits
  run 3 threads, fixed in `p3modal/remote.py` and independent of the container's CPU count.
- **Comparator.** `lin_dmdc_t` was fixed by the r3v3 decision and by the lock. `--decision-round r3v3` enforces it.
- **Nothing was folded into v1.** No commit touches `phase3/src/brainir_state/methods` after `bce6dbf`. No clean-room agent ran
  after the lock: the composer ended at 00:58Z and the baseline tuner at 23:39Z the day before.
- **Requirement batches.** Both pre-lock requirement batches to the composer are generic. Neither relays any review-G result.

### 5. Benchmark integrity and the salt

- All locks verify (item 2).
- The working BENCHMARK_LOCK.json equals the lock at tags `state-discovery-benchmark-v3-relock2` and `brainir-state-v1-preblind`,
  and the hash recorded in METHOD_LOCK (`9572436d...`).
- Between the v3 tag and re-lock 2, only PROTOCOL.md, `make_phase3_cleanroom.py`, `modal_tournament.py` and `p3modal/remote.py`
  changed. No dataset entry, tolerance or salt commitment changed.
- **Salt reveal.** `SALT_REVEAL.json` was committed at 10:33:25Z, after Level C DONE (09:04:08Z) and after the hidden-draw search
  (10:01:31Z).
- **Salt match.**
  - The revealed value equals `data/phase3/hidden/salt.txt`.
  - Its sha256 (`4fe1d860...cb3d276`) equals `salt_commitment.json` and `BENCHMARK_LOCK.salt_sha256`.
  - The commitment is the same at every lock commit I checked: `186b1d3` (the first lock), `7b73b61`, `dbf4e35`, `d056d35`,
    `e3603b5`, `bce6dbf` and HEAD.
- **Salt secrecy before the reveal.** The salt string appears in git only in `95fd31f`: `git log --all -S` finds no other commit.
  `salt.txt` is git-ignored and was never committed. No room file contains the salt.
- **Salt never on Modal.** Protocols are built locally. Jobs carry derived seeds only; `build_jobs` reads the salt locally.

### 6. Rooms and agent sessions

- **`self_audit.py --only I5,I6,I7`** (output in scratch): pass, pass, pass.
  - I5: problem classes `{}`.
  - I6: no answer-bearing file by hash or name in the clean or review room. The hidden tier has 2,784 files and the developer tier 133.
  - I7: 0 source names; the only token classes are numeric 5-6 digits in public data files, which are coincidences.
- **Rooms I6 and I7 do not cover.** I ran the same scans on `BrainIR_p3postreview`, `p3reviewG`, `p3bench`, `p3lit`, `p3regen`,
  and again on `p3clean` and `p3review`:
  - 0 non-empty Phase 1-2 answer-bearing files by hash. Every hash hit is a 0-byte file (uv `.lock` stubs, an empty `__init__.py`)
    matching the two empty stderr files of `research/phase2/blind_eval/`.
  - 0 answer tokens in `p3postreview` and `p3reviewG`.
  - 0 source names outside `p3regen`. `p3regen` is the orchestrator-only regeneration room; its output file names carry dataset
    names by design, and no agent works there.
  - `p3bench`'s 4 numeric hits are fractional digits of floats in `example_suite/public/index.jsonl`.
  - No file in any room contains the salt.
  - `p3postreview` holds Phase 3 results by design, and the DENY pattern excludes `SALT_REVEAL.json`.
- **`make_postlock_review_room.py --check`.** No missing or modified file, no forbidden name or content, and a clean answer scan.
  The only failures are the 7 `.pyc` files of m7.
- **Transcript audit** (re-run now): 20 agents, 33 streams, 38,877 events, 2,947 tool calls.
  - 0 forbidden-path inputs; 0 blocked-tool uses.
  - Web use only by the literature agent (558 queries).
  - 1 answer-token hit, class `numeric-5-digits` in m_lin. This is the known file-size coincidence, pre-lock.
  - 39 guard denials, and 12 calls the current guard would deny, all known pre-lock false positives except 2 post-lock ones below.
- **Sessions after the lock.** The p3clean, p3review, p3reviewG, p3bench and p3lit stores and rooms have no file modified after
  01:32:22Z, and the remote runner's last job was pre-lock. The only sessions after the lock are post-lock reviewers S, C, Y and R,
  started at 10:32-10:33Z in `BrainIR_p3postreview`. Their streams show:
  - 0 forbidden-path inputs and 0 answer tokens;
  - name hits only for `goal4.md` (in their room by design) and `hidden_eval` (the evaluation-log name in the contracts), with 0
    dataset, organism or source names;
  - 2 guard denials (S at 10:33:36Z and Y at 10:36:40Z): the conservative "variable used as a path prefix" rule, on paths inside the
    room.

### 7. Modal

**Fit volume** (`self_audit.py --only I11 --modal-checks` plus my own read-only listing):
- **Top level:** `_incoming` (empty), `bundles`, `methods`, `models`, `views`.
- **`views`** (dev, heldout, final, review_g, real): the index splits are `{train, val}` only, and the `traj/` file names equal the
  index keys exactly, with no extra file.
- **`bundles/dng100_public_blind`:** 18 files, byte-identical to `benchmarks/dng100/public_blind` and to the 18 hashes of the Phase 1
  BENCHMARK_LOCK. The version-3 amendment permits it (commit d056d35, before the lock).
- **`methods`:** 7 tars. The newest is the locked key `2f4ad2d3ddf2df33`, uploaded at 01:04:41Z by round 3.
- **`models`:** 235 entries (fitted models and side files, 2026-09-25T21:58Z-2026-09-26T07:54Z), fitted on public data only.

I11's failure is therefore the allowlist artefact the orchestrator describes.

**Hidden real data on Modal.** Section 3.1 originally said "no real hidden data ... uploaded". The version-3 amendment then allowed:
- generation on Modal;
- storage on the eval volume only;
- evaluation containers only, with fit containers never mounting the eval volume.

The amendment was committed 2026-09-25T23:19:47Z, before the method lock and before any salt-derived record (the first at
01:46:57Z). On the eval volume the hidden build begins at 06:17Z.

Fit containers never mounted the eval volume:
- the Level C fit classes mount `/fitvol` only;
- the frozen fit function likewise;
- the counterexample app mounts `/fitvol` only.

### 8. The post-lock execution wrappers (P3-D25 to P3-D28)

**`hidden_gen_gate.py` (P3-D26).**
- **Code path.** It replaces `generate_real_hidden._modal_calls` only. The frozen `build_jobs` runs with `per_family` 30 (the CLI
  default), with the same payloads, links and timeout. `gated()` calls the frozen function unchanged after the cpuinfo check.
- **Version used.** The version that ran was committed in ffd6d49: the last edit was at 06:13:46Z, the launch at 06:16:27Z, and
  there was no edit until 07:22Z. Later edits added only `finish`, `remote_hashes` and `resim-check`.
- **Public check before use.** The gated public verification (60 of 60, 06:16:12Z) passed before the launch.
- **Tar and transfer.** The tar was finished by the frozen ungated call (a byte copy). The transfer was verified end to end: tar
  sha256 plus the text-file hashes computed on the volume.
- **Crosscheck.** 1,727 of 1,764 records match the local store; the 37 that differ are the known Windows-versus-Linux differences.
- **Re-simulation.** 83 of 83 re-simulated records are identical.
- **Timing of the checks.** Both the crosscheck and the re-simulation ran after Level C had started, at 07:32Z and 07:35Z. They are
  numerics checks and involve no method.

**`level_c_fast.py` (P3-D27).**
- **Fits.** It builds the payloads of the frozen `modal_run_fits_real` field for field; only the `job_id` is random. It uses the
  frozen container callables and output files.
- **Evaluations, references and reproducibility** go through the frozen functions on the gated `_eval_map`.
- **Resources.** `cpu=4` and the memory sizes are execution parameters that PROTOCOL §10 re-lock 1 allows. The thread count stays at
  3. The fit container timeout is the frozen 3 h.
- **Validation.** The validation (`levelc_fast_validation.json`, 07:28:27Z) used public mechanism systems only.

**P3-D28.** The real hidden-draw search ran with `--backend local` (`counterexamples.py` refuses Modal for `--hidden --kind real`),
after Level C DONE, as pre-registered in PROTOCOL §10 and runbook L4b.

### 9. The three self-audit artefact claims

- **I3: artefact, confirmed (item 5).** The check reads the stale `git_tag` field. The property holds.
- **I8: artefact, confirmed.** `research/phase3/level_c/_refcache` holds 30 reference-control caches, all written at 09:01:53Z
  inside attempt 01. It is the frozen driver's `real_refcache` (`L.OUT / "_refcache"`), not an attempt. Attempt 01 has START and
  DONE rows.
- **I11: artefact, confirmed (item 7).**

## Commands run

```
uv run --project phase3 --no-sync python scripts/p3/method_lock_p3.py --check
uv run --project phase3 --no-sync python scripts/p3/freeze_benchmark.py --check
uv run --no-sync python benchmarks/dng100/freeze.py --check
uv run --no-sync python scripts/method_lock.py check
uv run --project phase3 --no-sync python scripts/p3/self_audit.py --only I5,I6,I7 --out-dir <scratch>/postlock_L/sa_I567
uv run --project phase3 --no-sync python scripts/p3/self_audit.py --only I11 --modal-checks --out-dir <scratch>/postlock_L/sa_I11
uv run --project phase3 --no-sync python scripts/p3agent/audit_transcripts.py
uv run --project phase3 --no-sync python scripts/p3/make_postlock_review_room.py --check
```

Read-only helper scripts are in `<scratch>/postlock_L/`:
- `snap_check*.py`: snapshots against the lock;
- `fitvol_check.py`, `fitvol_bundle.py`, `evalvol_ls.py`: volume listings and bundle hashes;
- `rooms_scan.py`, `bench_hits.py`: room scans with masked contexts;
- `names_postlock.py`: name classes in the post-lock streams.
