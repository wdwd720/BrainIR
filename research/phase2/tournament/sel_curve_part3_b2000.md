# Synthetic tournament — sel_curve_part3_b2000

suite `mechanisms_v1_heldout`; 108 runs; budget 2000 calls; seeds [0]; networks ['main', 'order1']; wall 74.1 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cem_search | 108 | 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | – | 86.00 | 2.00 | 0.93 | 0.01 | 0.86 / 0.85 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | cem_search |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 98 (n=14) |
| ei_pair_oscillator | 1.00 / 72 (n=14) |
| feedforward_driver | 1.00 / 149 (n=8) |
| integrator | 1.00 / 42 (n=4) |
| memory_switch | 1.00 / 40 (n=14) |
| negative_feedback_controller | 1.00 / 78 (n=8) |
| redundant_oscillator | 1.00 / 109 (n=14) |
| ring_oscillator | 1.00 / 104 (n=8) |
| two_implementations | 1.00 / 141 (n=14) |
| winner_take_all | 1.00 / 64 (n=10) |
