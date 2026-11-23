# What a third fly showed about a connectome simulation's hit list (BrainIR ledger, run 6)

## In one paragraph

A published rate model of the fly's nerve cord (Pugliese et al., 2026) screens descending-neuron types for rhythmic front-leg activity.
We ran it on a third animal's connectome (BANC, a female) that we had not examined before freezing our rules. **The gap between animals
was confirmed in the third animal**: BANC's cell-type scores agreed with the male nerve cord's (MANC) at 0.35 and with the male CNS's
(MaleCNS) at 0.50 of the agreement each screen has with itself, against 0.31 for the two males on the same 181 types. A pre-registered
caveat applies: BANC's wiring of these types also agrees less with the other two (0.61-0.63, against 0.82 between them). Our current-setting
procedure failed its positive control in BANC, so by the rule fixed in advance the tests used a current sweep. Under it, our MANC and
MaleCNS hits recurred in BANC above chance; the authors' six hits recurred at chance (1 of 6). Our model reproduces the authors' DNg100
and single-DNb08 results.

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
| Our MANC hits in BANC | above chance | 5 of 17 recur (1.7 expected, p = 0.016) |
| The authors' hits in BANC | at chance (low power) | 1 of 6 (0.6 expected, p = 0.47) |
| Our MaleCNS hits in BANC | above chance | 12 of 60 recur (6.3 expected, p = 0.004) |
| DNg100 in BANC (our procedure) | pass | 0.64; but 11 of 16 draws, short of the 12 needed to keep the procedure |
| Pooling two animals | not shown | beats MANC alone (+0.20), not MaleCNS alone (+0.02) |
| Animals needed (extrapolation) | (estimate) | about 7 (4.3 to 9.7) |
| Stability under count noise predicts BANC | predicts the third animal | Spearman 0.57, p = 0.029, 12 types (fragile: 10 near zero) |

**Our MaleCNS model is the authors' model.** At their configuration, one DNb08 neuron drives rhythm in 15 of 16 runs (theirs 0.80) and
DNg100 gives 0.98 (theirs 0.985). Our earlier failure to see single-DNb08 rhythm came from our current-setting procedure.

**DNb08 does not drive rhythm in BANC**, as the authors report: whole type 0.00, each copy 0 of 16.

**Post hoc, first two animals:** at the authors' threshold the hit lists share 1 hit where 1.0 is expected; at 0.3, 14 where 6 are
expected; under the sweep, 14 of 18 MANC hits recur in MaleCNS. Against published experiments, the simulation matched the best wiring
count and did not beat it.

## What holds up in the original work

The authors' rhythm circuit and its silencing results across four connectomes (we did not re-test them); DNb08 in three of four datasets;
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
