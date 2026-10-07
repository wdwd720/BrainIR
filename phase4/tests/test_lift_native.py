"""Native lift and multiple lifts (brainir_causal.evaluate_lift; PROTOCOL 5.7) on the toy linear system with a known causal state."""

from __future__ import annotations

import numpy as np
import pytest
from test_lift_toysys import DT, ExactModel, ToyLinear, make_records, passive_protocol

from brainir_causal import protocol as P
from brainir_causal.api import CausalStateModel
from brainir_causal.capacity import CountingSimulator
from brainir_causal.evaluate_lift import LiftConfig, completion_index, eval_native_lift, latent_whitening, lift_cost, requested_shifts, restart_protocol

CFG = LiftConfig(n_boot=200)


def _cases(s: ToyLinear, n: int = 4, with_history: bool = False):
    """Lift cases: a passive protocol, the case time and the case's exact microstate (the toy's full state is x) as the restart r0."""
    out = []
    for i in range(n):
        q = P.validate(passive_protocol(100 + i))
        t = round(0.6 + 0.05 * i, 2)
        rec = s.simulate(q, full=True)
        ic = round(t / DT)
        c = {"protocol": q, "t": t, "id": f"c{i}", "r0": {"kind": "state", "values": {str(u): float(v) for u, v in enumerate(rec["x"][ic])}}}
        if with_history:
            c.update(x_hist=rec["x"][: ic + 1], u_hist=rec["u"][: ic + 1], z_hist=rec["z"][: ic + 1])
        out.append(c)
    return out


def _public_histories(s: ToyLinear):
    """(x_hist, u_hist, dt) of public training trajectories (the harness's whiten_histories)."""
    recs, _ = make_records(s, n_passive=6, n_kick=6, n_pulse=0, seed=9, full=False)
    return [(r["x"][: i + 1], r["u"][: i + 1], DT) for r in recs for i in (60, 90, 120, 150)]


def test_exact_model_lifts_realise_the_shift_and_agree():
    s = ToyLinear()
    res = eval_native_lift(ExactModel(s), "toy", _cases(s), s.simulate_many, horizon_s=0.25, floor=0.01, truth=True, cfg=CFG,
                           whiten_histories=_public_histories(s))
    assert res["supported"] and res["n_requests"] == 4 * 6          # k = 2: (2 principal + 1 random) x 2 alphas per case
    assert res["whitening"] == {"source": "histories", "n": 72, "eig_floor": 1e-6}   # 18 public records x 4 times
    assert res["success_rate"] == 1.0
    # the achieved shift is measured one sample after the kick: one Euler step of the latent dynamics (dt |A| ~ 0.02) remains
    assert res["miss"]["point"] < 0.05
    assert res["future_consistency"]["point"] < 0.01
    cons = res["consistency"]
    assert cons["testable"] and cons["raw"]["point"] < 1e-8 and cons["adjusted"]["point"] < 1e-8
    assert cons["invariance_ratio"]["ratio"] < 1e-6
    assert res["true_shift_spread"]["point"] < 1e-8
    assert res["cost"]["kick_magnitude_mean"] > 0 and res["cost"]["current_dose_mean"] == 0.0


def test_given_histories_and_simulated_histories_agree():
    """A case may carry its history (the harness passes the stored trajectory) or let the evaluator simulate it: same scores."""
    s = ToyLinear()
    hz = _public_histories(s)
    a = eval_native_lift(ExactModel(s), "toy", _cases(s, 2), s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG, whiten_histories=hz)
    b = eval_native_lift(ExactModel(s), "toy", _cases(s, 2, with_history=True), s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG,
                         whiten_histories=hz)
    assert a["n_simulated"] == b["n_simulated"]
    assert a["miss"]["point"] == pytest.approx(b["miss"]["point"], rel=1e-12)
    assert a["future_consistency"]["point"] == pytest.approx(b["future_consistency"]["point"], rel=1e-12)


def test_wrong_latent_lifts_diverge_after_adjustment():
    """A causally wrong latent of the same dimension: its lifts hit the requested MODEL shift but different true states, so their
    futures diverge; the adjusted consistency (not confounded by the request magnitude) keeps that divergence."""
    s = ToyLinear()
    res = eval_native_lift(ExactModel(s, wrong=True), "toy", _cases(s), s.simulate_many, horizon_s=0.25, floor=0.01, truth=True, cfg=CFG,
                           whiten_histories=_public_histories(s))
    assert res["miss"]["point"] < 0.1                                # it does move ITS latent as requested
    assert res["consistency"]["adjusted"]["point"] > 0.2
    assert res["true_shift_spread"]["point"] > 0.2
    assert res["future_consistency"]["point"] > 0.5


def test_whitening_needs_public_training_data():
    s = ToyLinear()
    with pytest.raises(ValueError, match="PUBLIC training data"):
        eval_native_lift(ExactModel(s), "toy", _cases(s, 1), s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG)
    Z = np.stack([ExactModel(s).encode("toy", x, u, dt) for x, u, dt in _public_histories(s)])
    res = eval_native_lift(ExactModel(s), "toy", _cases(s, 1), s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG, whiten_z=Z)
    assert res["whitening"]["source"] == "encodings" and res["success_rate"] == 1.0
    with pytest.raises(ValueError, match="stored microstate"):
        c = _cases(s, 1)[0]
        c.pop("r0")
        eval_native_lift(ExactModel(s), "toy", [c], s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG, whiten_z=Z)


class NoLift(ExactModel):
    lift = CausalStateModel.lift


def test_model_without_lift_fails_every_request_without_simulation():
    s = ToyLinear()
    sim = CountingSimulator(s.simulate_many, many=True)
    res = eval_native_lift(NoLift(s), "toy", _cases(s, 3), sim, horizon_s=0.25, floor=0.01, cfg=CFG)
    assert not res["supported"] and res["success_rate"] == 0.0 and res["n_requests"] == 3 * 6
    assert sim.calls == 0


class BadLifts(ExactModel):
    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        return [{"events": [{"kind": "current", "t0": 0.0, "t1": None, "targets": {"0": 1.0}}]},       # persistent: refused
                {"events": [{"kind": "latent_kick", "t": 0.0, "dz": [1.0, 0.0]}]},                   # truth-only: refused
                {"events": [{"kind": "kick", "t": -0.1, "delta": {"0": 1.0}}]}]                      # before the case time


def test_invalid_lifts_are_counted_and_never_simulated():
    s = ToyLinear()
    sim = CountingSimulator(s.simulate_many, many=True)
    res = eval_native_lift(BadLifts(s), "toy", _cases(s, 2), sim, horizon_s=0.25, floor=0.01, cfg=CFG,
                           whiten_histories=_public_histories(s))
    assert res["n_candidates"] == 2 * 6 * 3 and res["n_invalid"] == res["n_candidates"]
    assert res["n_persistent"] == 2 * 6 and res["success_rate"] == 0.0
    assert res["invalid_reasons"]["event before the case time"] == 2 * 6
    assert res["consistency"]["testable"] is False
    assert sim.trajectories == 2                                 # only the two case histories were simulated


class DuplicateLifts(ExactModel):
    def lift(self, sid, x_hist, u_hist, delta_z, n_candidates=3, constraints=None):
        one = super().lift(sid, x_hist, u_hist, delta_z, 1)[0]
        return [one, dict(one), dict(one)]


def test_identical_event_sets_are_dropped_and_consistency_untestable():
    s = ToyLinear()
    res = eval_native_lift(DuplicateLifts(s), "toy", _cases(s, 2), s.simulate_many, horizon_s=0.25, floor=0.01, cfg=CFG,
                           whiten_histories=_public_histories(s))
    assert res["n_duplicate_events"] == 2 * 6 * 2
    assert res["consistency"]["testable"] is False and "untestable" in res["consistency"]["reason"]
    assert res["success_rate"] == 1.0


def test_restart_protocol_and_cost():
    q = P.validate({"system": "toy", "params_seed": 3, "t_end": 2.0, "dt": DT, "stimulus": [[0.0, 0.0], [0.1, 1.0], [0.9, 0.5]],
                    "weight_noise": {"sd": 0.05, "seed": 4}, "events": []})
    r0 = {"kind": "state", "values": {"0": 1.0}}
    rp = P.validate(restart_protocol(q, 0.6, r0, [{"kind": "kick", "t": 0.0, "delta": {"1": 2.0}}]))
    assert rp["r0"] == r0 and rp["t_end"] == pytest.approx(1.4) and rp["params_seed"] == 3 and rp["weight_noise"] == q["weight_noise"]
    assert rp["stimulus"] == [[0.0, 1.0], [pytest.approx(0.3), 0.5]]
    c = lift_cost([{"kind": "kick", "t": 0.0, "delta": {"1": 2.0, "2": -1.0}},
                   {"kind": "current", "t0": 0.0, "t1": 0.1, "targets": {"3": 4.0}},
                   {"kind": "silence", "t0": 0.0, "t1": 0.2, "targets": [4]}], t_end=1.4)
    assert c["kick_magnitude"] == 3.0 and c["current_dose"] == pytest.approx(0.4) and c["silence_unit_s"] == pytest.approx(0.2)
    assert c["n_targets"] == 4


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
    # the eigenvalue floor is 1e-6 x the largest (PROTOCOL 5.5 / 5.7)
    wd = latent_whitening(np.column_stack([rng.standard_normal(100), 1e-9 * rng.standard_normal(100)]))
    assert wd["evals"][1] == pytest.approx(1e-6 * wd["evals"][0])


def test_completion_index_semantics():
    ev = [{"kind": "kick", "t": 0.5, "delta": {"0": 1.0}}]
    assert completion_index(ev, 0.01) == 51
    ev2 = [{"kind": "current", "t0": 0.5, "t1": 0.6, "targets": {"0": 1.0}}, {"kind": "kick", "t": 0.52, "delta": {"1": 1.0}}]
    assert completion_index(ev2, 0.01) == 60
    assert completion_index([{"kind": "silence", "t0": 0.5, "t1": None, "targets": [0]}], 0.01) is None
