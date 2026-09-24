# Synthetic tournament — sel_v1_pairs_v2h

suite `pairs_v2_heldout`; 81 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['a']; wall 260.5 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 81 | 1.00 [1.00, 1.00] | 0.93 [0.86, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.96 | 185.00 | 2.00 | 0.96 | 0.00 | 1.00 / 1.00 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 264 (n=9) |
| ei_pair_oscillator | 1.00 / 149 (n=12) |
| feedforward_driver | 1.00 / 185 (n=9) |
| integrator | 1.00 / 148 (n=6) |
| memory_switch | 1.00 / 116 (n=9) |
| negative_feedback_controller | 1.00 / 212 (n=6) |
| redundant_oscillator | 1.00 / 212 (n=6) |
| ring_oscillator | 1.00 / 188 (n=12) |
| two_implementations | 1.00 / 335 (n=6) |
| winner_take_all | 1.00 / 216 (n=6) |

## Identity claims about the other network of each pair (review E)

A claim is correct only if both neurons are the same planted member; under an implementation shift only the retained alternative counts; on a null pair every claim is false.

| method | runs (with claims) | claims (correct) | precision | false: shift / null / structural decoy | claims on null pairs | core recall | Brier | reliability (bin: confidence -> observed, n) |
|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 81 (12) | 18 (18) | 1.00 | 0 / 0 / 0 | 0 | 0.17 | 0.00 | 0.96->1.00 (18) |
