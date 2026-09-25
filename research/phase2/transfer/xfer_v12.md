# Cross-connectome transfer experiments — xfer_v12

method `brainir_v1`; networks `male-cns_v1.0` <-> `manc_v1.2.1`; seeds [0, 1, 2]; budgets 1000/1000; 24 runs (0 failed); oracle-free

| direction / mode | n | source sufficient | destination sufficient | dest. pass fraction | calls src / dst / adapt / total | size src / dst | null pass |
|---|---|---|---|---|---|---|---|
| male-cns_v1.0->manc_v1.2.1/independent | 3 | 1.00 | 1.00 | 1.00 | 406.33 / 358.67 / 0.00 / 765.00 | 3.00 / 3.33 | n/a |
| male-cns_v1.0->manc_v1.2.1/transfer | 3 | 1.00 | 1.00 | 1.00 | 406.33 / 2.00 / 0.00 / 408.33 | 3.00 / 3.00 | 0.00 |
| male-cns_v1.0->manc_v1.2.1/prior | 3 | 1.00 | 1.00 | 1.00 | 406.33 / 362.00 / 0.00 / 768.33 | 3.00 / 3.33 | n/a |
| male-cns_v1.0->manc_v1.2.1/joint | 3 | 1.00 | 1.00 | 1.00 | 406.33 / 0.00 / 16.33 / 422.67 | 3.00 / 3.00 | n/a |
| manc_v1.2.1->male-cns_v1.0/independent | 3 | 1.00 | 1.00 | 1.00 | 358.67 / 406.33 / 0.00 / 765.00 | 3.33 / 3.00 | n/a |
| manc_v1.2.1->male-cns_v1.0/transfer | 3 | 1.00 | 0.67 | 0.67 | 358.67 / 2.00 / 21.33 / 382.00 | 3.33 / 3.33 | 0.00 |
| manc_v1.2.1->male-cns_v1.0/prior | 3 | 1.00 | 1.00 | 1.00 | 358.67 / 366.67 / 0.00 / 725.33 | 3.33 / 3.00 | n/a |
| manc_v1.2.1->male-cns_v1.0/joint | 3 | 1.00 | 1.00 | 1.00 | 0.00 / 406.33 / 16.33 / 422.67 | 3.00 / 3.00 | n/a |
- male-cns_v1.0->manc_v1.2.1/transfer_vs_independent_jaccard: 0.80
- manc_v1.2.1->male-cns_v1.0/transfer_vs_independent_jaccard: 0.80
