**Pre-registered verdict: the model predicts, but it adds nothing beyond wiring.** Its predicted movements identify the hemilineage that was switched on better than chance (mean percentile rank 0.633, 95 % interval 0.533 to 0.724, one-sided permutation p = 0.0076, 27 hemilineages), and a wiring count with no simulation, the signed two-step synapse paths from the stimulated group to each motor pool, does as well (0.638; model minus it -0.006, 95 % interval -0.172 to +0.166).

# BrainIR prediction ledger, results 2 (run 3): exam 2, hemilineages

Labels `LOCK_labels_h1.json` against predictions `LOCK_predictions_h1.json` (H-M, H-M-s0-3, the eight wiring baselines) and `LOCK_predictions_h1b.json` (the descriptive arms), under rulebook v3 (`LOCK_prereg_v3.json`, tag `ledger-prereg-v3`). The gate held all six conditions on its second run (`gates_v3/UNBLINDING_GATE_h1_run2.json`). The flag `UNBLIND_h1.json` was committed, the frozen pipeline ran once for the primary analysis (`results/run3/primary.json`) and once for the pre-declared secondary analyses (`results/run3/secondary.json`), nothing crashed, and the flag was then retired (`results/run3/UNBLIND_h1_used.json`). A fresh agent recomputed the primary statistic from the rulebook text with its own code; it agrees exactly (`results/run3/recompute/`).

How to read the statistic: for each hemilineage with at least 3 coded primary dimensions, its observed pattern is compared with all 43 predicted patterns. Its percentile rank is the share of the 42 other candidates whose prediction fits worse than its own (ties count half): 1 means its own prediction fits best, 0.5 is chance.

## Headline (H-M: the authors' full-cord model, L14 procedure, 16 seeds)

| statistic | value | chance (permutation null: mean, 2.5-97.5 %) |
|---|---|---|
| hemilineages scored (>= 3 coded primary dimensions) | 27 | (gate needs >= 20) |
| mean percentile rank of the true hemilineage | **0.633** (95 % interval 0.533-0.724) | 0.507 (0.398-0.612) |
| one-sided p (10,000 permutations) | 0.0076 | |
| top-1 accuracy | 0.000 (0 of 27) | 0.021 (0.000-0.074) |
| top-3 accuracy | 0.074 (2 of 27) | 0.068 (0.000-0.148) |

Decision rules (S3). Not underpowered (27 >= 20). "Predicts" holds: p < 0.05, and the interval's lower bound (0.533) is above both 0.5 and the permutation-null mean (0.507). "Adds value beyond wiring" does not hold: the paired interval against the best wiring baseline includes 0, and the model's point estimate is slightly below that baseline's.

## Ceiling: one lab's results identifying the other's

| truth | predictor | hemilineages | mean percentile rank |
|---|---|---|---|
| Soffers 2025 | Harris 2015 | 10 | 0.481 |
| Harris 2015 | Soffers 2025 | 10 | 0.692 |

Only 10 hemilineages are coded on at least 3 primary dimensions by both labs, and where both code the same cell they agree on 79 % of 33 cells, a Cohen's kappa of only 0.24 (chance agreement is 0.72). The ceiling is therefore low and unstable: 0.481 one way, 0.692 the other. The model's 0.633 lies between them. Each lab separately as truth (S4.2): Harris 2015 0.662 (19 hemilineages), Soffers 2025 0.556 (18 hemilineages).

## Wiring: each baseline (no simulation) and the paired comparison

| baseline | what it counts | mean percentile rank |
|---|---|---|
| H-S-k0 | motor neurons that are members of the group | 0.420 |
| H-S-k1-signed | one-hop synapses to each pool, signed | 0.557 |
| H-S-k1-unsigned | one-hop synapses, unsigned | 0.551 |
| H-S-k2-signed (best) | two-hop paths, signed | 0.638 |
| H-S-k2-unsigned | two-hop paths, unsigned | 0.497 |
| H-S-k3-signed | three-hop paths, signed | 0.506 |
| H-S-k3-unsigned | three-hop paths, unsigned | 0.476 |
| H-S-lin | steady state of the linearised network | 0.461 |
| **H-M (simulation)** | the authors' model | **0.633** |

Paired bootstrap over the 27 hemilineages (10,000 resamples): H-M minus H-S-k2-signed = -0.0057, 95 % interval -0.172 to +0.166. The best of the eight baselines is picked on these same labels, as pre-registered; that choice slightly favours the baselines.

## Controls: the ten control networks

Each control runs the H-M procedure on seeds 0-3, so it is compared with H-M on the same four seeds (H-M-s0-3): **0.616**.

| control | mean percentile rank |
|---|---|
| H-C-classshuffle-201 | 0.535 |
| H-C-classshuffle-202 | 0.563 |
| H-C-classshuffle-203 | 0.604 |
| H-C-classshuffle-204 | 0.614 |
| H-C-classshuffle-205 | 0.584 |
| H-C-rewire-101 | 0.512 |
| H-C-rewire-102 | 0.451 |
| H-C-rewire-103 | 0.597 |
| H-C-rewire-104 | 0.478 |
| H-C-rewire-105 | 0.528 |

Degree-preserving rewiring keeps each neuron's number of inputs and outputs and the sign of its outputs, and moves the targets. The class shuffles exchange whole input sets among neurons of the same class (excitatory or inhibitory descending neurons, excitatory or inhibitory interneurons, motor neurons): each neuron keeps its sign and how much it sends into each class, not which members it reaches. Rewired networks average 0.513 (0.451-0.597), class shuffles 0.580 (0.535-0.614). All ten score below the intact network on the same seeds, but the class shuffles keep most of its score: much of what identifies a hemilineage survives when its outputs reach the wrong members of each class.

## By class (S4.4: observations re-centred within the class; candidates still all 43)

| class | hemilineages | mean percentile rank |
|---|---|---|
| excitatory | 11 | 0.641 |
| inhibitory | 15 | 0.432 |
| motor | 1 | 0.500 (one hemilineage: nothing to compare within the class, 0.5 by construction) |

Within a class the model tells excitatory hemilineages apart moderately and inhibitory ones not at all. 18 of the 43 hemilineages are predicted to move nothing; they share one predicted pattern and tie with one another in every comparison, and 11 of them are among the 27 scored. 17 of the 18 are classed inhibitory, as anticipated before the predictions (M6: the model is silent at rest and inhibitory neurons can only lower activity). For 12 of these the tuner accepts a current (enough neurons become active) but no motor neuron in the read-out responds; the other 5 (00B, 14B, 17B, 21X, 26X; 4 to 39 thoracic members) stay too weak at every current. The last one, 08B, is classed excitatory (474 of its 488 thoracic members cholinergic): the tuner accepts it in every seed, yet no motor neuron in the read-out responds.

## Per dimension (S4.3: AUROC of the predicted value against the coded cells)

| dimension | coded cells (yes) | AUROC |
|---|---|---|
| any visible movement | 28 (27) | 0.815 |
| front legs move | 16 (14) | 0.554 |
| middle legs move | 19 (18) | 0.750 |
| hind legs move | 17 (15) | 0.517 |
| legs flex / body lowers, held | 20 (8) | 0.448 |
| legs extend / body rises, held | 16 (7) | 0.595 |
| repeated leg movement (7') | 18 (15) | 0.733 |
| jump or takeoff | 19 (7) | 0.661 |
| any wing movement | 20 (13) | 0.736 |
| wing buzzing / flight-like | 18 (8) | 0.794 |
| haltere movement | 1 (0) | none (one class only) |
| abdomen movement | 1 (0) | none (one class only) |
| pooled, standardised predictions | 193 | 0.564 |

'Any visible movement' has a single 'no' (00A), so its AUROC only says where that one hemilineage falls. Haltere and abdomen movement have one coded cell each.

## Fixed currents, alternative groups, secondary records (S4.5-S4.6)

| arm | what changes | mean percentile rank |
|---|---|---|
| H-D-128 | every member at fixed current 128, no tuner (seeds 0-7) | 0.571 |
| H-D-256 | every member at fixed current 256, no tuner (seeds 0-7) | 0.582 |
| H-D-384 | every member at fixed current 384, no tuner (seeds 0-7) | 0.588 |
| H-D-512 | every member at fixed current 512, no tuner (seeds 0-7) | 0.597 |
| H-M-S-all | every member in any segment, abdominal included (seeds 0-3) | 0.618 |
| H-M-S-post | thoracic members born postembryonically only (seeds 0-3) | 0.601 |
| H-M-S-T1 | T1 members only (seeds 0-3) | 0.622 |
| H-M-S-T2 | T2 members only (seeds 0-3) | 0.645 |
| H-M-S-T3 | T3 members only (seeds 0-3) | 0.589 |
| H-M-S-L | left members only, by soma side (seeds 0-3) | 0.623 |
| H-M-S-R | right members only, by soma side (seeds 0-3) | 0.614 |
| secondary records as truth | clonal, one-sided, partial or mixed records (7 hemilineages) | 0.599 |

Fixed currents give 0.571-0.597; changing which members are stimulated gives 0.589-0.645, around H-M-s0-3 (0.616).

## Scorecard (27 scored hemilineages, best first)

Predicted: the dimensions on which the hemilineage's prediction is at least 0.5 standard deviations above the mean of the 43; 'silent' means every predicted value is 0, 'weak' means some activity but no dimension that high. Observed: the consensus cells coded yes or no (dimensions not listed were not coded). Rank: position among the 43 candidates, ties shared.

| hemilineage | class | coded | percentile rank | rank (of 43) | predicted (above-average dimensions) | observed yes | observed no |
|---|---|---|---|---|---|---|---|
| 07B | excitatory | 8 | 0.952 | 3 | any, front, middle, hind, flex-held, rep-legs, jump, wings, wing-buzz, haltere, abdomen | any, middle, rep-legs, jump, wings, wing-buzz | flex-held, ext-held |
| 12A | excitatory | 6 | 0.952 | 3 | any, ext-held, rep-legs, jump, wings, wing-buzz, haltere | any, rep-legs, wings, wing-buzz | flex-held, ext-held |
| 04B | excitatory | 6 | 0.929 | 4 | any, front, middle, hind, ext-held, rep-legs, jump, wings, wing-buzz, haltere, abdomen | any, front, middle, hind, ext-held | flex-held |
| 10B | excitatory | 7 | 0.905 | 5 | any, front, middle, hind, rep-legs, jump, wings, wing-buzz, haltere, abdomen | any, ext-held, rep-legs, jump, wings, wing-buzz | flex-held |
| 08A | inhibitory | 9 | 0.905 | 5 | any, haltere | any, front, middle, hind, flex-held | ext-held, jump, wings, wing-buzz |
| 20A.22A | excitatory | 7 | 0.881 | 6 | any, front, middle, hind, ext-held, rep-legs, jump, wings, wing-buzz, haltere, abdomen | any, front, middle, hind, ext-held | flex-held, jump |
| 17A | excitatory | 5 | 0.833 | 8 | any, front, middle, hind, flex-held, rep-legs, wings, wing-buzz, haltere, abdomen | any, front, middle, hind, flex-held | - |
| 18B | excitatory | 8 | 0.810 | 9 | any, front, middle, hind, rep-legs, wings, wing-buzz, haltere, abdomen | any, middle, rep-legs, jump, wings, wing-buzz | flex-held, ext-held |
| 01A | excitatory | 8 | 0.810 | 9 | any, front, middle, hind, flex-held, rep-legs, wings, wing-buzz, haltere, abdomen | any, front, middle, hind, rep-legs, jump, wings | flex-held |
| 00A | inhibitory | 12 | 0.798 | 9.5 | silent (all 0) | - | any, front, middle, hind, flex-held, ext-held, rep-legs, jump, wings, wing-buzz, haltere, abdomen |
| 23B | excitatory | 7 | 0.762 | 11 | front, middle, hind, rep-legs, jump, wings, wing-buzz, haltere, abdomen | any, flex-held, ext-held, rep-legs, wings, wing-buzz | jump |
| 03B | inhibitory | 8 | 0.738 | 12 | weak | any, front, middle, hind, rep-legs, wings | jump, wing-buzz |
| 06B | inhibitory | 6 | 0.726 | 12.5 | silent (all 0) | any, rep-legs, wings | flex-held, ext-held, wing-buzz |
| 21A | inhibitory | 7 | 0.667 | 15 | weak | any, front, middle, hind, flex-held, rep-legs | jump |
| 05B | inhibitory | 10 | 0.655 | 15.5 | silent (all 0) | any, front, middle, hind, flex-held | ext-held, rep-legs, jump, wings, wing-buzz |
| 24B.25B | motor | 6 | 0.643 | 16 | flex-held | any, front, middle, hind, rep-legs, wings | - |
| 09A | inhibitory | 10 | 0.583 | 18.5 | silent (all 0) | any, front, middle, hind, flex-held, ext-held, rep-legs | jump, wings, wing-buzz |
| 13B | inhibitory | 8 | 0.583 | 18.5 | silent (all 0) | any, front, middle, hind, ext-held | jump, wings, wing-buzz |
| 12B | inhibitory | 8 | 0.560 | 19.5 | silent (all 0) | any, middle, hind, ext-held, rep-legs | flex-held, jump, wing-buzz |
| 08B | excitatory | 4 | 0.560 | 19.5 | silent (all 0) | any, jump | wings, wing-buzz |
| 11A | excitatory | 3 | 0.429 | 25 | weak | any, jump, wings | - |
| 06A | inhibitory | 9 | 0.369 | 27.5 | silent (all 0) | any, front, middle, hind, rep-legs, wings, wing-buzz | flex-held, ext-held |
| 19A | inhibitory | 9 | 0.357 | 28 | weak | any, middle, flex-held, rep-legs | front, hind, jump, wings, wing-buzz |
| 11B | inhibitory | 4 | 0.202 | 34.5 | silent (all 0) | any, wings, wing-buzz | jump |
| 14A | inhibitory | 6 | 0.202 | 34.5 | silent (all 0) | any, front, middle, hind, flex-held, rep-legs | - |
| 01B | inhibitory | 4 | 0.202 | 34.5 | silent (all 0) | any, front, middle, hind | - |
| 02A | inhibitory | 7 | 0.071 | 40 | ext-held | any, jump, wings, wing-buzz | flex-held, ext-held, rep-legs |

Every predicted value and observed cell for all 43 hemilineages: `results/run3/scorecard.csv`.

## Figures

- `results/run3/fig_scorecard.png`: the percentile rank of each scored hemilineage, coloured by class, with the permutation-null band.
- `results/run3/fig_matrix.png`: the predicted matrix (standardised per dimension) beside the observed one (yes, no, not coded), hemilineages in the same order.

## The three biggest caveats

1. **Wiring does as well, and what is identified is coarse.** The best synapse count matches the simulation, the class-shuffled networks keep most of the score, and the hemilineages ranked well are mostly excitatory ones predicted to move many body parts (exploratory split below). The simulated dynamics add nothing measurable on this test.
2. **The truth is thin, and the two labs disagree.** 27 hemilineages qualify, only 10 are coded on at least 3 dimensions by both labs, and on the 33 cells both labs code they agree at a kappa of 0.24. The label review (verdict: usable with caveats) found that a de-duplication step dropped 5 distinct Soffers experiments and that one Harris summary figure was read at low resolution. With the 15 affected coded cells removed (exploratory below), the result falls to 0.595 and its interval reaches below 0.5.
3. **It never names the right hemilineage.** Top-1 is 0 of 27 and top-3 is 2 of 27, both at chance. The predictions move the true hemilineage up the list without singling it out, and 18 of the 43 hemilineages have the same (silent) prediction.

## EXPLORATORY (after the unblinding; not pre-registered; none of this changes the verdict)

- **The headline ranks split by class** (the same ranks as the headline, not re-centred): excitatory 0.802 (11 hemilineages), inhibitory 0.508 (15), motor 0.643 (1). The excitatory hemilineages carry the result; the inhibitory ones sit at chance on average.
- **Label sensitivity.** `labels_h1/consensus_sensitivity.csv` was built before the flag: every cell the label review questions and every cell a dropped record codes differently is set to 'conflicting' (15 coded cells removed, still 27 hemilineages). Mean percentile rank 0.595, interval 0.489-0.696, p = 0.038, top-1 0.000, top-3 0.037. Under this consensus the "predicts" rule would not be met: the lower bound is below 0.5.
- **Leave one dimension out** (H-M, primary consensus): any visible movement 0.653, front legs move 0.639, middle legs move 0.635, hind legs move 0.641, legs flex / body lowers 0.612, legs extend / body rises 0.621, repeated leg movement 0.641, jump or takeoff 0.640, any wing movement 0.614, wing buzzing / flight-like 0.583, haltere movement 0.633, abdomen movement 0.633. Dropping wing buzzing / flight-like lowers the score most, to 0.583.
- **Code:** `ledger/scripts/posthoc/rescore_sensitivity.py` (written before the primary run, committed after it) -> `results/run3/exploratory.json`; `ledger/scripts/posthoc/results_h1.py` -> scorecard and figures (after the first render, the observed panel's colours were changed so that 'no' and 'not coded' differ; no number changed).
