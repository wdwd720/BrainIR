# Phase 2 method-development contract (for every method developer, human or agent)

You are implementing a **generic causal mechanism-discovery method**. It receives a public problem and an expensive
black-box simulator with a hard query budget, and must return a compact, causal, uncertainty-aware mechanism. It is
developed and tested on synthetic instances whose true mechanism is known only to the tournament scorer, and it will
later be run — unchanged and locked — on a real benchmark whose answer neither you nor your code may know.

## 1. The problem your method receives

`brainir.discovery.DiscoveryProblem` (loaded from a bundle-format directory): a signed synapse-count graph
(`W` post×pre, `C` observed counts, `signs` per neuron, `sizes`), a stimulated input neuron with a constant-current
pulse (`stim_positions`, `stimulus()`), a readout population (`readout_mask`), the rate-model configuration
(`model_cfg`) and a **functional criterion** (`criterion_spec`: one of `rhythm`, `activity_band`, `persistence`,
`selectivity`, `ramp`). The target computation is "the readout satisfies the criterion under the stimulus".
Candidate mechanism members are `problem.candidate_positions()` (everything except stimulus and readout).

`brainir.discovery.BudgetedSimulator`: `sim.run(SimQuery(intervention, seed))`, `sim.run_many([...])`,
`sim.evaluate(intervention, seeds)`, `sim.pass_fraction(intervention, seeds)`. Every new simulation is one **call**
against `sim.max_calls`; exceeding it raises `BudgetExhausted` (your method must catch it or stay within
`sim.remaining`). Interventions: `brainir.discovery.silence(positions)`, `keep_only(problem, positions)` (stimulus
and readout are always kept), weight-noise variants, group designs in `brainir.discovery.interventions`. Outcomes
carry `score`, `passed`, `frequency_hz`, `n_active_readout`, `active_positions` (activity fingerprint) and more.
Cost model: a full-network simulation of a 4,600-neuron graph takes ~2.4 s; a keep-only simulation of a small subset
~0.1 s — group/keep-only probes are ~20× cheaper than single silencing probes on the intact network.

## 2. What your method must return

`brainir.discovery.DiscoveryResult`: `core` (positions), `inclusion_probability` (p(z_i = 1) for every candidate you
assessed — calibrated where possible), `roles` (generic roles from `brainir.discovery.interface.GENERIC_ROLES`, with a
probability; `unknown` allowed), `essential` (per core member: silencing it alone destroys the function — True/False/None),
`alternatives` (other mechanisms you consider functionally equivalent), `loop`, predicted frequency / active readout /
function-preserved, `fidelity` (your own keep-only estimates, nominal and robust), `diagnostics`, `motif`.
The result converts to the frozen prediction schema automatically (`to_prediction`).

## 3. Rules (violations disqualify the method)

1. **Benchmark-generic.** No special cases for any dataset, no hard-coded mechanism size, no cell-type names, no neuron
   ids, no thresholds tuned to a particular instance. Everything you use must come from the problem object, the
   simulator and your own synthetic experiments.
2. **Budget honesty.** Every simulation goes through the `BudgetedSimulator` you are given. No side simulators.
3. **Uncertainty, not one answer.** If several mechanisms are equally supported, say so (`alternatives`,
   probabilities) instead of forcing one.
4. **Robustness.** Evaluate candidates across several parameter seeds (the simulator's `seed`), not one.
5. **Minimality with evidence.** Report members whose removal keeps the function as non-essential; do not output a set
   that is minimal only because of your search order.
6. **No answer-seeking.** Never look for, read about or reason about the published circuits of the real datasets.
   Never read anything outside your clean development directory.

## 4. Development loop

- Generate your own synthetic instances for debugging with `brainir.discovery.synthetic` (you know their truth: that
  is fine — they are yours). The **evaluation** suite's truth is not available to you.
- Register the method: `src/brainir/methods/<name>.py`, subclass `DiscoveryMethod`, decorate with
  `@MethodRegistry.register`, import it from `src/brainir/methods/__init__.py`.
- Run it through the public entry point: `python -m brainir.discovery.run --method <name> --bundle <dir> --network main
  --out pred.json --budget 1000 --seed 0`. It must also run under the clean-room runner
  (`benchmarks/dng100/cleanroom/run_method.py`, which sandboxes file access).
- Tests: add `tests/test_method_<name>.py` (deterministic under seed; respects the budget; valid prediction schema;
  recovers your own tiny synthetic mechanisms).
- Feedback from the tournament scorer arrives as aggregate metrics per mechanism family (success rate, calls,
  functional pass rates, Brier score), never per-neuron information.

## 5. Deliverables

`src/brainir/methods/<name>.py`, tests, and `research/phase2/methods/<name>.md`: the algorithm in plain language and
pseudocode, its hyper-parameters, complexity, stopping rule, what it does with the budget, known failure modes, and
what your own synthetic experiments showed (with the exact commands).
