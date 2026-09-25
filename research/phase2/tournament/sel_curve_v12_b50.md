# Synthetic tournament — sel_curve_v12_b50

suite `mechanisms_v1_heldout`; 108 runs; budget 50 calls; seeds [0]; networks ['main', 'order1']; wall 328.8 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 108 | 1.00 [1.00, 1.00] | 0.86 [0.80, 0.93] | 0.95 | 1.00 | 1.00 | 1.00 | 1.00 | – | 50.00 | 2.00 | 0.91 | 0.00 | 0.94 / 0.93 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.32 | 0.02 / 0.15 | 1.00 |

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 50 (n=14) |
| ei_pair_oscillator | 1.00 / 50 (n=14) |
| feedforward_driver | 1.00 / 50 (n=8) |
| integrator | 1.00 / 46 (n=4) |
| memory_switch | 1.00 / 45 (n=14) |
| negative_feedback_controller | 1.00 / 50 (n=8) |
| redundant_oscillator | 1.00 / 50 (n=14) |
| ring_oscillator | 1.00 / 50 (n=8) |
| two_implementations | 1.00 / 50 (n=14) |
| winner_take_all | 1.00 / 50 (n=10) |
