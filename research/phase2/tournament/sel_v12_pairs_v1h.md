# Synthetic tournament — sel_v12_pairs_v1h

suite `pairs_v1_heldout`; 78 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['a']; wall 355.1 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 78 | 0.96 [0.91, 1.00] | 0.96 [0.91, 1.00] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.96 | 136.00 | 2.00 | 1.00 | 0.00 | 1.00 / 1.00 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## Is the answer the mechanism the intact network uses? (reviews A, G)

success_intact = structural success AND every core member participates in the intact network AND the core contains every neuron whose single silencing breaks the intact function (truth-essential). Brier (contested) scores the inclusion probabilities only on neurons in question (truth sufficient sets, latent backups, complications, the method's core and alternatives, anything given >= 0.1), against the best-matching set and against 'member of any listed sufficient set'.

| method | success_intact | essential recall | runs missing an essential | latent backup returned | silent core member | intact passes with core silenced | Brier contested (best / any) | essential acc. (unambiguous) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 0.96 | 1.00 | 0.00 | 0.00 | 0.00 | 0.19 | 0.06 / 0.10 | 1.00 |

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 148 (n=9) |
| ei_pair_oscillator | 1.00 / 124 (n=12) |
| feedforward_driver | 1.00 / 108 (n=9) |
| integrator | 1.00 / 72 (n=6) |
| memory_switch | 0.67 / 76 (n=9) |
| negative_feedback_controller | 1.00 / 138 (n=6) |
| redundant_oscillator | 1.00 / 297 (n=6) |
| ring_oscillator | 1.00 / 133 (n=12) |
| two_implementations | 1.00 / 382 (n=6) |
| winner_take_all | 1.00 / 95 (n=3) |

## Identity claims about the other network of each pair (review E)

A claim is correct only if both neurons are the same planted member; under an implementation shift only the retained alternative counts; on a null pair every claim is false.

| method | runs (with claims) | claims (correct) | precision | false: shift / null / structural decoy | claims on null pairs | core recall | Brier | reliability (bin: confidence -> observed, n) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 78 (42) | 90 (90) | 1.00 | 0 / 0 / 0 | 0 | 0.47 | 0.00 | 0.98->1.00 (90) |
