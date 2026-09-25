"""The pre-registered Level C primary family (PROTOCOL.md section 8, version 2; review E B4): 13 one-sided non-inferiority tests
with margins, paired bootstraps, uncomputable tests kept with p = 1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "p3"))
import level_c as L  # noqa: E402
from brainir_state.harness import REAL_CFG, key_a, key_d  # noqa: E402

KA = key_a(REAL_CFG)
KC = f"C_w{int(round(REAL_CFG.primary_c_window_s * 1000))}ms"
KD = key_d(REAL_CFG)


def _res(rng, a_shift=0.0, c_scale=1.0, d_shift=0.0, e_noise=0.0, testable=True):
    n = 40
    a_units = {f"t{i}": 0.1 + 0.01 * i + a_shift for i in range(n)}
    c_units = {f"p{i}": (0.3 * c_scale * (1 + 0.1 * (i % 3)), 1.0, 0.1, "H_kick_B") for i in range(30)}
    traj = [i // 20 for i in range(400)]
    e_z = list(0.5 + 0.01 * rng.standard_normal(400))
    e_m = list(np.array(e_z) - 0.01 - d_shift)
    div = list(np.abs(rng.standard_normal(300)))
    d = list(np.array(div) + e_noise * np.abs(rng.standard_normal(300)))
    return {"A_B": {KA: {"mean": float(np.mean(list(a_units.values())))}, "_units": {KA: a_units}},
            "C_heldout": {"_units": {KC: c_units}},
            "D": {KD: {"_units": {"traj": traj, "e_z": e_z, "e_micro": e_m}}},
            "E": {"E_testable": testable, "E_ratio_latent_to_random": 0.01,
                  "_units": {"div": div, "d": d, "ti": [i % 10 for i in range(300)], "tj": [(i % 10 + 1) % 10 + 10 for i in range(300)],
                             "traj_draw": [0] * 10 + [1] * 10}}}


def test_identical_models_are_non_inferior_on_every_family():
    rng = np.random.default_rng(0)
    r = _res(rng)
    out = L.primary_tests(r, r, REAL_CFG)
    for fam in ("A", "C", "D"):
        assert out[fam]["computable"] and out[fam]["p_noninferiority"] < 0.01, (fam, out[fam])


def test_a_clearly_worse_method_is_not_non_inferior():
    rng = np.random.default_rng(1)
    base = _res(rng)
    worse = _res(np.random.default_rng(1), a_shift=0.2, c_scale=2.0)
    out = L.primary_tests(worse, base, REAL_CFG)
    assert out["A"]["p_noninferiority"] > 0.5 and out["C"]["p_noninferiority"] > 0.5


def test_uncomputable_tests_stay_in_the_family_with_p_one():
    rng = np.random.default_rng(2)
    out = L.primary_tests(_res(rng, testable=False), _res(np.random.default_rng(2)), REAL_CFG)
    assert out["E"]["p_noninferiority"] == 1.0 and not out["E"]["computable"]
    missing = L.primary_tests(None, None, REAL_CFG)
    assert all(v["p_noninferiority"] == 1.0 for v in missing.values())
    from brainir_state.evaluate_cross import holm
    h = holm({"x": 0.001, "y": missing["A"]["p_noninferiority"]})
    assert h["y"] == 1.0 and abs(h["x"] - 0.002) < 1e-12


def test_k_on_the_final_suite_is_paired_by_system(tmp_path, monkeypatch):
    rnd = tmp_path / "research" / "phase3" / "tournament" / "fin"
    rnd.mkdir(parents=True)
    # version 3: K = min(R^2 true <- model, R^2 model <- true); both directions are given here
    per_m = {f"s{i}": {"k_true": 2, "K": {"r2_true_from_model_rff": 0.95, "r2_model_from_true_rff": 0.95}} for i in range(20)}
    per_b = {f"s{i}": {"k_true": 2, "K": {"r2_true_from_model_rff": 0.90, "r2_model_from_true_rff": 0.90}} for i in range(20)}
    per_m["s0"] = {"k_true": 2, "error": "timeout"}            # a failure counts as the worst recovery
    (rnd / "m.json").write_text(json.dumps({"per_system": per_m}), encoding="utf-8")
    (rnd / "b.json").write_text(json.dumps({"per_system": per_b}), encoding="utf-8")
    monkeypatch.setattr(L, "ROOT", tmp_path)
    out = L.k_test_final("fin", "m", "b")
    assert out["n_systems"] == 20 and out["computable"]
    assert out["diff"] == pytest.approx((1.9 - 19 * 0.05) / 20)
    assert L.k_test_final("missing", "m", "b")["p_noninferiority"] == 1.0
