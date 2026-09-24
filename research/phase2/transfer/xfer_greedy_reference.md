# Cross-connectome transfer experiments — xfer_greedy_reference

method `greedy_reference`; networks `male-cns_v1.0` <-> `manc_v1.2.1`; seeds [0, 1, 2]; budgets 1000/1000; 24 runs (0 failed); oracle-free

| direction / mode | n | source sufficient | destination sufficient | dest. pass fraction | calls src / dst / adapt / total | size src / dst | null pass |
|---|---|---|---|---|---|---|---|
| male-cns_v1.0->manc_v1.2.1/independent | 3 | 1.00 | 1.00 | 1.00 | 388.33 / 681.00 / 0.00 / 1069.33 | 3.00 / 3.00 | n/a |
| male-cns_v1.0->manc_v1.2.1/transfer | 3 | 1.00 | 1.00 | 1.00 | 388.33 / 2.00 / 0.00 / 390.33 | 3.00 / 3.00 | 0.00 |
| male-cns_v1.0->manc_v1.2.1/prior | 3 | 1.00 | 1.00 | 1.00 | 388.33 / 651.33 / 0.00 / 1039.67 | 3.00 / 3.00 | n/a |
| male-cns_v1.0->manc_v1.2.1/joint | 3 | 1.00 | 1.00 | 1.00 | 388.33 / 0.00 / 16.33 / 404.67 | 3.00 / 3.00 | n/a |
| manc_v1.2.1->male-cns_v1.0/independent | 3 | 1.00 | 1.00 | 1.00 | 651.33 / 388.33 / 0.00 / 1039.67 | 3.00 / 3.00 | n/a |
| manc_v1.2.1->male-cns_v1.0/transfer | 3 | 1.00 | 1.00 | 1.00 | 651.33 / 2.00 / 0.00 / 653.33 | 3.00 / 3.00 | 0.00 |
| manc_v1.2.1->male-cns_v1.0/prior | 3 | 1.00 | 1.00 | 1.00 | 681.00 / 388.33 / 0.00 / 1069.33 | 3.00 / 3.00 | n/a |
| manc_v1.2.1->male-cns_v1.0/joint | 3 | 1.00 | 1.00 | 1.00 | 0.00 / 388.33 / 16.33 / 404.67 | 3.00 / 3.00 | n/a |
- male-cns_v1.0->manc_v1.2.1/transfer_vs_independent_jaccard: 1.00
- manc_v1.2.1->male-cns_v1.0/transfer_vs_independent_jaccard: 1.00
