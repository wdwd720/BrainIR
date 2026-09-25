# Paired reliability comparison — v12_vs_greedy_manc_v1.2.1

network `manc_v1.2.1`; A = `greedy_prune_sim_frozen`, B = `brainir_v1`; 24 paired runs (node order x seed)

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.667 | 1.000 | +0.333 [+0.167, +0.500] |
| functional_pass | 0.667 | 1.000 | +0.333 [+0.167, +0.542] |
| core_size | 3.000 | 3.250 | +0.250 [+0.083, +0.417] |
| calls | 776.708 | 399.000 | -377.708 [-419.168, -337.333] |
| simulated_seconds | 776.708 | 798.000 | +21.292 [-34.542, +76.959] |
| identity consistency (pairwise Jaccard) | 0.629 | 0.799 | +0.170 [+0.040, +0.277] |
| modal-core frequency | 0.67 | 0.75 | |
