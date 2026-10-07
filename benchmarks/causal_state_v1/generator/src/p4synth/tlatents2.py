"""Latent dynamics of types 15-25 (traps, contexts, attractors, transients, non-compressible controls, confounding, aliasing)."""

from __future__ import annotations

import math

import numpy as np

from .latents import Latent, ew_matmul, relu, sat, smooth_cap, smooth_floor, softrelu, srelu0
from .tlatents import _sig


# ================================================================================================================ 15 low-variance trap
class LowVarTrap(Latent):
    """Task z1 (leaky, input-driven) whose input gain and offset are set by a HIDDEN slow state z2 (tau2 ~ 0.8 s) that passive
    input drives only with strength eps: dz1 = (-z1 + g u (1 + gam tanh z2) + c tanh z2)/tau1, dz2 = (-z2 + eps u)/tau2.
    'osc' variant: the task is a Hopf oscillator whose bifurcation parameter and frequency are modulated by z2 (k = 3).
    The readout sees z2 directly and multiplicatively."""

    name = "lowvar_trap"
    fixed_scale_dims = (-1,)

    def setup(self, rng, eps=0.0, osc=False):
        self.eps, self.osc = eps, osc
        self.k = 3 if osc else 2
        self.params.update({"tau1": (0.06, 0.15, "log"), "g": (1.0, 0.15, "log"), "tau2": (0.8, 0.2, "log"),
                            "gam": (0.8, 0.1, "log"), "c": (0.8, 0.1, "log")})
        if osc:
            self.params.update({"freq": (9.0, 0.1, "log"), "lam": (20.0, 0.15, "log"), "uc": (0.4, 0.05, "lin")})
        self.z_scale = (0.8, 0.8, 1.0) if osc else (1.0, 1.0)
        self.time_scale = 0.06

    def make_f(self, P):
        it1, g, it2, gam, c, eps = 1 / P["tau1"], P["g"], 1 / P["tau2"], P["gam"], P["c"], self.eps
        if not self.osc:
            def f(z, u):
                uu = sat(u[0], 4.0)
                t2 = math.tanh(z[1])
                return [(-z[0] + g * uu * (1.0 + gam * t2) + c * t2) * it1, (-z[1] + eps * uu) * it2]
            return f
        w0, lam, uc = 2 * math.pi * P["freq"], P["lam"], P["uc"]

        def f(z, u):
            x, y, h = z
            uu = sat(u[0], 4.0)
            t2 = math.tanh(h)
            mu = (uu - uc) * (1.0 + gam * t2) + 0.5 * c * t2
            r2 = smooth_cap(x * x + y * y, 16.0)
            a = lam * (mu - r2)
            w = w0 * (1.0 + 0.3 * t2)
            return [a * x - w * y + 3.0 * uu, a * y + w * x, (-h + eps * uu) * it2]
        return f

    def features(self, Z, U, P):
        h = np.tanh(Z[:, -1:])
        return np.hstack([Z[:, :-1], Z[:, :-1] * (1.0 + 0.8 * h), h])

    def zobs(self, Z):
        return Z[:, :-1]

    def zres(self, Z, P=None):
        return Z[:, -1:]


# ================================================================================================================ 16 context
class Context(Latent):
    """Context / hidden-parameter state c modulating a task. 'latch': c = peak detector of the input (dc = kap relu(u - c)), the
    task is a Hopf oscillator whose frequency is set by c; 'drift': c slowly tracks tanh(z1) (tau_c ~ 3 s) and sets the input gain
    of a leaky task integrator; 'init': c is a perfect memory (dc = 0) that only initial conditions or interventions set; it sets
    the gain and offset of the task."""

    name = "context"

    def setup(self, rng, mode="latch"):
        self.mode = mode
        if mode == "latch":
            self.k = 3
            self.params.update({"freq": (8.0, 0.1, "log"), "lam": (20.0, 0.15, "log"), "uc": (0.35, 0.05, "lin"),
                                "kap": (10.0, 0.15, "log"), "sens": (0.8, 0.1, "log")})
            self.z_scale = (0.8, 0.8, 1.0)
            self.time_scale = 0.1
        elif mode == "drift":
            self.k = 2
            self.params.update({"tau1": (0.1, 0.15, "log"), "g": (1.0, 0.15, "log"), "tau_c": (3.0, 0.2, "log"),
                                "gc": (1.2, 0.1, "log")})
            self.z_scale = (1.0, 0.5)
            self.time_scale = 0.1
        else:
            self.k = 2
            self.params.update({"tau1": (0.08, 0.15, "log"), "g": (1.0, 0.15, "log"), "gc": (1.0, 0.1, "log")})
            self.z_scale = (1.0, 1.0)
            self.time_scale = 0.08

    def make_f(self, P):
        mode = self.mode
        if mode == "latch":
            w0, lam, uc, kap, sens = 2 * math.pi * P["freq"], P["lam"], P["uc"], P["kap"], P["sens"]

            def f(z, u):
                x, y, c = z
                uu = sat(u[0], 4.0)
                mu = uu - uc
                r2 = smooth_cap(x * x + y * y, 16.0)
                a = lam * (mu - r2)
                w = w0 * smooth_floor(0.6 + sens * sat(c, 3.0), 0.2)
                return [a * x - w * y + 3.0 * uu, a * y + w * x, kap * srelu0(uu - c, 0.02)]
            return f
        if mode == "drift":
            it1, g, itc, gc = 1 / P["tau1"], P["g"], 1 / P["tau_c"], P["gc"]

            def f(z, u):
                z1, c = z
                return [(-z1 + g * sat(u[0], 4.0) * (1.0 + gc * math.tanh(c))) * it1, (-c + 0.8 * math.tanh(z1)) * itc]
            return f
        it1, g, gc = 1 / P["tau1"], P["g"], P["gc"]

        def f(z, u):
            z1, c = z
            tc = math.tanh(c)
            return [(-z1 + g * sat(u[0], 4.0) * (1.0 + gc * tc) + 0.5 * tc) * it1, 0.0]
        return f

    def zobs(self, Z):
        return Z[:, :1] if self.mode == "init" else None

    def zres(self, Z, P=None):
        return Z[:, 1:2] if self.mode == "init" else None


# ================================================================================================================ 17 / 19 adaptation, transients
class Adaptation(Latent):
    """Adapting response: dr = (-r + psi(g u - a))/tau_r, da = (-a + alpha r)/tau_a, psi rectified-saturating: an onset transient
    followed by an adapted steady state."""

    name = "adaptation"
    k = 2
    z_scale = (1.0, 1.0)

    def setup(self, rng, tau_a=0.2, alpha=1.5):
        self.params.update({"tau_r": (0.02, 0.15, "log"), "tau_a": (tau_a, 0.2, "log"), "g": (1.5, 0.12, "log"),
                            "alpha": (alpha, 0.12, "log"), "xm": (2.0, 0.05, "log")})
        self.time_scale = 0.02

    def make_f(self, P):
        itr, ita, g, al, xm = 1 / P["tau_r"], 1 / P["tau_a"], P["g"], P["alpha"], P["xm"]

        def f(z, u):
            r, a = z
            x = g * sat(u[0], 4.0) - a
            psi = xm * math.tanh(srelu0(x, 0.05) / xm)
            return [(-r + psi) * itr, (-a + al * r) * ita]
        return f


class Transient3(Latent):
    """Onset transient by non-normal amplification: fast z1 follows u (tau 20 ms), slow z3 follows z1 (tau 300 ms), z2 amplifies
    their difference (dz2 = (-z2 + G (z1 - z3))/tau2): a large transient at input changes, then a steady state carried by z3."""

    name = "transient3"
    k = 3
    z_scale = (1.0, 1.5, 1.0)

    def setup(self, rng):
        self.params.update({"tau1": (0.02, 0.15, "log"), "tau2": (0.03, 0.15, "log"), "tau3": (0.3, 0.2, "log"),
                            "G": (3.0, 0.15, "log")})
        self.time_scale = 0.02

    def make_f(self, P):
        i1, i2, i3, G = 1 / P["tau1"], 1 / P["tau2"], 1 / P["tau3"], P["G"]

        def f(z, u):
            a, b, c = z
            return [(-a + sat(u[0], 4.0)) * i1, (-b + G * (a - c)) * i2, (-c + a) * i3]
        return f


class BurstOnset(Latent):
    """Damped burst at input changes: fast s and slow a filter the input; a Stuart-Landau oscillator (x, y) has
    mu = mu1 (relu(s - a) - uc) (> 0 only transiently after an onset), so the rhythm appears at onset and decays to a steady
    state."""

    name = "burst_onset"
    k = 4
    z_scale = (0.6, 0.6, 1.0, 1.0)

    def setup(self, rng):
        self.params.update({"freq": (11.0, 0.1, "log"), "lam": (20.0, 0.15, "log"), "mu1": (2.0, 0.15, "log"),
                            "uc": (0.15, 0.03, "lin"), "tau_s": (0.02, 0.15, "log"), "tau_a": (0.4, 0.2, "log")})
        self.time_scale = 0.02

    def make_f(self, P):
        w, lam, mu1, uc, its, ita = 2 * math.pi * P["freq"], P["lam"], P["mu1"], P["uc"], 1 / P["tau_s"], 1 / P["tau_a"]

        def f(z, u):
            x, y, s, a = z
            uu = sat(u[0], 4.0)
            mu = mu1 * (srelu0(s - a, 0.02) - uc)
            r2 = smooth_cap(x * x + y * y, 16.0)
            q = lam * (mu - r2)
            return [q * x - w * y + 0.3 * (s - a) * w, q * y + w * x, (-s + uu) * its, (-a + uu) * ita]
        return f


# ================================================================================================================ 18 attractors
class MultiWell(Latent):
    """Gradient flow in a multi-well landscape V = -sum_i A_i exp(-|z - w_i|^2 / 2 sig^2) + kappa |z|^4 / 4 (wells at w_i; the rest
    well at 0), tilted by the input along d: dz = r (-grad V(z) + grad V(0)) + beta u d. trap=True: the landscape is symmetric in
    z2 and the input acts along z1 only, so passive trajectories never leave z2 = 0; the well at (0, 1) is reachable only by
    perturbation."""

    name = "multiwell"
    k = 2
    z_scale = (1.0, 1.0)

    def setup(self, rng, trap=False):
        self.trap = trap
        if trap:
            self.W = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [0.0, -1.0]])
            self.A = np.array([1.0, 0.9, 0.95, 0.95])
            self.d = np.array([1.0, 0.0])
        else:
            self.W = np.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
            self.A = np.array([1.0, 0.9, 0.85, 0.8])
            self.d = np.array([1.0, 0.45]) / np.linalg.norm([1.0, 0.45])
        self.params.update({"rate": (20.0, 0.15, "log"), "sig": (0.33, 0.04, "log"), "beta": (1.6, 0.08, "log"),
                            "kap": (0.3, 0.1, "log")})
        self.time_scale = 0.05

    def make_f(self, P):
        r, s2, be, kap = P["rate"], P["sig"] ** 2, P["beta"], P["kap"]
        W = self.W.tolist()
        A = self.A.tolist()
        d = self.d.tolist()

        def gradV(x, y):
            gx = gy = 0.0
            for (wx, wy), a in zip(W, A):
                dx, dy = x - wx, y - wy
                e = a * math.exp(-(dx * dx + dy * dy) / (2 * s2)) / s2
                gx += e * dx
                gy += e * dy
            q = kap * (x * x + y * y)
            return gx + q * x, gy + q * y
        g0 = gradV(0.0, 0.0)

        def f(z, u):
            x, y = sat(z[0], 4.0), sat(z[1], 4.0)
            gx, gy = gradV(x, y)
            uu = sat(u[0], 4.0)
            bu = be * r * uu
            return [r * (-gx + g0[0]) + bu * d[0], r * (-gy + g0[1]) + bu * d[1]]
        return f

    def extra_spec(self):
        return {"W": self.W.tolist(), "A": self.A.tolist(), "d": self.d.tolist()}

    def zobs(self, Z):
        return Z[:, :1] if self.trap else None

    def zres(self, Z, P=None):
        return Z[:, 1:2] if self.trap else None


class SubHopf(Latent):
    """Subcritical Hopf: rest and a large limit cycle coexist, dz = lam (mu(u) + 2 r^2 - r^4) z + omega J z + beta u e1,
    mu = mu0 + mu1 u (bistable for -1 < mu < 0): the rhythm starts only when the state is pushed across the unstable cycle."""

    name = "subhopf"
    k = 2
    z_scale = (1.3, 1.3)

    def setup(self, rng, freq=8.0):
        self.params.update({"freq": (freq, 0.1, "log"), "lam": (10.0, 0.15, "log"), "mu0": (-0.85, 0.04, "lin"),
                            "mu1": (0.5, 0.1, "log"), "beta": (20.0, 0.15, "log")})
        self.time_scale = 1.0 / freq

    def make_f(self, P):
        w, lam, mu0, mu1, be = 2 * math.pi * P["freq"], P["lam"], P["mu0"], P["mu1"], P["beta"]

        def f(z, u):
            x, y = z
            uu = sat(u[0], 4.0)
            mu = mu0 + mu1 * uu
            r2 = smooth_cap(x * x + y * y, 9.0)
            a = lam * (mu + 2.0 * r2 - r2 * r2)
            return [a * x - w * y + be * uu, a * y + w * x]
        return f


# ================================================================================================================ 20 / 21 non-compressible
class SlowModes(Latent):
    """High-dimensional near-normal dynamics: k modes dz = Q Lambda Q^T sat(z) + b s(u) with Q orthogonal (a normal matrix: no
    transient amplification, a flat Hankel spectrum), Lambda = complex pairs with slow decay (0.25-1.2 s) and frequencies spread over
    0.4-18 Hz (distinct time courses) plus at most one slow real mode. Every coordinate mixes all modes, so single units excite and
    the readout reads every mode comparably. input_modes = None: the input drives every mode (type 20, no compact state);
    input_modes = m: only the first m modes (type 21: passive trajectories from rest stay exactly in an m-dimensional subspace).
    sat = identity ('lin') or a soft saturation c tanh(z / c) with c = 3 ('sat', weakly nonlinear)."""

    name = "slow_modes"
    vector = True          # the vector field takes and returns numpy arrays (high-dimensional; numpy integration loop)

    def setup(self, rng, k=30, input_modes=None, sat_c=None):
        self.k = int(k)
        self.m = input_modes
        self.sat_c = sat_c
        Q, _ = np.linalg.qr(rng.standard_normal((self.k, self.k)))
        self.Q = Q
        self.modes = []
        i = 0
        nreal0 = 0 if self.m is None else int(self.m)
        for _ in range(nreal0):                 # type 21: the input-driven modes are real (an exactly m-dimensional passive subspace)
            self.modes.append(("r", float(rng.uniform(0.2, 1.2))))
            i += 1
        npair = (self.k - nreal0) // 2
        freqs = np.exp(np.linspace(math.log(0.5), math.log(20.0), max(npair, 1)))
        rng.shuffle(freqs)
        j = 0
        while i < self.k:
            if i + 1 < self.k:
                self.modes.append(("c", float(freqs[j] * math.exp(0.05 * rng.standard_normal())), float(rng.uniform(0.2, 1.2))))
                j += 1
                i += 2
            else:
                self.modes.append(("r", float(rng.uniform(0.2, 1.2))))
                i += 1
        # input loading per mode coordinate (equal magnitudes, random signs; type 21: only the first m coordinates)
        bx = rng.choice([-1.0, 1.0], self.k) * rng.uniform(0.8, 1.2, self.k)
        if self.m is not None:
            bx[self.m:] = 0.0
        self.bx = bx
        self.params.update({"tscale": (1.0, 0.12, "log"), "gu": (1.0, 0.15, "log")})
        self.z_scale = tuple([1.0] * self.k)
        self.time_scale = 0.25

    def Lam(self, P):
        k = self.k
        Lm = np.zeros((k, k))
        i = 0
        for md in self.modes:
            if md[0] == "c":
                w, s = 2 * math.pi * md[1] / P["tscale"], 1.0 / (md[2] * P["tscale"])
                Lm[i:i + 2, i:i + 2] = [[-s, -w], [w, -s]]
                i += 2
            else:
                Lm[i, i] = -1.0 / (md[1] * P["tscale"])
                i += 1
        return Lm

    def make_f(self, P):
        Lm = self.Lam(P)
        A = self.Q @ Lm @ self.Q.T
        # input vector: each driven mode coordinate is loaded with its own decay rate, so every driven mode has a passive
        # amplitude of order 1 at the nominal input
        rate = np.abs(np.diag(Lm))
        b = self.Q @ (self.bx * rate * 0.6) * P["gu"]
        c = self.sat_c

        def f(z, u):
            zz = np.asarray(z, dtype=float)
            if c is not None:
                zz = c * np.tanh(zz / c)
            return A @ zz + b * sat(u[0], 4.0)
        return f

    def zobs(self, Z):
        if self.m is None:
            return None
        return ew_matmul(Z, self.Q[:, :self.m])

    def passive_basis(self):
        """Orthonormal basis of the exactly invariant passive subspace (type 21), kept invariant by weight noise (engine)."""
        return None if self.m is None else self.Q[:, :self.m]

    def zres(self, Z, P=None):
        if self.m is None:
            return None
        Qm = self.Q[:, :self.m]
        return Z - ew_matmul(ew_matmul(Z, Qm), Qm.T)

    def extra_spec(self):
        return {"Q": self.Q.round(8).tolist(), "modes": self.modes, "bx": self.bx.round(8).tolist(), "m": self.m,
                "sat_c": self.sat_c}


# ================================================================================================================ 22 slaved variable
class Slaved(Latent):
    """Readout easy, causal state hard: z2 is slaved to z1 (dz2 = (h(z1) - z2)/tau2, tau2 << tau1) and feeds its deviation back
    (dz1 = (-z1 + g u + kap (z2 - h(z1)))/tau1). Passively z2 = h(z1), so z1 alone predicts passive data; interventions on z2's
    units displace z2 from h(z1) and leave lasting shifts of z1; the readout weights z2 strongly."""

    name = "slaved"
    k = 2
    z_scale = (1.0, 1.0)

    def setup(self, rng, rho=0.1, tau1=0.15):
        self.params.update({"tau1": (tau1, 0.15, "log"), "rho": (rho, 0.1, "log"), "g": (1.0, 0.15, "log"),
                            "kap": (2.0, 0.1, "log"), "hg": (1.5, 0.1, "log")})
        self.time_scale = rho * tau1

    def make_f(self, P):
        it1, it2, g, kap, hg = 1 / P["tau1"], 1 / (P["rho"] * P["tau1"]), P["g"], P["kap"], P["hg"]

        def f(z, u):
            z1, z2 = sat(z[0], 4.0), sat(z[1], 4.0)
            h = math.tanh(hg * z1)
            return [(-z1 + g * sat(u[0], 4.0) + kap * (z2 - h)) * it1, (h - z2) * it2]
        return f

    def zobs(self, Z):
        return Z[:, :1]

    def zres(self, Z, P=None):
        hg = (P or self.nominal())["hg"]
        return Z[:, 1:2] - np.tanh(hg * 4.0 * np.tanh(Z[:, :1] / 4.0))


# ================================================================================================================ 23 confounding
class Confounded(Latent):
    """Intervention confounding: a and c are driven by the SAME input through the same filter, so passive trajectories keep a = c
    (exact aliasing by a common cause; delta > 0 makes the filters slightly different); their mutual coupling and nonlinearity
    differ, so once an intervention separates them they evolve differently, and the readout weights them differently. Optional
    visible third state b (independent input filter)."""

    name = "confounded"

    def setup(self, rng, delta=0.0, third=False):
        self.delta, self.third = delta, third
        self.k = 3 if third else 2
        self.params.update({"tau": (0.08, 0.15, "log"), "g": (1.0, 0.15, "log"), "ka": (3.0, 0.15, "log"),
                            "kc": (0.5, 0.15, "log"), "nu": (4.0, 0.1, "log")})
        if third:
            self.params.update({"tau_b": (0.3, 0.15, "log"), "gb": (0.8, 0.15, "log")})
        self.z_scale = tuple([1.0] * self.k)
        self.time_scale = 0.08

    def make_f(self, P):
        it, g, ka, kc, nu = 1 / P["tau"], P["g"], P["ka"], P["kc"], P["nu"]
        itc = it / (1.0 + self.delta)
        third = self.third
        if third:
            itb, gb = 1 / P["tau_b"], P["gb"]

        def f(z, u):
            a, c = sat(z[0], 4.0), sat(z[1], 4.0)
            uu = sat(u[0], 4.0)
            dca = c - a
            out = [(-a + g * uu + ka * dca) * it, (-c + g * uu - kc * dca + nu * sat(dca, 1.5) * math.sqrt(sat(dca, 1.5) ** 2 + 1e-4)) * itc]
            if third:
                out.append((-z[2] + gb * uu) * itb)
            return out
        return f

    def features(self, Z, U, P):
        return np.hstack([Z, (Z[:, 0] * Z[:, 1])[:, None]])

    def zobs(self, Z):
        cm = 0.5 * (Z[:, :1] + Z[:, 1:2])
        return np.hstack([cm, Z[:, 2:]]) if self.third else cm

    def zres(self, Z, P=None):
        return Z[:, :1] - Z[:, 1:2]


# ================================================================================================================ 25 aliasing
class Aliased(Latent):
    """Same immediate readout, different causal state: z = (a, p, s). a is the read-out task state, p a perturbation-sensitive state
    no input drives (dp = -p/tau_p), s a bistable hidden switch (wells 0 and 1, no input). da = (-a + g u + kp sigma(s) p)/tau_a
    with sigma(0) = -1, sigma(1) = +1: two states differing only in s have identical readout and identical passive futures, but
    opposite responses to perturbations of p."""

    name = "aliased"
    k = 3
    z_scale = (1.0, 1.0, 1.0)

    def setup(self, rng):
        self.params.update({"tau_a": (0.06, 0.15, "log"), "tau_p": (0.15, 0.15, "log"), "g": (1.0, 0.15, "log"),
                            "kp": (2.0, 0.1, "log"), "lam_s": (15.0, 0.15, "log")})
        self.time_scale = 0.06

    def make_f(self, P):
        ita, itp, g, kp, ls = 1 / P["tau_a"], 1 / P["tau_p"], P["g"], P["kp"], P["lam_s"]
        t2 = math.tanh(2.0)

        def f(z, u):
            a, p, s = z[0], sat(z[1], 4.0), sat(z[2], 3.0)
            sig = math.tanh(4.0 * (s - 0.5)) / t2
            return [(-a + g * sat(u[0], 4.0) + kp * sig * p) * ita, -p * itp, ls * (-s * (s - 0.5) * (s - 1.0))]
        return f

    def features(self, Z, U, P):
        return Z[:, :1]

    def zobs(self, Z):
        return Z[:, :1]

    def zres(self, Z, P=None):
        return Z[:, 1:3]
