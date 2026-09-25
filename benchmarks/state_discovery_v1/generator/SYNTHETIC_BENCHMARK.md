# p3synth — synthetic state-discovery benchmark (author documentation, TRUTH-SIDE)

This document describes the generator and contains ground-truth information (families, traps, groups). It is for the
benchmark authors and evaluators and must not be handed to method developers. Method developers get only the public
dataset directory (`manifest.json`, `index.jsonl`, `traj/`).

## 0. Files

| path | content |
|---|---|
| `p3synth/core.py` | engine: `Implementation`, `Model`, `SyntheticSystem` (x-space RK4 simulation, events, `lift_latent`) |
| `p3synth/latents.py` | latent dynamics, one class per dynamical family / trap latent |
| `p3synth/blocks.py` | auxiliary (non-causal) coordinate blocks: nuisance, null codes, readout copy, clock, stimulus copy, parameter report |
| `p3synth/embeddings.py` | observation maps (E, D, activations, baselines, noise, partial observation, permutation) |
| `p3synth/systems.py` | the catalogue of 48 systems (all 20 families, traps A-L, 2 implementation groups, 3 unrelated pairs) |
| `p3synth/protocol.py` | protocol validation (reference schema + signed r0, vector stimuli, evaluator-only latent events) |
| `p3synth/suite.py` | `build_suite(out_public, out_truth, seed, tier)`: protocol planning, splits and hold-outs |
| `p3synth/dataset.py` | public writer (only t, x, u, y; format of `data_format.md`) |
| `p3synth/truth.py` | truth writer (the only code that writes truth) and `system_truth()` |
| `p3synth/diagnostics.py` | independent latent-space reference solver (scipy DOP853), accuracy and timing reports |
| `tests/` | 237 tests (section 9) |
| `example_suite/public`, `example_suite/truth` | example suite, tier "dev", seed 0 |
| `reports/accuracy_timing.json` | integration accuracy and single-trajectory timings per system |

CLI: `uv run python -m p3synth --public <dir> --truth <dir> --seed 0 --tier dev [--scale s] [--workers w]`.
Python: `from p3synth import build_suite, get_system, build_all`.

## 1. What a system is

A system has coordinates `c in R^K`: `c[:k] = z` is the causal latent state, the remaining `K - k` coordinates belong to
auxiliary blocks (nuisance processes, persistent null codes, trap neurons). The latent follows the documented dynamics
`dz/dt = f(z, u; theta) (+ Sigma dW)`, auxiliary blocks follow their own dynamics, which may read `z`, `u` or `theta`
but never feed back into `z`. The readout is `y = g(z; theta)` (noise-free in this release).

`SyntheticSystem` exposes `system_id` (opaque), `n`, `observed`, `readout_dim`, `input_dim`, `simulate(protocol)`,
`truth()` and `lift_latent(delta_z, x, weight_noise=None, active=None)`.

## 2. Implementation by neurons (x-space simulation)

Every neuron `i` has an activation `v_i`; its recorded state is `x_i = phi_i(v_i)`, where `phi_i` is a per-neuron
bijection: identity, scaled tanh `s tanh(v/s)` (signed, saturating) or scaled logistic `s / (1 + e^-v)` (positive rate,
saturating). Neurons communicate deviations from baseline. The population signal is

    c = D (v - b)            D: K x N "synaptic readout" (sparse or dense), E: N x K embedding, D E = I_K

and the ODE actually integrated, neuron by neuron, is

    dv_i/dt = E_i . ( F(c, u, exo) + lam c )  -  lam (v_i - b_i)  +  I_i(t)   (+ synaptic noise E Sigma dW + private noise)

**Exactness.** `dc/dt = D dv/dt = D E F + lam D E c - lam D (v - b) = F(c)`. The population signal therefore follows the
claimed dynamics exactly, whatever the microstate. The off-manifold part `w = v - b - E c` satisfies `D w = 0` and
decays as `exp(-lam t)`. `lam` (20-50 /s) is uniform within a system, which is what makes the decomposition exact. The
manifold `v = b + E c` is flat in activation space and curved in recorded (x) space when `phi` saturates.

**Why micro interventions matter.** Neuron `j` enters the population signal through the column `D[:, j]`, so a kick
`dv_j` moves `c` by `D[:, j] dv_j` and injected current moves it at rate `D[:, j] I_j`. Silencing removes neuron `j` from
the sum. Neurons with `D[:k, j] = 0` (nuisance, copy, clock, stimulus-copy, parameter-report and carrier-only neurons)
cannot move `z`, whatever is done to them. Tests verify this for every one of these roles.

**Recorded latent.** `z(t)` in the returned dict (and in truth) is the causal population signal `c[:k] = D'(v - b)`.
During silencing it excludes the silenced neurons, because that is the signal the dynamics actually use.

**Noise.** (i) latent process noise `Sigma dW`, injected through `E` (correlated synaptic noise) with sd per sqrt(s)
drawn with the parameters; (ii) private per-neuron noise, which leaks into `c` through `D` and is capped so that the
leak is at most half the latent process noise; (iii) iid Gaussian observation noise on the recorded `x` only. The
observation-noise sd is 3-30% of each neuron's typical modulation. Without a `noise_seed`, all three are seeded by the
canonical protocol plus the system seed, and so is the hidden exogenous input of family 19.

**noise_seed (optional protocol field, int >= 0).** When it is present, every random realisation of the trajectory is
drawn from one generator seeded by (system seed, noise_seed) instead of the canonical protocol. That covers latent
process noise, private noise, observation noise, readout noise (currently zero) and the family-19 exogenous input. The
draws happen once, in a fixed order, with array shapes that depend only on `t_end`, `dt`, the substep, N, K and the
observed set, never on the events. Two protocols that differ only in their events and share a noise_seed therefore
share one noise realisation exactly: they are bitwise identical up to and including the sample at the first event
time (tested for kick, current, silence and edge removal). A change of stimulus, parameters or r0 with the same
noise_seed keeps the noise draws but changes the dynamics. `weight_noise` keeps its own seed (it is structural, not a
trajectory realisation).

**Structural (weight) noise.** `weight_noise {sd, seed}` perturbs the existing synapses: `D' = D * (1 + sd xi)`. The
recorded latent `c = D'(v - b)` then obeys the closed ODE `dc/dt = A F(c) - lam (I - A) c`, `A = D'E`, which is
verified against scipy (tests). For example, the perfect integrator becomes leaky or unstable. `A` is stored per
trajectory in truth.

**Integrator.** Classical RK4 on the activations with a fixed substep `h = dt / ceil(dt / h_max)`. `h_max` is
min(5 ms, family limit, 0.3 / lam, 0.3 x the fastest auxiliary time constant): 5 ms for most systems, 1.5 ms for the
slow/fast system, 2 ms for van der Pol and the bifurcation system, 2.5-3 ms where fast nuisance/copy blocks exist.
Additive noise is added after each substep (Euler-Maruyama split; weak order 1 for the noise, RK4 for the drift).
Inputs, currents, silencing and edge removal are piecewise constant on the output grid, so each RK4 step sees a smooth
right-hand side.

## 3. Protocols and interventions

Schema as in `protocol_spec.md`, validated by `p3synth.protocol.validate`. Differences from `reference/protocol.py`:
r0 values may be negative (signed activations), stimulus values may be lists of length `input_dim`, and the latent event
kinds are accepted by the simulator but rejected by `validate(..., allow_latent=False)`. The suite builder always
validates public protocols with `allow_latent=False`. The optional field `noise_seed` (integer >= 0; section 2) is
accepted, and when present it is part of the canonical form, so `canonical_json` and `protocol_hash` include it.
Without the field the canonical form, the hash and the simulation are exactly as before. `reference/protocol.py`
drops unknown fields, so evaluators must use `p3synth.protocol.validate` to keep it. `dt` is 0.01 s and `t_end` 4 s
in the built suites.

* **r0** `zero`: the default rest state `v = b + E c_rest(theta)`. `c_rest` is the family's rest point: the stable
  fixed point, one well of a bistable system, or a point on the cycle for autonomous oscillators; the clock starts
  at 0. `state`: the listed neurons are set to the given x values (clipped into the activation range), the others stay
  at rest. The suite's random initial states set all N neurons to `phi(b + E c0 + w)`, where `w` is a small random
  off-manifold component (`D w = 0`).
* **stimulus**: piecewise constant from each listed time. A scalar scales the system's nominal input pattern; a list is
  the input vector. The recorded `u(t_i)` is the value applied on `[t_i, t_i + dt)`.
* **kick** `x_j += d` right after the sample at `t` (the sample at `t` is pre-kick). Saturating neurons are clipped just
  inside their range.
* **current**: `I` is added to `dv_j/dt` (activation units per second) during `[t0, t1)`.
* **silence** during `[t0, t1)` (`t1 = null`: to the end):
  1. the neuron's output is removed: its `(v_j - b_j)` contributes nothing to any population sum;
  2. all its inputs are cut: population drive, stimulus, synaptic noise and injected current;
  3. its activation relaxes to baseline, `dv_j/dt = -lam (v_j - b_j)` (private noise continues), and the recorded x
     shows this relaxation;
  4. at `t1` it reconnects with whatever state it has, so the off-manifold remainder perturbs `c` (rebound).

  For the latent this gives `dz/dt = (I - D_S E_S) f(z) - lam D_S E_S z` (verified by test). The effect grows with the
  silenced share of the code.
* **edge_remove** `[post i, pre j]` during `[t0, t1)`: neuron `i` computes its population signal without neuron `j`,
  `c^(i) = c - D[:, j](v_j - b_j)`, so its drive is `E_i (F(c^(i)) + lam c^(i))`. A structural edge exists iff
  `D[:, j] != 0` and `E_i != 0`. Removing a non-existent edge, or one whose coordinates the post neuron does not use,
  has no effect (tested).
* **latent_set** `{t, values {i: v}}` (do(z_i := v)) and **latent_impulse** `{t, delta}` (evaluator only). The
  microscopic change is `dv = E_act (D'_act E_act)^-1 dc`, applied to the active (non-silenced) neurons, where `dc` is
  zero outside the targeted latent indices. The latent therefore moves exactly by `dc` and no other coordinate moves.
  This holds also under weight noise and during silencing. `lift_latent(delta_z, x, weight_noise, active)` returns the
  same change in x units (`phi(v + dv) - x`). Tests check that applying it as a microscopic kick reproduces the latent
  intervention to within 1e-6.

## 4. Families (all 20)

Parameters: each system has a centre `theta_0` drawn from its seed; `params_seed` redraws `theta = theta_0 * exp(s eps)`
with typical `s` = 0.1-0.2 for time scales and gains and 0.3 for noise. The latent TYPE never changes. Oscillation
frequencies are 0.4-1.6 Hz and time constants 0.1-1 s, with fast variables at 15-30 ms (slow/fast) and 10-20 ms (trap
neurons).

| # | internal name(s) | latent f (k) | readout g | observation map (N / observed) |
|---|---|---|---|---|
| 1 | linear_k1, linear_k3, linear_k6 (+ distributed, pairP3_b) | `dz = A z + B u`, A stable, real modes tau 0.15-1 s and oscillatory modes 0.4-1.5 Hz (k = 1, 3, 6; 4 for trap L) | `C z` | dense identity 10; sparse logistic 40/32; dense tanh 150 |
| 2 | harmonic (+ pairP3_a) | `dz1 = w z2, dz2 = -w z1 + w g u`, f0 0.7-1.5 Hz (k=2) | z1 | redundant copies, positive, 30 |
| 3 | duffing | conservative hardening Duffing `dz2 = -w(z1 + beta z1^3) + w g u` (k=2) | z1 | dense tanh 60 |
| 4 | damped (+ pairP1_a, nonmarkov) | linear damped oscillator, zeta 0.08-0.25 (k=2) | z1 | sparse mixed-sign identity 25, obs noise 10% |
| 5 | hopf, vanderpol (+ groupA, pairP1_b, traps I, J) | Hopf normal form mu 3-6 /s; van der Pol mu 0.8-2 rescaled to amplitude 1 (k=2) | z1 | dense logistic 50; distributed 80 + 10 nuisance |
| 6 | bistable_1d, toggle (+ pairP2_b, trap F) | `tau dz = z - z^3 + g u`; mutual-inhibition toggle `tau dz_i = -z_i + S(beta(1/2 - z_j) + g u_i)` (k=1, 2) | z; z1 - z2 | redundant tanh 20; sparse logistic 45 |
| 7 | leaky (+ pairP2_a, traps D, H) | `tau dz = -z + g u`, tau 0.3-0.8 s (k=1) | z | dense identity 15 |
| 8 | perfect_1d, perfect_2d | `dz = g M u` (k=1, 2) | z | dense positive 35; sparse tanh 70/49 |
| 9 | gated (+ groupB) | `dz = g sigmoid(12(u2 - 0.5)) u1 - z/tau_leak`, tau_leak 4-8 s (k=1, u = (signal, gate)) | z | dense logistic 40 |
| 10 | wta | `tau dz_i = -z_i + logistic(a z_i - c sum_{j!=i} z_j + g u_i - 3)`, stable null state, self-sustaining winner (k=3) | z | sparse logistic 90, 40% carrier-only neurons |
| 11 | controller | plant `tau_p dp = -p + c + d`, PI `c = kp(r - p) + q`, `dq = ki(r - p)`, u = (r, d) (k=2) | p | dense tanh 50 |
| 12 | slow_fast (+ trap K) | excitable FitzHugh-Nagumo, tau_f 15-30 ms, tau_s 0.4-0.8 s (k=2) | v | dense identity 60/45 |
| 13 | nuisance_ou, nuisance_rhythm (trap A) | damped oscillator / leaky integrator plus 3-6 OU nuisance coordinates (sd 2.5-3, one set stimulus-driven) and a 2-4 Hz nuisance rhythm | as base | 30 latent + 40 nuisance neurons (nuisance also mixed into latent neurons); 60 + 140 |
| 14 | redundant_switch, redundant_integrator (trap E) | double well / perfect integrator; 3 or 2 persistent null-code coordinates mixed into many copies | z | redundant copies, 120 / 80 |
| 15 | groupA_impl0-3, groupB_impl0-2 | ONE Hopf latent shared by 4 implementations; ONE gated integrator shared by 3 | as base | see section 7 |
| 16 | nonmarkov (trap G) | damped oscillator (zeta 0.1); z2 represented about 17x more weakly than z1 | z1 | dense 40, obs noise 10% |
| 17 | output_shortcut (trap B) | 3-D stable linear system (one oscillatory pair) + 4 readout-copy neurons (tau 10 ms, high gain) | `C z` (1-D) | dense 40 + 4 |
| 18 | time_index (trap C) | leaky integrator + clock coordinate `dc/dt = 1` carried by 6 ramping logistic neurons with staggered onsets; training stimuli time-locked | z | dense 25 + 6 |
| 19 | hidden_exogenous | damped oscillator driven by `u` AND a hidden unit-variance OU process e(t) (tau 0.5 s), independent per trajectory, carried by no neuron and not in u | z1 | dense 40 |
| 20 | highdim_chaotic, highdim_linear | `tau dz = -z + g W tanh(z) + B u`, N = 200, g ~ 3 (W realisation verified chaotic: separation grows > 1e3 in 12 s from 4 initial conditions at +-6% gain); 60-D linear system with flat spectrum tau 0.2-2 s, all modes driven by noise and inputs and read out | `W_out tanh z` (2); `C z` (3) | identity 200 (neurons are units); dense random rotation 60 |

Families 1-12 also appear inside traps and pairs with other observation maps.

## 5. Adversarial traps

Every trap is principled: it is a real property of the system, not a filter tuned against any method. The "fools" column
is what `tests/test_traps.py` demonstrates with a simple representation learner.

| trap | system | construction | how it fools a representation learner (tested) |
|---|---|---|---|
| A high-variance non-causal nuisance | nuisance_ou, nuisance_rhythm | OU / rhythm nuisance with sd 2.5-3x the latent, carried by dedicated neurons and mixed into latent neurons; D ignores it | the top-2 PCs explain < 30% of z's variance and > 80% is nuisance; kicking or silencing nuisance neurons leaves y exactly unchanged |
| B readout copy | output_shortcut | 4 neurons follow y with 10 ms lag and large gain | copy neurons predict y one step ahead with R^2 > 0.9, but 0.6 s ahead z beats them by > 0.3 R^2; they are non-causal |
| C clock | time_index | ramping clock neurons; training stimuli time-locked (nominal schedule, only amplitude varies) | clock neurons decode t (R^2 > 0.9); a time-indexed model predicts y with R^2 > 0.8 on time-locked trials and < 0.3 on shifted-stimulus (test) trials |
| D stimulus copy | stimulus_copy | 3 neurons low-pass u (20 ms) | copy neurons explain u (R^2 > 0.9) and part of y; non-causal |
| E many microstates, one causal state | redundant_switch, redundant_integrator | persistent null-code coordinates (dc = 0 + slow diffusion) mixed into redundant copies; D is orthogonal to them | two microstates differing by > 30% of the population's scale for the whole trial give identical z and y |
| F hysteresis | hysteresis | bistable memory z1 and a probe-gated output `tau2 dz2 = -z2 + g2 u2 z1`, y = z2; z1 weakly represented | identical y (to 1e-9) for z1 = +1 and -1 until probed; opposite outputs after the same probe; the same zero input leaves either state |
| G non-Markov compression | nonmarkov | z2 embedded at 6% gain | PC1 carries > 10x the variance of PC2; a 1-D AR model on PC1 gives one-step R^2 > 0.95 but 40-step R^2 < 0.3, while the 2-D latent AR gives > 0.8 |
| H parameter encoding | parameter_trap | set point s ~ N(0, 1.5^2) redrawn per params_seed; 4 neurons report s | parameter neurons predict mean y across draws (R^2 > 0.9) yet are constant within a trajectory and non-causal: s is a parameter, not state |
| I multiple limit cycles | multicycle_planar, multicycle_switch | concentric stable cycles r = 0.5 and 1.5 (unstable r = 1); a 3-D system with two equal-amplitude cycles of different frequency selected by a weakly represented switch | nearby initial conditions reach different cycles; in the 3-D case the two cycles have the same y amplitude (within 0.02) but frequencies differ by > 30% |
| J transient vs cycle | transient_cycle | subcritical-Hopf-like: stable rest, unstable cycle r = 0.8, stable cycle r = 1.4 | same phase, amplitudes 0.7 vs 0.9: one decays to rest, the other oscillates for ever |
| K bifurcation | bifurcation | Rayleigh oscillator with input-controlled damping mu(u) = -25 + 28 u | at u = 0 the trajectories lie on a 1-D slow manifold (PC1 > 99%); at u = 1 on a 2-D limit cycle (PC2 > 20%) |
| L distributed code | distributed | k = 4 with +-1-pattern loadings on 200 neurons, 6 nuisance coordinates mixed into every neuron, obs noise 30% | no neuron correlates > 0.6 with any latent; the best 5-neuron readout reaches < 50% of the population readout's R^2 |

Family 19 (hidden exogenous variable) is the remaining trap. Knowing (z, u) leaves a large one-step residual, which
knowing e(t) removes (tested). A method should report an unexplained input or abstain rather than invent neural state.

## 6. Observation maps

`embeddings.make_implementation` combines the following, and they vary across the suite (a test checks that each kind
is present):

* **code** (z -> latent neurons):
  * `dense`: Gaussian rows, signed or non-negative;
  * `sparse`: each neuron tuned to 1 coordinate, or 2 with probability 0.3;
  * `redundant`: groups of near-identical copies with 5% jitter;
  * `distributed`: +-1 patterns;
  * `rotation`: a dense orthogonal mix, for the 60-D control;
  * `identity`: neurons are the units, for the chaotic control.

  Row norms are 0.6-1.4. `core_gain` weakens individual latent coordinates (traps F, G, I).
* **activation** `identity | tanh | logistic`, per system or mixed. Logistic neurons get activation modulation 1.5-3 so
  they are strongly nonlinear.
* **sign**: mixed-sign tuning with signed baselines, or non-negative tuning with positive baselines (rate-like).
* **causal fraction**: in `wta` and `groupA_impl3` only 60% / 50% of latent neurons feed the population signal. The rest
  are carriers (E != 0, D = 0): they look exactly like latent neurons but are not causal.
* **auxiliary neurons**: nuisance, copy, clock and parameter neurons, optionally mixed into the latent neurons.
* **observation noise** (3-30% of modulation) and **partial observation**: 20-30% of latent/nuisance neurons unobserved
  in linear_k3, perfect_2d, slow_fast, groupA_impl1 and groupB_impl2. Trap neurons are always observed.
* **permutation** of neuron ids (always).

N ranges from 10 to 300 (observed 10-240). k ranges from 1 to 6 for compressible systems; K = N = 200 and 60 for the
controls.

## 7. Shared latent dynamics and unrelated pairs

* **grp-A (Hopf):** impl0 dense identity, N = 16, lam 25. impl1 sparse logistic, 100 latent + 20 nuisance, 30%
  unobserved, lam 35. impl2 redundant tanh, 60, obs noise 20%, lam 50. impl3 distributed, 200 latent (50%
  carrier-only) + 40-neuron nuisance rhythm mixed in, lam 20.
* **grp-B (gated integrator):** impl0 dense identity, 20. impl1 sparse tanh, 90 + 30 nuisance. impl2 distributed
  logistic, 300, 25% unobserved.

Members share one `Latent` object, so the same `params_seed` gives identical `theta`. Given the same latent initial
state and input, their z and y agree to 1e-5, the level of integration error, since members use different substeps
(tested). Their N, code, activation, nuisance, noise, lam and permutation differ (tested). In truth they share
`implementation_group`, and `truth.json` lists the groups.

**Unrelated pairs:** P1 damped oscillator vs Hopf cycle (both 1.0 Hz); P2 leaky integrator vs bistable switch; P3
harmonic oscillator vs 2-D non-oscillatory linear system. Both members of a pair have the identical implementation
(same E, D, b, activations, observed set, dims) and different latent dynamics, verified through vector-field and
trajectory differences. Different `implementation_group`; `truth.json` lists the pairs.

## 8. Suite builder

`build_suite(out_public, out_truth, seed, tier)`:

* tiers `dev` (scale 1), `heldout` (x2) and `final` (x3). The seed and tier change every draw (latent centres,
  embeddings, ids), never the system types.
* one worker process per system (default: all cores). Each worker: builds the system, runs 2 pilot simulations to
  measure every neuron's x and v variability (this sizes kicks and currents), plans the protocols, simulates, writes the
  public npz and the truth npz, and returns index rows.
* **system ids** `syn-<10 hex>` (hash of tier, seed, name); trajectory keys are 20-hex hashes; the dataset id hashes
  (tier, seed). The public `family` field is a protocol label (below). `group` and `network` are null, `readout` is `[]`.
* **protocol families per system at dev scale**, 53 per system:
  * train (32): nominal 3, init 7, stim 5, param_draw 5, weight_noise 2, kick 4, current 3, silence_single 3;
  * val (7): nominal, init 2, stim, kick, current, silence_single;
  * test (14): init_heldout 2, param_heldout 2, noise_heldout, kick_group 2, current_group, group_silence 2,
    edge_remove, kick_newtarget, silence_newtarget, combined_heldout (held-out params + held-out init + group
    silencing).

  Stimuli: 35% the nominal schedule (amplitude x0.7-1.3, shifted -0.3..0.8 s), 55% 1-3 random pulses or steps
  (50 ms-1.2 s, family-specific channel kinds: analog, positive or binary gates), 10% no input. The time-locked trap
  (C) uses only the unshifted nominal schedule in train/val and shifted schedules in test. 40% of intervention
  trajectories also start from a random initial state. Kicks are +-1.5-3 sd of the neuron. Currents are
  +-(1-3) sd_v * lam for 0.2-0.6 s. Silencing lasts 0.3-1.2 s, or to the end in 20% of cases. Group size is 15-40% of
  the held-out targets. Edge removal takes 20-80 existing edges among held-out targets.
* **hold-outs in test**, all checked by `tests/test_suite.py`:
  * *initial states*: generic latents draw train inits within radius <= 1 x amplitude around rest and test inits in
    the shell 1-1.5x. Families define their own regions: the far side of the wells for bistable systems, the
    outside of the outer cycle for trap I, above-threshold amplitudes for trap J, and so on;
  * *parameter draws*: params_seed 0-7 in train/val, 1000-1007 in test;
  * *noise*: weight_noise sd 0.05 with seeds < 10^4 in train; sd 0.12 with seeds 10^4-2*10^4 in test. Every
    trajectory has its own process and observation noise realisation;
  * *intervention types*: train/val have single-neuron kick, current and silence only; test has group kick, group
    current, group silence and edge removal;
  * *intervention targets*: per system, neurons are split 60/40 (stratified by role) into train targets and held-out
    targets; every train/val event touches only train targets, every test event only held-out targets (both ends of a
    removed edge count). Duplicate protocols are redrawn.
* **noise seeds**: after all protocols of a system are planned, each gets an explicit `noise_seed`, drawn from the
  planner's rng (unique within the system, in [0, 2^31)). The suite stays deterministic, and apart from this field
  every protocol is identical to the pre-noise_seed builder (checked on the example suite).
* **counterfactual twins**: every test-split trajectory with events also gets its twin: the same protocol with
  `"events": []` and the same noise_seed. Twins are ordinary public trajectories with split `"twin"` and the family of
  their intervened partner. Both index rows carry `info.pair` = key of the intervened trajectory (the intervened row
  points to itself). Twin latents are in truth like any other trajectory. The difference between a pair is therefore
  the pure causal effect of the intervention under one noise realisation. At dev scale that is 9 twins per system:
  kick_group 2, current_group, group_silence 2, edge_remove, kick_newtarget, silence_newtarget, combined_heldout.
  The test families init_heldout, param_heldout and noise_heldout have no events and get no twin.
* **targets_public**: each system's manifest entry lists `targets_public`, the sorted train intervention targets (the
  neurons train/val events may touch). The held-out targets and the rest of the split design stay in truth only.
* **public output** (`data_format.md`): `manifest.json` (systems: observed, readout [], input_dim, readout_dim, n,
  kind "synthetic", network/group null, targets_public; `splits` ["train", "val", "test", "twin"]; a `families` legend
  of protocol labels; a note on signed states, vector stimuli, noise_seed and twins), `index.jsonl` (info: simulator,
  n_samples and, for pairs, pair), and `traj/<key>.npz` holding only t, x (observed, float32), u and y.
* **truth output** (written only by `p3synth/truth.py`, refused inside the public directory):
  * `truth.json`: suite-level (seed, tier, implementation groups, unrelated pairs, per-system split design with the
    train/held-out target lists, parameter and noise hold-outs, timings) and per system `system_truth()`. The
    per-system fields are: family and number, dynamics type, trap and description, k (`"none"` for family 20),
    coordinates with roles, f, g, theta centre/spread, time scales, closed-dynamics flag, observation map (code,
    activation, sign, noise, unobserved fraction, lam, role counts, blocks), implementation group, group members,
    unrelated partner, per-neuron roles, observability (linear decodability of z from observed activations, singular
    values, causal neurons, per-neuron kick effect `|D[:k, j]|`, unobserved neurons), controllability notes, exact
    intervention semantics, the weight-noise law and the integrator;
  * `systems/<sid>.npz`: E, D, b, activation kinds and scales, observed, lam, noise levels, roles;
  * `latents/<key>.npz`: z (T, k), all coordinates (T, K), the exogenous input where relevant, and A under weight
    noise;
  * `truth_index.jsonl`: per trajectory the effective theta, latent-event log and substep.

## 9. Verification and tests

`uv run pytest` runs 237 tests, all passing (95 s on this 16-thread machine under heavy background load from other
applications; about 35 s when idle).

* `test_simulation.py`, for every system:
  * the latent from the neuron-level simulation equals an independent scipy DOP853 solution (rtol 1e-10) of the
    claimed `dc/dt = F(c, u)` from a random initial state with inputs. Max error 1e-15 to 8e-5, typically 1e-7
    (`reports/accuracy_timing.json`); the worst cases are the chaotic RNN (8e-5, amplified by chaos over 3 s) and
    van der Pol (1.6e-6);
  * every recorded step `z(t) -> z(t+dt)` is the flow of the documented f to within 1e-5.

  Also: 4th-order convergence of RK4 (error ratio > 10 per halving), determinism (bitwise-identical repeats, including
  noise), a noise realisation that depends on the protocol, the recording conventions, and scalar vs vector stimuli.
* `test_families.py`:
  * linear systems: k recovered as the rank of noise-free population activity; A recovered by regression of truth-level
    (z, u) to within 1e-3.
  * oscillators: harmonic energy conservation and frequency; Duffing energy conservation and amplitude-dependent
    frequency; damped decay rate `2 zeta w`; limit cycles attract from inside and outside.
  * switches and integrators: bistable and toggle switching and memory; leaky time constant; perfect integration
    exact and with no drift; gating.
  * WTA: stable null state, input-selected self-sustaining winner.
  * controller: disturbance rejection with integral state `q = r - d`.
  * FHN: threshold behaviour and time-scale ratio.
  * high-dimensional controls: chaos (separation x > 1e3) with PR > 5 and > 10 PCs for 90% variance; the 60-D control
    needs > 15 PCs.
  * hidden exogenous input: needed to close the dynamics.
* `test_interventions.py`:
  * kicks move z by `D[:k, j] dv`; kicks, silencing and currents on nuisance, copy, clock, stimulus-copy,
    parameter-report and carrier-only neurons change neither z nor y, while visibly changing those neurons.
  * silencing follows the documented relaxation and reduced latent law, and the effect persists after release.
  * currents drive z at `D[:k, j] I`; existing vs non-existent edges have an effect vs none.
  * `lift_latent` as a micro kick reproduces `latent_impulse` (logistic, tanh and distributed systems, with auxiliary
    coordinates untouched); `latent_set` is do(); exact during silencing.
  * the weight-noise closed law matches scipy; the integrator leaks under weight noise; saturating kicks are clipped.
* `test_traps.py`: A-L as in section 5.
* `test_groups_pairs.py`: shared dynamics across groups for 3 parameter draws (including a held-out one), implementation
  differences, pairs as in section 7.
* `test_truth.py`: truth complete and JSON-serialisable for all 48 systems; all 20 families and 12 traps present;
  observation-map variety; N range; exact lifting under weight noise.
* `test_protocol.py` / `test_noise_seed.py` (noise_seed):
  * the field is validated (int >= 0; negative, fractional, string and bool are rejected), and it appears in the
    canonical form and hash only when present;
  * a protocol with a kick and the same protocol without it (same noise_seed) are bitwise identical in x, u, y and z up
    to and including the kick sample, and differ afterwards. This holds for 5 systems, including partial observation,
    the family-19 exogenous input (identical exo) and the chaotic control;
  * the same holds before the first of a combined current, silence and edge-removal event;
  * a protocol without events reproduces itself bitwise;
  * different noise_seeds give different noise, including exo;
  * without the field, the legacy canonical-protocol seeding is unchanged.
* `test_suite.py` builds a 5-system suite and checks:
  * the reference `Dataset` loader reads it; public npz files contain only t, x, u and y;
  * no truth leaks: none of the 48 internal names, family names, trap descriptions, "latent", "trap", "grp-", "theta"
    or "k" appears in the manifest or index; ids are opaque;
  * all split hold-outs (targets, types, params, noise, initial states);
  * truth completeness, no duplicate trajectories, and truth outside the public directory;
  * re-simulating published protocols in another process reproduces the public x, y and the truth z bitwise;
  * every protocol carries an integer noise_seed; each intervened test trajectory has exactly one twin (split "twin",
    same family, protocol = intervened protocol with no events, info.pair on both rows, latents in truth); pairs are
    bitwise identical in public x, y and truth z up to the first event; no other row carries a pair;
  * `targets_public` equals the train targets, contains every neuron touched in train/val, and no other split-design
    field appears in public files.

What is NOT tested: identifiability of each latent from the public data alone; that the traps defeat strong modern
methods (only simple baselines: PCA, ridge, AR models, time regression); bitwise reproducibility across different
numpy/BLAS builds or CPUs; statistical properties of the noise beyond seeding.

## 10. Timings

Pure numpy, one trajectory per call, RK4 at the substeps above, CPU (16 logical cores, Windows):

* single trajectory of 4 s (401 samples), one core: median 41 ms (range 32-140 ms) on an idle machine; about 2x that
  under load. It scales with the number of substeps, not much with N: N = 10-300 costs 35-60 ms at h = 5 ms; the
  slow/fast, van der Pol and nuisance-rhythm systems with h = 1.5-2.5 ms cost 110-140 ms. That is 40-300x faster than
  real time.
* edge-removal trajectories are 4-7x slower: each post neuron with removed inputs needs its own evaluation of F.
* full example suite, current version with twins (48 systems, 2976 trajectories, 1.19 M samples): 106 s wall
  (115 s including start-up) with 16 worker processes. The worker-reported simulation time is 1095 s, about 0.37 s
  per trajectory. This build ran while other applications (browser, Docker) kept the CPU at about 96%. Under the same
  load, single-trajectory timings were about 2x the idle numbers (median 86 ms, range 65-330 ms).
* the previous build without twins (2544 trajectories) took 33 s wall (350 s simulation) on the idle machine. The
  noise_seed change does not alter the per-step cost, and twins add 17% more trajectories, so an idle build is expected
  to take about 40 s. That expectation was not re-measured. At idle speed, 20 000 trajectories take about 4-5 min;
  under heavy load it is about 3x longer.
* `uv run python -m p3synth.diagnostics` prints per-system accuracy and timing; the stored copy is
  `reports/accuracy_timing.json`.

## 11. Example suite (tier "dev", seed 0)

`example_suite/public` (296 MB) and `example_suite/truth` (74 MB). 48 systems, 2976 trajectories (train 1536, val
336, test 672, twin 432), 4 s each at dt = 0.01, 1 193 376 samples. Dataset id `p3synth-dev-a2db2c22`. Rebuild with
`uv run python -m p3synth --public example_suite/public --truth example_suite/truth --seed 0 --tier dev`. The output is
deterministic.

## 12. Known limitations (honest list)

1. **One construction for all compressible systems.** The latent is exactly a linear function of the neurons'
   activations (`z = D(v - b)`), and neurons couple through rank-K "population signal" connectivity
   `E (dF + lam) D`. That makes the ground truth exact and the latent interventions exactly liftable, but:
   * the manifold is flat in activation space. The only nonlinearity of the observation map is per-neuron
     saturation (plus noise and partial observation), so a method that inverts the activations can decode z linearly;
   * there are no curved embeddings `h(z)` that need a nonlinear decoder in activation space;
   * the dynamics are not those of a generic nonlinear RNN.

   Only the chaotic control is a genuine RNN.
2. **lam is uniform within a system.** This is needed for exactness; heterogeneous neuron time constants are not
   modelled. Off-manifold perturbations always decay at the single rate lam (20-50 /s).
3. **Silencing and edge-removal semantics are my definitions** (section 3). In particular, removing an edge changes
   only the post neuron's population signal, and silencing clamps a neuron by cutting all of its inputs rather than by
   hyperpolarising it.
4. **Weight noise perturbs only the synaptic readout D** (E is untouched), which gives a closed but perturbed latent law.
   It is not a generic perturbation of every parameter.
5. **Noise is Gaussian and additive**: no spiking or Poisson variability, no heavy tails, no drifts or nonstationarity
   across trials. The readout y is noise-free. Private noise is capped relative to latent noise (a design choice).
6. **Parameter hold-outs are new draws from the same distribution** (spread about +-15%), not extrapolations beyond the
   training range. Initial-state hold-outs are a radial shell for generic latents and ad hoc regions for a few families.
7. **The traps are demonstrated against simple baselines only** (PCA, ridge, AR, time regression). Their strength
   against modern representation learners is plausible but untested. Trap C depends on the time-locked training
   stimuli that the builder generates only for that system.
8. **The chaotic control's W was selected** from random draws to be chaotic (a structural requirement, independent of
   any method). The linear high-D control is not provably incompressible: its Hankel spectrum decays slowly but does
   decay.
9. **Public r0 values reveal every neuron's initial state** in init protocols, including unobserved neurons. Neuron ids
   0..n-1 of unobserved neurons can be targeted by events (they are public ids).
10. **The reference validator (`reference/protocol.py`) rejects negative r0 values and vector stimuli.** Synthetic
    protocols must be validated with `p3synth.protocol.validate`. The public manifest notes this.
11. **Determinism** is guaranteed for a given platform and numpy/BLAS build (verified across processes). Bitwise
    identity across different BLAS builds is not guaranteed, and the chaotic control amplifies any difference.
12. **Fixed sampling:** all suites use dt = 10 ms and 4 s trajectories. Very fast events (FitzHugh-Nagumo spikes of
    about 20-40 ms) are sampled with only a few points.
13. **The example suite is 370 MB** (dense float32 at 100 Hz). Use `--scale` for smaller builds.
14. **Twins are identical only up to the first event.** A twin and its intervened partner are bitwise identical only up
    to the first event. Afterwards their difference is the intervention's effect under the same noise draws. In the
    chaotic control that difference also includes chaotic amplification. Twins exist only for test-split
    trajectories with events.
15. **`targets_public` reveals the train/held-out target split by complement**: any neuron not listed is a held-out
    target. That is inherent to publishing the train targets.
