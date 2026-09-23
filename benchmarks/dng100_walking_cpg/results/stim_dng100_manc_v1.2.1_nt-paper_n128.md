# DNg100 stimulation manc:v1.2.1 nt=paper

n = 128 replicates (seeds 0..127), I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; wall 173 s on 8 workers.

| statistic | BrainIR | paper (n = 1024) |
|---|---|---|
| mean score | 0.975 | 0.974 |
| median score | 0.999 | 0.999 |
| fraction >= 0.5 | 1.000 | 0.998 |
| median active MNs (range) | 3 (1-5) | 3 (0-6) |
| median MN frequency (Hz) | 10.53 | ~10-11 (I = 250: 9.6 at 220, 11.0 at 260) |
| solver failures | 0 | n/a |
