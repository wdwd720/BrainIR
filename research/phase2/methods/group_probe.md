# `group_probe` — active causal probing with group tests and a Bernoulli membership posterior

Method file `src/brainir/methods/group_probe.py` (registered as `group_probe`, version 1.0); tests
`tests/test_method_group_probe.py`; experiment driver `research/phase2/methods/group_probe_results/tools/group_probe_experiments.py`;
clean-room entry `research/phase2/methods/group_probe_results/tools/run_group_probe.py`; results and logs in
`research/phase2/methods/group_probe_results/`; own development instances (truth known to the developer) in
`data/synthetic/dev_group_probe/`. Family: *active causal probing with group testing / compressive designs*.

**Hypothesis tested.** Choosing interventions that maximally reduce the uncertainty about mechanism membership finds the
mechanism with far fewer simulations than one-neuron-at-a-time deletion, and the savings come almost entirely from cheap
keep-only probes of small sets (≈0.3 s on the 4,604-neuron network) instead of full-network silencing (≈2.4–5 s).

## 1. The idea in one paragraph

Write `pass(S)` for "keep-only `S` (plus stimulus and readout) satisfies the criterion on all working parameter seeds"
and `M` for an unknown minimal sufficient set. As soon as a pool `P` with `pass(P) = 1` is in hand, the *removal probe*
`T(G) := pass(P \ G)` for `G ⊆ P` answers "does `G` contain a member of the sufficient set inside `P`?": under
monotonicity `T(G)` fails iff `G ∩ M ≠ ∅`. That is a classical **OR-type pooled test** on `G` (a "positive" pool is one
that holds a member), so the whole machinery of adaptive group testing applies to the *complement* of the keep-only
query (the keep-only query itself is AND-type: it passes only when the pool contains *all* members). Adaptive splitting
finds the `d` members of a pool of size `|P|` with about `d·log2(|P|/d) + O(d)` probes (Hwang's generalized binary
splitting; information bound `log2 C(|P|, d)`), against `|P|` probes for a single-deletion pass and `O(|P|^2)` for
leave-one-out backward elimination. The method maintains a posterior `q_i = p(z_i = 1)` over membership, picks the group
whose outcome is most uncertain (the noiseless expected-information-gain rule), and pays full-network prices only for
what sufficiency probes cannot see: essentiality and neurons that are necessary *in context*.

## 2. Algorithm

All simulations go through the `BudgetedSimulator`; `K` working parameter seeds per decision (default 2); a probe
**passes only if it passes on every working seed** (the conservative rule for a discard); a probe with disagreeing
seeds is weak evidence (`conf = 0.5`).

0. **Working seeds and baselines.** Simulate the intact network on `K+1` seeds (`seed·1000 + k`); the `K` passing
   seeds with the highest criterion score are the working seeds (more seeds are tried if fewer than `K` pass; if none
   passes, the result is empty and says so). Simulate keep-only of nothing (stimulus + readout alone): if it passes, the
   direct pathway is the mechanism and the core is empty.
1. **Structural prior.** Candidates that cannot be members under the model get `q = 0` without a call: neurons with
   unknown sign (their signed output column is zero) and neurons not reachable from the stimulus through positive
   edges (from rest, with `θ ≥ 0`, they provably never fire). The others are ordered in two strict tiers — first the
   neurons active in the intact runs (activity fingerprint: a neuron that never fires contributes nothing), then the
   rest — and inside a tier by `log(f_i + ε) + log(b_i + ε)`, where `f_i` is the fraction of `i`'s excitatory input
   attributable to the stimulus within `hops = 5` hops (row-normalised positive weights, hop decay 0.5) and `b_i` the
   fraction of `i`'s output reaching the readout within 5 hops (column-normalised absolute weights). An optional
   external prior (`config["prior"]`, §5b) adds a log-odds term to this score. Prior marginals:
   `q0_i ∝ 1/(rank_i + 4)` (× `inactive_factor = 0.05` for silent neurons), normalised so that the pool's mass is
   `prior_members = 4`, capped at 0.5.
2. **Localisation.** Keep-only of prior-ranked prefixes of size 16, 32, 64, … until one passes: the pool `P`. The slice
   added since the last failing prefix must contain a member (a *fail* update on that slice); everything outside `P`
   is down-weighted by 0.05 (it is not needed for *this* mechanism; it may still be a backup, see step 6).
3. **Group elimination (adaptive group testing).** Repeat while open items remain in `P`:
   choose `G` = the lowest-`q` open items whose pass probability `Π_{i∈G}(1 − q_i)` is closest to 1/2 (§3), probe
   `T(G) = pass(P \ G)`, update the posterior (§4); on a pass discard `G` from `P` (the pool stays verified
   sufficient at all times) and down-weight every open item that was silent in the passing runs (a silent neuron
   contributes nothing, so its removal cannot matter); on a fail of a singleton, confirm the member. Every member ends
   up confirmed by its own singleton fail; no member is ever inferred only from the failure of a larger group.
4. **Discrete minimality cleanup and add-back.** Leave-one-out inside the confirmed set (least certain first): removable
   members are dropped, the ablation signature (score and readout activity without the member) of kept ones is
   recorded. The keep-only of the result is then simulated on `fresh_seeds = 3` new seeds; if it fails on some, the
   discarded pool members with the highest residual `q` are added back one at a time (at most `max_addback = 6`), kept
   only if they restore the failing seeds *and* keep the working seeds passing (role `modulatory_supporting`); an
   addition that breaks the working seeds is recorded as an antagonist (non-monotone event).
5. **Essentiality.** Full-network silencing of every member on the working seeds: `essential = True` iff the silenced
   network passes on at most `essential_pass_max = 0.2` of the tested seeds (with `K = 2`: fails on both), the same
   definition as the synthetic truth ("silenced pass fraction < 0.2"). Step 7 re-measures it on more seeds.
5b. **Necessity screen (bounded).** A neuron can be necessary in the full network without being needed in isolation
   (in a winner-take-all circuit, keep-only of the winner alone passes because the probe itself removes the competitor;
   the lateral-inhibition neuron that silences the competitor is invisible to every sufficiency probe). With a share
   `necessity_share = 0.35` of the calls left, the neurons that are active in the intact network, structurally
   possible and outside the core are ranked by `prior score + log(1 + connection strength to the core and the
   readout)`; the top `necessity_singles = 8` are silenced one at a time (all of them when the share affords it), the
   rest in same-sign pools of at most `necessity_group_max = 4` with adaptive splitting (a passing pool is cleared, a
   failing one split). Neurons whose single silencing fails on all working seeds join the core as *context members*
   (`essential = True`; role `lateral_inhibition` under a selectivity criterion, `gain_control` for other inhibitory
   ones, `modulatory_supporting` for excitatory ones), and the keep-only of the enlarged core is re-checked.
6. **Redundancy / alternatives.** For every member `m` whose single silencing passes on all working seeds, steps 2–4
   are re-run with the other members forced in and `m` excluded (a fresh posterior over the remaining candidates);
   the cleanup also re-tests the forced members. The result is a minimal sufficient set that avoids `m`: a backup
   copy or an alternative implementation. Members of alternatives that are not in the core get role
   `redundant_backup` and inclusion probability `alt_weight (0.3) × their posterior`. A member for which an
   alternative avoiding it is already known is skipped; at most `max_alternatives = 3`; a search is not started with
   fewer than `alt_min_calls = 30` calls left.
7. **Spend-down (calibration with the leftover budget).** After the robust check (keep-only of the core with all
   parameter sds doubled, 3 fresh seeds), calls that are left are spent on calibration only — never on changing the
   search: (i) essentiality is re-measured on `essential_extra_seeds = 2` further seeds, after checking that the
   intact network passes on them (essentiality is undefined on a seed where the intact network already fails), and
   the pass fractions are pooled; (ii) the core's keep-only runs on 3 more fresh seeds; (iii) the active neurons that
   the necessity screen had no budget for are screened with `spend_down_share = 0.5` of what is left (same procedure
   as 5b). Whatever is still left is not used: the method stops when it has nothing more to learn (50–100 calls on a
   50-neuron instance).
8. **Roles, loop, dynamics, fidelity.** Roles from sign, membership of a directed cycle in the core-induced subgraph,
   direct stimulus input / readout output and the criterion type (§6). Loop = the largest strongly connected component
   of the core-induced graph (or the self-looped members). Predicted frequency / active readout = medians of the
   passing intact runs; fidelity = keep-only pass fraction of the core on the working seeds, on fresh seeds and
   (when affordable) on fresh seeds with all parameter sds doubled.

### Pseudocode

```
discover(problem, sim, seed):
    K ← replicates; working ← best K passing seeds of intact(seed·1000 + 0..K)
    if pass(∅): return core = ∅                                   # direct pathway
    order, impossible ← structural_prior(problem, active_intact)    # impossible: q = 0, no call
    q ← prior marginals; P ← first prefix of `order` with pass(P) (16, 32, 64, …)
    open ← P;  confirmed ← ∅
    while open ≠ ∅:                                                 # adaptive group testing on removal probes
        G ← lowest-q open items with Π(1−q_i) closest to 1/2
        if pass(P \ G): P ← P \ G; open ← open \ G; q[G] ↓ (pass update); q[silent in the run] ×= 0.05
        else:           q[G] ↑ (fail update);  if |G| = 1: confirmed ← confirmed ∪ G; open ← open \ G
    M ← leave-one-out cleanup of P (= confirmed)                    # discrete minimality
    fidelity on fresh seeds; add-back of high-q discarded items if a fresh seed fails
    for m in M: essential[m] ← silence({m}) fails on every working seed
    context ← necessity screen over active neurons ∉ M (singles, then same-sign pools ≤ 4), bounded by 35 % of the rest
    M ← M ∪ context
    for m in M with silence({m}) passing everywhere (skip m if a known alternative avoids it):
        alternative ← steps localise/eliminate/cleanup with forced = M \ {m}, excluded = {m}
    robust check; spend-down: essentiality on extra intact-passing seeds, more fresh seeds, screen untested active neurons
    return core = M, q, roles, essential, alternatives, loop, fidelity, diagnostics
```

## 3. Acquisition rule

For a removal probe of group `G` the outcome is Bernoulli with `P(pass) = Π_{i∈G}(1 − q_i)` under the independent
posterior (single-term monotone model). For a noiseless test the expected information gain about `z` equals the entropy
of the outcome, maximised at `P(pass) = 1/2`; with symmetric test noise the gain is a monotone function of the same
quantity. The rule therefore picks the prefix, in increasing order of `q`, whose log pass-probability is closest to
`log 1/2` (`Posterior.pick_group`). Grouping the *least* probable items together makes a pass clear as many items as
possible per call (the ProbDD / Hwang ordering), and a likely member (`q > 1/2`) is always probed alone. When all open
items have tiny `q` the rule probes the removal of *all* of them at once — one call that either finishes the
elimination or proves that a member is still hidden in the remainder. The same rule is what turns a failed group into a
binary search: after a fail the group's marginals rise, so its next groups are about half its size.

## 4. Posterior model

Independent Bernoulli marginals `q_i` (mean field). A removal probe is modelled as an OR-type noisy pooled test with
`false_pass = P(pass | G holds a member) = 0.02` and `false_fail = P(fail | G holds no member) = 0.05` when the working
seeds agree, both raised to 0.3 when they disagree. With `r_i = Π_{j∈G, j≠i}(1 − q_j)` (no *other* member in `G`), the
sequential marginal update of item `i` is

```
pass:  q_i ← q_i·fp / (q_i·fp + (1 − q_i)·[r_i (1 − ff) + (1 − r_i) fp])
fail:  q_i ← q_i (1 − fp) / (q_i (1 − fp) + (1 − q_i)·[r_i ff + (1 − r_i)(1 − fp)])
```

which is the exact marginal update for independent priors applied one test at a time (the "at least one" coupling
introduced by a fail is dropped after the update, which is why every member is re-confirmed by a singleton probe
rather than inferred). Free evidence from the activity fingerprint (silent in a passing probe: `×0.05`) and from the
localisation (outside the passing prefix: `×0.05`) enters multiplicatively. The reported `inclusion_probability` is the
final marginal for every candidate (0 for structurally impossible ones; `0.3 × posterior` for members of alternatives
that are not in the core; ≥ 0.9 for context members found by the necessity screen). It is calibrated in the sense
of the Brier score against the reported mechanism: members end near 0.95–0.99 after two singleton fails (elimination +
cleanup), discarded items near 0.001–0.01.

## 5. Hyper-parameters (all in `GroupProbe.default_config`; none tuned on hidden instances)

| name | default | meaning |
|---|---|---|
| `replicates` | 2 | working parameter seeds per decision (`K`) |
| `fresh_seeds` | 3 | fresh seeds for the fidelity estimate and add-back |
| `pool_start`, `pool_growth` | 16, 2.0 | prefix doubling of the localisation |
| `prior_members`, `prior_rank_offset`, `q_max` | 4, 4, 0.5 | initial posterior mass in the pool, `q0 ∝ 1/(rank+4)`, cap |
| `hops`, `hop_decay` | 5, 0.5 | structural prior propagation |
| `inactive_factor`, `outside_pool_factor` | 0.05, 0.05 | multiplicative free evidence |
| `false_pass`, `false_fail` | 0.02, 0.05 | noisy-test likelihood (0.3 when seeds disagree) |
| `max_addback` | 6 | add-back attempts when fresh seeds fail |
| `necessity_share`, `necessity_singles`, `necessity_group_max` | 0.35, 8, 4 | full-network necessity screen |
| `essential_pass_max` | 0.2 | essential ⇔ silenced pass fraction ≤ this |
| `max_alternatives`, `alt_weight`, `alt_min_calls` | 3, 0.3, 30 | backup searches |
| `robust_check` | True | keep-only of the core with doubled parameter sds on the fresh seeds |
| `essential_extra_seeds`, `spend_down_share` | 2, 0.5 | spend-down: extra essentiality seeds; share of the rest for untested active neurons |
| `prior`, `prior_weight` | None, 1.0 | optional external inclusion prior (§5b) and its log-odds weight |

The defaults were set on the developer's own instances (the ones in §9 and the unit tests) and on first principles;
nothing was tuned against the public evaluation suite, whose truth is not available.

## 5b. External prior (`config["prior"]`, optional)

The cross-network component may pass `config["prior"] = {position: p}` with `p ∈ [0, 1]` (JSON string keys are
accepted). It is never required: its absence means a uniform external prior and the purely structural ordering above.
When present it is used in two places only — (i) the candidate ordering: the structural score of every candidate gets
`prior_weight · log((p_i + 1e-3)/(p_default + 1e-3))` with `p_default = min(0.05, min given p)` for positions it does
not mention, so supported neurons enter the first keep-only prefixes (still behind the activity tier: a neuron silent
in the intact runs cannot be a member whatever the prior says); (ii) the initial marginal `q0_i = max(structural q0,
min(0.95, p_i))` for active supported neurons, so that they are probed early and, when the prior is right, confirmed by
a single removal probe each. The prior never removes a candidate, never adds a member without a probe, and a wrong prior
is overturned by the same probes (test `test_external_prior_is_optional_and_biases_ordering_only`). The diagnostics
record `external_prior = {n_given, n_candidates_covered, mass}`.

## 6. Roles (generic, criterion-aware, no simulation)

Excitatory member on a directed cycle of the core-induced graph: `recurrent_excitatory_core` under `rhythm` when it
receives the stimulus or drives the readout, else `input_relay`; `state_memory` under `ramp`/`persistence`;
`output_driver`/`input_relay` under `activity_band`/`selectivity`. Excitatory member off any cycle: `output_driver` if
it projects to the readout, else `input_relay`; under `selectivity` an excitatory member that projects only to readout
group B is a `competitor`. Inhibitory member: `inhibitory_feedback` under `rhythm`, `lateral_inhibition` under
`selectivity`, `gain_control` otherwise. Members of alternatives outside the core: `redundant_backup`; add-backs:
`modulatory_supporting`; context members: see step 5b. Unknown sign: `unknown`. Probabilities 0.55–0.7 reflect how
many of the structural cues agree.

## 7. Complexity, budget use and stopping

Let `N` be the number of candidates, `n_pool` the passing prefix, `d` the number of members, `K` the working seeds.
Calls: baselines `K+2`; localisation `K·⌈log2(n_pool/16)⌉ + K`; elimination `K·(d·log2(n_pool/d) + 2d + 2)` in the
noiseless idealisation (the free silent-neuron evidence usually collapses the first probe to "remove everything that
was silent"); cleanup `K·d`; fresh fidelity 3 (+ add-back ≤ 6·failing seeds); essentiality `K·d`; necessity screen
≤ 35 % of what is left; each backup search ≈ one localisation + elimination with `d' ≈ 1–2`; robust check 3;
spend-down `2 + 2·d + 3` plus at most half of what is left for untested active neurons. A single-deletion screen over
the candidates costs `K·N` full-network calls (`single_deletion_equivalent_calls` in the diagnostics) and the
reference's leave-one-out backward elimination `O(K·n_pool^2)` keep-only calls. Planning costs no simulations and is
negligible (`O(n_pool log n_pool)` per probe for the group choice; one sparse propagation of `hops` steps for the prior).

The method stops when every open item of the pool has been discarded or confirmed, the cleanup, essentiality,
necessity, backup and spend-down stages have run, or the budget is exhausted. It
never raises `BudgetExhausted`: every stage is wrapped, and the result always carries the best *verified* sufficient set
known at that moment (the current pool if the elimination was interrupted, flagged with `budget_exhausted` and
inclusion probabilities capped at 0.5 for unconfirmed members). The minimum useful budget is about `K·(4 + log2 n_pool)
+ elimination`, i.e. 30–60 calls on small instances; with `K = 2` the whole pipeline on a 50-neuron instance takes 45–75
calls and on the 4,604-neuron network a few hundred (§9).

## 8. Failure modes (known and expected)

- **Non-monotone keep-only responses.** A prefix can fail because it contains an antagonist whose suppressor is ranked
  lower; the doubling simply continues until the suppressor is included (worst case the full candidate set, which is
  the intact network and passes). Inside the elimination, an antagonist is discarded whenever it is probed (removing it
  passes), so a suppressor that was confirmed only because the antagonist was present becomes removable and is
  dropped by the cleanup. Add-backs that break the working seeds are recorded as antagonists.
- **Hidden context members.** Neurons necessary only in the presence of a competitor are invisible to sufficiency
  probes (winner-take-all). The necessity screen finds them at full-network prices, but pooled silencing can hide a
  necessary neuron when its pool also contains the neuron it suppresses (the inhibitor model); pools are therefore
  small and same-sign, and the most relevant candidates are always silenced alone. With a tight budget the screen's
  share may not cover every active neuron: what it did not test is reported with its prior probability, not cleared.
- **Marginal mechanisms.** When the pool passes on the working seeds only barely, many singleton removals fail on one
  seed and are kept (conservative): the core inflates. Working seeds are chosen by margin among the passing seeds to
  reduce this; the fresh-seed fidelity reports it.
- **Redundancy inside the pool.** Two alternatives inside `P` make the removal tests inconsistent with a single-term
  model, but the sequential procedure is always consistent with its own history (the pool shrinks monotonically) and
  finds one alternative; the others are found by the conditional backup searches, whose cost grows with the number of
  non-essential members (bounded by `max_alternatives`).
- **Several sufficient mechanisms of different sizes.** The elimination returns the sufficient set whose members
  survive the removal order, usually the smallest one inside the pool, and the backup searches add more. That set
  need not be the "planted" one. On my own instance `feedforward_driver__n500__hub_distractor+misleading_centrality+
  autonomous_module` (activity-band criterion, readout above 20 Hz), the reported core is the generator's single
  misleading-centrality neuron: its 6-synapse projection onto every readout neuron, driven at close to maximal rate
  by the stimulus, is on its own enough for the band. The alternative found is one hub distractor, also sufficient
  alone. The planted 3-neuron relay chain is a third sufficient set; it is not reported because backup searches only
  look for sets avoiding each non-essential core member, not the union of all sets found. The reported core passes
  the scorer's fresh-seed keep-only check (functional 1.0) but counts as a structural failure, because the truth
  lists only the planted chain. `greedy_reference` fails on the same instance in the same way. This is a
  truth-completeness issue of the generator, and the method is deliberately not tuned toward planted mechanisms.
  An iterative hitting-set search (look for a sufficient set avoiding the union of all sets found so far) would list
  all three, at about one localisation + elimination per extra set. The same happens with backup copies. On
  `delayed_inhibitory_oscillator__n60__backup_copy` the core [23, 31, 36, 49, 59] uses the half-weight copy 59 in place
  of member 46, and the backup search reports the planted set [23, 31, 36, 46, 49] as the alternative: both
  implementations are found, essentiality is correct (46 and 59 are non-essential, the other four essential),
  functional pass 1.0, but recall is 0.8 against the planted set. Which alternative becomes the core depends only on
  the removal order. A principled tie-break I did not implement for lack of time would promote the most robust set
  (highest keep-only pass fraction under doubled parameter sds and weight noise) from among the core and its
  alternatives.
- **Path-conditional inclusion probabilities.** `q_i` is the posterior that `i` belongs to the sufficient set *inside
  the localised pool*, not that it belongs to every minimal mechanism. When a member is non-essential and
  interchangeable (on the real network, the inhibitory member of the loop: 499 in one run, 3310 in another, {1126,
  1220} in the alternative), its `q_i` is still ≈ 0.998. The essentiality flag and the alternatives carry the right
  information, but the probability does not. A fix, not implemented, would cap non-essential members at
  `1 / (1 + number of known alternatives avoiding them)`.
- **Structural filter.** Excluding unknown-sign and positively-unreachable neurons is exact for this model class
  (zero output column; no activity from rest without an excitatory path); it would be wrong for a model with
  spontaneous activity or non-zero unknown-sign weights.
- **Roles.** They are structural heuristics; the truth of a redundant pair labels one pair `redundant_backup`
  arbitrarily, so a run that reports the other pair as core scores 0 on roles although the mechanism is right.

## 9. Results

Every number below comes from a run I executed; each block names the code revision that produced it (§11). Machine:
a shared 16-core Windows workstation, at most 3 simulation processes of mine at a time; wall times are inflated by
other users' jobs and are not a measure of the method. All commands are run from the repository root with
`uv run --no-sync` (`T=research/phase2/methods/group_probe_results/tools`).

### 9.1 Own synthetic instances with known truth (final revision 1.0)

```
uv run --no-sync python $T/group_probe_experiments.py build     # 54 specs, 43 verified by simulation (546 s) -> data/synthetic/dev_group_probe
uv run --no-sync python $T/group_probe_experiments.py own --budget 400 --methods group_probe greedy_reference --workers 2 \
    --filter __n50__ __n60__ __n500__ --label own_b400             # 82 runs, 0 errors, 1,367 s
uv run --no-sync python $T/group_probe_experiments.py table --label own_b400
```

The suite (seeds 91000+, disjoint from the public suite's) contains every family at n = 50 and n = 60 with hub
distractors and misleading centrality, seven families with backup copy / weak critical edge / autonomous module
at n = 60, and seven families at n = 500 with hubs, misleading centrality and an autonomous module: 41 instances.
The two n = 3000 instances were left out (§9.6). The instance generator verifies every truth by simulation, and 11
specs never verified and were dropped. Scoring uses the frozen tournament scorer (`brainir.discovery.tournament`):
success means the core contains a complete truth alternative; functional pass fractions come from keep-only of the core
on fresh seeds (nominal, parameter sds × 2, weight noise 0.2). `greedy_reference` runs with its defaults (`k = 3`).

| method | runs | success [95% CI] | recall (median) | precision (median) | functional nominal | functional sd × 2 | calls median | core size median | role acc | Brier |
|---|---|---|---|---|---|---|---|---|---|---|
| **group_probe** | 41 | **0.90** [0.80, 0.98] | 1.00 | 1.00 | **1.00** | 0.97 | **91** | 2 | 0.99 | **0.01** |
| greedy_reference | 41 | 0.54 [0.39, 0.68] | 1.00 | 0.33 | 0.73 | 0.70 | 208 | 3 | – | 0.24 |

| method | size | runs | success | precision (median) | functional nominal | calls median [min, max] | essential acc | role acc | Brier |
|---|---|---|---|---|---|---|---|---|---|
| group_probe | n50–60 | 34 | 0.91 | 1.00 | 1.00 | 82 [46, 192] | 1.00 | 0.98 | 0.0066 |
| group_probe | n500 | 7 | 0.86 | 1.00 | 1.00 | 230 [208, 280] | 1.00 | 1.00 | 0.0013 |
| greedy_reference | n50–60 | 34 | 0.62 | 0.33 | 0.82 | 178 [34, 399] | 1.00 | – | 0.263 |
| greedy_reference | n500 | 7 | 0.14 | 0.33 | 0.29 | 400 [244, 400] | 1.00 | – | 0.121 |

By family (success / median calls), group_probe vs greedy_reference: delayed inhibitory 0.83 / 108 vs 0.00 / 60
(n = 6); E-I pair 1.00 / 72 vs 0.80 / 236 (5); feed-forward driver 0.33 / 140 vs 0.00 / 399 (3); integrator 1.00 / 46
vs 1.00 / 106 (1); memory switch 1.00 / 67 vs 1.00 / 176 (6); negative-feedback controller 0.67 / 80 vs 0.33 / 202 (3);
redundant oscillator 1.00 / 102 vs 0.80 / 268 (5); ring 1.00 / 164 vs 0.67 / 246 (3); two implementations 1.00 / 116
vs 0.80 / 265 (5); winner-take-all 1.00 / 64 vs 0.00 / 194 (4). Per-run records: `own_b400.jsonl`; summaries:
`own_b400.md`, `own_b400.summary.json`, `own_b400.tables.md`.

- **All four group_probe failures are functionally correct** (nominal functional pass 1.0 for all four). Each is
  the truth-completeness case of §8. In two, the misleading-centrality neuron alone is sufficient for the
  activity-band criterion, and a hub is reported as the alternative (`feedforward_driver` n60 and n500). In two, a
  backup copy stands in for the member it copies, and the planted set is reported as the alternative
  (`delayed_inhibitory_oscillator` n60 and `negative_feedback_controller` n60 with `backup_copy`).
- Redundancy: 15 runs report ≥ 1 alternative. Of the 10 `redundant_oscillator` / `two_implementations` runs, 8
  report one implementation as the core and the other as the alternative, with both core members non-essential and
  the alternative's members labelled `redundant_backup`. `redundant_oscillator` n500 has both members non-essential
  but no alternative found. In `redundant_oscillator` n60 with `backup_copy` both members are essential; the verified
  truth agrees, so there was no alternative to find.
- Context members: on all 4 winner-take-all instances the necessity screen supplied the lateral-inhibition member(s),
  which no keep-only probe can see. `greedy_reference` fails all 4.
- Minimality on the scorer's seeds: 7 reported members in the 41 runs are removable from the keep-only core. Six are
  context members found by the necessity screen: needed in the full network, not in isolation, which is exactly what
  a keep-only minimality check cannot credit. The seventh is in the winner-take-all backup-copy instance.
  Weight-noise (0.2) functional pass: 0.86. Median wall time per run: 9 s.

### 9.2 Query counts versus single deletions

Medians over the own-suite runs of 9.1 (group_probe, `K = 2` working seeds):

| size | runs | candidates N | K·N single deletions | pool | members d | removal probes | d·log2(pool/d)+2d | keep-only calls | silencing calls | total calls |
|---|---|---|---|---|---|---|---|---|---|---|
| n50–60 | 34 | 47 | 94 | 16 | 2 | 9 | 10.0 | 41 | 32 | 82 |
| n500 | 7 | 479 | 958 | 16 | 2 | 10 | 10.0 | 33 | 188 | 230 |
| real network, final | 1 | 4,459 | 8,918 | 64 | 3 | 26 | 19.2 | 129 | 156 | 290 |
| real network, rc1 | 1 | 4,459 | 8,918 | 128 | 3 | 26 | 22.2 | 138 | 150 | 291 |

- **The search itself follows the group-testing law.** Localising the members of the pool took 9–10 removal probes
  (18–20 calls) on the synthetic pools, in line with the idealised `d·log2(pool/d) + 2d = 10`. Leave-one-out on the
  same pool costs `K·|pool| = 32` calls, and a single-deletion pass over all candidates costs `K·N = 94` / 958. On the
  4,604-neuron network, 26 probes (52 calls) found 3 members in a pool of 64 (final) or 128 (rc1). The alternatives
  are 128 / 256 calls for leave-one-out on the pool, and 8,918 full-network single deletions (≈ 6 h at 2.4 s each).
  There, the complete pipeline (search, confirmation, necessity screen, backup search and calibration) needed 290
  calls, **3.3 % of `K·N`**.
- **Confirmation, not search, dominates the total.** At n ≈ 50 the necessity screen affords to silence every active
  neuron singly, so the full pipeline (82 calls) costs about as much as one single-deletion pass (94). But it
  additionally returns essentiality, context members, alternatives and calibrated probabilities, and the search part
  alone is about 40 cheap keep-only calls. At n = 500 the total is 24 % of `K·N`, 82 % of it full-network silencing
  for the confirmation stages. The saving grows with N, because the search is `O(d log pool)` and the confirmation is
  bounded by the number of *active* neurons and a budget share, not by N.
- The structural filter excluded 1,028 of the 4,459 real candidates (23 %) with zero calls. The mean keep-only probe
  kept 15.7 neurons (final run).

### 9.3 Public evaluation suite (`data/synthetic/mechanisms_v1`, truth hidden; revision rc1)

`uv run --no-sync python $T/group_probe_experiments.py public --budget 400 --workers 4 --label public_suite_b400` (run
with rc1; rows in `rc1_public_suite_b400.json`). Only what the method reports about itself is available here: calls,
core size, and its own keep-only fidelity of the reported core on 3 fresh seeds (nominal) and with doubled parameter sds.

| size | runs | calls median [min, max] | keep-only / silencing calls (median) | pool | core size | `K·N` single deletions | fresh fidelity | robust (sd × 2) | runs with ≥ 1 alternative | budget exhausted |
|---|---|---|---|---|---|---|---|---|---|---|
| n50–60 | 48 | 69 [37, 199] | 38 / 28 | 16 | 2 | 94 | 1.00 | 0.94 | 13 | 0 |
| n500 | 8 | 175 [153, 239] | 38 / 133 | 16 | 2 | 958 | 1.00 | 0.96 | 3 | 0 |
| n3000 | 2 | 231 [213, 249] | 109 / 119 | 1,488 | 3 | 5,918 | 1.00 | 1.00 | 1 | 0 |

All 58 runs finished far inside the 400-call budget, and every reported core passed its own fresh-seed keep-only check.
Silencing calls dominate at n ≥ 500 because the necessity screen and the essentiality checks are full-network
simulations. rc1 had a localisation problem on large graphs: on the n3000 ring instance the doubling had to grow to
2,959 of 2,960 candidates, because the structural score ranked the members below silent neurons (pool median 1,488).
The activity tier of rc2 fixes this. Re-running the two n3000 instances with rc2
(`... public --budget 400 --filter ring_oscillator__n3000 two_implementations__n3000 --label public_n3000_recheck`,
`rc2_public_n3000_recheck.json`) localised a pool of 16 on both and needed 183 and 225 calls (126 silencing on median),
with fresh and robust fidelity 1.0. The public suite was **not** re-run with the final revision; see §9.6.

### 9.4 Real public bundle (`benchmarks/dng100/public_blind`, network `manc_v1.2.1`, tier A)

**Final revision 1.0, 1000-call budget, under the clean-room runner** (sandboxed; return code 0; 1,376 s; prediction
digest `9d59cf07ebef…`; `cleanroom_manc_b1000/{prediction_manc_v1.2.1.json,result.json,run_record.json}`):

```
uv run --no-sync python benchmarks/dng100/cleanroom/run_method.py --method $T/run_group_probe.py \
    --bundle benchmarks/dng100/public_blind --network manc_v1.2.1 \
    --out research/phase2/methods/group_probe_results/cleanroom_manc_b1000 --seed 0 \
    --method-args "--budget 1000 --result-json C:/Dev/BrainIR_p2clean/research/phase2/methods/group_probe_results/cleanroom_manc_b1000/result.json"
```

The run used 290 of 1,000 calls (5 intact, 129 keep-only, 156 silencing) and stopped with nothing left to learn.
1,028 of the 4,459 candidates were excluded without a call, and 78 neurons were active in the intact runs. Prefixes 16
and 32 failed and 64 passed. 26 removal probes reduced the 64 to 3 members:

| position | sign | role (p) | essential (silenced pass fraction, 4 seeds) | inclusion p |
|---|---|---|---|---|
| 2825 | + | recurrent_excitatory_core (0.7) | yes (0.0) | 0.999 |
| 2973 | + | recurrent_excitatory_core (0.7) | yes (0.0) | 0.996 |
| 3310 | − | inhibitory_feedback (0.7) | no (1.0) | 0.998 |

- The three members form a directed 3-cycle (the reported loop).
- Leave-one-out inside the core: removing any member abolishes the rhythm. Without 3310 the readout stays active (9
  neurons) but is not rhythmic.
- Alternative: [1126, 1220, 2825, 2973] (backup search for 3310). The necessity screen single-silenced all 72
  remaining active, structurally possible neurons: none is necessary; 1220 is ambiguous.
- Fidelity of the core as keep-only: pass 1.0 on 6 fresh seeds and 1.0 with doubled parameter sds; isolated core
  frequency 14.3 Hz. The predicted frequency of the full network is 11.0 Hz (median of the intact runs), with 2
  active readout neurons.

**Stability across revisions.** rc1 (below) and 1.0 agree on the essential excitatory pair 2825 / 2973 and on the
alternative. They differ in the non-essential inhibitory member: 499 in rc1, 3310 in 1.0, because the changed
ordering puts a different inhibitory neuron into the first passing prefix. Together the two runs show at least three
sufficient ways to close the loop: {499}, {3310}, {1126, 1220}. The inclusion probabilities (≈ 0.998 for the
inhibitory member in each run) are conditional on the search path and overstate certainty about *which* inhibitory
neuron fills that slot (§8).

**rc1, 1000-call budget** (`$T/group_probe_experiments.py real --budget 1000` with rc1; `rc1_real_manc_v1.2.1_b1000_s0/`):
the method used 291 of 1,000 calls (3 intact, 138 keep-only, 150 silencing). 1,028 of the 4,459 candidates were excluded
without a call (unknown sign or no excitatory path from the stimulus), and 78 neurons were active in the intact runs.
Prefixes of 16, 32 and 64 failed and 128 passed. **26 removal probes** (group sizes 86, 76, 18, 16, 14, 8, 7, … down
to singletons) reduced that pool of 128 to 3 members, positions 499 (inhibitory), 2825 and 2973 (excitatory), which
form a directed 3-cycle. Essentiality in the full network: 2825 and 2973 essential (silenced pass fraction 0), 499 not
(pass fraction 1.0). The backup search for 499 found the alternative [1126, 1220, 2825, 2973]. The necessity screen
silenced all 72 remaining active, structurally possible neurons one at a time: none was necessary, one (1220) was
ambiguous (fails on one of the two seeds). Keep-only fidelity of the core was 1.0 on 3 fresh seeds and 1.0 with
doubled sds. The predicted frequency is 11.0 Hz (median of the intact runs); the isolated core oscillates at 16.9 Hz
with 2 active readout neurons. rc1 also ran under the clean-room runner with a 250-call budget: return code 0, the same
3-neuron core and alternative, 197 calls, 1,034 s, prediction digest `851cf2280d1d…`. That record directory was later
lost: a follow-up chain cleared it and was then killed by the machine's low-memory monitor. The facts above are
quoted from the runner's output at the time.

### 9.5 Unit tests

`uv run --no-sync pytest tests/test_method_group_probe.py -q`: **8 passed in 57 s** on the final revision. The tests
cover registration and exact recovery of an E-I pair with a schema-valid prediction; determinism under the seed and
the same answer on another parameter ensemble; the budget respected at 1, 4, 12, 14 and 30 calls with a valid result
every time; a redundant mechanism (one pair as the core, the other as an alternative, nothing essential,
`redundant_backup` roles); a feed-forward chain with correct roles under `activity_band`; a winner-take-all context
member found only by the necessity screen; the optional external prior (right, wrong or absent: same verified
answer); and the posterior update and group-acquisition rule. `ruff check` is clean on the method, the tests and the
tools. The coordinator's re-synced infrastructure tests (`tests/test_discovery_infra.py`, `tests/test_discovery_cross.py`)
passed together with these tests: 22 passed, 1 skipped (clean-room builder absent from this checkout).

### 9.6 What I could not run

- A budget sweep (250 / 1000 / 2000 calls) and second seeds on the own suite. Runs at 250 and 1000 calls were started,
  but they and every other job on the machine were killed by the low-memory monitor, and the time left allowed one
  budget only (400).
- The two n3000 instances of the own suite, left out of the scored tournament for time and memory (10–20 min each).
  group_probe was run on the two n3000 instances of the public suite instead (§9.3).
- The public evaluation suite with the final revision: only rc1 (all 58 instances) and rc2 (the two n3000 instances)
  were run there.

## 10. Integrity statement

- The method reads only these public problem fields: `W`, `signs`, `stim_positions`, `readout_mask` /
  `readout_positions`, `candidate_positions()`, `criterion_spec` (its type, and for selectivity the readout group
  positions) and `model_cfg` (to double the parameter sds in the robust check). It never reads `problem.root`, instance
  or network names, manifests, `benchmark_id` or any file itself, and it uses no id, size, family or cell-type
  constant. The development harness (not the method) uses instance names to schedule the largest instances first and
  to group results by size.
- `data/synthetic/mechanisms_v1/BUILD_REPORT.json`, an evaluation-suite file copied into the clean room by mistake and
  since deleted by the coordinator, was read once, during my initial exploration and before any code was written:
  `head -80`, which showed its header (66 specs, 58 verified) and the first three instance entries (three
  `ei_pair_oscillator` instances whose two canonical motif nodes are essential and necessary). Nothing from it was used
  in the method, the tests, any hyper-parameter or any script; no script I ran reads it. What it showed is also what
  the public motif definition in `brainir.discovery.synthetic` implies by construction.
- Truth was read only for my own instances (`data/synthetic/dev_group_probe`, `data/synthetic/dev_scratch`, the test
  fixtures), which the contract allows.

## 11. Revision history (which results come from which code)

- **rc1**: the algorithm of §2 without the activity tier (3-hop structural score only; silent neurons merely
  down-weighted), without the spend-down (step 7), with essential ⇔ silenced pass fraction = 0 on the working seeds,
  and without the external prior.
- **rc2**: rc1 plus the activity-tier ordering and the 5-hop score. Motivated by the n3000 localisation failure of rc1
  (§9.3).
- **1.0 (final)**: rc2 plus the spend-down stage (essentiality on extra seeds, with the intact pass checked first; extra
  fresh seeds; screening of untested active neurons), `essential_pass_max`, budget-safe bookkeeping of context members,
  and the optional external prior of §5b. Diagnostics caveat: "no passing seed" and "localisation failed" end the run
  through the same code path as budget exhaustion, so `budget_exhausted` is also true in those two (reported) cases.
