# brainir_v1 vs greedy_reference — paired comparison

Sources: `conf_mech_b1000.json`

342 paired runs on 57 instances (same instance, node order and seed). Differences are brainir_v1 - greedy_reference (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | greedy_reference | difference [95% CI] |
|---|---|---|---|
| structural_success | 1.000 | 0.754 | +0.246 [+0.140, +0.360] |
| causal_functional_success | 1.000 | 0.155 | +0.845 [+0.754, +0.924] |
| functional_success_preregistered | 0.912 | 0.155 | +0.757 [+0.652, +0.857] |
| planted_success | 1.000 | 0.623 | +0.377 [+0.254, +0.500] |
| robust_sd_x2 | 0.954 | 0.733 | +0.221 [+0.114, +0.332] |
| robust_weight_noise | 0.851 | 0.670 | +0.181 [+0.073, +0.292] |
| nominal_pass | 0.996 | 0.777 | +0.219 [+0.113, +0.330] |
| core_size | 2.456 | 27.371 | -24.915 [-47.033, -7.579] |
| success_intact | 1.000 | 0.576 | +0.424 [+0.295, +0.553] |
| essential_recall | 1.000 | 0.728 | +0.272 [+0.172, +0.378] |
| latent_backup_returned | 0.000 | 0.000 | +0.000 [+0.000, +0.000] |
| calls | 149.816 | 290.117 | +140.301 [+84.853, +202.037] |
| identity_jaccard | 0.958 | 0.803 | +0.155 [+0.096, +0.217] |
| identical_cores | 0.930 | 0.526 | +0.404 [+0.281, +0.526] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than greedy_reference: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): yes / yes / yes
- rule PASSES
