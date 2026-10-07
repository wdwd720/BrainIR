"""Lift requests restricted to the kick-reachable span on synthetic systems (review T round 3, N4; PROTOCOL 5.7): the projection is
orthogonal in the whitened metric and keeps the request's whitened length; a request mostly outside the span is dropped; a span
that covers every direction changes nothing; the evaluator reports the reachability."""

from __future__ import annotations

import numpy as np
import pytest
from test_lift_native import CFG, _cases, _public_histories
from test_lift_toysys import ExactModel, ToyLinear

from brainir_causal.evaluate_lift import eval_native_lift, latent_whitening, restrict_to_reachable


def test_the_projection_keeps_the_whitened_length_and_drops_unreachable_requests():
    rng = np.random.default_rng(3)
    Z = rng.standard_normal((200, 3)) @ np.diag([3.0, 1.0, 0.5])
    whit = latent_whitening(Z)
    reach = np.array([[1.0, 0.0, 0.0], [2.0, 0.0, 0.0]])                  # one reachable direction (rank 1)
    V, sw = whit["evecs"], np.sqrt(whit["evals"])
    wlen = lambda d: float(np.linalg.norm((V.T @ d) / sw))                  # noqa: E731
    dz = np.array([3.0, 1.0, 0.0])
    out, rank = restrict_to_reachable(dz, whit, reach, 0.25)
    assert rank == 1 and out is not None and wlen(out) == pytest.approx(wlen(dz), rel=1e-9)
    assert abs(out[1]) < 1e-9 * abs(out[0]) and abs(out[2]) < 1e-9 * abs(out[0])     # along the reachable direction only
    off, rank2 = restrict_to_reachable(np.array([0.0, 0.0, 1.0]), whit, reach, 0.25)
    assert off is None and rank2 == 1
    full, rk = restrict_to_reachable(dz, whit, np.eye(3), 0.25)
    assert rk == 3 and np.allclose(full, dz, rtol=1e-12, atol=1e-12)


def _run(reach_fn=None):
    s = ToyLinear()
    return s, eval_native_lift(ExactModel(s, wrong=True), "toy", _cases(s, 4), s.simulate_many, horizon_s=0.25, floor=0.01, truth=True,
                               cfg=CFG, whiten_histories=_public_histories(s), reach_fn=reach_fn)


def test_a_span_covering_every_direction_changes_nothing_and_a_narrow_span_restricts():
    s, base = _run()
    assert "reachability" not in base                                        # no truth hook: output unchanged
    s, full = _run(lambda state: np.stack([s.C[:, u] for u in range(s.n)]))  # every unit a public target: rank 2 = k
    for key in ("n_requests", "n_simulated", "success_rate", "lift_success_rate"):
        assert full[key] == base[key], key
    assert full["miss"]["point"] == pytest.approx(base["miss"]["point"], rel=1e-9)
    r = full["reachability"]
    assert r["n_requests_unreachable"] == 0 and r["n_requests_merged"] == 0 and r["rank_median"] == 2
    assert r["n_cases_restricted"] == 4 and r["multiple_kick_lifts_possible"] is True
    s, one = _run(lambda state: s.C[:, [0]].T)                                # a single reachable direction
    r1 = one["reachability"]
    assert r1["rank_median"] == 1 and r1["n_requests_unreachable"] + r1["n_requests_merged"] > 0
    assert one["n_requests"] < base["n_requests"] and r1["multiple_kick_lifts_possible"] is False
    c0 = s.C[:, 0] / np.linalg.norm(s.C[:, 0])
    for rec in one["per_lift"]:                                              # every simulated request lies along that direction
        d = np.asarray(rec["requested_dz"], float)
        assert abs(abs(float(d @ c0)) / np.linalg.norm(d) - 1.0) < 1e-9
