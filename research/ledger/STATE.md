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

## Agent sessions used: 5 of 8 (1 rulebook auditor + re-check; 4 paper reviewers: referee 2, numbers/refs, naive reader, overclaim) -- final

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
- [x] Paper v1 written (abstract 220; main text about 3,650), SUPPLEMENT_v1 (generated), CLAIMS_v1 (39 rows), six figures
      (`posthoc/paper_figures_v6.py`), draft PDF/DOCX built and checked page by page (poppler installed with Homebrew for page checks).
- [x] STUDY_GUIDE (about 2,040 words), HAND_CHECK (20 items), BRIEF_v3 (2 pages), outreach v2 (192 / 126 / 120 words).
- [x] OTS: prereg_v6 Bitcoin-attested (committed); posthoc_v6 and thirdfly_v1 pending (upgrade later).
- [x] Four reviews done and committed as written (7d85be3); four addenda written first as the decision record (d0b67a8), verified
      after the revision.
- [x] Lock check before revising found `posthoc/paper_figures_v6.py` edited after two locks; restored; edits moved to
      `paper_figures_preprint_v1.py` (LOG L188).
- [x] New post hoc lock `LOCK_paper_posthoc_v1.json` (3dcb99d0...4b20), tag `ledger-paper-posthoc-v1` pushed, pre-mortem L189;
      four types are sweep hits in all three animals (DNg100, DNxl092, DNa13, DNxl134); OTS pending (background retry running).
- [x] Paper revised (32ffbf8, fd45dd3): abstract 218 words; Intro..Limitations 4,096, Intro..Use of AI 4,967; 18 references
      (refs_check_v2 18/18, order of first citation); CLAIMS_v1 56 rows; claims_check_v1 81/81; draft PDF 14 p, supplement 9 p,
      DOCX checked; every page viewed. RESULTS_5 corrected in place (marked), BRIEF_v3 (2 p), STUDY_GUIDE (2,262 w), outreach
      (authors 197 w, one paragraph 119 w, lab 129 w) (LOG L190-L191).
- [x] OTS: prereg_v6, posthoc_v6, thirdfly_v1 Bitcoin-attested and committed; paper_posthoc_v1 pending.
- [x] Final baseline 15:26 PST: 25 earlier lock checks pass; run-6 checks 4/4 (prereg_v6, posthoc_v6, thirdfly_v1, paper_posthoc_v1);
      ledger suite 302 passed; BrainIR fast suite 532 passed, 1 known failure (L5). Runner-hours 14.88 of 150 (82 jobs); no Modal.
- [ ] HANDOFF_6.md (14 sections, <= 2,500 words), printed as the final message; commit the paper_posthoc_v1 OTS proof when complete.
- Extra post hoc (exploratory) file for the paper: thirdfly_v1/POSTHOC_exam2_pairs.json (model clearly above 4 of 8 baselines).

## Facts fixed so far (run 6)
- K = 1 (tuned procedure: B1's screen `b1_screen_cfg(10)`: start 128, <= 10 runs, 10 <= active <= 1,500, <= 200 above 100 Hz,
  >= 1 active read-out MN; T = 1 s). Sweep = rulebook v4 fix 1 (`sweep_v4`, 19 currents 4 x 2^(k/2), k = 0..18, best in-bounds score).
- BANC: 4,963 neurons; read-out 139 front-leg MNs (68 L, 71 R); 922 excitatory DNs; 309 MANC-type groups; confidence high 206 /
  medium 103 / low 0; three-animal set 182. Authors' DNg100 = position 1605 at 400; E1 1689, E2 910, I2 3334.
- The authors' paper already reports DNb08 gives no rhythm in BANC (mean 0.000): disclose in Part Q; C5 makes no DNb08 prediction.
- Stored screens: MANC whole-type sweep exists (`dx-1-run4`, Modal, 8 seeds); no MaleCNS whole-type sweep (Part H must run one).
- Job wall times (stored): B2r 2.7 s mean, B1r 21.7 s, run 5 copies 25.7 s; BANC to be timed by the gate.
