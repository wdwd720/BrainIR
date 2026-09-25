# Area A: Classical and linear/nonlinear system identification and model reduction

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

## Area synthesis hints

### Tournament candidates from this area
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

### Baselines from this area and how to implement each well
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

### Using simulator interventions/inputs as excitation (practical rules)
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

### Evaluation measures relevant to (1)-(8) from this area, and pitfalls
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

### Open problems (literature gives no good answer)
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
