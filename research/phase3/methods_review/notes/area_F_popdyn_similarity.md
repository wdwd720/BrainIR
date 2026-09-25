# Area F: Population-dynamics latent-variable methods and comparing latent spaces up to transformations

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

## Area synthesis hints

### Tournament candidates from this area
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

### Baselines from this area and how to implement well
- **GPFA / FA + smoothing:** fit on square-root or z-scored activity; select q by leave-unit-out cross-validated prediction;
  orthonormalise for display only. No transition law, so pair with a fitted linear AR on the latents for forecasting.
- **PCA + linear dynamics / latent LDS:** Kalman-smoothed EM with inputs; regularise A (ridge) and check spectral radius;
  compare with RRR from past x/u to future x (a direct linear predictive-state baseline).
- **Trained-RNN + fixed-point skeleton:** fit a vanilla GRU to the data, run FixedPointFinder per input level, and use the
  number/type of fixed points and Jacobian spectra as a comparison target for every other model.
- **Denoising transformer (NDT) as an upper bound on smoothing quality** (not a state model).
- **Random-projection and PCA encoders at the same k** as nulls for every similarity measure below.

### Recommended measures for comparing latent spaces up to transformations (props 6 and 7)
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

### Known pitfalls
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

### Open problems
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
