# Post-lock review R: report accuracy and completeness (PHASE3_REPORT.md draft)

Reviewer: R (goal4 section 70). Scope: reporting, statistics and claims only. Nothing here proposes changing or tuning the locked
method. Every number was re-derived with `uv run --no-sync python` (1 thread) from the files named. Scratch scripts are in `.tmp/`.
"Draft L<n>" is a line of PHASE3_REPORT.md.

## Summary verdict

**Not acceptable as written: 2 blockers and 11 major issues.** Most numbers trace exactly to the result files: the FINAL profiles,
verdict counts, the Level C verdict table, Holm families, sharing, reproducibility, counterexamples, ablations, calibration, the
hidden-data checks and the lifting table (see "What I re-derived and found correct" below). The headline conclusion (NOT
SUPPORTED on the real circuits; partially supported on synthetic systems) survives, and so does the refusal to claim
interventional sufficiency. Three problems remain:

- **One headline scientific statement is false.** The claim that "a PCA latent of the same dimension predicts even better, on 9 of
  10 systems" comes from a horizon mismatch in self-audit check Q16. At matched horizons PCA-k is better on only 1-3 of 10 systems.
- **The Modal total double-counts three runs.** It is about $40 too high.
- **Negative or qualifying evidence is omitted or softened**, and the acceptance checklist marks criteria "met" that the self-audit
  marks fail:
  - the method's own abstentions on 8 of 10 real systems;
  - abstention on all kick / pulse held-out pairs, and state-independent C;
  - the OOD rows, where the method is worse than the input-only control;
  - the significance of the "better / worse than the comparator" statements;
  - vacuous or synthetic-only self-audit passes;
  - 18 deselected root tests;
  - missing compute items;
  - post-lock review results, "biggest limitation" and Phase 3 status.

## BLOCKERS

### B1. "A PCA latent of the same dimension predicts even better, on 9 of 10 systems" is false (a horizon-mismatch artefact)

- **Where:**
  - Summary, draft L30;
  - section 21 "Q16 ... passes on its synthetic criterion but not on the real systems", L991-998 (incl. "full networks: 0.018 vs
    0.024, 0.24 vs 0.51, 0.004 vs 0.006"; "adds no predictive value over PCA on the real circuits");
  - section 23, L1028.
- **Evidence:** `scripts/self_audit.py` q16 (L934-937) takes `key = next(k for k in pa if k.startswith("A_nmse_h"))`, which is the
  first key, `A_nmse_h10ms`. So it reads the PCA-k reference at the **10 ms** horizon. It then compares that with the method's
  verdict `A`, which is the **250 ms** horizon (`level_c_results.json` `systems.<sid>.brainir_state_v1.verdict.A` = `res.A_B.A_nmse_h250ms.mean`,
  e.g. net1 full 0.024420 in both). SELF_AUDIT.json Q16 `A_pca_k` for net1 full is 0.018305. That value equals
  `references.pca_k.A_B.A_nmse_h10ms.mean`, not the h250 value (0.0438).
- **Re-derived at matched horizons** (`systems.<sid>.brainir_state_v1.references.pca_k.A_B` vs `res.A_B`). The number of systems on
  which PCA-k beats the locked method:

  | horizon | 10 ms | 50 ms | 100 ms | 250 ms (the verdict's A) | 500 ms |
  |---|---|---|---|---|---|
  | systems (of 10) | 1 | 2 | 2 | 3 | 1 |

  - Full networks at 250 ms (method vs PCA-k):

    | network | method | PCA-k | better |
    |---|---|---|---|
    | net1 | 0.0244 | 0.0438 | method |
    | net2 | 0.514 | 0.445 | PCA |
    | net3 | 0.0055 | 0.0069 | method |

  - At 100 ms (the robustness table's horizon): net1 0.024 vs 0.041; net2 0.528 vs 0.353; net3 0.0054 vs 0.0067.
  - At 250 ms the three systems where PCA-k wins are net2 full, net2 mech a (0.229 vs 0.201) and net2 mech b (0.209 vs 0.195).
- **Correction:**
  - Delete the "9 of 10" statements and "adds no predictive value over PCA on the real circuits" (L30, L991-998, L1028).
  - Replace them with: "At the verdict's 250 ms horizon, a PCA latent with the method's k predicts the held-out readout better than
    the locked method on 3 of 10 real systems (net2 full 0.445 vs 0.514, and two net2 mechanisms) and worse on 7 (e.g. net1 full
    0.044 vs 0.024; net3 full 0.0069 vs 0.0055). The comparison is descriptive (no paired CI). The self-audit's real-system Q16
    evidence compared PCA at 10 ms with the method at 250 ms and is void."
  - Disclose the defect in self_audit.py Q16's real-system evidence. Its synthetic pass criterion is unaffected: it uses
    `key_a(SYNTH_CFG)` for both.
  - Note: this error made the draft MORE negative than the evidence. It is still a false statement of a result.

### B2. The Modal cost total ($312 / 23,704 calls / 481 container-hours) double-counts rounds 1, 2 and round-3 attempt 1

- **Where:** section 22, L1012 ("about **$312** over 23704 container calls and 481 container-hours"), and criterion 41.
- **Evidence:** `results/COMPUTE_SUMMARY.json` `rows` holds both of these for the same three runs:
  - the hand-kept ledger rows "Level B round 1" (727 calls, 76,727 s, $11.26), "Level B round 2" (2,276, 179,718 s, $26.36) and
    "Level B round 3 attempt 1" (215, 13,972 s, $2.05);
  - the per-part records `tournament:r1_*` (sum 727 calls, 76,727 s, $11.26), `tournament:r2_*` (2,276, 179,718 s, $26.36) and
    `tournament:r3_brainir_state_v1` (215, 13,972 s, $2.05). These are identical.

  `scripts/compute_summary.py` `ledger_rows` de-duplicates only when a record's directory name ("r1_cb") appears in the ledger text,
  or through `LEDGER_COVERED`, which lists only the dev smoke run. The draft's own "Level B rounds 1-3 (about $65)"
  (11.26 + 26.36 + 2.05 + 25.72 = 65.39) counts them once, so it is inconsistent with the total.
- **Correction:** "about **$272** (271.90) over 20,486 container calls and 406 (405.95) container-hours". Subtract $39.67, 3,218
  calls and 270,417 container-s. Regenerate COMPUTE_SUMMARY after adding the three ledger rows to `LEDGER_COVERED`, or state the
  correction in the report.

## MAJOR issues

### M1. The method's own abstention on 8 of 10 real systems is not reported, and one claim converts an abstention into a sufficiency claim

- **Evidence:** `level_c_results.json` `systems.<sid>.brainir_state_v1.verdict.abstention.no_compact_state` is True on 8 of 10
  systems, all except net1 full and net3 full.
  - net2 full: "latent explains too little beyond the input (val 0.480 > 0.5 x input floor 0.843)";
  - the mechanisms: "selected k=2..5 exceeds N/5 = 0.6-1.2". The mechanisms observe only 3-6 neurons (`n_observed`), so k = 2-5 is
    no compression there.
  - PROTOCOL.md L391: "A method's own abstention is recorded as such and is never converted into a verdict it did not claim."
- **Where:**
  - Summary L28-29 and section 23 L1026-1027 / L1043-1046 ("a 2-3 dimensional state representation ... was sufficient to predict
    the held-out readout of the three full networks");
  - the section 14 table has no abstention column.
- **Correction:**
  - Add an abstention column to the section 14 table and a family L (real) line: "the locked method declared 'no compact state' on
    8 of 10 real systems (including net2 full); it claimed a compact state only on net1 full and net3 full".
  - Qualify the permitted claim: "... sufficient to predict the held-out readout of net1 full and net3 full (and, by the evaluator's
    measurement, net2 full, where the method itself abstained) better than input-only and persistence controls".
  - State the observed-neuron counts of the mechanisms (3-6).

### M2. Held-out C on the full networks rests on silencing only: all kick and pulse pairs were abstained on, and C does not depend on the state

- **Evidence:** `res.C_heldout.n_abstained_unsupported` = 60 of 120 pairs on each full network. `res.C_per_family`:
  - H_kick_A/B and H_pulse_A/B: 30/30 abstained each, on all three networks;
  - C is computed only from H_silence1_A/B and H_group_silence.
  - `verdict.state_mediated` = False on all three. C with the pre-event state scrambled is:

    | network | C | C (state scrambled) | CI of C - C_scrambled |
    |---|---|---|---|
    | net1 | 1.268 | 1.271 | [-0.043, 0.039] |
    | net2 | 0.956 | 0.954 | [-0.002, 0.005] |
    | net3 | 1.036 | 1.036 | [-0.004, 0.003] |

  - n_eff = 4.1, 1.4 and 3.9, with 45-49 null pairs of 60.
  - Every primary C comparison carries `claim`: "not an interventional claim: ... non-inferiority to the baseline on C carries no
    interventional content".
- **Where:**
  - Summary L31-34 ("Held-out C is 1.27, 0.96 and 1.04"; "non-inferior on 5 of 13 ..., significantly better on 2");
  - section 14 L706-716.
- **Correction:**
  - After the C values, add: "computed on the 60 silencing pairs only; the method abstained on all 60 kick and pulse pairs of every
    full network, and its predicted effects do not depend on the latent state (C with scrambled z0 is identical; state_mediated =
    no)".
  - In the Summary, qualify the comparator result: "non-inferiority on C (net2, net3) carries no interventional content (the
    method's own C is not below 1)".

### M3. Robustness: under OOD input the compact model is worse than the input-only control; the draft omits this and some capped windows

- **Evidence:** `res.H_ood.<family>.A_nmse_h100ms` (method) vs `references.input_only.H_ood` (all values at 100 ms):

  | network | method, OOD stimulus | input-only, OOD stimulus | method, OOD weight noise | input-only, OOD weight noise |
  |---|---|---|---|---|
  | net1 | 1.82 | 0.78 (2.3x better) | 0.046 | 0.044 |
  | net2 | 3.52 | 5.74 | 1.25 | 1.24 |
  | net3 | 0.128 | 0.112 | 0.022 | 0.024 |

  On net2, 19 of 30 method windows hit the NMSE cap of 10 (`n_windows_capped`), so 3.52 is a lower bound.
- **Where:** section 17 L820-831 ("Weight noise ... tolerated about as well as, or better than, by the comparator"), and Summary L38.
- **Correction:**
  - Add the input-only row to the robustness table.
  - State: "out of distribution the compact latent adds nothing over the input-only control (weight noise: equal on all three
    networks; stimulus: worse on net1 and net3)", and "net2 OOD-stimulus values are capped on 19 of 30 windows (lower bounds)".

### M4. "Better / worse than the comparator" on the FINAL suite is stated without significance; only S1 and S6 differences are supported

- **Where:** Summary L24-25; section 8 L488-494; section 23 L1037-1038 ("worse on closure and abstention").
- **Evidence:**
  - SELF_AUDIT.json Q15, lin_dmdc_t, paired medians (method minus comparator) over the 46 compressible systems:

    | component | median | 95 % CI | significant |
    |---|---|---|---|
    | S1 | -0.30 | [-0.57, -0.07] | yes |
    | S2 | 0.001 | [-0.10, 0.09] | no |
    | S3 | 0.0004 | [-0.0012, 0.027] | no |
    | S4 | 0.0 | [-0.0006, 0.0] | no |
    | S5 | -0.0001 | [-0.0024, 0.0010] | no |

  - S6, my paired exact-k test on `final_b/*.json`: 14 systems exact only for v1 and 3 only for lin_dmdc_t; exact McNemar p = 0.013.
  - S7 is a profile difference: abstention recall 0.5 vs 1.0; false alarms 2 % vs 28 %; confident-wrong 52 % vs 33 %.
- **Correction:** "Paired over systems, it is significantly better on prediction (S1) and exact k (S6, McNemar p = 0.013). S2-S5 show
  no significant paired difference (the profile medians 0.031 vs 0.014 and 0.987 vs 0.991 are not significant). On abstention it
  abstains less often (recall 1/2 vs 2/2) with fewer false alarms (2 % vs 28 %) and more confident-wrong claims (52 % vs 33 %)."

### M5. Synthetic latent recovery is reported as a median only, which hides the failures

- **Where:** Summary L21 ("latent recovery K = 0.987"); section 23 L1036 ("the true latent up to an affine map (K = 0.987)").
- **Evidence:** `final_b/brainir_state_v1.json` `per_system.<s>.K`, min(r2_true_from_model_rff, r2_model_from_true_rff) over the
  46 compressible systems: median 0.987, mean 0.860; 13 of 46 systems are below 0.9 and 5 below 0.5 (lowest 0.12, 0.15, 0.16).
  The Level C primary K comparison is not non-inferior (Holm p = 0.30).
- **Correction:** "median K = 0.987 (mean 0.86; K < 0.5 on 5 of 46 systems)", and remove the unqualified "recovers the true latent"
  wording in section 23.

### M6. The acceptance checklist marks as "met" criteria whose self-audit checks FAIL (question 3)

- **Evidence:** SELF_AUDIT.json `criteria` of the failing checks:
  - I3 fails and supports criteria 9 and 10;
  - I8 fails and supports criteria 17, 47 and 48;
  - Q11 fails and supports 31 and 34;
  - Q12 fails and supports 29;
  - Q13 fails and supports 35.
- **Draft, section 15:**
  - criterion 3 lists I3 among its supporting evidence;
  - criterion 10 is "met";
  - criteria 17, 47 and 48 are "met", and criterion 47 cites I8 as supporting evidence although I8 FAILS;
  - criteria 29, 31 and 35 are "met";
  - criterion 34 is "met, method failed" (acceptable).
- **Also**, EVALUATION_LOG.md:
  - has no DONE rows for the four FINAL counterexample sweeps or for the ablations_final re-run;
  - has no rows at all for the two real public-draw sweeps (`counterexamples/real_public_*`), which used the Level C fits after
    Level C.
- **Correction:**
  - Add a "self-audit" column to the section 15 table. Mark criteria 3, 9, 10, 17, 47 and 48 "met; supporting check I3 / I8 fails as
    written (orchestrator note: artefact)". Mark 29, 31 and 35 "measured; the corresponding self-audit test FAILS (Q12 / Q11 / Q13)".
  - Add the missing DONE rows to the log, or state their absence under criterion 47.

### M7. Several self-audit passes are vacuous, synthetic-only while the real evidence contradicts them, or described wrongly (question 4)

- **Q9 (capacity)** passes because nothing is shared (note: "nothing to attribute to capacity"). The question was not tested. Report
  it as untestable (n/a), not among the "16 passes".
- **Q6 (closure)** passes on the synthetic fraction not closed (0.217). The real evidence in the same record is `real_closed` False
  on 7 of 10, which would FAIL the same threshold (> 0.5). Add "real: not closed on 7 of 10 (would fail the threshold)".
- **Q8** passes on the synthetic criterion only: 41 % of FINAL systems have held-out C no better than no effect, against a 50 %
  threshold. The draft (L987) describes it as "not collapsing ... relative to in-distribution ones", which is not the tested
  criterion. The real in-distribution CIs are not used, and the recorded real CIs are the 100 ms window, while the verdict uses
  250 ms. Replace with: "passes because 19 of 46 FINAL systems (41 %, threshold 50 %) have held-out C no better than no effect".
- **Q14** records `median: NaN`: `np.median` over ratios that include NaN for the 4 fully abstaining mechanisms, and `NaN > 3` is
  False. So the real criterion was not applied. Over the 6 finite ratios the median is 1.04, a pass. However 2 of the 6 exceed 3
  (net1 mech b 5.8, net2 mech b 6.7). Disclose this.
- **Q18** passes on "no compact claim". On review G's non-compressible trap G10, however, the locked method rated "partially
  supported" with k = 1 (draft L885), and on the FINAL control syn-6b76c3f5b6 it returned k = 3 without abstaining. Add both to the
  Q18 line.
- **Q19** passes on a pooled fraction of 0.17 over 116 system-runs from four sweeps (two of them on 48 synthetic systems, one with
  the post-event objective). The real public-draw effect sweep alone is 5 of 10 = 0.5, which meets the fail threshold (>= 0.5).
  State this.
- **Threshold fixing (question 4.3):** TH in `scripts/self_audit.py` equals SELF_AUDIT.json `thresholds` exactly. The room has no
  git history, so I cannot verify that they were fixed before the evidence; only the script's own comment asserts it. The draft's
  "thresholds fixed before that evidence existed" (L928) needs a pointer to the commit / tag that holds TH before the post-lock runs.
- **Also, the Q19 row** is a re-run (10:02:00Z) that replaced the full run's Q19; the replaced result is not in the room. The
  "FAILS AS WRITTEN" texts for I3, I8 and I11 are `orchestrator_note` fields, not check output. The draft's table (L934-942)
  presents them as the check's notes. Label them "orchestrator note".

### M8. Tests: "All old tests green: 534 passed, 1 skipped, 0 failed" omits 18 deselected tests

- **Evidence:** SELF_AUDIT.json I10 `root.summary`: "534 passed, 1 skipped, 18 deselected, 2 warnings".
- **Where:** criterion 42, L784.
- **Correction:** "534 passed, 1 skipped, 18 deselected (reason: ...), 0 failed". Say which tests were deselected and why, or
  re-run them. Criterion 42 is "all old tests remain green".

### M9. Compute reporting is incomplete against goal4 section 59, and the compute-for-gain trade-off is not reported (question 5)

- **Missing items:**
  - simulator calls: COMPUTE_SUMMARY has 476 clean-room trajectories and 36 refused or failed, `simulation_cache`; the draft gives
    none;
  - simulated biological seconds;
  - training samples and optimisation steps;
  - local CPU-hours (only wall-clock is given, e.g. the local hidden-draw sweep: 3,340 s on 6 workers);
  - Modal job ids. The draft gives none, and COMPUTE_SUMMARY has app ids for only 35 of 88 rows. There are none for the FINAL
    confirmation, Level C, the tournaments or the ablations; their modal_costs.json have no app_id.
- **The ~1,713 host-gate refusals of Level C** (`level_c/01/modal_costs.json` `refusals`) are not priced.
- **Compute vs gain:**
  - FINAL `fit_wall_s_total`: brainir_state_v1 24,088 s (median 190 s per fit), lin_dmdc_t 1,835 s (median 11 s). That is about
    13x the fit time.
  - The confirmation parts cost $5.75 vs $3.02.
  - The gains are S1 and S6 only, and the method ranks below the comparator on FINAL.
- **Correction:**
  - Add these items, or state "not recorded".
  - Add: "The locked method needs about 13x the comparator's fit time for significant gains on prediction and exact k only, and
    does not outrank it on the FINAL suite."

### M10. Required report / final-response items are missing (goal4 sections 84 and 91)

- **Post-lock reviews:**
  - Summary L44 says "the post-lock reviews are in section 18", and the section 18 table points to "section 18.1" (L878), which
    does not exist. I12 notes "post-lock reviews not yet present".
  - L878 also lists a post-lock reviewer "L", but only S, C, Y and R contracts exist.
  - Add section 18.1 with each review's blockers and majors and their resolution. Until then, change L44 to "post-lock reviews
    pending".
- **Phase 3 status (section 91):**
  - Not stated.
  - Criterion 26 is "partly" (no lift() and no rigorous reason documented). Under section 85 ("Do NOT declare Phase 3 complete
    until all ... are satisfied") the status must be stated as not complete, or a rigorous reason must be documented.
- **Biggest limitation (section 91):**
  - Section 17 lists 7 limitations but names none as the biggest.
  - Add one, e.g. "The latent state does not carry intervention effects: the method abstains on all kick / pulse interventions of
    the real full networks, and its silencing predictions do not depend on z."
- **Full-state vs compressed prediction on the real systems (section 91):**
  - Not reported (only S1 on FINAL).
  - From `verdict.A` / `A_full`, which are the 250 ms values: net1 0.0244 vs 0.0200; net2 0.514 vs 0.476; net3 0.0055 vs 0.0099.
    At 100 ms: 0.024 vs 0.007, 0.53 vs 0.12, 0.0054 vs 0.0015.
  - Report these, and note that the full-state reference is not an upper bound at 250 ms on net3.
- **Final Phase 3 tag (section 86):** not mentioned. State it, or state that it is pending.
- **Synthetic robustness (family H on FINAL):** section 17 reports only the real OOD families. Add the FINAL H results, or point to
  them.

### M11. Real leave-one-implementation-out results and the direction of the J transfer are misreported or omitted

- **I (within networks):**
  - Section 14 (L722-723) reports only "sharing rejected / untestable".
  - The LOIO adaptation on the real systems is worse than from-scratch fits in 4 of 4 computable cases (`I.net1.loio`: A +0.38,
    +0.017 (CI includes 0) and +9.8, with C +79, +0.23 and +30; `I.net3.loio`: A +0.12). The net2 LOIO fits all failed.
  - Q11 cites only the synthetic 0 of 3.
  - Add the real LOIO line.
- **J net1 + net3:**
  - The draft (L727) says adaptation "ties on A". That holds only with net1 held out (A +0.0024 [-0.0002, 0.0046]).
  - With net3 held out, adaptation is better on A: -0.178 [-0.345, -0.054] (`J.net1+net3.transfer[1]`).
  - Correct to "beats a fit from scratch on C when net1 is held out and on A when net3 is held out".

## Minor issues

1. **Hidden data on one platform.** L45 says "Hidden real data and Level C ran on one deterministic compute platform", and L623
   says "Level C and the hidden data ran only on gated hosts". The hidden-parameter-draw counterexample sweep simulated hidden draws
   locally on Windows (L805; EVALUATION_LOG 09:05-10:01Z), and Windows differs on 37 of 1,764 records. Add "except the
   pre-registered local hidden-draw counterexample sweep".
2. **Counterexample error range.** L530: "effect errors of 10^3 to 10^9". The per-system worst effect errors range from 12 to
   9.8 x 10^8 (`final_brainir_state_v1_effect/SUMMARY.json` `systems.*.worst`). Say "from 12 to 9.8 x 10^8 (median worst /
   random-median 2,357)".
3. **Real counterexamples in the Summary.** L39: "on 5 of 10 real systems" is the public-draw sweep; the hidden-draw sweep gives
   3 of 10. Name the sweep, or give both.
4. **Sign error in a dev ablation CI.** L543: `nn_dim_rule` dev CI "[0.30, 0.02]" should be "-0.15 [-0.30, -0.02]"
   (ablations_dev/SUMMARY.md).
5. **Benchmark lock counts.** L154: "BENCHMARK_LOCK.json (81 files, 24 dataset entries)". The current lock
   (results/benchmark/BENCHMARK_LOCK.json) has 97 files and 27 datasets (version 3, 2 re-locks). Say which version 81 / 24 refers to.
6. **Number of lifting models.** L768 / L899 say "7 baselines lift". On FINAL, 8 models lift: lin_dmdc, lin_dmdc_t, lin_falds,
   lin_falds_t, lin_pcadyn, lin_pcadyn_t, nn_aelin and nn_aelin_t. The table omits lin_falds_t, whose achieved-shift error is 1.02,
   so "misses by 31-89 %" should be "31-102 %". The invariance columns exclude 1-2 NaN ratios per model; say so.
7. **Mechanism C without CIs.** Section 14 table: mechanism C values are given without CIs, which suggests passes. Give net1 mech b
   0.91 [0.36, 2.69] and net2 mech b 0.79 [0.74, 1.13].
8. **Scope of limitation 7.** L863: "poor on the real mechanisms (2 of 10 systems agree)" mixes scopes. k also differs across seeds
   on net1 and net2 full ([2,2,2,3,2], [3,2,2,2,2]). Say "on 8 of 10 real systems, including two of the three full networks".
9. **Probe-accuracy ranges.** Section 17 (L832, full networks 0.33-0.58) and section 21 (L977, all systems 0.30-0.81) quote
   different ranges without naming the scope. Name the scope in both.
10. **Ledger times.** The COSTS_LEDGER time column is PDT (Level C "00:30-02:04" = 07:30-09:04 UTC), while the report uses UTC. Add
    the time zone where ledger times are quoted.
11. **Failures in the ablation table.** Section 10.1 does not mention the 3 evaluation failures of the `sharing_test` variant
    (ablations_final/SUMMARY.md, "0+3").
12. **Answer-bearing marking (question 6).** L3 is present and correct, but it names only "a Phase 4 clean development room". Make it
    general: "never copy it, or anything derived from it, into any later clean room (Phase 4 or any other clean development room)".

## What I re-derived and found correct

**FINAL confirmation** (`tournament/final_b/AGGREGATE_developer_facing.json`, `final_b/brainir_state_v1.json`):
- the ranking table, all profiles S1-S8, mean ranks (3.44 / 3.94 / 4.38 / ...) and P(rank 1) (0.37 / 0.17 / 0.25 / ...);
- the rank interval [1, 8] and the eligibility (4 ineligible);
- verdicts 17 + 2 / 12 / 15;
- conditions: predictive 32, interventional 24, closed 36, E-equivalent 34 of 40 testable, state-mediated 27, Markov 46/46;
- k exact 27 / under 3 / over 16;
- abstention recall 0.5, false alarms 2.2 %, confident-wrong 52 %;
- seeds: k agrees on 4 of 8, r2 0.69-1.00;
- sharing: groups untestable / rejected, pairs 3/3 rejected;
- fits 4 of 108 failed, evaluations 0 of 99.

**Round 3** (`r3v3/ROUND_DECISION.json`):
- P(rank 1) 0.519, rank interval [1, 5.05], mean ranks, comparator choice;
- 8 of 204 failures (`r3v3_brainir_state_v1`: 7 fits + 1 evaluation);
- cost $25.72 / 48.7 container-h.

**Rounds 1 and 2:** mean ranks and P(rank 1) match. Round-2 profiles match.

**Level C** (`level_c/01/level_c_results.json`):
- the per-system table:
  - k and verdicts for both methods (lin_dmdc_t k = 16, 3, 1, 64, 3, 4, 3, 64, 1, 3);
  - predictive, closed and microstate columns;
  - C 1.27 [1.03, 1.89], 0.96 [0.94, 1.02], 1.04 [1.01, 1.20], 0.91, 0.79, 0.39;
- Markov consistency: all systems;
- closure on 3 systems and microstate equivalence on 8;
- A - input-only: net3 -0.0067 [-0.0077, -0.0056], net2 -0.30 [-0.58, -0.11];
- Holm primary: 5 non-inferior (net2 C/D/E, net3 A/C). Secondary: better on net3 A and C; worse on net1 E, net2 A and net3 E;
- K: 0.0065 [-0.040, 0.054], Holm 0.296;
- J transfer: +4.92 A / +251 C;
- seeds: k agrees on 2 of 10, median min-R^2 on the full networks 0.991 / 0.993 / 0.693, mechanisms k 2-8;
- half-samples: k agrees on 4 of 10, r2 -1.16 to 0.93;
- probe accuracies 0.33-0.58 vs 0.96-0.98;
- robustness table values (100 ms) and ratios 75.8x / 25.7x;
- 163 fits / 128 evaluations (modal_costs), 8 fit failures, wall 5,647 s; cost $11.12 + $31.0 = $42.1.

**Counterexamples** (7 SUMMARY.json):
- every table entry: 47/48, 2,558, 2,357, 9; 48, 2,414, 1,048, 3; 39, 698, 31, 3; 41, 729, 23, 3; real 7, 430, 8.4e5, 5; 10, 564,
  3.6e7, 4; 7, 416, 1.7e5, 3;
- random-protocol medians 0.57 vs 0.70;
- Q19 fraction 20/116 = 0.172.

**Ablations** (FINAL and dev SUMMARY.md):
- event_calibration +0.30 [0.13, 0.47], compact 19 to 10; the dimension switches and their CIs; delays compact 19 to 15;
- dev +0.26 [0.10, 0.60], compact 8 to 3;
- wall 7,154 s, $27.83 / $23.96.

**Calibration** (`benchmark/calibration.json`, `tolerances.json`):
- the v3 taus and their CIs;
- true-latent verdicts 3 / 22 / 20; PCA-k partially supported on 6, random-k on 2;
- closure power 24 % (random) vs 80 % (true).

**Hidden-data checks:**
- 3,360 items / 1,920 restarts / 1.59 GB;
- 1,727 of 1,764 identical;
- 83 of 83 re-simulations identical;
- 13 of 20 ungated mismatches; 60 of 60 gated.

**Lifting** (FINAL `per_system.*.lift`): the medians and fractions of the table (NaN ratios excluded).

**Self-audit:**
- the counts 12 / 3 / 0 and 16 / 3 / 0 match SELF_AUDIT.json;
- all 19 questions have an executable check with recorded evidence (but see M7 for Q9, Q14 and Q16);
- the TH dict in the script equals the recorded thresholds.

**Compute:**
- the draft's $312 / 23,704 / 481 h match COMPUTE_SUMMARY.md, but see B2;
- the Level B $65, confirmation $54.81, ablations $24 / $28, counterexamples $11.27 and Level C $42 match.

**Could not trace in this room** (source files not copied): 7,542 clean-room files; the 7 regenerated candidates and 8/8 seeds;
METHODS_REVIEW statistics (110 entries, 324 sources); the 30 locked source files; the commit ids bce6dbf / 6c7c2cd; the root / phase3
test counts beyond I10's summary lines.
