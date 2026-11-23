# Which hits of a connectome simulation hold up? (BrainIR ledger, run 5)

## In one paragraph

A published rate model built from the fly's nerve-cord connectome (Pugliese et al., 2026) screens descending-neuron types for rhythmic
leg activity. Run on a second animal's connectome, its hits mostly do not recur: of 11 hits with a confidently matched counterpart, 2 are
hits again, and **those two are the paper's experimentally supported drivers, DNg100 and DNb08** (**post hoc**: the pattern was seen
before the rule that describes it; DNg100 is the neuron the model was calibrated on, the authors chose DNb08, and two neurons are a tiny
sample). A pre-registered test of whether a hit's stability under synapse-count noise predicts its replication was **not significant**
(p = 0.11; with three replicated types this is not evidence against). We pre-registered 12 experiments with orderable driver lines, and a
rule for reading their results against wiring counts.

## What was tested

Every analysis was frozen, hashed and timestamped before the data or simulations it concerned (rulebook v5, tag `ledger-prereg-v5`).
Our screens reimplement the authors' model, which reproduces their published dynamics; MANC is the first animal, MaleCNS the second (the
authors' network; the screen of it is ours). A driver scores at least 0.5 (the authors' rhythm score).

## Results

**1. Replication across animals (post hoc).** Types with a high-confidence cross-animal match lead; all matched types stand beside them.

| | high-confidence match (215 types) | all matched types (310) |
|---|---|---|
| drivers in MANC / in MaleCNS / in both | 11 / 23 / 2 (1.2 expected by chance) | 15 / 29 / 3 |
| replicated types | DNg100, DNb08 | DNg100, DNb08, DNit013* |
| MANC hits that recur in MaleCNS | 0.18 (95 % interval 0.00-0.44) | 0.20 (0.00-0.43) |
| overlap across animals, as a share of overlap within one | 0.26 (0.00-0.55) | 0.27 (0.04-0.53) |

*DNit013's cross-animal match is low confidence. In the authors' own single-neuron screen, DNg100 and DNb08 are also the only types with a
driver copy whose every copy is a driver.

**2. Stability does not demonstrably predict replication (pre-registered).** In 16 copies of MANC with synapse counts redrawn at Poisson
scale, DNg100 stayed a driver in 16, DNit013 in 12 and DNb08 in 7; three hits that do not replicate were as stable as DNit013. Exact rank
test: **p = 0.11, "not shown"**. The rulebook said in advance that a null here is uninformative.

**3. Why matched neurons disagree.** In the authors' published screen, a neuron's left and right copies agree at 0.63 of the screen's
agreement with itself (0.53-0.72). Two copies of MANC differing only by Poisson noise in synapse counts agree at 0.48 of the ceiling,
left against right 0.47 in the same design: noise of this size is enough to produce the gap. No pre-registered fix closed it.

**4. Blind exams.** The simulation ranked types that drive front-leg rhythm in flies no better than chance (AUROC 0.577, 0.417-0.724)
and no better than counting two-step synaptic paths (0.669); it identified activated hemilineages better than chance (0.633) but no
better than counting (0.638). A pre-registered audit by fresh blind readers upheld exam 1 (3 errors in 39 types, under the 10 % threshold)
and corrected six types that were never in its headline, including **DNg100, whose label was wrong**: one co-activation record decided it.

## What to test next

Switch each type on, both sides, in decapitated flies, and score rhythmic front-leg stepping blind to genotype (protocol in
`forward_v2/README.md`). R = replication reading, S = single-connectome reading, C = counting reading (yes / no).

| Type | Group | R / S / C | Lines listed today (clean) |
|---|---|---|---|
| DNp71 | near-replicated | yes / no / yes | 2 (1) |
| DNa13 | near-replicated | yes / no / no | 3 (3) |
| DNa07 | near-replicated | yes / yes / no | 9 (7) |
| DNa03 | near-replicated | yes / no / no | 1 (0; labels 6 other DNs) |
| DNp41 | MANC-only hit, on the authors' list | no / yes / yes | 2 (0; one also labels DNg100) |
| DNp02, DNg63 | MANC-only hits | no / no / no, yes | 10 (2); 1 (1) |
| DNg13, DNg21 | MaleCNS-only hits | no / no / yes | 5 (4); 4 (4) |
| DNp07, DNg39, DNp26 | controls: non-driver in both, high counting | no / no / yes | 5 (4); 2 (2); 7 (4) |

**Decision rule (fixed now).** For two readings, a reading is supported if it is right on enough of the tested types on which they
disagree to pass a one-sided binomial test at 0.05. Replication against counting can decide on up to 10 types (9 right needed);
single-connectome against counting on up to 8 (7 right needed). Replication against the published single-animal list can only be
inconclusive here: they disagree on just four of these types.

## What this does not show

That a real fly's sides behave differently; that the model is wrong about DNg100's own circuit or the authors' three-neuron rhythm
generator, which they tested across four connectomes; anything about other behaviours or models. Labels come from papers read by
language-model sessions. Full account: `paper/PREPRINT_v0.md`, `results/RESULTS_4.md`, `LABEL_AUDIT_v1.md`.
