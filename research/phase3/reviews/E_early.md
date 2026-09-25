# Review E (statistics): early round, evaluation machinery

Scope: the experimental and resampling units, contamination routes, paired comparisons, Holm and non-inferiority, the calibration of
the tolerances, the verdict rule, and the tournament ranking. Candidate methods were not reviewed.

Scripts and outputs are in `.tmp/E/`:
- `exp1_rank.py`: the ranking rule;
- `exp2_nonfinite.py`: non-finite handling in A;
- `exp3.py` / `exp3.json`: C, D and E variability on 45 dev systems;
- `exp4_tau.py`: tolerance uncertainty;
- `exp5_k.py`: K / S5.

All of them use only the public dev data, `calibration.json` and the generator with the public dev seed. The generator reproduces the
stored dev trajectories: the check `assert np.allclose(sim["x"], t.x, atol=1e-3)` passes.

## Summary verdict

**Not ready to lock.** The trajectory-level statistics of A and C are mostly sound: the units are matched and the effect error is a
ratio of sums. The real hidden data use a separate seed per trajectory, so the trajectory is a defensible unit there. I found no
route by which hidden data reach a fit.

Five problems break pre-registered claims or the selection:
1. The tournament ranking breaks ties and NaNs by the order of the command-line list.
2. Non-finite predictions are silently dropped from A, and the reported n hides the drop.
3. Missing and abstained systems are silently dropped from the S1-S5 medians.
4. The Level C code does not implement the pre-registered primary family and Holm correction.
5. The closed (D) and microstate (E) conditions are point estimates compared to a threshold. The evaluator's own random seed decides
   them in about half of the systems.

## BLOCKERS

### B1. The tournament ranking breaks ties and NaNs by list order (the pilot's S8 is pure list order)

**Location:**
- `extra/scripts/tournament.py:297-301` and `extra/scripts/merge_rounds.py:43-47`: `order = sorted(elig, key=...)` followed by
  `ranks[m].append(r + 1)`.
- `tournament.py:129-131`: `--pilot` sets `skip_shared`.
- `tournament.py:279`: S8 is then NaN for every candidate.

**Problem:**
- Tied values get distinct ranks 1..n in the order of `--methods`, or in the order of the parts in `merge_rounds`.
- NaN is mapped to `inf`, so when every candidate is NaN the ranks are again the list order.
- In round 1 (the pilot), S8 is NaN for everyone, so one of the eight rank components is the command-line order.
- S6 and S7 are coarse rates with many ties. The pilot has a single non-compressible system (highdim_chaotic), so the recall term of
  S7 is 0 or 1.
- The pre-registered tie-break (fewer transition parameters, PROTOCOL section 9) is not implemented.

**Evidence** (`exp1_rank.py`, the code copied verbatim):
- Four identical pilot profiles get mean ranks 1, 2, 3, 4 in list order. Reversing the list reverses the ranks.
- Candidate Y is strictly better than X on S1, S2 and S3 and tied on the other five. With the order (X, Y), X wins (1.375 vs 1.625).
- In another pair, the winner flips when only the list order changes: X 1.125 / Y 1.875, then Y 1.25 / X 1.75.

**Consequence:** the halving elimination and the final selection can be decided by the argument order.

**Fix:**
- Use average ranks for ties (`scipy.stats.rankdata(..., "average")`).
- Drop from the mean rank any component that is non-finite for every candidate, and pre-register this rule.
- Implement the transition-parameter tie-break on the mean rank.
- Add a test with permuted method lists that asserts the ranks do not change.

### B2. Non-finite rollouts are silently dropped from A (and from the shortcut test), and `n` hides it

**Location:**
- `src/brainir_state/evaluate.py:114-121`: `boot_mean` filters `isfinite`.
- `evaluate.py:165`: `"n": len(v)` counts the values before the filter.
- `evaluate_cross.py:38`: `paired_diff` drops non-finite differences.
- `harness.py:173, 177-183`: the verdict uses these values.

**Evidence** (`exp2_nonfinite.py`): a PCA-k model is wrapped so that it returns NaN whenever |z0| is above its 70th percentile, i.e.
it declines the hard start states. On 8 dev systems:

| system | honest A | NaN-dodging A | reported n (dodger) | shortcut CI, honest | shortcut CI, dodger |
|---|---|---|---|---|---|
| syn-0dccdf2720 | 0.382 | 0.063 | 36 | [-0.118, 0.134]: fails | [-0.171, -0.067] on n = 19: passes |
| syn-358d98ba4f | 0.834 | 0.306 | 36 | | |
| syn-1f16e42a17 | 0.195 | 0.066 | 36 | | |

- The reported `n` stays 36 while only 9-19 trajectories are actually scored.
- S1 (`A / A_full`) inherits the bias.
- C is not affected, because a NaN numerator makes the ratio NaN and the verdict fails. But see B3 for S2.

**Fix:**
- Treat a non-finite prediction as a failure: set that unit to +inf, or to a pre-registered cap such as the persistence NMSE times 10.
- Report `n_nonfinite`.
- Compute `A`, `A_full` and the paired tests on the same unit set.
- Report `n` after the filter.

### B3. The profile medians are taken over each method's own subset of systems (missing not at random)

**Location:**
- `tournament.py:84-86`: `med` drops None and NaN.
- `tournament.py:195-197, 270`: `comp_ok` excludes failed fits and failed evaluations.
- `tournament.py:273`: C is NaN when every held-out pair is abstained (unsupported kinds) or diverged.

**Problem:**
- S1-S5 are medians over different systems for different candidates.
- A candidate that fails, times out, diverges or abstains on its hardest systems is scored only on its easy ones.
- PROTOCOL section 8 says the synthetic unit is the system instance, paired across methods. The profile is not paired.
- Eligibility allows up to 10 % failed fits. Evaluation errors are not counted towards eligibility at all (`tournament.py:171` counts
  fit records only).

**Fix:**
- Compute every S over the fixed list of suite systems, with failures, abstentions and non-finite values imputed as the worst possible
  value (for example the no-effect value 1 for C, 0 for R², +inf for A).
- Count evaluation errors towards eligibility.

### B4. Level C does not implement the pre-registered primary family or its Holm correction

**Protocol (section 8):** the primary family is A, C, D and E per full system on real hidden data, plus K on the synthetic FINAL suite
paired by instance, with Holm across these comparisons.

**Code:**
- `level_c.py:241-249` enters only A and C of the 3 full systems into `holm` (6 p-values).
- D and E are stored as two point values with no CI and no test.
- No script computes the K comparison on the FINAL suite. `tournament.py --suite final` has no paired K statistic and no p-value.
- `holm` drops NaN p-values (`evaluate_cross.py:71`), so a comparison that could not be computed (for example `n = 0` when either
  model abstains on every held-out pair) silently shrinks the family.

**Hypothesis ambiguity:** section 8 lists non-inferiority margins, but `_boot_p` tests two-sided superiority against 0. The direction
and the hypothesis of each primary test are not stated anywhere.

**Fix:** pre-register, and implement before the lock:
- The family, with m = 3×4 + 1 = 13 or whatever is chosen.
- For each member, the hypothesis: superiority, or non-inferiority with margin tau_A·A_baseline or 0.05.
- The D and E test statistics, with a trajectory-cluster bootstrap. See B5 for E; for D, bootstrap by trajectory with the folds
  refitted.
- A paired-by-instance K test on FINAL: a paired bootstrap or a Wilcoxon over systems.
- The rule that a comparison which cannot be computed counts as not rejected (p = 1) and stays in the family.

### B5. The D and E conditions are unstable point estimates: the evaluator's seed decides them in about half the systems

**Location:**
- `harness.py:190-195`: `closed = D <= tau_D` and `microstate_equivalent = E <= tau_E`, with no CI.
- `evaluate.py:297-309`: D's time sampling and folds come from `cfg.seed`.
- `evaluate.py:475-500`: E's CI bootstraps pairs as independent (pairs share states, and states share a trajectory). The ratio itself
  has no CI.

**Evidence** (`exp3.py`: PCA-k with the true k on 45 dev systems):
- **D.** Changing only the evaluator seed (0-5) moves D with a median SD of 0.114 and a median range of 0.30. Compare tau_D = 0.085.
  - The "closed" decision flips across seeds for **22 of 45 systems (49 %)**.
  - The −1 clip is hit 21 times.
  - The oracle's own calibration values span −0.62 to +0.45, i.e. the true latent "gains" 0.45 from microstate.
- **E.** Each ratio rests on 36 matched pairs, from 4 draws × 8 trajectories.
  - A bootstrap that resamples pool trajectories within draw gives ratio CIs whose width is 2.1× the point estimate (median).
  - tau_E = 0.0039 lies inside that CI for **19 of 45** systems.

**Consequence:** for these systems the pre-registered verdict (and "compact causal state discovered") is not reproducible under a
change of the evaluator's seed.

**Fix:**
- Give D and E trajectory-cluster bootstrap CIs. For E, resample pool trajectories within draw and recompute the ratio.
- Judge them like C: the upper CI ≤ tau.
- Or at least average D over a pre-registered set of fold seeds, and report the flip rate.

## MAJOR

### M1. The tolerances rest on 45 systems and a tail percentile; they are very uncertain and are transferred to real circuits unchecked

**Location:** `calibrate.py:105-108`. Bootstrap over systems (`exp4_tau.py`):

| tolerance | point | 95 % CI |
|---|---|---|
| tau_A | 1.31 | [0.37, 15.7] |
| tau_C | 3.18 | [1.97, 123] |
| tau_D | 0.085 | [0.027, 0.245] |
| tau_E | 0.0039 | [0.0020, 0.018] |

- tau_A is interpolated between the 5th and 6th largest of 45 gaps. The gap distribution includes 24.0 and 80 682.
- The same tau_A, tau_D and tau_E are applied at Level C to real circuits. These use a different dt, other horizons (250 ms against
  1 s), another E future and another numerical floor. No calibration or sensitivity analysis on real public data supports the
  transfer.

**Fix:**
- Report the tolerance CIs.
- Pre-register a sensitivity analysis: verdict counts at the CI ends of every tau.
- Either calibrate the real-circuit tolerances on real PUBLIC data (for example the references on `val`), or declare the real
  verdicts conditional on synthetic-calibrated tolerances.

### M2. The oracle cannot pass the verdict it calibrated; calibration and verdict treat abstention differently

**Evidence:**
- In `calibration.json`, `C_abstained ≥ 1` on **45/45** systems for the true-latent, full-state and PCA-k references. None supports
  `edge_remove`, and PCA-k also lacks `current`.
- `harness.py:188-189` requires `n_abst == 0`, so each reference fails "interventional" on every system.
- tau_C was computed on the non-abstained pairs only.
- The verdict pass rates at the calibrated tau:

  | reference | E ≤ tau_E | C point < 1 |
  |---|---|---|
  | true latent | 89 % | 31 % |
  | full-state ceiling | 60 % | 22 % |

**Consequence:**
- The verdict was never validated on the oracle, whose "compact causal state discovered" rate is 0 by construction.
- tau_E is set at the tail of an oracle, a bar that the full microstate misses on 40 % of systems.

**Fix:**
- Report the verdict distribution of the oracle and of the ceiling as part of the calibration.
- Give the calibration references edge_remove support, or define C on the supported families consistently in both places.

### M3. C's CI rests on very few, heterogeneous units, and one unit dominates the ratio of sums

**Units:** the dev suite has 9 held-out pairs per system: 1 combined_heldout, 1 current_group, 1 edge_remove, 2 group_silence,
2 kick_group, 1 kick_newtarget, 1 silence_newtarget. HELDOUT has 18 and FINAL 27.

**Evidence** (`exp3`, PCA-k):
- 7 scored units per system.
- The CI upper bound minus the point estimate has a median of 0.94.
- The point estimate is < 1 on 29 systems, but the CI upper bound is < 1 on only 13.
- **One single trajectory carries more than 50 % of the denominator Σd_true² in 78 % of systems.** The largest family carries 67 %
  (median).

**Consequences:**
- A percentile bootstrap with 7-27 units undercovers.
- The pooled ratio mostly measures the one family with the largest effect.

**Fix:**
- Bootstrap stratified by family.
- Report per-family ratios, which are already computed (`C_per_family`), alongside the pooled value.
- Pre-register whether the pooled C weights families equally, i.e. use the mean of the per-family ratios of sums.

### M4. The sharing rule's margins are mis-scaled, so S8 is decided by arithmetic, not by evidence

**Location:** `evaluate_cross.py:189, 192`; `tournament.py:262`.
- **A margin too loose.** The A non-inferiority margin is `tau_A × A_indep` = 1.31 × A_indep: a shared model up to 131 % worse is
  "non-inferior". tau_A was calibrated for a different question (oracle vs ceiling), not as a sharing margin.
- **C margin unattainable.** The C margin is an absolute 0.05 on an effect-error CI whose upper-minus-point is ~0.9 (M3). It is
  essentially never met, so the implementation groups can hardly be "supported".
- **Nulls tested on one criterion only.** For the unrelated pairs, `tournament.py:262` passes a synthetic LOIO success, so the nulls
  are judged on non-inferiority and parameter count alone.
- **S8 degenerate.** A candidate that always rejects scores 3/5 = 0.6 (2 groups, 3 pairs) without evidence.

**Fix:**
- Pre-register margins on the scale of their CIs: for example a relative A margin of 10-20 %, and a C margin relative to the
  independent model's C.
- Check the operating characteristics on the dev suite: the true-latent reference with shared vs independent fits on the groups and
  pairs.
- Report S8 separately for groups and for pairs.

### M5. The tournament's aggregate ranking has no uncertainty, and the selection is optimistic

**Problem:**
- The mean rank over S1-S8 is a function of medians over 15 (pilot) to ~45 systems, with no CI.
- S5 is at its ceiling: plain PCA gives median K R² of 0.991 (k_true), 0.998 (5·k_true) and 0.989 (k = N_obs) on 12 dev systems
  (`exp5_k.py`). The S5 rank is therefore decided in the third decimal and by k inflation.
- Rank aggregation is scale-free: a trivial difference counts as much as a large one.
- The HELDOUT profile of the selected candidate, and of the round-3 hybrid composed after seeing the feedback of rounds 1-2, is
  subject to winner's-curse bias. The strongest baseline for Level C is chosen by the same noisy ranking.

**Fix:**
- Bootstrap the whole selection over systems (resample systems, recompute S1-S8 and the ranks). Report each candidate's P(rank 1)
  and a rank CI, and in the pilot, P(eliminated).
- In the report:
  - state that HELDOUT values of the selected method are selection-biased and are not performance estimates;
  - use only FINAL (Level B confirmation) and Level C for claims;
  - disclose the number of candidates, rounds and feedback releases.
- Consider replacing ties within a CI with shared ranks.

### M6. `merge_rounds.py` does not check that the parts share a design

**Location:** `merge_rounds.py:39-40` checks only `suite`.

**Problem:** a pilot part (16 systems, no S8) can be merged with a round-2 part (all systems, shared fits). The ranks then compare
medians over different system sets, and S8 NaN is ranked last for pilot-only candidates.

**Fix:** record `pilot`, the system list, `g_systems`, `skip_shared`, the sim budget and the timeout in the aggregate, and refuse to
merge if they differ.

## Minor

- **Clustered A units.** The synthetic A set is 2 init_heldout + 2 param_heldout + 32 event-free pool trajectories. The pool
  trajectories come from only 4 held-out draws (8 each). 89 % of the A units therefore sit in 4 clusters, while the within-system CIs
  (shortcut tests, sharing) resample trajectories as independent. Resample draws, or report the pool part apart.
- **Silently skipped pairs.** `evaluate.py:195-197` skips a pair without counting it when the event is too late for any window. It is
  counted neither as scored nor as abstained. Report it.
- **p-value floor.** `_boot_p` returns p = 0 when no resample crosses 0. Report it as p < 1/2000 and use (1 + count) / (1 + B).
- **Fewer training data for the references.** They are fitted on `train` only (`suite_eval.py:173`), while methods fit on
  `train + val`. A_full is therefore slightly handicapped, which loosens the predictive condition. Fit both on the same data, or state
  it.
- **Distances standardised on test data.** E's distance (`evaluate.py:480-482`) and K's feature standardisation
  (`evaluate_synth.py:32`) use statistics of the evaluated test set. This is not a model fit, but it is not "normalisers from training
  data only" either. Use the train statistics.
- **k = 0 lost.** `suite_eval.py:276` uses `(info.get("k") or {}).get(sid) or ...`, which treats k = 0 as missing.
- **Stale reference cache.** The cache (`suite_eval.py:166-167`) is keyed by (system, k, seed) and not by the code hash. A change to
  the evaluator after the first run reuses stale references.
- **Default keys.** `sharing_comparison` / `loio_comparison` default to the real keys (`A_nmse_h250ms`, `C_w250ms`). All callers pass
  the keys, but the defaults are a trap for synthetic use.

## Checked and found sound

- **Contamination:**
  - fits see only a train / val hard-link view (`suite_eval.py:92-111`) under the sandbox guard;
  - the readout scale and the PCA basis come from train only (`suite_eval.py:263-265`, `harness.py:47-51`);
  - references are fitted on train only;
  - the dev simulation policy (`synthsim.py:47-92`) refuses the held-out draws, the group and structural interventions, and non-rest
    initial states;
  - G alignment is fitted on public val and measured on test (`evaluate_cross.py:131-164`);
  - hidden real seeds are ≥ 10⁹ and derived from the committed salt.
- **Real-data unit:** every hidden real trajectory has its own hidden parameter seed (`generate_real_hidden.py:95`), so the trajectory
  is a reasonable resampling unit for the real A and C, as section 8 states.
- **Pairing:**
  - `paired_diff` and `paired_ratio_diff` use the intersection of trajectory keys, so both models are compared on the same units;
  - the C effect error and its paired difference are ratios of sums with a common denominator (the true effect), resampled by
    trajectory, as section 8 requires;
  - the shortcut tests are paired by trajectory.
- **Holm:** the adjustment itself (`evaluate_cross.py:69-77`) is correct (step-down, monotone, capped at 1).
- **Calibration reproducibility:** the public evaluator reproduces the calibration's PCA-k values exactly (for example syn-0dccdf2720:
  A 0.38193, C 0.44105, D −0.15519, E 0.00163).
