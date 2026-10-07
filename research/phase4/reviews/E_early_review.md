# Review E (statistics): evaluation, calibration, selection — early pre-freeze round

Reviewer E. Scope: resampling units, contamination, CIs and paired tests, mediation / closure regressions, calibration of the
tolerances and its power rules, verdict rule A–H and the Phase 4 conclusion, multiplicity, selection, active-design success rule.
All numbers below come from scripts in `.tmp/E/` run with `./sbx` on the scratch package `.tmp/E/pkg` (src + extra merged). The
toy system is `extra/tests/test_lift_toysys.ToyLinear`, which has a known causal state. I used the exact model, controlled
corruptions of it, and test items laid out like the benchmark (identity cells × 4 states).

## Summary verdict

**Not ready to freeze.** Most of the resampling machinery in `stats.py` is correct: ratios of resampled sums, paired resampling of
the same clusters, the Holm step-down, `(1+count)/(1+B)` p-values, capping, and scoring abstentions as "no effect". The
normalisers come from public training data only.

However, the two regression-based verdict quantities cannot be trusted as implemented:
- **SMS (criterion D):** a numerical defect turns SMS into a random ±1 for models with gross read-in errors.
- **ICG_y (criterion E):** its sign changes with the cross-fitting seed for a model that is missing half of its state, and its
  bootstrap CI does not include that variability.
- **Dropped failures:** failed or non-finite latents are removed from D and E, so both can be gamed.

Four further problems:
- MEV testability depends on the model's own k, so E can be escaped.
- The selection code does not implement the pre-registered selection rule.
- The primary Holm family has no operational definition.
- The stratified system bootstrap behind the headline P_m rule is anti-conservative at 2–3 systems per type.

Every one of these can be fixed cheaply now.

---

## BLOCKERS

### B1. SMS explodes when an intervention-identity column is constant in a training fold (criterion D is random)
**Location:** `src/brainir_causal/evaluate_mediation.py:70` (`sd = Xtr.std(0) + 1e-9`) together with `:406`
(`IDs = standardise(IDF)` over ALL items, before the fold split).

**Mechanism.** An action key (for example `current|u`) whose items all fall in the test fold has a training-fold standard
deviation of about 1.7e-16 (floating-point residue of the global standardisation), not 0. `_design` divides by 1e-16 + 1e-9. The
training column becomes ±1e-7 noise that receives a nonzero ridge weight, and the test values become about 4e9. Whichever arm gets
the larger noise weight explodes, and the gain is clipped to −1 or +1.

**Frequency.** With the benchmark layout (2 cells × 4 states per family, keys specific to a cell), a key lands wholly in one fold
with probability 2·2⁻⁴ = 1/8 per key and per repeat. With dozens of keys this happens in essentially every repeat.

**Evidence.**
- `.tmp/E/med_diag2.py`: fold 0 has `has:current|1` with training sd 1.67e-16 and test deviation 4.1; fold 1 has `current|2`.
- `SMS_id`: `err_A_null = 4.29`, `err_B = 13,777`.
- `.tmp/E/med_demo2.py` (64 items):

| model | EE | SMS as implemented | SMS with constant training columns zeroed |
|---|---|---|---|
| exact | 0.000 | −0.010 | −0.010 |
| abstains on the pulse family | 0.547 | **−1.000 [−1, −1]** | +0.879 [0.81, 0.91] |
| read-in gain 0.5 on pulses | 0.137 | **−1.000 [−1, −1]** | +0.873 [0.80, 0.91] |
| wrong read-in (nuisance mixed into z) | 0.823 | **−1.000 [−1, −1]** | +0.861 [0.82, 0.90] |

`.tmp/E/med_scale.py` (120 items, 30 cells, 20 units, read-in gain 0.5 on every item): as implemented, SMS = −0.41 [−1.00, 0.64] /
+0.50 / −0.01 [−1.00, 0.80] over three item draws. With the fix it is 0.89 / 0.82 / 0.88. In this state, D passes grossly wrong
models and would fail good ones at random. `tau_SMS`, calibrated on these values, would be meaningless.

**Fix.**
- Build the identity columns inside each fold.
- Drop (zero) columns whose training-fold sd is below a relative tolerance, in both training and test.
- Never add 1e-9 to a standard deviation that is used as a divisor.
- Add a regression test: a constant-in-train column must not change predictions.

### B2. The x_res arms of D and the verdict ICG_y (E) have no demonstrated power; their CIs omit the fitting variability
**Locations:**
- `evaluate_mediation.py:153-171` (`residual_microstate`: training rows get x_res from inner half-fits, test rows from a fit on all
  training rows);
- `:514-529` (closure random-feature arm with 1 row per item);
- `stats.boot_gain` (resamples rows given ONE cross-fitting draw).

**Evidence.** The model encodes only the first of the two true state coordinates (a missing state). Scripts:
`.tmp/E/icg_miss.py`, `smsx_diag2.py`, `icg_diag.py`, `seed_var.py`.

- **SMS_x_res** (the "missing state" diagnostic of 5.3) is −1.000 [−1, −1] on three item draws, i.e. x_res appears to make
  predictions twice as bad. It becomes +0.85 when the training rows' residuals come from the same fit as the test rows, and +0.95
  with a fixed penalty. The train/test construction mismatch in the residual destroys the arm.
- **ICG_y (random-feature version, the verdict quantity)** for the missing-state model is +0.097 [0.04, 0.17], +0.004
  [−0.03, 0.03] and **−0.436 [−0.73, −0.08]** on three item draws. On a fixed item set it varies across cross-fitting seeds:
  +0.097, +0.045 [0.019, 0.079], +0.131, **−0.071 [−0.116, −0.040]**, −0.023, +0.046. The CIs for seeds 11 and 33 do not overlap.
  The linear ICG detects the missing state every time (+0.148, +0.202, +0.163).
- A model missing half its state therefore passes E's ICG part (upper CI below any tau ≥ 0) on some seeds and fails it on others.

**Fix.**
- Construct x_res identically for training and test rows: cross-fit the ZU→PC map on the outer training fold only, and apply the
  same map to both.
- Base the ICG verdict on the linear version, or fix the random-feature arm (fewer random features, penalised, capacity no larger
  than the rows allow).
- Average over at least 20 cross-fitting seeds and make the CI include that variability. For example, bootstrap over items with
  the fold assignment redrawn in each replicate, or combine the between-seed variance with the bootstrap variance.
- Before the freeze, run a power table on the generator for exact, read-in-error and missing-state models. The benchmark cannot
  claim the D/E criteria detect anything until this table exists.

### B3. Failed or non-finite latents are silently dropped from D and E (gameable)
**Location:** `evaluate_mediation.py:321-334` (`_usable`), used by `eval_mediation` and `eval_closure`.

EE caps failures, but SMS and ICG simply drop items whose `encode` returned non-finite values, or whose call raised. `encode` is
called separately from `intervention_effect` (`evaluate.py:95` vs `:109`), so a model can predict effects normally and return NaN
from `encode` exactly where its read-in is wrong.

**Evidence** (`.tmp/E/med_demo2.py`, `half_pulse_hide`):
- A read-in-error model with honest encodings: SMS = +0.87 (with B1 fixed).
- The same model with NaN latents on the wrong items: SMS = −0.001 [−0.04, 0.02], `used = 32 of 64`, while EE stays 0.137 (passes
  A).
- With the benchmark-like 16-item layout: SMS = −0.284 [−0.66, −0.04].

**Fix.**
- Score dropped items at the worst admissible value: Model A = the model's prediction, and the correction arm without their
  features (the gain computed with those rows at the null-arm error).
- Or: make D/E fail whenever more than a small pre-registered fraction of items (e.g. 5 %) is unusable.
- Report `n_dropped_failed` next to every SMS and ICG.

### B4. MEV testability is decided by the model's own latent dimension, so E can be escaped
**Location:** `evaluate_micro.py:253` (untestable when the median matched / median random latent distance exceeds 0.2).

On the protocol's pool layout (8 draws × 15 trajectories × 5 states; 21,000 candidate pairs; M = 20), `.tmp/E/mev_k.py` finds, for
isotropic whitened latents:

| k | 1 | 2 | 3 | 4 | 5 | **6** | 8 | 10 | 20 | 40 |
|---|---|---|---|---|---|---|---|---|---|---|
| rho | 0.001 | 0.028 | 0.083 | 0.142 | 0.189 | **0.237** | 0.314 | 0.366 | 0.527 | 0.663 |

With a 2-D causal state and extra coordinates, 2 + 4 already gives rho = 0.243 (untestable).

**Consequences.**
- Every model with an effective latent dimension of about 6 or more gets "E untested". The compactness limit N_obs/5 allows k up to
  about 40 on the full networks, and mechanism systems are not judged on compactness at all.
- A model whose MEV fails (upper CI 0.6 > tau) is "partially supported". The same model with MEV untestable becomes "causal state
  supported (microstate equivalence untestable)" (`.tmp/E/verdict_demo.py`, case 2). Being less identifiable earns a better label,
  which is non-monotone and gameable.
- For the real part, any honest model with k ≥ 6 can reach at most PARTIAL.
- Synthetic types with k_true ≥ 6 make even the true-state reference untestable.

**Fix.**
- Make testability model-independent. For example, a fixed matched set defined by a reference metric (truth, PCA-k of public x, or
  observation-matched), then test the model's latent pairing against it.
- Alternatively, keep the model's pairing but set M as a function of k so that rho is pre-registered to be attainable. Fall back
  to "E FAILED", not "E untested", when a model's latent cannot resolve neighbours that the reference pairing can resolve.

### B5. The selection code does not implement the pre-registered selection rule
**Locations:** `src/brainir_causal/select.py:40, 105-110`; `extra/scripts/tournament.py:457`, `:311` / `:394`.

- **Gates.** PROTOCOL §10: the candidate's pass rates of A, D and E must each be at least half of the TRUE-STATE reference's pass
  rates on the same synthetic systems (and A at least half of the full-state bound's on real systems). The code uses absolute
  thresholds (A ≥ 50 %, D ≥ 40 %, E ≥ 40 %) and never looks at a reference. `.tmp/E/verdict_demo.py` case 4: a candidate with D
  and E at 30 % is ineligible by the code but eligible by the protocol whenever the true-state rate is ≤ 60 %. Because of B4, E's
  pass rate is 0 for every model with k ≥ 6, so the absolute E gate can exclude every candidate.
- **Ordering.** The protocol says: "Before any tie-break, candidates are ordered by the gate metrics themselves (mean EE, then SMS,
  then ICG), which also orders them when none is eligible". This is not implemented. `rank()` orders only eligible candidates,
  starting with compression, and returns an empty order when none is eligible. The protocol sentence also contradicts its own
  lexicographic list (4)–(8) and has to be rewritten.
- **Strata.** The protocol asks for type-stratified ties; the driver stratifies by `kind`. With the pilot's 1 system per type,
  type strata would give zero-width CIs (see B6), so kind strata are actually safer. The protocol text should say so.
- **Fit seeds.** Only fit seed 0 enters selection, although Level B fits 3 seeds. Seed-to-seed variability is ignored in the tie
  bands.
- **Efficiency.** Criterion (6) is always missing (`per_system_values(..., efficiency=None)`), so it is always a tie.

**Fix.** Implement the protocol's relative gates with the reference pass rates recomputed on the round's systems. Rewrite §10 into
one unambiguous order: gates → gate-metric order when none is eligible → lexicographic (4)–(8). Average criteria over fit seeds.
Pre-register the strata (recommended: kind, or type-pairs, never single-system strata).

### B6. The stratified system bootstrap is anti-conservative at 1–3 systems per type (headline P_m rule)
**Location:** `stats.py:179-194` (used by `verdict.phase4_conclusion`, `select.compare` and `loop.active_success`).

Resampling n_h systems with replacement within a stratum shrinks the variance by a factor of (n_h − 1)/n_h. That factor is 2/3 at
Level C (3 per type), 1/2 at Level B (2 per type) and 0 with 1 per type, where the CI collapses to the point.

`.tmp/E/strat_cov.py` (23 compressible types, 400 replications):

| systems per type | true P_m | 95 % CI coverage | P(lower CI ≥ 0.5), the SUPPORTED condition |
|---|---|---|---|
| 3 | 0.5 | 0.863 | **0.072** (nominal ≤ 0.025) |
| 3 | 0.6 | 0.890 | 0.570 |
| 2 | 0.5 | 0.850 | **0.130** |
| 2 | 0.6 | 0.797 | 0.652 |

The synthetic SUPPORTED rule ("lower CI of P_m ≥ 0.5") is therefore about 3× too liberal at Level C. The same applies to the
lower CI of P_m − P_t ≥ −0.2 and to every type-stratified tie band.

**Fix.** Use the rescaled stratified bootstrap (multiply each stratum's deviations by sqrt(n_h/(n_h − 1))), or an unstratified
system bootstrap. For the binary fraction, also require the Clopper–Pearson bound (`stats.binomial_lower_ci` already exists and is
not used by the rule). Never use strata of size 1.

### B7. The primary confirmatory family (Holm, §11) is not operationally defined and not built anywhere
**Locations:** PROTOCOL §11; `verdict.py:290-309` (a generic helper only; `grep` finds no caller outside the tests).

"The locked method against the strongest baseline on A, B, C, D, H … 5 + 15 one-sided tests" leaves several things undefined:
- the statistic of each test. A and C are EE differences, but "B" (vs the ID shortcut) and "H" against a baseline are differences
  of differences that the protocol never defines;
- the margin for D (SMS), where "0.2 × the baseline's value" is meaningless for a gain that can be ≤ 0;
- whether each test is superiority or non-inferiority.

The EE margin of 0.2 × the baseline's value is estimated from the same confirmation data, so it is random. That changes the test's
size and should be fixed from Level B values before the lock.

In addition, `noninferiority()` uses the two-sided 95 % upper CI for "pass" (a one-sided 2.5 % test), but a one-sided 5 %
bootstrap p for Holm (`stats.py:222-228`). The two outcomes can disagree.

**Fix.** Pre-register a table with, for each of the 20 tests: statistic, direction, margin (a fixed number from Level B), unit of
pairing and the null hypothesis. Implement `build_primary_family(...)` with a test, and use one α convention.

---

## MAJOR issues

### M1. EE, the verdict quantity of A, B, C and H, is dominated by the strong-magnitude quarter of the items
**Location:** `evaluate.py:241-248` (ratio of sums, den = effect energy).

Effect energy scales with the square of the magnitude, and the classes are 0.1 / 0.3 / 1 / 3 × m_s. Strong items therefore carry
most of Σ den.

`.tmp/E/ee_strong.py` (120 benchmark-like items): strong items are 33–37 % of the items but carry **69–92 %** of Σ den. A model
that is exact on strong items and predicts "no effect" on every weak and moderate item gets **EE = 0.08–0.31** (upper CI 0.14–0.45)
and passes A with any delta_A ≤ 0.5, although it predicts nothing for two thirds of the interventions.

The ratio of sums is the right choice against noisy denominators, but on its own it does not measure "intervention effects are
predicted".

**Fix.** Make the verdict EE class-balanced: the mean over magnitude (or detectability) classes of the per-class ratio of sums,
with the same cluster bootstrap. Alternatively, require A per detectability class ≥ weak. Keep the pooled EE as a descriptive
figure.

### M2. Resampling unit within a system: items share identity cells and families that the CI ignores
**Locations:** `extra/brainir_causal/suites.py:1627` (`group = r.key`, one cluster per item) and `design_cells` (2 identity cells ×
4 states per family).

Grouping by item is correct at the state level: every test item has its own parameter draw and history. However, A, B, H and the
target shift are meant to generalise over targets and families, and only 2 target sets per family are drawn.

`.tmp/E/cell_cov.py` (12 held-out families × 2 cells × 4 states, cell-level log-error sd 0.3 / 0.6): the item-clustered 95 % CI of
EE_heldout covers the population EE **0.82 / 0.78** of the time; clustering by cell gives 0.88 / 0.91.

**Fix.** For A, B, C and H, cluster by identity cell. For H, preferably use two-stage clustering by family, then cell. Report the
number of cells beside every CI.

### M3. Calibration: the tolerances absorb the reference's structural abstention; the conjunction is not calibrated; the power rule has no uncertainty
**Location:** `extra/brainir_causal/calibrate.py:226-275`.

- **Structural abstention.** The TRUE-STATE reference declares every never-trained event kind unsupported (`refs.py:759-764`),
  which is 1–2 kinds per rotation, e.g. edge and param for R1. It abstains on those far-shift and composite items, and SMS
  correctly flags abstention. With B1 fixed, abstaining on one family gives SMS = +0.88 (the table in B1). tau_SMS = P90 of the
  reference's upper CI therefore measures the reference's missing kinds, not sampling noise: D becomes vacuous. The same holds for
  delta_H, the P90 of the reference's (EE_heldout − EE_infamily).
  **Fix:** compute the SMS / ICG / MEV tolerances on the items the reference supports (report the abstention share), or make the
  reference support every kind (a generic read-in for untrained kinds).
- **Conjunction.** Each tolerance is a marginal P90 of the reference, and SUPPORTED needs all of A, B, C, D, E, F, G and H.
  Independent criteria at 0.9 each give a joint pass rate of about 0.9⁶ ≈ 0.53. C and H pass less than 90 % by construction:
  delta_C comes from point gaps while the test uses the upper CI of the paired difference. P_t < 0.5 then makes the synthetic part
  "not attainable" by rule. The calibration records the reference verdict distribution but has no rule that acts on it.
  **Fix:** pre-register a target joint pass rate for the true-state reference (e.g. ≥ 0.8 SUPPORTED on dev) and solve for a common
  percentile, or declare in advance what happens when it is not met.
- **Power rule.** It compares the true-state pass rate over all systems with the OBS-SHORTCUT pass rate over the few trap systems
  (about 4–6 on dev), using point rates with no CI. Since the true-state pass rate is about 0.9 by construction, the rule reduces
  to "null passes ≤ 0.7", which is decided by a single system on 4–6 systems.
  **Fix:** a one-sided test of the pass-rate difference (Fisher's exact, or a bootstrap over systems), a minimum number of trap
  systems, and the same system set for both rates.
- **Transfer.** The dev tier is built at level B: no OOD or robustness items. At Level C, "all test items" of A, and the items
  entering SMS / ICG, include OOD and robustness items, so the item mix and the CI widths differ from the calibration. Real full
  networks have 120 D1 trajectories instead of 200, and mechanisms have N_obs 3–6 (q ≤ 6 PCs for x_res).
  **Fix:** restrict A, D and E to the item roles present in the calibration (in, target, near, far, hidden) and report OOD /
  robustness separately, as §5.12 already intends. Pre-register that real verdicts are conditional on synthetic tolerances,
  together with a sensitivity table (verdicts at both CI ends of every tolerance — already computed for the reference — also for
  the method).
- `tolerance_cis` resamples systems unstratified, and the power tables are in-sample. Minor, but worth a note.

### M4. Active design, rule (ii) (budget ratio) is strongly biased; the reported ratio is not the budget ratio
**Location:** `loop.py:280-342` (`_budget_to_reach`, cap = 2 × the largest budget, target = random's 3-seed mean at 100).

`.tmp/E/active_null.py` and `active_power.py` (simulated learning curves; 3 loop seeds; 200 / 100 replications):
- With the own designer identical to random, the estimated mean ratio is **1.44** (should be 1.0). Rule (i) false-positive rate:
  0.5 % (identical designers) to 3.0 % (random = own, fixed worse): acceptable. Rule (ii) false-positive rate: 0.
- With the own designer truly 2× as sample-efficient (true ratio 0.50), the estimate is 0.74, and the power of (ii) is 0.32
  (25 systems) / 0.58 (50 systems). At 1.5× the estimate is 0.97–0.98, with power 0.11–0.13.

The bias has two sources. The target is a noisy value of the reference curve, compared with a first-passage time of another noisy
curve. Curves that never reach the target are charged 4 × ref_budget. So (ii) is valid (conservative) but nearly powerless, and a
reported "needs X % of random's budget" would be wrong by about 45 %.

Also: the MDE helper (`calibrate.mde_paired`) is a one-budget normal approximation. The success rule needs 2 of 5 budgets against
2 comparators, so the stated MDE overstates power.

**Fix.**
- Compute random's own budget-to-reach with the same estimator on held-out loop seeds (leave-one-seed-out), and report the ratio of
  sums Σ b_own / Σ b_random.
- Treat non-reaching curves as censored (e.g. a Kaplan–Meier-type or monotone curve fit) instead of a fixed cap.
- Compute the MDE for the actual success rule by simulation on dev.

### M5. Verdict criterion F can never be computed in the implemented paths
**Locations:** `harness.py:382-397` and `:515`; `verdict.py:202-218`.

`evaluate_job` never passes `dimension`, so `dimension_status(k, limit, None, range)` gives `stable = None`, F is a missing input,
and no system can be SUPPORTED. `.tmp/E/verdict_demo.py` case 1: identical metrics give "partially supported" without refits and
"causal state supported" with F = stable.

At Level B this makes every category shown to developers at most PARTIAL. The Level C bootstrap-refit path (5 refits per system)
has no code that feeds `k_refits` into the verdict.

The calibration sets `stable = True` for every reference (`calibrate.py:188`), so P_t gets F for free while P_m must earn it, which
biases P_m − P_t against the method.

**Fix.** Implement and test the refit → `dimension_status` → verdict path. At Level B, either compute F from the 3 fit seeds or
exclude F from the Level B category explicitly. State the reference/method asymmetry in the protocol, or give the reference the
same refits.

### M6. Selection-induced optimism and reuse of the real systems
Level B selects on validation systems. Aggregate feedback over repeated rounds allows adaptive tuning to the validation suite. The
finalist and full stages run on **all real systems**, and Level C evaluates the **same 10 real systems** (fresh items only). The
synthetic confirmation suite is fresh, but the real verdicts are partly in-sample with respect to selection: system-specific
fitting persists across fresh items of the same network.

The Holm family does not account for selecting the best of K candidates. That is fine only because the claims are Level C claims,
and only for the synthetic part.

**Report should state:**
- the number of candidates and rounds evaluated on each real system before the lock;
- that real verdicts come from systems used in selection;
- the Level B → Level C drop of the winner (a winner's-curse estimate);
- that Level B scores of the selected method are optimistic and are never reported as performance.

Cap the number of feedback rounds in advance.

### M7. Failures are dropped from paired system comparisons
**Locations:** `stats.paired_system_boot:197-203` (drops systems with a non-finite value in either arm); `select._criterion_values`
and `compare` (compare only common systems).

A candidate whose evaluation fails, or yields NaN, on a hard system is compared on the easy systems only. The eligibility
denominator does keep failed systems, which is correct.

**Fix.** Charge failures the worst admissible value (e.g. NMSE cap 10 or EE 1). Report the count.

---

## Minor issues

- `stats.percentile_ci` silently drops non-finite replicates, while `boot_pvalue` counts them on the null side. Use one convention
  (count them against the claim).
- `loop.active_success` docstring says "ratio of sums"; the code averages per-system ratios. The two are equivalent only because
  the denominator is a constant.
- ICG "unshrunk base while ≤ 1 column per 4 rows": base = k + 3·n_u + 12 columns and about 60–80 training rows per fold, so the base
  is unshrunk only for k ≤ 3–8. The rule is inactive for most models. Say so in the protocol, or fit the base on item × lag rows.
- H compares POINT estimates for the gap (a documented resolution). With 8 items per family the gap is noisy. At least report its
  CI.
- The full-state bound: the protocol says "the better of FULL-STATE and the best full-state baseline, fixed at Level B", but
  `evaluate_job` never passes `fullbound_eff`, so the bound is always the FULL-STATE reference.
- MEV "testable" but non-finite is a failure (good). "Untestable because of the floor" should be reported per sequence to the
  developer aggregate.
- `feedback.py` reports pass rates to 3 decimals with MIN_CELL = 3. Over repeated submissions this allows differencing. Coarsen to
  0.05 and limit rounds.
- `calibrate.tolerance_cis` resamples systems unstratified and is only descriptive. Fine, but label it so.
- The observational NMSE averages windows within a group and then uses an unweighted bootstrap over groups (a mean of per-group
  means). This is consistent with §5.2, but note that it weights groups equally.

## Checked and found sound

- `stats.boot_ratio` / `boot_ratio_diff`: ratio of resampled SUMS; paired differences resample the same clusters with the same
  denominators (den depends on the truth only, `evaluate.paired_ee_diff`). Multinomial multiplicities are correct.
- The Holm step-down implementation (monotone adjusted p-values; missing p counts as 1); p = (1 + count)/(1 + B).
- Item capping (10 × den), failed predictions counted as the cap and never dropped from EE; abstentions scored as no effect
  (num = den, EE_i = 1), so abstaining everywhere gives EE ≤ 1 and fails A. "Predicting no effect" cannot pass A. G passing with no
  covered detectable item cannot rescue a model, because A is needed.
- Normalisers: pooled readout sd and PCA basis from the public `train` split only (twins and test data excluded), with the
  blow-up rule; whitening for MEV from encodings of public training data. I found no contamination from test or validation data
  into normalisers. Calibration runs on the dev tier only, with references only.
- Test items each have their own parameter draw and history, so item-level grouping is correct at the state level (see M2 for the
  cell level). The MEV CI resamples source trajectories within draws and recomputes the matched set per replicate (correct unit).
- Permutation-matched null arms are a sound capacity control in principle (once B1 and B2 are fixed). With B1 fixed, the exact
  model's SMS is about 0 (−0.01 [−0.03, 0.00]), and read-in or abstention errors give SMS ≈ 0.8–0.9 (the table in B1).
- Active design rule (i) controls false positives (0.5–3 % in simulation) and has high power at 25 systems (0.97 at 1.25×
  efficiency).
- The Phase 4 conclusion rule is monotone: upgrading any system's category never worsens the synthetic or real status. Declaring
  "no compact causal state" on compressible systems counts against P_m. The rule is not gameable by declaration.
- The ICG with the linear regressor is robust to padding the latent with irrelevant coordinates (k from 2 to 40: |ICG| ≤ 0.003,
  `.tmp/E/icg_k.py`) and detects a missing state coordinate consistently (+0.15 to +0.20).

Scripts: `.tmp/E/med_demo2.py`, `med_diag2.py`, `med_fix.py`, `med_scale.py`, `icg_k.py`, `icg_miss.py`, `smsx_diag2.py`,
`icg_diag.py`, `seed_var.py`, `mev_k.py`, `strat_cov.py`, `cell_cov.py`, `ee_strong.py`, `active_null.py`, `active_power.py`,
`verdict_demo.py`.
