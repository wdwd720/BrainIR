# Contract: methods-only literature review for INTERVENTIONALLY trained causal state models and active experiment design

## Problem (generic)

A simulated neural population of N units (N from ~3 to ~5,000; typically 10-200 observed) has a microscopic state x(t), an ordinary
exogenous input u(t), a task-relevant readout y(t), and can be perturbed by neural interventions a(t): instantaneous state kicks,
input-current pulses and sustained currents (activation / inhibition), temporal patterns (pulse trains, binary sequences, chirps,
paired pulses), silencing of units (temporary or persistent; single, paired or grouped), weakening or removal of connections, and
changes of a unit's parameters (gain, threshold, time constant). The simulator can also be restarted from arbitrary initial
microstates and parameter draws. Simulations cost from milliseconds to tens of CPU-seconds each, so the number of experiments
matters.

We want to learn, WITH interventions as part of the learning problem from the start (not only as a test afterwards):

    encoder        z_t = phi(x_{<=t}, u_{<=t})          small k; causal (no future, no readout copying)
    dynamics       z_{t+dt} = f(z_t, u_t, a_t)
    readout        y_t = g(z_t, u_t)
    read-in        Delta z = r(z, a)  or  z+ = R(z-, a)  (the latent effect of a physical intervention, with explicit semantics)
    native lift    given a target Delta z, find valid physical interventions a* with R(z, a*) ~= Delta z (min cost / complexity),
                   several DISTINCT ones a1, a2, a3 whose relevant futures should then agree

such that the intervention's effect FLOWS THROUGH z: after conditioning on z (and u, and the read-in), the residual microstate and the
intervention's identity add little predictive information about the future (a "state mediation" / "interventional closure"
property); microstates with equal z have equal futures under the same future intervention sequence; the state generalises to
intervention TYPES and TARGETS never seen during fitting; dimension k is chosen for intervention fidelity and closure, not for
passive prediction alone; the model abstains when evidence is insufficient (tiny effects, out of domain, no compact state).
Where several physical implementations share the same latent computation, a shared f with implementation-specific encoders /
read-ins may exist, but only after within-system causal validity.

A second goal is ACTIVE EXPERIMENT DESIGN: choose which interventions (target, kind, magnitude, timing, duration, temporal pattern,
sequence) to run so that the causal state is identified with fewer experiments than random or fixed designs, including designs that
excite poorly observed latent directions and designs that discriminate candidate model classes (e.g. k = 2 vs k = 3).

## Review, for each area

1. Interventional state-space models: recent formulations in which interventions / perturbations enter a latent dynamical model
   explicitly (e.g. perturbation-aware or "interventional" SSMs for neural data), their assumptions, identifiability results,
   intervention representation, linear / nonlinear limits, scaling, and whether a simulator like ours satisfies the assumptions.
   Find the most recent and most cited such work and describe it precisely enough to adapt it.
2. Causal representation learning with interventions: identifiability from interventional data (single-node / multi-node,
   perfect / imperfect, known / unknown targets), temporal CRL (e.g. latent causal processes with interventions), causal
   abstraction (exact / approximate transformations, interchange interventions) and what they imply for testing whether a latent
   state MEDIATES intervention effects.
3. System identification with inputs and interventions: DMD with control, subspace identification (N4SID, MOESP, CVA) with
   inputs, controlled / input-output Koopman models, SINDy with control and control-affine models dz/dt = f(z, u) + sum_j g_j(z) a_j,
   bilinear models, persistent excitation, identifiability of input matrices, empirical observability / controllability Gramians,
   Fisher information of dynamical models, balanced truncation with inputs.
4. Neural latent dynamical models with inputs: latent neural SSMs / RSSMs, neural ODEs / CDEs with control inputs, predictive
   bottlenecks, information-bottleneck objectives with interventions, ensembles for uncertainty.
5. Optimal and active experiment design for dynamical systems: Bayesian OED, expected information gain (and cheap estimators),
   query-by-committee / ensemble disagreement, D- / A- / E-optimal input design, Fisher-information design, active system
   identification, active causal discovery, model-discrimination designs, designs that reduce latent-dimension uncertainty,
   temporal-pattern designs (impulses, steps, PRBS, chirps, multisine), budgeted and batch designs, curricula; and how to compare
   a design policy FAIRLY against random / uniform / fixed designs (matched budgets, simulator cost, confidence intervals).
6. State equivalence and closure: causal states / computational mechanics, predictive state representations, bisimulation and
   bisimulation metrics (including with actions), approximate state abstractions in RL, tests of Markov / interventional
   closure (conditional predictive-information tests), and mediation analysis in dynamical settings with its assumptions.
7. Inverse problems for latent interventions ("lifting"): minimum-norm / constrained control to reach a target latent change,
   controllability, model-based stimulation design in neuroscience (choosing perturbations to move population states), and how to
   test that several distinct physical interventions realising the same latent change have the same consequences.
8. Uncertainty, calibration and abstention for dynamical predictions: selective prediction, conformal methods for time series,
   ensembles, calibration metrics (Brier, calibration error, coverage, confident-wrong rate), effect-size detectability with a
   noise floor.
9. Perturbation-based validation of dynamical models in computational neuroscience: what perturbation experiments can and cannot
   reveal about latent dynamics, dimensionality under perturbation, and known pitfalls.
10. Counterexample-guided refinement of learned abstractions by simulation (CEGAR-like loops; adversarial search for model
    disagreement: random, Bayesian optimisation, evolutionary, gradient-based).

For EVERY candidate method record: assumptions; identifiability; intervention representation; support for unseen intervention
types / targets; nonlinear capacity; interpretability of the read-in; scaling (N, T, number of experiments); compute (CPU vs GPU);
failure modes; relevance to the problem above; open-source implementations (package, maturity, licence) and whether a correct
from-scratch implementation is simple.

## Synthesis (the part developers will use)

- The 6-10 most promising candidate FAMILIES for a tournament, each with a concrete recipe (objective, read-in form, lift
  procedure, dimension rule, uncertainty / abstention), including at least: an interventional linear SSM, DMDc, subspace ID with
  control, sparse controlled SINDy / control-affine, an interventional predictive bottleneck, a controlled Koopman model, a latent
  neural controlled SSM, a neural ODE with an intervention operator, an adapted interventional SSM (area 1), a shared-dynamics
  model with implementation-specific encoders / read-ins.
- A candidate training objective with the terms observational future, intervention future, state mediation, interventional
  closure, microstate equivalence, lift consistency, complexity and uncertainty: for each term a definition, motivation,
  units / scaling and how to ablate it; say which terms the literature supports and which are speculative.
- 5-8 acquisition functions for active design with cheap estimators, and the fair comparison protocol.
- Strong BASELINES and how to implement each well: DMDc (tuned), controlled linear SSM, subspace ID, full-state controlled model
  (the predictability upper bound), input-only, intervention-only, readout-history, intervention-ID -> output direct model,
  random projection + control, PCA + control.
- Recommended measures and pitfalls for: intervention prediction (including near-zero effects), state mediation, interventional
  closure, microstate equivalence, lift success, multiple-lift consistency, held-out intervention-family generalisation,
  dimension selection and its uncertainty, representation stability up to transformations, calibration / abstention,
  information efficiency; leakage pitfalls (future leakage, output / input copying, intervention-ID memorisation, dimension
  cheating through pathological encodings, history hidden in large recurrent memories).
- Open problems where the literature gives no good answer.

Judge methods on the properties above, not on fashion. Cite every source (authors, year, venue, URL or arXiv id). Do not search
for, name or discuss any specific biological dataset, organism-specific circuit or connectome: this is a METHODS review.

Deliverable: `METHODS_REVIEW.md` in the room root (Markdown, sections I areas 1-10, II synthesis), plus `REFERENCES.md`.
