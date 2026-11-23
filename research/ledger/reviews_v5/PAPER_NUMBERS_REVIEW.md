Numbers checked: 196; wrong: 11; unsourced: 5

Counting: one row per printed number or number word, per location (headings, section, figure and table numbers, version and tag names, citation years, type names, and number words with no checkable quantity, such as "one connectome", "two sides", "a second animal" or "three practices", are excluded). **Wrong** means the value, or its denominator, set, interval, direction or label, is misstated. **Unsourced** means no file frozen by a lock, a tag commit or an OpenTimestamps proof under `research/ledger/` or `ledger/` supports it. A further 30 numbers are correct and lock-frozen but have no CLAIMS.md row or field; their verdict is "OK, no CLAIMS row".

Reviewed: `research/ledger/paper/PREPRINT_v0.md` sha256 56953d8be654457932f416eb98fdf3b5a3adbae4285427966e4ec02741a3ac76 (last changed in 8d43572) and `CLAIMS.md` sha256 4ca1197580271c55b239c05a85049d466f7146336f3caf54e420ce6446b10779; HEAD 6bdd22e when this was written. Line numbers are those of that PREPRINT_v0.md.

How it was checked: every value was read from the named field with Python (`uv run --project ledger --no-sync`). The Part S rank tests, the S2 false-hit counts, the audit census, the decision-rule thresholds and powers, and the wiring ranges were recomputed from the per-row files. Every source file's SHA-256 was compared with its lock (all match), and every lock file with its tag (all identical). The exam files were compared with the scorecard tag commits (identical) and with the digests in their `.ots` proofs (match).

Freeze key: **[RV2]** `reliability_v2/`, LOCK_reliability_v2 (tag `ledger-reliability-v2`). **[REP]** `replication_v1/`, `gates_v5/`, `labels_audit_v1/`, `LABEL_AUDIT_v1.md`, LOCK_replication_v1 (`ledger-replication-v1`). **[PT]** `pertype_v1/`, LOCK_pertype_v1 (`ledger-pertype-v1`). **[FWD]** `forward_v2/`, LOCK_forward_v2 (`ledger-forward-v2`). **[P1]/[P3]/[P4]/[P5]** `PREREG.md` / `PREREG_v3.md` / `PREREG_v4.md` / `PREREG_v5.md` and `RUN5_PROMPT.md`, LOCK_prereg_v1/v3/v4/v5 (`ledger-prereg-v1/v3/v4/v5`). **[SC1]** `results/run2/P.json`, `results/RESULTS_1.md`: commit of `ledger-scorecard-v1` plus `.ots`. **[SCH1]** `results/run3/primary.json`, `results/RESULTS_2.md`: commit of `ledger-scorecard-h1` plus `.ots`. **[LH1]** `labels_h1/`, LOCK_labels_h1 (`ledger-labels-h1`). **[LV2]** `labels_v2/`, LOCK_labels_v2 (`ledger-labels-v2`). Paths are under `research/ledger/`.

## Table

| # | Number as printed | Location | Source file and field | Value found | Verdict |
|---|---|---|---|---|---|
| 1 | 0.63 | Abstract l.14 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.primary.ratio` | 0.6279 | OK |
| 2 | 0.53-0.72 (95 %) | Abstract l.15 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.bootstrap.interval.ratio` | 0.5308-0.7177 | OK |
| 3 | 11 (hits with a confidently matched counterpart) | Abstract l.15 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.n_drivers_x`; authors' list: `A1_x_B2r.high.overlap.n_drivers_x` | 11 for B1r (our MANC re-run); 6 for the authors' list A1 | WRONG (set): the abstract names only the authors' published screen and says it was "re-run", so the 11 reads as the authors' hits; they are our re-run's (B1r). Authors' list: 2 of 6 |
| 4 | 2 (hits in the second animal) | Abstract l.16 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.n_both` | 2 (also 2 for A1) | OK (post hoc, labelled) |
| 5 | those two = DNg100, DNb08 | Abstract l.16-17 | [REP] `B1r_x_B2r.high.categories.replicated.types` | DNb08, DNg100 | OK (post hoc, labelled) |
| 6 | p = 0.11 | Abstract l.18 | [REP] `S_tests.json` `tests.b1r_drivers.primary_stability.p` | 0.1143 (recomputed) | OK (pre-registered, label-free) |
| 7 | three replicated types | Abstract l.18 | [REP] `S_tests.json` `tests.b1r_drivers.replicated_from_locked_B2r` | 3 | OK |
| 8 | two blind exams | Abstract l.19 | [SC1] P.json; [SCH1] primary.json (unblind flags) | 2; prediction and label lock hashes in both files equal the current locks, and every lock `utc` precedes its unblind `utc` | OK (pre-registered, blind) |
| 9 | two-step (screen no better than two-step counting) | Abstract l.19 | [SC1] `results/run2/P.json` `primary.result` `.baselines_auroc.S2_twohop_signed` vs `.auroc`; [SCH1] `results/run3/primary.json` `vs_best_H-S` (best = `H-S-k2-signed`) | exam 1: 0.669 vs 0.577; exam 2: diff -0.006 (-0.172 to 0.166) | OK |
| 10 | six excluded types | Abstract l.20 | [REP] `labels_audit_v1/ERROR_RATES.json` `errata_exposed` | 6 | OK |
| 11 | three-neuron (rhythm-generating circuit) | Intro l.28 | none under research/ledger or ledger (only unlocked `BRIEF_v2.md` l.69) | - | UNSOURCED (claim about Pugliese et al.; no locked file, no CLAIMS row) |
| 12 | four connectome datasets | Intro l.29 | none (only unlocked `BRIEF_v2.md` l.70) | - | UNSOURCED |
| 13 | two blind exams | Intro l.37 | as Abstract l.19 | 2 | OK |
| 14 | two experimentally supported drivers ... are the hits that replicate | Intro l.39 | [REP] `confirmed_drivers`; `B1r_x_B2r.high.categories.replicated.types` | DNb08, DNg100 | WRONG (label): post hoc result stated without "post hoc" (PREREG v5 Part P) |
| 15 | 128 times | R1 l.45 | [P1] `PREREG.md` 3.2 (933 x 128); [PT] `A0_copies.csv` `n_replicates` | 128 for all 933 copies | OK, no CLAIMS row |
| 16 | 250 types | R1 l.46 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.n_types` | 250 | OK |
| 17 | 0.597 | R1 l.47 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.primary.rho_x` | 0.5974 | OK |
| 18 | 0.951 | R1 l.47 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.primary.c` | 0.9515 | OK |
| 19 | 0.63 | R1 l.47 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.primary.ratio`, `.words` | 0.6279, "a real gap" | OK (pre-registered, PREREG v4 A0) |
| 20 | 0.53-0.72 | R1 l.48 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.bootstrap.interval.ratio` | 0.5308-0.7177 | OK |
| 21 | Seven types | R1 l.48 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.secondary.replication.full.pairs[0].n_drivers_a` | 7 | OK |
| 22 | 0.5 (driver threshold) | R1 l.48 | [P4] `PREREG_v4.md` G5 | >= 0.5 | OK, no CLAIMS row |
| 23 | eight | R1 l.49 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `...pairs[0].n_drivers_b` | 8 | OK |
| 24 | one (driver on both) | R1 l.49 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `...pairs[0].n_drivers_both` | 1 | OK |
| 25 | three-way bands | R1 l.49 | [P4] G5 | driver / indeterminate / non-driver | OK, no CLAIMS row |
| 26 | kappa 0.47 | R1 l.49 | [RV2] `reliability_v2/A0.json` `A0.primary_one_member_each_side` `.secondary.kappa.full.value` (PREREG v4 G6(d)) | 0.4714 | OK, no CLAIMS row |
| 27 | two male connectomes | R2 l.54 | [P4] G2 | MANC, MaleCNS | OK, no CLAIMS row |
| 28 | 0.59 | R2 l.56 | [RV2] `A.json` `six_agreements_primary_homolog_consistent` `["MANC-L vs MANC-R"].primary.ratio` | 0.5866 | OK |
| 29 | 0.48-0.68 | R2 l.56 | same, `.bootstrap.interval.ratio` | 0.4846-0.6807 | OK |
| 30 | 0.64 | R2 l.56 | [RV2] `A.json` `six_agreements_primary_homolog_consistent` `["MaleCNS-L vs MaleCNS-R"].primary.ratio` | 0.6416 | OK |
| 31 | 0.53-0.74 | R2 l.56 | same, interval | 0.5278-0.7410 | OK |
| 32 | 0.32-0.50 | R2 l.56 | [RV2] `A.json` `six_agreements_primary_homolog_consistent`, four cross-fly entries | 0.4098, 0.3165, 0.3173, 0.4957 (215 types) | OK (Fig. 3 shows only the two same-side pairs) |
| 33 | 0.38 | R2 l.57 | [RV2] `A.json` `reference_R1_whole_type_cross_fly.primary.ratio` | 0.3801 | OK |
| 34 | 0.26-0.49 | R2 l.57 | same, `.bootstrap.interval.ratio` | 0.2648-0.4869 | OK |
| 35 | 310 matched types | R2 l.57 | same, `.n_types` | 310 | OK |
| 36 | seven summaries | R2 l.57 | [RV2] `WIRING_A4.json` `summaries_S1_S7_full_spearman` | S1-S7 | OK |
| 37 | 0.71-0.98 | R2 l.58 | same, `[*][*].spearman` | min 0.7130 (S2), max 0.9802 (S5_out_partners) | WRONG (set): called summaries "of each type's wiring to the motor neurons", but S4, S5 count all outputs and S7 is the member count (PREREG v4 A4(a)); the 0.98 is S5. The four motor-neuron summaries span 0.71-0.96 |
| 38 | 0.71-0.84 (two-step signed) | R2 l.58 | same, `[*]["S2_twohop_signed"]` | 0.7130-0.8402 | OK |
| 39 | about half / 51 % in MANC (exist on one side only) | R2 l.58-59 | [RV2] `WIRING_A4.json` `single_connections.MANC.share_one_side_only` | 0.5084; but `share_one_sided_only_because_of_floor` = 0.683 (38,545 of 56,421 have 1-4 raw synapses on the other side); raw 0 on the other side: 17,876 of 110,983 pairs = 16 % | WRONG (set): "exist" is at the 5-synapse floor, which the text omits; of the 110,983 pairs present at the floor on at least one side, 16 % have no synapse on the other side. Label: pre-registered (PREREG v4 A4(b)), the share seen before the v4 freeze and disclosed (PREREG v4 Part Q) |
| 40 | 58 % | R2 l.59 | [RV2] `WIRING_A4.json` `type_to_type_across_flies.pooled_sides.share_one_side_only` | 0.5814 | OK (also floored counts; not split) |
| 41 | 215 types | R2 l.61 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.n_types` | 215 | OK (post hoc) |
| 42 | 11 drivers (MANC, B1r) | R2 l.62 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.n_drivers_x` | 11 | OK |
| 43 | 23 (MaleCNS, B2r) | R2 l.62 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.n_drivers_B2r` | 23 | OK |
| 44 | two (drivers in both) | R2 l.62 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.n_both` | 2 | OK |
| 45 | 1.2 expected | R2 l.62 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.expected_both_if_independent` | 1.177 | OK |
| 46 | 0.18 | R2 l.63 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.point.rate_x_in_y` | 0.1818 | OK |
| 47 | 2 of 11 | R2 l.63 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.n_both`, `.n_drivers_x` | 2, 11 | OK |
| 48 | 0.00-0.44 | R2 l.63 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.bootstrap_95.rate_x_in_y` | 0.000-0.444 | OK |
| 49 | 0.09 | R2 l.63 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.point.rate_y_in_x` | 0.0870 | OK |
| 50 | 0.26 | R2 l.64 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.point.OC_ratio` | 0.2612 | OK |
| 51 | 0.00-0.55 | R2 l.64 | [REP] `R_replication.json` `B1r_x_B2r.high.overlap` `.bootstrap_95.OC_ratio` | 0.000-0.553 (2 of 10,000 resamples undefined) | OK |
| 52 | 310 matched types | R2 l.65 | [REP] `R_replication.json` `B1r_x_B2r.all.overlap` `.n_types` | 310 | OK |
| 53 | 3 of 15 | R2 l.66 | [REP] `R_replication.json` `B1r_x_B2r.all.overlap` `.n_both`, `.n_drivers_x` | 3, 15 | OK |
| 54 | 0.27 | R2 l.66 | [REP] `R_replication.json` `B1r_x_B2r.all.overlap` `.point.OC_ratio` | 0.2737 | OK |
| 55 | 0.04-0.53 | R2 l.66 | [REP] `R_replication.json` `B1r_x_B2r.all.overlap` `.bootstrap_95.OC_ratio` | 0.0423-0.5275 | OK |
| 56 | 2 of its 6 (A1, high confidence) | R2 l.67 | [REP] `R_replication.json` `A1_x_B2r.high.overlap.n_both`, `.n_drivers_x` | 2, 6 | OK, no CLAIMS row |
| 57 | exactly DNg100 and DNb08 (2) | R3 l.71 | [REP] `B1r_x_B2r.high.categories.replicated.types` | DNb08, DNg100 | OK (post hoc) |
| 58 | a third, DNit013 | R3 l.71 | [REP] `B1r_x_B2r.all.categories.replicated.types` | DNb08, DNg100, DNit013 | OK |
| 59 | low confidence, rated before looking | R3 l.72 | [PT] `match_confidence.csv` (DNit013 `confidence`); [P5] `PREREG_v5.md` Part Q; `RUN5_PROMPT.md` l.22 (locked); LOG L160-L161 (unlocked) | low; but RUN5_PROMPT l.22 already listed DNit013 as one of the 3 hits, and L160 records it was seen while the rule was written | WRONG (label): rated after the replication pattern was seen, by a rule fixed before Part R; not "before looking" |
| 60 | matched by body to DNit013, annotated DNit011 | R3 l.72 | [P5] Part Q; [PT] `match_confidence.csv` (`n_conflicts` 1) | as printed | OK, no CLAIMS row |
| 61 | two of 18 (all copies drivers) | R3 l.73 | [REP] `A0_copy_concordance.copies_on_both_sides.concordant_types`, `.n_with_a_driver_copy` | 2 (DNb08, DNg100) of 18 | OK (post hoc) |
| 62 | 308 types | R3 l.73 | same, `.n_types` | 308 | OK |
| 63 | DNg100's copies drive rhythm in both flies | R3 l.74 | [REP] `T_singlecopy.json` `focus.DNg100` | MANC 2/2 (0.98, 0.97); MaleCNS 2/2 (0.86, 0.78) | OK (descriptive, Part T), no CLAIMS row |
| 64 | four MaleCNS copies (DNb08) | R3 l.74 | [REP] `T_singlecopy.json` `focus.DNb08.MCNS.n_copies` | 4 | OK, no CLAIMS row |
| 65 | none (drives alone) | R3 l.74 | same, `.n_driver_copies` | 0 | OK, no CLAIMS row |
| 66 | 0.00-0.48 | R3 l.75 | same, `.copies` | 0.000, 0.000, 0.066, 0.476 | OK, no CLAIMS row |
| 67 | its whole type does | R3 l.75 | [PT] `B2r.csv` DNb08 `score` | 0.784 | OK, no CLAIMS row |
| 68 | two experimentally supported drivers hold up | R3 l.75 | [REP] `B1r_x_B2r.high.categories.replicated.types` | 2 | OK (post hoc section) |
| 69 | two confirmed neurons | R3 l.77 | [REP] `confirmed_drivers.caveats` | 2 | OK |
| 70 | two network copies | R4 l.81 | [RV2] `NOISE.json` `primary_homolog_consistent` `.poisson.copy_vs_copy` (pre-registered pair, PREREG v4 B4.2) | 2 | OK |
| 71 | 0.48 | R4 l.82 | [RV2] `NOISE.json` `primary_homolog_consistent` `.poisson.copy_vs_copy.primary.ratio` | 0.4838 | OK |
| 72 | 0.36-0.60 | R4 l.82 | same, `.bootstrap.interval.ratio` | 0.3579-0.6020 | OK |
| 73 | 0.47 | R4 l.82 | [RV2] `NOISE.json` `primary_homolog_consistent` `.observed_left_right_paired_design.primary.ratio` | 0.4693 | OK |
| 74 | 0.34-0.59 | R4 l.82 | same, interval | 0.3391-0.5893 | OK |
| 75 | met the pre-registered test | R4 l.83 | [RV2] `NOISE.json` `primary_homolog_consistent` `.poisson.reproduces_left_right` | true | OK |
| 76 | most of the gap, not demonstrably all | R4 l.84 | `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md` (in no lock; commit 71b0eb1, after the tag) | six pairings: about 86 % of the gap (0.66-1.14) | OK (post hoc, labelled); file identical at tags ledger-pertype-v1, -prereg-v5, -replication-v1, -forward-v2 but absent at ledger-reliability-v2 (the tag CLAIMS names); no lock hash, no OTS proof |
| 77 | 0.34 | R4 l.86 | [RV2] `B2_MANC.json` `primary_homolog_consistent.H_rest.closure.closure` | 0.3358 (0.10-0.53) | OK |
| 78 | 0.23 | R4 l.86 | same, `.H_own.closure.closure` | 0.2267 (-0.01-0.42) | OK ("closed more" compares point estimates; intervals overlap) |
| 79 | Eight pre-registered fixes | R4 l.88 | [P4] C1-C2; [RV2] `C.json` `primary` | fixes 1-8 (3a/3b, 5a/5b; 3b "not evaluated: no results collected") | OK |
| 80 | none passed | R4 l.89 | [RV2] `C.json`, `C_FIXES_1_TO_8.json` `passing` | [] in both | OK |
| 81 | two broke the DNg100 control | R4 l.89 | [RV2] `C.json` `primary.6.note`, `primary.8.note` | fixes 6 and 8 | OK |
| 82 | 0.31-0.39 | R4 l.90 | [RV2] `C.json` `primary.<fix>.cross_fly.ratio`, fixes 1, 2, 4, 5a, 5b, 7 | 0.313, 0.333, 0.392, 0.391, 0.378, 0.322 | OK |
| 83 | 0.8 required | R4 l.90 | [P4] C6.2 | ratio >= 0.80 | OK |
| 84 | once | R5 l.95 | [P5] header (one confirmatory test, S1) | 1 | OK |
| 85 | Sixteen Poisson copies | R5 l.95 | [REP] `S_tests.json` `n_copies`, `copy_seeds` | 16 | OK |
| 86 | all 448 of B1r's stored results | R5 l.96 | [REP] `gates_v5/S0_REGRESSION.json` `digest_identical`, `n`; [P5] S0; [PT] `B1r.csv` `n_replicates` | 448 of 448 re-run jobs = 56 Part S types x seeds 0-7; B1r stores 321 x 16 = 5,136 results | WRONG (denominator): 448 is the gate's sample, not all of B1r's results |
| 87 | 15 MANC drivers | R5 l.97 | [REP] `S_tests.json` `tests.b1r_drivers.drivers` | 15 | OK |
| 88 | the three that replicate | R5 l.97 | [REP] `S_tests.json` `tests.b1r_drivers.replicated_from_locked_B2r` | 3 | OK |
| 89 | p = 0.11 | R5 l.98 | [REP] `S_tests.json` `tests.b1r_drivers.primary_stability.p` | 0.1143 (recomputed) | OK (confirmatory; "not shown") |
| 90 | 52 of 455 | R5 l.98 | same, `.n_subsets_ge`, `.n_subsets` | 52, 455 (recomputed) | OK |
| 91 | all 16 copies (DNg100) | R5 l.99 | [REP] `S_tests.json` `per_type` DNg100 `stability` | 1.0 (16/16) | OK |
| 92 | DNit013 in 12 | R5 l.99 | same, DNit013 | 0.75 (12/16) | OK |
| 93 | DNb08 in 7 | R5 l.99 | same, DNb08 | 0.4375 (7/16) | OK |
| 94 | three non-replicating hits at least as stable | R5 l.99-100 | same, DNxl133, DNxl102, DNp02 | 0.875, 0.8125, 0.75 >= 0.75 | OK |
| 95 | 11-type list | R5 l.100 | [REP] `S_tests.json` `tests.a1_drivers.drivers` | 11 | OK |
| 96 | p = 0.27 | R5 l.100 | [REP] `S_tests.json` `tests.a1_drivers.primary_stability.p` | 0.2727 (recomputed) | OK (secondary, no words) |
| 97 | three replicated types | R5 l.100-101 | [P5] S7; [REP] `S_tests.json` `power_statement` | 3 | OK |
| 98 | 0.002 | R5 l.101 | [P5] S7 | 1/455 = 0.0022 | OK |
| 99 | 0.035 | R5 l.102 | [REP] `S_tests.json` `tests.b1r_drivers.sensitivity_ii_mean_copy_score.p` | 0.0352 (recomputed) | OK |
| 100 | 0.033 | R5 l.102 | [REP] `S_tests.json` `tests.b1r_drivers.sensitivity_iii_mean_frac_rhythmic.p` | 0.0330 (recomputed) | WRONG (set): this analysis is on the mean fraction rhythmic (PREREG v5 S5 iii), not "the mean score across copies" |
| 101 | 0.05 | R5 l.102 | [P5] S5 | 0.05 | OK |
| 102 | 40 sampled types | R5 l.103 | [REP] `S_tests.json` `S2_false_hits.n_types` | 40 | OK |
| 103 | 7 became drivers | R5 l.103 | same, `.types_with_any_driver_copy` | 7 | OK |
| 104 | 26 of 640 | R5 l.103 | same, `.pairs_with_copy_score_ge_0.5`, `.n_type_copy_pairs` | 26, 640 (22 of 26 from indeterminate types) | OK |
| 105 | none in half the copies | R5 l.104 | same, `.types_with_stability_ge_0.5` | 0 | OK |
| 106 | both exams: direct, two-step and three-step paths, signed or not | R6 l.108-110 | [P1] `PREREG.md` 3.5 (exam 1 S1-S7); [P3] `PREREG_v3.md` P3 (exam 2 H-S) | exam 1 has no three-step and no signed direct baseline (S1 unsigned, S2/S3 two-hop, S4-S7 non-path) | WRONG (set): true of exam 2 only |
| 107 | 39 labelled types | R6 l.111 | [SC1] `results/run2/P.json` `primary.result` `.n` | 39 | OK (pre-registered, blind) |
| 108 | 25 yes | R6 l.111 | [SC1] `results/run2/P.json` `primary.result` `.n_pos` | 25 | OK |
| 109 | 14 no | R6 l.111 | [SC1] `results/run2/P.json` `primary.result` `.n_neg` | 14 | OK |
| 110 | 0.577 | R6 l.112 | [SC1] `results/run2/P.json` `primary.result` `.auroc` | 0.5771 | OK |
| 111 | 0.417-0.724 | R6 l.112 | [SC1] `results/run2/P.json` `primary.result` `.boot.lo`, `.boot.hi` | 0.4171-0.7243 | OK |
| 112 | not better than chance (pre-registered rule) | R6 l.112 | [SC1] `results/run2/P.json` `primary.result` `.decision.model_predicts` | false (permutation p 0.18) | OK |
| 113 | 0.669 | R6 l.113 | [SC1] `results/run2/P.json` `primary.result` `.baselines_auroc.S2_twohop_signed` | 0.6686 | OK |
| 114 | 0.633 | R6 l.115 | [SCH1] `results/run3/primary.json` `H-M.mean_pr` | 0.6327 | OK (pre-registered, blind) |
| 115 | 0.533-0.724 | R6 l.115 | [SCH1] `results/run3/primary.json` `ci.lo`, `ci.hi` | 0.5331-0.7244 | OK |
| 116 | p = 0.008 | R6 l.115 | [SCH1] `results/run3/primary.json` `p` | 0.0076 | OK |
| 117 | 0.638 | R6 l.115 | [SCH1] `results/run3/primary.json` `H-S["H-S-k2-signed"].mean_pr` (= `best_H-S`; k = 2 is two-hop, PREREG v3 P3) | 0.6384 | OK |
| 118 | -0.006 | R6 l.115 | [SCH1] `results/run3/primary.json` `vs_best_H-S.diff` | -0.0057 | OK |
| 119 | -0.172 to 0.166 | R6 l.115 | [SCH1] `results/run3/primary.json` `vs_best_H-S.lo`, `.hi` | -0.1724 to 0.1662 | OK |
| 120 | two source laboratories | R6 l.116 | [SCH1] `RESULTS_2.md` l.28; [LH1] `labels_h1/agreement.json` `between_sources` | 2 (eLife 04493, 106042) | OK |
| 121 | kappa 0.24 | R6 l.116 | [SCH1] `RESULTS_2.md` l.28; [LH1] `agreement.json` `between_sources[...].kappa` | 0.2376 (n = 33 cells) | OK ("agree only moderately" overstates; see problems) |
| 122 | 21 of the 39 | R6 l.118 | [REP] `labels_audit_v1/ERROR_RATES.json` `census_39.atlas_only.n` (CLAIMS row 28's `...atlas_only.all.n` does not exist) | 21 (all intact_free, all yes) | OK |
| 123 | both forensic readers | R6 l.121 | [REP] `sessions/a5-F1/forensic.md`, `a5-F2/forensic.md`; `LABEL_AUDIT_v1.md` 1 | 2 | OK |
| 124 | one record | R6 l.121 | F1 forensic 0 (record -0042) | 1 | OK |
| 125 | two plain DNg100 records | R6 l.122 | F1 forensic 0 (-0020, -0011) | 2 | OK |
| 126 | 23 concordant records | R6 l.122 | F1 forensic (c); `LABEL_AUDIT_v1.md` 1(c) | 23, all front leg yes (14 headless single, 8 co-activation, 1 head-intact) | OK |
| 127 | 3 errors (of 39) | R6 l.123 | [REP] `labels_audit_v1/ERROR_RATES.json` `census_39.all.errors`, `.n` | 3, 39 | OK |
| 128 | 7.7 % | R6 l.123 | [REP] `labels_audit_v1/ERROR_RATES.json` `census_39.all.rate` | 0.0769 | OK |
| 129 | sample of 15: 1 error | R6 l.123-124 | [REP] `labels_audit_v1/ERROR_RATES.json` `sample_15.all.n`, `.errors` | 15, 1 | OK |
| 130 | 10 % threshold | R6 l.124 | [P5] L6; [REP] `labels_audit_v1/ERROR_RATES.json` `above_threshold` | census and sample both false | OK |
| 131 | six exposed types | R6 l.124 | [REP] `labels_audit_v1/ERROR_RATES.json` `errata_exposed` | 6 | OK |
| 132 | 0.559 | R6 l.125 | [REP] `RESCORE_exploratory.json` `audited.auroc` | 0.5592 | OK (exploratory) |
| 133 | 0.713 | R6 l.125 | same, `audited.baselines_auroc.S2_twohop_signed` | 0.7130 | OK (exploratory) |
| 134 | Three readings | R7 l.130 | [P5] F2; [FWD] `SHORTLIST.csv` | 3 | OK |
| 135 | top third | R7 l.133 | [P5] F2, G7 | tercile over A1's 321 types | OK |
| 136 | 12 types | R7 l.133 | [FWD] `SHORTLIST.csv` | 12 rows | OK |
| 137 | at least one available line | R7 l.133 | [FWD] `SHORTLIST.csv` `n_available` | min 1 | OK |
| 138 | 58 of the 78 lines | R7 l.134 | [FWD] `AVAILABILITY.csv` `listed_available` | 78 rows, 58 yes (2026-11-23) | OK |
| 139 | Table 1, near-replicated (4 types) | Table 1 l.138 | [FWD] `SHORTLIST.csv` readings | DNp71 y/n/y, DNa13 y/n/n, DNa07 y/y/n, DNa03 y/n/n | OK |
| 140 | Table 1, single-fly MANC (3 types) | Table 1 l.139 | same | DNp41 n/y/y, DNp02 n/n/n, DNg63 n/n/y | OK |
| 141 | Table 1, single-fly MaleCNS (2 types) | Table 1 l.140 | same | DNg13, DNg21 n/n/y | OK |
| 142 | Table 1, controls (3 types) | Table 1 l.141 | same; [REP] stable_non_driver | DNp07, DNg39, DNp26 n/n/y | OK |
| 143 | one-sided binomial at 0.05 | R7 l.144 | [P5] F5; [FWD] `DECISION_RULE.json` `rule` | as printed | OK |
| 144 | only four types | R7 l.145 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.A_replication_vs_single_connectome.max_n` | 4 | OK |
| 145 | up to 10 types | R7 l.146 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.B_replication_vs_counting.max_n` | 10 (recomputed from the table) | OK |
| 146 | 9 right needed | R7 l.147 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.B_replication_vs_counting.q` | 9 (recomputed) | OK |
| 147 | power 0.38 | R7 l.147 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.B_replication_vs_counting.power_a0.8` | 0.376 (recomputed) | OK |
| 148 | 0.74 | R7 l.147 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.B_replication_vs_counting.power_a0.9` | 0.736 (recomputed) | OK |
| 149 | 80 or 90 % | R7 l.147 | [P5] F5 power table | a = 0.8, 0.9 | OK |
| 150 | up to 8 | R7 l.148 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.C_single_connectome_vs_counting.max_n` | 8 (recomputed) | OK |
| 151 | 7 right needed | R7 l.148 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.C_single_connectome_vs_counting.q` | 7 (recomputed) | OK |
| 152 | 0.50 | R7 l.148 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.C_single_connectome_vs_counting.power_a0.8` | 0.503 (recomputed) | OK |
| 153 | 0.81 | R7 l.148 | [FWD] `forward_v2/DECISION_RULE.json` `comparisons` `.C_single_connectome_vs_counting.power_a0.9` | 0.813 (recomputed) | OK |
| 154 | both of DNp41's available lines (one DNg100) | R7 l.148-149 | [FWD] `SHORTLIST_LINES.csv` `other_dn_types` | SS67050: DNg100, DNp51; SS82242: DNp51 | OK |
| 155 | DNa03's only line, six other types | R7 l.149 | same | SS01592: DNa06, DNa09, DNp18, DNp19, DNp20, DNp22 | OK |
| 156 | the model's strongest hit (DNg100) | Disc l.153 | [PT] `A1.csv` `score` | DNg100 0.896 top (DNa07 0.843); in our B1r DNa07 0.861 > DNg100 0.828 | OK, no CLAIMS row |
| 157 | both replicate across animals | Disc l.154 | [REP] `B1r_x_B2r.high.categories.replicated.types` | DNb08, DNg100 | WRONG (label): post hoc result used as evidence of "a real signal" without "post hoc" |
| 158 | two-step (did not beat) | Disc l.157 | as R6 l.113, l.115 | 0.669 vs 0.577; 0.638 vs 0.633 | OK |
| 159 | three-neuron | Disc l.160 | none | - | UNSOURCED |
| 160 | four connectome datasets | Disc l.160 | none | - | UNSOURCED |
| 161 | both exams (counting did as well) | Disc l.167 | as R6 | as above | OK |
| 162 | three-neuron | Disc l.170 | none | - | UNSOURCED |
| 163 | One model and one behaviour | Lim l.176 | [P1] 3; [P4] G1 | as printed | OK, no CLAIMS row |
| 164 | Two animals, both male | Lim l.177 | [P4] G2 | MANC, MaleCNS | OK, no CLAIMS row |
| 165 | 82 of 328 | Lim l.179 | [PT] `match_confidence.csv` `confidence` | low 82 of 328 (high 217, medium 29) | OK |
| 166 | three replicated types | Lim l.182 | [P5] S7 | 3 | OK |
| 167 | one model family | Lim l.183 | [REP] `LABEL_AUDIT_v1.md` 7 | as printed | OK, no CLAIMS row |
| 168 | 30 of the 54 audited labels | Lim l.184 | [REP] `labels_audit_v1/ERROR_RATES.json` `by_design_L5.decided_by_tiers`; `comparison_with_exam1.csv` | 30; 54 rows (exam 1 labels of the audited types that have one; 73 audited) | OK (wording, see problems) |
| 169 | one of the three audit errors (scope rule) | Lim l.184 | [REP] `LABEL_AUDIT_v1.md` 3, 7 (DNg30) | 1 of 3 | OK |
| 170 | two laboratories | Lim l.185 | as R6 l.116 | 2 | OK |
| 171 | calibrated once on DNg100 | Lim l.187 | [REP] `R_replication.json` `confirmed_drivers.caveats`; [P4] C4 | as printed | OK, no CLAIMS row |
| 172 | our screens read out one side's motor neurons | Lim l.187 | [P4] G1; [P5] S3, Part T | only the one-sided half-fly screens do; B1r, B2r, Part S and Part T read all front-leg motor neurons | WRONG (set) |
| 173 | Two of the short list's types (DNp41, DNa03) | Lim l.189 | [FWD] `SHORTLIST_LINES.csv` | only these two have no clean available line | OK |
| 174 | Five runs | Methods l.193 | PREREG v1-v5 locks | 5 | OK, no CLAIMS row |
| 175 | 19-23 November 2026 | Methods l.193 | `LOCK_prereg_v1.json` `utc`; `LOCK_forward_v2.json` `utc` | 2026-11-20T06:35Z (19 Nov PST) to 2026-11-23T12:26Z | OK, no CLAIMS row |
| 176 | calibrated once on DNg100 | Methods l.199 | as Lim l.187 | as printed | OK, no CLAIMS row |
| 177 | at least 0.5 (driver) | Methods l.200 | [P4] G5 | >= 0.5 | OK, no CLAIMS row |
| 178 | 10,000-resample bootstrap | Methods l.201 | [RV2] `A0.json`, `A.json` `bootstrap.n_boot` | 10000 | OK, no CLAIMS row |
| 179 | 0.5 (threshold) | Methods l.205 | [P5] G2, R1 | 0.5 | OK, no CLAIMS row |
| 180 | 0.3 (band) | Methods l.205 | [P5] R1 | 0.3 | OK, no CLAIMS row |
| 181 | 0.05 (band) | Methods l.206 | [P5] R1 | 0.05 | OK, no CLAIMS row |
| 182 | 95 % over 10,000 resamples | Methods l.208 | [REP] `R_replication.json` `overlap.bootstrap` | n 10000, percentile 2.5-97.5 | OK, no CLAIMS row |
| 183 | Sixteen Poisson draws | Methods l.210 | [P5] S1; [REP] `S_tests.json` `copy_seeds` | 16 | OK |
| 184 | 5 synapses | Methods l.211 | [P5] S1 | floor 5 after resampling | OK, no CLAIMS row |
| 185 | 8 seeds | Methods l.212 | [REP] `S_tests.json` `seeds` | 0-7 | OK, no CLAIMS row |
| 186 | at least 0.5 (stability) | Methods l.213 | [P5] S4 | >= 0.5 | OK |
| 187 | 15 B1r drivers | Methods l.213 | [REP] `S_tests.json` `tests.b1r_drivers.drivers` | 15 | OK |
| 188 | 455 subsets of three | Methods l.213 | [REP] `S_tests.json` `primary_stability.n_subsets` | 455 | OK |
| 189 | three replicated types | Methods l.214 | [REP] `S_tests.json` `replicated_from_locked_B2r` | 3 | OK |
| 190 | 96 published sources | Methods l.217 | [LV2] `labels_v2/work/registry.csv` | 96 rows = exam 1's registry; exam 2's labels: [LH1] `labels_h1/registry_main.csv`, 3 sources (Harris 2015, Soffers 2025, Cheong 2024 summary) | WRONG (set): "Exam labels" covers both exams; 96 is exam 1 only (also no CLAIMS row) |
| 191 | two readings | Methods l.218 | [SC1] `RESULTS_1.md` l.118; [LH1] `agreement.json` `readings` | 2 | OK, no CLAIMS row |
| 192 | two independent readers per source | Methods l.219 | [P5] L3; `LABEL_AUDIT_v1.md` 2 | 2 | OK, no CLAIMS row |
| 193 | 250 types (Fig. 1) | Figures l.238 | script fig1 `len(w)` from [PT] `A0_copies.csv`; SVG title | 250 | OK |
| 194 | 215 high-confidence types (Fig. 2) | Figures l.239 | script fig2 from [REP] `B1r_x_B2r.high.table`; SVG title | 215 | OK |
| 195 | 95 % intervals (Fig. 3) | Figures l.239 | script `_ratio_ci` (bootstrap 2.5-97.5) | as printed | OK |
| 196 | 16 Poisson copies (Fig. 4) | Figures l.240 | [REP] `S_tests.json` `n_copies`; SVG axis | 16 | OK |

## Problems

### Wrong (11)

1. **Abstract l.15, "of 11 hits with a confidently matched counterpart, 2 are hits in the second animal" (row 3; moderate).** The abstract names only
   the authors' published screen and says it was "re-run on a second animal's connectome", so the 11 reads as the authors' hits. They are the hits
   of our MANC re-run, B1r (`R_replication.json` `B1r_x_B2r.high.overlap.n_drivers_x` = 11). For the authors' own list (A1) the high-confidence
   figures are 2 of 6 (`A1_x_B2r.high.overlap`). Fix: name the screen ("of the 11 hits of our MANC re-run with a confidently matched
   counterpart"), or give the authors' 2 of 6.
2. **Intro l.39, "whose two experimentally supported drivers, as shown below, are the hits that replicate" (row 14; minor).** This restates the
   post hoc replication result (PREREG v5 Part R) without "post hoc". PREREG v5 Part P requires post hoc results to be named as such. Fix: add
   "(post hoc)".
3. **Discussion l.153-154, "... its novel prediction was confirmed in flies, and both replicate across animals" (row 157; moderate).** The same
   post hoc result is used, without its label, as evidence that the screen "carries a real signal". Fix: add "(post hoc)".
4. **R2 l.57-58, "seven summaries of each type's wiring to the motor neurons correlate at 0.71-0.98" (row 37; minor).** Only S1, S2, S3 and S6
   describe wiring to the front-leg motor neurons. S4 and S5 summarise all outputs and S7 is the member count (PREREG v4 A4(a)). The 0.98 is
   S5, output partners, MANC-L vs MANC-R. The four motor-neuron summaries span 0.71-0.96. Fix: drop "to the motor neurons", or give 0.71-0.96
   for those four.
5. **R2 l.58-59, "about half of the homologous neuron-to-neuron connections exist on one side only (51 % in MANC)" (row 39; moderate).** The 51 %
   counts connections at the 5-synapse floor, which the text does not say. The same file shows that, for 68 % of those MANC pairs (38,545 of
   56,421), the partner on the other side has 1-4 synapses (`single_connections.MANC.share_one_sided_only_because_of_floor` = 0.683). Only
   17,876 of the 110,983 pairs present at the floor on at least one side (16 %) have no synapse on the other side. Fix: "at the 5-synapse
   floor, 51 % ... (two thirds of these have 1-4 synapses on the other side)". The 58 % type-to-type figure also rests on floored counts.
   The share is pre-registered (PREREG v4 A4(b)), but it was seen before the v4 freeze and disclosed (PREREG v4 Part Q, l.42-44). The text
   could say so.
6. **R3 l.72, "on a match we rated low confidence before looking" (row 59; moderate).** The replication pattern was already in `RUN5_PROMPT.md`
   l.22 ("In both flies: 3 types. DNg100, DNb08 and DNit013") before the confidence rule was written. PREREG v5 Part Q, and LOG L160, record
   that DNit013's low rating was seen while the rule was being defined. LOG L161 lists "the match-confidence rule bends to the replication
   pattern (DNit013 was seen)" as a risk. The rule was fixed before Part R, as Methods l.205 says, not before looking. Fix: "on a match rated low
   confidence by a rule written after the pattern was seen, before Part R (LOG L160)". CLAIMS row 12's status should say the same.
7. **R5 l.96, "a regression gate reproduced all 448 of B1r's stored results digest for digest" (row 86; minor).** S0 re-ran the 56 Part S types
   at seeds 0-7, which is 448 jobs (PREREG v5 S0; `gates_v5/S0_REGRESSION.json` `n` = 448). B1r stores 321 types x 16 seeds = 5,136 results
   (`pertype_v1/B1r.csv` `n_replicates`). Fix: "reproduced B1r's stored results digest for digest in all 448 re-run jobs (56 types x 8 seeds)".
8. **R5 l.101-102, "Two sensitivity analyses on the mean score across copies fell below 0.05 (0.035 and 0.033)" (row 100; minor).** 0.035 is
   sensitivity (ii), the mean copy score. 0.033 is sensitivity (iii), the mean fraction rhythmic over copies (PREREG v5 S5;
   `sensitivity_iii_mean_frac_rhythmic.p`). Fix: "on the mean copy score (0.035) and the mean fraction rhythmic (0.033)".
9. **R6 l.108-110, "both included pre-registered wiring baselines: counts of direct, two-step and three-step synaptic paths ..., signed or not"
   (row 106; minor).** Exam 1's baselines (PREREG v1 3.5, S1-S7) have no three-step count and no signed direct count. They include total
   outputs, output partners, premotor input and member count instead. The description fits exam 2 only (PREREG v3 P3: k = 1-3, signed and
   unsigned, plus membership and the linearised model). Fix: describe each exam's baselines separately.
10. **Limitations l.187, "our screens read out one side's motor neurons where the authors' single-neuron screen reads both" (row 172; minor).**
    Only the one-sided half-fly screens (PREREG v4 G1 one-sided variant; Parts A-C, so all of Results 4) read one side. B1r and B2r (the
    whole-type variant), Part S and Part T read all front-leg motor neurons. The replication results (Results 2-3) and Part S (Results 5) rest
    on those. Fix: "our one-sided (left-right) screens read out one side's motor neurons".
11. **Methods l.217, "Exam labels were collected from a registry of 96 published sources" (row 190; minor).** 96 is exam 1's registry v2
    (`labels_v2/work/registry.csv`, 96 rows, LOCK_labels_v2). Exam 2's labels came from `labels_h1/registry_main.csv`, 3 sources: Harris et al.
    2015, Soffers et al. 2025, and the Cheong et al. 2024 summary (LOCK_labels_h1). The number also has no CLAIMS row. Fix: "Exam 1's labels came
    from a registry of 96 sources; exam 2's from two laboratories' published screens".

### Unsourced (5)

12. **"three-neuron" (Intro l.28; Discussion l.160 and l.170) and "four connectome datasets" (Intro l.29; Discussion l.160) (rows 11, 12, 159,
    160, 162).** These describe Pugliese et al.'s pruning result. No locked file under `research/ledger/` or `ledger/` states them; the only
    mention is the unlocked `BRIEF_v2.md` l.69-70. CLAIMS.md has no row for them, and they contradict the Status line ("Every number comes from a
    file frozen by a lock"). Fix: cite the paper (section or figure) for them and exempt cited facts in the Status line, or add a CLAIMS row
    pointing to a locked copy of the source.

### Sources and freezing (not counted)

13. **Status line l.7.** Apart from item 12, the claim "most of the gap, not demonstrably all" (R4 l.84, row 76) rests on
    `reviews_v4/ADVERSARIAL_ADDENDUM_v4.md`. No lock hashes that file and it has no OTS proof. It was committed in 71b0eb1, after the
    `ledger-reliability-v2` tag, and is absent at that tag. It is identical at the later tags `ledger-pertype-v1`, `ledger-prereg-v5`,
    `ledger-replication-v1` and `ledger-forward-v2`, so a tag commit fixes it, but not the one CLAIMS names. The Status line's "file frozen by a
    lock" does not hold for it.
14. **Data and code, l.235-236.**
    - The tag list omits `ledger-reliability-v2` (Results 1, 2 and 4) and `ledger-scorecard-v1` / `ledger-scorecard-h1` (Results 6). CLAIMS
      relies on all three.
    - It also omits `ledger-labels-v2` and `ledger-labels-h1`. CLAIMS cites neither, but they freeze the machine-readable sources of the 96
      sources (item 11) and of the kappa 0.24.
15. **OpenTimestamps.**
    - At the time of this review, the proofs of `LOCK_replication_v1.json` and `LOCK_forward_v2.json` are pending, with no Bitcoin attestation
      yet; commit f43f268 says so. They back Results 2, 3, 5, 6 (audit) and 7.
    - The proofs of the other locks used here, and of `P.json`, `run3/primary.json`, `RESULTS_1.md` and `RESULTS_2.md`, contain a Bitcoin
      attestation and match the files' SHA-256. This was checked from the proof bytes; the chain itself was not verified.
    - For both exams, the prediction and label lock hashes in the result files equal the current locks, and each lock's `utc` precedes the
      unblinding `utc`, so the "blind" label holds.

### CLAIMS.md (not counted)

16. **Field paths that do not resolve.**
    - Row 25: the fields are under `primary.result`, as `primary.result.{n,n_pos,auroc,boot}` and
      `primary.result.baselines_auroc.S2_twohop_signed`.
    - Row 28: `census_39.atlas_only.all.n` does not exist; the field is `census_39.atlas_only.n` (21).
    - Every other field named resolves to the printed value.
17. **Row 16's tag.** `ledger-reliability-v2` does not contain the addendum. Later tag commits do, but no lock and no OTS proof covers it
    (item 13).
18. **Rows with no field.**
    - Row 17: `B2_MANC.json` `primary_homolog_consistent.H_rest.closure.closure` and `.H_own.closure.closure`.
    - Row 26: `H-M.mean_pr`, `ci`, `p`, `H-S["H-S-k2-signed"].mean_pr` and `vs_best_H-S`.
    - Row 33: `SHORTLIST.csv`, `AVAILABILITY.csv`, `SHORTLIST_LINES.csv` and `DECISION_RULE.json`.
    - Row 27 could cite the machine-readable `labels_h1/agreement.json` `between_sources[...].kappa` = 0.2376 (LOCK_labels_h1).
19. **Row 12's status.** It should add that the confidence rule was written after the replication pattern was seen (item 6).
20. **Printed results with no CLAIMS row.** All are lock-frozen, and all are correct except the 96, whose set is wrong (item 11):
    - A0's 128 replicates.
    - kappa 0.47 (`A0.json` `...secondary.kappa.full.value`).
    - A1's 2 of 6 (`A1_x_B2r.high.overlap`).
    - DNit013's DNit011 annotation (PREREG v5 Part Q).
    - Part T (`T_singlecopy.json` `focus`): DNg100's copies, DNb08's four MaleCNS copies, none of them a driver, 0.00-0.48. Also DNb08's
      whole-type B2r score of 0.784 (`B2r.csv`).
    - The authors' top type DNg100 (`A1.csv`).
    - The 96 sources.
    - Design and method constants: 0.5, the bands, 10,000 resamples, 5 synapses, 8 seeds, five runs and their dates, the numbers of readers.
      These are the remaining "OK, no CLAIMS row" rows.

### Wording attached to correct numbers (not counted)

21. **R6 l.116, "agree with each other only moderately (kappa 0.24)".** `RESULTS_2.md` calls it "only 0.24 (chance agreement is 0.72)" and says
    the labs disagree. The draft's own Limitations (l.185) say "disagree". A kappa of 0.24 is usually read as fair, not moderate.
22. **R2 l.56-57.** The 0.32-0.50 range is cited to Fig. 3. Fig. 3 shows only the two same-side pairs (0.41, 0.32); the 0.50 is the
    opposite-side pair, MANC-R vs MaleCNS-L.
23. **R4 l.88-90, "Eight ... fixes ... were judged on agreement across flies, sides and hits".**
    - Fix 3b was never evaluated (`C.json` note: "no results collected").
    - Fix 3 could not pass by design (there are no pre-floor MaleCNS counts).
    - Fixes 6 and 8 stopped at the control.
    - The breakdown ("two broke the control, those judged on every criterion ...") leaves fix 3 out.
24. **R4 l.86, "closed more of the gap (0.34) than ... (0.23)".** This compares point estimates whose intervals overlap (0.10-0.53 and
    -0.01-0.42), and the difference was not tested.
25. **Limitations l.184, "30 of the 54 audited labels".** These are exam 1's labels for the 54 audited types that have one; 73 types were
    audited. The "tie-breaks" are the consensus rule's tiers.
26. **R5 l.103, "drivers in neither screen".** This means neither B1r nor A1, both MANC screens, not neither fly.
27. **R5.** The pre-registered reference test on the real network's own score (`reference_v_B1r_score_seeds0to15` p = 0.32; seeds 0-7
    p = 0.37) is not reported beside the two sensitivity values.

### Non-numeric statements met while checking (not counted)

28. **Abstract l.20, "an audit of the exam labels upheld them".** The audit (Part L) covered exam 1 only.
29. **Abstract l.19, "the screen did no better".** Exam 2 scored BrainIR's hemilineage simulation (H-M), not the DN screen.
30. **Intro l.37-38, "readers who never saw a simulation score".** Exam 1's dedicated sessions read the simulation papers. Their records were set
    aside as sightings, as R6 says.
31. **R6 l.119, "types the readers had seen discussed alongside simulation scores were excluded".** The v1 exposed list came from the
    designers' notes (PREREG v1 section 2). Types whose records all came from dedicated sessions were added later (PREREG v2 L6).
32. **R2 l.66-67, "The thresholds matter less than the pattern: the authors' own list (A1) gives the same picture".** A1 is a different screen,
    not a different threshold.
33. **R6 l.120, "re-read every source".** The audit read exam 1's cached sources (64 plus the atlas); 9 audited types had none.

## Figures

- **Reproduction.** All four figures regenerate byte-identically from `ledger/scripts/posthoc/paper_figures_v5.py`, all 8 files (SVG and PNG).
  - The run used matplotlib 3.9.2, as the script's docstring says, and wrote to a scratch folder.
  - The script's sha256 d9350f97...c520 is the hash recorded in the `code` entries of LOCK_replication_v1 and LOCK_forward_v2, and in amendment
    row 5 of `AMENDMENTS_v5.jsonl`.
- **Inputs.** All inputs are locked and match:
  - `pertype_v1/A0_copies.csv` [PT].
  - `reliability_v2/A0.json`, `A.json` and `NOISE.json` [RV2].
  - `replication_v1/R_replication.json` and `S_tests.json` [REP].
- **The figure files.** No lock hashes them. They were committed in 0940de4, after LOCK_forward_v2. Their guarantee is that the locked script
  reproduces them.
- **Numbers printed inside the figures** match the locked values. They are not counted in N:
  - Fig. 1: "128 runs" and "250 types".
  - Fig. 2: 215, with legend counts 2 / 7 / 13.
  - Fig. 3: 0.63, 0.59, 0.64, 0.41, 0.32, 0.38, 0.47 and 0.48.
  - Fig. 4: 16 drivers (15 from B1r, plus DNg54 from A1 only), their stabilities, and p = 0.11.

## Lengths

- Abstract: 196 words (limit 200).
- Whole file: 3,725 words; 3,611 from the abstract to the end (whitespace tokens; limit 3,500-4,500). Both are within the limits.

## Side effect

- Regenerating the figures left one git-ignored bytecode file, `ledger/scripts/posthoc/__pycache__/paper_figures_v5.cpython-312.pyc`.
- The figures themselves were written to a scratch folder outside the repository.
- This report is the only other file written.
