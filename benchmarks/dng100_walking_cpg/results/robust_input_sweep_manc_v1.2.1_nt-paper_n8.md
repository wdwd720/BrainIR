# Stimulus-amplitude sweep (DNg100 activation)

Network manc:v1.2.1 nt=paper (N = 4604, 196535 pairs), stimulus = DNg100 at position(s) [31] with I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; seeds 0..7; wall 167 s on 6 workers.

| condition | n | mean score | median score | frac >= 0.5 | sustained / active MNs (median) | median MN f (Hz) | median active MNs (range) | median active neurons | paper |
|---|---|---|---|---|---|---|---|---|---|
| I=180 | 8 | 0.000 | 0.000 | 0.000 | 0.00 | - | 0 (0-0) | 16 | mostly no active MN |
| I=220 | 8 | 0.814 | 0.950 | 0.875 | 0.50 | 9.26 | 2 (0-3) | 66 | median MN f 9.6 Hz (both DNg100s, n = 512) |
| I=250 | 8 | 0.969 | 1.000 | 1.000 | 1.00 | 10.39 | 3 (2-5) | 91 |  |
| I=260 | 8 | 0.979 | 0.999 | 1.000 | 0.83 | 10.76 | 3 (2-5) | 95 | median MN f 11.0 Hz (both DNg100s, n = 512) |
| I=300 | 8 | 0.969 | 0.979 | 1.000 | 0.67 | 12.12 | 4 (2-5) | 122 | median MN f 12.0 Hz (both DNg100s, n = 512) |
| I=340 | 8 | 0.959 | 0.966 | 1.000 | 0.50 | 12.90 | 4 (4-7) | 152 | median MN f 12.7 Hz (both DNg100s, n = 512) |
