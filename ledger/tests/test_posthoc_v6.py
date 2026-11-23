"""PREREG v6 X4: the run 6 analysis code reproduces the first two animals' locked numbers before any BANC result is read."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

from brainir_ledger import RESEARCH, data_dir  # noqa: E402
from brainir_ledger import agree as AG  # noqa: E402
from brainir_ledger import overlap6 as O6  # noqa: E402
from brainir_ledger import screens6 as S6  # noqa: E402

if not (RESEARCH / "predictions_v2" / "B1r" / "replicates.parquet").exists():
    pytest.skip("locked screens not available", allow_module_level=True)

import posthoc_v6 as PH  # noqa: E402


def test_overlap_reproduces_run5():
    R = json.loads((RESEARCH / "replication_v1" / "R_replication.json").read_text())
    sets = PH.type_sets()
    assert (len(sets["high"]), len(sets["all"])) == (215, 310)
    for s in ("high", "all"):
        ts = sets[s]
        sx, sx1, sx2 = PH.vectors(S6.b1r(), ts, PH.H16)
        sy, sy1, sy2 = PH.vectors(S6.b2r(), ts, PH.H16)
        o = O6.overlap(sx, sy, sx1, sx2, sy1, sy2, 0.5, n_boot=200)["point"]
        r = R["B1r_x_B2r"][s]["overlap"]
        assert (o["n_x"], o["n_y"], o["k"]) == (r["n_drivers_x"], r["n_drivers_B2r"], r["n_both"])
        assert o["OC_ratio"] == pytest.approx(r["point"]["OC_ratio"], abs=1e-12)
        assert o["chance_expectation"] == pytest.approx(r["expected_both_if_independent"], abs=1e-12)


def test_agreement_reproduces_run4_reference():
    A = json.loads((RESEARCH / "reliability_v2" / "A.json").read_text())
    ts = PH.type_sets()["all"]
    c = AG.compare(S6.b1r(), S6.b2r(), ts, PH.H16, n_boot=200)
    assert c["primary"]["ratio"] == pytest.approx(A["reference_R1_whole_type_cross_fly"]["primary"]["ratio"], abs=5e-4)


def test_tuned_loader_rebuilds_b2r():
    p = data_dir() / "arms" / "GHA_b2r" / "results.pkl"
    if not p.exists():
        pytest.skip("B2r results not on this machine")
    got = S6._tuned_rows(S6.results("arms", "b2r"), "B2r")
    ref = S6.b2r().sort_values(["type", "seed"]).reset_index(drop=True)
    assert len(got) == len(ref)
    assert (got["type"].to_numpy() == ref["type"].to_numpy()).all() and (got["seed"].to_numpy() == ref["seed"].to_numpy()).all()
    assert (got["usable"].to_numpy() == ref["usable"].to_numpy()).all()
    u = ref["usable"].to_numpy()
    assert np.allclose(got["score"].to_numpy()[u], ref["score"].to_numpy()[u])


def test_auroc_ties_and_bounds():
    s = np.array([0.1, 0.2, 0.2, 0.9])
    pos = np.array([False, True, False, True])
    assert O6.auroc(s, pos)[0] == pytest.approx((1 + 0.5 + 1 + 1) / 4)
    assert np.isnan(O6.auroc(s, np.zeros(4, bool))[0])
    assert O6.clopper_pearson(0, 10)[0] == 0.0 and O6.clopper_pearson(10, 10)[1] == 1.0


def test_sweep_score_rule():
    res = {"DX-1|T|s0": {"runs": [{"in_bounds": False, "score": 0.9}, {"in_bounds": True, "score": 0.4}, {"in_bounds": True, "score": 0.6}]},
           "DX-1|U|s0": {"runs": [{"in_bounds": False, "score": 0.9}]}}
    d = S6._sweep_rows(res, "DX-1").set_index("type")["score"]
    assert d["T"] == 0.6 and d["U"] == 0.0
    assert isinstance(pd.Series([1]), pd.Series)
