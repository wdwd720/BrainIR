# Paired reliability comparison — v12_locked_vs_gate1.0_male-cns_v1.0

network `male-cns_v1.0`; A = `brainir_v1`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.969 | 0.927 | -0.042 [-0.073, -0.016] |
| functional_pass | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| core_size | 3.000 | 3.542 | +0.542 [+0.250, +0.875] |
| calls | 386.125 | 486.625 | +100.500 [+66.040, +139.381] |
| simulated_seconds | 772.250 | 973.250 | +201.000 [+132.079, +278.763] |
| identity consistency (pairwise Jaccard, no self-pairs) | 1.000 | 0.740 | -0.260 [-0.400, -0.113] |
| modal-core frequency | 1.00 | 0.75 | |
| same core in the paired run (A vs B, same order and seed) | 0 of 24 | | paired Jaccard 0.501; modal cores differ |
