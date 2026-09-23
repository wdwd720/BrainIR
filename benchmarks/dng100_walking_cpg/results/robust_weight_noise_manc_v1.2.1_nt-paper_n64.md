# Multiplicative synapse-count noise (DNg100 activation)

Network manc:v1.2.1 nt=paper (N = 4604, 196535 pairs), stimulus = DNg100 at position(s) [31] with I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; seeds 0..63; wall 746 s on 4 workers.

| condition | n | mean score | median score | frac >= 0.5 | sustained / active MNs (median) | median MN f (Hz) | median active MNs (range) | median active neurons | paper |
|---|---|---|---|---|---|---|---|---|---|
| sigma=0 | 64 | 0.972 | 0.999 | 1.000 | 0.67 | 10.53 | 3 (1-5) | 91 | mean score 0.974 |
| sigma=0.05 | 64 | 0.978 | 0.999 | 1.000 | 0.67 | 10.54 | 3 (1-5) | 88 | mean score 0.965 |
| sigma=0.1 | 64 | 0.976 | 0.999 | 1.000 | 0.67 | 10.64 | 2 (1-6) | 88 | mean score 0.954 |
| sigma=0.15 | 64 | 0.897 | 0.999 | 0.922 | 0.67 | 10.71 | 2 (0-6) | 86 | mean score 0.884 |
| sigma=0.2 | 64 | 0.866 | 0.999 | 0.891 | 0.67 | 10.75 | 3 (0-9) | 86 | mean score 0.814 |
| sigma=0.3 | 64 | 0.727 | 0.913 | 0.750 | 0.50 | 10.76 | 3 (0-89) | 90 | mean score 0.669 |
| sigma=0.5 | 64 | 0.433 | 0.193 | 0.422 | 0.00 | 8.93 | 6 (0-103) | 119 | mean score 0.435 |
