"""Exam 2 end to end on synthetic data (PREREG v3 P10, T9, S2-S7): job-like results -> the real table writer (`predict_h1._write`
over `groups_h1.arm_tables`) -> the real lock writers (`lock3`, in a temporary git repository) -> the real scoring pipeline. Checks
that the file formats and lock sections that the writers produce are the ones the scorer reads. No real prediction or label."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from brainir_ledger import groups_h1 as GH
from brainir_ledger.scoring_h1 import DIMS
from brainir_ledger.scoring_h1 import pipeline_h1 as PL

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _mm(n_mn=17):
    rows = []
    for seg, part in (("T1", "front_leg"), ("T2", "middle_leg"), ("T3", "hind_leg")):
        for side in "LR":
            rows += [{"index": len(rows), "segment": seg, "side": side, "body_part": part, "action": "tibia_flexor",
                      "pools": f"any_body;{part}"},
                     {"index": len(rows) + 1, "segment": seg, "side": side, "body_part": part, "action": "tibia_extensor",
                      "pools": f"any_body;{part}"}]
    rows += [{"index": 12, "segment": "T2", "side": "L", "body_part": "wing", "action": "jump_TTM", "pools": "any_body;jump"},
             {"index": 13, "segment": "T2", "side": "L", "body_part": "wing", "action": "wing_power_DLM", "pools": "any_body;wing_any;wing_power"},
             {"index": 14, "segment": "T3", "side": "L", "body_part": "haltere", "action": "haltere_power", "pools": "any_body;haltere"},
             {"index": 15, "segment": "A1", "side": "L", "body_part": "abdomen", "action": "abdominal", "pools": "any_body;abdomen"},
             {"index": 16, "segment": "T1", "side": "L", "body_part": "neck", "action": "neck", "pools": ""}]
    return pd.DataFrame(rows)


def _result(unit_i: int, seed: int, rng) -> dict:
    """A job-like result whose active motor neurons depend on the unit (so units are distinguishable) plus seed noise."""
    base = {(unit_i * 7 + j) % 16 for j in range(1 + unit_i % 5)}
    noise = {int(x) for x in rng.integers(0, 16, 1)} if seed % 2 else set()
    act = sorted(base | noise)
    ex = {"mn_peak": [1.0 if i in act else 0.0 for i in range(17)], "mn_active": act,
          "legs": {g: {"score": float((unit_i + k) % 3) / 2} for k, g in enumerate(GH.LEGS)}}
    usable = unit_i % 4 != 0
    r = {"key": f"H-M|U{unit_i:02d}|s{seed}", "seed": seed, "usable": usable, "final_verdict": "ok" if usable else "weak",
         "extras": ex if usable else {}}
    if not usable:
        r["final_run_extras"] = ex
    return r


def _git(repo, *a):
    subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def world(tmp_path, monkeypatch):
    import lock2 as L2
    import lock3 as L3
    import predict_h1 as PH

    repo = tmp_path / "repo"
    res = repo / "research" / "ledger"
    res.mkdir(parents=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    for n in L2.V1_LOCKS:  # base() hashes the v1 locks
        (res / n).write_text("{}\n")
    monkeypatch.setattr(L2, "REPO", repo)
    monkeypatch.setattr(L2, "RES", res)
    monkeypatch.setattr(L3, "RES", res)
    monkeypatch.setattr(L3, "REPO", repo)
    monkeypatch.setattr(L3, "H1_MANIFESTS", tmp_path / "no_sessions")
    units = [f"U{i:02d}" for i in range(43)]
    pd.DataFrame({"unit": units, "nt_class": ["excitatory"] * 20 + ["inhibitory"] * 20 + ["motor"] * 3}).to_csv(
        res / "UNITS_tmp.csv", index=False)
    (res / "hl_units").mkdir()
    pd.read_csv(res / "UNITS_tmp.csv").to_csv(res / "hl_units" / "UNITS_v1.csv", index=False)
    (res / "UNITS_tmp.csv").unlink()
    masks = GH.pool_masks(_mm())
    rng = np.random.default_rng(0)
    results = {u: [_result(i, s, rng) for s in range(4)] for i, u in enumerate(units)}
    pred, pools = GH.arm_tables(results, units, masks, {u: 10 for u in units})
    out = res / "predictions_h1"
    PH._write("H-M", pred, pools, {"campaign": "synthetic"}, out=out)
    PH._write("H-M-s0-3", pred, pools, {"campaign": "synthetic"}, out=out)
    hs = pred.copy()
    hs[DIMS] = hs[DIMS].to_numpy()[::-1]  # an unrelated baseline: another unit's pattern
    for arm in PL.HS_ARMS:
        PH._write(arm, hs, None, {"what": "synthetic"}, out=out)
    # labels: the predicted pattern of each unit, thresholded at its column median (so H-M identifies well), as consensus cells
    P = pred.set_index("unit")[DIMS]
    cons = (P > P.median()).replace({True: "yes", False: "no"}).astype(object)
    cons.iloc[::5, :6] = "not_assessed"
    for d in [f"d{i}" for i in range(1, 16) if f"d{i}" not in DIMS]:
        cons[d] = "not_assessed"
    (res / "labels_h1").mkdir()
    cons.rename_axis("unit").reset_index().to_csv(res / "labels_h1" / "consensus.csv", index=False)
    pd.DataFrame({"record_id": ["r1"]}).to_csv(res / "labels_h1" / "records.csv", index=False)
    for n in ("pairs.csv", "agreement.json", "verification.json", "transcript_audit.json"):
        (res / "labels_h1" / n).write_text("{}\n" if n.endswith(".json") else "a\n")
    (res / "reviews_v3").mkdir()
    (res / "reviews_v3" / "LABEL_REVIEW_h1.md").write_text("Verdict: usable\n")
    (res / "LOCK_prereg_v3.json").write_text("{}\n")
    (res / "LOCK_labelcode_h1.json").write_text("{}\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "synthetic")
    return repo, res, L3


def test_writers_locks_and_scorer_agree(world):
    repo, res, L3 = world
    with pytest.raises(SystemExit, match="no predicted.csv"):  # every primary arm is required (audit 3)
        (res / "predictions_h1" / "H-S-lin" / "predicted.csv").rename(res / "x.csv")
        try:
            L3.lock_predictions("synthetic")
        finally:
            (res / "x.csv").rename(res / "predictions_h1" / "H-S-lin" / "predicted.csv")
    L3.lock_predictions("synthetic")
    with pytest.raises(SystemExit, match="neither locked nor explained"):
        L3.lock_predictions_b([], {"H-D-128": "x"}, "synthetic")
    L3.lock_predictions_b([], {a: "not run (synthetic)" for a in L3.SECONDARY_ARMS}, "synthetic")
    L3.lock_labels()
    names = {"predictions": "LOCK_predictions_h1.json", "predictions_b": "LOCK_predictions_h1b.json", "labels": "LOCK_labels_h1.json"}
    lock = json.loads((res / names["predictions"]).read_text())
    assert "research/ledger/predictions_h1/H-M/predicted.csv" in lock["arms_locked"]["H-M"] and len(lock["arms_locked"]) == 10
    (res / "gates_v3").mkdir(exist_ok=True)
    (res / "gates_v3" / "UNBLINDING_GATE_h1_run2.json").write_text(json.dumps(
        {"all_conditions_hold": True, "conditions": {"1_locks": {"inputs_sha256": {f"research/ledger/{n}": _sha(res / n) for n in names.values()}}}}))
    flag = res / "UNBLIND_h1.json"
    f = {"authorised_by": "test", "utc": "t"}
    for k, n in names.items():
        f[f"{k}_lock"], f[f"{k}_lock_sha256"] = n, _sha(res / n)
    flag.write_text(json.dumps(f))
    r = PL.run("primary", res, flag)
    assert r["n_units_ge3_coded"] == 43 and r["H-M"]["n"] == 43
    assert r["H-M"]["mean_pr"] > 0.8 and r["p"] < 0.01 and r["best_H-S"] in PL.HS_ARMS
    assert r["decision"]["model_predicts"] is True
    s = PL.run("secondary", res, flag)["secondary"]
    assert s["H-D-128"] == {"status": "not_locked"} and s["by_class"]["motor"]["n"] == 3 and s["H-M-s0-3"]["n"] == 43
    assert (res / "results" / "run3" / "primary.json").exists()


def test_lock_refuses_untracked_and_second_write(world):
    repo, res, L3 = world
    (res / "predictions_h1" / "H-M" / "extra.csv").write_text("x\n")  # untracked file in a locked arm folder
    with pytest.raises(SystemExit, match="not tracked"):
        L3.lock_predictions("synthetic")
    (res / "predictions_h1" / "H-M" / "extra.csv").unlink()
    L3.lock_predictions("synthetic")
    with pytest.raises(SystemExit, match="written once"):
        L3.lock_predictions("synthetic")
