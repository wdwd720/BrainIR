# Does a fly nerve-cord simulation agree with itself? A ten-minute brief (BrainIR prediction ledger, run 4)

## What was tested, and how

A model that simulates the fly's ventral nerve cord from its connectome (the published rate model behind the DNg100 walking result)
can screen every descending-neuron type: stimulate the type, ask whether the front-leg motor neurons become rhythmic. We used agreement
between a neuron's left and right copies, and between two flies (the MANC and MaleCNS connectomes), as a consistency check: if the
screen captures function shared by copies built by the same genome, the two should agree about as well as the screen agrees with
itself across random seeds. Real animals can differ between sides and individuals (DNg100 itself drives its legs asymmetrically, in the
authors' runs and ours), so a gap is a warning about the screen, not proof of an error.

The analyses, thresholds and pass/fail criteria were frozen before the data existed (`PREREG_v4.md`, tag `ledger-prereg-v4`,
timestamped in the Bitcoin blockchain). Seven departures are recorded (`AMENDMENTS_v4.jsonl`): three code fixes made before the
affected analyses ran, two cost settings, a timeout, and a budget-forced cut of the analysed types from 278 to 262; some planned analyses
were dropped under the pre-registered budget rule, and the one post-hoc figure below is marked. Simulations ran on GitHub and Modal after
both reproduced 100 locked jobs exactly, and 20 jobs of every campaign were re-run and matched digit for digit. No experimental label
entered the analyses of the screen; labels were used once, to turn scores into probabilities for the forward ledger. Agreement is a
Spearman correlation of type scores between two screens, read against a ceiling: how well each screen agrees with itself across seeds.

## Three results

**1. The authors' own published scores disagree between left and right.** In their single-neuron screen (128 replicates per neuron), a
neuron's left and right copies agree at **0.63** of the screen's agreement with itself (95 % interval 0.53-0.72); of 7 and 8 driver
types on the two sides, exactly one is a driver on both. *Caveat:* their screen stimulates one neuron and reads out both legs together.

**2. Our simulation shows the same gap in both flies, and a larger one for the same side across flies.** Left against right reaches
**0.59** (MANC) and **0.64** (MaleCNS) of the ceiling; the same side in the two flies 0.32-0.41 (opposite sides 0.32 and 0.50).
Type-level wiring summaries (direct and two-hop connections onto the leg motor neurons, outputs, member counts) correlate at 0.71-0.98,
but these deterministic correlations are on another scale, and single connections differ much more: about half of the connections
between matched neurons exist on one side only. *Caveat:* stimulating one side and reading that side is our procedure; result 1 shows
the gap without it.

**3. Poisson-scale noise in synapse counts is enough to move the screen about as much as the left-right difference does.** In MANC,
two copies of the network that differ only by Poisson noise in their raw synapse counts (before the 5-synapse floor) agree at 0.40
(Spearman; 0.48 of their ceiling), almost as poorly as left and right in the same paired design (0.37; 0.47 of the ceiling). No
parameter was fitted, and the pre-registered test was met (left-right minus copy-copy -0.03, interval -0.16 to +0.10). A post-hoc check
by the adversarial reviewer over all six pairings of the four stored noise copies (two Poisson, two negative-binomial) puts the
reproduced share at about 86 % (0.66-1.14, too narrow because it ignores variation between copies): most of the gap, not demonstrably
all. *Caveat:* this shows that noise of this size (a third of the connections change between two copies) suffices, not that the real
left-right differences are count noise; MANC only, because MaleCNS is published already floored.

## Why the two sides disagree, and what fixed it or did not

- **The procedure explains part at most.** Scoring the best of a fixed grid of currents instead of the tuner closes about a third of
  the gap in MaleCNS (0.36, interval 0.08-0.61) and an amount not distinguishable from 0 in MANC (0.17, -0.07 to 0.38). At matched
  currents the sides still disagree: at all 19 in MANC, and at the 12 MaleCNS currents where the comparison was conclusive.
- **Not one place in the network (MANC).** Mirroring only the stimulated neurons' own outputs closes 0.23 of the gap (-0.01 to 0.42),
  only the downstream network 0.34 (0.10 to 0.53); in MaleCNS 0.17 and 0.21, both intervals including 0. Mirroring both gives the other
  side's network, closing the gap by construction; the parts summing to about 0.57 shows they interact.
- **Partly small one-sided connections and unpartnered neurons (MANC).** Mirroring the connections that exist on one side only closes
  0.29 (0.06-0.49), neurons without a partner 0.25 (0.06-0.42); most one-sided connections have 1-4 synapses on the other side, below
  the floor. Homologous weights, size and sign alone close less (0.09, 0.03, -0.05) with wide intervals; the weights matter in
  combination, and the classes interact.
- **No fix worked.** Of the eight pre-registered fixes, six kept the DNg100 control and were judged on all four criteria (a dose sweep
  instead of the tuner, a pooled read-out, symmetrised weights, two type-pooled variants, consensus annotations); all failed, with the
  two flies at only 0.31-0.39 of the ceiling against 0.8 required. A lower floor could be tested only on MANC's left-right agreement
  (floor 1; floor 3 dropped for budget), input normalisation and the combination of network fixes broke the control, and the combined
  procedure-plus-network fix was not run. One criterion (at most 2 drivers in a rewired control) was set on another regime and was hard
  to meet, but every fix fails the agreement criterion anyway.

**What this work does not show.** It does not show that the two sides of a real fly behave differently, nor that the model is wrong
about DNg100's own walking circuit: it tests the model's screen of all descending-neuron types. Nothing here was tested in an animal.
The ceilings come from 8-16 random seeds, and most single-cause estimates have wide intervals.

## The decisive experiments, and the ask

The forward ledger (tag `ledger-forward-v1`) gives, for 63 descending-neuron types with a driver line and no clear label yet, the
probability of rhythmic front-leg stepping in a decapitated fly from two sources: the authors' model and two-step signed synapse counting
(no fix passed, so no third source). The probabilities come from a fit to the earlier exam's labels (training on past results) and are
weak: in leave-one-out tests the model is no better than the base rate (Brier 0.248 against 0.242; AUROC 0.33, below chance) and
counting only slightly better (0.239; AUROC 0.61). The fit set is 39 labelled types, most labelled in intact flies (21 of 25 "yes" from
one atlas), so probabilities for decapitated flies are extrapolations. They were made after the earlier exams were unblinded, but
before the experiments they predict.

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

Availability was looked up in the public catalogues (Janelia FlyLight, Bloomington, VDRC) on 2026-11-22 (`forward/AVAILABILITY.csv`).
For four of the 15 types (DNp34, DNp35, DNg87, DNad006) no line is listed as available, and ten of the "available" entries rest on a FlyBank status
page that was not tested by ordering.

**The ask.** Express CsChrimson under these lines (LexAop-CsChrimson for a LexA line), decapitate, feed all-trans-retinal, give 1-s
light pulses, and score rhythmic front-leg stepping blind to genotype. Each source will be scored by its Brier score against a
base-rate guesser.

## Where everything is

Repository branch `ledger/v1`, folder `research/ledger/`. Tags: `ledger-prereg-v4` (rulebook), `ledger-reliability-v2` (every result
above except the six-copy noise figure, which comes from the unlocked adversarial review `reviews_v4/ADVERSARIAL_REVIEW_v4.md`;
`LOCK_reliability_v2.json`), `ledger-forward-v1` (the forward ledger; `LOCK_forward_v1.json`). Full results: `results/RESULTS_3.md`;
every claim here is traced to its file in `EVIDENCE_MAP.md`; this brief's overclaim review: `reviews_v4/BRIEF_OVERCLAIM_REVIEW.md`.

![Agreement across sides and flies](results/run4/fig_agreement.png)
*Agreement of type scores between left and right (blue) and between the two flies (red), for the wiring, the unfixed model and each fix;
bars mark the matched ceiling (the screen against itself).*
