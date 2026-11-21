"""Exam 2 scoring on synthetic data with known answers (PREREG v3 S2-S7). No real prediction or label is read."""

from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from brainir_ledger.scoring_h1 import (DIMS, BlindErrorH1, decide, derive_d7p, identification, observed, permutation_p,
                                       standardise)
from brainir_ledger.scoring_h1 import pipeline_h1 as PL


def _identity(n=12, sign=1.0):
    """n = 12: one-hot patterns; n = 24: the 12 one-hot patterns plus their complements. Either way the true match is the unique
    best candidate when predictions equal observations (worked out in LOG L71)."""
    units = [f"{i:02d}A" for i in range(n)]
    P = pd.DataFrame(0.0, index=units, columns=DIMS)
    O = pd.DataFrame(0.0, index=units, columns=DIMS)
    for i, u in enumerate(units):
        if i < 12:
            O.loc[u, DIMS[i]] = 1.0
        else:
            O.loc[u, :] = 1.0
            O.loc[u, DIMS[i - 12]] = 0.0
    P[:] = sign * O.to_numpy()
    return units, P, O


def test_perfect_identification_scores_one():
    units, P, O = _identity()
    r = identification(standardise(P), O)
    assert r["n"] == 12 and r["mean_pr"] == 1.0 and r["top1"] == 1.0 and r["top3"] == 1.0
    assert permutation_p(r, n_perm=2000) < 0.01


def test_reversed_identification_scores_zero():
    units, P, O = _identity(sign=-1.0)
    r = identification(standardise(P), O)
    assert r["mean_pr"] == 0.0 and r["top1"] == 0.0


def test_ties_count_half():
    units, P, O = _identity()
    r = identification(standardise(P * 0.0), O)
    assert r["mean_pr"] == 0.5
    assert all(v == 1 + 0.5 * 11 for v in r["pos"].values())


def test_random_predictions_are_near_chance():
    rng = np.random.default_rng(0)
    units = [f"{i:02d}A" for i in range(43)]
    P = pd.DataFrame(rng.normal(size=(43, len(DIMS))), index=units, columns=DIMS)
    O = pd.DataFrame(rng.integers(0, 2, size=(43, len(DIMS))).astype(float), index=units, columns=DIMS)
    r = identification(standardise(P), O)
    assert 0.35 < r["mean_pr"] < 0.65
    assert permutation_p(r, n_perm=2000) > 0.01


def test_min_coded_rule():
    units, P, O = _identity()
    O.loc[units[0], DIMS[3:]] = np.nan  # unit 0 keeps 3 coded dims
    O.loc[units[1], DIMS[2:]] = np.nan  # unit 1 keeps 2 coded dims -> excluded
    r = identification(standardise(P), O)
    assert units[0] in r["units"] and units[1] not in r["units"] and r["n"] == 11


def test_observed_and_d7p():
    c = pd.DataFrame({d: ["yes", "no", "unclear", "not_assessed", "conflicting"] for d in DIMS})
    O = observed(c)
    assert O[DIMS[0]].tolist()[:2] == [1.0, 0.0] and O[DIMS[0]].isna().sum() == 3
    assert derive_d7p({"d7": "no", "d8": "yes"}) == "yes"
    assert derive_d7p({"d7": "no", "d8": "no"}) == "no"
    assert derive_d7p({"d7": "unclear", "d8": "no"}) == "unclear"
    assert derive_d7p({"d7": "not_assessed", "d8": "no"}) == "not_assessed"


def test_decision_rules():
    ci_hi = {"lo": 0.6}
    assert decide({}, 0.01, ci_hi, 19, None)["underpowered"] is True
    d = decide({}, 0.01, ci_hi, 25, {"lo": 0.02})
    assert d == {"underpowered": False, "model_predicts": True, "adds_value_beyond_wiring": True, "hm_ranks_above_best_wiring_descriptive": True}
    assert decide({}, 0.2, ci_hi, 25, {"lo": -0.1})["model_predicts"] is False
    # the interval must clear the permutation-null mean too (audit 5)
    assert decide({}, 0.01, {"lo": 0.58}, 25, None, null_mean=0.6)["model_predicts"] is False
    # "beyond wiring" needs "predicts" (audit 4)
    d = decide({}, 0.40, {"lo": 0.31}, 25, {"lo": 0.02})
    assert d["adds_value_beyond_wiring"] is False and d["hm_ranks_above_best_wiring_descriptive"] is True


# ---------------------------------------------------------------------------------------------------- pipeline
def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _world(tmp_path):
    repo = tmp_path / "repo"
    research = repo / "research" / "ledger"
    units, P, O = _identity(24)
    (research / "hl_units").mkdir(parents=True)
    pd.DataFrame({"unit": units, "nt_class": ["excitatory"] * 12 + ["inhibitory"] * 12}).to_csv(research / "hl_units" / "UNITS_v1.csv", index=False)
    arms = {}
    hs_zero = [a for a in PL.HS_ARMS if a not in ("H-S-k2-signed",)]
    for arm, M in [("H-M", P), ("H-S-k2-signed", -P)] + [(a, P * 0.0) for a in hs_zero]:
        d = research / "predictions_h1" / arm
        d.mkdir(parents=True)
        M.rename_axis("unit").reset_index().to_csv(d / "predicted.csv", index=False)
        rel = f"research/ledger/predictions_h1/{arm}/predicted.csv"
        arms[arm] = {rel: _sha(repo / rel)}
    (research / "labels_h1").mkdir(parents=True)
    cons = O.replace({1.0: "yes", 0.0: "no"}).astype(object)
    for d in ("d7", "d8", "d9", "d12"):  # the consensus carries every V1 dimension (S7)
        cons[d] = "not_assessed"
    cons = cons.rename_axis("unit").reset_index()
    cons.to_csv(research / "labels_h1" / "consensus.csv", index=False)
    rel = "research/ledger/labels_h1/consensus.csv"
    (research / "LOCK_predictions_h1.json").write_text(json.dumps({"arms_locked": arms}))
    (research / "LOCK_predictions_h1b.json").write_text(json.dumps({"arms_locked": {}}))
    (research / "LOCK_labels_h1.json").write_text(json.dumps({"labels": {rel: _sha(repo / rel)}}))
    (research / "gates_v3").mkdir(parents=True)
    names = {"predictions": "LOCK_predictions_h1.json", "predictions_b": "LOCK_predictions_h1b.json", "labels": "LOCK_labels_h1.json"}
    (research / "gates_v3" / "UNBLINDING_GATE_h1_run2.json").write_text(json.dumps(
        {"all_conditions_hold": True, "conditions": {"1_locks": {"inputs_sha256": {f"research/ledger/{n}": _sha(research / n) for n in names.values()}}}}))
    flag = research / "UNBLIND_h1.json"
    f = {"authorised_by": "test", "utc": "t"}
    for k, n in names.items():
        f[f"{k}_lock"], f[f"{k}_lock_sha256"] = n, _sha(research / n)
    flag.write_text(json.dumps(f))
    return research, flag


def test_pipeline_refuses_without_flag(tmp_path):
    research, flag = _world(tmp_path)
    flag.unlink()
    with pytest.raises(BlindErrorH1):
        PL.run("primary", research, flag)


def test_pipeline_refuses_without_passing_gate(tmp_path):
    research, flag = _world(tmp_path)
    (research / "gates_v3" / "UNBLINDING_GATE_h1_run2.json").write_text(json.dumps({"all_conditions_hold": False}))
    with pytest.raises(BlindErrorH1):
        PL.run("primary", research, flag)


def test_pipeline_refuses_changed_lock(tmp_path):
    research, flag = _world(tmp_path)
    (research / "labels_h1" / "consensus.csv").write_text("unit\n")
    with pytest.raises(BlindErrorH1):
        PL.run("primary", research, flag)


def test_pipeline_primary_then_once(tmp_path):
    research, flag = _world(tmp_path)
    res = PL.run("primary", research, flag)
    assert res["H-M"]["mean_pr"] == 1.0 and res["n_units_ge3_coded"] == 24
    assert res["best_H-S"] == "H-S-k0"  # all-ties baselines (0.5) beat the reversed one (0.0); ties go to the first in HS_ARMS
    assert res["decision"]["model_predicts"] and res["decision"]["adds_value_beyond_wiring"]
    assert res["chance"]["null_mean_pr"]["mean"] < 0.6 and len(res["scoring_code_sha256"]) == 2
    with pytest.raises(BlindErrorH1):
        PL.run("primary", research, flag)
    sec = PL.run("secondary", research, flag)["secondary"]
    assert sec["by_class"]["excitatory"]["n"] == 12 and sec["H-D-128"] == {"status": "not_locked"}


def test_pipeline_refuses_unknown_unit_in_consensus(tmp_path):
    research, flag = _world(tmp_path)
    p = research / "labels_h1" / "consensus.csv"
    c = pd.read_csv(p, dtype={"unit": str})
    c.loc[0, "unit"] = "9A"  # not the unit list's spelling
    _relock_labels(research, flag, c)
    with pytest.raises(BlindErrorH1, match="not in the unit list"):
        PL.run("primary", research, flag)


def test_pipeline_refuses_consensus_without_d7p(tmp_path):
    research, flag = _world(tmp_path)
    c = pd.read_csv(research / "labels_h1" / "consensus.csv", dtype={"unit": str}).drop(columns=["d7p"])
    _relock_labels(research, flag, c)
    with pytest.raises(BlindErrorH1, match="columns missing"):
        PL.run("primary", research, flag)


def test_pipeline_refuses_missing_wiring_arm(tmp_path):
    research, flag = _world(tmp_path)
    lock = json.loads((research / "LOCK_predictions_h1.json").read_text())
    del lock["arms_locked"]["H-S-lin"]
    _relock_predictions(research, flag, lock)
    with pytest.raises(BlindErrorH1, match="H-S-lin is not locked"):
        PL.run("primary", research, flag)


def test_pipeline_refuses_gate_report_of_other_locks(tmp_path):
    research, flag = _world(tmp_path)
    g = research / "gates_v3" / "UNBLINDING_GATE_h1_run2.json"
    rep = json.loads(g.read_text())
    rep["conditions"]["1_locks"]["inputs_sha256"]["research/ledger/LOCK_labels_h1.json"] = "0" * 64
    g.write_text(json.dumps(rep))
    with pytest.raises(BlindErrorH1, match="gate report checked another"):
        PL.run("primary", research, flag)


def _relock_predictions(research, flag, lock):
    (research / "LOCK_predictions_h1.json").write_text(json.dumps(lock))
    f = json.loads(flag.read_text())
    f["predictions_lock_sha256"] = _sha(research / "LOCK_predictions_h1.json")
    flag.write_text(json.dumps(f))
    g = research / "gates_v3" / "UNBLINDING_GATE_h1_run2.json"
    rep = json.loads(g.read_text())
    rep["conditions"]["1_locks"]["inputs_sha256"]["research/ledger/LOCK_predictions_h1.json"] = f["predictions_lock_sha256"]
    g.write_text(json.dumps(rep))


def test_pipeline_refuses_prediction_table_missing_a_unit(tmp_path):
    research, flag = _world(tmp_path)
    repo = research.parents[1]
    d = research / "predictions_h1" / "H-M" / "predicted.csv"
    pd.read_csv(d, dtype={"unit": str}).iloc[1:].to_csv(d, index=False)
    lock = json.loads((research / "LOCK_predictions_h1.json").read_text())
    lock["arms_locked"]["H-M"] = {"research/ledger/predictions_h1/H-M/predicted.csv": _sha(d)}
    _relock_predictions(research, flag, lock)
    assert repo.exists()
    with pytest.raises(BlindErrorH1, match="exactly"):
        PL.run("primary", research, flag)


def _relock_labels(research, flag, c):
    p = research / "labels_h1" / "consensus.csv"
    c.to_csv(p, index=False)
    (research / "LOCK_labels_h1.json").write_text(json.dumps({"labels": {"research/ledger/labels_h1/consensus.csv": _sha(p)}}))
    f = json.loads(flag.read_text())
    f["labels_lock_sha256"] = _sha(research / "LOCK_labels_h1.json")
    flag.write_text(json.dumps(f))
    g = research / "gates_v3" / "UNBLINDING_GATE_h1_run2.json"
    rep = json.loads(g.read_text())
    rep["conditions"]["1_locks"]["inputs_sha256"]["research/ledger/LOCK_labels_h1.json"] = f["labels_lock_sha256"]
    g.write_text(json.dumps(rep))
