# Integrator and step-size convergence on the same replicate

Network manc:v1.2.1 nt=paper (N = 4604, 196535 pairs), stimulus = DNg100 at position(s) [31] with I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; seeds 0..0; wall 864 s on 1 workers.

Reference: RK45 rtol 1e-10 atol 1e-13 (reference); its own error is estimated at ~3.7e-06 Hz (default-RK45 error x tolerance ratio). Wall times were measured with up to 1 concurrent processes. Mean over seeds; per-seed rows in the JSON. 'window' = t >= 0.25 s (the scored interval); 't <= 0.3 s' = before phase drift accumulates.

## Part A: order study (pulse on for the whole run = the standard replicate shifted by 20 ms; no pulse edge inside the run)

| method | max abs dr (Hz) | RMS dr (Hz) | max abs dr, window | RMS dr, window | max abs dr, t <= 0.3 s | RMS dr, t <= 0.3 s | dr at onset sample | dr at last sample | max abs dscore | mean score | mean MN f (Hz) | active MNs | RHS evals | wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RK45 rtol 1e-10 atol 1e-13 (reference) | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.0e+00 | 0.8924 | 9.90 | 3 | 208352 | 189.8 |
| RK45 rtol 2e-6 atol 5e-9 (default) | 7.31e-02 | 8.88e-04 | 7.31e-02 | 9.49e-04 | 8.70e-03 | 5.31e-05 | 0.00e+00 | 1.68e-02 | 1.4e-03 | 0.8910 | 9.90 | 3 | 22730 | 29.5 |
| DOP853 rtol 2e-6 atol 5e-9 | 2.13e-02 | 2.57e-04 | 2.13e-02 | 2.73e-04 | 6.39e-03 | 7.81e-05 | 0.00e+00 | 6.07e-03 | 5.9e-04 | 0.8918 | 9.90 | 3 | 88118 | 82.5 |
| RK4 dt 1e-3 | 2.52e-02 | 2.82e-04 | 2.52e-02 | 2.98e-04 | 9.23e-03 | 1.37e-04 | 0.00e+00 | 7.11e-03 | 3.6e-04 | 0.8927 | 9.90 | 3 | 2000 | 3.8 |
| RK4 dt 5e-4 | 5.11e-03 | 4.39e-05 | 5.11e-03 | 4.38e-05 | 4.87e-03 | 4.92e-05 | 0.00e+00 | 1.47e-03 | 5.8e-05 | 0.8923 | 9.90 | 3 | 4000 | 6.8 |
| RK4 dt 2.5e-4 | 3.55e-03 | 4.75e-05 | 3.55e-03 | 5.05e-05 | 1.22e-03 | 1.70e-05 | 0.00e+00 | 1.95e-04 | 5.0e-06 | 0.8924 | 9.90 | 3 | 8000 | 12.9 |
| RK4 dt 1.25e-4 | 8.95e-04 | 9.17e-06 | 8.95e-04 | 9.75e-06 | 2.23e-04 | 3.24e-06 | 0.00e+00 | 2.57e-05 | 2.5e-05 | 0.8924 | 9.90 | 3 | 16000 | 39.8 |
| Euler dt 1e-3 | 1.47e+01 | 2.89e-01 | 1.47e+01 | 3.04e-01 | 1.12e+01 | 1.84e-01 | 0.00e+00 | 1.20e+01 | 9.0e-02 | 0.8020 | 9.17 | 4 | 2000 | 1.8 |
| Euler dt 1e-4 | 1.06e+01 | 1.33e-01 | 1.06e+01 | 1.42e-01 | 1.54e+00 | 2.05e-02 | 0.00e+00 | 4.69e+00 | 2.0e-03 | 0.8944 | 9.80 | 3 | 20000 | 16.8 |
| RK45 rtol 1e-8 atol 1e-11 | 7.21e-03 | 6.74e-05 | 7.21e-03 | 7.21e-05 | 3.97e-04 | 5.06e-06 | 0.00e+00 | 1.79e-03 | 2.6e-05 | 0.8924 | 9.90 | 3 | 97238 | 90.8 |

Empirical convergence orders (expected: RK4 -> 4, Euler -> 1 for a smooth right-hand side):

| family | error measure | dt sequence (s) | mean errors (Hz) | orders between successive dts |
|---|---|---|---|---|
| rk4 | err_max_all_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.52e-02, 5.11e-03, 3.55e-03, 8.95e-04 | 2.30, 0.53, 1.99 |
| rk4 | err_rms_all_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.82e-04, 4.39e-05, 4.75e-05, 9.17e-06 | 2.68, -0.11, 2.37 |
| rk4 | err_max_window_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.52e-02, 5.11e-03, 3.55e-03, 8.95e-04 | 2.30, 0.53, 1.99 |
| rk4 | err_rms_window_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.98e-04, 4.38e-05, 5.05e-05, 9.75e-06 | 2.77, -0.20, 2.37 |
| rk4 | err_max_early_hz | 0.001, 0.0005, 0.00025, 0.000125 | 9.23e-03, 4.87e-03, 1.22e-03, 2.23e-04 | 0.92, 2.00, 2.45 |
| rk4 | err_rms_early_hz | 0.001, 0.0005, 0.00025, 0.000125 | 1.37e-04, 4.92e-05, 1.70e-05, 3.24e-06 | 1.48, 1.53, 2.39 |
| euler | err_max_all_hz | 0.001, 0.0001 | 1.47e+01, 1.06e+01 | 0.15 |
| euler | err_rms_all_hz | 0.001, 0.0001 | 2.89e-01, 1.33e-01 | 0.34 |
| euler | err_max_window_hz | 0.001, 0.0001 | 1.47e+01, 1.06e+01 | 0.15 |
| euler | err_rms_window_hz | 0.001, 0.0001 | 3.04e-01, 1.42e-01 | 0.33 |
| euler | err_max_early_hz | 0.001, 0.0001 | 1.12e+01, 1.54e+00 | 0.86 |
| euler | err_rms_early_hz | 0.001, 0.0001 | 1.84e-01, 2.05e-02 | 0.95 |

## Part B: standard protocol with its pulse edges (on at 0.02 s, off at T - 1 ms); differences over t <= pulse_end

| method | max abs dr (Hz) | RMS dr (Hz) | max abs dr, window | RMS dr, window | max abs dr, t <= 0.3 s | RMS dr, t <= 0.3 s | dr at onset sample | dr at last sample | max abs dscore | mean score | mean MN f (Hz) | active MNs | RHS evals | wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RK45 rtol 1e-10 atol 1e-13 (reference) | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.0e+00 | 0.8964 | 9.90 | 3 | 206706 | 190.8 |
| RK45 default, segments | 1.07e-01 | 1.10e-03 | 1.07e-01 | 1.18e-03 | 7.92e-03 | 5.52e-05 | 0.00e+00 | 6.00e-02 | 1.7e-03 | 0.8947 | 9.90 | 3 | 22512 | 25.7 |
| RK45 default, single interval | 3.12e-02 | 2.80e-04 | 3.12e-02 | 2.97e-04 | 1.42e-02 | 1.68e-04 | 3.35e-05 | 2.29e-02 | 1.8e-03 | 0.8946 | 9.90 | 3 | 22855 | 25.9 |
| RK4 dt 1e-3 | 1.40e-01 | 2.05e-03 | 1.31e-01 | 2.02e-03 | 1.40e-01 | 2.34e-03 | 1.34e-01 | 1.27e-01 | 5.3e-04 | 0.8969 | 9.90 | 3 | 2000 | 7.5 |
| RK4 dt 5e-4 | 8.34e-02 | 1.42e-03 | 8.34e-02 | 1.45e-03 | 7.99e-02 | 1.38e-03 | 6.71e-02 | 6.37e-02 | 8.6e-04 | 0.8955 | 9.90 | 3 | 4000 | 14.6 |
| RK45 rtol 1e-8 atol 1e-11 | 3.45e-03 | 2.67e-05 | 3.45e-03 | 2.85e-05 | 6.06e-04 | 6.53e-06 | 0.00e+00 | 1.99e-03 | 7.2e-05 | 0.8963 | 9.90 | 3 | 97062 | 114.2 |

Fixed-step RK4 in part B (orders from the two dts):

| family | error measure | dt sequence (s) | mean errors (Hz) | orders between successive dts |
|---|---|---|---|---|
| rk4 | err_max_all_hz | 0.001, 0.0005 | 1.40e-01, 8.34e-02 | 0.75 |
| rk4 | err_rms_all_hz | 0.001, 0.0005 | 2.05e-03, 1.42e-03 | 0.53 |
| rk4 | err_max_window_hz | 0.001, 0.0005 | 1.31e-01, 8.34e-02 | 0.65 |
| rk4 | err_rms_window_hz | 0.001, 0.0005 | 2.02e-03, 1.45e-03 | 0.48 |
| rk4 | err_max_early_hz | 0.001, 0.0005 | 1.40e-01, 7.99e-02 | 0.81 |
| rk4 | err_rms_early_hz | 0.001, 0.0005 | 2.34e-03, 1.38e-03 | 0.77 |

Notes: the rate equation's right-hand side has a C0 kink (max(., 0)) at every threshold crossing, which lowers the order any fixed-step scheme can show; the reference's own error bounds what is measurable at the smallest dt. In part B the fixed-step schemes evaluate the pulse indicator at the stage times, so the k4 stage of the step ending at pulse_start and the k1 stage of the step starting at pulse_end see the other side of the switch: an O(dt) discrepancy of ~(dt/6) x activation/tau on the stimulated neuron (0.13 Hz at dt = 1 ms) that propagates into the oscillation phase (see 'dr at onset sample' and 'dr at last sample').
