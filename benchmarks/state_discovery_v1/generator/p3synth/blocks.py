"""Auxiliary coordinate blocks: variables carried by neurons that are NOT part of the causal latent z.

Each block has its own coordinates (appended after z), its own dynamics (which may read z, u or theta but never feed back
into z) and is embedded into neurons like z. Kicking or silencing neurons that only carry block coordinates therefore
never changes z or y (they are non-causal for the readout), which is exactly what the traps need.
"""

from __future__ import annotations

import math

import numpy as np


class Block:
    name = "aux"
    role = "aux"
    dim = 1
    h_max = 1.0

    def f(self, cb, c, u, th, model):
        return np.zeros(self.dim)

    def rest(self, z, th, model):
        return np.zeros(self.dim)

    def sigma(self, th):
        return 0.0

    def init(self, rng, z0, th, model, heldout=False):
        return self.rest(z0, th, model)

    def describe(self) -> str:
        return ""


class NuisanceOU(Block):
    """m independent Ornstein-Uhlenbeck processes (optionally stimulus driven): d xi = (-xi/tau + B u) dt + s dW."""
    name, role = "nuis", "nuisance"

    def __init__(self, rng, m=3, sd=1.0, tau=(0.15, 0.8), n_u=1, stim_gain=0.0):
        self.dim = int(m)
        self.tau = rng.uniform(*tau, self.dim)
        self.sd = np.broadcast_to(np.asarray(sd, float), (self.dim,)).copy()
        self.B = rng.standard_normal((self.dim, n_u)) * stim_gain
        self.stim_gain = stim_gain
        self.h_max = 0.3 * float(self.tau.min())

    def f(self, cb, c, u, th, model):
        return -cb / self.tau + self.B @ u

    def sigma(self, th):
        return self.sd * np.sqrt(2.0 / self.tau)

    def init(self, rng, z0, th, model, heldout=False):
        return self.sd * rng.standard_normal(self.dim) * (1.3 if heldout else 1.0)

    def describe(self):
        return (f"{self.dim} OU processes, tau {np.round(self.tau, 3).tolist()} s, stationary sd {np.round(self.sd, 3).tolist()}"
                + (f", stimulus-driven (gain {self.stim_gain})" if self.stim_gain else ""))


class NuisanceOsc(Block):
    """A nuisance rhythm: noisy Hopf oscillator unrelated to the latent (and to u)."""
    name, role = "rhythm", "nuisance"
    dim = 2
    h_max = 0.0025

    def __init__(self, rng, R=2.0, f0=None, mu=3.0, sigma=0.3):
        self.R = float(R)
        self.f0 = float(f0 if f0 is not None else rng.uniform(2.0, 4.0))
        self.mu = mu
        self.s = sigma

    def f(self, cb, c, u, th, model):
        a = self.mu * (1.0 - (cb[0] ** 2 + cb[1] ** 2) / self.R ** 2)
        w = 2 * math.pi * self.f0
        return np.array([a * cb[0] - w * cb[1], a * cb[1] + w * cb[0]])

    def rest(self, z, th, model):
        return np.array([self.R, 0.0])

    def sigma(self, th):
        return self.s

    def init(self, rng, z0, th, model, heldout=False):
        ph = rng.uniform(0, 2 * math.pi)
        return self.R * np.array([math.cos(ph), math.sin(ph)])

    def describe(self):
        return f"nuisance rhythm (Hopf, radius {self.R}, {self.f0:.2f} Hz), independent of z and u"


class Persistent(Block):
    """Persistent null code: coordinates with no dynamics (slow diffusion only) that change the microstate but not z."""
    name, role = "null", "null_code"

    def __init__(self, rng, m=2, amp=1.0, diffusion=0.02):
        self.dim = int(m)
        self.amp = amp
        self.diff = diffusion

    def sigma(self, th):
        return self.diff

    def init(self, rng, z0, th, model, heldout=False):
        return self.amp * rng.standard_normal(self.dim) * (1.4 if heldout else 1.0)

    def describe(self):
        return f"{self.dim} persistent null-space coordinates (d psi = {self.diff} dW), set by initial conditions and kicks"


class ReadoutCopy(Block):
    """Trap B: neurons that follow the readout y with a short lag: tau dc = g(z) - c."""
    name, role = "ycopy", "readout_copy"

    def __init__(self, n_y=1, tau=0.01):
        self.dim = int(n_y)
        self.tau = tau
        self.h_max = 0.3 * tau

    def f(self, cb, c, u, th, model):
        return (model.y(c, th) - cb) / self.tau

    def rest(self, z, th, model):
        return np.asarray(model.latent.g(z, th), float)

    def init(self, rng, z0, th, model, heldout=False):
        return self.rest(z0, th, model)

    def describe(self):
        return f"copy of the readout, tau = {self.tau} s (downstream only)"


class Clock(Block):
    """Trap C: time since trial start (dc/dt = 1), carried by ramping neurons."""
    name, role = "clock", "clock"
    dim = 1

    def f(self, cb, c, u, th, model):
        return np.ones(1)

    def describe(self):
        return "clock: dc/dt = 1 from c = 0 at t = 0 (ramping neurons with staggered saturation)"


class StimCopy(Block):
    """Trap D: neurons that low-pass the stimulus: tau dc = u - c."""
    name, role = "ucopy", "stimulus_copy"

    def __init__(self, n_u=1, tau=0.02):
        self.dim = int(n_u)
        self.tau = tau
        self.h_max = 0.3 * tau

    def f(self, cb, c, u, th, model):
        return (u - cb) / self.tau

    def describe(self):
        return f"stimulus copy, tau = {self.tau} s (driven by u, never feeds z)"


class ParamReport(Block):
    """Trap H: neurons that report a parameter of the current draw: tau dc = theta[key] - c."""
    name, role = "param", "parameter_report"
    dim = 1

    def __init__(self, key, tau=0.05):
        self.key = key
        self.tau = tau

    def f(self, cb, c, u, th, model):
        return (th[self.key] - cb) / self.tau

    def rest(self, z, th, model):
        return np.array([th[self.key]])

    def init(self, rng, z0, th, model, heldout=False):
        return np.array([th[self.key]])

    def describe(self):
        return f"reports parameter {self.key!r} of the draw (relaxes to it with tau = {self.tau} s)"
