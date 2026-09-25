# Contract: Review G — new adversarial trap families for state discovery

You are the adversarial reviewer of a benchmark for discovering low-dimensional causal STATE representations of simulated neural
systems. Candidate methods learn an encoder z = phi(x_{<=t}, u_{<=t}) from the observed microstate x, latent dynamics f(z, u,
events) and a readout g(z, u). They are judged on:
- multi-step prediction;
- Markov closure;
- the effects of held-out interventions (kicks, currents, silencing, removed couplings, on neurons never intervened in training);
- microstate equivalence;
- recovery of the true latent;
- dimension;
- abstention on systems with no compact state.

The existing generator (`p3synth/`, documentation `SYNTHETIC_BENCHMARK.md`) already has 48 systems with 20 dynamical families and
traps A-L. Your job is to build NEW trap families that the method developers do not know about. Each trap must be able to fool a
state-discovery method that passes the existing benchmark, while remaining principled: a real property of dynamical systems or
neural implementations, never a filter tuned against a particular algorithm.

## Deliverables (in this workspace)

1. `p3synth/review_g.py`: a function `review_g_catalog() -> list[SystemDef]` returning 8-12 NEW systems. Build them with the existing
   machinery (latents, blocks, embeddings, `SystemDef`) or with new latent / block classes that you add in the same module. Every
   system needs:
   - a documented latent dimension k, or "none" for a non-compressible control;
   - a trap label "G1", "G2", ...;
   - notes.

   They must work with the unchanged simulator, protocol, suite planner and truth writer, so that `build_suite` can build them.
   Add a function `build_review_g_suite(out_public, out_truth, seed)` that runs the suite builder on your catalogue only (tier
   "heldout" scale).
2. `tests/test_review_g.py`: for every new trap, a test that
   - it behaves as claimed (its latent dynamics are what the truth says);
   - a simple representation learner is fooled in the intended way;
   - the trap is not trivially unsolvable (the truth-level latent does predict it).
3. `REVIEW_G_TRAPS.md`: for every trap, the construction, what it attacks, why it is principled, what a correct method should do
   (handle it or abstain), and its limitations.

## Ideas to consider (use your judgement; do not copy existing traps)

- latent states observable only through intervention responses, not through spontaneous activity;
- slow parameter drift inside a trajectory (context vs state);
- delay-coupled latents (finite memory that looks like extra dimensions);
- input-dependent observability (a latent visible only under some inputs);
- two latents with identical observational statistics and different intervention responses;
- neurons whose tuning changes sign with the state;
- nuisance dynamics with the same timescale as the latent and correlated with it through the input;
- a system whose compact state holds only inside part of the state space;
- heavy-tailed or bursty intrinsic noise;
- partial observation that hides the causally important subpopulation.

## Rules

- Work only inside this workspace. You have no access to anything else and must not try to get it. No web access.
- Do not modify existing systems, the simulator core, the protocol, the suite planner or the truth writer (add only).
- Keep the existing 237 tests green.
- The traps must be generic: do not model any specific biological circuit or published result.
