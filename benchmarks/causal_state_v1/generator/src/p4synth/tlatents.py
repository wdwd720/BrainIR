"""Latent dynamics of the 25 system types (rest z = 0 and F(0, 0) = 0 for every parameter draw; python-float vector fields)."""

from __future__ import annotations

import math

import numpy as np

from .latents import Latent, relu, sat, smooth_cap, smooth_floor, softrelu, srelu0


def _sig(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    e = math.exp(x)
    return e / (1.0 + e)


def linear_field(A, B):
    """Unrolled python vector field z -> A z + B sat(u0) (code-generated: no loops, constants inlined)."""
    k = A.shape[0]
    zs = ", ".join(f"z{i}" for i in range(k))
    rows = []
    for i in range(k):
        terms = [f"{float(A[i, j])!r}*z{j}" for j in range(k) if A[i, j] != 0.0]
        if B[i] != 0.0:
            terms.append(f"{float(B[i])!r}*uu")
        rows.append(" + ".join(terms) if terms else "0.0")
    src = (f"def f(z, u):\n    {zs}{',' if k == 1 else ''} = z\n    uu = sat(u[0], 4.0)\n"
           f"    return [{', '.join(rows)}]\n")
    ns = {"sat": sat}
    exec(src, ns)
    return ns["f"]


def lat_rk4(latent, P, stim, t_end=2.0, dt=1e-3, z0=None):
    """Integrate the latent ODE alone (python RK4) for a piecewise-constant stimulus [[t, u], ...]; returns (T, k)."""
    f = latent.make_f(P)
    T = int(round(t_end / dt)) + 1
    z = [0.0] * latent.k if z0 is None else list(z0)
    out = np.empty((T, latent.k))
    st = sorted(stim, key=lambda r: r[0])
    j = 0
    for n in range(T):
        out[n] = z
        t = n * dt
        while j + 1 < len(st) and st[j + 1][0] <= t + 1e-12:
            j += 1
        u = [float(v) for v in np.atleast_1d(st[j][1])]
        if len(u) < latent.n_u:
            u = u * latent.n_u
        k1 = f(z, u)
        k2 = f([a + 0.5 * dt * b for a, b in zip(z, k1)], u)
        k3 = f([a + 0.5 * dt * b for a, b in zip(z, k2)], u)
        k4 = f([a + dt * b for a, b in zip(z, k3)], u)
        z = [a + dt / 6 * (b + 2 * c + 2 * d + e) for a, b, c, d, e in zip(z, k1, k2, k3, k4)]
    return out


# ================================================================================================================ 1 linear SSM
class LinearSSM(Latent):
    """Linear controlled state-space model dz/dt = A z + B u, A = V Lambda V^-1 (fixed non-normal modal basis V; complex pairs
    (sigma, omega) and real modes -1/tau drawn per trajectory); linear readout."""

    name = "linear_ssm"

    def setup(self, rng, modes=(("c", 9.0, 4.0),), cond=2.5, chain=None):
        self.modes = [tuple(m) for m in modes]
        k = sum(2 if m[0] == "c" else 1 for m in self.modes)
        self.k = k
        self.chain = chain
        if chain is not None:           # explicit feed-forward chain (non-normal amplification), V = I
            self.V = np.eye(k)
        else:
            V = np.eye(k) + rng.standard_normal((k, k)) * 0.6
            u_, _, vt = np.linalg.svd(V)
            s_ = np.linspace(cond, 1.0, k) if k > 1 else np.array([1.0])
            self.V = (u_ * s_) @ vt
        self.Vi = np.linalg.inv(self.V)
        self.bxi = rng.uniform(0.6, 1.4, k) * rng.choice([-1, 1], k)
        if chain is not None:
            self.bxi = np.zeros(k)
            self.bxi[0] = 1.0
        for j, m in enumerate(self.modes):
            if m[0] == "c":
                self.params[f"f{j}"] = (float(m[1]), 0.1, "log")
                self.params[f"s{j}"] = (float(m[2]), 0.2, "log")
            else:
                self.params[f"t{j}"] = (float(m[1]), 0.2, "log")
        self.params["bg"] = (1.0, 0.2, "log")
        self.time_scale = min([1.0 / m[2] if m[0] == "c" else m[1] for m in self.modes])

    def AB(self, P):
        k = self.k
        Lam = np.zeros((k, k))
        i = 0
        for j, m in enumerate(self.modes):
            if m[0] == "c":
                w, s = 2 * math.pi * P[f"f{j}"], P[f"s{j}"]
                Lam[i:i + 2, i:i + 2] = [[-s, -w], [w, -s]]
                i += 2
            else:
                Lam[i, i] = -1.0 / P[f"t{j}"]
                i += 1
        if self.chain is not None:
            for a in range(k - 1):
                Lam[a + 1, a] = self.chain[a] / self.modes[a + 1][1]
            B = np.zeros(k)
            B[0] = P["bg"] / self.modes[0][1]
        else:
            B = self.V @ (-Lam @ self.bxi) * P["bg"]      # modal steady state under u = 1 equals bxi (O(1))
        A = self.V @ Lam @ self.Vi
        return A, B

    def make_f(self, P):
        A, B = self.AB(P)
        return linear_field(A, B)

    def extra_spec(self):
        return {"V": self.V.round(8).tolist(), "bxi": self.bxi.round(8).tolist(), "modes": self.modes, "chain": self.chain}


# ================================================================================================================ 2 oscillators
class Hopf(Latent):
    """Stuart-Landau oscillator with input-controlled Hopf bifurcation: dz = lam (mu(u) - |z|^2) z + omega J z + b u e1,
    mu = mu1 (u - u_c): a focus at rest, a limit cycle of radius ~ sqrt(mu) (phase-dependent responses) under the input; the
    small direct drive b u e1 breaks the symmetry so the rhythm starts deterministically from rest."""

    name = "hopf"
    k = 2
    z_scale = (0.8, 0.8)

    def setup(self, rng, freq=10.0, lam=20.0, uc=0.4):
        self.params.update({"freq": (freq, 0.1, "log"), "lam": (lam, 0.2, "log"), "mu1": (1.0, 0.15, "log"),
                            "uc": (uc, 0.05, "lin"), "bu": (3.0, 0.1, "log")})
        self.time_scale = 1.0 / freq

    def make_f(self, P):
        w, lam, mu1, uc, bu = 2 * math.pi * P["freq"], P["lam"], P["mu1"], P["uc"], P["bu"]

        def f(z, u):
            x, y = z
            uu = sat(u[0], 4.0)
            mu = mu1 * (uu - uc)
            r2 = smooth_cap(x * x + y * y, 16.0)
            a = lam * (mu - r2)
            return [a * x - w * y + bu * uu, a * y + w * x]
        return f


class FHN(Latent):
    """FitzHugh-Nagumo relaxation oscillator shifted so rest = 0: dv = (v - v^3/3 - w + I)/tau, dw = eps (v + a - b w)/tau,
    I = g_u u (oscillates inside the Hopf window I ~ 0.33 - 1.4)."""

    name = "fhn"
    k = 2
    z_scale = (2.0, 1.0)

    def setup(self, rng, tau=0.007, a=0.7, b=0.8):
        from scipy.optimize import brentq
        self.a, self.b = a, b
        self.v0 = brentq(lambda v: v - v ** 3 / 3 - (v + a) / b, -3, 3)
        self.w0 = (self.v0 + a) / b
        self.params.update({"tau": (tau, 0.08, "log"), "eps": (0.1, 0.1, "log"), "gu": (0.6, 0.08, "log")})
        self.time_scale = 0.03

    def make_f(self, P):
        it, eps, gu = 1.0 / P["tau"], P["eps"], P["gu"]
        a, b, v0, w0 = self.a, self.b, self.v0, self.w0

        def f(z, u):
            v = v0 + sat(z[0], 4.5)
            w = z[1] + w0
            I = gu * sat(u[0], 4.0)
            return [(v - v * v * v / 3.0 - w + I) * it, eps * (v + a - b * w) * it]
        return f


class ShearHopf(Latent):
    """Stuart-Landau oscillator with amplitude- and input-dependent frequency (amplitude kicks change the phase velocity:
    effects grow as phases drift): omega = w0 (1 + c_r (r^2 - r0^2) + c_u (u - 1))."""

    name = "shear_hopf"
    k = 2
    z_scale = (0.8, 0.8)

    def setup(self, rng, freq=9.0):
        self.params.update({"freq": (freq, 0.1, "log"), "lam": (15.0, 0.2, "log"), "mu1": (1.0, 0.15, "log"),
                            "uc": (0.35, 0.05, "lin"), "cr": (0.8, 0.15, "lin"), "cu": (0.3, 0.05, "lin"),
                            "bu": (3.0, 0.1, "log")})
        self.time_scale = 1.0 / freq

    def make_f(self, P):
        w0 = 2 * math.pi * P["freq"]
        lam, mu1, uc, cr, cu, bu = P["lam"], P["mu1"], P["uc"], P["cr"], P["cu"], P["bu"]
        r0 = math.sqrt(max(mu1 * (1 - uc), 1e-3))

        def f(z, u):
            x, y = z
            uu = sat(u[0], 4.0)
            mu = mu1 * (uu - uc)
            r2 = smooth_cap(x * x + y * y, 16.0)
            a = lam * (mu - r2)
            w = w0 * smooth_floor(1.0 + cr * (r2 - r0 * r0) + cu * (uu - 1.0), 0.2)
            return [a * x - w * y + bu * uu, a * y + w * x]
        return f


# ================================================================================================================ 3 / 4 integrators
class LeakyInt(Latent):
    """Leaky integrator(s): dz_i = -z_i / tau_i + beta_i s(u), s = saturating input gain (k independent integrators with different
    time constants and gains)."""

    name = "leaky_integrator"

    def setup(self, rng, taus=(0.3,), gains=(1.0,), u_sat=4.0):
        self.k = len(taus)
        for i, (t, g) in enumerate(zip(taus, gains)):
            self.params[f"tau{i}"] = (float(t), 0.2, "log")
            self.params[f"g{i}"] = (float(g), 0.2, "log")
        self.u_sat = u_sat
        self.z_scale = tuple(float(g) for g in gains)
        self.time_scale = float(min(taus))

    def make_f(self, P):
        k, us = self.k, self.u_sat
        it = [1.0 / P[f"tau{i}"] for i in range(k)]
        g = [P[f"g{i}"] * it[i] for i in range(k)]

        def f(z, u):
            s = us * math.tanh(u[0] / us)
            return [(-z[i]) * it[i] + g[i] * s for i in range(k)]
        return f


class PerfectInt(Latent):
    """Perfect (leak-free) integrator(s) with soft walls: dz = beta B d(u) (1 - |z|^2/zm^2), memory is perfect while the input is
    off. mode 'signed': d = u (u - u0) integrates up above the reference level u0 and down below it. mode 'plane' (k = 2, one input):
    d = (u, u (u - u0)): the first coordinate integrates the input, the second integrates up above u0 and down below it, so the
    input level steers the direction of integration in the plane."""

    name = "perfect_integrator"

    def setup(self, rng, k=1, beta=0.5, zm=1.5, mode="plain", u0=0.8, n_u=1):
        self.k, self.n_u, self.mode, self.u0 = k, n_u, mode, u0
        self.params["beta"] = (beta, 0.2, "log")
        self.params["zm"] = (zm, 0.05, "log")
        if mode == "plane":
            self.B = np.array([[1.0, 0.0], [0.25 * float(rng.standard_normal()), 1.5]])     # (k, channels of d)
        else:
            self.B = np.ones((1, n_u)) / n_u if k == 1 else np.eye(k, n_u) + 0.3 * rng.standard_normal((k, n_u))
        self.z_scale = tuple([1.0] * k)
        self.time_scale = 1.0 / beta

    def make_f(self, P):
        be, zm2 = P["beta"], P["zm"] ** 2
        Bl = self.B.tolist()
        k, n_u, mode, u0 = self.k, self.n_u, self.mode, self.u0
        nd = len(Bl[0])

        def f(z, u):
            wall = 1.0 - sum(a * a for a in z) / zm2
            if mode == "signed":
                d = [sat(u[j], 4.0) * (sat(u[j], 4.0) - u0) for j in range(n_u)]
            elif mode == "plane":
                s = sat(u[0], 4.0)
                d = [s, s * (s - u0)]
            else:
                d = [sat(u[j], 4.0) for j in range(n_u)]
            return [be * wall * sum(Bl[i][j] * d[j] for j in range(nd)) for i in range(k)]
        return f

    def extra_spec(self):
        return {"B": self.B.round(8).tolist()}


# ================================================================================================================ 5 gated memory
class GatedMemory(Latent):
    """Gated memory, z = (s buffer, a gate drive, m memory). 'onset': a = slow adaptation of the input, gate g = sig((s-a-th)/w) opens
    transiently at input onsets; 'level': a = a fast filtered copy of the input level, g = sig((a-th)/w) opens while the input
    exceeds the level th. dm = g (s - m)/tau_w - (1-g) m/tau_leak."""

    name = "gated_memory"
    k = 3
    z_scale = (1.0, 1.0, 1.0)

    def setup(self, rng, mode="onset", th=0.3, n_u=1, trap=False):
        self.mode, self.n_u, self.trap = mode, n_u, trap
        self.params.update({"tau_s": (0.03, 0.15, "log"), "tau_a": (0.2 if mode == "onset" else 0.03, 0.15, "log"),
                            "th": (th, 0.04, "lin"), "w": (0.06, 0.1, "log"), "tau_w": (0.02, 0.15, "log"),
                            "tau_leak": (5.0, 0.2, "log")})
        self.time_scale = 0.03

    def make_f(self, P):
        its, ita, th, w, itw, itl = 1 / P["tau_s"], 1 / P["tau_a"], P["th"], P["w"], 1 / P["tau_w"], 1 / P["tau_leak"]
        onset = self.mode == "onset"

        def f(z, u):
            s, a, m = z
            u0 = sat(u[0], 4.0)
            g = _sig((s - a - th) / w) if onset else _sig((a - th) / w)
            da = (-a + u0) * ita
            return [(-s + u0) * its, da, g * (s - m) * itw - (1.0 - g) * m * itl]
        return f

    def zobs(self, Z):
        return Z[:, :2] if self.trap else None

    def zres(self, Z, P=None):
        return Z[:, 2:3] if self.trap else None


# ================================================================================================================ 6 bistable
class Bistable(Latent):
    """Bistable switch z1: dz1 = lam(-z1 (z1-th)(z1-1)) + beta u - gamma a + c2 z2 (the input flips it above u_c ~ 0.8); optional
    slow adaptation a (da = (z1 - a)/tau_a) and optional HIDDEN switch z2 (no input, rest 0, flips only under perturbation) that
    lowers z1's threshold and multiplies the readout gain by (1 + 1.5 z2)."""

    name = "bistable"

    def setup(self, rng, adapt=False, hidden=False):
        self.adapt, self.hidden = adapt, hidden
        self.k = 1 + int(adapt) + int(hidden)
        self.params.update({"lam": (20.0, 0.12, "log"), "th": (0.5, 0.03, "lin"), "beta": (1.2, 0.1, "log")})
        if adapt:
            self.params.update({"tau_a": (0.5, 0.2, "log"), "gamma": (6.0, 0.15, "log")})
        if hidden:
            self.params.update({"lam2": (12.0, 0.15, "log"), "c2": (0.6, 0.1, "log")})
        self.z_scale = tuple([1.0] * self.k)
        self.time_scale = 0.05

    def make_f(self, P):
        lam, th, be = P["lam"], P["th"], P["beta"]
        adapt, hidden = self.adapt, self.hidden
        ita, ga = (1 / P["tau_a"], P["gamma"]) if adapt else (0.0, 0.0)
        lam2, c2 = (P["lam2"], P["c2"]) if hidden else (0.0, 0.0)

        def f(z, u):
            x = sat(z[0], 3.0)
            d = lam * (-x * (x - th) * (x - 1.0)) + be * sat(u[0], 4.0)
            out = []
            i = 1
            if adapt:
                a = z[i]
                d -= ga * a
                out.append((z[0] - a) * ita)
                i += 1
            if hidden:
                y = sat(z[i], 3.0)
                d += c2 * 0.1 * lam * y
                out.append(lam2 * (-y * (y - 0.5) * (y - 1.0)))
            return [d] + out
        return f

    def features(self, Z, U, P):
        if not self.hidden:
            return Z
        F = Z.copy()
        F[:, 0] = Z[:, 0] * (1.0 + 1.5 * np.clip(Z[:, -1], -0.5, 1.5))
        return F

    def zobs(self, Z):
        return Z[:, :1] if self.hidden else None

    def zres(self, Z, P=None):
        return Z[:, -1:] if self.hidden else None


# ================================================================================================================ 7 WTA
class WTA(Latent):
    """Winner-take-all among m pools: tau dz_i = -z_i + psi(alpha z_i - beta sum_{j!=i} z_j + w_i g u), psi rectified-saturating;
    input weights differ slightly so the input selects a winner; alpha > 1 gives hysteresis (the winner persists)."""

    name = "wta"

    def setup(self, rng, m=3, alpha=0.6, beta=1.6, spread=0.08):
        self.k = m
        self.w = 1.0 + spread * np.sort(rng.uniform(-1, 1, m))[::-1]
        self.params.update({"tau": (0.03, 0.12, "log"), "alpha": (alpha, 0.05, "lin"), "beta": (beta, 0.08, "log"),
                            "gu": (1.2, 0.12, "log"), "xm": (2.0, 0.05, "log")})
        for i in range(m):
            self.params[f"dw{i}"] = (0.0, 0.03, "lin")
        self.z_scale = tuple([1.0] * m)
        self.time_scale = 0.03

    def make_f(self, P):
        m = self.k
        it, al, be, gu, xm = 1 / P["tau"], P["alpha"], P["beta"], P["gu"], P["xm"]
        w = [float(self.w[i]) + P[f"dw{i}"] for i in range(m)]

        def f(z, u):
            uu = sat(u[0], 4.0) * gu
            tot = sum(z)
            out = []
            for i in range(m):
                x = al * z[i] - be * (tot - z[i]) + w[i] * uu
                psi = xm * math.tanh(srelu0(x, 0.05) / xm)          # smooth rectified-saturating transfer
                out.append((-z[i] + psi) * it)
            return out
        return f

    def extra_spec(self):
        return {"w": self.w.round(8).tolist()}


# ================================================================================================================ 8 controller
class Controller(Latent):
    """Negative-feedback control. 'pi': plant tau_p dp = -p + w u - c, integral controller dc = ki (p - r) with r = 0 (perfect
    adaptation); 'pid': adds a filtered-derivative state d; 'setpoint': the reference r is a memory state (tau_r ~ 10 s) that no
    passive input moves."""

    name = "controller"

    def setup(self, rng, mode="pi"):
        self.mode = mode
        self.k = {"pi": 2, "pid": 3, "setpoint": 3}[mode]
        self.params.update({"tau_p": (0.05, 0.15, "log"), "w": (1.0, 0.15, "log"), "ki": (15.0, 0.2, "log")})
        if mode == "pid":
            self.params.update({"kp": (0.8, 0.2, "log"), "kd": (0.02, 0.2, "log"), "tau_d": (0.02, 0.1, "log")})
        if mode == "setpoint":
            self.params["tau_r"] = (10.0, 0.2, "log")
        self.z_scale = (1.0, 1.0, 0.6)[:self.k]
        self.time_scale = 0.05

    def make_f(self, P):
        itp, w, ki = 1 / P["tau_p"], P["w"], P["ki"]
        mode = self.mode
        kp = kd = itd = itr = 0.0
        if mode == "pid":
            kp, kd, itd = P["kp"], P["kd"], 1 / P["tau_d"]
        if mode == "setpoint":
            itr = 1 / P["tau_r"]

        def f(z, u):
            uu = sat(u[0], 4.0)
            p = sat(z[0], 5.0)
            c = sat(z[1], 5.0)
            if mode == "pi":
                return [(-p + w * uu - c) * itp, ki * p]
            if mode == "pid":
                d = z[2]
                deriv = (p - d) * itd
                return [(-p + w * uu - (c + kp * p + kd * deriv)) * itp, ki * p, deriv]
            r = sat(z[2], 3.0)
            return [(-p + w * uu - c) * itp, ki * (p - r), -r * itr]
        return f

    def zobs(self, Z):
        return Z[:, :2] if self.mode == "setpoint" else None

    def zres(self, Z, P=None):
        return Z[:, 2:3] if self.mode == "setpoint" else None


# ================================================================================================================ 9 fast / slow
class FastSlow(Latent):
    """Coupled fast / slow dynamics. 'burst': FHN-like fast oscillator (v, w) with slow adaptation s terminating bursts; 'relay':
    fast relaxation f integrated by a slow variable s; 'slaved': fast F relaxes to h(S) of a slow S and feeds (F - h(S)) back
    into S (passively F = h(S), so S alone predicts passive data)."""

    name = "fast_slow"

    def setup(self, rng, mode="burst"):
        self.mode = mode
        if mode == "burst":
            from scipy.optimize import brentq
            self.k = 3
            self.params.update({"tau": (0.008, 0.08, "log"), "eps": (0.1, 0.1, "log"), "gu": (0.9, 0.08, "log"),
                                "tau_s": (0.4, 0.15, "log"), "gs": (0.9, 0.1, "log")})
            self.v0 = brentq(lambda v: v - v ** 3 / 3 - (v + 0.7) / 0.8, -3, 3)
            self.w0 = (self.v0 + 0.7) / 0.8
            self.z_scale = (2.0, 1.0, 0.5)
            self.time_scale = 0.03
        elif mode == "relay":
            self.k = 2
            self.params.update({"tau_f": (0.01, 0.15, "log"), "tau_s": (0.8, 0.2, "log"), "g": (1.5, 0.15, "log")})
            self.z_scale = (1.0, 1.0)
            self.time_scale = 0.01
        else:
            self.k = 2
            self.params.update({"tau_S": (0.3, 0.15, "log"), "tau_F": (0.008, 0.1, "log"), "kap": (1.5, 0.15, "log"),
                                "hg": (2.0, 0.1, "log")})
            self.z_scale = (1.0, 1.0)
            self.time_scale = 0.008

    def make_f(self, P):
        mode = self.mode
        if mode == "burst":
            it, eps, gu, its, gs = 1 / P["tau"], P["eps"], P["gu"], 1 / P["tau_s"], P["gs"]
            v0, w0 = self.v0, self.w0

            def f(z, u):
                v = v0 + sat(z[0], 4.5)
                w = z[1] + w0
                s = z[2]
                I = gu * sat(u[0], 4.0) - gs * s
                return [(v - v * v * v / 3.0 - w + I) * it, eps * (v + 0.7 - 0.8 * w) * it, (-s + 0.5 * srelu0(v - v0, 0.05)) * its]
            return f
        if mode == "relay":
            itf, its, g = 1 / P["tau_f"], 1 / P["tau_s"], P["g"]

            def f(z, u):
                fz, s = z
                return [(-fz + g * math.tanh(sat(u[0], 4.0)) - 0.5 * s) * itf, (fz - 0.3 * s) * its]
            return f
        itS, itF, kap, hg = 1 / P["tau_S"], 1 / P["tau_F"], P["kap"], P["hg"]

        def f(z, u):
            S, F = z
            hS = math.tanh(hg * sat(S, 4.0))
            return [(-S + sat(u[0], 4.0) + kap * (F - hS)) * itS, (hS - F) * itF]
        return f

    def zobs(self, Z):
        return Z[:, :1] if self.mode == "slaved" else None

    def zres(self, Z, P=None):
        if self.mode != "slaved":
            return None
        hg = (P or self.nominal())["hg"]
        return Z[:, 1:2] - np.tanh(hg * 4.0 * np.tanh(Z[:, :1] / 4.0))


# ================================================================================================================ 10 hidden mode
class HiddenMode(Latent):
    """Hidden discrete mode m (steep bistable variable carried by hidden units) + continuous x = (x1, x2). Mode 0: x relaxes to
    the input-driven point; mode 1: x oscillates around it ('osc') or integrates with 2.5x gain ('gain'). m is driven on by
    s_up softrelu(x1 - th_up)(1 - m) and off by s_dn softrelu(th_dn - x1) m (smooth rectifiers)."""

    name = "hidden_mode"
    k = 3
    z_scale = (1.0, 1.0, 1.0)

    def setup(self, rng, mode1="osc", th_up=0.6, th_dn=0.15, trap=False):
        self.mode1, self.trap = mode1, trap
        self.params.update({"tau": (0.06, 0.15, "log"), "g0": (1.0, 0.12, "log"), "freq": (8.0, 0.1, "log"),
                            "lam_m": (40.0, 0.1, "log"), "s_up": (60.0, 0.15, "log"), "s_dn": (30.0, 0.15, "log"),
                            "th_up": (th_up, 0.05, "lin"), "th_dn": (th_dn, 0.03, "lin")})
        self.time_scale = 0.06

    def make_f(self, P):
        it, g0, w, lm, su, sd, tu, td = (1 / P["tau"], P["g0"], 2 * math.pi * P["freq"], P["lam_m"], P["s_up"], P["s_dn"],
                                         P["th_up"], P["th_dn"])
        osc = self.mode1 == "osc"

        def f(z, u):
            x1, x2 = sat(z[0], 4.0), sat(z[1], 4.0)
            m = sat(z[2], 2.0)
            uu = sat(u[0], 4.0)
            a1 = (-x1 + g0 * uu) * it
            a2 = -x2 * it
            if osc:      # mode 1: limit cycle of radius 0.5 around the input-driven point
                d1 = x1 - g0 * uu
                q = 3.0 * it * (0.25 - smooth_cap(d1 * d1 + x2 * x2, 16.0))
                b1 = q * d1 - w * x2
                b2 = q * x2 + w * d1
            else:
                b1 = (-x1 + 2.5 * g0 * uu) * it * 0.5
                b2 = (-x2 + x1) * it
            mm = min(max(m, 0.0), 1.0)
            dm = lm * (-m * (m - 0.5) * (m - 1.0)) + su * softrelu(x1 - tu, 0.02) * (1.0 - m) - sd * softrelu(td - x1, 0.02) * m
            return [(1 - mm) * a1 + mm * b1, (1 - mm) * a2 + mm * b2, dm]
        return f

    def zobs(self, Z):
        return Z[:, :2] if self.trap else None

    def zres(self, Z, P=None):
        return Z[:, 2:3] if self.trap else None


# ================================================================================================================ 12 / 11 shared dynamics
class HopfSlow(Latent):
    """Hopf oscillator whose bifurcation parameter follows a slow input integrator z3 (dz3 = (u - z3)/tau3, mu = mu1 (z3 - uc)):
    the rhythm builds up slowly after the input onset."""

    name = "hopf_slow"
    k = 3
    z_scale = (0.8, 0.8, 1.0)

    def setup(self, rng, freq=12.0, tau3=0.25, lam=20.0):
        self.params.update({"freq": (freq, 0.1, "log"), "lam": (lam, 0.15, "log"), "mu1": (1.0, 0.12, "log"),
                            "uc": (0.35, 0.05, "lin"), "tau3": (tau3, 0.15, "log"), "bu": (3.0, 0.1, "log")})
        self.time_scale = 1.0 / freq

    def make_f(self, P):
        w, lam, mu1, uc, it3, bu = 2 * math.pi * P["freq"], P["lam"], P["mu1"], P["uc"], 1 / P["tau3"], P["bu"]

        def f(z, u):
            x, y, s = z
            mu = mu1 * (sat(s, 3.0) - uc)
            r2 = smooth_cap(x * x + y * y, 16.0)
            a = lam * (mu - r2)
            return [a * x - w * y + bu * s, a * y + w * x, (-s + sat(u[0], 4.0)) * it3]
        return f


# ================================================================================================================ 13 population codes
class Ring(Latent):
    """Ring attractor(s). Ring j: p_j = r (cos th, sin th), dp = lam (1 - |p|^2) p + omega J p, omega = w_u u - kappa sin(th): the bump
    is pinned at th = 0 at rest and rotates (saddle-node on invariant circle) once w_u u > kappa. z = p - (1, 0) per ring."""

    name = "ring"

    def setup(self, rng, n_rings=1, freqs=(10.0,), pins=(6.0,)):
        self.nr = n_rings
        self.k = 2 * n_rings
        for j in range(n_rings):
            self.params[f"wu{j}"] = (float(freqs[j]), 0.08, "log")
            self.params[f"kp{j}"] = (float(pins[j]), 0.08, "log")
        self.params["lam"] = (15.0, 0.15, "log")
        self.z_scale = tuple([1.0] * self.k)
        self.time_scale = 0.05

    def make_f(self, P):
        nr = self.nr
        wu = [2 * math.pi * P[f"wu{j}"] for j in range(nr)]
        kp = [2 * math.pi * P[f"kp{j}"] for j in range(nr)]
        lam = P["lam"]

        def f(z, u):
            uu = sat(u[0], 4.0)
            out = []
            for j in range(nr):
                px, py = z[2 * j] + 1.0, z[2 * j + 1]
                r2 = px * px + py * py
                # smooth everywhere a strong kick can reach (a kink or the 1 / r singularity at the centre would reduce the RK4
                # order): pinning sin(th) regularised inside r ~ 0.1, radial term capped smoothly (C^2, identity up to r^2 = 4.5)
                om = wu[j] * uu - kp[j] * (py / math.sqrt(r2 + 0.01))
                a = lam * (1.0 - smooth_cap(r2, 9.0))
                out += [a * px - om * py, a * py + om * px]
            return out
        return f
