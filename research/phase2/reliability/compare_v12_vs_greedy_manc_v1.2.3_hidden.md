# Paired reliability comparison — v12_vs_greedy_manc_v1.2.3_hidden

network `manc_v1.2.3`; A = `greedy_prune_sim_frozen`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.667 | 1.000 | +0.333 [+0.333, +0.333] |
| functional_pass | 0.667 | 1.000 | +0.333 [+0.333, +0.333] |
| core_size | 3.000 | 3.167 | +0.167 [+0.042, +0.333] |
| calls | 754.958 | 403.042 | -351.917 [-357.833, -345.042] |
| simulated_seconds | 754.958 | 806.083 | +51.125 [+42.208, +60.250] |
| identity consistency (pairwise Jaccard, no self-pairs) | 0.649 | 0.847 | +0.198 [+0.025, +0.395] |
| modal-core frequency | 0.67 | 0.83 | |
| HIDDEN structural success | 0.67 | 0.88 | +0.21 [+0.04, +0.33] (runs: 6 B-only / 1 A-only, McNemar p = 0.125; order clusters 6 B / 1 A / 1 tied, sign test p = 0.125) |
