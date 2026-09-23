# Integrator and step-size convergence on the same replicate

Network manc:v1.2.1 nt=paper (N = 4604, 196535 pairs), stimulus = DNg100 at position(s) [31] with I = 250.0, T = 2.0 s, readout = 144 front-leg motor neurons; seeds 0..5; wall 446 s on 6 workers.

Reference: RK45 rtol 1e-08 atol 1e-11 (reference); its own error is estimated at ~5.7e-04 Hz (default-RK45 error x tolerance ratio). Wall times were measured with up to 6 concurrent processes. Mean over seeds; per-seed rows in the JSON. 'window' = t >= 0.25 s (the scored interval); 't <= 0.3 s' = before phase drift accumulates.

## Part A: order study (pulse on for the whole run = the standard replicate shifted by 20 ms; no pulse edge inside the run)

| method | max abs dr (Hz) | RMS dr (Hz) | max abs dr, window | RMS dr, window | max abs dr, t <= 0.3 s | RMS dr, t <= 0.3 s | dr at onset sample | dr at last sample | max abs dscore | mean score | mean MN f (Hz) | active MNs | RHS evals | wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RK45 rtol 1e-08 atol 1e-11 (reference) | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.0e+00 | 0.9817 | 11.25 | 2,3 | 89511 | 86.0 |
| RK45 rtol 2e-6 atol 5e-9 (default) | 1.14e-01 | 1.42e-03 | 1.14e-01 | 1.51e-03 | 1.11e-02 | 1.41e-04 | 0.00e+00 | 7.67e-02 | 1.4e-03 | 0.9815 | 11.25 | 2,3 | 20025 | 19.2 |
| DOP853 rtol 2e-6 atol 5e-9 | 2.48e-02 | 1.44e-04 | 2.48e-02 | 1.53e-04 | 1.45e-02 | 5.95e-05 | 0.00e+00 | 6.43e-03 | 6.2e-04 | 0.9816 | 11.25 | 2,3 | 79764 | 66.7 |
| RK4 dt 1e-3 | 2.32e-02 | 2.84e-04 | 2.32e-02 | 2.98e-04 | 1.10e-02 | 1.50e-04 | 0.00e+00 | 1.06e-02 | 3.4e-04 | 0.9818 | 11.25 | 2,3 | 2000 | 6.0 |
| RK4 dt 5e-4 | 8.57e-03 | 9.19e-05 | 8.57e-03 | 9.73e-05 | 2.33e-03 | 2.93e-05 | 0.00e+00 | 3.50e-03 | 8.4e-05 | 0.9817 | 11.25 | 2,3 | 4000 | 11.5 |
| RK4 dt 2.5e-4 | 3.52e-03 | 3.61e-05 | 3.52e-03 | 3.84e-05 | 8.35e-04 | 1.16e-05 | 0.00e+00 | 1.74e-03 | 2.1e-05 | 0.9817 | 11.25 | 2,3 | 8000 | 23.5 |
| RK4 dt 1.25e-4 | 2.54e-03 | 2.87e-05 | 2.54e-03 | 3.07e-05 | 2.46e-04 | 3.46e-06 | 0.00e+00 | 1.17e-03 | 5.0e-05 | 0.9817 | 11.25 | 2,3 | 16000 | 52.5 |
| Euler dt 1e-3 | 1.19e+01 | 2.30e-01 | 1.19e+01 | 2.42e-01 | 8.38e+00 | 1.33e-01 | 0.00e+00 | 7.12e+00 | 1.2e-01 | 0.9428 | 10.46 | 2,3,4 | 2000 | 1.7 |
| Euler dt 1e-4 | 7.74e+00 | 1.03e-01 | 7.74e+00 | 1.10e-01 | 1.08e+00 | 1.51e-02 | 0.00e+00 | 5.44e+00 | 1.9e-03 | 0.9821 | 11.12 | 2,3 | 20000 | 15.8 |

Empirical convergence orders (expected: RK4 -> 4, Euler -> 1 for a smooth right-hand side):

| family | error measure | dt sequence (s) | mean errors (Hz) | orders between successive dts |
|---|---|---|---|---|
| rk4 | err_max_all_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.32e-02, 8.57e-03, 3.52e-03, 2.54e-03 | 1.70, 1.26, 0.52 |
| rk4 | err_rms_all_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.84e-04, 9.19e-05, 3.61e-05, 2.87e-05 | 1.85, 1.35, 0.35 |
| rk4 | err_max_window_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.32e-02, 8.57e-03, 3.52e-03, 2.54e-03 | 1.70, 1.26, 0.52 |
| rk4 | err_rms_window_hz | 0.001, 0.0005, 0.00025, 0.000125 | 2.98e-04, 9.73e-05, 3.84e-05, 3.07e-05 | 1.85, 1.35, 0.33 |
| rk4 | err_max_early_hz | 0.001, 0.0005, 0.00025, 0.000125 | 1.10e-02, 2.33e-03, 8.35e-04, 2.46e-04 | 2.28, 1.51, 1.61 |
| rk4 | err_rms_early_hz | 0.001, 0.0005, 0.00025, 0.000125 | 1.50e-04, 2.93e-05, 1.16e-05, 3.46e-06 | 2.29, 1.40, 1.65 |
| euler | err_max_all_hz | 0.001, 0.0001 | 1.19e+01, 7.74e+00 | 0.20 |
| euler | err_rms_all_hz | 0.001, 0.0001 | 2.30e-01, 1.03e-01 | 0.35 |
| euler | err_max_window_hz | 0.001, 0.0001 | 1.19e+01, 7.74e+00 | 0.20 |
| euler | err_rms_window_hz | 0.001, 0.0001 | 2.42e-01, 1.10e-01 | 0.35 |
| euler | err_max_early_hz | 0.001, 0.0001 | 8.38e+00, 1.08e+00 | 0.90 |
| euler | err_rms_early_hz | 0.001, 0.0001 | 1.33e-01, 1.51e-02 | 0.95 |

## Part B: standard protocol with its pulse edges (on at 0.02 s, off at T - 1 ms); differences over t <= pulse_end

| method | max abs dr (Hz) | RMS dr (Hz) | max abs dr, window | RMS dr, window | max abs dr, t <= 0.3 s | RMS dr, t <= 0.3 s | dr at onset sample | dr at last sample | max abs dscore | mean score | mean MN f (Hz) | active MNs | RHS evals | wall (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RK45 rtol 1e-08 atol 1e-11 (reference) | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.00e+00 | 0.0e+00 | 0.9824 | 11.25 | 2,3 | 88130 | 85.5 |
| RK45 default, segments | 6.56e-02 | 8.57e-04 | 6.56e-02 | 9.13e-04 | 1.13e-02 | 1.47e-04 | 0.00e+00 | 4.25e-02 | 1.6e-03 | 0.9822 | 11.25 | 2,3 | 19875 | 14.1 |
| RK45 default, single interval | 6.19e-02 | 6.65e-04 | 6.19e-02 | 7.09e-04 | 1.22e-02 | 1.53e-04 | 1.25e-05 | 3.96e-02 | 1.7e-03 | 0.9821 | 11.25 | 2,3 | 20210 | 15.2 |
| RK4 dt 1e-3 | 1.50e-01 | 2.06e-03 | 1.13e-01 | 2.06e-03 | 1.50e-01 | 2.10e-03 | 1.49e-01 | 1.41e-01 | 6.0e-04 | 0.9825 | 11.25 | 2,3 | 2000 | 4.6 |
| RK4 dt 5e-4 | 7.75e-02 | 1.03e-03 | 5.48e-02 | 1.03e-03 | 7.65e-02 | 1.05e-03 | 7.45e-02 | 7.04e-02 | 7.9e-04 | 0.9823 | 11.25 | 2,3 | 4000 | 9.7 |

Fixed-step RK4 in part B (orders from the two dts):

| family | error measure | dt sequence (s) | mean errors (Hz) | orders between successive dts |
|---|---|---|---|---|
| rk4 | err_max_all_hz | 0.001, 0.0005 | 1.50e-01, 7.75e-02 | 0.95 |
| rk4 | err_rms_all_hz | 0.001, 0.0005 | 2.06e-03, 1.03e-03 | 1.00 |
| rk4 | err_max_window_hz | 0.001, 0.0005 | 1.13e-01, 5.48e-02 | 1.06 |
| rk4 | err_rms_window_hz | 0.001, 0.0005 | 2.06e-03, 1.03e-03 | 1.00 |
| rk4 | err_max_early_hz | 0.001, 0.0005 | 1.50e-01, 7.65e-02 | 0.97 |
| rk4 | err_rms_early_hz | 0.001, 0.0005 | 2.10e-03, 1.05e-03 | 1.00 |

Notes: the rate equation's right-hand side has a C0 kink (max(., 0)) at every threshold crossing, which lowers the order any fixed-step scheme can show; the reference's own error bounds what is measurable at the smallest dt. In part B the fixed-step schemes evaluate the pulse indicator at the stage times, so the k4 stage of the step ending at pulse_start and the k1 stage of the step starting at pulse_end see the other side of the switch: an O(dt) discrepancy of ~(dt/6) x activation/tau on the stimulated neuron (0.13 Hz at dt = 1 ms) that propagates into the oscillation phase (see 'dr at onset sample' and 'dr at last sample').
