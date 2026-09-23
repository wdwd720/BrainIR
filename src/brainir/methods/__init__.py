"""Discovery methods (registered with :class:`brainir.discovery.MethodRegistry`).

    greedy_reference  simulation-guided backward elimination on the generic API (the Phase 1 baseline's algorithm,
                      re-expressed so it can run on synthetic instances with any criterion; the frozen baseline itself
                      is `benchmarks/dng100/baselines/greedy_prune_sim.py` and is used unchanged for the dng100 comparison)
    greedy_plus       evidence-driven group elimination (Phase 2 tournament family A)
    cem_search        cross-entropy / EDA search over keep-only masks (family B)
    group_probe       active group testing with posterior inclusion probabilities (family C)
    surrogate_search  surrogate-assisted search (family D)
    evo_pareto        evolutionary multi-objective search (family E)
    brainir_v1        the Phase 2 method

Every candidate module present in the package is imported (and thereby registered); import errors propagate.
"""

from __future__ import annotations

import importlib
import importlib.util

from . import greedy_reference  # noqa: F401  (registers)

CANDIDATE_MODULES = ("greedy_plus", "cem_search", "group_probe", "surrogate_search", "evo_pareto", "brainir_v1")

for _name in CANDIDATE_MODULES:
    if importlib.util.find_spec(f"{__name__}.{_name}") is not None:
        importlib.import_module(f"{__name__}.{_name}")
