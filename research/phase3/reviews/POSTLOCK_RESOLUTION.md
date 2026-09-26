# Resolution of the post-lock reviews S, C, Y, R and L, verified by review V (ANSWER-BEARING)

Scope: reporting, statistics, claims and process only. **No finding led to a method change, and none could**: the method stays locked
(`method_lock_p3.py --check` passes). All numbers below were re-derived by `scripts/p3/postlock_numbers.py`
(`research/phase3/reviews/POSTLOCK_NUMBERS.json`) from the stored result files, not copied from the reviews. Section numbers refer
to the final `PHASE3_REPORT.md`.

## Where a reviewer's own number did not reproduce (not adopted)

| review | claim | re-derived | report |
|---|---|---|---|
| C, B1 | "at 10 ms PCA-k is better on 9 of 10" | at 10 ms PCA-k is better by point estimate on 1 of 10, significantly on 0 (C repeated the horizon mismatch) | section 14 uses the matched-horizon counts |
| C, minor 3 | "6 of the 8 microstate-equivalent systems have k >= N_observed" | k >= N_observed only on net2 mechanism c (k 5, N 3); on the mechanisms k is 50-167 % of N_observed | section 14 |
| Y, M4 | "k = N = 3 on net2 mechanism a" | k = 2 for N = 3 | section 14 |
| Y, M3 | "3 of the 8 G systems change k across seeds" | 4 of 8 | section 8 |
| R, M7 | "Q14 median over the 6 finite ratios 1.04" | 1.12 (Y's value) | section 21 |
| C, M9 | "no abstention on the non-compressible G10" | the locked method declared no compact state on G10 (`no_compact_state = true`, abstention recall 1 of 1), with verdict "partially supported" and k = 1. The first correction adopted C's sentence; verification review V found it false | summary; section 18 |
| S, B1 vs C / R, B1 | "2 of 10 significantly" vs "3 of 10" | both true: 3 by point estimate, 2 significant (paired CIs), method significantly better on 6 | section 14 |

Wrongly rejected at first: Y m2, "the mean-based CI of nn_dim_rule S3 excludes 0". Y is right: the stored ablation summary gives
-0.031 [-0.066, -0.0013]. The first version of `postlock_numbers.py` computed S3 from the point estimate of the D micro-gain instead of
the pre-registered max(0, upper CI); verification review V found the error, and the script and section 10.1 are corrected.

## Blockers

| id | finding | resolution |
|---|---|---|
| S B1, C B1, R B1 | "PCA-k predicts better on 9 of 10" came from self-audit Q16 comparing PCA at 10 ms with the method at 250 ms | retracted everywhere; matched-horizon paired comparison in section 14; Q16's real evidence declared void (orchestrator note, reported status unchanged: its pass rests on the synthetic criterion) |
| S B2, C B2 | "compact causal state (all verdict conditions met) on 19" merged the E-untestable category | 17 + 2 split everywhere (summary, sections 4.1, 4.2, 8, 10.1, 23); trap A disclosed |
| S B3 | "advantage rests on S2 and S6, not on prediction" | corrected: first place depends on S1, S2 and S6 (section 6) |
| S B4, Y B1 | a compact state claimed on net2 full, where the method declared no compact state; abstentions unreported | the method's own abstentions reported per system (section 14 table, summary, section 23); compact claims only on net1 and net3 full |
| C B3 | "never predicts held-out effects better than no effect" false for net3 mechanism b | "on no FULL network"; net3 mechanism b's pass reported as not state-mediated |
| Y B2 | Markov "with events" zero on every system | corrected: untested on 4 real mechanisms and 2 FINAL systems; markov_ok counts untested as passed (sections 8, 14) |
| Y B3 | counterexample mechanism ("huge spurious effects") contradicted by the job rows | rewritten: near-null true effects, in- and out-of-family, init-state rates, missing state (sections 9, 16) |
| R B2 | Modal total double-counted three runs | `compute_summary_postlock.py` removes them ($272); the BILLED amount ($136 through the 11:00 UTC hour, `modal_billing.py`) is now the headline (section 22) |

## Majors (grouped)

| findings | resolution |
|---|---|
| S M1, C M1, Y B1, R M2: held-out C covers silencing only; abstained pairs; null pairs, n_eff, C non-null, LOO max, alternative normalisers, denominator shares, state mediation | intervention table in section 14; statistics note in section 17 (abstained pairs excluded at Level C) |
| S M2, C minor 5: C reporting rule | applied to net2 C and net3 C; the comparator's C on the common silencing pairs given (section 14) |
| S M3: net3 mechanism b | reported as not state-mediated, not predictive, method abstained (section 14) |
| S M4, R M4 ("worse on closure, latent recovery and abstention"): paired support | paired medians and McNemar; only S1 and S6 significant; abstention profile with false alarms (section 8) |
| S M5, C M4: lineage | lineage column and per-reconstruction counts (section 14); Q19 per sweep (section 16) |
| S M6: G statistics | r2_min_mean, worst pair, prediction disagreement, modal k, data arm labelled descriptive (section 14 table) |
| S M7, Y M5, R M3: robustness horizon, capped windows, input-only control | section 17 table at 250 ms (100 ms in brackets), capped windows, input-only rows |
| S M8: S1-S5 ranking, RERANK_V3 | sections 6 and 8 |
| C M2: own abstentions | as S B4 |
| C M3: model assumptions next to Level C; title | section 14 opening, summary, section 23; title changed |
| C M5: causal wording, state mediation, lifting caveat | sections 8, 14, 23 ("not claimed" list) |
| C M6: additive-composition scope | sections 8, 23, summary |
| C M7, Y M2: kick-clip sensitivity; "conditional on the calibration"; closure power | section 8 (kick-clip S2 0.483 to 0.456); sections 4.2, 8, 14, 17 |
| C M8, Y M7: sharing wording; parameter counts; method's internal law; Q9 / Q17 | section 14 sharing table; Q9 reported n/a; Q17 non-discriminating (section 21) |
| C M9: traps missing from the summary | summary "Traps and abstention"; section 8. C's G10 sentence was false; corrected after review V (see above) |
| C M10, R M7: Q8 and other self-audit readings | section 21 notes (Q5, Q6, Q8, Q9, Q12, Q14, Q16, Q17, Q18, Q19); orchestrator notes labelled as such |
| C M11: conclusion basis and scope; fragile positive verdict | section 23; net3 full's latent reproducibility stated |
| Y M1: event kinds, unsearchable systems, typical errors, thresholds, init states, Q19 denominator | section 16 |
| Y M3: wrong-k compact verdicts, Hopf group k | section 8 |
| Y M4: k vs rhythm, N_observed, resampling | section 14 (oscillation flag on all 10; comparator k = 1 on two rhythmic mechanisms; N_observed and > 1 Hz counts; half-sample k) |
| Y M6: interventional closure gap | section 14 |
| Y M8: net1 + net3 transfer absolute level | section 14 |
| Y M9: Q5 and Q14 scope | section 21 |
| R M1: abstention column; mechanisms' N_observed | section 14 |
| R M5: K distribution | sections 8, 23, summary (median 0.987, mean 0.86, < 0.5 on 5 of 46) |
| R M6: acceptance table vs failing self-audit checks; missing log rows | section 15 self-audit column; 10 retrospective rows appended (marked), errata |
| R M8: 18 deselected tests | the 18 real-data tests were run: 18 passed (section 15, criterion 42) |
| R M9: compute items, refusals, compute-for-gain | section 22 (billed amount incl. refusals, datasets, protocols, fit CPU hours, 13x fit time) |
| R M10: post-lock reviews, Phase 3 status, biggest limitation, full-state vs compressed, final tag, synthetic family H | section 18.1; summary and section 15 (not declared complete: criterion 26 partly met); limitation 1; section 14 prediction table; tag `brainir-state-v1-phase3-final`; synthetic family H recovered by `final_h_family.py` (section 17) |
| R M11: real LOIO, J directions | section 14 |
| L M1: FINAL suite touched before the lock (reference controls, 2 systems, no method) | sections 4.2 and 7 qualified; log errata; LOG entry |

## Minors (all applied)

- S: nn_dim_rule sign; unadjusted ablation CIs and delays CI touching 0; mechanism C CIs and "abstained" wording; round 1-2 tables
  labelled version 2; comparator pool of 8 and the tie without ks_hankel (resolved by the pre-registered tie-break); net3 E margin;
  unadjusted verdict-condition CIs; limitation 7; Q12 split.
- C: net3 mechanism b C 0.38; mechanism rows; microstate equivalence on mechanisms; hidden-draw counterexample count; C reporting
  rule; organism-neutral wording; probe ranges labelled; lifting caveat in "formal causal abstraction"; denominator shares.
- Y: sign typo; ablation effects beyond medians (verdict changes, abstention switch, mean-based CIs, multiplicity); mechanism C CIs;
  section reference 13 to 14; Q8 window; FINAL interventional failures by abstention; Hopf "untestable" caused by the crash.
- R: hidden data on one platform except the local sweep; counterexample error range 12 to 9.8e8; both real sweeps named; sign typo;
  benchmark lock counts (97 files, 27 datasets); 8 lifting models and 31-102 %; mechanism C CIs; limitation 7 scope; probe ranges;
  ledger time zone; sharing_test evaluation failures; answer-bearing marking generalised.
- L: fake-salt records quarantined (`data/phase3/store_quarantine_fakesalt/`, index backup kept); the three local hidden-generation
  starts documented (section 11, LOG); amendment wording erratum and retention decision (LEAKAGE_POLICY.md section 3.1 errata); runbook
  annotated; log errata (ABORTED row, Level B launcher); snapshot provenance recorded (`scripts/p3/postlock_provenance.py`); P3-D27
  timing and "decided after the confirmation results, on public evidence only" disclosed (section 12); tool gaps listed (section 12);
  the family-H DONE row written.

## Verification review V (reviews/POSTLOCK_V.md; a separate session in the post-lock room, after the corrections)

V re-derived every blocker and major correction of S, C, Y and R from the result files. Verdict: all original blockers resolved; 35 of
39 majors resolved, 3 partly and 1 not; 1 new blocker, 3 majors and 14 minors in the corrections. All are fixed in this version:

| id | finding | resolution |
|---|---|---|
| V-B1 | "does not abstain on the non-compressible G10" (summary, section 18) is false | corrected: it declares no compact state there (recall 1 of 1), yet G10 meets the "partially supported" conditions with k = 1; false alarm on G3 (1 of 9) added; merge_self_audit Q18 note corrected |
| V-M1 | Y's nn_dim_rule S3 interval wrongly rejected; the script's S3 was not the pre-registered one | `postlock_numbers.py` uses S3 = max(0, upper CI of D) and records the stored summary's CIs; section 10.1 cites the stored `mean_ci95` (draw_folds S1, sparsity S5 [0.0015, 0.072], nn_dim_rule S3 [-0.066, -0.0013], float-level S3 of 8 switches) and its reading is rewritten |
| V-M2 | the permitted claim still called the net2-full latent "sufficient" | the claim, the summary and section 23 are split: net1 full and net3 full (R1, 2-dimensional, the method's own claim) against net2 full (R2: predictive against the controls, but the method declared no compact state and PCA-k and the comparator predict significantly better) |
| V-M3 | lineage missing from most Level C tables; pooled counts | lineage columns in the intervention, prediction, reproducibility and robustness tables; per-lineage counts for PCA-k, verdicts, abstentions, microstate equivalence, closure, seeds and the counterexample breakdown |
| minors 1-14 | "same to 3 decimals"; the all-abstained mechanisms' stored status; Q15 wording (lin_falds_t); seed-0 vs modal k (net2 mechanism b); FINAL leave-one-component-out rankings; capped marks and incomparable lower bounds; untraceable numbers; closure power next to "predictive and closed"; category names in trap sentences; billing window; family H ran twice; S7 wording; both alternative normaliser floors; "all corrected here" | all applied (sections 8, 14, 17, 18, 18.1, 21, 22, 23, 24, summary). The untraceable numbers now point to `POSTLOCK_NUMBERS.json` (fit records and public data), and the test runs to `research/phase3/TEST_RUNS.md` |

