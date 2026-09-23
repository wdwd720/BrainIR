# Synthetic tournament — sel_curve_ext_b100

suite `mechanisms_v1_heldout`; 648 runs; budget 100 calls; seeds [0]; networks ['main', 'order1']; wall 235.1 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cem_search | 108 | 1.00 [1.00, 1.00] | 0.88 [0.81, 0.94] | 0.97 | 1.00 | 1.00 | 1.00 | 0.99 | – | 56.00 | 2.00 | 0.92 | 0.01 | 0.80 / 0.80 |
| evo_pareto | 108 | 0.99 [0.97, 1.00] | 0.33 [0.25, 0.42] | 0.45 | 0.99 | 1.00 | 0.76 | 1.00 | – | 95.50 | 3.00 | 0.86 | 0.05 | 0.73 / 0.43 |
| greedy_plus | 108 | 1.00 [1.00, 1.00] | 0.91 [0.84, 0.95] | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | – | 49.00 | 2.00 | 0.93 | 0.00 | 0.80 / 0.80 |
| greedy_reference | 108 | 0.56 [0.47, 0.66] | 0.00 [0.00, 0.00] | 0.00 | 0.56 | 1.00 | 0.33 | 0.56 | – | 100.00 | 3.00 | – | 0.20 | 0.85 / 0.74 |
| group_probe | 108 | 1.00 [1.00, 1.00] | 0.88 [0.81, 0.94] | 0.95 | 1.00 | 1.00 | 1.00 | 1.00 | – | 84.00 | 2.00 | 0.87 | 0.00 | 0.93 / 0.91 |
| surrogate_search | 108 | 1.00 [1.00, 1.00] | 0.74 [0.66, 0.81] | 0.90 | 1.00 | 1.00 | 1.00 | 0.99 | – | 81.50 | 2.00 | 0.94 | 0.01 | 0.76 / 0.70 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | cem_search | evo_pareto | greedy_plus | greedy_reference | group_probe | surrogate_search |
|---|---|---|---|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 65 (n=14) | 1.00 / 100 (n=14) | 1.00 / 58 (n=14) | 0.00 / 70 (n=14) | 1.00 / 94 (n=14) | 1.00 / 89 (n=14) |
| ei_pair_oscillator | 1.00 / 47 (n=14) | 1.00 / 95 (n=14) | 1.00 / 44 (n=14) | 0.86 / 100 (n=14) | 1.00 / 79 (n=14) | 1.00 / 85 (n=14) |
| feedforward_driver | 1.00 / 68 (n=8) | 1.00 / 92 (n=8) | 1.00 / 46 (n=8) | 0.50 / 73 (n=8) | 1.00 / 78 (n=8) | 1.00 / 88 (n=8) |
| integrator | 1.00 / 26 (n=4) | 1.00 / 82 (n=4) | 1.00 / 31 (n=4) | 1.00 / 63 (n=4) | 1.00 / 44 (n=4) | 1.00 / 45 (n=4) |
| memory_switch | 1.00 / 28 (n=14) | 0.93 / 86 (n=14) | 1.00 / 31 (n=14) | 1.00 / 100 (n=14) | 1.00 / 56 (n=14) | 1.00 / 58 (n=14) |
| negative_feedback_controller | 1.00 / 46 (n=8) | 1.00 / 95 (n=8) | 1.00 / 48 (n=8) | 0.75 / 100 (n=8) | 1.00 / 77 (n=8) | 1.00 / 82 (n=8) |
| redundant_oscillator | 1.00 / 68 (n=14) | 1.00 / 95 (n=14) | 1.00 / 50 (n=14) | 0.71 / 100 (n=14) | 1.00 / 92 (n=14) | 1.00 / 86 (n=14) |
| ring_oscillator | 1.00 / 66 (n=8) | 1.00 / 98 (n=8) | 1.00 / 64 (n=8) | 0.00 / 100 (n=8) | 1.00 / 92 (n=8) | 1.00 / 93 (n=8) |
| two_implementations | 1.00 / 80 (n=14) | 1.00 / 99 (n=14) | 1.00 / 55 (n=14) | 0.07 / 100 (n=14) | 1.00 / 100 (n=14) | 1.00 / 99 (n=14) |
| winner_take_all | 1.00 / 40 (n=10) | 1.00 / 96 (n=10) | 1.00 / 49 (n=10) | 1.00 / 100 (n=10) | 1.00 / 65 (n=10) | 1.00 / 69 (n=10) |
