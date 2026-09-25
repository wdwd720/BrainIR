"""x-space simulation reproduces the claimed latent dynamics; determinism; conventions."""
import numpy as np
import pytest

from p3synth.diagnostics import accuracy_report, one_step_residual, protocol, reference_coords
from p3synth.systems import catalog

from conftest import sim

NAMES = [d.name for d in catalog()]


@pytest.mark.parametrize("name", NAMES)
def test_xspace_matches_latent_ode(systems, name):
    """z recorded from the neuron-level simulation == independent DOP853 solution of the claimed dc/dt = F(c, u)."""
    s = systems[name]
    rep = accuracy_report([s])[name]
    assert rep["max_abs_err_z"] < 2e-4 * rep["scale"], rep
    assert rep["max_abs_err_all_coords"] < 2e-3 * rep["scale"], rep


@pytest.mark.parametrize("name", NAMES)
def test_one_step_claimed_f(systems, name):
    """Recover f from truth-level data: every recorded step z(t) -> z(t+dt) is the flow of the documented f."""
    s = systems[name]
    rng = np.random.default_rng(3)
    th = s.model.latent.draw(2)
    z0 = s.model.latent.sample_init(rng, th)
    c0 = s.model.rest(th).copy()
    c0[: s.k] = z0
    amp = s.model.latent.channels[0][1]
    stim = [[0.0, 0.0], [0.4, 0.7 * amp], [0.9, 0.0]] if s.input_dim == 1 else \
        [[0.0, [0.0] * s.input_dim], [0.4, [0.7 * a for _, a in s.model.latent.channels]], [0.9, [0.0] * s.input_dim]]
    p = protocol(s, t_end=2.0, stimulus=stim, c0=c0, params_seed=2)
    out = s.simulate(p, noise=False)
    scale = max(1.0, np.abs(out["z"]).max())
    assert one_step_residual(s, out, p, n_check=40, rng=rng) < 1e-5 * scale


def test_rk4_convergence(systems):
    """Halving the substep reduces the error ~16x (4th order) on a nonlinear system."""
    s = systems["vanderpol"]
    p = protocol(s, t_end=2.0, stimulus=[[0.0, 0.0], [0.3, 1.0], [0.6, 0.0]])
    ref = reference_coords(s, p)[:, : s.k]
    errs = []
    h0 = s.h_max
    try:
        for h in (0.01, 0.005, 0.0025):
            s.h_max = h
            errs.append(np.abs(s.simulate(p, noise=False)["z"] - ref).max())
    finally:
        s.h_max = h0
    assert errs[0] / errs[1] > 10 and errs[1] / errs[2] > 10, errs


@pytest.mark.parametrize("name", ["hopf", "highdim_chaotic", "nuisance_rhythm", "hidden_exogenous"])
def test_deterministic_given_protocol(systems, name):
    s = systems[name]
    p = protocol(s, t_end=2.0, stimulus=[[0.0, 0.0], [0.5, 1.0], [0.7, 0.0]],
                 events=[{"kind": "kick", "t": 1.0, "delta": {"1": 0.3}}, {"kind": "silence", "t0": 1.2, "t1": 1.5, "targets": [2, 3]}])
    a, b = s.simulate(p), s.simulate(dict(p))
    for key in ("x", "y", "z", "u"):
        assert np.array_equal(a[key], b[key])
    p2 = dict(p, params_seed=1)
    c = s.simulate(p2)
    assert not np.allclose(a["x"], c["x"])


def test_noise_realisation_depends_on_protocol(systems):
    s = systems["leaky"]
    p = protocol(s, t_end=1.0)
    q = dict(p, stimulus=[[0.0, 0.0], [0.99, 0.0]])  # same dynamics, different canonical protocol
    a, b = s.simulate(p), s.simulate(q)
    assert not np.allclose(a["x"], b["x"])
    a0, b0 = s.simulate(p, noise=False), s.simulate(q, noise=False)
    assert np.allclose(a0["x"], b0["x"])


def test_output_shapes_and_observed_only(systems):
    s = systems["groupA_impl1"]            # partially observed
    out, p = sim(s, t_end=1.0)
    assert out["x"].shape == (101, len(s.observed)) and len(s.observed) < s.n
    assert out["u"].shape == (101, s.input_dim) and out["y"].shape == (101, s.readout_dim) and out["z"].shape == (101, s.k)
    assert np.allclose(out["t"], np.arange(101) * 0.01)


def test_kick_recording_convention(systems):
    s = systems["leaky"]
    out, _ = sim(s, t_end=1.0, events=[{"kind": "kick", "t": 0.5, "delta": {"0": 1.0}}], full=True)
    i = 50
    j = s.observed.index(0)
    # pre-kick sample at t; the jump appears between t and t + dt
    assert abs(out["x"][i, j] - out["x"][i - 1, j]) < 1e-3
    assert abs(out["x"][i + 1, j] - out["x"][i, j]) > 0.3


def test_stimulus_scalar_and_vector(systems):
    s = systems["gated"]
    out, _ = sim(s, t_end=1.0, stimulus=[[0.0, 0.0], [0.2, 0.5], [0.4, [1.0, 0.0]]])
    assert np.allclose(out["u"][25], 0.5 * s.model.latent.input_pattern)
    assert np.allclose(out["u"][50], [1.0, 0.0])
