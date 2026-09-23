# BrainIR ingestion validation - male-cns:v1.0

**Summary:** 53 pass, 0 fail, 1 warn, 19 info

## Context

```json
{
  "dataset": "male-cns",
  "version": "v1.0",
  "pipeline": "brainir.ingest.malecns@1.0.0",
  "git": {
    "commit": "8cf067322ea23496739abd3120e072d8c2a429d5",
    "src_dirty": true,
    "pipeline_code": {
      "combined_sha256": "ab0e92f8a991e1b10de10879a2e518cf3e9c32600d0553113d51719cae4c2758",
      "files": {
        "ingest/common.py": "12630e70eb3bfad0b984ec9eead6a6d5089ed55a579d34644cf043501a3b7bb1",
        "ingest/malecns.py": "35ea4d371889c774758e3be86e205b7bb42cf4ce0e2afc5b3a2430734567e4df",
        "ingest/manc.py": "c2c95ceaae0bc6138af3be97f2b87f818858ed4c4746336b2f3365ee9b7fc5c6",
        "io.py": "caef03300a0021f9f05eee4bef7d06b935d1a3d45b2d26d365def931f127d91c",
        "schema/tables.py": "98dc8ae7dc0b6dcb9789388df4d2a96923ab244b7a1376d2a5c1dbf5d56b7652",
        "schema/vocab.py": "63c9f8da8bcf9bd3ed25a914582d154f9a9f52ed92a7957b5f01d27f0b55b349",
        "schema/evidence.py": "ea3ec89660d7154d5c4182a10ef48d270e9ead8ad8fc05c03f137ed237bf0407",
        "sources/registry.py": "470bb9c6a6e82d1c2e486b964894566c6c08cb0fe185e6d0b5ea1923d4d6f84d",
        "validation.py": "2c16125a8ad1ceb30dd6c3e0bd0ac2b807e2eb5be4c5397df8e8d0ffc9773f61",
        "paths.py": "d1605ad6a2a90398bcac987703f3854601f7b57bfb15d600d0419836d3ca1c42"
      }
    }
  }
}
```

## provenance

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `provenance.acquisition_dataset` | ["male-cns", "v1.0"] | ["male-cns", "v1.0"] | Acquisition log dataset/version match the registry. |
| PASS | `provenance.raw_inputs_verified` | all ok | true | Every raw input exists, has the pinned size, and its recorded checksums match registry pins (CRC32C for all, MD5 where available, GCS generation). |
| PASS | `provenance.meta_dataset_tag` | ["male-cns", "v1.0"] | ["male-cns", "v1.0"] | neuPrint :Meta dataset/tag equal the requested dataset/version (no cross-version mixing). |
| info | `provenance.meta_identity` | {"uuid": "98d6995edd46478f896544dceaa6eab1", "latestMutationId": 1006591300, ... |  | neuPrint snapshot identity (DVID uuid, mutation id, last edit). |
| info | `provenance.synapse_thresholds` | {"postHighAccuracyThreshold": 0.5, "preHPThreshold": 0.0, "postHPThreshold": ... |  | Synapse confidence thresholds declared by neuPrint (weight: post>=postHighAccuracyThreshold; weightHP: post>=postHPThreshold). Flat files are pre-filtered at conf>=0.5 on BOTH pre and post. |

<details><summary><code>provenance.raw_inputs_verified</code> details</summary>

```json
{
  "inputs": [
    "neuprint_meta_json",
    "body_annotations",
    "body_neurotransmitters",
    "neuprint_neurons",
    "neuprint_connections",
    "flat_connectome_weights",
    "syn_partners"
  ]
}
```
</details>

## uniqueness

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `neuropils.hierarchy_is_dag` | 9 |  | ROIs listed under more than one parent in the source hierarchy (merged into one row each; 'parent' = roiInfo parent, 'all_parents' keeps every parent). |
| PASS | `neuropils.top_level_region_consistent` | {} | true | Every ROI has a single top-level region across all its hierarchy paths. |
| PASS | `ids.neuropils.unique` | 0 | 0 | ROI names are unique in the output catalogue. |
| PASS | `ids.neurons.unique` | 0 | 0 | Neuron IDs unique. |

<details><summary><code>neuropils.hierarchy_is_dag</code> details</summary>

```json
{
  "multi_parent_rois": {
    "CA(L)": [
      "CentralBrain",
      "MB(L)"
    ],
    "CA(R)": [
      "CentralBrain",
      "MB(R)"
    ],
    "IB": [
      "CentralBrain",
      "INP"
    ],
    "ICL(L)": [
      "CentralBrain",
      "INP"
    ],
    "ICL(R)": [
      "CentralBrain",
      "INP"
    ],
    "SCL(L)": [
      "CentralBrain",
      "INP"
    ],
    "SCL(R)": [
      "CentralBrain",
      "INP"
    ],
    "PED(L)": [
      "CentralBrain",
      "MB(L)"
    ],
    "PED(R)": [
      "CentralBrain",
      "MB(R)"
    ]
  }
}
```
</details>

## referential

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `neuropils.roiinfo_parent_consistent` | {} | true | The roiInfo 'parent' of each ROI is one of its hierarchy parents. |
| PASS | `referential.primary_rois_in_hierarchy` | [] | true | All primary ROIs exist in the ROI hierarchy. |
| info | `neuropils.stats_only_rois` | 4 |  | ROIs with statistics in roiInfo but absent from the hierarchy (kept, in_hierarchy=False). |
| PASS | `referential.neurons_in_neuprint` | 0 |  | Neurons missing from the neuPrint segment table (non-synaptic bodies are not exported by neuPrint). |
| PASS | `referential.raw_edges_reference_segments` | 0 | 0 | Every endpoint of every raw connection exists in the neuPrint segment table. |
| PASS | `referential.edges_reference_neurons` | 0 | 0 | Every edge endpoint is a neuron. |

<details><summary><code>neuropils.stats_only_rois</code> details</summary>

```json
{
  "rois": [
    "AL-unspecified(L)",
    "AL-unspecified(R)",
    "gL-unspecified(L)",
    "gL-unspecified(R)"
  ]
}
```
</details>

## coverage

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `coverage.primary_roi_synapse_fraction` | {"pre": 0.999301, "post": 0.99951} |  | Fraction of all T-bars / PSDs located inside some primary ROI (rest -> '<unassigned>'). |
| info | `coverage.neurons_without_nt_row` | 178 |  | Neurons absent from the NT table (no T-bars => no prediction). |
| PASS | `consistency.neuron_neuropils_not_exceeding_totals` | 0 | 0 | Per-neuron primary-ROI pre/post counts never exceed the neuron's totals. |
| PASS | `consistency.connection_neuropils_not_exceeding_weight` | 0 | 0 | Per-edge primary-neuropil counts never exceed the edge weight. |
| info | `coverage.connection_unassigned` | {"edges": 370, "synapses": 479} |  | Edges with synapses outside primary ROIs (stored as neuropil '<unassigned>'). |
| info | `coverage.annotation_fields` | {"cell_type": 0.9868, "instance": 0.9602, "cell_class": 0.159, "sub_class": 0... |  | Fraction of neurons with each annotation populated. |
| info | `coverage.by_superclass` | [{"super_class": "ENS", "typed": 0.0, "nt_known": 0.0, "n": 50}, {"super_clas... |  | Per-superclass neuron count, fraction typed, fraction with a known (non-unclear) consensus NT. |
| info | `coverage.nt_consensus_distribution` | {"acetylcholine": 103720, "glutamate": 29302, "gaba": 22069, "histamine": 789... |  | Distribution of consensus NT over neurons. |

## ingestion

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `rows.raw.body_annotations` | 211577 |  | Rows in the raw body annotation table. |
| info | `rows.raw.body_neurotransmitters` | 1835518 |  | Rows (bodies) in the raw NT table. |
| info | `rows.neurons` | 166700 |  | Neurons = bodies with a superclass (source definition). |
| info | `rows.raw.neuprint_neurons` | {"n_segments": 88404403, "n_neuron_label": 176422} |  | Synaptic segments in neuPrint and how many carry the :Neuron label. |
| info | `rows.raw.neuprint_connections` | 151856684 |  | Rows in the raw neuPrint connection table (segment pairs). |
| info | `rows.connections` | 25582938 |  | Neuron->neuron edges retained (both endpoints are neurons). |

## types

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `types.annotation_float_ids_integral` | ["group", "mancBodyid", "mancGroup", "mancSerial", "mcnsSerial", "assignedOlH... | true | Float-encoded ID columns (group, mancBodyid, ...) are integral and < 2^53, so the cast to int64 is lossless (a violation aborts the build). |
| PASS | `types.status_label_vocabulary` | [] | true | All statusLabel values are known DVID labels. |
| PASS | `types.nt_vocabulary` | {} | true | All NT labels are in the controlled vocabulary. |
| PASS | `types.schema_conformance.neurons` | ['neuron_uid', 'dataset', 'dataset_version', 'source_id', 'cell_type']... | true | neurons.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.connections` | ['pre_id', 'post_id', 'synapse_count', 'synapse_count_hp', 'is_autapse']... | true | connections.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.connection_neuropils` | ['pre_id', 'post_id', 'neuropil', 'synapse_count']... | true | connection_neuropils.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.neuron_neuropils` | ['source_id', 'neuropil', 'n_pre', 'n_post']... | true | neuron_neuropils.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.neuropils` | ['name', 'parent', 'all_parents', 'depth', 'in_hierarchy']... | true | neuropils.parquet schema equals the canonical schema (names, types, nullability). |

## ids

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `ids.annotations.non_null_positive` | null | true | bodyId non-null and positive. |
| PASS | `ids.neuprint_neurons.id_consistent` | [0, 0] | [0, 0] | :ID(Body-ID) equals bodyId for every segment, no nulls. |

## duplicates

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `duplicates.annotations.bodyId` | 0 | 0 | No duplicate bodyId rows in annotations. |
| PASS | `duplicates.nt.body` | 0 | 0 | No duplicate bodies in NT table. |
| PASS | `duplicates.neuprint_neurons.id` | 0 | 0 | No duplicate segment IDs in the neuPrint neuron table. |
| PASS | `duplicates.raw_connections.pair` | 0 | 0 | Each (pre, post) segment pair appears at most once in the raw connection table. |
| PASS | `duplicates.connections.pair` | 0 | 0 | Neuron->neuron edges are unique. |

## cross_source

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `consistency.status_vs_status_label` | 0 | 0 | neuPrint 'status' equals the flyem-snapshot mapping of 'statusLabel' where both present. |
| PASS | `consistency.nt_consensus_rule_untyped` | 0 | 0 | Untyped bodies: consensus_nt == body-level predicted_nt with octopamine/serotonin -> unclear (behaviour observed in the data; the Methods text only describes typed bodies). |
| WARN | `consistency.nt_consensus_rule_typed` | {"bodies": 4420, "cell_types": 91} | {"bodies": 0} | Typed bodies whose consensus_nt is not explained by (ground_truth else celltype prediction with octopamine/serotonin -> unclear). These are expert/literature overrides absent from the ground_truth column (documented source discrepancy; consensus is still what neuPrint shows and recommends). |
| PASS | `cross_source.annotations_flat_vs_neuprint` | {"type": 0, "instance": 0, "superclass": 0, "class": 0, "subclass": 0, "somaS... |  | Annotation fields agree between flat body-annotations export (2026-06-03) and neuPrint neuron table (2026-06-08) for neurons (count of mismatching neurons per field). |
| PASS | `cross_source.nt_flat_vs_neuprint` | {"predicted_nt": 0, "consensus_nt": 0, "celltype_predicted_nt": 0, "predicted... |  | Neurotransmitter fields agree between flat NT export and neuPrint neuron table (mismatch counts). |
| PASS | `consistency.total_weight_equals_psds` | 311833243 | 311833243 | Sum of all connection weights equals neuPrint totalPostCount (every PSD in exactly one pair). |
| PASS | `cross_source.flat_vs_neuprint_totals` | [151856684, 311833243] | [151856684, 311833243] | Flat connectome-weights export and neuPrint connection table have the same number of pairs and the same total weight. |
| PASS | `cross_source.flat_vs_neuprint_neuron_edges` | {"only_neuprint": 0, "only_flat": 0, "weight_differs": 0} | {"only_neuprint": 0, "only_flat": 0, "weight_differs": 0} | Every neuron->neuron edge has identical weight in the flat export and the neuPrint table. |

<details><summary><code>consistency.status_vs_status_label</code> details</summary>

```json
{
  "note": "4585 bodies have a statusLabel mapping to '' and null status (expected)."
}
```
</details>

<details><summary><code>consistency.nt_consensus_rule_typed</code> details</summary>

```json
{
  "top_overrides": [
    {
      "cell_type": "KCg-m",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 1342
    },
    {
      "cell_type": "KCab-s",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 657
    },
    {
      "cell_type": "KCab-m",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 536
    },
    {
      "cell_type": "KCab-c",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 488
    },
    {
      "cell_type": "KCa'b'-ap2",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 291
    },
    {
      "cell_type": "KCg-d",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 206
    },
    {
      "cell_type": "KCa'b'-m",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 205
    },
    {
      "cell_type": "KCa'b'-ap1",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 199
    },
    {
      "cell_type": "KCab-p",
      "celltype_predicted_nt": "dopamine",
      "consensus_nt": "acetylcholine",
      "bodies": 129
    },
    {
      "cell_type": "Acc. ti flexor MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 47
    },
    {
      "cell_type": "Ti flexor MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 37
    },
    {
      "cell_type": "Tr flexor MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 35
    },
    {
      "cell_type": "ltm MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 21
    },
    {
      "cell_type": "Fe reductor MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 20
    },
    {
      "cell_type": "ltm2-femur MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 12
    },
    {
      "cell_type": "Ta depressor MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 9
    },
    {
      "cell_type": "ltm1-tibia MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 9
    },
    {
      "cell_type": "Tergopleural/Pleural promotor MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 8
    },
    {
      "cell_type": "EN00B026",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 8
    },
    {
      "cell_type": "DVMn 1a-c",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 6
    },
    {
      "cell_type": "MNml78",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 6
    },
    {
      "cell_type": "MNml80",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 6
    },
    {
      "cell_type": "Ta levator MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 5
    },
    {
      "cell_type": "EN00B023",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 4
    },
    {
      "cell_type": "EN00B013",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 4
    },
    {
      "cell_type": "EN00B010",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 4
    },
    {
      "cell_type": "DNg28",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "serotonin",
      "bodies": 4
    },
    {
      "cell_type": "hi2 MN",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 4
    },
    {
      "cell_type": "MNnm07,MNnm12",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 4
    },
    {
      "cell_type": "EN00B008",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 3
    },
    {
      "cell_type": "EN00B015",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 3
    },
    {
      "cell_type": "EN00B016",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 3
    },
    {
      "cell_type": "MNhl65",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 3
    },
    {
      "cell_type": "MNml77",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 2
    },
    {
      "cell_type": "MNnm08",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 2
    },
    {
      "cell_type": "MNhm42",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 2
    },
    {
      "cell_type": "MNwm36",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 2
    },
    {
      "cell_type": "EN00B003",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 2
    },
    {
      "cell_type": "EN00B004",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 2
    },
    {
      "cell_type": "EN00B011",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 2
    },
    {
      "cell_type": "EN00B025",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "octopamine",
      "bodies": 2
    },
    {
      "cell_type": "FNM2",
      "celltype_predicted_nt": "unclear",
      "consensus_nt": "glutamate",
      "bodies": 2
    },
    {
      "cell_
```
</details>

## edge_values

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `edge_values.nt_confidence_range` | {"predicted_nt_confidence": [0.1868583281637717, 0.9753679521334674], "cellty... | true | NT confidences lie in [0, 1]. |
| PASS | `edge_values.no_nulls` | 0 | 0 | No null IDs/weights in raw connections. |
| PASS | `edge_values.no_negative` | 0 | 0 | No negative weights in raw connections. |
| PASS | `edge_values.no_zero_weight` | 0 | 0 | No connection rows with weight 0 (would indicate sub-threshold-only pairs). |
| PASS | `edge_values.hp_le_weight` | 0 | 0 | weightHP <= weight for every row. |
| PASS | `edge_values.weight_hr_equals_weight` | 0 | 0 | weightHR == weight everywhere (expected: synapses were pre-filtered at conf>=0.5, so the 'high-recall' tier adds nothing; BrainIR therefore does not store weightHR). |
| PASS | `edge_values.connections_positive` | 0 | 0 | All retained edges have synapse_count >= 1. |
| PASS | `edge_values.connections_hp_le_count` | 0 | 0 | synapse_count_hp <= synapse_count. |

## directionality

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `consistency.upstream_equals_post` | 311833243 | 311833243 | Total upstream connections == total PSDs (each PSD has exactly one presynaptic partner). |
| PASS | `consistency.segment_totals_equal_edge_totals` | [311833243, 311833243] | [311833243, 311833243] | Sum over all segments of neuPrint 'downstream' and of 'upstream' each equal the total weight of the connection table (conservation: every counted pair has an existing pre and post segment). |
| PASS | `directionality.edge_sums_match_neuron_totals` | [0, 0] | [0, 0] | For every neuron, sum of outgoing edge weights (all partners) == source 'downstream' and incoming == 'upstream'. A pre/post swap anywhere would break this. |
| PASS | `directionality.dn_an_polarity` | {"descending": {"n": 1316, "median_frac_pre_in_vnc": 0.6010911221676876, "med... |  | Biological polarity sanity check: descending neurons have relatively more output (T-bars) than input in the VNC; ascending neurons the reverse (fraction of neurons consistent, expected > 0.8). |
| PASS | `directionality.sensory_motor_polarity` | {"vnc_sensory": {"n": 6389, "median_output_fraction": 0.874741913282863}, "cb... |  | Sensory neurons are output-dominated (median output fraction > 0.5) and motor neurons input-dominated (roles from ROLE_RULE_ID). |

## autapses

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `autapses.raw` | {"rows": 123, "synapses": 542} |  | Self-connections (pre == post) in the raw table: kept, flagged is_autapse. |

## synapses

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `synapses.total_pairs` | 311833243 | 311833243 | Synaptic partner rows == neuPrint totalPostCount (one presynaptic partner per PSD). |
| PASS | `synapses.min_confidence` | [0.699999988079071, 0.5] | true | All partner rows have conf_pre >= 0.5 and conf_post >= 0.5. |
| info | `synapses.body_zero` | 0 |  | Partner rows touching body 0 (unsegmented). |
| PASS | `synapses.recomputed_edge_weights` | {"only_synapses": 0, "only_edges": 0, "weight_differs": 0, "weight_hp_differs... | {"only_synapses": 0, "only_edges": 0, "weight_differs": 0, "weight_hp_differs... | Edge weights (and HP weights at conf_post>=0.7) recomputed from individual synapses match the connection table for all outgoing edges of 300 random neurons (51437 edges). |
| PASS | `synapses.recomputed_edge_neuropils` | {"only_synapses": 0, "only_table": 0, "count_differs": 0} | {"only_synapses": 0, "only_table": 0, "count_differs": 0} | Per-edge neuropil counts recomputed from synapse primary_post ROIs match connection_neuropils (sampled neurons' outgoing edges). |
| PASS | `synapses.recomputed_neuron_totals` | {"downstream": 0, "upstream": 0, "pre_tbars_gt_neuprint_pre": 0} | {"downstream": 0, "upstream": 0, "pre_tbars_gt_neuprint_pre": 0} | For sampled neurons, synapse-level counts reproduce neuPrint downstream/upstream, and T-bars with partners never exceed neuPrint 'pre'. |

<details><summary><code>synapses.recomputed_edge_weights</code> details</summary>

```json
{
  "sample_seed": 20260922
}
```
</details>

## graph_stats

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `graph.basic_statistics` | {"n_neurons": 166700, "n_edges": 25582938, "total_synapses": 124177617, "dens... |  | Basic statistics of the neuron->neuron graph. |

