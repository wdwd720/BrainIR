# Synthetic tournament — sel_curve_part2_b500

suite `mechanisms_v1_heldout`; 108 runs; budget 500 calls; seeds [0]; networks ['main', 'order1']; wall 481.5 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| evo_pareto | 108 | 1.00 [1.00, 1.00] | 0.87 [0.81, 0.93] | 0.97 | 1.00 | 1.00 | 1.00 | 0.99 | – | 359.50 | 2.00 | 0.93 | 0.01 | 0.89 / 0.87 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | evo_pareto |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 436 (n=14) |
| ei_pair_oscillator | 1.00 / 288 (n=14) |
| feedforward_driver | 1.00 / 326 (n=8) |
| integrator | 1.00 / 204 (n=4) |
| memory_switch | 1.00 / 220 (n=14) |
| negative_feedback_controller | 1.00 / 306 (n=8) |
| redundant_oscillator | 1.00 / 428 (n=14) |
| ring_oscillator | 1.00 / 321 (n=8) |
| two_implementations | 1.00 / 428 (n=14) |
| winner_take_all | 1.00 / 282 (n=10) |
