# Which hits of a connectome simulation hold up? (BrainIR ledger, run 5)

## In one paragraph

A published rate model built from the fly's nerve-cord connectome (Pugliese et al., 2026) screens descending-neuron types for rhythmic
leg activity. Run on a second animal's connectome, its hits mostly do not recur: of our MANC screen's 11 confidently matched hits, 2 are hits again, and **those two are the paper's experimentally supported drivers, DNg100 and DNb08** (**post hoc**: the pattern was seen before its rule; our calibration guarantees DNg100's replication, so DNb08 is the real test; two is a tiny sample). A pre-registered test of whether a hit's stability under synapse-count noise predicts its replication was **not significant**
(p = 0.11; with three replicated types this is not evidence against). We pre-registered 12 experiments with listed driver lines, and a
rule for reading their results against wiring counts.

## What was tested

Each analysis was frozen, hashed and timestamped before it ran (rulebooks v1-v5), some after data were seen; result 1 is post hoc.
Both screens are ours, reimplementing the authors' model (our MANC hit list differs from theirs); MANC is the first animal, MaleCNS (their network) the second. A driver scores at least 0.5 (the authors' rhythm score).

## Results

**1. Replication across animals (post hoc).** Types with a high-confidence cross-animal match lead; all matched types stand beside them.

| | high-confidence match (215 types) | all matched types (310) |
|---|---|---|
| drivers in MANC / in MaleCNS / in both | 11 / 23 / 2 (1.2 expected by chance) | 15 / 29 / 3 |
| replicated types | DNg100, DNb08 | DNg100, DNb08, DNit013* |
| MANC hits that recur in MaleCNS | 0.18 (95 % interval 0.00-0.44) | 0.20 (0.00-0.43) |
| overlap across animals, as a share of overlap within one | 0.26 (0.00-0.55) | 0.27 (0.04-0.53) |

*DNit013's match is low confidence. In the authors' single-neuron screen only DNg100 and DNb08 of two-sided types have every copy a driver; in our MaleCNS runs no DNb08 copy is.

**2. Stability does not demonstrably predict replication (pre-registered).** In 16 copies of MANC with synapse counts redrawn at Poisson
scale, DNg100 stayed a driver in 16, DNit013 in 12 and DNb08 in 7; three hits that do not replicate were as stable as DNit013. Exact rank
test: **p = 0.11, "not shown"**. The rulebook said in advance that a null here is uninformative.

**3. Noise can mimic the side gap.** In the authors' published screen, which reads both legs, left and right copies agree at 0.63 of its self-agreement (0.53-0.72). Two copies of MANC differing only by Poisson noise in synapse counts agree at 0.48 of the ceiling,
left against right 0.47 in the same design: noise of this size can produce such a gap. No fix that ran passed.

**4. Blind exams.** The simulation ranked types that drive front-leg rhythm in mostly intact flies no better than chance (AUROC 0.577, 0.417-0.724) or than two-step path counts (0.669); it ranked activated hemilineages above chance (percentile 0.633), no better than counting (0.638). A pre-registered audit by readers blind to exam 1 upheld it (3 errors in 39 types, under the 10 % threshold) with an erratum for six types never in its headline, including **DNg100, whose label was wrong**: one co-activation record decided it.

## What to test next

Switch each type on, both sides, in decapitated flies, and score rhythmic front-leg stepping blind to genotype (protocol in
`forward_v2/README.md`). R, S, C = replication (post hoc groups), single-connectome, counting reading (yes / no).

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
disagree to pass a one-sided binomial test at 0.05. Replication against counting needs 9 right of up to 10 types, single-connectome 7 of 8 (power 0.38 and 0.50 if a reading is 80 % right). Replication against the published single-animal list can only be
inconclusive here: they disagree on just four of these types.

## What this does not show

That replicated hits are real; that a real fly's sides behave differently; that the model errs on DNg100's circuit or the authors' three-neuron rhythm generator, which they tested across connectomes; other behaviours or models. Labels come from papers read by
language-model sessions. Full account: `paper/PREPRINT_v0.md`, `results/RESULTS_4.md`, `LABEL_AUDIT_v1.md`.
