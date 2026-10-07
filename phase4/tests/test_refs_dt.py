"""dt-awareness of the benchmark references (review H, M2; brainir_causal.refs) and the calibration's power-table corruptions."""

from __future__ import annotations

import numpy as np
import pytest
from test_lift_toysys import DT, ToyLinear, make_records

from brainir_causal import refs as R

FAST = R.LearnerConfig(steps_one=300, steps_multi=40, readout_steps=300)
KICK = {"kind": "kick", "t": 0.1, "delta": {"1": 1.5}}
PULSE = {"kind": "current", "t0": 0.2, "t1": 0.3, "targets": {"3": 4.0}}


@pytest.fixture(scope="module")
def toy():
    s = ToyLinear()
    train, truth = make_records(s, seed=0)
    return s, train, truth


def test_rollout_at_twice_dt_is_the_substepped_rollout(toy):
    """At dt = 2 dt_train the learned map runs twice per row: with a constant input and events on the coarse grid, the latent rows equal
    every second row of the rollout at the training dt bit for bit (PCA-k and FULL-STATE); the readout (a batched matrix product over
    the rows) to rounding."""
    s, train, _ = toy
    for name in ("pca_k", "full_state"):
        m = R.fit_reference(name, "toy", train, s.record(), k=2, cfg=FAST)
        r = train[3]
        z0 = m.encode("toy", r["x"][:61], r["u"][:61], DT)
        u1 = np.ones((41, 1))
        z1 = m.rollout("toy", z0, u1, [KICK, PULSE], DT)
        z2 = m.rollout("toy", z0, u1[::2], [KICK, PULSE], 2 * DT)
        assert z2["z"].shape[0] == 21
        assert np.array_equal(z2["z"], z1["z"][::2]) and np.allclose(z2["y"], z1["y"][::2], rtol=1e-12, atol=1e-12), name


def test_non_integer_dt_ratios_are_refused(toy):
    s, train, _ = toy
    m = R.fit_reference("pca_k", "toy", train, s.record(), k=2, cfg=FAST)
    z0 = m.encode("toy", train[0]["x"][:61], train[0]["u"][:61], DT)
    for bad in (1.5 * DT, 0.5 * DT):
        with pytest.raises(ValueError, match="integer multiple"):
            m.rollout("toy", z0, np.ones((11, 1)), [], bad)
    with pytest.raises(ValueError, match="integer multiple"):
        R.n_substeps(0.003, 0.002)
    assert R.n_substeps(0.004, 0.002) == 2 and R.n_substeps(0.01, 0.01) == 1


def test_full_state_traces_are_in_seconds(toy):
    """The trace time constants are seconds: a history sampled at 2 dt gives nearly the trace of the same signal sampled at dt, much
    closer than a trace that (wrongly) reuses the training factor per sample."""
    s, train, _ = toy
    m = R.fit_reference("full_state", "toy", train, s.record(), cfg=FAST)
    taus = m.info()["trace_taus_s"]
    assert taus == pytest.approx([max(2 * DT, 0.25 * 0.05), max(2 * DT, 0.05)])
    r = train[5]
    i = 120
    fine = m.encode("toy", r["x"][: i + 1], r["u"][: i + 1], DT)
    coarse = m.encode("toy", r["x"][: i + 1][::-1][::2][::-1], r["u"][: i + 1][::-1][::2][::-1], 2 * DT)
    wrong = np.hstack([r["x"][i]] + [R._ema(r["x"][: i + 1][::-1][::2][::-1], a)[-1] for a in m.alphas])
    n = r["x"].shape[1]
    err_ok = np.abs(coarse[n:] - fine[n:]).max()
    err_wrong = np.abs(wrong[n:] - fine[n:]).max()
    assert np.allclose(coarse[:n], fine[:n]) and err_ok < 0.5 * err_wrong


def test_id_shortcut_maps_rows_by_time(toy):
    s, train, _ = toy
    m = R.fit_reference("id_shortcut", "toy", train, s.record(), cfg=FAST)
    m.register_records(train)
    r = train[40]
    z0 = m.encode("toy", r["x"][:61], r["u"][:61], DT)
    y1 = m.rollout("toy", z0, np.ones((41, 1)), [KICK], DT)["y"]
    y2 = m.rollout("toy", z0, np.ones((21, 1)), [KICK], 2 * DT)["y"]
    assert np.allclose(y2, y1[::2])
    with pytest.raises(ValueError, match="integer multiple"):
        m.rollout("toy", z0, np.ones((11, 1)), [], 1.5 * DT)
    # lag features at lag TIMES: a history sampled at 2 dt reads the same readout where a lag time is on its grid (interpolated in
    # between); the time since the input's onset agrees to one coarse sample
    y, u = r["y"][:61], r["u"][:61]
    f1 = m._hist_feat(y, u, DT)
    f2 = m._hist_feat(y[::-1][::2][::-1], u[::-1][::2][::-1], 2 * DT)
    assert f1.shape == f2.shape
    n_y = y.shape[1]
    for j, lag in enumerate(m.lag_s):
        block = slice(j * n_y, (j + 1) * n_y)
        if abs(lag / (2 * DT) - round(lag / (2 * DT))) < 1e-9:
            assert np.array_equal(f1[block], f2[block]), lag
        else:
            assert np.allclose(f2[block], 0.5 * (y[60 - round(lag / DT) - 1] + y[60 - round(lag / DT) + 1]))
    assert abs(f1[-1] - f2[-1]) <= 2 * DT + 1e-12


def test_missing_coordinate_and_readin_corruptions(toy):
    s, train, truth = toy
    miss = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST, drop=(1,))
    assert miss.k["toy"] == 1 and miss.info()["dropped_true_coordinates"] == [1]
    r = train[7]
    miss.register_truth(r["x"], r["u"], truth["z"][r["key"]])
    assert np.allclose(miss.encode("toy", r["x"][:51], r["u"][:51], DT), truth["z"][r["key"]][50, :1])
    base = R.fit_reference("true_state", "toy", train, s.record(), truth=truth, cfg=FAST)
    rec = dict(s.record(), capability={"kick": {"supported": True, "max": 50.0},
                                       "current": {"supported": True, "max": 50.0, "pulse_max_duration": 0.15, "sustained_min_duration": 0.3}})
    bad = R.ReadinGainModel(base, "kick.1", rec, gain=0.5)
    z0 = base.encode("toy", r["x"][:51], r["u"][:51], DT)
    u = np.ones((31, 1))
    half = dict(KICK, delta={"1": 0.75})
    assert np.array_equal(bad.rollout("toy", z0, u, [KICK], DT)["z"], base.rollout("toy", z0, u, [half], DT)["z"])
    # another family (a current pulse) is untouched
    assert np.array_equal(bad.rollout("toy", z0, u, [PULSE], DT)["z"], base.rollout("toy", z0, u, [PULSE], DT)["z"])
    assert bad.n_scaled == 1 and bad.supports("toy", "kick") == base.supports("toy", "kick")
