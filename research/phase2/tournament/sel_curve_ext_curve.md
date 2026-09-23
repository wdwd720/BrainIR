# Query-efficiency curve — sel_curve_ext

54 instances x networks ['main', 'order1'] x seeds [0]

| method | b=50 | b=100 | AUC(log budget) |
|---|---|---|---|
| greedy_reference | 0.52 / 0.48 / 47 | 0.56 / 0.56 / 88 | 0.542 |
| greedy_plus | 1.00 / 0.99 / 42 | 1.00 / 0.99 / 51 | 1.000 |
| group_probe | 1.00 / 1.00 / 47 | 1.00 / 1.00 / 79 | 1.000 |
| surrogate_search | 0.98 / 0.99 / 49 | 1.00 / 0.99 / 79 | 0.991 |
| evo_pareto | 1.00 / 1.00 / 46 | 0.99 / 1.00 / 95 | 0.995 |
| cem_search | 0.99 / 1.00 / 44 | 1.00 / 0.99 / 58 | 0.995 |

cells: structural success rate / mean keep-only pass fraction (nominal) / mean calls used
