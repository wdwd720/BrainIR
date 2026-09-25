# Part II. Synthesis

The synthesis draws on the Part I entries and the per-area notes (Appendix). The notes do not cite by number; each claim
can be traced to the Part I entry for the named method, where its references are listed.

## II.1 Cross-cutting conclusions

### II.1.1 The target object already has a precise definition
Write Sim_h(x, u, a) for the law of the readout path y_{t+1:t+h} after starting from microstate x, applying the input
sequence u and the intervention a. Let 𝒯 be a bank of tests (u, a, h, readout functional). Then:

- **Predictive/interventional equivalence** (the target of (3) and (4)): x ~_𝒯 x' iff Sim_h(x, u, a) = Sim_h(x', u, a)
  in law for all tests in 𝒯. The name depends on the literature: Nerode equivalence in realisation theory (area A),
  causal states or predictive states (area C), bisimulation or lumpability for Markov processes (area C). If 𝒯 contains
  interventions, it is also the abstraction condition of causal-abstraction theory (area E: exact transformations,
  τ-abstraction). The ε-version replaces equality with a divergence below ε (MMD or W1 over simulator noise; a norm for
  deterministic simulators).
- **Closure (2)** follows for the exact relation. If x ~ x', their successors are equivalent in distribution: the
  quotient is Markov (bisimulation/unifilarity). For the ε-version, closure has to be *measured*, as quasi-lumpability
  spread or latent self-consistency. It cannot be assumed.
- **Minimality (5)** is the coarsest such relation. In coordinates, it is the smallest k for which a *smooth* encoder
  realises it. Linear case: Hankel rank. Finite case: number of causal states or automaton size.
- **Abstention (8)** means the required k (Hankel rank, number of causal states, required automaton size) keeps growing
  as ε shrinks or the horizon and test bank grow, up to a budget k_max. Chaotic regimes illustrate this: exact classes
  are singletons, so only (ε, H)-indexed equivalences make sense.
- **Interventional sufficiency for held-out types (3)** is the question whether ~_𝒯 implies ~_𝒯'. No general theory
  answers it (II.7); it must be tested on a held-out test bank 𝒯'.

The main practical consequence: **the simulator's reset ability turns (4) and (2) into directly testable statements**.
Draw pairs x, x' with phi(x) ≈ phi(x'), re-simulate both under identical u and a, and compare. Every family below should
be trained and evaluated against this ground truth, not only against held-out prediction error.

### II.1.2 What each literature contributes
- **Classical system identification and model reduction (A, G)** give exact answers for linear systems: Hankel singular
  values for minimality, similarity-invariant spectra and Markov parameters for (6) and (7), and designed excitation.
  They give the only *intervention-driven* choice of coordinates: empirical controllability and observability gramians
  built from exactly the perturbations the simulator allows. They are strong baselines, and they supply references and
  diagnostics for nonlinear methods.
- **Koopman/DMD/SINDy (B)** give cheap linear-in-features predictors and spectral invariants for comparison. They also
  give two closure tests: the ResDMD residual and operator inference's re-projection. Their hard limits:
  - a finite linear Koopman model that contains the state cannot represent multiple isolated attractors;
  - the lifted dimension is not k;
  - SINDy needs good coordinates first.
- **Predictive-state and bisimulation work (C)** supplies the definitions above, the spectral (Hankel/test-matrix)
  estimators, the counterexample-guided refinement loop (CEGAR, L*) and principled abstention signals.
- **Neural state-space models (D)** are the function classes and training tricks: multi-horizon rollouts, free bits
  and KL balancing, generalized teacher forcing for chaotic regimes, and stop-gradient latent self-prediction. None gives
  identifiability, minimality or interventional sufficiency, and many hide extra state (II.6).
- **Causal representation learning (E)** gives identifiability theory. At the macro level our micro interventions are
  unknown-target, multi-node and soft, so only the unknown-target/soft results fit even partially. Its most useful
  practical contributions are:
  - **interchange-intervention training and evaluation**, which directly operationalise (3) and (4);
  - **abstraction-error metrics**, which a 2026 paper validated on simulated systems (Méloux et al., arXiv 2607.00267,
    [read-full]; reports ~30 interventions per family for 95% power);
  - **multi-view block identifiability**, the only theoretical handle on (7).
- **Population-dynamics methods (F)** give low-rank RNNs, a rare family where micro interventions, including structural
  ones, are expressible natively. They also give the best-developed toolkit for comparing latent spaces and dynamics up
  to transformations, and the warning that bidirectional smoothers and inferred inputs are future and input leaks.
- **Experiment design and canonical coordinates (G)** turn the simulator into a source of **ground-truth probes**: direct
  phase response curves and isostable response curves, empirical gramians, Jacobians at fixed points, and bifurcation
  diagrams. They also give the budget and hold-out protocol, and invariant long-horizon metrics (D_stsp, D_H, Lyapunov
  spectra).

### II.1.3 Methods de-prioritised for the tournament, and why
These are de-prioritised on the contract properties, not on fashion. Several remain useful as baselines or diagnostics.
- **RSSM/Dreamer with its deterministic h, VRNN, and history-conditioned sequence models as state learners.** The carried
  history channel violates the closure and minimal-k accounting. Keep RSSM as a *history-based* baseline (II.4) and
  report k_effective = dim(h) + dim(s).
- **LFADS-style bidirectional encoders with inferred inputs.** They leak future information, and inferred inputs absorb
  unmodelled dynamics, which makes (2) and (3) untestable. Their generator with known inputs and a causal encoder is a
  variant of Family 1. The reference implementation has a non-commercial licence.
- **CITRIS/iCITRIS and linear interventional CRL (Squires et al.).** These need known macro targets, or perfect
  single-node macro interventions, which micro interventions do not provide. They are usable only inside Family 5, where
  macro interventions are *constructed* through realisers.
- **IRM.** Theory and critiques (Rosenfeld et al.) show that it does not reliably recover invariant features in the
  nonlinear regime. It can be a weak baseline.
- **VAMPnets/MSMs as the main learner.** The theory needs stochastic, (near-)stationary dynamics and has no input
  channel. Their Chapman-Kolmogorov test is still valuable as a closure diagnostic.
- **NARMAX/Volterra/GP-SSM.** These are input-output or history models, with poor scaling in the number of outputs.
  NARX on (y, u) history is used as the readout-history baseline.
- **CSSR and discrete automata learning as final models.** They are discrete and scale poorly to continuous
  high-dimensional x. They are valuable as abstention diagnostics on coarse-grained readouts (Family 8).

## II.2 Common interface and data protocol (applies to all families and baselines)

**Interface.** Every method must expose:
- phi: x(t) → z(t) ∈ R^k. It is instantaneous: no access to past or future beyond x(t). History variants are allowed
  only as labelled baselines, with the carried state counted in k.
- f: (z, u, [intervention code]) → z(t+dt). It may be stochastic.
- g: (z, u) → y.
- Optional: a declared intervention set, and an abstain flag with a confidence score.

**Fair k accounting.** k is the total dimension of everything carried between time steps: latent, hidden recurrent
state, and augmented or delay coordinates.

**Data.** Organised by factors: parameter draw p, implementation m, initial condition x0, input sequence u, and
intervention (type τ, target set S, amplitude, time t0). Area G's protocol:
- **Parameter draws.** 64-256 for training, 16 for validation, 32 for test, disjoint. For (7), also disjoint
  *implementations* of the same computation.
- **Initial conditions** from three sources, with the source recorded:
  - on-attractor: burn-in of at least 10 slowest time constants;
  - near-attractor: offsets at 3 amplitudes;
  - far: about 10% of the budget.
- **Inputs.**
  - Band-limited random multisines or filtered noise at 3 amplitudes; check that the input block-Hankel of the chosen
    depth has full rank.
  - Steps, pulses, chirps and zero input.
  - The u-generator family is recorded as a factor that can be held out.
- **Intervention types:**
  - state offsets on unit sets;
  - injected currents (constant, pulse, sinusoid);
  - unit removal;
  - connection removal;
  - global parameter shift.
- **Targets:** single units; random sets of 2, 5 and 10% of units; structured sets (e.g. top or bottom k by empirical
  controllability).
- **Amplitudes.** Three levels, calibrated per draw from < 5% to > 30% change in y.
- **Timing.** For oscillatory regimes, the intervention time is set relative to phase (8-16 phases).
- **Paired design.** Every perturbed run has an unperturbed twin with identical seed and initial state (clean effect
  estimates).
- **Budget allocation (fraction of total):**

  | Share | Use |
  |---|---|
  | ~35% | observational / input-driven runs |
  | ~25% | training interventions |
  | ~10% | probe measurements, used only for evaluation: PRCs, gramians, fixed points, bifurcation sweeps |
  | 10-20% | active or counterexample rounds |
  | ~15% | frozen held-out evaluation, plus an untouched final test set |

**Held-out splits.** Report each separately; never pool.
1. Within-distribution.
2. Held-out initial-condition source or basin.
3. Held-out targets, with the same intervention type.
4. Held-out intervention types (leave-one-type-out, including structural).
5. Held-out amplitudes, as extrapolation into the nonlinear regime.
6. Held-out input families.
7. Held-out parameter draws, and for (7) held-out implementations.
8. Held-out bifurcation regime.

Split by whole trajectories and whole parameter draws, never by time windows.

**Controls, needed to calibrate (5) and (8):** simulators or regimes with *known* answers:
- a linear or low-rank network with known state dimension;
- a network with a known low-dimensional attractor (e.g. a limit cycle) embedded in many units;
- a regime with a known non-compact state (high-dimensional chaos, or random coupling with a flat spectrum);
- a pair of different implementations of the same low-dimensional computation (for (7)).

Every threshold used for abstention or for choosing k is set on these controls, never on the test simulators.

## II.3 Tournament families

Selection criteria: direct targeting of (2)-(5); an honest route to (7) and (8); use of the simulator's reset and
intervention power; ability to run at N ≈ 100-5,000; availability of a checkable implementation. For each family: why it
is included, the recipe, the sweep, how k is chosen, and the main risks.

### F1. Closed latent dynamics, "encode once, roll out", with a ladder of transition classes
*Sources: area D candidate A/B, area B KAE-u and SINDy-AE-c, area C self-predictive objectives.*

- **Why.** This is the most direct parameterisation of the contract (phi, f, g). With an instantaneous encoder and
  open-loop rollouts, closure (2) and predictive sufficiency (1) are what the loss optimises. The f-class ladder gives an
  internal test of how much nonlinearity is needed. Interventions of the state-offset type are handled exactly by
  re-encoding.
- **Model.**
  - phi: an MLP N→512→256→k with LayerNorm. For N ≈ 5,000, use a linear N→64 layer followed by an MLP. Apply a
    spectral-norm or Lipschitz bound, and inject small Gaussian noise into z during training.
  - f, one rung of the ladder per run:
    - (a) linear, z' = Kz + Bu (Koopman AE; K parameterised as stable block-rotation × contraction);
    - (b) bilinear, B(z) = B0 + Σ z_i B_i;
    - (c) sparse polynomial, Θ(z,u)Ξ (SINDy-AE with control; sequential thresholding at 0.05-0.1 of standardised
      coefficients, then a final refit);
    - (d) switching or piecewise-linear (rSLDS/shPLRNN);
    - (e) residual MLP, z' = z + dt·MLP([z,u]), or a latent ODE with fixed-step RK4;
    - (f) the stochastic version of (e): Gaussian transition noise or a latent SDE.
  - g(z,u): linear first, then an MLP. Add an auxiliary low-weight decoder z→x to resist collapse.
- **Interventions.**
  - State offsets: z = phi(x+δ), then roll out.
  - Injected currents: map the N-vector of currents into a low-dimensional input code through a shared linear map P,
    u_int = P·I(t), so that unseen target sets remain expressible. Alternatively, pass the current through one simulator
    step and re-encode.
  - Structural interventions: either condition f on a descriptor d (ablation), or declare them outside the intervention
    set.
- **Loss.** Sum over horizons h ∈ {1,2,4,8,16,32,64} of:
  - readout NLL/MSE of g(f^h(phi(x_t), u), u);
  - λ_lat · ||f^h(phi(x_t)) − sg(phi(x_{t+h}))||² / Var(z);
  - low-weight reconstruction of x_{t+h}.

  Anti-collapse: a per-dimension variance floor. Variational version: free bits of about 1 nat, and KL balancing.
  Chaotic regimes: generalized teacher forcing, z̃ = (1−α)f(z) + α·phi(x_t), with α annealed from 1 to ~0.1-0.3; or
  multiple shooting with resets every ~ln2/λ_max. Counterexample pairs from F8 add a hinge term (below).
- **Sweep.** k ∈ {1,2,3,4,6,8,12,16,24,32} × 3-5 seeds × each f-class, plus the Lipschitz bound and the noise level.
- **Choosing k.** The smallest k whose held-out multi-horizon *and* held-out-intervention error is within 1 SE of the
  plateau reached by the full-state predictor. The equivalence gap (II.5, (4)) at that k must also be below threshold at
  the declared Lipschitz level. Report the whole curve.
- **Risks.** No identifiability (only equivalence up to diffeomorphism). Seed instability of nonlinear encoders.
  Dimension cheating without smoothness control. A linear f cannot handle multiple attractors, and the ladder exposes
  this. Structural interventions are unsupported.

### F2. Subspace and Koopman linear-operator identification with interventions as inputs
*Sources: area A (N4SID/CVA → EM, PSID), area B (DMDc, EDMDc + ResDMD + balanced truncation).*

- **Why.** This is the strongest non-deep competitor: deterministic, fast, interpretable, and with similarity-invariant
  outputs for (6) and (7). If it matches F1, deep encoders are not justified. It also supplies the k reference from the
  singular-value spectrum.
- **Recipe, variant (a): CVA-weighted subspace ID, then EM.**
  - Inputs: persistently exciting multisine or random-binary u on each input channel. State offsets are encoded as
    impulses on augmented input channels with known directions.
  - Outputs: (i) x, pre-projected to 100-200 PCs, and (ii) y alone. The output choice is itself a finding: states
    sufficient for x versus for y (PSID's n1 vs nx).
  - Past/future horizons p = f ∈ {5,10,20,40}, subject to T ≫ (p+f)(m+n_u).
  - Order from canonical correlations versus phase-randomised surrogates, Bauer-type criteria and the CV plateau.
  - Refine by EM with inputs (dynamax), initialised from the subspace estimate. Enforce stability.
  - Encoder: the regression from x to the Kalman state.
- **Recipe, variant (b): lifted Koopman.**
  - Pipeline: PCA to r ≈ 20-50; dictionary [1, PCs, K = 100-500 RBFs with k-means centres, optionally degree-2
    monomials]; ridge EDMDc with known B where available; discard modes with ResDMD residual > 0.1-0.2; balanced
    truncation to k.
  - Keep M/K ≥ 10-20.
- **Sweep.** Horizons, output set, ridge, dictionary size, RBF bandwidth, k.
- **Choosing k.** Singular-value/HSV elbow combined with the held-out multi-step plateau. Report both.
- **Risks.**
  - Linear or local only. Multiple attractors are impossible.
  - Data needs grow super-polynomially in n/m when only few outputs are available (Sun et al. 2025, stochastic case), so
    identify with x as output and evaluate on y.
  - Closed-loop bias if inputs depend on outputs.

### F3. Interventional empirical-gramian balanced reduction with learned nonlinear closure
*Sources: area A candidate 1, area G candidate 2 (Lall-Marsden-Glavaski empirical gramians, emgr).*

- **Why.** This is the only classical method whose coordinates are chosen *jointly* by:
  - what interventions can move (empirical controllability, from exactly the simulator's allowed perturbations);
  - what the readout can see (empirical observability, from ± state offsets observed through y over a horizon).

  Directions with low observability energy are, by construction, those with equal futures, which is prop (4). The
  Hankel singular values give (5). A linear phi is hard to cheat and stable across seeds (6).
- **Recipe.**
  - Operating points: 4-8 per parameter draw (on- and near-attractor).
  - Controllability ensemble: impulses into each input channel and a subset of unit directions, at 2-4 scales.
  - Observability ensemble: ±ε offsets along all N unit directions (2N runs) or along a random/PCA subset, with output y,
    and separately output x.
  - Compute W_c and W_o (or the cross gramian), average over operating points, balance by square-root SVD, and set
    phi = top-k balanced coordinates.
  - Fit f(z,u) by a small MLP or SINDy on projected trajectories, or by Galerkin projection if the simulator's vector
    field is accessible.
- **Sweep.** ε ∈ {1e-3, 1e-2, 1e-1} × state s.d. (report linearity checks); operating-point set; output choice;
  horizon; f-class.
- **Choosing k.** HSV elbow, confirmed by the multi-horizon/intervention plateau.
- **Risks.**
  - A single global linear subspace is chosen from local information: a curved slow manifold needs larger k.
  - Deterministic regime assumed (noise requires averaging).
  - Cost is O(N) runs per operating point. This is cheap for a simulator, but check memory at N = 5,000 (low-rank and
    cross-gramian options in emgr).

### F4. Microstate predictive-state regression on a probe bank (PSR / kernel causal states with resets)
*Sources: area C candidates 2-3 (spectral PSR, two-stage regression, HSE-PSR, kernel ε-machines), area A (Hankel/Nerode),
area F (reduced-rank regression).*

- **Why.** This is the most literal estimator of the equivalence relation in II.1.1. Microstates are resettable, so the
  estimator can regress x directly onto the law of its futures under a fixed probe bank. Histories are not needed. The
  rank of that map is the test-matrix rank, a principled estimate of (5), and absence of a spectral gap is an abstention
  signal (8). It is cheap, deterministic and scalable.
- **Recipe.**
  - Sample microstates x_i (the three IC sources).
  - For each x_i, simulate a probe bank 𝒯: 32-64 input sequences (steps, pulses, noise, zero) and a few training
    intervention types, at horizons {1,5,20,50} steps, with R noise seeds if the simulator is stochastic.
  - Record future-readout features: y windows, moments, or random Fourier features. This gives Φ_future (n × m).
  - Fit reduced-rank ridge regression x → Φ_future, sweeping the rank k. The left factor is a linear phi.
  - Nonlinear variant: random features or Nyström kernel on x, with a diffusion-map reduction of the conditional mean
    embeddings (kernel causal states).
  - Fit the transition f by two-stage regression: next predictive state on current predictive state × input features.
- **Choosing k.** Held-out predictive loss plateau, combined with the singular-value gap. Report the spectrum.
- **Sweep.** Probe-bank family and size (the key hyperparameter: equivalence is relative to 𝒯), horizons, ridge, feature
  map, kernel bandwidth.
- **Risks.**
  - Relative to 𝒯: held-out intervention types need a *different* 𝒯' at evaluation.
  - The linear version captures only linear predictive structure.
  - Kernel versions scale as O(n²) without Nyström.
  - Stochastic simulators need many seeds per state.

### F5. Interchange-intervention-trained abstraction (IIT/DAS adapted to dynamics)
*Sources: area E candidate T2 and Recipe B (Geiger et al. IIT/DAS; causal abstraction theory; causal feature learning),
area C (must-separate pairs).*

- **Why.** This family optimises (3) and (4) *directly*, with the simulator in the loop. It checks that setting
  z-coordinates to new values produces the micro futures the macro model predicts, whichever microstate realises them.
  It is also the family most naturally extended to (7): cross-implementation interchange.
- **Recipe.**
  - Start linear: z = Wx, with W orthogonally parameterised (DAS-style), plus f and g.
  - Interchange loss:
    - sample a base x_b, a source x_s and a coordinate subset S;
    - set the target z* = z_b with the S-coordinates taken from z_s;
    - build the realiser x* = x_b + W⁺P_S W(x_s − x_b), a minimum-norm state offset (supported by the simulator);
    - simulate H steps under the same u;
    - penalise ||phi(x*(t+h)) − f^h(z*)||² and ||y*(t+h) − g(f^h(z*))||².
  - Null-space faithfulness pairs: x_b + (I − W⁺W)δ must leave y and phi(future) unchanged.
  - Nonlinear phi: realisers by Gauss-Newton projection onto {phi(x) = z*}. Use several realisers per z* (minimum-norm,
    nearest pool state, and minimum-norm plus a random null-space component).
  - Combine with the F1 multi-horizon loss.
- **Sweep.** k, H ∈ {1..50}, null-space weight, realiser type, share of on-manifold (pool) realisers.
- **Choosing k.** The smallest k with realiser-spread and null-space ratio below the calibrated thresholds *and*
  held-out interchange error at the plateau.
- **Risks.**
  - Simulator calls inside training: batch and cache them.
  - Off-manifold realisers can pass or fail for the wrong reasons, so report on-manifold realisers separately.
  - Unrealisable z* must be counted.
  - Output-only interchange accuracy is not certification: intermediate z can still be wrong (Méloux et al.).

### F6. Unit-space low-rank RNN models (structural interventions expressible natively)
*Sources: area F candidate 1 (Mastrogiuseppe & Ostojic; Dubreuil et al.; LINT, Valente et al.; stochastic/SMC low-rank
RNNs).*

- **Why.** Among the reviewed families, this is the one where **all** micro intervention types act on the model's own
  variables:
  - offsets and currents act on units;
  - removal of a unit deletes a row and column of the connectivity;
  - removal of a connection edits one entry of the low-rank factors.

  The latent state is the projection onto the column space of the rank-R connectivity (plus input directions), and
  k = R + (input dims), which makes the rank a clean minimality knob (5).
- **Recipe.**
  - Fit τẋ = −x + (1/N)·M Nᵀ φ(x) + W_in u (rank R) to simulator rollouts: all unit activities and y, open-loop
    multi-horizon MSE from the true x0, through BPTT with GTF for chaotic regimes.
  - Data: random x0 (not only on-attractor), random piecewise-constant u, and training interventions.
  - phi(x) = least-squares projection onto span(M). f = the reduced latent ODE.
  - Structural-intervention test: apply held-out removals to the fitted connectivity and compare with the simulator.
- **Sweep.** R = 1..10, nonlinearity, noise, and implementation mapping (units may not correspond across
  implementations; for (7), use per-implementation M and N with a shared reduced f).
- **Choosing k.** The smallest R at which held-out multi-horizon and held-out-intervention errors plateau.
- **Risks.**
  - It assumes the simulator is well approximated by a low-rank network in unit space. It may need large R even when a
    compact state exists through nonlinearity, and the literature does not characterise this.
  - It needs full unit observations.
  - Fitting is non-convex.

### F7. Multi-encoder shared-dynamics training (one f, implementation-specific phi_m)
*Sources: area E candidate T3 (multi-view/content-style block identifiability; contrastive identifiability; CEBRA
multi-session), area F (lfads-torch multi-session scheme, cross-prediction), area B (shared K/Ξ).*

- **Why.** Property (7) is not addressed by any single-system method. This family puts it in the objective:
  - M implementations are run on identical u sequences;
  - per-implementation encoders phi_m and readouts g_m (or a shared g if the readout is common);
  - a single f.

  Multi-view block identifiability gives the only available theory: the shared content is recovered up to an invertible
  map when views share it. The prediction loss then ties the *dynamics*, not just the state, across implementations.
- **Recipe.**
  - Training: the F1 loss summed over implementations with a shared f, plus InfoNCE alignment between
    phi_a(x^a_t) and phi_b(x^b_t) at the same t and the same u. Also include *equal-u, different-x0* negatives, so that z
    cannot just encode u.
  - Similarity: L1 or Lp (p ≠ 2) similarity if an axis-aligned gauge is wanted; cosine similarity leaves an orthogonal
    ambiguity.
  - Evaluation, a held-out implementation test: freeze f, train only a new encoder on *observational* data of a new
    implementation, then test on its interventions (split 7 of II.2). Also run cross-implementation interchange (F5) and
    check swap symmetry.
- **Sweep.** k, alignment weight, temperature, time offsets, shared versus per-implementation g.
- **Choosing k.** As in F1, but on the held-out-implementation test.
- **Risks.**
  - Theory covers the shared state, not shared dynamics.
  - If the implementations' futures are not identical given equal u, alignment forces spurious sharing, so the family
    needs the abstention branch: compare against per-implementation f and report the gap.

### F8. Counterexample-guided refinement, active design and abstention wrapper (CEGAR-Z)
*Sources: area C candidate 1 (CEGAR, L*, CSSR split tests, bisimulation metrics), area G candidate 3 (BOED, ensemble
disagreement), area B (E-SINDy active learning), area E (causal feature learning's split/merge).*

- **Why.** This is not a model class. It is a loop that wraps F1-F7 and uses the simulator as an *equivalence oracle*.
  It is the natural mechanism for (4) and (2), and the only principled route to abstention (8). Every refinement is
  explained by a concrete distinguishing experiment, which is also interpretable.
- **Recipe.**
  1. Train an ensemble of 5 (phi, f, g) from any family.
  2. **Invariance counterexamples:**
     - take nearest-neighbour pairs in z;
     - search adversarially for x' = x + v, optimising v with CMA-ES or simulator gradients to maximise future-readout
       divergence minus λ||phi(x+v) − phi(x)||;
     - optionally optimise u as well, falsification-style.
  3. **Closure counterexamples:**
     - (x, u) where the rollout g(f^h(phi(x))) disagrees with the simulator by more than ε;
     - (x, u) where phi(x_{t+h}) disagrees with f^h(phi(x_t)) by more than ε;
     - (x, u) where the ensemble disagrees most (an expected-information-gain proxy).
  4. **Validate** each candidate by re-simulation with R = 20-50 noise seeds and an MMD permutation test, with
     multiple-testing control. For deterministic simulators, require stability to the integrator step.
  5. **Refine:**
     - add the distinguishing test to the bank;
     - add must-separate pairs (hinge max(0, m − ||phi(x) − phi(x')||)) and training data;
     - retrain from a warm start;
     - if the counterexamples cannot be separated at the current k without losing fit, set k ← k+1, initialising the
       new coordinate on the residual direction;
     - symmetric **merge** step: pull together pairs that are far apart in z but indistinguishable on all tests, and
       prune coordinates that are unused.
  6. **Stop** when a budget B (10³-10⁴ simulations; 10-20% of the total budget) finds no validated counterexample.
     Random tests give a PAC-style statement; adversarial search does not. Report both.
  7. **Abstention.**
     - Sweep ε and H_max and plot the required k(ε, H). A plateau gives k.
     - No plateau up to k_max, or failure of the Markov test at every k, gives **abstain**. Report the curve and the
       failing counterexamples.
     - Coarse-grained CSSR or L* state counts versus resolution serve as an independent abstention diagnostic.
- **Sweep.** ε, δ, H_max, test-bank families, Lipschitz bound, oracle budget, seeds.
- **Risks.**
  - No completeness or termination guarantees for continuous systems.
  - Oracle overfitting: use a *different* oracle and seed stream for evaluation than for training.
  - Active sampling oversamples far-from-attractor states, so report metrics per IC source.

### Tournament logistics
- Run each family through the same harness (II.2) and the same evaluation battery (II.5), with an identical simulation
  budget. F8 wraps F1, F5 and F7 in a second round.
- Minimum reporting per family:
  - for each k: the multi-horizon curves per held-out split, closure gap, equivalence gap, realiser spread, and
    stability across 5 seeds;
  - the chosen k with its selection rule;
  - the abstention decision on the control simulators.
- Rank families by a **property profile**, not a single score. The contract properties are not commensurable.

## II.4 Baselines and how to implement each well

Every baseline goes through the same interface (phi, f, g), the same k sweep and the same splits. Numbers are starting
points from the area notes; tune them on validation data only.

| # | Baseline | Implementation advice | Common mistakes | Packages (licence) |
|---|---|---|---|---|
| 1 | **PCA + linear dynamics** | Standardise units with training statistics only. PCA for k. Ridge-regress z_{t+1} = Az + Bu + c with CV ridge. Evaluate *free-run* multi-horizon, not one-step. Add a delay-PCA variant to separate variance from memory. | One-step evaluation only; PCA fitted on test data; ignoring the spectral radius | scikit-learn (BSD-3) |
| 2 | **Factor analysis (+ LDS)** | FA to initialise C and R, then LDS-EM with inputs, initialised from N4SID. Stop EM on held-out log-likelihood. Floor the Q and R eigenvalues (~1e-6·trace/k). Pair FA/GPFA (no transition law) with a fitted AR on the latents. | Random EM init (local optima); unstable A | dynamax (MIT), ssm (MIT), Elephant GPFA (BSD-3) |
| 3 | **DMD** | Centre the data. Choose rank by energy knee *and* held-out multi-step error. Report eigenvalues as log(λ)/dt. Use fbDMD/BOP-DMD if readouts are noisy (noise biases eigenvalues towards damping). | Interpreting damping from noisy data; rank by energy only | PyDMD (MIT) |
| 4 | **EDMD / Koopman** | PCA to 10-30 first. Dictionary [1, PCs, 50-500 k-means RBFs, optional quadratics], standardised. Ridge or truncated-SVD solve, with M/K ≥ 10-20. ResDMD residual filtering, and eigenvalue persistence as K and M grow. With inputs: EDMDc (Korda-Mezic). | Counting lifted dimension as k; spectral pollution | pykoopman (MIT), PyDMD (MIT), deeptime (LGPL-3.0) |
| 5 | **Hankel / delay methods** (Hankel DMD, HAVOK, ERA) | Delays d with d·dt of 1-2× the slowest relevant timescale, chosen on a validation curve. SVD rank r. Split by trajectory *before* building the Hankel. Causal (past-only) delays. HAVOK needs forcing, so it is not a closed model; use Hankel DMDc as the closed baseline. ERA from paired-difference impulse responses. | Overlapping windows leaking across the split; centred delays | pykoopman, PyDMD, python-control ERA (BSD-3) |
| 6 | **Linear SSM identification** (LDS-EM / PEM) | Initialise from subspace ID. Inputs via B u_t. Check the spectral radius. Select k by held-out likelihood *and* multi-step error. | EM from random init; overfitting noise covariances | dynamax (MIT), ssm (MIT) |
| 7 | **N4SID-style subspace ID** | CVA weighting. Pre-whiten; pre-project outputs to 100-200 PCs if m is large. Check persistency of excitation (rank and condition of the input block Hankel). Order from canonical correlations versus surrogates plus the CV plateau. Enforce stability. Use SSARX/PBSID variants if inputs are closed-loop. | Closed-loop bias; horizons too short for slow modes | nfoursid (MIT), SIPPY (LGPL-3.0), python-control/Slycot (BSD-3/GPLv2), MATLAB n4sid (commercial) |
| 8 | **SINDy / SINDYc** | On PCA or balanced coordinates, with standardised library columns, degree 2 first. Use exact simulator derivatives, or weak-form derivatives. Sweep the threshold on a log grid and pick the knee of held-out *simulation* error. E-SINDy (q = 100 bootstraps, inclusion 0.6) for uncertainty. Inputs open-loop. | Threshold chosen by fit, not rollout; feedback-correlated inputs (ill-conditioned) | PySINDy (MIT) |
| 9 | **Autoencoder + linear latent dynamics** | MLP encoder, z_{t+1} = Az + Bu with A initialised near identity and stably parameterised. MLP decoder to y and x. Multi-horizon loss. Locally-linear A(z) as a step up. | One-step training; unconstrained A diverging in rollouts | from scratch (PyTorch/JAX) |
| 10 | **Koopman autoencoder** | Pretrain the AE. Multi-step loss with a horizon curriculum from 5 to 50+. Latent consistency ||phi(x_{t+m}) − K^m phi(x_t)||. Stable K. Early stopping on held-out rollouts. ≥ 5 seeds; report the eigenvalues of K across seeds. Consistent-KAE only for invertible dynamics. | Treating eigenfunction sets as unique; seed variance | DLKoopman (MIT), DeepKoopman (MIT) |
| 11 | **Latent neural ODE** | Encoder phi(x(t0)) only, not an ODE-RNN over the window. Fixed-step RK4 at the model dt with direct backprop. Piecewise-constant u. Kinetic or Jacobian regularisation if NFE grows (unverified recipe). | Future-leaking window encoder; adjoint instability on dissipative latents | diffrax (Apache-2.0), torchdiffeq (MIT) |
| 12 | **Recurrent state-space model** | GRU h of 128-256, Gaussian s of dim k, actions = [u, intervention code], free bits of 1 nat, KL balance (V3: dynamics 1 / representation 0.1). **Report k_nominal = dim(s) and k_effective = dim(h) + dim(s).** Two evaluations: history burn-in (a history baseline) and closed start from phi(x(t0)). | Crediting RSSM with k = dim(s) | DreamerV3 (MIT) or own implementation |
| 13 | **Variational SSM** (DKF/DMM) | Pyro DMM structure, but with a *filtering or single-frame* encoder at evaluation, not the backward smoother. KL annealing over the first 10-20% of training; clamp log-variances. Use the transition-noise level as an abstention signal. | Evaluating with the smoother (future leakage); posterior collapse | Pyro (licence not verified), dynamax |
| 14 | **Predictive state representations** | Microstate version: F4 with a fixed probe bank and linear reduced-rank regression. History version: spectral TPSR with input-conditioned blocks and a ridge pseudoinverse. Choose k by held-out multi-step error, not a fixed SV threshold. Report the full spectrum. | Choosing the probe bank post hoc on test interventions | from scratch (numpy); no maintained package found |
| 15 | **Sequence model with bottleneck** | S5, LRU, GRU or transformer decoder that receives only (z = phi(x(t0)) ∈ R^k, u_{t0:t0+H}) and emits y. Same k sweep. Tests (1) and (5) only: the decoder carries state, so it is *not* a closure test. Pair with no-z (input-only) and history versions. | Reporting it as a closed-state model | S5, minimal-LRU (MIT), mamba (Apache-2.0) |
| 16 | **Random projection** | phi = random Gaussian N→k (rows orthonormalised) with f and g trained exactly as in F1. The null for "does learning phi matter?" and for every similarity measure. | Omitting it; it is often surprisingly strong for linear readouts | from scratch |
| 17 | **Input-only predictor** | f and g see only u (z fixed or learned constant). Measures input copying: the credit any model gets for input-locked responses. | Omitting it on strongly driven regimes | from scratch |
| 18 | **Readout-history-only predictor** | GRU or NARX (SysIdentPy FROLS with AIC/BIC) on past (y, u) windows of matched length. Bounds what a microstate encoder must beat. Also include "persist y". | Letting it use future u beyond the prediction step | SysIdentPy (BSD-3) |
| 19 | **Full-state predictor** | The same f class with phi = identity (or PCA at 95-99% variance) and ridge VAR / MLP. The ceiling for (1)-(3), and the reference for closure ratios. | Under-regularised at N = 5,000 (use PCA or ridge) | from scratch |

## II.5 Evaluation measures for properties (1)-(8)

General rules:
- Compute every measure on held-out splits (II.2), separately per split.
- Normalise against the baselines: full-state as ceiling; input-only, readout-history-only and persistence as floors.
- Compute measures only on gauge-invariant quantities: y, the model's own lift phi(Sim(...)) compared with f's
  prediction, or z after aligning within the transformation class the method claims, with the alignment fitted on
  training data.

| Property | Primary measures | Secondary / diagnostic |
|---|---|---|
| **(1) Predictive sufficiency** | Open-loop multi-horizon NLL/MSE of y at h ∈ {1,5,20,100}·dt plus multiples of the slowest time constant / Lyapunov time, as fractions of the gap between floor and full-state ceiling. Valid prediction time. | For chaotic or long horizons: D_stsp (state-space KL; GMM in higher dimensions), D_H (power-spectrum Hellinger), largest Lyapunov exponent, attractor count per draw (dysts `metrics.py`). InfoNCE estimate of I(z_t; y_{t:t+H}) versus I(x_t; y_{t:t+H}). |
| **(2) Markov closure** | **Closure gap**: error of the open-loop rollout f^h(phi(x_t)) versus the refreshed rollout f(phi(x_{t+h−1})). **Semigroup check** ||f^{a+b}(phi(x_t)) − f^b(phi(x_{t+a}))|| / spread(z). **History gain**: improvement when adding z_{t−1..t−p} or x_t to f; it should be ≈ 0 by a held-out test. | Chapman-Kolmogorov test (VAMP/MSM). Operator-inference re-projection gap. ResDMD residual of phi as a dictionary. Residual independence tests of z_{t+1} − f(z_t, u_t) against lagged z, y and random micro projections (PCMCI or partial correlation). ε-quasi-lumpability spread on discretised z. |
| **(3) Interventional sufficiency** | Held-out-target and held-out-type errors on post-intervention trajectories, as **effect-normalised error** err / D(y_intervened, y_unintervened) (no credit for predicting the unperturbed path). ≥ 30 interventions per family (Méloux et al.), preferably 100+ with bootstrap CIs. **Interchange error** (F5 recipe) with ≥ 3 realisers. | Match of directly measured probe quantities never used in training: vector phase response curves and isostable response curves (model perturbed through Jacobian(phi)), bifurcation diagrams under unseen constant inputs, and principal angles between phi's row space and the empirical-gramian balanced subspace. Structural interventions reported separately, and allowed to fall outside the declared intervention set. |
| **(4) Microstate invariance** | **Equivalence gap curve**: E[D(future | x), D(future | x')] over pairs with ||phi(x) − phi(x')|| < δ, as a function of δ, relative to random pairs. Pairs from (a) near neighbours in a large state bank, (b) null-space perturbations of phi, (c) adversarial search (F8, with a separate evaluation oracle). **Realiser spread** in interchange tests. **Null-space ratio**: effect of a null-space perturbation divided by the effect of an equal-norm range-space perturbation (should be ≈ 0). | Collapse check: states on the same isochron or spectral-submanifold fibre (same asymptotic future by construction) should map to nearby z. Directions with low empirical observability energy should lie in phi's null space. |
| **(5) Minimality** | The smallest k meeting pre-registered thresholds for (1)-(4), from the full k-curve with seed error bars, at a *declared* encoder Lipschitz or noise level. | Comparison with reference k from: HSV spectrum, Koopman/Floquet spectral gap, SSM dimension, test-matrix (Hankel) rank, DCA I_pred(d) plateau, kernel causal-state gap, PSID n1 versus nx. Effective rank and per-dimension variance of z (unused dimensions). Fisher-information rank of the fitted model. Intrinsic-dimension estimators (TwoNN, MLE) give only a *state-cloud* dimension: a lower-bound sanity check, not a closed-state dimension. |
| **(6) Stability** | Across ≥ 5 seeds, data subsets and estimators, *in the invariance class the method claims*: principal angles (linear phi); linear/affine cross-prediction R² (both directions); Procrustes/shape metric (netrep, cross-validated alignment); MCC for elementwise claims. Invariants of f: continuous-time eigenvalues (Hungarian-matched), fixed-point count and type, Jacobian spectra, Lyapunov exponents, D_stsp/D_H between rollouts. | Debiased CKA with shuffled and random-network nulls, as a secondary check. Report between/within ratios, not raw scores. |
| **(7) Shared across implementations** | **Held-out-implementation test**: freeze the shared f, fit only a new encoder on observational data, test on that implementation's interventions. **Cross-implementation interchange** with swap symmetry. **Cross-prediction of dynamics**: the map z_A → z_B conjugates f_A into a predictor of z_B's future. Comparison against per-implementation f: the gap is the cost of sharing. | Coordinate-free invariants compared across implementations: spectra, bifurcation diagrams, phase response curves, Lyapunov spectra, normal-form coefficients, fixed-point topology. InputDSA and Koopman-spectrum conjugacy tests as necessary-condition checks. Calibrate against a known different-f control. |
| **(8) Abstention** | Pre-registered rule, calibrated on control simulators (II.2): abstain if no k ≤ k_max meets the (1)-(4) thresholds, or if k(ε, H) grows without a plateau, or if the history gain in (2) stays significant at every k. Score abstention as a classifier on controls with known answers (ROC/AUC; false-abstain and false-accept rates). | No HSV, VAMP or canonical-correlation gap. No residual-certified spectrum. Learned transition noise not falling with k. Causal-state or automaton counts exploding with resolution. Predictive information growing with window length. High Kaplan-Yorke dimension. |

**Minimum dimension-cheating guard (applies to (5) and every k claim).**
- Report each k together with (i) the encoder and transition Lipschitz bounds or spectral norms, and (ii) a
  **noise-robustness curve**: prediction error when Gaussian noise of scale σ·sd(z) is added to z. It should degrade
  gracefully, not catastrophically.
- Check that linear-alignment scores are not far below nonlinear-alignment scores across seeds, because a large gap
  suggests a pathological encoding.

## II.6 Pitfalls and countermeasures

| Pitfall | How it arises | Countermeasure |
|---|---|---|
| **Time leakage** | Random splits over windows or lagged pairs from the same trajectory. Hankel matrices built before splitting. Absolute time or time-since-onset channels (e.g. neural CDE time channel). | Split by whole trajectory and parameter draw. Build delay matrices after splitting. Use time increments only; randomise window start times. |
| **Future leakage** | Bidirectional or smoothing encoders (DKF/SRNN smoothers, LFADS, NDT, GPFA smoothing, latent-ODE window encoders, natural cubic splines). Centred delays. Probe measurements on test draws used for model selection. Future inputs u_{k+1} in DMDc regressions. | Instantaneous or causal encoders only for evaluation. Probe data restricted to training draws for anything touching model selection. Audit every regression for the time index of its regressors. |
| **Output copying** | y in x or y-history fed to f or g; D-terms; one-step metrics. | Multi-horizon free-run evaluation. Readout-history and persistence baselines. Mask y in similarity computations. |
| **Input copying** | g(z, u) predicting input-locked responses; contrastive positives defined by equal u; inferred inputs absorbing dynamics; unconstrained B. | Input-only baseline and gain over it. Equal-u, different-x0 pairs. Held-out input families. Forbid u_t inside phi. |
| **Parameter-identity leakage** | Different parameter draws occupy separable regions of x; the encoder memorises the draw; episode-level negatives; IC or input statistics differing by draw. | Held-out draws for all evaluation. Probe decodability of the draw ID from z. Identical IC and input generators across draws. Equivalence pairs (4) from the same draw unless parameters are part of the state. |
| **Memorisation** | Kernel DMD and kernel PSRs act as lookups over training samples; deep encoders fit trajectory quirks. | New IC sources and basins at test. Frozen, unseen final test set. |
| **Dimension cheating** | Space-filling or high-Lipschitz phi; history channels not counted (RSSM h, VRNN feedback, CPC context, sequence decoders, KVAE mixture LSTM); lifted dictionary dimension reported as k; products of Koopman eigenfunctions counted as independent. | Count all carried state in k. Lipschitz or spectral-norm limits and noise injection. Noise-robustness curves. Count only truncated or independent coordinates. |
| **Collapse** | Self-prediction without decoder or anti-collapse term; KL posterior collapse. | Readout loss always on; variance floors; free bits; monitor effective rank. |
| **Oracle / evaluation overfitting** | The same counterexample generator used for training and evaluation. | A separate oracle, seed stream and budget for evaluation. |
| **Realiser artefacts** | Minimum-norm realisers pushing x off-manifold. | Report pool (on-manifold) realisers separately; Mahalanobis gate; count unrealisable z*. |
| **Perturbation-scale artefacts** | PRC and gramian estimates depend on ε. | Linearity checks (ε versus 2ε within 5%). Report scale. |
| **Invariant-metric gaming** | D_stsp satisfied with the wrong temporal order; metrics pooled across basins. | Pair with D_H and short-horizon error; compute metrics per basin. |
| **Similarity-measure artefacts** | CKA bias for p ≫ n and dominance of high-variance directions; CCA saturation at high k with autocorrelated samples; geometry-only measures blind to f; DSA's orthogonal alignment is neither necessary nor sufficient for conjugacy (Godara et al. 2026, per area F). | Battery of measures with calibrated nulls; held-out evaluation of alignment; always pair geometry with dynamics measures. |
| **Theory-assumption mismatch** | VAMP on deterministic dynamics; consistent KAE on dissipative dynamics; identifiability theorems assuming invertible mixing or independent innovations; PE theory for LTI only. | Treat theory-derived guarantees as hypotheses, and test them on control simulators. |
| **Closed-loop bias** | Inputs computed from outputs (feedback) in SID or SINDy. | Open-loop, persistently exciting inputs, or SSARX/PBSID. |
| **Licence traps** | Non-commercial or copyleft code: lfads-torch (non-commercial research), DBC (CC-BY-NC, archived), SSMLearn (AGPL-3.0), GTF-PLRNN (GPL-3.0), tigramite (GPL-3.0), PyPSID (custom research licence), CEBRA < 0.4.0 (non-commercial), Slycot (GPLv2). | Reimplement from papers where needed (most are simple or moderate), or confine them to evaluation-only scripts, subject to legal review. |

## II.7 Open problems where the literature gives no good answer

1. **Minimal-state estimation for nonlinear input-driven systems.** Existence and minimality theory exists (Nerode-type,
   rational/RNN realisation theory), but there is no practical, consistent estimator or order test from finite
   simulator data. Information criteria are meaningless for over-parameterised models, singular-value gaps vanish under
   nonlinearity, and cross-validation plateaus lack guarantees.
2. **Which test bank suffices.** Equivalence is relative to a set of probes. For continuous nonlinear systems there is no
   analogue of L*'s characterising suffix set, and no theory of when equivalence under training interventions implies
   equivalence under *unseen intervention types*.
3. **Structural interventions.** Unit and connection removal change the vector field. No reviewed method predicts them
   with a fixed low-dimensional f, except unit-space models (low-rank RNNs, Galerkin reductions) that keep micro
   parameters, and those assume low-rank micro structure. How to define the micro-to-macro intervention map ω for
   structural interventions is open.
4. **Identifiability of Markov latent dynamics from micro interventions with multi-node, graded, unknown macro targets.**
   BISCUIT (binary interactions), Buchholz et al. (linear Gaussian latent SCM) and von Kügelgen et al. (perfect
   interventions) each cover only part of this setting. No result covers continuous-time dynamics with feedback.
5. **One shared f across implementations.** Multi-view block identifiability covers shared *state content*, not shared
   *dynamics*. Classical similarity-class equivalence covers only linear I/O maps. There is no statistical test of
   "same f up to conjugacy" with calibrated nulls. DSA, CSA, DFORM and Koopman-spectrum tests disagree and lack null
   distributions.
6. **Calibrated abstention.** Predictive-information divergence and k-growth are asymptotic notions. No finite-data test
   separates "large but finite" from "non-compact" state, and no reviewed method outputs a calibrated "no compact state
   exists".
7. **Deterministic chaos.** Exact equivalence classes are singletons, and only (ε, H)-indexed notions make sense. How to
   choose ε and H jointly, and how to combine invariant-measure metrics (D_stsp, D_H) with interventional tests on
   *transients*, is unresolved. There is no accepted analogue of D_stsp for post-intervention transients.
8. **Global canonical coordinates.** Phase and isostables, spectral submanifolds and normal forms are local to one
   attractor. There is no global gauge-fixed latent coordinate system for multistable, input-driven or chaotic regimes,
   or for switches between attractors under interventions. A finite linear Koopman model cannot represent multiple
   isolated attractors at all.
9. **Experiment design for abstractions.** Fisher/BOED design targets parameters or graphs. There is no design theory
   for information about phi and the microstate equivalence classes; ensemble disagreement and invariance-violation
   search are ad hoc proxies. Persistency-of-excitation richness conditions exist only for LTI systems.
10. **Curved balanced reduction at scale.** Empirical gramians yield one global linear subspace. No standard method gives a
    nonlinear balanced manifold from simulation data at N ~ 10³-10⁴.
11. **Termination and completeness of counterexample-guided refinement** for continuous states and learned neural
    abstractions. Adversarial oracles give no PAC bound.
12. **Invariance class of "identifiable up to transformations".** The literature does not say which class (linear,
    affine, diffeomorphic, conjugacy of f) is appropriate. The similarity metric chosen implicitly decides it, so the
    project must pre-register the class per property.
13. **Dimension estimation of a *closed, interventionally sufficient* state**, as opposed to a state-cloud dimension. It
    is unreliable above ~20 dimensions and under noise. Linear estimators overestimate nonlinear dimension, and
    nonlinear estimators are fooled by pathological encodings.
