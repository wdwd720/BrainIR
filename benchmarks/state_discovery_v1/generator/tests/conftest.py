import numpy as np
import pytest

from p3synth.systems import build_all


@pytest.fixture(scope="session")
def systems():
    return {s.meta["name"]: s for s in build_all(0, "dev")}


def sim(system, **kw):
    """Noise-free simulation helper: sim(s, t_end=.., stimulus=.., events=.., c0=.., params_seed=.., noise=False)."""
    from p3synth.diagnostics import protocol
    noise = kw.pop("noise", False)
    full = kw.pop("full", False)
    p = protocol(system, **kw)
    return system.simulate(p, noise=noise, full=full), p


def rest_coords(system, params_seed=0):
    th = system.model.latent.draw(params_seed)
    return system.model.rest(th)


def with_z(system, z, params_seed=0):
    c = rest_coords(system, params_seed).copy()
    c[: system.k] = z
    return c
