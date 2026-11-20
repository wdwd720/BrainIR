import json

import pandas as pd
import pytest

from brainir_ledger import UNBLIND_FLAG
from brainir_ledger.scoring import BlindError, require_unblind
from brainir_ledger.scoring.pipeline import PREREGISTERED_SECONDARY, run_scoring, score_tables

from .conftest import write_flag


def test_real_flag_does_not_exist():
    """Run 1 never creates the unblinding flag."""
    assert not UNBLIND_FLAG.exists()


def test_scoring_refuses_without_flag(tmp_path, synthetic_world):
    w = synthetic_world
    with pytest.raises(BlindError):
        require_unblind(tmp_path / "UNBLIND.json", tmp_path)
    with pytest.raises(BlindError):
        score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)


def test_scoring_refuses_on_the_real_tree(tmp_path):
    with pytest.raises(BlindError):
        run_scoring(tmp_path / "out")  # default paths: the real research/ledger, where no flag exists


def test_scoring_refuses_incomplete_or_wrong_flag(synthetic_world):
    w = synthetic_world
    for bad in ({k: v for k, v in w["flag"].items() if k != "authorised_by"}, dict(w["flag"], labels_lock_sha256="0" * 64),
                dict(w["flag"], predictions_lock="../LOCK_predictions_v1.json"), dict(w["flag"], labels_lock="/tmp/LOCK_labels_v1.json")):
        write_flag(w["research"], bad)
        with pytest.raises(BlindError):
            score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)


def test_scoring_refuses_changed_inputs(synthetic_world):
    w = synthetic_world
    write_flag(w["research"], w["flag"])
    p = w["pred"] / "A1" / "types.csv"
    df = pd.read_csv(p)
    df.loc[0, "primary_score"] = 0.99
    df.to_csv(p, index=False)
    with pytest.raises(BlindError):
        score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)


def test_scoring_refuses_type_labels_that_do_not_match_records(synthetic_world):
    w = synthetic_world
    tl = pd.read_csv(w["labels"] / "type_labels.csv")
    tl.loc[5, "front"] = "yes" if tl.loc[5, "front"] == "no" else "no"
    tl.to_csv(w["labels"] / "type_labels.csv", index=False)
    import hashlib
    llock = json.loads((w["research"] / "LOCK_labels_v1.json").read_text())
    for k in llock["labels"]:
        if k.endswith("type_labels.csv"):
            llock["labels"][k] = hashlib.sha256((w["labels"] / "type_labels.csv").read_bytes()).hexdigest()
    (w["research"] / "LOCK_labels_v1.json").write_text(json.dumps(llock))
    flag = dict(w["flag"], labels_lock_sha256=hashlib.sha256((w["research"] / "LOCK_labels_v1.json").read_bytes()).hexdigest())
    write_flag(w["research"], flag)
    with pytest.raises(BlindError):
        score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)


def test_end_to_end_every_preregistered_analysis_has_a_status(synthetic_world):
    w = synthetic_world
    write_flag(w["research"], w["flag"])
    out = w["research"] / "out"
    res = score_tables(w["pred"], w["labels"], w["research"], out, n_boot=300, n_perm=300)
    p = res["primary"]
    assert p["auroc"] == pytest.approx(w["expected_auroc"])
    assert p["n"] == 39                                   # the exposed type is excluded
    assert p["boot"]["lo"] <= p["auroc"] <= p["boot"]["hi"]
    assert p["best_baseline"] in p["baselines_auroc"] and "S8_informed" not in p["baselines_auroc"]
    assert (out / "score_primary.json").exists() and (out / "score.json").exists()
    A = res["analyses"]
    assert "analyses_missing_from_code" not in res
    assert set(PREREGISTERED_SECONDARY) <= set(A)
    for k in PREREGISTERED_SECONDARY:
        assert A[k]["status"] in ("ok", "not_locked", "input_missing"), (k, A[k])
    assert A["B3_pairs"]["status"] == "not_locked" and A["B6_legs_that_move"]["status"] == "not_locked"
    assert A["exposed_included"]["result"]["n"] == 40 and A["exposed_only"]["result"]["n"] == 1
    assert A["B1"]["status"] == "ok" and A["controls"]["status"] == "ok"
    assert A["B2_vs_B1_bands"]["result"]["n_matched_types"] == 40
    assert A["frequency"]["result"]["n"] >= 3
    assert A["B4_stop"]["result"]["n"] > 0 and A["B5_per_strength"]["status"] == "ok"
    assert A["headless_only"]["status"] == "ok" and A["headless_only"]["result"]["n"] > 0


def test_one_failing_analysis_does_not_stop_the_others(synthetic_world):
    w = synthetic_world
    write_flag(w["research"], w["flag"])
    # an arm present on disk but not in the predictions lock is reported as not_locked, not read
    (w["pred"] / "B3").mkdir()
    (w["pred"] / "B3" / "types.csv").write_text("garbage")
    res = score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)
    assert res["analyses"]["B3_pairs"]["status"] == "not_locked"
    assert res["primary"]["auroc"] is not None


def _relock_predictions(w):
    import hashlib
    plock = json.loads((w["research"] / "LOCK_predictions_v1.json").read_text())
    for arm, files in plock["arms_locked"].items():
        for k in files:
            files[k] = hashlib.sha256((w["pred"] / arm / "types.csv").read_bytes()).hexdigest()
    (w["research"] / "LOCK_predictions_v1.json").write_text(json.dumps(plock))
    flag = dict(w["flag"], predictions_lock_sha256=hashlib.sha256((w["research"] / "LOCK_predictions_v1.json").read_bytes()).hexdigest())
    write_flag(w["research"], flag)


def test_missing_column_is_an_error_not_not_locked(synthetic_world):
    w = synthetic_world
    p = w["pred"] / "B4" / "types.csv"
    pd.read_csv(p).drop(columns=["call_128"]).to_csv(p, index=False)
    _relock_predictions(w)
    res = score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)
    assert res["analyses"]["B4_stop"]["status"] == "error"


def test_baseline_failure_keeps_the_primary_auroc(synthetic_world):
    w = synthetic_world
    p = w["pred"] / "S" / "types.csv"
    df = pd.read_csv(p)
    df.loc[3, "S2_twohop_signed"] = float("nan")
    df.to_csv(p, index=False)
    _relock_predictions(w)
    res = score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)
    prim = res["primary"]
    assert prim["auroc"] == pytest.approx(w["expected_auroc"])
    assert prim["baseline_comparison_status"].startswith("error")
    assert prim["decision"]["adds_value_beyond_wiring"] is False


def test_b4_non_calls_are_excluded(synthetic_world):
    w = synthetic_world
    p = w["pred"] / "B4" / "types.csv"
    df = pd.read_csv(p)
    df["call_128"] = "background_not_rhythmic"
    df.to_csv(p, index=False)
    _relock_predictions(w)
    res = score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)
    st = res["analyses"]["B4_stop"]["result"]
    assert st["n"] == 0 and st["n_excluded_non_calls"] > 0


def test_type_labels_must_match_the_kit_exposed_list(synthetic_world):
    w = synthetic_world
    kit = w["research"] / "kit"
    kit.mkdir()
    pd.DataFrame({"name_as_given": ["X"], "manc_types": [w["types"][1]], "resolved": [True]}).to_csv(kit / "exposed_types.csv", index=False)
    write_flag(w["research"], w["flag"])
    with pytest.raises(BlindError):
        score_tables(w["pred"], w["labels"], w["research"], w["research"] / "out", n_boot=100, n_perm=100)
