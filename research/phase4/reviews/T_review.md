# Review T — truth audit of the synthetic generator (p4synth), pre-freeze round 2

Reviewer T. Scope: the truth claims of `extra/generator` (p4synth) as the benchmark uses them (`extra/brainir_causal/suites.py`,
`synthadapter.py`, `simservice.py`, `docs/PROTOCOL.md`). Every number below comes from a simulation in the sandbox on the systems
the benchmark actually builds: `build_suite("dev", suites.DEV_SEED = 20260926)` (50 systems; their ids match `data/synthetic_dev`),
plus 10 extra variants the dev tier does not contain (5-trap, 10-trap, 15-easy, 15-osc, 18-wells_trap, 21-modes30, 22-rho0.3,
23-near, 25-visible_s, 20-rnn24; built with the generator's own `build_type` / `implement`). Scripts and raw outputs:
`.tmp/T/*.py`, `.tmp/T/*.json`. Units: f_s = the system's `capability.readout_floor` = 0.05 sd(y) (the generator's effect floor);
"RMS over the primary horizon" = 12.5 % of T.

## Summary verdict

**Not ready to freeze.** The integrator is excellent (exact kick read-ins incl. clipping, bit-identical r0 ≡ kick, bit-exact
implementation groups, fourth-order convergence, stable at the extremes, fast). But four truth claims on which pre-registered metrics
rest are false as the benchmark uses the generator:

1. z is **not** the causal state under the full intervention set: states with equal true z differ in "off-manifold" core detail
   that every single-unit core intervention creates, and silencing / parameter / edge / clipped-kick interventions read it. The
   effect is as large as the reading intervention's own effect, spreads to other core units, and is reached by benchmark items
   (single-target compositions, pool states from persistent-intervention sources). The generator's "truth-equivalent" states never
   exercise it (they differ only in units with no path to z or y), so the benchmark's truth-equivalent reference is vacuous.
2. The central **trap is exposed by the benchmark's own PASSIVE data**: `obs.init` (8 of 40 D0 trajectories, 1/4 of the passive
   test set, and the "init" pool sources) moves the hidden residual by 0.4–7× its scale — as much as the exposing interventions —
   in 22 of 23 trap systems. "z_obs predicts passive data well" is false on the benchmark's passive set, so the OBS-SHORTCUT null
   of the POWER RULE and the trap metrics are invalid.
3. The public capability lets r0 'state' set **every unit** (`init.units` = all unit ids, range ±140), and r0 on a unit is
   bit-identical to a kick at t = 0. Held-out targets, held-out kick families, and hidden non-targetable units (type 10's mode units)
   are therefore accessible in development (D0 already contains such trajectories), which contaminates target-shift and family-shift
   tests and breaks the type-10 trap.
4. The **non-compressible controls (20, 21) are compressible at the benchmark's tolerance**: a latent of dimension below the
   compactness bound N_obs/5 reproduces every single-unit kick / pulse response within a fraction of f_s; and type 21 is not
   observationally compressible on the benchmark's D0 (initial-condition and weight-noise trajectories fill all 24–40 modes).

Answer to the specific question (r0 on all units): **yes, it weakens the traps and several truth claims, and restricting to observed
units is necessary but not sufficient** (details in B2/B3 and the r0 table).

## BLOCKERS

### B1. z is not causally sufficient under state-reading interventions; truth-equivalence is only tested on decoupled units

*Mechanism.* z = L (v_core − b). Readers see ẑ = z + L_S (o_S − d_S) for core units S in a non-nominal configuration
(`extra/generator/src/p4synth/integrate.py:406`, `:443`), and kicks clip on the unit's own v (`integrate.py:323`). Any
single-unit core kick / current leaves off-manifold detail w = δ (e_i − E L_i) (L w = 0, equal z) on ALL core units (the −E L_i δ
part), which relaxes with τ_c = 12–30 ms, or which persists while a persistent current / silencing is on.

*Demonstration 1* (`offman.py`, 50 dev systems × 2 core targets; pairs s0 and s0 + w with w = the detail a moderate kick leaves;
true z equal to 1e-9; future 0.5 s from a mid-trajectory state; RMS difference of y over the primary horizon, in f_s):

| future sequence at t = 0 of the future | median | max | fraction > 1 f_s | median diff / the event's own effect |
|---|---|---|---|---|
| none, current pulse | 0 | 0 | 0 | 0 |
| silence of the unit (0.1 s) | 6.8 | 49.7 | 0.99 | 1.07 |
| gain 1.5 / 0.5 on the unit | 4.2 / 3.6 | 89 / 29 | 0.99 / 0.97 | 1.2 / 1.15 |
| tau 0.5 on the unit | 3.6 | 62 | 0.96 | — |
| kick 9 m_s (clipped) / kick m_s | 7.8 / 0 | 57 / 48 | 0.89 / 0.24 | 0.33 |
| silence of ANOTHER core unit | 0.18 | 8.0 (T15-hard) | 0.05 | 0.04 |
| silence, detail aged 1 τ_c / 3 τ_c | 2.5 / 0.35 | 15.8 / 2.1 | 0.90 / 0.04 | 0.40 / 0.05 |

Every one of the 50 systems has silence-divergence > 1.3 f_s (per-type table below). The generator's §1.2 / §12.1 "closure bound"
says the detail matters only "on the same unit"; it is spread over all core units (T15-hard 8.0 f_s, T25-hidden_s 2.4 f_s,
T14-ratio10 1.2 f_s when silencing a different unit), and moderate (not only clipped) kicks read it (24 % of cases).

*Demonstration 2 — benchmark compositions* (`comp.py`). `FamilySampler.make` draws ONE target for `comp.seq` / `comp.sim`
(`extra/brainir_causal/suites.py:726-733`, default n_t = 1), so both components hit the same unit, the second 1 dt – 150 ms after the
first ends. True-z mediation (replace the core by the on-manifold core with the same z at the onset of b):

| a → b on the same unit | Δ = 5 ms | Δ = 25 ms | Δ = 75 ms |
|---|---|---|---|
| kick → silence: median / p90 / max (f_s); frac > 1 f_s | 4.5 / 10.4 / 42; 0.96 | 1.7 / 4.4 / 12.7; 0.72 | 0.11 / 0.52 / 1.2; 0.01 |
| kick → gain 0.5 | 2.5 / 5.1 / 28; 0.90 | 0.89 / 2.2 / 7.0; 0.38 | 0.05 / 0.24 / 0.56; 0 |
| pulse → silence | 2.0 / 5.6 / 17; 0.87 | 0.78 / 2.4 / 5.7; 0.37 | 0.04 / 0.28 / 0.60; 0 |
| param → silence / pulse | 0 | 0 | 0 |

The error is 50–78 % of component b's own effect at Δ = 5 ms. A model with the exact true z, exact dynamics and exact read-ins cannot
predict these items.

*Demonstration 3 — pools* (`pooldetail.py`, 1800 states emulating the benchmark's pool design: intervention sources with onsets
U(0.15, 0.5) T, states U(0.2, 0.7) T). Against the equal-z on-manifold state, under a moderate kick / silence / gain on the source's
target: persistent current sources 91 % of states > 1 f_s (median 3.3, max 327 f_s); persistent silencing 40 % (median 0.8, max 4.5).
Under a random public target the rate is 0.8 %, so the MEV itself is only mildly affected. But truth-matched pairs are not
equivalent, and the claim "equal z ⇒ equal futures under every permitted sequence" (contract §1) is false.

*Demonstration 4 — the truth-equivalent states are vacuous* (`truthfns.py`). `equivalent_states` (`extra/generator/src/p4synth/system.py:294`)
randomises only follower / relay / generator units, which have no path to z or y. In 50/50 dev systems the equivalent state differs
from the original in 0 core coordinates (4–157 nuisance coordinates). For T3-small and T6-small it also differs in 0 OBSERVED
coordinates, so the pair is identical to the encoder too. Bit-identical futures are therefore expected by construction for every
type, not evidence. The type-24 observation in the brief (40 coordinates differ, up to ~50 units, bit-identical futures) is exactly
this: 35 followers + 2 generator + 3 relays, 33 observed, 0 core. `evaluate_micro.py:318-331` reports this comparison as the
"truth_equivalent" MEV reference. It is a model-independent 0.

*Fix (either).* (a) Make the causal state exact: define silence / param / edge / clipping of core units through the unit's
MANIFOLD value b_i + E_i z (not its own v_i), or make off-manifold detail decay within one sample (separate, much faster
off-manifold relaxation). (b) Or keep the physics and restate the truth: the causal state is (z, w) with fast w; declare the
"causal-state horizon" (≥ 5 max τ_c after the last core intervention), and in the benchmark (i) draw two DIFFERENT targets for
`comp.*` or enforce a gap ≥ 5 τ_c_max (≈ 150 ms), (ii) exclude pool states within the horizon of a core intervention (and all states
of persistent-intervention sources) from truth-matched pairs and the true-state reference, (iii) extend `equivalent_states` with
off-manifold core variation (L w = 0) of realistic size and report its divergence, instead of a nuisance-only 0.

### B2. The central trap is exposed by the benchmark's PASSIVE set (`obs.init`)

`FamilySampler.initial_state` (`suites.py:548-556`) sets HALF of the observed units to U(init.min_value, init.max_value). The
generator publishes the GLOBAL min / max over all units' admissible ranges (`system.py:417-418`), ≈ [−140, +140]. `obs.init`
makes up 8 of the 40 D0 trajectories (`suites.py:122`), 1/4 of the passive test set (`suites.py:842`, `:1089`), and the "init" pool
sources. Hidden residual zres (the trap tests' own definition, `tests/test_traps.py`), max |zres| / residual scale (`traps.py`):

| trap system | passive (2 draws × 3 levels) | exposing interventions | obs.init as built (median / max of 8) | init on all units (max) | mild init ±1 tuning amp. (max) | weight noise 0.1 |
|---|---|---|---|---|---|---|
| T5 trap | 4.5e-6 | 2.58 | 1.05 / 1.76 | 2.28 | 0.15 | 0.02 |
| T6 hidden | 0 | 2.95 | 0.97 / 1.44 | 1.26 | 0.11 | 0 |
| T8 setpoint | 0 | 3.83 | 0.66 / 2.30 | 2.52 | 0.09 | 0 |
| T9 slaved | 0.06 | 3.51 | 0.90 / 3.73 | 4.01 | 0.39 | 0.05 |
| T10 trap | 4.5e-7 | 1.10 | 3e-17 / 6e-5 | **2.73** | 3e-17 | 3e-17 |
| T15 easy / medium / hard / osc | 0.30 / 0.064 / 0 / 0 | 1.93 / 1.76 / 4.62 / 5.71 | 0.60 / 0.54 / 1.02 / 0.82 (max 1.3 / 3.1 / 3.3 / 3.5) | 2.6 / 1.6 / 4.1 / 1.7 | 0.23 / 0.30 / 0.32 / 0.21 | 0.22 / 0.05 / 0.01 / 0 |
| T16 init | 0 | 4.47 | 0.41 / 1.42 | 2.28 | 0.20 | 0 |
| T18 wells_trap | 0 | 3.55 | 0.41 / 0.97 | 2.01 | 0.11 | 0 |
| T21 modes24 / 30 / 40 | ~1e-15 | 1.07 / 4.10 / 3.76 | **6.7 / 7.0 / 5.9** (max 10–11) | 9.7 | 0.56–0.76 | 0.02–0.06 |
| T22 rho0.3 / 0.1 / 0.04 | 0.25 / 0.14 / 0.07 | 2.57 / 2.71 / 2.34 | 0.85 / 1.51 / 1.41 (max 1.8–2.7) | 2.4–3.0 | 0.32–0.52 | 0.05–0.19 |
| T23 exact / near / third | 0 / 0.01 / 0 | 3.16 / 2.90 / 2.88 | 1.47 / 0.94 / 0.77 (max 2.4 / 2.3 / 4.6) | 2.5–3.4 | 0.14–0.23 | 0.01 |
| T25 visible_s / hidden_s / hard | 0 | 3.80 / 2.74 / 6.05 | 1.68 / 1.53 / 1.50 (max 3.6 / 2.8 / 3.1) | 2.9 / 4.0 / 6.3 | 0.16–0.41 | 0 |

In 22 of 23 trap systems the benchmark's passive init trajectories move the hidden residual by 0.4–7× its scale, typically 30–60 %
of (and for type 21 more than) what the exposing interventions reach. So:
- the defining premise "z_obs predicts passive trajectories well" is false on D0 and on the passive test set;
- the OBS-SHORTCUT reference, the null of the POWER RULE on trap types (PROTOCOL §7), is handicapped on passive items. Criteria D
  and the ICG / MEV parts of E can then bind because the null also fails passively, not because of the trap;
- the "z_obs capture" truth metric (PROTOCOL §5.16) is no longer a test of interventional sufficiency: D0 alone identifies the
  hidden direction.

Even a mild init (±1 tuning amplitude) exceeds the declared passive bounds of every hard / medium trap (0.1–0.76 vs bounds 0–0.08),
so shrinking the range does not rescue it. The problem is structural: an initial-condition change IS an intervention on the
hidden variable (see B3). Weight noise is harmless (≤ 0.22 = the easy grade's ε).

*Fix.* Classify r0 'state' as an interventional family (it is a kick at t = 0, B3), subject to the family / target split and absent
from passive D0 and passive tests; or, for synthetic trap systems, drop `obs.init` from D0 / passive tests / pool sources. State in the
truth record that each trap holds for passive data from rest under stimulus schedules and parameter draws. In any case publish a
per-unit initial-value range (e.g. rest ± 2 tuning amplitudes), not the global range (M4).

### B3. r0 'state' on every unit: held-out targets / families and hidden non-targetable units are accessible in development

- r0 on a unit is a kick at t = 0: `simulate(r0={u: rest_u + δ})` and `simulate(kick δ on u at t = 0)` are BIT-IDENTICAL from sample 1
  on, in 50/50 dev systems (`truthfns.py`). The kick read-in of this generator is state-independent (dz = L_i δ unless clipped), so
  r0 trajectories identify the kick read-in of every settable unit exactly.
- The generator declares `init.units` = every unit id (`system.py:417`). `normalize_capability` keeps it (`suites.py:296-299`,
  setdefault), and the simulation service then allows ANY unit (`simservice.py:223`: `allowed = None` unless units == "observed").
  Confirmed in the public data: every `data/synthetic_dev/*/manifest.json` has `init.units` = all n_units ids, range ≈ ±140.
- Even under an observed-only rule, 96 % (median; min 68 %) of targetable units and 100 % (median) of core targets are observed. The
  public target partition does not restrict r0, so D0's `obs.init` already contains initial "kicks" on held-out targets. For
  systems whose rotation holds out `kick.*` (e.g. syn-00e48aa6ad4d trains param.1 / pulse.1 / seq.train only), D0 contains group
  kicks at t = 0.
- Hidden units: all-unit r0 reaches type 10's 8 hidden, non-targetable mode units (residual 2.73 vs 1.10 for the exposing
  interventions, B2 table), the hidden cores of T6-hidden (5), T8-setpoint (5), T16-init (3), T18-wells_trap (6), T25-hard (6),
  T25-hidden_s (10), and the unobserved populations of type 17. These are exactly what the partial-observability and
  hidden-variable grades rely on.

Per-type answer to the brief's question: preparing hidden units directly makes the hidden direction directly controllable (z(0) =
L (v0 − b) is linear in the prepared values), bypassing the non-targetability that grades T10-trap, T6/T8/T16/T18/T25 (hidden
cores) and T17. For every other trap type the hidden-direction units are observed, so observed-only r0 already exposes the trap
(B2). The restriction to observed units is necessary (it closes T10 and the hidden-unit parts of T6 / T8 / T16 / T18 / T25 / T17)
but not sufficient (B2, and held-out targets).

*Fix.* Restrict r0 'state' to observed units that are PUBLIC targets or non-targetable. Treat it as kick-family exposure in the
rotation (a system whose rotation holds out `kick.*` gets no r0 'state' in development). Replace the generator's `init.units` list
by "observed" (or have `normalize_capability` override it, as it does for `public_seed_max` and `dt_allowed`).

### B4. The non-compressible controls (types 20, 21) are compressible at the benchmark's tolerance

PROTOCOL §5.10: compact ⇔ k ≤ max(1, N_obs/5); synthetic SUPPORTED requires "no compact causal state" on ≥ 2/3 of the type 20 / 21
systems (PROTOCOL l. 389). The controls have k_full only 1.2–1.5× the bound (24–40 vs 17–27). `controls2.py`: the readout
responses to EVERY single-unit kick and pulse on the targetable core units, from 3 states stacked (one common basis), SVD:

| system | k_full | bound q = N_obs/5 | median effect (f_s) | residual of the rank-q fit at q = bound, median / p90 / max (f_s) | smallest q with p90 < 1 f_s (primary / long horizon) |
|---|---|---|---|---|---|
| T20 lin40 | 40 | 27 | 7.3 | 0.11 / 0.19 / 0.27 | 13 / 11 |
| T20 rnn30 | 30 | 20 | 10.5 | 0.58 / 0.87 / 1.58 | 19 / 14 |
| T21 modes24 | 24 | 17 | 6.6 | 0.43 / 0.56 / 0.78 | 13 / 11 |
| T21 modes40 | 40 | 27 | 7.5 | 0.19 / 0.28 / 0.39 | 16 / 14 |
| (single state) T20 rnn24 / T21 modes30 | 24 / 30 | 16 / 20 | 5.2 / 9.9 | — | 13 / 18 (primary) |

A compact model at the bound captures the interventional input–output map within 0.1–0.6 f_s. For linear systems (lin40, modes*)
this is exact linear-systems theory: the Hankel rank at tolerance is far below k_full. An HONEST method would find a compact state
and not declare "no compact causal state", and the criterion would count that against it. Type 21's other half also fails
(`controls.py`): passive-from-rest z has rank 1–2 as claimed, but on a D0-like set (8 draws, 8 stimuli, 8 `obs.init`, 8 weight-noise)
z has n95 = 14–15 and full rank 24 / 40, more than type 20 (n95 9–10). On the benchmark's D0, type 21 is not "observationally
compressible".

*Fix.* Make the controls non-compressible by a wide margin at the tolerance: k_full ≥ 3× the bound with slow (≥ 200 ms), comparably
read-out and comparably excitable modes (e.g. near-normal A with a flat spectrum; check the Hankel singular values against f_s). Or
lower N_obs (fewer observed units makes the bound smaller). Verify with the SVD test above as a generator test. For type 21, remove
`obs.init` / `obs.wnoise` from its passive data (B2), or redefine its claim on the benchmark's actual D0.

## MAJOR

**M1. Per-unit truth in the public capability.** `capability.admissible_range` (`system.py:438`) and
`process_noise.unit_sd_per_sqrt_s` (`system.py:430`) pass verbatim into every public record (`normalize_capability` only adds keys).
From them alone (`leak.py`), a unit's role (core vs generator / relay / follower) is decoded with accuracy median 1.000, min 0.931
over 50 systems: generator = width 50, relay 40, follower 120, core units share nscale / (width/20) = √(2/τ_c). τ_c is recovered to
1e-4 relative error, and each core unit's rest potential b_i = the range midpoint (error 5e-5). "Roles never appear in public
records" (generator doc §1) is false. This defeats type 14 (the nuisance population is labelled), tells every method that ~half of
the targetable units have no readout effect, and reveals implementation detail. *Fix:* publish one system-wide admissible range and
one noise scale (or none), and strip per-unit fields in `normalize_capability`.

**M2. Lifts do not realise the request on several systems** (`truthfns.py`, dz = 0.5 z_scale in a random direction, n = 4). Both
dev type-10 systems (gain, osc) get only current pulses (the hidden mode dimension is not reachable by targetable kicks), with miss
29 % / 69 % against the generator's "< 10 %". T21-modes24 returns only 2 lifts (miss 31 %) and T25-hard a pulse lift with miss 15 %.
T22-rho0.04 kick lifts miss 15 %: the 5 % reachability acceptance in `system.py:241-243` plus clipping. Distinct lifts of one
request have passive futures differing by 4.2 f_s (T21-modes24), 1.25 (T25-hard), 1.23 (T22-rho0.04), 0.75 (T1-chain3). All other
systems: 4 exact kick lifts, equal passive futures (≤ 1e-13 f_s). Under a state-reading intervention 5 ms after the lift, distinct
exact lifts diverge by up to 7.1 f_s (T14-ratio10), 3.7 (T19-burst), 3.6 (T15-hard) (B1 again). The benchmark currently does not call
`lift_latent`, so no metric consumes it yet. It must not be used as "true lifts" before it reports its miss and drops failing
realisations.

**M3. The generator's tests and calibration never ran on the benchmark's systems.** `tests/conftest.py` and all test modules use
`build_suite("dev", 0)`, and `calibration_report.json` is for seed 0. The benchmark builds dev with `DEV_SEED = 20260926` and val / conf
with salted 128-bit seeds. The calibration stand-in (`calib.py:98-103`) also uses mild initial conditions (3 targetable units, ±2
m_s), not the benchmark's (half the observed units, ±140). *Fix:* make the test suite and the calibration seed-agnostic (parametrise
over several seeds including DEV_SEED), and calibrate with the benchmark's own sampler (`suites.FamilySampler`). My rerun of the
generator's calibration on DEV_SEED: see "Calibration" below.

**M4. `obs.init` values are extreme and partly artefactual** (`initmag.py`, benchmark sampler as built). 27 % (median; up to 62 % in
type 14) of the core values it sets are outside the unit's admissible range and clipped. z(0) reaches 1.7 z_scale (median;
8–14 z_scale in types 20 / 21). In T7-hyst3 58 % (T7-wta3 23 %) of the samples of those trajectories are in the regime where the
declared radial-confinement artefact (≥ 3.6 s⁻¹, generator §1.3 / §12.4) shapes the dynamics. *Fix:* per-unit init ranges (rest ± a
few tuning amplitudes) in the capability, and the benchmark samples within them.

**M5. The declared closure bound is misleading** (`SYNTHETIC_BENCHMARK.md` §1.2, §12.1; `truth()["closure"]`). It says the detail
matters "only for interventions that read an individual core unit on the same unit". Measured: it is on every core unit, it is read
by moderate (unclipped-in-nominal-state) kicks, and at 3 τ_c it is still up to 2.1 f_s (T15-hard 1.85, T17-adapt 2.1). The test that
backs the bound (2 % after 12 τ_c) does not test the time scales at which benchmark items occur (comp Δ ≥ 1 dt; pools). Rewrite with
the B1 numbers, or fix per B1.

**M6. Calibration report stale; one required statistic fails.** See "Calibration": 33 / 35 (seed 0) and 34 / 35 (DEV_SEED)
against the room's current targets; `input_gain_elasticity_y` fails on both.

## minor

- m1. Step self-convergence (contract §8.1: halving h changes y by < 1e-3 of the floor). With an extreme param window (tau 0.1 and
  gain 1.9, 0.4 s) plus a 3 m_s kick and pulse, 7 of 50 dev systems exceed 1e-3 f_s: T2-hopf 4.1e-3, T6-small 3.8e-3, T20-rnn30
  2.4e-3, T25-hidden_s 1.7e-3, T2-fhn 1.6e-3, T20-lin40 1.5e-3, T16-latch 1.5e-3, T5-cue 1.3e-3, T10-osc 1.25e-3 (`numgrp.py`). The
  generator's test omits the extreme tau. This is numerically harmless (< 0.5 % of f_s) but the stated requirement is not met.
- m2. T22-rho0.04's declared passive residual bound 0.08 is exceeded in 10 % of random parameter draws at nominal spread (max 0.095)
  and 30 % at `params_spread` 2 (max 0.134; the benchmark's OOD uses 1.5 / 2.0) (`thresh.py`). The threshold traps T5-trap and
  T10-trap stay far below their bounds even at spread 2 (max 0.038 / 1.6e-4 of scale).
- m3. `simulate()` without `full` returns `info.h`, `info.n_sub` (per-variant `H_MAX` identifies, e.g., types 11 / 12 / 20 and several
  variants) and `info.clipped_kicks`. The benchmark's whitelists (`suites.dataset_info`, `PUBLIC_INFO_KEYS`) drop them and the
  service returns arrays only, so nothing reaches a method today. Remove them from the non-`full` output anyway (contract item 7).
- m4. The generator's `public_record()` carries `content_hash` and `engine_id` (`system.py:446-452`); `GENERATOR_PUBLIC_KEYS` drops them.
  Keep the whitelist.
- m5. Moderate kicks clip at reachable states (kick_m diverges in 24 % of B1 cases; the generator's own calibration has median
  `kick_clipped_frac_all` 0.42). "Moderate = non-saturating" (contract §3) holds only near rest.
- m6. Minimality: the weakest latent direction at a 0.25 z_scale shift is below f_s in T5-cue (0.93), T7-wta3 (0.64), T9-relay
  (0.73), T19-adapt (0.86), T10-gain (0.09), T25-hard / hidden_s (≤ 1e-3). With 0.5–1 z_scale shifts and group kicks every
  dimension exceeds 2 f_s (T9-relay 2.3, T19-adapt 4.2, T10-gain mode needs a negative shift: 2.5–4.5 f_s). z is minimal, but some
  dimensions are visible only for large, discrete moves (switch / mode). Tolerances on "k = k_true" should allow for that.

## Per-type table (dev systems at DEV_SEED unless marked "extra")

Columns. **Equiv**: `equivalent_states` coordinates changed (observed, core); futures bit-identical under every kind in all cases
(expected: nuisance only). **Min**: weakest-direction readout effect at 0.25 z_scale (passive or under probe kicks), f_s. **Sil**:
max over 2 units of the equal-z divergence under silencing of a unit carrying fresh kick detail (B1), f_s; in brackets after 3 τ_c.
**Comp**: kick → silence 25 ms later on the same unit, max over 2 units, f_s. **Trap**: passive / exposed / obs.init-median of the
hidden residual (× scale). **Other**: groups, lifts, controls. TLE (kick incl. clipped) = the latent_kick of its dz to 0 error in 50/50,
r0 ≡ kick in 50/50, extremes (tau 0.1, gain 1.9, 9 m_s kicks / persistent currents on every role) finite and `success` in 50/50, CPU
0.05–0.33 s per 2 s trajectory in 50/50.

| type | variants | Equiv (obs, core) | Min | Sil [3 τ_c] | Comp | Trap | Other |
|---|---|---|---|---|---|---|---|
| 1 | chain3 / mixed4 | 22 (18,0) / 131 (118,0) | 1.36 / 2.3 | 7.3 [0.36] / 10.3 [0.51] | 1.6 / 3.4 | — | chain3 kick lifts miss 7 %, futures 0.75 f_s |
| 2 | hopf / fhn | 44 (36,0) / 33 (23,0) | 2.6 / 9.8 | 12.7 [0.50] / 9.4 [0.49] | 3.1 / 1.3 | — | step conv 4.1e-3 / 1.6e-3 f_s (m1) |
| 3 | small / twotau | 5 (**0**,0) / 36 (27,0) | 9.9 / 3.2 | 3.8 / 10.1 | 1.0 / 2.3 | — | small: equivalent states observationally identical |
| 4 | plane / signed | 44 (36,0) / 40 (29,0) | 3.3 / 15 | 8.8 / 8.2 | 1.8 / 1.7 | — | — |
| 5 | cue / onset; trap (extra) | 37 (32,0) / 25 (23,0) | 0.93→11 / 3.0 | 8.8 / 11.9 | 2.2 / 6.8 | trap: 4.5e-6 / 2.58 / 1.05 | — |
| 6 | hidden / small | 48 (41,0) / 4 (**0**,0) | 5.7 / 10 | 30.3 / 1.3 | 12.7 / 0.4 | hidden: 0 / 2.95 / 0.97 | 5 hidden core units settable by r0 |
| 7 | hyst3 / wta3 | 38 (34,0) / 28 (20,0) | 7.5 / 0.64→27 | 3.2 / 7.6 | 4.4 / 2.4 | — | obs.init: 58 % / 23 % of samples in confinement regime |
| 8 | pi / setpoint | 30 (26,0) / 42 (37,0) | 5.1 / 4.2 | 9.3 / 7.2 | 1.9 / 0.7 | setpoint: 0 / 3.83 / 0.66 | 5 hidden core units settable |
| 9 | slaved / relay | 39 (29,0) / 47 (38,0) | 2.0 / 0.73→2.3 | 11.4 / 12.5 | 3.6 / 3.7 | slaved: 0.06 / 3.51 / 0.90 | — |
| 10 | gain / osc; trap (extra) | 46 (39,0) / 36 (29,0) | mode dim: 2.5–4.5 (neg. shift) / 2.8 | 6.2 / 8.3 | 2.5 / 1.2 | trap: 4.5e-7 / 1.10 / 3e-17 (all-unit r0: **2.73**) | lifts: pulses only, miss **29 % / 69 %** |
| 11 | r3 / r6 | 32 (25,0) / 28 (24,0) | 4.7 / 4.2 | 8.0 / 9.0 | 1.9 / 0.7 | — | group: z, y identical (0.0) at seeds 0 and 5, lifted kicks 1e-13; unrelated to T12: RMS(Δy)/RMS(y) = 1.01 |
| 12 | impl0 / impl1 | 35 (30,0) / 64 (46,0) | 3.3 / 3.3 | 8.9 / 12.6 | 3.8 / 3.1 | — | group identical (0.0) |
| 13 | sigcode / torus | 46 (40,0) / 152 (140,0) | 11.4 / 3.7 | 7.7 / 17.5 [0.81] | 1.2 / 6.5 | — | — |
| 14 | ratio10 / ratio1000 | 157 (135,0) / 120 (105,0) | 8.3 / 20.7 | 6.8 / 7.9 | 3.3 / 2.4 | — | nuisance labelled by the public capability (M1); lift + later silence 7.1 f_s |
| 15 | hard / medium; easy, osc (extra) | 48 (42,0) / 30 (24,0) | 5.6 / 5.7 | **33.8** [1.85] / 6.9 | 1.4 / 1.2 | hard 0 / 4.62 / 1.02; medium 0.064 / 1.76 / 0.54; easy 0.30 / 1.93 / 0.60; osc 0 / 5.71 / 0.82 | hard: silencing ANOTHER unit 8.0 f_s |
| 16 | init / latch | 47 (42,0) / 39 (32,0) | 6.6 / 3.2 | 9.9 / 8.1 | 2.8 / 2.4 | init: 0 / 4.47 / 0.41 | 3 hidden core settable |
| 17 | adapt / osc | 49 (41,0) / 26 (24,0) | 1.2 / 9.2 | **43.0** [2.13] / 11.0 | 4.3 / 2.6 | — | unobserved populations settable by r0 (B3) |
| 18 | subhopf / wells4; wells_trap (extra) | 29 (25,0) / 50 (43,0) | 3.2 / 1.4 | 7.4 / **49.7** | 6.6 / 1.0 | wells_trap: 0 / 3.55 / 0.41 | — |
| 19 | adapt / burst | 33 (24,0) / 163 (147,0) | 0.86→4.2 / 1.2 | 8.0 / 6.7 | 5.3 / 1.6 | — | — |
| 20 | lin40 / rnn30; rnn24 (extra) | 17 (16,0) / 14 (10,0) | n/a | 3.9 / 3.9 | 0.4 / 2.0 | — | **compressible at tolerance** (B4): rank 13 / 19 / 13 < bound 27 / 20 / 16 |
| 21 | modes24 / modes40; modes30 (extra) | 20 (15,0) / 20 (15,0) | n/a | 5.0 / 4.2 | 1.0 / 1.1 | 0 / 1.07–4.10 / **5.9–7.0** | rank 13 / 16 / 18 < bound 17 / 27 / 20; D0 z n95 14–15, full rank; modes24 lifts: 2, miss 31 % |
| 22 | rho0.04 / rho0.1; rho0.3 (extra) | 50 (39,0) / 39 (33,0) | 1.9 / 1.7 | 5.9 / 7.5 | 1.4 / 4.5 | 0.07 / 2.34 / 1.41; 0.14 / 2.71 / 1.51; 0.25 / 2.57 / 0.85 | rho0.04 bound exceeded in 10–30 % of draws (m2); kick lifts miss 15 % |
| 23 | exact / third; near (extra) | 28 (26,0) / 42 (37,0) | 5.2 / 1.6 | 8.5 / **48.3** (gain 89) | 1.7 / 11.2 | exact 0 / 3.16 / 1.47; third 0 / 2.88 / 0.77; near 0.01 / 2.90 / 0.94 | — |
| 24 | clones8 / clones4 | **40 (33,0)** / 47 (41,0) | 3.7 / 3.7 | 11.4 / 7.3 | 1.0 / 4.4 | — | group identical (0.0); brief's observation reproduced: nuisance-only, bit-identity expected |
| 25 | hard / hidden_s; visible_s (extra) | 38 (31,0) / 41 (37,0) | switch dim ≥ 17 at 0.5–1 z_scale | 7.5 / 22.6 | 6.3 / 1.3 | hard 0 / 6.05 / 1.50; hidden_s 0 / 2.74 / 1.53; visible_s 0 / 3.80 / 1.68 | 6 / 10 hidden core settable; hard: pulse lift miss 15 % |

## r0 on hidden / all units — per-type conclusion (the brief's specific question)

| types | hidden-direction units | effect of r0 'state' |
|---|---|---|
| 10-trap | hidden (unobserved, non-targetable) mode units | only all-unit r0 exposes the trap (2.73 vs 1.10). Observed-only r0 is safe here. |
| 6-hidden, 8-setpoint, 16-init, 18-wells_trap, 25-* | partly hidden cores (3–10 units) plus observed units | observed-only r0 already exposes (B2). All-unit r0 exposes more and gives hidden units a direct handle. |
| 17 | unobserved populations carrying z2 / z3 | all-unit r0 prepares the unobserved state directly, which removes the history-inference difficulty. Observed-only restores it. |
| 5-trap, 9-slaved, 15-*, 21, 22, 23 | observed units | observed-only r0 exposes the trap exactly as all-unit r0 does (B2) |
| all others | — | r0 ≡ kick at t = 0 (bit-identical): held-out targets / kick families accessible (B3) |

Recommendation: restrict r0 to observed units, excluding held-out targets. Treat it as an intervention (kick) family in the rotation,
keep it out of passive D0 / passive tests / trap-null data, and use per-unit value ranges.

## Calibration (docs targets: `data/calibration_targets.json`; `docs/CALIBRATION_TARGETS.md` is not in the room)

I reran the generator's calibration script unchanged (`scripts/run_calibration.py`, own stand-in protocols, `ref/calibstats.py`)
against the room's current targets `data/calibration_targets.json` (`.tmp/T/run_calib.py`; outputs `.tmp/T/calib_*.json`):

| suite | required statistics passing | failing |
|---|---|---|
| generator's claim (`calibration_report.json`, seed 0, its targets) | 35 / 35 | — |
| seed 0, current targets | **33 / 35** | `input_gain_elasticity_y` (inside 0.32, needs 0.50; suite median 0.995 vs range 1.33–13.2); `effect_energy_outside_passive95` (coverage criterion fails) |
| DEV_SEED (the benchmark's dev tier), current targets | **34 / 35** | `input_gain_elasticity_y` (inside 0.36; median 1.13) |

The target ranges in the room differ from those in the report (e.g. `input_gain_elasticity_y` 1.33–13.2 now vs 0.845–12.3 in the
report), so `calibration_report.json` is stale. The input-elasticity mismatch the generator already called marginal is now a
failure on both seeds. MAJOR, added as **M6**: regenerate the report on the benchmark's tier and seed, with the benchmark's own
sampler (M3), and raise the readout's input dependence (types with near-zero or negative elasticity dominate the low tail:
suite min −1.5).

Whether types keep their defining properties while calibrated: yes under genuinely passive data (traps within bounds, groups exact,
controls high-rank from the generator's point of view). But two calibration-relevant sets defeat the properties: the benchmark's
`obs.init` (B2, M4) and the control-rank question (B4).

## What I checked and found sound

- **Exact on-manifold causal state.** With no state-reading event on a unit carrying off-manifold detail, equal-z states have
  identical futures (none / pulses / unclipped kicks: 0 f_s in 100/100 B1 cases). `true_state` = L (v_core − b) matches the returned z
  and the internal copy.
- **true_latent_effect for kicks.** Moderate and ±9 m_s (clipped) kicks give z and y trajectories identical, to machine precision, to
  the truth `latent_kick` of the returned dz, in 50/50 dev systems (contract §8.4 / §8.5).
- **r0 ≡ kick at t = 0.** Bit-identical in 50/50 (useful for the fix in B3).
- **Implementation groups (11, 12, 24).** z and y identical (max |Δ| = 0.0) across members at params_seed 0 and 5 with a latent kick.
  Lifted microscopic kicks in two members give identical z / y (≤ 1e-13). Unrelated pair T11 vs T12 differs (RMS(Δy) / RMS(y) = 1.01).
- **Traps under genuinely passive data.** Within declared bounds for all trap variants I tested (2 draws × 3 levels), and for the
  threshold traps T5 / T10 over 40 random draws even at `params_spread` 2. Exposing interventions move the residual by 1.1–6×
  scale. The traps are real dynamical properties; the problem is the benchmark's passive set (B2).
- **Minimality.** Every z dimension of every compact dev system changes the readout future by ≥ 2 f_s for 0.5–1 z_scale shifts,
  passively or under group kicks (m6 for the small-shift caveat).
- **Numerics.** Stable, finite, `success` at tau 0.1 / gain 1.9 / 9 m_s kicks and persistent currents on every role in 50/50;
  step-halving changes y by ≤ 4.1e-3 f_s (m1); CPU 0.046–0.33 s per 2 s trajectory (median ≈ 0.09 s; T13-torus 0.33 s is the only
  one above the contract's ~0.2 s); deterministic; bit-exact restarts and counter-based noise are covered by the generator's tests
  (I reran them: `222 passed in 288 s` on 2 CPUs; they run on seed 0 only, M3). Content hash / engine id cover every simulation source and spec field (`engine.py:40-57`).
- **Public data.** `data/synthetic_dev` rows carry no type / variant / k / trap / z. Info fields are whitelisted and pools carry no
  equivalents. The leaks are the per-unit capability fields (M1) and the all-unit init capability (B3).
