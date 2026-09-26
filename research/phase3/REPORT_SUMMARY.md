## Summary

**Conclusion (goal4 section 85, criterion 50): NOT SUPPORTED for the connectome-constrained rate-model simulations (the "real"
systems); partially supported on the synthetic FINAL suite, whose latent state is known.** PROTOCOL.md defines verdicts per system;
no suite-level rule was pre-registered, so these labels summarise the per-system counts below (section 23).

**Phase 3 status.** Every pre-registered stage ran once and is reported. 49 of the 50 acceptance criteria are met. Criterion 26 is
only partly met: lifting exists in the benchmark and 8 baseline models lift, but the locked method has no `lift()`, so its latent
interventions are untested. goal4 section 85 says not to declare Phase 3 complete until all criteria are satisfied, so **Phase 3 is
not declared complete** (section 15).

**Method.** BrainIR State v1 was built by an oracle-free composer in a technologically isolated clean room. It has:
- a linear causal encoder on delay features (a reduced-rank predictive basis);
- a sparse E-SINDy latent law and a polynomial readout;
- calibrated event operators;
- a generic plateau rule for k, and abstention rules (section 13).

It was selected in three Level B rounds on the synthetic heldout suite by a pre-registered rule (P(rank 1) = 0.52; the margin was
narrow). It was locked before any method was fitted or evaluated on the FINAL suite and before any hidden real data existed.

**Synthetic FINAL suite** (48 systems, run once after the lock).
- Verdicts on the 46 compressible systems: "compact causal state discovered" on 17; the same with microstate equivalence untestable
  (a separate category) on 2; partially supported on 12; not supported on 15.
- The verdict certifies sufficiency, not k: 5 of those 19 have the wrong k, including k = 8 against 1 on the nuisance trap A (latent
  recovery 0.12, not state-mediated).
- Exact k on 27 of 46. Latent recovery K (min R^2 both ways): median 0.987, mean 0.86, below 0.5 on 5 of 46.
- It ranks 3rd of 9 eligible methods, behind the comparator lin_dmdc_t and its twin (also 3rd on S1-S5 alone), so the heldout
  selection did not replicate.
- Paired over systems it is significantly better than the comparator on prediction (S1 -0.30 [-0.57, -0.07]) and exact k (27
  against 16 of 46; McNemar p = 0.013), with no significant difference on held-out C, closure, microstate equivalence or latent
  recovery.
- It abstains on 1 of 2 non-compressible controls (the comparator on 2 of 2), with fewer false alarms (2 % against 28 %) and more
  confident-wrong claims (52 % against 33 %).
- The interventional results are scoped to held-out targets and additive group interventions in population-code systems.

**Connectome-constrained rate-model simulations** (Level C: 10 systems; the hidden test was generated after the lock and run once).
They are simulations of a deterministic rate model on connectome-derived weights, with assumed neuron parameters, no noise, and kicks
clipped at 0 Hz: not recordings, and not statements about the animal. The verdicts are conditional on the synthetic calibration of
the tolerances.
- **The method's own abstentions.** It declared "no compact state" on 8 of 10 systems: on net2 full (its latent explains too little
  beyond the input) and on all 7 mechanisms (k exceeds N_observed / 5; they observe 3-6 neurons). It claimed a compact state only on
  net1 full and net3 full, two builds of ONE reconstruction.
- **Prediction.** A 2-3 dimensional latent (seed 0) predicts the held-out readout of all three full networks better than the
  input-only control and persistence (readout NMSE 0.024, 0.51 and 0.0055 at 250 ms). At that horizon a PCA latent of the same
  dimension is significantly better on 2 of 10 systems (both on net2), and the locked method is significantly better on 6. The
  dimension is fragile: across half-samples of the training data k is 2-8 on net1 full and 2-6 on net2 full.
- **Interventions.** On every full network the method abstained on all kick and current interventions (60 of 120 held-out pairs)
  and predicted only silencing. There its held-out C is 1.27, 0.96 and 1.04 (1 = predicting no effect; upper CIs >= 1; 45-49 of 60
  pairs null), and its predictions do not depend on the encoded state. On no full network does it predict held-out effects better
  than "no effect". The one interventional pass on a real system (net3 mechanism b, C 0.38 [0.21, 0.67]) is not state-mediated, and
  the method declared no compact state there. On 4 of 7 mechanisms it abstained on every held-out pair.
- **Verdicts.** "Not supported" on 9 of 10 systems. net3 full is "partially supported": predictive and closed, not interventional,
  and its latent is poorly reproduced across seeds and half-samples.
- **Against the comparator** (pre-registered, Holm): non-inferior on 5 of 13 comparisons (net2 C, D, E; net3 A, C); significantly
  better on net3 A and net3 C; worse on net1 E, net2 A and net3 E; K not shown non-inferior (Holm p 0.30). The C comparisons cover
  the silencing pairs only, and there neither method is better than predicting no effect.
- **Sharing.** The method's internal test declined to share on every network and pair, so its "shared" models are its independent
  models. Adapting dynamics between the independent reconstructions was far worse than a fit from scratch (one pair, one direction).
  This is a result about v1, not evidence that the circuits lack shared dynamics.
- **Seeds.** k agrees across 5 seeds on 2 of 10 systems (net3 full and one net3 mechanism, both of one reconstruction).

**Traps and abstention.**
- On the FINAL traps it claims a compact causal state with the wrong k on the nuisance (8 against 1), parameter (2 against 1) and
  transient (3 against 2) traps.
- On review G's 10 unseen traps it gets k wrong on 5 of 9 and does not abstain on the non-compressible G10.

**Robustness and counterexamples.**
- At the primary 250 ms horizon, an out-of-distribution stimulus degrades the locked method's prediction about 235-fold on net1 full
  (0.024 to at least 5.7), against about 29-fold for the comparator. Under it the method predicts worse than the input-only control
  on net1 and net3 full.
- Counterexample searches find extreme intervention-effect errors, mostly on protocols whose true effect is near zero, both inside
  and outside the public protocol families. They break the method at once on 9 of 48 FINAL systems, and on 5 of 10 real systems with
  public parameter draws (3 of 10 with hidden draws).

**Biggest limitation.** The learned state does not carry intervention effects: on the real systems the method abstains on kicks and
currents, its silencing predictions are state-independent and no better than "no effect", and v1 cannot lift latent interventions.

**Integrity.**
- The Phase 1 and Phase 2 locks are intact, and the Phase 3 method lock holds.
- Every hidden evaluation is logged. Rows found missing by review R were appended retrospectively and marked.
- There was no post-hidden change to the method.
- Reviews A-H were completed before the lock. The post-lock reviews S, C, Y and R found reporting errors in the first draft, all
  corrected here; none changed a verdict (section 18.1).
- Post-lock review L (leakage and process, answer-aware) found no blocker. The lock preceded every hidden evaluation, no change reached
  v1, the salt was revealed only after Level C, and the rooms and transcripts are clean. Its one major finding was a stopped
  reference-control precompute that touched 2 FINAL systems before the lock, with no method involved. It is disclosed, with 8 minor
  documentation fixes (section 12).
- Hidden real data and Level C ran on one deterministic compute platform (host-gated Modal), except the pre-registered local
  hidden-draw counterexample sweep.
- Modal: $135 billed; the job-record list-price estimate is $272 (section 22).
- Tests: the old root suite has 552 passed (incl. the 18 real-data tests), 1 opt-in Modal test skipped and 0 failed; the Phase 3
  suite has 194 passed.
