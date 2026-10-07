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
| A development | dev synthetic suite (public data, no truth), real public data, simulation service within the public policy (trajectories computed on the reference platform of section 4, bit-identical to the benchmark's own records; restarts from served or public trajectories) | developers | method development |
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
  changes (each a RESTART at 25-90 % of one of the 8 nominal trajectories, with its parameter draw, weight noise and spread, under a
  nominal stimulus schedule of its own), weight-noise draws.
- NO EXPLICIT INITIAL STATES: an explicit initial state (r0 'state') is bit-identical to a kick at t = 0, so it is not a development
  protocol on any system (capability init.state = false; the public policy refuses it; no planned set uses it; the engines accept it
  for orchestrator use only). Initial-condition variability comes only from restarts of NOMINAL passive trajectories of the same
  system and draw: in D0, the public validation set, the passive test trajectories (each restarts from the nominal test trajectory
  two positions before it) and the pools (the first source of every pool draw is a nominal trajectory; the draw's 'init' sources
  restart from it). A restart concatenated with its source is a trajectory from rest under a stimulus schedule. Dependent
  trajectories are simulated after their sources, have no spare seeds, and are dropped (counted) when their source is dropped.
- REFERENCE INTERVENTION set D1 (the fixed training data every method receives in the main comparison): B_main = 200 intervention
  trajectories (real full networks 120) drawn uniformly over families_train x public targets x magnitude classes x onset times, each
  with its counterfactual TWIN (same parameters, noise, initial condition, stimulus; no events).
- public VALIDATION set (development only): 20 % more of the same kinds.
- TEST sets (Levels B and C): in-family (new states, seeds, onset times), target shift (hidden targets), family shift (every held-out
  family, near and far; 8 items per family per system, each with its twin), hidden-only families, OOD (section 4.1), robustness
  (section 4.2); every intervention item has a twin; items are arranged so each (family, target set, magnitude class) occurs at >= 4
  distinct states (needed by the mediation regressions).
- ONSET CHECK: every intervention item equals its twin in x and y at every sample up to and including its onset sample (the earliest
  of its simulated and told events; the sample at an event's time is the pre-event state); a violation aborts that system's build,
  and the stored items are re-checked before the freeze.
- MAGNITUDE CLASSES OF KICKS are those of the REALIZED size where the simulator reports it (a kick is clipped at the floor): an
  unclipped item keeps its planned class; a clipped item takes the class nearest on a log scale to the median realized |kick| / m_s
  over its kicked units (a planned 'hi' item stays 'hi' while that median is inside hi_range); an item whose simulator reports only
  that its kicks were clipped keeps the planned class and is flagged. Orchestrator-held parts record the requested class and the
  realized sizes; public rows carry no new field. Build summaries report the clipped fraction per family.
- Items with a constant future (a mechanism silent at a low input level, a kick clipped to zero) are kept: test items are never
  selected by their outcome, and both metrics stay defined (EE's floor denominator, the observational NMSE's training sd); builds
  count them.
- PUBLIC CAPABILITY RECORDS carry system-wide values only: per-unit admissible ranges become the system's [min, max], per-unit
  process-noise scales their median, settable units 'observed'; a public record whose capability holds a per-unit numeric list is
  refused (the per-unit public fields are the observed, readout, target, member and edge lists and the public graph).
- POOLS for microstate equivalence and bisimulation: 600 microstates per system (8 parameter draws x 15 source trajectories x 5
  sample times; each state is a time point of a stored held-out trajectory, so its history is that trajectory's past), plus, for
  synthetic systems, truth-equivalent sets; the futures of every pool state under S = 6 intervention sequences (one per event kind
  the system supports, drawn from its train and held-out families; all states share each sequence's future input) and under no
  intervention, simulated from restarts of the stored microstate. Futures are stored as readouts (and the observed microstate over
  the primary horizon for the no-intervention future). A pool state may be sampled while an intervention of its source trajectory
  is active; its restart future does not continue that event (legitimate for a microstate test; the model encodes an intervened
  history). Public pools (dev tier, real public data) use only the system's trained families. Synthetic evaluation pools also start
  a share of their source trajectories from the generator's own pool states, and add 2 truth-equivalent microstates for each of 20
  pool states; both are FULL microstates (internal variables included), which no development protocol can set, so these
  orchestrator-held simulations start from a one-sample STATE CARRIER record holding the microstate
  and an ordinary restart (content-addressed key over system, time and state); public parts never contain carriers.
- LIFT cases: 16 states per system with histories (restartable), requested shifts defined in section 5.7.
- SEEDS: the dev tier and the real public data use public seeds; the val and conf tiers use 128-bit seeds derived from the salt
  (HMAC), and every protocol stream of an orchestrator-held set (val / conf public parts, non-public pool sequences, the real Level B
  and hidden sets) is drawn from a salted stream, so it cannot be regenerated from public code; parameter seeds of sets that must obey
  the public policy stay in the public range. The public parameter-seed range [0, 10^9) and the development dt (the nominal dt) are
  the benchmark's, imposed on every system whatever a generator declares.
- REFERENCE PLATFORM: every generator computation of an official build (planning: content hashes, capability records, pool states;
  simulation) and every trajectory the simulation service returns is computed on Linux with the pinned numerical stack (the Modal
  containers and the pinned local image agree bit for bit; the Windows development host does not, so it plans and simulates only
  tests); a build refuses a plan whose system hash differs from the building process's, and the store publisher compares every
  re-published record array by array.
- Every dataset record comes from a successful simulation with finite x and y: failed or non-finite simulations are refused at
  build time, counted per family in the build summary and replaced under a logged rule (a new seed from the same stream). Records
  carry the host fingerprint (CPU flags, numerical library versions and pins); real-system records are produced only on the pinned,
  host-gated path, synthetic simulations through the benchmark's context are host-gated the same way, and a sample of stored keys is
  replayed bit for bit before the freeze. Development protocols use the nominal dt.

Horizons (all systems): short = 2.5 %, medium = 12.5 % (PRIMARY), long = 50 % of the system's default duration (real: 50 / 250 /
1000 ms). Onsets leave at least the long horizon.

### 4.1 OOD families (Level C; goal5 section 74)
input amplitude outside the public range (0.5x and 1.5x its bounds); parameter spread (protocol field params_spread = 1.5 with
hidden-range parameter draws);
unseen intervention timing (onsets during strong transients / opposite phase); unseen compositions (hidden-only families); altered
initial conditions: the full microstate (a state carrier) of a nominal trajectory of the same parameter draw at 30-80 % of its
duration, with half of the observed units (random choice) displaced by twice the development kick maximum (random signs) and clipped
to each unit's admissible range (synthetic: the generator's per-unit range; real: rates in [0, the engine's maximum initial rate]);
off-pool, and never an explicit initial state; temporal sampling shift (the trajectory is simulated at the nominal dt and EVERY SECOND
sample is kept, with events on the 2 dt grid, so only the sampling changes; the model is given the new dt; development protocols use
the nominal dt only, so this shift is never seen in development).

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
VERDICT EE (review E, M1): CLASS-BALANCED = the unweighted mean, over the magnitude classes present among the items (below, weak,
moderate, strong, hi for the *.hi families, and "na" for kinds without a magnitude, e.g. silencing), of the per-class ratio of sums
above. The pooled ratio of sums is reported beside it (it is dominated by the strong items, whose effect energy scales with the
square of the magnitude).

CLASS MERGING (review E, N2 / N-new-4): a class carried by fewer than 3 FAMILIES with signal (families whose summed denominator in
the class is positive) is merged into its neighbour toward moderate: below -> weak -> moderate, hi -> strong -> moderate,
na -> moderate. A class whose neighbours are absent joins the class with the most families. This repeats until every class has at
least 3 families or only one class is left. So a class is never dropped and never missing from a jackknife replicate, and the errors
on a class without signal stay charged in its neighbour's ratio.

UNCERTAINTY (review E, N2 / M2 / N-new-4): delete-one-FAMILY jackknife, ALWAYS at the family level: cells are nested in families,
and there is no fallback to cells. Only a design with no family labels at all treats each cell as its own family, and it is
recorded. The degrees of freedom are Bell-McCaffrey degrees of freedom: a random-effect-per-family working model, family leverage
D_fk / D_k with the CR3-type adjustment. They are F - 1 for equal family weights and drop toward 1 when a class rests on one dominant
family (e.g. the high-magnitude *.hi family). With fewer than 4 families carrying signal there is NO interval ("too few families"),
and the criterion's input is missing.
- A single class-balanced EE: on the log scale, exp(log EE +- t se_log).
- A paired difference of two class-balanced EEs on the same items: on the linear scale, with the same leave-one-family-out sets.
  Only its UPPER bound is used by any rule (criteria B and C, primary hypotheses H2, H3, H6). The lower bound is descriptive (review
  E, N-new-7).
- The same interval is used for every class-balanced quantity (A, B, C, H and the primary family).

Simulation (review E's model: 4-20 families x 2 cells x 4 states, one or two *.hi families, family and cell log-sd 0.3-0.6, item
errors t3 on the log scale capped at 10x; 27 settings x 1,000 replications):
- 95 % coverage 0.945-0.991;
- P(upper bound < truth) 0.008-0.051, mean 0.027. The largest values (0.05) come with t3 item errors at 7 and 20 families: rare
  capped items that a sample may miss.
- The family jackknife with Satterthwaite df and a cell fallback it replaces gave 0.029-0.293 (0.17-0.29 below 6 families).
- Interval widths: equal to the old ones at 12-20 families (x1.00-1.09); x1.1-2.4 at 6-10 families; uninformative at 4-5 families
  when one family dominates a class.
- Paired differences: P(upper bound < truth) <= 0.002; P(lower bound > truth) 0.017-0.075; coverage 0.925-0.983 (old: 0.69-0.91).

The family count, the degrees of freedom and the class merges are reported with every CI and every verdict. Items whose TRUE future
is non-finite (a failed simulation; such records are refused at build time) are dropped and counted.

LIMITATION (review E, N-new-6): the merges depend on how many families carry each class, so the class weights of the class-balanced
EE differ between systems. Per-system verdicts are unaffected. A suite mean (H1, H5) averages statistics with different class
structures, and the report gives the merge pattern of every system and its distribution over the suite.

Also: absolute effect RMSE (readout units); sign accuracy of the time-integrated effect per readout dimension with |integral| above
the floor; post-intervention trajectory NMSE; per family, per shift type (in-family / target / near / far / hidden-only), per
magnitude class and per DETECTABILITY class of ES_i = RMS(e_i) / f_s: below (< 1), weak [1, 3), moderate [3, 10), strong (>= 10).
Horizons are taken per item with the item's own dt.

### 5.2 Observational prediction
Passive multi-horizon readout NMSE after encoding at 4 onset times per held-out passive trajectory (capped at 10 per window).

### 5.3 State mediation score (goal5 section 13)
Cross-fitted with ITEM folds stratified by identity cell (2 folds: each cell's states are split across the folds, so a cell's identity
is seen in training; whole-cell folds would leave every test identity unseen and hide read-in errors, as the early implementation
showed: SMS 0.03 instead of 0.75 for a gross read-in error); per-row errors averaged over 20 cross-fitting seeds; on the verdict
test items (section 9)
at the primary horizon (5 lags, per item with its own dt); readouts in units of the public pooled training sd. Model A = the model's
own prediction (for an abstained item its no-intervention prediction). Model B = Model A + a learned correction from EXTRA features:
- the residual microstate x_res at onset: the top-q public PCs of x (q = min(10, N_obs); components with near-zero public variance
  dropped) minus their ridge prediction from (z, u at onset), where the (z, u) -> PC map is fitted on the OUTER training fold only and
  the SAME map is applied to the fold's training and test rows (review E, B2); divided by ONE common scale (the public spread of the
  original components), never re-standardised per column;
- the intervention IDENTITY, decomposed additively: per action key (event kind x unit or edge) its presence and signed dose, plus
  family, magnitude class, duration, event count and onset time (a one-hot of whole composite interventions carries no sign and
  would not attribute a target-dependent read-in error to identity). Identity columns are built INSIDE each fold; columns whose
  training-fold spread is below a relative tolerance are dropped in both the training and the test rows; no constant is added to a
  standard deviation used as a divisor (review E, B1).
Correction learner: ridge on [extra ; extra x lag] + min(256, max(16, n/8)) random Fourier features, penalty by an inner split by
cell. CAPACITY CONTROL: arm A receives the WHOLE block of extra-feature columns (linear, lag interactions and random features)
built from the same extra features with the items permuted within each fold (a permutation-matched null), and both arms get an
unpenalised per-lag bias correction, so a gain measures information in the extra features, not added capacity or a constant bias.
SMS = 1 - SSE_B / SSE_A (error floor 0.01, clipped at -1); 95 % CI by resampling identity cells, each replicate drawing one of the
20 cross-fitting seeds, so the CI includes the cross-fitting variability (the between-seed sd is reported). UNUSABLE items are never silently dropped. An item is unusable when its call failed or its prediction over the primary horizon is
non-finite or wrongly shaped, so there is no Model A to correct.
- When more than 1 % of the verdict items are unusable, SMS (and ICG) FAIL and are charged the worst admissible value, +1. 1 % is
  below one identity cell for every verdict item set; the earlier 5 % allowance could hide one family's read-in error (review E,
  N3). Otherwise their count is reported next to the score.
- LATENT-MISSING items (the prediction exists but the LATENT at the onset failed: an encode error, or a non-finite or wrongly shaped
  z) STAY in both arms:
  - their identity features need no latent;
  - their residual microstate is the residual of the public PCs from u alone (a u -> PC map fitted on the training fold), so the
    correction can still attribute their error;
  - a failed latent can therefore never remove an item from the score. Review E's demonstration: 6 NaN latents on 8 read-in-error
    items moved SMS from 0.75 to 0.00; it now stays at 0.75.
  - Their count is reported. Reported: SMS with {x_res, ID} (primary), {x_res}, {ID}, and SMS_raw (no bias correction in
arm A).
SMS near 0: the effect is captured through z and the model's read-in; large SMS: z or its read-in misses causal information
(through x_res: missing state; through ID: a read-in that does not carry the intervention's effect).

### 5.4 Interventional closure (goal5 section 31)
Evaluator-fitted comparison on the same items: error(z, u, a) vs error(z, u, a, x_res) for (i) y at the end of the primary horizon
(the verdict quantity) and (ii) z_future = phi(true future history) at 2 lags (descriptive), with the rules of 5.3 (residual
computed inside each fold; permutation-matched capacity; single-time targets, so an intercept in both arms instead of a per-lag
bias).

The base is z and u at onset, the mean and last future input, and compact intervention descriptors (event kinds, arity, signed
log-dose, event count, duration, onset). It has ONE row per item, at the end of the primary horizon: a base shared across lags
cannot fit per-lag dynamics, and the gain became seed-dependent.

The base is fitted WITHOUT shrinkage only while it has at most 1 column per 4 training rows. With one row per item, a fold has about
half of the items as training rows, so for the benchmark's item counts the base is usually ridge-penalised like the other columns,
with the penalty chosen by the inner split (review E, m3). Whether it was unshrunk is reported (`unshrunk_base`). x_res is
residualised on (z, u) inside the fold, so a penalised base cannot pass its z-effects to x_res.

The identity features of 5.3 enter both arms, penalised. x_res is built as in 5.3 (one map per outer fold). The 20 cross-fitting
seeds and the CI of 5.3 apply. ICG = fractional error reduction from adding x_res (linear and random-feature versions; the VERDICT uses the LINEAR ICG_y at the primary horizon: in the early review it detected a missing state coordinate on every seed and was invariant to padding the latent with irrelevant coordinates, whereas the random-feature version changed sign across cross-fitting seeds; the random-feature version is reported). Unusable and latent-missing items are handled as in 5.3; a latent-missing item's latent columns are
zero and an indicator column marks it. Also the
model's own interventional closure gap: its latent a short horizon after the onset (rollout under the events) against the encoding
of the intervened history at that time, relative to the distance between the intervened and twin encodings.

### 5.5 Microstate equivalence under intervention (goal5 section 32)
On the pool: for each state its model latent (whitened by the covariance of the model's encodings of PUBLIC training data; eigenvalue floor
1e-6 x max). Candidate pairs are cross-trajectory pairs within one parameter draw. MATCHED pairs = the M = 20 closest candidate pairs
in latent distance (a FIXED count, so matches tighten as the pool grows; a fixed quantile would not); RANDOM pairs = all candidate
pairs. For each sequence (the 6 intervention sequences and the no-intervention future): the ratio of the mean future readout
divergence (primary horizon, same sequence) of matched pairs to that of random pairs; MEV = the mean of the per-sequence ratios (so
one large-effect sequence cannot dominate); 95 % CI by resampling pool source trajectories (the matched set is recomputed in every
resample). NUMERICAL FLOOR (review H, B1): the same statistic as the divergence (mean squared, in units of the public readout sd,
over rows 1..m of the primary horizon) between a pool state's no-intervention future and (a) a repeat run with a no-op breakpoint
one sample after the restart and (b) a restart from the float32-rounded stored state against the float64 continuation, over 20
floor states. UNTESTABLE when matched pairs are not close (median matched / median random latent distance > 0.2), or when for every
sequence the random-pair divergence is below 2x the numerical floor or below the detection floor (2 f_s / y_sd)^2 = 0.01. An
untestable MEV does NOT satisfy criterion E (section 9: equivalence not established, reported as "E untestable"), so a model cannot
escape the criterion by a latent too high-dimensional to resolve neighbours in the pool (review E, B4); with 600 states and M = 20,
isotropic latents are testable up to k of about 5. Synthetic systems, descriptive:
- the TRUTH-EQUIVALENT comparison (review T round 3, N2). The generator's truth-equivalent states share the true causal state
  with a pool state but differ in microstate detail that is visible in x; they are excluded from the pairing above. For every
  pair of equivalent states the MODEL is measured:
  - its latent distance, whitened exactly as for the MEV, relative to the random candidate pairs (median ratio and mean ratio;
    a causal state maps equivalent states close: ratio near 0);
  - its PREDICTED-future divergence under the pool sequences: the divergence statistic of the MEV on the model's own
    predictions from each state's history (intervention_effect; "none" = no events), relative to the detection floor
    max(2 x the numerical floor, the effect-floor term) and to the same statistic on a seeded sample of random candidate pairs
    (at most 200, twice the number of equivalent pairs), per sequence and averaged over the testable sequences.
  The divergence of their TRUE futures is zero up to numerics by construction; it is reported only as a check of the dataset
  builder, never as a model quantity;
- the TRUTH-MATCHED comparison (pairs of main-pool states matched on the TRUE causal state, the same M rule).
Also: observation-matched pairs, per sequence, and the old fixed-quantile rule as a sensitivity variant.

### 5.6 Interventional bisimulation-like test (goal5 section 33) — descriptive
For latent-neighbour pairs: (1) immediate readout difference, (2) difference of responses under each intervention class, (3) latent
distance after one primary horizon (re-encoded from the true futures) relative to the initial latent distance; curves against the
initial latent distance. No formal bisimulation claim.

### 5.7 Native lift and multiple lifts (goal5 sections 15-16, 72)
For each lift case c: requested shifts delta_z = alpha v in the model's whitened latent coordinates (whitening from the model's
encodings of PUBLIC training data, never of test data), v in {the model's first two principal latent directions, one random unit
direction}, alpha in {0.5, 1.0} latent sd. On SYNTHETIC systems the requests are restricted to the KICK-REACHABLE span (review T
round 3, N4): the true latent shifts of single kicks on the public targets at the case's microstate (the generator's
true_latent_effect), mapped into the model's coordinates by the affine map z ~ z_true fitted, as for the true read-in accuracy
(5.16), on states that span the true state (truth samples, item onset states, pool states); when they do not span it the requests
stay unrestricted and the reason is reported. Each request is
projected onto that span orthogonally in the whitened metric, keeping its whitened length; it is dropped when less than 25 % of
that length is reachable, and requests that become identical are merged. So no request points along a direction that no
permitted kick moves (e.g. a hidden mode reachable by no public target, or a static draw context); directions reachable only
through currents over time are not requested either (conservative). The evaluator reports the dropped and merged requests, the
span's rank and whether distinct kick lifts exist (more public targets than reachable dimensions); where they do not, the
multiple-lift consistency has no truth reference, and this is reported. Real systems: unrestricted requests. The model returns up
to 3 DISTINCT lifts (events allowed by the system's capability;
lifts may use any supported kind, trained or not). For each lift the evaluator simulates the lifted world and the twin, both
restarted from the case's stored microstate; at the completion sample j (one sample after the last instantaneous event, the end of
the last finite event) it measures:
- latent miss: ||(phi(lifted history) - phi(twin history)) - delta_z|| / ||delta_z|| (whitened);
- cost: sum over current / sequence events of |amplitude| x duration, the summed |kick| magnitudes SEPARATELY (a kick's cost does
  not scale with dt), and the number of targets;
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
The selected k, the reported plausible range, and the stability of k over EXACTLY the level's fits. The ADMISSIBLE k values are:
- the reported range, when it is TIGHT (hi - lo <= 1) and contains the modal k;
- otherwise {modal k}. A wide or excluding range is ignored for stability, and this is reported (review E, N-new-5: k_true is 1-4 on
  this benchmark, so a wider range such as 2-4 would call a factor-of-2 disagreement stable).

Stability:
- Level B, over the 3 fit seeds: STABLE if all three seeds produced a k and every k is admissible.
- Level C, over the 5 refits on bootstrap resamples of the training INTERVENTIONS (passive data kept): STABLE if all five refits
  produced a k, the modal k occurs in >= 4 of 5, and every k is admissible. So the fifth refit may differ from the modal k only
  within a tight range.

A missing or failed fit (no k) is never admissible (review E, N7 / N-new-8): a crash cannot use up the one disagreement Level C
allows, and a single seed or 1 of 5 refits cannot pass F. The number of missing fits is reported. Otherwise: "dimension unresolved:
min-max". The benchmark references have a fixed k, so they are stable by construction (an
asymmetry stated wherever P_t is used). Synthetic truth: k consistent with k_true (5.16); k_true within the range. Compact: k <= max(1, N_obs / 5) (full
and synthetic systems; mechanisms are judged on stability only). Every latent coordinate counts, static ones included. On synthetic
systems the limit carries a DRAW ALLOWANCE: compact = k <= max(1, N_obs / 5) + d_draw. Each trajectory has its own parameter draw,
so a draw-closed state carries up to d_draw static coordinates (5.16; d_draw from the system's truth record, the generator's
effective draw dimension, 3-10 on the development tier, median 6). The true state [z, draw] is then compact exactly when
k_true <= max(1, N_obs / 5), the compressibility condition. The non-compressible types stay above the limit, since their full rank
exceeds the bound by at least 1.5x and the allowance applies to both. Real systems keep max(1, N_obs / 5) (LOG P4-D62).

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
latent recovery min(R^2 of z_true from z, R^2 of z from [z_true, the trajectory's effective draw parameters]) (cross-fitted, linear +
random features); z_obs capture on trap systems (R^2 of the exposed causal variable from z); k CONSISTENT with the truth: k_true <= k
<= k_true + d_draw (every trajectory has its own parameter draw, so a history-based state may legitimately carry static coordinates
that identify the draw; d_draw = the generator's effective draw dimension, the number of draw parameters that change the causal-state
dynamics or the readout above the floor over the draw distribution, and the effective draw parameters of a trajectory come from its
truth record; LOG P4-D43); correct "no compact causal state" on types 20 / 21; true read-in accuracy on verdict items whose first
event is instantaneous and acts at the onset, each model quantity against the truth of its own definition (review H, N4), truth mapped
into model coordinates by the affine map z ~ z_true fitted on states that span the true state (the held-out samples, every item's onset
state and the pool states; "unidentifiable" when they do not span it; review H round 3b, NEW-5): headline, for every model, the rollout difference one
sample after the onset against the true latent difference item - twin one sample after the onset (the quantity the lift miss
measures); beside it, for models whose read-in returns dz, the read-in dz against the exact true latent effect of the event
(true_latent_effect). Reported, not binding.

### 5.17 Active experiment design (goal5 sections 24-29, 60, 73)
For each system and designer (the method's own; `random`, `uniform`, `magnitude_sweep`, `greedy_error`, `structural`, `passive`,
`fixed`), the method's learner is run in the experiment loop from D0 with checkpoints after 10, 25, 50, 100 and 200 intervention
experiments (real full networks: 10, 25, 50, 100), 3 loop seeds. One experiment = one intervention trajectory plus its twin (the
passive designer spends the same number of trajectories without interventions). Quality at each checkpoint: class-balanced EE
(primary horizon, verdict items), SMS, k correctness (synthetic), lift success. Costs: experiments, simulator calls, simulated
seconds, unique targets, magnitude budget (current doses and kick magnitudes reported separately), CPU / GPU s. ACTIVE DESIGN SUCCEEDS iff rule (i) or rule (ii) holds.
SYSTEM SET of the rule: every synthetic system of the confirmation suite (Level C; Level B uses its validation systems), the trap
systems of review G excluded. The real systems are reported beside it, descriptively, with the same statistics; they do not
enter the rule (few systems, and real full networks run to budget 100 instead of 200). No system is dropped for a failed or missing
loop; its cells are charged so that a failure never favours the method: a failed OWN cell gets the higher (worse) of the random
and fixed values at that budget, a failed COMPARATOR cell gets the lower of the other arms' values, and a cell where every arm
failed is missing for all arms.

(i) FIXED BUDGET, one test per comparator (review E, N6).
- For random and for fixed, the per-system statistic is the mean over the 5 checkpoint budgets of (EE_own - EE_comparator); each EE
  is the mean over loop seeds.
- The mean of this statistic over systems must have a one-sided upper bound below 0 for BOTH comparators (paired, unstratified,
  rescaled system bootstrap). This is an intersection-union test, so its overall level is alpha.
- In addition, the own designer must be significantly worse than a comparator at no single budget (one-sided lower bound above 0).
- The per-budget differences are reported as descriptive values.

(ii) BUDGET RATIO (review E, M4 / N6).
- The target quality is random's EE at 100 experiments.
- The budgets-to-reach of the method's designer and of random are estimated with the SAME estimator: random's own budget-to-reach
  on leave-one-loop-seed-out curves. Curves that never reach the target are right-censored, not charged a fixed cap.
- The ratio of sums R = sum b_own / sum b_random over systems must have a one-sided upper bound < 1. The bound is on log R, with the
  delta-method standard error of the per-system linearisation and a t quantile with n - 1 degrees of freedom. The rescaled paired
  percentile bootstrap was liberal at 25 systems; it is reported beside.

Each rule is tested ONE-SIDED at alpha = 0.025 (Bonferroni over the two rules), so the union stays at or below 5 %. In simulation
(review E's curve model; 800 replications per null), the false-positive rate of the union was:
- 0.021 with own = random (50 systems) and 0.026 (25 systems);
- 0.040 with fixed worse than random by 0.05 EE (50 systems);
- 0.035 with fixed worse by 0.10 (25 systems); it was 0.069 under the earlier "2 of 5 budgets" rule.
The power of the union was 1.00 at 1.5x efficiency (50 systems) and at 2x (25 systems).

R is conservative: the checkpoint grid and the censoring at 200 bias it toward 1 (a true 0.50 is estimated as about 0.63, a true
0.33 as about 0.46). "The designer needs X % of random's budget" is therefore reported as an UPPER BOUND on that fraction (review E,
N8).

Also reported, as a control for large-effect selection: the same comparison against a magnitude-MATCHED random design.

Computed on the dev suite before the freeze by simulation (`loop.mde_by_simulation`) and reported:
- the minimum detectable effect of the rule;
- its false-positive rate under nulls with a WEAKER fixed design (the fixed curve shifted up by 0.05 and by 0.10 EE).

## 6. Calibration to the real systems (goal5 section 8)
`public/calibration_targets.json` (version 3, from the public real data built with this design; `scripts/p4/calibration_targets.py`
with `brainir_causal.calibstats`; every public record of each system). The dev suite's statistics, computed on every public record
of each system (the targets' record selection), must fall in the recommended ranges of the statistics marked required; the check is
recorded (acceptance criterion 11) and repeated on the validation and confirmation suites.

## 7. Pre-registered calibration of the tolerances (dev suite only, before any method)
References (section 8) fitted on D0 + D1 of every dev system; evaluated on the verdict items (section 9). Every tolerance below is
computed on the items the TRUE-STATE reference SUPPORTS (it abstains on event kinds never trained; its abstention share is recorded),
so the tolerances measure the sampling variability of a correct state, not the reference's structural abstention (review E, M3).
With a COMMON percentile p (below):
- delta_A (margin of "meaningfully better than no effect") = max(0.1, p-th percentile over systems of the upper CI of the true-state
  reference's class-balanced EE minus its point value) [CAL];
- delta_C (non-inferiority margin to the full-state upper bound) = max(0.05, p-th percentile over systems of the UPPER CI of the
  paired difference EE_truestate - EE_fullstate) [CAL] (the same quantity the verdict tests);
- tau_SMS = p-th percentile of the upper CI of the true-state reference's SMS [CAL];
- tau_ICG = p-th percentile of the upper CI of the true-state reference's LINEAR ICG_y [CAL];
- tau_MEV = p-th percentile of the upper CI of the true-state reference's MEV where testable [CAL];
- tau_FC (false-confidence ceiling) = 0.2 [fixed];
- delta_H (held-out family margin) = max(0.1, p-th percentile of the true-state reference's (EE_heldout - EE_infamily)) [CAL].

COMMON PERCENTILE (the conjunction; review E, M3 / N4 / N-new-2).
- The BINDING FLAGS of D, E_icg and E_mev are decided ONCE, by the power rule at p = 90, and stay fixed at every candidate p. Raising
  p then only loosens the tolerances, so the support rate can rise only because the true state passes, never because a criterion
  stopped binding.
- The support rate at p is the fraction of the compressible dev systems on which the true-state reference meets every binding
  criterion jointly, with the fixed flags (criterion A including its class condition, section 9).
- p is the smallest value in {90, 95, 97.5, 99} whose support rate is at least 80 %.
- The power rule is re-run at the chosen p's tolerances. The calibration is NOT ATTAINABLE if any of the following holds:
  - MEDIATION AND CLOSURE: the fixed flags do not make D bind AND at least one part of E (ICG or MEV) bind. "Causal state
    supported" asserts both properties, so without them no system can be SUPPORTED (section 9).
  - A criterion that binds at p = 90 has no power at the chosen p (the nulls pass it about as often as the true state).
  - Even p = 99 does not reach 80 % (p = 99 is then used).
  In that case it records that the full verdict with powerful criteria is not attainable, and the synthetic part of the conclusion
  can be at most PARTIAL. This is declared here, before any method.
- `calibration.json` records the following:
  - at every candidate p: the tolerances, the fixed flags, the power rule's own flags at that p and the true-state support rate;
  - whether a binding mediation / closure criterion exists;
  - the reason for the choice.

ITEM SET (review E, N5): the calibration's 80 % target and the conclusion's P_t (section 9) use the SAME items, the verdict items
the TRUE-STATE reference supports (`calibrate.true_state_categories`). "P_t < 0.5: not attainable" therefore means what the
calibration measured.

SUITE MARGINS (review E, N9) for the suite-level tests of the primary family (section 11), from the same calibration rows at the
chosen p. A percentile of per-system upper bounds is a lenient boundary for a MEAN over systems.
- tau_SMS_suite (H4) = the p-th percentile, over 2,000 suites of n systems drawn with replacement from the calibration systems, of the
  true-state reference's one-sided 95 % upper bound of its MEAN SMS (mean + t_{0.95, n-1} sd / sqrt(n)). Here n is the number of
  compressible confirmation systems.
- delta_C_suite (H3) = the same for the mean of EE_truestate - EE_fullstate, at least 0.05.
- So the true state itself would reject these null hypotheses on about p % of confirmation-sized suites, as the per-system
  tolerances let it pass D and C on p % of systems. The suite margins are part of the locked calibration.

POWER RULE (D, the ICG part of E, the MEV part of E): a criterion binds only if a one-sided Fisher exact test (alpha 0.05) shows that
the true-state reference passes it more often than EACH null on the SAME systems (the observational-shortcut reference on the trap
types, at least 6 systems; random-k on all compressible systems); otherwise it is reported and does not bind.
Each tolerance has a descriptive 95 % CI (unstratified resampling of the calibration systems); the reference verdict distributions,
the power tables and the verdicts at both CI ends of every tolerance are recorded in `calibration.json` (locked); only the values go
to `public/tolerances.json`. Real verdicts are conditional on this synthetic calibration; the report gives the method's verdicts at
both CI ends of every tolerance as a sensitivity table.
POWER TABLE (review E, B2), computed on the dev suite before the freeze and recorded in `calibration.json`: pass rates of D and E for
the true-state reference, a read-in-error corruption of it (read-in gain 0.5 on one trained family), and a missing-state corruption
(one true state coordinate removed); the criteria are declared able to detect these failures only if the corruptions fail them
significantly more often (Fisher exact, alpha 0.05).

## 8. References and baselines
Benchmark references (code `brainir_causal.refs`, trained on D0 + D1 like a method):
- NO-EFFECT (e-hat = 0).
- TRUE-STATE (synthetic): encoder = [z, draw], the true causal state and the trajectory's effective draw parameters from the truth
  store (review E round 3, N-new-1).
- FULL-STATE: encoder = the observed microstate with two causal exponential traces of it, time constants 1/4 and 1 x the short
  horizon; the predictability anchor of goal5 section 23.
- OBS-SHORTCUT (synthetic trap types): encoder = [z_obs, draw].
- RANDOM-k and PCA-k (k = the method's k).
- ID-SHORTCUT: y future = h(intervention identity, stimulus, readout history), with no state (goal5 section 22).
The z-only forms of TRUE-STATE and OBS-SHORTCUT are descriptive references and enter no tolerance or verdict.

The state-based references share one generic learner (`refs.py` docstring, version 2), in six parts:
- Control-affine dynamics ds / d_sd = f0(s, u) + R (per-unit descriptors of currents, silencing, connection scaling and parameter
  changes), with R learned per (unit, kind) from the training interventions.
- Kicks enter through a kick read-in learned from the training kicks against their twins, around a structural prior: identity for the
  observed microstate, zero for a compact state, never a correlational probe.
- A static context for TRUE-STATE and OBS-SHORTCUT:
  - the draw coordinates that vary over the training records are appended to the state with zero dynamics; no intervention moves them;
  - they enter f0 and the readout and scale each channel effect per state coordinate;
  - a history without a registered draw gets the training-mean draw, and this is counted;
  - a system whose training records carry no draw falls back to z alone, and the reference records it (info()['draw_context']);
    the calibration refuses a system whose truth carries draws when TRUE-STATE fell back;
  - the reference's k is the dimension of its encoding, draw coordinates included; the dynamic and context parts are reported apart.
- Abstention on any event on a unit never intervened in training with that kind, and on any kind never trained.
- One-step training, then paired training:
  - one-step phase ('two_stage', the rule stated before the whole-suite comparison, for EVERY reference): f0 is fitted on the rows
    without an active channel, then R in closed form on the channel rows, then f0 again on all rows with R fixed (LOG P4-D51);
  - paired phase: each intervention trajectory and its twin are unrolled together from a common state, starting at most one short
    horizon before the onset and running through the whole primary horizon after the onset, clipped only at the trajectory's end;
    the loss covers both trajectories and their difference.
- A per-horizon least-squares calibration factor in [0, 1] on the predicted effect, fitted on training pairs.

Every trajectory has its own parameter draw, and the true causal state is closed only given it: a reference on z alone keeps an error
floor that no learner removes, so TRUE-STATE and OBS-SHORTCUT carry the draw. Version 1 of the learner (a correlational read-in with
short unrolls) predicted worse than no effect on most dev systems; version 2 was chosen by a rule stated before the whole-suite
comparison (research-side record, LOG P4-D42). Tournament BASELINES (goal5 section 21) are methods like any other, built in the clean
room on public data. The earlier locked state-discovery method (BrainIR State v1) runs unchanged as a frozen baseline.

The FULL-STATE BOUND and the ID-SHORTCUT comparator are each ONE model choice per system kind (synthetic, real), fixed at Level B
(review E, N-new-9).
- The choice is the candidate with the lowest MEDIAN verdict EE over the Level B validation systems of that kind:
  - for the full-state bound: the FULL-STATE reference, FULL-STATE-JOINT (the same learner with the joint one-step fit: f0 and
    R together on all rows; an extra candidate only, never a calibration reference; LOG P4-D51) or a full-state baseline;
  - for the comparator: the ID-SHORTCUT reference or an ID baseline.
- A baseline's per-system EE is its mean over the fit seeds. A missing seed, system or result counts as EE 10, and ties go to the
  reference.
- The choice is applied unchanged to every system of the kind, including the new confirmation systems at Level C.
- On a system where the chosen baseline has no result, that system uses the reference, and this is recorded.
- A per-system minimum over candidates on the same data would be optimistic for the bound, and would have no counterpart on new
  systems.

The references' k is fixed, so their dimension criterion (F) counts as stable in the calibration's reference verdicts.

## 9. Verdicts (per system; goal5 section 71)
VERDICT ITEMS = the roles present in the calibration: in-family, target shift, near shift, far shift and hidden-only. OOD and
robustness items never enter a verdict criterion; they are reported by 5.12 (validity domain). BOUNDS: the per-system criteria use the upper (or lower) end of the TWO-sided 95 % interval, the quantity the calibration's
tolerances are built from; one-sided 95 % bounds are used only in the primary family (section 11). The uncertainty of every class-balanced quantity (A, B, C, H) is the interval of 5.1: family jackknife with Bell-McCaffrey degrees
of freedom, always at the family level, and no interval below 4 families. Classes carried by fewer than 3 families are merged, never
dropped. 'hi' is its own class when it has at least 3 families; otherwise it is merged into strong. The family count and the merges
are reported with the verdict.
HELD-OUT items = the near-shift,
far-shift and hidden-only items (the family shift); the B subset adds the target-shift items. EE below = the class-balanced EE of 5.1.
- A intervention prediction: the upper CI of EE (primary horizon, verdict items, abstentions as no effect) < 1 - delta_A, AND the
  POINT EE of every merged magnitude class (5.1) < 1 - delta_A (review E, M1). A model that predicts only some classes (e.g. only the
  strong items) therefore cannot pass A. The per-class condition uses point values, because per-class intervals would rest on 3-6
  families. The condition enters the calibration's support rate (section 7), so a class that even the true state cannot predict
  shows up there as "not attainable", never silently; the per-class values are reported with every verdict.
- B shortcut: the upper CI of the paired difference EE_method - EE_idshortcut < 0 on the B subset.
- C full-state: the upper CI of EE_method - EE_fullbound <= delta_C; the full-state bound is the Level B choice of its system kind
  (section 8), applied unchanged at Level C.
- D mediation: upper CI of SMS <= tau_SMS if the power rule admits it; otherwise reported, not binding. D fails when more than 1 % of
  the items are unusable (5.3); latent-missing items stay in the score.
- E closure / microstate: upper CI of the linear ICG_y <= tau_ICG (power rule) AND the MEV is TESTABLE and its upper CI <= tau_MEV.
  An untestable MEV does not satisfy E (equivalence not established; reported as "E untestable", with the matched / random distance
  ratio and k).
- F dimension: compact (5.10) and stable over EXACTLY the 3 fit seeds (Level B) or the 5 bootstrap refits (Level C). Stability is
  judged on the k values, with a self-reported range counting only when it is tight (width <= 1). A missing or failed fit is never
  admissible. Mechanism systems (no compression criterion) are judged on stability only; on synthetic systems the compactness
  limit carries the draw allowance of 5.10.
- G false confidence: rate <= tau_FC (passes when no covered item has a detectable effect).
- H family generalisation: the upper CI of EE on held-out items < 1 - delta_A, and the point estimate EE_heldout - EE_infamily <=
  delta_H (its CI is reported).

Rules:
- A criterion that is not binding (power rule) is excluded from both SUPPORTED and PARTIAL.
- A criterion whose inputs are missing blocks SUPPORTED.
- MEDIATION AND CLOSURE (review E, N-new-2): CAUSAL STATE SUPPORTED can be issued only when the calibration makes D bind AND at
  least one part of E (ICG or MEV) bind. Otherwise the best category is PARTIALLY SUPPORTED, the verdict records that SUPPORTED was
  blocked, and the calibration is not attainable (section 7).

Verdicts:
- CAUSAL STATE SUPPORTED: every binding criterion A-H holds, and mediation and closure bind.
- PARTIALLY SUPPORTED: A holds and at least one binding criterion of D, E, H holds. The report names every failed, untestable or
  missing criterion.
- UNSUPPORTED: otherwise.

A method's declared "no compact causal state" is recorded as such (correct on types 20 / 21, a false alarm elsewhere). The categories
are ordered SUPPORTED > PARTIALLY SUPPORTED > UNSUPPORTED in every aggregate. Lift success (5.7) is required for the strongest claim (goal5 section 93) and
reported beside.

Overall conclusion (goal5 section 92.51), from the Level C results only.
- P_m = the fraction of compressible confirmation systems whose verdict for the locked method is CAUSAL STATE SUPPORTED, judged on
  all verdict items.
- P_t = the same for the TRUE-STATE reference, fitted on the same systems and data (post lock; a benchmark reference, not a method;
  stable dimension by construction). It is judged on the item set of the calibration's target: the verdict items the reference
  supports (section 7).
- P_m - P_t is computed on ONE item set: the method's verdicts on the true state's supported items
  (`calibrate.calibrate_from_inputs(extra_models=...)`, `calibrate.model_categories`). If those cannot be produced, the all-items
  verdicts are used (a superset, conservative for the method) and the report says so.
- MISSING RESULTS ARE CHARGED against the claim (review E, N10):
  - a missing method verdict counts as not supported;
  - a missing true-state verdict counts as not supported in P_t for the attainability rule, and as supported in the paired
    difference;
  - the charged counts are reported.
- Lower bound of P_m: the one-sided 97.5 % Clopper-Pearson bound on the count of supported systems.
- P_m - P_t: paired UNSTRATIFIED system bootstrap over all compressible systems, one-sided 97.5 % lower bound. The stratified
  bootstrap is anti-conservative with 2-3 systems per type (review E, B6).
- Synthetic part SUPPORTED: lower bound of P_m >= 0.5, lower bound of (P_m - P_t) >= -0.2, and "no compact causal state" declared on at
  least 2/3 of the non-compressible controls (types 20, 21). PARTIAL: not SUPPORTED, and the lower bound of P_m >= 0.2 or at least
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
public confirmation (all validation systems, all real systems, 3 seeds, active-design curves). At most 4 public rounds in total.
FIT SEEDS AND REFERENCES (review E, N1).
- Every Level B round fits and evaluates the round's fit seeds, at least 3; the driver refuses fewer.
- Every seed is evaluated. A candidate's per-system values are the SEED AVERAGE over them (`select.seed_average`); a seed without a
  result counts as a failure.
- Criterion F uses the k of the same seeds (5.10).
- Beside the candidates' rows, the driver writes the per-system rows of the gate references:
  - true_state.json: the TRUE-STATE reference's verdict on the round's synthetic systems, with the Level B-fixed bounds;
  - full_state_bound.json: on every system, the model that BOUNDS.json names.
- The decision step fails loudly when a round with synthetic systems has no true-state row; it never passes silently.

THE RULE (no single scalar; one order, review E, B5), applied to these seed-averaged values:
1. GATES (goal5 section 68, 1-3): a candidate is ELIGIBLE when, on the round's synthetic systems, its pass rates of A (intervention
   prediction), D (mediation) and E (closure / microstate) are each at least half of the TRUE-STATE reference's pass rates on the
   SAME systems (recomputed per round), and, on the round's real systems, its pass rate of A is at least half of the full-state
   bound's.
2. If NO candidate is eligible, all candidates are ordered by the gate metrics (median class-balanced EE, then median SMS, then median
   linear ICG_y; lower is better) and the report says "no candidate meets the gates"; halving then keeps the better half by this order.
3. Among eligible candidates, lexicographic with tie bands: (4) compression (fraction of systems compact and, synthetic, k consistent with k_true as in 5.16),
   (5) observational prediction, (6) experiment efficiency (5.17; a tie while no loop has run), (7) simplicity (parameters), (8)
   compute. Two candidates are TIED on a criterion when the 95 % CI of their paired difference (system bootstrap stratified by system
   KIND, synthetic vs real, with the rescaled stratified bootstrap; never strata of size 1) includes 0; ties pass to the next
   criterion; a candidate that failed or produced a non-finite value on a system is charged the worst admissible value there (EE 10,
   SMS / ICG +1, fit failure = not compact) and the count is reported (review E, M7).
Eligible candidates always rank above ineligible ones. A method that predicts passive dynamics well but fails the gates cannot win.
Level B scores of the selected method are optimistic (selection on the validation suite) and are never reported as performance.

## 11. Statistics (goal5 section 77)
Units: synthetic = system instance (paired across methods on the same instances; CIs by UNSTRATIFIED system resampling, or the
rescaled kind-stratified bootstrap where stated); within a system = the IDENTITY CELL (5.1); never time steps. Real: per system; the
two builds of one reconstruction are one lineage; pooling across networks is descriptive. CIs: percentile bootstrap, 2,000 resamples, except for the CLASS-BALANCED EE quantities. Their interval is the family jackknife with
Bell-McCaffrey degrees of freedom of 5.1 (no interval below 4 families). Their Estimate carries 2,000 seeded t-draws, so bounds and p = (1 + count) / (1 + B) are computed in the same way. Paired
differences use identical units. Non-finite replicates are counted AGAINST the claim, never dropped silently. ONE alpha convention: every confirmatory test is ONE-SIDED at alpha = 0.05 (its CI bound is the one-sided
95 % bound), Holm-adjusted within the primary family.
PRIMARY FAMILY (24 one-sided tests, Holm at alpha 0.05; computed by `verdict.build_primary_family`). M = the locked method; S = the
strongest baseline (fixed at Level B); ID = the ID-SHORTCUT comparator and FB = the full-state bound: each ONE Level B choice per system kind (section 8), applied unchanged
to the confirmation systems. Each hypothesis is tested on (a) the confirmation suite (statistic
= the mean over compressible systems of the per-system value; paired unstratified system bootstrap) and (b) each of the three real full
networks (statistic = the per-system value; identity-cell bootstrap):
| id | claim | statistic (lower = better) | null hypothesis | margin |
|---|---|---|---|---|
| H1 | effects predicted better than no effect | class-balanced EE of M | EE >= 1 - delta_A | delta_A (calibration) |
| H2 | better than the intervention-ID shortcut on held-out families and targets | EE_M - EE_ID on the B subset | difference >= 0 | 0 |
| H3 | near the full-state bound | EE_M - EE_FB | difference >= margin | suite: delta_C_suite; networks: delta_C (calibration) |
| H4 | intervention effects mediated by the state | SMS of M | SMS >= margin | suite: tau_SMS_suite; networks: tau_SMS (calibration) |
| H5 | held-out families predicted better than no effect | class-balanced EE of M on held-out items | EE >= 1 - delta_A | delta_A |
| H6 | not worse than the strongest baseline | EE_M - EE_S | difference >= delta_NI | delta_NI = 0.2 x S's median class-balanced EE on the validation suite, fixed as a NUMBER at the method lock |
MARGINS (review E, N9): every margin is a pre-registered NUMBER.
- The per-network tests (b) test per-system statistics against the per-system calibration margins (delta_A, delta_C, tau_SMS).
- The suite tests (a) test MEANS over systems:
  - H3 and H4 use the suite margins delta_C_suite and tau_SMS_suite of section 7 (the true state's own suite-level bound), because a
    percentile of per-system upper bounds is a lenient boundary for a mean (a larger margin makes H3 and H4 easier to reject).
  - H1 and H5 keep 1 - delta_A. There a larger margin makes the test stricter (it demands a larger improvement over no effect), so
    the per-system delta_A is conservative for a mean.
- delta_NI is fixed at the method lock.
- The class merges of each system are reported with the suite rows (5.1, limitation).

Everything else is descriptive (per-system verdicts A-H included; they are not multiplicity-corrected and are labelled so). The minimum detectable effects of the active-design rule, and its false-positive rate under nulls with a weaker fixed design
(5.17), are computed on the dev suite before the freeze and reported. The report states the number of
candidates and rounds evaluated on each real system before the lock, that real verdicts come from systems also used in selection
(fresh items only), and the Level B -> Level C drop of the selected method (review E, M6).

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
