"""Each adversarial trap fools a simple representation-learning baseline in the intended way (A-L)."""
import numpy as np
import pytest

from p3synth.suite import scaled_nominal

from conftest import sim, with_z


def r2(X, Y):
    X1 = np.hstack([X, np.ones((len(X), 1))])
    W = np.linalg.lstsq(X1, Y, rcond=None)[0]
    res = Y - X1 @ W
    return 1 - res.var(0).sum() / Y.var(0).sum()


def fit_predict(Xtr, Ytr, Xte):
    W = np.linalg.lstsq(np.hstack([Xtr, np.ones((len(Xtr), 1))]), Ytr, rcond=None)[0]
    return np.hstack([Xte, np.ones((len(Xte), 1))]) @ W


def r2_pred(Y, P):
    return 1 - ((Y - P) ** 2).sum() / ((Y - Y.mean(0)) ** 2).sum()


def pca(X, n):
    Xc = X - X.mean(0)
    U, S, Vt = np.linalg.svd(Xc, full_matrices=False)
    return Xc @ Vt[:n].T, S ** 2 / (S ** 2).sum()


def many(s, n=6, t_end=4.0, seed=0, stim=None, noise=True, heldout=False, rest=False):
    rng = np.random.default_rng(seed)
    outs = []
    for i in range(n):
        th = s.model.latent.draw(i % 3)
        z0 = s.model.latent.rest(th) if rest else s.model.latent.sample_init(rng, th, heldout)
        c0 = np.concatenate([z0] + [np.asarray(b.init(rng, z0, th, s.model), float) for b in s.model.blocks])
        st = stim(rng) if stim else [[0.0, 0.0], [float(rng.uniform(0.3, 2)), float(rng.uniform(-1.5, 1.5))],
                                     [float(rng.uniform(2.2, 3.0)), 0.0]]
        out, _ = sim(s, t_end=t_end, c0=c0, stimulus=st, params_seed=i % 3, noise=noise)
        outs.append(out)
    return outs


@pytest.mark.parametrize("name", ["nuisance_ou", "nuisance_rhythm"])
def test_A_high_variance_nuisance(systems, name):
    s = systems[name]
    outs = many(s)
    X = np.concatenate([o["x"] for o in outs])
    Z = np.concatenate([o["z"] for o in outs])
    C = np.concatenate([o["info"]["truth"]["coords"][:, s.k:] for o in outs])
    pcs, var = pca(X, 2)
    # the leading principal components are nuisance, not latent
    assert r2(Z, pcs) < 0.3 and r2(C, pcs) > 0.8
    # most of the observed variance is explained by the nuisance, not by the causal latent
    Xc = X - X.mean(0)
    assert r2(C, Xc) > 2 * r2(Z, Xc)


def test_B_readout_copy(systems):
    s = systems["output_shortcut"]
    outs = many(s, n=8)
    copy = [j for j in s.observed if s.impl.roles[j] == "readout_copy"]
    cols = [s.observed.index(j) for j in copy]
    Xc = np.concatenate([o["x"][:-1, cols] for o in outs])
    Zs = np.concatenate([o["z"][:-1] for o in outs])
    Y1 = np.concatenate([o["y"][1:] for o in outs])
    assert r2(Xc, Y1) > 0.9                          # one-step readout prediction from the copy neurons is excellent
    H = 60                                           # ... but they carry no state: 0.6 s ahead they are useless
    Xh = np.concatenate([o["x"][:-H, cols] for o in outs])
    Zh = np.concatenate([o["z"][:-H] for o in outs])
    Uh = np.concatenate([o["u"][:-H] for o in outs])
    YH = np.concatenate([o["y"][H:] for o in outs])
    free = np.concatenate([np.all(o["u"][:, 0] == 0) * np.ones(len(o["y"]) - H, bool) for o in outs])
    assert r2(Zh, YH) > r2(Xh, YH) + 0.3
    assert s.model.k == 3 and s.readout_dim == 1


def test_C_clock(systems):
    s = systems["time_index"]
    lat = s.model.latent
    locked = many(s, n=8, stim=lambda rng: scaled_nominal(lat, rng, 4.0), rest=True)
    shifted = many(s, n=8, seed=5, stim=lambda rng: scaled_nominal(lat, rng, 4.0, shift=float(rng.uniform(0.3, 1.5))), rest=True)
    ck = [s.observed.index(j) for j in s.observed if s.impl.roles[j] == "clock"]
    # clock neurons encode time
    X = np.concatenate([o["x"][:, ck] for o in locked])
    T = np.concatenate([o["t"] for o in locked])[:, None]
    assert r2(np.hstack([X, X ** 2]), T) > 0.9
    # with time-locked stimuli, "time" predicts the readout well; with shifted stimuli it does not
    feats = lambda o: np.stack([np.exp(-0.5 * ((o["t"] - c) / 0.15) ** 2) for c in np.arange(0, 4.01, 0.1)], 1)
    Ftr = np.concatenate([feats(o) for o in locked[:6]])
    Ytr = np.concatenate([o["y"] for o in locked[:6]])
    P_lock = fit_predict(Ftr, Ytr, np.concatenate([feats(o) for o in locked[6:]]))
    P_shift = fit_predict(Ftr, Ytr, np.concatenate([feats(o) for o in shifted]))
    assert r2_pred(np.concatenate([o["y"] for o in locked[6:]]), P_lock) > 0.8
    assert r2_pred(np.concatenate([o["y"] for o in shifted]), P_shift) < 0.3


def test_D_stimulus_copy(systems):
    s = systems["stimulus_copy"]
    outs = many(s, n=6)
    cols = [s.observed.index(j) for j in s.observed if s.impl.roles[j] == "stimulus_copy"]
    X = np.concatenate([o["x"][:, cols] for o in outs])
    U = np.concatenate([o["u"] for o in outs])
    Y = np.concatenate([o["y"] for o in outs])
    assert r2(X, U) > 0.9 and r2(X, Y) > 0.3          # copies u, and hence partly "predicts" y


def test_E_many_microstates_one_causal_state(systems):
    s = systems["redundant_switch"]
    rng = np.random.default_rng(0)
    th = s.model.latent.draw(0)
    c1 = s.model.rest(th).copy(); c1[0] = 1.0
    c2 = c1.copy(); c2[s.k:] = 1.5 * rng.standard_normal(s.model.K - s.k)
    stim = [[0.0, 0.0], [1.0, -1.0], [1.3, 0.0]]
    a, _ = sim(s, t_end=3.0, c0=c1, stimulus=stim)
    b, _ = sim(s, t_end=3.0, c0=c2, stimulus=stim)
    assert np.abs(a["y"] - b["y"]).max() < 1e-9 and np.abs(a["z"] - b["z"]).max() < 1e-9
    dx = np.linalg.norm(a["x"] - b["x"], axis=1) / np.linalg.norm(a["x"] - a["x"].mean(0), axis=1).mean()
    assert dx.min() > 0.3                                     # persistently different microstates


def test_F_hysteresis(systems):
    s = systems["hysteresis"]
    probe = [[0.0, [0.0, 0.0]], [1.5, [0.0, 1.0]], [2.1, [0.0, 0.0]]]
    up, _ = sim(s, t_end=3.0, c0=with_z(s, [1.0, 0.0]), stimulus=probe)
    dn, _ = sim(s, t_end=3.0, c0=with_z(s, [-1.0, 0.0]), stimulus=probe)
    assert np.abs(up["y"][:150] - dn["y"][:150]).max() < 1e-9          # same output
    assert np.abs(up["z"][:150, 0] - dn["z"][:150, 0]).min() > 1.9     # different hidden state
    assert up["y"][200, 0] > 0.8 and dn["y"][200, 0] < -0.8             # different futures under the same input
    # hysteresis: the same (zero) input leaves the system in whichever state its history selected
    set_up, _ = sim(s, t_end=3.0, stimulus=[[0.0, [0.0, 0.0]], [0.3, [1.0, 0.0]], [0.7, [0.0, 0.0]]])
    assert set_up["z"][-1, 0] > 0.9 and sim(s, t_end=3.0)[0]["z"][-1, 0] < -0.9


def test_G_non_markov_compression(systems):
    s = systems["nonmarkov"]
    outs = many(s, n=8, t_end=4.0, stim=lambda rng: [[0.0, 0.0]])
    X = np.concatenate([o["x"] for o in outs])
    pcs, var = pca(X, 1)
    assert var[0] > 10 * var[1]                              # x looks one-dimensional
    Xc = X.mean(0)
    _, _, Vt = np.linalg.svd(X - Xc, full_matrices=False)
    emb = [(o["x"] - Xc) @ Vt[0] for o in outs]
    H = 40

    def ar_fit(series):
        A = np.concatenate([s_[:-1].reshape(len(s_) - 1, -1) for s_ in series])
        B = np.concatenate([s_[1:].reshape(len(s_) - 1, -1) for s_ in series])
        return np.linalg.lstsq(A, B, rcond=None)[0]

    def rollout_r2(series, M, H):
        err, tot = 0.0, 0.0
        for s_ in series:
            s2 = s_.reshape(len(s_), -1)
            for i in range(0, len(s2) - H, 10):
                p = s2[i].copy()
                for _ in range(H):
                    p = p @ M
                err += ((p[:1] - s2[i + H, :1]) ** 2).sum()
                tot += ((s2[i + H, :1] - s2[:, :1].mean(0)) ** 2).sum()
        return 1 - err / tot

    M1 = ar_fit(emb[:5])
    one_step = rollout_r2(emb[5:], M1, 1)
    long_1d = rollout_r2(emb[5:], M1, H)
    zs = [o["z"] for o in outs]
    M2 = ar_fit(zs[:5])
    long_2d = rollout_r2(zs[5:], M2, H)
    assert one_step > 0.95 and long_1d < 0.3 and long_2d > 0.8


def test_H_parameter_encoding(systems):
    s = systems["parameter_trap"]
    cols = [s.observed.index(j) for j in s.observed if s.impl.roles[j] == "parameter_report"]
    P, Ym, Pw = [], [], []
    for ps in range(12):
        o, _ = sim(s, t_end=3.0, params_seed=ps, stimulus=[[0.0, 0.0], [1.0, 0.5], [1.5, 0.0]], noise=True)
        P.append(o["x"][:, cols].mean(0)); Ym.append(o["y"].mean()); Pw.append(o["x"][:, cols].std(0).mean())
    P, Ym = np.array(P), np.array(Ym)
    assert r2(P, Ym[:, None]) > 0.9                  # parameter-reporting neurons "predict" y across draws
    assert np.mean(Pw) < 0.1 * P.std(0).mean()       # ... but are constant within a trajectory: not state


def test_I_multiple_limit_cycles(systems):
    s = systems["multicycle_planar"]
    inner, _ = sim(s, t_end=8.0, c0=with_z(s, [0.8, 0.0]))
    outer, _ = sim(s, t_end=8.0, c0=with_z(s, [1.2, 0.0]))
    r_in = np.linalg.norm(inner["z"][-100:], axis=1).mean()
    r_out = np.linalg.norm(outer["z"][-100:], axis=1).mean()
    assert abs(r_in - 0.5) < 0.02 and abs(r_out - 1.5) < 0.02
    s = systems["multicycle_switch"]
    a, _ = sim(s, t_end=8.0, c0=with_z(s, [1.0, 0.0, 1.0]), stimulus=[[0.0, 0.0]])
    b, _ = sim(s, t_end=8.0, c0=with_z(s, [1.0, 0.0, -1.0]), stimulus=[[0.0, 0.0]])
    assert abs(np.abs(a["y"][-200:]).max() - np.abs(b["y"][-200:]).max()) < 0.02    # same amplitude
    fa = np.abs(np.fft.rfft(a["y"][-512:, 0])).argmax()
    fb = np.abs(np.fft.rfft(b["y"][-512:, 0])).argmax()
    assert fa > 1.3 * fb                                                            # different cycle


def test_J_transient_vs_cycle(systems):
    s = systems["transient_cycle"]
    small, _ = sim(s, t_end=8.0, c0=with_z(s, [0.7, 0.0]))
    big, _ = sim(s, t_end=8.0, c0=with_z(s, [0.9, 0.0]))
    assert np.abs(small["y"][-100:]).max() < 0.05 and np.abs(big["y"][-100:]).max() > 1.3
    # same phase at t=0, both oscillate at first: amplitude decides the future
    assert np.sign(small["z"][10, 1]) == np.sign(big["z"][10, 1])


def test_K_bifurcation_changes_dimension(systems):
    s = systems["bifurcation"]
    rng = np.random.default_rng(0)
    low, high = [], []
    for i in range(6):
        z0 = rng.uniform(-0.8, 0.8, 2)
        low.append(sim(s, t_end=3.0, c0=with_z(s, z0), stimulus=[[0.0, 0.0]])[0]["z"][30:])
        high.append(sim(s, t_end=6.0, c0=with_z(s, z0), stimulus=[[0.0, 1.0]])[0]["z"][300:])
    _, v_low = pca(np.concatenate(low), 2)
    _, v_high = pca(np.concatenate(high), 2)
    assert v_low[0] > 0.99 and v_high[1] > 0.2


def test_L_distributed_code(systems):
    s = systems["distributed"]
    outs = many(s, n=6, t_end=4.0)
    X = np.concatenate([o["x"] for o in outs])
    Z = np.concatenate([o["z"] for o in outs])
    C = np.corrcoef(np.hstack([X, Z]).T)[: X.shape[1], X.shape[1]:]
    assert np.abs(C).max() < 0.6                              # no single neuron is a latent variable
    # the best 5-neuron linear readout of each latent is far worse than the population readout
    half = len(X) // 2
    for i in range(s.k):
        cc = np.abs(C[:, i])
        top = np.argsort(cc)[-5:]
        sparse = r2_pred(Z[half:, i], fit_predict(X[:half, top], Z[:half, i], X[half:, top]))
        dense = r2_pred(Z[half:, i], fit_predict(X[:half], Z[:half, i], X[half:]))
        assert dense > 0.6 and sparse < 0.5 * dense
