import json

import pytest

from brainir_ledger import UNBLIND_FLAG
from brainir_ledger.scoring import BlindError, require_unblind
from brainir_ledger.scoring.pipeline import run_scoring, score_tables

from .conftest import write_flag


def test_real_flag_does_not_exist():
    """Run 1 never creates the unblinding flag."""
    assert not UNBLIND_FLAG.exists()


def test_scoring_refuses_without_flag(tmp_path):
    with pytest.raises(BlindError):
        require_unblind(tmp_path / "UNBLIND.json", tmp_path)


def test_scoring_refuses_on_the_real_tree(tmp_path):
    with pytest.raises(BlindError):
        run_scoring(tmp_path / "out")  # default paths: the real research/ledger, where no flag exists


def test_scoring_refuses_incomplete_or_wrong_flag(synthetic_world):
    w = synthetic_world
    bad = dict(w["flag"])
    del bad["authorised_by"]
    write_flag(w["research"], bad)
    with pytest.raises(BlindError):
        run_scoring(w["research"] / "out", w["pred"], w["labels"], w["research"])
    bad = dict(w["flag"], labels_lock_sha256="0" * 64)
    write_flag(w["research"], bad)
    with pytest.raises(BlindError):
        run_scoring(w["research"] / "out", w["pred"], w["labels"], w["research"])


def test_scoring_runs_with_valid_flag(synthetic_world):
    w = synthetic_world
    write_flag(w["research"], w["flag"])
    res = run_scoring(w["research"] / "out", w["pred"], w["labels"], w["research"])
    assert res["primary"]["auroc"] == pytest.approx(w["expected_auroc"])
    assert res["primary"]["n"] == 39  # the exposed type is excluded
    out = json.loads((w["research"] / "out" / "score.json").read_text())
    assert out["primary"]["decision"]["underpowered"] is False


def test_score_tables_primary_matches_expected(synthetic_world):
    w = synthetic_world
    res = score_tables(w["pred"], w["labels"], n_boot=500, n_perm=500)
    p = res["primary"]
    assert p["auroc"] == pytest.approx(w["expected_auroc"])
    assert p["boot"]["lo"] <= p["auroc"] <= p["boot"]["hi"]
    assert p["best_baseline"] in p["baselines_auroc"]
    assert "S8_informed" not in p["baselines_auroc"]
    assert res["analyses"]["exposed_included"]["n"] == 40
