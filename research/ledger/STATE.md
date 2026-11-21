# Ledger run 2: state (resume here after a context compaction)

Read first: `research/ledger/RUN2_PROMPT.md` (the spec), this file, `research/ledger/LOG.md` (L49 onward; run 1 = L1-L48).
Run 1 is closed (handoff `HANDOFF_1.md`); its locks (prereg v1, predictions v1, labels v1, labels v1.1) must never change.

## Fixed facts
- Branch `ledger/v1`; push branch + tags to origin with explicit refspecs; never `main`. Run 2 started 2026-11-20 12:51 PST.
- No Modal in run 2. Compute: GitHub Actions (`.github/workflows/ledger-gha.yml`, tags `gha-*` only; push the branch
  first, then the tag ALONE), fallback the Mac (~6 workers). Runner-hours cap 300. Logs: progress only.
- Orchestrator never reads papers or per-type labels; labels only by blind sessions. Never create UNBLIND.json before the
  Stage 4 gate passes.
- Never wait for the user: every pause schedules its own re-check within 10 min; blocked 30 min -> fallback (prompt sec 10).
- Claude account quota (labelers + orchestrator): 34 % of the 7-day window at the end of run 1 (resets 2026-11-25 17:00);
  L36 thresholds: slow down above 85 % (fewer sessions), never stop.

## Plan / checklist
- [x] Stage 0: caffeinate, prompt saved, locks/tree/UNBLIND checked, baseline re-run (L49), controls_check committed,
      GHA probe: fingerprint a72e417cfd91 identical.
- [x] Stage 0: GHA harness (`ledger/scripts/gha.py pack|publish|collect`, runner `gha_runner.py`; release `ledgerdata-<name>`
      holds inputs; tag `gha-run-<name>` (pushed alone after the branch) triggers; results encrypted to `.github/ledger_gha_pub.pem`,
      private key `data/cache/ledger_gha_key/`). TRUST GATE: 100/100 IDENTICAL (`gates_v2/TRUST_GATE.json`, L50).
- [x] Isolation canary passes with tool rules (`gates_v2/CANARY_v2.json`): repo, planted file, scratchpad, sibling room, banned
      hosts blocked; room files, PDF, image and own tool-results readable. Launcher `labels2_rooms.py` (queue + `schedule`).
- Code written (uncommitted parts may exist): `labels2_rooms.py`, `labels2_collect.py`, `labels2_audit.py`, `labels2_canary.py`,
  `typescreen_v2.py`, `jobs_v2.py` (group_v2), gha builders calibk/regress/b1r/b2r/g3v2, `g3v2_evaluate.py`, `lock2.py`.
  Downloader `labels2_download.py` being written by a helper agent; PREREG_v2 under review by a fresh reviewer (14:00).
- [x] Stage 1: rulebook v2 FROZEN 2026-11-20 22:41 UTC: tag `ledger-prereg-v2` (604c15b), `LOCK_prereg_v2.json` sha256
      2fa40cf8...51b0, OTS proof committed (564809a). Reviews: REVIEW, RECHECK, NARROW + resolutions in reviews_v2/ (L52-L54).
      From now on: files hashed by the prereg lock change only via `lock2.py amend` (L12/P4b); new evidence = new files.
- Item 4' decided by `gates_v2/G3v2_PREVIEW.json` (fails): B3, B6 not locked in run 2.
- [~] Stage 2: ALL P1 gates pass: K = 1 (CALIBK.json), regression 480/480 (REGRESSION_v2.json), determinism 200/200
      (DETERMINISM_v2.json), positive control DNg100 16/16 (B1r), 13/16 (B2r); DNb08 reported (B12R_CONTROLS.json, committed with the predictions);
      baseline identical (BASELINE_v2_predlock.json). G3 v2: 4' fails -> B3, B6 not locked. Tables written (NOT committed):
      predictions_v2/B1r (321 types), B2r (328), B4v2. Independent prediction review running (-> ~/ledger_rooms_review_pred2/).
      Then: fixes; `git add -f` the parquets; `lock2.py predictions B1r B2r B4v2 B3="G3 v2 fails (item 4', P2)" B6="G3 v2 fails
      (item 4', P2)" --platform "<PLATFORM of b12r_gates.py>"`; commit LOCALLY; tag `ledger-predictions-v2` locally; OTS stamp
      (hash only). **From that commit on, do NOT push ledger/v1 until LOCK_labels_v2 exists (P5).**
- [~] Stage 3: label-side review fixes committed + pushed (a1c0bce; 9 synthetic collector tests). Scoring/gate/lock2 fixes:
      helper agent working (scoring review B1, B2, M1-M3). Then: commit + push; `lock2.py labelcode` and `lock2.py scoring`
      (commit first; both refuse if they exist); commit + push + OTS; THEN first sessions: enqueue atlas-map, atlas-codeA,
      atlas-codeB and `readers --round 0` specs; `labels2_rooms.py schedule --max 8` in the background.
      Downloads: 70/75 at 15:43 (56 full text, 14 abstract only -> reader_web); no banned host or token in the download log.
- Quota: 40 % at 13:51 (run 2 start ~34 %). Helper agents are expensive (~0.5-1 % each): keep them few.
- [ ] Stage 2 (after freeze): G3 v2 incl. DNg100-only calibration BEFORE the first label session; tuner v2 K on DNg100
      (MANC + MaleCNS); tuner regression (K off = B1 on 30 types x 16 seeds); B1r, B2r, B3 (B6 only if budget); B4 v2
      recompute; determinism; review; LOCK_predictions_v2 (additive), tag, push, OTS.
- [ ] Stage 3: isolation canary; registry v2 + mechanical download (no reading); readers (<= 6 sources/session), atlas
      (map session + 2 coding sessions), searches (rounds until < 10 % new or 3 rounds), pass 2, adjudication, verification
      sample (30); assembly labels_v2/, v1_vs_v2.md, audit (v2 breach rule), reviewer, redact, LOCK_labels_v2, tag, OTS.
      Movies inventory only.
- [ ] Stage 4: gate (6 conditions) -> unblind once or stop; RESULTS_1.md, tag ledger-scorecard-v1.
- [ ] HANDOFF_2.md (<= 1,800 words), printed as the final message.
