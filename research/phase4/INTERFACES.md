# Phase 4 interfaces (GENERIC; the source of the room documents `docs/PROTOCOL_V2.md` and `docs/API.md`)

This file contains no history and no result. It fixes the contracts between the benchmark (simulators, service, evaluator,
harness) and the methods (learners, designers). Module names refer to the `phase4/` package `brainir_causal`.

## 1. Protocol v2 (`brainir_causal.protocol`, format id `p4-protocol-1`)

One protocol = one simulated trajectory of one system. JSON, canonicalised by `validate()` (unknown keys are errors; every
optional field appears in the canonical form with its default); content hash = sha256 of the canonical protocol + the system's
content hash + the engine and simulator versions (`protocol_hash`). The store keys MICROSTATES by the canonical protocol without
`obs_noise` (`microstate_protocol`), because observation noise never changes the simulated microstate.

```
{"system": "<system id>",
 "params_seed": int,                       # draw of the system's physical parameters (per trajectory)
 "params_spread": float,                   # in [0, 3], default 1.0 = the nominal parameter distribution; multiplies the standard
                                           # deviations of the parameter draw (OOD tests; development: 1.0 only)
 "weight_noise": {"sd": float, "seed": int} | null,   # multiplicative structural noise, fixed for the whole trajectory
 "process_noise": {"sd": float, "seed": int} | null,  # additive noise on the unit states during integration, only where the
                                           # system's capability["process_noise"]["supported"] (real systems: never; the engine
                                           # refuses it); development: null unless the capability gives a development range
 "r0": {"kind": "rest"}                    # the system's rest state (default)
     | {"kind": "state", "values": {"<unit>": value, ...}}      # explicit initial microstate (units not listed = rest value)
     | {"kind": "restart", "key": "<key>", "t": t}   # the full microstate of a stored trajectory at its sample time t (the
                                           # service accepts the trajectory keys it served to the caller or published, and maps
                                           # them to store keys; stored real states are float32)
 "t_end": float, "dt": float,              # duration and output sampling (s)
 "stimulus": [[t, value], ...],            # piecewise-constant exogenous input u (value: float, or list for n_u > 1)
 "events": [event, ...],                   # interventions (below)
 "obs_noise": {"sd": float, "seed": int} | null}      # additive Gaussian noise on the returned x and y, sd relative to the
                                                      # system's published observation scale (robustness only)
```

Units are the system's public unit ids (integers, positions in its unit list). Events (times in seconds, snapped to the output grid;
`t1: null` = until the end of the trajectory):

| kind | fields | semantics | class |
|---|---|---|---|
| `kick` | `t`, `delta: {unit: d}` | instantaneous offset of the targets' state variables (result clipped to the unit's admissible range) | instantaneous |
| `current` | `t0`, `t1`, `targets: {unit: I}` | additive input current during [t0, t1) (I > 0 activation, I < 0 inhibition) | finite / persistent |
| `current_seq` | `t0`, `seg`, `targets: {unit: [I_1, ..., I_m]}` | piecewise-constant current, I_j on [t0 + (j-1) seg, t0 + j seg); pulse trains, binary sequences, chirps (seg >= 5 dt) | finite |
| `silence` | `t0`, `t1`, `targets: [units]` | remove all synapses of the targets (inputs and outputs) during the window | finite / persistent |
| `edge_scale` | `t0`, `t1`, `edges: [[post, pre], ...]`, `factor` | multiply the listed synaptic weights by factor in [0, 2] (0 = removal, < 1 = weakening) | finite / persistent |
| `param` | `t0`, `t1`, `targets: {unit: {"gain": g, "threshold": d, "tau": c}}` | multiply gain by g and time constant by c, add d (in the system's input units) to the threshold; omitted fields unchanged | finite / persistent |
| `latent_set` | `t`, `z: [..]` | SYNTHETIC TRUTH ONLY (evaluator): set the true causal state | instantaneous |
| `latent_kick` | `t`, `dz: [..]` | SYNTHETIC TRUTH ONLY (evaluator): shift the true causal state | instantaneous |

A trajectory record samples the state BEFORE an instantaneous event at its time t; the jump appears between t and t + dt.
`breakpoints(p)` lists every time the right-hand side changes. `intervened_units(p)` lists every unit an event acts on.

## 2. Intervention families (`brainir_causal.families`)

`family_of(protocol, system)` returns one label of the frozen vocabulary (ranges per system in its capability record):

- observational: `obs.nominal`, `obs.stim` (stimulus schedule other than nominal), `obs.init` (r0 other than rest), `obs.param`,
  `obs.wnoise`
- single-event: `kick.1`, `kick.2`, `kick.g` (1 / 2 / >= 3 targets); `kick.hi` (1 target, magnitude above the development range);
  `pulse.1`, `pulse.2`, `pulse.g`, `pulse.hi` (current shorter than the pulse limit); `act.1` / `inh.1` (sustained or persistent
  positive / negative current, 1 target); `sil.1`, `sil.2`, `sil.g` (temporary), `sil.1p` (persistent, 1 target); `edge.w`
  (0 < factor < 1), `edge.rm` (factor 0); `param.1` (1 target)
- temporal patterns: `seq.train` (>= 3 equal pulses), `seq.prbs` (binary sequence), `seq.chirp` (frequency-swept sequence),
  `seq.pp` (two pulses separated by a gap)
- composition: `comp.seq` (two different single interventions, the second after the first ended), `comp.sim` (two different kinds
  overlapping in time)

Each system has a SPLIT RECORD: `families_train` (development and fitting may use them), `families_heldout` (evaluated only on
held-out data; the simulation service refuses them for this system) and the global HIDDEN-ONLY families (never simulatable in
development on any system). Synthetic systems rotate their held-out sets across systems (rotations frozen in the benchmark).

## 3. Systems and capability records (`systems_public.json`)

```
{"system_id": str, "kind": "real" | "synthetic", "dt": float, "t_end_default": float,
 "n_units": int, "observed": [units], "readout_dim": int, "input_dim": int,
 "targets_public": [units],            # units development interventions may target
 "edges_public": [[post, pre], ...],   # edges development edge interventions may target (may be empty)
 "obs_scale": {"x": float, "y": float},
 "capability": {"<kind>": {"supported": bool, "max": float, "max_duration": float, ...}, ...},
 "split": {"families_train": [...], "families_heldout": [...], "rotation": str | null},
 "public_graph": {...} | null}         # public connectivity summary among observed / target units, where published
```

## 4. Data (`brainir_causal.data`)

A trajectory record: `t (T,)`, `x (T, N_obs)` observed microstate, `u (T, n_u)` exogenous input, `y (T, n_y)` readout,
`protocol` (canonical), `family`, `split` (train / val / twin / pool / test...), `key` (content hash), `meta` (e.g. `twin_of`: the
key of the intervention trajectory whose counterfactual twin this is: same parameters, noise, initial state and input, no events).
An `ExperimentSet` is an ordered list of records with per-record provenance (who chose it: `benchmark`, `designer:<name>`).

## 5. The causal state model (`brainir_causal.api.CausalStateModel`; goal5 sections 14-16, 47-49, 90)

```
encode(sid, x_hist, u_hist, dt) -> z (k,)                 # causal: x and u up to t only; never y, never the future;
                                                          # history length used = info()["history"][sid] (counted as complexity)
step(sid, z, u, events_active, dt) -> z_next              # one controlled latent step with the intervention semantics
read_in(sid, z, event) -> {"dz": (k,)} | {"operator": {...}}   # R(z, a): latent effect of one physical intervention at state z
                                                          # (instantaneous kinds: dz; finite / persistent kinds: the latent
                                                          # operator it applies while active, as the model represents it)
rollout(sid, z0, u_future, events, dt) -> {"z": (H+1, k), "y": (H+1, n_y), "y_sd": (H+1, n_y) optional}
                                                          # events relative to time 0; may include latent_kick / latent_set in
                                                          # MODEL coordinates (used by the lift test)
readout(sid, z, u) -> y
intervention_effect(sid, x_hist, u_hist, u_future, events, dt) -> {"y_int", "y_base", "effect", "z_int", "z_base",
                                                          "effect_sd" optional, "abstain": bool, "validity": {...}}
                                                          # counterfactual API; default implementation = encode + two rollouts
lift(sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None) -> [{"events": [...], "predicted_dz": (k,),
                                                          "cost": float}, ...]
                                                          # NATIVE lift: distinct physical interventions (kinds and targets the
                                                          # system's capability allows) that move z to z + delta_z
uncertainty(sid, x_hist, u_hist, u_future, events, dt) -> {"y_sd": (H+1, n_y), "p_detectable": float, "p_sign_pos": (n_y,)}
validity(sid, x_hist, u_hist, events) -> {"in_domain": bool, "score": float, "reasons": [...]}
supports(sid, event_kind) -> bool                         # False = the evaluator scores abstention, never silent "no effect"
info() -> {"k", "k_range", "abstain", "history", "n_params": {"encoder", "transition", "read_in", "readout"}, "train_cost":
           {"cpu_s", "gpu_s", "flops", "sim_calls", "experiments"}, "sharing", ...}
schema() -> BrainIRCausalStateModel                        # the versioned description (goal5 section 48)
```

`abstain` in `intervention_effect` means "insufficient evidence": the prediction is not scored for accuracy but counts against
coverage. A model that never abstains is scored as confident everywhere.

## 6. Methods and designers (`brainir_causal.api`)

```
class CausalStateMethod:            # the learner
    fit(data: ExperimentSet, *, systems, config, seed) -> CausalStateModel
    update(model, new_data, *, data_all, systems, config, seed) -> CausalStateModel   # default: fit(data_all)
    designer() -> Designer | None   # the method's own experiment design policy, if any

class Designer:                     # experiment design (goal5 sections 24-29, 38)
    propose(sid, system, model, data, n, budget_left, rng) -> [protocol, ...]         # protocols within the system's
                                                                                      # families_train and capability
```

Config keys every method honours: `k` (force the dimension), `sharing` (`auto` | `independent` | `shared` | `partial`),
`adapt_from` (a fitted model whose transition is frozen; fit encoders / read-ins only), `budget` (number of intervention
experiments the method may request through its designer, 0 = none).

## 7. Experiment loop (`brainir_causal.loop`; goal5 sections 24-28, 60)

For one system: start from the benchmark's passive set D0 -> repeat { designer proposes n protocols -> the service validates them
against the public policy and simulates them (content-addressed cache) -> the learner updates } until the budget B is spent. The
model is checkpointed after 10, 25, 50, 100, 200 intervention experiments and each checkpoint is evaluated. Costs recorded per
checkpoint: experiments, simulator calls, simulated seconds, unique targets, magnitude budget (sum over events of |amplitude| x
duration, kicks counted as |delta| x dt), CPU and GPU seconds. Reference designers (benchmark code): `random`, `uniform`
(coverage of target x family x magnitude cells), `magnitude_sweep`, `greedy_error` (next experiments near the largest observed
prediction errors), `structural` (targets by public connectivity), `passive` (the same number of trajectories without
interventions), `fixed` (a pre-registered design).

## 8. Simulation access for developers

Only through the service (`brainir_causal.simclient.SimClient`): request files in the room's queue, results back as arrays of the
observed quantities only (x, u, y). The service refuses anything outside the public policy (held-out and hidden-only families,
non-public targets and edges, hidden seed ranges, inputs outside the public range, truth events) and charges a per-agent budget.
Identical protocols are served from the store.
