# Multiplicative synapse-count noise (DNg100 activation)

Network manc:v1.2.1 nt=paper (N = 4604, 196535 pairs), stimulus = DNg100 at position(s) [31] with I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; seeds 0..7; wall 263 s on 6 workers.

| condition | n | mean score | median score | frac >= 0.5 | sustained / active MNs (median) | median MN f (Hz) | median active MNs (range) | median active neurons | paper |
|---|---|---|---|---|---|---|---|---|---|
| sigma=0 | 8 | 0.969 | 1.000 | 1.000 | 1.00 | 10.39 | 3 (2-5) | 91 | mean score 0.974 |
| sigma=0.05 | 8 | 0.970 | 0.999 | 1.000 | 0.67 | 10.58 | 3 (2-5) | 88 | mean score 0.965 |
| sigma=0.1 | 8 | 0.972 | 0.992 | 1.000 | 0.67 | 10.75 | 2 (1-4) | 86 | mean score 0.954 |
| sigma=0.15 | 8 | 0.830 | 0.953 | 0.875 | 0.50 | 12.35 | 2 (1-6) | 84 | mean score 0.884 |
| sigma=0.2 | 8 | 0.714 | 0.927 | 0.750 | 0.42 | 11.44 | 2 (1-9) | 84 | mean score 0.814 |
| sigma=0.3 | 8 | 0.340 | 0.102 | 0.375 | 0.01 | 10.53 | 4 (1-89) | 88 | mean score 0.669 |
| sigma=0.5 | 8 | 0.215 | 0.037 | 0.125 | 0.00 | 4.04 | 10 (1-95) | 128 | mean score 0.435 |
