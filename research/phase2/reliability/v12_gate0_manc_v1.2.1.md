# Reliability sweep — v12_gate0_manc_v1.2.1

method `brainir_v1` on `manc_v1.2.1` (bundle `efc33d775d88`), 8 node orders x seeds [0, 1, 2], budget 1000; 24 runs, 0 failed; wall 1312.6 s

- SENSITIVITY ANALYSIS (review D, D4), not the locked condition: every variant carries a criterion.json with rhythm amplitude gate 0.0 Hz; discovery and fidelity use it

- identity consistency (node orders x parameter draws): pairwise Jaccard mean 0.799 (min 0.400); modal core frequency 0.75; size 3-4 (mean 3.25)
- functional fidelity (keep-only, fresh seeds): mean 1.000; pass rate 1.000
- simulator calls mean 395.3333333333333; wall per run 970.625 s
