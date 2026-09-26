"""Leave-one-intervention-out, leave-one-implementation-out, sharing comparison and the hard gate (brainir_causal.evaluate_transfer;
PROTOCOL 5.13-5.14)."""

from __future__ import annotations

import numpy as np
from test_lift_toysys import ToyLinear, make_records

from brainir_causal.evaluate_stability import intervention_items
from brainir_causal.evaluate_transfer import limpo_comparison, limpo_subsample, loio_datasets, loio_summary, paired_ee, sharing_comparison, sharing_gate


def _labelled(recs):
    for r in recs:
        ev = r["protocol"]["events"]
        r["family"] = ("kick.1" if ev[0]["kind"] == "kick" else "pulse.1") if ev else "obs.stim"
    return recs


def test_loio_removes_one_family_with_its_twins():
    recs = _labelled(make_records(ToyLinear(), n_passive=4, n_kick=6, n_pulse=3, seed=1, full=False)[0])
    sysrec = {"split": {"families_train": ["kick.1", "pulse.1"]}}
    ds = loio_datasets(recs, sysrec)
    assert set(ds) == {"kick.1", "pulse.1"}
    no_kick = ds["kick.1"]
    items, passive = intervention_items(no_kick)
    assert all(it[0]["family"] == "pulse.1" for it in items) and len(items) == 3 and len(passive) == 4
    assert len(no_kick) == 4 + 2 * 3                              # passive + pulse items with their twins


def test_loio_summary_is_paired_on_the_familys_items():
    full = {f"i{k}": (0.1, 1.0) for k in range(10)}
    loio = {"kick.1": {f"i{k}": (0.5, 1.0) for k in range(10)}}
    fams = {f"i{k}": ("kick.1" if k < 6 else "pulse.1") for k in range(10)}
    s = loio_summary(full, loio, fams, n_boot=200)
    f = s["per_family"]["kick.1"]
    assert f["n"] == 6 and abs(f["gap"] - 0.4) < 1e-12 and abs(f["ee_full"] - 0.1) < 1e-12


def test_limpo_subsample_and_comparison():
    recs = make_records(ToyLinear(), n_passive=8, n_kick=8, n_pulse=4, seed=2, full=False)[0]
    sub = limpo_subsample(recs, 0.25, seed=0)
    items, passive = intervention_items(sub)
    assert len(items) == 3 and len(passive) == 2 and len(sub) == 2 + 2 * 3
    rng = np.random.default_rng(0)
    good = {f"i{k}": (0.1 + 0.01 * rng.random(), 1.0) for k in range(40)}
    bad = {f"i{k}": (0.6 + 0.01 * rng.random(), 1.0) for k in range(40)}
    assert limpo_comparison(good, bad, n_boot=300)["adapted_beats_scratch"]
    assert limpo_comparison(bad, good, n_boot=300)["adapted_worse"]


def _units(level, n=30, seed=0):
    rng = np.random.default_rng(seed)
    return {f"i{k}": (level * (1 + 0.1 * rng.standard_normal()) ** 2, 1.0) for k in range(n)}


def test_sharing_rule_and_hard_gate():
    ee = {"A": {"s1": _units(0.2), "s2": _units(0.3, seed=1)}, "B": {"s1": _units(0.21, seed=2), "s2": _units(0.31, seed=3)}}
    sms = {"A": {"s1": {"point": 0.0, "ci95": [-0.05, 0.05]}, "s2": {"point": 0.0, "ci95": [-0.05, 0.05]}},
           "B": {"s1": {"point": 0.01, "ci95": [-0.04, 0.07]}, "s2": {"point": 0.0, "ci95": [-0.05, 0.06]}}}
    transfer = [{"adapted_beats_scratch": True, "adapted_worse": False}, {"adapted_beats_scratch": False, "adapted_worse": False}]
    ok = sharing_comparison(ee, sms, {"A": 1000, "B": 600}, transfer, n_boot=300)
    assert ok["models"]["B"]["verdict"] == "supported"
    assert sharing_comparison(ee, sms, {"A": 1000, "B": 1200}, transfer, n_boot=300)["models"]["B"]["verdict"] == "rejected"
    assert sharing_comparison(ee, sms, {"A": 1000, "B": None}, transfer, n_boot=300)["models"]["B"]["verdict"] == "untestable"
    worse = dict(ee, B={"s1": _units(0.6, seed=4), "s2": _units(0.31, seed=3)})
    assert sharing_comparison(worse, sms, {"A": 1000, "B": 600}, transfer, n_boot=300)["models"]["B"]["verdict"] == "rejected"
    gated = sharing_comparison(ee, sms, {"A": 1000, "B": 600}, transfer, within_verdicts={"s1": "causal state supported",
                                                                                        "s2": "partially supported"}, n_boot=300)
    assert gated["models"]["B"]["verdict"] == "prerequisite failed" and not gated["gate"]["passed"]
    assert sharing_gate({"s1": "Causal state supported"})["passed"]


def test_paired_ee_is_a_ratio_of_sums():
    a = {"x": (1.0, 2.0), "y": (3.0, 2.0)}
    b = {"x": (0.0, 2.0), "y": (1.0, 2.0), "z": (5.0, 1.0)}
    d = paired_ee(a, b, n_boot=100)
    assert d["n"] == 2 and abs(d["diff"] - (4.0 / 4.0 - 1.0 / 4.0)) < 1e-12
