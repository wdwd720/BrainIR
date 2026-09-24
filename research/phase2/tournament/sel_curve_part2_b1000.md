# Synthetic tournament — sel_curve_part2_b1000

suite `mechanisms_v1_heldout`; 108 runs; budget 1000 calls; seeds [0]; networks ['main', 'order1']; wall 336.0 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| evo_pareto | 108 | 1.00 [1.00, 1.00] | 0.88 [0.81, 0.94] | 0.97 | 1.00 | 1.00 | 1.00 | 0.99 | – | 800.00 | 2.00 | 0.95 | 0.00 | 0.87 / 0.85 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | evo_pareto |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 907 (n=14) |
| ei_pair_oscillator | 1.00 / 741 (n=14) |
| feedforward_driver | 1.00 / 702 (n=8) |
| integrator | 1.00 / 524 (n=4) |
| memory_switch | 1.00 / 502 (n=14) |
| negative_feedback_controller | 1.00 / 710 (n=8) |
| redundant_oscillator | 1.00 / 910 (n=14) |
| ring_oscillator | 1.00 / 698 (n=8) |
| two_implementations | 1.00 / 912 (n=14) |
| winner_take_all | 1.00 / 688 (n=10) |
