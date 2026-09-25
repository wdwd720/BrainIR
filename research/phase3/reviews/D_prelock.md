# Review D (computational neuroscience): pre-lock review of BrainIR State v1 and benchmark version 2

Reviewer D. Scope: whether the simulations are interpreted honestly, whether the low-level interventions make biological sense for
rate models, and whether the planned claims go beyond the evidence. I read PROTOCOL.md (v2), METHOD_DEV_CONTRACT.md,
notes/brainir_state_v1.md, notes/_evaluator_v2.md and notes/_tournament_feedback.md. I also read the frozen rate model
(extra/frozen_rate_model/model.py), the real engine and protocol generator (extra/orchestrator/brainir_state/realsim.py,
realgen.py), the synthetic generator documentation (extra/generator/SYNTHETIC_BENCHMARK.md, core.py), the evaluator
(src/brainir_state/evaluate.py, harness.py, refmodels.py) and extra/scripts/level_c.py.

All numbers below come from the PUBLIC data (data/real_public, data/synthetic_dev) unless stated otherwise. The hidden data do not
exist yet, so every real-data number is a public-data estimate of what Level C will face. The scripts are in `.tmp/D/`: stats.py,
scale.py, kicks.py, rhythm.py, norm.py, level.py, floorsens.py, afloor.py, sat.py. The synthetic kick-clipping count came from
running `.tmp/H/kick_clip.py`, which I re-ran and did not modify.

## Summary verdict

**Not ready to lock the evaluation of the real (Level C) systems. The synthetic side (Level B) is sound enough, provided its claims
are scoped.**

The simulators are implemented faithfully and documented honestly: the rate ODE, the piecewise composition, the silencing semantics
and the generator's limitation list all hold up. The problems are in how the real-circuit metrics are built on top of those
simulations:
- The real readout metrics are dominated by near-silent readout neurons and by per-trajectory offsets in readout level. The offsets
  come from each trajectory's own draw of every neuron's parameters, the readout neurons' included, and the encoder cannot see them.
- As a result:
  - the "predictive" verdict condition cannot be met on real systems by any model that encodes x only. On every public real system
    the readout-history control beats even the full-state "ceiling", which sees y;
  - real C is carried mainly by a few near-silent readout neurons, weighted up to 1000x;
  - on the 7 mechanism systems, the "held-out target" families are not held out.
- About 40 % of real kicks are no-ops, and most single-neuron silencing pairs have no effect.
- The synthetic held-out intervention "types" are additive by construction, so success there is not evidence for connectome
  circuits.

These can be fixed before the hidden real data are generated. Some need a version-3 protocol amendment. None needs a change to the
simulator.

On the method: v1 selects k = 1 on every real system. Yet the readouts of 8 of the 10 real systems are sustained 6-17 Hz
oscillations, which a 1-D autonomous state cannot represent. Its real A equals the input-only control and is worse than persistence
on 4 of the 7 mechanism systems.

---

## BLOCKERS

### B1. The real readout NMSE is dominated by near-silent readout neurons (1e-3 variance floor), so real C (and on net3 real A) does not measure fidelity on the circuit's output

**Where.** `evaluate.readout_scale` (evaluate.py:155-161) sets the per-dimension variance to max(var, 1e-3 x max var).
`_nmse` / `eval_intervention` then weight every readout dimension by 1/scale (evaluate.py:164-165, 259-263).

**Evidence (public real data).**
- The readout lists contain many near-silent neurons. On the full systems (nominal trajectories), 6 of 9 net1 readouts have
  ~0 variance and 4 of 9 fall below the floor. On net2 4 of 20 are below the floor, on net3 2 of 10.
- Mechanism systems inherit the whole network's readout list: 6-12 of their 9-20 readout dimensions are below the floor, most of
  them structurally silent.
- These dimensions receive up to 1000x the weight of the main readout. A 0.1 Hz twitch of a silent neuron then counts as much as a
  3.2 Hz change of the dominant one (`scale.py`, `floorsens.py`).
- Share of the pooled C effect denominator (all validation intervention pairs with their twins, 250 ms window) that comes from
  readout dimensions with variance below 1e-3 x max:

  | system | floor 1e-3 (as locked) | floor 1e-2 | largest effect on those dims |
  |---|---|---|---|
  | real:net1:full | 0.00 | 0.52 | 0.00 Hz (at 1e-3) / 0.90 Hz (at 1e-2) |
  | real:net2:full | **0.78** | 0.67 | 13.4 Hz (vs 27.4 Hz on the others) |
  | real:net3:full | **0.79** | 0.27 | **0.74 Hz** (vs 6.4 Hz on the others) |

  By family (floor 1e-3): net2:full kick_A 0.73 and pulse_A 0.80; net3:full kick_A 0.58 and silence1_A 0.975.
- On net3:full, real C is therefore mostly a measure of sub-1-Hz effects on two neurons that are silent in training. Which neurons
  carry it also changes with the arbitrary floor constant (net1 0 -> 52 %, net3 79 -> 27 %).
- The same holds for A on net3:full: 97 % of the persistence floor's error comes from its 2 floor dimensions (`afloor.py`).
- C enters the verdict and 3 of the 13 primary tests (C per full system); A enters 3 more.

**Why it matters.** The protocol presents C as the "interventional fidelity" of the readout. On the real systems it currently
measures the recruitment of near-silent neurons, amplified by a normaliser constant chosen only to avoid division by zero ("the
floor avoids silent dimensions"). This is the opposite of what the floor was meant to do.

**Fix (before hidden real data are generated; version 3).** Pre-register one of the following for the real systems:
- (a) pooled normalisation: sum over dimensions of the squared error divided by the sum of the training variances. Equivalently,
  weight each dimension by var_d / sum(var), not 1/var_d;
- (b) restrict y to readout neurons that are active by a pre-stated rule on public training data (for example, sd >= 1 % of the
  largest readout's sd), and report the dropped neurons.

In either case, report per-dimension shares of the C denominator and a floor-sensitivity analysis (1e-3 against 1e-2) as
pre-registered descriptive outputs. Re-derive the margins that depend on the baseline's C and A under the new normaliser.

### B2. The real "predictive" condition cannot be met on real systems: y carries per-trajectory parameters of unobserved readout neurons, and the readout-history control reads them off

**Where.** The verdict (PROTOCOL section 7; `harness.verdict`) requires "A below both shortcut controls", the readout-history
control among them. Every real trajectory draws fresh per-neuron tau, a, theta and r_max for ALL neurons, the readout neurons
included. See `realgen.Sampler._base` (a new `params_seed` per protocol), `generate_real_data.py:124` (`seed_fn` = a random integer
per trajectory) and `model.sample_neuron_params(cfg, n, …)`. Readout neurons are never part of x (`realgen.build_systems`).

**Evidence.**
- **Every public real trajectory has its own parameter draw.** net1:full has 425 trajectories and 425 distinct params_seeds, and the
  same holds for every system.
- **The level of y is not recoverable from x.** A ridge decoder from x (with 5-40 ms lags) plus u to y, on event-free validation
  trajectories, leaves 45-96 % of its error as a per-trajectory CONSTANT offset: net1:full 0.64, net2:full 0.67, net2 mechanisms
  0.79-0.90, net1:mech:02fa13b8 0.96 (`level.py`).
- **The within-window rhythm is a small share of the normaliser.** An oracle that predicts each 250 ms window's own mean scores
  NMSE 0.038 (net1:full), 0.001-0.07 (mechanisms) and 0.23 (net2:full) (`norm.py`).
- **In v1's own table (notes section 7.5), the readout-history control beats every model on all 8 real systems, the full-state
  "ceiling" included, even though the ceiling sees y.**
  - The "ceiling" is 0.003-0.264; readout-history is 0.002-0.043.
  - On net1:full: ceiling 0.087, readout-history 0.021.
  - The ceiling (`refmodels.FullStateModel`) is a 1-ms one-step MLP over ~200 dimensions, rolled out for 250 steps. On these data it
    is not a ceiling: it loses to the oracle-constant predictor on net1:full (0.087 against 0.038).
- **Round 2 contains no real systems,** so no held-out evidence contradicts this.

**Why it matters.** Whatever the method, every real verdict can only be "not supported". The report would then read "no compact
causal state in connectome circuits". But what is missing is a set of static parameters of neurons outside x, and the protocol's
own trap H says such a quantity "is a parameter, not state". The pre-registered real verdict therefore cannot tell methods apart,
and it would be misread.

**Fix (pre-register before Level C).** Either:
- (a) judge the real predictive condition against the input-only control and the persistence floor only. Report the
  readout-history control descriptively, with the reason stated. Add a level-corrected A: window NMSE after removing each window's
  mean error, as a descriptive secondary; or
- (b) state now that the real verdicts are uninformative for the predictive condition and report only the primary paired tests.

In both cases, stop calling A_full the "ceiling" for the real systems.

Regenerating hidden data with the readout neurons' parameters fixed at their means would also remove the confound. It changes the
simulation design, so it is the less preferable option.

### B3. On the 7 mechanism systems, the "held-out target" C families use the public targets, yet the verdict counts them as held-out

**Where.** `realgen.split_targets` returns `(sorted(obs), [])` for mechanism systems, and `family_protocol` then generates
`H_kick_B` / `H_pulse_B` / `H_silence1_B` with `smp.kick(B or A)` etc., i.e. on the public A targets.
`harness.HELDOUT_INTERVENTION = ("H_kick_B", "H_pulse_B", "H_silence1_B", "H_group_silence")` puts them all in the verdict's
"held-out" C. PROTOCOL section 3.1 calls these families "held-out TARGETS" but also says "For mechanism systems, A = all members".

**Consequence.** On 7 of the 10 real systems, three of the four "held-out" families are in-distribution targets with hidden draws,
the same design as H_kick_A / H_pulse_A / H_silence1_A. Only H_group_silence is held out. On 3-member mechanisms that family
silences 2-3 of the 3 members, which amounts to a near-total ablation of the circuit.

"Interventional (held-out STATE / INPUT interventions)" is therefore not what is measured on the mechanism systems.

**Fix.** For mechanism systems, define the verdict's held-out C as H_group_silence only (report the B families under their true
label, in-distribution), or state explicitly in PROTOCOL section 7 and in the Level C report that mechanism-system C is mostly
in-distribution. Record this in section 10.1.

---

## MAJOR issues

### M1. Real kicks and single-neuron silencing are largely no-op experiments. The kick sign is not biologically meaningful for near-silent rate units, and the recorded event is not what was applied

**Evidence** (`kicks.py`, `stats.py`, `scale.py`).
- **The observed population is mostly quiet.** It is defined as the neurons with peak rate above 0.01 Hz
  (`realsim.ACTIVE_HZ`). Of those, 51 % (net1), 47 % (net2) and 58 % (net3) peak below 1 Hz, and 36-43 % peak below 0.1 Hz. The
  median pre-kick rate of a kicked neuron on the full systems is 0.00 Hz.
- **Negative kicks are clipped.** Kicks are ±U[5, 30] Hz, and `realsim.run` applies `r = max(0, r + d)`.
  - On the full systems, 48-50 % of all kicks are negative and clipped. 34-41 % of all kicks are negative kicks on neurons below
    0.5 Hz, i.e. essentially no-ops.
  - On the mechanisms, 24-53 % of kicks are clipped.
  - The protocol, the public index and the hidden events all record the REQUESTED delta, not the applied one. PROTOCOL section 3.1
    and the contract ("instantaneous state offset") do not mention the clip. v1 happens to clip too; a method that trusts the
    record is penalised for an undocumented simulator rule.
- **Most single-neuron silencing is null.** In the public validation pairs, silence1_A pairs with effect energy below 1e-3 number
  11/15 on net1:full and 10/15 on net3:full. n_eff is 1.0 on net1 (one pair carries 99 % of the denominator), and 1.0-3.0 for many
  families. This is what silencing a neuron that is not firing produces: nothing.
- **Real and synthetic kicks are sized differently.** Synthetic kicks are scaled to each neuron (±1.5-3 sd). Real kicks are
  absolute and reach 1.4x the full networks' median trajectory peak (17-22 Hz). The C effects that the synthetic calibration was
  tuned on therefore come from a different intervention regime.

**Fix (in the hidden-data generator before it runs; version 3).**
- Document the clip, and store the applied delta in the event record, or make the generator never request an impossible delta.
- Draw intervention targets from neurons that are active at the event time (for example, rate > 1 Hz in the twin), or scale kicks
  to each neuron's public range, as the synthetic suite does.
- Report the fraction of null pairs per family.

If the generator stays as it is, at least pre-register a descriptive C over non-null pairs.

### M2. Synthetic held-out intervention "types" generalise by construction, and a kick-clipping artefact contaminates held-out kick_group

**Evidence.**
- **Group interventions are sums of single-neuron effects.** Synthetic neurons couple only through the rank-K population signal
  `c = D(v - b)` (SYNTHETIC_BENCHMARK.md section 2), and kicks, currents and silencing all enter through D:
  - a group kick moves c by the sum over j of `D[:, j] dv_j`;
  - silencing gives `dz/dt = (I - D_S E_S) f(z) - lam D_S E_S z`, with `D_S E_S` equal to the sum over j in S of `D_j E_j^T`.

  Group kicks, group currents and group silencing are therefore exact superpositions of single-neuron operators at the level of the
  perturbation. v1's operators (a sum through C_0) and the true-latent reference exploit exactly this. In a connectome rate network
  with thresholds and rectification, group silencing is not additive.
- **The H M1 artefact is concentrated in held-out C.** A synthetic kick that leaves a saturating neuron's range is clipped 1e-6
  inside it and inverted through arctanh / logit (core.py:63-76, 336-340). I re-ran `.tmp/H/kick_clip.py` on the DEV suite:
  - 189 of 1093 kicked neurons (17 %) leave the range;
  - the activation jumps reach 26x the neuron's scale;
  - the resulting latent jump can exceed the trajectory's sd of z (hopf test kick_group: |dc| 1.15 against sd 0.75);
  - most of the worst cases are TEST kick_group, i.e. held-out C in the verdict.

  Biologically this is inverted. A rate unit pushed past saturation should transmit LESS additional drive; here it injects a very
  large hidden drive. PROTOCOL section 10.1 keeps it "as a limitation", but it affects a verdict family.

**Fix.**
- Scope the Level B claim to "held-out targets and additive group compositions of single-neuron interventions in population-code
  systems", and do not present it as evidence for circuit-level type generalisation.
- Pre-register a sensitivity analysis of kick_group and combined C that excludes the kicks leaving the range. The generator stays
  locked; only the pairs are filtered, and their count is reported.

### M3. "Real" is a simulated rate model with assumed parameters. Several hold-outs described as "real" do not exist in it

**Evidence.**
- The model has these properties (model.py docstring and code):
  - one global synaptic gain b = 0.03 x signed synapse count for every synapse;
  - a first-order threshold-linear-tanh rate ODE: no synaptic or adaptation dynamics, no spiking, no process or observation noise;
  - neuron parameters are "MODEL_PARAMETER: assumed, never anatomy".
- PROTOCOL section 1 calls Level C "the real-circuit result", and throughout it and in the code the systems are "real". Line 20
  lists "noise realisations" among the hidden hold-outs, but the real engine is deterministic: there is no noise to hold out.
- "Held-out parameter draws" (H_nominal, H_init_state) are i.i.d. draws from the same distribution that already gives every
  training trajectory its own draw (425/425 distinct seeds). They test nothing beyond ordinary sampling.
- The protocol rightly calls real verdicts conditional on the synthetic calibration. The conditions differ in ways that matter:
  - dt 1 ms against 10 ms;
  - one parameter draw per trajectory, against 8 shared draws in synthetic training;
  - absolute-Hz kicks against sd-scaled ones (M1);
  - non-additive against additive intervention operators (M2);
  - near-silent readouts (B1).

**Fix.**
- In the report, call Level C "connectome-constrained rate-model simulations". State the model's assumptions next to every
  real-system result, and never phrase a result as a statement about the animal's circuit.
- Remove "noise realisations" from the real hold-outs. Describe the parameter hold-out as "new i.i.d. draws".
- List the calibration-transfer differences above in the conditional-verdict statement.

### M4. Dependent and nested systems risk being counted as replicates; the real I-sharing test is not pre-registered and is conceptually ill-posed

**Evidence.**
- **net1 and net3 are one reconstruction.** Both enter the primary family as separate full systems (8 of the 12 real tests), and
  the Level C output (`level_c.py`) carries no lineage flag on those tests; only the J row has the "same reconstruction" note.
- **The mechanism systems are overlapping variants from one Phase 2 run, not independent mechanisms.** All three net2 mechanisms
  contain neurons {653, 1052}. Both net1 mechanisms contain {2825, 2973}, and both net3 mechanisms contain {1251, 1351}
  (data/regenerated_candidates.json). Statements such as "k = 1 on 7 of 7 mechanisms" are not 7 observations.
- **I-sharing on real systems is defined only in the script.** `level_c.py` runs I (shared dynamics plus leave-one-out) over each
  NETWORK's full system together with its keep-only mechanisms. PROTOCOL section 4 defines I only on "the systems of one group", and
  section 7 defines J; neither defines real I groups.
- **Those groups are not alternative implementations of one computation.**
  - The mechanisms are nested keep-only subsets of the full circuit.
  - Their observed populations differ by two orders of magnitude (3-6 against 197-213 neurons).
  - Two of them do not share the full system's sustained dynamics (minor m1).

  "Supported" would mean something different from the synthetic groups, and "rejected" would be expected by construction.

**Fix.**
- Pre-register the real I groups, or drop I on the real systems (report it descriptively if kept).
- Add a reconstruction-lineage field to every Level C row.
- Pre-state that no claim may count net1 and net3 as two confirmations, and that overlapping mechanism variants count as one
  mechanism family.

### M5 (method; relay generically). The selected dimension cannot represent the real systems' dominant dynamics, and real A equals the input-only control

**Evidence.**
- **The readouts oscillate.** On 8 of 10 real systems (nominal, after 0.5 s) the readout carries a sustained oscillation at 6-17 Hz:
  - 78-94 % of the non-DC power lies at the peak frequency;
  - the sd of the last 0.5 s over the sd of 0.5-1.0 s is 0.99-1.00 (`rhythm.py`).
- **v1 selects k = 1 on every real system** (notes section 7.5). With the stimulus held constant, a 1-D autonomous flow
  z' = f(z, u) cannot oscillate.
- **v1's real A is essentially the input-only control's:**

  | system | v1 A | input-only A |
  |---|---|---|
  | net1:full | 0.099 | 0.099 |
  | 02fa | 0.018 | 0.017 |
  | 3aa9 | 0.044 | 0.041 |
  | 3e8f | 0.136 | 0.139 |
  | 6883 | 0.076 | 0.069 |

- **It is worse than the persistence floor** (y held at its value at t0, same windows, `afloor.py`) on 4 of the 7 mechanism
  systems: 02fa 0.018 vs 0.004, 3aa9 0.044 vs 0.027, 6883 0.076 vs 0.003, 9261 0.037 vs 0.007.
- The notes say "k = 1 on all of them" but do not say that k = 1 cannot represent the rhythm. The dimension rule is driven by an
  NMSE in which the rhythm is a small share of the variance (B2).

**Generic requirement for the developer.**
- The dimension rule must not select a k whose dynamics class cannot reproduce the dominant structure of the validation data (for
  example, a sustained oscillation needs k >= 2).
- Selection must be checked against the persistence floor, and the selected model must beat persistence where the data are not
  static.
- Report both checks per system.

---

## Minor issues

- **m1. Two of the seven "mechanism" systems do not sustain the rhythm.** net3:mech:92614efe (labelled `final_core`) and
  net1:mech:02fa13b8: the main readout's sd decays from 0.59-0.60 Hz (0.2-0.5 s) to 0.003-0.004 Hz (1.5-2 s) under the constant
  nominal stimulus, i.e. a damped oscillation. The keep-only rhythm criterion of Phase 2 may use another regime. Do not describe these
  systems as rhythm generators in the report. C and E on them concern a decaying transient.
- **m2. The 0.01 Hz activity threshold inflates N_observed.** Half the "observed" neurons of the full systems peak below 1 Hz (see
  M1). The compression figure k / N_observed (F) and the compact criterion k <= N_observed / 5 therefore count quiet neurons. Report
  k against the number of neurons that are active by a stated physiological threshold as well.
- **m3. Pulses can latch a network into a persistent high-rate state.**
  - Current pulses (up to 40 units for up to 150 ms into one neuron) drive 4 of 50 (net1), 5 of 50 (net2) and 8 of 50 (net3)
    pulse_A trajectories above 60 Hz.
  - Rates reach 210-220 Hz, near r_max, against a 17-22 Hz median peak.
  - In 4 of 50 net3 trajectories the network stays above 60 Hz to the end (`sat.py`).
  - These pairs will dominate the C denominator of the pulse families. Report them as state switches.
- **m4. Real currents are depolarising only (+5 to +40)**, whereas the synthetic currents are signed. "Current" results on the real
  systems cover excitation only.
- **m5. H_stim_ood (scale 1.5-2.0) may recruit neurons outside x.** The observed population is fixed by probes at scales 0.6-1.4.
  The engine stores every neuron that is ever non-zero, so the fraction of activity outside x can be computed. Report it with the
  OOD results, so that a failure of H there is not read as a state failure.
- **m6. Mechanism systems inherit the whole network's readout list.** 6-12 of their 9-20 readout dimensions have zero training
  variance. This is harmless for effects (d = 0) but misstates n_y. Report the active readout count.
- **m7. The public twins lack the event breakpoints.** Their pre-event readout difference is at most 0.0106 Hz (I measured this; it
  matches the protocol's <= 0.011 Hz), which is small next to the effects. Hidden twins keep the breakpoints (section 10.1). Nothing
  to fix; noted for completeness.

---

## What I checked and found sound

- **The real engine.**
  - The model is a first-order rate ODE whose full state is the rate vector. The "FULL microstate" restart of the real E pools is
    therefore truly complete: no hidden synaptic or adaptation variables are left out.
  - The piecewise composition keeps the right-hand side smooth inside each piece.
  - Kicks respect non-negative rates.
  - Weight noise preserves signs (truncated at -1).
  - Silencing zeroes rows and columns: the output is removed instantly and the recorded rate relaxes with tau. This is a sensible
    rate-model reading of "silencing".
- **Consistency between the benchmarks.** The synthetic silencing semantics (inputs cut, relaxation to baseline, rebound on release)
  mirror the real ones, and the generator lists them honestly as the author's definitions (section 12.3).
- **The generator's documentation is candid.** It covers the flat manifold, uniform lam, silencing and edge-removal semantics,
  parameter hold-outs that are only same-distribution draws, and traps tested against simple baselines only. Latent exactness is
  tested against an independent solver.
- **The protocol states the real-data caveats correctly.** It says real networks are not replicates, that per-network results are
  separate, and that cross-network pooling and J are descriptive with net1+net3 reported apart. Real verdicts are declared conditional
  on the synthetic calibration, and edge removal is correctly excluded from the verdict as structural.
- **No finite blow-ups** in the public real data by the evaluator's rule (`blowup.py`). Public twins are aligned before the event
  (m7).
- **v1's notes are honest about the real failure.** They report not-predictive, C ~ 1, and k = 1. The notes use the simulator
  budget 0 and do not claim biological validity.
