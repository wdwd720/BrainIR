# state_discovery benchmark, VERSION 2 — pre-registered evaluation protocol (Phase 3, goal4.md)

Version 1 of this protocol was frozen before any state-discovery method was developed (goal4 sections 6-7; git tag
`state-discovery-benchmark-v1`). Two early independent reviews then examined the evaluation machinery: E (statistics) and H
(numerical methods), `research/phase3/reviews/E_early.md` and `H_early.md`. They found errors that would have made pre-registered
claims invalid. Version 2 corrects them. It was locked before ANY held-out (Level B) or hidden (Level C) evaluation had run, and
before any candidate was scored on held-out data. Section 10 lists every change.

The locked hashes are in `BENCHMARK_LOCK.json` (git tag `state-discovery-benchmark-v2`). The directory keeps its version-1 name.
Any change after this lock is a new benchmark version. Only the files listed as PUBLIC in section 11 may enter a development clean
room.

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
| held-out interventions on the state or the input (C, in the verdict) | kick_group, current_group, group_silence, kick_newtarget, silence_newtarget, combined_heldout |
| held-out STRUCTURAL interventions (C_structural, reported, not in the verdict) | edge_remove |
| out of distribution (H) | noise_heldout |

Edge removal changes the dynamics law itself rather than the state. goal4 section 11 asks for it "where supported". Version 2
therefore scores it as a separate family. A model that does not support it is recorded as abstaining there, and this does not affect
the verdict.

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
- the readout variance per dimension, floored at 1e-3 x its maximum. It is computed without finite BLOW-UP trajectories: those whose
  max |y| or max |x| exceeds 100 x the median over the system's training trajectories. They stay in the data;
- the PCA basis of x;
- the whitening of E's distances: the full covariance of the model's encodings, the scaled readout and the PCs at the encoding times of
  up to 64 training trajectories, with an eigenvalue floor of 1e-8 x the largest.

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
| R (a, b) | (50, 200) ms | (0.25, 1.0) s |
| E future | 250 ms | 1.0 s |

Bold values are the primary ones.

| family | primary metric | also reported |
|---|---|---|
| A multi-step predictive sufficiency | window NMSE of the readout over the primary horizon after encoding at t0 (non-intervention hidden families), capped at 10 per window | other horizons; the references of section 5 and a persistence floor on the same data; counts of capped / non-finite windows |
| B readout sufficiency | NMSE of g(phi(x_{<=t})) against y_t | |
| C interventional fidelity | normalised EFFECT error sum(d_pred - d_true)^2 / sum d_true^2 over the primary window after the first event, on held-out targets / types of STATE / INPUT interventions. d = intervened - twin; 1 = predicting no effect; a non-finite prediction makes C non-finite (failure) | post-intervention NMSE; in-distribution families (real H_*_A); per family; structural interventions apart (C_structural); event kinds the model does not support count as abstentions; skipped late pairs; n_eff = (sum d)^2 / sum d^2 and the largest pair's share of the denominator |
| D approximate Markov closure | fractional error reduction when predicting y(t + task horizon) if the residual microstate is added to (z_t, u_t, future input). The residual = the top-10 public PCs of x minus their cross-fitted prediction from (z, u), scaled by the PCs' spread. The future input over (t, t + horizon] (mean and last value) is a feature of every fit. Readout targets keep the PUBLIC readout scale (no re-standardisation on test points). Cross-fitted by trajectory (two folds), REPEATED 5 times with new folds and random features; per-point errors are averaged over the repeats. Regressor: the linear features plus min(256, max(16, n / 8)) random Fourier features, the same capacity for every model and capacity-matched between the with / without-residual fits; ridge penalty chosen by an inner split of the training fold by trajectory. Error floor 0.01; clipped at -1. 95 % CI by resampling trajectories (clusters of points) | the same for z(t + deltas); a linear regressor; history gain (z at the two lags); CLOSURE GAP f^{a+b}(phi(x_t)) vs f^b(phi(x_{t+a})) in y and z; MARKOV ROLLOUT CONSISTENCY (restarting the model's own rollout from its predicted z must reproduce it; a model that carries memory beyond z fails and its k is invalid) |
| E microstate equivalence | ratio of the mean future readout divergence of the 2 % closest latent pairs to that of random pairs (same draw, different pool trajectories). Distances are WHITENED with the training covariance (section 4 normalisers), so E does not change under invertible linear maps of z. 95 % CI by resampling pool trajectories within their draw (the matched set is recomputed in every resample). E is UNTESTABLE when the matched pairs are not close (median matched / median random latent distance > 0.2: the pool is too sparse for the latent's dimension) or when random pairs diverge less than 2 x the numerical floor | PCA-k matched (effective k reported) and output-matched pairs, whitened the same way; numerical floor; the resolution ratio |
| F latent dimension / compression | the method's selected k (and range); k / N_observed | the method's dimension curve; the evaluator's k-sweep (config `k`) where run; DIMENSION-CHEATING GUARD: prediction error when Gaussian noise of sd sigma x sd(z) is added to z0 (sigma 0.01-0.2; sd(z) over all test encodings); reported Lipschitz bounds |
| G reproducibility | across training seeds (3 at Level B, 5 for the locked method): mean CCA correlation of latent states and linear cross-prediction R^2 in both directions. Alignment is fitted on PUBLIC validation data and measured on hidden test data | k agreement; readout-prediction disagreement |
| H robustness | A and C on out-of-distribution families (real H_stim_ood / H_weight_ood; synthetic noise_heldout) relative to in-distribution | PARAMETER-IDENTITY PROBE: cross-validated decodability of the parameter draw from z in the pools, against chance |
| I cross-mechanism invariance | shared-dynamics model (config sharing='shared') against independent models on the systems of one group: paired differences in A and C; parameter counts | leave-one-implementation-out: encoder-only adaptation (config adapt_from) on 25 % of the held-out implementation's training data, against a from-scratch model on the same data |
| J cross-connectome invariance | the rule of I for the full systems of net1 and net2 (independent reconstructions); models 1-4 of goal4 section 18 (independent; same k independent f; shared f; partially shared f where supported) | net3 (same reconstruction as net1) reported apart; nulls |
| K synthetic ground truth | latent recovery: cross-fitted (by trajectory) R^2 of the true latent from z at 12 times per held-out non-intervention trajectory (linear, and linear + random-feature with a data-adapted number of features and an inner-CV ridge penalty); dimension recovery: k = k_true, or k_true in the reported range | R^2 of z from the true latent (extra content); CCA; lifting: spread of the TRUE latent shift across distinct lifts of one requested shift |
| L failure / abstention | abstention recall on non-compressible controls; false-alarm rate on compressible systems; confident-wrong rate (a compact claim that fails the interventional or closure criterion) | per trap: handled (verdict) or abstained |

Latent-intervention lifting (goal4 sections 13-14) is scored where `StateModel.lift` exists. The base run, every lift and its twin
share the protocol's own end time, hence one noise realisation:
- the achieved latent shift against the requested one, re-encoded from the simulated microstate after the lift and compared with the
  twin. It is read one sample after a kick, and at the end sample of a current;
- the model's rollout from z + dz against the simulator after the lift;
- the future divergence across distinct lifts of one shift, against the divergence across different shifts.

A method without lifting is reported as not supporting it.

## 5. References and controls (goal4 sections 49-50, 77)

The evaluator trains these on the public train + val trajectories, like a method's fit, leaving out finite blow-ups
(`brainir_state.refmodels`). It evaluates them on the same hidden data:
- the full-state ceiling: a learned autoregressive model of the full active state INCLUDING the readout. It is a control, and the
  only model that may see y;
- the input-only predictor;
- the readout-history predictor. Both shortcut predictors have one direct ridge model per step up to the longest horizon;
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

The references are fitted on train + val without blow-ups. The tolerances are computed from these fits, never from real hidden data
and never from any candidate method (version 2):
- tau_A = max(0, 90th percentile over systems of (A_truelatent - A_full) / A_full);
- tau_C = 75th percentile of the true-latent reference's held-out effect error on state / input interventions;
- tau_D = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's micro-gain (the verdict judges D's upper bound);
- tau_E = 90th percentile of the UPPER 95 % CI bound of the true-latent reference's microstate ratio, over the systems where that E
  is testable.

Each tolerance gets a 95 % CI by resampling the calibration systems. The calibration also records:
- the verdict distribution of the true-latent reference and of the full-state ceiling under the calibrated tolerances;
- the true-latent verdicts at both CI ends of every tolerance (a pre-registered sensitivity analysis).

The values, the per-system baseline distributions and the code hashes are in `calibration.json`, locked in BENCHMARK_LOCK.json. Only
the tolerance values (`public/tolerances.json`) are public. The same tolerances are applied to the real systems, which have another dt,
other horizons and no true latent. Real verdicts are therefore CONDITIONAL on the synthetic calibration, and the report says so.

**Version 1 outcome (45 dev systems, 2026-09-24; superseded):** tau_A = 1.31, tau_C = 3.18, tau_D = 0.085, tau_E = 0.0039.

**Version 2 outcome (45 dev systems, 2026-09-25, on Modal):**

| tolerance | value | 95 % CI |
|---|---|---|
| tau_A | 0.784 | [0.26, 2.30] |
| tau_C | 3.29 | [2.03, 34.1] |
| tau_D (upper-bound rule) | 0.400 | [0.27, 0.55] |
| tau_E (upper-bound rule) | 0.0179 | [0.0063, 0.027] |

- **Verdicts of the true-latent reference:**
  - compact causal state discovered: 2;
  - the same with E untestable: 1;
  - partially supported: 28;
  - not supported: 14.
- **Verdicts of the full-state ceiling:** compact with E untestable 2, partially supported 30, not supported 13.
- **Binding condition:** interventional, which the true-latent reference fails on 41 of 45 systems (its median effect error is 1.58).
  Held-out intervention effects are hard to predict even with the exact state and a generic event probe. Predictive fails on 12
  systems (the shortcut test on 9), closed on 5. E is testable on 44 of 45.
- **Sensitivity:** the verdict counts barely change at either end of any tolerance's CI (`calibration.json`).

## 7. Verdicts (per system; goal4 sections 74-75, 79, 85.50; `harness.verdict`)

Each condition uses the hidden-test values and 95 % CIs (version 2):
- compact state: k <= max(1, N_observed / 5). This applies to full and synthetic systems. Mechanism systems are too small for a
  compression criterion and are judged on the other conditions only.
- predictive: A <= A_full x (1 + tau_A), and A is below both shortcut controls (the paired CI of the difference excludes 0).
- interventional (held-out STATE / INPUT interventions): C <= tau_C, the upper CI of C lies below 1, and no such pair was abstained on.
- closed: the upper CI of D <= tau_D.
- microstate-equivalent: the upper CI of E <= tau_E. If E is untestable (section 4), the condition is untested.

The verdicts are:
- **compact causal state discovered**: all five conditions hold;
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

  Real networks are not replicates. Per-network results are reported separately, and cross-network pooling is descriptive.
- CIs: percentile bootstrap with 2,000 resamples of the unit. Ratios use sums over units. Paired differences use the same units for
  both models. Bootstrap p-values are (1 + count) / (1 + B).
- The PRIMARY FAMILY compares the locked method with the strongest baseline, which is fixed at Level B, before Level C. It has 13
  one-sided NON-INFERIORITY tests: the null is "the method is worse than the baseline by at least the margin", on a lower-is-better
  scale:
  - A, C, D and E on real hidden data, per full system (3 x 4 = 12). Differences are paired on the same trajectories (A, C), on the
    same sampled points with a trajectory-cluster bootstrap (D), or on the same pool with a cluster bootstrap within draw (E).
    Margins:
    - A: 0.2 x the baseline's A;
    - C: max(0.05, 0.2 x the baseline's C);
    - D: 0.05 (gain units);
    - E: 0.2 x the baseline's E.
  - K (random-feature R^2 of the true latent) on the synthetic FINAL suite, paired by system instance. The difference is the
    baseline's minus the method's R^2, each clipped to [-1, 1]; a failure counts as -1. The margin is 0.05, and the bootstrap
    resamples systems.

  Holm correction at alpha = 0.05 is applied across the 13 tests. A test that cannot be computed stays in the family with p = 1: a
  missing result, an untestable E, or no common units.
- Two-sided superiority p-values for the same 13 comparisons form a SECONDARY family (Holm within). Everything else is descriptive.

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
  - A candidate is eligible if at most 10 % of its fits AND evaluations fail. Time limits: 30 min per synthetic fit and 60 min per
    shared fit, on 3 threads.
  - Aggregate profile over the FIXED list of the round's compressible heldout systems, the same list for every candidate (paired). A
    failed fit, a failed evaluation or a non-finite value counts as the WORST value: +inf for S1-S4, -inf for S5, "not in range" for
    S6:
    - S1: median A / A_full;
    - S2: median held-out C (state / input interventions);
    - S3: median D;
    - S4: median E ratio, over the systems where the candidate's E is testable (the untestable count is reported);
    - S5: median K latent recovery (random-feature R^2 of the true latent);
    - S6: dimension exact-or-in-range rate;
    - S7: abstention quality = (recall on non-compressible + (1 - false-alarm rate)) / 2;
    - S8: balanced accuracy of the sharing verdicts, i.e. the mean of the correct rates over the implementation groups (supported)
      and over the unrelated pairs (rejected).
  - The selected method has the best mean rank over S1-S8 among eligible candidates. Ranks:
    - ties get average ranks;
    - a non-finite value ranks last, tied with the other non-finite values;
    - a component that is non-finite for every candidate (S8 in the pilot) is dropped;
    - ties in the mean rank are broken by fewer transition parameters (median over systems), then by name.

    The result does not depend on the order in which candidates are listed.
  - Selection uncertainty: the systems are resampled 1,000 times and S1-S6 and the ranks recomputed. This gives each candidate's
    P(rank 1), its 90 % rank interval and, in the pilot, P(eliminated).
  - Parts of one round that run separately (per developer) are merged only if they share the design: suite, pilot flag, system list,
    G systems, shared fits, simulation budget, time limit (`merge_rounds.py`).
  - The heldout values of the selected method (and of the hybrid composed after feedback) are selection-biased and are not
    performance estimates. Claims rest on the FINAL suite (Level B confirmation) and on Level C. The report discloses the number of
    candidates, rounds and feedback releases.
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

### 10.1 Version history

- **Version 1:** locked 2026-09-24 (tag `state-discovery-benchmark-v1`). It was never used for a held-out or hidden evaluation.
- **Version 2:** locked 2026-09-25 (tag `state-discovery-benchmark-v2`), after the early reviews E and H. At that point:
  - the candidate methods were in development on the public data;
  - no candidate had been scored on held-out data;
  - no hidden real data existed.

  The developers were told the changes of the public evaluator (not the reviews). The changes:

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
