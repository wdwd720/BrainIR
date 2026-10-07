# Review H3c: numerical methods and compute (round-3 final check: the generator's final pre-freeze version)

Reviewer H. Scope: the items my round-3 follow-up (H3b) left pending the generator revision (N1 direct, N2, N3, N5 synthetic side),
the numerics of the new truth fields (d_draw / draw_effective, single-threaded construction), and new numerical problems.

**Test seeds:**
- the development tier `build_suite("dev", 20260926)`;
- seed **12345**, which is NOT among the author's test seeds (20260926, 0, 7);
- one system per type (25) unless stated.

**How the checks were run.** Scratch is in `.tmp/H/r3c/`, and every script ran with `sbx` against `extra/generator/src` (final
version) and the package assembled in `.tmp/H/r3c/pkg`.

## 1. Per-item table

| # | item | status | location | my re-run (numbers) |
|---|---|---|---|---|
| N1 direct | no intervention visible at its onset sample | **fixed** | generator: outputs at t_n use the configuration in force before t_n (SYNTHETIC_BENCHMARK §15 item 5) | `n1n3.py`: 8 event kinds (silence; param gain / threshold / tau; current; current_seq; kick; edge_scale) on a core AND a nuisance unit, from rest (onset 0.1 s) and at t = 0 of a restart. **Seed 20260926:** 784 cases, 0 visible at or before the onset sample (x and y); all 784 act after it. **Seed 12345:** 768 cases, 0 visible; 756 act. **Rebuilt `data/synthetic_dev`** (`datachk.py`): 0 of 2,624 items differ from their twin in x, y or u at or before the onset; 0 explicit states; 0 non-finite values; 7,098 of 7,098 rows admissible and pinned. |
| N2 | step self-convergence (bounds 1e-3 plain, 1.5e-3 extreme) | **partly** | per-variant h_max, smoothed caps / floors (§17 A) | `n2.py`, `order.py`; details below the table. **Within the stated scope the bounds hold:** plain at spreads 1 and 2 (worst 5.6e-4); the author's extreme window at spread 1 (max 3.4e-4). **Outside it:** the author's window at spread 2 exceeds once (1.73e-3); plain at spread 3 twice; hi-range kicks up to **0.275** of the floor (NEW-8). |
| N3 | non-trivial truth-equivalent states with futures at the numerical floor | **fixed** | `system.equivalent_states` (§17 B3) | `n1n3.py`. Both seeds: every equivalent state changes ≥ 2 core units (0 of 25 trivial on either seed). The observed x changes by ≥ 0.021 (0.023) × obs_scale. \|z_eq − z\| ≤ 1.8e-15. Futures under none / kick / core silencing / core param / current / edge removal are **bit-identical** (maximum difference 0) in 25 of 25 systems on both seeds. |
| N5 (synthetic) | realized kick sizes in the FULL output only; kick items classed by realized size | **partly** | generator `info["kicks_applied"]` (§16 B); benchmark `suites.realized_kick_class` (`suites.py:1340-1379`) | **Generator side fixed** (`n5draw.py`, 144 strong / hi kicks at pool states on 12 systems): `kicks_applied` appears in 144 of 144 full outputs and 0 of 144 non-full outputs; no kick clipped (realized = requested in 144 of 144). **Benchmark side not working:** the classing reads `"applied"`, but the generator reports `"units"`, so a clipped synthetic kick is never relabelled (NEW-7). |
| 5a | d_draw / draw_effective deterministic | **fixed** | `system.draw_effective`, `truth()["d_draw"]` | `n5draw.py`: two calls give bit-identical draw_effective (length = d_draw = 5); with weight noise, length 9; exactly linear in params_spread (spread 3 = 2 × spread 1.5, to 1e-12). |
| 5b | single-threaded construction: hashes bit-identical at 1 and 8 BLAS threads | **fixed** | `suite.build_system` under `threadpool_limits(1)` (§17 B6) | `threads.py`, fresh processes with OMP / OPENBLAS = 1 vs 8: all 50 content hashes, and d_draw plus draw_effective of 3 systems (d_draw 6, 4, 7), identical; 0 differences. |

**Counts (6 items): 4 fixed, 2 partly, 0 not fixed.**

**N2 detail** (y(h) vs y(h/2) over 2 s, in units of the readout floor; hidden-range parameter seeds):

| protocol | seed 20260926 | seed 12345 | bound |
|---|---|---|---|
| plain (3 m_s kick + 3 m_c pulse), spreads 1 / 2 | worst 1.4e-4 | worst 5.6e-4 | 1e-3 |
| plain, spread 3 (the protocol maximum; unused by the benchmark, whose OOD / robustness use 1.5 / 2) | 2.79e-3 (T23-third) | 1.01e-3 (T12-impl0) | 1e-3 |
| author's extreme window (τ × 0.1, gain 1.9 for 0.4 s over the kick and pulse), spread 1 | — | max 3.4e-4 | 1.5e-3 |
| author's extreme window, spread 2 | — | 1.73e-3 (T02-hopf) | 1.5e-3 |
| persistent parameter window incl. threshold | — | ≤ 1.5e-4 | — |
| persistent hi currents | — | ≤ 3.9e-4 | — |
| hi-range kicks ± 9 m_s | 8 of 50 above 1.5e-3, max 2.6e-2 (T12-impl1), 7.3e-3 (T18-subhopf) | 7 of 50 above 1.5e-3, max **2.75e-1** (T07-wta3) | none stated |

No integration failure occurred.

## 2. New findings

### NEW-7 (minor): the benchmark's realized-size kick classing does not read the generator's `kicks_applied` format

**Where:** `realized_kick_class` (`suites.py:1352-1361`) takes the realized size from `entry["applied"]`, the real engine's key,
and silently falls back to the REQUESTED size. The final generator reports `{"t", "event_index", "units": {unit: realized},
"requested": {...}}`.

**Evidence** (`threads.py`): a strong kick of −30 realized as −3 (0.1 of the request):
- in the real-engine format: `clipped: 1, mclass: 'weak'`;
- in the generator's format: `clipped: 0, mclass: 'strong'` (unchanged).

**Impact:** small today. None of the 144 strong / hi kicks I probed clipped (the generator's range is [−500, 500] in its own
units), so synthetic kick classes are almost always right anyway. But the pre-registered rule "kick items are classed by realized
size" is not implemented for synthetic systems.

**Fix:** read `entry.get("applied", entry.get("units"))` (as the lift code already does, `test_lift_per_lift_records`), and add a
test with the generator's own output.

### NEW-8 (minor): the step is too coarse for 1–2 ms after hi-range kicks

**Evidence** (`order.py`): convergence under repeated halving is clean 4th order (successive difference ratios 16.1 / 16.2,
16.2 / 16.3 and 17.4 / 16.8), and the error sits at t = 0.501–0.502 s, right after the 0.5 s kick. So this is truncation error
in the fast transient that a 9 m_s jump starts, not sensitivity near a separatrix:

| system | h | error / floor |
|---|---|---|
| T07-wta3 (seed 12345) | 0.5 ms | 0.275 |
| T12-impl1 | 0.5 ms | 1.4e-2 |
| T18-subhopf | 0.25 ms | 6.9e-3 |

**Impact:** kick.hi is a vocabulary family (held-out test items, magnitudes 1.5–3 × the development maximum = up to 9 m_s).
Their truth then carries up to 0.28 f_s of numerical error on one or two samples of the scored window. That is small against the
EE denominator floor, but it is 275 × the plain-protocol bound. The configuration-based step refinement (§17 A) covers parameter
windows, not post-kick transients.

**Fix:** refine the step for a few τ_fast after a kick whose realized size exceeds the strong class (e.g. n_sub × 4 for 5 ms),
include hi-range kicks in `test_step_self_convergence`, and state the bound's scope.

## 3. Verdict

**Ready to freeze from the numerical side, with two minor fixes recommended first.** Every point the final generator was asked to
fix holds in my own runs, including on a seed the author never tested:
- no intervention is visible at its onset sample (1,552 event cases on two seeds; 0 of 2,624 onset mismatches in the rebuilt
  public data);
- truth-equivalent states are non-trivial, with bit-identical futures under every probe;
- realized kick sizes appear in the full output only;
- the draw truth fields are deterministic;
- construction is bit-identical at 1 and 8 BLAS threads;
- the step bounds hold in their stated scope.

Open items (no blocker, no major):
- **NEW-7:** the benchmark's kick classing does not read the generator's `kicks_applied` format, so clipped synthetic kicks would
  keep their requested class. A one-line fix; today's impact is near zero.
- **NEW-8:** hi-range kicks leave up to 0.28 f_s of step error on one or two samples right after the kick, outside the stated
  bound. A local step refinement fixes it.
- **Scope:** the author's extreme-window bound is exceeded once at spread 2 (1.73e-3 against 1.5e-3). The bound should state its
  spread, or the check should run at spread 2 as well.
