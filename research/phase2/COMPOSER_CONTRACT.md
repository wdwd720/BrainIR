# Phase 2 contract: compose BrainIR v1 (for a fresh, oracle-free developer)

Read `METHOD_DEV_CONTRACT.md` and `CROSS_CONNECTOME_CONTRACT.md` first. All of their rules apply: benchmark-generic,
budget honesty, uncertainty, robustness, minimality with evidence, and no answer-seeking. Never read anything outside the
clean development directory.

## 1. What you have

- Five candidate discovery methods in `src/brainir/methods/`, each with its design document in
  `research/phase2/methods/<name>.md` and tests in `tests/test_method_<name>.py`:
  - `greedy_plus`: evidence-driven group elimination.
  - `cem_search`: cross-entropy / EDA search.
  - `group_probe`: active group testing with posterior inclusion.
  - `surrogate_search`: surrogate-assisted search.
  - `evo_pareto`: evolutionary multi-objective search.
- The reference `greedy_reference`, which re-expresses the frozen baseline's algorithm.
- The cross-connectome component `src/brainir/discovery/joint.py` (`discover_pair`, modes
  independent / transfer / prior / joint) with `research/phase2/methods/joint.md`.
- `research/phase2/selection_results/`: aggregate results of every candidate on a held-out synthetic suite you have
  never seen. It covers success (structural, functional, planted) with CIs, reliability across node orders and seeds,
  calls and simulated seconds, budget curves, robustness, minimality, calibration, roles, per-family breakdowns and the
  pair tournament. Aggregates are all you get: no instance, no truth.
- The library: `brainir.discovery` (problem, budgeted simulator with persistent-cache option, interventions,
  criteria, correspondence, transfer, synthetic generators) and the clean-room runner.

## 2. What to build

`src/brainir/methods/brainir_v1.py`: one coherent algorithm, registered as `brainir_v1`, following goal3 section 26.

1. Restrict the candidate graph using legal public structure: reachability, activity and signs. Never use names or
   ids.
2. Initialise inclusion probabilities, uniform or from `config["prior"]`.
3. Run structured group interventions (keep-only / silencing designs).
4. Infer posterior causal importance.
5. Optimise sparse, robust candidate masks across the parameter ensemble.
6. Validate candidates on the true simulator with fresh seeds.
7. Remove unnecessary members: 1-minimality with evidence, plus necessity by silencing in the full network.
8. Infer generic functional roles.
9. Align roles across connectomes when a second network is available (see §3).
10. Produce an uncertainty-aware result: inclusion probabilities, alternatives, essential claims, predicted frequency /
    active readout, fidelity.

Also required:

- **Intervention predictions.** For every core member, state the predicted effect of silencing it in the intact network
  (`essential`, backed by the silencing runs you did). Where defined, state the predicted effect of removing its
  strongest in-core edge, in `diagnostics["intervention_predictions"]`. These are pre-registered: the evaluator
  checks them.
- **MDL-style trade-off.** Along your search path, record core size versus functional error (1 - pass fraction on fresh
  seeds) in `diagnostics["size_error_curve"]`. Say which point you return and why. Compactness must never remove a
  member whose removal breaks the function.
- **Minimality with evidence.** Report members whose single removal keeps the function; the returned core should
  have none.
- **Roles.** Use the generic roles in `brainir.discovery.interface.GENERIC_ROLES`, each with a probability. Assign
  them from interventions and signed connectivity, never from names.

Take the best-supported parts of the candidates, justify every choice with the selection evidence, and drop what the
evidence does not support. The result must be ONE algorithm with a stated objective and stopping rule, not a vote
between five methods. It must never exceed the call budget it is given. It must be deterministic given `seed`. It
must not hard-code a mechanism size, and it must work for every criterion type.

## 3. Cross-connectome use in the real protocol

The clean-room runner invokes a method once per network (`BRAINIR_NETWORK`). The bundle copy it can read contains
all networks. `brainir_v1` may therefore read the other networks of its bundle. It may simulate another network only
through a separately created `BudgetedSimulator` with a fixed auxiliary budget set in the default config. Those calls
must be reported apart from the primary budget in `DiscoveryResult.diagnostics["auxiliary_budget"]`.

If you use the joint mode, emit `cross_connectome` claims through the diagnostics key
`diagnostics["cross_connectome"] = [{"source_position", "other_dataset", "other_version", "other_source_id",
"confidence", "basis"}]`. Take `other_dataset` and `other_version` from the other network's `DiscoveryProblem`, use
`other_source_id = other_problem.public_ids[position]`, and set `basis` to `"connectivity"`.
`DiscoveryResult.to_prediction` turns these entries into schema claims.

Decide, from the pair-tournament evidence, whether joint discovery is worth its auxiliary calls. If it is not, keep
v1 single-network and say so.

## 4. Deliverables

- `src/brainir/methods/brainir_v1.py` and `tests/test_method_brainir_v1.py`. The tests must be deterministic, respect the
  budget, produce a valid prediction and recover your own tiny mechanisms of several criterion types; total runtime is
  under 3 minutes.
- `research/phase2/BRAINIR_V1_METHOD.md` (goal3 section 45): mathematical formulation, pseudocode, objective,
  acquisition / intervention strategy, uncertainty model, complexity, stopping rule, hyper-parameters with defaults
  and their evidence, known failure modes, and your own experiments with the exact commands.
- A final summary message covering what v1 does, which components came from which candidate and why, your own results,
  known limitations, and the files created.
- Use at most 3 local worker processes, because the machine is shared.
