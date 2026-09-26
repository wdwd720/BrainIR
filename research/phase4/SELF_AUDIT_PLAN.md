# Phase 4 self-audit plan (goal5 section 91): every question TESTED, thresholds fixed before any Level C evidence exists

Draft written during benchmark construction; finalised (and implemented as `scripts/p4/self_audit_p4.py`) BEFORE the method lock.
Each check reads Level C results only; "fail" weakens the central claim and is reported, never hidden. Units and CIs follow
PROTOCOL.md section 11.

| id | question | test | pass rule (fixed now) |
|---|---|---|---|
| Q1 | Could intervention ID alone explain results? | paired EE, locked method vs the ID-shortcut (reference and best tournament ID baseline) on target-shift and held-out-family items; SMS with the ID features alone | method better (upper CI of the paired difference < 0) on the confirmation suite (system bootstrap) and on >= 2 of 3 real full networks; SMS_ID upper CI <= tau_SMS on >= 50 % of systems |
| Q2 | Could stimulus alone explain results? | paired EE vs the input-only baseline | method better on the confirmation suite and on >= 2 of 3 full networks |
| Q3 | Could readout history explain results? | paired EE and passive NMSE vs the readout-history baseline | method better on EE on the confirmation suite and on >= 2 of 3 full networks |
| Q4 | Did future data leak? | (a) encodings from histories truncated at t equal encodings inside the full evaluation (bitwise); (b) decoy check: encoding other trajectories first changes no prediction (fresh copies); (c) the fit / evaluation sandbox logs no refused file / process / network event; (d) code audit of the locked source for global state | all four hold |
| Q5 | Does the latent state collapse? | effective rank (participation ratio) of the model's encodings over the pool vs its k; fraction of systems where the whitening floor binds | participation ratio >= min(k, 1.5) on >= 80 % of systems with k >= 2; floor binds on < 5 % |
| Q6 | Does residual microstate predict intervention outcomes? | ICG_y and SMS with {x_res} alone (PROTOCOL 5.3-5.4) | upper CI <= tolerance on >= 60 % of compressible confirmation systems and on the real full networks where testable |
| Q7 | Are intervention operators state-dependent? | model read-in dz for identical events at different states: variance ratio across states; synthetic: correlation with the true state-dependence (true_latent_effect mapped into model coordinates) | descriptive; flag if the model's read-in is state-independent where the truth's state-dependence explains > 30 % of effect variance |
| Q8 | Does the lift exploit simulator quirks? | lift success under +-10 % amplitude jitter; fraction of successful lifts at clipping bounds or beyond the development magnitude range | success drops by < 50 % relative; < 20 % of successful lifts use saturating / out-of-range magnitudes |
| Q9 | Do multiple lifts diverge later? | multiple-lift divergence at the long horizon vs the medium horizon (relative to the lifted effect) | long / medium ratio <= 2 on >= 60 % of testable systems |
| Q10 | Does active design just choose large-effect interventions? | magnitude distribution of designed vs random experiments; a magnitude-MATCHED random design at the same budgets | if active design "succeeds" (PROTOCOL 5.17), it must also beat magnitude-matched random at >= 2 budgets; otherwise report "large-effect selection explains the gain" |
| Q11 | Does causal state fail under weak effects? | EE and abstention per detectability class | weak class: upper CI of EE < 1, or abstention >= 50 %; below-detection class: false-confidence rate <= tau_FC |
| Q12 | Does performance disappear on unseen intervention types? | EE on far-shift families vs in-family | far-shift EE upper CI < 1 on >= 50 % of systems |
| Q13 | Does k change wildly across resamples? | bootstrap-refit k (PROTOCOL 5.10) | stable on >= 70 % of confirmation systems |
| Q14 | Does a simple linear controlled model perform equally well? | paired EE, method vs the best linear controlled baseline (fixed at Level B) | report; "fail" = not significantly better (goal5 section 94 D: then use the simple model) |
| Q15 | Does the full-state model itself fail? | the full-state bound's EE and A criterion per system | report; where it fails, the compact-state failure is attributed to excitation / data (goal5 section 94 B) |
| Q16 | Does the synthetic benchmark resemble real response statistics? | calibstats compare of the confirmation suite vs the public real targets | required statistics in range (acceptance criterion 11) |
| Q17 | False compact causal states on non-compressible systems? | "CAUSAL STATE SUPPORTED" on types 20 / 21 | at most 1 of their confirmation systems |
| Q18 | Does shared dynamics fail when systems are unrelated? | sharing rule on unrelated pairs | rejected on every unrelated pair |
| Q19 | Can adversarial counterexample search break the model immediately? | counterexample search (random + evolutionary, 50 evaluations per system) for detectable-effect interventions within the model's claimed validity domain, not abstained, with EE_i > 1 | found on <= 50 % of confirmation systems within 50 evaluations |
| Q20 | Does intervention training matter? (critical ablation, goal5 section 88) | the locked method with ALL interventional training removed | removal worsens EE significantly (paired, system bootstrap); otherwise Phase 4's core hypothesis fails |
| Q21 | Is the state bottleneck needed? (goal5 section 89) | the locked method without the state bottleneck (direct model) | report: "outcomes predictable but compact causal abstraction unsupported" if the direct model predicts and the compact one does not |
