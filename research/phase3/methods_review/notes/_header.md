# METHODS_REVIEW: methods for discovering compact, causal, closed state variables of simulated populations

Phase 3 methods-only literature review. Task specification: `CONTRACT.md`. This document covers methodology only. It
names no biological circuit, organism, connectome or dataset.

## 0. How to read this document

**Structure.**
- **Section 1** gives a one-page overview: a method-by-property matrix and the headline conclusions.
- **Part I (Sections A-G)** has one entry per method. Each entry has every contract field: core idea, assumptions,
  identifiability, intervention support, nonlinear capacity, interpretability, scaling, failure modes, relevance to
  properties (1)-(8), open-source implementations (package, maturity, licence) and from-scratch simplicity, plus the
  references read for that entry. The seven areas are:
  - A. Classical system identification, minimal realisation, subspace ID, balanced reduction, observability, delay
    methods, nonlinear system ID, order selection.
  - B. Koopman operator learning, DMD family, transfer-operator methods, deep Koopman, SINDy family, operator inference.
  - C. Predictive state representations, causal states and computational mechanics, predictive information, bisimulation
    and lumpability, RL state abstraction, CEGAR and active automata learning.
  - D. Neural state-space models, variational SSMs, world models, neural ODEs/CDEs/SDEs, sequence models, contrastive
    and self-predictive objectives, switching models, dynamical-systems reconstruction.
  - E. Nonlinear ICA and temporal identifiability, interventional causal representation learning, multi-view and
    contrastive identifiability, invariance (ICP, IRM), formal causal abstraction, interchange interventions, dynamic
    SCMs, time-series causal discovery.
  - F. Population-dynamics latent-variable methods, low-rank RNNs, fixed-point analysis, dynamical similarity (DSA,
    conjugacy), representational similarity (CCA, CKA, shape metrics), dimensionality estimation.
  - G. Optimal and Bayesian experiment design, persistency of excitation, active learning, phase reduction and PRCs,
    isostables, continuation and bifurcation, spectral submanifolds, evaluation of reconstructed dynamics.
- **Part II** is the synthesis:
  - II.1 cross-cutting conclusions;
  - II.2 the common interface and data protocol;
  - II.3 eight tournament families with concrete recipes;
  - II.4 baselines and how to implement each well;
  - II.5 evaluation measures for properties (1)-(8);
  - II.6 pitfalls and countermeasures;
  - II.7 open problems.
- **Part III** is the consolidated reference list, grouped by area, with a verification tag on every item.
- **Appendix** reproduces the detailed per-area synthesis notes (area-level recipes, hyperparameters and pitfalls) that
  Part II condenses.

**Verification tags** (used on every reference):
- `[read-full]`: substantial body text was read. Often this was the arXiv HTML read through a summarising fetch tool, so
  equations were not checked line by line.
- `[read-abstract]`: the abstract or landing page was read.
- `[repo/docs]`: the code repository, LICENSE file or documentation was read.
- `[unverified]`: the source could not be opened, and the bibliographic data comes from search results or memory.

Statements inside entries that could not be traced to an opened source are marked "(unverified)". Licences were read from
LICENSE files or repository metadata where possible; otherwise the entry says "licence not verified". Star counts and
maintenance status are approximate as of September 2026.

**Coverage statistics.** Part I has about 110 method entries. The reference list has 324 unique sources: 48 [read-full],
45 [repo/docs], 179 [read-abstract] and 52 [unverified]. Most method claims therefore rest on abstracts plus
documentation. The synthesis relies on claims that are either standard or were checked in [read-full] sources. Where it
relies on weaker evidence, it says so.

**The eight contract properties**, abbreviated throughout:
- (1) predictive sufficiency over multiple horizons;
- (2) Markov closure;
- (3) interventional sufficiency, including unseen intervention types and targets;
- (4) microstate invariance;
- (5) minimal dimension;
- (6) stability across seeds and estimators;
- (7) one shared f across implementations, with implementation-specific encoders;
- (8) abstention when no compact state exists.

---

## 1. Overview

### 1.1 Headline conclusions

1. **Properties (2), (4) and (5) together define a well-studied object.** It appears as:
   - the Nerode/minimal-realisation state (area A);
   - the causal state or predictive state (area C);
   - the coarsest bisimulation or lumping (area C).

   Because the simulator can be **reset to any microstate x**, the definition can be applied to microstates directly:
   x ~ x' iff their futures agree in law under every allowed input sequence and intervention. Many methods in the
   literature only approximate this relation from histories. We can test it directly, and that should drive the design:
   evaluate by paired re-simulation, and train with counterexamples.
2. **No method family delivers all eight properties by construction.** Neural latent models (D, much of B) are flexible
   function classes that give none of (2)-(8) for free. Classical methods (A) give (2), (4), (5) and (6) exactly, but only
   for linear systems. Identifiability theory (E) gives (6) and parts of (3), but under assumptions that our setting
   violates. Micro interventions have unknown, multi-node, graded effects at the macro level. Properties (3), (4), (7) and
   (8) must therefore come mostly from the **training and evaluation protocol**: encode once and roll out, sweep k,
   re-simulate paired microstates, hold out intervention types, train with multiple encoders and one f, and set
   calibrated abstention thresholds. The protocol matters more than the architecture.
3. **The strongest tournament families** (Section II.3) are:
   - closed "encode once, roll out" latent dynamics with a ladder of transition classes;
   - subspace and Koopman linear-operator identification with interventions as inputs;
   - interventional empirical-gramian balanced reduction;
   - microstate predictive-state regression on a probe bank;
   - interchange-intervention-trained abstraction;
   - unit-space low-rank RNNs;
   - multi-encoder shared-f training;
   - a counterexample-guided refinement and abstention wrapper.
4. **Structural interventions** (removing units or connections) break every method that assumes a fixed f. Only models
   that keep a micro-level parameterisation can express them natively, for example low-rank RNNs in unit space or
   parametric/Galerkin reductions. Other methods need an explicit descriptor-conditioned f. Evaluate these interventions
   as a separate held-out class and allow the model to declare them outside its intervention set.
5. **Dimension cheating is real.** A single real coordinate can encode arbitrarily much information through a
   pathological (space-filling, high-Lipschitz) encoder. Every nonlinear method needs Lipschitz or noise-injection
   control on phi and f, and every k must be reported together with a smoothness or robustness curve. Otherwise "minimal
   k" is meaningless.
6. **Comparing latents up to transformations** needs a battery of measures, calibrated against controls of known
   similarity. No single number suffices:
   - predictive cross-mapping (the best single test of (7));
   - spectral and conjugacy invariants;
   - shape metrics with a stated invariance class;
   - principal angles;
   - CKA, as a secondary check only.

### 1.2 Method-by-property matrix (reviewer's judgement, based on the Part I entries)

Legend:
- `++` provided by construction or directly targeted;
- `+` partially, or with the right protocol;
- `0` not addressed (the protocol must supply it);
- `-` the method tends to work against the property.

Column "N~5k" gives feasibility at N ~ 5,000 units. Column "Impl" gives from-scratch difficulty: S = simple, M = moderate,
H = hard.

| Method (area) | 1 pred | 2 Markov | 3 interv | 4 invar | 5 minimal | 6 stable | 7 shared | 8 abstain | nonlinear | N~5k | Impl |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ho-Kalman / ERA (A) | + (lin) | ++ | + (inputs) | ++ (lin) | ++ | ++ | + | + (no SV gap) | no | ok (SVD) | S |
| N4SID / MOESP / CVA (A) | + (lin) | ++ | + (inputs) | + | ++ | ++ | + | + | no | needs PCA | M |
| PSID (A) | + | + | + (IPSID) | + | ++ (readout vs full) | ++ | + | + | no | needs PCA | M |
| Balanced truncation / empirical gramians (A, G) | + | + | ++ (designed) | ++ (obs.) | ++ (HSV) | ++ | + | + | local | 2N runs | S-M |
| Delay / Hankel / HAVOK (A, B) | + | - (history) | + (HDMDc) | 0 | + | + | + | + | via lift | ok | S |
| NARX / Volterra / GP-SSM (A) | + | - (I/O only) | + (inputs) | 0 | + | + | 0 | 0 | yes | poor | M |
| LDS-EM / FA / GPFA (A, F) | + | + | + (B u) | + | + (CV) | + (init) | + | 0 | no | ok | M |
| DMD / fbDMD / BOP-DMD (B) | + (lin) | + | 0 | + | + | ++ (spectra) | + (spectra) | + | no | ok | S |
| DMDc / ioDMD (B) | + | + | + | + | + | + | + | + | no | ok | S |
| EDMD / kernel DMD / ResDMD (B) | + | + (ResDMD check) | + (EDMDc) | + | - (lift dim) | + | + (spectra) | + | yes | needs PCA | S-M |
| VAMP / VAMPnets / TICA (B) | + | ++ (CK test) | 0 | + | + (VAMP-E) | + | + | + | yes | ok | M |
| Deep Koopman AE (B) | + | + | + (B, re-encode) | + | + | - (seeds) | + | + | yes | ok | M |
| SINDy / SINDYc / E-SINDy (B) | + | + | + | 0 | + (sparsity) | + (E-SINDy) | + (shared Xi) | + | yes (library) | needs PCA | S |
| SINDy autoencoder (B) | + | + | + | + | + | - (seeds) | + (shared Xi) | + | yes | ok | M |
| Operator inference (B) | + | ++ (re-projection) | + | + | + | + | 0 | + | quadratic | ok | S |
| PSR / spectral / 2SR (C) | ++ (def.) | ++ | + (actions) | ++ (def.) | ++ (rank) | + | 0 | + (rank) | kernel | M | M |
| Causal states / CSSR / eps-transducer (C) | ++ | ++ | + (inputs) | ++ | ++ | + | 0 | ++ (states vs L) | discrete | poor | M |
| DCA / past-future IB / CPIC (C) | + | + | 0 (no inputs) | + | + (I_pred curve) | + | 0 | + | DCA linear | ok | S-M |
| Bisimulation / lumpability / partition refinement (C) | + | ++ | + | ++ | ++ | + | + (between systems) | + | discrete | via clustering | M |
| DBC / MICo / DeepMDP / ZP encoders (C, D) | + | + | + (actions) | + | 0 | - | 0 | 0 | yes | ok | M |
| CEGAR / L* active automata (C) | + | ++ | + | ++ | ++ | + | 0 | ++ | discrete | via abstraction | M-H |
| DKF / VRNN / SRNN / KVAE / DVBF (D) | + | 0 / - (history) | + (actions) | 0 | 0 | - | 0 | + (noise level) | yes | ok | M |
| RSSM / Dreamer (D) | ++ | - (h channel) | + (actions) | 0 | - (h not counted) | - | 0 | 0 | yes | ok | H |
| E2C / RCE (D) | + | + | + (affine u) | 0 | 0 | - | 0 | 0 | loc. lin | ok | M |
| Neural / latent ODE, CDE, SDE (D) | + | ++ (encode x only) | + (u in f) | 0 | + (k sweep) | - | + (multi-enc) | + (SDE noise) | yes | ok | M |
| S4 / S5 / LRU / Mamba + bottleneck (D) | ++ | - (decoder state) | + | 0 | + | - | 0 | 0 | yes | ok | M |
| CPC / JEPA / C-SWM (D) | + | + | + (C-SWM actions) | 0 | 0 | - | + (views) | 0 | yes | ok | M |
| rSLDS (D) | + | + | + | 0 | + | + (affine) | + | + | piecewise | needs PCA | M |
| PLRNN + GTF / STF (D) | ++ (chaos) | + | + | 0 | + | + | + | + | yes | ok | M |
| TCL / PCL / iVAE / LEAP / TDRL (E) | + | + (TDRL) | + (regimes) | 0 | 0 | ++ (theory) | 0 | 0 | yes | ok | M |
| CITRIS / iCITRIS / BISCUIT (E) | + | + | ++ (known/unknown tgt) | 0 | + | ++ | 0 | 0 | yes | ok | H |
| Interventional CRL theory (E) | 0 | 0 | ++ (theory) | 0 | 0 | ++ | 0 | 0 | varies | n/a | H |
| Multi-view / contrastive identifiability, CEBRA (E) | + | 0 | 0 | 0 | 0 | ++ | ++ | 0 | yes | ok | S-M |
| ICP / nonlinear ICP / IRM (E) | 0 | + (as a test) | + | 0 | 0 | + | + | 0 | yes | ok | S |
| Causal abstraction, CFL (E) | 0 | + | ++ (definition) | ++ | + | + | + | + (no coarsening) | yes | ok | M |
| IIT / DAS / interchange tests (E) | + | + | ++ | ++ | + | + | ++ (cross-impl.) | + | yes | sim-in-loop | M |
| LFADS / NDT / iLQR-VAE (F) | ++ (smoothing) | - (bidirectional, inferred inputs) | + (inferred u) | 0 | + | - | + (multi-session) | 0 | yes | ok | H |
| Fixed-point analysis (F, G) | 0 | 0 | + (Jacobians) | 0 | + | + | + (topology) | + | yes | ok | S |
| Low-rank RNNs (F) | + | ++ | ++ (native units, structural) | + | ++ (rank) | + | + | + | yes | ok | M |
| DSA / InputDSA / conjugacy / CSA (F) | eval | eval | eval | eval | eval | ++ (compare) | ++ (compare) | eval | via delays | ok | S-M |
| CCA / CKA / shape metrics / principal angles (F) | eval | eval | eval | eval | eval | ++ (compare) | + (geometry only) | eval | varies | ok | S |
| Dimensionality estimators (F) | eval | eval | eval | eval | + (cloud dim only) | + | 0 | + | varies | ok | S |
| Fisher / Bayesian OED, active learning (G) | design | design | ++ (design) | + (search) | + | + | 0 | + | varies | budget | M |
| PRC / isostables / SSM / normal forms (G) | + (local) | ++ (local) | ++ (response curves) | ++ (isochrons, fibres) | ++ (spectral gap) | ++ (canonical) | ++ (invariants) | + (outside basin) | yes (local) | ok | M |
| DSR metrics: D_stsp, D_H, Lyapunov (D, G) | eval (long horizon) | eval | eval | 0 | 0 | ++ (invariant) | ++ (invariant) | + | n/a | ok | S |

