# Review A (nonlinear dynamics / system identification): pre-lock review of brainir_state_v1 and benchmark v2

Scope: is the learned model a state realisation (encoder, closed transition, readout) or does it carry hidden memory; are the
closure tests (family D, closure gap, Markov rollout consistency) meaningful and correctly implemented; is the dimension rule
sound and generic; is G (stability across seeds) measured correctly.

Experiments (scripts and raw output in `.tmp/A/`; public evaluator v2, SYNTH_CFG, synthetic DEV suite, fits on train + val):
- `fits.py`: brainir_state_v1 fitted with seeds 0, 1 and 2 on syn-1f16e42a17, syn-f62c10260a (trap G) and syn-567a33cb55, and
  with seed 0 on syn-154d77eb23. Each fit records k, the R checks, D and G. Four more systems were planned
  (fe868499dd, 0dccdf2720, 44f7fa1051, 94a60083e6), but the background run stopped with the session and **they did not run**.
- `stash.py`: models that carry memory beyond their reported z, run through the evaluator.
- `hist.py`: D micro-gain against the history gain for PCA-k, random-k and brainir.
- `probes.py`: D with the parameter-draw identity added, and latent closure after held-out interventions.
- The calibration's per-system D values (`extra/benchmark/calibration.json`).

True k values come from `calibration.json` (orchestrator side). Method findings go to the developer only as generic requirements.

## Summary verdict

**As a realisation, the method is sound.** Its rollout is a plain recursion on z: a clipped polynomial map, events applied
through z, and the readout g(z, u). `encode` has no side effects, and the Markov rollout inconsistency is exactly 0 on every fit.
The candidate therefore does not carry hidden memory.

**The evaluation of closure is not fit for the claims it supports.**
- The Markov rollout-consistency rule of PROTOCOL section 4 ("a model that carries memory beyond z fails and its k is invalid") is
  not implemented anywhere.
- The only closure condition in the verdict, the D micro-gain, never calls the transition f.
- Under the calibrated tau_D = 0.40, D passes random k-projections on 25 of 45 dev systems. It also passes a model that smuggles
  its full state through a side channel, and models with significant history gain on the non-Markov trap.
- G's headline CCA stays at 0.998 to 0.9999 even when the seeds select different k and their predictions disagree by NMSE 69.

**The method's dimension rule is unstable.** It selected a different k across seeds 0-2 on all three systems where I ran seeds,
and it depends on wall-clock time.

**Recommendation:** do not lock or run Level B confirmation / Level C until B1 and B2 are fixed or the affected claims are
removed from the pre-registration. The method-side items (M1, M2) should be fixed before the lock or declared as limitations.

## BLOCKERS

### B1. No test of the transition's closure or of hidden memory enters any verdict or ranking; the protocol's rule is unimplemented and easy to evade

**Evidence (code).**
- PROTOCOL section 4, row D, says: Markov rollout consistency — "a model that carries memory beyond z fails and its k is
  invalid".
- `evaluate.eval_rollout_checks` (`src/brainir_state/evaluate.py:464-512`) computes `markov_rollout_inconsistency_rel` and
  `closure_gap_*`. No consumer reads them. `harness.verdict` (`harness.py:214-272`) uses only A, C, D and E. The tournament
  profiles (S1-S8), `level_c.py` and `evaluate_synth.abstention_row` do not use them either. A grep for `markov_rollout` finds only
  the producer and one unit test.
- "closed" (`harness.py:251`) is the upper CI of the D micro-gain. D (`evaluate.py:356-460`) regresses y(t+h) on encodings
  phi(x_t) and never calls `rollout`. It certifies that the ENCODER is a sufficient statistic, not that f is closed.
- `nn_seqbottleneck` is a declared baseline (PROTOCOL section 9) and so eligible to be the "strongest baseline" for Level C. Its
  notes say its GRU decoder carries 64-dim state beyond z, and it reports the bottleneck as k. In tournament round 1 it received
  "compact causal state discovered: 2" (`notes/_tournament_feedback.md`).

**Evidence (experiment, `stash.py`, syn-1f16e42a17, true k = 2).** Base = brainir seed 0 (k = 3). Three models report k = 1:
- the honest forced-k = 1 fit;
- "hidden": the rollout carries the other two coordinates internally;
- "stash": `encode` stores the full 3-dim state in the object, and `rollout` uses it when z0 matches.

| model (reported k) | A | C (held out) | D [95 % CI] | closed (≤ 0.40) | Markov inconsistency | closure gap y |
|---|---|---|---|---|---|---|
| brainir k=3 | 0.060 | 0.245 | -0.03 [-0.74, 0.11] | yes | 0 | 0.014 |
| honest k=1 | 0.288 | 0.971 | -0.24 [-0.42, 0.33] | yes | 0 | 0.006 |
| hidden k=1 | 0.291 | 0.248 | -0.24 [-0.42, 0.33] | yes | 0.0020 | 0.018 |
| **stash k=1** | **0.060** | **0.245** | -0.24 [-0.42, 0.33] | **yes** | **0.0020** | 0.164 |

- The stash model gets the k = 3 model's A and C bit for bit while claiming k = 1. It passes "compact" and "closed".
- Its Markov inconsistency is no larger than that of the honest-but-hidden model. The check restarts from `zf[a]`, which does not
  match the stash, so both runs take the same fallback path.
- Only the (unused) closure gap exposes it.

**Why it is a blocker.** The per-system verdict and family F ("the method's selected k") are pre-registered claims. Neither can be
trusted for any model, including the strongest baseline in the Level C primary family. The fact that the locked method happens to
be Markov (inconsistency 0 on all 10 fits) does not repair the metric.

**Fix (evaluation).**
1. Implement the rule. When `markov_rollout_inconsistency_rel` exceeds a numerical tolerance (for example 1e-6, relative), mark k
   invalid, set compact = False and closed = False, and report it in F and L.
2. Run the check on a fresh deserialised copy of the model for every call, or call `encode` and `rollout` on separate copies. This
   removes side channels.
3. Compare y as well as z, and check that `rollout(...)["y"] == readout(z, u)`.
4. Run the check on rollouts WITH events too.
5. Either add a closure-gap condition to "closed" (with a threshold calibrated on the true-latent reference, like the other
   tolerances), or rename the condition to "encoder sufficiency" in the protocol and report.

### B2. The "closed" condition has almost no power at tau_D = 0.40 and ignores history; S3 rewards negative (noise) gains

**Evidence.**
- **Calibration.** Recomputed from `calibration.json`, per_system, over 45 dev systems:

  | reference model | closed (upper CI of D ≤ tau_D) |
  |---|---|
  | true latent | 40 / 45 |
  | **random-projection k** (a random orthonormal projection of x with linear dynamics) | **25 / 45** |
  | PCA-k | 38 / 45 |
  | full state | 44 / 45 |

  The true latent's D itself reaches 0.60 (syn-94a60083e6, perfect integrator) and 0.40 (syn-74c2a90450). Its median CI width is
  0.31. The null distribution is so wide and so positive that the 90th-percentile rule yields a tolerance of 40 % error reduction.
- **History ignored.** The verdict ignores the history gain, the D test that targets non-Markov projections. On trap G
  (syn-f62c10260a, "non-Markov projection trap"), every model I ran is "closed" (`hist.py`):

  | model | micro-gain [CI] | history gain [CI] | closed |
  |---|---|---|---|
  | random k2 | 0.31 [0.23, 0.39] | -0.03 [-0.13, 0.07] | yes |
  | brainir k1 | 0.12 [-0.15, 0.30] | **0.20 [0.07, 0.32]** | yes |

  On the same system, brainir seed 0 selects k = 1 (true 2), and its 1 s rollout NMSE is 10, the cap (`fits.log`). On
  syn-1f16e42a17, PCA-k2 and random-k2 have history gains of 0.38 [0.11, 0.44] and 0.44 [0.20, 0.49] with CIs excluding 0, and
  are still "closed".
- **S3 rewards noise.** S3 ranks the median D micro-gain, "lower is better". Negative D is not "more closed": it means the
  capacity-matched fit got worse when the residual was added, which is regression noise that grows as the residual shrinks.
  - The developer's own dev data (notes/brainir_state_v1.md section 7.1 and section 9) show that a larger k gives more negative D,
    so S3 rewards larger k, against compactness.
  - Round-2 S3 spans only -0.083 to -0.003 across all candidates, all within noise.
- **Parameter identity (checked, inconclusive).** I tested whether the positive D of true latents comes from parameter
  heterogeneity across held-out draws: adding the draw identity to both fits (`probes.py`). The results were mixed:
  - syn-f62c: D moved from 0.12 to 0.03;
  - syn-1f16: from -0.03 to 0.10;
  - syn-567a: from -0.31 to -0.20.

  I therefore do not claim a cause for the wide null.

**Why it is a blocker.** "Closed" is one of the three core conditions of "compact causal state discovered". As calibrated, it
cannot separate a random k-dimensional projection from the true state on more than half the calibration systems. It cannot see a
significant history gain on the trap built to test it. The pre-registered claim "approximately closed (Markov)" (contract
section 1) is therefore not supported by the condition that grants it.

**Fix (evaluation).** Redefine closure before any held-out use, and recalibrate:
1. Add a history-gain condition (upper CI ≤ its own calibrated tolerance) and a closure-gap condition (B1).
2. Report a power check with the calibration: the pass rate of random-k and of PCA-(k-1) must be low for any tau adopted.
3. Replace S3 by max(0, upper CI of D), or a similar non-negative score, so that noise is not rewarded.
4. If the wide true-latent null cannot be narrowed (more points per trajectory, a within-draw design), state in the protocol that
   "closed" means "no large microstate gain".

## MAJOR issues

### M1 (method). The dimension rule is noise-driven and not stable across seeds

**Evidence.**
- `_nn_select` (`brainir_state_v1.py:63-81`) uses a per-candidate tolerance tol_k = max(0.1 e*, 0.005, SE_k), where SE_k is the SE
  of that candidate's own paired difference. A noisier k gets a wider tolerance.
- On syn-1f16e42a17 seed 0:
  - k = 2 (mean 0.1373, SE 0.014) is rejected;
  - k = 3 (mean 0.1364, SE 0.026) is accepted;
  - selected k = 3, true k = 2.
- At each k, the error is the minimum over up to 27 configurations (delays × degree × threshold) evaluated on the same
  validation units that compare k (`score`, lines 207-219). The number of configurations shrinks with k (the `max_terms` cap), so
  the optimism bias differs between k values.
- Across seeds 0 / 1 / 2 (seeds change only the fold split, bags and subsampling), k differed on every system tested:

  | system | true k | k (seeds 0 / 1 / 2) |
  |---|---|---|
  | syn-1f16e42a17 | 2 | 3 / 2 / 2 |
  | syn-f62c10260a | 2 | 1 / 2 / 1 |
  | syn-567a33cb55 | 2 | 1 / 2 / 2 |
  | syn-154d77eb23 (seed 0 only) | 2 | 4 |

- The developer's own dev comparison (section 7.1) shows that the nn and ks rules disagree on 19 of 48 systems, by up to 1 vs 5
  and 8 vs 2.

**Requirement (generic, for the developer).**
- The dimension decision must use a tolerance that does not grow with the candidate's own variance. Examples: a one-SE rule
  with the SE taken at the best k, or a paired test of each smaller k against the best.
- Configurations must be selected on data disjoint from the units used to compare k (nested folds).
- The rule should be shown stable under the fit seed. For example, report the k distribution over 5 seeds on dev systems before
  the lock.

### M2 (method). The k sweep depends on wall-clock time

**Evidence.**
- `brainir_state_v1.py:222-243` stops the sweep when elapsed + 1.2 × (slowest k) > 600 s × sqrt(number of systems).
- The notes report real full-system fits of 362-416 s on a lightly loaded machine, and 10× slowdowns under load.
- `level_c.py` runs the 5 seed fits of the locked method in parallel (`run_fits(..., parallel=...)`).
- The selected k, and hence F, G and "compact", can therefore change with machine load. This violates the contract's
  "deterministic given its seed" and the "generic rule" requirement.

**Requirement.**
- Replace the wall-clock guard with a deterministic budget, such as a count of configurations or a fixed grid.
- Alternatively, show that the guard never binds in the locked environment, and treat `sweep_status == "time"` as a failed fit.

### M3 (evaluation). G's headline statistic is inflated and does not measure data stability

**Evidence.**
- `cca_fit_apply` (`evaluate_cross.py:172-187`) averages only min(k_a, k_b) canonical correlations. When the seeds' k differ,
  the smaller latent is always found inside the larger one. Results (`fits.log`):

  | system | k (seeds) | cca_mean | r2_min_mean | prediction disagreement NMSE |
  |---|---|---|---|---|
  | syn-1f16 | 3, 2, 2 | 0.9997 | 0.64 | 0.024 |
  | syn-f62c | 1, 2, 1 | **0.9999** | 0.70 | **69** |
  | syn-567a | 1, 2, 2 | 0.998 | 0.67 | 0.44 |

  Near-perfect CCA coexists with seeds whose predictions disagree by NMSE 69.
- Seeds of this method change only fold assignment and bagging, not the data. G therefore measures optimiser/split stability and
  is not comparable across method classes (least-squares vs SGD). METHODS_REVIEW II.5 (6) asks for stability across "seeds,
  bags and estimators".

**Fix.**
- Report `r2_min_mean` and k agreement as the primary G statistics, and pad CCA with zeros up to max(k).
- Add a data-resampling arm, for example fits on bootstrap or half-samples of the training trajectories, at least for the locked
  method at Level C.

### M4 (evaluation). S6 / K dimension recovery rewards wide ranges

**Evidence.**
- `evaluate_synth.dimension_recovery` (`extra/orchestrator/brainir_state/evaluate_synth.py:70-77`) counts "in range" for any
  reported `k_range`, with no penalty on width. A method reporting [1, 16] always scores S6 = 1.
- brainir's ranges are derived from 2 × tol, which is noise-inflated (M1). For example, [2, 4] on syn-1f16 and [1, 2] on
  syn-567a seed 2 contain the truth while the point k is wrong.

**Fix.**
- Score the exact rate and the range separately.
- Weight range hits by 1 / width, or cap the width (for example width ≤ 1).

### M5 (evaluation). No closure check under interventions

**Evidence.**
- The closure gap and the Markov check run only on event-free trajectories (`harness.py:176-177`).
- For a latent model, the event operator must commute with the encoder: the latent predicted after an event should equal the
  re-encoding of the intervened microstate history.
- `probes.py`, held-out interventions, latent at 0.25 s after the first event. Sums over 8 pairs of the squared distance between
  the model's latent and the re-encoded true latent:

  | system | model rollout with events | "no effect" | twin (no events) |
  |---|---|---|---|
  | syn-1f16 | 7.2 | 20.5 | 0.50 |
  | syn-154d | 40.7 | 66.9 | 3.5 |
  | syn-f62c | 246.9 | 246.9 | 44.9 |
  | syn-567a | 0.74 | 0.73 | 0.06 |

- On syn-f62c the predicted latent shift is 7e-12: the calibrated gains removed every effect, while the true shift is 183.
- For this method in particular, the encoder uses x delays of up to 10 % of T (0.4 s here), but events are applied only through
  the current-sample block C_0 (`ks_core.py:516`, `_apply_dq` with `Ck0`). The delayed copies of an intervention never enter z.
  z after an event is therefore not the encoder's own state of the intervened history.

**Fix (evaluation).** Report an interventional closure gap: ||z_model(t_e + a) - phi(x^int_{<= t_e + a})|| relative to the twin.
Consider using it in C's interpretation.

**Requirement (method).** Event operators must be consistent with the encoder's memory: apply the event to the delay block as it
ages, or state that z after an event is off the encoder's manifold.

## Minor issues

- **D residual leakage** (`evaluate.py:423-427`). The residual R for a training-fold row is computed by a regressor fitted on the
  other fold, which is the evaluation fold in `crossfit`. The leak is x/z information only, not y, so its effect is small. Compute
  R inside each training fold instead.
- **Relative gaps are not scale-invariant** (`evaluate.py:507-511`). `closure_gap_z_rel` and `markov_rollout_inconsistency_rel`
  divide by the summed variance of z, so rescaling one coordinate dilutes the others. Whiten with the training covariance, as E
  does.
- **SYNTH_CFG does not set `closure_start_s`.** It inherits the real 0.25 s. This is harmless for synthetic lam of 20-50/s but
  should be explicit.
- **Non-finite states zeroed (method).** `KSModel._rollout_grid` (`ks_core.py:530-531`) replaces non-finite z by 0 and continues.
  The latent box clip usually prevents this, but a failure is then scored as a finite prediction. Return NaN, and let the
  evaluator's cap apply.
- **Coarse-grid input sampling (method, real data).** On the coarse model grid (real data, s = 5), inputs are point-sampled every
  5 ms, and a final partial coarse step is integrated as a full step. Harmless for the protocol's pulse widths of 10 ms or more;
  worth a note.
- **Abstention is not reflected in the verdict.** `nn_seqbottleneck` sets `causal_equivalence_failed = True` but still receives
  verdicts. The verdict should read that flag, or at least report "compact causal state" as void when a model declares itself
  non-closed.

## What I checked and found sound

- **brainir rollout is a state recursion.** z_{t+1} = clip(z + Theta(z, u) W + w0), with events as functions of (z, event) and y =
  g(z, u). `encode` has no side effects. The Markov rollout inconsistency is 0.0 on all 10 fits. The closure gap is small where
  the model predicts well: y NMSE 0.014 against a 1 s rollout error of 0.06 on syn-1f16.
- **The encoder is causal.** Edge-padded past delays only; y is used only as a regression target; decimated histories end at the
  current sample.
- **`eval_rollout_checks` index alignment.** The windows `[a+1:]` vs `[1:]` and the restart input `u[a:]` are correct. The
  interpolated rollout on the real coarse grid restarts exactly because a = 50 ms is a multiple of the 5 ms step.
- **`eval_closure` design.** Cross-fitting by trajectory, capacity matching between the with- and without-residual random-feature
  sets, the public readout scale, the future-input features and the trajectory-cluster bootstrap are implemented as documented.
  The problems are power and scope (B2), not arithmetic.
- **G alignment protocol.** Alignment is fitted on public validation data and measured on held-out non-intervention trajectories.
  `cross_r2` takes the minimum over the two directions, which does expose differences in k.
- **The dimension rule uses only training/validation data.** It uses no truth and is stated in the notes. The problems are its
  statistics (M1) and its timing (M2), not leakage.
