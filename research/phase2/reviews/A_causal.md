# Review A — does BrainIR v1 identify a causal mechanism?

Independent, oracle-free review. Dates 2026-09-23/24. I read and ran code only inside `C:\Dev\BrainIR_p2clean`. I consulted no
literature, benchmark answer, evaluator or oracle, and I modified no code. The only synthetic truth I used belongs to instances I
generated myself: the generator suite with seeds offset by 41,000,000 (salt `revA`), and constructed cases with seeds 700–859
(salts `revA_cases`, `revA_cases2`). On the real bundle I used two kinds of material, both oracle-free:
- v1's own result files from the composer's final runs (`data/synthetic/dev_v1/real/final5_*_s0/result_*.json`), which are method
  outputs;
- the public blind bundle, on which I simulated v1's own predictions with fresh parameter seeds 5000–5007. This is the check the
  composer's `real_eval.py` makes.

I reviewed `brainir_v1.py` with sha256 `9ca36c4d…`. It differs from the `3a07cf80…` in `BRAINIR_V1_METHOD.md` §7; according to the
coordinator, the difference is the `oracle` → `Prober` rename. The library files were `joint.py` `38609d27…` (as documented),
`tournament.py` `58f6047d…` and `simulator.py` `149b606b…`.

**Question.** Does v1 identify a causal mechanism, or does it identify correlated importance such as activity, centrality or
co-occurrence?

**Standard applied.** A mechanism is causal if sufficiency and necessity are established by interventions v1 actually ran, under
the parameter ensemble. I check three things:
- (a) Every member's inclusion rests on an intervention outcome. Either removing it from the keep-only set breaks the function, or
  silencing it in the intact network breaks it.
- (b) The choice among sufficient sets is made by interventions on the intact network, not by structure. No neuron whose single
  silencing breaks the function is dropped without a claim.
- (c) The claims (essential, alternatives, probabilities, roles, predictions) say what the interventions showed.

## Summary

| severity | count | findings |
|---|---|---|
| blocker | 1 | 1 |
| major | 3 | 2, 3, 4 |
| minor | 5 | 5–9 |

**Membership is causal.**
- Every member of every returned core in my runs has a failed intervention behind it: 395 member slots in 193 synthetic runs.
  Either its keep-only leave-one-out decision failed and was certified on fresh replicates, or its pooled single silencing failed.
- No member entered on graph or activity evidence alone. The activity filter is itself verified by an intervention: a neuron silent
  in the analysis window but necessary was kept in 18 of 18 runs.
- Highly active, highly central or perfectly co-active neurons that are not needed were excluded in every constructed run (27 of
  27), with probability 0.03.
- The generator's hub and misleading-centrality distractors were excluded in 52 of 56 cases. The other 4 are sufficient on their own
  (audited). v1 returned them as the core or as a tied alternative.

**Which sufficient set v1 returns is not decided causally.**
- v1 compares candidate sets by keep-only validation, then size, then stress, then structural order. In this comparison it consults
  the intact network only through a set-level "reliance" statistic, and only between sets of different size. Context members found
  by the screen are added to every candidate alike.
- As a result it can return a set the intact network does not use, while discarding its own positive necessity measurements.
  - A generator instance (negative-feedback controller with a backup copy), 6 of 6 runs: the returned core can be silenced with no
    effect (16 of 16 seeds pass). The planted inhibitor, which v1 itself measured as essential (0 of 6 pooled replicates pass), is
    reported at probability 0.15 with no claim.
  - A constructed latent pathway, 10 of 10 runs: the pathway the intact network uses, both of whose members are essential, is tied at
    0.45 and labelled `redundant_backup`.
- The group-silencing screen is non-monotone. At realistic pool sizes (groups of 20–30 neurons) it clears neurons whose single
  silencing breaks the function when the same group also contains the neuron that makes them necessary (a suppressed competitor or a
  suppressor). A lateral inhibitor that is necessary in 8 of 8 seeds got 0.03 in 9 of 9 runs.
- The tournament metrics offered as evidence (structural success, "causal functional" success) cannot see either failure. Every one
  of these runs is scored a success.

**The secondary outputs are not causal statements.**
- The pre-registered edge-removal predictions are topological guesses. On the real networks, 9 of 14 condition-level predictions are
  wrong in simulation.
- The inclusion probabilities are evidence-class constants. Their calibration evidence is circular.
- The size–error rationale is a fixed string. It is false whenever the core contains a context member or was chosen by reliance.

## What I examined and ran

**Read.**
- `CLAUDE.md`, `README.md` (head).
- `research/phase2/`: `COMPOSER_CONTRACT.md`, `SELECTION_PROTOCOL.md` (including §7), `BRAINIR_V1_METHOD.md`,
  `METHOD_DEV_CONTRACT.md`, `methods_review.md` §4–5, and `reviews/E_cross_connectome.md` (summary, findings 10–12, verdict).
- `research/phase2/selection_results/`: all files (`selection_aggregates.json` by structure).
- Code:
  - `src/brainir/methods/brainir_v1.py` and `tests/test_method_brainir_v1.py`, in full;
  - `src/brainir/discovery/{simulator, interventions, criteria, interface, tournament, guard, problem, run, synthetic,
    suite_audit}.py`, in full;
  - `src/brainir/sim/model.py`;
  - `src/brainir/benchmark/prediction.py`;
  - `scripts/cleanroom_entry/brainir_discovery_entry.py`.
- The composer's `data/synthetic/dev_v1/{build_suite, run_dev}.py`, `real_eval.py` (head) and the final real-run result files
  (method outputs).

**Ran.** At most 2 of my processes at a time. `pytest tests/test_method_brainir_v1.py` gave 30 passed (160 s).

| id | what | runs |
|---|---|---|
| R1 | my generator suite: the `default_specs()` structure with seeds + 41,000,000; 54 of 61 specs verified (47 with n = 50–60, 7 with n = 500); truth-audited (30 unplanted sufficient sets). v1 at budget 1,000, seed 0, network `main`. R1b: nfc60_42 and ff60_16 × 2 node orders × seeds 0–2 | 54 + 12 |
| R2 | constructed cases C1–C5, n = 30, 3 verified instances each, 2 node orders × seeds 0–2 | 90 |
| R3 | C4 and C5 inside n = 200 backgrounds; C6 and C7 at n = 30. 3 instances each, seeds 0 and 1 on `main` and seed 0 on `order1` (plus one extra seed) | 37 |
| R4 | traced re-runs of nfc60_42, c4L_800 and c5L_800, logging every pooled necessity test and every screen group; wrappers only record, and the outputs are identical to R1/R3 | 3 |
| R5 | v1's 7 edge-removal predictions from its final real runs, simulated on the public blind bundle, plus single silencing of the tied members (seeds 5000–5007) | — |

**Independent checks** (unbudgeted simulator, my seeds; v1 queries only seeds below 5,000):
- For each core member: keep-only leave-one-out and single silencing on 16 seeds (5000–5015). Also silencing of the whole core, and
  keep-only of the core.
- For each alternative: sufficiency, leave-one-out and silencing on 8 seeds.
- Single silencing of a pool on 8 seeds:
  - every structurally possible candidate (n ≤ 60);
  - v1's K0 plus the core, on 4 seeds (n = 500);
  - motif, alternative and complication nodes (R3).
- Removal of each member's predicted strongest in-core edge (zeroed in `W`), in the intact network and in the keep-only core, on 8
  seeds.
- The size–error curve's search-path sets, recovered by instrumentation, on 16 seeds.

"Essential (mine)" means that single silencing fails on the majority of the seeds on which the intact network passes, which is v1's
own conditioning.

## Findings

### 1. [blocker] The choice among sufficient sets ignores intact-network necessity: v1 discards its own essential measurements and can return a core the intact network does not use

**Evidence (code).**
- `select()` (`brainir_v1.py:1121–1225`) compares candidates in this order:
  1. keep-only validation on 3 fresh seeds;
  2. size (Occam);
  3. stress;
  4. canonical structural order (`compare`, 1194–1210).
- The intact network enters only through `relied_more`, and only when sizes differ (1144, 1202–1206). Between equal sizes, the
  canonical (structural-relevance) order decides (1210).
- The pooled necessity results for the canonical set's members (982) are not an input to `select`. After selection:
  - `essential_out` keeps only the chosen core (1050);
  - `probabilities` gives members of a "decisively worse" set a floor of 0.15 (1342).
- Reliance silences a candidate's distinctive members all together (1161). This is non-monotone: when a member and its compensating
  partner are silenced at once, the member's own necessity is hidden.

**Evidence (runs).**
- **nfc60_42**: a generator negative-feedback controller whose excitatory member E (41) has a half-weight backup copy (42). The result
  is identical in 6 of 6 runs (2 orders × 3 seeds).
  - The canonical elimination finds the planted {I (19), E (41)}.
  - The R4 trace shows v1's own pooled test: `necessity_test 19: essential true, pass_fraction_silenced 0.0, n_seeds 6`.
  - The disjoint search then finds the copy {42} alone.
  - Reliance per member is 0.030 for {19, 41} against 0.023 for {42}. This is small because silencing 19 and 41 together lets the
    copy take over. It is not decisive, so the size rule applies and the core is `[42]`.
  - Output: `essential {42: False}`, p(42) = 0.90, p(19) = 0.15, and no claim about 19.
  - My checks: silencing 19 alone fails 16 of 16 seeds. Silencing the returned core passes 16 of 16.
  - The scorer counts the run as a structural success (the audit lists {42}) and a causal-functional success.
  - The same happens in the other node order: core `[5]`, and the essential inhibitor gets 0.15.
- **C4, latent pathway, n = 200** (10 of 10 runs).
  - Chain c (c1 → c2) carries the readout. Chain a (a1 → a2) has larger synapse counts and is held near threshold by an inhibitor D.
    Keep-only removes D, so chain a is sufficient in isolation.
  - v1 returns {a1, a2}. Both are non-essential: v1's pooled tests pass 6 of 6, and mine pass 8 of 8.
  - {c1, c2} is tied at 0.45 and labelled `redundant_backup` (0.5).
  - My checks: silencing c1 or c2 alone fails 8 of 8 seeds (5 of 8 in one instance). Silencing the returned core passes 16 of 16.
  - Why the intact network's pathway is lost: the screen cleared c1 and c2 (finding 2), and the equal-size tie then fell to the
    canonical order.
- **ff60_16 and ff500_56** (generator feed-forward drivers with hubs, 7 runs). The core is one hub, tied at 0.45 with the
  misleading-centrality node, although v1 had already measured reliance on both:

  | instance | reliance per member: hub | reliance per member: misleading-centrality node |
  |---|---|---|
  | ff60_16 | 0.082 | 0.017 |
  | ff500_56 | 0.104 | 0.023 |

  The planted chain gets 0.15. No neuron is essential there, so the core is valid. The 0.45 split, however, contradicts
  intervention evidence v1 has already paid for.
- **Real MaleCNS** (v1's own final run).
  - Candidates:

    | candidate | reliance | per-replicate range |
    |---|---|---|
    | [653, 1052, 2152] | 0.268 | 0.24–0.30 |
    | [653, 1052, 2948] | 0.056 | 0.03–0.08 |

  - Every replicate agrees. The difference, 0.21, exceeds v1's own decisiveness threshold max(0.05, 0.25 × 0.268), so
    `relied_more` would say yes.
  - `compare` never asks at equal size, so both are reported at 0.45.
  - My check: silencing 2152 alone passes 8 of 8 seeds, and so does silencing 2948. Neither is essential.
- **Rules violated.**
  - The contract: "Compactness must never remove a member whose removal breaks the function" (`COMPOSER_CONTRACT.md:50–51`).
  - The method's own objective: "(iii) causally used" (`brainir_v1.py:6`).

**Fix.**
1. Make measured necessity a hard constraint. Every neuron with a positive pooled necessity test must be in the returned mechanism
   or carry an explicit essential claim. This covers canonical members, screen isolates, and members of alternatives. A candidate
   that lacks such a neuron cannot win.
2. Before any structural tie-break, and at every size, give each candidate its distinctive members' pooled single-silencing results.
   This costs at most about 5 candidates × 3 members × 6 replicates in full-network calls.
3. Apply the existing decisive-reliance rule, where every replicate agrees and the margin is met, at equal size as well. Fall back
   to canonical order only when reliance is not decisive.
4. Emit essential claims, with their pass fraction and n, for every neuron tested, not only for core members.
5. Add regression tests for the backup-copy controller and the latent pathway.

### 2. [major] The group-silencing necessity screen is non-monotone: at realistic pool sizes it clears neurons whose single silencing breaks the function

**Evidence.**
- **Code.** `necessity_screen` (483–541) clears every member of a group whose joint silencing passes (509–510). That is valid only if
  silencing is monotone. The pool is ordered most relevant first (986), and the first group is 25 % of the pool (492).
- **Group sizes.** In my n = 200 cases the first group held 20–24 neurons. In v1's real runs the pools were 84 (MANC) and 118
  (MaleCNS), so the first groups held about 21 and about 30 neurons.
- **C5, winner-take-all with a weakly active loser, n = 200** (9 of 9 runs).
  - The R4 trace for c5L_800 shows the first group of 20 silenced, containing B (37), IA (56) and IB (7). The group passes because
    A wins unopposed, so IA is cleared.
  - Output: core {A}, p(IA) = 0.03, and no claim about IA.
  - My checks: silencing IA alone fails 8 of 8 seeds in all three instances.
  - The same motif at n = 30, where groups have 1–2 neurons: IA found in 18 of 18 runs.
- **C4 at n = 200.** The first group of 24 contains c1 (10), c2 (37) and the suppressor D (177). It passes because the latent chain
  is released. At n = 30, c1 and c2 are found in 18 of 18 runs.
- **Not covered by the documentation.** The documented failure mode 4 ("synergy only", `BRAINIR_V1_METHOD.md:287`) is about two
  members that compensate each other. It does not cover this case, where the group contains the very neuron whose activity makes the
  member necessary. The same masking weakens reliance (finding 1).
- **Real runs.** The MANC screen ran 12 tests and the MaleCNS screen 6, over 84 and 118 neurons. A passing group of about 21–30 real
  neurons is no evidence that each member is individually non-necessary.

**Fix.**
- Silence singly the top-k relevant active candidates, and group-test only the rest. For example, k = 30 × 3 replicates is about 90
  full-network calls. At about 2.4 s of CPU per simulated second of the 4,600-neuron network, that is roughly 4–7 minutes.
- Alternatively, split any passing group that contains an inhibitory neuron with an edge into or out of the group or M1 before
  clearing it.
- Record the cleared groups in the diagnostics.

### 3. [major] The edge-removal predictions are topological guesses: wrong on the canonical E–I motif and on both real networks, and absent from the frozen schema

**Evidence (code).** `edge_predictions` (641–713) decides from in-core reachability and cycle membership (700–706). Weights and
simulations play no part. The basis `redundant_route` means "preserved" in both the intact network and the core.

**Evidence (runs).** I zeroed each member's strongest in-core edge and simulated 8 fresh seeds. Each cell below gives the number of
wrong predictions out of the number made.

| population | predictions | wrong in ≥ 1 condition | "preserved", intact | "preserved", keep-only core | "breaks", intact / core |
|---|---|---|---|---|---|
| R1 generator suite | 126 | 34 (27 %) | 21 / 49 | 23 / 33 | 1 / 77, 0 / 93 |
| R2 cases (n = 30) | 180 | 72 (40 %) | 69 / 90 | 36 / 72 | 0 / 90, 0 / 108 |
| R3 cases | 64 | 24 (38 %) | 18 / 40 | 18 / 18 | 4 / 24, 4 / 46 |
| real runs (R5) | 7 | 7 | 2 / 7 | 7 / 7 | — |

- Every `redundant_route` prediction was wrong in at least one condition: 123 of 123 synthetic and 7 of 7 real.
- **The canonical case.** For every E–I pair, the E self-excitation or E → I edge (about 100 synapses) is predicted "preserved" in both
  conditions, at confidence 0.6. The generator's truth lists these as critical edges.
  - Where the pair is the only oscillator (the ei, nfc, C1, C3, C6 and C7 instances), removing the edge breaks the function in 8 of 8
    seeds in both conditions.
  - In redundant designs the intact-network prediction is right, but the in-core prediction is still wrong.
- **Real runs.** In-core removal breaks the function in 7 of 7 cases (0 of 8 seeds pass each). Removal in the intact network breaks
  it for MaleCNS 1052 → 653 (465 synapses, 0 of 8) and MANC 2973 → 2825 (539 synapses, 0 of 8). Both edges join members that v1
  itself claims are essential.
- **"Pre-registered".** The contract says these are "pre-registered: the evaluator checks them" (`COMPOSER_CONTRACT.md:47`). However,
  `to_prediction` exports no diagnostics (`interface.py:58–93`), and `NeuronClaim` carries only `essential` (`prediction.py:36`).
  The predictions exist only if the run also writes `--result-json`, which the clean-room entry does not do by default.

**Fix.**
- Add a generic edge intervention to the library (for example `Intervention.remove_edges`, charged as a call). Then simulate each
  member's strongest in-core edge: 3 keep-only calls and 3 full-network calls. Otherwise emit these predictions as unknown.
- Calibrate the confidences. "Preserved" at 0.6 was wrong in 29–100 % of cases, depending on population and condition. "Breaks" at
  0.75 was right in 83–100 %.
- Write the predictions to a hashed artifact.

### 4. [major] Inclusion probabilities are evidence-class constants; their calibration evidence is circular, and they cannot express partial or joint necessity

**Operational meaning** (`probabilities`, 1308–1344). Let T be the returned core plus the candidates v1 could not separate from it.
Then p_i = (1/|T|) Σ_{C ∈ T, i ∈ C} c_i(C), where:
- c_i = 0.97 if i's pooled single silencing failed, else 0.90 (0.60 if the budget ran out);
- members of decisively worse sets are floored at 0.15;
- non-members get 0.03, 0.01 or 0.002.

So p_i is "membership in a set drawn uniformly from v1's unresolved answers, times a fixed reliability". It is not a posterior. It
ignores replicate counts and measured pass fractions. Each population uses 4–8 distinct values.

**Reliability diagram** (R1, 54 runs, 5,462 candidate probabilities). Each cell is the observed frequency of the target.

| p (n) | member of best-matching truth set (tournament target) | member of any truth-listed sufficient set | essential in the intact network (mine) |
|---|---|---|---|
| 0.002 (1,504) | 0.00 | 0.00 | — |
| 0.01 (1,154) | 0.00 | 0.00 | 0.00 |
| 0.03 (2,615) | 0.00 | 0.003 | 0.00 |
| 0.15 (46) | 0.00 | **0.80** | 0.02 |
| 0.45 (26) | 0.50 | **1.00** | 0.12 |
| 0.90 (19) | 1.00 | 1.00 | 0.00 |
| 0.97 (98) | 0.99 | 0.99 | 0.99 |

```
p = 0.97  |########################################| 0.99   (tournament target)
p = 0.90  |########################################| 1.00
p = 0.45  |####################                    | 0.50
p = 0.15  |                                        | 0.00   (vs 0.80 against "any sufficient set")
p = 0.03  |                                        | 0.00
```

**Why this is not calibration evidence.**
- **The target is circular.** The tournament target is the truth alternative with the largest overlap with v1's own core
  (`tournament.py:47–60`). Core members therefore count as members by construction, and a symmetric tie scores 0.5 by construction.
- **The Brier score is dominated by trivial neurons.** Brier is 0.0021 over all candidates and 0.0040 over K0. It is dominated by the
  2,658 structurally excluded or silent neurons (0.002 and 0.01) and the 2,615 cleared ones.
- **"Decisively worse" does not mean "not a mechanism".** Measured against every sufficient set in the truth, the 0.15 class is
  under-confident by a factor of 5.
- **Partial necessity (C7)** is a booster relay B whose single silencing passes 31–88 % of my 16 seeds, depending on the instance and
  node order.
  - v1's own pooled silencing pass fractions for B were 0.29–0.43 in six runs. Each time it claimed essential with p = 0.97.
  - The fractions were 0.67–0.71 in two runs, giving p = 0.45; in the ninth run B was excluded (0.03, no claim).
  - Five of the eight claims disagree with my 16-seed silencing. v1 records the measured fraction in
    `intervention_predictions` but does not use it.
- **Joint necessity (C3).** Two parallel inhibitors each get 0.45. Silencing either alone passes 15–16 of 16 seeds, while silencing
  both fails 16 of 16 in all six networks. "At least one of them" is certain, but nothing in the output says so.

**Fix.**
- Derive p_i from the counts v1 already holds, for example a Beta posterior on each decision's pass and fail counts, combined over
  the unresolved sets.
- Report groups that are jointly necessary.
- Score calibration against a causal target, restricted to non-trivial candidates.

### 5. [minor] Essential claims are reliable where the necessity is clear-cut, but they are narrow

**Evidence.**
- **Agreement with my 16-seed silencing.** R1 130 of 130, R2 180 of 180, R3 68 of 73. The 5 errors are all the C7 booster, with
  pass fractions of 0.50–0.69.
- **Replicates.** 6 (3 working + 3 fresh) for 94 % of claims, 7–8 for the rest.
- **The rule differs from other definitions.** A claim is made when more than half of the intact-passing replicates fail. That is
  not the generator's truth, which is pass < 0.2 on 6 seeds (`synthetic.py:423`). Nor is it the schema's "abolishes the rhythm".
  The tournament's essential accuracy of 1.00 therefore covers clear-cut neurons only.
- **Claims are made for core members only** (1050). All other pooled tests are dropped or buried, which is finding 1.

**Fix.** Report each claim's pass fraction and n, and make claims for every neuron tested.

### 6. [minor] The size–error curve's stated rationale is a fixed string that is often false, and its points cannot be audited

**Evidence.**
- **The rationale is fixed text** (1277–1278), and it is false in:
  - 5 of 54 R1 runs (winner-take-all: the path point {A} has error 0.0 below the returned {A, IA});
  - 18 of 90 R2 runs;
  - 2 of 37 R3 runs;
  - v1's real MANC run (a 3-member path point with error 0.0 below the 4-member core chosen by reliance).
- **Points carry no members.** I recovered them by instrumentation. All 390 path points agree with my 16-seed re-simulation at the
  0.5 threshold (mean |difference| 0.007–0.024), so the errors are genuine 3-seed simulations.
- **The compared candidates are not on the curve.**

**Fix.** Store the member lists, generate the rationale from the actual reason (context member, reliance, Occam), and add the
candidates.

### 7. [minor] Roles ignore the interventions v1 ran and can invert causal status

**Evidence.**
- **How roles are made.** `infer_roles` (545–638) uses sign, core wiring and criterion, with constant probabilities.
  `redundant_backup` (0.5) is given to every member of a reported alternative outside the core (1048). That includes neurons v1
  measured as essential (19 in nfc60_42) and all c1, c2 in C4 at n = 200.
- **Accuracy.** Core-member roles match generator labels in 114 of 126 cases (R1) and 253 of 253 (R2 + R3). They mirror the
  generator's vocabulary (review E, finding 10).
- **Stated probabilities are not calibrated** (R1, against generator labels).

  | stated p | correct |
  |---|---|
  | 0.75 | 64 of 76 |
  | 0.55 | 23 of 23 |
  | 0.5 (the `redundant_backup` label on alternative members) | 0 of 44 |

- **Real MaleCNS.** 2152 is labelled `inhibitory_feedback` at 0.75, yet its silencing passes 8 of 8 seeds and it is tied with 2948.

**Fix.** Condition roles on the interventions. For example, give `redundant_backup` only to non-essential members that have a
validated replacement. Calibrate the stated probabilities or drop them.

### 8. [minor] Validation, the certificate, the curve and the reported fidelity all reuse the three selection seeds

**Evidence.**
- `validate` (841–864) starts at `val_first` for every candidate, for the certificate and for the curve. `fidelity` reuses the
  selection's validation (1286). The reported fidelity is therefore that of the selected winner (winner's curse).
- **red60_11r1.** v1 reported 1.0 (3 of 3). My seeds give 9 of 16, the scorer's give 1 of 4, and the run fails causal-functional.
- **Mean bias is small.** 1.000 against 0.987 over R1.

**Fix.** Reserve 3–5 unused seeds for the final fidelity.

### 9. [minor] The selection evidence cannot see findings 1–2

**Evidence.**
- **Structural success** counts any keep-only-sufficient set listed by the audit (`tournament.py:53`, `suite_audit.py`).
- **`causal_minimality`** (`tournament.py:86–97`) checks only the returned members. It never looks for necessary neurons that are
  missing, or for a core the intact network does not use.
- **Result.** nfc60_42 (6 runs), C4 at n = 200 (10) and C5 at n = 200 (9) all score as structural and causal-functional successes.
  "Causal functional 1.00" (`SELECTION_RESULTS.md`, `BRAINIR_V1_METHOD.md` §12.3) is therefore not evidence of causal identification.

**Fix.** Report on the confirmation suite, as the protocol allows ("every other metric is reported"):
- missed essentials: neurons whose single silencing fails, over K0 on 8 or more seeds, that are neither in the core nor claimed;
- whether silencing the core ∪ tied alternatives breaks the function;
- calibration against a causal target.

## What v1 gets right (no finding)

- **Q1.** In R1, the 130 core members split as follows:

  | evidence | members |
  |---|---|
  | keep-only-necessary and essential | 93 |
  | keep-only-necessary only (redundant) | 31 |
  | essential context members | 6 |
  | neither | 0 |

  R2 has 180 members, none without such evidence. v1's own diagnostics show a failed leave-one-out decision plus a certificate, or a
  pooled silencing failure, for every member.
- **Alternatives are verified sufficient sets.**
  - 21 of 21 (R1), 18 of 18 (R2) and 12 of 12 (R3) pass keep-only on my 8 fresh seeds.
  - 3 of 51 are not 1-minimal. One contains a context member. Two are a C7 "replacement" containing a removable distractor.
  - v1 accepts them when as few as 2 of its 3 fresh seeds pass, and it never measures whether the intact network uses them.
- **Single-silencing predictions** (`silence_alone`) match my 16-seed checks wherever the necessity is clear-cut: 130 of 130 and 180
  of 180.

## Answers to the seven questions

1. **Every member is backed by an intervention.** No member entered on graph or activity evidence alone. Structure enters in two
   places:
   - the choice among sufficient sets (equal-size ties go to structural order);
   - the grouping of the necessity screen.

   Both can override interventions v1 ran or could cheaply run (findings 1 and 2).
2. **Essential claims** rest on 6–8 pooled full-network replicates. They are right whenever the necessity is clear-cut (378 of 383
   overall), and wrong only under partial necessity (5 of 8 C7 claims).
   - The real gap is missing claims: essential neurons outside the core get no claim and probability 0.15 or 0.03. This happened in
     nfc60_42 (6 of 6 runs) and in C5 and C4 at n = 200 (19 of 19 runs).
3. **The alternatives are verified keep-only-sufficient sets.** They are not verified as mechanisms the intact network uses, and
   "decisively worse" ones still include valid causes (0.80 of the 0.15 class belong to a truth-listed sufficient set).
4. **Inclusion probabilities** are evidence-class constants mixed over unresolved sets. They are calibrated only against a target
   defined by v1's own core, and they are overconfident under partial necessity (see the diagram in finding 4).
5. **Roles** are heuristics from sign, wiring and criterion. They are correct on the generator's families, but confidently wrong
   where alternatives or partial necessity are involved (finding 7).
6. **Predictions and curve.**
   - The silencing predictions are backed by simulations.
   - The edge predictions are not simulated, and are wrong at 27–40 % (synthetic) and 9 of 14 (real).
   - The curve's errors are genuine 3-seed simulations, but its rationale is not.
7. **Correlation against causation** (constructed cases, my truth):

| case | correlational signal | causal truth | v1 (runs) | verdict |
|---|---|---|---|---|
| C1 relay H | most active neuron; 2nd most central; drives every readout neuron | not needed (silencing passes 8 of 8) | {E, I}, p(H) = 0.03 (18 of 18) | correct |
| C6 follower F | oscillates in phase with the rhythm; most active; drives the readout | not needed | {E, I}, p(F) = 0.03 (9 of 9) | correct |
| C2 kick relay K | silent in the analysis window (peak 1e-4 Hz) | necessary (silencing fails 8 of 8) | {K, M}, K essential at 0.97 (18 of 18); activity filter rejected by its own check | correct |
| C3 parallel inhibitors | each is active, and each alone is unnecessary | jointly necessary | tied {E, I1} / {E, I2} at 0.45, E essential (18 of 18) | correct; joint necessity not stated |
| C4 latent pathway, n = 30 | chain a more central (larger counts) | chain c used; its members essential | {c1, c2} (18 of 18) | correct |
| C4 latent pathway, n = 200 | same | same | {a1, a2}, with c tied at 0.45 as `redundant_backup` (10 of 10) | **wrong** (findings 1, 2) |
| C5 WTA active loser, n = 30 | IA active only as a suppressor | IA necessary in context | {A, IA} (18 of 18) | correct |
| C5 WTA active loser, n = 200 | same | same | {A}, p(IA) = 0.03 (9 of 9) | **wrong** (finding 2) |
| C7 booster B | active relay | partially necessary (fails 13–69 % of seeds) | claimed essential at 0.97 (6), at 0.45 (2), excluded (1) | claims flip; p overconfident (finding 4) |
| nfc60_42 (generator) | the backup copy is keep-only-sufficient and smaller | the planted inhibitor is essential | {copy}, p(I) = 0.15 (6 of 6) | **wrong** (finding 1) |

## Verdict

**BrainIR v1 identifies causally justified members, not correlated importance.**
- Every member rests on an intervention.
- The activity filter is itself tested.
- Active, central and co-active but unnecessary neurons are excluded, and a silent but necessary neuron is kept.

**v1 does not reliably identify the mechanism the intact network uses once several sufficient sets exist or necessity depends on
context.**
- It chooses among sufficient sets by keep-only validation, size and structural centrality.
- Its group-silencing screen is non-monotone at the pool sizes of the real networks.
- It discards its own positive necessity measurements.

The result can be a core the intact network does not need, with essential neurons at probability 0.15 or 0.03 and no claim. The
tournament metrics used to select v1 score all such runs as successes.

**Before the lock.**
1. Make measured necessity binding in the selection and emit it (finding 1).
2. Stop clearing passing groups untested at large group sizes (finding 2).
3. Simulate or withdraw the edge predictions (finding 3).
4. Report the finding 9 metrics on the confirmation suite.

Findings 4–8 are reporting fixes that can follow.

## Appendix: reproduction

My scripts and outputs are in a private scratch folder outside the repository (`…\scratchpad\revA\`); nothing was written into the
clean directory except this file. Before the coordinator's housekeeping note, I listed the scratchpad root once (file names only);
I opened none of those files. Afterwards I accessed only files I had created.

- `build_suite.py`: the `default_specs()` structure with seed + 41,000,000 and short names, `verify_instance` (≤ 3 retries),
  `export_instance(salt="revA")`, `audit_suite`.
- `cases.py`: C1–C7 as `Motif`s registered in `synthetic.MOTIFS`. The parameters:

  | case | parameters |
  |---|---|
  | C1 | the E–I pair; H: stim 60 synapses, H → E 5, H → readout 10 |
  | C2 | K → M 40, M → J 40, J ⊣ K 60, stim → K 30; persistence criterion with `during_start_s` 0.35 |
  | C3 | E → I1, I2 100; I1, I2 ⊣ E 100 |
  | C4 | c1 → c2 50; a1 → a2 80; D ⊣ a1 97; stim → c1 50, a1 110, D 60; c2 → readout 30, a2 → readout 18; activity band [60, 400] Hz |
  | C5 | winner-take-all with IA ⊣ B 17 and IB ⊣ A 20 |
  | C6 | E → F 100, F → readout 15 |
  | C7 | stim → E 3, stim → B 50, B → E 10 |

  `build_cases.py` and `build_cases2.py` export 3 verified instances per case (seeds 700–859, 2 node orders) and audit them.
- `harness.py`: runs `brainir_v1` under `truth_guard` with `count_real_simulations`. It wraps `_Run.execute` and
  `_Run.size_error_curve` only to record K0, M1, context members and the curve's sets. It then runs the independent checks listed
  above. Edge removal: `W.tolil(); W[post, pre] = 0`, then `simulator._simulate_query` with the problem's stimulus, criterion and
  seed.
- `trace_necessity.py`: wraps `_Run.necessity`, `necessity_screen` and `Prober.decide` to log pooled tests and screen groups.
  `real_edges.py` does the same edge check on `benchmarks/dng100/public_blind`, from v1's own result JSON.
- Commands, run from the clean directory with `uv run --no-sync python <script>`:
  - `harness.py --suite suite --out … --max-n 100`
  - `--filter 500_ --pool k0 --n-ess-seeds 4`
  - `--suite cases_suite --seeds 0 1 2 --networks main order1`
  - `--suite cases_suite2 --pool truth`
  - `trace_necessity.py <instance> main 0`
  - `real_edges.py male-cns_v1.0 data/synthetic/dev_v1/real/final5_malecns_s0/result_male-cns_v1.0.json 2948 2152`, and the same for
    MANC with `3310`.
