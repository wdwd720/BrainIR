You are taking full operational ownership of Phase 0 of a serious research project called BrainIR.

BrainIR's long-term goal is to automatically decompile biological neural circuits into compact, executable, human-readable programs whose variables and operations map back onto real neurons and whose causal predictions can be tested through interventions.

IMPORTANT OPERATING RULE:
The user should not be asked to manually perform routine work. You are expected to do essentially all operational work yourself using the computer, shell, browser, available tools, filesystem, package managers, APIs, downloads, local applications, and code execution.

That includes, when useful:

* inspect the machine and existing environment
* inspect directories and existing projects
* create the repository
* install packages and dependencies
* create virtual environments
* download datasets
* use the web for research
* read papers and official documentation
* interact with websites
* use APIs
* create/edit files
* run shell commands
* run scripts
* debug failures
* inspect logs
* run tests
* profile code
* retry failed approaches
* make engineering decisions
* refactor your own work
* validate data
* generate checksums
* initialize and use git
* inspect browser-accessible information
* reason deeply about mathematics, neuroscience, ML, systems design, and implementation details
* run experiments to resolve uncertainty rather than asking the user speculative questions

Do not give the user a list of manual steps when you can perform those steps yourself.

Only stop and ask the user to perform something manually when it is genuinely unavoidable, such as:

* authentication that specifically requires the user's login interaction
* CAPTCHA
* 2FA/security confirmation
* an OS/browser permission dialog that cannot be completed through your available tools
* a physical/hardware action
* explicit approval for a genuinely destructive or irreversible action involving unrelated user data

If such a blocker occurs, complete everything else possible first. Then ask for exactly one minimal manual action, explain precisely what must be done, and continue once available.

Do not repeatedly ask for confirmation on reversible engineering decisions. Make a reasonable decision, document it, test it, and proceed.

You have broad autonomy over implementation details. Think very deeply. Use experimentation and evidence. If an approach fails, diagnose it and try a better one. Do not prematurely stop because something is difficult.

PHASE 0 OBJECTIVE

Do NOT attempt to build the complete BrainIR system yet.

This phase exists to build a trustworthy, reproducible data and research foundation for later mathematical, causal, ML, program-synthesis, and formal-verification work.

The authoritative primary connectome for this phase is the HHMI Janelia MaleCNS v1.0 dataset, accessible through neuPrint using dataset `male-cns:v1.0`.

Prefer official Janelia sources and primary scientific publications over random mirrors or secondary descriptions.

Our first future biological benchmark will be the published Drosophila walking rhythm / central-pattern-generator system downstream of DNg100.

The relevant published work reports that connectome-constrained simulations across multiple fly connectomes repeatedly identify a compact recurrent oscillator involving excitatory populations corresponding to E1/IN17A001 and E2/INXXX466 together with inhibitory feedback.

IMPORTANT:
Do not bake this published solution into any algorithm we later claim independently rediscovered.

For Phase 0, however, you should study the paper deeply so we know exactly what benchmark exists, what evidence supports it, and what data are available.

TASKS

1. MACHINE + PROJECT DISCOVERY

Inspect the computer thoroughly enough to understand:

* operating system
* available disk space
* Python versions
* package managers
* git
* compilers/build tools
* GPU/CUDA availability if present
* browser access
* relevant existing folders
* existing neuroscience/ML packages if any
* any existing `brainir` directory or related work

Choose a sensible project location yourself.

Create or reuse a clean top-level BrainIR repository.

Set up a professional, reproducible Python project using a modern environment/package workflow.

Make the repository usable without requiring the user to execute setup commands manually.

Initialize git if appropriate.

Create a strong `.gitignore`.

Never commit:

* credentials
* API tokens
* browser/session secrets
* giant raw datasets
* cache directories
* generated temporary data
* machine-specific paths
* unnecessary binaries

2. RESEARCH THE CURRENT DATA ECOSYSTEM

Use the web and official documentation yourself.

Deeply inspect:

* MaleCNS v1.0 official documentation
* neuPrint access
* official downloadable flat files
* annotations
* cell types
* neuron-neuron connectivity
* raw synapse tables
* neuropils
* neurotransmitter/sign predictions
* morphology/skeleton availability
* segmentation/raw EM availability
* release/version metadata
* citation/licensing requirements

Also inspect relevant FlyWire/BANC/MANC/FANC resources enough to understand how our future canonical schema should accommodate them.

Do not download massive raw EM image volumes or voxel segmentation unless there is a strong technical reason discovered during research.

For Phase 0, prioritize structured connectome data suitable for graph analysis.

3. ACQUIRE THE STRUCTURED MALECNS DATA YOURSELF

Download/cache the structured MaleCNS v1.0 connectome locally.

Do not tell the user to download anything manually unless absolutely unavoidable.

Prefer official bulk files for large static tables when they are available and practical.

Use `neuprint-python` when API access is better for specific information.

If authentication is necessary:

* first inspect whether an authenticated method/token/session is already available safely
* never print secrets
* never hard-code credentials
* never expose tokens into git or logs

If user interaction is genuinely unavoidable for authentication, complete every independent task first, then stop only at that blocker and request exactly the minimum action necessary.

4. CREATE A CANONICAL BRAINIR DATA MODEL

Design a normalized internal representation capable of eventually supporting:

* MaleCNS
* FlyWire / FAFB
* BANC
* MANC
* FANC
* future connectomes

At minimum define stable representations for:

Neuron:

* stable internal ID
* source dataset
* source neuron ID
* dataset version
* cell type
* neurotransmitter
* neurotransmitter confidence
* biological sex where applicable
* side / hemisphere where applicable
* neuropils
* annotations
* morphology references
* provenance

DirectedConnection:

* pre neuron
* post neuron
* synapse count
* source dataset/version
* neuropil distribution
* predicted sign where justified
* sign confidence
* provenance

Synapse if needed:

* pre neuron
* post neuron
* location
* neuropil
* confidence/provenance

Experiment / Trial for future use:

* stimulus time series
* neural measurements
* behavioral measurements
* intervention type
* targeted neurons
* timing
* amplitude
* provenance

DatasetVersion:

* dataset name
* release
* acquisition source
* acquisition timestamp
* checksums
* transformations
* citation
* license

Keep raw biological facts distinct from inferred/modelled properties.

For example:

* `synapse_count` is observed/inferred anatomy
* `effective_weight` is a modelling parameter
* `predicted_neurotransmitter` is not ground-truth physiology

Do not collapse these concepts.

5. DATA STORAGE

Preserve source/raw downloads immutably.

Create derived data separately.

Use efficient formats such as Parquet/Arrow when appropriate.

Do not manually edit derived tables.

Every processed dataset must be reproducible through code.

Create a sensible directory layout such as:

brainir/
data/
raw/
processed/
cache/
manifests/
src/
tests/
research/
scripts/
docs/

Adapt this if you have a better design.

6. DATASET MANIFEST + PROVENANCE

Create a machine-readable manifest containing:

* official source
* dataset
* exact version
* acquisition method
* acquisition date
* file names
* file sizes
* row counts
* schemas
* hashes/checksums where practical
* transformations
* annotations coverage
* relevant documentation URLs
* publication citation
* licensing notes

The objective is that a future researcher can determine exactly what data entered every analysis.

7. INGESTION PIPELINE

Create one reproducible command/script that can rebuild the processed MaleCNS graph from raw/cached official data.

The pipeline must validate:

* IDs
* uniqueness
* duplicate rows
* missing neurons referenced by edges
* invalid/missing edge values
* data type consistency
* annotation coverage
* directionality
* basic graph statistics
* provenance consistency

Determine how self-connections/autapses are represented and handle them intentionally rather than accidentally dropping them.

Output both data and a validation report.

8. GRAPH ACCESS LAYER

Implement a clean Python API and/or CLI for:

* fetch neuron by ID
* fetch neurons by type
* search annotations
* direct upstream partners
* direct downstream partners
* edge strengths
* neuropil breakdown
* neurotransmitter/sign metadata
* k-hop subgraph extraction
* path queries where useful

Keep it simple and testable.

No UI yet.

9. DNG100 BENCHMARK INVESTIGATION

Use MaleCNS v1.0 and the relevant paper(s) to investigate the DNg100 walking-control benchmark.

Locate the corresponding MaleCNS neuron(s).

Inspect:

* annotations
* cell type
* dataset IDs
* downstream partners
* upstream partners
* relevant neuropils
* recurrent connectivity around the pathway
* how the paper maps named neurons/cell types into the connectome

Determine how E1 / IN17A001, E2 / INXXX466, and the inhibitory component are represented in the relevant datasets.

Do NOT manually encode the published minimal circuit as BrainIR output.

This step is data verification and benchmark characterization only.

10. DEEPLY STUDY THE WALKING-CIRCUIT PAPER

Read the primary paper and supplementary details carefully.

Write a concise research note covering:

* biological question
* datasets used
* connectome versions
* simulation model
* inputs
* outputs
* dynamics assumptions
* pruning/search procedure
* discovered circuit
* interventions
* cross-connectome validation
* any wet-lab validation
* known limitations
* what counts as ground truth versus modelling assumption

Then define what would count as independent BrainIR success later.

For example:

* BrainIR does not receive the known answer
* BrainIR receives the same or less evidence than the original analysis
* it recovers a functionally equivalent compact oscillator
* its neuron-role mapping overlaps the known circuit
* held-out interventions are predicted
* the same abstract mechanism appears across multiple connectomes

Keep this benchmark specification separate from future training inputs so we do not accidentally leak the answer.

11. TESTING

Create automated tests including:

* schema tests
* ingestion tests
* deterministic output tests
* duplicate handling
* invalid-edge tests
* neuron query tests
* subgraph query tests
* provenance/manifest tests
* a tiny synthetic fixture graph
* at least one integration/smoke test using a small real MaleCNS sample/cache

Run all tests.

Do not report completion with failing tests unless there is an external blocker you cannot resolve.

12. DATA QUALITY AUDIT

Independently inspect representative data.

Check examples manually through code.

Verify:

* neuron IDs actually exist
* edge directions are correct
* counts agree with official sources on sampled cases
* cell-type labels look sensible
* annotations are correctly joined
* no accidental integer/string corruption
* no accidental cross-version mixing

If Codex, neuPrint, official downloads, and publication statistics differ, investigate why.

Possible causes include:

* v0.9 vs v1.0
* neuron-pair edges vs individual synaptic contacts
* filtering
* segmentation changes
* aggregation
* annotation release differences

Document discrepancies rather than hiding them.

13. RESEARCH LOG

Maintain a research/engineering log containing:

* major decisions
* failed approaches
* useful documentation
* version discrepancies
* biological caveats
* technical caveats
* unresolved questions
* performance measurements
* important assumptions

This is specifically to stop future Claude sessions from repeating old work.

14. PHASE 0 REPORT

Create `PHASE0_REPORT.md` containing:

* repository location
* machine/environment summary
* exact dataset/version
* source URLs
* download/cache footprint
* schema
* graph size
* ingestion process
* validation results
* annotation coverage
* dataset limitations
* DNg100 findings
* benchmark readiness
* unresolved issues
* next recommended phase

15. SELF-AUDIT

Before declaring Phase 0 done, review your own work like a skeptical research engineer and computational neuroscientist.

Try to find:

* unreproducible state
* hidden dependencies
* data leakage
* bad biological assumptions
* silent type conversions
* inconsistent versions
* brittle paths
* missing tests
* mistaken synapse interpretation
* misleading terminology

Fix problems you find.

Rerun the test suite.

Rerun key data-validation commands.

Inspect representative records again.

SCIENTIFIC RULES

Treat scientific correctness as more important than making a flashy demo.

Never assume:

* synapse count = physiological synaptic strength
* anatomical connectivity = causal influence
* neurotransmitter prediction = absolute ground truth
* one fitted dynamical model = the actual biological brain
* one connectome = all flies
* a model explanation = biological proof

Keep observations, annotations, hypotheses, fitted parameters, and causal claims explicitly separated.

DO NOT BUILD YET

Do not yet build:

* full symbolic program synthesis
* formal verification engine
* whole-CNS simulator
* LLM explanation layer
* web frontend
* embodied FlyGym integration
* huge CUDA kernels
* arbitrary RL agent

Those come later.

PHASE 0 COMPLETION CRITERIA

Phase 0 is complete only when:

1. The project exists locally and is reproducible.
2. MaleCNS v1.0 structured connectome data are locally available/cached.
3. The data are normalized into BrainIR's schema.
4. A deterministic ingestion pipeline exists.
5. Provenance/versioning is explicit.
6. Automated validation/tests pass.
7. Basic graph queries work.
8. DNg100 and the future walking benchmark are locatable in the data.
9. The relevant biological literature has been summarized accurately.
10. A fresh future session can understand exactly what exists from the repository itself.

Do not stop early merely because the initial download or graph loader works.

AUTONOMY

Use your judgment aggressively.

Research first when necessary.
Experiment when uncertain.
Test assumptions.
Run code.
Inspect the results.
Change course if evidence suggests a better design.

Do not make the process unnecessarily long or repetitive.

Do not ask the user how to do things that you can determine yourself.

At the very end, give the user a short completion summary only:

* what you built
* where it is
* exact data/version acquired
* storage used
* tests/results
* DNg100 benchmark status
* genuine blocker if any
* single best next step

Everything else should be accomplished directly by you.
