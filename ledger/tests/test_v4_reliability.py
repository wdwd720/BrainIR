"""Run 4 analysis helpers (PREREG v4 A0, B6) on SYNTHETIC tables only."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))
import reliability_v2 as R2  # noqa: E402
import reliability_v2_bc as RB  # noqa: E402


def test_neuron_and_side_scores():
    rep = pd.DataFrame({"bodyId": [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3],
                        "replicate": [0, 1, 2, 3] * 3,
                        "usable": [True, True, False, True, False, False, False, False, True, True, True, True],
                        "score": [0.2, 0.4, 0.9, 0.6, 0.5, 0.5, 0.5, 0.5, 0.1, 0.1, 0.3, 0.3]})
    full = R2._neuron_scores(rep, "replicate", [0, 1, 2, 3])
    assert np.isclose(full[1], (0.2 + 0.4 + 0.6) / 3) and full[2] == 0.0 and np.isclose(full[3], 0.2)
    h1 = R2._neuron_scores(rep, "replicate", [0, 1])
    assert np.isclose(h1[1], 0.3) and h1[2] == 0.0 and np.isclose(h1[3], 0.1)
    side = R2._side_scores(full, {"T": [1, 3]})
    assert np.isclose(side["T"], (0.4 + 0.2) / 2)


def test_flips_and_rescue():
    rows = []
    for t, (sl, sr) in {"a": (0.9, 0.0), "b": (0.6, 0.55), "c": (0.0, 0.0)}.items():
        for s in range(8):
            rows.append(("L", t, s, sl))
            rows.append(("R", t, s, sr))
    df = {side: pd.DataFrame([{"type": t, "seed": s, "usable": True, "score": v} for sd, t, s, v in rows if sd == side])
          for side in ("L", "R")}
    flips = RB._flips(df["L"], df["R"], ["a", "b", "c"])
    assert flips == ["a"]  # band differs and fraction rhythmic differs by 1.0
    fixed = df["R"].copy()
    assert RB._rescued(fixed, df["R"], flips) == ["a"]
    assert RB._rescued(df["L"], df["R"], flips) == []


def test_same_minus_opposite_bootstrap_is_finite():
    rng = np.random.default_rng(0)
    types = [f"t{i}" for i in range(30)]
    base = rng.random(30)
    hf = {}
    for k in ("MANC-L", "MANC-R", "MCNS-L", "MCNS-R"):
        hf[k] = pd.DataFrame([{"type": t, "seed": s, "usable": True, "score": float(base[i] + 0.1 * rng.random())}
                              for i, t in enumerate(types) for s in range(16)])
    out = R2._same_minus_opposite(hf, types, n_boot=200)
    assert np.isfinite(out["difference"]) and out["n_boot_used"] > 150
