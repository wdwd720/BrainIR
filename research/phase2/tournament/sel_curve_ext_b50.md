# Synthetic tournament — sel_curve_ext_b50

suite `mechanisms_v1_heldout`; 648 runs; budget 50 calls; seeds [0]; networks ['main', 'order1']; wall 237.9 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cem_search | 108 | 0.99 [0.97, 1.00] | 0.64 [0.55, 0.73] | 0.77 | 0.99 | 1.00 | 1.00 | 1.00 | – | 49.00 | 2.00 | 0.92 | 0.03 | 0.75 / 0.65 |
| evo_pareto | 108 | 1.00 [1.00, 1.00] | 0.16 [0.09, 0.22] | 0.16 | 1.00 | 1.00 | 0.67 | 1.00 | – | 47.00 | 3.00 | 0.84 | 0.08 | 0.83 / 0.63 |
| greedy_plus | 108 | 1.00 [1.00, 1.00] | 0.82 [0.74, 0.89] | 0.96 | 1.00 | 1.00 | 1.00 | 0.99 | – | 44.00 | 2.00 | 0.93 | 0.01 | 0.73 / 0.69 |
| greedy_reference | 108 | 0.52 [0.43, 0.61] | 0.00 [0.00, 0.00] | 0.00 | 0.52 | 1.00 | 0.33 | 0.48 | – | 50.00 | 3.00 | – | 0.19 | 0.84 / 0.72 |
| group_probe | 108 | 1.00 [1.00, 1.00] | 0.88 [0.81, 0.94] | 0.95 | 1.00 | 1.00 | 1.00 | 1.00 | – | 48.00 | 2.00 | 0.88 | 0.00 | 0.92 / 0.91 |
| surrogate_search | 108 | 0.98 [0.95, 1.00] | 0.27 [0.19, 0.35] | 0.32 | 0.98 | 1.00 | 0.33 | 0.99 | – | 50.00 | 7.50 | 0.93 | 0.06 | 0.49 / 0.17 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | cem_search | evo_pareto | greedy_plus | greedy_reference | group_probe | surrogate_search |
|---|---|---|---|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 49 (n=14) | 1.00 / 50 (n=14) | 1.00 / 50 (n=14) | 0.00 / 50 (n=14) | 1.00 / 49 (n=14) | 1.00 / 50 (n=14) |
| ei_pair_oscillator | 1.00 / 46 (n=14) | 1.00 / 45 (n=14) | 1.00 / 42 (n=14) | 0.79 / 50 (n=14) | 1.00 / 48 (n=14) | 1.00 / 50 (n=14) |
| feedforward_driver | 1.00 / 46 (n=8) | 1.00 / 45 (n=8) | 1.00 / 40 (n=8) | 0.50 / 48 (n=8) | 1.00 / 42 (n=8) | 1.00 / 50 (n=8) |
| integrator | 1.00 / 26 (n=4) | 1.00 / 46 (n=4) | 1.00 / 29 (n=4) | 1.00 / 38 (n=4) | 1.00 / 40 (n=4) | 1.00 / 42 (n=4) |
| memory_switch | 1.00 / 28 (n=14) | 1.00 / 46 (n=14) | 1.00 / 29 (n=14) | 1.00 / 50 (n=14) | 1.00 / 44 (n=14) | 1.00 / 49 (n=14) |
| negative_feedback_controller | 0.88 / 46 (n=8) | 1.00 / 45 (n=8) | 1.00 / 42 (n=8) | 0.50 / 50 (n=8) | 1.00 / 48 (n=8) | 0.75 / 50 (n=8) |
| redundant_oscillator | 1.00 / 49 (n=14) | 1.00 / 47 (n=14) | 1.00 / 43 (n=14) | 0.64 / 50 (n=14) | 1.00 / 47 (n=14) | 1.00 / 50 (n=14) |
| ring_oscillator | 1.00 / 49 (n=8) | 1.00 / 48 (n=8) | 1.00 / 50 (n=8) | 0.00 / 50 (n=8) | 1.00 / 50 (n=8) | 1.00 / 50 (n=8) |
| two_implementations | 1.00 / 49 (n=14) | 1.00 / 49 (n=14) | 1.00 / 50 (n=14) | 0.00 / 50 (n=14) | 1.00 / 48 (n=14) | 1.00 / 50 (n=14) |
| winner_take_all | 1.00 / 40 (n=10) | 1.00 / 45 (n=10) | 1.00 / 44 (n=10) | 1.00 / 50 (n=10) | 1.00 / 47 (n=10) | 1.00 / 50 (n=10) |
