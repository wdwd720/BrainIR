# Contract: Phase 3 synthetic state-discovery benchmark (author: a fresh, oracle-free agent)

You build the synthetic benchmark on which state-discovery methods will be developed, selected and confirmed. You never see the
methods, and the method developers never see your generator code or any ground truth: they only receive generated trajectories.
Your deliverable is generic: dynamical systems with KNOWN hidden state, realised by simulated "neural" populations.

## 1. What a synthetic system is

A system has a hidden latent state z(t) in R^k that evolves by known dynamics dz/dt = f(z, u) (or a discrete-time map), is
realised by a population of N "neurons" with microstate x(t) in R^N, receives an external input u(t) in R^{n_u}, and produces a
readout y(t) in R^{n_y}. The neurons are the physical implementation: the dynamics must be simulated IN x-SPACE (so that
microscopic interventions have real consequences), and z must be recoverable from x only through the implementation, e.g.
x = h(z) + nuisance with x-dynamics that keep x near the manifold h(z) (or any other construction you can justify).

Implement, as a Python package `p3synth` in your workspace:

```python
class SyntheticSystem:
    system_id: str            # opaque id (set by the suite builder, never the family name)
    n: int                    # microstate dimension N
    observed: list[int]       # neuron ids the encoder may see (all of range(n) unless partially observed)
    readout_dim: int
    input_dim: int
    def simulate(self, protocol: dict) -> dict      # see section 3
    def truth(self) -> dict                          # see section 4 (NEVER shipped to method developers)
```

## 2. Families (all required; add variants and difficulty levels)

 1. linear stable state-space systems (several k)          11. negative feedback controller
 2. harmonic oscillator                                     12. coupled slow/fast dynamics (separated timescales)
 3. nonlinear oscillator                                    13. latent state + irrelevant nuisance neurons (incl. HIGH-VARIANCE nuisance)
 4. damped oscillator                                       14. redundant microscopic realisation (many neurons carry the same latent)
 5. limit-cycle oscillator                                  15. MULTIPLE physical implementations sharing ONE latent dynamic
 6. bistable switch                                         16. non-Markov projection trap
 7. leaky integrator                                        17. output-only shortcut trap
 8. perfect integrator                                      18. time-index shortcut trap
 9. gated integrator                                        19. hidden exogenous-variable trap
10. winner-take-all                                         20. genuinely high-dimensional system with NO small valid abstraction

Adversarial traps (each must be able to fool ordinary representation learning; methods should handle them or abstain):
A high-variance nuisance that does not cause the output; B a neuron that copies the readout; C a clock neuron tracking time;
D a neuron copying the stimulus; E many distinct microstates for one causal state; F hysteresis (same output, different hidden
state, different futures); G non-Markov compression (a 1-D embedding predicts one step but fails long-horizon); H a representation
that predicts because it encodes a parameter draw rather than state; I multiple limit cycles (cycle identity matters); J transient vs
limit cycle (amplitude/energy needed besides phase); K bifurcation (effective dimension changes with the input regime); L distributed
computation (no sparse neuron subset corresponds to the latent).

Observation maps must vary across systems: random linear embeddings, sparse population codes, redundant copies, nonlinear saturation,
mixed signs, observation noise, partial observation (some neurons unobserved). Sizes: N from about 10 to several hundred; k from 1 to
about 6 for compressible systems, and k comparable to N for the non-compressible controls.

For family 15 (and wherever it is natural), several implementations of the SAME latent dynamics must differ in neuron count,
connectivity, observation mixing, redundancy, nuisance dynamics and permutation, so that a method can be tested on whether it finds
one shared dynamics with different encoders. Also make pairs of UNRELATED systems that must not be judged equivalent.

## 3. Protocols (the same schema as the real circuits; see `protocol_spec.md`)

`simulate(protocol)` integrates one trajectory. The protocol fields: `system`, `params_seed` (a draw of the system's own parameters
within its family: timescales, gains, noise; the latent dynamics' TYPE stays fixed), `weight_noise` (structural perturbation, may be
ignored where meaningless), `r0` (initial MICROstate; {"kind": "zero"} means a default rest state, {"kind": "state", "values": {...}}
sets neurons), `t_end`, `dt`, `stimulus` (piecewise-constant input: [[t, value], ...], value a scalar that scales the system's nominal
input pattern, or a list of length input_dim), and `events`:

- microscopic (available to methods): `kick` (add delta to neurons' states), `current` (extra input into neurons during [t0, t1)),
  `silence` (remove neurons: their outputs and inputs are cut during [t0, t1); define precisely what this means in your
  implementation), `edge_remove` (where the implementation has explicit couplings);
- latent (EVALUATOR ONLY, never offered to methods): `latent_set` {"t", "values": {i: v}} (do(z_i := v)), `latent_impulse`
  {"t", "delta": {i: d}}. Implement them by the exact microscopic change your implementation defines (and expose that change:
  `lift_latent(delta_z, x) -> micro delta`), so an evaluator can check a method's own latent-to-micro lifting.

Return: `{"t": (T,), "x": (T, N) observed neurons only, "u": (T, n_u), "y": (T, n_y), "z": (T, k) TRUE latent, "info": {...}}`.
Integration must be accurate (state the method and step), deterministic given the protocol, and fast enough to generate tens of
thousands of trajectories on CPU. Timings must be documented.

## 4. Truth (kept apart)

`truth()` returns, per system: family, trap label (or null), latent dimension k (or "none" for non-compressible), a description of
f and g, the observation map type, which systems share latent dynamics (an implementation-group id), a statement of which inputs /
interventions reveal which latent directions (observability and controllability notes), and anything an evaluator needs to score
latent recovery. Truth is written ONLY by the suite builder's truth writer, never into a method-facing dataset.

## 5. Suite builder

`build_suite(out_public: Path, out_truth: Path, seed: int, tier: str)` builds a suite: systems with opaque ids, and for each
system a rich set of trajectories (many initial conditions, input strengths and timings, parameter draws, microscopic
interventions of every kind, and transient perturbations) in the dataset format of `data_format.md`, with a `split` label per
trajectory ("train", "val", "test"). Tiers: "dev" (development; public trajectories), "heldout" and "final" (built later with
secret seeds; same generator). Also write, into out_truth, the latent trajectories and every truth field. The test split must hold
out: initial states, parameter draws, noise, intervention TYPES (e.g. group silencing when training had single silencing only)
and intervention TARGETS (neurons never intervened in train/val).

## 6. Deliverables (in your workspace)

- `p3synth/` package (generators, systems, suite builder, truth writer);
- `tests/` with checks that each family's latent dynamics are what you claim (e.g. recovering k and f from truth-level data),
  that implementations in one group share dynamics, that traps behave as intended, and that simulation is deterministic;
- `SYNTHETIC_BENCHMARK.md`: every family, trap and observation map, parameter ranges, time scales, how each intervention is
  realised, integration accuracy, timings, and known limitations;
- a small example suite built with `tier="dev"`, `seed=0`.

## 7. Rules

- Work only inside your workspace. You have no access to anything else and must not try to get it.
- This benchmark is generic. Do not model any specific biological circuit, dataset or published result, and do not search the
  web for any (your session has no web access).
- Do not tune anything to make a particular method succeed or fail. The traps must be principled.
- Report honestly what is and is not tested.
