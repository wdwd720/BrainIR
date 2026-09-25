# Review H (numerical methods): integration, timing and solver artefacts. Early round, evaluation machinery

Scope: the recording conventions of PROTOCOL.md and both simulators, restart equivalence of the microstate pools, the generator's
integration, normalisation, numerical floors and near-zero denominators, and off-by-one alignment between encoders, rollouts and
targets. I did not review the candidate methods. Scripts and outputs are in `.tmp/H/` (the file named with each finding). Every
number below comes from the public data (`data/`), from the generator under the public DEV seed, or from `extra/benchmark/`.

## Summary verdict

The timing machinery is in good shape. The recording conventions (the sample at an event time is the pre-event state; u_t is the
input on [t, t+dt)) agree between `realsim.py`, `p3synth/core.py`, `evaluate.py`, `refmodels.py` and the lifting code. The synthetic
test/twin pairs are bit-identical up to and including the event sample. Synthetic pool restarts reproduce the continued trajectory to
1e-14. The stored DEV pools regenerate bit-for-bit from `build_synthetic_suites.py`. I found no off-by-one in A, B, C, D, R or K
indexing.

The problems are in the metrics' numerics:

- The E metric (a verdict condition, S4, and a primary Level C comparison) standardises each latent coordinate by its own spread.
  It therefore changes under invertible reparametrisations of a correct state, and it amplifies coordinates with near-zero variance.
  With the TRUE latent, both effects flip the tau_E verdict on a large share of the calibration systems. That is a blocker.
- Several majors change what C, D and the shortcut controls actually measure:
  - kicks whose effect is set by a clip constant;
  - a readout-history control handicapped by its horizon grid;
  - dilution of D by near-constant readout dims;
  - C on real systems carried by 3 pairs;
  - an un-screened diverged training trajectory that sets a normaliser;
  - tolerances transferred from the synthetic design to the real one, whose E and D windows and dt differ.

## BLOCKERS

### B1. E (microstate equivalence) changes under reparametrisation of the latent and blows up near-constant latent coordinates

Location: `src/brainir_state/evaluate.py:480-486` (`dist`: `As = (A - A.mean(0)) / (A.std(0) + 1e-9)`, Euclidean distance). The
verdict is at `harness.py:193-195` (`E <= tau_E`, tau_E = 0.0039).

Latent pairs are matched by Euclidean distance after dividing each coordinate by its own pool standard deviation. Two consequences
follow:

- The matching depends on the arbitrary coordinate system of z. A state z and an equally valid state A·z (A invertible) are matched
  differently.
- A coordinate that carries almost no variance (a dead or nuisance unit, which is common in learned encoders) is rescaled to unit
  variance. It then dominates the distance with noise. The `1e-9` guard only protects against exact zeros.

Evidence (`.tmp/H/e_analysis.py`, `.tmp/H/e_reparam.py`):

- Setup: I regenerated the DEV pools with the orchestrator's code (all 6144 restarts identical to `data/synthetic_dev/micro_futures.npz`,
  max difference 0.0). I then recomputed the TRUE-latent E ratio with `eval_microstate`, and it matches `calibration.json` exactly on
  all 45 calibration systems (max relative difference 0.0).
- Tiny extra coordinate: I appended ONE coordinate of Gaussian noise with sd 1e-6 × sd(z) to the true latent. The median E over the
  48 systems rose from 5.9e-4 to 1.1e-2. 31 systems that pass tau_E with the true latent fail with the extra coordinate. Examples:
  - linear_k1: 3.0e-5 → 4.6e-3;
  - hopf: 8.2e-4 → 1.5e-2;
  - perfect_2d: 2.3e-3 → 1.9e-2.
- Invertible reparametrisation: I replaced z by A·z, with A = rotation × diag(geomspace(1, 0.1)) × rotation (condition number 10).
  E rose by a median factor of 4.7 (max 8.3) over the 29 calibration systems with k ≥ 2. The pass/fail verdict flipped on 14 of 29
  systems. Examples:
  - hopf: 8.2e-4 → 5.8e-3;
  - duffing: 4.9e-4 → 3.5e-3;
  - damped: 1.0e-3 → 5.6e-3.

So a method that has recovered exactly the true state can fail "microstate-equivalent" for reasons unrelated to microstate
equivalence. The same per-dimension standardisation is used by the output-matched control. On real data that control is also
affected, because several readout dims are constant to about 1e-7 in normalised units (see M3). tau_E itself was calibrated on the
true latent's own coordinates, which a learned model does not share.

The standardisation is also a normaliser computed on hidden test data (the pool). PROTOCOL.md section 4 requires normalisers from
public training data only.

Fix:

- Use a distance that does not depend on the coordinates, for example a Mahalanobis distance. Whiten with the FULL covariance of
  the model's z, estimated on PUBLIC training encodings (not the pool), with an eigenvalue floor relative to the largest eigenvalue
  (for example 1e-4·λ_max). Full-covariance whitening is unchanged by invertible linear maps, and the floor removes dead
  directions.
- Alternatively, match in the model's own predicted-future space (the readout rollout from z under the common input).
- Apply the same fix to the output-matched and PCA-matched controls.
- Re-run the tau_E calibration with the corrected distance. This is a change to a frozen metric, so it needs a benchmark version
  bump before the method lock.

## MAJOR issues

### M1. Synthetic kicks on saturating neurons: the true effect is set by the clip constant eps = 1e-6

Location: `extra/generator/p3synth/core.py:335-340` (kick: `x_now[j] += d; v = phi.inv(phi.clip(x_now))`) and `core.py:63-76`
(`inv` / `clip`, eps = 1e-6).

When x_j + delta leaves the open range of a tanh or logistic neuron, x is clipped to s·(1 - 1e-6). It is then inverted to
v = s·arctanh(1 - 1e-6) ≈ 7.25 s. The activation jump, and through D the latent jump, is therefore governed by eps, not by the
kick. With eps = 1e-3 the same jump would be about 3.8 s.

Evidence (`.tmp/H/kick_clip.py`, `.tmp/H/kick_clip2.py`, DEV suite):

- 189 of 1093 kicked neurons leave the range.
- The activation jumps by up to 26 × the neuron's scale.
- The induced latent jump |Δc| is comparable to sd(z) over the whole trajectory (for example hopf kick_group: |Δc| = 1.15 vs sd(z) =
  0.75).
- Affected trajectories, i.e. those containing a kick whose latent jump changes between eps = 1e-6 and 1e-3:
  - 35/96 test kick_group;
  - 12/48 kick_newtarget;
  - 35/192 train kick;
  - 10/48 val kick.
- That is 47 of the 432 held-out intervention pairs (11 %). For those kicks the latent jump is a median 2.2× (max 4.7×) larger with
  eps = 1e-6 than with 1e-3.

C on synthetic held-out kicks, and the kick training data, therefore partly measure a numerical constant.

Fix: either define kicks so the result is independent of eps, or keep kicks inside the range. Options:
- apply delta in v-space (a kick of delta·phi'(v) in activation);
- clip x to a physically chosen ceiling and set v to the corresponding finite value;
- have the Planner reject or shrink kicks that leave the range.

Add a generator test that the kick effect is invariant to eps.

### M2. The readout-history shortcut control is handicapped by its horizon grid, which weakens the "predictive" verdict

Location: `src/brainir_state/refmodels.py:187-240`. Ridge models exist only at the horizons 1, 10, 50, 100, 250, 500, 1000 and 2000
ms. `rollout` predicts step j with the model of the NEAREST trained horizon (line 238). The verdict requires A to be below both
shortcut controls with a paired CI (`harness.py:176-183`).

Evidence (`.tmp/H/horizon_grid.py`, `.tmp/H/horizon_window.py`, real public train → val non-intervention trajectories):

- Per-step NMSE of the readout-history control, nearest-horizon model vs a model trained at exactly j:
  - net2:full, j = 75 ms: 0.609 vs 0.063;
  - net2:full, j = 30 ms: 0.590 vs 0.121;
  - net1:full, j = 75 ms: 0.172 vs 0.047.
- On the primary A window (250 ms), the control as implemented has NMSE 0.099 / 0.394 / 0.043 on net1 / net2 / net3. A version
  trained at every step 1-250 has 0.055 / 0.154 / 0.025, which is 1.8×, 2.6× and 1.7× better.

The input-only control is unaffected (its per-horizon errors barely differ). The synthetic configuration (dt = 10 ms, grid in
steps {1, 5, 10, 25, 50, 100, 200}, primary window 100 steps) has the same structure.

Fix:
- fit a ridge model at every step up to the longest horizon (cheap: 250 fits of about 30 k × 150 on real data);
- or interpolate between trained horizons;
- or use a single model with the horizon as an input.

Re-run the reference precompute.

### M3. D (closure) is diluted by near-constant readout dimensions that are standardised by their TEST spread

Location: `src/brainir_state/evaluate.py:340` (`Ys = (Y - Y.mean(0)) / (Y.std(0) + 1e-9)` on the test points) and `:321-326` (gain
from the mean error over all columns).

Evidence (`.tmp/H/dstd.py`, `.tmp/H/d_dilution.py`):

- On real public val nominal-type trajectories, at D's sample points (t ≥ 0.27 s, t + 100 ms), several readout dims have sd of about
  1e-7 in normalised units:
  - net1:full dims 1, 3, 7: 6.8e-8, 8.8e-8, 2.2e-7;
  - net3:full dim 0: 9.5e-8;
  - net2:full: 5 dims below 1e-3.
- These are constant up to float32 / solver resolution. Standardisation turns them into unit-variance noise targets that no feature
  can predict, and they dilute the averaged gain. With a PCA-k control:
  - net1 k=2: micro_gain 0.026 with all dims vs 0.038 with informative dims only;
  - net3 k=2: 0.025 vs 0.035;
  - net2 k=2: -0.18 vs -0.26.
- The dilution factor is about 0.7, which biases the verdict toward "closed". tau_D = 0.085 was calibrated on synthetic systems
  whose readouts have no such dims.

This is also a normaliser computed on hidden test data (PROTOCOL.md section 4).

Fix: weight output dims by the public-train readout variance (`y / sqrt(scale)`, already computed) instead of re-standardising on
the test points. Alternatively, drop dims whose test variance is below a floor tied to the public normaliser (for example 1e-6 ×
scale).

### M4. On the real full systems, C is carried by 3 pairs, and about half the pairs have effects below solver resolution

Evidence (`.tmp/H/twin_eff_raw.py`, `.tmp/H/twin_denom.py`; real public test/twin pairs, 40 per full system, 250 ms window):

- Pairs whose maximum readout effect |y_int - y_twin| is below 0.04 Hz (the protocol's own piecewise-vs-single discrepancy, which
  is also below the 0.07 Hz solver-tolerance figure): 16/40 on net1, 18/40 on net2, 24/40 on net3.
- Share of Σ d_true² contributed by these pairs: 2.5e-6, 1.8e-7 and 2.5e-5. The 3 largest pairs carry 90 %, 96 % and 59 % of the
  denominator.

Because C is a ratio of sums, "the CI of C lies below 1", the tau_C test and the Holm-corrected C comparison on real data are
decided by 2-4 trajectories per network. The other half of the pairs carries no resolvable effect.

Fix (pre-register one of these):
- a minimum-effect screen (pairs whose Σ d_true² is below a multiple of the numerical-floor twin are reported apart);
- a per-pair normalised effect error (median over pairs) next to the ratio of sums;
- or intervention magnitudes chosen so that held-out effects exceed the solver floor.

### M5. A finite but diverged training trajectory sets the readout normaliser; the screen removes only non-finite values

Location: `evaluate.py:124-128` (`readout_scale` = plain variance over train) and `build_synthetic_suites.py:341-379` (the screen
only checks `np.isfinite`).

Evidence (`.tmp/H/scale_outliers.py`):

- In DEV system nonmarkov (syn-f62c10260a), one train `silence_single` trajectory diverges to |y| = 8.6e6 (|x| = 1.0e7). The
  readout normaliser is 4.87e10; without that trajectory it is 4.8e4. A second train trajectory reaches 7.5e3.
- Every absolute NMSE of this system (A, B, C post, E divergences, where random-pair divergence is 5.4e-12) is deflated by about
  1e6. The ratio-based verdicts are unaffected, but reported and aggregated absolute values are meaningless.
- Two test `noise_heldout` trajectories reach 1.1e4 (highdim_linear) and 6.7e3 (nonmarkov). One such trajectory dominates the mean
  NMSE of the robustness family H.
- The FullStateModel / TrueLatentModel standardisations (`refmodels.py:129-133, 354-358`) are fitted on the same data. The 80682×
  entry in `calibration.json`'s A-gap list is consistent with this.

HELDOUT and FINAL have 2× and 3× more trajectories drawn from the same generator, so similar cases are likely.

Fix:
- extend the screen to finite blow-ups (for example max |x| or |y| > 100 × the system's nominal-trajectory range);
- make `readout_scale` robust (for example the median over training trajectories of the per-trajectory variance);
- record the counts.

### M6. The synthetic noise realisation depends on t_end, so the lifting evaluation mixes two realisations

Location: `p3synth/core.py:271-288`. The noise arrays are drawn in one stream with shapes (n_steps·nsub, K), (…, N), (T, n_obs), so
every array after the first shifts when t_end changes. In `evaluate_lift.py:62` vs `:87-89`, `base` is simulated with
t_end = ti + future + 2dt, but the lift and its twin use t_end = t_end_lift + future + 2dt. These differ for current lifts.

Evidence (`.tmp/H/prefix.py`): the same protocol and noise_seed with t_end 1.52 s vs 1.82 s differ over the common first 1.52 s by
max |Δx| = 0.12 (linear_k3), 0.15 (hopf), 0.32 (hidden_exogenous) and 0.97 (nuisance_ou), i.e. 0.3-0.8 × sd(x). The lift is
computed from `base`'s microstate but applied to a different noise realisation.

Fix: in `eval_lifting`, simulate `base`, the lifts and the twins with one common t_end (for example the original P["t_end"]). Also
document that prefixes are not t_end-invariant, so simulation-service users are not misled. Longer term: draw the noise per output
step from spawned SeedSequences.

### M7. The synthetic tau_E and tau_D are applied to a real design with different windows, dt and pool geometry, and E depends on k even for the true state

tau_E and tau_D come from the synthetic configuration only:
- E: 1 s future, dt 10 ms, 4 draws × 8 × 4 states;
- D: task horizon 0.5 s.

They are applied to the real systems:
- E: 250 ms future, dt 1 ms, 6 × 8 × 4 states, a solver-only floor;
- D: task horizon 100 ms.

Evidence (`.tmp/H/e_analysis.py`, true latent, DEV pools):

- Truncating the E future to 0.25 s moves the median true-latent E only from 5.9e-4 to 7.9e-4, but individual systems move by
  large factors (wta 0.175 → 0.0029; slow_fast 7e-6 → 1.6e-5).
- Within one family, the true-latent E grows with the true dimension because the 2 %-nearest pairs of a finite pool get farther
  apart: linear_k1 3.0e-5, linear_k3 1.0e-3, linear_k6 2.5e-2 (fails tau_E), highdim_linear 0.32.
- For 20 of 48 systems the synthetic floor (another noise realisation) divided by the random-pair divergence exceeds tau_E. tau_E is
  only attainable there because all restarts of a draw share one noise realisation. The real design has no such noise.

A real circuit whose true state has k ≥ 4-6 therefore cannot pass E even with the exact state.

Fix:
- calibrate E per k, or make the criterion relative (for example E_method ≤ E of the PCA-k control and ≤ a k-matched true-latent
  reference);
- state explicitly that tau_E and tau_D are synthetic-only and that the real verdict uses them untested;
- add a real public calibration of the E ratio on public pools (public seeds, the same restart design).

## Minor issues

- m1. Real counterfactual twins lack the event breakpoints, so they differ from the intervened run BEFORE the event
  (`realgen.counterfactual`, `realsim.py:95-141`). The twin is integrated with fewer pieces, and RK45 truncates its step at the event
  time only in the intervened run. On the public pairs the first differing sample is up to 20 ms before the event, with max
  pre-event |Δy| = 0.0106 Hz and |Δx| = 0.0085 Hz (`.tmp/H/twin_align.py`). The synthetic twins are exact. The impact on C is
  negligible (see M4), but d_true is not exactly 0 before the event. Fix: give the twin the same breakpoints (no-op stimulus steps
  at every event t, t0, t1), as the E floor twin already does.
- m2. The lifting "achieved shift" for current lifts is read at idx(t1) + 1 (`evaluate_lift.py:85`). A current acts on [t0, t1), so
  its full effect is already in sample idx(t1). The docstring says "at the end of a current pulse". The extra free step
  contaminates the measured shift. Use idx(t1) for currents and idx(t) + 1 for kicks.
- m3. The noise-robustness guard (`evaluate.py:399`) scales the perturbation by `zf.std(0)`, the temporal spread of ONE rollout over
  a+b. For latents that are nearly stationary within the window (integrators, fixed points), this is about 0, so the "dimension
  cheating guard" adds almost no noise. PROTOCOL.md says "sd(z)". Use the spread of z across the test encodings.
- m4. `eval_closure` ignores input changes between t and t+h (`evaluate.py:303`: only u_t). Synthetic non-intervention families
  (random stimuli, `suite.py:82-100`) often step inside the 0.5 s task horizon. The unpredictable part inflates e1 and e2 alike, which
  dilutes the D gain like M3. Add u over (t, t+h] (for example its mean and final value) to the features.
- m5. `eval_microstate` uses `comps[:k]` with at most 10 PCs (`harness.pca_basis`), but reports `"k": k`. For k > 10 (or k > N_obs
  on mechanism systems) the PCA-matched control silently uses fewer components. Report the effective k.
- m6. There is no guard on the E denominator. `E_ratio_latent_to_random` is computed whenever rm > 0, even when the random-pair
  divergence is at or below the numerical / noise floor (hidden_exogenous: floor / random = 3.06). Report "untestable" when
  rm < c × floor.
- m7. Kicks at t = t_end are silently ignored by both simulators (`realsim.py:99`, loop over interior pieces; `core.py:333-335`,
  break before events). The protocol accepts them. Validate event times < t_end.
- m8. The closure sampling window starts at a hard-coded 0.25 s (`evaluate.py:294`) instead of a config value. This is harmless now
  but inconsistent with the per-kind configuration.
- m9. `realsim` restarts each piece from the output clipped to [0, 1000] with NaN set to 0 (`model.py:380-383`, `realsim.py:141`). A
  single frozen call clips only its output. The difference stays within tolerance (rates ≥ 0 are attracting), but the
  `non_finite_samples` path would carry a zeroed state into later pieces. Only `success` is recorded; the counts are dropped.

## What I checked and found sound

- Event-onset alignment. Both simulators record the PRE-event state at the event sample: `realsim.py:101-107` (kick after `R[ia]`)
  and `core.py:327-340` (sample i before events at step i). A current or silence acts on [t0, t1) from the step starting at t0 in
  both. The evaluator encodes at `idx(first_event_time)` (the pre-event sample), shifts events to rollout time 0, and compares rows
  1..m with samples i0+1..i0+m (`evaluate.py:194-211`). `refmodels._events_at` / `_event_masks` apply kicks before step j and drop
  exactly the transition i→i+1 of a kick. On the DEV suite all 432 test/twin pairs are bit-identical up to and including the event
  sample, and the first difference is always at +1 for kick, current, silence and edge_remove (`.tmp/H/twin_align.py`).
- A / B / R indexing: `u_future = u[i0 : i0+n+1]` with row 0 = time 0; targets `y[i0+1 : i0+m+1]`; B at the same sample as the
  encoding; closure-gap rows `full[a+1:]` vs `ref[1:]`. D targets at i+hm and i+d stay inside the trajectory (hi = T - max - 1).
  Horizons fit the trajectory length for both configs (real 1.2 + 0.5 < 2.0 s; synthetic 2.0 + 2.0 = 4.0 s → index 400 < 401).
- Synthetic restart equivalence (`.tmp/H/restart_synth.py`). For every one of the 48 DEV systems I took 2 pool-type trajectories × 3
  states. Restarting noise-free from the recorded `x_full[i]` under the trajectory's own shifted stimulus reproduces the continuation
  over 1 s to ≤ 3.6e-15 in z and ≤ 6.5e-15 relative in y. The v → x → v round trip at the restart is exact to ≤ 7e-14. The
  substep h = dt / nsub stays aligned with the output grid, so a restart at a sample is a restart at a step boundary.
- Pool construction. The DEV pools regenerate bit-for-bit (6144/6144 futures and floors, max difference 0.0) from
  `build_synthetic_suites._pool_system`. The shared noise_seed per draw makes futures differ only through the state, as documented.
  Pairs are restricted to the same draw and different pool trajectories (`evaluate.py:466-470`).
- The real pool restart design (read only; the engine cannot run here). The frozen model's state is the rate vector alone, so a
  restart from all ever-active neurons' rates is a full-state restart. The float32 rounding of the restart state (about 1e-7
  relative) is far below the 0.04 Hz solver discrepancy. The floor twin (an extra breakpoint at 0.125 s) measures exactly the
  piecewise-solver artefact. Pool trajectories use the same constant nominal input as the restart.
- Piecewise composition in `realsim.py`. `pulse_start = 0`, `pulse_end = piece + dt` makes the frozen `segments` scheme integrate
  each piece as one smooth segment with the current on. Weight noise is applied once. Kicks are clipped at 0 rate. u is written per
  piece with the same [t, t+dt) convention. The observed pre-event test/twin discrepancies (≤ 0.011 Hz) are consistent with the
  protocol's 0.04 Hz equivalence claim.
- Generator integration. RK4 with h ≤ min(5 ms, 0.3/λ) gives λh ≤ 0.3 on the stiff leak, far inside RK4 stability; the stability
  factor 0.7408 matches e^-0.3. Additive process and private noise are added per substep with sd·√h (Euler-Maruyama for additive
  noise; the variance per output step is independent of nsub). The noise shapes do not depend on events, so twins share the noise
  exactly. The accuracy report (`reports/accuracy_timing.json`) agrees with a DOP853 reference to ≤ 2e-6 (chaotic RNN 8e-5). Its
  scope is noise-free and event-free (see M1 for the event path).
- Normalisation. `readout_scale` and `pca_basis` use train-only data (`suite_eval.py:263-265`, `train_only`). The paired
  comparisons use the same units for both models. The exceptions are the test-side standardisations in D (M3) and E (B1).
- Calibration reproducibility. My recomputation of the true-latent E matches `calibration.json` to 0.0 relative difference on all
  45 systems.
