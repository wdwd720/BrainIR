# Synthetic tournament — abl_v1_random_order

suite `mechanisms_v1_heldout`; 108 runs; budget 1000 calls; seeds [0]; networks ['main', 'order1']; wall 94.8 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 108 | 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | 0.91 | 91.50 | 2.00 | 0.96 | 0.00 | 0.92 / 0.91 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 113 (n=14) |
| ei_pair_oscillator | 1.00 / 73 (n=14) |
| feedforward_driver | 1.00 / 147 (n=8) |
| integrator | 1.00 / 46 (n=4) |
| memory_switch | 1.00 / 50 (n=14) |
| negative_feedback_controller | 1.00 / 90 (n=8) |
| redundant_oscillator | 1.00 / 153 (n=14) |
| ring_oscillator | 1.00 / 102 (n=8) |
| two_implementations | 1.00 / 184 (n=14) |
| winner_take_all | 1.00 / 70 (n=10) |
