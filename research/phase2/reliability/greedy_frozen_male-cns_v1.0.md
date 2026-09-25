# Reliability sweep — greedy_frozen_male-cns_v1.0

method `greedy_prune_sim_frozen` on `male-cns_v1.0` (bundle `efc33d775d88`), 8 node orders x seeds [0], budget 1000; 24 runs, 0 failed; wall 526.6 s

- identity consistency (node orders x parameter draws): pairwise Jaccard mean 0.872 (min 0.200); modal core frequency 0.92; size 3-3 (mean 3.00)
- functional fidelity (keep-only, fresh seeds): mean 0.891; pass rate 0.917
- simulator calls mean 550.0; wall per run 215.89583333333334 s

- HIDDEN evaluation (logged): success rate 0.917, E-core recall mean 0.958, inhibitory slot rate 0.917, precision mean 0.944
