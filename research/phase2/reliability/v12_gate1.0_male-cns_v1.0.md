# Reliability sweep — v12_gate1.0_male-cns_v1.0

method `brainir_v1` on `male-cns_v1.0` (bundle `efc33d775d88`), 8 node orders x seeds [0, 1, 2], budget 1000; 24 runs, 0 failed; wall 2389.7 s

- SENSITIVITY ANALYSIS (review D, D4), not the locked condition: every variant carries a criterion.json with rhythm amplitude gate 1.0 Hz; discovery and fidelity use it

- identity consistency (node orders x parameter draws): pairwise Jaccard mean 0.740 (min 0.222); modal core frequency 0.75; size 3-6 (mean 3.54)
- functional fidelity (keep-only, fresh seeds): mean 0.927; pass rate 1.000
- simulator calls mean 486.625; wall per run 1047.1083333333333 s
