# PREREG v6 audit (fresh reviewer, before the freeze)

**What was audited.** `PREREG_v6.md` as committed in b992bfd (unchanged at HEAD c5342c2), against RUN6_PROMPT section 6 and hard limits
1 to 3. Also audited:
- the reused definitions of PREREG v2 P1, v4 G/A/B4 and v5 G/R/S;
- `banc.py`, `gha6.py`, `lock6.py`, `banc_gate.py`, `prereg6_planning.py`, `test_gha6.py` and `agree.py`;
- the analysis code added in e2ef518 (`thirdfly_v1.py`, `posthoc_v6.py`, `screens6.py`, `overlap6.py`), which the freeze will hash;
- LOG L176 to L178 and `gates_v6/`.

**Severity.**
- **Blocker:** a verdict word that is forced by construction, or still choosable after BANC data exist.
- **Major:** an ambiguity or unlisted departure that needs a text change.
- **Minor:** a disclosure, a planning number or a test gap.

**What this audit did not do.** Nothing was simulated. BANC was read once, through `banc.groups()` (the type-match annotations), for one
check. Numbers marked "check" were computed here from the first two animals' locked tables (post hoc data) or from synthetic inputs, and
belong in Part Q (finding 9).

---

## Blockers

**1. C6's words are positive by construction.**
- *Where:* C6; `thirdfly_v1.c6`.
- *Problem:* For standardized scores, corr(mean(A, B), T) = (r_AT + r_BT) / sqrt(2 (1 + r_AB)). So each
  d_T = mean(r_AT, r_BT) x (sqrt(2 / (1 + r_AB)) - 1).
  - This is positive whenever the two sources agree with the target on average and are not identical, whatever the third animal contains.
  - Two of the three d_T use the already-seen MANC-MaleCNS agreement.
- *Check* (214 MANC-MaleCNS high types without DNg100, 2,000 resamples):
  - Third animal replaced by B2r's scores shuffled over types (no information): D was +0.029 to +0.056 in the first five shuffles, and
    its interval excluded zero in 10 of 20.
  - A1 as an informative stand-in: D = +0.070 (+0.036 to +0.103).
  - So "pooling helps" is a coin flip when BANC carries nothing, and C6's sentence that a real gain "may not be distinguishable from
    zero" is wrong.
- *Fix:*
  - Put the words on the one unseen target only:
    - d_M = rho(mean(MANC, MaleCNS), BANC) - rho(MANC, BANC);
    - d_C = rho(mean(MANC, MaleCNS), BANC) - rho(MaleCNS, BANC);
    - same type resamples for both. "Pooling helps" only if both intervals lie above zero.
  - Do not use "minus the better of the two": that maximum is biased against pooling.
  - Report the prompt's D beside it without words, and add a Part D row with this reason.
  - Restate the expected size and the power from a simulation on the first two animals.

**2. C8's code turns an undefined test into a positive verdict.**
- *Where:* `thirdfly_v1.c8` (bound by the lock).
- *Problem:* Suppose the 12 BANC outcomes are all equal, for example all 0, which is plausible if BANC has few drivers.
  - `agree.spearman` then returns NaN, and `perm >= rho - 1e-12` is False for every permutation.
  - So p = 1/100,001 and the words are "stability under count noise predicts the third animal".
  - Check (the 12 mean copy scores against zeros): p = 0.0005, positive words.
  - The rulebook has no rule for this case either.
- *Fix:*
  - Rulebook: "if rho is undefined, the words are 'not shown'".
  - Code: return before permuting, and count a NaN permutation as >= observed.
  - Add a unit test.
  - C2's and C4's word paths are already safe: they fall to the negative words.

**3. The rulebook and the frozen code disagree on DNg100 for five tests.**
- *Where:* G5 ("Part C's words rest on the version without it") and C3 ("three-animal set (182)"), against `thirdfly_v1`:
  - `c1` and `c2` use `c1_sets()`;
  - `c3`, `c6` and `c7` use `sets()["three_animal"]`, which is 182 types with DNg100;
  - only `c4` and `c8` drop DNg100.
- *Problem:* After the data, either version of C1 to C3, C6 and C7 could be cited as the pre-registered one. DNg100 is a top scorer in
  both seen animals and, by the gate, probably in BANC, so including it raises every agreement a little.
- *Fix:*
  - State for each test which set carries the words. Recommended: without DNg100 everywhere, so 181 types on the three-animal set, and
    C7's headline n* without it.
  - Have the code compute both versions and attach the words to that one.
  - Test that DNg100 is absent from each word-bearing set, as the C4 test already does.
  - Exempt C5 from G5's sentence.

## Majors

**4. C5 departs from the prompt, and Part D does not list it.**
- *Where:* C5 ("primary procedure, tuned unless B4 says otherwise"); `run()` passes `S[prim][2]`.
- *Problem:* RUN6_PROMPT says DNg100 is "predicted to be a driver in BANC under the unchanged tuned procedure".
  - Under B4's fallback, the tuned screen has just failed DNg100's 12-of-16 bar.
  - The sweep becomes primary only if DNg100 passes 6 of 8 seeds. So "pass" is nearly implied, and a tuned failure is reported as
    "pass".
  - C5 tests the type score (>= 0.5) and B4 counts seeds (12 of 16), so "C5 pass, screen invalid" can also happen.
- *Fix:*
  - Always judge C5 on the tuned screen.
  - Report DNg100's sweep result beside it, without words.
  - State how C5 relates to B4.

**5. X4 is out of date, and its amendment rule is weaker than run 5's.**
- *Where:* X4; Part D row 11; `lock6.py amend`.
- *Problem:*
  - e2ef518 committed the analysis code for Parts C, V, F and H before the freeze, but X4 and row 11 still say it is written after.
  - X4 ("a later change is an amendment row with its reason") and `lock6.amend` accept any change to ledger code, for any reason. That
    includes `banc.py` (sets, sides, matching) and the analysis code.
  - PREREG v5 X5 allowed bug fixes only: never a rule, criterion, seed or set, and with outputs before and after reported once the code
    had run on real data.
- *Fix:*
  - Rewrite X4 to list the frozen analysis files, and copy v5 X5's limits.
  - Require each amendment row to be committed and pushed before the data it affects are collected.
  - Delete row 11.

**6. Cases the rulebook leaves undefined.**
- **C3:** a BANC pair that is "not judged" (c < 0.2) falls into "inconclusive". Say "not judged".
- **C7:**
  - No rule for a pair that is not judged, or for rbar >= 1 (n* <= 0, so "rounded up" gives 0 or less).
  - Check: when more than about 2.5 % of resamples are infinite, numpy's interpolated 97.5th percentile is NaN.
  - Say: n* = 1 when rbar >= 0.8; "not computed" if a pair is not judged; the upper end may be infinity.
- **C4:**
  - n_X = 0 or n_Y = 0 gives p = 1 and "at chance". Say "not judged".
  - Under sweep-primary, the code swaps B1r and B2r for the dx-1 and ms sweeps but keeps A1, which has no sweep, at 16-seed halves. Write
    that down.
- **X2:** the drop order can remove `bs`, which B4 needs. Say that `bs` is never dropped when `bt` is invalid, and give the projection
  rule.
- **X3:** "investigated before its tests are read" leaves room for discretion.
  - Adopt v5's rule: a full re-run as a new campaign; if it still differs, the words are "not determinate".
  - Adopt v5 S8's rule for errored jobs: re-publish at most twice, then the key counts as an unusable seed.
  - `agree.compare` raises an error when a type lacks a seed half. Say what happens then.
- **G1 to G3:** the bootstrap resamples positions, so put the type order in the text (the code sorts by MANC type name).

**7. "Confirmed" is also what a broken build or type match would produce.**
- *Where:* C3's first-line sentence; B4.
- *Problem:*
  - "A real gap" needs only the ratio's upper end below 1.
  - A read-out, matching or build error also gives low agreement across animals, so "confirmed" is the default outcome of most
    failures.
  - DNg100 is the only positive control, and K was chosen on it. It can pass while everything else is wrong.
  - "Confirmed" says nothing about size: ratios of 0.80 and 0.38 both confirm.
- *Fix:*
  - The first line gives both BANC ratios with their intervals, beside the MANC-MaleCNS 0.38.
  - Pre-declare a descriptive wiring comparison to run after the freeze; hard limit 2 bars it only before the tag. For example: the
    two-step signed count per type, BANC against MANC and against MaleCNS, on the three-animal set.
  - Add a fixed caveat to the first line if that comparison falls below the first two animals' range (0.71 to 0.98).

## Minors

**8. Power statements.**
- **C4:**
  - The power is computed for N = 182 and n_X = 11 with DNg100.
  - The words rest on the MANC-BANC and MaleCNS-BANC high sets without DNg100, and A1 has no planning row.
  - Recompute from the annotations and the locked tables.
- **C8:**
  - The critical rho of 0.483 comes from a quantile of 2,000 draws.
  - Check (400,000 permutations, n = 12): P(rho >= 0.503) = 0.0496, so the one-sided 5 % point is about 0.50.
  - The stated power is therefore slightly high, and ties among BANC zeros lower it further.
- **C5 and C7:** no power or smallest-p sentence, although the prompt asks for one for every test.
- **C4's "at chance":** with power of 0.2 to 0.4 it will be read as "does not recur". Add a fixed sentence beside it giving the share's
  interval and the power.

**9. Part Q leaves things out.**
- `research/literature/pugliese_walking_cpg_detailed_notes.md`, written before run 6, holds BANC facts about DNg100 and its circuit:
  - signed counts (DNg100 to E1 198, E1 to E2 336, and so on);
  - DNg100's two BANC root IDs and annotated sides;
  - a derived rate of about 25 Hz at a current of 400;
  - 156 "motor module" rows, 27 of them not motor neurons.
- The gate's outputs beyond Part Q 4: active motor neurons per side (median left 3, right 2), their counts and frequencies.
- L177: BANC annotates DNg100 1605 as right, but it matches MANC's left DNg100. This foreshadows B2's unreliable-annotation branch.
- `banc.sign_check`: 13 rows with mixed labels carry outputs, and 87 rows have no outputs, by transmitter.
- This audit's own numbers from the first two animals: findings 1 and 8, and the checks in the sound list below.

**10. Some inputs are fixed outside any pre-freeze hash.**
- `dx-1-run4`'s result log (`MODAL_dx-1-run4/results.pkl`) feeds C3's companion comparison, and under B4 every primary comparison.
  - Only `LOCK_posthoc_v6` hashes it, and that lock may come after the BANC results are collected.
  - Put its SHA-256 in Part Q 6 or in the prereg lock.
- The annotation-only sets (the three-animal 182, the pairwise sets, C8's 12) are not written down.
  - Write them to `gates_v6/TYPE_SETS_v6.json` before the freeze, as v4 G9 did, and have the code read them.

**11. BANC's "high" confidence is weaker than MaleCNS's.**
- BANC: 0 ID-name conflicts among 1,221 ID-matched descending neurons. MaleCNS: 82 types with a conflict.
- This suggests BANC's `manc_121_cell_type` comes from the same match as the ID, so "no conflict" adds no evidence.
- Say so in G5 and in the limitations, and add a sensitivity analysis that also requires `same_name`.

**12. DNb08 is one of C8's 12 types, and its BANC outcome is partly foreseeable.** The authors' single DNb08 scored 0.000 in BANC.
Add a secondary analysis without DNb08, and mention this in C8's disclosure.

**13. Part V.**
- **V2's words** fire if any of the 80 member-and-current cells reaches 8 of 16 seeds.
  - Give the authors' own configuration (position 391 at 250) its own sentence first, then list the other cells.
- **Scoring:** state in the text what `part_v` does: every seed counts, the screen bounds are ignored, and a solver failure scores 0.
- **Read-out:** the read-out is B2r's 130 front-leg motor neurons, but the authors' notebooks scored the 129 module-labelled ones.
  - Either pre-declare a companion read-out, as the gate's diagnostic did, or say why none is needed.

**14. Tests and guards.**
- `test_one_sided_jobs_with_stand_in_sides` asserts `{...} >= set()`, which is always true, so the read-out masks are untested.
  - Assert the keys and the 68 and 71 motor neurons.
  - Checked by hand: a BH job equals `pa-manc-run4`'s stored job, `readout_L` included.
- `banc.require_unblind` checks only for the tag on origin, not the lock. Reuse `gha6.require_freeze6`.
- `det6` leaves out `bg-banc-run6`, although the prompt says every campaign. Add it (DNg100 only) or list it in Part D.

---

## Checked and found sound

- **Hard limit 2:**
  - Before the tag, no code path stimulates a BANC neuron other than DNg100 1605, or computes a wiring summary of BANC descending
    neurons.
  - The gate silences only E1, E2 and I2.
  - `dn_sides`, `halves`, `bh` and `bn` refuse to run.
  - The planning script and the tests read annotations only.
  - The gate spec (55c23ac) precedes the gate's packing (manifest `git_head` 55c23ac).
- **K and job specifications:**
  - K = 1 is unchanged: k_min 1, start current 128, B1's bounds, T = 1 s.
  - BT's job specification equals B2r's, and BS's and MS's equal `dx-1-run4`'s (tested).
  - BH's equals run 4's Part A (checked here).
  - Signing the unresampled counts reproduces the released matrix.
  - `simulate()` casts W to float64, so the integer matrix is harmless.
- **C8:**
  - 13 of the 16 drivers have a BANC group (confirmed with `banc.groups()`).
  - `mean_copy_score` exists for all 16 copies.
  - Within the 12, it does not stand in for the MANC score (Spearman -0.21 with B1r).
- **C2's departure is sound:** the cross-half halves use disjoint seeds, so pairing cannot enter. Copies without a floor match BANC.
- **Definitions and cited numbers:**
  - G1's words match `agree.words`.
  - These match the locked files: 0.59 and 0.64; 0.38 (0.26 to 0.49); copy-vs-copy 0.48 (0.36 to 0.60); run 5's p = 0.114, 0.035 and
    0.033.
- **Formulas:**
  - The Spearman-Brown algebra in C6 and C7 is correct, and C4's hypergeometric parametrisation is correct.
  - In the first two animals, driver status does not follow member count: 199 of 214 types have two members, Spearman 0.07. So C4's
    chance model is not obviously confounded.
- **Part D:** rows 1 to 10 are justified.

## Not checked

- `posthoc_v6.py` line by line (Part H is post hoc).
- The runner path of `group_v2` for one-sided read-outs (relied on run 4's use).
- The internals of `lock2`'s walk.
- The Zenodo configs themselves.
- The compute projection.
