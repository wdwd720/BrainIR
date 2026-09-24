# Synthetic tournament — ag_candidates_baseline

suite `mechanisms_v1_heldout`; 235 runs; budget 1000 calls; seeds [0]; networks ['main']; wall 108.5 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cem_search | 47 | 1.00 [1.00, 1.00] | 0.89 [0.81, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | – | 75.00 | 2.00 | 0.91 | 0.01 | – / – |
| greedy_plus | 47 | 1.00 [1.00, 1.00] | 0.89 [0.79, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | – | 64.00 | 2.00 | 1.00 | 0.00 | – / – |
| greedy_reference | 47 | 0.79 [0.68, 0.89] | 0.21 [0.11, 0.34] | 0.22 | 0.81 | 1.00 | 0.50 | 0.82 | – | 206.00 | 3.00 | – | 0.23 | – / – |
| group_probe | 47 | 1.00 [1.00, 1.00] | 0.85 [0.74, 0.94] | 0.96 | 1.00 | 1.00 | 1.00 | 1.00 | – | 88.00 | 2.00 | 0.84 | 0.00 | – / – |
| surrogate_search | 47 | 1.00 [1.00, 1.00] | 0.89 [0.81, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | – | 77.00 | 2.00 | 0.93 | 0.01 | – / – |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | cem_search | greedy_plus | greedy_reference | group_probe | surrogate_search |
|---|---|---|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 84 (n=6) | 1.00 / 94 (n=6) | 0.00 / 50 (n=6) | 1.00 / 94 (n=6) | 1.00 / 106 (n=6) |
| ei_pair_oscillator | 1.00 / 62 (n=6) | 1.00 / 58 (n=6) | 1.00 / 254 (n=6) | 1.00 / 87 (n=6) | 1.00 / 74 (n=6) |
| feedforward_driver | 1.00 / 55 (n=3) | 1.00 / 54 (n=3) | 0.33 / 46 (n=3) | 1.00 / 74 (n=3) | 1.00 / 86 (n=3) |
| integrator | 1.00 / 42 (n=2) | 1.00 / 34 (n=2) | 1.00 / 66 (n=2) | 1.00 / 44 (n=2) | 1.00 / 42 (n=2) |
| memory_switch | 1.00 / 37 (n=6) | 1.00 / 33 (n=6) | 1.00 / 129 (n=6) | 1.00 / 50 (n=6) | 1.00 / 58 (n=6) |
| negative_feedback_controller | 1.00 / 80 (n=4) | 1.00 / 74 (n=4) | 0.75 / 303 (n=4) | 1.00 / 86 (n=4) | 1.00 / 84 (n=4) |
| redundant_oscillator | 1.00 / 108 (n=6) | 1.00 / 115 (n=6) | 1.00 / 256 (n=6) | 1.00 / 97 (n=6) | 1.00 / 76 (n=6) |
| ring_oscillator | 1.00 / 81 (n=3) | 1.00 / 78 (n=3) | 1.00 / 246 (n=3) | 1.00 / 92 (n=3) | 1.00 / 106 (n=3) |
| two_implementations | 1.00 / 128 (n=6) | 1.00 / 170 (n=6) | 1.00 / 258 (n=6) | 1.00 / 125 (n=6) | 1.00 / 106 (n=6) |
| winner_take_all | 1.00 / 61 (n=5) | 1.00 / 61 (n=5) | 0.80 / 206 (n=5) | 1.00 / 67 (n=5) | 1.00 / 68 (n=5) |
