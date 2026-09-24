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

## 7. Amendment after review E (written 2026-09-23, before any method ran on a harder pair suite)

Review E (`research/phase2/reviews/E_cross_connectome.md`) found that the v1 pair design made correspondence nearly free:
- only members shared anchor profiles;
- hemilineage was present;
- the wiring was identical in both networks;
- the backgrounds were independent;
- the scorer ignored claims on implementation-shift pairs.

It also found that identity claims were not calibrated. This amendment adds evaluation, and it changes nothing that has
already been measured.

1. **Harder pair suites.** `hard_pair_specs()` (suite id `synthetic-pairs-v2`) produces `pairs_v2_heldout` (selection
   role) and `pairs_v2_final` (confirmation role, used once after BrainIR v1 is frozen). Both have fresh secret salts,
   secret 40-bit seed offsets and anonymised names, and neither enters the clean room. Every pair has:
   - blank interneuron hemilineage, weaker and noisier anchors, homologous backgrounds, and jittered motif counts in b;
   - per family, a rewired pair, a pair with a structural decoy plus a sign-consistent anchor decoy, and a null pair
     (b implements another family);
   - in addition, 4 implementation-shift pairs and 4 pairs of 2,000 × 2,500 neurons.
2. **Identity claims are scored on every pair.** A claim is correct only if both neurons are the same neuron, meaning
   the same planted mechanism member. Under a shift, only members of the retained alternative count. On a null pair
   every claim is false. The following are reported pooled over claims, per method and arm:
   - precision;
   - false claims on shift, null and structural-decoy pairs;
   - Brier score and reliability diagram of the confidence;
   - recall of the core.
3. **BrainIR v1's own cross-connectome step.** It is evaluated as run: v1 on network `a` of every pair, budget 1,000
   (its cross-connectome calls included, since spawned simulators share the budget), seeds 0, 1, 2. The runs use
   `pairs_v1_heldout` and `pairs_v2_heldout` before the freeze, and `pairs_v2_final` once after it.
   - **Interpretation rule (fixed now):** its identity claims are called reliable only if, on `pairs_v2_final`, the
     pooled precision is at least 0.8, null pairs receive at most 5 % of all claims, and the confidence is calibrated
     in the large: the mean claim confidence is within 0.10 of the observed precision.
   - *Correction, 2026-09-23, before any confirmation run.* The first version of this rule required the Brier score to
     beat the constant predictor at the observed precision. That condition cannot be met when every claim is correct:
     the constant predictor at 1.0 then has a Brier score of 0, so any confidence below 1 would fail. It was replaced by
     calibration in the large; the Brier score and the reliability diagram are still reported. The error was noticed
     when the held-out (selection-role) pair results showed a precision of 1.00. No confirmation data existed then.
   - Otherwise the report treats v1's cross-connectome claims, including their hidden-benchmark score, as unreliable.
     No tuning follows either way.
4. **Joint discovery against its controls** (review E finding 4). The comparison uses `pairs_v1_heldout` and
   `pairs_v2_heldout`, seeds 0, 1, 2, and budgets of 1,000 + 1,000. Base methods are `greedy_plus` and
   `greedy_reference`, under the arms `independent`, `independent_pooled` (b also gets a's unused calls), `joint` and
   `joint_null` (b's anchor labels and annotations destroyed, simulations unchanged). Success and calls are reported
   separately, with paired bootstrap CIs.
   - An efficiency gain is claimed only if joint needs fewer total calls than `joint_null`, with the CI of the
     difference entirely above 0.
   - A success gain is claimed only if joint beats both `independent_pooled` and `joint_null` in the same way.
   - Agreement between a method's own two outputs, such as role-graph similarity a↔b or claim precision on easy pairs,
     is not reported as evidence.
