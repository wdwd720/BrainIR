# Synthetic tournament — sel_mech_b1000_part1

suite `mechanisms_v1_heldout`; 1368 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 1204.8 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| greedy_plus | 342 | 1.00 [1.00, 1.00] | 0.91 [0.88, 0.94] | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | 0.93 | 88.00 | 2.00 | 0.95 | 0.00 | 0.88 / 0.75 |
| greedy_reference | 342 | 0.74 [0.70, 0.79] | 0.20 [0.15, 0.24] | 0.21 | 0.76 | 1.00 | 0.33 | 0.77 | 0.71 | 246.00 | 3.00 | – | 0.21 | 0.83 / 0.63 |
| group_probe | 342 | 1.00 [1.00, 1.00] | 0.88 [0.85, 0.92] | 0.95 | 1.00 | 1.00 | 1.00 | 1.00 | 0.92 | 92.00 | 2.00 | 0.88 | 0.00 | 0.95 / 0.86 |
| surrogate_search | 342 | 1.00 [1.00, 1.00] | 0.91 [0.88, 0.94] | 0.99 | 1.00 | 1.00 | 1.00 | 0.99 | 0.92 | 82.00 | 2.00 | 0.92 | 0.01 | 0.85 / 0.63 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | greedy_plus | greedy_reference | group_probe | surrogate_search |
|---|---|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 94 (n=42) | 0.00 / 70 (n=42) | 1.00 / 94 (n=42) | 1.00 / 117 (n=42) |
| ei_pair_oscillator | 1.00 / 61 (n=48) | 0.88 / 320 (n=48) | 1.00 / 88 (n=48) | 1.00 / 73 (n=48) |
| feedforward_driver | 1.00 / 102 (n=24) | 0.50 / 273 (n=24) | 1.00 / 106 (n=24) | 1.00 / 88 (n=24) |
| integrator | 1.00 / 36 (n=12) | 1.00 / 66 (n=12) | 1.00 / 44 (n=12) | 1.00 / 45 (n=12) |
| memory_switch | 1.00 / 33 (n=42) | 1.00 / 152 (n=42) | 1.00 / 56 (n=42) | 1.00 / 66 (n=42) |
| negative_feedback_controller | 1.00 / 68 (n=24) | 0.75 / 303 (n=24) | 1.00 / 85 (n=24) | 1.00 / 76 (n=24) |
| redundant_oscillator | 1.00 / 124 (n=42) | 0.90 / 268 (n=42) | 1.00 / 104 (n=42) | 1.00 / 79 (n=42) |
| ring_oscillator | 1.00 / 111 (n=30) | 0.80 / 378 (n=30) | 1.00 / 162 (n=30) | 1.00 / 116 (n=30) |
| two_implementations | 1.00 / 185 (n=48) | 0.88 / 378 (n=48) | 1.00 / 128 (n=48) | 1.00 / 101 (n=48) |
| winner_take_all | 1.00 / 57 (n=30) | 0.80 / 206 (n=30) | 1.00 / 67 (n=30) | 1.00 / 68 (n=30) |
