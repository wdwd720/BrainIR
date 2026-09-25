# BrainIR Phase 3 — Causal State-Variable Discovery and Cross-Brain Dynamical Abstraction

You are taking full scientific, mathematical, ML, computational-neuroscience, systems, statistical, and operational ownership of Phase 3 of BrainIR.

MAIN REPOSITORY
C:\Dev\BrainIR

PHASE 3 CLEAN DEVELOPMENT WORKSPACE
C:\Dev\BrainIR_p3clean

FROZEN PHASE 1 BENCHMARK
tag: dng100-benchmark-v1
commit: a7c0142

LOCKED PHASE 2 METHOD
BrainIR v1.2.0
tag: brainir-v1-preblind
commit: 959d689

CURRENT REPOSITORY HEAD REPORTED AT PHASE 2 COMPLETION
c8c935f

Phase 3 has NOT started.

======================================================================
0. THE SCIENTIFIC TRANSITION
======================================================================

Phase 2 answered:

    Which compact sets of neurons are causally sufficient/necessary
    for preserving the target computation?

Phase 2 also revealed a deeper problem:

    A neuron-level mechanism is not necessarily unique.

Different small neural implementations can preserve the same function.

Therefore Phase 3 must NOT continue treating:

    exact neuron identity

as the fundamental object we are trying to recover.

We now want to discover:

    what dynamical STATE is being represented and transformed by the circuit.

The Phase 3 scientific question is:

    Can BrainIR automatically discover the smallest low-dimensional
    causal state representation that explains the computation of a
    biological neural circuit, predicts unseen interventions, and
    remains equivalent across different valid neuron-level
    implementations and independently reconstructed connectomes?

Conceptually:

    microscopic neural state x(t)
              |
              v
        discovered abstraction
              |
              v
       z(t) in R^k, k << N
              |
              v
       compact dynamics
              |
              v
         future behavior

We want:

    x_t  --phi_d-->  z_t

and approximately:

    z_(t+dt) = f(z_t, u_t)

    y_t = g(z_t, u_t)

where:

    x_t = biological neural state
    z_t = discovered latent causal state
    u_t = externally supplied input/stimulus
    y_t = observed target/readout
    d   = connectome / physical implementation

The hard requirement is that z must not merely compress observations.

It must preserve causal and predictive behavior under interventions.

======================================================================
1. WHY THIS PHASE EXISTS
======================================================================

A normal dimensionality-reduction system can easily produce pretty latent
spaces that are scientifically meaningless.

PCA can find variance.

An autoencoder can reconstruct activity.

A neural network can predict output.

None of those alone establishes:

    "these are the state variables of the computation."

We require substantially stronger evidence.

A candidate latent state z must satisfy, as far as practical:

1. PREDICTIVE SUFFICIENCY

   Knowing z_t and future inputs should predict the relevant future
   computation nearly as well as knowing the full neural state x_t.

2. DYNAMICAL CLOSURE / APPROXIMATE MARKOV PROPERTY

   z_(t+1) should primarily depend on z_t and input u_t,
   not on discarded microscopic information.

3. INTERVENTIONAL SUFFICIENCY

   When the physical neural system is perturbed, the latent model should
   predict the downstream consequence.

4. MICROSTATE INVARIANCE

   Different microscopic neural states mapping to approximately the same
   z should have approximately the same future task-relevant behavior
   under the same future inputs.

5. COMPRESSION

   k should be substantially smaller than N.

6. STABILITY

   The discovered state should be reproducible across random seeds,
   reasonable model perturbations and estimation procedures.

7. CROSS-IMPLEMENTATION INVARIANCE

   Different valid neuron-level circuits implementing the same computation
   should map onto equivalent latent dynamics.

8. CROSS-CONNECTOME INVARIANCE

   Where function transfers between connectomes, a shared state-space
   model should explain both better than arbitrary unrelated representations.

9. INTERPRETABILITY WHERE SUPPORTED

   We should be able to characterize discovered variables after discovery,
   but semantic labels must NOT be hard-coded in advance.

We are trying to discover the VARIABLES before we write the PROGRAM.

======================================================================
2. DO NOT HARD-CODE THE EXPECTED VARIABLES
======================================================================

DO NOT assume the biological circuit has:

- exactly two latent variables
- "phase"
- "amplitude"
- "excitation"
- "inhibition"
- an oscillator coordinate system
- a particular feedback topology

Those are examples of possible interpretations.

They are NOT priors.

The method must be capable of discovering:

    k = 1, 2, 3, ...

based on evidence.

The system should be equally capable of discovering:

- an oscillator
- an integrator
- a switch
- a comparator
- gated memory
- a feed-forward transformation
- a multi-timescale controller
- a computation that cannot be compressed cleanly

If no compact causally sufficient representation exists under our model
class, BrainIR must be able to report that.

Do NOT force a nice story.

======================================================================
3. CRITICAL CLEAN-ROOM POLICY
======================================================================

This is substantially stricter than Phase 2.

PHASE2_REPORT.md IS ANSWER-BEARING.

It contains:

- hidden-evaluation results
- oracle comparisons
- information about which physical mechanisms succeeded
- structural scoring results
- cross-connectome hidden results

IT MUST NOT ENTER THE PHASE 3 CLEAN DEVELOPMENT ENVIRONMENT.

Do not copy it.

Do not summarize its hidden contents for method-development agents.

Do not paste sections into prompts sent to clean agents.

Do not allow method-development agents to search it.

Also exclude:

- Phase 2 hidden-evaluation directories
- hidden oracle
- oracle evaluation outputs
- answer-bearing review files
- hidden comparison tables
- Phase 1 oracle files
- private truth directories
- hidden benchmark results
- files whose purpose is to reveal which real neurons were correct

The main orchestrating Claude session has historical knowledge of Phase 2.

Therefore:

THE MAIN SESSION MUST NOT DESIGN THE PHASE 3 METHOD LOGIC.

Its responsibilities are:

- integrity checking
- clean-room creation
- allowlist enforcement
- generic infrastructure
- frozen evaluation harness
- experiment orchestration
- independent audits
- post-lock evaluation

Actual state-discovery method design should be performed by fresh,
oracle-free agents operating only inside:

    C:\Dev\BrainIR_p3clean

Whenever possible, enforce isolation technologically rather than only
through instructions.

Preferred options:

- explicit allowlist copy into clean directory
- containerized environment
- Modal container with only allowed files mounted
- process sandboxing
- read-deny hooks for parent repository
- path audit
- file-access audit

Do not rely solely on "please don't open this file."

======================================================================
4. WHAT MAY ENTER THE CLEAN ROOM
======================================================================

Build an explicit allowlist.

Permitted inputs should include only what is genuinely required.

Potentially allowed:

A. generic BrainIR library code required to load/simulate PUBLIC inputs

B. frozen public benchmark bundle

C. simulator API

D. generic mechanism-discovery API

E. LOCKED BrainIR v1.2 METHOD CODE if needed to GENERATE candidate mechanisms
   from public evidence

F. public Phase 2 method outputs that can be regenerated solely from:
       locked method
       +
       public benchmark
   without oracle information

G. generic dataset schema

H. generic cross-connectome public correspondence evidence permitted by
   the benchmark

I. generic synthetic state-discovery datasets specifically created for
   Phase 3

J. mathematical / ML dependencies

K. methods-only literature

Do NOT simply copy the entire repository.

Everything entering the clean room should have:

    path
    source
    reason
    hash
    leakage classification

Create:

    research/phase3/CLEANROOM_MANIFEST.json

and:

    research/phase3/LEAKAGE_POLICY.md

outside the clean room.

Create a clean-room builder:

    scripts/make_phase3_cleanroom.py

with:

    --build
    --check
    --destroy-and-rebuild

The checker should verify hashes and reject forbidden file classes.

======================================================================
5. IMPORTANT: REGENERATE PHASE 2 CANDIDATES CLEANLY
======================================================================

Do not tell Phase 3 developers:

    "These are the known valid alternative real circuits."

Instead, if Phase 3 needs compact mechanisms as inputs:

1. place the LOCKED BrainIR v1.2 code in the clean room;
2. provide the permitted public benchmark;
3. rerun the locked method there;
4. let it independently enumerate candidate mechanisms;
5. validate sufficiency using PUBLIC simulator behavior only;
6. retain its candidate/alternative outputs.

That way Phase 3 receives:

    public evidence
        ->
    locked Phase 2 discovery
        ->
    candidate physical implementations

rather than receiving answer-bearing Phase 2 report results.

These outputs are legitimate because they can be generated from public
inputs without the hidden oracle.

Hash them.

Store provenance.

======================================================================
6. BEFORE METHOD DEVELOPMENT: FREEZE THE PHASE 3 EVALUATION
======================================================================

We learned in Phase 2 that evaluation design itself can leak information.

Therefore Phase 3 should FIRST create and freeze an evaluation protocol.

This must happen BEFORE the clean state-discovery agents develop methods.

Create:

    benchmarks/state_discovery_v1/

with conceptually:

    public/
    hidden/
    evaluator/
    synthetic_public/
    synthetic_hidden/
    manifests/
    PROTOCOL.md
    BENCHMARK_LOCK.json

But only public pieces enter the clean room.

The Phase 3 evaluator should NOT contain neuron-identity ground truth as
its primary scoring target.

The key hidden evaluations should instead use FUTURE DATA unavailable
during training:

- held-out stimuli
- held-out initial states
- held-out parameter draws
- held-out low-level interventions
- held-out microstate perturbations
- held-out noise realizations
- held-out cross-implementation mappings where appropriate

This allows strong evaluation without needing a mythical "true latent
variable" for the real biological model.

======================================================================
7. PRE-REGISTER PHASE 3 SUCCESS CRITERIA
======================================================================

Before developing the method, define and lock what constitutes success.

Do not choose thresholds after seeing real results.

The evaluation should contain SEPARATE metrics.

Do not collapse everything into one number.

Metric families:

A. MULTI-STEP PREDICTIVE SUFFICIENCY

B. READOUT SUFFICIENCY

C. INTERVENTIONAL FIDELITY

D. APPROXIMATE MARKOV CLOSURE

E. MICROSTATE EQUIVALENCE / BISIMULATION-LIKE ERROR

F. LATENT DIMENSION / COMPRESSION

G. REPRODUCIBILITY

H. ROBUSTNESS TO PARAMETER UNCERTAINTY

I. CROSS-MECHANISM INVARIANCE

J. CROSS-CONNECTOME DYNAMICAL INVARIANCE

K. SYNTHETIC GROUND-TRUTH RECOVERY

L. FAILURE / ABSTENTION QUALITY

Pre-register:

- metric definitions
- confidence intervals
- multiplicity policy where needed
- model selection criteria
- latent-dimension selection protocol
- allowed hyperparameter search
- hidden evaluation count
- model-lock requirements

Do not choose expected performance values arbitrarily.

Use baseline distributions and synthetic calibration.

======================================================================
8. DEFINE THE STATE-DISCOVERY PROBLEM MATHEMATICALLY
======================================================================

Let a physical circuit d have neural state:

    x_t^(d) in R^(N_d)

and external input:

    u_t

and readout:

    y_t

We seek an encoder:

    phi_d : x_t^(d) -> z_t

where:

    z_t in R^k

and a shared or partially shared transition model:

    z_(t+1) = f(z_t, u_t) + epsilon_t

and output model:

    y_t = g(z_t, u_t) + eta_t

Potential decoder:

    x_hat_t = psi_d(z_t)

but high-quality reconstruction of x is SECONDARY.

The primary objective is task-relevant causal state.

A generic objective may contain:

    L =
        lambda_pred * L_multistep
      + lambda_readout * L_readout
      + lambda_interv * L_interventional
      + lambda_markov * L_markov
      + lambda_micro * L_microstate_equiv
      + lambda_cross * L_cross_impl
      + lambda_complex * C(z, f)
      + lambda_robust * L_robust

Do NOT implement this exact formula blindly.

Research and derive the objective.

Keep every component separately measurable.

======================================================================
9. PREDICTIVE SUFFICIENCY
======================================================================

A representation z_t is useful if future relevant behavior can be predicted
from it.

Evaluate:

    p(y_(t+1:t+H) | z_t, u_(t:t+H))

against:

    p(y_(t+1:t+H) | x_t, u_(t:t+H))

The full-state model establishes an empirical upper bound.

Compare against:

- input-only predictor
- readout-history-only predictor
- PCA state
- random projection
- full neural state
- candidate latent state

Measure multiple horizons.

Do not let the latent encoder see future activity.

No future leakage.

======================================================================
10. MARKOV CLOSURE
======================================================================

If z is truly a state variable, discarded microscopic information should
add little task-relevant predictive value.

Test:

    z_(t+1) ~ f(z_t, u_t)

and compare against:

    z_(t+1) ~ f(z_t, x_t, u_t)

If adding discarded microscopic state substantially improves prediction,
z is not dynamically closed.

Possible empirical closure score:

    Delta_markov =
        error(z-only)
        -
        error(z + residual microstate)

Smaller is better.

Also test history dependence:

    p(z_(t+1) | z_t, u_t)

versus:

    p(z_(t+1) | z_(t-L:t), u_(t-L:t))

If long history is required, the current latent may not contain enough
state.

Do not hide this by using a huge recurrent decoder.

======================================================================
11. CAUSAL STATE: INTERVENTIONAL FIDELITY
======================================================================

This is the central scientific requirement.

Observational latent spaces are insufficient.

Collect trajectories under:

- no intervention
- single-neuron silencing
- grouped silencing
- activation where supported
- edge perturbations where supported
- parameter perturbations
- state initialization changes
- input changes

Fit on a subset.

Hold out intervention families.

Evaluate whether the latent model predicts:

    effect of intervention
        ->
    latent trajectory
        ->
    output trajectory

Interventional prediction should be evaluated separately from ordinary
forecasting.

======================================================================
12. MICROSTATE EQUIVALENCE TEST
======================================================================

This may be one of Phase 3's deepest tests.

If two microscopic neural states:

    x_a
    x_b

map to nearly the same latent state:

    phi(x_a) ~= phi(x_b)

then under the same future input they should have similar task-relevant
future behavior.

Define neighborhoods in latent space.

For matched pairs with:

    ||z_a - z_b|| <= delta

measure future divergence:

    D_future(x_a, x_b)

over a horizon H.

A good latent representation should make:

    E[D_future | close latent states]

small.

Compare to:

- random states
- PCA-matched states
- output-only matched states
- random projections

This approximates a behavioral / bisimulation-style equivalence test.

======================================================================
13. CAUSAL LATENT INTERVENTIONS
======================================================================

A latent variable becomes much more convincing if we can perturb it.

But z is not a physical neuron.

Therefore construct an intervention-lifting problem.

Given desired latent perturbation:

    delta_z

find a low-level intervention:

    delta_x*

such that:

    phi(x + delta_x*) ~= z + delta_z

while minimizing intervention cost:

    min_delta_x
        ||phi(x + delta_x) - (z + delta_z)||^2
        +
        lambda * Cost(delta_x)

subject to allowed physical/simulator intervention classes.

Possible allowed low-level perturbations:

- activation
- inhibition
- state initialization
- grouped perturbations
- limited node-state offsets

Use only simulator operations that are scientifically meaningful.

Then compare:

    latent model prediction after do(z := z + delta_z)

against:

    low-level simulator after lifted intervention.

This is a major test of causal abstraction.

======================================================================
14. MULTIPLE MICRO-IMPLEMENTATIONS OF THE SAME LATENT INTERVENTION
======================================================================

Do not rely on one low-level intervention.

For the same target delta_z, find several distinct microscopic interventions:

    delta_x_1
    delta_x_2
    delta_x_3

that produce approximately the same immediate latent shift.

If z is a meaningful causal state, their subsequent task-relevant dynamics
should converge to similar trajectories.

This is stronger than ordinary prediction.

It asks:

    Does the future depend on the abstract state,
    or on hidden microscopic details?

Quantify residual dependence.

======================================================================
15. MINIMAL LATENT DIMENSION
======================================================================

Do not set k manually based on expected biology.

Search:

    k = 1, 2, 3, 4, ...

until additional dimensions produce diminishing returns.

Build a Pareto curve:

    dimension
      vs
    predictive fidelity
      vs
    interventional fidelity
      vs
    closure
      vs
    robustness

Prefer the SMALLEST k satisfying pre-registered fidelity requirements.

Where useful compare:

- cross-validation
- information criteria
- MDL
- held-out likelihood
- prediction plateau
- intervention plateau

If there is no sharp minimal dimension, report an uncertainty range.

======================================================================
16. COORDINATE NON-IDENTIFIABILITY
======================================================================

Latent coordinates are not unique.

If:

    z' = A z

for invertible A,

two methods may encode the same state in different coordinates.

Do NOT compare latent coordinates element-wise before alignment.

Use appropriate equivalence measures such as:

- canonical correlation
- Procrustes alignment
- principal angles
- subspace similarity
- CKA where justified
- predictive equivalence
- intervention equivalence
- dynamical conjugacy approximations

For nonlinear coordinate transforms, use stronger behavioral tests.

Our scientific claim should be about STATE EQUIVALENCE, not arbitrary axis
names.

======================================================================
17. CROSS-MECHANISM INVARIANCE
======================================================================

Use the locked Phase 2 method to generate alternative candidate physical
mechanisms from public data.

For mechanism m in network d:

    x_t^(d,m)

learn:

    phi_(d,m)(x) -> z

and test whether several physical mechanisms can share:

    SAME transition law f

or an equivalent f under a coordinate transformation.

Test:

    independent latent dynamics
        vs
    shared latent dynamics

If a shared model performs equally well or better on held-out trajectories
and interventions using fewer parameters, that is evidence that the
different neuron sets instantiate the same computation.

Do not force sharing if evidence rejects it.

======================================================================
18. CROSS-CONNECTOME INVARIANCE
======================================================================

This is a major BrainIR objective.

Different connectomes may use different neurons but implement the same
abstract dynamics.

Try:

    phi_A(x_A) -> z
    phi_B(x_B) -> z

with:

    shared f(z,u)

and dataset-specific encoders / optional decoders.

Compare:

MODEL 1:
    completely independent dynamics f_A, f_B

MODEL 2:
    shared latent dimension but independent dynamics

MODEL 3:
    shared dynamics with dataset-specific encoders

MODEL 4:
    partially shared dynamics

Evaluate on held-out trajectories/interventions.

A shared model wins only if:

- predictive quality is maintained;
- intervention fidelity is maintained;
- complexity is reduced;
- transfer improves;
- it does not rely on identity leakage.

======================================================================
19. LEAVE-ONE-IMPLEMENTATION-OUT TESTING
======================================================================

Where enough physical variants exist:

Train the shared latent transition law on some implementations.

Fit only the encoder for a held-out implementation.

Then test hidden interventions.

If this works with little adaptation, it is strong evidence that the
state-space dynamics are reusable.

Track separately:

- encoder adaptation cost
- transition-model adaptation cost

The strongest result is:

    new physical circuit
      ->
    learn mapping into existing latent dynamics
      ->
    predict function

without relearning the dynamics.

======================================================================
20. SYNTHETIC STATE-DISCOVERY BENCHMARK
======================================================================

Before using the real circuit, build a NEW Phase 3 synthetic benchmark.

Do not reuse hidden Phase 2 truths as the primary development benchmark.

Have fresh oracle-free developers create generic generators.

The orchestrator may define interfaces but should not encode a DNg100-like
answer.

Include systems with KNOWN hidden state variables:

1. linear stable state-space systems
2. harmonic oscillator
3. nonlinear oscillator
4. damped oscillator
5. limit-cycle oscillator
6. bistable switch
7. leaky integrator
8. perfect integrator
9. gated integrator
10. winner-take-all
11. negative feedback controller
12. coupled slow/fast dynamics
13. latent state with irrelevant nuisance neurons
14. redundant microscopic realization
15. multiple physical implementations sharing one latent dynamic
16. non-Markov projection trap
17. output-only shortcut trap
18. time-index shortcut trap
19. hidden exogenous-variable trap
20. genuinely high-dimensional system with no small valid abstraction

Observation maps should vary.

Examples:

    x = h_d(z) + nuisance

where h_d can be:

- random linear embedding
- sparse population embedding
- redundant copies
- nonlinear saturation
- mixed signs
- noisy observations
- partial observation

The method must recover the state despite different microscopic encodings.

======================================================================
21. SYNTHETIC CAUSAL INTERVENTIONS
======================================================================

Synthetic ground truth must support interventions.

Examples:

    do(z_i = value)
    impulse(z_i)
    low-level neuron perturbation
    group perturbation

Generate mappings from latent interventions to microscopic interventions.

This allows objective evaluation of whether learned latent variables
recover causal structure.

Metrics should include:

- latent subspace recovery
- dimension recovery
- dynamics recovery
- intervention prediction
- microstate equivalence
- cross-realization invariance

Ground truth stays outside the development clean room.

======================================================================
22. ADVERSARIAL SYNTHETIC TRAPS
======================================================================

Create traps specifically capable of fooling ordinary representation
learning.

Examples:

A. HIGH-VARIANCE NUISANCE

A nuisance process explains most variance but does not cause output.

B. READOUT COPY

One neuron simply mirrors the output.

C. CLOCK NEURON

A neuron tracks time and predicts periodic output without participating
causally.

D. INPUT COPY

A neuron mirrors the stimulus.

E. REDUNDANT MICROSTATES

Many distinct neural realizations correspond to one causal state.

F. HYSTERESIS

Same instantaneous output but different hidden state predicts different
future trajectories.

G. NON-MARKOV COMPRESSION

A one-dimensional embedding predicts one step well but fails long-horizon.

H. PARAMETER-CONFOUNDED LATENT

A representation predicts because it encodes a parameter draw rather than
system state.

I. MULTIPLE LIMIT CYCLES

Phase alone is insufficient; cycle identity matters.

J. TRANSIENT VS LIMIT CYCLE

Amplitude/energy is required in addition to phase.

K. BIFURCATION

The effective latent dimension changes by input regime.

L. DISTRIBUTED COMPUTATION

No sparse neuron subset directly corresponds to the latent variable.

BrainIR should either handle these or correctly abstain.

======================================================================
23. BASELINES — SERIOUS ONES
======================================================================

Do not compare only to PCA.

Implement strong baselines appropriate for system identification.

Research current implementations and literature.

At minimum investigate:

1. PCA + linear dynamics
2. factor analysis
3. DMD
4. extended DMD / Koopman features
5. delay-coordinate / Hankel methods
6. linear state-space identification
7. subspace identification / N4SID-style methods
8. SINDy / sparse nonlinear dynamics
9. autoencoder + latent linear dynamics
10. Koopman autoencoder
11. latent neural ODE
12. recurrent state-space model
13. variational state-space model where justified
14. predictive-state representation
15. generic sequence model with bottleneck
16. random projection control
17. input-only predictor
18. readout-history predictor
19. full-state predictor upper bound

Do not implement every technique poorly.

Research and select strong, appropriate implementations.

======================================================================
24. METHODS LITERATURE REVIEW
======================================================================

Conduct a fresh Phase 3 methods-only literature review.

Do not search DNg100 answers.

Research:

- nonlinear system identification
- minimal state realization
- predictive state representations
- causal states / computational mechanics
- balanced realization / model reduction
- Koopman operator learning
- dynamic mode decomposition
- SINDy
- neural state-space models
- latent ODEs
- intervention-aware representation learning
- causal representation learning
- bisimulation metrics / state abstractions
- invariant causal representation
- nonlinear ICA where relevant
- system identification under interventions
- experiment design for latent dynamics
- observability
- controllability
- canonical dynamical coordinates
- phase reduction
- limit-cycle identification
- neural population dynamics
- dynamical-systems approaches to neuroscience

For every candidate method record:

    assumptions
    identifiability
    intervention support
    nonlinear capacity
    interpretability
    scaling
    failure modes
    relevance to our problem

Do not select a method because it sounds modern.

======================================================================
25. OBSERVABILITY ANALYSIS
======================================================================

Before trying to discover latent variables, ask whether the state is even
observable from available neural measurements.

For candidate mechanisms compute appropriate observability diagnostics.

For linear approximations:

    observability rank / Gramian where meaningful.

For nonlinear systems:

- empirical observability
- local sensitivity
- delay embedding tests
- intervention response diversity

If the target state is not identifiable from the permitted observations,
document that.

Do not make impossible claims.

======================================================================
26. CONTROLLABILITY / INTERVENTION ACCESS
======================================================================

Similarly ask:

    Can we perturb enough independent directions to test the latent state?

Compute empirical intervention reachability.

If all permitted interventions change only one latent direction, we cannot
validate a multi-dimensional causal state robustly.

Record intervention coverage.

This matters when interpreting negative results.

======================================================================
27. DATA GENERATION FOR REAL CIRCUITS
======================================================================

Generate a rich trajectory dataset from PUBLIC simulator access.

Do not just use one periodic trajectory.

Sample:

- multiple initial conditions
- input strengths
- input timing
- parameter draws
- transient perturbations
- single-neuron interventions
- grouped interventions
- pulse perturbations
- temporary perturbations
- edge perturbations where allowed
- state perturbations where simulator supports them

Goal:

    excite the system enough to identify dynamics.

This is system identification, not movie compression.

Design input/perturbation protocols to cover state space.

Use optimal/active experimental design if useful.

======================================================================
28. ACTIVE EXPERIMENT DESIGN FOR STATE IDENTIFICATION
======================================================================

We have a simulator oracle.

Use it intelligently.

Rather than randomly collecting trajectories, identify experiments that
maximize information about candidate latent models.

For two models f1 and f2, search for:

    intervention/input I*

maximizing predicted disagreement.

Potential objective:

    I* = argmax_I D(
        p_f1(y_future | do(I)),
        p_f2(y_future | do(I))
    )

or posterior expected information gain.

This begins the foundation for later automated neuroscience.

Track simulator budget.

======================================================================
29. DO NOT TRAIN ON THE HIDDEN REAL TEST DISTRIBUTION
======================================================================

Split real experiments into:

PUBLIC TRAIN:
    development-visible

PUBLIC VALIDATION:
    tuning-visible if protocol permits

HIDDEN TEST:
    generated from secret seeds / protocols after method lock

Hidden test should differ in:

- perturbation identity
- input sequences
- parameter draws
- initial states

where scientifically meaningful.

Lock the generator before development.

Do not repeatedly inspect hidden results.

======================================================================
30. CANDIDATE PHASE 3 ALGORITHM FAMILIES
======================================================================

Do NOT decide the final algorithm in advance.

Run a method tournament.

Serious candidate families might include:

A. LINEAR SUBSPACE / BALANCED MODEL REDUCTION

Strong baseline and perhaps sufficient.

B. SPARSE NONLINEAR STATE IDENTIFICATION

Encoder + SINDy-like latent dynamics.

C. KOOPMAN-STYLE REPRESENTATION

Learn coordinates in which dynamics are approximately linear.

D. PREDICTIVE BOTTLENECK

Learn z minimizing dimension while retaining future-predictive information.

E. INTERVENTION-AWARE CAUSAL BOTTLENECK

Predict future plus intervention outcomes, with explicit latent closure.

F. LATENT NEURAL STATE-SPACE MODEL

Flexible nonlinear transition with strict bottleneck.

G. SHARED CROSS-IMPLEMENTATION STATE MODEL

Implementation-specific encoders + shared dynamics.

H. HYBRID METHOD

Possibly:
    linear/system-ID initialization
      +
    nonlinear encoder refinement
      +
    intervention loss
      +
    cross-implementation sharing
      +
    sparse dynamics extraction

But DO NOT assume the hybrid wins.

======================================================================
31. PREFERRED SCIENTIFIC DIRECTION TO INVESTIGATE
======================================================================

A particularly promising formulation is an
INTERVENTIONAL PREDICTIVE STATE representation.

The latent should be optimized not to reconstruct microscopic neurons, but
to predict:

    future target behavior
    +
    future latent evolution
    +
    consequences of interventions

while being minimal.

Conceptually:

    z_t = phi(x_t)

Train phi, f and g to minimize:

    multi-step future error
    +
    intervention effect error
    +
    latent closure error
    +
    cross-implementation discrepancy
    +
    complexity penalty

This may be more scientifically aligned than a standard autoencoder.

But evaluate it empirically against simpler methods.

======================================================================
32. PREVENT TRIVIAL SHORTCUTS
======================================================================

Explicitly test and block these failure modes:

A. TIME LEAKAGE

Latent encodes timestep on periodic trajectories.

Counter:
    randomize phase/start time;
    variable stimuli;
    transient perturbations.

B. OUTPUT LEAKAGE

Latent is just y_t.

Counter:
    exclude readout from encoder;
    test states with equal current y but different futures.

C. INPUT LEAKAGE

Latent is just stimulus history.

Counter:
    compare against input-only baseline;
    perturb internal state while holding input fixed.

D. FUTURE LEAKAGE

Encoder accidentally sees future samples.

Strictly audit train pipelines.

E. PARAMETER-ID LEAKAGE

Latent identifies parameter draw rather than dynamic state.

Test cross-parameter generalization.

F. MICROSCOPIC MEMORIZATION

High-capacity encoder memorizes neuron identities.

Test cross-implementation transfer.

G. DIMENSION CHEATING

One scalar stores arbitrary high-dimensional information using
pathological numerical coding.

Use smoothness/noise constraints and realistic finite precision.

======================================================================
33. TEMPORAL RESOLUTION
======================================================================

State dimensionality can depend on sampling interval.

Investigate several dt values if computationally practical.

A hidden fast variable may disappear at coarse sampling.

Evaluate whether discovered state is stable across reasonable temporal
resolutions.

Do not overclaim a universal state representation from one arbitrary dt.

======================================================================
34. MULTI-TIMESCALE DYNAMICS
======================================================================

Allow possibility of:

    fast state
    slow state

Use diagnostics:

- autocorrelation
- Jacobian eigenvalues
- spectral decomposition
- timescale separation

Do not force every state variable to operate at the same timescale.

If a slow parameter behaves more like context than dynamic state, represent
that distinction.

======================================================================
35. DISCRETE + CONTINUOUS STATE
======================================================================

A circuit may contain both:

    continuous dynamics
    +
    discrete modes

For example:

    mode q_t
    continuous z_t

Consider hybrid state-space models if evidence supports them.

Do not add discrete states by default.

Model selection must justify complexity.

======================================================================
36. LATENT DYNAMICS CHARACTERIZATION
======================================================================

After discovery, characterize the dynamics WITHOUT prematurely naming them.

For a low-dimensional latent system evaluate:

- fixed points
- limit cycles
- nullclines where feasible
- Jacobian
- eigenvalues
- stability
- phase portrait
- attractors
- basins
- frequency response
- impulse response
- perturbation recovery
- Lyapunov behavior where meaningful

If a variable behaves like a phase coordinate, derive that AFTER discovery.

If amplitude/radius is relevant, derive it AFTER discovery.

Semantic interpretation follows dynamics.

======================================================================
37. PHASE RESPONSE / PERTURBATION RESPONSE IF OSCILLATORY
======================================================================

ONLY IF the discovered dynamics exhibit a stable limit cycle:

Estimate a phase response curve.

Perturb at different locations along the cycle.

Measure:

    phase shift
    amplitude recovery
    output shift

Then compare PRCs across:

- alternative physical mechanisms
- connectomes
- latent model

A shared PRC would be powerful evidence of shared computation.

Do not assume oscillatory dynamics beforehand.

======================================================================
38. SHARED DYNAMICS VS SHARED TRAJECTORY
======================================================================

Two systems traversing similar trajectories does NOT necessarily mean they
implement the same dynamics.

Compare vector fields.

For aligned latent points z:

    f_A(z,u)
    versus
    f_B(z,u)

Measure vector-field discrepancy.

Also compare:

- fixed points
- eigenstructure
- attractors
- perturbation responses

Cross-brain equivalence should be dynamical, not merely visual.

======================================================================
39. APPROXIMATE DYNAMICAL CONJUGACY
======================================================================

Where coordinate systems differ, investigate whether there exists mapping h:

    h(F_A(z))
        ~=
    F_B(h(z))

This is a stronger statement than correlated trajectories.

For practical purposes learn h on one subset and test on held-out
trajectories/interventions.

Measure conjugacy error.

Do not claim formal conjugacy unless actually established.

======================================================================
40. CROSS-REALIZATION TEST USING SYNTHETICS
======================================================================

Generate multiple microscopic networks from one hidden source dynamic.

Example:

    hidden z-system
        ->
    neural implementation A
    neural implementation B
    neural implementation C

They should differ by:

- neuron count
- connectivity
- observation mixing
- redundancy
- nuisance dynamics
- permutation

Then test whether BrainIR discovers:

    one common latent dynamics model

with different encoders.

This is the cleanest objective test of BrainIR's core hypothesis.

======================================================================
41. MODEL COMPLEXITY
======================================================================

Track complexity explicitly.

For state model:

    latent dimension k
    transition parameter count
    encoder complexity
    decoder complexity if used

A 2D latent with a 50-million-parameter transition network is not a compact
mechanistic explanation.

Prefer simple transition laws where performance permits.

However:

Do not force sparse polynomials if biology requires nonlinear functions.

======================================================================
42. DISTINGUISH REPRESENTATION FROM DYNAMICS
======================================================================

Evaluate separately:

ENCODER QUALITY:
    Can physical state map into abstract state?

DYNAMICS QUALITY:
    Can abstract state evolve correctly?

READOUT QUALITY:
    Does abstract state determine relevant output?

INTERVENTION QUALITY:
    Does abstract state preserve intervention effects?

This helps diagnose failures.

======================================================================
43. UNCERTAINTY
======================================================================

We need uncertainty over:

- latent dimension
- encoder
- transition dynamics
- intervention predictions
- cross-brain equivalence

Use ensembles / posterior approximations / bootstrap where useful.

If two different latent models are equally supported, preserve both.

Do not choose one because its visualization looks nicer.

======================================================================
44. STATE VARIABLE STABILITY ACROSS TRAINING RUNS
======================================================================

For repeated runs:

- align latent spaces appropriately;
- measure subspace similarity;
- compare dynamics after alignment;
- compare intervention predictions.

We care more about:

    same causal state

than exact neural-network parameter equality.

Build confidence intervals.

======================================================================
45. NEURON-TO-STATE MAPPING
======================================================================

For every discovered latent dimension or subspace, identify how it is
implemented physically.

This can be:

    z_k = phi_k(x)

Measure contribution/sensitivity using methods appropriate to the encoder:

- linear loading
- Jacobian sensitivity
- integrated gradients if justified
- intervention effect
- sparse probe
- ablation

Do not overinterpret a raw neural-network attribution map.

Prefer causal validation.

Output may show:

    state variable z1
        supported by neurons {...}
        contribution distribution
        uncertainty

Different mechanisms/connectomes may map different neurons onto the same z.

That is exactly what we want to test.

======================================================================
46. NO SEMANTIC LABELS DURING TRAINING
======================================================================

Do not train with labels like:

    "phase"
    "amplitude"
    "feedback inhibition"

unless they are part of a synthetic ground-truth evaluation isolated from
method training.

For real biological discovery, label latents initially:

    z0
    z1
    z2

Only after causal/dynamical validation may a post-hoc interpreter say:

    z0 appears phase-like

and provide evidence.

======================================================================
47. PHASE 3 OUTPUT SCHEMA
======================================================================

Create a versioned structured result such as:

    BrainIRStateModel

Potential fields:

- method_version
- source dataset
- source mechanism ID
- latent_dimension
- encoder specification/hash
- transition model specification/hash
- readout model
- valid input domain
- training intervention classes
- held-out intervention classes
- predictive metrics
- intervention metrics
- closure metrics
- compression metrics
- robustness metrics
- latent uncertainty
- physical-to-latent mapping
- cross-mechanism equivalence
- cross-connectome equivalence
- failure cases
- abstention flags
- provenance

Do not make English text the primary output.

======================================================================
48. STATE MODEL SERIALIZATION
======================================================================

The learned state model should be executable.

Given:

    x_t
    u_t

it should produce:

    z_t

Then:

    z_t, u_future

should generate predicted future state/readout.

Save enough metadata to reproduce inference exactly.

Use stable versioning.

======================================================================
49. BASELINE FULL-STATE MODEL
======================================================================

Train a strong full-state predictor.

Purpose:

Establish how much predictive information is available at all.

If full state cannot predict a hidden intervention, a 2D model cannot be
expected to.

Compare latent performance relative to this empirical ceiling.

Do not punish compression for irreducible simulator uncertainty.

======================================================================
50. BASELINE READOUT-ONLY / INPUT-ONLY MODELS
======================================================================

These are critical shortcut controls.

If:

    stimulus history
        ->
    future output

already works perfectly, latent neural state may not be needed.

If:

    current readout history
        ->
    future output

works perfectly, state discovery may be trivial.

Quantify incremental value of neural latent state.

======================================================================
51. HELD-OUT INTERVENTION GENERALIZATION
======================================================================

Do not merely hold out trajectories from the same intervention.

Hold out intervention TYPES where practical.

Example:

Train:
    individual silencing
    input perturbations

Test:
    paired/group silencing
    pulse activation

or another pre-registered split.

This assesses whether the latent model captures mechanism rather than
memorizing intervention IDs.

======================================================================
52. COUNTERFACTUAL TESTS
======================================================================

Given observed state x_t and intervention I:

Predict:

    y_future if I were applied

Then compare with simulator.

Counterfactual error should be a first-class metric.

This will later support BrainIR's "what happens if..." interface.

======================================================================
53. COUNTEREXAMPLE GENERATION
======================================================================

For candidate state model S, search for:

    x, u, I

maximizing:

    disagreement(
        biological simulator,
        state model
    )

Use:

- gradient optimization where available
- evolutionary search
- Bayesian optimization
- randomized search
- structured intervention search

Counterexamples are not failures to hide.

They identify missing state.

Feed PUBLIC counterexamples back during development.

Keep HIDDEN counterexamples for evaluation.

======================================================================
54. CEGAR-LIKE LOOP — BUT ONLY FOR STATE DISCOVERY
======================================================================

Implement conceptually:

    candidate latent model
          |
          v
    adversarial verification
          |
     counterexample?
       /       \
     no         yes
     |           |
     |      add experiment
     |           |
     +------ refine model
                 |
                 loop

Do NOT build the later formal SMT verifier yet.

This is simulation/adversarial refinement.

======================================================================
55. DO NOT START SYMBOLIC PROGRAM SYNTHESIS
======================================================================

Very important.

Phase 3 stops after discovering validated state variables / state dynamics.

Do NOT yet create the final BrainIR DSL.

Do NOT yet turn f into human-readable source code as the main goal.

Do NOT yet build formal theorem proving.

Do NOT yet build an LLM explanation system.

Those come after we know WHAT VARIABLES the symbolic program needs.

======================================================================
56. METHOD SELECTION PROCEDURE
======================================================================

Use THREE levels.

LEVEL A — synthetic training/development

Method designers can inspect public synthetic training performance.

LEVEL B — synthetic held-out confirmation

Used only after candidate selection.

LEVEL C — real hidden intervention test

Run only after method lock.

Do not repeatedly optimize against Level C.

======================================================================
57. METHOD LOCK
======================================================================

Before real hidden evaluation:

Freeze:

- source code
- model architecture
- latent-dimension rule
- objective
- hyperparameters
- training budget
- simulator budget
- intervention training split
- evaluation script
- seeds / seed policy
- dependency versions

Create:

    research/phase3/METHOD_LOCK.json

Tag:

    brainir-state-v1-preblind

or an appropriate equivalent.

After hidden evaluation, any methodological change becomes v2.

======================================================================
58. COMPUTE POLICY
======================================================================

The project estimate suggests several hundred dollars of Modal credits
remain.

Verify actual available compute information if accessible.

Use compute aggressively when it saves wall-clock time.

Parallelize:

- synthetic systems
- algorithm tournament
- seeds
- latent dimensions
- hyperparameter sweeps
- interventions
- counterexample search
- cross-connectome experiments
- bootstraps

Do not burn budget blindly.

Use successive halving / early stopping:

1. tiny pilot
2. kill bad methods
3. medium evaluation
4. scale finalists

Cache generated simulator trajectories aggressively.

State-variable models should train on reusable rollout datasets whenever
scientifically permissible.

Simulator data generation and representation learning are different cost
centers. Track both.

======================================================================
59. COST ACCOUNTING
======================================================================

Record:

- simulator calls
- simulated biological seconds
- CPU hours
- GPU hours
- Modal job IDs
- wall-clock time
- approximate dollars
- training samples
- optimization steps

A method that needs vastly more compute for tiny gains should be reported
honestly.

======================================================================
60. BUILD A TRAJECTORY STORE
======================================================================

Phase 3 will generate many trajectories.

Create a content-addressed trajectory store keyed by:

- dataset manifest hash
- physical mechanism hash
- simulator version
- parameters
- initial state
- stimulus
- intervention
- seed
- dt

Do not regenerate identical trajectories.

Use chunked storage suited to time series:

- Zarr
- HDF5
- Arrow/Parquet when appropriate

Choose based on profiling.

Keep metadata queryable.

======================================================================
61. PERFORMANCE ENGINEERING
======================================================================

Do not optimize prematurely.

Profile:

- simulator
- IO
- trajectory batching
- encoder training
- transition training
- hidden-eval runtime

Potential accelerations:

- vectorized rollout batches
- JAX/PyTorch GPU
- compiled simulator path
- mixed precision if validated
- batched intervention runs
- persistent Modal workers

Numerical equivalence must be checked after optimization.

======================================================================
62. NUMERICAL CORRECTNESS
======================================================================

Validate:

- dt
- integration method
- time alignment
- stimulus alignment
- intervention onset
- transient removal
- phase shifts introduced by preprocessing
- normalization
- scaling
- interpolation

State discovery is extremely sensitive to timing bugs.

Write explicit tests.

======================================================================
63. PREPROCESSING
======================================================================

Preprocessing must be causal and reproducible.

Do NOT:

- smooth using future samples if online-state interpretation is claimed
- normalize using hidden test statistics
- phase-align using future information
- center using hidden test means

Separate:

    offline scientific analysis

from:

    causal online state estimation.

If using noncausal preprocessing for diagnostic plots, label it.

======================================================================
64. LATENT DIMENSION SEARCH
======================================================================

For every finalist method run:

    k = 1..Kmax

where Kmax is determined generically from circuit size / compute.

Plot:

    k vs
    prediction
    intervention fidelity
    closure
    compression

Select k using the pre-registered procedure.

Do not choose k because the latent plot "looks right."

======================================================================
65. CROSS-SEED ALIGNMENT
======================================================================

Latent axes may permute/rotate.

Implement alignment tools.

For linear subspaces:

- Procrustes
- canonical correlation
- principal angles

For nonlinear embeddings:

- fit mapping only on training data
- evaluate correspondence on held-out trajectories

Do not align using hidden test targets.

======================================================================
66. OUT-OF-DISTRIBUTION TESTS
======================================================================

Test reasonable shifts:

- input amplitude
- parameter spread
- perturbation timing
- initial state
- weight noise
- temporal sampling

Determine where state abstraction breaks.

Output valid operating domain.

Do not claim generality outside it.

======================================================================
67. REAL NETWORK SAMPLE SIZE HONESTY
======================================================================

We have few genuinely independent connectomes.

MANC releases are not independent animals in the same sense as MaleCNS.

Do not treat dataset versions as statistically independent biological
replicates.

Cross-connectome evidence is scientifically interesting but sample-limited.

Synthetic ensembles provide scale.

Real networks provide biological relevance.

State this clearly.

======================================================================
68. STATISTICS
======================================================================

Pre-register:

- experimental unit
- resampling unit
- confidence interval method
- paired comparison design
- multiplicity correction
- non-inferiority margins where relevant

Avoid pooling correlated trajectories as if they were independent animals.

Do not manufacture giant n from timesteps.

======================================================================
69. INDEPENDENT REVIEWERS
======================================================================

Before lock, run independent reviews:

REVIEW A — nonlinear dynamics / system identification

Questions:
- Is the latent model actually a state realization?
- Are Markov/closure tests meaningful?
- Is dimension selection sound?

REVIEW B — causal inference

Questions:
- Does intervention evidence justify causal claims?
- Are latent interventions legitimate?
- Are there shortcut confounders?

REVIEW C — representation learning

Questions:
- Could latent space be observationally predictive but mechanistically wrong?
- Are baselines strong enough?
- Is capacity controlled?

REVIEW D — computational neuroscience

Questions:
- Are simulations interpreted honestly?
- Are low-level interventions biologically sensible?
- Are claims stronger than evidence?

REVIEW E — statistics

Questions:
- Correct experimental unit?
- Hidden data contamination?
- CIs and tests?
- Multiplicity?

REVIEW F — leakage / clean-room

Questions:
- Can method agents access Phase 2 hidden answers?
- Did any answer-bearing files enter the clean room?
- Did names or sizes leak?

REVIEW G — adversarial state-discovery

Build NEW trap families unknown to the method composer.

REVIEW H — numerical methods

Check integration / timing / solver artifacts.

Fix blockers before lock.

======================================================================
70. POST-LOCK REVIEWS
======================================================================

After lock, allow reviewers to assess results.

They may identify:

- reporting errors
- statistical errors
- claims that need weakening

They must NOT modify the locked method while preserving the same version.

Method changes require a new version.

======================================================================
71. TEST SUITE
======================================================================

All existing tests must continue to pass.

Add Phase 3 tests covering:

CLEAN ROOM
- forbidden files rejected
- PHASE2_REPORT.md rejected
- oracle paths rejected
- hidden eval paths rejected
- allowlist hash verification

TRAJECTORY STORE
- deterministic cache keys
- no cross-dataset collisions
- correct intervention metadata

STATE MODELS
- dimension
- serialization
- deterministic inference
- input shape validation

SYNTHETIC TRUTH
- known state recovery
- nonlinear embeddings
- multiple implementations

CAUSAL TESTS
- intervention prediction
- microstate matching
- latent perturbation lifting

SHORTCUTS
- time leakage
- output copy
- input copy
- future leakage

CROSS-IMPLEMENTATION
- shared dynamics
- unrelated systems rejected

STATISTICS
- resampling unit
- CI regression tests

METHOD LOCK
- source/config hashes

MODAL
- optional smoke test

Do not weaken earlier tests.

======================================================================
72. EXPECTED PHASE 3 REPOSITORY ADDITIONS
======================================================================

Adapt cleanly to existing architecture.

Possible structure:

src/brainir/state/
    interface.py
    datasets.py
    encoders.py
    transitions.py
    readouts.py
    interventions.py
    lifting.py
    closure.py
    equivalence.py
    dimension.py
    uncertainty.py
    alignment.py

src/brainir/state/methods/
    pca_ssm.py
    subspace_id.py
    sindy_latent.py
    koopman.py
    predictive_bottleneck.py
    causal_state_v1.py

src/brainir/state/eval/
    predictive.py
    intervention.py
    markov.py
    microstate.py
    cross_impl.py
    synthetic_truth.py

research/phase3/
    methods_review.md
    selection_protocol.md
    reviews/
    METHOD_LOCK.json
    experiment_registry/

benchmarks/state_discovery_v1/

PHASE3_REPORT.md

Do not force this structure if a better one fits the repo.

======================================================================
73. POSSIBLE BRAINIR STATE-V1 METHOD
======================================================================

Do NOT hard-code this design.

But investigate whether the evidence supports something resembling:

STEP 1:
    collect informative trajectories and interventions.

STEP 2:
    estimate baseline intrinsic dimension / observability.

STEP 3:
    learn compressed encoder phi(x).

STEP 4:
    learn latent transition f(z,u).

STEP 5:
    penalize dependence on discarded microstate.

STEP 6:
    train on intervention outcomes.

STEP 7:
    learn implementation-specific encoders with shared dynamics.

STEP 8:
    perform latent-dimension pruning.

STEP 9:
    adversarially search for microstates/interventions that violate
    state equivalence.

STEP 10:
    refine until no public counterexample exceeds tolerance.

This could become a clean method.

But tournament it against simpler alternatives.

======================================================================
74. CRITICAL TEST: DOES THE STATE ACTUALLY EXIST?
======================================================================

For each real physical mechanism ask:

Can k << N achieve:

    near-full-state predictive performance
    +
    high intervention fidelity
    +
    approximate Markov closure?

If YES:
    compact state exists under our model and domain.

If NO:
    do not force one.

Maybe:

- additional hidden state is required;
- parameter context must be included;
- physical mechanism is not closed;
- the target computation is genuinely high-dimensional.

That is scientifically interesting too.

======================================================================
75. CRITICAL TEST: DO ALTERNATIVE CIRCUITS IMPLEMENT THE SAME STATE?
======================================================================

For alternative physical mechanisms discovered from public evidence:

Fit separate encoders.

Attempt shared dynamics.

Then test hidden trajectories.

Possible outcomes:

A.
    same low-dimensional state and same dynamics

This is strongest.

B.
    same dimension but different dynamics

Function may be similar but implementation differs computationally.

C.
    different dimensions

They may achieve similar output through different computations.

D.
    no compact state

The compact mechanism may not admit a simple abstraction.

Do not force outcome A.

======================================================================
76. CRITICAL TEST: CROSS-CONNECTOME SHARED STATE
======================================================================

If physical mechanisms transfer functionally between connectomes, test:

    Do they share a common latent dynamical system?

This is much more meaningful than:

    Do they contain the same neuron?

The desired final type of result would be:

    physical circuit A
       phi_A
         \
          shared latent dynamics f
         /
       phi_B
    physical circuit B

with held-out interventional fidelity.

======================================================================
77. LATENT MODEL NULLS
======================================================================

Construct null comparisons.

Examples:

- shuffled time
- random neural subspace
- random encoder
- random latent transition
- independent latent model per trajectory
- shared encoder on unrelated mechanisms
- shared dynamics between unrelated synthetic systems
- input-only representation
- readout-only representation

A shared latent model should not appear "universal" just because it is
overpowered.

======================================================================
78. MODEL CAPACITY MATCHING
======================================================================

When comparing shared vs independent models, match capacity reasonably.

Otherwise a large shared network may win merely because it has more
parameters.

Report:

    parameter count
    effective degrees of freedom
    training compute

Use regularization consistently.

======================================================================
79. FAILURE / ABSTENTION
======================================================================

BrainIR State should be able to say:

    no compact causal state found under current evidence

or:

    dimension unresolved: k in [2,4]

or:

    observational state found, causal equivalence failed

or:

    cross-connectome equivalence unsupported

These are legitimate outputs.

Do not always return a confident answer.

======================================================================
80. FIRST REAL RESULT WE WANT
======================================================================

A meaningful Phase 3 result would look approximately like:

    BrainIR finds that several different physical circuits can each be
    mapped into a low-dimensional state representation.

    A shared transition law predicts unseen trajectories and interventions
    across those implementations.

    The same abstract state can be perturbed through different low-level
    neuron interventions and produces equivalent downstream effects.

    The representation uses dramatically fewer dimensions than the
    physical circuit.

This is much stronger than another neuron-selection result.

======================================================================
81. WHAT WOULD BE A BAD RESULT
======================================================================

Do NOT call this success:

    "PCA explains 95% variance."

Do NOT call this success:

    "A 2D UMAP plot looks circular."

Do NOT call this success:

    "An autoencoder reconstructs neurons."

Do NOT call this success:

    "Latent z correlates with output."

Do NOT call this success:

    "Different circuits have correlated first principal components."

Those can be useful diagnostics, not causal state discovery.

======================================================================
82. WHAT WOULD CONSTITUTE A VERY STRONG RESULT
======================================================================

A strong Phase 3 result would satisfy:

1. low k

2. near-full-state multi-step prediction

3. strong hidden intervention prediction

4. low residual microstate dependence

5. robustness across parameter draws

6. stable state subspace across seeds

7. alternative physical mechanisms map to equivalent state dynamics

8. cross-connectome shared dynamics survive held-out interventions

9. strong baselines fail one or more of these tests

10. adversarial counterexample search cannot easily break the abstraction

That would justify moving toward program synthesis.

======================================================================
83. PHASE 3 SHOULD PRODUCE A STATE MODEL, NOT A STORY
======================================================================

Final scientific artifact should be executable:

    encoder phi
    transition f
    readout g
    intervention map
    uncertainty
    validity domain

A human-readable interpretation is secondary.

======================================================================
84. REPORTING
======================================================================

Create:

    PHASE3_REPORT.md

IMPORTANT:

If it contains hidden Phase 3 evaluation results, mark it answer-bearing.

Do not later copy it into Phase 4 clean development.

Report:

- clean-room construction
- leakage audit
- Phase 3 benchmark lock
- synthetic benchmark
- methods review
- methods tournament
- final algorithm
- mathematical formulation
- latent dimension selection
- predictive performance
- intervention performance
- Markov closure
- microstate equivalence
- robustness
- cross-mechanism equivalence
- cross-connectome equivalence
- latent intervention results
- counterexamples
- baselines
- ablations
- statistics
- compute
- failures
- uncertainty
- limitations
- reviews
- one next phase recommendation

Do not hide negative evidence.

======================================================================
85. PHASE 3 ACCEPTANCE CRITERIA
======================================================================

Do NOT declare Phase 3 complete until all of the following are satisfied:

1. Phase 1 benchmark remains frozen.

2. Phase 2 locked method remains unchanged.

3. Main repository integrity passes.

4. A genuinely clean Phase 3 workspace exists.

5. PHASE2_REPORT.md cannot enter the clean room.

6. Hidden oracle/evaluation artifacts cannot enter the clean room.

7. Clean-room allowlist is machine-readable and audited.

8. Phase 2 candidate mechanisms required for Phase 3 are regenerated from
   public evidence rather than copied from answer-bearing reports.

9. Phase 3 evaluation protocol is frozen before method development.

10. Hidden real-intervention test generation is locked.

11. Synthetic state-discovery benchmark exists.

12. Synthetic benchmark includes multiple physical implementations of the
    same hidden state dynamics.

13. Synthetic benchmark includes non-compressible controls.

14. Shortcut/adversarial traps exist.

15. Strong system-identification baselines are implemented.

16. Several candidate algorithm families are evaluated.

17. Method selection occurs without hidden real evaluation.

18. Final BrainIR State v1 method has a clear mathematical definition.

19. Latent dimension is selected generically, not manually.

20. Full-state predictive upper-bound baseline exists.

21. Input-only and output-history-only shortcut baselines exist.

22. Multi-step predictive sufficiency is measured.

23. Hidden intervention fidelity is measured.

24. Markov closure is measured.

25. Residual microstate dependence is measured.

26. Latent intervention lifting exists or a rigorous reason is documented
    for why it cannot be implemented.

27. Multiple low-level implementations of equivalent latent interventions
    are tested where possible.

28. Synthetic latent ground truth is recovered on held-out systems.

29. Reproducibility across training seeds is quantified.

30. Latent coordinate equivalence is evaluated up to valid transforms.

31. Alternative neuron-level mechanisms are tested for shared dynamics.

32. Cross-connectome shared dynamics are tested.

33. Independent vs shared dynamics models are compared fairly.

34. Cross-implementation generalization is evaluated.

35. Robustness under parameter uncertainty is evaluated.

36. OOD input/intervention behavior is evaluated.

37. Counterexample search is run.

38. Negative controls are run.

39. Model-capacity controls are run.

40. Important ablations are complete.

41. Simulation/query/compute costs are recorded.

42. All old tests remain green.

43. Phase 3 tests are green.

44. Independent reviews A–H are complete.

45. Blockers are resolved before method lock.

46. Final method/config is locked before hidden real evaluation.

47. Hidden evaluation attempts are logged.

48. No post-hidden-evaluation tuning is silently folded into v1.

49. PHASE3_REPORT.md exists.

50. A clear scientific conclusion is reached:

    - compact causal state discovered,
    - partially supported,
    - or not supported.

All three are acceptable if honestly demonstrated.

======================================================================
86. METHOD LOCK / TAG
======================================================================

Before hidden real evaluation create:

    research/phase3/METHOD_LOCK.json

Suggested tag:

    brainir-state-v1-preblind

After evaluation create an appropriate final Phase 3 tag.

Record:

- commit
- source hashes
- benchmark hash
- clean-room hash
- training-data manifest
- architecture
- hyperparameters
- latent dimension rule
- random seeds
- compute budget
- package environment

======================================================================
87. SELF-AUDIT
======================================================================

Before completion, try aggressively to disprove the central claim.

Ask:

Could time alone explain the latent state?

Could stimulus alone explain it?

Could output history alone explain it?

Did future information leak into the encoder?

Is latent dimensionality underestimated because of smoothing?

Does discarded neural state still predict future behavior?

Do two microstates with the same z actually diverge?

Does intervention fidelity collapse on unseen perturbations?

Does shared cross-connectome dynamics only work because capacity is huge?

Does alignment rely on neuron identity?

Does the latent model memorize physical implementation?

Does the representation change completely across random seeds?

Does parameter uncertainty require extra hidden state?

Does the model fail after transient perturbation?

Is a simple linear model equally good?

Is PCA equally good?

Can unrelated synthetic systems be falsely aligned?

Does the method incorrectly find low-dimensional states in the
non-compressible controls?

Can the counterexample search break it immediately?

Do not just answer these questions verbally.

TEST THEM.

======================================================================
88. IMPORTANT CLAIM LANGUAGE
======================================================================

Be scientifically precise.

Do not write:

    "We found the true state variables of the fly brain."

Prefer:

    "Within the tested connectome-constrained dynamical model and
     intervention domain, a k-dimensional state representation was
     sufficient to predict X and Y with error Z."

Do not claim formal causal abstraction unless requirements are actually met.

Do not claim biological truth from simulator-only evidence.

======================================================================
89. WHAT NOT TO DO
======================================================================

DO NOT:

- open PHASE2_REPORT.md in clean development
- expose Phase 2 oracle identities to method agents
- hard-code expected latent dimension
- hard-code oscillator semantics
- use hidden test results for tuning
- use UMAP/t-SNE as scientific state discovery
- let an LLM invent the latent interpretation
- optimize only reconstruction error
- collapse all metrics into one score
- treat MANC versions as independent biological animals
- claim causal variables from correlation alone
- begin symbolic source-code generation
- begin formal theorem proving
- build a web UI
- build FlyGym embodiment
- start whole-brain decompilation
- make consciousness claims

======================================================================
90. AUTONOMY
======================================================================

The user is not your operator.

YOU do the work.

Use:

- shell
- browser
- web research
- Python
- uv
- git
- Modal
- CPU/GPU compute
- package installation
- code generation
- testing
- debugging
- profiling
- paper reading
- mathematical derivation
- independent agents
- reviews

Do not ask the user to manually perform routine tasks.

Do not ask the user to copy data.

Do not ask the user to run commands.

Do not ask the user which method to choose.

Investigate and decide scientifically.

Only stop for genuinely unavoidable manual action such as:

- login
- CAPTCHA
- 2FA
- physical action
- inaccessible OS permission
- irreversible destructive action affecting unrelated user data

Complete everything else first.

======================================================================
91. FINAL RESPONSE TO USER
======================================================================

Do not send constant status updates.

Work autonomously until Phase 3 is actually complete or there is a genuine
blocker.

At completion, return a concise report containing:

- Phase 3 status
- clean-room status
- BrainIR State v1 algorithm in plain English
- discovered latent dimension(s)
- synthetic hidden-state recovery
- full-state vs compressed prediction
- held-out intervention fidelity
- Markov-closure result
- microstate-equivalence result
- whether latent interventions worked
- whether different physical mechanisms share the same latent dynamics
- cross-connectome result
- strongest baseline
- where BrainIR beats / matches / loses to it
- counterexample findings
- robustness result
- tests passing
- review status
- Modal cost
- method lock/tag
- biggest limitation
- ONE recommended next phase

DO NOT START THE NEXT PHASE.

======================================================================
92. THE PHASE 3 NORTH STAR
======================================================================

Phase 2 found compact physical circuits.

Phase 3 must answer a deeper question:

    What information must the nervous system remember from one moment
    to the next in order to generate this computation?

And then:

    Do different physical neural circuits preserve the SAME information
    and transform it according to the SAME dynamics?

If the answer is yes, BrainIR has moved from:

    finding important neurons

to:

    discovering computation.

That is the entire point of Phase 3.