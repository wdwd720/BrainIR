# BrainIR ingestion validation - manc:v1.0

**Summary:** 48 pass, 0 fail, 3 warn, 26 info

## Context

```json
{
  "dataset": "manc",
  "version": "v1.0",
  "pipeline": "brainir.ingest.manc@1.0.0",
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
| PASS | `provenance.acquisition_dataset` | ["manc", "v1.0"] | ["manc", "v1.0"] | Acquisition log dataset/version match the registry. |
| PASS | `provenance.raw_inputs_verified` | all ok | true | Every raw input exists, has the pinned size, and its recorded checksums match registry pins (CRC32C for all, MD5 where available, GCS generation). |
| PASS | `provenance.meta_dataset_tag` | ["manc", "v1.0"] | ["manc", "v1.0"] | neuPrint :Meta dataset/tag equal the expected dataset/version (no cross-version mixing). |
| info | `provenance.meta_identity` | {"uuid": "59b37970bc7a4341b9a3a965a0d6b402", "latestMutationId": 1000097500, ... |  | neuPrint snapshot identity (DVID uuid, mutation id, last edit). |
| info | `provenance.synapse_thresholds` | {"postHighAccuracyThreshold": 0.4, "preHPThreshold": 0.7, "postHPThreshold": ... |  | Synapse confidence thresholds declared by the neuPrint Meta (informational; the effective rule is inferred from the data, see synapses.inferred_count_rule). |
| info | `provenance.syn_partners_decompressed` | {"cache_path": "$DATA/cache/manc_v1.0/117eaecf66a1a2e2_manc-synapse-partners-... |  | bzip2 partner table decompressed into the cache (derived, disposable; keyed by the SHA-256 of the compressed input, which the acquisition check verified). |

<details><summary><code>provenance.raw_inputs_verified</code> details</summary>

```json
{
  "inputs": [
    "neuprint_meta",
    "neuron_properties",
    "neuprint_neurons",
    "neuprint_connections",
    "traced_neurons",
    "traced_connections",
    "traced_connections_per_roi",
    "syn_partners"
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
| PASS | `referential.properties_are_neuprint_neurons` | [102369, 102369, 102369] | [102369, 102369, 102369] | The per-body property export and the neuPrint :Neuron-labelled bodies are the same set. |
| PASS | `referential.raw_edges_reference_segments` | 0 | 0 | Every endpoint of every raw connection exists in the neuPrint segment table. |
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

## coverage

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `coverage.primary_roi_synapse_fraction` | {"pre": 0.995316, "post": 0.996989} |  | Fraction of all T-bars / PSDs located inside some primary ROI (rest -> '<unassigned>'). |
| info | `coverage.typed_bodies_outside_neuron_set` | 244 |  | :Neuron bodies with a cell type but a status other than 'Traced' (excluded from the neuron table; e.g. PRT Orphan). |
| PASS | `consistency.neuron_neuropils_not_exceeding_totals` | 0 | 0 | Per-neuron primary-ROI pre/post counts never exceed the neuron's totals. |
| PASS | `consistency.connection_neuropils_not_exceeding_weight` | 0 | 0 | Per-edge primary-neuropil counts never exceed the edge weight. |
| info | `coverage.connection_unassigned` | {"edges": 15860, "synapses": 23966} |  | Edges with synapses outside primary ROIs (stored as neuropil '<unassigned>'). |
| info | `coverage.annotation_fields` | {"cell_type": 0.9298, "instance": 1.0, "cell_class": 0.0, "sub_class": 0.9838... |  | Fraction of neurons with each annotation populated. |
| info | `coverage.by_superclass` | [{"super_class": "<NA>", "typed": 0.0, "nt_known": 0.0, "n": 25}, {"super_cla... |  | Per-superclass neuron count, fraction typed, fraction with a known (non-unclear) consensus NT. |
| info | `coverage.nt_consensus_distribution` | {"None": 23514} |  | Distribution of consensus NT over neurons. |

## ingestion

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `rows.raw.neuron_properties` | 102369 |  | Rows (bodies) in the v1.0 per-body property export. |
| info | `rows.raw.neuprint_neurons` | {"n_segments": 24522126, "n_neuron_label": 102369} |  | Synaptic segments in neuPrint and how many carry the :Neuron label. |
| info | `rows.neurons` | 23514 |  | Neurons = neuPrint :Neuron bodies with status 'Traced' (see definitions). |
| info | `rows.raw.neuprint_connections` | 42770212 |  | Rows in the raw neuPrint connection table (segment pairs). |
| info | `rows.connections_zero_weight_dropped` | 739081 |  | Neuron->neuron pairs whose neuPrint weight is 0 (only high-recall/low-confidence synapses); excluded from connections because synapse_count follows neuPrint 'weight'. |
| info | `rows.connections` | 5275519 |  | Neuron->neuron edges retained (both endpoints are neurons). |

## ids

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `ids.properties.non_null_positive` | null | true | bodyId non-null and positive. |
| PASS | `ids.neuprint_neurons.id_consistent` | [0, 0] | [0, 0] | :ID(Body-ID) equals bodyId for every segment, no nulls. |

## duplicates

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `duplicates.properties.bodyId` | 0 | 0 | No duplicate bodyId rows in the property export. |
| PASS | `duplicates.neuprint_neurons.id` | 0 | 0 | No duplicate segment IDs in the neuPrint neuron table. |
| PASS | `duplicates.raw_connections.pair` | 0 | 0 | Each (pre, post) segment pair appears at most once in the raw connection table. |
| PASS | `duplicates.connections.pair` | 0 | 0 | Neuron->neuron edges are unique. |

## types

| status | check | observed | expected | description |
|---|---|---|---|---|
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
| PASS | `edge_values.no_nulls` | 0 | 0 | No null IDs/weights in raw connections. |
| PASS | `edge_values.no_negative` | 0 | 0 | No negative weights in raw connections. |
| info | `edge_values.zero_weight_rows` | 5666874 |  | Connection rows with weight 0 (pairs supported only by synapses below the database confidence threshold; weightHR > 0). Expected for sources that keep a high-recall tier. |
| PASS | `edge_values.hp_le_weight` | 0 | 0 | weightHP <= weight for every row. |
| PASS | `edge_values.weight_hr_ge_weight` | 0 | 0 | weightHR >= weight for every row (the high-recall tier adds lower-confidence synapses; BrainIR stores weight and weightHP only). |
| info | `edge_values.weight_hr_summary` | {"rows_hr_ne_weight": 10276388, "sum_weight": 74456993, "sum_weight_hr": 8695... |  | Rows where weightHR differs from weight, and the two totals. |
| PASS | `edge_values.connections_positive` | 0 | 0 | All retained edges have synapse_count >= 1. |
| PASS | `edge_values.connections_hp_le_count` | 0 | 0 | synapse_count_hp <= synapse_count. |

## cross_source

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `consistency.nt_prediction_is_argmax` | 0 | 0 | predictedNt equals the argmax over the four body-level class probabilities (ACh/GABA/Glu/unknown). |
| PASS | `cross_source.properties_vs_neuprint` | {"type": 0, "instance": 0, "class": 0, "subclass": 0, "status": 314, "statusL... |  | Annotation fields agree between the per-body property export (2023-06-05) and the neuPrint neuron table (2023-06-12) (count of mismatching bodies per field). Status differences are analysed separately. |
| info | `cross_source.status_remap_between_exports` | [{"properties_status": "RT Orphan", "neuprint_status": "Traced", "bodies": 314}] |  | Bodies whose proofreading status differs between the two official exports (e.g. 'RT Orphan' in the 2023-06-05 property export is 'Traced' in the 2023-06-12 neuPrint database). |
| PASS | `consistency.total_weight_equals_psds` | 74456993 | 74456993 | Sum of connection weights equals neuPrint totalPostCount (the Meta counts PSDs above the database confidence threshold; the high-recall total is larger). |
| PASS | `cross_source.traced_neuron_set` | {"neurons": 23514, "traced_csv": 23188, "only_in_csv": 0, "only_in_ours": 326} |  | Neuron set vs the independent neuprint-python traced-neuron export (2023-06-02; proofreading continued until the 2023-06-12 database export). |
| PASS | `cross_source.traced_connections_csv` | {"only_ours": 0, "only_csv": 0, "weight_differs": 0, "compared": 5243574} |  | Edges between traced-CSV neurons: agreement of weights with the independent traced-connections.csv export (dates differ by 10 days; small differences reflect continued proofreading). |
| PASS | `cross_source.traced_connections_per_roi_csv` | {"only_ours": 0, "only_csv": 0, "count_differs": 0} |  | Per-edge neuropil counts vs traced-connections-per-roi.csv ('NotPrimary' == '<unassigned>'). |

<details><summary><code>consistency.total_weight_equals_psds</code> details</summary>

```json
{
  "sum_weight_hr": 86952391
}
```
</details>

## directionality

| status | check | observed | expected | description |
|---|---|---|---|---|
| PASS | `consistency.upstream_equals_post` | 74456993 | 74456993 | Total upstream connections == total PSDs (each PSD has exactly one presynaptic partner). |
| PASS | `consistency.segment_totals_equal_edge_totals` | [74456993, 74456993] | [74456993, 74456993] | Sum over all segments of neuPrint 'downstream' and of 'upstream' each equal the total weight of the connection table (conservation: every counted pair has an existing pre and post segment). |
| PASS | `directionality.edge_sums_match_neuron_totals` | [0, 0] | [0, 0] | For every neuron, sum of outgoing edge weights (all partners) == source 'downstream' and incoming == 'upstream'. A pre/post swap anywhere would break this. |
| PASS | `directionality.dn_an_polarity` | {"descending": {"n": 1328, "median_output_fraction": 0.9567114819925595, "fra... |  | VNC-only volume: descending neurons are output-dominated (fraction of synaptic connections that are outgoing > 0.5 for > 80% of DNs; judged only with >= 10 DNs). Ascending neurons: informational. |
| PASS | `directionality.sensory_motor_polarity` | {"vnc_sensory": {"n": 5755, "median_output_fraction": 0.8560975609756097}, "v... |  | Sensory neurons are output-dominated (median output fraction > 0.5) and motor neurons input-dominated (roles from ROLE_RULE_ID). |

## autapses

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `autapses.raw` | {"rows": 6, "synapses": 29} |  | Self-connections (pre == post) in the raw table: kept, flagged is_autapse. |

## synapses

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `synapses.raw_partner_table` | {"rows": 86952391, "min_conf_pre": 0.75, "min_conf_post": 0.20000000298023224... |  | Raw partner rows (T-bar->PSD pairs at minconf 0.0), minimum confidences, rows touching body 0, distinct T-bars. |
| PASS | `synapses.total_pairs_equal_weight_hr` | 86952391 | 86952391 | Raw partner rows == total neuPrint weightHR (the high-recall tier counts every pair of the minconf-0.0 table; one presynaptic partner per PSD). |
| PASS | `synapses.distinct_tbars_equal_meta_pre` | 10343391 | 10343391 | Distinct T-bar coordinates in the partner table == Meta totalPreCount. |
| PASS | `synapses.inferred_count_rule` | {"exact_rules": {"weight": [{"conf_pre_min": 0.0, "conf_post_min": 0.4}, {"co... |  | Confidence rules (conf_pre >= a AND conf_post >= b over a grid) that reproduce neuPrint weight, weightHR and weightHP exactly from the raw minconf-0.0 partner table for every pair of the sampled neurons (HR-only pairs included). Several equivalent rules match when no synapse falls between two grid values; the chosen rule prefers the Meta's declared threshold, else the loosest matching one. |
| PASS | `synapses.count_rule_matches_default` | {"conf_pre_min": 0.0, "conf_post_min": 0.4, "hp_conf_pre_min": 0.0, "hp_conf_... | {"conf_pre_min": 0.0, "conf_post_min": 0.4, "hp_conf_pre_min": 0.0, "hp_conf_... | The rule inferred here equals DEFAULT_COUNT_RULE, the rule the v1.2.x builds apply to their partner table. |
| WARN | `synapses.recomputed_edge_neuropils` | {"only_synapses": 1, "only_table": 1, "count_differs": 0} | {"only_synapses": 0, "only_table": 0, "count_differs": 0} | Per-edge neuropil counts recomputed from synapse roi_post under the count rule match connection_neuropils (sampled neurons' outgoing edges). |
| info | `synapses.tbar_psd_roi_span` | {"tbars": 117197, "tbars_spanning_multiple_rois": 705, "fraction": 0.006016} |  | T-bars (of sampled neurons) whose PSDs lie in more than one primary ROI. Quantifies the approximation used by the v1.2.x builds, where a T-bar's neuropil is taken from its PSDs. |
| WARN | `synapses.recomputed_neuron_totals` | {"downstream": 0, "upstream": 2, "pre_tbars_gt_neuprint_pre": 0} | {"downstream": 0, "upstream": 0, "pre_tbars_gt_neuprint_pre": 0} | For sampled neurons, synapse-level counts under the count rule reproduce neuPrint downstream/upstream, and T-bars with partners never exceed neuPrint 'pre'. |

<details><summary><code>synapses.recomputed_neuron_totals</code> details</summary>

```json
{
  "detail": {
    "downstream": 0,
    "upstream": 2,
    "pre_tbars_gt_neuprint_pre": 0,
    "pre_tbars_eq_neuprint_pre": 283,
    "n": 300
  }
}
```
</details>

## graph_stats

| status | check | observed | expected | description |
|---|---|---|---|---|
| info | `graph.basic_statistics` | {"n_neurons": 23514, "n_edges": 5275519, "total_synapses": 30808321, "density... |  | Basic statistics of the neuron->neuron graph. |

