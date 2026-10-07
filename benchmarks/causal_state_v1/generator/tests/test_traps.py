"""The central trap (types 15, 21, 22, 25 and trap variants of 5, 6, 8, 9, 10, 16, 18, 23): z_obs is sufficient on passive data
(the hidden residual zres, the part of z not determined by z_obs, is zero or small on passive trajectories) but insufficient under
the exposing interventions (microscopic interventions move zres, and states with equal z_obs but different z have different readout
futures)."""

import numpy as np
import pytest

from conftest import SEEDS, const_input, f_s, get_suite, mid_state

TRAPS = [(sd, sid) for sd in SEEDS for sid, s in get_suite(sd).items() if s.info["trap"] is not None]


class _Lookup:
    def __getitem__(self, key):
        sd, sid = key
        return get_suite(sd)[sid]


SUITE = _Lookup()
# passive residual bound relative to the hidden dimensions' operational scale, by grade keyword
GRADE_TOL = {"hard": 1e-3, "medium": 0.08, "easy": 0.35, "control": 1e-3}


def _grade_tol(s):
    g = str(s.info["trap_grade"])
    for key, tol in GRADE_TOL.items():
        if g.startswith(key):
            return tol
    return 0.35


def _zres(s, Z, seed=0):
    sd, spread = seed if isinstance(seed, tuple) else (seed, 1.0)
    return s.spec.latent.zres(np.atleast_2d(Z), s._draw(sd, spread, None).P)



def _res_scale(s):
    lat = s.spec.latent
    zs = np.asarray(lat.z_scale)
    r = lat.zres(np.diag(zs), lat.nominal())
    r0 = lat.zres(np.zeros((1, lat.k)), lat.nominal())
    return max(float(np.abs(r - r0).max()), 1e-6)


def _exposing_unit(s, st):
    """The targetable core unit whose kick moves the hidden residual most."""
    sp = s.spec
    z0 = s.true_state(st)
    mk = s.capability()["kick"]["moderate"] / s.units()["v"]         # internal units (dz = L delta)
    best, bu = -1.0, None
    for u in s.core_targets():
        dz = sp.L[:, sp.loc[u]] * 3 * mk
        ch = max(np.abs(_zres(s, z0 + dz) - _zres(s, z0)).max(), np.abs(_zres(s, z0 - dz) - _zres(s, z0)).max())
        if ch > best:
            best, bu = ch, u
    if best < 1e-9:       # residual reachable only through the dynamics (e.g. a threshold-triggered hidden mode): simulate
        base = s.base_protocol(t_end=0.3, stimulus=const_input(s))
        for u in s.core_targets()[:24]:
            for sgn in (1.0, -1.0):
                o = s.simulate(dict(base, events=[{"kind": "kick", "t": 0.02, "delta": {str(u): sgn * 9 * mk}}]), full=True,
                               restart_state=st)
                ch = float(np.abs(_zres(s, o["z"]) - _zres(s, z0)).max())
                if ch > best:
                    best, bu = ch, u
    return bu


def _passive_runs(s):
    """Passive trajectories over the benchmark's passive design (input levels 0.55-1.45, a multi-step schedule), parameter draws
    at params_spread 1 and 2 (the declared bound holds for both)."""
    runs = []
    for seed, spread in ((0, 1.0), (3, 1.0), (11, 2.0), (12, 2.0)):
        for st in (s.nominal_stimulus(0.55), s.nominal_stimulus(1.0), s.nominal_stimulus(1.45),
                   [[0.0, 0.0], [0.1, 0.6], [0.7, 1.4], [1.3, 0.8]]):
            o = s.simulate(s.base_protocol(params_seed=seed, params_spread=spread, stimulus=st), full=True)
            runs.append(((seed, spread), o))
    return runs


def _exposing_protocols(s, st):
    """Exposing interventions on the most exposing targetable core unit(s): single kicks (strong and kick.hi), a group kick on
    the three most exposing units, and a sustained current."""
    cap = s.capability()
    mk, mc = cap["kick"]["moderate"], cap["current"]["moderate"]
    u = _exposing_unit(s, st)
    evs = []
    for sgn in (1.0, -1.0):
        evs.append([{"kind": "kick", "t": 0.05, "delta": {str(u): sgn * 3 * mk}}])
        evs.append([{"kind": "kick", "t": 0.05, "delta": {str(u): sgn * 9 * mk}}])
        evs.append([{"kind": "current", "t0": 0.05, "t1": 0.35, "targets": {str(u): sgn * 3 * mc}}])
    # group kicks: the three targetable core units loading most on each latent dimension, sign-aligned (kick.g, 3 m_s each)
    sp = s.spec
    tg = s.core_targets()
    Lt = np.array([sp.L[:, sp.loc[x]] for x in tg])
    for d in range(sp.k):
        top = np.argsort(-np.abs(Lt[:, d]))[:3]
        for sgn in (1.0, -1.0):
            evs.append([{"kind": "kick", "t": 0.05, "delta": {str(tg[i]): float(sgn * np.sign(Lt[i, d]) * 3 * mk) for i in top}}])
    base = s.base_protocol(t_end=0.6, stimulus=const_input(s))
    return [dict(base, events=e) for e in evs]


@pytest.mark.parametrize("sid", TRAPS, ids=[f"{a}-{b}" for a, b in TRAPS])
def test_passive_residual_small_exposed_residual_large(sid):
    s = SUITE[sid]
    sc = _res_scale(s)
    passive = max(float(np.abs(_zres(s, o["z"], seed)).max()) for seed, o in _passive_runs(s))
    st = mid_state(s)
    exposed = max(float(np.abs(_zres(s, s.simulate(p, full=True, restart_state=st)["z"])).max()) for p in _exposing_protocols(s, st))
    bound = s.info["passive_residual_bound"]
    assert passive <= bound * sc, (s.info["type"], s.info["variant"], passive, bound, sc)
    assert exposed >= max(0.1 * sc, 1.5 * passive), (s.info["type"], s.info["variant"], passive, exposed, sc)


@pytest.mark.parametrize("sid", TRAPS, ids=[f"{a}-{b}" for a, b in TRAPS])
def test_equal_zobs_different_futures(sid):
    """Two microstates with the same z_obs but different hidden residual (a truth-level do() on the hidden directions) have
    different readout futures - passively or under the exposing intervention."""
    s = SUITE[sid]
    lat = s.spec.latent
    st = mid_state(s)
    z = s.true_state(st)
    k = lat.k
    J = np.stack([(lat.zobs((z + 1e-4 * np.eye(k)[i])[None])[0] - lat.zobs(z[None])[0]) / 1e-4 for i in range(k)], axis=1)
    _, sv, Vt = np.linalg.svd(J)
    null = Vt[(sv > 1e-8).sum():]
    assert null.shape[0] >= 1
    zs = np.asarray(lat.z_scale)
    fs = f_s(s)
    u = _exposing_unit(s, st)
    mk = s.capability()["kick"]["moderate"]
    base = s.base_protocol(t_end=0.5, stimulus=const_input(s))
    best = 0.0
    for d in null[:4]:
        for amp in (0.5, 1.0):
            dz = amp * d / np.linalg.norm(d / zs)
            st2 = s._set_z(st, z + dz)
            np.testing.assert_allclose(s.obs_shortcut_state(st2), s.obs_shortcut_state(st), atol=1e-8)
            for ev in ([], [{"kind": "kick", "t": 0.05, "delta": {str(u): 3 * mk}}],
                       [{"kind": "kick", "t": 0.05, "delta": {str(u): -3 * mk}}]):
                a = s.simulate(dict(base, events=ev), restart_state=st)["y"]
                b = s.simulate(dict(base, events=ev), restart_state=st2)["y"]
                best = max(best, float(np.sqrt(np.mean((a - b) ** 2))))
    assert best > 2 * fs, (s.info["type"], s.info["variant"], best, fs)


def test_trap_types_present():
    types = {SUITE[sid].info["type"] for sid in TRAPS}
    for t in (15, 21, 22, 25):
        assert t in types
    assert len(types) >= 6
