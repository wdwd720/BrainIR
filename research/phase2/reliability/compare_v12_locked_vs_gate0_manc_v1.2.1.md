# Paired reliability comparison — v12_locked_vs_gate0_manc_v1.2.1

network `manc_v1.2.1`; A = `brainir_v1`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| functional_pass | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| core_size | 3.250 | 3.250 | +0.000 [+0.000, +0.000] |
| calls | 399.000 | 395.333 | -3.667 [-6.250, -1.667] |
| simulated_seconds | 798.000 | 790.667 | -7.333 [-12.500, -3.333] |
| identity consistency (pairwise Jaccard, no self-pairs) | 0.799 | 0.799 | +0.000 [+0.000, +0.000] |
| modal-core frequency | 0.75 | 0.75 | |
| same core in the paired run (A vs B, same order and seed) | 24 of 24 | | paired Jaccard 1.000; modal cores equal |
