"""Add missing contract fields to a few brief entries in the area notes (idempotent)."""


def patch(path, header, before_label, insert):
    s = open(path, encoding='utf-8').read()
    i = s.index(header)
    ends = [x for x in (s.find('\n### ', i + 5), s.find('\n---', i)) if x != -1]
    j = min(ends) if ends else len(s)
    ent = s[i:j]
    first_line = insert.strip().split('\n')[0]
    if first_line in ent:
        return  # already patched
    k = ent.index('- **' + before_label)
    s = s[:i] + ent[:k] + insert + ent[k:] + s[j:]
    open(path, 'w', encoding='utf-8').write(s)


A = 'notes/area_A_classical_sysid.md'
patch(A, "### Supporting result: persistency of excitation", 'Relevance',
"""- **Assumptions:** Discrete-time LTI (or a system with an exact finite linear Koopman embedding for the nonlinear extension),
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
""")
s = open(A, encoding='utf-8').read()
s = s.replace("- **Open-source implementations / simplicity:** Check is a single rank computation.",
"""- **Open-source implementations:** No dedicated package needed; numpy/scipy rank and SVD (BSD-3). Data-driven control
  toolboxes exist but were not checked.
- **From-scratch simplicity:** Simple: build the input block Hankel of depth L + n and check its rank/condition number.""")
open(A, 'w', encoding='utf-8').write(s)

D = 'notes/area_D_neural_ssm_odes.md'
s = open(D, encoding='utf-8').read()
s = s.replace("- **Use here:** As an **upper-bound predictor**",
              "- **Relevance to problem (props 1-8):** Use here as an **upper-bound predictor**", 1)
open(D, 'w', encoding='utf-8').write(s)
patch(D, "### Hamiltonian / Lagrangian neural networks", 'Relevance',
"""- **Assumptions:** Conservative (energy-preserving), autonomous dynamics in canonical coordinates (HNN) or with a Lagrangian
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
""")
patch(D, "### Hamiltonian / Lagrangian neural networks", 'References',
      "- **From-scratch simplicity:** Simple (autograd of a scalar MLP; symplectic or RK integration).\n")

F = 'notes/area_F_popdyn_similarity.md'
CMP = ("- **Intervention support:** N/A (comparison measure); can be applied to post-intervention latents to compare "
       "responses.\n- **Nonlinear capacity:** {nl}\n- **Interpretability:** {interp}\n")
patch(F, "### CCA, SVCCA and PWCCA", 'Scaling',
"""- **Nonlinear capacity:** Linear only (kernel CCA and deep CCA extensions exist; not reviewed).
- **Interpretability:** Moderate: canonical directions and correlations are readable; mean-correlation summaries hide which
  directions match.
""")
patch(F, "### Centered Kernel Alignment (CKA) and its critiques", 'Failure modes', CMP.format(
    nl="Linear CKA compares linear geometry; RBF-kernel CKA captures nonlinear (local) similarity with a bandwidth choice.",
    interp="Low: a single scalar with no decomposition into matching directions.")
    + "- **Scaling:** O(n^2 p) for Gram matrices (linear CKA can be computed in O(n p^2) via feature covariances); "
      "n = number of samples.\n")
patch(F, "### Orthogonal Procrustes, generalized shape metrics", 'Failure modes', CMP.format(
    nl="Linear alignment (orthogonal to linear); nonlinear differences show up as residual distance, not modelled.",
    interp="High: the optimal alignment and per-condition residuals are inspectable; a proper metric allows clustering of models.")
    + "- **Scaling:** O(n p^2 + p^3) per pair; pairwise distance matrices over many models scale quadratically in the "
      "number of models.\n")
patch(F, "### Principal angles between subspaces and RSA", 'Invariance',
"""- **Assumptions:** Principal angles: subspaces in a common ambient space (same units). RSA: a shared, meaningful set of
  conditions and a chosen dissimilarity measure.
- **Identifiability:** Subspaces (not bases) are compared; RDMs are invariant to transforms preserving the dissimilarity.
""")
patch(F, "### Principal angles between subspaces and RSA", 'Failure modes', CMP.format(
    nl="Principal angles: linear subspaces only. RSA: any representation, via the chosen (possibly nonlinear) dissimilarity.",
    interp="High for principal angles (angle spectrum per direction); moderate for RSA (RDM structure is inspectable).")
    + "- **Scaling:** Principal angles O(N k^2); RSA O(c^2 p) for c conditions plus permutation tests.\n")
patch(F, "### Dimensionality estimation", 'Relevance',
"""- **Identifiability:** Estimates a number, not coordinates. Linear estimators give embedding dimension; kNN estimators give
  the local intrinsic dimension of the sampled state cloud; neither identifies the closed-state dimension.
- **Intervention support:** None intrinsically; can be applied to post-intervention state clouds, whose dimension may exceed
  the unperturbed one.
- **Nonlinear capacity:** PR/PCA/bi-CV: linear. TwoNN/MLE/DANCo: nonlinear manifolds (under local-uniformity assumptions).
- **Interpretability:** High (a single number per scale), but easily misread as state dimension.
- **Scaling:** PCA O(n p^2); kNN estimators O(n log n) with trees or O(n^2) brute force; bi-CV requires repeated SVDs.
""")
patch(F, "### Reduced-rank regression / communication subspace", 'Scaling',
      "- **Interpretability:** High: rank-r predictive directions in X and their target patterns in Y are directly readable.\n")
print('patched')
