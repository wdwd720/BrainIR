# Post-lock review V: verification of the post-lock corrections to PHASE3_REPORT.md

Reviewer V (goal4 section 70). Scope: reporting, statistics and claims only. Nothing here proposes a change to the locked method.

**Method.**
- I read the corrected report in full, the four reviews (S, C, Y, R) and `docs/POSTLOCK_RESOLUTION.md`.
- I ran the project's own `scripts/postlock_numbers.py` with only its paths changed to the room layout (`.tmp/pn.py`, output
  `.tmp/POSTLOCK_NUMBERS.json`). `research/phase3/reviews/POSTLOCK_NUMBERS.json`, which the report cites, is not in this room.
- I checked the critical numbers independently of that script, straight from the stored files. My scripts are in
  `.tmp/postlock_V/`.

File abbreviations:

| short name | file |
|---|---|
| LC | `results/level_c/01/level_c_results.json` |
| FB / CB | `results/tournament/final_b/brainir_state_v1.json` / `lin_dmdc_t.json` |
| SA | `results/SELF_AUDIT.json` |
| AB | `results/ablations/ablations_final/SUMMARY.json` |
| GL | `results/review_g/results_locked_v3.json` |
| CX/<run> | `results/counterexamples/<run>/SUMMARY.json` and `jobs/` |
| CS | `results/COMPUTE_SUMMARY.json` |
| MB | `results/MODAL_BILLING.json` |
| FH | `results/tournament/final_b_H/FINAL_H_FAMILY.json` |

## Summary verdict

**Not yet acceptable: 1 blocker and 3 major issues. Almost all of the corrections are right.**

The large corrections all reproduce exactly from `results/`:
- the PCA retraction;
- the 17 + 2 split of the compact verdicts;
- the method's abstentions and the silencing-only C;
- state mediation, null pairs, n_eff and the interventional closure gap;
- robustness at 250 ms, with capped windows and the input-only control;
- the paired FINAL comparison against the comparator (McNemar);
- the counterexample mechanism;
- the Q14, Q19 and Q16 notes;
- the compute double-count and the billed amount;
- the lineage table, G statistics and the family-H recovery.

Of the 12 blocker findings (8 distinct after merging duplicates), all are resolved. Of the 39 major findings:
- 35 are resolved;
- 3 are partly resolved: S M5 and C M4 (lineage), and Y M2 (closure power in section 23);
- 1 is not resolved: C M9 (traps in the summary).

The corrections introduced one new false statement into the summary. Review C's claim that the locked method "does not abstain on the
non-compressible G10" was adopted without checking it, and the result file contradicts it. The resolution map also rejected one
reviewer number that is in fact right: Y's mean-based `nn_dim_rule` S3 CI. The resolution script computes a different S3 from the one
PROTOCOL.md defines. The corrected permitted claim still calls the net2-full latent a "state representation ... sufficient to predict",
although the method declared no compact state there. Finally, lineage is still missing from most Level C tables, which PROTOCOL.md
section 8 requires.

---

## BLOCKERS

### V-B1. "It does not abstain on the non-compressible G10" is false. It was introduced by the correction for C M9.

**Where:**
- Summary, "Traps and abstention", line 71: "On review G's 10 unseen traps it gets k wrong on 5 of 9 and does not abstain on the
  non-compressible G10."
- Section 18, line 1254: "it does not abstain on the non-compressible G10, which it rates 'partially supported' with k = 1."

**Evidence** (GL, `methods.brainir_state_v1`):
- `per_system["syn-f1c1d7b6cb"]` (trap G10, `g10_masked_highdim`): `abstain.no_compact_state = true`, with reason "latent explains
  too little beyond the input (val 0.072 > 0.5 x input floor 0.141)". It has k = 1 and verdict "partially supported" (predictive and
  interventional true; closed and microstate-equivalent false).
- `abstention`: `abstention_recall = 1.0` over `n_noncompressible = 1`. In other words, the method abstained on G10.
- It raised a false alarm on G3, with `no_compact_state = true` (`false_alarm_rate` 0.111 = 1 of 9). Its `confident_wrong_rate` is
  0.8.
- The report uses the same definition elsewhere. Section 6, line 434, says of round 2 that "only lin_dmdc abstains" on G10, and in
  `results/review_g/results_r2top.json` lin_dmdc is the only method with `no_compact_state = true` on G10. The FINAL abstention counts
  (FB `abstention`, "1 of 2") also count `no_compact_state`.
- The Q18 note (line 1370) and section 21 (line 1416) state only the verdict and k. Those are true.

**Origin.** Review C M9 wrote "no abstention on the non-compressible G10". The resolution map ("C M9: summary 'Traps and abstention'")
adopted it. The sentence therefore also makes false the claims in the summary (line 88) and in section 18.1 that every post-lock
finding was "corrected here".

**Correction:**
- Line 71: "On review G's 10 unseen traps it gets k wrong on 5 of 9 compressible traps. On the non-compressible G10 it declares no
  compact state (abstention recall 1 of 1), yet G10 still meets the 'partially supported' conditions with k = 1. It also abstains
  falsely on G3 (1 of 9)."
- Line 1254: the same wording.
- Section 18.1, row C: note that C's G10 statement did not reproduce.
- Resolution map: move this item to "did not reproduce".

---

## MAJOR issues

### V-M1. Y's `nn_dim_rule` S3 CI was rejected wrongly: Y is right, and the resolution script computes a different S3

**Where:**
- Section 10.1, lines 701-704: "Review Y's mean CI for `nn_dim_rule` S3 ([-0.066, -0.001]) is at the boundary; with the script's
  bootstrap it includes 0."
- The "Reading" sentence, lines 705-706: "The dimension-rule changes are not shown to help or hurt."
- Resolution map row "Y, m2".

**Evidence:**
- The frozen ablation summariser's own output agrees with Y: AB `variants.nn_dim_rule.paired_vs_full.S3_D_micro_gain`,
  `mean_diff` -0.0309, `mean_ci95` [-0.0660, -0.0013].
- `scripts/postlock_numbers.py` `_component(..., "S3")` returns the raw point `D_micro_gain`. PROTOCOL.md section 9 defines S3 as
  max(0, upper 95 % CI of the D micro-gain). With the raw point I get -0.0266 [-0.064, +0.004] (seeds 0-5: the upper bound is
  +0.002 to +0.004). With the pre-registered definition, recomputed from `ablations_final/{full,nn_dim_rule}.json` `verdict.D_ci95`,
  I get -0.0309 [-0.0664, -0.0016], which excludes 0.
- The same list also cites the script's value, not the stored one, for the sparsity S5 CI: the report has [0.002, 0.070], while AB
  has [0.0015, 0.0717].
- AB's mean CIs also exclude 0 at float level (about 1e-14) for S3 of 8 switches, which the report does not list: domain_clip,
  esindy, event_calibration, grid_extension, input_floor, oscillation_check, sharing and sharing_test.

**Correction:**
- Take every mean-based CI in section 10.1 from AB. Replace lines 701-704 with: "Mean-based paired differences (descriptive,
  unadjusted; AB `mean_ci95`) exclude 0 for `draw_folds` S1 (-0.14 [-0.33, -0.004]), `sparsity` S5 (+0.027 [0.0015, 0.072]) and
  `nn_dim_rule` S3 (-0.031 [-0.066, -0.0013]). They also exclude 0 at float level (about 1e-14) for `sharing_test` S1 and for S3
  of eight switches."
- Reading: "Replacing the rebuilt dimension rule does not measurably change the exact-k rate on unbiased data (-0.04
  [-0.15, 0.07]). Descriptively, it lowers the closure component S3 (mean -0.031 [-0.066, -0.001], unadjusted over 90 CIs)."
- Fix `postlock_numbers.py` to use S3 = max(0, upper CI of D), or cite AB.
- Resolution map: Y m2 "reproduces; adopted".

### V-M2. The permitted claim still calls the net2-full latent "sufficient", although the method abstained there

**Where:**
- Section 23, the "Permitted" claim, lines 1498-1504: "a 2-3 dimensional state representation ... was sufficient to predict the
  held-out readout of the three full networks better than input-only and persistence controls, with readout NMSE 0.024, 0.51 and
  0.0055."
- Section 23, lines 1471-1472.
- Summary, lines 49-50.

**Evidence** (LC `systems["real:net2:full"]`):
- `brainir_state_v1.verdict.abstention.no_compact_state = true` ("val 0.480 > 0.5 x input floor 0.843").
- On hidden data the same criterion also fails: A 0.514 > 0.5 x input-only 0.8165 = 0.408.
- The PCA-k latent with the same k is significantly better: `references.pca_k` A 0.445; paired difference +0.069 [0.010, 0.123].
- So is the comparator: A 0.285; secondary Holm p 0.013 (`secondary_superiority_holm["real:net2:full:A"]`).
- The "3" in "2-3 dimensional" comes from this seed-0 net2 fit alone. The modal k over seeds is 2 (`G.k` [3, 2, 2, 2, 2]).

The claim is qualified by the next sentence ("The method itself declared a compact state only for net1 and net3"). Even so, calling a
latent the method disowns a "state representation ... sufficient" stretches PROTOCOL.md section 7 ("a method's own abstention ... is
never converted into a verdict it did not claim"). It also stretches the goal4 section 88 rule of precise language. S B4 and Y B1 are
resolved in section 14 and in the summary's bullets, but not in the claim sentence itself.

**Correction.** Permitted claim: "Within the tested connectome-constrained rate model (…) and intervention domain, a 2-dimensional
state representation learned from public data was sufficient to predict the held-out readout of net1 full and net3 full (two builds
of one reconstruction) better than input-only and persistence controls, with readout NMSE 0.024 and 0.0055 at the 250 ms horizon
(e.g. net3: …). On net2 full (the independent reconstruction), a 3-dimensional latent (seed 0) predicted better than those controls
(NMSE 0.51 against 0.82), but the method itself declared that no compact state exists there, and a PCA latent of the same dimension
and the comparator predicted significantly better. …" Apply the same split to lines 1471-1472 and 49-50.

### V-M3. Lineage is still missing from most Level C rows, and some real counts are still pooled (S M5 and C M4 partly resolved)

**Where:**
- Section 14: the intervention table (lines 903-914), the prediction table (937-941), the reproducibility table (1026-1037) and the
  PCA-k comparison (948-952).
- Section 17: the robustness table (1158-1168).
- Section 16: the counterexample table.
- Summary, lines 50-51 and 58.
- Section 23, lines 1475-1476 and 1482.

**Rule.**
- PROTOCOL.md section 2.1: "LINEAGE (reported in every Level C row)".
- PROTOCOL.md section 8: "Every Level C row carries its lineage … Per-network results are reported separately, and cross-network
  pooling is descriptive."
- LC `lineage_rules`: counts "are reported per reconstruction and per mechanism family".

Only the first section 14 table has a lineage column.

**Pooled counts that remain:**
- "significantly better on 6 of 10": by lineage these are R1 net1 full, net3 full, net1 mech b, net3 mech a and net3 mech b, and R2
  net2 mech c;
- "PCA-k better on 2 of 10": both R2;
- "not supported on 9 of 10";
- "on 4 of 7 mechanisms it abstained on every held-out pair": net1 family 1 of 2, net2 family 2 of 3, net3 family 1 of 2;
- "microstate equivalence holds on 8 of 10".

**Correction:**
- Add the lineage column (R1 / R2; mechanism family) to every Level C table.
- Restate the pooled counts per reconstruction and family. For example: "The locked method is significantly better than PCA-k on
  both R1 full networks and on 3 of 4 R1 mechanisms; PCA-k is significantly better on R2 full and one R2 mechanism."

---

## Minor issues

1. **"The same to 3 decimals" is false** (section 14, line 925). LC `verdict.C` against `C_scrambled_mean` gives net1 1.268 against
   1.271 and net2 0.956 against 0.954: the report's own example differs in the third decimal. Only net3 matches (1.036). Write
   "within 0.003 on every full network; the CI of C - C_scrambled includes 0". In sections 23 (line 1509) and 24 (line 1520),
   "C equals C_scrambled" should read "C is indistinguishable from C_scrambled".
2. **Stored interventional value on the 4 all-abstained mechanisms** (S minor 3, only partly applied). In the section 14 intervention
   table (line 908 ff.) they are marked "untestable". LC `verdict.interventional = false`, with reason "pairs abstained on". Write
   "not met: every held-out pair abstained".
3. **Q15 reading is wrong for one baseline** (section 21, line 1429: "every linear baseline is significantly worse … on at least one
   component, prediction"). For lin_falds_t, SA Q15 gives S1 +0.005, not significant. Its only significant component is S2 (-0.648).
   Write "on at least one component (prediction for 5 of 6; held-out C for lin_falds_t)".
4. **Seed-0 against modal k** (section 14, line 1041). The list omits net2 mechanism b: seeds [3, 2, 2, 3, 2], seed-0 k 3 against modal
   k 2. The report's own table shows it.
5. **FINAL leave-one-component-out ranking missing.** Section 17 (line 1203) says the LOCO rankings are reported in sections 6 and 8,
   but section 8 has only S1-S5. Recomputed with `merge_rounds.descriptive_rankings`, the method is never first: without S1 4th,
   S2 5th, S3 2nd, S4 4th, S5 4th, S6 3rd, S7 2nd, S8 3rd. Add these to section 8.
6. **Capped windows at 100 ms** (section 17 table). The net1 value "1.82, 6 capped" should carry "≥", by the table's own rule. The
   statement "better on net2 (3.6 against 5.8, both lower bounds)" (line 1176) orders two lower bounds; write "not comparable (both
   capped: 19 and 60 windows)".
7. **Numbers that do not trace to `results/` in this room**:
   - N_obs peaking above 1 Hz (101, 136, 101, …);
   - "oscillation … in the training data of all 10 systems";
   - "calibration … chose gain 0 for kicks and currents" (the source only shows that support = calibrated and gain > 0,
     `brainir_state_v1.py` line 222);
   - "18 passed" for the real-data tests, and hence the summary's "552 passed".

   They come from the git-ignored run directory, the public data or a test log. The regenerated POSTLOCK_NUMBERS.json has
   `fit_record_seed0 = null` and `n_observed_peak_above_1Hz = null`. Add those records (or POSTLOCK_NUMBERS.json and the test log) to
   the result set.

   Summary, line 97: "552 passed" presents two runs as one suite. Write "534 passed, 1 skipped, 18 deselected; the 18 real-data tests
   run separately: 18 passed".
8. **Closure power next to section 23's "predictive and closed"** (net3 full, lines 58 and 1482; Y M2 asked for sections 8, 14 and
   23). Add "('closed' passes a latent missing one dimension about one time in six, section 4.2)".
9. **Category merging in trap sentences**:
   - summary line 69: the nuisance trap A result (8 against 1) is the E-untestable category;
   - section 18, line 1256: "the comparator … claims a compact state on G4" is `compact causal state discovered (microstate
     equivalence untestable)` in GL;
   - section 6, line 434: likewise for lin_falds on G10.

   Name the category (PROTOCOL.md section 7: never merged).
10. **Billing window** (section 22). MB ends with the hour starting 10:00Z. The family-H extraction ran on Modal at 11:18-11:23Z (FH;
    job-record estimate $0.39), after the window, so the $135.39 excludes it. Say so.
11. **Family-H run count** (section 17). The log (lines 34-35) says the extraction ran twice and the first summary was discarded;
    section 17 says only "logged". Add "run twice; the first run read the real-system horizon keys and was discarded".
12. **S7 "driven by 2 controls"** (section 8, line 576). S7 = (recall + 1 - false alarm) / 2. The difference of -0.12 is -0.25 from
    recall (2 controls) plus +0.13 from false alarms (46 systems). Write "driven by recall on the 2 controls, partly offset by fewer
    false alarms".
13. **Alternative normalisers** (section 14, line 923). Only the 1e-3 floor is given (1.12 / 0.99 / 1.00). LC `C_alt_scales` with a
    1e-2 floor gives 1.13 / 0.98 / 1.01. Give both, as PROTOCOL.md section 4 (A, normalisers) lists both.
14. **"All corrected here"** (summary, line 88; section 18.1). Amend this after V-B1 and V-M1, or list them as open.

---

## Question 1: status of every S, C, Y and R blocker and major

"Re-derived" names the file and key. Every number listed was reproduced unless stated otherwise.

### Review S

| finding | status | report section | numbers re-derived |
|---|---|---|---|
| B1 PCA "9 of 10" | resolved | summary; 14; 21 (Q16 note); 23 | LC `res.A_B._units` vs `references.pca_k.A_B._units`, `evaluate_cross.paired_diff`. At 250 ms: PCA-k significantly better on 2 (net2 full +0.069 [0.010, 0.123]; net2 mech a +0.028 [0.007, 0.052]); method significantly better on 6 (net1 full -0.019 [-0.033, -0.011]; net3 full -0.0013 [-0.0019, -0.0009]; net1 mech b; net2 mech c; net3 mech a; net3 mech b); no clear difference on 2. At 10 ms: point 1 of 10, significant 0. SA Q16 `A_pca_k` = the 10 ms means |
| B2 17 + 2 | resolved | summary; 4.1; 4.2; 8; 10.1; 23 | FB `verdict_counts_compressible` 17 / 2 / 12 / 15; AB event_calibration 9 + 1, delays 13 + 2 |
| B3 selection sentence | resolved | 6 | `r3v3/ROUND_DECISION.json` `descriptive.leave_one_component_out`: without S1 4th (5.43; lin_falds 4.86), without S2 tied 5.571 and placed 2nd, without S6 3rd; first in 5 of 8 |
| B4 net2 compact claim | resolved in summary and 14; claim sentence see V-M2 | summary; 14; 23 | LC net2 `abstention.no_compact_state` true |
| M1 abstentions, C scope | resolved | 14; 17 (statistics) | LC `C_abstained_pairs` 60 and `C_n_pairs_primary` 60 on each full network; `C_per_family` kick / pulse 30 of 30 abstained; comparator 0 |
| M2 C reporting rule, C items | resolved | 14 | null 45 / 49 / 47; n_eff 4.08 / 1.44 / 3.89; `C_nonnull` 1.20 / 0.955 / 1.02; `C_loo_max` 1.53 / 0.96 / 1.06; C - C_scrambled CIs as quoted |
| M3 net3 mech b | resolved | summary; 14 | C 0.3846 [0.215, 0.666]; `C_scrambled_mean` 0.346; CI [+0.015, +0.083] |
| M4 FINAL "worse" claims | resolved | summary; 8; 23 | SA Q15 lin_dmdc_t: S1 -0.30 [-0.57, -0.07]; S2-S5 CIs include 0. S6 exact: 27 against 16; 14 / 3 discordant; McNemar 0.0127; rate difference 0.239 [0.087, 0.413]. CB `abstention` 1.0 / 0.283 / 0.333 |
| M5 lineage, Q19 pooling | partly (V-M3) | 14 (one table); 16 (Q19 per sweep) | Q19 per sweep 0.188 / 0.0625 / 0.30 / 0.50; pooled 0.172; searchable 0.185 |
| M6 G statistics | resolved | 8; 14 table | LC `G` and `G_resample`: all 10 rows of the reproducibility table reproduce; FB G: 4 of 8 agree, r2 0.69-1.00, disagreement 1.14 (syn-146831129f) |
| M7 robustness horizon | resolved (minor 6) | summary; 17 | LC `res.H_ood` at 250 ms: net1 5.738 with 63 capped windows (235-fold); comparator 0.644 (28.7-fold); net2 3.598 with 19 capped; input-only rows as tabled |
| M8 S1-S5 rankings, RERANK_V3 | resolved (minor 5) | 6; 8 | round 3: 4.6 / 4.8 / 5.0. FINAL: 2.5 / 3.3 / 3.6. RERANK_V3 r3 v3 order: lin_subspace first |

### Review C

| finding | status | report section | numbers re-derived |
|---|---|---|---|
| B1 PCA | resolved | as S B1 | as S B1 |
| B2 compact merge, trap A | resolved | summary; 8; 23 | FB syn-5501045d59: k 8 against 1, K_min 0.116, diff CI [-0.40, 0.28] |
| B3 "never" | resolved | summary; 14; 23 | as S M3 |
| M1 silencing only | resolved | summary; 14; 23 | as S M1 and M2; comparator on common pairs (`primary_comparisons.*.C.ratio_b`): 1.10 / 1.05 / 12.5 |
| M2 own abstentions | resolved | summary; 14 | 8 of 10 `no_compact_state`; input floor on cce0c6c4, 3aa95ab7 and 92614efe |
| M3 model assumptions, title | resolved | title; summary; 14; 17; 23 | — |
| M4 lineage | partly (V-M3) | 14 | — |
| M5 causal wording | resolved (minor 1) | 8; 14; 23 | FB: not state-mediated on trap A and trap D ([-0.66, 0.003]); 27 state-mediated |
| M6 additive scope | resolved | summary; 8; 23 | — |
| M7 kick-clip, conditional verdicts | resolved | 8; 14; 17; 23 | FB `C_sensitivity.kick_clip`: 22 systems (1-9 pairs each); S2 0.483 to 0.456 |
| M8 sharing wording | resolved | summary; 14; 23 | LC `I` / `J`: shared = independent (891, 5,256, 3,504, 5,064, 3,897); J net1+net3 both directions (C -0.166 [-0.616, -0.008]; A -0.178 [-0.345, -0.054]) |
| M9 traps in the summary | **not resolved** (V-B1) | summary line 71; 18 | FINAL trap figures correct (FB); the G10 abstention statement is false (GL) |
| M10 Q8 | resolved | 21 | SA Q8 0.413 = 19 / 46; its real CIs = LC `C_effect_error_w100ms` (net1 [1.10, 2.31]) |
| M11 conclusion basis | resolved | 23 | net3 full `G_resample.r2_min_mean` -1.164 |

### Review Y

| finding | status | report section | numbers re-derived |
|---|---|---|---|
| B1 abstentions | resolved (see V-M2 for the claim sentence) | summary; 14 | as S M1 |
| B2 Markov with events | resolved | 8; 14 | LC `markov_detail.events_worst` null on 02fa13b8, 3aa95ab7, 6883ab7b and 362044b4. FB null on syn-6a7b88532a and syn-8e0956913a |
| B3 counterexample mechanism | resolved | 9; 16; summary; 23 | CX jobs: FINAL 4,048 candidates; 39.0 % near-null; 74.5 % numerator at most 10x; 76.8 % post-event NMSE < 1; worst near-null on 36 of 47; 19.6 % in-family on 44 systems; rates 0.082 / 0.141 in / out of family and 0.155 / 0.111 perturbed / nominal initial state; comparator 46.5 % near-null. Real: 71.3 % / 61.7 %; 86 % / 85 %; 20.5 % / 10.3 % in-family; rates 0.198 / 0.183 and 0.126 / 0.229 |
| M1 counterexample details | resolved | 16 | CX real `kinds_supported`; typical errors 4.92 / 4.53, 1.088 / 1.079, 1.031 / 1.061; medians 0.951 / 0.986; thresholds 16,130 / 57,730 and 385 / 770 |
| M2 closure power, "conditional" | partly (minor 8) | 4.2; 8; 14; 17 | `benchmark/calibration.json` closure power 0.80 / 0.244 / 0.172 |
| M3 wrong-k compact verdicts | resolved | summary; 8 | FB: 5 wrong-k compact verdicts (4 over, 1 under); Hopf k 2, 6, 6, 2; G: k changes on 4 of 8 |
| M4 k and rhythm, N_observed, resampling | resolved (oscillation and > 1 Hz not traceable here, minor 7) | 14 | LC `n_observed` 197, 3, 4, 213, 3, 6, 3, 211, 4, 3; k / N 50-167 %; `k_range` [2, 8] / [2, 5] / [2, 2]; half-sample k as tabled |
| M5 OOD horizon | resolved | 17; summary | as S M7 |
| M6 interventional closure gap | resolved | 14 | LC `verdict.interventional_closure_gap` 24.6 / 2.38 / 31.4; `ratio_no_effect` 24.4 / 2.45 / 31.3; comparator 1.09 / 1.01 / 1.03 |
| M7 I / J parameters, Q9, Q17 | resolved | 14; 21 | `method_own_verdict.test.transition_params` 16 / 53, 34 / 78, 16 / 30; SA Q9 `reported_status` n/a |
| M8 net1 + net3 absolute level | resolved | 14 | `ratio_a` 1.052, `ratio_b` 1.218 |
| M9 Q5, Q14 | resolved | 21 | SA Q14 finite ratios 1.010, 5.797, 1.199, 6.684, 1.039, 1.036: median 1.119, 2 above 3 |

### Review R

| finding | status | report section | numbers re-derived |
|---|---|---|---|
| B1 PCA | resolved | as S B1 | as S B1 |
| B2 Modal double count | resolved | summary; 22 | CS `totals_modal` $271.90 / 20,486 containers / 405.96 h; `postlock_correction.totals_before` $311.57. MB `total_usd` 135.39, `n_apps` 124; stages 45.14 / 11.09 / 79.16; CPU 70.32, memory 65.07. The CS rows sum to 271.905 |
| M1 abstention column | resolved | 14 | as C M2 |
| M2 state-independent C | resolved | summary; 14 | as S M2 |
| M3 OOD against input-only | resolved (minor 6) | 17 | LC `references.input_only.H_ood` |
| M4 significance | resolved | as S M4 | as S M4 |
| M5 K distribution | resolved | summary; 8; 15; 20; 23 | FB K = min of the two RFF R^2: median 0.9872, mean 0.8602, 13 below 0.9, 5 below 0.5 (0.116, 0.152, 0.160) |
| M6 acceptance table, log rows | resolved | 15; `EVALUATION_LOG.md` lines 19-33 (10 retrospective rows) | SA `criteria` of the failing checks match the self-audit column |
| M7 self-audit readings | resolved | 21 | SA `orchestrator_note`, `counts_reported` (15 / 3 / 1), `thresholds_fixed_at` d056d35; BENCHMARK_LOCK relock 1 `of.commit` d056d35. The room copy of `self_audit.py` is redacted (MANIFEST: 9 redactions), so its lock hash cannot be checked here |
| M8 18 deselected tests | resolved, not verifiable here (minor 7) | 15 | SA I10: 534 passed, 1 skipped, 18 deselected. No record of the separate 18-test run in `results/` |
| M9 compute items | resolved | 22 | CS `datasets_simulated`; `counterexample_protocols` sum 145,996; `level_c_fits` 145 records / 31.72 CPU-h / 16.12 h / 0 simulator calls; refusals sum 1,713; `fit_times` 24,088 s against 1,835 s; app ids on 32 of 85 rows |
| M10 missing items | resolved | 15; 17 (limitation 1, family H); 18.1; index | FH: ratio median 1.337, IQR 0.605-3.771, above 2 on 16, max 69.1; comparator 0.966 (0.365-2.013), above 2 on 12; paired -0.0054 [-0.0287, 0.0002]; largest relative difference 8.5e-16 |
| M11 LOIO and J directions | resolved | 14 | LC `I.net1.loio` (A +0.376 [0.294, 0.467], C +79.4; A +0.017 [-0.002, 0.039], C +0.231 [0.100, 0.313]; A +9.83, C +30.2); `I.net3.loio` A +0.116 [0.067, 0.172]; J net1+net2 A +4.92 [4.80, 5.04], C +251 [78, 926] |

## Question 2: reviewer numbers the resolution map did not adopt

| reviewer claim | my re-derivation (file, key) | who is right |
|---|---|---|
| C B1: "at 10 ms PCA-k better on 9 of 10" | LC matched 10 ms keys: PCA-k better by point on 1 of 10 (net1 mech a), significantly on 0. C's "9 of 10" compares PCA-k at 10 ms with the method at 250 ms | resolution map |
| C minor 3: "6 of the 8 E-equivalent systems have k >= N_observed" | LC `k` against `n_observed`: only net2 mech c (5 against 3); k / N on the mechanisms is 0.67, 0.75, 0.67, 0.50, 1.67, 0.75, 0.67 | resolution map |
| Y M4: "k = N = 3 on net2 mechanism a" | LC 3aa95ab7: k 2, N 3 (Y's own B1 table says k = 2) | resolution map |
| Y M3: "3 of the 8 G systems change k" | FB `G.*.k`: 0f1a2b2092 [3, 2, 2], 146831129f [3, 2, 3], 1de2b0aa08 [2, 1, 1] and 27e0511d5b [6, 5, 6] change, so 4 of 8 | resolution map |
| R M7: Q14 median over 6 finite ratios "1.04" | SA Q14: median of the 6 finite values = (1.039 + 1.199) / 2 = 1.119 | resolution map (and Y) |
| **Y m2: mean-based nn_dim_rule S3 CI excludes 0** | AB `mean_ci95` [-0.0660, -0.0013]; pre-registered S3 recomputed: [-0.0664, -0.0016]. The map's "includes 0" uses the raw D point estimate, not S3 | **Y** (V-M1) |
| S B1 "2 of 10 significantly" against C / R B1 "3 of 10" | 250 ms: point 3, significant 2 | both, as the map says |

## Question 3: new errors introduced by the corrections

- **False statements:** V-B1 (G10 abstention, summary and section 18), V-M1 (nn_dim_rule S3), minor 1 ("to 3 decimals"), minor 3
  (Q15 "prediction").
- **Numbers that do not trace to `results/`:** minor 7.
- **Contradictions between sections:**
  - section 6 (line 434) against summary line 71 and section 18 line 1254, on what "abstains" means for G10;
  - the section 14 table itself against line 1041 (seed-0 against modal k);
  - section 17 (line 1203) against section 8 (FINAL LOCO rankings).

  I found no numeric contradiction between summary, 8, 14, 15, 17, 21, 22 and 23 in any other value. Every summary number re-derives.
- **Claims stronger than the evidence:** V-M2 (net2 "sufficient"). **Weaker than the evidence:** the "Reading" of section 10.1
  (V-M1).
- **Protocol rules broken:**
  - lineage in every Level C row (PROTOCOL.md sections 2.1 and 8; V-M3);
  - E-untestable never merged (minor 9, trap sentences).

  The C reporting rule (section 8), the conditional-verdict statement (section 6), the "closed" wording (the section 6 power rule
  permits it) and the abstention rule of section 7 are otherwise followed.

## Question 4: minors listed as applied

| reviewer | status |
|---|---|
| S | 9 of 10 applied. Not applied: S3, the "untestable" label for the 4 all-abstained mechanisms (minor 2). The comparator pool and tie are stated as 8 plus the tie-break, which is correct: lin_dmdc_t and lin_pcadyn tie at 3.0 with 15 against 26 transition parameters |
| C | all 9 applied (C1 0.38; C2 group-silencing label and CIs; C3 with the corrected number; C4 3 of 10; C5; C6 "animal's"; C7 probe scopes 0.33-0.58 and 0.30-0.81, SA Q13; C8; C9 per-dimension shares 0.829 on net1 with 9 dimensions and 0.772 on net3 with 10) |
| Y | m1, m3, m4, m5, m6 (4 systems: 1c5ebb1701, 6a7b88532a, 8e0956913a, d7a7574c7e) and m7 applied. m2 is applied with a wrong conclusion on nn_dim_rule S3 (V-M1) |
| R | all 12 applied (numbers checked: 12 to 9.8e8 from CX `worst_range`; 97 files and 27 datasets from SA I3 `check_tail`; 8 lifting models with 0.31-1.02 achieved-shift error; 1-11 exclusions; PDT; sharing_test 3 evaluation failures in AB; answer-bearing line 3) |

## What I re-derived and found correct (beyond the tables above)

- **FINAL:**
  - conditions 32 / 24 / 36 / 34 (40 testable) / 27;
  - exact k 27, under 3, over 16;
  - abstention 0.5 / 0.022 / 0.521; the other control has k 3 and no abstention;
  - 14 systems with abstained held-out pairs; interventional closure-gap medians 0.70 / 0.66;
  - the lifting table (all 8 models, medians and testable counts).
- **Level C:**
  - every cell of the verdict table (k, seeds, modal k, abstention reasons, conditions, comparator k and verdict);
  - the intervention table;
  - the prediction table at 250 ms and 100 ms: full-state 0.020 / 0.476 / 0.0099; input-only 0.034 / 0.82 / 0.012;
  - A - input-only CIs with p <= 0.003 (Holm over 6 is still significant);
  - Holm primary (net2 C / E, net3 A / C 0.0065; net2 D 0.022; K 0.296) and secondary;
  - net3 E; probe accuracies.
- **Counterexamples:** all three tables; Q19.
- **Ablations:** every median effect and verdict count in section 10.1; S7 0.739 to 0.50; dev -0.15 [-0.30, -0.02] (sign fixed).
- **Self-audit:** statuses as computed and as reported; the Q6 real count (7 of 10); Q7 0.15 of 40; Q12 0.795; Q16 synthetic 0.083.
- **Compute:** task attributions (Level B $65.4; FINAL $54.8; Level C $11.12 + $31.0; ablations $23.96 / $27.83; six Modal sweeps
  $11.27; remote runner $14.34; hidden generation and checks about $12-13).
- **Log:** 10 retrospective rows and the two family-H rows (EVALUATION_LOG.md).

## Verdict

The post-lock reviews' blockers are resolved. Every S, C, Y and R blocker is corrected in the report, and the corrected numbers
re-derive from `results/`: the PCA retraction, the 17 + 2 split, the selection sentence, the method's abstentions, the "on no full
network" scoping, the Markov events caveat, the counterexample mechanism and the Modal double count. Of the majors, 35 of 39 are
resolved, 3 only partly (lineage in S M5 and C M4; closure power in section 23 in Y M2), and C M9 is not resolved. Its correction put a new false
statement into the summary and section 18: the locked method did abstain on review G's non-compressible G10
(`no_compact_state = true`, recall 1 of 1). That is a blocker under this review's definition. In addition, the resolution map
wrongly rejected Y's correct `nn_dim_rule` S3 CI, the permitted claim still calls the latent the method disowned on net2 full
"sufficient", and lineage is missing from most Level C rows. None of this touches the method or the headline conclusions: NOT
SUPPORTED on the rate-model simulations, partially supported on the synthetic FINAL suite. Once V-B1 and the three majors are
corrected, I would consider the post-lock reviews' blockers and majors resolved.
