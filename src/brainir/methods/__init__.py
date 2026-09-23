"""Discovery methods (registered with :class:`brainir.discovery.MethodRegistry`).

    greedy_reference  simulation-guided backward elimination on the generic API (the Phase 1 baseline's algorithm,
                      re-expressed so it can run on synthetic instances with any criterion; the frozen baseline itself
                      is `benchmarks/dng100/baselines/greedy_prune_sim.py` and is used unchanged for the dng100 comparison)
    brainir_v1        the Phase 2 method (added by the method-development tournament)
"""

from __future__ import annotations

from . import greedy_reference  # noqa: F401  (registers)

try:  # the Phase 2 method is added later; its absence must not break the registry
    from . import brainir_v1  # noqa: F401
except ImportError:  # pragma: no cover
    pass
