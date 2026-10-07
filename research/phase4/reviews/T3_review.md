# Review T — round 3 (verification of the revised generator p4synth v3 and dataset design v2)

Reviewer T. Scope: every finding of my round-2 review (`reviews/T/T_review.md`), re-run on the revised generator
(`extra/generator`, SYNTHETIC_BENCHMARK.md §14–15) and the benchmark's dataset design v2 (`extra/brainir_causal/suites.py`,
`src/brainir_causal/sampling.py`, `extra/brainir_causal/simservice.py`), on the development tier `build_suite("dev", 20260926)`
(50 systems; ids match `data/synthetic_dev`) plus an all-variant audit suite `build_suite("audit", 1, 4)`. Scripts:
`.tmp/T/r3/*.py`; raw output `.tmp/T/r3/truth3.json`.

**Status of this report: PROVISIONAL.** At 05:41 the Docker Desktop engine crashed ("error waiting for container: unexpected EOF").
It killed four of my five running audits and has returned HTTP 500 on every call since (≥ 45 min of retries). Restarting it is
outside the room. Results below come from the runs that completed (`truth3.py`, all 50 dev systems) and the partial output of the
killed ones, marked as such. The following are **unverified** until the engine is back: the full 17-kind B1 sweep with compositions
and pool states (`b1.py`); the trap sweep over all trap variants (`traps3.py`; 5 of ~27 systems done); the controls for the
remaining audit systems (`controls3.py`; 5 of 12 done); the public-field classifier (`leak3.py`); the realism of equivalent states
(`eqreal.py`); the generator's test suite; the calibration against targets v3 (`run_calib.py`).

## Per-finding table (round-2 findings)

| # | finding (round 2) | status | fix location | my re-run (round 3) |
|---|---|---|---|---|
| B1 | equal z ⇏ equal futures under state-reading interventions; truth-equivalent states trivial | **partly** | generator: on-manifold synaptic outputs (`integrate.py:84-91` kick clipping on v̂; §1, §1.2), `system.py:385-414` equivalent_states. Evaluator: unchanged (`evaluate_micro.py:318-331`) | `truth3.py`, 50/50 dev systems: 3 equivalent states each, with off-manifold detail on EVERY core unit (all Nc changed; max |w| 0.6–365 state units). Readout futures are **bit-identical (max |Δy| = 0.0 f_s)** under no event, a 9 m_s kick, silencing 0.1 s, the extreme window (tau 0.1, gain 1.9, 0.2 s), and a persistent current followed by silencing of the same unit. The generator part is fixed for these kinds. **Unverified** (killed run): gain / threshold / tau alone, edge removal, silencing another unit or a group, current sequences, same-unit kick → silence 5 / 25 ms after, pool states taken during persistent currents / silencing. **Not fixed (evaluator):** the "truth_equivalent" MEV comparison still compares true FUTURES of equivalent states, which are now identical by construction, so it is a model-independent 0 (see N2) |
| B2 | the benchmark's passive set exposes the central trap (`obs.init` with explicit states) | **partly** | `suites.py:372-379` (`init_spec`: obs.init = restart from a nominal passive trajectory of the same draw), `sampling.py:67` (r0 'state' never a development protocol) | `traps3.py` (partial, 5 audit trap systems; 8 draws, 24 multi-step schedules at spread 1–2, 16 restart-obs.init, 8 weight-noise; max hidden residual / scale): T25-hard, T6-hidden 0 everywhere (exposed 8.3 / 4.4); T15-medium ≤ 0.066 (bound 0.075; exposed 2.7); T22-rho0.3 ≤ 0.35 (bound 0.54; exposed 5.3); restart-obs.init ≤ 0.11. **But T21-m2: weight noise (an obs.wnoise D0 family) moves the residual to 0.97 > the exposing interventions' 0.672** (nominal / stimulus / restart ≤ 7e-16). See N1. Remaining ~22 trap systems unverified |
| B3 | r0 'state' on every unit: held-out targets / families / hidden units reachable | **fixed** | `sampling.py:63-70` (`init.state = False`, `units = "observed"` for every system), `simservice.py:244-246` (explicit states refused) | Public data (`pub3.py`, 10 systems, 7,098 rows): 0 explicit initial states (r0: 6,558 rest, 540 restart). Every manifest has `init.state = false`, `units = "observed"`. Restarts only from served / public trajectories (service code). The service's refusal is read, not run |
| B4 | controls 20 / 21 compressible at the bound; type 21 not observationally compressible on D0 | **partly** | `SlowModes` latent (§15 item 3), k_full ≈ 0.72 N_obs | `controls3.py` (5 of 12 systems; all single-unit kick + pulse responses, 3 states stacked). Dev T21-m2: residual at q = bound (15) median 2.9 / p90 3.7 f_s, 100 % > 1 f_s; rank needed 36 (2.4×). Dev T20-lin: 2.26 / 2.75, 100 %, 27 vs 13 (2.1×). Dev T20-sat: 1.65 / 1.99, 100 %, 43 vs 28 (1.5×; long horizon 1.39×). Dev T21-m1: 1.77 / 2.08, 100 %, 43 vs 26 (1.65×). **Audit T20-lin (syn-1e27cc2abbd5): long horizon median 1.02 f_s, only 58 % of responses > 1 f_s at the bound, rank 14 vs bound 11 (1.27×)**: not "a wide margin". Type-21 passive from nominal / stimulus / restarts: z rank 1–2 as claimed. **With weight noise: full rank (55 / 96), n95 7–8** (N1) |
| M1 | per-unit capability fields reveal roles, τ_c, rest potentials | **partly (unverified classifier)** | generator: one range [−500, 500], one noise scale, common size / readout-dim distributions (§15 item 4); benchmark: `sampling.py:90-101` collapses any per-unit list; `assert_public_record` refuses them | Public manifests: `admissible_range` {lo −500, hi 500}, `process_noise.sd_per_sqrt_s` 100, `init.units` "observed": no per-unit field. Non-full `simulate` info = {engine, success, system}. **Unverified:** my classifier over 400 systems (type / k / controls / roles from public fields and edges; `leak3.py`) was killed. Obvious remaining tell (documented): the small regime (N = 4–5 units) is types 3 / 4 / 6-small only. The generator's public edge list contains autapses (e.g. [52, 52] in syn-00e48aa6ad4d); their role-predictiveness is untested |
| M2 | lifts miss (29–69 %) / distinct lifts disagree | **fixed** | `system.py:236-` (common completion sample, miss ≤ 1e-3 or not returned, `report=True`) | `truth3.py`, 50 systems × 3 random requests (0.5 z_scale): every returned lift has an independently simulated miss ≤ 9.2e-4 (equal to the reported miss to 1e-15). Distinct lifts' futures agree to ≤ 8.9e-9 f_s (≤ 1e-12 in 47/50), also under a silencing 5 ms after completion. Type 10 (both dev systems) returns **0 lifts** for all 6 requests, and types 20 / 21 exactly 1 lift per request: reported, not faked (N4) |
| M3 | tests / calibration only on seed 0 | **partly** | `tests/conftest.py:19` (SEEDS = 20260926, 0, 7); `calibration_report.json` now tier dev, seed 20260926 | Code read. **Unverified:** I could not run the test suite (engine down) |
| M4 | obs.init magnitudes extreme / clipped / confinement | **fixed** | obs.init = restart from a nominal passive state (`suites.py:372-379`, `:1281-1295`) | Restart-obs.init trajectories are passive continuations (hidden residual ≤ 7e-16 on T21-m2, 0 on T25-hard / T6-hidden; ≤ 0.11 on T22-rho0.3). No explicit values, so nothing is clipped |
| M5 | closure bound misleading | **fixed** | SYNTHETIC_BENCHMARK.md §1.1–1.2 rewritten (measured numbers, exact closure) | The rewritten claim (bit-identical futures) matches my run for the kinds above |
| M6 | calibration report stale; `input_gain_elasticity_y` failing | **not fixed / unverified** (follow-up item 8) | readout input gain g(u) (§14); report against targets v2 (35 / 35) | The room's targets are version 3 (`data/calibration_targets.json`); the report is against v2. My re-run against v3 could not be started (engine down) |
| m1 | step self-convergence > 1e-3 f_s in 7 / 50 under the extreme window | **unverified** | configuration-based step refinement (§15 item 9) | not re-run |
| m2 | T22-rho0.04 passive bound exceeded | **partly** | bounds re-measured (§15 item 10) | T22-rho0.3 (audit) ≤ 0.35 vs new bound 0.54 at spread up to 2 over 48 passive runs; rho0.04 / rho0.1 not re-run |
| m3 | non-full `simulate` info leaks h / n_sub / clipped_kicks | **fixed** | `system.py` simulate | Non-full info = {engine, success, system} (`list.py`). `clipped_kicks`, `h`, `n_sub`, `n_sub_max` remain in the full output only |
| m4 | public_record carries content_hash / engine_id | **fixed at the benchmark** (unchanged in the generator) | `GENERATOR_PUBLIC_KEYS` whitelist | Public manifests have no content_hash / engine_id |
| m5 | moderate kicks clip at reachable states | **unverified** | one range ±500, clipping on v̂ (§15 item 11) | not re-run (killed) |
| m6 | minimality visible only for large / discrete shifts | no change needed (tolerance note) | — | — |
| (5) | no intervention visible at its onset sample | **fixed** | outputs at t_n use the configuration before t_n (§15 item 5) | `truth3.py`: item == twin (x and y bit-identical) up to and including the onset sample, 1,782 / 1,782 cases. Every kind (kick, current, current_seq, silence, gain 1.9 / 0.05, threshold, tau 0.1, edge removal) on one core and one nuisance target per system, at t = 0.5 s from rest and at t = 0 of a restart, 50 systems |
| (7) | new truth fields (kicks_applied in the full output, d_draw, draw_effective) | **not yet present** (follow-up) | — | The full output has no `kicks_applied` (it has `clipped_kicks`); `truth()` has no `d_draw`; the generator has no `draw_effective` (the benchmark calls it only `if hasattr`, `suites.py:1044`) |

Counts: fixed 7 (B3, M2, M4, M5, m3, m4, item 5); partly 6 (B1, B2, B4, M1, M3, m2); not fixed / unverified 5 (M6, m1, m5, item 7 not
yet delivered, and the unverified parts above); no change needed 1 (m6).

## New findings

**N1 (MAJOR). Weight noise in D0 exposes type 21 and makes its passive set full-rank.** `obs.wnoise` (8 of the 40 D0 trajectories,
`suites.py:124`) perturbs the interneuron projection E_F. For type 21 that breaks the exact passive subspace. Dev T21-m2: max hidden
residual 0.97 of scale under weight noise sd 0.02–0.1, versus 0.672 for the exposing interventions, and ≤ 7e-16 without weight
noise. Passive z has rank 1–2 without weight noise but full rank (55 / 96) with it (n95 7–8). So on the benchmark's D0, type 21 is
neither "observationally compressible" nor a trap whose residual only interventions move. Round-2 B4's fix asked to remove
obs.wnoise from type 21's passive data; that part is not done. *Fix:* leave `obs.wnoise` out of type 21's passive sets (or apply
weight noise only on the passive subspace's complement-preserving synapses), and add weight noise to the generator's type-21
passive-rank test.

**N2 (MAJOR, evaluator; the remainder of B1).** The generator now supplies non-trivial equivalent states, but
`evaluate_micro.py:318-331` still only compares the TRUE futures of equivalent pairs. Those are identical by construction, so the
comparison is a model-independent 0 whatever the method does. It does not test what non-trivial equivalent states are for: that the
MODEL maps equal-z states with different observed detail (core detail is visible in x) to close latents and close predicted futures.
*Fix:* report the model's whitened latent distance between equivalent states relative to random pairs (and its predicted-future
divergence under the pool sequences), and drop or relabel the true-future ratio.

**N3 (minor → major pending `eqreal.py`). Equivalent states are far outside the reachable observation range.** In `truth3.py` the
observed x of an equivalent state differs from the original's by up to 6,441 × obs_scale.x (T10-osc), 2,148 × (T19-adapt), 1,700 ×
(T9-relay), 1,579 × (T11-r6), 842 × (T22-rho0.1), 644 × (T23-exact). It exceeds 10 × obs_scale in 27 / 50 systems. The generator
gives every core unit, simultaneously, detail of 0.3–1 × the moderate kick (§15 item 2 "realistic size"). A reachable state carries
such detail on one or a few units. For types whose moderate kick is 100–200 state units (18-subhopf, 22) that puts all units far out
(max |w| 365 state units). If equivalent states are ever given to an encoder (N2's fix), they will be out of distribution. *Fix:*
draw the detail as the superposition of a few moderate single-unit kicks / currents aged by U(0, 3) τ_c (what interventions actually
leave), and check x stays within the range of reachable trajectories (`eqreal.py` is the test).

**N4 (minor). No truth lifts for type 10, a single lift for types 20 / 21.** Both dev type-10 systems return 0 lifts for 6 / 6
random 0.5 z_scale requests (the hidden mode dimension is unreachable by targetable kicks). Types 20 / 21 return exactly one lift per
request, so multiple-lift consistency has no truth reference there. Honest reporting (fewer lifts, not faked). *Fix:* have the
benchmark restrict lift requests to the reachable subspace (the column space of L over the public core targets) and state which
systems have no multiple-lift truth.

**N5 (minor, design note). Core units' synaptic outputs ignore their own membrane potential off-manifold.** The B1 fix computes
every output from v̂_i = b_i + E_i z. The detail w_i is observed in x but causally inert, and a kick δ on unit i changes that unit's
own output by only E_i L_i δ (≈ k / N_c of the kick). This makes closure exact and is documented (§1). But it is a modelling choice
that real units do not share, so the synthetic tier cannot represent closure failures of the kind round 2 measured. Real-vs-synthetic
comparisons of closure / MEV should say so.

**N6 (minor). The audit type-20 system is compressible at the long horizon by a narrow margin** (see B4 row: 1.27×, 42 % of
responses within f_s at the bound). The generator's own figure "1.35–3.1 ×" is for other systems. The controls' margin should be
enforced per system (reject a draw whose rank-at-tolerance is < 1.5 × the bound), not reported over the suite.

## Verdict

**Not ready to freeze.** The revision fixes the core of my round-2 blockers where I could run it:
- equivalent states are now non-trivial, and their futures are bit-identical under clipped kicks, silencing, the extreme window and
  current-then-silencing on all 50 dev systems;
- no intervention is visible at its onset sample (1,782 / 1,782 cases);
- lifts meet their tolerance or are withheld;
- explicit initial states are gone from every dataset and from development;
- the dev-tier controls have 1.5–2.4× margins.

Four things block the freeze:
- weight noise in D0 still exposes type 21 and makes its passive set full-rank (N1);
- the evaluator's truth-equivalent comparison is still model-independent (N2);
- one audit type-20 draw is compressible at the long horizon within a 1.27× margin (N6 / B4);
- the calibration against targets v3, the new truth fields (d_draw, draw_effective, kicks_applied) and a large part of my
  verification (full B1 kind sweep, compositions, pool states, trap sweep, public-field classifier, equivalent-state realism,
  generator tests) are outstanding. The last group is blocked by the Docker engine crash, not by the authors. The scripts are ready
  in `.tmp/T/r3/` and will be re-run as soon as the engine is back.
