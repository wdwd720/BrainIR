# Post-lock review V2: my V findings, and the post-hoc lifting test for v1

Reviewer V, second pass, on the rebuilt room with the updated PHASE3_REPORT.md. Scope: reporting, statistics and claims only.
Nothing here proposes a change to the locked method.

**Files.** Scratch scripts are in `.tmp/postlock_V/` (`l1.py` recomputes the LIFT_V1 summary).

| short name | file |
|---|---|
| LV | `results/tournament/final_b_lift_v1/LIFT_V1.json` |
| FB | `results/tournament/final_b/<model>.json` |
| LC | `results/level_c/01/level_c_results.json` |
| MB | `results/MODAL_BILLING.json` |
| CX | `results/counterexamples/<run>/SUMMARY.json` |

## Summary verdict

**All of my V findings are fixed (V-B1, V-M1, V-M2, V-M3 and minors 1-14; minor 7 can only be checked for its citations).** The
post-hoc lifting test itself is sound: it applies goal4 section 13's lift to v1's own encoder, leaves v1 and every pre-registered
prediction unchanged, reuses the frozen lifting evaluator with the confirmation's cases and settings, and every number the report
gives traces to LV. What is still wrong is how the report uses the test.

**New findings: 0 blockers, 3 major issues and 5 minor issues.**
- The report now calls criterion 26 "met" and Phase 3 "complete". The only new evidence is a post-hoc, evaluator-side lift that is
  not a capability of the locked method. The previous version said this gap could not be closed without a new method version. The
  new test does not remove that reason; it moves the lift outside v1.
- The v1 lift results sit next to the baselines' without the caveats that make them non-comparable. A pre-registered lifting item
  that is unfavourable to v1 is omitted.
- Section 18.1 says review V "re-checked" the lifting test before any such check existed.

---

## Part 1: status of the V findings in the updated report

| finding | status | location in the updated report |
|---|---|---|
| V-B1 G10 abstention | **fixed** | summary lines 79-81; section 18 lines 1296-1302; section 21 Q18 note (line 1432, also in the `SELF_AUDIT.json` `orchestrator_note`) and line 1479. The wording matches GL (`no_compact_state` true, recall 1 of 1, G3 false alarm, confident-wrong 0.8). See minor V2-m1 for "first draft" |
| V-M1 nn_dim_rule S3 | **fixed** | section 10.1, lines 719-728: `mean_ci95` taken from the stored SUMMARY (sparsity S5 [0.0015, 0.072], nn_dim_rule S3 [-0.066, -0.0013], float-level S3 of 8 switches), and the reading is rewritten. The switch descriptions in the reading match `SUMMARY.json` (`draw_folds`, `sparsity`) |
| V-M2 net2 "sufficient" | **fixed** | the permitted claim (section 23) is split by reconstruction; summary lines 53-58; section 23 bullets; section 14 "Predictive" adds the hidden-data input-floor check (0.514 > 0.408, matching LC) |
| V-M3 lineage | **fixed** | lineage columns in the section 14 verdict, intervention, prediction and reproducibility tables and in the section 17 robustness table. Per-lineage counts are given for PCA-k, verdicts, abstentions, E, seeds, half-samples and counterexamples. I re-derived the counterexample breakdown from CX `broken_immediately_fraction` >= 0.5: public draws R1 = net3 full, net1 b, net3 a, net3 b and R2 = net2 full; hidden draws net1 full, net1 b, net3 full; comparator net1 full, net1 a, net2 full, net3 full. The section 16 table has no lineage column, but the breakdown follows it directly, which is acceptable |
| m1 "to 3 decimals" | fixed | section 14, "within 0.003 …"; sections 23 and 24 "indistinguishable" |
| m2 all-abstained mechanisms | fixed | section 14 intervention table, "not met: every held-out pair abstained" (LC `interventional` false) |
| m3 Q15 lin_falds_t | fixed | line 1494 |
| m4 seed-0 against modal k | fixed | line 1077 (net2 mechanism b added) |
| m5 FINAL LOCO | fixed | section 8, lines 579-581: 4th / 5th / 2nd / 4th / 4th / 3rd / 2nd / 3rd, as I derived |
| m6 capped marks | fixed | section 17 table ("≥ 1.82, 6 capped"); net2 "not comparable (both capped: 19 and 60 windows)" |
| m7 untraceable numbers | fixed as citations; not verifiable in this room | section 14 cites `POSTLOCK_NUMBERS.json` (fit records, public data); summary and criterion 42 cite `research/phase3/TEST_RUNS.md`. Neither file is in this room |
| m8 closure power | fixed | summary line 66; section 23 |
| m9 category names | fixed | summary lines 30-31 and 77; section 6, lines 446-448; section 18, line 1302 |
| m10 billing window | fixed | section 22. The window now ends with the hour starting 11:00Z: MB `total_usd` 136.03, 126 apps, post-lock 79.80, CPU 70.74, memory 65.28, all matching. The summary's "$136" matches |
| m11 family H ran twice | fixed | section 17 |
| m12 S7 wording | fixed | section 8 |
| m13 both normaliser floors | fixed | section 14 (1.12 / 0.99 / 1.00 and 1.13 / 0.98 / 1.01, matching LC `C_alt_scales`) |
| m14 "all corrected here" | fixed | summary lines 100-102; section 18.1. See V2-m2 for the characterisation |

---

## Part 2: the post-hoc lift of v1 (`scripts/lift_v1_encoder.py`, LV, log lines 46-47)

### 2a. Implementation and scope (checked against the source)

**Is v1 unchanged? Yes.**
- `EncoderLift` wraps the loaded seed-0 pickle and delegates `encode`, `rollout`, `readout`, `supports` and `info` unchanged. It adds
  only `lift()`. Nothing is refitted or re-selected.
- The output goes to a new file. The confirmation record is untouched: FB `brainir_state_v1.json` still has
  `lift = {supported: false, reason: "the model does not implement lift()"}` and verdict counts 17 / 2 / 12 / 15.
- No pre-registered prediction or verdict is affected.

**Does it follow goal4 section 13?**
- J = d phi / d x_t is taken by central differences through the public `encode()`. The recorded linearity check gives a maximum
  relative difference of 9.7e-12, so J is exact for this encoder.
- The lift is `lstsq(J[:, cols], delta_z)`: the minimum-norm Δx with J Δx = Δz. That is the λ → 0, Cost = ||Δx||² limit of goal4's
  objective, within an allowed class (instantaneous kicks on the observed public targets).
- The do(z) comparison is goal4's: the model rollout from z_twin + Δz against the simulator after the lift.

It is not "exactly" goal4's definition, as the criterion-26 cell (line 1114) says ("phi(x + delta_x) = z + delta_z"), for three
reasons:
1. The equality is the design target, not the outcome. The frozen evaluator measures the shift one simulated sample after the kick,
   and the median miss is 25 % (up to 328 %; LV per-system `achieved_shift_rel_error`).
2. The cost is the raw-unit norm.
3. When a candidate has fewer targets than k, the solve is least squares, not exact.

**Is it the frozen evaluator with the same cases and settings?** Yes.
- It calls `evaluate_lift.eval_lifting` with the defaults the confirmation job used (shift_sd 0.5, n_lifts 3, seed 0).
- `future_s = cfg.micro_future_s`, `scale = sd.scale(sid)`, and `roll = E.Fresh(model)` created before any encode, as in the job.
- The cases are the first 6 non-intervention test trajectories × `start_times_s[1:3]`, identical to
  `suite_eval.evaluate_model_job` (lines 349-355).
- The 46 compressible systems come from the stored seed-0 FINAL fits.

**Differences from the confirmation's lifting run that the report does not state:**
- It is a re-implementation of the job's lift block, run locally (3 workers), not the frozen Modal job.
- The baselines' lifts (`lin_core.lift`) invert each model's event kick-gain matrix K in standardised units. v1's lift inverts the
  encoder Jacobian in raw units. Only the candidate-subset rule is shared. See V2-M2 for why this matters.

### 2b. Traceability (recomputed from LV per-system rows)

| report item | report | LV |
|---|---|---|
| systems lifted, errors | 46, 0 | 46 of 46; 0 errors; 1,104 of 1,104 requests lifted; 3,310 distinct and 2 near-identical lifts |
| achieved-shift relative error (median) | 0.25 | 0.2475 (IQR 0.115-0.543; max 3.28) |
| readout NMSE after do(z) / twin (medians) | 0.17 / 0.079 | 0.1689 / 0.0787; after-lift > twin on 42 of 46 |
| "about 2.1 times" | 2.1 | ratio of medians 2.15 (median of per-system ratios 1.69) |
| baselines "1.7-3.7 times" | 1.7-3.7 | ratios of the FB medians: lin_falds 1.70, lin_falds_t 1.72, lin_dmdc(_t) 2.51, nn_aelin(_t) 3.02, lin_pcadyn(_t) 3.72 |
| invariance ratio (median; share < 1) | 0.16 (100 % of 45) | 0.165; 45 of 45 testable < 1 (max 0.97) |
| encoder linearity | 1e-11 | 9.7e-12 |
| criterion 27 range "0.03-0.30 … and 0.16 for v1" | yes | yes |

Every lifting number in the summary (lines 41-43), section 15 (criteria 26 and 27), section 19, section 23 ("not claimed") and
section 24 traces to LV or FB.

### 2c. Wording and the criterion-26 status: see V2-M1 and V2-M2.

### 2d. Other new errors: see V2-M3 and minors V2-m1 to V2-m5.

---

## BLOCKERS

None.

## MAJOR issues

### V2-M1. "Criterion 26 met" and "Phase 3 status: complete" rest on a reclassification, not on new evidence that meets the criterion as the report itself read it

**Where:**
- summary lines 13-16 ("**Phase 3 status: complete.** … all 50 acceptance criteria are met … criterion 26 … is met");
- reporting index line 117;
- section 15, criterion 26 (line 1114, "met, with disclosure") and the "Phase 3 status: complete" paragraph (lines 1139-1143).

**Evidence:**
- The previous version rated criterion 26 "partly" for two reasons. First, "the LOCKED method has no `lift()`". Second, "adding
  `lift()` now would be a post-hidden change to v1 … it needs a new, separately locked method version; the gap cannot be closed
  inside Phase 3 without a post-hidden change to v1".
- The new test changes neither fact. v1 still has no lift() (FB `lift.supported = false`). The lift is an evaluator-side procedure
  that the answer-aware orchestrator designed after the FINAL and Level C results and after the post-lock reviews. It is not
  pre-registered and it covers the synthetic FINAL suite only. No model has any real-system lifting test (section 19).
- The test shows that goal4 section 13's lift can be computed for v1's latent space without changing v1. That is real and useful
  evidence that lifting is implementable. But it is not a lifting capability of the locked method.
- If "lifting exists" is read at the benchmark level, criterion 26 was already met in the previous version (8 baselines lift), and
  the post-hoc test adds nothing to the status.
- If it is read at the method level, as the report did before, it is still not met.
- Either way, the status change from "not declared complete" to "complete" is driven by a change of reading plus a post-hoc
  construction, not by the criterion becoming satisfied.

goal4 section 85 says not to declare the phase complete until every criterion is satisfied, so the unqualified bold headline
overstates.

**Correction** (the wording the evidence supports):
- **Criterion 26 status:** "met at benchmark level; for the locked method only post hoc". Evidence cell: "Lifting exists and is
  scored in the benchmark (8 baseline models lift on the FINAL suite). The locked method has no lift(). After the post-lock reviews,
  the evaluator lifted v1's latent interventions post hoc through v1's own encoder, following goal4 section 13 (minimum-norm kicks
  on the public targets solving J Δx = Δz; v1 unchanged; synthetic FINAL suite only; not pre-registered; descriptive). This shows
  that lifting is implementable for v1's latent space. It is not a capability of the locked method, and no real-system lifting test
  exists for any model."
- **Summary and section 15 status:** "**Phase 3 status: every pre-registered stage ran once and is reported; 49 of 50 criteria are
  met in full, and criterion 26 is met at benchmark level but for the locked method only through a post-hoc, evaluator-side lift on
  the synthetic FINAL suite (section 19).**"
  - If the project declares completion on that basis, it must say so in the same sentence: "Phase 3 is declared complete under the
    benchmark-level reading of criterion 26; under the method-level reading used in the previous version it is not."
  - Otherwise keep "not declared complete".
- **Reporting index line 117:** the same qualification.
- Section 19 also calls the design "fixed and logged before any result". Add: "by the answer-aware orchestrator, after the FINAL and
  Level C results were known; the rule mirrors the baselines' lift".

### V2-M2. v1's lift results are set beside the baselines' without the caveats that make them non-comparable, and a pre-registered lifting item is omitted

**Where:**
- section 19 table (line 1365) and the "Unfavourable" bullet (lines 1372-1374: "31-102 % in the baselines' lifts and by 25 % … in
  v1's encoder lift");
- summary lines 41-43 ("Different neural implementations of one shift give similar futures");
- criterion 27 (line 1115).

**Evidence:**
- **The achieved-shift error favours v1's lift by construction.** It is measured through the model's encoder (`eval_lifting`:
  `z_l = encode(sim)`, `z_t = encode(twin)`). v1's lift inverts that same encoder. The baselines' lifts (`lin_core.lift`) invert their
  event kick-gain K in standardised units, not their encoders. So 0.25 against 0.31-1.02 does not compare lifting quality. The
  report's phrase "with the baselines' three-candidate rule" (line 1352) hides the difference: only the subset rule is shared.
- **The TRUE-latent spread is omitted.** PROTOCOL.md section 4 K lists "lifting: spread of the TRUE latent shift across distinct
  lifts of one requested shift" as a reported item. It is not reported for any model, and for v1 it is the worst of all:
  - LV `true_latent_shift_spread_rel` median **0.54** (46 systems);
  - baselines (FB): lin_dmdc_t 0.43, lin_falds 0.47, lin_falds_t 0.34, nn_aelin 0.30.

  Distinct lifts of one requested latent shift move the true latent differently by about half the shift's size. The
  "implementation-invariant" reading rests on readout futures only.
- After do(z) the readout error is higher than on the twin on 42 of 46 systems.

**Correction:**
- Add a column "true-latent shift spread (median)" to the section 19 table: 0.43 / 0.47 / 0.34 / (lin_pcadyn: not finite) / 0.30 /
  v1 0.54.
- Add below the table: "v1's row is not comparable with the baselines' on the achieved-shift error. Its lift inverts the same
  encoder that the metric uses, whereas the baselines' lifts invert their event operators, in standardised units."
- Summary lines 41-43: "… realised with a median 25 % miss, measured through the encoder the lift inverts. After do(z) the readout
  NMSE is 0.17 against 0.079 (higher on 42 of 46 systems). Different implementations of one shift give similar readout futures
  (ratio 0.16), but they move the true latent differently (spread 0.54 of the shift, the largest of all lifting models)."
- Section 19 "Favourable" bullet: restrict it to "similar readout futures".
- Criterion 26 cell: replace "exactly as goal4 section 13 defines lifting (… phi(x + delta_x) = z + delta_z)" with "following goal4
  section 13 (minimum-norm solution of J Δx = Δz; the realised shift misses by 25 % median)".

### V2-M3. Section 18.1 reports a verification that had not taken place

**Where:** section 18.1, row V (line 1338): "(on the corrections; re-checked the post-hoc lifting test added after its review, see
below)".

**Evidence:**
- The lifting test ran at 12:09-12:13Z, after my review (log lines 46-47).
- `reviews/POSTLOCK_V.md` contains no lifting check, and nothing "below" in section 18.1 reports one.
- The row asserts independent review of exactly the evidence that changed the Phase 3 status.

**Correction:** "V | 1 / 3 on the corrections (reviews/POSTLOCK_V.md). The post-hoc lifting test was added after that review.
Second pass V2 (reviews/POSTLOCK_V2.md): all V findings fixed; the lifting test is correctly implemented and its numbers trace, but
the criterion-26 status, the comparison with the baselines and this row overstated (V2-M1 to V2-M3)." Then state how each was
resolved.

## Minor issues

- **V2-m1.** Section 18, line 1301: "(The first draft said the method 'does not abstain' on G10 …)". The false sentence was introduced
  by the first round of corrections, not the first draft, as the summary itself says (line 101). Write "The first corrected version
  said …".
- **V2-m2.** Summary line 101 calls V's three majors "three incomplete corrections". They were a wrongly rejected reviewer number
  (V-M1), an overstated claim (V-M2) and missing lineage (V-M3). Write "a wrongly rejected reviewer number, an overstated claim and
  missing lineage".
- **V2-m3.** The lifting run is missing from the process sections:
  - section 12 (deviations and post-hoc runs);
  - the list of resolution routes in section 18.1, which names the family-H extraction but not the lift;
  - section 22, "Local machine": a local run, 3 workers, about 2 min, simulating FINAL-suite protocols on the development machine.

  Add it to all three.
- **V2-m4.** Smoke run. The DONE row (log line 47) says "one smoke run on syn-00d5084cf9 first". Give its time. "Design fixed and
  logged before any result" (section 19) holds only if the smoke run came after the START row (12:09:06Z). LV `generated_utc`
  12:13:02 with `wall_s` 124.6 puts the full run at about 12:11-12:13.
- **V2-m5.** Section 19 says the lift was scored "by the frozen lifting evaluator … with the confirmation's cases". Add: "through a
  re-implementation of the confirmation job's lift block, run locally rather than in the frozen Modal job".

---

## What I re-derived and found correct

- **Lifting:** every LV number in section 2b; the evaluator settings and cases (source comparison, section 2a); v1 unchanged (FB
  lift record and verdict counts); the baselines' lifting table (FB, as in POSTLOCK_V).
- **Compute:** MB totals, stages, apps and resources; the section 22 window statement.
- **Counterexamples:** the per-lineage breakdown (CX) and the summary's "4 of R1's 6 systems and R2's full network" / "all of R1".
- **Level C:** section 14 tables and text re-checked against LC, including the lineage columns, the within-0.003 C_scrambled values
  and the hidden-data input-floor check.
- **Ablations:** the section 10.1 mean CIs against `ablations_final/SUMMARY.json`.
- **Self-audit:** the Q18 `orchestrator_note` in `SELF_AUDIT.json`.

## Verdict

Every finding of my first review is fixed. The G10 statement, the `nn_dim_rule` interval, the net2 claim, the lineage columns and all
14 minors now match `results/`, so the post-lock reviews' blockers and majors are resolved. The post-hoc lift of v1 is technically
sound. It applies goal4 section 13's lift to v1's own linear encoder, changes nothing in v1 or in any pre-registered result, reuses the
frozen evaluator with the confirmation's cases, and every reported number traces to LIFT_V1.json. The report overstates what the test
shows. It turns criterion 26 into "met" and Phase 3 into "complete" on the strength of a post-hoc, answer-aware, synthetic-only,
evaluator-side construction that the locked method does not have. It sets v1's achieved-shift error beside the baselines' although
the metric favours an encoder inversion by construction, and it omits the pre-registered true-latent spread, where v1 is worst. And it
reports a review V check that had not happened. With the status wording of V2-M1 (qualified completion, or "not declared complete"),
the comparability caveats and true-latent spread of V2-M2, and the corrected review row of V2-M3, the report would be accurate. None of
this bears on the method or on the headline conclusions.
