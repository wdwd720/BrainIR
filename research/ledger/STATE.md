# Ledger STATE (run 6: a third animal, BANC; spec research/ledger/RUN6_PROMPT.md, sha256 ec622254...3ce3db)

Read RUN6_PROMPT.md, this file and LOG.md (L176+) after any context loss or in a new session. Runs 1-5 are closed (HANDOFF_1..5.md);
run 5's state is in git history (this file at ec770a8).

## Hard limits (RUN6_PROMPT section 3, short)
1. Declare first: PREREG_v6.md before the simulations it concerns. 2. BANC blind until `ledger-prereg-v6` is tagged and pushed: before
   that only DNg100 is stimulated in BANC and only the authors' rhythm-circuit neurons are silenced; no wiring summary of BANC DNs.
3. K (= 1) is never re-chosen; nothing is calibrated on BANC. 4. Everything about the first two animals' hit lists stays post hoc.
5. Exams closed. 6. Frozen stays frozen (25 lock checks pass; forward ledger v2 as locked; `main` untouched). 7. Reviews write-once,
   addenda after; tell reviewers the length limit. 8. GitHub Actions only, <= 20 jobs queued, <= 150 runner-hours, chunks < 1 h; no
   Modal; the Mac runs no prediction. 9. At most 8 fresh agent sessions in the run; no label-reading sessions (quota resets
   2026-11-25 17:00 PST). 10. Nothing leaves the machine except pushes to the repo. 11. Fair to the authors.

## Agent sessions used: 1 of 8 (rulebook auditor, incl. its re-check)

## Checklist
- [x] Stage 0 (10:19 PST): prompt saved; tree clean; start baseline 25/25 locks, ledger 285 passed, BrainIR 1 known failure (L5);
      caffeinate; trust gate `trust-run6` published (compare pending).
- [x] Stage 1 build: `ledger/src/brainir_ledger/banc.py` (pinned sources, build, matching, confidence); three-animal set 182 (L177).
- [x] Stage 1 gate PASSED (L178): DNg100 0.994 (64/64), E1 0.000, E2 0.028, I2 0.993; trust gate 100/100 identical.
- [x] Stage 2: PREREG_v6 audited (14 findings) and re-checked (N1-N6), all applied (L179-L180); analysis code, type sets
      (`gates_v6/TYPE_SETS_v6.json`), planning numbers, references (23/23), hand-check kit and build pipeline done before the freeze.
- [x] Frozen 12:11 PST: LOCK_prereg_v6 08f1ad75...bd20, tag ledger-prereg-v6 pushed, OTS pending (commit a8744d1) (L181).
- [x] Campaigns collected: bt-p1/p2 (5,040), ms (2,624), pv (1,344), bs-p1/p2 (1,648); det6-1 100/100 identical.
- [x] B4: tuned BANC INVALID (DNg100 11/16 < 12); sweep VALID (8/8) -> sweep primary for C3, C4, C6-C8; C5 tuned (L183-L184).
- [x] Part V: V1 reproduces (0.985); V2 reproduces at the authors' configuration 391 @ 250 (15/16, mean 0.86) (L183).
- [x] Part H built and LOCKED: LOCK_posthoc_v6 4b680b1f...7c50, tag ledger-posthoc-v6 pushed, OTS pending (L185).
- [x] All campaigns collected; det6-2 140/140; tests run; LOCK_thirdfly_v1 b8ef3e68...f395, tag ledger-thirdfly-v1 pushed, OTS pending
      (L186). RESULTS_5.md written. First line: gap between animals confirmed in the third animal (sweep primary), wiring caveat.
- [ ] Paper: PREPRINT_v1.md (draft started), SUPPLEMENT_v1.md, CLAIMS_v1.md, figures (`posthoc/paper_figures_v6.py` -> paper/figures_v1),
      `paper/build.sh --draft`, check every PDF page; 4 reviews (agents 2-5), addenda, revise; STUDY_GUIDE; BRIEF_v3; outreach v2;
      HANDOFF_6; final baseline (25 + 3 run-6 lock checks); OTS upgrades (prereg_v6, posthoc_v6, thirdfly_v1).
- Extra post hoc (exploratory) file for the paper: thirdfly_v1/POSTHOC_exam2_pairs.json (model clearly above 4 of 8 baselines).

## Facts fixed so far (run 6)
- K = 1 (tuned procedure: B1's screen `b1_screen_cfg(10)`: start 128, <= 10 runs, 10 <= active <= 1,500, <= 200 above 100 Hz,
  >= 1 active read-out MN; T = 1 s). Sweep = rulebook v4 fix 1 (`sweep_v4`, 19 currents 4 x 2^(k/2), k = 0..18, best in-bounds score).
- BANC: 4,963 neurons; read-out 139 front-leg MNs (68 L, 71 R); 922 excitatory DNs; 309 MANC-type groups; confidence high 206 /
  medium 103 / low 0; three-animal set 182. Authors' DNg100 = position 1605 at 400; E1 1689, E2 910, I2 3334.
- The authors' paper already reports DNb08 gives no rhythm in BANC (mean 0.000): disclose in Part Q; C5 makes no DNb08 prediction.
- Stored screens: MANC whole-type sweep exists (`dx-1-run4`, Modal, 8 seeds); no MaleCNS whole-type sweep (Part H must run one).
- Job wall times (stored): B2r 2.7 s mean, B1r 21.7 s, run 5 copies 25.7 s; BANC to be timed by the gate.
