# Review E — cross-connectome transfer and joint discovery

Independent, oracle-free review. Date 2026-09-23. I read and ran code only inside `C:\Dev\BrainIR_p2clean`. I consulted no
literature, benchmark answer, evaluator or oracle. My only access to `benchmarks/dng100/public` (tier B) was a join count on its
`size_voxels` column. I read no cell types there. The only synthetic truth I used belongs to pairs I generated myself (seeds
31000–32009, private salt). I wrote no code into the clean directory. My scratch scripts are summarised in the appendix.

**Question.** Is cross-connectome transfer built only from public evidence (labelled anchors, annotations, synaptic structure) and
from simulation on each network's own simulator, with every call counted? Could it smuggle in identity or hide cost? Is joint
discovery's claimed advantage real?

**Code drift during the review.** At 16:49–17:09 the discovery package was re-synced. The sync added the `BudgetedSimulator.spawn`
and `close` methods and the integrity counters, updated `pair_tournament.py`, `tournament.py`, `transfer.py` and `simulator.py`, and
added `src/brainir/methods/brainir_v1.py` and `BRAINIR_V1_METHOD.md`. The files I review below (`joint.py`, `correspondence.py`,
`synthetic_pairs.py`) have the same length and the same code at every line I cite, except that `joint.py:153` now calls `close()`.
Line numbers refer to the current files. The large pair runs (R4) used the pre-sync library. I re-ran 16 of those jobs on the post-sync library: 14 were identical, and
2 differed only by +4 adaptation calls with the same cores. The `brainir_v1` runs (R5) used the post-sync library. `brainir_v1.py`
was still being edited, so I cite it by function name.

## Summary

| severity | count | findings |
|---|---|---|
| blocker | 1 | 1 |
| major | 6 | 2–7 |
| minor | 5 | 8–12 |

**Provenance and accounting are legitimate.**
- The correspondence uses only synapse counts to and from labelled anchor types shared by name, plus five coarse annotations.
- The blind bundle offers no cross-dataset identity channel: no token reuse, no positional alignment, and no shared sizes between
  MaleCNS and MANC.
- Every simulation is charged. In 48 of 48 runs the number of real simulations equalled the ledger total.

**The claims are not yet trustworthy.**
- The "correspondence" claims (`joint.claims`, and v1's `cross_connectome`) carry a confidence that comes from structural alignment,
  not from identity evidence. v1 emitted 6 identity claims between non-homologous neurons on implementation-shift pairs, which its
  documentation says it does not do. It emitted 44 claims when the cross-network evidence had been destroyed.
- Joint discovery's agreement metrics (role-graph similarity 1.00, claim precision 1.00) are what its objective maximises.
- "Verified" transfer accepts a wrong sufficient set, or a set it never validated.
- The advantage is real only as an **efficiency** gain on a synthetic design where the correspondence is nearly free. For the weak base
  method, a third of the success gain survives when the correspondence is destroyed. For strong base methods there is no success gain.
- There is no real-data evidence for joint discovery or for v1's cross-connectome step.

## What I examined and ran

- **Read.**
  - Documents: `CLAUDE.md`, `CROSS_CONNECTOME_CONTRACT.md`, `methods/joint.md`, `SELECTION_PROTOCOL.md`, `BRAINIR_V1_METHOD.md` §9–11,
    and the pair tournament table in `selection_results/SELECTION_RESULTS.md`.
  - Code: `correspondence.py`, `transfer.py`, `joint.py`, `synthetic_pairs.py`, `synthetic.py` (motifs, export), `pair_tournament.py`,
    `tournament.py`, `problem.py`, `simulator.py`, `run.py`, `reliability.py`, `brainir_v1.py` (the `_cross_connectome` step), and the
    joint author's `data/synthetic/dev_joint/{harness,analyze}.py` with its result files.
  - Tests: `tests/test_discovery_cross.py`, `tests/test_joint.py`, `tests/test_method_brainir_v1.py` (cross-connectome test).
  - Data: the tier-A bundle (README, manifest, `male-cns_v1.0`, `manc_v1.2.1`, `manc_v1.2.3`).
- **Ran.** All runs were local with at most 3 worker processes.

| id | experiment | scale |
|---|---|---|
| R1 | identity channels in the tier-A bundle (tokens, positions, ids, sizes, annotations) | 3 networks |
| R2 | real correspondence strength: random interneurons of `male-cns_v1.0` matched into `manc_v1.2.1`, compared with nulls, a round trip, a same-animal control and a leave-one-type-out test on public labels | 300 interneurons; 705 labelled neurons |
| R3 | correspondence statistics on my own pairs, plus two harder variants | 25 + 19 + 19 pairs |
| R4 | `discover_pair` on my pairs: greedy_reference {independent, transfer, joint, joint_null}; greedy_plus {independent, transfer, prior, prior_null, joint, joint_null}; budget 400 + 400, seed 0; greedy_plus {independent, prior, joint} on both variants | 250 + 114 runs |
| R5 | `brainir_v1` (budget 400, aux 150, seed 0) on network a of every pair, with the real correspondence and with the null | 50 runs |
| R6 | audits: verified transfer under a small allowance; real-simulation vs ledger counts; decoy sign consistency; regeneration of `pairs_v1` and `mechanisms_v1`; tier A ↔ tier B join; role-graph similarity of random sets | — |

The **null control** (`*_null`) keeps network b's network, stimulus, readout and signs, so every simulation is identical. It
permutes b's `SRC#k` and `SNK#k` anchor labels among themselves (`DNsyn` and `MNsyn` are kept) and shuffles b's hemilineage,
neuromere and side across rows. Only the cross-network anchor and annotation evidence is destroyed. The code is in the appendix.

## Findings

### 1. [blocker] Cross-connectome "correspondence" claims are structural alignments, not identity evidence, and the v1 documentation says otherwise

**Evidence**

- **How the confidence is computed.** `joint.claims` (joint.py:627–658) pairs the members that the beam search assigns to each
  other in both directions, restricted to the two cores. The confidence is
  `conf = 1 − (1 − ½(w1 + w2)) / 2^edges` (L652).
  - One reproduced signed edge gives conf ≥ 0.5. Two give ≥ 0.75, three give ≥ 0.875. This holds whatever the fingerprint
    probabilities w1 and w2 are, even when they are about 0.
  - Disagreeing inferred roles multiply the confidence by 0.6 (L654–655). A pair is claimed at conf ≥ 0.1 (L656).
  - The same function produces `PairResult.correspondence` in every mode, including `independent` (L831). It also produces v1's
    schema claims (`brainir_v1._cross_connectome`: `pairs = run.claims(result, res_b)`).
- **brainir_v1, real correspondence (R5).**
  - 53 claims in total. 47 pair the same motif node.
  - **6 pair non-homologous, role-equivalent neurons.** These occur in 3 of the 6 implementation-shift pairs, at
    conf 0.31, 0.33, 0.50, 0.58, 0.75 and 0.88.
  - Example: `redundant_oscillator … shift_decoy s31022`. A's core is alternative 0 (one E–I pair). v1's fallback discovery on B
    finds alternative 1 (the other E–I pair). The two pairs are claimed as identities at 0.75 and 0.88.
  - BRAINIR_V1_METHOD.md §9, item 7, states: *"an implementation shift yields role-level alignment but no identity claims"*.
- **Null correspondence (R4, R5).**
  - v1 still emits 44 claims. 38 pair the same node and 6 do not. The same-node claims keep a mean confidence of 0.74, against
    0.84 with the real correspondence.
  - `discover_pair` in joint mode emits 50 claims (greedy_plus, 7 wrong) and 46 claims (greedy_reference, 19 wrong).
  - The identities are recovered from structure alone, because the motif is wired identically in a and b (finding 5). So the claim
    precision reported for joint and v1 on synthetic pairs (1.00) does not test the anchor-fingerprint correspondence.
- **The scorer cannot see the case.**
  - `score_pair` (pair_tournament.py:29) and the author's harness (`if (cl and tc)`) score correspondence only when the truth list
    is non-empty.
  - Under a shift, `build_pair` leaves the list empty (synthetic_pairs.py:134). That includes the nodes of the retained alternative,
    which are the same motif node in both networks (same anchor profile, wiring and role).
  - As a result, neither right nor wrong identity claims are scored in the case the contract names as the trap ("align roles, not
    identities").

**Fix (before the v1 lock)**

1. Make identity confidence a calibrated probability from fingerprint evidence against a null. It can be fitted on the
   leave-one-type-out test of finding 9 or on the anchor-permuted null. Reproduced edges may raise it only when the fingerprint
   evidence beats the "none" option in both directions.
2. Emit no identity claim when either direction falls below "none". Report role-level alignment only in that case.
3. Keep `role_alignment` and `identity_claims` as separate outputs.
4. In the synthetic truth, list identities for the retained alternative under a shift. Count cross-implementation claims as false
   positives. Report claim precision and calibration on shift pairs and on null pairs.
5. Correct BRAINIR_V1_METHOD.md §9.7.

### 2. [major] Joint discovery manufactures agreement, so its agreement metrics cannot be evidence of a shared mechanism

**Evidence**

- **The objective rewards agreement.**
  - `prefer_shared` (joint.py:753–765) ranks candidates by (validated, J, −size).
  - J is the role-graph similarity plus the mean claim confidence against the *other* network's current mechanism (L670–677).
  - A verified image is isomorphic to its source by construction, so it maximises J. It therefore replaces any own mechanism that
    is not already an image.
- **Observed switches (R4).**
  - Joint adopted the carried-over mechanism 9 times.
  - 5 times it replaced a wrong own mechanism. That is the intended repair.
  - Once (s31023 b) it replaced a correct superset [12, 73, 88] with its minimal version [12, 73].
  - **3 times it replaced a correct, different implementation.** These are the `two_implementations` shift pairs s31017
    (greedy_plus), s31018 and s31019 (greedy_reference), all on network a. a's own E–I pair was replaced by the image of b's
    4-neuron inhibitory ring.
  - In s31017, greedy_plus had found a's exact minimal 2-neuron alternative [60, 63]. Joint swapped it for the 4-neuron ring
    [51, 55, 66, 80] purely to agree with b.
  - Joint then reports the same mechanism in both networks, although a's own search found a different one.
- **The cited evidence is what the objective maximises.**
  - The pair table in SELECTION_RESULTS and BRAINIR_V1_METHOD.md §10 cite "role-graph similarity 1.00 (independent 0.88–0.96)" and
    "correspondence precision 1.00" as the benefit.
  - `role_graph_similarity_pred_ab` (pair_tournament.py:48) compares the method's two outputs with each other, not with truth.
- **Role-graph similarity is weak evidence on real data (R6).**
  - Two unrelated connected random sets of 20–30 interneurons, one per connectome, score 0.50–0.53 on average (90th percentile
    0.73–0.78).
  - Random 5-sets score exactly 1.0 in 24 % of draws, because their edge sets are empty and their role sets equal.
  - On synthetic pairs the true cores score 0.88 and random sets 0.19. There the metric discriminates, but only because the motif
    wiring is identical.

**Fix**

- Base any conservation statement on independent runs plus a null distribution of role-graph similarity for size-matched connected
  sets.
- In joint mode, report both the own and the adopted mechanism, and flag every switch.
- Summarise `role_graph_similarity_pred_vs_truth_b`, which is already computed, instead of `pred_ab`.
- Remove self-agreement metrics from the selection evidence.

### 3. [major] "Verified" transfer accepts wrong and unvalidated mechanisms

**(a) A wrong but sufficient set.** Pair `negative_feedback_controller … decoy s31001`, greedy_reference (R4):
- Lead network a's core is wrong: [16, 32, 68].
- Its structural image in b is [52]. That set passes keep-only under the activity-band criterion and is accepted after 12 calls.
- b's own discovery is then skipped. `independent` had solved b ([10, 61, 77] contains the truth [10, 61]); joint loses it. This is
  the only joint regression in R4.
- joint.md §10, item 4, calls this case "not observed … requires the same artefact to be sufficient in two independent backgrounds".
  With a permissive criterion, one relay is sufficient in any background, and real backgrounds are homologous anyway.

**(b) A set that was never validated.**
- `verified_transfer` accepts when `frac is None or frac >= 0.5` (joint.py:566). `result_from_transfer` reports
  `predicted_function_preserved = True if frac is None` (L596).
- So if the allowance runs out before the fresh-seed validation, the transfer is accepted on a single majority keep-only decision.
  This usually happens before the minimisation finishes as well.
- Measured (R6): with allowances of 2–8 calls (s31000) and 2–20 calls (s31014), the result is `accepted = True`,
  `validation = None` and `predicted_function_preserved = True`. The minimisation was also incomplete at allowances ≤ 4 (s31000)
  and ≤ 12 (s31014). Here the accepted set happened to contain the true mechanism, because the synthetic correspondence is good.
- brainir_v1 runs this step on a fixed 150-call auxiliary budget. By joint.md §8's own cost model, verification takes
  |S| + 2 log₂|probe| decisions plus one silencing decision per member, at 2–3 calls per decision. For the union image of a
  10–30-member core, that is several hundred calls on a 4,309/4,604-neuron network. So "accepted, never validated, not minimised" is
  the expected outcome there, and the members of that image become claims.

**Fix**

- Accept only when the validation pass fraction is at least 0.5 on at least 2 fresh seeds. Treat `None` as "unverified": no claims,
  and no `predicted_function_preserved`.
- Mark incomplete minimisations as supersets.
- When the follower's own discovery is affordable, run it anyway. Adopt a carried-over set only if it is consistent with the
  follower's own essential members.
- Scale v1's auxiliary budget with network size, or skip the step.

### 4. [major] The claimed advantage of joint discovery is an efficiency gain on easy correspondence; much of the success gain is not correspondence; the comparison is confounded

**Evidence.** R4, 25 own pairs, budget 400 + 400, seed 0:

| base method / mode | both-network success | total calls (a / b / adaptation) | follower solved by transfer |
|---|---|---|---|
| greedy_plus independent | 1.00 | 170 (90 / 79 / 0) | — |
| greedy_plus prior / prior_null | 1.00 / 1.00 | 153 (90 / 62 / 0) / 171 (90 / 81 / 0) | — |
| greedy_plus joint / joint_null | 1.00 / 0.96 | 108 (80 / 14 / 15) / 178 (97 / 70 / 12) | 22 / 3 of 25 |
| greedy_reference independent | 0.56 | 471 | — |
| greedy_reference joint / joint_null | 0.72 / 0.60 | 308 / 437 | 16 / 6 of 25 |

- **Strong base method (greedy_plus).**
  - There is no success gain: 1.00 vs 1.00 here, and 1.00 vs 0.98–1.00 in `sel_pairs_b1000`.
  - Joint's efficiency gain (−36 % total calls) and prior's saving on B (79 → 62 calls) disappear under the null (178 and 81). The
    gain is therefore genuinely from the correspondence, but on the design of finding 5.
  - The gain held on both harder variants: 88 vs 154 calls on the homolog and the multiplet variants.
- **Weak base method (greedy_reference).**
  - Success rose from 0.56 to 0.72: 4 wins, 0 losses on both networks (sign test p = 0.125).
  - The null keeps a third of that gain (0.60). On network a the null matches or beats joint: 0.76 vs 0.72, and 4 wins / 0 losses
    against independent.
  - So part of the gain comes from joint's extra search and not from cross-network identity. That extra search is full-network
    group elimination, essential completion, and alternating transfers located through the stimulus and readout anchors plus the
    wiring. There was also one regression (finding 3a).
- **Pooling.** The follower's discovery allowance exceeded its own budget in 9 of 25 greedy_reference joint runs and 3 of 25
  greedy_plus joint runs (19 and 22 of 25 under the null). Independent runs cannot pool.
- **The author's evidence is in-sample.**
  - E1 was iterated on the same 23 pairs it reports: "the first joint version … 0.52; carrying … back … raised it to 0.70" (joint.md
    §9). `analyze.py --joint` swaps the final joint run into the table.
  - All runs use a single seed. E2's 20/23 → 23/23 has sign-test p = 0.25.
- **v1 does not run the evaluated procedure.** BRAINIR_V1_METHOD.md §10 justifies v1's step with `discover_pair` joint-mode
  results. v1 instead keeps a fixed core, runs one verified transfer on 150 calls, runs v1 as a fallback when at least 60 calls are
  left, and has no alternating rounds and no switching. None of the cited numbers measures that procedure, and none comes from a
  network of real size.

**Fix.** Run a pre-registered paired comparison on held-out pairs with at least 3 seeds, including these arms:
- independent;
- independent-pooled (B gets `budget_b` plus A's unused calls);
- independent plus the same verification and minimisation machinery;
- joint;
- joint_null.

Report success and calls separately, with paired confidence intervals. Evaluate v1's actual step (fixed core, aux 150), including
pairs of at least 2,000 neurons. Claim only an efficiency gain unless joint beats the null.

### 5. [major] The synthetic pair design hands over the correspondence; the real bundle does not

**Evidence**

- **Only motif members share anchor profiles.** Distractors get independent random profiles (synthetic_pairs.py:168–183, L174 vs
  L180). The best-match distinctiveness therefore separates members from distractors: AUC 0.83 over my 25 pairs, 1.00 on 2 of them
  (R3). Correspondence strength itself is a membership signal.
- **Hemilineage.** It is drawn for every node in the synthetic pairs, with 10 values that agree with probability 1 − meta_noise
  (L102). In the real tier-A bundle it is blank for 2,415 of 2,416 tokenised interneurons in `male-cns_v1.0` and 2,474 of 2,475 in
  `manc_v1.2.1`. The most heavily weighted annotation (0.6, correspondence.py:30) does not exist for real interneurons.
- **Identical motif wiring.** Both networks embed `MOTIFS[family]()` at canonical nodes 1..m. The structural alignment is therefore
  exact, and the null gets 86 % of claims right with no anchor information (finding 1). Real homologous circuits differ in counts, in
  edges missing below the floor of 5, and in signs derived from neurotransmitter predictions.
- **Independent backgrounds.** The invariance argument of joint.md §2 is true by construction: no background set has a counterpart
  that works. Real backgrounds are homologous (joint.md §10.4 concedes this). Finding 3a shows that permissive criteria break the
  argument even with independent backgrounds.
- **Scale.** The pairs have 60–80 nodes (up to 600); the real networks have 4,309 and 4,604. The null best-match z is 2.0–2.4 on
  the synthetic pairs and 4.23 on the real bundle.
- **Decoys are weak.** They copy anchors and annotations but not wiring. In 5 of 13 decoy pairs the decoy is also given away by its
  sign (finding 11). Joint never put the decoy into b's core (0 of 13 with greedy_plus). Transfer mode did in 3 of 13 (greedy_reference)
  and 2 of 13 (greedy_plus). The fingerprint ranks the decoy above the true counterpart in 4 of 13 pairs.
- **Harder anchors barely matter.** On the homolog variant (every distractor has a counterpart: AUC 0.75, top-1 0.76) and the
  multiplet variant (3 look-alikes per member in each network: AUC 0.79, top-1 0.72), joint and prior kept all their gains. To its
  credit, joint does not over-rely on fingerprints. What it relies on is the identical wiring plus a counterpart within the top k.

**Harder settings to add**

1. Perturb motif wiring per network: drop or add edges, jitter counts ×/÷ 2, flip one NT-derived sign. Verify function after.
2. Structural decoys: a copy of the motif wiring among distractors, carrying the members' anchor profiles, not driven and not read
   out. Also add one that is sufficient but not planted, to test conformity.
3. Homologous backgrounds, including homologous hubs that are sufficient in both networks.
4. anchor_share 0.3–0.5, count noise sd ≥ 0.6, and members sharing anchors with 5–20 distractors.
5. Blank hemilineage for interneurons, as in the real tier A.
6. n ≥ 2,000, with mechanisms of 5–15 members.
7. Null pairs, where b implements a different family or no planted mechanism, to measure the false-claim rate.
8. Decoys whose sign is consistent with their wiring.

### 6. [major] v1's cross-connectome simulations are counted but not budgeted

**Evidence**

- `brainir_v1._cross_connectome` spawns an auxiliary simulator with its own `aux_budget = 150` calls (`sim.spawn(B, max_calls=…)`).
- `run.py:58` and `tournament.py:164` enforce `sim.calls <= budget` on the primary simulator only. Child calls appear only in
  `report()["children"]` and `total_calls_incl_children`.
- The test asserts this design: "the primary budget never pays for the other network" (test_method_brainir_v1.py:257).
- `reliability.py:187` records `result.budget["calls"]`, which counts primary calls only.
- On the real bundle, v1 at budget B therefore spends up to B + 150 simulations per network, or 2B + 300 for both. The joint contract
  requires a total of at most `budget_a + budget_b`.
- In R5, every run had total > primary. On 80-node networks the auxiliary cost was median 13 (max 76) calls with the real
  correspondence and median 65 (max 95) under the null. The integrity check was clean: real simulations equalled charged calls
  including children.

**Fix**

- Either reserve the auxiliary calls inside the declared budget, or declare the budget as B + aux everywhere.
- Compare methods on `total_calls()`, and fail runs whose `total_calls()` exceeds the declared total.
- Show auxiliary calls in every summary table.

### 7. [major] The synthetic evaluation does not keep truth away from the running method

**(a) Truth sits next to the method at run time.**
- A remote pair job writes the truth to `tmp/scorer/truth.json`, next to `tmp/inst/<name>`, *before* `discover_pair` runs
  (pair_tournament.py:76–78).
- Every worker receives all truth files in the shared payload (run_pair_tournament.py:74).
- Locally, the truth sits at `<suite>/truth/<name>.json`, reachable from `problem.root`. The single-network tournament has the same
  pattern (tournament.py:226–228, 248).
- No sandbox is used. The audit hook in `cleanroom/_sandbox.py` protects only `run_method.py`.
- `joint.py`, `correspondence.py` and `transfer.py` read no files (grep), so there is no leak in this code. But the harness cannot
  demonstrate that for any method.

**(b) Development truth can be regenerated from the labels.**
- Every public table of `pairs_v1` is reproduced from its readable label with public code: `default_pair_specs()` → `build_pair` →
  `_assemble(rng = default_rng(seed + 4242))`. Edges, counts, signed weights and signs were identical on 4 of 4 instances checked.
- The salt changes only the interneuron tokens (39–48 % token agreement = the labelled rows).
- The permutation, and hence every truth position, depends only on the seed (synthetic_pairs.py:216, 253).
- `mechanisms_v1` behaves the same way (1 of 1 checked; the label carries the salted seed; synthetic.py:453–456).

**Fix**

- Run discovery in a sandboxed subprocess whose roots hold only the instance, and give the truth to the scorer only after the result
  has been serialised.
- Derive every random draw from a secret key: backgrounds, profiles, annotations and permutations.
- Never put the effective seed or the family into a label.

### 8. [minor] `size_voxels` is a row identity key: the two MANC networks are the same animal, and tier A joins tier B

**Evidence**

- MaleCNS and MANC share no size value, so this is not a cross-animal channel.
- `manc_v1.2.1` and `manc_v1.2.3` share 4,582 unique sizes. The size map reproduces 196,021 of 196,021 edges exactly, and the tokens
  map 1 : 1. They are the same animal and the same graph.
  - The anchor correspondence recovers identity between them at 99.0 % top-1 (R2). Any "cross-connectome" claim between the two is
    trivial.
  - v1's `other_network` correctly requires a different dataset. `discover_pair`, the joint CLI and `transfer_experiment_job` accept
    any pair.
- Every tier-A row joins its tier-B row by size: 4,309 of 4,309 in `male-cns_v1.0`, 4,582 of 4,604 in `manc_v1.2.1`, with identical
  neuron and edge counts.
  - Tier B holds real types, which are largely shared across the datasets, and it sits in the same clean room.
  - Only the runner's sandbox stops a tier-A run from reading it. The joint and transfer entry points are not sandboxed and do not
    record the bundle tier.

**Fix**

- Refuse same-dataset pairs, or label them "same animal".
- Record the bundle tier and sha in `PairResult`.
- Run real-bundle transfer experiments through the sandbox.
- Keep tier B out of the Phase-2 clean room unless a tier-B method is being developed.

### 9. [minor] On real data the correspondence is informative but not identity, and its scores are not calibrated

**Evidence (R2)**

- The 300 random tokenised interneurons of `male-cns_v1.0` are ranked among 4,459 candidates of `manc_v1.2.1`, using 367 shared
  anchor types.
  - Best-match z has mean 4.26 [p5 2.98, p95 5.38]. With b's anchor labels permuted it drops to 2.61 [2.00, 3.31].
  - The a→b→a round trip returns to the same neuron in 51.7 % of cases, against 16.7 % under the null.
  - The ambiguity is large: in 32 % of cases the margin between best and second is < 0.05, and 32 % have ≥ 10 candidates within
    1 z of the best.
  - Joint's "none" logit (4.23) equals the median real best-match z.
- **Leave-one-type-out test on public labels.** 705 labelled neurons of 348 shared types; each neuron's own type is removed from the
  anchors, and it is ranked among all 4,459 candidates.
  - The same label is found at top-1 in 73 % of cases (76 % without hemilineage), top-3 in 80 % (83 %), top-10 in 87 %.
  - By class: ascending neurons 94–97 %, descending 67–73 %, sensory 15 %.
  - By best-match z: 29–36 % below z 3.5, 78–84 % between 3.5 and 5, 93 % at z ≥ 5.
  - Most interneuron matches fall between z 3.5 and 5, so a per-member top-1 accuracy of about 0.6–0.8 is plausible. This is an
    extrapolation from labelled neurons.
- **Consequence.** A top-1 image of an m-member mechanism is all-correct with probability of about 0.75^m (0.24 for m = 5, 0.06 for
  m = 10). The top-k union, minimisation and simulation are indispensable, and they cost more than 150 calls at this size
  (finding 3b).
- **Same-animal control** (`manc_v1.2.1` → `manc_v1.2.3`): 99.0 % top-1, 99.3 % top-5. The machinery works when the wiring is
  identical.
- **Calibration.**
  - With fingerprint-only scores, the best-match z is *higher* under the null (11.3) than on real data (9.1). z reflects the shape of
    the score distribution, not evidence.
  - `null_match_scores` samples all candidates, including labelled DN, AN and SN neurons, although its docstring says "interneurons"
    (correspondence.py:153).
  - `prior_rho = 0.8` and `prior_base = 0.02` are not calibrated for interneurons.

**Fix.** Calibrate match probabilities on the leave-one-type-out test and the anchor-permuted null. Restrict the null pool to
tokenised interneurons. Report per-member uncertainty in transported priors and in claims.

### 10. [minor] Roles and role graphs are sign and wiring descriptors, and the role scorers are lenient

**Evidence**

- **How roles are inferred.** `infer_roles` (joint.py:267–317) uses the sign, the member's own wiring (self-loop, SCC, excitatory
  cycle), its projection onto the readout or readout groups, and the criterion type.
  - The base methods' role rules are alike (greedy_plus, cem_search). The one simulation-derived role is `redundant_backup`, given to
    members of alternatives that the method found by simulation.
  - No role comes from interventions on the member itself, so role labels add little beyond signs and topology.
- **The rules mirror the generator's vocabulary.** test_joint.py:137 asserts `infer_roles == truth roles`, so synthetic role accuracy
  of about 1 holds by construction.
- **The role-alignment scorer is lenient.**
  - It skips any truth role that the method never names (pair_tournament.py:37).
  - It counts a hit on any overlap in a and in b.
- Role-graph similarity on real data: see finding 2.

**Fix.** Count unnamed truth roles as misses. Score role graphs against truth with a size-matched null.

### 11. [minor] The anchor decoy is given away by an inconsistent sign

**Evidence.** `build_pair` copies the member's sign into `inst_b.signs[d]` (synthetic_pairs.py:163) but leaves the decoy's own
outgoing weights unchanged. In 5 of my 13 decoy pairs, the decoy is the only neuron of network b whose published `sign` contradicts
its outgoing `signed_weight`. A sign/edge consistency check would single it out. The decoy also copies no wiring (finding 5).

**Fix.** Choose a decoy whose sign already matches, or rewrite its outgoing weights. Add wired decoys.

### 12. [minor] Reporting and accounting details

**Evidence**

- **Budget accounting is sound.**
  - The ledger closes each previous phase (joint.py:151–157). Every allowance is at most the calls left. Each network has one memo,
    and every memo entry is charged exactly once.
  - R6 checked 48 of 48 `discover_pair` runs (3 pairs × 4 modes × 2 methods × budgets 400 + 400 and 40 + 25). In every run the real
    simulations equalled the ledger total, which was within the limit, and the phase sums were consistent.
- **Some tables mislead.**
  - Per-network "calls b" excludes `adaptation_b`, which is spent on b. In joint mode that is about half of b's cost: calls b 14
    vs adaptation 15 (R4, greedy_plus).
  - Pooled allowances appear in no summary table.
- **Invariants and post-hoc checks.**
  - The invariants are Python `assert`s (joint.py:161, 172), which are disabled under `-O`.
  - `transfer_experiment_job` runs its post-hoc `sufficiency_check` and `null_transfer` on unbudgeted simulators
    (transfer.py:113, 170). That is fine as evaluation, and they are reported as `check_calls`. They must never feed decisions.
- **Every mode's claims come from the same function.** The claims in `independent` mode are produced by joint's `claims()`, so the
  "corr P/R" rows of the pair tables compare one claim function on different cores, not two correspondence methods.
- **A test instance was selected for its outcome.** test_joint.py's RESCUE instance was chosen because the base method fails on it.
  That is fine for a unit test, but it is not evidence.

**Fix.** Report `network_calls = b + adaptation_b`. Report the follower's allowance and whether budgets were pooled. Raise explicit
exceptions instead of `assert`s.

## Answers to the seven questions

1. **What the correspondence uses, and whether the blind bundle carries identity.**
   - It uses observed synapse counts (`C`) to and from labelled anchor types shared by exact name (correspondence.py:39–78), and
     five annotations: hemilineage, soma_neuromere, side, sign and sub_class. Joint adds the signed wiring among members and rules
     derived from it. It does not use tokens, positions, source ids, sizes, instance, super_class or degrees.
   - Tokens are not reused across networks. The only shared string is the literal `nan` of untyped rows (38 in male-cns, 2 in manc).
     Tokens are strictly per neuron (2,378 distinct tokens for 2,378 `T#` rows in male-cns; 2,473 for 2,473 in `manc_v1.2.1`), so
     there is not even a within-network type grouping.
   - Positions come from independent permutations. For 19 singleton anchor types, Spearman ρ = 0.16 and 0 positions are identical;
     for the MANC pair, ρ = 0.06 over 97 types.
   - `source_id` equals the position. Instance and hemilineage are blank for interneurons. No size is shared between MaleCNS and MANC.
   - **No cross-dataset identity channel exists beyond public labelled types.** The exceptions are within-dataset: the two MANC
     versions and tier B (finding 8).
2. **How distinctive anchor fingerprints are.** They are informative, not noise, but they are not identity. Numbers are in
   finding 9: best-match z 4.26 vs 2.61 under the null; round trip 52 % vs 17 %; top-1 same type on labelled neurons 73–76 %, but
   15 % for sensory neurons; a third of interneurons have ≥ 10 near-ties. That is enough to seed a search that simulation then
   verifies. It is not enough to transfer a multi-member mechanism as an image or to support identity claims without calibration.
3. **Decoys and implementation shifts.**
   - Joint never preferred a decoy: in b's core 0 of 13 (greedy_plus), claimed 0 of 13; the 1 of 13 with greedy_reference also
     occurs in `independent`.
   - Transfer mode picked the decoy in 2–3 of 13. v1 never claimed a decoy.
   - But the decoys are weak (findings 5 and 11), and joint and v1 **do** claim identity where only roles correspond: 6 v1 claims on
     3 of 6 shift pairs, conf up to 0.88 (finding 1). Joint also replaces a network's own valid implementation with the other
     network's (finding 2).
4. **Budget.**
   - Joint cannot exceed `budget_a + budget_b`, and no simulation goes unreported (finding 12). Adaptation is reported separately,
     overall, per network and per phase.
   - The prior's gain is measured at equal budgets: B gets `budget_b` in both arms. It is real on synthetic pairs (79 → 62 calls;
     null 81).
   - Joint pools budgets (finding 4). v1's auxiliary calls are counted but lie outside the enforced budget (finding 6).
5. **Is joint vs independent fair?** The base method, seeds and total budget are the same. It is confounded by pooling, by
   joint's extra search machinery, by in-sample development and by a single seed (finding 4).
6. **Does the synthetic design make transfer easier than real data?** Yes: only members carry shared profiles; hemilineage is
   present; wiring is identical; backgrounds are independent; networks are small; decoys are weak. See finding 5 for the harder
   settings to add.
7. **Are role labels inferred from interventions or signs?** From signs and public wiring plus the criterion type, never from
   interventions on the member (finding 10). Role-graph agreement is weak evidence on real data (finding 2).

## Verdict

**Cross-connectome transfer in this code base is legitimate in provenance and accounting, but its claims are not yet valid
evidence.**
- Nothing crosses between the networks except labelled anchor types, coarse annotations and public wiring.
- The blind bundle offers no cross-dataset identity channel.
- Every simulation is charged, and joint discovery respects `budget_a + budget_b`.

**What must change before cross-connectome claims made with this code are reported**
- Identity claims must be calibrated and suppressed at the role level (blocker 1), and the v1 documentation corrected.
- Agreement metrics must not serve as evidence of conservation (2).
- Unvalidated or wrong transfers must be rejected (3).
- v1's auxiliary calls must be inside the declared budget, or reported alongside it (6).
- The synthetic evaluation must be hardened: sandbox and secret-keyed suites (7), and harder pairs (5).

**Is the advantage real?** Joint discovery's efficiency gain is real on easy synthetic correspondence. It has not been shown on real
data, and its success gain comes from repairing a weak base method, a third of which happens without any correspondence.

## Appendix: reproduction

My scripts are in my scratch directory, not in the repository. Their key parts:

```python
# null control (R4, R5): identical simulations, no cross-network anchor/annotation evidence
def null_problem(p, seed=99):
    rng = np.random.default_rng(seed); nd = p.neurons.copy(); ct = nd["cell_type"].astype(object).to_numpy().copy()
    for pref in ("SRC#", "SNK#"):                                   # permute anchor labels among themselves
        idx = [i for i, t in enumerate(ct) if isinstance(t, str) and t.startswith(pref)]
        vals = [ct[i] for i in idx]
        for i, j in zip(idx, rng.permutation(len(idx))): ct[i] = vals[j]
    nd["cell_type"] = ct
    for c in ("hemilineage", "soma_neuromere", "side"): nd[c] = nd[c].to_numpy()[rng.permutation(len(nd))]
    return dataclasses.replace(p, neurons=nd)                         # W, stimulus, readout, signs unchanged
```

- **Pairs.** `PairSpec` seeds 31000–31025, with bump +1000 if unverified. Families: nfc, ffd, integrator, memory_switch, wta (60×80
  plain and decoy); nfc and ffd 80×60 complications + decoy; ei_pair and delayed (plain, decoy); ring; two_implementations and
  redundant (shift ×2, shift + decoy); three with `anchor_share` 0.4 and `meta_noise` 0.6. Verified with `verify_pair(seeds 0–3)` and
  exported with a private salt. The ffd 80×60 pair is present; the nfc 80×60 pair did not verify.
- **Variants.** Homolog: every b distractor gets `_perturb` of a distinct a distractor's profile plus `_noisy_copy` of its
  annotations. Multiplet: 3 distractors per member in each network get perturbed copies of the member's profile and annotations.
  Anchors are inert, so dynamics are unchanged; re-verified.
- **R2.** `match_candidates(male-cns, manc_v1.2.1, 300 random tokenised interneurons, fa, fb)` against `fb` with permuted anchor
  columns. The leave-one-type-out test recomputes `fingerprints` without type t for each shared labelled type (≤ 3 neurons per type)
  and ranks all of b's candidates.
- **R6.** Allowance test: `joint._PairRun(...).verified_transfer("a", "b", DiscoveryResult(core=truth_a, essential=True), BudgetedSimulator(b, cap))`
  for cap ∈ {2, …, 150}. Regeneration: `build_pair(spec)` from `default_pair_specs()` (+100,000 retries), then
  `_assemble(..., rng=default_rng(seed + 4242))` for a then b, compared with the shipped `edges.parquet`. Integrity:
  `count_real_simulations()` around `discover_pair`.
