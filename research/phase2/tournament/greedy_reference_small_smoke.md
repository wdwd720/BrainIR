# Synthetic tournament — greedy_reference_small_smoke

suite `mechanisms_v1`; 96 runs; budget 1000 calls; seeds [0]; networks ['main', 'order1']; wall 185.7 s on local

| method | runs | success rate [95% CI] | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier |
|---|---|---|---|---|---|---|---|---|---|---|
| greedy_reference | 96 | 0.71 [0.61, 0.80] | 1.00 | 0.67 | 0.82 | – | 206.00 | 3.00 | – | 0.23 |

## By family (success rate / median calls)

| family | greedy_reference |
|---|---|
| delayed_inhibitory_oscillator | 0.00 / 62 (n=12) |
| ei_pair_oscillator | 1.00 / 225 (n=12) |
| feedforward_driver | 0.00 / 66 (n=6) |
| integrator | 1.00 / 106 (n=6) |
| memory_switch | 1.00 / 266 (n=12) |
| negative_feedback_controller | 1.00 / 192 (n=8) |
| redundant_oscillator | 1.00 / 240 (n=12) |
| ring_oscillator | 1.00 / 108 (n=6) |
| two_implementations | 1.00 / 270 (n=12) |
| winner_take_all | 0.00 / 206 (n=10) |
