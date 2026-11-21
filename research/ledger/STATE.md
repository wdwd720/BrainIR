# Ledger STATE (run 3: hemilineage exam; spec research/ledger/RUN3_PROMPT.md, sha256 dc5b0d8d...aeb)

Read RUN3_PROMPT.md, this file and LOG.md (L70+) after any context loss.

## Hard limits (RUN3_PROMPT section 3)
- ONE unblinding for exam 2, through the Stage 5 gate. Never put a hemilineage prediction next to a hemilineage outcome before.
- NO hemilineage simulation before tag `ledger-prereg-v3` (only DNg100, DNb08, RNG-chosen synthetic groups).
- I never author labels and never read the hemilineage papers' results. Frozen locks/BrainIR/main untouched. No Modal; GitHub
  first (<= 300 runner-hours), Mac second. Push branch + tags only; no force push. After unblinding nothing moves.

## Checklist
- [~] Stage 0: caffeinate (running); RUN3_PROMPT saved; tree clean, 9 locks verify, baseline identical (532 + arm64 failure;
      ledger 133). Trust gate run 3 on GitHub (campaign trust-run3) RUNNING. Diagnosis (DNg100 only): active leg MNs match the
      authors (r 0.98, same medians, no MN differs by >= 0.25) -> no build error; tolerance experiment RUNNING
      (diag_v3/TOLERANCE_DIAG.json). Repo search for hemilineage outcomes: subagent RUNNING (locations only ->
      ~/ledger_rooms_hl_search/LOCATIONS.md).
- [ ] Stage 1: motor map (annotations) + fresh review; PREREG_v3.md; scoring h1 + synthetic tests + UNBLIND_h1 flag + label-side
      no-prediction test; gate copy; fresh audit; freeze, tag ledger-prereg-v3, push, OTS.
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
- Quota 59 % at run 3 start (resets 2026-11-25 17:00 PST): be frugal with helper agents.
