# Ablations of `p3stand.refstand:p3stand_ref` (val; run val1)

**DRY RUN** (val tier (Level B selection tier), stand-in models, before the lock): not a result; never released, never used for any decision.

50 systems; 46 compressible synthetic systems enter the suite statistics; tolerances PROVISIONAL (no calibration yet).

## Critical ablations

- **Q20 interventional training** (goal5 88): **FAIL**. Suite mean EE_ablated - EE_full = -0.25 (one-sided 95 % lower bound -0.398, p = 1).
- **Q21 state bottleneck** (goal5 89): **outcomes not predictable even without the bottleneck (attributed to excitation / data; goal5 section 94 B)**.

## Per switch (suite paired difference ablated - full; positive = the ablation is worse for lower-is-better metrics)

| switch | EE | EE held-out | SMS | ICG_y | MEV | lift success | false confidence | Holm p (EE) |
|---|---|---|---|---|---|---|---|---|
| interventional_training | -0.25 [-0.433, -0.107] | -0.313 [-0.536, -0.136] | -0.0379 [-0.0841, 0.0068] | 0.01 [-0.0105, 0.0357] | 0.0138 [-0.000524, 0.0421] | -0.0034 [-0.00861, -0.000453] | 0 [0, 0] | 1 |
| mediation_loss | 0.445 [0.282, 0.627] | 0.512 [0.323, 0.715] | 0.0522 [0.00555, 0.0961] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0.162 [0.113, 0.216] | 0.0035 |
| closure_loss | 0.0971 [-6.35e-05, 0.198] | 0.122 [0.0124, 0.24] | -0.0196 [-0.0522, 0.0158] | 0 [0, 0] | 0 [0, 0] | -0.000453 [-0.00113, 0] | 0.0427 [0.0215, 0.0659] | 0.156 |
| native_lift | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | -0.0034 [-0.00861, -0.000453] | 0 [0, 0] | 1 |
| multiple_lift_consistency | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | -0.00113 [-0.00272, 0] | 0 [0, 0] | 1 |
| dimension_penalty | 0.021 [-0.0699, 0.106] | 0.00729 [-0.108, 0.111] | -0.0147 [-0.0616, 0.028] | 0.00299 [-0.0111, 0.016] | -0.00581 [-0.0167, 0.000294] | 0.00136 [-0.00589, 0.00974] | 0.0354 [-0.00174, 0.0738] | 1 |
| state_bottleneck | -0.191 [-0.352, -0.0637] | -0.232 [-0.433, -0.0739] | -0.236 [-0.42, -0.0651] | 0.000965 [-0.0147, 0.0148] | -0.00599 [-0.0171, 6.52e-05] | -0.0034 [-0.00861, -0.000453] | -0.0707 [-0.119, -0.0245] | 1 |

Declared not applicable: history_delay (the stand-in's compact encoder reads the current sample only); uncertainty_ensemble (the stand-in reports no uncertainty and has no ensemble); shared_dynamics (the stand-in fits every system independently)

Descriptive: per-switch rows are not part of the primary family; Holm across switches is reported per metric.
