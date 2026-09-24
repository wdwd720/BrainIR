# Synthetic tournament — adv_h_v12

suite `adversarial_heldout`; 396 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 688.5 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 396 | 0.89 [0.86, 0.92] | 0.48 [0.43, 0.53] | 0.84 | 0.91 | 1.00 | 1.00 | 0.95 | 0.93 | 187.00 | 3.00 | 0.95 | 0.00 | 0.96 / 0.82 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 0.89 | 0.99 | 0.01 | 0.00 | 0.00 | 0.44 | 0.02 / 0.02 | – |

## Adversarial traps (third-party scorer, review G)

correct = the core is an acceptable core (degenerate instances: the result flags that no compact mechanism exists); confident-wrong = every core member at P >= 0.85 and not correct.

| method | runs (failed) | correct | confident-wrong | contested Brier | per trap: correct / confident-wrong / latent backup / essential recall |
|---|---|---|---|---|---|
| brainir_v1 | 396 (0) | 0.98 | 0.02 | 0.01 | distributed_drive 1.00/0.00/0.00/–; fragile_vs_robust 1.00/0.00/0.00/–; identical_decoy 1.00/0.00/0.00/1.00; latent_backup 1.00/0.00/0.00/1.00; masked_gate 1.00/0.00/0.00/1.00; subset_of_draws 0.75/0.19/0.00/0.83 |

Reliability (pooled calibration items: bin -> mean p / observed / n):

- brainir_v1: [0.00, 0.05) 0.02/0.01/974; [0.05, 0.30) 0.17/0.00/2; [0.30, 0.60) 0.55/0.61/28; [0.60, 0.85) 0.73/0.67/385; [0.85, 1.00) 0.97/0.98/1198

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| distributed_drive:identical | 0.00 / 638 (n=18) |
| distributed_drive:jittered | 0.00 / 518 (n=18) |
| fragile_vs_robust:band | 1.00 / 195 (n=18) |
| fragile_vs_robust:two_impl_rhythm | 1.00 / 223 (n=18) |
| identical_decoy:ei_rhythm | 1.00 / 153 (n=18) |
| identical_decoy:ffd_band | 1.00 / 239 (n=18) |
| identical_decoy:memory_persistence | 1.00 / 104 (n=18) |
| identical_decoy:nfc_band | 1.00 / 275 (n=18) |
| latent_backup:band | 1.00 / 174 (n=18) |
| latent_backup:band_active_head | 1.00 / 187 (n=18) |
| latent_backup:band_overlap | 1.00 / 178 (n=18) |
| latent_backup:rhythm_delayed | 1.00 / 368 (n=18) |
| latent_backup:rhythm_ring | 1.00 / 197 (n=18) |
| masked_gate:dio_rhythm | 1.00 / 174 (n=18) |
| masked_gate:ei_rhythm | 1.00 / 99 (n=18) |
| masked_gate:ffd_band | 1.00 / 123 (n=18) |
| masked_gate:integrator_ramp | 1.00 / 86 (n=18) |
| masked_gate:memory_persistence | 1.00 / 87 (n=18) |
| masked_gate:nfc_band | 1.00 / 345 (n=18) |
| masked_gate:wta_selectivity | 1.00 / 126 (n=18) |
| subset_of_draws:ei_rhythm | 0.72 / 262 (n=18) |
| subset_of_draws:latch_persistence | 0.83 / 194 (n=18) |
