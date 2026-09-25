# PHASE 2 REPORT — Blind causal mechanism discovery v1

Status: **DRAFT (in progress).** Sections marked *pending* are filled when the corresponding step is complete; no number in
this report comes from the hidden oracle unless the section says so explicitly, and every hidden evaluation is listed in
`research/phase2/HIDDEN_EVAL_LOG.md`. Spec: `goal3.md`. Frozen benchmark: `dng100-benchmark-v1` (commit a7c0142, lock
`bcaa8ee46e23dc29…`), unchanged throughout (`benchmarks/dng100/freeze.py --check` green).

## 1. What Phase 2 set out to do

Build the first algorithm that receives only the public DNg100 benchmark evidence (tier A: signed synapse-count graph,
NT-derived signs, sizes, coarse annotations, stimulus, readout, the rate model) and independently discovers a compact,
causal mechanism, and test whether it improves on the frozen simulation-guided baseline `greedy_prune_sim` on
reliability, query efficiency, robustness, minimality, calibration and cross-connectome transfer — not merely on
exact-oracle recall (goal3 §§0, 32, 51).

## 2. How leakage was prevented (goal3 §4)

The orchestrating session had seen the answer during Phase 1. It therefore built only generic infrastructure and never
designed method logic. Method families were implemented by **fresh agents in an oracle-free clean directory**
(`C:\Dev\BrainIR_p2clean`: the library, the public bundles, the clean-room runner, public synthetic instances; no oracle,
no Phase 1 reports, no literature about the circuit). Feedback to developers was aggregate synthetic scores only.
BrainIR v1 was composed by another fresh agent in the same clean directory from aggregate selection results. The method
is locked (`research/phase2/METHOD_LOCK.json`, tag `brainir-v1-preblind`) before any hidden evaluation; hidden evaluations
are few and logged.

One integrity incident: the development suite's build report (which carries per-node essential flags of the development
instances) was copied into the clean room by mistake. Four developers disclosed a one-time glance at it during
exploration; none used it (each stated so; the code was reviewed). It was deleted, and **selection and confirmation use
new suites built afterwards with fresh secret salts and anonymised names that never entered the clean room**.

## 3. Infrastructure built (all generic; `src/brainir/discovery/`)

- `DiscoveryProblem` (bundle loader), `BudgetedSimulator` (hard call budget checked before every batch, in-run memo,
  optional persistent content-addressed `CausalEffectCache` whose hits are still charged, accounting of calls, simulated
  seconds, CPU seconds, distinct interventions and candidate mechanisms), criteria (rhythm, activity band, persistence,
  selectivity, ramp), interventions (silence, keep-only, weight noise, group designs), `DiscoveryResult` → frozen
  prediction schema (incl. cross-connectome claims), method registry, clean-room entry script.
- Synthetic mechanism suite generator (10 families × complications × sizes 50–3,000; simulation-verified truth stored
  apart; truth-completeness audit that records unplanted sufficient sets), synthetic cross-connectome pair generator
  (shared labelled anchors, noisy annotations, implementation shifts, anchor decoys).
- Tournament scorer (structural success vs planted and audited sufficient sets; pre-registered functional success =
  sufficient + 1-minimal under keep-only; clarified causal functional success = sufficient and every member keep-only-
  necessary or essential in the intact network; identity consistency across node orders and seeds; robustness under
  doubled parameter spread and weight noise; roles; essentiality; Brier), pair-tournament scorer, budget curves,
  anti-gaming transforms, node-order reliability sweeps on the real bundle (oracle-free), paired comparison, transfer
  experiments on the real networks, matched random nulls, ablation runner, method lock and blind-evaluation tooling.

## 4. Methods-only literature review

`research/phase2/methods_review.md`: 55 entries in 15 areas (group testing, adaptive/Bayesian experimental design,
cross-entropy/EDA, surrogate-assisted and Bayesian optimisation, evolutionary multi-objective search, sparse masks,
causal abstraction, redundancy/Rashomon sets, robust objectives/CVaR, racing, transfer and correspondence). Its synthesis
proposed the candidate families below.

## 5. Candidate algorithm families (tournament)

| family | method | core idea | developer document |
|---|---|---|---|
| A | `greedy_plus` | evidence-driven group elimination on keep-only sets, 1-minimality, full-network essential screen | `research/phase2/methods/greedy_plus.md` |
| B | `cem_search` | cross-entropy / EDA over inclusion probabilities of keep-only masks, elite updates, cleanup | `cem_search.md` |
| C | `group_probe` | active Bayesian group testing: remove the group with the most uncertain outcome; per-candidate posteriors | `group_probe.md` |
| D | `surrogate_search` | ensemble surrogate of P(function | kept set) + Thompson/UCB proposals, validated eliminations | `surrogate_search.md` |
| E | `evo_pareto` | evolutionary search with a Pareto front over pass rate, size and robust pass rate | `evo_pareto.md` |
| F | `joint` | cross-network component: independent / transfer / prior / joint discovery over two connectomes | `joint.md` |
| ref | `greedy_reference` | the frozen baseline's algorithm re-expressed on the generic API (fixed k = 3, degree-ranked pool) | — |

## 6. Selection on a held-out suite (pre-registered; `research/phase2/SELECTION_PROTOCOL.md`)

Held-out suite `mechanisms_v1_heldout`: 57 anonymised instances (10 families; sizes 50–3,000; hub distractors, misleading
centrality, backup copies, weak critical edges, autonomous modules, weight jitter, unknown signs), each run on 2 node
orders × 3 seeds at a hard budget of 1,000 calls (342 runs per method, 0 errors).

| method | structural success | causal functional success | identity Jaccard / identical | mean calls | robust pass | role acc |
|---|---|---|---|---|---|---|
| greedy_plus | 1.00 | 0.997 | 0.88 / 0.75 | 108 | 0.93 | 0.95 |
| cem_search | 1.00 | 0.997 | 0.91 / 0.81 | 115 | 0.92 | 0.94 |
| surrogate_search | 1.00 | 0.991 | 0.85 / 0.63 | 96 | 0.92 | 0.92 |
| evo_pareto | 1.00 | 0.962 | 0.86 / 0.68 | 745 | 0.92 | 0.93 |
| group_probe | 1.00 | 0.953 | 0.95 / 0.86 | 142 | 0.92 | 0.88 |
| greedy_reference | 0.74 | 0.215 | 0.83 / 0.63 | 304 | 0.71 | – |

Budget curve (seed 0, both orders, n ≤ 600): the leaders are saturated from 250 calls; at 50 calls group_probe keeps
0.95 causal functional success with 0.91 identical cores, greedy_plus 0.96 / 0.69, cem_search 0.77 / 0.65,
surrogate_search 0.32 / 0.17, evo_pareto 0.16 / 0.63, greedy_reference 0.00.

Held-out pair tournament (`pairs_v1_heldout`: 26 anonymised pairs incl. implementation shifts and anchor decoys; 6 base
methods × 4 modes × 2 seeds; budgets 1,000 per network): both-network success and mean total calls

| base method | independent | transfer (≈2 + 15 calls on b) | prior | joint |
|---|---|---|---|---|
| greedy_plus | 0.98 / 174 | 0.69 / 103 | 0.98 / 157 | 1.00 / 104 |
| cem_search | 1.00 / 184 | 0.73 / 106 | 0.98 / 174 | 1.00 / 115 |
| group_probe | 1.00 / 246 | 0.69 / 143 | 1.00 / 237 | 1.00 / 143 |
| surrogate_search | 0.98 / 194 | 0.69 / 113 | 0.98 / 192 | 0.98 / 127 |
| evo_pareto | 1.00 / 1,518 | 0.71 / 769 | 1.00 / 1,485 | 1.00 / 848 |
| greedy_reference | 0.71 / 569 | 0.60 / 373 | 0.71 / 570 | 0.96 / 388 |

On these pairs joint discovery never lost to independent discovery and cut total calls by about 40 %.

Review E showed that this pair design made correspondence nearly free:
- only mechanism members shared anchor profiles;
- hemilineage was present;
- the motif wiring was identical in both networks;
- the backgrounds were independent.

The numbers above are therefore an efficiency gain under easy correspondence. For the weak base method, part of the success
gain also appears with the correspondence destroyed. Claimed-correspondence precision and role-graph similarity between a
method's own two outputs measure self-agreement, which joint discovery maximises by construction, so they are not
reported as evidence. The controlled comparison on harder held-out pairs, with pooled-budget and null-correspondence
arms (protocol §7), is reported in §10.

**BrainIR v1 on the same held-out suite** was run after composition, under the section 2 conditions (342 runs, 0
errors; `research/phase2/tournament/sel_v1_b1000.md`). The paired comparisons use the same instances, node orders and
seeds (`cmp_sel_v1_*.md`; 95 % CIs resample instances):

| v1 vs | structural success | causal functional | identity Jaccard / identical | calls | robust (sd ×2 / weight noise) |
|---|---|---|---|---|---|
| greedy_reference | 1.00 vs 0.74, +0.26 [+0.15, +0.37] | 1.00 vs 0.20 | 0.97 / 0.95 vs 0.83 / 0.63 | 106 vs 304, 198 fewer [141, 261] | +0.22 / +0.18 |
| greedy_plus | equal (1.00) | +0.003 | +0.086 [+0.033, +0.146] / +0.19 [+0.09, +0.30] | equal | −0.01 / −0.02 (n.s.) |
| group_probe | equal | +0.047 [+0.006, +0.102] | +0.021 (n.s.) / +0.088 | 36 fewer [9, 71] | equal |
| cem_search | equal | +0.003 | +0.058 [+0.011, +0.110] / +0.14 | 9 fewer (n.s.) | equal |

v1's planted-set success is lower than greedy_plus's: 0.947 vs 0.988. On a few feed-forward instances v1 returns an
unplanted but valid sufficient set, such as a hub, which the truth audit lists.

## 7. BrainIR v1 (`src/brainir/methods/brainir_v1.py`, `research/phase2/BRAINIR_V1_METHOD.md`)

A fresh oracle-free agent composed BrainIR v1 in the clean room. It worked from the candidates' code and documents and the
aggregate selection results. The design:

1. **Restriction.** Exact structural reachability and signs, then an activity filter verified by one simulation decision.
2. **Canonical order.** A permutation-equivariant structural relevance order replaces a random or index-based order.
3. **Group elimination.** Adaptive group testing over keep-only sets in that fixed order. Every accept/reject decision
   is a sequential strict majority over working parameter replicates, extended when the replicates disagree.
4. **Validation and necessity.** Fresh-replicate validation with add-back, then two necessity tests in the intact
   network: single silencing of every member (essential claims) and a group-silencing screen for context members.
5. **Alternatives.** A deterministic enumeration of other sufficient sets.
6. **Selection.** The canonical set is replaced only by a decisively better set: better fresh-seed validation; else
   Occam, unless the intact network relies decisively more per member on the larger set; else robustness between equal
   sizes. Equally supported sets share the probability mass.
7. **Outputs.** A minimality certificate, a size–error curve, fidelity, evidence-class inclusion probabilities, generic
   roles and intervention predictions.
8. **Cross-connectome step.** It runs after the core is final and spends from the same budget pool (at most 25 % of the
   budget). The core is carried to the other connectome and verified there. Identity claims are emitted only for a
   verified, complete link, with a calibrated probability. Otherwise only a role-level alignment is reported.

**What was kept from the candidates:**
- from greedy_plus: the restriction, group elimination and the essential screen;
- from group_probe: the canonical-order idea;
- from joint (as fixed after review E): the verified transfer.

**What was dropped:** the surrogate model, random restarts and orders, cross-entropy sampling, the evolutionary Pareto
search and group_probe's posterior bookkeeping. Each drop is justified by selection-suite evidence (method doc
sections 5–7).

**What is new in v1:**
- deterministic, order-invariant search;
- adaptive replication and pooled necessity tests;
- selection by reliance;
- a budget-pooled, verified cross-connectome step.

v1 contains no dataset name, neuron identifier, cell type, mechanism size or instance-specific threshold. This is checked
by review, by `tests/test_leakage_guard.py` and by the static rules of `tests/test_budget_integrity.py`.

## 8. Confirmation on untouched suites (BrainIR v1.2.0, frozen at commit c3362c0)

The confirmation-role suites were built with secret salts before any method was run on them. They were never in the clean
room and were used once, after the freeze.

**Mechanisms** (`mechanisms_v1_final`: 57 instances, 2 node orders × 3 seeds, 1,000 calls, robust checks;
`research/phase2/tournament/conf_mech_b1000.md`, paired comparison `cmp_conf_greedy_reference.md`):

| metric | BrainIR v1.2 | greedy_reference | difference [95 % CI] |
|---|---|---|---|
| structural success | 1.000 | 0.754 | +0.246 [+0.140, +0.360] |
| success_intact (the mechanism the intact network uses) | 1.000 | 0.576 | +0.424 [+0.295, +0.553] |
| causal functional success | 1.000 | 0.155 | +0.845 [+0.754, +0.924] |
| planted success | 1.000 | 0.623 | +0.377 [+0.254, +0.500] |
| essential recall | 1.000 | 0.728 | +0.272 [+0.172, +0.378] |
| identity Jaccard / identical cores (reliability) | 0.958 / 0.930 | 0.803 / 0.526 | +0.155 [+0.096, +0.217] / +0.404 [+0.281, +0.526] |
| mean calls (efficiency) | 150 | 290 | 140 fewer [85, 202] |
| keep-only pass, sd × 2 / weight noise (robustness) | 0.954 / 0.851 | 0.733 / 0.670 | +0.221 [+0.114, +0.332] / +0.181 [+0.073, +0.292] |

**Pre-registered decision rule** (protocol §5, amended §8):
- **(a)** Success must not be lower than greedy_reference's, on both structural success and `success_intact`. **Holds.**
- **(b)** At least one advantage in reliability, efficiency or robustness must have a paired CI entirely above 0. **Holds
  on all three.**

**BrainIR v1.2 is therefore locked as the Phase 2 method.**

**Pairs.** v1.2 ran on network a of each pair, cross-connectome step included, within the same 1,000 calls:

| suite | runs | structural / intact success | identity claims (correct) | false on shift / null / structural decoy |
|---|---|---|---|---|
| `pairs_v1_final` (easy design) | 81 | 1.00 / 1.00 | 94 (94) | 0 / 0 / 0 |
| `pairs_v2_final` (hard design) | 81 | 1.00 / 1.00 | 28 (28) | 0 / 0 / 0 |

**Protocol §7.3 interpretation rule for identity claims** on `pairs_v2_final`:
- pooled precision 1.00, against the required ≥ 0.8;
- claims on null pairs 0 %, against the required ≤ 5 %;
- mean confidence 0.97 against observed precision 1.00, within the required 0.10.

The claims are therefore called reliable. v1 is conservative, though: it claimed in 18 of 81 runs, with core recall 0.24.

**Adversarial** (`adversarial_final`): *pending*.

## 9. Real benchmark, oracle-free: reliability across node orders and seeds (goal3 §§20–21)

Frozen `greedy_prune_sim`, unchanged, 8 salted node orders × 3 seeds per network (24 runs each; keep-only fidelity on
8 fresh parameter seeds):

| network | pairwise Jaccard of cores | modal-core frequency | keep-only pass rate | mean calls |
|---|---|---|---|---|
| manc_v1.2.1 | 0.63 | 0.67 | 0.67 | 777 |
| male-cns_v1.0 | 0.87 | 0.92 | 0.92 | 550 |
| manc_v1.2.3 | 0.65 | 0.67 | 0.67 | 755 |

**BrainIR v1.2 (locked) under identical orders and seeds.** The sweeps ran on the exact locked code tree before the lock
was written, and are oracle-free. They are paired by (order variant, seed), with 95 % CIs from paired bootstrap resampling of
runs (`research/phase2/reliability/compare_v12_vs_greedy_*.md`):

| network | identity Jaccard (v1.2 / greedy) | modal-core frequency | keep-only pass rate | calls | simulated seconds | wall per run |
|---|---|---|---|---|---|---|
| manc_v1.2.1 | 0.80 / 0.63, +0.17 [+0.04, +0.28] | 0.75 / 0.67 | 1.00 / 0.67, +0.33 [+0.17, +0.54] | 399 / 777 | 798 / 777 (n.s.) | 992 / 327 s |
| male-cns_v1.0 | 1.00 / 0.87, +0.13 [+0.00, +0.28] | 1.00 / 0.92 | 1.00 / 0.92, +0.08 [0.00, +0.21] | 386 / 550 | 772 / 550 (+40 %) | 799 / 216 s |
| manc_v1.2.3 | 0.85 / 0.65, +0.20 [+0.00, +0.38] | 0.83 / 0.67 | 1.00 / 0.67, +0.33 [+0.17, +0.54] | 403 / 755 | 806 / 755 (+7 %) | 960 / 265 s |

**Reliability and function.** On every real network v1.2 is more consistent across node orders × parameter draws, and
every one of its 72 cores passes keep-only on fresh seeds.

**Compute.** v1.2 needs about half the simulator calls, but each of its calls simulates the bundle's full 2-second
protocol. The frozen baseline simulates 1 s per call. In simulated time v1.2 therefore costs the same as the baseline or
more, and in wall time 3–4× more, because of the many full-network silencing simulations reviews A and G required. The
honest efficiency claim is fewer queries, not less compute.

## 10. Cross-connectome transfer

Real public networks, oracle-free (`research/phase2/transfer/xfer_greedy_plus.md`): base method greedy_plus, 3 seeds,
1,000 calls per network. A mechanism is judged by keep-only sufficiency on 6 fresh parameter draws of its own network. The
null is 20 random interneuron sets per run with the same size and sign composition.

| base method | direction | independent: both sufficient / total calls | transfer only: destination sufficient (dest. calls) | null | joint: both sufficient / total calls |
|---|---|---|---|---|---|
| greedy_plus | MaleCNS → MANC v1.2.1 | 3/3 / 426 | 3/3 (2 calls) | 0.00 | 3/3 / 268 |
| greedy_plus | MANC v1.2.1 → MaleCNS | 3/3 / 426 | 2/3 (2 + 21 adaptation calls) | 0.00 | 3/3 / 268 |
| greedy_reference | MaleCNS → MANC v1.2.1 | 3/3 / 1,069 | 3/3 (2 calls) | 0.00 | 3/3 / 405 |
| greedy_reference | MANC v1.2.1 → MaleCNS | 3/3 / 1,040 | 3/3 (2 calls) | 0.00 | 3/3 / 405 |

These transfers show functional sufficiency of the carried-over set in the other connectome against a matched null. They
do not show neuron identity (review E finding 9).

**Synthetic pairs: does joint discovery help?** This is the pre-registered comparison of protocol §7.4, run after the
review E fixes. The base methods are greedy_plus and greedy_reference, with 3 seeds and 1,000 + 1,000 calls. Pairs are
matched on instance and seed (`research/phase2/tournament/cmp_arms_pairs_{v1h,v2h}.md`). The table gives calls saved by
the joint arm against the null arm, whose simulations are identical but whose cross-network cues are destroyed; success
is for both networks.

| pair design | base method | success: joint / independent / null | calls saved by joint vs null [95 % CI] |
|---|---|---|---|
| easy (v1 design, 26 pairs) | greedy_plus | 0.96 / 0.96 / 0.96 | +54 [+39, +68] |
| easy | greedy_reference | 0.72 / 0.72 / 0.73 | +121 [+66, +178] |
| hard (v2 design, 27 pairs) | greedy_plus | 1.00 / 1.00 / 1.00 | +14 [−0.1, +30] |
| hard | greedy_reference | 0.65 / 0.63 / 0.63 | +7 [−29, +45] |

- **Success.** Joint discovery raises success in no case.
- **Easy pairs.** Joint discovery saves calls, and the saving comes from the correspondence: the null arm does not save.
- **Hard pairs.** The saving is not distinguishable from zero. Hard pairs have blank hemilineage, noisy anchors,
  homologous backgrounds, rewired motifs, structural decoys and null pairs.
- **Earlier numbers.** The success gain seen before the fix (greedy_reference 0.71 → 0.96) came from adopting the other
  network's mechanism by agreement. Review E showed that adoption to be unjustified, and it is gone.
- **Identity claims.** Every claim the fixed joint mode made was correct (107 and 25 claims), except one on a null pair
  with the cues destroyed.

**BrainIR v1's own cross-connectome step** runs on network a of each held-out pair within the same 1,000-call budget
(`sel_v1_pairs_{v1h,v2h}.md`):

| pair design | runs with claims | identity claims (correct) | false claims on shift / null / structural-decoy pairs |
|---|---|---|---|
| easy (v1 design) | 42 of 78 | 90 (90) | 0 / 0 / 0 |
| hard (v2 design) | 12 of 81 | 18 (18) | 0 / 0 / 0 |

On the hard design v1 is conservative. It claims rarely, and when it does it is right.

BrainIR v1's own transfer experiments and the hidden-oracle scoring of its cross-connectome claims: *pending*.

## 11. Ablations, anti-gaming checks, nulls

Anti-gaming, candidates (`research/phase2/tournament/ag_candidates_summary.md`; 47 held-out instances, seed 0): every
candidate is invariant to five changes (0 runs lost, 0 gained):

- reordered edge rows;
- re-salted interneuron tokens;
- stripped side / neuromere / hemilineage annotations;
- appended sink-only distractors;
- doubled parameter spread.

greedy_reference gains one run with sink distractors.

**BrainIR v1, anti-gaming** (`research/phase2/tournament/ag_v1_summary.md`, same 47 instances): invariant to all five
transforms (0 runs lost, 0 gained).

**BrainIR v1, budget curve** (`sel_curve_v1_curve.md`; seed 0, both node orders, 54 held-out instances with n ≤ 600):
structural success is 1.00 at every budget from 50 to 2,000 calls. Mean calls used are 49 at a budget of 50 and 68 at 100,
levelling off at about 100.

| method | causal functional (50 calls) | identical cores (50 calls) | causal functional (100 calls) | identical cores (100 calls) |
|---|---|---|---|---|
| brainir_v1 | 0.95 | 0.93 | 1.00 | 0.94 |
| group_probe | 0.95 | 0.91 | 0.95 | 0.91 |
| greedy_plus | 0.96 | 0.69 | 1.00 | 0.80 |
| cem_search | 0.77 | 0.65 | 0.97 | 0.80 |
| greedy_reference | 0.00 | 0.72 | 0.00 | 0.74 |

**BrainIR v1, ablations** (`abl_v1_summary.md`): each component is switched off alone, on the same 54 instances, 2 node
orders and seed 0 (108 paired runs per variant). Structural success stays 1.00 in every variant.

| switched off | effect (paired difference to the default, 95 % CI) |
|---|---|
| group testing (one candidate per probe) | +105 calls [+69, +143] |
| canonical structural order (seeded random order instead) | +18 calls [+14, +24]; identity Jaccard 0.944 → 0.920 |
| minimality cleanup | causal functional success −0.065 [−0.111, −0.019]; cores +0.18 neurons |
| adaptive replication | identity Jaccard 0.944 → 0.926 |
| alternatives enumeration | −30 calls; cores +0.17 neurons (the alternatives let the smaller valid set win) |
| essentiality tests of members | −30 calls; the essential claims are lost |
| necessity screen | −6 calls; context members are lost (cores −0.09 neurons) |
| structural / activity pruning, active chunk sizes, reliance, robust objective | small call changes (−6 to +4); no success or consistency change |
| decisions on 1 replicate instead of 3 | −36 calls with no loss on this suite |
| evidence-class uncertainty model (point estimate instead) | Brier 0.004 → 0.000: on these instances v1's probabilities are under-confident |

The replication and the uncertainty model are insurance that this suite does not reward. The real-network sweeps
(section 9) test the replication.

## 12. Blind evaluation (*pending*; after the lock)

## 13. Independent reviews

| review | status | outcome |
|---|---|---|
| F computational | done (pre-lock) | 1 blocker, 7 major, 11 minor; all resolved (`research/phase2/reviews/F_resolution.md`) |

- **Blocker:** failed runs had dropped out of the success denominators. No selection run had failed, so no reported number
  changed.
- **Majors:**
  - the call budget had not been enforced against bypass (now guarded at runtime and statically);
  - unseeded weight noise had been cached under one key;
  - the Modal environment was unpinned;
  - provenance recorded the commit at registration time;
  - node-order reliability is confounded with parameter draws (renamed and documented; both compared methods face it
    equally);
  - the hidden-evaluation gate was not bound to the locked method;
  - one tie-break was unstable.

| E cross-connectome | done (pre-lock) | 1 blocker, 6 major, 5 minor; harness fixes done, method fixes with the composer (`research/phase2/reviews/E_resolution.md`) |

- **Review E blocker:** identity-claim confidence came from structural alignment, not identity evidence. Under
  implementation shifts, v1 claimed non-homologous neurons as identical.
- **Review E majors:**
  - joint discovery manufactures agreement;
  - "verified" transfer accepted unvalidated sets;
  - the joint advantage is an efficiency gain on easy correspondence;
  - the synthetic pairs made correspondence nearly free;
  - v1's cross-connectome calls were counted but not budgeted;
  - the harness could not show that synthetic truth stayed out of the method's reach.
- **Harness fixes:**
  - one budget pool per run;
  - a truth guard and static rules;
  - identity scoring on every pair type;
  - pooled-budget and null-correspondence arms;
  - the harder `synthetic-pairs-v2` design.

| A causal | done (pre-lock) | 1 blocker, 3 major, 5 minor; being fixed (v1.1) |
| G adversarial | done (pre-lock) | 1 blocker, 6 major, 3 minor; being fixed (v1.1) |

**Reviews A and G reached the same blocker independently.** BrainIR v1.0 chooses among keep-only-sufficient sets without
asking whether the intact network uses them.
- **Latent backup.** A backup that the intact network keeps silent behind an inhibitory gate was returned at P = 0.90.
  The circuit that actually runs was demoted to 0.15, including neurons v1 itself had measured as essential. This
  happened in 17 of 22 runs on review G's traps, and in 6 of 6 runs on a generator instance with a backup copy.
- **Masked gate.** The group-silencing screen misses an essential inhibitor when it is silenced together with what it
  gates. This happened in 28 of 28 runs at n ≥ 150.

**The v1.0 metrics were blind to both failure modes.** The tournament's structural and causal-functional success scored
every one of these runs as a success. The Brier score was also computed against a target chosen by overlap with the
method's own core, and neurons that were trivially excluded dominated it.

**Response:**
- a participation-aware audit and new metrics: `success_intact`, essential recall, latent backups, contested-neuron
  Brier;
- graded activity and edge-removal queries in the library;
- an adversarial trap suite built by a third party (review G's author);
- protocol amendment §8;
- method fixes by the oracle-free composer (v1.1).

The v1.0 selection numbers in section 6 stand as measured, but the metrics they rest on cannot see these failure modes.
The confirmation uses the amended metrics and the adversarial suites.

Reviews B, C and D: *pending*.

## 14. Compute and cost

Modal (registry, Phase 2 so far): *to be totalled at completion*.

## 15. Limitations, failures, conclusion, Phase 3 recommendation (*pending*)
