# Pair tournament — sel_pairs_b1000

1248 jobs; budgets a 1000 / b 1000; seeds [0, 1]; wall 758.9 s on modal

| method/mode | n | success a | success b | both [CI] | corr P/R | role align | role-graph sim | calls a/b/adapt/total |
|---|---|---|---|---|---|---|---|---|
| cem_search/independent | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 0.96/0.87 | 0.90 | 0.92 | 89.27/94.69/0.00/183.96 |
| cem_search/joint | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00/0.93 | 0.96 | 1.00 | 72.87/26.48/15.88/115.23 |
| cem_search/prior | 52 | 1.00 | 0.98 | 0.98 [0.94, 1.00] | 0.95/0.86 | 0.90 | 0.92 | 89.27/84.42/0.00/173.69 |
| cem_search/transfer | 52 | 1.00 | 0.73 | 0.73 [0.62, 0.85] | 0.87/0.78 | 0.77 | 0.78 | 89.27/2.00/14.46/105.73 |
| evo_pareto/independent | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00/0.89 | 0.92 | 0.92 | 759.81/758.65/0.00/1518.46 |
| evo_pareto/joint | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00/0.93 | 0.98 | 1.00 | 615.10/217.19/15.73/848.02 |
| evo_pareto/prior | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 0.98/0.88 | 0.90 | 0.92 | 757.48/727.69/0.00/1485.17 |
| evo_pareto/transfer | 52 | 1.00 | 0.71 | 0.71 [0.60, 0.83] | 0.87/0.78 | 0.79 | 0.76 | 752.46/2.00/14.85/769.31 |
| greedy_plus/independent | 52 | 0.98 | 1.00 | 0.98 [0.94, 1.00] | 0.98/0.92 | 0.94 | 0.96 | 85.87/88.48/0.00/174.35 |
| greedy_plus/joint | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00/0.94 | 0.98 | 1.00 | 64.90/23.98/15.50/104.38 |
| greedy_plus/prior | 52 | 0.98 | 1.00 | 0.98 [0.94, 1.00] | 0.98/0.92 | 0.94 | 0.96 | 85.87/70.77/0.00/156.63 |
| greedy_plus/transfer | 52 | 0.98 | 0.71 | 0.69 [0.56, 0.81] | 0.85/0.77 | 0.77 | 0.76 | 85.87/2.00/14.81/102.67 |
| greedy_reference/independent | 52 | 0.77 | 0.75 | 0.71 [0.58, 0.83] | 0.81/0.74 | 0.75 | 0.75 | 275.21/294.27/0.00/569.48 |
| greedy_reference/joint | 52 | 0.96 | 1.00 | 0.96 [0.90, 1.00] | 0.96/0.88 | 0.90 | 0.96 | 248.40/102.67/37.08/388.15 |
| greedy_reference/prior | 52 | 0.77 | 0.75 | 0.71 [0.60, 0.83] | 0.81/0.74 | 0.75 | 0.76 | 275.37/294.27/0.00/569.63 |
| greedy_reference/transfer | 52 | 0.77 | 0.67 | 0.60 [0.46, 0.73] | 0.62/0.68 | 0.64 | 0.62 | 275.25/2.00/95.31/372.56 |
| group_probe/independent | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 0.96/0.87 | 0.90 | 0.92 | 126.27/119.54/0.00/245.81 |
| group_probe/joint | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00/0.93 | 0.96 | 1.00 | 90.85/36.27/15.58/142.69 |
| group_probe/prior | 52 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 1.00/0.93 | 0.94 | 0.96 | 126.27/111.04/0.00/237.31 |
| group_probe/transfer | 52 | 1.00 | 0.69 | 0.69 [0.56, 0.81] | 0.87/0.78 | 0.77 | 0.74 | 126.27/2.00/15.08/143.35 |
| surrogate_search/independent | 52 | 1.00 | 0.98 | 0.98 [0.94, 1.00] | 1.00/0.87 | 0.92 | 0.88 | 96.02/97.60/0.00/193.62 |
| surrogate_search/joint | 52 | 1.00 | 0.98 | 0.98 [0.94, 1.00] | 1.00/0.93 | 1.00 | 1.00 | 79.92/31.87/15.35/127.13 |
| surrogate_search/prior | 52 | 1.00 | 0.98 | 0.98 [0.94, 1.00] | 1.00/0.87 | 0.92 | 0.88 | 96.00/96.33/0.00/192.33 |
| surrogate_search/transfer | 52 | 1.00 | 0.69 | 0.69 [0.56, 0.81] | 0.87/0.79 | 0.81 | 0.74 | 96.02/2.00/15.23/113.25 |

by family (both-success rate):

- cem_search/independent: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- cem_search/joint: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- cem_search/prior: delayed_inhibitory_oscillator 0.83, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.93
- cem_search/transfer: delayed_inhibitory_oscillator 0.67, ei_pair_oscillator 0.50, feedforward_driver 0.67, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 0.50, two_implementations 0.50, winner_take_all 1.00; shift 0.50; decoy 0.71
- evo_pareto/independent: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- evo_pareto/joint: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- evo_pareto/prior: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- evo_pareto/transfer: delayed_inhibitory_oscillator 0.67, ei_pair_oscillator 0.50, feedforward_driver 0.67, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 0.75, ring_oscillator 0.50, two_implementations 0.50, winner_take_all 1.00; shift 0.25; decoy 0.71
- greedy_plus/independent: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 0.83, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.93
- greedy_plus/joint: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- greedy_plus/prior: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 0.83, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.93
- greedy_plus/transfer: delayed_inhibitory_oscillator 0.67, ei_pair_oscillator 0.50, feedforward_driver 0.67, integrator 1.00, memory_switch 0.83, negative_feedback_controller 1.00, redundant_oscillator 0.75, ring_oscillator 0.50, two_implementations 0.50, winner_take_all 1.00; shift 0.25; decoy 0.64
- greedy_reference/independent: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 1.00, feedforward_driver 0.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 0.75, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 0.00; shift 1.00; decoy 0.71
- greedy_reference/joint: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 0.67, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.86
- greedy_reference/prior: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 1.00, feedforward_driver 0.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 0.75, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 0.00; shift 1.00; decoy 0.71
- greedy_reference/transfer: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 0.75, feedforward_driver 0.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 0.50, ring_oscillator 0.50, two_implementations 0.75, winner_take_all 1.00; shift 0.25; decoy 0.43
- group_probe/independent: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- group_probe/joint: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- group_probe/prior: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00
- group_probe/transfer: delayed_inhibitory_oscillator 0.67, ei_pair_oscillator 0.50, feedforward_driver 0.67, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 0.50, ring_oscillator 0.50, two_implementations 0.50, winner_take_all 1.00; shift 0.00; decoy 0.71
- surrogate_search/independent: delayed_inhibitory_oscillator 0.83, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.93
- surrogate_search/joint: delayed_inhibitory_oscillator 0.83, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.93
- surrogate_search/prior: delayed_inhibitory_oscillator 0.83, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.93
- surrogate_search/transfer: delayed_inhibitory_oscillator 0.67, ei_pair_oscillator 0.50, feedforward_driver 0.67, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 0.50, ring_oscillator 0.50, two_implementations 0.50, winner_take_all 1.00; shift 0.00; decoy 0.71
