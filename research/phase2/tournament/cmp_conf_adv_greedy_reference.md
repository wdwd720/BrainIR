# brainir_v1 vs greedy_reference — paired comparison

Sources: `conf_adv.json.gz`

396 paired runs on 66 instances (same instance, node order and seed). Differences are brainir_v1 - greedy_reference (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | greedy_reference | difference [95% CI] |
|---|---|---|---|
| structural_success | 0.889 | 0.177 | +0.712 [+0.609, +0.811] |
| causal_functional_success | 0.833 | 0.149 | +0.684 [+0.563, +0.801] |
| functional_success_preregistered | 0.457 | 0.134 | +0.323 [+0.194, +0.452] |
| planted_success | 0.889 | 0.177 | +0.712 [+0.609, +0.811] |
| robust_sd_x2 | 0.905 | 0.598 | +0.307 [+0.217, +0.405] |
| robust_weight_noise | 0.883 | 0.592 | +0.292 [+0.199, +0.391] |
| nominal_pass | 0.945 | 0.640 | +0.305 [+0.213, +0.407] |
| core_size | 4.513 | 58.909 | -54.396 [-82.481, -29.434] |
| success_intact | 0.889 | 0.139 | +0.750 [+0.654, +0.843] |
| essential_recall | 0.996 | 0.375 | +0.621 [+0.524, +0.716] |
| latent_backup_returned | 0.000 | 0.187 | -0.187 [-0.280, -0.098] |
| adversarial_correct | 0.980 | 0.091 | +0.889 [+0.813, +0.952] |
| adversarial_confident_wrong | 0.008 | 0.909 | -0.902 [-0.962, -0.828] |
| calls | 240.096 | 411.356 | +171.260 [+106.235, +242.559] |
| identity_jaccard | 0.965 | 0.787 | +0.178 [+0.122, +0.238] |
| identical_cores | 0.848 | 0.455 | +0.394 [+0.273, +0.515] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than greedy_reference: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): yes / yes / yes
- rule PASSES
