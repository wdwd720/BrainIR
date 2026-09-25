"""Implementations in one group share one latent dynamic; unrelated pairs do not."""
import numpy as np
import pytest

from p3synth.systems import get_system

from conftest import sim, with_z

GROUPS = {"A": ["groupA_impl0", "groupA_impl1", "groupA_impl2", "groupA_impl3"],
          "B": ["groupB_impl0", "groupB_impl1", "groupB_impl2"]}


@pytest.mark.parametrize("g", ["A", "B"])
def test_group_members_share_latent_dynamics(systems, g):
    members = [systems[n] for n in GROUPS[g]]
    rng = np.random.default_rng(0)
    for ps in (0, 5, 1003):
        th0 = members[0].model.latent.draw(ps)
        z0 = members[0].model.latent.sample_init(rng, th0)
        stim = [[0.0, [0.0] * members[0].input_dim], [0.5, [0.8] * members[0].input_dim], [1.0, [0.0] * members[0].input_dim]]
        zs, ys = [], []
        for s in members:
            th = s.model.latent.draw(ps)
            assert all(np.allclose(th[k], th0[k]) for k in th0)
            out, _ = sim(s, t_end=3.0, c0=with_z(s, z0, ps), stimulus=stim, params_seed=ps)
            zs.append(out["z"]); ys.append(out["y"])
        for z, y in zip(zs[1:], ys[1:]):
            # identical up to integration error (members may use different substeps because of their nuisance blocks)
            assert np.abs(z - zs[0]).max() < 1e-5 and np.abs(y - ys[0]).max() < 1e-5


@pytest.mark.parametrize("g", ["A", "B"])
def test_group_members_differ_in_implementation(systems, g):
    members = [systems[n] for n in GROUPS[g]]
    ns = [s.n for s in members]
    assert len(set(ns)) == len(ns)                                     # neuron counts
    assert len({s.impl.spec["code"] for s in members}) >= 3             # observation mixing / redundancy / connectivity
    assert len({s.model.K for s in members}) >= 2                       # nuisance dynamics present in some
    assert len({s.impl.spec["phi"] for s in members}) >= 2              # activation (observation nonlinearity)
    # permuted neuron ids: the latent-carrying neurons are not a contiguous block
    for s in members:
        lat = [i for i, r in enumerate(s.impl.roles) if r.startswith("latent")]
        if len(lat) < s.n:
            assert lat != list(range(len(lat)))


def test_group_shared_when_built_separately():
    a = get_system("groupA_impl0")
    b = get_system("groupA_impl3")
    assert a.model.latent.draw(7)["f0"] == b.model.latent.draw(7)["f0"]
    t = a.truth()
    assert t["implementation_group"] == b.truth()["implementation_group"] == "grp-A"


@pytest.mark.parametrize("pair", [("pairP1_a", "pairP1_b"), ("pairP2_a", "pairP2_b"), ("pairP3_a", "pairP3_b")])
def test_unrelated_pairs(systems, pair):
    a, b = systems[pair[0]], systems[pair[1]]
    # identical implementations (same neurons, embedding, readout dims) ...
    assert a.n == b.n and np.allclose(a.impl.E, b.impl.E) and np.allclose(a.impl.D, b.impl.D) and a.observed == b.observed
    assert a.input_dim == b.input_dim and a.readout_dim == b.readout_dim and a.k == b.k
    # ... but different latent dynamics: different vector fields on the same states and different trajectories
    rng = np.random.default_rng(1)
    ta, tb = a.model.latent.draw(0), b.model.latent.draw(0)
    Z = rng.uniform(-1, 1, (200, a.k))
    u = np.zeros(a.input_dim)
    fa = np.array([a.model.latent.f(z, u, None, ta) for z in Z])
    fb = np.array([b.model.latent.f(z, u, None, tb) for z in Z])
    assert np.linalg.norm(fa - fb) > 0.3 * np.linalg.norm(fa)
    z0 = np.full(a.k, 0.6)
    oa, _ = sim(a, t_end=4.0, c0=with_z(a, z0))
    ob, _ = sim(b, t_end=4.0, c0=with_z(b, z0))
    assert np.abs(oa["z"] - ob["z"]).max() > 0.3
    assert a.truth()["implementation_group"] != b.truth()["implementation_group"]
