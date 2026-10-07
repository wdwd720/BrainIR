# Review E, round 3 (verification): statistics of the evaluation, calibration and selection

Reviewer E. Every demonstration was re-run with `sbx` on a scratch package (`.tmp/E/r3/pkg`, src + extra merged). Scripts and outputs
are in `.tmp/E/r3/`.
- The orchestrator test suite was run with `.tmp/E/r3/run_tests.py`. It stubs the redacted engine package `brainir`, and I gave the
  toy tier a DUMMY salt / commitment in my own scratch area (`.tmp/E/data`, `.tmp/E/benchmarks`) so its salted seeds can be drawn.
- The generator in the room is still the round-2 version: `SYNTHETIC_BENCHMARK.md` has no section 14 and `truth()` has no `d_draw`.
- The calibration and MDE outputs have not arrived.

Anything that depends on those three (the revised generator, the calibration outputs, the MDE outputs) is marked **unverified**.

## 1. Per-finding table

### Round-2 findings (reviews/E/E2_review.md)

| # | finding | status | location of the fix | my re-run (numbers) |
|---|---|---|---|---|
| N1 | tournament decide crashed on the gates; one seed only | **fixed** (library and driver; the toy end-to-end run is recorded in section 4) | `tournament.py`: `ev_specs` over all seeds (:323), `assemble_round` writes `seed_averaged` and `true_state.json` / bound rows (:395-432), `decide_round` (:642-) | orchestrator tests `test_tournament_decide.py` (path-patched copy `.tmp/E/r3/test_tournament_decide_r3.py`): `refuses_fewer_than_three_seeds`, `decide_fails_loudly_without_true_state_rows`, `reference_rows_write_true_state_and_bound_rows` and one more **pass** (4 of 4 unit tests); the end-to-end toy run: see section 4 |
| N2 | class-balanced EE CI anti-conservative with small classes | **partly** | `stats.class_balanced_estimate` / `jackknife_class_balanced` / `merge_small_classes` (stats.py:300-437) | `r3/jk_cov.py` (400 replications each, family and cell random effects, heavy-tailed items, `hi` and `na` classes). See the table below this one. Fine at 12-20 families; liberal at 6-8 families; badly liberal below 6 families, where the unit switches to the CELL and family effects are ignored (N-new-4). The paired difference (`r3/jk_diff.py`) is conservative on the upper side (P(upper < truth) 0.005-0.007) but covers only 0.85-0.91 |
| N3 | 5 % unusable allowance hid a read-in error | **fixed** | latent-missing items stay in both arms (residual from u alone); `MAX_UNUSABLE` 1 % | `r3/hide5.py`: 6 NaN latents on the 8 read-in-error items: SMS **0.752** (was 0.000) and 0.829 (unchanged). `r3/nanlat.py`: NaN latents on ALL 120 items: exact model SMS −0.007 but ICG_y **+0.514 [0.085, 0.763]** (E fails, as it should); missing-state model SMS 0.608, ICG 0.514. A failed latent can no longer help |
| N4 | percentile search switched D/E off | **fixed** | `calibrate.common_percentile` (flags fixed at p = 90; "not attainable" if a base-binding criterion loses power at the chosen p) | `r3/calib_logic.py`, 200 synthetic calibrations (round-2 row model): 103 of 200 "not attainable", every one because binding was lost; none silently drops a criterion. See N-new-2 for the remaining gap |
| N5 | P_t on a different item set from the calibration | **fixed** (library); the Level C driver does not exist yet | `verdict.phase4_conclusion` (item_sets, `method_same_items`, charging); `calibrate.true_state_categories` / `model_categories`; `calibrate_from_inputs(extra_models=...)` | `test_eval_review_r2.py` (incl. `test_N5_method_scored_on_the_true_states_items`) **passes** (56 tests with verdict/select). A method's dimension given as missing blocks SUPPORTED (code read) |
| N6 | active-design union > 5 % under a weak-fixed null | **fixed** | `loop.active_success` (i) one test per comparator on the mean over budgets; (ii) `budget_ratio` delta-method log bound | `r3/active3.py`, 600 null replications each: see the active-design table below this one |
| N7 | F passed with one seed / missing refits | **fixed** | `verdict.dimension_status` (`n_required`, missing = disagreeing) | `r3/f_check.py`: B with one seed [3] → **False**; C with 1 of 5 → **False**; C [3,3,3,3,None] → False; B [3,3,3] → True. See N-new-5 (self-reported range) |
| N8 | budget ratio biased toward 1 | **fixed** (as reporting) | PROTOCOL 5.17: R reported as an UPPER BOUND | `r3/active3.py`: 1.25× → 0.875, 1.5× → 0.770, 2× with a plateau → 0.839 (true 0.80 / 0.67 / 0.50); conservative, as now stated |
| N9 | H4 / H1 margins lenient for means | **partly** (declared, not changed) | PROTOCOL 11 "MARGINS" paragraph | text only: tau_SMS (a percentile of per-system UPPER CIs) is still the null boundary for a MEAN of SMS points. It is now stated, not re-derived |
| N10 | missing true-state verdicts dropped in P_m − P_t | **fixed** | `phase4_conclusion` charging (missing = not supported for attainability, supported in the difference) | code read; covered by the verdict tests that pass |
| N11 | trap-null feasibility (informative) | n/a | — | the dev tier still has 13 trap nulls (round-2 generator); unverified for the revised generator |

**N2 — jackknife-t coverage (`r3/jk_cov.py`)**

| families (hi, na) | 95 % coverage | P(upper < truth) (nominal 0.025) |
|---|---|---|
| 20 (2, 4) | 0.938-0.958 | 0.040-0.058 |
| 12 (2, 3) | 0.925-0.958 | 0.028-0.065 |
| 8 (1, 2) | 0.873-0.912 | **0.087-0.125** |
| 6 (1, 1) | 0.905-0.932 | **0.062-0.090** |
| 5 (1, 1), cell units | **0.625-0.800** | **0.175-0.287** |

**N6 — active-design false-positive and power rates (`r3/active3.py`)**

| scenario | replications | P(i) | P(ii) | P(i or ii) |
|---|---|---|---|---|
| own = random, 50 systems (null) | 600 | 0.012 | 0.027 | 0.030 |
| own = random, 25 systems (null) | 600 | 0.008 | 0.017 | 0.023 |
| fixed worse by 0.05, 50 systems (null) | 600 | 0.022 | 0.025 | **0.037** (was 0.048) |
| fixed worse by 0.10, 25 systems (null) | 600 | 0.028 | 0.018 | **0.037** (was 0.069) |
| curves plateau after 50, 25 systems (null) | 600 | 0.003 | 0.015 | 0.017 |
| own 1.25× as efficient, 25 systems (power) | 200 | 0.885 | 0.355 | 0.90 |
| own 1.5× as efficient, 25 systems (power) | 200 | 1.00 | 0.825 | 1.00 |
| own 2× as efficient with a plateau, 25 systems (power) | 200 | 0.88 | 0.265 | 0.88 |

### Round-1 findings left partly / not fixed / unverified in round 2

| # | finding | status | location | re-run |
|---|---|---|---|---|
| B3 | failed latents dropped from D/E | **fixed** | see N3 | `r3/hide5.py`, `r3/nanlat.py` |
| B5 | selection code ≠ rule | **fixed** (with N1) | see N1 | tests above |
| M1 | verdict EE passes A with most items unpredicted | **partly (unchanged)** | — | `r3/ee_strong.py`: a model exact on strong items and "no effect" on everything else (33-37 % of the items predicted) has class-balanced EE **0.665 [0.662, 0.669]**. It passes A for any delta_A < 0.33. Exact on strong + moderate: 0.332. A still does not require every class to be predicted |
| M2 | CI ignores family structure | **partly** | family jackknife | see N2: fine at ≥ 12 families, liberal below |
| M3 | calibration | **partly / unverified** | `calibrate.py` rewritten; outputs pending | logic verified (N4, N5); tolerance values, power table and binding flags unverified. See N-new-1 and N-new-2 |
| M4 | active-design (ii) | **fixed** | see N6 / N8 | `r3/active3.py` |
| M5 | F never computed | **fixed** | see N7 | `r3/f_check.py` |
| M6 | selection-optimism reporting | **unverified** | PROTOCOL 10-11 text | no report generator to run |
| m3 | ICG unshrunk base inactive | **fixed** (documented + reported) | PROTOCOL 5.4; `eval_closure` `unshrunk_base` | `r3/minors.py`: 120 items → `unshrunk_base = False`, reported |
| m4 | H gap CI | **fixed** | `collect_metrics` `EE_gap` | `r3/minors.py`: EE_gap reported with its CI (27 cells) |
| m5 | full-state bound | **unverified** | BOUNDS.json, `bound_effects` (uses `seeds[0]`'s evaluation of a baseline) | code read only |
| m6 | MEV untestable reasons | **unverified** | `collect_metrics` MEV_rho / MEV_k | code read |
| m8 | tolerance CIs descriptive | **fixed** | `calibrate_rows` `tolerance_ci_note` | code read + the calibration tests pass |

**Counts** (11 round-2 findings + 13 carried round-1 items = 24):
- fixed: **15** (N1, N3, N4, N5, N6, N7, N8, N10, B3, B5, M4, M5, m3, m4, m8);
- partly: **5** (N2, N9, M1, M2, M3);
- not fixed: **0**;
- unverified: **3** (M6, m5, m6);
- n/a: **1** (N11).

---

## 2. New findings

### BLOCKER

**N-new-1. The TRUE-STATE reference is not a complete causal state under the benchmark's per-trajectory parameter draws, so the calibration anchor, P_t and the tolerances of C, D and E measure a reference with missing state.**
- *Location:*
  - `refs.TruthStateModel("z")` (encoder = z only; PROTOCOL 8).
  - Calibration (PROTOCOL 7: every tolerance comes from this reference; the power table's "missing-state" corruption removes a
    coordinate of an already incomplete state).
  - P_t (PROTOCOL 9).
  - PROTOCOL 5.16 itself says the opposite: "every trajectory has its own parameter draw, so a history-based state may legitimately
    carry static coordinates that identify the draw". The k-consistency rule k_true ≤ k ≤ k_true + d_draw exists for that reason.
  - The reference learner's own docstring (effect calibration): "late parts of an effect … are not predictable from the state
    alone".
- *Evidence* (`r3/draw_share.py`, the room's generator, dev tier, one compressible system per type).
  - Setup: z is set to the SAME z* with `latent_set`, and the same moderate kick is applied one sample later, under 8 parameter
    draws.
  - Measure: the share of the readout effect energy over the primary horizon that is NOT determined by (z, event), i.e. the EE of the
    BEST possible z-only predictor (the conditional mean over draws) before any learning error.
  - Results (all 23 compressible types, 3 (z*, unit) combinations each; median 0.076, 90th percentile 0.488):

    | types | share not determined by (z, event) |
    |---|---|
    | 16 latch | **0.631** |
    | 11 r6 | **0.497** |
    | 2 fhn | **0.489** |
    | 13 ring | **0.483** |
    | 10 osc | **0.482** |
    | 12 impl1 | **0.431** |
    | 9 burst | 0.223 |
    | 18 wells4 | 0.169 |
    | 5 onset | 0.153 |
    | 14 ratio10 | 0.121 |
    | 8 pi | 0.103 |
    | the other 12 types | 0.009-0.076 |

    Full list: `r3/draw_share.out`.
- *Consequences.*
  - On the oscillatory / latching types, about half of the effect is unpredictable for the TRUE-STATE reference however well it
    learns. A method that encodes the draw (legitimate by PROTOCOL 5.16) removes it.
  - The draw is identifiable from the history, and partly from the onset microstate: the followers carry filtered histories of z.
    The reference's EE therefore has an irreducible floor of this size. Its EE − EE_full-state gap, and its SMS_x / ICG_y to the
    extent that x at the onset carries the draw, measure the missing draw coordinates rather than sampling noise. tau_SMS, tau_ICG
    and delta_C (percentiles of those) then become lenient for every method. I could not run the full reference pipeline on the
    generator in the room to put a number on this inflation; the irreducible share above is measured.
  - P_t on these types is depressed. That favours "not attainable" and makes P_m − P_t ≥ −0.2 easy.
  - The per-horizon effect shrinkage (beta ≤ 1) turns part of this into a systematic read-in-like error, which SMS's ID arm then
    partly attributes.
- *Fix.*
  - Make the TRUE-STATE encoder [z, θ_eff]: the effective draw parameters from the truth record, which the revised generator is to
    provide for d_draw.
  - Keep the z-only model as a separate, descriptive reference.
  - Base every tolerance, the power table and P_t on the complete-state reference.
  - Re-run `r3/draw_share.py` on the revised generator. The share should be about 0 for [z, θ_eff] on every type; this belongs in
    the generator's test suite.

### MAJORS

**N-new-2. The calibration is "attainable" when D and E never bind, so "causal state supported" can be issued without any mediation or closure test.**
- *Location:* `calibrate.common_percentile` (calibrate.py:496-529); PROTOCOL 7 declares "not attainable" only when a criterion
  that binds AT p = 90 loses power.
- *Evidence* (`r3/calib_logic.py`):
  - With nulls as good as the true state, all 200 synthetic calibrations are **attainable with sms_binds = icg_binds = mev_binds =
    False**.
  - With the round-2 row model, 11 of the 97 attainable calibrations have no binding D/E part.
  - The SUPPORTED category then rests on A, B, C, F, G and H only, yet carries the name "causal state supported" (mediation and
    closure being the benchmark's defining properties).
- *Fix:* declare the calibration NOT ATTAINABLE (synthetic part at most PARTIAL) unless D and at least the MEV or ICG part of E bind
  at p = 90. Alternatively, give the category a distinct name ("predictive state supported; mediation / closure not testable"),
  as was done for E-untestable.

**N-new-3. The k-consistency rule cannot be verified, and it widens the compression criterion without a bound.**
- *Location:* `select.per_system_values` (:218-219); `evaluate_truth` (:161-163).
- The room's generator provides no `d_draw`, so `int(truth_d_draw or 0)` = 0 and the rule reduces to k = k_true (verified by
  reading: no `d_draw` anywhere in `extra/generator`).
- With the revised generator, d_draw is "the number of draw parameters that change the dynamics or the readout above the floor".
  Per 1.1 of the generator that is 5 or more z-level parameters (time constants, frequencies, gains, thresholds, readout gain), so
  any k in [k_true, k_true + 5 or more] would count as "compressed correctly" in selection criterion (4).
- *Fix:* pre-register d_draw per type (from the revised truth) and publish its distribution. Cap the credit, e.g. full credit only
  for k ≤ k_true + d_draw_eff where d_draw_eff comes from the draw coordinates actually needed (the `r3/draw_share` test with
  [z, θ_eff] subsets). Report k − k_true.

**N-new-4. The family jackknife is liberal at ≤ 8 families, and badly liberal below 6, where the unit silently becomes the cell.**
- *Location:* `stats.MIN_FAMILY_UNITS = 6` / `class_balanced_estimate`.
- *Evidence:* see the N2 table; at 5 families P(upper < truth) is 0.175-0.287.
- The main verdict subsets have 12-24 families, but subsets can be small: a true-state-supported subset, a mechanism system, the
  in-family subset, or a system with few feasible families.
- *Fix:*
  - With fewer than 8 families, widen the interval (e.g. use the larger of the family- and cell-jackknife se, with df = number of
    families − 1), or report "too few families" and treat the criterion as untested (missing).
  - Never fall back to cells when the cells are nested in families.
  - Record the family count with every verdict.

### MINORS
- **N-new-5.** Criterion F is gameable by the self-reported range. At Level B, any three k inside the reported range are "stable";
  at Level C, [3, 3, 3, 3, 40] with range (1, 40) is stable (`r3/f_check.py`). Cap the admissible range width (e.g. max − min ≤ 2),
  or judge stability on the k values alone.
- **N-new-6.** Class merging changes the estimand from system to system. `na` → moderate, `hi` → strong and so on depend on how many
  families carry the class, so "class-balanced EE" weights differ across systems. That is acceptable for per-system verdicts, but
  suite means (the primary family's H1, H5) average different statistics. Report the merge pattern per system and state it as a
  limitation.
- **N-new-7.** The paired class-balanced difference (B, C) is conservative on its upper bound (P(upper < truth) 0.005-0.007) but
  covers only 0.85-0.91 (`r3/jk_diff.py`). The lower side is too narrow, so any "significantly worse" use of it is liberal.
- **N-new-8.** Level C at 5 refits: a single failed refit makes F fail (`[3, 3, 3, 3, None]` → not stable). The protocol text
  ("modal k in ≥ 4 of 5") would allow one disagreeing refit. Align the code and the text.
- **N-new-9.** The full-state bound and the ID comparator are chosen PER SYSTEM on the validation suite (`tournament.choose_bounds`,
  the lower EE per system). Confirmation systems are new, so the per-system choice has no counterpart at Level C. The minimum over
  candidates on the same data is also optimistic for the bound. Pre-register one global choice per system kind (the model with the
  lower median EE over the validation systems), applied unchanged at Level C.

## 3. Verdict

**Not ready to freeze.** The statistical machinery is now largely sound, and I verified every fix by re-running:
- the latent-missing handling closes the gaming route (SMS 0.75 stays 0.75);
- the binding flags are fixed at p = 90;
- P_t and the calibration share one item set;
- the active-design union is at 0.017-0.037 under every null I tried, with power 0.88-1.00;
- F needs exactly 3 seeds / 5 refits;
- the tournament evaluates every seed and writes the gate-reference rows;
- the family jackknife-t covers 0.93-0.96 at the usual 12-20 families.

What remains blocks a valid calibration:
- the TRUE-STATE reference, which anchors every tolerance, the power table and P_t, is not a complete causal state under the
  benchmark's own per-trajectory draws: about half of the effect is undetermined on 6 of the 23 compressible types (N-new-1);
- the calibration can be "attainable" with no binding mediation or closure criterion (N-new-2);
- the k-consistency rule and the calibration itself cannot be checked until the revised generator and the calibration outputs
  arrive.

Fix N-new-1 (the reference encoder [z, θ_eff]) and N-new-2 before the calibration is run, then send the outputs for the last check.

## 4. End-to-end decide on the toy tier

The four unit tests of `test_tournament_decide.py` pass in my re-run: fewer than 3 seeds is refused, decide fails loudly without
true-state rows, per-developer method names resolve, and the reference rows are written.

The slow end-to-end test (`test_run_then_decide_end_to_end_on_the_toy_tier`: build a toy tier, fit the references, assemble 3 seeds,
decide) was still running when this review was written. It needs the reference fits, and it ran under the stubbed engine package and
a dummy salt. Its result is therefore **unverified** here, and N1's "fixed" rests on the unit tests and on reading
`assemble_round` / `decide_round`.

That test also uses the references' own results as the same result for every seed. It does not exercise genuinely different fits
per seed, so seed averaging is only checked for plumbing.
