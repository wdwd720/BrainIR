# Synthetic tournament — sel_mech_b1000_part3

suite `mechanisms_v1_heldout`; 342 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 332.6 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cem_search | 342 | 1.00 [1.00, 1.00] | 0.91 [0.88, 0.94] | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | 0.92 | 86.00 | 2.00 | 0.94 | 0.01 | 0.91 / 0.81 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | cem_search |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 90 (n=42) |
| ei_pair_oscillator | 1.00 / 71 (n=48) |
| feedforward_driver | 1.00 / 148 (n=24) |
| integrator | 1.00 / 38 (n=12) |
| memory_switch | 1.00 / 36 (n=42) |
| negative_feedback_controller | 1.00 / 80 (n=24) |
| redundant_oscillator | 1.00 / 110 (n=42) |
| ring_oscillator | 1.00 / 118 (n=30) |
| two_implementations | 1.00 / 130 (n=48) |
| winner_take_all | 1.00 / 62 (n=30) |
