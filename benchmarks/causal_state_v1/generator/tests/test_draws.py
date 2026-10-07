"""Per-trajectory parameter draws (addition C): z is closed GIVEN the draw. truth()["d_draw"] is the effective draw dimension and
draw_effective(protocol) (length d_draw, deterministic in params_seed / params_spread / weight noise) the draw's coordinates.

On one system per type of every test seed, for 6 random public draws: from the microstate a trajectory of that draw reaches at
0.8 s, futures of 0.5 s under a random input step (1.0 -> a level in [0.6, 1.4] at 0.2 s) and a +-2 m_s kick on a random core
target at 0.1 s.
  * (z, draw_effective) predicts the futures across draws: simulating with the draw reconstructed from draw_effective alone (the
    neglected directions at 0) reproduces the true futures (d_draw is defined so that the neglected directions jointly change
    the readout by <= 0.5 f_s RMS over the draw distribution, linearised) — median over the draws <= 1 f_s per system, pooled
    median <= 0.5 f_s; the full coordinates draw_parameters(protocol) reproduce them exactly;
  * z alone does not: from the SAME microstate the futures of the 6 draws differ; the best z-only prediction (their mean) misses
    the true one by e_z, which exceeds the (z, draw_effective) error in every system with d_draw > 0 and exceeds 1 f_s in most.
"""

import numpy as np

from conftest import const_input, one_per_type

K = 6


def _future(s, rng):
    """0.5 s from the state: nominal input stepping at 0.2 s to a level uniform in the input range, a +-2 m_s kick on a random core
    target at 0.1 s."""
    mk = s.capability()["kick"]["moderate"]
    tg = s.core_targets() or s.targetable
    lvl = lambda a: [a] * s.input_dim if s.input_dim > 1 else a  # noqa: E731
    a = round(float(rng.uniform(0.6, 1.4)), 3)
    u = int(tg[int(rng.integers(0, len(tg)))])
    return s.base_protocol(t_end=0.5, stimulus=[[0.0, lvl(1.0)], [0.2, lvl(a)]],
                           events=[{"kind": "kick", "t": 0.1, "delta": {str(u): float(rng.choice([-2.0, 2.0])) * mk}}])


def test_draw_effective_is_deterministic_and_sized(suite):
    for s in one_per_type(suite):
        tr = s.truth()
        d = tr["d_draw"]
        assert isinstance(d, int) and 0 <= d <= len(tr["draw"]["parameters"]) and tr["draw"]["tolerance_fs"] == 0.5
        p = s.base_protocol(params_seed=12345)
        a, b = s.draw_effective(p), s.draw_effective(dict(p))
        assert a.shape == (d,) and np.array_equal(a, b)
        assert np.all(s.draw_effective(s.base_protocol()) == 0.0)                     # the nominal draw
        assert np.allclose(s.draw_effective(dict(p, params_spread=2.0)), 2.0 * a, rtol=1e-9, atol=1e-12)
        w = s.draw_effective(dict(p, weight_noise={"sd": 0.1, "seed": 3}), include_weight_noise=True)
        assert w.shape == (d + s.spec.k ** 2,) and np.allclose(w[:d], a) and np.abs(w[d:]).max() > 0
        assert len(tr["draw"]["singular_values_fs"]) == len(tr["draw"]["parameters"])


def test_closure_given_the_draw(suite):
    rng = np.random.default_rng(11)
    rows = {}
    for s in one_per_type(suite):
        sens = s.draw_sensitivity()
        fs = sens["f_s"]
        seeds = [int(a) for a in rng.integers(1, 10 ** 9, K)]
        e_eff, e_z, e_full = [], [], []
        for i, ps in enumerate(seeds):
            fut = _future(s, rng)
            p = s.base_protocol(params_seed=ps)
            st = s.simulate(p, full=True)["state"][int(round(0.8 / s.dt))]
            ys = [s.simulate(dict(fut, params_seed=pj), restart_state=st)["y"] for pj in seeds]
            yi = ys[i]
            e_z.append(float(np.sqrt(np.mean((yi - np.mean(ys, axis=0)) ** 2))) / fs)
            q = dict(fut, params_seed=ps)
            eta_r = s.eta_from_effective(s.draw_effective(p))
            e_eff.append(float(np.sqrt(np.mean((yi - s.simulate_draw(q, eta_r, restart_state=st)["y"]) ** 2))) / fs)
            e_full.append(float(np.abs(yi - s.simulate_draw(q, s.draw_parameters(p), restart_state=st)["y"]).max()) / fs)
        lab = f"T{s.info['type']:02d}-{s.info['variant']}"
        rows[lab] = (sens["d_draw"], len(sens["names"]), float(np.median(e_eff)), max(e_eff), float(np.median(e_z)), max(e_full))
    print("label: (d_draw, n_params, e_eff median, e_eff max, e_z median, full-coordinate error) in f_s")
    for k, v in sorted(rows.items()):
        print(k, tuple(round(a, 3) if isinstance(a, float) else a for a in v))
    for lab, (d, n, em, emax, ez, ef) in rows.items():
        assert ef <= 1e-9, (lab, ef)
        assert em <= 1.0, (lab, em)
        if d > 0:
            assert em < 0.5 * ez, (lab, em, ez)
    pos = [v for v in rows.values() if v[0] > 0]
    assert float(np.median([v[2] for v in rows.values()])) <= 0.5
    assert np.mean([v[4] > 1.0 for v in pos]) >= 0.8 and float(np.median([v[4] for v in pos])) >= 3.0
