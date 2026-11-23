# How far can a simulation of one connectome be trusted? Left-right, cross-animal and blind literature tests of a walking screen in *Drosophila*

**Title options.** (1) How far can a simulation of one connectome be trusted? Left-right, cross-animal and blind literature tests of a
walking screen in *Drosophila* (chosen). (2) In one model's activation screen, the two experimentally supported hits replicate across two
connectomes (post hoc). (3) Poisson-scale synapse-count noise reproduces a simulated screen's left-right gap.

**Status.** Preprint draft v0, revised after three reviews (`reviews_v5/PAPER_*`). Every number about our work comes from a file frozen by
a lock (git tag, SHA-256, OpenTimestamps) or, for the exam results, by a tagged and timestamped commit; statements about the original
paper cite it. `CLAIMS.md` lists each claim with its file, field, tag and status. Results marked **post hoc** rest on a pattern seen
before the rule that describes them.

## Abstract

Connectome-constrained simulations can suggest which neurons to test. We asked how far such suggestions can be trusted, using the
rate-model screen of Pugliese et al. (2026) for descending neurons that drive rhythmic leg activity in *Drosophila*, in a ledger of
analyses frozen and timestamped before they ran. In the authors' published screen, a neuron's left and right copies agree at 0.63 of the
screen's agreement with itself (95 % interval 0.53-0.72). Our reimplementation shares 10 of their 11 hits in the first connectome, but in
a second connectome few recur (post hoc): of 11 confidently matched hits, 2 do, the paper's experimentally supported drivers DNg100, whose
replication our calibration guarantees, and DNb08. In the first connectome, Poisson-scale noise in synapse counts reproduces the
left-right gap. A pre-registered test of whether stability under such noise predicts replication was not significant (p = 0.11;
uninformative with three replicated types). In two blind exams against published experiments, the model did no better than counting
two-step synaptic paths, although exam 1's labels are confounded with their sources; an audit upheld them, with an erratum for six excluded
types. We pre-register 12 experiments and a rule for reading them.

## Introduction

Whole-nervous-system connectomes make it possible to simulate a circuit from its wiring and ask which neurons drive a behaviour.
Pugliese et al. (2026) built dynamic rate models of the *Drosophila* ventral nerve cord from its connectomes and ran a computational
activation screen of descending neurons (DNs), the brain's command lines to the cord. In their account, the screen identified DNg100, a
known command neuron for walking, as the strongest driver of rhythmic leg motor activity; simulated pruning isolated a three-neuron
rhythm-generating circuit that was necessary and sufficient in four connectome datasets; and the screen predicted that a second pathway,
DNb08, drives rhythmic leg movements, which they confirmed with optogenetics in behaving flies. A simulation pointed to a neuron, and the
experiment agreed. The authors present the screen as a tool for discovery rather than a complete classification of every type.

A screen of this kind is also a list of predictions about every type it stimulates, and that list is what a laboratory might use to choose
its next experiments. We asked how far the list can be trusted, through three properties. If the screen captures function shared by a
neuron's left and right copies, which are built by the same program, a hit should hold on both sides. A hit should replicate in a second
animal's connectome. And the list should predict what happens when the same neurons are switched on in real flies, better than simpler
readings of the same wiring. We tested these properties in a prediction ledger: most analyses and criteria were frozen before the data
or simulations they concerned, the rest are marked post hoc or exploratory, every frozen file was hashed and timestamped, and the labels
for two blind exams were collected from the literature by separate readers who never saw our predictions, with records next to a printed
simulation score set aside. The aim is to measure how reliable a single-connectome screen is, not to judge the original work, whose two
experimentally supported drivers are, post hoc, the hits that replicate among confidently matched types.

## Results

### 1. Left and right copies agree only partly in the authors' own published screen

The authors' single-neuron screen (A0) stimulates each DN copy alone, 128 times, and reports a rhythm score for the front-leg motor
neurons of both sides. For the 250 types with exactly one copy on each side, the left copy's score predicts the right copy's with a
Spearman correlation of 0.597 across halves of the replicates, against a ceiling of 0.951 when each copy is compared with itself: **0.63 of
the ceiling (95 % interval 0.53-0.72), a real gap** by the pre-registered criterion (Fig. 1). Seven types are drivers (score at least 0.5)
on one side and eight on the other; one is a driver on both, and the three bands (driver, indeterminate, non-driver) agree with a kappa of
0.47. This comparison uses the authors' published numbers, not our reimplementation; their screen reads out both front legs together, so a
one-sided input can reach either leg.

### 2. Simulated hit lists of two connectomes barely overlap (post hoc), though their wiring summaries agree

We reimplemented the screen, which reproduces the authors' published dynamical results; on MANC our whole-type screen (B1r) shares 10 of
the authors' 11 hits (A1) and adds 5. We ran it on two male connectomes: MANC (our rebuild, identical to the authors' network) and
MaleCNS (the authors' published network; they published no screen of it, so the MaleCNS screen, B2r, is ours). Stimulating one side of
each type and reading the same side (pre-registered, though an earlier run had already seen both gaps), left agreed with right at 0.59 of
the ceiling in MANC (0.48-0.68) and 0.64 in MaleCNS (0.53-0.74). Across flies, agreement fell to 0.32-0.50, and for whole-type screens to
0.38 (0.26-0.49) over 310 matched types (Fig. 3). Wiring agrees better: seven summaries of each type's wiring correlate at 0.71-0.98 between
sides and flies (the four counted to the motor neurons, 0.71-0.96), although about half of homologous neuron-to-neuron connections pass the
5-synapse floor on one side only (51 % in MANC; two thirds of these have 1-4 synapses on the other side) and 58 % of type-to-type
connections appear in one fly only.

The hit lists overlap little (**post hoc**: the thresholds below were chosen after the pattern was seen). Among the 215 types with a
high-confidence cross-fly match, B1r has 11 drivers and B2r 23; two are drivers in both, against 1.2 expected if the lists were independent
(Fig. 2). Of B1r's hits, 0.18 replicate (2 of 11; 95 % interval 0.00-0.44); of B2r's, 0.09. Comparing half-screens with half-screens, so
that noise is matched, the overlap across flies reaches 0.26 of the overlap within a fly (0.00-0.55; overlap coefficient, which is not
capped by unequal list sizes). Over all 310 matched types, including those whose match is low or medium confidence, the figures are 3 of
15 and 0.27 (0.04-0.53). At the same thresholds the authors' own list gives a similar picture: 2 of its 6 high-confidence hits replicate.
We did not vary the thresholds; a reviewer found that the overlap rises at lower ones (post hoc, not locked).

### 3. The hits that replicate include both experimentally confirmed drivers (post hoc)

With high-confidence matches, the replicated set is exactly **DNg100 and DNb08** (Fig. 2); over all matched types a third, DNit013, joins
them, only under the calibrated procedure and on a match rated low confidence by a rule written after the replication pattern was known (its MaleCNS neuron is matched to MANC's
DNit013 by body but annotated as DNit011). **DNg100's replication is not independent evidence:** our tuner's one free setting was chosen,
before any other neuron was run, as the smallest that makes DNg100 a driver in both connectomes; under the original procedure DNg100 was not
a driver in MaleCNS. DNb08, which the rulebook named in advance as the non-tautological check, is the informative case, and it is a
whole-type hit in both connectomes. In the authors' single-neuron screen, DNg100 and DNb08 are the only two of the 308 types with copies on
both sides whose every copy is a driver. Stimulating single copies with our procedure (descriptive), DNg100's copies drive rhythm in both
flies, while none of DNb08's four MaleCNS copies does so alone (scores 0.00-0.48), although its whole type does. The authors chose DNg100
and DNb08 to test, and our results support that choice: their two experimentally supported drivers remain hits in the second connectome.
The selection caveats stand: we saw this pattern after both exams were unblinded; DNg100 is the neuron our tuner was calibrated on and the
authors' model was built around; the authors chose DNb08; and two neurons are a tiny sample.

### 4. In MANC, synapse-count noise reproduces the left-right gap; no tested fix closes it

Why do matched neurons disagree? In MANC, two network copies that differ only by Poisson resampling of every connection's synapse count
agreed with each other at 0.48 of the ceiling (0.36-0.60), against 0.47 (0.34-0.59) for left against right in the same design (Fig. 3).
Count noise of this size, with no fitted parameter, met the pre-registered test of reproducing the left-right gap; the test used one pair of
copies, and a later look at other pairings (not locked) suggests noise accounts for most of the gap, not demonstrably all. It does not show
that real left-right differences are count noise, only that noise of this size can produce them. In MANC, transplanting the rest of the
network from one side into the other closed 0.34 of the gap (0.10-0.53) and transplanting a type's own outputs 0.23 (-0.01 to 0.42); no
class of difference closed it alone, and the classes interact. Pre-registered fixes to the procedure or network (dose sweeps, pooled
read-outs, symmetrised or consensus networks, lower synapse floors) were judged on agreement across flies and sides and on the number of
drivers; none passed: two broke the model's own DNg100 control, and those judged on every criterion left the flies at 0.31-0.39 of the
ceiling where 0.8 was required.

### 5. Stability under count noise does not demonstrably predict replication

If a hit flickers when synapse counts are re-rolled, it should not be expected to replicate in another animal; if that held, anyone with
one connectome could rank their hits. We tested this once, pre-registered. Sixteen Poisson copies of MANC's raw counts were screened with
B1r's exact procedure, after a regression gate reproduced all 448 of B1r's stored results for these types and seeds digest for digest. A
driver's stability is the fraction of copies in which it remains a driver. Among the 15 B1r drivers, the three that replicate in MaleCNS
were not significantly more stable than the rest (exact one-sided rank test, **p = 0.11**; 52 of 455 subsets as extreme): **not shown**
(Fig. 4). DNg100 was a driver in all 16 copies, DNit013 in 12 and DNb08 in 7, while three non-replicating hits (DNxl133, DNxl102, DNp02)
were at least as stable as DNit013. The repeat on the authors' 11-type list gave p = 0.27. The power statement fixed before the test applies:
with three replicated types the smallest attainable p is 0.002 and ties raise it, so this null is uninformative. Of the pre-specified
sensitivity analyses, the two on the mean copy score and the mean fraction of rhythmic seeds fell below 0.05 (0.035 and 0.033) and two did
not (0.13 and 0.18); none carries words. Noise sometimes creates hits: of 40 sampled types that are drivers in neither MANC screen, 7 became
drivers in at least one copy (26 of 640 type-copies, mostly types already between 0.05 and 0.5), and none in half the copies.

### 6. Two blind exams: the simulation does no better than two-step synapse counting

Both exams compared frozen predictions with labels collected blind from the literature (for exam 2 procedurally: its sources were
public), and both included pre-registered wiring baselines computed without any simulation. **Exam 1** asked whether a type's simulated
score ranks types that drive rhythmic front-leg movement when switched on in flies above types that do not. On 39 labelled types (25 yes,
14 no), the authors' whole-type score reached an AUROC of **0.577 (0.417-0.724), not better than chance by the pre-registered rule**; the
best of its wiring baselines, picked on these labels, counted signed two-step paths from the type to the front-leg motor neurons and reached
0.669. **Exam 2** asked whether the authors' full-cord model, run with our tuner, ranks the activated hemilineage highly from published
movement phenotypes: it did better than chance (mean percentile rank 0.633, 0.533-0.724, p = 0.008), never ranked it first (0 of 27), and
scored above seven of eight wiring baselines but no better than the best, signed two-step paths (0.638; difference -0.006, -0.172 to 0.166), which was picked on the
same labels. Exam 2's two source laboratories agree with each other poorly (kappa 0.24 where both code a cell), so its ceiling is low.

Exam 1's labels carry caveats that bear on the model. They were inferred from papers by language-model readers. All 21 types that rest on
a single intact-fly optogenetic atlas are "yes", while the "no" labels come from other papers, so the label is confounded with its source;
most labels describe intact flies, whereas the model is of the nerve cord alone; and a reviewer found that most "no" labels come from
takeoff or flight experiments (not locked). Eighteen types whose model scores and fly outcomes were already known were excluded
("exposed"), among them DNg100, whose exam 1 label ("no rhythm in headless flies") looked wrong. A pre-registered **audit** re-read every
cached source with fresh readers blind to exam 1. For DNg100, both forensic readers traced the "no" to one record of DNg100 activated
together with a brake neuron, coded as more line-specific than two plain DNg100 records; the consensus rule then let it decide, after the
blind rule had set aside 23 concordant records from the simulation papers. The audited label is **yes**. Across the 39 exam types the audit
found 3 errors (7.7 %, interval 1.6-20.9 %; 1 in the pre-registered sample of 15), below the 10 % threshold fixed in advance, and no
systematic fault, so exam 1 stands, with an erratum for six exposed types. The errors are not spread evenly: none among the 21 atlas types,
re-coded with exam 1's own procedure, and 3 of the 18 types read from papers. Recomputed with audited labels (exploratory), the AUROC is
0.559, and two-step counting 0.713.

### 7. Forward predictions

After both exams were unblinded, we locked a forward ledger of experiments that have not been done, built on the post hoc replication
categories. A candidate type is in a replication category, has a driver line in the labelling kit, and had not been tested in headless
flies according to the audit or exam 1. Three readings give each candidate yes or no for rhythmic front-leg stepping when it is switched on
in a decapitated fly: the **replication reading** (replicated or near-replicated types yes), the **single-connectome reading** (the authors'
A1 hits yes) and the **counting reading** (the top third of two-step signed counts yes). The short list (Table 1) holds 12 types, each with
at least one line listed as available on the day of the lookup (58 of the 78 lines checked):

| Group | Types | Replication / single-connectome / counting |
|---|---|---|
| near-replicated | DNp71, DNa13, DNa07, DNa03 | yes / no (DNa07: yes) / DNp71 yes, others no |
| single-fly hit, MANC (DNp41 on the authors' list) | DNp41, DNp02, DNg63 | no / DNp41 yes, others no / DNp41 and DNg63 yes |
| single-fly hit, MaleCNS | DNg13, DNg21 | no / no / yes |
| controls: non-driver in both flies, high counting | DNp07, DNg39, DNp26 | no / no / yes |

The decision rule was fixed before any experiment: for two readings, take the tested types with a clear outcome on which they disagree; one
reading is supported over the other if it is right on enough of them for a one-sided binomial test at 0.05. On this list the replication
and single-connectome readings disagree on only four types, so that comparison can only be inconclusive; we say so in advance rather than
discover it later. The informative comparisons are against counting: replication against counting on up to 10 types (9 right needed;
power 0.38 or 0.74 if the better reading is right on 80 or 90 % of types) and single-connectome against counting on up to 8 (7 right
needed; power 0.50 or 0.81). The replication-yes types are all near-replicated, not replicated. Both of DNp41's available lines also label
another DN type, one of them DNg100, and DNa03's only line labels six other types.

## Discussion

In this model, post hoc, the screen's two experimentally supported hits, DNg100, around which the model was built and whose replication
our calibration guarantees, and DNb08, its confirmed prediction, also replicate across two connectomes. Beyond those, the hit list is
fragile. In the model, copies of a neuron on two sides of one connectome disagree; the same type in two connectomes, which also differ in
reconstruction, disagrees more; and in MANC, Poisson-scale count noise moves the screen about as much as the left-right difference does.
The fragility is not confined to weak drivers near the threshold: on high-confidence matches, DNp41 (0.73 in our MANC screen and 0.65 in
the authors') scores 0.00 in MaleCNS (post hoc). In blind tests against published experiments, the simulation's ranking of types did not
beat a count of two-step synaptic paths, though exam 1's labels are too confounded with their sources to rank the two methods firmly.

These results bear on type-level hit lists, not on every claim a connectome simulation can make. The original paper's circuit claim, a
rhythm generator found by pruning, was tested by its authors across connectome datasets, which is the kind of cross-animal check this work
argues for; we did not re-test it. For anyone simulating a single connectome, our results, from one model and one behaviour, suggest three
practices, which the original authors' choice of neurons already follows. Report each hit's behaviour on matched copies, on the other side
and in another animal where one exists, before calling it a prediction. Stability under synapse-count noise is cheap to report, but our test
could not show that it predicts replication, so its value as a screen is unproven; it is no substitute for a second connectome. And compare
with wiring counts: signed two-step path counts, the best wiring baseline in each exam, did as well as the simulation.

What this work does not show: that a real fly's left and right copies behave differently; that the model is wrong about DNg100's own
circuit or the authors' rhythm generator; that the replicated hits are real drivers beyond the two already confirmed; or anything about other
behaviours or models. As designed, the forward list can test with modest power whether the replication or the single-connectome reading
beats wiring counts, but not, with the available lines, which of the two is better.

## Limitations

- One model and one behaviour: a rate model of rhythmic front-leg activity, scored by the authors' rhythmicity measure.
- Two animals, both male, whose connectomes also differ in reconstruction and annotation; the MaleCNS screen is ours (the authors published
  none), and the MANC network is our rebuild (identical to theirs). Our MANC screen shares 10 of the authors' 11 hits and adds 5.
- Cross-fly type matching is imperfect: 82 of 328 MaleCNS types have a low-confidence match, and the rule was written after the replication
  pattern was known; we lead with high-confidence matches.
- Everything in Results 2-3 that uses the hit-list categories is post hoc, at thresholds we did not vary; the replicated set includes the
  neuron our procedure was calibrated to make a driver in both connectomes, and a neuron the authors chose.
- Part S's null is uninformative by construction (three replicated types).
- Exam 1's labels were inferred from papers by language-model readers of one model family; they are confounded with their sources (all 21
  atlas-only types are "yes"); the consensus rule's tie-breaks decide 30 of the 54 audited labels; DNg100's label was wrong; and the audit's
  three errors all fall among the 18 types read from papers, one of them produced by the audit's own scope rule.
- Exam 2's two laboratories disagree with each other, so its ceiling is low.
- Our tuner was calibrated once on DNg100; the one-sided (half-fly) screens read out one side's motor neurons, the authors' single-neuron
  screen both, and the two flies' front-leg motor-neuron sets differ (144 in MANC, 130 in MaleCNS); our reimplementation reproduces the authors' published dynamics, but any procedure is one choice among several.
- Count noise sufficing to produce the gap does not identify the gap's cause.
- Two of the short list's types can only be tested with lines that also label other DN types (DNp41, DNa03).

## Methods

**Ledger.** Five runs (19-23 November 2026), each governed by a rulebook frozen before the simulations it governed (PREREG v1-v5);
rulebooks v3 to v5 disclose what had been seen before each freeze. A freeze is a lock file listing the SHA-256 of every rulebook, input,
output and code file it binds, chained to earlier locks, committed, tagged, pushed and timestamped with OpenTimestamps. Locked files are
never edited; later code changes are recorded as amendment rows before they are committed.

**Screens.** BrainIR reimplements the authors' rate model and reproduces their published dynamics. A screen stimulates a type's members (or
one side's), tunes the current per replicate with a fixed procedure whose one free setting was calibrated on DNg100, and scores the
front-leg motor neurons' rhythmicity; a type's score is the mean over usable replicates, a driver scores at least 0.5. Agreement is the
Spearman correlation of type scores across halves of the seeds, divided by the split-half ceiling, with 10,000-resample bootstrap intervals
over types.

**Replication (post hoc).** Types are matched across flies by the curated body match of each MaleCNS neuron to a MANC neuron, falling back on
the annotated MANC type name; a match is high confidence when every member is body-matched, no body match conflicts with the name and naming
is one-to-one. Categories use a driver threshold of 0.5 and the bands 0.3 and 0.05. Overlap uses replication rates (the share of one list's
hits that are hits in the other), the overlap coefficient (shared hits over the shorter list), whose cross-fly value on matched halves of the
seeds is compared with each fly's split-half value, and the Jaccard index with its maximum for the list sizes; intervals are 95 % percentile
intervals over 10,000 resamples of types.

**Count-noise stability (pre-registered).** Sixteen Poisson draws of every connection's raw synapse count in MANC (fixed seeds), each
thresholded at 5 synapses after resampling and signed by the presynaptic neuron's predicted transmitter, were screened with B1r's exact job
specification on 8 seeds. A type's copy score is its mean over usable seeds; its stability is the fraction of copies in which that score is
at least 0.5. The test ranks the 15 B1r drivers by stability (midranks for ties) and counts, over all 455 subsets of three, those whose
rank sum is at least that of the three replicated types. Sensitivity analyses and a reference test on the real network's score were fixed
in advance without words.

**Labels and exams.** Exam 1's labels were collected from a registry of 96 published sources by language-model reader sessions in isolated
rooms, with two readings, adjudication, quote checks by the second readers and transcript audits for breaches, and frozen before unblinding;
exam 2's came from three published sources; predictions were frozen separately. Exam 1's baselines counted direct and two-step paths and
other wiring summaries; exam 2's counted one- to three-step paths, signed or not, and a linearised network. The audit used fresh sessions in
isolated rooms (checked by a canary and by transcript audits), two independent readers per source, adjudication of disagreements, the atlas
re-coded with exam 1's own procedure, and verification of unclear outcomes, under rules and a consequence fixed before it began.

**Compute.** Simulations ran on GitHub Actions under a trust gate (locked jobs reproduced exactly) with determinism re-runs of every
campaign; run 4 also used Modal at the author's instruction.

## Disclosure

The analyses were designed with, and run by, AI agents (Anthropic's Claude models; Claude Opus 5.5 in this run, as orchestrator,
reviewers and label readers) under the author's direction. The author set the questions and the rules for each run; the agents wrote the
code, ran the analyses and drafted this text. Every review was done by a newly started agent.

## Data and code

Branch `ledger/v1` of the BrainIR repository; tags `ledger-prereg-v1` to `ledger-prereg-v5`, `ledger-reliability-v2`,
`ledger-scorecard-v1`, `ledger-scorecard-h1`, `ledger-pertype-v1`, `ledger-replication-v1` and `ledger-forward-v2`. Figures are drawn by
`ledger/scripts/posthoc/paper_figures_v5.py` from locked files.

**Figures.** Fig. 1: left against right copy in the authors' single-neuron screen (250 types). Fig. 2 (post hoc): whole-type scores in MANC
against MaleCNS, 215 high-confidence types, by category. Fig. 3: agreement as a fraction of the ceiling, with 95 % intervals. Fig. 4:
stability of each driver across 16 Poisson copies.
