"""Each family's latent dynamics are what the truth claims (qualitative signature + recovery of k and f)."""
import numpy as np
import pytest
from scipy.linalg import logm

from conftest import sim, with_z

TWO_PI = 2 * np.pi


def zero_cross_freq(y, dt):
    s = np.sign(y - y.mean())
    idx = np.flatnonzero((s[:-1] < 0) & (s[1:] >= 0))
    return (len(idx) - 1) / ((idx[-1] - idx[0]) * dt)


def rank(M, rel=1e-7):
    sv = np.linalg.svd(M - M.mean(0), compute_uv=False)
    return int((sv > rel * sv[0]).sum())


@pytest.mark.parametrize("name", ["linear_k1", "linear_k3", "linear_k6"])
def test_linear_recover_k_and_A(systems, name):
    s = systems[name]
    rng = np.random.default_rng(0)
    th = s.model.latent.draw(0)
    Z0, Z1, U, V = [], [], [], []
    for r in range(6):
        z0 = rng.standard_normal(s.k)
        stim = [[0.0, [0.0] * s.input_dim]] + [[float(t), list(rng.uniform(-1, 1, s.input_dim))] for t in (0.5, 1.2, 2.0)]
        out, _ = sim(s, t_end=3.0, c0=with_z(s, z0), stimulus=stim, full=True)
        Z0.append(out["z"][:-1]); Z1.append(out["z"][1:]); U.append(out["u"][:-1]); V.append(out["v_full"])
    Z0, Z1, U = map(np.concatenate, (Z0, Z1, U))
    # k = rank of the noise-free population activity
    assert rank(np.concatenate(V)) == s.k
    # f: least-squares discrete map, converted back to continuous time
    X = np.hstack([Z0, U])
    M = np.linalg.lstsq(X, Z1, rcond=None)[0].T
    A_est = np.real(logm(M[:, : s.k])) / 0.01
    assert np.abs(A_est - th["_A"]).max() < 1e-3 * max(1, np.abs(th["_A"]).max())
    assert np.all(np.linalg.eigvals(th["_A"]).real < 0)


def test_harmonic_energy_and_frequency(systems):
    s = systems["harmonic"]
    out, _ = sim(s, t_end=6.0, c0=with_z(s, [1.0, 0.0]))
    E = (out["z"] ** 2).sum(1)
    assert np.abs(E - 1).max() < 1e-6
    assert abs(zero_cross_freq(out["z"][:, 0], 0.01) - s.model.latent.draw(0)["f0"]) < 0.02


def test_duffing_frequency_depends_on_amplitude(systems):
    s = systems["duffing"]
    f_small = zero_cross_freq(sim(s, t_end=8.0, c0=with_z(s, [0.1, 0.0]))[0]["z"][:, 0], 0.01)
    f_large = zero_cross_freq(sim(s, t_end=8.0, c0=with_z(s, [1.5, 0.0]))[0]["z"][:, 0], 0.01)
    assert f_large > 1.3 * f_small
    E = lambda z, th: z[:, 0] ** 2 + th["beta"] * z[:, 0] ** 4 / 2 + z[:, 1] ** 2
    out, _ = sim(s, t_end=4.0, c0=with_z(s, [1.2, 0.3]))
    e = E(out["z"], s.model.latent.draw(0))
    assert np.abs(e - e[0]).max() < 1e-5 * e[0]


def test_damped_decay_rate(systems):
    s = systems["damped"]
    th = s.model.latent.draw(0)
    out, _ = sim(s, t_end=4.0, c0=with_z(s, [1.0, 0.0]))
    t = out["t"]
    E = (out["z"] ** 2).sum(1)
    slope = np.polyfit(t, np.log(E), 1)[0]
    w = TWO_PI * th["f0"]
    assert abs(slope + 2 * th["zeta"] * w) < 0.1 * 2 * th["zeta"] * w


@pytest.mark.parametrize("name", ["hopf", "vanderpol", "groupA_impl0"])
def test_limit_cycle_attracts(systems, name):
    s = systems[name]
    amps = []
    for z0 in ([0.15, 0.0], [1.6, 0.0]):
        out, _ = sim(s, t_end=8.0, c0=with_z(s, z0))
        amps.append(np.abs(out["z"][-150:, 0]).max())
    assert abs(amps[0] - amps[1]) < 0.02 * amps[1] and amps[1] > 0.5


def test_bistable_switch(systems):
    s = systems["bistable_1d"]
    out, _ = sim(s, t_end=3.0)
    assert abs(out["z"][-1, 0] + 1) < 1e-3                     # rest well
    out, _ = sim(s, t_end=3.0, stimulus=[[0.0, 0.0], [0.5, 1.0], [0.9, 0.0]])
    assert abs(out["z"][-1, 0] - 1) < 1e-3                     # switched and stays
    out, _ = sim(s, t_end=3.0, stimulus=[[0.0, 0.0], [0.5, 0.2], [0.9, 0.0]])
    assert abs(out["z"][-1, 0] + 1) < 1e-3                     # sub-threshold input: back to the old well


def test_toggle_two_stable_states(systems):
    s = systems["toggle"]
    a, _ = sim(s, t_end=3.0)
    b, _ = sim(s, t_end=3.0, stimulus=[[0.0, 0.0], [0.5, -1.0], [0.8, 0.0]])
    assert a["y"][-1, 0] > 0.9 and b["y"][-1, 0] < -0.9
    assert np.abs(np.diff(b["z"][-50:], axis=0)).max() < 1e-4


def test_leaky_time_constant(systems):
    s = systems["leaky"]
    th = s.model.latent.draw(0)
    out, _ = sim(s, t_end=2.0, c0=with_z(s, [1.0]))
    i = int(round(th["tau"] / 0.01))
    assert abs(out["z"][i, 0] - np.exp(-i * 0.01 / th["tau"])) < 1e-6


@pytest.mark.parametrize("name", ["perfect_1d", "perfect_2d"])
def test_perfect_integrator(systems, name):
    s = systems[name]
    th = s.model.latent.draw(0)
    u = [0.7] * s.input_dim
    out, _ = sim(s, t_end=3.0, stimulus=[[0.0, [0.0] * s.input_dim], [0.5, u], [1.5, [0.0] * s.input_dim]])
    expect = th["gain"] * s.model.latent.M @ np.array(u) * 1.0
    assert np.allclose(out["z"][-1], expect, atol=1e-9)
    assert np.abs(out["z"][150:] - out["z"][-1]).max() < 1e-12


def test_gated_integrator(systems):
    s = systems["gated"]
    closed, _ = sim(s, t_end=2.0, stimulus=[[0.0, [0.0, 0.0]], [0.5, [1.0, 0.0]], [1.5, [0.0, 0.0]]])
    opened, _ = sim(s, t_end=2.0, stimulus=[[0.0, [0.0, 0.0]], [0.5, [1.0, 1.0]], [1.5, [0.0, 0.0]]])
    assert abs(closed["z"][-1, 0]) < 0.01 and opened["z"][-1, 0] > 0.8


def test_winner_take_all(systems):
    s = systems["wta"]
    null, _ = sim(s, t_end=3.0)
    assert null["z"][-1].max() < 0.1
    out, _ = sim(s, t_end=4.0, stimulus=[[0.0, 0.0], [0.5, [0.3, 1.0, 0.6]], [1.0, 0.0]])
    zf = out["z"][-1]
    assert zf.argmax() == 1 and zf[1] > 0.8 and np.sort(zf)[-2] < 0.1


def test_feedback_controller_rejects_disturbance(systems):
    s = systems["controller"]
    out, _ = sim(s, t_end=6.0, stimulus=[[0.0, [0.0, 0.0]], [0.5, [1.0, 0.0]], [2.5, [1.0, 1.5]]])
    assert abs(out["y"][240, 0] - 1) < 0.02
    assert np.abs(out["y"][260:300, 0] - 1).max() > 0.05     # transient error after the disturbance ...
    assert abs(out["y"][-1, 0] - 1) < 0.01                  # ... removed by integral action
    assert abs(out["z"][-1, 1] - (1.0 - 1.5)) < 0.01         # the integral state holds the compensation q = r - d


def test_slow_fast_excitable(systems):
    s = systems["slow_fast"]
    th = s.model.latent.draw(0)
    rest, _ = sim(s, t_end=2.0)
    assert np.abs(rest["z"][-1] - rest["z"][0]).max() < 1e-6
    big, _ = sim(s, t_end=2.0, stimulus=[[0.0, 0.0], [0.5, 1.0], [0.56, 0.0]])
    small, _ = sim(s, t_end=2.0, stimulus=[[0.0, 0.0], [0.5, 0.1], [0.56, 0.0]])
    assert big["z"][:, 0].max() > 1.0 and small["z"][:, 0].max() < 0.0
    assert th["tau_s"] / th["tau_f"] > 10


def test_chaotic_rnn_is_high_dimensional(systems):
    s = systems["highdim_chaotic"]
    rng = np.random.default_rng(1)
    z0 = rng.standard_normal(s.k)
    a, _ = sim(s, t_end=20.0, c0=z0)
    b, _ = sim(s, t_end=20.0, c0=z0 + 1e-6 * rng.standard_normal(s.k))
    d = np.linalg.norm(a["z"] - b["z"], axis=1)
    assert d[-1] > 1e3 * d[0] and d[-1] > 1.0            # sensitive dependence
    ev = np.linalg.eigvalsh(np.cov(a["z"][200:].T))[::-1]
    assert ev.sum() ** 2 / (ev ** 2).sum() > 5
    assert np.searchsorted(np.cumsum(ev) / ev.sum(), 0.9) + 1 > 10   # > 10 PCs for 90% variance (k <= 6 elsewhere)


def test_highdim_linear_participation(systems):
    s = systems["highdim_linear"]
    out, _ = sim(s, t_end=20.0, noise=True)
    ev = np.linalg.eigvalsh(np.cov(out["z"][200:].T))
    assert ev.sum() ** 2 / (ev ** 2).sum() > 8
    assert np.searchsorted(np.cumsum(ev[::-1]) / ev.sum(), 0.9) + 1 > 15   # >15 PCs for 90% variance


def test_exogenous_input_is_needed(systems):
    s = systems["hidden_exogenous"]
    from p3synth.diagnostics import protocol, one_step_residual
    p = protocol(s, t_end=3.0)
    noisy = s.simulate(p)                     # exo on (and small process noise)
    exo = noisy["info"]["truth"]["exo"]
    assert exo.std() > 0.5
    # the claimed f without e(t) does not close the dynamics ...
    assert one_step_residual(s, noisy, p) > 5e-3
    # ... with e(t) known, it does (up to the small process noise)
    th = s.model.latent.draw(0)
    from scipy.integrate import solve_ivp
    errs = []
    for i in range(0, 290, 7):
        z1 = solve_ivp(lambda t, z: s.model.latent.f(z, noisy["u"][i], exo[i], th), (0, 0.01), noisy["z"][i], rtol=1e-10).y[:, -1]
        errs.append(np.abs(z1 - noisy["z"][i + 1]).max())
    errs0 = []
    for i in range(0, 290, 7):
        z1 = solve_ivp(lambda t, z: s.model.latent.f(z, noisy["u"][i], None, th), (0, 0.01), noisy["z"][i], rtol=1e-10).y[:, -1]
        errs0.append(np.abs(z1 - noisy["z"][i + 1]).max())
    assert np.median(errs) < 0.3 * np.median(errs0)
