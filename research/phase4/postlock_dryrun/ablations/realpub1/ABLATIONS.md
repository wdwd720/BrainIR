# Ablations of `p3stand.refstand:p3stand_ref` (None + real public; run realpub1)

**DRY RUN** (stand-in models, before the lock): not a result; never released, never used for any decision.

3 systems; 0 compressible synthetic systems enter the suite statistics; tolerances PROVISIONAL (no calibration yet).

## Critical ablations

- **Q20 interventional training** (goal5 88): **FAIL**. 
- **Q21 state bottleneck** (goal5 89): **outcomes not predictable even without the bottleneck (attributed to excitation / data; goal5 section 94 B)**.

## Per switch (suite paired difference ablated - full; positive = the ablation is worse for lower-is-better metrics)

| switch | EE | EE held-out | SMS | ICG_y | MEV | lift success | false confidence | Holm p (EE) |
|---|---|---|---|---|---|---|---|---|
| interventional_training | - | - | - | - | - | - | - | - |
| state_bottleneck | - | - | - | - | - | - | - | - |

Descriptive: per-switch rows are not part of the primary family; Holm across switches is reported per metric.
