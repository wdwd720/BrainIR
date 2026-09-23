# DNg100 stimulation manc:v1.2.1 nt=brainir

n = 1024 replicates (seeds 0..1023), I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; wall 2695 s on 6 workers.

| statistic | BrainIR | paper (n = 1024) |
|---|---|---|
| mean score | 0.973 | 0.974 |
| median score | 0.999 | 0.999 |
| fraction >= 0.5 | 0.997 | 0.998 |
| median active MNs (range) | 3 (0-5) | 3 (0-6) |
| median MN frequency (Hz) | 10.75 | ~10-11 (I = 250: 9.6 at 220, 11.0 at 260) |
| solver failures | 0 | n/a |
