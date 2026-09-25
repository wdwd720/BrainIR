# Area E: Causal representation learning, identifiability, nonlinear ICA, invariance, causal abstraction

Scope: methods only. The target problem (CONTRACT.md) is a micro-simulator x(t) (N units) with input u(t), readout y(t) and
microscopic interventions; we want z = phi(x), z' = f(z,u), y = g(z,u). This area asks: under which data and intervention
regimes is z identifiable, and up to what transformation? How do we test whether (phi, f, g) is a valid causal abstraction of
the simulator?

Citation tags: [read-full] = substantial body text read; [read-abstract] = abstract or landing page only; [repo/docs] = repo
or docs read; [unverified] = from memory, not opened in this session. Venue details not shown on the page I opened are
marked (unverified).

## Quick map: identifiability classes and data requirements

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

## Area synthesis hints

### Tournament candidates from this area

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

### Baselines from this area and how to implement them well
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

### Evaluation measures (properties 1-8) and a concrete interchange-intervention / abstraction-error recipe

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

### Open problems (no good answer in the literature read)
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
