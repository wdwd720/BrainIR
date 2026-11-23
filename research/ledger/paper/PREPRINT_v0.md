# How far can one connectome be trusted? Left-right, cross-animal and blind experimental tests of a simulated walking screen in *Drosophila*

**Title options.** (1) How far can one connectome be trusted? Left-right, cross-animal and blind experimental tests of a simulated walking
screen in *Drosophila* (chosen). (2) A connectome activation screen replicates across animals mainly for its experimentally supported
hits. (3) Synapse-count noise limits what a single-connectome activation screen can predict.

**Status.** Preprint draft v0. Every number comes from a file frozen by a lock (git tag, SHA-256, OpenTimestamps); `CLAIMS.md` lists
each claim with its file, field, tag and status. Results marked **post hoc** rest on a pattern seen before the rule that describes them.

## Abstract

Connectome-constrained simulations are increasingly used to choose which neurons to test. We asked how reliable such predictions are,
using the published rate-model screen of Pugliese et al. (2026) for descending neurons that drive rhythmic leg activity in *Drosophila*, in
a pre-registered prediction ledger. In the authors' own published screen, a neuron's left and right copies agree at 0.63 of the screen's
agreement with itself (95 % interval 0.53-0.72). Re-run on a second animal's connectome, hit lists barely overlap: of 11 hits with a
confidently matched counterpart, 2 are hits in the second animal, and those two are the paper's experimentally supported drivers, DNg100
and DNb08 (post hoc). Poisson-scale noise in synapse counts alone reproduces a left-right gap of the observed size. A pre-registered test of
whether stability under such noise predicts replication did not reach significance (p = 0.11; with three replicated types, this null is
uninformative). In two blind exams against published experiments, the screen did no better than counting two-step synaptic paths; an
audit of the exam labels upheld them, apart from an erratum for six excluded types, DNg100 among them. We pre-register a short list of
experiments and a rule for reading them.

## Introduction

Whole-nervous-system connectomes make it possible to simulate a circuit from its wiring and ask which neurons drive a behaviour.
Pugliese et al. (2026) built dynamic rate models of the *Drosophila* ventral nerve cord from its connectomes and ran a computational
activation screen of descending neurons (DNs), the brain's command lines to the cord. The screen identified DNg100, a known command neuron
for walking, as the strongest driver of rhythmic leg motor activity; simulated pruning isolated a three-neuron rhythm-generating circuit
that was necessary and sufficient in four connectome datasets; and the screen predicted that a second pathway, DNb08, drives rhythmic leg
movements, which the authors confirmed with optogenetics in behaving flies. A simulation pointed to a neuron, and the experiment agreed.

A screen of this kind is also a list of predictions about every type it stimulates, and that list is what a laboratory would use to choose
its next experiments. We asked how far the list can be trusted, through three properties. A hit should be robust to differences the
genome does not specify: a neuron's left and right copies are built by the same program. A hit should replicate in a second animal's
connectome. And the list should predict what happens when the same neurons are switched on in real flies, better than simpler readings of
the same wiring. We tested these properties in a prediction ledger: every analysis and criterion was written and frozen before the data
or simulations it concerned, every frozen file was hashed and timestamped, and the labels for two blind exams were collected from the
literature by separate readers who never saw a simulation score. The aim is to measure how reliable a single-connectome screen is, not to
judge the original work, whose two experimentally supported drivers, as shown below, are the hits that replicate.

## Results

### 1. Left and right copies disagree in the authors' own published screen

The authors' single-neuron screen (A0) stimulates each DN copy alone, 128 times, and reports a rhythm score for the front-leg motor
neurons. For the 250 types with exactly one copy on each side, the left copy's score predicts the right copy's with a Spearman correlation
of 0.597 across halves of the replicates, against a ceiling of 0.951 when each copy is compared with itself: **0.63 of the ceiling (95 %
interval 0.53-0.72), a real gap** by the pre-registered criterion (Fig. 1). Seven types are drivers (score at least 0.5) on one side and
eight on the other; one is a driver on both, and the three-way bands (driver, indeterminate, non-driver) agree with a kappa of 0.47. This comparison uses the authors' published numbers, not our reimplementation, but their
screen reads out both front legs together, so a one-sided input can reach either leg.

### 2. Two flies' hit lists barely overlap, though their wiring summaries agree

We reimplemented the screen, reproduced the authors' published dynamics, and ran it on two male connectomes: MANC (our rebuild, identical
to the authors' network) and MaleCNS (the authors' published network; they published no screen of it, so the MaleCNS screen is ours). Stimulating one side of each type and reading the same side (pre-registered), left agreed with
right at 0.59 of the ceiling in MANC (0.48-0.68) and 0.64 in MaleCNS (0.53-0.74). Across flies, agreement fell to 0.32-0.50, and for
whole-type screens to 0.38 (0.26-0.49) over 310 matched types (Fig. 3). The wiring itself agrees better: seven summaries of each type's
wiring to the motor neurons correlate at 0.71-0.98 between sides and flies (two-step signed paths 0.71-0.84), although about half of the
homologous neuron-to-neuron connections exist on one side only (51 % in MANC) and 58 % of type-to-type connections in one fly only.

The hit lists overlap little (**post hoc**: the thresholds below were chosen after the pattern was seen). Among the 215 types with a
high-confidence cross-fly match, MANC (B1r) has 11 drivers and MaleCNS (B2r) 23; two are drivers in both, against 1.2 expected if the
lists were independent (Fig. 2). Of MANC's hits, 0.18 replicate (2 of 11; 95 % interval 0.00-0.44); of MaleCNS's, 0.09. Comparing
half-screens with half-screens, so that noise is matched, the overlap across flies reaches 0.26 of the overlap within a fly (0.00-0.55;
overlap coefficient, which is not capped by unequal list sizes). Over all 310 matched types, including those whose match is low or medium
confidence, the same figures are 3 of 15 and 0.27 (0.04-0.53). The thresholds matter less than the pattern: the authors' own list (A1)
gives the same picture (2 of its 6 high-confidence hits replicate).

### 3. The hits that replicate include both experimentally confirmed drivers (post hoc)

With high-confidence matches, the replicated set is exactly **DNg100 and DNb08** (Fig. 2); over all matched types a third, DNit013, joins
them, on a match we rated low confidence before looking (its MaleCNS neuron is matched to MANC's DNit013 by body but annotated as DNit011). In the authors'
single-neuron screen, DNg100 and DNb08 are also the only two of 18 types with a driver copy, among 308 types with copies on both sides,
in which every copy is a driver. [[PART T]] This is fair to the original paper: its two experimentally supported drivers hold up across animals. It
is also post hoc and selected: we saw the pattern in a table after both exams were unblinded; DNg100 is the neuron the model was
calibrated on and built around; the authors chose DNb08 themselves; and two confirmed neurons are a tiny sample.

### 4. Synapse-count noise is enough to produce the gap; no simple fix closes it

Why do matched neurons disagree? In MANC, two network copies that differ only by Poisson resampling of every connection's synapse count
agreed with each other at 0.48 of the ceiling (0.36-0.60), against 0.47 (0.34-0.59) for left against right in the same design (Fig. 3).
Count noise of this size, with no fitted parameter, met the pre-registered test of reproducing the left-right gap; a post-hoc look at all
pairings of the stored copies suggests it explains most of the gap, not demonstrably all. It does not show that real left-right
differences are counting noise, only that noise of this size is enough. Transplanting the rest of the network from one side into the other
closed more of the gap (0.34 of it in MANC) than transplanting a type's own outputs (0.23), and no class of difference closed it alone;
the classes interact.
Eight pre-registered fixes to the procedure or network (dose sweeps, pooled read-outs, symmetrised or consensus networks, lower synapse
floors) were judged on agreement across flies, sides and hits; none passed: two broke the model's own DNg100 control, and those judged on
every criterion left the flies at 0.31-0.39 of the ceiling where 0.8 was required.

### 5. Stability under count noise does not demonstrably predict replication

If a hit flickers when synapse counts are re-rolled, it should not be expected to replicate in another animal; if that held, anyone with
one connectome could rank their hits. We tested this once, pre-registered. Sixteen Poisson copies of MANC's raw counts were screened with
the exact procedure of B1r (after a regression gate reproduced all 448 of B1r's stored results digest for digest). A driver's stability is
the fraction of copies in which it remains a driver. Among the 15 MANC drivers, the three that replicate in MaleCNS were not significantly
more stable than the rest (exact one-sided rank test, **p = 0.11**; 52 of 455 subsets as extreme): **not shown** (Fig. 4). DNg100 was a
driver in all 16 copies, DNit013 in 12 and DNb08 in 7, while three non-replicating hits (DNxl133, DNxl102, DNp02) were at least as stable
as DNit013. The repeat on the authors' 11-type list gave p = 0.27. The power statement fixed before the test applies: with three replicated
types the smallest attainable p is 0.002 and ties raise it, so this null is uninformative. Two sensitivity analyses on the mean score across
copies fell below 0.05 (0.035 and 0.033); they were pre-specified without words and are not a result. Noise rarely creates hits from
nothing: of 40 sampled types that are drivers in neither screen, 7 became drivers in at least one copy (26 of 640 type-copies, mostly
types already near the threshold), and none in half the copies.

### 6. Two blind exams: the simulation does no better than two-step synapse counting

Both exams compared frozen predictions with labels collected blind from the literature, and both included pre-registered wiring
baselines: counts of direct, two-step and three-step synaptic paths from the stimulated neurons to the motor neurons, signed or not,
computed without any simulation. **Exam 1** asked whether a type's simulated score
ranks types that drive rhythmic front-leg movement when switched on in flies above types that do not. On 39 labelled types (25 yes, 14
no), the authors' whole-type score reached an AUROC of **0.577 (0.417-0.724), not better than chance by the pre-registered rule**, and
counting signed two-step paths from the type to the front-leg motor neurons, with no simulation, reached 0.669. **Exam 2** asked whether
the model identifies which hemilineage was activated from the published movement phenotypes: it did better than chance (mean percentile
rank 0.633, 0.533-0.724, p = 0.008) but no better than two-step signed paths (0.638; difference -0.006, -0.172 to 0.166). Exam 2's two
source laboratories agree with each other only moderately (kappa 0.24 where both code a cell).

Exam 1's labels carry caveats. They were inferred from papers by language-model readers; 21 of the 39 types rest on a single intact-fly
optogenetic atlas; and types the readers had seen discussed alongside simulation scores were excluded ("exposed"), among them DNg100,
whose exam 1 label ("no rhythm in headless flies") looked wrong. A pre-registered **audit** re-read every source with fresh blind readers.
For DNg100, both forensic readers traced the "no" to one record of DNg100 activated together with a brake neuron, coded as more
line-specific than two plain DNg100 records; the consensus rule then let it decide, after the blind rule had set aside 23 concordant
records from the simulation papers. The audited label is **yes**. Across all 39 exam types the audit found 3 errors (7.7 %; sample of 15:
1 error), below the 10 % threshold fixed in advance, and no systematic fault, so exam 1 stands, with an erratum for six exposed types.
Recomputed with audited labels (exploratory), the AUROC is 0.559, and two-step counting 0.713.

### 7. Forward predictions

We locked a forward ledger of experiments that have not been done, built on replication status. A candidate type is in a replication
category, has a driver line in the labelling kit, and had not been tested in headless flies according to the audit or exam 1. Three
readings give each candidate yes or no for rhythmic front-leg stepping when it is switched on in a decapitated fly: the **replication
reading** (replicated or near-replicated types yes), the **single-connectome reading** (the authors' A1 hits yes) and the **counting
reading** (the top third of two-step signed counts yes). The short list (Table 1) holds 12 types, each with at least one line listed as
available on the day of the lookup (58 of the 78 lines checked):

| Group | Types | Replication / single-connectome / counting |
|---|---|---|
| near-replicated | DNp71, DNa13, DNa07, DNa03 | yes / no (DNa07: yes) / DNp71 yes, others no |
| single-fly hit, MANC (DNp41 on the authors' list) | DNp41, DNp02, DNg63 | no / DNp41 yes, others no / DNp41 and DNg63 yes |
| single-fly hit, MaleCNS | DNg13, DNg21 | no / no / yes |
| controls: non-driver in both flies, high counting | DNp07, DNg39, DNp26 | no / no / yes |

The decision rule was fixed before any experiment: for two readings, take the tested types with a clear outcome on which they disagree;
one reading is supported over the other if it is right on enough of them for a one-sided binomial test at 0.05. On this list the
replication and single-connectome readings disagree on only four types, so that comparison can only be inconclusive; we say so in
advance rather than discover it later. The informative comparisons are against counting: replication against counting on up to 10
types (9 right needed; power 0.38 or 0.74 if the better reading is right on 80 or 90 % of types) and single-connectome against counting on
up to 8 (7 right needed; power 0.50 or 0.81). Two caveats bear on the lines: both of DNp41's available lines also label another DN type,
one of them DNg100, and DNa03's only line labels six other types.

## Discussion

A single-connectome activation screen carries a real signal: the model's strongest hit is a known walking command neuron, its novel
prediction was confirmed in flies, and both replicate across animals. Beyond those, its hit list is fragile. Copies of a neuron on two
sides of one animal disagree; the same type in two animals disagrees more; and resampling synapse counts at Poisson scale moves the screen
about as much as the left-right difference does. In blind tests against published experiments, the simulation's ranking of types did not
beat a count of two-step synaptic paths.

These results bear on type-level hit lists, not on every claim a connectome simulation can make. The original paper's central circuit
claim, a three-neuron rhythm generator found by pruning, was tested by its authors across four connectome datasets, which is the kind of
cross-animal check this work argues for; we did not re-test it. The fragility we measured sits in which of many weakly driving types
cross a threshold, where small differences in wiring move a type from one side of the line to the other.

For anyone simulating a single connectome, three practices follow. Report each hit's behaviour on matched copies (the other side, and
another animal where one exists) before calling it a prediction. Report its stability under synapse-count noise; our test could not show
that stability predicts replication, so it is a cheap screen for fragility, not a substitute for a second connectome. And compare with
wiring counts, which in both exams did as well as the simulation.

What this work does not show: that a real fly's left and right copies behave differently; that the model is wrong about DNg100's own
circuit or the three-neuron rhythm generator, which we did not test; or anything about other behaviours or models. Whether replication
across connectomes picks out real drivers is the question the forward list is built to answer; as designed, it can say whether replication
or the single-connectome list beats wiring counts, but not, with the available lines, which of the two is better.

## Limitations

- One model and one behaviour: a rate model of rhythmic front-leg activity, scored by the authors' rhythmicity measure.
- Two animals, both male; the MaleCNS screen is our run of our reimplementation on the authors' MaleCNS network (the authors published
  none), and the MANC network is our rebuild (identical to theirs).
- Cross-fly type matching is imperfect: 82 of 328 MaleCNS types have a low-confidence match; we lead with high-confidence matches.
- Everything in Results 2-3 that uses the hit-list categories is post hoc; the replicated set includes the neuron the model was
  calibrated on and a neuron the authors chose.
- Part S's null is uninformative by construction (three replicated types).
- The exam labels were inferred from papers by language-model readers of one model family, with a consensus rule whose tie-breaks decide
  30 of the 54 audited labels; DNg100's label was wrong; one of the three audit errors comes from the audit's own scope rule.
- Exam 2's two laboratories disagree with each other, so its ceiling is low.
- Count noise sufficing to produce the gap does not identify the gap's cause.
- The tuner was calibrated once on DNg100, and our screens read out one side's motor neurons where the authors' single-neuron screen
  reads both; our reimplementation reproduces the authors' published dynamics, but any procedure is one choice among several.
- Two of the short list's types can only be tested with lines that also label other DN types (DNp41, DNa03).

## Methods

**Ledger.** Five runs (19-23 November 2026), each governed by a rulebook frozen before the data or simulations it concerned (PREREG v1-v5).
A freeze is a lock file listing the SHA-256 of every rulebook, input, output and code file it binds, chained to earlier locks, committed,
tagged, pushed and timestamped with OpenTimestamps. Locked files are never edited; later code changes are recorded as amendment rows
before they are committed.

**Screens.** BrainIR reimplements the authors' rate model and reproduces their published dynamics. A screen stimulates a type's members
(or one side's), tunes the current per replicate with a fixed procedure calibrated once on DNg100, and scores the front-leg motor neurons'
rhythmicity; a type's score is the mean over usable replicates, a driver scores at least 0.5. Agreement is the Spearman correlation of
type scores across halves of the seeds, divided by the split-half ceiling, with 10,000-resample bootstrap intervals over types.

**Replication (post hoc).** Types are matched across flies by the curated body match of each MaleCNS neuron to a MANC neuron, falling
back on the annotated MANC type name; a match is high confidence when every member is body-matched, no body match conflicts with the name
and naming is one-to-one (a rule fixed before the replication analysis). Categories use a driver threshold of 0.5 and the bands 0.3 and
0.05. Overlap uses replication rates (the share of one list's hits that are hits in the other), the overlap coefficient (shared hits over
the shorter list), whose cross-fly value on matched halves of the seeds is compared with each fly's split-half value, and the Jaccard
index with its maximum for the list sizes; intervals are 95 % percentile intervals over 10,000 resamples of types.

**Count-noise stability (pre-registered).** Sixteen Poisson draws of every connection's raw synapse count in MANC (fixed seeds), each
thresholded at 5 synapses after resampling and signed by the presynaptic neuron's predicted transmitter, were screened with B1r's exact
job specification on 8 seeds. A type's copy score is its mean over usable seeds; its stability is the fraction of copies in which that
score is at least 0.5. The test ranks the 15 B1r drivers by stability (midranks for ties) and counts, over all 455 subsets of three, those
whose rank sum is at least that of the three replicated types. Sensitivity analyses and a reference test on the real network's score were
fixed in advance without words.

**Labels and exams.** Exam labels were collected from a registry of 96 published sources by language-model reader sessions in isolated
rooms, with two readings, adjudication, quote checks by the second readers and transcript audits for breaches, and frozen before unblinding; predictions were frozen
separately. The audit used fresh sessions in isolated rooms (checked by a canary and by transcript audits), two independent readers per source,
adjudication of disagreements, the atlas re-coded with exam 1's own procedure, and verification of unclear outcomes, under rules and a
consequence fixed before it began; its error rate counts a clear audited label that differs from exam 1's, a non-clear one that a
verifier did not confirm, or an unread type.

**Compute.** Simulations ran on GitHub Actions under a trust gate (locked jobs reproduced exactly) with determinism re-runs of every
campaign; run 4 also used Modal at the author's instruction.

## Disclosure

The analyses were designed with, and run by, AI agents (Anthropic's Claude models; Claude Opus 5.5 in this run, as orchestrator,
reviewers and label readers) under the author's direction. The author set the questions and the rules for each run; the agents wrote the
code, ran the analyses and drafted this text. Every review was done by a newly started agent.

## Data and code

Branch `ledger/v1` of the BrainIR repository; tags `ledger-prereg-v1` to `ledger-prereg-v5`, `ledger-pertype-v1`,
`ledger-replication-v1` and `ledger-forward-v2`. Figures are drawn by `ledger/scripts/posthoc/paper_figures_v5.py` from locked files.

**Figures.** Fig. 1: left against right copy in the authors' single-neuron screen (250 types). Fig. 2 (post hoc): whole-type scores in
MANC against MaleCNS, 215 high-confidence types, by category. Fig. 3: agreement as a fraction of the ceiling, with 95 % intervals.
Fig. 4: stability of each driver across 16 Poisson copies.
