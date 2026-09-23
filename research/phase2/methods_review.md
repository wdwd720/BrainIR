# Phase 2 methods review: query-efficient discovery of compact causal sub-mechanisms in a signed directed dynamical network

Status: methods-only literature review, compiled 2026-09-23. Scope is deliberately generic: it covers
*how* to find a compact, sufficient, near-necessary, robust, transferable sub-mechanism in a black-box
dynamical simulator under a strict query budget. It contains no statements about which nodes or cell
types matter in any specific biological circuit, and none were consulted. Primary sources were
checked where practical (arXiv, journal pages, proceedings); entries marked "(not re-verified)" are
cited from memory of the primary source.

Contents

1. Problem abstraction and query-cost yardsticks
2. Method entries by area (A–O, 55 entries; several are grouped multi-paper entries)
3. Synthesis (a): tournament candidates
4. Synthesis (b): pitfalls and how the literature handles them
5. Synthesis (c): open questions
6. Compact index of all entries

---

## 1. Problem abstraction and query-cost yardsticks

### 1.1 The object we are learning

Let `V` be the node set (`N` = 20 to ~5,000), `u` the fixed drive into one node, `Y` the designated
output population, and `θ ~ P(θ)` the per-node parameter ensemble. The simulator gives two set
functions, both random through `θ`:

- `f(S; θ)` = readout when only `S ⊆ V` is kept (everything else silenced) — the **keep-only** or
  **sufficiency** query (~0.1 s for a small `S`).
- `g(A; θ)` = readout when `A ⊆ V` is silenced inside the full network — the **silence** or
  **necessity** query (~2.4 s).

A readout with a pass threshold turns each into a random Boolean test: `pass(S) = 1[f(S; θ) ≥ τ]`.
The discovery target is a compact `M` with

1. sufficiency: `E_θ[pass(M)]` (or a CVaR/quantile) high;
2. near-necessity: `g({i})` or `g(M)` drops the readout in the full network, for `i ∈ M`;
3. compactness: `|M|` small, unknown a priori;
4. robustness: (1)–(2) hold across the ensemble, not just at the mean `θ`;
5. stability: the same `M` (or the same posterior over `M`) is found across seeds and node orderings;
6. transfer: the mechanism found on graph `G_A` is found again on an independently reconstructed
   `G_B` implementing the same computation.

Two idealized structures anchor the theory below:

- **Monotone-DNF / hidden-hypergraph view.** If `pass(S) = 1` iff `S` contains at least one of
  several sufficient sets `T_1, …, T_s` (the "terms"), then `pass` is a monotone DNF with `s` terms of
  size ≤ `r`, and keep-only queries are exactly *membership queries* / *hyperedge-detecting queries*.
  The necessary nodes are the intersection of all terms (equivalently a hitting-set problem over the
  terms). Query-complexity theory for this model is mature (entries B2–B3) and gives the yardstick
  "logarithmic in `N`, exponential only in `r`".
- **Group-testing view.** If exactly one term exists and the response is (approximately) monotone in
  `S`, a keep-only query is a pooled test that is positive iff the pool contains all `r` members. This
  is the *complex* (AND-type) variant of group testing; the classical OR-type variant applies to the
  complementary silencing query when a single necessary node exists ("a test is positive iff the
  silenced pool contains a defective"). Inhibitory nodes make the tests non-monotone, which is the
  "inhibitor" group-testing model (entry B5).

Both views break when removal effects are non-monotone (disinhibition, gain normalization, backups),
so every family below is assessed on how it copes with non-monotonicity.

### 1.2 Query-cost yardsticks (best available theory)

| Task (idealized, noiseless unless noted) | Queries | Source |
|---|---|---|
| Find `k` defectives among `N` (adaptive OR-type group testing) | `≈ k·log2(N/k) + O(k)` (Hwang's generalized binary splitting; information bound `log2 C(N,k)`) | B1 |
| Same, non-adaptive, COMP decoder | `≈ e·k·ln N` | B1 |
| Learn an `r`-uniform hidden hypergraph with `m` edges by edge-detecting queries | `O(2^{4r}·m·poly(r, log N))`, adaptive | B2 |
| Exactly learn an `s`-term, size-`r` monotone DNF from membership queries | polynomial in `s`, logarithmic in `N`, exponential in `r`; "almost optimal" adaptive algorithms | B2 |
| Learn an arbitrary Boolean function of `r` relevant variables (junta) | `O(r·2^r·log N)` adaptive membership queries | B3 |
| 1-minimal failure-inducing subset under monotonicity (ddmin) | worst case `O(N^2)`; typical `O(k·log N)`; QuickXplain `O(2k·log(N/k) + 2k)` | B4 |
| Learn a `k`-Fourier-sparse set function of degree ≤ `d` | `O(k·d·log N)` random-subset evaluations | C3 |
| Recover a `k`-sparse linear weight vector from pooled perturbations | `O(k·log(N/k))` non-adaptive; adaptivity reduces the log factor to `O(k·log log(N/k))` | C1–C2 |
| Shapley values for `N` players by permutation sampling to precision `ε` | `Õ(N/ε^2)` coalition evaluations | G5 |

Budget arithmetic for this simulator: 5,000 keep-only calls ≈ 8 min CPU; 5,000 full-network calls
≈ 3.3 h; 200 full-network calls ≈ 8 min. Every candidate evaluated on `n_θ` ensemble draws costs
`n_θ` calls, so a 5,000-call budget with `n_θ = 16` is only ~300 distinct candidates unless racing
(I4) or shared-`θ` common random numbers are used. This asymmetry (cheap sufficiency tests, expensive
necessity tests) is the single most important design constraint and favours sufficiency-first search
with a small number of confirmatory silencing experiments.

---

## 2. Method entries by area

Field key for each entry: **Source** (authors, year, venue, link) · **Method** · **Assumptions** ·
**Cost** (query / compute) · **Relevance** (to this problem, specifically) · **Limits** · **As-is?**
(does the simulator support it unchanged: black-box, ensemble `θ`, keep-only/silence interventions,
no gradients) · **Budget?** (workable within 200–5,000 simulator calls).

### A. Active causal discovery, Bayesian experimental design, black-box intervention selection

**A1. Modern Bayesian experimental design (BED) — the umbrella framework**
- **Source:** Rainforth, Foster, Ivanova, Bickford Smith (2024), *Statistical Science* 39(1):100–114,
  [arXiv:2302.14545](https://arxiv.org/abs/2302.14545). Foundations: Foster et al. (2019) variational
  BOED, NeurIPS, [arXiv:1903.05480](https://arxiv.org/abs/1903.05480); Foster, Ivanova, Malik,
  Rainforth (2021) Deep Adaptive Design, ICML, [PMLR 139](https://proceedings.mlr.press/v139/foster21a.html);
  Kleinegesse & Gutmann (2020) MINEBED for implicit (simulator) models, ICML,
  [PMLR 119](https://proceedings.mlr.press/v119/kleinegesse20a.html).
- **Method:** choose the next design (here: an intervention set) maximizing expected information gain
  (EIG) about a latent (here: membership vector `z` and roles); EIG estimated by nested Monte Carlo or
  variational bounds; DAD amortizes the sequential policy; MINEBED handles likelihood-free simulators
  via mutual-information neural estimation.
- **Assumptions:** a prior and a likelihood (or a simulator) for the outcome given the design and the
  latent; EIG estimators need many simulator calls per candidate design unless a cheap surrogate
  likelihood is used.
- **Cost:** EIG estimation is the bottleneck: nested MC is `O(n_outer·n_inner)` likelihood
  evaluations per candidate design; cheap only when the likelihood is an analytic model of the
  simulator (e.g., a noisy monotone-DNF model), not the simulator itself.
- **Relevance:** the natural formalization of "which keep-only pool to test next" with a posterior over
  `z`; it directly yields calibrated `p(z_i = 1)`.
- **Limits:** myopic (one-step) EIG can be poor for combinatorial latents; amortized policies (DAD)
  need a training phase that itself costs many simulator calls or a surrogate.
- **As-is?** Partial — black-box and ensemble `θ` are fine if the likelihood is a cheap surrogate model
  of `pass(S)`; using the RK45 simulator inside EIG estimation is unaffordable.
- **Budget?** Yes with a surrogate likelihood (see B6 for the concrete group-testing instance); no if
  EIG is estimated by simulation.

**A2. Bayesian causal experimental design for structure learning (CBED / DiffCBED / ABCI / GO-CBED)**
- **Source:** Tigas, Annadani, Jesson, Schölkopf, Gal, Bauer (2022) "Interventions, where and how?",
  NeurIPS, [arXiv:2203.02016](https://arxiv.org/abs/2203.02016); Tigas et al. (2023) differentiable
  multi-target design, ICML, [PMLR 202](https://proceedings.mlr.press/v202/tigas23a.html); Toth et al.
  (2022) Active Bayesian Causal Inference, NeurIPS, [arXiv:2206.02063](https://arxiv.org/abs/2206.02063);
  Zhang, Dong, Liu, Huan (2025) GO-CBED, [arXiv:2507.07359](https://arxiv.org/abs/2507.07359).
- **Method:** maintain a posterior over SCMs (graph + mechanisms) with Bayesian causal-discovery
  models; pick intervention targets and values by EIG (or by EIG on a *specific* causal query, ABCI /
  GO-CBED, rather than on the whole graph); DiffCBED relaxes target selection to a continuous
  Gumbel-softmax problem; GO-CBED is non-myopic with an amortized transformer policy.
- **Assumptions:** interventions are hard/soft do-operations on variables with i.i.d. observational
  samples per intervention; posterior over DAGs from few hundred variables at most; acyclic SCMs.
- **Cost:** hundreds to thousands of interventional samples in the papers; each posterior update is a
  full Bayesian structure-learning step (minutes to hours).
- **Relevance:** the goal-oriented variants (ABCI, GO-CBED) are the right *shape*: our query is "which
  nodes constitute the mechanism", not "the whole graph". Multi-target designs (A3) also apply.
- **Limits:** our graph is known and cyclic (recurrent dynamics); the latent is not a DAG but a
  functional subgraph; SCM posteriors do not model rhythmic dynamics; heavy machinery for our `N`.
- **As-is?** No as published; the *acquisition logic* transfers, the SCM posterior does not.
- **Budget?** Marginal — the query-specific variants can be budgeted, but only after replacing the SCM
  posterior with a posterior over membership vectors.

**A3. Near-optimal multi-perturbation experimental design (submodular batch design)**
- **Source:** Sussex, Uhler, Krause (2021), NeurIPS, [arXiv:2105.14024](https://arxiv.org/abs/2105.14024).
- **Method:** design a *batch* of experiments each intervening on several variables at once, maximizing
  an informativeness objective (e.g., expected number of oriented edges / Bayesian objectives); proves
  submodularity of the objectives so greedy batch construction has `(1 − 1/e)`-type guarantees over a
  doubly exponential design space.
- **Assumptions:** causal structure learning under standard SCM assumptions; interventions are
  multi-target hard interventions.
- **Cost:** greedy over candidate composite interventions; polynomial in the number of candidates.
- **Relevance:** justifies *composite* interventions (silencing or keeping sets, not single nodes) and
  gives a template for building non-adaptive batches with guarantees — useful when we want to run many
  cheap keep-only pools in parallel.
- **Limits:** guarantees are for structure-learning objectives, not for functional readouts; needs a
  hypothesis space over which informativeness is computed.
- **As-is?** Partial — composite interventions are supported; the objective must be re-derived for the
  membership hypothesis space.
- **Budget?** Yes — batch design is cheap; the batch itself is the budget.

**A4. Active learning for optimal intervention design (target-matching acquisition)**
- **Source:** Zhang, Cammarata, Squires, Sapsis, Uhler (2023), *Nature Machine Intelligence*
  5:1066–1075, [doi:10.1038/s42256-023-00719-0](https://www.nature.com/articles/s42256-023-00719-0).
- **Method:** Bayesian updates of a (linear) causal model; a closed-form, causally informed acquisition
  function trades exploration against choosing interventions whose post-interventional mean is closest
  to a target; theory for linear SEMs with known DAG.
- **Assumptions:** known DAG, linear SEM (for guarantees), Gaussian noise, single-target or few-target
  interventions with a desired output.
- **Cost:** closed-form acquisition; each round one interventional experiment.
- **Relevance:** the "find interventions that produce a target output" framing is the mirror image of
  ours (find the minimal set whose retention produces the target readout); the closed-form acquisition
  is a model for cheap acquisition over a linear surrogate of `f(S)`.
- **Limits:** linearity and acyclicity are both violated by a recurrent rate model with a rhythmic
  readout; targets are means, not functional scores.
- **As-is?** No as published; the acquisition idea can be ported to a linear/quadratic surrogate over
  masks (I1).
- **Budget?** Yes for the acquisition; the surrogate quality is the limit.

**A5. Causal Bayesian optimization (CBO, MCBO)**
- **Source:** Aglietti, Lu, Paleyes, González (2020), AISTATS, [PMLR 108](https://proceedings.mlr.press/v108/aglietti20a.html);
  Sussex, Makarova, Krause (2023) Model-based CBO, ICLR (oral), [arXiv:2211.10257](https://arxiv.org/abs/2211.10257).
- **Method:** optimize a target variable by choosing *which* variables to intervene on and *at what
  value*, exploiting the causal graph to restrict to minimal intervention sets and to share information
  across intervention sets via do-calculus; MCBO learns a full system model (GP per mechanism) with
  cumulative-regret bounds.
- **Assumptions:** known DAG, hard interventions with continuous values, observational data to help,
  GP-modelable mechanisms; acyclic.
- **Cost:** BO-like: tens to a few hundred interventions; per-step cost dominated by GP fits over
  intervention sets (combinatorial in general, restricted by the graph).
- **Relevance:** the "minimal intervention set" logic (only manipulate variables that can matter for
  the target given the graph) is a structural prior we can use (M-side: ancestors of `Y` reachable from
  `u`), pruning `N` before any search.
- **Limits:** acyclic assumption; the intervention space is values-on-variables, not subset retention.
- **As-is?** Partial — graph-based pre-pruning transfers directly; the optimizer does not.
- **Budget?** Yes for the pruning step (zero simulator calls).

**A6. Differentiable structure learning from interventional data (DCDI, ENCO) — masks with Gumbel gates**
- **Source:** Brouillard, Lachapelle, Lacoste, Lacoste-Julien, Drouin (2020) DCDI, NeurIPS,
  [arXiv:2007.01754](https://arxiv.org/abs/2007.01754); Lippe, Cohen, Gavves (2022) ENCO, ICLR,
  [arXiv:2107.10483](https://arxiv.org/abs/2107.10483).
- **Method:** learn a graph by optimizing a likelihood over neural mechanisms with per-edge Bernoulli
  (Gumbel-sigmoid) gates; DCDI uses interventional likelihoods and an acyclicity penalty; ENCO models
  edge existence and orientation separately, with convergence guarantees without acyclicity constraints,
  scaling to hundreds of nodes using interventional data on each variable.
- **Assumptions:** i.i.d. samples per intervention; differentiable mechanisms; enough interventions
  (ENCO: intervention on every variable helps).
- **Cost:** gradient-based; thousands of gradient steps; data volume in the tens of thousands of samples.
- **Relevance:** the gate parametrization (independent Bernoulli logits per node/edge) is the same
  parametrization used by mask-pruning (F) and by EDAs (H); ENCO's separation of "existence" and
  "orientation" is a model for separating "membership" from "role".
- **Limits:** needs gradients through mechanisms and lots of data; learns a graph we already know.
- **As-is?** No (needs a differentiable forward model); Yes if the fixed-step RK4 variant is ported to
  an autodiff framework (see F2).
- **Budget?** No in simulator-call terms unless differentiable.

**A7. Adaptive submodularity, EC2 and adaptive-submodularity-ratio guarantees for sequential testing**
- **Source:** Golovin & Krause (2011), *JAIR* 42:427–486, [link](https://www.jair.org/index.php/jair/article/view/10731);
  Golovin, Krause, Ray (2010) EC2, NeurIPS, [arXiv:1010.3091](https://arxiv.org/abs/1010.3091);
  Fujii & Sakaue (2019) adaptive submodularity ratio, ICML, [PMLR 97](https://proceedings.mlr.press/v97/fujii19a.html).
- **Method:** if the expected marginal gain of a test is adaptive-submodular, the greedy adaptive policy
  (pick the test with best expected gain given observations so far) is within a constant / log factor of
  the optimal policy; EC2 gives such an objective for noisy Bayesian active learning over a finite
  hypothesis set (cut edges between equivalence classes); Fujii–Sakaue relax to an adaptive
  submodularity ratio for near-submodular cases.
- **Assumptions:** a finite (or sampled) hypothesis set with a prior; test outcomes conditionally
  independent given the hypothesis; noise handled via equivalence classes.
- **Cost:** per step, evaluate expected gain for each candidate test over the hypothesis sample:
  `O(#tests × #hypotheses)` cheap model evaluations, no simulator calls beyond the chosen test.
- **Relevance:** the principled backbone for adaptive keep-only testing when hypotheses are candidate
  mechanisms sampled from a prior (e.g., from graph structure); EC2 handles noisy pass/fail outcomes.
- **Limits:** hypothesis set must be enumerable or sampled; guarantees degrade when the outcome model
  is misspecified (non-monotone effects).
- **As-is?** Yes — black-box tests; ensemble `θ` enters as test noise.
- **Budget?** Yes — designed for it.

**A8. Active learning for level-set / threshold-boundary estimation (LSE, straddle)**
- **Source:** Gotovos, Casati, Hitz, Krause (2013), IJCAI, [PDF](https://www.ijcai.org/Proceedings/13/Papers/202.pdf);
  Bryan et al. (2005), NIPS, [link](https://proceedings.neurips.cc/paper/2005/hash/8e930496927757aac0dbd2438cb3f4f6-Abstract.html).
- **Method:** with a GP over the domain, classify points as above/below a threshold `τ`; sample where
  confidence bounds straddle `τ` (ambiguity), with sample-complexity guarantees (LSE).
- **Assumptions:** GP-smooth function over the design space; continuous or moderately sized discrete
  domain.
- **Cost:** BO-like; tens to hundreds of evaluations for low-dimensional domains.
- **Relevance:** our readout has a pass threshold; the question "is `S` sufficient?" is level-set
  classification over subsets, and "how robust is `M` across `θ`" is level-set estimation over `θ`
  (where the parameter space *is* continuous and GP-friendly).
- **Limits:** needs a kernel over subsets (Hamming / graph kernels; see I2); GP scaling.
- **As-is?** Yes for the `θ`-robustness sub-problem; Partial for subset space.
- **Budget?** Yes for `θ`-space; the subset space needs a sparse surrogate.

### B. Group testing, adaptive group testing, query learning of relevant variables

**B1. Group testing: information-theoretic view; adaptive splitting**
- **Source:** Aldridge, Johnson, Scarlett (2019), *Found. Trends Commun. Inf. Theory* 15(3–4):196–392,
  [arXiv:1902.06002](https://arxiv.org/abs/1902.06002); Hwang (1972), *JASA* 67:605–608 (generalized
  binary splitting; not re-verified); Sejdinovic & Johnson (2010) belief-propagation decoding of noisy
  group tests, Allerton, [arXiv:1010.2441](https://arxiv.org/abs/1010.2441).
- **Method:** pool items; a test is positive iff the pool contains a defective; adaptive binary
  splitting achieves `≈ k log2(N/k) + O(k)` tests; non-adaptive random designs with COMP/DD/SCOMP
  decoders need `≈ e k ln N`; noisy variants decoded by BP or maximum likelihood.
- **Assumptions:** OR-type monotone response; known or bounded `k`; symmetric or known noise.
- **Cost:** see table §1.2; decoding is linear to polynomial.
- **Relevance:** the necessity query `g(A)` (silence pool `A`; positive iff the readout breaks) is
  OR-type when there is a single necessary node set; but at 2.4 s per test the cheap regime is the
  *complementary* keep-only query, which is AND-type (B2). Both views set the `k log N` yardstick the
  greedy baseline should be judged against.
- **Limits:** inhibitory nodes and disinhibition break monotonicity (B5); multiple redundant
  mechanisms break the single-defective-set assumption; graded readouts are richer than binary tests
  (quantitative / semi-quantitative group testing uses them).
- **As-is?** Yes — pure black-box tests; ensemble `θ` = test noise.
- **Budget?** Yes — this is the regime it is built for.

**B2. Learning hidden hypergraphs / monotone DNF from membership (edge-detecting) queries**
- **Source:** Angluin & Chen (2006), *JMLR* 7:2215–2236, [link](https://jmlr.org/papers/v7/angluin06a.html);
  Abasi, Bshouty, Mazzawi (2014), ALT, [arXiv:1405.0792](https://arxiv.org/abs/1405.0792).
- **Method:** the target is a hypergraph whose hyperedges are the sufficient sets; a query on `S`
  returns whether `S` contains a hyperedge (i.e., `pass(S)`). Adaptive algorithms find edges by
  splitting positive pools and shrinking them; Abasi et al. give almost-optimal adaptive deterministic
  and randomized algorithms for `s`-term `r`-MDNF, linear-time in the query count.
- **Assumptions:** exact (noiseless) membership answers; monotone response; term size `r` small.
- **Cost:** `O(2^{4r} m poly(r, log N))` (Angluin–Chen, `r`-uniform, `m` edges); Abasi et al.: almost
  tight in `s` and `log N`, exponential in `r`.
- **Relevance:** this *is* the noiseless idealization of "find all minimal sufficient node sets with
  keep-only queries", including multiple equivalent mechanisms (several terms). It also says what the
  necessary set is (intersection of terms) and how to find it (hitting set).
- **Limits:** exponential in `r`; noise (ensemble `θ`) is not modelled; non-monotone responses violate
  the model; `N = 5,000` with `r ≈ 5–10` makes the constants matter.
- **As-is?** Yes for the query type; noise must be handled by repetition or by a Bayesian wrapper (B6).
- **Budget?** Marginal — feasible for small `r` and `s`, and greatly helped by graph-based pre-pruning
  (only nodes on `u → Y` paths).

**B3. Attribute-efficient learning of juntas (which variables are relevant?)**
- **Source:** Damaschke (2000), *Machine Learning* 41:197–215, [link](https://link.springer.com/article/10.1023/A:1007616604496);
  Bshouty & Costa (2016), ALT, [arXiv:1706.06934](https://arxiv.org/abs/1706.06934).
- **Method:** learn an arbitrary Boolean function of `N` variables that depends on at most `r` of them
  from membership queries; adaptive algorithm with `O(r 2^r log N)` queries; non-adaptive families of
  size `O(r 2^r log N + r 2^{2r})` exist; Bshouty–Costa tighten adaptive and non-adaptive bounds.
- **Assumptions:** noiseless membership queries; bounded number of relevant variables.
- **Cost:** as above; exponential in `r`, logarithmic in `N`.
- **Relevance:** does not assume monotonicity — the function may be non-monotone in its relevant
  variables — so it is the right yardstick when inhibitory/disinhibitory nodes are part of the
  mechanism. "Relevant variable" is exactly "member of the mechanism".
- **Limits:** noise, and `2^r` blows up beyond `r ≈ 12`.
- **As-is?** Yes for the query type (keep-only with the rest silenced is a membership query on `z`).
- **Budget?** Marginal — for `r ≤ 8` and `N = 5,000`, `r 2^r log2 N ≈ 25,000` in the worst case; the
  bound is loose and graph pre-pruning helps, but it shows why exact non-monotone identification needs
  priors.

**B4. Delta debugging (ddmin), probabilistic delta debugging, monotonicity assessment, QuickXplain**
- **Source:** Zeller & Hildebrandt (2002), *IEEE TSE* 28(2):183–200 (not re-verified); Wang, Shen,
  Chen, Xiong, Zhang (2021) ProbDD, ESEC/FSE, [PDF](https://xiongyingfei.github.io/papers/FSE21a.pdf);
  Tao & Xue (2025) probabilistic monotonicity assessment, EASE, [arXiv:2506.11614](https://arxiv.org/abs/2506.11614);
  Junker (2004) QuickXplain, AAAI (not re-verified).
- **Method:** ddmin repeatedly splits the current set into chunks and tests whether removing a chunk
  (or keeping only a chunk) preserves the property; returns a 1-minimal set. ProbDD keeps a per-element
  probability of being needed, tests the low-probability elements in blocks, and updates
  probabilities Bayesian-style; PMA adds a confidence function for monotonicity so that subsets can be
  excluded probabilistically when monotonicity is doubtful. QuickXplain finds a minimal conflicting
  subset with `O(2k log(N/k) + 2k)` consistency checks.
- **Assumptions:** monotonicity (supersets of a passing set pass) for the classical guarantees;
  deterministic property.
- **Cost:** ddmin worst case `O(N^2)`, typical `O(k log N)`; ProbDD provably better worst case and
  ~45–63 % fewer tests empirically; QuickXplain `O(k log(N/k))`.
- **Relevance:** the software-engineering literature already built the "reduce a large set to a
  minimal sufficient one with few black-box tests" tool, with probabilistic membership tracking
  (ProbDD gives per-element retention probabilities, i.e., a crude `p(z_i = 1)`).
- **Limits:** designed for deterministic properties; non-monotone effects can trap it in local minima
  (1-minimal, not cardinality-minimal); multiple minimal sets are found only by restarts.
- **As-is?** Yes — the property test is `pass(S)`; ensemble `θ` requires a stochastic property
  (majority over draws) which increases cost.
- **Budget?** Yes — a strong deterministic baseline complementary to backward elimination.

**B5. Non-monotone group testing: threshold tests, inhibitors, Boolean compressed sensing**
- **Source:** Damaschke (2006) threshold group testing, LNCS 4123 (not re-verified); Farach, Kannan,
  Knill, Muthukrishnan (1997) inhibitor model, *Compression and Complexity of Sequences* (not
  re-verified); Bui, Kuribayashi, Cheraghchi, Echizen (2018) generalized group testing with inhibitors,
  [arXiv:1810.01086](https://arxiv.org/abs/1810.01086); Atia & Saligrama (2012) Boolean compressed
  sensing and noisy group testing, *IEEE Trans. Inf. Theory*, [arXiv:0907.1061](https://arxiv.org/abs/0907.1061).
- **Method:** threshold GT: positive iff ≥ `u` positives (and negative iff ≤ `l`), with an ambiguous
  gap; inhibitor GT: an inhibitor in the pool forces a negative regardless of positives; GGTI classifies
  defectives, inhibitors and hybrids from non-adaptive designs; Boolean CS gives information-theoretic
  bounds for noisy OR-type tests.
- **Assumptions:** known structural form of the non-monotonicity (threshold, inhibitor); bounded
  numbers of each item type.
- **Cost:** more tests than plain GT (inhibitors typically add a multiplicative factor in the number of
  inhibitors); non-adaptive designs decodable in polynomial time.
- **Relevance:** signed graphs guarantee inhibitory members; a "keep-only" pool can fail because an
  inhibitory node that is *not* part of the mechanism suppresses the output, or succeed only when a
  disinhibitory pair is included. These models are the closest formal treatment; Bui et al. explicitly
  motivate GGTI by neuron classification.
- **Limits:** still binary tests with idealized response models; graded rhythmicity scores are richer
  than the model uses.
- **As-is?** Yes for the query type.
- **Budget?** Marginal — the added factor for inhibitors is the price of non-monotonicity.

**B6. Noisy adaptive group testing as Bayesian sequential experimental design (SMC posterior + EIG)**
- **Source:** Cuturi, Teboul, Berthet, Doucet, Vert (2020), [arXiv:2004.12508](https://arxiv.org/abs/2004.12508).
- **Method:** maintain the posterior over the binary status vector with sequential Monte Carlo
  (particles over `{0,1}^N`), given all noisy pooled tests so far; choose the next pools by maximizing
  a utility of the posterior (mutual information or AUC of the resulting ranking); works with arbitrary
  noise models and priors.
- **Assumptions:** a likelihood for a test outcome given the status vector (sensitivity/specificity or
  richer); prior prevalence; SMC particle count adequate for `N`.
- **Cost:** no simulator calls for planning; SMC over `N ≤ ~1,000` binary variables is routine; planning
  is `O(#candidate pools × #particles)`.
- **Relevance:** the most directly reusable *active* design: replace the infection-status vector by the
  membership vector `z`, the pooled test by a keep-only (AND-type) or silencing (OR-type) query, and the
  noise model by the ensemble variability of `pass(S; θ)`; the posterior marginals *are* the calibrated
  `p(z_i = 1)`, and SMC particles carry multiple competing mechanisms.
- **Limits:** the likelihood must encode the response model (AND-type with possible inhibitors);
  misspecification degrades calibration; SMC degeneracy in very high `N` without pre-pruning.
- **As-is?** Yes.
- **Budget?** Yes — designed for the few-hundred-tests regime.

**B7. Group testing for neural connectivity from ensemble stimulation (noisy GT, online inference)**
- **Source:** Draelos & Pearson (2020), NeurIPS, [link](https://proceedings.neurips.cc/paper/2020/hash/531d29a813ef9471aad0a5558d449a73-Abstract.html);
  Draelos, Naumann, Pearson (2020) ensemble stimulation, NeurIPS, [arXiv:2007.13911](https://arxiv.org/abs/2007.13911).
- **Method:** stimulate small random ensembles of neurons and observe responses; treat binarized
  connectivity as the defective set; a relaxation of ML inference is equivalent to Bayesian inference
  on binary links and solvable online; tests grow logarithmically with population size.
- **Assumptions:** approximately OR-type/linear response of a postsynaptic readout to ensemble
  stimulation; sparse connectivity.
- **Cost:** `O(log N)` tests per link under the stated assumptions; online updates.
- **Relevance:** demonstrates the group-testing → neural-perturbation mapping in a neuroscience
  setting, with noise, online inference and a fixed experimental budget — the same ingredients as our
  keep-only screens.
- **Limits:** targets connectivity, not a functional readout of dynamics; linear/OR-type response.
- **As-is?** Yes in spirit (ensemble = pool).
- **Budget?** Yes.

**B8. Group testing as a pre-screen for high-dimensional black-box optimization (GTBO)**
- **Source:** Hellsten, Hvarfner, Papenmeier, Nardi (2023), [arXiv:2310.03515](https://arxiv.org/abs/2310.03515).
- **Method:** phase 1 tests groups of variables for influence on the objective (extending group testing
  to continuous responses); phase 2 runs BO focused on the identified active dimensions.
- **Assumptions:** axis-aligned sparsity (few active variables); additive-ish influence detectable by
  group perturbations.
- **Cost:** group-testing phase `O(k log N)` evaluations, then standard BO.
- **Relevance:** the two-phase pattern — cheap group screen to shrink `N` from thousands to tens, then a
  richer surrogate over the survivors — is a template for combining B6 with I1/I2.
- **Limits:** interactions between active variables can hide them from single-group screens (the
  paper's assumption is axis-aligned).
- **As-is?** Yes.
- **Budget?** Yes.

### C. Compressed sensing and sparse recovery under nonlinear responses

**C1. Compressed sensing of neural circuits from pooled perturbations (RESCUME; Lasso over pooled
inhibition; model-based CS for holographic ensemble stimulation)**
- **Source:** Hu, Leonardo, Chklovskii (2009) RESCUME, NeurIPS, [index](https://mlanthology.org/neurips/2009/hu2009neurips-reconstruction/);
  Lee et al. (2018), *Nature Methods* 16:126–133, [doi](https://www.nature.com/articles/s41592-018-0233-6);
  Triplett, Gajowa, Antin, Sadahiro, Adesnik, Paninski (2025), *Nature Neuroscience*,
  [doi](https://www.nature.com/articles/s41593-025-02053-7); Shababo, Paige, Pakman, Paninski (2013)
  Bayesian inference and online design for circuit mapping, NeurIPS,
  [link](https://proceedings.neurips.cc/paper/2013/hash/17c276c8e723eb46aef576537e9d56d0-Abstract.html).
- **Method:** perturb random pools (stimulate or inhibit several units at once), measure a scalar
  readout, and solve an L1-regularized (or Bayesian sparse) regression `M w ≈ p` with a binary design
  matrix `M` (pool membership) to recover the sparse per-unit weight vector `w`; Lee et al. quantify
  `~n log N` measurements versus `N` one-at-a-time and test additivity; Triplett et al. add a
  model-based likelihood (photocurrent/synaptic model) and adaptive designs; Shababo et al. add online
  Bayesian optimal design (about half the trials for equal posterior quality).
- **Assumptions:** approximately additive (linear) contributions of units to the readout; sparsity;
  known pool membership.
- **Cost:** `O(k log(N/k))` pooled measurements for linear responses; adaptive designs reduce further.
- **Relevance:** closest neuroscience precedent for "few pooled perturbations recover a sparse set of
  functionally relevant units"; the binary design matrix is exactly a set of keep-only or silence
  pools; the reported failure mode (single promoters as "single points of failure", weights smeared by
  error propagation) is our redundancy/aliasing pitfall.
- **Limits:** linear-additivity assumption is the crux; a rhythmicity readout of a recurrent network is
  strongly non-additive (a mechanism needs all its members: AND, not SUM).
- **As-is?** Yes for pooling; No for the linear decoder as the primary inference.
- **Budget?** Yes for measurement counts; validity is the issue, not budget.

**C2. Sparse recovery with nonlinear / 1-bit observations; the power of adaptivity**
- **Source:** Plan & Vershynin (2016), *IEEE Trans. Inf. Theory* 62:1528–1537,
  [arXiv:1502.04071](https://arxiv.org/abs/1502.04071); Indyk, Price, Woodruff (2011), FOCS,
  [arXiv:1110.3850](https://arxiv.org/abs/1110.3850).
- **Method:** for single-index models `y = φ(⟨a, w⟩)` with unknown (even non-monotone or 1-bit) `φ`
  and *Gaussian* designs `a`, the generalized Lasso recovers `w` up to scale with `O(k log(N/k))`
  measurements; with adaptivity, sparse recovery needs only `O(k log log(N/k))` measurements.
- **Assumptions:** Gaussian (or sub-Gaussian) measurement vectors — not binary pool indicators; a
  single linear index inside the nonlinearity.
- **Cost:** see above.
- **Relevance:** sets the theoretical *limit*: even with unknown link functions, support recovery from
  pooled linear indices is possible, but only for one linear index; an AND-type mechanism is not a
  single-index model of pool membership, so CS guarantees do not transfer to sufficiency of a
  multi-node mechanism. Adaptivity's log-factor gains motivate adaptive rather than random designs.
- **Limits:** binary 0/1 designs lack the isotropy the theory needs; recurrent dynamics are not
  single-index.
- **As-is?** Partial (pools yes, Gaussian designs no — "graded" keep-only via partial silencing gains
  would approximate continuous designs if the simulator allowed scaled masks).
- **Budget?** Yes for counts.

**C3. Learning Fourier-sparse set functions (interaction-aware, query-efficient)**
- **Source:** Stobbe & Krause (2012), AISTATS, [PMLR 22](https://proceedings.mlr.press/v22/stobbe12.html);
  Amrollahi, Zandieh, Kapralov, Krause (2019), NeurIPS,
  [link](https://proceedings.neurips.cc/paper/2019/hash/c77331e51c5555f8f935d3344c964bd5-Abstract.html);
  Wendler, Amrollahi, Seifert, Krause, Püschel (2021) non-orthogonal Fourier bases, AAAI,
  [arXiv:2010.00439](https://arxiv.org/abs/2010.00439); Kang et al. (2025) SPEX, ICML,
  [arXiv:2502.13870](https://arxiv.org/abs/2502.13870).
- **Method:** treat `f(S)` as a set function on `{0,1}^N` and assume its Walsh–Hadamard (or a
  non-orthogonal) spectrum is `k`-sparse with degree ≤ `d`; recover it from `O(k d log N)` random or
  structured subset evaluations using sparse-FFT / channel-decoding algorithms (SPEX scales to ~1,000
  variables for interaction attribution of LLMs).
- **Assumptions:** spectral sparsity and low degree; noise tolerated by robust decoders.
- **Cost:** `O(k d log N)` queries, near-linear decoding time.
- **Relevance:** the only sparse-recovery family whose model class *includes* AND-type interactions
  (a `r`-node mechanism is a degree-`r` term); learned spectra directly give interaction indices,
  i.e., non-additive group effects and functional roles; Wendler et al.'s non-orthogonal bases model
  "value is realized only if a whole set is present", which is the sufficiency structure.
- **Limits:** degree `d = r` in the query count; the rhythmicity score of a recurrent network may not be
  spectrally sparse in the exact sense (many small interactions); ensemble noise reduces the effective
  sparsity.
- **As-is?** Yes — random keep-only subsets are the required queries.
- **Budget?** Marginal to Yes: for `k ≈ 50`, `d ≈ 5`, `N = 5,000`: `k d log2 N ≈ 3,000`; pre-pruning
  reduces this.

### D. Sparse dynamical-system identification

**D1. SINDy and successors (E-SINDy bagging, weak-form SINDy, UQ-SINDy, SINDy-PI, active SINDy,
weak-form SINDy on network dynamics)**
- **Source:** Brunton, Proctor, Kutz (2016), *PNAS* 113:3932–3937, [doi](https://www.pnas.org/doi/10.1073/pnas.1517384113);
  Fasel, Kutz, Brunton, Brunton (2022) E-SINDy, *Proc. R. Soc. A* 478:20210904,
  [doi](https://royalsocietypublishing.org/doi/10.1098/rspa.2021.0904); Messenger & Bortz (2021)
  WSINDy, *Multiscale Model. Simul.* 19:1474–1497, [doi](https://doi.org/10.1137/20M1343166); Hirsh,
  Barajas-Solano, Kutz (2022) UQ-SINDy, *R. Soc. Open Sci.* 9:211823,
  [doi](https://royalsocietypublishing.org/doi/10.1098/rsos.211823); Kaheman, Kutz, Brunton (2020)
  SINDy-PI, *Proc. R. Soc. A* (not re-verified); Larrañaga, Fasel, Brunton (2026) active learning for
  sparse model discovery, [arXiv:2606.12182](https://arxiv.org/abs/2606.12182); Tian, Messenger,
  Dukic, Rodríguez, Bortz (2026) WSINDy for network dynamics with multiple initial conditions,
  [arXiv:2605.30432](https://arxiv.org/abs/2605.30432).
- **Method:** regress time derivatives (or weak-form integrals) of observed state trajectories on a
  library of candidate terms with sparsity-promoting regression; bagging gives inclusion
  probabilities and robustness in low-data/high-noise regimes; sparsifying priors (spike-and-slab,
  horseshoe) give posterior inclusion probabilities; active variants query the most informative
  trajectories; network variants learn effective low-dimensional ODEs from ensembles of trajectories.
- **Assumptions:** access to state trajectories (not just a scalar readout); the true dynamics lie in
  the library; per-term sparsity.
- **Cost:** data-driven, not query-driven: a few trajectories suffice when the library is right;
  regression is cheap.
- **Relevance:** our simulator exposes full state trajectories at no extra cost, so SINDy-type
  regression on the *retained* mechanism's trajectories can (i) give a compact executable description
  of `M` (an "effective ODE" of a handful of variables), (ii) provide inclusion probabilities for
  coupling terms (roles), and (iii) serve as a fast surrogate of the dynamics of candidate subsets. It
  is not a subset-search method.
- **Limits:** the library must contain the rate-model nonlinearity; ensemble variability in `θ` moves
  coefficients; rhythmic regimes near bifurcations are hard for derivative-based fits (weak form helps).
- **As-is?** Yes (trajectories are available; black-box is irrelevant for regression).
- **Budget?** Yes — uses trajectories from queries already made.

### E. Neural-circuit discovery methods from computational neuroscience

**E1. Degeneracy and parameter ensembles: many parameter sets, same function**
- **Source:** Prinz, Bucher, Marder (2004), *Nature Neuroscience* 7:1345–1352, [doi](https://www.nature.com/articles/nn1352);
  Edelman & Gally (2001) degeneracy, *PNAS* 98:13763–13768 (not re-verified); Transtrum et al. (2015)
  sloppy models, *J. Chem. Phys.* 143:010901 (not re-verified); Gonçalves et al. (2020) SBI for
  mechanistic neural models, *eLife* 9:e56261 (not re-verified); Cranmer, Brehmer, Louppe (2020),
  *PNAS* 117:30055–30062 (not re-verified).
- **Method:** brute-force or SBI exploration of parameter space to find the set of parameterizations
  consistent with a functional criterion; reveals that widely disparate parameter combinations yield
  indistinguishable network activity (degeneracy) and that many parameter directions are "sloppy".
- **Assumptions:** a simulator and a functional criterion; density estimation or grid search over `θ`.
- **Cost:** Prinz et al. simulated >20 million model versions of a 3-cell circuit; SBI amortizes with
  neural density estimators (thousands of simulations).
- **Relevance:** defines what "robust across the ensemble" means operationally (a mechanism is a
  region of `θ`-space, not a point) and warns that the readout may be preserved by *different*
  sub-mechanisms at different `θ` — multiple equivalent mechanisms are expected, not exceptional.
- **Limits:** parameter-space exploration, not node-subset search; expensive at scale.
- **As-is?** Yes.
- **Budget?** Partial — a few hundred `θ` draws suffice to characterize robustness of a *given* `M`; not
  a search method.

**E2. Lesion / in-silico ablation analysis and its interpretive perils**
- **Source:** Alstott, Breakspear, Hagmann, Cammoun, Sporns (2009) modeling lesion impact, *PLoS
  Comput. Biol.* 5:e1000408 (not re-verified); Aerts, Fias, Caeyenberghs, Marinazzo (2016), *Brain*
  139:3063–3083 (not re-verified); Jonas & Kording (2017), *PLoS Comput. Biol.* 13:e1005268,
  [preprint](https://www.biorxiv.org/content/10.1101/055624.full.pdf); Wolff & Ölveczky (2018),
  *Curr. Opin. Neurobiol.* 49:84–94 (not re-verified).
- **Method:** systematically remove nodes/edges of a network model and measure the change in a
  functional or dynamical readout; rank by effect; interpret in light of compensation, off-target and
  distributed-function caveats.
- **Assumptions:** single-lesion effects are informative about function.
- **Cost:** `N` full-network simulations for single lesions (`≈ 3.3 h` at `N = 5,000` here); pairs are
  `O(N^2)`.
- **Relevance:** single-node silencing in the full network is our necessity query, and the most
  natural (but expensive) baseline; the microprocessor study shows single-lesion rankings can be
  systematically misleading about mechanism, which is the strongest argument for multi-perturbation
  and sufficiency-based designs.
- **Limits:** cannot see redundancy (backups) or higher-order interactions; costly.
- **As-is?** Yes.
- **Budget?** No for exhaustive single lesions at `N = 5,000`; Yes on a pre-pruned candidate set.

**E3. Multi-perturbation Shapley-value analysis (MSA) for causal function localization**
- **Source:** Keinan, Sandbank, Hilgetag, Meilijson, Ruppin (2004), *Neural Computation* 16:1887–1915,
  [doi](https://doi.org/10.1162/0899766041336387); Zavaglia & Hilgetag (2016), *Brain Struct. Funct.*
  221:2553–2568; Fakhar & Hilgetag (2022), *PLoS Comput. Biol.* 18:e1010250,
  [doi](https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010250);
  Wang & Jia (2023) Data Banzhaf (noise-robust semivalue), AISTATS, [arXiv:2205.15466](https://arxiv.org/abs/2205.15466).
- **Method:** treat nodes as players and the readout under a lesion configuration as the coalition
  value; estimate Shapley values (fair marginal contributions averaged over orderings) and
  interaction indices by sampling perturbation configurations; the Banzhaf value is more robust to
  noisy value functions.
- **Assumptions:** the value function is evaluable for arbitrary coalitions (it is: keep-only `S`);
  sampling estimators need many coalitions.
- **Cost:** `Õ(N/ε^2)` coalition evaluations for all `N` players; interaction indices cost more.
- **Relevance:** the established comp-neuro answer to "which elements contribute, given non-additive
  interactions", with an axiomatic notion of contribution that handles redundancy by averaging (which
  also hides it); interaction indices expose synergy (AND) versus redundancy (OR) explicitly.
- **Limits:** averaging over coalitions is exactly what we do *not* want for a mechanism that only
  works when complete; budget-heavy at `N = 5,000`; Shapley values are not membership probabilities.
- **As-is?** Yes.
- **Budget?** No for all nodes; Yes on ≤ ~50 pre-screened candidates as a role/interaction diagnostic.

**E4. Active experimental design for circuit mapping (Beta–Bernoulli inference + ambiguity acquisition)**
- **Source:** Morra, Fouke, Traubert, Naumann (2026) OPhELIA, [arXiv:2607.12930](https://arxiv.org/abs/2607.12930);
  see also Shababo et al. (2013) in C1.
- **Method:** Beta–Bernoulli posterior over binary connectivity, an ambiguity-based acquisition
  heuristic (test where the posterior is most uncertain), learned priors from pre-stimulation activity;
  reports connectome recovery with ~5 % of exhaustive trials.
- **Assumptions:** binary link model; conditionally independent trials; informative priors from
  baseline data.
- **Cost:** low per-step planning; trials as needed.
- **Relevance:** a minimal, practical active-learning loop with calibrated Bernoulli marginals; the
  "priors from baseline activity" idea maps to "priors from graph structure / signed path counts" for
  membership.
- **Limits:** independence across links; connectivity rather than function.
- **As-is?** Yes.
- **Budget?** Yes.

**E5. Connectome-constrained models with in-silico perturbation (ensembles of fitted models)**
- **Source:** Lappalainen et al. (2024), *Nature* 634:1132–1140, [doi](https://www.nature.com/articles/s41586-024-07939-3)
  (cited generically for methodology only).
- **Method:** a network model whose connectivity is fixed by a connectome and whose unknown
  single-neuron/synapse parameters are fitted to a task objective; an *ensemble* of such models is
  trained from different seeds; predictions (including in-silico perturbations) are made at the
  ensemble level and checked for consistency across models.
- **Assumptions:** connectome fixes the wiring; parameters are learnable/identifiable only up to an
  ensemble.
- **Cost:** training-time heavy; perturbation experiments are ordinary forward passes.
- **Relevance:** establishes the "ensemble of parameterizations, report only ensemble-consistent
  mechanisms" protocol we need for criterion (4); also a reminder that in-silico perturbation claims
  must be qualified by ensemble disagreement.
- **Limits:** methodology, not a subset-search algorithm.
- **As-is?** Yes (our `θ` ensemble plays the role of the trained-model ensemble).
- **Budget?** Yes.

### F. Differentiable / L0 / hard-concrete pruning, Gumbel-softmax, straight-through masks

**F1. L0 regularization with hard-concrete gates; Concrete/Gumbel-softmax; straight-through estimator**
- **Source:** Louizos, Welling, Kingma (2018), ICLR, [arXiv:1712.01312](https://arxiv.org/abs/1712.01312);
  Jang, Gu, Poole (2017), ICLR, [arXiv:1611.01144](https://arxiv.org/abs/1611.01144); Maddison, Mnih,
  Teh (2017), ICLR, [arXiv:1611.00712](https://arxiv.org/abs/1611.00712); Bengio, Léonard, Courville
  (2013) STE, [arXiv:1308.3432](https://arxiv.org/abs/1308.3432); Yin et al. (2019) STE analysis,
  ICLR, [arXiv:1903.05662](https://arxiv.org/abs/1903.05662).
- **Method:** each unit gets a stochastic gate `z_i ∈ [0,1]` with a hard-concrete (stretched, clipped
  binary Concrete) distribution parameterized by a logit; the expected L0 penalty is differentiable in
  the logits; gradients flow through the reparameterized gate; STE uses a hard threshold forward and a
  surrogate gradient backward.
- **Assumptions:** the loss is differentiable in the gated forward pass.
- **Cost:** one forward+backward per step; hundreds to thousands of steps; gate logits give
  `P(z_i = 1)` at convergence (not a calibrated posterior).
- **Relevance:** the most query-efficient family *if* a differentiable simulator exists: the fixed-step
  RK4 rate model (~0.8 s) is a straightforward autodiff port; masks on nodes (keep-only = multiply the
  rate by `z_i`) or edges (weights × gate) with L0 penalty and a differentiable proxy of the
  rhythmicity score (e.g., spectral power ratio) directly optimize "compact and sufficient".
- **Limits:** local optima and sensitivity to relaxation temperature; gate probabilities are
  overconfident; rhythmicity scores with thresholds need differentiable proxies; gradient through long
  rollouts of an oscillator can explode (chaotic sensitivity).
- **As-is?** No (no gradients); Yes after porting RK4 to JAX/PyTorch, which is a bounded engineering
  task.
- **Budget?** Not applicable in call-count terms (each step is one differentiable simulation);
  wall-clock is competitive (a few hundred steps ≈ minutes).

**F2. Mask-based circuit/structure pruning in practice (head pruning, differentiable masking, Edge Pruning)**
- **Source:** Voita, Talbot, Moiseev, Sennrich, Titov (2019), ACL, [link](https://aclanthology.org/P19-1580/);
  De Cao et al. (2020) differentiable masking, EMNLP (not re-verified); Bhaskar, Wettig, Friedman,
  Chen (2024) Edge Pruning, NeurIPS spotlight, [arXiv:2406.16778](https://arxiv.org/abs/2406.16778).
- **Method:** learn hard-concrete gates on components (heads) or on *edges* of the computation graph
  (Edge Pruning disentangles the residual stream so each edge can be gated), with a faithfulness loss
  (KL to the full model) plus an L0 sparsity penalty; Edge Pruning is the most faithful automated
  method on standard tasks and scales to 13B-parameter models.
- **Assumptions:** differentiable forward pass; a faithfulness metric comparable across sparsity levels.
- **Cost:** gradient steps over the full model; no combinatorial search.
- **Relevance:** the modern mechanistic-interpretability default for "find a sparse subgraph that
  preserves behaviour", i.e., criteria (1) and (3) at once; edge-level gating maps onto our signed
  edges and would yield the sub-mechanism as a wiring diagram, not just a node set.
- **Limits:** same as F1; results vary with seeds and ablation type (see J4); faithfulness ≠ necessity.
- **As-is?** No without differentiable port; Yes with it.
- **Budget?** Same as F1.

**F3. Probabilistic reparameterization for discrete BO acquisition (black-box-compatible relaxation)**
- **Source:** Daulton, Wan, Eriksson, Balandat, Osborne, Bakshy (2022), NeurIPS,
  [arXiv:2210.10199](https://arxiv.org/abs/2210.10199).
- **Method:** optimize the acquisition function over a *distribution* of discrete designs (independent
  Bernoulli per binary variable) so that the expected acquisition is differentiable in the Bernoulli
  parameters; Monte Carlo gradients; the objective itself stays black-box.
- **Assumptions:** a surrogate model over discrete inputs; acquisition evaluable on samples.
- **Cost:** acquisition-side compute only.
- **Relevance:** the bridge between the mask-relaxation idea and a black-box simulator: mask logits are
  optimized through the *surrogate*, not through the simulator; the same Bernoulli-product family is
  what CEM/PBIL (H1–H2) and hard-concrete gates use.
- **Limits:** surrogate quality; independence of Bernoulli factors ignores mechanism co-membership
  (SMC particles, H5, keep joint structure).
- **As-is?** Yes.
- **Budget?** Yes.

### G. Combinatorial subset selection, submodularity and non-submodular guarantees, formal minimal explanations

**G1. Submodular maximization and greedy guarantees**
- **Source:** Nemhauser, Wolsey, Fisher (1978), *Math. Programming* 14:265–294 (not re-verified);
  Krause & Golovin (2014) "Submodular function maximization", in *Tractability*, CUP (not re-verified).
- **Method:** for monotone submodular `f`, forward greedy under a cardinality constraint achieves
  `1 − 1/e`; greedy for submodular cover achieves `O(log N)`; lazy evaluations and stochastic greedy
  cut evaluations.
- **Assumptions:** monotone submodular set function; exact evaluations.
- **Cost:** `O(N k)` evaluations naive; `O(N log(1/ε))` with stochastic greedy.
- **Relevance:** the reference theory for both forward selection (add the node that most raises the
  readout) and the baseline backward elimination; tells us what breaks: a sufficiency readout of a
  mechanism is *supermodular-like* (nodes are worthless until the set is complete), so neither greedy
  direction has a guarantee.
- **Limits:** the readout is not submodular; `O(N k)` full evaluations is unaffordable at `N = 5,000`.
- **As-is?** Yes.
- **Budget?** No for forward greedy from scratch; Yes on a pre-pruned set.

**G2. Guarantees beyond submodularity: submodularity ratio, curvature, weak submodularity, difference
of submodular and modular**
- **Source:** Das & Kempe (2018), *JMLR* 19(3):1–34, [link](https://jmlr.org/papers/v19/16-534.html);
  Bian, Buhmann, Krause, Tschiatschek (2017), ICML, [PMLR 70](http://proceedings.mlr.press/v70/bian17a.html);
  Elenberg, Khanna, Dimakis, Negahban (2018), *Ann. Statist.* 46:3539–3568,
  [arXiv:1612.00804](https://arxiv.org/abs/1612.00804); Harshaw, Feldman, Ward, Karbasi (2019), ICML,
  [PMLR 97](https://proceedings.mlr.press/v97/harshaw19a.html).
- **Method:** greedy achieves `1 − e^{−γ}` for submodularity ratio `γ`, and `(1/α)(1 − e^{−γα})` with
  generalized curvature `α` (tight); RSC of the objective implies weak submodularity; `f = g − c` with
  `g` weakly submodular and `c` modular (e.g., a size penalty) admits distorted-greedy guarantees.
- **Assumptions:** the ratio/curvature can be bounded (often by data-dependent quantities).
- **Cost:** same as greedy.
- **Relevance:** tells us exactly *when* a simulation-guided greedy can be trusted: only if the
  readout, as a set function of retained nodes, has non-trivial `γ`. A "complete-or-nothing"
  mechanism has `γ ≈ 0` for forward greedy; backward elimination from the full set behaves better
  (removing a non-member changes little) but has no guarantee against redundancy (removing either of two
  backups is free, removing both is fatal). Harshaw's `g − c` form is our "readout minus size
  penalty".
- **Limits:** bounds are loose or vacuous for strongly synergistic objectives.
- **As-is?** Yes.
- **Budget?** As G1.

**G3. Necessity and sufficiency as explanation primitives; abductive (formally minimal) explanations;
black-box minimal-subset attribution**
- **Source:** Watson, Gultchin, Taly, Floridi (2021), UAI, [PMLR 161](https://proceedings.mlr.press/v161/watson21a.html);
  Ignatiev, Narodytska, Marques-Silva (2019), AAAI, [link](https://ojs.aaai.org/index.php/AAAI/article/view/3964);
  Chen et al. (2025/2026) minimal interpretable subset selection, [arXiv:2504.00470](https://arxiv.org/abs/2504.00470).
- **Method:** Watson et al. define probabilities of necessity and sufficiency of factor sets w.r.t. a
  context and give a sound and complete algorithm to enumerate minimal explanatory factors; Ignatiev
  et al. compute subset- or cardinality-minimal sufficient reasons (prime implicants) with an oracle
  (SAT/SMT/MILP) — exact but needs a logical encoding; Chen et al. cast minimal sufficient
  explanation as submodular subset selection solved by bidirectional greedy with black-box queries.
- **Assumptions:** for the formal route, a symbolic encoding of the model; for the probabilistic route,
  a sampling distribution over contexts (here: `θ`).
- **Cost:** formal: NP-oracle calls (exponential worst case); probabilistic/greedy: `O(N k)` queries.
- **Relevance:** gives the *definitions* we need for criteria (1)–(2) under an ensemble — `PS(M)`,
  `PN(M)` as `θ`-probabilities — and the minimal-hitting-set duality between the family of minimal
  sufficient sets and minimal necessary sets.
- **Limits:** the formal route does not scale to a dynamical simulator; the greedy route inherits G1–G2
  caveats.
- **As-is?** Yes (probabilistic route).
- **Budget?** Yes for computing `PS/PN` of *given* candidates; search is the expensive part.

**G4. Connectivity-constrained subnetwork extraction (prize-collecting Steiner forest)**
- **Source:** Tuncbag et al. (2013), *J. Comput. Biol.* 20:124–136, [doi](https://doi.org/10.1089/cmb.2012.0092)
  (not re-verified).
- **Method:** given node prizes (evidence of involvement) and edge costs, find the forest connecting
  high-prize nodes at minimal cost (a Steiner-type problem solved by MILP/message passing); yields
  compact, connected pathway hypotheses in systems biology.
- **Assumptions:** the mechanism is a connected subgraph; prizes/costs are meaningful.
- **Cost:** zero simulator calls; combinatorial solver on the graph (seconds to minutes at `N = 5,000`).
- **Relevance:** the mechanism must connect the driven node to the output population; combining
  posterior marginals (prizes) with signed-edge costs gives a structural completion step that converts
  a fuzzy membership vector into a concrete executable subgraph, and a candidate generator for group
  tests.
- **Limits:** connectivity is necessary not sufficient; cycles (feedback) are essential for rhythm and
  Steiner *trees* ignore them — use minimum-cost connected subgraph with a feedback constraint instead.
- **As-is?** Yes.
- **Budget?** Yes (no calls).

**G5. Marginal-contribution estimators under noise (see E3) and their query cost**
- Covered in E3; recorded here for the query-cost table: permutation sampling `Õ(N/ε^2)`; the
  group-testing Shapley estimator and Banzhaf's maximum-sample-reuse estimator are more sample-
  efficient and, for Banzhaf, provably more robust to noisy value functions (relevant because our value
  is a `θ`-average).

### H. Cross-entropy method, estimation-of-distribution algorithms, evolutionary and structured search

**H1. Cross-entropy method (CEM) for combinatorial optimization and rare-event estimation**
- **Source:** Rubinstein (1997) *EJOR* 99:89–112; de Boer, Kroese, Mannor, Rubinstein (2005) tutorial,
  *Ann. Oper. Res.* 134:19–67, [doi](https://doi.org/10.1007/s10479-005-5724-z) (not re-verified).
- **Method:** sample masks from an independent-Bernoulli product distribution, evaluate, keep the
  elite quantile, refit the Bernoulli parameters to the elites (with smoothing), iterate; the same loop
  estimates rare-event probabilities by importance sampling.
- **Assumptions:** an evaluable objective (noisy is fine); the product family is expressive enough to
  concentrate on good masks.
- **Cost:** population × generations, typically `50–200 × 10–50` = thousands of evaluations; each
  keep-only evaluation is cheap here.
- **Relevance:** the canonical population/distribution-based search over `{0,1}^N`; the Bernoulli
  parameters at convergence are marginal membership frequencies (a heuristic `p(z_i = 1)` that can be
  calibrated by re-simulation); a sparsity penalty (or a fixed prior on `|S|`) targets compactness; a
  CVaR-over-`θ` elite criterion (N1) buys robustness; naturally parallel.
- **Limits:** independence assumption loses co-membership structure (multiple mechanisms collapse to
  one mode or to a blur); premature convergence; needs pre-pruning at `N = 5,000` or a structured
  proposal (sample connected subgraphs).
- **As-is?** Yes.
- **Budget?** Yes for ≤ 5,000 keep-only calls with small populations; Marginal if each elite is
  re-evaluated on many `θ` draws (use racing, I4).

**H2. Estimation-of-distribution algorithms with dependency structure (PBIL, BOA)**
- **Source:** Baluja (1994) PBIL, CMU-CS-94-163 (not re-verified); Pelikan, Goldberg, Cantú-Paz (1999)
  BOA, GECCO (not re-verified).
- **Method:** PBIL is CEM with incremental updates from the best individuals; BOA learns a Bayesian
  network over the binary variables from the selected population, capturing pairwise and higher-order
  linkage, then samples from it.
- **Assumptions:** enough population to learn dependencies (BOA: hundreds).
- **Cost:** as H1, plus structure learning per generation (BOA).
- **Relevance:** linkage learning addresses H1's weakness: mechanism members are co-selected as a unit;
  the learned dependency graph is itself a readable hypothesis about which nodes act together.
- **Limits:** population sizes for reliable linkage learning exceed our budget at `N > 100`; only after
  pre-pruning.
- **As-is?** Yes.
- **Budget?** Marginal.

**H3. CMA-ES on relaxed masks**
- **Source:** Hansen (2016) tutorial, [arXiv:1604.00772](https://arxiv.org/abs/1604.00772); Hansen &
  Ostermeier (2001) *Evol. Comput.* 9:159–195 (not re-verified).
- **Method:** Gaussian search distribution with adapted covariance over a continuous relaxation of the
  mask (logits thresholded or sampled); rank-based updates are invariant to monotone transformations of
  the objective.
- **Assumptions:** continuous search space of moderate dimension (tens to low hundreds).
- **Cost:** `O(d^2)` per generation for covariance; population ~`4 + 3 ln d`.
- **Relevance:** useful for the *continuous* sub-problems (robustness over `θ`, gain thresholds) and for
  ≤ 100-dimensional relaxed masks; not for `N = 5,000` binary variables (covariance is `N^2`).
- **Limits:** dimension; binary relaxations waste evaluations on equivalent thresholded masks.
- **As-is?** Yes.
- **Budget?** Marginal.

**H4. Genetic algorithms on subsets; NSGA-II for compactness-vs-function trade-offs**
- **Source:** Deb, Pratap, Agarwal, Meyarivan (2002), *IEEE Trans. Evol. Comput.* 6:182–197,
  [doi](https://doi.org/10.1109/4235.996017) (not re-verified).
- **Method:** population of masks with crossover/mutation; NSGA-II keeps a Pareto front over
  objectives (here: readout robustness vs. `|S|` vs. necessity margin) via non-dominated sorting and
  crowding distance.
- **Assumptions:** a few hundred to thousands of evaluations; objectives cheap enough.
- **Cost:** population × generations; no model.
- **Relevance:** the Pareto front directly answers "how compact can the mechanism be for a given
  robustness level" without fixing `|M|` a priori (criterion 3 with unknown size); crossover between
  masks is a natural recombination of partial mechanisms.
- **Limits:** no principled uncertainty; sensitive to seeds (criterion 5 must be measured, not
  assumed); `N = 5,000` needs structured operators (mutations along graph edges).
- **As-is?** Yes.
- **Budget?** Marginal (a 100 × 30 run is 3,000 calls before `θ` replicates).

**H5. Sequential Monte Carlo on large binary spaces (posterior sampling over subsets)**
- **Source:** Schäfer & Chopin (2013), *Statistics and Computing* 23:163–184,
  [arXiv:1101.6037](https://arxiv.org/abs/1101.6037).
- **Method:** SMC over `{0,1}^N` for Bayesian variable selection: tempering from prior to posterior
  with adaptive, *dependent* binary proposal families (logistic-regression-type parametric proposals
  fitted to the current particles) that avoid the collapse of independent-Bernoulli proposals in high
  dimension.
- **Assumptions:** a target posterior evaluable up to a constant (needs a likelihood of the data given
  the mask).
- **Cost:** particles × tempering steps × likelihood evaluations; likelihood must be cheap (a surrogate
  model of `pass(S)`, not the simulator).
- **Relevance:** the principled version of CEM: proper posterior over masks with dependencies, from
  which `p(z_i = 1)` and the multimodality (several mechanisms) are read off; it is also the machinery
  inside B6.
- **Limits:** needs a likelihood; simulator-in-the-loop SMC is unaffordable, so the likelihood must be
  the accumulated-test model.
- **As-is?** Yes with a test-likelihood model.
- **Budget?** Yes (no simulator calls beyond the tests themselves).

### I. Bayesian optimization over structured discrete spaces; surrogate-assisted optimization; budget allocation

**I1. BOCS: sparse Bayesian polynomial surrogate over binary vectors + Thompson sampling**
- **Source:** Baptista & Poloczek (2018), ICML, [arXiv:1806.08838](https://arxiv.org/abs/1806.08838).
- **Method:** sparse Bayesian linear regression (horseshoe prior) on first- and second-order monomials
  of the binary mask; Thompson sampling of coefficient vectors; the acquisition (a quadratic binary
  program) is optimized by SDP relaxation or simulated annealing.
- **Assumptions:** the objective is well approximated by a sparse quadratic pseudo-Boolean function;
  tens of variables in the paper.
- **Cost:** a few hundred evaluations; surrogate fit is cheap; acquisition optimization `O(N^2)`–`O(N^3)`
  per step for the SDP.
- **Relevance:** the natural surrogate for pairwise node interactions (excitatory/inhibitory pairs,
  disinhibition) with automatic sparsity and posterior samples over interaction structure; Thompson
  sampling resists surrogate exploitation better than greedy UCB on a misspecified model.
- **Limits:** a degree-2 model cannot represent an AND of five nodes exactly (though it can rank
  members once most are present); scaling to `N = 5,000` is not practical — use after pre-screening
  (B8) to ≤ ~100 variables.
- **As-is?** Yes.
- **Budget?** Yes on a pre-screened set.

**I2. COMBO: GP with graph-Cartesian-product diffusion kernel; trust-region and embedding methods
(Casmopolitan, Bounce); high-dimensional GP priors (SAASBO, dimension-scaled lengthscale priors)**
- **Source:** Oh, Tomczak, Gavves, Welling (2019) COMBO, NeurIPS,
  [link](https://proceedings.neurips.cc/paper/2019/hash/2cb6b10338a7fc4117a80da24b582060-Abstract.html);
  Wan et al. (2021) Casmopolitan, ICML (not re-verified); Papenmeier, Nardi, Poloczek (2023) Bounce,
  NeurIPS, [arXiv:2307.00618](https://arxiv.org/abs/2307.00618); Eriksson & Jankowiak (2021) SAASBO,
  UAI (not re-verified); Hvarfner, Hellsten, Nardi (2024) vanilla BO in high dimensions, ICML,
  [arXiv:2402.02229](https://arxiv.org/abs/2402.02229).
- **Method:** COMBO builds a GP whose kernel is the diffusion kernel on the Cartesian product of
  per-variable graphs (Hamming-like smoothness) with graph-Fourier features scaling linearly in the
  number of variables; Casmopolitan and Bounce use trust regions in Hamming space and nested random
  embeddings for hundreds of binary variables; SAASBO puts sparsity-inducing priors on inverse
  lengthscales; Hvarfner et al. show a dimension-scaled lengthscale prior lets vanilla GP-BO work in
  hundreds of dimensions.
- **Assumptions:** smoothness of the objective in Hamming distance — reasonable for graded readouts
  but *not* for a complete-or-nothing mechanism (a Hamming-1 change flips pass/fail).
- **Cost:** GP fit `O(n^3)` in evaluations; acquisition over combinatorial space by local search.
- **Relevance:** the mainstream black-box option for ≤ few hundred binary variables and ≤ ~1,000
  evaluations; Bounce's reliability analysis (methods degrade when optima lack assumed structure) is a
  warning for our setting.
- **Limits:** kernel smoothness assumption; `N = 5,000` needs embeddings or pre-screening; poor at
  representing sharp AND structure.
- **As-is?** Yes.
- **Budget?** Yes for ≤ ~1,000 evaluations on ≤ ~300 variables.

**I3. Surrogate-assisted and cost-aware sequential model-based optimization; multi-fidelity**
- **Source:** Jones, Schonlau, Welch (1998) EGO, *J. Global Optim.* 13:455–492; Shahriari et al. (2016)
  BO review, *Proc. IEEE* 104:148–175; Snoek, Larochelle, Adams (2012) EI-per-second; Kandasamy et al.
  (2017) multi-fidelity BO (BOCA), ICML (all not re-verified).
- **Method:** fit a probabilistic surrogate; pick the next design by expected improvement per unit
  cost; multi-fidelity variants use cheap approximations (coarser step, shorter horizon, fewer `θ`) to
  screen and reserve expensive evaluations for promising designs.
- **Assumptions:** fidelities are informative about the target fidelity; cost model known.
- **Cost:** governed by the cost model.
- **Relevance:** the simulator has natural fidelities: keep-only vs full-network (24× cost), RK4 vs
  RK45 (3×), short vs long horizon, few vs many `θ` draws. A cost-aware acquisition should spend the
  cheap fidelity on sufficiency screening and the expensive one on necessity confirmation.
- **Limits:** keep-only and full-network queries measure different quantities (sufficiency vs
  necessity), not two fidelities of one quantity — model them as two correlated outputs, not as
  fidelities.
- **As-is?** Yes.
- **Budget?** Yes.

**I4. Racing, successive halving and best-arm identification for noisy `θ`-ensemble evaluation**
- **Source:** Birattari, Stützle, Paquete, Varrentrapp (2002) F-Race, GECCO; Li, Jamieson,
  DeSalvo, Rostamizadeh, Talwalkar (2018) Hyperband, *JMLR* 18(185):1–52; Jamieson & Nowak (2014)
  best-arm identification, CISS (all not re-verified).
- **Method:** evaluate many candidates on few `θ` draws, drop statistically inferior candidates early,
  and concentrate draws on survivors (successive halving); confidence-interval-based elimination
  (racing, lil'UCB) gives fixed-confidence guarantees.
- **Assumptions:** i.i.d. noisy evaluations; a scalar score per candidate.
- **Cost:** `O(n log n)` evaluations for `n` candidates versus `O(n · n_θ)` naive.
- **Relevance:** solves the budget arithmetic problem of §1.2: candidates from any search (CEM, BO,
  group testing) must be compared under ensemble noise; common random numbers (same `θ` draws across
  candidates) further reduce variance.
- **Limits:** assumes the score of interest is a mean (CVaR needs more draws); early elimination can
  drop mechanisms that are robust in a different `θ`-region (degeneracy, E1).
- **As-is?** Yes.
- **Budget?** Yes — it is the budget-management layer.

**I5. Transfer of search across related problems (multi-task BO; warm-started populations)**
- **Source:** Swersky, Snoek, Adams (2013) multi-task BO, NeurIPS (not re-verified).
- **Method:** a multi-output GP couples objectives of related tasks so evaluations on task A inform
  the surrogate for task B; population methods analogously seed B's population from A's elites.
- **Assumptions:** a correspondence between design variables of A and B (here: a node/cell-type mapping
  between graphs) and correlated objectives.
- **Cost:** none beyond the joint surrogate.
- **Relevance:** criterion (6): search on `G_B` should start from the posterior found on `G_A`,
  transported through the cross-graph node mapping (with its uncertainty), and the transfer *gain*
  itself is evidence of mechanism identity.
- **Limits:** a wrong mapping poisons the prior; must be tested against a cold start (J6 universality
  caveat).
- **As-is?** Yes.
- **Budget?** Yes.

### J. Mechanistic-interpretability circuit discovery and what transfers to biological graphs

**J1. ACDC: automated circuit discovery by greedy edge ablation with a faithfulness threshold**
- **Source:** Conmy, Mavor-Parker, Lynch, Heimersheim, Garriga-Alonso (2023), NeurIPS,
  [arXiv:2304.14997](https://arxiv.org/abs/2304.14997).
- **Method:** iterate over edges of the computational graph from output to input; for each edge, patch
  in corrupted activations and remove the edge if the KL divergence of the output rises less than a
  threshold; the surviving edges form the circuit.
- **Assumptions:** a faithfulness metric and a corrupted-input distribution; monotone-ish
  accumulation of ablation effects.
- **Cost:** one forward pass per edge per sweep — `O(|E|)`; ~32k edges for a small transformer.
- **Relevance:** ACDC *is* simulation-guided backward elimination over edges with a tolerance — the
  transformer analogue of our baseline; its known failure modes (threshold sensitivity, missing
  negative-effect components, sequential-order dependence) are the ones to test our baseline for.
- **Limits:** `O(|E|)` full evaluations is unaffordable here (`|E|` is millions of synapse-level edges,
  tens of thousands of type-level edges); greedy sequential removal is order-dependent (criterion 5).
- **As-is?** Yes conceptually; No at our edge counts without aggregation.
- **Budget?** No.

**J2. Edge attribution patching (EAP), EAP-IG, interaction-aware gradient attribution (GIM)**
- **Source:** Syed, Rager, Conmy (2024), BlackboxNLP@ACL, [arXiv:2310.10348](https://arxiv.org/abs/2310.10348);
  Hanna, Pezzelle, Belinkov (2024) EAP-IG, COLM, [arXiv:2403.17806](https://arxiv.org/abs/2403.17806);
  Edin et al. (2025) GIM, [arXiv:2505.17630](https://arxiv.org/abs/2505.17630).
- **Method:** first-order Taylor estimate of every edge's ablation effect from two forward passes and
  one backward pass; EAP-IG integrates gradients along the clean→corrupt path for faithfulness; GIM
  corrects vanishing gradients caused by self-repair (softmax redistribution) by modelling interactions
  during backpropagation; attribution and mask-optimization methods top the MIB circuit-localization
  leaderboard.
- **Assumptions:** differentiable model; linearity of ablation effects (the very assumption
  self-repair violates).
- **Cost:** `O(1)` passes for all edges — the query-efficiency champion when gradients exist.
- **Relevance:** with a differentiable RK4 port (F1), a gradient-based importance for every node/edge
  is available for the cost of a few simulations and gives an excellent *prior* for group tests or
  masks; GIM's insight (single-perturbation attribution underestimates components that are backed up)
  transfers directly to redundancy in biological circuits.
- **Limits:** linearization is unreliable for strongly non-linear/complete-or-nothing effects; needs
  gradients.
- **As-is?** No (gradients); Yes with the port.
- **Budget?** Yes with the port (a handful of simulations).

**J3. Path patching, causal scrubbing, causal abstraction (hypothesis-testing frameworks)**
- **Source:** Wang et al. (2023) IOI/path patching, ICLR, [arXiv:2211.00593](https://arxiv.org/abs/2211.00593);
  Goldowsky-Dill, MacLeod, Sato, Arora (2023), [arXiv:2304.05969](https://arxiv.org/abs/2304.05969);
  Chan et al. (2022) causal scrubbing, Alignment Forum,
  [link](https://www.alignmentforum.org/posts/JvZhhzycHu2Yd57RN/causal-scrubbing-a-method-for-rigorously-testing);
  Geiger, Ibeling, Zur, Chalupka, Icard (2025) causal abstraction, *JMLR* 26,
  [arXiv:2301.04709](https://arxiv.org/abs/2301.04709).
- **Method:** path patching tests whether a behaviour is localized to specific paths by patching
  activations along those paths only; causal scrubbing tests a *hypothesis* (a high-level causal
  graph plus a correspondence to model components) by resampling ablations that should not change the
  behaviour if the hypothesis is right, reporting the loss recovered; causal abstraction formalizes all
  of these as interchange interventions between a low-level and a high-level causal model, with graded
  faithfulness.
- **Assumptions:** ability to set internal activations to values from other inputs (resample
  ablation), not just to zero.
- **Cost:** per hypothesis, a batch of patched runs; cheap relative to search.
- **Relevance:** the conceptual home for *roles*: a high-level model (e.g., "driver → core oscillator
  → relay → output") is a causal abstraction of the sub-mechanism, and interchange interventions
  (swap a node's trajectory between conditions) test each node's role; causal scrubbing's
  "hypothesis-conditioned resampling" is a stronger test of sufficiency than keep-only alone.
- **Limits:** requires resample-style interventions (set a node's activity to a recorded trajectory)
  — the simulator supports silencing and keep-only; clamping to recorded trajectories would need a
  small extension; hypotheses must be proposed by a search method first.
- **As-is?** Partial (silence/keep-only only).
- **Budget?** Yes.

**J4. Ablation semantics and self-repair: activation-patching best practices, optimal ablation,
the Hydra effect, conditional co-ablation**
- **Source:** Zhang & Nanda (2024), ICLR, [arXiv:2309.16042](https://arxiv.org/abs/2309.16042);
  Li & Janson (2024) optimal ablation, [arXiv:2409.09951](https://arxiv.org/abs/2409.09951);
  McGrath, Rahtz, Kramár, Mikulik, Legg (2023) Hydra effect, [arXiv:2307.15771](https://arxiv.org/abs/2307.15771);
  Gong et al. (2026) conditional co-ablation, [arXiv:2607.01940](https://arxiv.org/abs/2607.01940).
- **Method:** systematic comparison of zero/mean/resample ablations and metrics (logit difference vs.
  probability vs. KL) showing that conclusions change with these choices; optimal ablation replaces a
  component with the constant that minimizes loss, with better theoretical properties; the Hydra effect
  documents downstream components compensating for ablated ones (even without dropout); CoAx ranks
  candidates by the *growth* of their ablation effect after removing the primary set, which
  aggregates all interaction orders and recovers dormant backups (ROC-AUC 0.94 vs 0.82 for intact-state
  scoring).
- **Assumptions:** access to alternative ablation values; a known primary set for conditioning.
- **Cost:** CoAx: one extra ablation sweep conditioned on the primary set (`O(N)` full-network
  evaluations, or `O(|candidates|)` after pruning).
- **Relevance:** silencing (zero ablation) is only one intervention semantics; biological "silencing"
  might be better approximated by mean-activity clamping; compensation/self-repair is the ML name for
  redundancy, and conditional co-ablation is exactly the procedure to find backup nodes that make a
  mechanism only *near*-necessary.
- **Limits:** conditional sweeps multiply cost; findings are specific to the primary set conditioned on.
- **As-is?** Yes for zero-ablation conditional sweeps; mean/resample ablation needs a small simulator
  extension.
- **Budget?** Yes on a pruned candidate set.

**J5. Evaluation: faithfulness metrics are not robust; circuit hypothesis tests; benchmarks with known
ground truth; variance and reporting protocols; certified stability; formal guarantees**
- **Source:** Miller, Chughtai, Saunders (2024), COLM, [arXiv:2407.08734](https://arxiv.org/abs/2407.08734);
  Shi et al. (2024) hypothesis testing the circuit hypothesis, NeurIPS, [arXiv:2410.13032](https://arxiv.org/abs/2410.13032)
  (not re-verified); Mueller et al. (2025) MIB, ICML, [arXiv:2504.13151](https://arxiv.org/abs/2504.13151);
  Gupta, Arcuschin, Kwa, Garriga-Alonso (2024) InterpBench, NeurIPS D&B,
  [arXiv:2407.14494](https://arxiv.org/abs/2407.14494); Wu, Tonin, Cevher (2026) variance in circuit
  discovery, [arXiv:2606.16920](https://arxiv.org/abs/2606.16920); Sheng & Fu (2026) circuit claims
  depend on extraction and comparison, [arXiv:2607.18921](https://arxiv.org/abs/2607.18921); Anani et
  al. (2026) certified circuits, [arXiv:2602.22968](https://arxiv.org/abs/2602.22968); Hadad, Katz,
  Bassan (2026) formal circuit discovery, [arXiv:2602.16823](https://arxiv.org/abs/2602.16823).
- **Method:** Miller et al. show faithfulness scores move substantially with ablation type and metric;
  Shi et al. formalize testable properties of a claimed circuit (equivalence/faithfulness,
  independence of the complement, minimality, sufficiency) as statistical tests; MIB evaluates methods
  by area under the faithfulness-vs-circuit-size curve; InterpBench trains semi-synthetic models with
  *known* circuits (strict interchange-intervention training) to score discovery methods against
  ground truth; Wu et al. decompose variance into resampling, rephrasing and per-sample components and
  propose a lower-variance attribution; Sheng & Fu show component overlap between extracted circuits
  can fall to chance depending on which object is reported and at what granularity; certified circuits
  wrap any black-box discovery algorithm with randomized subsampling to certify inclusion decisions
  against bounded dataset edits; formal methods give verified robustness/minimality on small vision
  models.
- **Assumptions:** a faithfulness metric, a data distribution, and (for benchmarks) synthetic ground
  truth.
- **Cost:** evaluation-side; certification multiplies discovery runs.
- **Relevance:** the blueprint for a *tournament protocol*: score methods on synthetic circuits with
  planted ground truth (the analogue of InterpBench), report faithfulness–size curves rather than single
  circuits (MIB), run every method across seeds/orderings and report inclusion stability (Wu; Anani),
  and fix the intervention semantics and comparison granularity in advance (Miller; Sheng & Fu).
- **Limits:** metric choices remain contestable; synthetic ground truth may not reflect the degeneracy of
  real ensembles.
- **As-is?** Yes.
- **Budget?** Yes (evaluation budget separate from discovery budget).

**J6. Transfer and universality: sparse feature circuits; a toy model of universality**
- **Source:** Marks et al. (2025) sparse feature circuits, ICLR oral, [arXiv:2403.19647](https://arxiv.org/abs/2403.19647);
  Chughtai, Chan, Nanda (2023), ICML, [PMLR 202](https://proceedings.mlr.press/v202/chughtai23a.html).
- **Method:** Marks et al. discover circuits over interpretable features (sparse-autoencoder latents)
  rather than raw units so circuits are comparable and editable across contexts; Chughtai et al. test
  the universality hypothesis (do different models learn the same circuits?) on group-composition
  tasks: the *family* of circuits is fully characterizable, but which member a given network learns is
  arbitrary.
- **Assumptions:** a shared feature basis across models (Marks); small algorithmic tasks (Chughtai).
- **Cost:** n/a.
- **Relevance:** criterion (6) should be posed at the right level of abstraction: two graphs may
  implement the same computation with different node-level mechanisms drawn from one family;
  comparison across graphs should therefore be done at the level of roles/abstract causal model (J3)
  and cell-type-level features, not node identity, and universality must be tested rather than assumed.
- **Limits:** LLM-specific tooling.
- **As-is?** Conceptual.
- **Budget?** n/a.

### K. Causal representation learning and invariance across environments

**K1. Invariant causal prediction (ICP) and invariant risk minimization (IRM) — and their limits**
- **Source:** Peters, Bühlmann, Meinshausen (2016), *JRSS-B* 78:947–1012,
  [arXiv:1501.01332](https://arxiv.org/abs/1501.01332); Arjovsky, Bottou, Gulrajani, Lopez-Paz (2019),
  [arXiv:1907.02893](https://arxiv.org/abs/1907.02893); Rosenfeld, Ravikumar, Risteski (2021) risks of
  IRM, ICLR, [arXiv:2010.05761](https://arxiv.org/abs/2010.05761).
- **Method:** ICP returns the set of variables `S` such that the conditional of the target given `S` is
  invariant across environments (interventional regimes), with a confidence set via intersection over
  accepted `S`; IRM seeks representations whose optimal predictor is the same across environments;
  Rosenfeld et al. show IRM can fail to recover invariant predictors with finitely many environments
  in nonlinear settings.
- **Assumptions:** environments differ by interventions not on the target; variables are aligned
  across environments; enough environments.
- **Cost:** `2^|candidates|` invariance tests in naive ICP; feasible for ≤ ~10–15 candidates.
- **Relevance:** environments = {graph A, graph B} × `θ` draws × intervention regimes; the mechanism is
  the node set whose *functional relationship to the readout is invariant* across environments, which
  is a sharper transfer criterion than "the same nodes appear"; ICP's intersection-of-accepted-sets
  construction is a direct way to obtain a conservative "necessary core".
- **Limits:** requires node/type alignment between graphs (the cross-graph mapping is itself
  uncertain) and enough environments; nonlinear ICP variants are needed for dynamical readouts.
- **As-is?** Partial.
- **Budget?** Yes on ≤ ~15 candidates.

### L. Network controllability and structural theory for intervention design

**L1. Feedback vertex sets determine long-term dynamics; structure-based control of nonlinear networks**
- **Source:** Fiedler, Mochizuki, Kurosawa, Saito (2013), *J. Dyn. Diff. Equations* 25:563–604,
  [doi](https://link.springer.com/article/10.1007/s10884-013-9312-7); Mochizuki, Fiedler, Kurosawa,
  Saito (2013), *J. Theor. Biol.* 335:130–146; Zañudo, Yang, Albert (2017), *PNAS* 114:7234–7239,
  [doi](https://www.pnas.org/doi/10.1073/pnas.1617387114).
- **Method:** for a broad class of dissipative network ODEs whose interaction graph is known, the
  long-term dynamics of the whole network are determined by (and can be controlled by clamping) the
  nodes of a feedback vertex set (FVS: a node set whose removal leaves the graph acyclic); Zañudo et
  al. turn this into an algorithm (FVS plus source nodes) for steering nonlinear networks to their
  natural attractors.
- **Assumptions:** dynamics of the "decay-plus-regulation" form with known graph; attractor-level
  statements (not transient).
- **Cost:** FVS computation is NP-hard in general but practical with heuristics/ILP for `N = 5,000`;
  zero simulator calls.
- **Relevance:** a sustained rhythm is an attractor, so any sub-mechanism generating it must contain a
  cycle, and the *minimal* FVS of the candidate subgraph is a principled lower bound on which nodes
  must be present/observed; FVS members are also the most informative nodes to clamp or record. This
  gives a structural prior over membership and a candidate generator (cycles through inhibitory edges,
  reachable from `u`, projecting to `Y`) that shrinks `N` by orders of magnitude before any simulation.
- **Limits:** attractor determination is not the same as sufficiency of a *small* subgraph in
  isolation; multiple FVSs exist (again: multiple mechanisms).
- **As-is?** Yes (graph-only).
- **Budget?** Yes (no calls).

**L2. Structural controllability, driver nodes, and controllability-based predictions of neuron function**
- **Source:** Liu, Slotine, Barabási (2011), *Nature* 473:167–173 (not re-verified); Gu et al. (2015),
  *Nat. Commun.* 6:8414 (not re-verified); Yan et al. (2017), *Nature* 550:519–523,
  [doi](https://www.nature.com/articles/nature24056).
- **Method:** linear structural controllability identifies minimal driver-node sets via maximum
  matching; Gu et al. define average/modal controllability metrics for brain networks; Yan et al.
  apply the control framework to a connectome to predict which neuron classes are required to control
  the motor output and validate a subset by ablation.
- **Assumptions:** linear time-invariant dynamics on the graph; often ignores edge signs and weights
  for the structural results.
- **Cost:** polynomial graph algorithms; zero simulator calls.
- **Relevance:** the only controllability line with an experimental validation of *ablation*
  predictions from graph structure; useful as a structural prior/ranking for necessity tests and as a
  baseline that uses no simulation at all.
- **Limits:** linearity; subsequent critiques of controllability metrics in brain networks (e.g., their
  dependence on degree) mean they should be used as priors, not conclusions.
- **As-is?** Yes.
- **Budget?** Yes (no calls).

### M. Minimum-description-length model selection and the multiplicity of good models

**M1. MDL / two-part codes; Rashomon sets and model-class reliance**
- **Source:** Rissanen (1978), *Automatica* 14:465–471; Grünwald (2007) *The MDL Principle*, MIT Press
  (both not re-verified); Semenova, Rudin, Parr (2022), FAccT, [doi](https://dl.acm.org/doi/10.1145/3531146.3533232);
  Fisher, Rudin, Dominici (2019), *JMLR* 20(177):1–81, [link](https://jmlr.org/papers/v20/18-760.html).
- **Method:** select the model minimizing `L(model) + L(data | model)`; for a sub-mechanism, `L(model)`
  = bits for its nodes, edges and role labels, `L(data | model)` = bits to encode the ensemble readouts
  given the mechanism's predictions; Rashomon-set work formalizes that many near-optimal models exist
  and that importance should be reported as a *range* over the set (model-class reliance).
- **Assumptions:** a coding scheme (prior) for mechanisms and a predictive model for the readout.
- **Cost:** evaluation-side.
- **Relevance:** criterion (3) with unknown size is exactly an MDL trade-off (each extra node must pay
  for itself in explained ensemble variance), which avoids fixing `|M|`; Rashomon reasoning says the
  deliverable should be the *set* of near-minimal mechanisms with membership ranges, not one set.
- **Limits:** code lengths depend on the chosen model family; MDL does not itself search.
- **As-is?** Yes.
- **Budget?** Yes.

### N. Risk-sensitive and robust optimization over the parameter ensemble

**N1. CVaR objectives; Bayesian optimization of risk measures; distributionally robust BO; scenario bounds**
- **Source:** Rockafellar & Uryasev (2000), *J. Risk* 2:21–41 (not re-verified); Cakmak, Astudillo,
  Frazier, Zhou (2020), NeurIPS, [arXiv:2007.05554](https://arxiv.org/abs/2007.05554); Kirschner,
  Bogunovic, Jegelka, Krause (2020) DRBO, AISTATS, [arXiv:2002.09038](https://arxiv.org/abs/2002.09038);
  Bogunovic, Scarlett, Jegelka, Cevher (2018) StableOpt, NeurIPS, [arXiv:1810.10775](https://arxiv.org/abs/1810.10775);
  Campi & Garatti (2008), *SIAM J. Optim.* 19:1211–1230 (not re-verified).
- **Method:** optimize `ρ[F(x, W)]` with `ρ` = VaR/CVaR over environmental randomness `W` (here `θ`)
  using a GP over `(x, w)` jointly and knowledge-gradient-type acquisitions that choose both the design
  and the `w` to simulate (Cakmak); DRBO optimizes the worst case over an MMD ball around the nominal
  `θ`-distribution; StableOpt optimizes the worst case over perturbations of the design; the scenario
  approach gives sample-size bounds for chance constraints in convex programs, and Hoeffding/binomial
  bounds do the same for estimating `P_θ[pass(M)]` in our non-convex setting.
- **Assumptions:** a distribution over `θ` (given); GP-modelable dependence on `θ` for the BO
  variants.
- **Cost:** BO variants use tens to hundreds of joint `(x, θ)` evaluations; CVaR estimation needs more
  draws than the mean (tail).
- **Relevance:** criterion (4) is a risk measure over `θ`, and Cakmak et al.'s joint modelling of
  design and environment is the efficient way to spend `θ` draws (simulate the `θ` that is most
  informative about the tail, not random draws); DRBO guards against misspecification of the ensemble
  itself.
- **Limits:** GP over `θ` (continuous, dozens of dimensions) is fine; the discrete design side needs
  I1/I2 surrogates; tails need budget.
- **As-is?** Yes.
- **Budget?** Yes for a shortlist of candidates.

### O. Active learning under expensive simulators (summary entry)

**O1. Sequential design for computer experiments; batch acquisition; parallelism**
- **Source:** Sacks, Welch, Mitchell, Wynn (1989) *Stat. Sci.* 4:409–423; Gramacy (2020) *Surrogates*,
  CRC; González, Dai, Hennig, Lawrence (2016) local penalization for batch BO, AISTATS (all not
  re-verified).
- **Method:** GP surrogates fitted to simulator outputs; sequential designs (active learning MacKay/
  Cohn, IMSE, entropy) pick where to simulate next; batch variants (q-EI, local penalization) choose
  several points per round for parallel execution.
- **Assumptions:** smooth response over a modest-dimensional continuous input space.
- **Cost:** one simulator batch per round.
- **Relevance:** the parallel-batch machinery matters operationally (CPU cores × 0.1 s keep-only runs);
  the continuous inputs here are `θ` and stimulation gain, not the mask.
- **Limits:** not designed for `{0,1}^5000`.
- **As-is?** Yes.
- **Budget?** Yes.

---

## 3. Synthesis (a): which families to enter in a tournament, and why

The cost structure (cheap keep-only, expensive silencing, ensemble noise, `N` up to 5,000) and the
criteria (sufficient, near-necessary, compact, robust, stable, transferable, calibrated) point to a
pipeline with a shared **structural pre-screen** and a shared **confirmation stage**, between which the
competing search families are swapped in. Six families look most promising:

1. **Bayesian adaptive group testing over keep-only pools (B6 + B2/B5 + A7).** *Active/group-testing
   design.* Maintain an SMC posterior over membership vectors (H5 machinery) with an AND-type
   (monotone-DNF) likelihood that allows several terms and explicit inhibitor nodes; choose pools by
   EIG or by EC2-style hypothesis splitting; noise model = ensemble pass rate. Why: it is the only
   family with query-complexity theory in the right regime (`k log N`), it yields calibrated
   `p(z_i = 1)` and carries several competing mechanisms as particle modes, and it spends almost all
   calls on 0.1 s queries. The deterministic cousins (ddmin/ProbDD/QuickXplain, B4) are cheap baselines
   that should also be entered; their retention probabilities are a crude calibration reference.

2. **Cross-entropy / EDA search over masks with a CVaR-over-`θ` elite criterion and an MDL size penalty
   (H1–H2 + N1 + M1).** *Population/distribution-based search.* Why: robust to non-monotone effects
   (no monotonicity assumption anywhere), trivially parallel, unknown mechanism size handled by the
   penalty, marginal membership frequencies fall out; racing (I4) controls the `θ`-replicate cost.
   Weakness to watch: independence across nodes; use structured proposals (connected subgraphs
   containing a cycle, from L1) and report multimodality via restarts. NSGA-II (H4) is the
   multi-objective variant if a robustness–compactness front is wanted instead of a penalty weight.

3. **Sparse interaction surrogate + Thompson sampling after a group-testing pre-screen (B8 → I1 or C3).**
   *Model-based search.* Why: once the group screen reduces `N` to ≤ ~100 candidates, a BOCS-style
   sparse quadratic (or Fourier-sparse, degree ≤ `r`) surrogate models pairwise/higher-order node
   interactions explicitly, resists surrogate exploitation through posterior sampling, and its learned
   interaction terms are interpretable as roles (synergy vs. redundancy). Standard GP-based
   combinatorial BO (I2) is the control arm; expect it to suffer from the complete-or-nothing structure.

4. **Differentiable mask pruning on an autodiff port of the fixed-step RK4 model (F1–F2, with J2 as a
   prior).** *Gradient-based (requires a bounded engineering change; not black-box).* Why: if the port
   is made, hard-concrete node/edge gates with an L0 penalty and a differentiable rhythmicity proxy
   deliver a sparse executable subgraph in minutes, and gradient attributions (EAP-style) give a strong
   prior for the black-box families. It must be scored under the same evaluator with the true RK45
   readout; its gate probabilities must not be reported as calibrated posteriors without re-simulation.

5. **Structure-primed greedy with necessity confirmation (L1–L2 + G4 + G2 + J4).** *Structural prior +
   simulation-guided greedy.* Why: FVS/cycle structure, reachability from `u` to `Y`, sign patterns,
   and controllability rankings generate a small candidate pool with *zero* simulator calls; forward
   selection over that pool (with submodularity-ratio diagnostics to detect when greedy is
   untrustworthy), followed by conditional co-ablation to find backups, is a direct, cheap improvement
   over the backward-elimination baseline and a useful ablation of "how much does structure alone buy".

6. **Marginal-contribution and interaction diagnostics on the shortlist (E3/G5 + J3).** *Role and
   redundancy analysis rather than search.* Shapley/Banzhaf interaction indices, conditional
   co-ablation, and interchange-style interventions against a proposed high-level causal model
   (causal abstraction) give roles and the necessary/back-up split for the ≤ ~20 nodes that survive the
   search; budget permits this only at the end.

Shared stages for all arms: (i) structural pre-screen (L1/L2/A5/G4; no calls); (ii) the arm's search
under a fixed call budget with keep-only queries; (iii) confirmation: racing over `θ` (I4), CVaR
estimate (N1), silencing-based necessity of each member in the full network (E2) and conditional
co-ablation for backups (J4), all on the shortlist; (iv) reporting: faithfulness–size curve, membership
posterior with calibration checked on planted synthetic circuits (J5), stability across seeds and node
orderings, and transfer to the second graph through the mapping with a cold-start control (I5/K1/J6).

## 4. Synthesis (b): pitfalls and how the literature handles them

- **Surrogate exploitation (the optimizer finds masks the surrogate loves and the simulator does not).**
  Handled by posterior sampling instead of UCB/greedy (BOCS Thompson sampling, I1), trust regions in
  Hamming space (Casmopolitan/Bounce, I2), always re-simulating the incumbent before acceptance,
  ensembles for epistemic uncertainty (E-SINDy, D1), and by never letting a relaxed gate probability
  stand in for a posterior (F1). Hvarfner et al. (I2) show much "high-dimensional BO failure" is
  prior misspecification, so priors on lengthscales/sparsity should be set deliberately.

- **Non-monotone and non-submodular effects of node removal.** Removing an inhibitory node can *create*
  or *destroy* rhythm; forward greedy has vacuous guarantees when the objective is complete-or-nothing
  (`γ ≈ 0`, G2). The literature's answers: model the non-monotonicity explicitly (threshold/inhibitor
  group testing, B5; junta learning without monotonicity, B3), assess monotonicity online and
  probabilistically (PMA, B4), use search families that do not assume it (H1–H5), and diagnose with
  submodularity-ratio/curvature estimates on the candidate pool (G2) so that greedy is only trusted
  where it is warranted. Ablation semantics matter too: zero vs. mean vs. resample vs. optimal ablation
  change conclusions (J4), so the intervention type must be fixed and reported.

- **Redundancy and multiple equivalent mechanisms.** Expected, not exceptional: degeneracy across
  parameter sets (E1), backup components and self-repair (Hydra effect, J4), multiple terms in the
  monotone DNF (B2), multiple FVSs (L1), Rashomon sets (M1). Handled by (i) learning *all* minimal
  sufficient sets (hypergraph learning) and reporting necessity as the hitting-set/intersection
  structure (G3), (ii) conditional co-ablation to surface backups (J4), (iii) SMC posteriors and
  restarts that preserve multimodality (B6, H5), (iv) reporting membership as ranges over the Rashomon
  set (model-class reliance) rather than a single set, and (v) weighing "near-necessary" as a graded
  `θ`-probability of necessity (G3), not a binary claim.

- **Non-linear group effects (AND-type sufficiency, disinhibition, gain normalization).** Linear
  compressed sensing decoders assume additivity and fail (C1–C2); Fourier-sparse set-function learning
  (C3), second-order BOCS surrogates (I1), MSA interaction indices (E3), interaction-aware gradient
  attribution (GIM, J2) and conditional co-ablation (J4) are the methods that represent interactions
  explicitly. Group-testing designs should use the *complex* (hyperedge) model rather than the OR model
  for keep-only pools.

- **Ensemble noise and budget accounting.** Every candidate evaluation is a noisy Bernoulli/graded
  draw; racing and successive halving (I4), common random numbers, joint `(design, θ)` GP models for
  risk measures (N1) and Hoeffding-style sample-size bounds for pass probabilities keep the `θ`
  multiplier from consuming the budget. CVaR-type criteria need more draws than means; reserve them
  for the shortlist.

- **Seed and ordering instability.** Greedy sequential procedures are order-dependent (J1), circuit
  discovery variance has resampling and per-sample components (J5), and different equivalent
  mechanisms can be found on different runs (E1). Use permutation-invariant algorithms where possible,
  run several seeds/orderings as part of the method (not as an afterthought), certify inclusion
  decisions under subsampling (Anani et al., J5), and score stability explicitly.

- **Metric and reporting choices.** Faithfulness scores are sensitive to metric and ablation type
  (Miller et al.), and component-overlap comparisons are sensitive to what is extracted and at what
  granularity (Sheng & Fu): pre-register the readout, threshold, ablation semantics, circuit-size
  sweep and comparison granularity (node vs. type vs. role), and evaluate on planted synthetic
  circuits (InterpBench analogue) before real graphs.

- **Cross-graph transfer.** Universality is a hypothesis, not a fact (J6); mapping uncertainty between
  graphs propagates into priors (I5); ICP-style invariance across environments is the sharper
  criterion, but needs aligned variables and enough environments (K1). Compare mechanisms at the level
  of roles/abstract causal models (J3), keep a cold-start control on the second graph, and treat
  transfer gain as evidence rather than as an assumption.

## 5. Synthesis (c): open questions

1. **Which response model for keep-only pools?** A single AND-term with inhibitors, a multi-term monotone
   DNF, or a graded (rhythmicity-score) likelihood? Calibration of the group-testing posterior depends
   entirely on this choice; the query-complexity theory (B2–B5) assumes noiseless binary answers and
   has not been extended to ensemble-noisy graded responses.
2. **How far does structural pre-screening go before it starts excluding mechanisms?** FVS and
   reachability arguments (L1) are attractor-level; a sub-mechanism sufficient in isolation may rely
   on tonic input from nodes that are not on any `u → Y` cycle. The right pre-screen should probably be
   a *prior*, not a hard filter.
3. **Is the readout, as a set function, spectrally sparse enough for C3 to work in practice?** Nobody
   has measured the Walsh–Hadamard spectrum of a rhythmicity score of a recurrent rate network; a
   pilot on synthetic circuits would decide whether Fourier-sparse learning or BOCS is the right
   interaction surrogate.
4. **What is the right "necessity" statistic under redundancy?** Single-node silencing in the full
   network (expensive) vs. leave-one-out within the mechanism (cheap) vs. conditional co-ablation:
   these disagree exactly when backups exist, and the literature offers definitions (probability of
   necessity, hitting sets) but no consensus estimator under a budget.
5. **Can differentiable-simulator methods be made black-box-comparable?** A fair tournament needs
   either a call-count equivalent for gradient steps or wall-clock accounting; also, whether gradients
   through long oscillatory rollouts are usable (exploding sensitivities) is untested for this model
   class.
6. **How should calibration of `p(z_i = 1)` be scored when the truth is a set of equivalent
   mechanisms?** Brier/log scores against a single planted circuit penalize correct multimodal
   posteriors; the target should probably be the marginal over all planted equivalents (Rashomon-aware
   scoring), which no benchmark currently provides.
7. **Transfer evaluation without a shared node identity.** The cross-graph mapping is a candidate
   table with uncertainty; ICP-style invariance and role-level comparison (J3/K1) need a formal
   statement of what "the same mechanism" means when nodes only correspond probabilistically.
8. **Non-adaptive vs. adaptive designs under parallelism.** With many cores, large non-adaptive batches
   (A3, B1 non-adaptive designs, C3 random subsets) may beat sequential EIG in wall-clock; the trade-off
   between adaptivity's log-factor savings (C2) and batch parallelism has not been quantified for this
   cost model.

---

## 6. Compact index of all entries

| ID | Family / method | As-is? | Budget 200–5k? | Suggested role |
|---|---|---|---|---|
| A1 | Bayesian experimental design (EIG, DAD, MINEBED) | Partial (needs surrogate likelihood) | Yes with surrogate | Acquisition backbone |
| A2 | CBED / ABCI / GO-CBED (causal BED) | No as published | Marginal | Acquisition ideas |
| A3 | Multi-perturbation batch design (submodular) | Partial | Yes | Non-adaptive batches |
| A4 | Active optimal intervention design (linear SEM) | No as published | Yes (acquisition) | Closed-form acquisition template |
| A5 | Causal BO / MCBO (minimal intervention sets) | Partial | Yes (pruning) | Graph-based pre-pruning |
| A6 | DCDI / ENCO (gated structure learning) | No (needs gradients) | No | Gate parametrization |
| A7 | Adaptive submodularity / EC2 | Yes | Yes | Sequential test selection with guarantees |
| A8 | Level-set active learning (LSE, straddle) | Yes (θ-space) | Yes | Threshold-robustness over θ |
| B1 | Group testing (adaptive / non-adaptive) | Yes | Yes | Yardstick; necessity pools |
| B2 | Hidden hypergraph / monotone-DNF learning | Yes | Marginal | Sufficiency-pool theory, multiple mechanisms |
| B3 | Junta learning (non-monotone relevant variables) | Yes | Marginal | Non-monotone yardstick |
| B4 | ddmin / ProbDD / PMA / QuickXplain | Yes | Yes | Deterministic minimal-subset baseline |
| B5 | Threshold / inhibitor group testing, Boolean CS | Yes | Marginal | Inhibitory-node response models |
| B6 | Bayesian sequential group testing (SMC + EIG) | Yes | Yes | **Tournament arm 1** |
| B7 | Noisy group testing for neural connectivity | Yes | Yes | Precedent, noise handling |
| B8 | GTBO (group-testing pre-screen for BO) | Yes | Yes | Two-phase template |
| C1 | CS from pooled perturbations (RESCUME, Lasso, model-based CS) | Partial | Yes | Pooling precedent; additivity caveat |
| C2 | Nonlinear/1-bit CS; adaptivity | Partial | Yes | Limits of linear-index recovery |
| C3 | Fourier-sparse set functions (SPEX etc.) | Yes | Marginal–Yes | Interaction-aware surrogate |
| D1 | SINDy family (E-, W-, UQ-, active, network) | Yes | Yes | Executable effective model of `M`; roles |
| E1 | Degeneracy / ensembles / SBI | Yes | Partial | Robustness definition |
| E2 | Lesion analysis and its perils | Yes | No (exhaustive) / Yes (shortlist) | Necessity confirmation |
| E3 | Multi-perturbation Shapley (MSA), Banzhaf | Yes | Shortlist only | Roles, interactions |
| E4 | Active circuit-mapping design (Beta–Bernoulli) | Yes | Yes | Minimal active loop |
| E5 | Connectome-constrained model ensembles | Yes | Yes | Ensemble-consistency protocol |
| F1 | Hard-concrete / Gumbel / STE masks | No (needs autodiff port) | Wall-clock | **Tournament arm 4** |
| F2 | Head pruning, differentiable masking, Edge Pruning | No (port) | Wall-clock | Edge-level mechanism |
| F3 | Probabilistic reparameterization | Yes | Yes | Black-box mask relaxation |
| G1 | Submodular greedy | Yes | Pre-pruned only | Baseline theory |
| G2 | Submodularity ratio / curvature / weak submodularity | Yes | Pre-pruned only | Diagnose when greedy is trustworthy |
| G3 | Necessity/sufficiency; abductive explanations; minimal subsets | Yes (probabilistic) | Yes | Definitions of PS/PN |
| G4 | Prize-collecting Steiner / connected subgraph | Yes | Yes (no calls) | Structural completion |
| G5 | Marginal-contribution estimators | Yes | Shortlist | Query cost reference |
| H1 | Cross-entropy method | Yes | Yes | **Tournament arm 2** |
| H2 | PBIL / BOA (linkage learning) | Yes | Marginal | Co-membership structure |
| H3 | CMA-ES on relaxed masks | Yes | Marginal | Continuous sub-problems |
| H4 | GA / NSGA-II | Yes | Marginal | Robustness–compactness front |
| H5 | SMC on binary spaces | Yes (with test likelihood) | Yes | Posterior machinery |
| I1 | BOCS (sparse quadratic + TS) | Yes | Yes (pre-screened) | **Tournament arm 3** |
| I2 | COMBO / Casmopolitan / Bounce / SAASBO | Yes | Yes (≤ ~300 vars) | Control arm |
| I3 | Cost-aware / multi-fidelity SMBO | Yes | Yes | Spend cheap vs expensive queries |
| I4 | Racing / successive halving / BAI | Yes | Yes | θ-replicate budget control |
| I5 | Multi-task BO / warm starts | Yes | Yes | Cross-graph transfer |
| J1 | ACDC (greedy edge ablation) | Conceptually | No | Baseline analogue |
| J2 | EAP / EAP-IG / GIM | No (gradients) | Yes with port | Prior from gradients |
| J3 | Path patching, causal scrubbing, causal abstraction | Partial | Yes | Role testing |
| J4 | Ablation semantics, Hydra, conditional co-ablation | Yes (zero-ablation) | Shortlist | Backups / near-necessity |
| J5 | Evaluation: faithfulness robustness, MIB, InterpBench, variance, certification | Yes | Yes | Tournament protocol |
| J6 | Sparse feature circuits; universality | Conceptual | n/a | Transfer framing |
| K1 | ICP / IRM and limits | Partial | Yes (≤ 15 candidates) | Invariance-based transfer |
| L1 | Feedback vertex sets; structure-based control | Yes | Yes (no calls) | **Tournament arm 5 (prior)** |
| L2 | Structural controllability; driver nodes | Yes | Yes (no calls) | Structural ranking |
| M1 | MDL; Rashomon sets; model-class reliance | Yes | Yes | Size selection; multiplicity reporting |
| N1 | CVaR / risk-measure BO / DRBO / scenario bounds | Yes | Shortlist | Robustness criterion |
| O1 | Sequential design for computer experiments; batch BO | Yes | Yes | Parallel batching |
