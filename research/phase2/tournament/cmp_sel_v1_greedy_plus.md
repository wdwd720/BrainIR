# brainir_v1 vs greedy_plus — paired comparison

Sources: `sel_v1_b1000.json`, `sel_mech_b1000_part1.json.gz`, `sel_mech_b1000_part2.json.gz`, `sel_mech_b1000_part3.json.gz`

342 paired runs on 57 instances (same instance, node order and seed). Differences are brainir_v1 - greedy_plus (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | greedy_plus | difference [95% CI] |
|---|---|---|---|
| structural_success | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| causal_functional_success | 1.000 | 0.997 | +0.003 [+0.000, +0.009] |
| functional_success_preregistered | 0.912 | 0.909 | +0.003 [+0.000, +0.009] |
| planted_success | 0.947 | 0.988 | -0.041 [-0.099, +0.000] |
| robust_sd_x2 | 0.921 | 0.933 | -0.012 [-0.028, +0.003] |
| robust_weight_noise | 0.836 | 0.857 | -0.022 [-0.056, +0.007] |
| nominal_pass | 0.996 | 0.995 | +0.001 [+0.000, +0.002] |
| core_size | 2.404 | 2.661 | -0.257 [-0.409, -0.123] |
| calls | 105.728 | 108.447 | +2.719 [-4.433, +10.314] |
| identity_jaccard | 0.968 | 0.882 | +0.086 [+0.033, +0.146] |
| identical_cores | 0.947 | 0.754 | +0.193 [+0.088, +0.298] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than greedy_plus: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): yes / no / no
- rule PASSES
