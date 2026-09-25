# Paired reliability comparison — v12_locked_vs_gate0_manc_v1.2.3

network `manc_v1.2.3`; A = `brainir_v1`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| functional_pass | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| core_size | 3.167 | 3.083 | -0.083 [-0.208, +0.000] |
| calls | 403.042 | 404.667 | +1.625 [-5.293, +9.542] |
| simulated_seconds | 806.083 | 809.333 | +3.250 [-10.585, +19.083] |
| identity consistency (pairwise Jaccard, no self-pairs) | 0.847 | 0.931 | +0.084 [+0.000, +0.162] |
| modal-core frequency | 0.83 | 0.92 | |
| same core in the paired run (A vs B, same order and seed) | 22 of 24 | | paired Jaccard 0.950; modal cores equal |
