# Paired reliability comparison — v12_locked_vs_gate1.0_manc_v1.2.1

network `manc_v1.2.1`; A = `brainir_v1`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 1.000 | 0.964 | -0.036 [-0.073, -0.010] |
| functional_pass | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| core_size | 3.250 | 4.000 | +0.750 [+0.583, +0.875] |
| calls | 399.000 | 408.208 | +9.208 [-27.420, +59.125] |
| simulated_seconds | 798.000 | 816.417 | +18.417 [-54.840, +118.250] |
| identity consistency (pairwise Jaccard, no self-pairs) | 0.799 | 0.845 | +0.045 [-0.102, +0.198] |
| modal-core frequency | 0.75 | 0.75 | |
| same core in the paired run (A vs B, same order and seed) | 3 of 24 | | paired Jaccard 0.692; modal cores differ |
