"""p4synth: synthetic causal-state benchmark systems (25 types, several variants each).

    from p4synth import build_suite
    suite = build_suite("dev", 0)            # {system_id: SyntheticSystem}

See SYNTHETIC_BENCHMARK.md for the model, the types, the traps and the tests.
"""

from .engine import ENGINE_ID
from .suite import build_suite, build_system
from .system import SyntheticSystem
from .types import TYPE_NAMES, VARIANTS

__all__ = ["build_suite", "build_system", "SyntheticSystem", "ENGINE_ID", "TYPE_NAMES", "VARIANTS"]
__version__ = "1.0.0"
