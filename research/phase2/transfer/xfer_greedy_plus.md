# Cross-connectome transfer experiments — xfer_greedy_plus

method `greedy_plus`; networks `male-cns_v1.0` <-> `manc_v1.2.1`; seeds [0, 1, 2]; budgets 1000/1000; 24 runs (0 failed); oracle-free

| direction / mode | n | source sufficient | destination sufficient | dest. pass fraction | calls src / dst / adapt / total | size src / dst | null pass |
|---|---|---|---|---|---|---|---|
| male-cns_v1.0->manc_v1.2.1/independent | 3 | 1.00 | 1.00 | 1.00 | 248.33 / 177.33 / 0.00 / 425.67 | 3.67 / 3.33 | n/a |
| male-cns_v1.0->manc_v1.2.1/transfer | 3 | 1.00 | 1.00 | 1.00 | 248.33 / 2.00 / 0.00 / 250.33 | 3.67 / 3.67 | 0.00 |
| male-cns_v1.0->manc_v1.2.1/prior | 3 | 1.00 | 1.00 | 1.00 | 248.33 / 132.67 / 0.00 / 381.00 | 3.67 / 3.00 | n/a |
| male-cns_v1.0->manc_v1.2.1/joint | 3 | 1.00 | 1.00 | 1.00 | 248.33 / 0.00 / 19.33 / 267.67 | 3.67 / 3.67 | n/a |
| manc_v1.2.1->male-cns_v1.0/independent | 3 | 1.00 | 1.00 | 0.89 | 177.33 / 248.33 / 0.00 / 425.67 | 3.33 / 3.67 | n/a |
| manc_v1.2.1->male-cns_v1.0/transfer | 3 | 1.00 | 0.67 | 0.67 | 177.33 / 2.00 / 21.33 / 200.67 | 3.33 / 3.33 | 0.00 |
| manc_v1.2.1->male-cns_v1.0/prior | 3 | 1.00 | 1.00 | 1.00 | 177.33 / 137.67 / 0.00 / 315.00 | 3.33 / 3.00 | n/a |
| manc_v1.2.1->male-cns_v1.0/joint | 3 | 1.00 | 1.00 | 0.89 | 0.00 / 248.33 / 19.33 / 267.67 | 3.67 / 3.67 | n/a |
- male-cns_v1.0->manc_v1.2.1/transfer_vs_independent_jaccard: 0.58
- manc_v1.2.1->male-cns_v1.0/transfer_vs_independent_jaccard: 0.58
