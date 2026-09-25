"""Core engine: a latent dynamic realised by a population of neurons and simulated in x-space.

Construction (identical for every system; see SYNTHETIC_BENCHMARK.md section 2):

* Coordinates c in R^K: c[:k] is the causal latent z, the rest are auxiliary coordinates (nuisance processes, persistent
  null codes, trap neurons' variables). They evolve by dc/dt = F(c, u, exo; theta) + Sigma dW.
* Each neuron i has an activation v_i and a recorded state x_i = phi_i(v_i) (phi = identity, scaled tanh or scaled logistic,
  a per-neuron bijection). Neurons communicate deviations from baseline: the population signal is c = D (v - b), where
  D (K x N) is a sparse-or-dense "synaptic readout" with D E = I.
* Neuron dynamics (the x-space ODE actually integrated):

      dv_i/dt = E_i . ( F(c, u, exo) + lam * c )  -  lam * (v_i - b_i)  +  I_i(t)  [+ noise]

  i.e. every neuron leaks to its baseline at rate lam and is driven by the population signal. Then
  d(D(v-b))/dt = D E F + lam D E c - lam D (v-b) = F(c): the population signal follows F EXACTLY, and the
  off-manifold part w = v - b - E c decays as exp(-lam t). Micro interventions act on individual neurons and so have
  real consequences for c (a kick on neuron j moves c by D[:, j] * dv_j; silencing removes neurons from the sum).
* weight_noise perturbs the synapses: D' = D * (1 + sd * xi) on existing synapses. The population signal c = D'(v - b)
  then obeys the closed ODE dc/dt = A F(c) - lam (I - A) c with A = D'E (recorded in truth). E.g. a perfect integrator
  becomes leaky or unstable, as a real mistuned network would.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import numpy as np

from .protocol import validate

SIM_VERSION = "p3synth-1.0"

PHI_ID, PHI_TANH, PHI_LOGI = 0, 1, 2
PHI_NAMES = {PHI_ID: "identity", PHI_TANH: "tanh", PHI_LOGI: "logistic"}


def seed_from(*parts) -> int:
    h = hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).digest()
    return int.from_bytes(h[:8], "little")


class Phi:
    """Per-neuron bijection v -> x: identity, x = s tanh(v/s) or x = s / (1 + exp(-v))."""

    def __init__(self, kind: np.ndarray, scale: np.ndarray):
        self.kind = np.asarray(kind, dtype=int)
        self.scale = np.asarray(scale, dtype=float)
        self.t = self.kind == PHI_TANH
        self.l = self.kind == PHI_LOGI
        self.trivial = not (self.t.any() or self.l.any())

    def fwd(self, v: np.ndarray) -> np.ndarray:
        if self.trivial:
            return v.copy()
        x = np.array(v, dtype=float, copy=True)
        s = self.scale
        x[..., self.t] = s[self.t] * np.tanh(v[..., self.t] / s[self.t])
        x[..., self.l] = s[self.l] / (1.0 + np.exp(-v[..., self.l]))
        return x

    def inv(self, x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
        """Inverse map (values outside the range are clipped to just inside it)."""
        if self.trivial:
            return np.array(x, dtype=float, copy=True)
        v = np.array(x, dtype=float, copy=True)
        s = self.scale
        r = np.clip(x[..., self.t] / s[self.t], -1 + eps, 1 - eps)
        v[..., self.t] = s[self.t] * np.arctanh(r)
        p = np.clip(x[..., self.l] / s[self.l], eps, 1 - eps)
        v[..., self.l] = np.log(p / (1 - p))
        return v

    def clip(self, x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
        return self.fwd(self.inv(x, eps))


@dataclass
class Implementation:
    """The population: embedding E, synaptic readout D, baselines b, leak lam, activation phi, noise levels."""

    E: np.ndarray                    # (N, K)
    D: np.ndarray                    # (K, N), D E = I
    b: np.ndarray                    # (N,)
    lam: float                       # leak / manifold-attraction rate (1/s)
    phi: Phi
    sigma_priv: np.ndarray           # (N,) private (per-neuron) noise, in v units / sqrt(s)
    obs_sigma: np.ndarray            # (N,) observation noise sd (added to recorded x only)
    observed: list[int]
    roles: list[str]                 # per neuron, truth only
    spec: dict = field(default_factory=dict)

    @property
    def n(self) -> int:
        return self.E.shape[0]

    def check(self) -> None:
        K = self.E.shape[1]
        err = np.abs(self.D @ self.E - np.eye(K)).max()
        if err > 1e-8:
            raise ValueError(f"D E != I (max err {err:.2e})")


class Model:
    """Coordinate dynamics: the causal latent (a `Latent`) plus auxiliary blocks."""

    def __init__(self, latent, blocks=()):
        self.latent = latent
        self.blocks = list(blocks)
        self.k = latent.k
        off = latent.k
        self.slices = [slice(0, latent.k)]
        for blk in self.blocks:
            blk.sl = slice(off, off + blk.dim)
            self.slices.append(blk.sl)
            off += blk.dim
        self.K = off
        self.n_u, self.n_y, self.n_exo = latent.n_u, latent.n_y, latent.n_exo

    def F(self, c, u, exo, th):
        if not self.blocks:
            return self.latent.f(c, u, exo, th)
        parts = [self.latent.f(c[: self.k], u, exo, th)]
        for blk in self.blocks:
            parts.append(blk.f(c[blk.sl], c, u, th, self))
        return np.concatenate(parts)

    def y(self, c, th):
        return self.latent.g(c[: self.k], th)

    def rest(self, th):
        z = np.asarray(self.latent.rest(th), dtype=float)
        parts = [z]
        for blk in self.blocks:
            parts.append(np.asarray(blk.rest(z, th, self), dtype=float))
        return np.concatenate(parts)

    def sigma(self, th):
        parts = [np.broadcast_to(np.asarray(self.latent.sigma(th), float), (self.k,))]
        for blk in self.blocks:
            parts.append(np.broadcast_to(np.asarray(blk.sigma(th), float), (blk.dim,)))
        return np.concatenate(parts)

    def coordinate_names(self):
        names = [f"z{i}" for i in range(self.k)]
        for blk in self.blocks:
            names += [f"{blk.name}{i}" for i in range(blk.dim)]
        return names

    def coordinate_roles(self):
        roles = ["latent"] * self.k
        for blk in self.blocks:
            roles += [blk.role] * blk.dim
        return roles


def _stimulus_steps(stim, n_steps, dt, n_u, pattern):
    u = np.zeros((n_steps + 1, n_u))
    for j, (t, val) in enumerate(stim):
        i0 = int(round(t / dt))
        i1 = int(round(stim[j + 1][0] / dt)) if j + 1 < len(stim) else n_steps + 1
        vec = np.asarray(val, float) if isinstance(val, list) else float(val) * pattern
        u[i0:i1] = vec
    return u


class SyntheticSystem:
    """One synthetic system: a Model (latent + auxiliary blocks) realised by an Implementation."""

    def __init__(self, system_id: str, model: Model, impl: Implementation, *, seed: int, meta: dict | None = None,
                 h_max: float | None = None, readout_noise: float = 0.0):
        self.system_id = system_id
        self.model = model
        self.impl = impl
        self.seed = int(seed)
        self.meta = dict(meta or {})
        self.readout_noise = float(readout_noise)
        impl.check()
        self.n = impl.n
        self.observed = list(impl.observed)
        self.readout_dim = model.n_y
        self.input_dim = model.n_u
        lat_h = getattr(model.latent, "h_max", 0.005)
        blk_h = min([getattr(b, "h_max", 1.0) for b in model.blocks] + [1.0])
        self.h_max = float(h_max or min(0.005, lat_h, blk_h, 0.3 / impl.lam))
        self._D_cache: dict = {}
        # structural couplings: pre j -> post i whenever j feeds the population signal and i is driven by it
        self._pre = np.flatnonzero(np.abs(impl.D).sum(0) > 0)
        self._post = np.flatnonzero(np.abs(impl.E).sum(1) > 0)

    # ------------------------------------------------------------------ helpers
    @property
    def k(self) -> int:
        return self.model.k

    def system_hash(self) -> str:
        blob = np.concatenate([self.impl.E.ravel(), self.impl.D.ravel(), self.impl.b]).round(12).tobytes()
        return hashlib.sha256(blob + str(self.seed).encode()).hexdigest()[:16]

    def has_edge(self, post: int, pre: int) -> bool:
        return bool(np.any(self.impl.D[:, pre] != 0) and np.any(self.impl.E[post] != 0))

    def synaptic_readout(self, weight_noise) -> np.ndarray:
        """D' under a weight_noise spec (the nominal D when None or sd == 0)."""
        if not weight_noise or float(weight_noise.get("sd", 0.0)) == 0.0:
            return self.impl.D
        key = (float(weight_noise["sd"]), int(weight_noise["seed"]))
        if key not in self._D_cache:
            rng = np.random.default_rng(seed_from("weight_noise", self.seed, key[1]))
            xi = rng.standard_normal(self.impl.D.shape)
            D = self.impl.D * (1.0 + key[0] * xi)
            self._D_cache[key] = D
        return self._D_cache[key]

    def effective_A(self, weight_noise) -> np.ndarray:
        return self.synaptic_readout(weight_noise) @ self.impl.E

    def rest_state(self, params_seed: int) -> np.ndarray:
        """Default rest microstate x (all N neurons) for r0 = {"kind": "zero"}."""
        th = self.model.latent.draw(params_seed)
        v = self.impl.b + self.impl.E @ self.model.rest(th)
        return self.impl.phi.fwd(v)

    def lift_latent(self, delta_z, x, *, weight_noise=None, active=None) -> np.ndarray:
        """Exact microscopic change (in x units, all N neurons) that moves the latent by delta_z and leaves every other
        coordinate unchanged: dv = E_act (D'_act E_act)^-1 [delta_z, 0], dx = phi(v + dv) - x (only active neurons)."""
        dz = np.zeros(self.model.K)
        dz[: self.k] = np.asarray(delta_z, float)
        dv = self._lift_v(dz, weight_noise, active)
        v = self.impl.phi.inv(np.asarray(x, float))
        return self.impl.phi.fwd(v + dv) - np.asarray(x, float)

    def _lift_v(self, dc, weight_noise, active):
        D = self.synaptic_readout(weight_noise)
        E = self.impl.E
        if active is None or active.all():
            M = D @ E
            return E @ np.linalg.solve(M, dc)
        act = np.asarray(active, bool)
        M = D[:, act] @ E[act]
        dv = np.zeros(self.n)
        dv[act] = E[act] @ np.linalg.lstsq(M, dc, rcond=None)[0]
        return dv

    # ------------------------------------------------------------------ simulation
    def simulate(self, protocol: dict, *, noise: bool = True, full: bool = False) -> dict:
        """Integrate one trajectory. Returns t, x (observed neurons), u, y, z (true latent) and info.

        info["public"] is safe to publish; info["truth"] is truth-only (effective parameters, all coordinates...).
        noise=False switches off process, private, observation and readout noise and the hidden exogenous input
        (verification only; never used for published data). full=True additionally returns the full microstate.
        """
        m, im = self.model, self.impl
        p = validate(protocol, n=self.n, input_dim=m.n_u, k=m.k)
        dt, t_end = p["dt"], p["t_end"]
        n_steps = int(round(t_end / dt))
        T = n_steps + 1
        th = m.latent.draw(p["params_seed"])
        D = self.synaptic_readout(p["weight_noise"])
        E, b, lam, N, K = im.E, im.b, float(im.lam), self.n, m.K
        nsub = max(1, int(np.ceil(dt / self.h_max - 1e-9)))
        h = dt / nsub
        # every random realisation below is drawn from ONE generator, in a fixed order and with shapes that do not depend
        # on the events: protocols sharing a noise_seed (and differing only in events) share the noise exactly
        if "noise_seed" in p:
            rng = np.random.default_rng(seed_from("noise", self.seed, p["noise_seed"]))
        else:
            rng = np.random.default_rng(seed_from("traj", self.seed, SIM_VERSION, json.dumps(p, sort_keys=True)))
        # exogenous (hidden) inputs, piecewise constant on the output grid (exact OU discretisation)
        exo_steps = m.latent.exo_signal(rng, T, dt, th) if m.n_exo else None
        if exo_steps is not None and not noise:
            exo_steps = np.zeros_like(exo_steps)
        # inputs
        pattern = np.asarray(m.latent.input_pattern, float)
        u_steps = _stimulus_steps(p["stimulus"], n_steps, dt, m.n_u, pattern)
        # noise
        sig_c = m.sigma(th) if noise else np.zeros(K)
        sig_p = im.sigma_priv if noise else np.zeros(N)
        n_tot = n_steps * nsub
        syn_noise = None
        if np.any(sig_c > 0):
            syn_noise = (rng.standard_normal((n_tot, K)) * (sig_c * np.sqrt(h))) @ E.T
        priv_noise = None
        if np.any(sig_p > 0):
            priv_noise = rng.standard_normal((n_tot, N)) * (sig_p * np.sqrt(h))
        obs_noise = rng.standard_normal((T, len(self.observed))) * im.obs_sigma[self.observed] if noise else None
        ro_noise = rng.standard_normal((T, m.n_y)) * self.readout_noise if (noise and self.readout_noise > 0) else None

        # event schedule
        inst = {}          # step -> list of instantaneous events
        cur = np.zeros((n_steps + 1, N)) if any(e["kind"] == "current" for e in p["events"]) else None
        sil = np.zeros((n_steps + 1, N), bool) if any(e["kind"] == "silence" for e in p["events"]) else None
        edge_ev = []
        for e in p["events"]:
            kind = e["kind"]
            if kind in ("kick", "latent_set", "latent_impulse"):
                inst.setdefault(int(round(e["t"] / dt)), []).append(e)
                continue
            i0 = int(round(e["t0"] / dt))
            i1 = n_steps + 1 if e.get("t1") is None else int(round(e["t1"] / dt))
            if kind == "current":
                for j, val in e["targets"].items():
                    cur[i0:i1, int(j)] += val
            elif kind == "silence":
                sil[i0:i1, e["targets"]] = True
            else:
                edge_ev.append((i0, i1, [(int(a), int(c)) for a, c in e["edges"]]))

        # initial state
        c_rest = m.rest(th)
        v = b + E @ c_rest
        if p["r0"]["kind"] == "state" and p["r0"]["values"]:
            x0 = im.phi.fwd(v)
            for j, val in p["r0"]["values"].items():
                x0[int(j)] = val
            v = im.phi.inv(im.phi.clip(x0))

        F = m.F
        # hot loop -------------------------------------------------------------
        xs = np.empty((T, N))
        cs = np.empty((T, K))
        vs = np.empty((T, N)) if full else None
        us = u_steps.copy()
        act_prev = None
        ev_log = []
        for i in range(T):
            dvb = v - b if act_prev is None else np.where(act_prev, v - b, 0.0)
            cs[i] = D @ dvb
            xs[i] = v
            if full:
                vs[i] = v
            if i == n_steps:
                break
            for e in inst.get(i, ()):
                if e["kind"] == "kick":
                    x_now = im.phi.fwd(v)
                    for j, d in e["delta"].items():
                        x_now[int(j)] += d
                    v = im.phi.inv(im.phi.clip(x_now))
                else:
                    act = None if (sil is None or not sil[i].any()) else ~sil[i]
                    c_now = D @ (v - b if act is None else np.where(act, v - b, 0.0))
                    dc = np.zeros(K)
                    for j, val in (e.get("values") or e.get("delta")).items():
                        dc[int(j)] = (val - c_now[int(j)]) if e["kind"] == "latent_set" else val
                    dv = self._lift_v(dc, p["weight_noise"], act)
                    ev_log.append({"t": round(i * dt, 9), "kind": e["kind"], "dv_norm": float(np.linalg.norm(dv))})
                    v = v + dv
            u = u_steps[i]
            ex = exo_steps[i] if exo_steps is not None else None
            I = cur[i] if cur is not None else None
            act = None if (sil is None or not sil[i].any()) else ~sil[i]
            edges = {}
            for (i0, i1, eds) in edge_ev:
                if i0 <= i < i1:
                    for post, pre in eds:
                        edges.setdefault(post, []).append(pre)
            if act is not None:
                edges = {q: pres for q, pres in edges.items() if act[q]}
            edge_items = [(q, np.asarray(pres)) for q, pres in edges.items()]

            def deriv(vv):
                dvb_ = vv - b
                if act is not None:
                    dvb_ = np.where(act, dvb_, 0.0)
                c = D @ dvb_
                dv_ = E @ (F(c, u, ex, th) + lam * c) - lam * (vv - b)
                if I is not None:
                    dv_ += I
                if act is not None:
                    dv_ = np.where(act, dv_, -lam * (vv - b))
                for q, pres in edge_items:
                    cq = c - D[:, pres] @ dvb_[pres]
                    dv_[q] = E[q] @ (F(cq, u, ex, th) + lam * cq) - lam * (vv[q] - b[q]) + (I[q] if I is not None else 0.0)
                return dv_

            base = i * nsub
            for s in range(nsub):
                k1 = deriv(v)
                k2 = deriv(v + 0.5 * h * k1)
                k3 = deriv(v + 0.5 * h * k2)
                k4 = deriv(v + h * k3)
                v = v + (h / 6.0) * (k1 + 2 * k2 + 2 * k3 + k4)
                if syn_noise is not None:
                    nz = syn_noise[base + s]
                    v = v + (nz if act is None else np.where(act, nz, 0.0))
                if priv_noise is not None:
                    v = v + priv_noise[base + s]
            act_prev = act
        # ---------------------------------------------------------------------
        x_full = im.phi.fwd(xs)
        x_obs = x_full[:, self.observed]
        if obs_noise is not None:
            x_obs = x_obs + obs_noise
        z = cs[:, : m.k]
        y = np.stack([m.y(c, th) for c in cs]) if T else np.zeros((0, m.n_y))
        y = np.asarray(y, float).reshape(T, m.n_y)
        if ro_noise is not None:
            y = y + ro_noise
        t = np.round(np.arange(T) * dt, 9)
        truth = {"coords": cs, "theta": {k_: np.asarray(v_).tolist() for k_, v_ in th.items() if not k_.startswith("_")},
                 "latent_events": ev_log, "h": h, "n_substeps": nsub}
        if p["weight_noise"] and p["weight_noise"]["sd"] > 0:
            truth["A"] = (D @ E).tolist()
        if exo_steps is not None:
            truth["exo"] = exo_steps
        out = {"t": t, "x": x_obs, "u": us, "y": y, "z": z,
               "info": {"public": {"simulator": SIM_VERSION, "n_samples": T}, "truth": truth}}
        if full:
            out["x_full"] = x_full
            out["v_full"] = vs
        return out

    def truth(self) -> dict:
        from .truth import system_truth
        return system_truth(self)
