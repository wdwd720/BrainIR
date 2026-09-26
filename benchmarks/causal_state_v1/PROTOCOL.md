# Benchmark `causal_state_v1`: PROTOCOL (DRAFT v0, not yet frozen)

Causal state discovery WITH interventions (goal5). A method learns, from passive and interventional experiments, a compact state
z = phi(x_{<=t}, u_{<=t}) with controlled dynamics z+ = f(z, u, a), readout y = g(z, u), an explicit intervention read-in
R(z, a) and a native lift a*(z, delta_z). The benchmark measures whether intervention effects are predicted, whether they are
MEDIATED by z, whether z is closed and microstate-invariant under interventions, whether lifts are valid and mutually consistent,
whether the state generalises to intervention families and targets never seen in fitting, and how efficiently active experiment
design finds it. Everything below is fixed before any method is developed; numbers marked CAL are set by the calibration of section 7
on the development suite only, before any method exists.

Generic interfaces: `docs/PROTOCOL_V2.md` (protocol format, families, system records) and `docs/API.md` (models, methods, designers,
experiment loop). Code: package `brainir_causal` (evaluator `evaluate*.py`, references `refs.py`, harness `harness.py`, loop
`loop.py`, selection `select.py`).

## 1. Levels

| level | data | who sees what | purpose |
|---|---|---|---|
| A development | dev synthetic suite (public data, no truth), real public data, simulation service within the public policy | developers | method development |
| B selection | validation synthetic suite (orchestrator-held data and truth) + real validation sets drawn under the public policy | developers see aggregate scores only | tournament with successive halving (section 10) |
| C confirmation (once, after the method lock) | synthetic confirmation suite and its family-shift, OOD and robustness sets, generated from the committed salt AFTER the lock; real hidden intervention test, family shift and OOD, generated from the salt after the lock | nobody before the lock | the claims |

## 2. Systems

### 2.1 Real (connectome-constrained rate-model simulations)
Ten systems: three full networks and seven candidate mechanisms generated from public evidence by a locked earlier method (three
networks: two independent reconstructions, one of them in two builds). Output sampling dt = 1 ms, default duration 2 s, one input
channel, readout dimension 9-20, observed populations of about 200 units (full) or 3-6 units (mechanisms). Public records:
`public/systems_real_public.json`. Lineage: systems of the two builds of the same reconstruction are NOT independent; mechanisms are
nested in their network. Every real result carries its lineage; real counts are reported by lineage.

### 2.2 Synthetic
25 system types (goal5 section 9) written by an author without access to any method or result (`generator/`, hash-locked), several
variants each, calibrated to generic statistics of public real data (section 6). Tiers: `dev` (2 systems per type, public seed),
`val` (2 per type, seed from the salt, generated before development, held by the orchestrator), `conf` (3 per type, seed from the
salt, generated after the lock). Opaque ids; the type, truth and trap labels stay orchestrator-side.

## 3. Intervention families, splits and targets

Family vocabulary and classification: `docs/PROTOCOL_V2.md` section 2 (`brainir_causal.families.family_of`). Each system has a
split record: `families_train` (the only families development data contain and the service simulates for that system),
`families_heldout` (evaluated at Levels B and C only) and the HIDDEN-ONLY families `comp.seq`, `comp.sim`, `seq.chirp` (never
simulatable in development on any system).

Synthetic ROTATIONS (assigned per system by a seeded balanced permutation within each type; frozen):

| rotation | families_train (plus every obs.* family) |
|---|---|
| R1 | sil.1, pulse.1 |
| R2 | kick.1, act.1, edge.w |
| R3 | pulse.1, param.1, seq.train |
| R4 | kick.1, pulse.1, sil.1, sil.2 |

families_heldout = every family the system supports, minus families_train, minus the hidden-only families. Held-out families are
reported as NEAR shifts (same event kind as a trained family, other arity / magnitude / duration / pattern: e.g. sil.2 after sil.1,
pulse.hi and act.1 after pulse.1) or FAR shifts (an event kind never trained on that system).

Real: families_train = obs.nominal, obs.stim, obs.init, obs.param, obs.wnoise, kick.1, pulse.1, sil.1 on the public targets; held out
= every other family, and the trained families on the HIDDEN targets (target shift).

Targets: systems have public targets (development interventions) and hidden targets (Level B / C only). Synthetic: a seeded half
of the targetable units; real full networks: the public / hidden partition of the probe population. Real MECHANISM systems (3-6
units) keep every member public (a split would leave one to three trainable targets): they have no target-shift test; their held-out
tests are the family shift, the hidden-only families, OOD and robustness.

Magnitudes: the capability record's moderate magnitude m_s per kind; classes below-detection (0.1 m_s), weak (0.3 m_s), moderate
(m_s), strong (3 m_s, where admissible); development ranges cap at the strong class of the trained families except `*.hi`, which
use (1.5-3) x the development maximum.

## 4. Datasets per system (benchmark code `brainir_causal.suites`; content-addressed store)

- PASSIVE set D0: nominal trajectories over 8 parameter draws, stimulus schedules within the public input range, initial-condition
  changes, weight-noise draws.
- REFERENCE INTERVENTION set D1 (the fixed training data every method receives in the main comparison): B_main = 200 intervention
  trajectories (real full networks 120) drawn uniformly over families_train x public targets x magnitude classes x onset times, each
  with its counterfactual TWIN (same parameters, noise, initial state, stimulus; no events).
- public VALIDATION set (development only): 20 % more of the same kinds.
- TEST sets (Levels B and C): in-family (new states, seeds, onset times), target shift (hidden targets), family shift (every held-out
  family, near and far; 8 items per family per system, each with its twin), hidden-only families, OOD (section 4.1), robustness
  (section 4.2); every intervention item has a twin; items are arranged so each (family, target set, magnitude class) occurs at >= 4
  distinct states (needed by the mediation regressions).
- POOLS for microstate equivalence and bisimulation: 600 microstates per system (8 parameter draws x 15 source trajectories x 5
  sample times; each state is a time point of a stored held-out trajectory, so its history is that trajectory's past), plus, for
  synthetic systems, truth-equivalent sets; the futures of every pool state under S = 6 intervention sequences (one per event kind
  the system supports, drawn from its train and held-out families; all states share each sequence's future input) and under no
  intervention, simulated from restarts of the stored microstate. Futures are stored as readouts (and the observed microstate over
  the primary horizon for the no-intervention future).
- LIFT cases: 16 states per system with histories (restartable), requested shifts defined in section 5.7.

Horizons (all systems): short = 2.5 %, medium = 12.5 % (PRIMARY), long = 50 % of the system's default duration (real: 50 / 250 /
1000 ms). Onsets leave at least the long horizon.

### 4.1 OOD families (Level C; goal5 section 74)
input amplitude outside the public range (0.5x and 1.5x its bounds); parameter spread (protocol field params_spread = 1.5 with
hidden-range parameter draws);
unseen intervention timing (onsets during strong transients / opposite phase); unseen compositions (hidden-only families); altered
initial conditions (off-pool microstates); temporal sampling shift (observations at 2x dt with the model given the new dt).

### 4.2 Robustness conditions (Level C; goal5 section 75)
parameter noise (params_spread 1.5 and 2.0 with hidden-range draws), weight noise (sd 0.05 and 0.1), trajectory (process) noise
(protocol field process_noise; only where a system's capability supports it: synthetic systems), observation noise (sd 0.05 and 0.1
of obs_scale), intervention amplitude noise (+-20 % jitter the model is not told), timing jitter (+-2 samples the model is not
told).

## 5. Metrics (families kept separate; never collapsed)

Isolation and leakage rules: every rollout / readout / lift / effect call runs on a FRESH copy of
the fitted model (pickle snapshot taken before the first encode); encoders receive x and u up to the encoding time only (never y,
never the future); future interventions are given as events; normalisers come from public training data only (readout scale =
pooled training variance, computed without finite blow-ups: trajectories whose max |x| or |y| exceeds 100x the training median);
per-item errors are capped (10x the item's denominator); non-finite predictions count as the cap and are reported, never dropped.

### 5.1 Intervention effect prediction (goal5 sections 44-46)
For a test intervention item i with onset t_i and twin i': true effect e_i(t) = y_i(t) - y_i'(t); the model encodes z_i from the
common history before t_i and predicts y-hat_i (rollout with the events) and y-hat_i' (without); predicted effect e-hat_i. With the
frozen floor f_s = 0.05 x the pooled training sd of y (per system):

    EE_s(h) = sum_i min(num_i, 10 den_i) / sum_i den_i,   num_i = sum_{t in (t_i, t_i+h]} ||e-hat_i(t) - e_i(t)||^2,
                                                          den_i = max(sum_t ||e_i(t)||^2, n_t n_y f_s^2)

(predicting no effect gives EE <= 1). Abstained items are scored as the no-effect prediction in EE and counted in coverage (5.9).
Also: absolute effect RMSE (readout units); sign accuracy of the time-integrated effect per readout dimension with |integral| above
the floor; post-intervention trajectory NMSE; per family, per shift type (in-family / target / near / far / hidden-only), per
magnitude class and per DETECTABILITY class of ES_i = RMS(e_i) / f_s: below (< 1), weak [1, 3), moderate [3, 10), strong (>= 10).

### 5.2 Observational prediction
Passive multi-horizon readout NMSE after encoding at 4 onset times per held-out passive trajectory (capped at 10 per window).

### 5.3 State mediation score (goal5 section 13)
Cross-fitted by resampling group (2 folds x 5 repeats; per-row errors averaged over the repeats) on the test intervention items at
the primary horizon (5 lags); readouts in units of the public pooled training sd. Model A = the model's own prediction (for an
abstained item its no-intervention prediction). Model B = Model A + a learned correction from EXTRA features:
- the residual microstate x_res at onset: the top-q public PCs of x (q = min(10, N_obs); components with near-zero public variance
  dropped) minus their within-fold ridge prediction from (z, u at onset), divided by ONE common scale (the spread of the original
  components), never re-standardised per column;
- the intervention IDENTITY, decomposed additively: per action key (event kind x unit or edge) its presence and signed dose, plus
  family, magnitude class, duration, event count and onset time (a one-hot of whole composite interventions carries no sign and
  would not attribute a target-dependent read-in error to identity).
Correction learner: ridge on [extra ; extra x lag] + min(256, max(16, n/8)) random Fourier features, penalty by an inner split by
group. CAPACITY CONTROL: arm A receives the WHOLE block of extra-feature columns (linear, lag interactions and random features)
built from the same extra features with the items permuted within each fold (a permutation-matched null), and both arms get an
unpenalised per-lag bias correction, so a gain measures information in the extra features, not added capacity or a constant bias. SMS = 1 - SSE_B / SSE_A (error floor 0.01, clipped at -1),
95 % CI by resampling groups. Reported: SMS with {x_res, ID} (primary), {x_res}, {ID}, and SMS_raw (no bias correction in arm A).
SMS near 0: the effect is captured through z and the model's read-in; large SMS: z or its read-in misses causal information
(through x_res: missing state; through ID: a read-in that does not carry the intervention's effect).

### 5.4 Interventional closure (goal5 section 31)
Evaluator-fitted comparison on the same items: error(z, u, a) vs error(z, u, a, x_res) for (i) y at the end of the primary horizon
(the verdict quantity) and (ii) z_future = phi(true future history) at 2 lags (descriptive), with the rules of 5.3 (residual
computed inside each fold; permutation-matched capacity; single-time targets, so an intercept in both arms instead of a per-lag
bias) and a base (z, u at onset, mean and last future input, compact intervention descriptors: event kinds, arity, signed
log-dose, event count, duration, onset) fitted WITHOUT shrinkage while it has <= 1 column per 4 rows; the identity features of 5.3
enter both arms, penalised. ICG = fractional error reduction from adding x_res (linear and random-feature versions; the VERDICT uses
the random-feature ICG_y at the primary horizon); 95 % CIs. Also the
model's own interventional closure gap: its latent a short horizon after the onset (rollout under the events) against the encoding
of the intervened history at that time, relative to the distance between the intervened and twin encodings.

### 5.5 Microstate equivalence under intervention (goal5 section 32)
On the pool: for each state its model latent (whitened by the covariance of the model's encodings of training data; eigenvalue floor
1e-8 x max). Candidate pairs are cross-trajectory pairs within one parameter draw. MATCHED pairs = the M = 20 closest candidate pairs
in latent distance (a FIXED count, so matches tighten as the pool grows; a fixed quantile would not); RANDOM pairs = all candidate
pairs. For each sequence (the 6 intervention sequences and the no-intervention future): the ratio of the mean future readout
divergence (primary horizon, same sequence) of matched pairs to that of random pairs; MEV = the mean of the per-sequence ratios (so
one large-effect sequence cannot dominate); 95 % CI by resampling pool source trajectories (the matched set is recomputed in every
resample). UNTESTABLE when matched pairs are not close (median matched / median random latent distance > 0.2) or random pairs
diverge less than 2x the numerical floor. Synthetic systems, descriptive: the TRUTH-EQUIVALENT comparison (the generator's
equivalent states, excluded from the pairing above: their future divergence under the same sequences) and the TRUTH-MATCHED
comparison (pairs of main-pool states matched on the TRUE causal state, the same M rule). Also: observation-matched pairs, per
sequence, and the old fixed-quantile rule as a sensitivity variant.

### 5.6 Interventional bisimulation-like test (goal5 section 33) — descriptive
For latent-neighbour pairs: (1) immediate readout difference, (2) difference of responses under each intervention class, (3) latent
distance after one primary horizon (re-encoded from the true futures) relative to the initial latent distance; curves against the
initial latent distance. No formal bisimulation claim.

### 5.7 Native lift and multiple lifts (goal5 sections 15-16, 72)
For each lift case c: requested shifts delta_z = alpha v in the model's whitened latent coordinates, v in {the model's first two
principal latent directions, one random unit direction}, alpha in {0.5, 1.0} latent sd. The model returns up to 3 DISTINCT lifts
(events allowed by the system's capability; lifts may use any supported kind, trained or not). For each lift the evaluator simulates
the lifted world and the twin from the exact microstate; at the completion sample j (one sample after the last instantaneous event,
the end of the last finite event) it measures:
- latent miss: ||(phi(lifted history) - phi(twin history)) - delta_z|| / ||delta_z|| (whitened);
- cost: sum over events of |amplitude| x duration (kicks: |delta| x dt), and the number of targets;
- future consistency (EFFECT form, the scored quantity): NMSE of the model's predicted lifted effect (its rollout from
  phi(twin history) + delta_z minus its rollout from phi(twin history)) against the simulated lifted effect (lifted - twin) over the
  primary horizon after j; the literal form (do-rollout against the lifted simulation) is reported beside it;
- multiple-lift consistency: for distinct lifts of one request, the RMS divergence of their simulated futures over a common window
  (from the latest completion sample) divided by the mean RMS lifted effect; reported raw and ADJUSTED = the divergence that the
  model's own dynamics cannot explain from the lifts' different achieved shifts (divergence of the simulated futures minus the
  divergence of the model's rollouts from the achieved shifts); the pooled-regression intercept is a secondary number (it is
  confounded by the request magnitude); lifts whose achieved microstate changes have cosine > 0.99 count as one realisation; no pair
  of distinct lifts = UNTESTABLE (never a perfect score);
- success per REQUEST: at least one lift with miss <= 0.5 and future-consistency NMSE <= 0.5; persistent events, truth events and
  events before the case time are refused as lifts (counted as failed);
- uncertainty: the model's reported uncertainty of its lift against the realised miss;
- synthetic truth: the spread of the TRUE causal-state shift across the distinct lifts of one request.
Lifting is required (goal5 section 15): a model without `lift` is scored as failing every lift case.

### 5.8 Composition (goal5 section 30)
EE on `comp.seq` (a then b) and `comp.sim` (a and b overlapping), and the model's composition consistency (predicted effect of a+b vs
its predicted effects of a and b alone, against the true non-additivity) — descriptive.

### 5.9 Abstention and calibration (goal5 sections 45-47, 76)
coverage = fraction of test items predicted (not abstained), per detectability class and OOD category; accuracy conditional on
prediction (EE over covered items); FALSE-CONFIDENCE rate = fraction of covered items with detectable true effect (ES >= 1) whose
EE_i > 1 (worse than predicting no effect) or with a confidently wrong sign; calibration: empirical coverage of the model's 90 %
predictive intervals (y_sd) per horizon and |coverage - 0.9|; Brier scores of p_detectable (ES >= 1) and p_sign_pos; a model that
reports no uncertainty is treated as confident everywhere (intervals of zero width).

### 5.10 Dimension (goal5 sections 35-36)
The selected k, the reported plausible range, and at Level C the distribution of k over 5 refits on bootstrap resamples of the
training INTERVENTIONS (passive data kept): STABLE if the modal k occurs in >= 4 of 5 and every k lies in the reported range;
otherwise "dimension unresolved: min-max". Synthetic truth: k = k_true; k_true within the range. Compact: k <= max(1, N_obs / 5)
(full and synthetic systems; mechanisms are judged on the other conditions).

### 5.11 Representation stability (goal5 section 37)
Across 3 fit seeds (Level B) / 5 seeds and the bootstrap refits (Level C): the smaller of the two cross-prediction R^2 directions of
latents on the same test data (linear map fitted on validation data), mean padded canonical correlation, Procrustes residual after
the affine map, predicted-effect disagreement relative to the effect size, vector-field similarity (the mapped flow of one model
against the other's on shared states).

### 5.12 OOD, robustness and validity (goal5 sections 74-75)
EE and NMSE per OOD category and robustness condition relative to in-distribution; the AUC of the model's validity score for
detecting items with EE_i > 1; the ratio of mean predicted sd (OOD / in-distribution) against the ratio of realised errors.

### 5.13 Leave-one-intervention-out (goal5 section 58)
Level C (and finalists at Level B): for each trained family of a system, refit without it and score EE on its test items; the gap
to the full fit.

### 5.14 Leave-one-implementation-out and shared dynamics (goal5 sections 55-59)
Synthetic implementation groups: shared fit on all but one implementation, encoder / read-in adaptation (config adapt_from) on 25 %
of the held-out implementation's training data, against a from-scratch fit on the same data; scored by EE on unseen interventions of
the held-out implementation. Sharing models A (independent), B (shared dynamics, separate encoders / read-ins), C (partially
shared), D (shared latent causal model) compared on held-out intervention EE, SMS, parameters and transfer. HARD GATE (goal5 section
57): cross-mechanism or cross-connectome sharing is interpreted only for systems whose within-system verdict is "causal state
supported"; otherwise the report says "prerequisite failed".

### 5.15 Capacity and compute (goal5 section 19)
parameters of encoder, transition, read-in and readout (model.info), training FLOPs as reported, CPU and GPU seconds (measured by
the harness), simulator calls, history length. Capacity is reported next to every comparison.

### 5.16 Synthetic truth (confirmation suite)
latent recovery min(R^2 of z_true from z, R^2 of z from z_true) (cross-fitted, linear + random features); z_obs capture on trap
systems (R^2 of the exposed causal variable from z); k = k_true; correct "no compact causal state" on types 20 / 21; true read-in
accuracy (the model's read-in against true_latent_effect mapped into model coordinates).

### 5.17 Active experiment design (goal5 sections 24-29, 60, 73)
For each system and designer (the method's own; `random`, `uniform`, `magnitude_sweep`, `greedy_error`, `structural`, `passive`,
`fixed`), the method's learner is run in the experiment loop from D0 with checkpoints after 10, 25, 50, 100 and 200 intervention
experiments (real full networks: 10, 25, 50, 100), 3 loop seeds. Quality at each checkpoint: EE (primary horizon, all test
families), SMS, k correctness (synthetic), lift success. Costs: experiments, simulator calls, simulated seconds, unique targets,
magnitude budget, CPU / GPU s. ACTIVE DESIGN SUCCEEDS iff (i) at a fixed budget its EE is lower than random's AND fixed's (paired CI
over systems below 0 at >= 2 of the 5 budgets, none significantly worse), or (ii) the budget it needs to reach the EE random
reaches at 100 experiments is significantly smaller (paired bootstrap of the ratio, upper CI < 1).

## 6. Calibration to the real systems (goal5 section 8)
`public/calibration_targets.json` (from public real data; `brainir_causal.calibstats`). The dev suite's pooled statistics must fall
in the recommended ranges of the statistics marked required; the check is recorded (acceptance criterion 11) and repeated on the
validation and confirmation suites.

## 7. Pre-registered calibration of the tolerances (dev suite only, before any method)
References (section 8) fitted on D0 + D1 of every dev system; the tolerances:
- delta_A (margin of "meaningfully better than no effect") = max(0.1, 90th percentile over systems of the upper CI of the true-state
  reference's EE minus its point EE) [CAL];
- delta_C (non-inferiority margin to the full-state upper bound) = max(0.05, 90th percentile over systems of (EE_truestate -
  EE_fullstate)) [CAL];
- tau_SMS = 90th percentile of the upper CI of the true-state reference's SMS [CAL]; POWER RULE: SMS binds only if the true-state
  reference's pass rate exceeds the pass rate of EACH null (the observational-shortcut reference on the trap types, and random-k) by
  at least 20 percentage points; if a null cannot be computed (no trap system in the calibration set), the criterion does not bind;
- tau_ICG = 90th percentile of the upper CI of the true-state reference's ICG_y [CAL], with the same power rule;
- tau_MEV = 90th percentile of the upper CI of the true-state reference's MEV where testable [CAL];
- tau_FC (false-confidence ceiling) = 0.2 [fixed];
- delta_H (held-out family margin) = max(0.1, 90th percentile of the true-state reference's (EE_heldout - EE_infamily)) [CAL].
Each with a 95 % CI by resampling calibration systems; the reference verdict distributions and power tables are recorded in
`calibration.json` (locked); only the values go to `public/tolerances.json`. Real verdicts are conditional on this synthetic
calibration.

## 8. References and baselines
Benchmark references (code `brainir_causal.refs`, trained on D0 + D1 like a method): NO-EFFECT (e-hat = 0); TRUE-STATE (synthetic:
encoder = the true causal state, a generic controlled learner for dynamics, read-in and readout); FULL-STATE (encoder = the observed
microstate with two causal exponential traces of it (time constants 1/4 and 1 x the short horizon); the same learner with per-unit
intervention inputs; the predictability anchor of goal5 section 23); OBS-SHORTCUT (synthetic trap types: encoder = z_obs); RANDOM-k
and PCA-k (k = the method's k); ID-SHORTCUT (y future = h(intervention identity, stimulus, readout history), no state; goal5
section 22). The shared learner (one design for every state-based reference; `refs.py` docstring): read-in through a probe of the
state plus a correction fitted on training kicks; per-unit intervention descriptors; half of every training batch from
intervention periods; one-step then short unrolled training; intervention kinds never seen in training are declared unsupported
(abstention) with their untrained weights zeroed. Tournament BASELINES (goal5 section 21) are methods like any other, built in the
clean room on public data; the earlier locked state-discovery method (BrainIR State v1) runs unchanged as a frozen baseline. The
full-state upper bound of the verdict is the better (lower EE on the validation split) of FULL-STATE and the best full-state
baseline, fixed at Level B. The references' k is fixed, so their dimension criterion (F) counts as stable in the calibration's
reference verdicts.

## 9. Verdicts (per system; goal5 section 71)
HELD-OUT items = the near-shift, far-shift and hidden-only items (the family shift); the B subset adds the target-shift items.
- A intervention prediction: the upper CI of EE (primary horizon, all test items, abstentions as no effect) < 1 - delta_A.
- B shortcut: the upper CI of the paired difference EE_method - EE_idshortcut < 0 on the B subset.
- C full-state: the upper CI of EE_method - EE_fullbound <= delta_C.
- D mediation: upper CI of SMS <= tau_SMS (if the power rule admits it; else reported, not binding).
- E closure / microstate: upper CI of ICG_y <= tau_ICG (power rule) and MEV upper CI <= tau_MEV (untestable -> untested).
- F dimension: compact (5.10) and stable; mechanism systems (no compression criterion) are judged on stability only.
- G false confidence: rate <= tau_FC (passes when no covered item has a detectable effect).
- H family generalisation: the upper CI of EE on held-out items < 1 - delta_A, and the point estimate EE_heldout - EE_infamily <=
  delta_H.
Rules: a criterion that is not binding (power rule) is excluded from both SUPPORTED and PARTIAL; a criterion whose inputs are
missing blocks SUPPORTED. Verdicts: CAUSAL STATE SUPPORTED (every binding criterion A-H holds); CAUSAL STATE SUPPORTED (E UNTESTED)
(its own category, never merged; counts as at least PARTIAL for the real part of the conclusion, not as SUPPORTED); PARTIALLY
SUPPORTED (A holds and at least one of D, E, H); UNSUPPORTED (otherwise); a method's declared "no compact causal state" is recorded
as such (correct on types 20 / 21, a false alarm elsewhere). Lift success (5.7) is required for the strongest claim (goal5 section
93) and reported beside.

Overall conclusion (goal5 section 92.51), from the Level C results only. P_m = the fraction of compressible confirmation systems
whose verdict is CAUSAL STATE SUPPORTED for the locked method; P_t = the same for the TRUE-STATE reference fitted on the same
systems and data (post lock; a benchmark reference, not a method); CIs by the type-stratified system bootstrap, P_m - P_t paired by
system.
- Synthetic part SUPPORTED: lower CI of P_m >= 0.5, lower CI of (P_m - P_t) >= -0.2, and "no compact causal state" declared on at
  least 2/3 of the non-compressible controls (types 20, 21). PARTIAL: not SUPPORTED, and the lower CI of P_m >= 0.2 or at least
  half of the compressible systems reach PARTIALLY SUPPORTED or better. Otherwise UNSUPPORTED.
- Real part SUPPORTED: every full network of every lineage is CAUSAL STATE SUPPORTED. PARTIAL: at least one full network is
  SUPPORTED, or every full network is at least PARTIALLY SUPPORTED. Otherwise UNSUPPORTED. Mechanism systems are reported beside.
- Overall: "compact causal state supported" iff both parts are SUPPORTED; "partially supported" iff at least one part is at least
  PARTIAL; otherwise "unsupported". If P_t itself is below 0.5, the report states that the criteria are not attainable even with the
  true causal state and a generic learner, and the synthetic part cannot be SUPPORTED.
- Reported with goal5 section 94's diagnosis: full state predicts but compact fails -> abstraction problem; full state fails ->
  simulator / data / excitation problem; random design as good as active -> design unnecessary; a simple controlled linear baseline
  wins -> use it; synthetic works, real fails -> distribution / model mismatch; effects need a high-dimensional state -> report
  high-dimensional causal dynamics; read-ins not invariant across states -> the causal-state definition needs revision.

## 10. Method selection (Level B; goal5 sections 66-68)
Successive halving on the validation suite: pilot (a pre-registered subset of 25 systems, one per type, plus 3 real mechanisms) ->
keep the better half -> medium (all 50 validation systems + all real mechanisms) -> finalists (top 3 + the best baseline) -> full
public confirmation (all validation systems, all real systems, 3 seeds, active-design curves). Rule (lexicographic with tolerance
bands, no single scalar): ELIGIBLE (goal5 section 68 gates 1-3) = on the systems of the round, the candidate's pass rates of A
(intervention prediction), D (mediation) and E (closure / microstate) are each at least half of the TRUE-STATE reference's pass rate
on the same synthetic systems (and A at least half of the full-state bound's pass rate on the real systems of the round); among
eligible candidates, rank by (4) compression (fraction of systems compact and, synthetic, k = k_true), then (5) observational
prediction, (6) experiment efficiency (5.17), (7) simplicity (parameters), (8) compute; a candidate is "tied" with the leader on a
criterion when their paired system-bootstrap CI includes 0, and ties pass to the next criterion. Before any tie-break, candidates
are ordered by the gate metrics themselves (mean EE, then SMS, then ICG), which also orders them when none is eligible (reported as
"no candidate meets the gates"). A method that predicts passive dynamics well but fails the gates cannot win.

## 11. Statistics (goal5 section 77)
Units: synthetic = system instance (paired across methods on the same instances; CIs by resampling systems, stratified by type);
within a system = the test ITEM (an intervention trajectory with its twin; items sharing a start state are resampled together);
never time steps. Real: per system; the two builds of one reconstruction are one lineage; pooling across networks is descriptive.
CIs: percentile bootstrap, 2,000 resamples; paired differences on identical units; p = (1 + count) / (1 + B). PRIMARY FAMILY (Holm,
alpha 0.05): the locked method against the strongest baseline (fixed at Level B) on A, B, C, D, H over the confirmation suite (paired
by system) and on the three real full networks (paired by item): 5 + 15 one-sided tests. Non-inferiority margins: delta_C for C; 0.2 x
the baseline's value for EE comparisons. Everything else is descriptive. Minimum detectable effects for the active-design comparison
are computed on the dev suite (section 7) and reported.

## 12. Lock and evaluation counts
BENCHMARK_LOCK.json hashes this protocol, the generator, `brainir_causal` evaluation code, public records, calibration and
tolerances, and the salt commitment (sha256 of the secret salt; the salt itself stays offline until after Level C). The confirmation
suite, the real hidden sets and every Level C artefact are generated after the method lock from the salt; each hidden run is logged
(START before, DONE after) in the orchestrator's evaluation log. Any change to a hashed file after the freeze is a new benchmark
version with a logged reason.

## 13. Public files (may enter a clean room)
This protocol, `docs/PROTOCOL_V2.md`, `docs/API.md`, `public/systems_*_public.json` (without hidden targets), public data (dev
synthetic data without truth; real public data), `public/calibration_targets.json`, `public/tolerances.json`, the evaluator and
harness code (no truth inside), the public-policy table. Never: `generator/`, `hidden/`, calibration internals, validation /
confirmation data or truth, the salt.
