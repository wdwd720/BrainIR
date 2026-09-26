"""Shared machinery of the linear family (prefix lin_): data preparation, the linear latent state model, least-squares and
prediction-error fits, readouts, event (intervention) operators, cross-validated dimension selection, sharing / adaptation.

Every lin_ method produces a `LinStateModel`:

    encoder    z_t = sum_l H_l xs_{t - lag_l} + sum_l Hu_l us_{t - lag_l} + b          (static when the only lag is 0)
    dynamics   z_{t+1} = A z_t + B us_t + c  [+ N(z_t, us_t)]                      (N: optional nonlinear closure)
    decoder    xs_t ~ C z_t + d                                                      (observation model; used by events)
    readout    y_t = G phi(z_t, us_t) + h                                             (phi linear or with quadratic terms)

xs = standardised observed microstate, us = standardised input (training statistics only). Events act through the model:
- kick   (dx on neuron j)       z <- z + K[:, j] dxs_j            (K = instantaneous encoder gain; rates clipped at 0 if x >= 0)
- current (I on neuron j)       z <- z + K[:, j] (gamma I / sx_j) per step   (gamma: one scalar gain per system, from training)
- silence (set S)               x_S relaxes to its decoupled level: z <- z + K[:, S] (r_S - xhat_S) after every step, and the
                                coupling of S onto the rest is removed through the read-in map R (z_{t+1} gets -R[:, S] dxs_S)
- edge_remove (post <- pre)     the coupling J[post, pre] (from the low-rank read-in / decoder structure) is removed:
                                z_{t+1} gets -K[:, post] J[post, pre] xhat_pre
None of these uses per-neuron lookup tables: all neuron-specific quantities come from the encoder / decoder / read-in maps, which
are defined for every observed neuron.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from ..api import StateModel

EVENT_KINDS = ("kick", "current", "silence", "edge_remove")


# ================================================================================================================ utilities
def thread_limit(n: int = 3):
    """Context manager limiting BLAS / torch threads (the CPU is shared)."""
    from threadpoolctl import threadpool_limits
    try:
        import torch
        torch.set_num_threads(n)
    except Exception:  # pragma: no cover
        pass
    return threadpool_limits(n)


def ridge_solve(F: np.ndarray, T: np.ndarray, lam: float, penalize_last: bool = False) -> np.ndarray:
    """argmin ||F W - T||^2 + lam * n * ||W||^2 (the last column of F, an intercept, is not penalised unless asked)."""
    n, p = F.shape
    G = F.T @ F
    reg = lam * max(n, 1) * np.ones(p)
    if not penalize_last:
        reg[-1] = 0.0
    G[np.diag_indices(p)] += reg + 1e-12 * (np.trace(G) / max(p, 1) + 1e-12)
    return np.linalg.solve(G, F.T @ T)


def events_at(events: list[dict], t: float, dt: float):
    """Events acting on the step [t, t + dt): (kicks {neuron: d}, silenced set, currents {neuron: I}, removed edges [(post, pre)])."""
    kicks, sil, cur, edges = {}, set(), {}, []
    for e in events:
        k = e["kind"]
        if k == "kick":
            if abs(e["t"] - t) < dt / 2:
                for n, v in e["delta"].items():
                    kicks[int(n)] = kicks.get(int(n), 0.0) + float(v)
        elif k == "current":
            if e["t0"] <= t + 1e-9 and t < e["t1"] - 1e-9:
                for n, v in e["targets"].items():
                    cur[int(n)] = cur.get(int(n), 0.0) + float(v)
        elif k == "silence":
            if e["t0"] <= t + 1e-9 and (e.get("t1") is None or t < e["t1"] - 1e-9):
                sil |= {int(n) for n in e["targets"]}
        elif k == "edge_remove":
            if e["t0"] <= t + 1e-9 and (e.get("t1") is None or t < e["t1"] - 1e-9):
                edges += [(int(a), int(b)) for a, b in e["edges"]]
    return kicks, sil, cur, edges


# ================================================================================================================ data preparation
@dataclass
class PTraj:
    """One prepared trajectory: standardised x / u, raw y, the free-transition mask and the event list."""
    key: str
    split: str
    family: str
    xs: np.ndarray            # (T, N) float32 standardised
    us: np.ndarray            # (T, n_u) float32 standardised
    y: np.ndarray             # (T, n_y) float64
    keep: np.ndarray          # (T - 1,) bool: transition t -> t+1 is free dynamics (no kick jump, no silencing, no current, no edits)
    events: list
    has_current: bool = False
    dt: float = 0.01
    twin_y: np.ndarray | None = None   # readout of the event-free counterfactual twin (simulation service), when available


@dataclass
class SysPrep:
    sid: str
    obs: list
    col: dict
    dt: float
    mx: np.ndarray
    sx: np.ndarray
    mu: np.ndarray
    su: np.ndarray
    my: np.ndarray
    sy: np.ndarray
    nonneg: bool
    rest: np.ndarray          # raw rest level per observed neuron (median first sample of rest-start trajectories)
    trajs: list = field(default_factory=list)
    T_len: int = 0

    @property
    def n_x(self) -> int:
        return len(self.obs)

    @property
    def n_u(self) -> int:
        return len(self.mu)

    @property
    def n_y(self) -> int:
        return len(self.my)


def _free_mask(tr, n: int) -> tuple[np.ndarray, bool]:
    keep = np.ones(n - 1, bool)
    has_cur = False
    for e in tr.events():
        k = e["kind"]
        if k == "kick":
            i = int(round(e["t"] / tr.dt))
            if 0 <= i < n - 1:
                keep[i] = False
        else:
            a = int(round(e["t0"] / tr.dt))
            b = n - 1 if e.get("t1") is None else int(round(e["t1"] / tr.dt))
            keep[max(0, a): max(0, b)] = False
            has_cur = has_cur or k == "current"
    return keep, has_cur


def prepare_system(sid: str, trajs: list, sysinfo: dict) -> SysPrep:
    """Standardisation statistics from the given (training) trajectories; drops trajectories with non-finite values."""
    obs = sysinfo.get("observed")
    if isinstance(obs, int):
        obs = list(range(obs))
    obs = [int(n) for n in obs]
    good = [tr for tr in trajs if np.isfinite(tr.x).all() and np.isfinite(tr.y).all() and np.isfinite(tr.u).all()]
    if not good:
        raise ValueError(f"{sid}: no finite training trajectories")
    # finite blow-ups of the simulator (max |x| or |y| > 100 x the median over trajectories) are left out of every fit
    mx_ = np.array([float(np.abs(t.x).max()) for t in good]); my_ = np.array([float(np.abs(t.y).max()) for t in good])
    ok = (mx_ <= 100 * max(np.median(mx_), 1e-12)) & (my_ <= 100 * max(np.median(my_), 1e-12))
    if ok.sum() >= max(2, len(good) // 2):
        good = [t for t, o in zip(good, ok) if o]
    dt = float(good[0].dt)
    # statistics accumulated per trajectory (memory: real systems hold ~10^8 samples)
    n = 0
    sx1 = np.zeros(len(obs)); sx2 = np.zeros(len(obs))
    nu = good[0].u.shape[1]; ny = good[0].y.shape[1]
    su1 = np.zeros(nu); su2 = np.zeros(nu); sy1 = np.zeros(ny); sy2 = np.zeros(ny)
    xmin = np.inf
    for tr in good:
        X = tr.x.astype(np.float64)
        n += len(X)
        sx1 += X.sum(0); sx2 += (X ** 2).sum(0)
        U = tr.u.astype(np.float64); Y = tr.y.astype(np.float64)
        su1 += U.sum(0); su2 += (U ** 2).sum(0); sy1 += Y.sum(0); sy2 += (Y ** 2).sum(0)
        xmin = min(xmin, float(X.min()))
    mx = sx1 / n
    vx = np.maximum(sx2 / n - mx ** 2, 0.0)
    sdx = np.sqrt(vx)
    med = float(np.median(sdx[sdx > 0])) if (sdx > 0).any() else 1.0
    sx = np.maximum(sdx, max(0.1 * med, 1e-6))
    mu = su1 / n
    su = np.sqrt(np.maximum(su2 / n - mu ** 2, 0.0))
    su = np.where(su > 1e-9, su, 1.0)
    my = sy1 / n
    sy = np.sqrt(np.maximum(sy2 / n - my ** 2, 0.0))
    sy = np.maximum(sy, max(1e-6, 1e-3 * float(sy.max()) if sy.size else 1e-6))
    rows = [tr.x[0] for tr in good if (tr.protocol.get("r0") or {}).get("kind", "zero") == "zero"]
    rest = np.median(np.stack(rows or [tr.x[0] for tr in good]).astype(np.float64), axis=0)
    P = SysPrep(sid=sid, obs=obs, col={n_: i for i, n_ in enumerate(obs)}, dt=dt, mx=mx, sx=sx, mu=mu, su=su, my=my, sy=sy,
                nonneg=bool(xmin >= -1e-9), rest=rest)
    for tr in good:
        keep, hc = _free_mask(tr, len(tr.t))
        P.trajs.append(PTraj(key=tr.key, split=tr.split, family=tr.family,
                             xs=((tr.x.astype(np.float64) - mx) / sx).astype(np.float32),
                             us=((tr.u.astype(np.float64) - mu) / su).astype(np.float32),
                             y=tr.y.astype(np.float64), keep=keep, events=tr.events(), has_current=hc, dt=dt))
    P.T_len = int(np.median([len(t.xs) for t in P.trajs]))
    return P


def pca_basis(P: SysPrep, trajs: list[PTraj] | None = None, r: int | None = None, max_rows: int = 200000) -> tuple[np.ndarray, np.ndarray]:
    """Principal axes (r, N) and variances of the standardised microstate (covariance accumulated per trajectory)."""
    trajs = trajs if trajs is not None else P.trajs
    N = P.n_x
    tot = sum(len(t.xs) for t in trajs)
    stride = max(1, tot // max_rows)
    C = np.zeros((N, N)); m = np.zeros(N); n = 0
    for t in trajs:
        X = t.xs[::stride].astype(np.float64)
        C += X.T @ X; m += X.sum(0); n += len(X)
    m /= n
    C = C / n - np.outer(m, m)
    w, V = np.linalg.eigh(C)
    o = np.argsort(w)[::-1]
    w, V = np.maximum(w[o], 0.0), V[:, o]
    r = N if r is None else min(r, N)
    return V[:, :r].T.copy(), w


# ================================================================================================================ the model
class LinStateModel(StateModel):
    """Executable linear (optionally closure-augmented) state model for one or several systems (see module docstring)."""

    def __init__(self, method: str, version: str):
        self.method, self.version = method, version
        self.k: dict[str, int] = {}
        self.sys: dict[str, dict] = {}         # per system: prep stats, encoder, decoder, readout, event parameters
        self.dyn: dict[str, dict] = {}         # transition per system (shared models point several systems to one dict)
        self._info: dict = {}

    # ---------------------------------------------------------------------------------------------------- helpers
    def _xs(self, sid, x):
        s = self.sys[sid]
        return (np.asarray(x, np.float64) - s["mx"]) / s["sx"]

    def _us(self, sid, u):
        s = self.sys[sid]
        return (np.asarray(u, np.float64) - s["mu"]) / s["su"]

    # ---------------------------------------------------------------------------------------------------- encoder
    def encode(self, sid, x_hist, u_hist, dt):
        s = self.sys[sid]
        enc = s["enc"]
        X = np.asarray(x_hist)
        U = np.asarray(u_hist)
        T = len(X)
        lags = enc["lags"]
        z = enc["b"].copy()
        for li, L in enumerate(lags):
            i = max(0, T - 1 - L)
            z = z + enc["Hx"][li] @ self._xs(sid, X[i])
            if enc.get("Hu") is not None:
                z = z + enc["Hu"][li] @ self._us(sid, U[i])
        return z

    def encode_batch(self, sid, X: np.ndarray, U: np.ndarray, idx: np.ndarray) -> np.ndarray:
        """Standardised X (T, N), U (T, n_u) of one trajectory; latent at the sample indices idx."""
        enc = self.sys[sid]["enc"]
        Z = np.tile(enc["b"], (len(idx), 1))
        for li, L in enumerate(enc["lags"]):
            ii = np.maximum(0, idx - L)
            Z = Z + X[ii] @ enc["Hx"][li].T
            if enc.get("Hu") is not None:
                Z = Z + U[ii] @ enc["Hu"][li].T
        return Z

    # ---------------------------------------------------------------------------------------------------- transition
    def _step(self, sid, Z, Us):
        """Z (B, k), Us (B, n_u) standardised -> next Z."""
        d = self.dyn[sid]
        s = self.sys[sid]
        Zn = Z @ d["A"].T + Us @ s["Bs"].T + d["c"]
        if s.get("c_sys") is not None:
            Zn = Zn + s["c_sys"]
        nl = d.get("nl")
        if nl is not None:
            Zn = Zn + nl_apply(nl, Z, Us, self.sys[sid])
        return Zn

    def supports(self, sid, kind):
        ev = self.sys.get(sid, {}).get("ev", {})
        return kind in ev.get("kinds", ())

    def _guard(self, sid, key, M_fn) -> float:
        """Largest factor f in (1, 0.5, 0.25, 0.1, 0) on the coupling part of an event operator such that the event-modified
        linear transition M(f) is not more expansive than max(1, rho(A)) (cached per event set)."""
        ev = self.sys[sid]["ev"]
        key = key + (round(float(ev.get("cpl_scale", 1.0)), 6), round(float(ev.get("rel_scale", 1.0)), 6), id(ev.get("R")))
        cache = self.sys[sid].setdefault("_guard", {})
        if key in cache:
            return cache[key]
        A = self.dyn[sid]["A"]
        lim = max(1.0, float(np.max(np.abs(np.linalg.eigvals(A))))) + 1e-9
        f_ok = 0.0
        for f in (1.0, 0.5, 0.25, 0.1):
            M = M_fn(f)
            if np.all(np.isfinite(M)) and float(np.max(np.abs(np.linalg.eigvals(M)))) <= lim:
                f_ok = f
                break
        if len(cache) < 256:
            cache[key] = f_ok
        return f_ok

    def rollout(self, sid, z0, u_future, events, dt):
        s = self.sys[sid]
        ev = s["ev"]
        Us = self._us(sid, u_future)
        z = np.asarray(z0, np.float64).copy()
        H = len(Us) - 1
        Zs = np.zeros((H + 1, len(z)))
        Zs[0] = z
        events = events or []
        col = s["col"]
        K, C, d = ev["K"], s["C"], s["d"]
        for j in range(H):
            if events:
                kicks, sil, cur, edges = events_at(events, j * dt, dt)
            else:
                kicks, sil, cur, edges = {}, set(), {}, []
            if kicks:
                cols = [col[n] for n in kicks if n in col]
                if cols:
                    dxs = np.array([kicks[n] for n in kicks if n in col]) / s["sx"][cols]
                    if s["nonneg"]:
                        xh = (C[cols] @ z + d[cols])            # standardised decoded level
                        lo = -s["mx"][cols] / s["sx"][cols]      # standardised zero
                        dxs = np.maximum(xh + dxs, lo) - np.maximum(xh, lo)
                    z = z + ev.get("kick_scale", 1.0) * (K[:, cols] @ dxs)
            zn = self._step(sid, z[None, :], Us[j][None, :])[0]
            if cur:
                cols = [col[n] for n in cur if n in col]
                if cols:
                    I = np.array([cur[n] for n in cur if n in col])
                    zn = zn + ev["Kc"][:, cols] @ (ev["gamma"] * I / s["sx"][cols])
            if edges and ev.get("Jp") is not None:
                xh = C @ z + d
                pairs = [(col[a], col[b]) for a, b in edges if a in col and b in col]
                if pairs:
                    post = np.array([p for p, _ in pairs]); pre = np.array([q for _, q in pairs])
                    # J[post, pre] from the factored coupling Jp (N x r) Jq (N x r)^T; standardised units
                    jw = np.einsum("ij,ij->i", ev["Jp"][post], ev["Jq"][pre])
                    Dm = np.zeros((len(d), len(z)))
                    np.add.at(Dm, post, -jw[:, None] * C[pre])
                    g = self._guard(sid, ("e", tuple(sorted(pairs))),
                                    lambda f: self.dyn[sid]["A"] + f * ev.get("cpl_scale", 1.0) * (ev["Kc"] @ Dm))
                    dx = np.zeros(len(d))
                    np.add.at(dx, post, -jw * (xh[pre] - ev["Jref"][pre]))
                    zn = zn + g * ev.get("cpl_scale", 1.0) * (ev["Kc"] @ dx)
            if sil:
                cols = [col[n] for n in sil if n in col]
                if cols:
                    cols = np.array(cols)
                    xh_prev = C[cols] @ z + d[cols]
                    # 1) coupling of the silenced neurons onto the rest removed: their deviation from the decoupled level no
                    #    longer drives the latent (read-in map R)
                    Rs = ev.get("Rs", ev.get("R"))
                    if Rs is not None:
                        cs, rs = ev.get("cpl_scale", 1.0), ev.get("rel_scale", 1.0) * ev["alpha_sil"]
                        Kr = np.eye(len(z)) - rs * (K[:, cols] @ C[cols])
                        g = self._guard(sid, ("s", tuple(cols.tolist())),
                                        lambda f: Kr @ (self.dyn[sid]["A"] - f * cs * (Rs[:, cols] @ C[cols])))
                        zn = zn - g * cs * (Rs[:, cols] @ (xh_prev - ev.get("r_cpl", ev["r_sil"])[cols]))
                    # 2) their own activity relaxes to the decoupled level (seen through the encoder gain)
                    xh = C[cols] @ zn + d[cols]
                    zn = zn + ev.get("rel_scale", 1.0) * ev["alpha_sil"] * (K[:, cols] @ (ev["r_sil"][cols] - xh))
            z = zn
            box = s.get("zbox")
            if box is not None:
                z = np.clip(z, box[0], box[1])
            Zs[j + 1] = z
        return {"z": Zs, "y": self.readout(sid, Zs, u_future[: H + 1])}

    def rollout_batch(self, sid, Z0: np.ndarray, Us: np.ndarray) -> np.ndarray:
        """Event-free batched rollout: Z0 (B, k), Us (B, H+1, n_u) standardised -> Z (B, H+1, k)."""
        B, H1, _ = Us.shape
        Z = np.zeros((B, H1, Z0.shape[1]))
        Z[:, 0] = Z0
        z = Z0
        box = self.sys[sid].get("zbox")
        for j in range(H1 - 1):
            z = self._step(sid, z, Us[:, j])
            if not np.isfinite(z).all():
                z = np.nan_to_num(z, nan=1e6, posinf=1e6, neginf=-1e6)
                z = np.clip(z, -1e6, 1e6)
            if box is not None:
                z = np.clip(z, box[0], box[1])
            Z[:, j + 1] = z
        return Z

    # ---------------------------------------------------------------------------------------------------- readout
    def readout(self, sid, z, u):
        s = self.sys[sid]
        z = np.asarray(z, np.float64)
        u = np.asarray(u, np.float64)
        shp = z.shape[:-1]
        Z = z.reshape(-1, z.shape[-1])
        Us = self._us(sid, u.reshape(-1, u.shape[-1]))
        F = readout_features(s["ro"], Z, Us)
        Y = F @ s["ro"]["G"] + s["ro"]["h"]
        return Y.reshape(shp + (Y.shape[-1],))

    def readout_s(self, sid, Z, Us):
        """Readout from standardised inputs (internal, batched)."""
        ro = self.sys[sid]["ro"]
        sh = Z.shape[:-1]
        F = readout_features(ro, Z.reshape(-1, Z.shape[-1]), Us.reshape(-1, Us.shape[-1]))
        return (F @ ro["G"] + ro["h"]).reshape(sh + (ro["G"].shape[1],))

    # ---------------------------------------------------------------------------------------------------- info
    def info(self):
        return self._info

    def lift(self, sid, x, z, delta_z, n_candidates=3):
        """Minimum-norm kicks realising delta_z through the kick gain K: dxs = K^+ delta_z, restricted to public targets; distinct
        candidates use (i) all public targets, (ii) the neurons with the largest gain norms, (iii) a random half of the targets."""
        s = self.sys[sid]
        K = s["ev"]["K"]
        targets = [n for n in s.get("targets", []) if n in s["col"]] or list(s["col"])
        cols_all = np.array([s["col"][n] for n in targets])
        rng = np.random.default_rng(0)
        cands = [cols_all]
        norms = np.linalg.norm(K[:, cols_all], axis=0)
        m = max(len(z), min(len(cols_all), 3 * len(z)))
        cands.append(cols_all[np.argsort(norms)[::-1][:m]])
        if len(cols_all) > 2 * len(z):
            cands.append(np.sort(rng.choice(cols_all, size=max(len(z), len(cols_all) // 2), replace=False)))
        out = []
        for cols in cands[:n_candidates]:
            Kc = K[:, cols]
            dxs = np.linalg.lstsq(Kc, np.asarray(delta_z, float), rcond=None)[0]
            dx = dxs * s["sx"][cols]
            out.append([{"kind": "kick", "t": 0.0, "delta": {str(s["obs"][c]): float(v) for c, v in zip(cols, dx) if abs(v) > 1e-9}}])
        return out


# ================================================================================================================ readout
def readout_features(ro: dict, Z: np.ndarray, Us: np.ndarray) -> np.ndarray:
    kind = ro.get("kind", "linear")
    parts = [Z, Us]
    if kind == "quad":
        Zn = (Z - ro["zm"]) / ro["zs"]
        iu = np.triu_indices(Z.shape[1])
        parts.append((Zn[:, :, None] * Zn[:, None, :])[:, iu[0], iu[1]])
    elif kind == "rff":
        Zn = (Z - ro["zm"]) / ro["zs"]
        parts.append(np.cos(Zn @ ro["Wf"] + ro["bf"]))
    return np.hstack(parts)


def fit_readout(Z: np.ndarray, Us: np.ndarray, Y: np.ndarray, kind: str = "linear", lam: float = 1e-4, seed: int = 0) -> dict:
    ro = {"kind": kind}
    if kind in ("quad", "rff"):
        ro["zm"], ro["zs"] = Z.mean(0), Z.std(0) + 1e-9
    if kind == "rff":
        rng = np.random.default_rng(seed)
        nf = int(min(200, max(20, 20 * Z.shape[1])))
        ro["Wf"] = rng.standard_normal((Z.shape[1], nf)) / np.sqrt(max(1, Z.shape[1]))
        ro["bf"] = rng.uniform(0, 2 * np.pi, nf)
    F = readout_features(ro, Z, Us)
    mu, sd = F.mean(0), F.std(0) + 1e-9
    Fs = np.hstack([(F - mu) / sd, np.ones((len(F), 1))])
    W = ridge_solve(Fs, Y, lam)
    ro["G"] = W[:-1] / sd[:, None]
    ro["h"] = W[-1] - mu @ ro["G"]
    return ro


def nl_apply(nl: dict, Z: np.ndarray, Us: np.ndarray, s: dict) -> np.ndarray:
    """Nonlinear closure residual: a small tanh MLP on standardised [z, u] (numpy forward)."""
    Zin = np.hstack([(Z - nl["zm"]) / nl["zs"], Us])
    h = np.tanh(Zin @ nl["W1"] + nl["b1"])
    if "W2" in nl and nl.get("W3") is not None:
        h = np.tanh(h @ nl["W2"] + nl["b2"])
        return (h @ nl["W3"] + nl["b3"]) * nl["scale"]
    return (h @ nl["W2"] + nl["b2"]) * nl["scale"]
