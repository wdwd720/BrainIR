"""Microscopic interventions have the documented consequences; latent interventions are exact liftings."""
import numpy as np
import pytest
from scipy.integrate import solve_ivp

from p3synth.diagnostics import protocol, reference_coords

from conftest import sim


def causal(s, j):
    return bool(np.any(s.impl.D[: s.k, j] != 0))


def flow(s, z, u, T, th=None, A=None):
    th = th if th is not None else s.model.latent.draw(0)
    f = (lambda t, zz: s.model.latent.f(zz, u, None, th)) if A is None else A
    return solve_ivp(f, (0, T), z, rtol=1e-11, atol=1e-12, method="DOP853").y[:, -1]


def test_kick_moves_latent_by_D_column(systems):
    s = systems["leaky"]  # identity activations
    j = next(j for j in range(s.n) if causal(s, j))
    out0, _ = sim(s, t_end=1.0)
    out1, _ = sim(s, t_end=1.0, events=[{"kind": "kick", "t": 0.5, "delta": {str(j): 0.7}}])
    dz_pred = s.impl.D[: s.k, j] * 0.7
    assert abs(dz_pred[0]) > 1e-3
    assert np.allclose(out1["z"][51], flow(s, out0["z"][50] + dz_pred, np.zeros(1), 0.01), atol=1e-7)


@pytest.mark.parametrize("name,role", [("nuisance_ou", "nuisance"), ("output_shortcut", "readout_copy"),
                                       ("time_index", "clock"), ("stimulus_copy", "stimulus_copy"),
                                       ("parameter_trap", "parameter_report"), ("wta", "latent_carrier")])
def test_noncausal_neurons_have_no_effect_on_latent(systems, name, role):
    s = systems[name]
    js = [j for j in range(s.n) if s.impl.roles[j] == role][:3]
    assert js and not any(causal(s, j) for j in js)
    stim = s.model.latent.nominal_stimulus(3.0)
    ev = [{"kind": "kick", "t": 0.8, "delta": {str(j): 2.0 for j in js}},
          {"kind": "silence", "t0": 1.0, "t1": 2.0, "targets": js},
          {"kind": "current", "t0": 0.3, "t1": 0.6, "targets": {str(j): 50.0 for j in js}}]
    a, _ = sim(s, t_end=3.0, stimulus=stim)
    b, _ = sim(s, t_end=3.0, stimulus=stim, events=ev)
    assert np.abs(a["z"] - b["z"]).max() < 1e-10 and np.abs(a["y"] - b["y"]).max() < 1e-10
    # ... while the recorded neurons themselves are clearly perturbed
    cols = [s.observed.index(j) for j in js if j in s.observed]
    assert np.abs(a["x"][:, cols] - b["x"][:, cols]).max() > 0.05


def test_silence_semantics(systems):
    s = systems["leaky"]
    lam = s.impl.lam
    S = [j for j in range(s.n) if causal(s, j)][:5]
    stim = [[0.0, 0.0], [0.3, 1.0], [2.5, 0.0]]
    out, p = sim(s, t_end=3.0, stimulus=stim, events=[{"kind": "silence", "t0": 1.0, "t1": 2.0, "targets": S}], full=True)
    # silenced neurons relax to their baseline at rate lam (identity activation here)
    j = S[0]
    dev = out["x_full"][100:200, j] - s.impl.b[j]
    assert abs(dev[50] / dev[0] - np.exp(-lam * 0.5)) < 1e-4
    # the recorded latent during silencing is the population signal WITHOUT the silenced neurons, and follows the
    # reduced dynamics dz = (I - D_S E_S) f(z, u) - lam D_S E_S z
    DS_ES = s.impl.D[: s.k, S] @ s.impl.E[S, : s.k]
    th = s.model.latent.draw(0)
    red = lambda t, zz: (np.eye(s.k) - DS_ES) @ s.model.latent.f(zz, np.ones(1), None, th) - lam * DS_ES @ zz
    # (the sample at t0 is the pre-silencing left limit; the reduced dynamics start from z minus the silenced share)
    z_eff = out["z"][100] - s.impl.D[: s.k, S] @ (out["v_full"][100, S] - s.impl.b[S])
    assert np.allclose(out["z"][101], flow(s, z_eff, None, 0.01, A=red), atol=1e-7)
    assert np.allclose(out["z"][150], flow(s, z_eff, None, 0.5, A=red), atol=1e-6)
    # silencing causal neurons really changes the latent trajectory, also after release
    base, _ = sim(s, t_end=3.0, stimulus=stim)
    assert np.abs(base["z"][150] - out["z"][150]).max() > 1e-3
    assert np.abs(base["z"][220] - out["z"][220]).max() > 1e-4


def test_current_drives_latent_along_D(systems):
    s = systems["perfect_1d"]
    j = next(j for j in range(s.n) if causal(s, j))
    I = 5.0
    out, _ = sim(s, t_end=2.0, events=[{"kind": "current", "t0": 0.5, "t1": 1.0, "targets": {str(j): I}}])
    # perfect integrator without input: z changes only through the current, at rate D[:k, j] I
    assert np.allclose(out["z"][100] - out["z"][50], s.impl.D[: s.k, j] * I * 0.5, rtol=1e-6)
    assert np.allclose(out["z"][150], out["z"][100])


def test_edge_remove_existing_vs_absent(systems):
    s = systems["nuisance_ou"]
    posts = [i for i in range(s.n) if causal(s, i)][:6]
    pres_causal = [j for j in range(s.n) if causal(s, j) and j not in posts][:6]
    pres_nuis = [j for j in range(s.n) if s.impl.roles[j] == "nuisance"][:6]
    stim = [[0.0, 0.0], [0.3, 1.0], [0.6, 0.0]]
    base, _ = sim(s, t_end=2.0, stimulus=stim)
    real, _ = sim(s, t_end=2.0, stimulus=stim,
                  events=[{"kind": "edge_remove", "t0": 0.2, "t1": None, "edges": [[i, j] for i in posts for j in pres_causal]}])
    # nuisance neurons feed only the nuisance coordinates, which the latent never reads: removing their edges onto
    # latent neurons leaves z untouched
    none, _ = sim(s, t_end=2.0, stimulus=stim,
                  events=[{"kind": "edge_remove", "t0": 0.2, "t1": None, "edges": [[i, j] for i in posts for j in pres_nuis]}])
    assert np.abs(real["z"] - base["z"]).max() > 1e-3
    assert np.abs(none["z"] - base["z"]).max() < 1e-9


@pytest.mark.parametrize("name", ["hopf", "groupB_impl2", "duffing", "multicycle_switch", "redundant_switch"])
def test_latent_impulse_equals_lifted_micro_kick(systems, name):
    """lift_latent gives the exact microscopic change; applying it as a kick reproduces the latent intervention."""
    s = systems[name]
    lat = s.model.latent
    stim = [[0.0, 0.0]] if s.input_dim == 1 else [[0.0, [0.0] * s.input_dim]]
    dz = np.linspace(0.3, -0.2, s.k)
    ev_lat = [{"kind": "latent_impulse", "t": 0.7, "delta": {str(i): float(dz[i]) for i in range(s.k)}}]
    a, _ = sim(s, t_end=2.0, stimulus=stim, events=ev_lat)
    pre, _ = sim(s, t_end=2.0, stimulus=stim, full=True)
    dx = s.lift_latent(dz, pre["x_full"][70])
    b, _ = sim(s, t_end=2.0, stimulus=stim, events=[{"kind": "kick", "t": 0.7, "delta": {str(j): float(v) for j, v in enumerate(dx)}}])
    assert np.abs(a["z"] - b["z"]).max() < 1e-6
    # the latent moved by exactly dz (one step later it is the flow from z + dz) and nothing else moved
    assert np.abs(a["z"][71] - flow(s, pre["z"][70] + dz, np.zeros(lat.n_u), 0.01)).max() < 1e-6
    ca, cp = a["info"]["truth"]["coords"], pre["info"]["truth"]["coords"]
    if s.model.K > s.k:
        assert np.abs(ca[70:, s.k:] - cp[70:, s.k:]).max() < 1e-8


def test_latent_set_is_do_operator(systems):
    s = systems["controller"]
    out, _ = sim(s, t_end=2.0, stimulus=[[0.0, [1.0, 0.0]]], events=[{"kind": "latent_set", "t": 1.0, "values": {"1": -0.5}}])
    z = out["z"][100].copy()
    z[1] = -0.5
    assert np.abs(out["z"][101] - flow(s, z, np.array([1.0, 0.0]), 0.01)).max() < 1e-7


def test_latent_set_during_silence_is_exact(systems):
    s = systems["damped"]
    S = [j for j in range(s.n) if causal(s, j)][:4]
    out, _ = sim(s, t_end=1.5, events=[{"kind": "silence", "t0": 0.2, "t1": 1.2, "targets": S},
                                       {"kind": "latent_set", "t": 0.6, "values": {"0": 0.9, "1": 0.0}}])
    DS_ES = s.impl.D[: s.k, S] @ s.impl.E[S, : s.k]
    th = s.model.latent.draw(0)
    red = lambda t, zz: (np.eye(2) - DS_ES) @ s.model.latent.f(zz, np.zeros(1), None, th) - s.impl.lam * DS_ES @ zz
    assert np.abs(out["z"][61] - flow(s, np.array([0.9, 0.0]), None, 0.01, A=red)).max() < 1e-6


def test_weight_noise_gives_documented_closed_dynamics(systems):
    s = systems["perfect_1d"]
    stim = [[0.0, 0.0], [0.2, 1.0], [0.8, 0.0]]
    p = protocol(s, t_end=3.0, stimulus=stim, weight_noise={"sd": 0.1, "seed": 3})
    out = s.simulate(p, noise=False)
    ref = reference_coords(s, p)  # integrates A F(c) - lam (I - A) c
    assert np.abs(out["z"] - ref[:, : s.k]).max() < 1e-8
    # the perfect integrator is no longer perfect: z drifts after the input is switched off
    clean, _ = sim(s, t_end=3.0, stimulus=stim)
    assert abs(out["z"][-1, 0] - out["z"][90, 0]) > 1e-3 and abs(clean["z"][-1, 0] - clean["z"][90, 0]) < 1e-10


def test_kick_on_saturating_neuron_is_clipped(systems):
    s = systems["hopf"]  # logistic activations
    out, _ = sim(s, t_end=1.0, events=[{"kind": "kick", "t": 0.5, "delta": {"0": 100.0}}], full=True)
    assert np.isfinite(out["x_full"]).all() and out["x_full"][51, 0] <= s.impl.phi.scale[0]
