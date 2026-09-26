## Summary

**Conclusion (goal4 section 85, criterion 50): NOT SUPPORTED for the real connectome-constrained circuits; partially supported on
synthetic systems with known state.**

**Method.** BrainIR State v1 was built by an oracle-free composer in a technologically isolated clean room. It uses a linear causal
encoder on delay features (a reduced-rank predictive basis), a sparse E-SINDy latent law, a polynomial readout, calibrated
event operators, a generic plateau rule for k and abstention rules (section 13). It was selected in three Level B rounds on the
synthetic heldout suite by a pre-registered rule (P(rank 1) = 0.52), and locked before any use of the FINAL suite or of hidden
real data.

**Synthetic FINAL suite** (48 systems, run once after the lock):
- compact causal state discovered on 19 of 46 compressible systems, partially supported on 12;
- exact k on 27 of 46;
- latent recovery K = 0.987 (min R^2 both ways);
- prediction A / A_full = 0.997.

It ranks 3rd of 9 eligible methods behind the comparator lin_dmdc_t, so the heldout selection did not replicate. It is better on
prediction and dimension, tied on interventions, and worse on closure, latent recovery and abstention.

**Real circuits** (Level C: 10 connectome-constrained rate-model systems, hidden test generated after the lock, run once):
- A 2-3 dimensional latent predicts the held-out readout of all three full networks better than input-only and persistence
  controls.
- It never predicts the effects of held-out interventions better than "no effect". Held-out C is 1.27, 0.96 and 1.04, with upper
  CIs >= 1.
- The verdict is "not supported" on 9 of 10 systems and partially supported on net3 full.
- Against the comparator: non-inferior on 5 of 13 pre-registered comparisons, significantly better on 2, worse on 3.
- No shared dynamics across mechanisms or across independently reconstructed connectomes.
- The same k across 5 seeds on only 2 of 10 systems.

**Robustness and counterexamples.** An out-of-distribution stimulus degrades prediction up to 75-fold. Counterexample searches
break the intervention predictions almost at once: on 9 of 48 FINAL systems and on 5 of 10 real systems.

**Integrity.**
- The Phase 1 and Phase 2 locks are intact, and the Phase 3 method lock holds.
- Every hidden evaluation is logged, with no post-hidden change to the method.
- Reviews A-H were completed before the lock, and the post-lock reviews are in section 18.
- Hidden real data and Level C ran on one deterministic compute platform (host-gated Modal).
