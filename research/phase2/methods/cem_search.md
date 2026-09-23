# `cem_search` — cross-entropy / estimation-of-distribution search over neuron inclusion

Method file: `src/brainir/methods/cem_search.py` (class `CemSearch`, registry name `cem_search`, version 1.0).
Tests: `tests/test_method_cem_search.py`. Development scripts and results: `research/phase2/methods/cem_search_dev/`.
Family (tournament arm 2 of `research/phase2/methods_review.md`): CEM / EDA over masks with a size penalty, elites judged on
functional pass across parameter seeds, marginal membership frequencies as the uncertainty output.

## 1. Idea in one paragraph

Keep an independent-Bernoulli distribution `q_i = P(z_i = 1)` over candidate neurons. Sample keep-only subsets from it, simulate
each on one parameter seed (seeds rotate over a small ensemble), rank them by *pass verdict, then score, then smaller size*,
and move `q` toward the elite samples (smoothed cross-entropy update). Two additions make this affordable on graphs of
thousands of nodes with a few hundred calls: **exoneration** — a neuron that is absent from (or kept but silent inside) a
*passing* keep-only set was not needed for that set, so its `q` is multiplied by a factor `< 1` (PBIL-style negative
learning, the group-testing view of the review, entry B1/H2) — and an **adaptive inclusion level** that expands `q` when too few
samples pass and shrinks it when almost all pass (a size pressure that never fixes a size). Members of the mechanism are
present and active in every passing sample, so they are never exonerated and the CE update drives them to `q -> 1`;
everything else decays geometrically. The search stops when the uncertain mass `sum_i min(q_i, 1 - q_i)` is small; a
discrete ddmin-style cleanup then minimises the MAP set, complement tests find alternative sufficient sets, full-network
silencing puts the keep-only result into the intact network's context (which sufficient set the network relies on, whether
the others are real backups, which strong neighbours are necessary in context) and gives essentiality, and fresh/widened
seeds give fidelity. Inclusion probabilities blend the converged `q` with a
mixture over the verified sufficient sets, so two equally supported implementations share probability mass instead of one
being reported with certainty.

## 2. Algorithm

### Stage 0 — zero-cost pre-screen and calibration (2·n_s to 2·n_s + 2 calls)

1. **Structural pool** (no calls). Under the rate model a neuron with no external input stays at rate 0 until it receives
   *excitatory* input from an active neuron, and it can influence the readout only through a directed path of non-zero signed
   edges. Hence `pool_struct = candidates ∩ {excitatory-edge reachable from the stimulus} ∩ {can reach a readout neuron in W}`.
   Unknown-sign neurons (zero output column) and modules without a path to the readout (e.g. an autonomous oscillator) are
   removed here with certainty; no size, weight or centrality assumption is involved.
2. **Intact runs** on the search seeds `seed·1000 + i`, `i < n_s` (`n_s = 3` if budget ≥ 400 else 2). Seeds on which the intact
   network fails the criterion are dropped from the search ensemble (two extra seeds are tried if all fail; if none passes the
   method runs in *soft mode*, ranking by score).
3. **Activity filter**. `active = ∪ active_positions` of the passing intact runs (the simulator's fingerprint). A neuron that is
   silent in the intact network carries no signal and cannot be part of the intact mechanism, except through transients
   before the analysis window. So `keep_only(active ∩ pool_struct)` is simulated on the search seeds; if it passes on ≥ 50 % of
   them the pool becomes the active set (`pool_kind = "active"`, MANC: 91 of 3,393), otherwise the structural pool is kept with
   prior `q = 0.5` for silent neurons and `0.95` for active ones (a warning is recorded).

4. **External prior (optional, never required).** If `config["prior"]` is a dict `{position: p ∈ [0, 1]}` (e.g. a mechanism
   transported from another network through a cross-network correspondence), the initial level is biased multiplicatively:
   `q0_i = level_i · (1 − s + s·p_i)` with `s = prior_strength = 0.5` and `p_i = 0.5` (neutral) for positions the dict does not
   mention; keys may be ints or strings. With `s = 0.5` a neuron with prior 1 starts at the level (0.95), a neuron with prior 0 at
   half of it (0.475) — still sampled, so a wrong prior costs iterations, not the answer (the adaptive level and the CE update
   take over after the first passing samples; tested with a deliberately misleading prior). Absence of the key means the uniform
   start described above. The pool itself (structure + activity) is never changed by the prior.

### Stage 1 — cross-entropy loop (≤ 50 % of the budget)

Population `M = clip(round(B_cem / 25), 6, 24)` per iteration (`B_cem` = calls available to this stage); one call per sample.

```
q ← q_init (0.95) on the pool
repeat for it = 0 .. max_iterations-1 while calls remain for this stage:
    draw M masks  x_m ~ Bernoulli(q);  seed_m = search_seeds[(it·M + m) mod n_s]
    outcomes_m ← sim(keep_only(pool[x_m]), seed_m)                          # M calls (cache hits are free)
    fitness_m  ← 1[pass_m] + 0.5·score_m − 0.25·|x_m| / |pool|             # pass dominates; then score; then smaller
    elites     ← the K = max(2, ceil(0.35·M)) best PASSING samples (if < 2 pass: the K best by fitness, failing ones weight 0.5)
    eff_m,i    ← x_m,i AND (i active in outcome m)                          # a kept-but-silent neuron did nothing
    f_i        ← weighted mean over elites of eff_m,i
    q          ← (1 − α)·q + α·f                                             # CE update, α = 0.5
    for every passing sample m:  q_i ← q_i·γ_ex (0.6) if x_m,i = 0;  q_i ← q_i·γ_si (0.7) if kept but silent
    pass_rate  ← #passing / M
    if pass_rate < 0.2: q ← min(1.25·q, q_max)   elif pass_rate > 0.8: q ← 0.9·q          # adaptive inclusion level
    q ← clip(q, 0.005, 0.995)
    U ← Σ_{i: q_i > 0.02} min(q_i, 1 − q_i)
    stop if it ≥ 2 and pass_rate ≥ 0.5 and (U < 0.5  or  MAP set unchanged for 3 iterations with pass_rate ≥ 0.6 and U < 2)
```

Every sample and its outcome is kept in a history (positions, seed, pass, score, fitness).

### Stage 2 — discrete cleanup (≤ 25 % of the budget, plus whatever stage 1 saved)

* Start set: the MAP set `{i : q_i ≥ 0.5}` if its keep-only passes on the search seeds; otherwise the best passing sample of the
  history that passes the ensemble (≤ 3 tried); otherwise the fragile best/MAP set (flagged in `diagnostics.cleanup_start`).
* `minimize(S)`: ddmin-style backward elimination in ascending-`q` order. Pending list = `S` sorted by `q`; chunk size
  `c = |S|/2`; remove the first `c` pending members and simulate on **all** search seeds; success → accept (chunk doubles), failure →
  halve the chunk; a single member whose removal fails is *necessary within the set* and stays. Cost ≈ `2k·log2(|S|/k) + k` tests.
* The result is verified on the search seeds; if it became fragile (< 50 % pass) removed members are re-added in descending `q`
  until it passes.

### Stage 3 — alternatives (reserve 10 % of the budget, hard cap 40 %)

Complement test: `keep_only(pool \ core)` on the search seeds. If it passes, `minimize(pool \ core)` yields a different sufficient
set, which is verified and added; the test is repeated on `pool \ (core ∪ alternatives)` up to `max_alternatives = 3` times.
The stage inherits budget left over by earlier stages but never spends more than `frac_alternatives_max = 0.4` of the total budget.
An alternative is accepted only if its minimisation **completed**. A minimisation cut short by the budget leaves a superset of
unknown size, which is not a mechanism. It is recorded as `diagnostics.alternatives_truncated`, and the search for alternatives
stops. Verified sets get weights `w ∝ pass_fraction · exp(−0.3·(|A| − k_min))` (highest weight first).

Both rules come from a bug found in the final evaluation round. The previous version accepted truncated minimisations. On
diffuse functions, where many weak routes lead to the readout, it then reported "alternatives" of hundreds of neurons and spent
up to 735 calls doing so: a dev 3,000-node negative-feedback instance and a public 500-node feedforward instance.

### Stage 4 — full-network context: which sufficient set does the intact network rely on? (silencing in the intact network)

Keep-only sufficiency removes *everything* else, including competitors that the intact network must actively suppress. In a
winner-take-all circuit, for example, the winning pool alone passes keep-only (the losing pool is gone), so its inhibitory
interneuron looks unnecessary; any neuron that drives only the "winning" readout group is then also keep-only sufficient.
This stage uses a few full-network silencing runs (`n_essential_seeds = 2` search seeds each, pass verdict `< 0.5` = destroyed) to
put the keep-only results back into the intact network's context:

```
f_A ← pass fraction of the intact network with set A silenced, for every verified set A
if some f_A < 0.5:                      # the intact network relies on A
    core ← that A (lowest f, then highest weight); other sets are NOT backups in context -> dropped from `alternatives`
    members of other sets that are also necessary are queued for the scan below
elif ≥ 2 sets:  f_∪ ← silence(union of all sets)
    f_∪ < 0.5  -> redundant implementations: all sets kept (weights as in stage 3)
    else       -> undetermined (recorded)
essential_i ← silence({i}) < 0.5 for every core member (descending q); `None` if the budget runs out
if the core is necessary:               # context scan
    for x in queued + the n_context (= 4) pool neurons with the largest synapse count to or from the core (not yet tested):
        if silence({x}) < 0.5 and keep_only(core ∪ {x}) still passes on the search seeds:  core ← core ∪ {x}, essential_x = True
```

The scan is what recovers an interneuron that is necessary only in context (the winner-take-all family); on redundant or
self-contained mechanisms it adds nothing because silencing a neighbour leaves the function intact. It costs
`2·(#sets + 1 + |core| + n_context)` full-network calls at most (~5 s each on the 4,604-node network).

### Stage 5 — fidelity and add-backs

`keep_only(core)` on `n_fidelity_seeds = 3` fresh seeds (`seed·1000 + 100 + j`) → nominal pass fraction and mean score; the same
with all parameter sds doubled (`cfg_override`) → robust pass fraction (the tournament's own robust ensemble definition).
Optional add-backs (`add_backs`, **off by default**): if the robust fraction is `< 1`, up to 3 removed members (descending `q`) are
tried and kept when they raise the robust fraction without lowering the nominal one (role `modulatory_supporting`,
`essential = False`). The feature is off because the evidence is one widened-parameter seed out of three. In a development run on
a public redundant-oscillator instance it also grew the core with a member of the *other* redundant implementation, which the
scorer's minimality check then flagged as removable. Compactness takes priority, and the robustness gap is reported instead of
papered over.

### Stage 6 — outputs

* `inclusion_probability`: for pool members `p_i = 0.3·q̃_i + 0.7·m_i`, where `m_i = Σ_a w_a·1[i ∈ A_a]` over the verified sets that
  survived stage 4 and `q̃` is the converged `q` (0.95 for members added by the context scan, capped at 0.1 for members removed
  individually and 0.2 for members removed in a chunk); active-filtered
  neurons get 0.02 (model deduction with a transient caveat), structurally excluded candidates 0.0. Two equally supported
  implementations therefore land near 0.65 / 0.35 rather than 1 / 0.
* `roles` (only `GENERIC_ROLES`): from the core's induced subgraph (strongly connected components → on a cycle, self-loops),
  sign, excitatory drive onto the readout (or onto readout group A/B for `selectivity`), input from the stimulus, and the
  criterion type: rhythm → `inhibitory_feedback` (I on cycle), `recurrent_excitatory_core` (E on cycle with self-loop, readout or
  stimulus contact), `input_relay` (E on cycle without either, or E feeding only other members), `output_driver`;
  activity_band → `gain_control` / `output_driver` / `input_relay`; persistence, ramp → `state_memory` (E on cycle) /
  `output_driver` / `input_relay` / `gain_control`; selectivity → `output_driver` (E driving group A) / `competitor` (E driving
  group B) / `lateral_inhibition` (I). Members of alternatives get `redundant_backup`, add-backs `modulatory_supporting`.
  Role probability `= (0.75 or 0.55 for fallback rules) · (0.6 + 0.4·p_i)`.
* `loop`: the largest strongly connected component (≥ 2) of the core subgraph, else a self-looped member.
* `predicted_frequency_hz`, `predicted_n_active_readout`, `predicted_function_preserved`: these claims describe the *intact*
  network under the stimulus, so they are the medians over the passing stage-0 intact runs (pass fraction ≥ 0.5 for
  `function_preserved`) and cost no extra calls. The keep-only core's own frequency and active-readout count are reported in
  `fidelity.core_frequency_hz` / `core_n_active_readout`, which are also the fallback when no intact run passed. The two
  can differ; on MANC the core alone oscillates faster (§9). `motif`: counts of E/I, loop size and roles.
* `diagnostics`: pool sizes and kind, per-iteration CE trace (pass rate, level action, `U`, expected and MAP size, number of
  exonerations), cleanup trace, verified sets with weights, stage call counts, `budget_exhausted`, warnings.

## 3. Hyper-parameters

| name | default | role |
|---|---|---|
| `n_search_seeds` | 3 (budget ≥ 400) / 2 | parameter seeds rotated through the samples; all cleanup tests must pass on all of them |
| `population` | `clip(round(B_cem/25), 6, 24)` | samples per CE iteration (6 at budget 250, 10 at 500, 20 at 1000, 24 at 2000) |
| `alpha` | 0.5 | CE smoothing toward the elite frequencies |
| `rho` | 0.35 | elite fraction (≥ 2 elites) |
| `gamma_exonerate`, `gamma_silent` | 0.6, 0.7 | multipliers for neurons absent from / silent inside a passing sample |
| `q_init`, `q_min`, `q_max` | 0.95, 0.005, 0.995 | initial level (keep-only of the whole pool passes, so start near it); floors keep exploration alive |
| `q_inactive_prior` | 0.5 | prior of intact-silent neurons when the activity filter is not verified |
| `pass_lo`, `pass_hi`, `expand`, `shrink` | 0.2, 0.8, 1.25, 0.9 | adaptive inclusion level |
| `score_weight`, `size_penalty` | 0.5, 0.25 | fitness = pass + score_weight·score − size_penalty·size/pool (pass always dominates) |
| `u_stop`, `min_iterations`, `max_iterations` | 0.5, 3, 60 | stopping rule |
| `activity_filter`, `activity_aware` | True, True | use the intact fingerprint for the pool; count kept-but-silent neurons as absent |
| `frac_cem`, `frac_cleanup`, `frac_alternatives`, `frac_final` | 0.5, 0.25, 0.10, 0.15 | reserves: a stage may spend down to `remaining − reserve of the later stages` |
| `frac_alternatives_max` | 0.4 | hard cap on the alternatives stage (it may inherit unspent budget up to this share) |
| `max_alternatives`, `n_essential_seeds`, `n_fidelity_seeds` | 3, 2, 3 | verification effort |
| `add_backs`, `max_add_backs` | False, 3 | optional robustness add-backs (stage 5); off by default |
| `n_context` | 4 | strongest core neighbours silenced in the intact network by the context scan (stage 4) |
| `w_search` | 0.3 | weight of the converged `q` in the final probability (rest: verified-set mixture) |
| `prior`, `prior_strength` | None, 0.5 | optional external prior `{position: p}` and how strongly it biases the initial level (see stage 0, item 4) |

None of them encodes a mechanism size, an identity or a dataset property; the same defaults were used on every instance and on
the real bundle.

## 4. Budget use and stopping rule

* Hard budget honesty: every simulation goes through the given `BudgetedSimulator`; a runner helper counts the *new* (uncached)
  queries of each batch with the simulator's own cache keys and refuses batches that do not fit into `sim.remaining` (or the
  stage allowance), so `BudgetExhausted` is never triggered by design (it is also caught). Each stage returns a usable
  partial state: a truncated CE loop still leaves `q`, the cleanup keeps untested members, essentiality left `None`.
* Stopping: the CE loop stops on convergence (`U < 0.5` after ≥ 3 iterations with pass rate ≥ 0.5, or a stable MAP set), on the
  stage allowance, or after 60 iterations. The whole method stops when the fidelity checks are done; unspent budget is
  simply not used (the tournament reports calls used, so cheap successes are rewarded).
* Actual spend is reported in §7–§9. The blind MANC network used 133 of 1,000 calls.

## 5. Complexity

Zero-call stage: two BFS passes on the sparse matrix, `O(E)`. CE stage: `T·M` calls with `T ≤ 60` iterations; per iteration
`O(M·N_pool)` for sampling and updates, plus the simulations (each ~0.1–0.5 s for small or dead subsets, up to the intact cost
for large oscillating subsets — on MANC the *passing* keep-only runs cost 2–4 s each because the integrator follows the rhythm).
Cleanup: `O(k·log(|S|/k))` tests × `n_s` seeds. Alternatives: the same on the complement, up to `max_alternatives` times.
Full-network context and essentiality: `n_essential_seeds·(#sets + 1 + k + n_context)` full-network runs at most (the expensive
ones, ~5 s each on 4,604 nodes). Memory: the sample history (`≤ T·M` position arrays); the simulator itself allocates the full
trajectory (~70–150 MB per run on 4,604 nodes).

## 6. Failure modes and known weaknesses

1. **Transient-only members.** A neuron that acts only before the analysis window (starting the oscillation and then falling
   silent) is invisible to the activity filter and to activity-aware presence. Guard: `keep_only(active set)` is verified by
   simulation before the filter is applied, and the cleanup verifies the core on the full seed ensemble and re-adds members if
   fragile. Residual risk: a transient-only member of a *sufficient* set that also has a non-transient substitute.
2. **Alternatives collapse during the search.** With several sufficient implementations, exoneration and the CE update pick one
   mode (the smallest, by the size term). Alternatives are recovered afterwards by complement tests, which cost `O(k log N)`
   calls each and at most 40 % of the budget. At small budgets on large pools, or on diffuse functions where no small
   alternative exists, the minimisation may not complete. No alternative is then reported: the core can still be right, but the
   ambiguity is under-reported. The inclusion probabilities of the unminimised complement stay at their search values.
3. **Non-monotone effects (disinhibition, disruptors, competitors).** A kept neuron whose inhibitor was removed can break the
   function; such samples fail, the disruptor is absent from the elites and its `q` decays. But a member that is *only* needed
   when a disruptor is present looks unnecessary to keep-only search (the winner-take-all interneuron is the canonical case).
   Stage 4 repairs this only for neurons among the `n_context = 4` strongest neighbours of the core (plus members of other
   necessary sets): a context-necessary neuron that is weakly or indirectly connected to the core is missed. Conversely, the
   scan adds any strong neighbour whose silencing destroys the function, which can include a tonic excitatory driver that is
   "necessary" without being part of the computation. Group-testing exoneration also assumes that "passed without i" means
   "i not needed", which fails for a member whose removal is compensated by a backup copy (both hover at intermediate `q`; the
   cleanup keeps one and the complement test finds the other if it is sufficient on its own).
4. **Mechanisms with many members** (say > 15): the pass rate of random samples at `q ≈ 0.9` is low, so exoneration is slow and
   the level control keeps `q` high; the CE update still separates members (present in every elite) from others, but the
   cleanup of a large MAP set costs `2k log N` tests and may be truncated at small budgets. Not observed on the synthetic
   families (`k ≤ 5`); on MANC the core had 3 members.
5. **Borderline criteria.** Samples that pass by a hair on one seed exonerate neurons that improve robustness. The core is
   minimal for the nominal ensemble, not for the widened one, so the reported robust pass fraction can be well below the nominal
   one (MANC: 1.0 nominal, 0.33 with doubled parameter sds). The optional add-back step can trade compactness for robustness.
6. **Several minimal sufficient sets; parsimony decides.** When a distractor offers a shorter sufficient route, the smallest set
   wins and the planted motif is reported as an alternative with lower weight. The canonical case is a hub with strong edges from
   the stimulus and onto the readout, which alone drives the readout into an activity band. Observed on the feedforward-driver
   instances with hub distractors: in all 7 runs the core was one hub neuron. The planted 3-neuron chain was verified as an
   alternative in 5 of them; in the two budget-250 runs the complement minimisation was truncated first (§7).
   Such a hub is a genuine minimal sufficient mechanism under the simulator. Silencing every verified set, and even their
   union, can leave the function intact (verdict "undetermined"), which says further redundant drivers exist. The method does
   not try to prefer planted motifs.
7. **Keep-only minimality vs context necessity.** A member added by the context scan is necessary in the intact network but
   removable under keep-only (the winner-take-all interneuron). A keep-only minimality check therefore lists it as removable;
   this is intended.
8. **Role labels** are rule-based and criterion-dependent; they encode the generic vocabulary, not a fitted model. Symmetric
   implementations (two identical E–I pairs) cannot be distinguished from the truth's arbitrary "core vs backup" naming.
9. **Wall time**, not calls, is the practical limit on the real network: each passing keep-only sample of an oscillating set
   costs ~2–4 s because the adaptive integrator resolves the rhythm. The simulator's per-batch process pool does not help on
   Windows: an earlier development run with 8 workers took longer (648 s for 126 calls) than a single process (§9).

## 7. Synthetic results (own development suite; truth known only to the scorer script)

**Suite.** `uv run --no-sync python research/phase2/methods/cem_search_dev/dev_eval.py build --workers 12 --large` (run once,
before the three-process limit on the shared machine) built 42 specs with `brainir.discovery.synthetic` and verified them by
simulation; 37 passed verification and 5 were dropped by the generator's own check. Generator seeds are 9000 and up, disjoint
from the public suite. The specs:
* every family at n = 50 (plain) and at n = 60 with hub distractors and misleading centrality;
* 7 families at n = 60 with a backup copy, and again with weak critical edge + low-degree critical + weight jitter + unknown
  signs;
* 5 families at n = 500 with hubs + misleading centrality + an autonomous module;
* 3 families at n = 3,000 with all four large-instance complications.

**Runs.** All runs used the final code, three slots of one process each (`bash research/phase2/methods/cem_search_dev/run_final.sh
slotA|slotB|slotC`, 15:40–15:58). Scoring was done by the public tournament scorer (`brainir.discovery.tournament.run_one`, score
seeds 5000–5003, robust checks on). Each `dev_run` line in `run_final.sh` is
`dev_eval.py run --workers 1 --label <label> <args>`. Tables: `dev_suite/results/<label>.md`; aggregate:
`results/SUMMARY.md` (`summarize_results.py`).

| label | instances | budget | seed | success | recall / precision (best alt, mean) | calls median / max | functional nominal / robust | Brier | essential acc | role acc | runs with removable members |
|---|---|---|---|---|---|---|---|---|---|---|---|
| dev_small_s0 | 30 (n ≤ 60) | 250 | 0 | 29/30 | 0.97 / 0.96 | 62 / 156 | 0.98 / 0.93 | 0.009 | 0.98 | 0.90 | 3 |
| dev_small_s0 | 30 | 500 | 0 | 29/30 | 0.97 / 0.97 | 78 / 254 | 0.98 / 0.93 | 0.007 | 0.98 | 0.90 | 2 |
| dev_small_s0 | 30 | 1000 | 0 | 29/30 | 0.97 / 0.96 | 88 / 267 | 0.98 / 0.94 | 0.009 | 0.98 | 0.90 | 3 |
| dev_small_s0 | 30 | 2000 | 0 | 29/30 | 0.97 / 0.97 | 94 / 273 | 0.98 / 0.93 | 0.008 | 0.98 | 0.90 | 2 |
| dev_small_s1_b500 | 30 | 500 | 1 | 29/30 | 0.97 / 0.97 | 74 / 238 | 0.98 / 0.93 | 0.008 | 0.98 | 0.90 | 2 |
| dev_n500_b250_s0 | 4 (n = 500) | 250 | 0 | 3/4 | 0.75 / 0.75 | 138 / 190 | 1.00 / 0.81 | 0.002 | 1.00 | 1.00 | 0 |
| dev_n500_b1000_s0 | 4 (n = 500) | 1000 | 0 | 3/4 | 0.75 / 0.75 | 216 / 390 | 1.00 / 0.81 | 0.002 | 1.00 | 1.00 | 0 |
| dev_n3000_delayed_b1000_s0 | 1 (n = 3,000) | 1000 | 0 | 1/1 | 1.00 / 1.00 | 273 | 1.00 / 1.00 | 0.000 | 1.00 | 1.00 | 0 |
| dev_n3000_redundant_b1000_s0 | 1 (n = 3,000) | 1000 | 0 | 1/1 | 1.00 / 1.00 | 336 | 1.00 / 0.75 | 0.000 | 1.00 | 0.00 | 0 |
| dev_n3000_nfc_b1000_s0 | 1 (n = 3,000) | 1000 | 0 | 1/1 | 1.00 / 1.00 | 530 | 1.00 / 1.00 | 0.000 | 1.00 | 1.00 | 0 |

Pooled over all 161 dev runs, success per family and median calls:

| family | delayed inh. osc. | E–I pair | feedforward driver | integrator | memory switch | neg. feedback | redundant osc. | ring osc. | two implementations | winner-take-all |
|---|---|---|---|---|---|---|---|---|---|---|
| success | 21/21 | 22/22 | **5/12** | 10/10 | 20/20 | 11/11 | 21/21 | 12/12 | 22/22 | 10/10 |
| median calls | 87 | 48 | 173 | 30 | 44 | 82 | 109 | 90 | 130 | 50 |

What the numbers show:
* **Budget.** No run exceeded its budget; the largest share used was 76 %. The method stops on convergence, so going from 250 to
  2000 calls changes the median spend only from 62 to 94 on small instances. Success is flat across budgets: the budget-250
  and budget-2000 runs recover the same mechanisms.
* **Two sufficient implementations** (43 runs on the redundant-oscillator and two-implementation instances). The core was always
  one of the planted implementations (43/43). The other was also reported as an alternative in 37/43 runs. The mean minimum
  p(core member) was 0.64 and the mean p(member of the other implementation) 0.33; the highest non-member p averaged 0.05. So the
  probabilities express the ambiguity instead of forcing one answer. The six runs without the second implementation:
  * the 3,000-node redundant oscillator, where the intact network relies on one pair (silencing it destroys the rhythm, which
    matches the generator's essential flags), so the other is correctly dropped;
  * one budget-250 run whose complement minimisation was truncated;
  * three runs where the second pair came out with an extra member;
  * one run where a borderline silencing (seed 1) made the core look necessary.
* **All 7 structural failures** are the feedforward-driver instances with hub distractors (failure mode 6). The core is a
  single hub neuron, and keep-only of that one neuron alone passes the activity band, including the scorer's check on 4 fresh
  seeds (functional nominal 1.0). The planted chain was reported as an alternative in 5 of the 7 runs (p ≈ 0.14 per member);
  in the two budget-250 runs the alternatives stage was truncated before reaching it. The coordinator confirmed that such hubs
  are genuinely sufficient and will extend the scorer's truth with functionally verified unplanted sets. The method was not
  tuned toward the planted chain.
* **Smaller imperfections**, all with the planted core recovered:
  * functional nominal is 0.75 on the memory-switch weak-edge instance and on the redundant-oscillator backup-copy instance
    (3 of 4 fresh seeds);
  * essential accuracy is 0.98, because 2 silencing seeds against the generator's 6-seed rule flip a borderline member;
  * role accuracy is 0.90, because the generator labels one of two symmetric redundant pairs `redundant_backup` (failure mode 8);
  * 2–3 runs per budget have "removable" members: the winner-take-all interneuron, necessary in context (failure mode 7), and
    a backup copy that the cleanup kept because its removal failed on one of the three search seeds.
* **Wall time** for all 12 steps was about 18 min on three processes.

## 8. Public evaluation instances (truth hidden)

The truth of these instances is hidden, so only functional fidelity can be checked. `eval_public.py` runs the method through
`run_one` without truth and then re-runs the tournament's own functional check (`score_function`) on the predicted core. That
check uses a separate, unbudgeted simulator: keep-only of the core on 4 fresh seeds (5000–5003), the same with doubled parameter
sds, and with 20 % weight noise, plus the keep-only minimality check. Commands, from `run_final.sh`, all at budget 1000, seed 0:

```
uv run --no-sync python research/phase2/methods/cem_search_dev/eval_public.py --budget 1000 --seed 0 --workers 1 --max-n 60 --label public_small_b1000_s0
uv run --no-sync python research/phase2/methods/cem_search_dev/eval_public.py --budget 1000 --seed 0 --workers 1 --min-n 400 --max-n 600 --label public_n500_b1000_s0
uv run --no-sync python research/phase2/methods/cem_search_dev/eval_public.py --budget 1000 --seed 0 --workers 1 --min-n 2000 --label public_n3000_b1000_s0
```

| set | instances | check nominal (mean; ≥ 0.5) | check robust sd×2 | weight noise 0.2 | core size median (range) | calls median / max | with alternatives | with removable members | wall |
|---|---|---|---|---|---|---|---|---|---|
| n ≤ 60 | 48 | 1.00; 48/48 | 0.95 | 0.84 | 2 (1–5) | 74 / 345 | 15 | 5 | 361 s |
| n = 500 | 8 | 1.00; 8/8 | 0.97 | 0.81 | 2 (1–5) | 174 / 643 | 3 | 0 | 391 s |
| n = 3,000 | 2 | 1.00; 2/2 | 1.00 | 0.62 | 3 (2–4) | 279 / 387 | 1 | 0 | 355 s |

Every predicted core on all 58 public instances reproduces the function on fresh parameter draws, at a median of 74–279
calls. The 5 "removable" cases are the 5 winner-take-all instances: their context-added interneuron is removable under keep-only
by design (failure mode 7). Weight noise is the weakest axis (0.62–0.84): minimal cores have little slack against 20 %
multiplicative synapse noise. Per-instance rows are in `results/public_*_b1000_s0.md`.

Not run: public instances at budgets other than 1000, and seeds other than 0. The shared machine allowed three processes and
the time box was about an hour after two interruptions.

## 9. Real bundle (blind tier A, `benchmarks/dng100/public_blind`, network `manc_v1.2.1`, 4,604 nodes)

Command (clean-room runner with the audit-hook sandbox; step `cleanroom_manc_b1000` of `run_final.sh slotC`):

```
uv run --no-sync python benchmarks/dng100/cleanroom/run_method.py --method research/phase2/methods/cem_search_dev/run_bundle.py \
    --bundle benchmarks/dng100/public_blind --network manc_v1.2.1 --out runs/cem_cleanroom_manc_final --seed 0 \
    --method-args "--budget 1000 --result-json C:/Dev/BrainIR_p2clean/runs/cem_cleanroom_manc_final/result_manc_v1.2.1.json"
```

Outcome:
* Return code 0 inside the sandbox, and a schema-valid prediction (`prediction_sha256 1d1a434aec72…`, bundle `efc33d775d88…`,
  method module `cem_search.py` sha256 `d9c86b76569619ea…`, the final code).
* 133 of the 1,000 calls used (11 cache hits), in 243.3 s wall time in one process. The CE stage converged after 5 iterations,
  so most of the budget was never needed.
* The output under the previous module version (`b4c6cc8f…`, without the stage-3 fix) was identical apart from the timestamp.

| stage | calls | what happened |
|---|---|---|
| pre-screen | 6 | 4,459 candidates → 3,393 in the structural pool → 91 active in the intact network (3/3 intact seeds pass); keep-only of the 91 passes on all 3 search seeds → pool = 91 |
| CE search | 88 | 5 iterations × 20 samples; pass rates 0.90, 0.65, 0.55, 0.60, 0.85; expected size 38.1 → 11.9 → 6.3 → 5.0 → 3.9; stopped at `U` = 0.49 |
| cleanup | 14 | the MAP set of 4 passes; ddmin removes 1 member (5 tests); the 3 survivors are each necessary within the set |
| alternatives | 3 | keep-only of the 88 other pool neurons fails → no alternative |
| context + essentiality | 16 | silencing the core set: 0/2 seeds pass (the intact network relies on it); silencing single members: 2825 → 0/2, 2973 → 0/2, 3310 → 2/2; silencing each of the 4 neighbours most strongly connected to the core (1,432 / 1,044 / 889 / 791 synapses to or from it): 2/2 each → nothing added |
| fidelity | 6 | keep-only of the core passes 3/3 fresh seeds (mean score 0.84); with doubled parameter sds, 1/3 |

Prediction:
* Core: positions 2825 (E, `recurrent_excitatory_core`, essential), 2973 (E, `recurrent_excitatory_core`, essential) and 3310
  (I, `inhibitory_feedback`, not essential when silenced alone). Inclusion probabilities 0.97 / 0.97 / 0.95; every other
  candidate is at ≤ 0.03. The three form one strongly connected loop; no alternatives.
* Dynamics, from the intact network over 3 seeds: rhythmic, 11.0 Hz, 2 active readout neurons. The keep-only core alone
  oscillates at 13.3 Hz, so in the simulator the rest of the network slows the rhythm.
* Robustness caveat: the 3-neuron core is sufficient on the nominal parameter ensemble but passes only 1/3 with doubled sds.
  The method reports this gap rather than hiding it.
* Tier A only: I did not reason about what these neurons are (rule 6).

Earlier development runs on the same bundle and seed agree on the core, essentiality and fidelity: an 8-worker run (648 s for
126 calls) and a single-process clean-room run (323 s, 136 calls). Both predate the full-network context stage and the
add-back default, and their outputs were deleted. They differed only in call counts and in the frequency claim, which was
then taken from the keep-only core.

## 10. Reproducibility

* Register: the module registers itself on import (`@MethodRegistry.register`); `src/brainir/methods/__init__.py` is shared and
  was not edited here — the maintainer adds `from . import cem_search` there, after which
  `uv run --no-sync python -m brainir.discovery.run --method cem_search --bundle <dir> --network main --out pred.json --budget 1000 --seed 0`
  works directly. Until then, `research/phase2/methods/cem_search_dev/run_bundle.py` imports the module and forwards to the same
  entry point (it is also the clean-room method file used in §9).
* Tests: `uv run --no-sync python -m pytest tests/test_method_cem_search.py -q`: 9 tests, 32 s, all passing on the final code
  (registration, E–I pair recovery + determinism + schema round trip, two implementations with ambiguous probabilities, tiny
  budgets 4 and 12 respected with a valid partial result, feedforward driver and memory switch, winner-take-all context
  necessity, optional external prior incl. a deliberately misleading one, structural pool excludes an autonomous module,
  tournament harness). The tests build their own tiny instances with `brainir.discovery.synthetic` (seeds 300–357).
* Determinism: all randomness comes from `np.random.default_rng(seed)`; simulator seeds are `seed·1000 + i` (search), `seed·1000 + 100 + j`
  (fresh fidelity seeds); ties are broken by position. Two runs with the same seed and budget give identical results (tested).
* Inputs and integrity:
  * The method reads only what `DiscoveryProblem` exposes as model inputs (`W`, `C`, `signs`, stimulus, readout, criterion,
    model config) and the budgeted simulator. It never reads `problem.root`, network, instance or manifest names, cell-type
    tokens or any other label (checked by grep on the module).
  * Development used three sources: my own dev suite (`dev_eval.py build`, generator seeds 9000+, truth read only by the scorer
    in `dev_eval.py`), the public instance directories (no truth; functional checks only; the harness uses directory names only
    to filter by size), and the blind MANC bundle.
  * One exposure to report: during orientation, `head -40` of `data/synthetic/mechanisms_v1/BUILD_REPORT.json` was displayed
    once. The coordinator later deleted that file as truth-bearing. The excerpt showed the per-node essential/necessary flags
    of the first public instance. Nothing from it was used in code, defaults or tuning, and no script of mine reads that file.
* Development scripts (`research/phase2/methods/cem_search_dev/`): `dev_eval.py` (build the own dev suite, run + score with the
  public tournament scorer, smoke runs), `eval_public.py` (public instances, functional checks only), `run_bundle.py` (bundle
  driver and clean-room method file), `run_final.sh` (the exact final runs of §7–§9, three slots of one process each, with
  per-step logs in `results/logs/`), `summarize_results.py` (the tables of §7–§8, saved as `results/SUMMARY.md`),
  `timing_probe.py` (pool sizes and call costs), `watch_steps.sh` (progress helper). Outputs: `dev_suite/` (own instances +
  truth + results), `results/` (public-instance tables and logs), `runs/cem_cleanroom_manc_final/` (clean-room record, prediction
  and full result JSON).
