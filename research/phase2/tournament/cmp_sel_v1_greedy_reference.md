# brainir_v1 vs greedy_reference — paired comparison

Sources: `sel_v1_b1000.json`, `sel_mech_b1000_part1.json.gz`, `sel_mech_b1000_part2.json.gz`, `sel_mech_b1000_part3.json.gz`

342 paired runs on 57 instances (same instance, node order and seed). Differences are brainir_v1 - greedy_reference (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | greedy_reference | difference [95% CI] |
|---|---|---|---|
| structural_success | 1.000 | 0.743 | +0.257 [+0.146, +0.374] |
| causal_functional_success | 1.000 | 0.196 | +0.804 [+0.702, +0.898] |
| functional_success_preregistered | 0.912 | 0.196 | +0.716 [+0.596, +0.825] |
| planted_success | 0.947 | 0.620 | +0.327 [+0.211, +0.456] |
| robust_sd_x2 | 0.921 | 0.705 | +0.216 [+0.114, +0.330] |
| robust_weight_noise | 0.836 | 0.654 | +0.181 [+0.073, +0.298] |
| nominal_pass | 0.996 | 0.770 | +0.225 [+0.124, +0.336] |
| core_size | 2.404 | 27.091 | -24.687 [-46.927, -7.371] |
| calls | 105.728 | 303.711 | +197.982 [+140.895, +261.187] |
| identity_jaccard | 0.968 | 0.834 | +0.134 [+0.079, +0.198] |
| identical_cores | 0.947 | 0.632 | +0.316 [+0.193, +0.439] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than greedy_reference: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): yes / yes / yes
- rule PASSES
