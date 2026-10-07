# Contract: synthetic CAUSAL-STATE benchmark systems (author: a fresh agent with no access to any method or result)

You build the synthetic systems on which methods that learn CAUSAL state models will be developed, selected and confirmed. You
never see the methods; method developers never see your code or any ground truth. They only receive simulated observations of
your systems and may request further simulations through a budgeted service that enforces a public policy.

The scientific question the benchmark serves: a latent representation can predict ordinary trajectories well, have low dimension
and reconstruct the readout, and still fail to preserve what happens when the system is causally perturbed. Methods must learn a
low-dimensional state z whose dynamics MEDIATE the effects of microscopic interventions, generalise to unseen intervention types and
targets, and support valid latent <-> microscopic intervention mappings. Your systems must make that distinction measurable.

## 1. What a synthetic system is

A system has a TRUE CAUSAL STATE z(t) in R^k (k small, except for the non-compressible controls) that evolves by known controlled
dynamics, is physically realised by a population of N units with microstate x(t) (plus any hidden units / internal variables you
need), receives an exogenous input u(t) in R^{n_u}, and produces a task-relevant readout y(t) in R^{n_y}. The units are the physical
implementation: dynamics are simulated in MICROSTATE space, so microscopic interventions (on units, connections and unit parameters)
have real consequences, and z is recoverable from the microstate only through the implementation.

Definition you must honour and document per system: z is the causal state with respect to the benchmark's FULL intervention set
(section 3): given z(t), the future inputs and the future interventions, the future readout is determined (up to declared noise),
and two microstates with equal z have equal readout futures under every permitted future intervention sequence. Where passive
(non-intervened) data admit a smaller or different sufficient state z_obs, also define z_obs (the observational shortcut).

## 2. System types (all 25 required; several variants / difficulty levels each)

 1. linear controlled state-space model               14. irrelevant high-variance nuisance units
 2. nonlinear controlled oscillator                   15. intervention-sensitive LOW-variance state
 3. leaky integrator with interventions               16. hidden parameter / context state
 4. perfect integrator                                17. partial observability requiring delay / history
 5. gated memory                                      18. multiple attractors
 6. bistable switch                                   19. transient dynamics + steady-state dynamics
 7. winner-take-all                                   20. genuinely high-dimensional system: NO compact causal state
 8. negative feedback controller                      21. observationally compressible but interventionally NON-compressible
 9. coupled fast / slow state                         22. readout prediction easy but causal state hard
10. hidden discrete mode + continuous state           23. intervention confounding
11. redundant physical implementation                 24. redundant low-level intervention realisations
12. multiple microscopic circuits implementing the    25. same immediate readout, different causal state
    SAME z-dynamics (several implementations)
13. latent state embedded through a nonlinear population code

THE CENTRAL TRAP (make it the core of several types, e.g. 15, 21, 22, 25, and variants of others): systems where an
observational latent z_obs predicts normal trajectories extremely well but fails badly under interventions, because some
causally relevant variable has little passive variance, is exposed only by perturbation, or is observationally aliased. A good
method must reject z_obs and recover the interventionally sufficient z. Make the trap principled (a real dynamical property, not a
coding artefact), graded in difficulty, and document why z_obs fails and which intervention families expose it.

For type 12 (and 11 / 24 where natural) several implementations of the same z-dynamics differ in unit count, connectivity,
observation mixing, redundancy, nuisance dynamics and permutation; also provide pairs of UNRELATED systems that must not be judged
equivalent. Type 20 has no compact causal state; type 21 has a compact passive description but needs a large state under
interventions; state what an honest method should report for them ("no compact causal state").

Observation maps must vary: random linear mixing, sparse population codes, redundant copies, nonlinear saturation, mixed signs
where appropriate, partial observation (some units unobserved), observation noise levels. All of this must be calibrated (section 5).

## 3. Interventions (protocol format `p4-protocol-1`: docs/PROTOCOL_V2.md; validate with `ref/protocol.py`)

Every system must implement EVERY microscopic kind meaningfully: `kick` (instantaneous state offset of units), `current`
(additive input to units during a window; activation and inhibition; pulses, sustained, persistent), `current_seq` (piecewise-
constant input sequences: pulse trains, binary sequences, chirps), `silence` (remove a unit's synapses, inputs and outputs, during a
window; define precisely), `edge_scale` (scale listed connections; weakening, removal), `param` (unit gain, threshold, time
constant), initial-condition changes (`r0`), stimulus schedules, weight noise, `params_spread` (multiplies the
spread of the per-trajectory parameter draw around its nominal distribution; 1.0 = nominal) and `process_noise` (additive noise on
the unit states, seeded; declare its support and a sensible scale in the capability record). Single, paired and grouped targets
must all be possible. Observation noise is added by the benchmark to the arrays you return (declare only obs_scale). Do not assume
an intervention's effect is independent of the current state: where the dynamics make effects
state-dependent (oscillators, switches, gates), keep that. Distinguish instantaneous, finite-duration and persistent semantics.

Truth-only events for the evaluator (never available to methods): `latent_set` (do(z := z*)) and `latent_kick` (z += dz), each
implemented by an exact microscopic change you define.

Per system, a CAPABILITY record: which units may be targeted, which connections exist and may be scaled, which parameters may be
perturbed, natural magnitude units for each kind (the "moderate" magnitude that produces a clearly detectable but non-saturating
readout effect from a typical state), a detection-floor estimate, the natural time scale, the pulse / sustained duration scale, the
nominal stimulus pattern, and the admissible microstate range (clipping). The benchmark derives effect-size classes (below detection,
weak, moderate, strong) and development / held-out families from these, so they must be honest.

## 4. Package interface (`p4synth`, in your workspace)

```python
def build_suite(tier: str, seed: int, n_per_type: int | None = None) -> dict[str, "SyntheticSystem"]
    # deterministic in (tier, seed); opaque system ids; seeded variants; n_per_type defaults: dev 2, val 2, conf 3, other tiers 1

class SyntheticSystem:
    system_id: str; engine_id: str             # engine_id = generator / simulator version string (enters every cache key)
    n_units: int; observed: list[int]; readout_dim: int; input_dim: int; dt: float; t_end_default: float
    def content_hash(self) -> str              # hash of the full system definition (enters every cache key)
    def public_record(self) -> dict            # docs/PROTOCOL_V2.md section 3 fields, WITHOUT the split (the benchmark adds it and
                                               # the public / hidden target partition): kind "synthetic", dt, t_end_default,
                                               # n_units, observed, readout_dim, input_dim, targetable units, edges, obs_scale
                                               # {"x", "y"}, capability, cost_units
    def capability(self) -> dict               # section 3 above
    def simulate(self, protocol: dict, full: bool = False, restart_state=None) -> dict
        # protocol: canonical p4-protocol-1 (truth events latent_set / latent_kick allowed here)
        # returns {"t": (T,), "x": (T, n_obs) observed units, "u": (T, n_u), "y": (T, n_y), "info": {...}}
        # full=True adds "state": (T, n_state) the complete microstate (all units and internal variables; restartable),
        # "z": (T, k) the TRUE causal state, "z_obs": (T, k_obs) the observational shortcut where defined
        # restart_state: a full microstate vector that replaces r0 (the benchmark resolves restart keys / pool states to it)
        # obs_noise in the protocol is IGNORED here (the benchmark adds observation noise to the returned arrays itself)
    def rest_state(self) -> np.ndarray         # the microstate of r0 = {"kind": "rest"}
    def true_state(self, state) -> np.ndarray              # z from a full microstate
    def obs_shortcut_state(self, state) -> np.ndarray | None
    def true_latent_effect(self, state, event) -> np.ndarray   # dz of an instantaneous microscopic event at this microstate
    def lift_latent(self, state, delta_z, n: int) -> list[list[dict]]   # n DISTINCT microscopic interventions realising z + dz
    def equivalent_states(self, state, n: int, rng) -> list[np.ndarray] # microstates with the same z, different microscopic detail
    def pool_states(self, n: int, rng) -> list[np.ndarray]              # diverse reachable microstates (for equivalence tests)
    def truth(self) -> dict   # type, trap label, k (or "none"), f / g / read-in description, observation map, implementation
                              # group, z_obs definition and why it fails, which intervention families expose which directions,
                              # observability / controllability notes, expected honest verdict
```

`r0` may also be `{"kind": "state", "values": {...}}` over the unit ids of your public record (explicit initial values of units;
internal variables at rest).
Simulation must be accurate (state the integrator and step; test convergence), deterministic given the protocol (including
`params_seed`, `weight_noise`, `obs_noise` seeds), and fast: at most about 0.2 s CPU for a typical 2 s trajectory, so that hundreds
of thousands of trajectories are affordable. `params_seed` draws the system's own parameters within its variant (time scales, gains,
noise), never its type.

## 5. Calibration to the real systems (docs/CALIBRATION_TARGETS.md, `ref/calibration_targets.json`, checker `ref/calibstats.py`)

The real systems' GENERIC statistics (from public data) are given: observed-population dimensionality, activity scales and
sparsity, time scales and frequency content, intervention magnitudes and response sizes (including near-zero effects), response
sparsity, persistence, parameter variability, observation counts, readout dimensions, durations and sampling, input gains,
saturation / clipping. Your suite, built with the benchmark's generic protocols, must fall inside the recommended target ranges for
the statistics marked "required", pooled over the suite, while each system type keeps its defining property. Report the check for
every statistic (pass / outside, with values). Do not copy any real system: match distributions, not identities.

## 6. Deliverables

- `p4synth/` (systems, 25 types with variants, capability records, truth, build_suite);
- `tests/`: each type's causal-state claim checked from truth-level data (e.g. equal z => equal futures under interventions;
  z_obs sufficient passively but insufficient under the exposing interventions; k recovered from truth), implementation groups
  share dynamics, lifts realise their target dz, equivalent states are equivalent, determinism, integration convergence, speed;
- `SYNTHETIC_BENCHMARK.md`: every type and variant, the central trap and its gradings, observation maps, parameter ranges, time
  scales, intervention semantics per kind, capability conventions, integration accuracy, timings, calibration check results,
  known limitations;
- `calibration_report.json` from `ref/calibstats.py` on a dev-tier build.

## 7. Rules

- Work only inside your workspace; run code only through `sbx` (a Docker sandbox: `sbx python ...`, `sbx pytest ...`).
- The benchmark is generic. Do not model any specific biological circuit, dataset or published result.
- Do not tune anything to make a particular method succeed or fail; traps must be principled.
- Report honestly what is and is not tested.

## 8. Addendum (numerical requirements; tests must check each)

1. Integration step: the internal step is independent of the output dt (or the output dt is fixed per system); document the step and
   its accuracy with a self-convergence test (halving the step changes y by less than 1e-3 of the system's detection floor over a
   long horizon).
2. Stability at the extremes: every system integrates stably at the benchmark's largest magnitudes (time-constant factor down to
   0.1, gain factor up to 1.9, kicks and currents up to the `hi` ranges of the capability record, i.e. up to about 9 x the moderate
   magnitude); a failed or non-finite integration must be reported through `info["success"] = False`, never returned silently.
3. Process noise: drawn from a counter-based stream keyed by (seed, absolute step index), so that a restart from a stored state or a
   split of the integration into pieces reproduces the uninterrupted trajectory exactly; Euler-Maruyama or better; the sd per sqrt(s)
   documented in the capability record.
4. Clipping: a kick clipped to the admissible range is clipped identically in `simulate` and in `true_latent_effect`.
5. Latent effects: `true_latent_effect` matches the simulated jump of the true state (state which definition, e.g. the jump between
   the pre-event sample and the next sample, and test it).
6. Equivalent states: `equivalent_states` verified by simulation (identical readout futures under every event kind the system
   supports).
7. Hashes: `content_hash` covers everything that changes a trajectory; `engine_id` changes whenever the simulation code changes.
8. Restarts: `simulate(protocol, restart_state=s)` from a state recorded at sample i reproduces the original trajectory from sample i
   on (without process noise: bit for bit; with process noise: through requirement 3).
