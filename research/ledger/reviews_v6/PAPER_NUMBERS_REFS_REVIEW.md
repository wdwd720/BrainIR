# Numbers and references review of PREPRINT_v1 and SUPPLEMENT_v1

Read-only; no simulation (P1 read stored sweep logs via `brainir_ledger.screens6`). Paths under `research/ledger/`. **C** =
`thirdfly_v1/C_tests.json`, **H** = `posthoc_v6/H_posthoc.json`, **TS** = `gates_v6/TYPE_SETS_v6.json`, **S** = `replication_v1/S_tests.json`,
**ER** = `labels_audit_v1/ERROR_RATES.json`; R1-R7 = Results sections. Misdescribed = value right, set/procedure/status wrong.

## 1. Numbers checked

| # | Claim (where) | Printed | File: field | Found | Verdict (CLAIMS row) |
|---|---|---|---|---|---|
| 1 | Authors' screen left vs right, 250 types, 128 runs; hits L / R / both (Abs, R1, Fig. 1) | 0.63 (0.53-0.72), real gap; 250; 128; 7/8/1 | `reliability_v2/A0.json`: A0.primary_one_member_each_side.{primary.ratio, bootstrap.interval.ratio, words, secondary.replication.full.pairs[0]}; `pertype_v1/A0_copies.csv` | 0.628 (0.531-0.718), "a real gap"; 250; 128; 7/8/1 (DNg100) | OK (1) |
| 2 | One-sided MANC, MaleCNS (R1, Fig. 2) | 0.59 (0.48-0.68); 0.64 (0.53-0.74) | `reliability_v2/A.json`: six_agreements_primary_homolog_consistent | 0.587 (0.485-0.681); 0.642 (0.528-0.741) | OK (2) |
| 3 | BANC left vs right (Abs, R1, Fig. 2) | 0.58 (0.38-0.77), real gap | C1.label_consistent_noDNg100 (180 types), C1.words | 0.582 (0.383-0.766) | OK (3) |
| 4 | MANC count noise, 5-synapse floor (R2, Fig. 2) | 0.48 (0.36-0.60) vs 0.47 (0.34-0.59); 5 | `reliability_v2/NOISE.json`: primary_homolog_consistent; PREREG_v4 B4.2 | 0.484 (0.358-0.602); 0.469 (0.339-0.589); floor 5 | OK; floor unsourced |
| 5 | BANC count noise (R2, Fig. 2) | 0.78 (0.64-0.89) vs 0.58; -0.21 (-0.37 to -0.05) | C2.label_consistent_noDNg100 | 0.777 (0.640-0.887); -0.208 (-0.370 to -0.052), a rho_x difference | misdescribed, P3 (5) |
| 6 | BANC has no threshold (R2, Lim.) | words | LOG L177 ("no floor") | as printed | OK (6) |
| 7 | First two animals, current-setting, 181 types (R3) | 0.40 (0.25-0.54) | C3.tuned["MANC-MaleCNS (reference, post hoc)"].three_animal_noDNg100 | 0.396 (0.245-0.539) | OK (7) |
| 8 | Sweep across animals (Abs, R3, Fig. 2) | 0.35 (0.20-0.49); 0.50 (0.38-0.62); 0.31 (0.17-0.45); confirmed | C3.sweep.*.three_animal_noDNg100; C3.first_line_words | 0.349 (0.200-0.486); 0.505 (0.376-0.621); 0.314 (0.170-0.451) | OK (8) |
| 9 | Wiring check (R3) | 0.82; 0.61, 0.63; 0.71 | C3_wiring.spearman, .floor; `reliability_v2/WIRING_A4.json` | 0.823; 0.611, 0.632 at a 5-synapse floor (0.626, 0.628 without); 0.713 | misdescribed, P6 (9) |
| 10 | First two animals at 0.5 and 0.3 (Abs, R3, Fig. 3) | 1 of 10 and 22, 1.0 expected, 214; 14 vs 6 | H: pairs.tuned_B1r_x_B2r["high\|without_DNg100"].cuts | 1, 10, 22, 1.03, N 214; 14, 5.96 | OK in R3; abstract misdescribed, P2 (10) |
| 11 | Sweep, first two animals (R3, Fig. 3) | 14 of 18, 6 expected | H: sweep_dx1_x_ms["high\|without_DNg100"].cuts["0.5"] | 14/18, 5.97 | OK (11) |
| 12 | Recurrence in BANC (Abs, R3, Disc.) | 5 of 17, 1.7, p 0.016; 12 of 60, 6.3, p 0.004; 1 of 6, 0.6, p 0.47 | C4[list][set].cuts["0.5"].overlap.point, words_at_0.5 | 5/17, 1.683, 0.0162; 12/60, 6.264, 0.0044; 1/6, 0.594, 0.4695 | values OK; sets, "its 6 hits" misdescribed, P5, P7 (12) |
| 13 | K = 1 chosen on DNg100; DNg100 not a hit in MaleCNS under K = 0 (R4, Methods) | 1 | PREREG_v2 P1; `predictions/B2/types.csv` primary_score | smallest of {1,2,3,5,10}; 0.059 | OK (13) |
| 14 | Original: only DNb08 shared; sweep: 14 (R4) | DNb08; 14 | H: original_K0_B1lo10_x_B2, sweep_dx1_x_ms types_in_both | DNb08 in every set; 14 without DNg100, 15 with | misdescribed, P8 (14) |
| 15 | Validity rule (Abs, R3, R4) | 11 of 16, bar 12; 8 of 8 | C.B4_validity; PREREG_v6 B4 | 11/16 invalid; 8/8 (bar 6) | OK (15) |
| 16 | DNg100 in BANC (R4) | 0.64; each copy a hit | C5.DNg100, C5.DNg100_single_members | 0.641; 13/16 each | OK (16) |
| 17 | DNb08 in BANC (R4) | whole type 0.00; 0 of 16 each | C5.DNb08 | tuned 0.00, sweep 0.246; copies 0/16 (tuned) | misdescribed, P4 (17) |
| 18 | Hits in all three under the sweep (R4) | 3: DNg100, DNa13, DNxl092 | C5.driver_table (tuned hits only) | 4: also DNxl134 (0.561 / 0.974 / 0.764) | **wrong, P1** (18) |
| 19 | Fig. 4: hits in at least one animal | 29 of 182 | same | 71 of 182 | **wrong, P1** (18) |
| 20 | Our MaleCNS model vs the authors (Abs, R4, Fig. 6) | 15 of 16, 0.86, theirs 0.80; four copies; 2-s runs; DNg100 0.98, theirs 0.985 | V.V2.{authors_configuration_sentence, table, cells_meeting_bar, authors_reported}; V.V1 | 15/16, 0.863, 0.803; 4 positions; 0.9849, 0.985 | OK; P12 (19) |
| 21 | Previous stability test (R5) | p 0.11; two graded versions positive | S: tests.b1r_drivers.{primary_stability, sensitivity_ii, sensitivity_iii}.p | 0.114; 0.035, 0.033 | OK (20) |
| 22 | Stability predicts BANC (Abs, R5, Fig. 5, Disc.) | 12 types; 16 copies; 0.57; p 0.029; partial 0.56; 10 of 12 below 0.07; two above 0.1 | C8.primary, .partial_given_B1r_score; S.n_copies; C5.driver_table | 12; 16; 0.571; 0.0286; 0.558; 10 (max 0.067); 0.976, 0.246 | OK (21) |
| 23 | Pooling (R5) | 181; 0.20 (0.08 to 0.32); 0.02 (-0.03 to 0.07); not shown | C6 | 0.199 (0.084-0.322); 0.020 (-0.034 to 0.074) | OK (22) |
| 24 | How many connectomes (R5) | 0.39; about 7 (4.3 to 9.7); 0.8 | C7; PREREG_v6 C7 | 0.389; 6.27, rounded 7; 4.29-9.72; 0.8 | OK (23) |
| 25 | Second literature test (R6) | 27; 0.633 (0.533-0.724), p 0.008; 0 of 27; eight baselines; 0.638; -0.006 (-0.172 to 0.166) | `results/run3/primary.json`: H-M.mean_pr, ci, p, H-M.top1, H-S, vs_best_H-S | 0.6327 (0.5331-0.7244), 0.0076; 0; 8; 0.6384; -0.0057 (-0.1724, 0.1662) | OK (24) |
| 26 | Above seven, clearly above four (R6) | seven; four; 0.13 to 0.21 | `thirdfly_v1/POSTHOC_exam2_pairs.json`: baselines | 7; 4; 0.135-0.213 | **wrong, P11** (25) |
| 27 | Inter-source kappa (R6) | 0.24 | `labels_h1/agreement.json`: between_sources[...].kappa (33 cells) | 0.238 | OK; unsourced in CLAIMS (24) |
| 28 | First literature test (R6, S4) | 0.577 (0.417-0.724); 0.669 | `results/run2/P.json`: primary.result.{auroc, boot, baselines_auroc.S2_twohop_signed} | 0.5771 (0.4171-0.7243); 0.6686 | OK (26) |
| 29 | Its labels confounded (R6, S4) | yes labels almost all atlas; 21 atlas types all yes | ER census_39.atlas_only.n; `labels_audit_v1/comparison_with_exam1.csv` | 21 of 25 yes are atlas-only; no "no" is | OK; field incomplete (27) |
| 30 | Twelve experiments (R7) | 12; three readings | `forward_v2/SHORTLIST.csv`, DECISION_RULE.json | 12 rows, each with an available line | OK; timing P13 (28) |
| 31 | Our MANC screen shares 10 of 11 (Disc.) | 10 of 11 | `pertype_v1/B1r.csv`, A1.csv, score >= 0.5 | 10 of 11 (not DNg54) | OK (29) |
| 32 | Sweep hits in MaleCNS (Lim.) | 60 of 182 | C4["MaleCNS sweep list"].mcns_banc_high_noDNg100 n_x | 60 of 182 (not Fig. 4's 182) | OK; set P5 (30) |
| 33 | Networks; gate; sides (Methods, S2) | 4,604/144; 4,310/130; 4,963/139; 0.994 (0.984); 0.000, 0.028 (0.014, 0.035); 63 % | PREREG_v4 G2; LOG L177; `gates_v6/BANC_GATE.json`; C.B2_sides.agreement | same; 0.9941; 0.000; 0.0277; 0.627 of 840 | OK (31-33) |
| 34 | Rulebook audit (Methods) | 14 findings | `reviews_v6/PREREG_AUDIT_RESOLUTION_v6.md`; LOG L179-L180 | 14 (re-check added N1-N6) | OK (34) |
| 35 | Label audit (Methods) | 39; 18; 3 (7.7 %); six errata incl. DNg100 | ER census_39.all, errata_exposed; P.json exposed_set.n_types | 3/39; 6; 18 | OK; "18" not in cited file (35) |
| 36 | Compute (Methods) | 100; 20 jobs; 240 of 240 | `gates_v6/TRUST_GATE_v6.json`, DETERMINISM_v6_stage1/2; PREREG_v6 X3 | 100/100; 100 + 140 (12 parts x 20) | numbers OK; platform P10 (36) |
| 37 | Procedure (Methods) | 128; 10 runs; 10-1,500; 200 above 100 Hz; 1 MN; 1 s; 16; 0.5; 19 currents 4-2,048; 8; x 0.03; 10,000; 95 % | PREREG_v6 B1, G1, G4; PREREG_v2 P1; LOG L177 (b 0.03) | all match | OK; unsourced (none) |
| 38 | The original paper (Intro, Disc.) | 933; 128; four; three of four; quotes | `research/literature/pugliese_walking_cpg_detailed_notes.md` §1 l.49, §4.2, §8.1, §9, §10.1, §13 item 7 | all match (left/right sentence v1 only) | OK (37) |
| 39 | Use of AI | Opus 5.5; Sonnet | LOG L36, L153-L154, L25 | match | OK; L25 not cited (39) |
| 40 | Abstract length | at most 220 | PREPRINT_v1.md | 221 tokens (220 without "=") | at the limit |
| 41 | S2 (16 values: 4,963 ... 232; 181) | as printed | LOG L177; BANC_GATE.json; C.B2_sides; TS | all match | OK; "181" P15 |
| 42 | S3 (11 rows) | as printed | identical to locked `thirdfly_v1/C_tables.md`; values traced to C | match | OK |
| 43 | S4 | 39 (25/14); 0.577; 0.669; 21; 3 (7.7 %), 0, 3 of 18; 10 %; six; 0.559; 0.713 | P.json; ER; RESCORE_exploratory.json; PREREG_v5 L6 | match | OK |
| 44 | S5 (128 values; 0.41 / 0.47 / 0.40 / 0.33); S6 (160 values; 0.985); S7; S8 | as printed | H: pairs.*["high\|without_DNg100"]; V.V2.table, V.V1; C.F; gates_v6 (script comparison) | all match | OK |

**Count.** About 190 printed values in the abstract, main text, captions and Methods (rows 1-38) and about 550 in the supplement.
**Problems:** wrong 3 values in 2 problems (P1, two claims; P11); misdescribed 12 (P2-P10, P12-P14) plus minor P15; unsourced 7 groups
without a CLAIMS row and 7 rows with a missing or wrong field (P16); references 2 wrong titles, 1 overstated citation, 1 style point.

## 2. Problems in detail

**P1 (wrong; the most important).** R4: "Three types are hits in all three animals under the sweep: DNg100, DNa13 and DNxl092 (Fig. 4)".
Fig. 4 caption: "the 29 types among the 182 ... that score at least 0.5 in at least one animal". Fig. 4 (`paper_figures_v6.py` fig4)
and CLAIMS row 18 read `C5.driver_table`, which (PREREG v6 C5) lists only hits of B1r, A1, B2r or the *tuned* BANC screen: sweep-only
hits are missing. From the stored sweep logs (`screens6.sweep_manc/sweep_mcns/banc_sweep`; scores equal the table's to 1e-16), **4**
of the 182 types are sweep hits in all three animals, the fourth being DNxl134 (0.561 / 0.974 / 0.764), and **71** are hits in at least
one; Fig. 4 lacks 42 (e.g. DNxl134, DNb05, DNb06, DNg75, DNg97, DNp56). Locked files alone show it too: DNxl134 is in the 0.5-cut
`types_in_both` of H sweep_dx1_x_ms (high) and of both C4 sweep lists, and in TS three_animal. With medium matches, DNfl031 and DNxl102
also hit in all three. Fix: redraw Fig. 4 from the sweep screens, name four types, re-source row 18.

**P2 (abstract).** "At the authors' threshold, the first two animals' hit lists overlap at chance (post hoc)" holds under the
current-setting (and original) procedure. Under the sweep, which every third-animal test uses, 14 of MANC's 18 hits recur (6.0 expected,
p < 0.001). The abstract then contrasts this with the third animal's sweep result, which compares two procedures. Add "under our
current-setting procedure", as R3 does.

**P3.** R2's "-0.21 (-0.37 to -0.05)" is the difference in cross-half correlation rho_x (0.422 - 0.630; LOG L186: "difference in
rho_x"). It follows the ratios 0.78 and 0.58, whose difference is -0.19. Name the statistic.

**P4.** R4: DNb08's "whole type (0.00)" is the current-setting score. Under the primary sweep it scores 0.25, which Fig. 5 plots. Its
0-of-16 single-copy runs also used the current-setting procedure. It is still not a hit, but the text should give 0.25 too.

**P5 (sets).** R3 announces the 181 three-animal types. But 5 of 17 and 1 of 6 are on the 202 MANC-BANC types, and 12 of 60 on the 182
MaleCNS-BANC types (high confidence, without DNg100), and R3 does not say so. "182" names two sets: three_animal with DNg100 (Fig. 4, in
which MaleCNS has 61 sweep hits) and mcns_banc_high_noDNg100 (Limitations, "60 of 182").

**P6.** R3 wiring: 0.61 and 0.63 are BANC with a 5-synapse floor imposed (C3_wiring.caveat_rests_on); without it they are 0.63 and 0.63.
The paper has just said BANC has no threshold, so it should state the floor. The 0.71 is the lowest side-specific comparison (MANC-R vs
MaleCNS-L, 245 types), not a value of the 181-type statistic (0.82).

**P7.** "1 of its 6 hits" (R3), "(1 of 6)" (abstract), "the authors' own six high-confidence hits" (Discussion): the authors' list has 11
hits (Discussion: "10 of their 11"). Six have a high-confidence BANC match once DNg100 is left out. Write "6 of its 11 hits that have a
high-confidence BANC match".

**P8.** R4's "Under the current sweep, 14 types are" excludes DNg100. The paragraph's point is independence from the DNg100 calibration,
so write 15, or "14 besides DNg100". The sweep's in-bounds rule needs one active motor neuron (G4). A run with no active motor neuron
cannot raise a maximum over fixed currents, so "does not depend on this calibration" holds.

**P9 (status wording).**
- (a) Abstract "left unexamined until our rules were frozen", R1 "which we did not examine": before the freeze BANC's annotations were
  read, type matches and set sizes computed and the DNg100 gate run (PREREG v6 Part Q 4), as the Methods say.
- (b) Introduction "Every analysis ... before the data" and Methods "Each analysis was written into a rulebook before the data" do not
  fit the post hoc analyses (Part H; POSTHOC_exam2_pairs). Write "every pre-registered analysis".
- (c) Limitations "The pre-registered tests are those on the third animal and our MaleCNS model's check" omits the earlier ones reported
  (A0, one-sided screens, MANC count noise, both literature tests, the run-5 stability test). Add "in this analysis".

**P10.** The Methods say "Simulations ran on GitHub Actions". But MANC's one-sided screen (seeds 4-15; LOG L116) and the MANC sweep
`dx-1-run4` (used by every primary C3-C8 test; PREREG v6 Part Q 6) ran on Modal under a Modal trust gate (L111). Write "this analysis's
simulations".

**P11 (wrong, rounding).** R6: "differences 0.13 to 0.21". The four clearly-above differences are 0.1354 (H-S-k2-unsigned), 0.157, 0.172
and 0.213, so 0.14 to 0.21. The 0.127 belongs to H-S-k3-signed, whose interval includes zero.

**P12.** R4: "mean 0.98; theirs 0.985". Ours is 0.9849, which is 0.985 at three decimals (S6 prints 0.985). The mixed precision suggests a
difference that is not there.

**P13.** R7: "Before any of these tests, we listed experiments". `forward_v2/README.md` says the list was made after both literature
tests were unblinded and after the replication pattern was seen. It predates only the third-animal tests.

**P14.** Fig. 2 puts MANC's count-noise bar (0.48) beside MANC's one-sided bar (0.59). The test compares it with 0.47 (paired design,
8 seeds, 261 types), which the figure omits. The caption should say so.

**P15 (minor).** Methods: the ratio divides by the mean of the two self-agreements (G1), not "each". S2 "181 ... (the set of the
left-right test)": the word set is 180. R6 kappa: over 33 hemilineage x phenotype cells; Truman authored both [13] and [14], so "two
source papers", not laboratories. The hand-check placeholder in "Use of AI" is open.

**P16 (CLAIMS).** Every cited file and field exists and holds its value, except: row 12 cites Fig. 3, which has no curve for the
authors' list; row 18 (P1); row 24 has no kappa field (`labels_h1/agreement.json` between_sources[...].kappa), and "0 of 27" is
H-M.top1, 0.638 H-S["H-S-k2-signed"].mean_pr; row 27 gives n = 21 but not the labels (`comparison_with_exam1.csv`); row 35's "18" is
`results/run2/P.json` exposed_set.n_types; row 37 omits notes §1 (the "because every DN" quote); row 39 omits LOG L25 (Sonnet). No row
covers the Methods procedure parameters, 10,000 resamples, 95 %, MANC's 5-synapse floor (PREREG_v4 B4.2), "20 jobs" (PREREG_v6 X3),
"two males, one female" or the 20 hand-check labels; all are correct.

## 3. References

Checked against `paper/REFERENCES_CHECK_v1.json`; re-fetched today from Crossref (1, 2, 3, 14, 15), arXiv (8, 9) and DataCite (18).

| # | Verdict | Problem |
|---|---|---|
| 1 | OK | Nature, online 28 Oct 2026, no volume yet. Content cited to [1] alone is unverifiable here (no abstract; the notes predate it). |
| 2 | OK | Posted 12 Sep 2025; v2 date from the notes (§13-14). Quotes match v2 (§1 l.49, §4.2) and v1 (§13 item 7). |
| 3 | OK | The DOI's Crossref record is the reviewed preprint (23 May 2024), without a volume. |
| 4 | OK | Cell 189(18), 5504-5526.e15. |
| 5 | OK | Nature 656, 957-970. "Female" is not in the abstract; the notes agree. |
| 6, 7 | OK | [7]'s citing sentence fits its abstract. |
| 8 | OK | arXiv 2609.38665v1 (29 Sep 2026). "Rhythm is generic, coordination of opposing muscles is not" matches the abstract. |
| 9 | OK | arXiv 2610.29205 (now v2). "Rival" is the title's word; the abstract says "more than halfway to the smallest between-fly difference". |
| 10 | OK | "Testable structural prior than as a blueprint" is the abstract's wording. |
| 11, 12, 13 | OK | [13]: dTRPA1 activation phenotypes, as cited. |
| 14 | **Title wrong** | Ends "... to behavior in the Drosophila ventral nerve cord", not "in Drosophila". |
| 15 | **Title wrong** | Ends "... in the Drosophila Male Adult Nerve Cord connectome" ("connectome" missing). It is also not a label source: the ledger used its summary of Harris 2015 only as a cross-check (PREREG v3 T5). "[13-15]" next to "two source laboratories" overstates its role. |
| 16, 17, 18 | OK | [17]: the abstract says "freely behaving", so "freely walking intact flies" is fair. [18]: DataCite lists 7 creators (Zenodo, 2026). |
| all | Style | Not numbered in order of first citation (the text cites [3], [6], [4], [5], [7], then [1,2]). |
