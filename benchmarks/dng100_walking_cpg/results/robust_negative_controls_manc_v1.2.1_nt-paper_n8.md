# Negative controls (DNg100 activation on manipulated networks)

Network manc:v1.2.1 nt=paper (N = 4604, 196535 pairs), stimulus = DNg100 at position(s) [31] with I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; seeds 0..7; wall 413 s on 6 workers.

Control network for seed k is built with seed k and simulated with parameter seed k. Classes for the class shuffle: {'exc_dn': 933, 'exc_in': 1484, 'inh_dn': 385, 'inh_in': 1654, 'mn': 148}.

| condition | n | mean score | median score | frac >= 0.5 | sustained / active MNs (median) | median MN f (Hz) | median active MNs (range) | median active neurons | construction |
|---|---|---|---|---|---|---|---|---|---|
| intact | 8 | 0.969 | 1.000 | 1.000 | 1.00 | 10.39 | 3 (2-5) | 91 |  |
| class_shuffle | 8 | 0.173 | 0.140 | 0.000 | 0.02 | 2.00 | 72 (58-88) | 1867 | 43 diagonal entries created |
| degree_rewire | 8 | 0.262 | 0.265 | 0.000 | 0.10 | 1.42 | 108 (107-117) | 3162 | 1779291 of 1965350 swaps accepted |
| sign_shuffle | 8 | 0.066 | 0.035 | 0.000 | 0.00 | 1.73 | 101 (11-120) | 2662 | 2408 + / 2048 - columns |
| weight_permute | 8 | 0.193 | 0.154 | 0.000 | 0.03 | 1.33 | 108 (82-124) | 1870 |  |
