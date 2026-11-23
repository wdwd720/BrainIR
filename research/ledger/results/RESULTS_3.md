**Cause found in part: Poisson-scale noise in synapse counts moves the model's predictions almost as much as the real left-right differences do.** Two copies of one network that differ only by such noise agree almost as poorly as the fly's left and right sides (0.40 against 0.37 for the pre-registered pair; over all six pairings of the four stored noise copies, a post-hoc check by the adversarial review, noise reproduces about 86 % of the gap); the left-right difference is carried most by connections that the 5-synapse floor leaves on one side only and by neurons without a partner; where the tuner lands explains about a third in MaleCNS (part of it through lower seed noise) and an amount indistinguishable from zero in MANC; and none of the fixes tested restores reproducibility.

# Results 3 (run 4): does the simulation agree with itself across the two sides of a fly and across two flies, and why not?

Pre-registered in `PREREG_v4.md` (tag `ledger-prereg-v4`, commit badc4d7; `LOCK_prereg_v4.json` sha256 fd34d9f7...19ad4; OpenTimestamps
proofs complete). Every number below is read from a file under the reliability lock (`LOCK_reliability_v2.json`, tag
`ledger-reliability-v2`) or, for Part E, the forward lock (`LOCK_forward_v1.json`, tag `ledger-forward-v1`), except two kinds, marked
where they appear: the Part D rows marked post-lock are exploratory and outside both (their hashes are in LOG L148), and the six-pair
noise figures are the adversarial reviewer's post-hoc analysis (`reviews_v4/ADVERSARIAL_REVIEW_v4.md`, under no lock). Both gaps had
been seen in run 3 before the freeze (left vs right on MANC seeds 0..3, which Part A reuses, and cross-fly; `PREREG_v4.md` Part Q
lists every number seen); result 1 (A0) had not been computed. Model seeds: 16 in Part A, 8 (0..7) in Parts B and C, always the same seeds on the
two sides of a comparison.

**How agreement is measured (G5-G7).** For each type, the type score is its mean rhythm score over usable replicates. Agreement
between two screens is the cross-half Spearman correlation of type scores (rho_x: one screen's first half of the seeds against the
other screen's second half, and vice versa). The ceiling c is the split-half agreement of each screen with itself on the same seeds,
so seed noise sets the ceiling. Ratio = rho_x / c, with a 10,000-resample bootstrap over types. Verdict words: "at the ceiling"
(ratio >= 0.90 and the interval reaches 1), "inconclusive" (ratio < 0.90, interval reaches 1), "a real gap" (interval below 1),
"not judged" (c < 0.2). The closure of a gap by an intervention is (rho_x after - rho_x before) / (c before - rho_x before), with a
bootstrap interval. It is read only when the before-pair is a real gap.

## 1. The authors' own scores (Part A0, no simulation)

The authors' published single-neuron screen (A0: one descending neuron stimulated, both front legs read out, 128 replicates). Left
copy against right copy of the same type; the ceiling splits each neuron's replicates in two (0-63 against 64-127).

| screen | types | rho_x (95 %) | ceiling c | ratio (95 %) | verdict | drivers that replicate | band kappa | top-30 overlap |
|---|---|---|---|---|---|---|---|---|
| authors' (A0), one member per side | 250 | 0.597 (0.502-0.684) | 0.951 | **0.628 (0.531-0.718)** | a real gap | 13 % (1 of 7; 1 of 8) | 0.47 | 0.43 |
| authors' (A0), all matched types | 308 | 0.596 (0.510-0.673) | 0.955 | 0.624 (0.536-0.704) | a real gap | 21 % | 0.49 | 0.47 |
| ours (B0, 16 replicates), one member per side | 250 | 0.522 (0.415-0.622) | 0.860 | 0.607 (0.489-0.715) | a real gap | 13 % | 0.39 | 0.47 |

**Reading.** In the authors' own published scores, a neuron's left copy predicts its right copy at about 63 % of the level at which
the screen predicts itself, and only about one driver in seven or eight is a driver on both sides. Their screen reads out both legs
together, so the left-right disagreement is not an artefact of our one-sided procedure or of our code.

## 2. The gap (Part A, 16 seeds, primary homolog-consistent types)

| pair | types | rho_x | ceiling c | ratio (95 %) | verdict | drivers that replicate | wiring: two-hop signed | wiring: two-hop unsigned |
|---|---|---|---|---|---|---|---|---|
| MANC left vs right | 307 | 0.500 | 0.852 | **0.587 (0.485-0.681)** | a real gap | 18 % | 0.84 | 0.96 |
| MaleCNS left vs right | 219 | 0.571 | 0.890 | **0.642 (0.528-0.741)** | a real gap | 30 % | 0.78 | 0.96 |
| MANC-L vs MaleCNS-L | 215 | 0.356 | 0.868 | 0.410 (0.274-0.535) | a real gap | 37 % | 0.78 | 0.96 |
| MANC-R vs MaleCNS-R | 215 | 0.277 | 0.876 | 0.317 (0.180-0.447) | a real gap | 7 % | 0.73 | 0.94 |
| MANC-L vs MaleCNS-R | 215 | 0.268 | 0.844 | 0.317 (0.172-0.458) | a real gap | 19 % | 0.81 | 0.94 |
| MANC-R vs MaleCNS-L | 215 | 0.446 | 0.899 | 0.496 (0.373-0.607) | a real gap | 29 % | 0.71 | 0.95 |
| reference: whole type, MANC vs MaleCNS (R1) | 310 | 0.340 | 0.893 | 0.380 (0.265-0.487) | a real gap | 15 % | | |

Wiring columns: Spearman over the same types of the type-level two-hop summaries (A4; deterministic, so their ceiling is 1). The
other five wiring summaries agree at 0.79-0.98 across sides and 0.79-0.97 across flies.

- **Neither side is worse everywhere** (A3): MANC 16 vs 18 drivers (left vs right), type scores paired by type Wilcoxon p = 0.86;
  MaleCNS 30 vs 19 drivers, p = 0.31.
- **The left-right difference is not shared across flies**: same-side minus opposite-side cross-fly agreement -0.04 (-0.10 to +0.02).
- **Side labels and homologs** (G3): on the MaleCNS types whose side annotation needed no correction (127) the left-right ratio is
  0.61, on MANC's side-concordant types (260) 0.58; all matched types (secondary) give the same values to two decimals.
- **Single connections differ although summaries agree** (A4): about half of the homologous connections between matched neurons exist
  on one side only (MANC 51 %, MaleCNS 52 %); 68 % of MANC's one-sided connections have 1-4 synapses on the other side (below the
  5-synapse floor); log counts of connections present on both sides correlate at 0.71 (MANC) and 0.68 (MaleCNS). Across flies, 58 %
  of type-to-type connections exist in one fly only (Spearman 0.74 over the shared ones).
- **Hemilineages** (A5, run 3's sensitivity groups): left vs right ratio 0.86. **DNg100's own per-leg asymmetry** is strong and the
  same in the authors' runs and ours (median leg scores L/R, T1 0.89/0.69 against our 0.94/0.78).

**Reading.** The simulation's left and right halves agree at only 59 % (MANC) and 64 % (MaleCNS) of the agreement that seed noise
allows, and the two flies at 32-50 %, while the wiring summaries agree at 0.71-0.98. The gap is real, it is in both flies, it does
not come from one bad side, and it is not the same gap in both flies.

## 3. Causes (Part B)

### 3.1 Procedure (Block 1: dose sweep, matched currents, current transplant; 8 seeds, cut analysed set)

| | MANC (261 types) | MaleCNS (203 types) |
|---|---|---|
| tuned screen, left vs right (before) | ratio 0.52 (rho_x 0.40, c 0.77) | 0.58 (0.49, 0.85) |
| **best in-bounds score over the 19-current grid** (B1.4 primary) | ratio 0.55 (0.43-0.66; c 0.84); **closure 0.17 (-0.07 to 0.38)** | 0.65 (0.55-0.75; c 0.95); **closure 0.36 (0.08 to 0.61)** |
| fraction of in-bounds currents rhythmic | closure 0.22 (-0.08 to 0.51) | -0.11 (-0.57 to 0.22) |
| left vs right at each fixed current | a real gap at all 19 (ratio 0.38-0.81) | a real gap at 12 of 19 (0.34-0.69); 2 inconclusive (22.6 and 32), the 5 lowest not judged |
| each side at the other side's tuned current | closure -0.16 / -0.27 (intervals include 0) | 0.00 / -0.12 (include 0) |
| run at the own tuned current reproduces the tuned run | 3,049 of 3,049 | 2,640 of 2,640 |

**Reading.** Where the tuner lands explains about a third of the gap in MaleCNS (interval 0.08-0.61) and an amount indistinguishable
from zero in MANC. Part of that closure is lower seed noise: the grid score's ceiling rises (MaleCNS 0.85 to 0.95, MANC 0.77 to 0.84),
and against its own ceiling left-right agreement rises only from 0.58 to 0.65 (MaleCNS) and from 0.52 to 0.55 (MANC). The two sides disagree at all 19 fixed currents in MANC and at every conclusive one in MaleCNS (12 of 19), and
giving both the same current does not bring them together. The difference is
mostly in the two networks.

### 3.2 Location (Block 2: the stimulated types' own output connections vs the rest of the network; paired draws)

Sanity (B2.3), checked before any other Block 2 number was read: transplanting left into left leaves all 50 sampled jobs identical
(both flies); the fully mirrored network reproduces the right-side screen (same tuner outcome in 2,094 of 2,096 MANC and 1,960 of
1,960 MaleCNS replicates; type-score Spearman 0.9999 and 0.994, against 1.000 for a pure relabelling of the network). Passed.

| | MANC (261 types) | MaleCNS (203 types) |
|---|---|---|
| before: left on W vs right on W (paired draws) | ratio 0.47 (rho_x 0.37, c 0.79), a real gap | ratio 0.59 (rho_x 0.51, c 0.87), a real gap |
| stimulated type's own output connections mirrored (H_own) | closure 0.23 (-0.01 to 0.42) | 0.17 (-0.13 to 0.40) |
| rest of the network mirrored (H_rest) | **closure 0.34 (0.10 to 0.53)** | 0.21 (-0.08 to 0.46) |

**Reading.** The difference is not in one place. The downstream network carries about a third of it in MANC and the stimulated
neurons' own outputs about a fifth; the two closures sum to 0.4-0.6, while mirroring both gives 1, so the two parts interact.

### 3.3 Class of wiring difference (Block 3, MANC; paired draws)

Closure of the MANC left-right gap (ratio 0.47) when one class of feature is replaced by its mirrored right-side value, alone or
together with all other classes (left out):

| class | mirrored alone | all mirrored but this one |
|---|---|---|
| 1. weights of connections present on both sides | 0.09 (-0.11 to 0.26) | 0.55 (0.33 to 0.72) |
| 2. connections present on one side only | **0.29 (0.06 to 0.49)** | **0.37 (0.16 to 0.56)** |
| 3. neurons with no partner on the other side | **0.25 (0.06 to 0.42)** | 0.58 (0.40 to 0.74) |
| 4. neuron size | 0.03 (-0.16 to 0.20) | 0.81 (0.66 to 0.95) |
| 5. transmitter sign | -0.05 (-0.17 to 0.07) | 0.88 (0.73 to 1.01) |

**Reading.** No single class closes the gap. Connections that exist on one side only and neurons without a partner carry the most
(the only alone-closures above 0). By the pre-registered reading (B3.3) the homologous weights and neuron size also contribute, in
combination only: left out, they leave a part of the gap (0.55 and 0.81, both upper ends below 1), and their alone and left-out
readings disagree; size's part is small. Sign does not contribute (left out 0.88, upper end 1.01). The alone-closures sum to 0.61, so
the classes interact. The MaleCNS repeats were dropped under the pre-registered budget rule (X9), so this block is MANC only.

### 3.4 Count noise (MANC; paired draws)

The raw synapse counts exist for MANC only (MaleCNS is published already floored at 5), so this block is MANC only.

| | agreement rho_x (95 %) | observed left-right minus the model |
|---|---|---|
| observed: left vs right (paired draws) | 0.37 (ratio 0.47) | |
| two Poisson resamplings of the raw counts, floor 5 applied after | 0.40 (0.29-0.51) | -0.03 (-0.16 to +0.10) |
| two negative-binomial resamplings, dispersion measured from left-right homologous pairs (1/k = 0.027, 475,462 pairs) | 0.45 (0.35-0.55) | -0.08 (-0.21 to +0.05) |
| floor lowered to 1, left vs right | 0.47 (ratio 0.57; closure 0.23, -0.01 to 0.44) | |

**Reading.** Two copies of the same network that differ only by Poisson-scale noise in their synapse counts disagree with each other
almost as much as the left side disagrees with the right. The adversarial review (`reviews_v4/ADVERSARIAL_REVIEW_v4.md`, post hoc)
found the pre-registered Poisson pair to be a low draw: over all six pairings of the four stored copies, copies agree at 0.38-0.54
(mean 0.46), so noise reproduces about 86 % of the gap (0.66-1.14), not demonstrably all of it (answer: `ADVERSARIAL_ADDENDUM_v4.md`). No parameter was fitted: the Poisson model has none, and the negative-binomial dispersion comes
from the left-right count pairs themselves. Lowering the floor to 1 recovers about a quarter of the gap (the interval just reaches 0).
The floors of 3 and 10 were dropped under the budget rule.

### 3.5 Rescue table (single interventions; a flipped type changes band and fraction rhythmic by at least 0.5 between sides)

| design | flips | share rescued by each single intervention |
|---|---|---|
| MANC, paired draws | 13 | rest of network mirrored 69 %; floor 1 69 %; one-sided connections 54 %; own outputs 46 %; size 46 %; homologous weights 38 %; unmatched neurons 23 %; sign 15 % |
| MANC, Part A design | 19 | fraction rhythmic over the grid 63 %; best in-bounds 37 %; current transplant 32 % |
| MaleCNS, paired draws | 29 | rest of network mirrored 62 %; own outputs 41 % |
| MaleCNS, Part A design | 32 | fraction rhythmic 47 %; best in-bounds 44 %; current transplant 12 % |

## 4. Fixes (Part C; unpaired, seeds 0..7, cut analysed set, primary types)

A fix "restores reproducibility" only if all four hold: (1) DNg100 scores >= 0.5 in >= 12 of 16 seeds (at a gain chosen on DNg100
alone); (2) cross-fly agreement >= 0.8 of its ceiling (c >= 0.2), and left-right too where the fix keeps the sides distinct; (3) mean
driver count between half and double the unfixed screen's (21.25); (4) specific reproducibility (cross-fly agreement minus agreement
with the fly's own degree-preserving rewiring) above 0 with its interval, and at most 2 driver types in the rewired control.

| fix | 1 control | 2 cross-fly ratio | 2 left-right ratio | 3 drivers | 4 SR (95 %) / rewired drivers | restores? |
|---|---|---|---|---|---|---|
| unfixed model | yes | 0.32 | 0.55 | 21.25 | 0.31 (0.14-0.49) / 16 | (reference) |
| 1 dose-sweep scoring | yes | 0.31 | 0.61 | **46.5 (> 2x)** | 0.26 (0.08-0.43) / **2** | no |
| 2 pooled read-out | yes | 0.33 | 0.54 | 31.0 | 0.34 (0.16-0.51) / 20 | no |
| 3a floor 1 | yes | not evaluable (no pre-floor MaleCNS counts) | 0.56 | 20.5 | not evaluable (no rewired control at a floor) | no |
| 3b floor 3 | dropped under the budget rule (X9) | | | | | not tested |
| 4 symmetrised | yes | 0.39 | 0.76 (not required) | 22.25 | 0.36 (0.19-0.52) / 4 | no |
| 5a type-pooled within side | yes | 0.39 | 0.57 | 23.75 | 0.45 (0.27-0.62) / 20 | no |
| 5b type-pooled across sides | yes | 0.38 | 0.61 (not required) | 23.75 | 0.39 (0.21-0.56) / 8 | no |
| 6 input-normalised | **no** (fails DNg100 at every gain) | | | | | no |
| 7 consensus annotations | yes | 0.32 | 0.50 | 20.75 | 0.35 (0.16-0.53) / 15 | no |
| 8 all network fixes | **no** (fails DNg100 at every gain) | | | | | no |
| 9 combined | not run (needs a passing procedure-level and network-level fix) | | | | | no |

**Reading.** No fix restores reproducibility. Every fix that keeps DNg100 working leaves the two flies agreeing at only 0.31-0.39 of
the ceiling, far below 0.8. The predictions do depend on the wiring (specific reproducibility is above 0 for every evaluable fix), but
not reproducibly. Criterion 4's "few" (at most 2 rewired drivers) was set from run 1's whole-type controls; the one-sided screen's
rewired controls give 4-20 drivers, so criterion 4 is met by fix 1 alone. Because no fix passed, the forward ledger has two sources.

## 5. Exams re-scored (Part D) — EXPLORATORY, after unblinding

Each variant scored once with run 2's frozen exam 1 pipeline (39 labelled types, 25 "yes"; AUROC with a 10,000-resample bootstrap).
Exam 1 was unblinded in run 2; these rows are not evidence for or against any fix. Fix 2's row comes from the locked
`results/run4/EXAM1_2.json`; the other rows were computed after the reliability lock, when the user allowed more compute for the
whole-type screens that the budget rule had dropped (`results/run4_postlock/`, LOG L145-L146). References on the same seeds 0..7:
the unfixed model (our replication) 0.43 (0.26-0.61); two-step signed counting 0.67 (0.44-0.87).

| fix | exam 1 AUROC (95 %) | minus unfixed (95 %) | minus counting (95 %) | source |
|---|---|---|---|---|
| 2 pooled read-out | 0.50 (0.37-0.63) | +0.07 (-0.05 to +0.19) | -0.17 (-0.42 to +0.11) | locked |
| 4 symmetrised | 0.47 (0.30-0.62) | +0.03 (-0.16 to +0.22) | -0.20 (-0.46 to +0.07) | post-lock |
| 5a type-pooled within side | 0.47 (0.29-0.65) | +0.04 (-0.09 to +0.17) | -0.20 (-0.48 to +0.10) | post-lock |
| 5b type-pooled across sides | 0.46 (0.28-0.63) | +0.02 (-0.11 to +0.16) | -0.21 (-0.49 to +0.08) | post-lock |
| 7 consensus annotations | 0.52 (0.36-0.68) | +0.09 (-0.02 to +0.20) | -0.15 (-0.42 to +0.13) | post-lock |
| 1 dose-sweep scoring | 0.41 (0.23-0.58) | -0.03 (-0.19 to +0.13) | -0.26 (-0.51 to -0.01) | post-lock |
| 3a floor 1, 3b floor 3 | not re-scored (whole-type screens dropped: budget) | | | |
| 6, 8 | not re-scored (failed the DNg100 control) | | | |
| 9 | not run | | | |

Exam 2 is not re-scored: it was reserved for the robust model, and no fix passed. **Reading (exploratory):** no fix moves exam 1 by more than its interval; every fix stays below two-step counting, significantly so for fix 1.

## 6. The forward ledger (Part E)

63 descending-neuron types with a kit driver line and no clear exam 1 label, two sources (the authors' model and two-step signed counting; no fix passed, so there is no robust model: `forward/SOURCES_NOTE.md`). Each score becomes a probability of rhythmic front-leg stepping in a decapitated fly by a one-variable logistic fit to exam 1's 39 labelled types (training on past results to predict future ones; only 6 are headless-labelled, so all labelled types are the fit set). Leave-one-out calibration is weak: Brier 0.248 for the model and 0.239 for counting, against 0.242 for the base rate; AUROC 0.33 and 0.61; 21 of exam 1's 25 'yes' types rest on the intact-fly atlas alone. The 15 decisive experiments (`forward/DECISIVE.csv`) separate the sources by 0.05-0.28 in probability; 34 of their 59 lines are listed as available (`forward/AVAILABILITY.csv`). The authors' screen gives 9 of the 15 a score of 0 (none is a driver; highest 0.13), which the fit maps to 0.59, near the base rate (0.641), so for these types the comparison tests the calibration rather than the screen's own call; and 7 of the available lines have at least one kit record naming another descending-neuron type (`kit_v2/driver_lines.csv`), so a positive result from them may reflect joint activation. A fresh reviewer checked ten entries by hand: ten of ten agree. These predictions are made after both exams were unblinded; they are clean with respect to the experiments they predict, because those have not been done.

## 7. Alternative explanations of the left-right gap

| explanation | test (rulebook) | what it showed |
|---|---|---|
| seed noise | matched split-half ceilings on the same seeds (G6) | ceilings 0.85 (MANC) and 0.89 (MaleCNS); agreement reaches only 59 % and 64 % of them, intervals below 1 |
| ties among zero scores | agreement over types non-zero in at least one half (G6a) | lower, not higher: 0.27 (MANC, 217 types) and 0.20 (MaleCNS, 130) against 0.51 and 0.60 over all types; zero-zero ties inflate agreement |
| the one-sided regime being noisier in itself | Part A's one-sided ceilings against R1's whole-type ceiling | one-sided ceilings 0.85-0.90, whole-type 0.89: not noisier |
| mismatched homologs or wrong side labels | G3 side checks, the uncorrected / side-concordant subsets, Block 2's full-transplant check (B2.3) | MaleCNS uncorrected-side types 0.61, MANC side-concordant types 0.58 (as all types); the mirrored network reproduces the other side (Spearman 0.994-0.9999) |
| unequal member counts | types with equal member counts on both sides (G6b) | MANC 0.51 (285 types), MaleCNS 0.59 (198): unchanged |
| one side worse everywhere | score distributions, driver counts, tuner outcomes (A3) | neither side (Wilcoxon p 0.86 and 0.31) |
| where the tuner lands | Block 1 | about a third in MaleCNS (0.36, 0.08-0.61), not distinguishable from 0 in MANC (0.17); the sides disagree at all 19 fixed currents in MANC and at the 12 conclusive ones in MaleCNS |
| our implementation | the authors' own scores (A0) against ours; Block 2's mirror checks | the authors' published scores show the same gap (ratio 0.63); our identity and full transplants reproduce exactly |

## 8. Three biggest caveats

1. **The attributions are partial and their intervals wide.** Most single-intervention closures have intervals that include 0, and the
   closures of separate parts sum to 0.4-0.6 where all parts together give 1, so the classes interact and cannot be read as a
   decomposition. The count-noise result shows that Poisson-scale count noise is enough to produce most of a gap this size with no fitted
   parameter (the pre-registered pair is a low draw; pooled over six copy pairings, about 86 %); it does not show that the real
   left-right differences are count noise.
2. **The mechanism results rest on MANC.** Count noise and floors need pre-floor counts, which exist only for MANC; Block 3's MaleCNS
   repeats, floors 3 and 10, fix 3b and Part D's whole-type screens were dropped under the pre-registered budget rule (X9) once the
   runner-hour projection passed 280 (five of those screens were run after the lock, when the user allowed more compute, and are
   reported as exploratory), and the analysed set's random part was cut from 41 to 25 types (an exploratory comparison on all 278 types
   changes no verdict).
3. **The Part C bar is strict, and one control was set on another regime.** Criterion 2 asks for 0.8 of the ceiling; criterion 4's
   "few" rewired drivers (2) came from run 1's whole-type controls, while the one-sided rewired controls give 4-20, so criterion 4 was
   nearly out of reach for any one-sided fix. Every number is in the table, so another bar can be applied. The forward ledger's
   calibration is weak (the authors' model is no better than the base rate in leave-one-out; counting only slightly better) and
   inherits exam 1's atlas caveat.

## 9. Where everything is

- Rulebook: `research/ledger/PREREG_v4.md`; tag `ledger-prereg-v4` (badc4d7), `LOCK_prereg_v4.json` (sha256 fd34d9f7...19ad4), Bitcoin-attested
  OpenTimestamps proofs. Amendments 1-7 with reasons: `research/ledger/AMENDMENTS_v4.jsonl`.
- Results of Parts A0-D: `research/ledger/reliability_v2/` (A0, A, WIRING_A4, A5, ANALYSED_SET[_X9], B1_*, B2_*, B3_MANC, NOISE, RESCUE,
  C_FIXES_1_TO_8, C), `research/ledger/results/run4/` (EXAM1_2, EXPLORATORY_X9_FULLSET, COMPUTE_v4, the figure), gates in
  `research/ledger/gates_v4/`; tag `ledger-reliability-v2`, `LOCK_reliability_v2.json` (sha256 02ca7209...b542).
- Forward ledger: `research/ledger/forward/`; tag `ledger-forward-v1`, `LOCK_forward_v1.json` (sha256 f62da273...4917).
- Part D re-scores made after the reliability lock (exploratory): `research/ledger/results/run4_postlock/` (hashes in LOG L148).
- Decisions, departures and every incident: `research/ledger/LOG.md` rows L104-L150. Compute: GitHub 288.9 of 300 runner-hours (plus about 0.3 for the post-lock
  determinism sample); Modal $36.17 logged of the $41 the user allowed.

