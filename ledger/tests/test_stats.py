import numpy as np
import pytest

from brainir_ledger.scoring import stats as ST


def test_auroc_known_values():
    assert ST.auroc([0.9, 0.8, 0.1, 0.2], [1, 1, 0, 0]) == 1.0
    assert ST.auroc([0.1, 0.2, 0.9, 0.8], [1, 1, 0, 0]) == 0.0
    assert ST.auroc([0.5, 0.5, 0.5, 0.5], [1, 0, 1, 0]) == 0.5
    # hand count: pos {3, 1}, neg {2, 0}: pairs (3>2,3>0,1<2,1>0) = 3/4
    assert ST.auroc([3, 1, 2, 0], [1, 1, 0, 0]) == 0.75
    # ties count one half: pos {1}, neg {1, 0} -> (0.5 + 1)/2
    assert ST.auroc([1, 1, 0], [1, 0, 0]) == 0.75
    assert np.isnan(ST.auroc([1, 2], [1, 1]))


def test_auroc_matches_bruteforce():
    rng = np.random.default_rng(0)
    for _ in range(20):
        s = rng.integers(0, 5, 30).astype(float)
        y = rng.integers(0, 2, 30)
        if y.sum() in (0, 30):
            continue
        pos, neg = s[y == 1], s[y == 0]
        brute = np.mean([(p > n) + 0.5 * (p == n) for p in pos for n in neg])
        assert ST.auroc(s, y) == pytest.approx(brute)


def test_bootstrap_is_stratified_and_deterministic():
    rng = np.random.default_rng(1)
    y = np.array([1] * 8 + [0] * 30)
    s = np.concatenate([rng.normal(1, 1, 8), rng.normal(0, 1, 30)])
    a = ST.bootstrap_auroc(s, y, n_boot=2000, seed=5)
    b = ST.bootstrap_auroc(s, y, n_boot=2000, seed=5)
    assert a == b
    assert a["lo"] <= a["auroc"] <= a["hi"]
    assert 0 <= a["lo"] < a["hi"] <= 1


def test_permutation_p():
    y = np.array([1] * 10 + [0] * 10)
    s = np.arange(20)[::-1].astype(float)  # perfect separation
    r = ST.permutation_p(s, y, n_perm=2000, seed=3)
    assert r["auroc"] == 1.0
    assert r["p"] < 0.002
    rng = np.random.default_rng(7)
    ps = [ST.permutation_p(rng.normal(size=20), y, n_perm=300, seed=i)["p"] for i in range(30)]
    assert 0.2 < np.mean(ps) < 0.8  # null: roughly uniform


def test_paired_bootstrap_diff():
    y = np.array([1] * 10 + [0] * 20)
    a = np.concatenate([np.ones(10), np.zeros(20)])          # perfect
    b = np.random.default_rng(2).normal(size=30)             # noise
    d = ST.paired_bootstrap_diff(a, b, y, n_boot=2000, seed=4)
    assert d["diff"] == pytest.approx(d["auroc_a"] - d["auroc_b"])
    assert d["lo"] > 0
    same = ST.paired_bootstrap_diff(a, a, y, n_boot=500, seed=4)
    assert same["lo"] == same["hi"] == 0.0


def test_bands_precision_npv_calibration():
    s = np.array([0.9, 0.6, 0.3, 0.01, 0.0, 0.7])
    y = np.array([1, 0, 1, 0, 0, 1])
    r = ST.precision_npv(s, y)
    assert r["n_driver"] == 3 and r["precision_driver"] == pytest.approx(2 / 3)
    assert r["n_non_driver"] == 2 and r["npv_non_driver"] == 1.0
    assert r["n_indeterminate"] == 1
    assert ST.band_of(0.5) == "driver" and ST.band_of(0.049) == "non_driver" and ST.band_of(0.05) == "indeterminate"
    c = ST.calibration(s, y)
    assert sum(b["n"] for b in c["bins"]) == len(s)
    assert c["brier"] == pytest.approx(np.mean((s - y) ** 2))


def test_kappa():
    assert ST.cohen_kappa(["y", "n", "y", "n"], ["y", "n", "y", "n"]) == 1.0
    # classic example: po = 0.7, pe = 0.5 -> 0.4
    a = ["y"] * 5 + ["n"] * 5
    b = ["y"] * 4 + ["n"] + ["n"] * 3 + ["y"] * 2
    assert ST.cohen_kappa(a, b) == pytest.approx(0.4)


def test_decision_rules():
    assert ST.primary_decision(19, 10, 9, 0.7, 0.1)["underpowered"]
    assert ST.primary_decision(30, 4, 26, 0.7, 0.1)["underpowered"]
    d = ST.primary_decision(30, 10, 20, 0.55, -0.01)
    assert d["model_predicts"] and not d["adds_value_beyond_wiring"] and not d["underpowered"]
    d = ST.primary_decision(30, 10, 20, 0.49, 0.2)
    assert not d["model_predicts"] and not d["adds_value_beyond_wiring"]  # "adds value" requires "predicts"
    d = ST.primary_decision(30, 10, 20, 0.6, 0.2)
    assert d["model_predicts"] and d["adds_value_beyond_wiring"]
