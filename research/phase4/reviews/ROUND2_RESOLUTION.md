# Round-2 pre-freeze reviews: resolution map (orchestrator; ANSWER-FREE but orchestrator-only)

Reviews: `E2_review.md` (statistics), `H2_review.md` (numerics), `F2_review.md` (leakage / isolation), `T_review.md` (truth audit of
the synthetic generator). All four: "not ready to freeze". Owners: AUTHOR = the synthetic generator's author (bench room, resumed);
E13 = reference learner v2; E14 = dataset design; E15 = statistics / selection; E16 = isolation; ORCH = orchestrator.

| finding | summary | owner | status |
|---|---|---|---|
| T-B1 | true z not a causal state under state-reading interventions (off-manifold core detail); truth-equivalent states vacuous | AUTHOR (+ E14 if the fix is a horizon) | open |
| T-B2 | the benchmark's passive obs.init (explicit states) exposes the trap variable | E14 (obs.init = restart from nominal trajectories) | fixed by E14 (P4-D40; real rebuilt; synthetic tiers rebuilt after the generator revision); awaits round 3 |
| T-B3 | r0 'state' = kick at t = 0, may set every unit: held-out targets / kick families / hidden units accessible | E14 (r0 'state' out of every development / public policy) | fixed by E14 (init.state = false everywhere; 0 explicit states in the real rebuild); awaits round 3 |
| T-B4 | non-compressible controls (types 20, 21) compressible at the tolerance | AUTHOR | open |
| T-M1 | per-unit capability fields reveal unit roles, tau_c, rest potentials | AUTHOR + E14 (strip in normalize_capability) | benchmark side fixed by E14 (system-wide values; per-unit lists refused); generator side open |
| T-M2 | lift_latent misses its request on several systems | AUTHOR | open |
| T-M3 | generator tests / calibration on seed 0 only | AUTHOR | open |
| T-M4 | obs.init values extreme, clipped, artefactual | E14 (resolved by T-B2 fix) | fixed (no explicit states) |
| T-M5 | closure bound understated | AUTHOR | open |
| T-M6 | calibration report stale; input_gain_elasticity_y fails (P4-D35) | AUTHOR (recalibration in progress) | open |
| T-m1..m6 | step convergence at extreme tau; rho0.04 bound; info fields; public_record keys (whitelisted); moderate kicks clip; minimality caveat | AUTHOR (m1, m2, m3, m5); ORCH (m4 kept whitelisted; m6 noted in 5.16) | open |
| H-N1 | intervention visible at the onset sample (generator) | AUTHOR (fix) + E14 (build-time item == twin check up to the onset) | benchmark check in place (E14); generator fix open |
| H-N2 | step accuracy only tested on seed 0 | AUTHOR | open |
| H-N3 | truth-equivalent comparison uninformative | AUTHOR (T-B1 item 2) | open |
| H-N4 | kick jump vs one sample later differs 4 % median | ORCH: informational (sampling), noted | noted |
| H-N5 | clipped kicks labelled by requested magnitude | E14 (realized size recorded; class by realized size) | fixed by E14 (synthetic needs the generator to report kicks_applied) |
| H-N6 | synthetic simulations not host-gated | E14 | fixed by E14 (SimContext.run host-gated) |
| F-N-B1 | readout_dim reveals types 20 / 21 | AUTHOR | open |
| F-N-M1 | service cache timing across agents; tokens not bound to queues; tokens printable | E16 | fixed by E16 (per-agent store namespaces; queue-bound tokens outside the host env; env listings refused); canary v4; awaits round 3 |
| F-N-M2 | other agents' files writable in shared work areas | E16 | fixed by E16 (owned per-agent subdirectories rw, rest ro; guard; builder owned_areas); canary v4; awaits round 3 |
| F-N-M3 | public size fields predict k | AUTHOR | open |
| F-M4 / M5 partial | tokens portable; round cap only within one call | E16 | fixed by E16 (queue binding; persistent FEEDBACK_RELEASES.json; tournament.py change forwarded to E15); awaits round 3 |
| F minors | abbreviated long options; gc tripwire; worker state between calls; 26 all-zero real futures | E16 (first three: fixed / documented), E14 (last: kept and counted, P4-D40) | fixed / documented |
| E-N1 | tournament decide step does not run the selection rule; one seed | E15 | fixed by E15 (P4-D39); awaits round 3 |
| E-N2 | class-balanced EE CI under-covers (tiny classes, no rescaling); A / C need the family level | E15 | fixed by E15 (P4-D39); awaits round 3 (residual: A interval one-sided error up to ~0.06 under strong heterogeneity, stated) |
| E-N3 | 5 % unusable allowance hides a read-in error | E15 | fixed by E15 (P4-D39); awaits round 3 |
| E-N4 | percentile search switches criteria off | E15 | fixed by E15 (P4-D39); awaits round 3 |
| E-N5 | P_t on a different item set from the calibration | E15 | fixed by E15 (P4-D39); awaits round 3 |
| E-N6 | active-design union > 5 % under a plausible null | E15 | fixed by E15 (P4-D39); awaits round 3 |
| E-N7 | criterion F passes by construction | E15 | fixed by E15 (P4-D39); awaits round 3 |
| E-N8..N10, m3 | ratio bias; margins vs CI widths; missing true-state results; unshrunk base | E15 | fixed by E15 (P4-D39); awaits round 3 |
| (orchestrator finding) | shared reference learner worse than no effect on dev systems | E13 | fixed by E13 (learner v2, P4-D42: TRUE-STATE median EE_cb 0.67, 76 % below 1); k-consistency rule P4-D43; awaits the calibration on the rebuilt dev tier and round 3 |

Round 3 (after all fixes, rebuilt data and the calibration): E, H, F, T verify every row; nothing is frozen before that.

## Round 3 (verification) status
- F (reviews/F3_review.md, 2026-09-27): fixed N-M1, N-M2, N-m1, N-m3, M4; M5 re-release gap and N3-m2 / m2 / N3-m1 fixed by the
  orchestrator afterwards (P4-D44); open only through the generator revision: N-B1 (readout_dim), N-M3 (size fields vs k). No new
  blocker or major. F re-verifies N-B1 / N-M3 on the revised generator.
- E (reviews/E3_review.md, 2026-09-27): fixed 15 of 24 (N1, N3-N8, N10, B3, B5, M4, M5, m3, m4, m8), partly 5 (N2, N9, M1, M2, M3),
  unverified 3 (M6, m5, m6). NEW: N-new-1 BLOCKER (the TRUE-STATE reference encodes z only; per-trajectory draws leave 0.43-0.63 of the
  effect undetermined on 6 types) -> E13 (reference encodes [z, draw]; generator provides draw_effective); N-new-2 (attainable without
  a binding mediation / closure criterion), N-new-4 (few-family interval liberal), N-new-5..9 minors -> E15; N-new-3 (k window width)
  waits for the generator's d_draw values. Calibration / MDE outputs still to come.
