# Synthetic tournament — adv_h_v10

suite `adversarial_heldout`; 396 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 1270.2 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 396 | 0.42 [0.37, 0.47] | 0.74 [0.70, 0.79] | 0.91 | 0.88 | 0.71 | 1.00 | 0.91 | 0.88 | 129.00 | 2.00 | 0.83 | 0.02 | 0.87 / 0.67 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 0.41 | 0.68 | 0.55 | 0.15 | 0.15 | 0.52 | 0.33 / 0.33 | – |

## Adversarial traps (third-party scorer, review G)

correct = the core is an acceptable core (degenerate instances: the result flags that no compact mechanism exists); confident-wrong = every core member at P >= 0.85 and not correct.

| method | runs (failed) | correct | confident-wrong | contested Brier | per trap: correct / confident-wrong / latent backup / essential recall |
|---|---|---|---|---|---|
| brainir_v1 | 396 (0) | 0.38 | 0.51 | 0.22 | distributed_drive 0.00/0.31/0.00/–; fragile_vs_robust 0.83/0.17/0.00/–; identical_decoy 0.76/0.07/0.00/0.96; latent_backup 0.32/0.68/0.68/0.46; masked_gate 0.28/0.72/0.00/0.73; subset_of_draws 0.00/0.81/0.00/0.61 |

Reliability (pooled calibration items: bin -> mean p / observed / n):

- brainir_v1: [0.00, 0.05) 0.03/0.24/942; [0.05, 0.30) 0.15/0.80/293; [0.30, 0.60) 0.45/0.56/347; [0.60, 0.85) 0.69/0.61/4; [0.85, 1.00) 0.93/0.76/1000

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| distributed_drive:identical | 0.00 / 526 (n=18) |
| distributed_drive:jittered | 0.00 / 419 (n=18) |
| fragile_vs_robust:band | 0.72 / 116 (n=18) |
| fragile_vs_robust:two_impl_rhythm | 0.94 / 123 (n=18) |
| identical_decoy:ei_rhythm | 1.00 / 104 (n=18) |
| identical_decoy:ffd_band | 1.00 / 183 (n=18) |
| identical_decoy:memory_persistence | 1.00 / 79 (n=18) |
| identical_decoy:nfc_band | 1.00 / 226 (n=18) |
| latent_backup:band | 0.00 / 122 (n=18) |
| latent_backup:band_active_head | 0.00 / 157 (n=18) |
| latent_backup:band_overlap | 0.78 / 139 (n=18) |
| latent_backup:rhythm_delayed | 0.67 / 274 (n=18) |
| latent_backup:rhythm_ring | 0.17 / 157 (n=18) |
| masked_gate:dio_rhythm | 0.28 / 135 (n=18) |
| masked_gate:ei_rhythm | 0.33 / 71 (n=18) |
| masked_gate:ffd_band | 0.33 / 94 (n=18) |
| masked_gate:integrator_ramp | 0.33 / 66 (n=18) |
| masked_gate:memory_persistence | 0.00 / 56 (n=18) |
| masked_gate:nfc_band | 0.33 / 256 (n=18) |
| masked_gate:wta_selectivity | 0.33 / 91 (n=18) |
| subset_of_draws:ei_rhythm | 0.00 / 122 (n=18) |
| subset_of_draws:latch_persistence | 0.00 / 86 (n=18) |
