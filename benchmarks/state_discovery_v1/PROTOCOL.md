# state_discovery_v1 — pre-registered evaluation protocol (Phase 3, goal4.md)

This protocol is frozen BEFORE any state-discovery method is developed (goal4 sections 6-7). The locked hashes are in
`BENCHMARK_LOCK.json` (git tag `state-discovery-benchmark-v1`). Any change after the lock is a new benchmark version. Only the files
listed as PUBLIC in section 11 may enter a development clean room.

The benchmark scores a *state model* of a system s:
- an encoder z_t = phi_s(x_{<=t}, u_{<=t}) from the observed microstate and the input;
- transition dynamics z_{t+dt} = f(z_t, u_t, events);
- a readout y_t = g_s(z_t, u_t).

The interface is `brainir_state.api.StateModel`. The benchmark does NOT score neuron identities. Its hidden evaluations use FUTURE
DATA the method never saw: held-out stimuli, initial states, parameter draws, intervention targets and types, microstate restarts,
noise realisations and implementations.

## 1. Levels (goal4 section 56)

| level | data | who sees what | use |
|---|---|---|---|
| A development | synthetic DEV suite (public trajectories incl. its test / twin / pool splits; truth outside the room); real public train / val / twin trajectories; the budgeted simulation service (public policy only) | method developers | any development, hyper-parameter search, self-evaluation with the public evaluator code |
| B selection | synthetic HELDOUT suite (secret seed; never in a clean room) | the orchestrator runs it; developers get aggregate profiles only | tournament selection (section 9); at most 3 selection rounds, each logged |
| B confirmation | synthetic FINAL suite (secret seed) | run ONCE on the locked method and the baselines | confirmation |
| C real hidden test | real hidden trajectories generated AFTER the method lock from a secret salt (committed now by sha256) | run ONCE on the locked method, the strongest baseline and the reference controls; logged | the real-circuit result |

## 2. Systems

### 2.1 Real

For each public network d in {net1, net2, net3}:
- `real:<d>:full`: the intact network;
- `real:<d>:mech:<h8>`: the keep-only network of every candidate mechanism that passes a fixed rule. A candidate is regenerated from
  public evidence by the locked Phase 2 method (seed 0, budget 1000, public no-gate rhythm criterion; `research/phase3/candidates/`).
  It is kept if it passes keep-only on at least half of 8 fresh public parameter seeds. No candidate is chosen by hand.

d is an anonymised name of one of the three networks of the frozen tier-A public benchmark bundle. The mapping stays outside every
clean room in `hidden/network_map.json`. There are 10 systems: 3 full, and 2, 3 and 2 mechanism systems on net1, net2 and net3.

Populations are set by a deterministic public probe rule (`brainir_state.realgen.build_systems`):
- observed x = the non-readout, non-stimulus neurons whose peak rate exceeds 0.01 Hz in any of 9 probe trajectories (3 seeds x
  stimulus scales 0.6, 1.0 and 1.4);
- readout y = the network's readout neurons that are active in its full system's probes; every system of a network uses the same
  list;
- input u = the stimulus current.

net1 and net3 are two builds of ONE reconstruction (same animal, same synapse table, different annotation snapshots). net2 is an
independent reconstruction of another animal. Real cross-network evidence therefore rests on two independent reconstructions and
is descriptive (goal4 section 67).

Integration uses the Phase 1 simulator, composed piecewise (`brainir_state.realsim`). It is numerically equivalent to a single
frozen call within the simulator's own tolerance: max 0.04 Hz, against 0.07 Hz between the frozen default and a 100x tighter
tolerance. Trajectories are 2 s long with dt = 1 ms.

### 2.2 Synthetic

The generator `p3synth` was written by an oracle-free author (contract `research/phase3/contracts/SYNTHETIC_BENCHMARK_CONTRACT.md`)
and is hash-locked in `generator/` (documentation: `generator/SYNTHETIC_BENCHMARK.md`, truth-side). It has 48 systems:
- all 20 required families;
- traps A-L;
- two implementation groups: one Hopf latent shared by 4 implementations, and one gated integrator shared by 3;
- three unrelated pairs with identical implementations and different latent dynamics;
- two non-compressible controls: a chaotic 200-unit RNN and a 60-D linear system.

The latent z is exactly a population signal of the neurons, simulated in x-space (RK4, verified against an independent solver).
Trajectories are 4 s long with dt = 10 ms.

There are three suites of the same catalogue with different seeds:
- DEV: public seed 20260924; public trajectories; truth outside the room;
- HELDOUT: secret seed, 2x trajectories;
- FINAL: secret seed, 3x trajectories.

Each suite's own test split holds out the following (generator section 8):
- initial states: a radial shell 1-1.5x the training range, or family-specific regions;
- parameter draws: 1000-1007, against 0-7 in training;
- structural noise: sd 0.12, against 0.05 in training;
- intervention TYPES: group kicks, group currents, group silencing and edge removal, against single-neuron events in training;
- intervention TARGETS: 40 % of neurons, stratified by role, never touched in train / val.

The orchestrator adds a counterfactual twin to every test intervention trajectory: same protocol and noise realisation (noise_seed),
no events. It also adds the microstate pools of section 3.3.

## 3. Protocol families and splits (goal4 sections 27, 29, 51)

### 3.1 Real

Intervention targets: the full system's observed population is split by a public seeded permutation into A (development targets)
and B (held out). For mechanism systems, A = all members.

| family | split | description |
|---|---|---|
| nominal | public | stimulus onset U[0.01, 0.15] s, scale 1 |
| stim_amp | public | scale U[0.6, 1.4], optional step change, optional early offset (persistence) |
| init_state | public | stimulus from t = 0; initial microstate from the system's own states (70 %) or random sparse rates |
| kick_A | public | 1-3 kicks of +-U[5, 30] Hz on 1-3 A neurons |
| pulse_A | public | 1-2 current pulses U[5, 40] for U[10, 150] ms into 1-2 A neurons |
| silence1_A | public | one A neuron silenced (temporary or to the end) |
| weight_noise | public | multiplicative weight noise sd U[0.02, 0.1] |
| H_nominal, H_init_state | hidden | as above with hidden parameter draws and states |
| H_kick_A, H_pulse_A, H_silence1_A | hidden | public intervention types on public targets, hidden draws (in-distribution control) |
| H_kick_B, H_pulse_B, H_silence1_B | hidden | held-out TARGETS |
| H_group_silence | hidden | 2-4 neurons silenced together (held-out TYPE) |
| H_stim_ood | hidden | stimulus scale U[1.5, 2.0] or U[0.3, 0.5] (out of distribution) |
| H_weight_ood | hidden | weight noise sd U[0.15, 0.25] (out of distribution) |
| H_micro | hidden | microstate-equivalence pools (section 3.3) |

Public trajectories per full system: 340 train and 85 val. Mechanism systems have half as many. Validation interventions have twins
(split `twin`).

Hidden trajectories: 30 per family per full system and 15 per mechanism system. Every hidden intervention trajectory has a
counterfactual twin (same seed, state and inputs, no events). Public seeds are < 10^9; hidden seeds are >= 10^9 and derive from the
secret salt.

The simulation service refuses all of the following, so no held-out family can be simulated during development:
- hidden seeds;
- B targets;
- group silencing;
- edge removal;
- stimulus scales outside {0} U [0.55, 1.45];
- weight noise sd > 0.1.

### 3.2 Synthetic

Train / val families: nominal, init, stim, param_draw, weight_noise, and single-neuron kick, current and silence_single.

Test families take roles in the evaluation:

| role | families |
|---|---|
| non-intervention (A, B, D, R, K) | init_heldout, param_heldout, and the event-free pool trajectories (H_micro: held-out parameter draws and initial states) |
| held-out interventions (C) | kick_group, current_group, group_silence, edge_remove, kick_newtarget, silence_newtarget, combined_heldout |
| out of distribution (H) | noise_heldout |

The development policy of the simulation service for synthetic dev systems allows:
- rest initial state only;
- parameter draws 0-7;
- weight-noise sd <= 0.05 with seeds < 10^4;
- single-target kicks, currents and silencing on public targets only, with no simultaneous or overlapping events;
- no edge removal and no latent events.

### 3.3 Microstate pools (family E)

Real, per hidden parameter draw:
- 6 draws x 8 pool trajectories, with different initial states and kicks;
- 4 states are sampled from each pool trajectory (t >= 0.3 s);
- each state is restarted from its FULL microstate (all neurons) under the common nominal input for 250 ms;
- the numerical floor is the same restart split at an extra breakpoint.

Synthetic, per system:
- 4 held-out parameter draws x 8 pool trajectories (held-out initial states or random inputs);
- 4 states are sampled from each pool trajectory (t >= 1 s);
- each state is restarted from its full microstate under the nominal input for 1 s;
- all restarts of one draw share one noise realisation;
- the floor is the same restart with another noise realisation.

Pairs are formed only between states of the SAME draw and DIFFERENT pool trajectories.

Diverged simulations (non-finite values) are removed with their counterfactual partners after building (`build_synthetic_suites.py --screen`). One heldout test trajectory (family noise_heldout) was removed; no dev or final trajectory, and no pool restart.

## 4. Metric families (separate; never collapsed; goal4 section 7)

All families are implemented in `brainir_state.evaluate`, `evaluate_cross`, `evaluate_lift` and `evaluate_synth`, and assembled by
`brainir_state.harness`.

Normalisers come from public training data only:
- the readout variance per dimension, floored at 1e-3 x its maximum;
- the PCA basis of x.

Time constants are fixed per data kind (`harness.REAL_CFG` / `harness.SYNTH_CFG`):

| constant | real | synthetic |
|---|---|---|
| A horizons | 10, 50, 100, **250**, 500 ms | 0.1, 0.25, 0.5, **1.0**, 2.0 s |
| encoding times t0 | 0.3 / 0.6 / 0.9 / 1.2 s | 0.5 / 1.0 / 1.5 / 2.0 s |
| C windows | 100, **250**, 500 ms | 0.25, 0.5, **1.0** s |
| D task horizon | 100 ms | 0.5 s |
| D latent deltas | 10 / 50 ms | 0.05 / 0.25 s |
| D history lags | 10 / 20 ms | 0.05 / 0.1 s |
| R (a, b) | (50, 200) ms | (0.25, 1.0) s |
| E future | 250 ms | 1.0 s |

Bold values are the primary ones.

| family | primary metric | also reported |
|---|---|---|
| A multi-step predictive sufficiency | window NMSE of the readout over the primary horizon after encoding at t0 (non-intervention hidden families) | other horizons; the references of section 5 and a persistence floor on the same data |
| B readout sufficiency | NMSE of g(phi(x_{<=t})) against y_t | |
| C interventional fidelity | normalised EFFECT error sum(d_pred - d_true)^2 / sum d_true^2 over the primary window after the first event, on held-out targets / types. d = intervened - twin; 1 = predicting no effect | post-intervention NMSE; in-distribution families (real H_*_A); per family; event kinds the model does not support count as abstentions |
| D approximate Markov closure | fractional error reduction when predicting y(t + task horizon) if the residual microstate is added to (z_t, u_t). The residual = the top-10 public PCs of x minus their cross-fitted prediction from (z, u), scaled by the PCs' spread. Cross-fitted by trajectory (two folds). Regressor: the linear features plus min(256, max(16, n / 8)) random Fourier features, the same capacity for every model and capacity-matched between the with / without-residual fits; ridge penalty chosen by an inner split of the training fold by trajectory. Error floor 1 % of variance; clipped at -1 | the same for z(t + deltas); a linear regressor; history gain (z at the two lags); CLOSURE GAP f^{a+b}(phi(x_t)) vs f^b(phi(x_{t+a})) in y and z; MARKOV ROLLOUT CONSISTENCY (restarting the model's own rollout from its predicted z must reproduce it; a model that carries memory beyond z fails and its k is invalid) |
| E microstate equivalence | ratio of the mean future readout divergence of the 2 % closest latent pairs to that of random pairs (same draw, different pool trajectories) | PCA-k matched and output-matched pairs; numerical floor |
| F latent dimension / compression | the method's selected k (and range); k / N_observed | the method's dimension curve; the evaluator's k-sweep (config `k`) where run; DIMENSION-CHEATING GUARD: prediction error when Gaussian noise of sd sigma x sd(z) is added to z0 (sigma 0.01-0.2); reported Lipschitz bounds |
| G reproducibility | across training seeds (3 at Level B, 5 for the locked method): mean CCA correlation of latent states and linear cross-prediction R^2 in both directions. Alignment is fitted on PUBLIC validation data and measured on hidden test data | k agreement; readout-prediction disagreement |
| H robustness | A and C on out-of-distribution families (real H_stim_ood / H_weight_ood; synthetic noise_heldout) relative to in-distribution | PARAMETER-IDENTITY PROBE: cross-validated decodability of the parameter draw from z in the pools, against chance |
| I cross-mechanism invariance | shared-dynamics model (config sharing='shared') against independent models on the systems of one group: paired differences in A and C; parameter counts | leave-one-implementation-out: encoder-only adaptation (config adapt_from) on 25 % of the held-out implementation's training data, against a from-scratch model on the same data |
| J cross-connectome invariance | the rule of I for the full systems of net1 and net2 (independent reconstructions); models 1-4 of goal4 section 18 (independent; same k independent f; shared f; partially shared f where supported) | net3 (same reconstruction as net1) reported apart; nulls |
| K synthetic ground truth | latent recovery: cross-fitted (by trajectory) R^2 of the true latent from z at 12 times per held-out non-intervention trajectory (linear, and linear + random-feature with a data-adapted number of features and an inner-CV ridge penalty); dimension recovery: k = k_true, or k_true in the reported range | R^2 of z from the true latent (extra content); CCA; lifting: spread of the TRUE latent shift across distinct lifts of one requested shift |
| L failure / abstention | abstention recall on non-compressible controls; false-alarm rate on compressible systems; confident-wrong rate (a compact claim that fails the interventional or closure criterion) | per trap: handled (verdict) or abstained |

Latent-intervention lifting (goal4 sections 13-14) is scored where `StateModel.lift` exists:
- the achieved latent shift against the requested one, re-encoded from the simulated microstate after the lift and compared with the
  twin;
- the model's rollout from z + dz against the simulator after the lift;
- the future divergence across distinct lifts of one shift, against the divergence across different shifts.

A method without lifting is reported as not supporting it.

## 5. References and controls (goal4 sections 49-50, 77)

The evaluator trains these on public training data (`brainir_state.refmodels`) and evaluates them on the same hidden data:
- the full-state ceiling: a learned autoregressive model of the full active state INCLUDING the readout. It is a control, and the
  only model that may see y;
- the input-only predictor;
- the readout-history predictor;
- PCA-k and random-projection-k linear latent models, with k = the method's k;
- the persistence floor.

Nulls for sharing: shared dynamics fitted across UNRELATED synthetic systems (the three unrelated pairs), which the sharing rule
must reject.

## 6. Pre-registered calibration of the tolerances (goal4 section 7: from baseline distributions and synthetic calibration)

The calibration runs BEFORE method development (`scripts/p3/calibrate.py`). It uses every DEV-suite system whose truth is
compressible (integer k) and closed (no hidden exogenous input). On those systems, the orchestrator fits:
- the reference models of section 5 with k = the true k;
- the TRUE-LATENT reference `refmodels.TrueLatentModel`. Its encoder is the true latent (exact on recorded samples, a ridge probe
  elsewhere); its transition and readout are MLPs of the ceiling's class and budget; events act through the probe.

The tolerances are computed from these fits, never from real hidden data and never from any candidate method:
- tau_A = max(0, 90th percentile over systems of (A_truelatent - A_full) / A_full);
- tau_C = 75th percentile of the true-latent reference's held-out effect error;
- tau_D = 90th percentile of the true-latent reference's micro-gain;
- tau_E = 90th percentile of the true-latent reference's microstate ratio.

The values, the per-system baseline distributions and the code hashes are in `calibration.json`, locked in BENCHMARK_LOCK.json. Only
the tolerance values (`public/tolerances.json`) are public.

**Outcome (45 dev systems, 2026-09-24):** tau_A = 1.31, tau_C = 3.18, tau_D = 0.085, tau_E = 0.0039.

- tau_A: a model that has the true state but learns its transition generically is often 1.5-2.3x worse at multi-step prediction
  than the full-state ceiling (which also sees the readout).
- tau_C: held-out intervention effects are hard even with the true state and generic intervention handling. The true-latent
  reference's median effect error is 1.6, and the full-state ceiling's is 1.2. tau_C therefore does not bind, and the binding
  interventional condition is that the CI of C lies below 1.
- tau_E: equivalence as tight as the true state's (90th percentile).

## 7. Verdicts (per system; goal4 sections 74-75, 79, 85.50; `harness.verdict`)

Each condition uses the hidden-test values and 95 % CIs:
- compact state: k <= max(1, N_observed / 5). This applies to full and synthetic systems. Mechanism systems are too small for a
  compression criterion and are judged on the other conditions only.
- predictive: A <= A_full x (1 + tau_A), and A is below both shortcut controls (the paired CI of the difference excludes 0).
- interventional: C <= tau_C, the CI of C lies below 1, and no held-out intervention pair was abstained on.
- closed: D <= tau_D.
- microstate-equivalent: E <= tau_E.

The verdicts are:
- **compact causal state discovered**: all five conditions hold;
- **partially supported**: predictive holds, and at least one of interventional / closed holds;
- **not supported**: otherwise.

A method's own abstention is recorded as such and is never converted into a verdict it did not claim.

Cross-mechanism sharing (I) is **supported** when all of the following hold:
- the shared model is non-inferior to the independent models on A and C in every system: the upper CI of the paired difference is
  <= tau_A x the independent A, and <= 0.05 in C;
- it has fewer parameters;
- encoder-only adaptation beats a from-scratch model for at least half of the held-out implementations, and is worse for none.

Otherwise sharing is **rejected**. It is **untestable** if the method cannot fit shared dynamics or reports no parameter counts.
The same rule applies to cross-connectome sharing (J).

## 8. Statistics (goal4 section 68)

- Experimental units:
  - synthetic: the system instance, paired across methods on the same instances;
  - real: the trajectory within a system; the start times and pairs of one trajectory are resampled together.

  Real networks are not replicates. Per-network results are reported separately, and cross-network pooling is descriptive.
- CIs: percentile bootstrap with 2,000 resamples of the unit. Ratios use sums over units. Paired differences use the same units for
  both models.
- Primary comparisons are between the locked method and the strongest baseline (fixed at Level B, before Level C):
  - families A, C, D and E on real hidden data, per full system;
  - family K on the synthetic final suite (paired by instance).

  Holm correction is applied across these comparisons. Everything else is descriptive.
- Non-inferiority margins: tau_A (relative) for prediction; 0.05 in effect error for C.

## 9. Method selection, hyper-parameters, dimension rule (goal4 sections 15, 56, 64)

- Hyper-parameter search is allowed on Level A data only, and its budget is recorded.
- Each method selects k by its own GENERIC rule, stated in its notes before Level B (e.g. the smallest k whose validation metric is
  within the method's tolerance of the plateau). The rule is locked with the method. k is never chosen manually.
- Level B selection runs in rounds (successive halving, goal4 section 58). All fits run in the sandbox (`brainir_state.runner`).
  - Round 1 (pilot): every submitted candidate, seed 0, on the PILOT subset of the heldout suite. The subset is the 16 systems whose
    catalogue names are linear_k3, damped, hopf, bistable_1d, leaky, perfect_2d, gated, wta, slow_fast, nuisance_ou, nonmarkov,
    output_shortcut, time_index, hidden_exogenous, highdim_chaotic and multicycle_planar. It was fixed here before any candidate
    existed. Candidates in the lower half of the mean rank (below) are eliminated.
  - Round 2: the survivors on every heldout system (seed 0). Seeds 1-2 are used on the first 8 compressible systems (G). Shared
    fits cover the two implementation groups and the three unrelated pairs, with leave-one-implementation-out fits for the groups
    (I).
  - Round 3 (optional): the composer's hybrid, if any, with the round-2 finalists, under the round-2 design.
  - A candidate is eligible if at least 90 % of its fits succeed within the time limits: 30 min per synthetic fit and 60 min per
    shared fit, on 3 threads.
  - Aggregate profile over the heldout systems:
    - S1: median A / A_full over compressible systems;
    - S2: median held-out C;
    - S3: median D;
    - S4: median E ratio;
    - S5: median K latent recovery (random-feature R^2 of the true latent);
    - S6: dimension exact-or-in-range rate;
    - S7: abstention quality = (recall on non-compressible + (1 - false-alarm rate)) / 2;
    - S8: fraction of sharing verdicts that are correct (both groups supported, all unrelated pairs rejected).
  - The selected method has the best mean rank over S1-S8 among eligible candidates. Ties are broken by fewer transition
    parameters.
  - Baselines are the methods that the developer assignments (`research/phase3/contracts/agent_prompts/`) name as baselines of
    goal4 section 23: lin_pcadyn, lin_dmdc, lin_falds, ks_hankel, nn_aelin, nn_rssm and nn_seqbottleneck, plus any method whose
    notes declare it a baseline before round 1. The reference controls of section 5 are also reported.
  - The strongest baseline for the Level C comparisons is the best-ranked eligible baseline of the last round that is not itself
    the selected method.
- Developers receive only the aggregate profiles S1-S8 and verdict counts, never per-instance values.
- At most 3 Level B rounds are run, each logged in `research/phase3/LEVELB_LOG.md`. The selection uses the last round in which the candidates were compared under the same design. Level C is never used for selection or tuning.

## 10. Lock and evaluation counts (goal4 sections 57, 86)

- Method lock before Level B confirmation and Level C: `research/phase3/METHOD_LOCK.json`, tag `brainir-state-v1-preblind`. It
  records source hashes, configuration, dimension rule, objective, hyper-parameters, training and simulator budgets, intervention
  training split, evaluator version, seeds and package environment.
- Level B confirmation and Level C run once each. Every hidden evaluation is appended to `research/phase3/HIDDEN_EVALUATIONS.md`. A
  repeated attempt must be logged with its reason. Any method change after Level C is v2.
- The hidden salt is committed by its sha256 in `BENCHMARK_LOCK.json` and revealed after Level C.

## 11. Public files (may enter a clean room)

Public:
- this PROTOCOL.md;
- `public/` (system definitions, the dev suite's seed, tolerances);
- the public evaluator code: `brainir_state.api`, `data`, `protocol`, `evaluate`, `evaluate_cross`, `evaluate_lift`, `harness`,
  `refmodels`, `simclient`;
- the synthetic DEV suite's public trajectories, twins and pools;
- the real public train / val / twin trajectories;
- the regenerated candidates (anonymised).

NOT public:
- `hidden/`, `generator/`, `calibration.json`;
- every synthetic truth directory and the heldout / final suites;
- the orchestrator modules (`realsim`, `realgen`, `simservice`, `store`, `synthsim`, `suite_eval`, `runner`, `runguard`,
  `evaluate_synth`);
- every Phase 1-2 answer-bearing file.
