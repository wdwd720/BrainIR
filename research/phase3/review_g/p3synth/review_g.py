"""Review G: ten NEW adversarial trap families (G1-G10) for low-dimensional causal state discovery.

Add-only module. It reuses the unchanged machinery (Latent, Block, Model, make_implementation via build_system,
SyntheticSystem, the suite planner and the truth writer) and adds new latent and block classes. Nothing in the existing
catalogue, simulator, protocol, planner or truth writer is modified.

    review_g_catalog()                                 -> list[SystemDef] (10 systems, traps "G1".."G10")
    build_review_g(suite_seed, tier, names)            -> list[SyntheticSystem]
    build_review_g_suite(out_public, out_truth, seed)  -> runs p3synth.suite.build_suite on this catalogue (tier "heldout")

Every trap is a property of the dynamics or of the neural implementation (symmetry, slow variables, context-dependent
coding, transmission delays, external rhythms, parallel pathways, state-dependent stability, heavy-tailed noise,
nonstationary parameters, input-uncontrollable modes). None is tuned against a particular algorithm. REVIEW_G_TRAPS.md
documents construction, target, principle, expected correct behaviour and limitations per trap.
"""

from __future__ import annotations

import math
from contextlib import contextmanager
from pathlib import Path

import numpy as np

from . import blocks as B
from . import latents as L
from . import suite as _suite
from .latents import TWO_PI, Latent
from .systems import SystemDef, build_system

TRAPS_G = {
    "G1": "symmetry-hidden transverse mode (synchronised oscillators; the relative phase is dormant)",
    "G2": "slow causal state that looks like a per-trial parameter (inverse of trap H)",
    "G3": "context-dependent sign of tuning (the causal effect of a neuron on y flips with the context state)",
    "G4": "transmission delay realised by a relay chain (finite memory = real, collinear state)",
    "G5": "external rhythm masquerading as an intrinsic oscillation (entrainment by a hidden periodic drive)",
    "G6": "confounded impostor population (same input, same time constant, not causal)",
    "G7": "compact state valid only inside part of state space (mode that ignites outside the training region)",
    "G8": "heavy-tailed (Levy-jump) intrinsic noise in a bistable system",
    "G9": "slow non-neural parameter drift inside a trajectory (context, not state)",
    "G10": "non-compressible system that looks one-dimensional (many dormant, input-uncontrollable modes)",
}


# ============================================================================================ G1
class SyncPair(Latent):
    """G1: two identical, diffusively coupled Hopf oscillators A and B driven by a COMMON input.

    Coordinates z = (s1, s2, d1, d2) with s = (A + B)/2 (synchronous part) and d = (A - B)/2 (transverse part).
    The synchronous manifold d = 0 is invariant under the dynamics AND under any input (symmetry), so every spontaneous or
    input-driven trajectory started synchronously stays on it: the population activity is exactly 2-D. The transverse
    mode is real state: a symmetry-breaking micro intervention (almost any single-neuron kick) excites it, it relaxes only
    slowly (weak coupling K, rate ~2K), and it cancels the readout y = A1 + B1 = 2 s1 near anti-phase.
    Process noise acts on the synchronous coordinates only (common fluctuations).
    """
    family, variant = "review_g_sync_pair", "symmetric_coupled_hopf"
    k, n_u, n_y = 4, 1, 1

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.3), mu=rng.uniform(3.0, 5.0), K=rng.uniform(0.25, 0.4), gain=1.5, sigma=0.03)
        self.logsd.update(f0=0.1, mu=0.15, K=0.15, gain=0.1, sigma=0.3)
        self.amp = 1.0

    @staticmethod
    def _hopf(a, w, mu):
        r2 = a[0] * a[0] + a[1] * a[1]
        return np.array([mu * (1 - r2) * a[0] - w * a[1], mu * (1 - r2) * a[1] + w * a[0]])

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        s, d = z[:2], z[2:]
        A, Bo = s + d, s - d
        fa = self._hopf(A, w, th["mu"]) - 2 * th["K"] * d
        fb = self._hopf(Bo, w, th["mu"]) + 2 * th["K"] * d
        drive = np.array([th["gain"] * u[0], 0.0])
        return np.concatenate([(fa + fb) / 2 + drive, (fa - fb) / 2])

    def g(self, z, th):
        return np.array([2.0 * z[0]])

    def sigma(self, th):
        return np.array([th["sigma"], th["sigma"], 0.0, 0.0])

    def rest(self, th):
        return np.array([1.0, 0.0, 0.0, 0.0])

    @staticmethod
    def from_phases(r1, p1, r2, p2):
        A = r1 * np.array([math.cos(p1), math.sin(p1)])
        Bo = r2 * np.array([math.cos(p2), math.sin(p2)])
        return np.concatenate([(A + Bo) / 2, (A - Bo) / 2])

    def sample_init(self, rng, th, heldout=False):
        ph = rng.uniform(0, TWO_PI)
        if not heldout:                            # synchronous initial states only
            r = rng.uniform(0.2, 1.3)
            return self.from_phases(r, ph, r, ph)
        psi = rng.uniform(0.5, 1.0) * math.pi * rng.choice([-1, 1])   # desynchronised (held-out region)
        return self.from_phases(rng.uniform(0.8, 1.2), ph, rng.uniform(0.8, 1.2), ph + psi)

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.8, 1.0], [1.0, 0.0], [2.5, -1.0], [2.7, 0.0]]

    def describe(self):
        return {"f": "A, B identical Hopf oscillators (unit radius, w = 2 pi f0, radial rate mu), diffusive coupling K (B - A) "
                     "resp. K (A - B), common input g u on A1 and B1; coordinates s = (A + B)/2, d = (A - B)/2",
                "g": "y = A1 + B1 = 2 s1",
                "timescales": "0.8-1.3 Hz, radial rate mu 3-5 /s, transverse (relative-phase) relaxation ~2K = 0.5-0.8 /s",
                "notes": "d = 0 is invariant under f and under u (symmetry): spontaneous and input-driven activity is exactly "
                         "2-D; the transverse mode d is excited only by symmetry-breaking micro interventions (or held-out "
                         "desynchronised initial states), relaxes over ~1.5-2 s and cancels y near anti-phase. k = 4."}


# ============================================================================================ G2
class SlowStateOsc(Latent):
    """G2: Hopf oscillator whose frequency is set by a very slow causal state s (tau_s 30-60 s).

    Within a 4 s trajectory s is constant to within a few per cent, exactly like a parameter; across trajectories it varies
    with the initial state. It is nevertheless state: kicking the neurons that carry it changes the oscillation frequency
    for the rest of the trial. The system also carries parameter-report neurons (ParamReport of f0) that look the same
    (flat within trial, correlated with frequency across trials) but are not causal.
    """
    family, variant = "review_g_slow_state", "frequency_set_by_slow_state"
    k, n_u, n_y = 3, 1, 1

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.2), mu=rng.uniform(3.0, 5.0), delta=0.3, tau_s=rng.uniform(30.0, 60.0),
                           gain=1.5, sigma=0.03, sigma_s=0.004)
        self.logsd.update(f0=0.12, mu=0.15, delta=0.05, tau_s=0.2, gain=0.1, sigma=0.3, sigma_s=0.2)
        self.amp = 1.0

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"] * (1.0 + th["delta"] * np.tanh(z[2]))
        a = th["mu"] * (1.0 - z[0] * z[0] - z[1] * z[1])
        return np.array([a * z[0] - w * z[1] + th["gain"] * u[0], a * z[1] + w * z[0], -z[2] / th["tau_s"]])

    def sigma(self, th):
        return np.array([th["sigma"], th["sigma"], th["sigma_s"]])

    def rest(self, th):
        return np.array([1.0, 0.0, 0.0])

    def sample_init(self, rng, th, heldout=False):
        ph = rng.uniform(0, TWO_PI)
        r = rng.uniform(0.3, 1.2)
        s = rng.choice([-1, 1]) * rng.uniform(1.2, 1.8) if heldout else rng.uniform(-1.2, 1.2)
        return np.array([r * math.cos(ph), r * math.sin(ph), s])

    def describe(self):
        return {"f": "Hopf: dz12 = mu (1 - |z12|^2) z12 + w(s) J z12 + (g u, 0), w(s) = 2 pi f0 (1 + delta tanh s); "
                     "ds = -s / tau_s (tau_s 30-60 s)",
                "g": "y = z1", "timescales": "0.8-1.2 Hz; s decays over 30-60 s (quasi-constant within a 4 s trial)",
                "notes": "s looks like a per-trial parameter but is causal state (kicks on its neurons change the frequency "
                         "for the rest of the trial). Parameter-report neurons of f0 are the non-causal look-alikes. k = 3."}


# ============================================================================================ G3
class SignFlip(Latent):
    """G3: a context-gated integrator whose neural code flips sign with a bistable context m.

    tau dp = -p + g m u1, tau_m dm = m - m^3 + g_m u2, y = m p. Because m = +-1 in both stable contexts, y obeys the SAME
    law tau dy = -y + g u1 in both contexts, but the neurons (linear in p) represent y with a context-dependent sign:
    their tuning to y flips, and the effect of kicking them on y flips sign with the context.
    """
    family, variant = "review_g_sign_flip", "context_signed_code"
    k, n_u, n_y = 2, 2, 1

    def setup(self, rng, **kw):
        self.center.update(tau=rng.uniform(0.3, 0.6), tau_m=rng.uniform(0.1, 0.2), gain=1.0, g_m=1.0, sigma=0.03)
        self.logsd.update(tau=0.15, tau_m=0.15, gain=0.15, g_m=0.1, sigma=0.3)
        self.input_pattern = [1.0, 0.0]
        self.channels = [("analog", 1.0), ("analog", 1.0)]
        self.amp = 1.0

    def f(self, z, u, exo, th):
        p, m = z[0], z[1]
        return np.array([(-p + th["gain"] * m * u[0]) / th["tau"], (m - m ** 3 + th["g_m"] * u[1]) / th["tau_m"]])

    def g(self, z, th):
        return np.array([z[0] * z[1]])

    def rest(self, th):
        return np.array([0.0, 1.0])

    def sample_init(self, rng, th, heldout=False):
        sgn = rng.choice([-1.0, 1.0])
        if heldout:
            return np.array([rng.choice([-1, 1]) * rng.uniform(1.0, 1.5), sgn * rng.uniform(1.2, 1.5)])
        return np.array([rng.uniform(-1.0, 1.0), sgn * rng.uniform(0.7, 1.2)])

    def nominal_stimulus(self, t_end):
        return [[0.0, [0.0, 0.0]], [0.3, [0.0, -1.0]], [0.5, [0.0, 0.0]], [0.8, [1.0, 0.0]], [1.4, [0.0, 0.0]],
                [2.0, [0.0, 1.0]], [2.2, [0.0, 0.0]], [2.5, [1.0, 0.0]], [3.1, [0.0, 0.0]]]

    def describe(self):
        return {"f": "tau dp = -p + g m u1 (context-gated integrator), tau_m dm = m - m^3 + g_m u2 (bistable context, "
                     "|g_m u2| > 0.385 switches)",
                "g": "y = m p (so tau dy = -y + g u1 in either context m = +-1)",
                "timescales": "tau 0.3-0.6 s, context switch 0.1-0.2 s",
                "notes": "neurons are linear in (p, m): relative to y their tuning, and the sign of their causal effect on y, "
                         "flips with the context m; a context switch re-interprets the stored value (y -> -y). k = 2."}


# ============================================================================================ G4
class DelayRelay(Latent):
    """G4: delayed negative feedback through a relay chain (linear chain trick, M stages, mean delay T).

    tau_a da = -a - kappa q_M + g u;  dq_1 = (M/T)(a - q_1);  dq_i = (M/T)(q_{i-1} - q_i).  y = a.
    The relay stages are lagged, smoothed copies of a: highly collinear, low extra variance, but each is real state.
    A kick to a relay stage returns to a as an echo after the remaining part of the delay.
    """
    family, variant = "review_g_delay_relay", "erlang_delay_feedback"
    n_u, n_y = 1, 1

    def __init__(self, seed, M=8, **kw):
        self.M = int(M)
        self.k = 1 + self.M
        super().__init__(seed, **kw)

    def setup(self, rng, **kw):
        self.center.update(tau_a=rng.uniform(0.06, 0.1), T=rng.uniform(0.4, 0.5), kappa=rng.uniform(1.05, 1.2), gain=1.0,
                           sigma=0.03)
        self.logsd.update(tau_a=0.1, T=0.1, kappa=0.05, gain=0.15, sigma=0.3)
        self.amp = 0.6

    def f(self, z, u, exo, th):
        r = self.M / th["T"]
        out = np.empty(self.k)
        out[0] = (-z[0] - th["kappa"] * z[self.M] + th["gain"] * u[0]) / th["tau_a"]
        out[1] = r * (z[0] - z[1])
        out[2:] = r * (z[1:self.M] - z[2:])
        return out

    def g(self, z, th):
        return z[:1].copy()

    def sample_init(self, rng, th, heldout=False):
        # physically meaningful histories: a smooth recent past (the relay holds lagged copies of a)
        a_now, a_past = rng.uniform(-1, 1, 2) * (rng.uniform(1.0, 1.5) if heldout else 1.0) * self.amp
        lag = np.linspace(0, 1, self.k)
        return (1 - lag) * a_now + lag * a_past

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [0.6, 0.0], [2.0, -1.0], [2.1, 0.0]]

    def describe(self):
        return {"f": f"tau_a da = -a - kappa q_M + g u; dq_1 = (M/T)(a - q_1), dq_i = (M/T)(q_(i-1) - q_i), M = {self.M}",
                "g": "y = a", "timescales": "tau_a 60-100 ms, mean delay T 0.4-0.5 s (Erlang, M stages); closed loop rings at "
                                            "~0.8-1.1 Hz with damping ratio ~0.1-0.15",
                "notes": f"k = {self.k}: the relay stages are state (collinear lagged copies of a, little extra variance); "
                         "kicks on relay neurons come back to a as delayed echoes"}


# ============================================================================================ G5
class ExoRhythm(Latent):
    """G5: damped oscillator (f0) entrained by a HIDDEN external periodic drive e(t) = sin(2 pi f_d t + phi).

    phi is random per trajectory (drawn from the trajectory's noise stream), the drive is carried by no neuron and is not
    in u. Unperturbed activity is dominated by a sustained oscillation at f_d that looks intrinsic. Interventions cannot
    shift its phase: the causal response to any kick is a transient at f0 that decays.
    """
    family, variant = "review_g_exo_rhythm", "entrained_damped_oscillator"
    k, n_u, n_y = 2, 1, 1
    n_exo = 1

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(1.2, 1.6), zeta=rng.uniform(0.15, 0.25), f_d=rng.uniform(0.5, 0.7), g_d=1.0,
                           gain=1.0, sigma=0.02)
        self.logsd.update(f0=0.08, zeta=0.15, f_d=0.08, g_d=0.1, gain=0.1, sigma=0.3)

    def f(self, z, u, exo, th):
        w = TWO_PI * th["f0"]
        e = exo[0] if exo is not None else 0.0
        return np.array([w * z[1], -w * z[0] - 2 * th["zeta"] * w * z[1] + w * (th["gain"] * u[0] + th["g_d"] * e)])

    def exo_signal(self, rng, T, dt, th):
        phi = rng.uniform(0, TWO_PI)
        t = np.arange(T) * dt
        return np.sin(TWO_PI * th["f_d"] * t + phi)[:, None]

    def describe(self):
        return {"f": "dz1 = w z2, dz2 = -w z1 - 2 zeta w z2 + w (g u + g_d e(t)), e = sin(2 pi f_d t + phi) (hidden)",
                "g": "y = z1",
                "timescales": "intrinsic f0 1.2-1.6 Hz (zeta 0.15-0.25, transients decay in ~0.5-1 s); hidden drive f_d 0.5-0.7 Hz",
                "notes": "the sustained rhythm is external: no neuron carries it and no intervention can shift its phase. "
                         "k = 2 plus a hidden, predictable but uncontrollable periodic input (closed_dynamics false)."}


class Impostor(B.Block):
    """G6 block: a population with the SAME law as the latent leaky integrator (reads tau and gain from theta), its own
    independent noise, never feeding z."""
    name, role = "imp", "impostor"
    dim = 1

    def __init__(self, sigma=0.03):
        self.s = sigma

    def f(self, cb, c, u, th, model):
        return (-cb + th["gain"] * u[:1]) / th["tau"]

    def sigma(self, th):
        return self.s

    def init(self, rng, z0, th, model, heldout=False):
        return np.asarray(z0[:1], float) + 0.2 * rng.standard_normal(1)

    def describe(self):
        return "impostor: tau dn = -n + g u with the latent's own tau and g, independent noise; never feeds z"


# ============================================================================================ G7
class LocalValidity(Latent):
    """G7: slow variable a plus a fast oscillatory mode b whose stability depends on a.

    tau_a da = -a + g u;  db = [mu (a^2 / a_c^2 - 1) - gamma |b|^2] b + w_b J b;  y = a + b1.
    For |a| < a_c the mode b is stable (decay rate mu (1 - a^2/a_c^2)) and sits near 0: the system is effectively 1-D.
    For |a| > a_c (reached only from held-out initial states or large interventions) b grows into a 2-3 Hz oscillation.
    Inside the training region the approach to the boundary shows as critical slowing down of b.
    """
    family, variant = "review_g_local_validity", "state_dependent_instability"
    k, n_u, n_y = 3, 1, 1

    def setup(self, rng, **kw):
        self.center.update(tau_a=rng.uniform(1.5, 2.5), gain=0.6, a_c=1.2, mu=rng.uniform(5.0, 7.0),
                           f_b=rng.uniform(2.0, 3.0), gamma=2.0, sigma=0.03)
        self.logsd.update(tau_a=0.1, gain=0.1, a_c=0.03, mu=0.1, f_b=0.08, gamma=0.1, sigma=0.3)
        self.amp = 1.0

    def f(self, z, u, exo, th):
        a, b = z[0], z[1:]
        rate = th["mu"] * (a * a / th["a_c"] ** 2 - 1.0) - th["gamma"] * (b[0] * b[0] + b[1] * b[1])
        wb = TWO_PI * th["f_b"]
        return np.array([(-a + th["gain"] * u[0]) / th["tau_a"], rate * b[0] - wb * b[1], rate * b[1] + wb * b[0]])

    def g(self, z, th):
        return np.array([z[0] + z[1]])

    def sample_init(self, rng, th, heldout=False):
        if heldout:
            a = rng.choice([-1, 1]) * rng.uniform(1.5, 2.0)
            return np.concatenate([[a], 0.05 * rng.standard_normal(2)])
        return np.concatenate([[rng.uniform(-1.0, 1.0)], 0.02 * rng.standard_normal(2)])

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [1.5, 0.0], [2.2, -1.0], [3.0, 0.0]]

    def describe(self):
        return {"f": "tau_a da = -a + g u; db = [mu (a^2/a_c^2 - 1) - gamma |b|^2] b + w_b J b (b = (b1, b2))",
                "g": "y = a + b1",
                "timescales": "tau_a 1.5-2.5 s; b decays at mu (1 - a^2/a_c^2) (5-7 /s at a = 0), oscillates at 2-3 Hz",
                "notes": "a_c = 1.2; training inputs and initial states keep |a| < ~1 (b dormant, effectively 1-D); held-out "
                         "initial states |a| = 1.5-2 ignite b. Critical slowing down of b inside the region foreshadows it. k = 3."}


# ============================================================================================ G8
class LevySwitch(Latent):
    """G8: double-well switch driven by Gaussian noise PLUS compound-Poisson jumps with Pareto (alpha 1.5) amplitudes.

    tau dz = z - z^3 + g u (+ Gaussian noise) and jumps J at Poisson times (rate lam_J), |J| ~ Pareto(x_m, alpha) capped
    at J_max, random sign. The jumps are white (independent of the past), so z alone is a Markov state; the switches they
    cause are memoryless. The jumps are generated as a hidden exogenous input (impulses J/dt over one output step).
    """
    family, variant = "review_g_levy_switch", "pareto_jump_double_well"
    k, n_u, n_y = 1, 1, 1
    n_exo = 1

    def setup(self, rng, **kw):
        self.center.update(tau=rng.uniform(0.15, 0.2), gain=1.0, rate_J=rng.uniform(1.2, 1.8), xm=0.3, alpha=1.5, J_max=3.0,
                           sigma=0.05)
        self.logsd.update(tau=0.1, gain=0.15, rate_J=0.15, sigma=0.3)
        self.amp = 1.3

    def f(self, z, u, exo, th):
        e = exo[0] if exo is not None else 0.0
        return (z - z ** 3 + th["gain"] * u[:1]) / th["tau"] + e

    @staticmethod
    def jumps(rng, T, dt, th):
        hit = rng.random(T) < th["rate_J"] * dt
        mag = np.minimum(th["xm"] * rng.random(T) ** (-1.0 / th["alpha"]), th["J_max"])
        sgn = np.where(rng.random(T) < 0.5, -1.0, 1.0)
        return np.where(hit, sgn * mag, 0.0)

    def exo_signal(self, rng, T, dt, th):
        J = self.jumps(rng, T, dt, th)
        J[-1] = 0.0
        return (J / dt)[:, None]

    def rest(self, th):
        return np.array([-1.0])

    def sample_init(self, rng, th, heldout=False):
        return np.array([rng.uniform(1.2, 1.8) * rng.choice([-1, 1]) if heldout else rng.uniform(-1.2, 1.2)])

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [0.7, 0.0], [1.8, -1.0], [2.0, 0.0]]

    def describe(self):
        return {"f": "tau dz = z - z^3 + g u + Gaussian noise, plus jumps J at Poisson times (rate 1.2-1.8 /s), |J| ~ Pareto("
                     "x_m 0.3, alpha 1.5) capped at 3, random sign (hidden exogenous impulses J/dt over one 10 ms step)",
                "g": "y = z", "timescales": "tau 0.12-0.2 s; jump-induced well switches ~0.1-0.2 /s",
                "notes": "the jumps are white noise, not state: z is Markov, switches are memoryless. A Gaussian noise model "
                         "cannot match both the within-well jitter and the switching rate. k = 1 (truth's closed_dynamics "
                         "flag is false only because the jumps are delivered through the exogenous channel)."}


# ============================================================================================ G9
class DriftingOsc(Latent):
    """G9: damped oscillator whose frequency and damping drift within a trajectory with a hidden slow OU context e(t)
    (tau_e 2-4 s): w = w0 (1 + 0.25 tanh e), zeta = zeta0 (1 - 0.6 tanh e). e is carried by no neuron and is not moved by
    any intervention: it is a nonstationary parameter (context), not state."""
    family, variant = "review_g_param_drift", "ou_modulated_oscillator"
    k, n_u, n_y = 2, 1, 1
    n_exo = 1

    def setup(self, rng, **kw):
        self.center.update(f0=rng.uniform(0.8, 1.2), zeta=rng.uniform(0.12, 0.2), gain=1.0, tau_e=rng.uniform(2.0, 4.0),
                           sigma=0.08)
        self.logsd.update(f0=0.1, zeta=0.15, gain=0.1, tau_e=0.15, sigma=0.2)

    def modulation(self, e, th):
        te = np.tanh(e)
        return TWO_PI * th["f0"] * (1.0 + 0.25 * te), th["zeta"] * (1.0 - 0.6 * te)

    def f(self, z, u, exo, th):
        e = exo[0] if exo is not None else 0.0
        w, zeta = self.modulation(e, th)
        return np.array([w * z[1], -w * z[0] - 2 * zeta * w * z[1] + w * th["gain"] * u[0]])

    def exo_signal(self, rng, T, dt, th):
        a = math.exp(-dt / th["tau_e"])
        e = np.zeros((T, 1))
        e[0] = rng.standard_normal()
        xi = rng.standard_normal(T)
        for i in range(1, T):
            e[i] = a * e[i - 1] + math.sqrt(1 - a * a) * xi[i]
        return e

    def describe(self):
        return {"f": "dz1 = w z2, dz2 = -w z1 - 2 zeta w z2 + w g u with w = 2 pi f0 (1 + 0.25 tanh e), zeta = zeta0 (1 - 0.6 "
                     "tanh e); e = hidden unit-variance OU context, tau_e 2-4 s, independent per trajectory",
                "g": "y = z1", "timescales": "0.8-1.2 Hz, zeta 0.05-0.3 depending on e; context drifts over 2-4 s",
                "notes": "the vector field itself drifts inside a trajectory; the drift is not carried by neurons and is not "
                         "controllable: context, not state. k = 2 plus a hidden nonstationary parameter (closed_dynamics false)."}


# ============================================================================================ G10
class MaskedHighDim(Latent):
    """G10: one input-driven, noise-driven leaky mode plus P weakly damped oscillatory modes that neither the input nor the
    process noise excites (dormant). All modes are read out with comparable weights. Spontaneous and input-driven
    activity is one-dimensional; any micro intervention excites all 2P + 1 modes, and the readout then carries P
    incommensurate damped oscillations (0.5-8 Hz, decay 0.8-3 s): there is no compact causal state."""
    family, variant = "high_dimensional", "masked_dormant_modes"
    n_u, n_y = 1, 1

    def __init__(self, seed, P=12, **kw):
        self.P = int(P)
        self.k = 1 + 2 * self.P
        super().__init__(seed, **kw)

    def setup(self, rng, **kw):
        P = self.P
        self.center.update(tau0=rng.uniform(0.4, 0.7), gain=1.0, freqs=np.exp(rng.uniform(np.log(0.5), np.log(8.0), P)),
                           taus=rng.uniform(0.8, 3.0, P), sigma=0.05)
        self.logsd.update(tau0=0.1, gain=0.1, freqs=0.05, taus=0.1, sigma=0.3)
        C = rng.uniform(0.4, 0.8, 2 * P) * rng.choice([-1, 1], 2 * P)
        self.C = np.concatenate([[1.0], C])
        self.amp = 1.0

    def f(self, z, u, exo, th):
        out = np.empty(self.k)
        out[0] = (-z[0] + th["gain"] * u[0]) / th["tau0"]
        x, v = z[1::2], z[2::2]
        w = TWO_PI * np.asarray(th["freqs"])
        d = 1.0 / np.asarray(th["taus"])
        out[1::2] = -d * x - w * v
        out[2::2] = w * x - d * v
        return out

    def g(self, z, th):
        return np.array([self.C @ z])

    def sigma(self, th):
        s = np.zeros(self.k)
        s[0] = th["sigma"]
        return s

    def sample_init(self, rng, th, heldout=False):
        z = np.zeros(self.k)
        z[0] = rng.uniform(-1, 1) * (1.5 if heldout else 1.0)
        if heldout:
            z[1:] = 0.3 * rng.standard_normal(self.k - 1)
        return z

    def nominal_stimulus(self, t_end):
        return [[0.0, 0.0], [0.5, 1.0], [1.5, 0.0], [2.2, -1.0], [2.8, 0.0]]

    def describe(self):
        return {"f": f"dz0 = (-z0 + g u)/tau0 (noise-driven); {self.P} damped rotations dz_i = (-1/tau_i + w_i J) z_i, not "
                     "driven by u or by process noise",
                "g": "y = z0 + sum_i C_i . z_i (|C| 0.4-0.8 per coordinate)",
                "timescales": "tau0 0.4-0.7 s; dormant modes 0.5-8 Hz, decay 0.8-3 s",
                "notes": f"k = none (K = {self.k}): observational activity is 1-D, but every micro intervention excites all "
                         "dormant modes and y then carries many incommensurate damped oscillations"}


# ============================================================================================ catalogue
def review_g_catalog() -> list[SystemDef]:
    S = SystemDef
    d = []
    d.append(S("g1_sync_pair", 5, "g1_sync_pair", lambda s: SyncPair(s),
               dict(n_core=60, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05, priv_noise=0.02), trap="G1",
               notes="G1 " + TRAPS_G["G1"] + ". Coordinates are the symmetric/antisymmetric combinations of the two "
                     "oscillators; dense code mixes them in every neuron."))
    d.append(S("g2_slow_state", 5, "g2_slow_state", lambda s: SlowStateOsc(s),
               dict(n_core=45, code="sparse", phi="identity", mixed_sign=True, obs_noise=0.05,
                    blocks=[dict(n=4, gain=2.0, mix=0.0)]),
               blocks=lambda rng, lat: [B.ParamReport("f0", tau=0.05)], trap="G2",
               notes="G2 " + TRAPS_G["G2"] + ". Sparse code: some neurons carry only s; 4 parameter-report neurons carry f0."))
    d.append(S("g3_sign_flip", 9, "g3_sign_flip", lambda s: SignFlip(s),
               dict(n_core=50, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05, core_gain=[1.0, 0.5]), trap="G3",
               notes="G3 " + TRAPS_G["G3"] + ". Readout y = m p is nonlinear in the state."))
    d.append(S("g4_delay_relay", 1, "g4_delay_relay", lambda s: DelayRelay(s, M=8),
               dict(n_core=80, code="sparse", phi="identity", mixed_sign=True, obs_noise=0.05), trap="G4",
               notes="G4 " + TRAPS_G["G4"] + ". Sparse code: relay populations carry single stages."))
    d.append(S("g5_exo_rhythm", 19, "g5_exo_rhythm", lambda s: ExoRhythm(s),
               dict(n_core=40, code="dense", phi="logistic", mixed_sign=False, obs_noise=0.05), trap="G5",
               notes="G5 " + TRAPS_G["G5"] + "."))
    d.append(S("g6_impostor", 7, "g6_impostor", lambda s: L.Leaky(s, tau_range=(0.3, 0.6)),
               dict(n_core=12, code="dense", phi="identity", mixed_sign=True, obs_noise=0.3,
                    blocks=[dict(n=60, gain=2.0, mix=0.5)]),
               blocks=lambda rng, lat: [Impostor(sigma=0.03)], trap="G6",
               notes="G6 " + TRAPS_G["G6"] + ". 12 causal neurons (30% observation noise, also carrying the impostor) vs 60 "
                     "impostor neurons; the impostor integrates the same input with the latent's own tau and gain."))
    d.append(S("g7_local_validity", 12, "g7_local_validity", lambda s: LocalValidity(s),
               dict(n_core=50, code="dense", phi="tanh", mixed_sign=True, obs_noise=0.05), trap="G7",
               notes="G7 " + TRAPS_G["G7"] + "."))
    d.append(S("g8_levy_switch", 6, "g8_levy_switch", lambda s: LevySwitch(s),
               dict(n_core=30, code="redundant", phi="tanh", mixed_sign=True, obs_noise=0.05), trap="G8",
               notes="G8 " + TRAPS_G["G8"] + "."))
    d.append(S("g9_param_drift", 19, "g9_param_drift", lambda s: DriftingOsc(s),
               dict(n_core=40, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05), trap="G9",
               notes="G9 " + TRAPS_G["G9"] + "."))
    d.append(S("g10_masked_highdim", 20, "g10_masked_highdim", lambda s: MaskedHighDim(s, P=16),
               dict(n_core=60, code="dense", phi="identity", mixed_sign=True, obs_noise=0.05, priv_noise=0.003, lam=30.0),
               trap="G10", notes="G10 " + TRAPS_G["G10"] + ". Non-compressible control: k = none."))
    return d


def build_review_g(suite_seed: int = 0, tier: str = "dev", names: list[str] | None = None):
    cache: dict = {}
    return [build_system(dd, suite_seed, tier, cache) for dd in review_g_catalog() if names is None or dd.name in names]


def get_review_g_system(name: str, suite_seed: int = 0, tier: str = "dev"):
    return build_review_g(suite_seed, tier, [name])[0]


# ============================================================================================ suite
_ORIGINAL_RUN_SYSTEM = _suite._run_system


@contextmanager
def _catalog_patched():
    """Point the (unchanged) suite builder at this catalogue for the duration of one build."""
    saved = (_suite.catalog, _suite._run_system)
    _suite.catalog = review_g_catalog
    _suite._run_system = _g_run_system
    try:
        yield _suite
    finally:
        _suite.catalog, _suite._run_system = saved


def _g_run_system(args):
    """Worker entry (picklable by reference): run the original per-system worker with this catalogue in scope
    (worker processes import p3synth.suite afresh, so the parent's patch is not visible there)."""
    saved = _suite.catalog
    _suite.catalog = review_g_catalog
    try:
        return _ORIGINAL_RUN_SYSTEM(args)
    finally:
        _suite.catalog = saved


def build_review_g_suite(out_public, out_truth, seed: int, *, tier: str = "heldout", scale: float | None = None,
                         workers: int | None = None, names: list[str] | None = None) -> dict:
    """Run p3synth.suite.build_suite on the Review G catalogue only (default tier "heldout", scale x2)."""
    with _catalog_patched() as S:
        return S.build_suite(Path(out_public), Path(out_truth), seed, tier, scale=scale, workers=workers, names=names)
