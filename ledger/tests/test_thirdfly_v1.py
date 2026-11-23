"""PREREG v6 X4: the Part C / V analysis code runs and behaves as defined, with the first two animals' screens standing in for BANC
(no BANC result exists before the freeze, and no wiring summary of BANC descending neurons is computed here)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

from brainir_ledger import RESEARCH  # noqa: E402
from brainir_ledger import screens6 as S6  # noqa: E402

if not (RESEARCH / "predictions_v2" / "B1r" / "replicates.parquet").exists():
    pytest.skip("locked screens not available", allow_module_level=True)
B = pytest.importorskip("brainir_ledger.banc")
try:
    B.fetch()
except Exception:  # noqa: BLE001
    pytest.skip("BANC sources not available", allow_module_level=True)

import thirdfly_v1 as T  # noqa: E402


def test_sets_sizes():
    s = T.sets()
    assert len(s["three_animal"]) == 182 and len(s["manc_mcns_high"]) == 215 and len(s["manc_mcns_all"]) == 310
    assert set(s["three_animal"]) <= set(s["manc_banc_high"]) and set(s["three_animal"]) <= set(s["mcns_banc_high"])


def test_validity_rule():
    bt = pd.DataFrame({"type": ["DNg100"] * 16, "seed": range(16), "usable": [True] * 16, "score": [0.9] * 11 + [0.1] * 5})
    bs = pd.DataFrame({"type": ["DNg100"] * 8, "seed": range(8), "usable": [True] * 8, "score": [0.9] * 6 + [0.0] * 2})
    v = T.validity(bt, bs)
    assert v["tuned"]["valid"] is False and v["sweep"]["valid"] is True and v["primary"] == "sweep"
    bt.loc[:11, "score"] = 0.9
    assert T.validity(bt, bs)["primary"] == "tuned"
    bs.loc[:, "score"] = 0.0
    bt.loc[:, "score"] = 0.0
    assert T.validity(bt, bs)["primary"] == "not judged"


def _stand_in(m: pd.DataFrame, c: pd.DataFrame) -> pd.DataFrame:
    """A synthetic BANC-like replicate table over every BANC group and both animals' types (16 seeds): MaleCNS replicates where the
    type has them, else MANC's, with a fixed jitter. It stands in for a BANC screen only to exercise the code."""
    rng = np.random.default_rng(0)
    types = sorted(set(B.groups()) | set(m["type"]) | set(c["type"]))
    src = pd.concat([c, m[~m["type"].isin(set(c["type"]))]])
    d = src[src["type"].isin(types)].copy()
    miss = sorted(set(types) - set(d["type"]))
    if miss:
        d = pd.concat([d, pd.DataFrame([{"type": t, "seed": s, "usable": True, "score": 0.0} for t in miss for s in range(16)])])
    d["score"] = np.clip(d["score"] + rng.normal(0, 0.05, len(d)), 0, 1)
    return d.reset_index(drop=True)


def test_c3_c4_c6_c7_c8_on_stand_ins():
    m, c = S6.b1r(), S6.b2r()
    stand_in = _stand_in(m, c)
    r3 = T.c3({"tuned": (m, c, stand_in, T.H16), "sweep": None}, "tuned")
    assert r3["first_line_words"] in ("confirmed in the third animal", "not confirmed", "inconclusive")
    ref = r3["tuned"]["MANC-MaleCNS (reference, post hoc)"]["manc_mcns_all"]["primary"]["ratio"]
    assert ref == pytest.approx(0.380, abs=5e-4)
    r4 = T.c4({"B1r": (m, T.H16, ("manc_banc_high",))}, stand_in, T.H16)
    blk = r4["B1r"]["manc_banc_high|without_DNg100"]
    assert "DNg100" not in blk["cuts"]["0.5"]["overlap"]["point"]["types_in_both"]
    assert blk["words_at_0.5"] in ("at chance at the authors' cut", "above chance")
    r6 = T.c6(m, c, stand_in)
    assert r6["words"] in ("pooling helps", "not shown") and r6["n_types"] == 182
    r7 = T.c7(m, c, stand_in, T.H16)
    assert r7["rbar"] > 0 and r7["n_star"] == pytest.approx(4 * (1 - r7["rbar"]) / r7["rbar"])
    T.N_PERM = 2000
    r8 = T.c8(stand_in)
    assert r8["primary"]["n"] == 12 and "DNg100" not in r8["primary"]["types"] and 0 < r8["primary"]["p_one_sided_permutation"] <= 1


def test_part_v_words():
    res = {f"V1|DNg100-9|I400|s{s}": {"solver_success": True, "score": 0.95} for s in range(64)}
    for s in range(16):
        res[f"V2|DNb08-391|I250|s{s}"] = {"solver_success": True, "score": 0.7 if s < 8 else 0.1}
        res[f"V2|DNb08-328|I4|s{s}"] = {"solver_success": True, "score": 0.0}
    v = T.part_v(res)
    assert v["V1"]["words"] == "reproduces the authors' DNg100 result"
    assert v["V2"]["words"].startswith("reproduces the authors' reported result at current 250 (position 391)")
    for s in range(16):
        res[f"V2|DNb08-391|I250|s{s}"]["score"] = 0.2
    assert T.part_v(res)["V2"]["words"] == "does not reproduce it at any tested current"
    assert np.isfinite(T.part_v(res)["V1"]["mean"])
