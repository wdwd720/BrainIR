# Phase 2 method selection protocol (pre-registered)

Written 2026-09-23 before any method was scored on the selection or confirmation suites. It fixes how BrainIR v1 is
chosen and how it is compared with the frozen baseline, so that neither step can drift toward whatever looks good
afterwards (goal3 sections 20–22, 27–30). The hidden dng100 oracle plays no role in any step before the method lock.

## 1. Three synthetic suites, three roles

| suite | built from | who sees what | role |
|---|---|---|---|
| development: `mechanisms_v1`, `pairs_v1` | readable instance names | public instances are in the clean room; truth is private | method developers debug on them; the orchestrator returns aggregate per-family scores only |
| selection: `mechanisms_v1_heldout`, `pairs_v1_heldout` | fresh secret salt, anonymised names | never in the clean room | every candidate is scored under identical budgets, seeds and node orders; aggregate results go to the composer of BrainIR v1 |
| confirmation: `mechanisms_v1_final`, `pairs_v1_final` | another fresh salt, anonymised | never in the clean room, never used for feedback | built and used once, after BrainIR v1 is frozen and before the lock: the final synthetic evidence recorded in METHOD_LOCK.json |

All suites are simulation-verified and truth-audited (`brainir.discovery.suite_audit`): unplanted sufficient sets are part
of the truth. Instance selection reads the private truth spec, so nothing public carries family information.

## 2. Selection tournament (identical conditions for every candidate)

- Methods: every registered candidate (`greedy_reference`, `greedy_plus`, `cem_search`, `group_probe`,
  `surrogate_search`, `evo_pareto`), each at its own documented default configuration. No method is tuned on the
  selection suite.
- Networks: `main` and `order1` of every instance, so each instance runs under two node orders. Seeds 0, 1, 2.
  Score seeds 5000–5003 (fresh parameter draws).
- Budget: 1,000 simulator calls, with the robust checks enabled. Budget curve: 250, 500 and 2,000 calls on instances
  with n ≤ 600.
- Backend: Modal, one CPU per run, identical code commit for all methods.

## 3. Metrics (all reported per method, none aggregated into one score)

1. **Success**: structural success (the core contains a listed sufficient set), functional success (sufficient on
   fresh seeds and 1-minimal) and planted success, each with a bootstrap 95 % CI.
2. **Reliability**: identity consistency across the 6 runs of each instance (2 orders × 3 seeds): mean pairwise
   Jaccard in the canonical frame, and the fraction of instances whose runs all agree.
3. **Efficiency**: median calls and simulated seconds, and the area under success versus log budget.
4. **Robustness**: keep-only pass fraction with doubled parameter spread and with weight noise 0.2.
5. **Minimality**: fraction of runs with a removable member. **Uncertainty**: Brier score of the inclusion
   probabilities. **Roles**: role accuracy. **Essentiality**: accuracy of the essential claims.
6. **Transfer** (pairs): success on a and b per mode (independent, transfer, prior, joint), correspondence
   precision/recall, role-alignment accuracy and calls.

Paired comparisons use the same (instance, network, seed) triples. Differences get bootstrap CIs, and a paired sign
test is used where appropriate.

## 4. Composition and freeze of BrainIR v1

A fresh, oracle-free composer agent receives the candidates' code and documentation and the aggregate selection results
(per method and per family; no per-instance truth). It builds BrainIR v1 as one coherent algorithm following the
goal3 section 26 pipeline and documents every design choice together with the evidence behind it. BrainIR v1 is then frozen.

## 5. Confirmation and decision rule

On the confirmation suite, BrainIR v1 and `greedy_reference` run under the section 2 conditions, and the frozen
`greedy_prune_sim` runs on the real blind bundle in the reliability sweep. BrainIR v1 is locked as the Phase 2 method
if both conditions hold:

- **(a) Success**: its success rate is not lower than `greedy_reference`'s, meaning the paired difference CI does not
  lie entirely below 0.
- **(b) Advantage**: it is better on at least one of reliability, efficiency or robustness, meaning the paired
  difference CI lies entirely above 0.

Every other metric is reported whichever way it goes. If a condition fails, the report says so plainly (goal3
section 48); no further tuning happens after the confirmation results.

## 6. Real benchmark (after the lock)

The real benchmark is run only after the lock, as follows:

1. **Blind run.** `scripts/blind_eval.py` performs one blind clean-room run per network with the locked seed and budget.
   It then runs the frozen evaluator, and the attempt is logged.
2. **Reliability sweeps.** Before the lock, the sweeps are scored oracle-free only: consistency, functional fidelity
   and calls. The locked method and the frozen baseline use the same 8 node orders × 3 seeds per network.
3. **Hidden scoring of the sweeps.** Only after the lock are both sets of sweep predictions scored on the structural
   families. That is one logged hidden evaluation per method and network.
