# Paired reliability comparison — v12_locked_vs_gate1.0_manc_v1.2.3

network `manc_v1.2.3`; A = `brainir_v1`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| functional_pass | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| core_size | 3.167 | 4.042 | +0.875 [+0.667, +1.083] |
| calls | 403.042 | 413.083 | +10.042 [-7.043, +26.917] |
| simulated_seconds | 806.083 | 826.167 | +20.083 [-14.085, +53.833] |
| identity consistency (pairwise Jaccard, no self-pairs) | 0.847 | 0.847 | +0.000 [-0.166, +0.148] |
| modal-core frequency | 0.83 | 0.75 | |
| same core in the paired run (A vs B, same order and seed) | 1 of 24 | | paired Jaccard 0.662; modal cores differ |
