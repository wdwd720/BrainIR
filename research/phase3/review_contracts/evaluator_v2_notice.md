# Notice from the orchestrator: public evaluator version 2 (2026-09-25)

Independent reviews of the evaluation machinery found errors in the benchmark's evaluator and statistics. The benchmark was revised to
version 2 BEFORE any candidate was scored on held-out data. The public evaluator in `src/brainir_state/` (evaluate, evaluate_cross,
evaluate_lift, harness, refmodels), `docs/PROTOCOL.md` and `data/tolerances.json` are updated. The full list of changes is in
docs/PROTOCOL.md section 10.1; sections 4 and 6-9 give the definitions.

Your method code and the method API are unchanged, and nothing you must implement is new. What changes:

- **A (prediction).** Window errors are capped at NMSE 10. A non-finite prediction counts as the cap and is never dropped.
- **C (interventions).** The verdict's C covers held-out interventions on the STATE or the INPUT: kicks, currents and silencing, in
  group, new-target and combined forms. Structural interventions (edge removal) are scored separately as `C_structural` and are
  reported, not part of the verdict. Each result also reports `n_eff`.
- **D (closure).**
  - D is averaged over 5 repeated cross-fits.
  - The future input over the task horizon is a feature for every model.
  - Readout targets keep the public training scale.
  - D has a 95 % CI (`micro_gain_ci95`, by trajectory); the verdict judges its UPPER bound.
- **E (microstate equivalence).**
  - Latent distances are whitened with the full covariance of your model's encodings of TRAINING trajectories, so E no longer depends
    on the coordinates of z. Pass your training trajectories: `harness.evaluate_system(..., train=train_trajectories)`. Without them,
    E falls back to the pool's own covariance.
  - E has a 95 % CI (`E_ratio_ci95`), and the verdict judges its upper bound.
  - E can be `untestable` when the pool is too sparse for the latent's dimension. The verdict then has its own category: "compact
    causal state discovered (microstate equivalence untestable)".
- **References.** Reference controls are fitted on train + val, like your fits, without finite blow-up trajectories. The input-only
  and readout-history controls now have one direct model per step, which makes them stronger.
- **Tolerances.** All four were recalibrated: tau_D and tau_E now apply to upper CI bounds (`data/tolerances.json`).
- **Tournament.**
  - Profiles are computed over the same fixed list of systems for every candidate, and a failure counts as the worst value.
  - Ranks are order-independent: average ranks for ties.
  - Sharing margins are relative: 20 % of the independent model's A; for C, max(0.05, 20 % of the independent C).
  - The unrelated-system nulls also get leave-one-implementation-out fits.
  - S8 is the balanced accuracy over groups and pairs.

Numbers from your earlier self-evaluations are not comparable with version 2. Re-run what you rely on (for example your dimension-rule
checks) with the updated evaluator.
