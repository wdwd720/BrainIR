"""Shared loaders for the second-round referee tests (read-only; no simulation, nothing written outside this directory).

Inputs: locked result files of run 6 (`thirdfly_v1/`, `posthoc_v6/`, `gates_v6/`), the locked tables of earlier runs, and the
collected result logs the third-fly lock hashes (`thirdfly_v1/MANIFEST.json`), read through the ledger's own loaders
(`brainir_ledger.screens6`). The C1 side sets are rebuilt from the locked `thirdfly_v1/banc_dn_sides.csv`, so no call reaches
`banc.dn_sides()` (which runs `git ls-remote`). Importing `thirdfly_v1` gives its pure helpers; its `build()` is never called.

Run every script as:  PYTHONDONTWRITEBYTECODE=1 uv run --project ledger --no-sync python <script>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[4]
LEDGER = REPO / "research" / "ledger"
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO / "ledger" / "scripts"))

import thirdfly_v1 as T  # noqa: E402  (pure helpers only; build() is never called)
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import banc as BN  # noqa: E402
from brainir_ledger import overlap6 as O6  # noqa: E402
from brainir_ledger import screens6 as S6  # noqa: E402

H16, H8 = T.H16, T.H8


def jload(rel: str) -> dict:
    return json.loads((LEDGER / rel).read_text())


C = jload("thirdfly_v1/C_tests.json")
H = jload("posthoc_v6/H_posthoc.json")
SETS = jload("gates_v6/TYPE_SETS_v6.json")


def screens() -> dict[str, pd.DataFrame]:
    """Replicate tables of every screen run 6 compares."""
    return {"B1r": S6.b1r(), "B2r": S6.b2r(), "A1": S6.a1(), "BT": S6.banc_tuned(), "BS": S6.banc_sweep(),
            "DX": S6.sweep_manc(), "MS": S6.sweep_mcns(), "BHL": S6.banc_side("L"), "BHR": S6.banc_side("R"),
            "BN1": S6.banc_copy(1), "BN2": S6.banc_copy(2)}


def c1_sets_from_csv() -> dict[str, list[str]]:
    """PREREG v6 B2 / thirdfly_v1.c1_sets, rebuilt from the locked side table (no git call)."""
    d = pd.read_csv(LEDGER / "thirdfly_v1" / "banc_dn_sides.csv")
    L = {t for t, g in d.groupby("manc_type") if (g["side"] == "L").any()}
    R = {t for t, g in d.groupby("manc_type") if (g["side"] == "R").any()}
    matched = sorted(L & R)
    lab = BN.match_confidence().set_index("manc_type")["banc_labels"]
    lc = [t for t in matched if ";" not in str(lab.get(t, ""))]
    return {"label_consistent": lc, "label_consistent_noDNg100": [t for t in lc if t != "DNg100"], "all_matched": matched}


def ts(df: pd.DataFrame, types=None, seeds=None) -> pd.Series:
    return AG.type_scores(df, seeds, types)


def hyper_p(k: int, N: int, n_y: int, n_x: int) -> float:
    from scipy import stats

    return float(stats.hypergeom.sf(k - 1, N, n_y, n_x))


def show(title: str, obj) -> None:
    print(f"\n== {title}")
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else str(o)))
    else:
        print(obj)
