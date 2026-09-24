# Synthetic tournament — adv_h_comparators

suite `adversarial_heldout`; 1188 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 1490.2 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| greedy_plus | 396 | 0.73 [0.69, 0.78] | 0.54 [0.49, 0.59] | 0.86 | 0.85 | 1.00 | 1.00 | 0.91 | 0.90 | 146.00 | 3.00 | 0.93 | 0.01 | 0.82 / 0.53 |
| greedy_reference | 396 | 0.19 [0.15, 0.23] | 0.12 [0.09, 0.15] | 0.17 | 0.24 | 0.50 | 0.20 | 0.62 | 0.60 | 244.00 | 3.00 | – | 0.22 | 0.78 / 0.41 |
| group_probe | 396 | 0.65 [0.61, 0.70] | 0.44 [0.39, 0.49] | 0.86 | 0.82 | 1.00 | 1.00 | 0.92 | 0.89 | 193.00 | 3.00 | 0.83 | 0.01 | 0.82 / 0.56 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| greedy_plus | 0.73 | 0.89 | 0.18 | 0.03 | 0.04 | 0.47 | 0.12 / 0.12 | – |
| greedy_reference | 0.11 | 0.40 | 0.82 | 0.20 | 0.62 | 0.46 | 0.73 / 0.73 | – |
| group_probe | 0.65 | 0.97 | 0.05 | 0.15 | 0.15 | 0.42 | 0.20 / 0.20 | – |

## Adversarial traps (third-party scorer, review G)

correct = the core is an acceptable core (degenerate instances: the result flags that no compact mechanism exists); confident-wrong = every core member at P >= 0.85 and not correct.

| method | runs (failed) | correct | confident-wrong | contested Brier | per trap: correct / confident-wrong / latent backup / essential recall |
|---|---|---|---|---|---|
| greedy_plus | 396 (0) | 0.70 | 0.25 | 0.10 | distributed_drive 0.00/0.58/0.00/–; fragile_vs_robust 1.00/0.00/0.00/–; identical_decoy 0.67/0.33/0.12/0.79; latent_backup 0.96/0.03/0.04/0.96; masked_gate 0.83/0.17/0.00/0.93; subset_of_draws 0.06/0.83/0.00/0.58 |
| group_probe | 396 (0) | 0.60 | 0.31 | 0.14 | distributed_drive 0.00/0.14/0.00/–; fragile_vs_robust 0.61/0.39/0.00/–; identical_decoy 0.53/0.47/0.22/1.00; latent_backup 0.52/0.48/0.48/0.99; masked_gate 0.99/0.01/0.00/1.00; subset_of_draws 0.19/0.69/0.00/0.58 |
| greedy_reference | 396 (0) | 0.08 | 0.92 | 0.95 | distributed_drive 0.00/1.00/0.00/–; fragile_vs_robust 0.33/0.67/0.00/–; identical_decoy 0.00/1.00/0.24/0.21; latent_backup 0.18/0.82/0.69/0.31; masked_gate 0.02/0.98/0.00/0.48; subset_of_draws 0.08/0.92/0.00/0.72 |

Reliability (pooled calibration items: bin -> mean p / observed / n):

- greedy_plus: [0.00, 0.05) 0.03/0.15/822; [0.05, 0.30) 0.15/0.20/366; [0.30, 0.60) 0.40/0.65/37; [0.60, 0.85) 0.69/0.65/50; [0.85, 1.00) 0.94/0.87/1343
- group_probe: [0.00, 0.05) 0.00/0.13/821; [0.05, 0.30) 0.30/0.48/357; [0.30, 0.60) 0.41/0.93/47; [0.60, 0.85) 0.79/0.67/207; [0.85, 1.00) 0.97/0.82/1167
- greedy_reference: [0.00, 0.05) 0.00/0.52/1540; [0.85, 1.00) 1.00/0.02/26031

## By family (success rate / median calls)

| family | greedy_plus | greedy_reference | group_probe |
|---|---|---|---|
| distributed_drive:identical | 0.00 / 613 (n=18) | 0.00 / 278 (n=18) | 0.00 / 378 (n=18) |
| distributed_drive:jittered | 0.00 / 584 (n=18) | 0.00 / 383 (n=18) | 0.00 / 293 (n=18) |
| fragile_vs_robust:band | 1.00 / 184 (n=18) | 0.00 / 244 (n=18) | 0.72 / 229 (n=18) |
| fragile_vs_robust:two_impl_rhythm | 1.00 / 178 (n=18) | 0.67 / 246 (n=18) | 0.56 / 174 (n=18) |
| identical_decoy:ei_rhythm | 0.61 / 137 (n=18) | 0.39 / 302 (n=18) | 1.00 / 152 (n=18) |
| identical_decoy:ffd_band | 1.00 / 240 (n=18) | 0.00 / 145 (n=18) | 0.78 / 173 (n=18) |
| identical_decoy:memory_persistence | 1.00 / 93 (n=18) | 1.00 / 264 (n=18) | 0.33 / 165 (n=18) |
| identical_decoy:nfc_band | 0.89 / 253 (n=18) | 0.33 / 581 (n=18) | 1.00 / 245 (n=18) |
| latent_backup:band | 1.00 / 166 (n=18) | 0.00 / 244 (n=18) | 0.28 / 182 (n=18) |
| latent_backup:band_active_head | 1.00 / 179 (n=18) | 0.00 / 338 (n=18) | 0.67 / 160 (n=18) |
| latent_backup:band_overlap | 1.00 / 146 (n=18) | 0.67 / 500 (n=18) | 0.78 / 176 (n=18) |
| latent_backup:rhythm_delayed | 0.89 / 280 (n=18) | 0.00 / 244 (n=18) | 0.44 / 238 (n=18) |
| latent_backup:rhythm_ring | 0.89 / 180 (n=18) | 0.22 / 382 (n=18) | 0.44 / 197 (n=18) |
| masked_gate:dio_rhythm | 0.89 / 162 (n=18) | 0.00 / 216 (n=18) | 1.00 / 219 (n=18) |
| masked_gate:ei_rhythm | 0.50 / 77 (n=18) | 0.11 / 244 (n=18) | 0.94 / 149 (n=18) |
| masked_gate:ffd_band | 0.94 / 105 (n=18) | 0.00 / 148 (n=18) | 1.00 / 153 (n=18) |
| masked_gate:integrator_ramp | 0.89 / 76 (n=18) | 0.06 / 244 (n=18) | 1.00 / 157 (n=18) |
| masked_gate:memory_persistence | 0.78 / 72 (n=18) | 0.00 / 244 (n=18) | 1.00 / 121 (n=18) |
| masked_gate:nfc_band | 0.83 / 318 (n=18) | 0.00 / 244 (n=18) | 1.00 / 260 (n=18) |
| masked_gate:wta_selectivity | 0.94 / 92 (n=18) | 0.22 / 244 (n=18) | 1.00 / 158 (n=18) |
| subset_of_draws:ei_rhythm | 0.11 / 114 (n=18) | 0.06 / 244 (n=18) | 0.17 / 111 (n=18) |
| subset_of_draws:latch_persistence | 0.00 / 74 (n=18) | 0.56 / 244 (n=18) | 0.22 / 210 (n=18) |
