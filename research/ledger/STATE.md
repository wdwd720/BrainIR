# Ledger STATE (run 3: hemilineage exam; spec research/ledger/RUN3_PROMPT.md, sha256 dc5b0d8d...aeb)

Read RUN3_PROMPT.md, this file and LOG.md (L70+) after any context loss.

## Hard limits (RUN3_PROMPT section 3)
- ONE unblinding for exam 2, through the Stage 5 gate. Never put a hemilineage prediction next to a hemilineage outcome before.
- NO hemilineage simulation before tag `ledger-prereg-v3` (only DNg100, DNb08, RNG-chosen synthetic groups).
- I never author labels and never read the hemilineage papers' results. Frozen locks/BrainIR/main untouched. No Modal; GitHub
  first (<= 300 runner-hours), Mac second. Push branch + tags only; no force push. After unblinding nothing moves.

## RUN 3 COMPLETE (2026-11-21 13:45 PST). Exam 2 unblinded once and scored; NEVER RE-RUN score_h1.py (flag retired).
- All tags pushed (prereg-v3, predictions-h1, labels-h1, scorecard-h1, reliability-v1); every proof complete; baseline,
  ledger suite and all locks green; HANDOFF_3.md written. The list below is the history of the run.

- Gate run 2: all six conditions hold. Flag committed (ebf0f01), primary + secondary run once, recompute agrees, flag retired to
  results/run3/UNBLIND_h1_used.json. Verdict: PREDICTS (0.633, 0.533-0.724, p 0.0076, 27 units) but NOT beyond wiring
  (H-S-k2-signed 0.638; diff -0.006, -0.172..+0.166). RESULTS_2.md written; results commit 3dd9746 (+ wording fix commit).
- Remaining, in order: commit wording fixes -> tag ledger-scorecard-h1 -> push branch + tag, verify ls-remote == HEAD and origin
  main unchanged -> OTS stamp RESULTS_2.md (commit .ots, push) -> lock3.py reliability (commit ALONE) -> tag ledger-reliability-v1
  -> push -> OTS stamp -> baseline checks (BrainIR `uv run pytest -m "not real_data"`: expect 532 passed + known arm64 failure;
  benchmarks/dng100/freeze.py --check; scripts/method_lock.py --check; scripts/p3/method_lock_p3.py --check) -> OTS upgrades
  (re-check every <= 10 min) -> HANDOFF_3.md (<= 2,000 words, 13 sections; draft scratch handoff_draft.md; compact scorecard)
  -> commit, push, print as final message.

## Checklist
- [x] Stage 0: caffeinate (running); RUN3_PROMPT saved; tree clean, 9 locks verify, baseline identical (532 + arm64 failure;
      ledger 133). Trust gate run 3 PASSED (100/100, gates_v3/TRUST_GATE_v3.json). Diagnosis: no build error (active MNs match);
      tolerance not the cause (diag_v3/TOLERANCE_DIAG.json); coupling difference = phase only (LOG L70, L72). Outcome-location
      list: reviews_v3/HL_OUTCOME_LOCATIONS.md (29 locations, none opened).
- [x] Stage 1: FROZEN 02:23 PST. Tag ledger-prereg-v3 = a175625 (pushed). LOCK_prereg_v3 8c674fd0..., LOCK_labelcode_h1 c4437386...
      (both verified in a clean worktree). OTS pending (upgrade later). Audit + re-check resolved (reviews_v3/).
- [x] Stage 2 (primary): LOCK_predictions_h1.json 732aca14... committed 04:49:14 (LOCAL; tag ledger-predictions-h1 LOCAL; OTS pending).
      Descriptive arms (H-C x10, hsens, H-D) via the FEEDER (publish log data/cache/ledger_logs/feeder_run3.log): collect3 each,
      predict_h1.py hc --campaign hc-<k>-run3 / hsens --campaign hsens-run3 --primary hm-run3 / hd --campaign hd-run3, then
      lock3.py predictions-b <arms> [ARM=reason] --platform ... BEFORE the labels lock (LOCK_predictions_h1b.json must exist).
- [x] Stage 3 (labels FINAL, NOT LOCKED yet): 14 sessions + verify-2 (verify-1 blocked by a safety classifier), no breach;
      79 final records, 27 units >= 3 coded, kappa 0.975, verification 4.1 %, review "usable with caveats" (L91-L92);
      sensitivity input labels_h1/consensus_sensitivity.csv (exploratory). Gate conditions 2-5 dry-run: pass.
- NEXT (in order): wait for the descriptive arms (CUTOFF 12:00 PST, L93) -> predict_h1.py hc/hsens/hd tables -> commit ->
      lock3.py predictions-b <arms> [ARM=reason] -> commit -> (>= 1 s later) lock3.py labels -> commit -> tag ledger-labels-h1 ->
      push branch + tags (hook allows once the labels lock is in HEAD) -> OTS. Then GATE: python -c gate_h1.evaluate() dry-run ->
      gate_h1.py (run 1) -> commit ONLY the report -> checklist reviewer (scratch gate_checklist_brief.md) -> commit ONLY the
      checklist -> gate_h1.py (run 2) -> commit. Do NOT write the reliability lock or amendment rows between gate runs.
      Then UNBLIND: research/ledger/UNBLIND_h1.json naming the three locks + sha256 -> commit -> score_h1.py --run primary ->
      --run secondary -> independent recompute (scratch recompute_brief.md) -> posthoc/results_h1.py (--with matplotlib) ->
      RESULTS_2.md -> retire flag to results/run3/UNBLIND_h1_used.json -> tag ledger-scorecard-h1 -> push -> OTS.
      R3/R4: feeder publishes r4, r3-51 early -> run reliability_v1.py r4/r3 on the first finished before the flag.
- [~] Stage 4: R1 done (cross-fly 0.37; split-half 0.86/0.93), R2 done (wiring cross-fly 0.78-0.97) -> reliability_v1/R1.json, R2.json.
      R3 (r3-<k>-run3) and R4 (r4-run3) published; after they finish: `reliability_v1.py r3` / `r4` -> LOCK_reliability_v1
      (lock3.py reliability), tag ledger-reliability-v1 (local until labels lock: the reliability lock hashes code incl. predictions? no -
      it hashes reliability_v1/** + code; but HEAD will hold predictions -> do not push until the labels lock).
- [ ] Stage 5: gate -> unblind once or stop; RESULTS_2.md; tag ledger-scorecard-h1.
- [~] Stage 6: post-mortem delegated to a fresh agent (exam 1 only; writes results/POSTMORTEM_1.md + ledger/scripts/posthoc/postmortem_1.py).
      HANDOFF_3.md (<= 2,000 words, printed as final message) at the end.
- Briefs ready in the orchestrator scratchpad: stage2_reviewer_brief.md (Stage 2 reviewer RUNNING; resume it for the H-M table
  spot-check once predicted.csv exists), label_review_brief.md, recompute_brief.md. Reporting script: ledger/scripts/posthoc/results_h1.py
  (outside lock-hashed folders; run with `--with matplotlib==3.9.2` after unblinding).
- CAUTION: any untracked .py directly in ledger/scripts/, ledger/src/brainir_ledger/, ledger/tests/ blocks lock3 writers (they refuse
  untracked code); put exploratory code in ledger/scripts/posthoc/.

## Facts fixed so far
- Full cord: 23,532 neurons; hemilineage annotation on every thoracic neuron (45 labels incl. TBD); birthtime covers 13,060 of
  13,064 thoracic hemilineage neurons (postembryonic = secondary + early_secondary); 732 MNs (fl 141, ml 119, hl 131, wm 66,
  hm 16, ad 229, nm 24, xm 6), leg MN motor modules annotated.
- Linearised model at the model's coupling constant: spectral radius 34 -> no steady state (H-S linear baseline undefined).
- Controls on the full cord build in seconds (class shuffle 0.3 s, rewire 12 s; 13.3 M of 13.7 M swaps).
- Quota 59 % at run 3 start (resets 2026-11-25 17:00 PST): be frugal with helper agents.
