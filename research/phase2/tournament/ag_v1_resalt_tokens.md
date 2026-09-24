# Synthetic tournament — ag_v1_resalt_tokens

suite `resalt_tokens`; 47 runs; budget 1000 calls; seeds [0]; networks ['main']; wall 120.6 s on modal-pinned

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| brainir_v1 | 47 | 1.00 [1.00, 1.00] | 0.89 [0.81, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | – | 77.00 | 2.00 | 0.91 | 0.00 | – / – |

runs = attempted runs; failed runs (errors, timeouts, budget-integrity or seed-namespace violations) count as unsuccessful.
structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | brainir_v1 |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 107 (n=6) |
| ei_pair_oscillator | 1.00 / 58 (n=6) |
| feedforward_driver | 1.00 / 66 (n=3) |
| integrator | 1.00 / 43 (n=2) |
| memory_switch | 1.00 / 38 (n=6) |
| negative_feedback_controller | 1.00 / 78 (n=4) |
| redundant_oscillator | 1.00 / 112 (n=6) |
| ring_oscillator | 1.00 / 77 (n=3) |
| two_implementations | 1.00 / 166 (n=6) |
| winner_take_all | 1.00 / 64 (n=5) |
