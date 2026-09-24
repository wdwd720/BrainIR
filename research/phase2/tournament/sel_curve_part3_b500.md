# Synthetic tournament — sel_curve_part3_b500

suite `mechanisms_v1_heldout`; 108 runs; budget 500 calls; seeds [0]; networks ['main', 'order1']; wall 72.0 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cem_search | 108 | 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | – | 73.00 | 2.00 | 0.93 | 0.01 | 0.87 / 0.87 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | cem_search |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 84 (n=14) |
| ei_pair_oscillator | 1.00 / 58 (n=14) |
| feedforward_driver | 1.00 / 137 (n=8) |
| integrator | 1.00 / 34 (n=4) |
| memory_switch | 1.00 / 34 (n=14) |
| negative_feedback_controller | 1.00 / 68 (n=8) |
| redundant_oscillator | 1.00 / 88 (n=14) |
| ring_oscillator | 1.00 / 82 (n=8) |
| two_implementations | 1.00 / 112 (n=14) |
| winner_take_all | 1.00 / 52 (n=10) |
