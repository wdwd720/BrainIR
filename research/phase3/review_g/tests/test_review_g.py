"""Review G traps (G1-G10): for every trap
  * claim  : the system behaves as its truth says (latent dynamics, invariances, causal structure);
  * fooled : a simple representation learner (PCA, ridge, linear / AR models, Gaussian SDE fits, context models) is
             fooled in the intended way;
  * truth  : the trap is not trivially unsolvable: the truth-level latent (plus documented context where relevant)
             predicts what the learner gets wrong.
Plus catalogue / truth / accuracy checks and a suite build through the unchanged suite builder."""
import json
import math
import os
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from p3synth.diagnostics import accuracy_report, one_step_residual, protocol
from p3synth.review_g import (TRAPS_G, SyncPair, build_review_g, build_review_g_suite, review_g_catalog)
from p3synth.suite import random_stimulus, scaled_nominal

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.data import Dataset  # noqa: E402

NAMES = [d.name for d in review_g_catalog()]
DT = 0.01


SEED = int(os.environ.get("REVIEW_G_SEED", "0"))     # robustness runs: REVIEW_G_SEED=1 uv run pytest tests/test_review_g.py


@pytest.fixture(scope="module")
def G():
    return {s.meta["name"]: s for s in build_review_g(SEED, "dev")}


# ------------------------------------------------------------------------------------------------ helpers
def coords(s, z, ps=0):
    th = s.model.latent.draw(ps)
    c = s.model.rest(th).copy()
    c[: s.k] = z
    return c


def run(s, stimulus=None, ns=0, events=(), z0=None, t_end=4.0, ps=0, noise=True, full=False, c0=None):
    if stimulus is None:
        stimulus = [[0.0, 0.0 if s.input_dim == 1 else [0.0] * s.input_dim]]
    if c0 is None and z0 is not None:
        c0 = coords(s, np.asarray(z0, float), ps)
    p = protocol(s, t_end=t_end, stimulus=stimulus, events=list(events), params_seed=ps, c0=c0)
    p["noise_seed"] = int(ns)
    return s.simulate(p, noise=noise, full=full)


def r2(X, Y):
    X1 = np.hstack([X, np.ones((len(X), 1))])
    W = np.linalg.lstsq(X1, Y, rcond=None)[0]
    return 1 - (Y - X1 @ W).var(0).sum() / Y.var(0).sum()


def fit(X, Y):
    return np.linalg.lstsq(np.hstack([X, np.ones((len(X), 1))]), Y, rcond=None)[0]


def pred(W, X):
    return np.hstack([X, np.ones((len(X), 1))]) @ W


def r2p(Y, P):
    Y, P = np.asarray(Y), np.asarray(P)
    return 1 - ((Y - P) ** 2).sum() / ((Y - Y.mean(0)) ** 2).sum()


def pca(X):
    mu = X.mean(0)
    _, S, Vt = np.linalg.svd(X - mu, full_matrices=False)
    return mu, Vt, S ** 2 / (S ** 2).sum()


def kick_event(t, dv):
    return {"kind": "kick", "t": t, "delta": {str(int(j)): float(v) for j, v in dv.items() if abs(v) > 1e-12}}


def lift_kick(s, t, dz, x_full):
    """Micro kick (all neurons, x units) that moves the latent by dz (exact lifting, as a public kick event)."""
    dx = s.lift_latent(dz, x_full)
    return kick_event(t, dict(enumerate(dx)))


def selective(s, coord):
    """Latent neurons whose embedding row is non-zero only on latent coordinate `coord`."""
    E = s.impl.E
    return [j for j in range(s.n) if s.impl.roles[j] == "latent" and E[j, coord] != 0
            and np.count_nonzero(E[j]) == 1]


def phase_freq(z, sl=slice(None)):
    ph = np.unwrap(np.arctan2(z[sl, 1], z[sl, 0]))
    return np.diff(ph).mean() / DT / (2 * math.pi)


def random_pulses(rng, n_u=1, amp=1.5, t_end=4.0):
    out = [[0.0, 0.0 if n_u == 1 else [0.0] * n_u]]
    t = 0.1
    while t < t_end - 0.2:
        v = round(float(rng.uniform(-amp, amp)), 3)
        out.append([round(t, 2), v if n_u == 1 else [v] + [0.0] * (n_u - 1)])
        t += float(rng.uniform(0.1, 0.5))
    return out


def lin_model(trajs, enc, n_lags=1):
    """Linear state model p_{t+1} = A [p_t..p_{t-L+1}] + B u_t + c on encoded trajectories, and readout y = C p + d."""
    P = [enc(o["x"]) for o in trajs]
    L = n_lags

    def emb(p):
        return np.hstack([p[L - 1 - l: len(p) - l] for l in range(L)])
    Xa = np.concatenate([np.hstack([emb(p)[:-1], o["u"][L - 1:-1]]) for p, o in zip(P, trajs)])
    Ya = np.concatenate([p[L:] for p in P])
    W = fit(Xa, Ya)
    Wy = fit(np.concatenate([emb(p) for p in P]), np.concatenate([o["y"][L - 1:] for o in trajs]))
    d = P[0].shape[1]

    def rollout(o, i0, n):
        st = emb(enc(o["x"][: i0 + 1]))[-1]
        out = []
        for i in range(n):
            out.append(pred(Wy, st[None])[0, 0])
            nxt = pred(W, np.concatenate([st, o["u"][i0 + i]])[None])[0]
            st = np.concatenate([nxt, st[:-d]]) if L > 1 else nxt
        return np.array(out)
    return W, rollout


# ------------------------------------------------------------------------------------------------ catalogue
def test_catalogue_labels_and_dimensions(G):
    defs = review_g_catalog()
    assert 8 <= len(defs) <= 12
    assert [d.trap for d in defs] == [f"G{i}" for i in range(1, len(defs) + 1)]
    assert set(TRAPS_G) == {d.trap for d in defs}
    for d in defs:
        s = G[d.name]
        t = json.loads(json.dumps(s.truth()))
        assert d.notes.startswith(d.trap + " ") and t["notes"]
        assert t["trap"] == d.trap and t["f"] and t["g"]
        if d.trap == "G10":
            assert t["k"] == "none" and t["K_total_coordinates"] >= 30
        else:
            assert isinstance(t["k"], int) and 1 <= t["k"] <= 9
        assert len(t["neuron_roles"]) == s.n


@pytest.mark.parametrize("name", NAMES)
def test_xspace_matches_claimed_latent_ode(G, name):
    """Neuron-level simulation == independent DOP853 solution of the claimed dc/dt = F(c, u) (exo = 0)."""
    s = G[name]
    rep = accuracy_report([s])[name]
    assert rep["max_abs_err_z"] < 2e-4 * rep["scale"], rep
    assert rep["max_abs_err_all_coords"] < 2e-3 * rep["scale"], rep


@pytest.mark.parametrize("name", NAMES)
def test_one_step_flow_of_documented_f(G, name):
    s = G[name]
    rng = np.random.default_rng(3)
    th = s.model.latent.draw(2)
    z0 = s.model.latent.sample_init(rng, th)
    amp = s.model.latent.channels[0][1]
    stim = [[0.0, 0.0], [0.4, 0.7 * amp], [0.9, 0.0]] if s.input_dim == 1 else \
        [[0.0, [0.0] * s.input_dim], [0.4, [0.7 * a for _, a in s.model.latent.channels]], [0.9, [0.0] * s.input_dim]]
    p = protocol(s, t_end=2.0, stimulus=stim, c0=coords(s, z0, 2), params_seed=2)
    out = s.simulate(p, noise=False)
    assert one_step_residual(s, out, p, n_check=40, rng=rng) < 1e-5 * max(1.0, np.abs(out["z"]).max())


# ------------------------------------------------------------------------------------------------ G1
def _g1_train(s, n=8, seed=0, noise=True):
    lat, rng = s.model.latent, np.random.default_rng(seed)
    th = lat.draw(0)
    return [run(s, stimulus=random_pulses(rng), ns=100 + i, z0=lat.sample_init(rng, th), noise=noise) for i in range(n)]


def test_G1_claim_synchronous_manifold_invariant(G):
    s = G["g1_sync_pair"]
    # any input, any synchronous start: the transverse mode stays exactly zero
    for o in _g1_train(s, n=6, noise=False):
        assert np.abs(o["z"][:, 2:]).max() < 1e-9 and np.abs(o["z"][:, :2]).max() > 0.2
    # a single-neuron kick breaks the symmetry
    j = int(np.argmax(np.linalg.norm(s.impl.D[2:], axis=0)))
    o = run(s, z0=[1.0, 0, 0, 0], events=[kick_event(1.0, {j: 1.0})], noise=False, t_end=2.0)
    assert np.abs(o["z"][:101, 2:]).max() < 1e-9 and np.linalg.norm(o["z"][102, 2:]) > 0.05
    # near anti-phase: the transverse mode relaxes slowly and cancels y
    z_anti = SyncPair.from_phases(1.0, 0.0, 1.0, 0.9 * math.pi)
    o = run(s, z0=z_anti, noise=False, t_end=4.0)
    d = np.linalg.norm(o["z"][:, 2:], axis=1)
    assert d[100] > 0.7 * d[0]                                     # still > 70% after 1 s (slow, ~2K)
    assert np.abs(o["y"][:100]).max() < 0.8                        # vs amplitude 2 when synchronous


def test_G1_fools_variance_based_encoder(G):
    s = G["g1_sync_pair"]
    outs = _g1_train(s)
    X = np.concatenate([o["x"] for o in outs])
    mu, Vt, var = pca(X)
    assert var[:2].sum() > 0.98 and var[2] < 0.002                 # activity looks 2-D (k = 4); the rest is noise floor
    V = Vt[:2].T
    obs, E, b = s.observed, s.impl.E, s.impl.b
    # two states with IDENTICAL 2-PC encoding: one synchronous, one near anti-phase
    z_anti = SyncPair.from_phases(1.0, 0.0, 1.0, 0.9 * math.pi)
    enc = V.T @ (b[obs] + E[obs][:, :4] @ z_anti - mu)
    s_star = np.linalg.solve(V.T @ E[obs][:, :2], enc - V.T @ (b[obs] - mu))
    z_sync = np.concatenate([s_star, [0.0, 0.0]])
    assert np.allclose(V.T @ (b[obs] + E[obs][:, :4] @ z_sync - mu), enc, atol=1e-9)
    a = run(s, z0=z_sync, noise=False, t_end=3.0)
    c = run(s, z0=z_anti, noise=False, t_end=3.0)
    w = slice(50, 300)
    # ... but different futures: any dynamics on this encoder violates Markov closure
    assert np.sqrt(((a["y"][w] - c["y"][w]) ** 2).mean()) > 0.3 * a["y"][w].std()


def test_G1_truth_latent_predicts(G):
    """A cubic polynomial model fitted on the 4-D truth latent (noise-free trajectories from synchronous and
    desynchronised initial states, with inputs) predicts a new near-anti-phase trajectory: the truth latent is a closed,
    learnable description. (The train split itself only contains small transverse excursions from single kicks.)"""
    s = G["g1_sync_pair"]
    rng = np.random.default_rng(1)
    lat, th = s.model.latent, s.model.latent.draw(0)
    trajs = []
    for i in range(12):
        trajs.append(run(s, stimulus=random_pulses(rng), z0=lat.sample_init(rng, th, heldout=i % 2 == 1), noise=False))

    def lib(Z, U):
        cols = [np.ones(len(Z))] + [Z[:, i] for i in range(4)]
        cols += [Z[:, i] * Z[:, j] for i in range(4) for j in range(i, 4)]
        cols += [Z[:, i] * Z[:, j] * Z[:, k] for i in range(4) for j in range(i, 4) for k in range(j, 4)]
        return np.column_stack(cols + [U[:, 0]])
    Xs, Ys = [], []
    for o in trajs:
        z, u = o["z"], o["u"]
        dz = (z[2:] - z[:-2]) / (2 * DT)
        ok = np.abs(np.diff(u[:, 0]))[1:] == 0                       # skip samples straddling input switches
        ok &= np.abs(np.diff(u[:, 0]))[:-1] == 0
        Xs.append(lib(z[1:-1], u[1:-1])[ok])
        Ys.append(dz[ok])
    Wf = np.linalg.lstsq(np.concatenate(Xs), np.concatenate(Ys), rcond=None)[0]
    z_anti = SyncPair.from_phases(1.0, 0.0, 1.0, 0.9 * math.pi)
    truth = run(s, z0=z_anti, noise=False, t_end=3.0)
    z = z_anti.copy()
    fz = lambda z: lib(z[None], np.zeros((1, 1)))[0] @ Wf
    ys = []
    for i in range(len(truth["y"])):
        ys.append(2 * z[0])
        for _ in range(2):
            h = DT / 2
            k1 = fz(z); k2 = fz(z + h / 2 * k1); k3 = fz(z + h / 2 * k2); k4 = fz(z + h * k3)
            z = z + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
    assert r2p(truth["y"][:, 0], np.array(ys)) > 0.95


# ------------------------------------------------------------------------------------------------ G2
def _g2_trials(s, n=24, seed=1, noise=False):
    lat, rng = s.model.latent, np.random.default_rng(seed)
    outs = []
    for i in range(n):
        ps = i % 8
        th = lat.draw(ps)
        c0 = np.concatenate([lat.sample_init(rng, th), [th["f0"]]])
        outs.append(run(s, c0=c0, ps=ps, ns=i, noise=noise))
    return outs


def test_G2_claim_slow_state_sets_frequency(G):
    s = G["g2_slow_state"]
    th = s.model.latent.draw(0)
    for sv in (-1.0, 0.0, 1.0):
        o = run(s, z0=[1.0, 0.0, sv], noise=False)
        assert abs(o["z"][-1, 2] / sv - 1) < 0.15 if sv else abs(o["z"][-1, 2]) < 1e-9     # quasi-constant over 4 s
        f_pred = th["f0"] * (1 + th["delta"] * math.tanh(o["z"][:, 2].mean()))
        assert abs(phase_freq(o["z"], slice(50, None)) / f_pred - 1) < 0.02
    # parameter-report neurons are not causal
    par = [j for j in range(s.n) if s.impl.roles[j] == "parameter_report"]
    a = run(s, z0=[1.0, 0, 0.5], events=[kick_event(1.5, {j: 2.0 for j in par})], noise=False)
    b = run(s, z0=[1.0, 0, 0.5], noise=False)
    assert np.abs(a["y"] - b["y"]).max() < 1e-12 and np.abs(a["x"] - b["x"]).max() > 0.5


def test_G2_fools_parameter_context_learner(G):
    s = G["g2_slow_state"]
    outs = _g2_trials(s)
    sn = [s.observed.index(j) for j in selective(s, 2) if j in s.observed]
    pn = [s.observed.index(j) for j in s.observed if s.impl.roles[j] == "parameter_report"]
    assert len(sn) >= 3 and len(pn) == 4
    F = np.array([phase_freq(o["z"], slice(50, None)) for o in outs])
    means = {}
    for name, cols in (("slow_state", sn), ("param", pn)):
        within = np.mean([o["x"][:, cols].std(0).mean() for o in outs])
        means[name] = np.array([o["x"][:, cols].mean(0) for o in outs])
        assert within < 0.1 * means[name].std(0).mean()            # both flat within a trial: they look like parameters
        assert r2(means[name], F) > 0.15                           # both predict part of the trial's frequency
    both = r2(np.hstack([means["slow_state"], means["param"]]), F)
    assert both > 0.95 and both - max(r2(m, F) for m in means.values()) > 0.15    # ... and both are needed
    # the per-trial-context view: frequency fixed from the pre-kick part of the trial
    J = selective(s, 2)
    dv = np.linalg.lstsq(s.impl.D[:3][:, J], np.array([0.0, 0.0, 1.2]), rcond=None)[0]
    z0 = [1.0, 0.0, 0.0]
    a = run(s, z0=z0, events=[kick_event(1.5, dict(zip(J, dv)))], noise=False)
    f_ctx = phase_freq(a["z"], slice(20, 150))
    f_late = phase_freq(a["z"], slice(300, None))
    assert abs(f_late / f_ctx - 1) > 0.15                          # context model is wrong until the end of the trial


def test_G2_truth_latent_predicts(G):
    s = G["g2_slow_state"]
    th = s.model.latent.draw(0)
    J = selective(s, 2)
    for target in (-1.0, 1.2):
        dv = np.linalg.lstsq(s.impl.D[:3][:, J], np.array([0.0, 0.0, target]), rcond=None)[0]
        a = run(s, z0=[1.0, 0.0, 0.0], events=[kick_event(1.5, dict(zip(J, dv)))], noise=False)
        s_post = a["z"][200:, 2].mean()
        f_pred = th["f0"] * (1 + th["delta"] * math.tanh(s_post))
        assert abs(phase_freq(a["z"], slice(200, None)) / f_pred - 1) < 0.02


# ------------------------------------------------------------------------------------------------ G3
def _g3_contexts(s, n=12, seed=0):
    rng = np.random.default_rng(seed)
    tr = {1.0: [], -1.0: []}
    for i in range(n):
        m = 1.0 if i % 2 == 0 else -1.0
        tr[m].append(run(s, stimulus=random_pulses(rng, n_u=2), ns=i, z0=[0.0, m]))
    return tr


def test_G3_claim_same_output_law_flipped_code(G):
    s = G["g3_sign_flip"]
    stim = random_pulses(np.random.default_rng(5), n_u=2)
    a = run(s, stimulus=stim, z0=[0.0, 1.0], noise=False)
    b = run(s, stimulus=stim, z0=[0.0, -1.0], noise=False)
    assert np.abs(a["y"] - b["y"]).max() < 1e-9                   # identical output law in both contexts ...
    assert np.abs(a["x"] - b["x"]).max() > 0.5                    # ... different neural states
    th = s.model.latent.draw(0)
    y, u = a["y"][:, 0], a["u"][:, 0]
    dy = np.diff(y) / DT
    assert r2p(dy, (-y[:-1] + th["gain"] * u[:-1]) / th["tau"]) > 0.98
    tr = _g3_contexts(s)
    X = {m: np.concatenate([o["x"] for o in tr[m]]) for m in tr}
    Y = {m: np.concatenate([o["y"][:, 0] for o in tr[m]]) for m in tr}
    cp = np.array([np.corrcoef(X[1.0][:, j], Y[1.0])[0, 1] for j in range(X[1.0].shape[1])])
    cn = np.array([np.corrcoef(X[-1.0][:, j], Y[-1.0])[0, 1] for j in range(X[1.0].shape[1])])
    tuned = np.abs(cp) > 0.5
    assert tuned.sum() > 20 and np.mean(np.sign(cp[tuned]) != np.sign(cn[tuned])) > 0.95


def test_G3_fools_linear_readout_and_fixed_sign_attribution(G):
    s = G["g3_sign_flip"]
    tr = _g3_contexts(s)
    h = 4
    Xtr = np.concatenate([o["x"] for m in tr for o in tr[m][:h]])
    Ytr = np.concatenate([o["y"][:, 0] for m in tr for o in tr[m][:h]])
    Xte = np.concatenate([o["x"] for m in tr for o in tr[m][h:]])
    Yte = np.concatenate([o["y"][:, 0] for m in tr for o in tr[m][h:]])
    assert r2p(Yte, pred(fit(Xtr, Ytr), Xte)) < 0.2                # pooled linear readout fails
    within = fit(np.concatenate([o["x"] for o in tr[1.0][:h]]), np.concatenate([o["y"][:, 0] for o in tr[1.0][:h]]))
    Xw = np.concatenate([o["x"] for o in tr[1.0][h:]])
    assert r2p(np.concatenate([o["y"][:, 0] for o in tr[1.0][h:]]), pred(within, Xw)) > 0.95
    # the same micro kick has opposite effects on y in the two contexts
    full = run(s, z0=[0.0, 1.0], noise=False, full=True, t_end=1.0)
    ev = lift_kick(s, 1.0, [0.3, 0.0], full["x_full"][50])
    eff = {}
    for m in (1.0, -1.0):
        a = run(s, z0=[0.0, m], events=[ev], noise=False, t_end=2.0)
        b = run(s, z0=[0.0, m], noise=False, t_end=2.0)
        eff[m] = (a["y"] - b["y"])[102, 0]
    assert eff[1.0] > 0.2 and eff[-1.0] < -0.2                    # a fixed-sign causal model is wrong in one context
    # the ridge readout learned in context +1 predicts the wrong sign in context -1
    a = run(s, z0=[0.0, -1.0], events=[ev], noise=False, t_end=2.0)
    b = run(s, z0=[0.0, -1.0], noise=False, t_end=2.0)
    d_pred = (pred(within, a["x"][102:103]) - pred(within, b["x"][102:103]))[0]
    assert np.sign(d_pred) != np.sign(eff[-1.0])


def test_G3_truth_latent_predicts(G):
    s = G["g3_sign_flip"]
    tr = _g3_contexts(s)
    Z = np.concatenate([o["z"] for m in tr for o in tr[m]])
    Y = np.concatenate([o["y"][:, 0] for m in tr for o in tr[m]])
    assert np.abs(Y - Z[:, 0] * Z[:, 1]).max() < 1e-12
    assert r2(np.column_stack([Z, Z[:, 0] * Z[:, 1]]), Y) > 0.999


# ------------------------------------------------------------------------------------------------ G4
def _g4_train(s, n=10, seed=0):
    lat, rng = s.model.latent, np.random.default_rng(seed)
    th = lat.draw(0)
    return [run(s, stimulus=random_pulses(rng), ns=i, z0=lat.sample_init(rng, th)) for i in range(n)]


def _g4_stage_kick(s, stage, size=0.8):
    J = selective(s, stage)
    dv = np.linalg.lstsq(s.impl.D[:, J], np.eye(s.k)[stage] * size, rcond=None)[0]
    ev = kick_event(1.0, dict(zip(J, dv)))
    a = run(s, events=[ev], noise=False, t_end=2.5)
    b = run(s, noise=False, t_end=2.5)
    return a, b


def test_G4_claim_relay_kicks_return_as_delayed_echoes(G):
    s = G["g4_delay_relay"]
    M = s.model.latent.M
    lat_peak = {}
    for stage in (1, M):
        a, b = _g4_stage_kick(s, stage)
        dz = a["z"] - b["z"]
        others = np.delete(dz[102], stage)
        assert dz[102, stage] > 0.4 and np.abs(others).max() < 0.6 * dz[102, stage]   # mainly moves that relay stage
        lat_peak[stage] = np.abs(dz[101:, 0]).argmax() * DT
    assert lat_peak[1] > lat_peak[M] + 0.2                                    # earlier stage -> later echo


def test_G4_fools_low_variance_dimension_and_reduced_model(G):
    s = G["g4_delay_relay"]
    outs = _g4_train(s)
    mu, Vt, var = pca(np.concatenate([o["x"] for o in outs]))
    assert var[:3].sum() > 0.99 and s.k == 9                                  # 3 PCs, 9 true coordinates
    V = Vt[:3].T
    _, roll = lin_model(outs, lambda x: (x - mu) @ V)
    a, b = _g4_stage_kick(s, 1)
    true = (a["y"] - b["y"])[101:201, 0]
    predicted = roll(a, 101, 100) - roll(b, 101, 100)
    peak = np.abs(true).max()
    assert np.abs(true[:20]).max() < 0.5 * peak                    # truth: little happens for 0.2 s, then the echo ...
    assert np.abs(predicted[:20]).max() > 0.9 * peak               # ... the reduced model responds at once
    assert abs(np.abs(predicted).argmax() - np.abs(true).argmax()) * DT > 0.3  # the echo arrives at the wrong time


def test_G4_truth_latent_predicts(G):
    s = G["g4_delay_relay"]
    outs = _g4_train(s)
    Xa = np.concatenate([np.hstack([o["z"][:-1], o["u"][:-1]]) for o in outs])
    Ya = np.concatenate([o["z"][1:] for o in outs])
    W = fit(Xa, Ya)
    a, b = _g4_stage_kick(s, 1)
    za, zb = a["z"][101].copy(), b["z"][101].copy()
    pa, pb = [], []
    for i in range(100):
        pa.append(za[0]); pb.append(zb[0])
        za = pred(W, np.concatenate([za, a["u"][101 + i]])[None])[0]
        zb = pred(W, np.concatenate([zb, b["u"][101 + i]])[None])[0]
    true = (a["y"] - b["y"])[101:201, 0]
    assert r2p(true, np.array(pa) - np.array(pb)) > 0.95


# ------------------------------------------------------------------------------------------------ G5
def _g5_kick_pair(s, ns=999):
    twin = run(s, ns=ns, t_end=6.0, full=True)                     # shares the noise (and the drive) with the kicked run
    ev = lift_kick(s, 2.0, [0.8, 0.0], twin["x_full"][200])        # exact lift at the actual pre-kick microstate
    return run(s, events=[ev], ns=ns, t_end=6.0), twin


def test_G5_claim_hidden_periodic_drive(G):
    s = G["g5_exo_rhythm"]
    th = s.model.latent.draw(0)
    runs = [run(s, ns=i, t_end=6.0) for i in range(1, 7)]
    o1, t = runs[0], runs[0]["t"]
    e1 = o1["info"]["truth"]["exo"][:, 0]
    C = np.column_stack([np.sin(2 * math.pi * th["f_d"] * t), np.cos(2 * math.pi * th["f_d"] * t)])
    phases = []
    for o in runs:                                                 # a pure sinusoid at f_d ...
        e = o["info"]["truth"]["exo"][:, 0]
        assert r2(C, e) > 0.999999
        c = np.linalg.lstsq(C, e, rcond=None)[0]
        phases.append(math.atan2(c[1], c[0]))
    spread = np.abs(np.angle(np.exp(1j * (np.array(phases)[:, None] - np.array(phases)[None]))))
    assert spread.max() > 1.0                                      # ... with a trajectory-specific (random) phase
    # the documented f closes the dynamics only with e: one-step residuals
    z, u, w = o1["z"], o1["u"][:, 0], 2 * math.pi * th["f0"]
    d2 = np.diff(z[:, 1]) / DT
    base = -w * z[:-1, 0] - 2 * th["zeta"] * w * z[:-1, 1] + w * th["gain"] * u[:-1]
    r_with = d2 - (base + w * th["g_d"] * e1[:-1])
    r_without = d2 - base
    assert r_without.var() > 10 * r_with.var()
    # interventions do not touch the drive; the causal response decays
    a, b = _g5_kick_pair(s)
    assert np.abs(a["info"]["truth"]["exo"] - b["info"]["truth"]["exo"]).max() == 0.0
    dy = (a["y"] - b["y"])[:, 0]
    assert np.abs(dy[201:251]).max() > 0.5 and np.abs(dy[450:]).max() < 0.1 * np.abs(dy[201:251]).max()


def test_G5_fools_autoregressive_learner(G):
    s = G["g5_exo_rhythm"]
    outs = [run(s, ns=100 + i, t_end=6.0) for i in range(10)]
    mu, Vt, var = pca(np.concatenate([o["x"][100:] for o in outs]))
    V = Vt[:2].T
    W, roll = lin_model(outs, lambda x: (x - mu) @ V, n_lags=2)
    A = W[:4].T                                                    # companion matrix of the AR(2) model
    comp = np.vstack([A, np.hstack([np.eye(2), np.zeros((2, 2))])])
    assert np.abs(np.linalg.eigvals(comp)).max() > 0.99            # it has "learned" an undamped intrinsic rhythm
    test = [run(s, ns=300 + i, t_end=6.0) for i in range(4)]
    e, yy = [], []
    for o in test:
        for i0 in range(150, 400, 50):
            e.append(roll(o, i0, 150) - o["y"][i0:i0 + 150, 0]); yy.append(o["y"][i0:i0 + 150, 0])
    assert 1 - (np.concatenate(e) ** 2).mean() / np.concatenate(yy).var() > 0.9      # excellent on unperturbed data
    a, b = _g5_kick_pair(s)
    predicted = roll(a, 201, 350) - roll(b, 201, 350)
    true = (a["y"] - b["y"])[201:551, 0]
    late, early = slice(200, 350), np.abs(true[:50]).max()        # 2-3.5 s after the kick
    assert np.abs(true[late]).max() < 0.1 * early                  # truth: the kick response has died out
    assert np.abs(predicted[late]).max() > 0.3 * early             # the AR learner: a persistent rhythm shift
    assert np.abs(predicted[late]).max() > 5 * np.abs(true[late]).max()


def test_G5_truth_latent_predicts(G):
    s = G["g5_exo_rhythm"]
    outs = [run(s, ns=100 + i, t_end=6.0, stimulus=random_pulses(np.random.default_rng(i))) for i in range(6)]
    Xa = np.concatenate([np.hstack([o["z"][:-1], o["u"][:-1], o["info"]["truth"]["exo"][:-1]]) for o in outs])
    Ya = np.concatenate([o["z"][1:] for o in outs])
    W = fit(Xa, Ya)
    A = W[:2].T                                                    # linear: the kick response evolves by A alone
    a, b = _g5_kick_pair(s)
    dz = (a["z"] - b["z"])[201].copy()
    pr = []
    for i in range(350):
        pr.append(dz[0]); dz = A @ dz
    assert r2p((a["y"] - b["y"])[201:551, 0], np.array(pr)) > 0.95


# ------------------------------------------------------------------------------------------------ G6
def _g6_data(s, n=16, seed=0):
    rng = np.random.default_rng(seed)
    return [run(s, stimulus=random_pulses(rng), ns=i, ps=i % 3) for i in range(n)]


def _ridge(X, Y, lam=1e-2):
    Xm, Ym = X.mean(0), Y.mean()
    A = X - Xm
    W = np.linalg.solve(A.T @ A + lam * len(X) * np.eye(A.shape[1]), A.T @ (Y - Ym))
    return lambda x: (x - Xm) @ W + Ym, W


def test_G6_claim_impostor_same_law_not_causal(G):
    s = G["g6_impostor"]
    outs = _g6_data(s)
    C = np.concatenate([o["info"]["truth"]["coords"] for o in outs])
    assert np.corrcoef(C.T)[0, 1] > 0.98                           # the impostor tracks the latent
    imp = [j for j in range(s.n) if s.impl.roles[j] == "impostor"]
    cau = [j for j in range(s.n) if s.impl.roles[j] == "latent"]
    stim = random_pulses(np.random.default_rng(9))
    b = run(s, stimulus=stim, ns=5)
    a = run(s, stimulus=stim, ns=5, events=[kick_event(1.0, {j: 2.0 for j in imp}),
                                            {"kind": "silence", "t0": 2.0, "t1": 3.0, "targets": imp[:30]}])
    assert np.abs(a["y"] - b["y"]).max() < 1e-12 and np.abs(a["x"] - b["x"]).max() > 1.0
    a = run(s, stimulus=stim, ns=5, events=[kick_event(1.0, {j: 1.0 * np.sign(s.impl.D[0, j]) for j in cau})])
    assert np.abs(a["y"] - b["y"]).max() > 0.3


def test_G6_fools_output_supervised_encoder(G):
    s = G["g6_impostor"]
    outs = _g6_data(s)
    X = np.concatenate([o["x"] for o in outs])
    Y = np.concatenate([o["y"][:, 0] for o in outs])
    enc, W = _ridge(X, Y)
    test = _g6_data(s, n=4, seed=7)
    assert r2p(np.concatenate([o["y"][:, 0] for o in test]), enc(np.concatenate([o["x"] for o in test]))) > 0.95
    imp = [s.observed.index(j) for j in s.observed if s.impl.roles[j] == "impostor"]
    assert np.abs(W[imp]).sum() / np.abs(W).sum() > 0.5            # most readout weight on the impostor
    sdx, K = X.std(0), s.k
    stim = random_pulses(np.random.default_rng(3))
    b = run(s, stimulus=stim, ns=55)
    ev_imp = kick_event(2.0, {j: 1.5 * sdx[s.observed.index(j)] * np.sign(s.impl.E[j, K])
                              for j in s.observed if s.impl.roles[j] == "impostor"})
    a = run(s, stimulus=stim, ns=55, events=[ev_imp])
    assert np.abs(a["y"] - b["y"]).max() < 1e-12
    assert abs(enc(a["x"][201]) - enc(b["x"][201])) > 0.3 * Y.std()          # predicts an effect that does not exist
    ev_c = kick_event(2.0, {j: 1.5 * sdx[s.observed.index(j)] * np.sign(s.impl.D[0, j])
                            for j in s.observed if s.impl.roles[j] == "latent"})
    a = run(s, stimulus=stim, ns=55, events=[ev_c])
    true = (a["y"] - b["y"])[201, 0]
    assert abs(enc(a["x"][201]) - enc(b["x"][201])) < 0.5 * abs(true)        # misses most of the real effect


def test_G6_truth_latent_predicts(G):
    s = G["g6_impostor"]
    sdx = np.concatenate([o["x"] for o in _g6_data(s, n=4)]).std(0)
    stim = random_pulses(np.random.default_rng(3))
    b = run(s, stimulus=stim, ns=55, full=True)
    dv = {j: 1.5 * sdx[s.observed.index(j)] * np.sign(s.impl.D[0, j]) for j in s.observed if s.impl.roles[j] == "latent"}
    a = run(s, stimulus=stim, ns=55, events=[kick_event(2.0, dv)])
    th = s.model.latent.draw(0)
    predicted_dz = sum(s.impl.D[0, j] * v for j, v in dv.items())            # truth: D[:k, j] dv_j (identity phi) ...
    decay = np.exp(-np.arange(0, 100) * DT / th["tau"])                       # ... then relaxes with the latent's tau
    assert np.abs((a["z"] - b["z"])[200 + 1: 301, 0] - predicted_dz * decay * np.exp(-DT / th["tau"])).max() < 1e-4 * predicted_dz
    assert np.abs(a["y"][:, 0] - a["z"][:, 0]).max() < 1e-12


# ------------------------------------------------------------------------------------------------ G7
def _g7_decay_rate(s, a0):
    th = s.model.latent.draw(0)
    ev = [{"kind": "latent_impulse", "t": 1.0, "delta": {"1": 0.1}}]
    o = run(s, z0=[a0, 0.0, 0.0], stimulus=[[0.0, a0 / th["gain"]]], events=ev, noise=False, t_end=2.0)
    bn = np.linalg.norm(o["z"][101:160, 1:], axis=1)
    return -np.polyfit(np.arange(len(bn)) * DT, np.log(bn), 1)[0]


def test_G7_claim_state_dependent_stability(G):
    s = G["g7_local_validity"]
    th = s.model.latent.draw(0)
    for a0 in (0.0, 0.6, 0.9):
        assert abs(_g7_decay_rate(s, a0) / (th["mu"] * (1 - a0 ** 2 / th["a_c"] ** 2)) - 1) < 0.03
    o = run(s, z0=[1.8, 0.01, 0.0], stimulus=[[0.0, 1.8 / th["gain"]]], noise=False, t_end=2.0)
    assert np.linalg.norm(o["z"][100, 1:]) > 10 * 0.01                       # outside the region b grows


def test_G7_fools_model_fitted_inside_training_region(G):
    s = G["g7_local_validity"]
    lat, rng = s.model.latent, np.random.default_rng(0)
    tr = []
    for i in range(20):
        ps = i % 4
        th = lat.draw(ps)
        st = random_stimulus(lat, rng, 4.0) if i % 2 else scaled_nominal(lat, rng, 4.0)
        tr.append(run(s, stimulus=st, ns=i, z0=lat.sample_init(rng, th), ps=ps))
    assert max(np.abs(o["z"][:, 0]).max() for o in tr) < s.model.latent.draw(0)["a_c"]
    mu, Vt, var = pca(np.concatenate([o["x"] for o in tr]))
    assert var[0] > 0.85
    V = Vt[:1].T
    _, roll = lin_model(tr, lambda x: (x - mu) @ V)
    th = lat.draw(0)

    def rmse(outs):
        e = [roll(o, i0, 50) - o["y"][i0:i0 + 50, 0] for o in outs for i0 in range(0, 350, 25)]
        return np.sqrt((np.concatenate(e) ** 2).mean())
    inside = [run(s, stimulus=random_stimulus(lat, rng, 4.0), ns=100 + i, z0=lat.sample_init(rng, th)) for i in range(6)]
    outside = [run(s, ns=200 + i, z0=lat.sample_init(rng, th, heldout=True)) for i in range(6)]
    assert rmse(outside) > 5 * rmse(inside)


def test_G7_truth_critical_slowing_predicts_boundary(G):
    """Inside the training region the b-mode's decay rate (measurable from kicks or fluctuations) shrinks with |a|;
    extrapolating rate(a) = mu (1 - a^2/a_c^2) from in-region measurements recovers the boundary."""
    s = G["g7_local_validity"]
    th = s.model.latent.draw(0)
    a = np.array([0.0, 0.3, 0.6, 0.9])
    rates = np.array([_g7_decay_rate(s, x) for x in a])
    c = np.polyfit(a ** 2, rates, 1)                               # rate = mu - (mu / a_c^2) a^2
    a_c_hat = math.sqrt(-c[1] / c[0])
    assert abs(a_c_hat / th["a_c"] - 1) < 0.05


# ------------------------------------------------------------------------------------------------ G8
@pytest.fixture(scope="module")
def g8_long(G):
    s = G["g8_levy_switch"]
    return s, [run(s, ns=i, t_end=20.0) for i in range(12)]


def _switch_steps(z):
    state, st = (-1 if z[0] < 0 else 1), []
    for i, v in enumerate(z):
        if state < 0 and v > 0.5:
            state = 1; st.append(i)
        elif state > 0 and v < -0.5:
            state = -1; st.append(i)
    return st


def test_G8_claim_heavy_tailed_jumps_cause_memoryless_switches(G, g8_long):
    s, outs = g8_long
    th = s.model.latent.draw(0)
    Z = [o["z"][:, 0] for o in outs]
    ex = [o["info"]["truth"]["exo"][:, 0] * DT for o in outs]
    res = np.concatenate([np.diff(z) - DT * (z[:-1] - z[:-1] ** 3) / th["tau"] for z in Z])
    assert ((res - res.mean()) ** 4).mean() / res.var() ** 2 > 50   # kurtosis >> 3
    J = np.concatenate(ex)
    J = J[J != 0]
    assert abs(len(J) / (len(Z) * 20.0) / th["rate_J"] - 1) < 0.25  # Poisson rate
    assert np.abs(J).max() <= th["J_max"] + 1e-12 and (np.abs(J) >= th["xm"] - 1e-12).all()
    sw = [_switch_steps(z) for z in Z]
    assert sum(map(len, sw)) >= 10
    caused = [np.abs(e[max(0, i - 60): i + 1]).max() > 0.6 for e, S in zip(ex, sw) for i in S]
    assert np.mean(caused) > 0.8                                   # switches follow single large jumps (< 0.6 s before)
    pre, base = [], np.mean([np.abs(z).mean() for z in Z])
    for z, e, S in zip(Z, ex, sw):
        big = np.flatnonzero(np.abs(e) > 0.6)
        for i in S:
            js = [q for q in big if i - 60 <= q <= i]
            if js and js[-1] >= 50:
                pre.append(np.abs(z[js[-1] - 50: js[-1] - 10]).mean())
    assert abs(np.mean(pre) - base) < 0.1                          # no precursor: nothing in z announces a switch


def test_G8_fools_gaussian_noise_model(G, g8_long):
    s, outs = g8_long
    Z = [o["z"][:, 0] for o in outs]
    A = np.concatenate([np.column_stack([np.ones(len(z) - 1), z[:-1], z[:-1] ** 2, z[:-1] ** 3]) for z in Z])
    dz = np.concatenate([np.diff(z) for z in Z])
    c = np.linalg.lstsq(A, dz, rcond=None)[0]
    r = dz - A @ c
    sig_ls, sig_rob = r.std(), 1.4826 * np.median(np.abs(r - np.median(r)))
    actual_rate = sum(len(_switch_steps(z)) for z in Z) / (len(Z) * 20.0)

    def gauss_rate(sig, n=20, T=2000, seed=0):
        rg = np.random.default_rng(seed)
        z = np.full(n, -1.0)
        n_sw, state = 0, -np.ones(n)
        for _ in range(T):
            z = np.clip(z + np.column_stack([np.ones(n), z, z * z, z ** 3]) @ c + sig * rg.standard_normal(n), -5, 5)
            up, dn = (state < 0) & (z > 0.5), (state > 0) & (z < -0.5)
            n_sw += up.sum() + dn.sum()
            state[up], state[dn] = 1, -1
        return n_sw / (n * T * DT)
    # a Gaussian noise model cannot match both the typical jitter and the switching rate
    assert gauss_rate(sig_rob) < 0.1 * actual_rate                 # robust fit: (almost) never switches
    assert sig_ls > 5 * sig_rob                                    # LS fit: typical jitter > 5x too large


def test_G8_truth_law_predicts_switching(G, g8_long):
    """The documented 1-D law (drift + Gaussian + compound-Poisson Pareto jumps), simulated independently of the
    neuron-level simulator, reproduces the observed switching rate."""
    s, outs = g8_long
    th = s.model.latent.draw(0)
    actual = sum(len(_switch_steps(o["z"][:, 0])) for o in outs) / (len(outs) * 20.0)
    rg = np.random.default_rng(1)
    n, T, sub = 40, 2000, 10
    z, state, n_sw = np.full(n, -1.0), -np.ones(n), 0
    for _ in range(T):
        for _ in range(sub):
            z = z + DT / sub * (z - z ** 3) / th["tau"] + th["sigma"] * math.sqrt(DT / sub) * rg.standard_normal(n)
        hit = rg.random(n) < th["rate_J"] * DT
        mag = np.minimum(th["xm"] * rg.random(n) ** (-1 / th["alpha"]), th["J_max"])
        z = z + np.where(hit, np.where(rg.random(n) < 0.5, -1, 1) * mag, 0.0)
        up, dn = (state < 0) & (z > 0.5), (state > 0) & (z < -0.5)
        n_sw += up.sum() + dn.sum()
        state[up], state[dn] = 1, -1
    predicted = n_sw / (n * T * DT)
    assert 0.5 < predicted / actual < 2.0


# ------------------------------------------------------------------------------------------------ G9
@pytest.fixture(scope="module")
def g9_data(G):
    s = G["g9_param_drift"]
    lat, rng = s.model.latent, np.random.default_rng(0)
    th = lat.draw(0)
    return s, [run(s, stimulus=random_stimulus(lat, rng, 4.0), ns=i, z0=lat.sample_init(rng, th)) for i in range(30)]


def _g9_models(outs):
    Ya = np.concatenate([np.diff(o["z"], axis=0) for o in outs])
    W1 = np.linalg.lstsq(np.concatenate([np.hstack([o["z"][:-1], o["u"][:-1]]) for o in outs]), Ya, rcond=None)[0]

    def f2(z, u, e):
        te = np.tanh(e)
        return np.hstack([z, z * te, z * te ** 2, u, u * te])
    W2 = np.linalg.lstsq(np.concatenate([f2(o["z"][:-1], o["u"][:-1], o["info"]["truth"]["exo"][:-1]) for o in outs]),
                         Ya, rcond=None)[0]

    def score(test, ctx):
        e, yy = [], []
        for o in test:
            ex = o["info"]["truth"]["exo"]
            for i0 in range(0, 300, 50):
                z, out = o["z"][i0].copy(), []
                for i in range(100):
                    out.append(z[0])
                    u = o["u"][i0 + i]
                    z = z + (f2(z[None], u[None], ex[i0 + i][None])[0] @ W2 if ctx else np.concatenate([z, u]) @ W1)
                e.append(np.array(out) - o["z"][i0:i0 + 100, 0]); yy.append(o["z"][i0:i0 + 100, 0])
        return (np.concatenate(e) ** 2).mean() / np.concatenate(yy).var()
    return score


def test_G9_claim_context_drifts_and_is_not_controllable(G, g9_data):
    s, outs = g9_data
    th = s.model.latent.draw(0)
    e = np.concatenate([o["info"]["truth"]["exo"][:, 0] for o in outs])
    assert 0.5 < e.std() < 1.5
    lag = int(round(0.5 / DT))
    ex = [o["info"]["truth"]["exo"][:, 0] for o in outs]
    ac = sum((q[:-lag] * q[lag:]).sum() for q in ex) / sum((q[:-lag] ** 2).sum() for q in ex)   # known zero mean
    assert abs(ac - math.exp(-0.5 / th["tau_e"])) < 0.15           # OU with the documented time constant
    # no intervention moves the context (twins share it exactly), while z does respond
    ev = [kick_event(1.0, {j: 1.0 for j in range(10)}), {"kind": "silence", "t0": 2.0, "t1": 3.0, "targets": list(range(10, 25))}]
    a, b = run(s, ns=77, events=ev), run(s, ns=77)
    assert np.abs(a["info"]["truth"]["exo"] - b["info"]["truth"]["exo"]).max() == 0.0 and np.abs(a["z"] - b["z"]).max() > 0.05


def test_G9_fools_stationary_and_state_augmenting_learners(G, g9_data):
    s, outs = g9_data
    score = _g9_models(outs[:20])
    assert score(outs[20:], ctx=False) > 5 * score(outs[20:], ctx=True)       # a stationary model is 5x worse
    # the missing variable is not neural: not decodable from the recorded activity at any time
    X = np.concatenate([o["x"] for o in outs])
    e = np.concatenate([o["info"]["truth"]["exo"][:, 0] for o in outs])
    h = len(X) // 2
    assert r2p(e[h:], pred(fit(X[:h], e[:h]), X[h:])) < 0.1


def test_G9_truth_with_context_predicts(G, g9_data):
    s, outs = g9_data
    score = _g9_models(outs[:20])
    assert score(outs[20:], ctx=True) < 0.03                       # 1 s rollouts, R^2 > 0.97


# ------------------------------------------------------------------------------------------------ G10
def _g10_kicks(s, n=12, seed=0, sdx=None):
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        J = rng.choice(s.n, 5, replace=False)
        ev = kick_event(1.0, {int(j): float(rng.choice([-1, 1]) * 2.0 * sdx[j]) for j in J})
        a, b = run(s, ns=500 + i, events=[ev]), run(s, ns=500 + i)
        out.append((a, b))
    return out


def _g10_unperturbed(s, n=12, seed=0):
    lat, rng = s.model.latent, np.random.default_rng(seed)
    th = lat.draw(0)
    return [run(s, stimulus=random_stimulus(lat, rng, 4.0), ns=i, z0=lat.sample_init(rng, th)) for i in range(n)]


def test_G10_claim_dormant_modes(G):
    s = G["g10_masked_highdim"]
    lat, rng = s.model.latent, np.random.default_rng(0)
    th = lat.draw(0)
    for i in range(3):
        o = run(s, stimulus=random_stimulus(lat, rng, 4.0), z0=lat.sample_init(rng, th), noise=False)
        assert np.abs(o["z"][:, 1:]).max() < 1e-9 and np.abs(o["z"][:, 0]).max() > 0.1
    o = run(s, events=[kick_event(1.0, {3: 1.0})], noise=False)
    amp = np.linalg.norm(o["z"][102, 1:].reshape(-1, 2), axis=1)
    assert (amp > 1e-4).all()                                      # one micro kick excites every dormant mode


def test_G10_fools_variance_dimension_and_low_dim_model(G):
    s = G["g10_masked_highdim"]
    outs = _g10_unperturbed(s)
    X = np.concatenate([o["x"] for o in outs])
    mu, Vt, var = pca(X)
    assert var[0] > 10 * var[1]                                    # one dominant dimension; the rest is noise floor
    V = Vt[:1].T
    _, roll = lin_model(outs, lambda x: (x - mu) @ V)
    sdx = np.zeros(s.n)
    sdx[s.observed] = X.std(0)
    e_lin, e_tot = [], []
    for a, b in _g10_kicks(s, sdx=sdx):
        true = (a["y"] - b["y"])[131:301, 0]                       # 0.3-2 s after the kick
        pr = roll(a, 101, 200)[30:] - roll(b, 101, 200)[30:]
        e_lin.append(((pr - true) ** 2).sum()); e_tot.append((true ** 2).sum())
    assert sum(e_lin) > 0.5 * sum(e_tot)                           # misses most of the intervention response


def test_G10_no_compact_state_but_truth_predicts(G):
    s = G["g10_masked_highdim"]
    X = np.concatenate([o["x"] for o in _g10_unperturbed(s, n=4)])
    sdx = np.zeros(s.n)
    sdx[s.observed] = X.std(0)
    pairs = _g10_kicks(s, n=16, seed=1, sdx=sdx)
    R = np.array([(a["y"] - b["y"])[101:301, 0] for a, b in pairs])
    H = np.array([R[q, i: i + 100] for q in range(len(R)) for i in range(0, 100, 2)])
    sv = np.linalg.svd(H, compute_uv=False) ** 2
    assert sv[:6].sum() / sv.sum() < 0.9                           # no 6-D linear state explains the responses
    # the (33-D) truth latent does: a linear map fitted on truth-level kick effects (kicked minus twin, same noise
    # realisation, so the difference obeys the latent's linear law exactly) predicts held-out kick effects
    tr, te = pairs[:10], pairs[10:]
    dZ = [(a["z"] - b["z"])[102:] for a, b in tr]
    A = np.linalg.lstsq(np.concatenate([d[:-1] for d in dZ]), np.concatenate([d[1:] for d in dZ]), rcond=None)[0].T
    C = s.model.latent.C
    for a, b in te:
        dz = (a["z"] - b["z"])[102].copy()
        pr = []
        for _ in range(199):
            pr.append(C @ dz); dz = A @ dz
        assert r2p((a["y"] - b["y"])[102:301, 0], np.array(pr)) > 0.95


# ------------------------------------------------------------------------------------------------ suite
def test_review_g_suite_builds_through_unchanged_builder(tmp_path):
    import p3synth.suite as S
    from p3synth.systems import catalog
    before = (S.catalog, S._run_system)
    res = build_review_g_suite(tmp_path / "public", tmp_path / "truth", seed=0, scale=0.25, workers=3)
    assert (S.catalog, S._run_system) == before                    # the builder is restored afterwards
    assert res["n_systems"] == len(NAMES)
    ds = Dataset(tmp_path / "public")
    assert len(ds.index) == res["n_traj"] and len(ds.systems) == len(NAMES)
    text = (tmp_path / "public" / "manifest.json").read_text() + (tmp_path / "public" / "index.jsonl").read_text()
    forbidden = NAMES + [d.latent_key for d in review_g_catalog()] + list(TRAPS_G.values()) + \
        [d.name for d in catalog()] + ["review_g", "trap", "theta", "latent_set", "latent_impulse"]
    for word in forbidden:
        assert not re.search(r"(?<![A-Za-z0-9_])" + re.escape(word) + r"(?![A-Za-z0-9_])", text), word
    truth = json.loads((tmp_path / "truth" / "truth.json").read_text())
    assert sorted(t["trap"] for t in truth["systems"].values()) == sorted(TRAPS_G)
    assert {t["name"] for t in truth["systems"].values()} == set(NAMES)
    assert truth["suite"]["tier"] == "heldout"
    for sid, t in truth["systems"].items():
        rows = ds.select(system_id=sid)
        assert {r["split"] for r in rows} == {"train", "val", "test", "twin"}
    for row in ds.index[:10]:
        with np.load(tmp_path / "public" / "traj" / f"{row['key']}.npz") as z:
            assert set(z.files) == {"t", "x", "u", "y"}
