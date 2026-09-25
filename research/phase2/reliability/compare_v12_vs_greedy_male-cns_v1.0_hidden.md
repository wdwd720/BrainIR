# Paired reliability comparison — v12_vs_greedy_male-cns_v1.0_hidden

network `male-cns_v1.0`; A = `greedy_prune_sim_frozen`, B = `brainir_v1`; 24 paired runs (node order x seed)

| metric | A | B | B - A [95% CI] |
|---|---|---|---|
| functional_fidelity | 0.891 | 0.969 | +0.078 [+0.000, +0.198] |
| functional_pass | 0.917 | 1.000 | +0.083 [+0.000, +0.208] |
| core_size | 3.000 | 3.000 | +0.000 [+0.000, +0.000] |
| calls | 550.000 | 386.125 | -163.875 [-178.708, -146.750] |
| simulated_seconds | 550.000 | 772.250 | +222.250 [+192.167, +255.504] |
| identity consistency (pairwise Jaccard) | 0.872 | 1.000 | +0.128 [+0.000, +0.275] |
| modal-core frequency | 0.92 | 1.00 | |
| HIDDEN structural success | 0.92 | 1.00 | +0.08 [+0.00, +0.21] (McNemar p = 0.5) |
