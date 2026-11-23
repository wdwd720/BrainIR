# HANDOFF 4: run 4 of the BrainIR prediction ledger

## 1. What exists now

All three tags exist, were pushed to `origin` (branch `ledger/v1` only; `main` untouched, no force push) and carry OpenTimestamps proofs:

- `ledger-prereg-v4` (commit badc4d7): `PREREG_v4.md`, `LOCK_prereg_v4.json` sha256 fd34d9f78d3acea47f611f914af95afc4580c0c1d6ddffdfea5a1a2e84219ad4; proofs Bitcoin-attested.
- `ledger-reliability-v2` (commit d81668b): `LOCK_reliability_v2.json` sha256 02ca7209f948505b42a37e71f8a6657ca238fff58ecc2ece6fcdf243d84bb542 (202 files: Parts A0-D, gates, reviews, code); proof Bitcoin-attested.
- `ledger-forward-v1` (commit c3ffcfa): `LOCK_forward_v1.json` sha256 f62da2732a3df5677e9566629eac8d3e5de05e3dd0cf9e81c4edbf963bae4917 (179 files, including the fresh reviewer's ten-entry check `reviews_v4/FORWARD_TEN_ENTRY_CHECK.md`, ten of ten agree); proof Bitcoin-attested (upgraded at 21:28).

Documents: `results/RESULTS_3.md`, `reviews_v4/ADVERSARIAL_REVIEW_v4.md` with `ADVERSARIAL_ADDENDUM_v4.md`, `BRIEF.md` (two pages:
US Letter, 1-inch margins, 11 pt, with the table and the figure; `ledger/scripts/posthoc/brief_pages_v4.py` prints "pages: 2") with its
two overclaim reviews (`reviews_v4/BRIEF_OVERCLAIM_REVIEW.md`; `BRIEF_OVERCLAIM_REVIEW_2.md` with `BRIEF_OVERCLAIM_ADDENDUM_2.md`),
`EVIDENCE_MAP.md` (one row per claim, 30 rows), this file. Baseline at the end, as at the start: 21 lock checks pass (15 ledger locks, 3 BrainIR locks, the three v4
locks), ledger suite 259 passed, BrainIR suite 532 passed with the known arm64 failure.

## 2. Departures from the prompt, with reasons

1. **Modal was used** (hard limit 7 said GitHub only), on your instructions in chat: $15, then +$14, then +$12 ($41). It passed the same
   trust gate (100/100 locked jobs identical), and every Modal campaign's sample was re-run on GitHub and matched. The Mac ran no
   prediction. Logged Modal spend $36.17.
2. **The 20-job limit was exceeded once**, for about 4 minutes (26 jobs), when a restarted feeder counted before GitHub registered a
   manual publish; cancelled at once (LOG L119).
3. **The budget rule X9 cut the plan** when the runner-hour projection passed 280: the analysed set's random part 41 -> 25 types, and
   the MaleCNS repeats of Block 3, floors 3 and 10, fix 3b and Part D's whole-type screens were dropped in the rulebook's order (L122,
   L132). After the reliability lock, your extra Modal budget let Part D's screens of fixes 1, 4, 5a, 5b and 7 run; they are reported as
   post-lock exploratory results (`results/run4_postlock/`, hashes in L148). Fix 3a's screen was never run.
4. **Seven recorded amendments** (`AMENDMENTS_v4.jsonl`): an indexing crash in A4; Modal's cost overhead; the workflow timeout
   (170 -> 340 min); the X9 cut; Block 1's transplant mapping (the analysis read a field the runner never wrote; found before
   collection); a guard in Part C's specific-reproducibility bootstrap (found by a dry run on fake results before collection); the
   Modal cap. Each was made before the analysis it touches had run on real data.
5. **Operations not in the prompt:** chunks that hit GitHub's time limit were re-packed and re-run as partial attempts of the same
   campaign (same jobs and payloads; collection merges attempts by key); a dry-run harness ran every analysis on fake results first.
6. **The brief was reviewed for overclaims twice.** The first fresh reviewer was stopped by the model provider's safeguards (an API
   error that flags biology-adjacent research) before writing anything; I did not do the review myself. A fresh reviewer on another
   model, as the error message suggests, marked 15 items, all fixed (LOG L151-L152). Because the stop hook questioned that substitution
   (the prompt names no model), a fresh reviewer on the default model then reviewed the revised brief and marked 13 more (overclaims,
   missing caveats, a mislabelled post-hoc figure, a fix count that mixed units); all are fixed, and its four corrections to its own
   report are in `BRIEF_OVERCLAIM_ADDENDUM_2.md` (LOG L154). The brief now uses only numbers from locked files, so the adversarial
   reviewer's post-hoc figures appear in it in words only. The brief was then cut to the two pages the prompt asks for (it had printed
   to 4) by removing whole claims, not caveats. Every item of both reviews is either kept in the final text or resolved by removing the
   claim it qualified (`BRIEF_OVERCLAIM_ADDENDUM_2.md` section 4; LOG L155-L156). Every review of this run was written by a newly
   started agent with none of this session's context (LOG L153).
7. **Wall-clock** was about 23.5 hours (16:28 to about 16:00 the next day), at the top of the 12-24 h estimate.

## 3. The dose-arm check

Not a bug: all 1,376 run 3 fixed-current job specs carried their current, and activity rises with the current; the identical run
classes at 128-384 come from the coarse full-cord classification. No erratum (L105).

## 4. Part A0: the authors' own scores

Left copy against right copy in the authors' published screen (250 types with one member per side, 128 replicates): cross-half
Spearman 0.597 against a ceiling of 0.951, **ratio 0.63 (0.53-0.72), a real gap**; drivers replicate 1 of 7 and 1 of 8; band kappa
0.47. All matched types 0.62; BrainIR's B0 0.61. Their screen reads out both legs, so the gap is not specific to our procedure.

## 5. Part A: the gap

Primary types, 16 seeds, ratio to the matched ceiling: MANC left-right **0.59** (0.48-0.68), MaleCNS **0.64** (0.53-0.74), both real
gaps; cross-fly same side 0.41 and 0.32, opposite sides 0.32 and 0.50; R1 whole-type 0.38. Wiring summaries agree at 0.71-0.98 (two-hop
signed 0.71-0.84), but about half of the homologous connections exist on one side only. Neither side is worse everywhere (Wilcoxon p
0.86 and 0.31); the left-right difference is not shared across flies (-0.04, -0.10 to +0.02).

## 6. Part B

Sanity checks passed on both flies before any Block 2 number was read: identity transplant 50/50 identical; full transplant reproduces
the other side (2,094/2,096 and 1,960/1,960 outcomes; Spearman 0.9999 and 0.994). Closures (95 %):

- **Procedure (Block 1):** best in-bounds score over the 19-current grid closes MANC 0.17 (-0.07 to 0.38), MaleCNS 0.36 (0.08 to
  0.61), part of it lower seed noise (its ceiling rises; against its own ceiling agreement rises only 0.52 to 0.55 and 0.58 to 0.65);
  real gaps at all 19 fixed currents in MANC and at the 12 conclusive ones in MaleCNS; current transplant 0.00 to -0.27.
- **Location (Block 2):** own outputs 0.23 (-0.01 to 0.42) MANC, 0.17 MaleCNS; rest of network 0.34 (0.10 to 0.53) MANC, 0.21 MaleCNS.
- **Class (Block 3, MANC):** alone / left out: weights 0.09 / 0.55; one-sided connections 0.29 / 0.37; partnerless neurons 0.25 /
  0.58; size 0.03 / 0.81; sign -0.05 / 0.88; by B3.3 weights and size contribute in combination, sign does not; classes interact.
- **Count noise:** two Poisson copies of the raw counts agree at 0.40 (0.29-0.51) against the observed 0.37: **reproduces the
  left-right agreement with no fitted parameter** (pre-registered B4.5; over all six copy pairings, post hoc, about 86 % of the gap); negative binomial (1/k = 0.027 from 475,462 homologous pairs) 0.45, also
  reproduces. Floor 1 closes 0.23 (-0.01 to 0.44).
- **Rescue table** (share of flips rescued alone): MANC paired (13 flips): rest of network 69 %, floor 1 69 %, one-sided connections
  54 %, own outputs 46 %, size 46 %, weights 38 %, partnerless 23 %, sign 15 %; MANC Part A design (19): fraction rhythmic 63 %, best
  in-bounds 37 %, transplant 32 %; MaleCNS paired (29): rest 62 %, own 41 %; MaleCNS Part A design (32): 47 / 44 / 12 %.

## 7. Part C (cross-fly ratio, left-right ratio, drivers, SR / rewired drivers; none passes)

- Unfixed: 0.32, 0.55, 21.25, 0.31 / 16.
- 1 dose sweep: 0.31, 0.61, 46.5 (fails 3), 0.26 / 2. 2 pooled read-out: 0.33, 0.54, 31.0, 0.34 / 20.
- 3a floor 1: cross-fly not evaluable, 0.56, 20.5, no rewired control. 3b dropped (X9).
- 4 symmetrised: 0.39, 0.76 (not required), 22.25, 0.36 / 4. 5a pooled within side: 0.39, 0.57, 23.75, 0.45 / 20. 5b pooled across
  sides: 0.38, 0.61 (not required), 23.75, 0.39 / 8.
- 6 input-normalised and 8 all network fixes: fail the DNg100 control at every gain. 7 consensus: 0.32, 0.50, 20.75, 0.35 / 15.
- 9 combined: not run. No robust model.

## 8. Part D (EXPLORATORY, after unblinding; exam 1 AUROC, 95 %)

Fix 2 0.50 (0.37-0.63) (locked); post-lock: fix 4 0.47, 5a 0.47, 5b 0.46, 7 0.52, 1 0.41 (0.23-0.58). References: unfixed 0.43,
two-step counting 0.67. No fix moves exam 1 beyond its interval; fix 1 is below counting (-0.26, -0.51 to -0.01). Exam 2 not re-scored.

## 9. Part E

63 types, two sources (authors' model, two-step signed counting; no robust model, `forward/SOURCES_NOTE.md`). Fit on all 39 labelled
types (6 headless). Leave-one-out Brier 0.248 (model) and 0.239 (counting) against 0.242 for the base rate; AUROC 0.33 and 0.61.
Ten-entry check: ten of ten agree. The 15 decisive experiments: DNg43, DNp56, DNg32, DNp34, DNp45, DNp35, DNp26, DNg87, DNad006,
DNg91, DNp31, DNg78, DNg39, DNp44, DNp15 (probability gaps 0.05-0.28); 34 of their 59 lines are listed as available.

## 10. The adversarial review

**Strongest objection:** the headline's 0.40 against 0.37 rests on one pair of Poisson copies, and its interval holds both copies
fixed. Over all six pairings of the four stored noise copies, copies agree at 0.38-0.54 (mean 0.46), every pairing above 0.37; pooled,
count noise reproduces about 86 % of the gap (0.66-1.14), not demonstrably all. Verdict: the headline survives with qualification.

**Answer (`reviews_v4/ADVERSARIAL_ADDENDUM_v4.md`):** accepted. The pre-registered test is met as locked, but the pair is a low draw,
so RESULTS_3, the brief and the evidence map now say "almost as poorly as" and "most of the gap", with the six-pair figure marked
post hoc. I also took its point that "counting noise" can suggest reconstruction error: two Poisson copies have about a third of their
connections in one copy only (the review's post-hoc check), against half between left and right.

## 11. The brief's opening paragraph

> A published rate model built from the fly's nerve-cord connectome screens descending-neuron types: stimulate a type, ask whether the
> front-leg motor neurons become rhythmic. If the screen captures function shared by copies built by the same genome, a type's left and
> right copies, and the same type in two flies (MANC and MaleCNS), should agree about as well as the screen agrees with itself across
> seeds (the ceiling; agreement is the Spearman correlation of type scores). Sides, flies and the connectomes' reconstruction and
> annotation can differ, so a gap is a warning about the screen, not proof of an error.

## 12. Compute and wall-clock

GitHub: 289.1 of 300 runner-hours (286.3 by the step-time rule plus a lost runner's 2.9 h); about 76 of them gave no result (chunks
that hit the 340-minute limit, a lost runner, cancelled attempts). Modal: $36.17 logged of $41. Wall-clock about 23.5 hours.

## 13. What worries me

1. The headline rests on one MANC comparison: counting noise suffices for a gap this size, which does not prove the real left-right
   differences are counting noise.
2. Criterion 4's "few rewired drivers" (2) came from whole-type controls; the one-sided rewired controls give 2-20 (only the dose sweep
   reached 2, and it failed on agreement and on driver count), so that criterion was close to unattainable. It was pre-registered, but
   it shaped the verdict.
3. The forward probabilities are barely calibrated, and the authors' model gives 0.59 to every zero-score type, so the decisive list is
   mostly about counting.
4. About a quarter of the GitHub budget gave no result, and the partial-attempt machinery that recovered from it is new code
   (every campaign was checked complete, and every result-bearing campaign's determinism sample was identical).

## 14. What I would do next

1. Make the screen robust to count noise and pre-register it as a new version: average the prediction over Poisson copies, or use
   expected rather than thresholded counts, and test it with this run's criteria.
2. Run what the budget dropped: MaleCNS Block 3, floors 3 and 10, fix 3a's whole-type screen.
3. Repeat the left-right test with the authors' exact two-sided procedure in our simulator, to tie A0 and Part A together.
4. Get the 15 decisive experiments done (34 lines are orderable) and score the forward ledger.
