# How reproducible is a simulated screen's hit list? A walking screen tested across three fly connectomes

**Title options.** (1) How reproducible is a simulated screen's hit list? A walking screen tested across three fly connectomes
(chosen). (2) The same model on three connectomes: which predicted walking neurons recur. (3) A connectome simulation's hits, from one
animal to three.

## Abstract

Connectome simulations suggest which neurons to test. We asked how reproducible the hit list of one such screen is: the rate-model
screen of Pugliese et al. (2026) for descending neurons driving rhythmic front-leg activity in *Drosophila*. In the authors' published
screen, a neuron's left and right copies agree at 0.63 of the screen's agreement with itself. Our reimplementation shows a similar
left-right gap in two male connectomes and, in a pre-registered test, in a third, female connectome left unexamined until our rules were
frozen (0.58). Across animals, screens agree at 0.31 to 0.50 of this ceiling; the gap was confirmed in the third animal (pre-registered),
although its wiring also matched the others' less closely. At the authors' threshold, the first two animals' hit lists overlap at chance
(post hoc). In the third animal, our own lists recurred above chance, while the authors' list recurred at chance (1 of 6). Because our
current-setting procedure failed its positive control there, these tests used a current sweep, as pre-registered. Our model reproduces
the authors' results for DNg100 and for a single DNb08 neuron. A neuron's stability under synapse-count noise predicted its score in the
third animal (12 types; p = 0.029; a second attempt). Against published experiments, the simulation did no better than counting
two-step synaptic paths. We list 12 experiments to test them.

## Introduction

A connectome is a map of every neuron and synapse in a nervous system. Connectomes of the fruit fly *Drosophila melanogaster* now cover
the whole nerve cord in several animals: a male nerve cord (MANC)[3], a female nerve cord (FANC)[6], a male central nervous system
(MaleCNS)[4] and a female brain and nerve cord (BANC)[5]. Simulating the wiring can suggest which neurons control a behaviour[7].

Pugliese and colleagues built rate models of the front-leg network of the nerve cord from these connectomes[1,2]. In a rate model each
neuron's activity is a firing rate driven by its synaptic inputs, with synapse counts as weights. They switched on, one at a time, all
933 excitatory descending neurons, the cells that carry commands from the brain to the nerve cord, and scored how rhythmic the front-leg
motor neurons became. They focused on two cell types, DNg100 and DNb08, "because every DN of these two types produced among the highest
rhythmicity scores"[2]. Simulated pruning then found a small circuit of interneurons that generates the rhythm; silencing either of its
two excitatory neurons abolished the rhythm in all four connectomes. DNb08 drove rhythm in three of the four connectomes but not in
BANC, and switching DNb08 on in headless flies produced rhythmic leg movements. These results hold up, and they are the authors': they
tested DNg100's circuit and DNb08 across datasets themselves.

The authors describe the screen as one that "works as a discovery tool, analogous to a forward genetic screen", and they "do not
interpret low scores as evidence against a DN's role"[2]. The first version of their preprint also notes that screen results were
"qualitatively similar for the left and right front legs"[2]. That sentence is about which leg's motor neurons are read out. We compare
something else: the left and right copies of the stimulated neuron. Our results therefore do not contradict theirs.

Others have asked related questions. A comparison of fly nerve-cord connectome models with rewired networks found that rhythm is generic,
and that what depends on the specific wiring is the coordination of opposing muscles[8]. In the fly compass circuit, differences between
reconstructions rival differences between animals, and trained models do not transfer between them[9]. A recent review argues that a
connectome is better treated as a testable structural prior than as a blueprint[10].

We ask a question the authors did not: how far does the whole hit list of such a screen reproduce? A hit list is what a laboratory might
use to choose experiments. We test three properties. If a hit reflects function that a neuron's left and right copies share, it should
hold on both sides. It should recur in another animal's connectome. And it should predict what happens when the same neurons are switched
on in real flies, better than simpler readings of the wiring. This goes beyond the use the authors made of the screen. Every analysis sits
in a prediction ledger: rules written, frozen and timestamped before the data they concern. Post hoc analyses are labelled as such.

## Results

### 1. Left and right copies disagree in the authors' own published screen

The authors' single-neuron screen stimulated each descending neuron alone, 128 times, and scored the rhythm of both front legs' motor
neurons. For the 250 cell types with exactly one copy on each side, we compared the scores of the left and the right copy (Fig. 1).
Because the screen has random elements, we measure agreement against a ceiling: how well the screen agrees with itself across two halves
of its random draws.

The left and right copies agree at 0.63 of that ceiling (95 % interval 0.53-0.72), a real gap by our pre-registered rule. Of the 250
types, 7 are hits (score of at least 0.5) on the left side and 8 on the right; one type is a hit on both sides.

Our reimplementation shows the same gap when only one side's copies are stimulated and that side's motor neurons are read out: 0.59 of
the ceiling in MANC (0.48-0.68) and 0.64 in MaleCNS (0.53-0.74). In BANC, which we did not examine before our rules were frozen, the
pre-registered test gave 0.58 (0.38-0.77): again a real gap (Fig. 2).

### 2. Count noise reproduces the gap in one animal but not in the third

Why would copies of the same neuron disagree? Synapse counts in a connectome carry noise. In MANC, we made two copies of the network in
which each connection's synapse count was redrawn from a Poisson distribution with the same mean, keeping the dataset's 5-synapse
threshold. The two copies agreed with each other at 0.48 of the ceiling (0.36-0.60), against 0.47 (0.34-0.59) for left against right in
the same design. Count noise of this size, with no fitted parameter, reproduced MANC's left-right gap (a pre-registered test of our
previous analysis).

In BANC, the pre-registered test did not reproduce it. Two BANC copies with redrawn counts agreed at 0.78 of the ceiling (0.64-0.89), well
above BANC's left-right agreement (0.58); the difference in agreement was -0.21 (-0.37 to -0.05). One difference may matter: the authors'
BANC network has no synapse threshold, so redrawing counts does not add or remove the many weak connections near a threshold, as it does
in MANC. Whatever the reason, count noise alone does not explain BANC's left-right gap.

### 3. Screens of different animals agree less than a screen agrees with itself

Next we compared whole-type screens of different animals. A whole-type screen stimulates all copies of a cell type together. We used the
181 cell types matched with high confidence in all three animals, leaving out DNg100 for reasons given in section 4.

For the first two animals, our screens agree at 0.40 of the ceiling (0.25-0.54; post hoc, as these animals were analysed before). The
pre-registered tests for the third animal used a current sweep instead of our current-setting procedure, because the procedure failed its
positive control in BANC (section 4). Under the sweep, BANC agreed with MANC at 0.35 (0.20-0.49) and with MaleCNS at 0.50 (0.38-0.62),
against 0.31 (0.17-0.45) for MANC with MaleCNS (Fig. 2). Both BANC comparisons are a real gap, so the gap between animals was confirmed in
the third animal.

This confirmation carries a pre-registered caveat. A broken build or a wrong type match would also lower agreement, so we compared the
wiring itself: for each type, the signed count of two-step paths to the front-leg motor neurons. MANC's and MaleCNS's agree at 0.82
(Spearman correlation). BANC's agree with them at 0.61 and 0.63, below the lowest value seen between the first two animals (0.71). Part of
the gap may therefore come from differences in reconstruction or in the type match rather than from the simulation.

Agreement over all types hides what matters most to an experimenter: whether the top of the list recurs. At the authors' threshold of
0.5, the first two animals' hit lists overlap at chance under our procedure: 1 shared hit among 10 and 22, where 1.0 is expected (post hoc;
214 types). At lower thresholds they overlap well above chance: at 0.3, 14 shared hits where 6 are expected (Fig. 3). Under the current
sweep, 14 of MANC's 18 hits are hits in MaleCNS (6 expected; post hoc).

In the third animal (pre-registered, current sweep), our MANC hits recurred above chance: 5 of 17 are hits in BANC, where 1.7 are expected
(p = 0.016). So did our MaleCNS hits: 12 of 60 recur, against 6.3 expected (p = 0.004). The authors' own hit list recurred at chance: 1 of
its 6 hits is a hit in BANC (0.6 expected; p = 0.47). With so few hits, this test has little power, so "at chance" does not show that the
authors' hits fail to recur.

### 4. Which neurons recur

One caveat comes before any list. Our current-setting procedure has one free setting, the number of front-leg motor neurons that must be
active for a run to count. It was chosen, before any other neuron was run, as the smallest value that makes DNg100 drive rhythm in MANC
and MaleCNS. DNg100's recurrence in those two animals is therefore built in, and we never count it as evidence. Under the original
procedure without this setting, DNg100 is not a hit in MaleCNS.

Two versions do not depend on this calibration. Under the original procedure, the only type that is a hit in both MANC and MaleCNS is
DNb08. Under the current sweep, 14 types are (post hoc).

In BANC, DNg100 was predicted to be a hit under our unchanged procedure, and it was: score 0.64, with each of its two copies a hit when
stimulated alone. But it reached 0.5 in only 11 of 16 random draws, short of the pre-registered bar of 12 for using the procedure in
BANC. The current sweep therefore became primary, as written in advance: under the sweep, DNg100 reached 0.5 in 8 of 8 draws. DNb08 did not
drive rhythm in BANC: neither the whole type (0.00) nor any of its four copies alone (0 of 16 draws each). This agrees with the authors,
who report the same for BANC.

Three types are hits in all three animals under the sweep: DNg100, DNa13 and DNxl092 (Fig. 4). DNa13 is one of the twelve types in our
list of experiments (section 7).

Is our second-animal screen faithful to the authors' model? Our previous analysis found that no single DNb08 copy drove rhythm in our
MaleCNS screen, whereas the authors report rhythm for a single DNb08 neuron there. At the authors' own configuration (their neuron, their
current, 2-s runs) our MaleCNS model reproduces their result: 15 of 16 draws reach 0.5 (mean 0.86; theirs 0.80; Fig. 6). All four DNb08
copies reach the bar at some fixed current. It also reproduces their DNg100 result (mean 0.98; theirs 0.985). The earlier failure came
from our current-setting procedure, not from the network.

### 5. Can one connectome tell you which hits to trust?

If a hit flickers when synapse counts are redrawn, it might also fail to recur in another animal. Anyone with one connectome could then
rank their hits. Our previous analysis tested this between MANC and MaleCNS and could not show it (p = 0.11, with too few recurring types
for the test to be informative). Two graded versions of that test were nominally positive, so we tried once more, pre-registered, on the
third animal. For 12 hits of our MANC screen or the authors' list, the mean score across 16 MANC copies with redrawn counts predicted the type's
score in BANC (Spearman
correlation 0.57, one-sided p = 0.029; Fig. 5). It did so beyond the type's score in the real MANC network (partial correlation 0.56). The
result is fragile: we chose this predictor because it was nominally positive before, and 10 of the 12 BANC scores are below 0.07, so the
correlation rests largely on the order of near-zero scores and on one clear hit.

Does pooling two animals predict a third? On the 181 shared types, the mean of MANC's and MaleCNS's scores predicted BANC better than
MANC's alone (gain 0.20 in correlation, 0.08 to 0.32), but not better than MaleCNS's alone (0.02, -0.03 to 0.07). The pre-registered
words are "not shown".

How many connectomes would a reliable screen need? The three cross-animal agreements average 0.39 of the ceiling. If animals were
interchangeable noisy measurements of one underlying screen, the Spearman-Brown formula[11,12] says that about 7 animals (4.3 to 9.7)
would have to be pooled for two pooled screens to agree at 0.8 of the ceiling. This is an extrapolation, and differences in
reconstruction count as differences between animals in it.

### 6. Against published experiments

We compared the simulation with published experiments in two blind tests, with labels collected from the literature before the
predictions were scored. In the second test, published movement phenotypes from switching on 27 neuron groups (hemilineages)[13-15] were
compared with the simulation's ranking of which group should move the legs most. The simulation did better than chance (mean percentile
rank 0.633, 0.533-0.724, p = 0.008) but never ranked the right group first (0 of 27). It was level with the best of eight wiring
baselines, signed two-step path counts (0.638; difference -0.006, -0.172 to 0.166). It scored above the other seven, and clearly above
four of them (post hoc: differences 0.13 to 0.21, intervals above zero). The two source laboratories agree with each other poorly (Cohen's
kappa[16] 0.24 where both code a group), so the ceiling of this test is low.

In the first test, whether a type drives rhythmic front-leg movement when switched on, the simulation's ranking was not better than chance
by the pre-registered rule (area under the curve 0.577, 0.417-0.724; signed two-step counting 0.669). We do not interpret this result. Its
"yes" labels come almost entirely from one atlas of freely walking intact flies[17] and its "no" labels from other kinds of experiment, so
the label is confounded with its source (Supplement S4).

### 7. Twelve experiments that could decide

Before any of these tests, we listed experiments that have not been done. They are twelve descending-neuron types to switch on in
headless flies, each with a driver line listed as available. Each type has three readings: replicated across animals, a hit in the
authors' list, and high in the two-step wiring count. We fixed in advance a rule for reading their outcomes. The list does not change
with the third animal; its BANC scores are reported beside it (Supplement S7).

## Discussion

For anyone simulating one connectome, our results suggest four things. First, a hit list from one connectome is fragile. In three
animals, left and right copies of the same neuron disagree, and the same cell type in different animals disagrees more. The authors'
own six high-confidence hits recurred in the third animal at chance. Second, the size of the disagreement depends on the procedure:
a current sweep recovers more shared hits than our current-setting procedure, and that procedure even failed its positive control in the
third animal. Third, simple wiring counts did as well as the simulation in published experiments. Fourth, a hit's stability under
synapse-count noise in one connectome may say something about another animal, but the evidence is one test of 12 types.

What holds up in the original work is substantial. The authors' rhythm circuit and its silencing results were reported for all four of
their connectomes; we did not re-test them. Their two experimentally supported drivers were chosen because every copy scored high, which
is the kind of check our results argue for. DNb08 drove rhythm in three of their datasets and not in BANC, and our model agrees in every
case we tested, including their single-DNb08 result in MaleCNS. Our MANC screen shares 10 of their 11 whole-type hits.

What we did not show: that real flies' left and right copies behave differently; that the model is wrong about DNg100's circuit; that the
hits that recur are real drivers; or anything about other behaviours or models. Whether the gap between animals reflects biology,
reconstruction or type matching, we cannot tell from these data: the wiring caveat in section 3 points to part of each.

## Limitations

- One model (the authors' rate model) and one behaviour (rhythmic front-leg activity, scored by the authors' rhythmicity measure).
- Three animals that also differ in sex (two males, one female), reconstruction method, synapse detection and annotation. BANC's network
  has no synapse threshold; MANC's and MaleCNS's have one.
- The second and third animals' screens are ours, run on the authors' networks; the authors published no screen of either. Our model
  reproduces their published DNg100 and single-DNb08 results there, but our current-setting procedure did not.
- Our current-setting procedure was calibrated once on DNg100 and failed its positive control in BANC, so the cross-animal tests rest on a
  current sweep, which calls many more hits (60 of 182 types in MaleCNS).
- Cell types are matched across animals by annotations. BANC's high-confidence matches are weaker evidence than MaleCNS's: no BANC type
  name conflicts with its ID match, which suggests both come from the same match. The wiring of BANC's matched types agrees less with the
  other animals' (section 3).
- The literature labels were read from papers by language-model readers of one model family (Use of AI). The first literature test's
  labels are confounded with their sources; we report its verdict and do not interpret it.
- Everything about the first two animals' hit lists is post hoc. The pre-registered tests are those on the third animal and our MaleCNS
  model's check against the authors (Methods).
- The positive stability result rests on 12 types, with a predictor chosen after a nominal positive.
- Count noise reproduced the left-right gap in MANC but not in BANC; noise of this size can produce such a gap in one network, which does
  not show that real left-right differences are count noise.

## Methods

**Models and screens.** We reimplemented the authors' rate model with their published parameters (time constant, gain, threshold and
maximum rate drawn per neuron from their published distributions; synaptic weights = signed synapse counts times 0.03; neuron size
scaling) and reproduced their published dynamical results. A screen stimulates the excitatory descending neurons of one cell type and
scores the rhythm of the front-leg motor neurons with the authors' published rhythmicity score. Our current-setting procedure starts at
a current of 128 and halves, doubles or bisects (at most 10 runs) until network activity lies within fixed bounds (10 to 1,500 active
neurons, at most 200 above 100 Hz) and at least one front-leg motor neuron is active. The required number of active motor neurons (1) is
its one free setting. Each run lasts 1 s; a type's score is its mean over the random draws with an accepted run (16 draws of the neuron
parameters), and a type scoring at least 0.5 is a hit. The original procedure omits the motor-neuron requirement. The current sweep runs
19 fixed currents from 4 to 2,048 and keeps the best score inside the activity bounds (8 draws). One-sided screens stimulate one side's
copies and read that side's motor neurons. In the third animal, as in MaleCNS, each copy's side is the side that receives most of its output synapses, because the annotated
sides agreed with it for only 63 % of neurons.

**Networks.** MANC: our rebuild of the authors' front-leg network (identical to theirs; 4,604 neurons, 144 front-leg motor neurons).
MaleCNS: the authors' network (4,310 neurons, 130). BANC: the authors' released network used as released (4,963 neurons, 139 front-leg
motor neurons; signs from each neuron's verified transmitter, else its predicted one). Before any other BANC neuron was simulated, the
BANC build passed a gate using only the authors' published DNg100 results: DNg100 at the authors' current drove rhythm (mean 0.994; theirs
0.984), and silencing either excitatory neuron of their rhythm circuit abolished it (0.000 and 0.028; theirs 0.014 and 0.035). Cell types
are named by MANC types: MaleCNS neurons through curated body matches, BANC neurons through the dataset's MANC match IDs. A match is high
confidence when every member is matched by ID, no ID match conflicts with the type name, and the naming is one-to-one.

**Agreement and overlap.** Two screens agree to the extent that their type scores have the same order (Spearman correlation). Agreement is
the mean correlation between one screen's first half of random draws and the other's second half, divided by each screen's agreement with
itself across its two halves (the ceiling), with 95 % intervals from 10,000 resamples of cell types. A ratio whose interval lies below 1 is
a real gap. Hit-list overlap counts the types that are hits in both screens, against the number expected by chance, with a hypergeometric
test and exact intervals.

**Pre-registration.** Each analysis was written into a rulebook before the data or simulations it concerned, frozen by a lock file listing
the SHA-256 of every rule, input, output and code file, tagged in git, pushed and timestamped with OpenTimestamps. The third animal stayed
blind until the rulebook was frozen: before that, only DNg100 was stimulated and only the authors' circuit neurons were silenced. The
rulebook was audited by a newly started agent (14 findings, all applied) and re-checked. It fixed which test carries which words, the
sets of cell types (DNg100 left out of every word-bearing set), the validity rule for the procedure, and every interval and threshold.

**Literature tests.** Labels were collected from published papers by language-model reader sessions in isolated rooms, with two readings,
adjudication and quote checks, and frozen before the predictions were scored. The first test's 39 types exclude 18 whose model scores and outcomes in flies were already known to us; an audit of its labels found
3 errors (7.7 %) and issued an erratum for six excluded types, among them DNg100.

**Compute.** Simulations ran on GitHub Actions, after a trust gate reproduced 100 previously locked simulations exactly; every campaign
passed a determinism re-run of 20 jobs (240 of 240 identical in this analysis).

## Use of AI

The ledger, its rules, code, simulations and analyses were designed, written and run by AI agents (Anthropic's Claude; the model recorded
in the logs and commit trailers is Claude Opus 5.5) under the direction of the human author, who set the questions and approved each run's
instructions. Agents also read the published papers to collect the literature labels, reviewed the rulebooks and drafts as newly started
sessions, and drafted this text. One earlier review was redone on another model after a provider safeguard stopped the first, and an
early test of the label readers' launcher used Claude Sonnet with a neutral prompt.

[[AUTHOR TO COMPLETE AFTER THE HAND CHECK: one sentence giving the result of the hand check of 20 labels (see paper/HAND_CHECK.md).]]

## Data and code

Branch `ledger/v1` of the BrainIR repository: rules, code, results and locks. Tags: `ledger-prereg-v6`, `ledger-posthoc-v6` and
`ledger-thirdfly-v1` (this analysis), and earlier `ledger-prereg-v1` to `ledger-prereg-v5`, `ledger-reliability-v2`,
`ledger-scorecard-v1`, `ledger-scorecard-h1`, `ledger-pertype-v1`, `ledger-replication-v1` and `ledger-forward-v2`. Figures are drawn by
`ledger/scripts/posthoc/paper_figures_v6.py` from locked files. The authors' code and data: their repository and Zenodo record[18].

## Figures

![**Figure 1. Left and right copies in the authors' published screen.** Each point is one of 250 cell types with exactly one copy on each
side in MANC: the mean rhythm score of its left copy (x) against its right copy (y), each over 128 runs, from the authors' single-neuron
screen. The diagonal marks equal scores. Agreement: 0.63 of the screen's agreement with itself.](figures_v1/fig1_left_right_authors.png)

![**Figure 2. Agreement between screens of matched cell types, as a fraction of the ceiling.** The ceiling is a screen's agreement with
itself across two halves of its random draws (1 = as close as a screen is to itself); bars are 95 % intervals over cell types. Blue:
left against right copies (authors' screen; our one-sided screens in each animal; BANC pre-registered). Green: two copies of the network
with redrawn synapse counts (MANC: previous analysis; BANC: pre-registered). Orange: whole-type screens of different animals under the
current sweep, on the 181 types matched with high confidence in all three animals, DNg100 left out.](figures_v1/fig2_agreement.png)

![**Figure 3. Share of one animal's hits that are hits in another, by threshold.** A type is a hit if its score is at least the threshold
(x). Solid lines: the share of the first animal's hits that are hits in the second; dashed lines of the same colour: the share expected by
chance (the second animal's hit rate). Left: our current-setting procedure, first two animals (post hoc). Right: current sweep; blue post
hoc, orange and green pre-registered. Types matched with high confidence; DNg100 left out.](figures_v1/fig3_recurrence_by_cut.png)

![**Figure 4. Scores of every type that is a hit in at least one animal.** Current sweep; the 29 types among the 182 matched with high
confidence in all three animals that score at least 0.5 in at least one animal; colour = mean rhythm score over 8 draws, sorted by the
mean of the three. DNg100's recurrence is built into our calibration.](figures_v1/fig4_hits_three_animals.png)

![**Figure 5. Stability under synapse-count noise in MANC against the score in the third animal.** Each point is one of 12 MANC hits with a
BANC match: its mean score over 16 MANC copies with redrawn synapse counts (x; previous analysis) against its BANC score under the current
sweep (y); only types scoring above 0.1 in BANC are named (DNxl102, DNb08); the other ten score below 0.07. Spearman 0.57, one-sided
permutation p = 0.029 (pre-registered).](figures_v1/fig5_stability_third_animal.png)

![**Figure 6. Single DNb08 neurons in our MaleCNS model.** Each of the four DNb08 copies stimulated alone at fixed currents (2-s runs),
16 random draws per current: the share of draws with a rhythm score of at least 0.5. Circle: the authors' configuration (their neuron at
current 250), which reproduces their reported result. Dashed line: half the draws.](figures_v1/fig6_dnb08_malecns_single.png)

## References

1. Pugliese, S. M., Chou, G. M., Abe, E. T. T., Turcu, D., et al. Connectome simulations identify a central pattern generator for fly
   walking. *Nature* (2026). doi:10.1038/s41586-026-11195-y
2. Pugliese, S. M., Chou, G. M., Abe, E. T. T., Turcu, D., et al. Connectome simulations identify a central pattern generator circuit for
   fly walking. *bioRxiv* (2025; version 1 posted 12 September 2025, version 2 30 April 2026). doi:10.1101/2025.09.12.675944
3. Takemura, S., Hayworth, K. J., Huang, G. B., Januszewski, M., et al. A connectome of the male *Drosophila* ventral nerve cord. *eLife*
   (2024). doi:10.7554/eLife.97769
4. Berg, S., Beckett, I. R., Costa, M., Schlegel, P., et al. Sexual dimorphism in the complete *Drosophila* male central nervous system
   connectome. *Cell* 189, 5504-5526 (2026). doi:10.1016/j.cell.2026.08.015
5. Bates, A. S., Phelps, J. S., Kim, M., Yang, H. H., et al. Distributed control circuits across a brain-and-cord connectome. *Nature*
   656, 957-970 (2026). doi:10.1038/s41586-026-10735-w
6. Azevedo, A., Lesser, E., Phelps, J. S., Mark, B., et al. Connectomic reconstruction of a female *Drosophila* ventral nerve cord.
   *Nature* 631, 360-368 (2024). doi:10.1038/s41586-024-07389-x
7. Shiu, P. K., Sterne, G. R., Spiller, N., Franconville, R., et al. A *Drosophila* computational brain model reveals sensorimotor
   processing. *Nature* 634, 210-219 (2024). doi:10.1038/s41586-024-07763-9
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
    neuronal circuits to behavior in *Drosophila*. *eLife* 14, RP106042 (2025). doi:10.7554/eLife.106042
15. Cheong, H. S. J., Eichler, K., Stürner, T., Asinof, S. K., et al. Organization of circuits linking descending input to motor output in
    the *Drosophila* male adult nerve cord. *eLife* 13, RP96084 (2026). doi:10.7554/eLife.96084
16. Cohen, J. A coefficient of agreement for nominal scales. *Educational and Psychological Measurement* 20, 37-46 (1960).
    doi:10.1177/001316446002000104
17. Cande, J., Namiki, S., Qiu, J., Korff, W., et al. Optogenetic dissection of descending behavioral control in *Drosophila*. *eLife* 7,
    e34275 (2018). doi:10.7554/eLife.34275
18. Pugliese, S., Chou, G., Abe, E., et al. Pugliese et al. 2026 data. *Zenodo* (2026). doi:10.5281/zenodo.22260924
