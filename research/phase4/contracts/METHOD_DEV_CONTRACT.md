# Method development contract — causal state models trained with interventions (Phase 4 clean room)

You develop ONE family of methods (your assignment is in your first message). Several developers work in parallel on other families
in this room; a tournament selects among them on data you never see; you receive aggregate feedback only. The benchmark is frozen:
`docs/PROTOCOL.md` says exactly how every method will be judged.

## 1. The problem

Predictive latent states are not sufficient: a latent representation can predict ordinary trajectories, have low dimension and
reconstruct the readout while failing to preserve what happens when the circuit is causally perturbed. Learn a causal state USING
interventions from the start.

Each system s is a simulated population of units. Every trajectory gives the observed microstate x(t) (T x N_obs), the exogenous
input u(t) (T x n_u), a task-relevant readout y(t) (T x n_y) and the protocol that produced it (parameter draw, initial state, input
schedule, interventions as events: kicks, current pulses / sustained currents / current sequences, silencing, connection scaling,
unit-parameter changes; `docs/PROTOCOL_V2.md`). Learn

    encoder   z_t = phi_s(x_{<=t}, u_{<=t})      causal, never using y or future samples; history length counts as complexity
    dynamics  z_{t+dt} = f(z_t, u_t, a_t)
    read-in   R(z, a): the latent effect of a physical intervention, with explicit, interpretable semantics
    readout   y_t = g_s(z_t, u_t)
    lift      given a target delta_z, several DISTINCT valid physical interventions a1, a2, a3 with R(z, a_i) ~= delta_z

such that: z is compact; predicts ordinary futures; predicts intervention outcomes, including intervention FAMILIES and TARGETS
never seen in fitting; after conditioning on z, the discarded microstate and the intervention's identity add little (state
mediation, interventional closure); microstates with equal z have equal futures under the same interventions; lifts realise their
target and distinct lifts of one target have the same consequences; k is chosen for intervention fidelity and closure, not passive
prediction alone; and the model abstains when evidence is insufficient (tiny effects, out of domain, no compact state). Where
systems are alternative implementations of one computation, a shared f with implementation-specific encoders / read-ins may
explain them, but only when the evidence supports it.

## 2. What you have (all inside this room)

- `src/brainir_causal/`: `api.py` (CausalStateModel / CausalStateMethod / Designer, config and info keys, the result schema:
  IMPLEMENT THIS), `protocol.py`, `families.py`, `data.py`, the evaluator (`evaluate*.py`, `harness.py`, `refs.py`, `loop.py`,
  `designers.py`, `stats.py`) and `simclient.py` (simulation service client).
- `baselines/brainir_state_v1/`: an earlier, locked state-discovery method (observational / predictive training), provided as a
  FROZEN BASELINE only: you may run and study it; never modify it.
- `data/synthetic_dev/`: 50 development systems of many kinds with a causal state known to the benchmark (not to you), including traps
  where a passively sufficient latent fails under interventions, systems with no compact causal state, and implementation groups.
  Splits and families: see the manifest. The tournament uses NEW systems of the same kinds, and every system holds out some
  intervention families (its split record says which) that you can neither download nor simulate.
- `data/real_public/`: simulated connectome-constrained circuits (full networks and candidate mechanisms), public splits only.
  `data/systems_public.json`: populations, public targets, capability and split records, public connectivity summaries.
- `docs/PROTOCOL.md` (the frozen evaluation), `docs/PROTOCOL_V2.md` (protocol format and families), `docs/API.md`,
  `docs/METHODS_REVIEW.md` (a methods-only literature review), `data/tolerances.json` (calibrated tolerances).
- The simulation service (`SimClient().run([protocol, ...])`; it finds your own queue by itself): new experiments within each
  system's public policy (its families_train, public targets, development ranges) and your budget (`budget()`), computed on the
  benchmark's reference platform (the same numbers the benchmark's own builds produce; your sandbox has the same pinned stack).
  You may restart from any trajectory you were served or any public trajectory (r0 = {"kind": "restart", "key": <its key>, "t": <a
  sample time>}). Active experiment design and counterexample search on development systems are encouraged.
- Compute: `sbx <cmd>` runs code in a Docker sandbox (no network, this room only, 2 CPUs, 3 GB). The machine runs ONE sandbox at a
  time for all developers: `sbx` waits for the shared slot (about 9 minutes at most, then exit code 75; retry; a run stops after 30 min by default, 1 h at most), so
  keep local runs to quick checks of a few minutes. Every fit, sweep or evaluation goes through the remote runner (your own queue
  `runs/<prefix>/_remote/`, see `docs/REMOTE_RUNNER.md`; CPU and GPU classes, many jobs in parallel).

## 3. Rules

1. Generic methods only: no special cases for particular systems, system kinds or suites (do not detect "trap" systems); no
   hard-coded latent dimension (a generic, stated rule using training / validation data only); no semantic labels as targets.
2. Never feed y to the encoder; never let it see samples after t; causal preprocessing only. Count history length as complexity; do
   not hide missing state in a large recurrent memory.
3. The read-in must have explicit semantics (not just an intervention embedding added to a recurrent network); events on targets or
   of kinds never seen in training must be handled through the model's structure, or abstained on honestly (`supports()` /
   `intervention_effect(...)["abstain"]`).
4. Objectives: every loss term needs a definition, motivation, units / scaling, an ablation switch and a sensitivity check. No
   magic loss soup.
5. Capacity: report parameters per component (encoder, transition, read-in, readout), training FLOPs if known, CPU / GPU seconds and
   simulator calls in `info()`. Prefer the simplest model that meets the requirements (goal: intervention prediction, mediation and
   closure first; then compression, observational prediction, experiment efficiency, simplicity, compute).
6. Counterexample-guided refinement: only with development systems and public data.
7. Work only inside this room; run code only through `sbx` or the remote runner.
8. The shared work areas are owned per developer: every developer READS all of `src/brainir_causal/methods/`, `tests/methods/`,
   `runs/` and `notes/`, but WRITES only its own `<prefix>/` subdirectory of each (`<prefix>` is given in your first message; it is
   also your sandbox scratch name). The sandbox binds only your own subdirectories read-write and the room guard refuses writes
   anywhere else; other developers' subdirectories are read-only for you.

## 4. Deliverables

- `src/brainir_causal/methods/<prefix>/`: your package (with an `__init__.py`; import your own modules relatively, e.g.
  `from .core import X`). The tournament imports every module of every developer's package, so registration happens on import; a
  method is named by its registered name (`<prefix>_...`) or as `<prefix>.<module>:<name>`. Its modules hold CausalStateMethod
  subclasses registered with `api.register`, whose
  `fit(data, systems=..., config=..., seed=...)` returns a CausalStateModel implementing encode, rollout (with events; optional
  y_sd), readout, supports, step, read_in, lift (native), intervention_effect (or the default), uncertainty, validity and info;
  optionally a Designer (`designer()`) for active experiment design. Requirements the tournament relies on:
  - `data` holds the system's passive and interventional training records (with twins); `systems` the public records. At fit time
    nothing else is available (no files, processes or network: the tournament's sandbox refuses them);
  - honour `api.CONFIG_KEYS` (`k`, `sharing`, `adapt_from`, `budget`, `ablate`); declare `supported_sharing` / `supports_adaptation`;
  - ABLATION SWITCHES: declare in `info()["ablation_switches"]` every name of `api.ABLATION_SWITCHES` (honoured, or
    "not_applicable" with a reason when your method has no such component) and apply `config["ablate"]` exactly as defined there
    (e.g. `interventional_training` = fit on the passive records only; `state_bottleneck` = predict without the compact state);
    report the applied list in `info()["ablated"]`. The locked method is ablated switch by switch after the lock;
  - a fit is DETERMINISTIC given its seed (on CPU; a GPU method must pass the CPU / GPU equivalence check of `equiv.py`), finishes
    within 15 minutes on 4 CPU threads for one synthetic system (30 minutes for a real full network or a shared fit), or within 10
    minutes on one GPU if the method declares `device = "cuda"` (tournament GPU fits run on the RTX-PRO-6000 class), and the model
    is picklable. Tournament fits run on Linux containers; initialise parameters in float64 (float32 initialisers round differently
    across platforms);
  - `info()` reports k, k_range, abstain (per system), history, n_params, train_cost.
- `tests/methods/<prefix>/test_<prefix>_*.py`: fast tests on toy data generated in the test (`sbx pytest -q tests/methods/<prefix>`;
  keep the `<prefix>` in the file names: test modules of different developers must not share a basename).
- Experiments, their scripts and outputs: `runs/<prefix>/`.
- `notes/<prefix>/*.md`: algorithm, mathematics, assumptions, identifiability conditions (goal: say under what assumptions the
  state and read-in are identifiable and whether the benchmark's systems satisfy them), objective and ablations, dimension and
  abstention rules, hyper-parameters and how they were chosen (development data only), results on public data against the
  benchmark references (every metric family you can compute), failure modes, compute used, and what did not work.
