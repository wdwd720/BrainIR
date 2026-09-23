# dng100-benchmark-v1 — blind discovery protocol

This document is the operating procedure for evaluating a circuit-discovery method (BrainIR's own or anyone else's)
on the DNg100 walking-rhythm benchmark without leaking the reference solution into the method. It is part of the frozen
benchmark (hashed in `BENCHMARK_LOCK.json`).

## 1. What the benchmark asks

Given a signed synapse-count network derived from a Drosophila connectome, a stimulus (constant current into one
descending neuron of type DNg100) and a readout population (front-leg motor neurons), all under a fixed firing-rate
model: **name the mechanism** — the interneurons through which the stimulus generates the motor rhythm, their
excitatory/inhibitory roles, which of them are individually essential, the rhythm frequency, and (across networks)
which neurons correspond. Output = one `BrainIRMechanismPrediction` (schema 1.0.0) per network.

Networks: `manc_v1.2.1` (primary; MANC neuPrint v1.2.1, rebuilt from public synapses), `manc_v1.2.3`, `male-cns_v1.0`
(VNC synapses only). Published node lists define membership; everything else is derived from BrainIR builds
(`benchmarks/dng100/nodes/README.md`, `networks/*/network.json`).

## 2. Information budget

| tier | a method receives | it never receives |
|---|---|---|
| **A (blind)** | `public_blind/`: network graphs with signed counts, NT labels and signs, sizes, side, soma neuromere, role class; stimulus and readout definitions; the model + metric definitions; interneuron types/instances replaced by salted tokens; neuron ids positional | cell-type names of interneurons, dataset body ids, anything outside the bundle |
| **B (labelled)** | `public/`: the same with the release's cell types, instances and body ids | anything outside the bundle |

Forbidden in both tiers: the paper (text, figures, tables, code, data), `benchmarks/dng100/oracle/`,
`benchmarks/dng100_walking_cpg/`, `benchmarks/dng100/baselines/results/`, `research/literature/`, `goal1.md`, `goal2.md`,
`PHASE0_REPORT.md` §13, `PHASE1_REPORT.md`, any evaluation output, any human hint about the answer. Generic prior knowledge that is not about this circuit (e.g. "insect walking
steps at 7–15 Hz", "GABA is inhibitory") is allowed and must be declared in `MethodInfo.description`.

Tier A is the scientifically meaningful setting: type names and body ids appear in the paper's tables, so a
literature-aware method (human or language model) could retrieve the answer from them.

**What tier A does and does not hide.** It hides *identifiers*: interneuron names are salted tokens and neuron ids are
positions in a salted random order (the position → body-id map lives in `oracle/tier_a_ids/`). It does not, and cannot,
hide *structure*: exact synapse counts and exact segment sizes are the benchmark's input, and they fingerprint every
neuron against the public neuPrint databases and against tier B. A method that looks anything up outside the bundle
(neuPrint, the paper's repository, tier B, this repository) has left the budget, whatever it found. Blinding therefore
protects against inadvertent name recall; adherence to the budget is a declared, auditable input list
(`MethodInfo.inputs`), not a cryptographic guarantee. The two MANC networks (v1.2.1, v1.2.3) share identical synapses
and node lists and differ only in annotations; agreement between them is not cross-connectome evidence — only MANC ↔
MaleCNS pairs are.

## 3. Running a method

1. Verify the bundle: `verify_bundle()` (every file hash equals `manifest.json`; `bundle_sha256` equals the one in
   `BENCHMARK_LOCK.json`).
2. Run through `cleanroom/run_method.py`: the bundle is copied to a fresh directory, the environment is stripped, the
   method runs as a subprocess with `BRAINIR_BUNDLE`, `BRAINIR_NETWORK`, `BRAINIR_OUT`, `BRAINIR_SEED` under the
   audit-hook sandbox `cleanroom/_sandbox.py` (file access confined to the bundle copy, its output directory, the Python
   installation and temp — the repository, the oracle, tier B and user files are unreadable; no subprocesses, sockets or
   ctypes calls; child interpreters inherit the hook); imports of `benchmarks`, `oracle` or `evaluate` are refused
   statically; each prediction is validated against the schema and hashed together with the method file, its arguments
   and the sandbox (`run_record.json`). The sandbox stops inadvertent and casual leakage; it is not OS-level isolation.
3. The method declares its inputs and compute in `MethodInfo`; any deviation from the budget disqualifies the run.
4. **Freeze before evaluation**: record the prediction hashes and the bundle hash (the run record) *before* the
   evaluator is invoked. Pre-registered intervention predictions (`essential` claims, `dynamics`) are part of the frozen
   prediction.

## 4. Evaluation

`evaluator/evaluate.py` is the only code that reads the oracle. It reports **separate metric families** and no
aggregate number:

| family | what it measures | oracle needed |
|---|---|---|
| structural | exact-neuron overlap with the published core (excitatory core recall over E1/E2, inhibitory slot I1\|I2, precision vs all published labels, Jaccard, compactness) | yes (paper_simulation) |
| type_role | the same at cell-type level (credits same-type neurons such as contralateral copies) + role agreement | yes |
| functional | **oracle-free**: sufficiency (keep only the predicted core + stimulus + readout → is the rhythm still produced?), necessity (silence each claimed neuron → does the rhythm vanish as claimed?), predicted vs simulated frequency / active MNs | no (simulation) |
| mechanism | graph sanity of the claimed loop, sign consistency with the network's NT labels, compactness | no |
| cross_connectome | published labels recovered in all networks; claimed correspondences vs the oracle's label correspondence | yes |
| robustness | stability of the sufficiency result under weight noise and doubled parameter spread | no |

Every evidence item in the oracle carries a level (`paper_simulation`, `brainir_simulation`, `wet_lab`,
`expert_interpretation`). No interneuron of this circuit has wet-lab evidence; structural agreement with the oracle is
agreement with a *model-derived* result, not biological proof — the functional family is therefore the primary
scientific signal.

## 5. What may be claimed

A method "independently recovers the published mechanism" only if, **in tier A**, with the budget respected and
logged: excitatory core recall = 1, the inhibitory slot is filled, the predicted core is sufficient (functional
sufficiency pass) and its essentiality claims are correct, and the structural result lies outside the null
distributions (`baselines/results/null_distributions.md`, empirical p < 0.05 against the matched null). Tier B
results are reported but cannot support an independence claim.

**Baselines set the bar, family by family** (`baselines/results/baselines_summary.md`). The structural heuristics
(degree, PageRank, betweenness, community, k-core, recurrence, statistical motif, random) recover at most one core
neuron and never a sufficient core. The simulation-guided elimination baseline (`greedy_prune_sim`) recovers the full
core in every network in tier A — the published answer was itself produced by simulation-guided pruning of this model,
so recovering it by search is expected. A method is judged against that baseline on the axes the structural family
does not see, each reported separately: simulation budget (number of simulated seconds; `MethodInfo.compute`),
robustness of its core under parameter spread and weight noise (robustness family), mechanism explanation (mechanism
family), cross-connectome transfer (cross_connectome family; MANC ↔ MaleCNS only) and independence from the specific
rate model (declared in `MethodInfo`). "Beats a baseline" means better on a named family with the same replicate
count and seeds; no family may be traded for another and no aggregate exists.

## 6. Freezing and versioning

`freeze.py` writes `BENCHMARK_LOCK.json` (hashes of both bundles, the oracle, the evaluator, the clean-room tools, the
baselines, the node lists, the dataset manifests, and the code commit) and the git tag `dng100-benchmark-v1` marks the
frozen state. Any change to the bundles, oracle or evaluator requires a new benchmark version; results are only
comparable within one version.
