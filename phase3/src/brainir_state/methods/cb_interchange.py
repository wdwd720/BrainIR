"""cb_interchange: interchange-intervention-trained causal abstraction (IIT / DAS adapted to dynamics; family E, method 1).

Model (cb_core.CBModel): orthonormal linear encoder z = W xs (DAS-style rotation, W = first k rows of an orthogonal matrix), residual
transition z' = z + A z + B u + b + sz MLP([z/sz, u]), readout y = C z + D u + e + MLP_g, and the structural event operators of
cb_core (kick: z += W delta; current: z += G W I; silence / edge removal through the latent-projected coupling K).

Objective (per mini-batch of training windows of H internal steps, all terms normalised):

  L = L_pred + lam_int L_int + lam_null L_null + lam_x L_x

  L_pred   multi-horizon readout loss  mean_h || g(f^h(z_t, u, events)) - y_{t+h} ||^2 / var(y)
           + latent self-consistency   mean_h || f^h(z_t) - W xs_{t+h} ||^2 / var(z)            (f^h commutes with the encoder)
  L_int    INTERCHANGE loss. A base window (state x_b at time t, input u_b) receives the abstract intervention
           "set the S-coordinates of z to those of a source state x_s": z* = z_b + P_S W (x_s - x_b). Its REALISER is a state offset
           of the microstate, delta = x_s - x_b, which the training data contain as recorded interventions: every recorded kick is
           a realised state offset delta (z* = z_b + W delta), every current / silencing window a realised input / structural
           intervention. The loss is the multi-horizon loss of the window with the realiser applied, i.e. the abstract model after
           the latent patch must reproduce the microscopic future after the realiser (g(f^h(z*)) vs y*_{t+h}, f^h(z*) vs
           phi(x*_{t+h})). Intervention windows are over-sampled (half of each batch when available). With a simulator
           (optional, `sim`), cb_cegar adds realisers of chosen latent shifts (several distinct realisers per shift).
  L_null   NULL-SPACE FAITHFULNESS. A realiser's component in the null space of W, (I - W^T W) delta, must not change the future.
           For recorded state offsets this is part of L_int (the model ignores the null component; a mismatch rotates W). In
           addition, pairs of training states that agree in z but differ in the null space are pushed to agree in their predicted
           residual: the rollout residual e_h = y_{t+h} - g(f^h(z_t)) must not be linearly predictable from the null-space residual
           r_t = top PCs of (I - W^T W) xs_t (a ridge probe fitted on the batch; penalty = explained fraction of e). This is the
           training-time version of the closure test (family D of the protocol).
  L_x      low-weight reconstruction of the top microstate PCs from z (keeps W on high-variance directions; anti-collapse).

The encoder is initialised with the rank-k predictive-state (RRR) subspace of cb_psr, the linear parts of f and g by least squares.
Validation = the given validation trajectories plus every trajectory of a seeded quarter of the parameter draws (cb_psr.split_train_val):
selection measures generalisation to NEW draws.

Dimension rule (generic, pre-registered): the cb_psr rule (spectral count / cross-validated plateau of the predictive-state
regression, then the model-based step: the smallest of k_rule..k_rule+2 whose complete closed-form model has a validation rollout
error within 10 % of the best). Option k_rule='sweep': fit the interchange model at k = k_psr - 1, ..., until two past the running
minimum of its validation loss and take the smallest k within 1.10 min + 0.005 (more expensive and, on the public dev suite, less
stable: runs/cb/results/ic_v2.jsonl).
Validated fallback: at the selected k the closed-form cb_psr model (same encoder subspace, same split) is fitted too and kept if its
validation loss is lower. Abstention: the PSR spectrum has no gap (cb_psr rule), or the sweep does not plateau before k_max, or
k > N/5 (not on keep-only mechanism systems) -> "no compact state"; the validation intervention loss worse than predicting no effect
-> "causal_equivalence_failed" (observational state only).

lift(): a latent shift dz is realised by kicks delta with W (delta / s) = dz (minimum norm over all units, and over two disjoint unit
halves: three distinct realisers of one latent intervention).
"""

from __future__ import annotations

import math

import numpy as np

from ..api import StateMethod, register
from . import cb_core as C
from . import cb_psr as P


# ================================================================================================================ torch model
def _torch():
    import torch
    return torch


class TorchCB:
    """Differentiable twin of CBModel for one system (training only; exported to numpy)."""

    def __init__(self, N, k, nu, ny, W0, hidden=64, hidden_g=32, seed=0, sz=1.0, base_s=None, mu_over_s=None, kappa=0.1, n_units=None):
        torch = _torch()
        self.n_units = int(n_units if n_units is not None else N)
        g = torch.Generator().manual_seed(seed)
        self.N, self.k, self.nu, self.ny = N, k, nu, ny
        f64 = torch.float32

        def P_(*shape, scale=0.0):
            t = torch.randn(*shape, generator=g, dtype=f64) * scale
            return t.requires_grad_(True)

        # encoder: W = first k rows of the orthonormalised [W0; noise]
        self.Wraw = torch.tensor(W0.T.copy(), dtype=f64).requires_grad_(True)       # (N, k)
        self.A = P_(k, k)
        self.B = P_(k, nu)
        self.b = P_(k)
        self.l1 = P_(hidden, k + nu, scale=1.0 / math.sqrt(k + nu))
        self.c1 = P_(hidden)
        self.l2 = P_(hidden, hidden, scale=1.0 / math.sqrt(hidden))
        self.c2 = P_(hidden)
        self.l3 = P_(k, hidden, scale=0.01 / math.sqrt(hidden))
        self.c3 = P_(k)
        # readout
        self.C = P_(ny, k, scale=0.1)
        self.D = P_(ny, nu)
        self.e = P_(ny)
        self.g1 = P_(hidden_g, k + nu, scale=1.0 / math.sqrt(k + nu))
        self.h1 = P_(hidden_g)
        self.g2 = P_(ny, hidden_g, scale=0.01 / math.sqrt(hidden_g))
        self.h2 = P_(ny)
        # events: scalar current gain (learned); unit leak kappa and silenced baseline fixed (estimated from the units' traces)
        self.g_cur = torch.tensor(0.0, dtype=f64).requires_grad_(True)
        self.kappa = float(kappa)
        self.sz = float(sz)
        self.base_s = torch.tensor(base_s if base_s is not None else np.zeros(self.n_units), dtype=f64)
        self.mu_over_s = torch.tensor(mu_over_s if mu_over_s is not None else np.zeros(self.n_units), dtype=f64)
        # latent gauge of this system (shared-dynamics fits): z = R W xs; fixed identity for a single system
        self.R = torch.eye(k, dtype=f64)
        self.free_gauge = False

    SHARED = ("A", "B", "b", "l1", "c1", "l2", "c2", "l3", "c3")

    def tie(self, other: "TorchCB", share_B: bool = True):
        """Use the transition tensors of `other` (one f for several systems)."""
        for name in self.SHARED:
            if name == "B" and not share_B:
                continue
            setattr(self, name, getattr(other, name))
        self.sz = other.sz

    def set_free_gauge(self):
        torch = _torch()
        self.R = torch.eye(self.k, dtype=torch.float32).requires_grad_(True)
        self.free_gauge = True

    def enc(self):
        W = self.W()
        return W if not self.free_gauge else self.R @ W

    def dec(self, E=None):
        W = self.W()
        if not self.free_gauge:
            return W.T
        return W.T @ _torch().linalg.inv(self.R)

    def params(self, which="all"):
        enc = [self.Wraw] + ([self.R] if self.free_gauge else [])
        dyn = [self.A, self.B, self.b, self.l1, self.c1, self.l2, self.c2, self.l3, self.c3]
        ro = [self.C, self.D, self.e, self.g1, self.h1, self.g2, self.h2]
        ev = [self.g_cur]
        return {"all": enc + dyn + ro + ev, "enc": enc, "dyn": dyn, "ro": ro, "ev": ev}[which]

    def W(self):
        torch = _torch()
        q, r = torch.linalg.qr(self.Wraw)
        # fix the sign ambiguity of QR so that W is a smooth function of Wraw
        s = torch.sign(torch.diagonal(r))
        s = torch.where(s == 0, torch.ones_like(s), s)
        return (q * s).T                                              # (k, N)

    def f(self, z, u):
        torch = _torch()
        h = torch.cat([z / self.sz, u], -1)
        a = torch.tanh(h @ self.l1.T + self.c1)
        a = torch.tanh(a @ self.l2.T + self.c2)
        return z + z @ self.A.T + u @ self.B.T + self.b + self.sz * (a @ self.l3.T + self.c3)

    def g(self, z, u):
        torch = _torch()
        h = torch.cat([z / self.sz, u], -1)
        return z @ self.C.T + u @ self.D.T + self.e + torch.tanh(h @ self.g1.T + self.h1) @ self.g2.T + self.h2

    def rollout(self, E, Wd, z, U, kick, cur, sil):
        n = self.n_units
        return self._rollout(E[:, :n], Wd[:n], z, U, kick, cur, sil)

    def _rollout(self, E, Wd, z, U, kick, cur, sil):
        """z (B,k); U (B,H+1,nu); kick/cur/sil (B,H,N) or None; E encoder (k,N), Wd decoder (N,k). Returns Z (B,H+1,k).
        Same operators as CBModel.step."""
        torch = _torch()
        Zs = [z]
        H = U.shape[1] - 1
        kap = self.kappa
        for h in range(H):
            if kick is not None:
                z = z + kick[:, h] @ E.T
            if sil is not None:
                s = sil[:, h]
                q = z @ Wd.T
                zn = self.f(z - (s * q) @ E.T, U[:, h]) + (s * ((1 - kap) * q + kap * self.base_s)) @ E.T
            else:
                zn = self.f(z, U[:, h])
            if cur is not None:
                zn = zn + self.g_cur * (cur[:, h] @ E.T)
            z = zn
            Zs.append(z)
        return torch.stack(Zs, 1)

    def export(self, model: C.CBModel, sid: str):
        torch = _torch()
        with torch.no_grad():
            S = model.sys[sid]
            S["W"] = self.enc().double().numpy().copy()
            S["Wd"] = None if not self.free_gauge else self.dec().double().numpy().copy()
            S["B"] = self.B.double().numpy().copy()
            model.trans = {"A": self.A.double().numpy().copy(), "b": self.b.double().numpy().copy(), "sz": self.sz,
                           "mlp": [(self.l1.double().numpy().copy(), self.c1.double().numpy().copy()),
                                   (self.l2.double().numpy().copy(), self.c2.double().numpy().copy()),
                                   (self.l3.double().numpy().copy(), self.c3.double().numpy().copy())], "rff": None}
            S["ro"] = {"C": self.C.double().numpy().copy(), "D": self.D.double().numpy().copy(),
                       "e": (self.e + self.h2).double().numpy().copy(),
                       "mlp": [(self.g1.double().numpy().copy(), self.h1.double().numpy().copy()),
                               (self.g2.double().numpy().copy(), np.zeros(self.ny))], "rff": None}
            model.ev = {"kappa": self.kappa, "g_cur": float(max(0.0, self.g_cur.item()))}

    def load_transition(self, model: C.CBModel, sid_ref: str):
        """Copy a fitted (numpy) transition into this net and freeze it (encoder-only adaptation)."""
        torch = _torch()
        T = model.trans
        vals = {"A": T["A"], "b": T["b"], "B": model.sys[sid_ref]["B"], "l1": T["mlp"][0][0], "c1": T["mlp"][0][1],
                "l2": T["mlp"][1][0], "c2": T["mlp"][1][1], "l3": T["mlp"][2][0], "c3": T["mlp"][2][1]}
        for name, v in vals.items():
            if name == "B" and v.shape != tuple(self.B.shape):
                continue
            setattr(self, name, torch.tensor(np.asarray(v), dtype=torch.float32))
        self.sz = float(T["sz"])


# ================================================================================================================ batches
class WindowSampler:
    """Training windows of H internal steps; windows that contain events are over-sampled (interchange realisers)."""

    def __init__(self, bins: list[C.Binned], H: int, seed: int):
        self.bins, self.H = bins, H
        self.rng = np.random.default_rng(seed)
        self.free, self.event = [], []
        for bi, b in enumerate(bins):
            for m in range(0, b.M - H + 1):
                (self.event if b.ev_bins[m: m + H].any() else self.free).append((bi, m))
        self.free = np.array(self.free, int).reshape(-1, 2)
        self.event = np.array(self.event, int).reshape(-1, 2)

    def sample(self, n: int, H: int, frac_event: float = 0.5):
        ne = int(round(n * frac_event)) if len(self.event) else 0
        nf = n - ne
        rows = []
        if nf:
            rows.append(self.free[self.rng.integers(0, len(self.free), nf)] if len(self.free) else self.event[self.rng.integers(0, len(self.event), nf)])
        if ne:
            rows.append(self.event[self.rng.integers(0, len(self.event), ne)])
        rows = np.concatenate(rows)
        # a shorter horizon (curriculum): random start inside the long window keeps events
        return rows, H

    def tensors(self, rows, H, N):
        torch = _torch()
        B = len(rows)
        X0 = np.stack([self.bins[b].xs[m] for b, m in rows])
        U = np.stack([self.bins[b].u[m: m + H + 1] for b, m in rows])
        Y = np.stack([self.bins[b].y[m + 1: m + H + 1] for b, m in rows])
        XF = np.stack([self.bins[b].xs[m + 1: m + H + 1] for b, m in rows])
        kick = cur = sil = None
        for r, (b, m) in enumerate(rows):
            bb = self.bins[b]
            if not bb.ev_bins[m: m + H].any():
                continue
            for mm, c, d in bb.kicks:
                if m <= mm < m + H:
                    if kick is None:
                        kick = np.zeros((B, H, N))
                    kick[r, mm - m, c] += d
            for a, e, c, v in bb.cur:
                lo, hi = max(a, m), min(e, m + H)
                if lo < hi:
                    if cur is None:
                        cur = np.zeros((B, H, N))
                    cur[r, lo - m: hi - m, c] += v
            for a, e, c in bb.sil:
                lo, hi = max(a, m), min(e, m + H)
                if lo < hi:
                    if sil is None:
                        sil = np.zeros((B, H, N))
                    sil[r, lo - m: hi - m, c] = 1.0
        tt = lambda a: None if a is None else torch.tensor(a, dtype=torch.float32)  # noqa: E731
        return tt(X0), tt(U), tt(Y), tt(XF), tt(kick), tt(cur), tt(sil)


# ================================================================================================================ training
def make_net(prep: C.Prep, btr, W0, seed, cfg):
    N, k = W0.shape[1], W0.shape[0]
    nu, ny = btr[0].u.shape[1], btr[0].y.shape[1]
    Z = np.concatenate([b.xs for b in btr]) @ W0.T
    sz = float(np.sqrt(np.mean(Z.var(0))) + 1e-6)
    leak = C.fit_unit_leak(btr, prep, W0)
    return TorchCB(N, k, nu, ny, W0, hidden=cfg["hidden"], seed=seed, sz=sz, base_s=C.base_state(prep, leak), mu_over_s=prep.mu / prep.s,
                   kappa=leak["kappa"], n_units=prep.n_units)


def train_cb(prep: C.Prep, btr, bva, W0, H, seed, cfg: dict, pcs: np.ndarray, freeze: dict | None = None, init: TorchCB | None = None):
    """Train a TorchCB for one system from the encoder W0 (k x N)."""
    _torch().manual_seed(seed)
    net = init or make_net(prep, btr, W0, seed, cfg)
    if init is None:
        linear_init(net, btr, W0)
    train_multi([net], [btr], [pcs], H, seed, cfg, freeze_dyn=bool(freeze and freeze.get("dyn")))
    return net


def _unique(params):
    out, seen = [], set()
    for p_ in params:
        if id(p_) not in seen and p_.requires_grad:
            seen.add(id(p_))
            out.append(p_)
    return out


def train_multi(nets: list, bins_list: list, pcs_list: list, H: int, seed: int, cfg: dict, freeze_dyn: bool = False):
    """Joint training of several systems' nets (their transition tensors may be tied: one f). Per iteration every system
    contributes one mini-batch; loss = sum over systems of the per-system objective of the module docstring."""
    torch = _torch()
    torch.manual_seed(seed)
    samplers = [WindowSampler(b, H, seed + 7 * i) for i, b in enumerate(bins_list)]
    pcs_t = [torch.tensor(p_, dtype=torch.float32) for p_ in pcs_list]
    mlp_w = _unique([t for n in nets for t in (n.l1, n.l2, n.l3, n.g1, n.g2)])
    if freeze_dyn:
        for n in nets:
            for p_ in n.params("dyn"):
                p_.requires_grad_(False)
        mlp_w = _unique([t for n in nets for t in (n.g1, n.g2)])
    ids = {id(p_) for p_ in mlp_w}
    enc = _unique([p_ for n in nets for p_ in n.params("enc")])
    rest = _unique([p_ for n in nets for p_ in n.params("dyn") + n.params("ro") + n.params("ev") if id(p_) not in ids])
    rest = [p_ for p_ in rest if id(p_) not in {id(q) for q in enc}]
    groups = [g_ for g_ in ({"params": enc, "lr": cfg["lr_enc"], "weight_decay": 0.0},
                            {"params": rest, "lr": cfg["lr"], "weight_decay": 0.0},
                            {"params": mlp_w, "lr": cfg["lr"], "weight_decay": cfg["wd"]}) if g_["params"]]
    if cfg.get("freeze_enc"):
        for n in nets:
            n.Wraw.requires_grad_(False)
        groups = [g_ for g_ in groups if g_["params"] is not enc]
    opt = torch.optim.AdamW(groups)
    gen = torch.Generator().manual_seed(seed + 101)
    n_short, n_long = cfg["steps"], cfg["steps_long"]
    steps = n_short + n_long
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=[g_["lr"] for g_ in groups], total_steps=steps, pct_start=0.15)
    H_short = int(min(H, cfg["h_short"]))
    all_params = [p_ for g_ in groups for p_ in g_["params"]]
    for it in range(steps):
        # multiple shooting: short windows (latent self-consistency ties them together), then full-horizon windows
        Hc = H_short if it < n_short else H
        loss = 0.0
        for net, sam, pt in zip(nets, samplers, pcs_t):
            loss = loss + _loss_one(net, sam, pt, Hc, H, it, cfg, gen, it < n_short)
        opt.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(all_params, 1.0)
        opt.step()
        sched.step()
    return nets


def _loss_one(net, sam, pcs_t, Hc, H, it, cfg, gen, short):
    torch = _torch()
    N, k = net.N, net.k
    rows, _ = sam.sample(cfg["batch"] if short else cfg["batch_long"], H, cfg["frac_event"])
    X0, U, Y, XF, kick, cur, sil = sam.tensors(rows, Hc, net.n_units)
    E = net.enc()
    Wd = net.dec()
    sz = net.sz
    z0 = X0 @ E.T
    if cfg["z_noise"] > 0:
        # latent noise injection (dimension-cheating guard / smoothness of f around the data)
        z0 = z0 + cfg["z_noise"] * sz * torch.randn(z0.shape, generator=gen)
    Zr = net.rollout(E, Wd, z0, U, kick, cur, sil)[:, 1:]
    Yp = net.g(Zr, U[:, 1:])
    l_y = ((Yp - Y) ** 2).mean()
    Zt = XF @ E.T
    l_z = ((Zr - Zt) ** 2).mean() / (sz ** 2)
    loss = l_y + cfg["lam_z"] * l_z
    if cfg["lam_x"] > 0:
        PCt = XF @ pcs_t.T                                           # (B,H,P)
        Zf = Zr.reshape(-1, k)
        Pf = PCt.reshape(-1, PCt.shape[-1])
        Z1 = torch.cat([Zf, torch.ones(len(Zf), 1)], 1)
        sol = torch.linalg.lstsq(Z1.detach(), Pf).solution
        l_x = ((Z1 @ sol - Pf) ** 2).mean() / (Pf.var(0).mean() + 1e-9)
        loss = loss + cfg["lam_x"] * l_x
    if cfg["lam_null"] > 0 and it % 2 == 0:
        # null-space faithfulness: rollout residual must not be predictable from the null-space residual of x_t
        W = net.W()
        Rn = X0 - (X0 @ W.T) @ W                                    # (B,N)
        Rp = Rn @ pcs_t.T                                           # (B,P)
        E_ = (Y - Yp).reshape(len(rows), -1)                         # (B, H*ny)
        Rp1 = torch.cat([Rp, torch.ones(len(Rp), 1)], 1)
        lamI = 1e-1 * (Rp1.T @ Rp1).trace() / Rp1.shape[1]
        sol = torch.linalg.solve(Rp1.T @ Rp1 + lamI * torch.eye(Rp1.shape[1]), Rp1.T @ E_)
        expl = ((Rp1 @ sol) ** 2).sum() / ((E_ - E_.mean(0)) ** 2).sum().clamp_min(1e-9)
        loss = loss + cfg["lam_null"] * expl * l_y.detach()
    return loss


def linear_init(net: TorchCB, btr, W0):
    """Least-squares linear transition (free steps) and readout for the initial encoder: the MLP then learns a correction."""
    torch = _torch()
    Z0, U0, Z1, Za, Ua, Ya = [], [], [], [], [], []
    for b in btr:
        z = b.xs @ W0.T
        i = np.flatnonzero(~b.ev_bins)
        Z0.append(z[i]); U0.append(b.u[i]); Z1.append(z[i + 1])
        Za.append(z); Ua.append(b.u); Ya.append(b.y)
    Z0, U0, Z1 = np.concatenate(Z0), np.concatenate(U0), np.concatenate(Z1)
    k, nu = Z0.shape[1], U0.shape[1]
    F = np.hstack([Z0, U0, np.ones((len(Z0), 1))])
    M = C.ridge_solve(F, Z1 - Z0, 1e-6)
    Za, Ua, Ya = np.concatenate(Za), np.concatenate(Ua), np.concatenate(Ya)
    Fy = np.hstack([Za, Ua, np.ones((len(Za), 1))])
    R = C.ridge_solve(Fy, Ya, 1e-6)
    with torch.no_grad():
        net.A.copy_(torch.tensor(M[:k].T, dtype=torch.float32))
        net.B.copy_(torch.tensor(M[k: k + nu].T, dtype=torch.float32))
        net.b.copy_(torch.tensor(M[k + nu], dtype=torch.float32))
        net.C.copy_(torch.tensor(R[:k].T, dtype=torch.float32))
        net.D.copy_(torch.tensor(R[k: k + nu].T, dtype=torch.float32))
        net.e.copy_(torch.tensor(R[k + nu], dtype=torch.float32))
        net.l3.mul_(0.0)
        net.g2.mul_(0.0)


def val_loss_np(model: C.CBModel, sid: str, bva, H: int, n_starts: int = 6):
    """Validation losses of the exported model: event-free windows (A-like) and event windows (post-event NMSE)."""
    free, ev = [], []
    for b in bva:
        if b.M <= H + 1:
            continue
        starts = np.linspace(0, b.M - H - 1, n_starts).astype(int)
        for m0 in starts:
            z = model.sys[sid]["W"] @ b.xs[m0]
            Zs = P._rollout_binned(model, sid, z, b, m0, H, True)
            yp = model.readout_n(sid, Zs[1:], b.u[m0 + 1: m0 + H + 1])
            e = float(np.mean((yp - b.y[m0 + 1: m0 + H + 1]) ** 2))
            (ev if b.ev_bins[m0: m0 + H].any() else free).append(e)
    fv = float(np.mean(free)) if free else float("nan")
    evv = float(np.mean(ev)) if ev else float("nan")
    tot = float(np.nanmean([fv, evv])) if (free or ev) else float("nan")
    return {"free": fv, "event": evv, "total": tot}


DEFAULTS = {"hidden": 64, "steps": 500, "steps_long": 80, "h_short": 20, "batch": 128, "batch_long": 64, "wd": 1e-2, "z_noise": 0.0,
            "lr": 3e-3, "lr_enc": 1e-3, "lam_z": 0.5, "lam_x": 0.05, "lam_null": 0.2,
            "frac_event": 0.4, "rel_tol": 0.10, "abs_tol": 0.005, "k_max": 12, "patience": 2, "share_tol": 0.10, "fallback": True,
            "k_rule": "psr"}


def finalize_system(model: C.CBModel, sid: str, prep, btr, bva, H):
    """Unit leak / baseline, latent bound, value ranges and validated event gains of one exported system."""
    S = model.sys[sid]
    evp = dict(model.ev)
    S["ev"] = evp
    leak = C.fit_unit_leak(btr, prep, S["W"] if S.get("Wd") is None else S["Wd"].T)
    S["base_s"] = C.base_state(prep, leak)
    evp["kappa"] = leak["kappa"]
    Z = np.concatenate([b.xs for b in btr]) @ S["W"].T
    S["zlim"] = 2.0 * np.abs(Z).max(0) + 1e-6
    C.install_latent_box(model, sid, btr + bva)
    C.install_ranges(model, sid)
    C.select_event_gains(model, sid, btr + bva, H, P._rollout_binned)


def fit_one_k(prep, btr, bva, fit_rrr, k, H, seed, cfg, pcs, sid, W_init=None):
    W0 = C.rrr_encoder(fit_rrr, k)
    if W_init is not None and np.asarray(W_init).shape == W0.shape:
        q, _ = np.linalg.qr(np.asarray(W_init, float).T)
        W0 = q[:, :k].T.copy()
    net = train_cb(prep, btr, bva, W0, H, seed, cfg, pcs)
    model = C.CBModel()
    model.sys[sid] = {"prep": prep}
    model.k[sid] = k
    net.export(model, sid)
    finalize_system(model, sid, prep, btr, bva, H)
    vl = val_loss_np(model, sid, bva, H)
    return model, vl


def no_effect_event_loss(model, sid, bva, H):
    """Validation event-window loss when the model ignores the events (the 'no effect' prediction)."""
    errs = []
    for b in bva:
        if b.M <= H + 1 or not b.ev_bins.any():
            continue
        for m0 in np.linspace(0, b.M - H - 1, 6).astype(int):
            if not b.ev_bins[m0: m0 + H].any():
                continue
            z = model.sys[sid]["W"] @ b.xs[m0]
            Zs = P._rollout_binned(model, sid, z, b, m0, H, False)
            yp = model.readout_n(sid, Zs[1:], b.u[m0 + 1: m0 + H + 1])
            errs.append(float(np.mean((yp - b.y[m0 + 1: m0 + H + 1]) ** 2)))
    return float(np.mean(errs)) if errs else float("nan")


# ================================================================================================================ per-system context
def prepare(train_sys, system, seed):
    trs, vas = P.split_train_val(train_sys, seed)
    prep, btr, bva, spec, hinfo = P.prepare_history(trs, vas, system, C.choose_stride(train_sys), seed)
    H = max(2, min(b.M for b in btr) // 4)
    N = prep.n_units
    mech = system.get("mode") == "mech"
    rule = P.psr_rank_rule(spec["err"], spec["sv2"], N, compact_applies=not mech)
    D = C.future_design(btr + bva, H, pcs=spec["pcs"])
    fit_rrr = C.rrr_fit(D[0], D[1], D[2], spec["lam"], 0.3, D[5], len(D[4]))
    return {"prep": prep, "btr": btr, "bva": bva, "H": H, "spec": spec, "N": N, "rule": rule, "fit_rrr": fit_rrr, "mech": mech,
            "history": hinfo}


def linear_dyn(btr, W):
    """Least-squares one-step linear latent map (A, B) of encoded free steps (for gauge alignment)."""
    Z0, U0, Z1 = [], [], []
    for b in btr:
        z = b.xs @ W.T
        i = np.flatnonzero(~b.ev_bins)
        Z0.append(z[i]); U0.append(b.u[i]); Z1.append(z[i + 1])
    Z0, U0, Z1 = np.concatenate(Z0), np.concatenate(U0), np.concatenate(Z1)
    k, nu = Z0.shape[1], U0.shape[1]
    M = C.ridge_solve(np.hstack([Z0, U0, np.ones((len(Z0), 1))]), Z1 - Z0, 1e-6)
    return M[:k].T, M[k: k + nu].T, float(np.sqrt(np.mean(Z0.var(0))))


def align_gauge(A0, B0, A1, B1):
    """R minimising ||R A1 - A0 R||^2 + ||R B1 - B0||^2 (similarity transform of the linear parts; the input term fixes the scale)."""
    k = A0.shape[0]
    I = np.eye(k)
    rows = [np.kron(I, A1.T) - np.kron(A0, I)]            # vec(R A1 - A0 R) in row-major vec(R)
    rhs = [np.zeros(k * k)]
    if B1.size and np.abs(B1).sum() > 1e-9:
        nu = B1.shape[1]
        rows.append(np.kron(I, B1.T))                        # vec(R B1)
        rhs.append(B0.reshape(-1))
    A = np.vstack(rows)
    b = np.concatenate(rhs)
    lam = 1e-3 * np.trace(A.T @ A) / A.shape[1]
    r = np.linalg.solve(A.T @ A + lam * np.eye(k * k), A.T @ b + lam * np.eye(k).reshape(-1))
    R = r.reshape(k, k)
    if not np.all(np.isfinite(R)) or abs(np.linalg.det(R)) < 1e-6:
        R = np.eye(k)
    return R


def n_params_of(model: C.CBModel, sids):
    enc = {sid: int(model.sys[sid]["W"].size) for sid in sids}
    ro = {}
    for sid in sids:
        R = model.sys[sid]["ro"]
        ro[sid] = int(R["C"].size + R["D"].size + R["e"].size + C.n_mlp(R.get("mlp") or []) + (R["Wr"].size if R.get("rff") is not None else 0))
    trans_objs = {}
    for sid in sids:
        T = model.sys[sid].get("trans") or model.trans
        trans_objs[id(T)] = int(C.n_mlp(T.get("mlp") or []) + T["A"].size + T["b"].size + (T["Wf"].size if T.get("rff") is not None else 0))
    b_sizes = {id(model.sys[sid]["B"]): int(model.sys[sid]["B"].size) for sid in sids}
    return {"encoder": enc, "transition": int(sum(trans_objs.values()) + sum(b_sizes.values())), "readout": ro, "events": 4 * len(sids)}


@register
class CBInterchange(StateMethod):
    name = "cb_interchange"
    version = "2"
    default_config = dict(DEFAULTS)
    supported_sharing = ("auto", "independent", "shared")
    supports_adaptation = True

    def fit(self, train, *, systems, config=None, sim=None, seed=0):
        torch = _torch()
        torch.set_num_threads(min(3, torch.get_num_threads()))
        cfg = dict(DEFAULTS)
        cfg.update({k_: v for k_, v in (config or {}).items() if k_ in DEFAULTS})
        config = dict(config or {})
        t0 = C.now()
        sharing = config.get("sharing") or "auto"
        if sharing not in ("auto", "independent", "shared"):
            raise NotImplementedError(f"cb_interchange does not support sharing={sharing!r}")
        sids = sorted({t.system_id for t in train})
        by = {sid: [t for t in train if t.system_id == sid] for sid in sids}
        if config.get("adapt_from") is not None:
            model = self._fit_adapt(by, systems, config["adapt_from"], cfg, config, seed)
            model.meta["train_cost"] = {"cpu_s": C.now() - t0, "sim_calls": 0, "mode": "encoder-only adaptation"}
            return model
        if len(sids) == 1:
            model = self._fit_single(sids[0], by[sids[0]], systems[sids[0]], cfg, config, seed)
            model.meta["sharing"] = {"mode": "independent", "verdict": None}
        elif sharing == "shared":
            model = self._fit_shared(by, systems, cfg, config, seed)
        else:
            singles = {sid: self._fit_single(sid, by[sid], systems[sid], cfg, config, seed) for sid in sids}
            model = merge_independent(singles)
            model.meta["sharing"] = {"mode": "independent", "verdict": None}
            if sharing == "auto":
                shared = self._fit_shared(by, systems, cfg, dict(config, k=max(model.k.values())), seed)
                ok = all(shared.meta["val_loss"][sid] <= singles[sid].meta["val_loss"][sid] * (1 + cfg["share_tol"]) + cfg["abs_tol"]
                         for sid in sids)
                fewer = shared.meta["n_params"]["transition"] < model.meta["n_params"]["transition"]
                verdict = "supported" if (ok and fewer) else "rejected"
                if verdict == "supported":
                    model = shared
                model.meta["sharing"] = {"mode": "shared" if verdict == "supported" else "independent", "verdict": verdict,
                                         "val_loss_shared": shared.meta["val_loss"],
                                         "val_loss_independent": {sid: singles[sid].meta["val_loss"][sid] for sid in sids}}
        model.meta.setdefault("train_cost", {})
        model.meta["train_cost"] = {"cpu_s": C.now() - t0, "sim_calls": 0}
        return model

    # ------------------------------------------------------------------ one system: k sweep
    def _fit_single(self, sid, train_sys, system, cfg, config, seed):
        ctx = prepare(train_sys, system, seed)
        prep, btr, bva, H, spec, N, rule, fit_rrr = (ctx[k_] for k_ in ("prep", "btr", "bva", "H", "spec", "N", "rule", "fit_rrr"))
        compact_limit = max(1, N / 5) if not ctx["mech"] else np.inf
        k_max = int(min(cfg["k_max"], max(2, N // 4), N))
        curve, models = [], {}
        # the sweep starts one below the predictive-state rank (lower dimensions are dominated on the PSR validation curve)
        k_max = max(k_max, min(N, rule["k"] + 2))
        psr_sel = None
        if config.get("k"):
            ks = [int(config["k"])]
        elif cfg["k_rule"] == "psr":
            k_psr, psr_sel = P.select_k(prep, sid, btr, bva, H, seed, spec, rule, N)
            ks = [k_psr]
        else:
            ks = list(range(max(1, rule["k"] - 1), k_max + 1))
        best_k, best_l = None, np.inf
        for k in ks:
            model, vl = fit_one_k(prep, btr, bva, fit_rrr, k, H, seed, cfg, spec["pcs"], sid, config.get("W_init"))
            curve.append({"k": k, **vl})
            models[k] = model
            if vl["total"] < best_l:
                best_k, best_l = k, vl["total"]
            if not config.get("k") and k - best_k >= cfg["patience"]:
                break
        tried = [c["k"] for c in curve]
        L = [c["total"] for c in curve]
        if config.get("k"):
            k_sel, k_rng, resolved = ks[0], [ks[0], ks[0]], True
        elif cfg["k_rule"] == "psr":
            k_sel, resolved = ks[0], True
            k_rng = [min(rule["k_range"][0], k_sel), max(rule["k_range"][1], k_sel)]
        else:
            k_sel, k_rng, resolved = C.plateau_k(tried, L, cfg["rel_tol"], cfg["abs_tol"])
        model = models[k_sel]
        # validated fallback: the closed-form predictive-state model (cb_psr construction) at the same k, same split; the model with the
        # lower validation loss (held-out parameter draws included) is kept. Guards against a nonlinear transition that fits the
        # training draws but not new ones.
        fb = None
        if cfg.get("fallback", True):
            psr_m, _ = P._build(prep, sid, C.rrr_encoder(fit_rrr, k_sel), btr, bva, H, seed, btr + bva)
            vl_psr = val_loss_np(psr_m, sid, bva, H)
            vl_ic = [c for c in curve if c["k"] == k_sel][0]
            fb = {"val_ic": vl_ic["total"], "val_psr": vl_psr["total"], "chosen": "interchange"}
            if np.isfinite(vl_psr["total"]) and vl_psr["total"] < vl_ic["total"]:
                psr_m, _ = P._build(prep, sid, C.rrr_encoder(fit_rrr, k_sel), btr, bva, H, seed, btr + bva, refit=True)
                model = psr_m
                fb["chosen"] = "psr"
                for c in curve:
                    if c["k"] == k_sel:
                        c.update({"total_psr": vl_psr["total"], "event_psr": vl_psr["event"]})
                curve = [dict(c, event=vl_psr["event"]) if c["k"] == k_sel else c for c in curve]
        # abstention
        no_plateau = (not resolved) and k_sel >= k_max
        no_compact = bool((rule["abstain"] or no_plateau or k_sel > compact_limit) and not config.get("k"))
        ne = no_effect_event_loss(model, sid, bva, H)
        ev_l = [c for c in curve if c["k"] == k_sel][0]["event"]
        causal_fail = bool(np.isfinite(ne) and np.isfinite(ev_l) and ev_l > ne * 1.05)
        reason = []
        if no_compact:
            reason.append(f"no compact state: psr [{rule['reason']}], sweep resolved={resolved}, k={k_sel}, N/5={compact_limit:.1f}")
        if causal_fail:
            reason.append(f"validation intervention loss {ev_l:.3g} > no-effect loss {ne:.3g}")
        abst = {"no_compact_state": no_compact, "dimension_unresolved": ([k_sel, max(k_sel, rule["k_range"][1])] if no_compact else None),
                "causal_equivalence_failed": causal_fail, "reason": "; ".join(reason)}
        k = k_sel
        model.meta = {"k": {sid: k}, "k_range": {sid: [int(min(k_rng)), int(max(k_rng))] if not no_compact else abst["dimension_unresolved"]},
                      "abstain": {sid: abst}, "n_params": n_params_of(model, [sid]),
                      "lipschitz_bound": 1.0, "val_loss": {sid: [c for c in curve if c["k"] == k_sel][0]["total"]},
                      "curve": {sid: {"sweep": curve, "psr_rule": rule, "psr_k_selection": psr_sel, "history": ctx["history"],
                                      "psr_sv2": [float(v) for v in spec["sv2"][:16]],
                                      "no_effect_event_loss": ne, "fallback": fb}},
                      "dimension_rule": ("cb_psr rule (spectral count / CV plateau + model-based step k..k+2 on validation incl. held-out "
                                         "draws)" if cfg["k_rule"] == "psr" else "sweep: smallest k with val loss <= 1.10 min + 0.005")}
        return model

    # ------------------------------------------------------------------ several systems, one transition f
    def _fit_shared(self, by, systems, cfg, config, seed):
        sids = sorted(by)
        ctxs = {sid: prepare(by[sid], systems[sid], seed) for sid in sids}
        k = int(config.get("k") or max(c["rule"]["k"] for c in ctxs.values()))
        H = min(c["H"] for c in ctxs.values())
        nus = {c["btr"][0].u.shape[1] for c in ctxs.values()}
        share_B = len(nus) == 1
        nets, W0s = [], {}
        for i, sid in enumerate(sids):
            c = ctxs[sid]
            W0 = C.rrr_encoder(c["fit_rrr"], k)
            W0s[sid] = W0
            net = make_net(c["prep"], c["btr"], W0, seed + i, cfg)
            if i == 0:
                linear_init(net, c["btr"], W0)
                A0, B0, _ = linear_dyn(c["btr"], W0)
            else:
                net.tie(nets[0], share_B=share_B)
                A1, B1, _ = linear_dyn(c["btr"], W0)
                R = align_gauge(A0, B0 if share_B else np.zeros((k, 0)), A1, B1 if share_B else np.zeros((k, 0)))
                net.set_free_gauge()
                with torch_no_grad():
                    net.R.copy_(_torch().tensor(R, dtype=_torch().float32))
                readout_init(net, c["btr"], R @ W0)
            nets.append(net)
        cfg2 = dict(cfg)
        cfg2["steps"] = int(cfg["steps"] * cfg.get("shared_steps_mult", 1.0))
        train_multi(nets, [ctxs[s]["btr"] for s in sids], [ctxs[s]["spec"]["pcs"] for s in sids], H, seed, cfg2)
        model = C.CBModel()
        vls, abst, kr = {}, {}, {}
        for net, sid in zip(nets, sids):
            c = ctxs[sid]
            model.sys[sid] = {"prep": c["prep"]}
            model.k[sid] = k
            net.export(model, sid)
            finalize_system(model, sid, c["prep"], c["btr"], c["bva"], H)
            vls[sid] = val_loss_np(model, sid, c["bva"], H)["total"]
            rule = c["rule"]
            abst[sid] = {"no_compact_state": bool(rule["abstain"] and rule["k"] > max(1, c["N"] / 5) and not config.get("k")),
                         "dimension_unresolved": None, "causal_equivalence_failed": False, "reason": rule["reason"]}
            kr[sid] = [k, k]
        model.meta = {"k": dict(model.k), "k_range": kr, "abstain": abst, "n_params": n_params_of(model, sids), "lipschitz_bound": None,
                      "val_loss": vls, "sharing": {"mode": "shared", "verdict": None},
                      "dimension_rule": "shared fit: k = max over systems of the cb_psr rank rule (or config k)"}
        return model

    # ------------------------------------------------------------------ encoder-only adaptation with f frozen
    def _fit_adapt(self, by, systems, base: C.CBModel, cfg, config, seed):
        base = getattr(base, "base", base)          # a cb_cegar wrapper: use its base model
        ref = sorted(base.sys)[0]
        k = int(base.k[ref])
        model = C.CBModel()
        model.trans = base.trans
        abst, kr, vls = {}, {}, {}
        for i, sid in enumerate(sorted(by)):
            c = prepare(by[sid], systems[sid], seed)
            W0 = C.rrr_encoder(c["fit_rrr"], k)
            net = make_net(c["prep"], c["btr"], W0, seed + i, cfg)
            net.load_transition(base, ref)
            A1, B1, _ = linear_dyn(c["btr"], W0)
            T = base.trans
            A0 = T["A"]
            B0 = base.sys[ref]["B"]
            same_u = B0.shape == B1.shape
            R = align_gauge(A0, B0 if same_u else np.zeros((k, 0)), A1, B1 if same_u else np.zeros((k, 0)))
            net.set_free_gauge()
            with torch_no_grad():
                net.R.copy_(_torch().tensor(R, dtype=_torch().float32))
            if not same_u:
                net.B = _torch().zeros((k, B1.shape[1]), dtype=_torch().float32).requires_grad_(True)
            readout_init(net, c["btr"], R @ W0)
            train_multi([net], [c["btr"]], [c["spec"]["pcs"]], c["H"], seed, cfg, freeze_dyn=True)
            model.sys[sid] = {"prep": c["prep"]}
            model.k[sid] = k
            trans_before = model.trans
            net.export(model, sid)
            model.trans = trans_before                 # the frozen f is the base's (export would copy the same values)
            finalize_system(model, sid, c["prep"], c["btr"], c["bva"], c["H"])
            vls[sid] = val_loss_np(model, sid, c["bva"], c["H"])["total"]
            abst[sid] = {"no_compact_state": False, "dimension_unresolved": None, "causal_equivalence_failed": False, "reason": ""}
            kr[sid] = [k, k]
        sids = sorted(by)
        npar = n_params_of(model, sids)
        model.meta = {"k": dict(model.k), "k_range": kr, "abstain": abst, "n_params": npar, "val_loss": vls,
                      "sharing": {"mode": "adapted (transition frozen)", "verdict": None}, "lipschitz_bound": None}
        return model


def torch_no_grad():
    return _torch().no_grad()


def readout_init(net: TorchCB, btr, E):
    """Least-squares linear readout for the encoder E (k x N) of this system."""
    torch = _torch()
    Za = np.concatenate([b.xs for b in btr]) @ E.T
    Ua = np.concatenate([b.u for b in btr])
    Ya = np.concatenate([b.y for b in btr])
    k, nu = Za.shape[1], Ua.shape[1]
    R = C.ridge_solve(np.hstack([Za, Ua, np.ones((len(Za), 1))]), Ya, 1e-6)
    with torch.no_grad():
        net.C.copy_(torch.tensor(R[:k].T, dtype=torch.float32))
        net.D.copy_(torch.tensor(R[k: k + nu].T, dtype=torch.float32))
        net.e.copy_(torch.tensor(R[k + nu], dtype=torch.float32))
        net.g2.mul_(0.0)


def merge_independent(singles: dict) -> C.CBModel:
    """Several independently fitted single-system models as one model (per-system transitions)."""
    model = C.CBModel()
    meta = {"k": {}, "k_range": {}, "abstain": {}, "curve": {}, "val_loss": {}}
    for sid, m in singles.items():
        model.sys[sid] = dict(m.sys[sid])
        model.sys[sid]["trans"] = m.trans
        model.sys[sid].setdefault("ev", m.ev)
        model.k[sid] = m.k[sid]
        for key in meta:
            meta[key].update(m.meta.get(key, {}))
    model.trans = next(iter(singles.values())).trans
    meta["n_params"] = n_params_of(model, sorted(singles))
    meta["lipschitz_bound"] = 1.0
    model.meta = meta
    return model
