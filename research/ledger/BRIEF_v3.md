# What a third fly showed about a connectome simulation's hit list (BrainIR ledger, run 6)

## In one paragraph

A published rate model of the fly's nerve cord (Pugliese et al., 2026) screens descending-neuron types for rhythmic front-leg activity.
We ran it on a third animal's connectome (BANC, a female) that we had not screened before freezing our rules. **The gap between animals
was confirmed in the third animal**: BANC's cell-type scores agreed with the male nerve cord's (MANC) at 0.35 and with the male CNS's
(MaleCNS) at 0.50 of the agreement each screen has with itself, no lower than the two males' 0.31 (post hoc). The pre-registered caveat:
BANC's wiring of these types agrees with the other animals' less than the first two animals' wiring agreed (0.61-0.63 against 0.82), so
part of the gap may come from the build or the type match. Our current-setting procedure failed its positive control in BANC, so by the
rule fixed in advance the cross-animal tests used a current sweep; under it, our MANC and MaleCNS hits recurred in BANC above chance.
Hit lists depend on the procedure. In MaleCNS, our model reproduces the authors' DNg100 and single-DNb08 results.

## What was tested

Rules, sets and verdict words were frozen, hashed and timestamped before any BANC screen (`PREREG_v6.md`, tag `ledger-prereg-v6`), after a
fresh audit. Pre-registered: the eight tests on BANC and the check of our MaleCNS model. Everything about the first two animals' hit lists
is post hoc. DNg100 is never counted as evidence of replication: our procedure's one setting was chosen to make it a hit.

## Results (pre-registered words; DNg100 left out)

| Test | Words | Numbers |
|---|---|---|
| Left vs right copies in BANC | a real gap | 0.58 of the ceiling (0.38-0.77); MANC 0.59, MaleCNS 0.64 |
| Count noise in BANC | does not reproduce it | redrawn-count copies agree at 0.78; left vs right 0.58 |
| Agreement across animals | confirmed in the third animal (wiring caveat) | MANC-BANC 0.35 (0.20-0.49), MaleCNS-BANC 0.50 (0.38-0.62) |
| Our MANC hits in BANC | above chance | 5 of 17 recur (1.7 expected, p = 0.016); with DNg100, 6 of 18 |
| The authors' whole-type hits in BANC (our 0.5 cut) | at chance (see below) | 1 of 6 (0.6 expected, p = 0.47); with DNg100, 2 of 7 |
| Our MaleCNS hits in BANC | above chance | 12 of 60 recur (6.3 expected, p = 0.004); with DNg100, 13 of 61 |
| DNg100 in BANC (our procedure) | pass | 0.64; but 11 of 16 draws, short of the 12 needed to keep the procedure |
| Pooling two animals | not shown | beats MANC alone (+0.20), not MaleCNS alone (+0.02) |
| Animals needed (extrapolation) | (estimate) | about 7 (4.3 to 9.7) |
| Stability under count noise predicts BANC | predicts the third animal | Spearman 0.57, p = 0.029, 12 types (fragile: 10 near zero) |

"At chance" means the overlap could not be told apart from chance by this test, whose power is low; it does not show that the hits fail
to recur. The left-right and count-noise tests used the current-setting procedure, as pre-registered.

**Our MaleCNS model reproduces the authors' results.** At their configuration, one DNb08 neuron drives rhythm in 15 of 16 draws (mean
0.86; theirs 0.80) and DNg100 gives 0.985 (theirs 0.985). So the network can produce their result; our current-setting procedure missed it.

**DNb08 is not a hit in BANC**, as the authors report for their single neuron: whole type 0.00 (current-setting) and 0.25 (sweep); each
copy 0 of 16. **Under the sweep, four types are hits in all three animals** (post hoc): DNg100, DNxl134, DNa13 and DNxl092.

**Post hoc, first two animals:** at the authors' threshold the hit lists share 1 hit where 1.0 is expected (with DNg100,
2 of 11); at 0.3, 14 where 6 are expected (with DNg100, 15); under the sweep, 14 of 18 MANC hits recur in MaleCNS (with DNg100, 15 of
19). In the one interpretable literature test, the simulation added nothing
beyond the best of eight wiring counts.

## What holds up in the original work

The authors' rhythm circuit and its silencing results across four connectomes (our BANC build check re-ran their silencing, which
reproduced); DNg100 as a hit in all three networks under the sweep; DNb08 in three of four datasets;
their choice to follow up the two types whose every copy scored high; and their DNg100 and single-DNb08 results in MaleCNS, which our model
reproduces.

## What to test next

Twelve descending-neuron types to switch on in headless flies, scored blind for rhythmic front-leg stepping, with a decision rule fixed
in advance (`forward_v2/`): DNp71, DNa13, DNa07, DNa03, DNp41, DNp02, DNg63, DNg13, DNg21, and controls DNp07, DNg39, DNp26. DNa13 is a hit
in all three animals under the current sweep; DNg13 scores 0.94 to 0.98 in BANC.

## Caveats

- One model, one behaviour, three animals that also differ in sex and reconstruction; BANC's wiring agrees less with the others.
- The cross-animal tests rest on the current sweep, not the procedure the first two animals' hit lists came from.
- The positive stability result is one test of 12 types, with a predictor chosen after a nominal positive.

Files: `results/RESULTS_5.md`, `thirdfly_v1/C_tests.json`, `paper/PREPRINT_v1.md`. Tags: `ledger-prereg-v6`, `ledger-posthoc-v6`,
`ledger-thirdfly-v1`.
