# Area D: Deep / neural state-space models and continuous-time latent models

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

## Area synthesis hints

### General verdict for this area
No method here gives identifiability, minimality or interventional sufficiency. They are **flexible function-class
containers** for f, phi and g. Their value for the tournament is (a) a training-objective toolbox (multi-horizon rollouts,
KL with free bits, partial teacher forcing, latent self-prediction with stop-gradient) and (b) strong predictive baselines.
Properties (2)-(5) must come from the *protocol*: encode from x(t) only, roll out open-loop, sweep k, and test with
interventions. The common architectural trap is a hidden history channel (the RSSM deterministic h, VRNN autoregressive
feedback, CPC/ODE-RNN context, a sequence-model decoder, a smoothing posterior). Any of these makes a small nominal k look
sufficient while the real state is large.

### Tournament candidate A: closed latent dynamics with a multi-horizon objective ("encode once, roll out")
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

### Tournament candidate B: variational / stochastic closed SSM (RSSM without h, or latent SDE)
Same as A, but with a Gaussian stochastic latent and a learned diffusion or transition noise. Use it to separate "unexplained
state" from intrinsic noise, and for abstention (8). If the learned noise does not fall as k increases and the multi-horizon
NLL plateaus far above a full-state model, abstain. Watch for diffusion absorbing model error: compare against a deterministic
model's residuals.

### Tournament candidate C: interpretable switching / piecewise-linear latent (rSLDS or shPLRNN)
Small k (2-10) and K modes (2-10), or hidden units L. These give analytic fixed points and regimes, affine identifiability
(rSLDS) that helps (6) and (7), and the PLRNN + GTF recipe for chaotic regimes. Fit rSLDS with the ssm package on
encoded/PCA-reduced x. shPLRNN is easy to write from scratch. Avoid vendoring the GPL-3.0 code unless licence-compatible.

### Baselines from this area and how to implement each well
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

### Evaluation measures for properties (1)-(8) from this area
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

### Known pitfalls specific to this area
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

### Open problems (no good answer in the literature read)
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
