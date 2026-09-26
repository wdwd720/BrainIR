"""The CPU half of the CPU / GPU equivalence harness (brainir_causal.equiv); the GPU half runs on Modal (scripts/p4/modal_p4.py
equiv-gpu). Checks: seeded CPU runs are bitwise identical; `compare` detects a real difference; the stated tolerances separate the
float64 and float32 regimes (float32 vs float64 on the same device fails the float64 bounds and passes the float32 ones)."""

import copy

import numpy as np
import pytest

torch = pytest.importorskip("torch")

from brainir_causal import equiv as E  # noqa: E402

CFG = {"kind": "rollout", "n_x": 6, "k": 2, "t_len": 30, "batch": 4, "lr": 1e-3}


@pytest.fixture(scope="module")
def runs():
    torch.set_num_threads(2)
    a = E.run_training(E.REFERENCE, CFG, "cpu", "float64", seed=3, steps=6)
    b = E.run_training(E.REFERENCE, CFG, "cpu", "float64", seed=3, steps=6)
    f = E.run_training(E.REFERENCE, CFG, "cpu", "float32", seed=3, steps=6)
    return a, b, f


def test_seeded_cpu_runs_are_bitwise_identical(runs):
    a, b, _ = runs
    c = E.compare(a, b)
    assert c["bitwise_identical"] and c["pass"]
    assert c["loss_rel_max"] == 0.0 and c["param_rel"] == 0.0 and c["pred_rel"] == 0.0
    assert len(a["losses"]) == 6 and all(np.isfinite(a["losses"]))


def test_compare_detects_a_parameter_difference(runs):
    a, _, _ = runs
    b = copy.deepcopy(a)
    k = sorted(b["params"])[0]
    b["params"][k] = b["params"][k] + 1e-3 * (np.abs(b["params"][k]).max() + 1.0)
    c = E.compare(a, b)
    assert not c["bitwise_identical"] and not c["pass"] and c["param_rel"] > E.TOLERANCES["float64"]["param_rel"]


def test_tolerances_separate_float64_and_float32(runs):
    a, _, f = runs
    c64 = E.compare(a, f, "float64")
    c32 = E.compare(a, f, "float32")
    assert not c64["pass"], "float32 rounding must exceed the float64 bounds (otherwise the float64 bounds are vacuous)"
    assert c32["pass"], c32


def test_gru_reference_trainer_runs_on_cpu():
    r = E.run_training(E.REFERENCE, dict(CFG, kind="gru"), "cpu", "float64", seed=0, steps=2)
    assert r["pred"].shape == (4, 30, 8) and np.all(np.isfinite(r["pred"]))


def test_run_training_restores_global_torch_settings():
    before = torch.are_deterministic_algorithms_enabled()
    E.run_training(E.REFERENCE, CFG, "cpu", "float64", seed=0, steps=1)
    assert torch.are_deterministic_algorithms_enabled() == before
