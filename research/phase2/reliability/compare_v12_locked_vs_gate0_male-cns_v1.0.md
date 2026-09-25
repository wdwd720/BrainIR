# Paired reliability comparison — v12_locked_vs_gate0_male-cns_v1.0

network `male-cns_v1.0`; A = `brainir_v1`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.969 | 1.000 | +0.031 [+0.000, +0.062] |
| functional_pass | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| core_size | 3.000 | 3.000 | +0.000 [+0.000, +0.000] |
| calls | 386.125 | 374.417 | -11.708 [-18.000, -6.125] |
| simulated_seconds | 772.250 | 748.833 | -23.417 [-36.000, -12.250] |
| identity consistency (pairwise Jaccard, no self-pairs) | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| modal-core frequency | 1.00 | 1.00 | |
| same core in the paired run (A vs B, same order and seed) | 24 of 24 | | paired Jaccard 1.000; modal cores equal |
