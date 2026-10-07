# Robustness sweeps: `p3stand.refstand:p3stand_ref` (val; run val1; descriptive)

**DRY RUN** (val tier (Level B selection tier), stand-in models, before the lock): not a result; never released, never used for any decision.

50 systems; 8 items per level. Flat uncertainty: param_noise, weight_noise, process_noise, obs_noise, amplitude_jitter, timing_jitter.

| condition | level | systems | EE | abstain | pred sd | RMS error | sd ratio | error ratio |
|---|---|---|---|---|---|---|---|---|
| param_noise | 0 | 50 | 1.07 | 0.147 | - | 0.663 | - | - |
| param_noise | 1.25 | 50 | 0.927 | 0.158 | - | 0.641 | - | 0.967 |
| param_noise | 1.5 | 50 | 0.939 | 0.19 | - | 0.698 | - | 1.053 |
| param_noise | 1.75 | 50 | 1.14 | 0.163 | - | 0.849 | - | 1.28 |
| param_noise | 2.0 | 50 | 0.936 | 0.158 | - | 56.4 | - | 85.103 |
| param_noise | 2.5 | 50 | 1.25 | 0.163 | - | 1.28 | - | 1.935 |
| weight_noise | 0 | 50 | 1.07 | 0.147 | - | 0.663 | - | - |
| weight_noise | 0.025 | 50 | 1.03 | 0.158 | - | 1.05e+41 | - | 1.590358965033656e+41 |
| weight_noise | 0.05 | 50 | 1.23 | 0.147 | - | 1.06e+44 | - | 1.6003009379103418e+44 |
| weight_noise | 0.075 | 50 | 1.03 | 0.172 | - | 4.14e+62 | - | 6.247834720020979e+62 |
| weight_noise | 0.1 | 50 | 0.922 | 0.147 | - | 0.554 | - | 0.836 |
| weight_noise | 0.15 | 50 | 1.01 | 0.155 | - | 0.61 | - | 0.92 |
| process_noise | 0 | 50 | 1.07 | 0.147 | - | 0.663 | - | - |
| process_noise | 0.025 | 50 | 0.984 | 0.19 | - | 0.732 | - | 1.105 |
| process_noise | 0.05 | 50 | 1.1 | 0.152 | - | 0.716 | - | 1.08 |
| process_noise | 0.1 | 50 | 0.908 | 0.152 | - | 0.758 | - | 1.143 |
| process_noise | 0.2 | 50 | 1.11 | 0.18 | - | 3.04e+08 | - | 458638393.483 |
| obs_noise | 0 | 50 | 1.07 | 0.147 | - | 0.663 | - | - |
| obs_noise | 0.025 | 50 | 1.17 | 0.152 | - | 0.653 | - | 0.984 |
| obs_noise | 0.05 | 50 | 1.13 | 0.147 | - | 1.53e+52 | - | 2.308640861016419e+52 |
| obs_noise | 0.1 | 50 | 0.968 | 0.165 | - | 3.7e+22 | - | 5.583007880749747e+22 |
| obs_noise | 0.2 | 50 | 1.15 | 0.145 | - | 0.589 | - | 0.888 |
| amplitude_jitter | 0 | 50 | 1.07 | 0.147 | - | 0.663 | - | - |
| amplitude_jitter | 0.1 | 50 | 1 | 0.172 | - | 0.7 | - | 1.056 |
| amplitude_jitter | 0.2 | 50 | 1.04 | 0.138 | - | 0.593 | - | 0.895 |
| amplitude_jitter | 0.3 | 50 | 1.02 | 0.175 | - | 3.74e+06 | - | 5639886.205 |
| amplitude_jitter | 0.5 | 50 | 0.911 | 0.175 | - | 0.56 | - | 0.844 |
| timing_jitter | 0 | 50 | 1.07 | 0.147 | - | 0.663 | - | - |
| timing_jitter | 1 | 50 | 1.25 | 0.135 | - | 0.731 | - | 1.103 |
| timing_jitter | 2 | 50 | 1.13 | 0.155 | - | 0.61 | - | 0.92 |
| timing_jitter | 4 | 50 | 1.07 | 0.152 | - | 0.614 | - | 0.925 |
| timing_jitter | 8 | 50 | 1.13 | 0.165 | - | 0.586 | - | 0.885 |
