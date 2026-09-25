# Synthetic tournament — conf_mech_b1000

suite `mechanisms_v1_final`; 684 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 1886.3 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 342 | 1.00 [1.00, 1.00] | 0.91 [0.88, 0.94] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.95 | 115.00 | 2.00 | 0.91 | 0.00 | 0.96 / 0.93 |
| greedy_reference | 342 | 0.75 [0.71, 0.80] | 0.15 [0.12, 0.19] | 0.17 | 0.75 | 1.00 | 0.33 | 0.78 | 0.73 | 236.00 | 3.00 | – | 0.21 | 0.80 / 0.53 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 1.00 | 1.00 | 0.00 | 0.00 | 0.00 | 0.33 | 0.02 / 0.10 | 1.00 |
| greedy_reference | 0.58 | 0.73 | 0.45 | 0.00 | 0.27 | 0.29 | 0.37 / 0.48 | 1.00 |

## By family (success rate / median calls)

| family | brainir_v1 | greedy_reference |
|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 138 (n=42) | 0.00 / 66 (n=42) |
| ei_pair_oscillator | 1.00 / 88 (n=48) | 0.88 / 310 (n=48) |
| feedforward_driver | 1.00 / 132 (n=24) | 0.50 / 145 (n=24) |
| integrator | 1.00 / 61 (n=12) | 1.00 / 49 (n=12) |
| memory_switch | 1.00 / 60 (n=42) | 1.00 / 152 (n=42) |
| negative_feedback_controller | 1.00 / 88 (n=24) | 0.75 / 204 (n=24) |
| redundant_oscillator | 1.00 / 174 (n=42) | 0.93 / 234 (n=42) |
| ring_oscillator | 1.00 / 128 (n=30) | 0.80 / 340 (n=30) |
| two_implementations | 1.00 / 230 (n=48) | 0.88 / 269 (n=48) |
| winner_take_all | 1.00 / 71 (n=30) | 0.90 / 206 (n=30) |
