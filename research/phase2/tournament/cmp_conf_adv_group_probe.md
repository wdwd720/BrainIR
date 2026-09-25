# brainir_v1 vs group_probe — paired comparison

Sources: `conf_adv.json.gz`

396 paired runs on 66 instances (same instance, node order and seed). Differences are brainir_v1 - group_probe (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | group_probe | difference [95% CI] |
|---|---|---|---|
| structural_success | 0.889 | 0.682 | +0.207 [+0.134, +0.288] |
| causal_functional_success | 0.833 | 0.843 | -0.010 [-0.030, +0.010] |
| functional_success_preregistered | 0.457 | 0.414 | +0.043 [-0.005, +0.096] |
| planted_success | 0.889 | 0.682 | +0.207 [+0.134, +0.288] |
| robust_sd_x2 | 0.905 | 0.875 | +0.030 [+0.012, +0.049] |
| robust_weight_noise | 0.883 | 0.848 | +0.035 [+0.018, +0.053] |
| nominal_pass | 0.945 | 0.915 | +0.030 [+0.014, +0.050] |
| core_size | 4.513 | 4.333 | +0.179 [-0.045, +0.366] |
| success_intact | 0.889 | 0.679 | +0.210 [+0.134, +0.293] |
| essential_recall | 0.996 | 0.978 | +0.018 [+0.000, +0.044] |
| latent_backup_returned | 0.000 | 0.144 | -0.144 [-0.222, -0.073] |
| adversarial_correct | 0.980 | 0.674 | +0.306 [+0.212, +0.402] |
| adversarial_confident_wrong | 0.008 | 0.242 | -0.235 [-0.318, -0.157] |
| calls | 240.096 | 291.674 | +51.578 [+10.143, +97.167] |
| identity_jaccard | 0.965 | 0.835 | +0.130 [+0.086, +0.178] |
| identical_cores | 0.848 | 0.606 | +0.242 [+0.152, +0.348] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than group_probe: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): yes / yes / yes
- rule PASSES
