# Robustness sweeps: `p3stand.refstand:p3stand_ref` (None; run realpub1; descriptive)

**DRY RUN** (stand-in models, before the lock): not a result; never released, never used for any decision.

3 systems; 2 items per level. Flat uncertainty: param_noise, weight_noise, obs_noise, amplitude_jitter, timing_jitter.

| condition | level | systems | EE | abstain | pred sd | RMS error | sd ratio | error ratio |
|---|---|---|---|---|---|---|---|---|
| param_noise | 0 | 3 | 0.97 | 0 | - | 0.387 | - | - |
| param_noise | 1.25 | 3 | 0.683 | 0.333 | - | 0.481 | - | 1.242 |
| param_noise | 1.5 | 3 | 0.88 | 0.167 | - | 0.517 | - | 1.334 |
| param_noise | 1.75 | 3 | 0.97 | 0.167 | - | 19.1 | - | 49.305 |
| param_noise | 2.0 | 3 | 0.747 | 0.167 | - | 0.756 | - | 1.952 |
| param_noise | 2.5 | 3 | 0.644 | 0.333 | - | 0.569 | - | 1.469 |
| weight_noise | 0 | 3 | 0.97 | 0 | - | 0.387 | - | - |
| weight_noise | 0.025 | 3 | 1.01 | 0 | - | 0.467 | - | 1.206 |
| weight_noise | 0.05 | 3 | 0.523 | 0.167 | - | 0.411 | - | 1.062 |
| weight_noise | 0.075 | 3 | 0.64 | 0.167 | - | 0.443 | - | 1.143 |
| weight_noise | 0.1 | 3 | 0.503 | 0.333 | - | 0.588 | - | 1.518 |
| weight_noise | 0.15 | 3 | 0.668 | 0.167 | - | 0.938 | - | 2.421 |
| process_noise | 0 | 3 | 0.97 | 0 | - | 0.387 | - | - |
| obs_noise | 0 | 3 | 0.97 | 0 | - | 0.387 | - | - |
| obs_noise | 0.025 | 3 | 0.54 | 0.333 | - | 0.403 | - | 1.041 |
| obs_noise | 0.05 | 3 | 0.712 | 0.333 | - | 0.434 | - | 1.121 |
| obs_noise | 0.1 | 3 | 0.666 | 0.333 | - | 0.425 | - | 1.098 |
| obs_noise | 0.2 | 3 | 0.954 | 0.167 | - | 19.6 | - | 50.591 |
| amplitude_jitter | 0 | 3 | 0.97 | 0 | - | 0.387 | - | - |
| amplitude_jitter | 0.1 | 3 | 0.687 | 0.167 | - | 0.37 | - | 0.954 |
| amplitude_jitter | 0.2 | 3 | 0.515 | 0.333 | - | 0.345 | - | 0.889 |
| amplitude_jitter | 0.3 | 3 | 0.679 | 0.333 | - | 0.631 | - | 1.629 |
| amplitude_jitter | 0.5 | 3 | 0.617 | 0.333 | - | 0.459 | - | 1.186 |
| timing_jitter | 0 | 3 | 0.97 | 0 | - | 0.387 | - | - |
| timing_jitter | 1 | 3 | 0.41 | 0 | - | 0.564 | - | 1.456 |
| timing_jitter | 2 | 3 | 0.598 | 0.333 | - | 0.368 | - | 0.949 |
| timing_jitter | 4 | 3 | 0.885 | 0.333 | - | 0.396 | - | 1.022 |
| timing_jitter | 8 | 3 | 1.02 | 0.167 | - | 0.641 | - | 1.654 |
