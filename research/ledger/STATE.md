# Ledger STATE (run 3: hemilineage exam; spec research/ledger/RUN3_PROMPT.md, sha256 dc5b0d8d...aeb)

Read RUN3_PROMPT.md, this file and LOG.md (L70+) after any context loss.

## Hard limits (RUN3_PROMPT section 3)
- ONE unblinding for exam 2, through the Stage 5 gate. Never put a hemilineage prediction next to a hemilineage outcome before.
- NO hemilineage simulation before tag `ledger-prereg-v3` (only DNg100, DNb08, RNG-chosen synthetic groups).
- I never author labels and never read the hemilineage papers' results. Frozen locks/BrainIR/main untouched. No Modal; GitHub
  first (<= 300 runner-hours), Mac second. Push branch + tags only; no force push. After unblinding nothing moves.

## Checklist
- [x] Stage 0: caffeinate (running); RUN3_PROMPT saved; tree clean, 9 locks verify, baseline identical (532 + arm64 failure;
      ledger 133). Trust gate run 3 PASSED (100/100, gates_v3/TRUST_GATE_v3.json). Diagnosis: no build error (active MNs match);
      tolerance not the cause (diag_v3/TOLERANCE_DIAG.json); coupling difference = phase only (LOG L70, L72). Outcome-location
      list: reviews_v3/HL_OUTCOME_LOCATIONS.md (29 locations, none opened).
- [~] Stage 1: unit list (43), motor map v1, PREREG_v3.md (full draft), scoring_h1 + tests, prediction code (typescreen_v3,
      jobs_v3, groups_h1, predict_h1, gha3 builders with freeze guard, gha_runner3 + ledger-gha3.yml), lock3.py, e2e test: DONE.
      RUNNING: P7 pipeline test on GitHub (campaign p7-run3, tag gha3-run-p7-run3) -> `gha3.py collect3 p7-run3` then
      `gha3.py p7-check p7-run3` and `predict_h1.py p7 --campaign p7-run3 --out <scratch>`; motor-map reviewer (fresh agent ->
      reviews_v3/MOTOR_MAP_REVIEW.md); rulebook auditor (fresh agent -> reviews_v3/PREREG_AUDIT.md). THEN: fix findings, LOG
      pre-mortem, commit, `lock3.py prereg`, commit lock, tag ledger-prereg-v3, push branch + tag, OTS stamp.
      Label code (labels3_*, gate_h1, kit_v3) is excluded from the prereg lock (bound later by LOCK_labelcode_h1).
- [ ] Stage 2 (after freeze): H-M, H-D, H-S, H-C, sensitivity groups; gates; LOCK_predictions_h1 (local until labels lock).
- [ ] Stage 3: kit_v3, canary, downloads, readers x2 per source, Cheong coder, searches, assembly, review, LOCK_labels_h1.
- [ ] Stage 4: reliability R1-R4 -> LOCK_reliability_v1, tag ledger-reliability-v1.
- [ ] Stage 5: gate -> unblind once or stop; RESULTS_2.md; tag ledger-scorecard-h1.
- [ ] Stage 6: POSTMORTEM_1.md (exploratory). HANDOFF_3.md (<= 2,000 words, printed as final message).

## Facts fixed so far
- Full cord: 23,532 neurons; hemilineage annotation on every thoracic neuron (45 labels incl. TBD); birthtime covers 13,060 of
  13,064 thoracic hemilineage neurons (postembryonic = secondary + early_secondary); 732 MNs (fl 141, ml 119, hl 131, wm 66,
  hm 16, ad 229, nm 24, xm 6), leg MN motor modules annotated.
- Linearised model at the model's coupling constant: spectral radius 34 -> no steady state (H-S linear baseline undefined).
- Controls on the full cord build in seconds (class shuffle 0.3 s, rewire 12 s; 13.3 M of 13.7 M swaps).
- Quota 59 % at run 3 start (resets 2026-11-25 17:00 PST): be frugal with helper agents.
