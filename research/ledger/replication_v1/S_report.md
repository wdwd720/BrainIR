# Part S: does stability under synapse-count noise inside MANC predict replication in MaleCNS? (pre-registered, PREREG v5)

**Verdict (S1, B1r list, exact one-sided rank test): not shown** (p = 0.1143; 52 of 455 subsets).

Reading against the real-network score (S5): not applicable (S1 not shown). Ranks run upward (rank 1 = least stable).

Stated before the test ran (PREREG v5 S7): only 3 replicated types; the smallest attainable p is 1/C(15,3) = 0.0022 (A1: 1/165); ties at the top raise it, and with seven or more B1r drivers perfectly stable p cannot fall below 0.05; a null result is uninformative; a positive result rests on three types, two of them the confirmed drivers and one (DNit013) on a low-confidence match.

Copies: 16 Poisson copies of MANC's raw counts (floor 5 after resampling), seeds 0..7 each; errored jobs counted as not usable: 0.

| p values (exact rank test) | B1r list (S1, words) | A1 list (secondary) |
|---|---|---|
| S1: stability | 0.1143 | 0.2727 |
| (i) high-confidence matches only | 0.1273 | 0.2 |
| (ii) mean copy score | 0.03516 | 0.1394 |
| (iii) mean fraction rhythmic | 0.03297 | 0.1273 |
| (iv) without low-usability drivers | 0.1818 | 0.2727 |
| (v) reference: real-network B1r score, seeds 0..7 | 0.367 | 0.2485 |
| (v) reference: real-network B1r score, seeds 0..15 | 0.3165 | 0.2485 |

Replicated (locked B2r): DNb08, DNg100, DNit013. Excluded in (iv): DNg63, DNxl121.

| type | stability | mean copy score | mean fraction rhythmic | mean usable seeds | B1r driver | A1 driver | replicated |
|---|---|---|---|---|---|---|---|
| DNg100 | 1.000 | 0.790 | 0.938 | 8.0 | yes | yes | yes |
| DNxl133 | 0.875 | 0.609 | 0.617 | 8.0 | yes | yes |  |
| DNg54 | 0.812 | 0.651 | 0.758 | 8.0 |  | yes |  |
| DNxl102 | 0.812 | 0.583 | 0.617 | 8.0 | yes | yes |  |
| DNit013 | 0.750 | 0.607 | 0.734 | 8.0 | yes | yes | yes |
| DNp02 | 0.750 | 0.588 | 0.688 | 7.9 | yes |  |  |
| DNit011 | 0.562 | 0.526 | 0.570 | 8.0 | yes | yes |  |
| DNa07 | 0.500 | 0.485 | 0.508 | 7.6 | yes | yes |  |
| DNb08 | 0.438 | 0.492 | 0.500 | 8.0 | yes | yes | yes |
| DNp63 | 0.438 | 0.452 | 0.438 | 7.9 | yes |  |  |
| DNxl053 | 0.438 | 0.462 | 0.461 | 6.6 | yes |  |  |
| DNxl110 | 0.438 | 0.427 | 0.445 | 8.0 | yes | yes |  |
| DNxl101 | 0.250 | 0.345 | 0.336 | 7.6 | yes | yes |  |
| DNp41 | 0.188 | 0.222 | 0.242 | 7.4 | yes | yes |  |
| DNxl121 | 0.062 | 0.114 | 0.023 | 0.8 | yes |  |  |
| DNg63 | 0.000 | 0.138 | 0.031 | 2.0 | yes |  |  |

**S2 (40 sampled non-hits):** 26 of 640 (type, copy) pairs scored >= 0.5 (rate 0.0406 per copy); 7 of 40 types had at least one driver copy (95 % CI 0.073-0.328); 0 had stability >= 0.5. By B1r band: B1r_non_driver_lt_0.05: 4 of 496 pairs, 2 of 31 types; B1r_indeterminate_0.05_to_0.5: 22 of 144 pairs, 5 of 9 types.
