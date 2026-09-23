# Evaluation — dng100-benchmark-v1 (tier A)

evaluator 1.1.0 `059a4fe0c25b` · oracle `269661940130` · bundle `efc33d775d88`

## male-cns_v1.0 — method `baseline_statistical_motif`

| family | metric | value |
|---|---|---|
| structural | predicted core size | 3 |
| structural | excitatory core recall (E1, E2) | 0.5 |
| structural | inhibitory slot filled | False [] |
| structural | precision vs DNg100-circuit labels (E1-E3, I1-I2) | 0.3333333333333333 |
| structural | precision vs all published labels (incl. DNb08 pathway) | 0.3333333333333333 |
| structural | Jaccard vs reference core | 0.2 |
| type/role | type-level excitatory recall | 0.5 |
| type/role | role agreement with oracle | {'n': 1, 'agree': 1, 'fraction': 1.0} |
| type/role | role consistent with network sign | {'n': 3, 'agree': 3, 'fraction': 1.0} |
| mechanism | internal edges / loop strongly connected | 0 / None |
| functional | intact network fraction rhythmic / sustained | 1.0 / 1.0 |
| functional | keep-only core fraction rhythmic / sustained (sufficiency) | 0.0 / 0.0 → pass=False |
| functional | necessity accuracy | None (0 claims) |
| functional | frequency abs error (Hz) | None |
| robustness | keep_only_core_weight_noise_0.1 | fraction rhythmic 0.0 / sustained 0.0 |
| robustness | keep_only_core_weight_noise_0.3 | fraction rhythmic 0.0 / sustained 0.0 |
| robustness | keep_only_core_parameter_sd_x2 | fraction rhythmic 0.0 / sustained 0.0 |

## manc_v1.2.1 — method `baseline_statistical_motif`

| family | metric | value |
|---|---|---|
| structural | predicted core size | 3 |
| structural | excitatory core recall (E1, E2) | 0.0 |
| structural | inhibitory slot filled | False [] |
| structural | precision vs DNg100-circuit labels (E1-E3, I1-I2) | 0.0 |
| structural | precision vs all published labels (incl. DNb08 pathway) | 0.0 |
| structural | Jaccard vs reference core | 0.0 |
| type/role | type-level excitatory recall | 0.0 |
| type/role | role agreement with oracle | {'n': 0, 'agree': 0, 'fraction': None} |
| type/role | role consistent with network sign | {'n': 3, 'agree': 3, 'fraction': 1.0} |
| mechanism | internal edges / loop strongly connected | 1 / None |
| functional | intact network fraction rhythmic / sustained | 1.0 / 1.0 |
| functional | keep-only core fraction rhythmic / sustained (sufficiency) | 0.0 / 0.0 → pass=False |
| functional | necessity accuracy | None (0 claims) |
| functional | frequency abs error (Hz) | None |
| robustness | keep_only_core_weight_noise_0.1 | fraction rhythmic 0.0 / sustained 0.0 |
| robustness | keep_only_core_weight_noise_0.3 | fraction rhythmic 0.0 / sustained 0.0 |
| robustness | keep_only_core_parameter_sd_x2 | fraction rhythmic 0.0 / sustained 0.0 |

## manc_v1.2.3 — method `baseline_statistical_motif`

| family | metric | value |
|---|---|---|
| structural | predicted core size | 3 |
| structural | excitatory core recall (E1, E2) | 0.0 |
| structural | inhibitory slot filled | False [] |
| structural | precision vs DNg100-circuit labels (E1-E3, I1-I2) | 0.0 |
| structural | precision vs all published labels (incl. DNb08 pathway) | 0.0 |
| structural | Jaccard vs reference core | 0.0 |
| type/role | type-level excitatory recall | 0.0 |
| type/role | role agreement with oracle | {'n': 0, 'agree': 0, 'fraction': None} |
| type/role | role consistent with network sign | {'n': 3, 'agree': 3, 'fraction': 1.0} |
| mechanism | internal edges / loop strongly connected | 0 / None |
| functional | intact network fraction rhythmic / sustained | 1.0 / 1.0 |
| functional | keep-only core fraction rhythmic / sustained (sufficiency) | 0.0 / 0.0 → pass=False |
| functional | necessity accuracy | None (0 claims) |
| functional | frequency abs error (Hz) | None |
| robustness | keep_only_core_weight_noise_0.1 | fraction rhythmic 0.0 / sustained 0.0 |
| robustness | keep_only_core_weight_noise_0.3 | fraction rhythmic 0.0 / sustained 0.0 |
| robustness | keep_only_core_parameter_sd_x2 | fraction rhythmic 0.0 / sustained 0.0 |

## cross-connectome (MANC <-> MaleCNS only; the two MANC networks are one lineage)

labels recovered in all datasets: []; excitatory core in all datasets: False

claimed correspondences: 0 (0 not gradeable by the oracle); accuracy vs oracle labels: None; agreement with curated pairs: None

- transfer male-cns_v1.0->manc_v1.2.1: 3/3 core neurons mapped; keep-only sustained fraction 0.0 → pass=False
- transfer male-cns_v1.0->manc_v1.2.3: 3/3 core neurons mapped; keep-only sustained fraction 0.0 → pass=False
- transfer manc_v1.2.1->male-cns_v1.0: 1/3 core neurons mapped; keep-only sustained fraction 0.0 → pass=False
- transfer manc_v1.2.3->male-cns_v1.0: 1/3 core neurons mapped; keep-only sustained fraction 0.0 → pass=False

Evidence levels of oracle facts: ('paper_simulation', 'brainir_simulation', 'wet_lab', 'expert_interpretation')
