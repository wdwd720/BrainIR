import json

import numpy as np
import pandas as pd
import pytest


def make_record(**over):
    rec = {"record_id": "r1", "pass_id": "pass1", "session": "s1", "doi": "10.1000/test", "source_locator": "Fig. 1a",
           "quote": "activation of the line evoked leg movements", "source_type": "systematic_screen", "access": "full_text",
           "name_in_paper": "DNx", "manc_type": "DNa01", "mapping_confidence": "high", "driver_lines": ["SS00001"],
           "effector": "CsChrimson", "effector_kind": "optogenetic", "stimulation": "red light 5 s", "sex": "male",
           "preparation": "intact_free", "expression": "bilateral", "line_specificity": "clean", "other_cell_types": [],
           "front_leg_rhythm": "yes", "middle_leg_rhythm": "yes", "hind_leg_rhythm": "yes", "behaviour_category": "forward_walking",
           "effect_on_walking": "not_assessed", "labeler_confidence": "high", "saw_simulation_score": False}
    rec.update(over)
    return rec


@pytest.fixture
def record():
    return make_record


@pytest.fixture
def synthetic_world(tmp_path):
    """Synthetic predictions + labels with a known primary AUROC, plus a valid UNBLIND flag in tmp."""
    rng = np.random.default_rng(11)
    types = [f"DNt{i:02d}" for i in range(40)]
    y = np.array([1] * 12 + [0] * 28)
    score = np.where(y == 1, rng.uniform(0.3, 1.0, 40), rng.uniform(0.0, 0.6, 40))
    research = tmp_path / "research"
    pred = research / "predictions"
    lab = research / "labels"
    (pred / "A1").mkdir(parents=True)
    (pred / "S").mkdir(parents=True)
    lab.mkdir(parents=True)
    a1 = pd.DataFrame({"arm": "A1", "network": "x", "manc_type": types, "n_members": 1, "member_ids": "1", "n_replicates": 16,
                       "n_usable": 16, "mean_score": score, "median_score": score, "frac_ge_0_5": 0.5, "best_score": score,
                       "median_freq_hz": 10.0, "median_current": 128.0, "median_n_active_readout": 3.0, "status": "ok",
                       "band": "x", "primary_score": score})
    a1.to_csv(pred / "A1" / "types.csv", index=False)
    base = pd.DataFrame({"manc_type": types, **{f"S{i}_{n}": rng.normal(size=40) for i, n in
                                                 [(1, "direct_mn"), (2, "twohop_signed"), (3, "twohop_abs"), (4, "total_out"),
                                                  (5, "out_partners"), (6, "premotor"), (7, "n_members"), (8, "informed")]}})
    base.to_csv(pred / "S" / "types.csv", index=False)
    tl = pd.DataFrame({"manc_type": types, "front": np.where(y == 1, "yes", "no"), "middle": "not_assessed", "hind": "not_assessed",
                       "stop_call": "not_assessed", "best_preparation": "intact_free", "best_specificity": "clean", "n_records": 1,
                       "has_systematic": True, "exposed": [i == 0 for i in range(40)], "confidence": "high", "freq_hz": None})
    tl.to_csv(lab / "type_labels.csv", index=False)
    import hashlib
    (research / "LOCK_predictions_v1.json").write_text("{}")
    (research / "LOCK_labels_v1.json").write_text("{}")
    sha = hashlib.sha256(b"{}").hexdigest()
    flag = {"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": "LOCK_labels_v1.json", "predictions_lock_sha256": sha,
            "labels_lock_sha256": sha, "authorised_by": "test", "utc": "2026-11-20T00:00:00Z"}
    keep = np.array([i != 0 for i in range(40)])  # type 0 is exposed
    from brainir_ledger.scoring.stats import auroc
    return {"research": research, "pred": pred, "labels": lab, "flag": flag, "expected_auroc": auroc(score[keep], y[keep])}


def write_flag(research, flag):
    (research / "UNBLIND.json").write_text(json.dumps(flag))
