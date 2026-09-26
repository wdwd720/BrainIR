# Methods review: causal state models trained with interventions, and active experiment design

Workspace: methods-only literature review (contract: `docs/METHODS_REVIEW_CONTRACT.md`). Date: 2026-09-26.
Companion files: `REFERENCES.md` (full bibliography with read status), `notes/` (per-area working notes with more detail,
equations and pseudo-code).

## 0. How to read this review

**Problem restated (notation used throughout).** Microstate x(t) of a simulated population (N units, 10-200 observed),
ordinary input u(t), readout y(t), physical intervention a(t) (kick, pulse, sustained current, temporal pattern, silencing,
connection weakening/removal, parameter change; restarts from arbitrary microstates). We want

    encoder  z_t = phi(x_{<=t}, u_{<=t})      dynamics  z_{t+dt} = f(z_t, u_t, a_t)      readout  y_t = g(z_t, u_t)
    read-in  z+ = R(z-, a)  (Delta z = r(z, a))   lift  a* = argmin cost(a) s.t. R(z, a) ~ z + Delta z*

with the intervention's effect flowing through z (state mediation / interventional closure), microstate equivalence, transfer to
unseen intervention types/targets, k chosen for intervention fidelity, abstention, and an active design loop.

**Evidence labels.** Each source in `REFERENCES.md` carries a read level: *full* (method section / full text read), *abstract*
(abstract or abstract-level summary read), *metadata* (bibliographic record or search summary only), *background* (standard
textbook material not re-checked in this session). In the text:

- `[unverified]` marks a specific claim I could not check against the primary source in this session.
- `[std]` marks standard textbook formulas written from background knowledge (the canonical form, but not re-checked here).
- `[synthesis]` marks my own adaptation or proposal. These are not claims made by any cited paper.

Most sources were read at abstract level. Full method sections were read for:

- the interventional SSM paper (Nejatbakhsh & Wang 2025);
- the low-rank active-stimulation paper (Wagenmaker et al. 2024);
- the interventional SDE identifiability paper (arXiv:2505.15987);
- the additive-latent-shift paper (von Kügelgen et al.);
- BRAID, iLQR-VAE and the IPSID preprint;
- the Rainforth et al. 2024 design review;
- the Lüth et al. 2023 active-learning evaluation pitfalls;
- the Bania 2019 discrimination design;
- the action-conditioned section of V-JEPA 2;
- Jonas & Kording 2017;
- the methods of Sourmpis et al. 2025;
- De, Kiani & Mazzucato 2026.

**Scope rule.** This is a methods review. Real-data applications in the cited papers are described only generically.

## Executive summary

1. **Closest published template.** The closest match to "interventions inside the latent model from the start" is the
   *interventional state-space model* (iSSM; Nejatbakhsh & Wang, ICML 2025).
   - **Model.** Linear latent dynamics with a hard clamp (do) on the latent coordinates that a stimulation hits, plus a
     nonlinear emission.
   - **Training.** Variational inference with a causal recognition network.
   - **Identifiability.** Block identifiability; elementwise identifiability (up to permutation and scale) when the
     intervention regimes cover every pair of latents.
   - **What it does not handle.** None of the other published interventional latent models mixes additive, clamp,
     observation-level and mechanism-change interventions in one model, and none generalises to unseen intervention
     *types*. The read-in R(z, a) for silencing, connection edits and parameter changes remains open (Sections 1, 2, 3).
2. **Intervention counts.** Identifiability theory gives explicit counts of how many intervention regimes are needed. These
   counts should set the minimum design:
   - latent-pair coverage (iSSM);
   - r shift regimes for a rank-r linear coupling, about r² in the nonlinear small-noise case (interventional SDEs);
   - one intervention per latent node in linear and nonparametric causal representation learning (CRL);
   - one per strongly connected component for Ornstein-Uhlenbeck steady states.
3. **Model class.** Additive models can represent kicks, pulses, currents and temporal patterns (examples: DMDc, subspace ID,
   Koopman lifts that are linear in the input). Silencing, connection weakening and parameter changes multiply the state, so the
   minimum principled class is **bilinear / control-affine**: z+ = A z + Σ_j a_j (N_j z + b_j). Bilinear Koopman and SINDYc
   support this form.
4. **Unseen targets.** Generalisation to unseen *targets* requires a **structured read-in** that is parametrised by the
   physical actuation geometry. Examples: B = W_in E, low-rank-RNN loadings, or emission pseudo-inverse rows. A free column
   per intervention ID never transfers. Unseen *types* have no guarantee anywhere in the literature, so they must be
   benchmarked on held-out families and the model should abstain on them.
5. **Passive fit is not evidence of mechanism.**
   - Twin models that match on passive data are separated only by perturbation.
   - Partial observation creates spurious attractors.
   - Models with the same outputs can differ in their perturbation responses.
   - Causal-abstraction metrics are the only ones that validate abstractions.

   The mediation / closure / equivalence tests should therefore be **interventional**. They should be built on
   exact-transformation consistency and interchange interventions (Sections 2, 6, 9).
6. **Active design.** Theory and the closest analogue (low-rank AR with targeted stimulation) show that adaptive designs beat
   white-noise or random stimulation, but typically by **≤ 2x in data**, not by orders of magnitude. The fair-comparison
   protocol matters as much as the acquisition function (Section 5).
7. **Recommended tournament.** Ten families (Section II.2):
   - F1 interventional linear SSM;
   - F2 tuned and bagged DMDc, plus a bilinear variant;
   - F3 subspace ID with control (CVA / IPSID-style);
   - F4 sparse control-affine SINDYc;
   - F5 controlled Koopman (bilinear);
   - F6 interventional predictive bottleneck;
   - F7 latent neural controlled SSM;
   - F8 neural ODE with a jump / intervention operator;
   - F9 adapted mixed-mode interventional SSM (iSSM-mix);
   - F10 shared-dynamics model with implementation-specific encoders / read-ins.

   There are seven acquisition functions and one cost wrapper (Section II.4), and ten baselines (Section II.5).

---

# PART I. Literature by area

Each area has two parts. First, the key methods, described precisely. Second, a **method record**. For methods not detailed
here, the record is a table with these fields: assumptions (Assm.), identifiability (Ident.), intervention representation
(Interv.), unseen types / targets, nonlinear capacity, read-in interpretability, scaling, compute, failure modes, relevance,
open-source code, and how simple a from-scratch implementation is.

## 1. Interventional state-space models

### 1.1 iSSM: Interventional state-space models (Nejatbakhsh & Wang, ICML 2025). The primary template

*Read: full method (text-extracted PDF) + code (fetch summaries of `models.py` / `inference.py`). PMLR 267:45877-45894.*

**Generative model** (their x is our z):

    z_{t+1} = 1{B u_t = 0} ⊙ A z_t  +  B u_t  +  ε_t,     ε_t ~ N(0, Q)
    y_t     ~ p( y_t | f_θ(z_t) )           (Gaussian or Poisson; f_θ = MLP (3 x 100 tanh in code) or linear C)

- u_t ∈ R^M is the known stimulation vector (one entry per stimulation channel). B ∈ R^{k×M} maps channels to latent
  coordinates and is sparse, with an L1 (Laplace) prior.
- The indicator is evaluated **per latent coordinate**. A latent coordinate that receives non-zero input is **clamped**: it is
  cut from its parents, and its next value is (B u)_i + noise. This is a hard do() on the latent coordinate.
- The code uses the discretised continuous-time form `mu = (inp==0)*((1-dt)*z + dt*A@z) + inp`. A flag
  `interventional=False` turns this into the ordinary additive model `mu = (1-dt) z + dt A z + B u`.
- Intervened observed units are *not* masked out of the likelihood.

**Identifiability** (paper §3; wording of the pair condition paraphrased, `[unverified]` exact form).

Assumptions:

- bounded completeness of p(y|z);
- piecewise-linear, continuous, injective mixing f_θ (ReLU-type; the code uses tanh, a theory/code gap);
- faithfulness of the unperturbed dynamics;
- linear-Gaussian latent dynamics;
- hard latent interventions with known u.

Results:

- **Theorem 3.4 (block identifiability).** A and f_θ are identified up to a block-diagonal affine map. The blocks separate
  intervened from non-intervened latents. Observation laws under *novel* interventions are identified if those interventions
  act on separate blocks.
- **Corollary 3.6 (up to permutation and scaling).** This holds if for every pair of latents (i, j) there are regimes that
  intervene on i without j and on j without i. So O(k) regimes with suitable coverage are needed, which is an explicit
  **design constraint**.

**Inference.** Amortised variational inference with a **causal** LSTM recognition network over [y_{≤t}, u_{≤t}]:

    ELBO = E_q[ log p(y_{1:T}|z_{1:T}) + log p(z_{1:T}|u_{1:T}) − log q(z_{1:T}|y,u) ],
    q = Π_t N(μ_Φ(y_{≤t},u_{≤t}), diag σ²_Φ(·))

The "interventional posterior trick" overwrites the posterior mean so that it respects the clamp:
μ_t ← 1{Bu_t=0} ⊙ μ_t + B u_t. The code minimises `−log_joint + γ·log_q` with Adam.

**Experiments** (generic description). The synthetic tests use 2-D rotational and attractor latents with 5-20 observed
dimensions. There, iSSM recovers A up to the allowed symmetry, while an additive SSM fits the observations equally well but
gets A wrong. On two real stimulation datasets (N ≈ 100-200, 5-30 latents), iSSM gives better held-out reconstruction and a
"consistency score" (distance between the B matrices of different seeds).

**Limitations stated in the paper.**

- The latent dynamics are linear.
- The assumption that interventions act directly on the latents is untested.
- Low dimensionality under intervention is not justified.

**Fit to our simulator** `[synthesis]`.

- Kicks and pulses are additive, so a clamp is wrong for them (it discards the state). Use the additive mode or a mixed
  read-in.
- Silencing a *unit* is a do() on the microstate, not on a latent coordinate. It reaches z only through the encoder.
- Connection removal and parameter changes are mechanism changes (soft interventions on A), which iSSM does not cover.
- Arbitrary restarts help, because they give diverse z_0, which strengthens the faithfulness and excitation assumptions.

**Code.** `github.com/amin-nejat/issm` (JAX / NumPyro / Flax). The README says "work-in-progress" and there is no licence file,
so treat it as all rights reserved.

### 1.2 Active learning of low-rank population dynamics with targeted stimulation (Wagenmaker et al., NeurIPS 2024)

*Read: full method (arXiv HTML v1). arXiv:2412.02529.*

This is an observed-space AR(p) model with per-unit additive stimulation:

    x_{t+1} = Σ_{s<p} ( A_s x_{t−s} + B_s u_{t−s} ) + v,    y_t = x_t + w_t
    A_s = D_{A_s} + U_{A_s} V_{A_s}^T,   B_s = D_{B_s} + U_{B_s} V_{B_s}^T    (diagonal + rank r)

- u_t ∈ [0,1]^d: every unit has its own input channel, and the targets are known.
- The latent is the r-dimensional span of V.
- **Fitting** is least squares or nuclear-norm-constrained least squares. Note: regressing on noisy y has an
  errors-in-variables bias `[synthesis]`.
- **Design** (Algorithm 1, doubling epochs):
  1. Estimate the top-r right singular subspace V̂₀.
  2. Solve two A-optimal designs over U = {u ∈ [0,1]^d : ‖u‖₁ ≤ γ}: λ^V = argmin tr((V̂₀ᵀΛ(λ)V̂₀)⁺) and
     λ^unif = argmin tr(Λ(λ)⁺).
  3. Sample stimulations from ½λ^V + ½λ^unif for 2^l trials, then refit.
- **Theory.** Theorem 1 decomposes the error into a term aligned with the subspace, tr((V₀ᵀΣV₀)⁺), and an isotropic term,
  tr(Σ⁺).
- **Result.** Up to about 2x fewer trials than random stimulation for the same accuracy.
- **What it lacks.** No hidden state beyond the low-rank coupling, no nonlinearity, and no mechanism interventions. No code
  was found `[unverified]`.

### 1.3 Identifiability of interventional SDEs with shift interventions (arXiv:2505.15987, 2025)

*Read: full method (HTML). The authors could not be captured `[unverified]`.*

The model is dX = v(X)dt + √ε dB with a stationary law. There are two forms of the drift:

- linear, v(x) = (AB − D)x with A ∈ R^{n×r} and B ∈ R^{r×n} (a rank-r coupling);
- nonlinear, v(x) = Aσ(Bx) − x (a low-rank RNN).

The intervention is a **known shift** of the drift, dX = (v(X) + c_i)dt + √ε dB. This is exactly a sustained current. Only the
stationary distribution of each regime is used.

Theorems:

- **Linear case (Thm 4.3).** With generic parameters, isotropic interventions and known D, **r interventions suffice** almost
  surely. r − 2 are not enough.
- **Nonlinear case (Thm 4.7-4.8).** In the small-noise limit with a contractive σ, **~r² interventions** and the first two
  moments recover A up to signed permutation. The error is ~ε^{1/2} poly(n, r, K).

Estimation is by moment matching: Lyapunov matching in the linear case, and fixed-point plus Jacobian-Lyapunov matching in the
nonlinear case. It is cheap (O(n²) per regime, CPU).

The method fails for transients, multistability, oscillation and large noise. On a semi-synthetic network-inference benchmark it
performs only slightly above chance (AUPRC ~0.07 vs 0.06).

For us it has two uses: its intervention counts can serve as a design prior, and its stationary-moment loss can be an extra
term for sustained currents. No code was found `[unverified]`.

### 1.4 Additive latent shift with an extrapolation guarantee (von Kügelgen, Ketterer, Vollenweider, Scholkemper, Shen, Meinshausen, Peters; arXiv:2504.18522 v3, 2026)

*Read: full method (HTML).*

The model is an encoder g: x → z plus a perturbation shift z_{e→h} = z_e + W(a_h − a_e) and a decoder f(z, noise). The loss is
a distributional **energy score** that matches every source condition to every target condition.

**Thm 4.7.** Assume f is an invertible C² map, the latent is isotropic Gaussian, and rank(W A) = d_Z. Then the effect of any
a_test with (a_test − a₀) in the span of the training perturbations is identified. This is extrapolation to **combinations**
inside the span, not to new directions. Interactions between perturbations are not handled.

**Use for us.** This is the template for a state-independent read-in r(z, a) = W a, and the energy-score loss suits a
stochastic simulator. The additive-shift assumption can be falsified: estimate W a separately in bins of z₋, and treat any
dependence on z as evidence that r(z, a) is needed `[synthesis]`.

### 1.5 BRAID: input-driven nonlinear dynamical modelling (Vahidi, Sani, Shanechi; ICLR 2025; arXiv:2509.18627)

*Read: full method (HTML).*

Forward model and predictor:

    forward:   x_{k+1} = A_fw(x_k) + K_fw(u_k) + w_k,  y_k = C_y(x_k,u_k) + v_k,  readout_k = C_z(x_k,u_k) + ε_k
    predictor: x_{k+1|k} = A(x_{k|k−1}) + K(y_k, u_k)   (causal, learned nonlinear filter)
    loss:      Σ_i α_i MSE(y_{k+m_i}, C_y(x_{k+m_i|k}, u))  with open-loop forecasts x_{k+m|k} = A_fw(x_{k+m−1|k}) + K_fw(u_{k+m−1})

Key point: the **multi-step open-loop forecast with known inputs** separates intrinsic dynamics A_fw from input effects K_fw.
With one-step filtering alone, K absorbs the dynamics. The paper checks this by recovering the eigenvalues in linear
simulations; it gives no nonlinear identifiability guarantee.

The input map K_fw(u) is additive and independent of the state. Code: `github.com/ShanechiLab/BRAID` (licence not checked).

**Use for us.** Keep the causal filter and the multi-step intervention-future loss, and replace K_fw(u) by R(z, a).

### 1.6 Related input-driven latent models (brief)

- **iLQR-VAE** (Schimel, Kao, Jensen, Hennequin; ICLR 2022). *Read: full (bioRxiv).*
  - **Model.** z_{t+1} = f_θ(z_t, u_t), with unknown inputs under a Gaussian or hierarchical Student-t (sparse) prior.
  - **Inference.** The posterior mode over the inputs is found by iLQR, and training differentiates through it implicitly.
    There is no amortisation gap.
  - **Cost.** O(T(n³ + n² n_o)) per iteration.
  - **Use for us.** Latent-space inference of inputs is the mathematical twin of our lift, and the Student-t prior suits
    sparse kicks. The inference is a smoother (acausal).
- **LFADS** (Sussillo et al. 2016, arXiv:1608.06315; Pandarinath et al. 2018). *Read: abstract.*
  - **Model.** Generator RNN, bidirectional encoder, and a controller that produces **inferred inputs**.
  - **Problems.** It is acausal, and the split between inputs and dynamics is set by the prior on the inputs.
- **Computation-through-Dynamics benchmark** (Versteeg et al., bioRxiv 10.1101/2025.02.07.637062). *Read: full-text summary.*
  - **Finding.** Models that infer inputs reconstruct equally well while attributing dynamics to the inferred inputs
    ("dynamical misattribution").
  - **Metrics provided.** State R² (affine map from true to inferred latents), cycle consistency, input R².
- **Input-output LSSM identification with binary-noise stimulation** (Yang, Connolly, Shanechi, J. Neural Eng. 2018,
  doi:10.1088/1741-2552/aad1a8). *Read: abstract.*
  - **Method.** A MIMO LSSM whose input is the stimulation parameters, excited by (generalised) binary noise, i.e. PRBS-like
    designs.
  - **Result.** They report much lower estimation error than step, sine or multisine modulation `[unverified magnitude]`.
- **SPARTAN** (Baumgartner, Lei, Watson, Posner; arXiv:2603.14483, 2026). *Read: full-method summary.*
  - **Result.** Latent parameters are identified up to permutation and elementwise maps when the local causal graphs satisfy
    ∩_{children a of i} Pa(a) = {i}.
  - **Use for us.** Sparsity of influence is the lever for our *parameter-change* interventions.
- **Low-rank latent carriers for counterfactual rollouts** (Liu & Chen, arXiv:2608.15156, 2026). *Read: abstract.*
  - **Method.** An affine read-in from (factual state, edit) onto a low-rank carrier subspace.
  - **Finding.** The carrier rank is not the same as the state dimension, so report the read-in rank and k separately.
- **Steady-state identifiability for linear stochastic dynamics** (Salehkaleybar, arXiv:2609.19955, 2026). *Read: abstract.*
  - **Result.** For a multivariate Ornstein-Uhlenbeck process, one intervention per strongly connected component suffices.
- **Causal models for dynamical systems** (Peters, Bauer, Pfister, arXiv:2001.06208). *Read: abstract.*
  - **Content.** Formal semantics: a clamp replaces a coordinate's equation; a mechanism change modifies f_i.
- **rSLDS** (Linderman et al., AISTATS 2017, arXiv:1610.08466). *Read: abstract.*
  - **Model.** z_{t+1} = A_{s}z_t + V_s u_t + b_s. The input term is from the `ssm` package `[unverified in paper]`.
  - **Use for us.** A **persistent** intervention can switch the regime s.
- **Latent-dynamics review** (arXiv:2606.10530, 2026). *Read: perturbation section.*
  - **Finding.** Most latent models are observational and rarely predict perturbation responses.
- **What latent world models can know** (Tan et al., arXiv:2607.27017). *Read: abstract.*
  - **Finding.** Latents keep only what the prediction target requires; a quantity fed in only as an input vanishes from the
    latent.
  - **Use for us.** Choose k for intervention futures, not for passive fit.

### 1.7 How an intervention can enter a latent SSM

| Mode | Latent equation | Semantics | Source | Our intervention types |
|---|---|---|---|---|
| Additive input | z+ = f(z) + B a | shift / kick | 1.2, 1.5, standard LDS | kicks, pulses, trains, sustained currents |
| Clamp (hard do) on latent coords | z+ = (1−m(a))⊙f(z) + m(a)⊙c(a) | cut parents | 1.1 | only if a latent is aligned with a unit; strong silencing |
| Drift shift | dz = (v(z) + c)dt | sustained current | 1.3 | sustained activation / inhibition |
| Static additive latent shift | z' = z + W a | state-independent read-in, superposition | 1.4, 1.6 carriers | small kicks; tests state dependence |
| Mechanism change / regime | f → f_a (A + Σ a_l U_l V_lᵀ; switch s) | soft intervention on dynamics | 1.6 SPARTAN, rSLDS, Peters | connection removal, parameter change, persistent silencing |
| Inferred unknown input | z+ = f(z, û) | unknown drive | iLQR-VAE, LFADS | none (a is known); residual channel only |
| Observation-level do | y_j := value; drop y_j from the likelihood; feed it to the encoder | microstate clamp | none explicitly | silencing observed units |

No published interventional SSM I found combines all of these modes in one model.

### 1.8 Identifiability facts for an interventional linear SSM

These are standard systems-theory facts `[std]` combined with 1.1-1.3.

- **Additive model.** For z+ = Az + Ba + w, y = Cz + Du + v, the model is identified only up to similarity: z → Sz,
  (A, B, C, Q) → (SAS⁻¹, SB, CS⁻¹, SQSᵀ). The Markov parameters CAⁱB, the transfer function and the eigenvalues are
  identifiable when (A, B) is controllable, (A, C) is observable, and a is persistently exciting.
  - The mediation, closure and prediction tests depend only on these similarity-invariant quantities, so no coordinate
    identifiability is needed for them.
- **Coordinate identifiability.** Recovering coordinates up to permutation and scaling needs one of the following:
  - clamps covering all latent pairs (1.1);
  - sparsity of the read-in or input matrix (SPARTAN; Zhang & Xie 2024 in §2);
  - targeted interventions on single latents (§2).
- **Intervention counts.**
  - Stationary shift regimes: ≥ r in the linear case, ~r² in the nonlinear case.
  - Ornstein-Uhlenbeck steady states: one per strongly connected component.
  - Trajectories with transient kicks: fewer regimes are needed, because each kick excites the impulse response CAⁱBe_j
    `[synthesis]`.
- **Unobserved directions.** A kick into ker C is invisible until the dynamics carry it into observed directions. Designs must
  therefore excite poorly observed directions (see §5).

### 1.9 Adapted model: iSSM-mix (exact EM with a time-varying linear-Gaussian model) `[synthesis]`

The adapted model mixes additive, clamp, observation-level and mechanism interventions in one time-varying linear-Gaussian
model, so exact Kalman filtering and EM apply.

    z_{t+1} = A_t z_t + B u_t + G a^add_t + b_t + w_t,      w_t ~ N(0, Q_t)
    A_t = (I − M_t) A_{s_t},   b_t = M_t c_t,   Q_t = (I − M_t) Q (I − M_t) + M_t Q_c M_t
    A_s = A + Σ_l s_l U_l V_lᵀ                  (known mechanism context s_t: connection removed / parameter changed)
    y_t = C z_t + D u_t + d + v_t,   R_t = R with rows of silenced observed units removed
    readout_t = H z_t + E u_t

The components:

- **Additive channels.** a^add holds the pulse, kick and current channels.
- **Unseen targets.** Use a **structured** G = Γ Φ, where Φ[:, j] is a feature vector of unit j (for example the emission row
  C_jᵀ). The simplest choice is G e_j = α (C⁺)_j, which makes the read-in generalise to unseen targets. This is speculative
  and must be tested on held-out targets.
- **Clamps.** M_t = diag(m_t) is a clamp mask. Use it only for latents aligned with a unit or group, after a targeted design.

**E-step.** Run a Kalman filter and RTS smoother with (A_t, b_t, Q_t, R_t). This gives ẑ_t, P_t and P_{t,t−1}, and the
sufficient statistics S_t = P_t + ẑẑᵀ and S_{t,t−1} = P_{t,t−1} + ẑ_t ẑ_{t−1}ᵀ.

**M-step** (additive part). Let x_t = [z_t; u_t; a_t; 1], Θ = [A B G b], and ξ_t = [z_t; u_t; 1]:

    Θ = (Σ_t E[z_{t+1} x_tᵀ]) (Σ_t E[x_t x_tᵀ])⁻¹ ;   Q = (1/(T−1)) Σ_t (S_{t+1} − Θ E[x_t z_{t+1}ᵀ])
    [C D d] = (Σ_t y_t E[ξ_tᵀ]) (Σ_t E[ξ_t ξ_tᵀ])⁻¹ ;   R = (1/T) Σ_t (y_t y_tᵀ − [C D d] E[ξ_t] y_tᵀ)

The other interventions modify the M-step as follows:

- **Clamps.** Estimate row i of Θ only on steps where m_{t,i} = 0 (per-row weighted least squares). Fit c_t = K_c a_t from the
  clamped rows.
- **Silenced observed units.** Drop their rows in the E-step and in the updates of C and R.
- **Mechanism contexts.** Keep sufficient statistics per context and fit U_l V_lᵀ by reduced-rank regression.
- **Restarts.** Sum the statistics over trials. Model the initial state as z₀ ~ N(μ₀, V₀) per restart family.

**Model selection.** The Kalman innovations give the log-likelihood for choosing k and the ranks. Prefer the **held-out
interventional** log-likelihood or the multi-step intervention-future error for this choice (1.5, 1.6 Tan et al.).

**Nonlinear variant.** The transition becomes

    p(z_{t+1}|z_t,u_t,a_t) = N((1−m(a_t))⊙[f_θ(z_t,u_t) + R_φ(z_t,a_t)] + m(a_t)⊙c(a_t), Q)

Train it with a causal GRU/LSTM filter and the iSSM clamp overwrite, and add BRAID-style open-loop multi-step terms
Σ_{m∈{1,2,4,8,…}} ‖y_{t+m} − g(ẑ^{roll}_{t+m|t})‖². Keep any inferred-input channel off or heavily penalised.

**Software.**

- `dynamax` (JAX, MIT): LinearGaussianSSM with inputs, EM, EKF/UKF. This is the best base.
- `ssm` (MIT): LDS, SLDS and rSLDS with inputs.
- `issm`: research code with no licence.

### 1.10 Does our simulator satisfy the assumptions?

| Assumption | Needed by | Our simulator |
|---|---|---|
| Known interventions (targets, timing, magnitude) | 1.1-1.5 | Yes |
| Linear latent dynamics | 1.1 theory, 1.2 | No in general; locally yes around operating points. Kicks of varying size test this. |
| Hard latent clamp | 1.1 | Rarely. Unit silencing clamps a microstate coordinate. |
| Additive latent shift | 1.2, 1.4, 1.5 | Plausible for small kicks. Violated by saturation and state-dependent gain, which need R(z, a). |
| Stationarity, small noise | 1.3 | Holds for sustained currents; not for transients. |
| Enough regimes covering latent pairs (≥ r, ~r²) | 1.1, 1.3 | Achievable: simulations are cheap and restarts are free. This is a design task. |
| Injective emission | 1.1 | Partial observation (10-200 of N units) breaks it; the encoder must use history. |
| Mechanism changes | none | Not covered by any source. |
| Arbitrary restarts | none require them | Yes. This enables paired "same z, different microstate" tests. |

### 1.11 Method record, area 1

| Method | Assm. | Ident. | Interv. | Unseen types / targets | Nonlin. | Read-in interp. | Scaling | Compute | Failure modes | Relevance | Code | Scratch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| iSSM | linear latent, injective emission, hard latent do, known u | block; perm+scale with pair-covering regimes | clamp (or additive) via sparse B | new combos of known channels; not new types/targets | emission only | high | small N tested; O(TNH) per ELBO | CPU/GPU (JAX) | clamp/additive mismatch; brittle "B u = 0" mask; LSTM absorbs dynamics | **high** | issm (no licence, WIP) | simple (linear EM version) |
| Low-rank AR + active design | linear, observed space, per-unit additive inputs | A, B from PE inputs | additive per unit | unseen targets yes (every unit has a column); types no | none | high | d ≲ 700; O(d³) SVD | CPU | rank misspecification; EIV bias | high (design) | none found | simple |
| Interventional SDE | stationary, small noise, contractive, known shifts | r (linear) / ~r² (nonlinear) regimes | drift shift | new shift vectors | low-rank RNN | high | O(n²) per regime | CPU | transients, multistability | medium-high | none found | simple |
| Additive latent shift (PDAE) | invertible decoder, Gaussian latent, spanning perturbations | effects inside the span | z + W a | combinations in span only | encoder/decoder | high | static | GPU/CPU | leaves decoder support; no interactions | medium | not found | simple |
| BRAID | causal filter; forecasting loss | eigenvalues (linear sims); none nonlinear | additive K_fw(u) | K_fw extrapolation only | MLP | medium | 16-64 states | CPU `[unverified]` | unmeasured inputs; state-independent read-in | high (objective) | ShanechiLab/BRAID | moderate |
| iLQR-VAE | known f form, sparse input prior | split set by prior | inferred input | as oracle read-in | RNN | medium | O(T n³) | CPU (MPI) | local optima; acausal | medium | OCaml `[unverified]` | hard |
| rSLDS + inputs | piecewise linear | similarity; mode perm | V_s a per mode | structured V only | moderate | high | long T fine | CPU | mode collapse | medium | ssm (MIT) | inference hard |

## 2. Causal representation learning (CRL) with interventions; causal abstraction

### 2.0 Where our problem sits in the CRL taxonomy

CRL assumes that interventions act on **latent** nodes. Ours act on **micro** units and parameters. So in latent terms a
physical intervention is generally:

- a **multi-node** intervention,
- **soft** (imperfect),
- with **unknown latent targets**, because learning those targets is the read-in problem.

This is the hardest regime. The theory there gives identifiability only "up to ancestors", or up to surrounded-node ambiguity.
Two features of our setting are much stronger than the usual CRL assumptions:

1. **Paired counterfactual data.** We can restart from the same microstate with common random numbers and apply a versus a′.
   This is exactly the weakly supervised setting of Brehmer et al. 2022.
2. **Known physical descriptors.** For every intervention we know its type, target, magnitude and timing.

Consequence `[synthesis]`: test **mediation and closure**, which do not depend on how z is parametrised. Do not test whether
individual coordinates are recovered.

### 2.1 Identifiability results (i.i.d. CRL)

| Paper | Setting | Result | Implication for us |
|---|---|---|---|
| Squires, Seigal, Bhate, Uhler, ICML 2023, arXiv:2211.16467 (*abstract + theorem summary*) | linear SEM latents, linear mixing, single-node soft or perfect interventions | **One intervention per latent node is necessary and sufficient** | A latent direction that no intervention moves is unidentified. Design must perturb every direction. |
| Varici et al., JMLR 26(112) 2025, arXiv:2402.00849; AISTATS 2024, arXiv:2310.15450; NeurIPS 2024, arXiv:2406.05937 (*abstract*) | score-based; linear or general mixing; single-node, or unknown multi-node | Linear mixing: 1 hard intervention per node gives perfect identifiability. General mixing: 2 hard interventions per node. Unknown multi-node: soft gives identifiability up to ancestors, hard gives perfect. | An intervention's signature is the **score difference ∇log p_a − ∇log p_0, which is sparse in true z**. This is a usable read-in localisation diagnostic. |
| Buchholz et al., NeurIPS 2023, arXiv:2306.02235 (*abstract*) | Gaussian linear-SEM latents, arbitrary injective nonlinear mixing, unknown single-node interventions | Identifiable (first such result for deep encoders) | Contrastive training: log p_a/p_0 is quadratic in z. Matches "linear latent dynamics + nonlinear encoder". |
| Jin & Syrgkanis, arXiv:2311.12267 (*abstract*) | general environments (many mechanisms change) | Graph identifiable; latents only up to **surrounded-node ambiguity**, which is unavoidable | Our interventions are "general environments" in latent space, so do not expect coordinate semantics. |
| von Kügelgen et al., NeurIPS 2023, arXiv:2306.00542 (*abstract*) | nonparametric latents and mixing, unknown perfect interventions | A pair of distinct perfect interventions per node suffices; causal influence strengths are preserved across all equivalent solutions | About 2 hard intervention families per latent dimension in the fully nonparametric case. |
| Jiang & Aragam, NeurIPS 2023, arXiv:2306.02899 (*abstract*) | nonparametric measurement model, number of latents unknown | Latent graph identifiable with ≤ 1 unknown intervention per hidden variable | Supports estimating **k from interventional data**. |
| Zhang, Squires, Greenewald, Srivastava, Shanmugam, Uhler, arXiv:2307.06250 (NeurIPS 2023 `[venue unverified]`) (*abstract*) | soft single-node interventions, unknown targets, nonlinear mixing | Identified up to an equivalence class; predicts **unseen combinations** | Train on single targets, test on paired or grouped silencing. |
| Ahuja, Mahajan, Wang, Bengio, ICML 2023, arXiv:2209.11924 (*abstract*) | do-interventions cause support/geometry signatures | Perfect: identified up to permutation and scale. Imperfect: block-affine. (Polynomial decoder `[unverified]`.) | Cheap diagnostic: under a clamp, the targeted z_i should become near-constant across microstates. |
| Brehmer, de Haan, Lippe, Cohen, NeurIPS 2022, arXiv:2203.16437 (*abstract*) | **paired** samples before and after an unknown intervention, with shared noise | Causal variables and graph identifiable | **Our regime.** Encode (x_pre, x_post) pairs and require that a sparse Δz explains the pair and its future. |
| Saengkyongam, Rosenfeld, Ravikumar, Pfister, Peters (Rep4Ex), ICLR 2024, arXiv:2310.04295 (*abstract*) | action A enters Z **linearly** (Z = MA + V), nonlinear mixing | Z identified up to affine; **extrapolation to unseen action magnitudes** | A linear-in-a read-in plus a nonlinear encoder extrapolates in magnitude. It does not extrapolate to new *types* unless they are parametrised in the same a-space. |
| Gamella, Bing, Runge, arXiv:2502.20099 (*abstract*) | a controllable real physical system that satisfies the CRL assumptions | **All** tested CRL methods failed to recover the factors consistently, including on its simulated twin | Do not certify a latent with identifiability theorems. Use empirical interventional tests and strong baselines. |

### 2.2 Temporal CRL with actions / interventions

- **Mechanism sparsity** (Lachapelle et al., arXiv:2401.04890, JMLR 2026; CLeaR 2022, arXiv:2107.10098). *Read: abstract.*
  - **Setting.** z_t depends sparsely on z_{t−1} and on observed auxiliary variables (actions, intervention indicators).
  - **Result.** Partial disentanglement, with an entanglement graph that says what stays mixed. Multi-node interventions with
    unknown targets can still disentangle.
  - **For us.** This is our setting: a sparse action→latent graph is our read-in. It motivates a sparsity prior on r(z, a).
- **CITRIS / iCITRIS / BISCUIT** (Lippe et al., ICML 2022, arXiv:2202.03169; ICLR 2023 `[iCITRIS id unverified]`; UAI 2023,
  arXiv:2306.09643). *Read: abstracts.*
  - **Mechanism.** A transition prior p(z^i_{t+1}|z_t, I^i_t) switches mechanism by an intervention indicator. The indicator
    is known in CITRIS; in BISCUIT it is an unknown binary interaction variable.
  - **Minimal causal variables.** Only the part of each factor that interventions move is identified.
  - **For us.** BISCUIT's binary interactions fit on/off interventions.
- **LEAP / TDRL** (Yao et al., ICLR 2022, arXiv:2110.05428; NeurIPS 2022). *Read: search summaries.*
  - **Result.** Latent processes are identifiable up to permutation and componentwise maps, given independent process noise
    and "sufficient variability" of the transitions.
  - **Caveat.** Micro-level noise aggregated into z may be correlated, which violates the assumption.
- **Rajendran, Reizinger, Brendel, Ravikumar**, CLeaR 2024, arXiv:2311.18048. *Read: abstract.*
  - **Result.** Gaussian LTI systems are identifiable from **diverse intervention signals across environments**. The
    identifiability conditions are tied explicitly to experiment design.
  - **For us.** This bridges CRL and persistent excitation.
- **Zhang & Xie**, arXiv:2410.17882 (preprint). *Read: abstract.*
  - **Result.** For linear and control-affine latent dynamics with **sparse input matrices** (in the style of a controllable
    canonical form), latents are identified up to scaling.
  - **For us.** A concrete way to remove the GL(k) ambiguity of our control-affine family.
- **Yao, Müller, Locatello**, NeurIPS 2024, arXiv:2405.13888. *Read: abstract.* CRL applied to identifying ODE parameters.
  Relevant to parameter-change interventions.
- **Yao, Rancati, Cadei, Fumero, Locatello**, ICLR 2025, arXiv:2409.02772. *Read: abstract.* Many CRL results are instances of
  the **invariance principle**. "Equal z implies equal futures" is such an invariance constraint.

### 2.3 Causal abstraction: the formal target

- **Exact transformations** (Rubenstein, Weichwald, Bongers, Mooij, Janzing, Grosse-Wentrup, Schölkopf; UAI 2017,
  arXiv:1707.00819). *Read: abstract; definition `[std]`.*
  - **Definition.** A (τ, ω) pair is an exact transformation if, for every allowed micro intervention i,
    τ_#(P_X^{do(i)}) = P_Y^{do(ω(i))}. Here ω is order-preserving and surjective. The paper covers time series mapped to
    stationary models.
  - **Mapping to us** `[synthesis]`: τ is the encoder φ, ω is the read-in, and the macro model is (f, R, g).
  - **Consequences.** "The effect flows through z" means the transformation is exact over an allowed intervention set, and
    the held-out-family test asks whether exactness survives outside the fitted set. If i₁ and i₂ have the same ω-image,
    exactness forces τ_#P^{do(i₁)} = τ_#P^{do(i₂)}. That is the **multiple-lift consistency** requirement.
- **Abstracting causal models** (Beckers & Halpern, AAAI 2019, arXiv:1812.03789; *abstract*) and **approximate causal
  abstraction** (Beckers, Eberhardt, Halpern, UAI 2019; *search summary*).
  - **Hierarchy.** Exact → uniform → τ-abstraction → strong τ-abstraction → constructive abstraction.
    - A τ-abstraction induces ω from τ. So the latent effect of a physical intervention equals the encoder applied to the
      post-intervention microstate: R(z, a) ≈ φ(x after a).
    - A strong τ-abstraction requires every macro intervention to be realisable. That is the **native lift** existence
      requirement.
  - **Approximate version.** A worst-case distance over interventions (α-approximate abstraction).
  - **Guard against cherry-picking.** Test consistency over the *whole* allowed intervention class, not only the
    interventions an optimiser happens to prefer.
- **Compositional abstraction error** (Rischel & Weichwald, UAI 2021, arXiv:2103.15758). *Read: abstract.*
  - **Definition.** The error is the worst-case distance between the two paths of the commuting diagram, for example
    Jensen-Shannon.
  - **Key property.** Errors **compose additively**, so a one-step error bounds the multi-step error. This supports one-step
    closure losses plus multi-step verification.
- **Learning abstractions jointly over many interventional distributions** (Zennaro, Dravucz, Apachitei, Widanage, Damoulas;
  CLeaR 2023, arXiv:2301.05893). *Read: abstract.*
  - **Method.** A differentiable learning objective summed over all interventional diagrams. Code:
    github.com/FMZennaro/CausalAbstraction (licence `[unverified]`).
  - **For us.** A template for our "intervention future + mediation" loss.
- **Interchange interventions / IIT / DAS / causal abstraction for mechanistic interpretability** (Geiger et al.,
  arXiv:2112.00826; arXiv:2303.02536; arXiv:2301.04709 v4 2025). *Read: abstracts.*
  - **Interchange intervention.** Run the model on base input b, overwrite the aligned representation with its value on
    source input s, and compare the result with the high-level counterfactual.
    - IIA (interchange-intervention accuracy) is the agreement rate.
    - IIT trains the model toward IIA = 1.
    - DAS learns a rotation and subspace alignment.
  - **Microstate-equivalence accuracy** `[synthesis]`: build x₁ ≠ x₂ with φ(x₁) = φ(x₂) and compare their futures under
    identical intervention sequences. Use only **reachable** (on-manifold) microstates, to avoid the "interpretability
    illusion" failure `[unverified]` (Makelov et al.). Code: `pyvene` (licence `[unverified]`).
- **Multi-level cause-effect systems / causal feature learning** (Chalupka, Eberhardt, Perona, AISTATS 2016). *Read: search
  summary.*
  - **Definition.** Macro variables are **equivalence classes of micro-states with the same interventional effect law**.
  - **Causal coarsening theorem** `[unverified precise statement]`: the causal partition is generically a coarsening of the
    observational one.
  - **For us.** A strategy: learn an observational predictive state first, then refine only where interventions show
    differences.

### 2.4 What CRL and abstraction imply for testing mediation

1. **Screening.** Y_future ⫫ (x_t, identity of a) | (z_t, R(z_t, a), u). This is a conditional-independence or
   predictive-gain test (§6).
2. **Consistency.** The macro model predicts the law of the future under ω(a). Test it with two-sample divergences per
   intervention family (the abstraction error).
3. **Interchange / equivalence.** Pairs with equal z have equal futures, and swapping z swaps the futures.
4. **Multiple realisability.** Different a with equal ω(a) give equal futures (strong abstraction).
5. **Coverage (necessity).** Latent directions that the training families never move are unidentified, so closure can fail on
   held-out families that move them.
6. **Ceiling.** Unknown, multi-node, soft latent effects allow identifiability only up to ancestors, so evaluate only
   invariant quantities.
7. **Empirical caution.** Theory does not guarantee practical recovery (Gamella et al.).

### 2.5 Method record, area 2

| Method | Assm. | Ident. | Interv. | Unseen | Nonlin. | Interp. | Scaling | Compute | Failure | Relevance | Code | Scratch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Linear CRL (Squires) | linear/Gaussian, single-node | iff 1 intervention per node | rank-1 precision change | combinations of identified nodes | none | high | ≥ k+1 contexts; cheap | CPU | multi-node, dynamics | principle | author code `[unverified]` | moderate |
| Score-based CRL | nonparametric latents | 1-2 hard per node; soft up to ancestors | score-difference sparsity | no | general | good | score estimation hard in high dimension | GPU | score error, i.i.d. | diagnostic | acarturk-e/score-based-crl | hard (general) |
| Weakly supervised (paired) | counterfactual pairs | vars + graph | latent intervention variable | no | VAE | medium | GPU | GPU | needs pairs (we have them) | **high** | `[unverified]` | moderate |
| Rep4Ex | linear action→Z | affine | Z = MA + V | **magnitudes** | encoder | high | modest | GPU/CPU | nonlinear read-in | high | `[unverified]` | simple |
| Mechanism sparsity | sparse temporal/action graph | partial disentanglement | sparse action→latent graph | no | VAE | high | GPU | GPU | sparsity must hold | **high** | `[unverified]` | moderate |
| CITRIS/BISCUIT | temporal, (binary) intervention indicators | minimal causal variables | mechanism switch | no | flows | medium | GPU | GPU | needs regime info | high | phlippe/CITRIS, BISCUIT `[licence unverified]` | nontrivial |
| Exact / τ-abstraction | micro and macro SCMs | n/a (definition) | ω map | defines the held-out test | any | high | test cost = simulations | CPU | only testable on a sampled intervention set | **definition** | n/a | trivial (test) |
| Interchange / IIT / DAS | aligned representation | IIA | patching | microstate pairs | any | high | cheap with a simulator | CPU/GPU | off-manifold patches | **high** (tests) | pyvene | simple |
| Abstraction learning (Zennaro) | finite SCMs | n/a | diagram consistency | no | any | medium | many interventions | CPU | finite spaces | medium | FMZennaro/CausalAbstraction | moderate |

## 3. System identification with inputs and interventions

Equations marked `[std]` are the canonical textbook forms. The arXiv PDFs could not be parsed in this session, so they were
checked only against abstracts. Detailed pseudo-code is in `notes/area03_sysid.md` §10.

### 3.0 Mapping our interventions onto system-ID model classes `[synthesis]`

| Physical intervention | Microstate effect | Latent representation (least to most general) |
|---|---|---|
| State kick | x+ = x− + d | impulse: z+ = z− + W_in d (the encoder Jacobian times d) |
| Current pulse / sustained current | dx/dt = F(x) + E_j a_j(t) | additive z+ = Az + Ba, with B = W_in E (E = known actuation geometry) |
| Temporal pattern | a(t) shaped | same additive model |
| Silencing unit j | x_j := 0 or F_j scaled by (1−a_j) | **bilinear** z+ = Az + Σ_j a_j N_j z (+ Ba); persistent → switched A |
| Weakening connection i←j | W_ij → (1−a)W_ij | rank-1 bilinear in x; in z bilinear plus a closure error |
| Parameter change (gain, threshold, τ) | θ_j → θ_j + a | LPV / switched A(p), B(p); bilinear to first order |
| Restart from arbitrary x₀ | chosen x₀ | excites the directions of the observability Gramian |

Consequences:

- Additive models are exact for kicks, currents and patterns (in the linear case). Multiplicative interventions need bilinear
  or switched/LPV terms.
- **Unseen targets** need B (and N) to be parametrised through the physical actuation geometry. A free column per ID does not
  transfer.

### 3.1 DMD with control (DMDc)

Proctor, Brunton, Kutz, SIAM J. Appl. Dyn. Syst. 15(1):142-161, 2016, arXiv:1409.6358. *Read: abstract.*
Model x_{k+1} = A x_k + B u_k `[std]`.

- **Unknown B.** Let Ω = [X; Υ] and G = [A B] = X′Ω⁺. Take a truncated SVD Ω ≈ ŨΣ̃Ṽᵀ (rank p) and split Ũ = [U₁; U₂]. A second
  SVD X′ ≈ ÛΣ̂V̂ᵀ (rank r) gives Ã = ÛᵀX′ṼΣ̃⁻¹U₁ᵀÛ and B̃ = ÛᵀX′ṼΣ̃⁻¹U₂ᵀ.
- **Known B.** A = (X′ − BΥ)X⁺.
- The abstract confirms that plain DMD on forced data gives corrupted modes, and that DMDc separates the intrinsic dynamics
  from actuation.
- **Identifiability.** [A B] is unique when Ω has full row rank. Under pure state feedback u = Kx, only A + BK is identified.
- **Failure modes.**
  - Measurement noise biases the eigenvalues toward 0.
  - A sustained constant input is collinear with an offset (add a bias column).
  - There is no hidden state unless delays are added.
- **Tuning.** POD rank r, input rank p, delay depth d and ridge λ, all scored on **held-out experiments**. Bag DMDc by
  bootstrapping whole *experiments*.
- Bagged optimised DMD (BOP-DMD: Askham & Kutz 2018; Sashidhar & Kutz, Phil. Trans. A 2022, arXiv:2107.10878) gives uncertainty
  for *autonomous* DMD. I found no control-input version `[unverified]`.
- **Software.** PyDMD `DMDc` and `BOPDMD` (MIT); PyKoopman `DMDc` (MIT).

### 3.2 Subspace identification: N4SID, MOESP, CVA, PBSID; PSID/IPSID

Sources:

- Van Overschee & De Moor, Automatica 30(1):75-93, 1994;
- Verhaegen & Dewilde, Int. J. Control 56(5), 1992;
- Larimore, IEEE CDC 1990;
- Chiuso, Automatica 43(6), 2007 (PBSID);
- Cox & Tóth, arXiv:2008.03347 (LPV subspace).

*Read: snippets/abstracts.*

Innovation form `[std]`: z_{k+1} = Az_k + Bu_k + Ke_k, y_k = Cz_k + Du_k + e_k.

**Algorithm.**

1. Build past/future block-Hankel matrices.
2. Compute the oblique projection O = Y_f /_{U_f} W_p.
3. Take a weighted SVD W₁OW₂ = USVᵀ.
   - MOESP and N4SID use W₁ = I.
   - CVA uses W₁ = (Y_fΠ_{U_f⊥}Y_fᵀ)^{−1/2}. Its singular values are the canonical correlations between the input-corrected
     future and the past, and the order is chosen by AIC.
4. Set Γ = W₁⁻¹U₁S₁^{1/2} and Ẑ = Γ⁺O.
5. Fit [A B; C D] by least squares.
6. K and the steady-state Kalman predictor give a **causal encoder** directly.

**Properties.**

- The latent is a Kalman state, so partial observation is handled. This is a major advantage over DMDc.
- **Identifiability.** Only up to similarity T. The invariants are eigenvalues, Markov parameters, the transfer function and
  the Hankel singular values.
- **Excitation.** Open-loop, persistently exciting inputs are required. If the design adapts within a run (closed loop), use
  PBSID/SSARX.
- **Multi-experiment data.** Build Hankel columns per experiment and never cross experiment boundaries.
- **Code.** `nfoursid` (MIT, small), SIPPY (N4SID/MOESP/CVA/PARSIM, LGPL per README).

**IPSID** (Vahidi, Sani, Shanechi, PNAS 121(7):e2212887121, 2024; *read: preprint methods*) and **PSID** (Sani et al.,
Nature Neuroscience 24:140-149, 2021; *snippet*).

- **Model.** x = [x⁽¹⁾; x⁽²⁾] with x_{k+1} = Ax + Bu + w, y = C_y x + D_y u + v, and a readout z = C_z x⁽¹⁾ + D_z u.
- **Stage 1** projects the *future readout* onto past observations and inputs, which gives the readout-relevant states first.
  **Stage 2** handles the residual.
- **Adaptation** `[synthesis]`: put a into u, use the post-intervention readout as the future, and choose n₁ by held-out
  intervention-effect error.
- **Licence.** PyPSID uses a USC academic, non-commercial licence (not OSI).

### 3.3 Controlled / input-output Koopman models

Sources:

- Williams, Kevrekidis, Rowley (EDMD), J. Nonlinear Sci. 2015;
- **Korda & Mezić**, Automatica 93:149-160, 2018, arXiv:1611.03537 (lift ψ(x), z+ = Az + Bu with u not lifted);
- Proctor, Brunton, Kutz, SIADS 17(1), 2018, arXiv:1602.07647;
- **Bruder, Fu, Vasudevan**, IEEE RA-L 2021, arXiv:2010.09961: every control-affine system has an (infinite) **bilinear**
  Koopman realisation, but not necessarily a linear one;
- **Nüske, Peitz, Philipp, Schaller, Worthmann**, J. Nonlinear Sci. 33:14, 2023, arXiv:2108.07102: bilinear EDMD via the
  generator, with finite-data error bounds O(M²/(δε²));
- **Shang, Haseli, Cortés, Zheng**, arXiv:2602.14537, 2026: an exact finite linear embedding z+ = Az + Bu exists **only if**
  the inputs enter a control-affine-preserved structure *and* the autonomous part has a finite Koopman-invariant subspace;
- Strässer et al., Annual Reviews in Control 2026, arXiv:2509.02839 (overview);
- Abudia et al., arXiv:2503.10891 (control Liouville operators);
- Han, Hao, Vaidya, CDC 2020, arXiv:2010.07546 (deep Koopman with control).

*Read: abstracts/snippets.*

**Estimators** `[std]`.

- Linear lift: [A B] = Ψ′[Ψ; U]⁺ (ridge), C = XΨ⁺.
- Bilinear lift: regress on [ψ(x); a; a⊗ψ(x)], i.e. z+ = Az + Σ_j a_j(N_j z + b_j).

**Conclusion.** **Bilinear is the principled minimum** for silencing and connection edits. Linear-in-input lifts are
systematically wrong under state-input coupling.

**Risks.** Keep a *out of* the encoder, otherwise it memorises the intervention ID. Large dictionaries give spurious
eigenvalues.

**Software.** PyKoopman (MIT: DMDc, EDMDc, NNDMD with control). I did not find bilinear EDMD there `[unverified]`; from scratch
it is one extra block of regressors.

### 3.4 SINDy with control (SINDYc) and control-affine sparse models

Sources:

- Brunton, Proctor, Kutz, IFAC-PapersOnLine 49(18):710-715, 2016, arXiv:1605.06682;
- Kaiser, Kutz, Brunton, Proc. R. Soc. A 474, 2018 (low-data MPC);
- Fasel, Kutz, Brunton, Brunton, Ensemble-SINDy, arXiv:2111.10992.

*Read: abstracts/snippets.*

**Model.** dz/dt = Ξᵀ Θ(z, a). The library contains polynomials in z and a and the cross terms z_i a_j, so it covers
**additive, bilinear, switched and parametric** read-ins.

**Assumptions.** SINDYc needs good low-dimensional coordinates (an encoder underneath), derivative estimates (or the weak
form), and designs that excite the cross terms.

**Uncertainty.** Ensemble-SINDy gives inclusion probabilities, which can serve as uncertainty estimates and an acquisition
signal.

**Scaling.** The library has ~(k+q)^d terms, which is practical for k ≲ 10.

**Software.** pysindy (MIT; STLSQ, SR3, MIOSR, SBR, ensembling).

### 3.5 Bilinear system identification

- Sattar, Oymak, Ozay, arXiv:2208.13915 (*abstract*): x_{t+1} = A₀x_t + Σ_k u_{t,k}A_k x_t + Bu_t + w_t with an observed state.
  From a single trajectory the sample complexity is of optimal order.
- Sattar, Jedra, Fazel, Dean, arXiv:2501.07652 (*abstract*): partially observed bilinear systems, via Markov-like parameters and
  a balanced realisation.
- **Implication** `[synthesis]`: random i.i.d. intervention amplitudes that preserve stability are a sufficient (not optimal)
  design for bilinear read-ins.

### 3.6 Persistent excitation, informativity, shortest experiments

- **Fundamental lemma** (Willems, Rapisarda, Markovsky, De Moor, Syst. Control Lett. 54(4):325-329, 2005; *abstract*): if u is
  persistently exciting of order L + n, the depth-L Hankel matrix of (u, y) spans all length-L trajectories.
- **Data-driven control** (De Persis & Tesi, IEEE TAC 65(3), 2020): closed loops designed directly from PE data.
- **Informativity** (van Waarde, Eising, Camlibel, Trentelman, arXiv:2302.10488): data can be informative for a property
  without identifying the system. This gives an abstention rule: abstain when the models consistent with the data disagree on
  the query.
- **Shortest experiment** (Camlibel, van Waarde, Rapisarda, arXiv:2407.12509, 2024; *abstract*): choosing inputs online gives
  identification experiments of minimum length. This is a linear active-design baseline.
- **Counting rule** `[synthesis]`:
  - k + q independent regressors [z; a] are needed.
  - Restarts excite the state part for free.
  - Each target and type must be applied at times that are not collinear with the state.
  - A **constant sustained current is PE of order 1 only**, so it is confounded with the bias.

### 3.7 Empirical Gramians, balanced truncation, observability

Sources:

- Moore, IEEE TAC 26(1), 1981 (balanced realisation);
- Lall, Marsden, Glavaški, Int. J. Robust Nonlinear Control 12(6), 2002 (empirical Gramians from simulated impulse and
  initial-condition responses);
- Rowley, Int. J. Bifurc. Chaos 15(3), 2005 (balanced POD);
- **Himpe, emgr**, Algorithms 11(7):91, 2018 and ACM TOMS 2023, arXiv:2209.03833. emgr provides seven Gramians, including
  sensitivity, identifiability and cross-identifiability Gramians. BSD-2, archived 2023;
- Krener & Ide, CDC 2009 (unobservability index 1/λ_min(W_o));
- Burohman et al., arXiv:2109.11685 (data-driven generalised balanced truncation).

*Read: abstracts/snippets.*

**Formulas** `[std]`.

- W_c = Σ_{j,m} (|S|c_m²)⁻¹ ∫(x^{jm} − x̄)(·)ᵀ dt, where x^{jm} is the response to input c_m e_j δ(t).
- W_o is built from output responses to initial conditions x₀ = x̄ + c_m e_i.

**Why this fits our simulator** `[synthesis]`. The simulator can restart and actuate at will, which is exactly what empirical
Gramians require. They give:

1. a **physics-side reference for k**: the Hankel singular values that are both reachable and observable, above the noise
   floor;
2. poorly reachable or poorly observable directions to target in active design;
3. a balanced linear encoder with read-in B_z = T_bal B_x and a Gramian lift.

The cost is O(N) runs; balanced POD and random directions reduce it.

### 3.8 Fisher information and sloppiness

Sources:

- Gutenkunst et al., PLoS Comput. Biol. 3(10):e189, 2007;
- Transtrum et al., J. Chem. Phys. 143:010901, 2015, arXiv:1501.07668;
- Bellman & Åström, Math. Biosci. 7, 1970.

*Read: abstracts.*

**Content.**

- Fisher-information spectra are spread over many decades, with a few stiff combinations. So focus on **predictions**, not
  microscopic parameters.
- For z+ = [A B]φ + w, the Fisher information is FIM = (Σφφᵀ) ⊗ Σ_w⁻¹ `[std]`, which gives D-optimal = max log det Σφφᵀ.
- For multi-step prediction, FIM = Σ_t J_tᵀΣ⁻¹J_t.

**Implication.** B columns for targets never actuated are **structurally unidentifiable** under a free parametrisation.

### 3.9 Non-asymptotic sample complexity

Sources:

- Simchowitz, Mania, Tu, Jordan, Recht, COLT 2018, arXiv:1802.08334: excitation, not mixing, drives accuracy;
- Oymak & Ozay, ACC 2019, arXiv:1806.05722: Ho-Kalman robustness;
- Tsiamis & Pappas, CDC 2019;
- **Tu, Frostig, Soltanolkotabi**, arXiv:2203.17193: m trajectories of length T in dimension n give error Θ(n/(mT)) when
  m ≥ n, i.e. i.i.d.-like rates from many short restarts;
- Ziemann et al., tutorial, CDC 2023, arXiv:2309.03873;
- He, Ziemann, Rojas, Qin, Hjalmarsson, arXiv:2501.16639: finite-sample bounds for MOESP/CVA.

*Read: abstracts.*

**Implications** `[synthesis]`.

- Budget in total simulated steps, with m ≥ k + q independent experiments.
- Rarely used targets get large errors, so report confidence intervals per target.
- The weakest Hankel singular values are lost first, so the **estimated k depends on the budget**. Report it with uncertainty.

### 3.10 Lift for linear models

A lift of this kind is published in De, Kiani, Mazzucato (see §9), using delay-embedded DMDc plus minimum-energy control.

    R_h = [A^{h−1}B, …, AB, B];  W_h = R_h R_hᵀ;  a* = R_hᵀ W_h⁺ Δz;  energy = Δzᵀ W_h⁺ Δz
    abstain if Δz ∉ range(R_h) or energy > budget
    distinct lifts: a_j = a* + (I − R_h⁺R_h) ξ_j, or disjoint target sets / different types
    bilinear: B(z) = [N_1 z + b_1, …]; one-step a = B(z)⁺ Δz; multi-step Gauss-Newton / iLQR

### 3.11 Method record, area 3

| Method | Interventions representable | Hidden state | Nonlin. | Ident. ambiguity | Unseen targets | Scaling / compute | Failure modes | Code (licence) | Scratch |
|---|---|---|---|---|---|---|---|---|---|
| DMDc (+delays, bagged) | additive | via delays | no | none given the POD basis | via structured B = ÛᵀE | SVD, ms-s, CPU; N ≤ 5000 trivial | noise bias, rank choice, collinear sustained inputs | PyDMD, PyKoopman (MIT) | trivial |
| Bilinear DMD / EDMD | + silencing, connection edits | via delays | low-mid | basis-fixed | structured N | CPU | more regressors need more excitation | from scratch | easy |
| N4SID / MOESP / CVA | additive | **yes (Kalman)** | no | similarity T | structured B via a read-in map | O(i²(p+m)²M), CPU s | closed-loop bias, order ambiguity, unstable A | nfoursid (MIT), SIPPY (LGPL) | moderate |
| PBSID / SSARX | additive; valid under adaptive design | yes | no | similarity | same | CPU | VARX order | none found in Python | moderate |
| IPSID | additive; readout-prioritised | yes | no | block similarity | same | CPU | linear, open loop | PyPSID (academic) | moderate |
| LPV subspace | parameter changes | yes | via scheduling | similarity T(p) | parametric | heavy | data hungry | not checked | hard |
| EDMDc (Korda-Mezić) | additive in the lift | via delays | mid | dictionary-fixed | no | O(MD²+D³) | spurious eigenvalues; wrong for state-input coupling | PyKoopman (MIT) | easy |
| Deep Koopman + control | additive or bilinear in latent | encoder | high | invertible linear | no | GPU helpful | a-in-encoder leakage | PyKoopman NNDMD (MIT) | moderate |
| SINDYc | additive, bilinear, switched, parametric | needs encoder | mid | sparsity-fixed | structured library | CPU s; k ≲ 10 | wrong coordinates, collinear library | pysindy (MIT) | easy |
| Empirical Gramians / BPOD | additive, plus sensitivity to parameters | reducer | empirical | balanced basis | per actuation | O(N) runs | cost at large N | emgr (BSD-2) | easy |

## 4. Neural latent dynamical models with inputs

### 4.1 How actions or interventions enter, and where history leaks

| Family (source; read level) | How a enters | Native kick / jump operator | Causal encoder by default | History-leak risk |
|---|---|---|---|---|
| Deep Kalman filter / DMM (Krishnan, Shalit, Sontag, arXiv:1511.05121; AAAI 2017 arXiv:1609.09869; *abstract*) | concatenated into the transition MLP | no | no (the structured variant is a smoother) | medium |
| RSSM: PlaNet / Dreamer (Hafner et al., ICML 2019 arXiv:1811.04551; ICLR 2020 arXiv:1912.01603; *abstract*) | concatenated into a GRU | no | yes (filtering posterior) | **high**: the deterministic h_t (200-600 units) is hidden memory, so k must count dim(h) + dim(s) |
| LFADS (arXiv:1608.06315; *abstract*) | inferred inputs (+ optional known inputs) | via inferred input | no (bidirectional) | **high** |
| iLQR-VAE (ICLR 2022; *full*) | f(z, u) with inferred or known u | inputs at t | no (smoother) | medium |
| Neural / latent ODE (Chen et al., NeurIPS 2018, arXiv:1806.07366; Rubanova et al., NeurIPS 2019, arXiv:1907.03907; *abstract*) | none natively; extension: concatenation or control-affine f(z) + G(z)a | add a jump map | no (the initial-condition encoder runs backwards over the whole sequence) | medium |
| Neural CDE (Kidger, Morrill, Foster, Lyons, NeurIPS 2020, arXiv:2005.08926; *abstract*) | **multiplicative**: dz = f_θ(z)dX, with a as a channel of X, so a step gives Δz ≈ f_θ(z)Δa | a step in X | only with causal (rectilinear) interpolation; natural cubic splines leak | medium |
| Latent SDE (Li, Wong, Chen, Duvenaud, AISTATS 2020, arXiv:2001.01328) / Neural Jump SDE (Jia & Benson, NeurIPS 2019, arXiv:1905.10403) (*abstract*) | drift; jumps w_θ(z₋, event) | **yes** (jump SDE) | encoder-dependent | medium |
| rSLDS (arXiv:1610.08466) | V_s a per mode | no | filter available | low |
| Low-rank RNN (Valente, Pillow, Ostojic, NeurIPS 2022; Pals et al., NeurIPS 2024, arXiv:2406.16749; *abstract*) | mechanistic, at the unit level | **derived** | n/a (state = x) | low |
| Predictive information bottleneck / CPC / VIB | predictor input | n/a | if designed | medium (if a enters the encoder) |
| PETS (Chua et al., NeurIPS 2018, arXiv:1805.12114) | concatenated | no | n/a | low |
| Action-conditioned JEPA (V-JEPA 2-AC, Assran et al., arXiv:2506.09985; *full, AC section*) | affine action tokens; **block-causal attention** | no | yes | medium |

### 4.2 Key methods for our purposes

- **Explicit jump read-in** `[synthesis, built on Neural Jump SDE and ODE-RNN]`. Represent a kick as z+ = z₋ + r_θ(z₋, a),
  applied at the intervention time as a module separate from f. It can then be inspected, regularised (sparsity, §2.2) and
  inverted (the lift).
  - Sustained currents enter as control-affine drift, dz/dt = f(z, u) + G(z)a (the Neural CDE form).
  - Parameter changes enter by **FiLM**, a feature-wise affine modulation of f's hidden layers (Perez et al., AAAI 2018,
    arXiv:1709.07871; *abstract*).
- **Low-rank RNNs** (LINT). The model is τ dx/dt = −x + M Nᵀ φ(x)/N + I u, with latent κ = Nᵀφ(x)/N.
  - A current pulse into unit i moves κ by ≈ n_i φ′(x_i)δ/N.
  - Silencing unit i removes its term from the sum.
  - Weakening a connection changes the corresponding entry of MNᵀ.
  - So this is the **only family whose read-in for silencing and parameter changes is derived rather than learned**. It
    therefore generalises to unseen *targets*, but only for observed units. Qian et al. (§9) warn that loadings of unobserved
    units are unconstrained.
  - Pals et al. find all fixed points of piecewise-linear low-rank RNNs at polynomial cost.
- **Past-future information bottleneck.**
  - Bialek, Nemenman, Tishby, Neural Comput. 13, 2001, arXiv:physics/0007070: predictive information.
  - Creutzig, Globerson, Tishby, Phys. Rev. E 79:041925, 2009 (*abstract*): for linear-Gaussian systems this reduces to a
    generalised eigenproblem, i.e. CCA or CVA, with **structural phase transitions** that each add a state dimension.
  - Deep VIB (Alemi et al., ICLR 2017, arXiv:1612.00410) bounds the compression term.
  - CPC / InfoNCE (van den Oord et al., arXiv:1807.03748) lower-bounds the prediction term. It saturates at log(batch size).
  - **Interventional version** `[synthesis]`: max I(z_t; x_{t+1:t+H} | u, a_{t:t+H}) − β I(z_t; x_{≤t}, u_{≤t}), with a
    entering only the predictor and never the encoder.
- **Ensembles.**
  - Deep ensembles (Lakshminarayanan, Pritzel, Blundell, NeurIPS 2017, arXiv:1612.01474): M networks with Gaussian heads.
    The mixture mean and variance give epistemic uncertainty as the variance of the member means.
  - PETS adds trajectory sampling (TS1 / TS∞) to propagate that uncertainty through rollouts.
  - Caveats: the members share blind spots for new intervention types, and latent spaces are not aligned across members, so
    compare them in readout or observation space.
- **Identifiability of action-conditioned latents.**
  - Mechanism sparsity (Lachapelle et al.).
  - Sparse input matrices (Zhang & Xie 2024).
  - **Variational Causal Dynamics** (Lei, Schölkopf, Posner, arXiv:2206.11131; *abstract*): a factorised transition model with
    a causal graph. An intervened environment changes a sparse set of mechanisms, which enables adaptation from a few samples
    to *unseen* intervened environments.
- **Observer-based recognition models for neural ODEs** (Buisson-Fenet, Morgenthaler, Trimpe, Di Meglio, arXiv:2205.12550;
  *abstract*). A causal encoder over a past window w, where w must be at least the observability index. Choose w by
  validation and report it (a long window with a large encoder risks hidden memory).
- **JEPA-style latent prediction** (LeCun 2022, OpenReview; *snippets*; V-JEPA 2-AC). Trained on a latent-only loss, a jointly
  trained encoder **collapses** to a constant z. Guard against this with an EMA/stop-gradient target, variance-covariance
  regularisation, or an observation/readout anchor.
- **CEBRA** (Schneider, Lee, Mathis, Nature 2023, arXiv:2204.00673; *abstract*). An encoder only, with no dynamics. It shows a
  pitfall: using the readout as an auxiliary label copies the readout into z, and using intervention labels bakes the
  intervention ID into z.

### 4.3 Method record, area 4

| Method | Assm. | Ident. | Interv. | Unseen | Nonlin. | Read-in interp. | Scaling | Compute | Failure | Relevance | Code | Scratch |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DKF / DMM | Markov latent, Gaussian | none | concatenation | interpolation only | high | implicit | linear in T | GPU/CPU | smoother leakage; posterior collapse | baseline | Pyro DMM tutorial (Apache-2.0) | simple |
| RSSM / Dreamer | observed actions | none | concatenation into GRU | poor | high | none | GPU | GPU | hidden memory h; objective mismatch | template (multi-step overshooting) | dreamerv3 (MIT `[unverified]`) | moderate |
| LFADS | trial structure | split input/dynamics not identified | inferred inputs | as a diagnostic | high | via inferred input | GPU | GPU | acausal; input absorbs dynamics | low (baseline, controller off) | lfads-torch `[licence unverified]` | moderate |
| Neural ODE + jump + control-affine | smooth f | none | f(z) + G(z)a, jump r(z, a), FiLM | structured r only | high | high (explicit modules) | solver cost | CPU for small k (RK4) | stiffness; trajectory crossings need larger k | **high** | torchdiffeq, diffrax | simple |
| Neural CDE | causal path interpolation | none | multiplicative f(z)dX | limited | universal | Δz = f(z)Δa | solver × k × d | GPU helpful | spline leakage | medium-high | torchcde, diffrax | moderate |
| Latent / jump SDE | Girsanov KL | none | drift and jumps | limited | high | jump function | slower than ODE | GPU | cost | medium | torchsde | moderate |
| Low-rank RNN | observed relevant units, rate model | up to R×R transform | mechanistic unit-level | **unseen targets (observed units)** | moderate | derived | N×R params | CPU | partial observation; rank chosen passively | high | LINT code `[unverified]` | simple |
| Predictive bottleneck (VIB / CPC / PF-IB) | MI estimators | invariant only | conditioning | if a is parametrised | any | depends on predictor | GPU/CPU | CPU ok | loose bounds; a in encoder | **high** (objective) | none canonical | simple |
| Deep ensembles / PETS | members independent | n/a | wrapper | under-dispersed out of domain | any | n/a | M × cost | parallel CPU | shared blind spots | **high** (UQ) | trivial | trivial |
| JEPA-AC | frozen or EMA encoder | none | affine tokens | limited | high | low | GPU | GPU | collapse | medium (objective idea) | V-JEPA 2 | simple (small MLP) |

## 5. Optimal and active experiment design for dynamical systems

Notation: θ = unknown model (parameters, class, or latent dimension k); ξ = design (target, kind, magnitude, timing, duration,
pattern, initial microstate, u(t)); y = response.

### 5.1 Bayesian optimal experimental design and EIG estimators

- **Reviews.** Chaloner & Verdinelli, Stat. Sci. 10(3), 1995 (*metadata*); Ryan, Drovandi, McGree, Pettitt, Int. Stat. Rev.
  84(1), 2016 (*abstract*); **Rainforth, Foster, Ivanova, Bickford Smith, "Modern Bayesian Experimental Design", Stat. Sci.
  39(1):100-114, 2024, arXiv:2302.14545 (*full*)**.
  - **EIG.** EIG(ξ) = E_{p(θ)p(y|θ,ξ)}[log p(y|θ,ξ) − log p(y|ξ)], i.e. the expected KL divergence from prior to posterior.
    It is invariant to reparametrising θ.
  - **Linear-Gaussian case** `[std]`. Bayesian D-optimality, log det(XᵀX + R), equals EIG up to constants. So Fisher
    D-optimal design is the correct cheap limit of EIG.
  - **Nested Monte Carlo (NMC)**: μ = (1/N)Σ_n log[p(y_n|θ_n,ξ) / ((1/M)Σ_m p(y_n|θ′_m,ξ))]. It is biased for finite M, and
    the MSE converges at about O(C^{−2/3}) in the cost C (Rainforth et al., ICML 2018, arXiv:1709.06181).
  - **Bounds.**
    - A variational marginal gives an *upper* bound.
    - A variational posterior gives a *lower* bound (Barber-Agakov).
    - **PCE** (prior contrastive estimation) is a lower bound: E[log p(y|θ₀,ξ) / ((M+1)⁻¹ Σ_{m=0}^M p(y|θ_m,ξ))].
      It is ≤ log(M+1).
    - ACE uses a proposal (Foster et al., NeurIPS 2019, arXiv:1903.05480; AISTATS 2020, arXiv:1911.00294).
  - **Failure modes stated in the review.**
    - Greedy design is myopic.
    - Under misspecification, sequential design can get **trapped**. Their example is a linear model that puts every design
      at the input extremes and never sees the interior nonlinearity. For us: a linearised latent model will push
      intervention magnitudes to saturation.
- **Amortised / policy-based design.**
  - DAD (Foster, Ivanova, Malik, Rainforth, ICML 2021, arXiv:2103.02438): a policy network over the history, trained on the
    sequential PCE bound. Decisions take milliseconds and are non-myopic. It needs a differentiable likelihood and
    conditionally independent experiments.
  - **iDAD** (Ivanova et al., NeurIPS 2021, arXiv:2111.02329): a likelihood-free version with InfoNCE/NWJ critics that handles
    dependent (time-series) experiments. It needs differentiable simulator samples or a surrogate.
  - Kleinegesse & Gutmann, arXiv:2105.04379: neural MI lower bounds used for parameter estimation, **model discrimination**
    and future prediction, in one framework.
- **Latent-state-aware EIG.** Pérez-Vieites, Iqbal, Särkkä, Baumann, arXiv:2511.04403 (2025/26; *abstract*). EIG estimators
  for partially observed nonlinear SSMs, using nested particle filters. They are heavy, so they fit only small k.

### 5.2 Disagreement-based acquisitions (cheap EIG surrogates)

- **Query by committee** (Seung, Opper, Sompolinsky, COLT 1992): query where the committee members disagree. In toy models
  this gives an exponential decay of the error.
- **BALD** (Houlsby, Huszár, Ghahramani, Lengyel, arXiv:1112.5745): I(y; θ | ξ, D) = H[y|ξ,D] − E_θ H[y|ξ,θ].
  - It needs a correct aleatoric (noise) model; otherwise it **picks noise**.
  - It targets *all* parameters, including irrelevant ones.
- **EPIG** (Bickford Smith, Kirsch, Farquhar, Gal, Foster, Rainforth, AISTATS 2023, arXiv:2304.08151):
  E_{x*~p*} I(y; y* | ξ, x*, D). This is information about predictions at *target* inputs. **Set p* to the held-out
  intervention families and the lift tests.**
- **Disagreement exploration** (Pathak, Gandhi, Gupta, ICML 2019, arXiv:1906.04161): the variance of ensemble next-state
  predictions. It is robust to stochastic "noisy-TV" dynamics.
- **MAX** (Shyam, Jaśkowski, Gomez, ICML 2019, arXiv:1810.12162): plans *in the learned models* to maximise the JS divergence
  between ensemble members. This is the template for planning intervention **sequences** without spending simulator calls.
- **OPAX** (Sukhija et al., arXiv:2306.12371): optimistic information gain with calibrated models, with GP guarantees.

### 5.3 Fisher-information / alphabetic input design for system identification

**Criteria** `[std]`. M(ξ) = Σ_t J_tᵀΣ⁻¹J_t, where J_t is the Jacobian of the predictions.

- D-optimal: max log det M.
- A-optimal: min tr M⁻¹.
- E-optimal: max λ_min(M).
- T/L-optimal: c ᵀM⁻¹c.

All of these are **local**, because they depend on the current estimate θ̂.

Sources:

- Mehra, IEEE TAC 19(6), 1974 (*metadata*): optimal power-constrained inputs are finite sums of sinusoids.
- Goodwin & Payne 1977 (*metadata*).
- Pronzato, Automatica 44, 2008, arXiv:0802.4381 (*abstract*): relations between design and control, and consistency under
  adaptive designs.
- Gevers, Eur. J. Control 11, 2005 (identification for control).
- Hjalmarsson, Automatica 41, 2005 and Eur. J. Control 15, 2009 (*metadata/summary*): **application-oriented, least-costly
  design**, i.e. make the model "as good as needed" for its intended use.
- **Manchester**, arXiv:1009.5614 (*abstract*): an SDP relaxation for **amplitude-constrained** (binary/bounded) input design
  that comes within 2/π of optimal. This is the right tool for on/off silencing sequences.
- Wilson, Schultz, Murphey, IEEE T-RO 30(6), 2014, arXiv:1709.03426: optimal control that maximises a Fisher-information norm
  for nonlinear systems. The resulting optimum is local.

### 5.4 Active system identification: theory

- **Wagenmaker & Jamieson**, COLT 2020, arXiv:2002.00495: an active design for linear systems with matching upper and lower
  bounds. **White-noise excitation provably cannot reach the optimal rate.**
- Wagenmaker, Simchowitz, Jamieson, ICML 2021, arXiv:2102.05214: **task-optimal exploration**, i.e. learn only what the task
  needs.
- **Mania, Jordan, Recht**, JMLR 23(32), 2022, arXiv:2006.10277: for x+ = A*φ(x, u) + w with a *known* feature map, plan
  trajectories that excite under-explored features, then refit. This fits **SINDYc / a fixed library** directly.
- Chatzikiriakos, Jamieson, Iannelli, AISTATS 2026, arXiv:2509.11907, "High effort, low gain": fundamental limits of active
  learning for finite hypothesis classes of LDS. This sets realistic expectations for k = 2 vs 3 discrimination.
- Blanke & Lelarge, arXiv:2204.06375: greedy one-step information-maximising control. A strong, cheap baseline.
- van Waarde, arXiv:2102.11193, and Camlibel, van Waarde, Rapisarda, arXiv:2407.12509: online designs that give the
  **shortest experiments**.
- Wagenmaker et al. 2024 (§1.2): the closest analogue, with ≤ 2x savings.
- Lewi, Butera, Paninski, Neural Comput. 21(3), 2009: sequential design with a Laplace posterior and rank-one updates, reduced
  to a 2-D search. Real-time.
- Shababo, Paige, Pakman, Paninski, NIPS 2013: online Bayesian design of multi-target stimulation for sparse input weights.
  Needs about half as many trials.

### 5.5 Active causal discovery (choosing intervention targets)

- Hauser & Bühlmann, IJAR 55(4), 2014, arXiv:1205.4174: a greedy single-target strategy that maximises the number of edges it
  can orient, and a minimum target set for full identifiability. It is for DAGs only; for recurrent systems, apply it to
  time-unrolled graphs.
- Kocaoglu, Dimakis, Vishwanath, ICML 2017, arXiv:1703.02645: minimum-cost intervention sets. Useful when intervention kinds
  cost different amounts.
- ABCD (Agrawal, Squires, Yang, Shanmugam, Uhler, AISTATS 2019): budgeted batch design for a *targeted* causal question, with
  submodular guarantees.
- Sussex, Uhler, Krause, NeurIPS 2021, arXiv:2105.14024: **multi-target** perturbation batches with greedy guarantees. Fits
  grouped or paired silencing.
- **CBED** (Tigas, Annadani, Jesson, Schölkopf, Gal, Bauer, NeurIPS 2022, arXiv:2203.02016): chooses both the intervention
  **target and its value**. Code: github.com/yannadani/cbed.

### 5.6 Model-discrimination designs (e.g. k = 2 vs k = 3)

- **Box & Hill**, Technometrics 9(1), 1967: sequentially maximise the expected entropy change of the model posterior.
- **T-optimality** (Atkinson & Fedorov, Biometrika 62, 1975; *metadata*):
  T(ξ) = min_{θ₂} Σ w(x)[η₁(x, θ₁) − η₂(x, θ₂)]². Choose the design where the best-fitting rival cannot mimic the assumed true
  model. For **nested** models (k = 2 inside k = 3), T is zero if the extra dimension can be switched off, so use the fitted,
  non-degenerate k = 3 model.
- Vanlier, Tiemann, Hilbers, van Riel, BMC Syst. Biol. 8:20, 2014: separate the posterior-predictive distributions of rival
  models (methods only).
- **Bania**, Entropy 21(4):351, 2019 (*full*): maximise I(Y; model | U) using the Kolchinsky-Tracey bound. For **two
  linear-Gaussian models** under an energy constraint, the optimal input is the **top eigenvector** of a matrix Q₁₂, which is a
  closed form. The error probability can locally *increase* with input energy.
- **Prediction deviation** (Letham, Letham, Rudin, Browne, Chaos 26, 2016, arXiv:1511.03395): find two models that both fit
  the data and disagree maximally, then design the experiment that resolves them (links to §10).
- **Designs for latent dimension.** I found **no paper** that designs interventions specifically to identify the latent
  dimension of a controlled SSM. The recipe in II.4 (A6) combines Box-Hill/T/Bania on per-k ensembles with E-optimal
  excitation of the weakest Gramian directions `[synthesis]`.

### 5.7 Temporal-pattern (excitation) design

Sources: Ljung 1999; Pintelon & Schoukens 2012 (*metadata*); Schoukens & Ljung, arXiv:1902.00683 (*abstract*). Standard facts
`[std]`:

| Signal | Strength | Weakness | Use for us |
|---|---|---|---|
| Impulse / kick | excites all modes; reads Δz directly | little energy per mode | read-in estimation |
| Step / sustained current | DC gains, slow modes | fast modes; collinear with an offset | stationary effects |
| PRBS (m-sequence) | near-white up to the clock frequency; binary; crest factor 1; periodic | fixed spectrum shape | on/off silencing sequences |
| Chirp | energy per band; shows nonlinear harmonics | long | frequency response |
| Random-odd multisine | user-set spectrum; **detects nonlinear distortion** (best linear approximation framework) | design effort | nonlinearity / class test |
| Paired pulses | short-term interaction and nonlinearity | narrow | superposition / facilitation test |

Fisher-optimal linear designs are sums of sinusoids (Mehra), so multisines are where D-optimal inputs live. The fixed-battery
baseline is {kicks per target, steps at 2-3 magnitudes, PRBS, log chirp, random-odd multisine, paired pulses at several
delays}, with total energy matched across signals.

### 5.8 Batch, budgeted and cost-aware design

- **BatchBALD** (Kirsch, van Amersfoort, Gal, NeurIPS 2019, arXiv:1906.08158): the joint mutual information is submodular, so
  greedy selection is within 1 − 1/e. Top-k BALD is redundant and can do worse than random.
- **Stochastic batch acquisition** (Kirsch et al., TMLR 2023, arXiv:2106.12059): sample the batch from softmax, power or
  soft-rank distributions of the single-point scores. It matches BatchBALD and BADGE at much lower cost. **Use this as the
  default batch rule.**
- BADGE (Ash et al., ICLR 2020, arXiv:1906.03671): k-means++ in gradient-embedding space.
- Kirsch & Gal, TMLR 2022, arXiv:2208.00549: Fisher-based selection approximates BALD/EPIG.
- Krause, Singh, Guestrin, JMLR 9, 2008: MI is submodular, so greedy log-det selection with lazy evaluation works.
- **Cost-aware acquisition.** EI per second (Snoek, Larochelle, Adams, NeurIPS 2012) and CArBO, which uses EI/c(x)^ν with ν
  cooled from 1 to 0 over the budget (Lee, Perrone, Archambeau, Seeger, arXiv:2003.10870). For us, simulation cost varies by a
  factor of 10³, so use information per CPU-second with cooling.
- **Curricula.** No dedicated methods source was read. The pattern `[synthesis]`:
  1. cheap single-target kicks and steps (read-in and linear core);
  2. paired and sequenced interventions (nonlinear interactions);
  3. probes of held-out families.

### 5.9 Fair comparison of design policies

- Mittal et al., arXiv:1912.05361, and **Munjal et al., CVPR 2022, arXiv:2002.09564**: under identical, well-tuned settings the
  gains of active learning over random are inconsistent, and run-to-run variance can overturn published conclusions.
- **Lüth, Bungert, Klein, Jaeger, NeurIPS 2023, arXiv:2301.10625 (*full, pitfalls*)** lists five pitfalls:
  - P1: narrow settings.
  - P2: a single starting budget.
  - P3: a single query size.
  - P4: an untuned or unreported classifier (gains misattributed to active learning).
  - P5: ignoring alternative training paradigms.
- **Agarwal et al., NeurIPS 2021, arXiv:2108.13264**: stratified bootstrap confidence intervals, the interquartile mean (IQM),
  performance profiles, and the probability of improvement (library: rliable).

The protocol derived from these is in II.4.

### 5.10 Method record, area 5 (acquisition methods)

| Method | Assumptions | Estimator / cost | Failure modes | Batch | Code |
|---|---|---|---|---|---|
| NMC EIG | explicit likelihood | N·M evaluations; O(C^{−2/3}) | infeasible on the microsimulator; use a surrogate | hard | from scratch |
| PCE / ACE | likelihood, differentiable in ξ | (M+1) evaluations per sample | saturates at log(M+1) | joint | Pyro `[unverified]` |
| DAD / iDAD | prior matches the truth; differentiable surrogate | large one-off training; ms per decision | prior misspecification | sequence | ae-foster/dad |
| QBC / disagreement / MAX | ensemble spread ≈ epistemic | M rollouts | collapsed ensembles; chases noise if heads are noisy | power sampling | trivial |
| BALD | calibrated aleatoric model | Gaussian moment-matched mixture | picks noise; irrelevant parameters | BatchBALD | BlackHC/BatchBALD |
| EPIG | a good target distribution p* | ensemble joint Gaussian MI | wrong p* | greedy | fbickfordsmith/epig |
| Fisher D/A/E | Laplace/local approximation, identifiable parameters | one Jacobian per design; rank-1 updates | local; extremes; latent rotation symmetry (use invariant or projected Fisher) | greedy log-det; SDP | from scratch |
| Box-Hill / T / Bania | candidate classes contain the truth approximately | refits (T) or eigenvector (Bania) | nested degeneracy; wrong candidate set | greedy | from scratch |
| CBED | Bayesian causal-discovery posterior | ensemble surrogate | DAG assumption | soft top-k | yannadani/cbed |
| Mania-style coverage | known feature map | min-eigenvalue of feature covariance | ignores noise; not task-targeted | greedy | from scratch |

## 6. State equivalence and closure

Every framework in this section defines a **state as an equivalence class of histories or microstates** that induce the same
future, given the future inputs or actions. They differ in three ways:

- exact (a partition) versus metric (a distance);
- whether inputs or actions are included;
- whether the criterion is the full future law, a recursive one-step law, or only reward/value.

Our target is the **input-output / action-conditioned** version: z is a sufficient statistic of (x_{≤t}, u_{≤t}) for the law of
the relevant future, under **any** future sequence of u and a.

### 6.1 Computational mechanics

- **Causal states** (Shalizi & Crutchfield, J. Stat. Phys. 104:817-879, 2001, arXiv:cond-mat/9907176; *abstract*).
  - **Definition.** Two pasts are equivalent iff P(future | past₁) = P(future | past₂).
  - **Properties.** Causal states are prescient, minimal (least statistical complexity among prescient rivals), unique up to
    relabelling, and Markov with unifilar updates.
  - **For us.** "Minimal + prescient" means choosing the smallest k that preserves the interventional predictions.
    Uniqueness up to relabelling justifies evaluating z only up to invertible maps.
- **ε-transducers** (Barnett & Crutchfield, J. Stat. Phys. 161:404-451, 2015, arXiv:1412.2690; *abstract*).
  - **Definition.** Causal states of input-output processes: two joint input-output pasts are equivalent iff they give the
    same law of future outputs **for every future input sequence** `[standard definition, wording unverified]`.
  - **For us.** This is the formal definition of our causal state when a is an input. The read-in is the transducer
    transition on an intervention symbol.
  - **Practical consequence.** "For every future input" must be approximated by a **probe set** of future interventions.
    Choosing that set is itself a design problem.
- **CSSR** (Shalizi, Shalizi, Crutchfield, arXiv:cs/0210025; *abstract*). A reconstruction algorithm: hypothesis tests on
  next-symbol distributions, with a state split whenever a test rejects.
  - **For us.** This is the template for a statistical **split test** within a latent cell (see §10).
  - **Limits.** It needs discrete symbols, and the number of histories grows exponentially with history length.

### 6.2 Predictive state representations (PSRs)

Littman, Sutton, Singh, NIPS 2001 (*abstract summary*); Boots, Siddiqi, Gordon, IJRR 30(7), 2011, arXiv:0912.2385 (spectral,
closed form; *search summary*); Boots, Gretton, Gordon, UAI 2013, arXiv:1309.6819 (Hilbert-space embeddings; *title*).

- **Definition.** The state is a vector of predictions for "tests" (future action-observation sequences).
- **Linear PSRs.** The number of core tests is at most the size of the minimal POMDP. The update is linear per
  action-observation operator.
- **Dimension rule.** k is the numerical rank of the history × (future under probe interventions) matrix. This is a dimension
  chosen for **interventional prediction**.
- **Identifiability.** The state is identified up to an invertible linear map.
- **Relation to subspace ID.** Spectral PSR learning is closely related to subspace identification with inputs (§3.2).
- **Unseen interventions.** Not supported unless the operators are parametrised by an intervention descriptor.

### 6.3 Bisimulation and its metrics

- **Bisimulation** (Givan, Dean, Greig, Artificial Intelligence 147, 2003; *bibliographic only*). Related states have the same
  reward for every action and the same probability of moving into each class. The coarsest bisimulation is the minimal model.
  - **For us.** The recursive **one-step** form makes equivalence locally testable. Equal-z microstates must have (i) the same
    immediate readout law and (ii) the same one-step distribution over z-cells under each intervention. Induction then gives
    multi-step equivalence.
- **Bisimulation metrics** (Ferns, Panangaden, Precup, UAI 2004, arXiv:1207.4114; *abstract*).
  - **Definition.** d(s, s′) = max_a (c_R|R(s,a) − R(s′,a)| + c_T W_d(P(·|s,a), P(·|s′,a))). The metric is a fixed point,
    and d = 0 iff the states are bisimilar (constants `[unverified]`).
  - MICo (Castro et al., NeurIPS 2021, arXiv:2106.08229) is a sample-based version.
- **DBC** (Zhang, McAllister, Calandra, Gal, Levine, ICLR 2021, arXiv:2006.10742; *abstract*). Train the encoder so that
  ‖z_i − z_j‖₁ matches |r_i − r_j| + γ W₂ between Gaussian latent transitions.
  - Collapse has been reported when reward differences are small `[unverified]`.
  - Code: facebookresearch/deep_bisim4control (licence believed to be CC-BY-NC `[unverified]`).
- **Interventional bisimulation distance** `[synthesis]`: replace reward by the readout and actions by interventions:
  d(x₁, x₂) = max_{a∈probe set}(|E[y|x₁,a] − E[y|x₂,a]| + γ W(P(z′|x₁,a), P(z′|x₂,a))).
  Test that the encoder distance tracks this distance (upper-bounds it, up to a constant).

### 6.4 Approximate abstractions and information states

- Li, Walsh, Littman, ISAIM 2006, and Abel, Hershkowitz, Littman, ICML 2016 (*search summaries*).
  - **Exact abstraction hierarchy.** Model-irrelevance (= bisimulation) is finer than Q^π-irrelevance, which is finer than
    Q*-, a*- and π*-irrelevance.
  - **Approximate versions.** Value loss is linear in ε.
  - **For us.** Model-irrelevance is our target. Readout-specific closure is a coarser notion.
- **Approximate information state (AIS)** (Subramanian, Sinha, Seraj, Mahajan, JMLR 23(12), 2022; *abstract*).
  - **(P1) Readout sufficiency** up to ε.
  - **(P2) Self-prediction** P(z_{t+1} | history, a) ≈ P(z_{t+1} | z_t, a), up to δ in an IPM (Wasserstein, MMD or TV).
  - Given (P1) and (P2), approximate dynamic programming has a bounded value loss.
  - **This is the most direct loss-level statement of our closure terms.** δ is exactly "how much the residual microstate
    adds", and the local terms bound the multi-step error.
  - **Caveat.** The guarantees are about value, which is task-specific. Use vector-valued "rewards" (future readouts) to get
    broader closure.
- **Informational, causal and computational closure** (Rosas, Geiger, Luppi, Seth, Polani, Gastpar, Mediano,
  arXiv:2402.09090; *abstract*).
  - **Informational closure.** I(Z_future; X_past | Z_past) = 0.
  - Causal closure is the interventional version. Computational closure means the macro ε-machine is a coarse-graining of
    the micro ε-machine.
  - **Our closure statistic** `[synthesis]`: C = I(Future; X_t, identity of a | Z_t, R(Z_t, a), U).

### 6.5 Tests of Markov and interventional closure

- **Markov-property test** (Shi, Wan, Song, Lu, Leng, arXiv:2002.01751, ICML 2020 `[venue unverified]`; *abstract*):
  forward-backward learning with conditional characteristic functions, used to select the order of an MDP/POMDP.
  - **For us.** Test whether (z_t, a_t) is Markov, and how much encoder history is needed.
- **Hardness of CI testing** (Shah & Peters, Ann. Stat. 48(3), 2020, arXiv:1804.07203; *abstract*).
  - **No free lunch.** With continuous conditioning, no CI test is both valid and powerful against all alternatives.
  - **GCM** (generalised covariance measure) uses normalised residual covariances from ML regressions. It is valid when the
    regressions are accurate enough.
- **Other CI tests.**
  - KCI (Zhang, Peters, Janzing, Schölkopf, UAI 2011, arXiv:1202.3775): cubic cost in n.
  - kNN-CMI with a local permutation null (Runge, AISTATS 2018, arXiv:1709.01447; Tigramite).
  - Signature-kernel CI tests for path-valued processes (Manten et al., arXiv:2402.18477).
  - Transfer entropy (Schreiber, PRL 85, 2000).
- **Practical closure test** `[synthesis]`:
  - Measure the **held-out predictive gain** from adding residual microstate features and the intervention identity to a
    predictor built on (z, R(z, a), u). Report it in nats, or as a fraction of explained variance, with a bootstrap CI over
    experiments.
  - Calibrate it against a **simulator-generated null**: pairs constructed with equal z.
  - Use the same predictor capacity with and without the extra inputs, so that power and leakage are matched.

### 6.6 Mediation analysis (static and dynamic)

Pearl, UAI 2001, arXiv:1301.2300; Imai, Keele, Tingley, Psychol. Methods 15(4), 2010; Luo, Shi, Wang, Wu, Li, arXiv:2310.16203
(dynamic, multivariate, RL framework); continuous-time mediation, arXiv:2403.11017 (*snippet*).

- **Effects.**
  - NDE = E[Y(a, M(a₀))] − E[Y(a₀, M(a₀))].
  - NIE = E[Y(a, M(a))] − E[Y(a, M(a₀))].
  - CDE(m) = E[Y(a, m)] − E[Y(a₀, m)].
- **Identification** in observational data needs **sequential ignorability**, which is untestable and cross-world, plus
  positivity and consistency. The dynamic versions also assume Markov structure and linearity.
- **In our simulator** `[synthesis]`, cross-world quantities are *computable*: use the same microstate with common random
  numbers. Two tests follow:
  - **Controlled direct effect test.** Apply a, then use a lift to reset z to its no-intervention value z(a₀), then compare
    the futures. "z fully mediates a" means CDE ≈ 0 (≈ NDE under a deterministic mediator reset).
  - **Natural indirect effect.** Implement a₀ with z set to z(a), using a lift from the a₀ state.
  - Mediation testing is therefore **coupled to the lift** (§7). Without an exact reset of z, fall back to closure tests (6.5).

### 6.7 Method record, area 6

| Method | Assm. | What it defines / tests | Interventions | Dimension rule | Scaling | Failure modes | Code | Scratch |
|---|---|---|---|---|---|---|---|---|
| Causal states / ε-transducer | stationarity; discrete (theory) | exact predictive equivalence with inputs | input symbols | minimal statistical complexity | exponential (exact) | untestable exactly in continuous spaces | CMPy `[unverified]` | n/a |
| CSSR | discrete, finite memory | split test | via inputs | number of states | exponential in history | discretisation | yes `[unverified]` | moderate |
| PSR (spectral) | linear in features | predictive state up to linear map | action operators | Hankel rank | SVD, CPU | needs rich exploration | from scratch | simple |
| Bisimulation / metrics / DBC | Markov, observed state | (metric) equivalence under all actions | yes | none | OT per pair; DBC scales | collapse; Gaussian W₂ | deep_bisim4control | simple |
| AIS | IPM estimable | ε/δ closure losses with bounds | yes | none | MMD cost | task-specific bounds | from scratch | simple |
| Markov test (Shi et al.) | ML regressions | Markov / order | yes | history length | moderate | power | `[unverified]` | moderate |
| GCM / KCI / CMI tests | regression or kernel accuracy | conditional independence | n/a | n/a | KCI O(n³) | no uniformly valid test | GeneralisedCovarianceMeasure (R), causal-learn, Tigramite | simple (GCM) |
| Mediation (natural, controlled) | ignorability (not needed in the simulator) | direct / indirect effects | yes | n/a | simulations | needs a lift to set z | R `mediation` | simple in the simulator |

## 7. Inverse problems for latent interventions ("lifting")

### 7.1 Minimum-energy control and controllability metrics

**Linear theory** `[std]` (Kalman-era textbook material, not re-read). For x+ = Ax + Bu:

- C_T = [B, AB, …, A^{T−1}B] and W_T = C_T C_Tᵀ.
- The minimum-energy input is u* = C_Tᵀ W_T⁻¹ δ, with E_min = δᵀW_T⁻¹δ, where δ = x_T − A^T x₀.
- Input weights enter through B W_u^{−1/2}.

**Metrics** (Pasqualetti, Zampieri, Bullo, IEEE TCNS 1(1):40-52, 2014, arXiv:1308.1201; *abstract*): tr W⁻¹ (average energy),
λ_min(W) (worst-case energy is 1/λ_min), log det W, and tr W.

- For many networks, the energy grows exponentially with network size when the number of drivers is fixed.
- tr W is modular, so greedy selection of drivers is exact for it.
- Summers, Cortesi, Lygeros (IEEE TCNS 3(1), 2016, arXiv:1404.7665) show that several Gramian metrics are submodular. A
  published correction exists, and metrics involving W⁻¹ or λ_min are not submodular in general `[unverified which exactly]`.
  Treat greedy selection as a heuristic for those.
- Yan et al. (PRL 108:218703, 2012; Nature Physics 11, 2015, arXiv:1503.01160; *metadata/title only*): control energy is
  dominated by a few hard directions `[unverified detail]`.

**Structural controllability** (Liu, Slotine, Barabási, Nature 473:167-173, 2011; *abstract*): the number of driver nodes is
N − |maximum matching|. It is binary and says nothing about energy. Self-loops make it nearly trivial `[unverified: Cowan et al.
2012]`. For us it is only a sanity check; compute rank [B, AB, …] numerically on the learned (A_z, B_a) instead.

**Implication** `[synthesis]`: lifts will fail, or need huge amplitudes, along poorly reachable latent directions. Use
λ_min(W) as a **lift-abstention** criterion and as a design heuristic that favours targets maximising log det W of the current
model.

### 7.2 Constrained and nonlinear lifts

- **Sparse / L1 lifts.** Maximum-hands-off control equals the L1-optimal (minimum-fuel) control, and the solution is
  bang-off-bang (Nagahara, Quevedo, Nešić, arXiv:1307.8232; *abstract*). Group-L1 over units selects few targets.
- **iLQR** (Li & Todorov, ICINCO 2004; *abstract*): iterated LQR around a nominal trajectory, O(T(k³ + k²m)) per iteration,
  local optima. Box constraints via control-limited DDP (Tassa, Mansard, Todorov 2014 `[unverified]`).
- **MPC / QP.** With a linear latent model and box constraints, the lift is a QP or LP solved in milliseconds with OSQP or cvxpy
  (Apache-2.0).
- **Embed to Control** (Watter, Springenberg, Boedecker, Riedmiller, NeurIPS 2015, arXiv:1506.07365; *abstract*).
  - **Method.** A latent model that is locally linear, z+ = A(z)z + B(z)u + o(z), trained so that iLQR works in latent space.
  - **Lesson.** The control objective shapes the representation.
  - **Known failure** (follow-ups `[unverified]`). The optimiser exploits model error: the latent is controllable in the model,
    but the real system does not follow. So penalise **ensemble disagreement** during the lift and check it against the
    simulator.
- **Model-based stimulation design** (methods only).
  - Bolus, Willats, Rozell, Stanley, J. Neural Eng. 18(3):036006, 2021 (*abstract*): low-order LDS identification followed by
    LQR with integral action and a Kalman filter. Feedback corrects model error, so an **open-loop** lift is the harder test of
    the read-in.
  - Yang, Qiao, Sani, …, Shanechi, Nat. Biomed. Eng. 2021 (*abstract*): input-output SSMs driven by time-varying stimulation
    parameters, with an input nonlinearity that is analogous to a parametrised read-in `[unverified details]`.
  - Fehrman & Meliza, arXiv:2406.14801 / Neural Comput. 37(12), 2025 (*abstract*): MPC on a learned latent model of a
    simulated spiking network. It beats PID under partial observation.
  - **De, Kiani, Mazzucato**, Curr. Opin. Behav. Sci. 67:101632, 2026, arXiv:2505.24790 (*full*): an end-to-end lift.
    1. Rank stimulation sites by a nonlinear directed-influence measure ("causal flow", from delay-embedding
       cross-reconstruction).
    2. Fit delay-coordinate DMDc (a Koopman-style model).
    3. Solve minimum-energy linear optimal control.
    - Stated limits: predicted and evoked trajectories diverge beyond short horizons; there is a trade-off between prediction
      and control; the tests use recurrent network simulations only.

### 7.3 Lift formulas (for implementation)

The current latent is z; the target change is Δz*. The feasible set 𝒜 covers box bounds, non-negativity, discrete masks and a
maximum number of targets. W is a positive-definite physical cost.

**(L) Linear read-in R(z, a) = z + B(z) a.** The weighted minimum-norm solution is

    a* = W⁻¹Bᵀ(BW⁻¹Bᵀ)⁻¹Δz*,   E = Δz*ᵀ(BW⁻¹Bᵀ)⁻¹Δz*

It is feasible iff Δz* ∈ range(B).

- **Tikhonov version:** a*_λ = (BᵀΣ⁻¹B + λW)⁻¹BᵀΣ⁻¹Δz*.
- **Multi-step:** replace B by the h-step reachability matrix (the Gramian form).
- **Constraints:** solve the convex program min ‖a‖²_W + γ‖a‖₁ + ρ Σ_g ‖a_g‖₂ s.t. ‖Ba − Δz*‖_{Σ⁻¹} ≤ ε, a ∈ 𝒜.

**(N) Nonlinear read-in, continuous a.** Minimise

    L(a) = ‖R(z,a) − z − Δz*‖²_{Σ⁻¹} + λ‖a‖²_W + μ·U(z,a),   U = tr Cov_m[R_m(z,a)]   (ensemble disagreement)

- Projected / proximal gradient: a ← Π_𝒜(S_{ηγ}(a − η∇L)).
- Levenberg-Marquardt: a ← Π_𝒜(a − (JᵀΣ⁻¹J + λW + νI)⁻¹(JᵀΣ⁻¹res + λWa)).
- Use multiple starts, and keep the **distinct** local optima; they are needed for the multiple-lift test.

**(D) Discrete or mixed a.** Use CMA-ES (Hansen, arXiv:1604.00772; pycma) on a continuous encoding, or enumerate small discrete
sets and solve the continuous part for each. Run 10²-10⁴ evaluations of the **model**, then **one simulator verification per
candidate**.

**(A) Abstain** when any of the following holds:

- the residual exceeds a χ² quantile;
- the energy exceeds the budget;
- U(z, a*) exceeds the conformally calibrated disagreement threshold (§8);
- the realised Δz in the simulator misses the target by more than the conformal radius.

### 7.4 Testing multiple realisations (multiple-lift consistency)

**Theory.** Exact transformations (Rubenstein et al.): interventions with the same ω-image must have equal pushed-forward laws.
Strong τ-abstraction (Beckers & Halpern): the test must cover the whole allowed class. Interchange interventions (Geiger et al.).
Validation evidence: Méloux, Pimentel, Portet, Peyrard, arXiv:2607.00267, 2026 (*abstract*). On ten simulated systems with
ground-truth abstractions, **only interventional (causal) metrics plus a faithfulness test on unmapped variables** separated
valid from invalid abstractions; about 30 sampled interventions were enough for convergence.

**Protocol** `[synthesis]`:

1. **Generate distinct lifts.** Use disjoint target sets, different kinds (kick vs current vs parameter change), or a repulsion
   term. Require a pairwise physical distance ≥ d_min.
2. **Verify realisation.** Compute the realised Δz_i = φ(post) − φ(pre). Record the fraction within ε as **lift success**.
3. **Run matched futures.** Start from the **same pre-intervention microstate** with R paired seeds, the same future u and the
   same future interventions. Record the futures Y_i, and the no-intervention control Y₀.
4. **Compute the statistic.** D_between = mean_{i<j} d(Ȳ_i, Ȳ_j) (normalised RMSE or energy distance / MMD). Get the null by
   permuting lift labels. Report **κ = D_between / mean_i‖Ȳ_i − Ȳ₀‖**, where κ ≈ 0 means consistent and κ ≈ 1 means the
   identity of the lift matters as much as its effect.
5. **Confirm equivalence.** Use **TOST** with a pre-registered margin (for example 10-20 % of the effect). Never read failure to
   reject a difference as equivalence.
6. **Guard against weak effects.** First require ‖Ȳ_i − Ȳ₀‖ to be significantly above the noise floor.
7. **Diagnose bias.** A lift-specific bias that is consistent across replicates is a counterexample (§10). It points to an
   unmodelled latent direction.

### 7.5 Method record, area 7

| Method | Assm. | Cost | Failure modes | Relevance | Code | Scratch |
|---|---|---|---|---|---|---|
| Gramian min-energy | linear | one pinv | ill-conditioning; ignores constraints | lift baseline + abstention | python-control (BSD-3), scipy | trivial |
| Constrained QP / L1 / group-L1 | linear read-in | ms | discrete choices need relaxation | sparse lifts | cvxpy, OSQP (Apache-2.0) | simple |
| iLQR / DDP | differentiable f | O(T k³) per iteration | local optima; model exploitation | multi-step lifts | trajax, crocoddyl `[unverified licences]` | moderate |
| CMA-ES / BO on model, verify on simulator | black-box | 10²-10⁴ model evaluations | noise; needs verification | discrete lifts | pycma, nevergrad (MIT) | simple |
| Uncertainty-penalised lift | ensemble | M × cost | under-dispersed ensembles | **anti-exploitation** | trivial | simple |
| Multiple-lift consistency test | simulator restarts | R × (#lifts) runs | equivalence by weakness | **core test** | none | simple |

## 8. Uncertainty, calibration and abstention

### 8.1 Selective prediction

- Chow, IEEE TIT 16(1), 1970: the Bayes reject rule, i.e. reject if max P < 1 − t.
- El-Yaniv & Wiener, JMLR 11, 2010: coverage φ = E[g] and selective risk R = E[ℓg]/φ, plotted as a **risk-coverage curve**.
- Geifman & El-Yaniv, NeurIPS 2017, arXiv:1705.08500: **SGR** (selection with guaranteed risk). Binary-search the threshold so
  that the selective risk plus a binomial-tail upper confidence bound is ≤ r*, with probability 1 − δ (algorithm details
  `[unverified]`).
- Formulas for our use:
  - AURC = ∫R(c)dc.
  - E-AURC = AURC − AURC_oracle `[unverified source]`.
  - **Confident-wrong rate:** CW = P(ℓ > τ_err and accepted), reported both conditionally and unconditionally.
  - Compute bootstrap CIs over **experiments**, not time bins.

### 8.2 Conformal prediction for trajectories

Angelopoulos & Bates, arXiv:2107.07511 (*abstract*).

**Split conformal.** Set q = the ⌈(n+1)(1−α)⌉/n quantile of the scores. Then P(Y ∈ C) ≥ 1 − α under exchangeability.

**Time-series and trajectory methods.**

- **CF-RNN** (Stankevičiūtė, Alaa, van der Schaar, NeurIPS 2021; *abstract*): calibrate on **independent sequences** and use a
  Bonferroni correction over horizons `[details unverified]`.
- Cleaveland, Lee, Pappas, Lindemann, AAAI 2024, arXiv:2304.01075: a parametrised maximum over horizons, with weights optimised
  by LP. Less conservative than Bonferroni.
- CopulaCPTS (Sun & Yu, ICLR 2024, arXiv:2212.03281).
- EnbPI (Xu & Xie, ICML 2021): for single long series.

**Recipe for our simulator** `[synthesis]`:

- **Unit of exchangeability.** One simulator experiment (restart, u, a, seed). Calibration experiments must be drawn from the
  same **design distribution** as the test experiments, and never from actively chosen ones.
- **Score.** s_e = max_h e_h/D_h, where D_h is a per-horizon scale. This gives a joint band y_{t+h} ∈ ŷ ± q·D_h for all h with
  no Bonferroni correction.
- **Conformalise effects directly** from paired runs with common random numbers: s_e = max_h |Δy − Δŷ|/D_h.
- **Mondrian (per-family) calibration.** It needs ≥ ~1/α calibration experiments per family (19 at α = 0.05).
- **Report** joint coverage with a Clopper-Pearson CI, band width, and per-family coverage.

**Adaptive designs break exchangeability.**

- **ACI** (Gibbs & Candès, NeurIPS 2021, arXiv:2106.00170; *key equations read*) updates α_{t+1} = α_t + γ(α − err_t) and
  guarantees |T⁻¹Σerr_t − α| ≤ (max{α₁, 1−α₁} + γ)/(γT) for **any** sequence.
- **Weighted conformal** (Barber, Candès, Ramdas, Tibshirani, Ann. Stat. 51(2), 2023, arXiv:2202.13415; *metadata*): weight
  calibration experiments by their similarity to the query. The coverage gap is bounded by Σ w̃_i d_TV.

### 8.3 Ensembles and out-of-domain detection

- **Deep ensembles** (M = 5) and **PETS** (§4).
- Ovadia et al., NeurIPS 2019 (*abstract*): calibration degrades under dataset shift for every method, and ensembles are the
  most robust. Held-out intervention families *are* a shift, so expect under-coverage and measure it.
- **SODA-MPC** (Contreras, Shorinwa, Schwager, arXiv:2406.02436; *abstract*): conformally calibrate the ensemble disagreement,
  with p(x) = (1 + #{U_i ≥ U(x)})/(n + 1), and abstain if p < α_OOD.

### 8.4 Calibration metrics and proper scores

- **Brier score** (Brier 1950 `[background]`): BS = mean (p − o)², with the Murphy decomposition.
- **ECE** (Guo, Pleiss, Sun, Weinberger, ICML 2017, arXiv:1706.04599): depends on binning, so also report reliability diagrams.
- **Proper scores** (Gneiting & Raftery, JASA 102, 2007; *metadata*):
  - CRPS = E|X − y| − ½E|X − X′|.
  - **Energy score** for trajectories: ES = E‖X − y‖ − ½E‖X − X′‖.
  - Interval score IS = (u − l) + (2/α)(l − y)1{y<l} + (2/α)(y − u)1{y>u}.
- **Regression calibration** (Kuleshov, Fenner, Ermon, ICML 2018): PIT histograms and isotonic recalibration. This checks
  marginal calibration only, so check calibration per family separately.

### 8.5 Detectability of effects: the noise floor and equivalence testing

**TOST** (Lakens, SPPS 8(4), 2017; *abstract*; Schuirmann 1987 `[background]`). Fix the margin [−Δ_L, Δ_U] before the
experiment.

    t₁ = (d̂ + Δ_L)/se ≥ t_{1−α,ν}   and   t₂ = (d̂ − Δ_U)/se ≤ −t_{1−α,ν}   ⇔   (1−2α) CI ⊂ (−Δ_L, Δ_U)

For trajectories, apply the intersection-union test over horizons, or a bootstrap CI on the RMS effect.

**Four-way classification of each intervention:**

- a real effect;
- a negligible effect;
- real but smaller than the SESOI (smallest effect size of interest);
- **inconclusive**, in which case abstain or run more replicates.

**MDE with paired replicates** (common random numbers): MDE = (z_{1−α/2} + z_{1−β})σ_d/√R.

- **Rule:** never classify an effect as "no effect" when MDE > SESOI.
- Normalise the prediction error of near-zero effects by the **noise floor**, σ_d/√R, never by the effect itself.
- Software: statsmodels `ttost_paired` (BSD-3); TOSTER (R).

### 8.6 Method record, area 8

| Method | Assm. | Guarantee | Cost | Failure modes | Code | Scratch |
|---|---|---|---|---|---|---|
| Split conformal (trajectory sup-score) | exchangeable experiments | marginal joint coverage ≥ 1 − α | one quantile | adaptive designs; family shift | MAPIE, crepes `[licences unverified]` | trivial |
| Mondrian conformal | ≥ 1/α per family | per-family coverage | same | small families | same | trivial |
| ACI | none | long-run frequency bound | O(1) per step | not conditional | from scratch | trivial |
| Weighted conformal | known weights | gap ≤ Σw̃ d_TV | same | weight choice | from scratch | simple |
| Deep ensembles / PETS | independent members | none (heuristic) | M × training | shared blind spots | trivial | trivial |
| Conformalised disagreement (OOD) | exchangeable calibration | false-alarm rate | small | shift of the calibration set | from scratch | simple |
| SGR / risk-coverage | i.i.d. calibration | selective risk ≤ r* w.p. 1 − δ | binary search | score quality | selective_deep_learning | simple |
| TOST / MDE | approximately normal paired differences | equivalence at level α | trivial | margin chosen post hoc | statsmodels, TOSTER | trivial |
| Proper scores (CRPS / ES / IS), PIT | samples | propriety | cheap | marginal only | properscoring, scoringrules | trivial |

## 9. Perturbation-based validation of dynamical models (methodology)

### 9.1 What perturbations reveal that passive data cannot

- **Twin models** (Sourmpis, Petersen, Gerstner, Bellec, eLife 2025, doi:10.7554/eLife.106827; *full, methods content only*).
  - **Twin-model argument.** A feedforward and a recurrent reference network have *identical* trial-averaged statistics without
    perturbation. The paper states that even with infinitely many trials, passive data cannot tell them apart. Inactivating a
    component does.
  - **Perturbations in the fitted models** were transient current injections into targeted subpopulations.
  - **Held-out validation.** Perturbation data were *withheld* from training and used only as a test of causal validity.
  - **Structure matters more than fit.** Generic RNNs generalised poorly to perturbations; structural inductive biases
    (sign-constrained excitation/inhibition, local inhibition) mattered most.
  - **Metrics.** The error in the perturbation-induced readout change, |Δp_data − Δp_model|, and a trial-matching distance.
  - **Cheap read-in estimate.** The first-order relation ΔY ≈ Σ ∂Y/∂u_{i,t} Δu_{i,t} makes the model's **input Jacobian** a
    read-in estimate and a target-selection heuristic.
- **Model mismatch** (Das & Fiete, Nat. Neurosci. 23:1286-1296, 2020; *abstract*). Even with unlimited data from every unit,
  mismatched inference models infer connections between correlated but unconnected units, especially in strongly recurrent
  regimes. Single-unit perturbations break this ambiguity.
- **Residual dynamics** (Galgali, Sahani, Mante, Nat. Neurosci. 26:326-338, 2023; *abstract + code README*; MATLAB, MIT). Fit
  linear dynamics to trial-by-trial residuals around the condition mean, in a low-dimensional subspace. Pronounced trajectories
  can be input-driven while the local recurrent dynamics are stable. This is the non-interventional control for Jacobian
  estimates; our simulator can measure Jacobians directly by kicking a restarted microstate.
- **Partial observation** (Qian, Zavatone-Veth, Ruben, Pehlevan, NeurIPS 2024; *abstract*). Observing only a subset of units
  produces student networks with **spurious attractors**, for example a line attractor where the teacher is feedforward or
  non-normal. The discriminating test is the **decay time of a kick along the putative attractor**. This makes a ready-made
  tournament test case.
- **Aligned vs oblique dynamics** (Schuessler, Mastrogiuseppe, Ostojic, Barak, eLife 13:RP93060, 2024, arXiv:2307.07654;
  *abstract*). Networks with the same output can respond differently to perturbations along the output direction. So readout
  equivalence does not imply state equivalence, and a z fitted only to predict the readout misses oblique dynamics.
- **Dimensionality under perturbation.**
  - Jazayeri & Ostojic, Curr. Opin. Neurobiol. 70, 2021, arXiv:2107.04084: intrinsic dimension ≤ linear embedding dimension.
  - **Wan & Rosenbaum, arXiv:2504.13727** (*abstract*): low-rank networks produce high-dimensional responses when driven by
    high-dimensional inputs, with **low-rank suppression** along the connectivity directions.
  - Consequence: a k chosen from passive variance can be both too large (embedding dimension) and too small (missing
    input-driven directions). This is the methodological case for choosing k by intervention fidelity and closure.

### 9.2 What perturbations cannot reveal, and known pitfalls

- **Acute vs chronic silencing.**
  - Otchy et al., Nature 528:358-363, 2015 (*abstract*): transient silencing can disrupt the output while permanent removal of
    the same component lets the output recover. The acute deficit was caused by off-target effects on a downstream component,
    which recover over days.
  - Wolff & Ölveczky, Curr. Opin. Neurobiol. 49:84-94, 2018 (*abstract*): necessity tests conflate direct contribution with
    network-wide knock-on effects.
  - **For our simulator:**
    - Treat temporary and persistent silencing as **different intervention kinds**.
    - If the simulator has slow adaptation, evaluate at several delays after onset.
    - A silencing effect that is mediated through downstream units is still a valid latent effect. The test is whether it
      flows through z, not whether it is local.
- **Lesion maps mislead** (Jonas & Kording, PLOS Comput. Biol. 13(1):e1005268, 2017; *full*).
  - Single-element lesions produced elements that looked "necessary" for particular behaviours, but they implement generic
    sub-functions.
  - Tuning curves were epiphenomenal, and dimensionality reduction recovered signals that did not explain the computation.
  - **Principle:** validate every analysis method on simulated ground truth, including systems where the right answer is
    "no compact state". The contract's "intervention-ID → output" baseline is exactly the lesion-map analysis criticised here.
- **Dynamics reconstruction review** (Durstewitz, Koppe, Thurm, Nat. Rev. Neurosci. 24:693-710, 2023; *abstract*): evaluate
  with invariant and long-term statistics as well as short-horizon error `[emphasis unverified]`.
- **Active design and lifts in this literature.** Wagenmaker et al. 2024 (§1.2) and De, Kiani, Mazzucato 2026 (§7.2).

### 9.3 Validation protocol derived from these papers `[synthesis]`

1. **Twin-simulator benchmark.** Build pairs of simulators that match on passive statistics but differ in mechanism. A method
   must separate them, and the decision must depend on intervention data.
2. **Hold out intervention families** (type × target), not just trials.
3. **Evaluate at multiple delays.** Separate transient from sustained effects, and acute from persistent silencing.
4. **Check the read-in against measured Jacobians.** Compare the model's input Jacobian with the Jacobian measured in the
   simulator by restarting from kicked microstates.
5. **Report effect errors properly:** readout-effect error Δy, a distributional activity distance, and the noise floor.
6. **Test under partial observation.** Check for spurious attractors with kick-decay tests.
7. **Validate every analysis on ground truth,** including cases where the correct answer is to abstain.

### 9.4 Method record, area 9

| Tool | What it tests | Assm. | Failure modes | Code |
|---|---|---|---|---|
| Held-out perturbation prediction (twin models) | causal validity beyond passive fit | perturbations withheld | families too similar to training | Sourmpis/BiologicallyInformed |
| Residual dynamics | local recurrent Jacobian without perturbation | inputs repeat across trials | input variability | residual-dynamics (MIT) |
| Kick-decay test | attractor vs transient amplification | restarts | noise floor | from scratch |
| Readout-direction perturbations | aligned vs oblique | readout known | none major | from scratch |
| Multi-delay silencing | acute vs persistent / off-target | adaptation timescale | cost | from scratch |
| Ground-truth sanity checks | method validity | simulator available | overfitting the benchmark | n/a |

## 10. Counterexample-guided refinement of learned abstractions

### 10.1 CEGAR, CEGIS, black-box checking

- **CEGAR** (Clarke, Grumberg, Jha, Lu, Veith, CAV 2000; JACM 50(5):752-794, 2003; *abstract*).
  - **Loop.** Build an abstraction, check it, and replay any counterexample on the concrete system. If the counterexample is
    spurious, find the "failure state" where concrete behaviours split and refine that block.
  - **Mapping** `[synthesis]`:
    - An abstract cell is a set of microstates with equal φ.
    - A spurious counterexample is two microstates with equal z whose futures differ, or a lift whose realised consequences
      differ from the model's prediction.
    - Refinement means increasing k along the discriminating direction, or reweighting training on those pairs.
    - The "failure state" corresponds to **the first time step after the intervention where the futures diverge**. That is
      where to refine.
- **CEGIS** (Solar-Lezama, PhD thesis 2008; *search summary*). A synthesiser fits unknowns to a finite set of inputs, and a
  verifier searches for a counterexample, which is added to the set.
  - **For us:** active learning where queries are chosen to *falsify* the model rather than to maximise information gain.
  - **Stopping rule:** stop when a falsifier with budget B finds no violation above the calibrated threshold. This is a
    probabilistic certificate, so always report the budget and the search method.
- **Abstraction-refinement for neural networks** (Elboher, Gottschlich, Katz, CAV 2020): run cheap adversarial search first and
  expensive reasoning only on the survivors.
- **Black-box checking** (Waga, HSCC 2020, arXiv:2005.02126): learn an automaton from queries, model-check it, and test
  counterexamples on the real system, with robustness guiding the search.

### 10.2 Simulation-based falsification

- S-TaLiRo (Annpureddy, Liu, Fainekos, Sankaranarayanan, TACAS 2011): minimise STL robustness ρ, where ρ < 0 is a violation.
- Breach (Donzé, CAV 2010): sensitivity-aided falsification.
- **VerifAI** (Dreossi et al., CAV 2019, arXiv:1902.04245; BSD-3 `[unverified]`): samplers (random, Halton, cross-entropy,
  simulated annealing, BO), monitors, and an error table used for retraining. This is a reusable architecture for our loop.
- BO-based falsification: Deshmukh et al., ACM TECS 2017; Ramezani, Šehić, Nardi, Åkesson, arXiv:2209.06735 (local and
  trust-region surrogates help most under tight budgets).
- **Survey** (Corso, Moss, Koren, Lee, Kochenderfer, JAIR 72, 2021, arXiv:2005.02979): optimisation, path planning, importance
  sampling and RL-based stress testing.

### 10.3 Adversarial search for disagreement

- QBC (Seung et al. 1992).
- DeepXplore (Pei, Cao, Yang, Jana, SOSP 2017): gradient ascent on inputs to maximise disagreement between models (differential
  testing).
- CMA-ES (Hansen, arXiv:1604.00772): derivative-free and invariant; population size 4 + ⌊3 ln n⌋; works up to ~100
  dimensions.
- PGD with restarts (Madry et al., ICLR 2018 `[background]`).
- **Model invalidation** (Smith & Doyle, IEEE TAC 37(7):942-952, 1992; *abstract*). Data can only **invalidate** a model, never
  validate it. So report "not invalidated at level ε* over the tested intervention set".
- **Residual-input cross-correlation** R_{εa}(τ) (Ljung 1999 `[background]`). A significant residual-intervention correlation
  directly shows a violation of closure. It is cheap and should be in every evaluation.

### 10.4 Falsification objectives and schedule `[synthesis]`

Let θ be the experiment parameters.

- **(O1)** Model vs simulator: J₁ = d(Y_sim, Ŷ)/s, compared with the conformal quantile. Needs simulator runs.
- **(O2)** Ensemble or model-class disagreement: J₂ = tr Cov_m[Ŷ_m]/noise, or the JS divergence between the k = 2 and k = 3
  models. Model-only, so cheap.
- **(O3)** Microstate-equivalence violation: J₃ = d(Y_sim(x₁,θ), Y_sim(x₂,θ)) s.t. ‖φ(x₁) − φ(x₂)‖ ≤ ε. Search along the null
  space of the encoder Jacobian.
- **(O4)** Lift inconsistency: J₄ = d(Y(a₁), Y(a₂)) s.t. R(z,a₁) ≈ R(z,a₂).

**Schedule** under a budget B in CPU-seconds:

1. Screen with a Sobol sample on the **models** (free).
2. Refine with CMA-ES or PGD on the model-only objectives.
3. Spend simulator runs on the top candidates, with R paired replicates each. Count a violation only above the conformal
   threshold, with Benjamini-Hochberg across candidates.
4. For expensive runs, use GP-BO / TuRBO on O1.
5. Compare the falsifier itself against random search at the same budget, reporting counterexamples per CPU-second.

**Loop.**

1. Calibrate on independent draws.
2. Falsify.
3. Classify each candidate as a real counterexample, noise, or out of domain.
4. Diagnose which component failed: read-in, dynamics, closure or dimension.
5. Refine: add the counterexample (CEGIS), split the cell by increasing k (CEGAR), or change the read-in class.
6. Stop when a budgeted falsifier fails, or when k exceeds a cap. Hitting the cap means abstaining: "no compact state".

**Pitfalls.**

- Overfitting to counterexamples: keep a fixed held-out family.
- The falsifier exploiting noise: use replicates.
- Calibration drift: recalibrate on independent draws, or use ACI.
- Reporting "none found" without the budget.

### 10.5 Method record, area 10

| Method | Assm. | Cost | Failure modes | Code | Scratch |
|---|---|---|---|---|---|
| CEGAR / CEGIS loop | a falsifiable spec with a calibrated threshold | budget B | overfitting counterexamples; noise exploitation | n/a | simple |
| Random / Sobol search | none | cheap | weak in high dimension | scipy.stats.qmc | trivial |
| CMA-ES | ≲ 100 dimensions | 10²-10⁴ evaluations | noisy fitness | pycma, nevergrad | simple |
| GP-BO / TuRBO | smooth objective, ≲ 20 dimensions | O(n³) GP | discrete spaces | BoTorch (MIT) | moderate |
| Gradient / PGD on models | differentiable models | cheap | model-only optimum | autograd | simple |
| VerifAI-style sampler + monitor + error table | scenario parametrisation | varies | none major | VerifAI | moderate |
| Residual-intervention correlation | linear residual test | trivial | only linear dependence | statsmodels | trivial |

---

# PART II. Synthesis for method developers

This part describes how to build and run the tournament. Anything not attributed to a source is my synthesis. The level of
literature support is stated for each piece.

## II.1 Design principles that follow from Part I

1. **Train interventionally from the start, but keep held-out intervention *families*.**
   - Passive fit does not determine mechanism (§9.1).
   - Only interventional metrics validate abstractions (§7.4, Méloux et al.).
   - Held-out families (type × target group) play the role that held-out perturbations play in the validation literature.
2. **Put the read-in in an explicit module, separate from the dynamics.**
   - Kicks: a jump operator.
   - Currents and pulses: an additive or control-affine term.
   - Silencing and connection weakening: a bilinear term.
   - Parameter changes: FiLM, context, or low-rank modulation.

   This makes the read-in inspectable, sparsifiable (identifiability, §2.2) and invertible (the lift).
3. **Parametrise the read-in by physical descriptors, never by intervention IDs.** This is the only route to unseen targets
   (§3.0, §4.2). Suggested descriptor for every intervention:
   - kind: one-hot over {kick, pulse, current, pattern, silence-temporary, silence-persistent, weaken-edge, param-change};
   - target features: for each targeted unit, a feature vector, e.g. its emission / encoder loading (the row of C⁺ or ∂φ/∂x_j),
     and whether it is observed;
   - magnitude, onset, duration;
   - pattern parameters.

   Sets of targets enter through permutation-invariant pooling (a sum over targets), so that grouped interventions compose.
4. **Encoders must be causal, have bounded memory, and never see a.**
   - The encoder window w is a reported hyper-parameter.
   - Any deterministic recurrent memory counts toward k.
   - The encoder input excludes the readout y, unless the readout is part of the declared observation.
5. **Evaluate only quantities that do not depend on the parametrisation** (predictions, effects, eigenvalues, transfer
   functions, closure gaps). Coordinates are identifiable only in special cases (§1.8, §2.0).
6. **Exploit the simulator's two special powers.**
   - Restarts from arbitrary microstates give paired counterfactuals, equal-z pairs and direct Jacobians.
   - Common random numbers give low noise floors and computable cross-world mediation.
7. **Design needs.**
   - Intervention regimes must cover every latent direction (Squires), every pair of latents (iSSM), and ≥ r or ~r² regimes
     (interventional SDEs).
   - Constant currents are weak excitation; use pulses, PRBS and multisines (§3.6, §5.7).
   - Realistic active-design gains are ≤ 2x (§5.4).

## II.2 Tournament families (10) with recipes

Shared protocol for every family:

- the same data and splits (II.5);
- an ensemble of M = 5 members (bootstrap over *experiments* for linear families; different seeds plus bootstrap for neural
  families);
- the same evaluation suite (II.6);
- the same abstention wrapper: conformal plus disagreement.

**Notation.**

- 𝒟_pass: passive windows.
- 𝒟_int: interventional windows. The pre-window gives z_{t−}; the read-in is applied at t; the futures run to t + H.
- 𝒟_pair: paired runs with common random numbers (same x₀; a vs none; a vs a′).
- σ²_floor: per-output noise-floor variance, estimated from replicate runs with common random numbers.

### F1. Interventional linear SSM (iLSSM, EM). Support: strong (standard LDS + iSSM + IPSID)

- **Model.** The iSSM-mix of §1.9, linear-Gaussian:

      z+ = A_s z + B u + G(ψ(a)) + b(a) + w;  y = C z + D u + v;  readout = H z

  - Additive channels: G(ψ) = Γ·Σ_{j∈targets} φ_j·mag·pattern_t, with target features φ_j.
  - Clamps: only for unit-aligned latents.
  - Mechanism contexts: A_s = A + Σ_l s_l U_l V_lᵀ.
- **Encoder.** The Kalman filter, which is causal and exact under the model. The window is effectively infinite, but it is
  linear and has k states, so there is no hidden memory beyond k.
- **Objective.** Maximum likelihood by EM (§1.9). Then optionally fine-tune on the open-loop multi-step intervention-future
  loss, because EM is one-step and multi-step fine-tuning reduces misattribution (BRAID).
- **Read-in.** Δz = G(ψ(a)), plus clamp or mechanism terms. It is interpretable as a latent kick per unit of physical
  magnitude.
- **Lift.** The Gramian minimum-norm or constrained QP of §7.3(L). Distinct lifts come from the null space of G or from
  disjoint target sets.
- **Dimension rule.** For k = 1…k_max, compute the held-out interventional log-likelihood and the multi-step effect error. Pick
  the smallest k within 1 SE of the best (the one-standard-error rule), subject to closure gap ≤ τ_clo (II.3). Report the
  posterior over k from the ensemble / bootstrap.
- **Uncertainty and abstention.** Kalman predictive covariance plus bootstrap spread, then trajectory conformal calibration
  (§8.2). Abstain when the conformal band on the effect includes 0 while the MDE exceeds the SESOI, or when the query is out of
  domain.
- **Compute.** CPU, seconds per fit for k ≤ 20, N_obs ≤ 200. Software: dynamax (MIT) for EM with inputs; clamp masks need a
  custom time-varying transition.
- **Fails when** dynamics are strongly nonlinear or multistable, or read-ins are state-dependent.

### F2. DMDc, tuned and bagged, plus bilinear DMDc. Support: strong (Proctor et al.; bilinear Koopman theory)

- **Model.** A delay-embedded observation h_t = [y_t; …; y_{t−d}], with a POD encoder z = Ûᵀh_t (causal).

      z+ = A_r z + B_r ψ(a) + Σ_j ψ_j(a)·N_j z

  The bilinear term is included for the silencing and weakening kinds.
- **Objective.** Ridge least squares on snapshot pairs within experiments (§3.1, P1 in the notes). Tune (r, p, d, λ) on
  held-out **experiments**, scored by intervention-effect error.
- **Read-in.** B_r = ÛᵀE_ψ, where E_ψ maps the physical actuation (the target unit's direction) into the observed/delay space.
  This gives unseen targets for free when the target unit is observed. For unobserved targets, learn a map from target
  features to B_r columns.
- **Lift.** The pseudo-inverse of B_r (or B(z) in the bilinear case), then Gramian or constrained variants.
- **Dimension rule.** r is chosen by held-out effect error with the 1-SE rule. Also report the singular-value spectrum.
- **Uncertainty.** Bagging over experiments, then conformal calibration.
- **Compute.** Milliseconds to seconds, CPU. Software: PyDMD / PyKoopman (MIT) for the linear version; bilinear from scratch.
- **Fails when** there is measurement-noise bias (use more delays or TLS), hidden state beyond the delays, or collinear
  sustained currents.

### F3. Subspace identification with control (CVA / N4SID; IPSID variant; PBSID under adaptive design). Support: strong

- **Model.** Innovation-form LTI with u ← [u; ψ(a)], plus a readout-prioritised block (IPSID Stage 1 on the future readout).
- **Encoder.** The steady-state Kalman predictor (causal).
- **Objective.** Closed-form projections and SVD. Multi-experiment Hankel columns never cross experiment boundaries. Use PBSID
  when interventions were chosen adaptively within a run.
- **Read-in.** The B column for each channel. For unseen targets, regress B columns on target features (a linear map from
  φ_j), with ridge regularisation.
- **Lift.** Gramian (§3.10).
- **Dimension rule.** The CVA canonical correlations between the input-corrected future and the past, with the "future"
  restricted to post-intervention windows. Order by AIC, cross-checked by held-out effect error. This is the closest classical
  "k for intervention fidelity" rule `[synthesis]`.
- **Uncertainty.** Bootstrap over experiments, then conformal calibration.
- **Compute.** CPU seconds. Software: SIPPY (LGPL), nfoursid (MIT), PyPSID (academic licence).
- **Fails when** the order is ambiguous, experiments are short, or the design is closed-loop (use PBSID).

### F4. Sparse control-affine / SINDYc on a low-dimensional encoder. Support: medium-strong

- **Encoder.** Linear (PCA over delays, or the F3 Kalman state) or a small causal autoencoder, with k from the sweep.
- **Model.** dz/dt = Ξ_fᵀΘ(z, u) + Σ_c Σ_j g_{c,j}(z)·ψ_{c,j}(a).
  - The library holds polynomials up to degree 2-3, the terms z·a (bilinear) and a (additive).
  - Kick jumps use Δz = (∂φ/∂x)·d, the encoder Jacobian times the physical kick.
- **Objective.** SR3 or STLSQ on derivative estimates, or the weak form. Then refine by multi-step integration of the
  effect error.
- **Read-in.** The sparse g(z) terms are readable: which latent coordinates each intervention kind moves, and how that
  depends on the state.
- **Lift.** Nonlinear least squares, or CMA-ES over a; check the result in the simulator.
- **Dimension rule.** Sweep the encoder k. Choose the smallest k whose sparse model reaches the effect-error plateau with the
  fewest active terms (Pareto knee).
- **Uncertainty.** Ensemble-SINDy inclusion probabilities, with bagged coefficients giving the predictive spread. Abstain
  when an active term's inclusion probability is below 0.5 for the queried intervention kind.
- **Compute.** CPU seconds, k ≲ 10. Software: pysindy (MIT).
- **Fails when** the coordinates are wrong or the library is collinear under a poor design (it needs excitation of the cross
  terms, which A5 in II.4 targets).

### F5. Controlled Koopman model, bilinear (EDMD or deep). Support: medium (theory for bilinear; few interventional benchmarks)

- **Model.** A lift ψ(h_t) (delays + RBF / random Fourier features, or a learned encoder).

      ζ+ = Aζ + Σ_c ψ_c(a)(N_c ζ + b_c);   y = Cζ

- **Objective.** EDMD ridge regression on [ψ; a; a⊗ψ]. For the deep variant: reconstruction + multi-step latent linearity +
  multi-step prediction under interventions.
- **Read-in.** Bilinear and state-dependent: Δζ = (N_c ζ + b_c)ψ_c.
- **Lift.** One-step: a = B(ζ)⁺Δζ. Multi-step: Gauss-Newton.
- **Dimension rule.** The reduced rank of A after a truncated SVD of the lifted operator. Evaluate "k" as the rank of the
  projection C, i.e. the dimension that matters for prediction, since the lift dimension itself is not the state dimension.
- **Uncertainty.** Bagging or deep ensembles.
- **Compute.** CPU for EDMD; GPU helps for deep Koopman. Software: PyKoopman (MIT; linear-in-input); bilinear from scratch.
- **Fails when** spurious eigenvalues appear, or intervention information leaks into the lift. The lift must not see a.

### F6. Interventional predictive bottleneck (IPB). Support: medium (VIB / CPC / PF-IB, CVA), interventional form speculative

- **Model.**
  - Causal encoder q(z_t | x^{obs}_{t−w:t}, u_{t−w:t}), which does not see a.
  - Latent rollout z_{t+1} = f(z_t, u_t) with read-in z+ = R(z−, ψ(a)).
  - Predictive heads for the future readout and the observed units.
  - No reconstruction of the past (non-generative).
- **Objective.**

      L = E_{𝒟_pass ∪ 𝒟_int} Σ_h w_h [ −log p(y_{t+h}, x^{obs}_{t+h} | rollout(z_t; u, a)) ] + β·KL(q(z_t|·) ‖ N(0, I))

  The KL term is the VIB rate. The linear-Gaussian version is "interventional CVA": canonical correlations between the past
  and the input-corrected future of post-intervention windows.
- **Read-in.** An explicit module, R(z, ψ) = z + W(z)ψ (control-affine), initialised linear.
- **Lift.** Gradient-based through R, with the ensemble-disagreement penalty.
- **Dimension rule.** Sweep β. Count the **active latent dimensions** (per-dimension KL > 0.01 nats per step). The past-future
  IB phase transitions (Creutzig et al.) add dimensions one at a time, so plot effect error against rate and take the knee.
- **Uncertainty.** Deep ensemble plus conformal calibration.
- **Compute.** CPU for small models; GPU optional.
- **Fails when** the MI or KL bounds are loose, a leaks into the encoder, or β is mis-set (collapse or over-coding).

### F7. Latent neural controlled SSM (RSSM-lite with explicit read-in). Support: medium-strong (DKF / RSSM, PETS)

- **Model.** A stochastic latent z ∈ R^k with **no separate deterministic memory** (or with memory h counted in k).
  - Transition: z+ = z + Δt·f_θ(z, u) + R_φ(z, ψ(a)) + σ_θ(z)ε.
  - FiLM modulation of f for parameter-change kinds.
  - Emission and readout heads.
- **Encoder.** A filtering posterior q(z_t | z_{t−1}, x_t^{obs}, u_t). The a-dependence enters only through the prior (the
  transition), never the posterior network input. The iSSM overwrite trick handles any clamps.
- **Objective.** ELBO + **latent overshooting** (multi-step KL between the open-loop prior and the posterior) + the II.3
  terms. Use free bits to avoid collapse.
- **Read-in.** The R_φ module, with an L1 group-sparsity penalty over latent coordinates per kind (mechanism sparsity).
- **Lift.** Gradient or CMA-ES through R_φ and f, with the disagreement penalty.
- **Dimension rule.** Sweep k and apply the II.3 selection rule, using effect error and closure gap.
- **Uncertainty.** A 5-member deep ensemble, trajectory sampling (PETS TS∞), and conformal calibration.
- **Compute.** CPU for k ≤ 8 and small MLPs; GPU for sweeps.
- **Fails when** there is posterior collapse, a smoother leaks into evaluation, or the ensemble is under-dispersed on new kinds.

### F8. Neural ODE with an intervention operator (hybrid jump-flow). Support: medium (Neural ODE / CDE / jump SDE)

- **Model** (continuous time):
  - flow: dz/dt = f_θ(z, u; FiLM(ψ_param)) + G_θ(z)·ψ_curr(a(t)) for currents and patterns;
  - kicks: z+ = z− + r_θ(z−, ψ_kick(a)) at kick times;
  - persistent silencing and edge weakening: a context c(a) that modulates f by low-rank or FiLM terms.
- **Encoder.** An observer-type causal encoder over a window w ≥ the observability index (§4.2).
- **Training.** Fixed-step RK4, multiple shooting over windows, multi-horizon effect loss plus the II.3 terms.
- **Read-in.** G_θ(z) (the control vector field) and r_θ (the jump). Both are inspectable, with Δz ≈ G(z)Δa for a small step
  (the CDE view).
- **Lift.** Adjoint or autograd gradient on a (a waveform or kick vector), iLQR for sequences, CMA-ES for discrete choices.
- **Dimension rule.** Same as F7. Note that a smaller k is possible than for linear families (intrinsic vs embedding
  dimension, §9.1). Check for trajectory crossings: a need for augmentation signals under-dimensioning.
- **Uncertainty.** Deep ensemble plus conformal calibration.
- **Compute.** CPU with fixed-step RK4 for k ≤ 8; GPU for sweeps. Software: torchdiffeq (MIT), diffrax.
- **Fails when** stiffness with sharp pulses appears (use event-based jumps), or solver-dependent gradients misbehave.

### F9. Adapted interventional SSM (iSSM-mix, nonlinear emission). Support: iSSM theory for clamps; the mix is speculative

- **Model.** The §1.9 nonlinear variant:
  - linear, or switching per mechanism context, latent dynamics;
  - nonlinear emission f_θ;
  - a mixed read-in: additive G(ψ) for kicks, pulses and currents; a clamp mask for unit-aligned latents when targeted
    designs exist; context-switched A_s for persistent mechanism changes.
- **Inference.** Amortised VI with a causal GRU recognition network, the iSSM posterior overwrite, and BRAID-style open-loop
  multi-step terms.
- **Identifiability lever.** The design must include regimes that cover latent pairs (Cor. 3.6). Check this coverage with the
  estimated B or G sparsity pattern.
- **Read-in.** Sparse G. The clamp mask is interpretable as "which latents this intervention cuts".
- **Lift.** Linear in the latent (Gramian), since the dynamics are linear given the context.
- **Dimension rule.** As in F1; seed-consistency of B (the iSSM "consistency score") is an extra stability measure.
- **Uncertainty.** An ensemble over seeds (the B spread across seeds is also an identifiability diagnostic), plus conformal
  calibration.
- **Compute.** CPU/GPU (JAX). Base on dynamax, or re-implement the issm code, since issm has no licence.
- **Fails when** the clamp mode is misassigned, or the linear latent dynamics are inadequate. The latter shows up as a closure
  gap that grows with the kick magnitude.

### F10. Shared latent dynamics with implementation-specific encoders / read-ins. Support: speculative (abstraction theory only)

Use this only after each implementation passes within-system causal validity (II.6 thresholds). An implementation is one
simulator variant: a different N, unit model, or parametrisation.

- **Model.** For each implementation i there is an encoder φ_i, a read-in R_i and an optional emission. There is **one**
  shared f (and a shared readout g, if the task readout is common).
- **Stage 1.** Fit the best within-system family per implementation (F1-F9) with a common k.
- **Stage 2.** Align latents with an invertible map T_i (affine, or a small normalising flow) that minimises the disagreement
  in *invariants*: eigenvalues or transfer functions, fixed points and Jacobians, and readout-conditioned trajectories. Then
  refit the shared f on the pooled, aligned data, keeping φ_i and R_i implementation-specific.
- **Objective.** Σ_i [L_int,i + L_med,i + L_clo,i] + λ_share Σ_i ‖f_i − f‖² (a soft-sharing warm-up), annealed to hard sharing.
- **Tests.**
  1. **Cross-implementation lift.** Lift a target Δz with R_j in implementation j, and check that the realised readout future
     matches the shared-f prediction.
  2. **Cross-implementation interchange.** Encode x in implementation i, map through the alignment, and predict the futures of
     implementation j under matched latent interventions.
- **Theory.** Two low-level models that abstract to the same high-level model (exact-transformation composition; Rischel &
  Weichwald's composition bound). There are no published estimation methods or benchmarks for this with interventions.
- **Fails when** the implementations do not share a computation. Detect this by comparing the invariants **before** forcing a
  shared f, and abstain from sharing when they differ beyond the within-system bootstrap spread.

### Summary table of families

| Family | Read-in form | Lift | Dimension rule | Uncertainty / abstention | Compute | Literature support |
|---|---|---|---|---|---|---|
| F1 iLSSM | additive G(ψ) + clamp + context | Gramian / QP | held-out interventional log-likelihood, 1-SE rule + closure | Kalman + bootstrap + conformal | CPU s | strong |
| F2 DMDc (+bilinear) | B_r = ÛᵀE; N_j z | pinv / Gramian | held-out effect error | bagging + conformal | CPU ms | strong |
| F3 Subspace ID | B columns; feature→B map | Gramian | CVA canonical correlations on post-intervention futures | bootstrap + conformal | CPU s | strong |
| F4 SINDYc | sparse g(z)a, jumps via ∂φ/∂x | NLS / CMA-ES | Pareto knee (k, #terms) | ensemble-SINDy inclusion | CPU s | medium-strong |
| F5 Bilinear Koopman | (Nζ + b)a | B(ζ)⁺ / Gauss-Newton | rank of the projected operator | bagging / ensembles | CPU (EDMD) | medium |
| F6 IPB | R = z + W(z)ψ | gradient | active dimensions vs β (IB knee) | ensemble + conformal | CPU/GPU | medium (speculative interventional form) |
| F7 Latent neural SSM | R_φ module + FiLM | gradient / CMA-ES | k sweep, II.3 rule | ensemble (TS∞) + conformal | CPU/GPU | medium-strong |
| F8 Neural ODE + operator | G(z) field + jump r(z, a) + context | adjoint / iLQR | k sweep; crossing check | ensemble + conformal | CPU (RK4) | medium |
| F9 iSSM-mix | sparse G + clamp + A_s | Gramian | as F1 + seed consistency | seed ensemble + conformal | CPU/GPU | iSSM theory; mix speculative |
| F10 Shared-f | per-implementation R_i | per-implementation | shared k | per-implementation conformal | 2-stage | speculative |

## II.3 Candidate training objective

    L = λ_obs L_obs + λ_int L_int + λ_med L_med + λ_clo L_clo + λ_eq L_eq + λ_lift L_lift + λ_cx L_cx + λ_unc L_unc

**Normalisation** (so that the λ's are comparable and units are explicit):

- Every prediction error is divided by the **noise-floor variance** σ²_floor per output and horizon. σ²_floor is estimated
  from replicate runs with common random numbers.
- Error terms are therefore dimensionless ("multiples of the noise floor"). Values ≈ 1 mean the model is at the noise floor.
- Information terms are in nats per step.

**Defaults.** λ_obs = λ_int = 1, and the other λ's are swept on a log grid. Report every term on the test set even when its
λ = 0.

| Term | Definition | Motivation | Units / scaling | Ablation | Literature support |
|---|---|---|---|---|---|
| **L_obs**, observational future | Σ_h w_h NLL(y_{t+h}, x^obs_{t+h} ; open-loop rollout from z_t, u, a = ∅) on 𝒟_pass | ordinary predictive state (causal states, PSR, CPC) | noise-floor units; w_h ∝ 1/H over h ∈ {1, 2, 4, …, H} | λ_obs = 0: does interventional data alone suffice? | **strong** |
| **L_int**, intervention future | the same on 𝒟_int, with R applied at t. Plus the **effect form** on 𝒟_pair: ‖(y^a − y^0) − (ŷ^a − ŷ^0)‖²/σ²_{d} | open-loop multi-step prediction with known inputs separates dynamics from input effects (BRAID); the effect form cancels baseline error | noise-floor units (σ²_d = variance of the paired difference) | λ_int = 0 gives a "passive model + read-in fitted afterwards" baseline | **strong** (BRAID, RSSM overshooting, validation literature) |
| **L_med**, state mediation (read-in commutation) | ‖φ(x^{a}_{t+}) − R(φ(x_{t−}), ψ(a))‖²_{Σ⁻¹} on 𝒟_int (encode after the intervention vs read-in of the encoded pre-state), plus an architectural constraint: after t, f receives no a-identity, only the ongoing physical waveform | τ-abstraction: ω must be induced by τ (Beckers & Halpern); the exact-transformation commuting diagram (Rubenstein; Zennaro) | normalised by Var(Δz) over 𝒟_int (dimensionless); the settling window after t is a hyper-parameter | λ_med = 0; also ablate the architectural constraint (give f access to the a-ID) and measure the closure gap | **definition supported**; as a training loss: Zennaro et al. (finite SCMs) → adapted |
| **L_clo**, interventional closure | the gain of an auxiliary predictor p_aux(future ∣ z_t, R, u, ξ_t, a-ID) over p(future ∣ z_t, R, u), where ξ_t = residual microstate features (the component of x orthogonal to the encoder's row space, or unobserved-unit summaries available only in simulation). L_clo = max(0, NLL_main − NLL_aux) on held-out data | AIS (P2); informational / causal closure (Rosas et al.); Markov tests | nats per step (or fraction of explained variance) | λ_clo = 0; it is always reported as a metric | **supported as a metric** (AIS, CI tests); as a min-max training loss **speculative**: aux-capacity arms race, instability |
| **L_eq**, microstate equivalence | pairs (x₁, x₂) with small ‖φ(x₁) − φ(x₂)‖ obtained by simulator restarts: E[max(0, d_fut(x₁, x₂) − L·‖φ(x₁) − φ(x₂)‖ − ε)²], where d_fut is the distance between future readout laws under the **same** probe intervention sequence (energy distance over replicates) | bisimulation metrics and DBC; interchange interventions (IIA) | noise-floor units; L = Lipschitz constant (hyper-parameter); ε = noise-floor tolerance | λ_eq = 0; report the equivalence accuracy anyway | **supported in RL** (DBC; bisimulation); pair construction in physical microstates **new** |
| **L_lift**, lift consistency | on lift experiments (a*, a₁, a₂ found by the §7.3 lift of the current model and run in the simulator): (i) lift success ‖φ(x after a*) − (z + Δz*)‖²; (ii) for distinct lifts, ‖(ŷ(a₁) − ŷ(a₂)) − (y(a₁) − y(a₂))‖²/σ²_d, i.e. the model must predict any *difference* the simulator shows | strong τ-abstraction / multiple realisability; also a targeted source of training data at the abstraction's fibres | noise-floor units | λ_lift = 0 (still evaluated) | **definition supported**; as a loss **speculative** |
| **L_cx**, complexity | discrete k (model selection) + β·KL rate (VIB) + group-L1 on read-in coefficients per kind + spectral / Lipschitz penalty on φ + a penalty on encoder window w | minimality (causal states); mechanism sparsity → identifiability; guards against dimension cheating | nats (KL); penalties dimensionless | sweep β and sparsity; w ∈ {1, 2, 4, 8, 16} | **supported** (VIB, mechanism sparsity) |
| **L_unc**, uncertainty | heteroscedastic Gaussian NLL (or energy score for trajectories), trained per ensemble member; optional ensemble-diversity term. **Calibration is done after training** (conformal), not in the loss | proper scoring gives calibrated spread in-domain; ensembles for epistemic uncertainty | nats; the energy score in noise-floor units | NLL → MSE (no variance head); M = 1 vs 5 | **strong** (proper scores, deep ensembles) |

**Selection rule for k** (every family):

1. For each k, compute on the validation experiments: the effect error E_int(k) (L_int, effect form), the closure gap C(k)
   (L_clo metric) and the equivalence accuracy Q(k).
2. **k̂ = the smallest k with E_int(k) ≤ min_k E_int + 1 SE, C(k) ≤ τ_clo and Q(k) ≥ τ_eq.**
3. If no k ≤ k_max satisfies this, **abstain** ("no compact state").
4. Report the bootstrap distribution of k̂ over experiment resamples, i.e. the dimension uncertainty.

Thresholds: τ_clo is the 95th percentile of the closure gap measured on the **true** full-state model (the full-state
controlled baseline), so that the estimator's own bias is subtracted. τ_eq is set from equal-microstate replicate pairs (the
noise ceiling).

**Ablation plan.** Remove one term at a time. Report all II.6 measures with paired seeds (same data, same initialisation). Also
run a "passive-only" arm (L_obs + L_cx, read-in fitted post hoc), which tests the contract's premise.

## II.4 Active experiment design: acquisition functions and fair comparison

**Candidate pool.** A design ξ = (restart distribution or specific x₀, u(t), kind, target set, magnitude, onset, duration,
pattern parameters; optionally a sequence of such interventions). Draw a candidate pool of 10³-10⁴ designs by Sobol sampling
over the descriptor space, stratified by kind. All scoring is done on the **models** (the ensemble), and only the selected batch
is simulated.

**Ensemble.** 𝓜 = {m₁…m_M}, M = 5, drawn from one family, or from several k (for A4).

### The 7 acquisition functions plus a cost wrapper

| # | Name | Score | Cheap estimator | Cost / candidate | Assumptions | Failure modes and guards | Source |
|---|---|---|---|---|---|---|---|
| **A1** | Effect disagreement (QBC / MAX) | S₁(ξ) = mean_h tr Cov_m[Δŷ_m(ξ)_h] / σ²_floor,h, i.e. the ensemble variance of the predicted **effect** (not the level) | M open-loop rollouts | M rollouts | ensemble spread ≈ epistemic uncertainty | collapsed ensembles (use bootstrap over experiments plus seeds); ignores relevance | Seung et al. 1992; Pathak et al. 2019; Shyam et al. 2019 |
| **A2** | Targeted information (EPIG-style) | S₂(ξ) = E_{ξ* ~ p*}[I(Δy(ξ); Δy(ξ*))], where p* is the distribution of **held-out-family probes and lift tests**. With Gaussian moment matching over the ensemble: ½ log[det Σ_ξ det Σ_{ξ*} / det Σ_{(ξ,ξ*)}] | the joint covariance of the ensemble predictions over (ξ, ξ*) pairs, with 20-50 probe designs ξ* | M rollouts × (1 + |ξ*|) | p* reflects the deployment use | wrong p* biases the design; with M = 5 the covariance estimate is crude (shrink it) | Bickford Smith et al. 2023 |
| **A3** | Fisher D-/A-optimal (linear / linearised families) | S₃(ξ) = log det(F_D + J_ξᵀΣ⁻¹J_ξ) − log det F_D, where J_ξ is the Jacobian of the predicted outputs with respect to **similarity-invariant** parameters (Markov parameters CAⁱB, or the read-in in output space). **Wagenmaker mixture**: sample half the batch from the A-optimal design on the estimated subspace and half from the isotropic A-optimal design | autodiff Jacobian; matrix-determinant-lemma rank-one updates | one Jacobian-vector product | local (Laplace) validity; identifiable parameters | extreme magnitudes (Rainforth et al. pathology), so cap magnitudes or stratify; latent rotation symmetry, so use invariant parametrisations | Mehra 1974; Pronzato 2008; Wagenmaker et al. 2024; Kirsch & Gal 2022 |
| **A4** | Dimension / model discrimination (k vs k+1; closure vs none; additive vs bilinear read-in) | Box-Hill: S₄(ξ) = Σ_{i<j} P(M_i)P(M_j)·D(p_i(y|ξ), p_j(y|ξ)), with D = symmetric KL between the Gaussian-moment predictive distributions of the per-class ensembles. For linear-Gaussian pairs, the **Bania closed form** (top eigenvector of Q₁₂ under an energy constraint). For nested pairs, use the T-criterion with the k+1 model **refitted** so that it is non-degenerate | per-class ensembles (already trained in the k sweep) | 2M rollouts | the candidate set contains an adequate model | nested degeneracy; wrong candidate set (always keep a "none" / abstain class) | Box & Hill 1967; Atkinson & Fedorov 1975; Bania 2019; Kleinegesse & Gutmann 2021 |
| **A5** | Weak-direction excitation (E-optimal coverage) | S₅(ξ) = λ_min(Σ_{acc} + Φ(ξ)Φ(ξ)ᵀ) − λ_min(Σ_{acc}), where Φ(ξ) = the latent excitation vector (the predicted Δz, or the library features [z; ψ; z⊗ψ] for F4/F5) and Σ_acc = the accumulated excitation. Complement it with the **model Gramian**: prefer targets that raise λ_min of the reachability Gramian × observability | incremental covariance / Gramian of the current model | cheap | the model's latent is roughly right | ignores noise and relevance, so use it in a mixture | Mania et al. 2022; Pasqualetti et al. 2014; Squires et al. 2023 (every direction must be hit) |
| **A6** | Falsification (closure / equivalence / lift inconsistency) | S₆(ξ) = the model-predicted **violation potential**: (i) the predicted divergence of futures for equal-z microstate pairs under ξ, computed across ensemble members (O3 proxy); (ii) the predicted difference between two distinct lifts (O4); (iii) the disagreement between additive-only and bilinear models | search with CMA-ES / PGD over ξ on the models (§10.4); verify on the simulator with paired replicates | 10²-10³ model evaluations | the models can see where they are fragile | the falsifier exploits simulator noise (replicates plus conformal threshold); overfits (keep a held-out family) | Clarke et al. 2003; Solar-Lezama 2008; Letham et al. 2016; Dreossi et al. 2019 |
| **A7** | Contrastive EIG (PCE) over the ensemble (principled reference) | S₇(ξ) = E[log p(y|θ₀, ξ) / ((M+1)⁻¹Σ_m p(y|θ_m, ξ))], with θ = ensemble members, y simulated from member θ₀ (a surrogate) | Gaussian likelihoods from member predictive heads | M² likelihood evaluations | calibrated likelihoods | ≤ log(M+1), so it saturates with M = 5 (use M ≥ 20 cheap members or bootstrap draws) | Foster et al. 2020; Rainforth et al. 2024 |
| **W** | Cost wrapper | S(ξ)/ĉ(ξ)^ν, where ĉ = predicted CPU-seconds (a regression on N, horizon, integration stiffness) and ν is cooled from 1 → 0 over the budget | a cost regressor | negligible | predictable cost | favours cheap, useless designs early (cooling fixes this) | Snoek et al. 2012; Lee et al. 2020 |

**Batch rule.** Use stochastic **power sampling**: p(ξ) ∝ S(ξ)^γ with γ ≈ 1-4, from Kirsch et al. 2023. It is the default
because it is cheap and diverse. Use greedy joint log-det for A2/A3 when the batch is ≤ 20.

**Recommended portfolio.** A1 as the base; A2 targeted at the held-out families; A3 for the linear families; A4 during
dimension selection; A5 early (coverage); A6 late (refinement); all wrapped by W.

**Curriculum** (it emerges from cost-cooling but can also be explicit):

1. Stage 1: single-target kicks and steps (read-in and linear core), selected by A5 + A3.
2. Stage 2: patterns and pairs (nonlinearity, bilinear terms), selected by A4 (additive vs bilinear) + A1.
3. Stage 3: A6 + A2 (closure refinement and held-out generalisation).

**Designs that reduce dimension uncertainty** `[synthesis; no dedicated source]`. Alternate A4 over (k, k+1) with A5 on the
weakest direction of the k_max model. Stop when P(k̂) > 0.9 across the bootstrap, or when the budget is exhausted. In the
latter case report the dimension posterior.

### Fair comparison protocol for design policies

Grounded in Munjal et al. 2022, Lüth et al. 2023 and Agarwal et al. 2021.

1. **Arms.** Each policy is compared against:
   - (a) **random** from the same candidate distribution;
   - (b) **stratified uniform** over kind × target group × magnitude bins × timing bins;
   - (c) the **fixed battery** (kicks per target, steps at 3 magnitudes, PRBS, log chirp, random-odd multisine, paired pulses
     at several delays, silencing single and paired; energy-matched);
   - (d) **greedy one-step D-optimal** (Blanke & Lelarge-style), a strong cheap baseline;
   - (e) passive (u only).
2. **Budgets.** Matched **both** in number of experiments and in **CPU-seconds**. The CPU time *includes* the policy's own
   compute (refits and scoring). Report learning curves against both axes.
3. **Identical learners.** The same model family, training recipe, hyper-parameter search budget and refit schedule for every
   arm. Re-tune for all arms or for none.
4. **Seeds and pairing.** ≥ 10 seeds per simulator configuration. Each seed fixes the simulator instance, the initial design
   and the model initialisation, and is shared across arms (a **paired** comparison). Use ≥ 3 simulator configurations (for
   example different N, true k, noise levels, and a "no compact state" system).
5. **Evaluation set.**
   - It is **fixed and independent of every candidate pool**.
   - It includes held-out intervention **families** (type × target group), lift tests and equivalence pairs.
   - It is never used for acquisition or calibration.
6. **Metrics.**
   - Learning curves of the II.6 measures.
   - The **normalised area under the learning curve**.
   - **Experiments-to-target** and **CPU-to-target**, reported as a data-efficiency ratio versus random, e.g. "1.6x (95% CI
     1.3-2.0)".
   - Dimension-selection accuracy / P(k_true).
7. **Statistics.**
   - Paired differences per seed, with a stratified bootstrap 95% CI.
   - The interquartile mean across configurations, and the probability of improvement.
   - Holm correction across policies.
8. **Robustness.** Several starting budgets (small, medium, large) and batch sizes (1, 8, 32); a misspecified-k regime; a
   noise-level sweep.
9. **Pre-registration.** Fix the primary metric and the budget before running. Report policies that do worse than random.

## II.5 Baselines and how to implement each well

Every baseline gets the same splits, the same tuning budget, the same conformal wrapper and the same evaluation.

| Baseline | What it tests | Implementation notes (to make it strong) |
|---|---|---|
| **DMDc (tuned)** | the linear, full-observation, additive ceiling | Delays d ∈ {0, 1, 2, 4, 8}; POD rank r and input rank p by held-out-experiment CV; ridge; bias column for sustained inputs; bagged over experiments. Evaluate open-loop multi-step, not one-step. Also try TLS/optimised variants when noise is large. |
| **Controlled linear SSM** (EM, dynamax) | hidden-state linear baseline | Kalman encoder; initialise from subspace ID (F3), not at random; k sweep; B per channel **and** a feature-parametrised B for unseen targets; multi-step fine-tuning. |
| **Subspace ID** (CVA / N4SID / PBSID) | closed-form linear with an order rule | Horizon i ∈ {5, 10, 20}; CVA weighting; multi-experiment Hankel stacking; PBSID for adaptively collected data; enforce stability (project eigenvalues if needed, and report it). |
| **Full-state controlled model** (predictability upper bound) | how much is predictable at all | Two versions. (i) A learned model with access to the **full microstate x (all N units)** and the parameters: a linear full-state DMDc when N ≲ 2000, plus an MLP or neural-ODE full-state model. It uses the same training data. (ii) The **simulator itself** re-run with independent seeds, which gives the irreducible noise ceiling. All error metrics are also reported as a fraction of the gap between the input-only baseline and this upper bound. |
| **Input-only** | how much is predictable from u, a alone | Predicts the future readout from (u, a, pattern) and the time since onset, **without** any state, using an MLP or GBM. It gives the "state adds nothing" floor. |
| **Intervention-only** | the average effect per descriptor | E[Δy | ψ(a)], the mean effect per intervention descriptor (regression on ψ), with no state and no u. It sets the effect baseline for the effect metrics. |
| **Readout-history** | whether the readout history alone is a sufficient state | An ARX model on y_{t−w:t} and a (linear and MLP), with window w matched to the encoder window. This is the "readout copying" control: if it matches the latent model, z adds nothing beyond y. |
| **Intervention-ID → output direct** | memorisation of intervention identity | A lookup / regression from the intervention ID (one-hot) and the time since onset to the output. It must **fail** on held-out families by construction. If it does well there, the split leaks. |
| **Random projection + control** | whether the learned encoder beats an arbitrary linear map of the same k | z = Pᵀh_t, where P is Gaussian random (k columns) over the delay-embedded observations, with controlled linear (and MLP) dynamics fitted as in F1/F7. Average over 10 draws of P. |
| **PCA + control** | whether passive-variance dimensions suffice | z = PCA_k(h_t) with controlled linear or MLP dynamics and a read-in. This is the direct test of "k chosen by passive variance" versus "k chosen by intervention fidelity". |

## II.6 Measures, and their pitfalls

| Property | Recommended measure(s) | Pitfalls and guards |
|---|---|---|
| **Intervention prediction**, including near-zero effects | Effect error in noise-floor units: E = ‖Δŷ − Δy‖²/(σ²_d/R) per horizon, with Δy from paired runs with common random numbers. Energy score / CRPS on the trajectory distribution. Sign accuracy only for effects that pass the MDE test. The **four-way TOST classification** (§8.5) scored against the truth. | Never divide by the effect size when effects are ≈ 0. Report the MDE per family. Use common random numbers to lower the floor. Keep one-step and multi-step errors separate (one-step hides drift). |
| **State mediation** | (i) Read-in commutation error L_med on held-out data. (ii) **Controlled direct effect**: apply a, reset z to z(a₀) via a lift, and measure the remaining future effect in noise-floor units (≈ 0 if mediated). (iii) Residual-intervention cross-correlation R_{εa}(τ) of the model's innovations. | (ii) depends on lift quality, so report lift success alongside it. Mediation "passes" trivially when effects are tiny, so require superiority first. |
| **Interventional closure** | Closure gap C = NLL(z-only predictor) − NLL(z + ξ + a-ID predictor) on held-out data, in nats per step, with a bootstrap CI. Calibrate against the gap of the **full-state model** (bias) and against simulator-constructed equal-z nulls. The Markov / order test (Shi et al.). | No CI test is both valid and powerful (Shah & Peters), so use a fixed-capacity auxiliary predictor and report its capacity. An overfitting auxiliary predictor inflates C; an underpowered one hides it. Leakage (future information in ξ) inflates C spuriously. |
| **Microstate equivalence** | **Equivalence accuracy**: the fraction of equal-z pairs (‖Δz‖ < ε, microstates distinct and reachable) whose future readout laws are equivalent by TOST under shared probe interventions. Also the curve of the bisimulation-style ratio d_fut / ‖Δz‖. | Off-manifold microstates (interchange illusion), so construct pairs from genuinely reachable states (different histories converging in z). The probe set must include held-out kinds. |
| **Lift success** | The fraction of targets Δz* for which a lift was found, not abstained, **and** realised within ε in the simulator. The realised-vs-target error. Energy used vs model-predicted energy. | Report abstention separately (success conditional on attempting, and overall). Model exploitation, so always verify on the simulator. |
| **Multiple-lift consistency** | κ = D_between/mean‖Ȳ_i − Ȳ₀‖, with a permutation p-value and TOST equivalence of futures across ≥ 3 distinct lifts (§7.4). | Lifts that are "distinct" only trivially (enforce d_min); weak effects (superiority first). |
| **Held-out family generalisation** | All the above on families (kind × target group) unseen in training, including **leave-one-kind-out** splits. Report the ratio of held-out to in-family error. | Leakage through the descriptor (a new kind encoded like an old one); target features computed from test data. |
| **Dimension selection and uncertainty** | k̂ by the II.3 rule; the bootstrap distribution of k̂; accuracy against the known true k on simulators with ground truth; P(abstain) on "no compact state" systems. | Budget dependence (weak directions are lost first); dimension cheating (below). Report k and the read-in rank separately. |
| **Representation stability up to transformations** | Across seeds / bootstraps: CCA or Procrustes similarity of latents after the best affine map; state R² from true latents where known (CtD metric); cycle consistency; invariants (eigenvalues, fixed-point Jacobians, transfer functions) compared directly. | Comparing raw coordinates (meaningless under GL(k)); flexible nonlinear alignments that make anything look similar (use affine maps). |
| **Calibration / abstention** | Joint conformal coverage per horizon and per family, with a Clopper-Pearson CI; interval score; PIT; Brier score and reliability for "effect > floor" events; **risk-coverage curve, AURC**; **confident-wrong rate**; abstention rate per family. | Calibrating on actively chosen data; marginal coverage hiding per-family failures; bins over autocorrelated time steps. |
| **Information efficiency** | Experiments-to-target and CPU-seconds-to-target; normalised AUC of the learning curves; the efficiency ratio against random with a CI. | Unmatched budgets; untuned baselines; ignoring the acquisition compute. |

### Leakage and cheating pitfalls: checklist

1. **Future leakage.** Smoothing or bidirectional encoders (DKF-structured, LFADS, latent-ODE backward encoders, natural cubic
   splines in Neural CDEs), and normalisation statistics computed over whole trials.
   - **Guard:** filter-only encoders with a fixed window; a unit test that perturbs x_{>t} and asserts φ_t is unchanged.
2. **Output / input copying.** The readout y is fed to the encoder, or u is passed straight through to the prediction.
   - **Guard:** the readout-history and input-only baselines; φ must not take y as input unless declared.
3. **Intervention-ID memorisation.** a (or its one-hot ID) fed into the encoder or into the dynamics after the read-in.
   - **Guard:** a enters only R; the ID → output baseline; held-out families; a probe that decodes the a-ID from z should
     not beat decoding from the true post-intervention state.
4. **Dimension cheating through pathological encodings.** A k-dimensional z can encode arbitrary information through
   space-filling or near-discontinuous maps.
   - **Guard:** Lipschitz / spectral-norm limits on φ and on its inverse mapping; noise injection on z (VIB rate); measure
     the **effective information** in z (KL rate, in nats); require stability of representations across seeds.
5. **History hidden in large recurrent memories.** RSSM's deterministic h, LSTM recognition networks, a large window w.
   - **Guard:** count all recurrent memory in k, or bottleneck it.
   - **Guard:** report w; run a Markov / order test on z.
   - **Guard:** compare against a "same encoder, z replaced by the raw window" model. If that model does as well, the "state"
     is really a history buffer.
6. **Split leakage.** Windows of the same experiment in both train and test; calibration on training experiments.
   - **Guard:** split by experiment and by family, never by time step.
7. **Evaluation on the acquisition pool.** Active designs evaluated on data they chose.
   - **Guard:** a fixed independent evaluation set.

## II.7 Open problems (no good answer found in the literature)

1. **One interventional latent model for all intervention kinds.** None published handles additive, clamp,
   observation-level, bilinear and mechanism-change interventions together, with an identifiability theory for the mixture
   (§1.7, §1.9).
2. **Generalisation to unseen intervention *types*.** Theory covers new magnitudes (linear read-in, Rep4Ex), new combinations
   inside the span (additive shift; soft-intervention CRL), and new targets through structured features (no theorem). No
   result covers a new kind (for example, trained on kicks and tested on silencing). Held-out-kind benchmarks and abstention
   are the only safeguards.
3. **Identifiability with micro-level interventions, partial observation and a history-based causal encoder.** CRL assumes
   latent-level interventions and injective instantaneous mixing; iSSM assumes injective emission. Our setting violates both.
4. **Closure of multiplicative interventions in compressed coordinates.** Bilinear in x does not imply bilinear in z = Wx. The
   closure error of such reductions is not characterised.
5. **Valid and powerful closure tests.** Conditional-independence tests with high-dimensional continuous conditioning have no
   uniform validity (Shah & Peters). Simulator-generated nulls are a workaround whose power is unknown.
6. **Choosing the probe set** for "for every future intervention sequence" in equivalence and bisimulation tests.
7. **Estimating multiple realisability / strong abstraction.** The definitions exist; no estimation procedures or benchmarks.
8. **Designs that target the latent dimension** of a controlled state-space model. None found; II.4-A4/A5 is a synthesis.
9. **Dimension choice for intervention fidelity with calibrated uncertainty**, as opposed to passive order selection (Hankel
   gap, CVA / AIC, IB transitions). All existing rules are passive or input-output based.
10. **Mediation tests that need a lift.** Controlled and natural direct effects need z to be set exactly. Where lifts are
    imperfect, there is no published way to separate lift error from mediation failure.
11. **Shared dynamics across implementations.** No estimation method or benchmark for multiple low-level systems abstracting
    to one controlled latent model with implementation-specific read-ins, beyond abstraction theory.
12. **Calibrated uncertainty for new intervention kinds.** Ensembles are under-dispersed under shift (Ovadia et al.), and
    conformal methods need exchangeability with the calibration families.
13. **Active design under misspecification.** Sequential Bayesian design can become trapped at extreme designs (Rainforth et
    al.), and theory for active identification exists only for linear, bilinear and known-feature systems.

## II.8 Suggested build order (pragmatic)

1. Data infrastructure: the descriptor ψ(a), paired runs with common random numbers, the noise-floor estimator, experiment-
   and family-level splits, and the leakage unit tests.
2. Baselines (II.5) and the evaluation suite (II.6), including the conformal wrapper and TOST.
3. Linear families F2, F3, F1 (fast; they establish the linear ceiling and give initial k estimates).
4. F4 and F5 (bilinear / sparse read-ins for silencing and weakening).
5. F7 and F8 (neural), then F6 and F9.
6. The active loop with A1, A5 and A3 plus W, then A4 and A6. Fair-comparison runs.
7. F10 only after within-system validity is established on at least two implementations.

