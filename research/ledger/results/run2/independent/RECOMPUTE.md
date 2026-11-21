# Independent recomputation of the run-P primary AUROC

Script: `~/ledger_rooms_recompute/recompute_auroc.py` (`python3 -I ~/ledger_rooms_recompute/recompute_auroc.py --compare`), Python standard library only; no project code imported or run. My numbers were fixed before I opened P.json.

## Inputs and locks

Repository ledger/v1 at a7d58e0. SHA-256:
- research/ledger/predictions/A1/types.csv: 83df4994439d98e153c610ec29fcb775929421f08f1173d92c15a1ece0c7440c, equal to research/ledger/LOCK_predictions_v1.json.
- research/ledger/labels_v2/type_labels.csv: adf02383829617b2fc9d2ce4f20619a074ce245c001ea21261bc8e44ad27dab5, equal to research/ledger/LOCK_labels_v2.json.
- research/ledger/kit_v2/exposed_types.csv: a7a7f9353c989de208b555e9f9da1e1203d7b6e1705d1b5db337a1bd0e5591be, matches its lock.
- research/ledger/labels_v2/exposed_v2.csv: aed2503709b53572d93a60eaba4420ec6c950bcc00d9cedf791bb22c5844f0ed, matches its lock.

Both lock files hash to the values in P.json's unblind flag. The v2 exposed set has 18 types, and the `exposed` column agrees with it on every row. Primary set: 66 types have front yes or no, 50 of them are A1 types, 39 are not exposed, and all 39 have finite scores.

## My numbers

- n = 39: 25 yes, 14 no.
- AUROC = 101/175 = 0.5771428571428572, with 150 of the 350 yes-no pairs tied. Pair counting, midranks and exact decimals agree.
- 95% bootstrap interval (seed 777): [0.4200, 0.7286]. Over ten seeds the endpoints average 0.4207 (sd 0.0015) and 0.7241 (sd 0.0026).
- Permutation p (seed 778) = 0.1830. Exact p over all C(39,25) labelings = 0.1825.

## Project's numbers (research/ledger/results/run2/P.json)

n = 39 (25 positive, 14 negative). AUROC = 0.5771428571428572. Interval (seed 20261120): [0.4171, 0.7243]. p (seed 20261121) = 0.1818.

## Verdict

- AUROC and counts agree exactly (|diff| = 0.0).
- p is close: both lie within 0.2 Monte Carlo standard errors of the exact p.
- The interval is close by my pre-set rule (each endpoint within 3 sd of my ten-seed mean). The upper endpoint is 0.05 sd away. The lower endpoint is 2.3 sd away, one AUROC step (1/700) below my lowest seed.
- Consistent with P.json's decision: not underpowered, and the lower bound is below 0.5 in every seed.
