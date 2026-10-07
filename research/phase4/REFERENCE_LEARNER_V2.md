# Reference learner v2 (fork E13, 2026-09-26; before the freeze)

The benchmark's shared generic controlled learner (`brainir_causal.refs`, PROTOCOL section 8) is the learner of every state-based
reference: TRUE-STATE (the calibration anchor), OBS-SHORTCUT, FULL-STATE (the predictability anchor), PCA-k, RANDOM-k and the
power-table corruptions. On the real generator systems of the dev tier, v1 scored WORSE THAN NO EFFECT for TRUE-STATE on most systems,
which would have made the pre-registered calibration declare the verdict unattainable. This note records the diagnosis, the redesign
and the dev-suite validation. Everything here uses the dev tier only (public D0 + D1 for fitting, the dev eval part for scoring); no
val / conf / real hidden data.

## 1. Symptom

Orchestrator diagnostic (`calibrate.reference_breakdown`, 8 dev systems) and fork E11's static fits: NO-EFFECT class-balanced EE
0.72-0.99; TRUE-STATE 0.57-6.78 (worse than no effect on 6 of 8), IN-FAMILY EE up to 8.8 (type 16) and 5.0 (type 13); FULL-STATE
1.09-2.29 on 8 of 8; many items at the 10x cap in the strong / hi classes.

## 2. Diagnosis (local, dev systems syn-4dbd7abc4a80 = type 16 and syn-00e48aa6ad4d = type 24; scripts in the orchestrator scratchpad)

Decomposition of TRUE-STATE's error at the primary horizon (250 steps at dt = 1 ms):

| quantity | type 16 | type 24 |
|---|---|---|
| EE (model) pooled / class-balanced | 1.27 / 2.28 | 6.35 / 5.94 |
| EE of the model's READOUT applied to the TRUE latent trajectories | 0.19 / 0.17 | 0.07 / 0.06 |
| in-family EE (model) | 8.84 | 1.82 |
| median relative latent-effect error at lag 5 / 25 / 250 steps | 9.6 / 10.0 / 42 | 3.3 / 3.3 / 8.8 |

1. The READOUT is fine; the error is in the latent dynamics under interventions, and it is large 5 ms after the onset already, so it
   is not (only) rollout drift. Training v1 with unrolls over the whole primary horizon (window_frac 5) changed almost nothing
   (type 16 in-family 8.81; type 24 1.01) at 4x the fit time.
2. READ-IN: v1 projected every intervention through the ridge PROBE x -> s (K = P + a kick correction; currents / silence / param had
   no correction), i.e. a CORRELATIONAL map. The generator's own truth says interventions reach z only through the core units
   (kick: dz = L[:, i] delta; current: dz/dt += L[:, i] I / tau_c), while follower / relay units encode z without driving it: the probe
   gives them large read-ins, so the learner predicted large effects of interventions that have none, and could not tell units with
   similar probe columns apart.
3. PER-TRAJECTORY PARAMETER DRAWS: nearly every trajectory has its own draw (504 training rows, 304 distinct draws; every test item its
   own). On type 24 (a linear latent SSM) the true z dynamics are EXACTLY linear within a trajectory (median R^2 = 1.0 of a per-trajectory
   linear fit) but only 73 % linear pooled over trajectories (frequency, damping, time constant and input gain are drawn per trajectory).
   So z is closed only GIVEN the draw; late parts of an effect (the phase of an oscillation after two cycles) are not predictable from z
   alone. An oracle that appended the TRUE draw parameters to z did not fix the v1-structured learner (EE_cb 3.8), and giving the compact
   states causal traces (evolving or frozen at the onset) or an in-context ridge correction fitted on the item's history made 250-step
   rollouts diverge (base drift up to 54 state sd).

## 3. Design v2 (refs.py docstring; LearnerConfig defaults)

- KICK READ-IN learned from the training kicks against their twins around a structural prior: identity for the observed microstate
  (FULL-STATE), ZERO for a compact state (never the correlational probe).
- CHANNELS act CONTROL-AFFINELY: ds / d_sd = f0([s, u]) + R . (A / scale), with a learned per-(unit, channel) read-in R (d_dyn x N x 7;
  FULL-STATE: each unit on its own coordinate), fitted in closed form (ridge on the one-step residuals of every row with an active
  descriptor) after the one-step phase, then refined jointly with f0. Linear in the descriptors: magnitudes outside the training
  range extrapolate linearly (exact for currents on the generator's core units). One-step phase (`one_step_mode = "auto"`, sections
  11 and 13): for a COMPACT state, f0 first on the rows WITHOUT an active channel, then the closed-form R, then f0 continued on all
  rows with R fixed ("two_stage"; fitted jointly, f0 absorbed part of the channel effects and biased R low); FULL-STATE keeps the
  joint fit ("joint"): better on each of 4 old-tier dev systems, and on the median of the 46 interim systems (sections 13 and 14).
- ABSTENTION: an event on a unit never intervened in training with that kind (for a compact state, a kick on a unit never kicked)
  has no learned read-in: `covers()` is False and `intervention_effect` abstains (kinds never trained stay unsupported as before).
  The calibration's item set uses it (`calibrate.supported_items`).
- PAIRED multi-step phase: an intervention record and its twin unrolled together from the same state (at most one short horizon
  before the onset) THROUGH the whole PRIMARY horizon after the onset (candidate C3, section 4; full post-onset coverage per pair,
  section 12); loss = both trajectory errors + the EFFECT error in units of the typical training effect.
- EFFECT CALIBRATION beta(tau) in [0, 1] per horizon (least squares of the predicted against the true readout effect on 48 training
  pairs, predicted from the true state at the onset, over the long horizon; smoothed), applied in `intervention_effect`: the
  least-squares shrinkage of late, draw-dependent parts of an effect towards 0 instead of a coherent, wrongly timed prediction.
- float64 training; compact states WITHOUT traces (they destabilised rollouts); FULL-STATE keeps its evolving traces.
- STATIC CONTEXT (section 10): TRUE-STATE / OBS-SHORTCUT encode [z, the trajectory's effective draw parameters]; the draw has zero
  dynamics, is an input of f0 and of the readout, and scales every channel effect per latent coordinate (max(0, 1 + W c)).

## 4. Candidate comparison on the whole dev suite

RULE, stated before any whole-suite result was read: candidates are ranked by (1) the median, over the 46 compressible dev systems, of
TRUE-STATE's class-balanced EE at the primary horizon on ONE COMMON item set (the verdict items whose every event targets units
intervened in training with that kind: `refs_validate.covered`); ties (difference < 0.05) are broken by (2) the median in-family EE,
then (3) the share of systems with EE_cb < 1, then (4) the median TRUE-STATE fit seconds. Candidates: C0 = v1; C1 = v2 with paired
windows of one short horizon; C2 = C1 without the effect calibration; C3 = C1 with paired windows over the whole primary horizon. C4
(C1 with twice the training steps) was added after the first (model-coverage) C1 run had been read, and is judged by the same rule.

Results (46 compressible dev systems; the common item set is identical for every candidate on all 46 systems; EE at the primary
horizon; TRUE-STATE fit seconds on Modal eval_s, 4 torch threads):

| candidate | systems | TRUE-STATE median EE_cb | median in-family EE | share EE_cb < 1 | share in-family < 0.5 | FULL-STATE median EE_cb | median TRUE-STATE fit s |
|---|---|---|---|---|---|---|---|
| C0_v1 | 46 | 1.714 | 0.980 | 0.30 | 0.24 | 1.528 | 38 |
| C1_v2 | 46 | 0.816 | 0.662 | 0.72 | 0.39 | 0.958 | 86 |
| C2_noshrink | 46 | 1.484 | 1.191 | 0.35 | 0.33 | 1.435 | 82 |
| C3_longwin | 46 | 0.671 | 0.444 | 0.76 | 0.52 | 0.937 | 258 |
| C4_budget2 | 46 | 0.784 | 0.635 | 0.70 | 0.41 | 0.961 | 159 |

Decision by the rule: C3 has the lowest median class-balanced EE (0.671; C4 0.784, C1 0.816, margins > 0.05), so C3 is adopted as
the default (`LearnerConfig.window_frac = 5.0`: paired windows over the whole primary horizon). C4 (twice the one-step, paired and
readout steps) ties C1 within the 0.05 band on (1) to (3) and loses on fit time; C2 (no effect calibration) shows that the calibration
is essential (0.816 -> 1.484). An earlier run of C1 on the v2 model's OWN coverage rule (4 more excluded items on 5 of 46 systems) gave
0.803 / 0.662 / 0.72: the two coverage rules agree.

## 5. The adopted learner (C3) per system

EE_cb = class-balanced EE at the primary horizon on the common item set (in parentheses: EE of the in-family items; NO-EFFECT's
in-family EE is about 1 by construction). OBS-SHORTCUT exists on the 12 trap systems only.

| system | type | k | items | NO-EFFECT | TRUE-STATE (in-family) | FULL-STATE (in-family) | OBS-SHORTCUT (in-family) | ID-SHORTCUT | fit s TRUE / FULL |
|---|---|---|---|---|---|---|---|---|---|
| syn-4fdc0d11d76a | 1 | 3 | 112 | 0.75 | 0.22 (0.39) | 0.89 (0.79) | - | 1.87 | 346.9 / 488.0 |
| syn-89acd7979c55 | 1 | 4 | 70 | 0.64 | 2.31 (2.81) | 2.44 (0.72) | - | 4.65 | 263.6 / 572.4 |
| syn-56297a6b5d33 | 2 | 2 | 111 | 0.99 | 0.87 (0.63) | 1.16 (1.03) | - | 2.37 | 227.8 / 437.6 |
| syn-f14087f695a5 | 2 | 2 | 128 | 1.00 | 1.38 (0.67) | 0.99 (1.00) | - | 1.16 | 253.4 / 460.2 |
| syn-8240207eb868 | 3 | 1 | 85 | 1.00 | 0.22 (0.34) | 0.70 (0.56) | - | 0.78 | 216.1 / 377.1 |
| syn-eff5937fabc3 | 3 | 2 | 109 | 0.99 | 0.41 (0.12) | 0.94 (1.38) | - | 1.08 | 253.0 / 463.6 |
| syn-9901c59557ef | 4 | 2 | 102 | 0.76 | 0.31 (0.25) | 0.65 (0.67) | - | 1.38 | 221.8 / 394.9 |
| syn-d2ddd11a0989 | 4 | 1 | 130 | 1.00 | 0.05 (0.03) | 0.89 (0.71) | - | 1.53 | 228.6 / 475.3 |
| syn-2b62d286546b | 5 | 3 | 115 | 0.98 | 0.48 (0.00) | 0.91 (1.85) | - | 0.90 | 245.1 / 393.6 |
| syn-949c3a599225 | 5 | 3 | 86 | 0.68 | 0.38 (0.56) | 0.63 (0.90) | - | 1.06 | 292.4 / 561.0 |
| syn-09a260ad2d4f | 6 | 2 | 111 | 0.95 | 0.64 (0.33) | 0.91 (1.39) | 0.62 (0.31) | 1.04 | 215.3 / 404.5 |
| syn-cd37364dea8b | 6 | 1 | 93 | 0.99 | 0.21 (0.22) | 0.44 (0.27) | - | 1.86 | 203.8 / 378.6 |
| syn-0e249728b7aa | 7 | 3 | 81 | 0.61 | 0.74 (1.49) | 1.60 (2.67) | - | 1.36 | 299.5 / 568.7 |
| syn-7d09cae2ea50 | 7 | 3 | 101 | 0.50 | 0.73 (0.65) | 1.04 (0.13) | - | 0.73 | 219.4 / 407.2 |
| syn-6eee8fe42700 | 8 | 2 | 132 | 1.00 | 0.70 (0.63) | 1.00 (1.00) | - | 0.84 | 258.7 / 465.5 |
| syn-dcd0b96fd1ee | 8 | 3 | 126 | 0.99 | 0.75 (1.06) | 1.00 (0.92) | 0.76 (0.65) | 1.00 | 284.1 / 546.2 |
| syn-183f27c93806 | 9 | 2 | 106 | 0.99 | 0.29 (0.21) | 0.87 (1.00) | 0.38 (0.39) | 0.89 | 224.2 / 434.0 |
| syn-fe0ec2cffb3d | 9 | 2 | 125 | 0.88 | 0.33 (0.07) | 0.91 (0.79) | - | 1.77 | 246.3 / 456.5 |
| syn-53e1765449ad | 10 | 3 | 109 | 0.99 | 0.89 (0.39) | 0.96 (0.96) | - | 0.76 | 246.0 / 432.4 |
| syn-d1c07b482d5b | 10 | 3 | 127 | 0.82 | 0.54 (0.76) | 0.83 (0.99) | - | 1.96 | 221.7 / 464.3 |
| syn-7a6c6c9d4137 | 11 | 2 | 124 | 1.00 | 1.04 (0.82) | 2.12 (4.22) | - | 1.21 | 258.5 / 508.5 |
| syn-fec7488cfd40 | 11 | 2 | 119 | 0.88 | 0.86 (0.60) | 1.03 (0.99) | - | 1.29 | 271.1 / 515.5 |
| syn-09b5deb51506 | 12 | 3 | 86 | 0.94 | 0.87 (1.43) | 0.94 (0.96) | - | 1.58 | 234.2 / 467.6 |
| syn-685ac0b02ef6 | 12 | 3 | 108 | 0.99 | 0.87 (0.81) | 0.98 (0.93) | - | 1.13 | 268.0 / 599.5 |
| syn-69a0e7a4ffef | 13 | 4 | 40 | 0.94 | 1.05 (0.85) | 0.95 (0.97) | - | 1.42 | 309.7 / 733.4 |
| syn-835b33247dbc | 13 | 2 | 106 | 0.88 | 1.36 (0.99) | 0.85 (0.87) | - | 4.41 | 264.2 / 506.8 |
| syn-9a9725d91b2b | 14 | 2 | 76 | 0.22 | 1.76 (3.91) | 0.69 (0.16) | - | 5.43 | 260.5 / 506.8 |
| syn-d7daf1720b88 | 14 | 1 | 71 | 0.18 | 0.11 (0.02) | 0.73 (0.45) | - | 2.09 | 214.3 / 570.4 |
| syn-9461633d1d73 | 15 | 2 | 89 | 0.90 | 0.17 (0.27) | 0.81 (0.98) | 0.24 (0.77) | 1.19 | 258.1 / 481.8 |
| syn-d0f603102633 | 15 | 2 | 110 | 0.98 | 0.28 (0.09) | 0.91 (0.72) | 0.38 (0.31) | 1.35 | 211.6 / 358.9 |
| syn-4dbd7abc4a80 | 16 | 2 | 97 | 0.68 | 0.43 (0.06) | 0.74 (0.50) | 0.75 (0.02) | 1.30 | 221.9 / 404.2 |
| syn-f87d2a3d8d10 | 16 | 3 | 114 | 1.00 | 1.07 (1.01) | 0.99 (1.00) | - | 1.61 | 226.0 / 428.1 |
| syn-96677e4dd643 | 17 | 2 | 90 | 0.92 | 0.77 (0.76) | 0.99 (1.42) | - | 1.45 | 260.2 / 496.1 |
| syn-c1d0914d0d85 | 17 | 2 | 130 | 0.97 | 1.01 (1.06) | 0.96 (0.96) | - | 1.19 | 259.3 / 459.2 |
| syn-04c74abe0096 | 18 | 2 | 108 | 0.97 | 0.70 (0.48) | 1.58 (1.01) | - | 1.37 | 212.4 / 396.5 |
| syn-526e042dee71 | 18 | 2 | 87 | 0.64 | 3.26 (9.55) | 1.97 (2.69) | - | 3.26 | 269.0 / 508.6 |
| syn-5f246af5e17f | 19 | 2 | 119 | 0.99 | 0.35 (0.13) | 0.70 (0.97) | - | 1.42 | 343.8 / 748.0 |
| syn-ce196ceecb49 | 19 | 4 | 58 | 0.74 | 1.64 (0.05) | 0.77 (0.11) | - | 1.17 | 309.5 / 717.4 |
| syn-37cd2a8ac958 | 22 | 2 | 101 | 0.99 | 0.40 (0.35) | 0.97 (0.89) | 0.23 (0.24) | 1.44 | 275.2 / 517.4 |
| syn-9daf7e1c62d9 | 22 | 2 | 81 | 0.97 | 0.39 (0.51) | 0.88 (1.13) | 0.38 (0.23) | 1.24 | 233.0 / 441.9 |
| syn-1bc959e4a710 | 23 | 3 | 106 | 1.00 | 0.64 (0.41) | 0.92 (1.05) | 0.59 (0.07) | 1.51 | 275.6 / 516.8 |
| syn-3e88ebab5419 | 23 | 2 | 110 | 0.80 | 0.43 (0.33) | 0.92 (0.90) | 0.82 (0.81) | 0.95 | 290.9 / 580.8 |
| syn-00e48aa6ad4d | 24 | 3 | 77 | 0.98 | 0.62 (0.38) | 1.25 (1.08) | - | 1.22 | 270.4 / 512.5 |
| syn-2e2d802cc736 | 24 | 3 | 71 | 0.99 | 0.64 (1.19) | 1.09 (0.99) | - | 1.69 | 263.5 / 520.2 |
| syn-2a013a2e85c0 | 25 | 3 | 108 | 0.94 | 0.72 (0.28) | 0.95 (0.57) | 1.00 (1.13) | 1.83 | 225.4 / 396.9 |
| syn-5a6cb6d3bdb4 | 25 | 3 | 117 | 1.00 | 1.35 (0.13) | 0.96 (0.76) | 0.94 (0.16) | 0.88 | 261.9 / 532.3 |
| MEDIAN | | | | 0.97 | 0.67 (0.44) | 0.94 (0.96) | 0.61 (0.31; n = 12) | 1.35 | |


Breakdowns (C3, medians over systems): TRUE-STATE by magnitude class weak 0.41, moderate 0.47, strong 0.59, na 0.65, hi 0.69; by
shift in-family 0.44, near 0.58, hidden-only 0.58, target 0.42 (7 systems have covered target-shift items); short-horizon EE 0.52,
long-horizon 0.84. Effect-calibration factors beta (median): 0.97 at one short horizon, 0.82 at the primary horizon, 0.57 at twice
it, 0.22 at the long horizon (C1: 0.89 / 0.27 / 0.11 / 0.01: training over the whole primary horizon made the late parts of the
predicted effects far more reliable).

## 6. Acceptance against the task's criteria

- TRUE-STATE beats NO-EFFECT (EE_cb < 1) on 76 % of the compressible dev systems (35 of 46; v1: 30 %); median EE_cb 0.67.
- In-family EE: median 0.44, below 0.5 on 52 % of the systems and below 1 on most (v1: median 0.98).
- OBS-SHORTCUT vs TRUE-STATE on the items of the EXPOSING families (trained and covered on all 12 trap systems, 80-110 items each):
  TRUE-STATE better (by > 0.05) on 7 of 12, OBS-SHORTCUT better on 5 of 12 (types 6, 9, 22, 22, 23). The generic learner does not
  reliably exploit the true state's extra coordinates under the exposing interventions at the primary horizon; the power rule's
  mediation / closure criteria (D, E) may still separate them, which the calibration measures.
- FULL-STATE is a WEAK predictability anchor with this learner (median EE_cb 0.94, in-family 0.96): the full observed microstate plus
  traces, with per-unit read-ins on each unit's own coordinate only, predicts little of the effects' propagation through the
  network. The verdict's full-state bound is the better of this reference and the best full-state BASELINE (fixed at Level B), so a
  stronger baseline built in the clean room raises the bar.

## 7. Observations for the orchestrator (not changed here)

1. PER-TRAJECTORY PARAMETER DRAWS: the generator's true causal state z is closed only GIVEN the trajectory's parameter draw (type 24:
   R^2 = 1.0 within trajectories, 0.73 pooled). The references do not receive the draw, so the calibration measures a correct state
   with a draw-agnostic generic learner. A method can identify the draw in context from the history, but only with extra (static)
   latent coordinates, which conflicts with scoring k = k_true (5.16) and with selection criterion (4) (compression incl. k = k_true).
2. ID-SHORTCUT is worse than NO-EFFECT (median EE_cb 1.35; hidden-only families 2.86): criterion B compares a method with the better
   of this reference and the best ID baseline (fixed at Level B), so B is weak unless a stronger ID baseline is built.
3. The remaining TRUE-STATE error is present at the short horizon already (median 0.52), i.e. in the immediate response (per-draw
   input gains; state-dependent descriptors decoded linearly from z), not only in propagation.
4. Metric: no sign that floor-level items drive the remaining error (TRUE-STATE's weak magnitude class has the LOWEST median EE,
   0.41). Items whose true effect is below the detection floor still penalise any non-abstaining predictor through the floor-based
   denominator; the effect calibration keeps the reference's spurious effects small there.
5. Explicit-state initial conditions (obs.init) in today's D0 were not used to tune anything (coordinator note); the redesign's
   choices were made on the diagnosis systems and the stated whole-suite rule.

## 8. Compute

- Fit times of the C3 learner (46 dev systems, Modal eval_s, 4 threads): TRUE-STATE median 258 s (max 347), FULL-STATE 479 s (max
  748), OBS-SHORTCUT 207 s.
- With the section-12 windows and the default one-step modes (4 dev systems, section 13; medians, the host type varies): TRUE-STATE
  378 s (two_stage; 326-385 s), FULL-STATE 681 s (joint; 670-858 s), OBS-SHORTCUT 287 s. The calibration fits TRUE-STATE, FULL-STATE,
  RANDOM-k, PCA-k, OBS-SHORTCUT (trap types) and the missing-coordinate corruption per system: about 40 min of fitting per system on
  eval_s, twice the ~20 min guideline. Run the calibration on eval_l, or fit the references of a system in separate jobs (they are
  independent of each other).
- On the interim tier (section 14; three references per job): TRUE-STATE 328 s (max 410), FULL-STATE 606 s (max 836).
- Modal runs (list-price estimates; research/phase4/MODAL_RUNS.md E13-1 to E13-19):
  - whole-suite validation runs: C1 (model-coverage variant) $3.36, C0 $2.81, C2 $2.76, C1 $2.92, C4 $4.36, C3 $5.62;
  - two duplicate launches stopped early (about $1-2), and the failed C5 whole-suite run $0.04;
  - the 4-system runs: C5 $0.67, C6 $0.65, C7 $0.67;
  - two sharded test runs: about $0.5 and $0.7;
  - the interim tier: overview $0.03, a failed single-client run (about $6), a failed eager relaunch (about $1-2), and the run of
    section 14 ($14.0);
  - downloads and the scratch upload: cents.
  About $48 in total.

## 9. Files

- `phase4/src/brainir_causal/refs.py`: learner v2 (LearnerConfig, `_LearnedStateModel`, `TruthStateModel` history / payload, prefix
  lookup in `HistoryIndex`, `ReadinGainModel.intervention_effect` / `covers` delegate to the base); the static context and [z, draw]
  (section 10: `_static_raw`, `_setup_static`, `_static_of`, `_fit_context_gain_ls`, `TruthStateModel(use_draw=True)`, the
  `true_state_zonly` / `obs_shortcut_zonly` references); the one-step modes (section 11: `one_step_mode`, `_train_one_step(readin=
  'train' | 'none' | 'fixed')`); the paired windows (section 12: `_paired_lengths`, masked paired loss); module docstring. It imports
  only room modules (families, protocol, accounting, api) and never writes its inputs (a test checks it).
- `phase4/src/brainir_causal/harness.py`: `register_heldout` (held-out truth, draws and readouts registered before the references are
  evaluated in `reference_results`); `training_truth` returns the training draws.
- `phase4/src/brainir_causal/calibrate.py`: `supported_items` (the items must also be covered: `refs.*.covers`) and the truth-loading
  lines of section 10 (the draw next to z / z_obs in `calibrate_system`, `registrations()`, `calibrate_from_inputs` and
  `reference_breakdown`).
- `phase4/src/brainir_causal/refs_validate.py` (new, orchestrator side, not a clean-room module): the dev-suite validation (the
  common item set, the draws, the variant check).
- Tests: `phase4/tests/test_refs_models.py` (abstention on units never intervened, calibration factors in [0, 1], read-in corruption
  through the base prediction, the paired windows cover the whole horizon after the onset, the references never write their inputs;
  the FULL-STATE kick read-in assertion relaxed to the learned read-in); `phase4/tests/test_refs_draw.py` (new: the draw floor, zero
  dynamics and k, the fallback and registrations); `phase4/tests/test_calibrate_pipeline.py` (the supported-item count follows the
  coverage rule).

## 10. The complete reference state [z, draw] (review E round 3, N-new-1; LOG P4-D43)

Reviewer E measured that z alone leaves 43-63 % of the readout effect undetermined on 6 of 23 compressible types (at equal z and equal
kick across 8 parameter draws; median 0.076): every trajectory has its own draw and z is closed only given it, so a z-only reference
has an error floor that no learner can remove and that loosens every tolerance built from it. Decision (coordinator): TRUE-STATE and
OBS-SHORTCUT encode [z, draw], draw = the trajectory's effective draw parameters from the truth store (`draw_effective`, written by
`suites.SimContext.run` as truth["draw"] for every record once the revised generator provides it).

Implementation (`refs.py`):
- a generic STATIC CONTEXT in the shared learner: one vector per training record (`_static_raw`), constant along the trajectory;
  coordinates constant over the training records are dropped (recorded); the rest are appended to the state after the dynamic part
  and the traces: state = [s_dyn, traces, context];
- ZERO DYNAMICS: rollouts carry the context unchanged; no intervention moves it (kick read-in, lift predictions and read_in are zero
  on it; a requested latent shift along it is part of a lift's miss);
- the context is an INPUT of the passive field f0 and of the readout (`context_linear=False`; the first-order form f = F0 + sum_j c_j
  F_j is the ablation) and scales every channel effect per latent coordinate, max(0, 1 + W c_norm) * (R . A) (`context_gain`; W fitted
  in closed form with R, alternating 3 times, then refined in the paired phase);
- `TruthStateModel(which, use_draw=True)`: `fit_truth(..., draw_by_key)`, `register_truth(x, u, z, dt, draw)`,
  `register_records(..., draw_by_key)`; a history registered WITHOUT a draw, and every unregistered history (probe fallback), gets
  the training-mean draw (counted: `info()['n_registered_without_draw']`, `n_probe_encodes`);
- FALLBACK: without a draw for every training record the state is z alone, `fit_notes['static_context']` says why and
  `info()['draw_context']` is False; `fit_reference('true_state_zonly' | 'obs_shortcut_zonly')` gives the descriptive z-only
  references (reviewer E: "keep the z-only model as a separate, descriptive reference");
- k = the dimension of the encoding, including the context (a method carrying draw coordinates counts them too); `info()` also
  reports `k_dynamic` and `k_context`. CONSEQUENCE for criterion F (compactness k <= max(1, N_obs // 5)): on the current dev tier two
  compressible systems have N_obs = 4-5 and k_true = 1 (limit 1), so TRUE-STATE with any draw coordinate is NOT compact there; every
  other compressible system has a slack of at least 7 coordinates (the per-type latent parameters number 3-9). Whether the reference's
  compactness is judged on `k` or on `k_dynamic` is the calibration's decision (calibrate.py uses `info()['k']`).

Plumbing (truth loading only): `harness.training_truth` returns "draw", `harness.register_heldout` passes each held-out record's draw;
calibrate.py: `calibrate_system` collects the training draws into truth["draw"] and yields each held-out record's "draw" and "dt"
in `registrations()`, `calibrate_from_inputs` passes them to `register_truth`, `reference_breakdown` does the same (lines listed in
the report to the coordinator). Callers that do not pass a draw yet: `active_mde.py` (two `register_truth` calls) and
`evaluate_lift.py` (the joined lift histories); they get the training-mean draw.

Evidence (toy: `phase4/tests/test_refs_draw.py`, the linear toy of the reference tests whose every trajectory has its own ARTIFICIAL
draw: latent speed w, readout gain gy and current gain gi, log factors with sd 0.35; 20 passive + 64 intervention trajectories with
their twins; test: 30 new intervention pairs with new draws; pooled relative effect error):

| reference | horizon 25 samples | 100 samples (1 s) | kicks (100) | currents (100) | beta at the long horizon |
|---|---|---|---|---|---|
| z alone (`true_state_zonly`) | 0.20 | 0.39 | 0.39 | 0.39 | 0.47 |
| [z, draw], default (context input + context gain) | 0.004 | 0.011 | 0.012 | 0.004 | 0.95 |
| [z, draw], context linear (first order) + gain | 0.028 | 0.036 | 0.038 | 0.019 | |
| [z, draw], context linear, no gain | 0.035 | 0.046 | 0.041 | 0.080 | |

With the final one-step mode of section 11 (two_stage for a compact state), the same toy gives z alone 0.21 / 0.46 / 0.44 / 0.61 and
[z, draw] 0.004 / 0.011 / 0.012 / 0.004 (horizon 25, 1 s, kicks, currents). The floor of the z-only reference disappears with the
draw (0.39 -> 0.011 at 1 s); the context gain matters for currents (0.080 ->
0.019 in the linear form; its learned coefficient on the current-gain coordinate is 0.34-0.39 in normalised units, the truth about
0.35). The slow test asserts e([z, draw]) < 0.4 e(z) and e(z) > 0.1; fast tests check zero dynamics, k, the context bookkeeping, the
registration without a draw and the z-only fallback.

## 11. Passive field fitted on channel-free rows (a bias found while testing section 10)

With the draw, the learned current read-in of the toy was 30-50 % too small (per unit: 0.50-0.90 of the truth) and current items kept
an effect error of about 0.3. Cause: the one-step phase fitted f0 JOINTLY with R on all rows, including the rows where a channel acts;
a context that differs between trajectories lets f0 separate a pulse trajectory from passive trajectories visiting the same region of
the state space and absorb part of its current effect, and the closed-form read-in fitted afterwards on the residual then comes out
small. Fix (first form, now `one_step_mode = "passive"`): the one-step phase fits f0 on the rows WITHOUT an active channel only
(passive rows, kick rows, the rows after interventions); R is then fitted in closed form on the channel rows. On the toy the read-in is now
0.96-1.06 of the truth. The fix also helps WITHOUT a draw: on the plain toy (no draw) current items improved from 0.039 to 0.001
(horizon 25) and from 0.10 to 0.008 (horizon 100), kicks from 0.023 to 0.004 (horizon 100).

On real dev systems, however, the "passive" mode was worse (section 13): f0 is then never fitted on the states that long channel
windows produce (sustained currents, connection scaling, silencing), and the linear channel term alone does not carry them. Hence a
third mode, `one_step_mode = "two_stage"`: f0 on the channel-free rows, the closed-form read-in, then f0 continued on ALL rows for half
the one-step steps with the read-in (and the context gain) FIXED, so f0 learns only what the read-in leaves.

RULE for the one-step mode, stated before the joint and two-stage dev runs were read (the passive run had been read): a mode is
eligible only if it passes the toy gates (draw toy: per-unit current read-in within [0.9, 1.1] of the truth; [z, draw] effect error
below 0.4 x the z-only error); among eligible modes the lowest mean TRUE-STATE class-balanced EE over the 4 dev systems of section 13
wins, ties (difference < 0.05) by the mean FULL-STATE class-balanced EE, then by fit time.

| mode (all with the section-12 windows) | draw toy: current read-in / truth | draw toy [z, draw] 1 s | plain toy currents 1 s |
|---|---|---|---|
| joint | 0.48-0.90 (FAILS the gate) | 0.076 | 0.101 |
| passive | 0.96-1.06 | 0.011 | 0.008 |
| two_stage | 0.96-1.06 | 0.011 | 0.010 |

FULL-STATE on the plain toy, measured after C6 and C7 had been read. The plain toy is an exact microstate: x = M s with M invertible,
a kick moves x by its delta, and a current into unit k acts on x_k alone, so FULL-STATE's per-unit read-in on each unit's own
coordinate is structurally exact there (the truth is 1 per unit):

| mode | FULL-STATE current read-in / truth | effect error 25 samples | 1 s | kicks 1 s | currents 1 s |
|---|---|---|---|---|---|
| joint | 0.21-0.83 | 0.030 | 0.156 | 0.137 | 0.361 |
| passive | 0.98-1.00 | 0.003 | 0.009 | 0.009 | 0.010 |
| two_stage | 0.98-1.00 | 0.003 | 0.007 | 0.006 | 0.018 |

OUTCOME OF THE RULE. joint is ineligible (toy gate). passive and two_stage tie on TRUE-STATE (mean 0.711 vs 0.666 over the 4 dev
systems of section 13; difference 0.045 < 0.05). The FULL-STATE tie-break selects two_stage (1.485 vs 1.529). So the rule selects
two_stage as the one mode for every reference.

DEVIATION, decided after C6 and C7 had been read (post hoc): the default is `one_step_mode = "auto"`, which is two_stage for every
compact state (TRUE-STATE, OBS-SHORTCUT, PCA-k, RANDOM-k, the corruptions; the rule's outcome) and joint for FULL-STATE. Reasons:
- With two_stage, FULL-STATE is worse than NO-EFFECT on all 4 dev systems (mean 1.485 against NO-EFFECT's 0.896; passive 1.529).
- With joint, FULL-STATE is better than with either of them on each of the 4 systems (mean 0.953; section 13), though still no
  better than NO-EFFECT on 3 of the 4. On the 46 systems of the interim tier (section 14, read after this decision): median 1.05
  against 1.15, per system 20 against 17; FULL-STATE is no better than NO-EFFECT on 34 of 46 in both modes.
- A weaker FULL-STATE loosens criterion C: delta_C moves towards its floor, and the bound becomes one that more methods meet
  trivially. It also makes goal5 section 94's "full state fails" diagnosis more likely, for a reason that lies in the learner.
The toy argues the other way for FULL-STATE (the table above). On an exact microstate the per-unit read-in is right, and joint biases
it as it does for a compact state. On the generator's systems the per-unit read-in is misspecified (section 13, finding 4). So the
better mode for FULL-STATE depends on the system kind.

`one_step_mode = "two_stage"` restores the rule's outcome in one field. PROPOSAL for the coordinator: fix FULL-STATE's one-step mode
per system kind (synthetic, real) at Level B together with the full-state bound. FULL-STATE (joint) and FULL-STATE (two_stage) would
then both be candidates of the bound's choice (PROTOCOL section 8: the lowest median verdict EE over the Level B validation systems of
the kind). Either way, the mode should be checked on the real public data before the freeze.

## 12. Paired windows cover the whole horizon after the onset (reviewer H round 3, NEW-2)

Each paired window starts st = j0 - U{0..pre} (pre = one short horizon) and previously ran L = min(m, ...) steps, so it covered only
m - (j0 - st) steps after the onset (0.8 m to m, mean 0.9 m): the last part of the scored window was never trained in paired mode for
some draws. Now every pair runs L_i = min(m + (j0 - st), n_i - 1 - st) steps (`_LearnedStateModel._paired_lengths`): m steps after
the onset, clipped only at the trajectory's end; a pair whose window is over is frozen and masked while the rest of the batch
continues, and the loss is the mean over the unrolled (pair, step) cells. `fit_notes['paired_post_onset']` records the minimum
post-onset coverage of the sampled long-enough pairs (= m) and the number of clipped short pairs; a test asserts both the rule and
the fit note.

## 13. Re-validation on 4 dev systems (the one-step modes and the section-12 windows)

TIER AND DATA. The dev tier as it was built BEFORE today's round-2 rebuild: the eval and truth parts of 4 systems copied at 00:05Z
(E13-1), before the eval volume lost the dev eval part at about 07:13Z (the whole-suite run E13-9 failed on it); the copy was put on a
scratch path of the eval volume (E13-10); the public D0 + D1 parts were read from the fit volume, and every job had loaded them by
about 10:22Z, before the rebuild began. NO-EFFECT and ID-SHORTCUT, which do not depend on the one-step mode, give identical numbers in
every run, so all runs saw the same data. That build writes NO draw (its truth holds z and z_obs only), so these runs exercise the
z-only fallback of section 10 (`draw_context` False). The [z, draw] design is validated on the toy only (section 10). On generator
systems it needs a tier whose truth carries `draw`. Neither this build nor the interim round-2 build (section 14) has one: their
generator has no `draw_effective` yet, and `suites.SimContext.run` writes truth["draw"] only when it has.

Systems: syn-00e48aa6ad4d (type 24, k 3, 77 items), syn-2b62d286546b (type 5, k 3, 115), syn-4dbd7abc4a80 (type 16, k 2, 97; a trap
type, so OBS-SHORTCUT exists), syn-69a0e7a4ffef (type 13, k 4, 40). Common item set of section 4; class-balanced EE at the primary
horizon; fit seconds on eval_s (4 threads; the host type varies).

| run | one-step mode | paired windows | TRUE-STATE EE_cb (types 24 / 5 / 16 / 13) | mean | FULL-STATE EE_cb | mean | OBS-SHORTCUT (16) | median fit s TRUE / FULL |
|---|---|---|---|---|---|---|---|---|
| C3 (section 5) | joint | before section 12 | 0.62 / 0.48 / 0.43 / 1.05 | 0.647 | 1.25 / 0.91 / 0.74 / 0.95 | 0.962 | 0.75 | 258 / 458 |
| C5 | passive | section 12 | 0.47 / 0.54 / 0.85 / 0.99 | 0.711 | 1.48 / 0.95 / 2.59 / 1.10 | 1.529 | 0.76 | 323 / 796 |
| C6 | joint | section 12 | 0.61 / 0.45 / 0.44 / 1.08 | 0.645 | 1.22 / 0.91 / 0.72 / 0.96 | 0.953 | 0.75 | 356 / 681 |
| C7 | two_stage | section 12 | 0.51 / 0.54 / 0.66 / 0.95 | 0.666 | 1.70 / 1.14 / 2.08 / 1.02 | 1.485 | 0.75 | 378 / 741 |
| default ("auto") | compact: two_stage; FULL-STATE: joint | section 12 | = C7 | 0.666 | = C6 | 0.953 | 0.75 | 378 / 681 |

NO-EFFECT 0.98 / 0.98 / 0.68 / 0.94 (mean 0.896) and ID-SHORTCUT 1.22 / 0.90 / 1.30 / 1.42 in every run. In-family EE of TRUE-STATE:
C7 0.43 / 0.00 / 0.03 / 0.87, C6 0.38 / 0.00 / 0.06 / 0.86. The default row is not a separate run: the references are fitted
independently, with the same seeds and code path as in C7 (compact states) and C6 (FULL-STATE).

Findings.
1. The section-12 windows change little at equal mode (C3 -> C6: TRUE-STATE 0.647 -> 0.645, FULL-STATE 0.962 -> 0.953) and cost about
   40 % more TRUE-STATE fit time (different runs; the host types vary).
2. TRUE-STATE: joint and two_stage tie on the mean (0.645 and 0.666; passive 0.711), with differences in both directions per system
   (type 16 prefers joint: 0.44 vs 0.66, close to NO-EFFECT's 0.68; types 24 and 13 prefer two_stage). joint fails the toy's read-in
   gate (section 11).
3. FULL-STATE: joint is better than two_stage and passive on EACH of the 4 systems (mean 0.953 vs 1.485 / 1.529). With two_stage,
   FULL-STATE is worse than NO-EFFECT on all 4 (passive: 3 of 4); with joint it is still no better than NO-EFFECT on 3 of 4, by
   0.02-0.24 (FULL-STATE is a weak anchor in every mode; section 6).
4. The effect is the opposite on the plain toy, an exact microstate (section 11: two_stage 0.007 at 1 s, joint 0.156; read-in 0.98-1.00
   vs 0.21-0.83 of the truth). The generator's observed units are driven by the latent state (interventions reach z through the core
   units, section 2), so the per-unit read-in on each unit's own coordinate cannot represent a channel's effect on the other observed
   units; the joint fit lets f0 carry what R cannot. The real systems (connectome rate models: the observed units are part of the
   microstate, apart from the unobserved ones) are closer to the toy, so there two_stage may be the better FULL-STATE; not checked here.

Decision (see section 11 for the rule and the deviation): `one_step_mode = "auto"`.

## 14. The interim dev tier (round-2 generator): 46 compressible systems

TIER AND DATA: "interim dev (round-2 generator)", the dev tier rebuilt with the author's round-2 generator (coordinator's notice,
2026-09-27), read from the volumes (eval and truth parts from the eval volume, public D0 + D1 from the fit volume). The truth store
of this tier carries NO effective draw either (E13-16: 0 of 20 sampled trajectories on every system), so TRUE-STATE and OBS-SHORTCUT
ran as z / z_obs alone (`draw_context` False on all 46 systems). The validation builds no generator system and runs no simulation:
every number comes from the stored tier. So the BLAS-thread dependence of the system construction (P6's notice) does not enter it;
whether the stored parts were built with matching system hashes is a property of that build. Final learner (`one_step_mode =
"auto"`); FULL-STATE also fitted with the two-stage mode; common item set of section 4; class-balanced EE at the primary horizon (in
parentheses: in-family EE). Run E13-19: three jobs per system (F1 = FULL-STATE joint, ID-SHORTCUT, NO-EFFECT; F2 = FULL-STATE
two_stage; T = TRUE-STATE, OBS-SHORTCUT), with the same item set in all three.

| system | type | k | items | NO-EFFECT | TRUE-STATE (in-family) | FULL-STATE joint (in-family) | FULL-STATE two_stage (in-family) | OBS-SHORTCUT | ID-SHORTCUT |
|---|---|---|---|---|---|---|---|---|---|
| syn-4fdc0d11d76a | 1 | 3 | 116 | 0.98 | 0.31 (0.45) | 0.88 (0.79) | 1.13 (0.72) | - | 1.12 |
| syn-89acd7979c55 | 1 | 4 | 86 | 0.99 | 0.41 (0.49) | 0.99 (0.65) | 1.07 (0.69) | - | 1.35 |
| syn-56297a6b5d33 | 2 | 2 | 95 | 0.96 | 0.87 (0.49) | 0.99 (1.75) | 0.95 (0.99) | - | 1.05 |
| syn-f14087f695a5 | 2 | 2 | 112 | 0.99 | 0.47 (0.54) | 1.03 (1.53) | 1.04 (1.75) | - | 1.04 |
| syn-8240207eb868 | 3 | 1 | 82 | 0.99 | 0.21 (0.21) | 1.48 (0.55) | 1.50 (0.68) | - | 0.85 |
| syn-eff5937fabc3 | 3 | 2 | 113 | 0.99 | 0.42 (1.76) | 1.06 (3.04) | 1.35 (3.19) | - | 1.45 |
| syn-9901c59557ef | 4 | 2 | 119 | 0.77 | 0.23 (0.12) | 0.78 (0.95) | 0.62 (1.02) | - | 0.85 |
| syn-d2ddd11a0989 | 4 | 1 | 139 | 0.99 | 0.11 (0.02) | 0.91 (0.97) | 0.80 (0.70) | - | 0.90 |
| syn-2b62d286546b | 5 | 3 | 116 | 0.99 | 0.53 (0.20) | 1.18 (0.16) | 1.46 (0.33) | - | 1.25 |
| syn-949c3a599225 | 5 | 3 | 74 | 0.86 | 0.12 (0.24) | 1.32 (0.79) | 2.12 (1.13) | - | 1.25 |
| syn-09a260ad2d4f | 6 | 2 | 90 | 0.99 | 0.25 (0.07) | 0.99 (1.01) | 1.32 (1.57) | 0.44 | 1.66 |
| syn-cd37364dea8b | 6 | 1 | 82 | 1.00 | 0.05 (0.02) | 0.55 (0.39) | 0.08 (0.03) | - | 0.79 |
| syn-0e249728b7aa | 7 | 3 | 89 | 0.49 | 1.61 (0.00) | 0.72 (0.18) | 0.54 (0.17) | - | 0.79 |
| syn-7d09cae2ea50 | 7 | 3 | 113 | 0.73 | 0.70 (2.87) | 1.25 (1.07) | 1.84 (1.01) | - | 2.04 |
| syn-6eee8fe42700 | 8 | 2 | 126 | 0.98 | 0.46 (0.24) | 0.99 (0.92) | 1.31 (2.44) | - | 1.05 |
| syn-dcd0b96fd1ee | 8 | 3 | 88 | 0.94 | 0.48 (0.75) | 2.22 (2.62) | 1.83 (2.39) | 2.61 | 0.97 |
| syn-183f27c93806 | 9 | 2 | 118 | 1.00 | 0.18 (0.06) | 0.86 (0.93) | 1.43 (1.37) | 0.18 | 1.08 |
| syn-fe0ec2cffb3d | 9 | 2 | 121 | 0.99 | 0.31 (0.13) | 1.09 (0.95) | 1.11 (1.10) | - | 0.92 |
| syn-53e1765449ad | 10 | 3 | 80 | 0.99 | 1.39 (3.23) | 1.58 (5.93) | 2.54 (8.62) | - | 1.01 |
| syn-d1c07b482d5b | 10 | 3 | 96 | 0.99 | 1.08 (1.00) | 1.02 (0.97) | 1.74 (0.88) | - | 2.49 |
| syn-7a6c6c9d4137 | 11 | 2 | 135 | 0.75 | 0.57 (0.82) | 0.76 (1.00) | 1.37 (1.03) | - | 0.94 |
| syn-fec7488cfd40 | 11 | 2 | 97 | 0.99 | 0.64 (0.89) | 1.01 (0.99) | 1.20 (0.93) | - | 1.19 |
| syn-09b5deb51506 | 12 | 3 | 88 | 1.00 | 0.35 (0.53) | 1.04 (0.89) | 1.04 (0.83) | - | 1.48 |
| syn-685ac0b02ef6 | 12 | 3 | 96 | 1.00 | 0.32 (0.94) | 0.98 (1.05) | 1.06 (1.03) | - | 1.10 |
| syn-69a0e7a4ffef | 13 | 4 | 56 | 0.99 | 1.03 (0.02) | 1.08 (0.23) | 0.95 (0.15) | - | 1.05 |
| syn-835b33247dbc | 13 | 2 | 96 | 0.95 | 0.73 (0.52) | 1.79 (1.01) | 0.93 (0.99) | - | 0.94 |
| syn-9a9725d91b2b | 14 | 2 | 89 | 0.99 | 0.68 (0.30) | 1.13 (2.84) | 1.64 (1.93) | - | 0.93 |
| syn-d7daf1720b88 | 14 | 1 | 69 | 0.74 | 0.22 (0.17) | 1.62 (0.62) | 1.47 (1.01) | - | 1.63 |
| syn-9461633d1d73 | 15 | 2 | 90 | 1.00 | 0.25 (0.17) | 1.01 (0.98) | 1.05 (1.02) | 1.10 | 0.79 |
| syn-d0f603102633 | 15 | 2 | 65 | 0.96 | 1.59 (0.85) | 1.13 (1.70) | 1.34 (1.75) | 0.75 | 1.32 |
| syn-4dbd7abc4a80 | 16 | 2 | 72 | 0.96 | 0.34 (0.00) | 1.13 (2.40) | 1.02 (3.36) | 0.69 | 0.91 |
| syn-f87d2a3d8d10 | 16 | 3 | 147 | 0.98 | 0.92 (0.88) | 1.19 (1.00) | 1.30 (1.02) | - | 1.08 |
| syn-96677e4dd643 | 17 | 2 | 110 | 0.64 | 3.02 (0.57) | 1.53 (1.00) | 1.35 (0.65) | - | 1.40 |
| syn-c1d0914d0d85 | 17 | 2 | 147 | 0.93 | 0.85 (0.37) | 2.47 (1.30) | 1.02 (0.99) | - | 1.15 |
| syn-04c74abe0096 | 18 | 2 | 115 | 0.98 | 1.96 (4.29) | 1.02 (0.99) | 1.10 (1.00) | - | 1.67 |
| syn-526e042dee71 | 18 | 2 | 89 | 1.00 | 1.06 (0.75) | 0.95 (0.89) | 0.82 (0.85) | - | 1.52 |
| syn-5f246af5e17f | 19 | 2 | 112 | 0.99 | 1.06 (0.87) | 1.38 (1.12) | 1.17 (0.96) | - | 1.10 |
| syn-ce196ceecb49 | 19 | 4 | 106 | 0.99 | 0.55 (0.54) | 1.20 (1.06) | 0.90 (0.90) | - | 1.13 |
| syn-37cd2a8ac958 | 22 | 2 | 112 | 1.00 | 0.65 (0.35) | 1.28 (1.17) | 1.47 (0.52) | 0.26 | 1.05 |
| syn-9daf7e1c62d9 | 22 | 2 | 74 | 0.99 | 0.28 (0.41) | 0.90 (0.98) | 0.95 (0.74) | 0.32 | 1.01 |
| syn-1bc959e4a710 | 23 | 3 | 141 | 0.99 | 0.82 (0.97) | 2.26 (0.95) | 2.61 (0.70) | 0.75 | 1.46 |
| syn-3e88ebab5419 | 23 | 2 | 89 | 0.94 | 0.61 (5.04) | 2.34 (1.80) | 1.26 (3.19) | 0.58 | 1.57 |
| syn-00e48aa6ad4d | 24 | 3 | 89 | 0.98 | 0.37 (0.25) | 0.97 (2.20) | 0.90 (1.74) | - | 1.73 |
| syn-2e2d802cc736 | 24 | 3 | 85 | 1.00 | 0.47 (0.24) | 0.91 (0.81) | 0.90 (0.76) | - | 1.00 |
| syn-2a013a2e85c0 | 25 | 3 | 118 | 1.00 | 0.48 (0.36) | 0.71 (0.44) | 0.69 (0.32) | 0.99 | 0.89 |
| syn-5a6cb6d3bdb4 | 25 | 3 | 126 | 0.91 | 0.75 (2.93) | 2.60 (4.08) | 1.67 (3.44) | 2.23 | 1.65 |
| MEDIAN | | | | 0.99 | 0.51 (0.47) | 1.05 (0.99) | 1.15 (1.00) | 0.72 (n = 12) | 1.09 |

Summary (medians over the 46 systems):
- TRUE-STATE (z alone): 0.51, in-family 0.47. It is better than NO-EFFECT on 37 of 46 systems (80 %), and its in-family EE is below
  0.5 on 54 %. By magnitude class: weak 0.44, moderate 0.34, strong 0.45, hi 0.54, na 0.66. By shift: in-family 0.47, near 0.46,
  hidden-only 0.60.
- It is NOT better than NO-EFFECT on 9 systems (types 7, 10, 10, 13, 15, 17, 18, 18, 19). These are candidates for the draw floor of
  section 10; that cannot be checked without the draw.
- NO-EFFECT 0.99; ID-SHORTCUT 1.09; OBS-SHORTCUT 0.72 (12 trap systems).
- On the items of the exposing families, TRUE-STATE beats OBS-SHORTCUT (by more than 0.05) on 9 of the 12 trap systems. OBS-SHORTCUT
  wins on 2 (types 15 and 22), and 1 is a tie.
- FULL-STATE: joint 1.05, two_stage 1.15. Per system, joint is better (by more than 0.05) on 20, two_stage on 17, and 9 are ties.
- In BOTH modes FULL-STATE is no better than NO-EFFECT on 34 of the 46 systems. On this generator the FULL-STATE reference is not a
  useful predictability anchor in either mode. The full-state bound of the verdicts will in practice come from a full-state baseline
  at Level B, unless the reference is improved.
- Fit seconds (eval_s, 4 threads): TRUE-STATE 328 (max 410), FULL-STATE joint 606 (max 836), FULL-STATE two_stage 611 (max 834).

For the one-step mode (section 11): on this tier joint beats two_stage for FULL-STATE on the median by 0.11, but not system by system
(20 against 17). The deviation of section 11 stays, with the weaker support stated here. The old-tier contrast (0.95 against 1.49 on 4
systems) does not recur at that size.
