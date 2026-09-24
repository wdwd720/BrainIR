# brainir_v1 vs cem_search — paired comparison

Sources: `sel_v1_b1000.json`, `sel_mech_b1000_part1.json.gz`, `sel_mech_b1000_part2.json.gz`, `sel_mech_b1000_part3.json.gz`

342 paired runs on 57 instances (same instance, node order and seed). Differences are brainir_v1 - cem_search (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | cem_search | difference [95% CI] |
|---|---|---|---|
| structural_success | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| causal_functional_success | 1.000 | 0.997 | +0.003 [+0.000, +0.009] |
| functional_success_preregistered | 0.912 | 0.909 | +0.003 [+0.000, +0.009] |
| planted_success | 0.947 | 0.930 | +0.018 [+0.000, +0.044] |
| robust_sd_x2 | 0.921 | 0.915 | +0.006 [-0.007, +0.021] |
| robust_weight_noise | 0.836 | 0.822 | +0.014 [-0.005, +0.037] |
| nominal_pass | 0.996 | 0.992 | +0.004 [+0.000, +0.010] |
| core_size | 2.404 | 2.418 | -0.015 [-0.038, +0.000] |
| calls | 105.728 | 114.591 | +8.863 [-2.936, +23.603] |
| identity_jaccard | 0.968 | 0.910 | +0.058 [+0.011, +0.110] |
| identical_cores | 0.947 | 0.807 | +0.140 [+0.053, +0.246] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than cem_search: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): yes / no / no
- rule PASSES
