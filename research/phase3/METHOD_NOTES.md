# brainir_state_v1 — the composer's method (family H)

Code: `src/brainir_state/methods/brainir_state_v1.py` (registers `brainir_state_v1`; imports ks_core / ks_sindy / ks_abstain and
re-implements nn_fit's plateau tolerance and input floor; no other developer's file is modified). Tests:
`tests/methods/test_brainir_state_v1.py` (toy network generated in the test, plus one v3-evaluator check on a dev system; 37 tests incl. every ablation switch, ~3 min).
Experiments: `runs/brainir/` — `evalkit.py` (fit + public v2 evaluator, `train=` passed for E), `dimexp.py` (the paired component
experiment on all 48 dev systems), `fitonly.py` (abstention / determinism / timing), `floorcheck.py`, `shareexp.py`, `refs.py`
(reference controls), `summarize.py`, `pubprofile.py`. Results: `runs/brainir/res/*.jsonl`, reference cache `runs/brainir/refcache/`.

## 0. Decision and the evidence behind it

**Is a hybrid better than the best single candidate?** The answer here is a narrow yes on the public evidence, for a specific,
small hybrid: ks_sindy's model and event machinery, with four components taken from the nn family or added by the composer, each
targeting a profile component where ks_sindy is measurably weak. It is not shown on held-out data (that is round 3).

Evidence used (notes/_tournament_feedback.md; ranks computed from the tables):

- Round 1 (pilot, 15 compressible systems): ks_sindy best on S1 (0.96), S2 (0.345) and S7 (0.967, tied); weak on S3 / S4 (rank 12),
  S6 (0.8). nn_closed best overall (S6 = 1.0).
- Round 2 (all 46 compressible held-out systems, sharing groups and nulls), eligible finalists:

  | candidate | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 | mean rank |
  |---|---|---|---|---|---|---|---|---|---|
  | lin_subspace | 0.999 | 0.564 | **-0.083** | 0.00175 | 0.996 | 0.674 | 0.457 | 0.5 | **3.31** |
  | lin_falds | 1.16 | **0.55** | -0.005 | **0.00105** | 0.997 | 0.587 | 0.891 | 0.5 | 3.69 |
  | nn_closed | **0.938** | 0.746 | -0.008 | 0.00226 | 0.991 | **0.783** | 0.978 | 0.5 | 3.88 |
  | lin_dmdc | 1.08 | 0.613 | -0.049 | 0.00159 | 0.995 | 0.565 | 0.902 | 0.5 | 3.94 |
  | ks_sindy | 0.969 | 0.585 | -0.035 | 0.00173 | 0.995 | 0.652 | 0.696 | **0.167** | 4.12 |
  | nn_aelin | 1.09 | 0.983 | -0.071 | 0.00277 | 0.991 | 0.783 | **0.989** | 0.5 | 4.38 |
  | lin_balanced | 1.03 | 0.68 | -0.046 | 0.00236 | 0.997 | 0.543 | 0.5 | 0.5 | 4.69 |

  ks_sindy is second on S1, third on S2 and near the top on S4, but loses most of its rank on three components that are NOT about
  its model: S6 (dimension rule), S7 (abstention: 0.696, i.e. about recall 0.5 on the two controls plus ~2 false alarms) and S8
  (sharing: 0.167, below the 0.5 that "reject every sharing request" earns; its shared law was accepted on unrelated pairs).
- The nn family's dimension tolerance and input-floor abstention carry the best held-out S6 / S7 of the tournament (nn_closed /
  nn_aelin S6 0.783 in round 2, 1.0 / 0.933 in round 1; S7 0.978 / 0.989).

Composition (every choice below is tested on the public data in section 7):

| component | from | targets | public evidence |
|---|---|---|---|
| predictive-basis encoder, E-SINDy integral-form law, polynomial readout, micro-coupling event operators with calibrated gains | ks_sindy | S1, S2, S4 | held-out S1 0.969 / S2 0.585 (2nd / 3rd); nothing else was better on both |
| plateau tolerance for k (tournament version: max(0.1 e*, 0.005, SE) of nn_fit.select_k; current: max(0.1 e*, 0.005) with nested configurations and a cross-fitted e*, section 3 / 10) | nn_fit.select_k | S6 (and A, C) | tournament version, dev: k changes on 19 / 48 systems vs ks_sindy's rule; better held-out C on 15 / 19 (sign test p ~ 0.02), A 11 / 19, E 11 / 19. Current version vs tournament version: neutral (section 11.1) |
| input-floor abstention (val error > 0.5 x input-only floor) | nn_fit.abstention | S7 recall | dev: flags both probable controls (incl. the 60-D linear one ks_sindy misses), one probable trap |
| k sweep continued past 8 while still falling | composer | S7 false alarms, S6 | dev: removes 2 probable false alarms (200-unit systems plateauing at k = 8) |
| internal sharing test (non-inferiority, 20 % margin) before returning a shared law | composer (rule of PROTOCOL section 7 / sd_shared) | S8 | dev: rejects all 3 probable unrelated pairs (ks_sindy's shared law is otherwise returned) |
| deterministic candidate budget | composer | determinism, eligibility | fits 47-122 s synthetic, 416 s real full (lightly loaded) |
| honest event support (abstain on kinds without calibrated evidence) | composer (pre-lock review) | S2 honesty, L | 6 of 16 dev systems abstain on some held-out pairs |

Considered and NOT adopted:
- other families' intervention operators (nn / cb / lin): none beats ks_sindy's route on held-out S2 in both rounds except lin_falds
  (0.55 vs 0.585, round 2), whose Kalman encoder would replace the encoder the whole ks model is built on;
- a multi-step prediction-error refinement of the law (lin_subspace PEM, ks_kae / nn training): would move the encoder the event
  operators depend on; trained-latent entries are not better on S1 than the integral-form regression by a margin that pays for it;
- counterexample refinement (cb_cegar): its held-out profile is below its base on most components;
- a consensus k (smallest k accepted by either rule): suggested by the dev results after the fact (section 7.1), not pre-registered;
  rejected as post-hoc;
- redesigning the shared law so that implementation GROUPS pass (median k, delays, longer joint training): the evaluator also needs
  encoder-only adaptation to beat a from-scratch fit, which sd_shared could not achieve with a dedicated design; not attempted.

## 1. Model (per system s; all statistics from the fit's own train + val trajectories)

Model grid: every s-th sample, s = round(T / 400) (synthetic 1; real 5 ms); rollouts are interpolated back to the data grid.
Standardisation x~ = (x - mu) / sd with sd floored at 5 % of the median unit sd; u and y statistics likewise (y only as a target).

**Encoder.** Features f_t = [x~_t, x~_{t-l_1}, ..., x~_{t-l_m}] (causal, edge-padded; delay set chosen in section 3). Predictive
basis (ks_core.predictive_basis): targets F_t = [y~_{t+h}, (P x~_{t+h}) / 4], h in {0, 1, 2, 4, ..., H}, H = T/4, P = top-16 PCs of
x~, on event-free windows; future-input summaries U_t = [u_t, u_{t+h}, mean u_{t:t+h}] partialled out of both sides (Frisch-Waugh);
ridge B = argmin ||F - f B||^2 + lambda n ||B||^2 (lambda in {1e-4, ..., 1e-1} by a trajectory split); SVD of f B = U S V^T;
C = B V_r, columns scaled to unit variance.

    z_t = (f_t - mean f) C_k            k leading columns; linear, causal, never sees y (y is only a regression target)

**Transition.** z_{t+1} = z_t + Theta(z_t, u_t) Xi, Theta = the monomials of degree <= p of (1, z, u) in which each input appears at
most once (control-affine / bilinear), at most 60 terms. Integral form over m = T/100 steps on event-free windows:
(z_{t+m} - z_t) / m = (1/m) sum_{s<m} Theta(z_{t+s}, u_{t+s}) Xi, standardised columns, STLSQ with threshold thr. E-SINDy: 24
bootstrap resamples of trajectories, inclusion probability pi_j, support {pi_j >= 0.6}, coefficients refitted on all rows on that
support. Rollouts are clipped to the training latent box widened by its span per coordinate (valid domain).

**Readout.** y_t = ridge regression on the monomials of (z_t, u_t) of degree r in {1, 2}.

**Decoder (for events only).** x^ = mu + sd (z D + d), least squares on the training data.

**Parameter counts** (info()["n_params"]): encoder = size(C_k) + size(mean f); transition = active terms + k; readout = ridge size.

## 2. Objective

No gradient training in an independent fit; everything is least squares:
- encoder: the reduced-rank ridge objective of the predictive basis;
- law: min_Xi sum_windows ||(z_{t+m} - z_t)/m - mean_s Theta(z_s, u_s) Xi||^2 + 1e-5 ||Xi||^2 on the STLSQ / E-SINDy support;
- readout / decoder: ridge.
Model SELECTION (k, delays, degree, threshold, readout degree) uses the simulation error: per validation trajectory, the window
NMSE of the readout over open-loop rollouts (with the trajectory's own events) from 4 start times in [T/8, T/2], horizon T/4, each
rollout capped at 2. (Shared fits, section 5, use ks_share's gradient training.)

## 3. Latent-dimension rule (generic; training / validation data only; version after the pre-lock reviews)

Folds: 2 x 2 random trajectory folds (two independent splits derived from the seed, units pooled; for k) and 2 parameter-draw
folds (for the final configuration); validation sets <= 16 trajectories per fold.
1. Ascending sweep over the base grid k in (1, 2, 3, 4, 5, 6, 8) on the trajectory folds. Every configuration (delays: none,
   {1, 2.5} % of T, {1, 2.5, 5, 10} % of T; degree p in {1, 2, 3} with at most 60 library terms; threshold in {0, 0.05, 0.2}) is
   fitted on each fold's training part and scored on its validation trajectories (units).
2. NESTED configuration choice (review D): the validation trajectories of every fold are split into two halves (alternating); for
   each k the configuration is chosen on one half (the simplest within log 1.05 of the best mean log(NMSE + 0.01)) and supplies the
   errors of the OTHER half, and vice versa. e_{k,i} = these cross-nested errors; the k comparison never uses the units on which the
   configuration was chosen.
3. Extension: k in (10, 12, 16) is scored in turn only while the last candidate is the best so far and improved on the previous one
   by more than the tolerance; the sweep stops at the first failure.
4. Minimum k from the data's structure (review E): if the training data show a SUSTAINED oscillation under a constant input
   (`sustained_oscillation`: on the leading microstate PC of the longest constant-input stretch of each trajectory, >= T/4 long,
   first quarter dropped, an autocorrelation trough <= -0.3 followed by a peak >= 0.3 and no amplitude decay below half; flagged when
   >= 25 % of >= 2 stretches oscillate), k_min = 2 (a 1-D autonomous flow cannot oscillate), else 1.
5. Rule (review D: no tolerance that grows with a candidate's variance):

       e* = min_k mean_i e_{k,i} (at k_b),   tol = max(0.1 e*, 0.005),
       k = the smallest candidate k >= k_min with mean_i e_{k,i} <= e* + tol   (else the best k >= k_min).

6. Range (review G: width from validation uncertainty; descriptive, earns no credit in v3): with d_k = e_k - e_{k_b} paired over
   units and SE_k its standard error, lo = the smallest k >= k_min whose one-sided 95 % LOWER bound mean d_k - 1.645 SE_k <= tol (not
   shown worse than the tolerance), hi = the smallest k whose UPPER bound mean d_k + 1.645 SE_k <= tol (shown within it; else k_b);
   k_range = [min(lo, k), max(hi, k)].
7. The configuration at k (delays, degree, threshold, then the readout degree) = the simplest within 5 % (log units) of the best on
   the parameter-draw folds; final E-SINDy fit on all trajectories at that configuration.
- Budget: deterministic (review 1). The candidate list is the base grid plus at most 3 extension values; nothing depends on wall-clock
  time or load (the earlier 600 s time guard was removed). Given the same data, config and seed the fitted model is identical.
- config["k"] forces k (no sweep over k, no extension, no oscillation check, no abstention).
- Law class across k: the library is capped at 60 terms, so degree 3 is available only for k <= 3 and degree 2 for k <= 8 (with one
  input); larger k have a poorer law class. This is a stated limitation of review D's "comparable law class" (the cap bounds cost).

## 4. Abstention rule

"No compact state under current evidence" when any of:
- (a) k > max(1, N_observed / 5);
- (b) no plateau: the best k (by ks_sindy's own paired log-error selection on the same curve) is the largest candidate scored and
  the validation NMSE still fell by more than log(1.05) over the last step (ks_abstain);
- (c) the best validation NMSE >= 0.6 (ks_abstain);
- (d) input floor: the validation NMSE at k > 0.5 x the input-only floor, the fold-averaged validation NMSE (same normaliser) of a
  ridge readout from the input, its lags (1, 4, 16, 64 model steps) and an onset flag (nn_fit's rule, on this method's folds).

"Dimension unresolved [k_lo, None]" only when the whole candidate list (up to k = 16) was used while the error still fell.
The checks of review E are reported (not abstention reasons) in info()["checks"][sid]: "oscillation" (flag, stretches, k_min),
"persistence" (the model's validation NMSE at k against the persistence floor y(t) = y(t0) on the same validation windows,
"static" when the persistence NMSE < 0.01, and "beats_persistence" = the one-sided 95 % upper bound of the paired difference < 0), and
"latent_clip_on_validation" (review B: fraction of rollout steps on the latent box, rollouts touching it, non-finite rollouts).
causal_equivalence_failed is not asserted. Forced-k and adapted models never abstain.
(b) is evaluated with ks_sindy's statistics, not the nn tolerance, on purpose: with the smaller nn tolerance the no-plateau test fires
on small drops and produced a probable false alarm on the dev suite (syn-fe868499dd). ks_sindy's range-width "unresolved" flag is
dropped (the range is descriptive).

## 5. Interventions, sharing, adaptation, lifting

**Interventions** (ks_core.KSModel operators; support per system and kind, see below; rollouts are
brainir's own copy of ks_core's grid rollout with one change: a non-finite latent is never replaced by a finite value, the rest of
the rollout is NaN and so is y, review B). With C_0 the current-sample block of C_k, x^ the decoded microstate,
A_off the off-diagonal of a ridge estimate of the microscopic one-step map dx = A x + B u + c (reduced rank by held-out error) and
gamma one global current gain (regression of the free-model residual on the injected current):
- kick dx at t: z <- z + g_kick (dx / sd) C_0 (for rates, the offset is clipped so the unit stays >= 0);
- current I on units during a window: per step z <- z + g_cur (gamma I / sd) C_0;
- silence S: 'drive' = per step z <- z + g_sil (-A_off[:, S] x^_S / sd) C_0 (outgoing couplings removed), or 'clamp' = decode, set the
  silenced units to rest, re-encode;
- edge removal (i <- j): per step z <- z + g_edge (-A_off[i, j] x^_j e_i / sd) C_0.
g_kind in {0, 0.25, 0.5, 1} and the silencing mechanism are chosen per kind by paired post-event rollout NMSE (capped at 2) on the
training trajectories carrying that kind (g = 0 = "no effect" is a guard against confidently wrong effects); g_edge = the best drive
gain x the split-half reliability of the coupling entries. Held-out targets and group / combined events use the same operators.
The simulator is not used (sim ignored).

**Events on unobserved neurons (review C).** The model has no encoder column or coupling estimate for neurons outside x, so the part
of an event acting on unobserved neurons (targets, or edges with an unobserved end) is predicted to have NO effect; events on observed
neurons in the same protocol are modelled as usual. supports() is per kind, so such pairs are not abstained on. This policy is
reported per system in info()["events"][sid]["unobserved_targets"]; the v3 evaluator scores these pairs apart from the verdict.

**Events and the encoder's memory (review F).** When the selected encoder reads delayed copies of x (delays chosen in 7), an event
enters z only through the CURRENT-sample block C_0: after a kick the model's z is the encoding of a history in which the kick is
present now but absent from the delayed copies, which is not where the encoder would place the true post-kick history once the
perturbation ages into the delayed copies. z after an event is therefore off the encoder's manifold for up to the longest delay (1-10 %
of T); the v3 evaluator reports this as the interventional closure gap. Not corrected here (a lag-aware event operator would need the
delayed copies as state, i.e. a larger k).

**Honest support (pre-lock review).** supports(sid, kind) is True only if (i) the system's training data contain trajectories whose
only events are of that kind (so its gain was actually calibrated; edge removal uses the silencing trajectories), (ii) the calibrated
gain is > 0, and (iii) the read-in exists: current needs gamma != 0 and finite; edge removal needs a positive drive gain x coupling
reliability. Otherwise the kind is abstained on (the evaluator records the abstention instead of scoring a silent "no effect").
info()["events"][sid][kind] = {"supported", "gain", "calibrated"} (+ "kick_readin_steps"). With `ablate: ["event_calibration"]`
the raw mechanisms are used and supported wherever their read-in exists. On the 16-system dev subset (`ev2.jsonl`) the new rule
abstains on at least one held-out pair on 6 systems (e.g. syn-b8dafc4f01: every gain calibrated to 0, all 8 pairs abstained;
syn-566e16b512: silencing gain 0, 4 pairs); the C of the supported families is unchanged. Consequence: those systems cannot meet
the "interventional" verdict condition (it requires no abstained pair) — the intended honesty cost.

**Kick read-in from intervention data (tested, NOT adopted; config kick_readin=True).** Recommended by the pre-lock review: neurons
the encoder reads but that do not drive the dynamics should not move the latent like the ones that do. Implemented option: the kick
is propagated through the estimated microscopic map before encoding, dx <- stab(I + A)^h dx (stab = spectral radius <= 1), h in
{0, m, 3m} (m = T/100; h = 0 is the encoder read-in), with (h, g_kick) chosen jointly by the paired post-event error on the training
kick trajectories. Result on the 16-system dev subset (same fits otherwise): group kicks better on 5 / worse on 4 systems (median C
0.82 -> 0.73), new-target kicks 4 / 4 (0.42 -> 0.44), with two large new failures where the encoder read-in had calibrated to
"no effect" (syn-0dccdf2720 group kick C 1.0 -> 2.4, syn-6f252b24d5 1.0 -> 22.7): with ~4 training kicks per system the joint choice
over-fits. The budgeted simulation service could supply more (kick, twin) pairs, but a fit may run with sim=None and the effect
was not established; the option is off in the locked default. Limitation: the kick read-in remains the encoder's observational
weights (a unit read by the encoder but causally inert still moves z, scaled by one calibrated gain per system).

**Sharing** (config sharing='shared', several systems). ks_sindy's shared fit: k = the largest per-system k (or config k); the
reference system's E-SINDy law at that k fixes the support; per-system linear encoders on each system's own predictive coordinates
are trained jointly with the law (multi-horizon rollout loss, latent mean / covariance normalised to the reference, multi-start
orthogonal initialisations); per-system readouts and event calibration. **Sharing test on held-out trajectories (review H)**:
per system the held-out set is its 'val' split (every 5th trajectory if fewer than 3); on the remaining trajectories the independent
models (at each system's selected k, configuration re-chosen) and the shared law are fitted; on the held-out trajectories only, the
shared law is supported iff for EVERY system the one-sided 95 % upper bound of the paired per-trajectory difference of rollout NMSE
(shared - independent) is <= 0.2 x the independent error (the evaluator's relative margin), and it has fewer transition parameters
than the independent laws together. Supported: the shared model is refitted on all trajectories and returned,
info()["sharing"] = {"mode": "shared", "verdict": "supported", "test": ...}; otherwise the independent models (fitted on all data)
with {"mode": "independent", "verdict": "unsupported", "test": ...}. (The first version compared both on the trajectories they were
fitted on.)
'auto' / 'independent' fit independent models. 'partial' is not supported (NotImplementedError).

**Adaptation** (config adapt_from = a fitted brainir_state_v1 / ks_sindy model): the source law (its first system's, for a model
with several independent laws) is frozen bit-identically; per new system, linear encoders (multi-start) and readouts are trained;
events calibrated on the new system's own training events; k inherited; info()["train_cost"]["adaptation"] = True.

**Lifting**: not supported (lift() returns []).

## 6. Ablation switches (config={"ablate": [...]}; each keeps a valid model through the same API; all tested)

| switch | removes |
|---|---|
| `nn_dim_rule` | the plateau tolerance max(0.1 e*, 0.005) -> ks_sindy's paired log rule (tol = max(SE, log 1.05)) |
| `nested_selection` | cross-nested configuration choice -> the in-sample best configuration supplies its own units |
| `oscillation_check` | k >= 2 for oscillating data -> no minimum k |
| `fold_repeats` | two pooled trajectory splits for the k sweep -> one split |
| `grid_extension` | the k sweep past 8 -> the base grid only |
| `draw_folds` | configuration chosen on parameter-draw folds -> on the trajectory folds |
| `delays` | causal delay features -> the current microstate only |
| `esindy` | E-SINDy bagging -> a single STLSQ fit |
| `sparsity` | thresholding (grid 0 / 0.05 / 0.2) -> threshold 0 (ridge on the full library) |
| `event_calibration` | calibrated per-kind gains and silencing mechanism -> raw mechanisms, gain 1, 'drive' (supported where a read-in exists) |
| `domain_clip` | the widened training latent box in rollouts -> unconstrained rollouts |
| `input_floor` | the input-floor abstention (d) -> ks_sindy's rules (a)-(c) only |
| `abstention` | every abstention rule -> never abstain |
| `sharing_test` | the held-out sharing test -> the shared law is always returned under sharing='shared' |
| `sharing` | the shared fit and adaptation -> independent fits (sharing='shared' / adapt_from ignored) |

Not a switch (always on, required by the reviews): the deterministic budget, honest supports(), NaN propagation, the reported checks.
Optional, off by default: config kick_readin=True (section 5).

`ablate: ["nn_dim_rule", "nested_selection", "oscillation_check", "fold_repeats", "grid_extension", "input_floor",
"sharing_test"]` approximately reproduces ks_sindy (differences: honest supports(), NaN propagation, no range-width "unresolved" flag).

## 7. Public results of the TOURNAMENT version (benchmark v2 evaluator, seed 0; historical — current results: section 11)

Synthetic: fit on train + val, evaluated on test / twin / pool with SYNTH_CFG (`train=` passed for E whitening). Real: fit on train,
evaluated on val / twin with REAL_CFG (val nominal / init_state as non-intervention, val kick_A / pulse_A / silence1_A with twins as
the intervention pairs; these targets are in-distribution, so real C is easier than the hidden test).

### 7.1 The dimension component: paired against ks_sindy's rule on ALL 48 dev systems (`runs/brainir/res/dimexp.jsonl`)

The two rules are applied to the same sweep; where they select a different k (19 of 48 systems) the pipeline was refitted with
`ablate: ["nn_dim_rule"]` (= ks_sindy's selection).

| system | k nn / ks | A | C | D | E |
|---|---|---|---|---|---|
| syn-0dccdf2720 | 1 / 3 | **0.414** / 0.770 | 0.98 / 0.99 | 0.023 / -0.263 | **0.0078** / 0.0102 |
| syn-154d77eb23 | 4 / 2 | **0.271** / 0.394 | 0.39 / 0.40 | -0.077 / -0.072 | 0.0086 / **0.0036** |
| syn-1e61c72597 | 1 / 2 | **0.095** / 0.463 | **0.12** / 3.50 | -0.346 / -0.018 | 0.0002 / 0.0001 |
| syn-1edfa10118 | 1 / 2 | **0.035** / 0.043 | **0.84** / 1.27 | 0.058 / -0.072 | **0.0020** / 0.0058 |
| syn-1f16e42a17 | 3 / 2 | 0.060 / 0.054 | 0.24 / 0.27 | -0.027 / -0.773 | 0.0047 / 0.0027 |
| syn-3296f4ad79 | 2 / 4 | 0.266 / 0.264 | **0.64** / 0.77 | 0.085 / -0.103 | **0.0031** / 0.0173 |
| syn-44f7fa1051 | 5 / 4 | 0.404 / 0.439 | **0.47** / 4.72 | 0.261 / 0.213 | 0.0056 / 0.0038 |
| syn-566e16b512 | 3 / 2 | 0.037 / 0.037 | **0.30** / 0.91 | 0.034 / -1.000 | 0.0018 / 0.0005 |
| syn-567a33cb55 | 1 / 2 | 0.171 / 0.171 | 1.00 / 1.00 | -0.310 / -0.460 | 0.0001 / 0.0003 |
| syn-58bf7d0101 | 1 / 5 | 0.121 / 0.107 | 0.11 / 0.12 | -0.060 / 0.306 | **0.0024** / 0.0272 |
| syn-74c2a90450 | 3 / 4 | 0.342 / 0.328 | 0.91 / **0.41** | -0.133 / 0.179 | 0.0034 / 0.0048 |
| syn-78aa168dd6 | 3 / 4 | 0.363 / 0.356 | 1.35 / 1.26 | -0.095 / -0.083 | 0.183 / 0.222 |
| syn-7bc1b50022 | 4 / 2 | 0.860 / 0.845 | 0.45 / 0.44 | -0.020 / -0.021 | 0.0316 / **0.0026** |
| syn-94a60083e6 | 1 / 2 | 0.013 / 0.013 | 0.20 / 0.20 | 0.594 / 0.537 | **0.0004** / 0.0044 |
| syn-b8ba1e6d77 | 2 / 3 | 0.007 / 0.007 | 0.17 / 0.20 | -0.015 / -0.065 | 0.0003 / 0.0004 |
| syn-c37b6a1b4d | 6 / 4 | 0.586 / 0.596 | 3.89 / **1.37** | -0.052 / -0.057 | 0.108 / 0.065 |
| syn-d18eff9b51 | 2 / 3 | **0.172** / 0.324 | 0.08 / 0.08 | 0.507 / 0.018 | **0.0038** / 0.0078 |
| syn-f365aa5a73 | 2 / 4 | 0.026 / 0.026 | 0.16 / 0.20 | -0.062 / 0.305 | **0.0031** / 0.0355 |
| syn-fe868499dd | 8 / 2 | **0.059** / 0.093 | **0.17** / 0.37 | 0.432 / 0.023 | 0.0101 / **0.0033** |

Over the 19: the nn tolerance is better on A 11 / 19, on held-out C 15 / 19, on E 11 / 19, on D 6 / 19. Whole-suite medians (48
systems; the ks rule substituted where it differs):

| | median A | median C | median D | median E |
|---|---|---|---|---|
| brainir_state_v1 | **0.126** | **0.654** | -0.017 | **0.0036** |
| same pipeline with ks_sindy's rule | 0.129 | 0.769 | -0.020 | 0.0041 |

The one cost is D (the closure gain is less negative when k is smaller: S3 may lose rank). Pattern: when the nn rule selects the
SMALLER k (12 systems) it is better or equal on almost every metric (exceptions: C on 74c2, A on 58bf); when it selects the LARGER
k (7 systems) A / C are split and E is worse in 7 of 7 — this pattern is what suggested the (rejected, post-hoc) consensus rule.

### 7.2 Against the reference controls (16-system dev subset `runs/brainir/res/sub16.txt`; `pubprofile.py`)

References fitted on train + val without blow-ups (harness.fit_references classes), evaluated with the same harness call.

| system | k | A | A_full | A_input | A_readout-hist | A_pca-k | C | C_pca-k | D | E | E_pca-k | P I Cl E |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| syn-0dccdf2720 | 1 | 0.414 | 0.449 | 0.371 | 0.360 | 0.434 | 0.98 | 1.01 | 0.023 | 0.0078 | 0.0208 | . . Y . |
| syn-1e61c72597 | 1 | 0.095 | 0.080 | 1.058 | 0.244 | 0.251 | 0.12 | 9.22 | -0.346 | 0.0002 | 0.0002 | Y Y Y Y |
| syn-3296f4ad79 | 2 | 0.266 | 0.314 | 1.019 | 0.374 | 0.311 | 0.64 | 3.46 | 0.085 | 0.0031 | 0.0047 | Y Y Y Y |
| syn-44f7fa1051 | 5 | 0.404 | 0.017 | 3.363 | 0.171 | 0.236 | 0.47 | 0.18 | 0.261 | 0.0056 | 0.0150 | . . Y Y |
| syn-566e16b512 | 3 | 0.037 | 0.047 | 0.981 | 0.161 | 0.135 | 0.30 | 2.65 | 0.034 | 0.0018 | 0.0015 | Y Y Y Y |
| syn-9853fca40a | 1 | 0.030 | 0.042 | 0.236 | 0.178 | 0.032 | 0.06 | 0.30 | 0.198 | 0.0029 | 0.0057 | Y Y Y Y |
| syn-b8dafc4f01 | 2 | 0.151 | 0.242 | 1.035 | 0.280 | 0.264 | 1.00 | 4.71 | 0.509 | 0.0019 | 0.0012 | Y . . Y |
| syn-f365aa5a73 | 2 | 0.026 | 0.026 | 0.769 | 0.634 | 0.095 | 0.16 | 0.17 | -0.062 | 0.0031 | 0.0078 | Y Y Y Y |
| syn-290fca687b | 1 | 0.119 | 0.133 | 0.897 | 0.368 | 1.002 | 0.60 | 0.55 | -0.468 | 0.0009 | 0.1007 | Y . Y Y |
| syn-6f252b24d5 | 4 | 0.088 | 0.217 | 0.884 | 0.167 | 0.151 | 0.80 | 307.6 | -0.013 | 0.0067 | 0.0033 | Y . Y Y |
| syn-7f8bce040d | 3 | 0.125 | 0.277 | 0.959 | 0.371 | 0.296 | 0.81 | 0.38 | -0.123 | 0.0099 | 0.0123 | Y Y Y Y |
| syn-c2a119aa19 | 6 | 0.104 | 0.261 | 1.010 | 0.316 | 0.289 | 4.23 | 4.40 | -0.049 | 0.0286 | 0.0579 | Y . Y . |
| syn-e8bb5a2e46 | 2 | 0.010 | 0.011 | 1.650 | 0.118 | 0.098 | 0.87 | 0.69 | -0.015 | 0.0005 | 0.0003 | Y . Y Y |
| syn-154d77eb23 | 4 | 0.271 | 0.381 | 1.079 | 0.467 | 0.380 | 0.39 | 0.54 | -0.077 | 0.0086 | 0.0186 | Y Y Y . |
| syn-c37b6a1b4d | 6 | 0.586 | 1.228 | 1.297 | 0.769 | 1.250 | 3.89 | 5.50 | -0.052 | 0.1075 | 0.0637 | Y . Y . |
| syn-1f16e42a17 | 3 | 0.060 | 0.053 | 1.988 | 0.297 | 0.225 | 0.24 | 0.29 | -0.027 | 0.0047 | 0.0036 | Y Y Y Y |

P / I / Cl / E = the verdict conditions predictive (A <= A_full (1 + tau_A) and below both shortcuts, point values), interventional
(C <= tau_C and upper CI < 1), closed (upper CI of D <= tau_D), microstate-equivalent (upper CI of E <= tau_E). All five hold (k is
compact everywhere) on 7 of 16 systems (1e61, 3296, 566e, 9853, f365, 7f8b, 1f16).

| subset of 16 | median A / A_full | median C | median D | median E | predictive | interventional | closed | micro-eq. |
|---|---|---|---|---|---|---|---|---|
| **brainir_state_v1** | **0.81** | **0.62** | -0.021 | 0.0039 | **14** | **8** | 15 | **12** |
| same pipeline, ks_sindy's rule | 0.86 | 0.84 | -0.053 | 0.0037 | 13 | 5 | 15 | 10 |

Other candidates on public dev data (their own notes; other subsets / code versions, descriptive only): ks_sindy (8 systems, v2)
median A / A_full 0.70, C 0.93; nn_closed (6 systems, v3) A / A_full 1.11, C 0.69; lin_subspace (7 systems, v5) A / A_full 1.00,
C 0.40; cb_psr (48 systems) C 0.52. Held-out comparisons are the tournament's (section 0).

### 7.3 Abstention on the dev suite (`fitonly.jsonl`, `fitonly_v2.jsonl`, `floorcheck.py`)

Final rule: abstains ("no compact state") on 3 of 48 systems:
- syn-12db9981b8 (N 200; probable chaotic control): best validation NMSE 0.89 >= 0.6, and 0.89 > 0.5 x input floor 0.97;
- syn-78aa168dd6 (N 60, 3 inputs; probable 60-D linear control, E 0.18 for every model): input floor (0.567 > 0.5 x 0.986) — ks_sindy
  does not abstain here;
- syn-c37b6a1b4d (probable bistable trap; compressible, so a probable FALSE ALARM): input floor (0.583 > 0.5 x 1.040); the model is
  poor there anyway (C 3.9, E 0.11).
Floor ratios of the other 45 systems: <= 0.39. Before the grid extension, syn-5f1b4fcec5 and syn-acc9812084 (N 200, validation
NMSE falling steeply to k = 8: 0.038, 0.085) were abstained as "no plateau"; with the extension k = 10 shows the plateau
(0.037, 0.084) and they are not. If the two probable controls are the controls, the dev abstention quality is (1 + 45 / 46) / 2 = 0.99
(ks_sindy's own pipeline, its k and rules, abstains on 12db, 5f1b, acc9 and syn-f365aa5a73 (k = 4 > N / 5) and misses 78aa:
(0.5 + 43 / 46) / 2 = 0.72, close to its held-out 0.696).

### 7.4 Sharing (`shareexp.py`, `share.jsonl`; sets from notes/sd_shared.md, NOT confirmed truth)

| set | systems | internal verdict | shared vs independent rollout NMSE (per system) |
|---|---|---|---|
| probable unrelated pair A | 1f16 / c011 | unsupported | 0.095 vs 0.080; 0.96 vs 0.23 |
| probable unrelated pair B | 7b62 / dcd0 | unsupported | 2.0 (diverged) vs 0.080; 2.0 vs 0.111 |
| probable unrelated pair C | 1edf / e8bb | unsupported | 0.116 vs 0.018; 0.235 vs 0.058 |
| candidate Hopf group | b8da / b972 / c2a1 | unsupported | 0.206 vs 0.112; 0.151 vs 0.114; 0.206 vs 0.084 |
| candidate gated group | 44f7 / 58bf / 74c2 | unsupported | 2.0 (diverged) vs 0.08-0.10 |

Every request returns the independent models, so the evaluator's rule (fewer parameters) rejects sharing everywhere: expected S8
0.5 (pairs correct, groups wrong), against ks_sindy's 0.167. The shared law of ks_sindy is too weak for the groups (k = the largest
per-system k, no delays; the gated law diverges); making groups pass is not solved here.

### 7.5 Real public systems (fit on train; val / twin; `real.jsonl`)

| system | k | A | A_full | A_input | A_readout-hist | A_pca-k | C [95 % CI] | C_full | D [95 % CI] | fit s |
|---|---|---|---|---|---|---|---|---|---|---|
| net1:mech:02fa13b8 | 1 | 0.018 | 0.003 | 0.017 | 0.002 | 0.015 | 1.30 [1.01, 1.60] | 0.78 | -0.21 [-0.56, 0.07] | 67 |
| net1:mech:cce0c6c4 | 1 | 0.088 | 0.235 | 0.114 | 0.043 | 0.191 | 0.13 [0.06, 0.95] | 1.03 | 0.15 [0.01, 0.31] | 68 |
| net2:mech:3aa95ab7 | 1 | 0.044 | 0.015 | 0.041 | 0.012 | 0.055 | 1.18 [0.79, 1.22] | 1.09 | 0.02 [-0.04, 0.09] | 68 |
| net2:mech:3e8f8895 | 1 | 0.136 | 0.059 | 0.139 | 0.043 | 0.172 | 1.16 [0.94, 1.70] | 13.6 | 0.08 [-0.05, 0.23] | 70 |
| net2:mech:6883ab7b | 1 | 0.076 | 0.132 | 0.069 | 0.002 | 0.068 | 1.58 [1.01, 3.26] | 2.76 | 0.18 [-0.06, 0.46] | 67 |
| net3:mech:362044b4 | 1 | 0.081 | 0.046 | 0.555 | 0.027 | 0.178 | 1.00 [1.00, 1.01] | 2.35 | -0.13 [-0.98, 0.13] | 67 |
| net3:mech:92614efe | 1 | 0.037 | 0.264 | 0.046 | 0.002 | 0.059 | 1.14 [0.71, 1.37] | 0.87 | -0.59 [-1.00, -0.05] | 65 |
| net1:full | 1 | 0.099 | 0.087 | 0.099 | 0.021 | 0.105 | 1.03 [1.00, 1.14] | 67.3 | 0.03 [-0.18, 0.17] | 416 |

Not predictive on any real system: the readout-history control wins everywhere (the readout neurons are not in x and carry their
own state), as for every family. k = 1 on all of them; the ks rule gives the same k on 6 of 7 mechanisms (on net2:mech:3e8f8895 it
gives k = 4 with A 0.049 and C 0.95: better). Interventions are not predicted beyond "no effect" except silencing on
net1:mech:cce0c6c4 (C 0.13). net2 / net3 full: not run (time). E: not computable on the real public data (no pools).

### 7.6 Reproducibility, determinism, compute

- Deterministic: the 48 dev fits repeated in a second process give identical k everywhere; re-running the final code reproduces
  A, C, D, E to 5 digits (`final_check.jsonl`). Unit-tested (same seed -> same rollouts; pickle round trip).
- Seeds: G (across-seed stability) NOT RUN; the only randomness is the fold split, bootstrap bags and sub-sampling.
- Fit time (3 threads, lightly loaded machine): synthetic median 54 s, max 122 s (N = 240: 94 s); real mechanism ~67 s; real full
  circuit 362-416 s; shared fits of 2-3 systems 128-243 s. (ks_sindy was measured at 1410 s on N = 240 on a heavily loaded machine;
  the sweep has no time guard; its cost is bounded by the candidate list.)
- Parameters: encoder = (k + 1) x N (1 + number of delays); transition = active terms + k (e.g. 4 for syn-290fca687b; the
  shared-fit comparison in 7.4 shows 20-126 for 2-3 independent laws together); readout = ridge coefficients + intercepts (5-45).
- Development compute: about 5 h of wall time on 3 threads (the dev sweep and its ablated refits 1.5 h, abstention passes 1.3 h,
  references 0.5 h, real 0.4 h, sharing 0.25 h); simulator budget used: 0 units.

## 8. Hyper-parameters and how they were chosen

All hyper-parameters of the backbone are ks_sindy's, chosen by its developer on the public dev suite (notes/ks_methods.md): delay
grid, degree grid, thresholds, E-SINDy 24 bags / 0.6, integral window T/100, validation design, event gain grid, abstention 0.6.
Composer's constants were NOT tuned on the dev suite; each is taken from its source: plateau tolerance 0.1 / 0.005 and range
2 tol / tol / 2 (nn_fit), input-floor features and ratio 0.5 (nn_fit), sharing margin 0.2 and one-sided 95 % (PROTOCOL section 7),
extension grid (10, 12, 16) (nn_fit's candidate list); the time budget of the tournament version was removed (review 1). Pre-lock constants: 2 pooled fold splits (4 tested, section 11.2), oscillation-check thresholds (-0.3 / 0.3 / 0.5 / 25 %; conventional, not tuned). The dev results (section 7)
were used to accept or reject components, not to set constants; the one data-suggested alternative (consensus k) was rejected.

## 9. Known weaknesses and risks (current version)

- Held-out gain over ks_sindy is not established. The dimension rule was rebuilt before the lock (section 10) to meet the reviews
  (no variance term, nested configuration choice, cross-fitted reference); on public dev data it is roughly NEUTRAL against the
  tournament version's rule (section 11.1), not better. S6 cannot be measured in the room (no truth).
- k is not stable across fit seeds on flat validation curves: 3 of 9 compressible dev systems of the stability set change k across
  seeds 0-2 (syn-3296f4ad79 2 / 2 / 4, syn-44f7fa1051 1 / 4 / 6, syn-566e16b512 1 / 1 / 2); 4 pooled splits instead of 2 fixed only
  one of them (section 11.2). The reported k_range brackets the seed-0 selection but not always the other seeds' k.
- Some dev systems lose with the new rule: syn-d18eff9b51 (k 2 -> 6: A 0.17 -> 0.33, E 0.004 -> 0.054), syn-fe868499dd (k 8 -> 2),
  syn-44f7fa1051 (k 5 -> 1: C 0.47 -> 2.6).
- Interventions: honest supports() abstains on kinds without calibrated evidence or with gain 0; such systems cannot meet the
  "interventional" condition (15 of 48 dev systems meet it). The kick read-in remains the encoder's observational weights (the
  intervention-calibrated read-in was tested and not adopted, section 5). Event operators act on the current-sample block only, so z
  after an event is off the encoder's manifold when delays are used (review F; section 5).
- Events on unobserved neurons are predicted to have no effect (reported, not abstained; section 5).
- Real circuits: not predictive against the input-only control and the persistence floor on any system (v3 rule); the oscillation
  check sets k >= 2 on every real system, which makes the ks compactness rule (a) (k > max(1, N/5)) abstain on 7 of 7 small
  mechanism systems — honest ("no compact state") but uninformative there. One real mechanism system (syn net3:mech:362044b4) has an
  unstable rollout (A 1.8 vs input-only 0.56; latent box active on 14 % of validation steps; reported in info()["checks"]).
- Abstention: one probable dev false alarm (syn-c37b6a1b4d, input floor), controls identified by curves, not truth.
- Sharing: never supported on the dev candidates (held-out test now, review H); S8 at best 0.5.
- The ablation switches are tested for validity only; their held-out effects are measured by the orchestrator after the lock.

## 10. Changes since the version that ran in the tournament (rounds 1-2 ran none of these; round 3 was not yet run)

| # | change | why (review item) | switch |
|---|---|---|---|
| 1 | Wall-clock time guard of the k sweep removed; the sweep is bounded by its deterministic candidate list | fits must not depend on time or load (batch 1, item 1) | - |
| 2 | supports(sid, kind) False for kinds without training events, with calibrated gain 0, or without a read-in (current gain gamma = 0, edge gain 0); per-kind support / gain / calibrated flag in info()["events"] | no silent "no effect" predictions (batch 1, item 2) | - |
| 3 | Intervention-calibrated kick read-in (microscopically propagated kick) implemented, measured, NOT adopted (config kick_readin, off) | recommended read-in from intervention data (batch 1, item 3); mixed dev effect with two new large failures | - (config) |
| 4 | Two pooled random trajectory splits for the k sweep | seed stability (batch 1, item 4; batch 2, D) | fold_repeats |
| 5 | Tolerance max(0.1 e*, 0.005) without the SE term (the tournament version used max(0.1 e*, 0.005, SE_k)) | no tolerance that grows with a candidate's variance (D) | nn_dim_rule (-> ks rule) |
| 6 | Cross-nested configuration choice per k (config chosen on one half of the validation units, errors from the other half) | configurations selected on data disjoint from the units comparing k (D) | nested_selection |
| 7 | Cross-fitted reference e* (best k chosen on one half, its error from the other) | added after the dev run of 5 + 6 showed that a noise dip at one large k sets e* (winner's curse): syn-1e61c72597 went from k = 1 to k = 5 | (part of 5) |
| 8 | k >= 2 when the data oscillate under constant input (sustained_oscillation); persistence-floor check reported | dynamics class must reproduce the dominant structure; beat persistence (E) | oscillation_check |
| 9 | k_range from paired one-sided 95 % bounds against the tolerance (was 2 tol / tol / 2) | range width justified by validation uncertainty (G) | - |
| 10 | Non-finite latent states propagate as NaN (ks_core replaced them by 0); latent-box activity on validation rollouts reported | failures must be counted (B) | - |
| 11 | Policy for events on unobserved neurons reported in info() | no silent dropping (C) | - |
| 12 | Sharing test on held-out trajectories (independent and shared fits on the rest) | test on data both models were not fitted on (H) | sharing_test |
| 13 | Notes: event operators and the encoder's delays (off-manifold z after events) | consistency statement (F) | - |
| 14 | Unit test with harness.evaluate_system (v3): R["markov_ok"] and the restart after events; encode() determinism | v3 compatibility (A) | - |

The time-guard switch `time_guard` and the internal-validation `sharing_test` semantics of the tournament version no longer exist.

## 11. Current results (benchmark v3 public evaluator, final code, seed 0; remote runner, `runs/brainir/unit.py`, tag v3b)

Synthetic: fit on train + val, evaluated on test / twin / pool with `train=` passed; references (full-state, input-only,
readout-history, PCA-k, persistence) fitted by harness.fit_references on the same data; verdicts by harness.verdict (v3) with
data/tolerances.json (tau_D 0.092, tau_H 0.234). Real: fit on train, evaluated on val / twin (public A-target interventions).
Per-system files: `runs/brainir/remote/*/runs/brainir/out/v3b/*.json`; table: `uv run python runs/brainir/v3sum.py v3b`.

### 11.1 Synthetic dev suite (48 systems)

| quantity | value |
|---|---|
| Markov checks (R event-free restart + decoy + restart after interventions) | pass on 48 / 48 |
| abstained ("no compact state") | 4: syn-12db9981b8, syn-78aa168dd6 (probable controls), syn-c37b6a1b4d (probable trap: false alarm), syn-d18eff9b51 (k 6 > N/5 = 4: false alarm of the new rule) |
| verdicts | compact causal state discovered 7, partially supported 22, not supported 19 |
| conditions | predictive 33, interventional 15, closed 33, microstate-equivalent 27 (10 untestable) |
| medians | A / A_full 0.958; held-out C 0.603; max(0, upper CI of D) 0.031 (S3 analogue); E 0.0032; k 2 |
| checks | oscillation flag on 12 systems; beats the persistence floor on 46 / 48 (none static); latent box inactive on validation |
| fit time (4 CPUs) | median 156 s, max 244 s |

Against the tournament version's rule (paired, v2 run, same fits otherwise): k differs on 14 of 48 systems; the new rule is better on
A on 6, worse on 7; better on C on 5, worse on 8; E better on 8. Net: neutral on the public data, adopted because the reviews'
requirements (D, E, G) are methodological, not because it scores better.

### 11.2 Seed stability (10 dev systems x seeds 0, 1, 2; tag stabb; small class)

| system | k (s0, s1, s2) new | tournament rule (s0, s1) |
|---|---|---|
| syn-154d77eb23 | 2, 2, 2 | 4, 2 |
| syn-1f16e42a17 | 2, 2, 2 | 3, 2 |
| syn-3296f4ad79 | 2, 2, 4 | 2, 2 |
| syn-44f7fa1051 | 1, 4, 6 | 5, 4 |
| syn-566e16b512 | 1, 1, 2 | 3, 2 |
| syn-6f252b24d5 | 4, 4, 4 | 4, 4 |
| syn-9853fca40a | 1, 1, 1 | 1, 1 |
| syn-c37b6a1b4d (abstained every seed) | 6, 5, 2 | 6, 2 |
| syn-e8bb5a2e46 | 1, 1, 1 | 2, 1 |
| syn-f365aa5a73 | 1, 1, 1 | 2, 1 |

Stable across 3 seeds: 6 / 10 (the 7 systems that varied between 2 seeds under the tournament rule were chosen for their
instability; 4 of them are now stable). With 4 pooled splits (tag stab_rep4, 4 varying systems, before item 7): 1 of 4 became
stable (syn-566e16b512); not adopted (double cost). Fit times of the stability jobs (2 CPUs): median 155 s, max 194 s.

### 11.3 Real public systems (val / twin; v3 predictive rule: below input-only and persistence)

| system | k | A | input-only | readout-hist | abstained | verdict |
|---|---|---|---|---|---|---|
| net1:full | 2 | 0.100 | 0.099 | 0.021 | no | not supported |
| net2:full | 4 | 0.192 | 0.314 | 0.099 | input floor | not supported |
| net3:full | 2 | 0.057 | 0.060 | 0.015 | no | not supported |
| net1:mech:02fa13b8 | 3 | 0.013 | 0.017 | 0.002 | k > N/5 | not supported |
| net1:mech:cce0c6c4 | 2 | 0.083 | 0.114 | 0.043 | k > N/5, input floor | not supported |
| net2:mech:3aa95ab7 | 2 | 0.048 | 0.041 | 0.012 | k > N/5, input floor | not supported |
| net2:mech:3e8f8895 | 2 | 0.139 | 0.139 | 0.043 | k > N/5, input floor | not supported |
| net2:mech:6883ab7b | 2 | 0.038 | 0.069 | 0.002 | k > N/5 | not supported |
| net3:mech:362044b4 | 2 | 1.806 | 0.555 | 0.027 | k > N/5 | not supported (unstable rollout) |
| net3:mech:92614efe | 2 | 0.061 | 0.046 | 0.002 | k > N/5 | not supported |

Markov checks pass on 10 / 10. Fit time (8 CPUs): full circuits 432-661 s, mechanisms 125-209 s.
