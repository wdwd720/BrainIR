import hashlib
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


def _sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _types_frame(arm, types, score):
    return pd.DataFrame({"arm": arm, "network": "x", "manc_type": types, "n_members": 1, "member_ids": "1", "n_replicates": 16,
                         "n_usable": 16, "mean_score": score, "median_score": score, "frac_ge_0_5": 0.5, "best_score": score,
                         "median_freq_hz": 10.0, "median_current": 128.0, "median_n_active_readout": 3.0, "status": "ok",
                         "band": ["driver" if s >= 0.5 else ("non_driver" if s < 0.05 else "indeterminate") for s in score],
                         "primary_score": score})


@pytest.fixture
def synthetic_world(tmp_path):
    """Synthetic predictions (every locked arm kind) + labels with a known primary AUROC, locks and a valid UNBLIND flag."""
    from brainir_ledger.labels.aggregate import type_labels
    from brainir_ledger.scoring.stats import auroc

    rng = np.random.default_rng(11)
    types = [f"DNt{i:02d}" for i in range(40)]
    y = np.array([1] * 12 + [0] * 28)
    score = np.where(y == 1, rng.uniform(0.3, 1.0, 40), rng.uniform(0.0, 0.6, 40))
    research = tmp_path / "research"
    pred = research / "predictions"
    lab = research / "labels"
    lab.mkdir(parents=True)
    arms = {}
    for arm, sc in (("A1", score), ("B1", np.clip(score + rng.normal(0, 0.1, 40), 0, 1)), ("B1-alt", score), ("A1-lo10", score),
                    ("B2", score[::-1].copy()), ("B1-ctl-rewire-101", rng.uniform(0, 1, 40))):
        df = _types_frame(arm, types, sc)
        (pred / arm).mkdir(parents=True)
        df.to_csv(pred / arm / "types.csv", index=False)
        arms[arm] = pred / arm / "types.csv"
    for arm in ("A0", "B0"):
        df = _types_frame(arm, types, score)
        df["type_max"], df["type_mean"] = score, score / 2
        (pred / arm).mkdir(parents=True)
        df.to_csv(pred / arm / "types.csv", index=False)
        arms[arm] = pred / arm / "types.csv"
    base = pd.DataFrame({"manc_type": types, **{f"S{i}_{n}": rng.normal(size=40) for i, n in
                                                 [(1, "direct_mn"), (2, "twohop_signed"), (3, "twohop_abs"), (4, "total_out"),
                                                  (5, "out_partners"), (6, "premotor"), (7, "n_members"), (8, "informed")]}})
    base["primary_score"] = base["S1_direct_mn"]
    (pred / "S").mkdir(parents=True)
    base.to_csv(pred / "S" / "types.csv", index=False)
    arms["S"] = pred / "S" / "types.csv"
    b4 = _types_frame("B4", types, score)
    b4["call_128"] = ["halts" if i % 3 == 0 else "no_effect" for i in range(40)]
    (pred / "B4").mkdir(parents=True)
    b4.to_csv(pred / "B4" / "types.csv", index=False)
    arms["B4"] = pred / "B4" / "types.csv"
    b5 = _types_frame("B5", types, score)
    for c in (32, 128, 512):
        b5[f"score_I{c}"] = score * c / 512
    (pred / "B5").mkdir(parents=True)
    b5.to_csv(pred / "B5" / "types.csv", index=False)
    arms["B5"] = pred / "B5" / "types.csv"
    recs = [make_record(record_id=f"r{i}", exp_id=f"pass1-atlas:r{i}", manc_type=t, quote_verified=True,
                        front_leg_rhythm="yes" if yi else "no", effect_on_walking="stops" if i % 5 == 0 else "none",
                        frequency_hz=8.0 + i if yi else None, preparation="headless" if i % 2 else "intact_free",
                        headless_surface="ball" if i % 2 else None)
            for i, (t, yi) in enumerate(zip(types, y))]
    with open(lab / "records.jsonl", "w") as fh:
        for r in recs:
            fh.write(json.dumps(r) + "\n")
    tl = type_labels(recs, exposed={types[0]}, type_list=types)
    tl.to_csv(lab / "type_labels.csv", index=False)
    plock = {"arms_locked": {a: {f"research/ledger/predictions/{a}/types.csv": _sha(p)} for a, p in arms.items()}}
    llock = {"labels": {f"research/ledger/labels/{n}": _sha(lab / n) for n in ("records.jsonl", "type_labels.csv")}}
    (research / "LOCK_predictions_v1.json").write_text(json.dumps(plock))
    (research / "LOCK_labels_v1.json").write_text(json.dumps(llock))
    flag = {"predictions_lock": "LOCK_predictions_v1.json", "labels_lock": "LOCK_labels_v1.json",
            "predictions_lock_sha256": _sha(research / "LOCK_predictions_v1.json"), "labels_lock_sha256": _sha(research / "LOCK_labels_v1.json"),
            "authorised_by": "test", "utc": "2026-11-20T00:00:00Z"}
    keep = np.array([i != 0 for i in range(40)])  # type 0 is exposed
    return {"research": research, "pred": pred, "labels": lab, "flag": flag, "expected_auroc": auroc(score[keep], y[keep]), "types": types}


def write_flag(research, flag):
    (research / "UNBLIND.json").write_text(json.dumps(flag))
