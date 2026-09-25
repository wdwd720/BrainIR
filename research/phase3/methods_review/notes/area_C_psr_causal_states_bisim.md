# Area C: Predictive-state and equivalence-class notions of state, state abstraction, abstraction refinement

Scope: predictive state representations (PSRs) and spectral learning; causal states / computational mechanics; past-future
information bottleneck; bisimulation, lumpability and RL state abstraction; counterexample-guided abstraction refinement
(CEGAR) and active automata learning. Methods only.

How to read the tags: [read-full] = substantial body text read (often via arXiv HTML); [read-abstract] = abstract/landing
page only; [repo/docs] = repository or documentation read; [unverified] = not opened (bibliographic data from search
snippets or memory). Formal statements marked "(unverified)" are from memory and were not checked in the source.

## Unifying view for this area (why it matters to the contract)

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

## Area synthesis hints

### Formal definitions to adopt (for props 2, 4, 5, 8)
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

### Tournament candidates from this area

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

### Baselines from this area and how to implement each well
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

### Evaluation measures relevant to (1)-(8), with pitfalls
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

### Open problems (literature gives no good answer)
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
