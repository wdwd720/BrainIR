# Pair-tournament arms: paired comparisons

Sources: `arms_pairs_v1h.json`

Pairs = (suite, instance, seed); CIs resample instances. Success = both networks solved. Calls saved = calls(B) - calls(A) (positive: A is cheaper). Failed runs count as unsuccessful at the full call limit.

| method | A vs B | runs (instances) | success A / B | success A - B [95% CI] | calls saved by A [95% CI] | wins / losses (sign p) |
|---|---|---|---|---|---|---|
| greedy_plus | joint vs joint_null | 78 (26) | 0.96 / 0.96 | +0.000 [+0.000, +0.000] | +53.6 [+39.0, +67.6] | 0 / 0 (n/a) |
| greedy_plus | joint vs independent_pooled | 78 (26) | 0.96 / 0.96 | +0.000 [+0.000, +0.000] | +45.3 [+29.5, +60.3] | 0 / 0 (n/a) |
| greedy_plus | joint vs independent | 78 (26) | 0.96 / 0.96 | +0.000 [+0.000, +0.000] | +45.3 [+29.5, +60.3] | 0 / 0 (n/a) |
| greedy_plus | independent_pooled vs independent | 78 (26) | 0.96 / 0.96 | +0.000 [+0.000, +0.000] | +0.0 [+0.0, +0.0] | 0 / 0 (n/a) |
| greedy_reference | joint vs joint_null | 78 (26) | 0.72 / 0.73 | -0.013 [-0.038, +0.000] | +120.8 [+66.1, +178.2] | 0 / 1 (1.000) |
| greedy_reference | joint vs independent_pooled | 78 (26) | 0.72 / 0.72 | +0.000 [+0.000, +0.000] | +111.5 [+52.5, +172.7] | 0 / 0 (n/a) |
| greedy_reference | joint vs independent | 78 (26) | 0.72 / 0.72 | +0.000 [+0.000, +0.000] | +111.7 [+52.8, +172.9] | 0 / 0 (n/a) |
| greedy_reference | independent_pooled vs independent | 78 (26) | 0.72 / 0.72 | +0.000 [+0.000, +0.000] | +0.2 [+0.0, +0.6] | 0 / 0 (n/a) |
