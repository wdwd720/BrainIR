# Synthetic tournament — sel_curve_part1_b250

suite `mechanisms_v1_heldout`; 432 runs; budget 250 calls; seeds [0]; networks ['main', 'order1']; wall 486.2 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| greedy_plus | 108 | 1.00 [1.00, 1.00] | 0.91 [0.85, 0.96] | 1.00 | 1.00 | 1.00 | 0.99 | – | 74.00 | 2.00 | 0.98 | 0.00 |
| greedy_reference | 108 | 0.63 [0.54, 0.71] | 0.10 [0.05, 0.17] | 0.65 | 1.00 | 0.33 | 0.65 | – | 244.00 | 3.00 | – | 0.21 |
| group_probe | 108 | 1.00 [1.00, 1.00] | 0.88 [0.81, 0.94] | 1.00 | 1.00 | 1.00 | 1.00 | – | 90.00 | 2.00 | 0.87 | 0.00 |
| surrogate_search | 108 | 1.00 [1.00, 1.00] | 0.87 [0.81, 0.93] | 1.00 | 1.00 | 1.00 | 0.99 | – | 71.00 | 2.00 | 0.93 | 0.01 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success = the core is sufficient on fresh seeds and 1-minimal (no member removable).

## By family (success rate / median calls)

| family | greedy_plus | greedy_reference | group_probe | surrogate_search |
|---|---|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 92 (n=14) | 0.00 / 70 (n=14) | 1.00 / 94 (n=14) | 1.00 / 100 (n=14) |
| ei_pair_oscillator | 1.00 / 60 (n=14) | 0.86 / 250 (n=14) | 1.00 / 88 (n=14) | 1.00 / 62 (n=14) |
| feedforward_driver | 1.00 / 97 (n=8) | 0.50 / 148 (n=8) | 1.00 / 78 (n=8) | 1.00 / 78 (n=8) |
| integrator | 1.00 / 34 (n=4) | 1.00 / 66 (n=4) | 1.00 / 44 (n=4) | 1.00 / 45 (n=4) |
| memory_switch | 1.00 / 33 (n=14) | 1.00 / 152 (n=14) | 1.00 / 56 (n=14) | 1.00 / 57 (n=14) |
| negative_feedback_controller | 1.00 / 66 (n=8) | 0.75 / 250 (n=8) | 1.00 / 85 (n=8) | 1.00 / 72 (n=8) |
| redundant_oscillator | 1.00 / 123 (n=14) | 0.71 / 250 (n=14) | 1.00 / 104 (n=14) | 1.00 / 71 (n=14) |
| ring_oscillator | 1.00 / 77 (n=8) | 0.50 / 248 (n=8) | 1.00 / 101 (n=8) | 1.00 / 100 (n=8) |
| two_implementations | 1.00 / 138 (n=14) | 0.43 / 250 (n=14) | 1.00 / 127 (n=14) | 1.00 / 90 (n=14) |
| winner_take_all | 1.00 / 58 (n=10) | 0.80 / 206 (n=10) | 1.00 / 67 (n=10) | 1.00 / 64 (n=10) |
