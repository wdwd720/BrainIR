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

BrainIR v1's own transfer experiments and the hidden-oracle scoring of its cross-connectome claims: *pending*.

## 11. Ablations, anti-gaming checks, nulls

Anti-gaming, candidates (`research/phase2/tournament/ag_candidates_summary.md`; 47 held-out instances, seed 0): every
candidate is invariant to five changes (0 runs lost, 0 gained):

- reordered edge rows;
- re-salted interneuron tokens;
- stripped side / neuromere / hemilineage annotations;
- appended sink-only distractors;
- doubled parameter spread.

greedy_reference gains one run with sink distractors. BrainIR v1's anti-gaming checks, ablations and matched random
nulls: *pending*.

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

Reviews A, B, C, D and G: *pending*.

## 14. Compute and cost

Modal (registry, Phase 2 so far): *to be totalled at completion*.

## 15. Limitations, failures, conclusion, Phase 3 recommendation (*pending*)
