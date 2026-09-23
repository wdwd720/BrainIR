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
4. `research/literature/pugliese_walking_cpg_detailed_notes.md` also contains the answer; treat it as
   answer-key material too.

## Files

| file | content |
|---|---|
| `README.md` | this policy |
| `SPEC.md` | benchmark definition: task, allowed inputs, held-out interventions, success criteria |
| `answer_key.json` | published circuits per dataset (types, IDs as published, provenance) |
| `investigate_malecns.py` | reproducible data-verification script (MaleCNS v1.0) |
| `malecns_v1.0_findings.md` | output of the investigation: DNg100 and circuit neurons located in v1.0 |
| `malecns_v1.0_mapping.json` | machine-readable mapping of published neurons -> MaleCNS v1.0 body IDs |
