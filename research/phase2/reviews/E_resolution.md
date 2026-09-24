# Review E (cross-connectome): resolution

Review: `research/phase2/reviews/E_cross_connectome.md`. It found 1 blocker, 6 majors and 5 minors.

The review confirmed two things:
- the transfer uses only public evidence;
- every simulation is charged.

Its findings are about claims that the evidence does not support, and about a synthetic design that made correspondence
too easy.

**Who fixes what.** Harness and generator fixes were made by the orchestrator. Method fixes were assigned to the
oracle-free composer of BrainIR v1: its cross-connectome step, `joint.py` and `correspondence.py`.

**Status legend.** "harness" = fixed in shared infrastructure, with tests. "method" = assigned to the composer; the
outcome is recorded when the composer returns. "evaluation" = measured under the protocol amendment
(`SELECTION_PROTOCOL.md` §7).

| # | severity | finding | resolution | status |
|---|---|---|---|---|
| 1 | blocker | Identity-claim confidence came from structural alignment; v1 claimed non-homologous neurons under implementation shifts, and kept claiming with the cross-network evidence destroyed. | **Method:** confidence becomes a calibrated identity probability estimated against a null. No claim is made when either direction falls below "none". Role alignment is a separate output. §9.7 of the method doc is corrected. **Harness:** identity truth now covers every pair: under a shift, only the retained alternative's members; on null pairs, nothing. Identity claims are scored on every pair, including shift and null pairs (precision, false claims by pair type, Brier score, reliability diagram): see `identity_truth`, `score_identity_claims` and `tournament.score_cross_claims`. | harness done; method in progress; evaluation pending |
| 2 | major | Joint discovery manufactures agreement: its objective rewards agreement, and its agreement metrics are what it maximises. | **Harness:** summaries compare role graphs with the truth. Self-agreement a↔b is labelled as not evidence and removed from the tables. **Method:** joint mode reports its own and its adopted mechanism and flags every switch. **Evaluation:** conservation claims rest on independent runs and nulls (§7.4). | harness done; method in progress |
| 3 | major | "Verified" transfer accepted a wrong sufficient set, and accepted sets that were never validated. | **Method:** a transfer is accepted only after validation on at least 2 fresh seeds. An unvalidated transfer gives no claims and no function claim. An incomplete minimisation is reported as a superset. A carried-over set must agree with the destination's own essential members. | method in progress |
| 4 | major | The advantage is an efficiency gain on easy correspondence; part of the success gain is not correspondence; the comparison is confounded. | **Harness:** new arms `independent_pooled` (b also gets a's unused calls) and `<mode>_null` (`perturb.null_correspondence`: cross-network cues destroyed, simulations unchanged). A pre-registered paired comparison runs on held-out pairs with 3 seeds (§7.4). The v1 step itself is evaluated as run, on pairs up to 2,000 × 2,500 neurons (§7.3). | harness done; evaluation pending |
| 5 | major | The synthetic pair design hands over the correspondence. | **Generator:** `hard_pair_specs()` (`synthetic-pairs-v2`) adds: jittered motif counts in b; dropped and added motif edges; structural decoys (a wired, silent copy of b's mechanism carrying the members' anchor profiles); homologous backgrounds; blank interneuron hemilineage; weaker, noisier anchors; sign-consistent anchor decoys; null pairs; pairs of 2,000 × 2,500 neurons. The v1 design is reproduced bit for bit (fingerprint check). Built as `pairs_v2_heldout` and `pairs_v2_final` with secret salts and seed offsets. | harness done; suites building |
| 6 | major | v1's cross-connectome calls were counted but not budgeted. | **Harness:** a spawned simulator draws from its parent's budget (one pool per run). `remaining` includes children. `run_one` and `run_method` fail any run whose `total_calls()` exceeds the declared budget. Tables and sweeps report total calls. Test: `test_spawned_simulators_draw_from_the_parent_budget`. **Method:** v1 fits its step inside the pool. | harness done; method in progress |
| 7 | major | Synthetic truth was not kept from the running method. | **Harness, runtime:** `discovery/guard.py` refuses to open or list any `truth*` or `*__private` path, and any build or audit report, while `discover` runs; the run then fails. Remote jobs keep the truth in memory until the result exists. **Harness, static:** `test_method_modules_cannot_reach_truth` checks method modules, `joint.py` and `correspondence.py`. It forbids truth-bearing imports (which could regenerate development truth), reading files, dynamic imports and frame or heap introspection. **Suites:** new suites derive a 40-bit seed offset from the secret salt (`--secret-offset`). | harness done |
| 8 | minor | `size_voxels` identifies rows: the two MANC networks are the same animal, and tier A joins tier B. | `DiscoveryProblem.bundle_networks()` / `other_dataset_networks()` / `load_network()` and `same_animal()`. Methods reach other networks only through them, and same-dataset pairs are flagged. The tier-B copy was removed from the clean room, since no clean-room code used it and no tier-B method is developed there. No Phase 2 job ships tier B to a worker, and the blind run goes through the frozen sandbox. | harness done |
| 9 | minor | On real data the correspondence is informative but not identity, and its scores are not calibrated. | **Method:** calibrated match probabilities, and a null pool of tokenised interneurons only (item 1). | method in progress |
| 10 | minor | Roles are sign and wiring descriptors, and the role scorers are lenient. | **Harness:** role alignment counts unnamed truth roles as misses and requires Jaccard ≥ 0.5 in both networks; a mean Jaccard is also reported. Role graphs are scored against the truth. | harness done |
| 11 | minor | The anchor decoy was given away by an inconsistent sign. | `decoy_sign_consistent` picks a decoy whose own sign matches; the v2 design uses it. A test checks sign/wiring consistency of every column. | harness done |
| 12 | minor | Reporting and accounting details. | Pair tables report a network's calls including its adaptation calls, and the pooled-allowance rate. The new code raises explicit exceptions instead of `assert`. | harness done |

Tests: `tests/test_budget_integrity.py` (pooled budget, truth guard, static rules, bundle API) and `tests/test_pairs_v2.py`
(harder settings, identity truth in old and new formats, claim scoring, null transform, pooled arm).
