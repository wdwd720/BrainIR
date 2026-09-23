# DNg100 baselines — dng100-benchmark-v1 (bundle `public_blind`, tier A, sha `efc33d775d88`)

Generated 2026-09-23T10:12:11Z by `benchmarks/dng100/baselines/run_all_baselines.py`. Metrics are copied from the frozen
evaluator's output (`results/eval/<method>.json`, answer-bearing: never expose to a method). There is deliberately no aggregate
score. E-core recall = fraction of the two published excitatory core neurons recovered by exact id; I-slot = a published
inhibitory-slot neuron is in the core; precision = fraction of predicted neurons that carry any published label; Jaccard is
against the reference core; type-level recall credits same-type neurons; sufficiency = keep-only-core simulation still
rhythmic in >= 50 % of replicates; necessity accuracy = fraction of essential/non-essential claims confirmed by silencing.

- `random_matched`: method sha `0b07650bd35b`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 101.6 s (all networks)
- `degree_topk`: method sha `46d36ffdfd8e`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 101.8 s (all networks)
- `pagerank`: method sha `ab4a3357c845`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 96.9 s (all networks)
- `betweenness_stim_to_readout`: method sha `77397a5c5ccb`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 93.6 s (all networks)
- `kcore_scc`: method sha `ea5593cde481`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 94.6 s (all networks)
- `recurrence_loop`: method sha `17443677b1c5`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 92.9 s (all networks)
- `community`: method sha `8a5df3e2cc95`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 92.6 s (all networks)
- `statistical_motif`: method sha `9457ff846cbb`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 92.7 s (all networks)
- `greedy_prune_sim`: method sha `4d8307ac0e3f`, evaluator `059a4fe0c25b`, simulation replicates 8 (seeds 1000..1007), t_end 2.0 s, evaluation wall 170.1 s (all networks)

## manc_v1.2.1

| method | k | E-core recall | I-slot | precision | Jaccard | type-level E recall | sufficiency frac | sufficiency pass | necessity acc | claims | method wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random_matched | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 1.10 |
| degree_topk | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 1.20 |
| pagerank | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 2.50 |
| betweenness_stim_to_readout | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 1.80 |
| kcore_scc | 3 | 0.00 | no | 0.00 | 0.00 | 0.50 | 0.00 | no | – | 0 | 2.50 |
| recurrence_loop | 3 | 0.00 | no | 0.33 | 0.00 | 0.00 | 0.00 | no | – | 0 | 1.20 |
| community | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 3.90 |
| statistical_motif | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 4.20 |
| greedy_prune_sim | 3 | 0.50 | no | 0.67 | 0.20 | 0.50 | 0.00 | no | 1.00 | 3 | 128 |

## manc_v1.2.3

| method | k | E-core recall | I-slot | precision | Jaccard | type-level E recall | sufficiency frac | sufficiency pass | necessity acc | claims | method wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random_matched | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 1.10 |
| degree_topk | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 1.20 |
| pagerank | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 2.20 |
| betweenness_stim_to_readout | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 1.80 |
| kcore_scc | 3 | 0.00 | no | 0.00 | 0.00 | 0.50 | 0.00 | no | – | 0 | 2.60 |
| recurrence_loop | 3 | 0.00 | no | 0.33 | 0.00 | 0.00 | 0.00 | no | – | 0 | 1.10 |
| community | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 4.50 |
| statistical_motif | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 3.90 |
| greedy_prune_sim | 3 | 1.00 | yes | 1.00 | 1.00 | 1.00 | 1.00 | yes | 1.00 | 3 | 107 |

## male-cns_v1.0

| method | k | E-core recall | I-slot | precision | Jaccard | type-level E recall | sufficiency frac | sufficiency pass | necessity acc | claims | method wall s |
|---|---|---|---|---|---|---|---|---|---|---|---|
| random_matched | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 1.10 |
| degree_topk | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 1.10 |
| pagerank | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 2.00 |
| betweenness_stim_to_readout | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 1.70 |
| kcore_scc | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 2.00 |
| recurrence_loop | 3 | 0.00 | no | 0.00 | 0.00 | 0.00 | 0.00 | no | – | 0 | 1.20 |
| community | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 3.20 |
| statistical_motif | 3 | 0.50 | no | 0.33 | 0.20 | 0.50 | 0.00 | no | – | 0 | 3.00 |
| greedy_prune_sim | 3 | 1.00 | yes | 1.00 | 1.00 | 1.00 | 1.00 | yes | 1.00 | 3 | 83.70 |

