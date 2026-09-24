# Synthetic tournament — abl_v1_no_member_essentiality

suite `mechanisms_v1_heldout`; 108 runs; budget 1000 calls; seeds [0]; networks ['main', 'order1']; wall 41.2 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 108 | 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 | 68.00 | 2.00 | 0.91 | 0.00 | 0.94 / 0.94 |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 76 (n=14) |
| ei_pair_oscillator | 1.00 / 50 (n=14) |
| feedforward_driver | 1.00 / 106 (n=8) |
| integrator | 1.00 / 37 (n=4) |
| memory_switch | 1.00 / 32 (n=14) |
| negative_feedback_controller | 1.00 / 60 (n=8) |
| redundant_oscillator | 1.00 / 72 (n=14) |
| ring_oscillator | 1.00 / 66 (n=8) |
| two_implementations | 1.00 / 92 (n=14) |
| winner_take_all | 1.00 / 58 (n=10) |
