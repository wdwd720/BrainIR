"""cb (family E, intervention-aware causal bottleneck): shared core of the cb_* methods.

One executable state model class (`CBModel`) is shared by cb_interchange, cb_psr and cb_cegar:

    encoder     z = W xs,  xs = (x - mu) / s              linear, instantaneous (x_t only), W (k x N) with ORTHONORMAL rows
    transition  z' = z + A z + B u~ + b + sz * MLP([z / sz, u~]) + e(z, events)       on an internal grid of `stride` samples
    readout     y = mu_y + sd_y * (C z + D u~ + e + MLP_g([z / sz, u~]))

Microscopic events act through the STRUCTURE of the model (never through per-neuron lookup tables). With x^s = W^T z the decoded
standardised microstate and p = x^s + mu / s the decoded raw activity of every unit (units of s):

    kick delta on units          z <- z + W (delta / s)                                   exact for a linear encoder
    current I on units           z' = f(z, u) + g W (I / s)                               g: scalar gain (training currents)
    silence of a set S           z' = f(z - W_S q_S, u) + W_S ((1 - kappa) q_S + kappa b_S)
    edge removal (post i, pre j) z' = f(z, u) - w_i w_i^T [f(z, u) - f(z - w_j q_j, u) - (1 - kappa) w_j q_j]

(q = W^T z: the decoded CENTRED activity; the unit's fluctuation is removed from the recurrence. Removing the raw activity mu/s + q
was tried first: for rate-like units with a large mean and a small spread it moves f far outside its training domain.) Each kind's
effect is multiplied by a gain alpha in [0, 1] chosen on the training event windows (1 = the structural prediction, 0 = no effect),
and the current response of a unit is bounded by its observed value range.

Derivation: for units with leak kappa per step and a low-rank coupling inside the encoder subspace (J = W^T K W: the unit's output
weights into the latent recurrence are aligned with its encoder column, which simulated silencing probes on the public systems
support), the latent update is f(z) = (1 - kappa) z + kappa R(z) + input. Silencing unit j removes its output from the recurrence
(R evaluated at z - w_j p_j), removes its inputs (its own state relaxes to its baseline b_j at rate kappa) and keeps the leak of the
other units; edge removal removes the single entry J_ij, i.e. the unit-i component (w_i w_i^T) of the recurrent contribution of unit j,
kappa K w_j p_j = f(z) - f(z - w_j p_j) - (1 - kappa) w_j p_j. So group silencing, edge removal and held-out targets follow from
the transition f and the encoder W; only kappa, the baseline map b = theta_r rho + theta_z (-mu / s) (rho = standardised rest state)
and g are fitted from the training single-neuron events (the silenced units' OWN traces and the current windows).

Everything in this module is generic: no system-specific constants, value ranges / rest states / scales estimated from the
training data, time handled in seconds.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

import numpy as np

from ..api import StateModel


# ================================================================================================================ helpers
def _as_col(system: dict) -> dict[int, int]:
    return {int(n): i for i, n in enumerate(system["observed"])}


def rest_state(trajs) -> np.ndarray:
    rows = [tr.x[0] for tr in trajs if (tr.protocol.get("r0") or {}).get("kind", "zero") == "zero"]
    if not rows:
        rows = [tr.x[0] for tr in trajs]
    return np.median(np.stack(rows).astype(np.float64), axis=0)


def drop_blowups(trajs, factor: float = 100.0) -> list:
    """Training trajectories without finite BLOW-UPS (max |x| or max |y| above `factor` x the median over the system's
    trajectories, or non-finite values); if everything would be dropped, the input is returned unchanged."""
    if len(trajs) < 3:
        return list(trajs)
    mx = np.array([np.nanmax(np.abs(t.x)) if np.isfinite(t.x).all() else np.inf for t in trajs])
    my = np.array([np.nanmax(np.abs(t.y)) if np.isfinite(t.y).all() else np.inf for t in trajs])
    keep = (mx <= factor * max(np.median(mx[np.isfinite(mx)]) if np.isfinite(mx).any() else 1.0, 1e-12)) &            (my <= factor * max(np.median(my[np.isfinite(my)]) if np.isfinite(my).any() else 1.0, 1e-12))
    out = [t for t, k_ in zip(trajs, keep) if k_]
    return out if len(out) >= 2 else list(trajs)


def choose_stride(trajs) -> int:
    """Internal model step = `stride` samples. Generic rule: keep about 400 internal steps per trajectory (the synthetic 4 s / 10 ms
    trajectories get stride 1, the real 2 s / 1 ms trajectories stride 5)."""
    T = int(np.median([len(tr.t) for tr in trajs]))
    return max(1, int(math.floor((T - 1) / 400)))


@dataclass
class Prep:
    """Per-system normalisation (training statistics only)."""
    mu: np.ndarray
    s: np.ndarray
    mu_u: np.ndarray
    sd_u: np.ndarray
    mu_y: np.ndarray
    sd_y: np.ndarray
    rest_s: np.ndarray          # standardised rest state
    xs_lo: np.ndarray           # standardised observed value range (0.1 % / 99.9 % quantiles)
    xs_hi: np.ndarray
    s_cur: float                # scale of injected currents
    col: dict
    dt: float
    stride: int
    taus: tuple = ()            # causal exponential history filters of xs (time constants in internal steps); () = x_t only

    @property
    def n_units(self) -> int:
        return len(self.mu)

    @staticmethod
    def fit(trajs, system: dict, stride: int) -> "Prep":
        X = np.concatenate([t.x for t in trajs]).astype(np.float64)
        U = np.concatenate([t.u for t in trajs]).astype(np.float64)
        Y = np.concatenate([t.y for t in trajs]).astype(np.float64)
        X = np.where(np.isfinite(X), X, 0.0)
        mu = np.median(X, 0) if False else X.mean(0)
        sd = X.std(0)
        med = float(np.median(sd)) if sd.size else 1.0
        s = np.maximum(sd, max(0.1 * med, 1e-6))
        sd_u = U.std(0)
        sd_u = np.where(sd_u > 1e-9, sd_u, 1.0)
        vy = Y.var(0)
        sd_y = np.sqrt(np.maximum(vy, max(1e-12, 1e-3 * float(vy.max()) if vy.size else 1e-12)))
        cur = []
        for tr in trajs:
            for e in tr.events():
                if e["kind"] == "current":
                    cur += [abs(float(v)) for v in e["targets"].values()]
        s_cur = float(np.median(cur)) if cur else 1.0
        return Prep(mu=mu, s=s, mu_u=U.mean(0), sd_u=sd_u, mu_y=Y.mean(0), sd_y=sd_y, rest_s=(rest_state(trajs) - mu) / s,
                    xs_lo=(np.quantile(X, 0.001, axis=0) - mu) / s, xs_hi=(np.quantile(X, 0.999, axis=0) - mu) / s,
                    s_cur=max(s_cur, 1e-9), col=_as_col(system), dt=float(trajs[0].dt), stride=int(stride))


# ================================================================================================================ binned data
@dataclass
class Binned:
    """One trajectory on the internal grid (bin m = samples [m*stride, (m+1)*stride)); state / readout at bin starts, input =
    block mean. Events snapped to bins."""
    key: str
    split: str
    family: str
    xs: np.ndarray               # (M+1, N) standardised microstate
    u: np.ndarray                # (M+1, n_u) normalised input (block means)
    y: np.ndarray                # (M+1, n_y) normalised readout
    kicks: list = field(default_factory=list)     # (m, col, dxs)
    cur: list = field(default_factory=list)       # (m0, m1, col, I / s_cur)
    sil: list = field(default_factory=list)       # (m0, m1, col)
    edges: list = field(default_factory=list)     # (m0, m1, post_col, pre_col)
    ev_bins: np.ndarray | None = None             # (M,) bool: an event acts during this step

    @property
    def M(self) -> int:
        return len(self.xs) - 1


def hist_features(xs_grid: np.ndarray, taus) -> np.ndarray:
    """[xs, EMA_tau1(xs), EMA_tau2(xs), ...] along the internal grid (causal; initialised at the first sample)."""
    if not taus:
        return xs_grid
    feats = [xs_grid]
    for ts in taus:
        a = 1.0 / max(1.0, float(ts))
        e = np.empty_like(xs_grid)
        acc = xs_grid[0].copy()
        for m in range(len(xs_grid)):
            acc += a * (xs_grid[m] - acc)
            e[m] = acc
        feats.append(e)
    return np.hstack(feats)


def _bin_index(t: float, dt: float, stride: int) -> int:
    return int(round(t / dt)) // stride


def bin_traj(tr, prep: Prep) -> Binned:
    s = prep.stride
    T = len(tr.t)
    M = (T - 1) // s
    idx = np.arange(M + 1) * s
    x = np.asarray(tr.x, np.float64)
    x = np.where(np.isfinite(x), x, 0.0)
    xs = hist_features((x[idx] - prep.mu) / prep.s, prep.taus)
    u = (np.asarray(tr.u, np.float64) - prep.mu_u) / prep.sd_u
    if s > 1:
        ub = np.stack([u[m * s: (m + 1) * s].mean(0) for m in range(M)] + [u[M * s]])
    else:
        ub = u[: M + 1]
    y = (np.asarray(tr.y, np.float64)[idx] - prep.mu_y) / prep.sd_y
    b = Binned(key=tr.key, split=tr.split, family=tr.family, xs=xs, u=ub, y=y)
    ev = np.zeros(M, bool)
    dt = tr.dt
    for e in tr.events():
        k = e["kind"]
        if k == "kick":
            m = min(M - 1, _bin_index(e["t"], dt, s))
            for n, d in e["delta"].items():
                if int(n) in prep.col:
                    c = prep.col[int(n)]
                    b.kicks.append((m, c, float(d) / prep.s[c]))
            ev[m] = True
        else:
            m0 = min(M, _bin_index(e["t0"], dt, s))
            m1 = M if e.get("t1") is None else min(M, max(m0 + 1, _bin_index(e["t1"], dt, s)))
            ev[m0:m1] = True
            if k == "current":
                for n, v in e["targets"].items():
                    if int(n) in prep.col:
                        c = prep.col[int(n)]
                        b.cur.append((m0, m1, c, float(v) / prep.s[c]))
            elif k == "silence":
                for n in e["targets"]:
                    if int(n) in prep.col:
                        b.sil.append((m0, m1, prep.col[int(n)]))
            elif k == "edge_remove":
                for post, pre in e["edges"]:
                    if int(post) in prep.col and int(pre) in prep.col:
                        b.edges.append((m0, m1, prep.col[int(post)], prep.col[int(pre)]))
    b.ev_bins = ev
    return b


def rollout_events(events: list[dict], n_int: int, dt: float, stride: int, prep: Prep) -> dict:
    """Events of a rollout (times relative to its start, seconds) on the internal grid of n_int steps."""
    N = len(prep.mu)
    out = {"kick": {}, "cur": None, "sil": None, "edges": []}
    span = stride * dt
    for e in events:
        k = e["kind"]
        if k == "kick":
            m = int(math.floor((e["t"] + 0.5 * dt) / span))
            if 0 <= m < n_int:
                v = out["kick"].setdefault(m, np.zeros(N))
                for n, d in e["delta"].items():
                    if int(n) in prep.col:
                        c = prep.col[int(n)]
                        v[c] += float(d) / prep.s[c]
            continue
        t0 = float(e["t0"])
        t1 = float("inf") if e.get("t1") is None else float(e["t1"])
        # fraction of each internal step covered by [t0, t1)
        a = np.arange(n_int) * span
        cov = np.clip((np.minimum(a + span, t1) - np.maximum(a, t0)) / span, 0.0, 1.0)
        if not cov.any():
            continue
        if k == "current":
            if out["cur"] is None:
                out["cur"] = np.zeros((n_int, N))
            for n, v in e["targets"].items():
                if int(n) in prep.col:
                    c = prep.col[int(n)]
                    out["cur"][:, c] += cov * float(v) / prep.s[c]
        elif k == "silence":
            if out["sil"] is None:
                out["sil"] = np.zeros((n_int, N))
            for n in e["targets"]:
                if int(n) in prep.col:
                    c = prep.col[int(n)]
                    out["sil"][:, c] = np.maximum(out["sil"][:, c], (cov >= 0.5).astype(float))
        elif k == "edge_remove":
            act = cov >= 0.5
            for post, pre in e["edges"]:
                if int(post) in prep.col and int(pre) in prep.col:
                    out["edges"].append((act, prep.col[int(post)], prep.col[int(pre)]))
    return out


# ================================================================================================================ numpy networks
def mlp_np(layers: list, h: np.ndarray) -> np.ndarray:
    for i, (Wm, bv) in enumerate(layers):
        h = h @ Wm.T + bv
        if i < len(layers) - 1:
            h = np.tanh(h)
    return h


def n_mlp(layers: list) -> int:
    return int(sum(Wm.size + bv.size for Wm, bv in layers))


# ================================================================================================================ the model
class CBModel(StateModel):
    """Executable cb state model (see module docstring). One instance may hold several systems (shared transition)."""

    def __init__(self):
        self.k: dict[str, int] = {}
        self.sys: dict[str, dict] = {}      # sid -> {"prep": Prep, "W": (k, N), "B", "ro": readout params, "base_s": (N,)}
        self.trans: dict = {}               # A, B (per system if input dims differ), b, mlp, sz
        self.ev: dict = {"kappa": 0.0, "g_cur": 0.0}   # unit leak per internal step, current gain
        self.meta: dict = {}                # info payload

    # ------------------------------------------------------------------ encoder
    def encode(self, system_id, x_hist, u_hist, dt):
        S = self.sys[system_id]
        p: Prep = S["prep"]
        x = np.asarray(x_hist, np.float64)
        if p.taus and x.ndim == 2:
            # history encoder: the same grid as training (stride samples, ending at the last sample), causal filters
            st = max(1, int(round(p.stride * p.dt / dt)))
            g = x[::-1][::st][::-1]
            xs = hist_features((np.where(np.isfinite(g), g, 0.0) - p.mu) / p.s, p.taus)[-1]
            return S["W"] @ xs
        x = x[-1] if x.ndim == 2 else x
        xs = (np.where(np.isfinite(x), x, 0.0) - p.mu) / p.s
        if p.taus:
            xs = np.tile(xs, 1 + len(p.taus))
        return S["W"] @ xs

    def encode_batch(self, system_id, X):
        """Encodings of single microstates (history filters, if any, at their steady state for that microstate)."""
        S = self.sys[system_id]
        p = S["prep"]
        xs = (np.asarray(X, np.float64) - p.mu) / p.s
        if p.taus:
            xs = np.tile(xs, (1, 1 + len(p.taus)))
        return xs @ S["W"].T

    def unit_maps(self, system_id):
        """(W_u, Wd_u): encoder columns and decoder rows of the CURRENT unit activities (the first block of a history encoder)."""
        S = self.sys[system_id]
        n = S["prep"].n_units
        W = S["W"]
        Wd = W.T if S.get("Wd") is None else S["Wd"]
        return W[:, :n], Wd[:n]

    # ------------------------------------------------------------------ transition
    def _ustd(self, system_id, u):
        p = self.sys[system_id]["prep"]
        return (np.asarray(u, np.float64) - p.mu_u) / p.sd_u

    def f(self, system_id, z, us):
        """One internal step without events; z (..., k), us (..., n_u) normalised input."""
        S = self.sys[system_id]
        T = S.get("trans") or self.trans
        sz = T["sz"]
        h = np.concatenate([z / sz, us], axis=-1)
        dz = z @ T["A"].T + us @ S["B"].T + T["b"]
        if T.get("mlp"):
            dz = dz + sz * mlp_np(T["mlp"], h)
        if T.get("rff") is not None:
            dz = dz + rff_apply(T["rff"], np.concatenate([z, us], axis=-1)) @ T["Wf"]
        return z + dz

    def step(self, system_id, z, us, m: int, ev: dict) -> np.ndarray:
        """One internal step with the events acting during step m (structural operators of the module docstring), each event
        effect scaled by its validated gain alpha[kind] in [0, 1]."""
        S = self.sys[system_id]
        W, Wd = self.unit_maps(system_id)
        evp = self.evp(system_id)
        al = evp.get("alpha") or {}
        if m in ev["kick"]:
            z = z + al.get("kick", 1.0) * (W @ ev["kick"][m])
        sil = ev["sil"][m] if ev["sil"] is not None else None
        has_sil = sil is not None and sil.any()
        edges = [(i, j) for act, i, j in ev["edges"] if act[m]]
        f0 = self.f(system_id, z, us)
        zn = f0
        if has_sil or edges:
            kap = evp["kappa"]
            a_s = al.get("silence", 1.0)
            q = Wd @ z                             # decoded (centred, standardised) activity of every unit
            if has_sil:
                zs = self.f(system_id, z - W @ (sil * q), us) + W @ (sil * ((1 - kap) * q + kap * S["base_s"]))
                zn = zn + a_s * (zs - f0)
            for i, j in edges:
                dj = W[:, j] * q[j]
                zn = zn - a_s * W[:, i] * float(Wd[i] @ (f0 - self.f(system_id, z - dj, us) - (1 - kap) * dj))
        if ev["cur"] is not None and ev["cur"][m].any():
            zn = zn + al.get("current", 1.0) * (W @ self.current_dx(system_id, z, ev["cur"][m]))   # W = unit block
        if not np.all(np.isfinite(zn)):
            zn = f0 if np.all(np.isfinite(f0)) else z.copy()
        return self._clip(system_id, zn)

    def evp(self, system_id) -> dict:
        """Event parameters of a system (per-system entry, else the model-wide one)."""
        return self.sys[system_id].get("ev") or self.ev

    def current_dx(self, system_id, z, cur):
        """Change of the standardised units by injected currents in one step: g I / s, bounded so that the decoded unit stays
        inside its observed value range (saturating units respond less)."""
        S = self.sys[system_id]
        dx = self.evp(system_id)["g_cur"] * cur
        lo, hi = S.get("xs_lo"), S.get("xs_hi")
        if lo is not None:
            q = self.unit_maps(system_id)[1] @ z
            dx = np.clip(q + dx, lo, hi) - np.clip(q, lo, hi)
        return dx

    def rollout(self, system_id, z0, u_future, events, dt):
        S = self.sys[system_id]
        p: Prep = S["prep"]
        u_future = np.asarray(u_future, np.float64)
        H = len(u_future) - 1
        stride = max(1, int(round(p.stride * p.dt / dt)))
        n_int = int(math.ceil(H / stride)) if H > 0 else 0
        us = self._ustd(system_id, u_future)
        # block-mean inputs on the internal grid
        ub = np.stack([us[m * stride: min(H, (m + 1) * stride)].mean(0) if m * stride < H else us[-1] for m in range(n_int)]) \
            if n_int else np.zeros((0, us.shape[1]))
        ev = rollout_events(events or [], n_int, dt, stride, p)
        z = np.asarray(z0, np.float64).copy()
        Z = [z.copy()]
        for m in range(n_int):
            z = self.step(system_id, z, ub[m], m, ev)
            Z.append(z.copy())
        Z = np.stack(Z)
        if stride > 1 and n_int:
            tg = np.arange(H + 1) / stride
            Zf = np.stack([np.interp(tg, np.arange(n_int + 1), Z[:, i]) for i in range(Z.shape[1])], axis=1)
        else:
            Zf = Z[: H + 1]
        return {"z": Zf, "y": self.readout(system_id, Zf, u_future)}

    def _clip(self, system_id, z):
        S = self.sys[system_id]
        if S.get("zlo") is not None:
            return np.clip(z, S["zlo"], S["zhi"])
        lim = S.get("zlim")
        return np.clip(z, -lim, lim) if lim is not None else z

    # ------------------------------------------------------------------ readout
    def readout(self, system_id, z, u):
        S = self.sys[system_id]
        p: Prep = S["prep"]
        R = S["ro"]
        z = np.atleast_2d(np.asarray(z, np.float64))
        us = np.atleast_2d(self._ustd(system_id, u))
        if len(us) == 1 and len(z) > 1:
            us = np.repeat(us, len(z), 0)
        yn = z @ R["C"].T + us @ R["D"].T + R["e"]
        if R.get("mlp"):
            yn = yn + mlp_np(R["mlp"], np.concatenate([z / (S.get("trans") or self.trans)["sz"], us], axis=-1))
        if R.get("rff") is not None:
            yn = yn + rff_apply(R["rff"], np.concatenate([z, us], -1)) @ R["Wr"]
        return p.mu_y + p.sd_y * yn

    def readout_n(self, system_id, Z, us):
        """Normalised readout (training units) for latent rows Z and normalised inputs us."""
        S = self.sys[system_id]
        R = S["ro"]
        yn = Z @ R["C"].T + us @ R["D"].T + R["e"]
        if R.get("mlp"):
            yn = yn + mlp_np(R["mlp"], np.concatenate([Z / (S.get("trans") or self.trans)["sz"], us], -1))
        if R.get("rff") is not None:
            yn = yn + rff_apply(R["rff"], np.concatenate([Z, us], -1)) @ R["Wr"]
        return yn

    # ------------------------------------------------------------------ events / lifting
    def supports(self, system_id, event_kind):
        return system_id in self.sys and event_kind in ("kick", "current", "silence", "edge_remove")

    def lift(self, system_id, x, z, delta_z, n_candidates=3):
        """Distinct kick realisers of the latent shift delta_z at time 0: since z = W (x - mu) / s, any delta with
        W (delta / s) = delta_z works. Candidates: minimum-norm over all units; minimum-norm restricted to two disjoint halves of
        the units (interleaved by encoder weight), each exact whenever its half spans the latent space."""
        S = self.sys[system_id]
        W, p = self.unit_maps(system_id)[0], S["prep"]
        dz = np.asarray(delta_z, np.float64)
        ids = [n for n, _ in sorted(p.col.items(), key=lambda kv: kv[1])]
        out = []

        def realiser(cols):
            Wc = W[:, cols]
            sol, *_ = np.linalg.lstsq(Wc, dz, rcond=None)
            if np.linalg.norm(Wc @ sol - dz) > 1e-6 * max(1.0, np.linalg.norm(dz)):
                return None
            d = {str(ids[c]): float(sol[i] * p.s[c]) for i, c in enumerate(cols) if abs(sol[i]) > 1e-12}
            return [{"kind": "kick", "t": 0.0, "delta": d}] if d else None

        N = W.shape[1]
        order = np.argsort(-np.linalg.norm(W, axis=0))
        cands = [list(range(N)), sorted(order[0::2].tolist()), sorted(order[1::2].tolist())]
        for cols in cands:
            r = realiser(cols)
            if r is not None:
                out.append(r)
            if len(out) >= n_candidates:
                break
        return out

    # ------------------------------------------------------------------ info
    def info(self):
        return dict(self.meta)


# ================================================================================================================ random features
def rff_make(d_in: int, n: int, gamma: float, rng: np.random.Generator, mu: np.ndarray, sd: np.ndarray) -> dict:
    return {"W": rng.standard_normal((d_in, n)) * np.sqrt(2 * gamma / max(1, d_in)), "b": rng.uniform(0, 2 * np.pi, n), "mu": mu,
            "sd": sd, "n": n}


def rff_apply(R: dict, X: np.ndarray) -> np.ndarray:
    Xs = (X - R["mu"]) / R["sd"]
    return np.sqrt(2.0 / R["n"]) * np.cos(Xs @ R["W"] + R["b"])


def ridge_solve(F: np.ndarray, Y: np.ndarray, lam: float, pen: np.ndarray | None = None) -> np.ndarray:
    """argmin ||F B - Y||^2 + lam * n * ||diag(pen) B||^2."""
    d = F.shape[1]
    P = np.ones(d) if pen is None else pen
    return np.linalg.solve(F.T @ F + lam * len(F) * np.diag(P), F.T @ Y)


# ================================================================================================================ PSR / RRR encoder
def future_design(bins: list[Binned], H: int, n_h: int = 12, n_pc: int = 10, pcs: np.ndarray | None = None, stride_s: int = 2,
                  free_only: bool = True):
    """Rows (one per sample time m with m + H inside the trajectory): current microstate xs_m, future-feature vector Phi (readout at
    n_h log-spaced horizons up to H and the top microstate PCs at the same horizons, both normalised), future-input features U_f
    (input at the same horizons and the current input) and the trajectory index. free_only: skip windows with events."""
    hs = np.unique(np.round(np.geomspace(1, H, n_h)).astype(int))
    X, F, Uf, G = [], [], [], []
    for ti, b in enumerate(bins):
        for m in range(0, b.M - H + 1, stride_s):
            if free_only and b.ev_bins is not None and b.ev_bins[m: m + H].any():
                continue
            X.append(b.xs[m])
            fy = b.y[m + hs].ravel()
            fx = (b.xs[m + hs] @ pcs.T).ravel() if pcs is not None else np.zeros(0)
            F.append(np.concatenate([fy, fx]))
            # future inputs: at every horizon and midway (piecewise-constant inputs), plus the current input
            Uf.append(np.concatenate([b.u[m], b.u[m + hs].ravel(), b.u[np.minimum(m + hs // 2, b.M)].ravel()]))
            G.append(ti)
    ny = bins[0].y.shape[1]
    return (np.array(X), np.array(F), np.array(Uf), np.array(G), hs, ny)


def rrr_fit(X, F, Uf, lam: float, w_x: float, ny: int, n_h: int):
    """Reduced-rank (ridge) regression of future features on the microstate, with the future inputs partialled out
    (Frisch-Waugh: the conditional predictive map x -> E[future | x, u_future]). Returns the full-rank coefficient B (N x m), the
    right singular vectors V and singular values of the fitted future, and the residualisers."""
    wts = np.ones(F.shape[1])
    wts[ny * n_h:] = w_x
    Fw = F * wts
    Z1 = np.hstack([np.ones((len(Uf), 1)), Uf])
    cu = np.linalg.lstsq(Z1, np.hstack([X, Fw]), rcond=None)[0]
    R = np.hstack([X, Fw]) - Z1 @ cu
    Xr, Fr = R[:, : X.shape[1]], R[:, X.shape[1]:]
    B = ridge_solve(Xr, Fr, lam)
    Fh = Xr @ B
    _, sv, Vt = np.linalg.svd(Fh, full_matrices=False)
    return {"B": B, "V": Vt.T, "sv": sv, "cu": cu, "wts": wts, "tot": float((Fr ** 2).sum()), "nX": X.shape[1]}


def rrr_predict_err(fit: dict, X, F, Uf, kmax: int) -> np.ndarray:
    """Held-out error of the rank-k predictor for k = 0..kmax (fraction of the residualised future variance)."""
    Z1 = np.hstack([np.ones((len(Uf), 1)), Uf])
    R = np.hstack([X, F * fit["wts"]]) - Z1 @ fit["cu"]
    Xr, Fr = R[:, : fit["nX"]], R[:, fit["nX"]:]
    P = Xr @ fit["B"]
    tot = float((Fr ** 2).sum()) + 1e-12
    errs = []
    for k in range(kmax + 1):
        V = fit["V"][:, :k]
        errs.append(float(((Fr - P @ V @ V.T) ** 2).sum()) / tot)
    return np.array(errs)


def rrr_encoder(fit: dict, k: int) -> np.ndarray:
    """Orthonormal encoder rows spanning the rank-k predictive subspace: range of B V_k (N x k)."""
    M = fit["B"] @ fit["V"][:, :k]
    q, _ = np.linalg.qr(M)
    return q[:, :k].T.copy()


# ================================================================================================================ dimension rule
def plateau_k(ks: list[int], losses: list[float], rel_tol: float, abs_tol: float) -> tuple[int, list[int], bool]:
    """Smallest k whose validation loss is within the tolerance of the best loss of the sweep; the plausible range is every k
    within twice the tolerance; `resolved` is False when the best loss is at the largest k tried (no plateau)."""
    L = np.asarray(losses, float)
    best = float(np.nanmin(L))
    thr = best * (1 + rel_tol) + abs_tol
    k_sel = int(ks[int(np.flatnonzero(L <= thr)[0])])
    thr2 = best * (1 + 2 * rel_tol) + 2 * abs_tol
    lo = int(ks[int(np.flatnonzero(L <= thr2)[0])])
    resolved = int(ks[int(np.nanargmin(L))]) < ks[-1] or k_sel < ks[-1]
    return k_sel, [lo, k_sel], resolved


def now() -> float:
    return time.process_time()


# ================================================================================================================ event-parameter estimators
def fit_unit_leak(bins: list[Binned], prep: Prep, W: np.ndarray) -> dict:
    """kappa (leak of a unit per internal step) and its silenced baseline b = theta_r rho + theta_z (-mu / s) from the silenced
    units' OWN standardised traces during training silencing (x_j' - x_j = -kappa x_j + kappa b_j, least squares, shared by all
    units). Without silencing data: kappa from the decay of the null-space residual (I - W^T W) xs, baseline = rest."""
    rows, tgt = [], []
    zero_s = -prep.mu / prep.s
    for b in bins:
        for m0, m1, c in b.sil:
            for m in range(m0, min(m1, b.M)):
                rows.append([-b.xs[m, c], prep.rest_s[c], zero_s[c]])
                tgt.append(b.xs[m + 1, c] - b.xs[m, c])
    if len(rows) >= 10:
        A, t = np.array(rows), np.array(tgt)
        coef = np.linalg.lstsq(A, t, rcond=None)[0]
        kap = float(np.clip(coef[0], 1e-3, 1.0))
        th_r, th_z = float(coef[1] / kap), float(coef[2] / kap)
        # a baseline far outside the data range is not credible: fall back to the rest state
        if not (np.isfinite(th_r) and np.isfinite(th_z)) or abs(th_r) > 3 or abs(th_z) > 3:
            th_r, th_z = 1.0, 0.0
        return {"kappa": kap, "theta_r": th_r, "theta_z": th_z, "source": "silenced traces", "n": len(rows)}
    R0, R1 = [], []
    P = np.eye(W.shape[1]) - W.T @ W
    for b in bins:
        free = np.flatnonzero(~b.ev_bins)
        r = b.xs @ P
        R0.append(r[free])
        R1.append(r[free + 1])
    R0, R1 = np.concatenate(R0), np.concatenate(R1)
    a = float((R0 * R1).sum() / max((R0 * R0).sum(), 1e-12))
    return {"kappa": float(np.clip(1 - a, 1e-3, 1.0)), "theta_r": 1.0, "theta_z": 0.0, "source": "null-space decay", "n": len(R0)}


def base_state(prep: Prep, leak: dict) -> np.ndarray:
    return leak["theta_r"] * prep.rest_s + leak["theta_z"] * (-prep.mu / prep.s)


def install_ranges(model, sid):
    p = model.sys[sid]["prep"]
    model.sys[sid]["xs_lo"], model.sys[sid]["xs_hi"] = p.xs_lo, p.xs_hi


def select_event_gains(model, sid, bins, H, rollout_fn, grid=(0.0, 0.25, 0.5, 0.75, 1.0)):
    """alpha[kind] per event kind (kick / current / silence) minimising the post-event readout error over H steps from the
    pre-event state on the training event windows (the model's own no-event rollout is alpha = 0)."""
    kinds = {"kick": [], "current": [], "silence": []}
    for b in bins:
        for m, c, d in b.kicks:
            kinds["kick"].append((b, m))
        for m0, m1, c, v in b.cur:
            kinds["current"].append((b, m0))
        for m0, m1, c in b.sil:
            kinds["silence"].append((b, m0))
    evp = model.sys[sid].get("ev")
    if evp is None:
        evp = model.ev
    alpha = {"kick": 1.0, "current": 1.0, "silence": 1.0}
    report = {}
    for kind, items in kinds.items():
        items = [(b, m) for b, m in items if m + H <= b.M][:40]
        if len(items) < 2:
            continue
        errs = []
        for a in grid:
            evp["alpha"] = dict(alpha, **{kind: a})
            e = 0.0
            for b, m in items:
                z = model.sys[sid]["W"] @ b.xs[m]
                Z = rollout_fn(model, sid, z, b, m, H)
                yp = model.readout_n(sid, Z[1:], b.u[m + 1: m + H + 1])
                e += float(np.mean((yp - b.y[m + 1: m + H + 1]) ** 2))
            errs.append(e / len(items))
        alpha[kind] = float(grid[int(np.argmin(errs))])
        report[kind] = {"grid": list(grid), "err": errs}
    evp["alpha"] = alpha
    return alpha, report


def install_latent_box(model, sid, bins, margin: float = 0.25):
    """Rollouts are confined to the training latent range widened by `margin` x its span per coordinate (bounded extrapolation:
    a transition or an event operator driven outside the data cannot produce unbounded predictions)."""
    S = model.sys[sid]
    Z = np.concatenate([b.xs for b in bins]) @ S["W"].T
    lo, hi = Z.min(0), Z.max(0)
    span = np.maximum(hi - lo, 1e-9)
    S["zlo"], S["zhi"] = lo - margin * span, hi + margin * span
