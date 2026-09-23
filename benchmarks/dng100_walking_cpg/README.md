# Benchmark: DNg100-driven walking rhythm (CPG) — ANSWER KEY DIRECTORY

> **ANSWER KEY — DO NOT USE AS INPUT.** This directory contains the *published solution* of the benchmark
> (the cell types and body IDs of the minimal rhythm-generating circuits reported by Pugliese et al.) and
> the data-verification work that locates them in MaleCNS v1.0. It exists so that BrainIR can later be
> **evaluated** against the literature. It must never be read by, imported into, embedded in, or used to
> tune any BrainIR discovery/synthesis algorithm, prompt, feature, prior or loss.

## Leakage policy

1. `src/brainir/` must not import from `benchmarks/` or `research/`, and must not contain the answer-key
   type names or body IDs. Enforced by `tests/test_leakage_guard.py`.
2. A future discovery run may receive only what the original analysis received (or less): the connectome
   (+ predicted neurotransmitters), the identity of the stimulated neuron (DNg100) and the readout
   population (leg motor neurons), and a rhythmicity objective. See `SPEC.md` for the exact allowed inputs.
3. Evaluation code that reads `answer_key.json` must live in this directory (or a future `evaluation/`
   package) and run *after* the discovery artefact is frozen (hash it first; record the hash in the result).
4. **Answer-bearing files.** These must be excluded from any context, retrieval corpus or prompt given to a
   discovery system:
   - everything in `benchmarks/` except the two public bundles `benchmarks/dng100/public/` and
     `benchmarks/dng100/public_blind/` (which are the ONLY inputs a method receives; `benchmarks/dng100/PROTOCOL.md`);
     in particular `benchmarks/dng100/oracle/`, `benchmarks/dng100/baselines/results/eval/` and
     `benchmarks/dng100/baselines/results/null_distributions.*`;
   - `research/literature/` (Pugliese notes);
   - `goal1.md` and `goal2.md` (the phase specs name the published cell types);
   - the "DNg100 benchmark" section of `PHASE0_REPORT.md`, and `PHASE1_REPORT.md` (§7–§8).

   `README.md`, `CLAUDE.md`, `docs/`, `src/` and `research/data_ecosystem.md` are kept free of answer-key IDs and
   type names. `tests/test_leakage_guard.py` checks `src/`.

## Files

| file | content |
|---|---|
| `README.md` | this policy |
| `SPEC.md` | benchmark definition: task, allowed inputs, held-out interventions, success criteria |
| `answer_key.json` | published circuits per dataset (types, IDs as published, provenance) |
| `investigate_malecns.py` | reproducible data-verification script (MaleCNS v1.0) |
| `malecns_v1.0_findings.md` | output of the investigation: DNg100 and circuit neurons located in v1.0 |
| `malecns_v1.0_mapping.json` | machine-readable mapping of published neurons -> MaleCNS v1.0 body IDs |
| `reproduce_manc_connectivity.py`, `manc_reproduction.md`, `tables/` | Phase 1: the authors' MANC / MaleCNS matrices vs BrainIR's rebuilt datasets (pair-exact reproduction) |
| `reproduce_dynamics.py` | DNg100 stimulation replicates with BrainIR's simulator (`paper_network()` builds the published networks) |
| `reproduce_interventions.py` | silencing / keep-only claims (uses the oracle; `--backend modal`) |
| `reproduce_pruning.py` | 1,024 stochastic sufficiency screens vs the published circuit prevalence (`--backend modal`) |
| `reproduce_dn_screen.py` | the descending-neuron activation screen (933 DNs; `--backend modal`) |
| `robustness_experiments.py` | dt-convergence, parameter / input / weight-noise sweeps, negative controls |
| `cross_connectome_eval.py` | mapping-table correspondence in both directions + functional transfer of the modal circuit |
| `results/` | small JSON/MD outputs of the above (answer-bearing: they name the published circuit) |
