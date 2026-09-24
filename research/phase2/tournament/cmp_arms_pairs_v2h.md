# Pair-tournament arms: paired comparisons

Sources: `arms_pairs_v2h.json`

Pairs = (suite, instance, seed); CIs resample instances. Success = both networks solved. Calls saved = calls(B) - calls(A) (positive: A is cheaper). Failed runs count as unsuccessful at the full call limit.

| method | A vs B | runs (instances) | success A / B | success A - B [95% CI] | calls saved by A [95% CI] | wins / losses (sign p) |
|---|---|---|---|---|---|---|
| greedy_plus | joint vs joint_null | 81 (27) | 1.00 / 1.00 | +0.000 [+0.000, +0.000] | +13.6 [-0.1, +29.5] | 0 / 0 (n/a) |
| greedy_plus | joint vs independent_pooled | 81 (27) | 1.00 / 1.00 | +0.000 [+0.000, +0.000] | +12.4 [-5.0, +33.1] | 0 / 0 (n/a) |
| greedy_plus | joint vs independent | 81 (27) | 1.00 / 1.00 | +0.000 [+0.000, +0.000] | +12.4 [-5.0, +33.1] | 0 / 0 (n/a) |
| greedy_plus | independent_pooled vs independent | 81 (27) | 1.00 / 1.00 | +0.000 [+0.000, +0.000] | +0.0 [+0.0, +0.0] | 0 / 0 (n/a) |
| greedy_reference | joint vs joint_null | 81 (27) | 0.65 / 0.63 | +0.025 [+0.000, +0.074] | +7.2 [-29.2, +45.1] | 2 / 0 (0.500) |
| greedy_reference | joint vs independent_pooled | 81 (27) | 0.65 / 0.63 | +0.025 [+0.000, +0.074] | +2.4 [-39.3, +46.0] | 2 / 0 (0.500) |
| greedy_reference | joint vs independent | 81 (27) | 0.65 / 0.63 | +0.025 [+0.000, +0.074] | +2.4 [-39.3, +46.0] | 2 / 0 (0.500) |
| greedy_reference | independent_pooled vs independent | 81 (27) | 0.63 / 0.63 | +0.000 [+0.000, +0.000] | +0.0 [+0.0, +0.0] | 0 / 0 (n/a) |
