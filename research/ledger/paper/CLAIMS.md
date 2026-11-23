# Claims table for PREPRINT_v0.md

One row per claim. **File** and **field** are under `research/ledger/`. **Tag** is the git tag whose lock (or, for the exam results,
whose commit and OpenTimestamps proof) freezes the file. **Status**:
- *pre-registered, label-free*: no exam label involved;
- *pre-registered, blind*: labels and predictions frozen separately before unblinding;
- *post hoc*: rests on a pattern seen before its rule;
- *exploratory*: reported once, without a decision rule.

| # | Claim (section) | Value as printed | File | Field | Tag | Status |
|---|---|---|---|---|---|---|
| 1 | A0 left vs right copy, 250 types (R1) | 0.597 vs ceiling 0.951; ratio 0.63 (0.53-0.72); "a real gap" | `reliability_v2/A0.json` | `A0.primary_one_member_each_side.primary.{rho_x,c,ratio}`, `.bootstrap.interval.ratio`, `.words` | `ledger-reliability-v2` | pre-registered, label-free (PREREG v4 A0) |
| 2 | A0 drivers by side (R1) | 7 and 8 drivers, 1 in both | `reliability_v2/A0.json` | `...secondary.replication.full.pairs[0].{n_drivers_a,n_drivers_b,n_drivers_both}` | `ledger-reliability-v2` | pre-registered, label-free |
| 3 | Left vs right, MANC and MaleCNS (R2) | 0.59 (0.48-0.68); 0.64 (0.53-0.74) | `reliability_v2/A.json` | `six_agreements_primary_homolog_consistent["MANC-L vs MANC-R"]`, `["MaleCNS-L vs MaleCNS-R"]` | `ledger-reliability-v2` | pre-registered, label-free (PREREG v4 Part A) |
| 4 | Across flies, half-fly (R2) | 0.32-0.50 | `reliability_v2/A.json` | the four cross-fly entries of `six_agreements_primary_homolog_consistent` | `ledger-reliability-v2` | pre-registered, label-free |
| 5 | Across flies, whole types, 310 types (R2) | 0.38 (0.26-0.49) | `reliability_v2/A.json` | `reference_R1_whole_type_cross_fly.primary.ratio` and interval | `ledger-reliability-v2` | pre-registered, label-free |
| 6 | Wiring summaries agree (R2) | 0.71-0.98; two-step signed 0.71-0.84 | `reliability_v2/WIRING_A4.json` | `summaries_S1_S7_full_spearman[*][*].spearman` (min-max) | `ledger-reliability-v2` | pre-registered, label-free |
| 7 | Homologous connections on one side only; type-to-type in one fly only (R2) | 51 %; 58 % | `reliability_v2/WIRING_A4.json` | `single_connections.MANC.share_one_side_only`; `type_to_type_across_flies.pooled_sides.share_one_side_only` | `ledger-reliability-v2` | pre-registered, label-free |
| 8 | High-confidence: 215 types, 11 / 23 drivers, 2 in both, 1.2 expected (R2) | as printed | `replication_v1/R_replication.json` | `B1r_x_B2r.high.overlap.{n_types,n_drivers_x,n_drivers_B2r,n_both,expected_both_if_independent}` | `ledger-replication-v1` | post hoc |
| 9 | Replication rates, high confidence (R2) | 0.18 (0.00-0.44); 0.09 | `replication_v1/R_replication.json` | `B1r_x_B2r.high.overlap.point.{rate_x_in_y,rate_y_in_x}`, `bootstrap_95.rate_x_in_y` | `ledger-replication-v1` | post hoc |
| 10 | Matched-noise overlap ratio (OC), high confidence (R2) | 0.26 (0.00-0.55) | `replication_v1/R_replication.json` | `B1r_x_B2r.high.overlap.point.OC_ratio`, `bootstrap_95.OC_ratio` | `ledger-replication-v1` | post hoc |
| 11 | All 310 matched types: 3 of 15; OC ratio 0.27 (0.04-0.53) (R2) | as printed | `replication_v1/R_replication.json` | `B1r_x_B2r.all.overlap.{n_both,n_drivers_x}`, `point.OC_ratio`, `bootstrap_95.OC_ratio` | `ledger-replication-v1` | post hoc |
| 12 | 82 of 328 MaleCNS types have a low-confidence match (R2, Limitations) | as printed | `pertype_v1/match_confidence.csv` | count of `confidence == low` | `ledger-pertype-v1` | label-free (rule fixed before PREREG v5) |
| 13 | Replicated set, high confidence: DNg100, DNb08; all types adds DNit013 (R3) | as printed | `replication_v1/R_replication.json` | `B1r_x_B2r.high.categories.replicated.types`, `.all.categories.replicated.types` | `ledger-replication-v1` | post hoc |
| 14 | A0: 2 of 18 types with a driver copy have every copy a driver (DNb08, DNg100), among 308 (R3) | as printed | `replication_v1/R_replication.json` | `A0_copy_concordance.copies_on_both_sides.{n_types,n_with_a_driver_copy,concordant_types}` | `ledger-replication-v1` | post hoc |
| 15 | Two Poisson copies 0.48 (0.36-0.60) vs left-right 0.47 (0.34-0.59); test met (R4) | as printed | `reliability_v2/NOISE.json` | `primary_homolog_consistent.poisson.copy_vs_copy`, `.observed_left_right_paired_design`, `poisson.reproduces_left_right` | `ledger-reliability-v2` | pre-registered, label-free (PREREG v4 B4.5) |
| 16 | "Most of the gap, not demonstrably all" (R4) | words | `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md` | the six-pairing figure (post hoc) | `ledger-reliability-v2` (addendum after it, git history) | post hoc |
| 17 | Transplants: rest of network 0.34, own outputs 0.23 (MANC) (R4) | as printed | `reliability_v2/B2_MANC.json` | closures of the two transplants | `ledger-reliability-v2` | pre-registered, label-free |
| 18 | No fix passed; two broke the DNg100 control; 0.31-0.39 vs 0.8 (R4) | as printed | `reliability_v2/C.json`, `C_FIXES_1_TO_8.json` | `passing`, per-fix criteria | `ledger-reliability-v2` | pre-registered, label-free |
| 19 | S0: 448 of 448 regression digests identical (R5) | as printed | `gates_v5/S0_REGRESSION.json` | `digest_identical`, `verdict` | `ledger-replication-v1` | pre-registered |
| 20 | S1: p = 0.11 (52 of 455); "not shown" (R5) | as printed | `replication_v1/S_tests.json` | `tests.b1r_drivers.primary_stability.{p,n_subsets_ge,n_subsets}`, `verdict_words` | `ledger-replication-v1` | pre-registered, confirmatory, label-free |
| 21 | Stabilities: DNg100 16/16, DNit013 12/16, DNb08 7/16; DNxl133, DNxl102, DNp02 at least DNit013's (R5) | as printed | `replication_v1/S_tests.json` | `per_type[*].stability` | `ledger-replication-v1` | pre-registered, descriptive |
| 22 | A1 list p = 0.27; sensitivities 0.035, 0.033 (R5) | as printed | `replication_v1/S_tests.json` | `tests.a1_drivers.primary_stability.p`; `tests.b1r_drivers.sensitivity_ii_mean_copy_score.p`, `sensitivity_iii_mean_frac_rhythmic.p` | `ledger-replication-v1` | pre-registered, secondary / sensitivity (no words) |
| 23 | S2: 7 of 40 types, 26 of 640, none at stability 0.5 (R5) | as printed | `replication_v1/S_tests.json` | `S2_false_hits.*` | `ledger-replication-v1` | pre-registered |
| 24 | Smallest attainable p 0.002 (R5) | as printed | `PREREG_v5.md` | S7 | `ledger-prereg-v5` | pre-registered |
| 25 | Exam 1: 39 types (25 yes, 14 no), AUROC 0.577 (0.417-0.724); counting 0.669 (R6) | as printed | `results/run2/P.json` | `primary.{n,n_pos,auroc,boot}`, `baselines_auroc.S2_twohop_signed` | `ledger-scorecard-v1` (commit + OpenTimestamps `P.json.ots`) | pre-registered, blind |
| 26 | Exam 2: 0.633 (0.533-0.724), p = 0.008; two-hop signed 0.638; difference -0.006 (-0.172 to 0.166) (R6) | as printed | `results/run3/primary.json`, `results/RESULTS_2.md` | headline and wiring tables | `ledger-scorecard-h1` (commit + OpenTimestamps) | pre-registered, blind |
| 27 | Exam 2 labs' kappa 0.24 (R6) | as printed | `results/RESULTS_2.md` | ceiling paragraph | `ledger-scorecard-h1` | pre-registered, blind (descriptive) |
| 28 | 21 of 39 exam 1 types rest on the atlas alone (R6) | as printed | `labels_audit_v1/ERROR_RATES.json` | `census_39.atlas_only.all.n` | `ledger-replication-v1` | descriptive |
| 29 | DNg100's label: co-activation record, consensus rule, 23 records set aside; audited "yes" (R6) | words | `LABEL_AUDIT_v1.md` section 1; `labels_audit_v1/sessions/a5-F1/forensic.md`, `a5-F2/forensic.md` | | `ledger-replication-v1` | audit (pre-registered procedure) |
| 30 | Audit: 3 of 39 errors (7.7 %), 1 of 15 in the sample; no systematic fault; exam 1 stands; erratum for six exposed types (R6) | as printed | `labels_audit_v1/ERROR_RATES.json`, `LABEL_AUDIT_v1.md` | `census_39.all`, `sample_15.all`, `above_threshold`, `errata_exposed` | `ledger-replication-v1` | audit (pre-registered consequence rule) |
| 31 | Re-score with audited labels 0.559; counting 0.713 (R6) | as printed | `labels_audit_v1/RESCORE_exploratory.json` | `audited.auroc`, `audited.baselines_auroc.S2_twohop_signed` | `ledger-replication-v1` | exploratory |
| 32 | Tiers decide 30 of 54 audited labels (Limitations) | as printed | `labels_audit_v1/ERROR_RATES.json`; `comparison_with_exam1.csv` | `by_design_L5.decided_by_tiers` (length); rows | `ledger-replication-v1` | audit (descriptive) |
| 33 | The forward list and its decision rule (R7) | see section 7 | `forward_v2/` | | `ledger-forward-v2` | forward (outcomes unknown) |
