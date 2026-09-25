"""noise_seed: one noise realisation shared by protocols that differ only in their events."""
import numpy as np
import pytest

from p3synth.diagnostics import protocol

KEYS = ("x", "u", "y", "z")


def proto(s, events=(), noise_seed=None, **kw):
    p = protocol(s, t_end=3.0, stimulus=[[0.0, 0.0], [0.4, 1.0], [0.7, 0.0]] if s.input_dim == 1 else
                 [[0.0, [0.0] * s.input_dim], [0.4, [1.0] * s.input_dim], [0.7, [0.0] * s.input_dim]],
                 events=list(events), **kw)
    if noise_seed is not None:
        p["noise_seed"] = noise_seed
    return p


# hidden_exogenous: exogenous input; output_shortcut: fast block; groupB_impl2: partial observation, logistic
@pytest.mark.parametrize("name", ["leaky", "hidden_exogenous", "groupB_impl2", "nuisance_rhythm", "highdim_chaotic"])
def test_kick_twin_identical_before_kick(systems, name):
    s = systems[name]
    j = s.observed[0]
    a = s.simulate(proto(s, noise_seed=123))
    b = s.simulate(proto(s, [{"kind": "kick", "t": 1.5, "delta": {str(j): 1.0}}], noise_seed=123))
    for k in KEYS:
        assert np.array_equal(a[k][:151], b[k][:151]), k            # sample at the kick time is pre-kick
    assert not np.array_equal(a["x"][151:], b["x"][151:])
    if s.model.n_exo:
        assert np.array_equal(a["info"]["truth"]["exo"], b["info"]["truth"]["exo"])
    # the same protocol without events reproduces itself bitwise
    c = s.simulate(proto(s, noise_seed=123))
    for k in KEYS:
        assert np.array_equal(a[k], c[k])


def test_twin_identical_before_first_event_all_kinds(systems):
    s = systems["nuisance_ou"]
    ev = [{"kind": "current", "t0": 1.0, "t1": 1.5, "targets": {"3": 20.0}},
          {"kind": "silence", "t0": 1.2, "t1": 2.0, "targets": [4, 5, 6]},
          {"kind": "edge_remove", "t0": 1.1, "t1": None, "edges": [[1, 2], [7, 8]]}]
    a = s.simulate(proto(s, noise_seed=5))
    b = s.simulate(proto(s, ev, noise_seed=5))
    for k in KEYS:
        assert np.array_equal(a[k][:101], b[k][:101]), k


def test_noise_seed_governs_all_noise(systems):
    s = systems["hidden_exogenous"]
    a = s.simulate(proto(s, noise_seed=1))
    b = s.simulate(proto(s, noise_seed=2))
    assert not np.allclose(a["x"], b["x"])
    assert not np.allclose(a["info"]["truth"]["exo"], b["info"]["truth"]["exo"])
    # noise does not depend on the rest of the protocol when noise_seed is set: a different stimulus changes the
    # dynamics but not the observation-noise draw (x minus noise-free x is then identical on an unaffected stretch)
    p1 = proto(s, noise_seed=9)
    p2 = dict(p1, params_seed=0, stimulus=[[0.0, 0.0], [2.9, 0.5]])
    n1 = s.simulate(p1)["x"] - s.simulate(p1, noise=False)["x"]
    n2 = s.simulate(p2)["x"] - s.simulate(p2, noise=False)["x"]
    assert np.allclose(n1[0], n2[0])                                   # observation noise of the first sample


def test_without_noise_seed_behaviour_unchanged(systems):
    s = systems["leaky"]
    p = proto(s)
    a, b = s.simulate(p), s.simulate(dict(p, events=[{"kind": "kick", "t": 1.5, "delta": {"0": 1.0}}]))
    # canonical-protocol seeding: different events -> different noise realisation (legacy behaviour)
    assert not np.array_equal(a["x"][:100], b["x"][:100])
    assert not np.array_equal(a["x"], s.simulate(proto(s, noise_seed=0))["x"])
