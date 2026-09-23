<!-- ANSWER-KEY MATERIAL: names the published circuit. Never feed to BrainIR discovery. See benchmarks/dng100_walking_cpg/README.md -->

# Research note — Pugliese et al., "Connectome simulations identify a central pattern generator circuit for fly walking"

*Concise note (Phase 0, 2026-09-22). Exhaustive notes with verbatim quotes and code/data checks:
[`pugliese_walking_cpg_detailed_notes.md`](pugliese_walking_cpg_detailed_notes.md). Key claims below were re-checked
against the full text (PMC13142387 = bioRxiv v2). MaleCNS numbers were re-derived from MaleCNS v1.0 by
`benchmarks/dng100_walking_cpg/investigate_malecns.py`.*

**Citation.** Pugliese SM, Chou GM, Abe ETT, Turcu D, Lancaster JK, Tuthill JC\*, Brunton BW\*. bioRxiv
2025.09.12.675944 (v1 2025-09-12; v2 2026-04-30), doi:10.1101/2025.09.12.675944; CC BY-NC-ND 4.0. **Preprint only:**
no journal version as of 2026-09-22 (the PMC/PubMed record is the NIH preprint-pilot copy of v2). Code:
github.com/smpuglie/Pugliese_2026 (MIT per README; no LICENSE file). Data: Zenodo 10.5281/zenodo.22260924 (CC-BY).

## Biological question
Which cells form the central pattern generator (CPG) that produces the leg-motor rhythm of walking? The CPG circuit
for walking is "not known in any animal". The paper uses dynamical simulations constrained by VNC connectomes to
find neurons whose activity is sufficient and necessary for rhythmic leg motor-neuron output.

## Datasets and versions
| dataset | sex / region | how used | version |
|---|---|---|---|
| MANC | male VNC | main dataset; T1 (front-leg) motor subnetwork (4,604 neurons); full VNC (23,532) in Fig. 4 | **not stated** (IDs consistent with v1.2.x) |
| FANC | female VNC | T1-left network (803 neurons); signs from hemilineage + 4 manual overrides | not stated (CAVE) |
| MaleCNS ("mCNS") | male CNS | 4,310-neuron T1 network; **VNC ROIs only**; NT from `consensusNt` | not stated; extraction dated 2026-02-10, so before v1.0 (2026-06-08), presumably v0.9 |
| BANC | female CNS | 4,963-neuron network; VNC bounding box; verified-else-predicted NT | not stated |

**BrainIR verification (MaleCNS v1.0).** All MaleCNS body IDs used by the authors exist in v1.0 with the same types.
All 13 published MaleCNS edge counts among DNg100/E1/E2/I1/I2/E3 are reproduced **exactly** by v1.0
(`benchmarks/dng100_walking_cpg/malecns_v1.0_findings.md` §D). This circuit therefore did not change between the
authors' snapshot and v1.0.

## Simulation model
- Rate model per neuron: τ·dr/dt = max(r_max·tanh((a/r_max)(I + b·Σ_j w_ij r_j − θ)), 0) − r.
- w_ij = signed synapse count (presynaptic NT: ACh +; GABA and Glu −). There is a global scale b = 0.03. Edges are
  floored at ≥ 5 synapses in MANC and MaleCNS, with no floor in FANC and BANC.
- Gain is divided and threshold multiplied by the neuron's size relative to the network median (volume, or mesh area
  in FANC/BANC). The authors call this critical for robust oscillation.
- Parameters are drawn independently per replicate: a ~ 𝒩(1, 0.1), θ ~ 𝒩(7.5, 0.6), r_max ~ 𝒩(200, 10) Hz,
  τ ~ 𝒩(20, 2) ms (truncated). There is no noise, the network starts quiescent, and integration uses Dopri5 (JAX/Diffrax).
- No neuron has intrinsic bursting, plateaus or rebound. Rhythm can only be network-generated, by construction.

## Inputs
- A tonic step input to **one DNg100** (BDN2, a walking "command" DN): the one whose axon innervates the **left** leg
  neuropils. Its soma is in the right hemisphere (MaleCNS `10056`, instance DNg100_R; MANC 10093).
- The step amplitude is set per dataset (250 MANC / 150 FANC / 400 CNS datasets; arbitrary units).
- A preceding screen activated each of 933 excitatory DNs, 128 replicates each, with auto-tuned amplitude.
  - DNg100 ranks first as a **cell type**.
  - Individually, the two DNg100 neurons rank 3rd and 4th in v2 (they were 1st and 2nd in v1).

## Outputs and the rhythm criterion
- The readout is the leg motor neurons of the network.
- The "motor rhythmicity score" is based on autocorrelation peaks normalised to a sinusoid of the same period, on a
  0–1 scale. The score is averaged over active MNs, and a network counts as rhythmic at ≥ 0.5.
- Frequencies are read from the autocorrelation peak.

## Pruning / search procedure
- Each screen fixes one random parameter draw, then repeatedly silences (deletes) one interneuron. The neuron is
  chosen with probability ∝ 1/max rate.
- A deletion is kept if rhythmicity stays ≥ 0.5 and undone otherwise.
- A screen stops when no interneuron can be removed.
- There are 1,024 screens per dataset. MNs are never pruned.

## Discovered circuit (the benchmark answer)
- **MANC, modal circuit (636/1024):** E1 = IN17A001 (ACh), E2 = INXXX466 (ACh), I1 = IN16B036 (Glu).
  - The strongest links are E1→E2, E2→I1, I1→E1 and I1→E2.
  - DNg100 drives E1 only.
- **Other datasets.** The modal circuit differs by dataset:

  | dataset | modal circuit | screens |
  |---|---|---|
  | FANC | E1-E2-E3-**I2** (I2 = IN19A007, GABA) | 721/1024 |
  | MaleCNS | E1-E2-**I2** | 655/1024 |
  | BANC | E1-E2-**I2** | 681/1024 |

  In MaleCNS, E1-E2-I1 is the second most common circuit (181/1024).
- **Across all datasets:** E1, E2 and one of I1/I2 appear in 3,521 of 4,096 screens (86%).
- **Mechanism (proposed):** the rhythm is a network oscillator of the E–E–I type (a minimal oscillator in
  threshold-linear networks). The E1-E2-I1 motif has the highest intrinsic frequency (~14 Hz) of 21,544 E–E–I motifs
  in the MANC front-leg network.
- **Six legs:** one copy of each type exists per leg neuropil. In MaleCNS v1.0 every type has exactly 6 copies, one
  per leg. DNg100 drives E1 in all three ipsilateral-to-axon legs (v1.0: 155/167/140 synapses).

## Interventions (in silico)
- Deleting E1 or E2 abolishes the rhythm in all four datasets. Deleting I1 or I2 alone does not: the inhibition is
  redundant.
- Adding ≤ 10% synaptic-count noise leaves rhythms intact.
- Removing size normalisation abolishes robust oscillation.
- Frequency rises with DNg100 drive in the full network, but not in the isolated 3-neuron core.
  - The paper states this qualitatively (Fig. 2g; ED Fig. 4a).
  - Median values recomputed by the research agent from the authors' figure CSVs, **not quoted from the paper**:
    ~9.6 → 12.7 Hz for I = 220 → 340.
- A second pathway, DNb08, drives rhythm via E4 (IN03A006) and E5 (INXXX464) onto the same core. This works in
  3 of 4 datasets; it fails in BANC.

## Cross-connectome validation
- Pruning was re-run independently per dataset. E1 and E2 recur everywhere; the inhibitory partner varies.
- The datasets differ in preprocessing (synapse floor, size metric, NT source, subnetwork extent).
- MaleCNS and BANC restrict to VNC synapses.

## Wet-lab validation
- **DN level only.**
  - DNg100 optogenetic activation in decapitated flies: stronger light gave faster walking and higher step frequency
    (n = 7; low vs high p = 0.042; medium vs high n.s.).
  - DNb08 activation produced rhythmic, search-like leg movements (n = 10).
- **No experiment has manipulated E1, E2, I1 or I2.** The authors state that new driver lines are needed.
- The Sapkal et al. 2026 follow-up (bioRxiv 10.64898/2026.04.29.721658) shows per-leg central rhythms (~11 Hz in air)
  but does not test these interneurons. Its connectivity-based motif shares E1, E4 and E5 (expanded: E2, I2), and it
  proposes additional cells (IN12B003, IN09A002). Those two are among the top DNg100 targets in MaleCNS v1.0.

## Known limitations (authors')
- No gap junctions, neuromodulation, receptor kinetics, sensory feedback or biomechanics.
- Some walking muscles (e.g. the main tibia flexors) stay silent in the model.
- No tripod or interleg coordination.
- Frequency scaling needs cells beyond the core circuit.
- The results differ across datasets (e.g. DNb08 in BANC).
- The screen can miss rhythms that rely on intrinsic cellular properties.
- The rhythm criterion is deliberately permissive.

## Ground truth vs modelling assumption
| kind | items |
|---|---|
| **Observation (EM anatomy)** | synapse counts and locations; neuron sizes; morphology |
| **Curated annotation** | cell types (MANC-style), hemilineages, sides; motor-module labels |
| **ML prediction** | neurotransmitter identities (and hence signs) |
| **Assumption** | sign = f(predicted NT), with Glu as inhibitory everywhere; weight ∝ synapse count with one global b; excitability ∝ 1/size; rate neurons with no intrinsic dynamics; parameter distributions; tonic single-DN drive; deletion = silencing; rhythmicity ≥ 0.5 = "rhythmic" |
| **Model output (not biology)** | the minimal circuits; necessity/sufficiency of E1/E2 "in silico"; ~14 Hz intrinsic frequency |
| **Experimental ground truth** | DNg100 activation speeds walking and raises step frequency; DNb08 activation evokes rhythmic leg movements; per-leg rhythms persist with reduced proprioception (follow-up) |

**Implication for BrainIR:** the E1/E2/(I1|I2) circuit is a *model-derived hypothesis* that is robust across four
connectomes. It is not experimentally established ground truth. A BrainIR rediscovery would show agreement with a
published analysis. It would not be validation against biology. Independent success criteria are defined in
[`benchmarks/dng100_walking_cpg/SPEC.md`](../../benchmarks/dng100_walking_cpg/SPEC.md), which is kept separate from
any future training inputs.
