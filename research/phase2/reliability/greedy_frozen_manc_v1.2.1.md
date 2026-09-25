# Reliability sweep — greedy_frozen_manc_v1.2.1

method `greedy_prune_sim_frozen` on `manc_v1.2.1` (bundle `efc33d775d88`), 8 node orders x seeds [0], budget 1000; 24 runs, 0 failed; wall 3492.8 s

- identity consistency (node orders x parameter draws): pairwise Jaccard mean 0.629 (min 0.200); modal core frequency 0.67; size 3-3 (mean 3.00)
- functional fidelity (keep-only, fresh seeds): mean 0.667; pass rate 0.667
- simulator calls mean 776.7083333333334; wall per run 327.43750000000006 s

- HIDDEN evaluation (logged): success rate 0.667, E-core recall mean 0.833, inhibitory slot rate 0.667, precision mean 0.889
