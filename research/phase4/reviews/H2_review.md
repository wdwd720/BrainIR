# Review H2: numerical methods and compute (second early round: verification)

Reviewer H. Scope: my 19 first-round findings (1 blocker, 6 majors, 12 minors), plus new problems in my area: the changed
machinery, the new synthetic generator (`extra/generator/`) and the rebuilt data (`data/real_public`, `data/synthetic_dev`).

**How the checks were run.** Scratch is in `.tmp/H/r2/` and every script was run with `sbx python .tmp/H/r2/<script>`. Package:
`src/brainir_causal` and `extra/brainir_causal` assembled in `.tmp/H/r2/pkg`. The toy Level C tier was rebuilt with the new code
(`build.py`, using a test salt in `.tmp/H/r2/salt.txt`): 522 records, 0 errors.

**Limits.** The frozen real-circuit integrator (`brainir`) is still not installed in the sandbox. Real-engine code paths could only
be checked through the rebuilt real public data and by reading the code.

**Status labels in the table:**
- **fixed**: verified by my own re-run, or by the orchestrator's tests I ran here.
- **partly**: part of the fix is verified, part is not.
- **unverified**: the fix exists in code, but I could not run it.

## 1. Per-finding table (round 1 → round 2)

| # | finding (round 1) | status | location of the fix | my re-run (numbers) |
|---|---|---|---|---|
| B1 | MEV numerical floor in the wrong units and measured outside the window | **fixed** | `evaluate_micro.py:191-230` (`floor_statistic`: mean square, sd units, rows 1..m; testable iff rm ≥ max(2·floor, (2 f_s/y_sd)² = 0.01)); `suites.py:1621-1633`: no-op breakpoint one sample after the restart, plus a float32-restart vs float64-continuation pair | `floor2.py`, all 22 public pools. **Real:** floors 2.8e-10 to 3.6e-06, detection floor 0.01, random divergence 0.056 to 44.8, every sequence testable. **Synthetic dev / toy:** no-op floor exactly 0, f32 floor ≤ 1.4e-14. `mevfloor2.py`: y × {1, 0.1, 10}, and a 0.5-unit offset of the repeat runs, give an identical floor (0.0291), MEV (0.00055) and testability. The round-1 flip is gone. |
| M1 | mediation / closure use the system-dt horizon | **fixed** | `evaluate_mediation.py:26, 569` (m_i = horizon with the item's own dt); `harness.py:208-212` (`verdict_items`: OOD / robustness items never enter D / E / A) | `look_items2.py`: 0 `horizon_steps(PRIMARY)` calls without dt remain; each ood:sampling item has m = 25 → 0.5 s. `m1m3.py`: mediation and closure run on 208 verdict items; the 40 OOD / robustness items are excluded. |
| M2 | references blind to dt | **fixed** | `refs.py:52-60, 317-323, 819-845` (integer sub-steps, non-integer ratios refused) | `refdt2.py`: the dt = 0.02 rollout equals the dt = 0.01 rollout[::2] (max difference 0.0), also with a kick at 0.1 s; dt 0.015 and 0.005 are refused. `test_refs_dt`: 5 passed. |
| M3 | 2 dt is not out of distribution; OOD items were re-simulated | **fixed** | `simservice.py:191`, `suites.py:312` (development dt = nominal only); `suites.py:885` (simulate at the nominal dt, keep every second sample) | `svc.py`: a dt = 2 ms request is refused ("dt must be the nominal dt"). `m1m3.py`: stored ood:sampling y equals the nominal-dt simulation [::2] (max difference 0.0). Real public data: all 6,554 records at dt = 1 ms. |
| M4 | failed / non-finite simulations stored; one NaN poisons EE | **fixed** | `store.py:20-80` (`check_record`, `InvalidRecord`); `evaluate.py:14` (non-finite truth dropped and counted); `suites.py:143, 1529` (spare seeds) | `nanitem2.py`: EE short / medium / long stay finite (2.0e-32 / 2.3e-32 / 2.5e-32) with 1 item counted in `n_dropped_nonfinite_truth`. `restart2.py`: `put` refuses a NaN record and a `success: false` record. Rebuilt public data: 0 non-finite records out of 13,652. |
| M5 | host / ISA dependence outside provenance | **partly** | `store.py:111-117` (host fingerprint on every record); `realsim.py:155` and `gate.py:89-95` (`require_admissible` on every real path) | **Verified:** `hosts.py`: all 6,554 real and 7,098 synthetic public records carry a fingerprint (admissible, Haswell OpenBLAS, pins set). `regen.py`: 120 of 120 synthetic_dev trajectories re-simulated on this AVX2-only host are bit-identical. **Unverified:** the real-engine gate itself (engine not runnable here). Synthetic simulations are not gated (new minor N6). |
| M6 | synthetic restarts unchecked; noise stream undefined | **fixed** | `suites.py:1172-1189` (`restart_index`, `check_restart_source`); `simservice.py:320, 508`; generator counter-based noise (`integrate.counter_normals`) | `restart2.py` (generator, dev seed): restart vs continuation max\|Δy\| = 0.0 without noise and 0.0 with process_noise sd 0.1. An off-grid time, a time beyond the source and a cross-system source are all refused. `svc.py`: the same three refusals through the service. |
| m1 | lift whitening from test histories | **fixed** | `evaluate_lift.py:4-8`, `harness.py:268, 295` | `lift2.py`: eval_native_lift with `whiten_histories` from public training data; 12 requests, success 1.0 (PCA-2 on the linear toy). |
| m2 | pool u in level units vs recorded current units | **fixed** | `suites.py:2085-2090` (the simulated u of the futures) | `test_suites_review_fixes` (17 passed; covers minor 2) |
| m3 | kick cost depends on dt | **fixed** | `evaluate_lift.py:18-21` (`lift_cost`: per kind, never summed); `loop.py:19, 95` | `test_loop_active`: 14 passed |
| m4 | no-op events at t_end accepted | **fixed** | `protocol.py:166-168` | `svc.py`: a kick at t_end is refused ("at or after the last step") |
| m5 | greedy_error has almost no floor | **unverified** | `designers.py:164-200` (`effect_floor_sq`: the evaluator's floor, capped at 10) | Code read only. `test_designers_policy` could not run fully (9 errors: missing `brainir`). |
| m6 | attach_truth uses the told events | **fixed** | `evaluate_truth.py:33-49` | `test_eval_review` (19 passed; includes the told / true events case) |
| m7 | non-finite bootstrap replicates dropped silently | **fixed** | `stats.py:111-130` (`n_nonfinite_reps`, worst-value charging), `evaluate_micro.py` (`MEV_CAP`) | `test_eval_review`; MEV outputs report `n_nonfinite_reps` |
| m8 | served key omits the engine | **fixed** | `simservice.py:503-506` (engine + service secret) | `svc.py`: the served key differs from the bare protocol hash |
| m9 | stale noisy files after an obs_scale change | **fixed** | `suites.py:1165` (obs_scale in noisy keys), `suites.py:1784` (directories cleared) | `test_suites_review_fixes` (17 passed) |
| m10 | pool states taken under an active intervention: undocumented | **fixed** | `docs/PROTOCOL.md:87-89` | documentation |
| m11 | whitening eigenvalue floor 1e-8 | **fixed** | `evaluate_micro.py:54`, `evaluate_lift.py:7` (1e-6) | code |
| m12 | lifts re-simulate each whole case | **fixed** | `evaluate_lift.py:8-12, 286-292` (restart from the case microstate; the history is joined without a duplicate row) | `lift2.py`: 26 candidate / twin simulations, all r0 restart; only the 2 case histories run from rest |

**Counts: 19 findings. 17 fixed, 1 partly (M5), 1 unverified (m5), 0 not fixed.**

Test runs with the round-2 code:

| test file | result |
|---|---|
| test_eval_review | 19 passed |
| test_suites_review_fixes | 17 passed |
| test_refs_dt | 5 passed |
| test_loop_active | 14 passed |
| test_protocol | 20 passed |
| test_eval_core | 20 passed |
| test_lift_native | 10 passed |
| generator suite | 222 passed (262 s) |

`test_simservice` could not be collected, and `test_designers_policy` had 9 errors, all for `brainir` not installed.

## 2. New findings

### N1 (MAJOR): the generator shows windowed interventions at their onset sample, so histories and twins diverge, and param items leak the intervention into the encoder input

**The benchmark's convention.** The sample at an event's time is the pre-event state (PROTOCOL_V2 §1). An item's history
x[0..i0] *including* the onset sample is shared by the item and its twin (`evalio.py` docstring). `items_from_set` builds
`x_hist = r.x[:i0+1]` from the intervened trajectory.

**What the generator does instead.** `integrate.py:623-653` computes the algebraic outputs of sample t_n with the configuration
"in force on [t_n, t_n+1)":
- `cfg_idx = arange(T)` is applied to the gain / threshold / out_off (silence) arrays for y (through `ZH`);
- the same holds for gain / threshold in x.

So an event starting at t0 is already visible at the sample t0. The real engine does not do this: its outputs are continuous state
variables.

**Evidence** (`datachk.py`, `twinmm2.py`, `leak.py`, on the published `data/synthetic_dev`):
- **Real public data:** 0 of 2,352 twin prefixes differ.
- **Synthetic_dev:** 464 of 2,624 twins differ from their intervention trajectory, every one first at the onset sample itself
  (offset 0):

| family | twins that differ at the onset sample |
|---|---|
| sil.1 | 246 / 452 (y) |
| sil.2 | 55 / 68 (y) |
| param.1 | 163 / 264 (125 in x) |

- The mismatching param events are all gain (82) or threshold (81) changes.
- At the onset sample, |y_int − y_twin| / sd(y) has median 0.039 and max 1.99.
- **Leak into the encoder input:** in the evaluator's own items (public evaluation part), 14 of 24 param.1 test items have an
  encoder input `x_hist[-1]` that differs from the twin's onset sample. The size is median 0.14 and max 15.4 × obs_scale.x.

**Consequences:**
- The model encodes a history that already contains the intervention (an action-identity leak into z0 for param items).
- The item's and the twin's histories are not common.
- For param items, x_res at the onset (SMS / ICG) carries the event's immediate effect.
- Real and synthetic systems follow different timing conventions for the same event kinds.
- The generator's own twin test ("bit-identical *before* the first event") excludes the onset sample, so it does not catch this.

**Fix:**
- In the generator, record the algebraic outputs of sample t_n with the left-limit configuration, i.e. the one in force on
  [t_{n−1}, t_n) (`cfg_idx = max(n−1, 0)`), so the onset sample is pre-event.
- Define the end-sample convention to match. The configuration at t1 is then still the event's, so an algebraic-output lift
  completes at t1 + dt; adjust `completion_index`, or document it.
- Extend the generator test to include the onset sample.
- Add a build-time assertion in `run_specs`: x and y of every item equal those of its twin on rows 0..i0 inclusive.
- Rebuild `data/synthetic_dev`.

### N2 (minor): the generator's step-accuracy guarantee (addendum 1) is tested only on suite seed 0 at params_spread 1, and fails on the benchmark's actual dev seed and at robustness spreads

**Evidence** (`genstep.py`). I computed y(h) − y(h/2) over 2 s with a 3 m_s kick and a 3 m_s pulse, relative to the readout
floor; the contract bound is < 1e-3.

| suite seed | worst ratio (system, params_spread) | cases > 1e-3 |
|---|---|---|
| 20260926 (the benchmark's `DEV_SEED`) | 0.0133 (T02-fhn, 3.0); 2.2e-3 (T19-burst, 3.0); 1.4e-3 (T10-osc, 2.0) | 6 |
| 7 | 1.9e-3 (T13-ring, 2.0) | 4, including T13-ring at spread 1.0: 1.15e-3 |

- The extreme-intervention checks gave 0 failures on both seeds (tau × 0.1, gain 1.9, hi-range kicks and currents, spread 2).
- The size is harmless (≤ 1.3 % of the detection floor), but the stated guarantee is unverified for the val / conf instances.

**Fix:** run the addendum-1 and addendum-2 checks as a build-time assertion on each tier actually built (dev / val / conf,
spreads 1, 1.5 and 2), or halve h_max for the fhn and ring variants.

### N3 (minor): truth-equivalent states differ only in units that cannot influence y, so the 5.5 truth-equivalent comparison is 0 by construction

`system.py:294-310` randomises only follower / generator / relay units.

**Evidence** (`gentruth.py`, dev seed): the futures of the equivalents are **bit-identical** to the source state's in 50 of 50
systems, under every sequence tested: none, a 3 m_s kick, silencing of a core unit, and a param change on a core unit.

The truth-equivalent reference therefore carries no information. The generator's own §1.2 describes "off-manifold core detail"
that is equivalent under passive dynamics, kicks and currents but not under state-reading interventions.

**Fix:** add such core-detail equivalents (the non-trivial case), or label the comparison a sanity check.

### N4 (minor): the "true latent effect" of a kick (the exact jump) is not what one sample later shows

**Evidence** (`gentruth.py`). The relative difference between z_kick[1] − z_twin[1] and `true_latent_effect` has median 4.1 %.
The worst cases:

| system | difference |
|---|---|
| T02-fhn | 14.6 % |
| T18-wells4 | 12.8 % |
| T09-slaved | 11.8 % |

Where each quantity is used:
- `evaluate_truth` scores the model's read-in against the exact jump.
- The model's fallback (the rollout difference) is taken one sample after the onset.
- The lift miss is measured one sample after the kick.

**Fix:** use one definition everywhere (e.g. the truth z one sample after the onset, which the simulator provides) or report both.

### N5 (minor): kick clipping is large on real systems and invisible on synthetic ones

**Real public data** (`datachk.py`, `info.kicks_applied`):
- 331 of 951 kicks (34.8 %) are clipped, losing a median 86 % of the requested magnitude.
- The items' magnitude classes and D1 design cells are still labelled by the *requested* magnitude.

**Synthetic data:** the generator reports `clipped_kicks`, but `suites.py:157` (`SYNTHETIC_INFO_KEYS`) keeps only
`kicks_applied`. No synthetic record discloses clipping, although the generator's own calibration puts the clipped share at
0.14 to 0.63.

**Fix:** map `clipped_kicks` to `kicks_applied`. Report per-class results by *applied* magnitude, or flag clipped items.

### N6 (minor): synthetic simulations are not host-gated (residual of M5)

- The gate applies to real systems only.
- The synthetic val / conf tiers may be built on any host; the fingerprint records it but nothing refuses it.
- Bit-identity across hosts is verified here for AVX2 (120 of 120), but not for AVX-512.

**Fix:** apply `require_admissible` (or at least a pinned-host check) when building orchestrator-held synthetic tiers.

## 3. Checked in the new parts and found sound

- **Generator integrator** (`integrate.py`, the 222-test suite, and my own runs):
  - fixed internal step, independent of the output dt;
  - counter-based process noise (restarts bit-exact with noise);
  - kick clipping shared by `simulate` and `true_latent_effect`;
  - stability and finiteness at the extreme magnitudes on 2 further seeds and at spread 2;
  - failures flagged through `info.success`.
- **State carriers** (`suites.py:957-993`): content-addressed full-state records, key re-derived on store, and the ordinary
  restart checks apply.
- **Rebuilt data:** finite; nominal dt; real twin prefixes identical; host fingerprints uniform and admissible; synthetic
  records reproducible bit-for-bit on another AVX2 host.

## 4. Verdict

**Not ready to freeze, pending one fix.** Every round-1 finding is fixed, and all but M5 (whose real-engine gate cannot be run
here) and minor 5 (code read only) are verified by re-runs. Notably, the MEV floor is now unit-invariant and binds at the
detection floor on all 22 public pools; references, mediation and closure respect item dt; and failed simulations can no longer
poison a ratio.

The blocking item is new: **N1**. The synthetic generator records the algebraic outputs of an event's onset sample with the
event's own configuration. As a result, 464 of 2,624 synthetic_dev twins diverge from their items at the onset, and 14 of 24
public param.1 test items hand the encoder a history that already contains the intervention (up to 15 × obs_scale). This breaks
the benchmark's pre-event sample convention, which the real engine honours. Unlike the real engine, the generator's twin test
does not check the onset sample.

The fix is local: left-limit outputs in `integrate.py`, an inclusive twin-prefix assertion at build time, and a rebuild of
`data/synthetic_dev`. After that, and the minor generator hardening (N2 to N6), the numerical machinery would be ready to freeze.
