# Synthetic tournament — ag_v12_baseline

suite `mechanisms_v1_heldout`; 47 runs; budget 1000 calls; seeds [0]; networks ['main']; wall 51.1 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 47 | 1.00 [1.00, 1.00] | 0.89 [0.81, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | – | 94.00 | 2.00 | 0.91 | 0.00 | – / – |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.32 | 0.03 / 0.12 | 1.00 |

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 129 (n=6) |
| ei_pair_oscillator | 1.00 / 77 (n=6) |
| feedforward_driver | 1.00 / 72 (n=3) |
| integrator | 1.00 / 54 (n=2) |
| memory_switch | 1.00 / 46 (n=6) |
| negative_feedback_controller | 1.00 / 100 (n=4) |
| redundant_oscillator | 1.00 / 180 (n=6) |
| ring_oscillator | 1.00 / 94 (n=3) |
| two_implementations | 1.00 / 208 (n=6) |
| winner_take_all | 1.00 / 75 (n=5) |
