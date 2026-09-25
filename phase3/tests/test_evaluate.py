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


# ------------------------------------------------------------------------------------------------ benchmark version 2 (reviews E, H)
class _NaNOnHardStarts(ProjectionLinearModel):
    """Declines (returns NaN) whenever |z0| is large: version 1 dropped such units and reported a better A."""

    def rollout(self, sid, z0, u_future, events, dt):
        out = super().rollout(sid, z0, u_future, events, dt)
        if np.linalg.norm(z0) > self._thr:
            out = {"z": np.asarray(out["z"]) * np.nan, "y": np.asarray(out["y"]) * np.nan}
        return out


def test_nonfinite_predictions_count_as_the_cap_and_are_reported(data):
    train, test, _ = data
    scale = E.readout_scale(train)
    cfg = E.EvalConfig(n_boot=100)
    honest = ProjectionLinearModel(2, "pca").fit("toy", train, list(range(N)))
    dodger = _NaNOnHardStarts(2, "pca").fit("toy", train, list(range(N)))
    zs = [np.linalg.norm(honest.encode("toy", t.x[: E.idx(0.6, DT) + 1], t.u[: E.idx(0.6, DT) + 1], DT)) for t in test]
    dodger._thr = float(np.percentile(zs, 50))
    a_h = E.eval_predictive(honest, "toy", test, scale, cfg)["A_nmse_h250ms"]
    a_d = E.eval_predictive(dodger, "toy", test, scale, cfg)["A_nmse_h250ms"]
    assert a_d["n_windows_nonfinite"] > 0 and a_d["n"] == a_h["n"]
    assert a_d["mean"] > a_h["mean"] and np.isfinite(a_d["mean"])           # declining is never rewarded


def _pool(rng, n, t_end=0.25, groups=2, per_traj=4, scale_z=1.5):
    pool = []
    for i in range(n):
        z0 = rng.standard_normal(2) * scale_z
        t, X, U, Y = simulate(z0, [(0.0, 1.0)], t_end=t_end)
        pool.append({"x_hist": X[:1].astype(np.float32), "u_hist": U[:1].astype(np.float32), "y_hist": Y[:1], "dt": DT, "y_now": Y[0],
                     "future_y": Y[1:], "group": i % groups, "traj": f"p{i // per_traj}"})
    return pool


def test_e_is_invariant_to_invertible_linear_maps_and_dead_coordinates(data):
    """Review H B1: the whitened distance gives the same E for z and for A z (A invertible, ill-conditioned), and a near-constant
    extra coordinate does not change it."""
    train, _, _ = data
    scale = E.readout_scale(train)
    base = ProjectionLinearModel(2, "pca").fit("toy", train, list(range(N)))
    rng = np.random.default_rng(3)
    Q, _ = np.linalg.qr(rng.standard_normal((2, 2)))
    A = Q @ np.diag([1.0, 0.05]) @ Q.T

    class Mapped:
        uses_readout = False

        def __init__(self, extra=False):
            self.extra = extra

        def encode(self, sid, x, u, dt):
            z = A @ np.asarray(base.encode(sid, x, u, dt), float)
            return np.r_[z, 1e-6 * rng.standard_normal()] if self.extra else z

    pool = _pool(np.random.default_rng(7), 96)
    cfg = E.EvalConfig(n_boot=100, micro_match_quantile=0.05)

    def wh(model):
        Z = np.stack([np.asarray(model.encode("toy", t.x[: E.idx(s, DT) + 1], t.u[: E.idx(s, DT) + 1], DT), float)
                      for t in train for s in (0.3, 0.6, 0.9, 1.2)])
        return {"z": E.whitener(Z, cfg.whiten_eig_floor)}

    e0 = E.eval_microstate(base, "toy", pool, scale, cfg, whiten=wh(base))
    e1 = E.eval_microstate(Mapped(), "toy", pool, scale, cfg, whiten=wh(Mapped()))
    assert abs(e0["E_ratio_latent_to_random"] - e1["E_ratio_latent_to_random"]) < 1e-6 * max(1.0, e0["E_ratio_latent_to_random"])
    e2 = E.eval_microstate(Mapped(extra=True), "toy", pool, scale, cfg, whiten=wh(Mapped(extra=True)))
    assert e2["E_ratio_latent_to_random"] < 2 * e0["E_ratio_latent_to_random"] + 1e-3
    assert e0["E_testable"] and e0["E_ratio_ci95"][0] <= e0["E_ratio_latent_to_random"] <= e0["E_ratio_ci95"][1] + 1e-12


def test_e_is_untestable_when_the_pool_is_too_sparse_for_the_latent(data):
    train, _, _ = data
    scale = E.readout_scale(train)
    rng = np.random.default_rng(4)

    class Noise8:
        uses_readout = False

        def encode(self, sid, x, u, dt):
            return rng.standard_normal(8)

    e = E.eval_microstate(Noise8(), "toy", _pool(np.random.default_rng(8), 64, t_end=0.1, groups=1), scale, E.EvalConfig(n_boot=50))
    assert e["E_testable"] is False and "not close" in e["E_untestable_reason"]


def test_closure_has_repeated_folds_and_a_trajectory_cluster_ci(data):
    train, test, _ = data
    scale = E.readout_scale(train)
    from brainir_state.harness import pca_basis
    m = ProjectionLinearModel(2, "pca").fit("toy", train, list(range(N)))
    d = E.eval_closure(m, "toy", test, pca_basis(train), scale, E.EvalConfig(n_boot=200, closure_repeats=3))
    r = d["D_y_h100ms_rff"]
    assert d["repeats"] == 3 and len(r["micro_gain_ci95"]) == 2 and r["micro_gain_ci95"][0] <= r["micro_gain_ci95"][1]
    assert r["micro_gain_ci95"][1] < 0.15, r                   # the true state is closed, CI included


def test_readout_history_control_has_a_model_for_every_step(data):
    train, _, _ = data
    m = DirectHorizonModel("readout_hist").fit("toy", train)
    assert m.hs == list(range(1, m.hs[-1] + 1)) and m.hs[-1] >= int(round(0.5 / DT))


def test_readout_scale_ignores_a_diverged_training_trajectory(data):
    train, _, _ = data
    b = traj("blow", np.array([1.0, 0.0]), [(0.0, 1.0)])
    bad = Trajectory(key="blow", system_id="toy", split="x", family="nominal", protocol=b.protocol, t=b.t, x=b.x * 1e6, u=b.u, y=b.y * 1e6)
    assert np.allclose(E.readout_scale(train), E.readout_scale(list(train) + [bad]))
