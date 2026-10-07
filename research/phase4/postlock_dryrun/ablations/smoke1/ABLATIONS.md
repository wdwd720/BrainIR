# Ablations of `p3stand.refstand:p3stand_ref` (dev; run smoke1)

1 systems; 1 compressible synthetic systems enter the suite statistics; tolerances PROVISIONAL (no calibration yet).

## Critical ablations

- **Q20 interventional training** (goal5 88): **FAIL**. Suite mean EE_ablated - EE_full = -0.121 (one-sided 95 % lower bound -0.121, p = 1).
- **Q21 state bottleneck** (goal5 89): **outcomes not predictable even without the bottleneck (attributed to excitation / data; goal5 section 94 B)**.

## Per switch (suite paired difference ablated - full; positive = the ablation is worse for lower-is-better metrics)

| switch | EE | EE held-out | SMS | ICG_y | MEV | lift success | false confidence | Holm p (EE) |
|---|---|---|---|---|---|---|---|---|
| interventional_training | -0.121 [-0.121, -0.121] | -0.112 [-0.112, -0.112] | -0.0183 [-0.0183, -0.0183] | 6.51e-05 [6.51e-05, 6.51e-05] | -4.47e-07 [-4.47e-07, -4.47e-07] | 0 [0, 0] | 0.404 [0.404, 0.404] | 1 |
| state_bottleneck | 0.245 [0.245, 0.245] | 0.268 [0.268, 0.268] | -0.00251 [-0.00251, -0.00251] | -2.49e-05 [-2.49e-05, -2.49e-05] | 7.18e-05 [7.18e-05, 7.18e-05] | 0 [0, 0] | -0.056 [-0.056, -0.056] | 0.0015 |
| native_lift | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 1 |

Descriptive: per-switch rows are not part of the primary family; Holm across switches is reported per metric.
