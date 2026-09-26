# BrainIR Phase 4 — Interventionally Trained Causal State Models + Active Experiment Design

You are taking full scientific, mathematical, ML, computational-neuroscience,
causal-inference, system-identification, statistical, software, and operational
ownership of Phase 4 of BrainIR.

MAIN REPOSITORY
C:\Dev\BrainIR

PHASE 4 CLEAN DEVELOPMENT WORKSPACE
C:\Dev\BrainIR_p4clean

FROZEN PHASE 1 BENCHMARK
tag: dng100-benchmark-v1
commit: a7c0142

LOCKED PHASE 2 METHOD
BrainIR v1.2.0
tag: brainir-v1-preblind
commit: 959d689

PHASE 3 FINAL
tag: brainir-state-v1-phase3-final
commit: cf5eebe

Phase 4 has NOT started.

======================================================================
0. PHASE 4 EXISTS BECAUSE PHASE 3 ANSWERED THE WRONG QUESTION TOO WELL
======================================================================

Phase 3 asked whether we could compress neural dynamics into a small
predictive state.

That is necessary.

It is NOT sufficient.

A latent representation can:

- predict ordinary trajectories;
- have low dimension;
- look dynamically clean;
- reconstruct readout behavior;

while completely failing to preserve what happens when the neural circuit
is causally perturbed.

That is unacceptable for BrainIR.

BrainIR is not trying to discover merely:

    a compact predictor.

It is trying to discover:

    a compact CAUSAL STATE of a neural computation.

Therefore Phase 4 changes the training target itself.

Instead of:

    learn latent state from passive/predictive trajectories
        ->
    test interventions afterward

we now want:

    interventions are part of the state-learning problem from the beginning.

The central Phase 4 question is:

    Can we learn a low-dimensional state representation whose dynamics
    actually mediate the effects of neural interventions, generalize to
    unseen interventions, and support valid low-level <-> latent
    intervention mappings?

If YES, then BrainIR has a legitimate candidate computational state.

If NO, then we stop claiming that this system has been causally decompiled.

======================================================================
1. PHASE 4 NORTH STAR
======================================================================

We want to learn:

    x_t --phi--> z_t

with controlled latent dynamics:

    z_(t+1) = f(z_t, u_t, a_t)

and relevant readout:

    y_t = g(z_t, u_t)

where:

    x_t = microscopic neural state
    z_t = compact causal state
    u_t = ordinary exogenous stimulus/input
    a_t = neural intervention / control action
    y_t = task-relevant output

But this equation alone is not enough.

The desired causal property is:

    low-level intervention
        ->
    latent state change
        ->
    future latent dynamics
        ->
    output consequence.

In other words, the intervention's effect should FLOW THROUGH z.

A candidate z should not merely correlate with intervention outcomes.

======================================================================
2. WHAT SUCCESS WOULD ACTUALLY MEAN
======================================================================

A strong Phase 4 result would show:

1. z is compact.

2. z predicts ordinary future behavior.

3. z predicts unseen intervention outcomes.

4. after conditioning on z, discarded microscopic state contributes little
   task-relevant intervention information.

5. two different microscopic interventions that create the same z produce
   approximately the same relevant future behavior.

6. desired latent-state perturbations can be implemented through valid
   low-level neural interventions.

7. an intervention policy trained to distinguish candidate latent models
   chooses informative perturbations more efficiently than random probing.

8. the learned state generalizes to intervention types not seen during fitting.

9. where multiple physical circuits exist, they may share the same causal
   latent dynamics.

10. where they do NOT share them, BrainIR reports that rather than forcing
    equivalence.

======================================================================
3. DO NOT START SYMBOLIC PROGRAM SYNTHESIS
======================================================================

Phase 3 did not provide enough causal evidence to justify symbolic
decompilation.

Therefore Phase 4 must NOT build:

- the final BrainIR DSL;
- executable source-code explanations;
- formal SMT verification;
- a whole-brain compiler;
- an LLM explanation layer;
- robotics embodiment;
- FlyGym integration;
- a UI.

Phase 4 ends with:

    a validated causal state model

or:

    evidence that no such compact state model is supported.

Only if Phase 4 succeeds should later phases attempt symbolic programs.

======================================================================
4. ABSOLUTELY DO NOT TUNE AGAINST PHASE 3 HIDDEN RESULTS
======================================================================

PHASE3_REPORT.md is answer-bearing.

It must NOT enter the Phase 4 clean development environment.

Do not copy:

- PHASE3_REPORT.md
- hidden Level C outputs
- hidden intervention results
- hidden cross-connectome scores
- answer-bearing post-lock reviews
- hidden counterexamples
- hidden benchmark truth
- hidden real predictions
- hidden method ranking tables

The Phase 4 clean agents may know only the GENERIC scientific task:

    predictive latent states are not sufficient;
    learn causal state using interventions.

They must NOT receive:

- which real system failed;
- how badly it failed;
- which intervention type failed;
- hidden k values;
- hidden model rankings;
- hidden network-specific outcomes.

The main orchestrator may know history.

The method-development agents may not.

======================================================================
5. HARDER CLEAN-ROOM ISOLATION
======================================================================

Create:

    C:\Dev\BrainIR_p4clean

with explicit technological isolation.

Preferred:

- Docker/container sandbox;
- only allowlisted files mounted;
- no parent repository mount;
- no access to scratchpads containing hidden outputs;
- file-access audit;
- content scanner;
- deny-list paths;
- network rules where useful.

Do not rely only on instructions.

Create:

    scripts/make_phase4_cleanroom.py

supporting:

    --build
    --check
    --destroy-and-rebuild
    --audit

Create:

    research/phase4/CLEANROOM_MANIFEST.json
    research/phase4/LEAKAGE_POLICY.md

Every copied file must record:

    source
    destination
    SHA256
    reason
    classification

======================================================================
6. ALLOWED INPUTS TO PHASE 4 CLEAN DEVELOPMENT
======================================================================

Potentially allowed:

- generic simulator interface;
- public connectome bundles;
- public trajectory-generation tools;
- locked Phase 2 method code;
- locked Phase 3 method code as a BASELINE only;
- generic state-model API;
- synthetic-development generator;
- public benchmark protocol;
- public intervention descriptions;
- generic numerical libraries;
- generic research papers/method descriptions;
- allowed public cross-connectome metadata.

Phase 3 locked model may be included only as:

    BrainIR State v1 baseline

not as a source of hidden outcomes.

======================================================================
7. BUILD A NEW BENCHMARK VERSION
======================================================================

Do NOT merely rerun Phase 3's benchmark.

Create a new benchmark focused explicitly on intervention mediation.

Suggested:

    benchmarks/causal_state_v1/

or:

    benchmarks/state_discovery_v2/

Choose the cleanest repository architecture.

The benchmark should include:

    public development split
    public validation split
    hidden synthetic confirmation
    hidden real intervention test
    hidden intervention-family shift
    hidden OOD test
    evaluator
    PROTOCOL.md
    BENCHMARK_LOCK.json

Freeze benchmark generation BEFORE Phase 4 method development.

======================================================================
8. THE NEW BENCHMARK MUST BE CALIBRATED TO THE REAL SYSTEMS
======================================================================

One major Phase 3 concern was that synthetic latent-state recovery was
meaningfully easier / differently structured than the real system.

Phase 4 synthetic systems must reproduce important REALISTIC properties
without leaking hidden real answers.

Calibrate GENERIC properties from public permitted data such as:

- dimensionality range;
- firing/rate scales;
- timescales;
- intervention magnitude distributions;
- noise scale;
- response sparsity;
- recurrent strength;
- parameter uncertainty;
- observation count;
- trajectory duration;
- input magnitude;
- signal-to-noise ratio;
- frequency range;
- saturation/clipping behavior.

Do NOT encode real hidden neuron identities or hidden real outcomes.

The purpose is distributional realism.

======================================================================
9. NEW SYNTHETIC CAUSAL-STATE SUITE
======================================================================

Build systems with known true causal state.

Include:

1. linear controlled state-space model

2. nonlinear controlled oscillator

3. leaky integrator with interventions

4. perfect integrator

5. gated memory

6. bistable switch

7. winner-take-all

8. negative feedback controller

9. coupled fast/slow state

10. hidden discrete mode + continuous state

11. redundant physical implementation

12. multiple microscopic circuits implementing same z-dynamics

13. latent state embedded through nonlinear population code

14. irrelevant high-variance nuisance neurons

15. intervention-sensitive low-variance state

16. hidden parameter/context state

17. partial observability requiring delay/history

18. multiple attractors

19. transient dynamics + steady-state dynamics

20. genuinely high-dimensional system where NO compact causal state exists

21. observationally compressible but interventionally non-compressible system

22. system where readout prediction is easy but causal state is hard

23. system with intervention confounding

24. system with redundant low-level intervention realizations

25. system where same immediate readout corresponds to different causal state

======================================================================
10. THE MOST IMPORTANT ADVERSARIAL TRAP
======================================================================

Create systems where:

    z_observational

predicts normal trajectories extremely well

BUT:

    z_observational

fails badly under interventions.

This trap should be central.

A successful Phase 4 method should reject the observational shortcut and
recover the interventionally sufficient state.

This is exactly the type of scientific distinction BrainIR needs.

======================================================================
11. INTERVENTION TYPES
======================================================================

Support a broad generic intervention API.

Potential intervention families:

- temporary single-neuron silencing
- persistent silencing
- activation pulse
- sustained activation/current
- paired intervention
- grouped intervention
- state kick
- edge weakening/removal
- parameter perturbation where scientifically appropriate
- stimulus perturbation
- initial-condition perturbation

Do not assume every simulator supports every class.

Record intervention capability per system.

======================================================================
12. HELD-OUT INTERVENTION GENERALIZATION
======================================================================

Do not only hold out new examples of intervention types already seen.

Create tests such as:

TRAIN:

    single-node silencing
    low-amplitude pulse
    stimulus changes

TEST:

    paired silencing
    larger pulse
    activation
    grouped intervention

and rotate splits across synthetic systems.

The exact split must be frozen before method development.

This answers:

    did the model learn dynamics,
    or memorize intervention IDs?

======================================================================
13. THE CENTRAL METRIC: STATE MEDIATION
======================================================================

Prediction under interventions alone is NOT enough.

A huge direct neural network could map:

    intervention ID -> output

without learning a causal state.

We need to test whether intervention effect is actually mediated by z.

Conceptually:

    a_t
      |
      v
    delta z_t
      |
      v
    z future
      |
      v
    y future

Measure whether adding microscopic state/intervention identity AFTER z
still provides substantial predictive information.

For example compare:

MODEL A:
    future ~ z_t, u_t, intervention-through-latent

MODEL B:
    future ~ z_t, u_t, intervention-through-latent, x_residual, intervention_ID

If B strongly improves held-out prediction, z is missing causal state.

Develop statistically sound mediation / conditional-prediction tests.

Do not make strong classical mediation claims unless assumptions justify them.

Call it:

    state mediation score

or another precise term.

======================================================================
14. INTERVENTION READ-IN
======================================================================

A major new component must explicitly model:

    low-level intervention -> latent state effect.

For physical intervention a:

    Delta z = r(z, a)

or:

    z^+ = R(z^-, a)

where R is an intervention read-in model.

Do not simply add an intervention embedding to an RNN and call it causal.

The intervention operator should have interpretable semantics and should be
tested on unseen interventions.

======================================================================
15. NATIVE LATENT LIFT
======================================================================

Phase 4 should learn the inverse problem jointly.

Given a desired abstract intervention:

    target delta_z

find valid physical intervention:

    a*

such that:

    R(z, a*) ~= target delta_z.

Train / derive / optimize this mapping as part of the Phase 4 framework.

Do not leave lifting entirely post hoc.

Possible objective:

    a* = argmin_a
        ||R(z,a) - delta_z_target||^2
        + lambda_cost * intervention_cost(a)
        + lambda_complexity * intervention_complexity(a)

subject to permitted intervention constraints.

======================================================================
16. MULTIPLE LIFTS OF THE SAME LATENT PERTURBATION
======================================================================

For target delta_z:

find several distinct physical interventions:

    a1
    a2
    a3

such that:

    R(z,a1) ~= R(z,a2) ~= R(z,a3).

Then test whether their future relevant trajectories agree.

This is one of the strongest possible tests that the abstraction is real.

If future behavior strongly depends on which microscopic implementation
was used, z is incomplete.

======================================================================
17. INTERVENTIONAL STATE-SPACE MODEL FAMILY
======================================================================

Explicitly investigate the recent interventional SSM formulation.

Do NOT blindly copy it.

Understand:

- assumptions;
- identifiability conditions;
- intervention representation;
- linear/nonlinear limits;
- whether our simulator satisfies assumptions;
- whether the method scales to our systems.

Implement an appropriately adapted baseline or candidate.

This should be a serious candidate, not a literature citation.

======================================================================
18. CANDIDATE METHOD FAMILIES
======================================================================

Run a tournament.

Candidate A:
INTERVENTIONAL LINEAR STATE-SPACE MODEL

Strong, simple reference.

Candidate B:
CONTROLLED DMD / DMDc

Because Phase 3's strongest baseline was linear-control-like, test this
seriously.

Candidate C:
SUBSPACE IDENTIFICATION WITH CONTROL

Candidate D:
SPARSE CONTROLLED SINDY

    dz/dt = Theta(z,u,a) Xi

Candidate E:
INTERVENTIONAL PREDICTIVE BOTTLENECK

Encoder optimized for future prediction AND intervention prediction.

Candidate F:
CONTROLLED KOOPMAN MODEL

Candidate G:
LATENT NEURAL CONTROLLED SSM

Candidate H:
NEURAL ODE WITH INTERVENTION OPERATOR

Candidate I:
INTERVENTIONAL CAUSAL STATE MODEL

Fresh Phase 4 composition.

Candidate J:
SHARED-DYNAMICS CAUSAL MODEL

Implementation-specific encoder/read-in
+
shared f.

Do not choose the winner in advance.

======================================================================
19. DO NOT LET MODEL CAPACITY WIN BY BRUTE FORCE
======================================================================

Compare methods at matched / reported capacity.

Track:

    encoder parameters
    transition parameters
    intervention read-in parameters
    decoder/readout parameters
    training FLOPs
    GPU time

A gigantic neural model beating a sparse 2D state model on prediction alone
does not automatically constitute a better mechanistic explanation.

======================================================================
20. PHASE 3 METHOD IS A FROZEN BASELINE
======================================================================

BrainIR State v1 must remain unchanged.

Run it on the NEW Phase 4 benchmark as a frozen comparator.

Do not tune it.

Its purpose is to answer:

    does explicit interventional training actually improve causal state
    discovery over the Phase 3 observational/predictive approach?

======================================================================
21. STRONGEST SIMPLE BASELINES
======================================================================

Include at minimum:

- Phase 3 BrainIR State v1
- DMDc / tuned DMDc
- controlled linear SSM
- subspace ID
- full-state model
- input-only model
- intervention-only model
- readout-history model
- intervention-ID -> output direct model
- random projection
- PCA + control model

If a simpler baseline wins, report it.

======================================================================
22. DIRECT INTERVENTION SHORTCUT BASELINE
======================================================================

Train:

    y_future = h(intervention_ID, stimulus, y_history)

with NO neural latent state.

This baseline is critical.

If BrainIR does not beat it on unseen interventions, then the state model
may add little.

======================================================================
23. FULL-STATE CAUSAL UPPER BOUND
======================================================================

Train the strongest reasonable full-state controlled model:

    x_t, u_t, a_t -> x_future / y_future.

This establishes:

    Is the intervention outcome predictable at all?

If the full state cannot predict it, failure of a compressed state cannot
be interpreted as evidence against compression.

======================================================================
24. ACTIVE EXPERIMENT DESIGN
======================================================================

Do not collect interventions randomly forever.

Build an active-design layer.

At each round:

1. maintain candidate causal state models / uncertainty ensemble;

2. generate feasible intervention candidates;

3. predict their outcomes;

4. score how informative each experiment would be;

5. choose intervention;

6. run simulator;

7. update model;

8. repeat.

Potential acquisition functions:

- expected information gain
- disagreement among models
- posterior entropy reduction
- observability gain
- Fisher information
- reduction in latent-dimension uncertainty
- reduction in intervention prediction uncertainty
- counterexample likelihood

Tournament acquisition strategies.

======================================================================
25. ACTIVE DESIGN MUST BE COMPARED FAIRLY
======================================================================

Compare against:

- random intervention selection
- uniform intervention coverage
- magnitude sweep
- greedy prediction-error targeting
- structural heuristics
- passive-only data
- fixed experimental protocol

Plot:

    causal-state quality
        vs
    number of interventions
        vs
    simulator cost

Active design must earn its complexity.

======================================================================
26. DESIGNED PERTURBATIONS FOR OBSERVABILITY
======================================================================

Before training, estimate which latent directions are poorly excited.

Use:

- empirical observability Gramian where applicable;
- Fisher information;
- local Jacobian sensitivity;
- intervention response covariance;
- singular-value spectra.

Design interventions that excite weakly observed directions.

The central logic:

    passive activity may not reveal all state dimensions.

Phase 4 must actively reveal them.

======================================================================
27. ACTIVE DESIGN MAY SEARCH OVER TEMPORAL PATTERNS
======================================================================

Do not restrict experiment design to:

    which neuron?

Also consider:

    when?
    duration?
    magnitude?
    pulse shape?
    sequence?

where supported.

Candidate perturbations may include:

- impulse
- step
- pulse train
- random binary sequence
- chirp / multiscale input
- paired temporally separated pulses

Only use patterns scientifically meaningful for the simulator.

======================================================================
28. INFORMATION EFFICIENCY
======================================================================

Track:

    number of experiments
    simulator calls
    simulated biological seconds
    unique intervention targets
    intervention magnitude budget
    CPU/GPU compute

One Phase 4 goal is not just better causal states.

It is:

    discovering them with fewer informative experiments.

======================================================================
29. CURRICULUM OF INTERVENTIONS
======================================================================

Investigate whether learning improves when progressing:

    simple interventions
        ->
    combined interventions
        ->
    unseen compositions.

Possible curriculum:

ROUND 1:
single perturbations

ROUND 2:
paired perturbations

ROUND 3:
group perturbations

ROUND 4:
temporal sequences

Do not force curriculum if evidence rejects it.

======================================================================
30. INTERVENTION COMPOSITION
======================================================================

Test whether learned operators compose.

If:

    a
    then b

is applied, does latent model predict:

    R(R(z,a), b)

appropriately?

Compare simultaneous vs sequential perturbations.

This is important for later program semantics.

======================================================================
31. CAUSAL CLOSURE TEST
======================================================================

Phase 3's observational Markov closure is not enough.

Define INTERVENTIONAL closure:

Given z_t, u_t, a_t,

does microscopic residual state x_residual add meaningful information about:

    z_future
    y_future

under intervention?

The key comparison is:

    error(z,u,a)

versus:

    error(z,u,a,x_residual).

If residual neural state still matters strongly under interventions,
z is incomplete.

======================================================================
32. MICROSTATE EQUIVALENCE UNDER INTERVENTION
======================================================================

Find pairs:

    x_A
    x_B

with:

    phi(x_A) ~= phi(x_B).

Apply SAME future intervention sequence.

Test whether:

    future relevant behavior_A
        ~=
    future relevant behavior_B.

This is stricter than Phase 3 because intervention sequences are included.

======================================================================
33. INTERVENTIONAL BISIMULATION-LIKE TEST
======================================================================

For states close in latent space, evaluate:

1. same immediate task-relevant output;

2. same response distribution under each permitted intervention class;

3. next latent states remain close.

This approximates causal state equivalence.

Do not claim formal bisimulation unless proven.

======================================================================
34. IDENTIFIABILITY ANALYSIS
======================================================================

For every major method, state:

    identifiable under what assumptions?

Check whether assumptions hold in synthetic systems.

For real connectome simulations, identify which assumptions are:

- supported;
- approximate;
- violated;
- unknown.

Do not make stronger claims than identifiability conditions permit.

======================================================================
35. LATENT DIMENSION SELECTION
======================================================================

Do not hard-code k.

Search k generically.

But Phase 4 dimension selection should prioritize:

    intervention fidelity
        +
    interventional closure

rather than observational prediction alone.

Possible rule:

smallest k satisfying frozen thresholds on:

    held-out prediction
    intervention fidelity
    mediation
    closure.

Pre-register exact rule.

======================================================================
36. DIMENSION UNCERTAINTY
======================================================================

If k=2 and k=3 perform similarly:

report:

    dimension unresolved: 2–3

Do not invent exactness.

Bootstrap / resample training interventions.

Measure selected-k stability.

======================================================================
37. CAUSAL REPRESENTATION STABILITY
======================================================================

Repeated seeds / intervention subsets should recover equivalent state
spaces up to valid transformations.

Measure:

- subspace alignment
- CCA
- Procrustes
- nonlinear alignment where justified
- intervention response equivalence
- vector-field similarity

Coordinate labels themselves do not matter.

======================================================================
38. ACTIVE LEARNING SHOULD REDUCE DIMENSION UNCERTAINTY
======================================================================

One explicit active-design target can be:

    choose intervention that maximally distinguishes k=2 vs k=3 models.

This is scientifically interesting.

The experiment designer is not only identifying parameters.

It can identify the correct model class.

======================================================================
39. COUNTEREXAMPLE-GUIDED MODEL REFINEMENT
======================================================================

Use:

    candidate causal state
       ->
    search intervention causing largest disagreement
       ->
    simulator response
       ->
    add to training
       ->
    refit

This is an interventional CEGAR-like loop.

Do NOT use hidden test counterexamples for development.

Public/development counterexamples only.

======================================================================
40. COUNTEREXAMPLE SEARCH OBJECTIVES
======================================================================

Search for interventions maximizing:

- output error;
- latent trajectory error;
- state-mediation violation;
- microstate-equivalence violation;
- intervention-lift disagreement;
- model-ensemble disagreement.

Use:

- random search
- Bayesian optimization
- evolutionary search
- gradients where valid

Tournament them on development systems.

======================================================================
41. NEW ADVERSARIAL TRAP FAMILIES
======================================================================

Reviewers should create traps UNKNOWN to the method composer.

Examples:

A. observationally perfect / causally wrong latent

B. intervention ID shortcut

C. input-history shortcut

D. time/phase shortcut

E. hidden slow state exposed only by perturbation

F. latent dimension changes under intervention

G. hysteresis

H. weak causal variable with tiny variance

I. two microscopic states equal observationally but different under intervention

J. parameter context masquerading as state

K. intervention saturation/clipping

L. state-dependent intervention efficacy

M. nonlinear composition of interventions

N. redundant intervention implementations

O. intervention affects unobserved nuisance but not task state

P. no compact causal state

======================================================================
42. STATE-DEPENDENT INTERVENTION EFFECTS
======================================================================

Do not assume intervention effect is independent of current state.

Model:

    R(z, a)

not necessarily:

    R(a).

Test whether same intervention applied at different z yields different
effects.

This may be critical for oscillatory/recurrent systems.

======================================================================
43. TIME-LOCAL VS PERSISTENT INTERVENTIONS
======================================================================

Distinguish:

- instantaneous kick;
- finite-duration perturbation;
- persistent parameter/state change.

Do not treat them as equivalent.

The latent intervention operator should know intervention semantics.

======================================================================
44. TEMPORAL CREDIT
======================================================================

Interventions may influence behavior after a delay.

Evaluate multiple horizons.

Do not score only immediate effect.

Measure:

    short
    medium
    long horizon.

======================================================================
45. SMALL-EFFECT INTERVENTIONS
======================================================================

Near-zero true effects can make normalized errors pathological.

Design metrics that remain meaningful when denominator ~0.

Use:

- absolute effect error
- normalized effect error with frozen floor
- sign correctness
- confidence intervals
- thresholded detectability

Pre-register floor.

Do not calibrate after hidden results.

======================================================================
46. EFFECT SIZE CALIBRATION
======================================================================

Generate intervention magnitudes spanning:

- below detection
- weak
- moderate
- strong

Evaluate whether model confidence reflects effect detectability.

BrainIR should abstain on genuinely unidentifiable tiny effects.

======================================================================
47. ABSTENTION
======================================================================

Outputs should distinguish:

    predicted effect

from:

    insufficient evidence.

Train/calibrate abstention.

Measure:

- coverage
- accuracy conditional on prediction
- false confidence
- calibration

Do not reward guessing.

======================================================================
48. CAUSAL STATE OUTPUT SCHEMA
======================================================================

Create versioned:

    BrainIRCausalStateModel

Fields should include:

- method version
- source dataset
- mechanism
- latent dimension
- encoder
- latent dynamics
- intervention read-in
- latent lift
- readout
- intervention domain
- observability diagnostics
- training intervention families
- held-out intervention families
- prediction metrics
- mediation metrics
- closure metrics
- lift metrics
- microstate equivalence
- dimension uncertainty
- intervention uncertainty
- active experiment history
- validity domain
- failure flags
- abstention
- provenance
- hashes

======================================================================
49. EXECUTABLE MODEL
======================================================================

Model should support:

    encode(x_t)
    step(z_t, u_t, intervention)
    predict(...)
    intervention_effect(...)
    lift(delta_z_target)
    uncertainty(...)
    validity(...)

Do not make English prose the artifact.

======================================================================
50. TRAINING OBJECTIVE
======================================================================

Do not blindly copy this, but investigate an objective of the form:

    L =
        L_observational_future
      + lambda_int * L_intervention_future
      + lambda_med * L_state_mediation
      + lambda_closure * L_interventional_closure
      + lambda_micro * L_microstate_equivalence
      + lambda_lift * L_lift_consistency
      + lambda_complex * L_complexity
      + lambda_robust * L_uncertainty

Every term must have:

- definition
- motivation
- units/scaling
- ablation
- sensitivity analysis

No magic loss soup.

======================================================================
51. TRAINING WITHOUT FUTURE LEAKAGE
======================================================================

Encoder may use:

    current state
    permitted causal history

It may NOT use:

    future trajectory
    future intervention result
    hidden evaluator output.

Audit data pipeline.

======================================================================
52. TREAT DELAYS HONESTLY
======================================================================

If the true state requires history, allow:

    phi(x_t, x_(t-1), ...)

or explicit delay coordinates.

But count history length as part of model complexity.

Do not hide missing state inside a giant RNN memory.

======================================================================
53. MECHANISTIC TRANSITION MODEL
======================================================================

Prefer interpretable/simple f where performance allows.

Tournament:

- linear
- bilinear/control-affine
- polynomial
- sparse nonlinear
- small neural network
- neural ODE

If simple controlled dynamics match a deep model, prefer simple.

======================================================================
54. CONTROL-AFFINE DYNAMICS
======================================================================

Investigate whether systems can be modeled as:

    dz/dt = f(z,u) + Sum_j g_j(z) a_j

This may provide interpretable intervention semantics.

Do not force control-affine structure if data rejects it.

======================================================================
55. SHARED CAUSAL STATE ACROSS ALTERNATIVE MECHANISMS
======================================================================

ONLY after strong within-system causal-state evidence exists:

Test multiple Phase 2-generated physical mechanisms.

Use:

    phi_m(x) -> z
    R_m(z,a_m)
    shared f(z,u)

Question:

    can different neuron-level mechanisms implement the same interventionally
    validated latent dynamics?

Do not start here.

Within-system causal validity comes first.

======================================================================
56. CROSS-CONNECTOME CAUSAL SHARING
======================================================================

Again only after within-system success.

Compare:

MODEL A:
independent causal states/dynamics

MODEL B:
shared dynamics, separate encoders/read-in

MODEL C:
partially shared dynamics

MODEL D:
shared latent causal model

The shared model must win on:

- held-out intervention prediction;
- mediation;
- complexity;
- transfer.

Not merely correlation.

======================================================================
57. NO CROSS-CONNECTOME CLAIM IF WITHIN-SYSTEM MEDIATION FAILS
======================================================================

Hard gate:

If causal state fails within either system:

    do NOT interpret cross-connectome alignment.

Report:

    prerequisite failed.

This prevents another pretty-but-noncausal result.

======================================================================
58. LEAVE-ONE-INTERVENTION-OUT
======================================================================

For each intervention target/family where feasible:

Train without it.

Test prediction on it.

This measures actual causal generalization.

======================================================================
59. LEAVE-ONE-IMPLEMENTATION-OUT
======================================================================

For synthetic systems sharing latent dynamics:

Train shared dynamics on implementations A/B.

Fit minimal mapping for C.

Test unseen interventions on C.

Strong result:

    shared causal dynamics transfer.

======================================================================
60. ACTIVE EXPERIMENT DESIGN BENCHMARK
======================================================================

Define budget B.

Compare methods after:

    10
    25
    50
    100
    ...
    interventions

Plot:

    causal-state score
    dimension correctness
    mediation
    intervention error

vs experiment count.

======================================================================
61. EXPERIENCE REPLAY / DATA REUSE
======================================================================

All generated public simulator trajectories should be cached.

Use content-addressed storage.

Key includes:

- system hash
- method-independent simulator version
- initial state
- parameters
- input
- intervention
- seed
- dt
- duration

Never regenerate identical trajectories.

======================================================================
62. MODAL / CLOUD POLICY
======================================================================

The user's local machine must NOT become the computational bottleneck.

Use Modal aggressively.

Keep local machine mainly for:

- orchestration
- git
- small integrity checks
- lightweight scripts.

Move heavy:

- simulation
- model training
- intervention sweeps
- active-search campaigns
- ablations
- counterexample searches
- bootstrap/statistics
- hidden evaluations

to Modal whenever scientifically permitted.

======================================================================
63. GPU POLICY
======================================================================

Phase 4 is substantially more GPU-friendly than earlier phases.

Benchmark GPUs for:

- neural SSM
- neural ODE
- representation learning
- encoder training
- Koopman neural models
- large batched trajectory training
- gradient-based counterexample search
- ensemble training

Benchmark best currently available Modal GPU classes.

Do not hard-code one class if another is faster.

Use CPU for:

- sparse system ID
- graph work
- SINDy
- linear algebra where CPU wins
- statistics
- orchestration
- lightweight simulations.

Profile.

Choose fastest scientifically identical backend.

======================================================================
64. HIGH-MEMORY MODAL
======================================================================

Use high-memory Modal CPU instances for:

- large trajectory assembly;
- real circuit simulation;
- large matrix factorization;
- large batch search.

Do not overload local RAM.

======================================================================
65. PARALLELISM
======================================================================

Parallelize independent:

- synthetic systems
- seeds
- methods
- dimensions
- hyperparameters
- intervention families
- active-design policies
- ablations
- counterexamples
- statistical resamples

Preserve all lock/blindness dependencies.

======================================================================
66. SUCCESSIVE HALVING
======================================================================

For PUBLIC method selection:

small pilot
    ->
discard weak configurations
    ->
medium evaluation
    ->
finalists
    ->
full public confirmation.

Never use hidden results for halving/tuning.

======================================================================
67. METHOD TOURNAMENT
======================================================================

Do not build one giant method first.

Tournament candidate families.

Select according to pre-registered multi-metric rule.

No single scalar leaderboard unless justified.

======================================================================
68. SELECTION PRIORITIES
======================================================================

A candidate must first satisfy:

1. intervention prediction;
2. causal mediation;
3. interventional closure.

Only then compare:

4. compression;
5. observational prediction;
6. experiment efficiency;
7. simplicity;
8. compute.

A method that predicts passive dynamics beautifully but fails interventions
cannot win.

======================================================================
69. METHOD LOCK
======================================================================

Before hidden real evaluation freeze:

- source
- architecture
- objective
- dimension rule
- training protocol
- active design policy
- intervention budget
- thresholds
- metrics
- seeds
- config
- dependency versions
- simulator version
- data manifests

Create:

    research/phase4/METHOD_LOCK.json

Suggested tag:

    brainir-causal-state-v1-preblind

No hidden evaluation before lock.

======================================================================
70. HIDDEN REAL EVALUATION
======================================================================

Run once per frozen protocol.

Hidden variables may include:

- intervention targets
- magnitudes
- timings
- initial states
- parameters
- stimulus sequences
- intervention combinations

Do not repeatedly probe hidden results.

======================================================================
71. PRIMARY REAL-WORLD-LIKE SUCCESS CRITERIA
======================================================================

The exact thresholds must be frozen statistically, not invented here.

But qualitatively Phase 4 should require:

A. intervention prediction meaningfully better than no-effect baseline;

B. better than intervention-ID shortcut where appropriate;

C. near enough to full-state upper bound;

D. positive state-mediation evidence;

E. low residual microstate dependence;

F. stable latent dimension;

G. low false-confidence rate;

H. held-out intervention-family generalization.

If these fail, causal state is unsupported.

======================================================================
72. NATIVE LIFT SUCCESS
======================================================================

For target delta_z:

measure:

- latent miss distance;
- intervention cost;
- future trajectory consistency;
- multiple-lift consistency;
- success rate;
- uncertainty.

Lift success alone does not prove causal state.

It is one required component.

======================================================================
73. ACTIVE DESIGN SUCCESS
======================================================================

Active design succeeds only if:

for same quality,
    fewer experiments

or:

for same budget,
    better causal-state recovery.

Compare CIs against random/fixed design.

======================================================================
74. OOD TESTING
======================================================================

Test:

- larger/smaller input amplitude;
- different parameter spread;
- unseen intervention timing;
- unseen intervention composition;
- altered initial condition;
- temporal sampling shift.

Record validity domain.

======================================================================
75. ROBUSTNESS
======================================================================

Evaluate:

- parameter noise;
- weight noise;
- trajectory noise;
- observation noise;
- intervention amplitude noise;
- timing jitter.

Uncertainty should increase appropriately.

======================================================================
76. CALIBRATION
======================================================================

For predicted intervention effects:

bin confidence.

Compare:

    predicted probability / confidence
    vs
    observed correctness/error.

Measure:

- Brier score where appropriate;
- calibration error;
- coverage;
- confident-wrong rate.

======================================================================
77. STATISTICS
======================================================================

Pre-register:

- experimental unit;
- resampling unit;
- CI method;
- multiplicity correction;
- paired comparisons;
- non-inferiority margins;
- minimum detectable effect if feasible.

Do not treat timesteps as independent samples.

Do not treat MANC versions as independent animals.

======================================================================
78. REVIEW A — CAUSAL REPRESENTATION
======================================================================

Ask:

- Does z actually mediate interventions?
- Is intervention read-in identifiable?
- Are shortcut models excluded?
- Are causal claims warranted?

======================================================================
79. REVIEW B — SYSTEM IDENTIFICATION / CONTROL
======================================================================

Ask:

- Are input designs persistently exciting?
- Is observability adequate?
- Is dimension identifiable?
- Is controlled dynamics model correctly specified?

======================================================================
80. REVIEW C — COMPUTATIONAL NEUROSCIENCE
======================================================================

Ask:

- Are perturbations meaningful?
- Are conclusions simulator-relative?
- Are timescales/dynamics biologically interpreted honestly?

======================================================================
81. REVIEW D — ACTIVE EXPERIMENT DESIGN
======================================================================

Ask:

- Does acquisition function actually improve information efficiency?
- Is random baseline fair?
- Is active policy overfitting synthetic families?

======================================================================
82. REVIEW E — STATISTICS
======================================================================

Ask:

- Are CIs correct?
- Are tests pre-registered?
- Are units independent?
- Is multiplicity controlled?

======================================================================
83. REVIEW F — LEAKAGE
======================================================================

Ask:

- Did Phase 3 hidden results reach Phase 4 clean agents?
- Did hidden benchmark generation leak?
- Did active design ever inspect hidden evaluator outcomes?

======================================================================
84. REVIEW G — ADVERSARIAL
======================================================================

Build NEW trap families after method composition.

Composer must not know their logic.

======================================================================
85. REVIEW H — NUMERICAL / COMPUTE
======================================================================

Check:

- solver accuracy;
- CPU/GPU equivalence;
- intervention timing;
- integration;
- caching correctness;
- reproducibility.

======================================================================
86. REVIEW I — CLAIMS
======================================================================

After hidden evaluation:

separate:

    simulator result
    methodological result
    neuroscience inference
    biological claim.

Do not blur them.

======================================================================
87. ABLATIONS
======================================================================

Ablate:

- intervention training;
- mediation loss;
- closure loss;
- active design;
- native lift;
- multiple-lift consistency;
- dimension penalty;
- history/delay;
- uncertainty ensemble;
- shared-dynamics component if used.

Measure which pieces actually matter.

======================================================================
88. THE CRITICAL ABLATION
======================================================================

Remove ALL interventional training.

This should approximately recover the Phase 3-style regime.

If interventional training does not improve causal metrics, Phase 4's core
hypothesis fails.

======================================================================
89. ANOTHER CRITICAL ABLATION
======================================================================

Train on interventions but remove the state bottleneck.

If large direct model predicts well but compact state does not:

report:

    intervention outcomes are predictable,
    but compact causal abstraction unsupported.

That distinction matters.

======================================================================
90. COUNTERFACTUAL API
======================================================================

For observed x_t and candidate intervention a:

return:

    predicted y_future under a
    uncertainty
    validity
    latent trajectory
    effect relative to no intervention.

Evaluate against simulator.

======================================================================
91. SELF-AUDIT
======================================================================

Aggressively test:

Could intervention ID alone explain results?

Could stimulus alone explain results?

Could readout history explain results?

Did future data leak?

Does latent state collapse?

Does residual microscopic state predict intervention outcomes?

Are intervention operators state-dependent?

Does lift exploit simulator quirks?

Do multiple lifts diverge later?

Does active design just choose large-effect interventions?

Does causal state fail under weak effects?

Does performance disappear on unseen intervention types?

Does k change wildly across resamples?

Does simple linear controlled model perform equally well?

Does full-state model itself fail?

Does synthetic benchmark actually resemble real response statistics?

Does method falsely find compact causal states on non-compressible systems?

Does shared dynamics fail when systems are unrelated?

Can adversarial counterexample search break the model immediately?

TEST all of these.

======================================================================
92. ACCEPTANCE CRITERIA
======================================================================

Do not declare Phase 4 complete until:

1. Phase 1 remains frozen.

2. Phase 2 remains frozen.

3. Phase 3 final artifacts remain unchanged.

4. Phase 4 clean room exists.

5. PHASE3_REPORT.md is excluded.

6. hidden Phase 3 results are excluded.

7. new benchmark is frozen before development.

8. synthetic suite has known causal state.

9. synthetic suite contains causal traps.

10. synthetic suite has non-compressible controls.

11. synthetic calibration matches permitted real summary statistics.

12. intervention API exists.

13. held-out intervention families exist.

14. full-state upper bound exists.

15. intervention-only shortcut baseline exists.

16. input-only shortcut baseline exists.

17. Phase 3 model is frozen baseline.

18. controlled linear baseline exists.

19. strong nonlinear baseline exists.

20. iSSM-like candidate is evaluated.

21. multiple candidate families are tournamented.

22. latent dimension is selected generically.

23. intervention read-in is explicit.

24. state mediation is measured.

25. interventional closure is measured.

26. microstate equivalence under intervention is measured.

27. native lift exists.

28. multiple lifts are tested.

29. active experiment design exists.

30. active design beats or is honestly compared to random/fixed design.

31. experiment-efficiency curves exist.

32. counterexample search exists.

33. adversarial traps are evaluated.

34. held-out intervention-type generalization is measured.

35. robustness is measured.

36. calibration is measured.

37. abstention is measured.

38. important ablations are complete.

39. CPU/GPU equivalence tests pass where applicable.

40. local machine is not required for heavy compute unless scientifically necessary.

41. Modal costs are recorded.

42. all previous tests remain green.

43. Phase 4 tests remain green.

44. reviews A–I are complete.

45. blockers fixed before lock.

46. method lock exists.

47. hidden evaluation occurs after lock.

48. hidden attempts are logged.

49. no silent post-hidden tuning occurs.

50. PHASE4_REPORT.md exists.

51. final conclusion is one of:

    compact causal state supported;
    partially supported;
    unsupported.

All three are acceptable.

======================================================================
93. STRONG SUCCESS CONDITION
======================================================================

The strongest desired result is:

A compact k-dimensional state model:

- nearly matches full-state intervention prediction;
- beats no-effect and shortcut baselines;
- generalizes to unseen intervention classes;
- mediates intervention effects;
- has little residual microscopic dependence;
- supports multiple equivalent low-level lifts;
- is stable across seeds/resamples;
- can be discovered with fewer experiments using active design;
- and, only if supported, transfers as shared dynamics across physical
  mechanisms/connectomes.

Do NOT lower this bar after seeing results.

======================================================================
94. IF PHASE 4 FAILS
======================================================================

Do not hide it.

Determine WHY.

Possible outcomes:

A. full state predicts interventions, compact state cannot
   -> abstraction problem.

B. even full state cannot predict
   -> simulator/data/excitation problem.

C. random active design performs equally well
   -> experiment-design component unnecessary.

D. simple DMDc wins
   -> use the simple model.

E. compact state works on synthetic but not real
   -> distribution/model mismatch.

F. intervention effect requires high-dimensional state
   -> report high-dimensional causal dynamics.

G. intervention operators are not invariant
   -> causal state definition needs revision.

Each is scientifically informative.

======================================================================
95. PHASE 4 REPORT
======================================================================

Create:

    PHASE4_REPORT.md

Mark it answer-bearing if it contains hidden results.

Include:

- benchmark construction;
- clean room;
- leakage audit;
- synthetic suite;
- methods review;
- candidate tournament;
- final algorithm;
- active design;
- intervention read-in;
- mediation;
- interventional closure;
- dimension;
- lift;
- multiple lifts;
- hidden intervention generalization;
- full-state comparison;
- shortcut baselines;
- counterexamples;
- robustness;
- calibration;
- ablations;
- cross-mechanism/cross-connectome only if prerequisite passes;
- statistics;
- compute;
- Modal usage;
- reviews;
- failures;
- one next-phase recommendation.

======================================================================
96. CLAIM LANGUAGE
======================================================================

Do not say:

    "BrainIR discovered the true causal state of the fly brain."

Prefer:

    "Within the tested connectome-constrained dynamical model and
     intervention domain, the learned k-dimensional state mediated
     held-out intervention effects with X performance relative to
     specified baselines."

Do not make biological claims unsupported by simulator-only evidence.

======================================================================
97. COMPUTE / SPEED DIRECTIVE
======================================================================

The user cares much more about wall-clock time than Modal cost.

Use more Modal compute if it reduces waiting.

Do not reduce scientific work.

Use:

- high-memory CPU containers;
- high-concurrency CPU workers;
- strong GPUs for GPU-native ML;
- persistent volumes;
- prebuilt images;
- caching;
- batching;
- parallel method sweeps;
- parallel seeds;
- parallel reviewers.

Benchmark representative workloads.

Use the fastest scientifically equivalent backend.

Do not force GPU usage when CPU wins.

======================================================================
98. AUTONOMY
======================================================================

The user is not your operator.

Do all routine work yourself.

Use:

- shell;
- browser;
- web research;
- Python;
- uv;
- git;
- Docker;
- Modal;
- CPUs;
- GPUs;
- agents;
- independent reviewers;
- profiling;
- debugging;
- papers.

Do not ask the user to:

- run commands;
- upload ordinary project data;
- choose methods;
- choose hardware;
- babysit jobs.

Only stop for unavoidable:

- login;
- 2FA;
- CAPTCHA;
- inaccessible permission;
- irreversible unrelated destructive action.

======================================================================
99. FINAL RESPONSE
======================================================================

At completion return a concise report containing:

- Phase 4 status;
- clean-room status;
- final method;
- latent dimension(s);
- synthetic causal-state recovery;
- real intervention prediction;
- full-state upper bound;
- no-effect baseline;
- intervention shortcut baseline;
- state mediation;
- interventional closure;
- native lift;
- multiple-lift consistency;
- held-out intervention-family result;
- active design efficiency;
- strongest baseline;
- where BrainIR wins/matches/loses;
- counterexample result;
- robustness;
- abstention/calibration;
- tests;
- reviews;
- Modal cost;
- method lock/tag;
- biggest limitation;
- ONE recommended next phase.

DO NOT START PHASE 5.

======================================================================
100. THE PHASE 4 NORTH STAR
======================================================================

Phase 3 asked:

    Can a small state predict what the circuit will do?

Phase 4 asks the harder question:

    Does that small state still tell us what the circuit will do
    when we deliberately change the circuit?

And even more importantly:

    Does the EFFECT of the intervention actually pass through that state?

If yes, we have something much closer to a computational state.

If not, we do not yet understand the computation.

That is the entire point of Phase 4.