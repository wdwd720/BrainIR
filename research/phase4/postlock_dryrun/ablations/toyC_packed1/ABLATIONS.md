# Ablations of `p3stand.refstand:p3stand_ref` (toyC; run toyC_packed1)

**DRY RUN** (stand-in models, before the lock): not a result; never released, never used for any decision.

2 systems; 2 compressible synthetic systems enter the suite statistics; tolerances PROVISIONAL (no calibration yet).

## Critical ablations

- **Q20 interventional training** (goal5 88): **PASS**. Suite mean EE_ablated - EE_full = 0.502 (one-sided 95 % lower bound 0.19, p = 0.0005).
- **Q21 state bottleneck** (goal5 89): **the compact state suffices (the bottleneck costs less than delta_C_suite)**.

## Per switch (suite paired difference ablated - full; positive = the ablation is worse for lower-is-better metrics)

| switch | EE | EE held-out | SMS | ICG_y | MEV | lift success | false confidence | Holm p (EE) |
|---|---|---|---|---|---|---|---|---|
| interventional_training | 0.502 [0.19, 0.813] | 0.587 [0.308, 0.865] | 0.0517 [-0.021, 0.124] | 1.48e-07 [-4.94e-08, 3.46e-07] | -1.13e-05 [-2.25e-05, 0] | -1 [-1, -1] | 0 [0, 0] | 0.001 |
| state_bottleneck | 0.173 [0.00568, 0.341] | 0.196 [0.0103, 0.381] | 0.0116 [-0.00177, 0.025] | 1.13e-07 [-1.83e-07, 4.1e-07] | 0.000143 [0.000131, 0.000154] | -1 [-1, -1] | 0.0696 [0, 0.139] | 0.001 |

Descriptive: per-switch rows are not part of the primary family; Holm across switches is reported per metric.
