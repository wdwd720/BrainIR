"""Reference models of the evaluator (controls, NOT candidate methods): empirical ceiling, shortcut floors, linear controls.

    fullstate     learned autoregressive model on the full ACTIVE state [x_observed, y] (the information ceiling of goal4 section 49):
                  an MLP for the one-step change; kicks add to the state, silencing clamps the neuron at its REST value (the first
                  sample of training trajectories that start at rest), current pulses enter as a per-neuron input channel
    input_only    y(t+h) from the input history alone (goal4 section 50; shortcut control)
    readout_hist  y(t+h) from the readout history and the input (shortcut control; cannot represent interventions)
    pca_linear    k principal components of x (public train fit) with least-squares linear latent dynamics and a ridge readout
    random_proj   the same with a random orthonormal projection (null control)
    true_latent   CALIBRATION ONLY (synthetic systems, orchestrator side): the TRUE latent state as encoder (exact lookup of the
                  recorded microstate, a ridge probe elsewhere), an MLP transition and readout of the ceiling's class, events through
                  the probe (kick: z += W dx; current: z += W I dt; silence: decode, clamp at rest, re-encode)

All implement brainir_state.api.StateModel, work at any sampling step dt, and are trained on PUBLIC train trajectories only (the
true-latent reference also on the training trajectories' truth). Nothing here depends on a particular system: value ranges (e.g.
non-negativity), rest values and input scales are estimated from the training data.
"""

from __future__ import annotations

import numpy as np

from .api import StateModel
from .data import Trajectory


def _ridge(X, Y, lam=1e-3):
    mu, sd = X.mean(0), X.std(0) + 1e-9
    A = (X - mu) / sd
    ym = Y.mean(0)
    W = np.linalg.solve(A.T @ A + lam * len(A) * np.eye(A.shape[1]), A.T @ (Y - ym))
    return mu, sd, W, ym


def _ridge_apply(p, X):
    mu, sd, W, ym = p
    return ((X - mu) / sd) @ W + ym


def _events_at(events: list[dict], t: float, dt: float):
    """(kicks at t, silenced set during [t, t+dt), current dict during [t, t+dt)) for one step."""
    kicks, silenced, cur = {}, set(), {}
    for e in events:
        if e["kind"] == "kick" and abs(e["t"] - t) < dt / 2:
            for k, v in e["delta"].items():
                kicks[int(k)] = kicks.get(int(k), 0.0) + float(v)
        elif e["kind"] == "silence" and e["t0"] <= t + 1e-9 and (e["t1"] is None or t < e["t1"] - 1e-9):
            silenced |= {int(n) for n in e["targets"]}
        elif e["kind"] == "current" and e["t0"] <= t + 1e-9 and t < e["t1"] - 1e-9:
            for k, v in e["targets"].items():
                cur[int(k)] = cur.get(int(k), 0.0) + float(v)
    return kicks, silenced, cur


def _event_masks(tr: Trajectory, col: dict[int, int], drop_current: bool = False):
    """Per step: current matrix (T, n_x) and a mask of transitions that are free dynamics (no kick jump, no silencing, and no
    injected current when drop_current)."""
    n = len(tr.t)
    cur = np.zeros((n, len(col)), np.float32)
    keep = np.ones(n - 1, bool)
    for e in tr.events():
        if e["kind"] == "current":
            a, b = int(round(e["t0"] / tr.dt)), int(round(e["t1"] / tr.dt))
            for k, v in e["targets"].items():
                if int(k) in col:
                    cur[a:b, col[int(k)]] += v
            if drop_current:
                keep[a:b] = False
        elif e["kind"] == "kick":
            keep[min(n - 2, int(round(e["t"] / tr.dt)))] = False
        elif e["kind"] in ("silence", "edge_remove"):
            a = int(round(e["t0"] / tr.dt))
            b = n - 1 if e.get("t1") is None else int(round(e["t1"] / tr.dt))
            keep[a:b] = False
    return cur, keep


def rest_state(trajs: list[Trajectory]) -> np.ndarray:
    """The observed state at rest: median first sample of training trajectories that start from the default rest state."""
    rows = [tr.x[0] for tr in trajs if (tr.protocol.get("r0") or {}).get("kind", "zero") == "zero"]
    if not rows:
        rows = [tr.x[0] for tr in trajs]
    return np.median(np.stack(rows).astype(np.float64), axis=0)


def _train_mlp(X: np.ndarray, Y: np.ndarray, hidden: int, seed: int, steps: int = 3000, batch: int = 4096, lr: float = 1e-3):
    import torch
    torch.manual_seed(seed)
    net = torch.nn.Sequential(torch.nn.Linear(X.shape[1], hidden), torch.nn.GELU(), torch.nn.Linear(hidden, hidden), torch.nn.GELU(),
                              torch.nn.Linear(hidden, Y.shape[1]))
    Xt, Yt = torch.tensor(X, dtype=torch.float32), torch.tensor(Y, dtype=torch.float32)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, steps)
    g = torch.Generator().manual_seed(seed)
    n, bs = len(Xt), min(batch, len(Xt))
    for _ in range(steps):
        b = torch.randint(0, n, (bs,), generator=g)
        loss = torch.mean((net(Xt[b]) - Yt[b]) ** 2)
        opt.zero_grad(); loss.backward(); opt.step(); sched.step()
    return net.eval()


def _mlp_apply(net, X: np.ndarray) -> np.ndarray:
    import torch
    with torch.no_grad():
        return net(torch.tensor(np.atleast_2d(X), dtype=torch.float32)).numpy().astype(np.float64)


# ------------------------------------------------------------------------------------------------------------ full-state ceiling
class FullStateModel(StateModel):
    """Autoregressive ceiling on s = [x_obs, y] with a torch MLP for (s_{t+1} - s_t)."""

    def __init__(self, observed: list[int], n_y: int, hidden: int = 256, steps: int = 3000, seed: int = 0):
        self.observed = [int(n) for n in observed]
        self.col = {n: i for i, n in enumerate(self.observed)}
        self.n_y, self.hidden, self.steps, self.seed = n_y, hidden, steps, seed
        self.k = {}

    def fit(self, sid: str, trajs: list[Trajectory]):
        S, U, C, DS = [], [], [], []
        for tr in trajs:
            s = np.hstack([tr.x, tr.y]).astype(np.float32)
            cur, keep = _event_masks(tr, self.col)
            S.append(s[:-1][keep]); U.append(tr.u[:-1][keep]); C.append(cur[:-1][keep]); DS.append((s[1:] - s[:-1])[keep])
        S, U, C, DS = map(np.concatenate, (S, U, C, DS))
        allS = np.concatenate([np.hstack([tr.x, tr.y]) for tr in trajs])
        self.nonneg = bool((allS >= -1e-9).all())          # e.g. firing rates: keep predictions in range
        self.rest = rest_state(trajs)
        self.s_mu, self.s_sd = S.mean(0), S.std(0) + 1e-3
        self.u_mu, self.u_sd = U.mean(0), U.std(0) + 1e-6
        nz = np.abs(C[C != 0])
        self.c_sd = float(nz.std() + nz.mean()) if nz.size else 1.0
        self.d_sd = DS.std(0) + 1e-6
        X = np.hstack([(S - self.s_mu) / self.s_sd, (U - self.u_mu) / self.u_sd, C / self.c_sd])
        self.net = _train_mlp(X, DS / self.d_sd, self.hidden, self.seed, self.steps)
        self.k[sid] = S.shape[1]
        return self

    def _step(self, s, u, cur):
        inp = np.hstack([(s - self.s_mu) / self.s_sd, (u - self.u_mu) / self.u_sd, cur / self.c_sd])
        s2 = s + _mlp_apply(self.net, inp)[0] * self.d_sd
        return np.maximum(s2, 0.0) if self.nonneg else s2

    uses_readout = True   # a CONTROL: the ceiling sees the full active state, readout included

    def encode(self, sid, x_hist, u_hist, dt):
        raise RuntimeError("the full-state ceiling is evaluated through encode_with_readout")

    def encode_with_readout(self, sid, x_hist, u_hist, y_hist, dt):
        return np.hstack([np.asarray(x_hist[-1], float), np.asarray(y_hist[-1], float)])

    def supports(self, sid, kind):
        return kind in ("kick", "silence", "current")

    def rollout(self, sid, z0, u_future, events, dt):
        n_x = len(self.observed)
        s = np.asarray(z0, float).copy()
        out = [s.copy()]
        for j in range(len(u_future) - 1):
            kicks, sil, cur = _events_at(events, j * dt, dt)
            for n, d in kicks.items():
                if n in self.col:
                    s[self.col[n]] += d
                    if self.nonneg:
                        s[self.col[n]] = max(0.0, s[self.col[n]])
            cvec = np.zeros(n_x)
            for n, v in cur.items():
                if n in self.col:
                    cvec[self.col[n]] = v
            s = self._step(s, u_future[j], cvec)
            for n in sil:
                if n in self.col:
                    s[self.col[n]] = self.rest[self.col[n]]
            out.append(s.copy())
        S = np.stack(out)
        return {"z": S, "y": S[:, n_x:]}

    def readout(self, sid, z, u):
        return np.asarray(z)[..., len(self.observed):]


# ------------------------------------------------------------------------------------------------------------ shortcut controls
class DirectHorizonModel(StateModel):
    """y(t+h) = R_h(features at t): input history (input_only) or readout + input history (readout_hist). z = the feature vector.
    Horizons and lags are in seconds (converted with the data's dt)."""

    def __init__(self, kind: str, horizons_s: tuple[float, ...] = (0.001, 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0),
                 lags_s: tuple[float, ...] = (0.0, 0.005, 0.01, 0.02, 0.05, 0.1, 0.2)):
        assert kind in ("input_only", "readout_hist")
        self.kind, self.hs_s, self.lags_s = kind, horizons_s, lags_s
        self.k = {}

    def _feat(self, u_hist, y_hist, i):
        f = [u_hist[max(0, i - L)] for L in self.lags]
        on = np.flatnonzero(np.abs(u_hist[: i + 1]).sum(axis=1) > 1e-9)
        f.append(np.array([0.0 if len(on) == 0 else min(1.0, (i - on[0]) * self.dt)]))   # time since input onset (input-derived)
        if self.kind == "readout_hist":
            f += [y_hist[max(0, i - L)] for L in self.lags]
        return np.concatenate(f)

    def fit(self, sid, trajs: list[Trajectory]):
        self.dt = trajs[0].dt
        self.lags = sorted({int(round(L / self.dt)) for L in self.lags_s})
        T = min(len(tr.t) for tr in trajs)
        self.hs = sorted({max(1, int(round(h / self.dt))) for h in self.hs_s if max(1, int(round(h / self.dt))) < T - self.lags[-1] - 1})
        stride = max(1, T // 80)
        self.models = {}
        for h in self.hs:
            X, Y = [], []
            for tr in trajs:
                for i in range(self.lags[-1], len(tr.t) - h, stride):
                    X.append(np.concatenate([self._feat(tr.u, tr.y, i), tr.u[i + h]]))
                    Y.append(tr.y[i + h])
            self.models[h] = _ridge(np.array(X), np.array(Y), 1e-2)
        self.k[sid] = len(self._feat(trajs[0].u, trajs[0].y, self.lags[-1]))
        return self

    @property
    def uses_readout(self) -> bool:     # the readout-history shortcut is a CONTROL that sees y by construction
        return self.kind == "readout_hist"

    def encode(self, sid, x_hist, u_hist, dt):
        if self.kind == "readout_hist":
            raise RuntimeError("readout_hist is evaluated through encode_with_readout")
        return self._feat(u_hist, None, len(u_hist) - 1)

    def encode_with_readout(self, sid, x_hist, u_hist, y_hist, dt):
        return self._feat(u_hist, y_hist, len(u_hist) - 1)

    def supports(self, sid, kind):
        return False

    def rollout(self, sid, z0, u_future, events, dt):
        H = len(u_future) - 1
        hs = np.array(self.hs)
        ys = []
        for j in range(H + 1):
            h = int(hs[np.argmin(np.abs(hs - max(j, 1)))])
            ys.append(_ridge_apply(self.models[h], np.concatenate([z0, u_future[j]])[None, :])[0])
        return {"z": np.tile(z0, (H + 1, 1)), "y": np.stack(ys)}

    def readout(self, sid, z, u):
        z, u = np.atleast_2d(z), np.atleast_2d(u)
        return _ridge_apply(self.models[self.hs[0]], np.hstack([z, u]))


# ------------------------------------------------------------------------------------------------------------ linear controls
class ProjectionLinearModel(StateModel):
    """z = P (x - mean) (P: top-k PCs or a random orthonormal basis); the exact one-step discrete map z_{t+dt} = A z_t + B u_t + c
    (least squares on consecutive free-dynamics samples, every `stride`-th pair used); y = ridge(z, u). Kicks: z += P dx.
    Silencing: reconstruct, clamp the neuron at its rest value, re-project, every step. Currents: unsupported."""

    def __init__(self, k: int, kind: str = "pca", stride: int = 1, seed: int = 0):
        self.kk, self.kind, self.stride, self.seed = k, kind, stride, seed
        self.k = {}

    def fit(self, sid, trajs: list[Trajectory], observed: list[int]):
        self.col = {int(n): i for i, n in enumerate(observed)}
        X = np.concatenate([t.x for t in trajs]).astype(np.float64)
        self.mean = X.mean(0)
        self.rest = rest_state(trajs)
        kk = min(self.kk, X.shape[1])
        if self.kind == "pca":
            _, _, Vt = np.linalg.svd(X[:: max(1, len(X) // 20000)] - self.mean, full_matrices=False)
            self.P = Vt[:kk]
        else:
            q, _ = np.linalg.qr(np.random.default_rng(self.seed).standard_normal((X.shape[1], kk)))
            self.P = q.T[:kk]
        Zs, Us, Zn, Ys = [], [], [], []
        s = self.stride
        for tr in trajs:
            Z = (tr.x - self.mean) @ self.P.T
            _, keep = _event_masks(tr, self.col, drop_current=True)
            ii = np.flatnonzero(keep)[::s]
            Zs.append(Z[ii]); Us.append(tr.u[ii]); Zn.append(Z[ii + 1]); Ys.append(tr.y)
        Zc, Uc, Znc = np.concatenate(Zs), np.concatenate(Us), np.concatenate(Zn)
        F = np.hstack([Zc, Uc, np.ones((len(Zc), 1))])
        self.M = np.linalg.lstsq(F, Znc, rcond=None)[0]
        Zall = np.concatenate([(t.x - self.mean) @ self.P.T for t in trajs])
        Uall = np.concatenate([t.u for t in trajs])
        self.R = _ridge(np.hstack([Zall, Uall]), np.concatenate(Ys), 1e-3)
        self.k[sid] = kk
        return self

    def encode(self, sid, x_hist, u_hist, dt):
        return (np.asarray(x_hist[-1], float) - self.mean) @ self.P.T

    def supports(self, sid, kind):
        return kind in ("kick", "silence")

    def rollout(self, sid, z0, u_future, events, dt):
        z = np.asarray(z0, float).copy()
        zs = [z.copy()]
        for j in range(len(u_future) - 1):
            kicks, sil, _ = _events_at(events, j * dt, dt)
            if kicks:
                dx = np.zeros(len(self.mean))
                for n, d in kicks.items():
                    if n in self.col:
                        dx[self.col[n]] = d
                z = z + self.P @ dx
            z = np.hstack([z, u_future[j], 1.0]) @ self.M
            if sil:
                xr = self.mean + z @ self.P
                for n in sil:
                    if n in self.col:
                        xr[self.col[n]] = self.rest[self.col[n]]
                z = (xr - self.mean) @ self.P.T
            zs.append(z.copy())
        Z = np.stack(zs)
        return {"z": Z, "y": _ridge_apply(self.R, np.hstack([Z, u_future[: len(Z)]]))}

    def readout(self, sid, z, u):
        z, u = np.atleast_2d(z), np.atleast_2d(u)
        return _ridge_apply(self.R, np.hstack([z, u]))


# ------------------------------------------------------------------------------------------------------------ calibration reference
class TrueLatentModel(StateModel):
    """CALIBRATION reference (orchestrator only; needs synthetic truth): encoder = the TRUE latent. For recorded samples whose truth
    is registered (`register`), encode returns the true latent exactly; elsewhere a ridge probe W from x to the true latent (fitted on
    training data). Transition: an MLP for z_{t+1} - z_t on [z, u, W-projected current] (the ceiling's class and budget); readout:
    an MLP z, u -> y. Events through the probe: kick z += W dx; current enters as W I; silencing decodes x (ridge decoder), clamps the
    neuron at its rest value and re-encodes. It measures how well a model that HAS the true state and learns everything else from
    the same training data can do, which calibrates the tolerances of PROTOCOL.md section 6."""

    def __init__(self, observed: list[int], hidden: int = 256, steps: int = 3000, seed: int = 0):
        self.observed = [int(n) for n in observed]
        self.col = {n: i for i, n in enumerate(self.observed)}
        self.hidden, self.steps, self.seed = hidden, steps, seed
        self.k = {}
        self.lookup: dict[bytes, np.ndarray] = {}

    def register(self, x: np.ndarray, z: np.ndarray) -> None:
        for xr, zr in zip(np.asarray(x, np.float32), np.asarray(z, np.float64)):
            self.lookup[xr.tobytes()] = zr

    def fit(self, sid: str, trajs: list[Trajectory], z_true: dict[str, np.ndarray]):
        X = np.concatenate([tr.x for tr in trajs]).astype(np.float64)
        Z = np.concatenate([z_true[tr.key] for tr in trajs]).astype(np.float64)
        self.W = _ridge(X, Z, 1e-4)                  # probe x -> z
        self.V = _ridge(Z, X, 1e-4)                  # decoder z -> x
        self.rest = rest_state(trajs)
        muX, sdX, Wm, _ = self.W
        self.Wlin = (Wm / sdX[:, None]).T            # dz = Wlin @ dx
        S, U, C, DS = [], [], [], []
        for tr in trajs:
            self.register(tr.x, z_true[tr.key])
            z = z_true[tr.key].astype(np.float64)
            cur, keep = _event_masks(tr, self.col)
            cz = cur.astype(np.float64) @ self.Wlin.T
            S.append(z[:-1][keep]); U.append(tr.u[:-1][keep]); C.append(cz[:-1][keep]); DS.append((z[1:] - z[:-1])[keep])
        S, U, C, DS = map(np.concatenate, (S, U, C, DS))
        self.z_mu, self.z_sd = S.mean(0), S.std(0) + 1e-6
        self.u_mu, self.u_sd = U.mean(0), U.std(0) + 1e-6
        nz = np.abs(C[C != 0])
        self.c_sd = float(nz.std() + nz.mean()) if nz.size else 1.0
        self.d_sd = DS.std(0) + 1e-9
        Xin = np.hstack([(S - self.z_mu) / self.z_sd, (U - self.u_mu) / self.u_sd, C / self.c_sd])
        self.net = _train_mlp(Xin, DS / self.d_sd, self.hidden, self.seed, self.steps)
        Zall = np.concatenate([z_true[tr.key] for tr in trajs]).astype(np.float64)
        Uall = np.concatenate([tr.u for tr in trajs]).astype(np.float64)
        Yall = np.concatenate([tr.y for tr in trajs]).astype(np.float64)
        self.y_mu, self.y_sd = Yall.mean(0), Yall.std(0) + 1e-9
        self.ro = _train_mlp(np.hstack([(Zall - self.z_mu) / self.z_sd, (Uall - self.u_mu) / self.u_sd]), (Yall - self.y_mu) / self.y_sd,
                             self.hidden, self.seed + 1, self.steps)
        self.k[sid] = Z.shape[1]
        return self

    def encode(self, sid, x_hist, u_hist, dt):
        xr = np.asarray(x_hist[-1], np.float32)
        z = self.lookup.get(xr.tobytes())
        return z.copy() if z is not None else _ridge_apply(self.W, xr[None, :].astype(np.float64))[0]

    def supports(self, sid, kind):
        return kind in ("kick", "silence", "current")

    def rollout(self, sid, z0, u_future, events, dt):
        z = np.asarray(z0, float).copy()
        out = [z.copy()]
        for j in range(len(u_future) - 1):
            kicks, sil, cur = _events_at(events, j * dt, dt)
            if kicks:
                dx = np.zeros(len(self.observed))
                for n, d in kicks.items():
                    if n in self.col:
                        dx[self.col[n]] = d
                z = z + self.Wlin @ dx
            cvec = np.zeros(len(self.observed))
            for n, v in cur.items():
                if n in self.col:
                    cvec[self.col[n]] = v
            inp = np.hstack([(z - self.z_mu) / self.z_sd, (u_future[j] - self.u_mu) / self.u_sd, (self.Wlin @ cvec) / self.c_sd])
            z = z + _mlp_apply(self.net, inp)[0] * self.d_sd
            if sil:
                xr = _ridge_apply(self.V, z[None, :])[0]
                x2 = xr.copy()
                for n in sil:
                    if n in self.col:
                        x2[self.col[n]] = self.rest[self.col[n]]
                z = z + self.Wlin @ (x2 - xr)
            out.append(z.copy())
        Z = np.stack(out)
        return {"z": Z, "y": self.readout(sid, Z, u_future[: len(Z)])}

    def readout(self, sid, z, u):
        z, u = np.atleast_2d(z), np.atleast_2d(u)
        return _mlp_apply(self.ro, np.hstack([(z - self.z_mu) / self.z_sd, (u - self.u_mu) / self.u_sd])) * self.y_sd + self.y_mu
