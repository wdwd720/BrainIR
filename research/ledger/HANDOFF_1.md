# BrainIR prediction ledger, run 1: handoff

Run: 2026-11-19 20:20 to 2026-11-20 ~10:55 PST, about 14.5 hours.
- Spec: `research/ledger/RUN1_PROMPT.md`.
- Decisions: `research/ledger/LOG.md` (L1-L48).

## 1. This machine

- Apple M5 (10 cores), 16 GB RAM, macOS 26.6, uv 0.13.7, managed CPython 3.12.14, Claude Code 2.1.329.
- **G0 passed.** MANC v1.2.1 and v1.2.3 rebuilt byte-identically; the authors' front-leg and full-cord matrices reproduced exactly.
- **What could not run here:**
  - one fast-suite test fails on arm64 at baseline (RK4 tolerance, L5);
  - the Phase 3 benchmark check (its data is only on the PC);
  - the MaleCNS bulk data was not downloaded (disk and RAM, L9), so B2 uses the authors' pinned MaleCNS matrix and table.
- Simulations ran on Modal (pinned image, one numerics fingerprint).
- **Pushing worked.** The prereg tag was pushed at the freeze; the branch and later tags only after the labels froze (PREREG 13).

## 2. What exists and where

- **Branch:** `ledger/v1`, from `main` @ 242e472, pushed. `main` is untouched.
- **Tags:** all annotated and pushed. v1.1 is a bug-fix version of the labels; its scoring inputs are byte-identical to v1.

| Tag | Commit | Lock file | SHA-256 |
|---|---|---|---|
| `ledger-prereg-v1` | 2c831da | `LOCK_prereg_v1.json` | 2a573239c386eae266f6fdfbcbe83bb2d20f1cc524832e6b650dfe932a691c05 |
| `ledger-predictions-v1` | e8bc214 | `LOCK_predictions_v1.json` | bfca7e8a8e2a220d3b6f89f5351aca23f1475a3af3eec830e511956b8643cb11 |
| `ledger-labels-v1` | 4a015bd | `LOCK_labels_v1.json` | a7b5363fa315b15096612b2790fe2bea22b660c8b6df9e3fc08d7771e286ffb1 |
| `ledger-labels-v1.1` | a21a380 | `LOCK_labels_v1_1.json` | 0a07e1eef2aad3eef271baaca3216cea8c5954a8052f678487c42c00c3f90e7f |

- `PREREG.md` SHA-256: b3561723f2c238fde6a7f3de0cd41231fb96fac06e479d4fee4d013833b15f6e.
- The predictions lock (22 arms, 182 files) was verified on the tag.
- **Timestamps:** OpenTimestamps proofs (`*.ots`) sit next to each lock.
- **Files:** `research/ledger/predictions/<arm>/types.csv`, `research/ledger/labels/`, `gates/`, `reviews/`, `movies/`, `final/`.
- In a clean checkout all four locks check clean. Scoring refuses to run without `UNBLIND.json`, which does not exist.

## 3. The rulebook in ten lines, and departures

1. Unit: the MANC DN type. Primary set: the 321 excitatory front-leg types.
2. Primary prediction A1 is the authors' type-level screen: the mean rhythm score of usable replicates (never usable scores 0).
3. Bands: driver if the score is at least 0.5, non-driver if it is below 0.05.
4. Truth: the blind front-leg consensus (yes or no) from two passes plus adjudication by separate headless sessions. Headless outranks intact, clean lines outrank non-specific ones, and conflicts are excluded.
5. Primary set: types labeled yes or no, among A1's 321, not exposed.
6. Statistic: AUROC with a stratified bootstrap 95 % interval (seed 20261120) and a one-sided permutation p (descriptive).
7. "Underpowered" below 20 types or 5 per class. "The model predicts" if the lower bound is above 0.5.
8. "Adds value beyond wiring" only if A1 beats the best of S1-S7 (paired bootstrap, lower bound above 0).
9. Controls, baselines and the BrainIR arms are descriptive.
10. Scoring runs once, after both locks. Amendments are allowed only before the affected stage has data.

**Departures (reasons in the LOG):**

- **Statistics** (L15, L21):
  - the bootstrap is stratified by label;
  - the permutation test is one-sided;
  - the informed baseline S8 is excluded from "best baseline";
  - the coupling test needs n ≥ 8;
  - records whose reader saw a score are dropped.
- **Exposed list:** two uncertain types added (DNg74, DNg62), on the conservative side (L8).
- **B1:** uses the authors' high-firing cap 200 (L13) and lower bound 10, the pre-registered tie rule (L26). It is scored on 144 front-leg motor neurons, while A1 is scored on the authors' 138 (L15).
- **B3 and B6 not locked:** G3 failed (L16). B3's lower bound was calibrated on DNg100 only (L14), and the authors' own traces fail the same coupling test (L18).
- **B2:** uses the pinned MaleCNS network (L9).
- **Modal:** batched containers ran 4 BLAS threads instead of 1, with 1,500/1,500 re-runs identical (L28-L32). The workspace was switched at your request (L31), and there were 6 idle hours after a spend-guard pause (L33).
- **Labels:**
  - Three labeler sessions (atlas, walking_stopping, search_names) read back images their own web fetches had saved outside their room. That counts as a breach under the frozen rule, so their records are excluded and the sessions were stopped. No amendment was allowed (L37).
  - From 09:13 a guard blocked such reads.
  - Home paths were redacted to `$HOME` (L40).
  - Labels v1.1 fixes the completeness statistic (L47).

## 4. Gates and reviews

- **G1:** pass (480/480 flags, currents and runs equal; 390/417 scores exact, maximum difference 0.00088).
- **G2:** done as the prompt requires. Spearman 0.792, just under about 0.8, so the cause was found before locking: 0.864 on the 293 types usable in both; no code bug.
- **G3:** fail. B3 and B6 are not locked.
- **G4:** pass. 1,500 of 1,500 re-runs across 15 campaigns gave identical digests, 615 of them on the other host type.
- **G5:** pass before the lock and at the end, identical to the baseline (`final/G5_END_REPORT.md`).
- **Independent reviews:**
  - Stage 0: three rounds, every finding resolved before the freeze (L19, L22, L23).
  - Arms: two rounds, verdict LOCK with conditions; all conditions met (L34).
  - Gates, final: a fresh reviewer found that every locked arm passed the gates that apply to it and the review. G2 was met by investigation, and G1 covers B4/B5 only indirectly (`final/gates_review/`, `final/DONE_CHECKLIST.md`).
  - Labels: one round after the lock, verdict usable with caveats, no blocker. The consensus reproduces exactly. Majors: coverage (needs v2) and the completeness statistic (fixed in v1.1, verified).

## 5. Predictions only

| Arm | Types | Usable | Drivers | Non-drivers |
|---|---|---|---|---|
| A1 (authors, type level) | 321 | 316 | 11 | 216 |
| A0 (authors, single neuron) | 321 | 314 | 20 | 196 |
| A1-lo10 | 321 | 307 | 11 | 215 |
| B0 (BrainIR, single neuron) | 321 | 303 | 21 | 221 |
| B1 (BrainIR, type level) | 321 | 293 | 10 | 239 |
| B1-alt (lower bound 5) | 321 | 304 | 7 | 244 |
| B2 (MaleCNS, the second fly) | 328 | 289 | 23 | 243 |
| B5 (best fixed strength) | 321 | - | 14 | 95 |
| 10 control networks | 321 each | 316-320 | 0-13 | 152-300 |

- **B4** (475 types, including inhibitory ones), calls at strength 128: no effect 250, halts 207, slows 14, speeds 4.
- **S** (anatomical baselines S1-S8): 321 types, no bands.
- **Authors vs BrainIR:** type level, Spearman 0.792 (top-10 overlap 8, band agreement 0.85); single neuron, per-type maximum, 0.840.
- **Two flies** (B2 vs B1, 310 shared types): Spearman 0.311, top-10 overlap 1 (cleanly mapped types 0.362, the rest 0.121).

## 6. Labels only

- **Sessions:** 18 separate Claude Code sessions (8 pass-1, 2 searches, 6 pass-2, 2 adjudicators). 15 ended on their own; the 3 breaching ones were stopped.
- **Records:**
  - Sources: 77 (v1 showed 61, with eLife papers merged). Final records: 141.
  - Of the 166 pass-1 records, 22 were not found by pass 2 and 3 were unresolved disputes; all 25 were dropped.
  - 56 search-only records (v1.1) stay out of the consensus.
  - 34 records whose reader saw a simulation score are kept out of the consensus.
- **Final records by preparation:** headless 43, intact free 60, intact tethered 36, other 2.
- **Final records by line specificity:** clean 2, minor off-target 19, multi-DN 33, unknown 87.
- **Types with a clear front-leg label: 18.**
  - Best preparation: headless 6, intact free 6, intact tethered 6.
  - Best specificity: clean 1, minor off-target 3, multi-DN 1, unknown 13.
  - 6 of them have a systematic source.
- **Agreement, pass 1 vs pass 2** (144 matched experiments):
  - front-leg rhythm, both readings yes or no: n = 112, raw 1.0, kappa 1.0;
  - front-leg rhythm, all values: raw 0.94, kappa 0.90;
  - MANC type 1.0; middle leg 0.94 (kappa 0.92); hind leg 0.94 (0.91); walking effect 0.90 (0.80); line specificity 0.88 (0.79).
- **Completeness (v1.1):** about 125 (paper, type) pairs, so pass 1 found about two fifths (v1 reported 182, wrongly).
- **Transcript audit:** 18 sessions. 3 sessions breached (5 reads in all); 9 attempts were blocked; there was no fetch from a banned host.
- **Final exposed list** (15 names, 18 MANC types): DNg100, DNb08, DNg12, DNg97, MDN, DNa01, DNa02, DNp09, DNg13, DNp01, DNg16, DNg55, DNg75, DNg74, DNg62.
- **Name-only overlap with the prediction tables:**
  - 27 types have labels: 25 are among A1's 321 types, 27 among B4's, 26 in B2.
  - Of the 18 with a clear front-leg label, 16 are in A1; 12 of those are not exposed.
  - So the primary set has 12 types, and the pre-registered rule will call the primary analysis underpowered.
- **Spot-check sample** (20 records): `labels/spot_check_sample.csv`.
- **Atlas movies:** a 2.2 GB CC0 zip on Dryad; leg-tip tracking looks plausible, full pose doubtful.

## 7. Money and time

- **Modal:** about $27 on the first workspace (an estimate) and $29.68 settled on the second ($0.00 billed), about $57 of the $300 cap.
- **Claude:** at least $94 at API list prices (the three stopped sessions report no cost), on your subscription; weekly usage went from 28 % to 34 %.
- **Wall clock:** prereg 22:35; predictions 08:47 (after about 6 idle hours); labels 10:30, pushed 10:31.

## 8. What worries me

- **Too few labels.** The primary set has 12 types, so the primary analysis will say "underpowered". Causes: the atlas family was lost to a tooling artefact, and recall is about two fifths.
- **Agreement probably overstates accuracy:** every reader was the same model family; pass-2 identifiers could cue the type.
- **Unflagged score sightings** are possible.
- **Line specificity is mostly unknown** (13 of 18 types).
- **B2:** DNg100 positive control 0.059; I would not trust its ranking.
- **B4:** 199 of its 207 "halts" calls are over-excitation, not stops.
- **A1 vs B1 agree at 0.79** overall (0.86 where both are usable).
- **The blind is procedural:** the labelers may have read the paper in training.

## 9. What I would do next

1. **Labels v2** under a new pre-registration, against the same locked predictions: deny tool-results reads at tool level, re-run every family including atlas, and decide which version to score before any scoring.
2. **Your hand check** of the 20-record sample before unblinding.
3. **Run 2 scoring:**
   - run `lock.py check` on all locks in a clean checkout of the labels tag;
   - create `UNBLIND.json` naming the locks;
   - run `python -m brainir_ledger.scoring.pipeline` once.
4. **Fix B2's tuning transfer** as a new locked version, and give batched Modal jobs per-job timeouts.

## 10. Statement

No label was joined to any prediction in this run. No hit rate or score-versus-outcome comparison was computed for any type, and `UNBLIND.json` does not exist.
