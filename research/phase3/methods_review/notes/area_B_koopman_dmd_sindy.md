# Area B: Koopman operator learning, dynamic mode decomposition, sparse identification

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

## Area synthesis hints

### Tournament candidates from this area

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

### Baselines from this area and how to implement each well

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

### Evaluation measures relevant to properties (1)-(8)

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

### Pitfalls

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

### Open problems where the literature gives no good answer

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
