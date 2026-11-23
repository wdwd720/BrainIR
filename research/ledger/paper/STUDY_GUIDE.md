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

**R1. Left and right copies disagree in the authors' own screen.** In the authors' published single-neuron screen, a type's left and
right copies agree at only 0.63 of the ceiling; our screens show the same in all three animals. *Remember:* 0.63 (0.53-0.72); ours 0.59,
0.64 and, pre-registered in BANC, 0.58 (0.38-0.77). *Measured:* Spearman of left-copy against right-copy scores across types, from halves of
the random draws, divided by the ceiling (`reliability_v2/A0.json`, `A.json`, `thirdfly_v1/C_tests.json` C1). *Weakest point:* left and
right copies are two different neurons; nothing says a real fly's copies behave differently.

**R2. Count noise reproduced the gap in MANC but not in BANC.** Redrawing synapse counts made two MANC networks disagree as much as left
and right did; in BANC, the two redrawn networks agreed much more than left and right. *Remember:* MANC 0.48 vs 0.47; BANC 0.78 vs 0.58
(difference -0.21, -0.37 to -0.05). *Measured:* the same agreement statistic between two copies (`NOISE.json`; `C_tests.json` C2).
*Weakest point:* BANC has no synapse threshold, MANC does, so the two noise models are not identical perturbations.

**R3. Screens of different animals agree less than a screen agrees with itself.** Across animals, the agreement is 0.31 to 0.50 of the
ceiling, and the pre-registered test confirmed the gap in BANC. *Remember:* MANC-BANC 0.35, MaleCNS-BANC 0.50, MANC-MaleCNS 0.31 (sweep,
181 types); at the authors' threshold the first two animals' lists share 1 hit where 1.0 is expected (post hoc); in BANC our MANC hits
recur 5 of 17 (1.7 expected), the authors' 1 of 6 (0.6 expected). *Measured:* `C_tests.json` C3, C4; `posthoc_v6/H_posthoc.json`.
*Weakest point:* BANC's wiring also agrees less with the others (0.61-0.63 vs 0.82), so part of the gap may be reconstruction or type
matching, not the simulation; and the tests use the sweep, not the procedure the first two animals' lists came from.

**R4. Which neurons recur.** DNg100 recurs everywhere but that is built into our calibration; DNb08 recurs between the two male animals
under every procedure and fails in BANC, as the authors also found. *Remember:* original procedure: only DNb08 shared; sweep: 14 shared;
in BANC DNg100 0.64 (11 of 16 draws, bar 12, so the sweep became primary), DNb08 0.00; our MaleCNS model reproduces the authors' single
DNb08 result (15 of 16 draws at their configuration). *Measured:* `posthoc_v6`, `C_tests.json` C5 and V. *Weakest point:* two named
neurons are a tiny sample, and the authors chose both.

**R5. Can one connectome tell you which hits to trust?** A hit's stability under count noise in MANC predicted its BANC score; pooling two
animals did not beat MaleCNS alone; about 7 animals would be needed. *Remember:* Spearman 0.57, p = 0.029 (12 types); pooling +0.02
(-0.03 to 0.07) over MaleCNS; 7 animals (4.3-9.7). *Measured:* `C_tests.json` C8, C6, C7. *Weakest point:* C8's predictor was chosen
after a nominal positive, and 10 of its 12 BANC scores are near zero; C7 is an extrapolation.

**R6. Against published experiments.** The simulation predicted which hemilineage moves the legs better than chance but no better than
counting two-step synaptic paths. *Remember:* 0.633 vs 0.638 (difference -0.006, -0.172 to 0.166); 0 of 27 ranked first; the first
test's AUROC 0.577 is not interpreted. *Measured:* `results/run3/primary.json`, `results/run2/P.json`. *Weakest point:* labels were read by
language models; the two source labs disagree with each other (kappa 0.24).

**R7. Twelve experiments.** A pre-registered list of twelve descending-neuron types to switch on in headless flies, with a decision rule.
*Remember:* 12 types, three readings each. *Measured:* `forward_v2/`. *Weakest point:* with the available lines, it cannot decide between
the replication reading and the authors' list.

## 3. The ten hardest questions the original authors could ask

1. **"Your MaleCNS and BANC screens are not our model."** Our MaleCNS model reproduces your DNg100 result (0.98 vs 0.985) and your single
   DNb08 result at your own configuration (15 of 16 draws); our BANC build reproduces your DNg100 and silencing results (gate); our MANC
   screen shares 10 of your 11 hits. What differs is our current-setting procedure, and we say so. *Files:* `thirdfly_v1/C_tests.json`
   (V), `gates_v6/BANC_GATE.json`, `pertype_v1/`.
2. **"DNg100's recurrence is circular."** Yes. Our procedure's one setting was chosen on DNg100; we never count it, and every
   pre-registered word rests on sets without DNg100. Under the original procedure DNg100 is not even a hit in MaleCNS (0.059). *Files:*
   `PREREG_v2.md` P1, `PREREG_v6.md` G5, `predictions/B2/types.csv`.
3. **"0.5 is an arbitrary threshold; lower it and the lists overlap."** Correct for the first two animals: at 0.3, 14 shared hits where 6
   are expected (post hoc). We show the whole curve and say so. *Files:* `posthoc_v6/H_tables.md`, `paper/figures_v1/fig3_*`.
4. **"Left and right copies are different neurons."** Yes; the ceiling asks how much of the screen's reproducible variation the copies
   share. We do not claim real flies' copies differ. *Files:* `PREREG_v4.md` G6-G7, `reliability_v2/A0.json`.
5. **"Your procedure failed its own control in BANC, so ignore BANC."** The rule fixed beforehand made the sweep primary (DNg100 8 of 8);
   the procedure's own numbers, reported beside, show the same gaps (0.32 and 0.44 vs 0.40). *Files:* `C_tests.json` B4_validity, C3.tuned.
6. **"BANC differs in sex, reconstruction and synapse detection."** Agreed, and our wiring check shows it (0.61-0.63 vs 0.82). We cannot
   separate biology from reconstruction; we say part of the gap may come from either. *Files:* `C_tests.json` C3_wiring.
7. **"Language models read your labels."** True; the first test is reported and not interpreted; an audit found 3 errors in 39 types; the
   hand check of 20 labels is yours to do before posting. *Files:* `LABEL_AUDIT_v1.md`, `paper/HAND_CHECK.md`.
8. **"So the gap is just counting noise?"** No. Noise reproduced it in MANC and not in BANC. Noise of this size can produce such a gap in
   one network; that does not identify the cause. *Files:* `reliability_v2/NOISE.json`, `C_tests.json` C2.
9. **"Your stability result contradicts your earlier null."** The earlier test had three recurring types and could not be informative;
   this one is a second, pre-registered try on a new animal, positive but fragile. *Files:* `replication_v1/S_tests.json`, `C_tests.json` C8.
10. **"We called the screen a discovery tool; you test a use we never claimed."** We quote that framing and say we test something beyond
    it; your choice to follow up only types whose every copy scored high is the kind of check our results support. *Files:*
    `paper/PREPRINT_v1.md` Introduction and Discussion; `research/literature/pugliese_walking_cpg_detailed_notes.md` sections 4.2, 13.

## 4. What you must never claim, and why

- **That the original paper is wrong.** We did not test their rhythm circuit, pruning or experiments; their DNg100 and DNb08 results hold
  up in our hands.
- **That DNg100's recurrence supports anything.** It is built into our calibration.
- **That hits "do not recur" when a test says "at chance".** The tests have little power (about 0.1 to 0.5); "at chance" means not
  distinguishable from chance.
- **That the gap between animals is biological.** The wiring check says part may be reconstruction or matching.
- **That count noise causes the left-right gap.** It reproduced it in one network and not in another.
- **That stability under count noise is a validated way to choose hits.** One fragile positive test of 12 types.
- **That the third animal's tests used the same procedure as the first two.** They used the current sweep, by the pre-registered rule.
- **That the first two animals' hit-list results were pre-registered.** They are post hoc.
- **That the labels were checked by a person,** until you have done the hand check, and then only for the 20 items you checked.
- **That the simulation predicts behaviour better than wiring counts.** It did not, in either test.
