# BrainIR v1 — order-invariant canonical group elimination with enumerated alternatives and a causal selection rule

Method file `src/brainir/methods/brainir_v1.py` (registered as `brainir_v1`, version 1.0; the registry imports it). Tests:
`tests/test_method_brainir_v1.py`. Composed by an oracle-free developer from the five Phase 2 candidates (`greedy_plus`,
`cem_search`, `group_probe`, `surrogate_search`, `evo_pareto`) and the cross-connectome component (`brainir.discovery.joint`), on
the evidence of the held-out selection suite (`research/phase2/selection_results/`, aggregates only) and of my own synthetic
experiments (section 12). Nothing in the method refers to a dataset, a cell type, a neuron id, a mechanism size or a threshold
tuned to an instance.

## 1. What v1 is, in one paragraph

v1 restricts the candidates to the neurons that can possibly shape the readout (exact reachability and signs, then a verified
activity filter), orders them by a permutation-equivariant structural relevance, and runs adaptive group elimination over
keep-only sets in that fixed order — least relevant first — until the kept set is 1-minimal. Every accept/reject decision is a
sequential strict majority over parameter replicates on which the intact network works, extended to more replicates when the
first ones disagree. Because the order is canonical and no random choice exists anywhere in the search, the same mechanism comes
out of any node order and any seed unless the evidence itself is marginal. v1 then (i) measures essentiality by single silencing
in the intact network and screens the other active neurons by group silencing for members that are necessary only in context,
(ii) enumerates the other sufficient sets deterministically (disjoint sets in the complement, and for every non-essential member a
hitting-set enumeration of its replacements), (iii) keeps the canonical set unless another set is *decisively* better — better
validated on fresh replicates; smaller (Occam), unless the intact network relies decisively more, per member, on the larger one;
more robust between equal sizes — each noisy key with a statistical margin, and (iv) reports every set it could not separate from
the chosen one with an equal share of the probability mass instead of silently picking one. A minimality certificate on fresh replicates, a size–error curve, fidelity estimates,
generic roles, pre-registered intervention predictions and, when the bundle holds a network of another dataset, identity claims
from a verified transfer of the final core (paid from the same budget pool, never changing the core) complete the result.

## 2. Formulation

Let `U` be the candidate neurons (everything except stimulus and readout) and `θ ~ P` the model's parameter replicates. For
`S ⊆ U`, `keep(S)` keeps only `S` (plus stimulus and readout) and `sil(A)` silences `A` in the intact network. The functional
criterion turns a simulation into a verdict `pass ∈ {0, 1}`; write

* `π(S) = P_θ[pass(keep(S); θ)]` (sufficiency), estimated on *working* replicates, i.e. replicates on which the intact network
  passes (on the others no member can be told from a non-member);
* `σ(A) = P_θ[pass(sil(A); θ)]` (function surviving the silencing of `A` in the intact network).

Definitions (all decisions use the strict-majority estimate `π̂ ≥ 1/2` of section 4):

* `S` is **sufficient** if `π(S) ≥ 1/2`; **1-minimal** if in addition `π(S \ {x}) < 1/2` for every `x ∈ S`.
* `x` is **essential** if `σ({x}) < 1/2`, estimated by the *pooled necessity test*: every working replicate is run (no early
  stop at two agreeing replicates), a split is extended to up to 5 working replicates, and the verdict pools them with the 3 fresh
  validation replicates on which the intact network passes — essential iff more than half of the pooled replicates fail. The
  **context members** `E = {x ∉ M : σ({x}) < 1/2}` are neurons the intact network needs although no keep-only probe can see them
  (a keep-only probe also removes the competitor they suppress); they are found by the screen and admitted only by the pooled test.
* A **candidate mechanism** is `C = S ∪ E` with `S` 1-minimal sufficient. `𝓜` is the set of candidate mechanisms found by the
  deterministic enumeration of section 5.
* **Reliance** of the intact network on `C ∈ 𝓜`: with `D_C = C \ ∩𝓜` its distinctive members,
  `ρ_C(θ) = ( 1[fail(sil(D_C); θ)] + Δ(readout | sil(D_C); θ) ) / |D_C|`, where `Δ` is the mean relative change of the readout
  statistics (criterion score, readout peak / mean / range, active readout count, frequency, criterion-specific means), each in
  `[0, 1]`. It is per distinctive member, so a larger set has to change the intact readout proportionally more.
* **Robustness** `r(C)`: keep-only pass fraction under a stress ensemble (half the probes with all parameter sds doubled, half
  with multiplicative weight noise sd 0.2).

**Objective.** Return `M* ∈ 𝓜` chosen by pairwise comparison with the canonical set as the incumbent (a challenger replaces it
only if it is *decisively* better; noisy keys carry margins):

1. validated sufficiency on fresh replicates (candidates below 1/2 are discarded; a difference counts only if ≥ 0.5);
2. **Occam with a reliance exception** — between sets of different size the smaller wins, unless the intact network relies
   decisively more, per member, on the larger one (paired over the same working replicates: every replicate agrees on the sign and
   the mean difference is ≥ max(0.05, 0.25 × the larger reliance));
3. between sets of equal size: robustness `r`, decisive only if the stress pass fractions are 4/4 vs 0/4 (margin 1.0);
4. otherwise the canonical order (the set the canonical elimination found first) — noise-free and permutation-equivariant.

Reliance is deliberately *not* used between sets of equal size: there the structural order measures the same thing (which set
carries more of the drive) without replicate noise, and my experiments (section 12) showed reliance flipping between equally
sized alternatives across seeds.

Minimality with evidence: `M*` must stay 1-minimal on the pooled working + fresh replicates (members whose removal passes are
dropped), except context members, which are justified by `σ({x}) < 1/2`.

**Uncertainty model.** Let `T ⊆ 𝓜` be `M*` and the mechanisms not decisively worse than it (they differ from `M*` only by the
canonical order), and `L` the decisively worse ones. For every neuron `i`,
`p_i = Σ_{C ∈ T, i ∈ C} c_i(C) / |T|`, raised to at least `0.15` for members of `L`, where `c_i(C)` is the evidence class of `i`
in `C`: 0.97 if its single silencing fails the function, 0.90 if its removal from the sufficient set fails (certified), 0.60 if
the budget ran out before it was tested. Non-members keep their evidence class: 0.03 (removed by a passing decision), 0.01 (silent
in every passing intact run), 0.002 (structurally unable to influence the readout). A unique mechanism therefore gets the
calibrated greedy_plus values; `k` equally supported mechanisms share the mass `1/k`.

## 3. Algorithm

```
discover(problem, sim, seed, cfg):
  working <- replicate seeds b+17+i (b = (seed mod 16) x 300) on which the intact network passes (3; more on demand, up to 5)
  K <- U ∩ {excitatory-reachable from the stimulus} ∩ {reaches the readout} ∩ {sign != 0}        # exact, no calls
  if decide(K \ silent_in_intact): K <- K \ silent_in_intact                                      # verified activity filter
  key(i) <- (log relevance(i) [+ w·logit(prior_i)], weighted degree(i)) on the subgraph K ∪ stimulus ∪ readout  # equivariant
  M1 <- eliminate(K, order = sort(K, key) ascending)                                             # canonical 1-minimal set
  if validate(M1) fails on most fresh replicates: add the failing replicate to the working seeds; M1 <- eliminate(K, ...)
  essential[x] <- pooled_necessity(x)  for x in M1          # >= 3 working + 3 fresh replicates, majority must fail
  E <- necessity_screen(K \ M1)          # group silencing, bisection, cap 30 %; an isolated neuron is admitted by pooled_necessity
  alternatives <- disjoint(K \ M1) ∪ replacements(x) for non-essential x in M1   # deterministic hitting-set enumeration
  C <- [M1 ∪ E] + [A ∪ E for A in alternatives]
  evaluate every C: validation (3 common fresh replicates), stress (4 probes); reliance (5 paired working replicates) when sizes differ
  M* <- canonical C unless a challenger is decisively better (validation; Occam unless decisively more relied on; robustness)
  M* <- certify(M*)          # members whose removal passes on pooled working + fresh replicates are dropped
  curve <- fresh-replicate error of 3 points of the search path, M*, and M* minus each member
  return M*, p (section 2), essential, alternatives (tied first), roles, loop, dynamics of the intact network,
         fidelity, intervention predictions, size-error curve, [cross-connectome claims]

eliminate(K, order):                                  # greedy_plus's adaptive group testing, deterministic order
  queue <- order; chunk <- 25 % of the queue
  while queue:
    X <- next chunk; if decide(K \ X): K <- K \ X; chunk *= 2; move neurons silent in the passing runs to the front
    else: bisect X (keep the half whose removal passes removed) down to one necessary neuron; chunk /= 2
  repeat <= 3 times: for x in order: if decide(K \ {x}): K <- K \ {x}                       # 1-minimality
  return K

decide(S): run the working replicates one at a time until the strict majority of 3 is determined; if they disagreed,
           continue with further working replicates until the strict majority of 5 is determined (adaptive replication)

replacements(x): excluded <- {x}; up to 2 times:
    start <- K \ excluded (or U \ excluded if that fails: a filler may be silent in the intact network)
    A <- eliminate(start, protected = M1 \ excluded); record A; excluded <- excluded ∪ (A \ M1)
```

Cross-connectome step (section 10; only when the bundle holds a network of ANOTHER dataset, only after the core is final and
validated, never changing the core):

```
  allowance <- min(calls left, 0.25 x declared budget, 60 x (|M*| + 2));  skip if < 30          # same budget pool as the core
  aux <- sim.spawn(other network, max_calls=allowance)                                            # counted in sim.total_calls()
  tr <- joint verified transfer of M*   # image -> keep-only probes -> minimisation -> counterparts of essential members
                                        # -> reliance of the other intact network -> validation on >= 2 fresh replicates
  if tr verified (validated, completely minimised, essential structure reproduced, relied on by the other intact network):
      if the matched, mutually aligned pairs pair up all members of M* and of the image one to one:
          identity claims <- those pairs whose fingerprint evidence beats 'none' in BOTH directions;
                             confidence = calibrated identity probability sigmoid(a + b logit(w_ab w_ba) + c edges)
  elif calls left in the allowance >= 60: own v1 discovery of the other network (no identity claims), with the transported
                                          prior unless the image was rejected on causal grounds
  role_alignment <- roles and signed role graphs of M* and the other network's mechanism (separate output)
```

## 4. Decisions, acquisition and stopping

* **Decisions.** Sequential strict majority over working replicates (greedy_plus): 2 agreeing replicates settle a decision (2
  calls), a split goes to 3; v1 adds *adaptive replication* — a split verdict is re-decided by the strict majority of up to 5
  working replicates (the same replicates for every decision, so outcomes are shared through the cache).
* **Acquisition.** The probe sequence is fixed by the canonical order and the outcomes: the chunk doubles after a passing group
  and halves after a failing one; bisection isolates one necessary neuron per failing chunk (about `k log2(n/k)` decisions for a
  `k`-member mechanism among `n` candidates); neurons that fall silent in a passing probe are queued first (their removal
  cannot matter). Full-network probes are used only for what keep-only probes cannot see: essentiality, context members,
  reliance. There is no random order, restart or sample anywhere.
* **Stopping rule.** The elimination stops when the kept set is 1-minimal (every member individually tested against the final
  set, re-checked up to three rounds for non-monotone effects). The enumeration stops when no further sufficient set exists
  outside the exclusions, or after 4 alternatives / 2 fillers per member / half of the remaining budget. The method stops when all
  phases are done — never because the budget is used up; unspent budget is not used. If the budget does run out, the current
  passing set (every removal verified) is returned with `P_UNTESTED` for untested members and `budget_exhausted` in the
  diagnostics; finishing phases are guarded (running out ends the phase, an unexpected error is recorded, the mechanism found is
  kept).
* **Size–error curve** (`diagnostics["size_error_curve"]`): fresh-replicate error of three passing sets along the canonical search
  path, of the returned core and of the core minus each member. The returned point is the smallest set on the path whose
  fresh-seed error is below 0.5 and from which no member can be removed (every leave-one-out point below it has error ≥ 0.5);
  compactness never removes a member whose removal breaks the function.
* **Intervention predictions** (`diagnostics["intervention_predictions"]`, pre-registered): for every core member the predicted
  effect of silencing it alone in the intact network (`silence_alone`: the silencing runs behind `essential`, with their pass
  fraction), and for its strongest in-core edge (outgoing, else incoming; self-loops included) a structural prediction — no
  edge-level intervention exists in the simulator. The edge is *cutting* if removing it leaves its presynaptic member with no
  in-core route to the readout, or takes it off every recurrent loop of the core under a criterion that needs recurrence (rhythm,
  persistence, ramp). Removing it is predicted to break the function in the intact network if the edge is cutting and the member
  is essential (`predicted_function_preserved`), and in the keep-only core if the edge is cutting and the member is necessary
  there (`predicted_function_preserved_in_core`).

## 5. Where each component comes from, and the evidence

Selection-suite numbers are from `SELECTION_RESULTS.md` (57 held-out instances x 2 node orders x 3 seeds, 1,000 calls; "identity"
= mean pairwise Jaccard / fraction of instances whose 6 runs agree).

| component | source | evidence for it |
|---|---|---|
| exact restriction (excitatory reachability from the stimulus, reachability of the readout, sign) + verified activity filter | greedy_plus (reachability, verified activity pruning), group_probe (excitatory reachability, sign 0) | every candidate that uses it reaches structural success 1.00; on the real network it leaves ~90 of 4,459 candidates (greedy_plus: 87) |
| canonical deterministic order (structural relevance, least relevant removed first) | group_probe (the only candidate without a random search order); relevance = surrogate_search's random-walk mass, restricted to excitatory forward flow | identity 0.95 / 0.86 for group_probe vs 0.88 / 0.75 greedy_plus (seeded random order), 0.91 / 0.81 cem_search (sampling), 0.86 / 0.68 evo_pareto, 0.85 / 0.63 surrogate_search, 0.83 / 0.63 greedy_reference; at 50 calls group_probe keeps ~0.91 identical cores, greedy_plus ~0.69, cem_search ~0.65, surrogate_search ~0.17 |
| adaptive group elimination with bisection and activity queue; 1-minimality rounds | greedy_plus | median 88 calls (68 small / 192 medium / 244 large), success 1.00 at every budget from 50 to 2,000 calls, causal functional success 1.00 |
| sequential strict majority over 3 working replicates | greedy_plus | best robust pass (0.93) and causal functional success (1.00) of all candidates |
| adaptive replication of split decisions (up to 5) | new in v1 (the review's racing / Hoeffding argument, methods_review §4) | split decisions are where replicates disagree; the extension fired 0.06 times per run on my small suite, 1.6 on the medium suite and 3–4 times on the real networks (section 12.3) — cheap where decisions are clear, active where replicates disagree |
| fresh-seed validation + add-back re-run | greedy_plus | as above |
| single silencing of members (essential claims), pooled over ≥ 3 working + 3 fresh replicates | all candidates (single silencing); pooling is new in v1 | essential accuracy 1.00 for all candidates; on the real network a context member admitted on two agreeing working replicates passed its single silencing on 7 of 8 fresh replicates (section 12.5) — two replicates cannot settle a claim that changes the core |
| group-silencing necessity screen with bisection (context members), capped at 30 % of the budget | greedy_plus | causal functional success 1.00 and WTA structural success 1.00; on large graphs 244 calls / 88 s median, vs group_probe's single-neuron screen + spend-down 706 calls / 851 s (causal 0.89) |
| deterministic enumeration of alternatives (disjoint complements, per-member replacements, iterated exclusion of found fillers) | greedy_plus (disjoint + replacement), group_probe (backup search per non-essential member), evo_pareto / group_probe §8 (hitting-set exclusion levels) | two_implementations functional success 0.98 (greedy_plus) and 1.00 (surrogate); the enumeration replaces greedy_plus's randomized restart |
| selection: validation → Occam unless decisively more relied on → robustness → canonical order | greedy_plus's ranking (nominal, stress, reliance, size), re-ordered and given decisiveness margins | greedy_plus has the highest planted success (0.99 vs 0.96 group_probe / evo_pareto, 0.94 surrogate, 0.93 cem) — the ranking picks the planted set among sufficient distractors; margins keep noise from overriding the canonical choice (section 12: symmetric redundant pairs) |
| per-member reliance with a generic readout-change statistic | new in v1 | greedy_plus's reliance (readout median peak) is uninformative when few readout neurons are active (the real networks: 2 of 144); per-member normalisation removes the size confound between a 1-neuron and a 2-neuron sufficient set (section 12) |
| minimality certificate on fresh replicates | cem_search / surrogate (verify after cleanup), greedy_plus (leave-one-out) | functional success needs 1-minimality on fresh seeds (0.87–0.91 for the candidates) |
| evidence-class probabilities | greedy_plus | Brier 0.0009, the best (group_probe 0.0028, evo 0.0052, surrogate 0.0055, cem 0.01) |
| mixture over tied mechanisms | cem_search (verified-set mixture), the contract's "equally supported alternatives" | honest shared mass when the evidence cannot separate mechanisms (section 12) |
| generic roles from sign, core wiring and criterion | greedy_plus | role accuracy 0.95, the best (cem 0.94, evo 0.93, surrogate 0.92, group_probe 0.88) |
| predicted dynamics = intact network under the stimulus | cem_search, surrogate_search, group_probe | the schema defines them for the benchmark stimulus |
| verified cross-connectome transfer of the final core, from the same budget pool; identity claims only from a verified transfer | joint (verified transfer, correspondence), reworked after review E | pair tournament: joint solves both networks for every base method (0.96–1.00) with ~40 % fewer total calls, transfer alone only ~0.70 — but review E showed the gain rests on identical wiring and the old claims on alignment scores; my own pair experiments (section 12.6) measure the claims that remain |

**Dropped, and why.**

* *Surrogate model* (surrogate_search): no predictive skill where it would matter (its own report: pre-registered Brier 0.218 vs
  base rate 0.212 at n = 500, 0.215 vs 0.215 at budget 250), lowest identity consistency (0.85 / 0.63; ~0.17 identical at 50
  calls), functional success collapses at low budget (0.27 at 50 calls). The validated elimination does the work.
* *Cross-entropy sampling* (cem_search): stochastic samples make the path seed-dependent (0.91 / 0.81, ~0.65 identical at 50
  calls; causal functional ~0.77 at 50 calls) and it has the lowest planted success (0.93). Its exoneration idea is kept as the
  activity queue.
* *NSGA-II evolution* (evo_pareto): 823 median calls (9x the others), causal functional 0.96, identity 0.86 / 0.68, functional
  success 0.16 at 50 calls. Its knee / MDL framing survives only as the reported size–error curve.
* *Randomized restarts and random chunk order* (greedy_plus): the source of its lower consistency (0.88 / 0.75; ~0.69 at 50
  calls); replaced by the canonical order and the deterministic enumeration.
* *Bernoulli posterior and max-entropy group choice* (group_probe): not needed once the order is canonical, and its marginals are
  path-conditional (its own §8; Brier 0.0028 vs greedy_plus's 0.0009). *Spend-down and single-neuron necessity screen*
  (group_probe): the large-graph cost (706 calls, 851 s median, causal 0.89).
* *Knee / add-back of robustness members* (evo_pareto, cem_search `add_backs`): trade minimality for robustness; functional
  success requires 1-minimality.

## 6. Switches (every component can be turned off by configuration)

Every switched-off configuration runs and returns a valid result within the budget (`test_every_switched_off_configuration_runs_within_budget`).

| switch (default) | off means |
|---|---|
| `structural_pruning` (True) | every candidate enters the pool (no reachability / sign exclusion); probabilities 0.002 are not assigned |
| `activity_pruning` (True) | neurons silent in the intact runs stay in the pool (more elimination decisions) |
| `use_structural_prior` (True) | seeded random removal order instead of the canonical one (greedy_plus style): the choice among equivalent sets depends on the seed and node order |
| `use_group_testing` (True) | one candidate per probe (plain backward elimination, `O(n)` decisions) |
| `use_active_selection` (True) | fixed chunk size (no doubling / halving) and no activity-guided queue; bisection of failing chunks remains |
| `n_seeds_per_decision` (3) | replicates per decision (strict majority) |
| `adaptive_replication` (True) | split decisions are not extended beyond `n_seeds_per_decision` |
| `minimality_cleanup` (True) | no 1-minimality rounds after the group phase and no fresh-seed certificate |
| `member_essentiality` (True) | members are not silenced alone: `essential` is None, no replacement searches (they need non-essential members) |
| `necessity_screen` (True) | no context members (e.g. the lateral inhibitor of a winner-take-all circuit is missed) |
| `max_alternatives` (4) | 0: no alternatives, the canonical set is the answer and carries the full probability |
| `reliance_tiebreak` (True) | pure Occam between sets of different size (a larger set can no longer win by the intact network's reliance) |
| `robust_objective` (True) | no stress probes: nominal-only selection and fidelity |
| `uncertainty_model` ("posterior") | "point": probability 1 for the core, 0 elsewhere |
| `use_cross_connectome` (True) | single-network run: no auxiliary simulations, no cross-connectome claims |
| `cross_fallback_discovery` (True) | if the verified transfer fails, no own discovery on the other network (no role alignment; never claims) |
| `joint_config` (see section 7) | joint.py's own switches, passed through: `require_essential_structure`, `require_reliance` (verification checks (iii), (iv)), `claims_require_verified_link`, `claims_require_complete_image`, `adoption` ("own_evidence" / "never", discover_pair only), `consistency_prune` (discover_pair only) — each False / "never" drops that rule and still returns a valid result |

## 7. Hyper-parameters (defaults; none tuned on hidden instances)

The default configuration below is FROZEN with the final code (`brainir_v1.py` sha256 `3a07cf80…`, `joint.py` `38609d27…`,
`correspondence.py` `11acef92…`); every final number in section 12 comes from it. The only value fitted on data is the identity
calibration (my dev pairs, section 12.6); everything else was set before the experiments or changed only as section 12.2 records.

| name | default | meaning, evidence |
|---|---|---|
| `n_seeds_per_decision` | 3 | strict majority of 3 (greedy_plus; robust pass 0.93) |
| `max_decision_seeds` | 5 | adaptive replication of split decisions and the reliance comparison |
| `max_seed_trials` | 10 | intact runs tried to collect working replicates |
| `validation_seeds` | 3 | fresh replicates common to every candidate mechanism (greedy_plus) |
| `relevance_hops`, `relevance_damping` | 6, 0.6 | random-walk horizon; 6 hops reach the far end of a 5-neuron relay loop |
| `initial_chunk_fraction` | 0.25 | first group size (greedy_plus) |
| `necessity_screen_fraction` | 0.3 | call cap of the screen (greedy_plus) |
| `max_alternatives`, `max_fillers_per_member`, `alternatives_budget_fraction` | 4, 2, 0.5 | enumeration caps |
| `stress_probes`, `stress_sd_factor`, `stress_noise_sd` | 4, 2.0, 0.2 | the tournament's robustness definitions |
| `reliance_margin`, `reliance_rel_margin` | 0.05, 0.25 | decisive reliance difference (set before the experiments; section 12.2: the planted chain beats a sufficient hub by 0.060–0.074 per member in every run, a 2-hub pair beats a planted single neuron by only 0.020–0.037) |
| `validation_margin`, `stress_margin` | 0.5, 1.0 | decisive pass-fraction differences (3 fresh replicates; 4 stress probes: only 4/4 vs 0/4 — with 0.75, identical redundant pairs switched on 1 of 6 runs by replicate noise, section 12.2) |
| `loser_weight` | 0.15 | floor probability of members of decisively worse mechanisms (greedy_plus's alternative-only value) |
| `size_error_points` | 3 | search-path points of the size–error curve |
| `aux_budget_fraction`, `aux_calls_per_member`, `aux_min_calls` | 0.25, 60, 30 | allowance of the cross-connectome step from the same pool: min(calls left, 0.25 x budget, 60 x (core size + 2)); skipped below 30 |
| `cross_fallback_min_calls` | 60 | calls left in the allowance needed for v1's own discovery on the other network after a failed transfer |
| `joint_config` | `identity_calibration` fitted (section 12.6) | joint's verified-transfer and claim settings (joint.DEFAULT_CONFIG otherwise: 3 probe seeds, 2 fresh validation seeds, essential structure and reliance required, claims only for matched pairs) |
| `t_end` | None | the bundle's protocol for every simulation (no shortened screening) |
| (seed layout) | fixed | replicate seeds of a run: block `b = (seed mod 16) x 300`; working `b+17..`, fresh validation `b+150..`, stress `b+250..`; every queried seed < 5,000 (5,000+ are reserved for independent scoring); joint's seeds use `seed mod 4` |
| `prior`, `prior_weight` | absent, 1.0 | optional `{position: p}`: adds `w·logit(p)` to the canonical order key; it never decides membership |

## 8. Complexity

With `n` candidates after restriction and a `k`-member mechanism: canonical elimination ≈ `k (log2(n/k) + 2)` decisions of 2–3
calls (keep-only); essentiality `k` decisions (full network); screen ≈ `|K \ M| / g*` group decisions plus `2 log2 g*` per context
member found (full network); each alternative one more elimination (keep-only); selection `3 + 4` keep-only calls and 5 full-network
calls per candidate; certificate `k (2 + 3)` keep-only calls; curve `3 x 3 + k x 3`. No-call parts: two BFS and six sparse
mat-vecs. Memory: the simulator's trajectory. Wall time is dominated by full-network simulations on large graphs (section 12).

## 9. Known failure modes

1. **Exact structural symmetry.** Two mechanisms related by a graph automorphism (e.g. two identical E–I pairs) cannot be told
   apart by any permutation-invariant quantity; the canonical order then falls back to the node position, so the reported core is
   the same for every seed of one node order but can differ between node orders. The probabilities say so (the two mechanisms
   share the mass, ~0.45 per member), and the generic role labels match the generator's arbitrary "primary vs backup" labelling
   only half of the time. Real connectomes practically never contain exact automorphisms; near-symmetric mechanisms are ordered by
   their (different) weights.
2. **Marginal mechanisms.** When a set passes on about half of the replicates, decisions stay coin flips even with adaptive
   replication; the core size can then differ between seeds, and the fresh-seed certificate may drop or keep a member. The
   size–error curve and the fidelity fields report such cases.
3. **Reliance is a heuristic for "which sufficient set the intact network uses".** It measures how much silencing a set changes
   the intact readout; a strongly driven distractor that carries much of the readout's drive can be relied on more than a planted
   motif that is sufficient but redundant in the intact network. Per-member normalisation and the decisiveness margins make it
   conservative (Occam decides when it is not decisive), so sufficient distractors (a hub under an activity band) can still be
   reported as the core with the planted set as an alternative (probability ≥ 0.15) — or the other way round. Measured case: on my
   pair suites, network a of the feed-forward-driver pairs with hub distractors (2 dev + 2 held-out pairs) holds two or three single
   hubs that each drive the readout alone; the intact network relies more on one hub per member (0.047) than on the planted 3-neuron
   chain (0.020 per member, 0.06 in total), so v1 returns a hub (tied with the other hubs, ~0.5 each) and reports the chain as a
   decisively worse alternative (0.15) — 4 of the 106 pair runs; greedy_plus, which ranks total reliance before size, returns the
   chain there but would return the 2-hub pair of the memory switch (section 12.2).
4. **Context members.** The group-silencing screen can clear a group in which two members compensate each other ("synergy only")
   and stops at its call cap (30 % of the budget); unscreened neurons keep their sufficiency-based probability.
5. **Transient members.** The activity filter is verified by one decision; a member active only before the analysis window is
   kept only if removing the silent group breaks that decision.
6. **Non-monotone effects** (an inhibitor whose removal creates the function, disinhibition inside a chunk) can make the group
   phase isolate a neuron that is needed only in that context; the 1-minimality rounds and the certificate remove it again at extra
   cost, but the path — and on redundant instances the canonical set — can depend on it.
7. **Cross-connectome.** Identity claims come only from a verified transfer (validated on at least two fresh replicates,
   completely minimised, the essential members' counterparts essential, relied on by the other intact network) and only for
   matched member pairs whose anchor-fingerprint evidence beats the 'none' option in both directions; an implementation shift or a
   failed transfer yields a role-level alignment (`diagnostics["role_alignment"]`) and no identity claim. A mechanism without
   essential members (redundant copies) cannot pass (iv) unless silencing the whole image breaks the function, so its transfer
   usually fails and no claim is made — the price of never claiming from sufficiency alone. The identity probability is calibrated on my synthetic pairs (section 12.6), whose anchor evidence differs from the real
   bundle's (review E finding 5): on real data it is an extrapolation. A decoy that copies a member's anchor profile is separated
   only by the reproduced signed edges and by simulation in the other network. The step spends from the same budget pool after
   the core: on large networks the allowance can end the transfer before validation (then: no claims).
8. **Edge-removal predictions are structural** (no edge-level intervention exists in the simulator); only the silencing
   predictions are backed by simulations.
9. **Wall time on large graphs** is dominated by full-network simulations (intact runs, essentiality, screen, reliance, the
   cross-connectome step); the method runs in one process (the clean-room sandbox forbids subprocesses).

## 10. Cross-connectome decision

**The step is kept, but only as a verified, budgeted, calibrated add-on that never changes the core.** Evidence for joint
discovery (held-out pair tournament `sel_pairs_b1000`, 26 pairs x 2 seeds, 1,000 + 1,000 calls): for the strong base methods
there is no success gain (greedy_plus 0.98 → 1.00, group_probe and cem_search 1.00 → 1.00; greedy_reference 0.71 → 0.96), only an
efficiency gain (about 40 % fewer total calls: greedy_plus 174 → 104, group_probe 246 → 143, cem_search 184 → 115), and transfer
alone solves only ~0.70 of the pairs. Review E showed that this gain comes from a synthetic design in which the motif wiring is
identical in both networks, that the claimed correspondence confidence was a structural-alignment score (identity claims were
made across different implementations and under a destroyed correspondence), that "verified" transfers could be unvalidated, and
that role-graph similarity 1.00 is what joint's objective maximises, not evidence. On the real bundle, greedy_plus's MaleCNS core
transferred to MANC in 3 / 3 runs with 2 destination calls, the reverse direction in 2 / 3 (REAL_TRANSFER_greedy_plus.md). The
core therefore stays single-network (identical with and without a partner network, as in the reliability sweeps whose variant
bundles hold one network), and the cross-connectome step only adds claims, with these rules (review E findings 1, 2, 3, 6, 8, 9):

* **Partner.** The first network of the bundle from ANOTHER dataset (`problem.other_dataset_networks()`, loaded with
  `problem.load_network`); two networks of the same dataset (the same animal) are never paired.
* **Budget.** One pool per run: the step runs after the core is final and validated, from the calls left, with an allowance of
  min(left, 0.25 x declared budget, 60 x (|core| + 2)), and is skipped below 30 calls. Its simulator is spawned from the primary
  one (`sim.spawn`), so `sim.total_calls()` never exceeds the declared budget; its calls and simulated seconds are reported in
  `diagnostics["auxiliary_budget"]`, and exhaustion ends the step without claims.
* **Verification.** joint's verified transfer (structural image from anchor fingerprints plus reproduced signed member edges, then
  top-1, then the union of the top-k images; keep-only probes; minimisation that keeps full-network-essential members;
  counterparts of the core's essential members). It counts as verified only if (i) its validation passes on at least half of at
  least two fresh replicates, (ii) the minimisation completed (an incomplete one is a superset, not a mechanism), (iii) every core
  member essential in the primary network has an essential counterpart in the image, and (iv) the other network's intact
  simulation relies on the image (a member is essential there, or silencing the whole image breaks the function). (iii) and (iv)
  were added after my pair experiments (section 12.6): keep-only sufficiency alone accepts sufficient sets the other network does
  not use — a hub that can drive the readout alone, a silent structural copy, or, on a pair whose second network implements
  another family, some sufficient set near the image.
* **Identity claims** (`diagnostics["cross_connectome"]`, turned into schema claims): only for a verified transfer, only for member
  pairs the transfer matched (a member and a candidate image of it that survived in the verified set) that the structural alignment
  also pairs in both directions, and only when the fingerprint evidence ranks the partner above the 'none' option in BOTH
  directions (the 'none' logit is the typical best-match z of the other network's tokenised interneurons). Confidence = calibrated
  identity probability sigmoid(a + b · logit(w_ab · w_ba) + c · e): w_ab, w_ba are the two softmax weights of the pair (top-5
  candidates plus 'none'), their product (dual softmax) is high only when both directions agree, and e counts the signed member
  edges the pair reproduces — edges can raise the confidence only of a pair the fingerprints already support. (a, b, c) were fitted
  on my own synthetic pairs and checked on held-out pairs (section 12.6). Roles play no part in identity.
* **Role alignment** (`diagnostics["role_alignment"]`): the roles and signed role graphs of the core and of the other network's
  mechanism (the verified image, or v1's own discovery of the other network — with the transported prior unless the image was
  rejected on causal grounds — when the transfer does not
  verify) — a separate, role-level output, never an identity claim.
* **joint.py** (which this composition now owns) implements the same rules for `discover_pair`: `verified_transfer` accepts only
  a validated, completely minimised image with the source's essential structure that the destination relies on;
  `result_from_transfer` sets no `predicted_function_preserved` without validation; identity claims (`PairResult.correspondence`)
  are made only between two cores linked by a verified transfer (independent, prior and transfer modes claim nothing) and only for
  matched pairs; in the alternating rounds a network keeps its own validated mechanism unless its OWN evidence prefers the
  carried-over one — its own mechanism fails validation, the carried-over set is a strict subset, or its intact network relies
  decisively more on the carried-over set (silencing the distinctive members, per member, every replicate agreeing, margin
  max(0.05, 0.25 x the larger reliance)); a set that drops a member it found essential is never adopted, and role-graph similarity
  or correspondence confidence (agreement with the other network) are no longer evidence. Every switch is recorded in
  `diagnostics["switches"]`. `correspondence.null_match_scores` draws its null from tokenised interneurons only. The coordinator's
  smoke test (a NULL pair on which joint mode replaced network b's correct mechanism and independent mode claimed two identities)
  is covered by these rules and by `test_joint.py::test_null_pair_keeps_each_network_own_mechanism_and_claims_no_identity`.

## 11. Integrity and budget rules

* Every simulation of the primary network goes through the `BudgetedSimulator` the method is given; the other network of a bundle
  is simulated only through `sim.spawn(other, max_calls=allowance, kind="auxiliary")`, whose calls count against the same budget
  (`sim.total_calls()`; if the library offers no `spawn`, the cross-connectome step is skipped and says so). The method never
  constructs a simulator, never assigns a simulator attribute, never imports `brainir.sim.*` or `scipy.integrate`, never exceeds
  `sim.remaining` (each phase reserves the calls later phases need; `BudgetExhausted` cannot escape).
* Weight-noise probes always carry an explicit noise seed; `cfg_override` only widens the four parameter sds; `t_end` is the
  bundle's.
* Parameter seeds: every seed the method queries is below 5,000 (section 7; below 1,000 at seed 0, joint's seeds included); the tests
  check it for seeds 15 and 31, which use the highest seed block.
* The method reads no file itself: it uses the public problem (matrix, counts, signs, sizes, stimulus, readout, criterion, model
  configuration) and, for the cross-connectome step, the first network of ANOTHER dataset offered by
  `problem.other_dataset_networks()`, loaded with `problem.load_network(name)` (which refuses a network of the same dataset); that
  network's files are added to `inputs_used`. It never reads instance names, manifests or any truth, and imports no truth-bearing
  module (the static test of `test_budget_integrity.py` checks method modules, joint.py and correspondence.py). No component was
  tuned on any hidden instance; the development used my own instances only (section 12).

## 12. Experiments

All commands run inside `C:\Dev\BrainIR_p2clean` with `uv run --no-sync` (at most 3–4 of my processes at a time on a shared
machine; wall times are inflated by other users' jobs). Development scripts (not deliverables) live in `data/synthetic/dev_v1/`.

### 12.1 My development suite

`data/synthetic/dev_v1/build_suite.py` builds `brainir.discovery.synthetic.default_specs()` — the spec structure of the held-out
suites — with every background seed shifted by 13,000,000 (the salted suites use offsets below 1,000,000), verifies each instance
by simulation (up to 4 re-draws), exports two node orders (`main`, `order1`) and runs the truth-completeness audit
(`suite_audit`, unplanted sufficient sets):

```
uv run --no-sync python data/synthetic/dev_v1/build_suite.py --max-n 600 --workers 3      # 55 of 61 verified (47 small, 8 medium), 92 s
uv run --no-sync python data/synthetic/dev_v1/build_suite.py --min-n 2000 --workers 3     # 3 of 5 verified (n = 3,000), 171 s
```

58 instances (all ten families, four criterion types: rhythm, activity band, persistence, ramp, selectivity), 28 audited unplanted
sufficient sets. Runs: `data/synthetic/dev_v1/run_dev.py` (the frozen tournament scorer `brainir.discovery.tournament.run_one`,
score seeds 5000–5003 with the robust / weight-noise / minimality / causal-minimality checks), tables from `tables.py` and
`summarize.py` in the same directory, records in `data/synthetic/dev_v1/results/<label>.jsonl`.

### 12.2 Development history (what the experiments changed)

Rows: the first ~190 runs (the same ~31 instances x 2 orders x 3 seeds, budget 1,000) of each development version.

| version | change | runs | structural / planted | causal functional | identity Jaccard / identical | calls med | what went wrong |
|---|---|---|---|---|---|---|---|
| v1a | reliance before size (greedy_plus's order), reliance = fail + median readout peak change, 3 replicates | 194 | 0.99 / 0.97 | 1.00 | 0.98 / 0.94 | 72 | memory switch with hub distractors: a 2-hub pair beat the planted single neuron on reliance (silencing two driven hubs changes the readout more — a size confound); symmetric redundant pairs: 3-replicate reliance flipped the choice |
| v1b | reliance per distinctive member, generic readout-change statistic, 5 paired replicates | 180 | 1.00 / 1.00 | 1.00 | 0.97 / 0.93 | 64 | redundant pairs with weight jitter / a backup copy: reliance between equal-size pairs was "decisive" on 5 of 6 runs and not on the 6th (paired t 2.4–11) — the threshold sits inside the noise |
| v1c | Occam with a reliance exception: reliance only lets a larger set beat a smaller one; equal sizes are decided by robustness, else the canonical order | 189 | 1.00 / 1.00 | 1.00 | 0.98 / 0.97 | 72 | only the exactly automorphic redundant pair differs between node orders (identical within each order) |
| final | relevance on the structurally possible subgraph (sink-only distractors cannot reorder it); unvalidated candidates never win; seed layout < 5,000; sanctioned auxiliary simulator; pooled necessity test for essential claims and context members; stress margin 1.0 (with 0.75 an identical redundant pair switched on one run by stress-probe noise: 0/4 vs 3/4) | see 12.3 | | | | | |

The two reliance statistics that decided the design (per-seed paired differences, 5 working replicates): feed-forward driver with
hubs — the planted 3-neuron chain vs a sufficient hub: +0.060 to +0.074 per member, paired t −12 to −31 in all 6 runs (the chain
is kept, planted success); memory switch with hubs — hub pair vs the planted single neuron: +0.020 to +0.037 per member (t 6–17,
but below the 0.05 margin: Occam keeps the planted neuron); symmetric pairs: |t| mostly < 2 with occasional 4.5.

### 12.3 Final results on my mechanism suite

Final code: `brainir_v1.py` sha256 `3a07cf80…`, `joint.py` `38609d27…` (the core search has been unchanged since the stress-margin
fix; the later changes touch only the cross-connectome step, which these single-dataset instances never enter). Budget 1,000 calls;
scorer `tournament.run_one` with independent score seeds 5000–5003. Records: `data/synthetic/dev_v1/results/final5_{small,medium,large}.jsonl`.

| suite | runs (instances x orders x seeds) | structural success [CI] | planted | functional | causal functional | identity Jaccard / identical (instances) | calls med / mean | sim s med | wall s med | size med | nominal / robust / weight-noise pass | removable frac | role acc | essential acc | Brier |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| small (n = 50–60) | 282 (47 x 2 x 3) | 1.00 [1.00, 1.00] | 1.00 | 0.89 | 1.00 | 0.99 / 0.98 (47) | 76 / 90 | 75 | 4.0 | 2 | 1.00 / 0.94 / 0.87 | 0.11 | 0.88 | 1.00 | 0.0041 |
| medium (n = 500) | 48 (8 x 2 x 3) | 1.00 [1.00, 1.00] | 0.88 | 1.00 | 1.00 | 1.00 / 1.00 (8) | 130 / 144 | 125 | 16.6 | 2 | 1.00 / 0.89 / 0.88 | 0.00 | 0.86 | 1.00 | 0.0011 |
| large (n = 3,000) | 12 (3 x 2 x 2) | 1.00 [1.00, 1.00] | 1.00 | 1.00 | 1.00 | 1.00 / 1.00 (3) | 138 / 197 | 138 | 77.1 | 2 | 1.00 / 0.92 / 0.71 | 0.00 | 1.00 | 0.96 | 0.0006 |

By criterion type (small suite; the medium suite has activity band, persistence, ramp and rhythm with structural success 1.00 each):

| criterion | runs | structural | causal functional | identity Jaccard / identical | calls med | Brier |
|---|---|---|---|---|---|---|
| rhythm | 162 | 1.00 | 1.00 | 0.98 / 0.96 (27) | 106 | 0.0058 |
| activity band | 42 | 1.00 | 1.00 | 1.00 / 1.00 (7) | 63 | 0.0004 |
| persistence | 36 | 1.00 | 1.00 | 1.00 / 1.00 (6) | 50 | 0.0005 |
| selectivity | 30 | 1.00 | 1.00 | 1.00 / 1.00 (5) | 64 | 0.0062 |
| ramp | 12 | 1.00 | 1.00 | 1.00 / 1.00 (2) | 36 | 0.0001 |

By family (small suite; structural / causal functional / median calls / identical fraction): delayed inhibitory oscillator 1 / 1 /
105 / 1.0; E–I pair 1 / 1 / 62 / 1.0; feed-forward driver 1 / 1 / 76 / 1.0; integrator 1 / 1 / 36 / 1.0; memory switch 1 / 1 / 50 /
1.0; negative-feedback controller 1 / 1 / 57 / 1.0; redundant oscillator 1 / 1 / 114 / 0.83; ring oscillator 1 / 1 / 77 / 1.0; two
implementations 1 / 1 / 143 / 1.0; winner-take-all 1 / 1 / 64 / 1.0.

**Order / seed reliability.** Of the 58 instances, 57 give the identical core (in canonical node ids) in all 6 (small, medium) or 4
(large) runs over both node orders and all seeds. The exception is the exactly automorphic redundant oscillator
(`redundant_oscillator__n60__autonomous_module__s13000038`): `[3, 4]` in every run of one node order and `[1, 2]` in every run of the
other — failure mode 1; both are the planted mechanism's two interchangeable copies, and each run reports the other copy as a tied
alternative with shared probability. Functional success 0.89 on the small suite is the winner-take-all family by design: its context
members (lateral inhibitors) are keep-only removable, so keep-only 1-minimality fails while the causal (full-network) minimality holds
(causal functional 1.00). Adaptive replication extended 0.06 decisions per run on the small suite (7 of 282 runs), 1.6 on the
medium suite (4 of 48 runs) and 3–4 on the real networks. Mean calls per run by phase (small / medium): essentiality 18.7 / 19.6,
alternatives 18.2 / 46.9, elimination 16.4 / 34.9, fidelity 8.0 / 9.8, minimality 7.2 / 6.9, selection 6.8 / 8.4, screen 6.4 / 6.0,
reliance 2.0 / 3.7.

### 12.4 Low budgets

Small + medium suites, both node orders, seed 0 (`final5_b50`, `final5_b100`; 1,000 calls from 12.3). No run exceeded its budget.

| budget | runs | structural | planted | causal functional | identity Jaccard / identical (55 instances) | calls med / mean | wall s med |
|---|---|---|---|---|---|---|---|
| 50 | 110 | 0.99 | 0.96 | 0.95 | 0.97 / 0.95 | 50 / 49 | 2.6 |
| 100 | 110 | 0.99 | 0.96 | 1.00 | 0.98 / 0.98 | 64 / 69 | 3.7 |
| 1,000 | 330 (3 seeds) | 1.00 | 0.98 | 1.00 | 0.99 / 0.98 (seed 0 alone: 0.98 / 0.98) | 80 / 98 | 4.6 |

At 50 calls the medium suite drops to causal functional 0.81 and 0.75 identical cores (the minimality rounds and the alternatives do
not fit; the canonical elimination alone still recovers every structure, 1.00); at 100 calls it is back to 1.00 / 1.00. The single
structural failure at 50 and 100 calls is the memory switch with hub distractors in one node order: without the budget for the
alternatives the canonical set (a hub pair tied in relevance with the planted neuron) is returned; at 1,000 calls the enumeration
finds the planted neuron and Occam keeps it. For comparison, the selection suite's low-budget extension at 50 calls: group_probe
~0.95 causal / ~0.91 identical, greedy_plus ~0.96 / ~0.69, cem_search ~0.77 / ~0.65, surrogate_search ~0.32 / ~0.17.

### 12.5 Real bundle (clean room, oracle-free)

Run exactly as it will be locked, final code:

```
uv run --no-sync python benchmarks/dng100/cleanroom/run_method.py --method scripts/cleanroom_entry/brainir_discovery_entry.py \
    --bundle benchmarks/dng100/public_blind --out <dir> --network manc_v1.2.1 --seed 0 --method-args "--method brainir_v1 --budget 1000"
```

(plus `--result-json` into the output directory for the full diagnostics), then `data/synthetic/dev_v1/real_eval.py`: keep-only
fidelity of the predicted core on FRESH parameter seeds 5000–5007 (nominal, all parameter sds x2, weight noise 0.2), single-member
removal (1-minimality) and single silencing in the intact network — no answer involved. Three of my processes ran in parallel, so
wall times include contention; CPU seconds are the cleaner cost measure.

| | `manc_v1.2.1` | `male-cns_v1.0` |
|---|---|---|
| restriction (structurally excluded / silent in intact / candidates) | 1,066 / 3,306 / 87 | 1,318 / 2,739 / 121 |
| core (positions) | [1126, 1220, 2825, 2973] | [653, 1052, 2152] |
| essential (single silencing, pooled test) | 2825, 2973 | 653, 1052 |
| inclusion probability | 2825, 2973: 0.97; 1126, 1220: 0.90; 3310: 0.15 | 653, 1052: 0.97; 2152, 2948: 0.45 (tied); 2779, 3262, 3682, 4196: 0.15 |
| selection | canonical [2825, 2973, 3310] (validation 1.0, stress 1.0) replaced by [1126, 1220, 2825, 2973] (validation 1.0, stress 0.75): the intact network relies on {1126, 1220} 0.40 per member vs 0.03 on {3310}, every replicate agreeing | canonical kept; [653, 1052, 2948] tied (equal size, stress 4/4 both); a 6-member replacement is larger |
| primary calls / simulated s / CPU s | 226 / 452 / 354.5 | 232 / 464 / 338.7 |
| calls by phase | elimination 40, alternatives 84, screen 30, essentiality 27, minimality 12, selection 11 + reliance 7, fidelity 7, validation 3, seeds 3, restriction 2 | alternatives 96, elimination 42, essentiality 21, selection 18 + reliance 12, screen 16, fidelity 10, minimality 9, validation 3, seeds 3, restriction 2 |
| cross-connectome (same pool) | allowance 250; verified transfer to MaleCNS failed at the keep-only probes (6 calls); v1 on MaleCNS with the transported prior: [653, 1052, 2152] (134 calls); role alignment only: inhibitory feedback 1126 ↔ 2152, recurrent excitatory core {1220, 2825, 2973} ↔ {653, 1052}; no identity claim | allowance 250; transfer to MANC VERIFIED in 17 calls: image [2825, 2973, 3310] (validation 2/2, complete, essential structure and reliance hold); 1 identity claim 653 ↔ MANC 2825 (confidence 0.9997, 4 reproduced member edges); 1052 ↔ 2973 and 2152 ↔ 3310 not claimed (one direction below 'none') |
| total calls (primary + auxiliary) / simulated s | 366 / 732 | 249 / 498 |
| wall (method) | 571 s (discovery 357 s, cross step 214 s) | 366 s |
| oracle-free keep-only fidelity, fresh seeds 5000–5007: nominal / sd x2 / weight noise 0.2 | 1.00 / 0.625 / 0.50 (core 5.2–7.4 Hz; intact 8.1–11.5 Hz, intact pass 1.00) | 0.875 / 0.75 / 0.50 (core 15.2–18.9 Hz; intact 10.3–13.0 Hz, intact pass 1.00) |
| single silencing in the intact network, pass fraction (8 fresh seeds) | 1126 1.00, 1220 0.875, 2825 0.00, 2973 0.00 — matches the essential claims | 653 0.00, 1052 0.00, 2152 1.00 — matches |
| leave-one-out on fresh seeds (1-minimality) | every member necessary (0.00) | every member necessary (0.00) |

Both cores are sufficient on fresh replicates, 1-minimal, and their essential claims hold on 8 fresh replicates; their robustness to
weight noise is moderate (0.5). The MaleCNS core's verified image in MANC is v1's canonical MANC set [2825, 2973, 3310], which the MANC
run replaced by the set its intact network relies on more; this is reported, not resolved — nothing here judges which is correct.
Earlier development runs on MANC (before the pooled necessity test) returned [1220, 2825, 2973, 3310] with 1220 admitted as a context
member on two agreeing replicates; its single silencing then passed on 7 of 8 fresh replicates (0.875 above), which is why the pooled
test exists. v1 returns its core well within 1,000 calls on both 4,300–4,600-neuron networks, including the cross-connectome step.

### 12.6 Cross-connectome pairs (review E, coordinator smoke test)

Pairs: `data/synthetic/dev_v1/build_pairs.py` builds the harder review-E design of `synthetic_pairs.hard_pair_specs()` (blank
hemilineage, weaker and noisier anchors, homologous backgrounds, jittered and rewired motif wiring in b, structural decoys with
sign-consistent anchor decoys, NULL pairs whose b implements another family, implementation shifts) plus the easier v1 design of
`default_pair_specs()` (≤ 80 neurons), every seed shifted by 4,500,000 (dev), 4,600,000 (held out) or 4,700,000 (large), unverified
draws re-drawn: 50 dev pairs (26 plain, 5 decoy, 5 structural decoy, 8 null, 6 shift), 52 held-out pairs (26 / 6 / 6 / 8 / 6) and
2 large pairs (2,000 x 2,500 neurons; 2 of the 4 large specs verified). Truth: `pair_tournament.identity_truth` (identities and
homologs); on a null pair every identity claim is false, under a shift only the retained alternative's members correspond.

**What the experiments changed.** The first version of the reworked step (verified = validated on ≥ 2 fresh seeds + completely
minimised; identity eligibility = fingerprints beat 'none' both ways) made no false v1 claim on the dev pairs, but joint mode with
greedy_plus lost a network on 2 of 8 dev null pairs under destroyed cues and on 3 hub-distractor pairs (all feed-forward drivers):
the verified image was a keep-only-sufficient set the destination does not use (a single hub that can drive the readout alone; on a
null pair, a sufficient set near the image). Hence two causal checks in `verified_transfer` — every member essential in the source
has an essential counterpart in the image, and the destination's intact network relies on the image (a member, or else the whole
image, is necessary) — which fixed all five; after them the damped transported prior misled greedy_plus once (held-out structural
decoy), so the follower's discovery gets no prior when the image was rejected on these causal grounds. The coordinator's smoke
test (joint mode losing network b of a NULL pair; independent mode claiming two identities there) is covered by the adoption rule
(own evidence only), the claim rule (only between cores linked by a verified transfer) and a regression test. A tiny null pair of my
test suite (NFC → integrator, 30 x 36) produced one false claim at 0.73 from a verified but PARTIAL image (a 2-member core whose
image is b's own single-neuron mechanism), hence the last rule: claims only when the link pairs up all members of both cores one
to one (on the dev and held-out pairs every claimed link was already complete, so no correct claim was lost).

**Calibration.** The raw dual-softmax probability w_ab·w_ba is badly under-confident for claims (Brier 0.58–0.61; mean 0.27 while
the claims were ~99 % correct). (a, b, c) of sigmoid(a + b·logit(w_ab·w_ba) + c·edges) were fitted by penalised logistic regression
(ridge 0.5·|θ − (0, 1, 0)|², b ≥ 0 and c ≥ 0 so the confidence is monotone in the evidence) on the 90 claimable member pairs of the
DEV pairs — v1's claims plus joint.py's claims (greedy_plus base) in joint mode and with destroyed cues (`joint_null`), 89 correct —
giving **a = 1.2988, b = 0.2166, c = 1.8127** (a claim with no reproduced member edge and w_ab·w_ba = 0.3 gets 0.75, one edge 0.95).
Checked on the HELD-OUT pairs without refitting:

| population (final code, final calibration) | pairs | runs | verified transfers | claims | correct | false on null / shift / structural decoy | Brier (claims) | mean confidence | aux calls median |
|---|---|---|---|---|---|---|---|---|---|
| v1, dev pairs (network a, 1,000 calls) | 50 | 50 | 25 | 37 | 37 | 0 / 0 / 0 | 0.0012 | 0.976 | 16 (plain) – 106 (decoy) |
| v1, held-out pairs | 52 | 52 | 27 | 35 | 35 | 0 / 0 / 0 | 0.0015 | 0.970 | 12 (plain) – 84 (null) |
| joint.py (greedy_plus, 400 + 400), dev, joint + joint_null | 50 x 2 | 100 | — | 53 | 52 | 1 / 0 / 0 (null pair, cues destroyed) | 0.0171 | 0.973 | — |
| joint.py, held-out, joint + joint_null | 52 x 2 | 104 | — | 45 | 45 | 0 / 0 / 0 | 0.0013 | 0.974 | — |

v1's claims per pair type on the held-out pairs: plain 27 (19 of 26 transfers verified), decoy 6, shift 1 (the retained
alternative, correct), structural decoy 1, null 0 (no transfer verified on any of the 8 null pairs). Transfers not verified by v1:
5 of 52 held-out runs were rejected by the causal checks (3 "the intact network does not rely on the image", 2 "essential structure
not reproduced"), the rest failed the keep-only probes or validation. All claims fall in the reliability bin [0.8, 1.0] (observed
1.00 for v1 on both sets). Over every matched pair of a verified transfer (claimed or not) the calibrated probability is 0.963 vs
0.964 observed (held-out, v1; Brier 0.033). The single false claim of the whole study is a null pair with destroyed cues on which
greedy_plus's single-neuron memory-switch core and b's single-neuron integrator are the same wiring motif (a self-exciting neuron)
and the fingerprints beat 'none' by chance (w_ab·w_ba = 0.04, confidence 0.92).

**Joint discovery after the fixes** (greedy_plus, 400 + 400 calls, seed 0; independent = both networks alone):

| pairs | mode | both networks solved | total calls mean / median | identity claims (false) |
|---|---|---|---|---|
| dev (50) | independent | 1.00 | 210 / 188 | 0 |
| dev | joint | 1.00 | 173 / 139 | 47 (0) |
| dev | joint, cues destroyed | 1.00 | 212 / 200 | 6 (1) |
| held out (52) | independent | 0.96 | 208 / 186 | 0 |
| held out | joint | 0.96 | 187 / 166 | 42 (0) |
| held out | joint, cues destroyed | 0.96 | 214 / 196 | 3 (0) |

The two held-out failures are base-method failures in every mode (a memory switch with a backup copy, an NFC with a structural
decoy). Joint discovery keeps its efficiency gain where the correspondence is informative (−18 % mean calls on dev, −10 % held out)
and loses it — without losing a network — when the cues are destroyed; it no longer loses a network on null pairs (8 + 8 of 8 + 8
solved in every mode).

**Large pairs (n ≥ 2,000).** The two verified 2,000 x 2,500 pairs (autonomous module, hub distractor, misleading centrality,
structural decoy, homologous backgrounds, blank hemilineage): v1 on network a found the planted core in both (E–I pair [136, 848]
with 83 primary calls, 38 s; ring [151, 250, 393, 406] with 115 calls, 107 s). E–I pair: the transfer to the 2,500-neuron network
verified with 12 auxiliary calls and both member identities were claimed correctly (confidences 0.985, 0.998). Ring: the transfer
failed at the probes, v1's own discovery of b (113 calls) gave a role alignment, no claim; total 234 calls. joint.py with greedy_plus
(400 + 400) solved both networks of both pairs (E–I pair: joint 124 total calls vs independent 230, 2 correct claims; ring: joint
300 vs independent 238 — the transfer failed and b was discovered with the prior).

### 12.7 Tests and lint (final code)

```
uv run --no-sync ruff check src/brainir/methods/brainir_v1.py tests/test_method_brainir_v1.py        # All checks passed
uv run --no-sync pytest tests/test_budget_integrity.py tests/test_method_brainir_v1.py tests/test_discovery_infra.py -q
                                                              # 56 passed, 1 skipped (clean-room builder not in this checkout), 124 s
uv run --no-sync pytest tests/test_joint.py tests/test_discovery_cross.py tests/test_pairs_v2.py -q   # 21 passed, 71 s
uv run --no-sync pytest tests/test_method_brainir_v1.py -q                                           # 30 passed, 115 s
```

`test_method_brainir_v1.py` (30 tests, own synthetic instances only): registration and switches; recovery of an E–I pair with roles,
essential claims, intervention predictions and schema; determinism under the seed and independence of the node order; redundant
mechanisms reported with shared probability; a context member found by full-network necessity; activity-band and persistence
mechanisms; the budget is never exceeded (budgets 1, 4, 12, 30) and results stay valid; every switched-off configuration (14) runs
within budget with a valid result; the budget-integrity rules (static checks, seeds < 5,000 at seeds 15 and 31, seeded noise,
`cfg_override` whitelist); meaning-preserving perturbations (sink distractors, edge order) keep the core; the prior only orders the
search; the cross-connectome step shares the budget pool and claims only verified, matched, complete identities; no identity claim
across implementations under a shift; no identity claim on a null pair (verified but partial image); the run entry point. joint.py
changes are covered by `test_joint.py` (identity claims only with a verified link; a null pair keeps each network's own mechanism
and claims nothing — the coordinator's smoke-test case; the rescue case now adopts by the destination's own reliance evidence).
