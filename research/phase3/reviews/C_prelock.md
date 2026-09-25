# Review C (representation learning): brainir_state_v1 and its evaluation, pre-lock

Reviewer C. Scope: whether the latent can be observationally predictive but mechanistically wrong; baseline strength and tuning;
capacity control; whether the selection rule holds up when many candidates are compared. Scripts I ran are in
`.tmp/review_c/work/` (`rk.py`, `s6.py`, `s6b.py`, `truth.py`, `carrier.py`, `carrier2.py`, `kicklag.py`). For ground truth on the
DEV suite I used `extra/benchmark/calibration.json` (per-system true k) and the generator in `extra/generator` with the public dev
seed 20260924 (neuron roles and the synaptic readout D). Neither is visible to the developers.

## Summary verdict

**Not ready to lock as is.** One blocker in the evaluation. The selection metric S6 and the K "dimension recovery" metric give
credit for any reported range that contains the true k, and a wider range never costs anything. The method's own dimension
component was adopted partly because of this credit.

The method's latent is observationally good (A, B and E are competitive on dev). Its intervention path, however, is not causal:
- The kick, current and silencing operators map a microscopic perturbation through the encoder's observational weights.
- On dev systems with non-causal "carrier" neurons, those neurons get the same weight as causal ones.
- The per-kind gain calibration then often sets the kick or current gain to 0. The model then predicts "no effect".

Neither problem invalidates the Level C tests formally. Two things do weaken what those tests can show:
- The baselines were never evaluated on the public data by their developers.
- The primary family can be passed by two models that both predict no effect.

Selection among the round-2 finalists is fragile. If any one of several components is dropped, a different candidate wins. The
hybrid's likely round-3 win depends on S6, S7 and S8, not on S1-S5.

## BLOCKERS

### B1. S6 and K dimension recovery reward wide k ranges and cost nothing for width (evaluation → orchestrator)

**Where.**
- `extra/orchestrator/brainir_state/evaluate_synth.py::dimension_recovery`: `in_range = k_range[0] <= k_true <= k_range[1]`, and
  `in_range or exact` is what counts.
- `evaluate_cross.system_values` → `S6_dim_ok`.
- PROTOCOL section 4 K ("k = k_true, or k_true in the reported range") and section 9 S6.

**Evidence.**
- The metric increases monotonically with the width of the range the method reports. A method that reports `[1, k_max]`
  everywhere scores S6 = 1. Neither the range width nor its coverage is scored anywhere.
- brainir_state_v1's final dev fits (`runs/brainir/res/fitonly*.jsonl`) against the calibration truth (45 compressible dev
  systems; `s6b.py`):
  - exact k: **23 / 45 (0.51)**;
  - "in range": **36 / 45 (0.80)**. 13 of the 36 hits come only from the range. Examples:
    - syn-44f7fa1051: true 1, k = 5, range [1, 5];
    - syn-fe868499dd: true 2, k = 8, range [2, 8];
    - syn-74c2a90450: true 1, k = 3, range [1, 5].
  - The method's k is ABOVE the true k on 19 of 45 dev systems (point estimates; `s6.py`).
- The method adopted the nn range rule ([first k within 2 tol, first k within tol / 2], tol = max(0.1 e*, 0.005, SE)) because of
  the nn family's held-out S6 (notes/brainir_state_v1.md section 0, table row "plateau tolerance"). Its notes also say
  ks_sindy's "range-width unresolved" flag was dropped "because the nn ranges are wider by design" (section 4). The dev ranges
  are wider than under ks_sindy's rule: mean width 1.21 vs 1.04 on the dimexp sweep.
- S6 decides the selection. I recomputed round-2 mean ranks from the feedback table (`rk.py`). Adding a hybrid with ks_sindy's
  S1-S5, S7 = 0.97 and S8 = 0.5 gives:
  - S6 = 0.65: the hybrid is 2nd;
  - S6 = 0.70: the hybrid is 1st (3.75 vs lin_subspace 3.88).

  A 0.05 change in S6 (about 2 systems of 46) flips rank 1. That change can come from range width alone.

**Fix.**
- Before round 3, score S6 (and K dimension recovery) on the point k (exact-k rate). Alternatively, give range credit weighted
  by 1 / (width + 1).
- Report the range width distribution and empirical coverage per candidate.
- Keep "true k in range" only as a descriptive quantity.
- Because this changes a pre-registered component, it is a benchmark version change: log it as such, apply it to every candidate
  of the round, and recompute rounds 1-2 under the new S6 for the record.
- Generic requirement for the method developer: the reported k range must come from a rule whose width is justified by
  validation uncertainty. It should not be widened for scoring.

## MAJOR issues

### M1. Intervention operators treat observational encoder weight as causal influence; on carrier neurons they are wrong by construction (method → developer, as a generic requirement)

**Where.** `ks_core.KSModel._rollout_grid` and `ks_sindy.SindyModel._apply_dq`. A kick moves z by `g_kick (dx / sd) @ Ck0`, where
`Ck0` is the current-sample block of the predictive-basis encoder, a ridge regression of the future on x. Currents and silencing
go through a linear microscopic coupling estimate and the same `Ck0`. One scalar gain per event kind is picked from
{0, 0.25, 0.5, 1}.

**Evidence** (`carrier.py`; truth rebuilt from the generator):

| system | true k | v1 k | encoder shift per unit kick, causal neurons (D ≠ 0) | carriers (D = 0) | nuisance (D = 0) | corr(model shift, true causal weight) | calibrated gains kick / current / silence |
|---|---|---|---|---|---|---|---|
| syn-de38f805b3 (wta) | 3 | 3 | 0.199 | 0.176 | - | 0.13 | 0 / 0.5 / 0 |
| syn-c2a119aa19 (groupA_impl3) | 2 | 6 | 0.097 | **0.103** | 0.036 | 0.12 | 0 / 0 / 0.5 |

Shifts are the median norm of the model's latent shift per unit kick, in units of sd(z).

- The generator's truth is that carriers "look exactly like latent neurons but are not causal" (SYNTHETIC_BENCHMARK.md section 6).
  Held-out targets are 40 % of neurons stratified by role (PROTOCOL 3.2), so carriers and nuisance neurons are among them.
- The model's kick map cannot tell carriers from causal neurons. Calibration handles this by turning the operator off:
  - on wta, every held-out pair except current_group has effect error exactly 1.00 ("no effect"; `carrier2.py`);
  - across the 48 dev systems, the kick gain is 0 on 13 (`dimexp.jsonl`);
  - on real systems, kick and current gains are 0 on 5 of 8 fitted systems (`real.jsonl`).
- This is the case the review question asks about: a well-predicting latent (k exact on wta, E 0.002-scale on dev) whose causal
  map is wrong. Only C can see it. K (M3) and E cannot.

**Fix (method, generic).**
- Estimate the event read-in from intervention data (training events, and the budgeted simulation service within its policy)
  rather than from observational encoder weights. For example, regress the latent effect on the perturbed units, as the lin
  family's read-in map R does.
- Report the per-kind gain and the fraction of event kinds switched off, per system, in `info()`.
- Treat a zero gain as an abstention on that intervention kind ("observational state only; causal equivalence failed"). It should
  not be scored silently as a claimed "no effect".

### M2. Declared baselines were not evaluated or tuned on the public data, and "strongest baseline" is chosen on components that the Level C tests do not use (evaluation → orchestrator)

**Evidence.**
- lin_pcadyn, lin_dmdc and lin_falds: "full suite NOT RUN (2-system smoke checks)" (notes/lin_methods.md section 5.2).
- lin_falds uses "2 EM iterations inside the CV sweep and 8 for the final fit" (section 2).
- nn_aelin, nn_rssm and nn_seqbottleneck: "Dev-suite and real evaluation: not run (implemented and unit-tested only)"
  (notes/nn_baselines.md).
- Every baseline author also developed competing candidates in the same family.
- By contrast, the candidate received about 5 h of dev evaluation and ablation, plus two rounds of held-out feedback (its notes,
  7.6 and 0).
- The strongest baseline is "the best-ranked eligible baseline of the last round" by mean rank over S1-S8 (PROTOCOL section 9).
  On round 2 this is lin_falds, which has the worst S1 of all seven finalists (1.16). Its rank comes from S2, S4 and S7. The
  Level C family tests A, C, D, E and K; S7 (abstention) and S8 (sharing) are not among them.
- Which baseline counts as "strongest" also depends on non-baselines in the round, because mean rank depends on the other
  candidates: removing lin_subspace or lin_falds from the round-2 set makes lin_dmdc the strongest baseline (`rk.py`).

**Fix.**
- Before Level C, give each declared baseline a recorded dev-suite tuning pass with a budget comparable to the candidate's
  (e.g. lin_falds EM iterations to convergence; nn baselines run on dev at least once), done by someone without a competing
  candidate.
- Choose the Level C comparator by rank over the components that the primary family actually tests (S1-S5), among baselines
  only.
- Report the comparison against each declared baseline descriptively.

### M3. K (S5, and the 13th primary Level C test) measures observational decodability, not mechanism, and is saturated (evaluation → orchestrator)

**Evidence.**
- The true latent is a linear population signal c = D (v - b) of the activations (SYNTHETIC_BENCHMARK.md section 2), and every
  candidate's encoder reads x.
- `r2_true_from_model_rff` is the scored direction. It is satisfied by any z that spans the latent, including:
  - over-complete z (v1's k exceeds the true k on 19 / 45 dev systems);
  - carrier-based z (M1).
- The reverse direction (`r2_model_from_true`, "extra content") is reported only.
- Median S5 over all 19 round-1 candidates lies in [0.984, 0.998], and in [0.991, 0.997] in round 2.
- The primary K test's non-inferiority margin is 0.05. It therefore cannot fail for any of these methods and gives Holm no
  information.
- In the selection, S5 differences in the third decimal get a full 1/8 of the rank weight. Rounding S5 to two decimals reorders
  places 2-6 of round 2 (`rk.py`).

**Fix.**
- Score K in both directions, e.g. min(R² true←z, R² z←true), or penalise extra content.
- Add an interventional K, for instance the alignment of the model's per-neuron event read-in with the true D columns (truth
  is available at Level B).
- Remove S5 from the rank, or rank it on a pre-registered resolution.
- In the primary family, replace K with a test that can fail.

### M4. The primary C non-inferiority test can be passed by two models that both predict no effect (evaluation → orchestrator)

**Evidence.**
- The margin is max(0.05, 0.2 × baseline C) (PROTOCOL section 8; `level_c.py::_margin`).
- On real circuits both v1 and the lin family calibrate kick and current gains to 0 ("calibrated scales go to 0, C ~ 1",
  notes/lin_methods.md section 6; v1: `real.jsonl`, net1:full kick 0 / current 0). With C ≈ 1 for both, the difference is
  about 0 and non-inferiority passes.
- The claim "the locked method is non-inferior to the strongest baseline on interventions" would then hold for a method with no
  interventional content.

**Fix.**
- Report each C test together with the method's own C upper CI against the no-effect value 1.
- Pre-register that a non-inferiority pass on C is described as "interventional" only if that upper CI is below 1.

### M5. Selection is fragile and was adapted to the held-out profiles; the bootstrap has no decision rule (evaluation → orchestrator)

**Evidence** (`rk.py`, round-2 feedback table; my recomputed means match the published ones to within rounding: 3.31, 3.75,
3.88, 3.94, ...):
- Dropping one component changes rank 1:
  - without S1 or without S3, lin_falds wins instead of lin_subspace;
  - without S7, the gap widens to 2.79 vs 3.71.
- S8 is 0.5 for 6 of 7 finalists: "reject every request" earns exactly the balanced accuracy of chance.
  - v1's S8 gain over ks_sindy (0.167 → 0.5) comes from an internal test that rejected every dev set, including both candidate
    implementation groups (notes 7.4).
  - The internal test compares shared and independent laws on the same training trajectories both were fitted on (in-sample;
    `_sharing_test`).
- The hybrid was composed after reading the round-1 and round-2 aggregate profiles. Each added component targets a component
  measured on the same held-out systems (notes section 0: S6, S7, S8). Round 3 then scores it on those systems.
  - The protocol calls held-out values selection-biased (section 9), but the *selection itself* still uses them.
  - The hybrid's projected rank-1 depends on S6, S7 and S8 alone, with S1-S5 unchanged from ks_sindy (B1).
- `selection_bootstrap` reports P(rank 1). No pre-registered rule uses it, e.g. "if P(rank 1) < 0.5, lock the simpler
  candidate or a baseline".

**Fix.**
- Pre-register, before round 3, a decision rule on the bootstrap: a minimum P(rank 1), or a tie region that is resolved by
  parsimony.
- Report the round-3 ranking with and without S6-S8.
- Disclose in the report that components were chosen from held-out profiles.
- The FINAL suite and Level C remain the only unbiased evidence, as the protocol already says.

## Minor issues

1. **Kick read-in uses only the lag-0 block of a delay encoder** (method).
   - `Ck0 = basis["C"][:N, :k]` is used while the encoder also reads x at lags up to 10 % of T. On dev, lags are selected on
     24 / 48 systems, 19 of them with kick gain 1.
   - On syn-f365aa5a73 (lags 4, 10), after the lag window the model's kick effect in z is 0.55-0.7 × the effect obtained by
     re-encoding the kicked trajectory against its twin (cos 0.86-1.0; `kicklag.py`). The model's post-kick z is therefore not
     phi(x) of the kicked system.
   - The lin family met the same issue and used the sum of the lag blocks (notes/lin_methods.md section 1: kick C 7.6 → 1.2).
     This is small here but untested elsewhere.
2. **The model class changes with k inside the dimension sweep** (method).
   - With the 60-term cap (n_u = 1), degree 3 is allowed only for k ≤ 4 and degree 2 only for k ≤ 6. For k ≥ 8 the law is
     linear.
   - The number of configurations minimised over on the same validation units falls from 27 to 18 to 9. The k curve therefore
     mixes dimension, law class and optimistic min-over-configurations bias. This may contribute to k > k_true on 19 / 45 dev
     systems.
   - Fix: a fixed library per k, or report the curve at a common law class.
3. **Parameter counts are self-reported, with different definitions per family**, and the sharing rule compares totals
   (`evaluate_cross.n_params`, `sharing_comparison`).
   - v1's shared fit uses no delays, so its encoder count drops for reasons unrelated to sharing the law.
   - The rank tie-break uses "transition parameters", which are counted differently per family (active polynomial terms + k vs
     A, B, c vs MLP weights).
   - Fix: compare transition parameters under a common counting rule, and audit the counts from the pickled model.
4. **The dimension-cheating guard is descriptive only.** The noise curve (`eval_rollout_checks`) has no threshold and does not
   enter the verdicts or S1-S8, so "compact" is k ≤ N / 5 with no check against a nonlinear encoder packing information into
   few coordinates.
   - Low risk for v1 (linear encoder, clipped degree ≤ 3 law); relevant for the nn candidates.
   - Fix: a pre-registered bound, e.g. the A degradation at sigma = 0.05 must stay within tau_A.
5. **The PCA-k and random-k references are not capacity-matched.** They get the method's k but no delays and a linear law, while
   v1 has up to 4 delays and a degree-3 law. "A below pca_k" therefore partly reflects capacity. Report PCA-k with the method's
   delay set as well.
6. The internal sharing test is in-sample and one-sided at 95 % per system with no multiplicity control. It cannot support
   groups in practice (0 / 2 dev groups). If kept, it should run on held-out folds.
7. syn-c37b6a1b4d (hidden_exogenous per the generator) is an input-floor abstention. It is outside the calibration's closed list,
   so the notes' label "probable FALSE ALARM" should be re-examined against the L definition (non-compressible only).

## What I checked and found sound

- **Causality and the y firewall in the encoder**: lag features are edge-padded and causal (`ks_core.lag_features`); y is only a
  regression target of the predictive basis and never an encoder input; `encode` uses only `x_hist[-need:]`.
- **Markov rollout**: `_rollout_grid` carries only z. Events act through decoded x̂(z), and nothing else is carried, so the
  evaluator's Markov-consistency check applies.
- **Determinism**: the notes report identical k in a second process (`final_check.jsonl`). My fits of syn-de38 and syn-c2a1
  reproduced the k values recorded in `fitonly.jsonl` (3 and 6).
- **Ranking implementation**: `rank_profiles` uses average ranks, handles non-finite values, drops all-NaN components and is
  order-independent. I reproduced the published round-2 mean ranks within rounding.
- **Fixed-list imputation**: failures and non-finite values are imputed as worst values over the fixed list (`system_values`);
  untestable E is left out of S4 and counted.
- **E whitening**: the full training covariance of z makes E invariant to invertible linear maps. Capacity in D is matched
  between the with- and without-residual fits.
- **Dev-only tuning**: hyper-parameters come from ks_sindy / nn_fit, and the dev experiment choices are documented. The one
  post-hoc alternative (consensus k) was rejected in the notes.
