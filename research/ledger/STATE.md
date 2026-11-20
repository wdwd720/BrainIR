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
- [ ] Stage 0: GHA campaign harness (release `ledgerdata-*` holds inputs; tag `gha-run-*` triggers; encrypted artifacts) and
      the TRUST GATE: 100 locked run 1 jobs incl. full-cord DNg100 seeds -> identical / rounding / fail.
- [ ] Stage 1: PREREG_v2.md (Parts L, P, S, disclosure) + kit v2; fresh reviewer audit; tag ledger-prereg-v2, push, OTS.
- [ ] Stage 2 (after freeze): G3 v2 incl. DNg100-only calibration BEFORE the first label session; tuner v2 K on DNg100
      (MANC + MaleCNS); tuner regression (K off = B1 on 30 types x 16 seeds); B1r, B2r, B3 (B6 only if budget); B4 v2
      recompute; determinism; review; LOCK_predictions_v2 (additive), tag, push, OTS.
- [ ] Stage 3: isolation canary; registry v2 + mechanical download (no reading); readers (<= 6 sources/session), atlas
      (map session + 2 coding sessions), searches (rounds until < 10 % new or 3 rounds), pass 2, adjudication, verification
      sample (30); assembly labels_v2/, v1_vs_v2.md, audit (v2 breach rule), reviewer, redact, LOCK_labels_v2, tag, OTS.
      Movies inventory only.
- [ ] Stage 4: gate (6 conditions) -> unblind once or stop; RESULTS_1.md, tag ledger-scorecard-v1.
- [ ] HANDOFF_2.md (<= 1,800 words), printed as the final message.
