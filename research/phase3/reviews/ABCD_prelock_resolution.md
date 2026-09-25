# Resolution of the pre-lock reviews A-D (benchmark version 3; method requirements)

The four independent pre-lock reviews (`A_prelock.md` system identification, `B_prelock.md` causal inference, `C_prelock.md`
representation learning, `D_prelock.md` computational neuroscience; scratch material in `*_prelock_scratch/`) examined
brainir_state_v1 and benchmark version 2 on PUBLIC data (DEV suite, real public data) and the calibration record. This file maps
every blocker and major issue to its resolution. Evaluation fixes went into benchmark version 3 (PROTOCOL.md section 10.1; tag
`state-discovery-benchmark-v3`). Method findings were relayed to the developer as GENERIC requirements only
(`research/phase3/review_contracts/composer_requirements*.txt`; no reviewer result, system or trap). The reviews are answer-bearing
(they discuss dev-suite truth and held-out aggregate feedback) and never enter a clean room.

Status key: FIXED (evaluation change, tested), RELAYED (generic requirement to the developer; the developer's response is recorded in
the method notes and the lock), LIMITATION (stated in PROTOCOL.md and the report), REPORTED (new descriptive output).

## Review A (system identification)

| finding | resolution | where |
|---|---|---|
| B1 no test of hidden memory; stash side channel | FIXED: rollout isolation (`evaluate.Fresh`), Markov restart in z and y, decoy check, restart after interventions; markov_ok gates k, compact and closed; readout consistency reported | evaluate.py (`Fresh`, `eval_rollout_checks`, `eval_intervention`), harness.verdict; tests `test_evaluate_v3.py` (instance stash defeated; hidden rollout memory and module-level stash fail) |
| B2 'closed' powerless; history ignored; S3 rewards noise | FIXED: tau_H (history gain) in 'closed'; closure gap under a pre-registered power rule; power table and wording rule in the calibration; S3 = max(0, upper CI of D). While fixing it, an ARTEFACT was found: the ridge penalty shrank the base (z, u) of the D regressions, so collinear columns (history copies of z, or the residual) "helped" even for the true state (history gain 0.74 on the toy with the exact state). The base is now fitted without shrinkage | evaluate.py (`_ridge_fit_predict` n_free, `eval_closure`), calibrate.py, PROTOCOL 4 / 6 / 7; test `test_true_state_has_no_closure_gain_in_either_regression` |
| M1 dimension rule noise-driven, seed-unstable (method) | RELAYED (requirements batch 1 item 4, batch 2 item 4) | composer_requirements*.txt |
| M2 k sweep depends on wall-clock (method) | RELAYED (batch 1 item 1, required); determinism now a protocol rule (PROTOCOL 9) | |
| M3 G's CCA inflated; no data-resampling arm | FIXED: r2_min, k agreement, prediction disagreement as headline; CCA padded to max(k); data-resampling arm at Level C | evaluate_cross.eval_reproducibility; level_c.py (`--resample-arm`) |
| M4 S6 / K reward wide ranges | FIXED: point k (exact) in S6 and K dimension recovery; range descriptive | evaluate_cross.system_values |
| M5 no closure check under interventions | FIXED / REPORTED: Markov restart after interventions (judged); interventional closure gap (reported); requirement on event operators and encoder memory RELAYED (batch 2 item 6) | eval_intervention |
| minor: D residual leakage | FIXED: residual inside each training fold | eval_closure |
| minor: relative gaps not scale-invariant | FIXED: per-coordinate relative to the training variance of z | eval_rollout_checks |
| minor: SYNTH_CFG closure start implicit | PROTOCOL table states it (0.25 s, both kinds) | PROTOCOL 4 |
| minor: non-finite states zeroed (method) | RELAYED (batch 2 item 2) | |
| minor: coarse-grid input sampling (method) | noted; harmless for the protocol's pulse widths; restart points on the rollout-restart grid | |
| minor: declared abstention not in the verdict | FIXED: a declared causal_equivalence_failed / no_compact_state blocks the "compact causal state" verdict | harness.verdict |

## Review B (causal inference)

| finding | resolution | where |
|---|---|---|
| B1 C does not establish a causal state | FIXED (option a + b): claim wording "held-out intervention effects predicted better than no effect"; tau_C declared non-binding; C_scrambled (mean training encoding, and another pair's z0) with the paired difference; 'state_mediated' reported | eval_intervention, harness.verdict, PROTOCOL 6-7 |
| B2 mechanism systems' *_B families not held out | FIXED: per-mode role table; mechanism held-out C = group silencing | harness.roles_for, suite_eval |
| M1 stateful side channel | FIXED (see A B1) | |
| M2 unobserved targets in C | FIXED: observed-target pairs in the verdict; unobserved-target pairs reported apart; requirement RELAYED (batch 2 item 3) | harness.evaluate_system(observed=...) |
| M3 C carried by 1-3 pairs | FIXED: leave-one-pair-out condition; untestable with < 3 primary-window pairs; n_eff, null pairs reported | eval_intervention, verdict |
| M4 no lifting for v1; lifting gameable | FIXED: identical / near-identical lifts rejected, untestable instead of perfect; lift_supported; the report states v1 does not support lifting (no do(z) claims) | evaluate_lift.py; tests `test_v3_lift_realgen.py` |
| M5 tau_C not from a causal state | LIMITATION (PROTOCOL 6) | |
| m1 clipping / non-finite (method) | RELAYED (batch 2 item 2) | |
| m2 zero-gain kinds reported as supported (method) | RELAYED (batch 1 item 2, required) | |
| m3 lift timing; zsd from one case | FIXED: one reference sample j for the achieved shift and the do() test; zsd over all cases | evaluate_lift.py |
| m4 parameter identity descriptive | LIMITATION (held-out draws; E pairs within draw) | |
| m5 pairs outside the primary window not counted | FIXED: pairs in the primary window reported; < 3 = untestable | |

## Review C (representation learning)

| finding | resolution | where |
|---|---|---|
| B1 S6 / K reward wide ranges | FIXED (see A M4); rounds 1-3 re-ranked under version 3 for the record | evaluate_cross; scripts/p3/rerank_v3.py |
| M1 event read-in from observational weights (method) | RELAYED (batch 1 item 3; batch 2 item 6) | |
| M2 baselines untuned; comparator on untested components | FIXED: independent baseline tuner (fresh clean-room agent without a competing candidate; `<baseline>_t` variants); comparator ranked on S1-S5 among markov-valid baselines only | agent_prompts/baseline_tuner.txt; level_c.choose_comparator; PROTOCOL 9 |
| M3 K saturated, one-directional | FIXED: min(R^2 both directions) in S5 and the primary K test | system_values; level_c |
| M4 C NI passable by no-effect models | FIXED: reporting rule (method's own C upper CI < 1) | level_c; PROTOCOL 8 |
| M5 selection fragile; no decision rule | FIXED: pre-registered bootstrap decision rule with a parsimony tie-break; rankings on S1-S5 and leave-one-component-out reported; disclosure that the hybrid was composed after aggregate feedback | tournament / merge_rounds; PROTOCOL 9 |
| minor 1 kick read-in lag-0 only (method) | RELAYED (batch 2 item 6) | |
| minor 2 model class changes with k (method) | RELAYED (batch 2 item 4) | |
| minor 3 parameter counts self-reported | LIMITATION; rank tie-break only | |
| minor 4 noise guard descriptive | REPORTED: noise fragility at sigma 0.05 per system | harness.verdict |
| minor 5 PCA-k / random-k not capacity-matched | LIMITATION (they are controls, not competitors) | |
| minor 6 in-sample sharing test (method) | RELAYED (batch 2 item 8) | |
| minor 7 a trap label in the notes | no evaluation change (L definition unchanged) | |

## Review D (computational neuroscience)

| finding | resolution | where |
|---|---|---|
| B1 real NMSE dominated by near-silent readouts | FIXED: pooled normaliser for real systems; per-dimension shares and C under per-dimension floors 1e-3 / 1e-2 reported | evaluate.readout_scale(pooled), SuiteData.scale / alt_scales |
| B2 real predictive condition unattainable | FIXED: real predictive = below input-only and persistence (paired); readout-history and the full-state reference descriptive ("reference", not "ceiling"); level-corrected A | harness.verdict, eval_persistence (units), eval_predictive |
| B3 mechanism *_B families not held out | FIXED (see B B2) | |
| M1 kicks clipped / null; record shows requested delta | FIXED: clip documented; applied deltas recorded in hidden data info; null pairs and non-null C reported | realsim / realgen / generate_real_hidden; eval_intervention |
| M2 synthetic types additive; kick-clip artefact | LIMITATION + FIXED: scoped claim; pre-registered kick-clip sensitivity (truth-side pair list) | PROTOCOL 2.2; scripts/p3/kick_clip_pairs.py; harness exclude_keys |
| M3 "real" overstated | FIXED (wording): "connectome-constrained rate-model simulations"; model assumptions; "noise realisations" removed; "new i.i.d. draws" | PROTOCOL 1-3 |
| M4 dependent systems; real I | FIXED: lineage fields; real I descriptive; no double counting | PROTOCOL 2.1 / 8; level_c |
| M5 k = 1 cannot represent oscillations; A = input-only (method) | RELAYED (batch 2 item 5) | |
| m1 two mechanisms do not sustain the rhythm | REPORT (not described as rhythm generators) | report |
| m2 N_observed inflated by quiet neurons | REPORTED: k / N against neurons peaking above 1 Hz | PROTOCOL 2.1 |
| m3 pulses latch networks | REPORT (state switches noted for pulse families) | report |
| m4 real currents depolarising only | PROTOCOL 3.1 | |
| m5 OOD may recruit neurons outside x | REPORTED (share of activity outside x) | PROTOCOL 3.1 |
| m6 inherited readout lists | REPORTED (active readout count) | PROTOCOL 2.1 |
| m7 public twins lack breakpoints | no change needed | |

## Re-checks

- Version 3 unit tests: `phase3/tests/test_evaluate_v3.py`, `test_v3_lift_realgen.py`, `test_v3_selection.py`, plus the existing
  Phase 3 tests.
- Calibration version 3 on the DEV suite (Modal): tolerances, closure power, Markov checks of every reference (`calibration.json`).
- Round 3 re-run under version 3 with the updated brainir_state_v1 and the tuned baselines (LEVELB_LOG.md).
- The reviewers' demonstration models (stash, hidden memory) are reproduced as unit tests and fail / are defeated as required.
