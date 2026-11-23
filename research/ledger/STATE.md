# Ledger STATE (run 5: replication, count-noise stability, label audit, forward ledger v2, paper; spec research/ledger/RUN5_PROMPT.md, sha256 65fabef7...1d25)

Read RUN5_PROMPT.md, this file and LOG.md (L159+) after any context loss. Runs 1-4 are closed (HANDOFF_1..4.md); exams 1 and 2 are
unblinded and closed. Run 4's state is in git history (this file at 0b15e33).

## Hard limits (RUN5_PROMPT section 3)
1. Declare first: every analysis and criterion in PREREG_v5.md before the data or simulations it concerns.
2. Mark post hoc: the replication pattern (B1r x B2r hits) was seen before PREREG_v5; every table, figure and sentence resting on it
   says "post hoc". Part S is the only new confirmatory test.
3. Exams closed: no primary result re-scored; an audited-labels re-score of exam 1 may be reported once, marked exploratory.
4. I never author labels: the audit is done by fresh reader sessions (they may read every source, incl. simulation papers).
5. Frozen stays frozen: every existing lock, the BrainIR locks, Phase 2-4 files, `main`. Corrections live in new files.
6. Reviews write-once; later thoughts in an addendum. Tell every reviewer the length limit of what it reviews.
7. Compute: GitHub Actions under the trust gate, <= 20 jobs queued, <= 100 runner-hours; time jobs first, chunks < 1 hour.
   No Modal (unless the user says so in chat). The Mac runs no prediction.
8. Nothing leaves this machine except pushes to the repo (branch, tags, campaign releases). No email, posting, uploading, contact.
9. Be fair to the original authors.

## Checklist
- [x] Stage 0: caffeinate (started 00:45 PST 2026-11-23); RUN5_PROMPT.md saved; tree clean (ba016c8 = origin); locks + baseline
      (lock checks 21/21; ledger 263 passed; BrainIR fast suite 1 known failure, LOG L5); trust gate 100/100 identical (L161).
- [x] Per-type tables `pertype_v1/` (all reproduce their locked aggregates); LOCK_pertype_v1 (40a4c521...c044) + tag ledger-pertype-v1
      pushed (L162); OTS pending upgrade (`LOCK_pertype_v1.json.ots`, commit after upgrade).
- [ ] PREREG_v5.md: drafted 01:10; fresh audit (23 findings, "freeze after these fixes", L163); revised + resolution file +
      code reconciled (L164); same auditor re-checking (reviews_v5/PREREG_AUDIT_RECHECK_v5.md). Then: audit kit manifest
      (`audit5_rooms.py kit-manifest`), amendment row for gha5.py (changed after the per-type lock), commit, pre-mortem (LOG),
      `lock5.py prereg`, commit, tag ledger-prereg-v5, push, OTS.
- [ ] Part R (from locked tables); Part S campaign (time first; chunks < 1 h; determinism sample); Part L (fresh readers);
      Part T if budget; LOCK_replication_v1 + tag ledger-replication-v1; OTS.
- [ ] Part F (readings, short list, availability lookups read-only, decision rule); LOCK_forward_v2 + tag ledger-forward-v2; OTS.
- [ ] RESULTS_4.md; paper/PREPRINT_v0.md + figures + CLAIMS.md; three reviews + addenda; BRIEF_v2.md (two pages, measured);
      outreach drafts (blank recipients); HANDOFF_5.md (<= 2,500 words, 13 sections); final baseline; print handoff.

## Facts fixed so far (run 5)
- Whole-type drivers (>= 0.5): B1r 15 types, A1 11, B2r 30; in both B1r and B2r: DNg100, DNb08, DNit013 (seen before PREREG_v5).
- Cross-fly match evidence (MaleCNS body annotations, raw file sha256 2177e246...a9a3b2; B2's mapping: curated `mancBodyid` first,
  `mancType` string as fallback): of 328 MaleCNS types, 320 fully body-matched; 82 have a member whose body match conflicts with its
  `mancType` string; 230 one-to-one in naming. Rule (fixed in Stage 0, before PREREG_v5): high = all members body-matched, no
  conflict, one-to-one naming; low = any conflict; medium = the rest. Counts: high 217, medium 29, low 82.
- DNit013's MaleCNS match is low-confidence (seen while building the tables): one MaleCNS body (11410, label DNpe023, soma side L,
  output side R) whose body match is MANC DNit013 (37139) but whose `mancType` string is DNit011; MaleCNS's DNpe023 pair maps to
  MANC DNit011 and DNit013 (two single-neuron MANC types on opposite sides).
- Part S: 16 drivers (B1r or A1) + 40 sampled non-hits; S0 448 jobs (7 chunks of 64); copies in 4 campaigns ps-b1..b4-run5 (1,792
  jobs each); Part T 3,824 jobs (pt-manc-run5, pt-mcns-run5); determinism det5-1-run5 (S0 + copies), det5-2-run5 (Part T).
- Part L: sandbox mode needs LEDGER_SCRATCH set; canary first; first batch = forensic F1/F2, atlas coders A/B, reader groups
  (primary-set groups first); then adjudicate-atlas, adjudicate-types, labels, verify, errors; rescore_audit_v1.py once.
- Compute plan: run 4's workflow and runner unchanged (`gha4-run-<name>` tags) through a new wrapper `gha5.py`; trust gate via the
  frozen `gha.py` (run 2's workflow), compared into `gates_v5/`.
