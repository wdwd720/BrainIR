# Synthetic tournament — abl_v1_no_active_selection

suite `mechanisms_v1_heldout`; 108 runs; budget 1000 calls; seeds [0]; networks ['main', 'order1']; wall 77.4 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 108 | 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 | 87.50 | 2.00 | 0.91 | 0.00 | 0.94 / 0.94 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 110 (n=14) |
| ei_pair_oscillator | 1.00 / 64 (n=14) |
| feedforward_driver | 1.00 / 108 (n=8) |
| integrator | 1.00 / 44 (n=4) |
| memory_switch | 1.00 / 46 (n=14) |
| negative_feedback_controller | 1.00 / 82 (n=8) |
| redundant_oscillator | 1.00 / 120 (n=14) |
| ring_oscillator | 1.00 / 97 (n=8) |
| two_implementations | 1.00 / 183 (n=14) |
| winner_take_all | 1.00 / 66 (n=10) |
