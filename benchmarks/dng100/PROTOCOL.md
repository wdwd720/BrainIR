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
`benchmarks/dng100_walking_cpg/`, `research/literature/`, `goal1.md`, `goal2.md`, `PHASE0_REPORT.md` §13, any evaluation
output, any human hint about the answer. Generic prior knowledge that is not about this circuit (e.g. "insect walking
steps at 7–15 Hz", "GABA is inhibitory") is allowed and must be declared in `MethodInfo.description`.

Tier A is the scientifically meaningful setting: type names and body ids appear in the paper's tables, so a
literature-aware method (human or language model) could retrieve the answer from them.

## 3. Running a method

1. Verify the bundle: `verify_bundle()` (every file hash equals `manifest.json`; `bundle_sha256` equals the one in
   `BENCHMARK_LOCK.json`).
2. Run through `cleanroom/run_method.py`: the bundle is copied to a fresh directory, the environment is stripped, the
   method runs as a subprocess with `BRAINIR_BUNDLE`, `BRAINIR_NETWORK`, `BRAINIR_OUT`, `BRAINIR_SEED`; imports of
   `benchmarks`, `oracle` or `evaluate` are refused; each prediction is validated against the schema and hashed
   (`run_record.json`).
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
sufficiency pass) and its essentiality claims are correct, and the result beats every baseline in
`baselines/results/` and lies outside the null distributions (`baselines/results/null_distributions.md`). Tier B
results are reported but cannot support an independence claim.

## 6. Freezing and versioning

`freeze.py` writes `BENCHMARK_LOCK.json` (hashes of both bundles, the oracle, the evaluator, the clean-room tools, the
baselines, the node lists, the dataset manifests, and the code commit) and the git tag `dng100-benchmark-v1` marks the
frozen state. Any change to the bundles, oracle or evaluator requires a new benchmark version; results are only
comparable within one version.
