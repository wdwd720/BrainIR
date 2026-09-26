# Contract: Review G — NEW adversarial trap families for causal state models trained with interventions

You are the adversarial reviewer of a benchmark for learning low-dimensional CAUSAL state models of simulated neural systems with
interventions. Candidate methods learn an encoder z = phi(x_{<=t}, u_{<=t}), controlled latent dynamics z+ = f(z, u, a), an explicit
intervention read-in R(z, a), a readout y = g(z, u) and a native lift. They are judged on intervention-effect prediction (including
intervention families and targets never seen in fitting), state mediation, interventional closure, microstate equivalence under
intervention, lifts and multiple-lift consistency, dimension, abstention and calibration.

The existing synthetic generator (`p4synth/`, documentation `SYNTHETIC_BENCHMARK.md`) already covers 25 system types. Your job is
to build NEW trap families that the method developers and the composer of the candidate do not know about. Each trap must be able
to fool a causal-state method that passes the existing benchmark, while remaining principled: a real property of dynamical systems,
interventions or neural implementations, never a filter tuned against a particular algorithm.

Consider at least these trap ideas (use your judgement; construct them from first principles):
A observationally perfect / causally wrong latent; B intervention-ID shortcut; C input-history shortcut; D time / phase shortcut;
E hidden slow state exposed only by perturbation; F latent dimension that changes under intervention; G hysteresis; H weak causal
variable with tiny variance; I two microscopic states equal observationally but different under intervention; J parameter context
masquerading as state; K intervention saturation / clipping; L state-dependent intervention efficacy; M nonlinear composition of
interventions; N redundant intervention implementations; O intervention that affects an unobserved nuisance but not the task state;
P no compact causal state.

## Deliverables (in this workspace)

1. `p4synth/review_g.py`: `review_g_catalog(seed) -> list[SyntheticSystem]` returning 12-20 NEW systems built with the existing
   package interface (every system implements the full SyntheticSystem interface: simulate, capability, truth, true_state,
   obs_shortcut_state, true_latent_effect, lift_latent, equivalent_states, pool_states, rest_state), each with a trap label
   "G-A" ... "G-P", its documented causal state (k or "none") and the honest verdict a correct method should reach.
2. `tests/test_review_g.py`: for every trap, tests that it behaves as claimed from truth-level data, that a simple representation
   learner (e.g. PCA + linear controlled dynamics fitted on passive plus training-family data) is fooled in the intended way, and that
   the trap is not trivially unsolvable (the true causal state predicts its intervention effects).
3. `REVIEW_G_TRAPS.md`: per trap: construction, what it attacks, why it is principled, what a correct method should do (handle it
   or abstain), limitations.

## Rules
- Work only inside this workspace; run code only through ./sbx. No web access.
- Do not modify the existing systems, the package's core or its tests (add only); keep every existing test green.
- The traps must be generic: do not model any specific biological circuit or published result.
