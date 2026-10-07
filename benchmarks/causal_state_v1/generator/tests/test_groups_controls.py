"""Implementation groups (types 11, 12, 24), unrelated pairs, redundant realisations, nuisance / partial-observability structure and
the non-compressible controls (types 20, 21)."""

import numpy as np
import pytest

from conftest import const_input, f_s, mid_state
from p4synth.engine import CORE, FOL, GEN
from p4synth.suite import build_system


@pytest.mark.parametrize("t", [11, 12, 24])
def test_group_members_share_dynamics(by_type, t):
    a, b = by_type[t]
    assert a.info["implementation_group"] == b.info["implementation_group"]
    assert b.system_id in a.info["group_members"]
    assert (a.n_units, a.spec.Nc, len(a.observed)) != (b.n_units, b.spec.Nc, len(b.observed))      # different implementations
    k = a.spec.k
    assert b.spec.k == k
    for seed in (0, 11):
        ev = [{"kind": "latent_kick", "t": 0.8, "dz": (0.3 * np.asarray(a.spec.latent.z_scale)).tolist()}]
        pa = a.base_protocol(params_seed=seed, events=ev)
        pb = b.base_protocol(params_seed=seed, events=ev)
        oa, ob = a.simulate(pa, full=True), b.simulate(pb, full=True)
        # same z-dynamics (z-level parameter draws are shared); tau_c differs only in the off-manifold relaxation
        np.testing.assert_allclose(oa["z"], ob["z"], atol=1e-8)
        np.testing.assert_allclose(oa["y"], ob["y"], atol=1e-7)


def test_unrelated_pairs_differ(by_type):
    g11 = by_type[11][0]
    g12 = by_type[12][0]
    assert g12.system_id in g11.info["unrelated_systems"]
    decoy = build_system("conf", 0, 12, 2, 3)
    member = build_system("conf", 0, 12, 0, 3)
    assert decoy.info["implementation_group"] != member.info["implementation_group"]
    oa = decoy.simulate(decoy.base_protocol(), full=True)
    ob = member.simulate(member.base_protocol(), full=True)
    assert np.abs(oa["z"] - ob["z"]).max() > 0.1


def test_redundant_realisations(by_type):
    for s in by_type[24] + by_type[11]:
        classes = s.info["realisation_classes"]
        assert classes, s.info["variant"]
        st = mid_state(s)
        mk = s.capability()["kick"]["moderate"]
        cls = next(c for c in classes if len(c) >= 2)
        u, v = cls[0], cls[1]
        base = s.base_protocol(t_end=0.3, stimulus=const_input(s))
        dza = s.true_latent_effect(st, {"kind": "kick", "t": 0, "delta": {str(u): mk}})
        dzb = s.true_latent_effect(st, {"kind": "kick", "t": 0, "delta": {str(v): mk}})
        np.testing.assert_allclose(dza, dzb, atol=1e-12)
        ya = s.simulate(dict(base, events=[{"kind": "kick", "t": 0.02, "delta": {str(u): mk}}]), restart_state=st)["y"]
        yb = s.simulate(dict(base, events=[{"kind": "kick", "t": 0.02, "delta": {str(v): mk}}]), restart_state=st)["y"]
        np.testing.assert_allclose(ya, yb, rtol=1e-7, atol=1e-7)


def test_nuisance_units_dominate_variance(by_type):
    for s in by_type[14]:
        o = s.simulate(s.base_protocol(), full=True)
        X = o["x_all"]
        var = X.var(axis=0)
        core = s.spec.units_of(CORE)
        nuis = np.concatenate([s.spec.units_of(FOL), s.spec.units_of(GEN)])
        assert np.median(var[nuis]) > 5 * np.median(var[core])


def test_partial_observability_structure(by_type):
    for s in by_type[17]:
        sp = s.spec
        seen = [u for u in sp.units_of(CORE) if s.meta["unit_tag"][u] == "seen"]
        unseen = [u for u in sp.units_of(CORE) if s.meta["unit_tag"][u] == "unseen"]
        assert unseen and not set(unseen) & set(s.observed)
        hidden_dims = sorted({d for u in unseen for d in s.meta["unit_dims"][u]})
        for u in seen:
            assert not set(s.meta["unit_dims"][u]) & set(hidden_dims)
        # followers read only the seen population
        unseen_loc = [sp.loc[u] for u in unseen]
        assert np.all(sp.W_fc[:, unseen_loc] == 0)


@pytest.mark.parametrize("t", [20, 21])
def test_non_compressible_controls(by_type, t):
    """The benchmark calls a state compact when k <= q = max(1, floor(N_obs / 5)). PER SYSTEM (review round 3, B4): the readout
    responses to EVERY moderate single-unit kick and 50 ms pulse on the targetable core units (from the nominal states at 0.4 and
    0.8 t_end; controls.simulated_margin), at the primary horizon (0.25 s) AND a long horizon (1 s): the rank needed for 90 % of
    the responses within 1 f_s is >= 1.5 q, and the best rank-q basis misses more than half of the responses by more than 1 f_s.
    k_full >= 3 N_obs / 5. Type 21: passive trajectories from rest, restarts from nominal passive trajectories AND weight-noise
    trajectories (sd 0.02-0.1; review round 3, B2) stay in the m-dimensional subspace (hidden residual <= 1e-9 of its scale)."""
    from p4synth.controls import simulated_margin
    for s in by_type[t]:
        tr = s.truth(include_draw=False)
        n_obs = len(s.observed)
        assert tr["k"] == "none" and tr["k_full"] >= 3 * n_obs / 5 and "no compact" in tr["expected_verdict"]
        mg = simulated_margin(s)
        print(f"T{t}-{s.info['variant']}: N_obs {n_obs}, " + ", ".join(
            f"H {h} s: bound {v['bound']}, rank needed {v['need']} ({v['ratio']:.2f} x), rank-bound residual median "
            f"{v['resid_median']:.2f} f_s, frac > 1 f_s {v['frac_gt_fs']:.2f}" for h, v in mg.items())
            + f"; build attempt {s.info.get('control_margin', {}).get('attempt')}")
        for h, v in mg.items():
            assert v["ratio"] >= 1.5 and v["frac_gt_fs"] > 0.5, (s.info["variant"], h, v)
        if t == 21:
            m = s.spec.latent.m
            Zs = []
            for sd, wn in ((0, None), (4, None), (4, {"sd": 0.02, "seed": 1}), (7, {"sd": 0.1, "seed": 2}),
                           (9, {"sd": 0.1, "seed": 5})):
                for lv in (0.6, 1.0, 1.4):
                    oo = s.simulate(s.base_protocol(params_seed=sd, weight_noise=wn, stimulus=s.nominal_stimulus(lv)), full=True)
                    Zs.append(oo["z"])
                    for ti in (0.5, 1.2):      # nominal restarts: a restart from a sample of a nominal passive trajectory
                        i = int(round(ti / s.dt))
                        Zs.append(s.simulate(s.base_protocol(params_seed=sd, weight_noise=wn, t_end=0.5,
                                                             stimulus=[[0.0, 0.8], [0.2, 1.3]]),
                                             full=True, restart_state=oo["state"][i])["z"])
            Z = np.vstack(Zs)
            svp = np.linalg.svd(Z, compute_uv=False)
            res = np.abs(s.spec.latent.zres(Z)).max() / max(1.0, float(np.abs(Z).max()))
            print(f"  type-21 passive design incl. weight noise: rank {int((svp > 1e-8 * svp[0]).sum())} (m = {m}), max hidden "
                  f"residual {res:.1e} of the z scale")
            assert int((svp > 1e-8 * svp[0]).sum()) == m and res <= 1e-9
