# brainir_v1 vs greedy_plus — paired comparison

Sources: `conf_adv.json.gz`

396 paired runs on 66 instances (same instance, node order and seed). Differences are brainir_v1 - greedy_plus (calls: calls saved by brainir_v1); 95 % CIs resample instances. Failed runs count as unsuccessful at the full budget.

| metric | brainir_v1 | greedy_plus | difference [95% CI] |
|---|---|---|---|
| structural_success | 0.889 | 0.720 | +0.169 [+0.116, +0.227] |
| causal_functional_success | 0.833 | 0.874 | -0.040 [-0.076, -0.010] |
| functional_success_preregistered | 0.457 | 0.556 | -0.098 [-0.136, -0.061] |
| planted_success | 0.889 | 0.720 | +0.169 [+0.116, +0.227] |
| robust_sd_x2 | 0.905 | 0.874 | +0.031 [+0.012, +0.052] |
| robust_weight_noise | 0.883 | 0.848 | +0.035 [+0.014, +0.059] |
| nominal_pass | 0.945 | 0.907 | +0.039 [+0.016, +0.064] |
| core_size | 4.513 | 5.293 | -0.780 [-2.556, +0.326] |
| success_intact | 0.889 | 0.720 | +0.169 [+0.116, +0.227] |
| essential_recall | 0.996 | 0.897 | +0.099 [+0.059, +0.146] |
| latent_backup_returned | 0.000 | 0.035 | -0.035 [-0.063, -0.015] |
| adversarial_correct | 0.980 | 0.720 | +0.260 [+0.184, +0.338] |
| adversarial_confident_wrong | 0.008 | 0.205 | -0.197 [-0.258, -0.141] |
| calls | 240.096 | 209.386 | -30.710 [-43.266, -17.270] |
| identity_jaccard | 0.965 | 0.795 | +0.169 [+0.125, +0.218] |
| identical_cores | 0.848 | 0.424 | +0.424 [+0.303, +0.545] |

Pre-registered decision rule (SELECTION_PROTOCOL.md section 5):

- (a) success not lower than greedy_plus: **yes**
- (b) better on reliability / efficiency / robustness (CI entirely above 0): yes / no / yes
- rule PASSES
