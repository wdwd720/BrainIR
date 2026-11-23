# Run 6: the third animal (BANC), tests C1-C8 and Part V (generated from `thirdfly_v1/C_tests.json`)

**Validity (B4):** tuned screen DNg100 >= 0.5 in 11 of 16 seeds (NOT valid; bar 12); sweep 8 of 8 (valid; bar 6). **Primary procedure: sweep.**

## The tests (words are PREREG v6's; sets without DNg100)

| test | pre-registered words | numbers |
|---|---|---|
| C1 left vs right in BANC (180 types) | a real gap | ratio 0.58 (0.38-0.77); drivers L 9, R 7; MANC 0.59, MaleCNS 0.64 (locked) |
| C2 count noise in BANC | does not reproduce it | copy vs copy rho_x 0.63 (0.50-0.74), ratio 0.78 (0.64-0.89); observed left-right rho_x 0.42, ratio 0.58 (0.38-0.77); difference -0.21 (-0.37--0.05) |
| C3 across animals (sweep; 181 types) | confirmed in the third animal | MANC-BANC 0.35 (0.20-0.49); MaleCNS-BANC 0.50 (0.38-0.62); MANC-MaleCNS (reference, post hoc) 0.31 (0.17-0.45); wiring check {"MANC-BANC": 0.626, "MaleCNS-BANC": 0.628, "MANC-BANC_floor5": 0.611, "MaleCNS-BANC_floor5": 0.632, "MANC-MaleCNS": 0.823}; CAVEAT: BANC's wiring of these types agrees with the other animals' less than the first two animals' wiring agreed, so part of the gap may come from the build or the type match |
| C4 MANC sweep list (manc_banc_high_noDNg100, N 202) | above chance | at 0.5: 5 of 17 recur (CP 0.10-0.56); BANC drivers 20; chance 1.68; p 0.016; OC ratio 0.29 (0.10-0.52); curve 0.3: 12/36 (chance 5.7), 0.4: 9/29 (chance 3.7), 0.5: 5/17 (chance 1.7), 0.6: 2/15 (chance 1.2); AUROC 0.67 |
| C4 A1 (the authors' list; 16-replicate halves under either procedure) (manc_banc_high_noDNg100, N 202) | at chance at the authors' cut | at 0.5: 1 of 6 recur (CP 0.00-0.64); BANC drivers 20; chance 0.59; p 0.469; OC ratio 0.16 (0.00-0.51); curve 0.3: 5/18 (chance 2.9), 0.4: 3/10 (chance 1.3), 0.5: 1/6 (chance 0.6), 0.6: 1/4 (chance 0.3); AUROC 0.61 |
| C4 MaleCNS sweep list (mcns_banc_high_noDNg100, N 182) | above chance | at 0.5: 12 of 60 recur (CP 0.11-0.32); BANC drivers 19; chance 6.26; p 0.004; OC ratio 0.72 (0.49-0.91); curve 0.3: 24/86 (chance 13.7), 0.4: 19/71 (chance 9.4), 0.5: 12/60 (chance 6.3), 0.6: 8/50 (chance 4.1); AUROC 0.67 |
| C5 DNg100 (tuned) | pass | tuned type score 0.64, 11 of 16 seeds >= 0.5; sweep 0.92 |
| C5 DNb08 (no prediction) | - | whole type tuned 0.00, sweep 0.25; members alone: 208: 0.00 (0/16); 2446: 0.00 (0/16); 2722: 0.00 (0/16); 4947: 0.00 (0/16); authors' BANC run position 2446 at 250.0: 0.000 |
| C6 pooling (181 types) | not shown | d_M 0.199 (0.084 to 0.322); d_C 0.020 (-0.034 to 0.074); prompt's D (no words) 0.080 |
| C7 how many connectomes | (an extrapolation; no words) | rbar 0.39; n* 6.3 (rounded up 7), interval 4.3 to 9.7 |
| C8 stability predicts BANC (12 types) | stability under count noise predicts the third animal | Spearman 0.57, one-sided p 0.029; with DNg100 0.64; without DNb08 0.54; stability fraction 0.53; partial given MANC score 0.56 |

## Part V (descriptive; fixed words)

- **V1:** reproduces the authors' DNg100 result (mean 0.98, 1.00 of 64 seeds >= 0.5; authors 0.985).
- **V2:** at the authors' configuration (position 391, current 250) it reproduces their result (15 of 16 seeds >= 0.5, mean 0.86).
- **V2 words:** reproduces the authors' reported result at current 250 (position 391), 362.039 (position 328), 512 (position 328), 724.077 (position 328), 1024 (position 328), 724.077 (position 330), 1024 (position 330), 1448.15 (position 330), 2048 (position 330), 362.039 (position 345), 512 (position 345), 724.077 (position 345), 128 (position 391), 181.019 (position 391), 256 (position 391), 362.039 (position 391), 512 (position 391), 724.077 (position 391), 1024 (position 391), 1448.15 (position 391), 2048 (position 391).

## Hits in any animal (C5 table; scores)

| type | MANC tuned | MaleCNS tuned | BANC tuned | MANC sweep | MaleCNS sweep | BANC sweep | authors (A1) | match MaleCNS / BANC |
|---|---|---|---|---|---|---|---|---|
| DNa03 | 0.35 | 0.89 | 0.00 | 0.06 | 0.97 | 0.00 | 0.02 | high / high |
| DNa07 | 0.86 | 0.42 | 0.00 | 0.99 | 0.92 | 0.00 | 0.84 | high / high |
| DNa13 | 0.42 | 0.62 | 0.00 | 0.74 | 0.84 | 0.56 | 0.46 | high / high |
| DNb08 | 0.61 | 0.78 | 0.00 | 0.80 | 0.83 | 0.25 | 0.63 | high / high |
| DNd05 | 0.00 | 0.68 | 0.01 | 0.00 | 0.79 | 0.00 | 0.00 | high / high |
| DNfl014 | 0.00 | 0.33 | 0.94 | 0.47 | 0.52 | 0.99 | 0.01 | medium / medium |
| DNfl015 | 0.00 | 0.86 | 0.56 | 0.00 | 0.97 | 0.77 | 0.00 | high / high |
| DNfl018 | 0.20 | 0.84 | - | 0.74 | 0.97 | - | 0.16 | low / none |
| DNfl021 | 0.08 | 0.04 | 0.66 | 0.00 | 0.20 | 0.99 | 0.09 | low / medium |
| DNfl022 | 0.07 | 0.81 | 0.03 | 0.04 | 0.94 | 0.34 | 0.05 | low / high |
| DNfl025 | 0.15 | 0.07 | 0.55 | 0.70 | 0.21 | 0.80 | 0.19 | high / high |
| DNfl026 | 0.38 | 0.19 | 0.73 | 0.47 | 0.45 | 0.99 | 0.37 | high / high |
| DNfl030 | 0.05 | 0.61 | 0.05 | 0.03 | 0.68 | 0.12 | 0.02 | medium / medium |
| DNfl031 | 0.28 | 0.70 | 1.00 | 0.79 | 0.98 | 1.00 | 0.25 | high / medium |
| DNfl034 | 0.27 | 0.65 | - | 0.35 | 0.71 | - | 0.23 | high / none |
| DNg100 | 0.83 | 0.67 | 0.64 | 0.81 | 0.98 | 0.92 | 0.90 | high / high |
| DNg109 | 0.01 | 0.69 | 0.00 | 0.05 | 0.74 | 0.19 | 0.03 | high / high |
| DNg12 | 0.00 | 0.52 | 0.04 | 0.00 | 0.56 | 0.09 | 0.08 | low / medium |
| DNg13 | 0.29 | 0.74 | 0.94 | 0.06 | 0.73 | 0.98 | 0.14 | high / high |
| DNg21 | 0.00 | 0.53 | 0.01 | 0.00 | 0.57 | 0.08 | 0.10 | high / high |
| DNg47 | 0.23 | 0.13 | 0.86 | 0.27 | 0.82 | 0.97 | 0.05 | high / medium |
| DNg54 | 0.43 | 0.00 | 0.00 | 0.90 | 0.01 | 0.01 | 0.59 | medium / high |
| DNg63 | 0.79 | 0.10 | 0.00 | 0.00 | 0.46 | 0.01 | 0.13 | high / high |
| DNg74 | - | 0.73 | - | - | 0.86 | - | - | medium / none |
| DNg87 | 0.02 | 0.00 | 0.81 | 0.03 | 0.27 | 0.97 | 0.02 | high / high |
| DNit011 | 0.79 | 0.03 | - | 0.95 | 0.42 | - | 0.76 | medium / none |
| DNit013 | 0.72 | 0.80 | 0.02 | 1.00 | 0.99 | 0.07 | 0.69 | low / medium |
| DNp02 | 0.66 | 0.05 | 0.01 | 0.49 | 0.13 | 0.05 | 0.40 | high / high |
| DNp41 | 0.73 | 0.00 | 0.00 | 0.88 | 0.11 | 0.00 | 0.65 | high / high |
| DNp63 | 0.79 | 0.00 | 0.00 | 0.99 | 0.89 | 0.06 | 0.00 | high / high |
| DNp71 | 0.44 | 0.56 | 0.01 | 0.63 | 0.76 | 0.02 | 0.47 | high / high |
| DNxl021 | 0.21 | 0.81 | 0.00 | 0.00 | 0.91 | 0.01 | 0.06 | high / high |
| DNxl053 | 0.52 | 0.46 | - | 0.32 | 0.51 | - | 0.46 | high / none |
| DNxl067 | 0.00 | 0.73 | 0.00 | 0.00 | 0.93 | 0.62 | 0.15 | high / medium |
| DNxl092 | 0.40 | 0.84 | 0.00 | 0.75 | 0.85 | 0.54 | 0.47 | high / high |
| DNxl101 | 0.52 | 0.15 | 0.00 | 0.30 | 0.43 | 0.00 | 0.63 | high / medium |
| DNxl102 | 0.64 | 0.00 | 0.93 | 0.68 | 0.92 | 0.98 | 0.66 | medium / high |
| DNxl110 | 0.54 | 0.18 | 0.00 | 0.06 | 0.66 | 0.01 | 0.58 | high / high |
| DNxl121 | 0.62 | 0.28 | 0.00 | 0.00 | 0.67 | 0.01 | 0.32 | high / high |
| DNxl125 | 0.36 | 0.20 | 0.61 | 0.37 | 0.50 | 0.90 | 0.23 | high / high |
| DNxl129 | 0.01 | 0.00 | 0.75 | 0.00 | 0.01 | 0.77 | 0.00 | high / high |
| DNxl130 | 0.38 | 0.54 | 0.23 | 0.50 | 0.78 | 0.46 | 0.00 | high / high |
| DNxl133 | 0.52 | 0.12 | - | 0.55 | 0.35 | - | 0.62 | low / none |
| DNxn104 | 0.00 | 0.71 | 0.00 | 0.00 | 0.94 | 0.00 | 0.00 | low / medium |
| DNxn118 | 0.44 | 0.90 | 0.00 | 0.52 | 0.92 | 0.00 | 0.39 | high / high |
| DNxn127 | 0.08 | 0.10 | 0.98 | 0.20 | 0.38 | 1.00 | 0.04 | high / high |
| DNxn143 | 0.00 | 0.70 | 0.00 | 0.00 | 0.86 | 0.46 | 0.28 | high / high |
| DNxn151 | 0.31 | 0.67 | 0.61 | 0.06 | 0.68 | 0.77 | 0.01 | high / high |
| DNxn168 | 0.05 | 0.85 | 0.02 | 0.03 | 0.87 | 0.02 | 0.05 | high / high |
| DNxn171 | 0.32 | 0.75 | 0.00 | 0.58 | 0.98 | 0.00 | 0.34 | high / medium |
| DNxn174 | 0.15 | 0.77 | 0.00 | 0.05 | 0.85 | 0.00 | 0.01 | high / high |
| pMP2 | 0.21 | 0.67 | - | 0.10 | 0.64 | - | 0.15 | high / none |

## The forward list with BANC scores (readings unchanged)

| type | BANC tuned | BANC sweep | BANC match |
|---|---|---|---|
| DNp71 | 0.01 | 0.02 | high |
| DNa13 | 0.00 | 0.56 | high |
| DNa07 | 0.00 | 0.00 | high |
| DNa03 | 0.00 | 0.00 | high |
| DNp41 | 0.00 | 0.00 | high |
| DNp02 | 0.01 | 0.05 | high |
| DNg63 | 0.00 | 0.01 | high |
| DNg13 | 0.94 | 0.98 | high |
| DNg21 | 0.01 | 0.08 | high |
| DNp07 | 0.00 | 0.00 | high |
| DNg39 | 0.00 | 0.01 | high |
| DNp26 | 0.00 | 0.12 | high |
