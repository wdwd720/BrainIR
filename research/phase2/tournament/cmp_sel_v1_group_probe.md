# brainir_v1 vs group_probe — paired comparison

Sources: `sel_v1_b1000.json`, `sel_mech_b1000_part1.json.gz`, `sel_mech_b1000_part2.json.gz`, `sel_mech_b1000_part3.json.gz`

342 paired runs on 57 instances (same instance, node order and seed). Differences are brainir_v1 - group_probe (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | group_probe | difference [95% CI] |
|---|---|---|---|
| structural_success | 1.000 | 1.000 | +0.000 [+0.000, +0.000] |
| causal_functional_success | 1.000 | 0.953 | +0.047 [+0.006, +0.102] |
| functional_success_preregistered | 0.912 | 0.883 | +0.029 [+0.000, +0.070] |
| planted_success | 0.947 | 0.956 | -0.009 [-0.026, +0.000] |
| robust_sd_x2 | 0.921 | 0.923 | -0.002 [-0.013, +0.009] |
| robust_weight_noise | 0.836 | 0.839 | -0.004 [-0.029, +0.018] |
| nominal_pass | 0.996 | 0.996 | +0.000 [+0.000, +0.000] |
| core_size | 2.404 | 2.523 | -0.120 [-0.231, -0.032] |
| calls | 105.728 | 141.860 | +36.132 [+8.669, +70.693] |
| identity_jaccard | 0.968 | 0.947 | +0.021 [-0.014, +0.057] |
| identical_cores | 0.947 | 0.860 | +0.088 [+0.000, +0.175] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than group_probe: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): no / yes / no
- rule PASSES
