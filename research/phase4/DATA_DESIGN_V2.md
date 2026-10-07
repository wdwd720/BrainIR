# Dataset design v2 (fork E14, 2026-09-26; LOG P4-D36 / P4-D38)

Benchmark-side fixes of the round-2 reviews: T (truth audit) B2, B3, M1, M4 and the benchmark parts of B1; H N1, N5, N6; F minor
N-m4. The synthetic tiers are rebuilt by the orchestrator after the generator's revision; the real public data and the real Level B
sets were rebuilt here with the new design.

## Decisions

1. **No explicit initial state is a development or public-policy protocol, on any system** (T B3: setting a unit's initial value is
   bit-identical to a kick at t = 0, so r0 'state' exposed held-out targets, held-out kick families and hidden units; T B2: the
   benchmark's own passive 'obs.init' moved the hidden trap variable by 0.4-7x its scale in 22 of 23 trap systems).
   `sampling.normalize_capability` (re-exported by `suites`) sets `init.state = false` and `init.units = "observed"` for every system; the real capability
   (`systems.REAL_CAPABILITY`) likewise; the simulation service's public policy (`check_public`) already refuses r0 'state' when the
   capability says so. The engines still accept r0 'state' (orchestrator use only; no planned set uses it).
2. **'obs.init' = a restart from a nominal passive trajectory of the same system** (`suites.init_spec`, completed by `run_specs`):
   r0 = {"kind": "restart", "key": <the source's store key>, "t": <a sample time at 25-90 % of the source>}, with the source's
   parameter draw, weight noise and spread and a nominal stimulus schedule of its own. The concatenation of the source's schedule and
   this one is a trajectory from rest under a stimulus schedule, so the initial-condition variability of the passive data is
   genuinely passive (the traps hold for such data: T "checked and found sound"). Where: D0 (8 restarts from the 8 nominal draws),
   the public validation set, the passive test trajectories (each obs.init restarts from the nominal trajectory two positions
   before it), and the pools: the first source of every pool draw is a nominal trajectory and the draw's 'init' sources restart from
   it (the float64-continuation floor (b) is unchanged: nominal input, no event after the stimulus onset). Dependent trajectories are
   simulated after their sources, have no spare seeds, and are dropped (counted) when their source is dropped.
3. **Level C OOD 'altered initial conditions' use state carriers** (P4-D31) for synthetic and real systems
   (`suites.resolve_carrier_start`): the full microstate of a same-draw nominal trajectory at 30-80 % of its duration with half the
   observed units displaced by twice the development kick maximum (random signs), clipped to the unit's admissible range (synthetic:
   the generator's own per-unit range, orchestrator side; real: rates in [0, the engine's maximum initial rate]); real carriers are
   stored in the engine's sparse restart format (`suites.put_real_carrier`).
4. **Capability records carry system-wide values only** (T M1: per-unit admissible ranges and noise scales decoded unit roles at 93-100 %):
   per-unit `admissible_range` -> the system's [min, max]; per-unit `process_noise.unit_sd_per_sqrt_s` -> the median `sd_per_sqrt_s`;
   per-unit `init.units` -> "observed". `suites.assert_public_record` refuses any numeric list of length >= 3 in a capability (the
   declared per-unit fields are the record's observed / readout / target / member / edge lists and its public graph); real public
   records are checked too.
5. **Onset / twin check** (H N1): `run_specs` aborts a system's build when an intervention item differs from its twin in x or y at or
   before its onset sample (the earliest of the simulated and the told events); `verify_real_build.py` re-checks every stored item.
6. **Realized kick classes** (H N5): a kick item's magnitude class is the class of its REALIZED size where the simulator reports it
   (the real engine's `kicks_applied`; a synthetic generator reporting the same field): unclipped kicks keep the planned class; a
   clipped item takes the class nearest on a log scale to the median realized |kick| / m_s over its kicked units (the planned 'hi'
   class stays while the median is still inside hi_range); a simulator that reports only THAT kicks were clipped (the current
   generator's `clipped_kicks`) leaves the planned class and flags the item (`kick_realized.unknown`). Non-public parts record
   `mclass_requested` and `kick_realized` beside the realized `mclass`; public parts relabel only real systems (their realized sizes
   are public already in `info.kicks_applied`) and add no key; synthetic rows never carry `kicks_applied`
   (`SYNTHETIC_INFO_KEYS`). Build summaries report the clipped fraction per family.
7. **Host gate for synthetic simulations** (H N6): `SimContext.run` calls `require_admissible` for synthetic systems as the real
   engine does (every CPU simulation / build / evaluation class on Modal is gated already; the ungated util and GPU classes cannot
   simulate synthetic systems through the benchmark's context).
8. **Quiescent items** (F N-m4: 26 real items with constant all-zero futures): the mechanisms of three systems are silent at low
   input levels (0.55-0.64 of nominal); passive windows there, and in-family items whose kick is clipped to 0 or whose target is
   already silent, have constant futures. Kept: test items are never selected by their outcome; EE's floor denominator scores a
   zero-effect prediction as 0 error and the observational NMSE uses the system's training sd, so both metrics are defined; the
   builds count them (`constant_future_items`).

## Evidence and counts

| | before (design v1) | after (design v2) |
|---|---|---|
| real public rows with an explicit initial state | 620 of 6,554 (all 'obs.init') | 0 of 6,554 |
| real public 'obs.init' rows | 620 (r0 'state' on half the observed units, up to the top of the rate range) | 620 (restarts from same-draw nominal trajectories) |
| real public build | 6,554 records, 0 errors | 6,554 records, 0 errors, 0 store mismatches, $0.88 |
| real Level B build | 1,840 records, 0 errors | 1,840 records, 0 errors, 0 store mismatches, $0.58 |
| kick items clipped (public / Level B) | labelled by the requested class | 252 / 791 and 32 / 80 clipped; 191 and 29 relabelled |
| items equal to their twin through the onset sample (public) | not checked | 2,352 / 2,352 |
| verification (public, local gated host) | 60 re-simulations | 120 re-simulations bit-identical (restart sources replayed first), 24,200 pool futures and 6,554 rows within the public policy; local copy = build manifests, file for file |
| rows with an admissible host fingerprint (public / Level B) | not counted | 6,554 / 6,554 and 1,840 / 1,840 (`scripts/p4/check_build_hosts.py`) |
| constant-future test items (public / Level B) | not counted | 10 / 24 (kept) |

Local check before the Modal builds (one mechanism, public part): 713 records, 0 errors; the 54 'obs.init' rows (D0, validation,
passive tests, pool 'init' sources) all restart from a same-draw nominal source. Modal runs E14-1 to E14-4 (MODAL_RUNS.md), about
$1.5 in total.

Tests: `phase4/tests/test_data_design_v2.py` (13), `test_calibration_targets_rules.py` (8), updated `test_suites_design.py`,
`test_suites_build.py`, `test_suites_review_fixes.py`.

## Calibration targets version 3 (LOG P4-D38)

Code: `scripts/p4/calibration_targets.py` (`build`: the documented rules of the targets file, i.e. per-system values from
`calibstats.compute_all` on every public record, the fixed anonymous labels, the summaries, the range rules pos / frac / dim / size /
dt, the coverage rule, min_inside_frac, change vs the earlier version and earlier_design; `apply-prose`: replaces the prose fields
without recomputing anything; `compare`: field-by-field differences of the computed fields) and `scripts/p4/calibration_targets_doc.py`
(templated prose whose numbers come from the data, and research/phase4/CALIBRATION_TARGETS.md generated from the JSON).

Validation against version 2: rebuilt from the pre-rebuild public data (the review room's copy, taken after the index-field strip of
P4-D26; calibstats does not read that field), with the v1 file as the earlier version and v2's prose. All 311 statistics and the 35
checked ones are reproduced; every computed field is equal except
- 164 per-system values that differ in the last digits (at most 3.4e-15 relative: the PCA-based dim_* statistics and the effect-norm
  percentiles eff_rel_x_current_* / eff_rel_x_kick_p25, floating-point summation order), with their summaries and ranges; with
  `compare --tol 1e-12` none of these remains;
- change_vs_earlier_design of the six init_* statistics: the v1 file (statistics code p4-calibstats-1) has no init_* statistic, so
  the documented rule over the earlier file's per-system values compares no system (n_systems 0), whereas v2 reports 10 systems. The
  ad-hoc builder of v2 must have taken earlier-design values for them from a source that is not in the repository (presumably the
  earlier data recomputed with p4-calibstats-2); they cannot be reproduced from the v1 file.

Version 3 (`calibration_targets.json`, version causal_state_v1/calibration_targets/3; v2 kept as
`calibration_targets_v2_explicit_init_design.json`): computed from the rebuilt public data (6,554 records), change columns against v2.
The document's design section describes the new design (restarts from nominal trajectories for initial-condition variability, no
explicit states); its brief of the real systems, the rationales and the caveats are regenerated from the data; a new table lists the
checked statistics that moved most. The largest moves (median per-system change, largest per-system change in brackets):

| statistic (class) | version 2 (all systems) | version 3 | change | why |
|---|---|---|---|---|
| `peak_rate_rel_p50` (design, checked) | 1.13-15.3; target 0.564-30.7 | 0.776-6.44; target 0.388-12.9 | 3.79 (15.1) | per-unit maxima were set by the explicit initial states (peak_rate_p50 192-211 in every system); now 9.3-12 in the large systems and 44-73 in four mechanisms |
| `kick_rel_scale_p50` (design, checked) | 0.0316-1.1; target 0.0158-2.2 | 0.0747-1.32; target 0.0374-2.64 | 1.53 (3.75) | the rate scale s_x of two large systems fell (45 -> 11.9, 29.8 -> 12.5); a median over four discrete magnitude classes also jumps between classes when the draws change |
| `dim_x_pooled_obs_n95` (mixed, checked) | 1-43; target 1-65 | 1-11; target 1-17 | 1.50 (4.78) | with the explicit states the pooled passive data spanned more directions (large systems 17-43 -> 9-11) |
| `effect_energy_outside_passive95` (mixed, checked) | 0-0.542; coverage [0.01, 0.3] | 0.0043-0.647; coverage [0.3, 0.4] | 1.18 (13.2); 4 from 0 | passive activity no longer spans every direction of the 3-unit mechanisms |
| `eff_rms_x_rel_scale_p50`, `effect_end_over_peak_median`, `snr_param_y_median`, `kick_clipped_frac_all`, `eff_rel_x_p50`, `eff_rel_y_p50` (checked) | | | 1.13-1.21 (1.4-2.7) | effect sizes relative to the new rate scales and twin variability; new draws (the removed initial-state draws shift the design streams) |
| `s_y` (mixed) | large systems 15.1-175 | 4.02-12.7 | 1.05 (43.6) | the persistent high-activity state no longer occurs; every readout statistic normalised by s_y moves with it (eff_rms_y_rel_scale_*: up to 100x in one system) |
| `init_high_state_frac_x` (mixed) | large systems 0.065-0.76 | 0 (small systems 0-0.11) | 3 to 0 | restarts from nominal trajectories stay in the nominal regime |

System-property statistics barely moved (median change at most 1.04 for every checked system statistic; spec_x_f_peak 5.86-16.6 ->
6.84-16.6); 18 statistics are identical in every system. Changes from or to 0 in single percentiles at the float32 floor (e.g.
eff_rel_y_current_p5, largest ratios 1e12-1e14) are floor artefacts, not system changes.

Record selection (LOG P4-D38): the calibration checks (`calibration_check_real.py`, `calibration_check_suite.py`, criterion 11) now
compute the statistics on EVERY public record by default, as the targets' record_selection states; `--max-per-kind 40` reproduces the
earlier selection (40 records per record kind plus their twins). On the real data against version 3:
- every public record (the default): all 3,110 per-system values equal the targets' own values exactly; 0 values outside the class
  or real range, 0 checked values outside their target range, `calibstats.compare` 35 / 35 (research/phase4/
  CALIBRATION_CHECK_real_public.json; 307 s for the ten systems);
- the earlier selection: 745 values outside their class range, 350 outside the real range, 1 checked value outside its target
  range (`kick_rel_scale_p50` of one mechanism, 0.0327 against 0.0374), compare 35 / 35 (CALIBRATION_CHECK_real_public_max40.json).
  The pooled statistics depend on the selection, so a suite must be measured with the targets' selection.

Note: the design change also changed the realization of the design. Removing the initial-state draws shifted the plan's random
streams, so most protocols differ from design v1 (in one mechanism 24 of 240 training protocols are unchanged); the change columns
of the design-dependent statistics mix the design change with sampling variability of a new draw.
