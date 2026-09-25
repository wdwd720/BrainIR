# Synthetic tournament — abl_v12_adv_random_order

suite `adversarial_heldout`; 132 runs; budget 1000 calls; seeds [0]; networks ['main', 'order1']; wall 400.5 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 132 | 0.86 [0.80, 0.92] | 0.47 [0.39, 0.55] | 0.83 | 0.88 | 1.00 | 1.00 | 0.95 | 0.91 | 228.00 | 3.00 | 0.94 | 0.00 | 0.90 / 0.83 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 0.86 | 0.98 | 0.02 | 0.01 | 0.01 | 0.45 | 0.04 / 0.04 | – |

## Adversarial traps (third-party scorer, review G)

correct = the core is an acceptable core (degenerate instances: the result flags that no compact mechanism exists); confident-wrong = every core member at P >= 0.85 and not correct.

| method | runs (failed) | correct | confident-wrong | contested Brier | per trap: correct / confident-wrong / latent backup / essential recall |
|---|---|---|---|---|---|
| brainir_v1 | 132 (0) | 0.95 | 0.02 | 0.04 | distributed_drive 1.00/0.00/0.00/–; fragile_vs_robust 1.00/0.00/0.00/–; identical_decoy 0.92/0.00/0.04/0.93; latent_backup 1.00/0.00/0.00/1.00; masked_gate 1.00/0.00/0.00/1.00; subset_of_draws 0.67/0.25/0.00/0.83 |

Reliability (pooled calibration items: bin -> mean p / observed / n):

- brainir_v1: [0.00, 0.05) 0.02/0.04/331; [0.05, 0.30) 0.17/0.00/2; [0.30, 0.60) 0.50/0.44/61; [0.60, 0.85) 0.76/0.58/144; [0.85, 1.00) 0.98/1.00/364

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| distributed_drive:identical | 0.00 / 764 (n=6) |
| distributed_drive:jittered | 0.00 / 670 (n=6) |
| fragile_vs_robust:band | 1.00 / 184 (n=6) |
| fragile_vs_robust:two_impl_rhythm | 1.00 / 268 (n=6) |
| identical_decoy:ei_rhythm | 1.00 / 222 (n=6) |
| identical_decoy:ffd_band | 1.00 / 303 (n=6) |
| identical_decoy:memory_persistence | 0.83 / 106 (n=6) |
| identical_decoy:nfc_band | 0.83 / 569 (n=6) |
| latent_backup:band | 1.00 / 234 (n=6) |
| latent_backup:band_active_head | 1.00 / 234 (n=6) |
| latent_backup:band_overlap | 1.00 / 194 (n=6) |
| latent_backup:rhythm_delayed | 1.00 / 368 (n=6) |
| latent_backup:rhythm_ring | 1.00 / 248 (n=6) |
| masked_gate:dio_rhythm | 1.00 / 190 (n=6) |
| masked_gate:ei_rhythm | 1.00 / 111 (n=6) |
| masked_gate:ffd_band | 1.00 / 129 (n=6) |
| masked_gate:integrator_ramp | 1.00 / 89 (n=6) |
| masked_gate:memory_persistence | 1.00 / 94 (n=6) |
| masked_gate:nfc_band | 1.00 / 389 (n=6) |
| masked_gate:wta_selectivity | 1.00 / 124 (n=6) |
| subset_of_draws:ei_rhythm | 0.67 / 298 (n=6) |
| subset_of_draws:latch_persistence | 0.67 / 233 (n=6) |
