# Calibration targets for the synthetic causal-state suite (goal5 section 8)

Generic summary statistics of ten simulated real systems, computed from PUBLIC trajectories only. The synthetic suite should be distributionally realistic: its systems should span these ranges, not copy any single system. The machine-readable targets are `benchmarks/causal_state_v1/public/calibration_targets.json`; the statistics are computed by `brainir_causal.calibstats.compute_all` from generic trajectory records (x observed microstate, u input, y readout, protocol with events, intervention / twin pairs), and `calibstats.compare` checks a suite against the targets (acceptance criterion 11).

## The real systems in brief

- **Two regimes.** Three large recurrent networks (about 200 observed units, 9-20 readout units, one input) and seven small sub-circuits of them (3-6 observed units, same readout and input). Output sampling 1 ms, trajectories 2 s, one input switched on within the first 150 ms.
- **Activity.** Rectified, sparse and bursty: in the large systems active units sit at the floor for 53-63 % of samples (about 10 % in the small ones); median activity of active units is 5-26 % of the rate scale (99th percentile of |x|), per-unit peaks 1-4 x the scale. Part of the readout is silent in the small systems.
- **Oscillation.** Every system oscillates, with dominant frequencies of 7-17 Hz and spectra concentrated below ~25 Hz; decorrelation within 12-29 ms; input-onset responses within 22-54 ms.
- **Dimensionality.** One passive trajectory is low-dimensional (participation ratio 1.1-2.3; 2-3 components for 95 %), but pooled over parameter draws, inputs and initial states the large systems need 5-27 components for 95 % of the variance. The readout is effectively one- to two-dimensional.
- **Interventions reveal more than passive activity.** Pooled intervention effects need up to ~24 components for 95 % of their energy, and 0.8-83 % of the effect energy lies OUTSIDE the subspace that holds 95 % of the passive variance (0.41-0.83 in the large systems). A synthetic suite must include systems where passive data hide causally relevant directions and systems where they do not.
- **Effect sizes.** In the large systems interventions are sparse and often invisible at the readout: a single-target intervention moves only 6-9 % of the other observed units by more than 1 % of the scale (42-46 % of them move any other unit), and 35-45 % of interventions change the readout by less than 1 % of its own variability. In the small systems nearly every intervention propagates everywhere. Median effects relative to the counterfactual twin's variability: x 0.2-0.3 (large), 1-22 (small); readout 0.016-0.16 (large), 1-23 (small).
- **Temporal structure of effects.** Transient effects decay to 1/e within 20-55 ms after the intervention ends, yet readout effects peak 50-380 ms after onset and part of the effect persists (phase shifts of the oscillation, persistent silencing): delayed consequences matter.
- **Clipping.** A quarter to a half of all kick offsets are clipped at the floor (negative kicks on units at or near rest).
- **Variability.** Parameter draws change trajectories substantially (spread 0.2-1.2 of the mean level; 1.3-5 x the dynamic range of the draw-averaged trajectory, because draws dephase oscillations). Intervention effects are often SMALLER than this variability (readout effect / parameter spread 0.013-0.9).
- **Input nonlinearity.** Activity grows as the 2.7-5.8th power of the input scale over the input scales of the public records (about 0.6-1.4; readout elasticity 1.7-6.1).
- **Noise.** The simulations are deterministic; the only measurable floor is an integration-path difference of 8e-6 to 3e-4 of the scale before any event. Observation noise is a benchmark parameter.

## Checked statistics and recommended target ranges

`min in` = the minimum fraction of synthetic systems that must fall inside the target range; `coverage [a, b]` = the suite must contain a system with value <= a and one with value >= b. Ranges: `pos` [min / 2, 2 x max] (a factor-2 margin on both sides of the real range); `frac` [max(0, min - 0.1), min(1, max + 0.1)]; `dim` [max(1, floor(min / 1.5)), ceil(1.5 x max)]; `size` [min, 1.25 x max]; `dt` [min / 2, 5 x max].

| statistic | real, large systems | real, small systems | target range | min in | coverage | why |
|---|---|---|---|---|---|---|
| `n_obs` | 197 - 213 | 3 - 6 | 3 - 266 | 0.0 | [6, 100] | The real systems come in two regimes (3-6 observed units, and about 200). The suite must contain both: at least one system with <= 6 and at least one with >= 100 observed units. |
| `dt` | 0.001 - 0.001 | 0.001 - 0.001 | 5.00e-04 - 0.005 | 0.5 | - | Real timescales are 10-50 ms; an output step above ~5 ms under-resolves them. |
| `frac_readout_active` | 1 - 1 | 0.444 - 0.8 | 0.344 - 1 | 0.5 | - | Part of the readout is silent in the small systems; all of it is active in the large ones. |
| `rate_active_rel_p50` | 0.068 - 0.0872 | 0.0456 - 0.259 | 0.0228 - 0.519 | 0.5 | - | Median activity of active units is a small fraction of the rate scale (sparse, bursty activity). |
| `peak_rate_rel_p50` | 1.45 - 4.4 | 1.07 - 2.59 | 0.537 - 8.79 | 0.5 | - | Per-unit peaks are 1-4 x the system scale (heterogeneous peak rates). |
| `frac_samples_at_floor` | 0.533 - 0.631 | 0.0904 - 0.118 | 0 - 0.731 | 0.5 | - | Rectification: the large systems spend 53-63 % of active-unit samples at the floor, the small ones about 10 %. |
| `kick_clipped_frac_all` | 0.482 - 0.497 | 0.239 - 0.526 | 0.139 - 0.626 | 0.5 | - | About a quarter to a half of all public kick offsets are clipped at the floor (negative kicks on units at or near rest). |
| `dim_x_traj_pr` | 2.26 - 2.34 | 1.11 - 1.45 | 0.556 - 4.69 | 0.5 | - | Single passive trajectories are low-dimensional. |
| `dim_x_traj_n95` | 3 - 3 | 2 - 2 | 1 - 5 | 0.5 | - | 2-3 components hold 95 % of a single trajectory's variance. |
| `dim_x_pooled_obs_n95` | 5 - 27 | 1 - 2 | 1 - 41 | 0.5 | - | Pooled over conditions (parameter draws, inputs, initial states) the large systems need 5-27 components. |
| `dim_y_traj_pr` | 1.06 - 1.36 | 1.02 - 1.11 | 0.508 - 2.73 | 0.5 | - | The readout is effectively one- to two-dimensional within a trajectory. |
| `dim_effect_x_pr` | 1.23 - 8.15 | 1.11 - 1.86 | 0.553 - 16.3 | 0.5 | - | Intervention effects span more directions than passive trajectories in the large systems. |
| `dim_effect_x_n95` | 2 - 24 | 1 - 3 | 1 - 36 | 0.5 | - | Up to ~24 components for 95 % of the pooled effect energy. |
| `effect_energy_outside_passive95` | 0.406 - 0.833 | 0.00797 - 0.306 | 0 - 0.933 | 0.5 | [0.1, 0.4] | Interventions excite directions that passive activity does not visit (0.008-0.83 of the effect energy lies outside the passive 95 % subspace). The suite must include systems where this fraction is small (<= 0.1) and systems where it is large (>= 0.4): this is the central observational-vs-interventional distinction. |
| `acf_decay_s_median` | 0.0155 - 0.0169 | 0.0115 - 0.0291 | 0.00576 - 0.0582 | 0.5 | - | Decorrelation within 12-29 ms (a quarter period of the oscillation where one is present). |
| `onset_latency_10pct_s` | 0.022 - 0.024 | 0.025 - 0.054 | 0.011 - 0.108 | 0.5 | - | Responses to the input onset start within 22-54 ms. |
| `spec_x_f_peak` | 8.79 - 10.7 | 6.84 - 16.6 | 3.42 - 33.2 | 0.25 | - | All ten real systems oscillate, with dominant frequencies of 7-17 Hz. At least a quarter of the synthetic systems should have their dominant frequency in the target band; families that do not oscillate by construction are exempt. |
| `spec_x_oscillatory_frac` | 1 - 1 | 0.976 - 0.992 | 0.876 - 1 | 0.25 | - | Every real system is oscillatory; at least a quarter of the synthetic systems should be. |
| `eff_rel_x_p50` | 0.207 - 0.288 | 1.04 - 21.5 | 0.103 - 43 | 0.5 | - | Median effect of an intervention relative to the twin's own variability: ~0.2-0.3 in the large systems, 1-22 in the small ones. |
| `eff_rel_y_p50` | 0.0161 - 0.158 | 1.05 - 23.4 | 0.00804 - 46.8 | 0.5 | - | The same for the readout: 0.016-0.16 in the large systems, 1-23 in the small ones. |
| `frac_eff_rel_y_below_0.01` | 0.35 - 0.45 | 0 - 0 | 0 - 0.55 | 0.5 | [0.0, 0.3] | Near-zero readout effects are common in the large systems (35-45 % of interventions change the readout by < 1 % of its variability) and absent in the small ones. The suite must contain both regimes (a system with none and one with >= 30 % near-zero effects). |
| `eff_rms_x_rel_scale_p50` | 0.0123 - 0.0197 | 0.0547 - 0.217 | 0.00614 - 0.433 | 0.5 | - | Effect RMS is 1-22 % of the rate scale. |
| `resp_frac_1pct_mean` | 0.0634 - 0.0867 | 0.861 - 1 | 0 - 1 | 0.5 | [0.1, 0.8] | Response sparsity: in the large systems a single-target intervention moves only 6-9 % of the other observed units by > 1 % of the scale; in the small ones nearly all. Both regimes must be present. |
| `resp_frac_1pct_any` | 0.417 - 0.462 | 0.933 - 1 | 0.317 - 1 | 0.5 | - | Fraction of single-target interventions that move at least one other unit: 0.42-0.46 (large), ~1 (small). |
| `decay_x_s_median` | 0.0215 - 0.0251 | 0.0231 - 0.0525 | 0.0108 - 0.105 | 0.5 | - | Transient effects decay to 1/e within 20-55 ms. |
| `latency_y_peak_s_median` | 0.208 - 0.384 | 0.053 - 0.181 | 0.0265 - 0.767 | 0.5 | - | Readout effects peak 50-380 ms after the intervention onset (delayed consequences; goal5 section 44). |
| `effect_end_over_peak_median` | 0.044 - 0.129 | 0.191 - 0.499 | 0 - 0.599 | 0.5 | - | Part of the effect persists to the end of the window (phase shifts of oscillations, persistent silencing). |
| `persistence_ratio_kick` | 1.03 - 1.23 | 0.919 - 2.11 | 0.459 - 4.23 | 0.5 | - | Network effect decay after kicks is 0.9-2.1 x the kicked unit's own decay. |
| `kick_rel_scale_p50` | 1.57 - 1.99 | 0.0938 - 1.73 | 0.0469 - 3.98 | 0.5 | - | Public kick offsets are 0.1-2 x the system's rate scale. |
| `snr_param_x_median` | 0.157 - 0.236 | 0.503 - 2.29 | 0.0784 - 4.58 | 0.5 | - | Intervention effects relative to the spread across parameter draws: 0.16-0.24 (large), 0.5-2.3 (small). |
| `snr_param_y_median` | 0.0132 - 0.117 | 0.316 - 0.906 | 0.0066 - 1.81 | 0.5 | - | The same for the readout: 0.013-0.12 (large), 0.3-0.9 (small); effects are often small compared with parameter variability. |
| `params_param_spread_x_rel_level` | 0.397 - 0.426 | 0.203 - 1.17 | 0.101 - 2.34 | 0.5 | - | Parameter draws change trajectories substantially (spread 0.2-1.2 of the mean level). |
| `params_param_spread_x_rel_dynamics` | 2.44 - 2.79 | 1.31 - 5.02 | 0.657 - 10 | 0.5 | - | The spread exceeds the dynamic range of the draw-averaged trajectory (1.3-5.0 x): draws dephase oscillations. |
| `input_gain_elasticity_x` | 3.42 - 3.87 | 2.74 - 5.8 | 1.37 - 11.6 | 0.5 | - | Strongly nonlinear input response: RMS activity grows as the 2.7-5.8th power of the input scale over the public range. |
| `input_gain_elasticity_y` | 4.07 - 6.14 | 1.69 - 4.66 | 0.845 - 12.3 | 0.5 | - | The readout's input elasticity is 1.7-6.1. |

## Definitions of the checked statistics

- `n_obs`: number of observed units (columns of x)
- `dt`: output sampling interval (s)
- `frac_readout_active`: fraction of readout units whose temporal sd exceeds 1e-3 s_y
- `rate_active_rel_p50`: percentile of the samples of active observed units that are above the floor, divided by s_x
- `peak_rate_rel_p50`: percentile across active observed units of each unit's maximum, divided by s_x
- `frac_samples_at_floor`: fraction of samples of active units at their lower bound (within 1e-6 s_x of the unit's minimum; rectified units at 0)
- `kick_clipped_frac_all`: fraction of kick offsets on observed targets (all records) that were clipped at the lower bound
- `dim_x_traj_pr`: PCA of one trajectory's x (covariance, centred): participation ratio (pr) or number of components for 90/95/99 % variance (n90/n95/n99); median over trajectories (up to 40 per record kind)
- `dim_x_traj_n95`: PCA of one trajectory's x (covariance, centred): participation ratio (pr) or number of components for 90/95/99 % variance (n90/n95/n99); median over trajectories (up to 40 per record kind)
- `dim_x_pooled_obs_n95`: PCA of all event-free trajectories pooled (sub-sampled every 5 ms): pr / n90 / n95 / n99
- `dim_y_traj_pr`: the same for the readout y of one trajectory
- `dim_effect_x_pr`: PCA (uncentred) of the intervention effects x_int - x_twin pooled over all (intervention, twin) pairs and post-onset samples: pr / n90 / n95 / n99
- `dim_effect_x_n95`: PCA (uncentred) of the intervention effects x_int - x_twin pooled over all (intervention, twin) pairs and post-onset samples: pr / n90 / n95 / n99
- `effect_energy_outside_passive95`: fraction of the pooled intervention-effect energy outside the subspace holding 95 % of the variance of the event-free trajectories (how much interventions excite directions passive activity does not visit)
- `acf_decay_s_median`: median over active units and event-free trajectories of the lag (s) at which the autocorrelation first drops below 1/e (window after the onset transient); uncensored units only. For oscillating units this is about a quarter period, not a memory time
- `onset_latency_10pct_s`: time (s) from the input onset until ||x(t) - x(onset)|| first reaches 10 % of its maximum (nominal trajectories)
- `spec_x_f_peak`: Welch spectrum of the active units of x after the onset transient, each unit normalised to unit power, averaged: dominant frequency f_peak (Hz), prominence_log10 (log10 of peak / median density), centroid (Hz), f05 / f50 / f95 (Hz at 5 / 50 / 95 % cumulative power); median over event-free trajectories
- `spec_x_oscillatory_frac`: fraction of event-free trajectories whose unit-averaged normalised power spectrum has a peak >= 10 x its median
- `eff_rel_x_p50`: intervention effect in x: ||x_int - x_twin||_F / ||x_twin - mean_t x_twin||_F over the window from the first event to the end (effect relative to the twin's own variability); percentiles over pairs; suffix = kind of the first event
- `eff_rel_y_p50`: the same for the readout y
- `frac_eff_rel_y_below_0.01`: fraction of pairs whose relative readout effect eff_rel_y is below the threshold (near-zero effects)
- `eff_rms_x_rel_scale_p50`: RMS of x_int - x_twin from the first event to the end, divided by s_x; percentiles over pairs
- `resp_frac_1pct_mean`: response sparsity over single-target first events: the fraction of the OTHER observed units whose max |effect| in the first-event window exceeds 1 % of s_x (_median / _mean / _p90 over events; _any = fraction of events with at least one responding unit)
- `resp_frac_1pct_any`: response sparsity over single-target first events: the fraction of the OTHER observed units whose max |effect| in the first-event window exceeds 1 % of s_x (_median / _mean / _p90 over events; _any = fraction of events with at least one responding unit)
- `decay_x_s_median`: time (s) from the peak of ||x_int - x_twin|| after the end of a transient first event to its fall below peak / e; median over pairs
- `latency_y_peak_s_median`: time (s) from the first event's onset to the peak of the readout effect norm within the first-event window; median over pairs
- `effect_end_over_peak_median`: effect norm in x at the end of the first-event window divided by its peak (persistence); median over pairs
- `persistence_ratio_kick`: median network effect decay time after kicks divided by the median decay of the kicked unit's own effect (recurrent persistence)
- `kick_rel_scale_p50`: |kick offset| / s_x for single-target first kicks; percentiles
- `snr_param_x_median`: median over pairs of the effect RMS in x divided by the RMS spread of x across parameter draws (nominal trajectories)
- `snr_param_y_median`: the same for the readout
- `params_param_spread_x_rel_level`: spread across parameter draws: nominal trajectories aligned at the input onset; rel_level = RMS(sd over draws) / RMS(mean over draws); rel_dynamics = RMS(sd) / RMS(mean - its time average); abs_rms in units of x / y
- `params_param_spread_x_rel_dynamics`: spread across parameter draws: nominal trajectories aligned at the input onset; rel_level = RMS(sd over draws) / RMS(mean over draws); rel_dynamics = RMS(sd) / RMS(mean - its time average); abs_rms in units of x / y
- `input_gain_elasticity_x`: slope of log(response RMS during the input) against log(input scale) over event-free trajectories
- `input_gain_elasticity_y`: slope of log(response RMS during the input) against log(input scale) over event-free trajectories

## All statistics (descriptive), by group

Real range over all ten systems, then large / small systems. Units: x and y in the simulator's rate units, times in seconds, frequencies in Hz.

### Sizes and sampling

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `dt` | 0.001 - 0.001; 0.001 | 0.001 - 0.001 | 0.001 - 0.001 |
| `duration_s` | 2 - 2; 2 | 2 - 2 | 2 - 2 |
| `n_obs` | 3 - 213; 4 | 197 - 213 | 3 - 6 |
| `n_targets_public` | 3 - 106; 4 | 98 - 106 | 3 - 6 |
| `n_u` | 1 - 1; 1 | 1 - 1 | 1 - 1 |
| `n_y` | 9 - 20; 10 | 9 - 20 | 9 - 20 |

### Rate scales and saturation

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `frac_readout_active` | 0.444 - 1; 0.689 | 1 - 1 | 0.444 - 0.8 |
| `frac_samples_at_floor` | 0.0904 - 0.631; 0.111 | 0.533 - 0.631 | 0.0904 - 0.118 |
| `frac_samples_near_system_max` | 2.27e-07 - 0.00763; 4.84e-04 | 2.27e-07 - 6.77e-05 | 3.18e-04 - 0.00763 |
| `frac_samples_near_unit_max` | 1.50e-04 - 0.014; 5.35e-04 | 1.50e-04 - 4.04e-04 | 3.51e-04 - 0.014 |
| `frac_units_active` | 1 - 1; 1 | 1 - 1 | 1 - 1 |
| `kick_clipped_frac` | 0 - 1; 0.267 | 0.167 - 0.667 | 0 - 1 |
| `kick_clipped_frac_all` | 0.239 - 0.526; 0.463 | 0.482 - 0.497 | 0.239 - 0.526 |
| `kick_clipped_frac_of_negative` | 0.5 - 1; 0.958 | 0.98 - 1 | 0.5 - 0.976 |
| `peak_rate_max` | 56.1 - 220; 176 | 147 - 220 | 56.1 - 218 |
| `peak_rate_p5` | 18.9 - 178; 30.4 | 18.9 - 19.4 | 29.5 - 178 |
| `peak_rate_p50` | 21 - 208; 39.2 | 21 - 53.7 | 31.1 - 208 |
| `peak_rate_p95` | 54.1 - 215; 116 | 56.7 - 201 | 54.1 - 215 |
| `peak_rate_rel_p5` | 0.295 - 1.95; 1.57 | 1.31 - 1.59 | 0.295 - 1.95 |
| `peak_rate_rel_p50` | 1.07 - 4.4; 1.82 | 1.45 - 4.4 | 1.07 - 2.59 |
| `peak_rate_rel_p95` | 1.11 - 16.4; 3.82 | 3.92 - 16.4 | 1.11 - 4.76 |
| `rate_active_p25` | 0.131 - 2.81; 2.38 | 0.131 - 0.231 | 1.99 - 2.81 |
| `rate_active_p5` | 0.00325 - 0.864; 0.369 | 0.00325 - 0.00809 | 0.256 - 0.864 |
| `rate_active_p50` | 0.833 - 9.52; 3.87 | 0.833 - 1.26 | 3.45 - 9.52 |
| `rate_active_p75` | 3.23 - 32.9; 7.8 | 3.23 - 3.95 | 5.04 - 32.9 |
| `rate_active_p95` | 9.15 - 118; 11.9 | 10.3 - 11 | 9.15 - 118 |
| `rate_active_p99` | 14.9 - 190; 17.2 | 14.9 - 17.5 | 16.4 - 190 |
| `rate_active_rel_p25` | 0.0107 - 0.172; 0.0165 | 0.0107 - 0.016 | 0.0147 - 0.172 |
| `rate_active_rel_p5` | 2.66e-04 - 0.052; 0.00257 | 2.66e-04 - 5.59e-04 | 0.00137 - 0.052 |
| `rate_active_rel_p50` | 0.0456 - 0.259; 0.0777 | 0.068 - 0.0872 | 0.0456 - 0.259 |
| `rate_active_rel_p75` | 0.111 - 0.52; 0.269 | 0.265 - 0.273 | 0.111 - 0.52 |
| `rate_active_rel_p95` | 0.305 - 0.85; 0.742 | 0.762 - 0.85 | 0.305 - 0.766 |
| `rate_active_rel_p99` | 1.01 - 1.26; 1.03 | 1.21 - 1.26 | 1.01 - 1.05 |
| `s_x` | 12.2 - 187; 16.4 | 12.2 - 14.5 | 16.1 - 187 |
| `s_y` | 4.5 - 130; 10.7 | 4.5 - 12.2 | 7.89 - 130 |

### Dimensionality

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `dim_effect_x_n90` | 1 - 15; 2 | 2 - 15 | 1 - 2 |
| `dim_effect_x_n95` | 1 - 24; 2 | 2 - 24 | 1 - 3 |
| `dim_effect_x_n99` | 2 - 43; 3 | 6 - 43 | 2 - 4 |
| `dim_effect_x_pr` | 1.11 - 8.15; 1.34 | 1.23 - 8.15 | 1.11 - 1.86 |
| `dim_x_pooled_all_n90` | 1 - 9; 2 | 6 - 9 | 1 - 2 |
| `dim_x_pooled_all_n95` | 2 - 28; 2 | 9 - 28 | 2 - 3 |
| `dim_x_pooled_all_n99` | 2 - 89; 3 | 30 - 89 | 2 - 3 |
| `dim_x_pooled_all_pr` | 1.13 - 3.51; 1.27 | 2.44 - 3.51 | 1.13 - 1.56 |
| `dim_x_pooled_all_std_pr` | 1.55 - 15.2; 2.05 | 8.62 - 15.2 | 1.55 - 2.17 |
| `dim_x_pooled_obs_n90` | 1 - 10; 1.5 | 3 - 10 | 1 - 2 |
| `dim_x_pooled_obs_n95` | 1 - 27; 2 | 5 - 27 | 1 - 2 |
| `dim_x_pooled_obs_n99` | 2 - 72; 3 | 20 - 72 | 2 - 3 |
| `dim_x_pooled_obs_pr` | 1.09 - 2.65; 1.23 | 1.46 - 2.65 | 1.09 - 1.45 |
| `dim_x_pooled_obs_std_pr` | 1.4 - 10.1; 1.69 | 6.95 - 10.1 | 1.4 - 1.72 |
| `dim_x_traj_n90` | 1 - 3; 2 | 3 - 3 | 1 - 2 |
| `dim_x_traj_n95` | 2 - 3; 2 | 3 - 3 | 2 - 2 |
| `dim_x_traj_n99` | 2 - 5; 2 | 5 - 5 | 2 - 3 |
| `dim_x_traj_pr` | 1.11 - 2.34; 1.26 | 2.26 - 2.34 | 1.11 - 1.45 |
| `dim_x_traj_std_pr` | 1.47 - 3.24; 1.82 | 3.01 - 3.24 | 1.47 - 1.85 |
| `dim_y_traj_n90` | 1 - 2; 1 | 1 - 2 | 1 - 1 |
| `dim_y_traj_n95` | 1 - 2; 1 | 1 - 2 | 1 - 2 |
| `dim_y_traj_n99` | 1 - 3; 2 | 2 - 3 | 1 - 2 |
| `dim_y_traj_pr` | 1.02 - 1.36; 1.06 | 1.06 - 1.36 | 1.02 - 1.11 |
| `effect_energy_outside_passive95` | 0.00797 - 0.833; 0.118 | 0.406 - 0.833 | 0.00797 - 0.306 |

### Timescales and spectra

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `acf_censored_frac` | 0 - 0; 0 | 0 - 0 | 0 - 0 |
| `acf_decay_s_median` | 0.0115 - 0.0291; 0.016 | 0.0155 - 0.0169 | 0.0115 - 0.0291 |
| `acf_decay_s_p10` | 0.0105 - 0.0245; 0.0115 | 0.0111 - 0.0115 | 0.0105 - 0.0245 |
| `acf_decay_s_p90` | 0.0231 - 0.174; 0.036 | 0.0231 - 0.0235 | 0.0257 - 0.174 |
| `onset_latency_10pct_s` | 0.022 - 0.054; 0.029 | 0.022 - 0.024 | 0.025 - 0.054 |
| `spec_x_centroid` | 6.36 - 16.5; 11.5 | 10.5 - 11.8 | 6.36 - 16.5 |
| `spec_x_f05` | 0.977 - 15.6; 5.86 | 0.977 - 0.977 | 4.88 - 15.6 |
| `spec_x_f50` | 6.35 - 16.6; 10.7 | 10.7 - 10.7 | 6.35 - 16.6 |
| `spec_x_f95` | 7.81 - 24.4; 16.1 | 24.4 - 24.4 | 7.81 - 17.6 |
| `spec_x_f_peak` | 6.84 - 16.6; 10.3 | 8.79 - 10.7 | 6.84 - 16.6 |
| `spec_x_oscillatory_frac` | 0.976 - 1; 0.988 | 1 - 1 | 0.976 - 0.992 |
| `spec_x_prominence_log10` | 6.91 - 11; 10.1 | 6.91 - 6.99 | 9.61 - 11 |
| `spec_y_centroid` | 6.87 - 14.8; 12 | 11.7 - 12.6 | 6.87 - 14.8 |
| `spec_y_f05` | 0.977 - 13.7; 0.977 | 0.977 - 0.977 | 0.977 - 13.7 |
| `spec_y_f50` | 6.84 - 15.6; 10.7 | 10.7 - 10.7 | 6.84 - 15.6 |
| `spec_y_f95` | 13.7 - 28.3; 16.1 | 24.4 - 28.3 | 13.7 - 17.6 |
| `spec_y_f_peak` | 0.977 - 14.6; 10.3 | 9.77 - 10.7 | 0.977 - 14.6 |
| `spec_y_oscillatory_frac` | 0.929 - 0.992; 0.961 | 0.952 - 0.979 | 0.929 - 0.992 |
| `spec_y_prominence_log10` | 7.74 - 11.3; 9.41 | 8.99 - 9.47 | 7.74 - 11.3 |

### Intervention effects

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `current_abs_p5` | 7.91 - 33.9; 12 | 8.09 - 11.4 | 7.91 - 33.9 |
| `current_abs_p50` | 14.1 - 33.9; 20.5 | 14.1 - 29.2 | 14.8 - 33.9 |
| `current_abs_p95` | 22.6 - 35.2; 29.3 | 26.3 - 35 | 22.6 - 35.2 |
| `current_duration_s_p5` | 0.0119 - 0.127; 0.027 | 0.0208 - 0.0855 | 0.0119 - 0.127 |
| `current_duration_s_p50` | 0.0285 - 0.127; 0.0632 | 0.0565 - 0.103 | 0.0285 - 0.127 |
| `current_duration_s_p95` | 0.0363 - 0.127; 0.0922 | 0.112 - 0.124 | 0.0363 - 0.127 |
| `decay_x_censored_frac` | 0 - 0.353; 0.068 | 0.0357 - 0.0645 | 0 - 0.353 |
| `decay_x_censored_frac_current` | 0 - 0.5; 0 | 0 - 0 | 0 - 0.5 |
| `decay_x_censored_frac_kick` | 0 - 0.286; 0.0667 | 0.0667 - 0.0667 | 0 - 0.286 |
| `decay_x_censored_frac_silence` | 0 - 0.333; 0 | 0 - 0.143 | 0 - 0.333 |
| `decay_x_s_current_median` | 0.0198 - 0.408; 0.0386 | 0.0198 - 0.0262 | 0.0288 - 0.408 |
| `decay_x_s_kick_median` | 0.0165 - 0.0433; 0.028 | 0.0204 - 0.0247 | 0.0165 - 0.0433 |
| `decay_x_s_median` | 0.0215 - 0.0525; 0.0283 | 0.0215 - 0.0251 | 0.0231 - 0.0525 |
| `decay_x_s_silence_median` | 0.0159 - 0.0456; 0.0353 | 0.0343 - 0.0381 | 0.0159 - 0.0456 |
| `decay_y_s_current_median` | 0.00839 - 0.0256; 0.0189 | 0.00839 - 0.0235 | 0.0116 - 0.0256 |
| `decay_y_s_kick_median` | 0.00838 - 0.041; 0.02 | 0.00838 - 0.018 | 0.0136 - 0.041 |
| `decay_y_s_median` | 0.00882 - 0.0374; 0.0174 | 0.00882 - 0.0144 | 0.015 - 0.0374 |
| `decay_y_s_silence_median` | 0.00836 - 0.0446; 0.0211 | 0.00836 - 0.00929 | 0.0117 - 0.0446 |
| `eff_rel_x_current_p25` | 0.229 - 2.21; 0.424 | 0.229 - 0.4 | 0.301 - 2.21 |
| `eff_rel_x_current_p5` | 0.11 - 2.11; 0.189 | 0.11 - 0.156 | 0.111 - 2.11 |
| `eff_rel_x_current_p50` | 0.375 - 8.71; 0.703 | 0.571 - 0.717 | 0.375 - 8.71 |
| `eff_rel_x_current_p75` | 0.452 - 18.2; 1.5 | 1.09 - 1.57 | 0.452 - 18.2 |
| `eff_rel_x_current_p95` | 0.826 - 66.6; 1.93 | 1.29 - 18.1 | 0.826 - 66.6 |
| `eff_rel_x_kick_p25` | 0.0837 - 6.01; 0.695 | 0.0837 - 0.266 | 0.474 - 6.01 |
| `eff_rel_x_kick_p5` | 0.00164 - 4.31; 0.379 | 0.00164 - 0.164 | 0.172 - 4.31 |
| `eff_rel_x_kick_p50` | 0.209 - 19.2; 0.956 | 0.209 - 0.34 | 0.536 - 19.2 |
| `eff_rel_x_kick_p75` | 0.271 - 32.2; 1.5 | 0.271 - 0.43 | 1.19 - 32.2 |
| `eff_rel_x_kick_p95` | 0.548 - 93.6; 2.98 | 0.548 - 8.74 | 1.54 - 93.6 |
| `eff_rel_x_p25` | 0.0083 - 4.52; 0.607 | 0.0083 - 0.0686 | 0.45 - 4.52 |
| `eff_rel_x_p5` | 7.73e-04 - 2.14; 0.271 | 7.73e-04 - 0.00261 | 0.0961 - 2.14 |
| `eff_rel_x_p50` | 0.207 - 21.5; 1.26 | 0.207 - 0.288 | 1.04 - 21.5 |
| `eff_rel_x_p75` | 0.4 - 134; 1.78 | 0.4 - 0.675 | 1.68 - 134 |
| `eff_rel_x_p95` | 1.16 - 391; 5.69 | 1.16 - 3.01 | 3.73 - 391 |
| `eff_rel_x_silence_p25` | 0.00149 - 124; 1.64 | 0.00149 - 0.00305 | 1.48 - 124 |
| `eff_rel_x_silence_p5` | 6.48e-04 - 44; 1.4 | 6.48e-04 - 0.00111 | 1.24 - 44 |
| `eff_rel_x_silence_p50` | 0.00415 - 225; 2.07 | 0.00415 - 0.00639 | 1.81 - 225 |
| `eff_rel_x_silence_p75` | 0.11 - 323; 3.07 | 0.11 - 0.459 | 1.88 - 323 |
| `eff_rel_x_silence_p95` | 0.759 - 1.04e+03; 7.59 | 0.759 - 1.2 | 3.66 - 1.04e+03 |
| `eff_rel_y_current_p25` | 0.0977 - 2.24; 0.439 | 0.0977 - 0.152 | 0.307 - 2.24 |
| `eff_rel_y_current_p5` | 0.00832 - 2.15; 0.189 | 0.00832 - 0.0461 | 0.107 - 2.15 |
| `eff_rel_y_current_p50` | 0.212 - 8.73; 0.562 | 0.212 - 0.255 | 0.369 - 8.73 |
| `eff_rel_y_current_p75` | 0.452 - 19; 0.902 | 0.496 - 1.05 | 0.452 - 19 |
| `eff_rel_y_current_p95` | 0.822 - 67.3; 1.82 | 0.949 - 67.3 | 0.822 - 60.9 |
| `eff_rel_y_kick_p25` | 0.00231 - 6.53; 0.698 | 0.00231 - 0.0818 | 0.467 - 6.53 |
| `eff_rel_y_kick_p5` | 6.45e-04 - 4.7; 0.379 | 6.45e-04 - 0.0014 | 0.128 - 4.7 |
| `eff_rel_y_kick_p50` | 0.0142 - 21.6; 0.944 | 0.0142 - 0.21 | 0.529 - 21.6 |
| `eff_rel_y_kick_p75` | 0.113 - 40.4; 1.57 | 0.113 - 0.243 | 1.22 - 40.4 |
| `eff_rel_y_kick_p95` | 0.44 - 56.7; 2.6 | 0.44 - 1.26 | 1.54 - 56.7 |
| `eff_rel_y_p25` | 0.00219 - 5.1; 0.613 | 0.00219 - 0.00462 | 0.448 - 5.1 |
| `eff_rel_y_p5` | 7.66e-04 - 2.19; 0.27 | 7.66e-04 - 0.00103 | 0.0519 - 2.19 |
| `eff_rel_y_p50` | 0.0161 - 23.4; 1.11 | 0.0161 - 0.158 | 1.05 - 23.4 |
| `eff_rel_y_p75` | 0.243 - 105; 1.88 | 0.243 - 0.34 | 1.75 - 105 |
| `eff_rel_y_p95` | 0.808 - 672; 10.4 | 0.808 - 1.44 | 4.54 - 672 |
| `eff_rel_y_silence_p25` | 0.00132 - 105; 1.76 | 0.00132 - 0.00205 | 1.35 - 105 |
| `eff_rel_y_silence_p5` | 5.96e-04 - 47.7; 1.42 | 5.96e-04 - 0.00116 | 1.08 - 47.7 |
| `eff_rel_y_silence_p50` | 0.00292 - 286; 2.07 | 0.00292 - 0.00467 | 1.78 - 286 |
| `eff_rel_y_silence_p75` | 0.0213 - 556; 3.52 | 0.0213 - 0.395 | 1.89 - 556 |
| `eff_rel_y_silence_p95` | 0.35 - 2.08e+03; 13 | 0.35 - 1.13 | 3.87 - 2.08e+03 |
| `eff_rms_x_rel_scale_current_p25` | 0.0076 - 0.16; 0.0269 | 0.0147 - 0.0257 | 0.0076 - 0.16 |
| `eff_rms_x_rel_scale_current_p5` | 0.00431 - 0.14; 0.0114 | 0.00691 - 0.00959 | 0.00431 - 0.14 |
| `eff_rms_x_rel_scale_current_p50` | 0.0289 - 0.163; 0.0454 | 0.0346 - 0.0469 | 0.0289 - 0.163 |
| `eff_rms_x_rel_scale_current_p75` | 0.0317 - 0.176; 0.0722 | 0.0688 - 0.0746 | 0.0317 - 0.176 |
| `eff_rms_x_rel_scale_current_p95` | 0.0436 - 1.2; 0.105 | 0.0904 - 1.2 | 0.0436 - 0.208 |
| `eff_rms_x_rel_scale_kick_p25` | 0.00565 - 0.216; 0.0587 | 0.00565 - 0.0185 | 0.0343 - 0.216 |
| `eff_rms_x_rel_scale_kick_p5` | 1.09e-04 - 0.174; 0.0376 | 1.09e-04 - 0.0086 | 0.0145 - 0.174 |
| `eff_rms_x_rel_scale_kick_p50` | 0.0141 - 0.269; 0.0841 | 0.0141 - 0.0206 | 0.0486 - 0.269 |
| `eff_rms_x_rel_scale_kick_p75` | 0.0168 - 0.296; 0.116 | 0.0168 - 0.0218 | 0.0591 - 0.296 |
| `eff_rms_x_rel_scale_kick_p95` | 0.029 - 0.364; 0.147 | 0.029 - 0.0917 | 0.0907 - 0.364 |
| `eff_rms_x_rel_scale_p25` | 6.56e-04 - 0.161; 0.0507 | 6.56e-04 - 0.00359 | 0.0345 - 0.161 |
| `eff_rms_x_rel_scale_p5` | 5.44e-05 - 0.141; 0.0151 | 5.44e-05 - 1.23e-04 | 0.00602 - 0.141 |
| `eff_rms_x_rel_scale_p50` | 0.0123 - 0.217; 0.0846 | 0.0123 - 0.0197 | 0.0547 - 0.217 |
| `eff_rms_x_rel_scale_p75` | 0.0283 - 0.358; 0.135 | 0.0283 - 0.0289 | 0.0871 - 0.358 |
| `eff_rms_x_rel_scale_p95` | 0.0708 - 0.986; 0.424 | 0.0708 - 0.0806 | 0.191 - 0.986 |
| `eff_rms_x_rel_scale_silence_p25` | 1.25e-04 - 0.358; 0.11 | 1.25e-04 - 1.77e-04 | 0.0852 - 0.358 |
| `eff_rms_x_rel_scale_silence_p5` | 4.56e-05 - 0.216; 0.0884 | 4.56e-05 - 7.58e-05 | 0.079 - 0.216 |
| `eff_rms_x_rel_scale_silence_p50` | 2.05e-04 - 0.378; 0.163 | 2.05e-04 - 3.93e-04 | 0.0889 - 0.378 |
| `eff_rms_x_rel_scale_silence_p75` | 0.00704 - 0.694; 0.2 | 0.00704 - 0.0241 | 0.167 - 0.694 |
| `eff_rms_x_rel_scale_silence_p95` | 0.0442 - 1.13; 0.479 | 0.0442 - 0.0571 | 0.287 - 1.13 |
| `eff_rms_y_rel_scale_current_p25` | 0.00636 - 0.0563; 0.0151 | 0.00841 - 0.0175 | 0.00636 - 0.0563 |
| `eff_rms_y_rel_scale_current_p5` | 0.00102 - 0.0552; 0.00598 | 0.00102 - 0.00523 | 0.00383 - 0.0552 |
| `eff_rms_y_rel_scale_current_p50` | 0.0136 - 0.0645; 0.0321 | 0.0204 - 0.0278 | 0.0136 - 0.0645 |
| `eff_rms_y_rel_scale_current_p75` | 0.0147 - 0.0706; 0.0518 | 0.0447 - 0.0648 | 0.0147 - 0.0706 |
| `eff_rms_y_rel_scale_current_p95` | 0.023 - 8.21; 0.0812 | 0.101 - 8.21 | 0.023 - 0.0899 |
| `eff_rms_y_rel_scale_kick_p25` | 2.01e-04 - 0.0883; 0.035 | 2.01e-04 - 0.00409 | 0.024 - 0.0883 |
| `eff_rms_y_rel_scale_kick_p5` | 5.30e-05 - 0.0712; 0.0196 | 5.30e-05 - 1.19e-04 | 0.0124 - 0.0712 |
| `eff_rms_y_rel_scale_kick_p50` | 0.00126 - 0.146; 0.0436 | 0.00126 - 0.0148 | 0.0338 - 0.146 |
| `eff_rms_y_rel_scale_kick_p75` | 0.0107 - 0.168; 0.0756 | 0.0107 - 0.0223 | 0.0415 - 0.168 |
| `eff_rms_y_rel_scale_kick_p95` | 0.0516 - 0.3; 0.111 | 0.0541 - 0.167 | 0.0516 - 0.3 |
| `eff_rms_y_rel_scale_p25` | 2.03e-04 - 0.0696; 0.0365 | 2.03e-04 - 4.88e-04 | 0.0173 - 0.0696 |
| `eff_rms_y_rel_scale_p5` | 4.90e-05 - 0.0559; 0.00803 | 4.90e-05 - 1.19e-04 | 0.00573 - 0.0559 |
| `eff_rms_y_rel_scale_p50` | 0.00157 - 0.102; 0.0575 | 0.00157 - 0.0146 | 0.0346 - 0.102 |
| `eff_rms_y_rel_scale_p75` | 0.0203 - 0.219; 0.101 | 0.0203 - 0.0297 | 0.0704 - 0.219 |
| `eff_rms_y_rel_scale_p95` | 0.0716 - 0.922; 0.321 | 0.0716 - 0.134 | 0.18 - 0.922 |
| `eff_rms_y_rel_scale_silence_p25` | 1.45e-04 - 0.217; 0.066 | 1.45e-04 - 2.06e-04 | 0.048 - 0.217 |
| `eff_rms_y_rel_scale_silence_p5` | 3.90e-05 - 0.187; 0.0488 | 3.90e-05 - 1.32e-04 | 0.0358 - 0.187 |
| `eff_rms_y_rel_scale_silence_p50` | 2.85e-04 - 0.273; 0.111 | 2.85e-04 - 4.91e-04 | 0.0715 - 0.273 |
| `eff_rms_y_rel_scale_silence_p75` | 0.00156 - 0.567; 0.176 | 0.00156 - 0.0331 | 0.0976 - 0.567 |
| `eff_rms_y_rel_scale_silence_p95` | 0.0401 - 1.51; 0.396 | 0.0401 - 0.0753 | 0.136 - 1.51 |
| `effect_end_over_peak_current_median` | 0.00986 - 0.856; 0.251 | 0.00986 - 0.231 | 0.201 - 0.856 |
| `effect_end_over_peak_kick_median` | 0.00675 - 0.698; 0.185 | 0.00675 - 0.0228 | 0.0242 - 0.698 |
| `effect_end_over_peak_median` | 0.044 - 0.499; 0.281 | 0.044 - 0.129 | 0.191 - 0.499 |
| `effect_end_over_peak_silence_median` | 0.111 - 0.796; 0.303 | 0.239 - 0.255 | 0.111 - 0.796 |
| `frac_eff_rel_x_below_0.001` | 0 - 0.075; 0 | 0 - 0.075 | 0 - 0 |
| `frac_eff_rel_x_below_0.001_current` | 0 - 0; 0 | 0 - 0 | 0 - 0 |
| `frac_eff_rel_x_below_0.001_kick` | 0 - 0.0667; 0 | 0 - 0.0667 | 0 - 0 |
| `frac_eff_rel_x_below_0.001_silence` | 0 - 0.133; 0 | 0 - 0.133 | 0 - 0 |
| `frac_eff_rel_x_below_0.01` | 0 - 0.275; 0 | 0.2 - 0.275 | 0 - 0 |
| `frac_eff_rel_x_below_0.01_current` | 0 - 0.1; 0 | 0 - 0.1 | 0 - 0 |
| `frac_eff_rel_x_below_0.01_kick` | 0 - 0.133; 0 | 0 - 0.133 | 0 - 0 |
| `frac_eff_rel_x_below_0.01_silence` | 0 - 0.6; 0 | 0.533 - 0.6 | 0 - 0 |
| `frac_eff_rel_x_below_0.1` | 0 - 0.375; 0 | 0.3 - 0.375 | 0 - 0.0526 |
| `frac_eff_rel_x_below_0.1_current` | 0 - 0.2; 0 | 0 - 0.1 | 0 - 0.2 |
| `frac_eff_rel_x_below_0.1_kick` | 0 - 0.267; 0 | 0.0667 - 0.267 | 0 - 0 |
| `frac_eff_rel_x_below_0.1_silence` | 0 - 0.733; 0 | 0.667 - 0.733 | 0 - 0 |
| `frac_eff_rel_y_below_0.001` | 0 - 0.1; 0 | 0.05 - 0.1 | 0 - 0 |
| `frac_eff_rel_y_below_0.001_current` | 0 - 0; 0 | 0 - 0 | 0 - 0 |
| `frac_eff_rel_y_below_0.001_kick` | 0 - 0.133; 0 | 0 - 0.133 | 0 - 0 |
| `frac_eff_rel_y_below_0.001_silence` | 0 - 0.2; 0 | 0 - 0.2 | 0 - 0 |
| `frac_eff_rel_y_below_0.01` | 0 - 0.45; 0 | 0.35 - 0.45 | 0 - 0 |
| `frac_eff_rel_y_below_0.01_current` | 0 - 0.1; 0 | 0 - 0.1 | 0 - 0 |
| `frac_eff_rel_y_below_0.01_kick` | 0 - 0.467; 0 | 0.133 - 0.467 | 0 - 0 |
| `frac_eff_rel_y_below_0.01_silence` | 0 - 0.733; 0 | 0.733 - 0.733 | 0 - 0 |
| `frac_eff_rel_y_below_0.1` | 0 - 0.65; 0.0263 | 0.425 - 0.65 | 0 - 0.105 |
| `frac_eff_rel_y_below_0.1_current` | 0 - 0.3; 0.1 | 0.2 - 0.3 | 0 - 0.2 |
| `frac_eff_rel_y_below_0.1_kick` | 0 - 0.733; 0 | 0.267 - 0.733 | 0 - 0.143 |
| `frac_eff_rel_y_below_0.1_silence` | 0 - 0.867; 0 | 0.733 - 0.867 | 0 - 0 |
| `kick_rel_scale_p5` | 0.0528 - 1.34; 0.588 | 0.536 - 1.34 | 0.0528 - 1.15 |
| `kick_rel_scale_p50` | 0.0938 - 1.99; 1.37 | 1.57 - 1.99 | 0.0938 - 1.73 |
| `kick_rel_scale_p95` | 0.11 - 2.25; 1.47 | 1.95 - 2.25 | 0.11 - 1.77 |
| `latency_y_peak_s_current_median` | 0.027 - 0.168; 0.0715 | 0.063 - 0.144 | 0.027 - 0.168 |
| `latency_y_peak_s_kick_median` | 0.025 - 0.196; 0.0455 | 0.045 - 0.196 | 0.025 - 0.166 |
| `latency_y_peak_s_median` | 0.053 - 0.384; 0.129 | 0.208 - 0.384 | 0.053 - 0.181 |
| `latency_y_peak_s_silence_median` | 0.214 - 0.76; 0.288 | 0.629 - 0.76 | 0.214 - 0.672 |
| `persistence_ratio_kick` | 0.919 - 2.11; 1.15 | 1.03 - 1.23 | 0.919 - 2.11 |
| `resp_frac_10pct_any` | 0.2 - 1; 0.767 | 0.2 - 0.308 | 0.667 - 1 |
| `resp_frac_10pct_current_any` | 0 - 1; 0.45 | 0 - 0.4 | 0 - 1 |
| `resp_frac_10pct_current_mean` | 0 - 1; 0.106 | 0 - 0.0128 | 0 - 1 |
| `resp_frac_10pct_current_median` | 0 - 1; 0.1 | 0 - 0 | 0 - 1 |
| `resp_frac_10pct_current_p90` | 0 - 1; 0.118 | 0 - 0.0357 | 0 - 1 |
| `resp_frac_10pct_kick_any` | 0 - 1; 0.417 | 0.2 - 0.333 | 0 - 1 |
| `resp_frac_10pct_kick_mean` | 0 - 1; 0.171 | 0.00102 - 0.00865 | 0 - 1 |
| `resp_frac_10pct_kick_median` | 0 - 1; 0.167 | 0 - 0 | 0 - 1 |
| `resp_frac_10pct_kick_p90` | 0 - 1; 0.313 | 0.00306 - 0.0259 | 0 - 1 |
| `resp_frac_10pct_mean` | 0.0136 - 1; 0.568 | 0.0136 - 0.0281 | 0.556 - 1 |
| `resp_frac_10pct_median` | 0 - 1; 0.683 | 0 - 0 | 0.667 - 1 |
| `resp_frac_10pct_p90` | 0.019 - 1; 1 | 0.019 - 0.137 | 1 - 1 |
| `resp_frac_10pct_silence_any` | 0.2 - 1; 1 | 0.2 - 0.267 | 1 - 1 |
| `resp_frac_10pct_silence_mean` | 0.0192 - 1; 0.829 | 0.0192 - 0.0412 | 0.762 - 1 |
| `resp_frac_10pct_silence_median` | 0 - 1; 0.9 | 0 - 0 | 0.667 - 1 |
| `resp_frac_10pct_silence_p90` | 0.05 - 1; 1 | 0.05 - 0.148 | 1 - 1 |
| `resp_frac_1pct_any` | 0.417 - 1; 1 | 0.417 - 0.462 | 0.933 - 1 |
| `resp_frac_1pct_current_any` | 0.5 - 1; 1 | 0.5 - 0.8 | 0.667 - 1 |
| `resp_frac_1pct_current_mean` | 0.0554 - 1; 0.653 | 0.0554 - 0.186 | 0.444 - 1 |
| `resp_frac_1pct_current_median` | 0.0165 - 1; 0.708 | 0.0165 - 0.181 | 0.667 - 1 |
| `resp_frac_1pct_current_p90` | 0.142 - 1; 0.808 | 0.142 - 0.376 | 0.667 - 1 |
| `resp_frac_1pct_kick_any` | 0.4 - 1; 1 | 0.4 - 0.5 | 1 - 1 |
| `resp_frac_1pct_kick_mean` | 0.0357 - 1; 0.817 | 0.0357 - 0.0637 | 0.8 - 1 |
| `resp_frac_1pct_kick_median` | 0 - 1; 0.817 | 0 - 0.0165 | 0.8 - 1 |
| `resp_frac_1pct_kick_p90` | 0.106 - 1; 0.883 | 0.106 - 0.175 | 0.8 - 1 |
| `resp_frac_1pct_mean` | 0.0634 - 1; 0.917 | 0.0634 - 0.0867 | 0.861 - 1 |
| `resp_frac_1pct_median` | 0 - 1; 1 | 0 - 0 | 1 - 1 |
| `resp_frac_1pct_p90` | 0.242 - 1; 1 | 0.242 - 0.299 | 1 - 1 |
| `resp_frac_1pct_silence_any` | 0.333 - 1; 1 | 0.333 - 0.4 | 1 - 1 |
| `resp_frac_1pct_silence_mean` | 0.0641 - 1; 1 | 0.0641 - 0.0772 | 1 - 1 |
| `resp_frac_1pct_silence_median` | 0 - 1; 1 | 0 - 0 | 1 - 1 |
| `resp_frac_1pct_silence_p90` | 0.288 - 1; 1 | 0.288 - 0.292 | 1 - 1 |
| `resp_frac_y_1pct_any` | 0.308 - 1; 1 | 0.308 - 0.36 | 0.917 - 1 |
| `resp_frac_y_1pct_current_any` | 0.5 - 1; 1 | 0.5 - 0.6 | 0.667 - 1 |
| `resp_frac_y_1pct_current_mean` | 0.138 - 0.5; 0.18 | 0.138 - 0.14 | 0.15 - 0.5 |
| `resp_frac_y_1pct_current_median` | 0.111 - 0.5; 0.2 | 0.111 - 0.2 | 0.15 - 0.5 |
| `resp_frac_y_1pct_current_p90` | 0.15 - 0.5; 0.247 | 0.26 - 0.3 | 0.15 - 0.5 |
| `resp_frac_y_1pct_kick_any` | 0.167 - 1; 1 | 0.167 - 0.5 | 1 - 1 |
| `resp_frac_y_1pct_kick_mean` | 0.0667 - 0.511; 0.211 | 0.0667 - 0.133 | 0.2 - 0.511 |
| `resp_frac_y_1pct_kick_median` | 0 - 0.556; 0.211 | 0 - 0.05 | 0.2 - 0.556 |
| `resp_frac_y_1pct_kick_p90` | 0.2 - 0.556; 0.286 | 0.2 - 0.35 | 0.2 - 0.556 |
| `resp_frac_y_1pct_mean` | 0.0833 - 0.492; 0.249 | 0.0833 - 0.102 | 0.194 - 0.492 |
| `resp_frac_y_1pct_median` | 0 - 0.556; 0.211 | 0 - 0 | 0.15 - 0.556 |
| `resp_frac_y_1pct_p90` | 0.222 - 0.79; 0.35 | 0.222 - 0.35 | 0.26 - 0.79 |
| `resp_frac_y_1pct_silence_any` | 0.267 - 1; 1 | 0.267 - 0.267 | 1 - 1 |
| `resp_frac_y_1pct_silence_mean` | 0.0667 - 0.614; 0.279 | 0.0667 - 0.08 | 0.207 - 0.614 |
| `resp_frac_y_1pct_silence_median` | 0 - 0.556; 0.211 | 0 - 0 | 0.2 - 0.556 |
| `resp_frac_y_1pct_silence_p90` | 0.222 - 0.8; 0.369 | 0.222 - 0.36 | 0.27 - 0.8 |
| `self_decay_s_kick_median` | 0.0145 - 0.045; 0.02 | 0.019 - 0.021 | 0.0145 - 0.045 |
| `self_decay_s_median` | 0.0145 - 0.045; 0.02 | 0.019 - 0.021 | 0.0145 - 0.045 |
| `snr_floor_x_current_median` | 142 - 4.18e+03; 951 | 142 - 249 | 438 - 4.18e+03 |
| `snr_floor_x_kick_median` | 62.5 - 9.81e+03; 1.33e+03 | 62.5 - 101 | 533 - 9.81e+03 |
| `snr_floor_x_median` | 59.5 - 1.08e+04; 1.44e+03 | 59.5 - 100 | 1.04e+03 - 1.08e+04 |
| `snr_floor_x_silence_median` | 0.993 - 3.35e+04; 2.05e+03 | 0.993 - 2.06 | 1.65e+03 - 3.35e+04 |
| `snr_param_x_median` | 0.157 - 2.29; 0.817 | 0.157 - 0.236 | 0.503 - 2.29 |
| `snr_param_x_p10` | 0.00135 - 1.47; 0.206 | 0.00135 - 0.00228 | 0.114 - 1.47 |
| `snr_param_y_median` | 0.0132 - 0.906; 0.566 | 0.0132 - 0.117 | 0.316 - 0.906 |
| `snr_param_y_p10` | 0.001 - 0.623; 0.147 | 0.001 - 0.00121 | 0.0684 - 0.623 |

### Noise floor

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `noise_floor_abs` | 3.07e-04 - 0.00732; 0.0021 | 0.00201 - 0.00407 | 3.07e-04 - 0.00732 |
| `noise_floor_pre_event_maxabs` | 3.07e-04 - 0.00732; 0.0021 | 0.00201 - 0.00407 | 3.07e-04 - 0.00732 |
| `noise_floor_rel_scale` | 7.52e-06 - 3.30e-04; 1.21e-04 | 1.39e-04 - 3.30e-04 | 7.52e-06 - 1.79e-04 |

### Parameter uncertainty

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `params_param_spread_x_abs_rms` | 0.957 - 32.2; 1.44 | 0.957 - 1.22 | 1.24 - 32.2 |
| `params_param_spread_x_rel_dynamics` | 1.31 - 5.02; 2.48 | 2.44 - 2.79 | 1.31 - 5.02 |
| `params_param_spread_x_rel_level` | 0.203 - 1.17; 0.41 | 0.397 - 0.426 | 0.203 - 1.17 |
| `params_param_spread_y_abs_rms` | 0.553 - 17.2; 1.12 | 0.553 - 1.29 | 0.815 - 17.2 |
| `params_param_spread_y_rel_dynamics` | 1.74 - 6.04; 2.86 | 3.02 - 4.38 | 1.74 - 6.04 |
| `params_param_spread_y_rel_level` | 0.316 - 1.42; 0.757 | 0.746 - 0.97 | 0.316 - 1.42 |
| `wnoise_param_spread_x_abs_rms` | 1.09 - 43.1; 1.5 | 1.09 - 1.41 | 1.32 - 43.1 |
| `wnoise_param_spread_x_rel_dynamics` | 1.41 - 4.37; 2.62 | 2.75 - 2.89 | 1.41 - 4.37 |
| `wnoise_param_spread_x_rel_level` | 0.223 - 1.11; 0.45 | 0.446 - 0.481 | 0.223 - 1.11 |
| `wnoise_param_spread_y_abs_rms` | 0.614 - 21.3; 1.24 | 0.614 - 1.6 | 0.739 - 21.3 |
| `wnoise_param_spread_y_rel_dynamics` | 1.72 - 4.8; 3.01 | 3.63 - 4.54 | 1.72 - 4.8 |
| `wnoise_param_spread_y_rel_level` | 0.319 - 1.24; 0.831 | 0.87 - 0.944 | 0.319 - 1.24 |
| `wnoise_sd_max` | 0.0705 - 0.0999; 0.0925 | 0.0978 - 0.0999 | 0.0705 - 0.0946 |

### Input

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `input_gain_elasticity_x` | 2.74 - 5.8; 3.68 | 3.42 - 3.87 | 2.74 - 5.8 |
| `input_gain_elasticity_y` | 1.69 - 6.14; 3.58 | 4.07 - 6.14 | 1.69 - 4.66 |
| `input_response_rms_x_rel_scale_median` | 0.0994 - 0.39; 0.215 | 0.203 - 0.215 | 0.0994 - 0.39 |
| `input_response_rms_y_rel_scale_median` | 0.0734 - 0.363; 0.162 | 0.124 - 0.173 | 0.0734 - 0.363 |
| `input_scale_max` | 1.3 - 1.4; 1.39 | 1.4 - 1.4 | 1.3 - 1.4 |
| `input_scale_min` | 0.604 - 0.65; 0.615 | 0.609 - 0.628 | 0.604 - 0.65 |

### Public protocol design (descriptive)

| statistic | all (min - max; median) | large | small |
|---|---|---|---|
| `design_current_abs_p5` | 5.72 - 8.67; 6.91 | 6.26 - 6.89 | 5.72 - 8.67 |
| `design_current_abs_p50` | 20.6 - 24.7; 23.3 | 23.1 - 23.5 | 20.6 - 24.7 |
| `design_current_abs_p95` | 35.3 - 39.3; 37.5 | 35.3 - 38.5 | 36.8 - 39.3 |
| `design_current_duration_s_p5` | 0.0148 - 0.0211; 0.0174 | 0.0149 - 0.0203 | 0.0148 - 0.0211 |
| `design_current_duration_s_p50` | 0.046 - 0.082; 0.0692 | 0.068 - 0.082 | 0.046 - 0.0755 |
| `design_current_duration_s_p95` | 0.128 - 0.148; 0.138 | 0.141 - 0.148 | 0.128 - 0.14 |
| `design_event_time_rel_p5` | 0.173 - 0.2; 0.187 | 0.173 - 0.194 | 0.173 - 0.2 |
| `design_event_time_rel_p50` | 0.433 - 0.523; 0.484 | 0.478 - 0.49 | 0.433 - 0.523 |
| `design_event_time_rel_p95` | 0.761 - 0.805; 0.783 | 0.761 - 0.795 | 0.77 - 0.805 |
| `design_kick_abs_p5` | 5.92 - 7.03; 6.24 | 6.08 - 6.36 | 5.92 - 7.03 |
| `design_kick_abs_p50` | 16.3 - 18.3; 17.1 | 16.9 - 18.3 | 16.3 - 18.1 |
| `design_kick_abs_p95` | 27.8 - 29.5; 28.5 | 28.6 - 29 | 27.8 - 29.5 |
| `design_silence_persistent_frac` | 0.378 - 0.627; 0.486 | 0.467 - 0.627 | 0.378 - 0.622 |

## Caveats

- The public trajectories are deterministic simulations. The measurable noise floor is the integration-path difference between an intervention trajectory and its twin before the first event (8e-6 to 3e-4 of the rate scale); observation noise is a benchmark parameter, not a property of the real systems.
- Current magnitudes are in the simulator's input units; their relation to a unit's threshold is not published, so only their effects are calibrated.
- Single-unit time constants are not published; persistence is estimated from the kicked unit's own decay (self_decay_s).
- Statistics from few pairs (19 per small system, 40 per large system) are noisy; the per-system values are medians over pairs.
- Oscillation: every real system oscillates (7-17 Hz). The autocorrelation decay is then about a quarter period, not a memory time.
- Ten systems in two classes are few; the recommended ranges widen the real range by a stated rule rather than fitting it.
