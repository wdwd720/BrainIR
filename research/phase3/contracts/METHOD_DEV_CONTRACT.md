# Method development contract — state discovery (Phase 3 clean room)

You develop ONE family of methods (your assignment is in your first message) for discovering low-dimensional causal state
representations of simulated neural systems. Several developers work in parallel on different families in this room; a tournament
selects among them on held-out data you never see. You receive aggregate tournament feedback only.

## 1. The problem

Each *system* s is a simulated population of neurons. For every trajectory you get the observed microstate x(t) (T x N_obs), the
external input u(t) (T x n_u) and a readout y(t) (T x n_y), sampled every dt, plus the protocol that produced it (parameter draw,
initial state, input schedule, microscopic interventions as events: `kick` (instantaneous state offset of neurons), `current` (extra
input into neurons during a window), `silence` (neurons removed during a window), `edge_remove` (couplings removed; synthetic
systems)). Learn

    encoder   z_t = phi_s(x_{<=t}, u_{<=t})     causal (no future samples), never using y
    dynamics  z_{t+dt} = f(z_t, u_t, events_t)
    readout   y_t = g_s(z_t, u_t)

with small k such that z is
- predictively sufficient: multi-step rollouts from z predict y nearly as well as the full microstate does;
- approximately closed (Markov): discarded microstate and longer history add little;
- interventional: the model predicts the EFFECTS of interventions, including intervention TARGETS and TYPES never seen in training
  (e.g. several neurons silenced together, kicks to groups, removed couplings);
- microstate-equivalent: different microstates with equal z have equal futures;
- stable across seeds; compact; and, where several systems are alternative physical implementations of one computation, explained
  by ONE shared f with system-specific encoders / readouts when the evidence supports it (and not when it does not).

Be able to ABSTAIN per system: "no compact state under current evidence", "dimension unresolved in [a, b]", "observational state
only; causal equivalence failed". Abstaining correctly on systems without a compact state is scored; abstaining on systems that
have one is scored as a false alarm.

## 2. What you have (all inside this room)

- `src/brainir_state/`: `api.py` (StateMethod / StateModel interface, config keys, info keys, result schema: IMPLEMENT THIS),
  `data.py` (datasets), `protocol.py` (protocol format), `evaluate.py` (the metric families), `harness.py` (how the evaluator
  assembles them: `hidden_sets`, `evaluate_system`, `fit_references`, `REAL_CFG` / `SYNTH_CFG`, family roles, `verdict`),
  `evaluate_cross.py` (reproducibility, shared-vs-independent comparisons, paired statistics), `evaluate_lift.py` (latent-intervention
  lifting), `refmodels.py` (reference controls: full-state ceiling, input-only, readout-history, PCA / random-projection linear
  models), `simclient.py` (simulation service client).
- `data/synthetic_dev/`: synthetic development systems with KNOWN-TO-THE-BENCHMARK (not to you) hidden state. dt 10 ms, 4 s
  trajectories. Splits: `train`, `val`, `test` (held-out initial states, parameter draws, structural noise, intervention types and
  targets: see the manifest's `families` legend), `twin` (the counterfactual twin of each test intervention trajectory: same protocol
  and noise realisation, no events; `info.pair` links them), `pool` (microstate-equivalence pools: `micro_index.json`,
  `micro_futures.npz`). You may evaluate on all of them with the public evaluator; the tournament uses NEW systems of the same kinds.
  Systems include controls that have no compact state and traps that fool naive representation learning.
- `data/real_public/`: simulated connectome-constrained circuits (networks net1 / net2 / net3; per network the intact circuit
  `real:<net>:full` and keep-only reductions `real:<net>:mech:<id>` to candidate mechanisms found from public evidence by an
  earlier method: `data/regenerated_candidates.json`). dt 1 ms, 2 s trajectories; splits `train`, `val`, `twin` (twins of the
  validation interventions). `data/systems_public.json`: populations, the neurons you may intervene on (`targets_public`), the local
  signed connectivity (`local_graph`, `signs`). The input u is the stimulus current; the readout y is a set of output neurons
  (never part of x). net1 and net3 are two builds of one reconstruction; net2 is an independent one.
- `docs/PROTOCOL.md`: the frozen evaluation (read it: it says what is held out and how every metric is computed; section 7 gives
  the verdict rules and `data/tolerances.json` the calibrated tolerances).
- `docs/METHODS_REVIEW.md`: a methods-only literature review (families, baselines, evaluation measures).
- The simulation service (`SimClient().run([protocol, ...])`): new experiments on the public systems within the public policy
  (public parameter draws, public input ranges, single-neuron kicks / currents / silencing on public targets; synthetic systems:
  rest initial state, development parameter draws 0-7, no group or structural interventions) and your budget (`budget()`; budget
  units per trajectory: real full circuit 10, real mechanism 3, synthetic 1; 6000 units per developer). Active experiment design
  and counterexample search are encouraged; every call is logged. A real full-circuit trajectory takes 10-30 s to simulate.

## 3. Rules

1. Generic methods only: no special cases for particular systems, networks or suites; no hard-coded latent dimension (choose k
   with a generic rule, stated in your notes, that uses training / validation data only); no semantic labels ("phase", "amplitude",
   "excitation"...) as training targets.
2. Never feed y to the encoder; never let the encoder see samples after t. Preprocessing must be causal (no future smoothing, no
   normalisation with statistics of held-out data).
3. Control capacity: report parameter counts (encoder / transition / readout) in `info()["n_params"]`; prefer the simplest model
   that meets the requirements.
4. Test your method against the reference controls on the PUBLIC data with the public evaluator (dev `test` / `twin` / `pool`;
   real `val` / `twin`).
5. CPU is shared: use at most 3 threads (`torch.set_num_threads(3)`, `OMP_NUM_THREADS=3`); keep single experiments under ~20
   minutes.
6. Work only inside this room.

## 4. Deliverables

- `src/brainir_state/methods/<name>.py` (one or more): `StateMethod` subclasses registered with `brainir_state.api.register`, whose
  `fit(train, systems=..., config=..., sim=None, seed=...)` returns a `StateModel` implementing `encode`, `rollout` (with events),
  `readout`, `supports`, `info` and, if your family allows, `lift`. Requirements the tournament relies on:
  - `train` holds the `train` and `val` trajectories of the systems to fit (the `split` field tells which); `systems` their manifest
    entries (every entry has `observed`, `input_dim`, `targets_public`; real entries also `readout`, `local_graph` and `signs`). At
    fit time only `train`, `systems`, `config` and `sim` are available (no files);
  - honour the config keys of `api.CONFIG_KEYS`: `k` (forced dimension), `sharing` (`independent` / `shared` / `partial` for a fit
    on several systems; declare what you support in `supported_sharing`), `adapt_from` (encoder-only adaptation of a fitted model to
    new systems with the transition law frozen; `supports_adaptation`);
  - a fit is DETERMINISTIC given its seed, reads no files, starts no processes, uses no network (the tournament runs fits in a
    sandbox that refuses all of these), finishes within 20 minutes on 3 threads for one synthetic system (40 minutes for a real
    full system or a shared fit on several systems), and the model is picklable (`StateModel.save`; no lambdas or local classes);
  - `sim` may be None at fit time (then fit from the data only); if you use it, a fit gets 250 budget units (synthetic 1 unit per
    trajectory, real mechanism 3, real full circuit 10) and must work (possibly less well) when the budget is exhausted;
  - `info()` reports `k`, `k_range`, `abstain` (per system), `n_params`, `sharing` and `train_cost`.
- `tests/methods/test_<name>.py`: fast tests on toy data you generate in the test.
- `notes/<name>.md`: the algorithm and its mathematics, assumptions, objective, dimension rule, abstention rule, hyper-parameters and
  how you chose them, results on public data against the reference controls (all metric families you can compute), failure modes,
  compute used, and what you could not make work.
