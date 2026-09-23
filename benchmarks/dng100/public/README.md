# dng100-benchmark-v1 — public bundle (tier B)

## Task

Each network below is a signed synapse-count matrix derived from a Drosophila connectome, a constant-current stimulus
into one descending neuron (`stimulus.json`) and a readout population of front-leg motor neurons (`readout.json`).
Under the firing-rate model in `model_config.json`, the stimulus produces rhythmic motor output in most parameter
replicates. **Identify the mechanism**: the set of interneurons through which the stimulus generates the rhythm, the
role (excitatory/inhibitory) of each, which of them are individually essential, the rhythm's frequency, and — across
the networks — which neurons correspond to each other. Submit one `BrainIRMechanismPrediction` per network
(`brainir.benchmark.prediction`, schema 1.0.0).

## Rules

- Use only the files in this bundle plus the `brainir` library (simulator, metrics, prediction schema).
- Do not consult literature, external databases or any file outside this bundle about these circuits.
- Record every input you used and your compute in `MethodInfo`.

## Files

| path | content |
|---|---|
| `manifest.json` | bundle id, format version, creation time, code commit, SHA-256 of every file |
| `model_config.json` | the rate model, its parameter distributions, integration settings and the rhythm metric |
| `networks/<name>/neurons.parquet` | one row per neuron: position, source_id, labels, role class, NT label used for the sign, sign, size, stimulus/readout flags |
| `networks/<name>/edges.parquet` | pre -> post pairs with synapse_count and signed_weight (>= 5 synapses, autapses removed) |
| `networks/<name>/network.json` | how the network was derived from the connectome release (provenance hashes) |
| `networks/<name>/stimulus.json`, `readout.json` | stimulated neuron(s) and current; readout neurons |

## Networks

| name | dataset | neurons | edges | Σ synapses | stimulus | readout |
|---|---|---|---|---|---|---|
| manc_v1.2.1 | manc:v1.2.1 | 4604 | 196359 | 3815864 | [10093] @ 250.0 | 144 MNs |
| manc_v1.2.3 | manc:v1.2.3 | 4604 | 196359 | 3815864 | [10093] @ 250.0 | 142 MNs |
| male-cns_v1.0 | male-cns:v1.0 | 4309 | 118745 | 2185576 | [10056] @ 400.0 | 130 MNs |

## Anatomy is not physiology

Synapse counts are anatomical estimates from EM; neurotransmitter labels are machine predictions; signs follow a
stated rule (cholinergic +, GABAergic/glutamatergic −, others 0). The model is a hypothesis, not a measurement.
