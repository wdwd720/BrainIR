# Review E, round 2 (verification): statistics of the evaluation, calibration and selection

Reviewer E. Every demonstration from round 1 was adapted to the new code and re-run with `sbx` on a scratch package
(`.tmp/E/r2/pkg`, src + extra merged). Scripts and outputs are in `.tmp/E/r2/`. The toy system is still
`extra/tests/test_lift_toysys.ToyLinear` (known causal state), with test items laid out like the benchmark (identity cells × 4
states). The new generator is `extra/generator/src/p4synth`. A fix that I only read in the code and could not run is marked
**unverified**. The calibration outputs (tolerance values, power table) had not arrived when this review was written, so anything
that depends on them is **unverified**.

## 1. Per-finding table (round-1 findings)

| # | finding (round 1) | status | location of the fix | my re-run (numbers) |
|---|---|---|---|---|
| B1 | SMS explodes when an identity column is constant in the training fold | **fixed** | `evaluate_mediation.py` `_live_columns` / `_design` (lines 93-120); identity columns built per fold (`id_features(..., train_mask)`) | `r2/med_demo2.py`, 64 items: exact −0.013; abstain-on-pulse **+0.926 [0.75, 0.97]** (was −1.000); read-in gain 0.5 **+0.922**; wrong read-in **+0.946**. `r2/med_scale.py`, 120 items × 3 draws: gain 1.0 → −0.008 / −0.005 / +0.002; gain 0.5 → **0.954 / 0.938 / 0.951** (was −0.41 / 0.50 / −0.01) |
| B2 | x_res arm and ICG_y have no power; CIs omit the cross-fitting variability | **fixed** (subject to the pending power table) | the same x_res map for training and test rows (`residual_map`); linear ICG_y is the verdict quantity; 20 seeds; cell bootstrap redraws the seed (`_bootstrap_seeds`) | `r2/b2.py`, missing-state model: SMS_x_res **+0.62 / +0.75 / +0.49** (was −1.000 on every draw); linear ICG_y +0.434 [0.035, 0.732] / +0.243 [−0.028, 0.933] / +0.408 [0.060, 0.736]; exact model ICG_y ≈ 0.000 [−0.003, 0.002]. On one item set across fold-seed bases: +0.434 / +0.305 / +0.356 / +0.284, and every CI contains the others' points (was +0.10 … −0.44 with non-overlapping CIs). The CIs are wide (seed_sd 0.16-0.27), so whether D and E detect anything depends on tau_ICG and the power table, which I have not seen |
| B3 | failed or NaN latents silently dropped from D and E | **partly** | `select_items` + `MAX_UNUSABLE = 0.05` → `_failed` (+1) | 64 items with the read-in error hidden behind NaN latents: SMS **+1.000 (fails)**, was −0.001. But the 5 % allowance is still enough to hide a read-in error: `r2/hide5.py`, 120 items, read-in gain 0.2 on 2 cells (8 items), 6 of them given a NaN latent (5.0 % unusable): SMS **+0.747 → +0.000 [−0.05, 0.02]** (seed 1) and **+0.829 → +0.503** (seed 2), while EE_cb is unchanged (0.031). See N3 |
| B4 | MEV testability depends on the model's k (escape from E) | **fixed** | `verdict.system_verdict`: untestable → `mev_pass=False`, listed under "untestable" | `r2/verdict_demo.py`: MEV fails → "partially supported" (failed = [E]); MEV untestable → "partially supported" (failed = [E], untestable = [E]). No escape any more. Cost: any model with an effective k ≳ 6 cannot pass E (isotropic rho 0.237 at k = 6, round 1). This cost does not bite the synthetic true state: `r2/mev_truth.py` gives rho 0.010-0.026 (testable) on the first 9 of the 23 compressible types (1, 10, 11, 12, 15, 16, 17, 19, 24; k_true 2-3); the run on the other 14 had not finished when I wrote this. It remains a validity limit for high-k real models (stated in §5.5) |
| B5 | selection code ≠ the pre-registered rule | **partly** | `select.py` rewritten (relative gates, gate-metric order, failure charging, rescaled kind-stratified ties, `seed_average`) | Library verified (`r2/sel_ver.py`): the gates are relative (thresholds A 0.5, D 0.3, E 0.25 = half of a reference at 100/60/50 %); ineligible candidates are ordered by gate metrics. But the DRIVER does not run the rule, see N1: `rank` raises when no `true_state.json` exists (the driver never writes one); only `seeds[0]` is evaluated and `seed_average` is never called |
| B6 | stratified bootstrap anti-conservative at 2-3 systems per type | **fixed** | `verdict.phase4_conclusion`: one-sided Clopper–Pearson 97.5 % for P_m; unstratified paired bootstrap for P_m − P_t; `stats.stratified_system_boot` rescaled | `r2/sel_ver.py`: P(CP lower ≥ 0.5 \| P_m = 0.5, n = 69) = **0.015** (was 0.072). P(lower bound of P_m − P_t ≥ −0.2 \| true −0.2) = **0.020**. `r2/cell_cov.py`: rescaled stratified coverage 0.933 (3 per type) / 0.930 (2 per type); P(lower ≥ 0.5 \| 0.5) = 0.023 / 0.037 (was 0.072 / 0.130) |
| B7 | primary Holm family not defined or built | **fixed** | PROTOCOL §11 table H1-H6; `verdict.build_primary_family`, `primary_thresholds`, `primary_estimates`; one α convention in `stats.noninferiority` | `r2/pf.py`: builds m = 24 tests; missing systems are charged (3 charged in H6, p = 0.96); Holm adjusts across all 24; decision on p ≤ α, with the one-sided bound reported |
| M1 | verdict EE dominated by strong items | **partly** | class-balanced EE (`evaluate._ee_cb`, `stats.boot_class_balanced`) | `r2/ee_strong.py`, a model exact on strong items and "no effect" elsewhere (33-37 % of the items predicted): pooled EE 0.08-0.31 → class-balanced **0.665 [0.659, 0.667]**. That still passes A for any delta_A ≤ 0.33. A model exact on strong + moderate gives 0.332. A still does not require every class to be predicted; the new class weighting also brings its own CI problem (N2) |
| M2 | items share cells and families that the CI ignores | **partly** | cell clusters everywhere; two-stage family → cell for B and H (`mode="family_cell"`) | `r2/cell_cov.py`, 12 held-out families × 2 cells × 4 states, 95 % coverage: family_cell **0.943 / 0.940 / 0.897** (family sd 0.3 / 0.3 / 0.6). The "class" mode used by **A and C** resamples cells only: **0.883 / 0.907 / 0.800**. A and C pool items across families, so they need the family level too |
| M3 | calibration absorbs reference abstention; conjunction not calibrated; power rule without uncertainty; transfer | **partly** (values **unverified**) | `calibrate.py` rewritten: supported-item set, common percentile p for an 80 % SUPPORTED target, Fisher-exact power rule on the same systems, power table with read-in and missing-state corruptions; verdict items exclude OOD/robust | Code read and exercised with synthetic rows (`r2/calib_logic.py`). Two new problems: N4 (raising p makes criteria stop binding) and N5 (P_t is undefined relative to the supported-item calibration). Trap nulls on dev: 13 compressible systems with z_obs (`r2/traps.py`), which meets the ≥ 6 minimum |
| M4 | active-design (ii) biased / powerless | **partly** | `loop.budget_ratio` (leave-one-loop-seed-out targets, right-censored restricted mean, ratio of sums, rescaled paired bootstrap); both rules at α = 0.025 | `r2/active.py`: null mean ratio **0.998** (was 1.44); power of (ii) at 2× efficiency **1.00** (was 0.32-0.58). The estimate is still biased toward 1 (1.5× → 0.77 for a true 0.67; 2× → 0.63 for 0.50; 3× → 0.46 for 0.33). The union is NOT at ≤ 5 %, see N6 |
| M5 | criterion F never computed | **partly** | `verdict.dimension_status(k_values, level)`; `tournament._refit_ks` | `r2/sel_ver.py`: `dimension_status(3, 10, [3], level="B")` gives stable = **True** from one seed; Level C with 1 of 5 refits also gives **True**. The driver's default `--seeds 0` (tournament.py:609) and silently missing refit files make F pass by construction. See N7 |
| M6 | selection optimism / real-system reuse | **unverified** | PROTOCOL §10-11 text (counts, Level B → C drop, "never reported as performance") | text only; no report generator exists to check |
| M7 | failures dropped from paired system comparisons | **fixed** | `stats.paired_system_boot(worst=...)`; `select.failed_system_values` / `WORST`; `build_primary_family` charges missing systems | verified in `r2/pf.py` (3 charged systems) and `r2/sel_ver.py`. The conclusion's P_m − P_t still drops systems without a true-state verdict (no `worst`); minor |
| m1 | `percentile_ci` drops non-finite replicates | **fixed** | `stats._quantile_against` | `r2/minors.py`: 10 NaNs in 2,000 replicates move the upper bound from 0.975 to 0.980 (counted against) |
| m2 | active-design docstring "ratio of sums" | **fixed** | `loop.budget_ratio` | ratio of sums implemented (`r2/active.py`) |
| m3 | ICG "unshrunk base" is inactive for most k | **not fixed** | — | with ONE row per item, a fold now has about 60 training rows, so the base (k + 3 n_u + 12 columns) is unshrunk only for k ≤ 0-3. The protocol text still promises an unshrunk base |
| m4 | H gap only as a point estimate | **unverified** | `collect_metrics` builds `EE_gap` (verdict.py:240) | code read |
| m5 | full-state bound was always the FULL-STATE reference | **unverified** | tournament `choose_bounds` → BOUNDS.json → `fullbound_eff` | code read |
| m6 | MEV untestable reasons in the aggregate | **unverified** | `collect_metrics` MEV_rho / MEV_k | code read |
| m7 | feedback differencing / rounds | **fixed** | `feedback.RATE_STEP = 0.05`, `MAX_ROUNDS = 4`, `check_release` | `r2/minors.py`: 5 rounds → ValueError |
| m8 | tolerance CIs descriptive | **unverified** | `calibrate.tolerance_cis` + note | code read |
| m9 | observational NMSE weights groups equally | no change needed | — | — |

**Counts:**
- 23 round-1 findings (7 blockers, 7 majors, 9 minors).
- Fixed: **9** (B1, B2, B4, B6, B7, M7, m1, m2, m7).
- Partly: **7** (B3, B5, M1, M2, M3, M4, M5).
- Not fixed: **1** (m3).
- Unverified: **5** (M6, m4, m5, m6, m8).
- No change needed: **1** (m9).

---

## 2. New findings

### BLOCKERS

**N1. The tournament driver does not run the selection rule (the gates crash; only one fit seed is used).**
- *Location:* `extra/scripts/tournament.py:509-518` (`_ref_values` reads `<round>/true_state.json` and `full_state.json`, which the
  driver never writes; its own docstring says "the references are evaluated but not turned into a candidate row");
  `:535-537` → `select.rank(..., true_state=None)` → `select.gates` raises.
- *Evidence* (`r2/sel_ver.py`): `rank(c, true_state=None)` gives `ValueError: no true-state reference result on any of the round's
  20 synthetic systems: the gate cannot be evaluated`. So `cmd_decide` cannot produce a decision for any round that contains
  synthetic systems.
- *Also:* the evaluations use `ev_specs = [(m, sid, seeds[0]) ...]` (tournament.py:283 and the Modal path :446). `seed_average`
  is never called (only its tests use it), and the default is `--seeds 0` (:609). §10's "values averaged over the round's fit seeds"
  and the Level B F criterion over 3 seeds are therefore not what runs.
- *Fix:*
  - Write the TRUE-STATE and full-state-bound per-system `per_system_values` rows in `assemble_round` (the references are already
    evaluated there).
  - Evaluate every fit seed and call `seed_average` before `rank`.
  - Make 3 seeds the default at Level B and refuse fewer.
  - Add an end-to-end test `run → decide` on the toy tier.

### MAJORS

**N2. The class-balanced verdict EE has classes with 1-3 cells, and its within-class bootstrap is not rescaled, so A's CI under-covers.**
- *Location:* `stats.CellDesign.weights(mode="class")` (stats.py:283-287) and `class_balanced_from_cells` (:299-311).
- *Mechanism.* With 2 identity cells per family (cell 0 moderate, cell 1 weak or strong), classes such as `hi` (one or two `*.hi`
  families), `na` (silencing / edge removal) and, on small systems, weak or strong have only 2-4 cells. Resampling n_k cells with
  replacement shrinks a class's variance by (n_k − 1)/n_k, and the class-balanced mean gives each class the same weight. This is
  the same defect that was fixed for system strata in B6.
- *Evidence* (`r2/cb_cov.py`, cell-level log-sd 0.5, 400 replications):

  | cells per class (moderate / weak / strong / hi / na) | 95 % coverage | P(upper CI < truth) (nominal 0.025) |
  |---|---|---|
  | 14 / 7 / 7 / 2 / 6 | 0.850 | 0.113 |
  | 14 / 7 / 7 / 2 / 2 | 0.795 | 0.133 |
  | 6 / 3 / 3 / 2 / 2 | 0.772 | 0.155 |

  A ("upper CI < 1 − delta_A") is therefore passed about 5× too easily at the boundary. C uses the same mode.
- *In `family_cell` mode (B and H),* a class that is absent from a replicate is silently dropped from that replicate's mean
  (`present = D > 0`), so the statistic changes definition across replicates.
- *Fix:*
  - Rescale each class's resampled cell sums by sqrt(n_k / (n_k − 1)).
  - Merge classes with fewer than 3 cells into their neighbour (hi → strong, below → weak), or require at least 3 cells per class.
  - Use two-stage family → cell resampling for A and C as well (M2).
  - In replicates where a class is missing, charge it rather than dropping it.

**N3. The 5 % unusable allowance is large enough to hide one family's read-in error from D (B3 residual).**
- *Location:* `evaluate_mediation.select_items` / `MAX_UNUSABLE` (5 %).
- *Evidence* (`r2/hide5.py`, 120 items): a read-in error on 2 cells (8 items) gives SMS 0.747 / 0.829. Making 6 of those 8 items'
  latents NaN (5.0 % unusable, just under the limit) gives SMS **0.000 [−0.05, 0.02]** / 0.503. EE_cb and A are unaffected (0.031),
  because `intervention_effect` still answers. The benchmark has 8 items per family, so 5 % of 120-160 items is one family.
- *Fix:*
  - Keep unusable items in the ID arm, which needs no latent: its features are built from the events.
  - For the x_res arm, compute the residual from u alone for those items.
  - Or score an item whose `encode` fails while `intervention_effect` succeeds as FAILED (the EE cap) too, so the latent failure is
    never free.
  - At the least, set MAX_UNUSABLE below one cell (e.g. 2 %).

**N4. The common-percentile search can buy the 80 % target by switching criteria off.**
- *Location:* `calibrate.calibrate_at` / `common_percentile` (calibrate.py:447-468).
- *Mechanism.* At each candidate p, the tolerances are loosened AND the power rule is re-run at those tolerances. A higher p lets
  the nulls pass D and E too, so the criteria stop binding. Non-binding criteria are removed from SUPPORTED, so the true-state
  support rate rises because the criterion is gone, not because the reference passes it.
- *Evidence* (`r2/calib_logic.py`, synthetic calibration rows with a 10 % heavy tail in the true state's SMS / ICG / MEV upper CIs
  and nulls spread over [0.25, 0.7]):
  - p = 90: D and E_icg bind, support 0.80.
  - p = 95: nothing binds, support 1.00.
  - Over 200 such calibrations, 107 chose p > 90, and in **101** of them a criterion that bound at p = 90 no longer bound at the
    chosen p.

  Whether the real calibration shows this depends on the pending outputs.
- *Fix:*
  - Fix the binding flags at p = 90, or require that a criterion binding at p = 90 still binds at the chosen p. If it no longer
    binds, declare "not attainable" rather than dropping it.
  - Record in `calibration.json` the binding flags at every p (already in the table) and the reason for the choice.

**N5. P_t and the "not attainable" rule are defined on a different item set from the one the calibration targets.**
- *Location:* PROTOCOL §7 vs §9; `calibrate.calibrate_from_inputs` (supported items only); no code computes P_t at Level C
  (`grep` finds no caller of `phase4_conclusion` outside the tests).
- *The mismatch.*
  - The tolerances and the 80 % SUPPORTED target are computed on the verdict items the TRUE-STATE reference supports. It abstains
    on never-trained event kinds; `row["abstention_share"]` records this.
  - The conclusion rule's P_t is "the same [verdict] for the TRUE-STATE reference … on the same systems", i.e. on ALL verdict items.
    There it scores its abstentions as no effect: H fails on the far-shift families, and D sees the abstention.
  - A reference that is 80 % SUPPORTED in calibration can therefore have P_t < 0.5 at Level C. That triggers "criteria not
    attainable" and caps the synthetic part.
- *Fix:* pre-register one definition for both places, and implement P_t with a test. Either P_t on the supported items only, with
  the method also reported on that subset, or calibration on all verdict items.

**N6. The active-design union rule exceeds 5 % under the null when the fixed design is weaker than random.**
- *Location:* `loop.active_success` (rule (i) "≥ 2 of 5 budgets", each one-sided at 0.025; rule (ii) rescaled ratio bootstrap).
- *Evidence* (`r2/active.py`, `r2/active_null2.py`, 800 replications; the own designer is statistically identical to random):

  | scenario | P(i) | P(ii) | P(i or ii) |
  |---|---|---|---|
  | fixed worse by 0.05, 50 systems | 0.033 | 0.028 | 0.048 |
  | fixed worse by 0.10, 25 systems | **0.049** | **0.041** | **0.069** (SE 0.009) |

  - Rule (i) is not a level-0.025 test, because of "≥ 2 of 5 correlated budgets". Once `fixed` is clearly beaten, only the
    random comparison is binding.
  - Rule (ii) is liberal at 25 systems.
  - §5.17's claim that the union stays ≤ 5 % is false in this regime. With identical designers it is 0.020-0.030.
- *Fix:*
  - Calibrate (i) as one test: e.g. require the one-sided bound on the MEAN difference over the 5 budgets, or Bonferroni over the
    budgets (α/5 each).
  - Use a small-sample-corrected interval for the ratio, e.g. BCa or Fieller.
  - Check the union's size by simulation in `mde_by_simulation` under a null with a weaker `fixed`.

**N7. Criterion F can pass by construction (one seed, or missing refits).**
- *Location:* `verdict.dimension_status` (verdict.py:194-216); `tournament._refit_ks` (:174-189).
- *Evidence* (`r2/sel_ver.py`): `k_values=[3]` gives stable = True at level B and at level C. `_refit_ks` skips missing or failed
  refit files, so 1 of 5 refits gives stable. Combined with the driver's single seed (N1), F cannot fail at Level B.
- *Fix:* require exactly 3 seeds (B) or 5 refits (C). A missing or failed refit counts as a disagreeing k, so the result is
  "unresolved" rather than silently dropped.

### MINORS
- **N8.** The budget-ratio estimate is still biased toward 1 (true 0.50 → 0.63; 0.33 → 0.46; `r2/active.py`), because of the
  checkpoint grid and censoring at 200. It is valid, since the bias is conservative, but the reported "needs X % of random's budget"
  overstates the ratio by 20-40 %. Report it as a bound, or estimate it from a fitted curve.
- **N9.** The suite-level H4 of the primary family tests the MEAN over systems of SMS points against tau_SMS, but tau_SMS is a
  percentile of per-system UPPER CIs. That is a lenient boundary for a mean. H1 / H5 use delta_A, a CI width, as the boundary of a
  mean EE. State in the protocol that these are margins, not CI widths, or re-derive them for means.
- **N10.** `phase4_conclusion` pairs P_m − P_t only over systems with a true-state verdict. Missing true-state results are dropped,
  not charged (no `worst`). Charge them, or report the count.
- **N11.** (Generator, informative.) The dev tier has 46 compressible systems (k_true 1-4: 4 / 23 / 18 / 1) and 13 compressible
  systems with z_obs (`r2/traps.py`). The power rule's obs-shortcut arm is therefore feasible (≥ 6), but a one-sided Fisher test
  at n = 13 needs, for example, 12 of 13 true-state passes vs at most about 7 of 13 null passes. D and E will bind only where the
  traps are strongly exposed. The first 9 compressible types checked have easily testable true-state MEVs (rho ≤ 0.026).

## 3. Verdict

**Not ready to freeze.** The round-1 statistical defects in the metric code are genuinely fixed, and I verified each by re-running:
- SMS and ICG now detect read-in errors and missing states, and the exact model scores 0;
- the cross-fitting variability is inside the CIs;
- the P_m rule has nominal size;
- the primary family exists and runs;
- failures are charged.

But the machinery that turns these metrics into a selection and a conclusion still does not run as pre-registered:
- the tournament's decide step crashes on the relative gates and uses one fit seed, with F trivially stable (N1, N7);
- the new class-balanced EE is about 5× too liberal at A's boundary because tiny classes are bootstrapped without rescaling (N2);
- the 5 % unusable allowance still hides one family's read-in error from D (N3);
- the calibration's percentile search can meet its 80 % target by switching D and E off (N4), and P_t is defined on a different
  item set from the one the calibration targets (N5);
- the active-design union exceeds 5 % in a plausible null (N6).

All of these are small code or protocol changes. The calibration outputs (tolerances, binding flags, power table) have to be
reviewed before the freeze, because whether D and E have any power is decided there.
