# PHASE 2 REPORT — Blind causal mechanism discovery v1

Status: **COMPLETE** (2026-09-25). Spec: `goal3.md`. Frozen benchmark: `dng100-benchmark-v1` (commit a7c0142, lock
`bcaa8ee46e23dc29…`), unchanged throughout (`benchmarks/dng100/freeze.py --check` green). Locked method: BrainIR v1.2.0,
`research/phase2/METHOD_LOCK.json` (lock `b4c0a9cb…`, tree `911625b9…`), commit 959d689, tag `brainir-v1-preblind`.

**This report is answer-bearing.** Sections 9, 12, 15 and 17 contain hidden-evaluation results and compare outputs with the oracle.
Never copy it into a clean development directory. No number comes from the hidden oracle unless its section says so, and every
hidden evaluation is listed in `research/phase2/HIDDEN_EVAL_LOG.md`.

## 0. Conclusion at a glance (goal3 §50.30)

BrainIR v1.2 **matches** the frozen `greedy_prune_sim` on what the structural score can see, **beats** it on reliability, function
and trap-robustness, and **loses** on compute. It is not better than the best simple candidate (greedy_plus) on query efficiency.

| dimension | result | where |
|---|---|---|
| structural recovery of the published circuit (real networks) | v1.2 met the frozen structural criterion in 65 of 72 sweep runs, the frozen baseline in 54 of 72. Per network the difference is not significant; pooled over clusters p = 0.0034, post hoc. The single blind draw succeeded on 2 of 3 networks, the same count as greedy's Phase 1 blind run. | §12 |
| reliability across node orders × parameter draws (real networks) | better on both MANC networks (Jaccard +0.17 and +0.20, CIs above 0). On MaleCNS 1.00 vs 0.87, with a CI reaching 0. | §9 |
| function of the returned core on fresh parameter draws | 72 of 72 v1.2 cores pass keep-only, against 54 of 72 for the baseline | §9 |
| simulator queries | about half the baseline's calls (399 / 386 / 403 vs 777 / 550 / 755) | §9 |
| compute | equal or more simulated time (each v1.2 call simulates 2 s, each baseline call 1 s) and 3–4× the wall time | §9 |
| synthetic confirmation vs greedy_reference (frozen algorithm, k = 3) | success, reliability, efficiency and robustness all better. Most of the success gap comes from greedy's fixed k = 3. | §8 |
| vs the best simple candidate (greedy_plus, k-free) | equal success; more consistent (identical cores +0.19); **38 more calls** | §8 |
| adversarial traps (fresh draws of designs v1.2 was built against) | correct 0.98 vs 0.72 (greedy_plus) and 0.09 (greedy_reference); confident-wrong 0.01 | §8 |
| cross-connectome | transferred cores work in the other connectome in 5 of 6 runs with 2 destination calls, where size- and sign-matched random sets never do. Identity claims were always correct, but they are rare, and the joint mode saves calls only when correspondence is easy. | §§8, 10 |
| leakage | no answer identity reached the method (review D). The answer's structure and one evaluator-calibrated threshold did reach the development environment; this is disclosed. Without that threshold, the locked method returns the same cores in 70 of 72 runs. | §§2, 9.3 |

## 1. What Phase 2 set out to do

Build the first algorithm that receives only the public DNg100 benchmark evidence and independently discovers a compact, causal
mechanism. The evidence is tier A: the signed synapse-count graph, NT-derived signs, sizes, coarse annotations, the stimulus, the
readout and the rate model. Then test whether the algorithm improves on the frozen simulation-guided baseline `greedy_prune_sim` on
reliability, query efficiency, robustness, minimality, calibration and cross-connectome transfer, not merely on exact-oracle recall
(goal3 §§0, 32, 51).

## 2. How leakage was prevented, and where the prevention was not airtight (goal3 §4; review D)

**Design.**
- The orchestrating session had seen the answer during Phase 1, so it built only generic infrastructure and never designed method
  logic.
- Method families were implemented by fresh agents in a separate directory, `C:\Dev\BrainIR_p2clean`. It holds the library, the tier-A
  public bundle, the clean-room runner and the public synthetic instances. It holds no oracle, evaluator, Phase 1 report or truth of
  any selection or confirmation suite.
- Developers received aggregate synthetic scores only.
- BrainIR v1 was composed by another fresh agent in the same directory.
- The method was locked (`METHOD_LOCK.json`, tag `brainir-v1-preblind`) before any hidden evaluation. Hidden evaluations are few and
  logged.

**Review D's verdict** (post-lock leakage audit, `research/phase2/reviews/D_leakage.md`; resolution `D_resolution.md`):
- The blind result is free of answer-identity leakage and of oracle feedback. No neuron id, tier-A position, tier-A token, cell type
  or oracle label of the answer occurs in the method, its configuration, the discovery library, the clean room, or the tool traffic of
  any development agent. No hidden evaluation preceded the lock.
- It is not fully blind to the answer's structure. Six things fell short of the stated design:

1. **The answer's structure was in the development environment (D1).**
   - The clean room received the benchmark's `PROTOCOL.md`, which names the structural family as "excitatory core recall over E1/E2,
     inhibitory slot I1|I2" and says that simulation-guided pruning recovers the published core.
   - It also received the baseline README and scripts (k = 3, "2 E + 1 I") and the repository README.
   - Every development agent inherited the main `CLAUDE.md`, which said the baseline recovers the published core.
   - One developer (surrogate_search) printed the protocol lines; its method contributed nothing to v1. The composer never opened them,
     but the orchestrator's prompt to it named the baseline's order sensitivity.
   - What leaked: the answer's size (about three neurons), sign composition, the interchangeability of its inhibitory member, and
     that keep-only pruning finds it. Which neurons form it did not leak.
   - v1 contains no size, composition or topology prior (review D read the method in full and scanned its literals).
2. **Isolation was procedural (D2).**
   - Every development agent was a subagent of the answer-aware session, with the main repository as working directory and the
     orchestrator's scratchpad as temp directory. The scratchpad holds answer-bearing files.
   - The transcript audit found that no development agent opened an answer-bearing file or read the main repository. The guarantee
     rests on instructions and that audit, not on access control.
3. **Tier B (real cell types) was in the clean room for about 8 hours (D3):** 2026-09-23T17:52Z to 2026-09-24T02:08Z, covering all
   candidate development and v1.0's composition.
   - Tier A joins tier B row by row by neuron size.
   - The answer's cell types appear in a preprint that predates the agents' knowledge cutoff.
   - Only review E touched the file, with a join count on the size column.
4. **One answer-calibrated constant defines function on the real bundle (D4).**
   - The discovery library's rhythm criterion for the real bundle uses the frozen evaluator's amplitude gate, 0.25 Hz. The evaluator
     chose that value so that every published core passes.
   - The public bundle has no gate, and the public library's default is 1.0 Hz.
   - The locked method was rerun oracle-free with the gate at 0 and at 1.0 Hz (§9.3).
5. **Development used the test networks (D5).** The composer ran v1 on the blind bundle about 20 times at seed 0, the locked seed. The
   blind predictions were therefore known, oracle-free, before the lock. §12 reports this, with the development trajectory as
   evidence against steering.
6. **The build-report incident (D6).**
   - The development suite's build report, which carries per-node essential flags of the development instances, was copied into the
     clean room by mistake.
   - All five candidate developers printed its head (disclosed in their method documents), and the joint developer printed the head of
     the pair suite's report (instance list only; now disclosed in `methods/joint.md`).
   - The files were deleted at 2026-09-23T20:03Z.
   - Selection and confirmation use suites built afterwards, with fresh secret salts and anonymised names, that never entered the clean
     room.

**Two further residuals:**
- The synthetic generator was written by the answer-aware orchestrator (D8). `ei_pair_oscillator` is an abstract analogue of the
  answer's loop, not a copy: 2 neurons, an autapse, no interchangeable inhibitor.
- The frozen public bundle and library cite the model's source paper (D1 residual).

**Tooling fixed for any later clean room** (`scripts/make_phase2_cleanroom.py`, `tests/test_leakage_guard.py`, `CLAUDE.md`):
- no protocol, baseline scripts or READMEs are copied;
- no `truth*` directory or build or audit report is copied;
- content is scanned for answer phrases, and `--check` validates each manual sync;
- post-lock answer-bearing paths are refused;
- the leakage guard now scans for answer tier-A positions, tokens and oracle labels;
- the main `CLAUDE.md` no longer states how the baseline fares on the answer.

## 3. Infrastructure built (all generic; `src/brainir/discovery/`)

- **Problem and simulator.**
  - `DiscoveryProblem` (bundle loader) and `BudgetedSimulator`: a hard call budget checked before every batch, one budget pool per
    run, an in-run memo and a truth guard.
  - Accounting of calls, simulated seconds, CPU seconds and distinct interventions.
  - Graded activity (`mean_rate_hz`, `peak_rate_hz`) and edge-removal queries.
- **Interfaces and scoring.**
  - Criteria (rhythm, activity band, persistence, selectivity, ramp) and interventions (silence, keep-only, weight noise, group
    designs).
  - `DiscoveryResult` → the frozen prediction schema, including cross-connectome claims; a method registry; the clean-room entry
    script.
- **Synthetic suites.**
  - The mechanism generator: 10 families × complications × sizes 50–3,000. The truth is simulation-verified and stored apart, with a
    participation-aware truth audit. It was written by the answer-aware orchestrator (§2).
  - The pair generator, in an easy v1 design and the harder `synthetic-pairs-v2` design (review E).
  - A third-party adversarial trap generator and scorer written by review G's author (`adversarial.py`: 6 trap types in 22 variants).
- **Scorers and experiment tooling.**
  - Tournament scorer: structural, causal-functional and `success_intact` success, essential recall, latent backups, a contested
    Brier score, identity consistency, robustness and identity-claim scoring. Plus a pair-tournament scorer.
  - Budget curves, anti-gaming transforms, node-order reliability sweeps (with a criterion-gate sensitivity option), paired
    comparisons, transfer experiments, matched nulls and an ablation runner.
  - The method lock and the blind-evaluation tooling.

## 4. Methods-only literature review

`research/phase2/methods_review.md` has 55 entries in 15 areas: group testing, adaptive/Bayesian experimental design,
cross-entropy/EDA, surrogate-assisted and Bayesian optimisation, evolutionary multi-objective search, sparse masks, causal
abstraction, redundancy/Rashomon sets, robust objectives/CVaR, racing, transfer and correspondence. Its synthesis proposed the
candidate families below.

## 5. Candidate algorithm families (tournament)

| family | method | core idea | developer document |
|---|---|---|---|
| A | `greedy_plus` | evidence-driven group elimination on keep-only sets, 1-minimality, full-network essential screen | `research/phase2/methods/greedy_plus.md` |
| B | `cem_search` | cross-entropy / EDA over inclusion probabilities of keep-only masks, elite updates, cleanup | `cem_search.md` |
| C | `group_probe` | active Bayesian group testing: remove the group with the most uncertain outcome; per-candidate posteriors | `group_probe.md` |
| D | `surrogate_search` | ensemble surrogate of P(function \| kept set) + Thompson/UCB proposals, validated eliminations | `surrogate_search.md` |
| E | `evo_pareto` | evolutionary search with a Pareto front over pass rate, size and robust pass rate | `evo_pareto.md` |
| F | `joint` | cross-network component: independent / transfer / prior / joint discovery over two connectomes | `joint.md` |
| ref | `greedy_reference` | the frozen baseline's algorithm re-expressed on the generic API (fixed k = 3, degree-ranked pool) | — |

## 6. Selection on a held-out suite (pre-registered; `research/phase2/SELECTION_PROTOCOL.md`)

**Held-out suite** `mechanisms_v1_heldout`: 57 anonymised instances (10 families; sizes 50–3,000).
- Complications: hub distractors, misleading centrality, backup copies, weak critical edges, autonomous modules, weight jitter,
  unknown signs.
- Each instance ran on 2 node orders × 3 seeds at a hard budget of 1,000 calls: 342 runs per method, 0 errors.

| method | structural success | causal functional success¹ | identity Jaccard / identical | mean calls | robust pass | role acc |
|---|---|---|---|---|---|---|
| greedy_plus | 1.00 | 0.997 | 0.88 / 0.75 | 108 | 0.93 | 0.95 |
| cem_search | 1.00 | 0.997 | 0.91 / 0.81 | 115 | 0.92 | 0.94 |
| surrogate_search | 1.00 | 0.991 | 0.85 / 0.63 | 96 | 0.92 | 0.92 |
| evo_pareto | 1.00 | 0.962 | 0.86 / 0.68 | 745 | 0.92 | 0.93 |
| group_probe | 1.00 | 0.953 | 0.95 / 0.86 | 142 | 0.92 | 0.88 |
| greedy_reference | 0.74 | 0.215 | 0.83 / 0.63 | 304 | 0.71 | – |

¹ Summary tables exclude cores of more than 40 neurons from causal functional success (30 greedy_reference runs); the paired tables
count them as failures, hence 0.215 here and 0.20 below (review C, C11).

**Budget curve** (seed 0, both orders, n ≤ 600). The leaders are saturated from 250 calls. At 50 calls:

| method | causal functional success | identical cores |
|---|---|---|
| group_probe | 0.95 | 0.91 |
| greedy_plus | 0.96 | 0.69 |
| cem_search | 0.77 | 0.65 |
| surrogate_search | 0.32 | 0.17 |
| evo_pareto | 0.16 | 0.63 |
| greedy_reference | 0.00 | 0.72 |

**Held-out pair tournament** (`pairs_v1_heldout`, easy design: 26 anonymised pairs; 6 base methods × 4 modes × 2 seeds; 1,000 calls
per network). Joint discovery never lost to independent discovery and cut total calls by about 40 %. Review E showed that this design
made correspondence nearly free, so the gain is an efficiency gain under easy correspondence. The controlled comparison on the harder
design is in §10.

**BrainIR v1.0** (the first composition) on the same held-out suite, same conditions (`sel_v1_b1000.md`, paired `cmp_sel_v1_*.md`;
95 % CIs resample instances):

| v1.0 vs | structural success | causal functional | identity Jaccard / identical | calls | robust (sd ×2 / weight noise) |
|---|---|---|---|---|---|
| greedy_reference | 1.00 vs 0.74, +0.26 [+0.15, +0.37] | 1.00 vs 0.20 | 0.97 / 0.95 vs 0.83 / 0.63 | 106 vs 304, 198 fewer [141, 261] | +0.22 / +0.18 |
| greedy_plus | equal (1.00) | +0.003 | +0.086 [+0.033, +0.146] / +0.19 [+0.09, +0.30] | equal | −0.01 / −0.02 (n.s.) |
| group_probe | equal | +0.047 [+0.006, +0.102] | +0.021 (n.s.) / +0.088 [0.000, +0.175] (n.s.) | 36 fewer [9, 71] | equal |
| cem_search | equal | +0.003 | +0.058 [+0.011, +0.110] / +0.14 | 9 fewer (n.s.) | equal |

v1.0's planted-set success was 0.947 against greedy_plus's 0.988. The difference is not significant: CI [−0.099, 0.000]. On a few
feed-forward instances v1.0 returned an unplanted but valid sufficient set that the truth audit lists.

**Reviews A and G then showed that these metrics could not see two failure modes** (§13). Every v1.x result after v1.0 is scored with
the amended metrics.

## 7. BrainIR v1.2 (`src/brainir/methods/brainir_v1.py`, `research/phase2/BRAINIR_V1_METHOD.md`)

A fresh oracle-free agent composed BrainIR in the clean room from the candidates' code and documents and aggregate selection results.
- **v1.0** was the first composition.
- **v1.1** answered reviews A and G. It was developed on adversarial instances the composer built with the third-party generator,
  with aggregates of the held-out adversarial suite.
- **v1.2.0** answered review B. It changed the selection statistics only.

The locked method, in order:

1. **Restriction.** Exact structural reachability and signs, then an activity filter verified by one simulation decision.
2. **Canonical order.** A permutation-equivariant structural relevance order replaces any random or index-based order. The search is
   deterministic given the seed and independent of the node order up to exact automorphisms.
3. **Group elimination** over keep-only sets in that fixed order, until the kept set is 1-minimal (the canonical set). Every
   accept/reject decision is a sequential strict majority over parameter replicates on which the intact network works, extended when
   they disagree.
4. **Necessity in the intact network.**
   - A pooled single-silencing test of every canonical member gives the essential claims.
   - A masking-proof screen covers the other active candidates: flagged inhibitory neurons and the most relevant ones are silenced
     alone, the rest in two independent partitions.
5. **Alternatives.** A deterministic enumeration of other sufficient sets, whose members' necessity is tested too. Every candidate is
   completed with every neuron found essential anywhere in the run.
6. **Admissibility-first selection.** A candidate can become THE mechanism only if:
   - its sufficiency validates decisively on fresh replicates;
   - every member participates in the intact network (graded activity or measured necessity);
   - its keep-only dynamics are not decisively further from the intact network's than another candidate's.

   Among admissible sets, a round robin compares every pair on the intact network's reliance on the pair's distinctive members
   (paired failure counts, then graded readout changes against the noise band), then Occam, then robustness. A posterior within a
   factor-2 band of the decisiveness threshold is a tie, and tied sets share the probability mass. Exchangeable, marginal copies are
   merged when their union validates better. A mechanism whose members are all exchangeable with neurons outside it is flagged as
   degenerate.
7. **Outputs.**
   - A minimality certificate, a final fidelity on reserved replicates and a size–error curve.
   - Evidence-count (Beta-posterior) inclusion probabilities, essential claims, generic roles and simulated edge-removal predictions.
8. **Cross-connectome step.** It runs after the core is final and draws from the same budget pool, at most 25 %. The core is carried
   to the other connectome and verified there. Identity claims are made only for a verified, complete link; otherwise only a
   role-level alignment is reported.

**Components.**
- **Kept:** from greedy_plus, the restriction, group elimination and essential screen; from group_probe, the canonical-order idea; from
  joint (as fixed after review E), the verified transfer.
- **Dropped:** the surrogate, random restarts and orders, cross-entropy sampling, the evolutionary search and group_probe's posterior
  bookkeeping. Each drop is justified by selection evidence (method document §§5–7).
- **Absent:** v1.2 contains no dataset name, neuron identifier, cell type, mechanism size or instance-specific threshold. This is
  checked by reviews B and D, `tests/test_leakage_guard.py` and the static rules of `tests/test_budget_integrity.py`.

## 8. Synthetic evidence for the locked method

### 8.1 Confirmation on untouched mechanisms (`mechanisms_v1_final`, used once, after the freeze)

**Design.** The confirmation-role suites were built with secret salts before any method ran on them. They never entered the clean
room. Each was used by exactly one run, after the freeze at c3362c0 and before the lock (review C, Q1).
- `mechanisms_v1_final`: 57 instances, 2 node orders × 3 seeds, 1,000 calls, robust checks.
- Results: `conf_mech_b1000.md`; paired comparison `cmp_conf_greedy_reference.md`.

| metric | BrainIR v1.2 | greedy_reference | difference [95 % CI] |
|---|---|---|---|
| structural success | 1.000 | 0.754 | +0.246 [+0.140, +0.360] |
| success_intact (the mechanism the intact network uses) | 1.000 | 0.576 | +0.424 [+0.295, +0.553] |
| causal functional success | 1.000 | 0.155 | +0.845 [+0.754, +0.924] |
| essential recall | 1.000 | 0.728 | +0.272 [+0.172, +0.378] |
| identity Jaccard / identical cores (reliability) | 0.958 / 0.930 | 0.803 / 0.526 | +0.155 [+0.096, +0.217] / +0.404 [+0.281, +0.526] |
| calls, mean (median) | 150 (115) | 290 (236) | 140 fewer [85, 202] |
| keep-only pass, sd × 2 / weight noise (robustness) | 0.954 / 0.851 | 0.733 / 0.670 | +0.221 [+0.114, +0.332] / +0.181 [+0.073, +0.292] |

**Pre-registered decision rule** (protocol §5, amended §8):
- (a) success not lower on structural success and on `success_intact`: holds;
- (b) at least one advantage in reliability, efficiency or robustness with a paired CI above 0: holds on all three.

**BrainIR v1.2 was therefore locked.** Review C re-derived every number from the records. The rule survives instance-level sign tests
and Holm adjustment. The one exception is weight-noise robustness: significant by the pre-registered bootstrap, but not by an instance
sign test (24 vs 18 instances, p = 0.44).

**What the gap means (review C, C4).** greedy_reference keeps the frozen baseline's k = 3.
- On the 12 instances whose smallest sufficient set has more than 3 neurons, its structural success is 0.33, against 1.00, with a
  median core of 13.5 neurons. These instances carry 57 % of the structural gap.
- On the other 45 instances it is 0.87 against 1.00, and its causal functional success is 0.11, because k forces non-minimal cores.

The gap is therefore largely built into greedy's k. The k-free comparisons below are the informative ones.

### 8.2 The locked method against the strong candidates (review C, C1)

**Held-out mechanisms** (selection role, whose aggregates the composer saw). Runs are paired with the candidates' selection runs; the
files are `cmp_sel_v12_*.md`.

| v1.2 vs | success (structural / causal) | identity Jaccard / identical | calls | robust sd × 2 / weight noise | rule |
|---|---|---|---|---|---|
| greedy_plus | equal (1.00 / +0.003) | +0.086 [+0.033, +0.146] / +0.19 [+0.09, +0.30] | **38 more** [30, 46] | −0.012 / −0.024 (n.s.) | passes (reliability) |
| cem_search | equal (1.00 / +0.003) | +0.058 [+0.011, +0.110] / +0.14 [+0.05, +0.25] | **32 more** [18, 43] | +0.006 / +0.012 (n.s.) | passes (reliability) |
| group_probe | equal / +0.047 [+0.006, +0.102] | +0.021 (n.s.) / +0.088 [0.000, +0.175] (n.s.) | 4 more (n.s.) | equal | **fails** (no CI above 0) |

On the plain generator families the locked method is **more consistent** than the k-free candidates, **not more successful**, and
**more expensive in calls** than greedy_plus and cem_search. It is not distinguishable from group_probe.

### 8.3 Adversarial traps (`adversarial_final`)

**Design and scoring.** 66 instances from review G's third-party generator, 2 node orders × 3 seeds, 1,000 calls (`conf_adv.md`;
paired `cmp_conf_adv_*.md`).
- *correct*: the core is an acceptable core; on degenerate traps, the result flags that no compact mechanism exists.
- *confident-wrong*: every core member has P ≥ 0.85, and the run is not correct.

| method | correct | confident-wrong | coverage (confident runs) | P(correct \| confident) | success_intact | essential recall | latent backup returned | mean calls / CPU s |
|---|---|---|---|---|---|---|---|---|
| BrainIR v1.2 | 0.98 | 0.01 | 0.82 | 0.991 | 0.89 | 1.00 | 0.00 | 240 / 48 |
| greedy_plus | 0.72 | 0.20 | 0.92 | 0.779 | 0.72 | 0.90 | 0.04 | 209 / 31 |
| group_probe | 0.67 | 0.24 | 0.90 | 0.730 | 0.68 | 0.98 | 0.14 | 292 / 102 |
| greedy_reference | 0.09 | 0.91 | 1.00 (0/1 probabilities) | 0.091 | 0.14 | 0.38 | 0.19 | 411 / 80 |

**Paired, v1.2 − greedy_plus:**
- better: correct +0.26 [+0.18, +0.34]; confident-wrong −0.20 [−0.26, −0.14]; success_intact +0.17 [+0.12, +0.23]; identical cores
  +0.42 [+0.30, +0.55];
- worse: **causal functional success −0.040 [−0.076, −0.010]** and **31 more calls** [17, 43].

The functional gaps come from the degenerate and subset-of-draws traps. There the correct answer (a flagged degenerate set, or the
union of copies) is by design not 1-minimal.

**v1.2 − group_probe:** correct +0.31 [+0.21, +0.40], at 52 fewer calls [10, 97].

**Protocol §8.4.** Confidence is called warranted if at least 90 % of confident runs are correct. v1.2: 322 of 325 confident runs
correct (0.991; instance-cluster CI [0.979, 1.000]), so the rule holds.

**How to read this (review C, C2 and C3):**
- **In-distribution.** This is not a test on unseen trap types. The composer built and tuned v1.1/v1.2 on the same generator (its own
  seeds), and `adversarial_final` differs only in secret seeds. None of the comparators was designed against these traps.
- **Output format.** The comparators cannot flag degeneracy, so the 36 distributed-drive runs are wrong for them by construction.
  Without them, correct is v1.2 0.978, greedy_plus 0.792 and group_probe 0.742, and the gap to greedy_plus stays +0.19 [+0.13, +0.25].
- **The truth definition changed once, before any confirmation data.**
  - What changed: after the composer reported an inconsistency, the generator's author redefined acceptable cores to contain every
    measured-essential node (2026-09-24 09:56, commit d6dc789). v1.1 had been scored confidently wrong on all 18 held-out
    `identical_decoy/nfc_band` runs under the first definition.
  - Fairness: the change was applied to every method, and all held-out files were re-scored.
  - Under the first definition: v1.2 correct 0.934 and P(correct | confident) 0.935 [0.868, 0.991], so the 90 % rule would pass on the
    point estimate only; greedy_plus 0.682 / 0.738; group_probe 0.629 / 0.679. The comparative conclusions are unchanged.
  - Residue: the re-scored held-out files keep first-definition calibration items.
- **Remaining weakness.** v1.2's only trap errors are on `subset_of_draws` (0.78 correct), where a mechanism works on some parameter
  draws only.

### 8.4 Synthetic pairs and identity claims

v1.2 ran on network a of each pair, cross-connectome step included, within the same 1,000 calls.

| suite | runs | structural / intact success | identity claims (correct) | from | false on shift / null / structural decoy |
|---|---|---|---|---|---|
| `pairs_v1_final` (easy design) | 81 | 1.00 / 1.00 | 94 (94) | 48 runs on 16 pairs | 0 / 0 / 0 |
| `pairs_v2_final` (hard design) | 81 | 1.00 / 1.00 | 28 (28) | 18 runs on 6 of 27 pairs (12, 4, 3, 3, 3, 3 claims) | 0 / 0 / 0 |

**Protocol §7.3 rule** on `pairs_v2_final`: precision 1.00 ≥ 0.8; claims on null pairs 0 % ≤ 5 %; mean confidence 0.973 within 0.10
of observed precision. The rule holds.

**The evidence behind "every claim correct" is thin (review C, C5):**
- With the pair as the unit, 6 all-correct pairs give a 95 % lower bound on precision of 0.54, below 0.8.
- 0 claims on 8 null pairs bounds the per-pair null claim rate at ≤ 0.31.
- The calibration condition is met automatically when every claim is correct.
- The rule's first version (a Brier comparison with the constant predictor) was replaced after the selection-role pairs showed
  precision 1.00. That change is disclosed in the protocol. The first version is degenerate at precision 1, so it would have failed.
- v1 is conservative: it claims in 18 of 81 runs, with core recall 0.24.

**Conclusion:** when v1 claims an identity it has not yet been wrong, but it rarely claims.

## 9. Real benchmark, oracle-free: reliability across node orders and seeds (goal3 §§20–21)

### 9.1 Design

**Frozen `greedy_prune_sim`, unchanged:**
- 8 node orders × 3 seeds per network, 24 runs each;
- order 0 is the bundle's own order, and orders 1–7 are seeded permutations (seed 1000 + k);
- keep-only fidelity on 8 fresh parameter seeds.

**BrainIR v1.2 (locked)** ran under identical orders and seeds, on the exact locked tree, before the lock was written.
- Paired by (order, seed).
- 95 % CIs resample node orders, the clusters that share a permutation. No run is paired with its own bootstrap copy (review C, C8).
- Files: `research/phase2/reliability/compare_v12_vs_greedy_*.md`.

| network | identity Jaccard (v1.2 / greedy) | modal-core frequency | keep-only pass rate | calls | simulated seconds | wall per run |
|---|---|---|---|---|---|---|
| manc_v1.2.1 | 0.80 / 0.63, +0.17 [+0.10, +0.27] | 0.75 / 0.67 | 1.00 / 0.67, +0.33 [+0.21, +0.46] | 399 / 777 | 798 / 777 (n.s.) | 992 / 327 s |
| male-cns_v1.0 | 1.00 / 0.87, +0.13 [0.00, +0.29] | 1.00 / 0.92 | 1.00 / 0.92, +0.08 [0.00, +0.21] | 386 / 550 | 772 / 550 (+40 %) | 799 / 216 s |
| manc_v1.2.3 | 0.85 / 0.65, +0.20 [+0.03, +0.40] | 0.83 / 0.67 | 1.00 / 0.67, +0.33 [+0.33, +0.33] | 403 / 755 | 806 / 755 (+7 %) | 960 / 265 s |

### 9.2 What it shows

**Reliability.**
- v1.2 is more consistent on both MANC networks. On MaleCNS it is 1.00 against 0.87, with a CI reaching 0.
- Each of v1.2's 72 cores passes keep-only on fresh seeds; 18 of the baseline's 72 do not.
- The two methods agree on the modal core of every network. Run by run, they return the same core in 15, 22 and 14 of 24
  paired runs, so v1.2's gain is consistency, not a different answer.
- Within an order, v1.2's three seeds return the same core in 3, 8 and 5 of 8 orders (manc_v1.2.1, male-cns_v1.0, manc_v1.2.3), and
  greedy's in 1, 6 and 0 (review C). The parameter draw matters as much as the order, so seeds are not replicates.
- The two MANC networks come from one reconstruction.
- The 8 × 3 design had no power analysis. It is enough for consistency on MANC, not for success on any single network (§12).

**Compute.**
- v1.2 needs about half the simulator calls, but each call simulates the bundle's full 2-second protocol; the baseline's simulates 1 s.
- In simulated time v1.2 therefore costs the same or more (+40 % on MaleCNS).
- In wall time it costs 3–4× more, because of the many full-network silencing simulations reviews A and G required.
- The honest efficiency claim is fewer queries, not less compute.

### 9.3 Sensitivity to the evaluator-calibrated amplitude gate (review D, D4)

**Design.** The locked configuration was rerun oracle-free, same design, with the real-bundle rhythm criterion's amplitude gate at
0 Hz (the public criterion) and at 1.0 Hz (the public library's default) instead of 0.25 Hz. Files:
`research/phase2/reliability/v12_gate{0,1.0}_*.md`; driver `scripts/reliability_sweep.py --criterion-gate`. These runs are not
hidden-evaluated.

**Structural outcome.** A sensitivity core that also occurs in the locked sweep inherits that core's logged structural outcome
(`reliability/gate_sensitivity_vs_logged.json`; the analysis is logged). No evaluator was run and the oracle was not read.

| network | gate (Hz) | same core as the locked run (same order and seed) | identity Jaccard | keep-only pass | cores meeting the frozen structural criterion by logged scores | cores never scored |
|---|---|---|---|---|---|---|
| manc_v1.2.1 | 0.25 (locked) | — | 0.80 | 1.00 | 20 of 24 | 0 |
| manc_v1.2.1 | 0 (public) | **24 of 24** | 0.80 | 1.00 | 20 of 24 | 0 |
| manc_v1.2.1 | 1.0 | 3 of 24 | 0.85 | 1.00 | 19 of 24 | 2 |
| male-cns_v1.0 | 0.25 (locked) | — | 1.00 | 1.00 | 24 of 24 | 0 |
| male-cns_v1.0 | 0 (public) | **24 of 24** | 1.00 | 1.00 | 24 of 24 | 0 |
| male-cns_v1.0 | 1.0 | 0 of 24 | 0.74 | 1.00 | — | 24 |
| manc_v1.2.3 | 0.25 (locked) | — | 0.85 | 1.00 | 21 of 24 | 0 |
| manc_v1.2.3 | 0 (public) | **22 of 24** (the other 2 move to the modal core) | 0.93 | 1.00 | 23 of 24 | 0 |
| manc_v1.2.3 | 1.0 | 1 of 24 | 0.85 | 1.00 | 18 of 24 | 1 |

**Without the gate** (the public criterion), the locked method returns the same cores: 70 of 72 runs identical, and the other two
move to the modal core. The evaluator-calibrated constant did not help v1.2 recover the published circuit; if anything it cost two
runs on MANC v1.2.3.

**With a stricter gate** (1.0 Hz), v1.2's answers change. It still returns cores that pass keep-only under that criterion.
- **MaleCNS.** The tie between the two inhibitory variants that v1.2 already reports flips to the other variant in 18 of 24 runs.
  Review D's audit found that this variant also meets the structural criterion. The other 6 runs return 4–6 neurons that contain the
  same excitatory pair.
- **MANC.** The modal core becomes a 4-neuron core that the locked sweep also returned. By its logged score it meets the criterion,
  with one extra neuron. The success counts barely move: 19 and 18 against 20 and 21.
- **Reading.** The discovered mechanism is robust to how the function is defined in the direction of the public criterion. Under a
  stricter one it shifts between the valid alternatives the method itself enumerates.

## 10. Cross-connectome transfer

**Real public networks, oracle-free, base method greedy_plus and greedy_reference** (`research/phase2/transfer/xfer_*.md`).
- 3 seeds, 1,000 calls per network.
- A mechanism is judged by keep-only sufficiency on 6 fresh parameter draws of its own network.
- The null is 20 random interneuron sets per run, with the same size and sign composition. It is evaluated on 3 draws.

| base method | direction | independent: both sufficient / total calls | transfer only: destination sufficient (dest. calls) | null | joint: both sufficient / total calls |
|---|---|---|---|---|---|
| greedy_plus | MaleCNS → MANC v1.2.1 | 3/3 / 426 | 3/3 (2 calls) | 0.00 | 3/3 / 268 |
| greedy_plus | MANC v1.2.1 → MaleCNS | 3/3 / 426 | 2/3 (2 + 21 adaptation calls) | 0.00 | 3/3 / 268 |
| greedy_reference | MaleCNS → MANC v1.2.1 | 3/3 / 1,069 | 3/3 (2 calls) | 0.00 | 3/3 / 405 |
| greedy_reference | MANC v1.2.1 → MaleCNS | 3/3 / 1,040 | 3/3 (2 calls) | 0.00 | 3/3 / 405 |

**BrainIR v1.2 as the base method** (`xfer_v12.md`). v1's own cross-connectome step is off here, because the transfer machinery is
what is being tested.

| goal3 §18 experiment | MaleCNS → MANC v1.2.1 | MANC v1.2.1 → MaleCNS |
|---|---|---|
| A / B: discover, then transfer only (destination sufficient, destination calls) | 3/3, 2 calls (vs 359 for independent discovery) | 2/3, 2 + 21 adaptation calls (vs 406) |
| matched random null (same size and sign composition) | 0.00 | 0.00 |
| C: joint vs independent (both sufficient, total calls) | 3/3, 423 vs 765 | 3/3, 423 vs 765 |
| D: correspondence prior only (destination calls) | 362 vs 359 (no saving) | 367 vs 406 (−10 %) |

**Reading the real-network results:**
- A mechanism discovered in one connectome is functionally sufficient in the other after anchor-based correspondence and
  verification, with almost no destination calls. It agrees with the destination's own core at Jaccard 0.80.
- These are descriptive results, with n = 3 per cell (review C, C13).
- The null shows only that random interneurons fail. It is not matched on degree or reachability, and it is evaluated on fewer draws.
- A working transfer is functional equivalence, not neuron identity (review E, finding 9).

**Synthetic pairs: does joint discovery help?** This is the pre-registered comparison of protocol §7.4, run after the review E fixes.
- Base methods greedy_plus and greedy_reference, 3 seeds, 1,000 + 1,000 calls.
- Matched on instance and seed (`cmp_arms_pairs_{v1h,v2h}.md`).
- The null arm runs the same simulations with the cross-network cues destroyed.

| pair design | base method | success (both networks): joint / independent / null | calls saved by joint vs null [95 % CI] |
|---|---|---|---|
| easy (v1 design, 26 pairs) | greedy_plus | 0.96 / 0.96 / 0.96 | +54 [+39, +68] |
| easy | greedy_reference | 0.72 / 0.72 / 0.73 | +121 [+66, +178] |
| hard (v2 design, 27 pairs) | greedy_plus | 1.00 / 1.00 / 1.00 | +14 [−0.1, +30] |
| hard | greedy_reference | 0.65 / 0.63 / 0.63 | +7 [−29, +45] |

- **Success.** Joint discovery raises success in no case.
- **Calls.** It saves calls only when correspondence is easy, and the saving comes from the correspondence: the null arm does not
  save. On hard pairs (blank hemilineage, noisy anchors, homologous backgrounds, rewired motifs, structural decoys, null pairs) the
  saving is not distinguishable from 0.
- **Identity claims.** The fixed joint mode's claims were all correct: greedy_plus 107 on easy pairs and 25 on hard, greedy_reference
  61 and 22. In the null arm, each base method still made 4 claims on easy pairs and 6 on hard pairs, one of the 6 false.

## 11. Ablations, anti-gaming checks, budget curves, calibration

### 11.1 Anti-gaming (goal3 §33)

**Design.** Five meaningless changes: reordered edge rows, re-salted interneuron tokens, stripped side / neuromere / hemilineage
annotations, appended sink-only distractors, doubled parameter spread. The set is the 47 held-out instances with n ≤ 100, seed 0.
- **Candidates** (`ag_candidates_summary.md`): greedy_plus, cem_search, group_probe, surrogate_search and greedy_reference (evo_pareto
  was not run). The four non-reference candidates lose and gain no run under any change. greedy_reference gains one run with sink
  distractors.
- **BrainIR v1.2** (`ag_v12_summary.md`): under every one of the five changes it returns **the same core as on the unperturbed
  instance in 47 of 47 instances** (identical-core rate 1.00), and success is unchanged. v1.0 had been invariant in success too
  (`ag_v1_summary.md`).
- **Power.** Success is at ceiling on this set: a 5 % loss rate would still give 0 lost runs with probability 0.09. The identical-core
  rate is the sharper test.

### 11.2 Budget curve of the locked method

`sel_curve_v12_curve.md`: seed 0, both node orders, 54 held-out instances with n ≤ 600, budgets 50 to 2,000 (108 runs per
budget). The last column counts runs in which a phase was cut by the budget; v1.2 records this in `diagnostics.flags`.

| budget | structural | success_intact | causal functional | identical cores (2 orders) | mean calls (v1.0) | runs flagged budget-limited |
|---|---|---|---|---|---|---|
| 50 | 1.00 | 1.00 | 0.95 | 0.93 | 49 (49) | 106 of 108 |
| 100 | 1.00 | 1.00 | 1.00 | 0.94 | 84 (68) | 104 of 108 |
| 250 | 1.00 | 1.00 | 1.00 | 0.94 | 114 (91) | 37 of 108 |
| 500 | 1.00 | 1.00 | 1.00 | 0.94 | 134 (100) | 4 of 108 |
| 1,000 | 1.00 | 1.00 | 1.00 | 0.94 | 136 (100) | 0 of 108 |
| 2,000 | 1.00 | 1.00 | 1.00 | 0.94 | 136 (100) | 0 of 108 |

- **Low budgets.** Success and consistency are saturated from 100 calls, so the answer found at low budgets is already the
  final one.
- **Unused budget.** v1.2 leaves most of a large budget unused: it levels off at about 136 calls, against 100 for v1.0. The extra
  calls pay for the single-silencing evidence and the admissibility checks that reviews A and G required.
- **Flagging.** Below 250 calls v1.2 flags nearly every run as budget-limited (the certificate, screen or enumeration was cut), so a
  low-budget answer is visibly marked as such.

**Candidates at 50 / 100 calls** (causal functional; identical cores):

| method | 50 calls | 100 calls |
|---|---|---|
| group_probe | 0.95; 0.91 | 0.95; 0.91 |
| greedy_plus | 0.96; 0.69 | 1.00; 0.80 |
| cem_search | 0.77; 0.65 | 0.97; 0.80 |
| greedy_reference | 0.00; 0.72 | 0.00; 0.74 |

### 11.3 Ablations

**v1.2 on the held-out adversarial suite** (`abl_v12_adv_summary.md`):
- each component is switched off alone;
- 66 instances × 2 node orders, seed 0;
- 95 % CIs resample instances, and failed runs count as failures.

The default configuration on these 132 runs: correct 0.97, confident-wrong 0.02, success_intact 0.88, identical cores 0.86, 243
calls.

| switched off (v1.2) | effect on the traps (variant − default, 95 % CI) |
|---|---|
| **necessity screen** (masking-proof screen of non-members) | **correct −0.36 [−0.47, −0.24]**; confident-wrong +0.36; essential recall −0.23; −44 calls |
| **group testing** (one candidate per probe) | **correct −0.32 [−0.43, −0.21]**; +306 calls [+235, +375]; cores +72 neurons (elimination does not finish within the budget) |
| degeneracy detection | correct −0.09 [−0.17, −0.03]; confident-wrong +0.05 (distributed drives are returned as compact mechanisms) |
| alternatives enumeration | correct −0.07 [−0.13, −0.02]; identity Jaccard −0.045; −76 calls |
| participation check | correct −0.06 [−0.12, −0.02] (silent backups are admitted); +8 calls |
| union repair | correct −0.06 [−0.12, −0.02]; causal functional +0.05 (a repaired union is not 1-minimal); robust sd × 2 −0.03 |
| canonical structural order (seeded random order instead) | +51 calls [+34, +70]; identity Jaccard −0.04 [−0.09, +0.00] (n.s.) |
| single-silencing screen of flagged / most relevant neurons | −25 calls; correct −0.02 (n.s.); confident-wrong +0.03 [0.00, +0.08] |
| member essentiality tests | −66 calls; no change in correct (the essential claims are lost) |
| reliance, tie band, second partition, necessity of alternatives, fidelity check, point uncertainty | at most ±7 calls; no significant change on the traps. The tie band and reliance exist for real-network edge cases (review B), which these traps do not contain. |

**What carries the trap-robustness.**
- **The masking-proof necessity screen** is the largest component, followed by **group testing**. Group testing buys efficiency and,
  at a fixed budget, success.
- **Degeneracy detection, alternatives, the participation check and union repair** add 6–9 points each.
- **The components added for review B change nothing here.** They were built for a failure these traps do not exercise.

**v1.0 on the held-out mechanisms** (`abl_v1_summary.md`, re-analysed with instance resampling, review C, C7). 54 instances × 2
orders, seed 0. Structural success stays 1.00 in every variant.

| switched off (v1.0) | effect (paired difference to the default, 95 % CI, instances resampled) |
|---|---|
| group testing (one candidate per probe) | +105 calls [+56, +161] |
| canonical structural order (seeded random order instead) | +18 calls [+12, +25]; identity Jaccard −0.025 [−0.086, +0.037] (n.s.) |
| minimality cleanup | causal functional success −0.065 [−0.120, −0.019]; identical cores −0.09 [−0.19, −0.02]; cores +0.18 neurons |
| adaptive replication | identity Jaccard −0.019 [−0.056, 0.000] (n.s.) |
| alternatives enumeration | −30 calls; cores +0.17 neurons (the alternatives let the smaller valid set win) |
| essentiality tests of members | −30 calls; the essential claims are lost |
| necessity screen | −6 calls; context members are lost (cores −0.09 neurons) |
| structural / activity pruning, active chunk sizes, reliance, robust objective | call changes of −6 to +4; no success or consistency change |
| decisions on 1 replicate instead of 3 | −36 calls with no loss on this suite |

### 11.4 Calibration

- **Target.** The inclusion-probability Brier score that uses the best-matching truth set as target is circular (review C, C6). The
  report therefore uses non-circular targets only: membership of any listed sufficient set, and the adversarial scorer's membership
  targets.
- **Confirmation mechanisms.** v1.2's non-circular contested Brier score is 0.10, against greedy_reference's 0.48; the circular values
  are 0.02 and 0.37.
- **Adversarial suite, reliability bins** (items; mean predicted / observed):

  | bin | items | mean predicted | observed |
  |---|---|---|---|
  | [0, 0.05) | 992 | 0.02 | 0.01 |
  | [0.05, 0.30) | 4 | 0.19 | 0.50 |
  | [0.30, 0.60) | 37 | 0.52 | 0.65 |
  | [0.60, 0.85) | 406 | 0.76 | 0.71 |
  | [0.85, 1] | 1,183 | 0.97 | 0.98 |

  The middle bins rest on 3–18 instances.
- **Summary.** The extremes are well calibrated; the middle is thinly populated. v1.0's point-versus-posterior ablation on the plain
  suite used the circular score and supports no calibration statement.

## 12. Hidden evaluation (after the lock: commit 959d689, tag `brainir-v1-preblind`)

Every hidden evaluation is logged in `research/phase2/HIDDEN_EVAL_LOG.md`, and none ran before the lock (review D, question 4).

### 12.1 Reliability sweeps scored with the frozen evaluator's structural families

One logged evaluation per method and network: 24 runs each, paired by node order and seed
(`research/phase2/reliability/compare_v12_vs_greedy_*_hidden.md`). The criterion is E-core recall 1 with the inhibitory slot filled.
The frozen baseline has the answer's size built in (k = 3), which favours it on this criterion (review D, D10).

| network | meets the frozen structural criterion: v1.2 / greedy | difference [95 % CI, orders resampled] | discordant runs (v1.2 only / greedy only), exact McNemar p | order clusters favouring v1.2 / greedy / tied, sign-test p |
|---|---|---|---|---|
| manc_v1.2.1 | 20/24 / 16/24 | +0.17 [+0.04, +0.29] | 5 / 1, p = 0.22 | 4 / 0 / 4, p = 0.125 |
| male-cns_v1.0 | 24/24 / 22/24 | +0.08 [0.00, +0.21] | 2 / 0, p = 0.50 | 2 / 0 / 6, p = 0.50 |
| manc_v1.2.3 | 21/24 / 16/24 | +0.21 [+0.04, +0.33] | 6 / 1, p = 0.125 | 6 / 1 / 1, p = 0.125 |
| pooled | 65/72 / 54/72 | | 13 / 2, p = 0.007 | 12 / 1 / 11, p = 0.0034 |

- **Per network.** v1.2 meets the criterion more often on every network. No single network's difference is significant by an exact
  test. The bootstrap CIs over 8 order clusters exclude 0 on MANC, but with so few clusters they are not trustworthy, and the exact
  tests govern.
- **Pooled.** The pooled tests are post hoc and were not pre-registered. The two MANC networks come from one reconstruction and carry
  11 of the 13 v1.2-only successes, so the evidence spans two independent reconstructions, not three.
- **Excitatory core.** v1.2's mean E-core recall is 1.00 on every network, against 0.83, 0.96 and 0.92 for greedy.

### 12.2 The blind run (`scripts/blind_eval.py`, the frozen clean-room protocol; attempt 01)

**Protocol.**
- The locked v1.2.0 ran through the frozen clean-room runner on `public_blind` at the locked seed and budget.
- `FROZEN.json` and the predictions were committed (bee81b3, 01:32:17Z) before the evaluator wrote its output (01:33:32Z).
- Evaluation: frozen evaluator 1.1.0, oracle `269661940130`, bundle `efc33d775d88`
  (`research/phase2/blind_eval/attempt_01/eval/evaluation.md`).

| network | core size | E-core recall | inhibitory slot | precision (circuit labels) | Jaccard vs reference | keep-only sufficiency | necessity claims correct | frequency error |
|---|---|---|---|---|---|---|---|---|
| manc_v1.2.1 | 4 | 1.0 | **not filled** | 0.75 | 0.40 | pass (1.00 / 1.00) | 4 of 4 | 1.27 Hz |
| manc_v1.2.3 | 3 | 1.0 | filled | 1.00 | 1.00 | pass (1.00 / 1.00) | 3 of 3 | 0.18 Hz |
| male-cns_v1.0 | 3 | 1.0 | filled | 1.00 | 1.00 | pass (0.94 / 0.88) | 3 of 3 | 0.45 Hz |

**Robustness and cross-connectome families.**
- Keep-only under weight noise 0.3: 0.00 / 0.50 / 0.88 of replicates rhythmic.
- Keep-only under doubled parameter spread: 0.88 / 0.75 / 0.75.
- Cross-connectome: v1's 2 identity claims are both correct (agreement with the curated pairs 1.00).
- Transfers MaleCNS → both MANC networks and MANC v1.2.3 → MaleCNS pass. MANC v1.2.1 → MaleCNS fails (0.31 sustained).

**How to read the blind run (review C, C15; review D, D5).**
- **It replays the sweeps.** The blind configuration (bundle order, seed 0) is the (order 0, seed 0) run of the already hidden-scored
  sweeps, and all three predictions reproduce those runs exactly. The blind run adds the evaluator's other families, not independent
  structural evidence.
- **Right result on two networks.** It returns the published core exactly on manc_v1.2.3 and male-cns_v1.0.
- **A valid alternative on manc_v1.2.1.** There it returns a different valid mechanism: a sufficient 4-neuron core with the full
  excitatory core and all 4 necessity claims correct, but without the inhibitory member.
- **That seed is a minority outcome.** In the sweep, 20 of 24 MANC v1.2.1 runs meet the criterion. The (order 0, seed 0) core appears
  in 4 of 24 runs, and the modal core in 18.
- **The single draw matches greedy's.** The frozen baseline's single Phase 1 blind run also met the criterion on 2 of 3 networks:
  on manc_v1.2.1 it returned an insufficient core with recall 0.5. The sweep comparison of §12.1, not a single draw, is the right
  comparison (goal3 §20).
- **Known in advance.** The blind predictions were known oracle-free before the lock, because development used the test networks
  (§2, D5).
- **Trajectory, evidence against steering** (review D, D5; this comparison was made by the reviewer after the lock and is logged). On
  MANC at seed 0, three development builds returned a core that fills the inhibitory slot, and each later change moved away from it:
  - a v1.0 intermediate returned the 4-neuron set with its inhibitory member swapped for the slot neuron;
  - a v1.1 intermediate returned the 3-neuron set;
  - a v1.2 build at `decisive` 0.975 returned the 3-neuron set confidently.

  The final v1.2 at `decisive` 0.975 ties the two sets. At the default 0.95, the locked setting, it returns the 4-neuron set, with
  the 3-neuron set's distinctive member at P = 0.013. The rule that turned the 0.975 result into a tie (the tie band, added after a
  real-bundle run) demoted the answer-consistent output from a win to a tie.

  The choice between the two MANC sets has sat near a decision threshold in every version (review B, B2), yet v1.2 reports it with
  confidence at seed 0. Its seed-0 answer is confidently different from the published one, while functionally valid.

## 13. Independent reviews (goal3 §47)

| review | when | findings (blocker / major / minor) | outcome | resolution |
|---|---|---|---|---|
| F computational | pre-lock | 1 / 7 / 11 | all resolved | `reviews/F_resolution.md` |
| E cross-connectome | pre-lock | 1 / 6 / 5 | harness fixes and method fixes (v1.1) | `reviews/E_resolution.md` |
| A causal | pre-lock | 1 / 3 / 5 | fixed in v1.1 (with G) | `reviews/AG_resolution.md` |
| G adversarial | pre-lock | 1 / 6 / 3 | fixed in v1.1; third-party trap suite | `reviews/AG_resolution.md`, `G_adversarial_suite.md` |
| B optimisation | pre-lock (on v1.1) | 0 / 1 / 8 | fixed in v1.2 (B2 major) or accepted | `reviews/B_resolution.md` |
| C statistics | post-lock | 0 / 5 / 10 | report and analysis fixes; no method change | `reviews/C_resolution.md` |
| D leakage | post-lock | 0 / 4 / 7 | disclosure, gate sensitivity, tooling fixes | `reviews/D_resolution.md` |

**Review F (computational), 1 blocker and 7 majors:**
- **Blocker:** failed runs had dropped out of the success denominators. No selection run had failed, so no reported number changed.
- **Majors:**
  - the call budget was not enforced against bypass (now guarded at runtime and statically);
  - unseeded weight noise was cached under one key;
  - the Modal environment was unpinned;
  - provenance recorded the commit at registration time;
  - node-order reliability is confounded with parameter draws (documented; both compared methods face it);
  - the hidden-evaluation gate was not bound to the locked method;
  - one tie-break was unstable.

**Review E (cross-connectome), 1 blocker and 6 majors:**
- **Blocker:** identity-claim confidence came from structural alignment, not from identity evidence, so v1.0 claimed non-homologous
  neurons as identical under implementation shifts.
- **Majors:** joint discovery manufactured agreement; "verified" transfer accepted unvalidated sets; the joint advantage was an
  efficiency gain under easy correspondence; the synthetic pairs made correspondence nearly free; v1's cross-connectome calls were
  counted but not budgeted; the harness could not show that synthetic truth stayed out of the method's reach.
- **Fixes:** one budget pool, a truth guard and static rules, identity scoring on every pair type, pooled-budget and null arms, the
  harder pair design, and the composer's method fixes.

**Reviews A and G (causal, adversarial) reached the same blocker independently.** v1.0 chose among keep-only-sufficient sets without
asking whether the intact network uses them.
- **Latent backups.** A backup kept silent behind an inhibitory gate was returned at P = 0.90, and the circuit that runs was demoted:
  17 of 22 runs on review G's traps.
- **Masked gates.** The group-silencing screen missed essential inhibitors masked by what they gate: 28 of 28 runs at n ≥ 150.
- **The metrics were blind to both.**
- **Response:**
  - participation-aware scoring and new metrics;
  - graded activity and edge-removal queries;
  - a third-party trap suite;
  - protocol amendment §8;
  - v1.1: admissibility-first selection, single-silencing evidence and a masking-proof screen.

**Review B (optimisation).**
- The search is correct and efficient.
- The major finding: a real-network choice between two valid cores was decided at the threshold edge by an unsuitable t test.
- v1.2 answered with paired discordant counts and a tie band.

**Review C (statistics).**
- The lock stands statistically.
- The report was corrected on all five majors: comparisons with the strong candidates (§8.2), the in-distribution adversarial
  confirmation and its truth-definition change (§8.3), k = 3 (§8.1) and the thin identity-claim evidence (§8.4).
- Also resolved: clustered CIs (§9), instance-level ablation CIs (§11) and the blind run as one draw (§12).

**Review D (leakage).** See §2 and §9.3.

## 14. Compute and cost

**Source.** The experiment registry (`benchmarks/dng100/manifests/experiments/index.jsonl`, summed by `scripts/phase2_costs.py`).
Costs are upper-bound estimates: every container-second is billed at list price.

| kind | registry runs | est. cost (USD) | wall (h) |
|---|---|---|---|
| confirmation (mechanisms, pairs, adversarial) | 4 | 83 | 1.8 |
| held-out runs of v1.0 / v1.1 / v1.2, and of the comparators on the adversarial suite | 13 | 87 | 2.1 |
| ablations (v1.0 on mechanisms; v1.2 on the adversarial suite) | 31 | 92 | 2.7 |
| joint vs controls on synthetic pairs | 4 | 41 | 1.0 |
| budget curves (candidates, v1.0, v1.2) | 26 | 45 | 1.7 |
| reliability sweeps (frozen greedy, v1.2) and gate sensitivity | 12 | 39 | 6.2 |
| selection and pair tournaments (candidates) | 4 | 22 | 0.8 |
| transfer experiments | 3 | 11 | 1.6 |
| anti-gaming (candidates, v1.0, v1.2) | 18 | 11 | 0.7 |
| smoke run (local) | 1 | 0 | 0.0 |
| **total, Phase 2** | **116** | **≈ 432** | **18.7** |

**Totals.** Together with Phase 1's ≈ $38, the project's registered Modal estimate is about $470. The largest single runs were the
confirmation adversarial suite ($49; 1,584 runs of four methods), the hard-pair arms campaign ($33), the confirmation mechanism suite
($28) and the no-group-testing ablation ($20).

**Not in the registry:**
- suite builds, truth audits and participation re-classifications (mostly local; the two audits that recorded a Modal cost total
  $0.74);
- the local blind evaluation;
- the agents' own work.

## 15. Limitations and failures

1. **The benchmark cannot separate the methods structurally.**
   - Any keep-only pruning search recovers the published circuit most of the time (Phase 1 protocol §5), and the frozen baseline has
     the answer's size built in.
   - v1.2's structural advantage is a higher rate over node orders and seeds (65/72 vs 54/72), significant only when pooled post hoc.
   - Its single blind draw matches greedy's 2 of 3.
2. **Mechanisms are not unique, and v1.2 does not always return the published one.**
   - On MANC v1.2.1 there are at least two valid sufficient sets. v1.2 returns the published one in 20 of 24 draws, and at the locked
     seed it confidently returns the other.
   - On MaleCNS it reports a tie between two variants.
   - The choice among valid sets is a heuristic, admissibility first and then reliance and Occam (review B, B4). It is not a
     principled identification of "the" mechanism.
3. **Efficiency is in calls, not compute.**
   - v1.2 uses half the baseline's calls, but equal or more simulated time and 3–4× the wall time.
   - On the synthetic suites it uses more calls than greedy_plus and cem_search.
4. **The adversarial evidence is in-distribution** (§8.3). A trap family designed without the composer's knowledge was not built.
5. **Identity claims are rare** (18 of 81 runs on hard pairs) and **rest on few pairs** (6).
6. **Joint discovery helps only under easy correspondence**, and raises success nowhere.
7. **Leakage of structure** (§2): the answer's size and composition and one calibrated threshold reached the development environment.
   Isolation was procedural, and development used the test networks.
8. **Parameter uncertainty.** Robustness on the real networks is moderate: the blind MANC v1.2.1 core fails under weight noise 0.3, and
   a mechanism that works on only a subset of parameter draws is v1.2's weakest trap type (0.78).
   - **Criterion strictness.** The exact neuron-level answer depends on how strictly "rhythmic" is defined. It is unchanged without
     the amplitude gate, but a 1.0 Hz gate moves it among the valid alternatives (§9.3).
9. **Statistics.** No non-inferiority margin or multiplicity rule was pre-registered. The real-network sweeps had no power analysis.
   The transfer results have n = 3 per cell, with a weak null.
10. **Roles are generic labels** (driver, recurrent excitatory, feedback inhibitory, …). They agree with the oracle's roles on the blind
    run (3 of 3 labelled neurons per network), but role inference was not the focus and is first-level only.

## 16. Acceptance criteria (goal3 §50)

| # | criterion | met? | evidence |
|---|---|---|---|
| 1 | Frozen Phase 1 benchmark unchanged and valid | yes | `freeze.py --check` green at the end of the phase; no commit touches a locked benchmark file (review D, question 5) |
| 2 | Public-only clean discovery environment | yes, with disclosed gaps | `C:\Dev\BrainIR_p2clean`; answer structure, tier B for 8 h and procedural isolation are disclosed (§2) |
| 3 | Substantial synthetic suite | yes | 10 families × complications × n 50–3,000, in development / selection / confirmation roles; easy and hard pair designs; third-party trap suite (§3) |
| 4 | Multiple algorithm families seriously evaluated | yes | 5 candidates + cross-network component + reference on 342-run held-out tournaments, budget curves and pair tournaments (§§5–6) |
| 5 | Coherent mathematical algorithm | yes | `BRAINIR_V1_METHOD.md` §2 (formulation), §§3–4 (algorithm, decisions and stopping) |
| 6 | Benchmark-generic, no DNg100-specific logic | yes | no dataset, id, type, size or instance threshold in the method (reviews B and D, leakage guard, static rules). The library's real-bundle rhythm gate came from the evaluator (§2, §9.3). |
| 7 | Simulator calls explicitly budgeted | yes | `BudgetedSimulator`: hard budget, one pool per run, runtime and static enforcement (review F) |
| 8 | Active intervention selection investigated | yes | group_probe (active Bayesian), surrogate_search (Thompson/UCB), v1's adaptive replication and active chunk sizes; ablated (§11.3) |
| 9 | Group / compressive probing investigated | yes | group testing; switching it off costs +105 calls [+56, +161] (§11.3) |
| 10 | Robust discovery across parameter uncertainty | implemented and evaluated | replicate-based decisions, robust objective, doubled parameter spread and weight-noise checks, subset-of-draws traps, gate sensitivity (§§8, 9, 11) |
| 11 | Mechanism uncertainty represented | yes | Beta-posterior inclusion probabilities, ties, enumerated alternatives, degeneracy flag, calibration (§§7, 11.4) |
| 12 | Minimality testing | yes | 1-minimality, minimality certificate; cleanup ablation −0.065 causal functional (§11.3) |
| 13 | Generic role inference, first level | yes | generic roles; synthetic role accuracy 0.95; blind role agreement 3 of 3 labelled neurons per network (§§6, 12.2) |
| 14 | Cross-connectome transfer supported | yes | v1's budget-pooled cross-connectome step, `joint.py`, transfer experiments A–D (§10) |
| 15 | Works beyond one oscillator | yes | success 1.00 on all 10 families (held-out and confirmation); 6 trap types (§8) |
| 16 | Phase 1 greedy rerun fairly | yes | frozen script, unchanged, same orders and seeds, 8 × 3 per network; the re-expressed algorithm on the synthetic suites. Its k = 3 is disclosed (§§8.1, 12.1). |
| 17 | Reliability across seeds / orderings quantified | yes | real-network sweeps with order-clustered CIs; synthetic identity consistency (§§8, 9) |
| 18 | Query-efficiency curves | yes | budget curves 50–2,000 calls for all candidates, v1.0 and v1.2 (§§6, 11.2) |
| 19 | Robustness quantified | yes | doubled parameter spread, weight noise, anti-gaming transforms, criterion-gate sensitivity (§§8, 9.3, 11.1) |
| 20 | Cross-connectome results quantified | yes | real transfer A–D with a null; synthetic joint vs controls; identity-claim scoring; blind cross family (§§8.4, 10, 12.2) |
| 21 | Important ablations complete | yes | 14 components of v1.0 (held-out mechanisms) and 15 of v1.2 (held-out traps) (§11.3) |
| 22 | Blind code and config locked before hidden evaluation | yes | `METHOD_LOCK.json`, commit 959d689, tag `brainir-v1-preblind`; the gate refused two pre-lock attempts (review D) |
| 23 | Blind evaluation uses the frozen clean-room protocol | yes | `scripts/blind_eval.py` → `cleanroom/run_method.py` → frozen evaluator 1.1.0 (§12.2) |
| 24 | Hidden-oracle attempts explicitly logged | yes | `HIDDEN_EVAL_LOG.md`: 6 sweep evaluations, the blind freeze and evaluation, and review D's audit comparison |
| 25 | Phase 2 tests pass | yes | full suite **552 passed**, 1 opt-in Modal consistency test skipped (`research/phase2/TESTS_final.txt`, 7 min 36 s) |
| 26 | All Phase 0/1 tests still pass | yes | the same run includes every Phase 0/1 test and the real-data tests |
| 27 | Independent audits completed | yes | reviews A–G (§13) |
| 28 | Serious audit findings resolved | yes | every blocker was fixed before the lock (F, E, A, G); B's major was fixed in v1.2; C's and D's majors were resolved by disclosure, corrected analysis, sensitivity runs and tooling fixes. A post-lock method change would be a new version. |
| 29 | `PHASE2_REPORT.md` exists | yes | this file |
| 30 | Clear conclusion | yes | §0 and §18 |

## 17. Final self-audit (goal3 §53)

| question | answer | evidence |
|---|---|---|
| Could greedy achieve this with equal compute? | **Partly.** v1.2's simulated time per run (772–806 s) buys about one frozen-greedy run (550–777 s), and a single greedy run is less consistent (Jaccard 0.63–0.87) and often non-functional (keep-only pass 0.67–0.92). The k-free greedy_plus matches v1.2's synthetic success with fewer calls, but it is less consistent and far less trap-robust. An ensemble of greedy runs (majority over node orders, about 8× the compute) was not tested. | §§8.2, 8.3, 9 |
| Could a random matched method achieve this? | No. | Phase 1 nulls: E-core recall ≤ 0.005, P(any published label) 0.4–3.2 %. The transfer null passes 0 times. |
| Did graph structure alone leak the answer? | Not the neurons. Phase 1's structural baselines recover at most one of the two excitatory core neurons and never a sufficient core. The answer's structural description (size, composition) did reach the development environment. | PHASE1_REPORT §8; §2 (D1) |
| Did an exact node count fingerprint the solution? | Not in v1.2: it has no size constant, and it returned 4 neurons on MANC v1.2.1. The frozen baseline has k = 3 built in. | reviews B and D; §12 |
| Did the method rely on a particular node ordering? | No by design (canonical order); consistency 0.80–1.00 across 8 orders × 3 seeds. The remaining variation comes with parameter draws, which are confounded with order. | §§7, 9, 11.1 |
| Did it exploit benchmark-specific IDs? | No. Tier-A ids are salted positions, the sweeps permute them, and the re-salted-token transform leaves results unchanged. | §11.1; `tests/test_leakage_guard.py` |
| Did a known biological name leak into a feature? | Not into the method: tier A has tokenised types and the guard scans for names. Tier B sat in the clean room for 8 h, unused (D3). The public bundle cites the model's paper (residual). | §2 |
| Did hidden evaluator output influence tuning? | No hidden evaluation ran before the lock. One evaluator constant (the 0.25 Hz amplitude gate) entered the library's real-bundle criterion, but it did not help: with the public criterion the locked method returns the same cores in 70 of 72 runs, and the other 2 move to the modal core. | review D, D4; §9.3 |
| Did the simulator cache leak oracle information? | No. The persistent cache was never instantiated, and the in-run memo is per run and oracle-free. | reviews D (question 6) and F |
| Did cross-connectome mapping reveal the answer? | No. v1 uses anchor fingerprints and bundle annotations; the curated mapping and the oracle's reference pairs are never imported. Transfer shows functional sufficiency, not identity. | reviews D and E; §10 |
| Does the method fail on a different synthetic family? | Not on the 10 generator families (1.00). On traps its weak spot is function on a subset of parameter draws (0.78). It was not tested on a trap family designed without the composer's knowledge. | §§8.1, 8.3 |
| Does the result disappear under parameter uncertainty? | No for fresh draws of the published parameter distribution: all 72 real-network cores pass. Partly under strong perturbation: the blind MANC v1.2.1 core fails at weight noise 0.3. | §§9, 12.2 |
| Is confidence calibrated or just a score? | Calibrated with respect to validity on the traps (99.1 % of confident runs correct; 93.5 % under the first truth definition), with well-populated extreme bins and a thin middle. It is not calibrated with respect to the published answer: at seed 0 on MANC v1.2.1, v1.2 is confident in a valid, non-published set. | §§8.3, 11.4, 12.2 |
| Does the method find alternative valid mechanisms? | Yes. It enumerates alternatives, reports ties (MaleCNS), finds unplanted sufficient sets on synthetic instances, and finds both valid MANC sets across seeds. It reports only one of them confidently at seed 0. | §§6, 12 |
| Would the conclusion survive a skeptical paper reviewer? | The narrow claims would. The structural-recovery advantage is weak (post hoc pooled). The leakage of the answer's structure lets a skeptic argue that the emphasis on reliability was informed by Phase 1; this is disclosed. | reviews C and D (0 blockers); §§2, 8, 9, 12 |

The narrow claims are:
- more consistent than the frozen baseline on MANC;
- always functional on fresh parameter draws;
- trap-robust in distribution;
- half the calls of the frozen baseline, but more compute.

## 18. Conclusion and the one recommended Phase 3 step

**Phase 2 is complete.** BrainIR v1.2 is a generic, deterministic, budgeted causal-discovery method: canonical group elimination,
necessity tests in the intact network, enumerated alternatives and admissibility-first selection. It was composed without access to
the answer's identity, locked, and blind-evaluated once.

**Against the frozen `greedy_prune_sim`:**
- **Better:** reliability across node orders and parameter draws on the MANC networks, and function of every returned core on fresh
  parameter draws.
- **Equal or better:** structural success. The margin is 65/72 vs 54/72 runs, significant only when pooled post hoc; one blind draw
  each gives 2 of 3 networks.
- **Better:** calls (half) and robustness on the synthetic suites and on the adversarial traps it was designed against.
- **Worse:** compute (equal or more simulated time, 3–4× the wall time).

Against the best simple candidate (greedy_plus) it is more consistent and far more trap-robust, but not more query-efficient.

**The strong success condition (goal3 §51) is partly met:**

| clause | status |
|---|---|
| a compact causal mechanism | met: 3–4 neurons, sufficient and necessary |
| without oracle leakage | met for identity; structure leaked and is disclosed |
| better reliability than greedy pruning | met on MANC; not significant on MaleCNS |
| better query efficiency | calls only, not compute |
| stable under parameter uncertainty | stable on fresh draws; weaker under strong noise |
| interpretable generic roles | first level only |
| transfers the abstract mechanism between connectomes | functional transfer in 5 of 6 runs; identity claims rare |

**What Phase 2 taught.** At the level of neurons the answer is not unique.
- Real networks carry more than one valid sufficient mechanism: the two MANC sets, and the MaleCNS tie.
- The synthetic suites carry unplanted sufficient sets.
- A method can be confidently right about validity and still return a set other than the published one.
- Transfer between connectomes preserves function without establishing neuron identity.

The structural criterion cannot separate these alternatives, and neither can more search.

**ONE recommended Phase 3 step: causal state-variable discovery.**
- **Goal:** for each discovered mechanism, and for its valid alternatives in both connectomes, identify the low-dimensional dynamical
  variables that are causally sufficient for the readout. An example is the phase and amplitude of the excitatory–inhibitory loop.
- **Test by intervening on the variables:** perturb along the latent direction, not on single neurons.
- **Test invariance:** check whether the alternative neuron-level mechanisms (MANC's two sets, MaleCNS's tie, the transferred cores)
  implement the same variables.

The evidence behind this choice:
1. Neuron-level mechanisms are non-unique, so the reusable object must sit above them.
2. Transfer already shows functional equivalence without identity.
3. Roles are only first-level labels.

A symbolic DSL or program synthesis needs to know what the variables of the program are. State-variable discovery comes first.
Phase 3 was not started.
