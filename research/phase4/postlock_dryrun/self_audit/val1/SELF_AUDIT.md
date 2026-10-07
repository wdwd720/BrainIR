# Phase 4 self-audit (goal5 section 91)

**DRY RUN** (val tier (Level B selection tier), stand-in models, before the lock): not a result; never released, never used for any decision.

Method `p3stand.refstand:p3stand_ref` on val; 50 systems (46 compressible synthetic, 0 real full networks); tolerances PROVISIONAL. Status counts: FAIL 11, NOT_APPLICABLE 2, PARTIAL 1, PASS 4, REPORT 3.

| id | question | status | pass rule | key evidence |
|---|---|---|---|---|
| Q1 | Could intervention ID alone explain results? | **FAIL** | method better (upper CI < 0) on the confirmation suite and on >= 2 of 3 real full networks; SMS_ID upper CI <= tau_SMS on >= 50 % of systems | id_baseline: suite diff -8.83 (upper -8.67); SMS_id within tau on 0.13 |
| Q2 | Could stimulus alone explain results? | **FAIL** | method better on the confirmation suite and on >= 2 of 3 full networks | suite diff 0.25 (upper 0.397); networks better 0/0 |
| Q3 | Could readout history explain results? | **PARTIAL** | method better on EE on the confirmation suite and on >= 2 of 3 full networks | suite diff -8.84 (upper -8.68); networks better 0/0 |
| Q4 | Did future data leak? | **PASS** | all four hold | a True, b True, c True (50 fits, 50 evals), d True (0 findings) |
| Q5 | Does the latent state collapse? | **FAIL** | PR >= min(k, 1.5) on >= 80 % of systems with k >= 2; floor binds on < 5 % | PR ok on 0.5 of 50; floor binds on 0 |
| Q6 | Does residual microstate predict intervention outcomes? | **FAIL** | upper CI <= tolerance on >= 60 % of compressible confirmation systems and on the real full networks where testable | within tolerance on 0.522 of 46 synthetic |
| Q7 | Are intervention operators state-dependent? | **REPORT** | descriptive; flag where the model's read-in is state-independent but the truth's state-dependence explains > 30 % | 50 testable; flagged 0 |
| Q8 | Does the lift exploit simulator quirks? | **PASS** | success drops by < 50 % relative; < 20 % saturating / out-of-range | success 0.00319 -> 0.00383 (drop -0.2); saturating 0.189 |
| Q9 | Do multiple lifts diverge later? | **PASS** | long / medium ratio <= 2 on >= 60 % of testable systems | ratio <= 2 on 1 of 23 |
| Q10 | Does active design just choose large-effect interventions? | **NOT_APPLICABLE** | if active design succeeds (PROTOCOL 5.17) it must also beat magnitude-matched random at >= 2 budgets | the locked method has no designer of its own (no active-design claim to audit) |
| Q11 | Does causal state fail under weak effects? | **FAIL** | weak class: upper CI of EE < 1, or abstention >= 50 %; below-detection class: false-confidence rate <= tau_FC | weak EE upper 1.86, weak abstention 0.544; below FC 0.435 |
| Q12 | Does performance disappear on unseen intervention types? | **FAIL** | far-shift EE upper CI < 1 on >= 50 % of systems | far-shift EE upper < 1 on 0.0435 of 46 |
| Q13 | Does k change wildly across resamples? | **FAIL** | stable on >= 70 % of confirmation systems | stable on 0.68 of 50 |
| Q14 | Does a simple linear controlled model perform equally well? | **FAIL** | report; FAIL = not significantly better (goal5 94 D) | suite diff 0.191 (upper 0.32); networks better 0/0 |
| Q15 | Does the full-state model itself fail? | **REPORT** | report; where it fails, the compact-state failure is attributed to excitation / data (goal5 94 B) | full-state bound fails A on 46 of 46 |
| Q16 | Does the synthetic benchmark resemble real response statistics? | **FAIL** | required statistics in range (acceptance criterion 11) | 34/35 in range; failing ['input_gain_elasticity_y'] |
| Q17 | False compact causal states on non-compressible systems? | **PASS** | at most 1 of their confirmation systems | 0 of 4 supported |
| Q18 | Does shared dynamics fail when systems are unrelated? | **NOT_APPLICABLE** | rejected on every unrelated pair | the method declares shared dynamics not applicable: {'reason': 'the stand-in fits every system independently', 'status': 'not_applicable'} |
| Q19 | Can adversarial counterexample search break the model immediately? | **FAIL** | found on <= 50 % of confirmation systems | found on 0.652 of 46 |
| Q20 | Does intervention training matter? | **FAIL** | removal worsens EE significantly (paired, system bootstrap) | EE_ablated - EE_full -0.25 (lower -0.398, p 1) |
| Q21 | Is the state bottleneck needed? | **REPORT** | report 'outcomes predictable but compact causal abstraction unsupported' if the direct model predicts and the compact one does not | outcomes not predictable even without the bottleneck (attributed to excitation / data; goal5 section 94 B) |

FAIL weakens the central claim and is reported, never hidden; NOT_TESTABLE / PARTIAL name the missing inputs in SELF_AUDIT.json.
