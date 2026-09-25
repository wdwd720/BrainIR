# Synthetic tournament — conf_adv

suite `adversarial_final`; 1584 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 3322.4 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 396 | 0.89 [0.86, 0.92] | 0.46 [0.41, 0.51] | 0.83 | 0.89 | 1.00 | 1.00 | 0.95 | 0.90 | 185.00 | 3.00 | 0.95 | 0.00 | 0.96 / 0.85 |
| greedy_plus | 396 | 0.72 [0.67, 0.76] | 0.56 [0.51, 0.60] | 0.88 | 0.85 | 1.00 | 1.00 | 0.91 | 0.87 | 148.00 | 3.00 | 0.92 | 0.01 | 0.80 / 0.42 |
| greedy_reference | 396 | 0.18 [0.14, 0.21] | 0.13 [0.10, 0.17] | 0.19 | 0.22 | 0.50 | 0.25 | 0.64 | 0.60 | 244.00 | 3.00 | – | 0.21 | 0.79 / 0.45 |
| group_probe | 396 | 0.68 [0.63, 0.73] | 0.41 [0.37, 0.46] | 0.85 | 0.81 | 1.00 | 1.00 | 0.91 | 0.88 | 212.00 | 3.00 | 0.83 | 0.01 | 0.83 / 0.61 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 0.89 | 1.00 | 0.00 | 0.00 | 0.00 | 0.41 | 0.02 / 0.02 | – |
| greedy_plus | 0.72 | 0.90 | 0.18 | 0.04 | 0.05 | 0.44 | 0.12 / 0.12 | – |
| greedy_reference | 0.14 | 0.38 | 0.86 | 0.19 | 0.57 | 0.49 | 0.72 / 0.72 | – |
| group_probe | 0.68 | 0.98 | 0.03 | 0.14 | 0.15 | 0.38 | 0.18 / 0.18 | – |

## Adversarial traps (third-party scorer, review G)

correct = the core is an acceptable core (degenerate instances: the result flags that no compact mechanism exists); confident-wrong = every core member at P >= 0.85 and not correct.

| method | runs (failed) | correct | confident-wrong | contested Brier | per trap: correct / confident-wrong / latent backup / essential recall |
|---|---|---|---|---|---|
| brainir_v1 | 396 (0) | 0.98 | 0.01 | 0.01 | distributed_drive 1.00/0.00/0.00/–; fragile_vs_robust 1.00/0.00/0.00/–; identical_decoy 1.00/0.00/0.00/1.00; latent_backup 1.00/0.00/0.00/1.00; masked_gate 1.00/0.00/0.00/1.00; subset_of_draws 0.78/0.08/0.00/0.94 |
| greedy_plus | 396 (0) | 0.72 | 0.20 | 0.12 | distributed_drive 0.00/0.33/0.00/–; fragile_vs_robust 1.00/0.00/0.00/–; identical_decoy 0.82/0.18/0.17/0.89; latent_backup 0.98/0.02/0.02/0.97; masked_gate 0.79/0.21/0.00/0.92; subset_of_draws 0.08/0.75/0.00/0.47 |
| group_probe | 396 (0) | 0.67 | 0.24 | 0.13 | distributed_drive 0.00/0.19/0.00/–; fragile_vs_robust 0.72/0.25/0.00/–; identical_decoy 0.75/0.25/0.25/1.00; latent_backup 0.57/0.43/0.43/1.00; masked_gate 1.00/0.00/0.00/1.00; subset_of_draws 0.28/0.64/0.00/0.69 |
| greedy_reference | 396 (0) | 0.09 | 0.91 | 0.94 | distributed_drive 0.00/1.00/0.00/–; fragile_vs_robust 0.33/0.67/0.00/–; identical_decoy 0.00/1.00/0.26/0.28; latent_backup 0.26/0.74/0.61/0.36; masked_gate 0.01/0.99/0.00/0.41; subset_of_draws 0.00/1.00/0.00/0.50 |

Reliability (pooled calibration items: bin -> mean p / observed / n):

- brainir_v1: [0.00, 0.05) 0.02/0.01/992; [0.05, 0.30) 0.19/0.50/4; [0.30, 0.60) 0.52/0.65/37; [0.60, 0.85) 0.76/0.71/406; [0.85, 1.00) 0.97/0.98/1183
- greedy_plus: [0.00, 0.05) 0.03/0.15/811; [0.05, 0.30) 0.15/0.18/372; [0.30, 0.60) 0.33/0.72/24; [0.60, 0.85) 0.61/0.17/551; [0.85, 1.00) 0.94/0.91/1302
- group_probe: [0.00, 0.05) 0.00/0.13/824; [0.05, 0.30) 0.30/0.45/360; [0.30, 0.60) 0.42/0.86/24; [0.60, 0.85) 0.79/0.71/198; [0.85, 1.00) 0.97/0.84/1249
- greedy_reference: [0.00, 0.05) 0.00/0.52/1526; [0.85, 1.00) 1.00/0.03/23151

## By family (success rate / median calls)

| family | brainir_v1 | greedy_plus | greedy_reference | group_probe |
|---|---|---|---|---|
| distributed_drive:identical | 0.00 / 642 (n=18) | 0.00 / 580 (n=18) | 0.00 / 352 (n=18) | 0.00 / 368 (n=18) |
| distributed_drive:jittered | 0.00 / 506 (n=18) | 0.00 / 534 (n=18) | 0.00 / 342 (n=18) | 0.00 / 264 (n=18) |
| fragile_vs_robust:band | 1.00 / 257 (n=18) | 1.00 / 202 (n=18) | 0.00 / 244 (n=18) | 0.89 / 187 (n=18) |
| fragile_vs_robust:two_impl_rhythm | 1.00 / 244 (n=18) | 1.00 / 183 (n=18) | 0.67 / 378 (n=18) | 0.67 / 252 (n=18) |
| identical_decoy:ei_rhythm | 1.00 / 172 (n=18) | 0.72 / 124 (n=18) | 0.28 / 263 (n=18) | 1.00 / 209 (n=18) |
| identical_decoy:ffd_band | 1.00 / 183 (n=18) | 1.00 / 172 (n=18) | 0.00 / 184 (n=18) | 1.00 / 238 (n=18) |
| identical_decoy:memory_persistence | 1.00 / 108 (n=18) | 0.72 / 95 (n=18) | 1.00 / 264 (n=18) | 0.00 / 192 (n=18) |
| identical_decoy:nfc_band | 1.00 / 178 (n=18) | 0.83 / 162 (n=18) | 0.00 / 560 (n=18) | 1.00 / 199 (n=18) |
| latent_backup:band | 1.00 / 197 (n=18) | 1.00 / 210 (n=18) | 0.00 / 244 (n=18) | 0.06 / 168 (n=18) |
| latent_backup:band_active_head | 1.00 / 223 (n=18) | 1.00 / 218 (n=18) | 0.00 / 244 (n=18) | 0.78 / 220 (n=18) |
| latent_backup:band_overlap | 1.00 / 166 (n=18) | 1.00 / 147 (n=18) | 0.67 / 500 (n=18) | 1.00 / 248 (n=18) |
| latent_backup:rhythm_delayed | 1.00 / 355 (n=18) | 1.00 / 298 (n=18) | 0.00 / 244 (n=18) | 0.39 / 245 (n=18) |
| latent_backup:rhythm_ring | 1.00 / 218 (n=18) | 0.89 / 190 (n=18) | 0.61 / 265 (n=18) | 0.61 / 270 (n=18) |
| masked_gate:dio_rhythm | 1.00 / 165 (n=18) | 0.83 / 155 (n=18) | 0.00 / 222 (n=18) | 1.00 / 215 (n=18) |
| masked_gate:ei_rhythm | 1.00 / 101 (n=18) | 0.89 / 100 (n=18) | 0.06 / 376 (n=18) | 1.00 / 152 (n=18) |
| masked_gate:ffd_band | 1.00 / 123 (n=18) | 0.78 / 102 (n=18) | 0.00 / 228 (n=18) | 1.00 / 144 (n=18) |
| masked_gate:integrator_ramp | 1.00 / 88 (n=18) | 0.56 / 68 (n=18) | 0.00 / 244 (n=18) | 1.00 / 147 (n=18) |
| masked_gate:memory_persistence | 1.00 / 81 (n=18) | 0.83 / 72 (n=18) | 0.00 / 244 (n=18) | 1.00 / 136 (n=18) |
| masked_gate:nfc_band | 1.00 / 188 (n=18) | 0.78 / 171 (n=18) | 0.00 / 244 (n=18) | 1.00 / 217 (n=18) |
| masked_gate:wta_selectivity | 1.00 / 149 (n=18) | 0.83 / 123 (n=18) | 0.00 / 482 (n=18) | 1.00 / 125 (n=18) |
| subset_of_draws:ei_rhythm | 0.67 / 310 (n=18) | 0.00 / 166 (n=18) | 0.17 / 376 (n=18) | 0.33 / 160 (n=18) |
| subset_of_draws:latch_persistence | 0.89 / 197 (n=18) | 0.17 / 69 (n=18) | 0.44 / 244 (n=18) | 0.28 / 174 (n=18) |
