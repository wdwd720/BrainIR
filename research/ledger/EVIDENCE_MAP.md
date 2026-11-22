# Evidence map for BRIEF.md (run 4)

One row per claim in the brief: the claim, the locked file and field that support it, the tag that locks it, and its main caveat.
Paths are relative to `research/ledger/`. "rel" = tag `ledger-reliability-v2` (`LOCK_reliability_v2.json`); "fwd" = tag
`ledger-forward-v1` (`LOCK_forward_v1.json`); "pre" = tag `ledger-prereg-v4` (`LOCK_prereg_v4.json`). In JSON paths, `P` stands for
`primary_homolog_consistent` (Part B files) or `primary` (Part C).

| # | claim in the brief | locked file : field | tag | main caveat |
|---|---|---|---|---|
| 1 | Every analysis, threshold and criterion was frozen before the data existed; timestamped in Bitcoin | `PREREG_v4.md`; `LOCK_prereg_v4.json`; `LOCK_prereg_v4.json.ots`, `PREREG_v4.md.ots` | pre | seven recorded amendments (`AMENDMENTS_v4.jsonl`): cut set, three code fixes, two cost settings, a timeout |
| 2 | GitHub and Modal reproduced 100 locked jobs exactly | `gates_v4/TRUST_GATE_v4.json` : `identical` = 100; `gates_v4/TRUST_GATE_v4_modal.json` : `identical` = 100 | rel | the Mac's numerics differ; it ran no prediction |
| 3 | Samples of every campaign were re-run and matched digit for digit | `gates_v4/DETERMINISM_stage1.json` ... `stage4.json` : `verdict` = identical (stage 5, post-lock: `DETERMINISM_stage5.json`) | rel | 20 jobs per campaign |
| 4 | No experimental label shaped any analysis | `PREREG_v4.md` hard limits 2-4; `LOG.md` L104-L150 | pre | the exam labels were used once, for the forward ledger's probability fit (stated there) |
| 5 | Authors' own scores: left vs right at 0.63 of the ceiling (0.53-0.72) | `reliability_v2/A0.json` : `A0.primary_one_member_each_side.primary.ratio`, `.bootstrap.interval.ratio` | rel | their screen reads out both front legs together |
| 6 | About one driver in seven or eight is a driver on both sides | `reliability_v2/A0.json` : `A0.primary_one_member_each_side.secondary.replication.full` (a_to_b 1/7, b_to_a 1/8) | rel | few drivers (7 and 8) |
| 7 | Our simulation: left vs right 0.59 (MANC) and 0.64 (MaleCNS) of the ceiling | `reliability_v2/A.json` : `six_agreements_primary_homolog_consistent["MANC-L vs MANC-R"].primary.ratio`, `["MaleCNS-L vs MaleCNS-R"]` | rel | one-sided stimulation is our procedure (claim 5 shows the gap without it) |
| 8 | Same side in the two flies 0.32-0.41 | `reliability_v2/A.json` : `six_agreements_primary_homolog_consistent["MANC-L vs MaleCNS-L"]`, `["MANC-R vs MaleCNS-R"]` `.primary.ratio` | rel | 215 types shared by both flies |
| 9 | Wiring summaries agree at 0.71-0.98 | `reliability_v2/WIRING_A4.json` : `summaries_S1_S7_full_spearman[pair][S1..S7].spearman` | rel | summaries; single connections differ (claim 15) |
| 10 | Two Poisson copies of the MANC network agree at 0.40, almost as poorly as left and right (0.37); no parameter fitted; over all six copy pairings noise reproduces about 86 % of the gap | `reliability_v2/NOISE.json` : `P.poisson.copy_vs_copy.primary.rho_x`; `P.observed_left_right_paired_design.primary.rho_x`; `P.poisson.reproduces_left_right` = true | rel | the pre-registered pair is a low draw: the six-pair figure (0.46, about 86 %) is post hoc, from `reviews_v4/ADVERSARIAL_REVIEW_v4.md` (unlocked); sufficiency, not identity; MANC only |
| 11 | MaleCNS is published already floored, so count noise is MANC only | `PREREG_v4.md` B4; `reliability_v2/NOISE.json` : `marking` | rel | |
| 12 | The tuner explains at most a third (MaleCNS 0.36; MANC 0.17, not distinguishable from 0) | `reliability_v2/B1_MaleCNS.json`, `B1_MANC.json` : `P.procedure_share_of_gap.closure`, `.interval` | rel | 8 seeds; wide intervals |
| 13 | The sides disagree at every fixed current | `reliability_v2/B1_MANC.json`, `B1_MaleCNS.json` : `P.matched_current[current].words` (= a real gap; the five lowest MaleCNS currents not judged) | rel | few runs in bounds at low currents |
| 14 | Own outputs close 0.23 of the MANC gap, downstream network 0.34; mirroring both closes all of it | `reliability_v2/B2_MANC.json` : `P.H_own.closure.closure`, `P.H_rest.closure.closure`; `sanity.ii_full_transplant` | rel | MaleCNS 0.17 / 0.21, both intervals include 0 |
| 15 | About half of the connections between matched neurons exist on one side only, most with 1-4 synapses on the other side | `reliability_v2/WIRING_A4.json` : `single_connections.MANC.share_one_side_only` (0.51), `.share_one_sided_only_because_of_floor` (0.68) | rel | MaleCNS has no pre-floor counts (52 % one-sided) |
| 16 | One-sided connections close 0.29, partnerless neurons 0.25; weights, size, sign little alone | `reliability_v2/B3_MANC.json` : `P.A2.closure.closure`, `P.A3.closure.closure`, `P.A1`, `P.A4`, `P.A5` | rel | MANC only; classes interact (sum 0.61) |
| 17 | No fix restored reproducibility; with the control working the flies agree at 0.31-0.39 of the ceiling | `reliability_v2/C.json` : `passing` = []; `P[fix].cross_fly.ratio`; `P[fix].passes` | rel | strict bar (0.8); "few rewired drivers" set on whole-type controls |
| 18 | Two fixes broke the DNg100 control | `gates_v4/C_GAINS.json` : `fixes["6"].verdict`, `fixes["8"].verdict` = fails | rel | gains tried on DNg100 only |
| 19 | What this work does not show | statement of scope (`RESULTS_3.md` section 8) | | |
| 20 | Forward ledger: 63 types, two sources, no third because no fix passed | `forward/README.md`; `forward/LEDGER.csv`; `forward/SOURCES_NOTE.md` | fwd | |
| 21 | Probabilities fitted to the earlier exam's labels; weak: Brier 0.248 (model), 0.239 (counting), 0.242 (base rate) | `forward/CALIBRATION.json` : `sources.authors_model.brier_loo`, `sources.two_step_count.brier_loo`, `.brier_base_rate_loo` | fwd | 21 of 25 "yes" labels rest on one atlas |
| 22 | Made after the exams were unblinded, before the experiments they predict | `forward/README.md` (honesty line) | fwd | |
| 23 | The 15 decisive experiments, their probabilities and lines | `forward/DECISIVE.csv` : `p_authors_model`, `p_two_step_count`, `lines` | fwd | the sources differ by 0.05-0.28 only |
| 24 | Which lines are listed as available | `forward/AVAILABILITY.csv` : `listed_available`, `url`, `date_checked`; method in `forward/AVAILABILITY_NOTE.md` | fwd | ten FlyBank-only "yes" rows are the weakest |
| 25 | Each source will be scored by its Brier score against a base-rate guesser | `forward/README.md` (scoring rule, E7) | fwd | |
| 26 | The figure | `results/run4/fig_agreement.json` : `rows` (from `WIRING_A4.json` and `C.json`) | rel | primary types, seeds 0-7 |
