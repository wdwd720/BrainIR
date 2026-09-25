"""Latent dynamics (the causal state z in R^k): one class per dynamical family.

Every latent has a fixed TYPE and a centre parameter vector drawn once from its construction seed; `draw(params_seed)`
returns one parameter draw within the family (timescales, gains, noise: log-normal spread around the centre). Systems
that share a Latent object (implementation groups) therefore share f exactly for equal params_seed.

Units: time in seconds; z is O(1). f is written for a single state vector (numpy, shape (k,)).
"""

from __future__ import annotations

import math

import numpy as np

TWO_PI = 2.0 * math.pi


def logistic(x):
    return 1.0 / (1.0 + np.exp(-x))


class Latent:
    family = ""
    variant = ""
    k = 1
    n_u = 1
    n_y = 1
    n_exo = 0
    h_max = 0.005
    amp = 1.0

    def __init__(self, seed: int, **kw):
        self.seed = int(seed)
        self.kw = dict(kw)
        rng = np.random.default_rng([self.seed, 7777])
        self.center: dict = {}
        self.logsd: dict = {}
        self.input_pattern = np.ones(self.n_u)
        self.channels = [("analog", 1.0)] * self.n_u
        self.setup(rng, **{k_: v_ for k_, v_ in kw.items() if k_ != "center_override"})
        self.center.update(kw.get("center_override") or {})
        self.input_pattern = np.asarray(self.input_pattern, float)
        self._cache: dict = {}

    # to override -------------------------------------------------------------
    def setup(self, rng, **kw):
        pass

    def derive(self, th, rng):
        pass

    def f(self, z, u, exo, th):
        raise NotImplementedError

    def g(self, z, th):
        return z[:1].copy()

    def rest(self, th):
        return np.zeros(self.k)

    def sigma(self, th):
        return th.get("sigma", 0.0)

    def describe(self) -> dict:
        return {"f": "", "g": "", "notes": ""}

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [0.8, 0.0]]

    def sample_init(self, rng, th, heldout=False):
        """Initial latent state for the suite builder (train: radius <= 1 amp; held-out: radius in [1, 1.5] amp)."""
        d = rng.standard_normal(self.k)
        d /= np.linalg.norm(d) + 1e-12
        r = rng.uniform(1.0, 1.5) if heldout else rng.uniform(0.0, 1.0) ** (1.0 / self.k)
        return self.rest(th) + self.amp * r * d

    def exo_signal(self, rng, T, dt, th):
        return None

    # generic ---------------------------------------------------------------
    def draw(self, params_seed: int) -> dict:
        params_seed = int(params_seed)
        if params_seed not in self._cache:
            rng = np.random.default_rng([self.seed, 1, params_seed])
            th = {}
            for name in sorted(self.center):
                val = np.asarray(self.center[name], float)
                sd = self.logsd.get(name, 0.0)
                eps = rng.standard_normal(val.shape)
                th[name] = val * np.exp(sd * eps) if sd else val.copy()
                if th[name].ndim == 0:
                    th[name] = float(th[name])
            self.derive(th, rng)
            self._cache[params_seed] = th
        return self._cache[params_seed]

    def info(self) -> dict:
        d = self.describe()
        return {"family": self.family, "variant": self.variant, "k": self.k, "input_dim": self.n_u, "readout_dim": self.n_y,
                "exogenous_dim": self.n_exo, "theta_center": {k: np.asarray(v).tolist() for k, v in self.center.items()},
                "theta_logsd": dict(self.logsd), "f": d["f"], "g": d["g"], "notes": d.get("notes", ""),
                "timescales": d.get("timescales", "")}


# ============================================================================ 1 linear stable
class LinearStable(Latent):
    family, variant = "linear_stable", "k"

    def __init__(self, seed, k=2, n_u=1, n_y=1, osc=None, **kw):
        self.k, self.n_u, self.n_y = int(k), int(n_u), int(n_y)
        self._osc = osc
        super().__init__(seed, **kw)
        self.variant = f"k{self.k}"

    def setup(self, rng, **kw):
        k = self.k
        n_pairs = self._osc if self._osc is not None else int(rng.integers(0, k // 2 + 1))
        n_pairs = min(n_pairs, k // 2)
        self.n_pairs = n_pairs
        self.center["tau_real"] = rng.uniform(0.15, 1.0, k - 2 * n_pairs)
        self.center["tau_osc"] = rng.uniform(0.35, 1.2, n_pairs)
        self.center["f_osc"] = rng.uniform(0.4, 1.5, n_pairs)
        self.center["sigma"] = 0.03
        self.logsd.update(tau_real=0.15, tau_osc=0.15, f_osc=0.1, sigma=0.3)
        Q, _ = np.linalg.qr(rng.standard_normal((k, k)))
        self.S = Q * rng.uniform(0.7, 1.3, k)
        self.Si = np.linalg.inv(self.S)
        B = rng.standard_normal((k, self.n_u))
        self.B0 = B / np.linalg.norm(B, axis=0, keepdims=True) * 3.0
        self.C = rng.standard_normal((self.n_y, k)) / math.sqrt(k)
        self.C /= np.maximum(np.linalg.norm(self.C, axis=1, keepdims=True), 1e-9)

    def derive(self, th, rng):
        k = self.k
        Lb = np.zeros((k, k))
        j = 0
        for tau, fr in zip(np.atleast_1d(th["tau_osc"]), np.atleast_1d(th["f_osc"])):
            w = TWO_PI * fr
            Lb[j:j + 2, j:j + 2] = [[-1 / tau, w], [-w, -1 / tau]]
            j += 2
        for tau in np.atleast_1d(th["tau_real"]):
            Lb[j, j] = -1 / tau
            j += 1
        th["_A"] = self.S @ Lb @ self.Si
        th["_B"] = self.B0
        th["A"] = th["_A"]

    def f(self, z, u, exo, th):
        return th["_A"] @ z + th["_B"] @ u

    def g(self, z, th):
        return self.C @ z

    def describe(self):
        return {"f": "dz/dt = A z + B u, A = S blockdiag(-1/tau_real; [[-1/tau, w], [-w, -1/tau]]) S^-1 (stable)",
                "g": "y = C z", "timescales": "tau_real in [0.15, 1] s, oscillatory modes 0.4-1.5 Hz with decay 0.35-1.2 s",
                "notes": "every latent direction is excited by u (B generic) and visible in y only through C"}


# ============================================================================ 2-4 oscillators
class Harmonic(Latent):
    family, variant = "harmonic_oscillator", "undamped"
    k = 2

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.7, 1.5), gain=1.0, sigma=0.02)
        self.logsd.update(f0=0.12, gain=0.15, sigma=0.3)

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        return np.array([w * z[1], -w * z[0] + w * th["gain"] * u[0]])

    def describe(self):
        return {"f": "dz1 = w z2, dz2 = -w z1 + w g u  (w = 2 pi f0)", "g": "y = z1", "timescales": "f0 in 0.7-1.5 Hz",
                "notes": "energy z1^2+z2^2 conserved without input; phase AND amplitude are state"}


class Duffing(Latent):
    family, variant = "nonlinear_oscillator", "duffing"
    k = 2

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.6, 1.2), beta=rng.uniform(0.8, 1.5), gain=1.0, sigma=0.02)
        self.logsd.update(f0=0.12, beta=0.2, gain=0.15, sigma=0.3)

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        return np.array([w * z[1], -w * (z[0] + th["beta"] * z[0] ** 3) + w * th["gain"] * u[0]])

    def describe(self):
        return {"f": "dz1 = w z2, dz2 = -w (z1 + beta z1^3) + w g u (conservative hardening Duffing)", "g": "y = z1",
                "timescales": "small-amplitude frequency 0.6-1.2 Hz, frequency increases with amplitude",
                "notes": "frequency depends on energy: phase alone does not predict the future"}


class Damped(Latent):
    family, variant = "damped_oscillator", "linear"
    k = 2

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.7, 1.5), zeta=rng.uniform(0.08, 0.25), gain=1.0, sigma=0.03)
        self.logsd.update(f0=0.12, zeta=0.2, gain=0.15, sigma=0.3)

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        return np.array([w * z[1], -w * z[0] - 2 * th["zeta"] * w * z[1] + w * th["gain"] * u[0]])

    def describe(self):
        return {"f": "dz1 = w z2, dz2 = -w z1 - 2 zeta w z2 + w g u", "g": "y = z1",
                "timescales": "f0 0.7-1.5 Hz, zeta 0.08-0.25 (decay time 1/(zeta w) ~ 0.4-3 s)"}


# ============================================================================ 5 limit cycles
class Hopf(Latent):
    family, variant = "limit_cycle", "hopf"
    k = 2

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.6), mu=rng.uniform(3.0, 6.0), R=1.0, gain=1.5, sigma=0.03)
        self.logsd.update(f0=0.12, mu=0.2, R=0.1, gain=0.15, sigma=0.3)

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        a = th["mu"] * (1.0 - (z[0] * z[0] + z[1] * z[1]) / th["R"] ** 2)
        return np.array([a * z[0] - w * z[1] + th["gain"] * u[0], a * z[1] + w * z[0]])

    def rest(self, th):
        return np.array([th["R"], 0.0])

    def sample_init(self, rng, th, heldout=False):
        ph = rng.uniform(0, TWO_PI)
        r = rng.uniform(1.2, 1.6) if heldout else rng.uniform(0.05, 1.2)
        return th["R"] * r * np.array([math.cos(ph), math.sin(ph)])

    def describe(self):
        return {"f": "Hopf normal form: dz = mu (1 - |z|^2/R^2) z + w J z + (g u, 0)", "g": "y = z1",
                "timescales": "0.8-1.6 Hz, radial attraction mu 3-6 /s", "notes": "rest (r0 zero) = point (R, 0) on the cycle"}


class VanDerPol(Latent):
    family, variant = "limit_cycle", "van_der_pol"
    k = 2
    h_max = 0.002

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.6, 1.2), mu=rng.uniform(0.8, 2.0), gain=1.0, sigma=0.03)
        self.logsd.update(f0=0.12, mu=0.2, gain=0.15, sigma=0.3)

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        return np.array([w * z[1], w * (-z[0] + th["mu"] * (1.0 - 4.0 * z[0] ** 2) * z[1]) + w * th["gain"] * u[0]])

    def rest(self, th):
        return np.array([1.0, 0.0])

    def describe(self):
        return {"f": "van der Pol (rescaled so the cycle amplitude is ~1): dz1 = w z2, dz2 = w(-z1 + mu (1 - 4 z1^2) z2) + w g u",
                "g": "y = z1", "timescales": "0.6-1.2 Hz, mu 0.8-2 (relaxation-like for larger mu)"}


# ============================================================================ 6 bistable
class Bistable1D(Latent):
    family, variant = "bistable_switch", "double_well"
    k = 1

    def setup(self, rng, **kw):
        self.center.update(tau=rng.uniform(0.1, 0.25), gain=1.0, sigma=0.05)
        self.logsd.update(tau=0.15, gain=0.15, sigma=0.3)
        self.amp = 1.3

    def f(self, z, u, exo, th):
        return (z - z ** 3 + th["gain"] * u[:1]) / th["tau"]

    def rest(self, th):
        return np.array([-1.0])

    def sample_init(self, rng, th, heldout=False):
        return np.array([rng.uniform(1.2, 1.8) * rng.choice([-1, 1]) if heldout else rng.uniform(-1.2, 1.2)])

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [0.7, 0.0], [1.8, -1.0], [2.0, 0.0]]

    def describe(self):
        return {"f": "tau dz = z - z^3 + g u (wells at +-1, saddle at 0; |g u| > 0.385 removes one well)", "g": "y = z",
                "timescales": "tau 0.1-0.25 s"}


class Toggle(Latent):
    family, variant = "bistable_switch", "mutual_inhibition"
    k, n_u, n_y = 2, 2, 1

    def setup(self, rng, **kw):
        self.center.update(tau=rng.uniform(0.08, 0.2), beta=rng.uniform(4.5, 6.0), gain=4.0, sigma=0.03)
        self.logsd.update(tau=0.15, beta=0.08, gain=0.15, sigma=0.3)
        self.input_pattern = [1.0, -1.0]
        self.amp = 0.6

    def f(self, z, u, exo, th):
        be, g = th["beta"], th["gain"]
        s1 = 0.5 * (1 + np.tanh(be * (0.5 - z[1]) + g * u[0]))
        s2 = 0.5 * (1 + np.tanh(be * (0.5 - z[0]) + g * u[1]))
        return np.array([(-z[0] + s1) / th["tau"], (-z[1] + s2) / th["tau"]])

    def g(self, z, th):
        return np.array([z[0] - z[1]])

    def rest(self, th):
        z = np.array([1.0, 0.0])
        for _ in range(200):
            z = z + 0.2 * th["tau"] * self.f(z, np.zeros(2), None, th)
        return z

    def sample_init(self, rng, th, heldout=False):
        return rng.uniform(-0.3, 1.3, 2) if heldout else rng.uniform(0.0, 1.0, 2)

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, -1.0], [0.8, 0.0], [2.0, 1.0], [2.3, 0.0]]

    def describe(self):
        return {"f": "tau dz1 = -z1 + S(beta (1/2 - z2) + g u1), tau dz2 = -z2 + S(beta (1/2 - z1) + g u2), S(a) = (1 + tanh a)/2",
                "g": "y = z1 - z2", "timescales": "tau 0.08-0.2 s", "notes": "two stable states (1,0) and (0,1); nominal pattern u = s (1, -1)"}


# ============================================================================ 7-9 integrators
class Leaky(Latent):
    family, variant = "leaky_integrator", "1d"
    k = 1

    def setup(self, rng, tau_range=(0.3, 0.8), **kw):
        self.center.update(tau=rng.uniform(*tau_range), gain=1.0, sigma=0.03)
        self.logsd.update(tau=0.15, gain=0.15, sigma=0.3)

    def f(self, z, u, exo, th):
        return (-z + th["gain"] * u[:1]) / th["tau"]

    def g(self, z, th):
        return z.copy()

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [1.5, 0.0]]

    def describe(self):
        return {"f": "tau dz = -z + g u", "g": "y = z", "timescales": "tau 0.3-0.8 s"}


class Perfect(Latent):
    family, variant = "perfect_integrator", "1d"
    k = 1

    def __init__(self, seed, k=1, **kw):
        self.k = self.n_u = self.n_y = int(k)
        super().__init__(seed, **kw)
        self.variant = f"{self.k}d"

    def setup(self, rng, **kw):
        self.center.update(gain=1.0, sigma=0.02)
        self.logsd.update(gain=0.15, sigma=0.3)
        M = np.eye(self.k) + 0.3 * rng.standard_normal((self.k, self.k)) * (self.k > 1)
        self.M = M

    def f(self, z, u, exo, th):
        return th["gain"] * (self.M @ u)

    def g(self, z, th):
        return z.copy()

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [1.0, 0.0], [2.0, -0.5], [2.4, 0.0]]

    def describe(self):
        return {"f": "dz = g M u (no leak)", "g": "y = z", "timescales": "none intrinsic (memory is permanent; noise diffuses)",
                "notes": "marginally stable: structural weight noise makes it leaky or unstable"}


class Gated(Latent):
    family, variant = "gated_integrator", "gate_channel"
    k, n_u, n_y = 1, 2, 1

    def setup(self, rng, **kw):
        self.center.update(gain=1.2, tau_leak=rng.uniform(4.0, 8.0), sigma=0.02)
        self.logsd.update(gain=0.15, tau_leak=0.2, sigma=0.3)
        self.channels = [("analog", 1.5), ("binary", 1.0)]

    def f(self, z, u, exo, th):
        gate = logistic(12.0 * (u[1] - 0.5))
        return th["gain"] * gate * u[:1] - z / th["tau_leak"]

    def g(self, z, th):
        return z.copy()

    def nominal_stimulus(self, t_end):
        return [[0.0, [0.0, 0.0]], [0.5, [1.0, 1.0]], [1.0, [1.0, 0.0]], [1.5, [-1.0, 0.0]], [2.0, [-0.5, 1.0]], [2.4, [0.0, 0.0]]]

    def describe(self):
        return {"f": "dz = g * sigmoid(12 (u2 - 0.5)) * u1 - z / tau_leak", "g": "y = z",
                "timescales": "integration only while the gate channel u2 ~ 1; slow leak 4-8 s",
                "notes": "u1 alone (gate closed) has no effect: input direction is controllable only when gated"}


# ============================================================================ 10 winner-take-all
class WTA(Latent):
    family, variant = "winner_take_all", "3way"
    k = n_u = n_y = 3

    def setup(self, rng, **kw):
        self.center.update(tau=rng.uniform(0.08, 0.2), a=rng.uniform(5.5, 7.0), c=rng.uniform(5.0, 7.0), gain=4.0, sigma=0.02)
        self.logsd.update(tau=0.15, a=0.05, c=0.05, gain=0.1, sigma=0.3)
        self.input_pattern = [1.0, 0.6, 0.3]
        self.channels = [("positive", 1.0)] * 3
        self.amp = 0.5

    def f(self, z, u, exo, th):
        s = z.sum()
        arg = th["a"] * z - th["c"] * (s - z) + th["gain"] * u - 3.0
        return (-z + logistic(arg)) / th["tau"]

    def g(self, z, th):
        return z.copy()

    def rest(self, th):
        z = np.full(3, 0.04)
        for _ in range(200):
            z = z + 0.2 * th["tau"] * self.f(z, np.zeros(3), None, th)
        return z

    def sample_init(self, rng, th, heldout=False):
        return rng.uniform(0.3, 1.1, 3) if heldout else rng.uniform(0.0, 0.8, 3)

    def describe(self):
        return {"f": "tau dz_i = -z_i + logistic(a z_i - c sum_{j!=i} z_j + g u_i - 3)", "g": "y = z",
                "timescales": "tau 0.08-0.2 s", "notes": "stable null state; inputs select one self-sustaining winner (memory)"}


# ============================================================================ 11 negative feedback controller
class Controller(Latent):
    family, variant = "feedback_controller", "PI"
    k, n_u, n_y = 2, 2, 1

    def setup(self, rng, **kw):
        self.center.update(tau_p=rng.uniform(0.2, 0.4), kp=rng.uniform(1.0, 2.0), ki=rng.uniform(3.0, 6.0), sigma=0.02)
        self.logsd.update(tau_p=0.15, kp=0.15, ki=0.15, sigma=0.3)
        self.input_pattern = [1.0, 0.0]
        self.channels = [("analog", 1.0), ("analog", 1.5)]

    def f(self, z, u, exo, th):
        p, q = z[0], z[1]
        e = u[0] - p
        c = th["kp"] * e + q
        return np.array([(-p + c + u[1]) / th["tau_p"], th["ki"] * e])

    def g(self, z, th):
        return z[:1].copy()

    def nominal_stimulus(self, t_end):
        return [[0.0, [0.0, 0.0]], [0.5, [1.0, 0.0]], [1.5, [1.0, 1.0]], [2.3, [0.0, 1.0]]]

    def describe(self):
        return {"f": "plant tau_p dp = -p + c + d, PI controller c = kp (r - p) + q, dq = ki (r - p); u = (r, d)",
                "g": "y = p", "timescales": "tau_p 0.2-0.4 s, ki 3-6 /s",
                "notes": "integral state q is invisible in y at steady state but encodes the compensated disturbance"}


# ============================================================================ 12 slow/fast
class FHN(Latent):
    family, variant = "slow_fast", "fitzhugh_nagumo_excitable"
    k = 2
    h_max = 0.0015

    def setup(self, rng, **kw):
        self.center.update(tau_f=rng.uniform(0.015, 0.03), tau_s=rng.uniform(0.4, 0.8), gain=1.0, sigma=0.03)
        self.logsd.update(tau_f=0.1, tau_s=0.15, gain=0.1, sigma=0.3)
        self.amp = 0.6

    def f(self, z, u, exo, th):
        v, w = z[0], z[1]
        return np.array([(v - v ** 3 / 3.0 - w + th["gain"] * u[0]) / th["tau_f"], (v + 0.7 - 0.8 * w) / th["tau_s"]])

    def rest(self, th):
        # fixed point of v - v^3/3 - (v + 0.7)/0.8 = 0
        r = np.roots([-1 / 3.0, 0.0, 1 - 1 / 0.8, -0.7 / 0.8])
        v = float(np.real(r[np.argmin(np.abs(np.imag(r)))]))
        return np.array([v, (v + 0.7) / 0.8])

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [0.56, 0.0], [1.5, 0.4], [1.56, 0.0]]

    def describe(self):
        return {"f": "tau_f dv = v - v^3/3 - w + g u, tau_s dw = v + 0.7 - 0.8 w (excitable FitzHugh-Nagumo)", "g": "y = v",
                "timescales": "fast 15-30 ms, slow 0.4-0.8 s (ratio ~25)",
                "notes": "threshold-like response to pulses; slow recovery variable w makes the response history dependent"}


# ============================================================================ trap-specific latents
class Hysteresis(Latent):
    """Trap F: a bistable memory z1 invisible in y until probed."""
    family, variant = "hysteresis_memory", "probe"
    k, n_u, n_y = 2, 2, 1

    def setup(self, rng, **kw):
        self.center.update(tau1=rng.uniform(0.1, 0.2), tau2=rng.uniform(0.1, 0.25), g1=2.0, g2=1.5, sigma=0.03)
        self.logsd.update(tau1=0.15, tau2=0.15, g1=0.1, g2=0.1, sigma=0.3)
        self.channels = [("analog", 1.0), ("binary", 1.0)]
        self.input_pattern = [0.0, 1.0]
        self.amp = 1.2

    def f(self, z, u, exo, th):
        return np.array([(z[0] - z[0] ** 3 + th["g1"] * u[0]) / th["tau1"], (-z[1] + th["g2"] * u[1] * z[0]) / th["tau2"]])

    def g(self, z, th):
        return z[1:2].copy()

    def rest(self, th):
        return np.array([-1.0, 0.0])

    def sample_init(self, rng, th, heldout=False):
        s = rng.choice([-1.0, 1.0])
        return np.array([s * (rng.uniform(1.2, 1.5) if heldout else rng.uniform(0.6, 1.2)), rng.uniform(-0.5, 0.5)])

    def nominal_stimulus(self, t_end):
        return [[0.0, [0.0, 0.0]], [0.4, [1.0, 0.0]], [0.7, [0.0, 0.0]], [1.2, [0.0, 1.0]], [1.8, [0.0, 0.0]], [2.4, [-1.0, 0.0]], [2.7, [0.0, 0.0]], [3.0, [0.0, 1.0]], [3.6, [0.0, 0.0]]]

    def describe(self):
        return {"f": "tau1 dz1 = z1 - z1^3 + g1 u1 (bistable memory), tau2 dz2 = -z2 + g2 u2 z1 (probe-gated output)",
                "g": "y = z2", "timescales": "0.1-0.25 s",
                "notes": "without the probe u2, y ~ 0 for both memory states z1 = +-1 (same output, different hidden state, "
                         "different futures once probed); u1 pulses set the memory with hysteresis"}


class SetPoint(Latent):
    """Trap H: dynamics relax to a per-draw set point theta_s (a parameter, not a state)."""
    family, variant = "set_point", "parameter_trap"
    k = 1

    def setup(self, rng, **kw):
        self.center.update(tau=rng.uniform(0.2, 0.4), gain=1.0, sigma=0.03)
        self.logsd.update(tau=0.15, gain=0.15, sigma=0.3)

    def derive(self, th, rng):
        th["setpoint"] = float(1.5 * rng.standard_normal())

    def f(self, z, u, exo, th):
        return (-(z - th["setpoint"]) + th["gain"] * u[:1]) / th["tau"]

    def g(self, z, th):
        return z.copy()

    def rest(self, th):
        return np.array([th["setpoint"]])

    def describe(self):
        return {"f": "tau dz = -(z - s) + g u, set point s ~ N(0, 1.5^2) redrawn per params_seed", "g": "y = z",
                "timescales": "tau 0.2-0.4 s", "notes": "s is a parameter (constant within a trajectory, not changed by any "
                "intervention); across draws it dominates the variance of y"}


class MultiCycle(Latent):
    """Trap I (planar): two concentric stable limit cycles separated by an unstable one."""
    family, variant = "multiple_limit_cycles", "concentric"
    k = 2

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.4), mu=rng.uniform(2.0, 4.0), r1=0.5, r2=1.0, r3=1.5, gain=1.5, sigma=0.03)
        self.logsd.update(f0=0.1, mu=0.2, gain=0.1, sigma=0.3)
        self.amp = 1.6

    def f(self, z, u, exo, th):
        rho = z[0] * z[0] + z[1] * z[1]
        h = -th["mu"] * (rho - th["r1"] ** 2) * (rho - th["r2"] ** 2) * (rho - th["r3"] ** 2) / th["r3"] ** 4
        w = TWO_PI * th["f0"]
        return np.array([h * z[0] - w * z[1] + th["gain"] * u[0], h * z[1] + w * z[0]])

    def rest(self, th):
        return np.array([th["r1"], 0.0])

    def sample_init(self, rng, th, heldout=False):
        ph = rng.uniform(0, TWO_PI)
        r = rng.uniform(1.6, 1.9) if heldout else rng.uniform(0.1, 1.6)
        return r * np.array([math.cos(ph), math.sin(ph)])

    def describe(self):
        return {"f": "dz = h(|z|^2) z + w J z + (g u, 0), h(rho) = -mu (rho - r1^2)(rho - r2^2)(rho - r3^2)/r3^4",
                "g": "y = z1", "timescales": "0.8-1.4 Hz",
                "notes": "stable cycles at radius r1 = 0.5 and r3 = 1.5, unstable cycle at r2 = 1; which cycle (amplitude) "
                         "is part of the state; pulses can switch cycles"}


class CycleSwitch(Latent):
    """Trap I (3-D): two limit cycles with equal amplitude but different frequency, selected by a hidden switch."""
    family, variant = "multiple_limit_cycles", "switch_selected"
    k, n_u, n_y = 3, 2, 1

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.3), delta=0.35, mu=4.0, tau_s=0.15, gain=1.0, sigma=0.03)
        self.logsd.update(f0=0.1, delta=0.1, mu=0.15, tau_s=0.15, sigma=0.3)
        self.input_pattern = [0.0, 1.0]
        self.channels = [("analog", 1.0), ("analog", 1.0)]

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"] * (1.0 + th["delta"] * np.tanh(2.0 * z[2]))
        a = th["mu"] * (1.0 - z[0] * z[0] - z[1] * z[1])
        return np.array([a * z[0] - w * z[1] + th["gain"] * u[0], a * z[1] + w * z[0], (z[2] - z[2] ** 3 + u[1]) / th["tau_s"]])

    def rest(self, th):
        return np.array([1.0, 0.0, -1.0])

    def sample_init(self, rng, th, heldout=False):
        ph = rng.uniform(0, TWO_PI)
        r = rng.uniform(1.2, 1.5) if heldout else rng.uniform(0.3, 1.2)
        return np.array([r * math.cos(ph), r * math.sin(ph), rng.choice([-1, 1]) * rng.uniform(0.5, 1.2)])

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [1.0, 1.0], [1.2, 0.0]]

    def describe(self):
        return {"f": "Hopf oscillator (unit radius) with frequency w0 (1 + delta tanh(2 z3)); z3 bistable switch "
                     "tau_s dz3 = z3 - z3^3 + u2", "g": "y = z1",
                "timescales": "0.8-1.3 Hz; the two cycles differ in frequency by ~2 delta = 70%",
                "notes": "two limit cycles (z3 = +-1) with identical amplitude in y; cycle identity is a hidden binary state"}


class SubHopf(Latent):
    """Trap J: stable rest coexisting with a stable limit cycle (transient vs sustained oscillation)."""
    family, variant = "transient_vs_cycle", "subcritical_hopf"
    k = 2

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.4), mu=rng.uniform(1.0, 2.0), r2=0.8, r3=1.4, gain=1.5, sigma=0.03)
        self.logsd.update(f0=0.1, mu=0.2, gain=0.1, sigma=0.3)
        self.amp = 1.5

    def f(self, z, u, exo, th):
        rho = z[0] * z[0] + z[1] * z[1]
        h = -th["mu"] * (rho - th["r2"] ** 2) * (rho - th["r3"] ** 2) / th["r3"] ** 2
        w = TWO_PI * th["f0"]
        return np.array([h * z[0] - w * z[1] + th["gain"] * u[0], h * z[1] + w * z[0]])

    def sample_init(self, rng, th, heldout=False):
        ph = rng.uniform(0, TWO_PI)
        r = rng.uniform(1.5, 1.8) if heldout else rng.uniform(0.0, 1.5)
        return r * np.array([math.cos(ph), math.sin(ph)])

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [0.6, 0.0], [1.5, 2.0], [1.7, 0.0]]

    def describe(self):
        return {"f": "dz = h(|z|^2) z + w J z + (g u, 0), h(rho) = -mu (rho - r2^2)(rho - r3^2)/r3^2", "g": "y = z1",
                "timescales": "0.8-1.4 Hz",
                "notes": "rest is stable; oscillations with amplitude < r2 = 0.8 decay (transient), > r2 converge to the cycle "
                         "r3 = 1.4. Same phase, different amplitude -> different futures"}


class Rayleigh(Latent):
    """Trap K: input-controlled damping; overdamped (effectively 1-D) at low input, limit cycle (2-D) at high input."""
    family, variant = "bifurcation", "input_controlled_rayleigh"
    k = 2
    h_max = 0.002

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.2), mu0=25.0, gmu=28.0, gamma=3.0, sigma=0.05)
        self.logsd.update(f0=0.1, mu0=0.1, gmu=0.1, gamma=0.1, sigma=0.3)
        self.amp = 0.8

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        mu = -th["mu0"] + th["gmu"] * u[0]
        return np.array([w * z[1], -w * z[0] + (mu - th["gamma"] * z[1] ** 2) * z[1]])

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [1.0, 1.0], [2.5, 0.0]]

    def describe(self):
        return {"f": "dz1 = w z2, dz2 = -w z1 + (mu(u) - gamma z2^2) z2, mu(u) = -mu0 + gmu u", "g": "y = z1",
                "timescales": "at u = 0: eigenvalues ~ -w^2/mu0 (~ -1.6/s) and -mu0 (~ -25/s): one slow direction; "
                              "at u = 1: Rayleigh limit cycle at ~0.8-1.2 Hz",
                "notes": "effective dimension is 1 for u <~ 0.5 and 2 for u >~ 0.9"}


class ExoDriven(Latent):
    """Family 19: damped oscillator driven by a hidden exogenous process e(t) (not in u, not in any neuron)."""
    family, variant = "hidden_exogenous", "ou_driven_oscillator"
    k = 2
    n_exo = 1

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.6, 1.2), zeta=rng.uniform(0.15, 0.3), gain=1.0, g_exo=1.0, tau_e=0.5, sigma=0.02)
        self.logsd.update(f0=0.1, zeta=0.15, gain=0.1, g_exo=0.1, tau_e=0.2, sigma=0.3)

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        e = exo[0] if exo is not None else 0.0
        return np.array([w * z[1], -w * z[0] - 2 * th["zeta"] * w * z[1] + w * (th["gain"] * u[0] + th["g_exo"] * e)])

    def exo_signal(self, rng, T, dt, th):
        tau = th["tau_e"]
        a = math.exp(-dt / tau)
        e = np.zeros((T, 1))
        e[0] = rng.standard_normal()
        xi = rng.standard_normal(T)
        for i in range(1, T):
            e[i] = a * e[i - 1] + math.sqrt(1 - a * a) * xi[i]
        return e

    def describe(self):
        return {"f": "damped oscillator + hidden exogenous drive: dz2 = -w z1 - 2 zeta w z2 + w (g u + g_e e(t)), "
                     "e = unit-variance OU process (tau_e ~ 0.5 s) independent per trajectory", "g": "y = z1",
                "timescales": "0.6-1.2 Hz, tau_e 0.5 s",
                "notes": "(z, u) is NOT a closed description: e(t) is unobservable from x and u; a method should report an "
                         "unexplained input / stochasticity or abstain, not invent extra neural state"}


# ============================================================================ 20 non-compressible
_CHAOS_CACHE: dict = {}


class RandomRNN(Latent):
    family, variant = "high_dimensional", "chaotic_rnn"
    n_y = 2
    h_max = 0.005

    def __init__(self, seed, N=100, g=3.0, **kw):
        self.k = int(N)
        self._g = g
        super().__init__(seed, **kw)

    @staticmethod
    def _divergence(W, g, rng, T=12.0, h=0.01, tau=0.1):
        """Growth factor of a 1e-6 separation over T seconds (RK4, no input)."""
        N = W.shape[0]
        f = lambda Z: (-Z + g * np.tanh(Z) @ W.T) / tau
        Z = np.tile(rng.standard_normal(N), (2, 1))
        Z[1] += 1e-6 * rng.standard_normal(N)
        for _ in range(int(T / h)):
            k1 = f(Z); k2 = f(Z + 0.5 * h * k1); k3 = f(Z + 0.5 * h * k2); k4 = f(Z + h * k3)
            Z = Z + h / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        return np.linalg.norm(Z[0] - Z[1]) / 1e-6 / math.sqrt(N)

    def setup(self, rng, **kw):
        N = self.k
        # draw connectivities until one is chaotic at the nominal gain (finite-N networks may settle on fixed points)
        # from every one of 4 initial conditions and at +-6% gain (~2 sd of the parameter draw)
        key = (self.seed, N, self._g)
        if key not in _CHAOS_CACHE:
            for attempt in range(60):
                W = rng.standard_normal((N, N)) / math.sqrt(N)
                growth = min(self._divergence(W, self._g * fac, np.random.default_rng([self.seed, attempt, r]))
                             for r in range(4) for fac in (0.94, 1.06))
                if growth > 1e3:
                    break
            _CHAOS_CACHE[key] = (W, attempt + 1, growth)
        self.W, self.chaos_attempts, self.chaos_growth = _CHAOS_CACHE[key]
        rng = np.random.default_rng([self.seed, 99])
        self.Bin = rng.standard_normal((N, 1))
        self.Wout = rng.standard_normal((self.n_y, N)) / math.sqrt(N)
        self.center.update(tau=0.1, g=self._g, sigma=0.05)
        self.logsd.update(tau=0.1, g=0.03, sigma=0.3)
        self.amp = 1.0

    def f(self, z, u, exo, th):
        return (-z + th["g"] * (self.W @ np.tanh(z)) + self.Bin @ u) / th["tau"]

    def g(self, z, th):
        return self.Wout @ np.tanh(z)

    def rest(self, th):
        return 0.5 * np.random.default_rng([self.seed, 5]).standard_normal(self.k)

    def sample_init(self, rng, th, heldout=False):
        return rng.standard_normal(self.k) * (1.5 if heldout else 1.0)

    def describe(self):
        return {"f": f"tau dz = -z + g W tanh(z) + B u, W_ij ~ N(0, 1/N) (a realisation verified chaotic at the nominal gain), N = {self.k}, g ~ {self._g}",
                "g": "y = W_out tanh(z)", "timescales": "tau 0.1 s; chaotic fluctuations",
                "notes": "no low-dimensional valid abstraction: every unit is state; kicks to any direction have lasting, "
                         "divergent effects"}


class HighDimLinear(Latent):
    family, variant = "high_dimensional", "flat_spectrum_linear"
    n_u = 3
    n_y = 3

    def __init__(self, seed, N=60, **kw):
        self.k = int(N)
        super().__init__(seed, **kw)

    def setup(self, rng, **kw):
        k = self.k
        self.center.update(tau=rng.uniform(0.2, 2.0, k), sigma=0.15)
        self.logsd.update(tau=0.1, sigma=0.2)
        Q, _ = np.linalg.qr(rng.standard_normal((k, k)))
        self.Q = Q
        self.Bm = rng.standard_normal((k, self.n_u)) / math.sqrt(self.n_u)
        self.Cm = rng.standard_normal((self.n_y, k)) / math.sqrt(k) * 2.0
        self.channels = [("analog", 1.0)] * self.n_u
        self.input_pattern = [1.0, -0.5, 0.5]

    def derive(self, th, rng):
        th["_A"] = self.Q @ np.diag(-1.0 / th["tau"]) @ self.Q.T

    def f(self, z, u, exo, th):
        return th["_A"] @ z + self.Bm @ u

    def g(self, z, th):
        return self.Cm @ z

    def describe(self):
        return {"f": f"dz = A z + B u, A symmetric with {self.k} eigenvalues -1/tau, tau ~ U[0.2, 2] s (flat spectrum), "
                     "noise drives every mode", "g": "y = C z (C dense)", "timescales": "0.2-2 s, flat",
                "notes": "no small abstraction: all modes are driven, all are read out, Hankel spectrum decays slowly"}
