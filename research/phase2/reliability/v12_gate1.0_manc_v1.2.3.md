# Reliability sweep — v12_gate1.0_manc_v1.2.3

method `brainir_v1` on `manc_v1.2.3` (bundle `efc33d775d88`), 8 node orders x seeds [0, 1, 2], budget 1000; 24 runs, 0 failed; wall 3192.6 s

- SENSITIVITY ANALYSIS (review D, D4), not the locked condition: every variant carries a criterion.json with rhythm amplitude gate 1.0 Hz; discovery and fidelity use it

- identity consistency (node orders x parameter draws): pairwise Jaccard mean 0.847 (min 0.500); modal core frequency 0.75; size 4-5 (mean 4.04)
- functional fidelity (keep-only, fresh seeds): mean 1.000; pass rate 1.000
- simulator calls mean 413.0833333333333; wall per run 1135.5333333333333 s
