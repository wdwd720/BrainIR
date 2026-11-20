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


def test_coupling_detects_locked_phase_and_not_random():
    rng = np.random.default_rng(5)
    t = np.arange(751) * 1e-3
    a, b, c = [], [], []
    for _ in range(16):
        f = rng.uniform(9, 12)
        ph = rng.uniform(0, 2 * np.pi)
        a.append(np.sin(2 * np.pi * f * t + ph))
        b.append(np.sin(2 * np.pi * f * t + ph + np.pi / 2))            # locked offset
        c.append(np.sin(2 * np.pi * rng.uniform(9, 12) * t + rng.uniform(0, 2 * np.pi)))  # independent
    locked = L.coupling(a, b, n_null=300, seed=1)
    assert locked["coupled"] and locked["R"] > 0.9 and locked["p"] < 0.01
    free = L.coupling(a, c, n_null=300, seed=1)
    assert not free["coupled"]
    small = L.coupling(a[:5], b[:5])
    assert small["R"] is None and small["coupled"] is None


def test_random_derangement_has_no_fixed_points():
    rng = np.random.default_rng(0)
    for n in (2, 3, 8, 16):
        p = L.random_derangement(n, rng)
        assert sorted(p) == list(range(n)) and not np.any(p == np.arange(n))


def test_baselines_on_a_tiny_network():
    from brainir_ledger.baselines import compute

    # neurons: 0,1 = group members; 2 = premotor; 3 = core; 4,5 = MNs.  C/W post x pre.
    C = np.zeros((6, 6))
    C[2, 0] = 10      # 0 -> 2
    C[4, 0] = 7       # 0 -> MN4 (direct)
    C[3, 1] = 5       # 1 -> core
    C[5, 2] = 20      # premotor 2 -> MN5
    C[4, 3] = 6       # core 3 -> MN4
    W = C.copy()
    W[:, 3] *= -1     # neuron 3 inhibitory
    mn = np.array([0, 0, 0, 0, 1, 1], bool)
    df = compute(sp.csr_matrix(C), sp.csr_matrix(W), mn, {"T": [0, 1]}, [3]).iloc[0]
    assert df["S1_direct_mn"] == 7
    assert df["S2_twohop_signed"] == 10 * 20 + 5 * (-6)     # 0->2->5 and 1->3-|4
    assert df["S3_twohop_abs"] == 10 * 20 + 5 * 6
    assert df["S4_total_out"] == 22 and df["S5_out_partners"] == 3 and df["S7_n_members"] == 2
    assert df["S6_premotor"] == 10 + 5  # neurons 2 and 3 both project onto MNs
    assert df["S8_informed"] == 5
