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

import prereg6_planning as PL  # noqa: E402
import thirdfly_v1 as T  # noqa: E402


def _stand_in(m: pd.DataFrame, c: pd.DataFrame, seed: int = 0, shuffle: bool = False) -> pd.DataFrame:
    """A synthetic BANC-like replicate table over every BANC group and both animals' types (16 seeds): MaleCNS replicates where the
    type has them, else MANC's, with a fixed jitter (or type labels shuffled: no information). It only exercises the code."""
    rng = np.random.default_rng(seed)
    types = sorted(set(B.groups()) | set(m["type"]) | set(c["type"]))
    src = pd.concat([c, m[~m["type"].isin(set(c["type"]))]])
    d = src[src["type"].isin(types)].copy()
    miss = sorted(set(types) - set(d["type"]))
    if miss:
        d = pd.concat([d, pd.DataFrame([{"type": t, "seed": s, "usable": True, "score": 0.0} for t in miss for s in range(16)])])
    d["score"] = np.clip(d["score"] + rng.normal(0, 0.05, len(d)), 0, 1)
    if shuffle:
        ts = sorted(set(d["type"]))
        mp = dict(zip(ts, rng.permutation(ts)))
        d["type"] = d["type"].map(mp)
    return d.reset_index(drop=True)


def test_frozen_sets_match_recomputation_and_exclude_dng100():
    s = T.sets()
    fresh = PL.type_sets()
    for k, v in fresh.items():
        assert s[k] == v, k
    assert (len(s["three_animal"]), len(s["three_animal_noDNg100"])) == (182, 181)
    for k, v in s.items():
        if k.endswith("_noDNg100"):
            assert "DNg100" not in v, k
    assert "DNg100" not in s["C8"]["primary"] and len(s["C8"]["primary"]) == 12 and "DNb08" not in s["C8"]["without_DNb08"]


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


def test_tests_on_stand_ins():
    m, c = S6.b1r(), S6.b2r()
    stand_in = _stand_in(m, c)
    r3 = T.c3({"tuned": (m, c, stand_in, T.H16), "sweep": None}, "tuned")
    assert r3["first_line_words"] in ("confirmed in the third animal", "not confirmed", "inconclusive")
    assert set(r3["first_line_ratios"]) >= {"MANC-BANC", "MaleCNS-BANC"}
    assert T.c3({"tuned": None, "sweep": None}, "tuned")["first_line_words"] == "not judged"
    r4 = T.c4({"B1r": (m, T.H16, ("manc_banc_high_noDNg100", "manc_banc_high"))}, stand_in, T.H16)
    blk = r4["B1r"]["manc_banc_high_noDNg100"]
    assert "DNg100" not in blk["cuts"]["0.5"]["overlap"]["point"]["types_in_both"]
    assert blk["words_at_0.5"] in ("at chance at the authors' cut", "above chance", "not judged (an empty driver list)")
    assert r4["B1r"]["manc_banc_high"]["words_at_0.5"].endswith("(beside the words of record, not words)")
    r6 = T.c6(m, c, stand_in)
    assert r6["n_types"] == 181 and r6["words"] in ("pooling helps", "not shown")
    r7 = T.c7(m, c, stand_in, T.H16)
    assert r7["rbar"] > 0 and r7["n_star"] == pytest.approx(1.0 if r7["rbar"] >= 0.8 else 4 * (1 - r7["rbar"]) / r7["rbar"])
    T.N_PERM = 2000
    r8 = T.c8(stand_in)
    assert r8["primary"]["n"] == 12 and "DNg100" not in r8["primary"]["types"] and 0 < r8["primary"]["p_one_sided_permutation"] <= 1


def test_c6_null_and_c8_undefined():
    m, c = S6.b1r(), S6.b2r()
    shuffled = _stand_in(m, c, seed=3, shuffle=True)
    assert T.c6(m, c, shuffled)["words"] == "not shown"
    flat = _stand_in(m, c)
    flat["score"] = 0.0
    T.N_PERM = 500
    r8 = T.c8(flat)
    assert r8["primary"]["rho"] is None and r8["primary"]["words"].startswith("not shown")


def test_part_v_words():
    res = {f"V1|DNg100-9|I400|s{s}": {"solver_success": True, "score": 0.95} for s in range(64)}
    for s in range(16):
        res[f"V2|DNb08-391|I250|s{s}"] = {"solver_success": True, "score": 0.7 if s < 8 else 0.1}
        res[f"V2|DNb08-328|I4|s{s}"] = {"solver_success": True, "score": 0.0}
    v = T.part_v(res)
    assert v["V1"]["words"] == "reproduces the authors' DNg100 result"
    assert v["V2"]["words"].startswith("reproduces the authors' reported result at current 250 (position 391)")
    assert v["V2"]["authors_configuration_sentence"].startswith("at the authors' configuration (position 391, current 250) it reproduces")
    for s in range(16):
        res[f"V2|DNb08-391|I250|s{s}"]["score"] = 0.2
    v = T.part_v(res)
    assert v["V2"]["words"] == "does not reproduce it at any tested current" and "does not reproduce" in v["V2"]["authors_configuration_sentence"]


def test_missing_keys_count_as_unusable(tmp_path, monkeypatch):
    res = {"BT|DNx|s0": {"usable": True, "score": 0.7}}
    monkeypatch.setattr(S6, "_manifest_keys", lambda c: ["BT|DNx|s0", "BT|DNx|s1"])
    d = S6._tuned_rows(res, "BT", "bt-test")
    assert len(d) == 2 and not bool(d.loc[d["seed"] == 1, "usable"].iloc[0]) and S6.missing_report()["bt-test:BT"] == ["BT|DNx|s1"]
