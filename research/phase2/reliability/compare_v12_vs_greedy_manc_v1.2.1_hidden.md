# Paired reliability comparison — v12_vs_greedy_manc_v1.2.1_hidden

network `manc_v1.2.1`; A = `greedy_prune_sim_frozen`, B = `brainir_v1`; 24 paired runs (node order x seed) in 8 node-order clusters; failed runs A / B: 0 / 0 (counted as failures); 95 % CIs resample node orders

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.667 | 1.000 | +0.333 [+0.208, +0.458] |
| functional_pass | 0.667 | 1.000 | +0.333 [+0.208, +0.458] |
| core_size | 3.000 | 3.250 | +0.250 [+0.125, +0.417] |
| calls | 776.708 | 399.000 | -377.708 [-403.876, -348.832] |
| simulated_seconds | 776.708 | 798.000 | +21.292 [-25.793, +72.626] |
| identity consistency (pairwise Jaccard, no self-pairs) | 0.629 | 0.799 | +0.170 [+0.100, +0.272] |
| modal-core frequency | 0.67 | 0.75 | |
| HIDDEN structural success | 0.67 | 0.83 | +0.17 [+0.04, +0.29] (runs: 5 B-only / 1 A-only, McNemar p = 0.219; order clusters 4 B / 0 A / 4 tied, sign test p = 0.125) |
