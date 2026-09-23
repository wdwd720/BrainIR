# Synthetic tournament — sel_curve_part1_b1000

suite `mechanisms_v1_heldout`; 432 runs; budget 1000 calls; seeds [0]; networks ['main', 'order1']; wall 385.5 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| greedy_plus | 108 | 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] | 1.00 | 1.00 | 1.00 | 0.99 | – | 76.00 | 2.00 | 0.98 | 0.00 |
| greedy_reference | 108 | 0.78 [0.70, 0.85] | 0.20 [0.13, 0.29] | 0.80 | 1.00 | 0.50 | 0.81 | – | 244.00 | 3.00 | – | 0.21 |
| group_probe | 108 | 1.00 [1.00, 1.00] | 0.88 [0.81, 0.94] | 1.00 | 1.00 | 1.00 | 1.00 | – | 91.50 | 2.00 | 0.87 | 0.00 |
| surrogate_search | 108 | 1.00 [1.00, 1.00] | 0.92 [0.86, 0.96] | 1.00 | 1.00 | 1.00 | 0.99 | – | 78.50 | 2.00 | 0.93 | 0.01 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success = the core is sufficient on fresh seeds and 1-minimal (no member removable).

## By family (success rate / median calls)

| family | greedy_plus | greedy_reference | group_probe | surrogate_search |
|---|---|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 94 (n=14) | 0.00 / 70 (n=14) | 1.00 / 94 (n=14) | 1.00 / 122 (n=14) |
| ei_pair_oscillator | 1.00 / 60 (n=14) | 1.00 / 264 (n=14) | 1.00 / 88 (n=14) | 1.00 / 73 (n=14) |
| feedforward_driver | 1.00 / 108 (n=8) | 0.50 / 273 (n=8) | 1.00 / 106 (n=8) | 1.00 / 96 (n=8) |
| integrator | 1.00 / 34 (n=4) | 1.00 / 66 (n=4) | 1.00 / 44 (n=4) | 1.00 / 45 (n=4) |
| memory_switch | 1.00 / 33 (n=14) | 1.00 / 152 (n=14) | 1.00 / 56 (n=14) | 1.00 / 59 (n=14) |
| negative_feedback_controller | 1.00 / 66 (n=8) | 0.75 / 303 (n=8) | 1.00 / 85 (n=8) | 1.00 / 79 (n=8) |
| redundant_oscillator | 1.00 / 123 (n=14) | 0.86 / 268 (n=14) | 1.00 / 104 (n=14) | 1.00 / 78 (n=14) |
| ring_oscillator | 1.00 / 94 (n=8) | 1.00 / 312 (n=8) | 1.00 / 127 (n=8) | 1.00 / 110 (n=8) |
| two_implementations | 1.00 / 171 (n=14) | 1.00 / 324 (n=14) | 1.00 / 127 (n=14) | 1.00 / 98 (n=14) |
| winner_take_all | 1.00 / 58 (n=10) | 0.80 / 206 (n=10) | 1.00 / 67 (n=10) | 1.00 / 68 (n=10) |
