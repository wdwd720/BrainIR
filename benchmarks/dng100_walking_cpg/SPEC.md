# BrainIR benchmark B1 — DNg100-driven walking rhythm (CPG) — specification

> ANSWER-KEY DIRECTORY. This spec names what the evaluator may compare against; it is written so that the
> *inputs* section can be handed to a discovery system without the rest of this directory.

Status: defined in Phase 0 (2026-09-22). Primary dataset: MaleCNS v1.0 (`male-cns:v1.0`). The published reference
solution is Pugliese et al. (bioRxiv 2025.09.12.675944 v2); see `answer_key.json`.

## 1. Question posed to BrainIR

Given a connectome, the descending neuron that is driven, and the motor neurons that are read out: **produce a
compact, executable, human-readable program** that explains how tonic drive to that descending neuron generates
rhythmic leg motor output. The program's variables must map onto identified neurons, and it must make causal
predictions for interventions (silencing and activation).

## 2. Information budget (what a discovery run MAY receive)

The run must use the same evidence as the original analysis, or less.

| item | tier A (blind) | tier B (labelled) |
|---|---|---|
| connectome graph: neuron IDs, synapse counts, per-neuropil counts, sizes | yes | yes |
| predicted neurotransmitters (consensus) and derived sign hypotheses | yes | yes |
| stimulus: the DNg100 neuron innervating the LEFT leg neuropils (MaleCNS v1.0 `10056`) | yes | yes |
| readout: leg motor neurons (`super_class=vnc_motor`, `sub_class` in fl/ml/hl), optionally restricted to the front-left leg | yes | yes |
| objective: "rhythmic MN output"; generic walking facts from literature *not derived from this paper* (e.g. step frequency ~7–15 Hz) | yes | yes |
| superclass, side, soma neuromere, hemilineage letters | yes | yes |
| VNC interneuron **type names** (e.g. `INnnXnnn`) and synonyms | **no — replaced by opaque tokens** | yes |

**Forbidden in every tier:**

- anything under `benchmarks/`, and `research/literature/pugliese*`;
- the paper, its figures and tables, and its code or data (Zenodo, GitHub);
- the Sapkal et al. 2026 candidate lists;
- any prompt or retrieval that names the published cell types or body IDs (listed in `tests/test_leakage_guard.py`).

Tier A is the scientifically stronger setting: type names can carry hemilineage and literature priors, and would let
a language model retrieve the published answer.

## 3. Reference answer (held out; evaluation only)

- **Published modal circuit (in silico, per dataset):** see `answer_key.json`.
  - MaleCNS: E1-E2-I2 (655/1024 screens), then E1-E2-I1 (181/1024).
  - MANC: E1-E2-I1 (636/1024).
- **MaleCNS v1.0 neuron IDs (front-left, T1L copies):**
  - E1 `800173` (IN17A001), E2 `800863` (INXXX466)
  - I1 `801884` (IN16B036), I2 `800374` (IN19A007)
  - E3 `800216`, E4 `800663`, E5 `800286`
  - These were verified to exist, with unchanged types and identical connectivity to the paper's matrix, in
    `malecns_v1.0_findings.md`. Six-leg copies are in `tables/circuit_types_all_copies.csv`.
- **Nature of the reference.** It is a *model-derived* hypothesis, robust across four connectomes; it is not
  experimentally established. No wet-lab manipulation of E1/E2/I1/I2 exists (as of 2026-09).

## 4. Success levels (report every level separately; never collapse them)

| level | criterion | evidence required |
|---|---|---|
| **S0 functional** | The BrainIR program, driven only through the stimulus neuron, produces rhythmic leg-MN output: rhythmicity ≥ 0.5 under the paper's autocorrelation score (re-implemented in evaluation code), dominant frequency within 5–20 Hz, and robust over ≥ 100 random parameter draws of the program's own model family. | simulation traces + score distribution |
| **S1 compact & executable** | The core program has ≤ 10 interneuron state variables plus the DN and MN readouts, runs standalone, and reproduces S0. Size is reported as #variables, #edges and #parameters. | program source, hash |
| **S2 neuron-role overlap** | The program's variables map to neuron IDs. **Excitatory core recall:** fraction of {E1, E2} (T1L copies) present in the core. **Inhibitory slot:** satisfied if I1 **or** I2 is present, since the reference itself varies. Report Jaccard(core, {E1, E2, I1\|I2}) and precision (fraction of core neurons that are reference members E1–E5, I1, I2). | mapping table |
| **S3 held-out interventions** | Predictions are **pre-registered before** the answer key is opened, then compared with the paper's in-silico results: (i) deleting E1 → rhythm lost; (ii) deleting E2 → rhythm lost; (iii) deleting I1 alone → rhythm persists; (iv) deleting I2 alone → rhythm persists; (v) DNb08 drive (4 neurons) → rhythmic output that depends on E4/E5 (MaleCNS: yes); (vi) frequency increases with drive in the full network but not in the isolated core. Score = fraction correct. | pre-registration hash + results |
| **S4 cross-connectome invariance** | The same abstract mechanism (graph-isomorphic core up to relabelling; same sign pattern) is recovered **independently** in ≥ 2 connectomes (e.g. MaleCNS v1.0 and MANC v1.2.x, BANC or FANC), and the neuron mappings agree with independent cross-dataset matches (e.g. MaleCNS `manc_body_id`). | per-dataset runs |
| **S5 biological validation** | Future only: predictions confirmed by experiments (e.g. E1/E2 silencing abolishes DNg100-evoked stepping). Cannot be claimed from this benchmark. | wet-lab data |

**Independent-success claim.** BrainIR may claim that it *independently rediscovered* the published oscillator only
if S0, S1 and S2 hold **in tier A**, with the information budget respected and logged (§5), and the result beats
the baselines in §6. S3 and S4 strengthen the claim. Even then, the claim is agreement with a published model
analysis, not biological proof.

## 5. Protocol (anti-leakage)

1. The discovery code never imports `benchmarks/` or `research/`; this is enforced by `tests/test_leakage_guard.py`.
2. Tier A runs replace VNC interneuron `cell_type` and `instance` with salted hashes. The salt is stored outside
   the run.
3. Before evaluation:
   - freeze the discovery artefact (program + neuron mapping + intervention predictions);
   - record its SHA-256 and the exact list of inputs (dataset manifest hash, columns used).
4. Only then run the evaluation, which reads `answer_key.json` and `malecns_v1.0_mapping.json`. Store the
   evaluation output next to the frozen hashes.
5. Any human-in-the-loop hint counts as input and must be logged.

## 6. Baselines a result must beat (difficulty notes)

The reference circuit is **not** the strongest pathway from the stimulus, but once one member is known the rest is
the strongest-edge neighbourhood. MaleCNS v1.0 numbers (`malecns_v1.0_mapping.json` → `recurrence`):

- E1 is only the **#11** target of the stimulated DNg100 (669 targets with ≥ 5 synapses). DNg100 supplies just 1.7%
  of E1's input.
- E2 is E1's **#1** output, and E1 is E2's **#1** input.
- I1 is E1's **#1** input overall and I2 is its **#2**. They are also E1's top two inhibitory inputs.

**Consequence:** the hard part is selecting E1 among DNg100's targets. A "top-k DNg100 targets + strongest reciprocal
loop" heuristic with k ≥ 11 would already recover E1/E2/I1/I2. BrainIR must therefore demonstrate value beyond such
baselines: executable dynamics, intervention predictions, cross-dataset invariance, and a *reason* for choosing E1.

Required baselines, all evaluated with S0–S3 under the same model family:

- (a) top-k DNg100 targets (k matched to BrainIR's core size);
- (b) greedy strongest-path expansion from DNg100 toward MNs;
- (c) random connected subnetworks of DNg100's 2-hop VNC neighbourhood with a matched E/I ratio;
- (d) the full front-leg network without compression, as an upper bound for S0.

## 7. Known confounds

- **Sign rule.** Glutamate is treated as inhibitory (GluCl). This is an assumption: I1 is glutamatergic.
- **NT predictions.**
  - MaleCNS consensus NT includes expert overrides that are not in the `ground_truth` column (see the validation
    report).
  - I2's predicted GABA probability in MANC is 0.69.
- **Incompleteness.** Only ~33% of DNg100's output connections reach identified neurons in MaleCNS v1.0. Postsynaptic
  completeness is low, so weights are anatomical lower bounds.
- **Region restriction.** The paper restricted MaleCNS to VNC synapses. For these circuit edges all synapses are in
  the VNC anyway (v1.0 check).
- **Size normalisation.** The paper's result depends on size normalisation. A BrainIR model family should state
  whether it uses neuron size.
