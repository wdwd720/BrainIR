# Notice from the orchestrator: public evaluator version 3 (2026-09-25)

Independent pre-lock reviews examined the evaluation. The benchmark was revised to version 3 BEFORE any method was locked, before the
final synthetic suite was used, and before any hidden real data existed. The public evaluator in `src/brainir_state/` (evaluate,
evaluate_cross, evaluate_lift, harness, refmodels), `docs/PROTOCOL.md` and `data/tolerances.json` are updated. The full list of
changes is in docs/PROTOCOL.md section 10.1; sections 4 and 6-9 give the definitions.

The method API is unchanged. Two contract points are now ENFORCED by the evaluator:

1. **Predictions must go through z.** Every rollout and readout runs on a fresh copy of your model as it was before the evaluation
   started encoding: nothing `encode()` stores in the object can reach a prediction. The rollout checks (family R) restart your
   model's own rollout from its predicted z on a fresh copy, after event-free stretches and after interventions, and compare a
   rollout made right after encoding with one made after other histories were encoded. If the restarted rollout does not reproduce
   z and y (relative tolerance 1e-4), the model carries memory beyond z: its k is invalid, and it cannot be "compact" or "closed".
   `encode()` must be deterministic.
2. **Fits must be deterministic** given data, configuration and seed (no wall-clock-dependent branches).

What else changes:

- **A (prediction).** A level-corrected NMSE (each window's mean error removed) is reported. On the REAL systems the readout NMSE is
  POOLED over readout neurons (sum of squared errors / sum of training variances), and the predictive condition compares your model
  with the input-only control and the persistence floor; the readout-history control and the full-state model are reported only.
- **C (interventions).**
  - The verdict's C uses held-out pairs whose events act on OBSERVED neurons. Pairs with a target outside the observed population
    are reported apart.
  - On real MECHANISM systems every observed neuron is a public target, so the held-out C there is group silencing only.
  - The interventional condition: the upper CI of C below 1, the largest leave-one-pair-out C below 1, no abstention; untestable
    with fewer than 3 pairs. It supports the claim "held-out intervention effects are predicted better than no effect".
  - Also reported: C with z0 replaced by the mean training encoding (does the prediction depend on the state?), null pairs, and the
    interventional closure gap.
- **D (closure).** The base (z, u, future input) of each closure regression is fitted without shrinkage, and the residual microstate
  is computed inside each training fold. "Closed" now also requires the upper CI of the HISTORY gain to be at most tau_H (and a
  closure-gap condition if the calibration's power rule admits it).
- **Tolerances.** Recalibrated (`data/tolerances.json`, including tau_H and tau_gap; tau_gap may be null, meaning "reported, not
  judged").
- **Lifting.** Identical or near-identical lifts are not counted as distinct; without distinct lifts, implementation invariance is
  "untestable".
- **Tournament profile.** S3 = median of max(0, upper CI of the D micro-gain). S5 = median of min(R^2 true latent from z, R^2 z from
  true latent). S6 = the rate at which your POINT k equals the true k (the reported k range is descriptive and earns no credit).
  A pre-registered decision rule resolves close rankings: if the leader's bootstrap P(rank 1) is below 0.5, the tie set is resolved by
  the smallest median k.
- **Baselines.** Declared baselines may receive independently tuned variants (`<baseline>_t`).

Numbers from your earlier self-evaluations are not comparable with version 3. Re-run what you rely on with the updated evaluator.
