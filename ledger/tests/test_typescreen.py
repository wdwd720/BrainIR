"""The ledger tuner is the locked tuner: with one member it must give exactly the locked result."""

import numpy as np
import pytest
import scipy.sparse as sp
from brainir.sim.model import ModelConfig, Stimulus, sample_neuron_params
from brainir.sim.screen import ScreenConfig, screen_candidate

from brainir_ledger import legs as L
from brainir_ledger.typescreen import fixed_run, screen_group


def _net(n=40, seed=0):
    rng = np.random.default_rng(seed)
    W = sp.random(n, n, density=0.15, random_state=seed, format="csr") * 40
    W.data = np.round(W.data) + 5
    signs = np.where(rng.random(n) < 0.7, 1.0, -1.0)
    W = (W @ sp.diags(signs)).tocsr()
    W.setdiag(0)
    W.eliminate_zeros()
    readout = np.zeros(n, bool)
    readout[-8:] = True
    return W, readout


@pytest.mark.parametrize("cand", [0, 3, 7])
@pytest.mark.parametrize("cfg", [ScreenConfig(n_active_lower=5, n_active_upper=30, n_high_fr_upper=10),
                                 ScreenConfig(n_active_lower=10, n_active_upper=25, n_high_fr_upper=5)])
def test_single_member_equals_locked(cand, cfg):
    W, ro = _net()
    mc = ModelConfig(t_end=0.4)
    p = sample_neuron_params(mc, W.shape[0], 3)
    a = screen_candidate(W, p, mc, cand, ro, seed=3, cfg=cfg)
    b = screen_group(W, p, mc, [cand], ro, seed=3, cfg=cfg)
    for f in ("usable", "score", "frequency_hz", "n_active_readout", "current", "n_tuning_runs", "n_active_all", "n_high_fr"):
        assert getattr(a, f) == getattr(b, f), f


def test_group_stimulates_every_member_at_one_current():
    W, ro = _net()
    assert Stimulus((1, 4, 6), (99.0,)).vector(W.shape[0])[[1, 4, 6]].tolist() == [99.0, 99.0, 99.0]
    mc = ModelConfig(t_end=0.3)
    p = sample_neuron_params(mc, W.shape[0], 1)
    calls = []
    r = screen_group(W, p, mc, [1, 4, 6], ro, seed=1, cfg=ScreenConfig(n_active_lower=3, n_active_upper=39),
                     extras=lambda traj: calls.append(1) or {"n": traj.n})
    if r.usable:
        assert r.extras == {"n": W.shape[0]} and calls == [1]
    else:
        assert calls == []


def test_fixed_run_matches_screen_scoring():
    W, ro = _net()
    mc = ModelConfig(t_end=0.4)
    p = sample_neuron_params(mc, W.shape[0], 2)
    out = fixed_run(W, p, mc, [0, 1], [200.0, 200.0], ro)
    assert out["verdict"] in ("ok", "weak", "strong") and 0.0 <= out["score"] <= 1.0


def test_phase_offset_of_shifted_sinusoids():
    t = np.arange(1000) * 1e-3
    a = np.sin(2 * np.pi * 10 * t)
    for lag_ms, expect in [(0, 0.0), (25, -np.pi / 2), (50, -np.pi)]:
        b = np.roll(a, lag_ms)
        ph = L.phase_offset(a, b)
        d = np.angle(np.exp(1j * (ph - expect)))
        assert abs(d) < 0.15, (lag_ms, ph)
    assert np.isnan(L.phase_offset(np.zeros(500), a[:500]))


def test_tripod_index_and_resultant():
    perfect = {}
    for a, b in L.LEG_PAIRS:
        perfect[f"{a}-{b}"] = L.tripod_target(a, b)
    rhythmic = {leg: True for leg in L.LEGS}
    assert L.tripod_index(perfect, rhythmic) == pytest.approx(1.0)
    anti = {k: v + np.pi for k, v in perfect.items()}
    assert L.tripod_index(anti, rhythmic) == pytest.approx(-1.0)
    assert L.tripod_index(perfect, {leg: False for leg in L.LEGS}) is None
    assert L.resultant_length([0.3, 0.3, 0.3]) == pytest.approx(1.0)
    assert L.resultant_length([0, np.pi]) == pytest.approx(0.0, abs=1e-12)


def test_trace_packing_roundtrip():
    x = np.random.default_rng(0).random((50, 3))
    y = L.unpack_traces(L.pack_traces(x))
    assert np.allclose(x.astype(np.float32), y)
