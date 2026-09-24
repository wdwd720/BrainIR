# Synthetic tournament — ag_candidates_add_sink_distractors

suite `add_sink_distractors`; 235 runs; budget 1000 calls; seeds [0]; networks ['main']; wall 148.7 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cem_search | 47 | 1.00 [1.00, 1.00] | 0.89 [0.81, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | – | 75.00 | 2.00 | 0.93 | 0.00 | – / – |
| greedy_plus | 47 | 1.00 [1.00, 1.00] | 0.89 [0.79, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | – | 64.00 | 2.00 | 0.93 | 0.00 | – / – |
| greedy_reference | 47 | 0.81 [0.70, 0.91] | 0.19 [0.09, 0.30] | 0.20 | 0.83 | 1.00 | 0.33 | 0.82 | – | 236.00 | 3.00 | – | 0.20 | – / – |
| group_probe | 47 | 1.00 [1.00, 1.00] | 0.87 [0.77, 0.96] | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | – | 93.00 | 2.00 | 0.98 | 0.00 | – / – |
| surrogate_search | 47 | 1.00 [1.00, 1.00] | 0.89 [0.81, 0.98] | 1.00 | 1.00 | 1.00 | 1.00 | 0.98 | – | 85.00 | 2.00 | 0.93 | 0.00 | – / – |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | cem_search | greedy_plus | greedy_reference | group_probe | surrogate_search |
|---|---|---|---|---|---|
| delayed_inhibitory_oscillator | 1.00 / 84 (n=6) | 1.00 / 93 (n=6) | 0.00 / 70 (n=6) | 1.00 / 122 (n=6) | 1.00 / 142 (n=6) |
| ei_pair_oscillator | 1.00 / 62 (n=6) | 1.00 / 60 (n=6) | 1.00 / 254 (n=6) | 1.00 / 91 (n=6) | 1.00 / 78 (n=6) |
| feedforward_driver | 1.00 / 55 (n=3) | 1.00 / 54 (n=3) | 0.33 / 72 (n=3) | 1.00 / 102 (n=3) | 1.00 / 102 (n=3) |
| integrator | 1.00 / 42 (n=2) | 1.00 / 34 (n=2) | 1.00 / 212 (n=2) | 1.00 / 57 (n=2) | 1.00 / 60 (n=2) |
| memory_switch | 1.00 / 37 (n=6) | 1.00 / 33 (n=6) | 1.00 / 178 (n=6) | 1.00 / 60 (n=6) | 1.00 / 66 (n=6) |
| negative_feedback_controller | 1.00 / 80 (n=4) | 1.00 / 77 (n=4) | 0.75 / 299 (n=4) | 1.00 / 90 (n=4) | 1.00 / 80 (n=4) |
| redundant_oscillator | 1.00 / 108 (n=6) | 1.00 / 117 (n=6) | 1.00 / 318 (n=6) | 1.00 / 98 (n=6) | 1.00 / 85 (n=6) |
| ring_oscillator | 1.00 / 81 (n=3) | 1.00 / 78 (n=3) | 1.00 / 246 (n=3) | 1.00 / 104 (n=3) | 1.00 / 110 (n=3) |
| two_implementations | 1.00 / 128 (n=6) | 1.00 / 175 (n=6) | 1.00 / 285 (n=6) | 1.00 / 130 (n=6) | 1.00 / 101 (n=6) |
| winner_take_all | 1.00 / 61 (n=5) | 1.00 / 61 (n=5) | 1.00 / 233 (n=5) | 1.00 / 71 (n=5) | 1.00 / 73 (n=5) |
