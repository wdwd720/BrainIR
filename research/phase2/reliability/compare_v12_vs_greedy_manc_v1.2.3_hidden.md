# Paired reliability comparison — v12_vs_greedy_manc_v1.2.3_hidden

network `manc_v1.2.3`; A = `greedy_prune_sim_frozen`, B = `brainir_v1`; 24 paired runs (node order x seed)

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.667 | 1.000 | +0.333 [+0.167, +0.542] |
| functional_pass | 0.667 | 1.000 | +0.333 [+0.167, +0.542] |
| core_size | 3.000 | 3.167 | +0.167 [+0.042, +0.333] |
| calls | 754.958 | 403.042 | -351.917 [-380.375, -321.958] |
| simulated_seconds | 754.958 | 806.083 | +51.125 [+11.041, +94.585] |
| identity consistency (pairwise Jaccard) | 0.649 | 0.847 | +0.198 [+0.003, +0.375] |
| modal-core frequency | 0.67 | 0.83 | |
| HIDDEN structural success | 0.67 | 0.88 | +0.21 [+0.00, +0.42] (McNemar p = 0.125) |
