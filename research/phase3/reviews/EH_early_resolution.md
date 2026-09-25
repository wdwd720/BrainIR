# Early reviews E (statistics) and H (numerical methods): resolution (2026-09-25)

The reviews are `E_early.md` and `H_early.md`, with their evidence scripts in `E_early_scratch/` and `H_early_scratch/`.

**Setup.** Both reviewers were oracle-free agents in `C:\Dev\BrainIR_p3review`: a snapshot of the clean room plus `extra/`, the
orchestrator-side code with dataset and paper names redacted (LOG P3-D13).

**What they found.** E reported 5 blockers and 6 majors, H 1 blocker and 7 majors. Every finding concerns the evaluation machinery.
None concerns leakage (E: "I found no route by which hidden data reach a fit").

**Timing.** All of it was found before any candidate had been scored on held-out data and before the hidden real data existed. The
fixes therefore make up benchmark VERSION 2 (PROTOCOL.md section 10.1), locked before any Level B or Level C evaluation. The
developers were told what changed in the public evaluator (generic description, `notes/_tournament_feedback.md`), never the reviews.

## Blockers

| finding | resolution | verification |
|---|---|---|
| E B1: the tournament rank depends on the command-line order (ties, NaN, all-NaN S8 in the pilot); tie-break not implemented | `evaluate_cross.rank_profiles`: average ranks, non-finite last (tied), components non-finite for every candidate dropped, ties broken by fewer transition parameters then name; used by `tournament.py` and `merge_rounds.py` | `test_selection_v2.py`: permutation invariance, a strictly better candidate wins in either order, tie-break |
| E B2: non-finite rollouts silently dropped from A (a model that declines hard starts got a better A; n misreported) | window errors capped at NMSE 10; a non-finite prediction counts as the cap; counts of capped / non-finite windows reported; n = the units actually scored | `test_evaluate.py::test_nonfinite_predictions_count_as_the_cap_and_are_reported` |
| E B3: S1-S5 medians over each method's own subset of systems; evaluation errors not counted for eligibility | `evaluate_cross.profile_from_systems` over the round's FIXED compressible list with worst-value imputation (+inf S1-S4, -inf S5, not-in-range S6); S4 leaves out untestable E (count reported); eligibility counts fit AND evaluation failures | `test_selection_v2.py::test_failed_systems_count_as_worst_values` |
| E B4: Level C did not implement the pre-registered primary family (only A and C entered Holm; D, E, K had no test; NaN p-values shrank the family; superiority vs non-inferiority unstated) | `level_c.py`: 13 one-sided non-inferiority tests (A, C, D, E per full system; K on FINAL), margins pre-registered in PROTOCOL section 8, paired bootstraps (D: trajectory clusters on the same points; E: pool trajectories within draw on the same pool; K: systems); an uncomputable test stays in the family with p = 1; secondary two-sided superiority family | `test_selection_v2.py::test_holm_keeps_uncomputable_tests_and_ni_p_has_a_floor`; `holm` test updated |
| E B5: D and E conditions are point estimates that the evaluator's seed flips on about half the systems | D: 5 repeated cross-fits (new folds and random features), per-point errors averaged, 95 % CI by trajectory clusters; E: 95 % CI by resampling pool trajectories within draw (matched set recomputed per resample); verdicts judge the UPPER CI bound; tau_D, tau_E recalibrated on the true-latent reference's upper bounds | `test_closure_has_repeated_folds_and_a_trajectory_cluster_ci`; E CI in the invariance test |
| H B1: E changes under invertible reparametrisations of z and blows up near-constant coordinates | distances whitened with the FULL covariance of the model's encodings of up to 64 PUBLIC training trajectories (eigenvalue floor 1e-8 x the largest), the same for the output- and PCA-matched controls | `test_e_is_invariant_to_invertible_linear_maps_and_dead_coordinates` (a condition-20 map changes E by < 1e-6 relative; a dead coordinate does not blow it up) |

The eigenvalue floor was first set at H's suggested 1e-4. The invariance test then failed: the toy's own PCA latent has a 3000:1
variance ratio, and the condition-20 map pushes a legitimate direction to 1e-6 of the largest eigenvalue. At 1e-8 a numerical-noise
coordinate (1e-6 of sd(z)) still stays negligible after whitening.

## Majors

| finding | resolution |
|---|---|
| E M1: tolerances uncertain (bootstrap CIs over the 45 calibration systems are wide) and transferred to real circuits unchecked | the calibration now reports every tolerance's 95 % CI over systems, and the true-latent verdicts at both CI ends (pre-registered sensitivity analysis); PROTOCOL section 6 declares the real verdicts CONDITIONAL on the synthetic calibration |
| E M2: the oracle could never earn "compact causal state discovered" (no reference supports edge removal; verdict and calibration treat abstention differently); tau_E is a bar the ceiling misses | edge removal (a change of the dynamics law) is scored as its own family C_structural, reported, not in the verdict (goal4 section 11 asks for it "where supported"); calibration and verdict now use the same pair set; the calibration records the verdict distribution of the true-latent reference and of the full-state ceiling |
| E M3 and H M4: C rests on few units; one pair carries most of the denominator | C stays the energy-weighted ratio of sums (it measures the fraction of effect energy mispredicted; a family-balanced mean would be driven by near-zero-effect families). Reported per system: n_eff = (sum d)^2 / sum d^2 and the largest pair's share, plus per-family C. Limitation in the report. The hidden real sets have 30 pairs per family per full system (the review's figures used the 40 public pairs) |
| E M4: sharing margins mis-scaled (A margin tau_A = 131 %, C margin 0.05 unattainable); the unrelated-pair nulls got an automatic leave-one-out pass; always-reject scored 0.6 on S8 | margins relative to the quantities (A: 0.2 x independent A; C: max(0.05, 0.2 x independent C)); leave-one-implementation-out fits for the unrelated pairs too (the same rule for nulls); S8 = balanced accuracy over groups and pairs. Operating characteristics with a shared true-latent reference were NOT computed (no reference implements shared dynamics); limitation |
| E M5: ranking has no uncertainty; selection optimism | `selection_bootstrap`: P(rank 1), 90 % rank interval, P(eliminated) in the pilot (1,000 resamples of systems); PROTOCOL section 9 states that heldout values of the selected method are selection-biased and that claims rest on FINAL and Level C |
| E M6: merges across different designs possible | the round's design is recorded (suite, pilot flag, systems, compressible list, G systems, shared fits, simulation budget, time limit, benchmark version); `merge_rounds.py` refuses mixed designs |
| H M1: synthetic kicks that push a saturating unit out of range produce a jump set by the generator's clip constant (11 % of held-out intervention pairs) | NOT changed: the generator is hash-locked (written by the oracle-free author), and the behaviour is deterministic and equally present in the training kicks, so a model can learn it. Limitation in the report; a sensitivity analysis excluding affected pairs is possible truth-side |
| H M2: the readout-history shortcut was handicapped by its horizon grid | `DirectHorizonModel`: one direct ridge model per step up to the longest horizon |
| H M3: D diluted by near-constant readout dims standardised by their test spread | D's readout targets keep the PUBLIC readout scale (no re-standardisation on test points) |
| H M5: a finite but diverged training trajectory sets the readout normaliser (1e6 deflation on one dev system) | `readout_scale` leaves out blow-ups (max abs y or x > 100 x the median trajectory's); reference controls are fitted without them. The trajectories stay in the data; methods see them |
| H M6: the lifting evaluation mixed two noise realisations (the generator's noise depends on t_end) | base run, lifts and twins share the protocol's own end time |
| H M7: E cannot pass for a true state with k >= 4-6 with a finite pool; tolerances synthetic-only | testability rule: E is UNTESTABLE when the matched pairs are not close (median matched / median random whitened distance > 0.2) or random pairs diverge less than 2 x the floor; a separate verdict category "compact causal state discovered (microstate equivalence untestable)"; PROTOCOL declares tau_D / tau_E synthetic-calibrated |

## Minors

Resolved:
- E: p-value floor (1 + count) / (1 + B); references fitted on train + val like methods; k = 0 kept; the reference cache keyed by the
  evaluator's code tag; explicit keys in the sharing functions; skipped late pairs counted.
- H m1: real twins keep the event breakpoints (`realgen.counterfactual`; hidden real data are generated with it; the public twins keep
  a <= 0.011 Hz pre-event difference).
- H m2: current lifts are read at the end sample.
- H m3: the noise guard uses the spread of z over all test encodings.
- H m4: future-input features in D.
- H m5: the effective PCA k is reported.
- H m6: E floor guard (the testability rule).
- H m8: closure start as a config value.

Kept, as limitations:
- E: A units cluster within parameter draws (the pool trajectories come from 4 draws). The within-system A CIs treat trajectories as
  units.
- E: K's regression standardises features within the cross-fitted test set.
- H m7: events at t = t_end are ignored by the simulators.
- H m9: the real engine's non-finite counts are not recorded.

## Calibration (version 2)

The run: 45 dev systems on Modal, 429 s wall, 14,303 container-seconds, about $2.1 (`benchmarks/state_discovery_v1/calibration.json`;
PROTOCOL section 6).

| tolerance | v2 value | 95 % CI over systems | v1 value (point-estimate rule) |
|---|---|---|---|
| tau_A | 0.784 | [0.26, 2.30] | 1.31 |
| tau_C | 3.29 | [2.03, 34.1] | 3.18 |
| tau_D | 0.400 (upper CI rule) | [0.27, 0.55] | 0.085 |
| tau_E | 0.0179 (upper CI rule) | [0.0063, 0.027] | 0.0039 |

**Verdicts under the calibrated tolerances (review E M2):**
- true-latent reference: 2 compact, 1 compact with E untestable, 28 partially supported, 14 not supported;
- full-state ceiling: 2 compact with E untestable, 30 partially supported, 13 not supported.

**Why the true-latent reference fails.** The interventional condition fails on 41 of 45 systems: the upper CI of C is below 1 only
rarely, and the median C is 1.58. The predictive condition fails on 12 (the shortcut test on 9), closure on 5. E is testable on 44.

**Sensitivity.** The verdict counts barely change at either end of any tolerance's CI (pre-registered sensitivity analysis). The
verdict is therefore dominated by held-out intervention prediction, which is hard even with the exact state. The report must say
this whenever it interprets a candidate's verdict counts.
