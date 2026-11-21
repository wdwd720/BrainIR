"""The arm-table commands of `predict_h1.py` (PREREG v3 P1-P6, P10) on synthetic job results: every command writes one row per unit,
counts replicates and tuner outcomes, and refuses an incomplete arm. No simulation, no network, no label."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from brainir_ledger import groups_h1 as GH  # noqa: E402

UNITS = ["U1", "U2", "U3"]


def _mm():
    rows = []
    for seg, part in (("T1", "front_leg"), ("T2", "middle_leg"), ("T3", "hind_leg")):
        for side in "LR":
            rows += [{"index": len(rows), "segment": seg, "side": side, "body_part": part, "action": "tibia_flexor", "pools": f"any_body;{part}"},
                     {"index": len(rows) + 1, "segment": seg, "side": side, "body_part": part, "action": "tibia_extensor", "pools": f"any_body;{part}"}]
    rows += [{"index": 12, "segment": "T2", "side": "L", "body_part": "wing", "action": "wing_power_DLM", "pools": "any_body;wing_any;wing_power"}]
    return pd.DataFrame(rows)


def ex(active):
    return {"mn_peak": [1.0 if i in active else 0.0 for i in range(13)], "mn_active": sorted(active),
            "legs": {g: {"score": 0.0} for g in GH.LEGS}}


def group_result(key, seed, active, usable=True, verdict="ok"):
    r = {"key": key, "seed": seed, "usable": usable, "final_verdict": verdict, "extras": ex(active) if usable else {}}
    if not usable:
        r["final_run_extras"] = ex(active)
    return r


@pytest.fixture()
def PH(tmp_path, monkeypatch):
    import gha3
    import predict_h1 as PH

    monkeypatch.setattr(PH, "OUT", tmp_path / "predictions_h1")
    monkeypatch.setattr(gha3, "require_freeze", lambda what: None)
    masks = GH.pool_masks(_mm())
    monkeypatch.setattr(PH, "_masks", lambda c: (masks, {"mn_order_is_motor_map_order": True, "mn_order_sha256": "x"}))
    monkeypatch.setattr(PH.GH, "load_units", lambda: UNITS)
    monkeypatch.setattr(PH.N, "full_cord", lambda: SimpleNamespace(table=None, W=None, name="fake"))
    groups = {"primary": {"U1": [1, 2], "U2": [3], "U3": [4, 5, 6]}, "all": {"U1": [1, 2, 9], "U2": [3], "U3": [4, 5, 6]},
              "T1": {"U1": [1], "U2": [], "U3": [4]}}
    for v in ("post", "T2", "T3", "L", "R"):
        groups[v] = dict(groups["primary"])
    monkeypatch.setattr(PH.gha3, "_unit_groups", lambda fc, v: groups[v])
    plan = {v: {u: ("empty" if not groups[v][u] else "same_as_primary" if groups[v][u] == groups["primary"][u] else "run") for u in UNITS}
            for v in GH.SENS_VARIANTS}
    monkeypatch.setattr(PH.gha3, "sens_plan", lambda fc: plan)
    store = {}
    monkeypatch.setattr(PH, "_results", lambda c: (store[c], {"campaign": c}))
    return PH, store, plan


def test_hm_and_matched(PH):
    PH, store, _ = PH
    store["hm"] = {f"H-M|{u}|s{s}": group_result(f"H-M|{u}|s{s}", s, {0, 1} if u == "U1" else set(), usable=(s != 3 or u != "U2"),
                                                verdict="weak") for u in UNITS for s in range(16)}
    PH.cmd_hm(SimpleNamespace(campaign="hm"))
    t = pd.read_csv(PH.OUT / "H-M" / "predicted.csv").set_index("unit")
    m = pd.read_csv(PH.OUT / "H-M-s0-3" / "predicted.csv").set_index("unit")
    assert list(t.index) == UNITS and t.loc["U1", "d2"] == 0.5 and t.loc["U2", "n_too_weak"] == 1 and t.loc["U1", "n_replicates"] == 16
    assert m.loc["U1", "n_replicates"] == 4 and json.loads((PH.OUT / "H-M" / "provenance.json").read_text())["campaign"] == "hm"
    del store["hm"]["H-M|U3|s7"]
    with pytest.raises(SystemExit, match="expected 16"):
        PH.cmd_hm(SimpleNamespace(campaign="hm"))


def test_hd(PH):
    PH, store, _ = PH
    store["hd"] = {f"H-D-{c}|{u}|s{s}": {"key": f"H-D-{c}|{u}|s{s}", "seed": s, "verdict": "ok", "extras": ex({0} if c == 512 else set())}
                   for c in (128, 256, 384, 512) for u in UNITS for s in range(8)}
    PH.cmd_hd(SimpleNamespace(campaign="hd"))
    t = pd.read_csv(PH.OUT / "H-D-512" / "predicted.csv").set_index("unit")
    assert t.loc["U1", "d2"] == 0.25 and t.loc["U1", "n_fixed_ok"] == 8
    assert pd.read_csv(PH.OUT / "H-D-128" / "predicted.csv")["d2"].eq(0).all()


def test_hc(PH):
    PH, store, _ = PH
    store["hc"] = {f"H-C-rewire-101|{u}|s{s}": group_result(f"H-C-rewire-101|{u}|s{s}", s, {12}) for u in UNITS for s in range(4)}
    PH.cmd_hc(SimpleNamespace(campaign="hc"))
    t = pd.read_csv(PH.OUT / "H-C-rewire-101" / "predicted.csv").set_index("unit")
    assert t.loc["U2", "d11"] == 1.0 and t.loc["U2", "d13"] == 1.0
    store["hc"]["H-C-classshuffle-201|U1|s0"] = group_result("x", 0, set())
    with pytest.raises(SystemExit, match="one control network"):
        PH.cmd_hc(SimpleNamespace(campaign="hc"))


def test_hsens(PH):
    PH, store, plan = PH
    store["hm"] = {f"H-M|{u}|s{s}": group_result(f"H-M|{u}|s{s}", s, {0}) for u in UNITS for s in range(16)}
    store["hs"] = {}
    for v in GH.SENS_VARIANTS:
        for u in UNITS:
            if plan[v][u] == "run":
                store["hs"].update({f"H-M-S-{v}|{u}|s{s}": group_result(f"H-M-S-{v}|{u}|s{s}", s, {2, 3}) for s in range(4)})
    PH.cmd_hsens(SimpleNamespace(campaign="hs", primary="hm"))
    t1 = pd.read_csv(PH.OUT / "H-M-S-T1" / "predicted.csv").set_index("unit")
    assert t1.loc["U2", "source"] == "empty" and t1.loc["U2", "d1"] == 0.0 and t1.loc["U1", "source"] == "run" and t1.loc["U1", "d2"] == 0.5
    ta = pd.read_csv(PH.OUT / "H-M-S-all" / "predicted.csv").set_index("unit")
    assert ta.loc["U2", "source"] == "same_as_primary" and ta.loc["U2", "d2"] == 0.25 and ta.loc["U2", "n_replicates"] == 4
