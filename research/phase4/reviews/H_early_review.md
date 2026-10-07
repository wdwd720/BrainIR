# Review H: numerical methods and compute (early round, pre-freeze)

Reviewer H. Scope: solver accuracy, intervention timing, piecewise integration, restarts, caching keys, reproducibility, CPU/GPU,
normalisation, numerical floors, off-by-one errors, and dt dependence of metrics. Scratch scripts are in `.tmp/H/` and all ran
with `./sbx python .tmp/H/<script>`. The frozen Phase 1 integrator (`brainir.sim`) is not installed in the sandbox, so the
real-circuit engine could not be run. Engine findings come from reading the code and the orchestrator's own tests and results.
Synthetic-side checks use the adapter's `ToySystem`: a small Level C toy tier built with `.tmp/H/build.py` into `.tmp/H/suiteC`,
plus the public `data/toy_example`.

## Summary verdict

Most of the timing machinery is consistent and sound:
- **Canonical protocols and breakpoints.** Times are snapped to the output grid, and every place the right-hand side changes is
  a breakpoint.
- **Twins.** Each counterfactual twin keeps the intervened run's breakpoints.
- **One convention for kicks and windows.** The sample at an instantaneous event is the pre-event state. This holds in the
  engine, the toy, the reference `Timeline`, the lift completion index and the evaluator's rows 1..m.
- **Store keys** cover dt, duration, r0 (including the restart key and time), params_spread, process noise, weight noise,
  stimulus and events.

However, one pre-registered rule is numerically invalid:
- **The MEV "numerical floor" untestability rule (criterion E)** compares quantities in different units.
- **The floor itself is measured outside the window it guards.** It is exactly 0 on every deterministic fixed-step system.

Several other issues make metrics depend on dt or on the host, or let a single failed simulation silently disable a verdict
criterion. **Verdict: fix B1 and the majors before the freeze.** None needs a redesign.

## BLOCKERS

### B1. The MEV numerical floor is in the wrong units and is measured outside the MEV window, so the untestability rule of 5.5 / criterion E is invalid

**The comparison mixes units.**
- `evaluate_micro.py:224-229` declares a sequence testable iff `rm >= 2 * floor`.
- `rm` is the random-pair **mean squared** future divergence **in units of the public readout sd**, over rows 1..m of the
  primary horizon (`_futures`, `pair_divergence`).
- `floor` is `pool.floor_div`, built in `suites.py:1622-1624` as an **RMS** difference in **raw readout units**, over the
  **whole** pool future (25 % of T).
- So the rule compares a squared, standardised quantity with an unsquared, raw one. Testability therefore changes with the
  units of y.

**The floor run cannot see any numerical error inside the window.**
- `pool_future_protocol(..., floor=True)` (`suites.py:1318-1319`) puts its no-op breakpoint at `T_future/2 + dt`.
- With `T_future = 0.25 T` and the primary horizon at `0.125 T`, that is exactly the primary horizon plus one sample.
- The repeat run is therefore identical to the reference run over the whole MEV window by construction.
- For a deterministic fixed-step generator it is identical everywhere, so the floor is 0.
- For the adaptive real integrator it measures only divergence after the window.

**Evidence** (`.tmp/H/floor.py`, `.tmp/H/mevfloor.py`, `.tmp/H/look_items.py`):
- Public `data/toy_example`, both systems: `pool.floor_div = 0.0` on all 20 floor states, and `max|floor - none| = 0.0` over
  the whole future.
- The toy Level C build gives the same result: floors `[0.0, 0.0, 0.0, 0.0]`.
- With floor 0, `rm >= 0` always holds, so the floor rule never triggers.
- Unit dependence: the same pool with a hypothetical repeat-run difference of 0.5 readout units (0.17 y_sd, far below the
  random-pair divergence of 0.34 sd² mean-square) was scored with `eval_microstate(..., m_match=3)`:

| readout units | floor as coded | testable | MEV | floor in consistent units (sd²) | random divergence (sd²) |
|---|---|---|---|---|---|
| ×1 | 0.5 | False | NaN | 0.0345 | 0.338 |
| ×0.1 | 0.05 | True | 0.0275 | 0.0345 | 0.338 |
| ×10 | 5.0 | False | NaN | 0.0345 | 0.338 |

Physically these are identical systems, yet the E category ("supported" vs "supported (E untested)") flips with the unit of y.
On real systems (y in Hz) the rule will declare pools untestable whenever the raw RMS floor exceeds half the standardised
mean-square divergence. On synthetic systems it never binds.

**Fix:**
1. Compute the floor exactly like `rm`: mean squared difference, standardised by `sysc.y_sd`, over rows 1..m of the primary
   horizon.
2. Make the repeat run perturb the numerics inside the window:
   - put the no-op breakpoint at `dt` (or m/4); and/or
   - add a restart of the float32-rounded state against the float64 continuation, which is the real engine's actual
     restart error.
3. Add an absolute floor tied to the detection floor, e.g. untestable when every sequence's random divergence is below
   `(2 f_s / y_sd)^2 = 0.01`. With a deterministic generator the numerical floor alone is 0, so it can never make a
   non-diverging pool untestable.
4. Add a unit test: scaling y by 10 must not change `testable`.

## MAJOR issues

### M1. Mediation (D), closure (E) and composition use the system-dt horizon for every item, which is wrong for the temporal-sampling OOD items

**Where:**
- `evaluate_mediation.py:323, 358, 455` and `evaluate.py:350` call `sysc.horizon_steps(PRIMARY)` without `it.dt`.
- By contrast, the EE, NMSE and calibration scorers pass `it.dt` (`evaluate.py:177, 205, 321, 390, 517`).

**Why it matters:**
- At Level C, `design_ood` creates `ood:sampling` items at 2 dt (`suites.py:790-792`).
- `load_eval_inputs(roles=None)` passes every item to `eval_mediation` / `eval_closure` (`harness.py:216-218`).

**Evidence** (`.tmp/H/look_items.py`, toy Level C, dt 0.01, primary horizon 0.5 s):
```
ood:sampling item dt=0.02 rows=101  mediation/closure row m=50 -> t=1.00s ; EE row m=25 -> t=0.50s
```
The SMS lags and the ICG_y target are taken at twice the primary horizon for these items, and are pooled with the other items
under the same lag feature `L/m`.

**Fix:** use `m_i = sysc.horizon_steps(PRIMARY, it.dt)` per item, with lags as fractions of `m_i`. Alternatively, exclude
`ood:*` and `robust:*` items from the D / E inputs explicitly and say so in PROTOCOL 5.3 / 5.4. Also note that verdict A at
Level C currently scores all items, including roughly 40 % OOD and robustness items (no `roles` filter anywhere). Please make
that choice explicit in PROTOCOL 9.

### M2. The benchmark references are dt-blind: their learned dynamics take one training-dt step per output row whatever `dt` is

**Where:** `refs.py:766-788`. `rollout` uses `dt` only to place events (`Timeline`). The update `s += MLP(...)` is one step at
the training dt.

**Evidence** (`.tmp/H/refdt.py`, PCA-2 reference fit on the toy):
- The rollout for an `ood:sampling` item is bit-identical for `dt = 0.01` and `dt = 0.02`.
- A kick at 0.1 s first acts at row 11 with dt 0.01 and at row 6 with dt 0.02. Events are re-timed, but the dynamics are not.

**Consequences:**
- TRUE-STATE, FULL-STATE and the other references predict the 2 dt items on the wrong time axis. The FULL-STATE EMA traces are
  also in samples.
- Because Level C verdicts score all items (M1), P_t and the full-state bound include these mis-timed predictions.
- The OOD degradation reported for methods has no valid reference.

**Fix:** either integrate the reference dynamics per unit time (sub-step `round(dt / dt_train)` times, and refuse non-integer
ratios), or have the references abstain on `dt != dt_train` and exclude `ood:sampling` from reference-based verdict inputs.

### M3. The temporal-sampling "OOD" shift is not out of distribution on real systems, and it confounds sampling with integration

- **Not out of distribution.** Real capability `timing.dt_allowed = [0.001, 0.002, 0.005]` (`systems.py:226`), so 2 ms and
  5 ms are development protocols the service simulates on request. The "2x dt" shift is therefore in-distribution for any
  developer who asks for it.
- **Sampling is confounded with integration.** OOD sampling items are re-simulated at 2 dt (`FamilySampler({**sysrec, "dt":
  2 dt})`, `suites.py:790`) rather than subsampled. For any generator whose internal step scales with the output dt (the toy
  uses RK4 with `h = dt/10`; the future generator is unknown), the shift changes the numerical trajectory, not just its
  sampling. Event onsets and durations are also re-snapped to the coarser grid.

**Fix:**
- Restrict development dt to the nominal dt (or make the OOD factor exceed every development dt).
- Generate the OOD item by simulating at the nominal dt and keeping every second sample. Use events already on the 2 dt grid so
  the told and simulated events coincide.

### M4. Failed or non-finite simulations are stored and scored silently, and one NaN disables the system's EE

**Where:** `realsim.py:258, 267` sets `info["success"] = False` when a piece fails or yields non-finite samples. Nothing reads
it: `store.put`, `SimContext.run`, `run_specs`, `run_job` and `items_from_set` never check it or check finiteness.

**Consequence:** `score_item` computes `den = max(nan, floor) = nan`, and `boot_ratio` then returns NaN for the whole system
(`stats.py`, `if not np.isfinite(den).all()`).

**Evidence** (`.tmp/H/nanitem.py`): 30 items, a PERFECT effect prediction, one item whose true future is NaN after row 150:
```
EE_medium (rows 1..50, NaN outside the window): 2.4e-32
EE_long   (rows 1..200, NaN inside)          : nan [nan, nan]
```
If the NaN falls inside the primary window, criterion A becomes a "missing input", which blocks SUPPORTED for that system.

Strong parameter changes make this plausible:
- `class_value` draws a tau factor down to `max(0.05, 1 - 0.9) = 0.1` and gains up to 1.9. The service allows the same
  (`simservice.py:151-158`).
- For fixed-step generators this raises stiffness 10x.
- `params.validate()` failures drop such items entirely (recorded only in the build summary), which biases item selection.

**Fix:**
- Refuse to store records with `success == False` or non-finite x / y (raise in `SimContext.run` and `run_job`). Count and
  report such failures per family in the build summary. Regenerate with a new seed under a logged rule.
- In the evaluator, drop items with non-finite truth, count them and report the count, rather than letting them poison the
  ratio.

### M5. Host / ISA dependence is outside the store's provenance

**The gate covers Modal only.** `p4modal/gate.py` documents that the frozen engine and the fits are not bit-identical on
AVX-512 hosts ("Phase 3 found 13 of 20 records differing"), and the gate plus `CPU_PINS` apply only to Modal jobs
(`p4modal/app.py:85-86`, `images.py:22`). These paths have no gate and no pins:
- `LocalBackend`, `SimServer`'s local process pool, `SimContext`;
- the service's local pool, which simulates all mechanism and synthetic requests.

**The store cannot tell hosts apart.**
- Record `info` carries no host fingerprint: `realsim.py:267` records engine, simulator, bundle and system only.
- The store key has no host component, and `get_or_compute` is first-writer-wins.
- So records produced on different ISAs mix silently under one key. A frozen dataset can then be neither re-derived nor
  verified bit-for-bit, and a replay on another machine will "mismatch" without any bug.

**Fix:**
- Store `info.host`: CPU flags, the numpy / scipy / OpenBLAS / torch versions, `NPY_DISABLE_CPU_FEATURES` and
  `ATEN_CPU_CAPABILITY`.
- Apply `gate.admissible()` (or the same env pins) in `LocalBackend` / `run_job` for real systems.
- Before the freeze, replay a sample of stored keys on the production path and require bit-identity.

**Scope of the CPU/GPU evidence.** `extra/results/cpu_gpu_equivalence.json` (72 comparisons, all pass) covers 50 optimiser
steps of a toy trainer. It does not show that full method training is device-equivalent (float32 chaos over thousands of
steps). Record the device in every result, and treat CPU vs GPU fits as different seeds in 5.11.

### M6. Synthetic restarts are unchecked, and restart semantics under process noise are undefined

- **No checks on the synthetic restart paths** (`suites.py:1038-1040` and `simservice.py:180-186`). They compute
  `i = round(t / dt_src)` without checking that `t` is a sample time, and without checking that the source is the same
  system. The real engine checks both (`realsim.py:132-140`).
- **Evidence** (`.tmp/H/restart.py`):
  - `t = 1.234` was accepted and silently used the state at 1.23.
  - `syn:toy:1` was restarted from a `syn:toy:0` microstate and served (x0 = [2.23, -2.26, -1.34, ...]).
- **Cross-system restarts reach developers.** The service accepts any key "served to you", across systems, so developers can
  obtain trajectories started from another system's states.
- **Process noise.** Restart vs continuation is bit-identical without noise (max difference 0.0). With `process_noise
  {sd 0.1}` it diverges by 0.27 on a scale of 9.7, because the noise stream restarts. This is harmless today (pool futures,
  lifts and twins carry no process noise), but the generator contract does not define it.

**Fix:**
- Port the real engine's two checks (sample time within 1e-6 dt; `info.system_id` equal) to both synthetic paths.
- Require generators to draw process noise from a counter-based stream keyed by (seed, absolute step index), so that restarts
  and piece splits reproduce the continuation.

## Minor issues

1. **Lift whitening uses held-out data.** `harness.py:229` passes `whiten_trajs=None`, so `eval_native_lift` whitens with
   encodings of the lift cases' own base trajectories (held-out tests, from 10 % of T including transients). Requested shifts
   are "alpha latent sd" of test data, not of the public training encodings used in 5.5. Pass `whiten_histories(inputs)`
   instead.
2. **Units of u in the pool.** The real engine records `u = level × stim_current` (`realsim.py:263`), but pool futures build
   `u_future = level` (`suites.py:1607`). These agree only if `stim_current == 1`. This affects the bisimulation
   re-encodings (5.6). Store the futures' simulated `u` instead of reconstructing it.
3. **Kick cost depends on dt.** Cost = |delta| × dt (lift cost 5.7 and the loop's magnitude budget 5.17), so the kick cost
   halves with dt and is not commensurable with current doses. Report kick magnitude separately.
4. **No-op events are accepted.** Kicks at `t == t_end` and windows starting at `t_end` pass `validate`, are classified as
   families and charged, but never act (the engine loop stops before `t_end`). Refuse events at or after `t_end - dt`.
5. **The `greedy_error` designer has almost no floor.** Its error uses `max(sum e², 1e-12 + 1e-6 n)` in raw units
   (`designers.py:~169`), not the evaluator's `n_t n_y f_s²`. Items below detection dominate its selection. Use the
   evaluator's floor.
6. **`attach_truth` uses the told events.** It computes `dz_true` from the told events at the onset state
   (`evaluate_truth.py:44-45`). For amplitude- and timing-jitter items this is not the simulated event or state; use
   `true_events`, or skip robustness items in the read-in accuracy.
7. **Silent loss of bootstrap replicates.** `stats.percentile_ci` drops non-finite replicates silently (e.g. MEV resamples
   without matched pairs). Report the number of dropped replicates, or count them on the null side.
8. **The served trajectory key omits the engine.** `traj_key = protocol_hash(q)` excludes the system hash and engine id
   (`simservice.py:310`), so a persisted `served_keys.json` can map an old key to an old-engine store key after an engine
   bump. Include the engine id.
9. **Stale noisy dataset files.** Observation noise uses `obs_scale` from the system record, which is not in `dataset_key`,
   and `SetWriter.add` skips files that already exist. A rebuild after an `obs_scale` change keeps stale noisy arrays.
10. **Pool sources can carry active interventions.** Pool sources of kind "intervention" can be sampled while a window or
    persistent event is active (onsets 0.15-0.5 T, states 0.2-0.7 T), and the restart future drops that event. This is
    legitimate for a microstate test, but it should be documented. The model's history-based z then encodes an intervened
    history.
11. **The whitening floor is weak.** The eigenvalue floor of 1e-8 × max (5.5 and 5.7) inflates near-degenerate latent
    coordinates up to 10^4. A relative floor of about 1e-6 (like `PC_REL_FLOOR`) would be more robust. Minor, because it is
    the model's own latent.
12. **Lift simulation cost.** Lifts re-simulate each whole case protocol from t = 0 (about 600 full-network trajectories per
    model per system). Restarting from the case microstate for both the lifted run and its twin would cut this 2-4x, while
    keeping lifted and twin consistent.

## For the generator round (the contract should require, and tests should check)

1. **Step size.** The internal step must be independent of the output dt, or dt must be fixed. Document the step and its
   accuracy, e.g. a self-convergence test: halving the step changes y by < 1e-3 f_s over the long horizon.
2. **Stiffness at the extremes.** The development and test magnitudes reach a tau factor of 0.1, gain 1.9, kicks of 3 m_s
   and hi-range values up to 9 m_s. The generator must run stably there (M4).
3. **Process noise.** Noise must come from a counter-based stream keyed by absolute time (M6), use Euler-Maruyama or
   better, and have a documented sd per √s.
4. **Clipping.** Kicks clipped to `admissible_range` must be clipped identically in `simulate` and `true_latent_effect`
   (the toy clips in neither).
5. **Latent effects.** `true_latent_effect` must match the simulated jump. The toy test accepts one dt of drift
   (atol 2e-3); state which definition is scored.
6. **Equivalent states.** `equivalent_states` should be verified by simulation (identical futures under the exact families).
7. **Hash coverage.** `content_hash` must cover everything that changes a trajectory; `engine_id` must change with code.

## What I checked and found sound

- **Protocol canonicalisation** (`protocol.py`): snapping, breakpoints (stimulus steps, event edges, sequence boundaries),
  `counterfactual` keeping the breakpoints, and seq boundary snapping. `test_protocol`: 19 passed.
- **Twins.** Twin prefix identity holds on the toy Level C build: 238 of 238 intervention items have x identical to their
  twin up to and including the onset sample.
- **Engine composition** (`realsim.py`, by reading):
  - pieces are constant between breakpoints;
  - kicks are applied after recording the pre-kick sample, with clipping at 0;
  - `_active` window rule, `current_seq` segment lookup, `edge_scale` on the noised matrix (factor 0 set to exactly 0),
    param changes on a copy of the draw, and weight noise applied once;
  - the restart time and system checks;
  - observation noise stays outside the microstate.
- **Real-engine evidence.** The orchestrator's bit-identity tests against the Phase 3 engine and the restart test (≤ 0.2 % after
  0.3 s from float32 rounding) exist; I did not run them (no `brainir` in the sandbox). The Modal smoke test reports
  bit-identical passes, cache hits and restarts.
- **Offsets and horizons.** These agree everywhere: history `x[0..i0]` inclusive, futures from the onset row, events relative
  to the onset, EE and NMSE rows 1..m with `it.dt`, and the lift completion index (kick +1 sample, window end sample).
  Mediation lags index the same rows as the model's prediction. Refs' `Timeline` applies kicks before the step, as the
  simulators do.
- **Timing jitter.** The onset is the minimum of the told and true onsets, so the history never contains the jitter.
- **Store keys.** The store key (canonical protocol without obs_noise + system hash + engine | simulator) covers dt, t_end,
  r0 restart source and time, params_spread, process noise, weight noise, stimulus and events. The dataset key includes
  obs_noise, and targets use `y_clean`.
- **Restart equivalence (toy).** Restart vs continuation is bit-identical without noise.
- **Normalisers.** They come from the public `train` split only, with blow-up exclusion (`evalio.make_eval_system`). The EE
  denominator floor is `m n_y f²`. EE, ES and the detectability classes are invariant to dt, because the sum and the floor
  scale together. The SMS gain floor (0.01) and the x_res drop rule (1e-6 relative, one common scale) look correct.
- **Stats.** Ratio of sums, paired resampling on identical clusters, Holm's procedure and `(1 + count) / (1 + B)` look
  correct.
- **Test runs** (orchestrator tests run from the assembled package):

| test file | result |
|---|---|
| test_eval_core | 20 passed |
| test_lift_native | 7 passed |
| test_lift_toysys | 1 passed |
| test_eval_verdict | 19 passed |
| test_calibstats | 8 passed |
| test_stability_repr | 4 passed |
| test_transfer_rules | 5 passed |
| test_select_rules | 5 passed |
| test_refs_models | 8 passed |
| test_equiv_cpu | 5 passed |

  The failures in `test_families`, `test_designers_policy` and `test_loop_active` were all environmental (missing `brainir`,
  method registry).
