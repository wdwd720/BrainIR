# Hidden-oracle evaluation log (Phase 2)

Every evaluation of a prediction against the frozen dng100 oracle during Phase 2 is appended here (goal3 §28–29).
Policy: the frozen Phase 1 baseline may be evaluated for its reliability sweep (its outcome is not used to design
BrainIR v1 and is not shown to method developers); BrainIR v1 is evaluated only after `METHOD_LOCK.json` and the tag
`brainir-v1-preblind` exist; any further attempt is a new, separately locked method version.

| when (UTC) | what | method | network | n predictions | outcome | purpose |
|---|---|---|---|---|---|---|
| 2026-09-25T00:39:25Z | reliability sweep `v12_manc_v1.2.1` | `brainir_v1` | `manc_v1.2.1` | 24 | success rate 0.8333333333333334, E-core recall mean 1.0 | baseline/final-method reliability (structural families, no simulation) |
| 2026-09-25T00:40:32Z | reliability sweep `greedy_frozen_manc_v1.2.1` | `greedy_prune_sim_frozen` | `manc_v1.2.1` | 24 | success rate 0.6666666666666666, E-core recall mean 0.8333333333333334 | baseline/final-method reliability (structural families, no simulation) |
| 2026-09-25T00:41:39Z | reliability sweep `v12_male-cns_v1.0` | `brainir_v1` | `male-cns_v1.0` | 24 | success rate 1.0, E-core recall mean 1.0 | baseline/final-method reliability (structural families, no simulation) |
| 2026-09-25T00:42:44Z | reliability sweep `greedy_frozen_male-cns_v1.0` | `greedy_prune_sim_frozen` | `male-cns_v1.0` | 24 | success rate 0.9166666666666666, E-core recall mean 0.9583333333333334 | baseline/final-method reliability (structural families, no simulation) |
| 2026-09-25T00:43:50Z | reliability sweep `v12_manc_v1.2.3` | `brainir_v1` | `manc_v1.2.3` | 24 | success rate 0.875, E-core recall mean 1.0 | baseline/final-method reliability (structural families, no simulation) |
| 2026-09-25T00:44:55Z | reliability sweep `greedy_frozen_manc_v1.2.3` | `greedy_prune_sim_frozen` | `manc_v1.2.3` | 24 | success rate 0.6666666666666666, E-core recall mean 0.9166666666666666 | baseline/final-method reliability (structural families, no simulation) |
