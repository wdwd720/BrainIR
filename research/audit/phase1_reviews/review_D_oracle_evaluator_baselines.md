# Review D — oracle, prediction schema, frozen evaluator, baselines, null distributions

Independent review, 2026-09-23, working tree at commit `5776d24` (untracked at the time: `PHASE1_REPORT.md`,
`benchmarks/dng100/baselines/`, `tests/test_baselines_contract.py`; the baseline campaign was still running, so
`baselines/results/` was partial: 8 of 9 methods evaluated, no `baselines_summary`, no `null_distributions`).
Read-only review; nothing under `src/` or `benchmarks/` was modified. This report uses the oracle's labels (E1, E2,
I1, I2, E3, E4, E5) and bundle positions only; it contains no published cell-type name and no body ID.

Scope: `benchmarks/dng100/oracle/{oracle.json,oracle.py}`, `src/brainir/benchmark/prediction.py`,
`benchmarks/dng100/evaluator/evaluate.py`, `benchmarks/dng100/baselines/*` and `tests/test_baselines_contract.py`,
`benchmarks/dng100_walking_cpg/cross_connectome_eval.py`, the limitation language in `PROTOCOL.md`, the oracle's
`scoring_notes` and the evaluator docstrings; `src/brainir/mapping.py` only for the recommendation in §2 (D-M3).

## 1. Verdict

The architecture is right and mostly implemented as specified: the oracle is a separate, hashed file read only by the
evaluator; the prediction schema is strict (frozen models, `extra="forbid"`, unique ids, stimulus excluded, pinned
version); the evaluator reports six metric families with no aggregate number, its functional family is genuinely
oracle-free, its seeds and settings are recorded, and the clean room + evaluator run end to end (verified on the example
method). The nine baselines see only the bundle, take roles from the network's own sign column, claim essentiality only
where they simulated it, and are deterministic under the seed. The limitation language is, with two exceptions noted
below, careful and correct.

It is **not ready to freeze**. Two defects must be fixed before `BENCHMARK_LOCK.json` / the tag exist, because both live
in files whose hash the lock pins: (1) in tier A — the only tier that can support an independence claim — the type/role
family is dead: it reads the blind bundle's token column, so `type_level_excitatory_recall` is 0 for every prediction
(confirmed in all 8 baseline evaluations and in my run); the second of the three scoring layers required by goal2 §13
does not exist in the blind setting, and the null distribution of that metric is meaningless. (2) The oracle's MaleCNS
"BrainIR reference statistics" and the LOG §8.8 "recruitment discrepancy" come from a reproduction that stimulated a
different DNg100 body than the benchmark's stimulus (the first DNg100 in the authors' table, not the one selected by the
bundle rule and the paper); at the benchmark stimulus the evaluator's own intact-network runs recruit a median of 8
active front-leg motor neurons, i.e. the paper's value — the discrepancy is very probably an artefact, and the oracle
currently records the wrong reference and says the evaluator relies on it (it does not). Beyond these, the main
weaknesses are: the functional pass criteria rest solely on the amplitude-blind published score (the D30 gates exist
in `brainir.metrics.rhythm` but are not used), the cross-connectome family evaluates no transfer of a prediction between
datasets (both directions are evaluated only for the *published* circuit, oracle-driven), the null distributions are
structural only (no functional null, no degree-matched sampler, no confidence intervals on the estimates), several
oracle facts carry no evidence level despite the report's claim that every fact does, and the eight baseline
evaluations already on disk span two oracle hashes.

## 2. Findings, ranked

### Blockers (must be fixed before the freeze)

**D-B1 — Tier-A type/role family is always zero.** `benchmarks/dng100/evaluator/evaluate.py:63-71` restores real ids
for a positional (tier A) bundle but not cell types; `type_of()` (`:110-112`) reads `neurons["cell_type"]`, which in
tier A is the salted token; `type_role()` (`:176-182`) intersects those tokens with the oracle's type names, so `found`
is always empty. The note at `:203-204` ("computed from the evaluator's own type table") describes a table that does not
exist. Evidence: every file under `baselines/results/eval/*.json` (tier A) has `type_level_excitatory_recall = 0.0`,
`published_types_found = []`, `n_predicted_with_type = 3` (tokens counted as types); my run of the example method on the
blind bundle gives the same. Impact: layer 2 of goal2 §13 (cell-type/role agreement, the layer that credits a
functionally equivalent contralateral copy) is non-functional in the only tier that can support the PROTOCOL §5 claim;
`null_distributions.py` computes and reports p-values for a metric that is identically zero in tier A. Fix: have the
exporter write `cell_type` (and `instance`, `side`) into `oracle/tier_a_ids/ids_<network>.csv` next to `position,source_id`
(`src/brainir/benchmark/bundle.py:134`, `:181-189`), and have `BundleNetwork.__init__` restore `cell_type` from that map
when `positional`; rename the note. Add a regression test on a synthetic tier-A bundle (or on the real blind bundle
under `real_data`) asserting that a claim on a published-type neuron yields `type_level_excitatory_recall > 0`. There is
no evaluator test today (`tests/test_benchmark_package.py` covers schema, tokens and bundle integrity only).

**D-B2 — The oracle's MaleCNS BrainIR statistics and the §8.8 discrepancy rest on the wrong stimulus neuron.**
`benchmarks/dng100_walking_cpg/reproduce_dynamics.py:85-89` stimulates `dn[0]`, the first DNg100 in the authors' table.
For MANC that happens to be the paper's neuron (bundle position 31). For MaleCNS it is the *other* copy (bundle position
6, soma side L); the bundle's rule (`bundle.py:82-91`, most output into LegNp(T1)(L)) and the answer key's
`DNg100_left_VNC` both select position 9 (soma side R). `results/stim_dng100_male-cns_v1.0_nt-paper_n128.json`
(`stimulated.positions = [6]`) is the file the oracle cites at `oracle.json:436`; its statistics (median 4 active MNs,
13.16 Hz) are copied into `stimulation_statistics_brainir` (`:422-437`) and motivate `discrepancy_note` (`:438`) and
LOG §8.8. At the benchmark stimulus, BrainIR's own runs give the paper's recruitment: baseline evaluations (n = 8,
T = 1 s) `intact_network.active_readout_median = 8.0`, my example-method evaluation (n = 2) 8.0,
`cross_connectome_eval_n8.md` intact row 8.0, frequency 10.9-11.6 Hz; paper 8 (6-16). Impact: an incorrect fact in a
file that is about to be frozen; an "unresolved question" that is most likely resolved; and a misleading sentence —
"Functional evaluation on this network uses BrainIR's own simulated statistics as reference" — since `evaluate.py` never
reads `stimulation_statistics_*` (the functional family recomputes the intact network). Fix: re-run
`reproduce_dynamics.py stim --dataset male-cns ... --stim-index 9` (n = 128 at T = 2 s), replace the oracle block and
note, rewrite LOG §8.8 and PHASE1_REPORT §7.2 accordingly, and make `run_stim` default to the bundle's rule
(`choose_stimulus`) instead of `dn[0]`. Scores are unaffected (the evaluator does not use these numbers), but the oracle
hash will change, so this must precede the lock.

### Major

**D-M1 — The functional pass criteria use only the amplitude-blind published score.** `evaluate.py:46` (`RHYTHMIC = 0.5`),
`:124-125` (mask = peak > 0.01 Hz), `:221` (necessity), `:235` (sufficiency) and the whole robustness family use
`network_oscillation_score` alone. LOG D30 records why that is insufficient ("a 2e-4 Hz ripple scores 1.0"; a damped
transient scores 0.83) and `brainir.metrics.rhythm.rhythm_report` / `RhythmResult.is_sustained_rhythm` implement the
amplitude, persistence and inter-peak gates — but the evaluator does not call them. Measured on the blind MANC network
(intact, seeds 1000-1002, T = 1 s): of the 3-4 "active" readout neurons per replicate, one has a peak-to-peak range of
0.35-0.87 Hz and scores 0.995-1.0, another has a range of 0.12 Hz and scores 0.76-0.78; both enter the mean that decides
`fraction_rhythmic`. Impact: a keep-only core that leaves a sub-Hz ripple on a single motor neuron passes sufficiency;
necessity verdicts inherit the same blindness. None of the eight evaluated baselines exploits this (all sufficiency 0),
but a search-based method could. Fix (before the freeze, since it changes pass semantics): report next to the published
score, per condition, `fraction_sustained` (replicates in which `is_sustained_rhythm()` holds for the readout trace with
the largest range, or for a majority of active MNs) and the median readout range in Hz; keep the published score as the
paper-comparable primary number; define `sufficiency_pass` as both. Also state in PROTOCOL §4 that "rhythm" in the
functional family is the paper's amplitude-normalised score.

**D-M2 — Evidence levels: incomplete coverage, informal vocabulary, no validation.** `oracle.py:22` defines
`EVIDENCE_LEVELS` but nothing checks that `evidence` values belong to it; values are free text ("paper_simulation +
brainir_simulation (68.1% ...)"). Facts without any entry in a network's `evidence` dict: `labels.*.type/nt/role`
(`oracle.json:15-51`; the NT is an ML prediction, not any of the four levels), `stimulus_source_ids` (a data rule),
`core_contralateral_copies` (`:323-331`), `other_circuits`, `modal_prevalence`, `silencing_paper`,
`stimulation_statistics_paper`; `cross_connectome.pairs[*].evidence` uses "curated type annotation" (`:456`), which is not
in the vocabulary. The roles are correctly *not* called wet-lab facts, but "expert_interpretation" undersells what they
are: a stated rule applied to an ML NT prediction (the same rule the paper used) — a `rule_on_prediction` /
`curated_annotation` level is missing, and the same gap makes the mapping pairs unclassifiable. PHASE1_REPORT.md:224-225
("every fact carries an evidence level") therefore overclaims. Fix: make each fact `{"value": ..., "evidence":
["paper_simulation", ...], "note": "..."}` or keep the parallel dict but add a test (`tests/`) that every key of every
network block has an evidence entry whose levels are all in the vocabulary; extend the vocabulary with
`curated_annotation` and `ml_prediction` (+ `rule_on_prediction` if wanted); the `frequency_hz` band (see D-m7) needs its
own entry. Positive: paper vs BrainIR statistics are cleanly separated (`*_paper` / `*_brainir` blocks; the
`modal_circuit` evidence names both with their numbers).

**D-M3 — Cross-connectome family evaluates no transfer; "both directions" exist only for the published circuit.**
`evaluate.py:266-286` reports (a) which labels the per-network predictions hit and (b) whether *claimed* pairs share a
label. There is no notion of direction and no test of whether a mechanism found in dataset A works in dataset B
(goal2 §16). `cross_connectome_eval.py:97-135` does run both directions (MANC->MaleCNS and MaleCNS->MANC: map the modal
circuit through the public mapping table, simulate keep-only in the destination) — but for the *oracle's* modal circuit,
on the authors' networks (`paper_network`), i.e. an answer-key-adjacent analysis, not an evaluation capability for
predictions. Further defects: `claimed_correspondence_accuracy` (`:281`, `:286`) counts a pair between two unlabelled
neurons as wrong (the oracle has no information about it: it is unscorable, not false); in tier A the tokens are not
comparable across networks (bundle README), so a method can only claim correspondences from connectivity — the family is
close to unscorable in the tier that matters; and `manc_v1.2.3` is the same graph as `manc_v1.2.1` (identical
`edges.parquet` hash in both tiers, identical id order, identical signs; 7 retyped bodies, of which 2 front-leg MNs became
`vnc_intrinsic`, so the readout is 142 vs 144 and those two bodies are interneuron *candidates* in v1.2.3), so
`labels_recovered_in_all_networks` / `excitatory_core_in_all` (`:283-284`) are inflated by a near-duplicate; in tier A
the positional ids of the two MANC networks even coincide. Fix: (1) compute `*_in_all` per *dataset* and report
v1.2.3 as an annotation replicate of v1.2.1; (2) add an oracle-free `transfer` sub-family: for each ordered pair
(src, dst) of evaluated datasets, map the src prediction's core into dst with the public mapping table
(`brainir.mapping.forward_lookup` / `reverse_lookup`; high-confidence candidates, else all candidates; report
`mapping_kind`, `confidence`, `ambiguity` per neuron and the unmapped count) and simulate it keep-only in dst with the
same seeds — exactly `functional_transfer()` applied to predictions; (3) split claimed pairs into consistent /
inconsistent / unscorable. **Recommendation on the mapping table:** use it *inside the evaluator*, evaluator-side only,
with the table's SHA-256 (`load_summary()["table"]["sha256"]`) recorded in `BENCHMARK_LOCK.json` and in every evaluation
record; do not ship it in either bundle (its `curated_body_match` rows restate the MaleCNS release's `manc_body_id`
annotation — in tier A they would align positions across networks and hand a method the cross-network answer for free).
State in the transfer output that the correspondence is the release's curated annotation (D39), so a transfer result
means "the mechanism transfers under the curated correspondence", not that the method or BrainIR derived it.

**D-M4 — Null distributions: structural only, no degree-matched sampler, no confidence intervals.**
`null_distributions.py:41-46`: k in {3,4,5}, samplers `uniform` / `two_hop` / `sign_matched_two_hop`, 500 draws, scored
with `structural` + `type_role` only. goal2 §15 asks for the probability that a random matched set "preserves rhythm"
and "transfers across both connectomes"; PROTOCOL §5 requires a result to "lie outside the null distributions" — but the
only functional evidence is the baselines themselves (all sufficiency 0 so far) and the negative controls in
`robustness_experiments.py`, none of which is a null over random k-sets. goal2 §14 asks for sets "matched for degree
distribution": absent (the `two_hop` sampler ignores degree; `statistical_motif` uses degree-matched shuffles internally,
which is a method, not a null). `summarise_null()` (`:106-115`) reports mean, sd and 2.5-97.5 percentiles of each metric
across draws — the spread of the null, not a confidence interval on the estimated probabilities (`p_excitatory_recall_full`
etc.); for the discrete metrics (recall in {0, 0.5, 1}, slot in {0, 1}) the percentile interval is usually [0, 0] and
uninformative. `baseline_pvalues()` (`:144-167`): one-sided empirical p with the +1 correction is fine; `k_used` snaps
to the nearest of {3,4,5} (`:154`), silently mismatching a k = 6+ method. `MATCHED_NULL` (`:44-46`) pairs `degree_topk`
(direct targets, 1 hop) with `two_hop`, and `random_matched` with the sampler it *is* a draw from (p ~ uniform; fine as
a sanity check but say so). Fix: add `degree_matched_two_hop` (match each baseline's picks by weighted-degree decile
within the 2-hop set); add a small functional null (e.g. 200 sign-matched 2-hop triplets x 2 replicates, keep-only,
T = 1 s -> P(sufficient) with a Wilson interval; about 2-3 s per keep-only simulation, feasible locally or on Modal);
report Wilson intervals for every hit probability and the full PMF for the discrete metrics; report the null's own
`type_level_*` only after D-B1.

**D-M5 — Baseline evaluations already span two oracle hashes.** `oracle.json` changed in commit `5de3e7c` (01:54) while
`run_all_baselines.py` was running: evaluations of `random_matched`, `degree_topk`, `pagerank`,
`betweenness_stim_to_readout`, `kcore_scc` carry oracle `543aac55...`; `community`, `recurrence_loop`,
`statistical_motif` carry `6e3c90f7...` (the current file). The change only added the two `stimulation_statistics_brainir*`
blocks and the discrepancy note (core ids unchanged), so no score is affected — but PROTOCOL §6 says results are
comparable only within one lock, and `summarise()` (`run_all_baselines.py:102-123`) copies hashes per method without
checking they agree. Fix: after D-B1/D-B2 and the lock, re-run `run_all_baselines.py --skip-run` so every evaluation
carries the locked oracle/evaluator hashes; make `summarise()` refuse (or loudly flag) mixed `oracle_sha256` /
`evaluator_sha256` / `bundle_sha256`.

**D-M6 — Necessity accuracy is vacuously satisfiable and carries no uncertainty.** `evaluate.py:216-224, 238`: accuracy
is averaged over *claimed* neurons only; a method claiming `essential=False` for everything is right for almost any
random neuron (accuracy 1.0), one claiming nothing gets `None`, and PROTOCOL §5 ("its essentiality claims are correct")
is then met trivially. With `--n-replicates 8` (the baseline campaign) `fraction_rhythmic` is a binomial proportion with a
95 % interval of about +-0.3 around 0.5, yet `observed_essential = fraction < 0.5` is a hard verdict. Fix: report
confusion counts (claimed-essential confirmed / refuted, claimed-non-essential confirmed / refuted), i.e. sensitivity and
specificity separately; require for §5 at least one confirmed `essential=True` claim; attach a Wilson interval to every
`fraction_rhythmic` and mark verdicts whose interval contains 0.5 as `borderline`.

### Minor

**D-m1 — `t_end` 1.0 s vs the bundle's 2.0 s.** `evaluate.py:309, 402` default 1.0 s; `public*/model_config.json` says
2.0 s; the paper used 1 s for screens/pruning and 2 s for activation and silencing (`pugliese_model_spec_from_code.md`
rows 11, 344-345). Measured on the same seeds (blind MANC, intact): score 0.996 / 0.970 / 0.938 at 1.0 s vs
0.9995 / 0.980 / 0.945 at 2.0 s (a systematic -0.003 to -0.010; fewer autocorrelation cycles), frequency identical
(11.24 / 10.10-10.14 / 10.42 Hz; the 1/lag estimator is window-independent), active counts identical, fraction >= 0.5
unchanged. So the shortening is benign for pass/fail metrics, halves the cost, and matches the paper's pruning
convention — but the necessity family deviates from the paper's 2-s silencing convention, and `intact_network.score_mean`
is not directly comparable with the oracle's 2-s statistics. Fix: state the 1.0 s evaluation window in PROTOCOL §4 and
the bundle README (a method calibrating `DynamicsClaim` at 2 s is compared with 1-s simulations); have `evaluate()`
read `model_config.json` from the bundle and assert it equals `ModelConfig()` apart from `t_end` (it currently never
reads it, `:321`).

**D-m2 — Definitions of precision and the Jaccard reference.** `structural()` `:158, 167`: `precision_vs_all_published_labels`
counts E4/E5 as hits although the oracle itself labels them "DNb08 pathway" (not part of the DNg100 mechanism); either
restrict to E1-E3/I1/I2 or rename. `:160`: when no inhibitory member is hit, the Jaccard reference uses
`inhibitory_slot[0]` (I1) for every network, including the one whose published modal circuit uses I2 — use the modal
circuit's inhibitory member.

**D-m3 — Robustness uses one noise realisation.** `evaluate.py:296` `weight_noise_seed=7` for every parameter replicate:
the family measures robustness to a single perturbation of the weights, not to the noise distribution; vary the noise
seed with the replicate (`seed + 7`). The family stresses only the keep-only core; necessity verdicts are never
stress-tested. (Design is otherwise sensible: sd 0.1 / 0.3 match the paper's noise sweep; doubled parameter SDs match
`robustness_experiments.py`.)

**D-m4 — `to_markdown` is a partial view.** `evaluate.py:358-392` omits `modal_circuit_recovered`, `published_labels_found`,
`compactness`, `evidence_level_of_reference`, `type_level_inhibitory_slot_filled`, `published_types_found`,
`core_neurons_missing_from_network`, `core_receives_stimulus_directly` / `core_projects_to_readout`, the predicted vs
simulated `rhythmic` and `n_active_readout`, `solver_failures`, and any network caveat. The evidence level is the most
important omission for limitation language: a reader of the .md sees "excitatory core recall" without being told the
reference is `paper_simulation`. All six families are present, but not faithfully.

**D-m5 — Schema expressiveness and validators (`prediction.py`).** Missing relative to goal2 §11: edge claims (no way to
claim a specific connection or its sign), causal ordering beyond `rank`, multi-neuron intervention claims (e.g. "silencing
I1 and I2 together abolishes"), an explicit sufficiency claim. `DynamicsClaim.frequency_hz` (`:44`) is ambiguous — the
intact network's or the isolated core's (LOG §3.17: 10.75 vs 16.7 Hz); the evaluator compares with the intact network,
so say so. Validators to add (`:89-96`): `mechanism.loop_neurons` unique and a subset of `core_neurons`;
`cross_connectome[*].source_id` in `core_neurons`; `frequency_range_hz` ordered; `stimulus_source_ids` non-empty; unique
`rank`s; decide whether an empty `core_neurons` is a valid prediction (it is today). Versioning: `Literal["1.0.0"]` pins
the version and the history block exists; document that a schema bump implies a benchmark version bump (it changes the
evaluator's hash anyway). Free-text `motif` / `notes` are unscored (fine) but appear verbatim in evaluation output.

**D-m6 — Evaluator edge cases.** `evaluate.py:320`: two predictions for one network silently overwrite each other.
`:154-173, 176-205`: tier-B ids that are not in the network are accepted silently (they lower precision; only the
functional family lists them at `:236`) — flag them in `structural` too. `:331-335`: a cross-connectome claim towards a
network that is not part of the evaluated set keeps its untranslated (positional, in tier A) `other_source_id` and is
then compared with body IDs — mark as unscorable instead. `evaluate()` never calls `verify_bundle()` (only
`run_method.py` does): an edited bundle can be evaluated. `OracleNetwork.essential`, `frequency_hz`, `modal_prevalence`
are never read by the evaluator — the oracle should say which fields are scored and which are informational.

**D-m7 — Oracle / documentation inconsistencies.** (a) Readout count: the bundles, the stimulation result and the
evaluation output all have 130 front-leg MNs for MaleCNS, but LOG §3.18 (`:154`), PHASE1_REPORT §8 (`:217-218`,
"144 / 144 / 135") and `reproduce_dynamics.py:75` say 135; the bundle's manc_v1.2.3 has 142, not 144. (b)
`oracle.json:301` "connectivity identical for this network" for v1.2.3 is true for edges and signs but the readout
differs by two retyped bodies (see D-M3) — say so; its `frequency_hz` evidence claims `brainir_simulation` although no
v1.2.3 run exists (trivially identical W, but state that). (c) `wet_lab.DNg100_activation` (`:517`) merges the paper
(intact tethered flies on a treadmill: speed and stepping frequency) with the Sapkal et al. follow-up (decapitated
flies, ~11 Hz stepping in air) without citing the latter. (d) `frequency_hz` [8, 14] has no stated derivation; the
isolated modal circuit runs at ~16.7 Hz (LOG §3.17), outside the band, so a method predicting the core's frequency would
be "wrong" — harmless today because the evaluator does not use the band, but the `scoring_notes.frequency` text suggests
it does. (e) `other_circuits` and `circuits_top5` mix labels with raw type names; fine while the oracle is private, but
every raw name is one more leakage surface. (f) `oracle.json:2` `_warning` and `oracle.py` docstring are good;
`scoring_notes.essential` is correct and consistent with `silencing_paper` (checked against the literature notes:
MANC E1 0.000 / E2 0.005 / I1 0.938 (99.7 %), MaleCNS E1 0.028 / E2 0.003 / I2 0.952; modal counts 636/1024 = 0.621 and
655/1024 = 0.64). The per-network core ids, roles, essential flags, modal circuits and inhibitory slot are mutually
consistent and consistent with `cross_connectome.pairs` (same ids on both sides for E1, E2, I1, I2, E3).

**D-m8 — Role metrics are tautological for sign-copying methods.** Every baseline reads its roles from the network's
sign column, and the oracle's roles are the same rule on the same predictions, so `role_consistent_with_network_sign`
is 1.0 by construction and `role_agreement_with_oracle` is 1.0 whenever the id matches (seen in all evaluations).
Document that these metrics are informative only for methods that infer roles from dynamics or connectivity.

**D-m9 — Baseline defaults are answer-shaped; one path hygiene point.** `baselines/README.md:12, 20` and
`random_matched.py:68-71`: k = 3 and a 2 E + 1 I composition equal the size and composition of the published modal
circuit. Both are defensible priors ("a compact CPG needs inhibition") and the nulls cover k in {3, 4, 5}, but they should
be declared as benchmark parameters, and the graph baselines should also be reported at k = 4 and 5. Fairness otherwise
holds: bundle-only inputs through the clean room, `MethodInfo` records inputs/seed/compute, deterministic under
`BRAINIR_SEED`, no `essential` claims except from the simulation baseline (verified in the predictions on disk), and
`tests/test_baselines_contract.py` enforces the import rules, forbidden words and the absence of absolute paths.
`cleanroom/example_method.py:43` prints the absolute output path, which ends up in `run_record.json` (`stdout_tail`);
the baselines print only the file name (their run records are clean). Print `out.name`.

**D-m10 — Matched-null choices.** See D-M4: `degree_topk` vs `two_hop`, `random_matched` vs its own sampler,
`k_used` snapping. Also the `sign_matched_two_hop` composition rule `round(k/3)` is fixed rather than matched to the
baseline's observed composition; matching to each baseline's own E/I split would make "matched" literal.

### Notes

- `BENCHMARK_LOCK.json` and the `dng100-benchmark-v1` tag do not exist yet (expected while the baselines run), but
  `PROTOCOL.md:5` already speaks of the protocol as "hashed in `BENCHMARK_LOCK.json`" and PHASE1_REPORT carries
  `[PENDING]` markers for hashes, baselines, nulls and cross-connectome results.
- The functional family is oracle-free: `functional()`, `robustness()` and `mechanism()` take only the prediction, the
  bundle network, the model config and the seeds; the only oracle-directory access on that path is the tier-A id map.
  `always_keep` = stimulus + readout comes from the bundle. No leakage found.
- Determinism: fixed public seeds (1000..1000+n), deterministic RK45 in float64, ordered process-pool map; two
  evaluations of the same prediction give identical numbers (the eight baseline files share identical
  `intact_network` statistics per network, as expected for identical seeds).
- What the eight evaluated baselines show (tier A, k = 3, n = 8): `degree_topk`, `pagerank` and
  `betweenness_stim_to_readout` recover exactly one excitatory core neuron in all three networks (recall 0.5);
  the others recover none; no baseline fills the inhibitory slot or passes sufficiency. Degree centrality alone does
  not solve the benchmark, which is the question goal2 §14 asks.
- Limitation language: PROTOCOL §4 ("agreement with a model-derived result, not biological proof"), the oracle's
  evidence-level definitions, `wet_lab.interneurons` and PHASE1_REPORT §11 are precise. No "ground truth" / "proven"
  wording was found in the benchmark package. The two overclaims are PHASE1_REPORT:224-225 (every fact has an
  evidence level) and `oracle.json:438` (the evaluator "uses BrainIR's own simulated statistics as reference").

## 3. goal2 requirements in scope — checklist

| requirement (goal2) | status | evidence / caveat |
|---|---|---|
| §9 oracle separate from the public bundle, usable only by the evaluator | pass | `oracle/` read by `evaluate.py` only; clean room forbids imports; leakage audit PASS |
| §9 evidence level documented for every oracle fact | fail | D-M2: labels, stimulus, contralateral copies, paper statistics, pairs lack a level or use an undeclared one; no validation |
| §9 simulated results not presented as biological truth | pass | evidence definitions, `wet_lab.interneurons`, PROTOCOL §4, PHASE1_REPORT §11 |
| §11 versioned `BrainIRMechanismPrediction`, expressive but not vague | pass with gaps | strict validators; no edge / multi-intervention claims; ambiguous frequency field (D-m5) |
| §12 deterministic evaluator, separate families, no single magic number | pass | six families, no aggregate; thresholds are the paper's 0.5 and are recorded |
| §12 structural metrics (neuron / type precision-recall, edge, motif) | partial | neuron level yes; type level dead in tier A (D-B1); no edge precision/recall; loop check only |
| §12 functional metrics (rhythm, frequency, intervention agreement, necessity/sufficiency) | pass with caveat | oracle-free sufficiency/necessity; amplitude-blind criterion (D-M1); necessity vacuously satisfiable (D-M6) |
| §12 mechanism quality (compactness, causal faithfulness, role consistency) | partial | compactness + graph sanity; role consistency tautological for sign-copying methods (D-m8) |
| §12 cross-connectome generalisation (role recovered in both, conserved mechanism, overfitting penalty) | partial | label co-occurrence and claimed pairs only; no transfer test; duplicate network inflates "all networks" (D-M3) |
| §12 robustness (seeds, parameter variation, noise) | pass with caveat | seeds, doubled SDs, weight noise 0.1/0.3; single noise realisation (D-m3) |
| §13 three scoring layers, scored separately | fail in tier A | layer 1 pass; layer 2 always 0 in tier A (D-B1); layer 3 pass |
| §13 functional equivalence not so loose that arbitrary circuits pass | pass so far | all eight baselines fail sufficiency; formal criterion = paper score >= 0.5 in >= 50 % of replicates (D-M1 caveat) |
| §14 random baselines: uniform, size-matched, sign-matched, neighbourhood-matched, degree-matched | partial | first four via `random_matched` + nulls; degree-matched missing (D-M4) |
| §14 graph heuristics (degree, PageRank, betweenness, k-core/SCC, recurrence, edge ranking) | pass | seven structural baselines; shortest-path relevance via subset betweenness |
| §14 module/community baselines | pass | Louvain around the heaviest direct target |
| §14 functional baselines (greedy neuron deletion; edge deletion; perturbation ranking) | partial | `greedy_prune_sim` (neuron deletion with LOO ranking); no edge deletion; running at review time |
| §14 statistical / representation baselines | partial | `statistical_motif` (degree-matched enrichment); none on trajectories — defensible under "do not inflate the list" |
| §14 baselines fair: bundle only, no answer knowledge, deterministic | pass | clean-room contract, source checks in `tests/test_baselines_contract.py`, roles from the sign column; answer-shaped k / composition defaults declared? no (D-m9) |
| §15 null distributions per relevant baseline, enough samples | partial | 500 draws x 3 samplers x k in {3,4,5}, structural only; no functional or transfer null (D-M4) |
| §15 confidence intervals | fail | percentiles of the null, no interval on the estimates (D-M4) |
| §16 MaleCNS->MANC and MANC->MaleCNS evaluation supported | partial | both directions for the published circuit (`cross_connectome_eval.py`); not for predictions (D-M3) |
| §16 explicit definition of "same mechanism" across datasets | partial | oracle labels + curated pairs; no functional definition in the evaluator |
| §28 precise limitation language | pass with two exceptions | D-M2 (report claim), D-B2 (oracle note) |
| §23 lock file and tag | not yet | expected: campaign still running; PROTOCOL wording anticipates the lock |
| §29 tests for prediction schema / evaluator / baselines | partial | schema, bundle, baselines tested; no evaluator test (would have caught D-B1) |
| acceptance 18 deterministic evaluator exists | pass | |
| acceptance 19 strong baselines exist | pass (pending completion) | 8 of 9 evaluated at review time |
| acceptance 20 null distributions estimated where relevant | partial | structural only |
| acceptance 21 both cross-connectome directions supported | partial | see §16 rows |
| whether the paper's MaleCNS active-MN statistic used the bundle's readout definition | unverifiable | the paper's mCNS configuration is not in its repository (LOG §8.8); BrainIR's value at the bundle stimulus matches it anyway (D-B2) |

## 4. What I ran

- `uv run --no-sync pytest -m "not real_data" -q` — 358 passed, 18 deselected, 53 s.
- Clean room + evaluator on the example method, blind bundle, networks `manc_v1.2.1` and `male-cns_v1.0`, seed 0
  (`cleanroom/run_method.py`, 1.8-2.0 s per network; `evaluator/evaluate.py --n-replicates 2 --workers 2`, 55.8 s;
  outputs in my scratchpad, not in the repository). Confirms end-to-end operation, the run record, the cross-connectome
  block, and D-B1 (type-level recall 0 with `n_predicted_with_type = 3`).
- A 6-simulation check (scratchpad script importing `evaluate.BundleNetwork`): blind MANC intact network, seeds
  1000-1002, `t_end` 1.0 vs 2.0 s, published score + `rhythm_report` gates per active readout neuron (D-M1, D-m1).
- Static checks: SHA-256 of `oracle.json` vs the `oracle_sha256` recorded in the eight `results/eval/*.json` (D-M5);
  `git diff 8df59ad 5de3e7c -- oracle.json` (what changed mid-campaign); bundle manifests of both tiers (identical
  `edges.parquet` hashes for the two MANC networks; readout 144 / 142 / 130; stimulus positions); tier-B neuron tables
  (id order, retyped bodies, DNg100 positions and sides, readout sign composition); the reproduction result files cited
  by the oracle (`stimulated.positions`, `readout.n`, statistics); `answer_key.json` and
  `research/literature/pugliese_walking_cpg_detailed_notes.md` against the oracle's paper-derived numbers; grep of the
  package and reports for "ground truth" / "proven" wording; grep of `baselines/results/` for absolute paths (clean).
- Not run: `run_all_baselines.py`, `null_distributions.py`, anything on Modal.

## 5. Files reviewed

`benchmarks/dng100/{PROTOCOL.md,LEAKAGE_AUDIT.md,freeze.py}`, `oracle/{oracle.json,oracle.py}`,
`evaluator/evaluate.py`, `cleanroom/{run_method.py,example_method.py}`, `baselines/{README.md,run_all_baselines.py,
null_distributions.py,random_matched.py,degree_topk.py,pagerank.py,betweenness_stim_to_readout.py,kcore_scc.py,
recurrence_loop.py,community.py,statistical_motif.py,greedy_prune_sim.py}`, `baselines/results/eval/*.json|md` and
`results/runs/*/`, `nodes/README.md`, `public*/{README.md,manifest.json,model_config.json}`;
`src/brainir/benchmark/{prediction.py,bundle.py}`, `src/brainir/sim/model.py`, `src/brainir/metrics/rhythm.py`,
`src/brainir/mapping.py` (docstring and lookup API); `tests/{test_baselines_contract.py,test_benchmark_package.py}`;
`benchmarks/dng100_walking_cpg/{cross_connectome_eval.py,reproduce_dynamics.py,answer_key.json}` and its `results/`
(stimulation, pruning, cross-connectome files cited by the oracle); `research/LOG.md` (D29-D39, §3.17, §3.18, §5,
§8, §10), `research/literature/pugliese_*`, `PHASE1_REPORT.md`, `goal2.md`, `CLAUDE.md`.
