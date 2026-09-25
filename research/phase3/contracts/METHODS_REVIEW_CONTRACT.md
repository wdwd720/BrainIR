# Contract: methods-only literature review for causal state-variable discovery

Problem (generic): a simulated population of N neurons (N from ~10 to ~5,000; typically ~100 active) with state x(t), an external
input u(t) and a readout y(t). We can run the simulator with arbitrary initial states, input sequences, parameter draws and
microscopic interventions (state offsets, input currents into neurons, removing neurons or connections). We want an encoder
z = phi(x) with small k, a transition law z(t+dt) = f(z, u) and a readout y = g(z, u) such that z is: (1) predictively
sufficient over multiple horizons, (2) approximately Markov (closed), (3) interventionally sufficient (predicts the effects of
held-out perturbations, including unseen intervention types and targets), (4) microstate-invariant (microstates with equal z
have equal futures), (5) minimal in dimension, (6) stable across seeds and estimation procedures, (7) shared across different
physical implementations of the same computation (implementation-specific encoders, one shared f), (8) able to abstain when no
compact state exists. Latent coordinates are identifiable only up to transformations.

Review, for each area: nonlinear system identification; minimal state realisation; predictive state representations; causal
states / computational mechanics; balanced realisation and model reduction; Koopman operator learning; dynamic mode decomposition
(incl. extended/kernel DMD, DMD with control); SINDy and sparse identification (incl. SINDy autoencoders, with control);
subspace identification (N4SID, MOESP, CVA); delay/Hankel methods; neural state-space models (RNN/RSSM, variational SSMs,
deep Kalman filters); latent ODEs / neural ODEs / neural SDEs; intervention-aware representation learning; causal
representation learning and identifiability (incl. interventional identifiability); bisimulation metrics and state abstraction
(RL); invariant causal representation; nonlinear ICA where relevant; system identification under interventions; optimal /
active experiment design for dynamical models; observability and controllability (linear and empirical nonlinear); canonical
dynamical coordinates, phase reduction and phase response curves; limit-cycle identification; dynamical-systems methods in
computational neuroscience (population dynamics, LFADS-like models, dynamical similarity measures such as DSA); latent
dimension selection (information criteria, MDL, cross-validated prediction plateaus); comparing latent spaces up to
transformations (CCA, Procrustes, principal angles, CKA, dynamical conjugacy); counterexample-guided refinement of abstractions
by simulation.

For EVERY candidate method record: assumptions; identifiability; intervention support; nonlinear capacity; interpretability;
scaling (N, T, data size); failure modes; relevance to the problem above; available open-source implementations (package,
maturity, licence) and whether a correct from-scratch implementation is simple.

Then write a synthesis:
- the 6-8 most promising algorithm FAMILIES for a tournament, each with a concrete recipe, and why;
- a list of strong BASELINES and how to implement each well (PCA + linear dynamics, factor analysis, DMD, EDMD/Koopman,
  Hankel/delay methods, linear SSM identification, N4SID-style subspace ID, SINDy, autoencoder + linear latent dynamics,
  Koopman autoencoder, latent neural ODE, recurrent state-space model, variational SSM, predictive state representations,
  sequence model with bottleneck, random projection, input-only, readout-history-only and full-state predictors);
- recommended evaluation measures for each property (1)-(8) and known pitfalls (time leakage, output copying, input copying,
  future leakage, parameter-identity leakage, memorisation, dimension cheating through pathological encodings);
- open problems where the literature gives no good answer.
Do not pick methods because they are fashionable; judge them on the properties above.
