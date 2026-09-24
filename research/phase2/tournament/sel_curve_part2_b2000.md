# Synthetic tournament — sel_curve_part2_b2000

suite `mechanisms_v1_heldout`; 108 runs; budget 2000 calls; seeds [0]; networks ['main', 'order1']; wall 580.7 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| evo_pareto | 108 | 1.00 [1.00, 1.00] | 0.89 [0.82, 0.94] | 0.98 | 1.00 | 1.00 | 1.00 | 0.99 | – | 793.00 | 2.00 | 0.94 | 0.00 | 0.90 / 0.87 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | evo_pareto |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 976 (n=14) |
| ei_pair_oscillator | 1.00 / 722 (n=14) |
| feedforward_driver | 1.00 / 1038 (n=8) |
| integrator | 1.00 / 524 (n=4) |
| memory_switch | 1.00 / 502 (n=14) |
| negative_feedback_controller | 1.00 / 710 (n=8) |
| redundant_oscillator | 1.00 / 1182 (n=14) |
| ring_oscillator | 1.00 / 658 (n=8) |
| two_implementations | 1.00 / 1136 (n=14) |
| winner_take_all | 1.00 / 688 (n=10) |
