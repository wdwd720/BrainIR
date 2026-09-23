"""Threshold-linear-tanh firing-rate network of Pugliese et al. (independent re-implementation).

Model (per neuron i; see research/literature/pugliese_model_spec_from_code.md for the line-referenced derivation)::

    tau_i dr_i/dt = max( r_max_i * tanh( (a_i / r_max_i) * (I_i(t) + sum_j Wb[i, j] r_j(t) - theta_i) ), 0 ) - r_i(t)

with ``Wb = b * W`` (``W`` = signed synapse counts, post x pre), external current ``I_i(t)`` = a constant pulse on the
stimulated neurons between ``pulse_start`` and ``pulse_end``, and ``r(0) = 0``.

Per-neuron parameters are drawn from truncated normals (inverse-CDF method with the authors' bound conventions) and
size-scaled (``a /= s``, ``theta *= s`` with ``s = size / median(size)``). Everything is float64 by default (the authors
ran float32 on GPUs; bit-exact agreement with their runs is not achievable and not attempted, see the spec, section 10).

Design notes
------------
* The published code integrates one discontinuous ODE with Dopri5 (rtol 2e-6, atol 5e-9). Here the default is the
  same tolerances with scipy's RK45 (Dormand-Prince 5(4)), integrating *segment-wise* at the pulse edges so the
  discontinuity is never inside a step (``integration="segments"``); ``integration="single"`` reproduces the authors'
  single-interval scheme. Fixed-step RK4 (``method="rk4"``, ``dt``) exists for convergence studies.
* Interventions (silencing = zeroing a neuron's rows and columns; keep-only; weight noise; column shuffles) act on the
  signed count matrix before scaling, exactly as in the published code (``W * W_mask`` before ``reweight``).
* Model parameters are ``EvidenceKind.MODEL_PARAMETER``: assumed, never anatomy.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
import scipy.sparse as sp
from scipy.integrate import solve_ivp
from scipy.special import ndtr, ndtri

MODEL_ID = "brainir.sim.pugliese_rate_v1"


# ---------------------------------------------------------------------------
# configuration and parameters
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ModelConfig:
    """Everything that is assumed rather than observed. Defaults = the authors' ``neuron_params/default.yaml`` and
    ``sim/default.yaml``."""
    b_exc: float = 0.03
    b_inh: float = 0.03
    tau_mean: float = 0.020
    tau_sd: float = 0.002
    a_mean: float = 1.0
    a_sd: float = 0.1
    theta_mean: float = 7.5
    theta_sd: float = 0.6
    r_max_mean: float = 200.0
    r_max_sd: float = 10.0
    size_scaling: bool = True
    t_end: float = 2.0
    dt_out: float = 1e-3
    pulse_start: float = 0.02
    pulse_end: float | None = None
    """Default: t_end - dt_out (the authors' 1.999 for T = 2)."""
    method: Literal["RK45", "DOP853", "LSODA", "rk4", "euler"] = "RK45"
    rtol: float = 2e-6
    atol: float = 5e-9
    integration: Literal["segments", "single"] = "segments"
    dt: float | None = None
    """Fixed step for method='rk4'/'euler' (defaults to dt_out)."""
    max_step: float | None = None
    clip_max_rate: float = 1000.0
    """The authors clip rates to [0, 1000] after solving (only acts on numerical garbage)."""

    def resolved_pulse_end(self) -> float:
        return self.t_end - self.dt_out if self.pulse_end is None else self.pulse_end

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NeuronParams:
    """Per-neuron parameter vectors (already size-scaled). MODEL_PARAMETER evidence."""
    tau: np.ndarray
    a: np.ndarray
    theta: np.ndarray
    r_max: np.ndarray
    seed: int | None = None
    size_scale: np.ndarray | None = None

    @property
    def n(self) -> int:
        return int(self.tau.shape[0])

    def validate(self) -> None:
        n = self.n
        for name in ("tau", "a", "theta", "r_max"):
            v = getattr(self, name)
            if v.shape != (n,):
                raise ValueError(f"{name} has shape {v.shape}, expected ({n},)")
            if not np.all(np.isfinite(v)):
                raise ValueError(f"{name} contains non-finite values")
        if np.any(self.tau <= 0):
            raise ValueError("tau must be positive")
        if np.any(self.r_max <= 0):
            raise ValueError("r_max must be positive")


def sample_trunc_normal(rng: np.random.Generator, mean: float, sd: float, shape: tuple[int, ...],
                        lower: float = 0.0) -> np.ndarray:
    """Inverse-CDF truncated normal with the authors' bound conventions (sim_utils.sample_trunc_normal):
    upper = mean + min(100 sd, 1e6) (<= 1e10); standardised bounds clipped to [-10, 10]; CDF values clipped to
    [1e-10, 1 - 1e-10]; u ~ U[cdf(lower), cdf(upper)); sd < 1e-10 -> constant max(mean, 0)."""
    if sd < 0 or not all(math.isfinite(x) for x in (mean, sd, lower)):
        return np.zeros(shape)
    if sd < 1e-10:
        return np.full(shape, max(mean, 0.0))
    upper = min(mean + min(100.0 * sd, 1e6), 1e10)
    za = np.clip((lower - mean) / sd, -10.0, 10.0)
    zb = np.clip((upper - mean) / sd, -10.0, 10.0)
    ca = float(np.clip(ndtr(za), 1e-10, 1 - 1e-10))
    cb = float(np.clip(ndtr(zb), 1e-10, 1 - 1e-10))
    cb = max(cb, ca + 1e-10)
    u = rng.uniform(ca, cb, size=shape)
    z = ndtri(np.clip(u, 1e-10, 1 - 1e-10))
    return np.clip(mean + sd * z, -1e10, 1e10)


def size_scaling(sizes: np.ndarray | None, n: int) -> np.ndarray:
    """Relative size s = size / nanmedian(size); NaN/0 sizes -> median (s = 1). None -> all ones."""
    if sizes is None:
        return np.ones(n)
    s = np.asarray(sizes, dtype=np.float64).copy()
    med = np.nanmedian(s) if np.isfinite(s).any() else 1.0
    s[~np.isfinite(s)] = med
    s[s == 0] = med
    return s / med


def sample_neuron_params(cfg: ModelConfig, n: int, seed: int, sizes: np.ndarray | None = None) -> NeuronParams:
    """One replicate: independent draws per neuron for tau, a, theta, r_max (in that order, one stream), then size
    scaling of a and theta. Different seeds give independent replicates."""
    rng = np.random.default_rng(seed)
    tau = sample_trunc_normal(rng, cfg.tau_mean, cfg.tau_sd, (n,))
    a = sample_trunc_normal(rng, cfg.a_mean, cfg.a_sd, (n,))
    theta = sample_trunc_normal(rng, cfg.theta_mean, cfg.theta_sd, (n,))
    r_max = sample_trunc_normal(rng, cfg.r_max_mean, cfg.r_max_sd, (n,))
    s = size_scaling(sizes, n) if cfg.size_scaling else np.ones(n)
    p = NeuronParams(tau=tau, a=a / s, theta=theta * s, r_max=r_max, seed=int(seed), size_scale=s)
    p.validate()
    return p


def mean_neuron_params(cfg: ModelConfig, n: int, sizes: np.ndarray | None = None) -> NeuronParams:
    """Deterministic parameters at the distribution means (useful for tests and sensitivity analyses)."""
    s = size_scaling(sizes, n) if cfg.size_scaling else np.ones(n)
    p = NeuronParams(tau=np.full(n, cfg.tau_mean), a=np.full(n, cfg.a_mean) / s, theta=np.full(n, cfg.theta_mean) * s,
                     r_max=np.full(n, cfg.r_max_mean), seed=None, size_scale=s)
    p.validate()
    return p


# ---------------------------------------------------------------------------
# stimulus and interventions
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Stimulus:
    """Constant current pulse into ``indices`` (positional indices into the network) with amplitudes ``currents``."""
    indices: tuple[int, ...]
    currents: tuple[float, ...]
    pulse_start: float | None = None
    pulse_end: float | None = None

    def __post_init__(self):
        if len(self.currents) not in (1, len(self.indices)):
            raise ValueError("currents must have one entry or one per stimulated neuron")

    def vector(self, n: int) -> np.ndarray:
        v = np.zeros(n)
        cur = list(self.currents) * len(self.indices) if len(self.currents) == 1 else list(self.currents)
        for i, c in zip(self.indices, cur):
            if not 0 <= i < n:
                raise IndexError(f"stimulated index {i} outside network of size {n}")
            v[i] = c
        return v

    def scaled(self, factor: float) -> Stimulus:
        return Stimulus(self.indices, tuple(float(c) * factor for c in self.currents), self.pulse_start, self.pulse_end)


@dataclass(frozen=True)
class Intervention:
    """Structural perturbations of the count matrix (applied before scaling, as W * W_mask in the published code)."""
    silence: tuple[int, ...] = ()
    """Zero the rows AND columns of these neurons (the paper's 'silencing' / 'removal')."""
    keep_only: tuple[int, ...] | None = None
    """Keep synapses only among these neurons (plus ``always_keep``); everything else loses inputs and outputs."""
    always_keep: tuple[int, ...] = ()
    weight_noise_sd: float = 0.0
    """Multiplicative weight noise w (1 + eta), eta ~ truncated normal(0, sd) with eta >= -1 (sign preserved)."""
    weight_noise_seed: int | None = None
    scale_by_nt: dict[str, float] = field(default_factory=dict)
    """Optional per-presynaptic-class output multipliers (e.g. {'glutamate': 0.5}); applied by the caller who knows NTs."""

    def mask(self, n: int) -> np.ndarray | None:
        if not self.silence and self.keep_only is None:
            return None
        keep = np.ones(n, dtype=bool)
        if self.keep_only is not None:
            keep[:] = False
            keep[list(self.keep_only)] = True
            keep[list(self.always_keep)] = True
        keep[list(self.silence)] = False
        return keep


def apply_intervention(W: sp.csr_matrix, iv: Intervention | None) -> sp.csr_matrix:
    """Return the perturbed count matrix (post x pre). Never mutates the input."""
    if iv is None:
        return W
    M = W.tocsr(copy=True)
    keep = iv.mask(M.shape[0])
    if keep is not None:
        d = sp.diags(keep.astype(np.float64))
        M = (d @ M @ d).tocsr()
        M.eliminate_zeros()
    if iv.weight_noise_sd > 0:
        rng = np.random.default_rng(iv.weight_noise_seed)
        M = M.tocoo()
        eta = sample_trunc_normal(rng, 0.0, iv.weight_noise_sd, M.data.shape, lower=-1.0)
        M = sp.csr_matrix((M.data * (1.0 + eta), (M.row, M.col)), shape=M.shape)
    return M


def scaled_weights(W: sp.csr_matrix, cfg: ModelConfig) -> sp.csr_matrix:
    """Wb = b_exc * max(W, 0) + b_inh * min(W, 0)."""
    W = W.tocsr()
    pos = W.multiply(W > 0)
    neg = W.multiply(W < 0)
    return (cfg.b_exc * pos + cfg.b_inh * neg).tocsr()


# ---------------------------------------------------------------------------
# dynamics
# ---------------------------------------------------------------------------
@dataclass
class Trajectory:
    t: np.ndarray
    """Output grid (s), shape (T,)."""
    r: np.ndarray
    """Rates (Hz), shape (T, N)."""
    info: dict

    @property
    def n(self) -> int:
        return int(self.r.shape[1])

    def window(self, t0: float, t1: float | None = None) -> np.ndarray:
        m = self.t >= t0 - 1e-12 if t1 is None else (self.t >= t0 - 1e-12) & (self.t <= t1 + 1e-12)
        return self.r[m]

    def max_rates(self, t0: float = 0.0) -> np.ndarray:
        return self.window(t0).max(axis=0)


def activation(x: np.ndarray, a: np.ndarray, r_max: np.ndarray) -> np.ndarray:
    return np.maximum(r_max * np.tanh((a / r_max) * x), 0.0)


def make_rhs(Wb: sp.csr_matrix, p: NeuronParams, i_ext: np.ndarray):
    """dr/dt for a constant input vector (the pulse is handled by the integration schedule)."""
    inv_tau = 1.0 / p.tau

    def rhs(t, r):
        x = i_ext + Wb @ r - p.theta
        return (activation(x, p.a, p.r_max) - r) * inv_tau

    return rhs


def _pulse_rhs(Wb, p, I_vec, t_on, t_off):
    inv_tau = 1.0 / p.tau

    def rhs(t, r):
        cur = I_vec if (t >= t_on) and (t <= t_off) else 0.0
        x = cur + Wb @ r - p.theta
        return (activation(x, p.a, p.r_max) - r) * inv_tau

    return rhs


def _fixed_step(rhs, r0, ts, dt, method):
    """Explicit fixed-step integrator sampled onto ``ts`` (each output interval is subdivided into steps of ``dt``)."""
    out = np.empty((len(ts), len(r0)))
    r = r0.copy()
    out[0] = r
    for k in range(1, len(ts)):
        t = ts[k - 1]
        span = ts[k] - t
        n_sub = max(1, int(round(span / dt)))
        h = span / n_sub
        for _ in range(n_sub):
            if method == "euler":
                r = r + h * rhs(t, r)
            else:
                k1 = rhs(t, r); k2 = rhs(t + h / 2, r + h / 2 * k1)
                k3 = rhs(t + h / 2, r + h / 2 * k2); k4 = rhs(t + h, r + h * k3)
                r = r + (h / 6) * (k1 + 2 * k2 + 2 * k3 + k4)
            t += h
        out[k] = r
    return out


def simulate(W: sp.csr_matrix | np.ndarray, params: NeuronParams, cfg: ModelConfig, stimulus: Stimulus,
             intervention: Intervention | None = None, *, r0: np.ndarray | None = None) -> Trajectory:
    """Integrate the network. ``W`` is the signed synapse-count matrix, post x pre (W[i, j] = pre j -> post i)."""
    W = sp.csr_matrix(W, dtype=np.float64)
    n = W.shape[0]
    if W.shape != (n, n) or params.n != n:
        raise ValueError(f"W {W.shape} and params (n={params.n}) disagree")
    params.validate()
    Wb = scaled_weights(apply_intervention(W, intervention), cfg)
    I_vec = stimulus.vector(n)
    t_on = cfg.pulse_start if stimulus.pulse_start is None else stimulus.pulse_start
    t_off = cfg.resolved_pulse_end() if stimulus.pulse_end is None else stimulus.pulse_end
    ts = np.round(np.arange(0.0, cfg.t_end + cfg.dt_out / 2, cfg.dt_out), 12)
    ts = ts[ts <= cfg.t_end + 1e-12]
    r0 = np.zeros(n) if r0 is None else np.asarray(r0, dtype=np.float64)
    info = {"model_id": MODEL_ID, "config": cfg.to_dict(), "n": n, "stimulus": asdict(stimulus),
            "intervention": None if intervention is None else {k: v for k, v in asdict(intervention).items() if k != "scale_by_nt"},
            "params_seed": params.seed, "pulse": [t_on, t_off]}
    if cfg.method in ("rk4", "euler"):
        dt = cfg.dt or cfg.dt_out
        r = _fixed_step(_pulse_rhs(Wb, params, I_vec, t_on, t_off), r0, ts, dt, cfg.method)
        info.update(method=cfg.method, dt=dt, n_steps=int(round(cfg.t_end / dt)), success=True)
    elif cfg.integration == "single":
        sol = solve_ivp(_pulse_rhs(Wb, params, I_vec, t_on, t_off), (0.0, cfg.t_end), r0, method=cfg.method, t_eval=ts,
                        rtol=cfg.rtol, atol=cfg.atol, max_step=cfg.max_step or np.inf, first_step=cfg.dt_out)
        r = sol.y.T
        info.update(method=cfg.method, success=bool(sol.success), n_steps=int(sol.nfev), message=sol.message)
    else:
        # segment-wise: [0, t_on], [t_on, t_off], [t_off, t_end]; the RHS is smooth inside each segment
        edges = sorted({0.0, min(max(t_on, 0.0), cfg.t_end), min(max(t_off, 0.0), cfg.t_end), cfg.t_end})
        r_parts, ok, nfev, msgs = [], True, 0, []
        r_cur = r0
        for s0, s1 in zip(edges[:-1], edges[1:]):
            if s1 <= s0:
                continue
            on = (s0 >= t_on - 1e-12) and (s1 <= t_off + 1e-12)
            rhs = make_rhs(Wb, params, I_vec if on else np.zeros(n))
            m = (ts >= s0 - 1e-12) & (ts <= s1 + 1e-12)
            t_eval = ts[m]
            if len(t_eval) == 0 or t_eval[0] > s0 + 1e-12:
                t_eval = np.concatenate([[s0], t_eval])
            if t_eval[-1] < s1 - 1e-12:
                t_eval = np.concatenate([t_eval, [s1]])
            sol = solve_ivp(rhs, (s0, s1), r_cur, method=cfg.method, t_eval=t_eval, rtol=cfg.rtol, atol=cfg.atol,
                            max_step=cfg.max_step or np.inf)
            ok &= bool(sol.success); nfev += int(sol.nfev); msgs.append(sol.message)
            r_cur = sol.y[:, -1]
            r_parts.append((sol.t, sol.y.T))
        r = np.empty((len(ts), n))
        for tt, yy in r_parts:
            idx = np.searchsorted(ts, tt)
            hit = (idx < len(ts)) & np.isclose(ts[np.minimum(idx, len(ts) - 1)], tt, atol=1e-9)
            r[idx[hit]] = yy[hit]
        info.update(method=cfg.method, success=ok, n_steps=nfev, message=msgs[-1] if msgs else "")
    if not np.all(np.isfinite(r)):
        info["non_finite_samples"] = int((~np.isfinite(r)).sum())
        r = np.nan_to_num(r, nan=0.0, posinf=0.0, neginf=0.0)
    r = np.clip(r, 0.0, cfg.clip_max_rate)
    return Trajectory(t=ts, r=r, info=info)
