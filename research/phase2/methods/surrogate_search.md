# `surrogate_search` — surrogate-assisted mechanism search

Method file: `src/brainir/methods/surrogate_search.py` (class `SurrogateSearch`, registered as `surrogate_search`, version 1.0).
Tests: `tests/test_method_surrogate_search.py`. Developer harness: `runs/surrogate_search/dev/` (own synthetic suite with truth,
tournament driver, smoke and profile scripts); clean-room entry point: `runs/surrogate_search/entry.py`.
Nothing in the method refers to a dataset, a cell type, an id, a mechanism size or a threshold tuned on hidden answers.

Note for integration: the shared `src/brainir/methods/__init__.py` was not modified (per the development contract);
`MethodRegistry.get("surrogate_search")` needs `import brainir.methods.surrogate_search` first (the entry script and the tests do
this). One import line in `brainir/methods/__init__.py` makes it available to `python -m brainir.discovery.run`.

## 0. Information used (integrity statement)

At run time the method reads only public problem fields: `C`, `signs`, `stim_positions`, `readout_mask` /
`readout_positions`, `candidate_positions()`, `criterion_spec`, `model_cfg` (for the widened-sd robustness check) and
`network_hash()` (cache keys). It uses the simulator only through the given `BudgetedSimulator`. It never reads
`problem.root`, network or instance names, manifest labels, sizes or the neuron table. Its constants were set on the developer's
own synthetic suite (`data/synthetic/dev_surrogate_search`, own truth) and did not change after any public-suite or real-bundle
run.

Disclosure: while surveying the clean directory at the start of development, the developer printed the first 80 lines of
`data/synthetic/mechanisms_v1/BUILD_REPORT.json`. That file was later identified as truth-bearing and has been deleted. The lines
shown were the suite counts (66 specs, 58 verified, 8 dropped) and the records of the first two or three E-I-pair instances:
intact pass, one alternative with keep-only pass 1.0, and canonical nodes 1 and 2 both essential and necessary, which is the E-I
pair motif as defined in the public generator `brainir.discovery.synthetic`. Nothing from it was used in the method, its
hyper-parameters or its tests. The public suite was run once, unscored (§7.3), and nothing was changed because of it.

## 1. Problem view

The simulator gives, for a kept subset `S` of the candidate pool, `pass(S; θ) ∈ {0, 1}` (keep-only of `S` + stimulus + readout
satisfies the criterion under parameter draw `θ`) at ~0.1–0.3 s, and `pass_silence(A; θ)` for silencing `A` in the full network
at ~2.4–4.7 s. The target is a compact set `M` such that keep-only of `M` passes across `θ`, every member is needed (leave-one-out
fails), members are marked essential when silencing them alone in the full network destroys the function, alternatives
(other sufficient sets) are reported with probabilities, and the whole thing is found within a hard call budget.

`pass(·)` over subsets behaves like a noisy monotone DNF with inhibitors: one or more "terms" (sufficient sets), plus nodes whose
presence can *break* a subset (inhibitors) — so the surrogate must represent conjunctions, disjunctions of conjunctions and
negative members, not just additive effects.

## 2. Algorithm

```
discover(problem, sim, seed, config):
  seeds       = [seed*1000 + i for i in range(replicates)]       # validation seeds; seeds[0] screens
  A. ACTIVITY SCREEN + POOL   (calls: n_intact + ~2)
     intact outcomes on seeds[:n_intact]  ->  active = union of active candidates (peak rate > active_rate in the window)
     order candidates: active first, then inactive, each by structural relevance (random-walk mass stimulus->node × node->readout)
     P = first min(|active|, pool_cap); keep_only(P) on 2 seeds; while it fails: P = all active, then double P along the
     order (inactive candidates) up to all candidates (= intact network)
  B. INITIAL DESIGN            (calls: n_init)
     n_init random "drop" subsets of P (drop fraction 0.15..0.65), screened on seeds[0]; passing ones smaller than the
     incumbent are validated on the other seeds; incumbent S* = smallest validated passing set
  C. SURROGATE-GUIDED SEARCH   (calls: until the reserve for D–G is reached, patience rounds without improvement, or |S*| = 1)
     each round: refit the surrogate ensemble on every (subset, seed) outcome so far (+ activity-reduced pseudo-labels)
                 propose ≤ batch subsets (Thompson-elimination ×2, Thompson from the pool every 3rd round, UCB-elimination,
                     EI over random drops ×2, intersection of passing sets, activity-reduced incumbent, random drops)
                 screen each on seeds[0]  (pre-registered surrogate predictions -> error tracker)
                 validate the passers smaller than S* on the remaining seeds; accept if pass fraction ≥ 0.5 (smallest wins)
                 adapt the random drop fraction toward a mixed pass/fail rate
  D. CLEANUP (minimality with evidence)
     chunked removal above one_by_one_below (least-needed half by surrogate necessity; halve the chunk on failure), then
     leave-one-out: screen S* \ {i} on seeds[0]; if it passes, validate; remove i only if the pass fraction stays ≥ 0.5
  E. ESSENTIALITY   silence({i}) in the FULL network on all seeds for every core member; essential = pass fraction < 0.5
  F. ALTERNATIVES   for every non-essential core member i: find a validated sufficient set without i (start from the smallest
     passing set without i, jump to the intersection of passing sets without i and to surrogate proposals, adaptive random
     chunk removal, leave-one-out), report it if validated and no larger than max(2|S*|, |S*|+3)
  F2. EXTRA ESSENTIAL SCREEN + RE-SELECTION   silence-test the most plausible non-core pool nodes (alternative members, then
     surrogate necessity / relevance); if an essential node lies outside S*, the core becomes the smallest validated
     sufficient set containing every essential node (an alternative, or S* ∪ essentials re-validated); the old core becomes an
     alternative
  G. ADD-BACK + FIDELITY   if the core's pass fraction < 1, re-add the most recently removed nodes (≤ 3) when that restores 1.0
     (role modulatory_supporting); widened-parameter robustness (sd × 2) on 2 seeds
  REPORT  core, inclusion probabilities, roles, essential, alternatives, loop, dynamics, fidelity, diagnostics
```

### 2.1 Pool (phase A)

A neuron whose peak rate stays below the criterion's `active_rate_hz` in the analysis window contributes nothing to the dynamics
(its output current is negligible against the threshold), so the union of active candidates over the intact seeds is a safe
hard filter. On the real 4,604-node network 92 of 4,459 candidates are active; on synthetic instances 3–362 (n ≤ 500) and
~1,450–1,510 (n = 3000). The structural relevance `sqrt(f · g)` (forward random-walk mass from the stimulus, backward mass from
the readout, 4 hops, damping 0.6, over synapse counts) only orders nodes; nothing is excluded by structure alone. The first pool is
the active set cut to `pool_cap` along that order. It is verified by keep-only simulation on 2 seeds. If it fails, it grows: to
the whole active set first, then by doubling through the inactive candidates up to all candidates. Keep-only of all candidates
is the intact network, so a passing pool always exists when the intact network passes. The growth covers non-monotone effects and
over-aggressive capping, which happens because the 4-hop relevance ranks loop members more than 4 hops from the stimulus low.
`pool_cap` therefore bounds the feature dimension only while the capped pool passes.

### 2.2 Surrogate (phase C)

Features of a subset `z ∈ {0,1}^K`: the `K` inclusion indicators plus 8 pool-level aggregates in [0, 1] — kept fraction, kept
stimulus drive, kept excitatory and inhibitory input to the readout, kept excitatory/inhibitory fraction, log kept recurrence
`zᵀQz` (symmetrised within-pool counts) and log kept E↔I loop weight. All single-node removals from a subset are evaluated
incrementally in O(|S|) (quadratic terms via `zᵀQz − 2(Qz)_i + Q_ii`), which is what makes greedy elimination cheap.

Model: an ensemble of `R` = 12 "noisy-OR of soft conjunctions" networks,

    P(pass | x) = 1 − Π_m (1 − σ(w_m · x + b_m)),   m = 1..M_r,  M_r = 1 + (r mod 3)

Each unit is a soft sufficient set (a monotone-DNF term; negative weights = inhibitors), the noisy-OR combines alternative
implementations; members with one unit are plain logistic regressions. Training: weighted cross-entropy (Poisson bootstrap
weights per member → epistemic spread), Adam (lr 0.05; 400 steps at the first fit, 120 warm-started steps per refit), L2 1e-3,
and an L1 proximal soft-threshold (0.01) on the indicator weights so a conjunction names few members instead of spreading weight
over the correlated indicators of random-drop designs. The gradient of the noisy-OR output is `c (q − y) s_m / q`, bounded and
stable. Pseudo-labels: a passing subset whose silent kept neurons are dropped is added with weight 0.5 (never reported as a
simulator result; every proposal built from it is simulated).

### 2.3 Acquisition (phase C)

- **Thompson elimination**: pick one ensemble member; from the incumbent, repeatedly remove the node whose removal keeps that
  member's P(pass) highest while it stays ≥ τ (τ = 0.5 and τ/2 for two proposals); every third round the same from the whole pool
  (explores other basins).
- **UCB elimination**: as above with mean + κ·std over the ensemble (κ = 1).
- **Expected improvement**: 200 random drop perturbations of the incumbent; EI = (mean + 0.5 std) × (|S*| − |S|); top 2.
- **Intersection** of all subsets that passed on any seed (exact for a single conjunction), **activity-reduced incumbent**, and
  random drops with an adaptive fraction (pushed toward a ~50 % screen pass rate).

Proposals are deduplicated against everything simulated; ≤ `batch` (3–8 by budget) per round.

### 2.4 Validation policy (anti-exploitation)

A subset can only become the incumbent, an alternative or the reported core after it passed on the screen seed **and** the
remaining validation seeds with pass fraction ≥ 0.5 (3 seeds by default: at least 2 of 3). Every removal in the cleanup is
validated the same way; essentiality uses all seeds; the final core is re-simulated on every seed and on a widened-parameter
ensemble. The surrogate's prediction for every screened/validated query is recorded *before* the simulation and scored after it:
Brier, log-loss, accuracy, optimism (mean predicted − mean actual), calibration bins and per-proposal-type breakdown appear in
`diagnostics.surrogate`, together with the out-of-bag Brier of the ensemble and the training loss. Inclusion probabilities of
non-core nodes derived from the surrogate are shrunk by `1 − Brier/Brier(base rate)`.

### 2.5 Output

- `core`: the final validated set; `inclusion_probability`: 0.95 for essential members, 0.9 for members needed within the core,
  0.6 otherwise, capped at 0.75 when a validated alternative without the member exists, 0.5 for add-back members; 0.3–0.5 for
  members of validated alternatives; 0.02–0.35 for other pool nodes (shrunk surrogate necessity); 0.01 for silent candidates.
  Surrogate numbers never enter the probabilities of the core or of alternative members: those come only from simulated evidence
  (validated sufficiency, leave-one-out, silencing).
- `roles` (from `GENERIC_ROLES`): sign + core-induced graph (strongly connected components, self-loops, stimulus input, readout
  drive, relay pattern) + criterion type: e.g. rhythm: E on a cycle → `recurrent_excitatory_core` (pure pass-through E →
  `input_relay`), I on a cycle → `inhibitory_feedback`; activity band: E driving the readout → `output_driver`, I → `gain_control`;
  persistence/ramp: self-exciting E → `state_memory`; selectivity: I → `lateral_inhibition`; alternative-only members →
  `redundant_backup`; add-backs → `modulatory_supporting`; unknown sign → `unknown`.
- `essential`: simulated (full-network silencing) for every core member, `None` when the budget ran out.
- `alternatives`: validated sufficient sets other than the core (most probable first); `loop`: core members on a cycle.
- `predicted_frequency_hz` / `n_active_readout`: median over the passing intact-network runs (the prediction for the benchmark
  stimulus); `fidelity`: keep-only pass fraction / score / frequency of the core, widened-sd pass fraction.

### 2.6 Optional prior (cross-network transfer convention)

`config["prior"]`, when present, is a dict `{position: prior inclusion probability in [0, 1]}` (int or string keys; missing
positions count as 0.5; absent or empty = uniform = no effect). It is never required and it can only *bias*, never decide:

- pool ordering: candidates are ordered by prior first, then structural relevance (matters for capping/expansion only);
- initial design: the per-node drop probability in the random drop designs is scaled by `1 − strength·(prior − 0.5)`
  (renormalised so the expected drop fraction is unchanged), so high-prior nodes stay in the early subsets;
- surrogate: the indicator weights are initialised at `0.5·strength·(logit(prior) − mean logit)`, a starting point that the
  data and the L1 penalty overwrite as evidence accrues;
- cleanup / exclusion search: tie-break of the least-needed order (low prior removed first); extra essential screen: tie-break of
  the candidate order (high prior screened first);
- inclusion probabilities of non-core pool nodes: the surrogate-derived part is scaled by `1 + strength·(prior − 0.5)` (never the
  validated core/alternative probabilities, which come from simulation).

`prior_strength` (default 1.0; 0 disables) scales all of the above. On a 60-node delayed-inhibitory-oscillator instance
(`runs/surrogate_search/dev/prior_check.py`, budget 600, seed 0): no prior → 110 calls (54 in the search); a helpful prior
(0.9 on the true core, 0.1 elsewhere) → 98 calls (38 in the search), same core; a misleading prior (0.05 on the true core, 0.95 on
a distractor) → 98 calls, same correct core. `diagnostics["prior"]` records the number of entries, how many fall in the pool and the
strength (`None` when no prior was given).

## 3. Hyper-parameters (`default_config`)

| name | default | meaning |
|---|---|---|
| replicates | 3 | validation seeds (`seed*1000+i`); screening uses the first |
| n_intact | 3 | intact seeds for the activity screen |
| pool_cap | 600 | first-attempt pool size (feature dimension); exceeded only when the capped pool fails its keep-only check |
| batch | None → 3..8 (budget/120) | proposals per search round |
| n_init | 8 | random drop designs before the first fit |
| ensemble_size / n_units | 12 / 3 | ensemble members / max conjunction units per member |
| fit_steps / refit_steps | 400 / 120 | Adam steps (first fit / warm refits) |
| l2 / l1 / lr | 1e-3 / 0.01 / 0.05 | regularisation and learning rate |
| tau | 0.5 | elimination continues while the acquisition value ≥ tau |
| kappa | 1.0 | UCB exploration weight |
| patience | 10 | rounds without improvement before the cleanup |
| pseudo_weight | 0.5 | weight of activity-reduced pseudo-labels |
| one_by_one_below | 12 | cleanup: chunked removal above, leave-one-out at or below |
| max_alt_calls | 30 (+2·start size) | exclusion-search calls per member (bounded by the remaining budget minus the later phases) |
| alt_members_max | 6 | members that get an exclusion search |
| extra_essential_max | 8 | non-core pool nodes screened by full-network silencing |
| robust_check | True | widened-sd fidelity of the final core (2 calls) |
| t_end | None | optional shorter horizon for every simulation |
| prior / prior_strength | None / 1.0 | optional {position: p} prior (section 2.6); absent = uniform |

Nothing is tuned per instance; the same defaults are used for 50-node synthetic instances and the 4,604-node real network.

## 4. Budget use and stopping rule

Calls: intact `n_intact` + pool check 2 (+ doublings) + design `n_init` (+ validations) + search rounds (`batch` screens +
validations of improving passers) + cleanup (≈ 1 call per needed member, 3 per removable member) + essentiality
(`replicates` × |core|) + alternatives (≤ cap per non-essential member) + extra essential screen (`replicates` ×
`extra_essential_max`) + fidelity (≤ 5). The search reserves `cleanup + essentiality + alternatives + extra screen + 3` calls (the
`_reserve()` estimate, recomputed from the incumbent's size) and stops when the next batch would eat into it, when `patience`
rounds brought no smaller validated incumbent, when the incumbent has one member, or when no untested proposal exists. Every
phase trims its batches to `sim.remaining` (cache hits are free and are not counted); `BudgetExhausted` is caught and the best
validated evidence so far is reported. Any budget yields a schema-valid result (tested at 5, 12 and 40 calls; the core may be
empty or incomplete when the budget ends before a validated sufficient set exists).

The method stops by itself long before large budgets are exhausted on small pools: on the 56 small developer instances it used a
median of 74 calls whether the budget was 1000 or 2000 (the extra budget is simply not needed once the incumbent cannot shrink and
the evidence phases are done). The budget matters for large pools (exclusion searches, more search rounds).

Wall time is dominated by the simulator: on a 60-node instance 52.5 of 53.5 s were simulations (profile in
`runs/surrogate_search/dev/profile_run.py`); the surrogate fits and the acquisition cost < 1 s per run (K ≤ 600 features,
≤ 2,000 rows). Measured simulator costs on the real 4,604-node network: intact / single-silencing 4.7 s, keep-only of a quiet
random subset 0.23–0.28 s (`runs/surrogate_search/dev/timing_probe.py`), but keep-only of an *oscillating* subset costs about as
much as an intact run, because the solver integrates the full 4,604-dimensional state with many adaptive steps. Since most
validation queries are of passing (oscillating) subsets, the real-bundle run averaged ~6 s of simulation per call (1,144 s for 192
calls, with other jobs running concurrently); the "keep-only ≈ 0.1 s" cost model holds only for failing subsets.

## 5. Complexity

Surrogate fit: O(steps · n · F · R · M) with n ≤ budget rows, F = K + 8, R·M ≤ 36 — milliseconds to a second. Greedy elimination:
O(|S|² · R' · M) per proposal with the incremental features (|S| ≤ K). Relevance: 4 sparse mat-vecs. Memory: two dense K×K
matrices (K ≤ 600). Simulator calls: ≤ budget, by construction.

## 6. Failure modes (known)

- **Sufficient in isolation ≠ mechanism in context.** A strongly driven hub projecting onto the readout can satisfy an
  activity-band criterion under keep-only on its own. It is then a genuine minimal sufficient set, but not the planted one: the
  feed-forward hub instance returned the 1-node core {41} (nominal 1.0). Phase F2 repairs the case where an essential node
  (full-network silencing) is missing from the core, at `replicates × extra_essential_max` full-network calls; that is what makes
  the winner-take-all cores include their inhibitory interneuron. Nodes that are neither in the smallest sufficient set nor
  individually essential stay outside the core by design. Nothing in the method prefers planted-looking structure.
- **Very large active sets.** When the capped pool fails, the pool grows to the whole active set (1,508 nodes in §7.4) or
  further. Surrogate features, two dense K×K matrices (~0.3 GB at K = 4,459) and the search then cost more; the n = 3000
  delayed-oscillator run needed 255 search calls to shrink 1,508 → 5.
- **Surrogate misspecification far from the data.** Predictions for regions never sampled (e.g. large subsets excluding the
  incumbent) can be badly optimistic (`optimism` up to +0.4 was observed on a 308-node pool); nothing is reported from the
  surrogate without simulation, and the error record makes the misspecification visible.
- **Alternatives buried in large pools.** The exclusion search is an adaptive splitting descent; from a 150-node start with a
  4-member hidden alternative it needs ~30–60 calls; with small budgets alternatives may go unreported (the `no_alternative_in_pool`
  and `checked_members` diagnostics say what was tried).
- **Screen-seed bias.** Sets that fail on the screening seed but pass on the others are never validated; sets accepted with
  2 of 3 seeds may score 0.5 on fresh seeds. The add-back step only repairs cores whose pass fraction is < 1.
- **Activity filter.** A mechanism member active only before the analysis window (a transient kick-starter) would be excluded from
  the pool; the pool check would then fail and the pool would expand along the relevance order, which is a weaker guarantee.
- **Non-monotone removals.** A node whose removal *creates* the function is handled (negative weights, validated proposals), but
  the leave-one-out cleanup is 1-minimal, not cardinality-minimal.
- **Local optimum at a small wrong set.** Search proposals are mostly subsets of the incumbent; once a 2-node set that is
  sufficient but not the planted mechanism is the incumbent, a 1-node mechanism outside it is only reachable through the
  pool-level Thompson proposals (every third round) and the exclusion search. Observed once: memory switch with hub distractors
  (seed 1, order variant 1), where the core was {0, 2} and the alternatives were {2, 4} and {0, 4, 53}.
- **Equal-size implementations are tied arbitrarily.** When two validated sufficient sets of the same size exist, for example a
  set using a weaker duplicate neuron and the set using the original, `_update_best` breaks the tie by validation pass fraction
  (both 3/3), number of seeds, mean score and finally subset order. The other set is still reported as an alternative.
  Observed twice: feed-forward driver with a backup copy (seed 1, order 1), core {1, 27, 34} with alternative {1, 30, 34}; and
  the n = 3000 delayed oscillator (§7.4), where the chosen core passed only 0.75 on fresh seeds (robust 0.5). A generic fix
  based on simulator evidence only, not implemented for lack of time: break equal-size ties by robustness, i.e. the pass
  fraction under widened parameter sds and weight noise, at 2–4 extra keep-only calls per tied set, and report the less
  robust set as the alternative.
- **Surrogate skill is modest at small budgets.** With the budget-250 batch size (3 proposals per round), the pooled
  pre-registered Brier score equalled the base-rate Brier score (0.215 vs 0.215), so at that budget the surrogate predicted pass/fail
  no better than a constant. Success was unchanged (55/56) because the validated elimination, the intersection and activity-reduced
  proposals and the cleanup do the work. At budget 1000 the surrogate is informative (Brier 0.125 vs 0.180).

## 7. Synthetic experiments

All commands run inside `C:\Dev\BrainIR_p2clean` with `uv run --no-sync`. The developer suite (own truth, seeds 7,200,000+, all ten
families; 66 of 74 specs verified by simulation in 395 s: 56 small instances with n = 50/60, every complication; 7 with n = 500
(hub distractors, misleading centrality, autonomous module); 3 with n = 3000 (plus backup copy). The negative-feedback,
integrator and winner-take-all specs that failed verification were dropped) was built with

    uv run --no-sync python runs/surrogate_search/dev/build_dev_suite.py --workers 4

and the tournaments with `runs/surrogate_search/dev/run_dev.py` (which imports the method in every worker and uses the shared
scorer `brainir.discovery.tournament.run_one` with fresh seeds 5000–5003 and the robust/weight-noise/minimality checks). Results
are in `runs/surrogate_search/results/<label>.{json,md}`.

Code revisions. "final" = the code in this commit. One last fix, pool growth past `pool_cap` (§2.1), was made after the final
small-suite, n = 500, public-suite and real-bundle runs. It changes behaviour only when the first pool check fails, which
happened in none of those runs (each passed its first check, verified from the stored diagnostics), so their numbers hold for the
final code. The n = 3000 runs and the tests were repeated after the fix. "Rev A" = the previous revision. The only differences
from rev A are in the
exclusion search (`_minimize_excluding`: 3 attempts per chunk size, cap 30 + 2·start instead of 30 + 8·log2(start/8),
leave-one-out and validation only for sets ≤ 3·`one_by_one_below`), a clip bound of the non-core inclusion probability, and
the optional prior, which is inactive without `config["prior"]`. On the same 56 small instances at budget 1000 both revisions
give identical success, precision, functional, essentiality, role and Brier numbers. Runs of rev A were not repeated with the
final code where noted, because a machine-wide low-memory monitor killed them and time was limited.

### 7.1 Small developer instances (56 instances, n = 50/60, all ten families, every complication)

    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search --budget 1000 --max-n 60 --workers 2 --label final_small_b1000
    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search greedy_reference --budget 1000 --max-n 60 --workers 5 --label dev_small_b1000
    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search greedy_reference --budget 250 --max-n 60 --workers 4 --label dev_small_b250
    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search --budget 2000 --max-n 60 --workers 2 --label dev_small_b2000
    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search --budget 1000 --max-n 60 --seeds 1 --networks order1 --workers 3 --label dev_small_b1000_seed1_order1
    uv run --no-sync python runs/surrogate_search/dev/summarize_results.py <label> ...      # the aggregates below
    uv run --no-sync python runs/surrogate_search/dev/acquisition_stats.py <label>          # per-acquisition statistics

Scores come from the shared scorer (fresh seeds 5000–5003). Success means some sufficient alternative of the truth is fully
recovered. Functional values are keep-only pass fractions of the reported core on the true simulator: nominal, parameter sds × 2,
weight noise 0.2. "Removable" is the share of runs whose core has a member that can be dropped while the function is kept.

| label (code) | method | budget | seed / network | success | precision (median) | nominal / robust / weight-noise | calls median (max) | essential acc (claims) | role acc | inclusion Brier | removable |
|---|---|---|---|---|---|---|---|---|---|---|---|
| final_small_b1000 (final) | surrogate_search | 1000 | 0 / main | **0.982 (55/56)** | 1.00 | 1.000 / 0.933 / 0.862 | 74 (138) | 0.995 (134) | 0.964 | 0.0066 | 0.089 |
| dev_small_b1000 (rev A) | surrogate_search | 1000 | 0 / main | 0.982 (55/56) | 1.00 | 1.000 / 0.933 / 0.862 | 74 (138) | 0.995 (134) | 0.964 | 0.0066 | 0.089 |
| dev_small_b1000 | greedy_reference | 1000 | 0 / main | 0.679 (38/56) | 0.33 | 0.804 / 0.759 / 0.714 | 178 (547) | 1.000 (113) | – | 0.2500 | 0.625 |
| dev_small_b250 (rev A) | surrogate_search | 250 | 0 / main | 0.982 (55/56) | 1.00 | 1.000 / 0.933 / 0.862 | 66 (146) | 0.995 (134) | 0.964 | 0.0066 | 0.089 |
| dev_small_b250 | greedy_reference | 250 | 0 / main | 0.589 (33/56) | 0.33 | 0.714 / 0.670 / 0.621 | 178 (250) | 1.000 (85) | – | 0.2570 | 0.607 |
| dev_small_b2000 (rev A) | surrogate_search | 2000 | 0 / main | 0.982 (55/56) | 1.00 | 1.000 / 0.933 / 0.862 | 74 (138) | 0.995 (134) | 0.964 | 0.0066 | 0.089 |
| dev_small_b1000_seed1_order1 (rev A) | surrogate_search | 1000 | 1 / order1 | 0.946 (53/56) | 1.00 | 1.000 / 0.933 / 0.866 | 76 (167) | 1.000 (132) | 0.944 | 0.0077 | 0.107 |

Success rate / median calls by family (final_small_b1000 vs greedy_reference in dev_small_b1000, n instances per family):

| family (n) | surrogate_search | greedy_reference |
|---|---|---|
| delayed_inhibitory_oscillator (6) | 1.00 / 109 | 0.00 / 34 |
| ei_pair_oscillator (6) | 1.00 / 70 | 1.00 / 291 |
| feedforward_driver (6) | 0.83 / 88 | 0.00 / 60 |
| integrator (5) | 1.00 / 66 | 1.00 / 178 |
| memory_switch (6) | 1.00 / 63 | 1.00 / 142 |
| negative_feedback_controller (4) | 1.00 / 64 | 0.75 / 96 |
| redundant_oscillator (6) | 1.00 / 82 | 1.00 / 206 |
| ring_oscillator (6) | 1.00 / 92 | 1.00 / 208 |
| two_implementations (6) | 1.00 / 97 | 1.00 / 252 |
| winner_take_all (5) | 1.00 / 64 | 0.00 / 206 |

The greedy reference runs with its frozen default k = 3. It fails wherever the mechanism does not have 3 members (1-node
integrator and switch cores give precision 0.33; 5-node delayed oscillators and 2-node winner-take-all cores are cut or padded).
`surrogate_search` has no size parameter.

Failures:

- final and rev A, seed 0: `feedforward_driver__n60__hub_distractor+misleading_centrality`. The core is {41}, a hub distractor
  whose own drive puts the readout into the activity band. It is functionally valid (nominal 1.0) and not the planted chain.
  The alternative {29} is another hub. Silencing no single node breaks the intact function, so the essentiality screen cannot
  repair it (failure mode "sufficient in isolation").
- rev A, seed 1 / order 1: the same instance, plus the backup-copy tie and the memory-switch local optimum described in §6.

Stability, rev A (`dev_small_b1000` vs `dev_small_b1000_seed1_order1`, mapped through the order permutation): the reported cores
are the same neurons in 52/56 instances, and both runs succeed in 53/56.

Surrogate error, pre-registered prediction before every screened or validated simulation, pooled over runs with ≥ 10 scored
predictions:

| label | runs | Brier | base-rate Brier | accuracy | optimism | predictions / run (median) |
|---|---|---|---|---|---|---|
| final_small_b1000 | 48 | 0.126 | 0.181 | 0.820 | +0.067 | 28 |
| dev_small_b250 (rev A) | 34 | 0.215 | 0.215 | 0.685 | −0.001 | 26 |
| dev_small_b1000_seed1_order1 (rev A) | 49 | 0.132 | 0.192 | 0.806 | +0.086 | 26 |

By acquisition type (final_small_b1000, pooled; search screen pass rate and the surrogate's Brier on those queries):
active-reduce 34 proposals, pass 1.00 (Brier 0.005); intersection 51, 0.84 (0.069); random drop 396, 0.29 (0.130);
Thompson elimination 191, 0.21 (0.179); EI 125, 0.26 (0.365, the most optimistic: mean prediction 0.69 vs pass rate 0.26);
UCB 44, 0.11 (0.163); pool-level Thompson 24, 0.17 (0.199). Validation queries (520, all of screen-passing sets) have Brier
0.046. The activity-reduced incumbent and the intersection of passing sets have the highest screen pass rates, 1.00 and 0.84.
The attribution of each accepted improvement to a proposal type is not recorded.

Other facts from final_small_b1000:

- **Cleanup.** It removed nothing in 56/56 runs: every leave-one-out test confirmed each member on the screen seed, so the
  search had already stopped at a 1-minimal set.
- **Stop reasons.** "No untested proposals" in 39 runs, "incumbent has one member" in 17.
- **Calls per phase (median).** Intact 3, pool 2, design 16, search 19.5, cleanup 0, essentiality 6, alternatives 0, extra
  essential screen 24, fidelity 2. The full-network screen of non-core nodes is the largest single cost.
- **Re-selection.** The essential-node re-selection (F2) changed the core in 5 runs, all winner-take-all. The search's
  keep-only minimum was the output pool alone; silencing its inhibitory interneuron in the intact network breaks selectivity,
  so the interneuron was added, giving the planted core. The same 5 runs are the ones the scorer flags as having a
  keep-only-removable member (the "removable" column: 0.089 = 5/56). This member is necessary in context, not in isolation.

Calibration of the inclusion probabilities against the developer truth (`runs/surrogate_search/dev/calibration.py
final_small_b1000`; 2,532 (run, candidate) pairs; target = membership in the truth alternative that best matches the core, and
in parentheses membership in any planted sufficient implementation):

| reported p | n | mean p | member of best-matching alternative | member of any alternative |
|---|---|---|---|---|
| [0, 0.05) | 2352 | 0.013 | 0.001 | 0.001 |
| [0.05, 0.3) | 3 | 0.077 | 0.000 | 0.000 |
| [0.3, 0.55) (members of validated alternatives only) | 42 | 0.500 | 0.000 | 0.857 |
| [0.55, 0.8) (core members with a validated alternative lacking them) | 35 | 0.741 | 0.971 | 0.971 |
| [0.92, 1] (core members that are essential or needed) | 100 | 0.950 | 1.000 | 1.000 |

The core probabilities are slightly under-confident, and the low end is calibrated. The 0.5 given to members of other validated
implementations is deliberate: they are equally well supported, since sufficiency is validated on the same seeds. The
tournament's single-alternative Brier counts them as non-members, and they account for ~0.004 of the 0.0066 total. The
seed-1 / order-1 run gives the same picture (Brier 0.0078).

### 7.2 Optional prior (`runs/surrogate_search/dev/prior_check.py`, final code)

See §2.6: on one 60-node delayed-inhibitory-oscillator instance, with budget 600, no prior, a helpful prior and a misleading
prior all return the correct 5-node core (110 / 98 / 98 calls). The prior only moves proposals, as intended. The test
`test_prior_is_optional_and_only_biases` checks this on an activity-band instance (misleading prior, helpful prior with string
keys, empty prior).

### 7.3 Public evaluation instances, unscored (truth withheld; rev A)

    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search --suite data/synthetic/mechanisms_v1 --budget 1000 --max-n 60 --workers 3 --label public_small_b1000

This covered 48 public instances with n ≤ 60. There were 0 errors and 0 empty cores; calls median 76 (max 177), wall median
21 s. The method's own keep-only pass fraction of the core averaged 0.993 over 3 seeds, and the widened-sd pass fraction 0.938.
Alternatives were reported in 19/48 runs. Core sizes per family: delayed-inhibitory 5 (6×); E-I pair 2 (6×); feed-forward
3, 1, 3; integrator 1 (3×); memory switch 1 (6×); negative feedback 2 (4×); redundant 2 (6×); ring 4 (3×);
two-implementations 2 (6×); winner-take-all 2, 2, 2, 4, 3. These are the method's own outputs; no scores are available here.

### 7.4 Medium and large developer instances (final code)

    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search --budget 1000 --min-n 500 --max-n 500 --workers 2 --label final_n500_b1000
    uv run --no-sync python runs/surrogate_search/dev/run_dev.py --methods surrogate_search --budget 1000 --min-n 3000 --workers 2 --label final_n3000_b1000

n = 500 (7 instances, 20 readout neurons, hub distractors + misleading centrality + an autonomous oscillator module; 145 s wall
with 2 workers): **success 7/7**, precision 1.00, nominal / robust / weight-noise 1.000 / 0.964 / 0.714, calls median 149
(max 225), essential accuracy 1.000 (19 claims), role accuracy 0.857, inclusion Brier 0.0010, no removable member. Pools had
276–362 active candidates. Both alternative implementations were reported where they exist: the second E-I pair of the
redundant oscillator and the 4-node ring of two-implementations (62 calls of exclusion search from a 322-node pool). The
feed-forward driver additionally got a 1-node alternative {301}, a hub that drives the readout into the band on its own.

| instance (n = 500) | core = planted | calls | pool | search / alternatives / extra-screen calls | surrogate Brier (base rate) |
|---|---|---|---|---|---|
| delayed_inhibitory_oscillator | 5/5 | 195 | 276 | 138 / 0 / 24 | 0.201 (0.250) |
| ei_pair_oscillator | 2/2 | 125 | 288 | 74 / 0 / 24 | 0.162 (0.228) |
| feedforward_driver | 3/3 | 149 | 340 | 69 / 18 / 24 | 0.282 (0.250) |
| memory_switch | 1/1 | 76 | 362 | 22 / 0 / 24 | 0.192 (0.043) |
| redundant_oscillator | 2/2 (+ other pair as alternative) | 109 | 315 | 47 / 9 / 24 | 0.220 (0.218) |
| ring_oscillator | 4/4 | 225 | 322 | 172 / 0 / 24 | 0.148 (0.243) |
| two_implementations | 2/2 (+ ring as alternative) | 191 | 322 | 78 / 62 / 24 | 0.319 (0.249) |

Pooled over these runs the surrogate's pre-registered Brier is 0.218 against 0.212 for the base rate, so it has no net
predictive skill at this size. It helps on the oscillators with long searches (ring, E-I pair, delayed) and is worse than a
constant where passes are rare (memory switch). All reported sets are simulator-validated, so this does not reach the output,
but it means the surrogate is not the component that makes the method work at n = 500.

n = 3000 (3 instances, 40 readout neurons, hubs + misleading centrality + backup copy + autonomous module; 1,443–1,508 active
candidates, so the first pool is capped at 600). Final code: 399 s wall with 2 workers. **Success 2/3**, precision 1.00, nominal
/ robust / weight-noise 0.917 / 0.750 / 0.750, calls median 224 (max 412), essential accuracy 1.000 (8 claims), inclusion Brier
0.0004, surrogate Brier 0.219 vs base rate 0.237.

| instance (n = 3000) | pool (checks) | core vs planted | alternatives | calls | nominal / robust |
|---|---|---|---|---|---|
| ei_pair_oscillator | 600 (pass) | 2/2 exact, both essential | – | 150 | 1.00 / 1.00 |
| two_implementations | 600 (pass) | E-I pair exact | the planted 4-node ring, exact | 224 | 1.00 / 0.75 |
| delayed_inhibitory_oscillator | 600 (fail) → 1,508 (pass) | 4/5 + node 258 | the planted 5-node set, exact | 412 | 0.75 / 0.50 |

For the delayed oscillator the core {258, 986, 1527, 2033, 2240} and the planted set {986, 1527, 2033, 2240, 2551} are
equal-size validated sufficient sets. The chosen core is the less robust one: it passes 0.75 on the scorer's fresh seeds and 0.5
with widened sds. The planted set passed the generator's verification (≥ 0.8 of 6 seeds); its fresh-seed rate was not
measured here. 258 is presumably the backup copy of 2551 (not checked). Its essentiality claims are correct: 258 is not
essential, the other four are. The run is scored a failure because the planted set is only an alternative (§6, equal-size
ties).

Before the pool-growth fix the same instance returned an **empty core after 5 of 1,000 calls**
(`runs/surrogate_search/results/prefix_n3000_b1000.*`). The 600-node capped pool failed its keep-only check and the old loop
stopped at the cap. This was the reason for the fix. The other two instances are identical before and after it.

### 7.5 Real public bundle, tier A (`benchmarks/dng100/public_blind`, network `manc_v1.2.1`, budget 1000)

    uv run --no-sync python benchmarks/dng100/cleanroom/run_method.py --method runs/surrogate_search/entry.py \
        --bundle benchmarks/dng100/public_blind --out runs/surrogate_search/cleanroom_manc_final --network manc_v1.2.1 --seed 0 \
        --method-args "--budget 1000 --result-json <abs path>/runs/surrogate_search/cleanroom_manc_final/result_manc_v1.2.1.json"

This ran under the clean-room runner with the audit-hook sandbox (bundle `efc33d77…`, exit code 0, prediction sha256
`723dc920…`, 400.5 s wall). The method knew nothing about the circuit, and nothing below is compared with any answer.

- **Inputs used.** 4,604 neurons, 4,459 candidates. 92 candidates are active in the intact network (3 seeds, pass 3/3), and
  keep-only of these 92 passes 2/2, so the pool is 92.
- **Search.** Incumbent sizes over the rounds: 61 → 44 → 27 → 14 → 6 → 3; stopped with no untested proposals.
- **Core.** {499, 2825, 2973} (positions in the tier-A bundle): 2 excitatory neurons plus 1 inhibitory, all on one recurrent
  loop. The generic roles are recurrent_excitatory_core ×2 and inhibitory_feedback. Every member is needed within the core
  (leave-one-out fails).
- **Essentiality (full-network silencing, 3 seeds).** 2825 and 2973 are essential; 499 is not.
- **Alternatives.** The exclusion search without 499 found a validated alternative, {1126, 1220, 2825, 2973}, where two other
  neurons replace the non-essential inhibitory member. Inclusion probabilities: 2825 and 2973 0.95, 499 0.75, 1126 and 1220
  0.5. The screen of 8 non-core pool neurons found no other essential neuron.
- **Fidelity.** Keep-only of the core passes 3/3 seeds (score 0.994) and 2/2 with parameter sds × 2. The core in isolation
  oscillates at 16.4 Hz, while the intact network oscillates at 11.0 Hz with 2 of 144 readout neurons active. The prediction
  carries the intact values (frequency 10.99 Hz, 2 active readout neurons, rhythmic). So the isolated core is sufficient for the
  rhythm, but the rest of the network sets its frequency.
- **Calls.** 182 of 1,000: intact 3, pool 2, design 12, search 79, cleanup 0, essentiality 9, alternatives 51, extra screen 24,
  fidelity 2.
- **Surrogate on this run.** 130 pre-registered predictions, Brier 0.215 vs base rate 0.245, accuracy 0.70, optimism +0.056.

The rev-A run of the same command (before the exclusion-search change) returned the same core, essentiality and fidelity with
192 calls. It reported no alternative: 61 exclusion-search calls found none. Its wall time was 1,275 s because other jobs were
running concurrently.

### 7.6 Tests

    uv run --no-sync pytest tests/test_method_surrogate_search.py -q      # 11 passed (34 s before the pool fix, 76 s after it with other jobs running)
    uv run --no-sync ruff check src/brainir/methods/surrogate_search.py tests/test_method_surrogate_search.py runs/surrogate_search   # clean

The tests check: the surrogate learns an AND and an OR of two conjunctions without any simulator; incremental single-removal
features equal the directly computed ones; registration; recovery of a tiny E-I oscillator with essentiality, roles, inclusion
probabilities and Brier < 0.05; an alternative is found in a redundant oscillator with a backup copy; an activity-band instance
is solved; the same seed gives the same core, probabilities, calls and surrogate diagnostics; budgets 5 / 12 / 40 are never
exceeded and still give schema-valid predictions; the prediction round-trips through the frozen schema; the optional prior; the
surrogate-error report (Brier, log-loss, calibration bins, per-tag breakdown).
