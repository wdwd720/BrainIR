# Ledger STATE (run 4: left-right and cross-fly reproducibility; spec research/ledger/RUN4_PROMPT.md, sha256 ec03c9a6...9756)

Read RUN4_PROMPT.md, this file and LOG.md (L104+) after any context loss. Run 3 is closed (HANDOFF_3.md); exams 1 and 2 are
unblinded and closed.

## Hard limits (RUN4_PROMPT section 3)
1. Declare first: every analysis, metric and criterion in PREREG_v4.md before its data or simulation (Part A0 included). Later
   ideas -> section marked exploratory.
2. Calibrate on DNg100 only (gains, thresholds). DNb08 reported, never tuned on. No exam label shapes a fix.
3. Exams closed: Part D re-scores are exploratory, each variant scored once, said every time.
4. Labels used only for the Part E probability fit (stated as training on past results).
5. Frozen stays frozen: existing locks, BrainIR locks, Phase 2-4 files, `main`. BrainIR methods imported read-only.
6. Reviews write-once; later thoughts in an addendum file.
7. No paid compute: GitHub Actions only (trust gate); the Mac runs no prediction. At most 20 GitHub jobs queued+running at a time
   (count jobs, not campaigns). Stop at 300 runner-hours.
8. Push branch + tags only. Never `main`. No force push.

## Checklist
- [x] Stage 0: caffeinate (detached `caffeinate -dimsu`, restart if gone); RUN4_PROMPT saved; baseline identical (532 + arm64
      failure; 15 locks; ledger 201); trust gate trust-run4 100/100 (gates_v4/TRUST_GATE_v4.json); dose arm: current applied, not a
      bug (diag_v4/DOSE_ARM_CHECK.json, L105).
- [x] Stage 1: FROZEN. Tag ledger-prereg-v4 = badc4d7 (pushed), LOCK_prereg_v4 fd34d9f7...19ad4 (186 files; clean-worktree check
      258 passed); OTS pending (upgrade later). Audit + re-check resolved (reviews_v4/). Amendments: 1 (A4 indexing), 2 (Modal x1.3).
- [x] Part A0: real gap in the authors' own scores (ratio 0.63) -> reliability_v2/A0.json (L114).
- [x] Part A: real gap both flies (MANC 0.59, MaleCNS 0.64); cross-fly 0.32-0.50; analysed set 278 (A.json, ANALYSED_SET.json, L116).
      A4 (WIRING_A4.json), A5 (A5.json) done (L115).
- [x] Modal done (b3-manc-run4, crw-run4; billing $14.93 of $15; L120). Determinism stage 1 (Part A) 40/40 (L-row in commit 314aa6f).
- [x] X9 re-budget (L122): random part cut to 25 (ANALYSED_SET_X9.json, amendment 4; 262 analysed types); DROPPED: MaleCNS Block 3
      repeats, floors 3/10 (fl-3, fl-10), fix 3b (cx-32, dx-32); fix 2 kept (zero compute); Part D dx deferred until the robust
      model is chosen (its whole-type screen first). Fix campaigns use LABEL names: cx-3a, cx-5a, cx-5b (dx-3a, dx-5a, dx-5b).
- [x] Amendments 5 (B1 transplant mapping) and 6 (SR guard) after a dry run on fake results (posthoc/dryrun_analyses_v4.py, all
      19 steps OK; L125). Feeder crash on an existing tag -> b2-manc published as -r2 (L124).
- [x] Block 1 both flies (B1_MANC.json, B1_MaleCNS.json; L126): tuner explains <= ~1/3 of the gap; gap at every fixed current.
- [x] Block 2 MaleCNS (B2_MaleCNS.json): sanity pass; H_own closure 0.17, H_rest 0.21 (both CIs include 0).
- [~] RUNNING (23:15 PST): GitHub b2-manc-run4-r2 (7, ~00:40), cn-run4 (6, ~01:00), fl-1-run4 (6, ~01:40); feeder
      (feeder_run4_core2.log) next: cx-4, cx-5a, cx-5b, cx-7, cx-3a, cx-1. Collector collect_all2.sh. Monitor on both logs.
- NEXT: b2 MANC, then b3 MANC (B3_MALECNS_CHOICE.json is written; b3-mcns NOT run: dropped),
      noise (cn + fl-1 only), then c (C_FIXES_1_TO_8) -> fix 9 if a procedure and a network fix both pass -> c --final -> robust
      model's dx first, then re-check the envelope for Part D (dx-*) -> rescue; det4 stages 2-5 (stage 3 without fl-3/fl-10);
      exploratory full-278 comparison for Block 1/3; LOCK_reliability_v2; then forward ledger.
- [ ] Stages 2-5: A0 -> A -> Block 1 -> Block 2 -> Block 3 + count noise -> C -> D; LOCK_reliability_v2, tag ledger-reliability-v2.
- [ ] Stage 6: forward ledger research/ledger/forward/, LOCK_forward_v1, tag ledger-forward-v1.
- [ ] Stage 7: RESULTS_3.md, adversarial review + addendum, BRIEF.md, EVIDENCE_MAP.md; HANDOFF_4.md (<= 2,200 words, 14 sections,
      printed as the final message).

## Facts fixed so far (run 4)
- Dose arm (H-D): all 1,376 job specs carry the key's current for every member; neurons above 100 Hz rise with the current; the
  run class is set by member count and sign in this range (only 01B and 27X change, at 512).
- One-sided screen (R4, run 3): MANC seeds 0..3, 2,464 jobs, 20.9 s per job (median 11.3). B1r accepted currents 1-99 %:
  4.06-1024 (min 1.75, max 2048). B2r (MaleCNS) jobs 2.7 s.
- MANC front leg: 4,604 neurons, 144 fl MNs (72 L / 72 R), 933 excitatory DN members in 321 types, DN side = rootSide of the
  full-cord table. MaleCNS (authors' matrix): 4,310 neurons, 130 fl MNs (67 L / 63 R), 885 excitatory DN members in 328 types,
  DN side annotated only as brain soma side; MaleCNS matrix floored at 5 (no pre-floor counts): floors and count noise on MANC only.
- Run 1 unfixed rewired controls (B1, whole type): 1, 1, 2, 0, 0 drivers of 321 (B1 itself 10).

## Earlier facts (runs 1-3)
- Full cord: 23,532 neurons; 732 MNs; linearised model spectral radius 34 (no stable steady state).
- Mac numerics differ from GitHub (arm64): the Mac never runs a prediction. GitHub runner numerics digest a72e417cfd91.
- GitHub workflow key bug (L82): a random key starting with a newline breaks encryption (1/256 per chunk): re-run the job.
- Queue stalls at ~270 queued jobs (L83): keep the queue small.
- CAUTION: untracked .py directly in ledger/scripts/, ledger/src/brainir_ledger/, ledger/tests/ blocks the lock writers.
