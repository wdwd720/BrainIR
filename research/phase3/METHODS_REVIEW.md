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

**Coverage statistics.** Part I has 110 method entries. The reference list has 324 unique sources: 48 [read-full],
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

---

# Part I. Method entries

## A. Classical system identification, minimal realisation and model reduction

_Source notes: `notes\area_A_classical_sysid.md`._

Scope: minimal realisation, subspace identification (incl. PSID), balanced truncation and empirical gramians,
observability/controllability (linear and empirical nonlinear), delay/Hankel methods, classical nonlinear system
identification (NARMAX, Volterra/block-oriented, GP-SSM), linear-Gaussian SSM via EM and factor-analysis baselines,
and latent-dimension selection.

Notes on sourcing (read before using this file):
- Many primary PDFs (Juang & Pappa 1985, Rowley 2005, Ghahramani & Hinton 1996, Hermann & Krener 1977, the eolss chapters,
  the HAVOK PDF) could not be text-extracted by the fetch tool. For those I read the landing page or abstract only, or the
  item is tagged [unverified] where only a search-result snippet was seen. Technical details I state from background
  knowledge that I could not confirm in an opened source are marked "(unverified)".
- Methods only. No biological application of any cited paper is described.

---

### Minimal state realisation: Ho-Kalman, Eigensystem Realization Algorithm (ERA), Hankel rank / Nerode state (Ho-Kalman / ERA)
- **Core idea:** For an LTI input-output map with Markov parameters h_k = C A^(k-1) B, the block Hankel matrix
  H = [h_(i+j-1)] factors as H = O * R (extended observability x extended controllability). Its rank equals the minimal state
  dimension; an SVD H ~= U_n S_n V_n^T gives O = U_n S_n^(1/2), R = S_n^(1/2) V_n^T, and A is read off from the shifted
  Hankel matrix: A = S_n^(-1/2) U_n^T H_shift V_n S_n^(-1/2). ERA (Juang & Pappa 1985) is the SVD-based, noise-tolerant
  version of Ho-Kalman, with the realisation coming out approximately balanced. The abstract concept behind this is
  Nerode equivalence: two pasts are the same state iff they induce the same future input-output behaviour; the minimal
  state space is the quotient of pasts by this equivalence, and for linear systems its dimension equals Hankel rank.
- **Assumptions:** LTI, (finite-dimensional) finite Hankel rank, Markov parameters available (impulse responses, or
  estimated from input-output data by least squares as in Oymak & Ozay 2018), stable (or finite horizon), noise small
  relative to the Hankel singular-value gap.
- **Identifiability:** The input-output map (equivalently the Markov parameters) is identifiable; (A,B,C) are recovered only
  up to a similarity transform T (A -> T A T^-1, B -> T B, C -> C T^-1). The minimal dimension n = rank(H) is identifiable in
  the noise-free case. For general nonlinear discrete-time causal systems, a state-space representation always exists and
  minimality can be defined via Nerode-type equivalence (Rojas & Wachel 2022); for RNN-type (rational) systems a
  realisation theory with minimality conditions exists (Defourneau & Petreczky 2019).
- **Intervention support:** Direct: the B-matrix/Markov parameters ARE the response to input interventions. Impulse
  responses from each input channel are exactly "state-offset / input-pulse interventions". Predicts responses to any
  held-out input sequence for LTI systems (by superposition). Does not by itself handle structural interventions (removing
  units/connections change A).
- **Nonlinear capacity:** None (linear). Applied to a nonlinear simulator it recovers a local linearisation around the
  operating point used to collect impulse responses; impulse amplitude matters.
- **Interpretability:** High: eigenvalues of A give modes/time-constants; Hankel singular values rank states by joint
  input-to-output energy.
- **Scaling (N, T, data size):** SVD of an (m*p) x (n_u*q) Hankel matrix (m outputs, n_u inputs, p, q block rows/cols):
  O(min^2 * max). Cheap for m, n_u in the hundreds and p, q ~ 2-5 x expected order. Sample complexity for estimating
  Markov parameters from one random-input trajectory scales roughly with number of Markov parameters (Oymak & Ozay 2018).
- **Failure modes:** No clear singular-value gap under noise or slow/marginal modes; Hankel too short to see slow modes;
  too few block rows relative to n (need p*m >= n and q*n_u >= n); nonlinear or non-stationary systems produce spurious
  "noise" modes; ill-conditioning when n/m is large (few outputs, many states): smallest Hankel singular value decays
  super-polynomially in n/m (Sun et al. 2025, stochastic case).
- **Relevance to problem (props 1-8):** (1) exact multi-horizon linear prediction if linear; (2) realisation is closed by
  construction; (3) input-intervention sufficiency is built in (Markov parameters); (4) Nerode equivalence IS the
  definition of microstate invariance: states equal iff futures equal - this is the conceptual target of the whole
  project; (5) rank(H) is the minimal dimension; (6) SVD is deterministic, similarity class stable; (7) two
  implementations with the same I/O map have similar realisations (same Hankel matrix), which directly supports "shared f
  up to similarity"; (8) absence of a singular-value gap is a natural abstention signal.
- **Open-source implementations:** python-control `eigensys_realization` (ERA from impulse response, returns Hankel
  singular values; `markov` estimates Markov parameters from data) - https://github.com/python-control/python-control -
  active, ~2.1k stars - BSD-3-Clause. harold (minimal realisation utilities) - https://github.com/ilayn/harold - ~177
  stars, maintenance level unclear - MIT.
- **From-scratch simplicity:** Simple (about 30 lines numpy). Pitfalls: index the shifted Hankel correctly; choose
  p, q >= 2-3 x candidate n; normalise channels before SVD; for data-driven Markov parameters use a long enough FIR
  (past horizon) and random (persistently exciting) inputs.
- **References:**
  - Juang, J.-N., Pappa, R. S. (1985). An eigensystem realization algorithm for modal parameter identification and model
    reduction. J. Guidance, Control, and Dynamics 8(5):620-627. https://ntrs.nasa.gov/citations/19850064186 ;
    PDF https://people.duke.edu/~hpgavin/SystemID/References/Juang+Pappa-JG-1985.pdf [unverified] (PDF not text-extractable;
    bibliographic info and "extended version of the Ho-Kalman algorithm" from search snippet).
  - Ho, B. L., Kalman, R. E. (1966). Effective construction of linear state-variable models from input/output functions.
    Regelungstechnik 14. [unverified]
  - Oymak, S., Ozay, N. (2018/2019). Non-asymptotic identification of LTI systems from a single trajectory. arXiv:1806.05722
    (ACC 2019). https://arxiv.org/abs/1806.05722 [read-abstract]
  - Rojas, C. R., Wachel, P. (2022). On state-space representations of general discrete-time dynamical systems. IEEE TAC.
    https://arxiv.org/abs/2205.03366 [read-abstract]
  - Defourneau, T., Petreczky, M. (2019). Realization theory of recurrent neural networks and rational systems.
    arXiv:1903.05609. https://arxiv.org/abs/1903.05609 [read-abstract]
  - Sun, S., Hu, W., Wang, X. (2025). Finite sample analysis of subspace identification for stochastic systems.
    arXiv:2501.18853. https://arxiv.org/html/2501.18853 [read-full] (procedure and main theorem statements)
  - python-control docs, `eigensys_realization`, `markov`, `hankel_singular_values`.
    https://python-control.readthedocs.io/en/latest/generated/control.eigensys_realization.html [repo/docs]

### Subspace identification with inputs: N4SID, MOESP, CVA (+ nuclear-norm variants) (SID)
- **Core idea:** Stack data into block Hankel matrices of past (horizon p) and future (horizon f) inputs and outputs.
  Project future outputs onto past data (oblique projection along future inputs), which yields O_f X_hat (extended
  observability times Kalman-filter state sequence). A weighted SVD W1 * Proj * W2 reveals the order (number of dominant
  singular values) and a state sequence / observability matrix; then (A,B,C,D,K) follow by least squares. N4SID
  (Van Overschee & De Moor 1994), MOESP (Verhaegen & Dewilde 1992) and CVA (Larimore 1990) differ mainly in the weights
  W1, W2 (CVA: whitens by future and past covariances, so singular values are canonical correlations between past and
  future) (weight interpretation: unverified against the primary text; consistent with MATLAB's `N4Weight` options).
  Regression view: estimate Hankel H by least squares Y_f ~ H Y_p then SVD (Sun et al. 2025; Mercère 2013).
  Nuclear-norm variants (N2SID, Verhaegen & Hansson; Hankel rank minimisation, Fazel et al. 2013) replace the hard
  truncation by convex low-rank regularisation, reported to help on short data.
- **Assumptions:** LTI, stationary noise (innovations form x+ = Ax + Bu + Ke, y = Cx + Du + e), open loop (inputs
  uncorrelated with noise; closed-loop needs SSARX/PBSID-type variants), inputs persistently exciting of sufficient order
  (roughly order >= p + f, or 2i for i block rows (unverified)), (A,C) observable, stable A, known or estimated order.
- **Identifiability:** Transfer function and innovations model up to similarity T; state sequence identified up to T.
  Consistent (asymptotically) under the assumptions; finite-sample rates O(1/sqrt(N)) for (A,C,K) but pole errors
  O(N^(-1/2n)) and super-polynomial sample needs in n/m (Sun et al. 2025).
- **Intervention support:** Native handling of measured inputs u(t): input currents, stimulus sequences and random
  probing signals. Held-out input sequences are predicted via the identified B, D. State-offset interventions can be
  encoded as impulse inputs on an augmented input channel. Structural interventions (deletions) are not modelled unless
  treated as parameter changes and identified separately.
- **Nonlinear capacity:** Linear only. On a nonlinear simulator it yields the best linear (Kalman-optimal linear
  predictor) model at the excitation amplitude used. Can be applied to lifted/nonlinear features (kernel CVA variants
  exist; not reviewed here).
- **Interpretability:** Canonical correlations (CVA) or weighted singular values give a graded "how much state carries
  past->future information" profile; modes are interpretable.
- **Scaling (N, T, data size):** QR/LQ of a ((p+f)(m+n_u)) x T matrix: O(T * ((p+f)(m+n_u))^2). For m = 100 outputs and
  p = f = 10 this is a 2000-row matrix: fine for T up to ~1e6. For m ~ 5000 one must pre-reduce outputs (PCA) or use small
  horizons. Needs T >> (p+f)(m+n_u).
- **Failure modes:** Order selection ambiguous with no gap; bias under feedback/closed loop (input depends on output);
  biased if inputs are not persistently exciting or are low-pass; horizon too short for slow modes; unstable A estimated
  (use stability enforcement); ill-conditioning for n >> m; nonlinearity shows up as "extra noise" and inflates the
  apparent order.
- **Relevance to problem (props 1-8):** (1) optimal linear multi-step predictor; (2) Markov by construction (Kalman
  state); (3) predicts held-out input sequences in the linear regime - a strong baseline for input-type interventions;
  (5) singular value / canonical-correlation spectrum is the classical order estimate; (6) deterministic given data and
  hyperparameters (p, f, weighting), so seed-stable; sensitivity to p/f should be reported; (7) can fit a shared (A,B)
  across implementations only via a joint/stacked formulation (not standard); (8) flat canonical-correlation spectrum
  suggests no compact linear state.
- **Open-source implementations:**
  - SIPPY - https://github.com/CPCLAB-UNIPI/SIPPY - N4SID, MOESP, CVA, PARSIM-P/S/K plus ARX/ARMAX/OE/BJ families; info
    criteria for SISO only - ~337 stars, 20 open issues, maintenance moderate - LGPL-3.0 (per repo page).
  - nfoursid - https://github.com/spmvg/nfoursid - N4SID + Kalman filter, docs on ReadTheDocs - ~29 stars, small - MIT.
  - MATLAB System Identification Toolbox `n4sid` (commercial): `N4Weight` = MOESP / CVA / SSARX / auto, `N4Horizon`
    = [r sy su], Hankel singular-value plot for order choice when nx is given as a range, `EnforceStability`, refine
    with `ssest` (PEM). https://www.mathworks.com/help/ident/ref/n4sid.html [repo/docs].
  - Slycot (Python wrapper of SLICOT; GPLv2) - https://github.com/python-control/Slycot; whether it exposes SLICOT's
    subspace (IB01) routines was not confirmed (licence verified: GPLv2).
- **From-scratch simplicity:** Moderate. A regression-form SID (estimate Y_f = [H_y H_u] [Y_p; U_p] + G U_f by ridge
  least squares, SVD of the H block, recover A, C by shift-invariance, then B, D, K by LS) is ~100 lines. Pitfalls:
  removing future-input effect (oblique vs orthogonal projection), numerical conditioning (use LQ not normal
  equations), consistent scaling of channels, stability of recovered A, choice of p = f.
- **References:**
  - Van Overschee, P., De Moor, B. (1994). N4SID: subspace algorithms for the identification of combined
    deterministic-stochastic systems. Automatica 30(1):75-93. https://dl.acm.org/doi/abs/10.1016/0005-1098(94)90230-5
    [unverified] (landing page not opened; bibliographic info from search result)
  - Verhaegen, M., Dewilde, P. (1992). Subspace model identification Part 1: the output-error state-space model
    identification class of algorithms. Int. J. Control 56(5):1187-1210.
    https://people.duke.edu/~hpgavin/SystemID/References/Verhaegen-IJC-1992a.pdf [unverified]
  - Larimore, W. E. (1990). Canonical variate analysis in identification, filtering and adaptive control. 29th IEEE CDC.
    [unverified]
  - Mercère, G. (2013). Regression techniques for subspace-based black-box state-space system identification: an
    overview. arXiv:1305.7121. https://arxiv.org/abs/1305.7121 [read-abstract]
  - Sun, S., Hu, W., Wang, X. (2025). Finite sample analysis of subspace identification for stochastic systems.
    arXiv:2501.18853. https://arxiv.org/html/2501.18853 [read-full]
  - Verhaegen, M., Hansson, A. (2015/2016). N2SID: Nuclear norm subspace identification. arXiv:1501.04495.
    https://arxiv.org/abs/1501.04495 [read-abstract]
  - Fazel, M., Pong, T. K., Sun, D., et al. (2013). Hankel matrix rank minimization with applications to system
    identification and realization. SIAM J. Matrix Anal. Appl. 34(3):946-977. [unverified]
  - Tadipatri, U. K. R., Haeffele, B. D., Agterberg, J., et al. (2025). Nonconvex linear system identification with
    minimal state representation. L4DC 2025. https://arxiv.org/abs/2504.18791 [read-abstract]
  - SIPPY repo https://github.com/CPCLAB-UNIPI/SIPPY [repo/docs]; nfoursid repo https://github.com/spmvg/nfoursid and
    https://nfoursid.readthedocs.io [repo/docs]; MATLAB n4sid docs [repo/docs]; Slycot repo [repo/docs].

### Preferential subspace identification (PSID / IPSID)
- **Core idea:** A two-stage subspace method for a primary signal y (here: population state/observations) and a
  secondary signal z (here: readout). Stage 1 extracts n1 latent states from the projection of future z onto past y,
  i.e. the part of y's dynamics that predicts z; stage 2 extracts the remaining nx - n1 states that predict y. The
  result is a linear SSM (A, Cy, Cz, ...) whose first n1 coordinates are readout-relevant. IPSID adds measured inputs u
  (Vahidi, Sani & Shanechi 2024). A 2025 extension adds optimal Kalman-gain learning by reduced-rank regression and
  forward-backward smoothing.
- **Assumptions:** Linear Gaussian SSM, stationarity, enough data for projections; horizon i >= 2 with n1 <= nz*i and
  nx <= ny*i (from README).
- **Identifiability:** As for SID: up to similarity within the readout-relevant block and within the remainder; the split
  into relevant/irrelevant subspaces is the extra structure. The 2025 paper states that the secondary signal enables unique
  identification of the SSM with optimal Kalman updates (read-abstract).
- **Intervention support:** IPSID handles measured inputs; no explicit notion of do-interventions.
- **Nonlinear capacity:** Linear only (the same group has later nonlinear/deep variants, not reviewed here).
- **Interpretability:** High; explicit partition of state into readout-relevant and other dynamics.
- **Scaling (N, T, data size):** Same as SID; README advises smaller i for high-dimensional y.
- **Failure modes:** Readout-relevant subspace can be over-prioritised so that closure (prop 2) fails for the n1 block
  alone when readout-relevant dynamics depend on "irrelevant" states; hyperparameters (nx, n1, i) must be searched.
- **Relevance to problem (props 1-8):** Directly addresses the tension between minimality (5) and predictive
  sufficiency for y (1): a minimal readout-sufficient state is exactly n1. Useful baseline for "y-sufficient vs
  x-sufficient" state. Also a diagnostic: if n1 small but closure requires nx large, the readout-relevant state is not
  self-contained.
- **Open-source implementations:** PyPSID (pip `PSID`) - https://github.com/ShanechiLab/PyPSID - ~59 stars, active -
  custom USC academic licence (free for research/non-profit; commercial use requires contacting USC) (verified from
  LICENSE.md). MATLAB version https://github.com/ShanechiLab/PSID.
- **From-scratch simplicity:** Moderate (a regression-form SID with two stages). Using the package is preferable; note
  licence constraints for redistribution.
- **References:**
  - Sani, O. G., Abbaspourazad, H., Wong, Y. T., et al. (2021). Modeling behaviorally relevant neural dynamics enabled by
    preferential subspace identification. Nature Neuroscience 24:140-149.
    https://www.nature.com/articles/s41593-020-00733-0 [unverified] (paywall redirect; method described from README)
  - Sani, O. G., Shanechi, M. M. (2025). Preferential subspace identification (PSID) with forward-backward smoothing.
    arXiv:2507.15288. https://arxiv.org/abs/2507.15288 [read-abstract]
  - PyPSID and PSID repos/README/LICENSE https://github.com/ShanechiLab/PyPSID ,
    https://github.com/ShanechiLab/PSID/blob/main/README.md [repo/docs]

### Balanced realisation, balanced truncation, balanced POD, data-driven balancing (BT / BPOD)
- **Core idea:** Transform a linear system into coordinates where controllability and observability gramians are equal
  and diagonal (Moore 1981); the diagonal entries (Hankel singular values) measure each state's joint reachability and
  observability; truncate small ones. Balanced POD (Rowley 2005) computes approximate balancing transformations from
  snapshots of impulse responses of the primal and adjoint systems (method of snapshots), at cost similar to POD, avoiding
  full gramian computation. Data-driven balancing (Gosea, Gugercin & Beattie 2021) performs balancing from transfer-function
  or impulse-response samples without a realisation. Nonlinear balancing via energy functions (Scherpen-type) requires
  Hamilton-Jacobi solutions; Kramer et al. make this scalable via Taylor/tensor approximations.
- **Assumptions:** LTI, stable, (for BPOD) access to adjoint simulations or output-projected adjoints; for nonlinear
  energy-function balancing, polynomial/analytic dynamics with known model.
- **Identifiability:** Balanced coordinates are unique up to signs (and orthogonal mixing within repeated Hankel
  singular values) (unverified) - i.e. much more canonical than a generic similarity class. Useful for comparing
  latent spaces across implementations.
- **Intervention support:** Controllability part is defined with respect to the input channels; choosing which
  intervention channels count as "inputs" changes the reduced state. Observability part is with respect to the chosen
  outputs (readout y vs full x).
- **Nonlinear capacity:** Linear in its classical form; empirical-gramian / BPOD variants handle nonlinear systems
  heuristically (next entry); energy-function methods handle polynomial nonlinearities.
- **Interpretability:** High; ordered states with an a priori H-infinity error bound of 2 * sum of discarded Hankel
  singular values (unverified; standard textbook result).
- **Scaling (N, T, data size):** Exact BT needs Lyapunov solves O(N^3) - fine up to N ~ 5000 on a workstation.
  BPOD cost ~ (number of snapshots)^2 * N.
- **Failure modes:** Needs a model (or adjoint); for nonlinear simulators linearisation about one point may miss
  state-dependent structure; unstable modes must be separated first.
- **Relevance to problem (props 1-8):** (5) HSV decay gives principled minimal k for input-to-readout behaviour; (3) the
  controllability side makes the reduced state "intervention-aware" for the chosen input channels; (7) balanced
  coordinates provide a near-canonical frame to compare implementations; (4) truncating low-HSV directions merges
  microstates whose differences are weakly observable.
- **Open-source implementations:** python-control `gram`, `hankel_singular_values`, `balanced_reduction`,
  `minimal_realization` (BSD-3; balanced reduction uses Slycot, GPLv2 (dependency need unverified for each function));
  harold (MIT); emgr (next entry). BPOD: no dedicated package verified (licence not verified).
- **From-scratch simplicity:** Simple for exact BT with scipy (`solve_discrete_lyapunov`, Cholesky, SVD - square-root
  algorithm). BPOD: moderate. Pitfall: use square-root algorithm rather than forming products of gramians.
- **References:**
  - Moore, B. C. (1981). Principal component analysis in linear systems: controllability, observability, and model
    reduction. IEEE TAC 26(1):17-32. [unverified] (abstract seen only via search snippet)
  - Rowley, C. W. (2005). Model reduction for fluids, using balanced proper orthogonal decomposition. Int. J. Bifurcation
    and Chaos 15:997-1013. https://cwrowley.princeton.edu/papers/bt_ijbc3.pdf [unverified] (PDF not text-extractable)
  - Gosea, I. V., Gugercin, S., Beattie, C. (2021). Data-driven balancing of linear dynamical systems. arXiv:2104.01006.
    https://arxiv.org/abs/2104.01006 [read-abstract]
  - Kramer, B., Gugercin, S., Borggaard, J., et al. (2022/2024). Scalable computation of energy functions for nonlinear
    balanced truncation. arXiv:2209.07645. https://arxiv.org/abs/2209.07645 [read-abstract]
  - python-control function list https://python-control.readthedocs.io/en/latest/functions.html [repo/docs]

### Empirical gramians for nonlinear model reduction (Lall-Marsden-Glavaski; emgr)
- **Core idea:** Replace analytic gramians by covariance matrices of simulated trajectories: the empirical
  controllability gramian averages x(t) x(t)^T over impulse-like input perturbations of several directions and
  amplitudes; the empirical observability gramian averages output-difference inner products over initial-state
  perturbations +/- eps e_i. Balance and truncate these (Lall et al. 2002), then Galerkin/Petrov-Galerkin project the
  nonlinear vector field, giving a reduced NONLINEAR model with inputs/outputs. emgr (Himpe) implements controllability,
  observability, cross, linear cross, sensitivity, augmented (parameter-)observability and joint gramians, plus
  parameter identifiability / combined state-parameter reduction.
- **Assumptions:** Access to a simulator with controllable inputs and settable initial states (our setting exactly);
  perturbation scales chosen to represent the operating range; reduced model obtained by projection needs the
  full vector field (intrusive).
- **Identifiability:** Gramians are defined w.r.t. the chosen perturbation ensemble; result is a subspace (linear
  projection) of state space, unique up to basis within degenerate eigenvalues.
- **Intervention support:** Excellent in the simulator setting: controllability gramian uses the actual intervention
  channels (input currents, state offsets); the augmented/joint gramians can include parameters (e.g. parameter draws) as
  extra states for sensitivity/identifiability. Structural interventions could be treated as parameters (unverified idea).
- **Nonlinear capacity:** Moderate: the reduced model is nonlinear but the reduction basis is a single linear subspace
  (global linear projection) - fails when the relevant state manifold is curved.
- **Interpretability:** High (linear projection, ordered energies).
- **Scaling (N, T, data size):** Observability gramian needs 2N simulations (one per +/- perturbation direction) times
  number of scales; controllability needs n_u x scales simulations; cross gramian N x ... For N = 5000 this is ~1e4
  simulations of length T, feasible if simulator is fast. emgr offers low-rank/partitioned cross-gramian options.
- **Failure modes:** Choice of perturbation scale (too small: numerical noise; too large: leaves linear regime);
  results local to operating point/trajectory ensemble; linear projection cannot capture curved manifolds; projection
  requires access to the full vector field.
- **Relevance to problem (props 1-8):** Very relevant as an interventional baseline: (3) reduction explicitly driven by
  intervention channels; (5) gramian eigenvalue decay gives k; (4) directions with low observability energy are
  "microstate" directions that do not affect futures of y; (2) Galerkin-projected model is closed by construction; (8)
  slow HSV decay = no compact linear-projection state.
- **Open-source implementations:** emgr - https://github.com/gramian/emgr - MATLAB/Octave with a Python port
  (`py/emgr.py`), v5.99 (2022), ~21 stars, stable/slow maintenance - BSD-2-Clause (repo page).
- **From-scratch simplicity:** Simple to moderate (loops over perturbations, trapezoidal time integration of outer
  products). Pitfalls: centring around steady state/mean trajectory, scaling of states, time-step weighting.
- **References:**
  - Lall, S., Marsden, J. E., Glavaski, S. (2002). A subspace approach to balanced truncation for model reduction of
    nonlinear control systems. Int. J. Robust Nonlinear Control 12:519-535.
    https://onlinelibrary.wiley.com/doi/abs/10.1002/rnc.657 [unverified] (abstract content seen via search snippet only)
  - Himpe, C. (2018). emgr - The Empirical Gramian Framework. Algorithms 11(7):91. https://arxiv.org/abs/1611.00675
    [read-abstract]
  - Himpe, C. (2022). emgr - EMpirical GRamian Framework Version 5.99. arXiv:2209.03833.
    https://arxiv.org/abs/2209.03833 [read-abstract]
  - emgr repo https://github.com/gramian/emgr [repo/docs]

### Observability and controllability: Kalman rank, gramians, Lie-derivative rank condition, empirical observability (OBS/CTRB)
- **Core idea:** Linear: (A,C) observable iff rank [C; CA; ...; CA^(n-1)] = n; (A,B) controllable iff
  rank [B AB ... A^(n-1)B] = n; gramians grade this. Nonlinear: Hermann & Krener (1977) observability rank condition on
  the span of differentials of iterated Lie derivatives of the outputs along the vector fields (local weak
  observability; sufficient in general). Krener & Ide (2009): empirical observability gramian from simulated
  +/- eps perturbations of initial state; the "local unobservability index" (1/ smallest eigenvalue) and "estimation
  condition number" grade how observable a state is, requiring only a simulator.
- **Assumptions:** Linear case: model known. Lie-derivative test: analytic model, symbolic differentiation. Empirical:
  simulator with settable state, local around a point/trajectory.
- **Identifiability:** Observability is the precondition for identifiability of states from outputs; unobservable
  directions are exactly the directions an encoder from y-history cannot recover. Structural identifiability of
  parameters can be posed as observability of an augmented state (see emgr augmented gramian).
- **Intervention support:** Controllability is "which state directions interventions can reach"; empirical
  controllability gramian with actual intervention channels quantifies this.
- **Nonlinear capacity:** Lie-derivative test is fully nonlinear but binary and local; empirical gramians give graded
  local measures.
- **Interpretability:** High.
- **Scaling (N, T, data size):** Kalman rank tests are numerically unreliable for large N (use gramians/SVD instead);
  empirical gramian needs O(N) simulations; symbolic Lie derivatives do not scale beyond small N.
- **Failure modes:** Binary rank tests mislead in floating point; empirical measures depend on eps and on the chosen
  operating region; local-only.
- **Relevance to problem (props 1-8):** Core validation tools. (4) Microstate invariance w.r.t. readout = unobservable
  directions of (x -> y) should be the null space of phi; test: perturb x along directions with ~0 observability energy
  and check z unchanged. (3) Controllability gramian of the intervention channels restricted to span(phi) checks that the
  encoder retains intervention-reachable directions. (5) Minimal state for y-prediction = observable and (for input-driven
  behaviour) reachable part. (8) Flat gramian spectra argue against compact state.
- **Open-source implementations:** python-control `ctrb`, `obsv`, `gram` (BSD-3); emgr (BSD-2). Lie-derivative tools
  (e.g. symbolic observability toolboxes) not checked here (licence not verified).
- **From-scratch simplicity:** Simple (linear, empirical gramians); moderate for symbolic Lie derivatives.
- **References:**
  - Hermann, R., Krener, A. J. (1977). Nonlinear controllability and observability. IEEE TAC 22(5):728-740.
    https://www.math.ucdavis.edu/~krener/1-25/10.IEEETAC77.pdf [unverified] (PDF not text-extractable; rank-condition
    statement from search snippet)
  - Krener, A. J., Ide, K. (2009). Measures of unobservability. Proc. IEEE CDC 2009, 6401-6406.
    https://www.math.ucdavis.edu/~krener/101-125/125.CDC09.pdf [unverified] (PDF fetched but not reliably
    text-extracted; definitions of unobservability index and condition number from search snippet)
  - python-control function list [repo/docs]; emgr repo [repo/docs] (see above).

### Delay embedding (Takens; forced-system embeddings) (DELAY)
- **Core idea:** For a generic observation function of a d-dimensional (box-counting dimension d_A) deterministic
  system, the delay map x -> (h(x), h(Fx), ..., h(F^(n-1)x)) is one-to-one on the attractor when n > 2 d_A (prevalence
  version, Sauer, Yorke & Casdagli 1991). Stark (1999) extends Takens to forced systems, with one theorem for unknown
  forcing and one where the forcing is known (inputs can be appended to the delay vector).
- **Assumptions:** Deterministic, autonomous (or forced with known/deterministic forcing), compact attractor, generic
  observation, noise small, trajectory on/near an attractor (transients not covered).
- **Identifiability:** The delay vector is a state up to a diffeomorphism (on the attractor); it recovers the attractor's
  state, not off-attractor states.
- **Intervention support:** Weak: embedding describes the unperturbed attractor; perturbations that move off the
  attractor may not be represented. Forced-system version handles known inputs.
- **Nonlinear capacity:** Full (existence result), but gives only coordinates, not a model of f.
- **Interpretability:** Low (delay coordinates are generic).
- **Scaling (N, T, data size):** Embedding dimension grows with attractor dimension, not N. Data needed to populate the
  attractor grows exponentially with d_A (unverified, standard).
- **Failure modes:** Wrong delay tau/embedding length, noise amplification, high attractor dimension, non-stationarity,
  input-driven systems off attractor.
- **Relevance to problem (props 1-8):** Theoretical justification for "readout-history-only" baselines: if y is generic
  and the dynamics are low-dimensional, a y-history window is a sufficient state; hence a readout-history predictor is a
  must-have baseline and a lower bar for encoder quality (1,2). Also warns: good y-history prediction does not imply
  interventional sufficiency (3) off attractor.
- **Open-source implementations:** Trivial to implement; pykoopman TimeDelay observables (MIT).
- **From-scratch simplicity:** Simple.
- **References:**
  - Sauer, T., Yorke, J. A., Casdagli, M. (1991). Embedology. J. Stat. Phys. 65:579-616. [unverified] (abstract seen
    via search snippet)
  - Stark, J. (1999). Delay embeddings for forced systems. I. Deterministic forcing. J. Nonlinear Science 9:255-332.
    https://doi.org/10.1007/s003329900072 [unverified] (abstract seen via search snippet)
  - Takens, F. (1981). Detecting strange attractors in turbulence. Lecture Notes in Mathematics 898. [unverified]

### Hankel/delay-coordinate Koopman methods: HAVOK and Hankel DMD (HAVOK / HDMD)
- **Core idea:** Build a Hankel matrix of delay-embedded measurements, take SVD, and fit a linear model in the leading
  r delay coordinates. HAVOK (Brunton et al. 2017) regresses dv/dt = A v + B v_r where the last retained coordinate v_r
  acts as intermittent forcing (heavy-tailed, flags switching/bursting). Hankel DMD (Arbabi & Mezic 2017) proves that DMD
  on Hankel data matrices converges to Koopman eigenvalues/eigenfunctions for ergodic systems in the infinite-data
  limit. Kamb et al. show delay observables give universal (system-independent) Koopman representations for some system
  classes. Hankel-DMD with control is available in pykoopman (tutorial).
- **Assumptions:** Stationary/ergodic sampling of an attractor (HDMD theory), uniform sampling, sufficient delays; for
  HAVOK, chaotic dynamics well represented by linear + forcing.
- **Identifiability:** Koopman eigenvalues (spectral quantities) are identifiable in the ergodic limit; delay
  coordinates up to orthogonal transform within SVD subspaces.
- **Intervention support:** Plain versions: none. DMDc/Hankel-DMDc add a B u term; predictive validity under novel
  interventions is unproven.
- **Nonlinear capacity:** Linear model in delay space; nonlinearity captured implicitly through many delays; HAVOK's
  forcing term is unmodelled (must be supplied), so it is not a closed predictor.
- **Interpretability:** Moderate (modes, frequencies; forcing signal as event detector).
- **Scaling (N, T, data size):** SVD of (q*m) x T Hankel; randomised SVD makes q*m ~ 1e4 feasible.
- **Failure modes:** Rank/delay choices arbitrary; HAVOK is not closed (needs v_r); spurious eigenvalues; non-ergodic
  transient data break theory; numerical differentiation noise (HAVOK continuous-time).
- **Relevance to problem (props 1-8):** Baseline for "delay/Hankel methods" (contract list). Fails (2) closure in the
  HAVOK form by design; Hankel DMD with control is a reasonable linear baseline for (1),(3). Delay-based z depends on
  history not on x, so microstate invariance (4) must be tested through the encoder that maps x to delay coordinates
  (only possible via simulation from x forward, or not at all).
- **Open-source implementations:** pykoopman - https://github.com/dynamicslab/pykoopman - HAVOK, TimeDelay, DMDc,
  EDMD, NNDMD; JOSS 2024 - ~456 stars, active - MIT. PyDMD - https://github.com/PyDMD/PyDMD - HankelDMD, HAVOK, DMDc,
  BOPDMD, optimal DMD - ~1.3k stars, active - MIT.
- **From-scratch simplicity:** Simple (Hankel + SVD + least squares); pitfalls: train/test split must be done before
  Hankel construction to avoid overlapping windows leaking future data.
- **References:**
  - Brunton, S. L., Brunton, B. W., Proctor, J. L., et al. (2017; arXiv 2016). Chaos as an intermittently forced linear
    system. Nature Communications 8:19 (venue unverified). https://arxiv.org/abs/1608.05306 [read-abstract]
  - Arbabi, H., Mezic, I. (2017). Ergodic theory, dynamic mode decomposition, and computation of spectral properties of
    the Koopman operator. SIAM J. Appl. Dyn. Syst. 16(4):2096-2126. https://arxiv.org/abs/1611.06664 [read-abstract]
  - Kamb, M., Kaiser, E., Brunton, S. L., et al. (2018/2020). Time-delay observables for Koopman: theory and
    applications. arXiv:1810.01479. https://arxiv.org/abs/1810.01479 [read-abstract]
  - pykoopman repo and docs https://github.com/dynamicslab/pykoopman , https://pykoopman.readthedocs.io [repo/docs]
  - PyDMD repo https://github.com/PyDMD/PyDMD [repo/docs]

### Singular spectrum analysis (SSA / MSSA)
- **Core idea:** Embed a (multivariate) series with window L into a (stacked) Hankel trajectory matrix, SVD, group
  components, diagonal-average back to series; forecast by linear recurrence relations (LRR). It is essentially PCA of
  delay vectors - the non-dynamical sibling of HDMD/SID.
- **Assumptions:** Series of finite "rank" (sum of exponentials-times-polynomials-times-sinusoids), separability of
  components, stationarity helpful.
- **Identifiability:** Signal subspace (rank) identifiable if components separable; basis within groups not unique.
- **Intervention support:** None (no inputs).
- **Nonlinear capacity:** Linear recurrences only.
- **Interpretability:** Good for trends/oscillations.
- **Scaling (N, T, data size):** FFT-based Hankel products (Rssa) make long series cheap.
- **Failure modes:** Choice of L and grouping; no input handling; not a state-space model with inputs.
- **Relevance to problem (props 1-8):** Mainly as a dimension diagnostic (rank of delay-trajectory matrix) and a
  denoising pre-step; weak relevance to (3).
- **Open-source implementations:** Rssa (R, CRAN) - licence not verified. Python: trivial.
- **From-scratch simplicity:** Simple.
- **References:**
  - Golyandina, N., Korobeynikov, A. (2014). Basic singular spectrum analysis and forecasting with R. Comput. Stat. Data
    Anal. 71:934-954. https://arxiv.org/abs/1206.6910 [read-abstract]
  - Golyandina, N., Korobeynikov, A., Shlemov, A., et al. (2015). Multivariate and 2D extensions of singular spectrum
    analysis with the Rssa package. J. Stat. Softw. 67(2). https://arxiv.org/abs/1309.5050 [read-abstract]

### NARX / NARMAX with orthogonal-least-squares structure selection (NARMAX)
- **Core idea:** Model y(t) = F(y(t-1..ny), u(t-1..nu), e(t-1..ne)) + e(t) with F typically a sparse polynomial (or other
  basis); select terms greedily by forward regression orthogonal least squares (FROLS) using the error reduction ratio
  (ERR), then estimate parameters; validate with free-run simulation and residual correlation tests (Chen & Billings 1989).
- **Assumptions:** Input-output representation valid (observable system, finite memory), discrete time, noise
  modelled as MA terms, basis adequate.
- **Identifiability:** Selected terms and coefficients in the chosen basis; no latent state (state = lagged I/O window).
- **Intervention support:** Handles measured inputs; held-out input sequences via free-run simulation; state offsets are
  not representable except through past outputs.
- **Nonlinear capacity:** High (polynomial/rational/neural bases), but combinatorial term growth with lags and order.
- **Interpretability:** High for sparse polynomial models (term list with ERR).
- **Scaling (N, T, data size):** Candidate terms grow as C(n_lags*channels + degree, degree): only practical for few
  channels (<~10); multi-output with ~100 channels infeasible without prior reduction.
- **Failure modes:** One-step-ahead fit good but free-run simulation unstable; lag and degree choice; term explosion;
  ERR greedy selection biased under coloured noise without MA terms.
- **Relevance to problem (props 1-8):** Good "readout-history + input" baseline for low-dimensional y; it is the
  classical "input-output state" (Nerode-by-history) approach; provides no encoder phi(x) and no microstate test.
- **Open-source implementations:** SysIdentPy - https://github.com/wilsonrljr/sysidentpy - NARMAX/NARX/NFIR, FROLS, AOLS,
  MetaMSS, entropic regression, ERR, AIC/BIC/FPE/LILC, multiple inputs, neural NARX (PyTorch), JOSS 2020 - ~521 stars,
  active - BSD-3-Clause.
- **From-scratch simplicity:** Moderate (FROLS is ~80 lines; validation tests more).
- **References:**
  - Chen, S., Billings, S. A. (1989). Representations of non-linear systems: the NARMAX model. Int. J. Control
    49(3):1013-1032. https://www.tandfonline.com/doi/abs/10.1080/00207178908559683 [unverified]
  - SysIdentPy repo and docs https://github.com/wilsonrljr/sysidentpy , https://sysidentpy.org [repo/docs]
  - Schoukens, J., Ljung, L. (2019). Nonlinear system identification: a user-oriented road map. IEEE Control Systems
    Magazine 39(6):28-99. https://arxiv.org/html/1902.00683v1 [read-full]

### Volterra / Wiener series and block-oriented (Wiener, Hammerstein, Wiener-Hammerstein) models (VOLTERRA / BLOCK)
- **Core idea:** Volterra: y = sum of multidimensional convolutions of the input (kernels of order 1..K); Wiener series:
  orthogonalised version for Gaussian inputs. Block-oriented: static nonlinearity(-ies) sandwiched with LTI blocks
  (Hammerstein = NL then linear; Wiener = linear then NL; Wiener-Hammerstein = L-NL-L); parallel WH structures are
  universal approximators of fading-memory systems. Schoukens & Ljung recommend starting from the best linear
  approximation (BLA) measured with random-phase multisines, and moving to nonlinear models only if linear ones
  demonstrably fail.
- **Assumptions:** Fading memory (unique steady state; no multistability or chaos), stationarity; Volterra kernels
  exponential in order.
- **Identifiability:** Kernels identifiable (symmetrised) given rich inputs; block-oriented models have gain/scaling
  ambiguities between blocks (unverified, standard).
- **Intervention support:** Input-output only; no state offsets.
- **Nonlinear capacity:** Fading-memory nonlinearities only; cannot represent multistability, limit cycles, hysteresis,
  chaos (these need nonlinear state-space structures such as PNLSS) (per Schoukens & Ljung).
- **Interpretability:** Moderate (kernels, BLA).
- **Scaling (N, T, data size):** Volterra parameters grow as (memory)^order: infeasible beyond order 2-3 and a few
  inputs.
- **Failure modes:** Curse of dimensionality; systems with persistent internal state/memory (attractors) violate fading
  memory - likely for recurrent populations.
- **Relevance to problem (props 1-8):** Mostly as a caution and as a BLA diagnostic: a "nonlinearity level" test (BLA
  residual vs noise floor under multisine excitation) tells whether linear baselines are adequate. Fading-memory models
  have no compact latent state in the sense needed for (2),(4).
- **Open-source implementations:** MATLAB SysID Toolbox (nlhw, commercial); SysIdentPy covers polynomial NARX/NFIR.
  No Python block-oriented package verified (licence not verified).
- **From-scratch simplicity:** Simple for order-2 Volterra with basis expansion (Laguerre) by least squares; moderate
  for WH.
- **References:**
  - Schoukens, J., Ljung, L. (2019). Nonlinear system identification: a user-oriented road map. IEEE CSM 39(6):28-99.
    https://arxiv.org/abs/1902.00683 , https://arxiv.org/html/1902.00683v1 [read-full]
  - Aguirre, L. A. (2019/2022). A bird's eye view of nonlinear system identification. arXiv:1907.06803.
    https://arxiv.org/abs/1907.06803 [read-abstract]

### Gaussian-process state-space models (GP-SSM)
- **Core idea:** Place a GP prior on the transition function f in x(t+1) = f(x(t), u(t)) + noise, with (usually
  parametric) observation model; marginalise f and sample the latent trajectory with particle MCMC (PGAS) (Frigola et al.
  2013), with sparse GP approximations for scalability. Later variational versions exist (not reviewed here).
- **Assumptions:** Smooth transition function (kernel), low latent dimension (GP on k-dim input), stationarity, known
  latent dimension; observation model often linear to reduce non-identifiability.
- **Identifiability:** Latent states only up to a (nonlinear) reparametrisation unless observation model constrained;
  with linear C, up to affine transformations (unverified).
- **Intervention support:** Inputs u enter f; posterior uncertainty is useful for abstention (8) and for detecting
  extrapolation to novel interventions.
- **Nonlinear capacity:** High (nonparametric), but only in low k.
- **Interpretability:** Moderate (posterior over f can be visualised in k <= 3).
- **Scaling (N, T, data size):** PMCMC costs O(particles x T x iterations) with sparse GP O(M^2) per step; practical for
  k <= ~4-6 and T ~ 1e3-1e4 (unverified).
- **Failure modes:** Poor mixing, sensitivity to kernel and inducing points, latent-dimension non-identifiability,
  slow.
- **Relevance to problem (props 1-8):** Principled uncertainty for (8) abstention and (6) stability; limited by scaling
  and low k. Mainly a small-k reference model in the tournament rather than a primary candidate.
- **Open-source implementations:** No maintained reference implementation verified here (licence not verified).
- **From-scratch simplicity:** Hard (PMCMC with GP marginalisation); variational versions moderate with GPyTorch-type
  tools (unverified).
- **References:**
  - Frigola, R., Lindsten, F., Schön, T. B., Rasmussen, C. E. (2013). Bayesian inference and learning in Gaussian
    process state-space models with particle MCMC. NIPS 2013. https://arxiv.org/abs/1306.2861 [read-abstract]

### Linear Gaussian state-space models by EM; factor analysis / PCA + linear dynamics; GPFA (LDS-EM / FA / GPFA)
- **Core idea:** LDS x(t+1) = A x + B u + w, y = C x + D u + v with Gaussian noise; EM alternates Kalman (RTS)
  smoothing (E-step) with closed-form updates of A, B, C, D, Q, R, initial state (M-step) (Shumway & Stoffer 1982;
  Ghahramani & Hinton 1996 who relate it to factor analysis). Static baselines: PCA or factor analysis to get z, then
  fit a linear (or VAR) dynamics z(t+1) = A z + B u by least squares. GPFA (Yu et al. 2009): factor analysis whose latent
  factors have independent GP priors over time (learned timescales), fitted by EM; dimension chosen by leave-one-unit-out
  cross-validated prediction; latents orthonormalised for display. GPFA is a smoother, not a dynamical (Markov) model.
- **Assumptions:** Linear Gaussian (LDS), stationarity; FA: diagonal private noise; GPFA: independent stationary GP
  latents (no inputs, no Markov dynamics).
- **Identifiability:** LDS/FA: up to invertible (FA: rotation after whitening) transform of latents; EM finds local
  optima. GPFA: up to scaling/permutation with independent GPs (unverified).
- **Intervention support:** LDS with B u: yes for inputs. PCA/FA + dynamics: inputs added in regression. GPFA: none.
- **Nonlinear capacity:** None (switching LDS / nonlinear SSMs in dynamax extend this).
- **Interpretability:** High.
- **Scaling (N, T, data size):** Kalman smoothing O(T k^3 + T k m) with m outputs; EM iterations 100-1000; fine for
  m = 5000 if R diagonal. GPFA: O(k^3 T^3) naive per trial (limit on trial length) (unverified).
- **Failure modes:** EM slow convergence and local optima (initialise with SID/N4SID or PCA+LS), degenerate Q/R; PCA
  picks high-variance not high-predictive directions (fails when dynamics-relevant directions have low variance);
  GPFA's independent GPs do not provide a transition law.
- **Relevance to problem (props 1-8):** The contract's "PCA + linear dynamics" and "factor analysis" baselines and the
  "linear SSM identification" baseline. LDS-EM initialised from N4SID is the strong linear-Gaussian reference for
  (1),(2),(3 for inputs); PCA+LDS isolates the effect of variance-based vs prediction-based state selection (5).
- **Open-source implementations:** dynamax - https://github.com/probml/dynamax - LGSSM with EM and SGD, nonlinear
  Gaussian SSMs, HMMs, HMC/SMC via Blackjax, JOSS 2024 - >1k stars, active - MIT. GPFA: implementations exist (e.g.
  in an electrophysiology-analysis toolkit) but none opened here (licence not verified). sklearn PCA/FactorAnalysis
  (BSD-3, unverified here).
- **From-scratch simplicity:** Moderate for LDS-EM (RTS smoother + lag-one covariances; numerically use
  Joseph form / square-root or symmetric updates; add small ridge on Q, R). Simple for PCA/FA + least-squares dynamics.
- **References:**
  - Shumway, R. H., Stoffer, D. S. (1982). An approach to time series smoothing and forecasting using the EM algorithm.
    J. Time Series Analysis 3(4):253-264. https://dsstoffer.github.io/files/em.pdf [unverified] (PDF not
    text-extractable)
  - Ghahramani, Z., Hinton, G. E. (1996). Parameter estimation for linear dynamical systems. Tech. Rep. CRG-TR-96-2,
    Univ. Toronto. https://www.cs.utoronto.ca/~hinton/absps/tr96-2.html [read-abstract]
  - Yu, B. M., Cunningham, J. P., Santhanam, G., et al. (2009). Gaussian-process factor analysis for low-dimensional
    single-trial analysis of neural population activity. NeurIPS 21 (2008 proceedings).
    https://proceedings.neurips.cc/paper_files/paper/2008/hash/ad972f10e0800b49d76fed33a21f6698-Abstract.html
    [read-abstract] (methodology only; no data described)
  - dynamax repo https://github.com/probml/dynamax [repo/docs]

### Latent dimension / model order selection: AIC/BIC/MDL, singular-value gaps, subspace order criteria, CV plateaus, parallel analysis (ORDER)
- **Core idea:** (a) Information criteria penalise likelihood by parameter count: AIC (2p), BIC (p log T); MDL
  (Rissanen 1978) picks the model minimising total description length of model + data and estimates integer structure
  (order) and real parameters jointly; refined MDL uses NML/stochastic complexity (Grünwald 2004 tutorial). (b) Subspace
  order estimation: Bauer (2001) gives three consistent criteria - two based on estimated singular values (thresholded /
  penalised SV sums) and one based on the estimated innovation variance - for systems with and without observed inputs.
  (c) Cross-validated prediction plateaus: choose smallest k whose held-out multi-step prediction is within noise of the
  best (as in GPFA's leave-unit-out CV and PSID's CV grid search over (nx, n1)). (d) Parallel analysis (Horn 1965):
  keep components whose eigenvalues exceed those of random data of equal size (permutation/shuffle surrogates);
  corrects the inflation of sample eigenvalues.
- **Assumptions:** (a) correct model class, T large relative to p; (b) LTI, consistency asymptotic; (c) i.i.d. or
  blocked CV folds; (d) static covariance - does not account for temporal autocorrelation unless surrogates preserve it.
- **Identifiability:** Order itself; ICs consistent (BIC/MDL) or efficient (AIC) under class correctness (unverified,
  standard).
- **Intervention support:** Not per se; but CV can be done on held-out intervention types - the most relevant variant.
- **Nonlinear capacity:** Criteria are generic; for neural models parameter counts are uninformative, so CV plateaus
  dominate.
- **Interpretability:** High.
- **Scaling (N, T, data size):** Cheap except CV (refits per k per fold).
- **Failure modes:** No gap in singular values (continuous spectrum); AIC overfits; BIC underfits at small T; MDL/BIC
  parameter counts ill-defined for over-parameterised models; CV leaks through overlapping windows; parallel analysis on
  autocorrelated time series overestimates k unless surrogates are phase-randomised or block-shuffled (unverified).
- **Relevance to problem (props 1-8):** (5) minimality directly; (8) abstention: if no criterion shows an elbow before
  k_max and CV curves keep improving slowly, report "no compact state".
- **Open-source implementations:** SysIdentPy (AIC/BIC/FPE/LILC for NARMAX), SIPPY (IC for SISO), MATLAB n4sid (Hankel
  SV plot), python-control ERA returns Hankel SVs. Parallel analysis: trivial.
- **From-scratch simplicity:** Simple.
- **References:**
  - Rissanen, J. (1978). Modeling by shortest data description. Automatica 14:465-471. [unverified]
  - Grünwald, P. (2004). A tutorial introduction to the minimum description length principle. arXiv:math/0406077.
    https://arxiv.org/abs/math/0406077 [read-abstract]
  - Bauer, D. (2001). Order estimation for subspace methods. Automatica 37:1561-1573. [unverified] (abstract content seen
    only via search snippet)
  - Horn, J. L. (1965). A rationale and test for the number of factors in factor analysis. Psychometrika 30:179-185.
    [unverified]; Parallel analysis overview https://en.wikipedia.org/wiki/Parallel_analysis [read-full] (secondary)
  - PyPSID README (CV grid search over nx, n1) [repo/docs]; GPFA abstract (leave-out CV) [read-abstract].

### Supporting result: persistency of excitation and Willems' fundamental lemma (PE)
- **Core idea:** For a controllable LTI system of order n, if the input is persistently exciting of order L + n (block
  Hankel matrix of inputs with L+n block rows has full row rank), then every length-L trajectory is a linear combination
  of columns of the data Hankel matrix; i.e. the data span the whole behaviour. Relaxations replace controllability with
  conditions on controllable/unobservable subspaces (Yu et al. 2021); a Koopman-embedding extension shows that
  trajectories of nonlinear systems with a finite linear embedding span the lifted behaviour given rich enough (number
  and length of) trajectories (Shang, Cortés & Zheng 2024).
- **Assumptions:** Discrete-time LTI (or a system with an exact finite linear Koopman embedding for the nonlinear extension),
  controllable (or the relaxed conditions of Yu et al.), noise-free data for the exact statement; known upper bound on n.
- **Identifiability:** Not an estimator itself; it guarantees that the data Hankel matrix spans all length-L behaviours, so the
  input-output behaviour (hence any minimal realisation up to similarity) is determined by the data.
- **Intervention support:** Directly about inputs: gives the richness condition the input/intervention sequence must satisfy.
  Says nothing about structural interventions or held-out intervention types.
- **Nonlinear capacity:** None in the classical form; the Koopman-embedding extension applies only when a finite linear
  embedding exists (unverified beyond the abstract).
- **Interpretability:** High (a rank condition).
- **Scaling (N, T, data size):** Requires roughly T >= (n_u + 1)(L + n) - 1 samples for one trajectory (standard count,
  unverified here); checking it is one rank computation on an (n_u (L+n)) x (T-L-n+1) matrix.
- **Failure modes:** Noise makes rank conditions fuzzy (use condition numbers / singular-value floors); nonlinear systems
  violate the linear span property; closed-loop inputs may lose excitation.
- **Relevance:** Gives the concrete excitation requirement for SID/ERA/DMDc baselines and a design rule for simulator
  input sequences: random inputs with full-rank input Hankel matrices of depth >= p + f (+ n), and many independent
  trajectories rather than one long one.
- **Open-source implementations:** No dedicated package needed; numpy/scipy rank and SVD (BSD-3). Data-driven control
  toolboxes exist but were not checked.
- **From-scratch simplicity:** Simple: build the input block Hankel of depth L + n and check its rank/condition number.
- **References:**
  - Yu, Y., Talebi, S., van Waarde, H. J., et al. (2021). On controllability and persistency of excitation in data-driven
    control: extensions of Willems' fundamental lemma. arXiv:2102.02953. https://arxiv.org/abs/2102.02953 [read-abstract]
  - Shang, X., Cortés, J., Zheng, Y. (2024). Willems' fundamental lemma for nonlinear systems with Koopman linear
    embedding. arXiv:2409.16389. https://arxiv.org/abs/2409.16389 [read-abstract]
  - Willems, J. C., Rapisarda, P., Markovsky, I., De Moor, B. (2005). A note on persistency of excitation. Systems &
    Control Letters. [unverified]

---

## B. Koopman operator learning, DMD and sparse identification

_Source notes: `notes\area_B_koopman_dmd_sindy.md`._

Scope: linear-operator (Koopman / transfer-operator) methods from snapshot data, their control extensions, deep Koopman
autoencoders, SINDy-family sparse regression, and operator inference. Everything here is methods-only.

Reading notes and tag conventions:
- [read-full] means the paper body was fetched (arXiv HTML via ar5iv) and queried for specific algorithmic details
  (equations, loss terms, hyperparameters). The fetch tool summarises the page, so I checked every detail through that
  summary and did not do a line-by-line read. Anything I could not trace to a fetched source is marked "(unverified)".
- [read-abstract] means only the arXiv abstract or landing page was opened.
- Licences were read from raw LICENSE files on GitHub unless stated otherwise. Star counts are approximate, as of 2026-09.
- Notation: x in R^N is the simulator state, u the input, y the readout, psi(x) a dictionary (lifting), z the latent
  state, K the Koopman matrix, M the number of snapshot pairs, and r or k the retained rank or latent dimension.

Cross-cutting facts that apply to every entry (details and references are in the entries below):
- **Spectral invariance.** Linear latent models z+ = A z are identifiable only up to similarity A -> S A S^-1. The
  eigenvalues (and therefore continuous-time rates and frequencies) are similarity-invariant. They are the natural
  quantity to compare across seeds, estimation procedures and physical implementations (props 6 and 7). Eigenvectors,
  modes and eigenfunctions are identified only up to a complex scalar per eigenvalue, and up to a basis of the eigenspace
  when eigenvalues are repeated. Products and powers of Koopman eigenfunctions are also eigenfunctions (Brunton et al.
  2021 review), so "the" k-dimensional eigenfunction set is not unique. One has to pick a principal or slowest subset.
- **No finite-dimensional linear model for multiple attractors.** A finite-dimensional linear Koopman model that contains
  the state cannot represent several isolated fixed points or attractors. The Brunton et al. 2021 review states that no
  homeomorphic coordinate change gives a global linear model with three isolated fixed points. For multistable network
  simulators this is a hard limit of "encoder + linear f" (prop 8: abstain or go nonlinear).
- **Interventions map naturally onto these methods.** (a) State offsets x0 -> x0 + delta are just extra initial
  conditions. DMD, EDMD, the Korda-Mezic predictor and VAMP only need snapshot pairs, not a single trajectory. (b) Input
  currents are u in DMDc / EDMDc / SINDYc / OpInf. (c) Removing units or connections is a parameter change, not an
  input. It needs parametric models (SINDy with mu-dot = 0, parametric OpInf, parametric DMD) or a per-regime operator.

---

### Exact DMD (DMD; incl. projected DMD and Hankel/delay DMD)
- **Core idea:** Fit the best linear map Y ~ A X between snapshot matrices X = [x_1..x_m] and Y = [x_2..x_{m+1}] (or any
  set of pairs), using a rank-r truncated SVD of X. The eigenpairs of the r x r reduced operator give DMD eigenvalues and
  modes. Tu et al. (2014) define DMD as "the eigendecomposition of an approximating linear operator" and allow arbitrary
  pair sets (non-sequential data, concatenated runs).
- **Assumptions:** The dynamics are well approximated by a linear map on the span of the measured observables, i.e. the
  measured state is close to a Koopman-invariant subspace. Data are noise-free, or the noise is small relative to the
  retained singular values. Uniform time step within each pair.
- **Identifiability:** Algorithm (Tu et al.): X = U Sigma V*, A_tilde = U* Y V Sigma^-1, A_tilde w = lambda w. Exact modes are
  phi = lambda^-1 Y V Sigma^-1 w and projected modes are U w. Tu et al. prove Y = A X holds exactly iff X and Y are "linearly
  consistent" (null(X) is contained in null(Y)). Under that condition the DMD eigenvalues and modes are Koopman
  eigenvalues and modes. Eigenvalues are similarity-invariant. Modes are identified up to a scalar each. The r-dim
  subspace is identified only if there is a spectral gap in the singular values of X.
- **Intervention support:** No inputs. State-offset interventions enter as extra snapshot pairs: pairs need not come from
  one trajectory, and concatenating runs is explicitly supported (Tu et al., Sec. 3.2.4). Applying DMD to forced data gives
  modes "corrupted by external forcing" (Proctor et al. 2016), so use DMDc instead.
- **Nonlinear capacity:** Linear only, in the measured coordinates. Time-delay (Hankel) augmentation "can enlarge the rank"
  and captures more modes (Tu et al., Sec. 3.2.2). HAVOK (Brunton et al. 2017) combines delay embedding with a linear model
  plus an intermittent forcing coordinate. Tu et al. show ERA and DMD operators are related by a similarity transform
  (Sec. 4.2), so delay DMD overlaps with subspace identification (Area on subspace ID).
- **Interpretability:** High. Each mode has a growth rate and frequency (log(lambda)/dt) and a spatial pattern over units.
- **Scaling (N, T, data size):** One thin SVD, O(N m min(N, m)). Trivial for N <= 5,000 and m ~ 10^4 to 10^5. Use a
  randomised SVD or the method of snapshots for larger sizes. Memory is O(N m).
- **Failure modes:** Noise biases eigenvalues toward stability (Dawson et al. 2016). Rank truncation choice drives results.
  Standing waves or rank-deficient data miss modes without delays. Transients and nonstationarity are mixed together.
  Multistability and limit cycles can only be approximated as neutral oscillations. Spurious modes appear when data are
  not linearly consistent.
- **Relevance to problem (props 1-8):** (1) good for short horizons near an operating point, weak for multi-horizon
  nonlinear prediction. (2) linear closure is testable by linear consistency and residuals. (5) rank r is a direct handle on
  k. (6) spectra are stable across procedures when the gap is clear. (7) eigenvalues are implementation-invariant and are a
  good cross-implementation comparison. (8) large residual or no singular-value gap is an abstention signal. Main role:
  **baseline**.
- **Open-source implementations:** PyDMD - https://github.com/PyDMD/PyDMD - active, ~1.3k stars, many variants (DMD,
  HankelDMD, FbDMD, TLS/"optimal closed-form", BOPDMD, DMDc, EDMD, HAVOK, SpDMD, MrDMD, randomized/compressed DMD) - MIT
  (LICENSE read). pykoopman - https://github.com/dynamicslab/pykoopman - active, ~456 stars - MIT (LICENSE read).
- **From-scratch simplicity:** Simple, about 15 lines of numpy. Pitfalls: centre or not centre consistently (mean
  subtraction changes the eigenvalue at 1). Do not invert tiny singular values. Use exact rather than projected modes when
  Y's range differs from X's. Keep dt fixed.
- **References:**
  - Dynamic mode decomposition of numerical and experimental data. P. J. Schmid. 2010. J. Fluid Mech. 656:5-28.
    https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/dynamic-mode-decomposition-of-numerical-and-experimental-data/AA4C763B525515AD4521A6CC5E10DBD4 [read-abstract]
  - On dynamic mode decomposition: theory and applications. J. H. Tu, C. W. Rowley, D. M. Luchtenburg et al. 2014.
    J. Computational Dynamics 1(2). https://arxiv.org/abs/1312.0041 [read-full]
  - Chaos as an intermittently forced linear system (HAVOK). S. L. Brunton, B. W. Brunton, J. L. Proctor et al. 2017
    (arXiv 2016). Nature Communications. https://arxiv.org/abs/1608.05306 [read-abstract]

### Noise-robust DMD: forward-backward, total-least-squares, optimized (VarPro) and BOP-DMD (fbDMD, tlsDMD, optDMD, BOP-DMD)
- **Core idea:** Plain DMD is a least-squares fit with noise only on Y, but noise is also present in X. That errors-in-variables
  problem biases eigenvalues. The fixes are:
  - fbDMD: take the geometric mean of the forward and inverse-backward operators, A ~ (A_f A_b^-1)^{1/2}.
  - tlsDMD / TDMD: total least squares on the stacked [X; Y] after rank-r projection.
  - optDMD: fit X ~ Phi diag(b) exp(omega t) directly by variable projection. It works with irregular sampling and has
    reduced bias.
  - BOP-DMD: bag optDMD over random subsets of snapshots to get mean and variance of eigenvalues and modes (UQ).
- **Assumptions:** Additive, independent, zero-mean sensor noise (Dawson et al.). fbDMD needs invertible dynamics. optDMD
  assumes the data are a sum of exponentials, i.e. linear dynamics after projection.
- **Identifiability:** Dawson et al. derive E(A_m) = A (I - E(N_X N_X*) (X X*)^-1). Sensor noise moves eigenvalues inside the
  unit circle (spuriously more damped), with bias proportional to the noise variance divided by the POD energy. Low-energy
  modes are hit hardest. Bias dominates random error roughly when m^{1/2} SNR > N^{1/2}. The corrections remove this bias
  asymptotically. Similarity invariance is unchanged. BOP-DMD adds per-eigenvalue variance, but Sashidhar & Kutz do not
  address matching eigenvalues across bags explicitly. They seed every bag with the full-data optDMD solution.
- **Intervention support:** None directly (autonomous). They can be run per intervention regime or on DMDc residuals.
  Noise-bias correction matters if simulator readouts have observation noise. It does not matter for noise-free simulated
  full states.
- **Nonlinear capacity:** Linear only (same as DMD).
- **Interpretability:** Same as DMD, plus error bars (BOP-DMD).
- **Scaling (N, T, data size):** fbDMD and tlsDMD cost a small multiple of DMD. tlsDMD needs r < m/2 (Dawson et al.). optDMD is
  a nonlinear least-squares fit, and BOP-DMD runs it K times (e.g. K = 100) on subsets of p of m snapshots (p = 20 of 100
  was enough in their example).
- **Failure modes:** VarPro "often fails to converge" without a good initialisation (Sashidhar & Kutz), so initialise from
  exact DMD. fbDMD and tlsDMD also symmetrise process noise, which removes genuine stochastic forcing. noise-corrected DMD
  needs a known noise variance.
- **Relevance to problem (props 1-8):** Mainly (6): stable, unbiased spectra across seeds and procedures. BOP-DMD
  eigenvalue variances are a direct stability score. Useful for comparing spectra across implementations (7) without noise
  bias.
- **Open-source implementations:** PyDMD (FbDMD, TLS/optimal-closed-form, BOPDMD, optimized DMD) - MIT. Upstream MATLAB
  optdmd by Askham (not checked; licence not verified).
- **From-scratch simplicity:** fbDMD and tlsDMD are simple (tens of lines). optDMD and BOP-DMD are moderate (VarPro Jacobians,
  complex-valued optimisation). Use PyDMD.
- **References:**
  - Characterizing and correcting for the effect of sensor noise in the dynamic mode decomposition. S. T. M. Dawson,
    M. S. Hemati, M. O. Williams et al. 2016. Experiments in Fluids. https://arxiv.org/abs/1507.02264 [read-full]
  - De-biasing the dynamic mode decomposition for applied Koopman spectral analysis. M. S. Hemati, C. W. Rowley,
    E. A. Deem et al. 2017 (arXiv 2015). Theor. Comput. Fluid Dyn. https://arxiv.org/abs/1502.03854 [read-abstract]
  - Variable projection methods for an optimized dynamic mode decomposition. T. Askham, J. N. Kutz. 2018 (arXiv 2017).
    SIAM J. Appl. Dyn. Syst. (venue unverified). https://arxiv.org/abs/1704.02343 [read-abstract]
  - Bagging, optimized dynamic mode decomposition (BOP-DMD) for robust, stable forecasting with spatial and temporal
    uncertainty quantification. D. Sashidhar, J. N. Kutz. 2022 (arXiv 2021). Phil. Trans. R. Soc. A (venue unverified).
    https://arxiv.org/abs/2107.10878 [read-full]

### DMD with control and input-output DMD (DMDc, ioDMD)
- **Core idea:** DMDc fits x_{k+1} = A x_k + B u_k from [X; U] -> X'. If B is known, it fits A on X' - B U. If B is unknown, it
  takes an SVD of Omega = [X; U] at rank p and an SVD of X' at rank r < p, then projects:
  A_tilde = U_hat* X' V Sigma^-1 U_1* U_hat and B_tilde = U_hat* X' V Sigma^-1 U_2*.
  ioDMD (Annoni et al.; formulation as given by Benner, Himpe & Mitchell) also fits an output map:
  [X_1; Y_0] = [A B; C D][X_0; U_0], i.e. a least-squares state-space model (A, B, C, D).
- **Assumptions:** Linear time-invariant dynamics in the chosen coordinates, affine in u. Inputs are rich enough and not
  collinear with the state. Full state (DMDc) or state plus outputs (ioDMD) are measured.
- **Identifiability:** (A, B) are identified up to the same similarity as DMD (A -> S A S^-1, B -> S B, C -> C S^-1 in ioDMD).
  Transfer function and Markov parameters C A^j B are invariant. Proctor et al. assume sufficiently rich excitation but give
  no formal condition. If u is a function of x (feedback), A and B are not separable. The same point is made explicitly for
  SINDYc. Benner et al. compare excitation types: target data, persistent excitation (noise/steps) and "cross excitation"
  via initial-state perturbations. The last is directly analogous to simulator state-offset interventions.
- **Intervention support:** Yes. Input currents are u: stack per-unit current injections as columns of U. For held-out
  intervention *targets*, B learned in a reduced basis generalises only if the new target's input direction lies in the
  span seen in training. If the microscopic input map B_micro is known (current into unit i = e_i), use known-B DMDc in the
  full state or project it: B_r = U_r^T B_micro. This is **zero-shot for unseen targets**, which is a strong reason to keep
  the microscopic input map rather than learn B in latent space. State offsets = impulses in u, or extra initial conditions.
  Unit or connection removals are not representable (they change A).
- **Nonlinear capacity:** Linear. EDMDc is the lifted extension (see the Korda-Mezic entry).
- **Interpretability:** High (modes, B-columns = input directions). ioDMD gives a standard (A, B, C, D) usable with
  Gramians and balanced truncation.
- **Scaling (N, T, data size):** Two SVDs, O(N m min(N, m)). Cheap.
- **Failure modes:** Collinear inputs (feedback, smooth low-dimensional inputs) make B unidentifiable. Identified models may
  be unstable, so Benner et al. stabilise with a constrained fit |lambda(A)| < 1 - tau. Truncation choices p > r matter.
  Linear models cannot capture input-dependent gain changes (bilinear effects).
- **Relevance to problem (props 1-8):** (3) the only DMD variant that addresses interventions. Known-B projection gives
  held-out-target prediction for linear regimes. (1)/(2) tested with multi-step open-loop rollouts. Strong **baseline**
  ("PCA/DMD + linear dynamics with inputs").
- **Open-source implementations:** PyDMD DMDc (MIT); pykoopman DMDc/EDMDc (MIT). ioDMD: no maintained Python package checked.
  It is a single least-squares solve.
- **From-scratch simplicity:** Simple. Pitfall: fit the output map as y_k = C x_k + D u_k (same time index) and never regress on
  u_{k+1} (future input leakage). Note the index convention in Benner et al. (y_{k+1} = C x_k + D u_k, as written by them).
- **References:**
  - Dynamic mode decomposition with control. J. L. Proctor, S. L. Brunton, J. N. Kutz. 2016 (arXiv 2014). SIAM J. Appl.
    Dyn. Syst. (venue unverified). https://arxiv.org/abs/1409.6358 [read-full]
  - On reduced input-output dynamic mode decomposition. P. Benner, C. Himpe, T. Mitchell. 2018 (arXiv 2017). Adv. Comput.
    Math. https://arxiv.org/abs/1712.08447 [read-full]
  - Input-output dynamic mode decomposition. J. Annoni, P. Seiler et al. 2015. APS DFD abstract (original ioDMD; not
    opened, ADS page returned 405) [unverified]

### Extended DMD (EDMD)
- **Core idea:** Choose a dictionary psi(x) = [psi_1..psi_K] and compute G = (1/M) sum psi(x_m)* psi(x_m) and
  A = (1/M) sum psi(x_m)* psi(y_m). Then K = G^+ A. Eigenvectors xi_j give eigenfunctions phi_j(x) = psi(x) xi_j. Koopman modes
  come from left eigenvectors and the projection of the full-state observable onto the dictionary.
- **Assumptions:** The dictionary spans (approximately) a Koopman-invariant subspace. Data are sampled from a measure rho, and
  the result depends on rho. As M -> infinity, EDMD "almost surely converges" to the Galerkin projection of Koopman onto
  span(psi) in L2(rho) at Monte Carlo rate O(M^-1/2) (Williams et al. 2015).
- **Identifiability:** Eigenvalues and eigenfunctions of the *projected* operator, up to scalar per eigenfunction. They are not
  those of the true operator unless span(psi) is invariant. With a non-invariant dictionary, eigenfunctions go missing
  (e.g. a needed 5th-order term absent) and spurious ones appear (Williams et al.). This is spectral pollution (see ResDMD).
  For stochastic systems with exact state and process noise, EDMD approximates the stochastic Koopman operator E[psi(F(x, w))],
  i.e. the Kolmogorov backward generator. Only the interpretation of A changes.
- **Intervention support:** Initial-condition interventions: yes (pairs from anywhere, and sampling design shapes rho).
  Inputs: via EDMDc / Korda-Mezic (next entries).
- **Nonlinear capacity:** Universal in the limit of a rich dictionary. In practice it is limited by the dictionary and data.
  Dictionaries used by Williams et al.: Hermite polynomials (good for Gaussian-distributed data), thin-plate RBFs with
  centres from k-means, and discontinuous spectral elements. K ranged from 25 to more than 1,000.
- **Interpretability:** Moderate. Eigenfunctions are explicit functions of x (level sets = invariant partitions, e.g.
  basins). Leading eigenfunctions of the slowest eigenvalues are candidate slow coordinates z = phi(x).
- **Scaling (N, T, data size):** O(M K^2) to assemble and O(K^3) to solve. A polynomial dictionary of degree d in N variables has
  C(N+d, d) terms (N = 100, d = 2 gives 5,151; d = 3 gives 176,851, which is infeasible). So do POD/PCA to r ~ 10-30 first,
  or use kernels or RBFs. Need M >> K.
- **Failure modes:** Dictionary choice is "an open question" (Williams et al.). Spurious eigenvalues. Smooth dictionaries blur
  discontinuous eigenfunctions (basin boundaries). With noisy data some eigenvalues exist only because of noise. The
  full-state observable is not in span(psi), so reconstruction error adds to the dynamics error. Ill-conditioned G, so use
  truncated pseudoinverse or Tikhonov.
- **Relevance to problem (props 1-8):** (1) good for short to medium horizons if the dictionary is good. (4) eigenfunction level
  sets directly define microstate equivalence classes ("equal z => equal future" for the linear part). (5) k = number of
  retained eigenfunctions. (8) ResDMD residuals give an abstention test. Core **baseline** "EDMD/Koopman".
- **Open-source implementations:** pykoopman (EDMD, EDMDc, observables: polynomial, RBF, random Fourier features, time delay,
  custom) - MIT. deeptime EDMD/KernelEDMD - https://github.com/deeptime-ml/deeptime - active, ~889 stars - LGPL-3.0 (LICENSE
  read). PyDMD EDMD - MIT.
- **From-scratch simplicity:** Simple (20-30 lines). Pitfalls: use lstsq or an SVD-truncated pinv of Psi_X rather than
  inv(G). Include the constant and the linear state in the dictionary so C (the decoder) is linear. Standardise inputs before
  the RBFs. Evaluate on held-out *trajectories*, not held-out pairs.
- **References:**
  - A data-driven approximation of the Koopman operator: extending dynamic mode decomposition. M. O. Williams,
    I. G. Kevrekidis, C. W. Rowley. 2015 (arXiv 2014). J. Nonlinear Science. https://arxiv.org/abs/1408.4408 [read-full]
  - Modern Koopman theory for dynamical systems. S. L. Brunton, M. Budisic, E. Kaiser, J. N. Kutz. 2022 (arXiv 2021).
    SIAM Review (venue unverified). https://arxiv.org/abs/2102.12086 [read-full] (sections 1-2 only)

### Kernel DMD (KDMD)
- **Core idea:** Replace the explicit dictionary with a kernel k(x, x'). Build M x M Gram matrices G_hat_ij = k(x_i, x_j) and
  A_hat_ij = k(y_i, x_j), and compute an M-dimensional representation of the EDMD matrix. The cost depends on M and N, not on
  the (possibly infinite) feature dimension. Eigenfunctions at new points: phi(x) = [k(x, x_1)..k(x, x_M)] Q Sigma^+ v.
- **Assumptions:** As EDMD, with the feature space implicitly defined by the kernel. Truncation of small singular values is
  required. Williams et al. keep the 150 largest singular values "to avoid spurious unstable eigenvalues".
- **Identifiability:** As EDMD, for the kernel-induced dictionary. Results depend on the kernel and its bandwidth, and on the
  truncation rank. "No guarantee" that even the leading eigenvalues are accurate (Williams et al.).
- **Intervention support:** Autonomous. Controlled kernel variants exist, but I did not check them.
- **Nonlinear capacity:** High (polynomial kernel of degree 20 in the paper; Gaussian kernels).
- **Interpretability:** Lower than EDMD. Eigenfunctions are kernel expansions over training points.
- **Scaling (N, T, data size):** O(M^2 N) to assemble and O(M^3) to decompose. Practical up to M ~ 10^4. Evaluating at a new
  point costs O(M N) (Otto & Rowley note the same cost for kernel reconstructions).
- **Failure modes:** Kernel and bandwidth choice. Truncation acts as unprincipled regularisation. Accuracy decays for
  eigenvalues further "down" the spectrum. Memorisation risk: the model is a lookup over training points, which inflates
  in-distribution scores.
- **Relevance to problem (props 1-8):** Useful when N is large (hundreds to thousands of units) and a polynomial dictionary
  explodes. For (5) the eigenfunction count is small, but the encoder is non-parametric, which hurts (7) cross-implementation
  sharing. Also used by ResDMD to learn a dictionary.
- **Open-source implementations:** pykoopman KDMD (MIT); deeptime KernelEDMD (LGPL-3.0); PyDMD LANDO (kernel-based; MIT).
- **From-scratch simplicity:** Simple to moderate. Pitfalls: centring in feature space, conditioning (add a jitter), and
  choosing the bandwidth by cross-validated multi-step prediction rather than one-step error.
- **References:**
  - A kernel-based method for data-driven Koopman spectral analysis. M. O. Williams, C. W. Rowley, I. G. Kevrekidis. 2015
    (arXiv 2014). J. Computational Dynamics (venue unverified). https://arxiv.org/abs/1411.2260 [read-full]

### Residual DMD (ResDMD)
- **Core idea:** Also form L = Psi_Y* W Psi_Y, a Galerkin approximation of K*K, from the same data. For any candidate pair
  (lambda, g = Psi xi), this gives the residual ||(K - lambda) g|| / ||g|| **with respect to the true infinite-dimensional
  operator**, not just the finite matrix. Its uses:
  - Discard eigenpairs whose residual exceeds a tolerance epsilon.
  - Compute epsilon-pseudospectra free of spectral pollution, with convergence guarantees.
  - Compute smoothed spectral measures for measure-preserving systems.
  - A kernelised variant learns the dictionary on a data subset and then verifies it on the rest.
- **Assumptions:** Snapshots form a quadrature rule for the sampling measure (random i.i.d. initial conditions, or ergodic
  sampling along long trajectories for measure-preserving systems). M >> K is needed for accurate L. The fewer-snapshots
  regime is treated in a later paper (arXiv 2403.05891, not opened).
- **Identifiability:** Gives certified (lambda, eigenfunction) pairs up to epsilon, which separates real spectral content from
  discretisation artefacts. Scaling and eigenspace-basis non-uniqueness remain.
- **Intervention support:** None directly. It is a validation layer usable on any EDMD, DMD, DMDc or Koopman-AE latent model
  whose dictionary can be evaluated on (x, y) pairs.
- **Nonlinear capacity:** As the underlying dictionary. Handles continuous spectra (chaotic or mixing regimes), where plain
  EDMD produces spurious eigenvalues.
- **Interpretability:** High. The residual is a per-mode trust score. Colbrook et al. (JFM 2023) propose ordering modes by
  residual rather than modulus.
- **Scaling (N, T, data size):** Cost is the same order as EDMD plus pseudospectrum evaluation on a grid of z (one generalised
  eigen- or SVD-problem per grid point). The kernelised version targets very large state dimensions (the paper reports
  examples with more than 2 x 10^5 dimensions).
- **Failure modes:** Needs a good quadrature (i.i.d. samples or ergodicity). With few snapshots, L is rank-deficient. It certifies
  but does not fix a poor dictionary.
- **Relevance to problem (props 1-8):** Directly useful for (2) closure (a small residual for the retained eigenfunctions means
  the span is approximately invariant = Markov/closed in the linear sense), (6) spectral stability, and (8) abstention. If no
  small-residual set of k eigenfunctions exists, report "no compact linear state". A **recommended evaluation tool** for all
  Koopman-type candidates, including Koopman autoencoders: apply it to the learned encoder as a dictionary.
- **Open-source implementations:** MColbrook/Residual-Dynamic-Mode-Decomposition -
  https://github.com/MColbrook/Residual-Dynamic-Mode-Decomposition - MATLAB, ~47 stars, research code - BSD-2-Clause
  (LICENSE read). No Python package checked (a port is easy).
- **From-scratch simplicity:** Simple for the residual filter: res(lambda, xi) = sqrt(xi* (L - lambda A* - conj(lambda) A +
  |lambda|^2 G) xi / xi* G xi). This is the standard form as I recall it; the summarised page did not reproduce it (unverified).
  Pseudospectra are moderate.
- **References:**
  - Rigorous data-driven computation of spectral properties of Koopman operators for dynamical systems. M. J. Colbrook,
    A. Townsend. 2024 (arXiv 2021). Comm. Pure Appl. Math. (venue unverified). https://arxiv.org/abs/2111.14889 [read-full]
  - Residual dynamic mode decomposition: robust and verified Koopmanism. M. J. Colbrook, L. J. Ayton, M. Szoke. 2023
    (arXiv 2022). J. Fluid Mech. https://arxiv.org/abs/2205.09779 [read-abstract]

### Koopman lifted linear predictors with control / Koopman MPC (EDMDc, Korda-Mezic; bilinear variants)
- **Core idea:** Lift the state z = psi(x) and fit z+ = A z + B u and x_hat = C z by least squares:
  [A, B] = Y_lift [X_lift; U]^+ and C = X X_lift^+. The input stays **unlifted**, so linear MPC applies. Korda & Mezic
  stress that the data "is not required to come from one trajectory".
- **Assumptions:** Control-affine and linear in u in the lifted space. This is exact only for special systems; in general
  u enters bilinearly (the gradient of psi times the input vector field). Finite-horizon accuracy only: "one cannot hope
  that a trajectory of a linear system ... will be an accurate prediction ... for all future times".
- **Identifiability:** (A, B, C) up to similarity in the lifted space, as for DMDc. Theory gives convergence of finite-horizon
  predictions in L2(mu) for their basis structure (Corollary 1 in the paper).
- **Intervention support:** Strong for input interventions seen in training. Paper examples:
  - Van der Pol: 200 trajectories x 1,000 steps, u ~ Uniform[-1, 1], random initial conditions, lift = state + 100
    thin-plate RBFs (N_lift = 102).
  - Motor example: 3 output delays + 100 RBFs.
  - PDE example: state, squares, shifted products and a constant (385 functions).
  Held-out *targets*: the same issue as DMDc. Bilinear or interpolated-generator variants (Peitz, Otto & Rowley 2020) model
  input-dependent dynamics better; they show linear interpolation between operators is exact for control-affine systems.
- **Nonlinear capacity:** Moderate. It captures the nonlinear autonomous part through the lift. Input effects are linear (EDMDc)
  or bilinear (gEDMD-based variants).
- **Interpretability:** Moderate (linear A, B in lifted coordinates, readout C).
- **Scaling (N, T, data size):** As EDMD with K + n_u columns. MPC cost is like linear MPC with prediction horizon N_p.
- **Failure modes:** Error accumulation over long horizons. Poor B when input effects are strongly state-dependent. Random
  excitation must cover the operating region. The lifted dimension >> k, so it is not a minimal state. Only (A, C) restricted to
  a leading subspace are candidates for z.
- **Relevance to problem (props 1-8):** (3) the simplest nonlinear-in-state, input-aware predictor. It is a **baseline** for
  "EDMD/Koopman with control". For (5) follow with balanced truncation or rank reduction of (A, B, C) to get k (Otto & Rowley
  use BPOD on over-parameterised KDMD, next section but one).
- **Open-source implementations:** pykoopman EDMDc/DMDc (MIT). Korda-Mezic MATLAB code is linked from the paper (not checked;
  licence not verified).
- **From-scratch simplicity:** Simple (a least-squares solve). Pitfalls: fit on multi-step rollouts or at least validate
  multi-step. Regularise [A, B] (ridge). Keep x inside psi so C is well posed.
- **References:**
  - Linear predictors for nonlinear dynamical systems: Koopman operator meets model predictive control. M. Korda, I. Mezic.
    2018 (arXiv 2016). Automatica. https://arxiv.org/abs/1611.03537 [read-full]
  - Data-driven model predictive control using interpolated Koopman generators. S. Peitz, S. E. Otto, C. W. Rowley. 2020.
    SIAM J. Appl. Dyn. Syst. (venue unverified). https://arxiv.org/abs/2003.07094 [read-abstract]
  - PyKoopman: a Python package for data-driven approximation of the Koopman operator. S. Pan, E. Kaiser, B. M. de Silva
    et al. 2023. arXiv / JOSS (venue unverified). https://arxiv.org/abs/2306.12962 [read-abstract]

### Koopman generator EDMD for ODEs/SDEs (gEDMD)
- **Core idea:** Approximate the infinitesimal generator L instead of the time-tau operator. Apply L to the dictionary:
  (L psi)(x) = b(x) . grad psi + (1/2) a(x) : Hess psi, using drift and diffusion (known, or estimated from finite
  differences / Kramers-Moyal). Then solve M = dPsi Psi^+. Eigenvalues of M are continuous-time rates. Expressing the
  identity observable in the basis recovers the drift b(x) and diffusion a = sigma sigma^T. SINDy is a special case
  (Klus et al.).
- **Assumptions:** Access to time derivatives or small-step increments. The dictionary contains the drift and diffusion
  terms. Continuous-time Ito SDE.
- **Identifiability:** Generator eigenvalues and eigenfunctions up to scale. Drift and diffusion coefficients are identified in
  the chosen basis (up to library collinearity, as in SINDy).
- **Intervention support:** The paper covers MPC (control through switching or bilinear surrogate models, per the abstract).
  Initial-condition interventions work naturally.
- **Nonlinear capacity:** As the dictionary. Explicitly handles stochastic (noise-driven) simulators, which is relevant if the
  simulator has intrinsic noise.
- **Interpretability:** High (explicit drift and diffusion).
- **Scaling (N, T, data size):** As EDMD, plus dictionary gradient and Hessian evaluation. Hessians are costly for large N, so
  reduce dimension first.
- **Failure modes:** Noisy derivatives. Kramers-Moyal estimates need a small dt and many samples. Noisy data give non-sparse
  fits (per the paper, as summarised; unverified phrasing).
- **Relevance to problem (props 1-8):** A continuous-time alternative to EDMD when the simulator step is fine. It gives
  z-dynamics with explicit noise (a stochastic f), which is relevant for (2) Markov closure in the presence of intrinsic noise.
- **Open-source implementations:** Authors' d3s MATLAB/Python toolbox (not checked; licence not verified). deeptime does not
  list gEDMD in its decomposition API page as fetched.
- **From-scratch simplicity:** Moderate (analytic dictionary derivatives, e.g. via autodiff).
- **References:**
  - Data-driven approximation of the Koopman generator: model reduction, system identification, and control. S. Klus,
    F. Nuske, S. Peitz et al. 2020 (arXiv 2019). Physica D. https://arxiv.org/abs/1909.10638 [read-full]

### Transfer-operator linear methods: TICA, VAMP, Markov state models (TICA / VAMP / MSM)
- **Core idea:** Estimate instantaneous and time-lagged covariances C00, C01, C11 of feature functions at lag tau. Take the SVD
  of the whitened C00^-1/2 C01 C11^-1/2. Its top singular functions are the best rank-k linear model of the Koopman operator
  (Wu & Noe). VAMP-r score = sum of r-th powers of the singular values. VAMP-E is a Hilbert-Schmidt error estimate usable for
  cross-validation. TICA is the reversible or stationary special case (eigen- rather than singular decomposition). An MSM
  is the special case where the features are indicator functions of a state partition, giving a transition matrix.
  EDMD is recovered when the same basis is used at both times.
- **Assumptions:** Markov dynamics at lag tau in the full state. Stochastic dynamics: the theory needs a Hilbert-Schmidt
  (compact) Koopman operator, and "all conclusions ... are not applicable to deterministic systems" (Wu & Noe). This is
  important for a deterministic simulator. Adding small noise or treating ensembles over initial conditions is a workaround
  (unverified as to rigour). VAMP handles non-reversible and non-stationary data. TICA assumes reversibility or stationarity.
- **Identifiability:** Singular functions up to rotation within blocks of degenerate singular values, and up to sign. The
  k-dimensional *subspace* is identified when there is a singular-value gap. Implied timescales t_i = -tau / ln|lambda_i| are
  invariant and comparable across implementations.
- **Intervention support:** None built in. Interventions as initial conditions are fine. VAMP explicitly allows different
  distributions at t and t + tau, so it is suited to non-equilibrium ensembles started from perturbed states. Inputs would
  need a controlled extension (not reviewed).
- **Nonlinear capacity:** Linear in the features. MSMs are nonlinear through discretisation (clustering). VAMPnets are the
  deep version (next entry).
- **Interpretability:** High. Slow coordinates and implied timescales. MSM states are metastable sets.
- **Scaling (N, T, data size):** O(M F^2 + F^3) for F features. MSM cost is dominated by clustering. Needs many transitions
  per state pair.
- **Failure modes:** The lag choice trades Markovianity against resolution. Deterministic dynamics violate the theory.
  Oscillatory (non-reversible) dynamics break TICA. MSMs suffer discretisation error and poor clustering in high dimension.
- **Relevance to problem (props 1-8):** (2) the Chapman-Kolmogorov test K(n tau) ~ K(tau)^n is a **direct Markov-closure test
  for any learned z** and should be reused as an evaluation measure. (5) VAMP-E cross-validation over the dimension m gives a
  principled k. (6) the singular-value gap measures stability. (8) an MSM with no timescale separation suggests no compact
  state. Good **baseline** ("TICA/VAMP on PCA features + linear or MSM dynamics").
- **Open-source implementations:** deeptime (TICA, VAMP, KernelCCA, KVAD, EDMD, KernelEDMD, VAMPNet, TAE, TVAE; MSM:
  MaximumLikelihoodMSM, BayesianMSM, TransitionCountEstimator, TRAM, OOMReweightedMSM; also a SINDy) -
  https://github.com/deeptime-ml/deeptime - active, ~889 stars - **LGPL-3.0** (LICENSE.txt read).
- **From-scratch simplicity:** Simple for TICA and VAMP (covariances, whitening with eigenvalue cut-off, SVD). Pitfalls: remove
  the mean or add the constant function consistently. Regularise C00 (drop eigenvalues < 1e-10 relative). Build lagged
  pairs *within* trajectories only.
- **References:**
  - Variational approach for learning Markov processes from time series data (VAMP). H. Wu, F. Noe. 2020 (arXiv 2017).
    J. Nonlinear Science (venue unverified). https://arxiv.org/abs/1707.04659 [read-full]
  - Identification of slow molecular order parameters for Markov model construction (TICA). G. Perez-Hernandez, F. Paul,
    T. Giorgino et al. 2013. J. Chem. Phys. (venue unverified). https://arxiv.org/abs/1302.6614 [read-abstract]
  - deeptime docs, decomposition and Markov API pages. https://deeptime-ml.github.io/latest/api/index_decomposition.html,
    https://deeptime-ml.github.io/latest/api/index_markov.html [repo/docs]

### VAMPnets (deep VAMP)
- **Core idea:** Two network "lobes" (usually weight-shared) map x_t and x_{t+tau} to features, typically with a softmax output
  giving soft state memberships. Training maximises the VAMP-2 score ||C00^-1/2 C01 C11^-1/2||_F^2 + 1. A linear Koopman or
  MSM matrix is then estimated on the learned features.
- **Assumptions:** As VAMP (stochastic Markov dynamics at lag tau). There must be enough output nodes: at least the number of
  wanted singular functions + 1.
- **Identifiability:** Only the span of the top singular functions is identifiable (rotations, sign, and permutation of softmax
  states). Different seeds give different parameterisations of the same subspace.
- **Intervention support:** None (autonomous). Perturbation ensembles serve as data.
- **Nonlinear capacity:** High (deep encoder).
- **Interpretability:** Moderate to high with softmax (few metastable states and a transition matrix).
- **Scaling (N, T, data size):** Minibatch deep learning. The score needs covariance estimates per batch, so large batches are
  needed for stable whitening.
- **Failure modes:** "can get stuck in suboptimal local maxima". In the paper, fewer than 40% of runs succeeded on one example
  because rare slow processes were hard to find. Batch-covariance ill-conditioning. The lag tau must be chosen so that implied
  timescales are flat in tau. Deterministic dynamics fall outside the theory.
- **Relevance to problem (props 1-8):** A **tournament candidate** for an encoder objective that directly targets closure (2)
  and minimality (5) without a decoder. So it cannot "cheat" by reconstructing x, but it also does not ensure readout
  sufficiency, so add a readout head for y. Validate with Chapman-Kolmogorov and implied timescales. Its variance across seeds
  (6) is a known problem.
- **Open-source implementations:** deeptime VAMPNet (PyTorch) - LGPL-3.0.
- **From-scratch simplicity:** Moderate. The loss is short, but you need a numerically stable matrix inverse square root
  (eigendecomposition with epsilon clipping) and gradients through it.
- **References:**
  - VAMPnets for deep learning of molecular kinetics. A. Mardt, L. Pasquali, H. Wu, F. Noe. 2018 (arXiv 2017). Nature
    Communications. https://arxiv.org/abs/1710.06012 [read-full]

### Deep Koopman autoencoders (Lusch-Kutz-Brunton; LKIS by Takeishi et al.; LRAN by Otto-Rowley)
- **Core idea:** Learn encoder phi, decoder phi^-1 and a linear latent operator K so that phi(x_{t+m}) ~ K^m phi(x_t) and
  phi^-1(K^m phi(x_t)) ~ x_{t+m}. The three variants differ as follows.
  - **Lusch et al. 2018:**
    - Losses: reconstruction + linearity over all steps m = 1..T-1 + future-state prediction over S_p = 30 steps +
      L-infinity + l2 weight decay.
    - K is block-diagonal with 2x2 blocks exp(mu dt)[cos, -sin; sin, cos] whose (mu, omega) are output by an **auxiliary
      network** as functions of the latent radius. This handles continuous spectra with a single conjugate pair.
    - Training: Adam at lr 1e-3, autoencoder pretraining, random hyperparameter search.
  - **Takeishi et al. 2017 (LKIS):** minimise the least-squares residual ||Y1 - (Y1 Y0^+) Y0||_F of the latent pair
    regression (K computed in closed form) plus a reconstruction term to avoid trivial constant embeddings. A learned linear
    **delay embedder** of the last k observations handles partial observation.
  - **Otto & Rowley 2019 (LRAN):** a discounted multi-step loss over horizon T, with weights delta^tau (0 < delta <= 1), on
    both state reconstruction and latent prediction, normalised per step. K is learned jointly and initialised with
    eigenvalues on a circle of radius 0.8. Optionally alternate with Tikhonov-regularised EDMD solves for K. Also: balanced
    truncation (BPOD) of an over-parameterised KDMD model as a shallow alternative.
- **Assumptions:** A low-dimensional (approximately) Koopman-invariant subspace exists and the latent dimension is chosen a
  priori. Lusch et al. note the latent dimension p requires expert choice.
- **Identifiability:** Only the latent up to invertible linear maps S (z -> S z, K -> S K S^-1) for linear decoders. With
  nonlinear decoders, much more freedom: any diffeomorphism conjugating the linear flow. Latent eigenvalues are the stable,
  comparable quantity. The auxiliary-network variant makes K state-dependent, which weakens pure linear identifiability.
- **Intervention support:** Not in these papers (autonomous). Two natural extensions are (a) z+ = K z + B u and (b)
  **encoder-mediated intervention**: apply the microscopic intervention to x and re-encode, z' = phi(x + delta). Option (b)
  generalises to unseen targets if phi generalises off the training distribution. Otherwise it fails silently, so train with
  perturbed initial conditions.
- **Nonlinear capacity:** High in the encoder. Dynamics are linear or quasi-linear in latent space, so a single linear K
  cannot capture multistability (see cross-cutting note). The Lusch parametric-eigenvalue trick partly addresses
  continuous spectra.
- **Interpretability:** Moderate (eigenvalues and frequencies of K; latent eigenfunctions as network outputs).
- **Scaling (N, T, data size):** Standard deep learning. Examples used 5,000 to 20,000 training trajectories and 2-6 GPU hours
  (Lusch). Deep nets (up to about 22 hidden layers in Lusch's Table 2) are unnecessary for moderate N (unverified opinion).
- **Failure modes:** Local optima (LKIS explicitly). Trivial solutions without reconstruction or anti-collapse terms. Loss
  weight sensitivity. Unstable K producing blow-up in long rollouts. The encoder can smuggle information (e.g. absolute time or
  trajectory identity) into z if trajectories are not randomised. Decoder capacity can hide non-closure: the latent
  is not Markov but the decoder reconstructs well at t.
- **Relevance to problem (props 1-8):** Core **tournament candidate / baseline** ("Koopman autoencoder"). (1) multi-step
  prediction loss directly targets predictive sufficiency. (2) linear latent transition is closed by construction on
  training data. (5) sweep the latent dimension. (4) test by encoding distinct microstates with equal z. (6) compare K spectra
  across seeds. (7) implementation-specific encoders with one shared K is architecturally natural.
- **Open-source implementations:**
  - BethanyL/DeepKoopman - https://github.com/BethanyL/DeepKoopman - TensorFlow (version not checked, likely TF1),
    ~494 stars, stale research code - MIT (LICENSE read).
  - GaloisInc/dlkoopman - https://github.com/GaloisInc/dlkoopman - ~121 stars, state and trajectory predictors plus
    hyperparameter search; no control inputs mentioned - MIT (LICENSE read).
  - pykoopman NNDMD (MIT).
  - deeptime TAE/TVAE (time-lagged autoencoders; LGPL-3.0).
  - No official LKIS or LRAN code checked.
- **From-scratch simplicity:** Moderate. It is about 100 lines of PyTorch. Pitfalls:
  - Parameterise K for stability, e.g. spectral norm or block-rotation form with |lambda| <= 1.
  - Use multi-step losses (horizon 10-50) with curriculum.
  - Normalise the loss per horizon step.
  - Detach nothing that should be trained jointly.
  - Compute latent targets phi(x_{t+m}) with the same encoder.
- **References:**
  - Deep learning for universal linear embeddings of nonlinear dynamics. B. Lusch, J. N. Kutz, S. L. Brunton. 2018. Nature
    Communications. https://arxiv.org/abs/1712.09707 [read-full]
  - Learning Koopman invariant subspaces for dynamic mode decomposition. N. Takeishi, Y. Kawahara, T. Yairi. 2017. NeurIPS
    (NIPS 2017). https://arxiv.org/abs/1710.04340 [read-full]
  - Linearly-recurrent autoencoder networks for learning dynamics. S. E. Otto, C. W. Rowley. 2019 (arXiv 2017). SIAM J.
    Appl. Dyn. Syst. (venue unverified). https://arxiv.org/abs/1712.01378 [read-full]

### Consistent Koopman autoencoders (cKAE)
- **Core idea:** A Koopman autoencoder with a forward latent matrix C and a backward matrix D. Losses: identity
  (reconstruction), forward multi-step prediction, backward multi-step prediction, and a consistency penalty pushing DC ~ I and
  CD ~ I (on leading sub-blocks). Paper defaults: lambda_id = lambda_fwd = 1, lambda_bwd = 0.1, lambda_con = 0.01, 8 prediction
  steps. The penalty pushes eigenvalues toward the unit circle, which stabilises long rollouts.
- **Assumptions:** The dynamics are (approximately) invertible, i.e. backward dynamics exist. It is **invalid for strongly
  dissipative systems**, and performance degraded with added diffusion (Azencot et al.).
- **Identifiability:** As Koopman AE. The consistency constraint removes some freedom in K (it cannot be arbitrarily
  contractive) but not the similarity or encoder ambiguity.
- **Intervention support:** None (autonomous forecasting).
- **Nonlinear capacity:** High encoder, linear latent.
- **Interpretability:** Moderate (spectrum of C).
- **Scaling (N, T, data size):** About 1.8x the cost of a plain Koopman AE (paper).
- **Failure modes:** Wrong inductive bias for dissipative or contracting networks (e.g. leaky rate units, which decay to fixed
  points). The eigenvalue-near-unit-circle bias can overstate memory.
- **Relevance to problem (props 1-8):** Mostly (6) stability of long rollouts. Use it only as an ablation variant of the Koopman
  AE. Its assumption is likely violated by dissipative neural-population simulators (unverified for any specific simulator).
- **Open-source implementations:** Authors' code exists per the paper (repo not checked; licence not verified).
- **From-scratch simplicity:** Simple, given a Koopman AE (add D and two loss terms).
- **References:**
  - Forecasting sequential data using consistent Koopman autoencoders. O. Azencot, N. B. Erichson, V. Lin, M. W. Mahoney.
    2020. ICML 2020 (venue unverified). https://arxiv.org/abs/2003.02236 [read-full]

### SINDy and SINDy with control (SINDy, SINDYc)
- **Core idea:** Regress X_dot = Theta(X) Xi with a library Theta of candidate functions (constant, polynomials,
  trigonometric terms, ...) and sparse Xi. It uses sequentially thresholded least squares (STLSQ): LS fit, zero coefficients
  below lambda, refit on the survivors, iterate. Derivatives come from total-variation regularised differentiation when the
  data are noisy. The discrete-time variant x_{k+1} = f(x_k) avoids derivatives. For high-dimensional systems, apply it to POD
  coefficients. SINDYc extends the library to Theta(X, U) with cross terms.
- **Assumptions:** The dynamics are sparse in the library **in the given coordinates**. Accurate derivatives. The library columns
  are not (near-)collinear on the data. Parameters mu are handled by appending mu_dot = 0.
- **Identifiability:** Xi is identifiable only relative to the library and coordinates. A rotation or coordinate change turns a
  sparse model into a dense one (Brunton et al. list coordinate choice as an open issue). High-order polynomial libraries
  introduce degeneracy because combinations of powers mimic other exponentials (paper, discussion). With feedback u = k(x),
  "it is impossible to disambiguate the effect of the feedback control" and the regression "becomes ill-conditioned". The remedy
  is to inject white noise or occasional large impulses or steps in u (Brunton et al. 2016, SINDYc). For simulator
  interventions: use **open-loop random input currents and impulse kicks**, never inputs correlated with the state.
- **Intervention support:** Inputs: yes (SINDYc). Initial-condition interventions: yes (stack trajectories). Unit or connection
  removal: as a parameter mu in the library (a parametric normal form), identifiable only with several removal levels.
- **Nonlinear capacity:** As the library (polynomial degree 2-3 typical). Poor for saturating or sigmoidal nonlinearities
  unless those are included (the library must contain e.g. tanh(z) terms, which multiplies the column count).
- **Interpretability:** Highest in this area: explicit sparse equations.
- **Scaling (N, T, data size):** The library size is C(n+d, d) for n variables and degree d. Fine for n <= ~10 latent
  variables. For N = 100 raw units at degree 2 there are 5,151 columns per equation, which is ill-conditioned and slow. So
  use it only on low-dimensional coordinates (PCA, DMD or autoencoder latents). Each STLSQ iteration is one least-squares
  solve per equation.
- **Failure modes:** Noisy derivatives. The wrong coordinates give dense models. Threshold sensitivity (lambda interacts with
  coefficient scale, so standardise the library columns). Chaotic systems diverge pointwise even with a correct attractor.
  Identified models can be unstable in simulation.
- **Relevance to problem (props 1-8):** Mostly as f given a candidate z: (5) sparsity is an extra minimality measure. (6)
  coefficient stability across seeds is meaningful only after fixing a canonical coordinate frame (e.g. whitening plus
  Procrustes alignment). (7) a shared sparse f across implementations is a strong test of "same computation". Solid **baseline**
  ("PCA + SINDYc").
- **Open-source implementations:** PySINDy - https://github.com/dynamicslab/pysindy - active, ~1.9k stars. Optimisers: STLSQ,
  SR3, ConstrainedSR3, SINDyPI, MIOSR, TrappingSR3, SBR, EnsembleOptimizer. Weak and PDE libraries, control inputs, multiple
  differentiation methods - MIT (LICENSE read). deeptime also includes a SINDy (LGPL-3.0).
- **From-scratch simplicity:** Simple (STLSQ is about 15 lines). Pitfalls:
  - Normalise the library columns.
  - Fit per equation.
  - Use ridge in the refits.
  - Choose lambda by held-out multi-step simulation error (not derivative residual) along a Pareto front of sparsity
    versus error.
  - For discrete-time simulators, use the discrete-time form rather than differentiating.
- **References:**
  - Discovering governing equations from data by sparse identification of nonlinear dynamical systems. S. L. Brunton,
    J. L. Proctor, J. N. Kutz. 2016 (arXiv 2015). PNAS. https://arxiv.org/abs/1509.03580 [read-full]
  - Sparse identification of nonlinear dynamics with control (SINDYc). S. L. Brunton, J. L. Proctor, J. N. Kutz. 2016.
    IFAC NOLCOS. https://arxiv.org/abs/1605.06682 [read-full]

### Robust SINDy variants: ensemble-SINDy, weak SINDy, SINDy-PI (E-SINDy, WSINDy, SINDy-PI)
- **Core idea:**
  - **E-SINDy:** bootstrap aggregate SINDy fits (bagging = mean, bragging = median) over data subsets and/or library
    subsets (library bagging: l of D terms). Keep terms with inclusion probability above a threshold (e.g. 0.6 for bagging,
    0.4 for library bagging), typically with q = 100 models. The ensemble gives UQ and probabilistic forecasts. **Active
    learning** picks the initial condition (from 200 random candidates) with maximal ensemble forecast variance.
  - **Weak SINDy:** multiply the ODE by compactly supported test functions phi_k(t) = C(t-a)^p (b-t)^q and integrate by parts,
    giving G w = b with -<phi_k', y> on the right. No pointwise derivatives are needed, and coefficient error scales favourably
    with SNR.
  - **SINDy-PI:** for implicit or rational dynamics f(x, x_dot) = 0, try each library term theta_j as the left-hand side and
    solve a sparse regression on the rest. Select the model by held-out prediction error. It is "over 10^5 more measurement
    noise" tolerant than the older null-space implicit-SINDy on the paper's example.
- **Assumptions:** As SINDy. Weak SINDy needs test-function support hyperparameters (degree, support width, number of test
  functions). SINDy-PI needs a library that contains the numerator and denominator terms.
- **Identifiability:** As SINDy (library- and coordinate-relative). E-SINDy gives inclusion probabilities, i.e. a
  data-driven confidence that a term is identified. SINDy-PI resolves the scale ambiguity of implicit equations by fixing one
  term's coefficient to 1.
- **Intervention support:** E-SINDy explicitly demonstrated with MPC and active learning, which is **directly transferable to
  simulator experiment design**: pick the next initial state or intervention by ensemble disagreement. SINDy-PI allows forcing
  terms in the library. Weak SINDy works with inputs if u is integrable against the test functions.
- **Nonlinear capacity:** SINDy-PI adds rational functions (e.g. saturating responses x/(1+x)), which matter for saturating
  unit models. Otherwise as SINDy.
- **Interpretability:** High, plus UQ (E-SINDy).
- **Scaling (N, T, data size):** E-SINDy costs q x SINDy (library bagging reduces it). Weak SINDy's linear system is smaller than
  the data but needs more flops. SINDy-PI runs one regression per candidate LHS term, so it is |library| times more
  expensive.
- **Failure modes:** Weak SINDy degrades for fast timescales at high noise and for chaotic long horizons (paper). SINDy-PI
  libraries grow fast and become ill-conditioned. E-SINDy thresholds are heuristic.
- **Relevance to problem (props 1-8):** (6) E-SINDy inclusion probabilities are a ready-made stability score. Active
  learning addresses "counterexample-guided refinement" and experiment design. Weak form matters if the readouts are noisy.
- **Open-source implementations:** PySINDy (EnsembleOptimizer, WeakPDELibrary, SINDyPI optimiser) - MIT.
- **From-scratch simplicity:** E-SINDy is simple (a loop around STLSQ). Weak SINDy is moderate (test-function quadrature).
  SINDy-PI is moderate (many regressions plus a constrained variant needing cvxpy).
- **References:**
  - Ensemble-SINDy: robust sparse model discovery in the low-data, high-noise limit, with active learning and control.
    U. Fasel, J. N. Kutz, B. W. Brunton, S. L. Brunton. 2022 (arXiv 2021). Proc. R. Soc. A (venue unverified).
    https://arxiv.org/abs/2111.10992 [read-full]
  - Weak SINDy: Galerkin-based data-driven model selection. D. A. Messenger, D. M. Bortz. 2021 (arXiv 2020). Multiscale
    Model. Simul. (venue unverified). https://arxiv.org/abs/2005.04339 [read-full]
  - SINDy-PI: a robust algorithm for parallel implicit sparse identification of nonlinear dynamics. K. Kaheman, J. N. Kutz,
    S. L. Brunton. 2020. Proc. R. Soc. A. https://arxiv.org/abs/2004.02322 [read-full]

### SINDy autoencoder (SINDy-AE)
- **Core idea:** Jointly learn encoder z = phi(x), decoder x ~ psi(z) and sparse latent dynamics z_dot = Theta(z) Xi. The loss
  terms are:
  - reconstruction ||x - psi(phi(x))||^2;
  - SINDy loss in x, ||x_dot - (grad_z psi)(Theta(z) Xi)||^2 (weight lambda1);
  - SINDy loss in z, ||(grad_x phi) x_dot - Theta(z) Xi||^2 (weight lambda2);
  - L1 penalty on Xi (weight lambda3).
  Every 500 epochs, coefficients with |Xi| < 0.1 are set permanently to zero. The latent dimension is fixed in advance
  (1-3 in the paper's examples).
- **Assumptions:** Clean data with good derivatives. The authors state: "A current limitation of our approach is the
  requirement for clean measurement data that is approximately noise-free". A sparse model exists in *some* latent
  coordinates. The library (usually polynomial) is chosen a priori.
- **Identifiability:** The coordinates are not unique. Different initialisations give "similar but distinct solutions", so
  the authors select among multiple runs. Symmetries of the library (scaling, permutations, sign flips) remain. Sparsity
  selects among the coordinate systems, but only relative to the library.
- **Intervention support:** Not in the paper. Extension: Theta(z, u) as in SINDYc, or encoder-mediated interventions
  z' = phi(x + delta).
- **Nonlinear capacity:** High in the encoder, library-limited in the dynamics.
- **Interpretability:** High for f (explicit sparse ODE), low for phi.
- **Scaling (N, T, data size):** Needs Jacobian-vector products of the encoder and decoder per sample (autodiff: about 2-3x
  the cost of a plain AE). Library size is small because k is small.
- **Failure modes:** Needs derivatives of x (from the simulator's right-hand side, which is available for free in a
  simulator: **use the simulator's own x_dot instead of finite differences**). Thresholding schedule sensitivity. Collapse to
  trivial dynamics if lambda3 is too large. Seed variance.
- **Relevance to problem (props 1-8):** A **tournament candidate** for (5) minimality and interpretability. The shared-f
  across implementations (7) is especially natural: encoders per implementation, one sparse Xi. (6) seed variance is a known
  issue, so run multiple seeds and compare Xi after canonical alignment.
- **Open-source implementations:** kpchamp/SindyAutoencoders - https://github.com/kpchamp/SindyAutoencoders - TensorFlow
  (version not checked), ~392 stars, stale research code - MIT (LICENSE read).
- **From-scratch simplicity:** Moderate. In PyTorch use torch.func.jvp for the chain-rule terms. Pitfalls: normalise z (the
  latent scale interacts with the fixed threshold 0.1). Anneal lambda3. Refine Xi without L1 at the end.
- **References:**
  - Data-driven discovery of coordinates and governing equations. K. Champion, B. Lusch, J. N. Kutz, S. L. Brunton. 2019.
    PNAS. https://arxiv.org/abs/1904.02107 [read-full]

### Operator inference (OpInf) - brief
- **Core idea:** Project snapshots onto a POD basis V_r. Then fit a polynomial reduced model, e.g.
  q_dot = c + A q + H (q kron q) + B u, by (Tikhonov-regularised) least squares on projected states and their time derivatives.
  This is non-intrusive: it needs no access to operators, only snapshots. Peherstorfer (2019) shows that fitting to projected
  raw trajectories incurs **non-Markovian closure error**: the reduced state depends on its history (Mori-Zwanzig). He proposes
  **re-projection sampling**: step the full simulator from V_r q_k one step, project back, and repeat. The learned operators
  then *exactly* equal the intrusive projection-based reduced model, under the stated conditions (polynomial dynamics,
  sufficient data).
- **Assumptions:** Polynomial (or lifted-to-polynomial) full model structure. A linear POD subspace. Re-projection needs a
  simulator that can be **initialised at arbitrary states**, which we have.
- **Identifiability:** Operators are identified exactly (w.r.t. the chosen basis) with re-projection. They are unique up to the
  choice of V_r, and orthogonal changes of basis transform them covariantly.
- **Intervention support:** Inputs via B u. Parametric variants mu -> A(mu). The ability to set arbitrary states is exploited
  directly by re-projection.
- **Nonlinear capacity:** Polynomial (quadratic or cubic) on a linear subspace. Lifting transformations extend this.
- **Interpretability:** Moderate (reduced operators).
- **Scaling (N, T, data size):** Least squares with r + r(r+1)/2 + m columns. Fine for r <= 30.
- **Failure modes:** Ill-conditioning (needs regularisation). Linear subspaces are inefficient for nonlinear manifolds. Without
  re-projection, the closure error is absorbed into biased operators.
- **Relevance to problem (props 1-8):** Re-projection is a **simulator-specific tool for testing Markov closure (2)** of any
  candidate linear encoder: compare the model fitted to raw projected trajectories with the one fitted to re-projected
  trajectories. A large gap means the subspace is not closed. The same idea generalises to nonlinear encoders if a decoder
  exists (lift, step the simulator, re-encode), which relates to prop (4) microstate invariance.
- **Open-source implementations:** opinf - https://github.com/operator-inference/opinf (formerly
  Willcox-Research-Group/rom-operator-inference-Python3) - active, ~85 stars, docs at operator-inference.github.io/opinf -
  MIT (LICENSE read).
- **From-scratch simplicity:** Simple (build the quadratic features without redundant symmetric terms, then ridge regression).
  Re-projection is simple given simulator access.
- **References:**
  - Data-driven operator inference for nonintrusive projection-based model reduction. B. Peherstorfer, K. Willcox. 2016.
    Comput. Methods Appl. Mech. Eng. 306 (page returned 403; not opened) [unverified]
  - Sampling low-dimensional Markovian dynamics for pre-asymptotically recovering reduced models from data with operator
    inference. B. Peherstorfer. 2020 (arXiv 2019). SIAM J. Sci. Comput. (venue unverified). https://arxiv.org/abs/1908.11233 [read-full]
  - Learning nonlinear reduced models from data with operator inference. B. Kramer, B. Peherstorfer, K. Willcox. 2024.
    Annu. Rev. Fluid Mech. 56 (seen only in search results) [unverified]
  - opinf repository README and LICENSE. https://github.com/operator-inference/opinf [repo/docs]

---

## C. Predictive states, causal states, bisimulation and abstraction refinement

_Source notes: `notes\area_C_psr_causal_states_bisim.md`._

Scope: predictive state representations (PSRs) and spectral learning; causal states / computational mechanics; past-future
information bottleneck; bisimulation, lumpability and RL state abstraction; counterexample-guided abstraction refinement
(CEGAR) and active automata learning. Methods only.

How to read the tags: [read-full] = substantial body text read (often via arXiv HTML); [read-abstract] = abstract/landing
page only; [repo/docs] = repository or documentation read; [unverified] = not opened (bibliographic data from search
snippets or memory). Formal statements marked "(unverified)" are from memory and were not checked in the source.

### Unifying view for this area (why it matters to the contract)

All methods here define "state" as an **equivalence class**: two things (histories, or microstates x) are equivalent iff
they cannot be told apart by any allowed experiment ("test"). They differ in (a) what counts as a test (future
observation sequences under input sequences; rewards; value functions; logical properties), (b) exact vs approximate
(metric) equivalence, and (c) how the classes are found (spectral factorisation of a test matrix, splitting of classes
by statistical tests, fixed points of a metric operator, gradient-trained encoders, or query/counterexample loops).

For our simulator the key simplification is that **microstates are observable and resettable**. The contract's
property (4) "microstates with equal z have equal futures" is exactly the definition of a causal state / PSR state when
histories are replaced by microstates x:
  x ~ x'  iff  P(y_{t+1:t+H} | x_t = x, u_{t:t+H}, a) = P(y_{t+1:t+H} | x_t = x', u_{t:t+H}, a)
for all input sequences u, horizons H, and (for property 3) all allowed interventions a.
That relation is automatically closed (property 2): if x ~ x' then, for every input u, the next microstates are
equivalent in distribution (a standard property of causal states / bisimulations: the quotient is unifilar / Markov;
stated here from the definitions, not from a single checked theorem). Minimality (5) is "the coarsest such partition";
abstention (8) corresponds to "the number of classes / the rank of the test matrix does not saturate".
In the linear-Gaussian deterministic case this reduces to the quotient by the unobservable subspace (cross-ref.
minimal-realisation area).

---

### Predictive state representations and the system-dynamics matrix (PSR, linear PSR, OOM)
- **Core idea:** State = vector of predictions p(t | h) for a set of core "tests" t (action/input-conditioned future
  observation sequences). The system-dynamics matrix D has rows = histories, columns = tests, entries = test success
  probabilities; its rank (the "linear dimension") is the minimal size of a linear PSR, and it is no larger than the
  number of states of the minimal POMDP. Updates are linear-fractional in the prediction vector.
- **Assumptions:** Discrete time; typically finite observation and action alphabets; finite rank of D (finite linear
  dimension); stationarity of the controlled process; well-defined input-conditioned test probabilities (policy
  independent, "blind" or open-loop tests).
- **Identifiability:** The predictive state itself is observable (a vector of future-probabilities), so it is
  identified without any latent-variable ambiguity once the core-test set is fixed; different core-test sets give
  states related by an invertible linear map. The class of equivalent histories (same row of D) is identified exactly.
- **Intervention support:** Actions/inputs are part of the tests, so input-conditioned prediction is native. Discrete
  interventions can be added as extra actions; held-out intervention types are not covered unless they are expressible
  as input sequences already in the test algebra.
- **Nonlinear capacity:** Linear in prediction space, but can represent any finite-rank process (includes all finite
  POMDPs and k-th order Markov models, which PSRs strictly generalise). Continuous nonlinear dynamics generally have
  infinite rank; need kernels/features (see HSE-PSR, PSRNN).
- **Interpretability:** High in principle: each state coordinate is "probability of this experiment's outcome".
- **Scaling (N, T, data size):** D is estimated from counts; number of candidate tests grows exponentially in horizon;
  discovering core tests is the hard part. With a resettable simulator rows can be sampled directly.
- **Failure modes:** Estimated D is full rank due to noise -> rank selection needed; predictions can leave the valid
  probability simplex (negative probabilities) after errors accumulate; no likelihood for general PSRs.
- **Relevance to problem (props 1-8):** (1) by construction; (2) closed by construction (state update depends only on
  state and new input/output); (4) exactly the PSR equivalence; (5) rank of D = minimal linear dimension; (8) rank that
  keeps growing with test length is a natural abstention signal. Main mismatch: our y is continuous and multivariate.
- **Open-source implementations:** No maintained general PSR package located. `emic` (github.com/johnazariah/emic,
  MIT, 3 stars, early-stage) has a spectral learner for epsilon-machines (discrete symbols).
- **From-scratch simplicity:** Simple for discrete tests with resets: build D from simulated rollouts, SVD, pick rank.
  Pitfalls: normalisation, choosing test set, negative probabilities.
- **References:**
  - Predictive Representations of State. M. L. Littman, R. S. Sutton, S. Singh. 2001 (NIPS 14, published 2002). https://proceedings.neurips.cc/paper/2001/hash/1e4d36177d71bbb3558e43af9577d70e-Abstract.html [read-abstract]
  - Predictive State Representations: A New Theory for Modeling Dynamical Systems. S. Singh, M. James, M. Rudary. 2004. UAI 2004. https://arxiv.org/abs/1207.4167 [read-abstract]

### Spectral / method-of-moments learning of HMMs and transformed PSRs (HKZ spectral HMM, TPSR, two-stage regression)
- **Core idea:** Estimate low-order moment matrices (e.g. P(x_{t+1}, x_t), P(x_{t+2}, x_{t+1}=o, x_t)), take an SVD of the
  past-future (Hankel) matrix, and recover "observable operators" B_o = U^T P_{3,o,1} (U^T P_{2,1})^+ that update a
  k-dimensional predictive state. TPSRs do the same for controlled systems (actions), giving a PSR up to an invertible
  linear transform; two-stage regression (2SR) generalises this to instrumental-variable regressions with features.
- **Assumptions:** Finite rank k; spectral separation (smallest singular values of the relevant matrices bounded away
  from zero); stationarity or reset-based sampling; for control, an exploration policy that covers the tests.
- **Identifiability:** Operators recovered up to a similarity transform S (B_o -> S B_o S^{-1}); the predictive
  distribution over observable sequences is identified. Statistically consistent.
- **Intervention support:** TPSR: actions as inputs (the Boots-Siddiqi-Gordon paper closes the loop to planning).
  Interventions only as extra action symbols.
- **Nonlinear capacity:** Exact for finite-state latent processes; for continuous dynamics requires features/kernels.
- **Interpretability:** Moderate; states are linear transforms of predictions of feature-futures.
- **Scaling (N, T, data size):** Just SVD and matrix products; HKZ sample complexity does not depend explicitly on the
  number of distinct observations (only through spectral quantities). Cost dominated by covariance estimation, O(T d^2)
  in the feature dimension d.
- **Failure modes:** Poor finite-sample inference because the estimator minimises parameter error, not filtering error
  (Downey, Hefny, Gordon 2017 stress this); error compounding in the recursive filter; negative probabilities; rank
  selection sensitivity; small singular values amplify noise.
- **Relevance to problem (props 1-8):** Directly a baseline for (1),(2),(5): the singular value spectrum of the
  input-conditioned past-future Hankel matrix is the classic minimal-dimension diagnostic; plateau/no-plateau informs (8).
  With a resettable simulator, "past" can be replaced by microstate features (rows = sampled x, columns = future features
  under probe inputs), which yields a microstate-to-predictive-state regression.
- **Open-source implementations:** No maintained Python package found for TPSR/2SR (licence not verified for any
  paper-code). `emic` spectral (MIT) for discrete symbol processes.
- **From-scratch simplicity:** Simple (tens of lines) for the linear/discrete case; moderate with features and
  controls. Pitfalls: regularise pseudo-inverses (ridge), use held-out rank choice, whiten features.
- **References:**
  - A Spectral Algorithm for Learning Hidden Markov Models. D. Hsu, S. M. Kakade, T. Zhang. 2009 (arXiv 2008; JCSS 78(5), 2012). https://arxiv.org/abs/0811.4413 [read-abstract]
  - Closing the Learning-Planning Loop with Predictive State Representations. B. Boots, S. M. Siddiqi, G. J. Gordon. 2009 arXiv (IJRR 2011, unverified). https://arxiv.org/abs/0912.2385 [read-abstract]
  - Practical Learning of Predictive State Representations. C. Downey, A. Hefny, G. Gordon. 2017. arXiv. https://arxiv.org/abs/1702.04121 [read-abstract]

### Hilbert space embeddings of PSRs (HSE-PSR, kernel PSR)
- **Core idea:** Represent the predictive state as a conditional embedding operator of future-observation
  distributions in an RKHS, so continuous actions and observations are handled nonparametrically; learned by a kernel
  analogue of the spectral algorithm.
- **Assumptions:** Characteristic kernels; finite (effective) rank of the covariance operators; stationarity or resets;
  regularisation parameters controlling conditional embedding estimates.
- **Identifiability:** Predictive state identified up to invertible linear transform in the (finite-rank projection of
  the) RKHS; consistent under the paper's conditions.
- **Intervention support:** Continuous action/input sequences handled natively.
- **Nonlinear capacity:** High (nonparametric), limited by kernel choice and sample size.
- **Interpretability:** Low-moderate; states are coefficients over training samples.
- **Scaling (N, T, data size):** Gram matrices O(n^2) memory, O(n^3) time in number of samples n; needs random features or
  Nystrom for > ~10^4 samples (unverified for this paper; standard for kernel methods).
- **Failure modes:** Kernel bandwidth sensitivity; curse of dimensionality in N; regularisation-bias; costly filtering.
- **Relevance to problem (props 1-8):** Continuous-valued version of predictive equivalence (4); good as a principled
  nonparametric reference on low-dimensional readouts y, not on the full x.
- **Open-source implementations:** None located (licence not verified).
- **From-scratch simplicity:** Moderate (kernel two-stage regression with ridge); numerical pitfalls in inverting Gram
  matrices.
- **References:**
  - Hilbert Space Embeddings of Predictive State Representations. B. Boots, G. Gordon, A. Gretton. 2013. UAI 2013. https://arxiv.org/abs/1309.6819 [read-abstract]

### Learned predictive-state filters: PSIM, PSRNN, inference-gradient refinement
- **Core idea:** Keep the "state = sufficient statistic of future observations" constraint but learn the filter
  discriminatively. PSIM learns the predictive-state update as a composition of supervised predictors (DAgger-style
  training on its own rollouts), with guarantees in realizable and agnostic settings. PSRNN uses a bilinear
  (observation-gated) update derived from Bayes filtering, initialised by two-stage regression then trained by BPTT;
  tensor factorisation links it to multiplicative RNN/LSTM gates. Inference Gradients: spectral init + PSIM-style
  gradient refinement.
- **Assumptions:** Predictive state (features of a finite future window) is a sufficient statistic; enough data to
  regress; for guarantees, a no-regret learner (PSIM).
- **Identifiability:** State is anchored to explicit future-feature statistics, so it is identifiable up to the linear
  map between feature choices; after BPTT the anchoring weakens (unverified whether PSRNN retains it).
- **Intervention support:** Actions/inputs in PSRNN via the bilinear gating (controlled variants such as RPSP networks
  exist; not read). Interventions only as extra inputs.
- **Nonlinear capacity:** Moderate-high (features, bilinear gating, BPTT).
- **Interpretability:** Moderate: each state dimension regresses onto future-feature expectations.
- **Scaling (N, T, data size):** Like RNNs; 2SR init is linear algebra on features.
- **Failure modes:** Future window too short -> non-sufficient state; BPTT drifts away from predictive semantics;
  covariate shift in filtering (PSIM addresses via DAgger).
- **Relevance to problem (props 1-8):** A strong "predictively sufficient + closed" baseline family: the loss directly
  enforces (1) over a window and the recursive update enforces (2). The "anchor state to explicit future statistics"
  trick is a direct guard against dimension cheating (state coordinates cannot hide arbitrary codes).
- **Open-source implementations:** Paper code not verified (licence not verified).
- **From-scratch simplicity:** Moderate: implement future-feature targets, 2SR init, then a bilinear RNN with multi-step
  loss.
- **References:**
  - Learning to Filter with Predictive State Inference Machines. W. Sun, A. Venkatraman, B. Boots, J. A. Bagnell. 2016. ICML 2016. https://arxiv.org/abs/1512.08836 [read-abstract]
  - Predictive State Recurrent Neural Networks. C. Downey, A. Hefny, B. Li, B. Boots, G. Gordon. 2017. NeurIPS 2017 (venue unverified; arXiv read). https://arxiv.org/abs/1705.09353 [read-abstract]
  - Practical Learning of Predictive State Representations. C. Downey, A. Hefny, G. Gordon. 2017. https://arxiv.org/abs/1702.04121 [read-abstract]

### Causal states, epsilon-machines and statistical complexity (computational mechanics)
- **Core idea:** Two pasts are equivalent iff they induce the same conditional distribution over futures; the classes
  are causal states, and the process's epsilon-machine (states + transitions) is the minimal optimal predictor.
  Statistical complexity C_mu = entropy of the causal-state distribution. Theorems: causal states are prescient
  (sufficient for prediction), minimal among prescient rivals, unique, and their transitions are deterministic given the
  next symbol (unifilar), hence Markov.
- **Assumptions:** Stationary (conditionally) stochastic process; originally discrete symbols and discrete time.
- **Identifiability:** The partition (causal states) and its transition structure are uniquely defined by the process;
  any other prescient partition is a refinement of it (up to measure-zero sets). No coordinate ambiguity: the object is
  a partition, not coordinates.
- **Intervention support:** None for output-only processes; see epsilon-transducers (below) for inputs.
- **Nonlinear capacity:** Fully general (no functional form); but finite epsilon-machines exist only for some processes;
  many (incl. chaotic continuous systems observed without coarse-graining) have infinitely many or uncountably many causal
  states.
- **Interpretability:** High for finite machines (small graphs); C_mu is a scalar memory measure.
- **Scaling (N, T, data size):** Definition-level; estimation is the hard part (see CSSR / kernel methods).
- **Failure modes:** Infinite/uncountable causal-state sets; C_mu estimates biased by history length and sample size.
- **Relevance to problem (props 1-8):** The cleanest formalisation of (4) microstate invariance + (5) minimality + (2)
  Markov closure (unifilarity). Minimality theorem justifies "coarsest predictive partition" as the ground-truth target
  of (5). (8): a process with divergent C_mu (or causal-state count growing with resolution/history) signals no compact
  state. With microstate access, "pasts" can be replaced by microstates x; then the causal-state map is epsilon(x) =
  law of future outputs given x (and inputs).
- **Open-source implementations:** CMPy (Crutchfield group, "Computational Mechanics Python") is referenced by
  third-party repos (e.g. github.com/cstrelioff/cbayes) but I did not locate a public CMPy repository (licence not
  verified). `emic` (MIT, early-stage).
- **From-scratch simplicity:** Definitions are simple; estimation is moderate (see next entries).
- **References:**
  - Inferring Statistical Complexity. J. P. Crutchfield, K. Young. 1989. Physical Review Letters 63, 105. https://csc.ucdavis.edu/~cmg/compmech/pubs/ISCTitlePage.htm [read-abstract]
  - Computational Mechanics: Pattern and Prediction, Structure and Simplicity. C. R. Shalizi, J. P. Crutchfield. 2001. Journal of Statistical Physics 104. https://arxiv.org/abs/cond-mat/9907176 [read-abstract]

### CSSR and epsilon-transducers (input-output causal states)
- **Core idea:** CSSR (Causal-State Splitting Reconstruction) grows history length L up to L_max; histories are assigned
  to existing states if a hypothesis test (chi^2/KS/G) cannot reject equality of their next-symbol distributions,
  otherwise a new state is split off; then states are split until transitions are deterministic (recursive/unifilar).
  Epsilon-transducers extend causal states to input-output channels: two joint input-output pasts are equivalent iff
  they give the same distribution of future outputs conditional on future inputs; the transducer is the minimal optimal
  such model.
- **Assumptions:** Discrete-valued, discrete-time, stationary, finite L_max adequate (process has finite-order causal
  states, i.e. histories of length L_max suffice to determine the state); enough samples for the tests.
- **Identifiability:** Converges to the true causal-state partition under the stated conditions (per the paper's
  abstract "under certain conditions"; exact conditions unverified here).
- **Intervention support:** epsilon-transducers handle exogenous inputs, i.e. input-conditioned predictive equivalence,
  which is the right notion for u(t). Interventions as additional input symbols.
- **Nonlinear capacity:** Fully nonparametric over discrete symbols.
- **Interpretability:** High (small state graphs; C_mu).
- **Scaling (N, T, data size):** Exponential in L_max times alphabet size; needs symbolisation of continuous data, which
  is itself a strong (and often misleading) abstraction choice.
- **Failure modes:** Symbolisation artefacts (generating vs non-generating partitions); multiple testing errors create
  spurious states; L_max too small merges distinct states; data hunger for large alphabets.
- **Relevance to problem (props 1-8):** Template for a **split-by-statistical-test** refinement loop: the CSSR split
  criterion is exactly a "counterexample validator" for predictive equivalence. transCSSR's input/output version matches
  our (u -> y) setting if u, y are coarse-grained. Number of states vs L_max curve = abstention diagnostic (8).
- **Open-source implementations:**
  - CSSR (C++, original by Shalizi) - https://bactra.org/CSSR/ , GitHub mirror https://github.com/stites/CSSR - old/stable - GPL (per homepage) [repo/docs]
  - transCSSR (Python, epsilon-transducers) - https://github.com/ddarmon/transCSSR - moderately maintained, ~32 stars, numpy/scipy only - GPL (per repo page) [repo/docs]
  - emic (Python; CSSR, spectral, CSM, Bayesian) - https://github.com/johnazariah/emic - 3 stars, early-stage - MIT [repo/docs]
- **From-scratch simplicity:** Moderate: straightforward suffix-tree counting + hypothesis tests, but the determinisation
  step and edge cases have "known issues" noted on the CSSR homepage.
- **References:**
  - Blind Construction of Optimal Nonlinear Recursive Predictors for Discrete Sequences. C. R. Shalizi, K. L. Shalizi (Klinkner). 2004. UAI 2004. https://arxiv.org/abs/cs/0406011 [read-abstract]
  - Computational Mechanics of Input-Output Processes: Structured transformations and the epsilon-transducer. N. Barnett, J. P. Crutchfield. 2015 (arXiv 2014). Journal of Statistical Physics. https://arxiv.org/abs/1412.2690 [read-abstract]
  - CSSR homepage. C. R. Shalizi. https://bactra.org/CSSR/ [repo/docs]

### Continuous-valued causal states: kernel epsilon-machines and topology of predictive states
- **Core idea:** Embed the conditional distribution of futures given a past into an RKHS (kernel mean embedding); pasts
  with equal embeddings are the same causal state. A reduced-dimension (diffusion-map-like) transform of the embedded
  causal states gives coordinates ("causal diffusion components") and a finite- or infinite-state kernel epsilon-machine,
  with evolution operators estimated in RKHS; Loomis & Crutchfield show predictive states converge from empirical samples
  in the weak topology of measures and that Hilbert-space embeddings preserve this topology.
- **Assumptions:** Stationarity; characteristic kernels on past and future windows; finite past/future window lengths;
  enough samples to estimate conditional embeddings.
- **Identifiability:** Causal-state set identified as a metric/topological object (weak topology); coordinates from the
  spectral reduction are defined up to the usual diffusion-map ambiguities (sign/rotation within degenerate
  eigenspaces; unverified detail).
- **Intervention support:** Not in the read abstracts (output-only processes).
- **Nonlinear capacity:** High; applicable to discrete or continuous events/time.
- **Interpretability:** Moderate: low-dimensional coordinates of the causal-state manifold.
- **Scaling (N, T, data size):** Kernel methods: O(n^2)-O(n^3) in samples; window-dimension issues for large N.
- **Failure modes:** Bandwidth and window-length choices dominate; spectral gap may be absent (no clear dimension).
- **Relevance to problem (props 1-8):** The closest existing method to "predictive equivalence for continuous x":
  replace past windows by microstates x (available!) and futures by (u-conditioned) output windows. Spectral-gap of the
  causal-state kernel is a direct minimality/abstention diagnostic (5, 8). Needs input-conditioning for our u(t).
- **Open-source implementations:** No code link found on the arXiv pages read (licence not verified).
- **From-scratch simplicity:** Moderate: conditional mean embeddings + diffusion maps are standard linear algebra;
  pitfalls are regularisation and bandwidth.
- **References:**
  - Discovering Causal Structure with Reproducing-Kernel Hilbert Space epsilon-Machines. N. Brodu, J. P. Crutchfield. 2022 (arXiv 2020). Chaos 32, 023103. https://arxiv.org/abs/2011.14821 [read-abstract]
  - Inferring Kernel epsilon-Machines: Discovering Structure in Complex Systems. A. M. Jurgens, N. Brodu. 2024. arXiv. https://arxiv.org/abs/2410.01076 [read-abstract]
  - Topology, Convergence, and Reconstruction of Predictive States. S. P. Loomis, J. P. Crutchfield. 2021. arXiv. https://arxiv.org/abs/2109.09203 [read-abstract]

### Predictive information and the past-future information bottleneck (PFIB, I_pred, DCA, CPIC)
- **Core idea:** Predictive information I_pred(T) = I(past_T; future_T). Its growth with T classifies processes: finite
  (bounded), logarithmic (finite-parameter models; coefficient ~ number of parameters/2), power-law (nonparametric). The
  past-future information bottleneck compresses the past into Z maximising I(Z; future) - beta^{-1} I(Z; past); for
  Gaussian (linear) systems this is a generalised eigenvalue problem related to CCA, and increasing beta adds state
  dimensions at structural phase transitions. DCA finds a linear projection V maximising Gaussian I_pred of the
  projected series: I_pred = log|Sigma_T(Y)| - 0.5 log|Sigma_2T(Y)|. CPIC adds a compression term and variational MI bounds
  (stochastic linear encoder) to capture non-Gaussian predictive information.
- **Assumptions:** Stationarity; DCA/PFIB-linear: Gaussianity; finite window T; CPIC: validity of variational bounds.
- **Identifiability:** DCA/PFIB-linear: the predictive subspace (not a basis) is identified, i.e. up to invertible linear
  transforms within the subspace; non-convex objective for DCA (multiple restarts).
- **Intervention support:** PFIB of Creutzig et al. is input-past -> output-future (so exogenous inputs are native);
  DCA/CPIC are autonomous (no inputs) as published.
- **Nonlinear capacity:** DCA linear; kernel/nonlinear extensions discussed but not developed in the paper; CPIC mostly
  linear encoder with stochasticity; PFIB general in principle, tractable in the Gaussian case.
- **Interpretability:** High for linear projections (loadings over units).
- **Scaling (N, T, data size):** DCA: covariance O(n^2 T^2 T_tot), per-evaluation O(T n^2 d + T n d^2 + T^3 d^3) (from the
  paper); fine for n ~ 100-1000, T ~ 5-20.
- **Failure modes:** Gaussian I_pred misses nonlinear predictive structure; window T choice unguided; ill-conditioned
  covariances need diagonal regularisation; I_pred-maximisation favours slow/oscillatory components and may ignore
  input-driven components if u is not included.
- **Relevance to problem (props 1-8):** (1) and (5): the beta-sweep or d-sweep of I_pred(d) gives a principled
  "information-vs-dimension" curve; plateau -> k. (8): Bialek et al.'s taxonomy is the theoretical basis for abstention
  (log/power-law divergence of I_pred means no finite state suffices). DCA is a strong linear baseline to replace PCA.
  Being linear projections of x, DCA/PFIB are encoders z = V^T x directly usable as phi.
- **Open-source implementations:** DCA - https://github.com/BouchardLab/DynamicalComponentsAnalysis - active-ish (CI,
  ReadTheDocs; ~38 stars, 422 commits) - LBNL/UC Regents BSD-style licence with DOE government-licence clause (read on
  repo page; exact SPDX identifier not verified) [repo/docs]. CPIC: no code link on arXiv page (licence not verified).
- **From-scratch simplicity:** Simple for DCA (block-Toeplitz covariance, log-det objective, L-BFGS with
  orthonormality penalty, 5+ restarts). Pitfalls: regularise Sigma, centre data, keep T fixed across compared d.
- **References:**
  - Predictability, Complexity and Learning. W. Bialek, I. Nemenman, N. Tishby. 2001. Neural Computation 13. https://arxiv.org/abs/physics/0007070 [read-abstract]
  - Past-future information bottleneck in dynamical systems. F. Creutzig, A. Globerson, N. Tishby. 2009. Physical Review E 79, 041925. https://cris.tau.ac.il/en/publications/past-future-information-bottleneck-in-dynamical-systems/ [read-abstract]
  - Unsupervised Discovery of Temporal Structure in Noisy Data with Dynamical Components Analysis. D. G. Clark, J. A. Livezey, K. E. Bouchard. 2019. NeurIPS 2019. https://arxiv.org/abs/1905.09944 (HTML body read) [read-full]
  - Compressed Predictive Information Coding. R. Meng, T. Luo, K. Bouchard. 2022. arXiv. https://arxiv.org/abs/2203.02051 [read-abstract]

### Exact bisimulation, model minimisation, lumpability and partition refinement
- **Core idea:** A partition of a (finite) Markov chain/MDP is a (stochastic) bisimulation / strongly lumpable if all
  states in a block have equal rewards/outputs and equal transition probability into every block, for every action.
  The coarsest such partition is computed by partition refinement: start from the output partition, repeatedly split
  blocks whose members disagree on block-transition probabilities (Paige-Tarjan relational coarsest partition, and its
  probabilistic variants; Givan-Dean-Greig model minimisation for MDPs). Lumpability of Markov chains (Kemeny & Snell) is
  the output-free version; Buchholz distinguishes ordinary vs exact lumpability; spectral characterisation: states in a
  lump share components of dual (left) eigenvectors (Jacobi & Goernerup). Li, Walsh & Littman order abstraction types by
  fineness: model-irrelevance (bisimulation) finer than Q^pi-irrelevance finer than Q*-irrelevance finer than a*- and
  pi*-irrelevance (unverified: from snippet + memory).
- **Assumptions:** Finite state space, known (or estimated) transition matrix; exact equalities.
- **Identifiability:** The coarsest bisimulation is unique; it is a partition (no coordinates).
- **Intervention support:** Actions are part of the definition (block transitions must match per action), so
  "interventions as actions" are natively covered; unseen interventions are not.
- **Nonlinear capacity:** Any finite dynamics; continuous spaces need a discretisation.
- **Interpretability:** High.
- **Scaling (N, T, data size):** Paige-Tarjan O(m log n) for relational coarsest partition (m edges, n states;
  complexity from memory, unverified on the page I read); probabilistic lumping has similar O(m log n) algorithms
  (unverified). Model minimisation is exponential in factored representations in the worst case.
- **Failure modes:** Exact equality is brittle under noise/estimation (everything splits); continuous states are never
  exactly lumpable after discretisation -> need approximate versions.
- **Relevance to problem (props 1-8):** Canonical formal definition of (2)+(4): "equal outputs and equal transition law
  into blocks" is precisely a closed, microstate-invariant abstraction. The refinement algorithm is the discrete
  prototype for our counterexample loop (a split witness = counterexample).
- **Open-source implementations:** None specific checked (licence not verified). Partition refinement is a few dozen
  lines.
- **From-scratch simplicity:** Simple for finite chains (naive O(n^2) refinement is fine up to ~10^4 states).
- **References:**
  - Equivalence notions and model minimization in Markov decision processes. R. Givan, T. Dean, M. Greig. 2003. Artificial Intelligence 147. https://doi.org/10.1016/S0004-3702(02)00376-4 [unverified: landing page 403, PDF not parseable]
  - Towards a Unified Theory of State Abstraction for MDPs. L. Li, T. J. Walsh, M. L. Littman. 2006. ISAIM 2006. http://anytime.cs.umass.edu/aimath06/proceedings/P21.pdf [unverified: could not open]
  - Three Partition Refinement Algorithms. R. Paige, R. E. Tarjan. 1987. SIAM Journal on Computing 16(6). https://scholarsmine.mst.edu/math_stat_facwork/349/ [read-abstract]
  - Exact and ordinary lumpability in finite Markov chains. P. Buchholz. 1994. Journal of Applied Probability 31. [unverified]
  - Finite Markov Chains. J. G. Kemeny, J. L. Snell. 1960/1976. Van Nostrand / Springer. [unverified]
  - A dual eigenvector condition for strong lumpability of Markov chains. M. N. Jacobi, O. Goernerup. 2007. arXiv. https://arxiv.org/abs/0710.1986 [read-abstract]

### Approximate lumpability / approximate bisimulation (quasi-lumpability, aggregation error bounds, epsilon-bisimulation for continuous systems)
- **Core idea:** Relax equality: a partition is epsilon-quasi-lumpable if |P(x, A) - P(y, A)| <= epsilon for all x, y in the
  same block and all blocks A (definition as quoted in search snippet); Michel & Siegle bound the stepwise increment of
  transient-distribution error of an aggregated chain (and error-growth rate in continuous time) and search for low-error
  aggregations. For continuous/hybrid systems, Girard & Pappas define approximate (epsilon-precision) simulation and
  bisimulation relations whose observations stay within epsilon, certified by Lyapunov-like "bisimulation functions";
  used to build finite abstractions and for simulation-based verification.
- **Assumptions:** Known or estimable transition kernels (Markov); for Girard-Pappas, incremental-stability-like
  properties to obtain bisimulation functions (unverified detail).
- **Identifiability:** Not unique: many epsilon-partitions; the coarsest one depends on epsilon.
- **Intervention support:** Via actions/inputs in the transition system.
- **Nonlinear capacity:** General (definitions are model-free); certificates are easier for (incrementally) stable
  systems.
- **Interpretability:** High (error bounds per block).
- **Scaling (N, T, data size):** Error-bound computation is linear algebra on the chain; continuous-system certificates
  (SOS/Lyapunov) scale poorly with dimension.
- **Failure modes:** Errors compound with horizon; epsilon must be chosen; chaotic or marginally stable systems have no
  small-epsilon finite bisimulation.
- **Relevance to problem (props 1-8):** Supplies the quantitative version of (2)/(4): report the aggregation error
  epsilon per horizon as the closure/invariance score; the "no small-epsilon abstraction at small k" outcome is an
  operational abstention criterion (8).
- **Open-source implementations:** None checked.
- **From-scratch simplicity:** Simple for estimated finite chains (compute block-transition spread).
- **References:**
  - Formal Error Bounds for the State Space Reduction of Markov Chains. F. Michel, M. Siegle. 2024. arXiv. https://arxiv.org/abs/2403.07618 [read-abstract]
  - Approximation metrics for discrete and continuous systems. A. Girard, G. J. Pappas. 2007. IEEE Transactions on Automatic Control. [unverified]
  - Approximate bisimulation (overview PDF by G. J. Pappas; exact title/venue not verified). https://www.georgejpappas.org/wp-content/uploads/2024/04/EJC-Pappas.pdf [read-abstract]

### Bisimulation metrics and learned behavioural distances (Ferns metric, DBC, MICo)
- **Core idea:** Replace the bisimulation relation by a pseudometric d, the fixed point of
  d(s,t) = max_a [ c_R |R(s,a) - R(t,a)| + c_T W_1^d(P(.|s,a), P(.|t,a)) ] (Ferns et al.; exact form from memory, unverified),
  whose kernel is bisimilarity and which bounds optimal-value differences. DBC trains an encoder so that the L1 latent
  distance matches |r_i - r_j| + gamma W_2(latent transition Gaussians), with a learned Gaussian latent dynamics model.
  MICo replaces the optimal coupling by the independent coupling:
  U(x,y) = |r_x - r_y| + gamma E_{x'~P_x, y'~P_y} U(x',y'), a "diffuse metric" (U(x,x) can be > 0), learned from sampled
  transition pairs with U_w(x,y) = (||phi(x)||^2 + ||phi(y)||^2)/2 + beta*angle(phi(x), phi(y)); on-policy guarantee
  |V^pi(x) - V^pi(y)| <= U^pi(x,y).
- **Assumptions:** Markov ground state; a scalar "reward" that defines what must be preserved; DBC: Gaussian latent
  transitions; MICo: fixed policy.
- **Identifiability:** The metric (and its zero set = bisimulation classes) is unique for given reward and policy; the
  encoder is identified only up to isometries of the latent metric (and MICo's parameterisation constrains to
  norms + angles).
- **Intervention support:** Actions/policies; nothing specific for unseen interventions.
- **Nonlinear capacity:** High (deep encoders).
- **Interpretability:** Low-moderate; distances are interpretable as behavioural differences.
- **Scaling (N, T, data size):** Exact metric computation is polynomial but expensive (Wasserstein LPs; MICo cites
  O~(|X|^5|A|) vs O(|X|^4)); learned versions scale like standard deep RL with pairwise losses on minibatches.
- **Failure modes:** Collapse when rewards are sparse/constant (reward-free bisimulation collapses all states); W_2
  under Gaussian assumption is loose; distances dominated by reward scale; MICo's self-distance must be handled (use the
  reduced distance).
- **Relevance to problem (props 1-8):** Directly usable if we replace "reward" by the readout y (and optionally
  multi-horizon y features): the fixed-point metric then measures predictive (future-y) distinguishability of
  microstates, giving a graded version of (4). Invariance to distractors ~ microstate invariance. Metric-matching also
  gives a continuous counterexample score (pairs with small latent distance but large behavioural distance). Caveat: a
  scalar reward is a much weaker test set than full future-output distributions; use vector-valued y.
- **Open-source implementations:**
  - DBC - https://github.com/facebookresearch/deep_bisim4control - archived Oct 2023, ~157 stars - CC-BY-NC 4.0 (non-commercial) [repo/docs]
  - MICo - https://github.com/google-research/google-research/tree/master/mico - research code (Atari, DM control) - Apache-2.0 (google-research repo licence) [repo/docs]
- **From-scratch simplicity:** Moderate: MICo loss is ~20 lines on top of any encoder; DBC needs a probabilistic latent
  model. Pitfalls: target networks/stop-gradients for the bootstrapped metric, reward scaling, pair sampling.
- **References:**
  - Metrics for Finite Markov Decision Processes. N. Ferns, P. Panangaden, D. Precup. 2004. UAI 2004. https://arxiv.org/abs/1207.4114 [read-abstract]
  - Learning Invariant Representations for Reinforcement Learning without Reconstruction (DBC). A. Zhang, R. McAllister, R. Calandra et al. 2021. ICLR 2021. https://arxiv.org/abs/2006.10742 [read-abstract]
  - MICo: Improved representations via sampling-based state similarity for Markov decision processes. P. S. Castro, T. Kastner, P. Panangaden, M. Rowland. 2021. NeurIPS 2021. https://arxiv.org/abs/2106.08229 (HTML body read) [read-full]

### Latent model / self-predictive abstractions (DeepMDP, self-predictive ZP, Markov state abstractions, Denoised MDP)
- **Core idea:** Learn an encoder phi and latent model so the abstraction is (approximately) model-irrelevant. DeepMDP:
  minimise reward-prediction loss plus Wasserstein distance between predicted and actual next-latent distributions,
  with Lipschitz assumptions giving value-bound guarantees and a link to bisimulation. Ni et al. unify >20 methods: an
  encoder is self-predictive (ZP) if the next latent is predictable from current latent + action; observation-predictive
  (phi_O) => self-predictive (phi_L) => Q*-irrelevance, not conversely; stop-gradient targets provably prevent collapse in
  the linear case (preserve phi^T phi). Allen et al.: an abstraction is Markov if abstract-state beliefs depend only on
  the latest abstract state; sufficient conditions = (i) abstract inverse model equals ground inverse model and (ii)
  abstract next-state density ratio equals ground density ratio; implemented with an inverse-dynamics loss and a
  contrastive (consecutive vs shuffled) ratio loss, plus smoothness. Denoised MDP factorises information by
  controllability x reward-relevance and keeps only the controllable and reward-relevant part.
- **Assumptions:** Markov ground process; a policy class covering the actions; reward or other target defining
  relevance; for guarantees, Lipschitz/realizability assumptions.
- **Identifiability:** Latent coordinates only up to invertible (often nonlinear) transforms; ZP alone admits trivial
  solutions (constant encoder) unless anchored (stop-gradient dynamics, reward/observation losses, contrastive terms).
- **Intervention support:** Actions only. Allen's inverse-model condition is interesting for interventions: it forces
  z to retain whatever distinguishes the effects of different actions (controllable information).
- **Nonlinear capacity:** High.
- **Interpretability:** Low.
- **Scaling (N, T, data size):** Standard deep-learning scaling; minibatch losses.
- **Failure modes:** Representation collapse; reward-only anchoring discards task-irrelevant but predictive state
  (fails (1) for y if y != reward); Markov conditions only approximately enforced; contrastive negatives choice matters.
- **Relevance to problem (props 1-8):** (2) Markov closure is the ZP condition; the phi_O => phi_L => ... hierarchy
  tells us that insisting on predicting the full readout future (phi_O restricted to y) implies closure, whereas pure
  latent self-prediction does not imply predictive sufficiency for y. Allen's density-ratio condition gives a
  contrastive Markov test usable as an evaluation. Denoised MDP's controllable/uncontrollable split maps onto
  "input-driven vs autonomous" parts of z.
- **Open-source implementations:**
  - self-predictive-rl (Ni et al.) - https://github.com/twni2016/self-predictive-rl - ~28 stars, small - licence not stated on repo page (licence not verified) [repo/docs]
  - markov-state-abstractions (Allen et al.) - https://github.com/camall3n/markov-state-abstractions - ~20 stars - MIT [repo/docs]
  - denoised_mdp - https://github.com/facebookresearch/denoised_mdp - licence not verified (paper text is CC BY-NC-SA 4.0)
  - DeepMDP: no official code checked.
- **From-scratch simplicity:** Simple-moderate: ZP loss with stop-gradient target (EMA or detached encoder) is a few
  lines; inverse and ratio losses are standard classifiers.
- **References:**
  - DeepMDP: Learning Continuous Latent Space Models for Representation Learning. C. Gelada, S. Kumar, J. Buckman et al. 2019. ICML 2019. https://arxiv.org/abs/1906.02736 [read-abstract]
  - Bridging State and History Representations: Understanding Self-Predictive RL. T. Ni, B. Eysenbach, E. Seyedsalehi et al. 2024. ICLR 2024. https://arxiv.org/abs/2401.08898 (HTML body read; author list beyond first author from memory, unverified) [read-full]
  - Learning Markov State Abstractions for Deep Reinforcement Learning. C. Allen, N. Parikh, O. Gottesman, G. Konidaris. 2021. NeurIPS 2021 (venue unverified). https://arxiv.org/abs/2106.04379 (HTML body read) [read-full]
  - Denoised MDPs: Learning World Models Better Than the World Itself. T. Wang, S. S. Du, A. Torralba et al. 2022. ICML 2022. https://arxiv.org/abs/2206.15477 [read-abstract]

### Counterexample-guided abstraction refinement (CEGAR) and simulation-based falsification
- **Core idea:** Build a coarse (existential) abstraction; check a property on it; if the abstract model produces a
  counterexample, replay it on the concrete system; if it is not realisable (spurious), identify the abstract state where
  concrete behaviour fails (dead-end vs bad concrete states merged in one abstract state) and split that abstract state;
  iterate. Finding the coarsest refinement is NP-hard, so heuristics are used. Abstractions are conservative for
  universal (ACTL) properties. For hybrid/continuous systems, counterexample validation requires reachable-set
  computation and refinement splits polyhedral regions (Clarke, Fehnker, Han, Krogh et al. 2003). Simulation-based
  falsification (S-TaLiRo/PSY-TaLiRo, Breach) searches inputs/initial states to minimise a temporal-logic robustness
  score; Corso et al. survey black-box validation via optimisation, path planning, RL and importance sampling.
- **Assumptions:** Discrete CEGAR: finite (or finitely abstracted) transition systems and a property to check. Hybrid:
  computable reachability. Falsification: a simulator and a quantitative (robustness) objective.
- **Identifiability:** Not a learning method; the result is an abstraction adequate for the property, not unique.
- **Intervention support:** Inputs/initial conditions are search variables; interventions can be modelled as extra
  inputs; the whole method assumes the ability to run arbitrary concrete simulations, which our simulator provides.
- **Nonlinear capacity:** Arbitrary (black-box simulation), but no completeness guarantees for continuous systems.
- **Interpretability:** High (explicit counterexample traces explain every split).
- **Scaling (N, T, data size):** Driven by the number of refinement iterations and cost of counterexample search;
  falsification cost = number of simulations x simulation cost.
- **Failure modes:** Non-termination for infinite-state systems; over-refinement (state explosion) from local splitting;
  falsification is incomplete (absence of counterexample is not proof); robustness landscapes are non-convex.
- **Relevance to problem (props 1-8):** Provides the control loop for our setting: "abstract prediction disagrees with
  concrete simulation" = counterexample; "split the abstract state where the disagreement starts" = refinement.
  Replace the logical property by "multi-horizon predictive/interventional equivalence within epsilon". Falsification
  optimisers are the natural equivalence-oracle implementation for a continuous simulator. Failure to converge at small k
  is an abstention signal.
- **Open-source implementations:**
  - PSY-TaLiRo (Python falsification) - https://gitlab.com/sbtg/psy-taliro - active (710 commits, 3 releases) - BSD-3-Clause [repo/docs]
  - S-TaLiRo / Breach (MATLAB) - licence per search snippet GPL for S-TaLiRo (licence not verified).
- **From-scratch simplicity:** The loop is simple; counterexample search (e.g. CMA-ES / random restarts over inputs and
  microstate pairs) is simple; the difficulty is statistical validation in stochastic settings.
- **References:**
  - Counterexample-Guided Abstraction Refinement. E. Clarke, O. Grumberg, S. Jha et al. 2000. CAV 2000, LNCS 1855, pp. 154-169. https://web.stanford.edu/class/cs357/cegar.pdf [read-abstract: PDF fetched but only a summary-level extraction was obtained]
  - Abstraction and Counterexample-Guided Refinement in Model Checking of Hybrid Systems. E. Clarke, A. Fehnker, Z. Han et al. 2003. Int. J. Foundations of Computer Science 14(4). https://www.worldscientific.com/doi/abs/10.1142/S012905410300190X [unverified: page 403, PDF not parseable]
  - A Survey of Algorithms for Black-Box Safety Validation of Cyber-Physical Systems. A. Corso, R. J. Moss, M. Koren et al. 2021. JAIR 72. https://arxiv.org/abs/2005.02979 [read-abstract]
  - PSY-TaLiRo repository. https://gitlab.com/sbtg/psy-taliro [repo/docs]

### Active automata learning by queries and counterexamples (L*, KV, TTT, L#; LearnLib, AALpy; RNN extraction)
- **Core idea:** L* maintains an observation table with prefixes S (candidate states) and suffixes E (distinguishing
  experiments); rows are equivalence classes by Myhill-Nerode (equal outputs on all suffixes). The learner asks
  membership/output queries to make the table closed (every one-step extension of a state looks like an existing state)
  and consistent, conjectures a minimal automaton, and asks an equivalence query; a counterexample adds a new
  distinguishing suffix, which splits a state. Learns the minimal DFA in time polynomial in its number of states and the
  longest counterexample. Variants: Mealy/Moore machines (input->output), stochastic (L*_MDP, stochastic Mealy),
  passive (RPNI, Alergia). In practice the equivalence oracle is approximated by random/conformance testing (e.g.
  W-method). Weiss et al. use a trained RNN as the teacher: L* queries the RNN, and equivalence is checked by comparing
  the conjectured DFA against an adaptively refined partition of the RNN's continuous hidden state space; disagreements
  are counterexamples that refine either the DFA or the hidden-state partition.
- **Assumptions:** Finite (or finitely abstracted) input/output alphabets; ability to reset and query (exactly our
  simulator's capability); target has a finite minimal machine; deterministic (or stochastic variants with sampling).
- **Identifiability:** The minimal machine is unique up to state renaming (Myhill-Nerode).
- **Intervention support:** Any intervention expressible as an input symbol is a query; the "suffix set" E is literally
  a set of distinguishing experiments, which can include perturbation protocols.
- **Nonlinear capacity:** Any finite-state behaviour; continuous systems need input/output quantisation (a "mapper").
- **Interpretability:** High (explicit automaton + the experiments that distinguish each pair of states).
- **Scaling (N, T, data size):** Query count polynomial in states x alphabet x counterexample length; equivalence
  testing dominates in practice; LearnLib/TTT reduce redundant queries.
- **Failure modes:** Quantisation choice determines everything; stochastic outputs require many samples per query;
  approximate equivalence oracles miss rare distinctions; state explosion for systems with continuous memory.
- **Relevance to problem (props 1-8):** The best worked-out theory of **active state discovery with resets**: states =
  equivalence under a growing test bank; each counterexample adds exactly one discriminating experiment; the final table
  proves microstate-invariance (4) and closure (2) with respect to the test bank, and minimality (5) is guaranteed. The
  Weiss et al. construction (partition a continuous state space, refine by counterexamples) is a direct template for
  continuous microstates x.
- **Open-source implementations:**
  - AALpy (Python) - https://github.com/DES-Lab/AALpy - active, ~248 stars, pip install aalpy; DFA/Mealy/Moore/ONFSM/MDP/SMM; L*, KV, L#, L*_MDP, Alergia - MIT [repo/docs]
  - LearnLib (Java 17) - https://github.com/learnlib/learnlib - active, ~236 stars; L*, TTT, KV, NL*, Observation Pack - Apache-2.0 [repo/docs]
- **From-scratch simplicity:** Simple for deterministic L* (~200 lines); moderate for stochastic variants.
- **References:**
  - Learning regular sets from queries and counterexamples. D. Angluin. 1987. Information and Computation 75, 87-106. https://people.eecs.berkeley.edu/~dawnsong/teaching/s10/papers/angluin87.pdf [unverified: PDF not parseable; abstract content seen only in search snippet]
  - Extracting Automata from Recurrent Neural Networks Using Queries and Counterexamples. G. Weiss, Y. Goldberg, E. Yahav. 2018. ICML 2018. https://arxiv.org/abs/1711.09576 [read-abstract]
  - AALpy repository. https://github.com/DES-Lab/AALpy [repo/docs]
  - LearnLib repository. https://github.com/learnlib/learnlib [repo/docs]

---

## D. Neural state-space and continuous-time latent models

_Source notes: `notes\area_D_neural_ssm_odes.md`._

Scope: variational SSMs (DKF/DMM, VRNN, SRNN, KVAE, DVBF), latent world models with actions (RSSM / PlaNet / Dreamer, E2C / RCE),
neural differential equations (neural ODE / ANODE, latent ODE / ODE-RNN, neural CDE, neural / latent SDE), deep linear
sequence layers (S4 / S5 / LRU / Mamba) as black-box predictors with a bottleneck, latent-prediction objectives (JEPA / SPR,
CPC, C-SWM), switching models (rSLDS), physics-inspired nets (HNN / LNN), and dynamical-systems reconstruction with PLRNNs
trained by sparse / generalized teacher forcing.

Reading status: the arXiv abstract page was opened for every paper cited. Where noted, I also read full text through
ar5iv/arXiv HTML (PlaNet, E2C, KVAE, rSLDS, Mikhaeil et al., latent SDE, neural CDE, C-SWM, GTF, DreamerV3). A PDF extraction
of DreamerV2 gave only partial text. Architectural details I state from memory without having read them are marked (unverified).

Shared observation for the whole area: **none of these methods identifies latent coordinates beyond predictive (observational)
equivalence.** Any invertible reparameterisation of z that is absorbed by the encoder, transition and decoder gives the same
likelihood. Stochastic latents with a Gaussian prior are at best identified up to isometries or rotations of the prior, and
in practice not even that. For this contract that is acceptable, because the contract already says coordinates are identifiable only up
to transformations. What is NOT guaranteed is anything stronger: that k is minimal, that the state is closed (Markov), or that interventions work.
These have to be tested (see synthesis).

---

### Deep Kalman filter / Deep Markov model with structured inference network (DKF / DMM)
- **Core idea:** Nonlinear Gaussian SSM z_t ~ N(mu_theta(z_{t-1}, u_{t-1}), Sigma_theta(.)), x_t ~ p_theta(x_t | z_t), where both
  the transition and the emission are neural networks. It is trained by amortised variational inference (ELBO). The 2017 paper
  adds a structured posterior q(z_t | z_{t-1}, x_{t:T}) computed by a backward RNN plus a "combiner", which mirrors the true
  posterior factorisation of an SSM.
- **Assumptions:** Markov latent process of fixed dimension; Gaussian transition noise; observations conditionally independent given z_t.
  Actions enter additively as conditioning of the transition (the 2015 paper uses actions and counterfactual queries on a
  synthetic sequence task).
- **Identifiability:** None beyond predictive equivalence. The latent is identified at most up to diffeomorphisms absorbed by the
  networks, and the Gaussian prior on z_1 only weakly pins down the scale.
- **Intervention support:** Inputs u_t enter the transition and, optionally, the emission. "Counterfactual" in the DKF paper means
  changing u in the generative model. There is no mechanism for state-offset interventions except re-encoding the perturbed
  observation. Predicting held-out intervention types is not addressed.
- **Nonlinear capacity:** High. The gated transition (Pyro DMM) mixes a linear path with an MLP proposal.
- **Interpretability:** Low. Latents are only meaningful up to reparameterisation.
- **Scaling:** Linear in T per sequence. The emission for N ~ 5000 is a single MLP head and is cheap. Training is sequential over T
  because of the RNN posterior.
- **Failure modes:** Posterior collapse or unused latents. The Pyro tutorial uses linear KL annealing because strong KL early
  in training creates bad local optima. The backward RNN posterior uses future observations (smoothing). This is correct for
  learning, but it is future leakage if that posterior is used as the "encoder" at test time. Over-dimensioned latents get
  switched off rather than penalised, so k is not identified.
- **Relevance (props 1-8):** (1) yes, via generative rollouts; (2) Markov by construction in the model, but the smoothing
  posterior can hide non-closure; (3) only for u-type inputs; (5) no pressure toward minimal k beyond KL; (6) seed-unstable
  coordinates; (8) no abstention. It is a sound "variational SSM" baseline.
- **Open-source implementations:** Pyro DMM tutorial (pyro.ai/examples/dmm.html) - mature, part of Pyro - licence not verified
  (Pyro is commonly Apache-2.0, unverified). NumPyro DKF example: not checked.
- **From-scratch simplicity:** Moderate. It is an ELBO with reparameterised Gaussians. The pitfalls are KL annealing, the
  log-variance clamp, and the need to evaluate using a filter-only encoder.
- **References:**
  - Deep Kalman Filters. R. G. Krishnan, U. Shalit, D. Sontag. 2015. arXiv:1511.05121. https://arxiv.org/abs/1511.05121 [read-abstract]
  - Structured Inference Networks for Nonlinear State Space Models. R. G. Krishnan, U. Shalit, D. Sontag. 2017. AAAI. https://arxiv.org/abs/1609.09869 [read-abstract]
  - Pyro Deep Markov Model tutorial. https://pyro.ai/examples/dmm.html [repo/docs]

### Stochastic recurrent networks: VRNN and SRNN
- **Core idea:** VRNN places a VAE at every step of an RNN. The prior p(z_t | h_{t-1}) and the decoder are conditioned on the
  deterministic RNN state, and h_t = RNN(h_{t-1}, x_t, z_t). SRNN separates a deterministic RNN layer from a stochastic SSM layer
  stacked on top of it. Its posterior respects the SSM factorisation through a backward pass.
- **Assumptions:** Autoregressive in observations (x_{t-1} is fed into h_t). The "state" is (h_t, z_t), not z_t alone.
- **Identifiability:** None beyond predictive equivalence.
- **Intervention support:** Inputs can be concatenated into the RNN input. There is no native intervention semantics.
- **Nonlinear capacity:** High.
- **Interpretability:** Low. Most information usually flows through the deterministic h.
- **Scaling:** O(T) sequential, and fine for N in the thousands.
- **Failure modes:** Because x_{t-1} feeds the recurrence, the model can act as a strong autoregressive predictor while z carries
  almost nothing (posterior collapse in the stochastic path). This amounts to **output copying**: one-step likelihood is excellent but
  there is no compact closed state. The effective state dimension is dim(h) + dim(z), which is large. Exposure bias appears when
  the model is rolled out on its own samples.
- **Relevance:** Mainly a cautionary baseline. For this contract the latent must be computed from x(t) only, and rollouts
  must not feed back ground-truth observations. VRNN-style autoregressive feedback violates (2) and (5) unless it is removed.
- **Open-source implementations:** Many unofficial ones. The original authors' code was not checked (licence not verified).
- **From-scratch simplicity:** Moderate.
- **References:**
  - A Recurrent Latent Variable Model for Sequential Data. J. Chung, K. Kastner, L. Dinh et al. 2015. NeurIPS 2015. https://arxiv.org/abs/1506.02216 [read-abstract]
  - Sequential Neural Models with Stochastic Layers. M. Fraccaro, S. K. Sønderby, U. Paquet, O. Winther. 2016. NeurIPS 2016. https://arxiv.org/abs/1605.07571 [read-abstract]

### Kalman variational auto-encoder (KVAE)
- **Core idea:** A per-frame VAE maps x_t to a low-dimensional pseudo-observation a_t. A linear-Gaussian SSM on z_t (with
  control B_t u_t) explains a_t, so q(z | a) is computed exactly by Kalman filtering and smoothing. Nonlinearity comes from a
  "dynamics parameter network" (an LSTM over past a) that outputs weights mixing K learned (A, B, C) matrices, giving locally
  linear dynamics.
- **Assumptions:** Dynamics are a convex mixture of K linear regimes. Gaussian noise. There is a two-level latent (a = content,
  z = dynamics).
- **Identifiability:** Up to invertible linear maps of z within each regime (as in a standard LGSSM), composed with the arbitrary
  nonlinear encoder for a. The mixture weights are not identified.
- **Intervention support:** Control input u_t enters linearly via B_t. Exact smoothing allows imputation.
- **Nonlinear capacity:** Moderate (switching or locally linear). The mixing LSTM reads history, so the effective state includes
  the LSTM state. This is a closure caveat.
- **Interpretability:** Moderate. There are explicit linear regimes and inspectable A_k matrices.
- **Scaling:** Kalman ops are O(T k^3) and cheap for small k. The encoder handles large N.
- **Failure modes:** The mixture collapses to a single regime. The paper uses a staged training schedule and down-weights
  reconstruction so that the dynamics can be learned (read in full text). The LSTM-driven weights make the model non-Markov in z alone.
- **Relevance:** Good structural prior for (5) and interpretability. Replacing the mixture-weight LSTM with alpha(z_{t-1}) makes
  it an rSLDS-like, Markov model. This is recommended if used here.
- **Open-source implementations:** simonkamronn/kvae - https://github.com/simonkamronn/kvae - stale (TensorFlow 1.x), ~143 stars - MIT.
- **From-scratch simplicity:** Moderate. It needs a differentiable Kalman smoother. dynamax provides one in JAX.
- **References:**
  - A Disentangled Recognition and Nonlinear Dynamics Model for Unsupervised Learning. M. Fraccaro, S. Kamronn, U. Paquet, O. Winther. 2017. NeurIPS 2017. https://arxiv.org/abs/1710.05741 ; full text via https://ar5iv.labs.arxiv.org/html/1710.05741 [read-full]
  - kvae repository. https://github.com/simonkamronn/kvae [repo/docs]

### Deep variational Bayes filter (DVBF)
- **Core idea:** A variational SSM where the transition is reparameterised as z_{t+1} = f(z_t, u_t, w_t), with the stochasticity
  in a "process noise" w_t that is inferred. Gradients must flow *through the transition*, so the latent is forced to obey the
  state-space assumption rather than the encoder explaining each frame on its own. It uses locally linear transitions (a
  mixture of matrices chosen by a network of z_t).
- **Assumptions:** Markov latent; control input enters the transition.
- **Identifiability:** None beyond predictive equivalence. The authors claim the latent captures full state information
  empirically, not as an identifiability theorem.
- **Intervention support:** Controls enter the transition. There are no do-interventions.
- **Nonlinear capacity:** Moderate to high.
- **Interpretability:** Moderate (locally linear).
- **Scaling:** O(T), sequential.
- **Failure modes:** Encoder-dominated latents if the transition is bypassed. This is the point DVBF addresses, and it is highly
  relevant for closure. KL annealing is needed (unverified detail).
- **Relevance:** Its main lesson carries over directly: **force information through the transition** (latent is x-independent
  after t0 except via inferred noise). This is what property (2) demands. It is a stepping stone to "encode once, roll out" training.
- **Open-source implementations:** None official found. Licence not verified.
- **From-scratch simplicity:** Moderate.
- **References:**
  - Deep Variational Bayes Filters: Unsupervised Learning of State Space Models from Raw Data. M. Karl, M. Soelch, J. Bayer, P. van der Smagt. 2017. ICLR 2017. https://arxiv.org/abs/1605.06432 [read-abstract]

### Recurrent state-space model as latent world model (RSSM: PlaNet, Dreamer V1-V3)
- **Core idea:** The state is split into a deterministic path h_t = GRU(h_{t-1}, s_{t-1}, a_{t-1}) and a stochastic path
  s_t ~ p(s_t | h_t) (prior), with posterior q(s_t | h_t, o_t). It is trained with reconstruction plus a KL(posterior || prior)
  ELBO. Planning or behaviour learning happens in imagined latent rollouts that use only the prior.
- **Key details (read):** PlaNet uses a GRU with 200 units, a 30-dimensional diagonal Gaussian stochastic state, 3 free nats and a
  planning horizon of 12. The paper argues that purely deterministic transitions let the planner exploit model errors and cannot
  represent multiple futures, while purely stochastic ones struggle to remember information across steps. **Latent overshooting**
  (a multi-step KL between the d-step prior and the posterior, weighted by beta_d) helped other models but "slightly reduces
  performance" of the RSSM. DreamerV2 uses 32x32 categorical latents with straight-through gradients and KL balancing with
  alpha = 0.8 (from partial PDF text). DreamerV3 uses h_t = f(h_{t-1}, z_{t-1}, a_{t-1}), a dynamics loss (beta = 1) and a
  representation loss (beta = 0.1) with stop-gradients, free bits clipped below 1 nat, 1% uniform mixture in the categoricals,
  symlog transforms, and imagination horizon 16. One fixed configuration is used across more than 150 tasks.
- **Assumptions:** POMDP with actions. The latent (h, s) is intended to be a sufficient belief state.
- **Identifiability:** None beyond predictive equivalence.
- **Intervention support:** Actions enter the deterministic recurrence at every step. That is the natural slot for u(t) and
  for parametrised intervention descriptors. Multi-step open-loop prediction is native. Predicting unseen intervention types is
  not addressed.
- **Nonlinear capacity:** High.
- **Interpretability:** Low. h is a 200-4096-dimensional history summary.
- **Scaling:** O(T) sequential GRU. It scales to very large data. DreamerV3 models range up to hundreds of millions of
  parameters (unverified exact numbers).
- **Failure modes:** (a) **The deterministic h is the real state and is large.** Its minimal dimension is hidden, so counting
  only dim(s) as k is dimension cheating. (b) Posterior collapse or over-regularised prior, mitigated by free bits and KL
  balancing. (c) Compounding error in open-loop rollouts. PlaNet reports that overshooting did not help the RSSM itself.
  (d) Reconstruction-dominated latents that spend capacity on unpredictable detail.
- **Relevance:** Strong for (1) and for the input pathway. For (2), (5) and (8) it must be modified: drop or shrink h, encode
  from x(t) only, and evaluate open-loop rollouts from the encoded state. The KL-balancing and free-bits recipes transfer directly.
- **Open-source implementations:** danijar/dreamerv3 - https://github.com/danijar/dreamerv3 - active, ~3.8k stars, JAX - MIT.
- **From-scratch simplicity:** Moderate. The small RSSM is about 200 lines. The pitfalls are the stop-gradient placement in KL
  balancing, free bits applied to the batch-mean KL vs per-dimension KL, and prior/posterior sharing of h.
- **References:**
  - Learning Latent Dynamics for Planning from Pixels. D. Hafner, T. Lillicrap, I. Fischer et al. 2019. ICML 2019. https://arxiv.org/abs/1811.04551 ; https://ar5iv.labs.arxiv.org/html/1811.04551 [read-full]
  - Dream to Control: Learning Behaviors by Latent Imagination. D. Hafner, T. Lillicrap, J. Ba, M. Norouzi. 2020. ICLR 2020. https://arxiv.org/abs/1912.01603 [read-abstract]
  - Mastering Atari with Discrete World Models. D. Hafner, T. Lillicrap, M. Norouzi, J. Ba. 2021. ICLR 2021. https://arxiv.org/abs/2010.02193 [read-abstract; partial PDF text]
  - Mastering Diverse Domains through World Models. D. Hafner, J. Pasukonis, J. Ba, T. Lillicrap. 2023 (rev. 2024). arXiv:2301.04104. https://arxiv.org/html/2301.04104 [read-full]
  - dreamerv3 repository. https://github.com/danijar/dreamerv3 [repo/docs]

### Embed to Control and robust locally-linear controllable embedding (E2C / RCE)
- **Core idea:** E2C uses a VAE encoder into a low-dimensional z and a locally linear transition
  z_{t+1} ~ N(A_t mu_t + B_t u_t + o_t, C_t). A network of z_t outputs A_t = I + v_t r_t^T (rank-1), B_t and o_t. The loss is
  reconstruction + KL + lambda * KL(predicted next || encoded next), a temporal consistency term that is effectively
  latent-space next-state prediction. The latent dimension is small (2-8). Latent iLQR is used for control. RCE fixes two issues:
  the E2C objective is not a sequence likelihood, and the encoder has large approximation error under noise. It directly models
  p(x_{t+1} | x_t, u_t) through a bottleneck, with added structure so that linearisation is robust.
- **Assumptions:** Single-step Markov with full observability of the state from one observation. Control enters affinely at
  each linearisation point.
- **Identifiability:** None beyond predictive equivalence. Local linearity fixes nothing globally.
- **Intervention support:** u_t enters linearly (B_t u_t), which suits LQR-type control. Input currents map naturally to u.
- **Nonlinear capacity:** Moderate. It is globally nonlinear through state-dependent (A, B, o).
- **Interpretability:** Moderate. Local Jacobians A_t and B_t are available, which gives local controllability and observability
  analysis in the latent.
- **Scaling:** Cheap per step. Trained on (x_t, u_t, x_{t+1}) triples, so it is fully parallel.
- **Failure modes:** One-step training only, so rollouts drift. The temporal-consistency KL can be satisfied by shrinking the
  latent (collapse) if reconstruction is weak. Noisy dynamics break E2C (motivating RCE).
- **Relevance:** The closest classical ancestor of the "AE + (locally) linear latent dynamics with input" baseline. Its latent
  Jacobians are useful for (5) and for controllability checks.
- **Open-source implementations:** No official code found. Several third-party PyTorch ports exist (not checked, licence not verified).
- **From-scratch simplicity:** Simple. Use a multi-step loss rather than E2C's single step.
- **References:**
  - Embed to Control: A Locally Linear Latent Dynamics Model for Control from Raw Images. M. Watter, J. T. Springenberg, J. Boedecker, M. Riedmiller. 2015. NeurIPS 2015. https://arxiv.org/abs/1506.07365 ; https://ar5iv.labs.arxiv.org/html/1506.07365 [read-full]
  - Robust Locally-Linear Controllable Embedding. E. Banijamali, R. Shu, M. Ghavamzadeh et al. 2018. AISTATS 2018 (PMLR v84). https://arxiv.org/abs/1710.05373 [read-abstract, via search result summary]

### Neural ODEs and augmented neural ODEs (NODE / ANODE)
- **Core idea:** dz/dt = f_theta(z, t), solved by a numerical ODE solver. Gradients come either from backpropagating through the
  solver or from the adjoint ODE, which uses O(1) memory. ANODE shows that NODE flows are homeomorphisms, so they preserve
  input-space topology and cannot represent some maps. Augmenting the state with extra zero-initialised dimensions fixes this and
  improves training stability and cost.
- **Assumptions:** Autonomous or time-dependent smooth vector field. Deterministic. The state must be fully given at t0.
- **Identifiability:** A vector field learned in observed coordinates is identifiable where data covers state space. In a latent
  space, it is identified only up to diffeomorphism (conjugacy).
- **Intervention support:** Inputs require dz/dt = f(z, u(t)) with an interpolated u (zero-order hold or spline), or the CDE
  form (below). State offsets are handled natively by re-initialising z.
- **Nonlinear capacity:** High, but any 1-D ODE and autonomous flows cannot cross trajectories. The ANODE point implies that
  **a latent of too small k cannot represent non-Markov observed dynamics**. This is a useful property for detecting insufficient k.
- **Interpretability:** Moderate. Fixed points, Jacobians and phase portraits can be analysed.
- **Scaling:** Cost is solver steps x network evaluations. Adaptive solvers blow up on stiff or poorly trained fields.
- **Failure modes:** Stiffness (NFE explodes). Adjoint instability: the backward-reconstructed trajectory diverges for
  dissipative or chaotic systems, giving wrong gradients (unverified in the sources read, but widely reported). Exploding
  gradients on chaotic systems (see Mikhaeil et al. below). Using absolute t as input causes time leakage.
- **Relevance:** Strong for (2) (a continuous-time Markov state by construction) and (4). Use it as the transition f inside an
  encoder-decoder.
- **Open-source implementations:** torchdiffeq - https://github.com/rtqichen/torchdiffeq - active, ~6.5k stars - MIT.
  diffrax (JAX) - https://github.com/patrick-kidger/diffrax - active, ~2.1k stars - Apache-2.0 (ODE/SDE/CDE, several adjoints).
- **From-scratch simplicity:** Simple with a fixed-step RK4 and direct backprop (discretise-then-optimise). This is recommended
  over the adjoint for short windows.
- **References:**
  - Neural Ordinary Differential Equations. R. T. Q. Chen, Y. Rubanova, J. Bettencourt, D. Duvenaud. 2018. NeurIPS 2018. https://arxiv.org/abs/1806.07366 [read-abstract]
  - Augmented Neural ODEs. E. Dupont, A. Doucet, Y. W. Teh. 2019. NeurIPS 2019. https://arxiv.org/abs/1904.01681 [read-abstract]
  - On Neural Differential Equations (thesis). P. Kidger. 2022. Univ. Oxford / arXiv:2202.02435. https://arxiv.org/abs/2202.02435 [read-abstract]
  - torchdiffeq; diffrax repositories [repo/docs]

### Latent ODE and ODE-RNN
- **Core idea:** ODE-RNN evolves its hidden state by an ODE between observations and applies an RNN update at each observation.
  The latent ODE is a VAE: an ODE-RNN encoder (run backwards) gives q(z0 | x_{1:T}), and a neural ODE from z0 generates the whole
  trajectory. The model handles irregular sampling and can model observation times with a Poisson process.
- **Assumptions:** The entire future is determined by z0, i.e. an autonomous deterministic latent flow (for the latent ODE).
  Gaussian or other likelihood.
- **Identifiability:** None beyond conjugacy / predictive equivalence.
- **Intervention support:** The original model has no inputs. They must be added to the vector field. Because the whole
  trajectory depends only on z0, the latent ODE is structurally a **closure test**: if encoding x(t0) into z0 and flowing gives
  good multi-horizon predictions, then z0 is a closed state.
- **Nonlinear capacity:** High.
- **Interpretability:** Moderate.
- **Scaling:** Sequential ODE-RNN encoder. Solver cost as for NODE.
- **Failure modes:** The encoder reads the entire window (x_{1:T}), which is **future leakage** if it is used as the state encoder
  in evaluation. For this contract, replace it with phi(x(t0)). Posterior collapse of z0 variance is possible. Stiffness.
- **Relevance:** A very direct fit for (1) and (2) once the encoder is restricted to x(t0). It is the recommended "latent neural
  ODE" baseline.
- **Open-source implementations:** YuliaRubanova/latent_ode - https://github.com/YuliaRubanova/latent_ode - stale, ~600 stars - MIT
  (depends on torchdiffeq).
- **From-scratch simplicity:** Simple to moderate.
- **References:**
  - Latent ODEs for Irregularly-Sampled Time Series. Y. Rubanova, R. T. Q. Chen, D. Duvenaud. 2019. NeurIPS 2019. https://arxiv.org/abs/1907.03907 [read-abstract]
  - latent_ode repository [repo/docs]

### Neural controlled differential equations (neural CDE)
- **Core idea:** dz_t = f_theta(z_t) dX_t, where X is a continuous interpolation of the (input / observation) path with time as an
  explicit channel. It is the continuous-time analogue of an RNN. The initial state is z_{t0} = zeta(x_0, t_0). Universal
  approximation results are given, as well as memory-efficient adjoints across observations.
- **Assumptions:** The input path is interpolated. Natural cubic splines are **non-causal** (X_t depends on future samples); the
  paper flags online use as a limitation. torchcde offers Hermite cubic with backward differences, linear and rectilinear
  interpolation, and rectilinear is intended for causal/online use.
- **Identifiability:** None.
- **Intervention support:** It is the cleanest mathematical formalism for "input u(t) drives the state": set X = (t, u(t)) and let
  z0 come from phi(x(t0)). Then f(z) dX is linear in the input increments. Time must be a channel because CDEs are otherwise
  invariant to reparameterisations of time. Beware that including absolute time can cause time leakage.
- **Nonlinear capacity:** High in z. The dependence on dU is linear, which is a limitation for strongly nonlinear input effects
  unless the input is lifted (e.g. log-signature features).
- **Interpretability:** Low to moderate.
- **Scaling:** f_theta outputs a (k x d_X) matrix, so its cost is O(k d_X) per evaluation. That is fine for small k.
- **Failure modes:** Non-causal interpolation causes future leakage of u. Stiffness. Using the observations themselves as X
  (the paper's classification setting) turns it into a filter, not a closed-state model.
- **Relevance:** Good for (1) and (3) with u; for (2), X must contain only exogenous inputs, not y or x.
- **Open-source implementations:** torchcde - https://github.com/patrick-kidger/torchcde - maintained (the author now recommends
  diffrax for new projects), ~490 stars - Apache-2.0. diffrax supports CDEs natively.
- **From-scratch simplicity:** Moderate. It is simple with fixed-step Euler on dX = u(t+dt) - u(t).
- **References:**
  - Neural Controlled Differential Equations for Irregular Time Series. P. Kidger, J. Morrill, J. Foster, T. Lyons. 2020. NeurIPS 2020. https://arxiv.org/abs/2005.08926 ; https://ar5iv.labs.arxiv.org/html/2005.08926 [read-full]
  - torchcde repository [repo/docs]

### Neural SDEs and latent SDEs
- **Core idea:** dz = mu_theta(z, t) dt + sigma_theta(z, t) dW. The latent SDE of Li et al. has a prior SDE and a posterior SDE
  with the same diffusion but a data-conditioned drift. The ELBO's path-space KL is integral 1/2 |u|^2 dt, where
  sigma u = h_phi - h_theta (read). Gradients use a stochastic adjoint with O(1) memory and a virtual Brownian tree. Kidger et al.
  2021 fit SDEs as Wasserstein GANs with a neural-CDE discriminator.
- **Assumptions:** Markov diffusion. The diffusion must be shared between prior and posterior for the KL to be finite.
- **Identifiability:** The drift and diffusion of an observed SDE are identifiable in principle given dense data. In latent form,
  they are identified only up to diffeomorphism (with Ito correction terms).
- **Intervention support:** Inputs enter the drift. The stochastic latent lets the model represent **intrinsic noise** that a
  compact z cannot explain, which is useful for honest closure tests where the microscopic simulator is noisy.
- **Nonlinear capacity:** High.
- **Interpretability:** Low to moderate. The drift field is analysable.
- **Scaling:** Several samples per sequence. The adjoint gives O(1) memory. It is slower than ODEs.
- **Failure modes:** Diffusion absorbs model error: a large learned sigma "explains" poor dynamics. **This is a real
  dimension-cheating risk: unmodelled state gets treated as noise.** Stability of SDE-GAN training is also a concern. Note that
  torchsde was **archived (read-only) in April 2026**.
- **Relevance:** Useful for (8). Comparing the learned diffusion magnitude across k gives an abstention signal: if the residual
  noise does not shrink as k grows, no compact deterministic state exists.
- **Open-source implementations:** torchsde - https://github.com/google-research/torchsde - archived Apr 2026, ~1.7k stars -
  Apache-2.0 (latent SDE and SDE-GAN examples). diffrax (JAX) - Apache-2.0 - active.
- **From-scratch simplicity:** Moderate. Euler-Maruyama with direct backprop is easy. The adjoint and Brownian tree are hard.
- **References:**
  - Scalable Gradients for Stochastic Differential Equations. X. Li, T.-K. L. Wong, R. T. Q. Chen, D. Duvenaud. 2020. AISTATS 2020. https://arxiv.org/abs/2001.01328 ; https://ar5iv.labs.arxiv.org/html/2001.01328 [read-full]
  - Neural SDEs as Infinite-Dimensional GANs. P. Kidger, J. Foster, X. Li, H. Oberhauser, T. Lyons. 2021. ICML 2021. https://arxiv.org/abs/2102.03657 [read-abstract]
  - torchsde repository [repo/docs]

### Deep linear-recurrence sequence models as black-box predictors: S4, S5, LRU, Mamba (+ bottleneck)
- **Core idea:** Stacks of linear state-space recurrences with nonlinear mixing between layers. S4 uses structured (HiPPO,
  low-rank-corrected) SISO SSMs computed via a convolution kernel. S5 uses one MIMO diagonal SSM per layer with a parallel scan.
  LRU shows that a plain RNN with linear diagonal complex recurrence, stable exponential parameterisation, careful initialisation
  and normalisation matches SSMs. Mamba makes the SSM parameters input-dependent ("selective").
- **Assumptions:** None about the system. These are generic sequence-to-sequence predictors.
- **Identifiability:** None. The internal state has dimension (#layers x #channels x state size), in the thousands, so it is **not a
  compact state**.
- **Intervention support:** Inputs u and intervention descriptors can be fed as extra input channels. Out-of-distribution
  intervention generalisation is not addressed.
- **Nonlinear capacity:** High.
- **Interpretability:** Low.
- **Scaling:** Excellent in T (parallel scan or convolution). Mamba's fast kernels need CUDA or ROCm GPUs (Linux).
- **Relevance to problem (props 1-8):** Use here as an **upper-bound predictor** (history-conditioned, large state), and as a **bottlenecked** model. For the
  bottleneck version, encode x(t0) into a k-dimensional vector, broadcast or inject it as the initial condition or first token,
  and let the sequence model map (z, u_{t0:t0+H}) to y. The same design applies to a transformer that must route all
  information about x(t0) through a single "bottleneck token" of dimension k (a generic design; I did not read a specific
  primary source for it; unverified). **Caveat:** the decoder here is a powerful non-Markov map of the input sequence, so the
  bottleneck tests predictive sufficiency (1) and minimal k (5), but NOT closure (2). For closure, also require that z(t+h)
  re-encoded from the true x(t+h) predicts the remainder of the trajectory equally well (a semigroup consistency check).
- **Failure modes:** Input copying (the output is a function of u alone); memorisation; hidden history in the decoder.
- **Open-source implementations:** state-spaces/s4 - https://github.com/state-spaces/s4 - active, ~2.9k stars - Apache-2.0
  (S4, S4D, DSS, ...). lindermanlab/S5 - https://github.com/lindermanlab/S5 - ~325 stars, JAX - MIT.
  NicolasZucchet/minimal-LRU (unofficial LRU) - https://github.com/NicolasZucchet/minimal-LRU - ~65 stars, JAX - MIT.
  state-spaces/mamba - https://github.com/state-spaces/mamba - active, ~18.9k stars - Apache-2.0.
- **From-scratch simplicity:** LRU/S5 are simple (a diagonal complex recurrence plus a scan, about 100 lines). S4 is hard.
  Mamba is simple in pure PyTorch but slow without kernels.
- **References:**
  - Efficiently Modeling Long Sequences with Structured State Spaces. A. Gu, K. Goel, C. Ré. 2022. ICLR 2022. https://arxiv.org/abs/2111.00396 [read-abstract]
  - Simplified State Space Layers for Sequence Modeling. J. T. H. Smith, A. Warrington, S. W. Linderman. 2023. ICLR 2023. https://arxiv.org/abs/2208.04933 [read-abstract]
  - Resurrecting Recurrent Neural Networks for Long Sequences. A. Orvieto, S. L. Smith, A. Gu et al. 2023. ICML 2023. https://arxiv.org/abs/2303.06349 [read-abstract]
  - Mamba: Linear-Time Sequence Modeling with Selective State Spaces. A. Gu, T. Dao. 2023. arXiv:2312.00752. https://arxiv.org/abs/2312.00752 [read-abstract]
  - s4, S5, minimal-LRU, mamba repositories [repo/docs]

### Latent-space self-prediction: JEPA-style and self-predictive representations (JEPA / SPR / BYOL-style)
- **Core idea:** Predict the *representation* of future (or masked) inputs rather than the inputs themselves. The loss is
  ||P(f(z_t, a_{t:t+h})) - sg(phi_EMA(x_{t+h}))||, with an EMA target encoder and stop-gradient. SPR does this multi-step with an
  action-conditioned transition model. I-JEPA does it spatially with masked context and target blocks.
- **Assumptions:** No generative model. A trivial constant representation minimises the loss, so avoiding collapse relies on
  optimisation dynamics. Tang et al. identify a faster-learning predictor and semi-gradient (stop-gradient) updates as the key
  ingredients. Under idealised linear assumptions, self-predictive learning recovers spectral information (eigenvectors) of the
  transition matrix.
- **Identifiability:** At best, in the idealised linear case, the dominant invariant subspace of the transition operator is
  recovered up to linear transformations. This connects to Koopman methods. In general there is none.
- **Intervention support:** Actions enter the latent transition (SPR). It gives multi-step interventional prediction in latent
  space only. y must be decoded by a separate head.
- **Nonlinear capacity:** High.
- **Interpretability:** Low to moderate.
- **Scaling:** Cheap. There is no decoder over N units.
- **Failure modes:** **Complete or dimensional collapse** (latents shrink or occupy a subspace). Because nothing forces the
  latent to retain y-relevant information, it may keep only the easily predictable slow modes, which is predictively
  insufficient for y. Always add a y-prediction head, and a variance/covariance regulariser (VICReg-style, unverified in this
  area's reading) or reconstruction.
- **Relevance:** Attractive for (2) and (4): the loss asks directly that z_{t+h} be a function of z_t and u, which is closure in
  latent space. But it must be paired with a y or x decoder for (1), and collapse checks are needed for (5), since collapsed
  dimensions make k look smaller than it is.
- **Open-source implementations:** SPR code is linked from the paper (not checked, licence not verified). I-JEPA code (not
  checked, licence not verified).
- **From-scratch simplicity:** Simple, but the collapse diagnostics (per-dimension variance, effective rank) are mandatory.
- **References:**
  - Data-Efficient Reinforcement Learning with Self-Predictive Representations. M. Schwarzer, A. Anand, R. Goel et al. 2021. ICLR 2021. https://arxiv.org/abs/2007.05929 [read-abstract]
  - Understanding Self-Predictive Learning for Reinforcement Learning. Y. Tang, Z. D. Guo, P. H. Richemond et al. 2023. arXiv:2212.03319 (ICML 2023, unverified). https://arxiv.org/abs/2212.03319 [read-abstract]
  - Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture. M. Assran, Q. Duval, I. Misra et al. 2023. ICCV 2023. https://arxiv.org/abs/2301.08243 [read-abstract]

### Contrastive predictive coding (CPC)
- **Core idea:** An encoder z_t = g_enc(x_t) and an autoregressive context c_t = g_ar(z_{<=t}). A bilinear score predicts z_{t+k}
  from c_t, trained with the InfoNCE contrastive loss against negatives. This maximises a lower bound on I(x_{t+k}; c_t)
  (bound form from memory; unverified in reading).
- **Assumptions:** Negatives are representative. The information of interest is predictable across time.
- **Identifiability:** None. Only mutual information is constrained, which is invariant to any invertible map.
- **Intervention support:** None natively. Actions can be added to the predictor.
- **Nonlinear capacity:** High.
- **Interpretability:** Low.
- **Scaling:** Cheap. The quality of the bound saturates at log(#negatives) (unverified).
- **Failure modes:** The context c_t is a history summary (non-Markov). The representation keeps "slow features" useful for
  discriminating negatives, not necessarily what matters for y. Negatives sampled from the same trajectory can be too easy or too hard.
- **Relevance:** Mainly as a scoring tool. An InfoNCE critic between z_t and future y or x is a model-free estimate of
  predictive information retained by z. Comparing I(z_t; future) with I(x_t; future) quantifies predictive sufficiency (1)
  without training a generative decoder.
- **Open-source implementations:** No official code checked. Licence not verified.
- **From-scratch simplicity:** Simple.
- **References:**
  - Representation Learning with Contrastive Predictive Coding. A. van den Oord, Y. Li, O. Vinyals. 2018. arXiv:1807.03748. https://arxiv.org/abs/1807.03748 [read-abstract]

### Contrastive learning of structured world models (C-SWM)
- **Core idea:** Encode observations into (object-factored) latents and learn a transition z_t + T(z_t, a_t) with a GNN over
  objects. It is trained with an energy-based hinge loss: pull d(z_t + T(z_t, a_t), z_{t+1}) down and push the distance to
  random negative states above a margin. There is no reconstruction. Evaluation uses latent-space ranking (Hits@1, MRR) after
  multi-step rollouts.
- **Assumptions:** Deterministic, Markov, fully observed from one frame (the paper states it is limited to deterministic worlds).
  Factorisation into slots.
- **Identifiability:** None. The hinge loss is invariant to isometries and, near the margin, to rescaling.
- **Intervention support:** Actions are assigned to objects and enter the GNN edges and nodes. Factorisation gives some
  compositional generalisation to new combinations.
- **Nonlinear capacity:** Moderate to high.
- **Interpretability:** Moderate. Slots are interpretable when objects exist.
- **Scaling:** Cheap. The GNN is O(K^2) in slots.
- **Failure modes:** Deterministic only. Ranking metrics can be high while metric accuracy is poor. Negatives from the buffer
  can cause a trivial solution if they are too easy.
- **Relevance:** Its **evaluation protocol** transfers well: multi-step latent rollout ranked against encodings of true future
  states tests closure (2) and microstate invariance (4) directly in latent space. The slot-factored transition is relevant for
  (7) only speculatively.
- **Open-source implementations:** tkipf/c-swm - https://github.com/tkipf/c-swm - stale, ~400 stars, PyTorch - MIT.
- **From-scratch simplicity:** Simple.
- **References:**
  - Contrastive Learning of Structured World Models. T. Kipf, E. van der Pol, M. Welling. 2020. ICLR 2020. https://arxiv.org/abs/1911.12247 ; https://ar5iv.labs.arxiv.org/html/1911.12247 [read-full]
  - c-swm repository [repo/docs]

### Recurrent switching linear dynamical systems (rSLDS)
- **Core idea:** A discrete mode s_t selects linear-Gaussian dynamics x_t = A_{s_t} x_{t-1} + b_{s_t} + noise over a continuous
  latent. In the "recurrent" version the mode transition depends on the previous continuous latent through stick-breaking
  logistic regression. Polya-gamma augmentation makes the conditionals Gaussian, which enables O(T) block Gibbs / message
  passing. Variants include shared recurrence weights, recurrence-only, sticky, and tree-structured.
- **Assumptions:** Piecewise-linear dynamics partitioned by (approximately) linear boundaries in latent space. Gaussian or
  GLM emissions. A fixed number of modes K.
- **Identifiability:** The continuous latent is identified up to an invertible linear (affine) map per model, as in an LDS, and
  the modes up to permutation. Stick-breaking ordering is an artefact the authors address with greedy initialisation. This is
  stronger than most entries in this area.
- **Intervention support:** The lindermanlab ssm package supports exogenous inputs in transitions and dynamics (per its
  input-driven model classes; details not verified in docs read). There are no do-interventions.
- **Nonlinear capacity:** Moderate (K linear pieces). It is a natural approximation for multistable or piecewise systems.
- **Interpretability:** High. It gives fixed points per mode, linear dynamics and switching surfaces.
- **Scaling:** Gibbs or SVI is O(T (k^3 + K)). Examples in the paper use k = 2-3 and K = 4. Emissions to N ~ 100-5000 are fine
  with Gaussian or Poisson GLMs.
- **Failure modes:** Choice of K and k. Slow mixing. Mode proliferation to fit nonlinearity. Nonlinear transition alternatives
  need non-conjugate inference (the authors note this).
- **Relevance:** A good interpretable baseline for (5), (6) and (2). Affine identifiability helps (6) and (7): shared f across
  implementations can be tested via affine alignment of latents.
- **Open-source implementations:** lindermanlab/ssm - https://github.com/lindermanlab/ssm - maintained (a JAX refactor is in
  progress), ~720 stars - MIT (HMM, ARHMM, IOHMM, LDS, SLDS, rSLDS; EM, SVI). probml/dynamax - https://github.com/probml/dynamax -
  active, ~1k stars - MIT (HMM, LGSSM, nonlinear Gaussian SSM with EKF/UKF, inputs supported; no rSLDS seen).
- **From-scratch simplicity:** Hard for the Bayesian Polya-gamma version. Moderate for a variational/gradient version
  (a Laplace-EM variant exists in ssm; unverified).
- **References:**
  - Recurrent Switching Linear Dynamical Systems. S. W. Linderman, A. C. Miller, R. P. Adams et al. 2017. AISTATS 2017. https://arxiv.org/abs/1610.08466 ; https://ar5iv.labs.arxiv.org/html/1610.08466 [read-full]
  - ssm; dynamax repositories [repo/docs]

### Hamiltonian / Lagrangian neural networks (HNN / LNN) - brief
- **Core idea:** Learn a scalar H(q, p) (or L(q, qdot)) and derive the vector field from Hamilton's or Euler-Lagrange equations.
  This enforces energy conservation and time reversibility.
- **Assumptions:** Conservative (energy-preserving), autonomous dynamics in canonical coordinates (HNN) or with a Lagrangian
  (LNN); smooth vector fields.
- **Intervention support:** None natively; external forcing and dissipation require port-Hamiltonian or forced variants
  (unverified; not read).
- **Nonlinear capacity:** High within the conservative class; none outside it (cannot represent attracting fixed points or
  limit cycles, which are dissipative).
- **Interpretability:** Moderate: the learned energy function is a readable scalar invariant.
- **Scaling (N, T, data size):** Needs time derivatives (or integration) and gradients of a scalar network; latent versions
  scale like other neural ODEs.
- **Failure modes:** Structural mismatch with dissipative, driven dynamics; forced conservation distorts trajectories or
  inflates k.
- **Relevance:** Mostly **not appropriate** here. Driven, dissipative, input-forced population dynamics violate conservation,
  and a forced conservative structure would bias k upward. Port-Hamiltonian or dissipative extensions exist (unverified;
  not read). Listed for completeness.
- **Identifiability / other fields:** H is identified up to an additive constant in canonical coordinates. In a latent, coordinates
  are identified only up to symplectomorphisms.
- **Open-source implementations:** Code is referenced by the papers (not checked, licence not verified).
- **From-scratch simplicity:** Simple (autograd of a scalar MLP; symplectic or RK integration).
- **References:**
  - Hamiltonian Neural Networks. S. Greydanus, M. Dzamba, J. Yosinski. 2019. NeurIPS 2019. https://arxiv.org/abs/1906.01563 [read-abstract]
  - Lagrangian Neural Networks. M. Cranmer, S. Greydanus, S. Hoyer et al. 2020. ICLR 2020 DeepDiffEq workshop. https://arxiv.org/abs/2003.04630 [read-abstract]

### Dynamical-systems reconstruction with PLRNNs, sparse teacher forcing and generalized teacher forcing (PLRNN / dendPLRNN / shPLRNN + STF / GTF)
- **Core idea:** Train a small RNN to be a *generative* model of the dynamics (attractor geometry and long-term statistics), not
  just a one-step predictor. The theory (Mikhaeil et al.) says that for RNNs with chaotic dynamics, loss gradients necessarily
  diverge with sequence length (via the Lyapunov spectrum), while stable or periodic RNNs have bounded gradients. Their fix is
  **sparse teacher forcing**: every tau steps, replace the latent by the "inverted" observation z = B^+ x, with
  tau ~ ln2 / lambda_max estimated from data. **GTF** (Hess et al.) instead forces at every step by interpolation,
  z~_t = (1 - alpha) z_t + alpha z_bar_t, with alpha* = 1 - 1/sigma_max (sigma_max bounds the Jacobian spectral norm). An
  adaptive-annealing variant (aGTF) starts at alpha = 1 and decays. The architecture is the shallow PLRNN
  z_t = A z_{t-1} + W1 ReLU(W2 z_{t-1} + h2) + h1 (A diagonal) with a linear observation x = B z. dendPLRNN adds a spline basis
  expansion and is trained by BPTT+TF or VI.
- **Evaluation measures (read in GTF):** **D_stsp**, the KL between the state-space occupation distributions of true and
  free-running generated trajectories in observation space, computed by binning (low-dimensional) or a GMM approximation
  (higher-dimensional). **D_H**, the Hellinger distance between smoothed power spectra per observed variable, averaged (0 = perfect).
  **n-step prediction error** (MSE) from test initial conditions.
- **Assumptions:** Observations are (close to) a linear readout of the latent. The latent dimension M is at least the
  observation dimension used for forcing, since B^+ must give full forcing. Autonomous or input-driven (inputs can be added
  linearly, C u_t, unverified in these papers). Stationary long-term dynamics are needed for D_stsp and D_H to be meaningful.
- **Identifiability:** None beyond conjugacy. PLRNNs, however, allow analytic fixed-point and cycle search, which helps compare
  dynamics up to topological conjugacy.
- **Intervention support:** Weak. It is focused on autonomous reconstruction. Offsets can be simulated by perturbing the latent.
- **Nonlinear capacity:** High, including chaos and multistability, which is exactly what stability-constrained training kills.
- **Interpretability:** High for PLRNN (piecewise-linear regions, analytic fixed points).
- **Scaling:** Small models (M ~ 3-50, L hidden ~ 10^2-10^3; unverified ranges). Linear readout to large N is fine, but forcing
  via B^+ from N ~ 5000 units needs an encoder or dimension reduction first. The GTF paper notes the forcing is defined via the
  pseudo-inverse of B.
- **Failure modes:** GTF benefits were not reproduced for dendPLRNN (stated limitation). sigma_max estimates are crude. Unbounded
  ReLU needs clipping. Short-horizon MSE is uninformative for chaotic systems, which is why D_stsp and D_H are used.
- **Relevance:** Highly relevant training recipe for (1) and (2) when the latent dynamics may be chaotic: **multi-step rollouts
  with partial forcing are the right way to train a closed f without exploding gradients.** For this contract, replace B^+ x with
  the learned encoder phi(x) as the forcing signal (z_bar_t = phi(x_t)). D_stsp and D_H are the right long-horizon evaluation
  measures when trajectories are chaotic.
- **Open-source implementations:** DurstewitzLab/GTF-shPLRNN - https://github.com/DurstewitzLab/GTF-shPLRNN - Julia/Flux, ~23 stars
  - **GPL-3.0** (implements D_stsp by binning or GMM, and Lyapunov spectra via DynamicalSystems.jl). DurstewitzLab/dendPLRNN -
  https://github.com/DurstewitzLab/dendPLRNN - PyTorch, ~24 stars - **GPL-3.0**. The GPL licence matters if code is vendored;
  re-implementing from the paper is easy.
- **From-scratch simplicity:** Simple. shPLRNN plus the GTF mixing takes about 50 lines. D_H is simple (FFT, Gaussian
  smoothing, Hellinger). D_stsp by binning is simple in low dimension; in high dimension use a GMM on trajectory points.
- **References:**
  - On the difficulty of learning chaotic dynamics with RNNs. J. M. Mikhaeil, Z. Monfared, D. Durstewitz. 2022. NeurIPS 2022. https://arxiv.org/abs/2110.07238 ; https://ar5iv.labs.arxiv.org/html/2110.07238 [read-full]
  - Generalized Teacher Forcing for Learning Chaotic Dynamics. F. Hess, Z. Monfared, M. Brenner, D. Durstewitz. 2023. ICML 2023. https://arxiv.org/html/2306.04406 [read-full]
  - Tractable Dendritic RNNs for Reconstructing Nonlinear Dynamical Systems. M. Brenner, F. Hess, J. M. Mikhaeil et al. 2022. ICML 2022. https://arxiv.org/abs/2207.02542 [read-abstract]
  - GTF-shPLRNN; dendPLRNN repositories [repo/docs]

---

## E. Causal representation learning, identifiability, invariance and causal abstraction

_Source notes: `notes\area_E_causal_rep_learning.md`._

Scope: methods only. The target problem (CONTRACT.md) is a micro-simulator x(t) (N units) with input u(t), readout y(t) and
microscopic interventions; we want z = phi(x), z' = f(z,u), y = g(z,u). This area asks: under which data and intervention
regimes is z identifiable, and up to what transformation? How do we test whether (phi, f, g) is a valid causal abstraction of
the simulator?

Citation tags: [read-full] = substantial body text read; [read-abstract] = abstract or landing page only; [repo/docs] = repo
or docs read; [unverified] = from memory, not opened in this session. Venue details not shown on the page I opened are
marked (unverified).

### Quick map: identifiability classes and data requirements

| Result | Identifiability class | Data / intervention requirement |
|---|---|---|
| TCL (2016) | sources up to pointwise (elementwise) transforms, after a final linear ICA | nonstationary time series, segment labels |
| PCL (2017) | elementwise, under stated conditions | stationary, temporally dependent, non-Gaussian sources |
| GCL (2019) / iVAE (2020) | permutation + elementwise (details unverified) | observed auxiliary variable u that modulates a factorised prior |
| LEAP / TDRL / CaRiNG | componentwise (permutation + elementwise) latent processes (details unverified) | time-lagged latent transitions plus nonstationarity or fixed dynamics; CaRiNG allows a non-invertible mixing |
| SlowVAE | permutation + elementwise/sign (unverified detail) | sparse (Laplace-like) temporal transitions |
| CITRIS / iCITRIS | blocks of multidimensional causal variables, up to invertible maps within each block (unverified detail) | temporal sequences, **known** intervention targets (binary target vector per step) |
| BISCUIT | causal variables (componentwise, unverified detail) | **unknown** binary interaction variables per causal variable, driven by an observed action/regime |
| Ahuja et al. | perfect do: permutation + scaling; imperfect: block-affine | polynomial decoder (unverified detail); interventional data |
| Squires et al. (linear) | full latent linear SCM | linear mixing and linear latent SCM; **one intervention per latent node** is necessary and sufficient |
| Varici et al. (score-based) | linear transform up to scaling plus DAG | linear mixing; soft interventions give the DAG; hard interventions give the transform |
| Buchholz et al. | linear Gaussian latent SCM through a **general nonlinear** mixing | single-node interventions, unknown targets |
| von Kugelgen et al. 2023 | nonparametric latent SCM (up to the stated ambiguities) | unknown-target **perfect** interventions: 2 variables need one per node; more variables need two distinct perfect interventions per node |
| Zhang et al. 2023 | CD-equivalence class | single-node **soft** interventions, unpaired data, generalised faithfulness |
| Content/style, multi-view | block identifiability of the shared (content) block, up to a smooth invertible map | paired views sharing content |
| Zimmermann et al. | orthogonal + scaling (hypersphere/vMF); affine (convex body); permutation + sign (Lp, p != 2) | positive pairs drawn from a conditional that matches the model |
| Roeder et al. | linear (function space) | a broad family of discriminative/contrastive models |
| CEBRA | inherits contrastive identifiability (affine/linear), checked in practice by a linear-fit consistency R^2 | time or auxiliary labels |

Main implication for the target problem: the simulator gives us **micro-level** interventions with known micro targets. At the
macro level (z) these are usually **unknown-target, possibly multi-node, soft** interventions. So the theorems that fit best
are the unknown-target and soft-intervention ones (BISCUIT, Buchholz, von Kugelgen 2023, Zhang 2023), plus the temporal
nonlinear-ICA results. Theorems that need known macro targets or perfect single-node macro interventions (CITRIS, Squires)
fit only if we can build such interventions ourselves, e.g. by pushing a chosen z-coordinate through a realiser (see the
synthesis section).

---

### Time-contrastive / permutation-contrastive / generalized contrastive learning for nonlinear ICA (TCL, PCL, GCL)
- **Core idea:** Train a feature extractor h(x) and a multinomial or logistic classifier to discriminate (TCL) which time
  segment a sample came from, (PCL) real consecutive windows from time-shuffled windows, or (GCL) real (x, aux) pairs from
  pairs with a randomised auxiliary variable. At the optimum, h recovers the independent sources.
- **Assumptions:** Invertible, smooth mixing x = F(s). TCL: sources are nonstationary, with a variance/exponential-family
  modulation that differs across segments (enough distinct segments). PCL: stationary sources with non-Gaussian temporal
  dependence (for Gaussian sources only the mixing part is recovered). GCL: the auxiliary variable (time index, history, label)
  modulates conditionally independent sources.
- **Identifiability:** TCL plus a final linear ICA recovers sources "up to point-wise transformations" (abstract). PCL and GCL
  give elementwise identifiability under their conditions (GCL states full identifiability and consistency).
- **Intervention support:** None explicit. An intervention regime label, or the input u(t), can serve as the auxiliary
  variable or segment label, so the modulation can come from interventions. There is no mechanism for predicting held-out
  interventions.
- **Nonlinear capacity:** Arbitrary invertible nonlinear mixing, estimated with a deep net.
- **Interpretability:** Each recovered source is one independent coordinate, but its scale and nonlinearity are unknown
  (elementwise gauge).
- **Scaling:** A classifier over segments. Cheap and scales like standard supervised training. Needs many segments (TCL) and
  a long T.
- **Failure modes:** The theory assumes latent dimension = observed dimension (invertible) and independent sources. The latents
  of the target problem are dynamically coupled, not independent. Too few segments or weak modulation gives partial
  identification. The classifier can exploit trivial cues such as time trends (a form of time leakage).
- **Relevance:** (6) elementwise identifiability gives a principled route to seed-stable coordinates. (1),(2),(3) are not
  addressed: these are representation methods with no transition model. Useful as an **encoder pre-training or baseline
  family**; PCL-style "real vs shuffled window" is a cheap self-supervised signal.
- **Open-source implementations:** No canonical maintained package seen. Implementations exist inside research repos
  (unverified). The iVAE repo (below) contains related code.
- **From-scratch simplicity:** Simple (a classifier plus a feature net). Pitfall: segment boundaries and normalisation leak
  time.
- **References:**
  - Hyvarinen, A., Morioka, H. (2016). Unsupervised Feature Extraction by Time-Contrastive Learning and Nonlinear ICA. NeurIPS 2016 (venue unverified; arXiv page read). https://arxiv.org/abs/1605.06336 [read-abstract]
  - Hyvarinen, A., Morioka, H. (2017). Nonlinear ICA of Temporally Dependent Stationary Sources. AISTATS 2017, PMLR 54:460-469. https://proceedings.mlr.press/v54/hyvarinen17a.html [read-abstract]
  - Hyvarinen, A., Sasaki, H., Turner, R. E. (2019). Nonlinear ICA Using Auxiliary Variables and Generalized Contrastive Learning. AISTATS 2019. https://arxiv.org/abs/1805.08651 [read-abstract]

### Identifiable VAE (iVAE)
- **Core idea:** A VAE whose latent prior p(z|u) is factorised and conditioned on an observed auxiliary variable u. This makes
  the joint p(x,z) identifiable up to simple transformations, which unifies VAEs with nonlinear ICA.
- **Assumptions:** Conditionally factorised exponential-family prior given u. Injective decoder. Enough distinct values of u,
  roughly 2n+1 in the exponential-family theorem (unverified detail). Handles observation noise, the undercomplete case and
  discrete observations (abstract).
- **Identifiability:** Up to "very simple transformations" (abstract). In the paper these are a permutation plus componentwise
  (affine in sufficient statistics) maps (unverified detail).
- **Intervention support:** u can be an intervention or environment index, so the model learns latents that are modulated by
  regime. It does not predict unseen regimes and has no dynamics.
- **Nonlinear capacity:** Deep decoder and encoder.
- **Interpretability:** Moderate; axis-aligned latents up to elementwise maps.
- **Scaling:** Standard VAE cost. Fine for N ~ 100-5,000 with an MLP encoder.
- **Failure modes:** Posterior collapse. The conditions on u are easily violated when u varies too little. Guarantees hold
  only at the MLE with infinite data. Its latent independence given u conflicts with coupled dynamics.
- **Relevance:** (6) seed stability (identifiability). For (3), environment labels can come from intervention families.
  The temporal extensions below are closer to the problem.
- **Open-source implementations:** ilkhem/iVAE - https://github.com/ilkhem/iVAE - stale (last push 2020-06), ~42 stars - MIT [repo/docs]
- **From-scratch simplicity:** Simple (a VAE with a learned conditional prior network).
- **References:**
  - Khemakhem, I., Kingma, D. P., Monti, R. P., et al. (2020). Variational Autoencoders and Nonlinear ICA: A Unifying Framework. AISTATS 2020, PMLR 108:2207-2217. https://arxiv.org/abs/1907.04809 [read-abstract]

### Identifiable temporal latent causal processes (LEAP, TDRL, CaRiNG)
- **Core idea:** Latent variables z_t follow time-lagged causal transitions z_t = f(z_{t-1..t-L}, eps_t) with independent
  noise and are observed through a nonlinear mixing. A sequential VAE whose learned prior enforces this transition structure
  (conditionally independent innovations; a flow or noise-inversion prior) recovers the latents and their lagged graph. LEAP
  uses nonstationarity (domain index) or a parametric process. TDRL covers fixed nonparametric dynamics and distribution
  shift, factorising the shifts into transition changes. CaRiNG handles a **non-invertible** mixing by using temporal context
  to recover lost information.
- **Assumptions:** Time-delayed influences between latents. No instantaneous effects (in LEAP/TDRL). Conditionally independent
  innovations given the past. Enough variability of the transition across time or domains (LEAP nonparametric setting), or
  sufficient change of the conditional (TDRL). Invertible mixing (LEAP/TDRL); relaxed in CaRiNG.
- **Identifiability:** Componentwise (permutation + elementwise invertible) recovery of the latent processes, plus the lagged
  causal graph (per abstracts; the exact class is unverified).
- **Intervention support:** Domain or regime labels (TDRL: distribution shift) can come from intervention families or
  parameter draws. There is no explicit do-operator on latents. Held-out interventions are predicted only if they appear as
  changes in the modelled transition.
- **Nonlinear capacity:** Nonparametric transitions and mixing (neural).
- **Interpretability:** Recovered lagged graph among the latents, which is useful for mechanistic reading.
- **Scaling:** A sequential VAE with a normalising-flow prior. Moderate cost. Performance is typically shown at small latent
  dimension (≤ 10) (unverified).
- **Failure modes:** Instantaneous effects (sampling that is coarse relative to the dynamics) break the theory; later work
  addresses this. The latent independence assumption is fragile. The latent dimension must be specified. Guarantees are
  asymptotic.
- **Relevance:** (1),(2) The model *is* a Markov latent transition law with a lag L, so it matches f directly. (6)
  componentwise identifiability. (3) partial: domain labels from intervention families. (7) TDRL-style "fixed dynamics
  across domains with domain-specific shift" parallels "shared f, implementation-specific nuisance". Strong tournament
  candidate as "identifiable sequential VAE".
- **Open-source implementations:** weirayao/leap - https://github.com/weirayao/leap - stale (2022), ~41 stars - MIT [repo/docs];
  weirayao/tdrl - https://github.com/weirayao/tdrl - stale (2022), ~2 stars - MIT [repo/docs]; sanshuiii/CaRiNG -
  https://github.com/sanshuiii/CaRiNG - low activity (2025), ~8 stars - MIT [repo/docs]
- **From-scratch simplicity:** Moderate. You need the inverse-transition noise estimator and a Jacobian log-determinant term
  in the prior. Pitfalls: log-det numerical stability and KL balancing.
- **References:**
  - Yao, W., Sun, Y., Ho, A., et al. (2022). Learning Temporally Causal Latent Processes from General Temporal Data. ICLR 2022. https://arxiv.org/abs/2110.05428 [read-abstract]
  - Yao, W., Chen, G., Zhang, K. (2022). Temporally Disentangled Representation Learning. NeurIPS 2022. https://arxiv.org/abs/2210.13647 [read-abstract]
  - Chen, G., Shen, Y., Chen, Z., et al. (2024). CaRiNG: Learning Temporal Causal Representation under Non-Invertible Generation Process. ICML 2024. https://arxiv.org/abs/2401.14535 [read-abstract]

### SlowVAE (temporal sparse coding)
- **Core idea:** A VAE on pairs of consecutive frames with a sparse (Laplace) prior on the latent transition z_t - z_{t-1}:
  most factors change little and some jump. It comes with an identifiability proof.
- **Assumptions:** Sparse, heavy-tailed temporal transitions of the generative factors. Invertible mixing. It does not need to
  know how many factors change per step.
- **Identifiability:** The abstract states an identifiability proof. The class is permutation + sign/elementwise
  (unverified detail).
- **Intervention support:** None.
- **Nonlinear capacity:** Deep VAE.
- **Interpretability:** Axis-aligned slow factors.
- **Scaling:** Cheap; the unit of data is a pair of frames.
- **Failure modes:** Smooth, non-sparse dynamics (typical of continuous population dynamics) violate the prior. Oscillatory
  latents change every step.
- **Relevance:** Mostly as a **baseline and prior choice** for (6). A slowness prior pushes toward minimal, slowly varying
  z (5), but can wrongly drop fast yet causally relevant variables (it hurts (1) and (3)).
- **Open-source implementations:** Research code from the authors (not checked; licence not verified).
- **From-scratch simplicity:** Simple.
- **References:**
  - Klindt, D., Schott, L., Sharma, Y., et al. (2021). Towards Nonlinear Disentanglement in Natural Data with Temporal Sparse Coding. ICLR 2021. https://arxiv.org/abs/2007.10930 [read-abstract]

### CITRIS and iCITRIS (causal identifiability from temporal intervened sequences)
- **Core idea:** A VAE (or normalising flow on a pretrained autoencoder) over temporal sequences in which, at each step, a
  known binary vector I_t says which causal variables were intervened on. The latent space is split into blocks, and a learned
  assignment maps latent dimensions to causal variables. The prior p(z_t | z_{t-1}, I_t) is structured so that each block
  depends on its own intervention bit. iCITRIS adds **instantaneous** effects, using differentiable causal discovery over the
  learned variables.
- **Assumptions:** Known intervention targets (observed, e.g. agent actions). Temporal (first-order Markov) latent dynamics.
  Interventions on a variable may affect only some of its components (CITRIS allows partial intervention on multidimensional
  variables). iCITRIS requires observed intervention targets in order to separate instantaneous from lagged effects.
- **Identifiability:** Multidimensional causal variables identified as blocks, i.e. the minimal causal variables, up to
  invertible transformations within blocks (details unverified).
- **Intervention support:** Explicit; the method needs intervention labels. Predicting new intervention *types* is not a
  goal. The learned per-variable block structure supports counterfactual swapping of blocks (a natural interchange test).
- **Nonlinear capacity:** Deep encoders and priors.
- **Interpretability:** Good: one block per causal variable plus a graph.
- **Scaling:** Moderate (VAE/flow training). The number of causal variables is small (≈ 5-10 in experiments; unverified).
- **Failure modes:** Needs targets defined at the macro level. In our problem, micro interventions map to unknown macro
  targets. Wrong or missing target labels break the theory.
- **Relevance:** (3) directly models interventions. (4),(6) block identifiability. For our problem the **micro-to-macro
  target mismatch** is the main obstacle. A workaround is to use designed macro interventions (pushing chosen z-coordinates
  via a realiser; see the synthesis section) once a first phi exists, which gives iterative refinement.
- **Open-source implementations:** phlippe/CITRIS - https://github.com/phlippe/CITRIS - stale (last push 2023-06), ~63 stars - BSD-3-Clause-Clear [repo/docs]
- **From-scratch simplicity:** Moderate to hard (flow prior, target-assignment Gumbel-softmax, the instantaneous graph in iCITRIS).
- **References:**
  - Lippe, P., Magliacane, S., Lowe, S., et al. (2022). CITRIS: Causal Identifiability from Temporal Intervened Sequences. ICML 2022. https://arxiv.org/abs/2202.03169 [read-abstract]
  - Lippe, P., Magliacane, S., Lowe, S., et al. (2023). Causal Representation Learning for Instantaneous and Temporal Effects in Interactive Systems (iCITRIS). ICLR 2023. https://arxiv.org/abs/2206.06169 [read-abstract]

### BISCUIT (causal representation learning from binary interactions)
- **Core idea:** Each latent causal variable has two mechanisms (observational vs "interacted/intervened"). A latent binary
  interaction variable, predicted from an observed regime or action signal, selects the mechanism. The model jointly learns
  the latents and these binary interaction patterns, **without known targets**.
- **Assumptions:** Two mechanisms per variable. The interaction variables are functions of an observed regressor (action,
  regime). Identifiability is shown for common setups such as additive Gaussian noise models (abstract).
- **Identifiability:** The causal variables are identified (componentwise; exact class unverified) under these conditions.
- **Intervention support:** Handles unknown intervention targets, provided a regime or action signal drives them. Our
  micro-intervention descriptor (which units, what offset or current) can play the "action" role; the model then learns which
  macro variables each micro intervention touches. This is exactly the micro-to-macro target mapping we need for (3).
- **Nonlinear capacity:** Deep (normalising flow on autoencoder latents, as in CITRIS; unverified detail).
- **Interpretability:** The learned "which micro action touches which z" map is itself interpretable.
- **Scaling:** Similar to CITRIS.
- **Failure modes:** Real micro interventions give graded, not binary, effects on macro variables; the binary-mechanism
  assumption is then violated. Assumes a one-step Markov latent structure.
- **Relevance:** (3) best-fitting theory in this area for "known micro intervention, unknown macro target". (6)
  identifiability. Candidate for the tournament (see recipe).
- **Open-source implementations:** phlippe/BISCUIT - https://github.com/phlippe/BISCUIT - stale (last push 2024-03), ~41 stars
  - BSD-style licence from Qualcomm Innovation Center (GitHub shows NOASSERTION; the LICENSE text is BSD-like with no patent
  grant) [repo/docs]
- **From-scratch simplicity:** Moderate to hard.
- **References:**
  - Lippe, P., Magliacane, S., Lowe, S., et al. (2023). BISCUIT: Causal Representation Learning from Binary Interactions. UAI 2023. https://arxiv.org/abs/2306.09643 [read-abstract]

### Interventional identifiability theory, parametric/linear latent SCMs (Squires et al.; Varici et al.; Buchholz et al.; Zhang et al.)
- **Core idea:** Recover a latent causal model from observational plus interventional (unpaired) distributions by exploiting
  how the latent distribution changes under single-node interventions. Examples: a generalised RQ decomposition (Squires);
  latent score functions varying minimally across environments (Varici); precision-matrix quadratic forms (Buchholz);
  a generalised faithfulness condition with soft interventions (Zhang).
- **Assumptions:**
  - Squires: linear mixing and a linear latent SCM. **One intervention per latent node is sufficient; missing one makes
    models indistinguishable.**
  - Varici: linear mixing, general nonlinear latent mechanisms. Soft interventions suffice for the DAG; stochastic hard
    interventions recover the transform.
  - Buchholz: Gaussian linear latent SCM, **arbitrary nonlinear mixing**, single-node interventions with **unknown targets**.
    A contrastive algorithm is provided.
  - Zhang: soft single-node interventions, unpaired data, possibly unobserved latent causal variables. An autoencoding
    variational Bayes algorithm is provided; it predicts **unseen combinations** of interventions.
- **Identifiability:** Squires: the full latent model. Varici: transform up to scaling plus DAG. Buchholz: "strong"
  identifiability of the linear causal structure. Zhang: up to CD-equivalence.
- **Intervention support:** Core to the method. Zhang's model predicts effects of combinations of soft interventions that were
  never seen, which is a direct analogue of (3) held-out combinatorial perturbations.
- **Nonlinear capacity:** Limited in the latent SCM (linear or Gaussian) except Varici. The mixing is nonlinear only in
  Buchholz and Zhang (decoder).
- **Interpretability:** High: explicit latent DAG and weights.
- **Scaling:** Algebraic methods are cheap at small k. The VAE variants are moderate.
- **Failure modes:** These are static (i.i.d.) settings, not dynamical systems. Macro interventions induced by micro
  interventions are usually **multi-node**, violating the single-node premise. The requirement of one intervention per latent
  node sets a floor on intervention diversity. Faithfulness violations are possible.
- **Relevance:** (3) theory that tells us **how many distinct intervention families we need** (at least one "clean"
  intervention per latent dimension). It also gives a check on (5): if k exceeds the number of distinguishable intervention
  effects, the extra dimensions are unidentifiable. For a dynamical system the latent SCM can be the time-unrolled
  (z_{t-1}, u_t) -> z_t graph, but these papers do not treat that case directly.
- **Open-source implementations:** Not checked in this session (licence not verified).
- **From-scratch simplicity:** Linear methods are moderate (matrix decompositions, but sensitive to finite-sample noise).
  The nonlinear ones are hard.
- **References:**
  - Squires, C., Seigal, A., Bhate, S., Uhler, C. (2023). Linear Causal Disentanglement via Interventions. ICML 2023 (venue unverified). https://arxiv.org/abs/2211.16467 [read-abstract]
  - Varici, B., Acarturk, E., Shanmugam, K., et al. (2023). Score-based Causal Representation Learning with Interventions. arXiv. https://arxiv.org/abs/2301.08230 [read-abstract]
  - Buchholz, S., Rajendran, G., Rosenfeld, E., et al. (2023). Learning Linear Causal Representations from Interventions under General Nonlinear Mixing. NeurIPS 2023. https://arxiv.org/abs/2306.02235 [read-abstract]
  - Zhang, J., Squires, C., Greenewald, K., et al. (2023). Identifiability Guarantees for Causal Disentanglement from Soft Interventions. NeurIPS 2023 (venue unverified). https://arxiv.org/abs/2307.06250 [read-abstract]

### Interventional identifiability theory, nonparametric/geometric (Ahuja et al.; von Kugelgen et al. 2023)
- **Core idea:** Ahuja et al.: interventional data carries **geometric signatures of the latent support**, e.g. a do-intervention
  pins a coordinate, and this identifies the latents without distributional or graph assumptions. von Kugelgen et al.: with
  unknown-target **perfect** interventions, nonparametric latent SCMs are identifiable under a genericity condition.
- **Assumptions:** Ahuja: a polynomial decoder in the main results (unverified detail); do or imperfect interventions.
  von Kugelgen: nonparametric mixing and SCM; perfect interventions with unknown targets; **for more than two variables, two
  distinct perfect interventional domains per node** (one per node suffices for two variables); genericity.
- **Identifiability:** Ahuja: perfect do gives **permutation + scaling**; imperfect gives **block-affine**. von Kugelgen:
  latents and graph up to ambiguities that preserve causal-influence strengths.
- **Intervention support:** Central. The theory tells us which interventions carry information: hard clamps (do) are much more
  informative than soft ones.
- **Nonlinear capacity:** Nonparametric (von Kugelgen); polynomial decoder (Ahuja).
- **Interpretability:** Theory results. The practical estimators are research-grade.
- **Scaling:** Not a practical-scale method; guidance for experiment design.
- **Failure modes:** Perfect macro interventions are rarely available from micro interventions. An exception is clamping,
  i.e. holding a set of units fixed, if the simulator supports it; state offsets are not clamps.
- **Relevance:** (3) and experiment design. It argues for adding **clamp-type interventions** (hold a unit or subspace fixed
  over a window) to the simulator's intervention menu, not only offsets and currents. It also argues for at least 2
  distinct interventions per putative latent. Clamps on the *macro* variable can be approximated by closed-loop control of
  phi(x) (see recipe).
- **Open-source implementations:** Not checked (licence not verified).
- **From-scratch simplicity:** Hard (the estimators). The design guidance is simple.
- **References:**
  - Ahuja, K., Mahajan, D., Wang, Y., Bengio, Y. (2023). Interventional Causal Representation Learning. ICML 2023 (venue unverified; arXiv page read). https://arxiv.org/abs/2209.11924 [read-abstract]
  - von Kugelgen, J., Besserve, M., Wendong, L., et al. (2023). Nonparametric Identifiability of Causal Representations from Unknown Interventions. NeurIPS 2023. https://arxiv.org/abs/2306.00542 [read-abstract]

### Multi-view / content-style block identifiability (von Kugelgen et al. 2021; Yao et al. 2024)
- **Core idea:** When two or more views share a latent "content" block and differ in "style", contrastive or generative
  learning with one encoder per view recovers the shared block up to an invertible (smooth) map. With partial observability,
  an "identifiability algebra" says which intersections of shared blocks are identifiable.
- **Assumptions:** Paired views (augmentations or simultaneous modalities). Content invariant across the pair. Smooth
  invertible mixing per view. Causal dependence between content and style is allowed.
- **Identifiability:** **Block identifiability**: the content block up to a smooth bijection (not elementwise).
- **Intervention support:** None directly. A pair can be generated by an intervention that changes only "style"
  (implementation details) and keeps the computation fixed.
- **Nonlinear capacity:** Deep encoders.
- **Interpretability:** The block is identified but its internal coordinates are not.
- **Scaling:** Contrastive training; cheap.
- **Failure modes:** Content that is not truly invariant across the views. The encoders can collapse to a lower-dimensional
  block unless the positives are informative.
- **Relevance:** Strongest theory for **(7)**: treat two physical implementations (different N, connectivity or parameter
  draws) run on the same input sequence u as two "views". Their shared content block is the implementation-invariant
  computational state, learned with **implementation-specific encoders**. Also relevant to (4): microstate differences are
  "style".
- **Open-source implementations:** Not checked (licence not verified).
- **From-scratch simplicity:** Simple (InfoNCE with per-view encoders).
- **References:**
  - von Kugelgen, J., Sharma, Y., Gresele, L., et al. (2021). Self-Supervised Learning with Data Augmentations Provably Isolates Content from Style. NeurIPS 2021. https://arxiv.org/abs/2106.04619 [read-abstract]
  - Yao, D., Xu, D., Lachapelle, S., et al. (2024). Multi-View Causal Representation Learning with Partial Observability. ICLR 2024 (venue from a search snippet; unverified). https://arxiv.org/abs/2311.04056 [read-abstract]
  - Gresele, L., et al. (2019). The Incomplete Rosetta Stone Problem: Identifiability Results for Multi-View Nonlinear ICA. UAI 2019. [unverified]

### Contrastive identifiability up to isometry/affine/linear (Zimmermann et al. 2021; Roeder et al. 2021)
- **Core idea:** InfoNCE-trained encoders implicitly invert the generative process when positives are drawn from a
  conditional p(z~|z) that matches the loss's similarity. Separately, a large family of discriminative models is identifiable
  in function space up to a linear map.
- **Assumptions (Zimmermann, theorems read via ar5iv):** Thm 2: latents on the hypersphere, uniform marginal, vMF
  conditional; InfoNCE minimisers recover the latents "up to an orthogonal linear transformation and a constant scaling
  factor". Thm 5: convex-body latent space, uniform marginal, exponential-family conditional based on a metric; gives an
  **affine** recovery. Thm 6: Lp metrics with p >= 1, p != 2, give recovery "up to generalized permutations"
  (permutation + sign). Empirically robust to mismatched marginals and conditionals.
- **Identifiability:** Orthogonal/isometry, affine, or permutation + sign, depending on the geometry. Roeder et al.: linear
  (function space).
- **Intervention support:** None per se. Positive pairs can be built as (x_t, x_{t+dt}), giving time-contrastive learning,
  or as (pre, post) under the same intervention.
- **Nonlinear capacity:** Deep encoders.
- **Interpretability:** Coordinates recovered up to rotation (on the sphere). Lp with p = 1 gives axis alignment.
- **Scaling:** Cheap; batches of negatives.
- **Failure modes:** A mismatch between the conditional and the true dynamics degrades the guarantee (empirically mild in that
  paper). Uniform-marginal assumptions are unrealistic for dynamics. The hypersphere constraint distorts the geometry of
  unbounded latents.
- **Relevance:** (6) gives a concrete transformation class to use when **comparing runs**: evaluate seed stability up to
  orthogonal or affine maps, as the latent-space comparison tools (CKA, Procrustes) covered in another area do. It also motivates choosing an L1-type similarity if we want
  axis-aligned z. (1)-(3) are not addressed without a dynamics head.
- **Open-source implementations:** Authors' code (not checked; licence not verified).
- **From-scratch simplicity:** Simple.
- **References:**
  - Zimmermann, R. S., Sharma, Y., Schneider, S., et al. (2021). Contrastive Learning Inverts the Data Generating Process. ICML 2021, PMLR 139. https://arxiv.org/abs/2102.08850 ; https://ar5iv.labs.arxiv.org/html/2102.08850 [read-full: theorem statements and results]
  - Roeder, G., Metz, L., Kingma, D. P. (2021). On Linear Identifiability of Learned Representations. ICML 2021 (venue unverified; arXiv page read). https://arxiv.org/abs/2007.00810 [read-abstract]

### CEBRA (contrastive embeddings with auxiliary variables), methods only
- **Core idea:** Contrastive learning in which positive pairs are chosen by time offset (self-supervised, "time" mode), by
  closeness in continuous or discrete auxiliary labels ("behaviour"/hypothesis mode), or both (hybrid). Supports multi-session
  training with **one encoder per session** feeding a shared embedding, plus a consistency score (linear-regression R^2 between
  embeddings of different runs or sessions).
- **Assumptions:** The contrastive identifiability conditions above (the sampling conditional should resemble the latent
  conditional). The auxiliary variables must be informative.
- **Identifiability:** Claims embeddings are consistent up to a linear/affine map (checked empirically by R^2 fits across
  runs). Theoretical backing comes from the contrastive identifiability literature.
- **Intervention support:** None explicit. Intervention descriptors or u(t) could be auxiliary labels (hypothesis mode), but
  that risks input copying (the embedding just encodes u).
- **Nonlinear capacity:** Convolutional time-offset encoders (receptive field set by the architecture, e.g. offset10). The
  receptive field means the encoder sees a **window** of x, which breaks the phi(x_t) instantaneous-encoder requirement unless
  it is set to offset1.
- **Interpretability:** Low-dimensional embedding (default 8 dimensions); cosine/sphere geometry by default.
- **Scaling:** Mature, GPU-backed; handles large T and N in the thousands.
- **Failure modes:** Label-supervised modes can simply encode labels, a form of output/input copying (a known critique; see
  the contract pitfalls). There is no transition model f. Sphere geometry needs a temperature choice.
- **Relevance:** (6) consistency metric (between-run linear R^2) is a ready-made seed-stability measure. (7) the multi-session
  design (implementation-specific encoders, shared embedding) mirrors the property. Use as a **strong representation
  baseline**, with a separately fitted f and g, and with time-only sampling to avoid label copying.
- **Open-source implementations:** CEBRA - https://github.com/AdaptiveMotorControlLab/CEBRA - active (push 2026-06), ~1.1k
  stars - Apache-2.0 for v0.4.0+ (versions 0.1.0-0.3.1 were under a non-commercial licence; the LICENSE notes an EPFL patent)
  [repo/docs]. Docs: https://cebra.ai/docs/usage.html [repo/docs]
- **From-scratch simplicity:** Simple (InfoNCE with time-offset positives), but the package is mature enough to use.
- **References:**
  - Schneider, S., Lee, J. H., Mathis, M. W. (2023). Learnable latent embeddings for joint behavioural and neural analysis. Nature 2023. https://arxiv.org/abs/2204.00673 [read-abstract]

### Invariant Causal Prediction (ICP) and nonlinear ICP
- **Core idea:** Among candidate predictor sets S for a target Y, accept those for which the conditional Y | X_S is invariant
  across environments (interventions that do not target Y). The intersection of accepted sets is a confidence set for the
  causal parents, with coverage guarantees. Nonlinear ICP fits a pooled nonlinear regression and tests whether the residual
  distributions differ across environments ("invariant residual distribution test").
- **Assumptions:** Observed variables (no representation learning). Environments do not intervene on Y. Invariance of the
  causal mechanism. Enough environments for power.
- **Identifiability:** The set of causal predictors (confidence intervals are valid in general scenarios; identifiable under
  sufficient SEM assumptions).
- **Intervention support:** Environments = interventions. It does not predict held-out intervention effects but yields a
  mechanism that is invariant under them.
- **Nonlinear capacity:** Linear ICP; nonlinear variants via nonparametric regression and residual tests.
- **Interpretability:** High.
- **Scaling:** Exhaustive over subsets (exponential in the number of candidate predictors); fine for small k (the macro
  level), infeasible at the micro level.
- **Failure modes:** Hidden confounders and weak power give empty sets (which is informative). Complexity increases when
  parent sets exceed two variables (nonlinear ICP abstract).
- **Relevance:** Excellent **test for (2)/(3) at the macro level**. Given candidate z, test whether the transition
  z_{t+1} | (z_t, u_t) is invariant across intervention environments whose micro interventions do not act at time t+1. A
  failed invariance test means z is not closed or not interventionally sufficient. It can also serve as the abstention
  signal (8): "no invariant compact transition found".
- **Open-source implementations:** R package InvariantCausalPrediction and nonlinearICP (not checked; licence not verified).
- **From-scratch simplicity:** Simple for the residual-invariance test (a pooled fit, then a two-sample test per
  environment).
- **References:**
  - Peters, J., Buhlmann, P., Meinshausen, N. (2016). Causal inference using invariant prediction: identification and confidence intervals. JRSS-B 78(5):947-1012. https://arxiv.org/abs/1501.01332 [read-abstract]
  - Heinze-Deml, C., Peters, J., Meinshausen, N. (2018). Invariant Causal Prediction for Nonlinear Models. J. Causal Inference 2018 (venue unverified; arXiv page read). https://arxiv.org/abs/1706.08576 [read-abstract]

### Invariant Risk Minimization (IRM) and its critique
- **Core idea:** Learn a representation Phi such that one classifier on top of Phi is simultaneously optimal in all training
  environments (IRMv1: a gradient-penalty relaxation on a dummy scalar classifier).
- **Assumptions:** Enough and diverse environments; invariant features exist.
- **Identifiability:** None in general. Rosenfeld et al.: in the linear case IRM recovers the invariant predictor only under
  conditions (roughly, the number of environments must exceed the spurious dimension; unverified detail). In the
  nonlinear case "IRM can fail catastrophically unless the test data are sufficiently similar to the training distribution".
- **Intervention support:** Environments as interventions.
- **Nonlinear capacity:** Deep.
- **Interpretability:** Low.
- **Scaling:** Cheap.
- **Failure modes:** As above. No better than ERM in many nonlinear settings. Sensitive to the penalty weight.
- **Relevance:** **Negative guidance**: do not rely on an IRM-style penalty to obtain interventional sufficiency (3). Direct
  interventional prediction losses with explicit held-out intervention families are more trustworthy. At most a weak
  baseline.
- **Open-source implementations:** Reference code by the authors (not checked; licence not verified).
- **From-scratch simplicity:** Simple.
- **References:**
  - Arjovsky, M., Bottou, L., Gulrajani, I., Lopez-Paz, D. (2019). Invariant Risk Minimization. arXiv. https://arxiv.org/abs/1907.02893 [read-abstract]
  - Rosenfeld, E., Ravikumar, P., Risteski, A. (2021). The Risks of Invariant Risk Minimization. ICLR 2021. https://arxiv.org/abs/2010.05761 [read-abstract]

### Formal causal abstraction (exact transformations, tau-abstraction, approximate abstraction, abstraction error)
- **Core idea:** A macro causal model is a valid abstraction of a micro model if a map tau on states (and a map omega on
  interventions) makes the diagram commute: intervening at the micro level and then abstracting gives the same result as
  abstracting and then applying the corresponding macro intervention. Four strands:
  - Rubenstein et al. 2017: **exact transformations** between SEMs; covers marginalisation, micro-to-macro aggregation and
    time-series-to-equilibrium abstraction.
  - Beckers & Halpern 2019: a hierarchy of exact transformation, uniform transformation, tau-abstraction, strong abstraction
    and constructive abstraction; macro-variable aggregation is a case of strong abstraction.
  - Beckers, Eberhardt & Halpern 2019: **approximate** abstraction, i.e. a distance measuring how far the macro model is from
    exact, including probabilistic models.
  - Rischel & Weichwald 2021: a category of causal models, where abstraction error is **compositional** (the error of
    M -> M' -> M'' is bounded by the sum). Otsuka & Saigo 2022: Phi-abstraction as a natural transformation between
    functors; interventional calculus translates consistently. Zennaro et al. 2023: interventional consistency vs
    information-loss measures and algorithms to learn abstractions.
- **Assumptions:** Discrete or finite variables in much of the formal work (Otsuka & Saigo: discrete; Rischel & Weichwald:
  finite stochastic maps; unverified detail for others). A given set of allowed interventions I_micro and a map omega to
  I_macro.
- **Identifiability:** Not a learning theory. It defines when a (phi, f) pair is *correct*, which is exactly the target.
- **Intervention support:** Central. Validity is always *relative to an intervention set*. (3) held-out intervention types
  = checking commutation on interventions outside the training set.
- **Nonlinear capacity:** Agnostic.
- **Interpretability:** Defines what the macro variables "mean" causally.
- **Scaling:** Exact checks need all interventions. In practice, sample interventions and estimate the error (see CAE).
- **Failure modes:** Choice of distance and intervention distribution drives the result. Abstraction may hold only for a
  restricted intervention set; that is fine as long as it is stated explicitly. With continuous states, exact abstraction
  essentially never holds; use approximate errors and horizons.
- **Relevance:** Supplies the **definitions** for (3) (commutation under interventions), (4) (tau is many-to-one;
  microstates in the same fibre must have equal macro futures), (7) (two micro models abstract to the *same* macro model;
  compositionality bounds errors along chains), and (8) (abstain when minimal approximate-abstraction error exceeds a
  threshold). The Rubenstein time-series-to-equilibrium example also covers temporal abstraction (dt coarsening).
- **Open-source implementations:** FMZennaro/CausalAbstraction - https://github.com/FMZennaro/CausalAbstraction (seen in
  search results only; not opened; licence not verified).
- **From-scratch simplicity:** Simple to compute errors given tau/omega and a simulator. Learning tau is the hard part.
- **References:**
  - Rubenstein, P. K., Weichwald, S., Bongers, S., et al. (2017). Causal Consistency of Structural Equation Models. UAI 2017. https://arxiv.org/abs/1707.00819 [read-abstract]
  - Beckers, S., Halpern, J. Y. (2019). Abstracting Causal Models. AAAI 2019. https://arxiv.org/abs/1812.03789 [read-abstract]
  - Beckers, S., Eberhardt, F., Halpern, J. Y. (2019). Approximate Causal Abstraction. UAI 2019. https://arxiv.org/abs/1906.11583 [read-abstract]
  - Rischel, E. F., Weichwald, S. (2021). Compositional abstraction error and a category of causal models. UAI 2021, PMLR 161. https://proceedings.mlr.press/v161/rischel21a.html [read-abstract]
  - Otsuka, J., Saigo, H. (2022). On the Equivalence of Causal Models: A Category-Theoretic Approach. CLeaR 2022. https://arxiv.org/abs/2201.06981 [read-abstract]
  - Zennaro, F. M., Turrini, P., Damoulas, T. (2023). Quantifying Consistency and Information Loss for Causal Abstraction Learning. IJCAI 2023. https://arxiv.org/abs/2305.04357 [read-abstract]

### Causal feature learning (CFL: macro-variables from micro-variables)
- **Core idea:** Partition micro-states of a cause X into macro-states such that all micro-states in a cell have the same
  interventional effect distribution P(Y | do(x)) (the "causal partition"). The Causal Coarsening Theorem says the
  observational partition (by P(Y|x)) generically refines the causal partition. So one first learns the observational
  partition (cheap), then merges cells with a few targeted interventions. Links to computational mechanics (causal states).
- **Assumptions:** Discrete or clusterable effect distributions. Generic (measure-one) parameters. Ability to intervene to set
  micro-states.
- **Identifiability:** The macro-variable as an equivalence class (partition) of micro-states, which is coordinate-free. No
  coordinate gauge is needed.
- **Intervention support:** Explicit. An active learning algorithm chooses manipulations with minimal experimental effort.
- **Nonlinear capacity:** Arbitrary (clustering in conditional-distribution space).
- **Interpretability:** High: macro-states are named clusters.
- **Scaling:** Density or conditional estimation over high-dimensional X; clustering. Continuous macro-variables are awkward.
- **Failure modes:** Continuous-valued macro states (population dynamics) do not form discrete cells. Estimating the
  conditional distributions in high dimension. Static cause-effect setting (the dynamical extension is via the
  causal-states literature).
- **Relevance:** Provides the operational definition of (4) microstate-invariance: **equal z implies equal interventional
  futures**. The "observational partition refines the causal partition" idea gives a workflow: learn a predictive state
  (observational), then test and merge with interventions. That supports (5) and (3).
- **Open-source implementations:** Not checked (an eberharf/cfl package exists; unverified; licence not verified).
- **From-scratch simplicity:** Moderate.
- **References:**
  - Chalupka, K., Perona, P., Eberhardt, F. (2015). Visual Causal Feature Learning. UAI 2015. https://arxiv.org/abs/1412.2309 [read-abstract]
  - Chalupka, K., Eberhardt, F., Perona, P. (2017). Causal feature learning: an overview. Behaviormetrika 44(1):137-164. https://authors.library.caltech.edu/77825/ [read-abstract]

### Interchange interventions, IIT, DAS, and the Causal Abstraction Error benchmark
- **Core idea:** To test whether a high-level variable V is realised by a low-level representation R, run a *base* input,
  replace R with its value from a *source* input (interchange intervention), and check that the low-level output equals the
  high-level model's counterfactual output with V set to its source value. Four uses:
  - Evaluation: Geiger et al. 2021, via **interchange intervention accuracy, IIA**.
  - Training: **Interchange Intervention Training, IIT**. Differentiable; zero loss implies the high-level model is a causal
    abstraction of the neural model.
  - **Distributed Alignment Search, DAS**: learns a rotation of the representation space by gradient descent, so that V is
    aligned with a linear *subspace* rather than a set of units.
  - Theory: extended to arbitrary mechanism transformations (Geiger et al. 2023/2025).
- **Assumptions:** A candidate high-level causal model and alignment. The low-level system must be interventionable on
  internal states (our simulator is). DAS assumes linearly encoded (subspace) variables.
- **Identifiability:** Not an identifiability theory. DAS finds *an* alignment and can find spurious ones (an overfitting
  concern). Méloux et al. 2026: "Even perfect IIA ... does not certify causal abstraction in the general sense, since
  intermediate variables may still violate consistency."
- **Intervention support:** Core. **CAE benchmark** (Méloux et al. 2026, [read-full]):
  - Across ten simulated complex systems (particle, spin, agent-based, logic circuits, a processor, and more) with
    known ground-truth abstractions, over thirty validity metrics were compared.
  - Only causal-abstraction metrics reliably separated valid from invalid explanations.
  - The proposed **Causal Abstraction Error (CAE)** includes **faithfulness testing**: interventions on *unmapped*
    micro-variables, which are overwritten with noise to check they do not matter. It detected all six planted failure modes:
    hidden confounder, backup path through unmapped variables, wrong intermediate variable, spurious mediator, unreachable
    macro states, and wrong causal direction.
  - Statistical power reached 95% within about 30 interventions for most systems.
  - Definitions: instance error IAE = D( macro(Y | tau_U(u), do(nu)), tau_Y( micro(a^{-1}(Y) | u, do(mu)) ) ).
    **CAE-down** samples macro interventions nu (random cardinality, random subset, values uniform over range) and grounds
    them via tau^{-1}. **CAE-up** samples micro interventions and lifts them via tau.
  - That paper also evaluates a "dynamic causal consistency" metric inspired by epsilon-machines.
- **Nonlinear capacity:** IIT and DAS apply to arbitrary networks. DAS is linear-subspace; nonlinear variants exist
  (unverified).
- **Interpretability:** High; it tests specific variable-to-subspace hypotheses.
- **Scaling:** Each interchange needs two forward passes (or simulator runs). DAS training is cheap for moderate hidden size.
- **Failure modes:** IIA checks only outputs. For continuous systems, "accuracy" must become an error metric. Realising a
  macro value in the micro system needs a realiser map tau^{-1}, which is non-unique; different realisers can give different
  results, and that difference is itself the test of (4). Expressive nonlinear alignments can "find" abstractions in random
  systems (unverified concern from the interpretability literature).
- **Relevance:** Supplies the **evaluation protocol for (3), (4), (7)** and a **training signal** (IIT loss on
  simulator-generated counterfactual pairs). See the recipe below.
- **Open-source implementations:**
  - pyvene - https://github.com/stanfordnlp/pyvene - active (push 2026-03), ~900 stars - Apache-2.0 [repo/docs]. Built for
    PyTorch modules; our simulator would need a PyTorch wrapper, or the logic can be reimplemented.
  - CAE - https://github.com/MelouxM/CAE - new (2026-06), ~2 stars - GitHub reports MIT (the repo describes itself as
    website code; a PyPI package causal-abstraction-eval is referenced but the PyPI page failed to load, so the package was
    not checked; the paper page states CC BY-SA 4.0 for the paper) [repo/docs]
- **From-scratch simplicity:** Simple for the evaluation (a dozen lines around the simulator). IIT and DAS are moderate.
- **References:**
  - Geiger, A., Lu, H., Icard, T., Potts, C. (2021). Causal Abstractions of Neural Networks. NeurIPS 2021. https://arxiv.org/abs/2106.02997 [read-abstract]
  - Geiger, A., Wu, Z., Lu, H., et al. (2022). Inducing Causal Structure for Interpretable Neural Networks (IIT). ICML 2022 (venue unverified; arXiv page read). https://arxiv.org/abs/2112.00826 [read-abstract]
  - Geiger, A., Wu, Z., Potts, C., Icard, T., Goodman, N. D. (2024). Finding Alignments Between Interpretable Causal Variables and Distributed Neural Representations (DAS). CLeaR 2024 (venue unverified). https://arxiv.org/abs/2303.02536 [read-abstract]
  - Geiger, A., et al. (2023-2025). Causal Abstraction: A Theoretical Foundation for Mechanistic Interpretability. arXiv (JMLR version unverified). https://arxiv.org/abs/2301.04709 [read-abstract]
  - Wu, Z., Geiger, A., Arora, A., et al. (2024). pyvene: A Library for Understanding and Improving PyTorch Models via Interventions. arXiv / NAACL demo (venue unverified). https://arxiv.org/abs/2403.07809 [read-abstract]
  - Meloux, M., Pimentel, T., Portet, F., Peyrard, M. (2026). Validating Causal Abstraction Metrics on Simulated Complex Systems. arXiv (ICML 2026 MI workshop per repo). https://arxiv.org/html/2607.00267v1 [read-full: definitions, sampling, failure modes]

### Causal models of dynamical systems (dynamic SCMs from ODEs; SDCMs; equilibrium and cyclic SCMs)
- **Core idea:** Rubenstein et al. 2018: the asymptotic behaviour of a deterministic ODE under **time-varying** interventions
  can be represented by a dynamic SCM whose variables are whole trajectories. Bongers, Blom & Mooij: Structural Dynamical
  Causal Models (random differential equations), with conditions under which they **equilibrate** to (possibly cyclic) SCMs.
  This tells us when equilibrium causal semantics is legitimate.
- **Assumptions:** Stable (convergent) dynamics for the equilibrium results. Interventions on the ODE (clamping variables,
  changing parameters) map to SCM interventions.
- **Identifiability:** Not about learning; about the correctness of the abstraction from ODE to SCM.
- **Intervention support:** Defines how micro (ODE-level) interventions become macro (SCM-level) ones, i.e. the omega map
  for temporal abstraction.
- **Nonlinear capacity:** General ODEs/RDEs.
- **Interpretability:** Formal.
- **Scaling:** Not applicable.
- **Failure modes:** Non-convergent dynamics (limit cycles, chaos) do not equilibrate. The equilibrium SCM loses transient
  information, so it is a poor abstraction for (1) at short horizons.
- **Relevance:** Formal basis for temporal abstraction (dt coarsening) and for checking that macro f is causally consistent
  with the micro ODE. It warns that steady-state abstractions fail for transient-response prediction.
- **Open-source implementations:** None (theory).
- **From-scratch simplicity:** Not applicable.
- **References:**
  - Rubenstein, P. K., Bongers, S., Scholkopf, B., Mooij, J. M. (2018). From Deterministic ODEs to Dynamic Structural Causal Models. UAI 2018. https://arxiv.org/abs/1608.08028 [read-abstract]
  - Bongers, S., Blom, T., Mooij, J. M. (2018/2022). Causal Modeling of Dynamical Systems. arXiv. https://arxiv.org/abs/1803.08784 [read-abstract]

### Time-series causal discovery as system-ID tools under interventions (Granger, PCMCI, J-PCMCI+, JCI, causal-learn)
- **Core idea:**
  - Granger causality: lagged predictive improvement.
  - PCMCI: PC-style condition selection followed by momentary conditional independence (MCI) tests, giving lagged causal
    graphs in high-dimensional nonlinear time series with controlled false positives.
  - J-PCMCI+: multiple datasets and contexts, with observed or dummy context variables.
  - Joint Causal Inference (JCI): pool data from multiple contexts by adding context variables as exogenous nodes. It
    accommodates perfect, imperfect and stochastic interventions **with unknown targets**, and many existing algorithms
    become special cases.
- **Assumptions:** Causal sufficiency (or latent-aware variants), faithfulness, stationarity per context, and a correct CI
  test (partial correlation, GPDC, CMI-knn, etc.).
- **Identifiability:** Lagged graph up to a Markov equivalence class (contemporaneous edges may stay unoriented). JCI with
  context variables can orient more.
- **Intervention support:** JCI and J-PCMCI+ treat intervention regimes as context nodes. Predicting held-out intervention
  *effects* needs a fitted SCM on top.
- **Nonlinear capacity:** Depends on the CI test (nonlinear tests are expensive).
- **Interpretability:** High (graph).
- **Scaling:** PCMCI scales to hundreds of variables with a linear CI test; nonlinear CMI tests are expensive (O(T^2)-ish;
  unverified). Micro level at N ~ 5,000 is impractical. Use it on **candidate macro variables z** (k small).
- **Failure modes:** Deterministic or near-deterministic dynamics violate faithfulness (CI tests break). Coarse sampling
  creates contemporaneous links. Unobserved micro-states confound macro variables, which is exactly the non-closure we want
  to detect.
- **Relevance:** (2) Markov closure test for z: after conditioning on z_t and u_t, no lagged dependence on z_{t-2..}, y history
  or unused micro projections should remain. PCMCI with z plus "leak probes" (e.g. random micro projections) flags
  non-closure. (3) JCI-style pooling of intervention regimes. Also a baseline for "graph among macro variables".
- **Open-source implementations:**
  - tigramite - https://github.com/jakobrunge/tigramite - active (push 2026-01), ~1.7k stars - GPL-3.0 [repo/docs]. Note:
    GPL is copyleft; check compatibility before bundling.
  - causal-learn - https://github.com/py-why/causal-learn - active (push 2026-09), ~1.7k stars - MIT [repo/docs]. Includes
    Granger, PC/FCI, GES and CD-NOD for heterogeneous/nonstationary data (the algorithm list is from memory; unverified).
  - J-PCMCI+ tutorial in tigramite (seen in search results only).
- **From-scratch simplicity:** Granger/VAR tests are simple. PCMCI is moderate; use tigramite.
- **References:**
  - Runge, J., Nowack, P., Kretschmer, M., et al. (2019). Detecting and quantifying causal associations in large nonlinear time series datasets. Science Advances 5(11). https://arxiv.org/abs/1702.07007 [read-abstract]
  - Mooij, J. M., Magliacane, S., Claassen, T. (2020). Joint Causal Inference from Multiple Contexts. JMLR 2020. https://arxiv.org/abs/1611.10351 [read-abstract]
  - Gunther, W., Ninad, U., Runge, J. (2023). Causal discovery for time series from multiple datasets with latent contexts. UAI 2023, PMLR 216. https://arxiv.org/pdf/2306.12896 (seen in search results only) [unverified]
  - Granger, C. W. J. (1969). Investigating causal relations by econometric models and cross-spectral methods. Econometrica. [unverified]

---

## F. Population-dynamics latent models and comparing latent spaces

_Source notes: `notes\area_F_popdyn_similarity.md`._

Scope: methods only. Experimental data used in the cited papers are deliberately not described.
Citation tags follow notes/TEMPLATE.md. "(unverified)" marks claims not confirmed in a source opened during this review.
Where a WebFetch summary of a PDF looked unreliable, only the parts consistent with the abstract are used and the rest is marked.

---

### Latent Factor Analysis via Dynamical Systems (LFADS; AutoLFADS; lfads-torch)
- **Core idea:** Sequential VAE. A bidirectional RNN encoder infers a per-trial initial condition g0 and (optionally) a
  time-varying inferred input u(t) via a controller RNN; a generator RNN evolves the latent state from g0 driven by u(t);
  low-dimensional factors are a linear readout of the generator state; rates are a (Poisson or other) readout of the factors.
  AutoLFADS adds coordinated dropout (masked input elements whose loss gradients are blocked, to stop identity copying) and
  population-based training (PBT) of hyperparameters.
- **Assumptions:** Observations are noisy emissions of a low-dimensional autonomous dynamical system plus sparse/low-power
  inferred inputs; trials of fixed length; conditionally independent emissions given factors.
- **Identifiability:** Factors identifiable only up to an invertible (in practice roughly affine) transform; generator state is
  over-parameterised (e.g. 100-200 units) so the dynamics f are not unique. Split between "dynamics" and "inferred inputs" is not
  identified: a strong enough controller can explain everything as input. Priors on u (autoregressive, KL weight) set the split.
- **Intervention support:** Known inputs can be fed to the encoder/generator (supported in lfads-torch configs, unverified detail);
  inferred inputs are an estimate of unmodelled drive, not a causal intervention model. Nothing in the method predicts
  held-out microscopic interventions; the generator could be rolled out with a perturbed state, but this is untested extrapolation.
- **Nonlinear capacity:** High (GRU generator).
- **Interpretability:** Low for f (black-box GRU); factors can be analysed post hoc (e.g. fixed points of the generator).
- **Scaling:** O(T * H^2) per trial for GRU size H; fine for N up to thousands; needs many trials (hundreds+) and heavy
  hyperparameter tuning (hence AutoLFADS/PBT, which is compute-intensive, tens of parallel models).
- **Failure modes:** Identity/copy solutions without coordinated dropout; inferred inputs absorbing dynamics; poor
  extrapolation outside the trial distribution; sensitivity to KL/L2 weights; latent dimension is a hyperparameter.
- **Relevance (props 1-8):** (1) strong on smoothing/denoising and within-trial prediction; (2) generator state is Markov by
  construction, but factors are not closed if inputs are inferred from the future (encoder is bidirectional = future leakage
  if used for forecasting); (3) weak; (5) not minimal by design; (6) seeds give different f, need alignment metrics; (7) multi-session
  "PCR initialisation" (per-session linear read-in/read-out, shared generator) is a direct template for implementation-specific
  encoders with one shared f.
- **Open-source implementations:** lfads-torch - https://github.com/arsedler9/lfads-torch - active, ~140 stars - custom
  Emory/Georgia Tech research licence (non-commercial research use; restricts modification/distribution per LICENSE summary;
  check before reuse). Original TF implementation - licence not verified.
- **From-scratch simplicity:** Moderate. The model is ~300 lines in PyTorch; the hard parts are the regularisers (coordinated
  dropout, KL ramping, AR prior on inputs) and hyperparameter search.
- **References:**
  - Sussillo D., Jozefowicz R., Abbott L.F., Pandarinath C. (2016). LFADS - Latent Factor Analysis via Dynamical Systems. arXiv. https://arxiv.org/abs/1608.06315 [read-abstract]
  - Pandarinath C. et al. (2018). Inferring single-trial neural population dynamics using sequential auto-encoders. Nature Methods. [unverified]
  - Keshtkaran M.R., Sedler A.R., et al. (2022). A large-scale neural network training framework for generalized estimation of single-trial population dynamics. Nature Methods. https://www.nature.com/articles/s41592-022-01675-0 [unverified] (coordinated dropout + PBT description taken from search-result snippets only)
  - Sedler A.R., Pandarinath C. (2023). lfads-torch: A modular and extensible implementation of latent factor analysis via dynamical systems. arXiv. https://arxiv.org/abs/2309.01230 [read-abstract]
  - lfads-torch repo and LICENSE. https://github.com/arsedler9/lfads-torch [repo/docs]

### Neural Data Transformers (NDT, STNDT) - brief
- **Core idea:** Replace the RNN sequential VAE with a non-recurrent transformer trained by masked reconstruction of binned
  activity (BERT-style). STNDT adds attention across units (spatial) as well as time, and a contrastive loss on augmented views.
- **Assumptions:** None about dynamics; purely a denoising/imputation model.
- **Identifiability:** None; no explicit latent state or transition law.
- **Intervention support:** None.
- **Nonlinear capacity:** High.
- **Interpretability:** Low (attention maps only).
- **Scaling:** Parallel over time (fast inference); O(T^2) attention; STNDT adds O(N^2) spatial attention.
- **Failure modes:** No closed Markov state; bidirectional attention leaks future into "state".
- **Relevance:** Useful only as a strong predictive/denoising baseline for (1); fails (2), (4), (5) by construction. The
  "explicit dynamics may not be needed for smoothing" result is a warning: denoising accuracy does not validate a state.
- **Open-source implementations:** neural-data-transformers - https://github.com/snel-repo/neural-data-transformers - archival, ~90 stars - Unlicense. STNDT code - licence not verified.
- **From-scratch simplicity:** Simple (standard transformer encoder + masking).
- **References:**
  - Ye J., Pandarinath C. (2021). Representation learning for neural population activity with Neural Data Transformers. arXiv. https://arxiv.org/abs/2108.01210 [read-abstract]
  - Le T., Shlizerman E. (2022). STNDT: Modeling Neural Population Activity with Spatiotemporal Transformers. NeurIPS 2022. https://arxiv.org/abs/2206.04727 [read-abstract]
  - NDT repo. https://github.com/snel-repo/neural-data-transformers [repo/docs]

### iLQR-VAE (control-based inference of input-driven dynamics)
- **Core idea:** Input-driven sequential VAE z_{t+1} = f_theta(z_t, u_t), observations h(C z_t + b) (Gaussian or Poisson).
  The recognition model is not a separate encoder: the posterior mean of the inputs u is obtained by solving a nonlinear
  optimal-control problem with iLQR (log-likelihood of observations as running cost, log p(u) as control cost); the
  posterior covariance is a shared separable (Kronecker spatial x temporal) Gaussian. Gradients flow through the iLQR
  solution by implicit differentiation (memory independent of iteration count). Input priors: Gaussian, or hierarchical
  Student-t for sparse/heavy-tailed inputs.
- **Assumptions:** Known latent/input dimension; dynamics family (linear or GRU); unimodal posterior near the MAP.
- **Identifiability:** Same dynamics-vs-input ambiguity as LFADS, but controlled through the explicit input prior; latent
  coordinates up to invertible transforms.
- **Intervention support:** Treats unobserved drive explicitly as control inputs, which is conceptually closest to
  "inputs as interventions"; known inputs can be included. Held-out intervention prediction not studied (unverified).
- **Nonlinear capacity:** Moderate-high (GRU dynamics).
- **Interpretability:** Moderate; inferred inputs are explicit and sparse under Student-t prior.
- **Scaling:** Per iLQR solve O(T (n^3 + n^2 n_o)), n = latent dim, n_o = observation dim; iterative so slower than amortised encoders; far fewer parameters than LFADS.
- **Failure modes:** Local optima of MAP control; shared posterior covariance; long sequences need chunking.
- **Relevance:** (1)(2) latent state is Markov given inputs; (3) the only method in this area where "input" is a first-class
  inferred quantity; useful for separating simulator-imposed u(t) from intrinsic dynamics; (5) small n by design.
- **Open-source implementations:** Code release location not found in the opened sources (licence not verified).
- **From-scratch simplicity:** Hard (differentiable iLQR; could reuse differentiable MPC libraries).
- **References:**
  - Schimel M., Kao T.-C., Jensen K.T., Hennequin G. (2022). iLQR-VAE: control-based learning of input-driven dynamics with applications to neural data. ICLR 2022. https://www.biorxiv.org/content/10.1101/2021.10.07.463540v1 [read-full] (method sections via fetch)

### Gaussian-Process Factor Analysis (GPFA) and DLAG
- **Core idea:** y_t = C x_t + d + e, e ~ N(0, R) diagonal; each latent dimension x_j(.) has an independent GP prior over time
  (squared-exponential kernel, learned timescale). Unifies smoothing and dimensionality reduction; fit by EM; latents
  orthonormalised post hoc (SVD of C) for ordering. DLAG extends to two or more groups of units with across-group latents that
  have learned time delays plus within-group latents, fit by EM with cross-validated dimensionalities; a frequency-domain
  variant speeds fitting.
- **Assumptions:** Linear-Gaussian emissions (after square-root transform of counts in practice), stationary GP per latent,
  no explicit dynamics or inputs.
- **Identifiability:** Up to invertible linear transform of x (rotation plus per-dimension scaling fixed by the GP prior);
  orthonormalisation picks a canonical basis. DLAG delays are identifiable up to sign conventions.
- **Intervention support:** None; no transition law, so cannot predict perturbation effects.
- **Nonlinear capacity:** None (linear emissions, GP smoothing only).
- **Interpretability:** High.
- **Scaling:** Exact GP inference O(q^3 T^3) per trial (q latents) unless using structure; fine for T of a few hundred bins.
- **Failure modes:** Nonlinear manifolds inflate dimension; not a dynamical model so no Markov state.
- **Relevance:** Baseline for (5) dimension (cross-validated leave-unit-out prediction) and as a smoothing front end; fails (2)(3).
  DLAG's delayed shared latents are a methodological analogue of implementation-to-implementation shared latents (7).
- **Open-source implementations:** Elephant `elephant.gpfa` (Python port of original MATLAB) - https://elephant.readthedocs.io/en/latest/reference/gpfa.html - active - BSD-3-Clause. DLAG - https://github.com/egokcen/DLAG - MATLAB, ~40 stars - MIT.
- **From-scratch simplicity:** Moderate (EM with GP kernel hyperparameter gradients; numerical care with Toeplitz covariances).
- **References:**
  - Yu B.M., Cunningham J.P., Santhanam G., et al. (2008). Gaussian-process factor analysis for low-dimensional single-trial analysis of neural population activity. NeurIPS 21. https://proceedings.neurips.cc/paper/2008/hash/ad972f10e0800b49d76fed33a21f6698-Abstract.html [read-abstract] (J. Neurophysiol. 2009 version not opened)
  - Elephant GPFA docs and LICENSE.txt. [repo/docs]
  - Gokcen E., et al. (2022). Disentangling the flow of signals between populations of neurons. Nature Computational Science. https://github.com/egokcen/DLAG [repo/docs] (paper itself not opened: [unverified])

### Latent linear dynamical systems with count likelihoods (PLDS, PfLDS/fLDS, vLGP)
- **Core idea:** PLDS: x_{t+1} = A x_t + B u_t + w_t, y_t ~ Poisson(exp(C x_t + d)); fit with Laplace/variational EM (unverified detail).
  fLDS/PfLDS: linear latent dynamics but emission rate an arbitrary smooth (neural-network) function of x, with a structured
  variational posterior. vLGP: GP smoothness prior on latents with a history-dependent point-process likelihood, variational inference.
- **Assumptions:** Linear Gaussian latent dynamics (PLDS, fLDS); vLGP has no dynamics, only smoothness.
- **Identifiability:** PLDS: (A, B, C) up to similarity transform x -> T x (classic LDS). fLDS: nonlinear emission removes
  linear-transform identifiability guarantees; latent recovered only up to (at least) invertible linear maps, possibly more.
- **Intervention support:** PLDS/LDS with B u_t supports known inputs and state-offset interventions naturally (linear
  superposition); prediction of connection removals impossible (no microscopic parameters).
- **Nonlinear capacity:** PLDS none; fLDS nonlinear emissions only; vLGP none in dynamics.
- **Interpretability:** High (eigenvalues of A are time constants/rotations).
- **Scaling:** Kalman/Laplace inference O(T k^3); cheap.
- **Failure modes:** Linear dynamics cannot represent multistability or limit cycles; fLDS trades interpretability for fit.
  The original comparison found latent-dynamics models beat coupled GLMs, but gains of Poisson over Gaussian noise were small.
- **Relevance:** Core baseline "latent LDS with inputs" for (1)(2)(3)(5); fLDS is the nonlinear-embedding/linear-dynamics
  compromise, i.e. a probabilistic cousin of "autoencoder + linear latent dynamics".
- **Open-source implementations:** dynamax (JAX; LGSSM, nonlinear/generalised Gaussian SSMs, HMMs; EM, SGD, HMC/SMC) - https://github.com/probml/dynamax - active, ~1k stars - MIT. ssm (Linderman lab; LDS incl. Poisson emissions, SLDS, rSLDS; Laplace-EM, SVI) - https://github.com/lindermanlab/ssm - ~700 stars, maintenance slowed pending JAX refactor - MIT.
- **From-scratch simplicity:** Simple for Gaussian LDS (Kalman smoother + EM); moderate for Poisson (Laplace/variational E-step).
- **References:**
  - Macke J.H., Buesing L., Cunningham J.P., et al. (2011). Empirical models of spiking in neural populations. NeurIPS 24. https://proceedings.neurips.cc/paper/2011/hash/7143d7fbadfa4693b9eec507d9d37443-Abstract.html [read-abstract]
  - Gao Y., Archer E., Paninski L., Cunningham J.P. (2016). Linear dynamical neural population models through nonlinear embeddings. NeurIPS 2016. https://arxiv.org/abs/1605.08454 [read-abstract]
  - Zhao Y., Park I.M. (2017). Variational latent Gaussian process for recovering single-trial dynamics from population spike trains. Neural Computation. https://arxiv.org/abs/1604.03053 [read-abstract]
  - dynamax repo; ssm repo. [repo/docs]

### Fixed-point / slow-point linearisation analysis of trained RNNs (FixedPointFinder)
- **Core idea:** For a trained RNN x' = F(x, u) (or x_{t+1} = F(x_t, u)), minimise q(x) = 1/2 |F(x) - x|^2 (discrete) or
  1/2 |F(x)|^2 (continuous) from many initial conditions sampled on visited trajectories, with the input held at a constant
  value. Minima with q = 0 are fixed points, small non-zero q are slow points. Linearise (Jacobian) there; eigen-decomposition gives
  stable/unstable/slow modes, line attractors, saddles.
- **Assumptions:** Differentiable model; computation governed by structure near the visited manifold; inputs piecewise constant.
- **Identifiability:** Topological features (number/type of fixed points, Jacobian spectra) are invariant to smooth coordinate
  changes, so they are a natural "up to conjugacy" descriptor; eigenvalues are invariant under similarity transforms.
- **Intervention support:** Jacobians predict the linear response to small state offsets near fixed points; input-conditional
  fixed-point families show how u reshapes the flow. Large perturbations are not covered.
- **Nonlinear capacity:** Analysis tool; captures local linear structure around many points (piecewise-linear skeleton).
- **Interpretability:** High; this is the classic reverse-engineering tool.
- **Scaling:** Each optimisation is cheap (autodiff); Jacobian eigendecomposition O(H^3) per point; thousands of starts are routine.
- **Failure modes:** Misses fixed points in unvisited regions; slow-point threshold is arbitrary; spurious/duplicate points
  need deduplication; limit cycles and chaotic sets are not captured; results differ across seeds even when behaviour matches.
- **Relevance:** Converts any learned f (from LFADS, RSSM, latent ODE) into a comparable dynamical skeleton; supports (6)(7)
  via comparing fixed-point counts/types and Jacobian spectra across seeds or implementations; supports (8) as a diagnostic
  (no low-dimensional slow manifold => no compact description).
- **Open-source implementations:** fixed-point-finder - https://github.com/mattgolub/fixed-point-finder - maintained, ~110 stars - Apache-2.0; supports PyTorch (nn.RNN/GRU/LSTM) and TensorFlow; test suite noted as needing updates.
- **From-scratch simplicity:** Simple (tens of lines with autograd); pitfalls: learning-rate schedules, tolerance, deduplication, excluding outliers far from data.
- **References:**
  - Sussillo D., Barak O. (2013). Opening the black box: low-dimensional dynamics in high-dimensional recurrent neural networks. Neural Computation 25(3):626-649. https://web.stanford.edu/class/cs379c/archive/2016/calendar_invited_talks/articles/SussilloandBarakNC-13.pdf [read-full] (via fetch summary)
  - Golub M.D., Sussillo D. (2018). FixedPointFinder: A Tensorflow toolbox for identifying and characterizing fixed points in recurrent neural networks. JOSS 3(31):1003. https://joss.theoj.org/papers/10.21105/joss.01003 [read-abstract]
  - fixed-point-finder repo. [repo/docs]

### Low-rank RNNs as minimal-rank dynamical models (Mastrogiuseppe & Ostojic; Dubreuil et al.; LINT; stochastic low-rank RNNs)
- **Core idea:** Connectivity J = (1/N) sum_{r=1..R} m_r n_r^T (+ optional random part). Then the network state lies in the
  span of {m_r} plus input vectors, and the dynamics reduce to an R(+inputs)-dimensional latent system
  kappa' = -kappa + <n, phi(m kappa + I u)>, with mean-field theory relating connectivity statistics to dynamics. LINT
  (Valente et al. 2022) fits a rank-R RNN to recorded trajectories and selects R by where prediction quality stops improving;
  the fitted model yields a reduced latent dynamical system, dimensionality-reduction axes, and predictions for silencing
  subsets of units (by lesioning the fitted model). Pals et al. (2024) fit stochastic low-rank RNNs as latent-variable models
  with variational sequential Monte Carlo and show all fixed points of piecewise-linear low-rank RNNs can be found in
  polynomial rather than exponential time. Valente, Ostojic, Pillow (2021) show linear RNNs map to latent LDS with latent
  dimension up to 2x rank, while general latent LDS do not map to low-rank RNNs (non-Markovianity in observed space).
- **Assumptions:** Observed units are the network units (or a linear readout of them); rate dynamics with known nonlinearity.
- **Identifiability:** Latent dynamics identifiable up to invertible linear maps of the rank-R subspace; the connectivity
  factors (m, n) are not unique (similar dynamics from different connectivity; stated by the authors).
- **Intervention support:** Strong for the problem here: the model lives in unit space, so input currents into units,
  state offsets and removing units map directly onto model operations; latent dynamics then predict the intervention's effect.
  Connection removal is representable only if the removed connection is part of the low-rank structure (unverified in general).
- **Nonlinear capacity:** Moderate; rank-R with nonlinearity supports multistability, limit cycles, gating by inputs.
- **Interpretability:** High (low-dimensional latent ODE with explicit input directions; populations via Gaussian mixture on loadings).
- **Scaling:** Parameters O(N R); training by BPTT; easy for N ~ 10^3; SMC variant more expensive.
- **Failure modes:** Only fits if the true system is close to low-rank; rank sweep may plateau ambiguously; non-unique connectivity; deterministic version ignores noise.
- **Relevance:** Very relevant to (3)(5)(7): directly gives phi (projection onto m-space), f (reduced ODE) and a microscopic model
  on which held-out interventions can be simulated; rank = k gives a clean minimality sweep; different implementations can
  share the reduced f while having different m, n.
- **Open-source implementations:** lowrank_inference (LINT) - https://github.com/adrian-valente/lowrank_inference - ~20 stars, research code - licence not verified (LICENSE file present, type not read). populations_paper_code (low_rank_rnns library) - https://github.com/adrian-valente/populations_paper_code - ~35 stars - licence not verified. smc_rnns - https://github.com/mackelab/smc_rnns - ~27 stars - Apache-2.0. Also fmastrogiuseppe/LowRank (licence not verified).
- **From-scratch simplicity:** Simple for deterministic LINT (parameterise J = M N^T / N, BPTT, MSE); moderate for SMC variant.
- **References:**
  - Mastrogiuseppe F., Ostojic S. (2018). Linking connectivity, dynamics and computations in low-rank recurrent neural networks. Neuron. https://arxiv.org/abs/1711.09672 [read-abstract]
  - Dubreuil A., Valente A., Beiran M., et al. (2022). The role of population structure in computations through neural dynamics. Nature Neuroscience. [unverified] (only repo opened)
  - Valente A., Pillow J.W., Ostojic S. (2022). Extracting computational mechanisms from neural data using low-rank RNNs. NeurIPS 35. https://proceedings.neurips.cc/paper_files/paper/2022/hash/9877d915a4b4f00e85e7b4cfdf41e450-Abstract-Conference.html [read-abstract] (PDF fetch summary used only where consistent with abstract)
  - Valente A., Ostojic S., Pillow J.W. (2021). Probing the relationship between linear dynamical systems and low-rank recurrent neural network models. arXiv. https://arxiv.org/abs/2110.09804 [read-abstract]
  - Pals M., Sagtekin A.E., Pei F., et al. (2024). Inferring stochastic low-rank recurrent neural networks from neural data. NeurIPS 2024. https://arxiv.org/abs/2406.16749 [read-abstract]
  - Repos above. [repo/docs]

### Dynamical Similarity Analysis (DSA) and follow-ups (InputDSA, fastDSA)
- **Core idea:** For each system: delay-embed observations (Hankel matrix, HAVOK-style), optionally reduce rank by SVD, fit a
  linear operator A by DMD in the delay space (a finite Koopman approximation). Compare two systems by
  d(A_x, A_y) = min_{C in O(n)} ||A_x - C A_y C^T||_F ("Procrustes over vector fields"): similarity up to orthogonal change of
  basis, applied to the operators rather than the states. InputDSA uses a subspace-identification variant of DMD with control
  (Subspace DMDc) to estimate separate intrinsic (A) and input (B) operators and compares both, can use surrogate inputs when
  true inputs are unknown, and adds a much faster optimiser. fastDSA uses random-matrix theory for rank selection, faster
  alignment pipelines, and Koopman embeddings.
- **Assumptions:** Stationary dynamics well-approximated by a linear operator in delay space; enough data for DMD; both
  systems embedded at equal rank; alignment restricted to orthogonal (plus in some variants other groups).
- **Identifiability:** Invariant to orthogonal transforms of the delay-embedded latent space; sensitive to time step, delay count, rank.
- **Intervention support:** DSA none; InputDSA separates input-driven from intrinsic operators (DMDc), which is the relevant
  variant when u(t) differs across implementations.
- **Nonlinear capacity:** Through delay/Koopman lifting only; comparison itself is linear-operator based.
- **Interpretability:** Moderate (eigenvalues of A).
- **Scaling:** DMD cheap (SVD of Hankel matrix); Procrustes-over-vector-fields is a non-convex optimisation over O(n) (the original
  was slow; fastDSA/InputDSA claim orders-of-magnitude speedups).
- **Failure modes (critical):** Godara et al. (2026) argue orthogonal alignment is both insufficient (topologically conjugate
  systems can require non-orthogonal basis changes, so DSA calls them different) and overstated (non-conjugate systems can
  have orthogonally equivalent finite Koopman operators, so DSA calls them similar). Also depends strongly on delay/rank hyperparameters
  and on autonomous-vs-driven regimes (fixed by InputDSA). Positive evidence: DSA distinguished conjugate from non-conjugate RNNs where
  geometric measures failed, and was reported more noise-robust than Procrustes/CKA in a compositional-RNN benchmark (Guilhot et al.).
- **Relevance:** (6)(7): a principled dynamics-level comparison of learned f across seeds/implementations, beyond state geometry;
  use InputDSA when inputs matter. Treat as one of several measures, not a certificate of conjugacy.
- **Open-source implementations:** DSA (dsa-metric on PyPI) - https://github.com/mitchellostrow/DSA - active, ~100 stars - MIT; includes GeneralizedDSA, InputDSA, PyKoopman/PyDMD back-ends, GPU.
- **From-scratch simplicity:** Moderate (Hankel DMD is simple; the orthogonal-alignment optimisation needs care: parameterise via Cayley/matrix exponential, multiple restarts; for rotation-and-reflection use O(n)).
- **References:**
  - Ostrow M., Eisen A., Kozachkov L., Fiete I. (2023). Beyond Geometry: Comparing the Temporal Structure of Computation in Neural Circuits with Dynamical Similarity Analysis. NeurIPS 2023 (arXiv). https://arxiv.org/abs/2306.10168 [read-abstract]
  - Huang A., Ostrow M., Singh S.H., et al. (2025). InputDSA: Demixing then Comparing Recurrent and Externally Driven Dynamics. ICLR 2026 (arXiv). https://arxiv.org/abs/2510.25943 [read-abstract]
  - Behrad A., Ostrow M., Fakharian M.T., et al. (2025). Fast dynamical similarity analysis. arXiv. https://arxiv.org/abs/2511.22828 [read-abstract]
  - Guilhot Q., Wojcik M., Achterberg J., Costa R.P. (2024). Dynamical similarity analysis can identify compositional dynamics developing in RNNs. arXiv. https://arxiv.org/abs/2410.24070 [read-abstract]
  - DSA repo and LICENSE. [repo/docs]

### Conjugacy-based comparison of dynamics (Koopman-spectrum conjugacy tests, CSA, DFORM)
- **Core idea:** Two systems are "the same computation" if topologically conjugate: there is a homeomorphism h with
  h o F = G o h. Approaches: (a) Koopman spectra are invariant under conjugacy (eigenvalues of the Koopman operator are
  preserved, eigenfunctions compose with h), so compare estimated Koopman eigenvalues (Redman et al.); (b) Conjugacy-based
  Similarity Analysis (CSA; Godara et al.) restricts alignments to those induced by a state-space bijection, i.e. the
  finite-data projection of the composition operator of a candidate h, instead of arbitrary orthogonal matrices; (c) DFORM
  (Chen et al.) learns an explicit nonlinear diffeomorphism between state spaces that aligns vector fields, giving a
  similarity score for both equivalent and non-equivalent systems.
- **Assumptions:** Autonomous (or fixed-input) dynamics; spectra estimated reliably (EDMD/DMD dictionary choice); for (c), a
  learnable diffeomorphism exists over the sampled region.
- **Identifiability:** Targets exactly the invariance class the contract needs for (7) ("up to transformations"): smooth or
  topological conjugacy, not just orthogonal/linear maps. Spectra are necessary but not sufficient for conjugacy (unverified in
  general form; point spectrum equality does not imply conjugacy for all systems).
- **Intervention support:** None directly; can compare input-conditioned flows separately.
- **Nonlinear capacity:** High (nonlinear h in DFORM/CSA).
- **Interpretability:** Moderate; DFORM additionally localises invariant manifolds/limit sets.
- **Scaling:** Spectrum comparison cheap; diffeomorphism learning moderate (neural-network training per pair).
- **Failure modes:** Spectral estimates biased by dictionary/rank and noise; continuous spectra (chaos) break (a); learned h can
  overfit; only comparing within sampled regions.
- **Relevance:** Best-matched criterion for (7) cross-implementation sharing and for checking (6) that different seeds learn
  conjugate f. Recommend (a) as a cheap necessary check and (c)/(b) as stronger tests.
- **Open-source implementations:** Not checked for any of the three (licence not verified).
- **From-scratch simplicity:** (a) simple given EDMD; (b)(c) moderate-hard.
- **References:**
  - Redman W.T., Bello-Rivas J.M., Fonoberova M., et al. (2023/2024). Identifying Equivalent Training Dynamics. arXiv. https://arxiv.org/abs/2302.09160 [read-abstract]
  - Godara P., Tay P.S., Mattar M.G. (2026). Beyond DSA: Conjugacy-based Comparison of Dynamical Systems. arXiv. https://arxiv.org/abs/2607.04493 [read-abstract]
  - Chen R., Vedovati G., Braver T., Ching S. (2025/2026). Comparing Dynamical Models Through Diffeomorphic Vector Field Alignment. Neural Computation 38(6). https://arxiv.org/abs/2512.18566 [read-abstract]

### MARBLE (manifold representation basis learning) - and CEBRA briefly
- **Core idea:** Input: point clouds of states with vector-field samples (finite differences of trajectories), grouped by
  user-defined conditions. Build a continuous kNN proximity graph, estimate local tangent frames by SVD, denoise the vector field
  by learnable vector diffusion (connection Laplacian, parallel transport via Kabsch alignment), extract local flow-field features
  with gradient filters (Taylor expansion to order p, p=2 typical), optionally make them rotation-invariant via learnable
  inner products ("embedding-agnostic" mode), map with an MLP to E-dim latent vectors. Unsupervised contrastive loss: adjacent
  local flow fields should be close (positives from one-step random walks, negatives uniform). Distance between systems/conditions =
  optimal-transport (Wasserstein) distance between the empirical distributions of latent vectors.
- **Assumptions:** Dense sampling of a smooth manifold; trials within a condition are dynamically consistent; condition labels.
- **Identifiability:** Embedding-agnostic mode is invariant to local rotations of the embedding (so to different linear
  read-outs of the same manifold dynamics); the latent map itself is not unique.
- **Intervention support:** None (describes flows, no transition law for rollouts).
- **Nonlinear capacity:** High.
- **Interpretability:** Moderate (local flow features).
- **Scaling:** Graph over all sampled states; GPU recommended; OT distances scale with sample count.
- **Failure modes:** Needs condition labels; no explicit time or Markov model; hyperparameters (graph density, diffusion scale).
- **Relevance:** (7) and (6) as a flow-based comparison robust to embedding differences, complementary to DSA (local nonlinear
  flow statistics vs global linear operator). Not a state-discovery method for (1)-(3).
- **CEBRA (brief):** contrastive embedding with time/auxiliary-variable positives; covered in another area. [unverified here]
- **Open-source implementations:** MARBLE - https://github.com/agosztolai/MARBLE - ~115 stars, maintained - MIT (LICENSE read); PyTorch Geometric.
- **From-scratch simplicity:** Hard (vector diffusion, tangent frames, parallel transport).
- **References:**
  - Gosztolai A., Peach R.L., Arnaudon A., et al. (2025). MARBLE: interpretable representations of neural population dynamics using geometric deep learning. Nature Methods (arXiv 2023: "Interpretable statistical representations of neural population dynamics and geometry"). https://arxiv.org/abs/2304.03376 ; https://arxiv.org/html/2304.03376 [read-full] (methods section)
  - MARBLE repo and LICENSE. [repo/docs]

### CCA, SVCCA and PWCCA
- **Core idea:** CCA finds paired directions maximising correlation between two representations X (n x p1) and Y (n x p2) on the
  same n samples; summary = mean canonical correlation. SVCCA first truncates each to top SVD directions (e.g. 99% variance)
  then applies CCA. PWCCA weights canonical correlations by how much of the original representation each canonical direction
  accounts for, down-weighting noise directions.
- **Assumptions:** Paired samples (same inputs/time points); linear relation.
- **Identifiability / invariance:** Invariant to invertible linear (affine) transforms of each representation. This is the
  correct invariance class for "latent coordinates identifiable up to linear transform" but see failure modes.
- **Intervention support:** N/A (comparison measure).
- **Nonlinear capacity:** Linear only (kernel CCA and deep CCA extensions exist; not reviewed).
- **Interpretability:** Moderate: canonical directions and correlations are readable; mean-correlation summaries hide which
  directions match.
- **Scaling:** O(n p^2 + p^3).
- **Failure modes:** Kornblith et al. show any statistic invariant to invertible linear transforms cannot give meaningful
  similarity when dimension >= number of samples (CCA saturates at 1); overfits in high dims, so use regularised CCA, SVD
  truncation or held-out evaluation. Mean canonical correlation over-weights low-variance directions (PWCCA's motivation).
  SVCCA's variance threshold is an arbitrary hyperparameter.
- **Relevance:** (6)(7) for low-k latents (k << samples) where linear-transform invariance is appropriate; compute on held-out
  samples (fit CCA on train, evaluate correlations on test).
- **Open-source implementations:** google/svcca (licence not verified); netrep LinearMetric with alpha=0 is a CCA-type metric (MIT); sklearn CCA (BSD-3, unverified here).
- **From-scratch simplicity:** Simple (QR/SVD of whitened cross-covariance); add ridge regularisation.
- **References:**
  - Raghu M., Gilmer J., Yosinski J., Sohl-Dickstein J. (2017). SVCCA: Singular Vector Canonical Correlation Analysis for Deep Learning Dynamics and Interpretability. NeurIPS 2017. https://arxiv.org/abs/1706.05806 [read-abstract]
  - Morcos A.S., Raghu M., Bengio S. (2018). Insights on representational similarity in neural networks with canonical correlation. NeurIPS 2018. https://arxiv.org/abs/1806.05759 [read-abstract]

### Centered Kernel Alignment (CKA) and its critiques
- **Core idea:** CKA(K, L) = HSIC(K, L) / sqrt(HSIC(K, K) HSIC(L, L)) on centred Gram matrices; linear CKA uses K = X X^T.
  Invariant to orthogonal transforms and isotropic scaling, not to arbitrary invertible linear maps, which lets it work when
  dimension exceeds sample count. RBF-kernel variant available.
- **Assumptions:** Paired samples.
- **Identifiability / invariance:** Orthogonal + isotropic scaling. Normalised Bures similarity (NBS) is closely related; its
  arccos equals the Procrustes (Riemannian) shape distance (Harvey, Larsen, Williams), and CKA/CCA can be read as average alignment of
  optimal linear decoders over a distribution of decoding tasks (Harvey, Lipshutz, Williams).
- **Intervention support:** N/A (comparison measure); can be applied to post-intervention latents to compare responses.
- **Nonlinear capacity:** Linear CKA compares linear geometry; RBF-kernel CKA captures nonlinear (local) similarity with a bandwidth choice.
- **Interpretability:** Low: a single scalar with no decomposition into matching directions.
- **Scaling:** O(n^2 p) for Gram matrices (linear CKA can be computed in O(n p^2) via feature covariances); n = number of samples.
- **Failure modes (important):** Davari et al.: CKA is sensitive to simple transformations and outliers, responds unexpectedly to
  transformations preserving linear separability, and can be manipulated substantially without changing function. Murphy et al.:
  the standard (biased) CKA estimator gives high similarity even for random matrices when features >> samples; use the
  debiased HSIC estimator. Linear CKA is dominated by high-variance directions, so two representations sharing only a dominant
  (possibly trivial, e.g. input-copying or slow drift) component look similar. Not a metric (no triangle inequality).
- **Relevance:** Cheap sanity check for (6)(7); never the sole criterion. Report debiased CKA with a shuffled/random-network
  null distribution.
- **Open-source implementations:** Numerous small implementations; netrep does not centre on CKA; from scratch is trivial.
- **From-scratch simplicity:** Simple; pitfall: use unbiased HSIC (Song et al. estimator) when n is small relative to p.
- **References:**
  - Kornblith S., Norouzi M., Lee H., Hinton G. (2019). Similarity of Neural Network Representations Revisited. ICML 2019. https://arxiv.org/abs/1905.00414 [read-abstract]
  - Davari M., Horoi S., Natik A., et al. (2022). Reliability of CKA as a Similarity Measure in Deep Learning. arXiv (ICLR 2023 per unverified). https://arxiv.org/abs/2210.16156 [read-abstract]
  - Murphy A., Zylberberg J., Fyshe A. (2024). Correcting Biased Centered Kernel Alignment Measures in Biological and Artificial Neural Networks. ICLR 2024 Re-Align Workshop. https://arxiv.org/abs/2405.01012 [read-abstract]
  - Harvey S.E., Larsen B.W., Williams A.H. (2023). Duality of Bures and Shape Distances with Implications for Comparing Neural Representations. arXiv. https://arxiv.org/abs/2311.11436 [read-abstract]
  - Harvey S.E., Lipshutz D., Williams A.H. (2024). What Representational Similarity Measures Imply about Decodable Information. arXiv. https://arxiv.org/abs/2411.08197 [read-abstract]

### Orthogonal Procrustes, generalized shape metrics and stochastic shape metrics (netrep)
- **Core idea:** Generalized shape metrics: after centring and partial whitening with parameter alpha in [0,1] (alpha=1: plain
  Procrustes/rotation invariance; alpha=0: full whitening -> CCA-like invariance to invertible linear maps), d(X, Y) =
  arccos or Euclidean distance after optimal orthogonal alignment. These are proper metrics (triangle inequality), enabling
  clustering/embedding of many networks; permutation-invariant and convolution-respecting variants exist. Stochastic shape
  metrics extend this to noisy representations by comparing conditional response distributions (Wasserstein distance between
  Gaussians, i.e. means + covariances with an interpolation parameter, or energy distance).
- **Assumptions:** Paired conditions/time points; equal dimension (zero-pad otherwise).
- **Identifiability / invariance:** Tunable: rotations only (alpha=1) through linear (alpha=0); add permutation group when
  units correspond.
- **Intervention support:** N/A (comparison measure); can be applied to post-intervention latents to compare responses.
- **Nonlinear capacity:** Linear alignment (orthogonal to linear); nonlinear differences show up as residual distance, not modelled.
- **Interpretability:** High: the optimal alignment and per-condition residuals are inspectable; a proper metric allows clustering of models.
- **Scaling:** O(n p^2 + p^3) per pair; pairwise distance matrices over many models scale quadratically in the number of models.
- **Failure modes:** Rotation-only metrics penalise legitimate anisotropic scaling differences between implementations;
  alpha=0 inherits CCA overfitting; purely geometric - two systems with the same state cloud but different flows score as equal
  (the DSA critique). Cross-validate alignment (fit rotation on train, measure distance on test; netrep supports this).
- **Relevance:** Recommended primary geometric measure for (6)(7) because it is a metric with an explicit, adjustable
  invariance group; stochastic variant useful when the simulator is noisy and latents are distributions.
- **Open-source implementations:** netrep - https://github.com/ahwillia/netrep - research code, ~145 stars - MIT; LinearMetric(alpha), PermutationMetric, GaussianStochasticMetric, EnergyStochasticMetric, pairwise distance matrices, train/test alignment.
- **From-scratch simplicity:** Simple (orthogonal Procrustes = SVD of X^T Y).
- **References:**
  - Williams A.H., Kunz E., Kornblith S., Linderman S.W. (2021). Generalized Shape Metrics on Neural Representations. NeurIPS 2021. https://arxiv.org/abs/2110.14739 [read-abstract]
  - Duong L.R., Zhou J., Nassar J., et al. (2023). Representational dissimilarity metric spaces for stochastic neural networks. ICLR 2023. https://arxiv.org/abs/2211.11665 [read-abstract]
  - netrep repo. [repo/docs]

### Principal angles between subspaces and RSA
- **Core idea:** Principal angles: for orthonormal bases Q_A, Q_B, cos(theta_i) = singular values of Q_A^T Q_B; compares the
  subspaces spanned (e.g. latent loading matrices, dynamics-mode subspaces, input subspaces) independently of basis. RSA:
  build a representational dissimilarity matrix (RDM) of pairwise condition dissimilarities (e.g. 1 - Pearson correlation),
  compare RDMs by rank (Spearman) correlation over the upper triangle, and test by permuting condition labels.
- **Assumptions:** Principal angles: subspaces in a common ambient space (same units). RSA: a shared, meaningful set of
  conditions and a chosen dissimilarity measure.
- **Identifiability:** Subspaces (not bases) are compared; RDMs are invariant to transforms preserving the dissimilarity.
- **Invariance:** Principal angles: any invertible change of basis within each subspace. RSA: any transform preserving the
  chosen dissimilarity (orthogonal + scaling for Euclidean/correlation distance; monotone distortion of dissimilarities via rank correlation); no unit correspondence needed.
- **Intervention support:** N/A (comparison measure); can be applied to post-intervention latents to compare responses.
- **Nonlinear capacity:** Principal angles: linear subspaces only. RSA: any representation, via the chosen (possibly nonlinear) dissimilarity.
- **Interpretability:** High for principal angles (angle spectrum per direction); moderate for RSA (RDM structure is inspectable).
- **Scaling:** Principal angles O(N k^2); RSA O(c^2 p) for c conditions plus permutation tests.
- **Failure modes:** Principal angles need equal-dimension subspaces in a common ambient space (same units), so they suit
  comparing subspaces within one simulator (e.g. across seeds with identical units) not across implementations; small angles are
  numerically delicate (scipy uses the Knyazev-Argentati sine-based algorithm). RSA discards dynamics and depends on the
  condition set.
- **Relevance:** Principal angles: (6) stability of phi's row space across seeds/estimators in unit space. RSA: condition-level
  geometry check for (7).
- **Open-source implementations:** scipy.linalg.subspace_angles (BSD-3, unverified here); rsatoolbox (licence not verified).
- **From-scratch simplicity:** Simple.
- **References:**
  - SciPy docs, scipy.linalg.subspace_angles (algorithm: Knyazev A.V., Argentati M.E. (2002), SIAM J. Sci. Comput. 23:2008-2040). https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.subspace_angles.html [repo/docs]
  - Bjorck A., Golub G.H. (1973). Numerical methods for computing angles between linear subspaces. Math. Comp. [unverified]
  - Kriegeskorte N., Mur M., Bandettini P. (2008). Representational similarity analysis - connecting the branches of systems neuroscience. Frontiers in Systems Neuroscience 2:4. https://www.frontiersin.org/articles/10.3389/neuro.06.004.2008/full [read-full] (method parts)

### Dimensionality estimation (participation ratio, variance thresholds, bi-cross-validation, TwoNN, MLE)
- **Core idea:** Linear/embedding dimension: participation ratio PR = (sum_i lambda_i)^2 / sum_i lambda_i^2 of covariance
  eigenvalues; PCA variance thresholds (e.g. 90%); cross-validated PCA / factor-analysis log-likelihood; bi-cross-validation
  (Owen & Perry): hold out a block of rows and columns, predict the held-out block from a rank-k fit of the retained blocks,
  choose k minimising error (balanced ~50/50 hold-outs worked best). Intrinsic (nonlinear) dimension: TwoNN uses only the ratio
  mu = r2/r1 of second to first nearest-neighbour distances, which is Pareto-distributed with exponent d under local uniformity;
  scale dependence probed by decimation. Levina-Bickel MLE: Poisson-process likelihood of k-NN distances.
- **Key methodological point:** Intrinsic dimension (number of latent variables) differs from embedding dimension (number of
  linear dimensions the manifold occupies); Jazayeri & Ostojic frame the pair as informative about computation. Altan et al.
  showed linear estimators overestimate the dimension of nonlinear noise-free manifolds, most estimators overestimate under high
  noise, all fail at high dimension (>~20) or small samples, and denoising (a joint autoencoder) before estimation helps.
- **Assumptions:** PR/PCA: linear; kNN estimators: locally uniform density, low noise, enough samples (exponential in d).
- **Identifiability:** Estimates a number, not coordinates. Linear estimators give embedding dimension; kNN estimators give
  the local intrinsic dimension of the sampled state cloud; neither identifies the closed-state dimension.
- **Intervention support:** None intrinsically; can be applied to post-intervention state clouds, whose dimension may exceed
  the unperturbed one.
- **Nonlinear capacity:** PR/PCA/bi-CV: linear. TwoNN/MLE/DANCo: nonlinear manifolds (under local-uniformity assumptions).
- **Interpretability:** High (a single number per scale), but easily misread as state dimension.
- **Scaling:** PCA O(n p^2); kNN estimators O(n log n) with trees or O(n^2) brute force; bi-CV requires repeated SVDs.
- **Relevance:** (5) minimality and (8) abstention. Important contrast: the dimension of the state cloud is not the dimension
  of a Markov/interventionally sufficient state (a limit cycle has intrinsic dim 1 but k for a closed state is 1 only on-cycle;
  transients/perturbations need more). Use these only as bracketing priors for k; choose k finally by held-out multi-horizon and
  interventional prediction plateaus. PR of a high-dim noisy system scales with N; report vs N.
- **Failure modes:** Noise inflates all estimates; time-autocorrelated samples violate i.i.d. assumptions of kNN estimators (subsample in time); PCA thresholds arbitrary; curvature inflates linear dimension.
- **Open-source implementations:** scikit-dimension - https://github.com/scikit-learn-contrib/scikit-dimension - ~110 stars, CI active - BSD-3-Clause; implements TwoNN, MLE, DANCo, lPCA, CorrInt, ESS, MiND_ML, FisherS (global and local).
- **From-scratch simplicity:** Simple (PR, TwoNN, MLE are a few lines); bi-CV simple via pseudo-inverse formula.
- **References:**
  - Facco E., d'Errico M., Rodriguez A., Laio A. (2017). Estimating the intrinsic dimension of datasets by a minimal neighborhood information. Scientific Reports. https://arxiv.org/abs/1803.06992 [read-abstract]
  - Levina E., Bickel P.J. (2004). Maximum Likelihood Estimation of Intrinsic Dimension. NeurIPS 17. https://proceedings.neurips.cc/paper/2004/hash/74934548253bcab8490ebd74afed7031-Abstract.html [read-abstract]
  - Owen A.B., Perry P.O. (2009). Bi-cross-validation of the SVD and the nonnegative matrix factorization. Annals of Applied Statistics 3(2):564-594. https://arxiv.org/abs/0908.2062 [read-abstract]
  - Jazayeri M., Ostojic S. (2021). Interpreting neural computations by examining intrinsic and embedding dimensionality of neural activity. Current Opinion in Neurobiology. https://arxiv.org/abs/2107.04084 [read-abstract]
  - Altan E., Solla S.A., Miller L.E., Perreault E.J. (2021). Estimating the dimensionality of the manifold underlying multi-electrode neural recordings. PLoS Comput. Biol. https://www.biorxiv.org/content/10.1101/2020.12.17.423196v1 [read-abstract] (only methodological findings used)
  - Gao P. et al. (2017). A theory of multineuronal dimensionality, dynamics and measurement (participation ratio usage). bioRxiv. [unverified]
  - scikit-dimension repo. [repo/docs]

### Reduced-rank regression / communication subspace
- **Core idea:** Multivariate regression Y = X B + E with rank(B) <= r; closed form: OLS fit then project fitted values onto
  their top-r principal directions (Izenman). The "communication subspace" analysis uses RRR from one group of units to another
  and cross-validated prediction vs rank to find a low-rank input-output channel, compared against the target group's own
  dimensionality (e.g. factor analysis) (method description from memory; unverified).
- **Assumptions:** Linear, Gaussian noise; paired samples.
- **Identifiability:** Row space of B (predictive subspace in X) and column space identifiable; bases not.
- **Intervention support:** Predictive only; with simulator interventions on X-subspace one can test whether the subspace is causal.
- **Nonlinear capacity:** None (kernel/neural extensions possible).
- **Interpretability:** High: rank-r predictive directions in X and their target patterns in Y are directly readable.
- **Scaling:** O(n p^2) OLS + SVD; use ridge-regularised RRR when p is large.
- **Failure modes:** Rank selection is hard (discrete parameter); shared latent drive rather than communication can create
  low-rank predictability; time lags matter.
- **Relevance:** Tool for (1)(5): the minimal rank of the map x(t) -> future y or x(t+h) is a direct linear "predictive state"
  dimension (this is essentially CCA/CVA-style subspace identification with past/future); also a baseline encoder: phi = top-r
  RRR predictor directions from past x (and u) to future y.
- **Open-source implementations:** Many small implementations; none checked (licence not verified).
- **From-scratch simplicity:** Simple.
- **References:**
  - Izenman A.J. (1975). Reduced-rank regression for the multivariate linear model. J. Multivariate Analysis 5(2):248-264. https://ideas.repec.org/a/eee/jmvana/v5y1975i2p248-264.html [unverified] (only search snippet seen)
  - Semedo J.D., Zandvakili A., Machens C.K., Yu B.M., Kohn A. (2019). Communication subspace (reduced-rank regression between populations). Neuron. [unverified] (deliberately not opened)

---

## G. Experiment design, canonical dynamical coordinates and evaluation of learned dynamics

_Source notes: `notes\area_G_design_phase_eval.md`._

Scope: how to *choose* simulator runs (initial states, inputs, microscopic perturbations, parameter draws) to identify a
compact causal state, how to extract *canonical* coordinates (phase, isostables, spectral-submanifold / normal-form
coordinates, fixed/slow points, bifurcation structure) that serve as reference answers and as candidate latent states, and
how to *evaluate* learned dynamical models beyond one-step error (attractor geometry, spectra, Lyapunov exponents,
held-out perturbation responses).

Key point for this project: we have a simulator, not a fixed dataset. That changes experiment design from "which
experiment can we afford" into "how to split a compute budget". Quantities that are hard to estimate from passive data
(PRCs, isostable response curves, empirical gramians, Jacobians at slow points, invariant-manifold geometry) can be
measured *directly* by controlled perturbation of the full microstate x. So they can serve as ground-truth probes against which
learned z = phi(x), f and g are checked.

Citation tags follow notes/TEMPLATE.md: [read-full], [read-abstract], [repo/docs], [unverified].
"[read-abstract]" below includes cases where the abstract/landing page was only seen through a fetch summary.

---

### Fisher-information optimal input / experiment design for dynamical models (classical OED: D/A/E-optimal)
- **Core idea:** Pick inputs u(t), sampling times, initial conditions and sensors to optimise a scalar function of the
  Fisher information matrix M(xi, theta) of the model parameters: D-optimal maximises log det M (minimum-volume confidence
  ellipsoid), A-optimal minimises trace M^-1 (mean parameter variance), E-optimal maximises lambda_min(M) (worst direction).
  For dynamical systems M is built from output sensitivities dy/dtheta along simulated trajectories. Mehra (1974) set out
  optimal input design for dynamic systems; Pronzato (2008) reviews the links between OED and control (optimal inputs for
  precise estimation, designed perturbations in adaptive control, asymptotics of estimators, extension to non-parametric
  learning).
- **Assumptions:** A parametric model structure that is (approximately) correct; local linearisation around a nominal theta
  ("local design": the optimal design depends on the unknown theta). Remedies are robust/Bayesian/sequential designs.
  Gaussian noise gives the standard M. Asymptotic regime.
- **Identifiability:** A singular M means the parameters are not locally identifiable from the design; the rank and conditioning
  of M are a direct local identifiability diagnostic. It says nothing about latent coordinates, which are identifiable only up to
  a transformation: the Fisher information of a latent-coordinate model is always singular along the gauge (reparametrisation)
  directions, and these must be quotiented out.
- **Intervention support:** Native. The design variable *is* the input or perturbation. It extends to impulsive state
  perturbations and to the choice of which units receive input.
- **Nonlinear capacity:** Any differentiable simulator (sensitivities via adjoint or forward sensitivity equations, or
  finite differences). The design is only locally optimal.
- **Interpretability:** High. Eigenvectors of M show which parameter combinations are ("sloppy") and are not constrained.
- **Scaling:** M is p x p for p parameters. For a microscopic model with ~N^2 weights the full M is huge, so work
  in low-dimensional parameter subspaces or use randomised/trace estimators. Sensitivities cost about one extra forward/adjoint run
  per design.
- **Failure modes:** Local optimality at a wrong theta. Designs concentrate on few support points (poor for model
  checking and generalisation). Sloppy spectra cause an ill-conditioned M. Model misspecification makes "optimal" designs misleading.
- **Relevance to problem:** Mainly (3) and (5). It picks input/perturbation sets that separate candidate latent
  models, and the rank of M restricted to the latent-model parameters is a check on minimality. Use it to *audit* a
  training set (does it excite all directions the latent model claims to represent?), not as the main learner.
- **Open-source implementations:** PyOED (Python, model-constrained A/D-optimal OED and sensor placement for inverse
  problems/data assimilation) - https://gitlab.com/ahmedattia/pyoed - active (1,300+ commits) - BSD-3-Clause [repo/docs].
  Pyomo.DoE exists (not checked; licence not verified).
- **From-scratch simplicity:** Simple for small p. Compute sensitivities with autodiff through the simulator (JAX/PyTorch)
  and optimise log det(M + eps I) over input parametrisations. Pitfalls: parameter scaling (use log-parameters), noise model,
  a regulariser eps for the singular gauge directions.
- **References:**
  - R. K. Mehra, "Optimal input signals for parameter estimation in dynamic systems - Survey and new results", 1974, IEEE
    Trans. Automatic Control 19(6):753-768. [unverified] (bibliographic data from search results only)
  - L. Pronzato, "Optimal experimental design and some related control problems", 2008, Automatica 44:303-325,
    https://arxiv.org/abs/0802.4381 [read-abstract]
  - M. Gevers, "Identification for control" line of work (e.g. "Identification for control: from the early achievements to
    the revival of experiment design", Eur. J. Control 2005). [unverified]
  - A. Chowdhary, S. E. Ahmed, A. Attia, "PyOED: An Extensible Suite for Data Assimilation and Model-Constrained Optimal
    Design of Experiments", 2023, arXiv/ACM TOMS, https://arxiv.org/abs/2301.08336 [read-abstract]; repo
    https://gitlab.com/ahmedattia/pyoed [repo/docs]

### Persistency of excitation and Willems' fundamental lemma (behavioural / data-driven control)
- **Core idea:** For a controllable LTI system, if the input is persistently exciting (PE) of order L + n (block-Hankel
  matrix of u has full row rank), then the columns of the depth-L Hankel matrix of (u, y) data span *all* length-L
  trajectories of the system (Willems, Rapisarda, Markovsky, De Moor 2005). The Hankel matrix then acts as a
  non-parametric model. De Persis & Tesi (2019/2020) use this to write state-feedback, LQR and robust controllers as
  data-dependent LMIs without explicit identification. Yu et al. (2021) weaken the controllability and PE requirements.
  Camlibel, van Waarde & Rapisarda (2024) give *online* input design that yields the shortest possible
  identifying experiment, beating offline PE designs.
- **Assumptions:** LTI, known upper bounds on state dimension n and lag. Noise-free for the exact statements (robust
  variants exist).
- **Identifiability:** The behaviour (the set of trajectories) is identified exactly, and state-space realisations follow up to
  similarity transform. The rank of the Hankel matrix reveals n (minimal state dimension). This connects directly to
  minimal realisation (property 5).
- **Intervention support:** It is a statement about which inputs are *sufficient*. It tells us how long and how rich u
  must be. In our setting "inputs" include injected currents into units and impulsive state offsets (which act like
  inputs through B = e_i).
- **Nonlinear capacity:** Linear only. Nonlinear extensions exist via lifting (Koopman/feature Hankel matrices) or local
  linearisation. The theory does not transfer cleanly.
- **Interpretability:** High for the linear case (rank = order).
- **Scaling:** Hankel matrix of size L(m + p) x (T - L + 1). Needs T >= (m + 1)(L + n) - 1 samples as a rough PE count
  for m inputs. With many input channels (currents into ~100 units) T grows linearly in m. So excite a low-dimensional input
  subspace or use multiple short experiments (the mosaic-Hankel variant (unverified)).
- **Failure modes:** Noise inflates numerical rank, so rank selection needs SVD gaps or a statistical test. Nonlinearity
  makes the rank grow with L. PE of u does not guarantee excitation of all state directions when the system is uncontrollable
  (Yu et al. treat this).
- **Relevance to problem:** (3) and (5): a principled lower bound on how rich the input/perturbation protocol must be so that
  a linearised latent model is identifiable. It is also a cheap baseline, "Hankel/behavioural predictor", for linear-regime
  responses to held-out inputs. Around a stable operating point the local Hankel rank estimates the local minimal k.
- **Open-source implementations:** No single canonical package was checked. The core is ~30 lines of NumPy (Hankel matrix, SVD,
  least squares). Licence not applicable.
- **From-scratch simplicity:** Simple. Pitfalls: use the same L for training and prediction, regularise (ridge / low-rank
  truncation) when noisy, standardise channels.
- **References:**
  - J. C. Willems, P. Rapisarda, I. Markovsky, B. L. M. De Moor, "A note on persistency of excitation", 2005, Systems &
    Control Letters 54:325-329. [unverified] (abstract seen only in search snippets)
  - C. De Persis, P. Tesi, "Formulas for Data-driven Control: Stabilization, Optimality and Robustness", 2019 CDC /
    IEEE TAC 65(3) 2020, https://export.arxiv.org/abs/1903.06842v3 [read-abstract]
  - Y. Yu, S. Talebi, H. J. van Waarde et al., "On Controllability and Persistency of Excitation in Data-Driven Control:
    Extensions of Willems' Fundamental Lemma", 2021, CDC 2021, https://arxiv.org/abs/2102.02953 [read-abstract]
  - M. K. Camlibel, H. J. van Waarde, P. Rapisarda, "The shortest experiment for linear system identification", 2024,
    arXiv, https://arxiv.org/abs/2407.12509 [read-abstract]

### Bayesian optimal experimental design: variational, sequential and amortised (BOED, DAD)
- **Core idea:** Choose design xi to maximise expected information gain (EIG) about the quantity of interest (parameters,
  model identity, or a *prediction*), EIG(xi) = E[log p(y | theta, xi) - log p(y | xi)]. Foster et al. (2019) give fast
  variational EIG estimators (posterior, marginal, VNMC bounds) via amortised variational inference. Deep Adaptive Design
  (DAD; Foster et al. 2021) trains a design *policy network* offline on contrastive (sPCE) lower bounds, so that sequential
  adaptive designs cost one forward pass at deployment. The architecture exploits permutation symmetry of the history.
  Rainforth et al. (2023, Statistical Science) review the field: estimators, sequential/amortised/policy-based BED, and
  implicit-likelihood (simulator-only) settings.
- **Assumptions:** A prior over models/parameters and a likelihood (explicit, or implicit through a simulator with
  likelihood-free bounds). DAD needs a differentiable simulator for the reparametrised gradient w.r.t. designs, or
  score-function/RL variants.
- **Identifiability:** EIG is invariant to reparametrisation of theta. Targeting information about *predictions* (e.g. the
  future readout under a held-out perturbation) sidesteps latent-coordinate gauge freedom. This is attractive for
  properties (1) and (3).
- **Intervention support:** Native. Designs can be the intervention type, target unit, amplitude and timing.
- **Nonlinear capacity:** Arbitrary models. The limit is estimator variance and cost.
- **Interpretability:** Moderate. Designs are explainable post hoc (e.g. where posterior predictive disagreement is largest).
- **Scaling:** Nested Monte Carlo EIG is costly (inner x outer samples). Variational bounds reduce this. DAD moves the cost to
  offline policy training and suits many repeated experiments. High-dimensional designs (which of N units, which
  waveform) need gradient-based or policy-based optimisation.
- **Failure modes:** Misspecified prior/model leads to confidently uninformative designs. Myopic greedy EIG can be
  suboptimal. EIG bounds can be loose. The policy overfits to the prior.
- **Relevance to problem:** Because simulation is cheap relative to learning, BOED is most useful at the
  *model-comparison / counterexample* stage: choose the perturbations that best discriminate between competing
  candidate abstractions (phi_1, f_1) vs (phi_2, f_2), or that maximally violate microstate invariance (4) or
  closure (2). This supports counterexample-guided refinement. It is not needed for bulk training data.
- **Open-source implementations:** dad - https://github.com/ae-foster/dad - research code, few commits, ~47 stars - MIT
  [repo/docs]. Pyro OED module (`pyro.contrib.oed`), which Foster et al. build on (not opened; licence of Pyro is Apache-2.0 (unverified)).
  BoTorch - https://github.com/pytorch/botorch - active, ~3.6k stars - MIT [repo/docs] (Bayesian optimisation; the
  acquisition docs page I read listed EI/UCB/PI and MC acquisitions; information-theoretic acquisitions such as max-value
  entropy search and integrated posterior variance are believed present (unverified)).
- **From-scratch simplicity:** Moderate. A plug-in "ensemble disagreement / mutual information between model and outcome"
  EIG for a finite set of candidate models is simple. Full DAD is harder (policy training, bound variance).
- **References:**
  - A. Foster, M. Jankowiak, E. Bingham et al., "Variational Bayesian Optimal Experimental Design", 2019, NeurIPS,
    https://arxiv.org/abs/1903.05480 [read-abstract]
  - A. Foster, D. R. Ivanova, I. Malik, T. Rainforth, "Deep Adaptive Design: Amortizing Sequential Bayesian Experimental
    Design", 2021, ICML, https://arxiv.org/abs/2103.02438 [read-abstract]
  - T. Rainforth, A. Foster, D. R. Ivanova, F. Bickford Smith, "Modern Bayesian Experimental Design", 2023/2024,
    Statistical Science, https://arxiv.org/abs/2302.14545 [read-abstract]
  - dad repo https://github.com/ae-foster/dad [repo/docs]; BoTorch https://github.com/pytorch/botorch and
    https://botorch.org/docs/acquisition [repo/docs]

### Active learning of dynamics models (uncertainty/information-driven data collection)
- **Core idea:** Collect trajectories where the current dynamics model is most uncertain. Buisson-Fenet, Solowjow &
  Trimpe (2020) pick GP-dynamics sample points by information-theoretic criteria (high predictive variance/entropy) while
  respecting that samples must be reachable along system trajectories. Capone et al. (2020) maximise mutual information of
  exploration trajectories within a bounded region of interest, decoupled from MPC. MAX (Shyam et al. 2019) plans
  exploration using disagreement among an ensemble of forward models as a Bayesian novelty measure.
- **Assumptions:** A model with calibrated epistemic uncertainty (GP, ensemble, Bayesian NN). In physical settings the
  reachability constraint matters. **In a simulator we can reset to any x0**, which removes the reachability constraint
  and allows "query-anywhere" active learning (though states off the natural manifold may be irrelevant, see failure modes).
- **Identifiability:** Not addressed. Improves sample efficiency of f only.
- **Intervention support:** Inputs/controls, yes. Perturbation types can be included as actions.
- **Nonlinear capacity:** Full (GP/NN).
- **Interpretability:** Low-moderate.
- **Scaling:** GP versions scale poorly in state dimension (fine in latent z of small k, not in x with N ~ 100-5000).
  Ensemble disagreement scales well.
- **Failure modes:** Uncertainty-seeking drifts to unphysical or irrelevant regions (e.g. far-from-attractor microstates
  with saturated units), which biases the training distribution. Aleatoric noise is mistaken for epistemic uncertainty. With
  free resets, it can over-sample transients at the expense of attractor dynamics.
- **Relevance to problem:** (1), (3), (4): once a candidate latent model exists, direct extra simulation to (a) latent
  regions with high ensemble disagreement, and (b) *microstate pairs with equal z but divergent predicted futures*
  (active search for violations of (4)). Budget recommendation below.
- **Open-source implementations:** No maintained package checked for these specific papers (licence not verified).
  Ensemble-disagreement acquisition is trivial to implement.
- **From-scratch simplicity:** Simple (ensemble variance acquisition over candidate (x0, u, perturbation) tuples). Moderate
  for trajectory-level MI.
- **References:**
  - M. Buisson-Fenet, F. Solowjow, S. Trimpe, "Actively Learning Gaussian Process Dynamics", 2020, L4DC (PMLR 120),
    https://arxiv.org/abs/1911.09946 [read-abstract]
  - A. Capone, J. Umlauft, T. Beckers et al., "Localized active learning of Gaussian process state space models", 2020,
    L4DC, https://arxiv.org/abs/2005.02191 [read-abstract]
  - P. Shyam, W. Jaskowski, F. Gomez, "Model-Based Active Exploration", 2019, ICML, https://arxiv.org/abs/1810.12162
    [read-abstract]

### Active causal discovery / intervention design (brief)
- **Core idea:** Choose interventions to identify a causal graph or causal quantity. Hauser & Buhlmann (2014): greedy
  single-vertex interventions maximising orientable edges, and a polynomial-time minimum target set guaranteeing full
  identifiability of the essential graph. ABCD (Agrawal et al. 2019): budgeted Bayesian design targeted at a *specific*
  causal feature (e.g. descendants of a node), with submodularity-based guarantees. CBED (Tigas et al. 2022): Bayesian
  design choosing *both* intervention target *and value*, for large nonlinear SCMs, using uncertainty from data scarcity and
  non-identifiability.
- **Assumptions:** Static (acyclic) SCMs over observed variables. Dynamics/feedback not native (temporal unrolling
  needed). Hard/soft interventions on observed variables.
- **Identifiability:** Graph up to Markov/interventional equivalence class, shrinking with interventions.
- **Intervention support:** Core purpose.
- **Nonlinear capacity:** CBED handles nonlinear SCMs. The earlier methods are mainly structural.
- **Interpretability:** High (graph).
- **Scaling:** Tens to hundreds of variables. Not x with thousands of units.
- **Failure modes:** Cyclic dynamical systems violate DAG assumptions unless time-unrolled. Latent confounding.
- **Relevance to problem:** Mostly conceptual for (3): the principle that *target and value* should both be designed, and that
  the design objective should be the downstream quantity (targeted, as in ABCD). Here, the target is the macroscopic
  transition f and the equivalence class is "microstates mapped to the same z".
- **Open-source implementations:** Not checked (licence not verified). pcalg (R) implements Hauser-Buhlmann GIES (unverified).
- **From-scratch simplicity:** Moderate.
- **References:**
  - A. Hauser, P. Buhlmann, "Two Optimal Strategies for Active Learning of Causal Models from Interventional Data", 2014,
    Int. J. Approx. Reasoning 55(4), https://arxiv.org/abs/1205.4174 [read-abstract]
  - R. Agrawal, C. Squires, K. Yang et al., "ABCD-Strategy: Budgeted Experimental Design for Targeted Causal Structure
    Discovery", 2019, AISTATS, https://arxiv.org/abs/1902.10347 [read-abstract]
  - P. Tigas, Y. Annadani, A. Jesson et al., "Interventions, Where and How? Experimental Design for Causal Models at
    Scale", 2022, NeurIPS, https://arxiv.org/abs/2203.02016 [read-abstract]
  - Zhang et al., "Active learning for optimal intervention design in causal models", 2023, Nature Machine Intelligence,
    arXiv:2209.04744 [unverified] (seen in search results only)

### Empirical gramians and observability/controllability-aware sensor and perturbation selection
- **Core idea:** Replace the linear gramians by averages over simulated responses: the empirical controllability gramian from
  impulse responses to input perturbations, the empirical observability gramian from output responses to small initial-state
  perturbations (+/- c e_i), the empirical cross gramian, and a parameter-identifiability gramian (Himpe, emgr). Kazma & Taha
  (2024) show that a variational (tangent-linear) gramian equals the empirical observability gramian under linear outputs, is
  cheaper, relates observability to Lyapunov exponents, and use it for sensor selection/placement in nonlinear networks.
  Sensor selection maximises log det / trace / lambda_min of the gramian over subsets, often via submodular greedy
  selection.
- **Assumptions:** Perturbation scale c small enough for local validity but above numerical noise. Averaging over an
  operating region / trajectory set. Stability or finite horizon for convergence.
- **Identifiability:** The gramian rank equals the locally observable/controllable dimension. Its eigenvectors give coordinates
  up to rotation within degenerate eigenspaces.
- **Intervention support:** Directly built from interventions: state offsets (observability) and injected inputs
  (controllability). This matches the simulator's microscopic perturbations one to one.
- **Nonlinear capacity:** Local-to-regional. Empirical gramians average over trajectories and perturbation scales, so they see
  some nonlinearity.
- **Interpretability:** High. Balancing the two gramians gives the dominant input-output coordinates (empirical balanced
  truncation), a strong interpretable reduced-coordinate baseline.
- **Scaling:** Observability gramian needs 2N perturbed runs (N ~ 100-5000). That is feasible on a simulator and trivially
  parallel. Memory N^2. Randomised/low-rank variants (perturb random directions) reduce the cost to O(k) runs (unverified for
  error bounds).
- **Failure modes:** Wrong perturbation scale. Unstable/chaotic dynamics make finite-horizon gramians horizon-dependent.
  Gramians of the *microscopic* output are not the same as the causal state: they measure input-output relevance, not
  closure.
- **Relevance to problem:** (3), (5), (8). The empirical cross/balanced gramian spectrum gives a principled "how many input-
  and output-relevant directions" estimate for k. A flat Hankel-singular-value spectrum is an abstention signal (8). It also
  gives a reference subspace to compare learned phi against (principal angles).
- **Open-source implementations:** emgr (MATLAB/Octave + Python variant) - https://github.com/gramian/emgr - archived
  (read-only) Sept 2023, ~21 stars - BSD-2-Clause [repo/docs].
- **From-scratch simplicity:** Simple. Pitfalls: centre on the unperturbed trajectory (subtract the nominal response), use
  several perturbation scales, and symmetric +/- perturbations to cancel even-order terms.
- **References:**
  - C. Himpe, "emgr - The Empirical Gramian Framework", 2018, Algorithms 11(7):91, https://arxiv.org/abs/1611.00675
    [read-abstract]; repo https://github.com/gramian/emgr [repo/docs]
  - M. H. Kazma, A. F. Taha, "Observability for Nonlinear Systems: Connecting Variational Dynamics, Lyapunov Exponents,
    and Empirical Gramians", 2024, arXiv, https://arxiv.org/abs/2402.14711 [read-abstract]
  - A. J. Krener, K. Ide, "Measures of unobservability", 2009, IEEE CDC. [unverified]
  - S. Lall, J. E. Marsden, S. Glavaski, "A subspace approach to balanced truncation for model reduction of nonlinear
    control systems", 2002, Int. J. Robust Nonlinear Control. [unverified]

### Phase reduction and phase response curves (PRC; direct and adjoint)
- **Core idea:** For an exponentially stable limit cycle of period T, each point in its basin has an asymptotic phase
  theta(x) (isochrons = level sets). Under weak input, d theta/dt = omega + Z(theta)^T p(t), where Z = grad theta on the
  cycle is the infinitesimal PRC (iPRC). **Direct method:** deliver a brief pulse of size eps in direction e_i at phase
  theta, simulate several periods, measure the asymptotic phase shift, divide by eps. **Adjoint method:** solve the adjoint
  linearised equation backward along the cycle with normalisation Z(theta) . F(gamma(theta)) = omega. The two coincide as
  eps -> 0 (as automated in XPPAUT; MatCont also computes PRCs; see Govaerts & Sautois 2006). Classical sources: Winfree,
  Kuramoto, Ermentrout & Kopell.
- **Assumptions:** Hyperbolic attracting limit cycle; weak perturbations (O(eps)); the perturbation relaxes back to the cycle
  faster than the next input (large Floquet gap). Otherwise use the augmented reductions below.
- **Identifiability:** Phase is defined up to a constant offset (choice of theta = 0). Z is unique given that.
- **Intervention support:** The PRC *is* an interventional quantity: it predicts the effect of any weak perturbation on
  timing. The full vector iPRC Z(theta) in R^N predicts responses to perturbations of *any* unit, so it tests
  generalisation to unseen intervention targets.
- **Nonlinear capacity:** Exact near the cycle, first order in input amplitude.
- **Interpretability:** Very high (1-D phase, PRC shape).
- **Scaling:** Direct method: N units x n_phase pulses x a few periods of simulation each. For N = 100 and 50 phases, 5,000 short
  runs, embarrassingly parallel. Adjoint: one backward solve (needs the Jacobian). Via autodiff through a differentiable
  simulator: Z is the gradient of the asymptotic phase w.r.t. the initial state.
- **Failure modes:** Pulse too large (nonlinear PRC, amplitude effects), or too small (numerical noise). Weakly attracting
  cycles (small |Floquet exponent|) break the phase-only model. Noise-induced phase diffusion. Multiple coexisting attractors.
- **Relevance to problem:** (3), (4), (7). When the macro dynamics include a limit cycle, a correct latent state must
  contain the phase, and the learned (phi, f) must reproduce the measured vector PRC for held-out perturbation targets.
  Isochrons give a direct test of microstate invariance: all microstates on one isochron must map to z with the same
  asymptotic future. PRCs are also implementation-independent descriptors (7).
- **Open-source implementations:** MatCont (MATLAB) - https://sourceforge.net/projects/matcont/ - updated 2026 -
  SourceForge lists "Public Domain", while other sources say "free for non-commercial use" (licence ambiguous; verify)
  [repo/docs]. XPPAUT (not checked; licence not verified). Direct method needs only the simulator.
- **From-scratch simplicity:** Simple (direct method). Pitfalls: define phase by a robust Poincare section crossing
  (interpolated), measure after >= 3-5 periods, use +/- pulses, check linearity in eps.
- **References:**
  - W. Govaerts, B. Sautois, "Computation of the phase response curve: a direct numerical approach", 2006, Neural
    Computation 18:817-847. [unverified] (search-result abstract only)
  - Scholarpedia "Phase response curve" (Canavier; attempted fetch failed - certificate error). [unverified]
  - A. T. Winfree, "The Geometry of Biological Time", 1980/2001; Y. Kuramoto, "Chemical Oscillations, Waves, and
    Turbulence", 1984; G. B. Ermentrout, N. Kopell, 1991 (adjoint). [unverified]

### Isostable coordinates, augmented phase(-amplitude) reduction and Koopman isostables
- **Core idea:** Augment phase with *isostable* coordinates psi_j: level sets of Koopman eigenfunctions with eigenvalues
  equal to the non-trivial Floquet exponents kappa_j, so d psi_j/dt = kappa_j psi_j + I_j(theta)^T p(t), where I_j is the
  isostable response curve (computable by an adjoint equation or by direct perturbation). Mauroy, Mezic & Moehlis (2013)
  define isostables for stable fixed points as level sets of the Koopman eigenfunction of the slowest eigenvalue, show that
  isostables and isochrons give action-angle coordinates, and compute them by Laplace averages along trajectories. Wilson &
  Moehlis (2016) extend this to periodic orbits. Wilson & Ermentrout (2018/2019, SIAM Review) develop augmented phase
  reduction for not-so-weak coupling. Monga & Moehlis (2020) give analytical augmented reductions near homoclinic
  bifurcations and for relaxation oscillators (small-magnitude Floquet exponents).
- **Assumptions:** Hyperbolic attractor (fixed point or limit cycle). Spectral gap: keep the slow isostables, discard fast
  ones. Local (basin-restricted) validity. Complex/degenerate eigenvalues complicate the picture.
- **Identifiability:** Koopman eigenfunctions are unique up to scale (and phase offset), given simple eigenvalues. This is
  one of the few settings where "canonical latent coordinates" are defined intrinsically, independent of the observation
  map. So they are a *gauge-fixed* reference for comparing latent spaces across implementations (7).
- **Intervention support:** Isostable response curves predict the effect of perturbations on amplitude/return; directly
  measurable by pulses.
- **Nonlinear capacity:** Exact within the basin in the Koopman sense. First-order reductions are accurate to O(eps). Higher-order
  (adaptive) variants handle larger inputs.
- **Interpretability:** Very high (phase + few decay-rate coordinates with physical time constants).
- **Scaling:** Laplace averages: many trajectories x long integration, parallel. Adjoint needs the Jacobian along the cycle.
- **Failure modes:** Slow non-dominant modes, where truncation is invalid. Near bifurcations (small kappa) the reduction degrades,
  which Monga & Moehlis address. Noise. Laplace averages converge slowly for eigenvalues close together.
- **Relevance to problem:** (1), (2), (5), (7). Phase + m slowest isostables is a *reference minimal Markov state* near an
  attractor, with k = 1 + m chosen by the Floquet/Koopman spectral gap. Learned z should be a diffeomorphic image of it
  (test by regression / conjugacy). The gap size itself is a principled "compact state exists" diagnostic (8).
- **Open-source implementations:** None checked (licence not verified).
- **From-scratch simplicity:** Moderate. Laplace averages are simple but slow. Adjoint/Floquet computation needs care
  (monodromy matrix, normalisation).
- **References:**
  - A. Mauroy, I. Mezic, J. Moehlis, "Isostables, isochrons, and Koopman spectrum for the action-angle representation of
    stable fixed point dynamics", 2013, Physica D 261:19-30,
    https://sites.engineering.ucsb.edu/~moehlis/moehlis_papers/isostables.pdf [read-abstract] (fetched PDF; only a
    summary was extracted)
  - D. Wilson, J. Moehlis, "Isostable reduction of periodic orbits", 2016, Phys. Rev. E 94:052213. [unverified] (fetch
    blocked; abstract seen only in search results)
  - D. Wilson, B. Ermentrout, "Augmented phase reduction of (not so) weakly perturbed coupled oscillators", 2019, SIAM
    Review 61(2):277-315. [unverified]
  - B. Monga, J. Moehlis, "Augmented Phase Reduction for Periodic Orbits Near a Homoclinic Bifurcation and for Relaxation
    Oscillators", 2020, arXiv, https://arxiv.org/abs/2005.11628 [read-abstract]

### Data-driven phase/amplitude and isostable estimation
- **Core idea:** Estimate asymptotic phase/amplitude functions and response curves from trajectories without equations.
  Namura et al. (2022): polynomial regression posed as a convex problem to fit phase and amplitude functions from time series,
  then design optimal entrainment inputs. Yamamoto, Nakao & Kobayashi (2024, GPPI): evaluate phase on the cycle, then extend
  it off-cycle by GP regression; robust to noise. Wilson (2021): infer isostable response functions and output maps from
  steady-state responses to sinusoidal forcing, from linear to higher-order expansions.
- **Assumptions:** Stable oscillation or fixed point. Low-dimensional observation (polynomial/GP regression in observed
  coordinates; low state dimension in the examples). Adequate sampling of the basin (initial states off the cycle).
- **Identifiability:** As above (phase up to offset, isostables up to scale).
- **Intervention support:** Wilson's approach uses designed sinusoidal inputs. Phase-function estimators use relaxation
  trajectories from varied initial states. The resulting models predict responses to new inputs.
- **Nonlinear capacity:** Moderate (polynomial/GP basis).
- **Interpretability:** High.
- **Scaling:** Polynomial regression blows up with dimension. GP scales as O(n^3) in samples. Both are fine in a small latent
  z, not in raw x of dimension 100+. Apply to learned z or to a PCA projection.
- **Failure modes:** High-dimensional x, poor basin coverage, and multiple attractors.
- **Relevance to problem:** Evaluation tool: apply the *same* phase/isostable estimator to (a) simulator microstates via
  direct perturbation and (b) the learned latent model, and compare PRCs/isostable response curves. It also gives an
  interpretable latent-model baseline for oscillatory regimes.
- **Open-source implementations:** None checked (licence not verified).
- **From-scratch simplicity:** Moderate.
- **References:**
  - N. Namura, S. Takata, K. Yamaguchi et al., "Estimating asymptotic phase and amplitude functions of limit-cycle
    oscillators from time series data", 2022, Phys. Rev. E 106:014204, https://arxiv.org/abs/2203.01663 [read-abstract]
  - T. Yamamoto, H. Nakao, R. Kobayashi, "Gaussian Process Phase Interpolation for estimating the asymptotic phase of a
    limit cycle oscillator from time series data", 2024, arXiv, https://arxiv.org/abs/2409.03290 [read-abstract]
  - D. Wilson, "Data-Driven Inference of High-Accuracy Isostable-Based Dynamical Models in Response to External Inputs",
    2021, arXiv, https://arxiv.org/abs/2102.04526 [read-abstract]

### Numerical continuation, bifurcation analysis and Poincare maps (attractor identification)
- **Core idea:** Track equilibria and periodic orbits as parameters vary (pseudo-arclength continuation). Detect bifurcations
  (fold, Hopf, period-doubling, torus, codim-2 points). Compute Floquet multipliers. Switch branches. Periodic orbits via
  shooting or collocation. A Poincare section reduces a flow to a map whose fixed points are cycles and whose Jacobian gives
  the Floquet multipliers.
- **Assumptions:** Access to the vector field (or a smooth simulator map) and its Jacobian. Smooth dependence on parameters.
  Deterministic dynamics.
- **Identifiability:** Invariant sets and bifurcation structure are coordinate-free (topological/conjugacy invariants).
  So they are ideal for comparing a learned f with the true system up to diffeomorphism.
- **Intervention support:** Parameters and constant inputs are continuation parameters. That gives "bifurcation diagrams under
  interventions" (e.g. constant input current into a unit, fraction of units removed).
- **Nonlinear capacity:** Full, local branch by branch.
- **Interpretability:** Very high.
- **Scaling:** Dense methods are fine up to ~10^3 dimensions. Matrix-free Newton-Krylov (BifurcationKit.jl) scales to large systems.
  Applying continuation to the *learned* low-dimensional f is cheap.
- **Failure modes:** Missing branches not connected to the starting point. Chaos (continuation needs periodic orbits).
  Non-smooth simulators. Learned NN vector fields may create spurious equilibria far from data.
- **Relevance to problem:** (3) and (7): a strong generalisation test. Compare the bifurcation diagram of learned (f, g) under
  a constant-input or parameter sweep *not in training* with that of the simulator (bifurcation types and parameter
  values; number/stability of attractors). Identical bifurcation structure across implementations supports a shared f (7).
- **Open-source implementations:**
  - BifurcationKit.jl (Julia) - https://github.com/bifurcationkit/BifurcationKit.jl - active, ~360 stars, 2,300+ commits;
    periodic orbits (shooting/collocation), Floquet, codim-2, deflated continuation, matrix-free, GPU - licence: MIT
    (unverified; not shown in fetch) [repo/docs]
  - PyDSTool (Python; PyCont + AUTO interface) - https://github.com/robclewley/pydstool - ~179 stars, maintenance
    appears slow (unverified) - BSD [repo/docs]
  - MatCont (MATLAB) - https://sourceforge.net/projects/matcont/ - updated 2026; equilibria, periodic and homoclinic
    orbits, normal forms, maps (MatcontM) - licence listed "Public Domain" on SourceForge, "free for non-commercial use"
    elsewhere [repo/docs]
  - AUTO-07p - not checked (licence not verified).
- **From-scratch simplicity:** Moderate for natural/pseudo-arclength continuation of equilibria. Hard for robust periodic
  orbit continuation and codim-2 detection: use a package.
- **References:** repos/docs above [repo/docs]; A. Dhooge, W. Govaerts, Yu. A. Kuznetsov, "MATCONT: a Matlab package for
  numerical bifurcation analysis of ODEs", 2003, ACM TOMS 29(2). [unverified]

### Fixed-point / slow-point finding and local linearisation (reverse engineering high-dimensional dynamics)
- **Core idea:** Find points where the speed q(x) = 1/2 |F(x)|^2 is zero (fixed points) or small (slow points / slow manifolds)
  by minimising q from many initial states drawn from visited trajectories. Linearise there (Jacobian eigendecomposition) to
  get local stable/unstable modes, line attractors, and saddles mediating transitions (Sussillo & Barak 2013). FixedPointFinder
  implements this for PyTorch/TensorFlow RNNs.
- **Assumptions:** Differentiable dynamics. Slow regions are dynamically relevant. Autonomous or constant-input dynamics
  (repeat for each input condition).
- **Identifiability:** Fixed points, their stability and eigenvalues are conjugacy-invariant. Eigenvectors transform with the
  coordinate change.
- **Intervention support:** Condition on constant inputs, or on the network after unit/connection removal. Compare how fixed
  points move or vanish.
- **Nonlinear capacity:** Local linearisation of a nonlinear system. Global topology is assembled from many local analyses.
- **Interpretability:** High.
- **Scaling:** Each optimisation costs O(N^2) per step (Jacobian-vector products). Hundreds of seeds. Fine for N <= 5,000.
- **Failure modes:** Missed fixed points (initialisation), spurious slow points, tolerance choices, and non-autonomous input
  dependence.
- **Relevance to problem:** Applied to both the simulator and the learned f: matching number, stability and eigenvalue
  spectra of fixed/slow points is an interpretable test of (3) and (7). The dimension of slow manifolds (number of near-zero
  eigenvalues) suggests k (5).
- **Open-source implementations:** FixedPointFinder - https://github.com/mattgolub/fixed-point-finder - ~108 stars,
  JOSS 2018 - Apache-2.0 [repo/docs]
- **From-scratch simplicity:** Simple (Adam/LBFGS on q, dedupe by distance, eigen-decomposition of the Jacobian). Pitfalls:
  q tolerance, deduplication radius, reporting slow points as fixed points.
- **References:**
  - D. Sussillo, O. Barak, "Opening the Black Box: Low-Dimensional Dynamics in High-Dimensional Recurrent Neural
    Networks", 2013, Neural Computation 25(3). [unverified] (fetch blocked; seen via search result abstract)
  - M. D. Golub, D. Sussillo, "FixedPointFinder: A Tensorflow toolbox for identifying and characterizing fixed points in
    recurrent neural networks", 2018, JOSS 3(31):1003; repo https://github.com/mattgolub/fixed-point-finder [repo/docs]

### Spectral submanifolds, normal forms and slow/center/inertial manifolds (SSM, SSMLearn)
- **Core idea:** For a hyperbolic fixed point (or periodic orbit) of a dissipative system, a spectral submanifold (SSM) is
  the smoothest invariant manifold tangent to a chosen spectral subspace (typically the slowest modes). Haller & Ponsioen
  (2016) prove existence/uniqueness under a spectral-quotient non-resonance condition and define NNMs and SSMs. Cenedese
  et al. (2022) learn SSMs from data: delay-embed observations, fit the manifold parametrisation (graph over tangent
  coordinates), then fit a sparse extended Poincare-Birkhoff normal form for the reduced dynamics. Models trained on
  *unforced decaying* trajectories predict *forced* responses (backbone curves, forced response curves). Related
  classical reductions: center manifolds (near bifurcation), slow manifolds (timescale separation), inertial manifolds
  (dissipative PDEs, global finite-dimensional attracting manifolds) (background, unverified).
- **Assumptions:** Hyperbolic attracting equilibrium or cycle with spectral gap. Smooth (analytic) nonlinearity. Non-resonance
  (spectral quotient). Data near the SSM (transients from initial conditions off it decay onto it). The forced-prediction
  step assumes small forcing with finitely many frequencies.
- **Identifiability:** The SSM is unique in the stated smoothness class. Normal-form coordinates are unique up to the normal form's
  residual symmetry (e.g. phase rotation). A strong canonical-coordinate result.
- **Intervention support:** Forcing is added a posteriori to the autonomous reduced model. State perturbations produce
  decaying trajectories, which are exactly the SSMLearn training data. Removing units/connections changes the fixed point, so the SSM
  must be re-learned or parametrised.
- **Nonlinear capacity:** Strong near an attractor (polynomial orders 3-7 typical). Not global. Not for chaos far from a
  fixed point (unverified extensions exist).
- **Interpretability:** Very high (normal-form coefficients, backbone curves, damping/frequency vs amplitude).
- **Scaling:** Works with high-dimensional observations via linear projection to tangent coordinates. SSM dimension usually
  2-6.
- **Failure modes:** Resonances, no spectral gap, multiple attractors, and trajectories that never approach the SSM. Delay
  embedding choice.
- **Relevance to problem:** (1), (2), (5), and a *canonical-coordinate reference* for (6)/(7). Near stable operating
  points, the slow SSM gives a minimal Markov state and a gauge-fixed normal form. "Learned on relaxations, tested on forced
  responses" is a ready-made held-out-intervention protocol. It is a tournament candidate for regimes dominated by one
  attractor.
- **Open-source implementations:**
  - SSMLearn (MATLAB) - https://github.com/haller-group/SSMLearn - active, ~121 stars - AGPL-3.0 [repo/docs]
    (full features need SSMTool and coco).
  - SSMLearnPy (Python) - https://github.com/haller-group/SSMLearnPy - ~41 stars, "under active development and may
    contain bugs" - GPL-3.0 [repo/docs]
  - SSMTool (equation-based SSM computation) - https://github.com/haller-group/SSMtool - licence not verified.
- **From-scratch simplicity:** Moderate. The basic recipe (PCA/tangent projection -> polynomial graph regression -> polynomial
  reduced dynamics fitted by ridge regression -> optional normal-form transform) is simple. Proper normal-form computation
  and resonance handling are harder.
- **References:**
  - G. Haller, S. Ponsioen, "Nonlinear normal modes and spectral submanifolds: existence, uniqueness and use in model
    reduction", 2016, Nonlinear Dynamics 86:1493-1534, https://arxiv.org/abs/1602.00560 [read-abstract]
  - M. Cenedese, J. Axas, B. Bauerlein et al., "Data-driven modeling and prediction of non-linearizable dynamics via
    spectral submanifolds", 2022, Nature Communications 13:872, https://arxiv.org/abs/2201.04976 [read-abstract]
  - Repos above [repo/docs]

### Evaluation of dynamical-systems reconstructions: attractor geometry, power spectra, Lyapunov spectra (DSR metrics, dysts)
- **Core idea:** For chaotic or long-horizon dynamics, pointwise MSE fails beyond the Lyapunov time. So evaluate
  *invariant/statistical* agreement between free-running model trajectories and ground truth. The Durstewitz group uses
  (i) D_stsp: KL divergence between the true and generated state-space occupation distributions (binning in low
  dimension, GMM along trajectories in high dimension), for geometric agreement, (ii) D_H: average dimension-wise Hellinger
  distance between smoothed power spectra, for temporal agreement, (iii) largest Lyapunov exponent / spectrum, plus
  fixed-point and topological-entropy comparisons (Hess et al. 2023; Brenner et al. 2024; Kramer et al. 2022). Gilpin
  (2021) provides dysts: 131+ chaotic ODEs annotated with known properties (e.g. Lyapunov exponents, dimension estimates),
  timescale-standardised sampling, and benchmarks correlating forecast error with degree of chaos. Its `metrics.py`
  implements sMAPE/MASE/MSE, horizon-wise metrics, GMM-based KL (`estimate_kl_divergence`, `geometrical_misalignment`),
  `average_hellinger_distance` on power spectra, DTW, and mutual information.
- **Assumptions:** Ergodicity/stationarity for invariant measures. Enough samples on the attractor. A common observation space
  (compare in y or in a fixed embedding, *not* in each model's own latent coordinates).
- **Identifiability:** Invariant-measure and spectral metrics are invariant to time shift and (for observables in y)
  to latent reparametrisation, so they fit latent models identified only up to transformation.
- **Intervention support:** Not native. Extend them by computing the same metrics on post-intervention free-running
  trajectories (e.g. attractor after unit removal, or under a new constant input).
- **Nonlinear capacity:** N/A (metrics).
- **Interpretability:** Moderate. D_stsp is sensitive to bin/GMM choices.
- **Scaling:** Binning is exponential in dimension. GMM KL scales well. Lyapunov spectra need Jacobians or QR-based
  estimation over long runs.
- **Failure modes:** D_stsp can be fooled by correct occupancy with wrong temporal order (use it with D_H and short-horizon
  error). Multistability: the metrics must be computed per basin / per initial condition. Transient-dominated regimes are
  poorly captured by invariant metrics. Lyapunov exponent estimates from data are noisy.
- **Relevance to problem:** (1) long horizons, (3) post-intervention attractor fidelity, (6) stability across seeds (spread of
  metrics), (7) compare implementations through observable-space statistics.
- **Open-source implementations:** dysts - https://github.com/williamgilpin/dysts - active, ~558 stars - Apache-2.0
  [repo/docs]. Durstewitz lab code (e.g. https://github.com/DurstewitzLab/CNS-2023) - not opened; licence not verified.
- **From-scratch simplicity:** Simple for D_H (Welch spectrum, Gaussian smoothing, normalise, Hellinger) and GMM-KL.
  Moderate for Lyapunov spectra (Benettin/QR with renormalisation; in learned models use autodiff Jacobians).
- **References:**
  - W. Gilpin, "Chaos as an interpretable benchmark for forecasting and data-driven modelling", 2021, NeurIPS Datasets &
    Benchmarks, https://arxiv.org/abs/2110.05266 [read-abstract]; repo https://github.com/williamgilpin/dysts and
    https://github.com/williamgilpin/dysts/blob/master/dysts/metrics.py [repo/docs]
  - F. Hess, Z. Monfared, M. Brenner, D. Durstewitz, "Generalized Teacher Forcing for Learning Chaotic Dynamics", 2023,
    ICML, https://arxiv.org/abs/2306.04406 [read-abstract]
  - M. Brenner, C. J. Hemmer, Z. Monfared, D. Durstewitz, "Almost-Linear RNNs Yield Highly Interpretable Symbolic Codes in
    Dynamical Systems Reconstruction", 2024, arXiv (NeurIPS 2024 (unverified)), https://arxiv.org/html/2410.14240
    [read-full] (main text; D_stsp and D_H defined as KL of state-space occupation and dimension-wise Hellinger distance
    of power spectra; detailed estimator settings are in its appendix, not read)
  - D. Kramer, P. L. Bommer, C. Tombolini et al., "Reconstructing Nonlinear Dynamical Systems from Multi-Modal Time
    Series", 2022, ICML (unverified venue), https://arxiv.org/abs/2111.02922 [read-abstract]

### Model-order-reduction evaluation under perturbations (balanced truncation error bounds, MOR benchmarks)
- **Core idea:** In linear MOR, balanced truncation to k states has an a priori H-infinity error bound of 2 * sum of the
  discarded Hankel singular values. This gives a *certified* input-output error for all inputs, and the singular value
  decay is a principled order-selection curve. For nonlinear/empirical versions no global bound holds, so reduced models
  are evaluated empirically on held-out input families (impulses, steps, chirps, random multisines at several amplitudes),
  on parameter variations, and on stability preservation. Community benchmark collections (MORwiki, SLICOT benchmarks)
  standardise this (unverified; not opened).
- **Assumptions:** LTI for the bounds. Stable systems.
- **Identifiability:** Balanced coordinates are unique up to signs (distinct HSVs).
- **Intervention support:** Input-output by construction. State perturbations enter as impulse inputs through B = I
  columns.
- **Nonlinear capacity:** Linear (bounds); empirical gramians extend it heuristically (see the gramian entry).
- **Interpretability:** High.
- **Scaling:** O(N^3) dense Lyapunov solves, fine for N <= 5,000. Low-rank ADI for larger N.
- **Failure modes:** Linearisation hides amplitude-dependent behaviour. Reduced models can be unstable in the nonlinear case.
  Evaluating only on the training input family overstates accuracy.
- **Relevance to problem:** (3), (5): the HSV curve of the linearised simulator at each operating point is a strong
  *reference for k*. Any learned latent model with k below the number of dominant HSVs should fail held-out input tests,
  and a learned model with much larger k is suspect (dimension cheating).
- **Open-source implementations:** python-control / slycot, pyMOR (not opened; licences not verified). emgr for empirical
  versions (BSD-2-Clause, above).
- **From-scratch simplicity:** Simple (scipy.linalg.solve_continuous_lyapunov / solve_discrete_lyapunov, square-root
  balancing). Pitfall: use the square-root algorithm, not an explicit inverse of the gramians.
- **References:** B. C. Moore, "Principal component analysis in linear systems", 1981, IEEE TAC; K. Glover 1984 (Hankel
  norm bound). [unverified]; emgr as above [read-abstract]/[repo/docs].

---

# Part II. Synthesis

The synthesis draws on the Part I entries and the per-area notes (Appendix). The notes do not cite by number; each claim
can be traced to the Part I entry for the named method, where its references are listed.

## II.1 Cross-cutting conclusions

### II.1.1 The target object already has a precise definition
Write Sim_h(x, u, a) for the law of the readout path y_{t+1:t+h} after starting from microstate x, applying the input
sequence u and the intervention a. Let 𝒯 be a bank of tests (u, a, h, readout functional). Then:

- **Predictive/interventional equivalence** (the target of (3) and (4)): x ~_𝒯 x' iff Sim_h(x, u, a) = Sim_h(x', u, a)
  in law for all tests in 𝒯. The name depends on the literature: Nerode equivalence in realisation theory (area A),
  causal states or predictive states (area C), bisimulation or lumpability for Markov processes (area C). If 𝒯 contains
  interventions, it is also the abstraction condition of causal-abstraction theory (area E: exact transformations,
  τ-abstraction). The ε-version replaces equality with a divergence below ε (MMD or W1 over simulator noise; a norm for
  deterministic simulators).
- **Closure (2)** follows for the exact relation. If x ~ x', their successors are equivalent in distribution: the
  quotient is Markov (bisimulation/unifilarity). For the ε-version, closure has to be *measured*, as quasi-lumpability
  spread or latent self-consistency. It cannot be assumed.
- **Minimality (5)** is the coarsest such relation. In coordinates, it is the smallest k for which a *smooth* encoder
  realises it. Linear case: Hankel rank. Finite case: number of causal states or automaton size.
- **Abstention (8)** means the required k (Hankel rank, number of causal states, required automaton size) keeps growing
  as ε shrinks or the horizon and test bank grow, up to a budget k_max. Chaotic regimes illustrate this: exact classes
  are singletons, so only (ε, H)-indexed equivalences make sense.
- **Interventional sufficiency for held-out types (3)** is the question whether ~_𝒯 implies ~_𝒯'. No general theory
  answers it (II.7); it must be tested on a held-out test bank 𝒯'.

The main practical consequence: **the simulator's reset ability turns (4) and (2) into directly testable statements**.
Draw pairs x, x' with phi(x) ≈ phi(x'), re-simulate both under identical u and a, and compare. Every family below should
be trained and evaluated against this ground truth, not only against held-out prediction error.

### II.1.2 What each literature contributes
- **Classical system identification and model reduction (A, G)** give exact answers for linear systems: Hankel singular
  values for minimality, similarity-invariant spectra and Markov parameters for (6) and (7), and designed excitation.
  They give the only *intervention-driven* choice of coordinates: empirical controllability and observability gramians
  built from exactly the perturbations the simulator allows. They are strong baselines, and they supply references and
  diagnostics for nonlinear methods.
- **Koopman/DMD/SINDy (B)** give cheap linear-in-features predictors and spectral invariants for comparison. They also
  give two closure tests: the ResDMD residual and operator inference's re-projection. Their hard limits:
  - a finite linear Koopman model that contains the state cannot represent multiple isolated attractors;
  - the lifted dimension is not k;
  - SINDy needs good coordinates first.
- **Predictive-state and bisimulation work (C)** supplies the definitions above, the spectral (Hankel/test-matrix)
  estimators, the counterexample-guided refinement loop (CEGAR, L*) and principled abstention signals.
- **Neural state-space models (D)** are the function classes and training tricks: multi-horizon rollouts, free bits
  and KL balancing, generalized teacher forcing for chaotic regimes, and stop-gradient latent self-prediction. None gives
  identifiability, minimality or interventional sufficiency, and many hide extra state (II.6).
- **Causal representation learning (E)** gives identifiability theory. At the macro level our micro interventions are
  unknown-target, multi-node and soft, so only the unknown-target/soft results fit even partially. Its most useful
  practical contributions are:
  - **interchange-intervention training and evaluation**, which directly operationalise (3) and (4);
  - **abstraction-error metrics**, which a 2026 paper validated on simulated systems (Méloux et al., arXiv 2607.00267,
    [read-full]; reports ~30 interventions per family for 95% power);
  - **multi-view block identifiability**, the only theoretical handle on (7).
- **Population-dynamics methods (F)** give low-rank RNNs, a rare family where micro interventions, including structural
  ones, are expressible natively. They also give the best-developed toolkit for comparing latent spaces and dynamics up
  to transformations, and the warning that bidirectional smoothers and inferred inputs are future and input leaks.
- **Experiment design and canonical coordinates (G)** turn the simulator into a source of **ground-truth probes**: direct
  phase response curves and isostable response curves, empirical gramians, Jacobians at fixed points, and bifurcation
  diagrams. They also give the budget and hold-out protocol, and invariant long-horizon metrics (D_stsp, D_H, Lyapunov
  spectra).

### II.1.3 Methods de-prioritised for the tournament, and why
These are de-prioritised on the contract properties, not on fashion. Several remain useful as baselines or diagnostics.
- **RSSM/Dreamer with its deterministic h, VRNN, and history-conditioned sequence models as state learners.** The carried
  history channel violates the closure and minimal-k accounting. Keep RSSM as a *history-based* baseline (II.4) and
  report k_effective = dim(h) + dim(s).
- **LFADS-style bidirectional encoders with inferred inputs.** They leak future information, and inferred inputs absorb
  unmodelled dynamics, which makes (2) and (3) untestable. Their generator with known inputs and a causal encoder is a
  variant of Family 1. The reference implementation has a non-commercial licence.
- **CITRIS/iCITRIS and linear interventional CRL (Squires et al.).** These need known macro targets, or perfect
  single-node macro interventions, which micro interventions do not provide. They are usable only inside Family 5, where
  macro interventions are *constructed* through realisers.
- **IRM.** Theory and critiques (Rosenfeld et al.) show that it does not reliably recover invariant features in the
  nonlinear regime. It can be a weak baseline.
- **VAMPnets/MSMs as the main learner.** The theory needs stochastic, (near-)stationary dynamics and has no input
  channel. Their Chapman-Kolmogorov test is still valuable as a closure diagnostic.
- **NARMAX/Volterra/GP-SSM.** These are input-output or history models, with poor scaling in the number of outputs.
  NARX on (y, u) history is used as the readout-history baseline.
- **CSSR and discrete automata learning as final models.** They are discrete and scale poorly to continuous
  high-dimensional x. They are valuable as abstention diagnostics on coarse-grained readouts (Family 8).

## II.2 Common interface and data protocol (applies to all families and baselines)

**Interface.** Every method must expose:
- phi: x(t) → z(t) ∈ R^k. It is instantaneous: no access to past or future beyond x(t). History variants are allowed
  only as labelled baselines, with the carried state counted in k.
- f: (z, u, [intervention code]) → z(t+dt). It may be stochastic.
- g: (z, u) → y.
- Optional: a declared intervention set, and an abstain flag with a confidence score.

**Fair k accounting.** k is the total dimension of everything carried between time steps: latent, hidden recurrent
state, and augmented or delay coordinates.

**Data.** Organised by factors: parameter draw p, implementation m, initial condition x0, input sequence u, and
intervention (type τ, target set S, amplitude, time t0). Area G's protocol:
- **Parameter draws.** 64-256 for training, 16 for validation, 32 for test, disjoint. For (7), also disjoint
  *implementations* of the same computation.
- **Initial conditions** from three sources, with the source recorded:
  - on-attractor: burn-in of at least 10 slowest time constants;
  - near-attractor: offsets at 3 amplitudes;
  - far: about 10% of the budget.
- **Inputs.**
  - Band-limited random multisines or filtered noise at 3 amplitudes; check that the input block-Hankel of the chosen
    depth has full rank.
  - Steps, pulses, chirps and zero input.
  - The u-generator family is recorded as a factor that can be held out.
- **Intervention types:**
  - state offsets on unit sets;
  - injected currents (constant, pulse, sinusoid);
  - unit removal;
  - connection removal;
  - global parameter shift.
- **Targets:** single units; random sets of 2, 5 and 10% of units; structured sets (e.g. top or bottom k by empirical
  controllability).
- **Amplitudes.** Three levels, calibrated per draw from < 5% to > 30% change in y.
- **Timing.** For oscillatory regimes, the intervention time is set relative to phase (8-16 phases).
- **Paired design.** Every perturbed run has an unperturbed twin with identical seed and initial state (clean effect
  estimates).
- **Budget allocation (fraction of total):**

  | Share | Use |
  |---|---|
  | ~35% | observational / input-driven runs |
  | ~25% | training interventions |
  | ~10% | probe measurements, used only for evaluation: PRCs, gramians, fixed points, bifurcation sweeps |
  | 10-20% | active or counterexample rounds |
  | ~15% | frozen held-out evaluation, plus an untouched final test set |

**Held-out splits.** Report each separately; never pool.
1. Within-distribution.
2. Held-out initial-condition source or basin.
3. Held-out targets, with the same intervention type.
4. Held-out intervention types (leave-one-type-out, including structural).
5. Held-out amplitudes, as extrapolation into the nonlinear regime.
6. Held-out input families.
7. Held-out parameter draws, and for (7) held-out implementations.
8. Held-out bifurcation regime.

Split by whole trajectories and whole parameter draws, never by time windows.

**Controls, needed to calibrate (5) and (8):** simulators or regimes with *known* answers:
- a linear or low-rank network with known state dimension;
- a network with a known low-dimensional attractor (e.g. a limit cycle) embedded in many units;
- a regime with a known non-compact state (high-dimensional chaos, or random coupling with a flat spectrum);
- a pair of different implementations of the same low-dimensional computation (for (7)).

Every threshold used for abstention or for choosing k is set on these controls, never on the test simulators.

## II.3 Tournament families

Selection criteria: direct targeting of (2)-(5); an honest route to (7) and (8); use of the simulator's reset and
intervention power; ability to run at N ≈ 100-5,000; availability of a checkable implementation. For each family: why it
is included, the recipe, the sweep, how k is chosen, and the main risks.

### F1. Closed latent dynamics, "encode once, roll out", with a ladder of transition classes
*Sources: area D candidate A/B, area B KAE-u and SINDy-AE-c, area C self-predictive objectives.*

- **Why.** This is the most direct parameterisation of the contract (phi, f, g). With an instantaneous encoder and
  open-loop rollouts, closure (2) and predictive sufficiency (1) are what the loss optimises. The f-class ladder gives an
  internal test of how much nonlinearity is needed. Interventions of the state-offset type are handled exactly by
  re-encoding.
- **Model.**
  - phi: an MLP N→512→256→k with LayerNorm. For N ≈ 5,000, use a linear N→64 layer followed by an MLP. Apply a
    spectral-norm or Lipschitz bound, and inject small Gaussian noise into z during training.
  - f, one rung of the ladder per run:
    - (a) linear, z' = Kz + Bu (Koopman AE; K parameterised as stable block-rotation × contraction);
    - (b) bilinear, B(z) = B0 + Σ z_i B_i;
    - (c) sparse polynomial, Θ(z,u)Ξ (SINDy-AE with control; sequential thresholding at 0.05-0.1 of standardised
      coefficients, then a final refit);
    - (d) switching or piecewise-linear (rSLDS/shPLRNN);
    - (e) residual MLP, z' = z + dt·MLP([z,u]), or a latent ODE with fixed-step RK4;
    - (f) the stochastic version of (e): Gaussian transition noise or a latent SDE.
  - g(z,u): linear first, then an MLP. Add an auxiliary low-weight decoder z→x to resist collapse.
- **Interventions.**
  - State offsets: z = phi(x+δ), then roll out.
  - Injected currents: map the N-vector of currents into a low-dimensional input code through a shared linear map P,
    u_int = P·I(t), so that unseen target sets remain expressible. Alternatively, pass the current through one simulator
    step and re-encode.
  - Structural interventions: either condition f on a descriptor d (ablation), or declare them outside the intervention
    set.
- **Loss.** Sum over horizons h ∈ {1,2,4,8,16,32,64} of:
  - readout NLL/MSE of g(f^h(phi(x_t), u), u);
  - λ_lat · ||f^h(phi(x_t)) − sg(phi(x_{t+h}))||² / Var(z);
  - low-weight reconstruction of x_{t+h}.

  Anti-collapse: a per-dimension variance floor. Variational version: free bits of about 1 nat, and KL balancing.
  Chaotic regimes: generalized teacher forcing, z̃ = (1−α)f(z) + α·phi(x_t), with α annealed from 1 to ~0.1-0.3; or
  multiple shooting with resets every ~ln2/λ_max. Counterexample pairs from F8 add a hinge term (below).
- **Sweep.** k ∈ {1,2,3,4,6,8,12,16,24,32} × 3-5 seeds × each f-class, plus the Lipschitz bound and the noise level.
- **Choosing k.** The smallest k whose held-out multi-horizon *and* held-out-intervention error is within 1 SE of the
  plateau reached by the full-state predictor. The equivalence gap (II.5, (4)) at that k must also be below threshold at
  the declared Lipschitz level. Report the whole curve.
- **Risks.** No identifiability (only equivalence up to diffeomorphism). Seed instability of nonlinear encoders.
  Dimension cheating without smoothness control. A linear f cannot handle multiple attractors, and the ladder exposes
  this. Structural interventions are unsupported.

### F2. Subspace and Koopman linear-operator identification with interventions as inputs
*Sources: area A (N4SID/CVA → EM, PSID), area B (DMDc, EDMDc + ResDMD + balanced truncation).*

- **Why.** This is the strongest non-deep competitor: deterministic, fast, interpretable, and with similarity-invariant
  outputs for (6) and (7). If it matches F1, deep encoders are not justified. It also supplies the k reference from the
  singular-value spectrum.
- **Recipe, variant (a): CVA-weighted subspace ID, then EM.**
  - Inputs: persistently exciting multisine or random-binary u on each input channel. State offsets are encoded as
    impulses on augmented input channels with known directions.
  - Outputs: (i) x, pre-projected to 100-200 PCs, and (ii) y alone. The output choice is itself a finding: states
    sufficient for x versus for y (PSID's n1 vs nx).
  - Past/future horizons p = f ∈ {5,10,20,40}, subject to T ≫ (p+f)(m+n_u).
  - Order from canonical correlations versus phase-randomised surrogates, Bauer-type criteria and the CV plateau.
  - Refine by EM with inputs (dynamax), initialised from the subspace estimate. Enforce stability.
  - Encoder: the regression from x to the Kalman state.
- **Recipe, variant (b): lifted Koopman.**
  - Pipeline: PCA to r ≈ 20-50; dictionary [1, PCs, K = 100-500 RBFs with k-means centres, optionally degree-2
    monomials]; ridge EDMDc with known B where available; discard modes with ResDMD residual > 0.1-0.2; balanced
    truncation to k.
  - Keep M/K ≥ 10-20.
- **Sweep.** Horizons, output set, ridge, dictionary size, RBF bandwidth, k.
- **Choosing k.** Singular-value/HSV elbow combined with the held-out multi-step plateau. Report both.
- **Risks.**
  - Linear or local only. Multiple attractors are impossible.
  - Data needs grow super-polynomially in n/m when only few outputs are available (Sun et al. 2025, stochastic case), so
    identify with x as output and evaluate on y.
  - Closed-loop bias if inputs depend on outputs.

### F3. Interventional empirical-gramian balanced reduction with learned nonlinear closure
*Sources: area A candidate 1, area G candidate 2 (Lall-Marsden-Glavaski empirical gramians, emgr).*

- **Why.** This is the only classical method whose coordinates are chosen *jointly* by:
  - what interventions can move (empirical controllability, from exactly the simulator's allowed perturbations);
  - what the readout can see (empirical observability, from ± state offsets observed through y over a horizon).

  Directions with low observability energy are, by construction, those with equal futures, which is prop (4). The
  Hankel singular values give (5). A linear phi is hard to cheat and stable across seeds (6).
- **Recipe.**
  - Operating points: 4-8 per parameter draw (on- and near-attractor).
  - Controllability ensemble: impulses into each input channel and a subset of unit directions, at 2-4 scales.
  - Observability ensemble: ±ε offsets along all N unit directions (2N runs) or along a random/PCA subset, with output y,
    and separately output x.
  - Compute W_c and W_o (or the cross gramian), average over operating points, balance by square-root SVD, and set
    phi = top-k balanced coordinates.
  - Fit f(z,u) by a small MLP or SINDy on projected trajectories, or by Galerkin projection if the simulator's vector
    field is accessible.
- **Sweep.** ε ∈ {1e-3, 1e-2, 1e-1} × state s.d. (report linearity checks); operating-point set; output choice;
  horizon; f-class.
- **Choosing k.** HSV elbow, confirmed by the multi-horizon/intervention plateau.
- **Risks.**
  - A single global linear subspace is chosen from local information: a curved slow manifold needs larger k.
  - Deterministic regime assumed (noise requires averaging).
  - Cost is O(N) runs per operating point. This is cheap for a simulator, but check memory at N = 5,000 (low-rank and
    cross-gramian options in emgr).

### F4. Microstate predictive-state regression on a probe bank (PSR / kernel causal states with resets)
*Sources: area C candidates 2-3 (spectral PSR, two-stage regression, HSE-PSR, kernel ε-machines), area A (Hankel/Nerode),
area F (reduced-rank regression).*

- **Why.** This is the most literal estimator of the equivalence relation in II.1.1. Microstates are resettable, so the
  estimator can regress x directly onto the law of its futures under a fixed probe bank. Histories are not needed. The
  rank of that map is the test-matrix rank, a principled estimate of (5), and absence of a spectral gap is an abstention
  signal (8). It is cheap, deterministic and scalable.
- **Recipe.**
  - Sample microstates x_i (the three IC sources).
  - For each x_i, simulate a probe bank 𝒯: 32-64 input sequences (steps, pulses, noise, zero) and a few training
    intervention types, at horizons {1,5,20,50} steps, with R noise seeds if the simulator is stochastic.
  - Record future-readout features: y windows, moments, or random Fourier features. This gives Φ_future (n × m).
  - Fit reduced-rank ridge regression x → Φ_future, sweeping the rank k. The left factor is a linear phi.
  - Nonlinear variant: random features or Nyström kernel on x, with a diffusion-map reduction of the conditional mean
    embeddings (kernel causal states).
  - Fit the transition f by two-stage regression: next predictive state on current predictive state × input features.
- **Choosing k.** Held-out predictive loss plateau, combined with the singular-value gap. Report the spectrum.
- **Sweep.** Probe-bank family and size (the key hyperparameter: equivalence is relative to 𝒯), horizons, ridge, feature
  map, kernel bandwidth.
- **Risks.**
  - Relative to 𝒯: held-out intervention types need a *different* 𝒯' at evaluation.
  - The linear version captures only linear predictive structure.
  - Kernel versions scale as O(n²) without Nyström.
  - Stochastic simulators need many seeds per state.

### F5. Interchange-intervention-trained abstraction (IIT/DAS adapted to dynamics)
*Sources: area E candidate T2 and Recipe B (Geiger et al. IIT/DAS; causal abstraction theory; causal feature learning),
area C (must-separate pairs).*

- **Why.** This family optimises (3) and (4) *directly*, with the simulator in the loop. It checks that setting
  z-coordinates to new values produces the micro futures the macro model predicts, whichever microstate realises them.
  It is also the family most naturally extended to (7): cross-implementation interchange.
- **Recipe.**
  - Start linear: z = Wx, with W orthogonally parameterised (DAS-style), plus f and g.
  - Interchange loss:
    - sample a base x_b, a source x_s and a coordinate subset S;
    - set the target z* = z_b with the S-coordinates taken from z_s;
    - build the realiser x* = x_b + W⁺P_S W(x_s − x_b), a minimum-norm state offset (supported by the simulator);
    - simulate H steps under the same u;
    - penalise ||phi(x*(t+h)) − f^h(z*)||² and ||y*(t+h) − g(f^h(z*))||².
  - Null-space faithfulness pairs: x_b + (I − W⁺W)δ must leave y and phi(future) unchanged.
  - Nonlinear phi: realisers by Gauss-Newton projection onto {phi(x) = z*}. Use several realisers per z* (minimum-norm,
    nearest pool state, and minimum-norm plus a random null-space component).
  - Combine with the F1 multi-horizon loss.
- **Sweep.** k, H ∈ {1..50}, null-space weight, realiser type, share of on-manifold (pool) realisers.
- **Choosing k.** The smallest k with realiser-spread and null-space ratio below the calibrated thresholds *and*
  held-out interchange error at the plateau.
- **Risks.**
  - Simulator calls inside training: batch and cache them.
  - Off-manifold realisers can pass or fail for the wrong reasons, so report on-manifold realisers separately.
  - Unrealisable z* must be counted.
  - Output-only interchange accuracy is not certification: intermediate z can still be wrong (Méloux et al.).

### F6. Unit-space low-rank RNN models (structural interventions expressible natively)
*Sources: area F candidate 1 (Mastrogiuseppe & Ostojic; Dubreuil et al.; LINT, Valente et al.; stochastic/SMC low-rank
RNNs).*

- **Why.** Among the reviewed families, this is the one where **all** micro intervention types act on the model's own
  variables:
  - offsets and currents act on units;
  - removal of a unit deletes a row and column of the connectivity;
  - removal of a connection edits one entry of the low-rank factors.

  The latent state is the projection onto the column space of the rank-R connectivity (plus input directions), and
  k = R + (input dims), which makes the rank a clean minimality knob (5).
- **Recipe.**
  - Fit τẋ = −x + (1/N)·M Nᵀ φ(x) + W_in u (rank R) to simulator rollouts: all unit activities and y, open-loop
    multi-horizon MSE from the true x0, through BPTT with GTF for chaotic regimes.
  - Data: random x0 (not only on-attractor), random piecewise-constant u, and training interventions.
  - phi(x) = least-squares projection onto span(M). f = the reduced latent ODE.
  - Structural-intervention test: apply held-out removals to the fitted connectivity and compare with the simulator.
- **Sweep.** R = 1..10, nonlinearity, noise, and implementation mapping (units may not correspond across
  implementations; for (7), use per-implementation M and N with a shared reduced f).
- **Choosing k.** The smallest R at which held-out multi-horizon and held-out-intervention errors plateau.
- **Risks.**
  - It assumes the simulator is well approximated by a low-rank network in unit space. It may need large R even when a
    compact state exists through nonlinearity, and the literature does not characterise this.
  - It needs full unit observations.
  - Fitting is non-convex.

### F7. Multi-encoder shared-dynamics training (one f, implementation-specific phi_m)
*Sources: area E candidate T3 (multi-view/content-style block identifiability; contrastive identifiability; CEBRA
multi-session), area F (lfads-torch multi-session scheme, cross-prediction), area B (shared K/Ξ).*

- **Why.** Property (7) is not addressed by any single-system method. This family puts it in the objective:
  - M implementations are run on identical u sequences;
  - per-implementation encoders phi_m and readouts g_m (or a shared g if the readout is common);
  - a single f.

  Multi-view block identifiability gives the only available theory: the shared content is recovered up to an invertible
  map when views share it. The prediction loss then ties the *dynamics*, not just the state, across implementations.
- **Recipe.**
  - Training: the F1 loss summed over implementations with a shared f, plus InfoNCE alignment between
    phi_a(x^a_t) and phi_b(x^b_t) at the same t and the same u. Also include *equal-u, different-x0* negatives, so that z
    cannot just encode u.
  - Similarity: L1 or Lp (p ≠ 2) similarity if an axis-aligned gauge is wanted; cosine similarity leaves an orthogonal
    ambiguity.
  - Evaluation, a held-out implementation test: freeze f, train only a new encoder on *observational* data of a new
    implementation, then test on its interventions (split 7 of II.2). Also run cross-implementation interchange (F5) and
    check swap symmetry.
- **Sweep.** k, alignment weight, temperature, time offsets, shared versus per-implementation g.
- **Choosing k.** As in F1, but on the held-out-implementation test.
- **Risks.**
  - Theory covers the shared state, not shared dynamics.
  - If the implementations' futures are not identical given equal u, alignment forces spurious sharing, so the family
    needs the abstention branch: compare against per-implementation f and report the gap.

### F8. Counterexample-guided refinement, active design and abstention wrapper (CEGAR-Z)
*Sources: area C candidate 1 (CEGAR, L*, CSSR split tests, bisimulation metrics), area G candidate 3 (BOED, ensemble
disagreement), area B (E-SINDy active learning), area E (causal feature learning's split/merge).*

- **Why.** This is not a model class. It is a loop that wraps F1-F7 and uses the simulator as an *equivalence oracle*.
  It is the natural mechanism for (4) and (2), and the only principled route to abstention (8). Every refinement is
  explained by a concrete distinguishing experiment, which is also interpretable.
- **Recipe.**
  1. Train an ensemble of 5 (phi, f, g) from any family.
  2. **Invariance counterexamples:**
     - take nearest-neighbour pairs in z;
     - search adversarially for x' = x + v, optimising v with CMA-ES or simulator gradients to maximise future-readout
       divergence minus λ||phi(x+v) − phi(x)||;
     - optionally optimise u as well, falsification-style.
  3. **Closure counterexamples:**
     - (x, u) where the rollout g(f^h(phi(x))) disagrees with the simulator by more than ε;
     - (x, u) where phi(x_{t+h}) disagrees with f^h(phi(x_t)) by more than ε;
     - (x, u) where the ensemble disagrees most (an expected-information-gain proxy).
  4. **Validate** each candidate by re-simulation with R = 20-50 noise seeds and an MMD permutation test, with
     multiple-testing control. For deterministic simulators, require stability to the integrator step.
  5. **Refine:**
     - add the distinguishing test to the bank;
     - add must-separate pairs (hinge max(0, m − ||phi(x) − phi(x')||)) and training data;
     - retrain from a warm start;
     - if the counterexamples cannot be separated at the current k without losing fit, set k ← k+1, initialising the
       new coordinate on the residual direction;
     - symmetric **merge** step: pull together pairs that are far apart in z but indistinguishable on all tests, and
       prune coordinates that are unused.
  6. **Stop** when a budget B (10³-10⁴ simulations; 10-20% of the total budget) finds no validated counterexample.
     Random tests give a PAC-style statement; adversarial search does not. Report both.
  7. **Abstention.**
     - Sweep ε and H_max and plot the required k(ε, H). A plateau gives k.
     - No plateau up to k_max, or failure of the Markov test at every k, gives **abstain**. Report the curve and the
       failing counterexamples.
     - Coarse-grained CSSR or L* state counts versus resolution serve as an independent abstention diagnostic.
- **Sweep.** ε, δ, H_max, test-bank families, Lipschitz bound, oracle budget, seeds.
- **Risks.**
  - No completeness or termination guarantees for continuous systems.
  - Oracle overfitting: use a *different* oracle and seed stream for evaluation than for training.
  - Active sampling oversamples far-from-attractor states, so report metrics per IC source.

### Tournament logistics
- Run each family through the same harness (II.2) and the same evaluation battery (II.5), with an identical simulation
  budget. F8 wraps F1, F5 and F7 in a second round.
- Minimum reporting per family:
  - for each k: the multi-horizon curves per held-out split, closure gap, equivalence gap, realiser spread, and
    stability across 5 seeds;
  - the chosen k with its selection rule;
  - the abstention decision on the control simulators.
- Rank families by a **property profile**, not a single score. The contract properties are not commensurable.

## II.4 Baselines and how to implement each well

Every baseline goes through the same interface (phi, f, g), the same k sweep and the same splits. Numbers are starting
points from the area notes; tune them on validation data only.

| # | Baseline | Implementation advice | Common mistakes | Packages (licence) |
|---|---|---|---|---|
| 1 | **PCA + linear dynamics** | Standardise units with training statistics only. PCA for k. Ridge-regress z_{t+1} = Az + Bu + c with CV ridge. Evaluate *free-run* multi-horizon, not one-step. Add a delay-PCA variant to separate variance from memory. | One-step evaluation only; PCA fitted on test data; ignoring the spectral radius | scikit-learn (BSD-3) |
| 2 | **Factor analysis (+ LDS)** | FA to initialise C and R, then LDS-EM with inputs, initialised from N4SID. Stop EM on held-out log-likelihood. Floor the Q and R eigenvalues (~1e-6·trace/k). Pair FA/GPFA (no transition law) with a fitted AR on the latents. | Random EM init (local optima); unstable A | dynamax (MIT), ssm (MIT), Elephant GPFA (BSD-3) |
| 3 | **DMD** | Centre the data. Choose rank by energy knee *and* held-out multi-step error. Report eigenvalues as log(λ)/dt. Use fbDMD/BOP-DMD if readouts are noisy (noise biases eigenvalues towards damping). | Interpreting damping from noisy data; rank by energy only | PyDMD (MIT) |
| 4 | **EDMD / Koopman** | PCA to 10-30 first. Dictionary [1, PCs, 50-500 k-means RBFs, optional quadratics], standardised. Ridge or truncated-SVD solve, with M/K ≥ 10-20. ResDMD residual filtering, and eigenvalue persistence as K and M grow. With inputs: EDMDc (Korda-Mezic). | Counting lifted dimension as k; spectral pollution | pykoopman (MIT), PyDMD (MIT), deeptime (LGPL-3.0) |
| 5 | **Hankel / delay methods** (Hankel DMD, HAVOK, ERA) | Delays d with d·dt of 1-2× the slowest relevant timescale, chosen on a validation curve. SVD rank r. Split by trajectory *before* building the Hankel. Causal (past-only) delays. HAVOK needs forcing, so it is not a closed model; use Hankel DMDc as the closed baseline. ERA from paired-difference impulse responses. | Overlapping windows leaking across the split; centred delays | pykoopman, PyDMD, python-control ERA (BSD-3) |
| 6 | **Linear SSM identification** (LDS-EM / PEM) | Initialise from subspace ID. Inputs via B u_t. Check the spectral radius. Select k by held-out likelihood *and* multi-step error. | EM from random init; overfitting noise covariances | dynamax (MIT), ssm (MIT) |
| 7 | **N4SID-style subspace ID** | CVA weighting. Pre-whiten; pre-project outputs to 100-200 PCs if m is large. Check persistency of excitation (rank and condition of the input block Hankel). Order from canonical correlations versus surrogates plus the CV plateau. Enforce stability. Use SSARX/PBSID variants if inputs are closed-loop. | Closed-loop bias; horizons too short for slow modes | nfoursid (MIT), SIPPY (LGPL-3.0), python-control/Slycot (BSD-3/GPLv2), MATLAB n4sid (commercial) |
| 8 | **SINDy / SINDYc** | On PCA or balanced coordinates, with standardised library columns, degree 2 first. Use exact simulator derivatives, or weak-form derivatives. Sweep the threshold on a log grid and pick the knee of held-out *simulation* error. E-SINDy (q = 100 bootstraps, inclusion 0.6) for uncertainty. Inputs open-loop. | Threshold chosen by fit, not rollout; feedback-correlated inputs (ill-conditioned) | PySINDy (MIT) |
| 9 | **Autoencoder + linear latent dynamics** | MLP encoder, z_{t+1} = Az + Bu with A initialised near identity and stably parameterised. MLP decoder to y and x. Multi-horizon loss. Locally-linear A(z) as a step up. | One-step training; unconstrained A diverging in rollouts | from scratch (PyTorch/JAX) |
| 10 | **Koopman autoencoder** | Pretrain the AE. Multi-step loss with a horizon curriculum from 5 to 50+. Latent consistency ||phi(x_{t+m}) − K^m phi(x_t)||. Stable K. Early stopping on held-out rollouts. ≥ 5 seeds; report the eigenvalues of K across seeds. Consistent-KAE only for invertible dynamics. | Treating eigenfunction sets as unique; seed variance | DLKoopman (MIT), DeepKoopman (MIT) |
| 11 | **Latent neural ODE** | Encoder phi(x(t0)) only, not an ODE-RNN over the window. Fixed-step RK4 at the model dt with direct backprop. Piecewise-constant u. Kinetic or Jacobian regularisation if NFE grows (unverified recipe). | Future-leaking window encoder; adjoint instability on dissipative latents | diffrax (Apache-2.0), torchdiffeq (MIT) |
| 12 | **Recurrent state-space model** | GRU h of 128-256, Gaussian s of dim k, actions = [u, intervention code], free bits of 1 nat, KL balance (V3: dynamics 1 / representation 0.1). **Report k_nominal = dim(s) and k_effective = dim(h) + dim(s).** Two evaluations: history burn-in (a history baseline) and closed start from phi(x(t0)). | Crediting RSSM with k = dim(s) | DreamerV3 (MIT) or own implementation |
| 13 | **Variational SSM** (DKF/DMM) | Pyro DMM structure, but with a *filtering or single-frame* encoder at evaluation, not the backward smoother. KL annealing over the first 10-20% of training; clamp log-variances. Use the transition-noise level as an abstention signal. | Evaluating with the smoother (future leakage); posterior collapse | Pyro (licence not verified), dynamax |
| 14 | **Predictive state representations** | Microstate version: F4 with a fixed probe bank and linear reduced-rank regression. History version: spectral TPSR with input-conditioned blocks and a ridge pseudoinverse. Choose k by held-out multi-step error, not a fixed SV threshold. Report the full spectrum. | Choosing the probe bank post hoc on test interventions | from scratch (numpy); no maintained package found |
| 15 | **Sequence model with bottleneck** | S5, LRU, GRU or transformer decoder that receives only (z = phi(x(t0)) ∈ R^k, u_{t0:t0+H}) and emits y. Same k sweep. Tests (1) and (5) only: the decoder carries state, so it is *not* a closure test. Pair with no-z (input-only) and history versions. | Reporting it as a closed-state model | S5, minimal-LRU (MIT), mamba (Apache-2.0) |
| 16 | **Random projection** | phi = random Gaussian N→k (rows orthonormalised) with f and g trained exactly as in F1. The null for "does learning phi matter?" and for every similarity measure. | Omitting it; it is often surprisingly strong for linear readouts | from scratch |
| 17 | **Input-only predictor** | f and g see only u (z fixed or learned constant). Measures input copying: the credit any model gets for input-locked responses. | Omitting it on strongly driven regimes | from scratch |
| 18 | **Readout-history-only predictor** | GRU or NARX (SysIdentPy FROLS with AIC/BIC) on past (y, u) windows of matched length. Bounds what a microstate encoder must beat. Also include "persist y". | Letting it use future u beyond the prediction step | SysIdentPy (BSD-3) |
| 19 | **Full-state predictor** | The same f class with phi = identity (or PCA at 95-99% variance) and ridge VAR / MLP. The ceiling for (1)-(3), and the reference for closure ratios. | Under-regularised at N = 5,000 (use PCA or ridge) | from scratch |

## II.5 Evaluation measures for properties (1)-(8)

General rules:
- Compute every measure on held-out splits (II.2), separately per split.
- Normalise against the baselines: full-state as ceiling; input-only, readout-history-only and persistence as floors.
- Compute measures only on gauge-invariant quantities: y, the model's own lift phi(Sim(...)) compared with f's
  prediction, or z after aligning within the transformation class the method claims, with the alignment fitted on
  training data.

| Property | Primary measures | Secondary / diagnostic |
|---|---|---|
| **(1) Predictive sufficiency** | Open-loop multi-horizon NLL/MSE of y at h ∈ {1,5,20,100}·dt plus multiples of the slowest time constant / Lyapunov time, as fractions of the gap between floor and full-state ceiling. Valid prediction time. | For chaotic or long horizons: D_stsp (state-space KL; GMM in higher dimensions), D_H (power-spectrum Hellinger), largest Lyapunov exponent, attractor count per draw (dysts `metrics.py`). InfoNCE estimate of I(z_t; y_{t:t+H}) versus I(x_t; y_{t:t+H}). |
| **(2) Markov closure** | **Closure gap**: error of the open-loop rollout f^h(phi(x_t)) versus the refreshed rollout f(phi(x_{t+h−1})). **Semigroup check** ||f^{a+b}(phi(x_t)) − f^b(phi(x_{t+a}))|| / spread(z). **History gain**: improvement when adding z_{t−1..t−p} or x_t to f; it should be ≈ 0 by a held-out test. | Chapman-Kolmogorov test (VAMP/MSM). Operator-inference re-projection gap. ResDMD residual of phi as a dictionary. Residual independence tests of z_{t+1} − f(z_t, u_t) against lagged z, y and random micro projections (PCMCI or partial correlation). ε-quasi-lumpability spread on discretised z. |
| **(3) Interventional sufficiency** | Held-out-target and held-out-type errors on post-intervention trajectories, as **effect-normalised error** err / D(y_intervened, y_unintervened) (no credit for predicting the unperturbed path). ≥ 30 interventions per family (Méloux et al.), preferably 100+ with bootstrap CIs. **Interchange error** (F5 recipe) with ≥ 3 realisers. | Match of directly measured probe quantities never used in training: vector phase response curves and isostable response curves (model perturbed through Jacobian(phi)), bifurcation diagrams under unseen constant inputs, and principal angles between phi's row space and the empirical-gramian balanced subspace. Structural interventions reported separately, and allowed to fall outside the declared intervention set. |
| **(4) Microstate invariance** | **Equivalence gap curve**: E[D(future | x), D(future | x')] over pairs with ||phi(x) − phi(x')|| < δ, as a function of δ, relative to random pairs. Pairs from (a) near neighbours in a large state bank, (b) null-space perturbations of phi, (c) adversarial search (F8, with a separate evaluation oracle). **Realiser spread** in interchange tests. **Null-space ratio**: effect of a null-space perturbation divided by the effect of an equal-norm range-space perturbation (should be ≈ 0). | Collapse check: states on the same isochron or spectral-submanifold fibre (same asymptotic future by construction) should map to nearby z. Directions with low empirical observability energy should lie in phi's null space. |
| **(5) Minimality** | The smallest k meeting pre-registered thresholds for (1)-(4), from the full k-curve with seed error bars, at a *declared* encoder Lipschitz or noise level. | Comparison with reference k from: HSV spectrum, Koopman/Floquet spectral gap, SSM dimension, test-matrix (Hankel) rank, DCA I_pred(d) plateau, kernel causal-state gap, PSID n1 versus nx. Effective rank and per-dimension variance of z (unused dimensions). Fisher-information rank of the fitted model. Intrinsic-dimension estimators (TwoNN, MLE) give only a *state-cloud* dimension: a lower-bound sanity check, not a closed-state dimension. |
| **(6) Stability** | Across ≥ 5 seeds, data subsets and estimators, *in the invariance class the method claims*: principal angles (linear phi); linear/affine cross-prediction R² (both directions); Procrustes/shape metric (netrep, cross-validated alignment); MCC for elementwise claims. Invariants of f: continuous-time eigenvalues (Hungarian-matched), fixed-point count and type, Jacobian spectra, Lyapunov exponents, D_stsp/D_H between rollouts. | Debiased CKA with shuffled and random-network nulls, as a secondary check. Report between/within ratios, not raw scores. |
| **(7) Shared across implementations** | **Held-out-implementation test**: freeze the shared f, fit only a new encoder on observational data, test on that implementation's interventions. **Cross-implementation interchange** with swap symmetry. **Cross-prediction of dynamics**: the map z_A → z_B conjugates f_A into a predictor of z_B's future. Comparison against per-implementation f: the gap is the cost of sharing. | Coordinate-free invariants compared across implementations: spectra, bifurcation diagrams, phase response curves, Lyapunov spectra, normal-form coefficients, fixed-point topology. InputDSA and Koopman-spectrum conjugacy tests as necessary-condition checks. Calibrate against a known different-f control. |
| **(8) Abstention** | Pre-registered rule, calibrated on control simulators (II.2): abstain if no k ≤ k_max meets the (1)-(4) thresholds, or if k(ε, H) grows without a plateau, or if the history gain in (2) stays significant at every k. Score abstention as a classifier on controls with known answers (ROC/AUC; false-abstain and false-accept rates). | No HSV, VAMP or canonical-correlation gap. No residual-certified spectrum. Learned transition noise not falling with k. Causal-state or automaton counts exploding with resolution. Predictive information growing with window length. High Kaplan-Yorke dimension. |

**Minimum dimension-cheating guard (applies to (5) and every k claim).**
- Report each k together with (i) the encoder and transition Lipschitz bounds or spectral norms, and (ii) a
  **noise-robustness curve**: prediction error when Gaussian noise of scale σ·sd(z) is added to z. It should degrade
  gracefully, not catastrophically.
- Check that linear-alignment scores are not far below nonlinear-alignment scores across seeds, because a large gap
  suggests a pathological encoding.

## II.6 Pitfalls and countermeasures

| Pitfall | How it arises | Countermeasure |
|---|---|---|
| **Time leakage** | Random splits over windows or lagged pairs from the same trajectory. Hankel matrices built before splitting. Absolute time or time-since-onset channels (e.g. neural CDE time channel). | Split by whole trajectory and parameter draw. Build delay matrices after splitting. Use time increments only; randomise window start times. |
| **Future leakage** | Bidirectional or smoothing encoders (DKF/SRNN smoothers, LFADS, NDT, GPFA smoothing, latent-ODE window encoders, natural cubic splines). Centred delays. Probe measurements on test draws used for model selection. Future inputs u_{k+1} in DMDc regressions. | Instantaneous or causal encoders only for evaluation. Probe data restricted to training draws for anything touching model selection. Audit every regression for the time index of its regressors. |
| **Output copying** | y in x or y-history fed to f or g; D-terms; one-step metrics. | Multi-horizon free-run evaluation. Readout-history and persistence baselines. Mask y in similarity computations. |
| **Input copying** | g(z, u) predicting input-locked responses; contrastive positives defined by equal u; inferred inputs absorbing dynamics; unconstrained B. | Input-only baseline and gain over it. Equal-u, different-x0 pairs. Held-out input families. Forbid u_t inside phi. |
| **Parameter-identity leakage** | Different parameter draws occupy separable regions of x; the encoder memorises the draw; episode-level negatives; IC or input statistics differing by draw. | Held-out draws for all evaluation. Probe decodability of the draw ID from z. Identical IC and input generators across draws. Equivalence pairs (4) from the same draw unless parameters are part of the state. |
| **Memorisation** | Kernel DMD and kernel PSRs act as lookups over training samples; deep encoders fit trajectory quirks. | New IC sources and basins at test. Frozen, unseen final test set. |
| **Dimension cheating** | Space-filling or high-Lipschitz phi; history channels not counted (RSSM h, VRNN feedback, CPC context, sequence decoders, KVAE mixture LSTM); lifted dictionary dimension reported as k; products of Koopman eigenfunctions counted as independent. | Count all carried state in k. Lipschitz or spectral-norm limits and noise injection. Noise-robustness curves. Count only truncated or independent coordinates. |
| **Collapse** | Self-prediction without decoder or anti-collapse term; KL posterior collapse. | Readout loss always on; variance floors; free bits; monitor effective rank. |
| **Oracle / evaluation overfitting** | The same counterexample generator used for training and evaluation. | A separate oracle, seed stream and budget for evaluation. |
| **Realiser artefacts** | Minimum-norm realisers pushing x off-manifold. | Report pool (on-manifold) realisers separately; Mahalanobis gate; count unrealisable z*. |
| **Perturbation-scale artefacts** | PRC and gramian estimates depend on ε. | Linearity checks (ε versus 2ε within 5%). Report scale. |
| **Invariant-metric gaming** | D_stsp satisfied with the wrong temporal order; metrics pooled across basins. | Pair with D_H and short-horizon error; compute metrics per basin. |
| **Similarity-measure artefacts** | CKA bias for p ≫ n and dominance of high-variance directions; CCA saturation at high k with autocorrelated samples; geometry-only measures blind to f; DSA's orthogonal alignment is neither necessary nor sufficient for conjugacy (Godara et al. 2026, per area F). | Battery of measures with calibrated nulls; held-out evaluation of alignment; always pair geometry with dynamics measures. |
| **Theory-assumption mismatch** | VAMP on deterministic dynamics; consistent KAE on dissipative dynamics; identifiability theorems assuming invertible mixing or independent innovations; PE theory for LTI only. | Treat theory-derived guarantees as hypotheses, and test them on control simulators. |
| **Closed-loop bias** | Inputs computed from outputs (feedback) in SID or SINDy. | Open-loop, persistently exciting inputs, or SSARX/PBSID. |
| **Licence traps** | Non-commercial or copyleft code: lfads-torch (non-commercial research), DBC (CC-BY-NC, archived), SSMLearn (AGPL-3.0), GTF-PLRNN (GPL-3.0), tigramite (GPL-3.0), PyPSID (custom research licence), CEBRA < 0.4.0 (non-commercial), Slycot (GPLv2). | Reimplement from papers where needed (most are simple or moderate), or confine them to evaluation-only scripts, subject to legal review. |

## II.7 Open problems where the literature gives no good answer

1. **Minimal-state estimation for nonlinear input-driven systems.** Existence and minimality theory exists (Nerode-type,
   rational/RNN realisation theory), but there is no practical, consistent estimator or order test from finite
   simulator data. Information criteria are meaningless for over-parameterised models, singular-value gaps vanish under
   nonlinearity, and cross-validation plateaus lack guarantees.
2. **Which test bank suffices.** Equivalence is relative to a set of probes. For continuous nonlinear systems there is no
   analogue of L*'s characterising suffix set, and no theory of when equivalence under training interventions implies
   equivalence under *unseen intervention types*.
3. **Structural interventions.** Unit and connection removal change the vector field. No reviewed method predicts them
   with a fixed low-dimensional f, except unit-space models (low-rank RNNs, Galerkin reductions) that keep micro
   parameters, and those assume low-rank micro structure. How to define the micro-to-macro intervention map ω for
   structural interventions is open.
4. **Identifiability of Markov latent dynamics from micro interventions with multi-node, graded, unknown macro targets.**
   BISCUIT (binary interactions), Buchholz et al. (linear Gaussian latent SCM) and von Kügelgen et al. (perfect
   interventions) each cover only part of this setting. No result covers continuous-time dynamics with feedback.
5. **One shared f across implementations.** Multi-view block identifiability covers shared *state content*, not shared
   *dynamics*. Classical similarity-class equivalence covers only linear I/O maps. There is no statistical test of
   "same f up to conjugacy" with calibrated nulls. DSA, CSA, DFORM and Koopman-spectrum tests disagree and lack null
   distributions.
6. **Calibrated abstention.** Predictive-information divergence and k-growth are asymptotic notions. No finite-data test
   separates "large but finite" from "non-compact" state, and no reviewed method outputs a calibrated "no compact state
   exists".
7. **Deterministic chaos.** Exact equivalence classes are singletons, and only (ε, H)-indexed notions make sense. How to
   choose ε and H jointly, and how to combine invariant-measure metrics (D_stsp, D_H) with interventional tests on
   *transients*, is unresolved. There is no accepted analogue of D_stsp for post-intervention transients.
8. **Global canonical coordinates.** Phase and isostables, spectral submanifolds and normal forms are local to one
   attractor. There is no global gauge-fixed latent coordinate system for multistable, input-driven or chaotic regimes,
   or for switches between attractors under interventions. A finite linear Koopman model cannot represent multiple
   isolated attractors at all.
9. **Experiment design for abstractions.** Fisher/BOED design targets parameters or graphs. There is no design theory
   for information about phi and the microstate equivalence classes; ensemble disagreement and invariance-violation
   search are ad hoc proxies. Persistency-of-excitation richness conditions exist only for LTI systems.
10. **Curved balanced reduction at scale.** Empirical gramians yield one global linear subspace. No standard method gives a
    nonlinear balanced manifold from simulation data at N ~ 10³-10⁴.
11. **Termination and completeness of counterexample-guided refinement** for continuous states and learned neural
    abstractions. Adversarial oracles give no PAC bound.
12. **Invariance class of "identifiable up to transformations".** The literature does not say which class (linear,
    affine, diffeomorphic, conjugacy of f) is appropriate. The similarity metric chosen implicitly decides it, so the
    project must pre-register the class per property.
13. **Dimension estimation of a *closed, interventionally sufficient* state**, as opposed to a state-cloud dimension. It
    is unreliable above ~20 dimensions and under noise. Linear estimators overestimate nonlinear dimension, and
    nonlinear estimators are fooled by pathological encodings.

---

# Part III. References

Deduplicated across areas (by arXiv id or URL). Each item keeps the strongest verification tag found. Items are listed under the area where they first appear; per-entry reference lists in Part I show which method each supports.

### R-A. Classical system identification and model reduction

- Juang, J.-N., Pappa, R. S. (1985). An eigensystem realization algorithm for modal parameter identification and model reduction. J. Guidance, Control, and Dynamics 8(5):620-627. https://ntrs.nasa.gov/citations/19850064186 ; PDF https://people.duke.edu/~hpgavin/SystemID/References/Juang+Pappa-JG-1985.pdf [unverified] (PDF not text-extractable; bibliographic info and "extended version of the Ho-Kalman algorithm" from search snippet).
- Ho, B. L., Kalman, R. E. (1966). Effective construction of linear state-variable models from input/output functions. Regelungstechnik 14. [unverified]
- Oymak, S., Ozay, N. (2018/2019). Non-asymptotic identification of LTI systems from a single trajectory. arXiv:1806.05722 (ACC 2019). https://arxiv.org/abs/1806.05722 [read-abstract]
- Rojas, C. R., Wachel, P. (2022). On state-space representations of general discrete-time dynamical systems. IEEE TAC. https://arxiv.org/abs/2205.03366 [read-abstract]
- Defourneau, T., Petreczky, M. (2019). Realization theory of recurrent neural networks and rational systems. arXiv:1903.05609. https://arxiv.org/abs/1903.05609 [read-abstract]
- Sun, S., Hu, W., Wang, X. (2025). Finite sample analysis of subspace identification for stochastic systems. arXiv:2501.18853. https://arxiv.org/html/2501.18853 [read-full] (procedure and main theorem statements)
- python-control docs, `eigensys_realization`, `markov`, `hankel_singular_values`. https://python-control.readthedocs.io/en/latest/generated/control.eigensys_realization.html [repo/docs]
- Van Overschee, P., De Moor, B. (1994). N4SID: subspace algorithms for the identification of combined deterministic-stochastic systems. Automatica 30(1):75-93. https://dl.acm.org/doi/abs/10.1016/0005-1098(94)90230-5 [unverified] (landing page not opened; bibliographic info from search result)
- Verhaegen, M., Dewilde, P. (1992). Subspace model identification Part 1: the output-error state-space model identification class of algorithms. Int. J. Control 56(5):1187-1210. https://people.duke.edu/~hpgavin/SystemID/References/Verhaegen-IJC-1992a.pdf [unverified]
- Larimore, W. E. (1990). Canonical variate analysis in identification, filtering and adaptive control. 29th IEEE CDC. [unverified]
- Mercère, G. (2013). Regression techniques for subspace-based black-box state-space system identification: an overview. arXiv:1305.7121. https://arxiv.org/abs/1305.7121 [read-abstract]
- Verhaegen, M., Hansson, A. (2015/2016). N2SID: Nuclear norm subspace identification. arXiv:1501.04495. https://arxiv.org/abs/1501.04495 [read-abstract]
- Fazel, M., Pong, T. K., Sun, D., et al. (2013). Hankel matrix rank minimization with applications to system identification and realization. SIAM J. Matrix Anal. Appl. 34(3):946-977. [unverified]
- Tadipatri, U. K. R., Haeffele, B. D., Agterberg, J., et al. (2025). Nonconvex linear system identification with minimal state representation. L4DC 2025. https://arxiv.org/abs/2504.18791 [read-abstract]
- SIPPY repo https://github.com/CPCLAB-UNIPI/SIPPY [repo/docs]; nfoursid repo https://github.com/spmvg/nfoursid and https://nfoursid.readthedocs.io [repo/docs]; MATLAB n4sid docs [repo/docs]; Slycot repo [repo/docs].
- Sani, O. G., Abbaspourazad, H., Wong, Y. T., et al. (2021). Modeling behaviorally relevant neural dynamics enabled by preferential subspace identification. Nature Neuroscience 24:140-149. https://www.nature.com/articles/s41593-020-00733-0 [unverified] (paywall redirect; method described from README)
- Sani, O. G., Shanechi, M. M. (2025). Preferential subspace identification (PSID) with forward-backward smoothing. arXiv:2507.15288. https://arxiv.org/abs/2507.15288 [read-abstract]
- PyPSID and PSID repos/README/LICENSE https://github.com/ShanechiLab/PyPSID , https://github.com/ShanechiLab/PSID/blob/main/README.md [repo/docs]
- Moore, B. C. (1981). Principal component analysis in linear systems: controllability, observability, and model reduction. IEEE TAC 26(1):17-32. [unverified] (abstract seen only via search snippet)
- Rowley, C. W. (2005). Model reduction for fluids, using balanced proper orthogonal decomposition. Int. J. Bifurcation and Chaos 15:997-1013. https://cwrowley.princeton.edu/papers/bt_ijbc3.pdf [unverified] (PDF not text-extractable)
- Gosea, I. V., Gugercin, S., Beattie, C. (2021). Data-driven balancing of linear dynamical systems. arXiv:2104.01006. https://arxiv.org/abs/2104.01006 [read-abstract]
- Kramer, B., Gugercin, S., Borggaard, J., et al. (2022/2024). Scalable computation of energy functions for nonlinear balanced truncation. arXiv:2209.07645. https://arxiv.org/abs/2209.07645 [read-abstract]
- python-control function list https://python-control.readthedocs.io/en/latest/functions.html [repo/docs]
- Lall, S., Marsden, J. E., Glavaski, S. (2002). A subspace approach to balanced truncation for model reduction of nonlinear control systems. Int. J. Robust Nonlinear Control 12:519-535. https://onlinelibrary.wiley.com/doi/abs/10.1002/rnc.657 [unverified] (abstract content seen via search snippet only)
- C. Himpe, "emgr - The Empirical Gramian Framework", 2018, Algorithms 11(7):91, https://arxiv.org/abs/1611.00675 [read-abstract]; repo https://github.com/gramian/emgr [repo/docs] (also cited in area G)
- Himpe, C. (2022). emgr - EMpirical GRamian Framework Version 5.99. arXiv:2209.03833. https://arxiv.org/abs/2209.03833 [read-abstract]
- emgr repo https://github.com/gramian/emgr [repo/docs]
- Hermann, R., Krener, A. J. (1977). Nonlinear controllability and observability. IEEE TAC 22(5):728-740. https://www.math.ucdavis.edu/~krener/1-25/10.IEEETAC77.pdf [unverified] (PDF not text-extractable; rank-condition statement from search snippet)
- Krener, A. J., Ide, K. (2009). Measures of unobservability. Proc. IEEE CDC 2009, 6401-6406. https://www.math.ucdavis.edu/~krener/101-125/125.CDC09.pdf [unverified] (PDF fetched but not reliably text-extracted; definitions of unobservability index and condition number from search snippet)
- python-control function list [repo/docs]; emgr repo [repo/docs] (see above).
- Sauer, T., Yorke, J. A., Casdagli, M. (1991). Embedology. J. Stat. Phys. 65:579-616. [unverified] (abstract seen via search snippet)
- Stark, J. (1999). Delay embeddings for forced systems. I. Deterministic forcing. J. Nonlinear Science 9:255-332. https://doi.org/10.1007/s003329900072 [unverified] (abstract seen via search snippet)
- Takens, F. (1981). Detecting strange attractors in turbulence. Lecture Notes in Mathematics 898. [unverified]
- Brunton, S. L., Brunton, B. W., Proctor, J. L., et al. (2017; arXiv 2016). Chaos as an intermittently forced linear system. Nature Communications 8:19 (venue unverified). https://arxiv.org/abs/1608.05306 [read-abstract] (also cited in area B)
- Arbabi, H., Mezic, I. (2017). Ergodic theory, dynamic mode decomposition, and computation of spectral properties of the Koopman operator. SIAM J. Appl. Dyn. Syst. 16(4):2096-2126. https://arxiv.org/abs/1611.06664 [read-abstract]
- Kamb, M., Kaiser, E., Brunton, S. L., et al. (2018/2020). Time-delay observables for Koopman: theory and applications. arXiv:1810.01479. https://arxiv.org/abs/1810.01479 [read-abstract]
- pykoopman repo and docs https://github.com/dynamicslab/pykoopman , https://pykoopman.readthedocs.io [repo/docs]
- PyDMD repo https://github.com/PyDMD/PyDMD [repo/docs]
- Golyandina, N., Korobeynikov, A. (2014). Basic singular spectrum analysis and forecasting with R. Comput. Stat. Data Anal. 71:934-954. https://arxiv.org/abs/1206.6910 [read-abstract]
- Golyandina, N., Korobeynikov, A., Shlemov, A., et al. (2015). Multivariate and 2D extensions of singular spectrum analysis with the Rssa package. J. Stat. Softw. 67(2). https://arxiv.org/abs/1309.5050 [read-abstract]
- Chen, S., Billings, S. A. (1989). Representations of non-linear systems: the NARMAX model. Int. J. Control 49(3):1013-1032. https://www.tandfonline.com/doi/abs/10.1080/00207178908559683 [unverified]
- SysIdentPy repo and docs https://github.com/wilsonrljr/sysidentpy , https://sysidentpy.org [repo/docs]
- Schoukens, J., Ljung, L. (2019). Nonlinear system identification: a user-oriented road map. IEEE Control Systems Magazine 39(6):28-99. https://arxiv.org/html/1902.00683v1 [read-full]
- Aguirre, L. A. (2019/2022). A bird's eye view of nonlinear system identification. arXiv:1907.06803. https://arxiv.org/abs/1907.06803 [read-abstract]
- Frigola, R., Lindsten, F., Schön, T. B., Rasmussen, C. E. (2013). Bayesian inference and learning in Gaussian process state-space models with particle MCMC. NIPS 2013. https://arxiv.org/abs/1306.2861 [read-abstract]
- Shumway, R. H., Stoffer, D. S. (1982). An approach to time series smoothing and forecasting using the EM algorithm. J. Time Series Analysis 3(4):253-264. https://dsstoffer.github.io/files/em.pdf [unverified] (PDF not text-extractable)
- Ghahramani, Z., Hinton, G. E. (1996). Parameter estimation for linear dynamical systems. Tech. Rep. CRG-TR-96-2, Univ. Toronto. https://www.cs.utoronto.ca/~hinton/absps/tr96-2.html [read-abstract]
- Yu, B. M., Cunningham, J. P., Santhanam, G., et al. (2009). Gaussian-process factor analysis for low-dimensional single-trial analysis of neural population activity. NeurIPS 21 (2008 proceedings). https://proceedings.neurips.cc/paper_files/paper/2008/hash/ad972f10e0800b49d76fed33a21f6698-Abstract.html [read-abstract] (methodology only; no data described)
- dynamax repo https://github.com/probml/dynamax [repo/docs]
- Rissanen, J. (1978). Modeling by shortest data description. Automatica 14:465-471. [unverified]
- Grünwald, P. (2004). A tutorial introduction to the minimum description length principle. arXiv:math/0406077. https://arxiv.org/abs/math/0406077 [read-abstract]
- Bauer, D. (2001). Order estimation for subspace methods. Automatica 37:1561-1573. [unverified] (abstract content seen only via search snippet)
- Horn, J. L. (1965). A rationale and test for the number of factors in factor analysis. Psychometrika 30:179-185. [unverified]; Parallel analysis overview https://en.wikipedia.org/wiki/Parallel_analysis [read-full] (secondary)
- PyPSID README (CV grid search over nx, n1) [repo/docs]; GPFA abstract (leave-out CV) [read-abstract].
- Yu, Y., Talebi, S., van Waarde, H. J., et al. (2021). On controllability and persistency of excitation in data-driven control: extensions of Willems' fundamental lemma. arXiv:2102.02953. https://arxiv.org/abs/2102.02953 [read-abstract] (also cited in area G)
- Shang, X., Cortés, J., Zheng, Y. (2024). Willems' fundamental lemma for nonlinear systems with Koopman linear embedding. arXiv:2409.16389. https://arxiv.org/abs/2409.16389 [read-abstract]
- Willems, J. C., Rapisarda, P., Markovsky, I., De Moor, B. (2005). A note on persistency of excitation. Systems & Control Letters. [unverified]

### R-B. Koopman, DMD and sparse identification

- Dynamic mode decomposition of numerical and experimental data. P. J. Schmid. 2010. J. Fluid Mech. 656:5-28. https://www.cambridge.org/core/journals/journal-of-fluid-mechanics/article/dynamic-mode-decomposition-of-numerical-and-experimental-data/AA4C763B525515AD4521A6CC5E10DBD4 [read-abstract]
- On dynamic mode decomposition: theory and applications. J. H. Tu, C. W. Rowley, D. M. Luchtenburg et al. 2014. J. Computational Dynamics 1(2). https://arxiv.org/abs/1312.0041 [read-full]
- Characterizing and correcting for the effect of sensor noise in the dynamic mode decomposition. S. T. M. Dawson, M. S. Hemati, M. O. Williams et al. 2016. Experiments in Fluids. https://arxiv.org/abs/1507.02264 [read-full]
- De-biasing the dynamic mode decomposition for applied Koopman spectral analysis. M. S. Hemati, C. W. Rowley, E. A. Deem et al. 2017 (arXiv 2015). Theor. Comput. Fluid Dyn. https://arxiv.org/abs/1502.03854 [read-abstract]
- Variable projection methods for an optimized dynamic mode decomposition. T. Askham, J. N. Kutz. 2018 (arXiv 2017). SIAM J. Appl. Dyn. Syst. (venue unverified). https://arxiv.org/abs/1704.02343 [read-abstract]
- Bagging, optimized dynamic mode decomposition (BOP-DMD) for robust, stable forecasting with spatial and temporal uncertainty quantification. D. Sashidhar, J. N. Kutz. 2022 (arXiv 2021). Phil. Trans. R. Soc. A (venue unverified). https://arxiv.org/abs/2107.10878 [read-full]
- Dynamic mode decomposition with control. J. L. Proctor, S. L. Brunton, J. N. Kutz. 2016 (arXiv 2014). SIAM J. Appl. Dyn. Syst. (venue unverified). https://arxiv.org/abs/1409.6358 [read-full]
- On reduced input-output dynamic mode decomposition. P. Benner, C. Himpe, T. Mitchell. 2018 (arXiv 2017). Adv. Comput. Math. https://arxiv.org/abs/1712.08447 [read-full]
- Input-output dynamic mode decomposition. J. Annoni, P. Seiler et al. 2015. APS DFD abstract (original ioDMD; not opened, ADS page returned 405) [unverified]
- A data-driven approximation of the Koopman operator: extending dynamic mode decomposition. M. O. Williams, I. G. Kevrekidis, C. W. Rowley. 2015 (arXiv 2014). J. Nonlinear Science. https://arxiv.org/abs/1408.4408 [read-full]
- Modern Koopman theory for dynamical systems. S. L. Brunton, M. Budisic, E. Kaiser, J. N. Kutz. 2022 (arXiv 2021). SIAM Review (venue unverified). https://arxiv.org/abs/2102.12086 [read-full] (sections 1-2 only)
- A kernel-based method for data-driven Koopman spectral analysis. M. O. Williams, C. W. Rowley, I. G. Kevrekidis. 2015 (arXiv 2014). J. Computational Dynamics (venue unverified). https://arxiv.org/abs/1411.2260 [read-full]
- Rigorous data-driven computation of spectral properties of Koopman operators for dynamical systems. M. J. Colbrook, A. Townsend. 2024 (arXiv 2021). Comm. Pure Appl. Math. (venue unverified). https://arxiv.org/abs/2111.14889 [read-full]
- Residual dynamic mode decomposition: robust and verified Koopmanism. M. J. Colbrook, L. J. Ayton, M. Szoke. 2023 (arXiv 2022). J. Fluid Mech. https://arxiv.org/abs/2205.09779 [read-abstract]
- Linear predictors for nonlinear dynamical systems: Koopman operator meets model predictive control. M. Korda, I. Mezic. 2018 (arXiv 2016). Automatica. https://arxiv.org/abs/1611.03537 [read-full]
- Data-driven model predictive control using interpolated Koopman generators. S. Peitz, S. E. Otto, C. W. Rowley. 2020. SIAM J. Appl. Dyn. Syst. (venue unverified). https://arxiv.org/abs/2003.07094 [read-abstract]
- PyKoopman: a Python package for data-driven approximation of the Koopman operator. S. Pan, E. Kaiser, B. M. de Silva et al. 2023. arXiv / JOSS (venue unverified). https://arxiv.org/abs/2306.12962 [read-abstract]
- Data-driven approximation of the Koopman generator: model reduction, system identification, and control. S. Klus, F. Nuske, S. Peitz et al. 2020 (arXiv 2019). Physica D. https://arxiv.org/abs/1909.10638 [read-full]
- Variational approach for learning Markov processes from time series data (VAMP). H. Wu, F. Noe. 2020 (arXiv 2017). J. Nonlinear Science (venue unverified). https://arxiv.org/abs/1707.04659 [read-full]
- Identification of slow molecular order parameters for Markov model construction (TICA). G. Perez-Hernandez, F. Paul, T. Giorgino et al. 2013. J. Chem. Phys. (venue unverified). https://arxiv.org/abs/1302.6614 [read-abstract]
- deeptime docs, decomposition and Markov API pages. https://deeptime-ml.github.io/latest/api/index_decomposition.html, https://deeptime-ml.github.io/latest/api/index_markov.html [repo/docs]
- VAMPnets for deep learning of molecular kinetics. A. Mardt, L. Pasquali, H. Wu, F. Noe. 2018 (arXiv 2017). Nature Communications. https://arxiv.org/abs/1710.06012 [read-full]
- Deep learning for universal linear embeddings of nonlinear dynamics. B. Lusch, J. N. Kutz, S. L. Brunton. 2018. Nature Communications. https://arxiv.org/abs/1712.09707 [read-full]
- Learning Koopman invariant subspaces for dynamic mode decomposition. N. Takeishi, Y. Kawahara, T. Yairi. 2017. NeurIPS (NIPS 2017). https://arxiv.org/abs/1710.04340 [read-full]
- Linearly-recurrent autoencoder networks for learning dynamics. S. E. Otto, C. W. Rowley. 2019 (arXiv 2017). SIAM J. Appl. Dyn. Syst. (venue unverified). https://arxiv.org/abs/1712.01378 [read-full]
- Forecasting sequential data using consistent Koopman autoencoders. O. Azencot, N. B. Erichson, V. Lin, M. W. Mahoney. 2020. ICML 2020 (venue unverified). https://arxiv.org/abs/2003.02236 [read-full]
- Discovering governing equations from data by sparse identification of nonlinear dynamical systems. S. L. Brunton, J. L. Proctor, J. N. Kutz. 2016 (arXiv 2015). PNAS. https://arxiv.org/abs/1509.03580 [read-full]
- Sparse identification of nonlinear dynamics with control (SINDYc). S. L. Brunton, J. L. Proctor, J. N. Kutz. 2016. IFAC NOLCOS. https://arxiv.org/abs/1605.06682 [read-full]
- Ensemble-SINDy: robust sparse model discovery in the low-data, high-noise limit, with active learning and control. U. Fasel, J. N. Kutz, B. W. Brunton, S. L. Brunton. 2022 (arXiv 2021). Proc. R. Soc. A (venue unverified). https://arxiv.org/abs/2111.10992 [read-full]
- Weak SINDy: Galerkin-based data-driven model selection. D. A. Messenger, D. M. Bortz. 2021 (arXiv 2020). Multiscale Model. Simul. (venue unverified). https://arxiv.org/abs/2005.04339 [read-full]
- SINDy-PI: a robust algorithm for parallel implicit sparse identification of nonlinear dynamics. K. Kaheman, J. N. Kutz, S. L. Brunton. 2020. Proc. R. Soc. A. https://arxiv.org/abs/2004.02322 [read-full]
- Data-driven discovery of coordinates and governing equations. K. Champion, B. Lusch, J. N. Kutz, S. L. Brunton. 2019. PNAS. https://arxiv.org/abs/1904.02107 [read-full]
- Data-driven operator inference for nonintrusive projection-based model reduction. B. Peherstorfer, K. Willcox. 2016. Comput. Methods Appl. Mech. Eng. 306 (page returned 403; not opened) [unverified]
- Sampling low-dimensional Markovian dynamics for pre-asymptotically recovering reduced models from data with operator inference. B. Peherstorfer. 2020 (arXiv 2019). SIAM J. Sci. Comput. (venue unverified). https://arxiv.org/abs/1908.11233 [read-full]
- Learning nonlinear reduced models from data with operator inference. B. Kramer, B. Peherstorfer, K. Willcox. 2024. Annu. Rev. Fluid Mech. 56 (seen only in search results) [unverified]
- opinf repository README and LICENSE. https://github.com/operator-inference/opinf [repo/docs]

### R-C. Predictive states, causal states, bisimulation and abstraction refinement

- Predictive Representations of State. M. L. Littman, R. S. Sutton, S. Singh. 2001 (NIPS 14, published 2002). https://proceedings.neurips.cc/paper/2001/hash/1e4d36177d71bbb3558e43af9577d70e-Abstract.html [read-abstract]
- Predictive State Representations: A New Theory for Modeling Dynamical Systems. S. Singh, M. James, M. Rudary. 2004. UAI 2004. https://arxiv.org/abs/1207.4167 [read-abstract]
- A Spectral Algorithm for Learning Hidden Markov Models. D. Hsu, S. M. Kakade, T. Zhang. 2009 (arXiv 2008; JCSS 78(5), 2012). https://arxiv.org/abs/0811.4413 [read-abstract]
- Closing the Learning-Planning Loop with Predictive State Representations. B. Boots, S. M. Siddiqi, G. J. Gordon. 2009 arXiv (IJRR 2011, unverified). https://arxiv.org/abs/0912.2385 [read-abstract]
- Practical Learning of Predictive State Representations. C. Downey, A. Hefny, G. Gordon. 2017. arXiv. https://arxiv.org/abs/1702.04121 [read-abstract]
- Hilbert Space Embeddings of Predictive State Representations. B. Boots, G. Gordon, A. Gretton. 2013. UAI 2013. https://arxiv.org/abs/1309.6819 [read-abstract]
- Learning to Filter with Predictive State Inference Machines. W. Sun, A. Venkatraman, B. Boots, J. A. Bagnell. 2016. ICML 2016. https://arxiv.org/abs/1512.08836 [read-abstract]
- Predictive State Recurrent Neural Networks. C. Downey, A. Hefny, B. Li, B. Boots, G. Gordon. 2017. NeurIPS 2017 (venue unverified; arXiv read). https://arxiv.org/abs/1705.09353 [read-abstract]
- Inferring Statistical Complexity. J. P. Crutchfield, K. Young. 1989. Physical Review Letters 63, 105. https://csc.ucdavis.edu/~cmg/compmech/pubs/ISCTitlePage.htm [read-abstract]
- Computational Mechanics: Pattern and Prediction, Structure and Simplicity. C. R. Shalizi, J. P. Crutchfield. 2001. Journal of Statistical Physics 104. https://arxiv.org/abs/cond-mat/9907176 [read-abstract]
- Blind Construction of Optimal Nonlinear Recursive Predictors for Discrete Sequences. C. R. Shalizi, K. L. Shalizi (Klinkner). 2004. UAI 2004. https://arxiv.org/abs/cs/0406011 [read-abstract]
- Computational Mechanics of Input-Output Processes: Structured transformations and the epsilon-transducer. N. Barnett, J. P. Crutchfield. 2015 (arXiv 2014). Journal of Statistical Physics. https://arxiv.org/abs/1412.2690 [read-abstract]
- CSSR homepage. C. R. Shalizi. https://bactra.org/CSSR/ [repo/docs]
- Discovering Causal Structure with Reproducing-Kernel Hilbert Space epsilon-Machines. N. Brodu, J. P. Crutchfield. 2022 (arXiv 2020). Chaos 32, 023103. https://arxiv.org/abs/2011.14821 [read-abstract]
- Inferring Kernel epsilon-Machines: Discovering Structure in Complex Systems. A. M. Jurgens, N. Brodu. 2024. arXiv. https://arxiv.org/abs/2410.01076 [read-abstract]
- Topology, Convergence, and Reconstruction of Predictive States. S. P. Loomis, J. P. Crutchfield. 2021. arXiv. https://arxiv.org/abs/2109.09203 [read-abstract]
- Predictability, Complexity and Learning. W. Bialek, I. Nemenman, N. Tishby. 2001. Neural Computation 13. https://arxiv.org/abs/physics/0007070 [read-abstract]
- Past-future information bottleneck in dynamical systems. F. Creutzig, A. Globerson, N. Tishby. 2009. Physical Review E 79, 041925. https://cris.tau.ac.il/en/publications/past-future-information-bottleneck-in-dynamical-systems/ [read-abstract]
- Unsupervised Discovery of Temporal Structure in Noisy Data with Dynamical Components Analysis. D. G. Clark, J. A. Livezey, K. E. Bouchard. 2019. NeurIPS 2019. https://arxiv.org/abs/1905.09944 (HTML body read) [read-full]
- Compressed Predictive Information Coding. R. Meng, T. Luo, K. Bouchard. 2022. arXiv. https://arxiv.org/abs/2203.02051 [read-abstract]
- Equivalence notions and model minimization in Markov decision processes. R. Givan, T. Dean, M. Greig. 2003. Artificial Intelligence 147. https://doi.org/10.1016/S0004-3702(02)00376-4 [unverified: landing page 403, PDF not parseable]
- Towards a Unified Theory of State Abstraction for MDPs. L. Li, T. J. Walsh, M. L. Littman. 2006. ISAIM 2006. http://anytime.cs.umass.edu/aimath06/proceedings/P21.pdf [unverified: could not open]
- Three Partition Refinement Algorithms. R. Paige, R. E. Tarjan. 1987. SIAM Journal on Computing 16(6). https://scholarsmine.mst.edu/math_stat_facwork/349/ [read-abstract]
- Exact and ordinary lumpability in finite Markov chains. P. Buchholz. 1994. Journal of Applied Probability 31. [unverified]
- Finite Markov Chains. J. G. Kemeny, J. L. Snell. 1960/1976. Van Nostrand / Springer. [unverified]
- A dual eigenvector condition for strong lumpability of Markov chains. M. N. Jacobi, O. Goernerup. 2007. arXiv. https://arxiv.org/abs/0710.1986 [read-abstract]
- Formal Error Bounds for the State Space Reduction of Markov Chains. F. Michel, M. Siegle. 2024. arXiv. https://arxiv.org/abs/2403.07618 [read-abstract]
- Approximation metrics for discrete and continuous systems. A. Girard, G. J. Pappas. 2007. IEEE Transactions on Automatic Control. [unverified]
- Approximate bisimulation (overview PDF by G. J. Pappas; exact title/venue not verified). https://www.georgejpappas.org/wp-content/uploads/2024/04/EJC-Pappas.pdf [read-abstract]
- Metrics for Finite Markov Decision Processes. N. Ferns, P. Panangaden, D. Precup. 2004. UAI 2004. https://arxiv.org/abs/1207.4114 [read-abstract]
- Learning Invariant Representations for Reinforcement Learning without Reconstruction (DBC). A. Zhang, R. McAllister, R. Calandra et al. 2021. ICLR 2021. https://arxiv.org/abs/2006.10742 [read-abstract]
- MICo: Improved representations via sampling-based state similarity for Markov decision processes. P. S. Castro, T. Kastner, P. Panangaden, M. Rowland. 2021. NeurIPS 2021. https://arxiv.org/abs/2106.08229 (HTML body read) [read-full]
- DeepMDP: Learning Continuous Latent Space Models for Representation Learning. C. Gelada, S. Kumar, J. Buckman et al. 2019. ICML 2019. https://arxiv.org/abs/1906.02736 [read-abstract]
- Bridging State and History Representations: Understanding Self-Predictive RL. T. Ni, B. Eysenbach, E. Seyedsalehi et al. 2024. ICLR 2024. https://arxiv.org/abs/2401.08898 (HTML body read; author list beyond first author from memory, unverified) [read-full]
- Learning Markov State Abstractions for Deep Reinforcement Learning. C. Allen, N. Parikh, O. Gottesman, G. Konidaris. 2021. NeurIPS 2021 (venue unverified). https://arxiv.org/abs/2106.04379 (HTML body read) [read-full]
- Denoised MDPs: Learning World Models Better Than the World Itself. T. Wang, S. S. Du, A. Torralba et al. 2022. ICML 2022. https://arxiv.org/abs/2206.15477 [read-abstract]
- Counterexample-Guided Abstraction Refinement. E. Clarke, O. Grumberg, S. Jha et al. 2000. CAV 2000, LNCS 1855, pp. 154-169. https://web.stanford.edu/class/cs357/cegar.pdf [read-abstract: PDF fetched but only a summary-level extraction was obtained]
- Abstraction and Counterexample-Guided Refinement in Model Checking of Hybrid Systems. E. Clarke, A. Fehnker, Z. Han et al. 2003. Int. J. Foundations of Computer Science 14(4). https://www.worldscientific.com/doi/abs/10.1142/S012905410300190X [unverified: page 403, PDF not parseable]
- A Survey of Algorithms for Black-Box Safety Validation of Cyber-Physical Systems. A. Corso, R. J. Moss, M. Koren et al. 2021. JAIR 72. https://arxiv.org/abs/2005.02979 [read-abstract]
- PSY-TaLiRo repository. https://gitlab.com/sbtg/psy-taliro [repo/docs]
- Learning regular sets from queries and counterexamples. D. Angluin. 1987. Information and Computation 75, 87-106. https://people.eecs.berkeley.edu/~dawnsong/teaching/s10/papers/angluin87.pdf [unverified: PDF not parseable; abstract content seen only in search snippet]
- Extracting Automata from Recurrent Neural Networks Using Queries and Counterexamples. G. Weiss, Y. Goldberg, E. Yahav. 2018. ICML 2018. https://arxiv.org/abs/1711.09576 [read-abstract]
- AALpy repository. https://github.com/DES-Lab/AALpy [repo/docs]
- LearnLib repository. https://github.com/learnlib/learnlib [repo/docs]

### R-D. Neural state-space and continuous-time latent models

- Deep Kalman Filters. R. G. Krishnan, U. Shalit, D. Sontag. 2015. arXiv:1511.05121. https://arxiv.org/abs/1511.05121 [read-abstract]
- Structured Inference Networks for Nonlinear State Space Models. R. G. Krishnan, U. Shalit, D. Sontag. 2017. AAAI. https://arxiv.org/abs/1609.09869 [read-abstract]
- Pyro Deep Markov Model tutorial. https://pyro.ai/examples/dmm.html [repo/docs]
- A Recurrent Latent Variable Model for Sequential Data. J. Chung, K. Kastner, L. Dinh et al. 2015. NeurIPS 2015. https://arxiv.org/abs/1506.02216 [read-abstract]
- Sequential Neural Models with Stochastic Layers. M. Fraccaro, S. K. Sønderby, U. Paquet, O. Winther. 2016. NeurIPS 2016. https://arxiv.org/abs/1605.07571 [read-abstract]
- A Disentangled Recognition and Nonlinear Dynamics Model for Unsupervised Learning. M. Fraccaro, S. Kamronn, U. Paquet, O. Winther. 2017. NeurIPS 2017. https://arxiv.org/abs/1710.05741 ; full text via https://ar5iv.labs.arxiv.org/html/1710.05741 [read-full]
- kvae repository. https://github.com/simonkamronn/kvae [repo/docs]
- Deep Variational Bayes Filters: Unsupervised Learning of State Space Models from Raw Data. M. Karl, M. Soelch, J. Bayer, P. van der Smagt. 2017. ICLR 2017. https://arxiv.org/abs/1605.06432 [read-abstract]
- Learning Latent Dynamics for Planning from Pixels. D. Hafner, T. Lillicrap, I. Fischer et al. 2019. ICML 2019. https://arxiv.org/abs/1811.04551 ; https://ar5iv.labs.arxiv.org/html/1811.04551 [read-full]
- Dream to Control: Learning Behaviors by Latent Imagination. D. Hafner, T. Lillicrap, J. Ba, M. Norouzi. 2020. ICLR 2020. https://arxiv.org/abs/1912.01603 [read-abstract]
- Mastering Atari with Discrete World Models. D. Hafner, T. Lillicrap, M. Norouzi, J. Ba. 2021. ICLR 2021. https://arxiv.org/abs/2010.02193 [read-abstract; partial PDF text]
- Mastering Diverse Domains through World Models. D. Hafner, J. Pasukonis, J. Ba, T. Lillicrap. 2023 (rev. 2024). arXiv:2301.04104. https://arxiv.org/html/2301.04104 [read-full]
- dreamerv3 repository. https://github.com/danijar/dreamerv3 [repo/docs]
- Embed to Control: A Locally Linear Latent Dynamics Model for Control from Raw Images. M. Watter, J. T. Springenberg, J. Boedecker, M. Riedmiller. 2015. NeurIPS 2015. https://arxiv.org/abs/1506.07365 ; https://ar5iv.labs.arxiv.org/html/1506.07365 [read-full]
- Robust Locally-Linear Controllable Embedding. E. Banijamali, R. Shu, M. Ghavamzadeh et al. 2018. AISTATS 2018 (PMLR v84). https://arxiv.org/abs/1710.05373 [read-abstract, via search result summary]
- Neural Ordinary Differential Equations. R. T. Q. Chen, Y. Rubanova, J. Bettencourt, D. Duvenaud. 2018. NeurIPS 2018. https://arxiv.org/abs/1806.07366 [read-abstract]
- Augmented Neural ODEs. E. Dupont, A. Doucet, Y. W. Teh. 2019. NeurIPS 2019. https://arxiv.org/abs/1904.01681 [read-abstract]
- On Neural Differential Equations (thesis). P. Kidger. 2022. Univ. Oxford / arXiv:2202.02435. https://arxiv.org/abs/2202.02435 [read-abstract]
- torchdiffeq; diffrax repositories [repo/docs]
- Latent ODEs for Irregularly-Sampled Time Series. Y. Rubanova, R. T. Q. Chen, D. Duvenaud. 2019. NeurIPS 2019. https://arxiv.org/abs/1907.03907 [read-abstract]
- latent_ode repository [repo/docs]
- Neural Controlled Differential Equations for Irregular Time Series. P. Kidger, J. Morrill, J. Foster, T. Lyons. 2020. NeurIPS 2020. https://arxiv.org/abs/2005.08926 ; https://ar5iv.labs.arxiv.org/html/2005.08926 [read-full]
- torchcde repository [repo/docs]
- Scalable Gradients for Stochastic Differential Equations. X. Li, T.-K. L. Wong, R. T. Q. Chen, D. Duvenaud. 2020. AISTATS 2020. https://arxiv.org/abs/2001.01328 ; https://ar5iv.labs.arxiv.org/html/2001.01328 [read-full]
- Neural SDEs as Infinite-Dimensional GANs. P. Kidger, J. Foster, X. Li, H. Oberhauser, T. Lyons. 2021. ICML 2021. https://arxiv.org/abs/2102.03657 [read-abstract]
- torchsde repository [repo/docs]
- Efficiently Modeling Long Sequences with Structured State Spaces. A. Gu, K. Goel, C. Ré. 2022. ICLR 2022. https://arxiv.org/abs/2111.00396 [read-abstract]
- Simplified State Space Layers for Sequence Modeling. J. T. H. Smith, A. Warrington, S. W. Linderman. 2023. ICLR 2023. https://arxiv.org/abs/2208.04933 [read-abstract]
- Resurrecting Recurrent Neural Networks for Long Sequences. A. Orvieto, S. L. Smith, A. Gu et al. 2023. ICML 2023. https://arxiv.org/abs/2303.06349 [read-abstract]
- Mamba: Linear-Time Sequence Modeling with Selective State Spaces. A. Gu, T. Dao. 2023. arXiv:2312.00752. https://arxiv.org/abs/2312.00752 [read-abstract]
- s4, S5, minimal-LRU, mamba repositories [repo/docs]
- Data-Efficient Reinforcement Learning with Self-Predictive Representations. M. Schwarzer, A. Anand, R. Goel et al. 2021. ICLR 2021. https://arxiv.org/abs/2007.05929 [read-abstract]
- Understanding Self-Predictive Learning for Reinforcement Learning. Y. Tang, Z. D. Guo, P. H. Richemond et al. 2023. arXiv:2212.03319 (ICML 2023, unverified). https://arxiv.org/abs/2212.03319 [read-abstract]
- Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture. M. Assran, Q. Duval, I. Misra et al. 2023. ICCV 2023. https://arxiv.org/abs/2301.08243 [read-abstract]
- Representation Learning with Contrastive Predictive Coding. A. van den Oord, Y. Li, O. Vinyals. 2018. arXiv:1807.03748. https://arxiv.org/abs/1807.03748 [read-abstract]
- Contrastive Learning of Structured World Models. T. Kipf, E. van der Pol, M. Welling. 2020. ICLR 2020. https://arxiv.org/abs/1911.12247 ; https://ar5iv.labs.arxiv.org/html/1911.12247 [read-full]
- c-swm repository [repo/docs]
- Recurrent Switching Linear Dynamical Systems. S. W. Linderman, A. C. Miller, R. P. Adams et al. 2017. AISTATS 2017. https://arxiv.org/abs/1610.08466 ; https://ar5iv.labs.arxiv.org/html/1610.08466 [read-full]
- ssm; dynamax repositories [repo/docs]
- Hamiltonian Neural Networks. S. Greydanus, M. Dzamba, J. Yosinski. 2019. NeurIPS 2019. https://arxiv.org/abs/1906.01563 [read-abstract]
- Lagrangian Neural Networks. M. Cranmer, S. Greydanus, S. Hoyer et al. 2020. ICLR 2020 DeepDiffEq workshop. https://arxiv.org/abs/2003.04630 [read-abstract]
- On the difficulty of learning chaotic dynamics with RNNs. J. M. Mikhaeil, Z. Monfared, D. Durstewitz. 2022. NeurIPS 2022. https://arxiv.org/abs/2110.07238 ; https://ar5iv.labs.arxiv.org/html/2110.07238 [read-full]
- Generalized Teacher Forcing for Learning Chaotic Dynamics. F. Hess, Z. Monfared, M. Brenner, D. Durstewitz. 2023. ICML 2023. https://arxiv.org/html/2306.04406 [read-full] (also cited in area G)
- Tractable Dendritic RNNs for Reconstructing Nonlinear Dynamical Systems. M. Brenner, F. Hess, J. M. Mikhaeil et al. 2022. ICML 2022. https://arxiv.org/abs/2207.02542 [read-abstract]
- GTF-shPLRNN; dendPLRNN repositories [repo/docs]

### R-E. Causal representation learning, identifiability and causal abstraction

- Hyvarinen, A., Morioka, H. (2016). Unsupervised Feature Extraction by Time-Contrastive Learning and Nonlinear ICA. NeurIPS 2016 (venue unverified; arXiv page read). https://arxiv.org/abs/1605.06336 [read-abstract]
- Hyvarinen, A., Morioka, H. (2017). Nonlinear ICA of Temporally Dependent Stationary Sources. AISTATS 2017, PMLR 54:460-469. https://proceedings.mlr.press/v54/hyvarinen17a.html [read-abstract]
- Hyvarinen, A., Sasaki, H., Turner, R. E. (2019). Nonlinear ICA Using Auxiliary Variables and Generalized Contrastive Learning. AISTATS 2019. https://arxiv.org/abs/1805.08651 [read-abstract]
- Khemakhem, I., Kingma, D. P., Monti, R. P., et al. (2020). Variational Autoencoders and Nonlinear ICA: A Unifying Framework. AISTATS 2020, PMLR 108:2207-2217. https://arxiv.org/abs/1907.04809 [read-abstract]
- Yao, W., Sun, Y., Ho, A., et al. (2022). Learning Temporally Causal Latent Processes from General Temporal Data. ICLR 2022. https://arxiv.org/abs/2110.05428 [read-abstract]
- Yao, W., Chen, G., Zhang, K. (2022). Temporally Disentangled Representation Learning. NeurIPS 2022. https://arxiv.org/abs/2210.13647 [read-abstract]
- Chen, G., Shen, Y., Chen, Z., et al. (2024). CaRiNG: Learning Temporal Causal Representation under Non-Invertible Generation Process. ICML 2024. https://arxiv.org/abs/2401.14535 [read-abstract]
- Klindt, D., Schott, L., Sharma, Y., et al. (2021). Towards Nonlinear Disentanglement in Natural Data with Temporal Sparse Coding. ICLR 2021. https://arxiv.org/abs/2007.10930 [read-abstract]
- Lippe, P., Magliacane, S., Lowe, S., et al. (2022). CITRIS: Causal Identifiability from Temporal Intervened Sequences. ICML 2022. https://arxiv.org/abs/2202.03169 [read-abstract]
- Lippe, P., Magliacane, S., Lowe, S., et al. (2023). Causal Representation Learning for Instantaneous and Temporal Effects in Interactive Systems (iCITRIS). ICLR 2023. https://arxiv.org/abs/2206.06169 [read-abstract]
- Lippe, P., Magliacane, S., Lowe, S., et al. (2023). BISCUIT: Causal Representation Learning from Binary Interactions. UAI 2023. https://arxiv.org/abs/2306.09643 [read-abstract]
- Squires, C., Seigal, A., Bhate, S., Uhler, C. (2023). Linear Causal Disentanglement via Interventions. ICML 2023 (venue unverified). https://arxiv.org/abs/2211.16467 [read-abstract]
- Varici, B., Acarturk, E., Shanmugam, K., et al. (2023). Score-based Causal Representation Learning with Interventions. arXiv. https://arxiv.org/abs/2301.08230 [read-abstract]
- Buchholz, S., Rajendran, G., Rosenfeld, E., et al. (2023). Learning Linear Causal Representations from Interventions under General Nonlinear Mixing. NeurIPS 2023. https://arxiv.org/abs/2306.02235 [read-abstract]
- Zhang, J., Squires, C., Greenewald, K., et al. (2023). Identifiability Guarantees for Causal Disentanglement from Soft Interventions. NeurIPS 2023 (venue unverified). https://arxiv.org/abs/2307.06250 [read-abstract]
- Ahuja, K., Mahajan, D., Wang, Y., Bengio, Y. (2023). Interventional Causal Representation Learning. ICML 2023 (venue unverified; arXiv page read). https://arxiv.org/abs/2209.11924 [read-abstract]
- von Kugelgen, J., Besserve, M., Wendong, L., et al. (2023). Nonparametric Identifiability of Causal Representations from Unknown Interventions. NeurIPS 2023. https://arxiv.org/abs/2306.00542 [read-abstract]
- von Kugelgen, J., Sharma, Y., Gresele, L., et al. (2021). Self-Supervised Learning with Data Augmentations Provably Isolates Content from Style. NeurIPS 2021. https://arxiv.org/abs/2106.04619 [read-abstract]
- Yao, D., Xu, D., Lachapelle, S., et al. (2024). Multi-View Causal Representation Learning with Partial Observability. ICLR 2024 (venue from a search snippet; unverified). https://arxiv.org/abs/2311.04056 [read-abstract]
- Gresele, L., et al. (2019). The Incomplete Rosetta Stone Problem: Identifiability Results for Multi-View Nonlinear ICA. UAI 2019. [unverified]
- Zimmermann, R. S., Sharma, Y., Schneider, S., et al. (2021). Contrastive Learning Inverts the Data Generating Process. ICML 2021, PMLR 139. https://arxiv.org/abs/2102.08850 ; https://ar5iv.labs.arxiv.org/html/2102.08850 [read-full: theorem statements and results]
- Roeder, G., Metz, L., Kingma, D. P. (2021). On Linear Identifiability of Learned Representations. ICML 2021 (venue unverified; arXiv page read). https://arxiv.org/abs/2007.00810 [read-abstract]
- Schneider, S., Lee, J. H., Mathis, M. W. (2023). Learnable latent embeddings for joint behavioural and neural analysis. Nature 2023. https://arxiv.org/abs/2204.00673 [read-abstract]
- Peters, J., Buhlmann, P., Meinshausen, N. (2016). Causal inference using invariant prediction: identification and confidence intervals. JRSS-B 78(5):947-1012. https://arxiv.org/abs/1501.01332 [read-abstract]
- Heinze-Deml, C., Peters, J., Meinshausen, N. (2018). Invariant Causal Prediction for Nonlinear Models. J. Causal Inference 2018 (venue unverified; arXiv page read). https://arxiv.org/abs/1706.08576 [read-abstract]
- Arjovsky, M., Bottou, L., Gulrajani, I., Lopez-Paz, D. (2019). Invariant Risk Minimization. arXiv. https://arxiv.org/abs/1907.02893 [read-abstract]
- Rosenfeld, E., Ravikumar, P., Risteski, A. (2021). The Risks of Invariant Risk Minimization. ICLR 2021. https://arxiv.org/abs/2010.05761 [read-abstract]
- Rubenstein, P. K., Weichwald, S., Bongers, S., et al. (2017). Causal Consistency of Structural Equation Models. UAI 2017. https://arxiv.org/abs/1707.00819 [read-abstract]
- Beckers, S., Halpern, J. Y. (2019). Abstracting Causal Models. AAAI 2019. https://arxiv.org/abs/1812.03789 [read-abstract]
- Beckers, S., Eberhardt, F., Halpern, J. Y. (2019). Approximate Causal Abstraction. UAI 2019. https://arxiv.org/abs/1906.11583 [read-abstract]
- Rischel, E. F., Weichwald, S. (2021). Compositional abstraction error and a category of causal models. UAI 2021, PMLR 161. https://proceedings.mlr.press/v161/rischel21a.html [read-abstract]
- Otsuka, J., Saigo, H. (2022). On the Equivalence of Causal Models: A Category-Theoretic Approach. CLeaR 2022. https://arxiv.org/abs/2201.06981 [read-abstract]
- Zennaro, F. M., Turrini, P., Damoulas, T. (2023). Quantifying Consistency and Information Loss for Causal Abstraction Learning. IJCAI 2023. https://arxiv.org/abs/2305.04357 [read-abstract]
- Chalupka, K., Perona, P., Eberhardt, F. (2015). Visual Causal Feature Learning. UAI 2015. https://arxiv.org/abs/1412.2309 [read-abstract]
- Chalupka, K., Eberhardt, F., Perona, P. (2017). Causal feature learning: an overview. Behaviormetrika 44(1):137-164. https://authors.library.caltech.edu/77825/ [read-abstract]
- Geiger, A., Lu, H., Icard, T., Potts, C. (2021). Causal Abstractions of Neural Networks. NeurIPS 2021. https://arxiv.org/abs/2106.02997 [read-abstract]
- Geiger, A., Wu, Z., Lu, H., et al. (2022). Inducing Causal Structure for Interpretable Neural Networks (IIT). ICML 2022 (venue unverified; arXiv page read). https://arxiv.org/abs/2112.00826 [read-abstract]
- Geiger, A., Wu, Z., Potts, C., Icard, T., Goodman, N. D. (2024). Finding Alignments Between Interpretable Causal Variables and Distributed Neural Representations (DAS). CLeaR 2024 (venue unverified). https://arxiv.org/abs/2303.02536 [read-abstract]
- Geiger, A., et al. (2023-2025). Causal Abstraction: A Theoretical Foundation for Mechanistic Interpretability. arXiv (JMLR version unverified). https://arxiv.org/abs/2301.04709 [read-abstract]
- Wu, Z., Geiger, A., Arora, A., et al. (2024). pyvene: A Library for Understanding and Improving PyTorch Models via Interventions. arXiv / NAACL demo (venue unverified). https://arxiv.org/abs/2403.07809 [read-abstract]
- Meloux, M., Pimentel, T., Portet, F., Peyrard, M. (2026). Validating Causal Abstraction Metrics on Simulated Complex Systems. arXiv (ICML 2026 MI workshop per repo). https://arxiv.org/html/2607.00267v1 [read-full: definitions, sampling, failure modes]
- Rubenstein, P. K., Bongers, S., Scholkopf, B., Mooij, J. M. (2018). From Deterministic ODEs to Dynamic Structural Causal Models. UAI 2018. https://arxiv.org/abs/1608.08028 [read-abstract]
- Bongers, S., Blom, T., Mooij, J. M. (2018/2022). Causal Modeling of Dynamical Systems. arXiv. https://arxiv.org/abs/1803.08784 [read-abstract]
- Runge, J., Nowack, P., Kretschmer, M., et al. (2019). Detecting and quantifying causal associations in large nonlinear time series datasets. Science Advances 5(11). https://arxiv.org/abs/1702.07007 [read-abstract]
- Mooij, J. M., Magliacane, S., Claassen, T. (2020). Joint Causal Inference from Multiple Contexts. JMLR 2020. https://arxiv.org/abs/1611.10351 [read-abstract]
- Gunther, W., Ninad, U., Runge, J. (2023). Causal discovery for time series from multiple datasets with latent contexts. UAI 2023, PMLR 216. https://arxiv.org/pdf/2306.12896 (seen in search results only) [unverified]
- Granger, C. W. J. (1969). Investigating causal relations by econometric models and cross-spectral methods. Econometrica. [unverified]

### R-F. Population-dynamics latent models and latent-space comparison

- Sussillo D., Jozefowicz R., Abbott L.F., Pandarinath C. (2016). LFADS - Latent Factor Analysis via Dynamical Systems. arXiv. https://arxiv.org/abs/1608.06315 [read-abstract]
- Pandarinath C. et al. (2018). Inferring single-trial neural population dynamics using sequential auto-encoders. Nature Methods. [unverified]
- Keshtkaran M.R., Sedler A.R., et al. (2022). A large-scale neural network training framework for generalized estimation of single-trial population dynamics. Nature Methods. https://www.nature.com/articles/s41592-022-01675-0 [unverified] (coordinated dropout + PBT description taken from search-result snippets only)
- Sedler A.R., Pandarinath C. (2023). lfads-torch: A modular and extensible implementation of latent factor analysis via dynamical systems. arXiv. https://arxiv.org/abs/2309.01230 [read-abstract]
- lfads-torch repo and LICENSE. https://github.com/arsedler9/lfads-torch [repo/docs]
- Ye J., Pandarinath C. (2021). Representation learning for neural population activity with Neural Data Transformers. arXiv. https://arxiv.org/abs/2108.01210 [read-abstract]
- Le T., Shlizerman E. (2022). STNDT: Modeling Neural Population Activity with Spatiotemporal Transformers. NeurIPS 2022. https://arxiv.org/abs/2206.04727 [read-abstract]
- NDT repo. https://github.com/snel-repo/neural-data-transformers [repo/docs]
- Schimel M., Kao T.-C., Jensen K.T., Hennequin G. (2022). iLQR-VAE: control-based learning of input-driven dynamics with applications to neural data. ICLR 2022. https://www.biorxiv.org/content/10.1101/2021.10.07.463540v1 [read-full] (method sections via fetch)
- Yu B.M., Cunningham J.P., Santhanam G., et al. (2008). Gaussian-process factor analysis for low-dimensional single-trial analysis of neural population activity. NeurIPS 21. https://proceedings.neurips.cc/paper/2008/hash/ad972f10e0800b49d76fed33a21f6698-Abstract.html [read-abstract] (J. Neurophysiol. 2009 version not opened)
- Elephant GPFA docs and LICENSE.txt. [repo/docs]
- Gokcen E., et al. (2022). Disentangling the flow of signals between populations of neurons. Nature Computational Science. https://github.com/egokcen/DLAG [repo/docs] (paper itself not opened: [unverified])
- Macke J.H., Buesing L., Cunningham J.P., et al. (2011). Empirical models of spiking in neural populations. NeurIPS 24. https://proceedings.neurips.cc/paper/2011/hash/7143d7fbadfa4693b9eec507d9d37443-Abstract.html [read-abstract]
- Gao Y., Archer E., Paninski L., Cunningham J.P. (2016). Linear dynamical neural population models through nonlinear embeddings. NeurIPS 2016. https://arxiv.org/abs/1605.08454 [read-abstract]
- Zhao Y., Park I.M. (2017). Variational latent Gaussian process for recovering single-trial dynamics from population spike trains. Neural Computation. https://arxiv.org/abs/1604.03053 [read-abstract]
- dynamax repo; ssm repo. [repo/docs]
- Sussillo D., Barak O. (2013). Opening the black box: low-dimensional dynamics in high-dimensional recurrent neural networks. Neural Computation 25(3):626-649. https://web.stanford.edu/class/cs379c/archive/2016/calendar_invited_talks/articles/SussilloandBarakNC-13.pdf [read-full] (via fetch summary)
- Golub M.D., Sussillo D. (2018). FixedPointFinder: A Tensorflow toolbox for identifying and characterizing fixed points in recurrent neural networks. JOSS 3(31):1003. https://joss.theoj.org/papers/10.21105/joss.01003 [read-abstract]
- fixed-point-finder repo. [repo/docs]
- Mastrogiuseppe F., Ostojic S. (2018). Linking connectivity, dynamics and computations in low-rank recurrent neural networks. Neuron. https://arxiv.org/abs/1711.09672 [read-abstract]
- Dubreuil A., Valente A., Beiran M., et al. (2022). The role of population structure in computations through neural dynamics. Nature Neuroscience. [unverified] (only repo opened)
- Valente A., Pillow J.W., Ostojic S. (2022). Extracting computational mechanisms from neural data using low-rank RNNs. NeurIPS 35. https://proceedings.neurips.cc/paper_files/paper/2022/hash/9877d915a4b4f00e85e7b4cfdf41e450-Abstract-Conference.html [read-abstract] (PDF fetch summary used only where consistent with abstract)
- Valente A., Ostojic S., Pillow J.W. (2021). Probing the relationship between linear dynamical systems and low-rank recurrent neural network models. arXiv. https://arxiv.org/abs/2110.09804 [read-abstract]
- Pals M., Sagtekin A.E., Pei F., et al. (2024). Inferring stochastic low-rank recurrent neural networks from neural data. NeurIPS 2024. https://arxiv.org/abs/2406.16749 [read-abstract]
- Repos above. [repo/docs] (also cited in area G)
- Ostrow M., Eisen A., Kozachkov L., Fiete I. (2023). Beyond Geometry: Comparing the Temporal Structure of Computation in Neural Circuits with Dynamical Similarity Analysis. NeurIPS 2023 (arXiv). https://arxiv.org/abs/2306.10168 [read-abstract]
- Huang A., Ostrow M., Singh S.H., et al. (2025). InputDSA: Demixing then Comparing Recurrent and Externally Driven Dynamics. ICLR 2026 (arXiv). https://arxiv.org/abs/2510.25943 [read-abstract]
- Behrad A., Ostrow M., Fakharian M.T., et al. (2025). Fast dynamical similarity analysis. arXiv. https://arxiv.org/abs/2511.22828 [read-abstract]
- Guilhot Q., Wojcik M., Achterberg J., Costa R.P. (2024). Dynamical similarity analysis can identify compositional dynamics developing in RNNs. arXiv. https://arxiv.org/abs/2410.24070 [read-abstract]
- DSA repo and LICENSE. [repo/docs]
- Redman W.T., Bello-Rivas J.M., Fonoberova M., et al. (2023/2024). Identifying Equivalent Training Dynamics. arXiv. https://arxiv.org/abs/2302.09160 [read-abstract]
- Godara P., Tay P.S., Mattar M.G. (2026). Beyond DSA: Conjugacy-based Comparison of Dynamical Systems. arXiv. https://arxiv.org/abs/2607.04493 [read-abstract]
- Chen R., Vedovati G., Braver T., Ching S. (2025/2026). Comparing Dynamical Models Through Diffeomorphic Vector Field Alignment. Neural Computation 38(6). https://arxiv.org/abs/2512.18566 [read-abstract]
- Gosztolai A., Peach R.L., Arnaudon A., et al. (2025). MARBLE: interpretable representations of neural population dynamics using geometric deep learning. Nature Methods (arXiv 2023: "Interpretable statistical representations of neural population dynamics and geometry"). https://arxiv.org/abs/2304.03376 ; https://arxiv.org/html/2304.03376 [read-full] (methods section)
- MARBLE repo and LICENSE. [repo/docs]
- Raghu M., Gilmer J., Yosinski J., Sohl-Dickstein J. (2017). SVCCA: Singular Vector Canonical Correlation Analysis for Deep Learning Dynamics and Interpretability. NeurIPS 2017. https://arxiv.org/abs/1706.05806 [read-abstract]
- Morcos A.S., Raghu M., Bengio S. (2018). Insights on representational similarity in neural networks with canonical correlation. NeurIPS 2018. https://arxiv.org/abs/1806.05759 [read-abstract]
- Kornblith S., Norouzi M., Lee H., Hinton G. (2019). Similarity of Neural Network Representations Revisited. ICML 2019. https://arxiv.org/abs/1905.00414 [read-abstract]
- Davari M., Horoi S., Natik A., et al. (2022). Reliability of CKA as a Similarity Measure in Deep Learning. arXiv (ICLR 2023 per unverified). https://arxiv.org/abs/2210.16156 [read-abstract]
- Murphy A., Zylberberg J., Fyshe A. (2024). Correcting Biased Centered Kernel Alignment Measures in Biological and Artificial Neural Networks. ICLR 2024 Re-Align Workshop. https://arxiv.org/abs/2405.01012 [read-abstract]
- Harvey S.E., Larsen B.W., Williams A.H. (2023). Duality of Bures and Shape Distances with Implications for Comparing Neural Representations. arXiv. https://arxiv.org/abs/2311.11436 [read-abstract]
- Harvey S.E., Lipshutz D., Williams A.H. (2024). What Representational Similarity Measures Imply about Decodable Information. arXiv. https://arxiv.org/abs/2411.08197 [read-abstract]
- Williams A.H., Kunz E., Kornblith S., Linderman S.W. (2021). Generalized Shape Metrics on Neural Representations. NeurIPS 2021. https://arxiv.org/abs/2110.14739 [read-abstract]
- Duong L.R., Zhou J., Nassar J., et al. (2023). Representational dissimilarity metric spaces for stochastic neural networks. ICLR 2023. https://arxiv.org/abs/2211.11665 [read-abstract]
- netrep repo. [repo/docs]
- SciPy docs, scipy.linalg.subspace_angles (algorithm: Knyazev A.V., Argentati M.E. (2002), SIAM J. Sci. Comput. 23:2008-2040). https://docs.scipy.org/doc/scipy/reference/generated/scipy.linalg.subspace_angles.html [repo/docs]
- Bjorck A., Golub G.H. (1973). Numerical methods for computing angles between linear subspaces. Math. Comp. [unverified]
- Kriegeskorte N., Mur M., Bandettini P. (2008). Representational similarity analysis - connecting the branches of systems neuroscience. Frontiers in Systems Neuroscience 2:4. https://www.frontiersin.org/articles/10.3389/neuro.06.004.2008/full [read-full] (method parts)
- Facco E., d'Errico M., Rodriguez A., Laio A. (2017). Estimating the intrinsic dimension of datasets by a minimal neighborhood information. Scientific Reports. https://arxiv.org/abs/1803.06992 [read-abstract]
- Levina E., Bickel P.J. (2004). Maximum Likelihood Estimation of Intrinsic Dimension. NeurIPS 17. https://proceedings.neurips.cc/paper/2004/hash/74934548253bcab8490ebd74afed7031-Abstract.html [read-abstract]
- Owen A.B., Perry P.O. (2009). Bi-cross-validation of the SVD and the nonnegative matrix factorization. Annals of Applied Statistics 3(2):564-594. https://arxiv.org/abs/0908.2062 [read-abstract]
- Jazayeri M., Ostojic S. (2021). Interpreting neural computations by examining intrinsic and embedding dimensionality of neural activity. Current Opinion in Neurobiology. https://arxiv.org/abs/2107.04084 [read-abstract]
- Altan E., Solla S.A., Miller L.E., Perreault E.J. (2021). Estimating the dimensionality of the manifold underlying multi-electrode neural recordings. PLoS Comput. Biol. https://www.biorxiv.org/content/10.1101/2020.12.17.423196v1 [read-abstract] (only methodological findings used)
- Gao P. et al. (2017). A theory of multineuronal dimensionality, dynamics and measurement (participation ratio usage). bioRxiv. [unverified]
- scikit-dimension repo. [repo/docs]
- Izenman A.J. (1975). Reduced-rank regression for the multivariate linear model. J. Multivariate Analysis 5(2):248-264. https://ideas.repec.org/a/eee/jmvana/v5y1975i2p248-264.html [unverified] (only search snippet seen)
- Semedo J.D., Zandvakili A., Machens C.K., Yu B.M., Kohn A. (2019). Communication subspace (reduced-rank regression between populations). Neuron. [unverified] (deliberately not opened)

### R-G. Experiment design, canonical coordinates and evaluation

- R. K. Mehra, "Optimal input signals for parameter estimation in dynamic systems - Survey and new results", 1974, IEEE Trans. Automatic Control 19(6):753-768. [unverified] (bibliographic data from search results only)
- L. Pronzato, "Optimal experimental design and some related control problems", 2008, Automatica 44:303-325, https://arxiv.org/abs/0802.4381 [read-abstract]
- M. Gevers, "Identification for control" line of work (e.g. "Identification for control: from the early achievements to the revival of experiment design", Eur. J. Control 2005). [unverified]
- A. Chowdhary, S. E. Ahmed, A. Attia, "PyOED: An Extensible Suite for Data Assimilation and Model-Constrained Optimal Design of Experiments", 2023, arXiv/ACM TOMS, https://arxiv.org/abs/2301.08336 [read-abstract]; repo https://gitlab.com/ahmedattia/pyoed [repo/docs]
- J. C. Willems, P. Rapisarda, I. Markovsky, B. L. M. De Moor, "A note on persistency of excitation", 2005, Systems & Control Letters 54:325-329. [unverified] (abstract seen only in search snippets)
- C. De Persis, P. Tesi, "Formulas for Data-driven Control: Stabilization, Optimality and Robustness", 2019 CDC / IEEE TAC 65(3) 2020, https://export.arxiv.org/abs/1903.06842v3 [read-abstract]
- M. K. Camlibel, H. J. van Waarde, P. Rapisarda, "The shortest experiment for linear system identification", 2024, arXiv, https://arxiv.org/abs/2407.12509 [read-abstract]
- A. Foster, M. Jankowiak, E. Bingham et al., "Variational Bayesian Optimal Experimental Design", 2019, NeurIPS, https://arxiv.org/abs/1903.05480 [read-abstract]
- A. Foster, D. R. Ivanova, I. Malik, T. Rainforth, "Deep Adaptive Design: Amortizing Sequential Bayesian Experimental Design", 2021, ICML, https://arxiv.org/abs/2103.02438 [read-abstract]
- T. Rainforth, A. Foster, D. R. Ivanova, F. Bickford Smith, "Modern Bayesian Experimental Design", 2023/2024, Statistical Science, https://arxiv.org/abs/2302.14545 [read-abstract]
- dad repo https://github.com/ae-foster/dad [repo/docs]; BoTorch https://github.com/pytorch/botorch and https://botorch.org/docs/acquisition [repo/docs]
- M. Buisson-Fenet, F. Solowjow, S. Trimpe, "Actively Learning Gaussian Process Dynamics", 2020, L4DC (PMLR 120), https://arxiv.org/abs/1911.09946 [read-abstract]
- A. Capone, J. Umlauft, T. Beckers et al., "Localized active learning of Gaussian process state space models", 2020, L4DC, https://arxiv.org/abs/2005.02191 [read-abstract]
- P. Shyam, W. Jaskowski, F. Gomez, "Model-Based Active Exploration", 2019, ICML, https://arxiv.org/abs/1810.12162 [read-abstract]
- A. Hauser, P. Buhlmann, "Two Optimal Strategies for Active Learning of Causal Models from Interventional Data", 2014, Int. J. Approx. Reasoning 55(4), https://arxiv.org/abs/1205.4174 [read-abstract]
- R. Agrawal, C. Squires, K. Yang et al., "ABCD-Strategy: Budgeted Experimental Design for Targeted Causal Structure Discovery", 2019, AISTATS, https://arxiv.org/abs/1902.10347 [read-abstract]
- P. Tigas, Y. Annadani, A. Jesson et al., "Interventions, Where and How? Experimental Design for Causal Models at Scale", 2022, NeurIPS, https://arxiv.org/abs/2203.02016 [read-abstract]
- Zhang et al., "Active learning for optimal intervention design in causal models", 2023, Nature Machine Intelligence, arXiv:2209.04744 [unverified] (seen in search results only)
- M. H. Kazma, A. F. Taha, "Observability for Nonlinear Systems: Connecting Variational Dynamics, Lyapunov Exponents, and Empirical Gramians", 2024, arXiv, https://arxiv.org/abs/2402.14711 [read-abstract]
- A. J. Krener, K. Ide, "Measures of unobservability", 2009, IEEE CDC. [unverified]
- S. Lall, J. E. Marsden, S. Glavaski, "A subspace approach to balanced truncation for model reduction of nonlinear control systems", 2002, Int. J. Robust Nonlinear Control. [unverified]
- W. Govaerts, B. Sautois, "Computation of the phase response curve: a direct numerical approach", 2006, Neural Computation 18:817-847. [unverified] (search-result abstract only)
- Scholarpedia "Phase response curve" (Canavier; attempted fetch failed - certificate error). [unverified]
- A. T. Winfree, "The Geometry of Biological Time", 1980/2001; Y. Kuramoto, "Chemical Oscillations, Waves, and Turbulence", 1984; G. B. Ermentrout, N. Kopell, 1991 (adjoint). [unverified]
- A. Mauroy, I. Mezic, J. Moehlis, "Isostables, isochrons, and Koopman spectrum for the action-angle representation of stable fixed point dynamics", 2013, Physica D 261:19-30, https://sites.engineering.ucsb.edu/~moehlis/moehlis_papers/isostables.pdf [read-abstract] (fetched PDF; only a summary was extracted)
- D. Wilson, J. Moehlis, "Isostable reduction of periodic orbits", 2016, Phys. Rev. E 94:052213. [unverified] (fetch blocked; abstract seen only in search results)
- D. Wilson, B. Ermentrout, "Augmented phase reduction of (not so) weakly perturbed coupled oscillators", 2019, SIAM Review 61(2):277-315. [unverified]
- B. Monga, J. Moehlis, "Augmented Phase Reduction for Periodic Orbits Near a Homoclinic Bifurcation and for Relaxation Oscillators", 2020, arXiv, https://arxiv.org/abs/2005.11628 [read-abstract]
- N. Namura, S. Takata, K. Yamaguchi et al., "Estimating asymptotic phase and amplitude functions of limit-cycle oscillators from time series data", 2022, Phys. Rev. E 106:014204, https://arxiv.org/abs/2203.01663 [read-abstract]
- T. Yamamoto, H. Nakao, R. Kobayashi, "Gaussian Process Phase Interpolation for estimating the asymptotic phase of a limit cycle oscillator from time series data", 2024, arXiv, https://arxiv.org/abs/2409.03290 [read-abstract]
- D. Wilson, "Data-Driven Inference of High-Accuracy Isostable-Based Dynamical Models in Response to External Inputs", 2021, arXiv, https://arxiv.org/abs/2102.04526 [read-abstract]
- D. Sussillo, O. Barak, "Opening the Black Box: Low-Dimensional Dynamics in High-Dimensional Recurrent Neural Networks", 2013, Neural Computation 25(3). [unverified] (fetch blocked; seen via search result abstract)
- M. D. Golub, D. Sussillo, "FixedPointFinder: A Tensorflow toolbox for identifying and characterizing fixed points in recurrent neural networks", 2018, JOSS 3(31):1003; repo https://github.com/mattgolub/fixed-point-finder [repo/docs]
- G. Haller, S. Ponsioen, "Nonlinear normal modes and spectral submanifolds: existence, uniqueness and use in model reduction", 2016, Nonlinear Dynamics 86:1493-1534, https://arxiv.org/abs/1602.00560 [read-abstract]
- M. Cenedese, J. Axas, B. Bauerlein et al., "Data-driven modeling and prediction of non-linearizable dynamics via spectral submanifolds", 2022, Nature Communications 13:872, https://arxiv.org/abs/2201.04976 [read-abstract]
- W. Gilpin, "Chaos as an interpretable benchmark for forecasting and data-driven modelling", 2021, NeurIPS Datasets & Benchmarks, https://arxiv.org/abs/2110.05266 [read-abstract]; repo https://github.com/williamgilpin/dysts and https://github.com/williamgilpin/dysts/blob/master/dysts/metrics.py [repo/docs]
- M. Brenner, C. J. Hemmer, Z. Monfared, D. Durstewitz, "Almost-Linear RNNs Yield Highly Interpretable Symbolic Codes in Dynamical Systems Reconstruction", 2024, arXiv (NeurIPS 2024 (unverified)), https://arxiv.org/html/2410.14240 [read-full] (main text; D_stsp and D_H defined as KL of state-space occupation and dimension-wise Hellinger distance of power spectra; detailed estimator settings are in its appendix, not read)
- D. Kramer, P. L. Bommer, C. Tombolini et al., "Reconstructing Nonlinear Dynamical Systems from Multi-Modal Time Series", 2022, ICML (unverified venue), https://arxiv.org/abs/2111.02922 [read-abstract]

---

# Appendix. Detailed per-area synthesis notes

Condensed in Part II; kept here for the detailed recipes, hyperparameters and area-specific pitfalls.

## Appendix A. Area synthesis notes: Classical system identification, minimal realisation and model reduction

#### Tournament candidates from this area
1. **Interventional empirical-gramian balanced reduction (EG-BT) + Galerkin/learned closure.**
   Data: from a set of operating points (random initial states on/near typical trajectories, several parameter draws),
   apply (i) impulse/step input perturbations on each intervention channel at 2-3 amplitudes (controllability ensemble)
   and (ii) +/- eps state offsets along N directions or along a random/ PCA-truncated subset of directions
   (observability ensemble, with output = readout y, and separately output = full x). Compute empirical controllability
   W_c and observability W_o (or cross gramian, emgr), balance by square-root SVD, choose k at the Hankel-singular-value
   elbow. Encoder phi = balancing projection (linear); transition: Galerkin projection of the simulator vector field if
   accessible, else fit f(z,u) by regression (linear or small MLP) on projected trajectories. Sweep: perturbation scale
   eps in {1e-3, 1e-2, 1e-1} x state std, number of operating points, output choice (y vs x). Why: the only classical
   method whose state is chosen jointly by "what interventions can move" and "what the readout can see" - a direct
   operationalisation of props (3),(4),(5).
2. **Subspace identification with interventions as inputs (N4SID/CVA -> PEM/EM refinement).**
   Data: many trajectories with random persistently exciting inputs (white or random multisine on each input channel,
   plus random pulse state offsets encoded as extra impulse input channels), initial states from the simulator's
   stationary distribution. Outputs: y alone (readout-minimal state) and x (or a PCA(x) to ~50-200 dims) (full-state
   baseline). Fit CVA-weighted SID with p = f in {5, 10, 20, 40} steps (should exceed the slowest relevant timescale / dt
   if feasible, subject to T >> (p+f)(m+n_u)); order k via canonical-correlation elbow + Bauer-style criteria + CV
   plateau; refine with EM (dynamax) or PEM. Encoder phi(x) = linear map from x to the Kalman state (regress the SID
   state sequence on x, or use Cx pseudoinverse when outputs = x). Why: strongest linear baseline; interpretable; fast;
   deterministic.
3. **PSID-style readout-prioritised SID (y = x-features, z = readout).** Report n1 (readout-sufficient) vs nx
   (closure-sufficient); gap between them is itself a finding about properties (2) vs (5).
4. **Local-linear / piecewise ERA atlas (diagnostic, not a final model).** ERA at multiple operating points from
   simulator impulse responses; compare Hankel ranks and principal angles between local observable subspaces. If ranks
   and subspaces agree, a global linear encoder is plausible; if they rotate, nonlinear encoders are needed. Cheap and
   informative for props (4),(6),(8).

#### Baselines from this area and how to implement each well
- **PCA + linear dynamics:** PCA on x (standardised per unit, fitted on training trajectories only); for each k, fit
  z(t+1) = A z + B u + c by ridge LS (ridge chosen by CV); evaluate multi-step free-run, not only one-step. Include
  the variant PCA on [x, lagged x] (delay-PCA) to separate "variance" from "memory".
- **Factor analysis + LDS:** sklearn-style FA to initialise C, R; then LDS-EM (dynamax) with inputs; initialise A, B from
  N4SID; stop EM by held-out log-likelihood; floor Q, R eigenvalues (e.g. 1e-6 x trace/k).
- **N4SID / CVA:** use CVA weighting by default (orders by canonical correlation); pre-whiten/standardise channels; if m
  large, pre-project outputs to top 100-200 PCs and report sensitivity; enforce stability (reflect eigenvalues or
  constrained LS); check persistency of excitation by rank of input block Hankel (depth p+f); avoid closed-loop inputs
  (inputs computed from outputs) or use SSARX/PBSID-type variant (MATLAB `N4Weight='SSARX'`); refine with PEM/EM.
  Report k from (a) canonical correlations > surrogate threshold (parallel-analysis-style with phase-randomised or
  trial-shuffled surrogates), (b) CV multi-step plateau, (c) BIC on the refined model.
- **ERA from simulator impulse responses:** unit-pulse on each input channel and on selected state-offset directions,
  averaged over K repeated runs from the same initial state distribution (subtract the unperturbed run from the same
  seed/initial state to cancel autonomous dynamics - paired-difference design). Hankel with p, q >= 3 x expected order
  and covering >= 3 slowest time constants; choose k at HSV elbow.
- **Hankel DMD / DMDc and HAVOK:** delays q chosen so q*dt covers the slowest relevant timescale; rank r by optimal
  hard threshold or HSV elbow (optimal-threshold method not verified here); for HAVOK, report it as non-closed (needs
  forcing) and only use Hankel DMDc as the closed predictive baseline.
- **Readout-history-only and input-only predictors (Takens / NARX justification):** NARX from (y history, u history)
  with sparse polynomial (SysIdentPy FROLS, AIC/BIC) for low-dim y; ridge linear ARX as the simplest. These bound what an
  encoder of x must beat.
- **Full-state predictor:** LS or ridge VAR on all x (or large PCA) with inputs - the "no compression" upper reference.

#### Using simulator interventions/inputs as excitation (practical rules)
- Persistency of excitation: inputs white/random-binary or random-phase multisine covering the band of interest; the
  input block Hankel of depth (p+f) must be full row rank (check numerically, condition number < 1e6).
- Prefer many medium-length trajectories with independent random initial states and inputs (ensemble data) over one long
  run: covers state space, supports trajectory-level train/test split, and matches finite-sample theory that counts
  trajectories.
- Amplitude ladder: run each experiment at 2-3 input amplitudes; compare BLA/linear model fit across amplitudes to
  quantify nonlinearity (Schoukens & Ljung workflow). Large divergence -> linear baselines are local only.
- State-offset interventions: encode as impulse inputs on an augmented channel with known direction; this makes them
  first-class inputs for SID/ERA/gramian methods, and allows held-out offset directions to test (3).
- Structural interventions (unit/connection removal) change A; treat as separate "systems" and test whether a shared
  encoder/transition generalises, or include as parameters in augmented gramians (emgr joint gramian).
- Paired designs: for every perturbed run keep an unperturbed twin with identical seed/initial state; analyse the
  difference (removes autonomous variability, yields clean impulse responses).

#### Evaluation measures relevant to (1)-(8) from this area, and pitfalls
- (1) Multi-horizon free-run prediction error of y (and of x for full-state) normalised by variance, at horizons
  {1, 5, 20, 100} steps; report one-step AND simulation (Schoukens & Ljung: simulation is much harder).
- (2) Closure: compare prediction from z(t) alone vs from z(t) plus history (z(t-1..t-L)) or plus x(t); the gain from
  history should be ~0 (conditional-independence-style test).
- (3) Interventional: held-out input channels, held-out offset directions, held-out amplitudes; compare to the
  linear-response prediction of the identified (A,B).
- (4) Microstate invariance: sample pairs x, x' with phi(x) ~= phi(x') (e.g. perturb x along the estimated null space of
  phi, or along directions with low empirical observability energy) and measure divergence of simulated futures of y;
  compare with the empirical observability gramian of the true system (directions with low W_o energy SHOULD be in the
  null space).
- (5) Minimality: HSV / canonical-correlation spectrum, Bauer-style criteria, CV plateau; report the whole curve.
- (6) Stability: principal angles between subspaces (linear encoders) across seeds/data splits; eigenvalues of A are
  similarity-invariant and directly comparable; transfer functions / Markov parameters are invariant comparisons.
- (7) Shared f: compare identified (A,B) across implementations up to similarity via eigenvalues, Markov parameters or
  balanced realisations (near-canonical), not raw matrices.
- (8) Abstention: absence of gap in HSV/canonical correlations; CV curve without plateau; empirical gramian spectra with
  slow decay.
- Pitfalls: (i) Hankel/delay matrices built before the train/test split leak future samples through overlapping
  windows - split by trajectory first; (ii) output copying - when y is in the output set and D != 0 or lags include
  current y, one-step prediction is trivial - always evaluate multi-step free-run; (iii) input copying - if y depends
  directly on u (D term), a "state" that is just u looks good - include an input-only baseline; (iv) parameter-identity
  leakage - different parameter draws create separable clusters in x that an encoder can memorise; hold out parameter
  draws; (v) closed-loop bias in SID if inputs were generated from outputs; (vi) order "cheating" through high-frequency
  or ill-conditioned coordinates - require bounded condition number of the encoder / report balanced coordinates;
  (vii) EM local optima and unstable A estimates - initialise from SID and check spectral radius.

#### Open problems (literature gives no good answer)
- Minimal-state (Nerode) estimation for NONLINEAR input-driven systems from finite simulator data: there is existence
  and minimality theory (Rojas & Wachel 2022; rational systems) but no practical, consistent estimator or order test.
- Empirical gramians give one global linear subspace; no standard method yields a curved (nonlinear) balanced
  manifold from simulation data at N ~ 1e3-1e4 (energy-function balancing scales via Taylor tensors but needs the model
  and polynomial structure).
- Order selection for nonlinear models: IC parameter counts are meaningless for over-parameterised models, and
  singular-value gaps vanish under nonlinearity; CV plateaus are the only practical tool and lack guarantees.
- Excitation design for interventional sufficiency: persistency-of-excitation theory is for LTI/Koopman-embeddable
  systems; no guidance on how to choose intervention types so that held-out intervention TYPES (not just amplitudes or
  sequences) are predictable.
- Shared dynamics across implementations: classical theory compares systems up to similarity via I/O maps, but there is
  no standard identification procedure that fits one shared (A,B) (or f) with implementation-specific encoders and
  tests the hypothesis statistically.
- Ill-conditioning when n/m is large (few readout channels, many states): subspace methods need super-polynomial data
  in n/m (Sun et al. 2025); readout-only identification of a moderately large state is fundamentally hard, which
  argues for using x (the full microstate) as output during identification and y only for evaluation.

---

## Appendix B. Area synthesis notes: Koopman operator learning, DMD and sparse identification

#### Tournament candidates from this area

1. **Koopman autoencoder with inputs and encoder-mediated interventions (KAE-u).**
   - Data: many short trajectories (length 50-200 steps) from randomised initial states. Include states produced by random
     state offsets on top of on-attractor states. Add open-loop random input currents: band-limited noise plus sparse random
     impulses, with per-unit injection patterns drawn at random so that many target sets are covered. Hold out entire
     intervention *types* and *target sets*.
   - Model: z = phi(x) (MLP; per-implementation encoders for prop 7), z+ = K z + B(z) u. Start with plain B; use a bilinear
     B(z) = B0 + sum_i z_i B_i as the ablation. Readout y = g(z, u), linear first.
   - Loss: multi-step open-loop latent and readout prediction over horizon H in {10, 30, 100}, with discount delta in
     [0.9, 1] (Otto & Rowley). Add a reconstruction term only as a regulariser. Add a latent-consistency term
     ||phi(x_{t+m}) - K^m phi(x_t)|| (Lusch).
   - Interventions: apply microscopic interventions in x-space and re-encode, z' = phi(x + delta), plus B for currents via
     z' = phi(x + dt B_micro u) during training. This gives zero-shot transfer to unseen targets.
   - Stability: parameterise K as block-rotation times contraction (|lambda| <= 1).
   - Sweep: k in {1..16}, H, loss weights, encoder width, bilinear on or off.
   - Choose k at the plateau of held-out multi-horizon prediction error and of the ResDMD residual of the learned phi.
2. **VAMP/VAMPnet encoder plus readout head.**
   - Objective: VAMP-2 at several lags (tau in {1, 5, 20} steps), plus a readout loss for y.
   - Validation: Chapman-Kolmogorov and implied-timescale flatness.
   - Choose k by the cross-validated VAMP-E plateau.
   - Caveats: deterministic simulators violate the theory. Run with intrinsic noise if the simulator has it, or treat
     ensembles. It has no input handling, so add B u, or train per input regime.
3. **SINDy-autoencoder with control (SINDyAE-c).**
   - Architecture: encoder per implementation, one shared sparse f(z, u) = Theta(z, u) Xi.
   - Library: polynomial degree 2-3 plus optional saturating terms.
   - Derivatives: use the simulator's exact x_dot through the chain rule, which removes the main stated limitation.
   - Thresholding: 0.05-0.1 on standardised z every ~500 epochs, then a final unregularised refit.
   - Seeds: run 5-10 and compare aligned Xi.
   - Choose k by the smallest k whose held-out multi-step error is within tolerance of the plateau.
4. **EDMDc on PCA/delay coordinates with balanced truncation to k.**
   - Pipeline: PCA to r ~ 20-50, then RBF or polynomial dictionary (K ~ 100-500), then EDMDc (A, B, C), then ResDMD filtering,
     then balanced truncation to k (as in Otto & Rowley's BPOD step).
   - This is a cheap, fully deterministic "non-deep" competitor that tests whether deep encoders add anything.
5. **Active-learning wrapper (from E-SINDy).** For any candidate above, pick the next simulator experiment (initial state,
   input, intervention) by maximum ensemble disagreement among bootstrap or seed replicates. This is a
   counterexample-guided refinement loop.

#### Baselines from this area and how to implement each well

- **DMD / PCA + linear dynamics:**
  - Rank: centre the data. Choose r by the cumulative-energy knee *and* held-out multi-step error. The Gavish-Donoho
    optimal hard threshold is a principled default (unverified here; not read).
  - Modes and noise: use exact DMD modes. If the readouts are noisy, use fbDMD or BOP-DMD.
  - Reporting: report eigenvalues as continuous-time rates log(lambda)/dt.
- **Delay/Hankel DMD (HAVOK-style):**
  - Stack d delays with d*dt at about one to two times the slowest relevant timescale. Choose d by a validation curve.
  - SVD the Hankel matrix and keep r.
  - Split train and test **by trajectory**, never by time window inside a trajectory: overlapping windows leak the future.
  - The encoder then uses past observations only (causal).
- **DMDc / ioDMD:**
  - Inputs must be open-loop and persistently exciting.
  - If the microscopic input map is known, fix it (known-B DMDc) and project it into the reduced basis.
  - Enforce stability, by eigenvalue clipping or a constrained fit (Benner et al.).
  - Fit y_k = C x_k + D u_k with the same-time input only.
- **EDMD / Koopman:**
  - Dictionary: [1, PCA coordinates, RBFs on PCA coordinates with centres from k-means (K = 50-500), optionally degree-2
    monomials].
  - Standardise the features. Solve with truncated-SVD pseudoinverse or ridge.
  - Target lifting dimension: M/K >= 10-20.
  - Validate spectra with ResDMD residuals (discard modes with residual > epsilon, e.g. 0.1-0.2) and by checking
    eigenvalue persistence as K and M grow.
  - Validate multi-step on held-out trajectories.
- **Kernel DMD:** Gaussian kernel with bandwidth set to the median pairwise distance times {0.5, 1, 2}. Truncate at a relative
  singular value of 1e-6 to 1e-3 or a fixed rank. Use subsampled M <= 10^4.
- **TICA/VAMP:** Lags within trajectories only. Regularise C00 by eigenvalue cut-off. Choose dimension by VAMP-E
  cross-validation. Run a Chapman-Kolmogorov check at multiples 2-5 of tau.
- **Koopman autoencoder (Lusch/Otto-Rowley style):**
  - Loss and schedule: multi-step loss with horizon curriculum (start at 5, grow to 50 or more). Pretrain the autoencoder.
  - K: stable parameterisation.
  - Model selection: early stopping on held-out trajectory rollout, not one-step error. At least 5 seeds.
  - Reporting: the eigenvalues of K and their variance across seeds.
- **SINDy / SINDYc on PCA coordinates:**
  - Library: standardise the library columns; degree 2 first.
  - Threshold: sweep lambda over a log grid and pick by held-out *simulation* error (Pareto knee).
  - Discrete time: with a discrete-time simulator, use the discrete-time form or the simulator's x_dot. Otherwise use
    weak-form or smoothed derivatives.
  - Uncertainty: E-SINDy with q = 100 and inclusion threshold 0.6.
- **Operator inference:** Quadratic reduced model on POD coordinates with Tikhonov regularisation chosen by rollout error.
  Also run the re-projection variant as the closure test (see below).

#### Evaluation measures relevant to properties (1)-(8)

- **(1) Predictive sufficiency:**
  - Open-loop multi-horizon error curves (1, 5, 20, 100 steps) on held-out trajectories and held-out interventions,
    normalised per horizon.
  - Always report against trivial predictors: persistence, input-only, readout-history-only, full-state linear.
- **(2) Markov closure:**
  - Chapman-Kolmogorov test K(n tau) vs K(tau)^n (VAMPnets/MSM).
  - ResDMD residuals of the learned phi used as a dictionary.
  - The operator inference closure gap: fit f on encoded raw trajectories vs on re-encoded one-step simulator
    re-projections. For a closed z these coincide (Peherstorfer 2019).
  - Improvement in prediction from adding latent history (delays) should be about 0.
- **(3) Interventional sufficiency:**
  - Prediction error on held-out intervention types and targets, comparing learned-B vs encoder-mediated interventions.
  - Separate "seen targets, new amplitudes" from "new targets" from "new intervention type (e.g. removal)".
- **(4) Microstate invariance:** Sample microstates x, x' with ||phi(x) - phi(x')|| < eps (by optimisation, or by perturbing
  within the approximate null space of the encoder's Jacobian). Simulate both and compare future readout divergence. EDMD
  eigenfunction level sets give the linear analogue.
- **(5) Minimality:** Plateau k from held-out multi-horizon error. Singular-value gap (DMD, VAMP). Number of residual-certified
  eigenvalues. SINDy sparsity as a secondary measure.
- **(6) Stability:**
  - Spectra (continuous-time eigenvalues or implied timescales) across seeds, bags (BOP-DMD) and estimators.
  - Subspace principal angles between seeds.
  - E-SINDy inclusion probabilities.
  - Eigenvalues are similarity-invariant; compare them with Hungarian matching on the complex plane.
- **(7) Shared across implementations:** Fit one shared K or Xi with per-implementation encoders. Compare the fit with
  implementation-specific K. Compare spectra, because they are conjugacy invariants: equal spectra are necessary, not
  sufficient, for linear conjugacy.
- **(8) Abstention:** No singular-value or VAMP gap. No k with small ResDMD residual. Held-out error not plateauing. CK test
  failing at every k. Report "no compact linear-latent state" and fall back to nonlinear f (SINDy-AE / neural).

#### Pitfalls

- **Time leakage.** Delay/Hankel windows, lagged pairs, and random splits over pairs from the same trajectory leak the future.
  Split by trajectory and by parameter draw.
- **Future-input leakage.** Regressing on u_{k+1} in DMDc or ioDMD, or using a non-causal (centred) delay encoder.
- **Output copying.** If y or a near-copy is in x, a readout-only z trivially "works". Always compare against the
  readout-history-only baseline.
- **Input copying.** For strongly driven systems, a z that stores recent u predicts well. Compare against the input-only
  baseline and against held-out input statistics.
- **Parameter-identity leakage.** If trajectories from the same parameter draw appear in train and test, EDMD, kernel DMD and
  autoencoders can encode draw identity. Use grouped splits.
- **Memorisation.** Kernel DMD is a lookup over training samples. Deep encoders with trajectory-specific quirks overfit.
  Evaluate on new initial-state distributions.
- **Dimension cheating.**
  - The EDMD and Korda-Mezic lifted dimension (100s) is not k. Only count dimensions after truncation.
  - A Koopman-AE latent can encode continuous information in pathological ways (space-filling, very high-frequency
    encodings). Penalise encoder Lipschitz constants and test robustness of z to small x noise.
  - Products of eigenfunctions inflate apparent dimension, so count only independent (functionally generating) eigenfunctions.
- **Noise bias.** Sensor noise makes DMD eigenvalues look more stable. Do not interpret damping from noisy readouts without
  fbDMD, tlsDMD or BOP-DMD.
- **Theory mismatch.** VAMP/VAMPnet theory does not cover deterministic dynamics. Consistent Koopman AE assumes invertible
  (non-dissipative) dynamics.

#### Open problems where the literature gives no good answer

- Koopman models with **interventions that change the system** (unit or connection removal): there is no standard treatment
  beyond parametric models or per-regime operators. Predicting unseen removal targets is unaddressed.
- **Held-out intervention targets** in learned latent B: there is no identifiability theory for when latent input maps
  generalise to new injection sites. Encoder-mediated interventions are plausible but not theoretically analysed (my
  proposal, unverified in the literature).
- **Multistable / multi-attractor networks:** finite linear Koopman models cannot represent several isolated attractors. Local
  or switching Koopman models lack a principled minimal-k criterion.
- Choice of dictionary, kernel, lifting dimension and latent dimension remains "an open question" (Williams et al.). ResDMD
  certifies a dictionary but does not construct a minimal one.
- **Seed stability of deep Koopman and SINDy-AE encoders:** only spectra are comparable, and there is no accepted canonical
  alignment of nonlinear encoders across seeds or implementations.
- Spectral theory (VAMP, ResDMD measures) mostly assumes stochastic or measure-preserving settings. Deterministic, dissipative,
  input-driven simulators with transients fit none of these assumptions cleanly.
- There is no general closure test for nonlinear encoders. Re-projection (OpInf) and Chapman-Kolmogorov tests are the nearest
  tools, and extending re-projection to nonlinear encoders needs a decoder, i.e. a right-inverse of phi.

---

## Appendix C. Area synthesis notes: Predictive states, causal states, bisimulation and abstraction refinement

#### Formal definitions to adopt (for props 2, 4, 5, 8)
Let T be a test bank: each test tau = (input sequence u_{0:H}, optional intervention a at time 0 or during the window,
readout functional of y_{1:H}). For microstates x, x':
- **Predictive equivalence (prop 4):** x ~_T x' iff Law(tau-outcome | x) = Law(tau-outcome | x') for all tau in T.
  Epsilon version: D(Law(.|x), Law(.|x')) <= epsilon for all tau (D = MMD or W_1 over simulator noise; for a deterministic
  simulator, the output difference norm).
- **Closure (prop 2):** the partition/encoder is a bisimulation: phi(x) = phi(x') implies phi(F(x,u)) = phi(F(x',u)) in
  distribution and g agrees; epsilon version = quasi-lumpability spread / ZP residual at each horizon.
- **Minimality (prop 5):** coarsest such partition; in coordinates, smallest k whose encoder achieves the epsilon
  equivalence (compare with Hankel/test-matrix rank and with the kernel causal-state spectral gap).
- **Interventional sufficiency (prop 3):** same as (4) but T includes interventions; held-out intervention types are
  a *new test bank* T' and the honest statement is "~_T implies ~_T' ?" - evaluate, never assume.
- **Abstention (prop 8):** declare "no compact state" if, as the tolerance epsilon decreases or the horizon H / test
  bank grows, the required k (or number of classes, Hankel rank, C_mu) keeps growing without a plateau up to k_max, or
  if predictive information I_pred(T) keeps growing with T (Bialek et al. log/power-law regimes).

#### Tournament candidates from this area

1. **Simulation-based counterexample-guided refinement of a continuous latent state (CEGAR-Z).** Concrete recipe:
   - *Data/initialisation.* Sample a reference distribution of microstates by running the simulator from random initial
     states under random (band-limited, multi-scale) inputs, discarding burn-in; also include perturbed states
     (x + small offsets along random and top-variance directions). Initial test bank T_0: M (e.g. 32-64) input
     sequences of length H in {1, 5, 20, 50} steps (step, pulse, noise, zero input) plus a few intervention types from
     the training intervention set. Initial encoder: linear phi_0 from DCA or input-conditioned Hankel/CCA with k_0 = 2.
   - *Model.* Encoder phi (linear first, then MLP with spectral-norm Lipschitz bound L), transition f(z,u) (MLP or
     locally linear), readout g(z,u). Loss: multi-horizon readout loss over T (sum over H of ||g(z_hat_H) - y_H||^2), latent
     closure loss ||f(phi(x_t),u_t) - sg(phi(x_{t+1}))||^2 with stop-gradient/EMA target (Ni et al.), plus a
     metric-matching term (MICo/DBC-style) d_z(x,x') ~ d_T(x,x') where d_T is the behavioural distance over the test bank.
   - *Counterexample search (equivalence oracle).* Two kinds, both run on the real simulator:
     (a) **Invariance counterexamples:** find pairs (x, x') with ||phi(x) - phi(x')|| <= delta but max_tau D(tau|x, tau|x') >
     epsilon. Search: nearest-neighbour pairs in z from the reference set; then adversarial local search
     x' = x + v with v optimised (CMA-ES or gradient if the simulator is differentiable) to maximise output divergence
     minus lambda ||phi(x+v) - phi(x)||; also optimise the input sequence u (falsification-style, as in
     S-TaLiRo) to maximise divergence given the pair. (b) **Closure/prediction counterexamples:** (x, u) where the
     rolled-out abstract prediction g(f^H(phi(x),u)) differs from the simulated readout by > epsilon, or where
     phi(x_{t+H}) differs from f^H(phi(x_t)) by more than the tolerance (CEGAR's "spurious abstract trace").
   - *Validation.* For stochastic simulators, re-simulate each candidate with R (e.g. 20-50) noise seeds and accept only if
     a two-sample test (MMD permutation test, or KS on scalar summaries; cf. CSSR's split test) rejects equality at level
     alpha with multiple-testing control; for deterministic simulators require the difference to exceed numerical
     tolerance and be stable to integrator step.
   - *Refinement.* (i) Add the distinguishing test (u, a, H, readout functional) to T (L*-style suffix set). (ii) Add the
     pair to a "must-separate" set with hinge loss max(0, m - ||phi(x) - phi(x')||) and to the metric-matching pairs.
     (iii) Retrain (warm start). If the loss cannot separate the counterexamples while keeping the fit, increase k by 1
     (new coordinate initialised on the residual direction, e.g. top CCA direction between x and the unexplained test
     outcomes). Symmetric **merge** step for minimality: pairs with large ||phi(x)-phi(x')|| but indistinguishable on all
     of T get a pull-together term (or k is pruned if a coordinate becomes predictively irrelevant).
   - *Termination / choice of k.* Stop when B (e.g. 10^3-10^4 simulations) of oracle search finds no validated
     counterexample at tolerance epsilon; with m independent random tests passing, the usual PAC-style statement bounds
     the probability mass of undetected disagreement (as for randomised equivalence oracles in L*), but adversarial
     search gives no such bound - report both. Sweep epsilon (and H_max) and plot required k(epsilon, H): plateau -> k;
     no plateau up to k_max -> abstain (prop 8).
   - *Hyperparameters to sweep:* epsilon, delta, H_max, test-bank families, Lipschitz bound L, k_max, oracle budget B,
     seed. Stability (6): repeat with different seeds and different initial encoders; compare final partitions via
     pairwise-equivalence agreement and coordinates via CCA/Procrustes.
   - *Why:* It uses the simulator's reset/query power directly, targets (2)(3)(4)(5)(8) explicitly, is
     implementation-agnostic, and each refinement is explained by a concrete experiment.

2. **Input-conditioned predictive-state regression (microstate PSR / 2SR with resets).** Sample microstates x_i; for each,
   simulate a fixed probe bank of input sequences and record future-readout features (moments or random Fourier
   features of y windows) -> matrix Phi_future (n x m). Fit a reduced-rank regression x -> Phi_future (rank k sweep,
   ridge); the rank-k left factor is a linear encoder; the singular spectrum gives k. Transition f learned by 2SR
   (regress next predictive state on current predictive state x input features). Nonlinear variant: kernel or random
   features of x. Choose k by held-out predictive loss plateau and by the singular-value gap. Very strong, cheap baseline;
   also the natural estimator of the "test matrix rank".

3. **Kernel causal states on microstates (kernel epsilon-machine with inputs).** Conditional mean embedding of
   (probe-input-conditioned) future-output windows given x (Gram on x with Nystrom), diffusion-map reduction of the
   embedded states; k from the spectral gap; transition by kernel regression in the reduced coordinates. Sweep bandwidths
   and probe banks. Good for low-to-moderate N and as a nonparametric check on the minimal dimension.

4. **Bisimulation-metric encoder with vector readout (MICo/DBC-y).** Replace reward by the readout y (vector) and use a
   MICo-style bootstrapped loss with sampled pairs under the same input sequence (and matched intervention), plus a
   multi-horizon readout and ZP closure loss. Sweep gamma (effective horizon), beta (angular weight), k. Report whether
   the learned distance matches simulated behavioural distances on held-out pairs.

5. **Markov-abstraction encoder (inverse + contrastive ratio + ZP).** Allen et al. losses with "action" = input u and
   intervention label, combined with readout prediction. Useful mainly for (2) and (3): the inverse-model term forces z to
   carry what distinguishes the effects of different inputs/interventions.

6. **Discretised active automata learning (for small N or coarse readouts).** Quantise inputs to a small alphabet (e.g.
   5-10 input patterns including interventions) and readouts to a few symbols (or threshold events); run AALpy L*/KV (or
   L*_MDP / stochastic Mealy for noisy simulators) with the simulator as SUL; resets = re-initialising from sampled
   microstates. Output: minimal Mealy/MDP state count as a function of quantisation resolution -> plateau test for
   finite state, abstention if it explodes. Mostly a diagnostic, not a final continuous model.

#### Baselines from this area and how to implement each well
- **Hankel / test-matrix SVD (spectral PSR):** centre features, use input-conditioned blocks (or regress out future
  inputs, as in subspace ID), ridge-regularised pseudoinverses, choose k by held-out multi-step error, not by a fixed
  singular-value threshold. Report the full singular spectrum.
- **DCA:** use BouchardLab package; T in {3, 5, 10}; >= 5 restarts; diagonal regularisation of covariances; compare
  I_pred(d) curves across d to choose k; note DCA ignores inputs -> also run it on residuals after regressing out input
  history, and on input-free (autonomous) segments.
- **CSSR / transCSSR:** only on coarse-grained readouts (and inputs) - symbolise with quantiles; sweep L_max and alpha;
  report states-vs-L_max curves; use as an abstention diagnostic, not as the main model.
- **Partition refinement on an estimated finite chain:** cluster microstates (k-means with many clusters, e.g. 500-2000)
  -> estimate block transitions per input symbol -> run lumping/refinement with epsilon-quasi-lumpability tolerance ->
  coarsest partition size vs epsilon. Pitfall: the initial clustering must be fine enough, else errors are
  attributed to the abstraction instead of the discretisation.
- **Self-predictive (ZP) encoder:** always add a readout-prediction loss (ZP alone admits collapse); stop-gradient/EMA
  target; monitor phi^T phi rank.
- **MICo encoder:** implement the reduced distance; target network; pairs sampled from the same minibatch under the same
  inputs.

#### Evaluation measures relevant to (1)-(8), with pitfalls
- (1) Predictive sufficiency: multi-horizon readout error under held-out input sequences from microstates drawn from the
  reference distribution and from off-distribution (perturbed) microstates; compare against a full-state predictor as
  ceiling and input-only / readout-history-only predictors as floors.
- (2) Closure: latent consistency ||f^H(phi(x_t),u) - phi(x_{t+H})|| normalised by latent spread; Markov test = does
  adding z_{t-1..t-p} (or x_t itself) to the transition model reduce error? (conditional-MI or held-out gain; Allen's
  contrastive ratio classifier as a test); epsilon-quasi-lumpability spread on a discretised z.
- (3) Interventional sufficiency: predictive-equivalence gap on held-out intervention banks (new types and targets);
  "do pairs with equal z respond equally to an unseen intervention?"
- (4) Microstate invariance: **equivalence gap** = expected future-output divergence (MMD/W1 over simulator noise, across
  the test bank) between microstate pairs with ||phi(x)-phi(x')|| < delta, as a function of delta; ideally ~ Lipschitz in
  delta. Construct pairs adversarially too (the CEGAR oracle doubles as an evaluator; keep evaluation oracle budget and
  seeds separate from training).
- (5) Minimality: smallest k reaching the (1)-(4) thresholds; compare with test-matrix rank, DCA I_pred(d) plateau,
  kernel causal-state spectral gap, automaton state count.
- (6) Stability: agreement of induced partitions (pairwise same-class agreement, adjusted Rand on discretised z) and
  CCA/Procrustes of coordinates across seeds, oracles, and methods.
- (8) Abstention: k(epsilon, H) growth curves; I_pred(T) growth; CSSR/automaton state count vs resolution; calibrated
  on synthetic simulators with known finite and known non-compact state (e.g. chaotic regimes).
- Pitfalls: **dimension cheating** - a single real coordinate can encode arbitrarily many classes, so exact
  equivalence notions are meaningless in R^k without a smoothness constraint: enforce Lipschitz encoders/decoders, add
  noise to z during training (an information-bottleneck rate), and evaluate with delta-balls rather than exact equality;
  **output copying** - if y is a (near-)linear function of x, z = y trivially passes 1-step tests: use multi-horizon and
  input-conditioned tests; **input copying** - forbid u_t in phi, test on inputs uncorrelated with the past;
  **future leakage** - microstate sampling must not use future information (no smoothing across the evaluation window);
  **time leakage** - split train/test by trajectory and by initial-state region, not by time index within a trajectory;
  **parameter-identity leakage** - pairs used for (4) must come from the same parameter draw unless parameters are
  part of the state; **memorisation** - held-out microstates and held-out test inputs; oracle overfitting - the
  counterexample generator used for training must not be the only one used for evaluation.

#### Open problems (literature gives no good answer)
- Continuous-state predictive equivalence with finite samples and inputs: kernel epsilon-machines and HSE-PSRs exist but
  are output-only or not intervention-aware; no known consistency/rate results for "microstate -> input-conditioned
  future law" partitions in high N (N ~ 100-5000).
- Choice of the test bank: equivalence is relative to T; no theory for which finite probe set suffices for continuous
  nonlinear systems (the L* analogue of a characterising suffix set), nor for when interventional equivalence on T
  implies equivalence on unseen intervention types.
- Deterministic chaos and sensitive dependence: exact predictive equivalence classes are singletons; only horizon- and
  tolerance-indexed approximate equivalences are meaningful, and how to choose (epsilon, H) jointly is unresolved.
- Termination/completeness of CEGAR-style refinement for continuous systems and for learned (neural) abstractions: no
  guarantees; adversarial oracles give no PAC bound.
- Principled abstention thresholds: I_pred divergence and k-growth are asymptotic notions; finite-data tests that
  distinguish "large but finite" from "non-compact" state are lacking.
- Sharing one f across implementations (prop 7) is absent from this literature (bisimulation between different systems
  is defined, e.g. approximate bisimulation between two systems, but learning a shared quotient from two simulators is
  not treated in what I read).

---

## Appendix D. Area synthesis notes: Neural state-space and continuous-time latent models

#### General verdict for this area
No method here gives identifiability, minimality or interventional sufficiency. They are **flexible function-class
containers** for f, phi and g. Their value for the tournament is (a) a training-objective toolbox (multi-horizon rollouts,
KL with free bits, partial teacher forcing, latent self-prediction with stop-gradient) and (b) strong predictive baselines.
Properties (2)-(5) must come from the *protocol*: encode from x(t) only, roll out open-loop, sweep k, and test with
interventions. The common architectural trap is a hidden history channel (the RSSM deterministic h, VRNN autoregressive
feedback, CPC/ODE-RNN context, a sequence-model decoder, a smoothing posterior). Any of these makes a small nominal k look
sufficient while the real state is large.

#### Tournament candidate A: closed latent dynamics with a multi-horizon objective ("encode once, roll out")
- **Data from the simulator:** many short windows (T = 64-256 steps at the model dt) starting from diverse initial states:
  on-attractor samples, off-attractor states (random perturbations of sampled states), and several parameter draws.
  u(t) is a mixture of band-limited noise, steps and pulses at several amplitudes. Keep a held-out set of input *families*,
  not just held-out seeds.
- **Model:** phi is an MLP N -> 512 -> 256 -> k with LayerNorm, or a linear map N -> 64 followed by an MLP for N ~ 5000.
  f is a residual (Euler or RK4) step z' = z + dt * MLP([z, u]) (2 x 128-256, SiLU), or a latent neural ODE / CDE with
  X = (u) (no absolute time channel). g is an MLP([z, u]) -> y, plus an optional linear/MLP decoder z -> x with a small weight
  (it helps against collapse). An optional stochastic version adds a Gaussian transition noise head (variational SSM). No
  deterministic side-channel h is allowed; if one is used, it counts towards k.
- **Loss:** sum over horizons h in {1, 2, 4, 8, 16, 32, 64} of w_h * [ NLL/MSE(y_{t+h} | g(f^h(phi(x_t), u), u_{t+h}))
  + lambda_lat * || f^h(phi(x_t), u) - sg(phi(x_{t+h})) ||^2 / Var(z) ] + lambda_x * reconstruction of x_{t+h}. Use
  w_h roughly equal, or normalised by per-horizon baseline error. Anti-collapse: a per-dimension variance floor
  (VICReg-style) or the decoder term. For the variational version, KL(q || p) with **free bits (~1 nat per dimension or per
  step)** and DreamerV3-style balancing (dynamics KL weight 1 or 0.5 to the prior, 0.1 to the posterior; sg on the opposite side).
- **Chaotic regimes:** use GTF-style partial forcing during training, z~_t = (1 - alpha) f(z_{t-1}, u) + alpha phi(x_t),
  annealing alpha from 1 toward ~0.1-0.3 (aGTF). Alternatively use multiple shooting: forced resets every tau ~ ln2 / lambda_max
  steps. Evaluate free-running with D_stsp and D_H in addition to n-step MSE.
- **k sweep:** k in {1, 2, 3, 4, 6, 8, 12, 16, 24, 32} with 3-5 seeds each. Pick the smallest k whose held-out multi-horizon
  error is within a tolerance (e.g. 1 SE) of the plateau set by a full-state predictor. Report the whole curve.
- **Inputs and interventions:** u(t) enters f (concatenated, or affinely z' = z + dt(F(z) + B(z)u) as in E2C, which also allows
  local controllability analysis). **State-offset interventions:** apply the offset to x, re-encode z = phi(x + delta), and roll
  out. No special handling is needed, and this is the cleanest test of (3) and (4). **Input currents to units:** feed as
  additional input channels via a learned linear map from the N-dimensional current vector to a small input code,
  u_int = P * I(t) (P shared, so unseen target sets can still be expressed). **Structural interventions (removing units or
  connections)** change f itself. Condition f on a descriptor, or treat this as the open problem it is (below).

#### Tournament candidate B: variational / stochastic closed SSM (RSSM without h, or latent SDE)
Same as A, but with a Gaussian stochastic latent and a learned diffusion or transition noise. Use it to separate "unexplained
state" from intrinsic noise, and for abstention (8). If the learned noise does not fall as k increases and the multi-horizon
NLL plateaus far above a full-state model, abstain. Watch for diffusion absorbing model error: compare against a deterministic
model's residuals.

#### Tournament candidate C: interpretable switching / piecewise-linear latent (rSLDS or shPLRNN)
Small k (2-10) and K modes (2-10), or hidden units L. These give analytic fixed points and regimes, affine identifiability
(rSLDS) that helps (6) and (7), and the PLRNN + GTF recipe for chaotic regimes. Fit rSLDS with the ssm package on
encoded/PCA-reduced x. shPLRNN is easy to write from scratch. Avoid vendoring the GPL-3.0 code unless licence-compatible.

#### Baselines from this area and how to implement each well
- **RSSM (Dreamer-style):** GRU h of 128-256 units, Gaussian s of dimension k (not 32x32 categoricals, so that k is interpretable),
  actions = [u, intervention code]. Free bits 1 nat, KL balance 0.8 (V2) or dynamics/representation weights 1/0.1 (V3),
  symlog on y if scales vary. **Report two numbers:** k_nominal = dim(s) and k_effective = dim(h) + dim(s). For the fair
  closed-state comparison, initialise from phi(x(t0)) and not from a filtered history. Take the 30-step warm-up ("burn-in")
  that world models use as a separate, *history-based* baseline.
- **Variational SSM (DKF/DMM):** Pyro DMM structure, but at evaluation use a filtering (causal) or single-frame encoder, not
  the backward-RNN smoother. Use linear KL annealing over the first ~10-20% of training. Clamp the log-variance.
- **Latent neural ODE:** encoder phi(x(t0)) only (not ODE-RNN over the window). Use a fixed-step RK4 at dt_model with
  discretise-then-optimise (direct backprop). Reserve the adjoint for long windows. Hold u piecewise constant within steps.
  Add small Jacobian or kinetic regularisation if NFE grows (unverified recipe). Libraries: diffrax (Apache-2.0) or torchdiffeq
  (MIT). torchsde is archived, so prefer diffrax for SDEs.
- **Sequence model with bottleneck:** S5 / LRU / GRU / transformer decoder that receives only (z = phi(x(t0)) in R^k,
  u_{t0:t0+H}) and outputs y over the horizon. Sweep k identically to the others. Pair it with (i) a "no-z" version (input-only
  baseline) and (ii) a "history" version (sees y or x history, upper bound). Remember that this tests (1) and (5), not closure.
- **AE + linear latent dynamics (E2C/KVAE-style, overlaps Koopman area):** MLP encoder, z_{t+1} = A z_t + B u_t (A initialised
  near identity, spectral radius penalty or eigenvalue parameterisation as in LRU), MLP decoder to y and x, multi-horizon loss.
  A locally linear variant (A(z), B(z) from a network, rank-1 corrections as in E2C) is a cheap nonlinear step up.
- **Upper and lower reference predictors:** a full-state predictor (the same f with k = N or with phi = identity after PCA to
  ~95-99% variance); input-only (z fixed or zero); readout-history-only (GRU on past y and u); random projection phi (a random
  linear N -> k map, trained f and g).

#### Evaluation measures for properties (1)-(8) from this area
- (1) Multi-horizon NLL/MSE of y (and of x if decoded) vs horizon h, relative to full-state and input-only baselines. For chaotic
  regimes, add D_stsp (KL of state-space occupancy, binning in low dimension, GMM in high dimension) and D_H (Hellinger
  distance of smoothed power spectra) computed on free-running rollouts. Optionally add an InfoNCE critic estimate of
  I(z_t; y_{t:t+H}) vs I(x_t; y_{t:t+H}).
- (2) **Closure gap:** error of an open-loop rollout f^h(phi(x_t)) vs the one-step-refreshed rollout f(phi(x_{t+h-1})). Also a
  **semigroup check:** || f^{a+b}(phi(x_t)) - f^b(phi(x_{t+a})) || in latent space, with C-SWM-style ranking of predicted
  latents against encodings of true futures (Hits@1, MRR). Compare the closed model against the same model given a GRU history
  channel. If history helps significantly at equal k, z is not Markov.
- (3) Held-out intervention types: re-encode after state offsets and roll out. For input-type interventions, use held-out
  target sets and amplitudes. Report error relative to the full-state model under the same interventions.
- (4) For pairs x, x' with ||phi(x) - phi(x')|| small (near neighbours, or x' constructed by optimising along phi's null
  directions), simulate both and measure future divergence of y and x relative to random pairs.
- (5) The k-sweep plateau (see above), plus per-dimension variance and effective rank of z to detect collapsed or unused
  dimensions. Latent-ODE/ANODE logic applies: if a k-dimensional autonomous flow cannot fit trajectories that cross in
  z-space, k is too small.
- (6) Latent alignment across seeds up to the allowed class (affine for rSLDS/linear models, general diffeomorphism via
  CCA/Procrustes/CKA or cross-predictive fits from other areas). Compare f across seeds via conjugacy (fixed points, Jacobian
  eigenvalues, D_stsp between rollouts).
- (8) Residual noise level of stochastic models (SDE diffusion, transition noise) vs k, and the gap to full-state
  performance that does not close with k.

#### Known pitfalls specific to this area
- **Future leakage:** backward-RNN smoothers (DKF, SRNN), latent-ODE window encoders and natural cubic splines in neural CDEs
  all use future data. Evaluation encoders must be causal and preferably single-time.
- **History leakage / dimension cheating:** RSSM h, VRNN autoregressive x feedback, CPC context, KVAE mixture LSTM, and
  sequence-model decoders all carry hidden state. Count all carried state in k, or remove it.
- **Output copying:** feeding past y into f or g (or letting x contain y trivially) gives excellent short-horizon scores.
  Compare against the readout-history-only baseline.
- **Input copying:** g(z, u) can predict input-locked parts of y from u alone. Always report the input-only baseline and the
  gain over it.
- **Time leakage:** absolute time channels (required in CDEs) or time-since-trial-start features. Use time increments only,
  and randomise window start times.
- **Parameter-identity leakage:** with multiple parameter draws, phi can encode the draw ID in a latent dimension. Test on
  held-out draws and check whether a probe can decode the draw ID from z.
- **Pathological encodings:** a continuous low-dimensional z can encode arbitrarily much information with a high-Lipschitz
  phi (space-filling curves). Countermeasures: noise injection in z during training (the variational KL does this),
  Lipschitz/spectral-norm limits on phi and f, and evaluating robustness of predictions to small z perturbations.
- **Collapse:** latent self-prediction without a decoder or anti-collapse term. KL posterior collapse in variational models.
  Monitor per-dimension variance.
- **Chaotic training:** exploding gradients for long BPTT windows are a theorem for chaotic RNNs, not a bug. Use STF/GTF
  or multiple shooting. Plain gradient clipping was reported insufficient.
- **Solver issues:** stiffness (NFE blow-up) and adjoint back-integration errors in dissipative or chaotic latents. Prefer a
  fixed-step discretise-then-optimise approach for short windows.

#### Open problems (no good answer in the literature read)
- Predicting effects of **structural** interventions (removing units or connections) with a fixed low-dimensional f. All
  methods here assume f is fixed. A descriptor-conditioned f(z, u, d) has no guarantees for unseen d.
- Principled **minimal k** for neural latent models. Existing practice is plateau heuristics. KL and free-bits penalties do
  not produce a consistent estimator of the state dimension.
- A **shared f across implementations** (7) with implementation-specific encoders. It is plausible as multi-encoder training
  with one f, but I found no primary source in this area that establishes identifiability or consistency for it.
- **Abstention (8):** no method in this area provides a calibrated test that "no compact closed state exists". Residual-noise
  and closure-gap heuristics need calibration against simulated positive and negative controls.
- Closure testing when the true system is chaotic: finite-horizon errors saturate, so D_stsp/D_H-type distributional measures
  are necessary. How to combine them with interventional tests is not established.

---

## Appendix E. Area synthesis notes: Causal representation learning, identifiability, invariance and causal abstraction

#### Tournament candidates from this area

**T1. Interventional identifiable sequential VAE (LEAP/TDRL-style prior, BISCUIT-style unknown-target regimes).**
- Data:
  - Many simulator episodes with random initial states, random input sequences u (band-limited noise plus steps) and random
    parameter draws.
  - In a fraction of episodes (e.g. 30-50%), apply one micro intervention per window from a *training* set of intervention
    families: state offsets on random unit subsets, input currents, unit removal. Keep held-out families and targets aside.
  - Record the intervention descriptor a_t: family, target mask and magnitude.
- Model: encoder phi(x_t), not windowed; add a history variant only as an ablation. Latent transition
  z_{t+1} = f(z_t, u_t, m_t) + eps with conditionally independent innovations. m_t is a *learned* binary or soft mask
  predicted from a_t, as in BISCUIT, saying which latent mechanisms the intervention touches. Readout y = g(z, u).
- Loss: ELBO on x with a flow prior, plus multi-step prediction loss on y and on phi(x_{t+h}) (h in {1,5,20,100}·dt), plus a
  sparsity penalty on m.
- Sweep: k in {1..12}, lag L in {1,2}, sparsity weight, and the fraction of intervened episodes.
- Choose k at the smallest value at which held-out-intervention multi-horizon error plateaus (within 1 SE), cross-checked with
  the across-seed identifiability score below.
- Why: the only family here with identifiability theory that matches "known micro action, unknown macro target", together
  with a Markov transition.

**T2. Interchange-intervention-trained abstraction (IIT/DAS adapted to dynamics).**
- Learn phi (start linear: z = W x, W of shape k x N, with DAS-style orthogonal parametrisation), f and g jointly.
- Loss = multi-step prediction loss + **interchange loss**:
  - Sample a base microstate x_b and a source x_s, and a coordinate subset S of z.
  - Construct the micro realiser x* = x_b + W^+ P_S W (x_s - x_b), a minimum-norm state offset (the simulator supports state
    offsets). Run the simulator for H steps under the same u.
  - Penalise || phi(x*(t+h)) - f^h(z*) ||^2 and || y*(t+h) - g(f^h(z*)) ||^2, where z* = swap_S(z_b, z_s).
  - Also add **null-space faithfulness** pairs: x_b + (I - W^+W) delta should leave y and phi(future) unchanged.
- Sweep: k, H in {1..50}, and the null-space loss weight.
- For a nonlinear phi, compute realisers with a Gauss-Newton projection: min ||x - x_b|| subject to phi(x) = z*.
- Why: this directly optimises (3) and (4) with the simulator in the loop. It needs simulator calls during training, so batch
  and cache them.

**T3. Multi-view contrastive shared-state learning for (7) (content-style / multi-view identifiability + CEBRA multi-session).**
- Run M different implementations (different N, connectivity, parameter draws) on identical u sequences.
- Implementation-specific encoders phi_m; InfoNCE where positives are (phi_a(x^a_t), phi_b(x^b_t)) on the same u at the same
  t, plus time-offset positives within an implementation.
- A shared f and g are trained on top with a prediction loss.
- Use L1 or Lp similarity (p != 2) if axis alignment is wanted (Zimmermann Thm 6); cosine gives orthogonal ambiguity.
- Sweep: k, temperature, and the time offset.
- Why: block identifiability of the shared content is the only theory here that addresses "same computation, different
  implementation". Guard against input copying: positives defined by equal u reward encoding u itself, so also include pairs
  with equal u but different initial states. Content must then reflect the internal state, not just u.

**T4. CFL-style refinement (observational partition, then interventional merge/split).**
- Start from any predictive encoder (e.g. from another area).
- For clusters or grid cells in z, sample several micro realisers from the pool (states with nearly equal z). Apply the same
  intervention and compare futures.
- Split z-cells whose realisers diverge, increasing k or refining f. Merge cells whose interventional futures agree.
- This is counterexample-guided refinement grounded in the Causal Coarsening Theorem, and a natural mechanism for (8):
  abstain when refinement does not converge below a threshold at small k.

#### Baselines from this area and how to implement them well
- **Time-contrastive encoder (TCL/PCL/CEBRA-time) + separately fitted f (linear or MLP) and g.** Use offset-1 (no window)
  encoders so that phi is instantaneous. Normalise x per unit using *training* statistics only. Choose the negatives from
  other episodes as well as the same episode, to avoid learning episode identity (parameter-identity leakage).
- **iVAE with auxiliary u = intervention family / episode regime.** Watch for posterior collapse; use KL warm-up. Report
  identifiability through MCC (mean correlation coefficient after optimal permutation) across seeds.
- **SlowVAE**, as a prior-choice ablation.
- **IRMv1 penalty added to an AE + dynamics model.** Include only as a weak baseline showing that invariance penalties do
  not buy (3).
- **Macro causal-discovery baseline**: PCMCI (tigramite, ParCorr then GPDC/CMI) on the learned z plus u. It checks the
  macro graph and closure. Use the ParCorr test first; deterministic systems need added observation noise or they violate
  faithfulness.

#### Evaluation measures (properties 1-8) and a concrete interchange-intervention / abstraction-error recipe

Notation: micro simulator Sim_h(x, u_{t:t+h}, mu) returns x(t+h) after micro intervention mu. The macro model is (phi, f, g).
D is a distance. Because z is identifiable only up to a transformation, **compute D on gauge-invariant quantities**:
- the readout y, which is observable;
- z after an optimal transformation of the class the method claims (orthogonal or affine) fitted on *training* data only;
- the encoder's own lift phi(Sim(...)) compared with f's prediction, which is self-consistent and gauge-free.

**Recipe A: bottom-up abstraction error (CAE-up) for (3).**
1. Split intervention families into train, held-out-target (same family, new units) and held-out-type (new family, e.g.
   lesions if training used offsets and currents).
2. Define omega, the map from micro to macro interventions. For state offsets and clamps: omega(mu) = do(z := phi(mu(x))),
   an instantaneous jump in z. For input currents: either (a) a macro input channel learned by an intervention-effect
   encoder e(mu) that enters f as an extra input, trained only on training families; or (b) treat the current as a
   perturbation of x integrated through Sim for one dt and then encoded. For removals and lesions (structural changes): a
   macro counterpart exists only if f has a structural parameter slot. Otherwise **declare them outside the abstraction's
   intervention set and report them separately** (validity is relative to an intervention set; Beckers & Halpern).
3. For each sampled (x0 from held-out initial states, u from held-out input sequences, mu), compute:
   err_h = D( y_micro(t+h), g(f^h(omega(mu)(phi(x0))), u) ) and err_z_h = D( phi(x_micro(t+h)), f^h(...) ).
   Use h on a log grid up to the longest horizon of interest.
4. Normalise by the error of trivial predictors: the no-intervention macro prediction (does the model capture the
   intervention *effect* at all?), mean-effect-per-family, and a full-state predictor. Report the **effect-normalised
   error** = err / D(y_intervened, y_unintervened). This removes credit for predicting the unperturbed trajectory.
5. Use at least 30 interventions per family (the CAE paper reports 95% power at ≈ 30 for most systems). Prefer 100+ with
   bootstrap CIs over x0 and u.

**Recipe B: top-down interchange interventions (IIA-style, continuous) for (3) and (4).**
1. Sample base x_b and source x_s, and a subset S of z coordinates. Target z* = z_b with z*_S := z_s,S.
2. Realise z* in the micro system with **R ≥ 3 different realisers**:
   - (i) minimum-norm offset x_b + J^+ (z* - z_b), iterated Gauss-Newton for nonlinear phi;
   - (ii) nearest pool state with phi(x) ≈ z* (from a large simulated bank, tolerance epsilon);
   - (iii) a random null-space-perturbed realiser: (i) plus a random component in ker J.
3. Run Sim forward under the same u. Record y and phi of the future.
4. **Interchange error** = D(y_micro(realiser r), g(f^h(z*))). Report its mean over r (the (3)-type score) and its **spread
   across realisers** (the (4) microstate-invariance score; it should be ≈ 0).
5. For discrete readouts, IIA = the fraction of matches. For continuous readouts, use R^2 of predicted vs realised
   counterfactual y, pooled over pairs.
6. **Faithfulness / unmapped-variable test** (the CAE failure-mode detector): intervene only in the null space of phi
   (for the nonlinear case, perturb x and then project back to the same z). Measure ||Delta y|| and ||Delta phi(future)||
   relative to a range-space perturbation of equal norm. The ratio should be ≈ 0. A large ratio means hidden variables that
   z misses (hidden-confounder or backup-path failures).
7. Check **unreachable macro states**: when realiser (i) fails to converge or produces out-of-distribution x (e.g. activity
   outside the simulator's typical range, Mahalanobis distance to the state bank), count z* as unrealisable. Report the
   fraction; the macro model claims validity only on the realisable set.

**Recipe C: cross-implementation interchange for (7).**
Take the source from implementation A and the base from implementation B: z* = phi_B(x_b) with S-coordinates from
phi_A(x_s), after the shared-gauge alignment learned on training data. Realise in B, run B, and compare with the shared f.
Also require **swap symmetry**: A-to-B and B-to-A errors comparable. A shared f that works only in one direction indicates
implementation-specific leakage into z.

**Other measures.**
- (2) Markov closure: invariant residual test (nonlinear ICP style) of z_{t+1} - f(z_t,u_t) across contexts, including
  intervention regimes and history bins. Add a PCMCI/partial-correlation test of residuals against lagged z, lagged y and
  random micro projections.
- (6) Seed and procedure stability: MCC (permutation + elementwise claims), linear/affine R^2 (CEBRA consistency; for
  affine or linear claims), orthogonal Procrustes (isometry claims). Always compare in the class the method claims; a
  looser class hides instability, a tighter one penalises legitimate gauge freedom.
- (8) Abstention: a stated threshold on the effect-normalised abstraction error and the realiser-spread at the chosen k. If
  no k ≤ k_max meets it, abstain. Calibrate the thresholds on simulators with known compact states and with known
  non-compressible dynamics (e.g. high-dimensional chaotic or random-coupling regimes).

**Pitfalls specific to this area.**
- IIA on outputs only is not certification. Intermediate or long-horizon z can be wrong (Méloux et al.). Always add
  faithfulness and null-space tests.
- **Input copying**: contrastive or auxiliary-label methods (CEBRA hypothesis mode, iVAE with u = input) can make z encode u.
  Test with equal-u / different-x0 pairs.
- **Parameter-identity leakage**: episode-level negatives let the encoder memorise parameter draws. Use held-out parameter
  draws for all evaluation. Make sure the intervention-effect encoder e(mu) does not see episode id.
- **Realiser leakage**: minimum-norm realisers can push x off the natural manifold. The model may pass on off-manifold
  states for the wrong reasons, or fail for them. Report on-manifold (pool) realisers separately.
- **Dimension cheating**: an injective but pathological phi (e.g. space-filling encodings of many micro variables into one
  coordinate) makes k look small. Countermeasures: Lipschitz or smoothness constraints on phi and f; a noise-robustness test
  (small Gaussian noise on z should give graded rather than catastrophic prediction error); report effective dimension via
  an eps-sensitivity curve.
- Identifiability theorems are asymptotic and assumption-bound (independent innovations, invertible mixing, single-node
  interventions). None covers our "micro intervention with unknown multi-node macro effect in continuous dynamics" setting
  exactly.

#### Open problems (no good answer in the literature read)
1. Identifiability of a **Markov latent dynamical system** from micro interventions whose macro effects are multi-node,
   graded and target-unknown. BISCUIT (binary), Buchholz (Gaussian linear latent, i.i.d.) and von Kugelgen (perfect) each
   cover only part.
2. How to define omega (the micro-to-macro intervention map) for **structural interventions** such as unit or connection
   removal, and whether a single f can represent them without a separate parametrisation.
3. Choosing the realiser distribution for top-down interchange tests in continuous systems. The CAE paper samples
   macro-intervention values uniformly on the ranges of the macro variables and grounds them via tau^{-1}; there is no
   principled choice for continuous micro-to-macro maps with large fibres.
4. Formal abstraction error for **continuous-time, continuous-state stochastic** systems with a horizon-dependent metric.
   Most formal work (Rischel & Weichwald; Otsuka & Saigo) is for finite or discrete models.
5. A theory for "one shared f across implementations" beyond block identifiability of shared content. Nothing guarantees the
   *dynamics*, rather than just the state, are shared.
6. A principled abstention criterion (8). No reviewed work gives calibrated tests for "no compact abstraction exists". The
   CFL "partition does not coarsen" idea and error thresholds are heuristics.
7. Robust and practical estimators for the nonparametric interventional identifiability results. Most are theory with
   small-scale demonstrations.

---

## Appendix F. Area synthesis notes: Population-dynamics latent models and comparing latent spaces

#### Tournament candidates from this area
1. **Low-rank RNN fit on simulator data (LINT-style, optionally stochastic/SMC).** Data: many simulator rollouts with random
   initial states (not only on-attractor), random piecewise-constant u(t) and random microscopic interventions (state kicks,
   input currents into random units, a held-out set of intervention types). Objective: multi-horizon MSE (or Poisson NLL) of
   all unit activities and y(t) under open-loop rollout from the true initial state. Sweep rank R = 1..10, nonlinearity,
   noise level. k = R (+ input dims): choose smallest R at which held-out multi-horizon and held-out-intervention prediction
   plateau. phi = projection onto span(M) (least squares), f = reduced latent ODE. Why: it lives in unit space, so interventions
   are native (prop 3), and rank is a clean minimality knob (5). Caveat: assumes near-low-rank microscopic structure.
2. **Sequential VAE with explicit inputs (LFADS generator with known u, causal encoder; or iLQR-VAE).** Use a causal (forward)
   encoder only, feed simulator u(t) as known input, disable or strongly penalise inferred inputs (they otherwise absorb
   unmodelled dynamics and leak future). Coordinated dropout on inputs. For (7): implementation-specific linear read-in/read-out
   with a shared generator (lfads-torch multi-session scheme). Sweep factor dim and generator size; choose k by the factor
   dimension at which held-out prediction plateaus. Licence of lfads-torch is non-commercial research; consider reimplementation.
3. **Latent LDS/fLDS with inputs as the interpretable linear-dynamics member** (dynamax / ssm): EM with known B u_t; fLDS
   variant with neural-network emission for nonlinear embeddings.

#### Baselines from this area and how to implement well
- **GPFA / FA + smoothing:** fit on square-root or z-scored activity; select q by leave-unit-out cross-validated prediction;
  orthonormalise for display only. No transition law, so pair with a fitted linear AR on the latents for forecasting.
- **PCA + linear dynamics / latent LDS:** Kalman-smoothed EM with inputs; regularise A (ridge) and check spectral radius;
  compare with RRR from past x/u to future x (a direct linear predictive-state baseline).
- **Trained-RNN + fixed-point skeleton:** fit a vanilla GRU to the data, run FixedPointFinder per input level, and use the
  number/type of fixed points and Jacobian spectra as a comparison target for every other model.
- **Denoising transformer (NDT) as an upper bound on smoothing quality** (not a state model).
- **Random-projection and PCA encoders at the same k** as nulls for every similarity measure below.

#### Recommended measures for comparing latent spaces up to transformations (props 6 and 7)
Use a battery, because each measure has a different invariance class and blind spot:
1. **Geometry, adjustable invariance, proper metric:** netrep generalized shape metric with cross-validated alignment; report
   alpha=1 (rotation) and alpha=0.5 or 0 (towards linear). If latents are only identifiable up to invertible linear maps, a
   linear-invariant measure is the principled one, but only when k << number of samples; with small k (<10) and long
   rollouts this holds. Add regularised CCA (fit on train, evaluate on held-out time points).
2. **Predictive/functional alignment (best single measure for the contract):** fit a linear (then small MLP) map z_A -> z_B on
   train rollouts and evaluate held-out R^2 in both directions; and, stronger, check that f_A conjugated by the map predicts
   z_B's future (cross-rollout of dynamics). This tests (7)'s "one shared f".
3. **Dynamics-level:** DSA / InputDSA (because u(t) matters here) on latent trajectories; Koopman-spectrum comparison as a cheap
   conjugacy necessary condition; DFORM/CSA as a stronger nonlinear-conjugacy check where affordable; fixed-point counts and
   Jacobian spectra per input level.
4. **Subspace stability in unit space (6):** principal angles between phi's row spaces across seeds/estimators on the same simulator.
5. **Debiased CKA** only as a secondary sanity check with random-network / time-shuffled nulls.
Calibrate every measure with: (i) same model, different seeds; (ii) same model, different data subsets; (iii) random rotation /
random invertible linear map / random diffeomorphism of the same latent (should score as identical under the claimed invariance);
(iv) a deliberately different f (should score different). Report the between/within ratio, not raw scores.

#### Known pitfalls
- **CKA:** biased estimator inflates similarity when p >> n; dominated by high-variance directions; manipulable without
  functional change; sensitive to outliers. Use debiased HSIC and nulls.
- **CCA:** saturates (all correlations ~1) when k or p approaches sample count and when time-autocorrelated samples reduce the
  effective n; always evaluate on held-out time/rollouts; SVCCA threshold arbitrary; mean CCA weights noise directions equally (PWCCA).
- **Geometry vs dynamics:** identical state clouds can arise from different flows and vice versa; shape metrics, CKA, RSA and
  principal angles are all blind to f. Always pair a geometric measure with a dynamics-level one.
- **DSA-specific:** orthogonal alignment is neither necessary nor sufficient for conjugacy (Godara et al. 2026); hyperparameters
  (delays, rank, dt) change scores; autonomous DSA confounds different input drive with different dynamics (use InputDSA).
- **Time leakage / future leakage:** bidirectional encoders (LFADS, NDT, GPFA smoothing) use future observations; states from
  them are not filtering states. For props (1)(2) use causal encoders or evaluate with filtering-only inference.
- **Input copying:** inferred inputs (LFADS controller) or unconstrained B can copy u(t) into z and make z look predictive;
  compare against an input-only predictor.
- **Output copying / identity:** without coordinated dropout, autoencoders copy observations; for similarity, two models that
  both copy y look similar trivially. Include readout-history-only baselines and mask y in similarity computations.
- **Parameter-identity leakage:** if simulator parameter draws differ across rollouts, latents may encode the draw ID; similarity
  across implementations may then reflect shared draw labels. Split train/test by parameter draw.
- **Dimension estimates:** linear dimension overestimates nonlinear intrinsic dimension; noise and small samples inflate
  estimates; temporally correlated samples bias kNN estimators; state-cloud dimension is not closed-state dimension.
- **Dimension cheating:** a 1-D latent can encode anything via a space-filling / highly nonlinear encoding; similarity measures
  with nonlinear alignment (DFORM, MLP maps) will then happily align it. Constrain encoder smoothness (Lipschitz) and check
  that the linear-alignment score is not far below the nonlinear one.

#### Open problems
- No standard, statistically calibrated test of topological conjugacy between learned systems from finite, noisy, input-driven
  data; DSA/CSA/DFORM/Koopman-spectrum approaches give different answers and none has null distributions established.
- Invariance-class mismatch: the contract says latents are identifiable "up to transformations" but which class (linear,
  diffeomorphic, conjugacy of f) is not specified by any of these methods; the chosen similarity metric implicitly decides it.
- Separating intrinsic dynamics from input drive (LFADS inferred inputs, iLQR-VAE, InputDSA surrogate inputs) is unidentifiable
  without priors; how to use designed simulator interventions to resolve this is largely unexplored in this literature.
- Dimension estimation is unreliable above ~20 dims and under noise; there is no accepted method for the dimension of a closed,
  interventionally sufficient state (as opposed to a state-cloud dimension).
- Low-rank RNN inference assumes low-rank microscopic structure; how it degrades when the simulator is full-rank but still has
  a compact state (e.g. via nonlinearity) is not characterised.
- Abstention (8): none of these methods outputs "no compact state"; the closest signals are the absence of a prediction plateau
  vs k and the absence of slow manifolds in fixed-point analysis.

---

## Appendix G. Area synthesis notes: Experiment design, canonical dynamical coordinates and evaluation of learned dynamics

#### A. What a simulator changes
Most methods in this area were developed for settings where experiments are expensive and data passive. Here we can reset
x to any microstate, inject any u, apply exact impulsive offsets to any unit, remove units/edges, and redraw parameters.
Consequences:
1. **Direct measurement replaces estimation** for many reference quantities: vector PRCs and isostable response curves by
   pulse perturbation, empirical controllability/observability/cross gramians by +/- impulses, Jacobians at fixed/slow
   points, Floquet multipliers via Poincare maps of perturbed runs, bifurcation diagrams by continuation or brute-force
   sweeps. These become **ground-truth probes** for evaluating a learned (phi, f, g) that was never trained on them.
2. **Experiment design mainly becomes budget allocation**, plus targeted counterexample search (BOED/active learning)
   at the refinement stage. Fisher/PE theory gives *lower bounds* on richness (input dimension, order of excitation,
   horizon).
3. **Reachability is not a constraint** (unlike Buisson-Fenet et al.), but the *distribution* over microstates is a design
   choice that can create leakage or irrelevance (see pitfalls).

#### B. Tournament candidates from this area
1. **Canonical-coordinate reduction near attractors (phase + isostables / SSM normal form).**
   Recipe: for each parameter draw, find attractors (fixed points via FixedPointFinder-style q-minimisation on the
   simulator vector field; cycles via Poincare sections). For fixed points: SSMLearn-style fit on relaxation trajectories
   from 200-1,000 perturbed initial states (offsets drawn in the span of random unit directions at 3 amplitudes), with
   polynomial order 3-7 and SSM dimension 2-6 swept, k chosen at the Koopman/Floquet spectral gap. For cycles: phase +
   m slowest isostables, with response curves by direct pulses. Objective: invariance error + reduced-dynamics regression.
   Good for (1), (2), (5), and a gauge-fixed reference. Weakness: local, one attractor at a time, and it abstains outside basins
   (which is a feature for (8)).
2. **Empirical-gramian balanced reduction (nonlinear balanced truncation) as a learner.**
   Recipe: empirical controllability gramian from impulses into each unit and each external input channel, observability
   gramian from +/- state offsets observed through y (or through future y over horizon H), 2-4 perturbation scales, averaged over
   operating points. phi(x) = top-k balanced coordinates (linear encoder), f fitted by a small MLP or polynomial (SINDy)
   on those coordinates. Sweep k by the HSV curve. Linear phi makes it a strong, interpretable, hard-to-cheat candidate.
3. **Active counterexample-guided refinement (BOED/ensemble-disagreement loop) wrapped around any learner.**
   Recipe: train an ensemble of 5 (phi, f, g). Repeat rounds: propose candidate experiments (x0 from the visited
   distribution, intervention type/target/amplitude/timing), score them by (a) ensemble disagreement on future y (EIG
   proxy) and (b) *microstate-invariance violation*: sample pairs x, x' with |phi(x) - phi(x')| < delta but large
   predicted/true future divergence. Simulate the top 5-10% and add them to training. Stop when violation rates plateau. Use DAD-like
   amortisation only if rounds are many. Budget: 10-20% of total simulation.

#### C. Simulation-budget / data-generation protocol (concrete)
Let B be the total number of simulated trajectory-seconds (or trajectories of length T). Factors: parameter draw p
(network weights/biases/noise seeds), initial condition x0, input sequence u, intervention (type tau, target set S,
amplitude a, time t0), implementation (for property 7).

**Factor design**
- Parameter draws: P_train = 64-256, P_val = 16, P_test = 32 (disjoint draws; for (7) also disjoint *implementations*
  of the same computation).
- Initial conditions per draw: 3 sources, (i) on-attractor (burn-in >= 10 slowest time constants from random x0),
  (ii) near-attractor (on-attractor state + offsets at 3 amplitudes, relative to per-unit std), (iii) far (random x0 from a
  broad distribution; only 10% of the budget). Record the source; report metrics per source.
- Inputs: a mix of (a) band-limited random multisines / filtered noise at 3 amplitude levels (these give PE of adequate
  order; check the rank of the block-Hankel matrix of u for the chosen window L), (b) steps and pulses, (c) chirps, (d) zero input.
  Keep the u-generator family as a factor so it can be held out.
- Interventions (types): tau in {state offset on a unit set, injected current (constant / pulse / sinusoid) into a unit
  set, unit removal (silencing), connection removal (single edge, fan-in/out set), global parameter shift}.
  Targets S: single units, random sets of size {2, 5, 10%}, structured sets (e.g. top-k by empirical-controllability
  score, and bottom-k). Amplitudes: 3 levels spanning linear -> clearly nonlinear response (calibrate per draw so that
  the smallest gives < 5% change in y and the largest > 30%). Timing t0 relative to phase for oscillatory regimes (8-16
  phases).

**Allocation (fraction of B)**
- 35% observational/input-driven trajectories (no interventions) across P_train x ICs x u-families.
- 25% training interventions: all tau except the held-out types, on training targets only.
- 10% probe measurements (not training data for the learner): direct PRCs/isostable response curves (N_probe units x
  8-16 phases x 2 signs), empirical gramians (2N runs per operating point on 4-8 operating points per draw), fixed/slow
  points, bifurcation sweeps of 1-2 constant-input/parameter axes.
- 10-20% active/counterexample rounds (section B.3).
- 15% held-out evaluation (generated once, frozen, never inspected during development), with an extra untouched
  "final" test set.

**Held-out splits (report each separately; never pool)**
1. *Within-distribution:* new ICs and new u draws, training p and training intervention types/targets.
2. *Held-out initial-condition source:* train on on/near-attractor, test on far ICs (or vice versa). Also held-out basins
   in multistable draws.
3. *Held-out targets:* same intervention type, unseen target units/sets (disjoint unit sets; for structured targets,
   hold out entire structural classes).
4. *Held-out intervention types:* e.g. train on offsets + currents, test on unit removal and edge removal (and the
   reverse fold). Leave-one-type-out cross-validation over tau.
5. *Held-out amplitudes:* train on low/mid, test on high (extrapolation into nonlinearity).
6. *Held-out input families:* train on multisines, test on chirps/steps.
7. *Held-out parameter draws:* disjoint p. For (7), held-out implementations with frozen f and only a new encoder
   trained on *observational* data of the new implementation, then tested on its interventions.
8. *Held-out bifurcation regime:* constant-input or parameter values beyond the training range (continuation-based
   test).
Split at the level of *whole trajectories and whole parameter draws*, never by time-window within a trajectory
(overlapping windows leak).

**Budget sizing heuristics**
- PE requirement: per operating regime and per excited input channel, windows L >= 2-3x the slowest relevant time
  constant; total samples >= (m + 1)(L + n_hat) with n_hat the empirical HSV-rank estimate.
- Stop adding observational data when the validation multi-horizon loss curve (log-log in data size) flattens. Then shift
  the budget to interventions and active rounds.
- Direct PRC: eps chosen by a linearity check (phase shift at eps and 2*eps agree within 5%).

#### D. Evaluation measures relevant to (1)-(8) from this area
- (1) Multi-horizon prediction in y (and in held-out probe observables) at horizons {1, 5, 25, 100} x dt plus multiples of
  the Lyapunov time or slowest time constant. Valid prediction time (first crossing of a normalised error threshold).
  For long horizons: D_stsp (GMM-KL in y-space or a fixed PCA of y), D_H (power spectra Hellinger), largest Lyapunov exponent
  and spectrum, attractor count/type per draw. Use dysts' `metrics.py` for consistent implementations.
- (2) Closure: compare the learned z-dynamics prediction with the "oracle" prediction from the full x. Report the ratio of their
  errors per horizon. Markov test: adding z-history to f should not improve prediction.
- (3) Interventional sufficiency: held-out-split errors (C.1-C.8) on post-intervention trajectories. Match of **vector PRCs /
  isostable response curves** (learned model perturbed in z via the Jacobian of phi, vs directly measured). **Bifurcation
  diagram match** under unseen constant inputs/parameters (bifurcation types and locations; number and stability of fixed
  points/cycles; Floquet multipliers). **Empirical-gramian principal angles** between the learned encoder's row space
  (for linear phi) and the simulator's dominant balanced subspace.
- (4) Microstate invariance: sample microstates on the same isochron / same SSM fibre (same asymptotic future by
  construction) and check phi collapses them. Conversely, sample pairs with equal phi and measure future divergence under
  identical interventions (active search as in B.3).
- (5) Minimality: learned k vs reference k from (i) HSV spectrum of the linearisation, (ii) Koopman/Floquet spectral gap
  (phase + slow isostables), (iii) SSM dimension, (iv) Hankel-rank plateaus. Also the rank of the Fisher information of the latent
  model under the training design (unidentified directions indicate excess k).
- (6) Stability: spread across seeds of invariant metrics (D_stsp, D_H, Lyapunov exponent, fixed-point counts, PRCs), and
  conjugacy/Procrustes alignment of latent spaces via canonical coordinates (phase, isostables are gauge-fixed).
- (7) Shared f: compare bifurcation diagrams, PRCs, Lyapunov spectra and normal-form coefficients across implementations.
  These are coordinate-free invariants.
- (8) Abstention: flag when the HSV/Koopman spectrum has no gap, when chaos yields a high Kaplan-Yorke dimension, or when
  held-out intervention errors fail to improve with k. The model should report "no compact state" rather than return a
  large-k fit.

#### E. Pitfalls specific to this area
- **Time leakage:** overlapping windows across train/test within one trajectory. Split by trajectory/draw.
- **Future leakage:** probe measurements (PRCs, gramians) computed on test draws and used for model selection.
- **Parameter-identity leakage:** ICs or input statistics that differ systematically per draw let the encoder memorise
  p. Randomise the IC/input generators identically across draws, and test on held-out draws.
- **Input/output copying:** short-horizon metrics reward copying y(t) or u(t). Always report the baselines "persist y",
  "input-only" and "readout-history-only".
- **Invariant-metric gaming:** a model that samples the right attractor distribution but in the wrong temporal order passes
  D_stsp. Pair it with D_H and short-horizon error. Multistability: compute metrics per basin.
- **Pathological encodings / dimension cheating:** space-filling or high-frequency phi can pack information into small k.
  Guard with Lipschitz constraints on phi, noise-robustness tests (small perturbations of x should move z smoothly,
  consistent with the measured gramians/PRCs), and the Fisher-rank check.
- **Perturbation-scale artefacts:** PRC/gramian estimates depend on eps. Always report linearity checks.
- **Far-from-attractor oversampling** by active learning: report metrics per IC source.

#### F. Open problems (literature gives no good answer)
- Canonical coordinates (isostables, SSMs, PRCs) are *local to one attractor*. There is no accepted global canonical latent
  coordinate system for multistable, input-driven, or chaotic regimes, or for transitions between attractors under
  interventions.
- No design theory for "maximally informative interventions for learning an *abstraction*" (information about phi and the
  equivalence classes of microstates) as opposed to parameters or graphs. BOED targets exist only as ad hoc
  proxies (ensemble disagreement, invariance-violation search).
- Persistency-of-excitation results are for LTI. No usable richness condition guarantees identifiability of a nonlinear
  latent state under a given intervention family.
- Evaluation of *interventional* long-horizon fidelity: invariant-measure metrics assume stationarity. For
  post-intervention transients there is no accepted analogue of D_stsp/D_H.
- Hold-out-type generalisation (e.g. training on currents, testing on unit removal) has no theory predicting when it should
  succeed. Structural interventions change the vector field itself, not only the input.
- Choosing perturbation scales and the microstate distribution (on-/near-/far-attractor) is a design choice with large
  effects on every metric. No principled standard exists.
