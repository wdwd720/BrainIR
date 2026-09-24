# Review B — optimisation: search, objective and budget of BrainIR v1

Independent reviewer B (optimisation), oracle-free, 2026-09-23 22:00 to 2026-09-24 10:45. I worked only in `C:\Dev\BrainIR_p2clean`
and in my own scratch folder (`<session scratchpad>\review_B_opt\`). Every experiment used synthetic instances I generated myself (truth
known only to me) or ran oracle-free on the public blind bundle. I modified no repository code; this file is the only file I wrote in the
clean room.

**Question.** Is v1's search and objective correct and efficient, and would a simpler algorithm do equally well?

**What I reviewed.** The method changed twice while I worked (§0). This review is about **the final v1.1, `brainir_v1.py` sha256
`94ea1f8e…`**, the code that `BRAINIR_V1_METHOD.md` §7 declares frozen. I re-ran on a pinned copy of that file every measurement the
last change could affect. Problems I had found in the intermediate version and that the final code fixed are recorded in §7.2, with the
numbers that show the fixes work.

**Note added at 10:41.** At 10:38 `brainir_v1.py` changed again, to version 1.2.0 (sha256 `25494c8a…`), which starts implementing the
findings of a first draft of this review (it cites B1, B2 and B7). I have not reviewed 1.2.0; everything below is about `94ea1f8e`.

## Summary

- **The search is correct and efficient; keep it.** It consists of the exact restriction, the canonical relevance order and adaptive
  group elimination with sequential-majority decisions, and it is unchanged since v1.0 (identical calls and kept sets in all 126 paired
  runs of the three versions).
  - It returns the same core as a plain single deletion in the same order in 125 of 126 runs, with k(log2(n/k) + 2) decisions (median
    ratio 1.00, maximum 1.78): 2x fewer elimination calls than single deletion on small pools, 16x fewer on n = 500 pools.
  - Every core returned at 1,000 calls (612 runs over the three versions) was sufficient and causally 1-minimal on 16 fresh parameter
    draws.
  - No run of 4,620 exceeded its budget or let `BudgetExhausted` escape. Results are bit-identical across interpreters for v1.0 and
    the intermediate v1.1 (12/12 digests each); I did not re-run the digests on the final code (incomplete, §6).
- **The final v1.1 fixed the two largest problems I had measured in the intermediate v1.1** (§7.2).
  - The necessity screen is now selective: on n = 500 it costs 63 calls per run instead of 336, and at n = 3,000 102–114 calls instead
    of hitting its 400-call cap.
  - Paired selection keys now need a difference beyond the network's own noise band: instances whose core differs between node orders
    fell from 7 of 63 back to v1.0's 4 of 63 (the redundant oscillators with two identical copies, documented failure mode 1).
- **One major problem remains (B2).** On the real MANC network, which of two valid mechanisms is returned is decided by one reliance
  test at posterior 0.954 against the 0.95 threshold — a t test on a statistic dominated by pass/fail outcomes. Rerun with `decisive` =
  0.975, the same run returns the other mechanism. The MANC core has changed with every version, each time decided by a statistic
  within 0.03 of its threshold, while the probabilities give the other mechanism 4.6 %. Testing the failures as paired counts, as the
  code already does for sufficiency, would decide it robustly (P = 0.984).
- **Cost.** The final v1.1 costs 39 [32, 47] more calls per run than v1.0 on my suite (median 129 vs 100; n = 500: 239 vs 148) for the
  same structural, causal and success_intact results and planted success +0.048 [−0.016, +0.127]. On the real networks it needs 2.7–3.1x
  v1.0's CPU (MANC: 26 minutes of wall time under load, against the contract's 30). The elimination is 12–14 % of the calls; enumerating
  alternatives (20–42 %), the screen (12–26 % of calls, 35–71 % of CPU at scale) and the necessity tests take most of the rest (B3–B5).
- **Would a simpler algorithm do as well?**
  - At 1,000 calls: greedy_plus matches the final v1.1 on structural, causal, planted and success_intact (all differences ≤ 0.008) with
    40 [34, 46] fewer calls per run, but is less consistent across node orders and seeds. Pipelines without a necessity screen (v1-lean,
    single deletion) lose success_intact (0.889 vs 0.984): they miss context members the intact network needs.
  - At 50–100 calls the final v1.1 is the best or tied arm: causal success +0.103 [+0.024, +0.190] over greedy_plus at 50 calls and
    +0.16 to +0.29 over single deletion, tied with group_probe; the same core in both node orders for 92–94 % of the instances, against
    70–75 % for greedy_plus.
- **Incomplete (time box).** On the final code I did not re-run the determinism digests or the budget sweep, and the two efficiency
  fixes were measured on one instance of the intermediate code only. Every place this matters says so.
- **Findings: 0 blockers, 1 major (B2), 8 minor (B1, B3–B9).** Verdict (§10): keep the search and the final code's structure; fix B2 (or
  report the MANC choice as a tie) before the lock; record the code hash in every result (B1).

## 0. What was reviewed — the method changed during this review

| time | clean-room state | my evidence on it |
|---|---|---|
| assigned (2026-09-23) | v1.0: `brainir_v1.py` 1,479 lines (I did not hash it); `BRAINIR_V1_METHOD.md` of 21:56 | 1,229 runs (1,000 / 100 / 50 calls, lean and node-order variants, baselines), determinism 12/12 |
| 2026-09-24 01:02 | library extended (graded rates, `SimQuery.remove_edges`, new scorer fields); `SELECTION_PROTOCOL.md` §8 | v1.0 determinism re-run under the new library: identical cores and calls in 12 of 12 cases |
| 01:15–01:58 | `brainir_v1.py` rewritten; at 01:58 sha256 `05876be0…`, 2,063 lines — **v1.1-intermediate** | pinned copy at 02:06; 2,582 runs (1,000 calls, 50/100 calls, 987 hyper-parameter runs, 216-run budget sweep, n = 3,000, real bundle), determinism 12/12 |
| 06:14 | sha256 `94ea1f8e…`, 2,203 lines, still `version = "1.1"` — **v1.1-final** | pinned copy at 08:16; 783 runs (1,000 calls in both orders, real bundle including `decisive` = 0.975 on MANC, n = 3,000, 50/100 calls, 399 hyper-parameter runs); no determinism digests or budget sweep (incomplete) |
| 08:08 and 09:40 | `BRAINIR_V1_METHOD.md` rewritten for v1.1 (§7 declares `94ea1f8e` frozen); seven placeholders at 08:08, filled at 09:40 | 08:08 version read in full; the sections filled at 09:40 read |
| 10:38 | `brainir_v1.py` version 1.2.0, sha256 `25494c8a…` (responds to this review's first draft) | not reviewed |

- **Unchanged since v1.0** (evidence from all versions pooled): restriction, relevance order, `eliminate`, `Prober.decide`, the pooled
  necessity test, the enumeration of alternatives, the seed layout, the phase reserves.
- **Changed in the final code** (re-measured on `94ea1f8e`): the screen's gate flag and singles cap, the noise band and sequential
  extension of the paired selection keys, the winner's validation size, the lazy certificate, the selection fallback.
- Line numbers refer to `94ea1f8e` unless stated otherwise.

## 1. Setup

**Instances (mine; truth generated and kept in my scratch folder).**
- `suite`: the spec structure of `brainir.discovery.synthetic.default_specs()` with every seed shifted by 27,000,000 (the composer used
  13,000,000; the salted suites use offsets below 1,000,000).
  - Simulation-verified with up to 4 re-draws, two node orders (`main`, `order1`), audited with `suite_audit` for unplanted sufficient
    sets.
  - 56 of 61 small/medium specs verified: 47 small (n = 50–60) and 9 medium (n = 500). The audit found 36 unplanted sufficient sets in
    10 instances.
- `suite_extra`: 7 more hard cases (backup copy + hub distractors at n = 60 for five families; weight-jittered hub instances at n = 150).
- `suite_large`: the default large specs (n = 3,000) with my offset; 3 of 5 verified (E–I pair, ring, two implementations).
- The main comparisons use 63 instances x 2 node orders, seed 0 (v1.0 and greedy_plus also seed 1).

**Arms.** Every run went through the frozen scorer `brainir.discovery.tournament.run_one` (truth guard active, score seeds 5000–5003):
- `v1.0`, `v1.1-intermediate` (`05876be0`), `v1.1-final` (`94ea1f8e`): `brainir_v1` at its default configuration, each version loaded
  from a pinned copy of the package through `PYTHONPATH`.
- `v1.0-lean` / `v1.1-lean`: the same code with every component beyond the canonical elimination switched off by configuration
  (v1.0: `max_alternatives=0, necessity_screen=False, member_essentiality=False, robust_objective=False, reliance_tiebreak=False`;
  v1.1 additionally `union_repair`, `degeneracy_detection`, `joint_necessity`, `simulate_edge_predictions`, `necessity_of_alternatives`
  off). Both keep restriction, canonical order, group elimination, validation, certificate and final fidelity. I did not re-run the lean
  arm on the final code: it switches off every component the final change touched.
- `greedy_plus`, `group_probe`: their defaults (unchanged during the review).
- `sde`: my plain single-deletion elimination (appendix A.1): v1's working replicates, exact zero-call restriction and verified
  activity filter, then one-at-a-time deletion (sequential strict majority of 3, no extension) in v1's canonical order (`sde:relevance`)
  or in node order (`sde:position`), repeated until a pass removes nothing; nothing else.
- **Population check.** Every returned core was evaluated on 16 independent parameter draws (5000–5015), outside the method's range:
  keep-only pass fraction π̂ of the core and of the core minus each member, and single silencing in the intact network of every member
  that keep-only does not need.

Budgets: 1,000 (main), 50 and 100, a sweep from 1 to 500 calls. At most two of my worker processes ran at any time; wall times include
contention with the other reviewers' and the composer's jobs, so call counts and CPU seconds are the cleaner cost measures.

## 2. Stopping rule and guarantees (question 1)

**What the elimination guarantees.** `eliminate` (lines 446–537) and `Prober.decide` (lines 271–330) are unchanged since v1.0: the
elimination made exactly the same calls and kept exactly the same set in all 126 seed-0 runs of v1.0, v1.1-intermediate and v1.1-final.

Let D(S) be v1's verdict on a kept set S: a sequential strict majority over the working replicates (the first 3 parameter draws on which
the intact network passes). A 2–1 split is re-decided over 5 replicates.
- **Start.** Under the model, keep-only of the structurally possible set equals the intact network, so D(K0) passes.
- **Each step.** Every accepted removal keeps D = pass. Bisection infers necessity from the failed parent without an extra call.
- **Stop.** The queue is empty and a full leave-one-out round removes nothing (lines 511–528, at most 3 rounds, line 1014).

The returned set M1 is therefore **1-minimal with respect to D**, i.e. with respect to 3 (at most 5) fixed parameter draws, not with
respect to the population pass rate. Generalisation rests on two later steps, both sequential in v1.1: the fresh-seed validation
(lines 828–868; conditional on the intact network passing, at least 3 and at most 12 replicates, decisive at a Beta posterior of 0.95)
and the paired certificate (lines 1720–1766; working seeds, then intact-passing validation seeds one at a time, up to 12).

For a set whose per-replicate pass probability is p, P(D passes) = p² + 2p³(1−p)(3−2p) (checked by enumeration): 0.18 at p = 0.3, 0.50
at 0.5 and 0.82 at 0.7, between a majority of 3 and a majority of 5. The expected cost is 2 + 5p(1−p) ≤ 3.25 calls.

The complexity claim holds: the elimination's decisions divided by k(log2(n/k) + 2) have median 1.00 (90th percentile 1.16, maximum
1.78) over 486 runs; median pool n = 10 on small graphs and n = 314 on medium graphs.

**Measured at 1,000 calls (population check on 16 fresh draws).**

| version | runs | insufficient (π̂ < 0.5) | π̂ < 0.8 | keep-only non-minimal | not causally minimal |
|---|---|---|---|---|---|
| v1.0 | 252 | 0 | 0 | 20 (all winner-take-all context members) | 0 |
| v1.1-intermediate | 234 | 0 | 0 | 22 (context members) | 0 (the scorer's 4-seed check flags 1 run) |
| v1.1-final | 126 | 0 | 0 | 12 (context members) | 0 |

- **Components that never changed an answer on my suite:** the certificate removed nothing (612 runs, and 252 lean runs); add-back never
  triggered; the union repair was never adopted and degeneracy was never flagged (both v1.1 versions).
- **Caveat.** Most planted mechanisms here pass on almost every parameter draw, an easy regime for the guarantee; marginal mechanisms are
  where it would be tested (the document's adversarial suites cover them).

**Can v1 stop with a non-minimal or insufficient core?** Yes, in four identifiable ways; none occurred at 1,000 calls on my suite.
1. **Budget exhausted inside the elimination.** The current passing set, a verified superset, is returned and flagged
   `budget_exhausted` (lines 529–536). In the budget sweeps this happens below about 20 calls; the superset shrinks from 474 neurons at 1
   call to the core.
2. **The leave-one-out rounds are capped at 3** (line 1014) without a closing round (B8).
3. **Failed validation that add-back cannot repair.** Add-back needs more than 20 % of the budget left and fails if it re-finds the same
   set (lines 1023–1033). The final code then returns the best participating candidate flagged `undecided` or `no_validated_mechanism`.
4. **The certificate removes members on weak evidence** (line 1756): a removal needs only that the reduced set passes on at least half
   the replicates and that the member is not decisively needed (B8).

At low budgets the phases without a reserve (the screen, up to 40 % of the budget, and the enumeration) run before the certificate,
which is then skipped (B6); the returned core is still 1-minimal on the working replicates because the elimination's own rounds completed.

## 3. Budget use (question 2)

### 3.1 Allocation by phase (1,000 calls; mean calls per run and share)

| version, size | runs | calls | elimination | essentiality (+ of alternatives) | screen | alternatives | selection + reliance | certificate | final fidelity + curve | validation | edge predictions | other |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| v1.0 small | 216 | 105 | 18 (17 %) | 20 (19 %) | 6 (6 %) | 27 (26 %) | 12 (11 %) | 7 (7 %) | 8 (8 %) | 3 | – | 4 |
| v1.0 n = 500 | 36 | 198 | 39 (20 %) | 19 (10 %) | 6 (3 %) | 94 (47 %) | 15 (8 %) | 7 (3 %) | 10 (5 %) | 3 | – | 5 |
| v1.1-intermediate n = 500 | 18 | 546 | 39 (7 %) | 22 (4 %) | **336 (61 %)** | 81 (15 %) | 22 (4 %) | 5 (1 %) | 16 (3 %) | 8 (1 %) | 10 (2 %) | 7 |
| **v1.1-final small** | 108 | 136 | 18 (13 %) | 15 + 5 (15 %) | 17 (12 %) | 27 (20 %) | 13 (10 %) | 4 (3 %) | 15 (11 %) | 8 (6 %) | 9 (7 %) | 4 |
| **v1.1-final n = 500** | 18 | 281 | 39 (14 %) | 15 + 15 (10 %) | 63 (22 %) | 89 (32 %) | 17 (6 %) | 5 (2 %) | 16 (6 %) | 8 (3 %) | 9 (3 %) | 5 |
| **v1.1-final n = 3,000** | 3 | 336 | 44 (13 %) | 20 + 5 (8 %) | 110 (33 %) | 83 (25 %) | 24 (7 %) | 7 (2 %) | 16 (5 %) | 8 (2 %) | 11 (3 %) | 8 |
| **v1.1-final, real MANC (n = 4,604)** | 1 | 342 | 40 (12 %) | 18 + 4 (6 %) | 90 (26 %) | 84 (25 %) | 54 (16 %) | 9 (3 %) | 14 (4 %) | 8 (2 %) | 16 (5 %) | 5 |
| **v1.1-final, real MaleCNS (n = 4,309)** | 1 | 352 | 42 (12 %) | 18 + 22 (11 %) | 66 (19 %) | 98 (28 %) | 49 (14 %) | 8 (2 %) | 17 (5 %) | 8 (2 %) | 12 (3 %) | 12 |

**The search itself — the canonical group elimination — is 12–14 % of the final code's calls.** The enumeration of alternatives (20–32 %)
and the screen (12–33 %) are the largest phases, followed by the necessity tests, selection and reliance, final fidelity and edge
predictions.

- **The elimination is efficient.** Median pool n = 10 on small graphs and 314 on n = 500; about k(log2(n/k) + 2) decisions at 1.7–1.9
  calls each. My single-deletion baseline needs 39 elimination calls on small pools and 638 on n = 500 pools; v1 needs 18 and 39.
- **The final v1.1 costs more than v1.0 on almost every instance:** +39 calls per run (95 % CI [32, 47]; 124 of 126 runs dearer), median
  129 vs 100. On n = 500: median 239 vs 148 (+61 %).

**Real bundle** (public blind bundle, seed 0, 1,000 calls; my runs with two processes of mine in parallel and the composer's jobs on
the same machine):

| run | network | calls (primary + auxiliary) | primary CPU s | wall s | core |
|---|---|---|---|---|---|
| v1.0 as documented (old §12.5) | MANC | 226 + 140 | 355 | 571 | [1126, 1220, 2825, 2973] |
| v1.0 as documented (old §12.5) | MaleCNS | 232 + 17 | 339 | 366 | [653, 1052, 2152] |
| v1.1-intermediate | MANC | 374 + 16 | 1,176 | 1,213 | [2825, 2973, 3310] |
| v1.1-intermediate | MaleCNS | 432 + 16 | 1,461 | 1,500 | [653, 1052, 2948] |
| **v1.1-final** | MANC | 342 + 184 | 966 | 1,544 | [1126, 1220, 2825, 2973] |
| **v1.1-final** | MaleCNS | 352 + 17 | 1,047 | 1,089 | [653, 1052, 2152] |
| sde (canonical order) | MANC | 185 | 458 | 469 | [2825, 2973, 3310] |
| sde (canonical order) | MaleCNS | 253 | 705 | 721 | [653, 1052, 2152] |

- The final code needs 2.7–3.1x v1.0's primary CPU. 81 % of it goes to full-network simulations; the screen alone takes 35 % (MaleCNS)
  and 49 % (MANC), down from 66 % in the intermediate version.
- MANC's 184 auxiliary calls are the cross-connectome step: the transfer of the chosen 4-member core to MaleCNS did not verify, so the
  fallback discovery ran (in the MaleCNS run the transfer of its core verified after 17 calls and landed on MANC's canonical set
  [2825, 2973, 3310]). The contract asks for "under about 30 minutes per network on one CPU"; 26 minutes of wall time under load leaves
  little margin.
- Every returned core passes keep-only on 15–16 of 16 fresh draws and fails on every leave-one-out.

### 3.2 What each phase changes (1,000 calls)

| component | v1.0 (252 runs, seeds 0–1) | v1.1-final (126 runs, seed 0) |
|---|---|---|
| add-back | never triggered | never triggered |
| necessity screen: context members admitted | 20 runs (every winner-take-all run) | 14 runs: winner-take-all 10; `mem60_e902` 2 (the planted essential neuron, which is also sufficient alone and so becomes the core); `nfc500_d57` 2 (the same genuine context member in both orders) |
| alternatives found | 108 runs | 54 runs |
| selection returned a non-canonical candidate | 40 runs, all by Occam | 22 runs: Occam 14 (two implementations), fidelity 6 (feed-forward driver with hubs), minimality 2 (`mem60_e902`) |
| keys that never decided | validation margin, stress margin (0 of 157 comparisons) | stress (0 of 35 pairwise comparisons; 2.2 stress calls per run) |
| certificate removed a member | 0 | 0 |
| union repair / degeneracy | – | never adopted / never flagged |
| adaptive replication fired | 32 runs (mean 0.9 extensions per run) | identical elimination (0.6 per run in the intermediate records) |

### 3.3 Waste and worst cases (final code)

Calls that changed no returned core on my suite (B5):
1. **The pooled necessity test runs every replicate.** 508 of the 516 tests in my 126 final runs were unanimous (289 all pass, 219 all
   fail). Stopping each test as soon as its verdict is fixed would save at least 10.4 calls per run (median 10), about half of the
   essentiality calls (21.9 per run), without changing any verdict. (On the intermediate code a pinned run of this fix, `v11_f2`, saved 10 calls
    on `dio500_d53` with the same core.)
2. **Necessity tests of the alternatives' members re-test screened neurons:** 184 tests, none essential, every one of them already
   silenced alone or cleared in both partitions by the screen (5.4 / 14.6 calls per run on small / n = 500; 64–76 in `ff500_d56`).
3. **Replacement searches do not use the alternatives already found:** with a one-member canonical set the first search can re-derive
   a disjoint alternative found a moment earlier. (Measured on one instance only — `dio500_d53` on the intermediate code,
    where `v11_f1` saved nothing.)
4. **Stress probes** (4 per compared candidate, 2.2 calls per run) for a key that decided none of 35 comparisons.

**Worst cases on large graphs.**
- At n = 3,000 the verified activity filter leaves 1,541–1,606 active candidates (against 87–121 on the real networks). The final code
  needs 186–493 calls and 205–375 s there; its screen stays at 102–114 calls (no cap hit) but is 41–71 % of the CPU. The plain single
  deletion cannot finish (1,000 calls, supersets of 1,044–1,109 neurons).
- The heaviest item at n = 3,000 is the enumeration on the two-implementation instance: 208 of 493 calls.
- The real networks are the relevant worst case: 18–26 minutes per network under load (§3.1), inside the contract's 30 minutes but by
  a small margin on MANC (B3).

## 4. Hyper-parameter sensitivity (question 3)

Each default was changed alone to about 0.5x and about 1.5x (integers rounded; for posterior thresholds the tail mass 1 − p was
perturbed by ±50 %: `decisive` 0.95 → 0.90 / 0.975, `decisive_stress` 0.99 → 0.98 / 0.995). Instances: 10 small instances in both node
orders plus the n = 500 two-implementation instance (one order), 21 runs per configuration, chosen where tie-breaking and budget rules
matter (symmetric redundant pairs, redundant pair with a backup copy, two implementations, feed-forward driver with hubs, memory switch
with hubs, winner-take-all with a backup copy, controller with a backup copy, weak critical edge, ring with hubs, jittered E–I pair).

- **v1.1-intermediate, 23 defaults (987 runs): no perturbation changed any returned core** (0 of 966). Only the cost moved: decision
  replication `n_seeds_per_decision` 2 / 4 → 0.87 / 1.17 of the default calls; `validation_seeds` 0.96 / 1.09; `max_validation_seeds`
  0.93 / 1.08; `max_alternatives` 0.93 / 1.00; `max_fillers_per_member` 0.95 / 1.01; `necessity_screen_fraction` 0.97 / 1.00 (0.80 on
  the n = 500 instance); every other parameter 0.98–1.02.
- **v1.1-final, the 9 defaults whose role the final change touched** (`decisive`, `max_validation_seeds`, `validation_seeds`,
  `n_seeds_per_decision`, `max_decision_seeds`, `screen_singles_fraction`, `screen_min_singles`, `screen_singles_per_member`,
  `necessity_screen_fraction`; 378 perturbed runs): no perturbation changed a returned core (0 of 378), including `decisive` = 0.975 on `mem60_d25`/main: its
  fidelity exclusion (0.961 at n = 4) is extended to 5 replicates and holds at 0.988. The cost moved with decision replication
  (`n_seeds_per_decision` 0.85 / 1.18 of the default calls) and validation (`validation_seeds` 0.95 / 1.12,
  `max_validation_seeds` 0.98 / 1.03); the screen parameters moved the calls by at most 1 %.
- **Interpretation.** The search and the screen are insensitive to their constants. The selection is sensitive exactly where a paired
  posterior sits near the decisiveness threshold (the sequential extension protects a key that can still grow its sample, as on `mem60_d25`, but not one already at the 12-replicate cap; on the real MANC network 0.954, B2).

## 5. Simpler algorithms at matched budgets (question 4)

### 5.1 1,000 calls (63 instances x 2 node orders, seed 0)

| arm | runs | structural | planted | causal (scorer) | success_intact | instances whose core differs between node orders | calls median small / medium | calls mean | wall median small / medium (s) |
|---|---|---|---|---|---|---|---|---|---|
| **v1.1-final** | 126 | 0.984 | **0.984** | 1.000 | 0.984 | **4 / 63** | 109 / 239 | 157 | 6.6 / 53.3 |
| v1.1-intermediate | 126 | 0.984 | 0.984 | 0.992 | 0.984 | 7 / 63 | 124 / 499 | 206 | 8.0 / 120.1 |
| v1.0 | 126 | 1.000 | 0.937 | 1.000 | 0.984 | 4 / 63 | 96 / 148 | 118 | 6.0 / 35.6 |
| v1.0-lean | 126 | 0.984 | 0.841 | 1.000 | 0.889 | 4 / 63 | 41 / 62 | 47 | 3.1 / 7.3 |
| v1.1-intermediate-lean | 126 | 0.984 | 0.841 | 1.000 | 0.889 | 4 / 63 | 69 / 85 | 74 | 4.1 / 11.4 |
| sde (canonical order) | 126 | 0.984 | 0.841 | 1.000 | 0.889 | 5 / 63 | **27** / 640 | 129 | **1.9** / 145.9 |
| sde (node order) | 126 | 0.968 | 0.833 | 0.992 | 0.889 | 19 / 63 | 27 / 636 | 129 | 2.2 / 100.1 |
| greedy_plus | 126 | 0.992 | 0.976 | 1.000 | **0.992** | 7 / 63 (16 / 63 over two seeds) | 83 / 192 | 117 | 5.8 / 50.7 |
| group_probe | 126 | 0.992 | 0.937 | 0.929 | 0.992 | 7 / 63 | 86 / 229 | 122 | 7.3 / 80.9 |

Paired differences (cluster bootstrap over instances, 95 % CI):

| comparison | planted | causal | success_intact | calls per run | same core in both node orders |
|---|---|---|---|---|---|
| v1.1-final − greedy_plus | +0.008 [−0.024, +0.048] | 0 | −0.008 [−0.024, 0] | **+40 [34, 46]** | +0.048 [−0.032, +0.127] |
| v1.1-final − v1.0 | +0.048 [−0.016, +0.127] | 0 | 0 [−0.048, +0.048] | **+39 [32, 47]** | 0 |
| v1.1-final − v1.1-intermediate | 0 | +0.008 | 0 | **−49 [−73, −28]** | +0.048 [0, +0.111] |
| v1.1-final − group_probe | +0.048 [−0.016, +0.111] | **+0.071 [+0.024, +0.135]** | −0.008 [−0.048, +0.024] | +35 [18, 53] | +0.048 [−0.032, +0.127] |
| v1.1-final − v1.1-lean | **+0.143 [+0.063, +0.238]** | 0 | **+0.095 [+0.032, +0.175]** | +82 [61, 106] | 0 |
| v1.0 − greedy_plus (2 seeds x 2 orders, small graphs) | −0.040 [−0.103, +0.008] | 0 | – | +1 [−5, +7] | **+0.185 [+0.093, +0.296]** (identical in all 4 runs) |
| v1.0-lean − sde (canonical order) | 0 (identical core in 125 of 126 runs) | 0 | 0 | **−82 [−135, −34]** | 0 |
| sde canonical − sde node order | +0.008 | +0.008 | 0 | 0 | **+0.222 [+0.095, +0.349]** |

Planted success by family (seed 0; the other six families are 1.00 in every arm):

| family | v1.0 | v1.1-intermediate and final | v1.1-lean, sde | greedy_plus | group_probe |
|---|---|---|---|---|---|
| feed-forward driver (hub distractors) | 0.40 | **1.00** | 0.40 | 0.80 | 0.50 |
| memory switch | **1.00** | 0.88 | 0.75 | 0.94 | 1.00 |
| negative-feedback controller | 0.83 | 1.00 | 1.00 | 1.00 | 0.75 |
| winner-take-all | 1.00 | 1.00 | **0.00** | 1.00 | 1.00 |

### 5.2 50 and 100 calls (63 instances x 2 node orders, seed 0)

| arm | budget | structural | planted | causal (scorer) | success_intact | same core in both node orders | calls median |
|---|---|---|---|---|---|---|---|
| **v1.1-final** | 50 | 0.98 | 0.94 | **0.92** | **0.976** | **0.92** | 50 |
| greedy_plus | 50 | 0.96 | 0.91 | 0.82 | 0.897 | 0.70 | 44 |
| group_probe | 50 | 0.99 | 0.89 | 0.90 | 0.944 | 0.89 | 47 |
| sde (canonical order) | 50 | 1.00* | 0.92 | 0.63 | 0.762 | 0.78 | 29 |
| **v1.1-final** | 100 | 0.98 | 0.94 | **0.98** | 0.984 | **0.94** | 99 |
| greedy_plus | 100 | 0.94 | 0.90 | 0.95 | 0.937 | 0.75 | 50 |
| group_probe | 100 | 0.99 | 0.94 | 0.94 | **0.992** | 0.90 | 82 |
| sde (canonical order) | 100 | 0.98* | 0.86 | 0.83 | 0.730 | 0.76 | 29 |

\* Single deletion cannot finish on n = 500 pools at 50–100 calls: it returns supersets of 268–292 neurons, which count as structural
successes under the scorer's definition but have no causal success.

The final and the intermediate v1.1 give the same success in all 252 low-budget runs (the changed phases barely run at these budgets;
the final code spends 7 fewer calls at 100). Paired v1.1-final − X (95 % CI):

| comparison | budget | causal | same core in both node orders |
|---|---|---|---|
| v1.1-final − greedy_plus | 50 | **+0.103 [+0.024, +0.190]** | **+0.222 [+0.095, +0.349]** |
| v1.1-final − greedy_plus | 100 | +0.032 [−0.024, +0.079] | **+0.190 [+0.079, +0.317]** |
| v1.1-final − group_probe | 50 / 100 | +0.024 / +0.048 (both CIs include 0) | +0.032 / +0.032 (both CIs include 0) |
| v1.1-final − sde | 50 | **+0.286 [+0.175, +0.397]** | **+0.143 [+0.048, +0.238]** |
| v1.1-final − sde | 100 | **+0.159 [+0.063, +0.270]** | **+0.175 [+0.079, +0.270]** |

On n = 500 at 50 calls group_probe is better than v1.1 (causal 0.89 vs 0.67, 18 runs each): v1's minimality rounds and finishing phases
compete for the last calls there (B6).

### 5.3 Does the added machinery earn its calls? (final code)

| component | calls per run (small / n = 500) | what it buys on my suite | verdict |
|---|---|---|---|
| exact restriction + verified activity filter | 0–1 decision | removes a median 33 of about 45 candidates (small), about 160 silent neurons (n = 500), about 1,400 (n = 3,000), 4,000–4,400 of the real networks' 4,178–4,459 candidates | earns |
| canonical relevance order | 0 | node-order consistency: single deletion in canonical vs node order +0.222 [+0.095, +0.349]; v1.0 vs greedy_plus over 2 seeds x 2 orders +0.185 [+0.093, +0.296] | earns |
| adaptive group elimination | 18 / 39 | the same core as single deletion in 125 of 126 runs with 2x / 16x fewer elimination calls; decisive at 50–100 calls | earns |
| adaptive replication | 0.6–0.9 extensions per run | no ±50 % change of `max_decision_seeds` changed a core | cheap; unproven on this suite |
| sequential validation, add-back | 8 / 8 | the admissibility gate; add-back never triggered | cheap insurance |
| pooled necessity (members, isolates, alternatives' members) | 21 / 29 | essential claims (accuracy 1.00); measured necessity as a hard constraint (`mem60_e902`) | needed; can stop sequentially (B5) |
| necessity screen | 17 / 63 (102–114 at n = 3,000; 66–90 on the real networks) | the context members that make success_intact +0.095 [+0.032, +0.175] over the lean pipeline | earns on my suite; its CPU at scale is the cost (B3) |
| alternatives + selection + reliance | 41 / 106 | planted +0.143 [+0.063, +0.238] over lean (Occam between implementations, fidelity in the feed-forward family), no change in structural or causal success; decides the MANC core | partly: family-dependent (B4), decided on a threshold (B2) |
| certificate, final fidelity + curve, edge predictions | 28 / 31 | evidence and reporting the contract and reviews A and G ask for; never changed a core | required |
| stress probes | 2.2 (mean over all runs; used in 34 of 126) | decided 0 of 35 comparisons | does not earn (B5) |

**Answer to question 4.**
- At 1,000 calls **greedy_plus alone does as well** on every success measure of my suite (planted +0.008, success_intact −0.008,
  causal 0) with 40 [34, 46] fewer calls per run. v1's advantage there is consistency — the same core in both node orders and across
  seeds — which comes from the canonical order at zero calls.
- A **lean v1 or a plain single deletion in canonical order** is as good on structural and causal success at 27–70 calls, but loses
  success_intact (−0.095) and planted success (−0.143): the screen and the enumeration with selection earn those.
- At **50–100 calls** v1 is the best or tied arm: better than greedy_plus and single deletion, tied with group_probe (which is better on
  n = 500 at 50 calls).
- The machinery does not earn its calls in the stress probes, the full-length necessity tests (B5) and, at scale, the full-protocol
  screen (B3).

## 6. Determinism and budget exhaustion (question 5)

**Determinism.** No version has a random number generator outside the `use_structural_prior=False` ablation; the seed only selects a
block of parameter replicates. I compared full-result digests between two interpreters (`PYTHONHASHSEED` 1 and 987). The digest covers
the core, probabilities, roles, essential claims, alternatives, fidelity, budget counters and every diagnostic except timings. Twelve
cases per version, including three budget-limited runs (37, 61 and 90 calls) and an n = 500 instance: **v1.0 12/12 identical,
v1.1-intermediate 12/12, v1.1-final not re-run (incomplete: the final code's new loops are deterministic by construction — no random number generator, fixed seed offsets — but I did not verify it with digests).** The seed-to-block map has period 16 (B7).

**Budget exhaustion.**
- No run of 4,620 exceeded its budget, `BudgetExhausted` never escaped `discover`, and no run raised an error. Every finishing phase
  is guarded (lines 96–105: exhaustion ends the phase; any other exception is recorded in `diagnostics["errors"]`, which stayed empty in
  every final run), and the elimination returns its current passing set.
- Intermediate sweep (8 instances x 27 budgets from 1 to 500 calls, 216 runs): below about 20 calls the result is a verified superset
  (474 neurons at 1 call on n = 500), flagged `budget_exhausted` and counted as a structural success by the scorer. Final sweep (the same
  8 instances x 14 budgets from 1 to 300, 112 runs): not re-run (incomplete); the final code's 252 runs at 50 and 100 calls all stayed within budget, with no escaped exception and no error.
- The returned mechanism depends on the budget, because the alternatives and the selection run only once enough calls are left (B6).
- The final code's new sequential loops handle exhaustion by construction: the noise band and the fresh certificate seeds catch
  `_OutOfBudget` (lines 899–935, 1729–1735), and reliance is measured replicate-major so that an exhausted budget leaves equal-length
  paired lists (lines 1537–1576).

## 7. Findings

Severity: **blocker** — must be fixed before the lock; **major** — fix before the freeze, or record it as an accepted limitation with
this evidence; **minor** — improve when convenient. Every finding in §7.1 applies to the final code (`94ea1f8e`). Findings I had
made on v1.0 or on the intermediate v1.1 that no longer apply are listed briefly in §7.2.

### 7.1 Open findings

### B1 — minor — The code does not identify its own version, and the target changed twice during the review

- **Evidence.**
  - `brainir_v1.py` was replaced at 01:15–01:58 (sha256 `05876be0…`) and again at 06:14 (`94ea1f8e…`). Every v1.1 variant, including
    the development versions the document lists in §12.6 (v11a–v11g, final), says `version = "1.1"` (line 643), and nothing in a result
    or its diagnostics records which file produced it; a run record can be traced to its code only through external hashes.
  - `BRAINIR_V1_METHOD.md` was rewritten twice during the review: at 08:08 with seven unfilled placeholders, complete at 09:40. It cites
    two different v1.0 hashes without saying whether they differ in behaviour: "the reviewed v1.0 code `9ca36c4d`" (§12.2, §12.6) and
    "the frozen v1.0 records (`final5_*`, code `3a07cf80`)" (§12.4).
  - §12.9 describes the MANC decision as "paired over 5 replicates"; the run extended that comparison to 12 replicates (diagnostics
    `sequential_extensions`: reliance to 9, then to 12), and the 0.954 is the posterior on 12.
  - No reviewer was told that the code changed; reviews run on different versions cannot be compared without this.
- **Fix.**
  - Record the sha256 of the method file in `diagnostics` (and in `run_record`), and bump the version string on every behavioural
    change (1.1.0, 1.1.1, …).
  - State how `9ca36c4d` and `3a07cf80` differ; correct §12.9.
  - Announce code changes to the reviewers with the new hash.

### B2 — major — On the real MANC network, which of two valid mechanisms is returned is decided at the threshold (posterior 0.954 against 0.95) by a t test that does not suit the statistic, and a ±50 % change of `decisive` flips the answer

- **Mechanism** (`select`, lines 1398–1521; `compare`, lines 1578–1599). Admissible candidates first pass the fidelity filter, then meet
  pairwise on reliance — a paired t-posterior that the mean difference of per-member reliance exceeds the noise band, decisive at
  `decisive` = 0.95 — then Occam (fewer members). A decided comparison leaves the loser `1 − confidence` of its weight.
- **Evidence (public blind bundle, MANC, seed 0, 1,000 calls).**
  - Two admissible candidates: the canonical 1-minimal set [2825, 2973, 3310] and the replacement [1126, 1220, 2825, 2973]. Both
    validated on 12 of 12 replicates; on 16 fresh draws both are sufficient (keep-only 15/16 and 16/16) and 1-minimal (every
    leave-one-out 0/16).
  - Fidelity: difference 0.157, inside the noise band 0.213 (posterior 0.109 after two sequential extensions to 12 replicates) — a tie.
  - Reliance, replacement minus canonical, per replicate (12 after two extensions): 0.74, 0.71, 0.08, 0.16, 0.18, 0.73, 0.12, 0.76,
    0.11, 0.11, 0.13, 0.81; band 0.213. The statistic is bimodal: on 5 replicates silencing {1126, 1220} breaks the function (≈ 0.75),
    on the other 7 it changes the readout by less than the band; silencing {3310} never breaks it. The t model gives P(mean > band) =
    **0.9539**, so the 4-member set wins and the canonical set keeps 4.6 % of its weight.
  - **Rerun with `decisive` = 0.975** (the tail mass halved, inside the ±50 % range of question 3; everything else identical): the same
    reliance values, the same band, 0.9539 < 0.975 → no decision → Occam → **the canonical set [2825, 2973, 3310] is returned** (352 + 16
    calls).
  - The MANC answer has changed with every version, each time decided by one statistic within 0.03 of its threshold: v1.0 [1126, 1220,
    2825, 2973] (reliance with fixed margins), intermediate [2825, 2973, 3310] (the replacement excluded by fidelity at 0.977, n = 4),
    final [1126, 1220, 2825, 2973] (reliance at 0.954).
  - The choice also drives the cross-connectome step: at 0.95 the transfer of the 4-member set to MaleCNS does not verify, and the
    fallback discovery costs 184 auxiliary calls and 566 s of wall time (no identity claim); at 0.975 the transfer verifies in 16
    calls. The final MaleCNS run's own verified transfer lands on MANC's canonical set [2825, 2973, 3310].
  - The same kind of decision on my suite: `mem60_d25`/main excludes the planted latch by fidelity at 0.961 on n = 4 (order1: 0.989).
    With `decisive` = 0.975 that comparison is extended to 5 replicates and the exclusion holds at 0.988
    (§4): the sequential extension protects a key below the cap; the MANC comparison was already at 12.
  - MaleCNS is not affected: the canonical set [653, 1052, 2152] wins there whether the reliance comparison decides (0.975) or Occam
    does, and the tied set [653, 1052, 2948] shares the probability mass.
- **Why this matters.** The substance of the decision is defensible — the intact network needs {1126, 1220} on some draws and 3310 on
  almost none (silencing 3310 alone passes on 15 of 16 fresh draws) — but the method reports it as a 0.95 / 0.04 split while the
  answer moves with its own tuning constant. A t model on a mixture of pass/fail outcomes and small readout changes is the wrong tool at
  n = 12: the mean is carried by the 5 failing replicates.
- **Fix.**
  - Preferred: test the two parts of reliance separately — the function failures as paired discordant counts, with the rule the code
    already uses for sufficiency (`paired_validation`; here 5 against 0 discordant replicates, P = 0.984, still decisive at 0.975), and
    the readout change with the paired test against the band.
  - Whatever the test, do not treat a posterior within a small margin of `decisive` as decisive: extend to the cap and, if it is still
    within the margin, call it a tie that shares the probability mass.
  - Before the lock, rerun the real bundle with `decisive` 0.90 and 0.975 and report every core that changes as tied, or record this
    evidence as an accepted limitation.

### B3 — minor — Full-network CPU dominates the final code at scale, and the screen is its largest part

- **Evidence (final code).**
  - n = 3,000 (main order, seed 0): 186 / 328 / 493 calls and 205 / 310 / 375 s for the E–I pair, ring and two-implementation
    instances, against greedy_plus's 120 / 246 / 415 calls and 87 / 159 / 258 s. The screen costs 102–114 calls (the 40 % cap is no
    longer reached) but 41–71 % of the CPU (52 % over the three runs); it found nothing on these instances.
  - Real networks: primary CPU 966 s (MANC) and 1,047 s (MaleCNS), 2.7–3.1x v1.0's; 81 % of it in full-network simulations, 35–49 % in
    the screen, which found nothing on either network. MANC took 26 minutes of wall time (under load) including 184 auxiliary calls,
    against the contract's "under about 30 minutes per network on one CPU".
  - On my plain suite the screen's finds are the winner-take-all context members (every run), the planted essential neuron of
    `mem60_e902` and the context member of `nfc500_d57`; the document's ablations (§12.3) show the single silencing is what finds masked
    gates. The screen earns a place; its price at scale is the issue.
- **Fix.**
  - Run the screen's singles and group tests with shorter simulations, as the contract allows for screening ("You may use shorter
    simulations for screening, but validate final claims under the bundle's protocol"), and confirm every isolate with the pooled test
    under the bundle's protocol.
  - Rank the flagged gates by how strongly their release would drive the mechanism and silence only the strongest (the economy the
    document's §12.4 names and leaves out of v1.1).
  - Report the per-phase CPU seconds in `diagnostics` (the prober already knows the phase), so the 30-minute guidance can be checked on
    every run.

### B4 — minor — The choice among sufficient sets is a family-dependent heuristic, and enumerating alternatives is the largest phase

- **Evidence.**
  - Which sufficient set is returned is decided by the selection rule, and the rule changed between versions (§5.1, planted success by
    family): feed-forward driver with hubs 0.40 (v1.0, Occam) → 1.00 (v1.1, fidelity first); memory switch with hubs 1.00 → 0.88. In
    `mem60_d25` the final code returns the canonical 2-hub pair (not the planted latch, not an audited alternative) because the latch's
    keep-only readout is further from the intact network's (mismatch 0.176 vs 0.126, n = 4). The document records this as failure mode
    3.
  - Enumeration of alternatives is the final code's largest phase: 20 % of the calls on small graphs, 32 % on n = 500, 25–28 % on the
    real networks, 42 % (208 calls) on the n = 3,000 two-implementation instance. It is what buys planted success over the lean
    pipeline (+0.143 [+0.063, +0.238]) — mostly by Occam between two implementations and by fidelity in the feed-forward family — with
    no change in structural or causal success on my suite.
  - Worst case, `ff500_d56` (both orders): 321–336 of 541–566 calls in the enumeration and 64–76 more in necessity tests of the
    alternatives' members. The enumeration found the planted chain (which then won by fidelity), a single hub, and an 8–10-member set that
    was never validated (failed in one node order, undecided in the other).
- **Fix.**
  - State in `BRAINIR_V1_METHOD.md` §2 that the choice among equally sufficient 1-minimal sets is a heuristic (fidelity, reliance,
    Occam) with no success guarantee, and report such runs with the tied candidates (the probability model already has them).
  - Seed each replacement search with the fillers already found for that member's slot (`v11_f1`, appendix A), and abort a disjoint
    elimination once it has isolated more necessary members than a few times the largest candidate found so far (report the residual
    pool as a large alternative that was not minimised).

### B5 — minor — Calls that changed no returned core on my suite (every version)

- **Evidence (final code, 126 runs at 1,000 calls).**
  - **The pooled necessity test runs every replicate** (`necessity`, lines 790–815: "Every working replicate is run (no early stop)"),
    for every canonical member, screen isolate and member of an alternative: 4.1 tests and 21.9 essentiality calls per run. 508 of 516
    tests were unanimous; a sequential stop would save at least 10.4 calls per run (median 10) with identical verdicts. (On the intermediate code a pinned run of this fix, `v11_f2`, saved 10 calls
    on `dio500_d53` with the same core.) The price
    is a weaker posterior on essential claims: 4/4 failures give `p_ess` = 0.969 instead of 0.992 for 6/6.
  - **Replacement searches ignore the alternatives already found** (`alternatives`, lines 1367–1392): each search for a non-essential
    member p starts from K0 − {p} with the other canonical members protected. When the canonical set has one member nothing is
    protected, and the first search can re-derive a disjoint alternative found a moment earlier (it is not recorded again, but its
    elimination is paid). (Measured on one instance only — `dio500_d53` on the intermediate code,
    where `v11_f1` saved nothing.)
  - **Necessity tests of the alternatives' members re-test screened neurons:** 184 such tests in my 126 runs (5.4 / 14.6 calls per run on
    small / n = 500 graphs; 64–76 in `ff500_d56`), none essential. Every one of these neurons had already been silenced alone as a
    screen single (126) or cleared in both screen partitions (58).
  - **Stress probes never decide.** 4 probes per compared candidate (2.2 calls per run, 34 of 126 runs) for a key that decided none of 35
    pairwise comparisons; it is decisive only at 4/4 against 0/4.
- **Fix.**
  - Stop the pooled test once its verdict cannot change (`v11_f2`, appendix A); if the stronger posterior of the full test is wanted,
    run the remaining replicates only for neurons whose `p_ess` is reported as an essential claim.
  - Seed each replacement search with the fillers already found for that slot (`v11_f1`).
  - Run the pooled test for an alternative's member only if the screen neither silenced it alone with a clean pass nor cleared it in
    both partitions.
  - Run stress probes only when two candidates of equal size are still tied after reliance.

### B6 — minor — At low budgets the answer depends on the budget, and the certificate and the alternatives are starved first

- **Evidence.**
  - Intermediate sweep (8 instances x 27 budgets): "minimality" (the certificate) is among the out-of-budget phases at 40–200 calls on 4
    of 8 instances, and the alternatives are starved up to 200–300 calls, because they reserve half of the remaining calls plus their
    evaluation reserve. The returned mechanism changes with the budget: `ff60_d16` returns a single hub (unplanted, audited) at 25–200
    calls and the planted chain from 300; `two50_d12` the ring at 30–200 and the E–I pair from 300; `wta50_d27` the winner alone at
    20–30 and the planted pair from 35.
  - Final code: the budget sweep was not re-run (incomplete).
  - Final code at 50 and 100 calls: the same structural, planted and causal success as the intermediate code in all 252
    runs; on n = 500 at 50 calls its causal success is 0.67 against group_probe's 0.89 (18 runs each), because the minimality
    rounds and the finishing phases compete for the last calls.
- **Fix.**
  - Reserve the certificate's calls before the screen and the enumeration run: the certificate is evidence about the returned core,
    the others are selection among alternatives.
  - Record in the result that the budget decided which sufficient set was returned (e.g. `diagnostics["budget_limited_phases"]` next to
    the core), so a low-budget answer is not read as the method's preferred mechanism.

### B7 — minor — The seed-to-replicate map has period 16 (every version)

- **Evidence.** `block = (seed mod 16) x 300` (line 748; the document's §4 "Seeds"). Seeds s and s + 16 produce bit-identical runs
  (same digest), and joint's seeds use `seed mod 4`. A reliability sweep with more than 16 seeds would count duplicated runs as
  agreement.
- **Fix.** Refuse or warn on seed ≥ 16 in sweeps, or derive the block from a hash of the seed within the admissible range and record a
  warning when two sweep seeds map to one block.

### B8 — minor — Two minimality steps end without a closing check (every version)

- **Evidence.**
  - The elimination's leave-one-out rounds are capped at 3 (`minimality_rounds = 3`, line 1014) and the loop exits after round 3 even
    when that round removed a member (lines 511–528); the `necessary` records of the other members are then stale. It needs three
    successive non-monotone removals; never observed.
  - The certificate removes a member when the paired posterior of "needed" is below 0.95 and the reduced set passes on at least half of
    the replicates (line 1756). The reduced core then carries only that ≥ 1/2 evidence, not the decisive validation (posterior ≥ 0.95)
    that admitted the winner; e.g. 8 passes of 15 gives P(π > 1/2) ≈ 0.6. The certificate removed nothing in 612 runs on my suite.
- **Fix.** Loop the rounds until one removes nothing (bounded by |kept|), or flag `minimality_unverified` at the cap. After a certificate
  removal, validate the reduced core with the same sequential rule as every candidate, and fall back to the unreduced core if it is not
  decisively validated.

### B9 — minor — The selection is a sequential incumbent tournament with a non-transitive comparator, and reliance depends on the candidate set (every version)

- **Evidence.**
  - Lines 1494–1499: a challenger that beats the current incumbent replaces it without being compared with the candidates the
    incumbent displaced. The keys are of different kinds (reliance, Occam, stress), so the comparator need not be transitive and the
    winner can depend on the order of the candidate list.
  - Lines 1500–1508 then file every other candidate as a loser (the winner decisively better) or as *tied* — including a candidate that
    decisively beats the winner (`compare` returns −1), which should instead reopen the selection.
  - Reliance uses each candidate's members outside the intersection of *all* compared candidates (line 1527 and 1534), so adding an
    unrelated candidate changes the A-versus-B comparison.
  - Not observed on my suite (no run returned a candidate that was tied with the canonical one while another candidate decided it).
- **Fix.** Return the candidate that no other candidate beats decisively (prefer the canonical one among those; fall back to it on a
  cycle). Compute reliance pairwise on each pair's own distinctive members.

### 7.2 Findings that no longer apply (fixed in v1.1; record them, do not reintroduce)

F-a to F-c are problems I found on the intermediate v1.1 (`05876be0`) and had drafted as major findings; the final code changed exactly
these parts (document §12.6, rows v11d–final), and my re-runs on `94ea1f8e` show that the changes work on my suite. F-d lists the v1.0
problems that v1.1 fixed.

**F-a. The necessity screen was not selective (intermediate: 61 % of the calls on n = 500).**
- Intermediate (lines 1132–1251 of `05876be0`): every active inhibitory candidate with an edge onto the canonical set *or onto any
  intact-silent neuron with a path to the readout* was silenced alone, plus the top 25 % of the pool (at least 8). On n = 500 graphs that
  flagged 116 of ~314 pool neurons (median) and cost 336 calls per run (61 % of the run); on the real networks 58 of 84 and 72 of 118
  candidates, 146 and 184 calls, 66 % of the CPU. It found no context member on the real networks.
- Final (lines 1182–1235): a gate is flagged only if it holds down a silent neuron that acts directly on the mechanism or the readout
  (mean-input test from public model parameters, no calls), and the relevance singles are capped at max(4, min(15 %, 4 per canonical
  member)). Same instances, seed 0, both orders:

  | n = 500 (18 runs) | flagged (median) | singles (median) | screen calls (mean) | run calls (mean / median) | wall (median) |
  |---|---|---|---|---|---|
  | intermediate `05876be0` | 116 | 162 | 336 | 546 / 499 | 120 s |
  | final `94ea1f8e` | 16 | 24 | 63 | 281 / 239 | 53 s |
  | v1.0 | – | – | 6 | 194 / 148 | 36 s |

  On small graphs the screen costs 17 calls (intermediate 21). The final screen still finds every winner-take-all context member and,
  on `nfc500_d57`, the same genuine context member in both node orders (silencing it alone passes on 3 and 2 of 16 fresh draws; the
  intermediate had admitted a different set of background inhibitors in each order, one of which failed the scorer's own silencing
  check). success_intact is unchanged (0.984).

**F-b. Paired selection keys decided between equally valid mechanisms from 4–5 replicates without a noise band (intermediate: 7 of 63
instances returned different cores in the two node orders).**
- Intermediate: the fidelity key excluded a candidate at a paired t-posterior ≥ 0.95 on n = 4 common replicates, reliance decided on the
  5 working replicates, with no minimum effect size. `two500_d55` returned the ring in one order (the E–I pair excluded at 0.978, n = 4)
  and the E–I pair in the other (reliance 0.975, n = 5); `two60_d13` likewise (reliance 0.988 vs fidelity 0.995); the real MaleCNS core
  was decided by a fidelity exclusion at 0.967.
- Final: both keys test the paired difference against the network's own between-draw noise band (`noise_band`, lines 914–935; a
  difference inside it is a tie), and an undecided comparison gets 4 more common replicates at a time up to 12 (lines 1452–1483,
  1537–1569).
- Instances whose core differs between node orders (seed 0): **v1.0 4/63, intermediate 7/63, final 4/63** — the same four exactly
  symmetric redundant oscillators as v1.0 (documented failure mode 1). The final code returns the same core as the intermediate in 122
  of 126 runs; the four changes are `nfc500_d57` (both orders, F-a) and `two500_d55`/main and `two60_d13`/order1, which now agree with
  their other node order.

**F-c. A lone candidate was validated to the cap.** The intermediate validated the winner on 12 replicates even without a competitor;
the final code does so only when the intact network itself failed on some draw (lines 1510–1519). Validation sizes in the final runs:
4 replicates for 160 candidates, 7–8 for 17, 12 for 31.

**F-d. Issues of v1.0 that v1.1 fixed.**
- Validation counted a fresh replicate as a pass even when the intact network failed on it (v1.0 lines 848–858); v1.1 conditions on
  the intact network (lines 828–868).
- The fresh validation seeds were reused for add-back, selection, the certificate and the necessity test, then reported as fidelity;
  v1.1 reserves offsets 200–229 for the final fidelity.
- The size–error curve's "why" text described a rule the code did not apply (v1.0 line 1277); it is now generated from the selection
  record (lines 1853–1880).

## 8. Files read

In `C:\Dev\BrainIR_p2clean` only:
- `CLAUDE.md`, `README.md`; `research/phase2/COMPOSER_CONTRACT.md`; `research/phase2/SELECTION_PROTOCOL.md` (including §7 and §8);
  `research/phase2/BRAINIR_V1_METHOD.md`: the v1.0 version (2026-09-23 21:56) and the v1.1 version (2026-09-24 08:08) in full, and the
  sections the 09:40 revision filled in (§12.4–§12.10);
  `research/phase2/selection_results/*.md`; `research/phase2/methods_review.md` §1.
- `src/brainir/methods/brainir_v1.py`: v1.0 (1,479 lines) and v1.1-intermediate `05876be0` in full; v1.1-final `94ea1f8e` through its
  complete diff against `05876be0` plus `_Run.__init__`, `necessity`, `execute` (validation, add-back, phase reserves), `select`,
  `reliance`, `compare`, `alternatives`, `certify`, `eliminate` and `guarded`. (Version 1.2.0 of 10:38: only its diff header, to identify it.)
- `tests/test_method_brainir_v1.py` (v1.0 version).
- `src/brainir/methods/greedy_plus.py`, `group_probe.py`, `__init__.py`.
- `src/brainir/discovery/`: `simulator.py`, `interventions.py`, `criteria.py`, `interface.py`, `guard.py`, `problem.py`, `run.py`,
  `synthetic.py`, `synthetic_pairs.py`, `suite_audit.py`, `tournament.py` (and their 01:02 additions); `src/brainir/sim/model.py` (parts).
- `data/synthetic/dev_v1/build_suite.py` (template for my suite builder).
- The public blind bundle only through `DiscoveryProblem.from_bundle` in my oracle-free runs (network sizes, model configuration).
- Not read: reviews A, E and G and the adversarial-suite description (file names only).

In the session scratchpad only my own folder `review_B_opt\` (scripts, pinned copies `snap_v11\` and `snap_v12\` with per-file sha256,
my suites and truth, results).

## 9. Reproduction

From `C:\Dev\BrainIR_p2clean`, with `RB` = my scratch folder and `PYTHONPATH=%RB%\snap_v12` (final code; `snap_v11` for the intermediate
version, nothing for v1.0-era records):
```
uv run --no-sync python %RB%\rb_build.py --root suite --max-n 600 --workers 2          # my suite (+ suite_extra, suite_large)
uv run --no-sync python %RB%\rb_run.py --campaign v12main --workers 2                  # 1,000 calls, both orders, seed 0
uv run --no-sync python %RB%\rb_run.py --campaign v12low --workers 2                   # 50 / 100 calls
uv run --no-sync python %RB%\rb_run.py --campaign v12large --workers 2                 # n = 3,000
uv run --no-sync python %RB%\rb_run.py --campaign v12hyper --workers 2                 # +-50 % of 9 defaults
uv run --no-sync python %RB%\rb_real.py --method v1_timed --network manc_v1.2.1 --tag v12 [--config "{\"decisive\": 0.975}"]
# defined but not run on the final code (incomplete): --campaign v12sweep, v12fixes; rb_determinism.py --tag v12a / v12b
uv run --no-sync python %RB%\rb_analyze.py results/main1000.jsonl results/v11main.jsonl results/v12main.jsonl --seeds 0 --pairs v1:v12,greedy_plus:default
uv run --no-sync python %RB%\rb_v12cmp.py | rb_intact.py | rb_v11diag.py results/v12main.jsonl --label v12 | rb_hyper_analyze.py results/v12hyper.jsonl
uv run --no-sync python %RB%\rb_real_show.py v12 v12_dec0975
```
Campaign definitions are in `rb_run.py` and `rb_v11.py`; every record carries the instance, node order, seed, budget, calls, the scorer's
metrics, the method's diagnostics and the 16-draw population check.

### 9.1 Scratch code (not part of the repository)

**A.1 Plain single-deletion elimination (`rb_sde.py`, registered as `sde` inside the harness process only).** It reuses v1's public
helpers for the replicates, the exact restriction and the canonical key; nothing else.

```python
U = frozenset(problem.candidate_positions())
pr = v1.Prober(problem, sim, U, base_seed=(seed % 16) * 300 + 17, max_seed_trials=10)
pr.collect_working(3); seeds = tuple(pr.working[:3])
K, dropped = v1.structural_candidates(problem)                              # exact, zero calls
silent = {p for p in K if p not in union(active_positions of the intact runs on seeds)}
if silent and pr.decide(K - silent, seeds).passed: K = K - silent           # verified activity filter (one decision)
order = v1.canonical_order(K, key)        # "relevance": v1's (log relevance, weighted degree) key; "position": sorted(K)
kept = K
for _ in range(3):                         # passes until nothing is removed
    removed = False
    for v in order:
        if v in kept and pr.decide(kept - {v}, seeds).passed:   # sequential strict majority of 3, no extension
            kept, removed = kept - {v}, True
    if not removed: break
return kept                               # the current passing set if the budget runs out
```

**A.2 Fix variants (`rb_v11fix.py`; subclasses of `_Run`, registered under new names in the harness process; the repository is
untouched; run on one instance of the intermediate code only).**
- `v11_f2`: `necessity(x)` pools exactly as v1.1 does (every working replicate, a split extended to 5, then up to 3 fresh replicates on
  which the intact network passes) but stops as soon as the verdict cannot change: essential once 2·n_fail > n + r_left, not essential
  once 2·n_fail + r_left ≤ n (r_left = fresh replicates still to come). Verdicts are identical by construction; `p_ess` is computed on
  fewer replicates.
- `v11_f1`: before a member's replacement search, count the alternatives already found that avoid the member as fillers of its slot,
  exclude their non-canonical members from the search start, and run only `max_fillers_per_member − (known fillers)` searches.
- (`v11_f3`, a leaner gate flag for the intermediate screen, is superseded by the final code's own rule and was not re-run.)

**A.3 Harness.** `rb_run.py` wraps `tournament.run_one` without changing it; it only raises the diagnostic size limit of
`compact_result` and adds the 16-draw population check through a `CausalEffectCache` store (which saves compute and never touches a
method's budget). `rb_determinism.py` hashes the full `DiscoveryResult.to_dict()` without timing fields. Each code version runs from a
pinned copy of the package (`snap_v11\`, `snap_v12\`, with `SHA256SUMS.txt`) through `PYTHONPATH`, so edits in the clean room cannot mix
versions.

## 10. Verdict

- **Search: correct, efficient, keep.** The canonical group elimination gives the same answer as plain single deletion at 2–16x fewer
  calls, is bit-identical given the seed, is stable across node orders up to exact symmetry, and never broke a budget in 4,620 runs.
  At 50–100 calls it is the best or tied search in this comparison.
- **Objective: sound as a filter, heuristic as a chooser.** Admissibility (validated, participating, containing every neuron measured
  essential) is well founded, and the final code enforces it at a reasonable cost. Choosing among several admissible 1-minimal sets
  (fidelity, reliance, Occam) is a heuristic; its decisions must not be reported with more confidence than the statistics carry. On the
  real MANC network they are (B2).
- **Efficiency: acceptable for the lock, with clear savings left.** The final code fixed the intermediate version's two expensive
  problems (§7.2). It still costs about 1.3x v1.0's calls on my suite and about 3x its CPU on the real networks; B3–B5 list savings:
  a sequential stop of the necessity test and stress probes only for equal-size ties cannot change the returned core (by
  construction; stress decided nothing on my suite); shorter screening simulations, skipping re-tests of screened neurons and seeded
  replacement searches need a check before adoption.
- **Simpler algorithms.** greedy_plus alone matches v1's success at 1,000 calls with fewer calls. v1's advantages are consistency (the
  canonical order, no randomness), low budgets, and success_intact over lean pipelines (the screen). That is enough to prefer v1, and not
  enough to justify its cost in every phase.
- **Before the lock:** fix B2 — test the failure part of reliance as paired counts (decisive at 0.984 on MANC) and do not treat a
  posterior within a small margin of `decisive` as decisive — or at least rerun the real bundle with `decisive` 0.90 and 0.975, report
  every core that changes as tied, and record this as an accepted limitation. Record the
  code hash in every result and correct §12.9 of the document (B1). The other minor findings can follow.

**Verdict: accept the final v1.1 (`94ea1f8e`) for the lock once B2 is fixed or recorded as an accepted limitation; there is no
blocker.**
