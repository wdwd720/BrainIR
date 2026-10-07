"""Shared, TRUSTED code of the post-lock drivers (goal5 sections 75, 84, 87-91): ablations (scripts/p4/ablations_p4.py),
counterexample search (counterexamples_p4.py), robustness sweeps (robustness_p4.py), counterfactual API evaluation
(counterfactual_p4.py) and the self-audit executor (self_audit_p4.py). ORCHESTRATOR SIDE; hashed by the method lock.

- `common`   paths, the hidden-data guard (hidden tiers only after the method lock; START / DONE log rows), system resolution in the
             remote layout, Modal submission helpers, JSON I/O;
- `declare`  the ablation contract of `brainir_causal.api` (ABLATION_SWITCHES, config "ablate", info "ablation_switches" / "ablated");
- `pstats`   paired statistics: suite-level system bootstrap, per-system identity-cell estimates, one-sided bounds, Holm;
- `isojob`   custom TRUSTED jobs inside the ISOLATED containers (method code only in unprivileged model workers): the passive-only
             fit of the critical ablation, per-item predictions with validity / uncertainty / API completeness, audit probes;
- `itemsets` custom evaluation item sets (counterexample candidates, robustness grids) planned here and built on Modal with the
             benchmark's own builder (`suites.build_system_job`).

The package is baked into the Modal images at /repo/phase4/src/p4post (`common.extra_dirs`), so container jobs import it as `p4post`.
"""

VERSION = "p4post-1"
