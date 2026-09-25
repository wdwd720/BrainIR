"""The evaluator on a toy system with KNOWN state (goal4 section 71: SYNTHETIC TRUTH, CAUSAL TESTS, SHORTCUTS).

Toy: z in R^2, a damped oscillator driven by u; microstate x = C z (N = 20 neurons, x-dynamics exactly those of z mapped by C),
readout y = D z. A kick dx on neurons moves z by pinv(C) dx. With the true dimension a PCA-2 linear model must be predictive,
closed and Markov-consistent; the input-only shortcut must be worse; latent-matched microstates must have near-equal futures.
"""

from __future__ import annotations

import numpy as np
import pytest

from brainir_state import evaluate as E
from brainir_state.data import Trajectory
from brainir_state.refmodels import DirectHorizonModel, ProjectionLinearModel

DT, T_END = 0.001, 1.6
N, NY = 20, 3
RNG = np.random.default_rng(0)
C = RNG.standard_normal((N, 2))
Dm = RNG.standard_normal((NY, 2))
Cp = np.linalg.pinv(C)
OMEGA, GAMMA = 2 * np.pi * 6.0, 1.5


def _f(z, u):
    return np.array([z[1], -OMEGA**2 * z[0] - 2 * GAMMA * z[1] + 40.0 * u])


def simulate(z0, u_sched, events=(), t_end=T_END):
    n = int(round(t_end / DT)) + 1
    z = np.array(z0, float)
    X, Y, U = [], [], []
    for i in range(n):
        t = i * DT
        u = [s for ts, s in u_sched if ts <= t + 1e-9][-1]
        X.append(C @ z); Y.append(Dm @ z); U.append([u])
        for e in events:
            if e["kind"] == "kick" and abs(e["t"] - t) < DT / 2:
                dx = np.zeros(N)
                for k, v in e["delta"].items():
                    dx[int(k)] = v
                z = z + Cp @ dx
        k1 = _f(z, u); k2 = _f(z + DT / 2 * k1, u); k3 = _f(z + DT / 2 * k2, u); k4 = _f(z + DT * k3, u)
        z = z + DT / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    t = np.arange(n) * DT
    return t, np.array(X), np.array(U), np.array(Y)


def traj(key, z0, u_sched, events=(), fam="nominal"):
    t, X, U, Y = simulate(z0, u_sched, events)
    proto = {"system": "toy", "params_seed": 0, "t_end": T_END, "dt": DT, "stimulus": [list(s) for s in u_sched], "events": list(events)}
    return Trajectory(key=key, system_id="toy", split="x", family=fam, protocol=proto, t=t, x=X.astype(np.float32), u=U.astype(np.float32),
                      y=Y.astype(np.float32))


def _u_sched(rng):
    return [(0.0, 0.0), (round(float(rng.uniform(0.05, 0.2)), 3), float(rng.uniform(0.5, 1.5))),
            (round(float(rng.uniform(0.6, 1.0)), 3), float(rng.uniform(0.0, 1.5)))]


@pytest.fixture(scope="module")
def data():
    rng = np.random.default_rng(1)
    train = [traj(f"tr{i}", rng.standard_normal(2), _u_sched(rng)) for i in range(40)]
    test = [traj(f"te{i}", rng.standard_normal(2), _u_sched(rng)) for i in range(12)]
    pairs = []
    for i in range(12):
        z0, us = rng.standard_normal(2), _u_sched(rng)
        ev = [{"kind": "kick", "t": round(float(rng.uniform(0.4, 1.0)), 3), "delta": {str(int(rng.integers(N))): float(rng.uniform(-3, 3))}}]
        pairs.append((traj(f"k{i}", z0, us, ev, "H_kick_B"), traj(f"kt{i}", z0, us, (), "H_kick_B")))
    return train, test, pairs


class KickAwarePCA(ProjectionLinearModel):
    pass


def test_pca_at_the_true_dimension_is_predictive_closed_and_markov(data):
    train, test, pairs = data
    scale = E.readout_scale(train)
    pca = E.pca_basis if hasattr(E, "pca_basis") else None
    m = ProjectionLinearModel(2, "pca").fit("toy", train, list(range(N)))
    io = DirectHorizonModel("input_only").fit("toy", train)
    cfg = E.EvalConfig(n_boot=200)
    a_m = E.eval_predictive(m, "toy", test, scale, cfg)["A_nmse_h250ms"]["mean"]
    a_io = E.eval_predictive(io, "toy", test, scale, cfg)["A_nmse_h250ms"]["mean"]
    assert a_m < 0.05, a_m                 # the true 2-D state predicts 250 ms ahead
    assert a_io > 3 * a_m, (a_io, a_m)     # the input-only shortcut cannot
    from brainir_state.harness import pca_basis
    d = E.eval_closure(m, "toy", test, pca_basis(train), scale, cfg)
    assert abs(d["D_y_h100ms_linear"]["micro_gain"]) < 0.1, d
    r = E.eval_rollout_checks(m, "toy", test, scale, cfg)
    assert r["markov_rollout_inconsistency_rel"] < 1e-9, r
    c = E.eval_intervention(m, "toy", pairs, scale, cfg)
    assert c["C_effect_error_w250ms"]["ratio"] < 0.2, c      # a kick moves z by P dx: the model predicts its effect


def test_one_dimensional_latent_is_not_closed(data):
    train, test, _ = data
    scale = E.readout_scale(train)
    from brainir_state.harness import pca_basis
    m1 = ProjectionLinearModel(1, "pca").fit("toy", train, list(range(N)))
    cfg = E.EvalConfig(n_boot=200)
    a1 = E.eval_predictive(m1, "toy", test, scale, cfg)["A_nmse_h250ms"]["mean"]
    d1 = E.eval_closure(m1, "toy", test, pca_basis(train), scale, cfg)
    assert a1 > 0.2 or d1["D_y_h100ms_rff"]["micro_gain"] > 0.2, (a1, d1)


def test_microstate_equivalence_prefers_the_true_state(data):
    train, _, _ = data
    scale = E.readout_scale(train)
    m = ProjectionLinearModel(2, "pca").fit("toy", train, list(range(N)))
    rng = np.random.default_rng(5)
    pool = []
    for i in range(80):
        z0 = rng.standard_normal(2) * 1.5
        t, X, U, Y = simulate(z0, [(0.0, 1.0)], t_end=0.25)
        pool.append({"x_hist": X[:1].astype(np.float32), "u_hist": U[:1].astype(np.float32), "y_hist": Y[:1], "dt": DT, "y_now": Y[0],
                     "future_y": Y[1:], "group": 0})
    e = E.eval_microstate(m, "toy", pool, scale, E.EvalConfig(n_boot=200, micro_match_quantile=0.05))
    assert e["E_ratio_latent_to_random"] < 0.2, e
