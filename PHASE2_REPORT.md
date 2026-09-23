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

Joint discovery never lost to independent discovery, cut total calls by about 40 %, and raised claimed-correspondence
precision to 1.00 and role-graph similarity a↔b to 1.00.

## 7. BrainIR v1 (*pending*: composed from the selection evidence; `research/phase2/BRAINIR_V1_METHOD.md`)

## 8. Confirmation on an untouched suite (*pending*)

## 9. Real benchmark, oracle-free: reliability across node orders and seeds (goal3 §§20–21)

Frozen `greedy_prune_sim`, unchanged, 8 salted node orders × 3 seeds per network (24 runs each; keep-only fidelity on
8 fresh parameter seeds):

| network | pairwise Jaccard of cores | modal-core frequency | keep-only pass rate | mean calls |
|---|---|---|---|---|
| manc_v1.2.1 | 0.63 | 0.67 | 0.67 | 777 |
| male-cns_v1.0 | 0.87 | 0.92 | 0.92 | 550 |
| manc_v1.2.3 | 0.65 | 0.67 | 0.67 | 755 |

BrainIR v1 under identical orders and seeds: *pending*.

## 10. Cross-connectome transfer (*pending*)

## 11. Ablations, anti-gaming checks, nulls (*pending*)

## 12. Blind evaluation (*pending*; after the lock)

## 13. Independent reviews (*pending*)

## 14. Compute and cost

Modal (registry, Phase 2 so far): *to be totalled at completion*.

## 15. Limitations, failures, conclusion, Phase 3 recommendation (*pending*)
