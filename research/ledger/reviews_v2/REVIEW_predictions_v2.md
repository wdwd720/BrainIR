lock after these fixes

Prediction side only; no label file opened. Every numeric check was re-run independently from the raw logs (`$DATA/ledger/...`). No blocker; one major.

**Q1. Calibration. Yes: K = 1 was chosen exactly by P1, from DNg100 alone.**
- Recomputed from `$DATA/ledger/calibration/GHA_calibk/results.pkl`, whose SHA-256 equals `CALIBK.json`: MANC K1 16/16, MaleCNS K1 13/16, so K = 1 is the smallest passing K.
- The 160 job specs hold only the DNg100 pair, K in {1,2,3,5,10}, B1's screen, and run 1's B1/B2 payload keys.
- The tuner, screen, start current and seeds are byte-identical from c3b4e70 (pre-freeze) to HEAD and match the `LOCK_prereg_v2.json` snapshot.
- B1r/B2r were packed 37-44 s after `CALIBK.json` was written.
- No v2 prediction script was saved after the first non-DNg100 v2 result was collected (`regress`, 14:50:10 PST).
- DNb08 ran in no campaign before B1r/B2r.
- *Minor 1:* `regress` (30 non-DNg100 types, K = 0; `gha.py:101-107`) was launched together with `calibk`, before K was fixed. That breaks the letter of "No other neuron is run before K is fixed". The "3 local jobs at K = 0" of LOG L51 may also have (types not recorded). No information path: K = 0 is B1's procedure; the `regress` results were encrypted, collected after `CALIBK.json` and equal to locked v1 digests. *Fix:* disclose both in the LOG and in the lock.
- *Minor 2:* `calibk_choose.py`, `gha_det.py` and `b12r_gates.py` are post-freeze code outside P4b. `calibk_choose.py` was saved 12 s after the calibration log arrived; its rule is mechanical and reproduced. *Fix:* name the three files as post-freeze in the LOG. `lock2.py` hashes them.

**Q2. Yes: B1r/B2r add only the K condition, and the gates are computed as P1 says.**
- `screen_group_v2` differs from the frozen `screen_group` only in its signature and `typescreen_v2.py:44-45`.
- Jobs: all 5,136/5,248 have `k_min = 1`, lower bound 10, cap 200, start 128, 10 runs, T = 1 s and seeds 0..15.
- Groups: member IDs equal B1's/B2's for all 321/328 types, and member positions equal the run-1 logs.
- Full-arm invariant: the 2,061/1,983 jobs whose v1 accepted run had 0 front-leg MNs all changed, with none accepted at 0 MNs. All other jobs (3,075/3,265) are digest-identical to v1.
- `types.csv`: re-derived byte-for-byte from the logs.
- Regression: the 30-type pick reproduces seed 20261204, compared against `predictions/B1/replicates.parquet` (matches the v1 lock): 480/480.
- Determinism: the pick reproduces seed 20261205: 200/200, 58 of them on another CPU model.
- Positive control: passes and is tautological; DNg100's B1r/B2r digests equal `calibk` K1. DNb08 is reported, not gated.
- Baseline: `BASELINE_v2_predlock.json` passes.
- **Major:** `arms._final` (`arms.py:70-71`, v1-locked) infers "weak" only from `n_active_all < 10`. In 646/1,411 (B1r) and 576/1,300 (B2r) unusable replicates, the last run was inside the bounds and rejected only by K, yet `final_verdict` says "strong". As a result, 32/30 types read `never_usable_strong`, where P1 says "counts as too weak". Scoring reads only `primary_score` and `band`, so no outcome changes, but the locked reason code is wrong.
  - *Fix* after `b12r_gates.py:78`, not in `arms.py`: for unusable replicates, final = weak if `n_active_all < 10`, or if `n_active_all <= 1500` and `n_high_fr <= 200`; else strong. Recompute `status` with `tables.status_from`.
  - Log it as a bug fix, and verify that `primary_score`, `band` and all numeric columns are byte-identical.
- *Minor:* `DETERMINISM_v2.json` lacks the log SHA-256s and the count of runs on another CPU model (`gha_det.py:59-62`). Two docstrings are wrong: `typescreen_v2.py:1-2` says "imported unchanged" (it is a copy), and `gha_runner.py:6` says `jobs.run_job`, but the code calls `jobs_v2`.

**Q3. B4 v2: yes, P3 exactly.**
- An independent reimplementation reproduces all 475 x 3 calls.
- The log SHA-256 equals P3's (94cd68fd...). All 22,816 locked digests equal both the stored digests and digests recomputed from the stored fields. The parquet file matches the v1 lock.
- Non-halt v1 calls are unchanged; v1 halts split only into the three new calls.
- *Minor:* the P3 hash is recorded but not asserted (`b4v2.py:54-63`), and the v1 parquet hash is not asserted either. The provenance (`b4v2.py:80-82`) lacks the code commit, the time and `types.csv`'s SHA-256, and the folder has no `config.json`. The crosstab axes are unlabelled; the outer key is the second strength (`b4v2.py:78`).

**Q4. G3 v2: yes.**
- `g3v2_evaluate.py:123-124` takes item 4' from the preview.
- The formal run's 64 runs are digest-identical to run 1's, and every pair's n, R and p equal the preview's.
- Items 1-3 and 5 pass; 4' fails (T1R-T2R, p 0.0035). B3/B6 go under `arms_not_locked`.

**Q5. Outputs: nothing misleading beyond the major.**
- No absolute paths or user names appear in `predictions_v2/` or `gates_v2/`.
- The platform text is accurate (ubuntu-24.04 x64; every chunk's numerics digest is a72e417cfd91).
- P5 holds so far: origin holds no per-type v2 prediction, only DNg100 gate files, counts and canaries.
- *Minor:* `code_commit` in `provenance.json` is the HEAD when the tables were written (`arms.py:106`), not the runner commit (828e669; specs packed at 564809a). The code is identical, so this is incomplete rather than wrong. *Fix,* when regenerating for the major: add the runner commit, the GHA run IDs (44831777087/44831808385), the manifest SHA-256 and the numerics digest.
- *Before the lock:* track `predictions_v2/` (parquet needs `git add -f`), `B12R_CONTROLS.json`, `DETERMINISM_v2.json` and `BASELINE_v2_predlock.json`. Then push nothing on `ledger/v1` until `LOCK_labels_v2.json` exists. That includes any GHA campaign, because `gha.py:175` requires HEAD on origin.
