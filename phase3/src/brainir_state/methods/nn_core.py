"""Shared machinery of the "nn" family (families D and F: predictive bottleneck and latent neural state-space models).

Model (one system s; several systems may share the transition f):

    features   a_t = [x~_t, x~_{t-l_1}, ...]                       x~ = (x - mu_x) / sd_x  (train statistics; causal lags chosen by
                                                                   nn_fit.history_rule, usually none)
    encoder    z_t = phi_s(a_t) = W_s a_t + b_s  (+ MLP_s(a_t))      never sees y, never sees samples after t
    dynamics   z_{j+1} = f(z_j, u~_j) + G_cur W0 c~_j + G_J W0 J (m_j * (r~ - x^_j) - E_j (x^_j - r~))   [+ G_so W0 (m_j * (r~ - x^_j))]
    readout    y~_j = g_s(z_j, u~_j)
    decoder    x^_j = d_s(z_j)          (auxiliary reconstruction; gives the activity of silenced / decoupled neurons)

on an internal grid of step Delta = stride * dt (stride from a generic autocorrelation rule). W0 = the encoder block acting on
the current sample. Events (neuron ids -> columns of x):
    kick     z <- z + phi(x^ + d~) - phi(x^)      (= W0 d~ for the linear encoder): through the encoder, exact for any target;
    current  latent drive G_cur W0 c~ (c~ = injected current / sd_x, averaged over the step);
    silence  removal of the silenced neurons' outgoing effective couplings J (ridge regression of x~ increments on x~ over event-free
             training steps, off-diagonal part, masked by the public connectome when one is given), mapped to latent space through
             the encoder: G_J W0 J (m * (r~ - x^)). (Optional, off by default: an observation-side route G_so that pulls the decoded
             activity of silenced neurons to rest; in these simulators silenced neurons keep their own activity, and the two routes
             double-counted - see notes/nn_closed.md.)
    edge_remove  the removed couplings' drive -(J * E)(x^ - r~) through the same J path (G_J is learned from single-neuron
             silencing, i.e. removal of all outgoing couplings of a neuron).
Gains are scalars times the identity by default (gain_mode 'scalar', initialised at 0 and learned from the training events).
No per-neuron parameters are learned for events: a target never intervened in training acts through its encoder column, its
decoded activity and its estimated couplings.

Objective (per window of H internal steps started at a sampled grid point, events of the window applied in the rollout):
    L = mean_h ||g(z_h, u_h) - y~_h||^2                               multi-horizon open-loop readout NMSE (h = 0..H)
      + lam_lat mean_h ||z_h - sg(phi(a_{t+h}))||^2 / Var(z)            latent self-consistency f^h(phi(x_t)) ~ phi(x_{t+h})
      + lam_x   mean_h ||d(z_h) - x~_{t+h}||^2                          low-weight reconstruction (anti-collapse, decoder)
      + lam_n   sum_i (mean z_i^2 + (Var z_i - 1)^2)                     latent normalisation (fixes the scale gauge)
with Gaussian noise of sd sigma_z on z_0 and on every step (dimension-cheating guard) and weight decay.
"""

from __future__ import annotations

import copy
import math
import time
from dataclasses import dataclass, field

import numpy as np
import torch
import torch.nn as nn

from ..api import StateModel

EVENT_KINDS_ALL = ("kick", "current", "silence", "edge_remove")


# ------------------------------------------------------------------------------------------------------------ threads / seeds
def set_threads(n: int = 3) -> None:
    try:
        torch.set_num_threads(n)
    except Exception:
        pass


def seed_all(seed: int) -> torch.Generator:
    torch.manual_seed(int(seed))
    np.random.seed(int(seed) % (2 ** 32))
    return torch.Generator().manual_seed(int(seed))


# ------------------------------------------------------------------------------------------------------------ normalisation
@dataclass
class SysNorm:
    """Per-system preprocessing (fitted on the fit's training data only)."""
    sid: str
    observed: list
    col: dict
    mu_x: np.ndarray
    sd_x: np.ndarray
    mu_u: np.ndarray
    sd_u: np.ndarray
    mu_y: np.ndarray
    sd_y: np.ndarray
    y_min: np.ndarray
    rest: np.ndarray            # standardised rest state (x~ units)
    dt: float
    stride: int
    lags: tuple                 # history lags in internal steps (0 = current sample only)

    @property
    def n_x(self) -> int:
        return len(self.mu_x)

    @property
    def n_u(self) -> int:
        return len(self.mu_u)

    @property
    def n_y(self) -> int:
        return len(self.mu_y)


def _rest_state(trajs) -> np.ndarray:
    rows = [tr.x[0] for tr in trajs if (tr.protocol.get("r0") or {}).get("kind", "zero") == "zero"]
    if not rows:
        rows = [tr.x[0] for tr in trajs]
    return np.median(np.stack(rows).astype(np.float64), axis=0)


def choose_stride(trajs, max_steps: int = 400, acf_min: float = 0.9) -> int:
    """Generic internal-step rule: the largest stride s (from 1) such that the lag-s autocorrelation of the increments-free signal
    (top principal components of x and y) stays >= acf_min, and trajectories keep >= 200 internal steps; and at least the stride that
    brings a trajectory to <= max_steps... never above the acf limit."""
    T = min(len(tr.t) for tr in trajs)
    sample = trajs[: min(len(trajs), 40)]
    X = np.concatenate([np.hstack([tr.x, tr.y]) for tr in sample]).astype(np.float64)
    mu, sd = X.mean(0), X.std(0) + 1e-9
    Xs = (X - mu) / sd
    _, _, Vt = np.linalg.svd(Xs[:: max(1, len(Xs) // 4000)], full_matrices=False)
    P = Vt[: min(5, Vt.shape[0])]

    def acf(s):
        vals = []
        for tr in sample:
            Z = ((np.hstack([tr.x, tr.y]) - mu) / sd) @ P.T
            a, b = Z[:-s], Z[s:]
            num = ((a - a.mean(0)) * (b - b.mean(0))).sum(0)
            den = np.sqrt(((a - a.mean(0)) ** 2).sum(0) * ((b - b.mean(0)) ** 2).sum(0)) + 1e-12
            vals.append(num / den)
        return float(np.median(np.concatenate(vals)))

    s = 1
    while T // (s + 1) >= 200 and acf(s + 1) >= acf_min and s < 50:
        s += 1
    return s


def fit_norm(sid: str, trajs, observed, stride: int, lags: tuple) -> SysNorm:
    X = np.concatenate([tr.x for tr in trajs]).astype(np.float64)
    U = np.concatenate([tr.u for tr in trajs]).astype(np.float64)
    Y = np.concatenate([tr.y for tr in trajs]).astype(np.float64)
    mu_x, sd_x = X.mean(0), X.std(0)
    pos = sd_x[sd_x > 0]
    floor = 0.1 * float(np.median(pos)) if pos.size else 1.0
    sd_x = np.maximum(sd_x, max(floor, 1e-6))
    mu_u, sd_u = U.mean(0), U.std(0)
    sd_u = np.where(sd_u > 1e-9, sd_u, 1.0)
    vy = Y.var(0)
    vy = np.maximum(vy, max(1e-6, 1e-3 * float(vy.max()) if vy.size else 1e-6))   # the evaluator's NMSE normaliser
    rest = (_rest_state(trajs) - mu_x) / sd_x
    return SysNorm(sid=sid, observed=[int(n) for n in observed], col={int(n): i for i, n in enumerate(observed)}, mu_x=mu_x, sd_x=sd_x,
                   mu_u=mu_u, sd_u=sd_u, mu_y=Y.mean(0), sd_y=np.sqrt(vy), y_min=Y.min(0), rest=rest, dt=float(trajs[0].dt),
                   stride=int(stride), lags=tuple(int(l) for l in lags))


# ------------------------------------------------------------------------------------------------------------ events on a grid
def _grid_events(events: list, norm: SysNorm, n_steps: int, dt: float, stride: int) -> list[dict]:
    """Compile protocol events (times relative to the grid origin) into per-internal-step descriptors on a grid of n_steps steps:
    [{"kind", "j0", "j1", "idx" (columns), "val" (standardised), "frac" (per-step fraction active, for windows)}]."""
    out = []
    s = stride
    for e in events or []:
        k = e["kind"]
        if k == "kick":
            i = int(round(float(e["t"]) / dt))
            j = i // s
            if j < 0 or j >= n_steps:
                continue
            idx, val = [], []
            for n, d in e["delta"].items():
                c = norm.col.get(int(n))
                if c is not None:
                    idx.append(c); val.append(float(d) / norm.sd_x[c])
            if idx:
                out.append({"kind": "kick", "j0": j, "j1": j + 1, "idx": np.array(idx), "val": np.array(val, np.float32), "frac": None})
            continue
        i0 = int(round(float(e["t0"]) / dt))
        i1 = n_steps * s if e.get("t1") is None else int(round(float(e["t1"]) / dt))
        i0, i1 = max(0, i0), min(n_steps * s, i1)
        if i1 <= i0:
            continue
        j0, j1 = i0 // s, (i1 - 1) // s + 1
        frac = np.array([(min(i1, (j + 1) * s) - max(i0, j * s)) / s for j in range(j0, j1)], np.float32)
        if k == "current":
            idx, val = [], []
            for n, v in e["targets"].items():
                c = norm.col.get(int(n))
                if c is not None:
                    idx.append(c); val.append(float(v) / norm.sd_x[c])
            if idx:
                out.append({"kind": "current", "j0": j0, "j1": j1, "idx": np.array(idx), "val": np.array(val, np.float32), "frac": frac})
        elif k == "silence":
            idx = [norm.col[int(n)] for n in e["targets"] if int(n) in norm.col]
            if idx:
                out.append({"kind": "silence", "j0": j0, "j1": j1, "idx": np.array(idx), "val": None, "frac": frac})
        elif k == "edge_remove":
            pairs = [(norm.col[int(a)], norm.col[int(b)]) for a, b in e["edges"] if int(a) in norm.col and int(b) in norm.col]
            if pairs:
                out.append({"kind": "edge_remove", "j0": j0, "j1": j1, "idx": np.array(pairs), "val": None, "frac": frac})
    return out


def dense_events(evs_per_window: list[list[dict]], starts: list[int], H: int, n_x: int, kinds=("kick", "current", "silence")):
    """Per-step dense event tensors for a batch of windows: {kind: (H, B, n_x) tensor} (only kinds present), and for edge removal a
    list of (step, b, pairs, frac) records."""
    B = len(starts)
    arr = {}
    edges = []
    for b, (evs, j0) in enumerate(zip(evs_per_window, starts)):
        for e in evs:
            a, c = max(e["j0"], j0), min(e["j1"], j0 + H)
            if c <= a:
                continue
            if e["kind"] == "edge_remove":
                for j in range(a, c):
                    edges.append((j - j0, b, e["idx"], float(e["frac"][j - e["j0"]])))
                continue
            if e["kind"] not in kinds:
                continue
            if e["kind"] not in arr:
                arr[e["kind"]] = np.zeros((H, B, n_x), np.float32)
            A = arr[e["kind"]]
            for j in range(a, c):
                if e["kind"] == "kick":
                    A[j - j0, b, e["idx"]] += e["val"]
                elif e["kind"] == "current":
                    A[j - j0, b, e["idx"]] += e["val"] * e["frac"][j - e["j0"]]
                else:
                    A[j - j0, b, e["idx"]] = np.maximum(A[j - j0, b, e["idx"]], e["frac"][j - e["j0"]])
    return {k: torch.from_numpy(v) for k, v in arr.items()}, edges


# ------------------------------------------------------------------------------------------------------------ compiled data
@dataclass
class SysData:
    """One system's trajectories on the internal grid (torch tensors) plus compiled events."""
    sid: str
    A: list | None   # unused (encoder features are gathered on the fly from X and the lags: feat_rows)
    X: list          # per traj (T_s, n_x) standardised x (grid)
    U: list          # per traj (T_s, n_u) step-mean standardised u
    Ui: list         # per traj (T_s, n_u) instantaneous standardised u at grid points
    Y: list          # per traj (T_s, n_y) standardised y
    EV: list         # per traj compiled events
    split: list      # "train" / "val"
    ev_starts: list = field(default_factory=list)   # (traj, grid step) of every event start in training trajectories
    lags: tuple = ()                                 # encoder history lags (internal steps)


def feat_rows(d: SysData, t: int, idx) -> torch.Tensor:
    """Encoder features [x~_j, x~_{j-l1}, ...] (edge padding at the start) for grid indices idx of trajectory t."""
    X = d.X[t]
    idx = torch.as_tensor(idx, dtype=torch.long)
    if not d.lags:
        return X[idx]
    return torch.cat([X[idx]] + [X[(idx - l).clamp(min=0)] for l in d.lags], -1)


def features_from_grid(Xg: np.ndarray, lags: tuple) -> np.ndarray:
    """[x_j, x_{j-l1}, ...] with edge padding (the first sample)."""
    if not lags:
        return Xg
    cols = [Xg]
    for l in lags:
        sh = np.concatenate([np.repeat(Xg[:1], l, 0), Xg[:-l]], 0) if l < len(Xg) else np.repeat(Xg[:1], len(Xg), 0)
        cols.append(sh)
    return np.concatenate(cols, 1)


def _grid_u(u: np.ndarray, s: int, n: int) -> np.ndarray:
    """Step-mean of the input over each internal step [j s, (j+1) s)."""
    if s == 1:
        return u[:n]
    m = len(u)
    out = np.zeros((n, u.shape[1]))
    for j in range(n):
        seg = u[j * s: min(m, (j + 1) * s)]
        out[j] = seg.mean(0) if len(seg) else u[min(m - 1, j * s)]
    return out


def compile_system(sid: str, trajs, norm: SysNorm) -> SysData:
    s = norm.stride
    d = SysData(sid=sid, A=None, X=[], U=[], Ui=[], Y=[], EV=[], split=[], lags=tuple(norm.lags))
    for ti, tr in enumerate(trajs):
        n = (len(tr.t) - 1) // s + 1
        xg = ((tr.x[:: s][:n].astype(np.float64) - norm.mu_x) / norm.sd_x)
        ug = (_grid_u(tr.u.astype(np.float64), s, n) - norm.mu_u) / norm.sd_u
        ui = (tr.u[:: s][:n].astype(np.float64) - norm.mu_u) / norm.sd_u
        yg = (tr.y[:: s][:n].astype(np.float64) - norm.mu_y) / norm.sd_y
        xt = torch.tensor(xg, dtype=torch.float32)
        d.X.append(xt)
        d.U.append(torch.tensor(ug, dtype=torch.float32))
        d.Ui.append(torch.tensor(ui, dtype=torch.float32))
        d.Y.append(torch.tensor(yg, dtype=torch.float32))
        ev = _grid_events(tr.events(), norm, n, tr.dt, s)
        d.EV.append(ev)
        d.split.append(tr.split)
        if tr.split != "val":
            for e in ev:
                d.ev_starts.append((ti, e["j0"]))
    return d


# ------------------------------------------------------------------------------------------------------------ modules
def mlp(n_in: int, n_out: int, hidden: int, depth: int = 2, act=nn.SiLU, zero_last: bool = False) -> nn.Sequential:
    layers, d = [], n_in
    for _ in range(depth):
        layers += [nn.Linear(d, hidden), act()]
        d = hidden
    last = nn.Linear(d, n_out)
    if zero_last:
        nn.init.zeros_(last.weight); nn.init.zeros_(last.bias)
    layers.append(last)
    return nn.Sequential(*layers)


class Encoder(nn.Module):
    """phi(a) = W a + b (+ MLP(a) for kind 'mlp'). W0 = the block of W acting on the current sample (first n_x features)."""

    def __init__(self, n_feat: int, n_x: int, k: int, kind: str = "linear", hidden: int = 128, stochastic: bool = False):
        super().__init__()
        self.kind, self.n_x = kind, n_x
        self.lin = nn.Linear(n_feat, k)
        nn.init.normal_(self.lin.weight, std=1.0 / math.sqrt(n_feat))
        self.net = mlp(n_feat, k, hidden, 2, zero_last=True) if kind == "mlp" else None
        self.logv = None
        if stochastic:                       # q(z | x) = N(phi(x), diag exp(logv(x))) for the predictive bottleneck
            self.logv = nn.Linear(n_feat, k)
            nn.init.zeros_(self.logv.weight)
            nn.init.constant_(self.logv.bias, -3.0)

    def sample(self, a, gen=None):
        """A reparameterised sample of q(z | a) and the per-dimension KL(q || N(0, I)) averaged over the batch."""
        mu = self.forward(a)
        lv = self.logv(a).clamp(-12.0, 4.0)
        z = mu + torch.exp(0.5 * lv) * torch.randn(mu.shape, generator=gen)
        kl = 0.5 * (mu ** 2 + lv.exp() - 1.0 - lv)
        return z, kl.reshape(-1, kl.shape[-1]).mean(0)

    def forward(self, a):
        z = self.lin(a)
        if self.net is not None:
            z = z + self.net(a)
        return z

    def W0(self):
        return self.lin.weight[:, : self.n_x]

    def delta(self, a, dx):
        """phi(a with current sample + dx) - phi(a): exact W0 dx for the linear encoder."""
        lin = dx @ self.W0().T
        if self.net is None:
            return lin
        pad = torch.zeros(dx.shape[:-1] + (a.shape[-1] - self.n_x,), dtype=dx.dtype)
        a2 = a + torch.cat([dx, pad], -1)
        return lin + self.net(a2) - self.net(a)


class Transition(nn.Module):
    """f(z, u): 'linear' z' = A z + B u + c ; 'mlp' z' = z + MLP([z, u]) ; 'ode' one RK4 step of dz/ds = MLP([z, u]) (unit step)."""

    def __init__(self, k: int, n_u: int, kind: str = "mlp", hidden: int = 64):
        super().__init__()
        self.kind, self.k, self.n_u = kind, k, n_u
        if kind == "linear":
            self.A = nn.Parameter(torch.zeros(k, k))
            self.B = nn.Parameter(torch.zeros(n_u, k))
            self.c = nn.Parameter(torch.zeros(k))
        else:
            self.net = mlp(k + n_u, k, hidden, 2, act=nn.Tanh if kind == "ode" else nn.SiLU, zero_last=True)

    def forward(self, z, u):
        if self.kind == "linear":
            return z + z @ self.A.T + u @ self.B + self.c
        if self.kind == "mlp":
            return z + self.net(torch.cat([z, u], -1))
        f = lambda zz: self.net(torch.cat([zz, u], -1))
        k1 = f(z); k2 = f(z + 0.5 * k1); k3 = f(z + 0.5 * k2); k4 = f(z + k3)
        return z + (k1 + 2 * k2 + 2 * k3 + k4) / 6.0


class Head(nn.Module):
    """System-specific parts: encoder, readout, decoder, event gains, effective couplings J (buffer)."""

    def __init__(self, n_feat: int, n_x: int, n_u: int, n_y: int, k: int, enc_kind: str, hidden: int, J: np.ndarray | None,
                 readout_kind: str = "mlp", stochastic: bool = False, gain_mode: str = "matrix", gain_init: dict | None = None,
                 silence_obs: bool = True, private: bool = False, leak: float = 0.0):
        super().__init__()
        gain_init = gain_init or {}
        # private-offset route (optional): kicks and injected currents leave a per-neuron offset xi that decays with the fitted
        # per-step leak and drives the latent through the effective couplings (g_priv W0 J xi); xi is a causal filter of the KNOWN
        # event inputs (no extra latent state)
        self.private = bool(private)
        self.register_buffer("leak", torch.tensor(float(min(max(leak, 1e-3), 1.0))))
        self.g_priv = nn.Parameter(torch.tensor(0.0))
        self.silence_obs = bool(silence_obs)      # observation-side silencing route (clamp decoded activity to rest) on / off
        self.enc = Encoder(n_feat, n_x, k, enc_kind, max(hidden, 64), stochastic)
        self.readout_kind = readout_kind
        self.ro_lin = nn.Linear(k + n_u, n_y)
        self.ro = mlp(k + n_u, n_y, hidden, 2, zero_last=True) if readout_kind == "mlp" else None
        self.dec_lin = nn.Linear(k, n_x)
        self.dec = mlp(k, n_x, max(hidden, 64), 2, zero_last=True)
        # event gains: 'matrix' = free k x k matrices (init 0); 'scalar' = gamma * I, the physically expected form for a latent that
        # is a linear readout of x (a current I adds (Delta / tau) I to x per step; removed couplings act through J per step)
        self.gain_mode = gain_mode
        if gain_mode == "scalar":
            self.g = nn.Parameter(torch.tensor([float(gain_init.get("cur", 0.0)), float(gain_init.get("so", 0.0)),
                                                float(gain_init.get("J", 1.0))]))
        else:
            self.G_cur_m = nn.Parameter(torch.zeros(k, k))
            self.G_so_m = nn.Parameter(torch.zeros(k, k))
            self.G_J_m = nn.Parameter(torch.zeros(k, k))
        self.k_lat = k
        self.register_buffer("J", torch.tensor(J if J is not None else np.zeros((n_x, n_x)), dtype=torch.float32))
        self.has_J = J is not None

    def _gain(self, i, name):
        if self.gain_mode == "scalar":
            return self.g[i] * torch.eye(self.k_lat)
        return getattr(self, name)

    @property
    def G_cur(self):
        return self._gain(0, "G_cur_m")

    @property
    def G_so(self):
        return self._gain(1, "G_so_m")

    @property
    def G_J(self):
        return self._gain(2, "G_J_m")

    def init_pca(self, X: np.ndarray):
        """Whitened-PCA initialisation of the encoder's current-sample block: z = V_k^T x~ / sqrt(lambda_k) (unit variance)."""
        k = self.enc.lin.out_features
        mu = X.mean(0)
        _, sv, Vt = np.linalg.svd(X - mu, full_matrices=False)
        lam = (sv ** 2) / max(1, len(X) - 1)
        W = np.zeros((k, self.enc.lin.in_features))
        m = min(k, Vt.shape[0])
        W[:m, : self.enc.n_x] = Vt[:m] / np.sqrt(lam[:m, None] + 1e-6)
        if m < k:
            W[m:, : self.enc.n_x] = np.random.default_rng(0).standard_normal((k - m, self.enc.n_x)) * 1e-2
        with torch.no_grad():
            self.enc.lin.weight.copy_(torch.tensor(W, dtype=torch.float32))
            self.enc.lin.bias.copy_(torch.tensor(-W[:, : self.enc.n_x] @ mu, dtype=torch.float32))

    def init_matrix(self, W_mu):
        """Initialise the encoder's linear map at W (k, F) centred at the feature mean mu."""
        W, mu = W_mu
        with torch.no_grad():
            self.enc.lin.weight.copy_(torch.tensor(W, dtype=torch.float32))
            self.enc.lin.bias.copy_(torch.tensor(-W @ mu, dtype=torch.float32))

    def readout(self, z, u):
        zu = torch.cat([z, u], -1)
        y = self.ro_lin(zu)
        if self.ro is not None:
            y = y + self.ro(zu)
        return y

    def decode(self, z):
        return self.dec_lin(z) + self.dec(z)


def n_params(m: nn.Module) -> int:
    return int(sum(p.numel() for p in m.parameters() if p.requires_grad))


# ------------------------------------------------------------------------------------------------------------ one step
def update_private(head: Head, xi, kick=None, cur=None):
    """Per-neuron private offsets of the event inputs: xi <- (1 - leak) xi + leak c~ (+ kick d~). None when inactive."""
    if not getattr(head, "private", False) or not head.has_J:
        return None
    if xi is None and kick is None and cur is None:
        return None
    ref = kick if kick is not None else cur
    xi = torch.zeros_like(ref) if xi is None else xi
    lam = head.leak
    xi = (1.0 - lam) * xi + (lam * cur if cur is not None else 0.0)
    if kick is not None:
        xi = xi + kick
    return xi


def step(head: Head, f: Transition, z, u, rest, kick=None, cur=None, sil=None, edges=None, a0=None, noise: float = 0.0,
         gen: torch.Generator | None = None, xi=None):
    """One internal step for a batch. kick / cur / sil: (B, n_x) or None; edges: list of (b, pairs (m,2), frac); a0: (B, F) the encoder
    features of the state (for the MLP encoder's kick; None = decoded state)."""
    if kick is not None:
        if head.enc.kind == "linear":
            z = z + kick @ head.enc.W0().T
        else:
            # MLP encoder: phi(a + dx) - phi(a) at the decoded state (history blocks = the decoded current sample)
            xh = head.decode(z)
            a = a0 if a0 is not None else xh.repeat_interleave(1, -1).tile(head.enc.lin.in_features // xh.shape[-1])
            z = z + head.enc.delta(a, kick)
    zn = f(z, u)
    if cur is not None:
        zn = zn + (cur @ head.enc.W0().T) @ head.G_cur.T
    if xi is not None:
        zn = zn + head.g_priv * ((xi @ head.J.T) @ head.enc.W0().T)
    # structural events (silencing, edge removal) need the decoded activity: only on the rows that have one
    rows = set()
    if sil is not None:
        rows |= set(torch.nonzero(sil.abs().sum(-1) > 0).flatten().tolist())
    if edges and head.has_J:
        rows |= {int(b) for b, _, _ in edges}
    if rows:
        ridx = torch.tensor(sorted(rows))
        pos = {int(b): i for i, b in enumerate(ridx.tolist())}
        xh = head.decode(z[ridx])
        dz = torch.zeros(len(ridx), zn.shape[-1])
        dx_struct = torch.zeros_like(xh)
        if sil is not None:
            dclamp = sil[ridx] * (rest - xh)                     # silenced neurons' activity relative to rest
            if getattr(head, "silence_obs", True):              # observation side: pull their decoded activity to rest
                dz = dz + (dclamp @ head.enc.W0().T) @ head.G_so.T
            if head.has_J:
                dx_struct = dx_struct + dclamp @ head.J.T        # remove their outgoing couplings
        if edges and head.has_J:
            for b, pairs, fr in edges:
                i = pos[int(b)]
                post, pre = torch.as_tensor(pairs[:, 0]), torch.as_tensor(pairs[:, 1])
                contrib = head.J[post, pre] * (xh[i, pre] - rest[pre]) * fr
                dx_struct[i] = dx_struct[i].index_add(0, post, -contrib)
        if head.has_J:
            dz = dz + (dx_struct @ head.enc.W0().T) @ head.G_J.T
        zn = zn.index_add(0, ridx, dz)
    if noise > 0:
        zn = zn + noise * torch.randn(zn.shape, generator=gen)
    return zn


# ------------------------------------------------------------------------------------------------------------ effective couplings
def estimate_coupling(d: SysData, graph_mask: np.ndarray | None, lam: float = 1e-2, max_rows: int = 60000) -> np.ndarray:
    """Ridge regression of grid increments x~_{j+1} - x~_j on [x~_j, u~_j, 1] over event-free steps; J = the off-diagonal part of the
    state matrix (masked by the public connectome if given). A crude, generic effective-coupling estimate used only to map removed
    synapses (silencing, edge removal) into latent drives."""
    Xs, Us, Dn = [], [], []
    for ti in range(len(d.X)):
        X, U = d.X[ti].numpy().astype(np.float64), d.U[ti].numpy().astype(np.float64)
        keep = np.ones(len(X) - 1, bool)
        for e in d.EV[ti]:
            keep[max(0, e["j0"] - 1): min(len(keep), e["j1"] + 1)] = False
        Xs.append(X[:-1][keep]); Us.append(U[:-1][keep]); Dn.append((X[1:] - X[:-1])[keep])
    X, U, D = np.concatenate(Xs), np.concatenate(Us), np.concatenate(Dn)
    if len(X) > max_rows:
        sel = np.linspace(0, len(X) - 1, max_rows).astype(int)
        X, U, D = X[sel], U[sel], D[sel]
    n = X.shape[1]
    F = np.hstack([X, U, np.ones((len(X), 1))])
    reg = lam * len(F) * np.eye(F.shape[1])
    reg[-1, -1] = 0.0
    M = np.linalg.solve(F.T @ F + reg, F.T @ D)       # (n + n_u + 1, n)
    A = M[:n].T                                       # A[post, pre]
    J = A.copy()
    np.fill_diagonal(J, 0.0)
    if graph_mask is not None:
        J = J * graph_mask
    estimate_coupling.last_leak = float(max(0.0, -np.median(np.diag(A))))     # per-step leak rate (Delta / tau)
    return J.astype(np.float32)


def graph_mask_from_entry(entry: dict, norm: SysNorm) -> np.ndarray | None:
    g = entry.get("local_graph") if isinstance(entry, dict) else None
    if not g or not isinstance(g, dict) or "edges_post_pre_signed_count" not in g:
        return None
    M = np.zeros((norm.n_x, norm.n_x), np.float32)
    for post, pre, _w in g["edges_post_pre_signed_count"]:
        a, b = norm.col.get(int(post)), norm.col.get(int(pre))
        if a is not None and b is not None and a != b:
            M[a, b] = 1.0
    return M


# ------------------------------------------------------------------------------------------------------------ the net container
class NNNet(nn.Module):
    """Heads per system + transitions (one per group of systems sharing f)."""

    def __init__(self, heads: dict, transitions: dict, f_of: dict, rest: dict, lag_max: dict):
        super().__init__()
        self.heads = nn.ModuleDict({_key(s): h for s, h in heads.items()})
        self.fs = nn.ModuleDict(transitions)
        self.f_of = dict(f_of)            # sid -> transition key
        self.rest = {_key(s): torch.tensor(np.asarray(r), dtype=torch.float32) for s, r in rest.items()}   # standardised rest
        self.lag_max = dict(lag_max)      # sid -> largest history lag (internal steps)

    def head(self, sid):
        return self.heads[_key(sid)]

    def f(self, sid):
        return self.fs[self.f_of[sid]]


def _key(sid: str) -> str:
    return sid.replace(".", "_").replace(":", "__")


# ------------------------------------------------------------------------------------------------------------ batched rollout
def rollout_batch(net: NNNet, sid: str, d: SysData, tis: list[int], j0s: list[int], H: int, noise0: float = 0.0,
                  noise: float = 0.0, gen=None, with_events: bool = True, sigma_in: float = 0.0):
    """Encode at j0 and roll out H steps with the recorded inputs and events. Returns z (H+1, B, k). sigma_in: Gaussian noise on the
    encoder input (standardised units; training only), a ridge-like regulariser that favours minimum-norm, robust encoders."""
    head, f = net.head(sid), net.f(sid)
    A0 = torch.stack([feat_rows(d, t, j) for t, j in zip(tis, j0s)])
    if sigma_in > 0:
        A0 = A0 + sigma_in * torch.randn(A0.shape, generator=gen)
    net._last_kl = None
    if head.enc.logv is not None and noise0 > 0:        # training a stochastic (bottleneck) encoder: sample z0, keep the KL
        z, net._last_kl = head.enc.sample(A0, gen)
        noise0 = 0.0
    else:
        z = head.enc(A0)
    if noise0 > 0:
        z = z + noise0 * torch.randn(z.shape, generator=gen)
    U = torch.stack([d.U[t][j: j + H] for t, j in zip(tis, j0s)], 1)        # (H, B, n_u)
    ev_d, edges = (dense_events([d.EV[t] for t in tis], j0s, H, head.enc.n_x) if with_events else ({}, []))
    rest = net.rest[_key(sid)]
    zs = [z]
    xi = None
    for h in range(H):
        e_h = [(b, p, fr) for (hh, b, p, fr) in edges if hh == h] if edges else None
        kk = ev_d["kick"][h] if "kick" in ev_d else None
        cc = ev_d["current"][h] if "current" in ev_d else None
        xi = update_private(head, xi, kk, cc)
        z = step(head, f, z, U[h], rest, kick=kk, cur=cc, sil=ev_d["silence"][h] if "silence" in ev_d else None,
                 edges=e_h, noise=noise, gen=gen, xi=xi)
        zs.append(z)
    return torch.stack(zs)


def window_targets(d: SysData, tis, j0s, H):
    Y = torch.stack([d.Y[t][j: j + H + 1] for t, j in zip(tis, j0s)], 1)
    X = torch.stack([d.X[t][j: j + H + 1] for t, j in zip(tis, j0s)], 1)
    A = torch.stack([feat_rows(d, t, torch.arange(j, j + H + 1)) for t, j in zip(tis, j0s)], 1)
    Ui = torch.stack([d.Ui[t][j: j + H + 1] for t, j in zip(tis, j0s)], 1)
    return Y, X, A, Ui


# ------------------------------------------------------------------------------------------------------------ training
DEFAULTS = dict(
    enc="linear", f_class="mlp", readout="mlp", hidden=64, lags="auto",
    iters=250, sweep_iters=250, refine_iters=100, sweep="independent", batch=256, lr=3e-3, wd=1e-5, lam_lat=0.1, lam_x=0.1,
    lam_norm=0.01,
    sigma0=0.05, sigma_step=0.01, horizon_frac=0.25, max_horizon=150, ev_frac=0.35, eval_every=25,
    val_starts=4, use_J=True, gain_mode="scalar", enc_init="pca", sigma_in=0.0, lam_W=0.0,
)


def _sample_windows(d: SysData, rng: np.random.Generator, B: int, H: int, lag_max: int, ev_frac: float, train_idx: list[int]):
    tis, j0s = [], []
    n_ev = int(round(B * ev_frac)) if d.ev_starts else 0
    for _ in range(n_ev):
        t, j = d.ev_starts[rng.integers(len(d.ev_starts))]
        T = len(d.X[t])
        j0 = int(np.clip(j - rng.integers(0, max(1, H // 4)), 0, T - H - 1))
        tis.append(t); j0s.append(j0)
    for _ in range(B - n_ev):
        t = train_idx[rng.integers(len(train_idx))]
        T = len(d.X[t])
        j0s.append(int(rng.integers(min(lag_max, T - H - 2), T - H - 1))); tis.append(t)
    return tis, j0s


def window_loss(net: NNNet, sid: str, d: SysData, tis, j0s, H: int, cfg: dict, gen, train: bool = True):
    zs = rollout_batch(net, sid, d, tis, j0s, H, cfg["sigma0"] if train else 0.0, cfg["sigma_step"] if train else 0.0, gen,
                       sigma_in=cfg.get("sigma_in", 0.0) if train else 0.0)
    Y, X, A, Ui = window_targets(d, tis, j0s, H)
    head = net.head(sid)
    yp = head.readout(zs, Ui)
    ly = ((yp - Y) ** 2).mean()
    if not train:
        return ly, None
    with torch.no_grad():
        zt = head.enc(A)
        var = zt.reshape(-1, zt.shape[-1]).var(0) + 1e-4
    dw = cfg.get("_dimw")                # per-dimension weights of the latent terms (ramp-in of dimensions added by the sweep)
    if dw is None:
        dw = torch.ones(zs.shape[-1])
    llat = ((((zs[1:] - zt[1:]) ** 2) / var) * dw).mean()
    lx = ((head.decode(zs) - X) ** 2).mean()
    ze = head.enc(A[0])
    lnorm = ((ze.mean(0) ** 2 + (ze.var(0) - 1.0) ** 2) * dw).sum() if len(ze) > 2 else ze.new_zeros(())
    lw = (head.enc.lin.weight ** 2).sum() if cfg.get("lam_W", 0.0) > 0 else 0.0
    loss = ly + cfg["lam_lat"] * llat + cfg["lam_x"] * lx + cfg["lam_norm"] * lnorm + cfg.get("lam_W", 0.0) * lw
    if getattr(net, "_last_kl", None) is not None:
        loss = loss + cfg.get("beta", 0.0) * net._last_kl.sum()
    return loss, ly


def val_score(net: NNNet, sid: str, d: SysData, H: int, n_starts: int, lag_max: int, idx: list[int]) -> np.ndarray:
    """Per-trajectory open-loop readout NMSE (standardised y ~ the evaluator's NMSE) over H internal steps from n_starts evenly spaced
    start points, events included. Deterministic."""
    out = []
    with torch.no_grad():
        for t in idx:
            T = len(d.X[t])
            lo, hi = min(lag_max + 1, T - H - 1), T - H - 1
            if hi <= lo:
                continue
            j0s = list(np.linspace(lo, hi, n_starts).astype(int))
            tis = [t] * len(j0s)
            zs = rollout_batch(net, sid, d, tis, j0s, H)
            Y, _, _, Ui = window_targets(d, tis, j0s, H)
            yp = net.head(sid).readout(zs, Ui)
            out.extend(((yp[1:] - Y[1:]) ** 2).mean(dim=(0, 2)).tolist())      # one unit per (trajectory, start)
    return np.array(out)


def train_net(net: NNNet, datas: dict, cfg: dict, seed: int, deadline: float | None = None, trainable=None, log=None) -> dict:
    """Train all systems in `datas` jointly (batches cycle through systems). Early stopping on the mean validation score."""
    gen = torch.Generator().manual_seed(int(seed))
    rng = np.random.default_rng(int(seed))
    params = [p for p in (trainable if trainable is not None else net.parameters()) if p.requires_grad]
    opt = torch.optim.AdamW(params, lr=cfg["lr"], weight_decay=cfg["wd"])
    iters = int(cfg["iters"])
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg["lr"], total_steps=iters, pct_start=0.1)
    sids = list(datas)
    info = {}
    for sid in sids:
        d = datas[sid]
        T = min(len(x) for x in d.X)
        lag_max = net.lag_max.get(sid, 0)
        H = int(max(4, min(cfg["max_horizon"], round(cfg["horizon_frac"] * T), T - lag_max - 3)))
        tr_idx = [i for i, s in enumerate(d.split) if s != "val"] or list(range(len(d.X)))
        va_idx = [i for i, s in enumerate(d.split) if s == "val"] or tr_idx[: max(1, len(tr_idx) // 5)]
        info[sid] = dict(H=H, lag_max=lag_max, tr=tr_idx, va=va_idx)
    best, best_state, hist = np.inf, None, []
    if cfg.get("eval_initial"):          # refinement of an already trained net: never end worse than the starting point
        net.eval()
        best = float(np.mean([val_score(net, s, datas[s], info[s]["H"], cfg["val_starts"], info[s]["lag_max"], info[s]["va"]).mean()
                              for s in sids]))
        best_state = copy.deepcopy(net.state_dict())
    for it in range(iters):
        sid = sids[it % len(sids)]
        d, inf = datas[sid], info[sid]
        # horizon curriculum: from H/8 to H over the first 40 % of training (not for continued training of a trained net)
        frac = 1.0 if cfg.get("no_curriculum") else min(1.0, it / max(1, 0.4 * iters))
        if cfg.get("grow_from") is not None:     # dimensions added by the sweep: their latent terms ramp in over half the run
            kk = next(iter(net.heads.values())).enc.lin.out_features
            dw = torch.ones(kk)
            dw[int(cfg["grow_from"]):] = min(1.0, it / max(1, 0.5 * iters))
            cfg["_dimw"] = dw
        H = int(max(2, round(inf["H"] * (0.125 + 0.875 * frac))))
        tis, j0s = _sample_windows(d, rng, cfg["batch"], H, inf["lag_max"], cfg["ev_frac"], inf["tr"])
        net.train()
        loss, _ = window_loss(net, sid, d, tis, j0s, H, cfg, gen)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(params, 1.0)
        opt.step(); sched.step()
        last = it == iters - 1
        if (it + 1) % cfg["eval_every"] == 0 or last or (deadline is not None and time.time() > deadline):
            net.eval()
            sc = float(np.mean([val_score(net, s, datas[s], info[s]["H"], cfg["val_starts"], info[s]["lag_max"], info[s]["va"]).mean()
                                for s in sids]))
            hist.append((it + 1, sc))
            if log:
                log(f"  it {it + 1} H {H} loss {float(loss.detach()):.4f} val {sc:.4f}")
            if np.isfinite(sc) and sc < best:
                best, best_state = sc, copy.deepcopy(net.state_dict())
            if deadline is not None and time.time() > deadline:
                break
    if best_state is not None:
        net.load_state_dict(best_state)
    net.eval()
    return {"best_val": best, "history": hist, "info": info}


# ------------------------------------------------------------------------------------------------------------ the state model
class NNStateModel(StateModel):
    """Executable model of the nn family (closed latent dynamics)."""

    closed = True

    def __init__(self, net: NNNet, norms: dict, k: int, meta: dict):
        self.net = net
        self.norms = norms               # sid -> SysNorm
        self.k = {s: int(k) for s in norms}
        self.meta = meta
        self.net.eval()

    # --- encoder
    def _features(self, sid, x_hist) -> torch.Tensor:
        nm = self.norms[sid]
        s = nm.stride
        x = (np.asarray(x_hist, np.float64) - nm.mu_x) / nm.sd_x
        i = len(x) - 1
        cols = [x[i]]
        for l in nm.lags:
            cols.append(x[max(0, i - l * s)])
        return torch.tensor(np.concatenate(cols), dtype=torch.float32)

    def encode(self, system_id, x_hist, u_hist, dt):
        with torch.no_grad():
            return self.net.head(system_id).enc(self._features(system_id, x_hist)[None])[0].numpy().astype(np.float64)

    # --- readout
    def readout(self, system_id, z, u):
        nm = self.norms[system_id]
        z = np.asarray(z, np.float64)
        u = np.asarray(u, np.float64)
        shp = z.shape[:-1]
        zt = torch.tensor(z.reshape(-1, z.shape[-1]), dtype=torch.float32)
        ut = torch.tensor(((u.reshape(-1, u.shape[-1]) - nm.mu_u) / nm.sd_u), dtype=torch.float32)
        with torch.no_grad():
            y = self.net.head(system_id).readout(zt, ut).numpy().astype(np.float64)
        y = y * nm.sd_y + nm.mu_y
        y = np.maximum(y, nm.y_min)
        return y.reshape(shp + (nm.n_y,))

    def supports(self, system_id, event_kind):
        h = self.net.head(system_id)
        if event_kind in ("kick", "current", "silence"):
            return True
        if event_kind == "edge_remove":
            return bool(h.has_J)
        return False

    # --- rollout
    def rollout(self, system_id, z0, u_future, events, dt):
        nm = self.norms[system_id]
        s = nm.stride
        u_future = np.asarray(u_future, np.float64)
        H = len(u_future) - 1
        n_steps = int(math.ceil(H / s)) if H > 0 else 0
        # pad inputs to a whole number of internal steps
        need = n_steps * s + 1
        uf = u_future if len(u_future) >= need else np.vstack([u_future, np.repeat(u_future[-1:], need - len(u_future), 0)])
        ug = torch.tensor((_grid_u(uf, s, n_steps + 1) - nm.mu_u) / nm.sd_u, dtype=torch.float32)
        evs = _grid_events(events, nm, n_steps + 1, dt, s)
        ev_d, edges = dense_events([evs], [0], max(1, n_steps), nm.n_x, kinds=("kick", "current", "silence"))
        head, f = self.net.head(system_id), self.net.f(system_id)
        rest = self.net.rest[_key(system_id)]
        z = torch.tensor(np.asarray(z0, np.float64), dtype=torch.float32)[None]
        zs = [z]
        xi = None
        with torch.no_grad():
            for j in range(n_steps):
                e_h = [(0, p, fr) for (hh, b, p, fr) in edges if hh == j] if edges else None
                kk = ev_d["kick"][j] if "kick" in ev_d else None
                cc = ev_d["current"][j] if "current" in ev_d else None
                xi = update_private(head, xi, kk, cc)
                z = step(head, f, z, ug[j][None], rest, kick=kk, cur=cc, sil=ev_d["silence"][j] if "silence" in ev_d else None,
                         edges=e_h, xi=xi)
                if not torch.isfinite(z).all():
                    z = torch.nan_to_num(z, nan=0.0, posinf=1e3, neginf=-1e3).clamp(-1e3, 1e3)
                zs.append(z)
        Zg = torch.cat(zs).numpy().astype(np.float64)                 # (n_steps + 1, k) on the grid
        if s == 1:
            Z = Zg[: H + 1]
        else:
            tt = np.arange(H + 1) / s
            j = np.minimum(np.floor(tt).astype(int), len(Zg) - 2) if len(Zg) > 1 else np.zeros(H + 1, int)
            w = (tt - j)[:, None]
            Z = Zg[j] * (1 - w) + Zg[np.minimum(j + 1, len(Zg) - 1)] * w if len(Zg) > 1 else np.repeat(Zg, H + 1, 0)
        return {"z": Z, "y": self.readout(system_id, Z, u_future[: H + 1])}

    # --- lifting: minimum-norm kicks (through the linear part of the encoder) that realise delta_z
    def lift(self, system_id, x, z, delta_z, n_candidates=3):
        nm = self.norms[system_id]
        W0 = self.net.head(system_id).enc.W0().detach().numpy().astype(np.float64)       # (k, n_x) in x~ units
        Wx = W0 / nm.sd_x[None, :]                                                        # per raw unit
        out = []
        rng = np.random.default_rng(0)
        n = Wx.shape[1]
        subsets = [np.arange(n)]
        for _ in range(max(0, n_candidates - 1)):
            m = max(Wx.shape[0] + 1, n // 2)
            subsets.append(np.sort(rng.choice(n, size=min(n, m), replace=False)))
        for sub in subsets[:n_candidates]:
            Ws = Wx[:, sub]
            d = Ws.T @ np.linalg.lstsq(Ws @ Ws.T + 1e-9 * np.eye(Ws.shape[0]), np.asarray(delta_z, np.float64), rcond=None)[0]
            delta = {str(nm.observed[i]): float(v) for i, v in zip(sub, d) if abs(v) > 1e-12}
            if delta:
                out.append([{"kind": "kick", "t": 0.0, "delta": delta}])
        return out

    def info(self):
        return dict(self.meta)


def lipschitz_bound(net: NNNet) -> float:
    """Product of spectral norms of the encoder's linear map (x~ units) - reported for the dimension-cheating guard."""
    vals = []
    for h in net.heads.values():
        vals.append(float(torch.linalg.matrix_norm(h.enc.lin.weight.detach(), ord=2)))
    return float(max(vals)) if vals else float("nan")
