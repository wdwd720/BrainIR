"""Exam 2 prediction rules (PREREG v3 M1-M4, P3) on hand-made read-outs with known answers. No simulation, no label."""

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp

from brainir_ledger import groups_h1 as GH


def _mm():
    rows = []
    for seg, part in (("T1", "front_leg"), ("T2", "middle_leg"), ("T3", "hind_leg")):
        for side in "LR":
            rows += [{"index": len(rows), "segment": seg, "side": side, "body_part": part, "action": "tibia_flexor",
                      "pools": f"any_body;{part};{part}_flexor"},
                     {"index": len(rows) + 1, "segment": seg, "side": side, "body_part": part, "action": "tibia_extensor",
                      "pools": f"any_body;{part};{part}_extensor"}]
    rows += [{"index": 12, "segment": "T2", "side": "L", "body_part": "wing", "action": "jump_TTM", "pools": "any_body;jump"},
             {"index": 13, "segment": "T2", "side": "L", "body_part": "wing", "action": "wing_power_DLM", "pools": "any_body;wing_any;wing_power"},
             {"index": 14, "segment": "T3", "side": "L", "body_part": "haltere", "action": "haltere_power", "pools": "any_body;haltere"},
             {"index": 15, "segment": "A1", "side": "L", "body_part": "abdomen", "action": "abdominal", "pools": "any_body;abdomen"},
             {"index": 16, "segment": "T1", "side": "L", "body_part": "neck", "action": "neck", "pools": ""}]
    return pd.DataFrame(rows)


def _ex(active, rhythm=None):
    rhythm = rhythm or {}
    return {"mn_peak": [1.0 if i in active else 0.0 for i in range(17)], "mn_active": sorted(active),
            "legs": {g: {"score": rhythm.get(g, 0.0)} for g in GH.LEGS}}


def test_pools():
    m = GH.pool_masks(_mm())
    assert m["any_body"].sum() == 16 and m["front_leg"].sum() == 4 and m["T1L_flexor"].sum() == 1 and m["wing_power"].sum() == 1
    assert not m["any_body"][16]  # neck feeds no pool


def test_held_flexion_and_rhythm():
    m = GH.pool_masks(_mm())
    # every leg's flexor active, no extensor, no rhythm: d5 = 1, d6 = 0
    act, rhy, d = GH.replicate_dims(_ex({0, 2, 4, 6, 8, 10}), m)
    assert d["d5"] == 1.0 and d["d6"] == 0.0 and d["d7p"] == 0.0 and d["d2"] == 0.5 and d["d1"] == 6 / 16
    # same, but T1L fully rhythmic: its held flexion vanishes; d7' = the most rhythmic leg
    act, rhy, d = GH.replicate_dims(_ex({0, 2, 4, 6, 8, 10}, {"T1L": 1.0, "T2R": 0.4}), m)
    assert d["d5"] == pytest.approx((0 + 1 + 1 + 0.6 + 1 + 1) / 6) and d["d7p"] == 1.0
    # extension on one leg only
    act, rhy, d = GH.replicate_dims(_ex({1}), m)
    assert d["d6"] == pytest.approx(1 / 6) and d["d5"] == 0.0
    act, rhy, d = GH.replicate_dims(_ex({12, 13, 14, 15}), m)
    assert (d["d10"], d["d11"], d["d13"], d["d14"], d["d15"]) == (1.0, 1.0, 1.0, 1.0, 1.0) and d["d2"] == 0.0


def test_readout_choice_and_outcomes():
    acc = {"key": "a", "seed": 0, "usable": True, "extras": _ex({0}), "final_verdict": "ok"}
    weak = {"key": "b", "seed": 1, "usable": False, "extras": {}, "final_run_extras": _ex({1}), "final_verdict": "weak"}
    strong = {"key": "c", "seed": 2, "usable": False, "extras": {}, "final_run_extras": _ex({2}), "final_verdict": "strong"}
    fixed = {"key": "d", "seed": 0, "verdict": "weak", "extras": _ex({3})}
    assert GH.replicate_readout(acc)[1] == "accepted" and GH.replicate_readout(weak) == (weak["final_run_extras"], "too_weak")
    assert GH.replicate_readout(strong)[1] == "saturating" and GH.replicate_readout(fixed)[1] == "fixed_weak"
    with pytest.raises(ValueError):
        GH.replicate_readout({"key": "e", "error": "x"})
    m = GH.pool_masks(_mm())
    pred, pools = GH.arm_tables({"U1": [acc, weak, strong], "U3": [fixed]}, ["U1", "U2", "U3"], m, {"U1": 5, "U2": 0, "U3": 2})
    r = pred.set_index("unit")
    assert r.loc["U1", "n_accepted"] == 1 and r.loc["U1", "n_too_weak"] == 1 and r.loc["U1", "n_saturating"] == 1
    assert r.loc["U1", "d2"] == pytest.approx((0.25 + 0.25 + 0.25) / 3) and r.loc["U2", "d1"] == 0.0 and r.loc["U2", "n_replicates"] == 0
    with pytest.raises(ValueError):
        GH.arm_tables({}, ["U1"], m, {"U1": 3})


def test_wiring_baselines():
    mm = _mm()
    m = GH.pool_masks(mm)
    n = 20  # neurons 0..16 are the motor neurons of the map; 17, 18, 19 interneurons
    W = sp.lil_matrix((n, n))
    W[0, 17] = 10.0   # 17 excites the T1L flexor
    W[1, 18] = -4.0   # 18 inhibits the T1L extensor
    W[17, 19] = 2.0   # 19 excites 17
    W = W.tocsr()
    mn = list(range(17))
    k1 = GH.hs_values(W, [17, 18], np.array(mn), m, 1, True)
    assert k1["d2"] == pytest.approx((10 - 4) / 4) and k1["d5"] == 0.0 and k1["d7p"] == 0.0
    k1u = GH.hs_values(W, [17, 18], np.array(mn), m, 1, False)
    assert k1u["d2"] == pytest.approx(14 / 4)
    k2 = GH.hs_values(W, [19], np.array(mn), m, 2, True)
    assert k2["d2"] == pytest.approx(20 / 4)
    k0 = GH.hs_values(W, [0, 1, 12], np.array(mn), m, 0, True)
    assert k0["d2"] == 0.5 and k0["d10"] == 1.0
    tabs = GH.hs_tables(W, {"A": [17], "B": [19]}, mn, m)
    assert sorted(tabs) == sorted(GH.HS_ARMS) and len(GH.HS_ARMS) == 7 and list(tabs["H-S-k0"]["unit"]) == ["A", "B"]


def test_members_variants():
    t = pd.DataFrame({"bodyId": [1, 2, 3, 4, 5], "hemilineage": ["01A", "01A", "01A", "01A", "02B"],
                      "somaNeuromere": ["T1", "T2", "A1", "T3", "T1"], "somaSide": ["LHS", "RHS", "LHS", "LHS", "LHS"]})
    bt = pd.Series({1: "primary", 2: "secondary", 4: "early_secondary"})
    assert GH.members(t, bt, "01A") == [0, 1, 3] and GH.members(t, bt, "01A", "all") == [0, 1, 2, 3]
    assert GH.members(t, bt, "01A", "post") == [1, 3] and GH.members(t, bt, "01A", "T2") == [1]
    assert GH.members(t, bt, "01A", "L") == [0, 3] and GH.members(t, bt, "01A", "R") == [1]


def test_arm_names_match_the_scoring_code():
    from brainir_ledger.scoring_h1 import pipeline_h1 as PL

    assert GH.HS_ARMS == PL.HS_ARMS
    assert [f"H-M-S-{v}" for v in GH.SENS_VARIANTS] == PL.SENS_ARMS
