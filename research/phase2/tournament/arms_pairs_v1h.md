# Pair tournament — arms_pairs_v1h

624 jobs; budgets a 1000 / b 1000; seeds [0, 1, 2]; wall 460.7 s on modal-pinned

Calls per network include that network's adaptation calls. Identity claims are scored on every pair: under an implementation shift a claim across implementations is false, and on a null pair every claim is false. Role graphs are compared with the truth; the similarity of a method's two outputs to each other is self-agreement and is not evidence (review E).

| method/mode | n | success a | success b | both [CI] | calls a/b (adapt) /total | pooled | claims (correct) | false shift/null/sdecoy | Brier | role align | role graph vs truth a/b |
|---|---|---|---|---|---|---|---|---|---|---|---|
| greedy_plus/independent | 78 | 0.97 | 0.99 | 0.96 [0.91, 1.00] | 87.22/88.32 (0.00) /175.54 | 0.00 | 0 (0) | 0/0/0 | n/a | 0.84 | 0.96/0.92 |
| greedy_plus/independent_pooled | 78 | 0.97 | 0.99 | 0.96 [0.91, 1.00] | 87.22/88.32 (0.00) /175.54 | 1.00 | 0 (0) | 0/0/0 | n/a | 0.00 | 0.96/0.92 |
| greedy_plus/joint | 78 | 0.97 | 0.99 | 0.96 [0.91, 1.00] | 77.53/52.69 (17.31) /130.22 | 0.26 | 107 (107) | 0/0/0 | 0.00 | 0.84 | 0.96/0.92 |
| greedy_plus/joint_null | 78 | 0.97 | 0.99 | 0.96 [0.91, 1.00] | 89.91/93.87 (14.00) /183.78 | 0.91 | 4 (4) | 0/0/0 | 0.00 | 0.84 | 0.96/0.92 |
| greedy_reference/independent | 78 | 0.77 | 0.76 | 0.72 [0.62, 0.82] | 276.31/292.63 (0.00) /568.94 | 0.00 | 0 (0) | 0/0/0 | n/a | 0.63 | 0.69/0.65 |
| greedy_reference/independent_pooled | 78 | 0.77 | 0.76 | 0.72 [0.63, 0.82] | 276.10/292.63 (0.00) /568.73 | 1.00 | 0 (0) | 0/0/0 | n/a | 0.00 | 0.00/0.00 |
| greedy_reference/joint | 78 | 0.85 | 0.83 | 0.72 [0.62, 0.81] | 269.96/187.24 (33.44) /457.21 | 0.44 | 61 (61) | 0/0/0 | 0.00 | 0.63 | 0.78/0.77 |
| greedy_reference/joint_null | 78 | 0.78 | 0.77 | 0.73 [0.63, 0.83] | 288.12/289.90 (32.68) /578.01 | 0.91 | 4 (4) | 0/0/0 | 0.00 | 0.63 | 0.71/0.66 |

by family (both-success rate):

- greedy_plus/independent: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 0.89, integrator 1.00, memory_switch 0.78, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.86; null n/a; structural decoy n/a
- greedy_plus/independent_pooled: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 0.89, integrator 1.00, memory_switch 0.78, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.86; null n/a; structural decoy n/a
- greedy_plus/joint: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 0.89, integrator 1.00, memory_switch 0.78, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.86; null n/a; structural decoy n/a
- greedy_plus/joint_null: delayed_inhibitory_oscillator 1.00, ei_pair_oscillator 1.00, feedforward_driver 0.89, integrator 1.00, memory_switch 0.78, negative_feedback_controller 1.00, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 1.00; shift 1.00; decoy 0.86; null n/a; structural decoy n/a
- greedy_reference/independent: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 1.00, feedforward_driver 0.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 0.83, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 0.00; shift 1.00; decoy 0.71; null n/a; structural decoy n/a
- greedy_reference/independent_pooled: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 1.00, feedforward_driver 0.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 0.83, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 0.00; shift 1.00; decoy 0.71; null n/a; structural decoy n/a
- greedy_reference/joint: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 1.00, feedforward_driver 0.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 0.83, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 0.00; shift 1.00; decoy 0.71; null n/a; structural decoy n/a
- greedy_reference/joint_null: delayed_inhibitory_oscillator 0.00, ei_pair_oscillator 1.00, feedforward_driver 0.00, integrator 1.00, memory_switch 1.00, negative_feedback_controller 0.83, redundant_oscillator 1.00, ring_oscillator 1.00, two_implementations 1.00, winner_take_all 0.33; shift 1.00; decoy 0.71; null n/a; structural decoy n/a
