# Paired reliability comparison — v12_vs_greedy_male-cns_v1.0

network `male-cns_v1.0`; A = `greedy_prune_sim_frozen`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.891 | 0.969 | +0.078 [+0.000, +0.188] |
| functional_pass | 0.917 | 1.000 | +0.083 [+0.000, +0.208] |
| core_size | 3.000 | 3.000 | +0.000 [+0.000, +0.000] |
| calls | 550.000 | 386.125 | -163.875 [-177.292, -148.667] |
| simulated_seconds | 550.000 | 772.250 | +222.250 [+195.417, +252.667] |
| identity consistency (pairwise Jaccard, no self-pairs) | 0.872 | 1.000 | +0.128 [+0.000, +0.288] |
| modal-core frequency | 0.92 | 1.00 | |
| same core in the paired run (A vs B, same order and seed) | 22 of 24 | | paired Jaccard 0.933; modal cores equal |
