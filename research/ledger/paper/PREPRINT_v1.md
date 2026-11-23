# How reproducible is a simulated screen's hit list? A front-leg rhythm screen tested across three fly connectomes

<!-- Title options, for the author (not printed): (1) How reproducible is a simulated screen's hit list? A front-leg rhythm screen
tested across three fly connectomes (chosen). (2) The same model on three connectomes: which predicted walking-rhythm neurons recur.
(3) A connectome simulation's hits, from one animal to three. -->

## Abstract

Connectome simulations help choose experiments. We asked how reproducible one such hit list is: the rate-model screen of Pugliese et
al. (2026) for descending neurons driving front-leg rhythm in *Drosophila*. Unless marked post hoc, tests were pre-registered. In the
authors' published screen, a cell type's left and right copies agree at 0.63 of the screen's agreement with itself. Our
reimplementation shows a similar gap in two male connectomes and in a female connectome, BANC, not screened until our rules were frozen
(0.58). Screens of different animals agree at 0.31 (post hoc) to 0.50 of this ceiling. For BANC the verdict fixed in advance is
"confirmed", but its agreement was no lower than between the first two animals, and its wiring matched theirs less, so part of the gap
may come from the build or the type match. Hit lists depend on how the stimulus is set: at the authors' threshold, the first two
animals' lists overlap at chance under our current-setting procedure but above chance under a current sweep (post hoc), and under the
sweep our lists recurred in BANC above chance. In the male CNS, our model reproduces the authors' DNg100 result and their single-DNb08
result, which our current-setting procedure had missed. In the one interpretable literature test, the simulation added nothing beyond
the best wiring count.

## Introduction

Simulations of connectomes are now used to choose neurons for experiments[1-3]. A connectome is a map of every neuron and synapse in a
nervous system. In the fruit fly *Drosophila melanogaster*, the nerve cord, which holds the circuits that move the legs, has been mapped
in several animals: a male nerve cord (MANC)[4], a female nerve cord (FANC)[5], a male central nervous system (MaleCNS)[6] and a female
brain and nerve cord (BANC)[7].

Pugliese and colleagues built rate models of the nerve cord's front-leg network from these connectomes[1,2]. In a rate model each
neuron's activity is a firing rate driven by its synaptic inputs, with synapse counts as weights. In MANC they switched on, one at a
time, all 933 excitatory descending neurons, the cells that carry commands from the brain to the nerve cord, and scored how rhythmic the
front-leg motor neurons became. They focused on two cell types, DNg100 and DNb08, "because every DN of these two types produced among
the highest rhythmicity scores"[2]. Simulated pruning then found a small circuit of interneurons that generates the rhythm in the model;
silencing either of its two excitatory neurons abolished the rhythm in all four connectomes. DNb08 drove rhythm in three of the four
but not in BANC, and switching DNb08 on in headless flies produced rhythmic leg movements. These results are the authors'; what we
re-ran of them reproduces.

The authors describe the screen as one that "works as a discovery tool, analogous to a forward genetic screen", and they "do not
interpret low scores as evidence against a DN's role"[2]. They followed up only the two types whose every copy scored high.

We ask a question the authors did not: how far does the whole hit list of such a screen reproduce? Most cell types have a left and a right copy, the two mirror-image neurons of a bilateral pair. If a hit reflects
what a cell type does, both copies should score alike, the hit should recur in another animal's connectome, and it should predict what
happens when the neurons are switched on in real flies better than simpler readings of the wiring. This goes beyond the use the authors
made of the screen. The first version of their preprint notes that screen results were "qualitatively similar for the left and right
front legs"[2]. We read that sentence as being about which leg's motor neurons are read out; we compare the left and right copies of the
stimulated neuron, so our results do not contradict it.

Others have asked related questions. Comparing fly nerve-cord connectome models with rewired networks, one study found that rhythm is
generic and that the coordination of opposing muscles depends on the specific wiring[8]. In the fly compass circuit, differences between
reconstructions rival differences between animals, and trained models do not transfer between them[9]. A review argues that a connectome
is better treated as a testable structural prior than as a blueprint[10].

Every pre-registered test was written down, frozen and timestamped before the data it concerns. Table 1 gives each result's status.

## Results

### How the screens work

A screen stimulates descending neurons in the model and scores the front-leg motor neurons with the authors' rhythmicity score: for
each active motor neuron, how periodic its activity is, from 0 (not rhythmic) to 1 (perfectly periodic), averaged over the active motor
neurons. A cell type scoring at least 0.5, the authors' threshold, is a hit. Each simulation draws the neurons' parameters at random, so a
screen is repeated over many random draws, and a type's score is its mean.

How strongly to stimulate matters. The authors' screen sets the stimulus current automatically in each run: it starts at 128 and doubles
or halves the current until network activity lies within fixed bounds. We use three procedures. The *original procedure* is our
reimplementation of that rule for whole cell types. Our *current-setting procedure* adds one requirement: at least one front-leg motor
neuron must be active. We added it because, under the original procedure, DNg100, the authors' top-ranked cell type, was not a hit
in MaleCNS (0.06). The *current sweep* runs 19 fixed currents and keeps each draw's best score at which activity is within bounds; none of
its settings was chosen on any neuron. For their experiments on named neurons, the authors set one fixed current per dataset.

*Agreement* between two screens is the rank correlation of their type scores, divided by a *ceiling*: how well a screen agrees with
itself across two halves of its random draws. A ratio of 1 means two screens agree as closely as each agrees with itself; a ratio whose
95 % interval lies below 1 is "a real gap", our pre-registered term. *Hit-list overlap* counts how many of one screen's hits are hits in
the other, against the number expected by chance.

**Table 1. Status of each result.**

| Status | Results |
|---|---|
| Pre-registered in this analysis | Every test of the third animal, BANC; the check of our MaleCNS model against the authors' results |
| Pre-registered earlier | Left against right in the authors' screen and in our one-sided screens of MANC and MaleCNS; count noise in MANC; both literature tests; the first stability test |
| Post hoc | Everything about the first two animals' agreement and hit lists; comparisons between procedures; the four types that are hits in all three animals; the second literature test's comparison with each baseline; the estimates for each pair of animals |

### 1. In the authors' published screen, left and right copies agree less than the screen agrees with itself

The authors' single-neuron screen stimulated each descending neuron alone, in 128 random draws, and scored both front legs' motor
neurons together. For the 250 cell types with exactly one copy on each side, the left and right copies' scores agree at 0.63 of the
ceiling (95 % interval 0.53-0.72), a real gap (Fig. 1). Seven types are hits on the left and 8 on the right; only DNg100 is a hit on
both sides.

Our reimplementation shows a similar gap when one side's copies are stimulated and that side's motor neurons are read out: 0.59 of the
ceiling in MANC (0.48-0.68) and 0.64 in MaleCNS (0.53-0.74), with our current-setting procedure (Fig. 2A). In BANC, which we had not
screened before our rules were frozen, the pre-registered test gave 0.58 (0.38-0.77): again a real gap. It also used the current-setting
procedure, which failed its whole-type positive control in BANC (section 4), although each DNg100 copy stimulated alone, with both legs
read out, reached 0.5 in 13 of 16 draws. In these screens the median type scores 0 on each side, so the agreement rests on the types that respond.

### 2. Count noise reproduced the gap in MANC but not in BANC

Synapse counts carry noise. In our earlier analysis of MANC, we built two *resampled networks*, each
connection's count redrawn from a Poisson distribution with the same mean, keeping the 5-synapse threshold. They agreed with each other
at 0.48 of the ceiling (0.36-0.60), against 0.47 (0.34-0.59) for left against right in the same design (Fig. 2B): count noise, with no
fitted parameter, reproduced the gap. That rests on one pre-registered pair of networks; a reviewer's post hoc check over all stored pairs found
it a low draw, with noise reproducing most, but not demonstrably all, of the gap.

In BANC, the pre-registered test did not reproduce it. Two resampled networks agreed at 0.78 (0.64-0.89), well above BANC's left-right
0.58; the difference in raw cross-half correlation was -0.21 (-0.37 to -0.05). The two tests differ in ways that may matter (post hoc). With MANC's threshold, resampling both removes
connections and creates new ones; BANC's network has no threshold, so resampling only removes weak connections (a single-synapse
connection becomes zero about a third of the time). And BANC's test compared halves of the random draws, whereas MANC's paired the draws
of the two networks. MANC's result may depend on its threshold. Count noise alone does not explain BANC's left-right gap.

### 3. Screens of different animals agree less than a screen agrees with itself

A whole-type screen stimulates all copies of a cell type together. Table 2 compares animals under both procedures. For BANC, the
pre-registered tests used the current sweep, because the current-setting procedure failed its positive control there (section 4).

**Table 2. Agreement across animals and hit-list overlap.** Agreement: fraction of the ceiling on the 181 types matched with high
confidence in all three animals (95 % interval). Overlap: the first animal's hits that are hits in the second at 0.5, against chance,
on the pair's high-confidence types (214, 202, 182). DNg100 left out throughout.

| Animals | Agreement, sweep | Agreement, current-setting | Overlap, sweep | Overlap, current-setting |
|---|---|---|---|---|
| MANC, MaleCNS (post hoc) | 0.31 (0.17-0.45) | 0.40 (0.25-0.54) | 14 of 18 (6.0 expected) | 1 of 10 (1.0) |
| MANC, BANC | 0.35 (0.20-0.49) | 0.32 (0.17-0.46) | 5 of 17 (1.7) | not computed |
| MaleCNS, BANC | 0.50 (0.38-0.62) | 0.44 (0.30-0.57) | 12 of 60 (6.3) | not computed |

Both BANC agreements under the sweep are a real gap (Fig. 2C), so the verdict fixed in advance is "confirmed in the third animal", with
a caveat also fixed in advance: "BANC's wiring of these types agrees with the other animals' less than the first two animals' wiring
agreed, so part of the gap may come from the build or the type match." "Confirmed" alone says nothing about the size of the gap: BANC's
agreements are no lower than the first two animals' with each other (0.31, post hoc). On the 96 types whose BANC name equals the MANC
name, the sweep gives 0.32 and 0.57 (no verdict).

The caveat comes from the wiring: for each type, the signed count of two-step paths to the front-leg motor neurons. MANC's and MaleCNS's
counts agree at 0.82 (Spearman); BANC's, cut at the same 5-synapse threshold, agree with them at 0.61 and 0.63 (0.63 and 0.63 without
it), below the lowest earlier value for one side of one animal against a side of another (0.71). The check cannot apportion the gap, and
across the three pairs wiring agreement does not track screen agreement (post hoc): the most similarly wired pair, MANC and
MaleCNS, has the least similar screens. The authors attribute
some differences between their datasets to "variation in motor neuron reconstruction fidelity and synapse detection"[2].

What matters most to an experimenter is whether the top of the list recurs. Under the sweep, 14 of MANC's 18 hits are hits in MaleCNS
(post hoc; with DNg100, 15 of 19). In BANC (pre-registered), our MANC hits recurred above chance (5 of 17, p = 0.016; with DNg100, 6 of
18), and so did our MaleCNS hits (12 of 60, p = 0.004; with DNg100, 13 of 61). Still, most do not: 29 % and 20 % recur. Keeping each
draw's best of 19 currents, the sweep calls many hits: 61 of the 182 three-animal types in MaleCNS, against 18 under the current-setting
procedure (post hoc).

The authors' whole-type screen (their Extended Data Fig. 1c), cut by us at 0.5, has 11 hits. (Their published hit list is of single
neurons; we compare whole types with whole types.) Six of the 11 have a high-confidence BANC match once DNg100 is left out, and 1 is a
hit in BANC (0.6 expected; p = 0.47; with DNg100, 2 of 7). The verdict fixed in advance is "at chance at the authors' cut", with this
fixed sentence: "'At chance' means the overlap could not be told apart from chance by this test, whose power is low; it does not show
that the hits fail to recur." With six hits the test had about one chance in four of detecting recurrence even if 30 % truly recur, and
one of the six is DNb08, whose failure in BANC the authors reported. On the 96 same-name types (no verdict), 1 of 7 MANC hits, 7 of 30
MaleCNS hits and 0 of 3 of the authors' hits recur.

Under our current-setting procedure, the first two animals' lists overlap at chance at 0.5 (post hoc) but well above chance at 0.3: 14
shared hits where 6 are expected (Fig. 3). So the answer depends on the procedure. The sweep shares more hits beyond chance, but it calls
more hits and agrees no better over all types (0.31 against 0.40).

### 4. Which neurons recur

One caveat comes before any list. Our current-setting procedure has one free setting, the number of front-leg motor neurons that must be
active. Both animals had first been screened with the original procedure (DNg100 0.06 in MaleCNS); the setting was then chosen by running
DNg100 alone, as the smallest value that made it a hit in at least 12 of 16 draws in both. DNg100's recurrence under this procedure is
built in, and we never count it as evidence.

Two versions do not depend on this calibration (post hoc). Under the original procedure, the only type that is a hit in both MANC and
MaleCNS is DNb08. Under the sweep, 14 types besides DNg100 are.

In BANC, DNg100 was predicted to be a hit under the unchanged current-setting procedure, as the build check and the authors' result made
likely, and it was (0.64). But it reached 0.5 in only 11 of 16 draws, short of the pre-registered bar of 12, so, as written in advance,
the sweep became primary for the cross-animal tests, DNg100 having passed its bar there (8 of 8). Under the sweep DNg100 is a hit in all
three animals (0.81, 0.98, 0.92), as the authors found; it is not counted, because the build check and the validity rule used it.

DNb08 was not a hit in BANC: 0.00 under the current-setting procedure and 0.25 under the sweep; each of its four copies alone reached 0.5
in 0 of 16 draws (current-setting procedure). The authors found the same for their single DNb08 neuron; we did not run their BANC
configuration.

Under the sweep, four types are hits in all three animals (post hoc; Fig. 4): DNg100, DNxl134, DNa13 and DNxl092. Under the
current-setting procedure only DNg100 is; DNa13 and DNxl092 score 0.00 in BANC.

Is our model of MaleCNS faithful to the authors'? Our earlier analysis found no rhythm for any single DNb08 copy in our MaleCNS screen,
whereas the authors report it for a single DNb08 neuron. In a pre-registered check at their configuration (their neuron, current 250,
2-s runs), our model reproduces their result: 15 of 16 draws reach 0.5 (mean 0.86; theirs 0.80; Fig. 6). Each of the four copies
reaches 0.5 in at least half the draws at some fixed current, but only within a range of currents that differs between copies. The
model also reproduces their DNg100 result (mean 0.985; theirs 0.985). So the network can produce their result, and our current-setting
procedure missed it; the check changed the current, run length and activity bounds at once, so we cannot say which mattered.

### 5. Can one connectome tell you which hits to trust?

If hits that flicker under resampled synapse counts also fail to recur in other animals, anyone with one connectome could rank their
hits. Our earlier analysis tested this between MANC and MaleCNS and could not show it (p = 0.11), with too few recurring types
to be informative. Two of its four sensitivity analyses, both graded (a mean over the resampled networks instead of the number of networks in
which the type stays a hit), were nominally positive (p = 0.035 and 0.033; the others 0.13 and 0.18). So we tried once more, pre-registered, on BANC.

The test used the 12 hits of our MANC screen or the authors' whole-type screen that have a BANC match, DNg100 left out. Each type's mean
score across 16 MANC networks with resampled counts predicted its BANC score under the sweep: Spearman 0.57, one-sided p = 0.029 (Fig.
5). The verdict fixed in advance is "stability under count noise predicts the third animal". Secondary, without a verdict: 0.64 with
DNg100, 0.54 without DNb08, 0.53 with the earlier count of networks in which the type stays a hit, and a partial correlation of 0.56 given the type's score
in the real network (no test or interval). The result is fragile: the predictor was chosen after a nominal positive; ten of the 12 BANC
scores are below 0.07, so the correlation rests largely on the order of near-zero scores and on one clear hit; DNb08's failure in BANC
was foreseeable from the authors' report; and two MANC hits rest on 1 and 6 usable draws of 16.

Does pooling two animals predict a third? On the 181 shared types, the mean of MANC's and MaleCNS's scores predicted BANC better than
MANC's alone (gain in correlation 0.20, 0.08 to 0.32), but not better than MaleCNS's alone (0.02, -0.03 to 0.07): "not shown".

How many connectomes would a reliable screen need? The three cross-animal agreements average 0.39 of the ceiling. If animals were
interchangeable noisy measurements of one screen, the Spearman-Brown formula[11,12] says about 7 animals (4.3 to 9.7) would have to be
pooled for two pooled screens to agree at 0.8 of the ceiling. This extrapolation's interval resamples cell types, not animals; the three
pairs differ (0.31 to 0.50), which its assumption does not allow, and each pair alone gives about 4 to 9 animals (post hoc).

### 6. Against published experiments

Two earlier tests compared the simulation with published experiments, using literature labels frozen before the predictions were
scored.

The second test is the one we can interpret. Published experiments switched on the neurons of 27 hemilineages, groups of nerve-cord
neurons born from the same stem cell, and recorded the movements that followed[13,14]; a summary in [15] served as a cross-check. We
switched on each hemilineage in the authors' model of the whole nerve cord, with a current-setting rule calibrated on DNg100 for that
model, and predicted the movements. The statistic is the percentile rank of a hemilineage's own prediction among all 43, by fit to its
observed movements (1: its own fits best; 0.5: chance). The simulation beat chance (mean 0.633, 0.533-0.724, p = 0.008) but never ranked
a hemilineage's own prediction first (0 of 27). The verdict fixed in advance is "the model predicts, but it adds nothing beyond wiring":
the best of eight wiring baselines, picked on these labels, counted signed two-step paths and scored 0.638 (difference -0.006, -0.172 to
0.166). The simulation scored above the other seven, clearly above four (post hoc: differences 0.14 to 0.21). The two source papers
agree poorly (Cohen's kappa[16] 0.24 over the 33 hemilineage-by-movement cells both code), so the test's ceiling is low.

The first test asked whether a type drives rhythmic front-leg movement when switched on. The simulation was not better than chance by
the pre-registered rule (area under the curve 0.577, 0.417-0.724; signed two-step counting 0.669). We do not interpret this. Its "yes"
labels come almost entirely from one atlas of freely walking intact flies[17] and its "no" labels from takeoff and flight experiments,
most decided by our consensus rule's tie-breaks, so the label is confounded with its source; counting's higher value may reflect neuron
size (both points are a reviewer's findings, not locked analyses). The test also reads low scores as predictions of no effect, which the
authors explicitly do not do (Supplement S4).

### 7. Twelve experiments that could test the readings

After both literature tests and the post hoc replication pattern, but before the third animal, we listed twelve descending-neuron types
to switch on in headless flies, each with a driver line listed as available, scoring rhythmic front-leg stepping blind to genotype. Each
type carries three predictions: from replication between the first two animals, from a single connectome's screen and from the two-step
wiring count; a rule for reading the outcomes was fixed in advance. Twelve types cannot separate the replication reading from the
single-connectome reading (power near zero) but can test each against the wiring count (power 0.38 to 0.81). Their BANC scores are
reported beside the unchanged list (Supplement S7): only DNa13 and DNg13 are BANC hits under the sweep. DNg63 was a MANC hit on a single
usable draw, and DNg21 and DNg39 had no usable MANC draw (Supplement S7).

## Discussion

For one model and one behaviour, our results suggest four things. First, a hit list from one connectome is only partly reproducible. In
all three animals, a type's left and right copies agree less than a screen agrees with itself, and different animals' screens agree at
0.31 to 0.50 of that ceiling. Even under the sweep, where hits recur above chance, most hits of one animal are not hits in another.
Second, the answer depends on how the stimulus is set (post hoc): the sweep shares more hits beyond chance than our current-setting
procedure but calls more hits and agrees no better over all types, while the current-setting procedure failed its positive control in
BANC and missed the authors' single-DNb08 result. A hit is worth checking at several currents, in both copies and in a second
connectome. Third, in the one interpretable literature test, the simulation added nothing beyond the best of eight wiring counts, picked
on the same labels. Fourth, stability under synapse-count noise may say something about another animal, but the evidence is one fragile
test of 12 types.

What holds up in the original work is substantial. The authors reported their rhythm circuit and its silencing in all four connectomes,
and our BANC build check re-ran their silencing of its two excitatory neurons, which reproduced. DNg100 is a hit in all three networks
under the sweep, as they found. Our model reproduces their single-DNb08 result in MaleCNS, which our screen had missed, and, like them,
finds no DNb08 hit in BANC. Their decision to follow up only types whose every copy scored high is the kind of check our results
support. Our MANC screen shares 10 of their 11 whole-type hits, two of them on few usable draws (DNg63, 1 of 16; DNxl121, 6 of 16).

What we did not show: that real flies' left and right copies behave differently; that the model is wrong about DNg100's circuit; that
the hits that recur are real drivers; or anything about other behaviours or models. Whether the gap between animals reflects biology,
reconstruction or type matching, these data cannot tell, and the wiring check cannot separate them; the authors attribute some of their
own cross-dataset differences to reconstruction and synapse detection[2].

## Limitations

- One model (the authors' rate model) and one behaviour (rhythmic front-leg activity, scored by the authors' measure).
- Three animals that also differ in sex (two males, one female), reconstruction, synapse detection and annotation. The networks, as the
  authors built them, differ too: BANC's has no synapse threshold, MANC's and MaleCNS's keep connections of at least 5 synapses; neuron
  sizes come from surface area in BANC and volume in MANC and MaleCNS; MANC's descending neurons are cut at the neck.
- The second and third animals' screens are ours, on the authors' networks; the authors published no screen of either.
- Our current-setting procedure was calibrated once on DNg100, after a first screen, and failed its positive control in BANC. The
  cross-animal tests rest on the current sweep, which calls many more hits; the BANC left-right and count-noise tests used the
  current-setting procedure.
- The BANC build check tested one neuron and its circuit at one current; it cannot catch errors in other neurons' wiring, signs or sizes.
- Cell types are matched by annotations. BANC's type names appear to come from the same ID match, so its "no conflict" check cannot fail
  and its high-confidence matches add little to the ID match. The rule for high-confidence MANC-MaleCNS matches was written after the
  first two animals' hit lists were known, though before the third animal was examined.
- Literature labels were read by language-model readers of one model family (Use of AI). The first literature test is confounded with
  its sources; the second ran the authors' whole-nerve-cord model, not the front-leg screen.
- Everything about the first two animals' hit lists is post hoc (Table 1).
- Noise of this size can produce a left-right gap in one network (MANC) and did not in another (BANC); this does not show that real
  left-right differences are count noise.

## Methods

**Models and screens.** We reimplemented the authors' rate model with their published parameters (time constant, gain, threshold and
maximum rate drawn per neuron from their distributions; weights equal to signed synapse counts times 0.03; their neuron size scaling).
It reproduced their published dynamical results except one item of our own check, coupling between legs in the whole-nerve-cord model,
which the authors' own simulation output also fails. A screen gives the excitatory descending neurons of one cell type a constant input
current (the authors' arbitrary units) and scores the front-leg motor neurons. A neuron is active if its rate exceeds 0.01 Hz at any
time (the authors' definition). Our current-setting procedure starts at 128 and halves, doubles or bisects (at most 10 runs) until
activity lies within fixed bounds (10 to 1,500 active neurons, at most 200 above 100 Hz) and at least one front-leg motor neuron is
active; the bounds, start and run limit follow the authors' screen, and the required number of active motor neurons (1) is the one free
setting. Runs last 1 s. A type's score is its mean over the draws with an accepted run (16 draws), or 0 if none; at least 0.5 is a hit.
The original procedure omits the motor-neuron requirement. The sweep runs 19 fixed currents from 4 to 2,048 and keeps each draw's best
in-bounds score (8 draws). One-sided screens stimulate one side's copies and read that side's motor neurons; a BANC copy's side is the
side receiving most of its output synapses (Supplement S2).

**Networks.** MANC: our rebuild of the authors' front-leg network (identical to theirs; 4,604 neurons, 144 front-leg motor neurons).
MaleCNS: the authors' network (4,310 neurons, 130). BANC: the authors' released network, used as released (4,963 neurons, 139; signs
from each neuron's verified transmitter, else its predicted one). Before any other BANC neuron was simulated, the build passed a check
using only the authors' DNg100 results: DNg100 at their current drove rhythm (mean 0.994; theirs 0.984), and silencing either excitatory
neuron of their circuit abolished it (0.000 and 0.028; theirs 0.014 and 0.035). Cell types are named by MANC types, through curated
body matches (MaleCNS) or the dataset's MANC match IDs (BANC). A match is high confidence when every member is matched by ID, no ID
match conflicts with the type name, and the naming is one-to-one.

**Agreement and overlap.** Agreement is the mean Spearman correlation between one screen's type scores from one half of its random draws
and the other screen's from the other half, divided by the mean of the two screens' self-agreements across their own halves (the
ceiling), with 95 % intervals from 10,000 resamples of cell types. Overlap uses a hypergeometric test and exact (Clopper-Pearson)
intervals. A type's signed two-step path count sums, over all two-step paths from its neurons to the front-leg motor neurons, the
product of the two signed synapse counts.

**Pre-registration.** Each pre-registered test was written into a rulebook before the data it concerned; the rulebook was frozen by a
lock file listing the SHA-256 of every rule, input, output and code file, tagged in git, pushed and timestamped with OpenTimestamps. No
BANC screen ran before the freeze; before it, BANC's annotations were read to match types, only DNg100 was stimulated, only the authors'
circuit neurons were silenced, and the authors' BANC results were known. A newly started agent audited the rulebook (14 findings, all
applied) and re-checked it. The rulebook fixed each test's verdict words, the sets of cell types (DNg100 left out of every set carrying a
verdict), the validity rule and every interval. Post hoc numbers are locked separately.

**Literature tests.** Labels were collected by language-model reader sessions, each in an isolated copy of the project without the
predictions, with two readings, adjudication and quote checks, and frozen before scoring. The first test's 39 types exclude 18 whose
model scores and fly outcomes we already knew. An audit found 3 errors among the 39 labels (7.7 %): none among the 21 labelled from the
atlas alone, 3 among the 18 others (17 %, above the pre-registered 10 % bar if taken alone); it also issued an erratum for six excluded
types, DNg100 among them.

**Compute.** This analysis's simulations ran on GitHub Actions after a re-run of 100 locked simulations matched exactly; every campaign
passed a determinism re-run of 20 jobs (240 of 240 identical). MANC's one-sided screen (draws 4-15) and current sweep ran earlier
on Modal, under their own reproduction check.

## Use of AI

The ledger, its rules, code, simulations and analyses were designed, written and run by AI agents (Anthropic's Claude; the model recorded
in the logs and commit trailers is Claude Opus 5.5) under the direction of the human author, who set the questions and approved each
run's instructions. Agents also read the published papers to collect the literature labels, reviewed the rulebooks and drafts as newly
started sessions, and drafted this text. One earlier review was redone on another model after a provider safeguard stopped it, and an
early test of the label readers' launcher used Claude Sonnet.

[[AUTHOR TO COMPLETE AFTER THE HAND CHECK: one sentence giving the result of the hand check of 20 labels (see paper/HAND_CHECK.md).]]

## Data and code

Branch `ledger/v1` of the BrainIR repository holds the rules, code, results and locks. Tags for this analysis: `ledger-prereg-v6`,
`ledger-posthoc-v6`, `ledger-thirdfly-v1` and `ledger-paper-posthoc-v1`. Earlier tags: `ledger-prereg-v1` to `ledger-prereg-v5`,
`ledger-reliability-v2`, `ledger-scorecard-v1`, `ledger-scorecard-h1`, `ledger-pertype-v1`, `ledger-replication-v1` and
`ledger-forward-v2`. The figures are drawn by `ledger/scripts/posthoc/paper_figures_preprint_v1.py` from locked files. The authors'
code and data are in their repository and Zenodo record[18].

## Figures

![**Figure 1. Left and right copies in the authors' published screen.** Each point is one of 250 cell types with exactly one copy on each
side in MANC: the mean rhythm score of its left copy (x) against its right copy (y), each over 128 random draws, from the authors'
single-neuron screen. Dashed lines: the hit threshold, 0.5. The diagonal marks equal scores. Agreement: 0.63 of the screen's agreement
with itself (0.53-0.72).](figures_v1/fig1_left_right_authors.png)

![**Figure 2. Agreement between screens, as a fraction of the ceiling.** The ceiling is a screen's agreement with itself across two
halves of its random draws (1 = as close as a screen is to itself). Dots: estimates; bars: 95 % intervals over cell types. (A) Left
against right copies: the authors' screen, which reads both legs, and our one-sided screens, run with the current-setting procedure.
(B) Two networks with resampled synapse counts, each beside left against right in the same design: MANC from our earlier analysis
(paired design, 261 types) and BANC (cross-half design, 180 types). (C) Whole-type screens of different animals on the 181 types matched
with high confidence in all three, DNg100 left out, under the current sweep (the primary procedure for BANC) and the current-setting
procedure (reported beside it). Asterisk: pre-registered test of the third animal. Panels A and C use different designs and are not
compared with each other.](figures_v1/fig2_agreement.png)

![**Figure 3. Share of one animal's hits that are hits in another, by threshold.** A type is a hit if its score is at least the
threshold (x). Thick lines: the share of the first animal's hits that are hits in the second. Thin lines of the same colour: the share
expected by chance, which is the second animal's hit rate (the three BANC lines nearly coincide). Left: our current-setting procedure,
first two animals (post hoc). Right: current sweep; MANC to MaleCNS post hoc, the BANC comparisons pre-registered (asterisk). The
authors' whole-type screen keeps its own procedure. Types matched with high confidence; DNg100 left
out.](figures_v1/fig3_recurrence_by_cut.png)

![**Figure 4. Types that are hits in at least two animals under the current sweep (post hoc).** The 22 of the 182 types matched with
high confidence in all three animals (DNg100 included) that score at least 0.5 in at least two animals under the sweep; 71 types are
hits in at least one. Each cell gives the mean rhythm score; boxed, bold cells are hits. Left: current sweep (8 draws). Right: the same
types under our current-setting procedure (16 draws). Under the sweep four types are hits in all three animals; under the
current-setting procedure only DNg100 is. DNg100 is not counted as evidence, because the build check and the validity rule used
it.](figures_v1/fig4_hits_three_animals.png)

![**Figure 5. Stability under synapse-count noise in MANC against the score in the third animal (pre-registered).** Each point is one of
12 hits of our MANC screen or the authors' whole-type screen with a BANC match, DNg100 left out: its mean score over 16 MANC networks
with resampled synapse counts (from our earlier analysis) against its BANC score under the current sweep. DNxl102 is here but not in
Fig. 4, because its MaleCNS match is of medium confidence. Left: the scores; ten BANC scores are below 0.07. Right: their ranks, on which
the test is computed (Spearman 0.57, one-sided permutation p = 0.029).](figures_v1/fig5_stability_third_animal.png)

![**Figure 6. Single DNb08 neurons in our MaleCNS model (pre-registered check).** Each of DNb08's four copies stimulated alone at 19 fixed
currents and at the authors' current (2-s runs, 16 random draws each): the share of draws with a rhythm score of at least 0.5. Circle:
the authors' configuration (their neuron, copy 4, at current 250), which reproduces their reported result. Dashed line: half the draws.
Our current-setting procedure, which starts at 128 and accepts the first current at which activity is within bounds, had found no
rhythm for any single copy.](figures_v1/fig6_dnb08_malecns_single.png)

## References

1. Pugliese, S. M., Chou, G. M., Abe, E. T. T., Turcu, D., et al. Connectome simulations identify a central pattern generator for fly
   walking. *Nature* (2026). doi:10.1038/s41586-026-11195-y
2. Pugliese, S. M., Chou, G. M., Abe, E. T. T., Turcu, D., et al. Connectome simulations identify a central pattern generator circuit for
   fly walking. *bioRxiv* (2025; version 1 posted 12 September 2025, version 2 30 April 2026). doi:10.1101/2025.09.12.675944
3. Shiu, P. K., Sterne, G. R., Spiller, N., Franconville, R., et al. A *Drosophila* computational brain model reveals sensorimotor
   processing. *Nature* 634, 210-219 (2024). doi:10.1038/s41586-024-07763-9
4. Takemura, S., Hayworth, K. J., Huang, G. B., Januszewski, M., et al. A connectome of the male *Drosophila* ventral nerve cord. *eLife*
   (2024). doi:10.7554/eLife.97769
5. Azevedo, A., Lesser, E., Phelps, J. S., Mark, B., et al. Connectomic reconstruction of a female *Drosophila* ventral nerve cord.
   *Nature* 631, 360-368 (2024). doi:10.1038/s41586-024-07389-x
6. Berg, S., Beckett, I. R., Costa, M., Schlegel, P., et al. Sexual dimorphism in the complete *Drosophila* male central nervous system
   connectome. *Cell* 189, 5504-5526 (2026). doi:10.1016/j.cell.2026.08.015
7. Bates, A. S., Phelps, J. S., Kim, M., Yang, H. H., et al. Distributed control circuits across a brain-and-cord connectome. *Nature*
   656, 957-970 (2026). doi:10.1038/s41586-026-10735-w
8. Guan, I., Zhao, Y., Zhang, D., Lyu, S. & Chen, I.-M. How much of fly walking is written in the wiring? *arXiv* (2026).
   arXiv:2609.38665
9. Yad, M. A. A. & Nabila, N. T. Reconstruction differences rival individual differences in the fly compass connectome and break trained
   circuit models. *arXiv* (2026). arXiv:2610.29205
10. Jiang, W. & Xu, L. Connectomes as structural priors for embodied control: lessons from digital *Drosophila*. *Biomimetics* 11, 835
    (2026). doi:10.3390/biomimetics11110835
11. Spearman, C. Correlation calculated from faulty data. *British Journal of Psychology* 3, 271-295 (1910).
    doi:10.1111/j.2044-8295.1910.tb00206.x
12. Brown, W. Some experimental results in the correlation of mental abilities. *British Journal of Psychology* 3, 296-322 (1910).
    doi:10.1111/j.2044-8295.1910.tb00207.x
13. Harris, R. M., Pfeiffer, B. D., Rubin, G. M. & Truman, J. W. Neuron hemilineages provide the functional ground plan for the
    *Drosophila* ventral nervous system. *eLife* 4, e04493 (2015). doi:10.7554/eLife.04493
14. Soffers, J. H. M., Beck, E., Sytkowski, D. J., Maughan, M. E., et al. A library of lineage-specific driver lines connects developing
    neuronal circuits to behavior in the *Drosophila* ventral nerve cord. *eLife* 14, RP106042 (2025). doi:10.7554/eLife.106042
15. Cheong, H. S. J., Eichler, K., Stürner, T., Asinof, S. K., et al. Organization of circuits linking descending input to motor output
    in the *Drosophila* male adult nerve cord connectome. *eLife* 13, RP96084 (2026). doi:10.7554/eLife.96084
16. Cohen, J. A coefficient of agreement for nominal scales. *Educational and Psychological Measurement* 20, 37-46 (1960).
    doi:10.1177/001316446002000104
17. Cande, J., Namiki, S., Qiu, J., Korff, W., et al. Optogenetic dissection of descending behavioral control in *Drosophila*. *eLife* 7,
    e34275 (2018). doi:10.7554/eLife.34275
18. Pugliese, S., Chou, G., Abe, E., et al. Pugliese et al. 2026 data. *Zenodo* (2026). doi:10.5281/zenodo.22260924
