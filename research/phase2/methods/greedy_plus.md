# greedy_plus — intervention-guided group elimination with multi-seed decisions

Method family: **improved simulation-guided elimination** (successor of `greedy_reference`, the Phase 1 baseline's
algorithm). Code: `src/brainir/methods/greedy_plus.py` (registered as `greedy_plus`, version **1.2**). Tests:
`tests/test_method_greedy_plus.py`. Everything below was developed on the author's own synthetic instances
(`brainir.discovery.synthetic`, truth known), checked functionally on the public instances (truth hidden) and run on the
real blind bundle; no answer of any real circuit was used or looked at. The module registers itself on import; the
integrator adds `from . import greedy_plus` to `brainir/methods/__init__.py` (until then import the module first).

## 1. What changes relative to the reference

| reference (`greedy_reference`) | `greedy_plus` |
|---|---|
| candidate pool = top-degree neurons within 2 hops of the stimulus, doubled until it passes | candidate set = every neuron that can influence the readout (exact reachability pruning) minus neurons silent in the intact runs (verified by simulation) |
| one seed for the ranking, two for acceptance | every accept/reject decision is a strict majority over 3 working seeds, run sequentially with early stopping |
| removes the least impactful neuron per round (leave-one-out over the whole pool) | adaptive group testing over keep-only sets: remove random chunks, bisect failing chunks, double/halve the chunk (about `k log2(n/k)` decisions) |
| stops at a preset size `k` (3) | stops when no member can be removed (1-minimality, re-checked for non-monotone effects); fresh-seed validation with add-back |
| ties broken by degree and node position | node order is a seeded random permutation (or ordered by an optional prior); results checked on permuted copies of the graph |
| essential = silencing a survivor | essential = silencing a member; plus a group-silencing screen of the other active candidates that adds neurons which are essential without being needed under keep-only |
| no uncertainty, no alternatives, no roles | inclusion probabilities from evidence classes; alternatives from disjoint search, replacement search and a randomized restart; the reported core is the most robust minimal set; generic roles from sign + wiring + criterion |

## 2. Algorithm (plain language)

Let `U` be the candidate positions (everything except stimulus and readout). A kept set `S ⊆ U` is simulated as
`keep_only(S)` (or, when `S` is large, as `silence(U \ S)`: the same network, cheaper canonical form); `S = U` is the
intact network. A set **passes** when a strict majority of the working seeds pass the problem's criterion; seeds are run
one at a time and the decision stops once it is determined (3 seeds: two passes accept, two failures reject). Decisions
and outcomes are cached, so a repeated question costs nothing.

1. **Working seeds.** Simulate the intact network on seeds `1000·seed + 17, +18, …` until 3 pass (at most 8 tries). A seed
   on which the intact network fails cannot separate necessary from unnecessary neurons and is discarded.
2. **Exact pruning.** (a) Structural, zero calls: neurons not reachable from the stimulus through non-zero signed weights
   are silent (no baseline activity in this rate model); neurons from which no readout neuron is reachable cannot change
   the readout. (b) Activity: neurons silent (peak below the criterion's activity threshold) in every passing intact run
   are removed as one group and the reduced set is verified by one decision; if it fails, (b) is undone. Result: `K0`.
3. **Group elimination** (`eliminate`). `K := K0` passes by construction. Order the unresolved neurons (seeded random
   permutation; with a prior, lowest prior first), take a chunk `X` (initially 25 % of them) and decide `K \ X`:
   * passes → `X` is unnecessary: `K := K \ X`, the chunk doubles; neurons that were silent in the passing outcomes are
     queued as the next chunk;
   * fails → bisect `X`: decide `K \ X1`; if it passes, clear `X1` and continue inside `X2` (which must hold a necessary
     neuron, because `(K \ X1) \ X2 = K \ X` failed); otherwise continue inside `X1` and put `X2` back in the queue. The
     surviving singleton is necessary; the chunk halves.
   When the queue is empty, every remaining neuron is tested individually against the final set (up to 3 rounds); a
   neuron whose removal now passes (a non-monotone context effect) is removed and the round restarts. Output: a 1-minimal
   passing set `M` together with the failed leave-one-out decisions of its members.
4. **Validation and add-back.** Decide `keep_only(M)` on 3 fresh seeds (a failing seed counts only if the intact network
   passes on it). If a strict majority fails and at least 20 % of the budget is left, the first failing seed joins the
   working seeds (majority of 4 = 3 passes) and step 3 is re-run from `K0` (cached decisions make this cheap); the re-run
   adds back whatever the extra seed needs.
5. **Essentiality.** For each member: decide `silence({v})` in the full network (essential = fails). Then the
   **essential screen**: the other active candidates (`K0 \ M`) are group-silenced in the full network; a passing group
   is cleared, a failing group is bisected (both halves tested; not cumulative) down to single neurons whose silencing
   alone fails. Such neurons (e.g. an inhibitor that keeps a competitor silent — never needed under keep-only, because
   keep-only removes the competitor as well) are essential parts of the mechanism and join the core (set `E`). The
   screen may use at most 30 % of the initial budget; with a prior, high-prior neurons are screened first.
6. **Alternatives and restart** (each phase capped: alternatives ≤ 50 % of the calls left after the screen, the restart
   ≤ 35 % of the calls left after that, both minus a reserve for step 7). If `K0 \ M` still passes, a disjoint
   alternative is eliminated from it (repeated up to `max_alternatives`). For every non-essential member `v` of `M`, a
   replacement mechanism is searched in `K0 \ {v}` (falling back to `U \ {v}`) with the other members protected. One
   randomized restart of step 3 (different order) re-derives the mechanism if affordable.
7. **Core selection.** Candidates = `M ∪ E` and every alternative `∪ E`. Each is validated on the same 3 fresh seeds as
   step 4 (nominal pass fraction) and probed with 3 stress runs (all parameter sds ×2 and multiplicative weight noise
   sd 0.2). A candidate that strictly contains a candidate at least as good on both is not minimal and is dropped. If
   several candidates tie on (nominal, stress), each tied set's distinctive members (those not shared by all tied sets)
   are silenced in the FULL network on the working seeds: reliance = 1 if the function fails + the relative change of
   the readout's median peak rate, i.e. how much the intact network relies on that set. Ranking: nominal pass fraction,
   stress pass fraction, reliance, size (Occam), stress score, mean absolute weighted degree of the members (the only
   anatomical input, last), order of discovery. The winner is the core; the rest are `alternatives`. Essentiality is
   completed for new members if the core switched.
8. **Fidelity, probabilities, roles.** Fidelity = keep-only pass fraction on the fresh seeds and on the search seeds,
   stress pass fraction, median frequency and active-readout count of passing runs. Inclusion probabilities (§5). Roles
   from sign + wiring + criterion (§6). `loop` = largest strongly connected component of the core's subgraph.

The finishing phases (5–8) run inside a guard: running out of budget ends the phase, and an unexpected failure (for
example a `MemoryError` inside the simulator on a memory-starved machine) is recorded in `diagnostics.errors` without
losing the mechanism found. A `MemoryError` during the elimination returns the current passing set (`complete=False`).

### Pseudocode

```
discover(problem, sim, seed, prior=None):
    U = candidates;  seeds = first 3 seeds on which the intact network passes
    K0 = structural_prune(U);  silent = K0 \ active(intact runs);  if decide(K0 \ silent): K0 = K0 \ silent
    M = eliminate(K0, seeds, order=prior or random)                    # 1-minimal passing set
    val = validate(M, 3 fresh seeds);  if most fail and budget: M = eliminate(K0, seeds + failing seed)
    ess = {v: not decide(U \ {v}) for v in M};   E = essential_screen(K0 \ M)    # group silencing, bisected
    alts = disjoint(K0 \ M) + replacements(non-essential v in M) + restart()          # all capped
    C = [M ∪ E] + [A ∪ E for A in alts];  drop supersets dominated by a subset (nominal and stress)
    core = argmax_C (nominal fresh-seed pass, stress pass, reliance of distinctive members if tied, -size, stress score, strength)
    return core, probabilities, roles, essential, alternatives, fidelity

eliminate(K, seeds):
    queue = order(K);  chunk = |queue| / 4
    while queue:
        X = pop(queue, chunk)
        if decide(K \ X): K -= X; chunk *= 2; queue = silent_in(passing outcomes) + queue
        else:
            while |X| > 1:
                X1, X2 = halves(X)
                if decide(K \ X1): K -= X1; X = X2        # X2 must hold a necessary neuron
                else: queue = X2 + queue; X = X1
            mark X[0] necessary; chunk /= 2
    repeat ≤ 3 times: for v in shuffle(K): if decide(K \ {v}): K -= {v}         # 1-minimality
    return K

decide(S, seeds): run keep_only(S) [or silence(U \ S)] seed by seed; stop at a strict majority either way (cached)
```

## 3. Hyper-parameters (`default_config`)

| name | default | meaning |
|---|---|---|
| `seeds_per_decision` | 3 | working seeds per decision (strict majority: 2 → both, 3 → 2 of 3, 4 → 3 of 4) |
| `max_seed_trials` | 8 | intact runs tried to collect the working seeds |
| `validation_seeds` | 3 | fresh seeds for the keep-only validation of the core and of every alternative |
| `initial_chunk_fraction` | 0.25 | first group size relative to the unresolved candidates (then ×2 / ÷2 adaptively) |
| `activity_pruning` | True | remove neurons silent in passing runs (always verified by a decision) |
| `structural_pruning` | True | exact reachability pruning |
| `essential_screen`, `essential_screen_fraction` | True, 0.3 | group-silencing screen of the active non-members; call cap as a fraction of the initial budget |
| `max_alternatives`, `alternatives_budget_fraction` | 3, 0.5 | alternatives searched/reported; cap as a fraction of the calls left |
| `restarts`, `restart_budget_fraction` | 1, 0.35 | randomized re-derivations, only if their cost fits the cap |
| `stress_probes`, `stress_noise_sd` | 3, 0.2 | stress ensemble (sds ×2 + weight noise) for ranking the equivalent sets |
| `t_end` | None | optional shorter simulation horizon passed to every query (not used in any run reported here) |
| `prior` | absent | optional `{position: prior inclusion probability}` (§4) |

No parameter encodes a mechanism size, a neuron id, a cell type or a dataset-specific threshold. The values were set
once on the author's small instances and not tuned per instance.

## 4. Optional prior (`config["prior"]`)

`config["prior"]` = `{position: p}` with `p ∈ [0, 1]` (keys may be strings; unknown positions and non-numeric values are
ignored; absent or empty = uniform). It is how a cross-network component can hand structure from one network to
another. It is used only to **order** the search, never to decide membership:

* group elimination: the unresolved neurons are sorted by `prior + U(0, 0.25)` ascending — low-prior neurons are removed
  first, so a good prior makes the first large chunks pass and saves bisections; a bad prior only costs calls;
* essential screen: high-prior neurons are screened first (so they are covered even if the screen's call cap is hit);
* a core member that could not be tested individually because the budget ran out gets `0.5·0.6 + 0.5·prior`
  instead of 0.6.

Every membership decision is still made by simulation. The test `test_optional_prior_orders_the_search_but_never_decides`
gives a deliberately wrong prior (0.05 on the true members, 0.9 on everything else) and checks that the true mechanism
is still recovered within the budget.

## 5. Inclusion probabilities

Every candidate receives a probability from its evidence class:

| class | p |
|---|---|
| core member; its removal from the core fails AND silencing it alone in the full network fails (essential) | 0.97 |
| core member; its removal from the core fails (necessary in the final set) | 0.90 |
| core member of a switched-to alternative (completed, validated elimination) | 0.90 |
| core member never tested individually (budget ran out: partial result) | 0.60 (or 0.5·0.6 + 0.5·prior) |
| member of a reported alternative, not of the core | 0.15 |
| cleared by a passing group/bisect/singleton decision, or member of a dropped non-minimal set | 0.03 |
| silent in every passing intact run | 0.01 |
| structurally unable to influence the readout | 0.002 |

If a restart was affordable and it re-derived a set overlapping the core, the non-screen members of those runs are blended
50/50 with their membership frequency across the runs (`0.02 + 0.93·freq`); runs that found a disjoint set found another
mechanism and are reported as alternatives instead. The values are a coarse calibration on the author's instances (mean
Brier score 0.007–0.008 there, against 0.244 for the reference's 0/1 output).

## 6. Roles, loop, motif (no calls)

Per core member, from its sign, its place in the core's own wiring (`W` restricted to the core: self-loop, strongly
connected component, all-excitatory cycle, projection onto the readout or onto other members, input from the stimulus)
and the criterion type:

* `selectivity`: inhibitory → `lateral_inhibition`; excitatory driving readout group A → `output_driver`, group B →
  `competitor`, otherwise `input_relay`;
* inhibitory: `rhythm` → `inhibitory_feedback`; other criteria → `gain_control`;
* excitatory in an all-excitatory cycle or self-exciting: `persistence`/`ramp` → `state_memory`, otherwise
  `recurrent_excitatory_core`; in a mixed cycle and projecting to the readout: `rhythm` → `recurrent_excitatory_core`,
  otherwise `output_driver`; projecting to the readout → `output_driver`; projecting to other members → `input_relay`;
* members of alternatives outside the core → `redundant_backup`; unknown sign → `unknown`.

Role probabilities are 0.4–0.75. `loop` = the largest strongly connected component of the core (or the self-exciting
neuron); the motif string summarises its sign composition.

## 7. Complexity, stopping rule, budget

* **Calls.** Elimination: about `k·(log2(n_K/k) + 2)` decisions for a `k`-neuron mechanism among `n_K` candidates after
  pruning, 2–3 calls each. Plus 3–5 intact runs, 1 pruning verification, `k` leave-one-out confirmations, 3–6 validation
  calls, `k` essentiality decisions, the screen (`≈ |K0 \ M| / g*` decisions, where `g*` is the largest group the network
  tolerates silencing, plus `2·log2 g*` per essential neuron found), the capped alternative/restart eliminations and
  6 calls per candidate set in step 7. Observed totals: 16–236 calls for `n ≤ 60`, 65–330 for `n = 500`, 117–207 for
  `n = 3000`, far below the budgets tried (250–1000).
* **Stopping rule.** The elimination stops when no member can be removed without losing the function (1-minimal: every
  member individually tested against the final set); there is no size prior. The method stops when its phases are done,
  not when the budget is used up.
* **Budget honesty.** Every simulation goes through the `BudgetedSimulator`. Each phase reserves the calls the later
  phases need; a phase that would exceed its allowance ends gracefully. If the elimination itself is cut short, the
  current passing set (a superset of a mechanism; every removal was verified) is returned as the core, untested members
  get 0.6 and `diagnostics.oracle.budget_exhausted` is true. The tests exercise budgets of 6, 12 and 25 calls.
* **Wall time** is dominated by full-network simulations (intact seeds, essentiality, the screen, reliance) and the
  first large keep-only sets; the method is sequential (one process, no batching).

## 8. Results

### 8.1 Instances and commands

Own instances: `brainir.discovery.synthetic.build_instance(InstanceSpec(family, n, seed, complications))`, verified with
`verify_instance(inst, seeds=list(range(6)))`, exported with `export_instance(inst, ver, root, n_order_variants=2)`.
Specs (the same layout as the public suite, different seeds): small = every family at n = 50 (plain) and n = 60 with
`hub_distractor+misleading_centrality` and `weight_jitter+unknown_signs` (seeds 100–129), plus `backup_copy`,
`weak_critical_edge+low_degree_critical` and `autonomous_module` at n = 60 for the seven families of the public suite
(seeds 130–150): 45 of 51 verified. Medium = every family at n = 500 with `hub_distractor+misleading_centrality+
autonomous_module`, 20 readout neurons (seeds 300–309): 7 of 10 verified. Large = five families at n = 3000 with
`hub_distractor+misleading_centrality+backup_copy+autonomous_module`, 40 readout neurons, density 0.004 (seeds 400–404):
3 of 5 verified. Scoring: `brainir.discovery.tournament.run_one(..., truth_path=<own truth>, score_seeds=[5000, 5001,
5002, 5003], robust=True)` and `tournament.summarize` (success = all members of some listed sufficient alternative
recovered; functional = keep-only of the predicted core on fresh seeds, nominal and with parameter sds ×2).

The runs used a local harness (session scratchpad, not part of the repository) whose two commands are equivalent to the
script in Appendix A (`build` = the spec loop above; `run` = `run_one` per instance in a process pool; `--max-n 100` =
the small instances, `--min-n 400 --max-n 600` = medium):

```
uv run --no-sync python dev_harness.py build --sizes small|medium|large --workers 6
uv run --no-sync python dev_harness.py run --methods greedy_plus [greedy_reference] --budget 500 --seeds 0 [1] \
    [--networks main order1] [--max-n 100 | --min-n 400 --max-n 600 | --min-n 2000] [--no-robust] --workers 2 --label <label>
```

### 8.2 Small instances (45 instances, n = 50/60, budget 500)

| version | runs | success | precision (median) | functional nominal | functional robust | calls median (min–max) | size median | role acc | essential acc | Brier |
|---|---|---|---|---|---|---|---|---|---|---|
| **1.2 (final), seed 0** | 45 | **1.000 (45/45)** | 1.00 | 0.994 | 0.950 | 76 (20–226) | 2 | 0.93 | 1.00 | **0.001** |
| 1.1, seeds 0+1 | 90 | 0.956 (86/90) | 1.00 | 0.994 | 0.944 | 72 (19–236) | 2 | 0.94 | 1.00 | 0.008 |
| 1.0, seeds 0+1 | 90 | 0.856 (77/90) | 1.00 | 0.997 | 0.947 | 64 (16–224) | 2 | 0.93 | 1.00 | 0.007 |
| `greedy_reference` (k = 3), seeds 0+1 | 90 | 0.689 (62/90) | 0.67 | 0.819 | 0.792 | 204 (8–500) | 3 | – | 1.00 | 0.244 |

Command of the final row: `dev_harness.py run --methods greedy_plus --budget 500 --seeds 0 --workers 2 --max-n 100
--label small_final_b500` (exact final code; wall 8 s median, 30 s max per run on the shared machine). It reproduces the
earlier run of 1.2 before the last two ranking refinements call for call. Per family (success / median calls): delayed
inhibitory oscillator 1.00/86, E-I pair 1.00/48, feedforward driver 1.00/74, integrator 1.00/33, memory switch 1.00/41,
negative-feedback controller 1.00/51, redundant oscillator 1.00/128, ring 1.00/84, two implementations 1.00/196,
winner-take-all 1.00/51. No run recorded a swallowed error or ran out of budget. Where the calls went: alternatives
31 %, elimination 24 %, restart 16 %, stress probes 7 %, essential screen 7 %, member essentiality 5 %, validation 4 %,
working seeds 3 %, pruning 2 %, fidelity 1 %, reliance 1 %. The core switched away from the first sufficient set in 6
runs; the reliance tie-break was needed in 4. In the three distractor cases that failed in earlier versions it chose the
planted mechanism: feedforward chain 0.09 vs single hubs 0.06/0.06/0.01, negative-feedback pair 0.52 vs the half-weight
backup copy 0.12, and memory switch 0.06 vs a mutually exciting hub pair 0.05 — the last margin is thin (see §9).
Role accuracy 0.93: the misses are redundant-oscillator runs that report the second E-I pair, which the generator labels
`redundant_backup` while the rules call it `recurrent_excitatory_core`/`inhibitory_feedback` (which pair is canonical is
arbitrary). Only seed 0 was run for the final version; versions 1.0/1.1 and the reference used seeds 0 and 1.

Version history: 1.0 = pruning + group elimination + validation + member essentiality + alternatives; it missed every
winner-take-all instance (the lateral inhibitor is not needed under keep-only) and one backup-copy case. 1.1 added the
essential screen and the choice of the most robust equivalent set (stress ensemble). 1.2 (final) added fresh-seed
validation of every candidate set, the lexicographic ranking (nominal pass, stress pass, reliance of the distinctive
members, size) instead of a continuous stress score, removal of non-minimal supersets, the budget caps for
alternatives/restarts, the guarded finishing phases and the optional prior.

Reference failures (for comparison): 0/12 delayed inhibitory oscillator and 0/6 feedforward driver (its pool — the
top-degree neurons within 2 hops of the stimulus — does not contain the members further downstream: recall 0.4 / 0.67,
and the elimination stalls at 7–44 neurons), 0/8 winner-take-all (the lateral inhibitor is not needed under keep-only;
the fixed size 3 is filled with other neurons), 6/8 negative-feedback controller.

### 8.3 A second seed on the hard instances (hub distractors and backup copies)

Seed 1 on the 14 small instances with `hub_distractor` or `backup_copy` (`--seeds 1 --instances hub_distractor
backup_copy --workers 1`), version 1.2 before the last ranking refinement: 13/14 success, median 119 calls (26–238),
functional nominal 1.00, robust 0.93, Brier 0.005. The failure (negative-feedback controller with a backup copy) showed
that the reliance probe was confounded by a member shared by both tied sets (the essential inhibitor): silencing it
together with either set changes what the remaining neuron does. The final version silences only each set's distinctive
members; re-run with the final code (`--seeds 0 1 --instances negative_feedback_controller__n60__backup`), the instance
succeeds on both seeds (108 and 131 calls). In the saved diagnostics this is the only run in which tied sets shared
members.

### 8.4 Node-order independence (version 1.1, 45 small instances × {`main`, `order1`}, budget 500, seed 0)

The same neurons (mapped through the permutation) were returned on both orderings for 40/45 instances. The 5 differences
are 4 redundant-oscillator instances (either E-I pair is a correct answer; which one is reported depends on the chunk
order) and 1 memory-switch instance with hub distractors (the planted single neuron on one ordering, a hub pair on the
other). Success: 0.933 (`main`) and 0.956 (`order1`); median calls 75 and 77.

### 8.5 Medium and large instances

| version | instances | budget | success | precision | functional nominal | functional robust | calls median (min–max) | wall median (max) | Brier |
|---|---|---|---|---|---|---|---|---|---|
| 1.2* | 7 × n = 500 | 500 | 7/7 | 1.00 | 1.00 | 0.96 | 174 (66–309) | 38 s (67 s) | 0.001 |
| 1.1 | 7 × n = 500 | 250 | 7/7 | 1.00 | 1.00 | 0.93 | 109 (65–250) | 72 s (161 s) | 0.002 |
| 1.1 | 7 × n = 500 | 500 | 7/7 | 1.00 | 1.00 | 0.96 | 172 (65–328) | 106 s (209 s) | 0.002 |
| 1.1 | 3 × n = 3000 | 1000 | 3/3 | 1.00 | 1.00 | not run (`--no-robust`) | 203 (117–207) | 701 s (789 s) | 0.001 |

\* run with version 1.2 before the last two ranking refinements (nominal before stress; reliance on distinctive
members). An offline check of the saved diagnostics shows that the final ranking selects the same core in all 7 runs and
that no tie needed the reliance probe, so these numbers hold for the final code. Command: `dev_harness.py run --methods
greedy_plus --budget 500 --seeds 0 --workers 1 --min-n 400 --max-n 600 --label med_v12_b500`. At budget 250 (1.1) the
two-implementations instance used the whole budget and still succeeded (its alternative search was cut short). The large
instances were not re-run with version 1.2.

### 8.6 Public evaluation instances (truth hidden; version 1.1, budget 500, seed 0, network `main`)

All 56 public instances with n ≤ 600 (`run_one(..., truth_path=None)` + an independent keep-only check of the returned
core on fresh seeds 5000–5003 with a fresh simulator): mean fresh-seed pass fraction **0.982**; 55/56 cores pass on at
least half of the fresh seeds; median 73 calls (max 500: one n = 500 feedforward-driver instance, where the capped
alternative search did not exist yet in 1.1); 20/56 runs report alternatives. The one weak core
(`two_implementations__n60__weight_jitter+unknown_signs__s522563`, fresh 0.25) is a 2-neuron oscillator that passes on
the search seeds but is marginal on fresh ones. The final version validates every candidate set on 3 fresh seeds and
ranks the nominal pass fraction first: on this instance it now reports the 4-neuron implementation (validation 3/3,
stress 2/3) and lists the 2-neuron one (validation 2/3, stress 3/3) as the alternative; the independent fresh-seed check
gives 4/4 for the reported core (1/4 for the alternative). Command: `one_public.py
two_implementations__n60__weight_jitter+unknown_signs__s522563 500` (= `run_method(..., budget=500, seed=0)` + the
fresh-seed check). The other public instances were not re-run with the final version, and the large public instances
(n = 3000) were not run at all.

### 8.7 Real blind bundle (`benchmarks/dng100/public_blind`, network `manc_v1.2.1`, 4,604 neurons)

Final version, budget 1000, seed 0, through `brainir.discovery.run.run_method` (the same call as the command in
Appendix B; the machine was shared): **157 of 1000 calls, 243 s wall**, no error, no phase out of budget. Structural
pruning removed 541 candidates and the verified activity pruning another 3,831 (neurons silent in all three passing
intact runs), leaving 87 candidates. The group elimination used 44 calls (3 passing groups, 9 bisection steps) and
returned a 3-neuron set (2 excitatory, 1 inhibitory) whose members are each individually necessary. The keep-only
network of that set passed on 3/3 fresh seeds and 3/3 search seeds, but only on 1/3 stress probes (sds ×2 + weight
noise). The 2 excitatory members are essential by single silencing in the full network; the inhibitory one is not. The
essential screen (84 other active candidates, 7 calls) found nothing more. One alternative was found: a 4-neuron set
sharing the two excitatory members. The randomized restart re-derived the same 3-neuron set. Call split: seeds 3,
pruning 2, elimination 44, validation 3, essentiality 6, screen 7, alternatives 42, restart 40, stress 9, fidelity 1.
This shows only that the method runs within the budget and produces a self-consistent, validated result; its
correctness is not knowable here. (The run used version 1.2 before the last two ranking refinements; its saved
diagnostics give (nominal, stress) = (1.00, 0.33) for the reported set and (1.00, 0.00) for the alternative, so the final
ranking makes the same choice without a reliance probe and the same 157 calls.)

Clean-room runner (version 1.1, budget 60, seed 0): `benchmarks/dng100/cleanroom/run_method.py --method
<wrapper.py> --bundle benchmarks/dng100/public_blind --out <dir> --network manc_v1.2.1 --seed 0 --method-args
"--budget 60"` with the 6-line wrapper of Appendix B → return code 0, schema-valid prediction, 3-neuron core, 60 calls,
512 s wall (the machine was heavily shared). This shows the method runs under the sandbox and stops at its budget; it
says nothing about correctness, which is not knowable here.

### 8.8 What could not be run

* The budget-1000 medium sweep (greedy_plus and greedy_reference, n = 500) was stopped by the machine's low-memory
  monitor and, per instructions, not restarted; the medium numbers above are for budgets 250 and 500.
* Budget 2000 was not tried; the method's own stopping rule ends every run far below 1000 calls on the synthetic sizes
  tried, so a larger budget only enlarges the caps for alternatives and restarts.
* Final-code runs: the small suite (seed 0), the backup-copy instance on seeds 0 and 1, the marginal public instance,
  and the unit tests. The medium sweep and the real-bundle run used version 1.2 just before the last two ranking
  refinements (shown above to make the same choices). The order-variant, full public-instance and large sweeps are
  from version 1.1 (differences: §8.2 history). The seed-1 hub/backup subset is from pre-refinement 1.2 (§8.3).
* Seeds 1+ of the full small suite, the public instances with n = 3000, and the other two real networks
  (`manc_v1.2.3`, `male-cns_v1.0`) were not run with the final version for lack of time.

### 8.9 Data-use statement

* **BUILD_REPORT exposure.** During initial orientation, one exploration command printed the first 3,000 bytes of
  `data/synthetic/mechanisms_v1/BUILD_REPORT.json` (`head -c 3000`). The coordinator later removed this file because it
  holds truth-derived fields. That excerpt contained the build header (66 specs, 58 verified, 8 dropped) and the entries
  of the first 4–5 public instances (E-I pair and ring families): intact pass fractions, the alternatives' pass
  fractions, and "essential"/"necessary" flags keyed by the generator's canonical node indices. Those flags imply 2-member
  cores for the E-I pairs and 4-member cores for the rings.
* **Nothing from the excerpt was used.** No code, configuration, threshold or design decision is based on it, and no
  script I ran read the file. The public-instance runner lists only `mechanisms_v1/instances/*` directories and scores
  with `truth_path=None`. The per-family motif sizes are defined in the generator source
  (`brainir/discovery/synthetic.py`) anyway. My own suite mirrors `default_specs()` from that source with other seeds.
* **The method reads only the problem object.** It uses the signed matrix, signs, stimulus/readout positions, criterion
  spec and model configuration. It never reads `problem.root`, network or instance names, manifest labels or any file;
  a grep of the module for these finds nothing.
* **Instance names in dev scripts.** My scripts parse instance directory names (size, family) only to select which
  instances to run and to label my reports; the names are never passed to the method.

## 9. Known failure modes and weaknesses

1. **Distractors that implement the function.** A stimulus-driven hub that drives the readout into an activity band, a
   pair of mutually exciting hubs that sustains activity, or a half-weight backup copy that alone keeps the readout in
   band are genuinely sufficient under the simulator. The method then has to choose among equivalent sets; robustness,
   reliance and size decide, and when they point to the distractor the planted mechanism is reported only as an
   alternative (scored as a miss by a scorer that lists only the planted sets). The reliance tie-break fixed all such
   cases on the author's suite in the final version, but it is a heuristic with thin margins: the memory-switch hub case
   was decided by 0.06 vs 0.05, and a different parameter draw can flip it. Reliance also assumes that the planted
   mechanism is the one the intact network uses most, which need not hold in real circuits with genuine redundancy.
2. **Non-monotone group effects.** A chunk removal can fail through synergy or pass because an inhibitor is removed
   together with its target; the bisection may then isolate a neuron that is needed only in that context. The final
   1-minimality rounds remove such neurons again (extra calls). In dense networks the essential screen may need small
   groups and hits its cap; unscreened neurons keep their sufficiency-based probability.
3. **Seed flukes.** With 3 working seeds a set with a true pass probability of 0.3 is accepted with probability 0.22.
   Fresh-seed validation of every candidate and the add-back re-run catch most consequences; a genuinely marginal
   mechanism (intact pass rate near 0.5) can still be misjudged. Validation uses only 3 fresh seeds, so the nominal
   ranking of equivalent sets can be decided by one seed (the marginal public instance of §8.6: 3/3 vs 2/3).
4. **Replacement mechanisms made of neurons that are silent in the intact network** are only found through the
   `U \ {v}` fallback of the replacement search. (Essentiality itself is exact: silencing a silent neuron changes nothing.)
5. **Wall time on large graphs.** Full-network decisions cost seconds each and the method is sequential; at 4,604
   neurons a run takes tens of minutes, more on a shared machine.
6. **Roles are rule-based** (sign + wiring + criterion). They match the synthetic families by construction and carry
   moderate probabilities; on real circuits they are hypotheses.
7. **Probabilities are evidence-class constants**, not a posterior; they are well calibrated only for the kinds of
   evidence seen on the author's suite.

## Appendix A — reproduction script (equivalent to the harness)

```python
# uv run --no-sync python repro.py   (Windows: run from a file, not stdin, when using a process pool)
import json
from pathlib import Path
import brainir.methods.greedy_plus  # registers the method
from brainir.discovery.synthetic import FAMILIES, InstanceSpec, build_instance, export_instance, verify_instance
from brainir.discovery.tournament import run_one, summarize

ROOT = Path("mysuite")
specs, seed = [], 100
for fam in FAMILIES:
    for comp, n in (((), 50), (("hub_distractor", "misleading_centrality"), 60), (("weight_jitter", "unknown_signs"), 60)):
        specs.append(InstanceSpec(fam, n, seed, comp)); seed += 1
for fam in ("ei_pair_oscillator", "delayed_inhibitory_oscillator", "redundant_oscillator", "two_implementations",
            "negative_feedback_controller", "memory_switch", "winner_take_all"):
    for comp in (("backup_copy",), ("weak_critical_edge", "low_degree_critical"), ("autonomous_module",)):
        specs.append(InstanceSpec(fam, 60, seed, comp)); seed += 1
for spec in specs:
    inst = build_instance(spec)
    ver = verify_instance(inst, seeds=list(range(6)))
    if ver["verified"]:
        export_instance(inst, ver, ROOT, n_order_variants=2)
records = [run_one("greedy_plus", d, "main", budget=500, seed=0, config=None, truth_path=ROOT / "truth" / f"{d.name}.json",
                   score_seeds=[5000, 5001, 5002, 5003], workers=1, robust=True)
           for d in sorted((ROOT / "instances").iterdir())]
print(json.dumps(summarize(records)["greedy_plus"], indent=1))
```

## Appendix B — clean-room wrapper and real-bundle command

```python
# cleanroom_greedy_plus.py — the method file handed to benchmarks/dng100/cleanroom/run_method.py
import sys
import brainir.methods.greedy_plus  # noqa: F401  (registers the method)
from brainir.discovery.run import main
if __name__ == "__main__":
    sys.exit(main(["--method", "greedy_plus", *sys.argv[1:]]))
```

```
uv run --no-sync python -c "import brainir.methods.greedy_plus; from brainir.discovery.run import main; main(['--method', 'greedy_plus', '--bundle', 'benchmarks/dng100/public_blind', '--network', 'manc_v1.2.1', '--out', 'pred.json', '--budget', '1000', '--seed', '0'])"
```
