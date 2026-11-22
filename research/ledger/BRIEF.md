# Does a fly nerve-cord simulation agree with itself? A ten-minute brief (BrainIR prediction ledger, run 4)

## What was tested, and how

A model that simulates the fly's ventral nerve cord from its connectome (the published rate model behind the DNg100 walking result) can
be used to screen every descending-neuron type: stimulate the type, ask whether the front-leg motor neurons become rhythmic. We asked a
question with a known answer. A neuron's left copy and right copy are built by the same genome and do the same job, so a correct
screen must give them the same prediction, and the same in two different flies (the MANC and MaleCNS connectomes).

Every analysis, threshold and pass/fail criterion was written down and frozen before the data existed (`PREREG_v4.md`, git tag
`ledger-prereg-v4`, timestamped in the Bitcoin blockchain with OpenTimestamps). Simulations ran on GitHub's servers and on Modal after both
reproduced 100 locked jobs exactly; samples of every campaign were re-run and matched digit for digit. No experimental label shaped any
analysis. Agreement is always measured against a matched ceiling: how well the same screen agrees with itself across random seeds.

## Three results

**1. The authors' own published scores disagree between left and right.** In their single-neuron screen (128 replicates per neuron), a
neuron's left and right copies agree at **0.63** of the level at which the screen agrees with itself (95 % interval 0.53-0.72), and only
about one driver in seven or eight is a driver on both sides. *Caveat:* their screen stimulates one neuron and reads out both front legs together.

**2. Our simulation shows the same gap on both sides of both flies, and a larger one between flies, while the wiring agrees.** Left
against right reaches **0.59** (MANC) and **0.64** (MaleCNS) of the ceiling; the same side in the two flies 0.32-0.41. Summaries of the wiring itself
(direct and two-hop connections onto the leg motor neurons, outputs, member counts) agree at 0.71-0.98. *Caveat:* stimulating one side and reading out that side is our procedure; result 1
shows the gap without it.

**3. Noise in synapse counts produces most of the gap.** Two copies of the MANC network that differ only by Poisson noise in their raw
synapse counts (before the 5-synapse floor) agree with each other at **0.40**, almost as poorly as the left and right sides (0.37). No
parameter was fitted. An adversarial check found this pre-registered pair to be a low draw: over all six pairings of the four stored
noise copies, noise reproduces about 86 % of the gap. *Caveat:* this shows that Poisson-scale count noise (a third of the connections change between two copies) suffices for
most of a gap this large, not that the real left-right differences are count noise; it is MANC only, because MaleCNS is published already floored.

## Why the two sides disagree, and what fixed it or did not

- **Not mainly the screen's procedure.** Where the current tuner lands explains at most about a third of the gap (MaleCNS 0.36; MANC
  0.17, not distinguishable from 0), and the sides disagree at every fixed current.
- **Not one place in the network.** Mirroring only the stimulated neurons' own outputs closes 0.23 of the MANC gap, only the downstream
  network 0.34; together they close all of it, so the parts interact.
- **Mostly small, one-sided connections.** About half of the connections between matched neurons exist on one side only, most with 1-4
  synapses on the other side, below the floor. Mirroring those connections alone closes 0.29 of the gap, neurons without a partner 0.25;
  weights, size and sign matter little on their own.
- **No fix worked.** Eight parameter-free fixes, fixed in advance, were tested against four pre-registered criteria
  (a lower floor, symmetrised or type-pooled weights, input normalisation, consensus annotations, all of these together, a dose sweep
  instead of the tuner, a pooled read-out). None restores
  reproducibility: whenever the DNg100 control still works, the two flies agree at only 0.31-0.39 of the ceiling, far below the 0.8
  required. Two fixes broke the DNg100 control.

**What this work does not show.** It does not show that the two sides of a real fly behave differently, nor that the model is wrong
about DNg100's own walking circuit: it tests the model's screen of all descending-neuron types. Nothing here was tested in an animal.
The ceilings come from 8-16 random seeds, and most single-cause estimates have wide intervals.

## The decisive experiments, and the ask

The forward ledger (tag `ledger-forward-v1`) gives, for 63 descending-neuron types that have a driver line and no clear label yet, the
probability of rhythmic front-leg stepping in a decapitated fly from two sources: the authors' model and two-step signed synapse
counting (no fix passed, so there is no third source). The probabilities come from a fit to the earlier exam's labels (training on past
results), and they are weak: in leave-one-out tests the model is no better than guessing the base rate (Brier 0.248 against 0.242) and
counting only slightly better (0.239). These predictions were made after the earlier exams were unblinded, but before the experiments
they predict.

| type | driver lines (listed as available) | P(rhythmic): authors' model | P(rhythmic): two-step counting |
|---|---|---|---|
| DNg43 | 2 of 4: SS66182, SS68371 | 0.72 | 0.44 |
| DNp56 | 1 of 2: SS88245 | 0.76 | 0.50 |
| DNg32 | 1 of 1: R50E12 | 0.59 | 0.80 |
| DNp34 | 0 of 3 | 0.59 | 0.80 |
| DNp45 | 1 of 1: SS81831 | 0.59 | 0.76 |
| DNp35 | 0 of 2 | 0.59 | 0.45 |
| DNp26 | 7 of 10: R29G08, SS01553, SS01588 +4 more | 0.69 | 0.81 |
| DNg87 | 0 of 1 | 0.70 | 0.80 |
| DNad006 | 0 of 1 | 0.59 | 0.69 |
| DNg91 | 3 of 4: SS58304, SS94997, SS95034 | 0.59 | 0.68 |
| DNp31 | 8 of 8: R58E07, SS00733, SS02621 +5 more | 0.59 | 0.50 |
| DNg78 | 5 of 11: SS13337, SS72084, SS88264 +2 more | 0.59 | 0.65 |
| DNg39 | 2 of 6: SS64882, SS70659 | 0.76 | 0.82 |
| DNp44 | 2 of 2: SS64688, SS66153 | 0.68 | 0.73 |
| DNp15 | 2 of 4: SS01556, SS12653 | 0.59 | 0.54 |

Availability was looked up in the public catalogues (Janelia FlyLight, Bloomington, VDRC) on 2026-11-22; each line's collection and URL are in `forward/AVAILABILITY.csv`.

**The ask.** Express CsChrimson under these lines (LexAop-CsChrimson for a LexA line), decapitate, feed all-trans-retinal, give 1-s
light pulses, and score rhythmic front-leg stepping blind to genotype. Each source will be scored by its Brier score against a base-rate
guesser.

## Where everything is

Repository branch `ledger/v1`, folder `research/ledger/`. Tags: `ledger-prereg-v4` (rulebook), `ledger-reliability-v2` (all results
above; `LOCK_reliability_v2.json`), `ledger-forward-v1` (the forward ledger; `LOCK_forward_v1.json`). Full results: `results/RESULTS_3.md`;
every claim here is traced to its locked file in `EVIDENCE_MAP.md`.

![Agreement across sides and flies](results/run4/fig_agreement.png)
*Agreement of type scores between left and right (blue) and between the two flies (red), for the wiring, the unfixed model and each fix;
bars mark the matched ceiling (the screen against itself).*
