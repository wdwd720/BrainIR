"""Latent (causal-state) dynamics F(z, u) and readouts G(z, u) of the system types.

Every latent is written in coordinates where the rest state is z = 0 and F(0, 0) = 0 for EVERY parameter draw, so the rest
microstate does not depend on the draw. `make_f(P)` returns a python-float function f(z, u) -> list (called ~10^4 times per
trajectory; it must be fast and must saturate gracefully for states far outside the operating range, which strong interventions
can reach). `readout(ZH, U, P)` is vectorised over time. Parameters are drawn by `draw(rng, spread)`: every parameter consumes
exactly one normal deviate in a fixed (sorted) order, so draws are reproducible and shared across implementations of a group.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np

tanh = math.tanh
exp = math.exp


EW_BLOCK = 256


def ew_matmul(A: np.ndarray, B: np.ndarray) -> np.ndarray:
    """A (..., m) @ B (m, n) as an explicit elementwise sum over m in fixed order: bit-identical results for any number of rows
    (BLAS kernels may change their summation order with the matrix shape, which would break bit-exact restarts)."""
    m = A.shape[-1]
    if m > 8:           # long inner dimension: fixed-shape (EW_BLOCK x m) @ (m x n) products over zero-padded row blocks: every row
        A2 = A.reshape(-1, m)                 # goes through the same BLAS kernel whatever its position, so its result is the same
        Bc = np.ascontiguousarray(B)          # bit for bit in any call (tested: scratch/blas_det.py)
        rows = A2.shape[0]
        out = np.empty((rows, Bc.shape[1]))
        buf = np.zeros((EW_BLOCK, m))
        for i in range(0, rows, EW_BLOCK):
            c = min(EW_BLOCK, rows - i)
            buf[:c] = A2[i:i + c]
            if c < EW_BLOCK:
                buf[c:] = 0.0
            out[i:i + c] = (buf @ Bc)[:c]
        return out.reshape(A.shape[:-1] + (Bc.shape[1],))
    out = np.zeros(A.shape[:-1] + (B.shape[1],))
    for r in range(m):
        col = B[r]
        if np.any(col != 0.0):
            out += A[..., r:r + 1] * col
    return out


def relu(x):
    return x if x > 0.0 else 0.0


def softrelu(x, w):
    """Smooth rectifier w log(1 + exp(x / w)) (~0 for x << -w); C-infinity, so RK4 keeps its order across the threshold."""
    y = x / w
    return x + w * math.log1p(math.exp(-y)) if y > 0 else w * math.log1p(math.exp(y))


_LOG2 = math.log(2.0)


def srelu0(x, w):
    """Shifted smooth rectifier, exactly 0 at x = 0 (keeps F(0, 0) = 0); -w log 2 for x << -w, x - w log 2 for x >> w."""
    return softrelu(x, w) - w * _LOG2


def softplus(x):
    return x + math.log1p(math.exp(-x)) if x > 0 else math.log1p(math.exp(x))


def smooth_cap(x, c):
    """min(x, c) made C^2 (a kink reduces the RK4 order when a strong intervention pushes the state across it): the identity up to
    c / 2, then c / 2 + (c / 2) tanh((x - c / 2) / (c / 2)) (-> c)."""
    h = 0.5 * c
    return x if x <= h else h + h * math.tanh((x - h) / h)


def smooth_floor(x, lo, w=0.05):
    """max(x, lo) made smooth: lo + w log(1 + exp((x - lo) / w)) (equal to x up to w exp(-(x - lo) / w) away from the floor)."""
    d = (x - lo) / w
    return lo + (x - lo + w * math.log1p(math.exp(-d)) if d > 0 else w * math.log1p(math.exp(d)))


def sat(x, c=4.0):
    """Smooth saturation keeping |x| < c (identity near 0)."""
    return c * math.tanh(x / c)


IN_GAIN_W = 0.1


def input_gain_factor(U: np.ndarray, p: float, th: float) -> np.ndarray:
    """g(u) = [sp(u - th) / sp(1 - th)]^p per sample (g(1) = 1), u = mean input channel softly saturated at 3,
    sp(x) = w log(1 + exp(x / w)) with w = 0.1: an expansive, near-threshold transfer of the stimulus drive."""
    ue = 3.0 * np.tanh(np.asarray(U, float).mean(axis=1) / 3.0)
    w = IN_GAIN_W
    num = w * np.logaddexp(0.0, (ue - th) / w)
    den = w * np.logaddexp(0.0, (3.0 * math.tanh(1.0 / 3.0) - th) / w)      # normalised at the (saturated) nominal input
    return (num / den) ** p


class Readout:
    """y_j = g(u) * gain_j * psi_j(R_j . feat(z) + c_j + d_j u_0 + ...) with psi in {lin, relu, relu2, softplus, sig}; channels
    with R_j = 0 and d_j = 0 are silent (constant). g(u) (optional, `in_gain` = (p, th)) is the input-dependent readout gain: the
    readout units receive the stimulus as a multiplicative gain input with an expansive near-threshold transfer, g(1) = 1."""

    KINDS = ("lin", "relu", "relu2", "softplus", "sig")

    def __init__(self, R, c, d, gain, kinds, width=None, in_gain=None):
        self.R = np.asarray(R, float)
        self.c = np.asarray(c, float)
        self.d = np.asarray(d, float).reshape(self.R.shape[0], -1)
        self.gain = np.asarray(gain, float)
        self.kinds = list(kinds)
        self.width = np.ones(self.R.shape[0]) if width is None else np.asarray(width, float)
        self.in_gain = None if in_gain is None else (float(in_gain[0]), float(in_gain[1]))

    @property
    def n_y(self) -> int:
        return int(self.R.shape[0])

    def __call__(self, feat: np.ndarray, U: np.ndarray, gain_factor: float = 1.0) -> np.ndarray:
        a = ew_matmul(feat, self.R.T) + self.c[None, :] + ew_matmul(U[:, :self.d.shape[1]], self.d.T)
        y = np.empty_like(a)
        for j, kd in enumerate(self.kinds):
            w = self.width[j]
            if kd == "lin":
                y[:, j] = a[:, j]
            elif kd == "relu":
                y[:, j] = np.maximum(a[:, j], 0.0)
            elif kd == "relu2":
                y[:, j] = np.maximum(a[:, j], 0.0) ** 2
            elif kd == "softplus":
                y[:, j] = w * np.logaddexp(0.0, a[:, j] / w)
            elif kd == "sig":
                y[:, j] = 1.0 / (1.0 + np.exp(-np.clip(a[:, j] / w, -60, 60)))
        y = y * (self.gain * gain_factor)[None, :]
        if self.in_gain is not None:
            y = y * input_gain_factor(U, *self.in_gain)[:, None]
        return y

    def spec(self) -> dict:
        return {"R": self.R.round(6).tolist(), "c": self.c.round(6).tolist(), "d": self.d.round(6).tolist(),
                "gain": self.gain.round(6).tolist(), "kinds": self.kinds, "width": self.width.round(6).tolist(),
                "in_gain": None if self.in_gain is None else [round(a, 9) for a in self.in_gain]}


def random_readout(rng, n_feat, n_y, *, kinds=("relu", "softplus", "lin"), n_silent=0, scale=10.0, bias=(-0.3, 0.3),
                   input_weight=0.0, sparse=False, n_u=1, feat_scale=None, width=0.3, input_gain=True) -> Readout:
    """A generic readout of n_feat features: n_y channels, some silent."""
    fs = np.ones(n_feat) if feat_scale is None else np.asarray(feat_scale, float)
    R = rng.standard_normal((n_y, n_feat)) / fs[None, :] / math.sqrt(n_feat)
    if sparse:
        mask = rng.random((n_y, n_feat)) < 0.5
        mask[np.arange(n_y), rng.integers(0, n_feat, n_y)] = True
        R = R * mask
    c = rng.uniform(*bias, n_y)
    d = np.zeros((n_y, n_u))
    if input_weight:
        d[:, 0] = input_weight * rng.uniform(-1, 1, n_y)
    ks = [kinds[int(i)] for i in rng.integers(0, len(kinds), n_y)]
    ks = [("relu2" if (kd == "relu" and rng.random() < 0.4) else kd) for kd in ks]     # some expansive channels
    silent = rng.choice(n_y, size=min(n_silent, n_y), replace=False) if n_silent else []
    for j in silent:
        R[j] = 0.0
        d[j] = 0.0
        c[j] = -1.0
        ks[j] = "relu"
    gain = scale * rng.uniform(0.6, 1.4, n_y)
    in_gain = None
    if input_gain:
        # exponent in [2, 3], derived from the readout's own weights (a separate stream: no other draw is shifted)
        h = int.from_bytes(hashlib.sha256(np.ascontiguousarray(R).tobytes()).digest()[:4], "little")
        in_gain = (2.0 + (h % 1001) / 1000.0, 0.25)
    return Readout(R, c, d, gain, ks, width=np.full(n_y, width), in_gain=in_gain)


class Latent:
    """Base class. Subclasses define `k`, `n_u`, `PARAMS` {name: (nominal, sd, 'log' | 'lin')}, `make_f`, `features`
    (readout features from zh), optionally `zobs` and `describe`."""

    name = "latent"
    k = 1
    n_u = 1
    PARAMS: dict = {}
    z_scale: tuple = (1.0,)
    k_obs = None
    vector = False           # True: make_f returns a numpy vector field (high-dimensional latents)
    fixed_scale_dims: tuple = ()   # dims whose declared z_scale is kept by the auto-scaling (trap dimensions)

    def __init__(self, rng=None, **kw):
        self.opts = dict(kw)
        self.params = dict(self.PARAMS)
        self.params.setdefault("ro_gain", (1.0, 0.15, "log"))
        self.ro: Readout | None = None
        self.setup(rng, **kw)

    def setup(self, rng, **kw):
        pass

    # ---------------------------------------------------------------- parameters
    def draw(self, rng, spread: float) -> dict:
        P = {}
        for name in sorted(self.params):
            nom, sd, kind = self.params[name]
            xi = float(rng.standard_normal())
            if kind == "log":
                P[name] = nom * math.exp(spread * sd * xi)
            else:
                P[name] = nom + spread * sd * xi
        return P

    def nominal(self) -> dict:
        return {k: v[0] for k, v in self.params.items()}

    # ---------------------------------------------------------------- dynamics / readout
    def make_f(self, P):  # pragma: no cover - abstract
        raise NotImplementedError

    confine_rate = 20.0          # 1/s

    def field(self, P):
        """The vector field used by the engine: make_f(P) plus a weak radial confinement -c min(r^6, 10) z, r^2 = mean_i (z_i / 4 z_scale_i)^2
        (< 0.5 %/s for |z_i| <= z_scale_i; 20 /s at 4 z_scale). It keeps strongly perturbed states bounded, leaves the rest point
        and every invariant subspace through the origin unchanged."""
        f = self.make_f(P)
        k = self.k
        zs = np.broadcast_to(np.asarray(self.z_scale, float), (k,))
        w = (1.0 / (4.0 * zs)) ** 2 / k
        lc = float(self.confine_rate)
        if self.vector:
            # high-dimensional latents: r^2 = (mean_i q_i^8)^(1/4), q_i = z_i / (4 z_scale_i): a smooth near-maximum norm, so an
            # excursion along one direction is confined at a few z_scale whatever k is (the mean of q^2 would dilute it by 1/k);
            # the rate grows as r^2 (not r^6): a gentle profile whose Jacobian stays well within the RK4 step's accuracy
            iq = 1.0 / (4.0 * zs)

            def g(z, u):
                zz = np.asarray(z, dtype=float)
                F = np.asarray(f(zz, u), dtype=float)
                q2 = (zz * iq) ** 2
                q4 = q2 * q2
                r2 = float(np.mean(q4 * q4)) ** 0.25
                return F - (lc * 10.0 * math.tanh(r2 / 10.0)) * zz
            return g
        r2 = " + ".join(f"{float(w[i])!r} * z[{i}] * z[{i}]" for i in range(k))
        src = (f"def g(z, u):\n    F = f(z, u)\n    r2 = {r2}\n    c = {lc!r} * 10.0 * tanh(r2 * r2 * r2 / 10.0)\n"
               f"    return [{', '.join(f'F[{i}] - c * z[{i}]' for i in range(k))}]\n")
        ns = {"f": f, "tanh": math.tanh}
        exec(src, ns)
        return ns["g"]

    def features(self, Z: np.ndarray, U: np.ndarray, P: dict) -> np.ndarray:
        return Z

    def readout(self, ZH: np.ndarray, U: np.ndarray, P: dict) -> np.ndarray:
        return self.ro(self.features(ZH, U, P), U, P.get("ro_gain", 1.0))

    def zobs(self, Z: np.ndarray):
        return None

    def zres(self, Z: np.ndarray, P: dict | None = None):
        """Trap types: the part of z that passive data do not determine from z_obs (zero or small on passive trajectories)."""
        return None

    def spec(self) -> dict:
        return {"name": self.name, "class": type(self).__name__, "k": self.k, "n_u": self.n_u,
                "z_scale": [float(a) for a in np.broadcast_to(np.asarray(self.z_scale, float), (self.k,))],
                "confine_rate": float(self.confine_rate), "params": {k: list(v) for k, v in sorted(self.params.items())},
                "opts": {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in sorted(self.opts.items())},
                "readout": self.ro.spec() if self.ro is not None else None, "extra": self.extra_spec()}

    def extra_spec(self) -> dict:
        return {}

    def describe(self) -> dict:
        return {"f": self.__doc__ or "", "g": "readout y = gain * psi(R feat(z) + c + d u)"}


# ================================================================================================================ simple test latents
class LeakyIntegrator(Latent):
    """dz_i/dt = -z_i / tau_i + beta_i * s(u) (k independent leaky integrators of the input, s = saturating input gain)."""

    name = "leaky_integrator"

    def setup(self, rng, k=1, taus=(0.25,), betas=(1.0,), u_sat=3.0):
        self.k = k
        self.z_scale = tuple(float(b * t) for b, t in zip(betas, taus))
        for i in range(k):
            self.params[f"tau{i}"] = (float(taus[i]), 0.2, "log")
            self.params[f"beta{i}"] = (float(betas[i]), 0.2, "log")
        self.u_sat = u_sat

    def make_f(self, P):
        k = self.k
        it = [1.0 / P[f"tau{i}"] for i in range(k)]
        be = [P[f"beta{i}"] for i in range(k)]
        us = self.u_sat

        def f(z, u):
            s = us * tanh(u[0] / us)
            return [-z[i] * it[i] + be[i] * s for i in range(k)]
        return f


class HopfOscillator(Latent):
    """Stuart-Landau oscillator with input-controlled bifurcation: dz = lam (mu(u) - |z|^2) z + omega J z, mu = mu1 (u - u_c)."""

    name = "hopf"
    k = 2
    z_scale = (1.0, 1.0)
    PARAMS = {"freq": (10.0, 0.1, "log"), "lam": (20.0, 0.2, "log"), "mu1": (1.0, 0.15, "log"), "uc": (0.4, 0.05, "lin")}

    def make_f(self, P):
        w = 2 * math.pi * P["freq"]
        lam, mu1, uc = P["lam"], P["mu1"], P["uc"]

        def f(z, u):
            x, y = z
            mu = mu1 * (u[0] - uc)
            r2 = x * x + y * y
            a = lam * (mu - r2)
            return [a * x - w * y, a * y + w * x]
        return f
