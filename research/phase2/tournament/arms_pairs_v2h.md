# Pair tournament — arms_pairs_v2h

648 jobs; budgets a 1000 / b 1000; seeds [0, 1, 2]; wall 3039.9 s on modal-pinned

Calls per network include that network's adaptation calls. Identity claims are scored on every pair: under an implementation shift a claim across implementations is false, and on a null pair every claim is false. Role graphs are compared with the truth; the similarity of a method's two outputs to each other is self-agreement and is not evidence (review E).

| method/mode | n | success a | success b | both [CI] | calls a/b (adapt) /total | pooled | claims (correct) | false shift/null/sdecoy | Brier | role align | role graph vs truth a/b |
|---|---|---|---|---|---|---|---|---|---|---|---|
| greedy_plus/independent | 81 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 150.21/116.58 (0.00) /266.79 | 0.00 | 0 (0) | 0/0/0 | n/a | 0.71 | 0.93/0.88 |
| greedy_plus/independent_pooled | 81 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 150.21/116.58 (0.00) /266.79 | 1.00 | 0 (0) | 0/0/0 | n/a | 0.00 | 0.93/0.88 |
| greedy_plus/joint | 81 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 151.07/103.36 (16.42) /254.43 | 0.83 | 25 (25) | 0/0/0 | 0.00 | 0.71 | 0.93/0.88 |
| greedy_plus/joint_null | 81 | 1.00 | 1.00 | 1.00 [1.00, 1.00] | 156.53/111.49 (13.51) /268.02 | 0.91 | 6 (5) | 0/1/0 | 0.15 | 0.71 | 0.93/0.88 |
| greedy_reference/independent | 81 | 0.70 | 0.74 | 0.63 [0.53, 0.73] | 310.72/304.59 (0.00) /615.31 | 0.00 | 0 (0) | 0/0/0 | n/a | 0.53 | 0.60/0.61 |
| greedy_reference/independent_pooled | 81 | 0.70 | 0.74 | 0.63 [0.52, 0.73] | 310.72/304.59 (0.00) /615.31 | 1.00 | 0 (0) | 0/0/0 | n/a | 0.00 | 0.00/0.00 |
| greedy_reference/joint | 81 | 0.73 | 0.81 | 0.65 [0.54, 0.77] | 319.36/293.58 (44.27) /612.94 | 0.70 | 22 (22) | 0/0/0 | 0.00 | 0.53 | 0.60/0.63 |
| greedy_reference/joint_null | 81 | 0.70 | 0.74 | 0.63 [0.52, 0.73] | 322.04/298.10 (26.98) /620.14 | 0.84 | 6 (5) | 0/1/0 | 0.15 | 0.53 | 0.60/0.61 |

by family (both-success rate):

- greedy_plus/independent: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00; null 1.00; structural decoy 1.00
- greedy_plus/independent_pooled: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00; null 1.00; structural decoy 1.00
- greedy_plus/joint: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00; null 1.00; structural decoy 1.00
- greedy_plus/joint_null: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 1.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 1.00; null 1.00; structural decoy 1.00
- greedy_reference/independent: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 0.75, feedforward_driver 0.33, integrator 0.50, memory_switch 1.00, negative_feedback_controller 0.50, redundant_oscillator 1.00, ring_oscillator 0.75, two_implementations 1.00, winner_take_all 0.50; shift 1.00; decoy 0.80; null 0.50; structural decoy 0.67
- greedy_reference/independent_pooled: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 0.75, feedforward_driver 0.33, integrator 0.50, memory_switch 1.00, negative_feedback_controller 0.50, redundant_oscillator 1.00, ring_oscillator 0.75, two_implementations 1.00, winner_take_all 0.50; shift 1.00; decoy 0.80; null 0.50; structural decoy 0.67
- greedy_reference/joint: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 0.75, feedforward_driver 0.33, integrator 0.50, memory_switch 1.00, negative_feedback_controller 0.50, redundant_oscillator 1.00, ring_oscillator 0.75, two_implementations 1.00, winner_take_all 0.83; shift 1.00; decoy 0.80; null 0.50; structural decoy 0.67
- greedy_reference/joint_null: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 0.75, feedforward_driver 0.33, integrator 0.50, memory_switch 1.00, negative_feedback_controller 0.50, redundant_oscillator 1.00, ring_oscillator 0.75, two_implementations 1.00, winner_take_all 0.50; shift 1.00; decoy 0.80; null 0.50; structural decoy 0.67
