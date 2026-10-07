"""Per-lift records of the native lift evaluation (brainir_causal.evaluate_lift; self-audit Q8 in research/phase4/SELF_AUDIT_PLAN.md:
the fraction of successful lifts at clipping bounds or beyond the development magnitude range; LOG P4-D50).

The records are ADDED beside the aggregates, which must not change: the golden values below were produced by the evaluator before the
records existed (same toy, same configuration). On the development machine the aggregates were verified bit-identical before / after on
three configurations; the tolerance here (1e-10 relative) only absorbs last-bit BLAS differences between platforms.
"""

from __future__ import annotations

import pytest
from test_lift_native import CFG, _cases, _public_histories
from test_lift_toysys import ExactModel, ToyLinear

from brainir_causal.evaluate_lift import beyond_development_range, eval_native_lift, event_magnitudes, kicks_clipped

GOLDEN_WRONG_LATENT = {"n_requests": 24, "n_simulated": 76, "success_rate": 1.0, "lift_success_rate": 0.6111111111111112,
                       "miss": 0.032838741090860823, "future_consistency": 0.7156307299790288, "kick_magnitude_mean": 0.43256532374499385,
                       "consistency_adjusted": 0.4397837402634497}


def _run(capability=None):
    s = ToyLinear()
    return eval_native_lift(ExactModel(s, wrong=True), "toy", _cases(s, 4), s.simulate_many, horizon_s=0.25, floor=0.01, truth=True,
                            cfg=CFG, whiten_histories=_public_histories(s), capability=capability)


def test_aggregates_are_unchanged_and_every_simulated_lift_has_a_record():
    res = _run()
    g = GOLDEN_WRONG_LATENT
    assert res["n_requests"] == g["n_requests"] and res["n_simulated"] == g["n_simulated"]
    assert res["success_rate"] == g["success_rate"]
    for got, want in ((res["lift_success_rate"], g["lift_success_rate"]), (res["miss"]["point"], g["miss"]),
                      (res["future_consistency"]["point"], g["future_consistency"]),
                      (res["cost"]["kick_magnitude_mean"], g["kick_magnitude_mean"]),
                      (res["consistency"]["adjusted"]["point"], g["consistency_adjusted"])):
        assert got == pytest.approx(want, rel=1e-10, abs=0.0)
    pl = res["per_lift"]
    assert len(pl) == res["n_candidates"] - res["n_invalid"] - res["n_duplicate_events"] > 0      # one record per simulated lift
    assert sum(r["success"] for r in pl) / len(pl) == pytest.approx(res["lift_success_rate"], rel=1e-12)
    for r in pl:
        assert set(r) == {"case", "request", "direction", "alpha", "requested_dz", "events", "raw_events", "beyond_dev_range", "clipped",
                          "miss", "fc", "success", "distinct"}
        assert [e["kind"] for e in r["raw_events"]] == [e["kind"] for e in r["events"]]
        assert r["case"] in {"c0", "c1", "c2", "c3"} and len(r["requested_dz"]) == 2 and r["events"]
        assert r["beyond_dev_range"] is None                                   # no capability given
        assert all(e["kind"] in ("kick", "current", "current_seq", "silence", "edge_scale", "param") for e in r["events"])
    kick_events = [e for r in pl for e in r["events"] if e["kind"] == "kick"]
    assert kick_events and all(isinstance(v, float) for e in kick_events for v in e["magnitudes"].values())


def test_the_capability_sets_the_development_range_flag_without_changing_aggregates():
    tight = {"kick": {"max": 1e-6}, "current": {"max": 1e-6}, "current_seq": {"max": 1e-6}, "edge_scale": {"max": 1e-6},
             "param": {"moderate": {"gain": 1e-6, "threshold": 1e-6, "tau": 1e-6}}}
    a, b = _run(), _run(capability=tight)
    assert b["miss"]["point"] == a["miss"]["point"] and b["lift_success_rate"] == a["lift_success_rate"]
    assert all(r["beyond_dev_range"] is True for r in b["per_lift"] if any(e["kind"] != "silence" for e in r["events"]))
    loose = {"kick": {"max": 1e9}, "current": {"max": 1e9}, "current_seq": {"max": 1e9}, "edge_scale": {"max": 1.0},
             "param": {"moderate": {"gain": 1e9, "threshold": 1e9, "tau": 1e9}}}
    assert all(r["beyond_dev_range"] is False for r in _run(capability=loose)["per_lift"])


def test_range_and_clipping_rules():
    cap = {"kick": {"max": 1.5}, "current": {"max": 2.0}, "current_seq": {"max": 2.0}, "edge_scale": {"max": 0.9},
           "param": {"moderate": {"gain": 0.3, "threshold": 1.0, "tau": 0.3}}}
    k_in = {"kind": "kick", "t": 0.1, "delta": {"3": 1.5}}
    k_out = {"kind": "kick", "t": 0.1, "delta": {"3": -1.6}}
    assert beyond_development_range([k_in], cap) is False and beyond_development_range([k_in, k_out], cap) is True
    assert beyond_development_range([{"kind": "current", "t0": 0.1, "t1": 0.2, "targets": {"1": 2.5}}], cap) is True
    assert beyond_development_range([{"kind": "current_seq", "t0": 0.1, "seg": 0.01, "targets": {"1": [0.5, -2.1]}}], cap) is True
    assert beyond_development_range([{"kind": "edge_scale", "t0": 0.1, "t1": 0.2, "edges": [[1, 2]], "factor": 0.05}], cap) is True
    assert beyond_development_range([{"kind": "edge_scale", "t0": 0.1, "t1": 0.2, "edges": [[1, 2]], "factor": 0.2}], cap) is False
    assert beyond_development_range([{"kind": "param", "t0": 0.1, "t1": 0.2, "targets": {"1": {"gain": 1.95}}}], cap) is True
    assert beyond_development_range([{"kind": "param", "t0": 0.1, "t1": 0.2, "targets": {"1": {"gain": 1.85, "threshold": -2.9}}}],
                                    cap) is False
    assert beyond_development_range([k_out], None) is None
    info_clip = {"kicks_applied": [{"t": 0.1, "requested": {"3": 1.5}, "applied": {"3": 0.4}}]}
    info_ok = {"kicks_applied": [{"t": 0.1, "requested": {"3": 1.5}, "applied": {"3": 1.5}}]}
    info_units = {"kicks_applied": [{"t": 0.1, "units": {"3": 0.9}}]}           # a synthetic generator's naming of the realized sizes
    assert kicks_clipped([k_in], info_clip) is True and kicks_clipped([k_in], info_ok) is False
    assert kicks_clipped([k_in], info_units) is True and kicks_clipped([k_in], {}) is None
    assert kicks_clipped([{"kind": "current", "t0": 0.1, "t1": 0.2, "targets": {"1": 1.0}}], info_clip) is None
    assert event_magnitudes({"kind": "silence", "t0": 0.1, "t1": 0.3, "targets": [2, 5]}) == {"kind": "silence", "t0": 0.1, "t1": 0.3,
                                                                                            "targets": [2, 5]}
