# Review T — round 3 follow-up (final pre-freeze generator, p4synth v3.2)

Reviewer T. Verification of the author's final version (`extra/generator`, SYNTHETIC_BENCHMARK.md §15–17) against my round-2
(`T_review.md`) and round-3 (`T3_review.md`) findings.
- Systems: the development tier `build_suite("dev", 20260926)` (50 systems; ids match `data/synthetic_dev`) and an audit suite
  `build_suite("audit", 1, 4)` for extra draws of types 20 / 21.
- Everything was re-run in the sandbox, one job at a time. Scripts and logs: `.tmp/T/r3c/`.
- f_s = the effect floor 0.05 sd(y); magnitudes in the new public units.

## Key demonstrations: before → after

| demonstration | before (round 2 / round 3) | after (this version) | script |
|---|---|---|---|
| B1: equal true z, different core detail (L w = 0; a moderate-kick detail and a random 3 m_s detail), futures under 17 kinds / sequences: none, moderate / clipped kick (2000 → 500), pulse, current_seq, silence (temporary, persistent, another unit, group of 4), gain 1.5 / 0.5, threshold, tau 0.5, extreme window (tau 0.1 + gain 1.9, 0.4 s), edge removal, kick → silence 5 ms, persistent current → silence | r2: silence median 6.8 f_s (max 50), gain 4.2, tau 3.6, clipped kick 7.8, another unit up to 8 f_s | **max |Δy| = 0 f_s** for every kind on 17 dev systems × 2 detail kinds (own effects of these events: median 2.3–302 f_s) | `b1c.py` |
| B1: same-unit kick → silence 5 / 25 ms later, true-z-mediated (on-manifold state at the onset of b) | r2: median 4.5 / 1.7 f_s, max 42 | max 7.4e-12 f_s (34 cases) | `b1c.py` |
| B1: pool states during a persistent current / persistent silencing vs the equal-z on-manifold state (5 sequences incl. clipped kick, extreme window) | r2: 91 % / 40 % > 1 f_s, max 327 f_s | max 4.2e-11 f_s (102 states; median detail 7.6 internal units) | `b1c.py` |
| Truth-equivalent states non-trivial and equivalent | r2: 0 core coords changed (50/50); r3: every core unit changed but |x_eq − x| up to 6,441 obs_scale (> 10 in 27/50) | 4–7 core units changed (the k+1..k+3 zero-latent group kick; every core unit in types 20/21). Futures bit-identical (0 f_s) under 5 probe sets on 50/50. Against my reachable set (nominal, inputs 0.6 / 1.4, ±3 m_s kicks, pulses, silencing on 8 targets), ≤ 2 % of observed units lie outside it, max excess 30 obs_scale (T13-torus, exponential maps); the generator's own reachable set (which includes group kicks) passes its test | `truth3c.py`, `eqreal.py` |
| Onset invisibility (item == twin up to and incl. the onset sample, every kind, core + nuisance target, at 0.5 s and at t = 0 of a restart) | r2 (reviewers): 464 / 2,624 twins differ | 0 / 1,782 | `truth3c.py` |
| Lifts (3 random 0.5 z_scale requests × 50 systems, n = 4) | r2: misses 29–69 % (type 10), 15–31 %; futures differ up to 4.2 f_s | every returned lift: independent miss ≤ 2.1e-4 (= the reported miss); distinct lifts' futures ≤ 9e-9 f_s, also under a silencing 5 ms later. Type 10: 0 lifts (both dev systems); types 20 / 21: exactly 1 per request (reported). The evaluator now restricts requests to the reachable span (`evaluate_lift.restrict_to_reachable`; `extra/tests/test_lift_reachable.py` passes) | `truth3c.py` |
| B4: SVD test of 20 / 21 (every moderate single-unit kick + pulse response, 3 states; rank needed for p90 < 1 f_s, / bound max(1, N_obs/5)) | r2: 0.7–0.95×; r3: 1.27× (audit T20-lin, 1 s) | dev: T21-m2 2.0 / 1.8×, T20-lin 2.25 / 1.9×, T20-sat 1.95 / 1.8×, T21-m1 1.7 / 1.65× (primary / 1 s), 96–100 % of responses > 1 f_s at the bound. Audit: 1.9–2.4× for 3 draws, but **syn-d1e76b6f98f3 (T20-sat, N_obs 39): 1.29× at 1 s; the generator's own `controls.simulated_margin` gives 1.286, with 47 % of responses missed at the bound, while its construction surrogate said 1.86** (N8) | `controls3c.py`, `margin.py` |
| Type-21 passive compressibility (nominal draws, schedules 0.55–1.45, restart-obs.init, + weight noise) | r3: with weight noise full rank 55/96, residual 0.97 > exposing 0.67 | rank 1–2 with and without weight noise (both dev type-21 systems) | `controls3c.py` |
| Public-field classifier (300 systems, 6 seeds, grouped 4-fold RF; 75 features: sizes, readout_dim, obs_scale, every numeric capability field after `normalize_capability`, edge-graph stats; per-unit: observed / targetable, degrees, reciprocity) | r2: roles 93–100 %; r3 (reviewers): "no compact" AUC 1.0 | type 7.0 % (chance 4.0 %), k 43.7 % (majority 41.0 %), "no compact state" AUC 0.44, roles AUC 0.54 (accuracy 61.3 % vs majority 63.6 %) | `leak3c.py` |
| Realized kick sizes | — | `info["kicks_applied"]` only in the full output (non-full: absent). A 2000 request is applied as 496–550 (to the ±500 bound) and moderate ones exactly. Public synthetic rows carry none (0 / 7,098) | `draws.py` |
| d_draw / draw_effective (9 dev systems, 4 random draws each, futures 0.5 s under a step + 2 m_s kick from the draw's own state) | closure stated for z alone | d_draw 4–6. z alone (nominal draw) mispredicts by median 7.2–26 f_s (max 110); (z, draw_effective) median 0–0.2 f_s, max 0.55 f_s; (z, draw_parameters) exact (0) | `draws.py` |
| Generator tests on the benchmark tier | r2: seed 0 only | `P4_TEST_SEEDS=20260926`: **212 passed** (41 min), incl. step self-convergence under the extreme window, passive-residual bounds at spread 1–2, moderate kicks never clip, equivalent states in range, controls' simulated margin, public leakage | `pytest.log` |
| Calibration against targets v3 | r2: 33–34 / 35 (stale report) | report: tier dev, seed 20260926, targets version 3 (= `data/calibration_targets.json`, byte-identical), 713 records per system, 35 / 35. My recomputation of part 0/25 (2 systems) reproduces all 298–310 per-system statistics to ≤ 3.3e-15 relative | `cal_part0.json`, `calcmp.py` |

## Per-finding table

| finding | status | location / evidence |
|---|---|---|
| r2 B1 (z not causal under state-reading interventions; trivial equivalents) | **fixed** | on-manifold outputs (§1, `integrate.py:84-91`); table rows 1–4 |
| r2 B2 (passive set exposes the trap) | **fixed** | dataset design v2 (restart-obs.init, no explicit states); generator trap tests pass on 20260926 (spread 1–2, inputs 0.55–1.45); type 21 with weight noise rank 1–2. My full `traps3.py` sweep was not repeated this round |
| r2 B3 (r0 on every unit) | **fixed** | `sampling.py:63-70`; rebuilt public data: 0 / 7,098 explicit states, `init.state = false` in 10 / 10 manifests |
| r2 B4 (controls compressible) | **partly** | 9 of 10 checked controls ≥ 1.65×; one audit draw 1.29× (N8) |
| r2 M1 (public fields reveal roles / τ_c) | **fixed** | classifier row |
| r2 M2 (lifts) | **fixed** | lifts row |
| r2 M3 (tests / calibration on seed 0 only) | **fixed** | 212 passed on 20260926; report on 20260926 |
| r2 M4 (obs.init magnitudes) | **fixed** | restart-obs.init (design v2) |
| r2 M5 (closure bound) | **fixed** | §1.2 exact; confirmed by B1 rows |
| r2 M6 (calibration stale) | **fixed** | v3, 35 / 35, spot-check reproduces |
| r2 m1 (step convergence, extreme window) | **fixed** | `test_step_self_convergence` (plain and extreme) passed on 20260926 |
| r2 m2 (type-22 bound) | **fixed** | bounds re-measured; `test_passive_residual_small_exposed_residual_large` passed |
| r2 m3 (non-full info) | **fixed** | non-full info = {engine, success, system} |
| r2 m4 (content_hash in public_record) | **fixed at the benchmark** | whitelist; not in public manifests |
| r2 m5 (moderate kicks clip) | **fixed** | range ±500 public; `test_moderate_kicks_do_not_clip` passed; moderate kick with detail: 0 f_s divergence |
| r2 m6 (minimality at small shifts) | no change needed | — |
| r3 item 5 (onset visibility) | **fixed** | 0 / 1,782 |
| r3 item 7 (kicks_applied, d_draw, draw_effective) | **fixed** | draws row; kicks row |
| r3 N1 (weight noise exposes type 21) | **fixed** | rank 1–2 with weight noise; §17 B2 |
| r3 N2 (truth-equivalent comparison model-independent) | **fixed** | `evaluate_micro.py:348-378` (model latent distance); `test_microstate_equivalence` passes (merged package) |
| r3 N3 (equivalent states out of range) | **fixed** | ≤ 2 % of units outside my reachable set; generator test passes |
| r3 N4 (no lifts for type 10 / one for 20-21) | **fixed at the evaluator** | requests restricted to the reachable span; test passes (the generator still returns 0 / 1 lifts, honestly) |
| r3 N5 (outputs ignore own potential off-manifold) | **fixed (documented)** | §12 limitation 0 |
| r3 N6 (per-system control margin) | **partly** | construction uses a linearised surrogate; one audit draw fails the simulated margin (N8) |

Counts: **fixed 20** (incl. 1 at the benchmark only and 1 by documentation); **partly 2** (r2 B4, r3 N6: the same residual problem,
N8); **not fixed 0**; **no change needed 1**. New: 2 MAJOR (N7, N8), 0 blockers.

## New findings

**N7 (MAJOR). Moderate time-constant and edge interventions are nearly inert; their capability "moderate" is not honest.**
Contract §3 requires the moderate magnitude to give a clearly detectable readout effect. Measured on 17 dev systems (`moderate.py`;
4 core targets each, RMS readout effect over the primary horizon from a mid-trajectory state):

| kind | median | p90 | share below f_s |
|---|---|---|---|
| kick | 7.7 f_s | 10.6 f_s | 2 % |
| pulse | 7.7 f_s | 10.8 f_s | 2 % |
| silence | 8.9 f_s | 28 f_s | 8 % |
| threshold | 12.6 f_s | 22 f_s | 0 % |
| gain 1.5 | 2.7 f_s | 12 f_s | 23 % |
| **tau 0.5** | 0.013 f_s | 0.28 f_s | **97 %** |
| **tau 1.5** | 0.004 f_s | 0.10 f_s | **98 %** |
| **edge at the published moderate depth 0.5** (first 6 public edges) | 0.012 f_s | 0.40 f_s | **95 %** |
| **edge removal** | 0.024 f_s | 0.79 f_s | **92 %** |

The cause is the v3 model. A time-constant factor only rescales that unit's 1/N_c share of the latent drive (a = min(1/c, 2)). A
core–core edge carries a (k/N_c-sized) entry of W = E L, and most listed edges end on nuisance units. Consequences:
- `param.1` items that draw the tau field, and every `edge.w` / `edge.rm` item (198 edge.w training rows per dev system in the
  public data), are no-effect items labelled "moderate" / "strong";
- their family-shift and target-shift cells are won by the NO-EFFECT reference;
- effect-size classes derived from these moderates are wrong.

*Fix:* probe tau and edge_scale like kick / current (search the magnitude for ES ≈ 8, or declare "no detectable readout effect at
any admissible magnitude" and have the benchmark treat those families as below-detection / exclude them from the synthetic
generalisation cells); and add a generator test that every published moderate gives a median ES within [3, 10) per kind.

**N8 (MAJOR). The per-system control margin is guaranteed only on the tested seeds.** Type-20/21 draws are accepted at
construction by a linearised surrogate (`controls.surrogate_margin`, threshold 1.7), and the simulated margin (≥ 1.5) is tested
only on the tiers / seeds the test suite builds. On `build_suite("audit", 1, 4)`, T20-sat syn-d1e76b6f98f3 (N_obs 39, bound 7) has
simulated margin 1.29× at 1 s by the generator's own `controls.simulated_margin` (need 9, 47 % of responses missed at the bound),
while its surrogate reports 1.86×. The confirmation tier uses salted seeds no test ever sees, so a compressible "control" can reach
the binding criterion "no compact causal state declared on ≥ 2/3 of the controls". *Fix:* accept type-20/21 draws at construction by
`simulated_margin` (cheap: 2–3 simulations per core target) or raise the surrogate threshold for 'sat' variants. In the suite builder,
assert simulated margin ≥ 1.5 at both horizons for every control of every tier built (val / conf included), and redraw otherwise.

## Verdict

**Not ready to freeze, but close.** Every round-2 and round-3 truth finding I re-ran is fixed:
- z is now an exact causal state: 0 f_s divergence under all 17 kinds and sequences, compositions and persistent-intervention pool
  states;
- truth-equivalent states are non-trivial, reachable and bit-equivalent;
- no intervention is visible at its onset sample (0 / 1,782);
- lifts meet 1e-3 or are withheld, and the evaluator restricts lift requests to the reachable span;
- public fields no longer predict type, k or roles;
- the draw dimension closes futures (≤ 0.55 f_s);
- tests run and pass on the benchmark's own tier (212 passed), and the calibration report is v3, 35 / 35 and reproducible.

Two majors remain:
- **N7:** the published moderate magnitudes of tau and edge interventions produce no detectable effect in 92–98 % of cases, which
  makes two development / test families no-effect items mislabelled as moderate;
- **N8:** the control margin that the binding "no compact causal state" criterion depends on is enforced by a surrogate that
  accepted a 1.29× draw on an unseen seed.

Both have cheap, local fixes (probe-based moderates or a declared no-effect status for tau / edge; simulated-margin acceptance of
controls at build time). With them in place I see no truth-level reason not to freeze.
