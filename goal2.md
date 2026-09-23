# BrainIR Phase 1 — Cross-Connectome Benchmark, Dynamics Reproduction, and Frozen Evaluation Infrastructure

You are taking full operational and scientific ownership of Phase 1 of BrainIR.

PROJECT LOCATION
C:\Dev\BrainIR

IMPORTANT: Begin by reading, in this order:

1. CLAUDE.md
2. PHASE0_REPORT.md
3. the Phase 0 research notes
4. the DNg100 benchmark specification
5. the engineering/research log
6. the current source tree
7. current git history/status
8. current test suite

Do not assume the summaries in this prompt are more authoritative than the repository itself. Inspect and verify the actual current state before modifying anything.

======================================================================
MISSION
======================================================================

BrainIR's long-term objective is to automatically decompile biological neural circuits into compact, executable, causally testable programs whose variables and operators map back onto real neurons.

We are NOT ready to build the decompiler yet.

Phase 1 exists to build the benchmark and scientific infrastructure that will determine whether BrainIR later actually discovers biological mechanisms or merely produces plausible-looking explanations.

The core Phase 1 objective is:

    Build a rigorous, cross-connectome, anti-leakage benchmark around the
    DNg100 walking-rhythm circuit using MaleCNS + MANC, reproduce the relevant
    published dynamical behavior as faithfully as possible, implement strong
    non-BrainIR baselines, and freeze the benchmark before any circuit-discovery
    algorithm is developed.

This phase should leave us with a benchmark where a future discovery algorithm can be given a CLEAN PUBLIC INPUT BUNDLE and evaluated against a SEPARATE ORACLE without having access to the known biological answer.

This distinction is fundamental.

Phase 1 is successful when we can honestly run:

    unknown discovery algorithm
            ↓
    public benchmark data only
            ↓
    candidate mechanism
            ↓
    frozen evaluator + hidden oracle
            ↓
    quantitative score

and know that the result was not leaked from the paper, benchmark notes, source code, filenames, annotations added by us, or benchmark construction process.

======================================================================
OPERATING MODE — EXTREMELY IMPORTANT
======================================================================

The user is not your operator.

YOU are the operator.

The user should not be asked to manually perform routine engineering, research, downloading, installation, experimentation, testing, environment management, debugging, or compute tasks.

You have broad autonomy.

You are expected to use whatever tools are available and useful, including:

- shell
- PowerShell
- Python
- uv
- git
- browser/web research
- Claude in Chrome
- official APIs
- official data downloads
- package managers
- local filesystem
- compression/decompression tools
- scientific Python
- compiled dependencies
- Docker/WSL if useful and already practical
- Modal cloud compute
- parallel workers/subagents if available
- multi-agent review tools if available
- CPU/GPU cloud jobs
- profiling tools
- static analysis
- test frameworks
- experiment runners
- reproducibility tools

Do not ask the user how to perform something you can determine yourself.

Do not ask the user to download anything manually.

Do not ask the user to install anything manually.

Do not ask the user to run commands.

Do not ask the user to copy files.

Do not ask the user to search papers.

Do not stop because a task is complicated.

Research it, test hypotheses, inspect failures, iterate, and solve it.

Only involve the user if genuinely unavoidable, such as:

- interactive login
- CAPTCHA
- 2FA
- browser/OS security dialog inaccessible to you
- physical hardware action
- destructive or irreversible action involving unrelated personal data

If one of these occurs:

1. finish everything that does not depend on it;
2. identify the exact blocker;
3. ask for exactly ONE minimal manual action;
4. continue immediately afterward.

Do not provide unnecessary status chatter.

Work until the phase is genuinely complete or there is a true blocker.

======================================================================
COMPUTE / SPEED POLICY
======================================================================

The user has access to Modal and roughly $1,000 of compute budget/credits.

Use it.

We want the work done PROPERLY and FULLY, but also QUICKLY.

Do not spend hours doing locally what can be completed substantially faster through parallel cloud compute.

Use Modal aggressively when it materially improves wall-clock time for:

- simulation sweeps
- parameter sweeps
- Monte Carlo validation
- cross-connectome experiments
- repeated reproducibility runs
- independent baseline evaluation
- bootstrap/null distributions
- CPU-heavy processing
- GPU-appropriate workloads
- future differentiable dynamics
- parallel verification

However:

- do not waste compute merely because it exists;
- IO-bound downloads do not magically need GPUs;
- small unit tests should stay local;
- record approximate cloud usage/cost;
- prefer parallel jobs when tasks are independent;
- cache expensive reusable results;
- terminate unnecessary jobs;
- never silently create an uncontrolled runaway cost loop.

Cost is secondary to scientific quality and wall-clock efficiency, but pointless spending is still bad engineering.

The local machine has no CUDA GPU. Do NOT allow that to slow down a workload for hours if Modal can execute it efficiently.

======================================================================
CURRENT PHASE 0 STATE
======================================================================

Phase 0 reportedly established:

- MaleCNS v1.0 structured connectome
- official files downloaded
- checksums verified
- 166,700 neurons
- 25,582,938 neuron-pair connections
- approximately 124.2M synapses
- normalized versioned BrainIR schema
- evidence-type labeling
- deterministic ingestion
- approximately 70 validation checks
- Python API
- brainir CLI
- graph queries
- provenance
- research notes
- DNg100 benchmark location
- 86/86 tests passing
- independent 23/23 audit
- three byte-identical processed builds
- git repository with Phase 0 history

VERIFY ALL OF THIS YOURSELF.

Do not rely blindly on the report.

Before Phase 1 modifications:

1. inspect git status;
2. preserve existing work;
3. rerun Phase 0 tests;
4. rerun critical validation;
5. verify representative MaleCNS records;
6. verify dataset hashes/manifests where practical;
7. confirm no unexplained local modifications exist.

Create a clean Phase 1 branch/commit structure if appropriate.

Do not destroy Phase 0 reproducibility.

======================================================================
PHASE 1 SCIENTIFIC PRINCIPLE
======================================================================

We must separate THREE things extremely carefully:

A. INPUT EVIDENCE
   information a future BrainIR discovery algorithm is allowed to see

B. BENCHMARK ORACLE
   information known to us from published work but hidden from the discovery system

C. EVALUATION LOGIC
   frozen rules used to score a candidate mechanism

If these are mixed, the benchmark becomes scientifically weak.

For example, if the discovery algorithm is allowed to read a research note containing:

    "the important oscillator is E1 + E2 + inhibitory neuron X"

and later returns E1 + E2 + X, that is meaningless.

Phase 1 must make this kind of leakage difficult by design.

======================================================================
WORKSTREAM 1 — ACQUIRE AND INGEST MANC
======================================================================

Add the Male Adult Nerve Cord connectome to BrainIR.

IMPORTANT:

Do NOT blindly assume "MANC v1.2.x" means one exact release.

Research:

- which MANC version the relevant walking-rhythm paper actually used;
- which MANC release is currently officially available;
- whether those versions differ;
- whether neuron IDs or annotations changed;
- whether exact paper reproduction requires a historical release.

The BENCHMARK should use the exact connectome release used by the paper whenever that release can be obtained.

If a newer MANC release also has scientific value, it may be ingested separately.

NEVER silently substitute one dataset version for another.

For every MANC dataset ingested, record:

- official dataset name
- exact version
- release date
- official source
- acquisition method
- checksums
- raw file sizes
- schemas
- neuron count
- connection count
- synapse count
- annotation version
- known caveats
- citation/license information
- relationship to the version used in the paper

Reuse the Phase 0 canonical BrainIR schema.

Do NOT fork the entire data model merely for MANC.

Instead build a clean dataset-adapter architecture if Phase 0 does not already provide one.

A canonical internal identifier must never allow accidental cross-dataset collision.

Conceptually use something equivalent to:

    (dataset, version, source_neuron_id)

rather than assuming neuron ID alone is globally unique.

Preserve source IDs exactly.

Do not overwrite or "normalize away" biologically relevant annotations.

======================================================================
WORKSTREAM 2 — EXTEND THE CANONICAL CONNECTOME ABSTRACTION
======================================================================

Audit the Phase 0 schema against MANC.

Determine which fields:

- map directly;
- require transformation;
- do not exist in MANC;
- exist in MANC but not MaleCNS;
- are predictions rather than observations;
- differ in semantics.

Maintain explicit evidence typing.

Examples:

    raw anatomy
    curated annotation
    inferred annotation
    ML neurotransmitter prediction
    rule-derived sign
    model parameter
    literature-derived label

NEVER silently convert one evidence type into another.

If MANC contains information that deserves a schema extension, make the extension general enough to remain useful for:

- MaleCNS
- MANC
- BANC
- FANC
- FlyWire / FAFB

Avoid dataset-specific hacks when a principled abstraction exists.

Add migration/versioning support if needed.

All transformations must remain reproducible.

======================================================================
WORKSTREAM 3 — MANC VALIDATION
======================================================================

Apply at least the rigor used for MaleCNS.

Validate:

- source checksums
- row counts
- uniqueness constraints
- neuron IDs
- edge endpoints
- duplicate edges
- duplicate synapses
- null handling
- annotation joins
- directionality
- synapse aggregation
- autapses
- neuropil labels
- neurotransmitter fields
- evidence provenance
- data types
- suspicious impossible values
- cross-table referential integrity

Sample representative records against the official source.

Where possible, reconstruct published statistics.

Perform multiple independent processed builds.

If outputs are expected to be deterministic, confirm deterministic output.

If nondeterminism exists due only to non-semantic metadata such as timestamps, separate that from scientific content.

Do not settle for "pipeline ran."

Prove the resulting graph is trustworthy.

======================================================================
WORKSTREAM 4 — CROSS-CONNECTOME CELL-TYPE / NEURON MAPPING
======================================================================

Build a principled mapping layer between MaleCNS and MANC for the walking benchmark.

The mapping must distinguish:

1. exact neuron identity when meaningful;
2. homologous neuron;
3. same named cell type;
4. same inferred functional role;
5. uncertain correspondence.

Do NOT collapse these categories.

For each mapping, record:

- source dataset neuron
- destination dataset neuron
- cell type
- mapping method
- evidence
- confidence
- ambiguity
- provenance

Use:

- official annotations
- published cross-dataset mappings
- morphology when necessary
- cell-type labels
- neuropil/arborization information
- connectivity signatures
- side/leg/body-region metadata

Do not invent a mapping simply because two neurons have similar names.

If there are disagreements between official resources and papers, investigate.

Create a machine-readable cross-connectome mapping table and a human-readable report.

======================================================================
WORKSTREAM 5 — DEEPLY RECONSTRUCT THE DNG100 BENCHMARK
======================================================================

Read the complete relevant walking-rhythm paper again.

Read:

- main text
- methods
- supplementary methods
- supplementary figures
- supplementary tables
- code repository if one exists
- dataset/version notes
- parameter descriptions
- simulation details
- pruning procedure
- interventions
- cross-connectome comparison

Understand the original pipeline well enough that we could explain every transformation mathematically.

Determine precisely:

- what neuronal population was considered;
- how the graph was extracted;
- what DNg100 input was applied;
- how synapse counts were transformed into model influence;
- which neurotransmitter/sign assumptions were used;
- what neuron dynamical equations were used;
- timestep/integration details;
- initialization;
- stochasticity;
- normalization;
- thresholds;
- output populations;
- how "rhythmic" was defined;
- how candidate circuits were pruned;
- what stopping conditions were used;
- how robustness was assessed;
- how the four connectomes were compared;
- what was experimentally validated versus simulated.

Never fill missing methods details with unmarked guesses.

If some details cannot be recovered:

- document uncertainty;
- test plausible alternatives;
- quantify whether results depend on them.

======================================================================
WORKSTREAM 6 — REPRODUCE THE PUBLISHED DYNAMICS
======================================================================

Implement or faithfully reuse the paper's dynamical model.

Prefer this hierarchy:

1. official authors' released executable code, if available and appropriately licensed;
2. faithful independent implementation from methods;
3. clearly labeled reconstruction if some details are unavailable.

Do not copy code with unclear licensing.

If official code is used:

- pin the exact commit/version;
- record its license;
- preserve provenance;
- wrap it rather than corrupting it.

Create a BrainIR benchmark simulator interface.

Conceptually:

    simulate(
        connectome,
        model_config,
        stimulus,
        intervention,
        seed
    ) -> trajectory

The trajectory should expose whatever is required for evaluation, such as:

- neuron activity
- population activity
- motor output
- time vector
- stimulus
- intervention events
- derived rhythm metrics

The simulator must be independent from the future BrainIR symbolic-program synthesizer.

======================================================================
WORKSTREAM 7 — BUILD A RIGOROUS RHYTHM METRIC
======================================================================

Do not define "rhythm" using one arbitrary threshold.

Construct a proper evaluation suite.

Investigate the original paper's definition first.

Then implement scientifically defensible metrics that may include:

- oscillation frequency
- dominant spectral peak
- spectral concentration
- autocorrelation periodicity
- peak-to-trough amplitude
- coefficient of variation of period
- cycle stability
- phase relationships
- persistence across time
- left/right or flexor/extensor relationships where relevant
- motor-output periodicity
- sensitivity to transient perturbation
- recovery after perturbation

Do not assume all are appropriate.

Select metrics based on the actual benchmark biology.

Where useful, combine multiple quantities into an explicit rhythm score:

    R = f(
        spectral evidence,
        temporal periodicity,
        amplitude,
        stability,
        biological output
    )

If you construct a composite score:

- make the components visible;
- justify the weighting;
- test sensitivity to weighting;
- avoid tuning it to make the published circuit look best.

The metric should distinguish:

- true sustained rhythm
- damped transient
- noisy firing
- constant high activity
- constant low activity
- irregular bursting
- numerical artifacts

Create synthetic test signals for all of those cases.

The evaluator must classify them correctly.

======================================================================
WORKSTREAM 8 — CREATE THE BENCHMARK PUBLIC BUNDLE
======================================================================

Create a clean PUBLIC benchmark package containing ONLY evidence a future mechanism-discovery algorithm is permitted to use.

Example conceptual contents:

    dataset subset / graph
    allowed biological annotations
    allowed NT/sign information
    model definition
    input protocol
    simulation interface
    observational trajectories if allowed
    intervention data if allowed
    benchmark task definition

DO NOT INCLUDE:

- the known minimal circuit
- known target neuron set
- oracle labels
- paper-derived "important neuron" hints
- filenames revealing the answer
- comments revealing the answer
- tests revealing exact expected circuit
- constants chosen using knowledge of the hidden answer unless justified independently
- literature notes containing the answer
- benchmark construction logs that reveal the answer

The public bundle should be exportable independently.

Implement a command conceptually like:

    brainir benchmark dng100 export-public ...

The exported directory should contain everything needed to run a future discovery method and NOTHING from the oracle.

Generate a manifest and hash for the public bundle.

======================================================================
WORKSTREAM 9 — BUILD THE ORACLE
======================================================================

Create a SEPARATE benchmark oracle.

The oracle may contain:

- published minimal circuit identities
- cell types
- relevant edges
- abstract roles
- known intervention results
- published cross-connectome correspondences
- known simulation outcomes
- expected qualitative mechanism
- any exact results necessary for scoring

Document the evidence level for every oracle fact.

Example:

    result:
        known from paper simulation

versus:

    result:
        wet-lab validated

versus:

    result:
        expert interpretation

These are not equivalent.

Do not pretend simulated ground truth is biological ground truth.

The oracle should be usable ONLY by the benchmark evaluator.

Future discovery code should not import it.

======================================================================
WORKSTREAM 10 — ANTI-LEAKAGE ARCHITECTURE
======================================================================

This is extremely important.

Merely putting oracle files in another folder is NOT enough because future Claude sessions may have access to the whole repository.

Design a CLEAN-ROOM evaluation workflow.

Strong preferred design:

    FULL REPOSITORY
        |
        | export
        v
    PUBLIC BENCHMARK BUNDLE
        |
        | run discovery in isolated environment
        v
    prediction.json
        |
        | bring prediction back
        v
    ORACLE EVALUATOR

The discovery process should execute in an environment where the oracle is not mounted.

Possible approaches:

- isolated temporary workspace
- container
- separate package build
- Modal job with only the public bundle mounted
- another clean execution environment

Choose the strongest practical implementation.

Add automated leakage checks.

Examples:

- scan exported public files for hidden cell-type names
- scan comments/docs
- ensure evaluator/oracle modules are not imported
- ensure environment variables don't expose oracle path
- ensure package metadata doesn't encode answer
- ensure test fixtures do not contain oracle identities
- ensure filenames do not reveal answer

Create a `LEAKAGE_AUDIT.md`.

======================================================================
WORKSTREAM 11 — DEFINE A STANDARD PREDICTION FORMAT
======================================================================

Future algorithms need a fixed output format.

Create something like a versioned:

    BrainIRMechanismPrediction

At minimum consider fields for:

- benchmark version
- dataset(s)
- candidate neurons
- candidate cell types
- candidate edges
- abstract functional roles
- excitatory/inhibitory relationship
- predicted recurrence
- predicted causal ordering
- predicted oscillatory mechanism
- predicted intervention consequences
- uncertainty/confidence
- optional textual description

Do not require future algorithms to output our final BrainIR DSL yet.

Phase 1 should score CIRCUIT / MECHANISM DISCOVERY.

The full symbolic program language belongs later.

Make the prediction schema expressive enough for several discovery methods, but not so vague that scoring becomes subjective.

======================================================================
WORKSTREAM 12 — BUILD THE FROZEN EVALUATOR
======================================================================

Create a deterministic evaluator:

    public benchmark
    +
    submitted prediction
    +
    hidden oracle
        ↓
    quantitative report

The evaluator should produce separate scores rather than hiding everything inside one magic number.

Consider metrics in these families:

STRUCTURAL RECOVERY
- neuron-level precision
- neuron-level recall
- cell-type-level precision/recall
- edge precision/recall
- relevant recurrent motif recovery

FUNCTIONAL RECOVERY
- rhythm preservation
- frequency agreement
- trajectory agreement
- intervention response agreement
- causal necessity/sufficiency where available

MECHANISM QUALITY
- compactness
- causal faithfulness
- role consistency

CROSS-CONNECTOME GENERALIZATION
- equivalent role recovered in MaleCNS
- equivalent role recovered in MANC
- conserved abstract mechanism
- dataset-specific overfitting penalty

ROBUSTNESS
- seeds
- plausible model parameter variations
- perturbation strength
- noise
- initialization

Do not average these immediately into a single opaque score.

Keep the individual metrics visible.

If a composite score is useful later, define it after the components are frozen.

======================================================================
WORKSTREAM 13 — FUNCTIONAL EQUIVALENCE MATTERS MORE THAN EXACT NAME MATCHING
======================================================================

Do not make the benchmark unfairly require one exact published answer if biologically/functionally equivalent mechanisms exist.

Example:

If a different inhibitory neuron in MaleCNS produces the same valid recurrent inhibitory role as the canonical MANC neuron, the evaluator must be capable of recognizing:

    exact identity != functional role

This issue already appeared in Phase 0.

Therefore define at least three layers:

1. exact-neuron agreement
2. cell-type/role agreement
3. functional-mechanism agreement

Score them separately.

A candidate should not get zero merely because it discovers a functionally equivalent implementation.

At the same time, do not make "functional equivalence" so loose that arbitrary circuits pass.

Formalize the criteria.

======================================================================
WORKSTREAM 14 — BASELINES
======================================================================

Implement meaningful baselines BEFORE BrainIR discovery algorithms exist.

This is essential.

A sophisticated method is not impressive if degree centrality solves the benchmark.

At minimum investigate and implement appropriate variants of:

RANDOM
- uniformly random neuron sets
- random sets matched for candidate-set size
- random sets matched for degree distribution
- random sets matched for neurotransmitter/sign
- random sets matched for local graph neighborhood

GRAPH HEURISTICS
- weighted degree
- in-degree
- out-degree
- betweenness
- PageRank/eigenvector-style centrality where appropriate
- k-core
- strongly connected component membership
- recurrent-edge density
- shortest-path relevance between DNg100 and output populations
- edge-weight ranking

MODULE / COMMUNITY BASELINES
- community detection
- spectral clustering
- recurrent-subgraph extraction

FUNCTIONAL BASELINES
- greedy neuron deletion / pruning using the simulator
- greedy edge deletion
- simple perturbation sensitivity ranking

STATISTICAL / REPRESENTATION BASELINES if appropriate
- PCA/factor analysis on trajectories
- clustering neural activity
- simple linear state-space models

Do not add a baseline merely to inflate a list.

Each baseline must answer a legitimate alternative explanation for why a future BrainIR method succeeds.

======================================================================
WORKSTREAM 15 — NULL DISTRIBUTIONS
======================================================================

For each relevant baseline, estimate null distributions.

For example:

    probability that a random matched 3-neuron set:
        preserves rhythm
        forms required recurrence
        matches oracle cell types
        transfers across both connectomes

Run enough random samples to get stable empirical estimates.

Use Modal parallelism where beneficial.

Calculate confidence intervals.

This is important because:

    "Our method found a 3-neuron oscillator"

means little if thousands of random 3-neuron subnetworks also oscillate.

Quantify how exceptional the biological mechanism is.

======================================================================
WORKSTREAM 16 — CROSS-CONNECTOME BENCHMARK
======================================================================

MaleCNS and MANC should not merely be two separate datasets.

Use them to create a true cross-connectome test.

For example:

TRAIN / DISCOVER:
    MaleCNS evidence

TEST:
    Does the discovered abstract mechanism map into MANC?

and the reverse:

DISCOVER:
    MANC

TEST:
    MaleCNS

Eventually:

    shared mechanism across both

Do not yet build the discovery model.

But build the evaluation capability for these experiments.

Define what "same mechanism" means across datasets.

Possibly:

    different neuron IDs
    +
    homologous cell types
    +
    same causal roles
    +
    same recurrent interaction pattern
    +
    same functional output

Create explicit metrics.

======================================================================
WORKSTREAM 17 — ROBUSTNESS / PARAMETER UNCERTAINTY
======================================================================

One major BrainIR principle is:

    anatomy does not uniquely determine dynamics.

Therefore the benchmark should not depend completely on one arbitrary parameter setting.

Research the plausible model uncertainties in the walking simulator.

Generate an uncertainty configuration.

Potential dimensions may include:

- synaptic efficacy scaling
- neuronal time constants
- thresholds
- stimulus amplitude
- inhibitory/excitatory gains
- initialization
- numerical timestep
- biological noise where justified

Do NOT choose ranges arbitrarily.

Use:

- paper values
- biological literature
- model sensitivity
- explicitly labeled engineering stress tests

Run parameter sweeps.

Measure:

    Which conclusions remain stable?

The benchmark oracle may include:

    robust properties
    fragile properties

Do not require future algorithms to rediscover a property that disappears under tiny model perturbations without labeling that fragility.

======================================================================
WORKSTREAM 18 — NUMERICAL CORRECTNESS
======================================================================

Treat simulator numerics seriously.

Check:

- integration method
- timestep convergence
- floating-point precision
- deterministic seeds
- solver stability
- overflow/underflow
- discrete-time artifacts
- transient length
- measurement window
- spectral leakage
- FFT resolution
- initialization sensitivity

Perform convergence tests.

For example:

    dt
    dt/2
    dt/4

and verify important benchmark conclusions do not arise purely from numerical artifacts.

If they do, investigate before continuing.

======================================================================
WORKSTREAM 19 — SYNTHETIC EVALUATOR TESTS
======================================================================

Before trusting the biological benchmark, create synthetic circuits with known behavior.

Examples:

- stable fixed point
- damped oscillator
- sustained oscillator
- noisy oscillator
- bistable system
- recurrent excitation only
- delayed inhibitory oscillator
- feed-forward chain that looks periodic briefly
- random recurrent network

Use these to prove the rhythm evaluator and mechanism scoring behave correctly.

For every synthetic case, ground truth is known.

Add automated tests.

This catches benchmark mistakes before they contaminate BrainIR.

======================================================================
WORKSTREAM 20 — PERFORMANCE ENGINEERING
======================================================================

Profile before optimizing.

Do not rewrite everything in CUDA just because it sounds impressive.

Measure:

- ingestion time
- graph query time
- simulation time
- memory
- baseline runtime
- sweep runtime
- evaluator runtime

Optimize actual bottlenecks.

Use efficient representations such as:

- CSR/CSC sparse matrices
- vectorized NumPy/SciPy
- PyTorch/JAX only where helpful
- memory-mapped Parquet/Arrow where useful

If repeated simulation is expensive:

- cache graph transformations;
- batch parameter sets;
- parallelize seeds;
- use Modal;
- use GPUs only if the arithmetic benefits.

Record performance results.

======================================================================
WORKSTREAM 21 — MODAL INTEGRATION
======================================================================

If Modal is configured or can be configured without unavoidable user interaction, create a reusable compute layer.

BrainIR should eventually be able to launch:

    parameter sweeps
    baseline sweeps
    random null simulations
    reproducibility jobs

through Modal.

Do not make the local code dependent on Modal.

Have a local execution backend and an optional Modal backend.

Use content-addressed inputs/results where practical so we do not recompute identical experiments.

Record:

- job config
- git commit
- dataset manifest hash
- benchmark version
- seed
- model parameters
- environment
- result artifact
- runtime
- approximate compute usage

The same scientific experiment should be reproducible locally on a small scale.

======================================================================
WORKSTREAM 22 — EXPERIMENT REGISTRY
======================================================================

Create a proper experiment-record system.

Every significant benchmark run should record at least:

    experiment_id
    timestamp
    git commit
    benchmark version
    dataset manifest hashes
    simulator version
    configuration
    seeds
    machine/backend
    results
    runtime
    failure status

Avoid relying on random filenames like:

    final2_results_REAL.csv

Use structured run directories or a lightweight experiment registry.

Do not introduce a massive MLOps dependency unless it genuinely helps.

======================================================================
WORKSTREAM 23 — FROZEN RESULT PROTOCOL
======================================================================

Before any future circuit-discovery algorithm is developed, freeze the benchmark.

Create something like:

    benchmarks/dng100/
        public/
        oracle/
        evaluator/
        baselines/
        manifests/

Create a machine-readable benchmark lock file containing cryptographic hashes of:

- public benchmark bundle
- oracle
- evaluator source/version
- metric configuration
- simulator configuration
- baseline definitions
- dataset manifests

Example conceptual name:

    BENCHMARK_LOCK.json

Then create a git tag/release point such as:

    dng100-benchmark-v1

or another appropriate immutable identifier.

After this freeze:

A future BrainIR discovery algorithm must NOT modify the benchmark to improve its score.

Any future benchmark change becomes:

    v2

with explicit rationale.

======================================================================
WORKSTREAM 24 — BLIND DISCOVERY PROTOCOL
======================================================================

Design, but DO NOT yet run BrainIR discovery.

Document the future blind protocol.

It should resemble:

1. create clean public benchmark bundle;
2. start isolated discovery environment;
3. mount only public bundle;
4. install discovery algorithm;
5. run with specified compute budget;
6. emit `prediction.json`;
7. terminate discovery environment;
8. evaluate prediction against hidden oracle;
9. record score;
10. no benchmark modifications after seeing result.

If an LLM/Claude later participates in discovery:

THE LLM MUST NOT HAVE ACCESS TO:

- paper notes containing the answer
- oracle
- Phase 0 benchmark-answer notes
- previous result files
- benchmark evaluator internals that leak answer

This needs to be operationally enforceable as much as practical.

======================================================================
WORKSTREAM 25 — REPRODUCE PAPER-REPORTED CONNECTIVITY
======================================================================

Phase 0 reproduced the MaleCNS reported connection counts.

Do the equivalent for MANC.

Create a structured reproduction table:

    source claim
    dataset
    source neuron/type
    target neuron/type
    published count
    reproduced count
    exact match?
    explanation if different

Investigate every mismatch.

Possible causes:

- dataset version
- annotation release
- segmentation update
- synapse threshold
- hemisphere/leg selection
- neuron ID remapping
- aggregation rule
- typo in paper
- our pipeline bug

Never hand-wave a mismatch.

======================================================================
WORKSTREAM 26 — REPRODUCE PAPER-REPORTED RHYTHM
======================================================================

The benchmark must reproduce the original model behavior before we use it to judge BrainIR.

At minimum reproduce:

- baseline network behavior under the paper's DNg100 stimulation;
- reported periodic/rhythmic output;
- effect of critical pruning/manipulations where feasible;
- cross-connectome qualitative findings relevant to the benchmark.

Compare:

    our result
    vs
    paper figure/table/numeric result

Quantify error.

Do not settle for "looks similar."

If exact reproduction is impossible because necessary code/data are missing:

- identify why;
- reconstruct the closest legitimate model;
- label it explicitly;
- quantify sensitivity to uncertain choices.

======================================================================
WORKSTREAM 27 — NEGATIVE CONTROLS
======================================================================

Build negative controls.

Examples may include:

- shuffled edges
- degree-preserving rewired graph
- neurotransmitter-sign shuffle
- random cell-type reassignment
- edge-weight shuffle
- graph without recurrent edges
- neuron-identity permutation preserving degrees

The objective is to test whether the biological structure actually matters.

Do not assume it does.

If a degree-preserving random network reproduces the benchmark just as well, that is scientifically important and must be reported.

======================================================================
WORKSTREAM 28 — DOCUMENT SCIENTIFIC LIMITATIONS
======================================================================

Maintain extremely clear language.

The DNg100 benchmark currently appears primarily simulation-derived.

Do NOT write:

    "these neurons are proven to be the biological oscillator"

unless the evidence actually supports that statement.

Distinguish:

- anatomical evidence
- computational model result
- published inference
- experimental intervention
- wet-lab validation
- our reproduction
- our hypothesis

Phase 1 documentation must state these separately.

======================================================================
WORKSTREAM 29 — TESTING
======================================================================

Extend the automated test suite substantially.

At minimum cover:

MANC:
- schema
- ingestion
- checksums
- deterministic processing
- query API
- dataset version isolation

MAPPING:
- MaleCNS ↔ MANC mappings
- ambiguity handling
- confidence/provenance

SIMULATOR:
- deterministic seeds
- known toy model
- timestep behavior
- intervention execution

RHYTHM:
- sustained oscillator
- damped oscillator
- noise
- constant signal
- irregular signal
- edge cases

BENCHMARK:
- public export
- oracle isolation
- prediction schema
- evaluator
- hash locking
- freeze detection
- leakage scanning

BASELINES:
- reproducibility
- expected behavior on toy graphs

CLOUD:
- small Modal smoke test if configured
- local/cloud result equivalence within tolerance

Do not choose an arbitrary test count.

Create enough tests to protect actual scientific assumptions.

All Phase 0 tests must continue to pass.

======================================================================
WORKSTREAM 30 — INDEPENDENT REVIEWS
======================================================================

Before declaring Phase 1 complete, perform several independent audits.

If parallel agents/review tools are available, use them.

Have separate reviews focus on:

REVIEW A — Computational neuroscience
Ask:
- Did we misunderstand the biology?
- Are model assumptions represented honestly?
- Does the benchmark measure what we claim?

REVIEW B — Data engineering
Ask:
- Are datasets/versioning/provenance trustworthy?
- Did we mix IDs/releases?
- Can everything be rebuilt?

REVIEW C — Numerical methods
Ask:
- Are oscillator results numerically stable?
- Are spectral/rhythm metrics correct?
- Are parameter sweeps valid?

REVIEW D — Benchmark leakage
Ask:
- Could a future discovery algorithm infer the answer from supposedly public artifacts?
- Are any filenames, comments, fixtures, logs, annotations, or code leaking the oracle?

REVIEW E — ML benchmarking
Ask:
- Are baselines strong enough?
- Are metrics gameable?
- Are null models appropriate?
- Is the benchmark biased toward the published answer?

REVIEW F — Reproducibility
Ask:
- Can a fresh environment reproduce results?
- Are hidden machine assumptions present?

Fix serious findings.

Do not merely append reviewer comments.

======================================================================
NON-GOALS — DO NOT DO THESE YET
======================================================================

DO NOT build the actual BrainIR program synthesizer.

DO NOT build neural-to-symbolic latent discovery.

DO NOT build the final BrainIR DSL.

DO NOT build causal abstraction learning.

DO NOT build formal verification.

DO NOT build a web UI.

DO NOT build an LLM explanation layer.

DO NOT attempt whole-CNS decompilation.

DO NOT optimize for flashy visualizations.

DO NOT train an RL agent.

DO NOT use the oracle to "help" future discovery.

PHASE 1 creates the test.

Phase 2 will begin solving the test.

======================================================================
EXPECTED REPOSITORY SHAPE
======================================================================

Adapt this to the existing repository rather than blindly replacing the structure.

Conceptually we should end with something like:

brainir/
│
├── src/brainir/
│   ├── connectome/
│   │   ├── schema
│   │   ├── adapters/
│   │   │   ├── malecns
│   │   │   └── manc
│   │   ├── mapping
│   │   └── queries
│   │
│   ├── dynamics/
│   │   ├── simulator
│   │   ├── models
│   │   ├── interventions
│   │   └── metrics
│   │
│   ├── benchmark/
│   │   ├── public_api
│   │   ├── prediction_schema
│   │   ├── evaluator
│   │   ├── baselines
│   │   └── export
│   │
│   └── compute/
│       ├── local
│       └── modal
│
├── benchmarks/
│   └── dng100_walking_cpg/
│       ├── public/
│       ├── oracle/
│       ├── baselines/
│       ├── manifests/
│       ├── SPEC.md
│       ├── LEAKAGE_AUDIT.md
│       └── BENCHMARK_LOCK.json
│
├── data/
│   ├── raw/
│   │   ├── malecns/
│   │   └── manc/
│   ├── processed/
│   ├── mappings/
│   └── manifests/
│
├── experiments/
│
├── research/
│
├── tests/
│
├── CLAUDE.md
│
└── PHASE1_REPORT.md

Do not force this exact structure if the existing design has a cleaner equivalent.

======================================================================
KEY COMMANDS WE SHOULD IDEALLY HAVE AT THE END
======================================================================

Aim for clean commands conceptually equivalent to:

    brainir data status

    brainir ingest malecns

    brainir ingest manc

    brainir validate malecns

    brainir validate manc

    brainir map malecns manc --benchmark dng100

    brainir benchmark dng100 status

    brainir benchmark dng100 reproduce

    brainir benchmark dng100 export-public

    brainir benchmark dng100 baseline --all

    brainir benchmark dng100 evaluate prediction.json

    brainir benchmark dng100 audit-leakage

    brainir benchmark dng100 verify-lock

    brainir compute status

Exact syntax is your decision.

Prefer coherent UX over blindly following these strings.

======================================================================
ACCEPTANCE CRITERIA
======================================================================

Do NOT call Phase 1 complete until all of the following are satisfied.

1. Phase 0 remains reproducible.

2. MANC exact benchmark version is identified.

3. MANC official data are acquired automatically.

4. MANC checksums/provenance are recorded.

5. MANC is represented in the canonical BrainIR schema.

6. MANC validation passes.

7. MaleCNS/MANC neuron/cell-type mapping exists for the benchmark.

8. Mapping uncertainty/provenance are explicit.

9. Published benchmark connectivity is independently reproduced as far as data permit.

10. Published dynamical behavior is independently reproduced or every reproducibility gap is precisely characterized.

11. A scientifically defensible rhythm evaluator exists.

12. Rhythm evaluator passes synthetic tests.

13. A public benchmark bundle exists.

14. The oracle exists separately.

15. The public bundle does not contain known-answer leakage.

16. A clean-room discovery execution design exists and preferably works.

17. A fixed prediction schema exists.

18. A deterministic evaluator exists.

19. Strong baseline methods exist.

20. Null distributions have been estimated where relevant.

21. MaleCNS→MANC and MANC→MaleCNS cross-connectome evaluation is supported.

22. Robustness across relevant parameter uncertainty has been tested.

23. Negative controls have been run.

24. Important numerical conclusions survive convergence testing.

25. Experiment provenance is machine-readable.

26. Modal compute path works if accessible.

27. All tests pass.

28. Independent audits are completed.

29. Serious audit findings are fixed.

30. Benchmark artifacts are cryptographically locked/versioned.

31. A git tag or equivalent immutable benchmark version exists.

32. `PHASE1_REPORT.md` exists and is sufficient for a fresh research session to continue without asking the user what happened.

======================================================================
PHASE 1 REPORT
======================================================================

Create `PHASE1_REPORT.md`.

It should cover:

- what was built
- exact MANC dataset/version
- relationship to paper version
- storage
- processing
- validation
- cross-connectome mappings
- reproduction of published connectivity
- reproduction of published dynamics
- simulator equations
- numerical details
- rhythm metrics
- baseline methods
- baseline results
- null results
- negative controls
- robustness/sensitivity results
- benchmark public/oracle separation
- leakage audit
- benchmark lock/version
- Modal/cloud usage
- tests
- independent reviews
- unresolved uncertainties
- scientific limitations
- exact recommended Phase 2 objective

Do not pad the report.

Make it technically precise.

======================================================================
SELF-AUDIT BEFORE FINISHING
======================================================================

Before completion, pretend you are a skeptical reviewer trying to reject the future BrainIR paper.

Try to prove that:

- data versions are wrong;
- the MANC mapping is incorrect;
- the simulator does not reproduce the source work;
- rhythm detection is flawed;
- the result is a numerical artifact;
- trivial graph heuristics solve the benchmark;
- random circuits perform similarly;
- the benchmark leaks the answer;
- functional-equivalence scoring is subjective;
- the oracle contains unsupported claims;
- cross-connectome mapping is cherry-picked;
- parameter uncertainty destroys the conclusion;
- cloud/local results differ;
- the benchmark is irreproducible.

Actually test these possibilities.

If you find weaknesses, fix them or document them honestly.

Do not optimize the project to make the benchmark look impressive.

Optimize it to make the benchmark TRUE.

======================================================================
FINAL BEHAVIOR
======================================================================

Work autonomously.

Do not stop every few minutes to tell the user what you are doing.

Do not ask permission for reversible technical decisions.

Do not ask the user to execute routine commands.

Do not give the user setup homework.

Use the web.

Download files yourself.

Install dependencies yourself.

Run experiments yourself.

Use Modal when useful.

Parallelize work when useful.

Research uncertainty deeply.

Test rather than guess.

If one implementation path fails, find another.

Continue until Phase 1 is actually complete.

Only interrupt the user for a genuinely unavoidable manual action.

At the very end, return a concise completion report with:

- Phase 1 status
- exact MANC version acquired
- benchmark reproduction result
- key MaleCNS/MANC findings
- baseline/null results
- benchmark leakage status
- tests/audit results
- compute used
- benchmark frozen version/tag
- genuine unresolved issue, if any
- ONE recommended next step for Phase 2

Do not start Phase 2.

Phase 1 exists so that when we eventually claim:

    "BrainIR independently rediscovered a biological algorithm"

we have a benchmark rigorous enough that the claim actually means something.