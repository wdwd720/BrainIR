# Does a fly nerve-cord model agree with itself? (BrainIR ledger, run 4)

## What was tested, and how

A published rate model built from the fly's nerve-cord connectome screens descending-neuron types: stimulate a type, ask whether the
front-leg motor neurons become rhythmic. If the screen captures function shared by copies built by the same genome, a type's left and
right copies, and the same type in two flies (MANC and MaleCNS), should agree about as well as the screen agrees with itself across
seeds (the ceiling; agreement is the Spearman correlation of type scores). Sides, flies and the connectomes' reconstruction and
annotation can differ, so a gap is a warning about the screen, not proof of an error.

Analyses and criteria were frozen before any simulation of this run (`PREREG_v4.md`, Bitcoin-timestamped), though both gaps had been
seen in an earlier run whose MANC seeds Part A reuses (rulebook Part Q); result 1 had not. Departures are recorded in
`AMENDMENTS_v4.jsonl`, and a pre-registered budget rule dropped some analyses. No exam label entered Parts A-C (the fixes were
calibrated on DNg100 only); labels set the forward probabilities and, exploratorily, re-scored an earlier exam.

## Three results

**1. The authors' own published scores disagree between left and right:** a neuron's left and right copies agree at **0.63** of the
ceiling (95 % interval 0.53-0.72). *Caveat:* their screen reads out both legs together.

**2. Our simulation shows a similar gap in both flies, and a larger one across flies:** left against right **0.59** (MANC) and 0.64
(MaleCNS) of the ceiling, across flies 0.32-0.50, and the flies' left-right differences are not shared (same-side pairs agree no better
than opposite-side ones). *Caveat:* stimulating one side and reading it out is our procedure; result 1 shows the gap without it.

**3. Poisson-scale noise in synapse counts moves the screen almost as much as the left-right difference does:** in MANC, two network
copies differing only by such noise agree at **0.48** of their ceiling, left and right 0.47 in the same design (result 2 used another):
with no fitted parameter, the pre-registered test is met. A post-hoc check of other copies (under no lock) suggests most of the gap, not
demonstrably all. *Caveat:* noise of this size suffices, which does not make the real differences count noise; MANC only.

## Why the two sides disagree, and what fixed it or did not

Scoring the best of a fixed grid of currents instead of the tuner closes 0.36 of the gap in MaleCNS (0.08-0.61) and 0.17 in MANC (-0.07
to 0.38), partly by lowering seed noise (against its own ceiling, MaleCNS agreement rises only from 0.58 to 0.65). In MANC, mirroring
one-sided connections closes 0.29 (0.06-0.49) and unpartnered neurons 0.25 (0.06-0.42); no single class closes the gap. **No fix
worked:** of the ten variants of fixes 1-8, six were judged on all four criteria and failed (flies at 0.31-0.39 of the ceiling; 0.8
required); two broke the DNg100 control, one floor was judged on MANC only and one dropped for budget; fix 9 (combined) was not run.

**What this work does not show:** that a real fly's sides behave differently, or that the model is wrong about DNg100's own circuit;
nothing was tested in an animal. It covers excitatory descending-neuron types whose two copies are annotated homologs (MANC 307 of 321,
MaleCNS 219 of 328; the causes and fixes used a budget-cut subset).

## The decisive experiments, and the ask

For 63 unlabelled types with a driver line, the forward ledger gives the probability of rhythmic front-leg stepping in a decapitated fly
from two sources, because no fix passed: the authors' model and two-step signed counting. Fitted to earlier exam labels (training on
past results), mostly from intact flies, these are weak extrapolations (leave-one-out Brier 0.248 and 0.239, base rate 0.242; AUROC
0.33, below chance, and 0.61), made before the experiments they predict. The 15 where they disagree most, by only 0.05-0.28:

| type | model (score) | counting | lines | type | model (score) | counting | lines |
|---|---|---|---|---|---|---|---|
| DNg43 | 0.72 (0.04) | 0.44 | 2 of 4 | DNad006 | 0.59 (0.00) | 0.69 | 0 of 1 |
| DNp56 | 0.76 (0.13) | 0.50 | 1 of 2 | DNg91 | 0.59 (0.00) | 0.68 | 3 of 4 |
| DNg32 | 0.59 (0.00) | 0.80 | 1 of 1 | DNp31 | 0.59 (0.00) | 0.50 | 8 of 8 |
| DNp34 | 0.59 (0.00) | 0.80 | 0 of 3 | DNg78 | 0.59 (0.00) | 0.65 | 5 of 11 |
| DNp45 | 0.59 (0.00) | 0.76 | 1 of 1 | DNg39 | 0.76 (0.12) | 0.82 | 2 of 6 |
| DNp35 | 0.59 (0.00) | 0.45 | 0 of 2 | DNp44 | 0.68 (0.01) | 0.73 | 2 of 2 |
| DNp26 | 0.69 (0.01) | 0.81 | 7 of 10 | DNp15 | 0.59 (0.00) | 0.54 | 2 of 4 |
| DNg87 | 0.70 (0.02) | 0.80 | 0 of 1 |  |  |  |  |

*Model:* the authors' screen score (bracketed) through the fit; 9 of the 15 score 0 (no rhythm), mapped to 0.59, near the base rate
(0.64), and none is a driver (highest 0.13), so for them the Brier comparison tests calibration, not the screen. *Lines:* listed as
available on 2026-11-22 (none for four types; `forward/AVAILABILITY.csv`); ten rest only on an untested FlyBank status page, and seven
have at least one kit record naming another descending-neuron type (`kit_v2/driver_lines.csv`), so a positive from them may be joint
activation.

**The ask:** express CsChrimson under these lines, decapitate, feed all-trans-retinal, give 1-s light pulses, score front-leg rhythm
blind to genotype; sources are scored by Brier score against a base-rate guesser.

**Where everything is:** branch `ledger/v1`, `research/ledger/`; tags `ledger-prereg-v4`, `ledger-reliability-v2`, `ledger-forward-v1`,
`ledger-labels-v2`, each with a `LOCK_*.json`; `EVIDENCE_MAP.md` traces each claim and marks what is unlocked; results in
`results/RESULTS_3.md`.

![Agreement across sides and flies](results/run4/fig_agreement.png)
*Raw Spearman agreement (not the ratios above): left vs right (blue), across flies (red); bars mark ceilings.*
