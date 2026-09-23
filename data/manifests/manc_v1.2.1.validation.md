# BrainIR ingestion validation - manc:v1.2.1

**Summary:** 32 pass, 0 fail, 1 warn, 23 info

## Context

```json
{
  "dataset": "manc",
  "version": "v1.2.1",
  "pipeline": "brainir.ingest.manc@1.0.0",
  "git": {
    "commit": "b5d956511449c325b0c8e2b15fa4f6ab92b0b54b",
    "src_dirty": true,
    "pipeline_code": {
      "combined_sha256": "022fa60850ae391adf7644ef8f96914b400f02be6bb6a3f1567db77f1d1694d0",
      "files": {
        "ingest/common.py": "12630e70eb3bfad0b984ec9eead6a6d5089ed55a579d34644cf043501a3b7bb1",
        "ingest/malecns.py": "35ea4d371889c774758e3be86e205b7bb42cf4ce0e2afc5b3a2430734567e4df",
        "ingest/manc.py": "c2c95ceaae0bc6138af3be97f2b87f818858ed4c4746336b2f3365ee9b7fc5c6",
        "io.py": "caef03300a0021f9f05eee4bef7d06b935d1a3d45b2d26d365def931f127d91c",
        "schema/tables.py": "98dc8ae7dc0b6dcb9789388df4d2a96923ab244b7a1376d2a5c1dbf5d56b7652",
        "schema/vocab.py": "b6aa8e69db0db034c8bb4b904b2089b3287340352f5fa218d25e62314d2d4ce0",
        "schema/evidence.py": "ea3ec89660d7154d5c4182a10ef48d270e9ead8ad8fc05c03f137ed237bf0407",
        "sources/registry.py": "1a680704222ab892de0ffb4b81ed7df4a27f5115316244b2c865f5b83ad39dba",
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
| PASS | `provenance.acquisition_dataset` | ["manc", "v1.2"] | ["manc", "v1.2"] | Acquisition log dataset/version match the registry. |
| PASS | `provenance.raw_inputs_verified` | all ok | true | Every raw input exists, has the pinned size, and its recorded checksums match registry pins (CRC32C for all, MD5 where available, GCS generation). |
| PASS | `provenance.acquisition_dataset.v1_0` | ["manc", "v1.0"] | ["manc", "v1.0"] | Acquisition log dataset/version match the registry. |
| PASS | `provenance.raw_inputs_verified.v1_0` | all ok | true | Every raw input exists, has the pinned size, and its recorded checksums match registry pins (CRC32C for all, MD5 where available, GCS generation). |
| PASS | `provenance.meta_dataset_tag` | ["manc", "v1.0"] | ["manc", "v1.0"] | neuPrint :Meta dataset/tag equal the expected dataset/version (no cross-version mixing). |
| info | `provenance.meta_identity` | {"uuid": "59b37970bc7a4341b9a3a965a0d6b402", "latestMutationId": 1000097500, ... |  | neuPrint snapshot identity (DVID uuid, mutation id, last edit). |
| info | `provenance.synapse_thresholds` | {"postHighAccuracyThreshold": 0.4, "preHPThreshold": 0.7, "postHPThreshold": ... |  | Synapse confidence thresholds declared by the neuPrint Meta (informational; the effective rule is inferred from the data, see synapses.inferred_count_rule). |
| info | `neuropils.totals_source` | null |  | ROI catalogue from manc:v1.0 Meta; n_post_total recomputed from the v1.2 partner table under the count rule; n_pre_total null (T-bar ROIs are not published for v1.2). |

<details><summary><code>provenance.raw_inputs_verified</code> details</summary>

```json
{
  "inputs": [
    "syn_partners",
    "segprops_v1_2_1_info"
  ]
}
```
</details>

<details><summary><code>provenance.raw_inputs_verified.v1_0</code> details</summary>

```json
{
  "inputs": [
    "neuprint_meta",
    "neuron_properties"
  ]
}
```
</details>

## uniqueness

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `neuropils.hierarchy_is_dag` | 0 |  | ROIs listed under more than one parent in the source hierarchy (merged into one row each; 'parent' = roiInfo parent, 'all_parents' keeps every parent). |
| PASS | `neuropils.top_level_region_consistent` | {} | true | Every ROI has a single top-level region across all its hierarchy paths. |
| PASS | `ids.neuropils.unique` | 0 | 0 | ROI names are unique in the output catalogue. |
| PASS | `ids.neurons.unique` | 0 | 0 | Neuron IDs unique. |

<details><summary><code>neuropils.hierarchy_is_dag</code> details</summary>

```json
{
  "multi_parent_rois": {}
}
```
</details>

## referential

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `neuropils.roiinfo_parent_aliases` | {"ventral nerve core": "ventral nerve cord"} |  | roiInfo 'parent' values that are misspellings of hierarchy names in the source (mapped by alias). |
| PASS | `neuropils.roiinfo_parent_consistent` | {} | true | The roiInfo 'parent' of each ROI is one of its hierarchy parents. |
| WARN | `referential.primary_rois_in_hierarchy` | {"primary_not_in_hierarchy": ["LegNp(T1)(L)", "LegNp(T1)(R)", "LegNp(T2)(L)",... |  | Primary ROIs absent from the source roiHierarchy, and hierarchy names without roiInfo statistics. Known source inconsistency (stale hierarchy); roiInfo/primaryRois are taken as authoritative and hierarchy-only names are not included in the catalogue. |
| info | `neuropils.stats_only_rois` | 8 |  | ROIs with statistics in roiInfo but absent from the hierarchy (kept, in_hierarchy=False). |
| PASS | `referential.partner_rois_are_primary` | [] | true | Every roi_post value of the partner table is a primary ROI of the ROI catalogue, null, or the export's '<unspecified>' marker (mapped to '<unassigned>'). |
| PASS | `referential.edges_reference_neurons` | 0 | 0 | Every edge endpoint is a neuron. |

<details><summary><code>neuropils.stats_only_rois</code> details</summary>

```json
{
  "rois": [
    "LegNp(T1)(L)",
    "LegNp(T1)(R)",
    "LegNp(T2)(L)",
    "LegNp(T2)(R)",
    "LegNp(T3)(L)",
    "LegNp(T3)(R)",
    "Ov(L)",
    "Ov(R)"
  ]
}
```
</details>

<details><summary><code>referential.partner_rois_are_primary</code> details</summary>

```json
{
  "n_rois": 60
}
```
</details>

## coverage

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `coverage.primary_roi_synapse_fraction` | {"pre": 0.995316, "post": 0.996989} |  | Fraction of all T-bars / PSDs located inside some primary ROI (rest -> '<unassigned>'). |
| info | `coverage.snapshot_classes` | {"intrinsic_neuron": 13060, "sensory_neuron": 5927, "ascending_neuron": 1862,... |  | Distribution of the 'class' tag. |
| PASS | `consistency.connection_neuropils_sum_to_weight` | 0 | 0 | Per-edge neuropil counts sum exactly to the edge synapse_count. |
| info | `coverage.connection_unassigned` | {"edges": 16235, "synapses": 24401} |  | Edges with synapses outside primary ROIs (stored as neuropil '<unassigned>'). |
| info | `coverage.nt_carried_from_v1_0` | {"neurons": 24143, "absent_from_v1_0": 0, "without_body_prediction": 230} |  | Body-level NT predictions are carried over from the manc:v1.0 property export by body ID (same segmentation lineage). Neurons absent from v1.0 or without a v1.0 prediction have null nt_body_*. |
| info | `coverage.annotation_fields` | {"cell_type": 0.9778, "instance": 0.0, "cell_class": 0.0, "sub_class": 0.912,... |  | Fraction of neurons with each annotation populated. |
| info | `coverage.by_superclass` | [{"super_class": "<NA>", "typed": 0.0, "nt_known": 0.0, "n": 67}, {"super_cla... |  | Per-superclass neuron count, fraction typed, fraction with a known (non-unclear) consensus NT. |
| info | `coverage.nt_consensus_distribution` | {"None": 24143} |  | Distribution of consensus NT over neurons. |

## ingestion

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `rows.raw.annotation_snapshot` | 24143 |  | Bodies in annotation snapshot v1.2.1 (neuroglancer segment_properties_v1.2.1 (type, PreSyn, PostSyn, tagged properties)). |
| info | `rows.raw.neuron_properties` | 102369 |  | Rows (bodies) in the v1.0 per-body property export. |
| info | `rows.neurons` | 24143 |  | Neurons = bodies of annotation snapshot v1.2.1 (see definitions). |
| info | `rows.raw.syn_partners` | {"rows_total": 86952391, "rows_counted": 74457060, "rows_hp": 53505834, "rows... |  | Raw T-bar->PSD pairs (minconf 0.0) and how many pass the count rule. |
| info | `rows.connections` | 5338378 |  | Neuron->neuron edges retained (both endpoints are neurons). |

<details><summary><code>rows.raw.annotation_snapshot</code> details</summary>

```json
{
  "columns": [
    "PostSyn",
    "PreSyn",
    "bodyId",
    "tag_birthtime",
    "tag_class",
    "tag_entry_nerve",
    "tag_exit_nerve",
    "tag_hemilineage",
    "tag_long_tract",
    "tag_modality",
    "tag_origin",
    "tag_serial_motif",
    "tag_soma_neuromere",
    "tag_soma_side",
    "tag_subclass",
    "tag_target",
    "type"
  ]
}
```
</details>

<details><summary><code>rows.raw.syn_partners</code> details</summary>

```json
{
  "count_rule": {
    "conf_pre_min": 0.0,
    "conf_post_min": 0.4,
    "hp_conf_pre_min": 0.0,
    "hp_conf_post_min": 0.7,
    "basis": "inferred on manc:v1.0 (neuPrint weight/weightHP vs raw partner counts)"
  }
}
```
</details>

## ids

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `ids.snapshot.non_null_positive` | null | true | bodyId non-null and positive. |
| PASS | `ids.properties.non_null_positive` | null | true | bodyId non-null and positive. |

## duplicates

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `duplicates.snapshot.bodyId` | 0 | 0 | No duplicate bodies in the snapshot. |
| PASS | `duplicates.properties.bodyId` | 0 | 0 | No duplicate bodyId rows in the property export. |

## types

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `types.snapshot_multivalued_tags` | {} |  | Bodies with more than one tag value per prefix (joined with '|'). |
| PASS | `types.properties_float_ids_integral` | ["group", "serial", "subcluster"] | true | Float-encoded integer columns (group, serial, subcluster) are integral and < 2^53 (lossless int64 cast). |
| info | `types.properties_placeholders` | {"hemilineage": 3238, "somaNeuromere": 11, "class": 61} |  | String placeholders ('None', 'TBD', 'NA', '~') converted to null (per column). |
| PASS | `types.status_label_vocabulary` | [] | true | All statusLabel values are known DVID labels. |
| PASS | `types.nt_vocabulary` | [] | true | All predictedNt labels are in the controlled vocabulary. |
| PASS | `types.schema_conformance.neurons` | ['neuron_uid', 'dataset', 'dataset_version', 'source_id', 'cell_type']... | true | neurons.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.connections` | ['pre_id', 'post_id', 'synapse_count', 'synapse_count_hp', 'is_autapse']... | true | connections.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.connection_neuropils` | ['pre_id', 'post_id', 'neuropil', 'synapse_count']... | true | connection_neuropils.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.neuron_neuropils` | ['source_id', 'neuropil', 'n_pre', 'n_post']... | true | neuron_neuropils.parquet schema equals the canonical schema (names, types, nullability). |
| PASS | `types.schema_conformance.neuropils` | ['name', 'parent', 'all_parents', 'depth', 'in_hierarchy']... | true | neuropils.parquet schema equals the canonical schema (names, types, nullability). |

## edge_values

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `edge_values.nt_confidence_range` | {"ntGabaProb": [2.605764216868315e-14, 1.0], "predictedNtProb": [0.2753386283... | true | NT probabilities lie in [0, 1]. |
| PASS | `edge_values.no_nulls` | 0 | 0 | No null bodies/confidences in the raw partner table. |
| PASS | `edge_values.connections_positive` | 0 | 0 | All retained edges have synapse_count >= 1. |
| PASS | `edge_values.connections_hp_le_count` | 0 | 0 | synapse_count_hp <= synapse_count. |

## cross_source

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `consistency.nt_prediction_is_argmax` | 0 | 0 | predictedNt equals the argmax over the four body-level class probabilities (ACh/GABA/Glu/unknown). |
| info | `cross_source.snapshot_synapse_counts` | {"PreSyn == T-bars (unfiltered)": {"equal": 24143, "n": 24143, "fraction": 1.... |  | Per-neuron synapse counts recomputed from the partner table vs the counts published in the annotation snapshot (both under the count rule and unfiltered). Tells which filtering the snapshot's counts used. |

## autapses

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `autapses.raw` | {"edges": 36} |  | Self-connections (pre == post) among neuron->neuron edges: kept, flagged is_autapse. |

## directionality

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `directionality.edge_sums_match_neuron_totals` | [0, 0] | [0, 0] | For every neuron, sum of outgoing edge weights (all partners) == source 'downstream' and incoming == 'upstream'. A pre/post swap anywhere would break this. |
| PASS | `directionality.dn_an_polarity` | {"descending": {"n": 1328, "median_output_fraction": 0.9567114819925595, "fra... |  | VNC-only volume: descending neurons are output-dominated (fraction of synaptic connections that are outgoing > 0.5 for > 80% of DNs; judged only with >= 10 DNs). Ascending neurons: informational. |
| PASS | `directionality.sensory_motor_polarity` | {"vnc_sensory": {"n": 5927, "median_output_fraction": 0.8565815324165029}, "v... |  | Sensory neurons are output-dominated (median output fraction > 0.5) and motor neurons input-dominated (roles from ROLE_RULE_ID). |

## graph_stats

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `graph.basic_statistics` | {"n_neurons": 24143, "n_edges": 5338378, "total_synapses": 31002847, "density... |  | Basic statistics of the neuron->neuron graph. |

