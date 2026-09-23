# Synthetic tournament — sel_mech_b1000_part2

suite `mechanisms_v1_heldout`; 342 runs; budget 1000 calls; seeds [0, 1, 2]; networks ['main', 'order1']; wall 759.6 s on modal

| method | runs | structural success [95% CI] | functional success [95% CI] | causal functional | either | recall (best alt, median) | precision (median) | functional nominal | functional robust | calls median | size median | role acc | Brier | identity Jaccard / identical |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| evo_pareto | 342 | 1.00 [1.00, 1.00] | 0.87 [0.83, 0.90] | 0.96 | 1.00 | 1.00 | 1.00 | 0.99 | 0.92 | 823.50 | 2.00 | 0.93 | 0.01 | 0.86 / 0.68 |

structural success = the core contains a sufficient set listed in the truth (planted, or unplanted but found by the suite audit); functional success (pre-registered) = the core is sufficient on fresh seeds and 1-minimal under keep-only; causal functional (clarified) = sufficient and every member is keep-only-necessary or essential when silenced in the intact network.

## By family (success rate / median calls)

| family | evo_pareto |
|---|---|
| delayed_inhibitory_oscillator | 1.00 / 901 (n=42) |
| ei_pair_oscillator | 1.00 / 658 (n=48) |
| feedforward_driver | 1.00 / 712 (n=24) |
| integrator | 1.00 / 529 (n=12) |
| memory_switch | 1.00 / 562 (n=42) |
| negative_feedback_controller | 1.00 / 730 (n=24) |
| redundant_oscillator | 1.00 / 910 (n=42) |
| ring_oscillator | 1.00 / 715 (n=30) |
| two_implementations | 1.00 / 912 (n=48) |
| winner_take_all | 1.00 / 610 (n=30) |
