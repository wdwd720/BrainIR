# Reliability sweep — v12_gate0_male-cns_v1.0

method `brainir_v1` on `male-cns_v1.0` (bundle `efc33d775d88`), 8 node orders x seeds [0, 1, 2], budget 1000; 24 runs, 0 failed; wall 1278.7 s

- SENSITIVITY ANALYSIS (review D, D4), not the locked condition: every variant carries a criterion.json with rhythm amplitude gate 0.0 Hz; discovery and fidelity use it

- identity consistency (node orders x parameter draws): pairwise Jaccard mean 1.000 (min 1.000); modal core frequency 1.00; size 3-3 (mean 3.00)
- functional fidelity (keep-only, fresh seeds): mean 1.000; pass rate 1.000
- simulator calls mean 374.4166666666667; wall per run 871.4958333333334 s
