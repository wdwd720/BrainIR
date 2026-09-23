# BrainIR Phase 2 — Blind Causal Mechanism Discovery v1

You are taking full scientific, mathematical, ML, systems, and operational ownership of Phase 2 of BrainIR.

Repository:
C:\Dev\BrainIR

Frozen benchmark:
dng100-benchmark-v1

Frozen benchmark commit:
a7c0142

Phase 1 benchmark tag:
dng100-benchmark-v1

Phase 2 has NOT yet started.

======================================================================
0. READ THIS FIRST — WHAT PHASE 2 ACTUALLY IS
======================================================================

BrainIR's eventual goal is:

    biological neural circuit
            ↓
    automatically discovered compact mechanism
            ↓
    executable symbolic program
            ↓
    causal validation
            ↓
    formal/counterexample-driven verification
            ↓
    cross-brain invariant algorithm

We are NOT building all of that in Phase 2.

Phase 2 is the first actual discovery phase.

The goal is to build the first algorithm that receives ONLY the frozen public DNg100 benchmark evidence and independently discovers a compact, causal, cross-connectome mechanism WITHOUT receiving the hidden published answer.

This is the foundation that later symbolic decompilation will sit on.

The Phase 2 question is:

    Can BrainIR discover the small causal mechanism responsible for the
    observed computation more efficiently, reliably, robustly, and
    generally than ordinary simulation-guided greedy pruning?

The benchmark is already difficult in an important way:

Phase 1 showed that a generic simulation-guided greedy elimination baseline can recover the published structural core in 2 of 3 tested networks.

Therefore:

    "BrainIR found E1/E2/etc."

IS NOT SUFFICIENT.

Phase 2 must demonstrate an actual methodological advantage.

The required dimensions include:

- reliability across node orderings / random seeds
- simulator-query efficiency
- mechanism quality
- robustness to model uncertainty
- cross-connectome transfer
- minimality
- causal faithfulness
- uncertainty calibration where possible

Do not optimize only for exact structural answer recovery.

======================================================================
1. FIRST ACTIONS
======================================================================

Before modifying anything, read and inspect the repository.

At minimum inspect:

1. CLAUDE.md
2. PHASE0_REPORT.md
3. PHASE1_REPORT.md
4. benchmarks/dng100/PROTOCOL.md
5. benchmarks/dng100/BENCHMARK_LOCK.json
6. benchmarks/dng100/LEAKAGE_AUDIT.md
7. benchmarks/dng100_walking_cpg/SPEC.md if still relevant
8. experiment registry
9. Phase 1 audit reports
10. current test suite
11. current benchmark/public API
12. prediction schema
13. baseline implementations
14. Modal integration
15. git log/status/tags

Then:

- verify the working tree is clean;
- verify the benchmark lock;
- rerun the critical benchmark integrity checks;
- confirm all tests still pass;
- confirm the frozen benchmark has not changed.

DO NOT MODIFY ANY FILE COVERED BY THE FROZEN BENCHMARK LOCK.

The benchmark is immutable.

If Phase 2 requires new functionality, implement it outside the frozen benchmark.

======================================================================
2. OPERATING MODE
======================================================================

The user is NOT your operator.

YOU are the operator.

Do essentially all work yourself.

You may:

- inspect the computer
- inspect the repository
- use shell/PowerShell
- write and edit source code
- install dependencies
- create environments
- browse the web
- research current literature
- read papers
- use APIs
- run simulations
- run tests
- debug
- use Modal
- use cloud CPUs/GPUs
- spawn parallel agents if available
- use Claude in Chrome
- create temporary clean-room environments
- profile code
- perform large parameter sweeps
- run statistical analyses
- refactor implementations
- create experiment registries
- run independent reviews

Do not ask the user to manually perform routine work.

Do not ask the user to run commands.

Do not ask the user to download files.

Do not ask the user what implementation to choose when you can investigate it yourself.

Only stop for genuine unavoidable human interaction such as:

- login / 2FA
- CAPTCHA
- inaccessible browser/OS permission
- irreversible action involving unrelated user data

Complete all independent work before asking for such an action.

======================================================================
3. SPEED + COMPUTE POLICY
======================================================================

The user has roughly $960 of Modal compute remaining.

Use cloud compute aggressively when it meaningfully reduces wall-clock time.

Phase 2 should be rigorous but fast.

Parallelize independent work such as:

- synthetic benchmark generation
- candidate algorithm testing
- parameter sweeps
- node-order experiments
- uncertainty ensembles
- baseline reruns
- null experiments
- cross-connectome trials
- bootstrap evaluation
- ablations

Use GPUs if an algorithm benefits from them.

Do not spend hours waiting on the local AMD machine for a task that Modal can parallelize efficiently.

However:

- do not burn compute pointlessly;
- cache reusable simulations;
- deduplicate identical jobs;
- terminate unused jobs;
- record approximate cost;
- use local execution for small tests.

Optimize for:

    scientific quality
    +
    wall-clock speed
    +
    reproducibility

not minimal cloud spend.

======================================================================
4. CRITICAL ANTI-LEAKAGE RULE
======================================================================

Phase 2 must be treated as a blind mechanism-discovery experiment.

The known DNg100 circuit identities and published answer MUST NOT be used to design or tune the discovery algorithm.

There is an unavoidable complication:

Previous repository work and high-level reports may already have exposed some biological names to the orchestration environment.

Therefore compensate operationally.

The actual discovery-method development must be benchmark-generic.

Do NOT:

- add special cases for DNg100
- encode E1/E2/I1/I2 names
- use published circuit identities
- use exact oracle neuron IDs
- use known answer-specific synapse counts
- hard-code number of expected neurons
- tune thresholds to maximize hidden oracle recovery
- use oracle files to debug discovery
- use oracle identities in unit tests
- use known circuit topology as a prior
- inspect hidden oracle during algorithm development

Ideally create an isolated Phase 2 development environment containing ONLY:

- generic BrainIR library code
- frozen public benchmark bundle
- synthetic benchmarks
- generic methodological literature/resources

Do NOT mount:

- oracle
- hidden-answer notes
- evaluator internals that reveal target identity
- previous hidden evaluation artifacts

If fresh isolated agents/sessions are available, strongly prefer using them for method implementation.

The implementation agent should receive a generic mechanism-discovery objective, not the hidden DNg100 result.

The main orchestration process may manage infrastructure but must not inject hidden biological information into algorithm design.

======================================================================
5. LITERATURE REVIEW — METHODS ONLY
======================================================================

Before choosing the algorithm, perform a targeted current literature review.

Research GENERAL methods relevant to:

- active causal discovery
- optimal experiment design
- black-box intervention selection
- sparse dynamical system identification
- differentiable network pruning
- combinatorial subset selection
- sparse causal mechanism discovery
- Bayesian experimental design
- cross-environment invariant mechanism learning
- graph intervention optimization
- neural circuit discovery
- symbolic/sparse model discovery
- submodular optimization
- cross-entropy method
- Gumbel-Softmax / Concrete distributions
- straight-through binary mask optimization
- Bayesian optimization over structured discrete spaces
- CMA-ES / evolutionary search
- sequential model-based optimization
- active learning under expensive simulators
- mechanistic interpretability circuit discovery
- causal representation learning
- network controllability where relevant

Focus on methodological ideas.

During Phase 2 algorithm design, do NOT search for:

    "what are the important DNg100 neurons?"

or equivalent answer-leaking queries.

Maintain a Phase 2 methods research note containing:

- paper
- method
- assumptions
- complexity
- relevance
- limitations
- whether our simulator supports it
- whether it can operate under a strict query budget

Use primary sources where practical.

======================================================================
6. DO NOT COMMIT TO ONE ALGORITHM IMMEDIATELY
======================================================================

The biggest mistake would be deciding upfront:

    "we will use Gumbel masks"

or:

    "we will use Bayesian optimization"

without experimentation.

Treat algorithm selection scientifically.

Build a small method-development tournament on synthetic circuits FIRST.

Evaluate several plausible families.

Candidate families worth investigating include:

A. Improved simulation-guided pruning

Use it as a reference, not necessarily the final BrainIR method.

B. Continuous sparse gating

Learn node/edge gates:

    g_i ∈ [0,1]

with objectives such as:

    functional fidelity
    +
    sparsity
    +
    robustness

then project to a discrete circuit.

Possible tools:

- Concrete distributions
- Gumbel-Softmax
- hard-concrete / L0 regularization
- straight-through estimators

ONLY if the simulator or a surrogate supports useful gradients.

C. Cross-Entropy Method / population-based discrete search

Maintain a probability distribution over neuron inclusion.

Sample candidate mechanisms.

Evaluate them.

Update inclusion probabilities toward successful mechanisms.

Potentially very parallelizable.

D. Evolutionary structured search

Search candidate neuron/edge subsets using:

- mutation
- crossover
- pruning
- add-back

while optimizing multiobjective fitness.

E. Surrogate-assisted mechanism search

Learn:

    candidate subset/intervention
        →
    expected functional score

from previous expensive simulations.

Then use the surrogate to propose informative candidates.

F. Bayesian optimization over structured intervention/subset spaces

Only if representation and scaling make sense.

G. Active causal discovery

Rather than repeatedly evaluating entire subsets, design interventions that maximally reduce uncertainty about which neurons/edges are causally necessary.

H. Hybrid approach

Likely strongest:

    graph prior
        +
    active causal probes
        +
    probabilistic sparse mask
        +
    robust optimization
        +
    discrete minimality cleanup

Do not assume the hybrid is better.

Test it.

======================================================================
7. SYNTHETIC MECHANISM-DISCOVERY SUITE
======================================================================

Before touching hidden biological evaluation, build a substantially stronger synthetic suite.

This is crucial because here we know the real source mechanism.

Generate circuits from known hidden mechanisms including at least:

- recurrent oscillator
- delayed inhibitory oscillator
- excitatory-inhibitory feedback oscillator
- redundant oscillator
- two interchangeable implementations of the same oscillator
- integrator
- leaky integrator
- comparator
- winner-take-all
- gated memory
- bistable switch
- feed-forward controller
- negative feedback controller
- motif with distractor high-degree neurons
- motif embedded in large random recurrent graph
- motif with redundant backup neurons
- motif with misleading centrality
- mechanism whose critical edge is weak
- mechanism whose critical neuron has low degree
- multiple distinct physical implementations of the same abstract computation

Create families at multiple sizes.

For example:

small:
    20–100 neurons

medium:
    100–1,000

larger:
    1,000–5,000 where practical

Embed hidden mechanisms in increasingly distracting graphs.

Add realistic complications:

- noisy weights
- uncertain signs where appropriate
- irrelevant strong edges
- weak critical edges
- redundant neurons
- irrelevant recurrent modules
- parameter uncertainty
- multiple initial conditions
- different graph realizations implementing the same mechanism

Store ground truth separately from public synthetic inputs.

The discovery algorithm should not receive ground truth.

======================================================================
8. DEFINE THE PHASE 2 DISCOVERY PROBLEM MATHEMATICALLY
======================================================================

Formalize the method before implementation.

We have a network:

    G = (V, E)

with simulator:

    y = F(G, θ, u, I)

where:

    θ = uncertain dynamical parameters
    u = external input/stimulus
    I = intervention
    y = neural/behavioral output

We seek a mechanism:

    M ⊆ G

that is:

1. sufficient to preserve the target computation;
2. causally necessary or near-necessary where appropriate;
3. compact;
4. robust across plausible θ;
5. stable across random seeds/node orders;
6. transferable across connectomes where an equivalent mechanism exists.

One generic objective may resemble:

    J(M) =
        L_function(M)
        + λ_size * C(M)
        + λ_robust * R(M)
        + λ_transfer * T(M)
        + λ_uncertainty * U(M)

but do not blindly implement this exact formula.

Derive the objective carefully.

Keep individual components observable.

Never hide all scientific behavior inside one scalar.

======================================================================
9. MODEL THE PROBLEM AS UNCERTAINTY, NOT ONE ANSWER
======================================================================

A major weakness of greedy pruning is that it often produces one result dependent on:

- deletion order
- seed
- parameter setting
- numerical noise

BrainIR should instead maintain uncertainty over candidate mechanisms.

For example:

    p(z_i = 1 | data)

where:

    z_i = whether neuron i belongs to the causal mechanism

and possibly:

    p(r_i = role | data)

for functional role.

The output should ideally include:

- inclusion probability
- role probability
- confidence
- alternative mechanisms
- uncertainty remaining

This provides a natural advantage over greedy elimination.

If multiple functionally equivalent mechanisms exist, preserve that ambiguity instead of forcing a single arbitrary answer.

======================================================================
10. ACTIVE CAUSAL PROBING
======================================================================

A central Phase 2 hypothesis worth testing is:

    BrainIR can discover mechanisms using fewer simulations by choosing
    interventions that maximally reduce uncertainty rather than greedily
    deleting neurons one at a time.

Develop a formal acquisition strategy.

At each step, we have candidate hypotheses H.

Choose intervention I maximizing something like:

    expected information gain

or another justified acquisition function:

    I* = argmax_I E[ H_before - H_after ]

Possible interventions:

- silence one neuron
- silence a group
- activate one neuron
- perturb an edge if simulator supports it
- group knockouts
- structured partitions
- adaptive binary splitting

Do not automatically default to single-neuron interventions.

Group testing may dramatically reduce the number of simulations.

For example, if 1,000 neurons remain uncertain, intelligently designed group interventions may identify causal subsets much faster than 1,000 individual deletions.

Investigate this deeply.

======================================================================
11. CONSIDER COMPRESSIVE / GROUP-TESTING IDEAS
======================================================================

This may be a major algorithmic opportunity.

Mechanism discovery can be viewed partly as sparse recovery.

Suppose only k neurons among N are truly important.

Instead of N individual perturbations, test structured groups:

    intervention 1: subset A
    intervention 2: subset B
    intervention 3: subset C
    ...

Infer causal membership from changes in functional output.

Explore connections to:

- compressed sensing
- group testing
- adaptive group testing
- sparse recovery
- experimental design

However:

The simulator response is nonlinear.

Do not assume classical linear compressed sensing theory directly applies.

Test whether adapted group-testing strategies meaningfully reduce simulation count.

This could become one of the strongest Phase 2 contributions if it works.

======================================================================
12. GRAPH STRUCTURE AS A PRIOR, NOT AN ANSWER
======================================================================

Use anatomy intelligently.

Potential structural priors:

- input-to-output causal cone
- directed reachability
- recurrent components
- signed cycles
- feedback motifs
- edge strength
- neuropil locality
- cell-type grouping
- paths between known benchmark inputs and allowed outputs

But anatomy must remain a PRIOR.

Do not conclude:

    high degree = causal

or:

    strong edge = important.

Phase 1 already showed simple structural heuristics perform poorly.

BrainIR should combine:

    structure
    +
    causal intervention evidence
    +
    dynamics.

======================================================================
13. ROBUST DISCOVERY OBJECTIVE
======================================================================

Do not discover a circuit that works only at the exact frozen nominal parameter setting.

Let Θ represent the allowed uncertainty ensemble from Phase 1.

Evaluate candidate M across:

    θ₁, θ₂, ..., θK

and relevant seeds/initial states.

Potential robust objective:

    Eθ[L(M, θ)]
        +
    β * CVaRα(L(M, θ))

or another justified risk-sensitive criterion.

The mechanism should preserve the target behavior over the biologically/model-plausible region, not merely exploit one parameterization.

Track:

- mean performance
- worst-tail performance
- variance
- failure probability

======================================================================
14. MULTIOBJECTIVE OPTIMIZATION
======================================================================

Avoid collapsing everything prematurely.

Mechanisms have multiple objectives:

- fidelity
- size
- robustness
- query budget
- cross-connectome transfer

Maintain a Pareto frontier where practical.

For example:

    Circuit A:
        3 neurons
        91% robust fidelity
        2,000 simulator calls

    Circuit B:
        5 neurons
        99% robust fidelity
        500 simulator calls

Both may be scientifically interesting.

Do not force arbitrary scalar weighting early.

======================================================================
15. MINIMALITY
======================================================================

Once a candidate mechanism M is discovered, test minimality.

For every neuron v ∈ M:

    evaluate M \ {v}

For relevant edges e ∈ M:

    evaluate M \ {e}

Determine:

- necessary components
- redundant components
- interchangeable components
- robustness-enhancing components

Also perform add-back tests where useful.

Report:

    causal core
    supporting components
    redundant alternatives

Do not simply output a minimal set created by search order.

======================================================================
16. FUNCTIONAL ROLE DISCOVERY
======================================================================

Phase 2 should begin moving beyond:

    "these neurons matter."

Attempt to infer roles WITHOUT using hidden biological labels.

Possible generic roles:

- input relay
- recurrent excitatory core
- inhibitory feedback
- gain control
- state memory
- output driver
- redundant backup
- modulatory/supporting

Infer roles from:

- directed connectivity
- sign
- intervention effects
- temporal activity
- causal ordering
- recurrence
- response latency
- ablation signatures

Do not force every neuron into a role.

Allow:

    role = unknown

if evidence is insufficient.

Output role uncertainty.

======================================================================
17. CROSS-CONNECTOME SHARED MECHANISM DISCOVERY
======================================================================

This is one of the central BrainIR ideas.

Suppose:

    G_A = MaleCNS
    G_B = MANC

Physical neurons differ.

But we want to identify a shared abstract mechanism.

Do not simply run the algorithm independently twice and compare names afterward.

Test whether joint discovery improves reliability.

Conceptually:

    shared roles R
        ↑            ↑
      φ_A          φ_B
        ↑            ↑
    MaleCNS       MANC

Learn dataset-specific neuron assignments φ while encouraging a shared role structure.

Possible objective:

    Σ_d L_function(M_d)
    + λ_shared * L_role_alignment
    + λ_size * Σ_d |M_d|

Do not force exact structural identity.

The benchmark already indicates implementation details can differ.

Allow:

    same abstract role
    ≠
    same exact neuron identity.

======================================================================
18. TRANSFER EXPERIMENTS
======================================================================

Perform at least these conceptual tests if permitted by the frozen protocol:

A. Discover on MaleCNS.
   Transfer inferred mechanism/roles to MANC.

B. Discover on MANC.
   Transfer to MaleCNS.

C. Joint discovery.
   Compare against independent discovery.

D. Cross-connectome prior only.
   Determine whether shared structure reduces simulator calls.

Do not retrain/tune on the destination in a way that turns transfer into another full discovery run.

Track the adaptation budget separately.

======================================================================
19. STRICT QUERY-BUDGET ACCOUNTING
======================================================================

The simulator is effectively our expensive experimental oracle.

Count every meaningful simulator query.

Record:

    simulator_calls
    total simulated biological time
    total candidate mechanisms evaluated
    number of interventions
    CPU/GPU time
    wall-clock time
    Modal cost

The algorithm should not "beat greedy" by using 100× more simulation.

Produce performance curves:

    mechanism quality
        vs
    simulator calls

not merely final quality.

Examples:

    100 calls
    250
    500
    1k
    2k
    5k

adapt based on actual scale.

Compute area-under-budget curves where meaningful.

======================================================================
20. FAIR BASELINE COMPARISON
======================================================================

Use the frozen Phase 1 baseline implementation.

Do not weaken it.

In particular compare against:

    greedy_prune_sim

under matched:

- simulator
- uncertainty configuration
- functional criterion
- computational budget where possible
- datasets
- random seeds
- node orderings

Also retain structural/random baselines for context.

Use paired experiments.

Do not compare one lucky BrainIR run to an average baseline.

======================================================================
21. RELIABILITY EXPERIMENTS
======================================================================

Phase 1 identified node-order sensitivity as a major weakness.

Run enough independent orderings/seeds to estimate:

- success probability
- mechanism size distribution
- identity consistency
- role consistency
- functional fidelity distribution
- simulation budget distribution

Use confidence intervals.

Do not pick an arbitrary sample count without checking statistical stability.

Parallelize these heavily on Modal.

======================================================================
22. SYNTHETIC METHOD SELECTION
======================================================================

The first algorithm selection should occur WITHOUT hidden biological scoring.

For each candidate algorithm family, measure synthetic:

- structural recovery
- role recovery
- functional fidelity
- intervention prediction
- query efficiency
- robustness
- cross-instance transfer
- scaling behavior

Do not select the method solely because it performs best on one oscillator family.

Use multiple mechanism families.

Choose the Phase 2 BrainIR method based on:

    broad synthetic performance
    +
    benchmark-generic reasoning
    +
    computational feasibility.

Document rejected algorithms and why.

======================================================================
23. SURROGATE MODELS IF USEFUL
======================================================================

If simulator evaluations dominate cost, investigate learning a surrogate:

    S(M, I, θ)
        ≈
    simulator outcome

Possible models:

- gradient-boosted trees
- graph neural network
- set transformer
- neural surrogate
- Gaussian process where dimension permits

But guard against surrogate exploitation.

Candidate mechanisms optimized against S must periodically be validated on the true simulator.

Track surrogate error.

Never report surrogate performance as biological simulator performance.

======================================================================
24. IF THE SIMULATOR IS DIFFERENTIABLE
======================================================================

Inspect the simulator implementation.

If useful gradients are available, test differentiable sparse-mask methods.

If not, do NOT spend days forcing differentiability into the system just because it sounds advanced.

A black-box algorithm may be superior.

If implementing a differentiable approximation:

- validate it against the authoritative simulator;
- quantify approximation error;
- use the true simulator for final scoring.

======================================================================
25. METHOD ARCHITECTURE
======================================================================

Design a generic discovery API.

Conceptually:

    discover(
        public_benchmark,
        budget,
        seed,
        config
    ) -> BrainIRMechanismPrediction

A method should NOT receive:

- oracle
- hidden answer
- evaluation result internals

Potential package structure:

src/brainir/discovery/
    interface.py
    candidate_space.py
    interventions.py
    causal_effects.py
    active_search.py
    sparse_masks.py
    group_testing.py
    robust_objective.py
    roles.py
    minimality.py
    transfer.py
    uncertainty.py

src/brainir/methods/
    greedy_reference/
    brainir_v1/

Adapt to the existing architecture.

Avoid architecture astronautics.

======================================================================
26. BRAINIR V1 SHOULD BE A REAL METHOD, NOT A BAG OF HEURISTICS
======================================================================

By the end of Phase 2, BrainIR v1 should have a coherent algorithmic description.

For example — only as an illustration, NOT a mandated design:

1. restrict candidate graph using legal public structural information;
2. initialize inclusion probabilities;
3. run structured group interventions;
4. infer posterior causal importance;
5. optimize sparse robust candidate masks;
6. validate candidates on true simulator;
7. remove unnecessary components;
8. infer functional roles;
9. align roles across connectomes;
10. produce uncertainty-aware prediction.

If this or another method emerges as best, write it mathematically.

A future paper reader should be able to understand the algorithm without reading the code.

======================================================================
27. METHOD LOCK BEFORE HIDDEN EVALUATION
======================================================================

This is mandatory.

Before the first hidden-oracle evaluation:

- all algorithm code must be committed;
- configuration must be frozen;
- hyperparameters must be frozen;
- synthetic evaluation must be complete;
- public-only tests must pass;
- method documentation must exist;
- method hash must be recorded.

Create something conceptually like:

    METHOD_LOCK.json

containing:

- git commit
- source hashes
- config hash
- package versions
- synthetic results
- benchmark public bundle hash
- random seeds or seed policy
- compute budget
- expected output schema

Tag it, e.g.:

    brainir-v1-preblind

Do not modify that method after seeing its hidden evaluation and still call it the same version.

======================================================================
28. BLIND EVALUATION
======================================================================

Run BrainIR v1 through the frozen clean-room protocol.

The discovery environment receives only:

- public bundle
- BrainIR v1 method
- allowed generic dependencies

It emits:

    prediction.json

Then evaluate against the frozen hidden oracle OUTSIDE the discovery environment.

Preserve:

- prediction
- logs
- method commit
- benchmark hash
- compute usage
- evaluation output

The discovery environment should not get the oracle afterward.

======================================================================
29. AVOID ITERATIVE ORACLE OVERFITTING
======================================================================

Do not repeatedly:

    evaluate hidden oracle
    inspect exact failure
    tweak algorithm
    reevaluate
    repeat

That would undermine the point of freezing Phase 1.

If BrainIR v1 fails:

- preserve the result;
- diagnose using PUBLIC behavior, synthetic failures, generic method analysis;
- do not inspect hidden target identities to fix it.

If a BrainIR v2 is developed in Phase 2, treat it as a separate preregistered method with another lock.

Keep the number of hidden evaluation attempts minimal and explicitly logged.

Follow the frozen PROTOCOL.md exactly where it already defines these rules.

======================================================================
30. STATISTICAL ANALYSIS
======================================================================

For each meaningful comparison, report uncertainty.

Use appropriate methods such as:

- bootstrap confidence intervals
- paired tests
- permutation tests
- empirical success intervals
- effect sizes

Do not report:

    BrainIR = 0.93
    Greedy = 0.91

and call that meaningful without variability.

Reliability itself is one of the primary outcomes.

======================================================================
31. KEY PHASE 2 METRICS
======================================================================

Keep individual metrics visible.

At minimum consider:

DISCOVERY
- neuron recall
- neuron precision
- role recovery
- edge/motif recovery where appropriate

FUNCTION
- nominal functional fidelity
- robust functional fidelity
- intervention fidelity

EFFICIENCY
- simulator calls
- biological time simulated
- wall-clock
- cloud cost

RELIABILITY
- success rate across seeds
- success rate across node orderings
- variance in mechanism size
- variance in discovered identity

MINIMALITY
- removable nodes
- removable edges
- causal core size

TRANSFER
- MaleCNS → MANC
- MANC → MaleCNS
- joint mechanism consistency

UNCERTAINTY
- inclusion calibration
- confidence vs correctness if measurable

Do not reduce Phase 2 to one score.

======================================================================
32. IMPORTANT SUCCESS CONDITION
======================================================================

BrainIR v1 should NOT be declared superior merely because it obtains slightly higher exact-oracle recall.

A strong result would look more like:

    Greedy:
        success 67%
        8,000 simulator calls
        high node-order sensitivity
        no uncertainty
        weak transfer

    BrainIR:
        success 95%
        1,500 simulator calls
        low variance
        calibrated inclusion probabilities
        strong transfer

Numbers above are illustrative only.

Do not target/fabricate them.

The key is meaningful Pareto improvement.

======================================================================
33. DO NOT GAME THE BENCHMARK
======================================================================

Explicitly test for benchmark exploitation.

For the final method ask:

Does it still work when:

- neuron ordering changes?
- source IDs are randomly permuted?
- irrelevant annotations are removed?
- irrelevant distractor neurons are added?
- graph representation order changes?
- seeds change?
- parameter ensemble changes?
- source dataset changes?
- synthetic circuit family changes?

If performance collapses under meaningless representation changes, fix the method.

======================================================================
34. CROSS-CONNECTOME INVARIANCE AS A CORE TEST
======================================================================

A major BrainIR hypothesis is:

    computation can remain conserved even when physical implementation varies.

Therefore reward methods that recover role-level invariants.

Represent mechanisms at two levels:

PHYSICAL:
    exact neurons and edges

ABSTRACT:
    functional roles and interactions

For example:

    role A → role B
    role B → inhibitory feedback
    feedback ┤ role A/B

Do not put the known answer into this template.

The abstract role graph must be inferred.

Then test whether equivalent role graphs appear across MaleCNS and MANC.

======================================================================
35. MECHANISM PREDICTION OUTPUT
======================================================================

Use the frozen Phase 1 prediction schema.

If extensions are absolutely necessary, do not modify the frozen benchmark schema in place.

Create a backward-compatible Phase 2 extension outside the frozen artifact.

Prediction should include as much of the following as the existing schema permits:

- selected neurons
- selected edges
- inclusion confidence
- inferred roles
- role confidence
- recurrence structure
- predicted sign interactions
- intervention predictions
- alternative mechanisms
- robustness
- cross-connectome correspondence

Do not include an English explanation as the main scientific result.

Structured mechanism first.

English explanation may be generated secondarily.

======================================================================
36. MINIMUM-DESCRIPTION-LENGTH PRINCIPLE
======================================================================

We ultimately want decompilation.

Phase 2 should therefore prefer compact causal explanations.

Explore an MDL-style penalty:

    description length of mechanism
        +
    residual functional error

But compactness must not destroy causally relevant structure.

Track the tradeoff.

This prepares us for later symbolic-program synthesis.

======================================================================
37. INTERVENTION PREDICTION
======================================================================

BrainIR should not only select a circuit.

It should predict consequences of perturbing its discovered components.

For discovered candidate neuron v:

    predicted effect of silence(v)
    predicted effect of activate(v) where defined

For candidate edge e:

    predicted effect of remove(e) where supported

Evaluate on allowed held-out perturbations.

This is much stronger than graph recovery.

======================================================================
38. BUILD A CAUSAL EFFECT CACHE
======================================================================

If many algorithms repeatedly query identical interventions, cache them safely.

Key cache entries by:

- dataset manifest
- simulator version
- parameters
- intervention
- seed
- input protocol

Use content hashes.

Do not accidentally reuse an outcome from the wrong parameter ensemble.

This can save substantial compute.

======================================================================
39. MODAL EXECUTION
======================================================================

Make Phase 2 experiments easy to distribute.

Ideal conceptual commands:

    brainir discovery synthetic --method brainir_v1

    brainir discovery dng100 \
        --method brainir_v1 \
        --budget 1000 \
        --backend modal

    brainir discovery sweep \
        --method brainir_v1 \
        --seeds ... \
        --backend modal

    brainir discovery transfer \
        --source malecns \
        --target manc

Exact CLI design is your decision.

Use batched Modal jobs rather than enormous numbers of tiny high-overhead jobs when practical.

Record cost.

======================================================================
40. PERFORMANCE PROFILING
======================================================================

Measure:

- simulator latency
- batch throughput
- intervention generation time
- candidate evaluation time
- surrogate inference time if used
- graph preprocessing time
- Modal overhead

Do not prematurely rewrite the simulator.

If the bottleneck is Python overhead, optimize it.

If the bottleneck is simulator math, vectorize/batch.

If GPU helps, use GPU.

If CPU parallelism is superior, use CPU.

Measure before deciding.

======================================================================
41. ABLATIONS
======================================================================

Once BrainIR v1 exists, remove components one at a time.

Examples:

BrainIR without:
- active experiment selection
- group testing
- graph prior
- robustness objective
- uncertainty model
- cross-connectome term
- minimality cleanup
- surrogate

Only test components that actually exist.

Measure what each contributes.

If a fancy component does nothing, remove it.

======================================================================
42. FAILURE ANALYSIS
======================================================================

For failed synthetic or public experiments, classify causes.

Possible categories:

- candidate pool omitted critical node
- acquisition strategy failed
- nonlinear interaction hidden from marginal interventions
- redundant mechanism ambiguity
- surrogate error
- optimizer local minimum
- insufficient budget
- robustness objective too conservative
- cross-connectome misalignment
- numerical instability

Do not patch each failure with circuit-specific rules.

Fix general weaknesses.

======================================================================
43. REPRODUCIBILITY
======================================================================

Every experiment must record:

- experiment ID
- timestamp
- git commit
- method version/hash
- benchmark public hash
- dataset manifest
- simulator version
- config
- seeds
- backend
- Modal job ID where applicable
- runtime
- simulator call count
- cost
- result path

Phase 1 experiment-registry conventions should be reused.

======================================================================
44. TESTING
======================================================================

Add comprehensive tests for Phase 2.

At minimum cover:

DISCOVERY INTERFACE
- public-only input
- deterministic seed behavior
- prediction schema validity

CANDIDATE SPACE
- graph filtering
- no oracle dependency

INTERVENTIONS
- correct application
- grouping
- caching

SYNTHETIC CIRCUITS
- known mechanisms recoverable
- distractor robustness

UNCERTAINTY
- probability normalization
- reproducibility

MINIMALITY
- removal tests
- redundant-node behavior

TRANSFER
- mapping behavior
- ambiguous mapping

BUDGET
- simulator call accounting
- hard budget enforcement

CLEAN ROOM
- oracle unavailable
- path escapes blocked where applicable

METHOD LOCK
- source/config hash checks

CLOUD
- small local/Modal consistency test

All 385 Phase 1 tests must remain passing.

Do not weaken benchmark tests to make Phase 2 easier.

======================================================================
45. METHOD DOCUMENTATION
======================================================================

Create a rigorous method document, perhaps:

    research/phase2/BRAINIR_V1_METHOD.md

It should include:

- problem definition
- notation
- algorithm
- pseudocode
- objective
- acquisition strategy
- uncertainty model
- complexity
- stopping rule
- hyperparameters
- rationale
- known failure modes

A knowledgeable researcher should be able to reconstruct the method from the document.

======================================================================
46. PHASE 2 RESULT DOCUMENTATION
======================================================================

Create:

    PHASE2_REPORT.md

Include:

- what was researched
- algorithms considered
- synthetic benchmark design
- algorithm tournament
- chosen method
- rejected methods and why
- mathematical method specification
- simulator budget
- synthetic results
- baseline comparisons
- reliability
- robustness
- transfer
- ablations
- minimality
- uncertainty
- blind evaluation protocol
- blind result
- Modal usage
- compute cost
- test status
- limitations
- failures
- whether BrainIR v1 genuinely beats greedy
- exact next Phase 3 recommendation

Do not hide negative results.

======================================================================
47. INDEPENDENT REVIEWS
======================================================================

Before completion, conduct independent reviews.

A. CAUSAL DISCOVERY REVIEW

Ask whether the method actually identifies causal mechanism or merely correlated importance.

B. OPTIMIZATION REVIEW

Check search/objective correctness and whether easier algorithms would perform equally well.

C. STATISTICS REVIEW

Check comparisons, confidence intervals, nulls, and claims.

D. LEAKAGE REVIEW

Try to prove hidden oracle information influenced method design.

E. CROSS-CONNECTOME REVIEW

Check whether transfer is legitimate or mapping leakage.

F. COMPUTATIONAL REVIEW

Check budget accounting, caching, Modal reproducibility, performance.

G. ADVERSARIAL REVIEW

Try hard to construct synthetic cases where BrainIR gives a confident but wrong mechanism.

Fix serious findings.

======================================================================
48. IMPORTANT RESEARCH HONESTY RULE
======================================================================

If greedy_prune_sim remains better than BrainIR v1:

SAY SO.

Do not manipulate metrics.

Do not weaken greedy.

Do not cherry-pick seeds.

Do not quietly expand BrainIR's simulation budget.

Do not change the frozen benchmark.

A negative result is useful.

Diagnose why.

Then determine whether a general Phase 2 v2 is justified without hidden-answer tuning.

======================================================================
49. WHAT NOT TO BUILD YET
======================================================================

Do NOT build:

- final symbolic BrainIR DSL
- full program synthesis
- LLM-generated brain explanations as the core
- formal SMT verification
- CEGAR
- whole-brain decompilation
- FlyGym embodiment
- web UI
- consciousness claims
- generic foundation model

Those are later phases.

Phase 2 is specifically:

    CAUSAL MECHANISM DISCOVERY.

======================================================================
50. PHASE 2 ACCEPTANCE CRITERIA
======================================================================

Do not call Phase 2 complete unless:

1. Frozen Phase 1 benchmark remains unchanged and valid.

2. A public-only clean discovery environment exists.

3. A substantial synthetic mechanism-discovery suite exists.

4. Multiple algorithm families were seriously evaluated.

5. BrainIR v1 has a coherent mathematical algorithm.

6. BrainIR v1 is benchmark-generic and contains no DNg100 answer-specific logic.

7. Simulator calls are explicitly budgeted.

8. Active intervention selection is investigated.

9. Group/compressive causal probing is investigated.

10. Robust mechanism discovery across parameter uncertainty is implemented or rigorously evaluated.

11. Mechanism uncertainty is represented.

12. Minimality testing exists.

13. Generic role inference exists at least at a first meaningful level.

14. Cross-connectome transfer is supported.

15. Synthetic results show the algorithm actually works beyond one oscillator.

16. Phase 1 greedy baseline is rerun fairly.

17. Reliability across seeds/orderings is quantified.

18. Query-efficiency curves are produced.

19. Robustness is quantified.

20. Cross-connectome results are quantified.

21. Important ablations are complete.

22. Blind method code/config are locked before hidden evaluation.

23. The blind evaluation uses the frozen clean-room protocol.

24. Hidden-oracle evaluation attempts are explicitly logged.

25. Phase 2 tests pass.

26. All Phase 0/1 tests still pass.

27. Independent audits are completed.

28. Serious audit findings are resolved.

29. PHASE2_REPORT.md exists.

30. A clear conclusion is reached:

        BrainIR v1 beats / matches / loses to greedy,
        and exactly in which dimensions.

======================================================================
51. STRONG SUCCESS CONDITION
======================================================================

The ideal Phase 2 result is NOT simply:

    "we recovered the published circuit."

The ideal result is:

    BrainIR discovers a compact causal mechanism
    without oracle leakage,
    with substantially better reliability and/or query efficiency
    than greedy pruning,
    remains stable under parameter uncertainty,
    assigns interpretable generic functional roles,
    and transfers the same abstract mechanism between independently
    reconstructed connectomes.

If we obtain that, BrainIR has crossed an important line:

It is no longer merely reducing a neural graph.

It is beginning to infer a reusable causal computation.

======================================================================
52. PHASE 3 SHOULD NOT BEGIN
======================================================================

Do not begin symbolic program synthesis in this goal.

At completion, recommend ONE next Phase 3 step.

Likely possibilities include:

- causal state-variable discovery
- neuron-to-latent mapping
- first BrainIR symbolic DSL
- program synthesis over the discovered mechanism

But choose the next step from evidence.

Do not assume it now.

======================================================================
53. FINAL SELF-AUDIT
======================================================================

Before finishing Phase 2, aggressively try to disprove your own result.

Ask:

Could greedy achieve this with equal compute?

Could a random matched method achieve this?

Did graph structure alone leak the answer?

Did an exact node count fingerprint the solution?

Did the method rely on a particular node ordering?

Did it exploit benchmark-specific IDs?

Did a known biological name leak into a feature?

Did hidden evaluator output influence tuning?

Did the simulator cache leak oracle information?

Did cross-connectome mapping reveal the answer?

Does the method fail on a different synthetic mechanism family?

Does the result disappear under parameter uncertainty?

Is confidence calibrated or just a score?

Does the method find alternative valid mechanisms?

Would the conclusion survive a skeptical paper reviewer?

Test these questions.

Fix general methodological problems.

Document irreducible limitations honestly.

======================================================================
54. FINAL RESPONSE TO USER
======================================================================

Do not give the user constant progress updates.

Operate autonomously until done or genuinely blocked.

At completion, return a concise report containing only:

- Phase 2 status
- BrainIR v1 algorithm in plain English
- major technical innovation(s)
- synthetic performance
- blind DNg100 result
- comparison against greedy_prune_sim
- reliability improvement
- simulator-query reduction or increase
- robustness
- cross-connectome transfer result
- whether generic roles were recovered
- total tests passing
- independent audit status
- Modal compute/cost used
- git commit/tag/method lock
- important limitation
- ONE recommended Phase 3 step

Do not start Phase 3.

======================================================================
CORE PRINCIPLE
======================================================================

We are not trying to produce a result that LOOKS impressive.

We are trying to determine whether an algorithm can genuinely infer
a compact causal computation from a biological neural circuit.

If the benchmark shows BrainIR v1 is worse than greedy, report it.

If an unexpectedly simple method wins, use it.

If multiple mechanisms are equally supported, preserve the uncertainty.

If biology does not support a simple explanation, do not invent one.

The goal is discovery, not storytelling.