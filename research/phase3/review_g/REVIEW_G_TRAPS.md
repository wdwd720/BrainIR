# Review G: new adversarial trap families G1-G10 (author documentation, TRUTH-SIDE)

This file contains ground truth. Like `SYNTHETIC_BENCHMARK.md`, it must not be handed to method developers.

## 0. What was added

| file | content |
|---|---|
| `p3synth/review_g.py` | 9 new latent classes (`SyncPair`, `SlowStateOsc`, `SignFlip`, `DelayRelay`, `ExoRhythm`, `LocalValidity`, `LevySwitch`, `DriftingOsc`, `MaskedHighDim`), 1 new block (`Impostor`), `review_g_catalog()` (10 `SystemDef`s, traps G1-G10), `build_review_g()`, `get_review_g_system()`, `build_review_g_suite()` |
| `tests/test_review_g.py` | 52 tests: for each trap a *claim*, a *fooled* and a *truth* test; plus catalogue, truth-JSON, simulator accuracy against scipy, one-step flow and a suite build |
| `REVIEW_G_TRAPS.md` | this file |

Nothing else was changed: the existing systems, `core.py`, `protocol.py`, `suite.py`, `truth.py`, `embeddings.py`,
`blocks.py`, `latents.py` and `systems.py` are untouched. `uv run pytest` runs 289 tests (237 existing + 52 new), all
passing (141 s on this machine).

Usage:

```
from p3synth.review_g import review_g_catalog, build_review_g, build_review_g_suite
systems = build_review_g(suite_seed=0, tier="dev")
build_review_g_suite("out/public", "out/truth", seed=0)        # tier "heldout" (scale x2), all cores
```

`build_review_g_suite` runs the unchanged `p3synth.suite.build_suite`. For the duration of the call it points
`suite.catalog` at `review_g_catalog`, and it swaps in a picklable worker (`review_g._g_run_system`) that does the same
inside each worker process before calling the original `_run_system`. Both are restored afterwards (tested).

## 1. Conventions shared by all ten traps

* Every system is a `SystemDef` built by the unchanged `build_system`. The x-space construction is exact
  (`c = D(v - b)` follows `F`), so everything in `SYNTHETIC_BENCHMARK.md` sections 2-3 holds, including the
  intervention semantics, lifting and weight noise. `family_no` reuses the existing family numbers because
  `build_system` looks them up in `FAMILIES`. The truth field `family` is therefore the nearest existing family, and
  `dynamics_type` (`review_g_*`) and `notes` (which start with the trap label and its description) identify the trap.
* `trap` in truth is `"G1"`...`"G10"`. `trap_description` is `null`, because `truth.py` looks descriptions up in the
  unmodified `TRAPS` dict. The description is in `notes` and in `review_g.TRAPS_G`.
* `k` is documented in truth: G1 4, G2 3, G3 2, G4 9, G5 2, G6 1, G7 3, G8 1, G9 2 and G10 `"none"`. G10's latent
  class has family `high_dimensional`, which is what makes the unchanged truth writer emit `"none"`.
* G5, G8 and G9 use the existing hidden-exogenous channel (`n_exo = 1`, as family 19 does). Truth therefore says
  `closed_dynamics: false` and stores `exo` per trajectory. For G8 this flag is misleading. The jumps are white noise,
  so z alone is Markov; the exogenous channel is only how the jumps are delivered. The G8 notes say so.
* The evidence below is from `tests/test_review_g.py` (suite seed 0, tier dev). I also ran every G test with suite
  seeds 1-5 (`REVIEW_G_SEED=s uv run pytest tests/test_review_g.py`), and all of them pass. Several thresholds were
  loosened after that sweep: the first thresholds had been read off a single seed and failed on others (see section
  3). Numeric ranges quoted as "seeds 0-5" come from that sweep.
* "Simple learner" means the same kind of baseline used for traps A-L: PCA, ridge regression, linear or AR state
  models, least-squares Gaussian SDEs and per-trial context models. Whether the traps defeat strong modern methods
  was not tested.

## 2. The traps

### G1: symmetry-hidden transverse mode (`g1_sync_pair`, k = 4)

**Construction.** Two identical Hopf oscillators A and B (0.8-1.3 Hz, radial rate 3-5 per s) with weak diffusive
coupling K (0.25-0.4 per s) and a common input on A1 and B1. The coordinates are `s = (A+B)/2` and `d = (A-B)/2`,
and `y = A1 + B1 = 2 s1`. Process noise acts on s only. Dense identity code, 60 neurons.

**What it attacks.** Dimension estimates based on variance or prediction, and encoders trained mostly on unperturbed
data. The synchronous manifold `d = 0` is invariant under f and under every input, so spontaneous and input-driven
activity is exactly 2-D. The two transverse dimensions are real state, and they matter a great deal: near anti-phase
they cancel y, and they relax only over seconds.

**Why principled.** Symmetric circuits (identical sub-networks, common drive) have invariant synchronous manifolds.
Only symmetry-breaking perturbations reveal the transverse dynamics, and a single-neuron stimulation is exactly such a
perturbation.

**Evidence.** *Claim:* with any input and any synchronous start, `max|d| < 1e-9`. A single-neuron kick makes
`|d| > 0.05`. From 0.9 pi anti-phase, |d| is still above 70% after 1 s (81-92% over seeds 0-5) and |y| < 0.8 during
the first second, against an amplitude of 2 when synchronous. *Fooled:* 2 PCs explain > 98% of the unperturbed
variance, and PC3 is < 0.2%. A synchronous state and a near-anti-phase state are constructed with identical 2-PC
encodings; their y futures differ by an RMS of > 0.3 sd(y). Any dynamics on that encoder therefore violates Markov
closure. *Truth:* a cubic polynomial vector field fitted to the 4-D truth latent (noise-free, synchronous and
desynchronised starts) predicts a new anti-phase trajectory with R^2 > 0.95.

**Correct behaviour.** Report k = 4, using the kick, current and silencing trajectories of the train split. A method
that sees only unperturbed data cannot know about d and should not claim that k = 2 is closed under interventions.

**Limitations.** (i) In the train split, single-neuron kicks move d by only about 0.05-0.2, so the nonlinear
anti-phase dynamics must be extrapolated. The truth test fits on desynchronised initial states, which are a held-out
region. (ii) Private noise (`priv_noise` 0.02) leaks into d at about 0.5% of the amplitude, so spontaneous activity is
not exactly 2-D in principle. (iii) The coordinates (s, d) are a linear re-parametrisation of (A, B). No neuron is
"an A neuron", because the dense code mixes everything.

### G2: slow causal state that looks like a parameter (`g2_slow_state`, k = 3)

**Construction.** A Hopf oscillator whose frequency is `f0 (1 + 0.3 tanh s)`. The variable s decays with tau_s
30-60 s, so it drifts by only a few per cent within a 4 s trial. Initial states set s in [-1.2, 1.2], and held-out
initial states set |s| in [1.2, 1.8]. A sparse code gives some neurons only s. Four `ParamReport("f0")` neurons report
the parameter draw.

**What it attacks.** The lesson of trap H, taken too far: "whatever is constant within a trial is a parameter or
context". Here two populations look the same observationally, and only interventions tell them apart. Both are flat
within a trial, and both explain part of the trial's frequency across trials. One (s) is causal state; the other
(f0 reporters) is not causal.

**Why principled.** Slow variables such as adaptation currents, neuromodulator tone or synaptic resources are state on
the time scale of minutes, even though they look like fixed context inside a short trial.

**Evidence.** *Claim:* noise-free, s changes by < 15% over 4 s, and the measured frequency equals
`f0 (1 + delta tanh s)` within 2% for s = -1, 0 and 1. Kicking all four parameter neurons changes x by > 0.5 and y by
< 1e-12. *Fooled:* over 24 trials (8 parameter draws), the within-trial sd of both populations is < 10% of their
across-trial sd. Each population alone explains 0.2-0.8 of the trial frequency's variance (R^2, seeds 0-5), both
together > 0.95, and both are needed (dropping either loses > 0.15). A context model that fixes the frequency from
the pre-kick part of the trial is wrong by > 15% until the end of the trial after a kick of the s-selective neurons.
*Truth:* the post-kick frequency equals `f0 (1 + delta tanh s_post)` within 2% (s moved to -1 and to +1.2).

**Correct behaviour.** Treat s as state (k = 3), because kicks on s-neurons in the train split change the frequency.
Treat the f0 reporters as non-causal correlates of a parameter.

**Limitations.** s varies across trajectories only through the initial state (init protocols) and kicks, while f0
varies with `params_seed`. The two are therefore not identically distributed across the suite, and a method could
separate them by protocol family. With tau_s at 30-60 s, s is not exactly constant (it decays by about 7-13% per
trial).

### G3: context-dependent sign of tuning (`g3_sign_flip`, k = 2)

**Construction.** `tau dp = -p + g m u1` and `tau_m dm = m - m^3 + g_m u2` (a bistable context switched by u2 pulses),
with `y = m p`. Because m = +-1, y obeys the same law `tau dy = -y + g u1` in both contexts. The neurons are linear in
(p, m): dense identity code, 50 neurons, m at half gain.

**What it attacks.** Linear readouts, and any assumption that a neuron has a fixed-sign causal effect on the output.
Relative to y, every tuned neuron's tuning flips sign with the context, and so does the effect of stimulating it.

**Why principled.** Context-dependent mixed selectivity: the same population holds a variable in a context-dependent
frame, and a downstream gain (here the multiplicative readout) undoes the frame. The generator states no biological
claim.

**Evidence.** *Claim:* for the same u1 input in contexts +1 and -1, y is identical to 1e-9 while x differs by > 0.5.
Regressing dy/dt on the documented law gives R^2 > 0.98. Every neuron with |corr(x, y)| > 0.5 has the opposite sign
in the other context (> 95% required; 100% observed). *Fooled:* a linear readout of y pooled over both contexts has
held-out R^2 < 0.2 (it is negative), while a within-context readout has > 0.95. The same micro kick (an exact lift of
dp = +0.3) changes y by > +0.2 in one context and < -0.2 in the other. The readout learned in context +1 predicts the
wrong sign in context -1. *Truth:* `y = z1 z2` exactly (1e-12).

**Correct behaviour.** Find (p, m) as the state, with a nonlinear (bilinear) readout, and predict context-dependent
intervention effects.

**Limitations.** A context switch while p != 0 flips y (y -> -y) during the 0.1-0.2 s switch. This is a property of
the construction, not of the "same law in both contexts" claim, which holds only while m = +-1. With saturating
activations (tanh), the nonlinearity itself creates p*m terms that a linear decoder exploits: a tanh version reached
a pooled R^2 of 0.9. For that reason G3 uses identity activations.

### G4: transmission delay as a relay chain (`g4_delay_relay`, k = 9)

**Construction.** Delayed negative feedback `tau_a da = -a - kappa q_M + g u`, where the delay is realised by an
M = 8 stage relay (linear chain trick, Erlang delay with mean T = 0.4-0.5 s). tau_a is 60-100 ms, kappa 1.05-1.2, and
the loop rings at about 0.8-1.1 Hz with damping ratio 0.1-0.15. `y = a`. Sparse identity code, 80 neurons, so relay
populations carry single stages.

**What it attacks.** Dimension estimation by variance, and reduced models. The relay stages are lagged, smoothed
copies of a: they are highly collinear and add little variance, yet each is real state. A kick to an early stage stays
silent for about 0.2 s and then returns to a as an echo about 0.4-0.5 s later.

**Why principled.** Axonal and synaptic delays, multi-synaptic loops and relay nuclei implement delayed feedback with
finite, distributed memory held in intermediate populations.

**Evidence.** *Claim:* a kick mostly on stage 1 produces a peak change in a > 0.2 s later than the same kick on stage
8. *Fooled:* 3 PCs explain > 99% of the unperturbed variance (99.3-99.8%, seeds 0-5), while k = 9. A 3-PC linear state
model fitted to unperturbed data responds at once to a stage-1 kick (> 0.9 of the true echo peak within 0.2 s, where
the truth is < 0.5), and its peak-latency error is > 0.3 s (0.39-0.54 s). *Truth:* a 9-D linear model fitted by least
squares to the truth latent of the same unperturbed data predicts the echo with R^2 > 0.95.

**Correct behaviour.** k = 9 (or an honest statement that the memory is distributed over about M relay stages). A
non-Markov or delay-embedding description of a alone cannot predict interventions on relay neurons.

**Limitations.** The 3-PC model's R^2 on the echo varies from -6 to +0.57 over seeds 0-5, so only the timing error is
robust. A 4-5-D reduced model already gets later-stage echoes right; the trap bites mainly for early stages. An Erlang
delay is smoother than a true fixed delay.

### G5: external rhythm masquerading as an intrinsic oscillation (`g5_exo_rhythm`, k = 2)

**Construction.** A damped oscillator (f0 1.2-1.6 Hz, zeta 0.15-0.25) driven by u and by a hidden
`e(t) = sin(2 pi f_d t + phi)`, with f_d 0.5-0.7 Hz and phi random per trajectory. No neuron carries e, and it is not
in u. Logistic neurons, 40.

**What it attacks.** Attributing a sustained rhythm to the circuit. Unperturbed activity is dominated by a steady
oscillation at f_d that looks intrinsic, and an AR or linear model internalises it as an undamped mode. Kicks cannot
shift the drive's phase: the causal response to a kick is a transient at f0 that dies out.

**Why principled.** Entrainment by rhythmic input from an unrecorded area (or a sensory rhythm) is ubiquitous. The
difference between "internal oscillator" and "driven filter" is exactly what perturbations reveal.

**Evidence.** *Claim:* e is a pure sinusoid at f_d (R^2 > 0.999999) with a trajectory-specific phase. The one-step
residual of the documented f without e is > 10x its residual with e. Kicked and twin trajectories share e exactly, and
the kick response decays to < 10% within 2.5 s. *Fooled:* an AR(2) model on 2 PCs, trained on unperturbed data, has a
companion eigenvalue |lambda| > 0.99 and predicts 1.5 s ahead with R^2 > 0.9 on unperturbed data. After an exact 0.8
latent kick, however, it predicts a persistent response 2-3.5 s later (> 0.3 of the initial response, and > 5x the
truth; 0.46-1.9 vs <= 0.07 of the initial response over seeds 0-5). *Truth:* a linear model on (z, u, e) fitted on
truth predicts the kick response with R^2 > 0.95.

**Correct behaviour.** k = 2 plus a predictable but uncontrollable external drive. Report the drive as an unexplained
input rather than as intrinsic state, or represent its phase as a non-manipulable context.

**Limitations.** The drive is deterministic within a trajectory, so representing its phase as two extra latent
dimensions is a legitimate predictive model. The trap penalises such a model only when it treats those dimensions as
movable by interventions. Truth marks the system `closed_dynamics: false`.

### G6: confounded impostor population (`g6_impostor`, k = 1)

**Construction.** A leaky integrator (tau 0.3-0.6 s) as the latent, carried by 12 causal neurons with 30% observation
noise. The new `Impostor` block obeys the latent's law exactly: `tau dn = -n + g u`, with tau and g read from theta
and its own independent noise. It is carried by 60 dedicated neurons (gain 2) and is also mixed into the causal
neurons. n never feeds z.

**What it attacks.** Representation selection by output prediction, and correlational attribution. On observational
data, corr(z, n) > 0.98 (0.997-0.999). The impostor population is larger and cleaner, so an output-supervised encoder
relies on it.

**Why principled.** Parallel pathways that receive the same afferent input with similar integration time constants
but project elsewhere. Common input creates correlations that only interventions can break.

**Evidence.** *Claim:* kicking and silencing impostor neurons leaves y unchanged (< 1e-12) while changing x by > 1.
A coherent kick of the causal neurons moves y by > 0.3. *Fooled:* a ridge encoder of y has held-out R^2 > 0.95, and
more than 50% of its |weight| is on impostor neurons (69-72%). A coherent impostor kick makes the encoder predict a
change > 0.3 sd(y) (1.4-1.5 sd(y) observed), while the true change is 0. For a coherent kick of the causal neurons,
the encoder recovers < 50% of the true effect (15-20%). *Truth:* the causal kick effect equals `D[0, J] dv`,
decaying with the latent's tau (to 1e-4 relative); y = z exactly.

**Correct behaviour.** Use the train-split interventions: 60% of impostor neurons are train targets, so kicks on them
show no effect on y. The impostor should be recognised as a non-causal correlate.

**Limitations.** The impostor's noise is independent, so a careful method can in principle separate n from z
observationally, using the small components of y that follow z's noise and not n's.

### G7: compact state valid only inside part of state space (`g7_local_validity`, k = 3)

**Construction.** A slow variable a (`tau_a da = -a + g u`, tau_a 1.5-2.5 s, g 0.6) and a fast oscillatory mode b
with state-dependent stability `db = [mu (a^2/a_c^2 - 1) - gamma |b|^2] b + w_b J b`. Here a_c = 1.2, mu 5-7 per s
and w_b 2-3 Hz. `y = a + b1`. Train initial states and inputs keep |a| < 1; held-out initial states have |a| = 1.5-2.

**What it attacks.** Extrapolating a compact model beyond its training region. Inside the region b is stable and tiny,
so the system is effectively 1-D. Outside it, b ignites into a 2-3 Hz oscillation.

**Why principled.** State-dependent stability (a slow variable pushing a fast subsystem through a Hopf bifurcation)
is generic in excitable and oscillatory circuits. Critical slowing down before the boundary is a real, measurable
precursor.

**Evidence.** *Claim:* the decay rate of b at a = 0, 0.6 and 0.9 matches `mu (1 - a^2/a_c^2)` within 3%. With a held
at 1.8, b grows more than 10x in 1 s. *Fooled:* in the training region, |a| stays < a_c and PC1 explains > 85% of the
variance. A 1-PC linear model fitted there has a 0.5 s rollout RMS error on held-out-region trajectories > 5x its
in-region error (0.34 vs 0.028 for seed 0). *Truth:* extrapolating the in-region decay rates (a = 0-0.9) with
`rate = mu - (mu/a_c^2) a^2` recovers a_c within 5%.

**Correct behaviour.** Model b (k = 3), which the kicks and noise in the train split make visible, including its
a-dependent damping. Alternatively, flag low confidence or abstain outside the region.

**Limitations.** Whether b ignites in a held-out trajectory depends on the noise realisation and on how long |a|
stays above a_c (the burst is transient because a relaxes). Some held-out trajectories show only a small burst.

### G8: heavy-tailed intrinsic noise in a switch (`g8_levy_switch`, k = 1)

**Construction.** A double well `tau dz = z - z^3 + g u` (tau 0.15-0.2 s) with Gaussian noise plus compound-Poisson
jumps: rate 1.2-1.8 per s, |J| Pareto(x_m = 0.3, alpha = 1.5) capped at 3, random sign. The jumps are delivered as
impulses J/dt over one output step through the exogenous channel. Redundant tanh code, 30 neurons.

**What it attacks.** Gaussian-noise assumptions (least-squares or MSE training, Kalman-style likelihoods, Markov
tests on Gaussian residuals). Rare single jumps cause memoryless well switches. No Gaussian model matches both the
within-well jitter and the switching rate, which tempts a method to invent a hidden "switch-trigger" state.

**Why principled.** Bursty, heavy-tailed input (synchronous volleys, population bursts) is common. White jumps are
noise, not state.

**Evidence** (12 x 20 s trajectories). *Claim:* the kurtosis of the true-drift residuals is > 50 (about 400). The jump
rate matches rate_J within 25%, and amplitudes lie in [x_m, J_max]. More than 80% of switches follow a single jump
> 0.6 within 0.6 s (92-100% over seeds 0-5). No precursor: the mean |z| in the 0.5 s before the triggering jump
differs from the overall mean by < 0.1. *Fooled:* a Gaussian SDE with a cubic drift fitted by least squares has
residual sd > 5x the robust (MAD) sd, so its typical jitter is far too large. A Gaussian model with the robust sd
predicts < 10% of the observed switching rate (it essentially never switches). *Truth:* the documented 1-D law,
simulated independently of the neuron-level simulator, reproduces the switching rate within a factor of 2.

**Correct behaviour.** k = 1, with a heavy-tailed innovation model (or an honest report that the noise is
non-Gaussian). No extra state.

**Limitations.** Switches are rare (about 0.1 per s), so a 4 s trajectory usually has none and suite-level
statistics are thin. Truth's `closed_dynamics: false` is an artefact of the delivery channel. Jumps are applied over a
10 ms step (smeared by the drift, with tau at least 0.15 s).

### G9: slow non-neural parameter drift (`g9_param_drift`, k = 2)

**Construction.** A damped oscillator whose frequency and damping follow a hidden OU context e(t) with tau_e 2-4 s:
`w = w0 (1 + 0.25 tanh e)` and `zeta = zeta0 (1 - 0.6 tanh e)`. e is carried by no neuron, is not in u, and is
independent per trajectory.

**What it attacks.** Both sides of the context-versus-state question. A stationary model is wrong. A model that
adds e as a latent treats something as neural state that no neuron carries and no intervention moves. Together with
G2, the pair brackets the distinction: G2 is neural state that looks like context, G9 is context that looks like
state.

**Why principled.** Slow nonstationarity (arousal, neuromodulation, temperature) modulates circuit parameters within a
recording.

**Evidence.** *Claim:* e has sd about 1, and its pooled lag-0.5 s autocorrelation matches exp(-0.5 / tau_e) within
0.15. A kick plus silencing leaves e bitwise identical to the twin's, while z changes. *Fooled:* the 1 s rollout
error of a stationary linear model on the truth latent is > 5x that of a context-aware model (about 11x for seed 0),
and e is not linearly decodable from the recorded x (held-out R^2 < 0.1). *Truth:* with e known, 1 s rollouts have
normalised error < 0.03 (R^2 > 0.97).

**Correct behaviour.** k = 2 with a hidden, non-controllable, time-varying parameter. Report the nonstationarity or
abstain from claiming a closed state; do not add e as neural state.

**Limitations.** The "fooled" test uses the truth latent for both models; it shows what information is missing, not
that a specific representation learner fails. e is inferable from the dynamics (the local frequency), so a model that
tracks it as context is legitimate. The OU sd is 1, so tanh(e) often saturates.

### G10: non-compressible system that looks one-dimensional (`g10_masked_highdim`, k = none)

**Construction.** One input-driven, noise-driven leaky mode z0, plus P = 16 damped rotations (0.5-8 Hz, decay
0.8-3 s) that neither u nor the process noise excites. All modes are read out: `y = z0 + sum C_i z_i`, with |C|
0.4-0.8. K = 33, dense identity code with 60 neurons, `priv_noise` 0.003.

**What it attacks.** The abstention decision. Observational activity has one dominant dimension, so a method will
report k = 1 and not abstain. Every micro intervention excites all 32 dormant coordinates, and y then carries many
incommensurate damped oscillations.

**Why principled.** A network with many weakly damped internal modes that are orthogonal to its input and quiet at
rest. Perturbation reveals richness that spontaneous activity hides.

**Evidence.** *Claim:* noise-free, the dormant coordinates are 0 (< 1e-9) under any input, and one single-neuron kick
excites every one of the 16 rotations (> 1e-4). *Fooled:* PC1 carries > 10x the variance of PC2 (15-51x over seeds
0-5; the rest is the observation-noise floor). A 1-PC linear model misses > 50% of the energy of the response to
5-neuron kicks over 0.3-2 s. *No compact state / truth:* in the Hankel matrix of 16 kick responses, the first 6
singular directions carry < 90% of the energy (about 78%). A linear map fitted on 10 truth-level kick effects (kicked
minus twin, 33-D) predicts held-out kick effects with R^2 > 0.95.

**Correct behaviour.** Abstain, or report k >= 30. Truth says `"none"`.

**Limitations.** Like the existing linear high-D control, this is not provably incompressible: about 10-16 dimensions
capture 99% of the kick-response energy. Private noise weakly excites the dormant modes (sd about 1e-3), so a method
could in principle detect them in the fluctuation spectrum. Single-neuron kicks produce responses of only about 5-10%
of sd(y).

## 3. General limitations and notes

1. **Same construction as the base benchmark.** All latents are linear in activation space (`z = D (v - b)`), with a
   flat manifold and a uniform lam. Traps that need a hidden synaptic variable, heterogeneous neuron time constants
   or targeted partial observation of a specific sub-population cannot be built without changing `embeddings.py` or
   `core.py`. That is why "partial observation hiding the causally important sub-population" from the contract's idea
   list is not implemented: `make_implementation` chooses unobserved neurons at random by role.
2. **Only simple baselines are fooled** (PCA, ridge, linear/AR, Gaussian SDE, per-trial context). The traps are
   designed around structural properties, so strong methods should also have to use the interventions. That is
   plausible but was not tested.
3. **Thresholds were loosened after a seed sweep.** The first version of the tests passed on seed 0 but failed on
   seeds 1-3 (anti-phase relaxation speed in G1, the reduced-model R^2 for the relay echo in G4, the individual
   frequency R^2 in G2, the jump-to-switch window in G8, the PC-ratio floor in G10). Two failures were bugs in the
   tests themselves: G5 lifted the kick at a noise-free state, and G7 did not hold a outside the region. The final
   thresholds hold for seeds 0-5 at tier dev; other seeds and tiers were not checked.
4. **Exogenous channel.** G5, G8 and G9 inherit family 19's mechanics. Without a `noise_seed`, exo is seeded by the
   canonical protocol; with one, twins share it exactly. `noise=False` zeroes exo, so the scipy accuracy tests check
   these systems without their drive, and the drive is checked separately via one-step residuals.
5. **Suite identity.** `build_suite` derives `dataset_id` from (tier, seed) only, so a Review G suite and a
   main-catalogue suite with the same tier and seed have the same `dataset_id`. System ids differ, because they hash
   the internal names. Build them into separate directories.
6. **Timing.** A tier-dev single trajectory costs 0.05-0.12 s. `tests/test_review_g.py` takes about 75 s, including a
   suite build at scale 0.25 with 3 workers (about 25 s). A full heldout-tier build (`build_review_g_suite(..., seed=0)`, 10 workers) writes 1240 trajectories (497 240 samples) in 39 s wall (257 s of simulation).
