# Phase 4 self-audit (goal5 section 91)

**DRY RUN** (stand-in models, before the lock): not a result; never released, never used for any decision.

Method `p3stand.refstand:p3stand_ref` on None + real public; 3 systems (0 compressible synthetic, 1 real full networks); tolerances PROVISIONAL. Status counts: FAIL 3, NOT_APPLICABLE 1, NOT_TESTABLE 12, PASS 3, REPORT 2.

| id | question | status | pass rule | key evidence |
|---|---|---|---|---|
| Q1 | Could intervention ID alone explain results? | **NOT_TESTABLE** | method better (upper CI < 0) on the confirmation suite and on >= 2 of 3 real full networks; SMS_ID upper CI <= tau_SMS on >= 50 % of systems | ; SMS_id within tau on 0 |
| Q2 | Could stimulus alone explain results? | **NOT_TESTABLE** | method better on the confirmation suite and on >= 2 of 3 full networks | no evaluations of the role 'input_only' |
| Q3 | Could readout history explain results? | **NOT_TESTABLE** | method better on EE on the confirmation suite and on >= 2 of 3 full networks | no evaluations of the role 'readout_history' |
| Q4 | Did future data leak? | **PASS** | all four hold | a True, b True, c True (3 fits, 3 evals), d True (0 findings) |
| Q5 | Does the latent state collapse? | **FAIL** | PR >= min(k, 1.5) on >= 80 % of systems with k >= 2; floor binds on < 5 % | PR ok on 0.333 of 3; floor binds on 0 |
| Q6 | Does residual microstate predict intervention outcomes? | **FAIL** | upper CI <= tolerance on >= 60 % of compressible confirmation systems and on the real full networks where testable | within tolerance on - of 0 synthetic |
| Q7 | Are intervention operators state-dependent? | **NOT_TESTABLE** | descriptive; flag where the model's read-in is state-independent but the truth's state-dependence explains > 30 % | 0 testable; flagged 0 |
| Q8 | Does the lift exploit simulator quirks? | **PASS** | success drops by < 50 % relative; < 20 % saturating / out-of-range | success 0.174 -> 0.188 (drop -0.08); saturating 0.142 |
| Q9 | Do multiple lifts diverge later? | **PASS** | long / medium ratio <= 2 on >= 60 % of testable systems | ratio <= 2 on 1 of 1 |
| Q10 | Does active design just choose large-effect interventions? | **NOT_APPLICABLE** | if active design succeeds (PROTOCOL 5.17) it must also beat magnitude-matched random at >= 2 budgets | the locked method has no designer of its own (no active-design claim to audit) |
| Q11 | Does causal state fail under weak effects? | **NOT_TESTABLE** | weak class: upper CI of EE < 1, or abstention >= 50 %; below-detection class: false-confidence rate <= tau_FC | weak EE upper -, weak abstention -; below FC - |
| Q12 | Does performance disappear on unseen intervention types? | **NOT_TESTABLE** | far-shift EE upper CI < 1 on >= 50 % of systems | far-shift EE upper < 1 on - of 0 |
| Q13 | Does k change wildly across resamples? | **NOT_TESTABLE** | stable on >= 70 % of confirmation systems | stable on - of 0 |
| Q14 | Does a simple linear controlled model perform equally well? | **NOT_TESTABLE** | report; FAIL = not significantly better (goal5 94 D) | no evaluations of the linear controlled baseline |
| Q15 | Does the full-state model itself fail? | **REPORT** | report; where it fails, the compact-state failure is attributed to excitation / data (goal5 94 B) | full-state bound fails A on 1 of 1 |
| Q16 | Does the synthetic benchmark resemble real response statistics? | **NOT_TESTABLE** | required statistics in range (acceptance criterion 11) | no calibration compare of the confirmation suite (None) |
| Q17 | False compact causal states on non-compressible systems? | **NOT_TESTABLE** | at most 1 of their confirmation systems | no non-compressible confirmation system |
| Q18 | Does shared dynamics fail when systems are unrelated? | **NOT_TESTABLE** | rejected on every unrelated pair | no sharing results configured |
| Q19 | Can adversarial counterexample search break the model immediately? | **NOT_TESTABLE** | found on <= 50 % of confirmation systems | no counterexample study configured |
| Q20 | Does intervention training matter? | **FAIL** | removal worsens EE significantly (paired, system bootstrap) | EE_ablated - EE_full - (lower -, p -) |
| Q21 | Is the state bottleneck needed? | **REPORT** | report 'outcomes predictable but compact causal abstraction unsupported' if the direct model predicts and the compact one does not | outcomes not predictable even without the bottleneck (attributed to excitation / data; goal5 section 94 B) |

FAIL weakens the central claim and is reported, never hidden; NOT_TESTABLE / PARTIAL name the missing inputs in SELF_AUDIT.json.
