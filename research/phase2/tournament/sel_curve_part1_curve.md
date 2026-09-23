# Query-efficiency curve — sel_curve_part1

54 instances x networks ['main', 'order1'] x seeds [0]

| method | b=250 | b=500 | b=1000 | b=2000 | AUC(log budget) |
|---|---|---|---|---|---|
| greedy_reference | 0.63 / 0.65 / 185 | 0.77 / 0.80 / 242 | 0.78 / 0.81 / 267 | 0.80 / 0.83 / 270 | 0.753 |
| greedy_plus | 1.00 / 0.99 / 85 | 1.00 / 0.99 / 99 | 1.00 / 0.99 / 100 | 1.00 / 0.99 / 100 | 1.000 |
| group_probe | 1.00 / 1.00 / 99 | 1.00 / 1.00 / 114 | 1.00 / 1.00 / 111 | 1.00 / 1.00 / 165 | 1.000 |
| surrogate_search | 1.00 / 0.99 / 83 | 1.00 / 0.99 / 86 | 1.00 / 0.99 / 91 | 1.00 / 0.99 / 91 | 1.000 |

cells: structural success rate / mean keep-only pass fraction (nominal) / mean calls used
