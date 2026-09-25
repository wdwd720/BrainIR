# Area G: Experiment design, system identification under interventions, canonical dynamical coordinates, evaluation of learned dynamical models

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

## Area synthesis hints

### A. What a simulator changes
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

### B. Tournament candidates from this area
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

### C. Simulation-budget / data-generation protocol (concrete)
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

### D. Evaluation measures relevant to (1)-(8) from this area
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

### E. Pitfalls specific to this area
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

### F. Open problems (literature gives no good answer)
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
