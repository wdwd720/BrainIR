"""Native lift and multiple lifts (brainir_causal.evaluate_lift; PROTOCOL 5.7) on the toy linear system with a known causal state."""

from __future__ import annotations

import numpy as np
from test_lift_toysys import ExactModel, ToyLinear, passive_protocol

from brainir_causal.api import CausalStateModel
from brainir_causal.capacity import CountingSimulator
from brainir_causal.evaluate_lift import LiftConfig, completion_index, eval_native_lift, latent_whitening, requested_shifts

CFG = LiftConfig(n_boot=200)


def _cases(n: int = 4):
    return [{"protocol": passive_protocol(100 + i), "t": 0.6 + 0.05 * i} for i in range(n)]


def test_exact_model_lifts_realise_the_shift_and_agree():
    s = ToyLinear()
    res = eval_native_lift(ExactModel(s), "toy", _cases(), s.simulate_many, horizon_s=0.25, floor=0.01, truth=True, cfg=CFG)
    assert res["supported"] and res["n_requests"] == 4 * 6          # k = 2: (2 principal + 1 random) x 2 alphas per case
    assert res["success_rate"] == 1.0
    # the achieved shift is measured one sample after the kick: one Euler step of the latent dynamics (dt |A| ~ 0.02) remains
    assert res["miss"]["point"] < 0.05
    assert res["future_consistency"]["point"] < 0.01
    cons = res["consistency"]
    assert cons["testable"] and cons["raw"]["point"] < 1e-8 and cons["adjusted"]["point"] < 1e-8
    assert cons["invariance_ratio"]["ratio"] < 1e-6
    assert res["true_shift_spread"]["point"] < 1e-8


def test_wrong_latent_lifts_diverge_after_adjustment():
    """A causally wrong latent of the same dimension: its lifts hit the requested MODEL shift but different true states, so their
    futures diverge; the adjusted consistency (not confounded by the request magnitude) keeps that divergence."""
    s = ToyLinear()
    res = eval_native_lift(ExactModel(s, wrong=True), "toy", _cases(), s.simulate_many, horizon_s=0.25, floor=0.01, truth=True, cfg=CFG)
    assert res["miss"]["point"] < 0.1                                # it does move ITS latent as requested
    assert res["consistency"]["adjusted"]["point"] > 0.2
    assert res["true_shift_spread"]["point"] > 0.2
    assert res["future_consistency"]["point"] > 0.5


class NoLift(ExactModel):
    lift = CausalStateModel.lift


def test_model_without_lift_fails_every_request_without_simulation():
    s = ToyLinear()
    sim = CountingSimulator(s.simulate_many, many=True)
    res = eval_native_lift(NoLift(s), "toy", _cases(3), sim, horizon_s=0.25, floor=0.01, cfg=CFG)
    assert not res["supported"] and res["success_rate"] == 0.0 and res["n_requests"] == 3 * 6
    assert sim.calls == 0


class BadLifts(ExactModel):
    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        return [{"events": [{"kind": "current", "t0": 0.0, "t1": None, "targets": {"0": 1.0}}]},       # persistent: refused
                {"events": [{"kind": "latent_kick", "t": 0.0, "dz": [1.0, 0.0]}]},                   # truth-only: refused
                {"events": [{"kind": "kick", "t": -0.1, "delta": {"0": 1.0}}]}]                      # before the case time


def test_invalid_lifts_are_counted_and_never_simulated():
    s = ToyLinear()
    res = eval_native_lift(BadLifts(s), "toy", _cases(2), s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG)
    assert res["n_candidates"] == 2 * 6 * 3 and res["n_invalid"] == res["n_candidates"]
    assert res["n_persistent"] == 2 * 6 and res["success_rate"] == 0.0
    assert res["consistency"]["testable"] is False


class DuplicateLifts(ExactModel):
    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        one = super().lift(sid, x_hist, u_hist, delta_z, 1)[0]
        return [one, dict(one), dict(one)]


def test_identical_event_sets_are_dropped_and_consistency_untestable():
    s = ToyLinear()
    res = eval_native_lift(DuplicateLifts(s), "toy", _cases(2), s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG)
    assert res["n_duplicate_events"] == 2 * 6 * 2
    assert res["consistency"]["testable"] is False and "untestable" in res["consistency"]["reason"]
    assert res["success_rate"] == 1.0


def test_requested_shifts_have_whitened_norm_alpha():
    rng = np.random.default_rng(0)
    Z = rng.standard_normal((200, 3)) @ np.array([[3.0, 0, 0], [1.0, 0.5, 0], [0, 0.2, 0.1]])
    w = latent_whitening(Z)
    reqs = requested_shifts(w, CFG, np.random.default_rng(1))
    assert len(reqs) == 6
    for r in reqs:
        assert abs(np.linalg.norm(w["isqrt"] @ r["dz"]) - r["alpha"]) < 1e-9
    w1 = latent_whitening(rng.standard_normal((50, 1)) * 2.0)
    r1 = requested_shifts(w1, CFG, np.random.default_rng(2))
    assert [r["direction"] for r in r1] == ["pc1+", "pc1+", "pc1-", "pc1-"]
    assert np.allclose(r1[0]["dz"], -r1[2]["dz"])


def test_completion_index_semantics():
    ev = [{"kind": "kick", "t": 0.5, "delta": {"0": 1.0}}]
    assert completion_index(ev, 0.01) == 51
    ev2 = [{"kind": "current", "t0": 0.5, "t1": 0.6, "targets": {"0": 1.0}}, {"kind": "kick", "t": 0.52, "delta": {"1": 1.0}}]
    assert completion_index(ev2, 0.01) == 60
    assert completion_index([{"kind": "silence", "t0": 0.5, "t1": None, "targets": [0]}], 0.01) is None
