# state_discovery benchmark, VERSION 3 — pre-registered evaluation protocol (Phase 3, goal4.md)

Version 1 of this protocol was frozen before any state-discovery method was developed (goal4 sections 6-7; git tag
`state-discovery-benchmark-v1`). Version 2 (tag `state-discovery-benchmark-v2`) corrected errors found by the early independent
reviews E (statistics) and H (numerical methods) before any held-out evaluation. Version 3 corrects the blockers and major issues of
the four PRE-LOCK reviews A (system identification), B (causal inference), C (representation learning) and D (computational
neuroscience), `research/phase3/reviews/{A,B,C,D}_prelock.md`. When version 3 was locked:
- the Level B held-out suite had been used for selection rounds 1-3 under version 2 (selection only; the scores of that round are
  re-computed under version 3, section 9);
- no method had been locked;
- the Level B FINAL suite had never been used;
- no hidden real data existed.
Section 10.1 lists every change of every version.

The locked hashes are in `BENCHMARK_LOCK.json` (git tag `state-discovery-benchmark-v3`). The directory keeps its version-1 name.
Any change after this lock is a new benchmark version. Only the files listed as PUBLIC in section 11 may enter a development clean
room.

The benchmark scores a *state model* of a system s:
- an encoder z_t = phi_s(x_{<=t}, u_{<=t}) from the observed microstate and the input;
- transition dynamics z_{t+dt} = f(z_t, u_t, events);
- a readout y_t = g_s(z_t, u_t).

The interface is `brainir_state.api.StateModel`. The benchmark does NOT score neuron identities. Its hidden evaluations use data the
method never saw: held-out stimuli, initial states, new i.i.d. parameter draws, intervention targets and types, microstate restarts
and implementations (and, on synthetic systems, noise realisations).

## 1. Levels (goal4 section 56)

| level | data | who sees what | use |
|---|---|---|---|
| A development | synthetic DEV suite (public trajectories incl. its test / twin / pool splits; truth outside the room); real public train / val / twin trajectories; the budgeted simulation service (public policy only) | method developers | any development, hyper-parameter search, self-evaluation with the public evaluator code |
| B selection | synthetic HELDOUT suite (secret seed; never in a clean room) | the orchestrator runs it; developers get aggregate profiles only | tournament selection (section 9); at most 3 selection rounds, each logged |
| B confirmation | synthetic FINAL suite (secret seed) | run ONCE on the locked method and the baselines | confirmation |
| C real hidden test | hidden trajectories of the connectome-constrained rate-model systems, generated AFTER the method lock from a secret salt (committed now by sha256) | run ONCE on the locked method, the strongest baseline and the reference controls; logged | the real-circuit result |

"Real" names the systems built from real connectomes. They are SIMULATIONS of a rate model on connectome-derived weights (section
2.1), not recordings. Every Level C statement is a statement about those connectome-constrained rate-model simulations and is
reported next to the model's assumptions; none is a statement about the animal's circuit.

## 2. Systems

### 2.1 Real (connectome-constrained rate-model simulations)

For each public network d in {net1, net2, net3}:
- `real:<d>:full`: the intact network;
- `real:<d>:mech:<h8>`: the keep-only network of every candidate mechanism that passes a fixed rule. A candidate is regenerated from
  public evidence by the locked Phase 2 method (seed 0, budget 1000, public no-gate rhythm criterion; `research/phase3/candidates/`).
  It is kept if it passes keep-only on at least half of 8 fresh public parameter seeds. No candidate is chosen by hand.

d is an anonymised name of one of the three networks of the frozen tier-A public benchmark bundle. The mapping stays outside every
clean room in `hidden/network_map.json`. There are 10 systems: 3 full, and 2, 3 and 2 mechanism systems on net1, net2 and net3.

Populations are set by a deterministic public probe rule (`brainir_state.realgen.build_systems`):
- observed x = the non-readout, non-stimulus neurons whose peak rate exceeds 0.01 Hz in any of 9 probe trajectories (3 seeds x
  stimulus scales 0.6, 1.0 and 1.4). About half of them peak below 1 Hz; k / N_observed is also reported against the neurons that
  peak above 1 Hz (descriptive);
- readout y = the network's readout neurons that are active in its full system's probes; every system of a network uses the same
  list (mechanism systems inherit it; the number of readout dimensions with non-zero training variance is reported);
- input u = the stimulus current.

The model (the Phase 1 simulator): a first-order threshold-linear-tanh RATE ODE with one global synaptic gain times the signed
synapse count; per-neuron time constants, gains, thresholds and maximal rates are MODEL PARAMETERS (assumed, drawn per trajectory,
never anatomy). There are no synaptic or adaptation dynamics, no spiking, and no process or observation noise: the real engine is
deterministic. Every trajectory has its own parameter draw, and hidden trajectories use NEW i.i.d. draws from the same distribution.

LINEAGE (reported in every Level C row): net1 and net3 are two builds of ONE reconstruction (same animal, same synapse table,
different annotation snapshots); net2 is an independent reconstruction of another animal. The mechanism systems of one network are
overlapping keep-only variants from one Phase 2 run (they share neurons) and count as ONE mechanism family. No claim may count net1
and net3 as two confirmations, or several mechanisms of one network as independent observations. Real cross-network evidence rests
on two independent reconstructions and is descriptive (goal4 section 67).

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

SCOPE of the synthetic intervention evidence (version 3, review D M2): synthetic neurons couple only through a low-rank population
signal, and kicks, currents and silencing all act through it, so held-out GROUP interventions are additive compositions of
single-neuron operators at the level of the perturbation. Level B claims about held-out intervention types are therefore scoped to
"held-out targets and additive group compositions of single-neuron interventions in population-code systems"; they are not
evidence of type generalisation in circuits with thresholds and rectification. A synthetic kick that pushes a saturating neuron out
of its activation range is clipped just inside it and inverted (generator behaviour, locked). The pairs with such kicks are listed
on the truth side (`scripts/p3/kick_clip_pairs.py`, `kick_clip_pairs.json`), and the held-out C without them is reported as a
pre-registered sensitivity analysis (descriptive).

The orchestrator adds a counterfactual twin to every test intervention trajectory: same protocol and noise realisation (noise_seed),
no events. It also adds the microstate pools of section 3.3.

## 3. Protocol families and splits (goal4 sections 27, 29, 51)

### 3.1 Real

Intervention targets: the full system's observed population is split by a public seeded permutation into A (development targets)
and B (held out). For mechanism systems, A = all members, so their *_B families use the public targets (section 7 roles).

| family | split | description |
|---|---|---|
| nominal | public | stimulus onset U[0.01, 0.15] s, scale 1 |
| stim_amp | public | scale U[0.6, 1.4], optional step change, optional early offset (persistence) |
| init_state | public | stimulus from t = 0; initial microstate from the system's own states (70 %) or random sparse rates |
| kick_A | public | 1-3 kicks of +-U[5, 30] Hz on 1-3 A neurons |
| pulse_A | public | 1-2 current pulses U[5, 40] (depolarising only) for U[10, 150] ms into 1-2 A neurons |
| silence1_A | public | one A neuron silenced (temporary or to the end) |
| weight_noise | public | multiplicative weight noise sd U[0.02, 0.1] |
| H_nominal, H_init_state | hidden | as above with new i.i.d. parameter draws and states |
| H_kick_A, H_pulse_A, H_silence1_A | hidden | public intervention types on public targets, new draws (in-distribution control) |
| H_kick_B, H_pulse_B, H_silence1_B | hidden | held-out TARGETS (full systems; in-distribution on mechanism systems) |
| H_group_silence | hidden | 2-4 neurons silenced together (held-out TYPE) |
| H_stim_ood | hidden | stimulus scale U[1.5, 2.0] or U[0.3, 0.5] (out of distribution; it may recruit neurons outside x, whose share of the activity is reported) |
| H_weight_ood | hidden | weight noise sd U[0.15, 0.25] (out of distribution) |
| H_micro | hidden | microstate-equivalence pools (section 3.3) |

KICKS are instantaneous rate offsets whose result is clipped at 0 (`brainir_state.protocol`: r = max(0, r + d)). An event record
states the REQUESTED offset, in the public and in the hidden data alike; the hidden data also record the APPLIED offsets in each
trajectory's info (`kicks_applied`, never passed to a model). Many negative kicks on quiet neurons, and many single-neuron silencing
events on neurons that are not firing, are therefore (near) no-ops: the number of NULL pairs (pairs carrying < 0.1 % of a system's
effect denominator) is reported per family, with C over the non-null pairs (descriptive). Real kicks are absolute (Hz); synthetic
kicks are scaled to each neuron; real currents are depolarising only.

Public trajectories per full system: 340 train and 85 val. Mechanism systems have half as many. Validation interventions have twins
(split `twin`).

Hidden trajectories: 30 per family per full system and 15 per mechanism system. Every hidden intervention trajectory has a
counterfactual twin (same seed, state and inputs, no events, the event breakpoints kept). Public seeds are < 10^9; hidden seeds are
>= 10^9 and derive from the secret salt.

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
| held-out interventions on the state or the input (C, in the verdict) | kick_group, current_group, group_silence, kick_newtarget, silence_newtarget, combined_heldout; only the pairs whose events act on OBSERVED neurons (version 3) |
| held-out interventions with a target outside the observed population (C_unobserved, reported, not in the verdict) | the same families |
| held-out STRUCTURAL interventions (C_structural, reported, not in the verdict) | edge_remove |
| out of distribution (H) | noise_heldout |

Edge removal changes the dynamics law itself rather than the state. goal4 section 11 asks for it "where supported". It is scored as
a separate family. A model that does not support it is recorded as abstaining there, and this does not affect the verdict. The
effect of an event on a neuron outside the observed population cannot be identified from x (review B M2); such pairs are scored
apart.

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
- each state is restarted from its FULL microstate (all neurons; the rate vector is the model's complete state) under the common
  nominal input for 250 ms;
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

ROLLOUT ISOLATION (version 3; reviews A B1, B M1). Every rollout and readout of a method's model runs on a FRESH copy of the model
as it was before the evaluation's first encode call (a pickle snapshot, `evaluate.Fresh`). Nothing an encode call stores in the
model object can reach a prediction: a prediction is a function of (z0, inputs, events) and the fitted parameters. State kept at
module or class level is outside this guard; the decoy check (R) and the code audit of the locked method cover it. The evaluator's
own reference controls (`refmodels`) are trusted and not copied.

Normalisers come from public training data only:
- the readout scale. SYNTHETIC systems: the variance per dimension, floored at 1e-3 x its maximum. REAL systems (version 3, review
  D B1): POOLED, i.e. every dimension gets the mean training variance, so an NMSE is sum(squared error) / sum(training variance) and
  near-silent readout neurons are not weighted up to 1000x; C under the version-2 per-dimension normaliser (floors 1e-3 and 1e-2)
  and each dimension's share of the effect denominator are reported (sensitivity). Both are computed without finite BLOW-UP
  trajectories: those whose max |y| or max |x| exceeds 100 x the median over the system's training trajectories. They stay in the
  data;
- the PCA basis of x;
- the whitening of E's distances: the full covariance of the model's encodings, the scaled readout and the PCs at the encoding times of
  up to 64 training trajectories, with an eigenvalue floor of 1e-8 x the largest;
- the mean and per-coordinate variance of the model's encodings of those training trajectories (the scrambled-state control of C and
  the latent scale of the Markov checks).

Window errors (A, B, C post-NMSE, R) are capped at NMSE 10. A non-finite prediction counts as the cap. Such a unit is never dropped,
and the counts are reported.

Time constants are fixed per data kind (`harness.REAL_CFG` / `harness.SYNTH_CFG`):

| constant | real | synthetic |
|---|---|---|
| A horizons | 10, 50, 100, **250**, 500 ms | 0.1, 0.25, 0.5, **1.0**, 2.0 s |
| encoding times t0 | 0.3 / 0.6 / 0.9 / 1.2 s | 0.5 / 1.0 / 1.5 / 2.0 s |
| C windows | 100, **250**, 500 ms | 0.25, 0.5, **1.0** s |
| D task horizon | 100 ms | 0.5 s |
| D latent deltas | 10 / 50 ms | 0.05 / 0.25 s |
| D history lags | 10 / 20 ms | 0.05 / 0.1 s |
| D start | 0.25 s | 0.25 s |
| R (a, b) | (50, 200) ms | (0.25, 1.0) s |
| E future | 250 ms | 1.0 s |

Bold values are the primary ones.

| family | primary metric | also reported |
|---|---|---|
| A multi-step predictive sufficiency | window NMSE of the readout over the primary horizon after encoding at t0 (non-intervention hidden families), capped at 10 per window | other horizons; the references of section 5 and the persistence floor on the same data and units; the LEVEL-CORRECTED NMSE (each window's mean error per readout dimension removed; review D B2); counts of capped / non-finite windows |
| B readout sufficiency | NMSE of g(phi(x_{<=t})) against y_t | |
| C interventional fidelity | normalised EFFECT error sum(d_pred - d_true)^2 / sum d_true^2 over the primary window after the first event, on held-out targets / types of STATE / INPUT interventions with OBSERVED targets (real mechanism systems: group silencing only, section 7). d = intervened - twin; 1 = predicting no effect; a non-finite prediction makes C non-finite (failure) | post-intervention NMSE; in-distribution families; per family; structural interventions and unobserved-target pairs apart; abstentions; skipped late pairs; pairs in the primary window; n_eff = (sum d)^2 / sum d^2 and the largest pair's share; the LEAVE-ONE-PAIR-OUT maximum of C; NULL pairs and C over the non-null pairs; STATE DEPENDENCE (version 3, review B B1): C with z0 replaced by the mean training encoding and by another pair's z0, and the paired difference C - C_scrambled with its CI; the INTERVENTIONAL CLOSURE GAP (the model's latent a rollout interval after the first event against the encoding of the intervened history, relative to the twin's encoding; review A M5); alternative normalisers (real); the kick-clip sensitivity (synthetic) |
| D approximate Markov closure | fractional error reduction when predicting y(t + task horizon) if the residual microstate is added to (z_t, u_t, future input). The residual = the top-10 public PCs of x minus their prediction from (z, u), computed INSIDE each training fold (an inner two-fold split by trajectory for the training rows, a fit on all training rows for the test rows; version 3), scaled by the PCs' spread. The future input over (t, t + horizon] (mean and last value) is a feature of every fit. Readout targets keep the PUBLIC readout scale. Cross-fitted by trajectory (two folds), REPEATED 5 times with new folds and random features; per-point errors are averaged over the repeats. Regressor: the base (z, u, future input) plus min(256, max(16, n / 8)) random Fourier features, the same capacity for every model and capacity-matched between the with / without-residual fits. The ridge penalty (chosen by an inner split of the training fold by trajectory) applies to every column EXCEPT the base, which is fitted without shrinkage while it has at most 1 column per 4 fitted rows (version 3: otherwise extra columns that merely repeat z "help" by undoing the shrinkage of the base; this artefact produced large gains for the true state). Error floor 0.01; clipped at -1. 95 % CI by resampling trajectories (clusters of points). The HISTORY GAIN is the same with z at the two history lags added instead of the residual | the same for z(t + deltas); a linear regressor |
| R rollout checks (version 3) | MARKOV CONSISTENCY: the model's own rollout, restarted at t0 + a from its predicted z on a fresh copy, must reproduce the continued rollout (largest per-coordinate squared difference relative to the training variance of z, and y NMSE), and the same after held-out interventions (restart a after the end of the last event, on the rollout-restart grid); DECOY CONSISTENCY: the rollout from z0 made right after re-encoding the history must equal the rollout from z0 made after other histories were encoded. markov_ok = all within 1e-4. A model that fails carries memory beyond z: its k is invalid | CLOSURE GAP f^{a+b}(phi(x_t)) vs f^b(phi(x_{t+a})) in y (NMSE) and z; READOUT CONSISTENCY (the rollout's y against readout(z, u)); the noise curve (F) |
| E microstate equivalence | ratio of the mean future readout divergence of the 2 % closest latent pairs to that of random pairs (same draw, different pool trajectories). Distances are WHITENED with the training covariance, so E does not change under invertible linear maps of z. 95 % CI by resampling pool trajectories within their draw (the matched set is recomputed in every resample). E is UNTESTABLE when the matched pairs are not close (median matched / median random latent distance > 0.2) or when random pairs diverge less than 2 x the numerical floor | PCA-k matched (effective k reported) and output-matched pairs, whitened the same way; numerical floor; the resolution ratio |
| F latent dimension / compression | the method's selected k; k / N_observed (real: also against the neurons peaking above 1 Hz); k is INVALID when markov_ok fails | the method's reported range (descriptive: never scored); its dimension curve; DIMENSION-CHEATING GUARD: prediction error when Gaussian noise of sd sigma x sd(z) is added to z0 (sigma 0.01-0.2), with the ratio at sigma = 0.05 reported as noise fragility; reported Lipschitz bounds |
| G reproducibility | across training seeds (3 at Level B, 5 for the locked method): the smaller of the two linear cross-prediction R^2 directions (r2_min), k agreement and the readout-prediction disagreement (version 3, review A M3). Alignment is fitted on PUBLIC validation data and measured on hidden test data | mean canonical correlation PADDED with zeros up to max(k_a, k_b); at Level C also a DATA-RESAMPLING arm (the locked method fitted on seeded half-samples of the training trajectories) |
| H robustness | A and C on out-of-distribution families (real H_stim_ood / H_weight_ood; synthetic noise_heldout) relative to in-distribution | PARAMETER-IDENTITY PROBE: cross-validated decodability of the parameter draw from z in the pools, against chance |
| I cross-mechanism invariance | shared-dynamics model (config sharing='shared') against independent models on the systems of one SYNTHETIC group: paired differences in A and C; parameter counts | leave-one-implementation-out: encoder-only adaptation (config adapt_from) on 25 % of the held-out implementation's training data, against a from-scratch model on the same data. On the REAL systems (a network's full system with its nested keep-only mechanisms, which differ in size by two orders of magnitude) I is descriptive only |
| J cross-connectome invariance | the rule of I for the full systems of net1 and net2 (independent reconstructions); models 1-4 of goal4 section 18 (independent; same k independent f; shared f; partially shared f where supported) | net3 (same reconstruction as net1) reported apart; nulls |
| K synthetic ground truth | latent recovery: min(R^2 of the true latent from z, R^2 of z from the true latent), cross-fitted by trajectory at 12 times per held-out non-intervention trajectory with the linear + random-feature regressor (version 3, review C M3: a z that carries extra content costs as much as one that misses content); dimension recovery: the point k equals k_true (version 3, review C B1) | each direction and the linear regressor; CCA; k_true within the reported range and the range width (descriptive); lifting: spread of the TRUE latent shift across distinct lifts of one requested shift |
| L failure / abstention | abstention recall on non-compressible controls; false-alarm rate on compressible systems; confident-wrong rate (a compact claim that fails the interventional or closure criterion) | per trap: handled (verdict) or abstained |

Latent-intervention lifting (goal4 sections 13-14) is scored where the model's class implements `StateModel.lift`; otherwise it is
reported as unsupported. A lift requested at t_i for delta_z asks for a counterfactual latent shift. Once every lifted event has
acted (sample j: one sample after a kick, the end of a current pulse), the lifted world's latent should equal the twin's latent at
the same sample plus delta_z. The achieved shift and the do() test (the model's rollout from z_twin(j) + delta_z against the lifted
simulation) both refer to sample j. Identical event sets are dropped (version 3, review B M4). A lift whose achieved microstate
change x_lift(j) - x_twin(j) has cosine similarity above 0.99 with an earlier distinct lift of the same shift is one realisation: it
counts for the shift and fidelity statistics, not for implementation invariance. The invariance ratio compares the futures of
distinct lifts over one common window per case, starting at the latest completion sample among them. Without a same-shift pair of
distinct lifts, and without distinct lifts of both shifts, it is reported as untestable, never as a perfect score. delta_z is
scaled by the spread of z over all cases. For k = 1 the second shift is the opposite of the first. Rollouts run on fresh copies of
the model. The base run, every lift and its twin share the protocol's own end time, hence one noise realisation.

## 5. References and controls (goal4 sections 49-50, 77)

The evaluator trains these on the public train + val trajectories, like a method's fit, leaving out finite blow-ups
(`brainir_state.refmodels`). It evaluates them on the same hidden data:
- the full-state REFERENCE: a learned autoregressive model of the full active state INCLUDING the readout. It is a control, and the
  only model that may see y. On the synthetic systems it is the reference of the predictive condition. On the real systems it is NOT
  a ceiling (each trajectory's readout level depends on parameters of neurons outside x, review D B2) and is reported only;
- the input-only predictor;
- the readout-history predictor. Both shortcut predictors have one direct ridge model per step up to the longest horizon;
- PCA-k and random-projection-k linear latent models, with k = the method's k;
- the persistence floor (y held at its value at t0), evaluated on the same windows and units as a model's A.

Nulls for sharing: shared dynamics fitted across UNRELATED synthetic systems (the three unrelated pairs), which the sharing rule
must reject.

## 6. Pre-registered calibration of the tolerances (goal4 section 7: from baseline distributions and synthetic calibration)

The calibration runs on the synthetic DEV suite only, never on held-out or hidden data and never with a candidate method
(`scripts/p3/calibrate.py`). It uses every DEV system whose truth is compressible (integer k) and closed (no hidden exogenous input).
On those systems, the orchestrator fits:
- the reference models of section 5 with k = the true k, and PCA-(k-1) (version 3; power of the closure condition);
- the TRUE-LATENT reference `refmodels.TrueLatentModel`. Its encoder is the true latent (exact on recorded samples, a ridge probe
  elsewhere); its transition and readout are MLPs of the full-state reference's class and budget; events act through the probe.

The references are fitted on train + val without blow-ups. The tolerances (version 3):
- tau_A = max(0, 90th percentile over systems of (A_truelatent - A_full) / A_full);
- tau_C = 75th percentile of the true-latent reference's held-out effect error on observed-target state / input interventions. It
  does NOT bind: the interventional condition is decided by the upper CI of C lying below 1 (section 7). tau_C is not a calibration
  from a true causal state: the reference maps events through a generic linear probe, not through the generator's causal routes
  (review B M5);
- tau_D = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's micro-gain;
- tau_H = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's history gain (version 3);
- tau_gap = 90th percentile of the true-latent reference's closure gap (version 3). Pre-registered power rule: the closure gap
  enters 'closed' only if random-k passes it at least 20 percentage points less often than the true latent; otherwise tau_gap is
  null and the gap is reported only (a model whose rollouts forget their initial state has a small gap whatever its latent);
- tau_E = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's microstate ratio, over the systems where that E
  is testable.

Each tolerance gets a 95 % CI by resampling the calibration systems. The calibration also records:
- the verdict distributions of the true-latent reference, the full-state reference, PCA-k, random-k and PCA-(k-1) under the
  calibrated tolerances;
- the true-latent verdicts at both CI ends of every tolerance (a pre-registered sensitivity analysis);
- the POWER of the closure condition: the pass rates of 'closed' and of each of its parts (markov_ok, micro-gain, history gain,
  closure gap) for every reference. Pre-registered wording rule: if random-k passes 'closed' on more than 25 % of the calibration
  systems, every report calls the condition "no large microstate or history gain detected" instead of "closed";
- the Markov checks of every reference, and the effective-pair and null-pair counts of the held-out C.

The values, the per-system baseline distributions and the code hashes are in `calibration.json`, locked in BENCHMARK_LOCK.json. Only
the tolerance values (`public/tolerances.json`) are public. The same tolerances are applied to the real systems. These differ from
the synthetic calibration in ways that matter: dt 1 ms against 10 ms; one parameter draw per trajectory against 8 shared draws;
absolute-Hz kicks against neuron-scaled kicks; non-additive against additive intervention operators; near-silent readouts; a pooled
against a per-dimension normaliser. Real verdicts are therefore CONDITIONAL on the synthetic calibration, and the report says so.

**Version 1 outcome (45 dev systems, 2026-09-24; superseded):** tau_A = 1.31, tau_C = 3.18, tau_D = 0.085, tau_E = 0.0039.

**Version 2 outcome (45 dev systems, 2026-09-25, on Modal; superseded):** tau_A = 0.784, tau_C = 3.29, tau_D = 0.400 (upper-bound
rule), tau_E = 0.0179. Under version 2 the D null of the true latent was wide and positive; version 3 traced much of it to the
shrinkage artefact of section 4 (D).

**Version 3 outcome (45 dev systems, 2026-09-25, on Modal, final image, 12,741 container-s, about $1.9; an earlier run on the pre-final image gave the same tolerances to 1e-6 and the same verdict counts):**

| tolerance | value | 95 % CI |
|---|---|---|
| tau_A | 0.784 | [0.26, 2.30] |
| tau_C (does not bind) | 3.69 | [2.10, 51.0] |
| tau_D (upper-bound rule) | 0.092 | [0.051, 0.248] |
| tau_H (upper-bound rule) | 0.234 | [0.147, 0.293] |
| tau_gap | null (reported only; value 0.152 [0.062, 0.214]) | power rule failed: random-k passes the gap on 100 % of systems, like the true latent |
| tau_E (upper-bound rule) | 0.0179 | [0.0065, 0.027] |

- **Power of 'closed'** (pass rate over the calibration systems): true latent 0.80, full-state reference 0.47, PCA-k 0.44, random-k
  0.24, PCA-(k-1) 0.17 (29 systems with k >= 2). Random-k passes on at most 25 % of the systems, so reports use the word "closed".
  Under version 2 random-k passed on 25 of 45 systems. Every reference passes markov_ok on every system.
- **Verdicts of the true-latent reference:** compact causal state discovered 2; the same with E untestable 1; partially supported
  22; not supported 20. Full-state reference: compact with E untestable 1, partially supported 18, not supported 26. PCA-k: partially
  supported 6, not supported 39. Random-k: partially supported 2, not supported 43. PCA-(k-1): partially supported 1, not supported 28.
- **Held-out C design on DEV** (8 pairs per system): n_eff median 2.0 (10-90 %: 1.24-3.24); 69 null pairs in total; 5 systems have
  pairs with a target outside the observed population. The heldout and final suites have 2x and 3x as many pairs.

## 7. Verdicts (per system; goal4 sections 74-75, 79, 85.50; `harness.verdict`)

Roles: on synthetic systems and real FULL systems the held-out C uses the held-out families of section 3. On real MECHANISM systems
every observed neuron is a public target, so H_kick_B, H_pulse_B and H_silence1_B are in-distribution there, and the held-out C of
the verdict is H_group_silence only (reviews B B2, D B3; `harness.roles_for`).

Each condition uses the hidden-test values and 95 % CIs (version 3):
- markov_ok (state validity): the Markov and decoy consistency checks of R, and the restart after held-out interventions, stay within
  1e-4. If markov_ok fails, the model carries memory beyond z: k is INVALID, and compact and closed are False.
- compact state: markov_ok and k <= max(1, N_observed / 5). This applies to full and synthetic systems. Mechanism systems are too
  small for a compression criterion and are judged on the other conditions only.
- predictive:
  - synthetic: A <= A_full x (1 + tau_A), and A is below the input-only and the readout-history controls (the paired CI of each
    difference lies below 0);
  - real (version 3, review D B2): A is below the input-only control and below the persistence floor (paired CIs below 0). The
    readout-history control and the full-state reference are reported, not judged: the readout carries each trajectory's parameters
    of neurons outside x, which is a parameter, not state.
- interventional (held-out STATE / INPUT interventions on observed targets): the upper CI of C lies below 1; the leave-one-pair-out
  maximum of C lies below 1 (the claim must not rest on one pair; review B M3); no such pair was abstained on; C <= tau_C (kept for
  the record; it does not bind). With fewer than 3 pairs in the primary window the condition is UNTESTABLE (None). The claim this
  condition supports is "held-out intervention effects are predicted better than no effect". Whether the prediction depends on the
  state is reported separately: 'state_mediated' = the CI of C - C_scrambled (z0 = the mean training encoding) lies below 0.
- closed: markov_ok, the upper CI of the D micro-gain <= tau_D, the upper CI of the D history gain <= tau_H, and (if the power rule
  of section 6 admits it) the closure gap <= tau_gap. The report uses the wording of the section 6 power rule.
- microstate-equivalent: the upper CI of E <= tau_E. If E is untestable (section 4), the condition is untested.
- A model that declares `causal_equivalence_failed` or `no_compact_state` for a system cannot receive a "compact causal state"
  verdict there.

The verdicts are:
- **compact causal state discovered**: compact, predictive, interventional, closed and microstate-equivalent all hold;
- **compact causal state discovered (microstate equivalence untestable)**: compact, predictive, interventional and closed hold, and E
  is untestable. This is reported as its own category and never merged with the first;
- **partially supported**: predictive holds, and at least one of interventional / closed holds;
- **not supported**: otherwise.

A method's own abstention is recorded as such and is never converted into a verdict it did not claim.

Cross-mechanism sharing (I) is **supported** when all of the following hold:
- the shared model is non-inferior to the independent models on A and C in every system. The upper CI of the paired difference must
  be <= 0.2 x the independent A, and <= max(0.05, 0.2 x the independent C) in C;
- it has fewer parameters;
- encoder-only adaptation (f frozen, fitted on the other members) beats a from-scratch model on 25 % of the held-out member's
  training data for at least half of the held-out members, and is worse for none.

Otherwise sharing is **rejected**. It is **untestable** if the method cannot fit shared dynamics, reports no parameter counts, or
has no leave-one-out result.

The unrelated pairs (the sharing nulls) face the SAME rule, including leave-one-out; their correct verdict is "rejected". The same
rule applies to cross-connectome sharing (J).

## 8. Statistics (goal4 section 68)

- Experimental units:
  - synthetic: the system instance, paired across methods on the same instances;
  - real: the trajectory within a system; the start times and pairs of one trajectory are resampled together.

  Real networks are not replicates. Per-network results are reported separately, and cross-network pooling is descriptive. Every
  Level C row carries its lineage (section 2.1).
- CIs: percentile bootstrap with 2,000 resamples of the unit. Ratios use sums over units. Paired differences use the same units for
  both models. Bootstrap p-values are (1 + count) / (1 + B).
- The PRIMARY FAMILY compares the locked method with the strongest baseline, which is fixed at Level B, before Level C (section 9).
  It has 13 one-sided NON-INFERIORITY tests: the null is "the method is worse than the baseline by at least the margin", on a
  lower-is-better scale:
  - A, C, D and E on real hidden data, per full system (3 x 4 = 12). Differences are paired on the same trajectories (A, C), on the
    same sampled points with a trajectory-cluster bootstrap (D), or on the same pool with a cluster bootstrap within draw (E).
    Margins:
    - A: 0.2 x the baseline's A;
    - C: max(0.05, 0.2 x the baseline's C);
    - D: 0.05 (gain units);
    - E: 0.2 x the baseline's E.
  - K on the synthetic FINAL suite, paired by system instance: min(R^2 both directions) (section 4, K). The difference is the
    baseline's minus the method's value, each clipped to [-1, 1]; a failure counts as -1. The margin is 0.05, and the bootstrap
    resamples systems.

  Holm correction at alpha = 0.05 is applied across the 13 tests. A test that cannot be computed stays in the family with p = 1: a
  missing result, an untestable E, or no common units.
- REPORTING RULE for C (version 3, review C M4): a non-inferiority result on C is described as "interventional" only if the METHOD's
  own C has an upper CI below 1 on that system; otherwise it is described as "no worse than the baseline, neither better than
  predicting no effect". Every C row reports the method's C upper CI.
- The D test compares gains near 0 with a margin of 0.05; its power depends on the D CI width, which is reported with it.
- Two-sided superiority p-values for the same 13 comparisons form a SECONDARY family (Holm within). Everything else is descriptive,
  including real I-sharing.

## 9. Method selection, hyper-parameters, dimension rule (goal4 sections 15, 56, 64)

- Hyper-parameter search is allowed on Level A data only, and its budget is recorded.
- Each method selects k by its own GENERIC rule, stated in its notes before Level B (e.g. the smallest k whose validation metric is
  within the method's tolerance of the plateau). The rule is locked with the method. k is never chosen manually. A fit must be
  deterministic given its data, configuration and seed (no wall-clock-dependent branches).
- Level B selection runs in rounds (successive halving, goal4 section 58). All fits run in the sandbox (`brainir_state.runner`).
  - Round 1 (pilot): every submitted candidate, seed 0, on the PILOT subset of the heldout suite. The subset is the 16 systems whose
    catalogue names are linear_k3, damped, hopf, bistable_1d, leaky, perfect_2d, gated, wta, slow_fast, nuisance_ou, nonmarkov,
    output_shortcut, time_index, hidden_exogenous, highdim_chaotic and multicycle_planar. It was fixed here before any candidate
    existed. Candidates in the lower half of the mean rank (below) are eliminated.
  - Round 2: the survivors on every heldout system (seed 0). Seeds 1-2 are used on the first 8 compressible systems (G). Shared
    fits cover the two implementation groups and the three unrelated pairs, with leave-one-implementation-out fits for the groups
    (I).
  - Round 3: the composer's hybrid with the round-2 finalists and the declared baselines (and their independently tuned variants,
    below), under the round-2 design. Under version 3 the selection uses the round-3 run scored by the version-3 evaluator (the
    version-2 round-3 run is recorded, not used).
  - A candidate is eligible if at most 10 % of its fits AND evaluations fail. Time limits: 30 min per synthetic fit and 60 min per
    shared fit, on 3 threads.
  - Aggregate profile over the FIXED list of the round's compressible heldout systems, the same list for every candidate (paired). A
    failed fit, a failed evaluation or a non-finite value counts as the WORST value: +inf for S1-S4, -inf for S5, "not exact" for
    S6:
    - S1: median A / A_full;
    - S2: median held-out C (state / input interventions on observed targets);
    - S3: median of max(0, upper 95 % CI of the D micro-gain) (version 3, review A B2: a negative gain is noise, not "more closed");
    - S4: median E ratio, over the systems where the candidate's E is testable (the untestable count is reported);
    - S5: median K latent recovery, min(R^2 both directions) (version 3);
    - S6: the rate at which the POINT k equals k_true (version 3; the reported range and its width are descriptive);
    - S7: abstention quality = (recall on non-compressible + (1 - false-alarm rate)) / 2;
    - S8: balanced accuracy of the sharing verdicts, i.e. the mean of the correct rates over the implementation groups (supported)
      and over the unrelated pairs (rejected).
  - Ranks:
    - ties get average ranks;
    - a non-finite value ranks last, tied with the other non-finite values;
    - a component that is non-finite for every candidate (S8 in the pilot) is dropped;
    - ties in the mean rank are broken by fewer transition parameters (median over systems), then by name.

    The result does not depend on the order in which candidates are listed.
  - Selection uncertainty: the systems are resampled 1,000 times and S1-S6 and the ranks recomputed. This gives each candidate's
    P(rank 1), its 90 % rank interval and, in the pilot, P(eliminated).
  - DECISION RULE (version 3, pre-registered before the version-3 round 3; review C M5): the eligible candidate with the best mean
    rank over S1-S8 is selected if its bootstrap P(rank 1) >= 0.5. Otherwise the TIE SET is that candidate plus every eligible
    candidate with P(rank 1) >= 0.10, and the tie is resolved by PARSIMONY: the lowest median point k over the fixed system list (k
    available on at least 90 % of it), then fewer transition parameters, then the better mean rank. The ranking on S1-S5 alone and the
    leave-one-component-out rankings are reported (descriptive).
  - Parts of one round that run separately (per developer) are merged only if they share the design: suite, pilot flag, system list,
    G systems, shared fits, simulation budget, time limit, benchmark version (`merge_rounds.py`).
  - The heldout values of the selected method (and of the hybrid composed after feedback) are selection-biased and are not
    performance estimates. The hybrid's components were chosen after aggregate held-out feedback; claims rest on the FINAL suite
    (Level B confirmation) and on Level C. The report discloses the number of candidates, rounds and feedback releases.
  - BASELINES are the methods that the developer assignments (`research/phase3/contracts/agent_prompts/`) name as baselines of
    goal4 section 23: lin_pcadyn, lin_dmdc, lin_falds, ks_hankel, nn_aelin, nn_rssm and nn_seqbottleneck, plus any method whose
    notes declare it a baseline before round 1, plus their variants tuned on development data by an independent tuner without a
    competing candidate (`<baseline>_t`, notes/bt_baselines.md; review C M2). The reference controls of section 5 are also reported.
  - The STRONGEST BASELINE for the Level C comparisons (version 3, review C M2) is chosen among the baselines of the selection round
    only: eligible (at most 10 % fit + evaluation failures) and markov_ok on at least 90 % of the fixed system list (a model whose
    predictions do not go through z cannot be a state-model comparator); ranked among themselves by their mean rank over S1-S5 (the
    components the primary family tests); ties broken by fewer transition parameters, then by name. The comparison against every
    declared baseline is reported descriptively at Level B.
- Developers receive only the aggregate profiles S1-S8 and verdict counts, never per-instance values.
- At most 3 Level B rounds are run, each logged in `research/phase3/LEVELB_LOG.md`. Level C is never used for selection or tuning.

## 10. Lock and evaluation counts (goal4 sections 57, 86)

EXECUTION (version 3). Level B fits and evaluations, the calibration and the Level C fits run on Modal (`scripts/p3/modal_tournament.py`,
LEAKAGE_POLICY.md section 3.1). Modal hosts are mixed hardware; every Modal image pins numpy's SIMD dispatch and torch's kernels to the
AVX2 code paths of the development machine (`NPY_DISABLE_CPU_FEATURES`, `ATEN_CPU_CAPABILITY=avx2`), under which Modal simulations of
the real engine reproduce the stored public trajectories exactly. OpenBLAS's kernels are NOT forced (forcing them made worker processes
crash on some hosts, `research/phase3/level_c/modal_pinning_crash_experiment.json`), so dense linear algebra, and through it fits and
evaluation statistics, may differ between hosts in the last digits (fits agree to ~1e-13 in parameters; evaluation statistics to ~3e-4
relative, a D CI endpoint near 0 by up to ~0.003; `research/phase3/level_c/MODAL_BACKEND_CHECK.md`). All fits of one Level C run come
from one environment (Modal). A worker killed by a signal is re-run once in its container and then in a fresh container (up to 3
times); every such event is recorded and is an infrastructure retry, never a retry of a scientific failure. The hidden real data are generated on the pinned Modal image (`generate_real_hidden.py --backend modal`): the protocols
are built locally from the salt, simulated on Modal, and the records and the assembled dataset are written to the EVAL volume only;
the local copy is downloaded and checked against hashes computed at write time. Every test trajectory, its twin and every
microstate restart are simulated on that one platform. Before the lock this code path reproduced the stored PUBLIC records of all
ten real systems bit for bit (`research/phase3/level_c/hidden_generator_modal_smoke.json`); the local backend remains available.
Equivalence records: `research/phase3/level_c/`, `research/phase3/postlock_infra/`.

POST-LOCK ANALYSES (pre-registered here; `research/phase3/POSTLOCK_RUNBOOK.md`):
- ABLATIONS of the locked method (its own `ablate` switches) run on the synthetic FINAL suite after the Level B confirmation (the only
  data that neither selected nor tuned the method), and on the DEV suite for comparison with the developer's notes; never on the real
  hidden data. They are logged as hidden evaluations and are descriptive.
- COUNTEREXAMPLE searches (`scripts/p3/counterexamples.py`) run on synthetic dev / final systems and on the real systems with public
  parameter draws; searches with hidden real draws run after Level C, locally, and are logged. They are descriptive.
- Post-lock independent reviews (`research/phase3/review_contracts/POSTLOCK_*`) run in parallel after Level C.

- Method lock before Level B confirmation and Level C: `research/phase3/METHOD_LOCK.json`, tag `brainir-state-v1-preblind`. It
  records source hashes, configuration, dimension rule, objective, hyper-parameters, training and simulator budgets, intervention
  training split, evaluator version, seeds and package environment.
- Level B confirmation and Level C run once each. Every hidden evaluation is appended to `research/phase3/HIDDEN_EVALUATIONS.md`. A
  repeated attempt must be logged with its reason. Any method change after Level C is v2.
- The hidden salt is committed by its sha256 in `BENCHMARK_LOCK.json` and revealed after Level C.

### 10.1 Version history

- **Version 1:** locked 2026-09-24 (tag `state-discovery-benchmark-v1`). It was never used for a held-out or hidden evaluation.
- **Version 2:** locked 2026-09-25 (tag `state-discovery-benchmark-v2`), after the early reviews E and H, before any held-out
  evaluation. Used for selection rounds 1-3 on the heldout suite.
- **Version 3:** locked 2026-09-25 (tag `state-discovery-benchmark-v3`), after the pre-lock reviews A-D. At that point no method was
  locked, the FINAL suite had never been used and no hidden real data existed. The developers were told the changes of the public
  evaluator (not the reviews).

Version 2 changes:

| finding | change |
|---|---|
| E B1: ranks broken by list order | average ranks, non-finite last, all-non-finite components dropped, tie-break implemented; permutation test |
| E B2: non-finite predictions dropped from A | window errors capped at 10, non-finite = cap, counts reported |
| E B3: medians over each method's own systems | fixed system list with worst-value imputation; evaluation failures count for eligibility |
| E B4: Level C family not implemented | 13 non-inferiority tests with margins, D / E / K paired tests, uncomputable = p 1 in the family, secondary superiority family |
| E B5, H B1: D and E point estimates, E coordinate-dependent | D averaged over 5 repeated cross-fits with a cluster CI; E whitened with training covariance, cluster CI within draw; verdicts on upper CI bounds; tau_D / tau_E recalibrated on upper bounds |
| H M7: E cannot pass for k >= 4-6 with a finite pool | testability rule (untestable, not failed) and a separate verdict category |
| E M1: tolerance uncertainty; transfer to real | tolerance CIs, sensitivity at the CI ends, real verdicts declared conditional |
| E M2: the oracle could never pass (edge removal) | structural interventions scored apart; the oracle's and ceiling's verdict distributions recorded |
| E M3, H M4: C carried by few pairs | n_eff and the largest share reported per system; limitation |
| E M4: sharing margins mis-scaled; nulls without leave-one-out | relative margins; leave-one-out for the unrelated pairs; S8 balanced |
| E M5: no ranking uncertainty | selection bootstrap; selection-bias statement |
| E M6: merges across designs | design recorded and checked |
| H M2: readout-history control handicapped | one direct model per step |
| H M3, m4: D diluted by constant dims and input changes | public readout scale for D targets; future input features |
| H M5: diverged training trajectories set the normaliser | robust readout scale; references fitted without blow-ups |
| H M6: lifting mixed two noise realisations | one common end time for base, lifts and twins |
| H m1: real twins lacked the event breakpoints | twins keep the breakpoints (hidden real data are generated with it; the public twins keep a <= 0.011 Hz pre-event difference) |
| H m2, m3, m5, m6, m8; E minors | current lifts read at the end sample; noise guard scale over all encodings; effective PCA k; E floor guard; closure start in the config; references on train + val; p-value floor; k = 0 kept; reference cache keyed by the evaluator's code; explicit keys |
| H M1: a numerical property of some synthetic kick events | kept (the generator is locked; the behaviour is deterministic and present in the training kicks too); reported as a limitation |

Version 3 changes (pre-lock reviews A-D):

| finding | change |
|---|---|
| A B1, B M1: no test of hidden memory; stateful side channels | rollout isolation on fresh copies; Markov restart (z and y) and decoy checks, also after interventions; markov_ok gates k, compact and closed |
| A B2: 'closed' powerless, ignores history; S3 rewards noise | history-gain condition (tau_H); closure-gap condition subject to a pre-registered power rule (tau_gap); power table and wording rule; S3 = max(0, upper CI of D) |
| (found while fixing A B2) D artefact: shrinkage of the base made collinear columns "help" | the base of every D regression is fitted without shrinkage (guarded by rows per column) |
| A minor: D residual leakage across folds | residual computed inside each training fold |
| A M3: G's CCA inflated | r2_min, k agreement and prediction disagreement as headline; CCA padded; data-resampling arm at Level C |
| A M4, C B1: S6 / K reward wide ranges | S6 and dimension recovery on the point k; range descriptive |
| A M5: no closure check under interventions | interventional closure gap (reported); Markov restart after interventions (judged) |
| B B1: C does not show a causal STATE | claim worded as "held-out effects predicted better than no effect"; tau_C declared non-binding; state-dependence control C_scrambled reported |
| B B2, D B3: mechanism systems' *_B families are not held out | role table per system mode; mechanism held-out C = group silencing only |
| B M2: unobservable targets mixed into C | observed-target pairs in the verdict; unobserved-target pairs reported apart |
| B M3: C rests on 1-3 pairs | leave-one-pair-out condition; untestable with < 3 pairs; n_eff and null pairs reported |
| B M4: lifting gameable by identical lifts | identical and near-identical lifts rejected; untestable instead of perfect |
| B M5: tau_C not from a causal state | stated as a limitation (section 6) |
| C M2: comparator chosen on components Level C does not test; baselines untuned | comparator ranked on S1-S5 among markov-valid baselines only; independent baseline tuning on dev data |
| C M3: K saturated and one-directional | K = min(R^2 both directions) in S5 and in the primary family |
| C M4: C non-inferiority passable by two no-effect models | reporting rule: "interventional" only with the method's own C upper CI < 1 |
| C M5: selection fragile, no decision rule | pre-registered bootstrap decision rule with a parsimony tie-break; rankings without S6-S8 reported |
| D B1: real readout NMSE dominated by near-silent neurons | pooled real normaliser; per-dimension shares and floor sensitivity reported |
| D B2: real predictive condition unattainable (readout carries hidden parameters) | real predictive = below input-only and persistence; readout-history and full-state reference descriptive; level-corrected A reported |
| D M1: real kicks clipped and often null | clip documented; applied deltas recorded in the hidden data; null pairs and non-null C reported |
| D M2: synthetic group types additive; kick-clip artefact | Level B claim scoped; kick-clip sensitivity pre-registered |
| D M3: "real" overstated | wording "connectome-constrained rate-model simulations"; model assumptions stated; "noise realisations" removed from the real hold-outs |
| D M4: dependent systems; real I not pre-registered | lineage fields; net1 + net3 never two confirmations; real I descriptive |
| B m5, D m2, m6 and other minors | pairs in the primary window counted; k / N against active neurons; active readout count reported |

## 11. Public files (may enter a clean room)

Public:
- this PROTOCOL.md;
- `public/` (system definitions, the dev suite's seed, tolerances);
- the public evaluator code: `brainir_state.api`, `data`, `protocol`, `evaluate`, `evaluate_cross`, `evaluate_lift`, `harness`,
  `refmodels`, `simclient`;
- the synthetic DEV suite's public trajectories, twins and pools;
- the real public train / val / twin trajectories;
- the regenerated candidates (anonymised);
- the notices to developers (`notes/_evaluator_v2.md`, `notes/_evaluator_v3.md`) and the aggregate tournament feedback.

NOT public:
- `hidden/`, `generator/`, `calibration.json`;
- every synthetic truth directory (including `kick_clip_pairs.json`) and the heldout / final suites;
- the orchestrator modules (`realsim`, `realgen`, `simservice`, `store`, `synthsim`, `suite_eval`, `runner`, `runguard`,
  `evaluate_synth`);
- the reviews and the per-system tournament results;
- every Phase 1-2 answer-bearing file.
