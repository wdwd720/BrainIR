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
- [~] Stage 0: caffeinate (task bpzx5j4ux); RUN4_PROMPT saved; tree clean at start (HEAD fb9fc60 = origin). Dose arm: current
      applied, not a bug (diag_v4/DOSE_ARM_CHECK.json, LOG L105). TODO: lock checks, baseline suite, trust gate (trust-run4).
- [ ] Stage 1: PREREG_v4.md (design draft: orchestrator scratchpad run4_design.md + advisor items in LOG L106), code before the
      freeze (jobs_v4, gha_runner4, ledger-gha4.yml with the key-newline fix, gha4.py, lock4.py, analysis code), side QA
      (annotations/wiring only, disclosed), fresh rulebook audit, tag ledger-prereg-v4, push, OTS.
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
