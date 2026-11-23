# Study guide: how to defend PREPRINT_v1

For the sole human author: a strong programmer with no biology training. Read it once before you read the paper, and again before any
conversation about it. Every file named is under `research/ledger/` unless stated.

## 1. Glossary

- **Connectome**: a wiring diagram of a nervous system from electron microscopy: every neuron and the number of synapses between each
  pair. Think of a weighted directed graph whose node and edge lists were traced by people and machine learning, with errors.
- ***Drosophila***: the fruit fly. **MANC** (male nerve cord), **MaleCNS** (male brain and nerve cord), **BANC** (female brain and nerve
  cord) and **FANC** (female nerve cord) are four connectomes of different individual flies, reconstructed by different teams.
- **Nerve cord** (ventral nerve cord, VNC): the fly's equivalent of a spinal cord; it holds the circuits that move the legs.
- **Descending neuron (DN)**: a neuron that carries a command from the brain down to the nerve cord. Names like DNg100 and DNb08 are cell
  type names. **Cell type**: a set of neurons with the same shape and wiring, usually one **copy** on each side of the body.
- **Motor neuron**: a neuron that drives a muscle. **Front-leg motor neurons**: the read-out of every screen here.
- **Rate model**: a simulation in which each neuron's activity is a firing rate (spikes per second), updated by an equation driven by its
  synaptic inputs; weights = synapse counts times a gain, signed by the sending neuron's transmitter (excitatory or inhibitory).
- **Stimulus current**: the input injected into the stimulated neurons. Too little and nothing happens; too much and the network saturates.
- **Rhythm score**: the authors' measure (0 to 1) of how rhythmic the active motor neurons are. **Hit** (driver): a cell type whose mean
  score is at least 0.5 (the authors' threshold).
- **Screen**: stimulating every cell type in turn and scoring each. **Whole-type screen**: all copies of a type together. **One-sided
  screen**: only one side's copies, reading that side's motor neurons. **Single-neuron screen**: one copy at a time (the authors').
- **Random draws** (seeds, replicates): each neuron's parameters are drawn at random around published values, so a screen is repeated
  16 times (or 8, or 128) and averaged.
- **Current-setting procedure**: our way of choosing the current per run (start at 128, halve or double until activity is in bounds, at
  least one front-leg motor neuron active). Its **one free setting** (how many motor neurons must be active) was chosen on DNg100.
- **Original procedure**: the same without the motor-neuron requirement. **Current sweep**: 19 fixed currents, keep the best in-bounds
  score; no setting chosen on any neuron.
- **Ceiling**: how well a screen agrees with itself across two halves of its random draws. **Agreement ratio**: agreement between two
  screens divided by the ceiling; 1 = as close as the screen is to itself. **A real gap**: the ratio's 95 % interval lies below 1.
- **Spearman correlation**: correlation of ranks. **Bootstrap interval**: the spread of a statistic when the cell types are resampled
  with replacement 10,000 times.
- **Hypergeometric test**: the probability of seeing at least k shared hits if two lists were drawn independently. **Chance
  expectation**: the expected number of shared hits under independence. **Overlap coefficient**: shared hits over the shorter list.
- **AUROC**: the probability that a hit ranks above a non-hit; 0.5 is chance.
- **Poisson resampling / count noise**: redrawing every synapse count from a Poisson distribution with the same mean, to mimic noise in
  counting synapses. **Synapse threshold (floor)**: connections below 5 synapses dropped (MANC, MaleCNS; not BANC).
- **Type match**: deciding which BANC (or MaleCNS) neurons belong to which MANC type, from the datasets' own cross-annotations.
  **High confidence**: every member matched by ID, no conflicting names, one-to-one naming.
- **Hemilineage**: a group of nerve-cord neurons born from the same stem cell; the second literature test's unit.
- **Headless (decapitated) fly**: the brain is removed, so only the nerve cord's own circuits act. **Optogenetics**: switching neurons on
  with light through a light-sensitive channel; a **driver line** (split-GAL4) is the fly strain that targets the channel to one type.
- **Pre-registration**: writing the analysis and its verdict words before seeing the data. **Lock file**: a JSON listing SHA-256 hashes of
  every rule, input, output and code file; **tag**: a git name for the commit; **OpenTimestamps**: a public proof that a hash existed by a
  date. **Post hoc**: decided after seeing the data. **Power**: the chance a test detects a real effect of a given size.
- **Spearman-Brown formula**: predicts how reliability grows when independent measurements are averaged.
- **Trust gate / determinism check**: re-running previously locked simulations, or a sample of new ones, and requiring identical results.

## 2. The results, one by one

**R1. Left and right copies agree less than a screen agrees with itself.** In the authors' published single-neuron screen, a type's left
and right copies agree at 0.63 of the ceiling; our one-sided screens show a similar gap in all three animals (BANC's ran on the
current-setting procedure, which failed its control there). *Remember:* 0.63 (0.53-0.72); ours 0.59,
0.64 and, pre-registered in BANC, 0.58 (0.38-0.77). *Measured:* Spearman of left-copy against right-copy scores across types, from halves of
the random draws, divided by the ceiling (`reliability_v2/A0.json`, `A.json`, `thirdfly_v1/C_tests.json` C1). *Weakest point:* left and
right copies are two different neurons; nothing says a real fly's copies behave differently.

**R2. Count noise reproduced the gap in MANC but not in BANC.** Redrawing synapse counts made two MANC networks disagree as much as left
and right did; in BANC, the two redrawn networks agreed much more than left and right. *Remember:* MANC 0.48 vs 0.47; BANC 0.78 vs 0.58
(difference -0.21, -0.37 to -0.05). *Measured:* the same agreement statistic between two copies (`NOISE.json`; `C_tests.json` C2).
*Weakest point:* BANC has no synapse threshold, MANC does, so the two noise models are not identical perturbations.

**R3. Screens of different animals agree less than a screen agrees with itself.** Across animals, the agreement is 0.31 to 0.50 of the
ceiling, and the pre-registered test confirmed the gap in BANC. *Remember:* MANC-BANC 0.35, MaleCNS-BANC 0.50, MANC-MaleCNS 0.31 (sweep,
181 types); hit lists depend on the procedure: at the authors' threshold the first two animals' lists share 1 hit where 1.0 is
expected under the current-setting procedure, but 14 of 18 MANC hits recur under the sweep (6 expected; both post hoc); in BANC our MANC
hits recur 5 of 17 (1.7 expected), our 0.5 cut of the authors' whole-type screen 1 of 6 (0.6 expected; a test of low power). *Measured:* `C_tests.json` C3, C4; `posthoc_v6/H_posthoc.json`.
*Weakest point:* BANC's wiring also agrees less with the others (0.61-0.63 vs 0.82), so part of the gap may come from the build or the type
match; and the tests use the sweep, not the procedure the first two animals' lists came from.

**R4. Which neurons recur.** Under the current-setting procedure DNg100's recurrence is built into our calibration; under the sweep it
is a hit in all three animals, as the authors found, but it is not counted because the build check and the validity rule used it. DNb08
recurs between the two male animals under every procedure and is not a hit in BANC, as the authors also found. *Remember:* original
procedure: only DNb08 shared; sweep: 14 besides DNg100; four types are sweep hits in all three animals (DNg100, DNxl134, DNa13, DNxl092;
post hoc); in BANC DNg100 0.64 (11 of 16 draws, bar 12, so the sweep became primary), DNb08 0.00 (current-setting) and 0.25 (sweep);
our MaleCNS model reproduces the authors' single-DNb08 result (15 of 16 draws at their configuration). *Measured:* `posthoc_v6`, `C_tests.json` C5 and V. *Weakest point:* two named
neurons are a tiny sample, and the authors chose both.

**R5. Can one connectome tell you which hits to trust?** A hit's stability under count noise in MANC predicted its BANC score; pooling two
animals did not beat MaleCNS alone; about 7 animals would be needed. *Remember:* Spearman 0.57, p = 0.029 (12 types); pooling +0.02
(-0.03 to 0.07) over MaleCNS; 7 animals (4.3-9.7). *Measured:* `C_tests.json` C8, C6, C7. *Weakest point:* C8's predictor was chosen
after a nominal positive, and 10 of its 12 BANC scores are near zero; C7 is an extrapolation.

**R6. Against published experiments.** In the one interpretable test, the authors' whole-nerve-cord model predicted which hemilineage
moves the legs better than chance but added nothing beyond the best of eight wiring baselines (signed two-step paths, picked on the same
labels). *Remember:* 0.633 vs 0.638 (difference -0.006, -0.172 to 0.166); 0 of 27 ranked first; the first
test's AUROC 0.577 is not interpreted. *Measured:* `results/run3/primary.json`, `results/run2/P.json`. *Weakest point:* labels were read by
language models; the two source labs disagree with each other (kappa 0.24).

**R7. Twelve experiments.** A pre-registered list of twelve descending-neuron types to switch on in headless flies, with a decision rule.
*Remember:* 12 types, three readings each. *Measured:* `forward_v2/`. *Weakest point:* it cannot separate the replication reading from the
single-connectome reading (power near zero); the list was made after the replication pattern was seen; DNg63 rests on one usable MANC
draw, and DNg21 and DNg39 had none.

## 3. The ten hardest questions the original authors could ask

1. **"Your MaleCNS and BANC screens are not our model."** Our MaleCNS model reproduces your DNg100 result (0.985 vs 0.985) and your
   single-DNb08 result at your configuration (15 of 16 draws); the BANC build reproduces your DNg100 and silencing results; our MANC screen
   shares 10 of your 11 whole-type hits. What differs is our current-setting procedure, and the paper says so. *Files:*
   `thirdfly_v1/C_tests.json` (V), `gates_v6/BANC_GATE.json`, `pertype_v1/`.
2. **"DNg100's recurrence is circular."** Under the current-setting procedure, yes: its one setting was chosen on DNg100, after a first
   screen in which DNg100 scored 0.059 in MaleCNS. Under the sweep nothing was calibrated, but DNg100 was the build check and the validity
   control, so it is never counted. *Files:* `PREREG_v2.md` P1, `predictions/B2/types.csv`, `PREREG_v6.md` G5.
3. **"Your headline depends on the procedure."** Correct, and the paper now leads with it. At 0.5, the first two animals' hit lists overlap
   at chance under the current-setting procedure but 14 of 18 recur under the sweep (6 expected; post hoc). But the sweep calls about three
   times as many hits, and over all types it agrees no better (0.31 against 0.40). Lower thresholds also raise the overlap (Fig. 3).
   *Files:* `posthoc_v6/H_tables.md`, `thirdfly_v1/C_tests.json` C3, `paper_posthoc_v1/`.
4. **"'Confirmed in the third animal' could not fail."** Nearly so: only agreement at the ceiling would have refuted it, and no pair of
   animals has come close. The rulebook itself says "confirmed" says nothing about size. What informs is the size: BANC's agreements, 0.35
   and 0.50, are no lower than the first two animals' 0.31. *Files:* `PREREG_v6.md` C3, `C_tests.json` C3.
5. **"Your procedure failed its own control in BANC, yet your BANC left-right and noise tests used it."** As pre-registered: the validity
   rule moved only the cross-animal tests to the sweep. Each DNg100 copy alone still reached 0.5 in 13 of 16 draws, and the paper states
   which procedure each test used. The one-sided screens rest on the minority of types that respond (median score 0). *Files:*
   `C_tests.json` B4_validity, C1, C5.
6. **"Left and right copies are different neurons."** Yes; the ceiling asks how much of the screen's reproducible variation the copies
   share. We do not claim that real flies' copies differ. *Files:* `PREREG_v4.md` G6-G7, `reliability_v2/A0.json`.
7. **"BANC differs in sex, reconstruction and synapse detection, and your wiring check does not even track the screen agreement."**
   Agreed on both. BANC's wiring agrees less with the others (0.61-0.63 vs 0.82), yet the most similarly wired pair (MANC and MaleCNS) has
   the least similar screens. We cannot separate biology from the build, and the paper says so. You attribute some of your own
   cross-dataset differences to reconstruction and synapse detection, and we cite that. *Files:* `C_tests.json` C3_wiring.
8. **"Our list recurred at chance because it is short."** Yes. With six matched hits, the test had about one chance in four of detecting
   recurrence even if 30 % recur; the rates are similar (17 %, against 29 % and 20 % for our lists). The list is our 0.5 cut of your
   whole-type screen, not a list you published, and the contrast is gone from the abstract and the Discussion. *Files:* `PREREG_v6.md` C4
   (power), `C_tests.json` C4.
9. **"We called the screen a discovery tool; you test a use we never claimed."** We quote that framing and say we test something beyond
   it. Your choice to follow up only types whose every copy scored high is the kind of check our results support. *Files:*
   `paper/PREPRINT_v1.md` (Introduction, Discussion); the notes on your paper.
10. **"Your positive evidence is thin: language models read the labels, the stability result is fragile, and '7 animals' assumes
    exchangeable animals."** All true. The first literature test is not interpreted, and an audit found 3 errors in 39 labels. The
    stability correlation rests on 12 types, 10 of them near zero, with a predictor chosen after a nominal positive. The '7 animals'
    interval resamples types, not animals, and the pairs differ (each pair alone gives 4 to 9). The hand check of 20 labels is yours to do.
    *Files:* `LABEL_AUDIT_v1.md`, `C_tests.json` C7 and C8, `paper_posthoc_v1/PAPER_POSTHOC.json`.

## 4. What you must never claim, and why

- **That the original paper is wrong.** We did not test their rhythm circuit, pruning or experiments; their DNg100 and DNb08 results hold
  up in our hands.
- **That DNg100's recurrence supports anything.** It is built into our calibration under the current-setting procedure, and DNg100 was
  the build check and the validity control under the sweep.
- **That BANC was never looked at before the freeze.** Its annotations were read to match types, DNg100 was run for the build check and
  the authors' BANC results were known; only the screens were blind.
- **That the authors' list fails to recur.** It is our 0.5 cut of their whole-type screen, and the test had about one chance in four.
- **That hits "do not recur" when a test says "at chance".** The tests have little power (about 0.1 to 0.5); "at chance" means not
  distinguishable from chance.
- **That the gap between animals is biological.** The wiring check says part may be reconstruction or matching.
- **That count noise causes the left-right gap.** It reproduced it in one network and not in another.
- **That stability under count noise is a validated way to choose hits.** One fragile positive test of 12 types.
- **That the third animal's tests used the same procedure as the first two.** They used the current sweep, by the pre-registered rule.
- **That the first two animals' hit-list results were pre-registered.** They are post hoc.
- **That the labels were checked by a person,** until you have done the hand check, and then only for the 20 items you checked.
- **That the simulation predicts behaviour better than wiring counts.** In the one interpretable test it added nothing beyond the best
  of eight; the other test is not interpretable.
- **That hit lists fail to replicate, full stop.** It depends on the procedure: under the sweep, hits recur above chance.
