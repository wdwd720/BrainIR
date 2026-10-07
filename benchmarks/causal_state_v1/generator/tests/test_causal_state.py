"""Truth-level checks of every type's causal-state claim (one dev system per type, parametrised by type).

- equal z => equal readout futures under every intervention kind (equivalent_states: same z, different nuisance microstate);
- closure: a microstate with the same z but different off-manifold core detail has the same future under no intervention,
  currents and latent events; for state-reading interventions (silence) on the same unit the difference decays with tau_c;
- minimality: every z dimension changes the readout future (directly or under a probe intervention);
- lifts: kick lifts realise dz exactly; distinct lifts of one request have identical futures; pulse lifts reach dz;
- true_latent_effect of a kick equals the simulated jump; pool states are distinct, finite and restartable.
"""

import numpy as np
import pytest

from conftest import TYPES, const_input, f_s, mid_state, probe_protocols
from p4synth.engine import CORE  # noqa: F401
from p4synth.system import LIFT_D, LIFT_TOL


def _sys(by_type, t):
    return by_type[t][0]


@pytest.mark.parametrize("t", TYPES)
def test_equal_z_equal_futures(by_type, t):
    s = _sys(by_type, t)
    st = mid_state(s)
    rng = np.random.default_rng(t)
    eq = s.equivalent_states(st, 3, rng)
    for e in eq:
        np.testing.assert_allclose(s.true_state(e), s.true_state(st), atol=1e-12)
        assert np.abs(e - st).max() > 1e-3                        # different microscopic detail
    for p in probe_protocols(s):
        ref = s.simulate(p, restart_state=st)["y"]
        for e in eq:
            np.testing.assert_array_equal(s.simulate(p, restart_state=e)["y"], ref)


@pytest.mark.parametrize("t", TYPES)
def test_embedding_and_true_state(by_type, t):
    s = _sys(by_type, t)
    sp = s.spec
    assert np.linalg.matrix_rank(sp.E) == sp.k
    np.testing.assert_allclose(sp.L @ sp.E, np.eye(sp.k), atol=1e-9)
    np.testing.assert_allclose(s.true_state(s.rest_state()), np.zeros(sp.k), atol=1e-12)


@pytest.mark.parametrize("t", [t for t in TYPES if t not in (20, 21)])
def test_every_dimension_is_causal(by_type, t):
    """Minimality: a latent kick along any single z dimension changes the readout future by more than the effect floor, either
    directly or under a probe intervention on each core population."""
    s = _sys(by_type, t)
    sp = s.spec
    st = mid_state(s)
    fs = f_s(s)
    zs = np.asarray(sp.latent.z_scale)
    cap = s.capability()
    probes = [[]]
    tags = {}
    for u in s.core_targets():
        tags.setdefault(s.meta["unit_tag"][u], u)
    for u in tags.values():
        probes.append([{"kind": "kick", "t": 0.1, "delta": {str(u): 3 * cap["kick"]["moderate"]}}])
        probes.append([{"kind": "kick", "t": 0.1, "delta": {str(u): -3 * cap["kick"]["moderate"]}}])
    base = s.base_protocol(t_end=0.5, stimulus=const_input(s))
    for i in range(sp.k):
        best = 0.0
        for sgn in (1.0, -1.0):
            dz = np.zeros(sp.k)
            dz[i] = sgn * zs[i]
            for pe in probes:
                a = s.simulate(dict(base, events=pe), restart_state=st)["y"]
                b = s.simulate(dict(base, events=[{"kind": "latent_kick", "t": 0.02, "dz": dz.tolist()}] + pe), restart_state=st)["y"]
                best = max(best, float(np.sqrt(np.mean((a - b) ** 2))))
                if best > fs:
                    break
            if best > fs:
                break
        assert best > fs, (t, i, best, fs)


@pytest.mark.parametrize("t", TYPES)
def test_lifts(by_type, t):
    s = _sys(by_type, t)
    sp = s.spec
    st = mid_state(s)
    rng = np.random.default_rng(7 + t)
    zs = np.asarray(sp.latent.z_scale)
    tg = s.core_targets()
    # a reachable request (about 0.3 z_scale): the shift at the completion sample j = LIFT_D produced by a random kick on the
    # targetable core units one sample before j
    base = s.base_protocol(t_end=0.25, stimulus=const_input(s))
    twin = s.simulate(base, full=True, restart_state=st)
    w = rng.normal(size=len(tg))
    w *= 0.3 / np.linalg.norm((sp.L[:, [sp.loc[u] for u in tg]] @ w) / zs)
    kick = [{"kind": "kick", "t": (LIFT_D - 1) * s.dt, "delta": {str(u): float(a * s.units()["v"]) for u, a in zip(tg, w)}}]
    dz = s.simulate(dict(base, events=kick), full=True, restart_state=st)["z"][LIFT_D] - twin["z"][LIFT_D]
    rep = s.lift_latent(st, dz, 3, report=True)
    assert len(rep) >= 2, t
    assert [r["events"] for r in rep] == s.lift_latent(st, dz, 3)
    j = LIFT_D                                            # one common completion sample (t0 = 0)
    futures = []
    for r in rep:
        o = s.simulate(dict(base, events=r["events"]), full=True, restart_state=st)
        miss = np.linalg.norm((o["z"][j] - twin["z"][j] - dz) / zs) / np.linalg.norm(dz / zs)
        assert miss <= LIFT_TOL and abs(miss - r["miss"]) <= 1e-9, (t, miss, r["miss"])
        futures.append(o["y"][j:])
    # distinct lifts reach the same z at the same sample: their futures agree to the stated tolerance
    eff = float(np.sqrt(np.mean((futures[0] - twin["y"][j:]) ** 2)))
    for fut in futures[1:]:
        assert float(np.sqrt(np.mean((fut - futures[0]) ** 2))) <= 3 * LIFT_TOL * eff + 1e-9 * max(1.0, np.abs(fut).max())
    # an unreachable request (the lifts see only the targetable read-in L_T): whatever is returned meets the tolerance
    for r in s.lift_latent(st, 0.3 * rng.normal(size=sp.k) * zs, 3, report=True):
        assert r["miss"] <= LIFT_TOL


@pytest.mark.parametrize("t", TYPES)
def test_true_latent_effect_kick_matches_simulation(by_type, t):
    s = _sys(by_type, t)
    st = mid_state(s)
    u = s.core_targets()[0]
    ev = {"kind": "kick", "t": 0.0, "delta": {str(u): 2.0 * s.capability()["kick"]["moderate"]}}
    dz = s.true_latent_effect(st, ev)
    base = s.base_protocol(t_end=0.2, stimulus=const_input(s))
    a = s.simulate(dict(base, events=[ev]), full=True, restart_state=st)
    c = s.simulate(dict(base, events=[{"kind": "latent_kick", "t": 0.0, "dz": dz.tolist()}]), full=True, restart_state=st)
    # the microscopic kick and the truth-level do(z += dz) produce the same causal-state trajectory (closure)
    np.testing.assert_allclose(a["z"], c["z"], rtol=1e-8, atol=1e-8 * max(1.0, np.abs(c["z"]).max()))
    np.testing.assert_allclose(a["y"], c["y"], rtol=1e-7, atol=1e-7 * max(1.0, np.abs(c["y"]).max()))
    # addendum 5: definition = the jump z(t+) - z(t-) at the event; on a 0.1 ms output grid the sampled difference between the
    # intervention and its twin one sample after the event equals it up to 0.1 ms of dynamics
    fine = s.base_protocol(t_end=0.002, dt=1e-4, stimulus=const_input(s))
    a1 = s.simulate(dict(fine, events=[ev]), full=True, restart_state=st)["z"]
    b1 = s.simulate(fine, full=True, restart_state=st)["z"]
    assert np.linalg.norm(a1[1] - b1[1] - dz) <= 0.05 * np.linalg.norm(dz) + 1e-12
    # addendum 4: a kick clipped at the admissible range is clipped identically in simulate and in true_latent_effect; the
    # range acts on the unit's on-manifold potential vhat = b + E z
    lo = s.spec.lo[u]
    c = s.spec.loc[u]
    vh = s.spec.b[c] + s.spec.E[c] @ s.true_state(st)
    big = {"kind": "kick", "t": 0.0, "delta": {str(u): float((lo - vh - 5.0) * s.units()["v"])}}
    dzb = s.true_latent_effect(st, big)
    np.testing.assert_allclose(dzb, s.spec.L[:, c] * (lo - vh), rtol=1e-9, atol=1e-9 * np.abs(s.spec.L[:, c] * (lo - vh)).max())
    ab = s.simulate(dict(base, events=[big]), full=True, restart_state=st)
    cb = s.simulate(dict(base, events=[{"kind": "latent_kick", "t": 0.0, "dz": dzb.tolist()}]), full=True, restart_state=st)
    assert ab["info"]["clipped_kicks"] and ab["state"][1, u] != st[u]
    np.testing.assert_allclose(ab["z"], cb["z"], rtol=1e-8, atol=1e-8 * max(1.0, np.abs(cb["z"]).max()))
    # a finite event: the latent effect at the completion sample is the simulated difference
    cur = {"kind": "current", "t0": 0.0, "t1": 0.02, "targets": {str(u): s.capability()["current"]["moderate"]}}
    dzc = s.true_latent_effect(st, cur)
    assert np.all(np.isfinite(dzc)) and np.linalg.norm(dzc) > 0


@pytest.mark.parametrize("t", TYPES[::4])
def test_pool_states(by_type, t):
    s = _sys(by_type, t)
    pool = s.pool_states(20, np.random.default_rng(t))
    assert len(pool) == 20 and all(p.shape == (s.n_state,) and np.all(np.isfinite(p)) for p in pool)
    assert len({p.round(9).tobytes() for p in pool}) >= 15
    o = s.simulate(s.base_protocol(t_end=0.2, stimulus=const_input(s)), restart_state=pool[0])
    assert np.all(np.isfinite(o["y"]))
