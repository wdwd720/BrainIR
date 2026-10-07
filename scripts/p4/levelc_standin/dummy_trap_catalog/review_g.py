"""DUMMY trap catalog of the Level C driver's DRY RUN. It is NOT review G's catalog: that one is research/phase4/review_g/review_g.py,
hashed by the method lock and baked only into official Level C runs.

`level_c.py trap-probe` bakes THIS file at the catalog's container path (levelc_lib.TRAP_CATALOG_CONTAINER) to check, before the lock,
that a Level C image loads a catalog the way `brainir_causal.synthadapter.load_trap_catalog` does (as the submodule
`<generator package>.review_g`, relative imports into the generator) and that the catalog is root-only in an iso container. Interface of
review G's contract (research/phase4/review_contracts/REVIEW_G_CONTRACT.md): review_g_catalog(seed) -> a list of systems, each with a
trap label, its causal state (k or "none") and the honest verdict. The dummy relabels systems of two existing public generator types; it
adds no trap logic.
"""

from __future__ import annotations

from .suite import build_system

#: (generator type, dummy label): 23 = intervention confounding (a compact state), 21 = observationally compressible but
#: interventionally non-compressible (k "none")
DUMMY_TRAPS = ((23, "G-dummy-1"), (21, "G-dummy-2"))


def review_g_catalog(seed: int) -> list:
    out = []
    for t, label in DUMMY_TRAPS:
        s = build_system("trapdummy", int(seed), t, 0, 1)
        s.info["trap"] = label
        s.info["trap_grade"] = "dummy (dry run)"
        out.append(s)
    return out
