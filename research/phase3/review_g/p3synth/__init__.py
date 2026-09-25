"""Phase 3 synthetic state-discovery benchmark generators.

Public entry points:
    SyntheticSystem                 one system (simulate(protocol), truth(), lift_latent(delta_z, x))
    build_all / get_system          instantiate the catalogue for a suite seed
    build_suite(out_public, out_truth, seed, tier)
"""

from .core import SIM_VERSION, SyntheticSystem
from .protocol import ProtocolError, validate
from .suite import build_suite
from .systems import FAMILIES, TRAPS, build_all, catalog, get_system

__all__ = ["SIM_VERSION", "SyntheticSystem", "ProtocolError", "validate", "build_suite", "FAMILIES", "TRAPS", "build_all",
           "catalog", "get_system"]
