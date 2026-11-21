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
- [x] Stage 1: FROZEN 02:23 PST. Tag ledger-prereg-v3 = a175625 (pushed). LOCK_prereg_v3 8c674fd0..., LOCK_labelcode_h1 c4437386...
      (both verified in a clean worktree). OTS pending (upgrade later). Audit + re-check resolved (reviews_v3/).
- [~] Stage 2: campaigns published (data/cache/ledger_logs/publish_all_run3.log): hm-run3, hmdet-run3, hc-<k>-run3 (k 101-105,
      201-205), hsens-run3, hd-run3, r4-run3, r3-<k>-run3 (k 51 52 53 101 102 103 201 202 203). H-S computing locally
      (predict_h1.py hs). NEXT: collect3 hm-run3 -> predict_h1.py hm -> det-compare hmdet-run3 hm-run3 -> P9 gates -> Stage 2
      reviewer (brief in scratch) -> commit predictions LOCALLY (never push until LOCK_labels_h1) -> lock3.py predictions -> tag
      ledger-predictions-h1 (local) -> OTS -> THEN label sessions (labels3_rooms.py enqueue specs + schedule).
      RULE: after the first prediction commit, NO PUSH until the labels lock; publish3 re-runs tag origin (works without push).
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
