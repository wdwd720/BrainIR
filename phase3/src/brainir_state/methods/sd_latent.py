"""Torch latent model of the sd family: implementation-specific linear encoders / decoders / input maps / readouts and ONE
(or one per system) latent transition law, trained by open-loop multi-step rollouts. Also the numpy inference engine used by the
fitted StateModel (fast per-step evaluation, picklable, no torch needed at inference).

Model, per system s (standardised microstate xs = (x - mu_s) / sd_s, normalised input un = (u - umu_s) / usd_s):
    encoder     z = E_s xs                                              (k x N_s, linear, instantaneous: causal by construction)
    decoder     xs_hat = D_s z + d_s                                     (used for silencing / edge removal and as an auxiliary loss)
    transition  z' = z + h F(z, A_s un) [+ h L_s z  (partial sharing)] + dt g_s E_s (I / sd_s)      h = dt / T_c
    readout     y = y_mu + y_sd * (W_s [z, un] + MLP_s([z, un]))
Events (all through the per-unit encoder / decoder, so every observed neuron is addressable, including never-intervened ones):
    kick dx on units      z += E_s (dx / sd_s)                                      exact for a linear encoder
    current I on units    z += dt g_s E_s (I / sd_s) per step                          g_s = learned gain (1 / unit time constant)
    silence of units S    after each step: z += E_s[:, S] (rest_S - xs_hat_S)          the units are held at rest (inputs and
                                                                                        outputs removed)
    edge removal post<-pre  z += h E_s[:, post] D_s[post] (F(z_pre@rest) - F(z))    first-order effect of removing pre's input to
                                                                                        post, where z_pre@rest = z with unit pre at rest
"""

from __future__ import annotations

import time

import numpy as np

from .sd_core import SysData, batch_windows, se_mean, window_starts


# ------------------------------------------------------------------------------------------------------------ torch model
def _torch():
    import torch
    return torch


class _Mods:
    """Lazy holder so that this module imports without torch initialisation cost."""


def build_net(k: int, systems: list[SysData], shared: str, hidden_f: int, hidden_g: int, n_v: int, seed: int, inits: list[dict] | None,
              Tc: float, bases: list[np.ndarray]):
    torch = _torch()
    nn = torch.nn

    class FNet(nn.Module):
        """F(z, v) = [Wz z + Wv v + b]_{:k} + W3 tanh([Wz z + Wv v + b]_{k:}): a linear part plus one tanh hidden layer, with the
        two input matmuls fused (and the input part precomputable for a whole window)."""

        def __init__(self):
            super().__init__()
            self.Wz = nn.Linear(k, k + hidden_f)
            self.Wv = nn.Linear(n_v, k + hidden_f, bias=False)
            self.W3 = nn.Linear(hidden_f, k, bias=False)
            with torch.no_grad():
                self.Wz.weight[:k].mul_(0.1)
                self.Wz.bias[:k].zero_()
                self.Wv.weight[:k].mul_(0.1)
                self.W3.weight.mul_(0.1)

        def pre_v(self, v):
            return self.Wv(v)

        def step(self, z, pv):
            p = self.Wz(z) + pv
            return p[..., :k] + self.W3(torch.tanh(p[..., k:]))

        def forward(self, z, v):
            return self.step(z, self.pre_v(v))

    class Readout(nn.Module):
        def __init__(self, n_in, n_y):
            super().__init__()
            self.lin = nn.Linear(n_in, n_y)
            self.l1 = nn.Linear(n_in, hidden_g)
            self.l2 = nn.Linear(hidden_g, n_y)
            with torch.no_grad():
                self.l2.weight.mul_(0.1)
                self.l2.bias.zero_()

        def forward(self, a):
            return self.lin(a) + self.l2(torch.tanh(self.l1(a)))

    class Net(nn.Module):
        def __init__(self):
            super().__init__()
            torch.manual_seed(seed)
            nF = 1 if shared in ("shared", "partial") else len(systems)
            self.F = nn.ModuleList([FNet() for _ in range(nF)])
            # encoder / decoder restricted to the signal subspace V_s (r x N, leading PCs of the standardised microstate):
            # E_s = C_s V_s, D_s = V_s^T B_s
            self.Cp = nn.ParameterList()
            self.Bp = nn.ParameterList()
            self.dbias = nn.ParameterList()
            self.A = nn.ParameterList()
            self.lgam = nn.ParameterList()
            self.L = nn.ParameterList()
            self.G = nn.ModuleList()
            for s, sd in enumerate(systems):
                ini = (inits or [None] * len(systems))[s] or {}
                V = np.asarray(bases[s], np.float64)
                self.register_buffer(f"V{s}", torch.tensor(V, dtype=torch.float32))
                self.Cp.append(nn.Parameter(torch.tensor(np.asarray(ini["E"], np.float64) @ V.T, dtype=torch.float32)))
                self.Bp.append(nn.Parameter(torch.tensor(V @ np.asarray(ini["D"], np.float64), dtype=torch.float32)))
                self.dbias.append(nn.Parameter(torch.tensor(ini["dbias"], dtype=torch.float32)))
                A0 = np.zeros((n_v, sd.n_u), np.float32)
                A0[: min(n_v, sd.n_u), : min(n_v, sd.n_u)] = np.eye(min(n_v, sd.n_u))
                self.A.append(nn.Parameter(torch.tensor(ini.get("A", A0), dtype=torch.float32)))
                self.lgam.append(nn.Parameter(torch.tensor(float(ini.get("lgam", np.log(1.0 / Tc))), dtype=torch.float32)))
                self.L.append(nn.Parameter(torch.zeros(k, k)))
                self.G.append(Readout(k + sd.n_u, sd.n_y))
            self.shared = shared

        def Ef(self, s):
            return self.Cp[s] @ getattr(self, f"V{s}")

        def Df(self, s):
            return getattr(self, f"V{s}").T @ self.Bp[s]

        def Fs(self, s):
            return self.F[0] if len(self.F) == 1 else self.F[s]

        def f_step(self, s, z, pv):
            out = self.Fs(s).step(z, pv)
            if self.shared == "partial":
                out = out + z @ self.L[s].T
            return out

    return Net()


class Trainer:
    """Fits a Net on the windows of one or more systems. Frozen parts (adaptation) are passed by name."""

    def __init__(self, systems: list[SysData], k: int, *, shared: str = "independent", hidden_f: int = 64, hidden_g: int = 32,
                 Tc: float | None = None, seed: int = 0, cfg: dict | None = None):
        torch = _torch()
        self.torch = torch
        self.systems, self.k, self.shared, self.seed = systems, k, shared, seed
        self.cfg = dict(DEFAULT_TRAIN)
        self.cfg.update(cfg or {})
        self.n_v = max(sd.n_u for sd in systems)
        self.Tc = float(Tc if Tc is not None else np.median([sd.timescale() for sd in systems]))
        self.hidden_f, self.hidden_g = hidden_f, hidden_g
        self.pcs = [sd.pca(min(10, sd.N)) for sd in systems]
        if self.cfg.get("init", "predictive") == "predictive":
            self.inits = [self._pred_init(sd) for sd in systems]
        else:
            self.inits = [self._pca_init(sd, pc) for sd, pc in zip(systems, self.pcs)]
        # unit current gain: measured directly from training current onsets; with >= 2 events it is fixed (a direct measurement is
        # more reliable than the weak multi-step gradient of a few pulse windows), otherwise learned from 1 / T_c
        from .sd_core import current_gain
        self.gain_fixed = []
        for ini, sd in zip(self.inits, systems):
            g, n = current_gain(sd)
            if g is not None and g > 0:
                ini["lgam"] = float(np.log(g))
            self.gain_fixed.append(bool(g is not None and g > 0 and n >= 2))
        self.bases = [self._basis(sd) for sd in systems]
        self.net = build_net(k, systems, shared, hidden_f, hidden_g, self.n_v, seed, self.inits, self.Tc, self.bases)
        self.rest_s = [torch.tensor((sd.rest - sd.mu) / sd.sd, dtype=torch.float32) for sd in systems]
        self.sd_t = [torch.tensor(sd.sd, dtype=torch.float32) for sd in systems]
        self.mu_t = [torch.tensor(sd.mu, dtype=torch.float32) for sd in systems]
        self.log = []

    def _basis(self, sd: SysData) -> np.ndarray:
        """Signal subspace of the encoder / decoder: the leading r PCs of the standardised training microstate, r = the number
        reaching pc_var of the variance (default 99.5 %), at least 2k, at most N (pc_var >= 1: no restriction)."""
        pv = float(self.cfg.get("pc_var", 0.995))
        _, V, lam = sd.pca(sd.N)
        if pv >= 1.0:
            return V
        c = np.cumsum(lam) / max(lam.sum(), 1e-12)
        r = int(np.searchsorted(c, pv) + 1)
        r = int(min(len(lam), max(r, 2 * self.k)))
        return V[:r]

    def _pred_init(self, sd: SysData, rot: np.ndarray | None = None) -> dict:
        from .sd_core import predictive_encoder
        hz = float(self.cfg.get("pred_horizon_s", self.cfg.get("horizon_s", 1.0)))
        E, D, m = predictive_encoder(sd, self.k, lags_s=tuple(hz * f for f in (0.1, 0.25, 0.5, 1.0)), seed=self.seed)
        if rot is not None:
            E = (rot @ E).astype(np.float32)
            D = (D @ rot.T).astype(np.float32)
        return {"E": E, "D": D, "dbias": m}

    def init_for(self, s: int, rot: np.ndarray | None = None) -> dict:
        if self.cfg.get("init", "predictive") == "predictive":
            return self._pred_init(self.systems[s], rot)
        return self._pca_init(self.systems[s], self.pcs[s], rot)

    def _pca_init(self, sd: SysData, pc, rot: np.ndarray | None = None) -> dict:
        m, V, lam = pc
        k = self.k
        V = V[:k]
        lam = lam[:k]
        if V.shape[0] < k:                       # fewer units than k: pad with random directions
            r = np.random.default_rng(self.seed).standard_normal((k - V.shape[0], sd.N)) * 0.1
            V = np.vstack([V, r])
            lam = np.concatenate([lam, np.full(k - len(lam), 1e-2)])
        E = V / np.sqrt(lam + 1e-6)[:, None]
        D = V.T * np.sqrt(lam + 1e-6)[None, :]
        if rot is not None:
            E = rot @ E
            D = D @ rot.T
        return {"E": E.astype(np.float32), "D": D.astype(np.float32), "dbias": m.astype(np.float32)}

    # ----------------------------------------------------------------------------------------------------- rollout (torch)
    def rollout_t(self, s: int, x, u, kick, cur, sil, has_ev: bool):
        """x (B, H+1, N) raw; returns z_pred (B, H+1, k), z_enc (B, H+1, k), xs (B, H+1, N) standardised, un (B, H+1, n_u)."""
        torch = self.torch
        net = self.net
        sd = self.systems[s]
        xs = (x - self.mu_t[s]) / self.sd_t[s]
        un = (u - torch.tensor(sd.u_mu, dtype=torch.float32)) / torch.tensor(sd.u_sd, dtype=torch.float32)
        E = net.Ef(s)
        z_enc = xs @ E.T
        pv = net.Fs(s).pre_v(un @ net.A[s].T)
        H = x.shape[1] - 1
        h = sd.dt / self.Tc
        z = z_enc[:, 0]
        zs = [z]
        if has_ev:
            gam = torch.exp(net.lgam[s])
            if sd.nonneg:
                kick = torch.where(kick < 0, torch.maximum(kick, -x[:, :H]), kick)   # rates: the kicked state is clipped at 0
            kz = (kick / self.sd_t[s]) @ E.T
            cz = (sd.dt * gam) * ((cur / self.sd_t[s]) @ E.T)
            sil_any = sil.amax(dim=(0, 2)) > 0
            rho = torch.clamp(sd.dt * gam, max=1.0)            # unit relaxation per step (tau_u = 1 / gain)
            a = torch.zeros_like(sil[:, 0])
            prev = torch.zeros_like(sil[:, 0])
        zeta = z                                               # free-population state (differs from z only while units are silenced)
        for j in range(H):
            if has_ev:
                zeta = zeta + kz[:, j]
                m = sil[:, j]
                if bool(sil_any[j]):
                    on = m * (1.0 - prev)
                    dev = (zeta @ net.Df(s).T + net.dbias[s] - self.rest_s[s]) * m      # latent-implied deviation of S from rest
                    a = a * m + on * dev                                                   # actual deviation, decays
                    zeta = zeta + h * net.f_step(s, zeta - dev @ E.T, pv[:, j]) + cz[:, j]
                    a = a * (1.0 - rho)
                    dev2 = (zeta @ net.Df(s).T + net.dbias[s] - self.rest_s[s]) * m
                    z = zeta - (dev2 - a) @ E.T                                            # observed population latent
                else:
                    if bool(prev.any()):
                        zeta = z                                                           # units rejoin at their actual state
                    zeta = zeta + h * net.f_step(s, zeta, pv[:, j]) + cz[:, j]
                    z = zeta
                    a = a * 0.0
                prev = m
            else:
                z = z + h * net.f_step(s, z, pv[:, j])
            zs.append(z)
        return torch.stack(zs, 1), z_enc, xs, un

    def losses(self, s: int, starts, H: int):
        torch = self.torch
        sd = self.systems[s]
        x, u, y, kick, cur, sil, has = batch_windows(sd, starts, H)
        x, u, y = torch.tensor(x), torch.tensor(u), torch.tensor(y)
        kick, cur, sil = torch.tensor(kick), torch.tensor(cur), torch.tensor(sil)
        zp, ze, xs, un = self.rollout_t(s, x, u, kick, cur, sil, has)
        net = self.net
        yhat = net.G[s](torch.cat([zp, un], -1))
        yt = (y - torch.tensor(sd.y_mu, dtype=torch.float32)) / torch.tensor(sd.y_sd, dtype=torch.float32)
        L_y = ((yhat - yt) ** 2).mean()
        L_z = ((zp[:, 1:] - ze[:, 1:]) ** 2).mean()
        xh = zp @ net.Df(s).T + net.dbias[s]
        L_x = ((xh - xs) ** 2).mean()
        z0 = ze[:, 0]
        C = (z0 - z0.mean(0)).T @ (z0 - z0.mean(0)) / max(1, len(z0) - 1)
        L_w = ((C - torch.eye(self.k)) ** 2).mean() + (z0.mean(0) ** 2).mean()
        c = self.cfg
        return L_y + c["w_z"] * L_z + c["w_x"] * L_x + c["w_white"] * L_w, {"y": float(L_y.detach()), "z": float(L_z.detach()), "x": float(L_x.detach()), "w": float(L_w.detach())}

    def fit(self, n_iter: int | None = None, H_max: int | None = None, train_params: str = "all", time_limit: float | None = None,
            systems_idx: list[int] | None = None):
        """train_params: 'all' or 'encoders' (adaptation: F frozen). H_max: rollout horizon in samples."""
        torch = self.torch
        c = self.cfg
        n_iter = n_iter or c["n_iter"]
        sidx = systems_idx if systems_idx is not None else list(range(len(self.systems)))
        dt = self.systems[sidx[0]].dt
        H_max = H_max or max(4, int(round(c["horizon_s"] / dt)))
        H_max = min(H_max, min(min(len(self.systems[s].X[i]) for i in self.systems[s].train_idx) for s in sidx) - 2)
        for s in range(len(self.systems)):
            self.net.lgam[s].requires_grad_(not self.gain_fixed[s])
        if train_params == "encoders":
            params = []
            for s in sidx:
                params += [self.net.Cp[s], self.net.Bp[s], self.net.dbias[s], self.net.A[s], self.net.L[s]]
                params += [self.net.lgam[s]] if not self.gain_fixed[s] else []
                params += list(self.net.G[s].parameters())
            for p in self.net.F.parameters():
                p.requires_grad_(False)
        else:
            for p in self.net.F.parameters():
                p.requires_grad_(True)
            params = [p for p in self.net.parameters() if p.requires_grad]
        opt = torch.optim.Adam(params, lr=c["lr"], weight_decay=c["wd"])
        sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=c["lr"], total_steps=n_iter, pct_start=0.1)
        rng = np.random.default_rng(self.seed + 17)
        starts_all = {}
        t0 = time.time()
        for it in range(n_iter):
            frac = it / max(1, n_iter - 1)
            H = int(max(2, round(H_max * min(1.0, c["h_min_frac"] + frac / c["curriculum"]))))
            if H not in starts_all:
                starts_all[H] = {s: window_starts(self.systems[s], self.systems[s].train_idx, H) for s in sidx}
            loss = 0.0
            parts = {}
            for s in sidx:
                st = starts_all[H][s]
                b = [st[j] for j in rng.integers(0, len(st), c["batch"])]
                l, parts = self.losses(s, b, H)
                loss = loss + l
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step()
            sched.step()
            if it % 100 == 0 or it == n_iter - 1:
                self.log.append({"it": it, "H": H, "loss": float(loss.detach()), **parts})
            if time_limit is not None and time.time() - t0 > time_limit:
                self.log.append({"stopped_at": it, "reason": "time_limit"})
                break
        for p in self.net.F.parameters():
            p.requires_grad_(True)
        return self

    # ----------------------------------------------------------------------------------------------------- export
    def export(self) -> dict:
        """Numpy parameters of the fitted net (the executable model)."""
        net = self.net

        def lin(m):
            return (m.weight.detach().numpy().astype(np.float64), m.bias.detach().numpy().astype(np.float64))

        Fs = [{"Wz": lin(F.Wz), "Wv": F.Wv.weight.detach().numpy().astype(np.float64),
               "W3": F.W3.weight.detach().numpy().astype(np.float64), "k": self.k} for F in net.F]
        per = []
        for s, sd in enumerate(self.systems):
            G = net.G[s]
            per.append({"sid": sd.sid, "obs": sd.obs, "mu": sd.mu, "sd": sd.sd, "u_mu": sd.u_mu, "u_sd": sd.u_sd, "y_mu": sd.y_mu,
                        "y_sd": sd.y_sd, "rest_s": (sd.rest - sd.mu) / sd.sd, "dt": sd.dt, "nonneg": bool(sd.nonneg),
                        "E": net.Ef(s).detach().numpy().astype(np.float64), "D": net.Df(s).detach().numpy().astype(np.float64),
                        "r_basis": int(self.bases[s].shape[0]),
                        "dbias": net.dbias[s].detach().numpy().astype(np.float64), "A": net.A[s].detach().numpy().astype(np.float64),
                        "gam": float(np.exp(net.lgam[s].detach().numpy())), "L": net.L[s].detach().numpy().astype(np.float64),
                        "G": {"lin": lin(G.lin), "l1": lin(G.l1), "l2": lin(G.l2)}, "F": 0 if len(Fs) == 1 else s})
        for s, sd in enumerate(self.systems):
            per[s]["z_lo"], per[s]["z_hi"] = self.latent_box(s)
        return {"k": self.k, "Tc": self.Tc, "shared": self.shared, "F": Fs, "systems": per}

    def latent_box(self, s: int, margin: float = 0.5):
        """Box of the training encodings (0.1 / 99.9 percentiles) widened by `margin` x its extent: rollouts are kept inside it
        (the transition law is not identified far outside the data)."""
        sd = self.systems[s]
        E = self.net.Ef(s).detach().numpy().astype(np.float64)
        Z = np.concatenate([sd.xs(sd.X[i][::3]) @ E.T for i in sd.train_idx if sd.finite[i]])
        lo, hi = np.percentile(Z, 0.1, axis=0), np.percentile(Z, 99.9, axis=0)
        w = hi - lo
        return lo - margin * w - 1e-6, hi + margin * w + 1e-6

    def load_F(self, Fp: dict, dst: int = 0) -> None:
        """Copy an exported transition law into F[dst]."""
        torch = self.torch
        F = self.net.F[dst]
        with torch.no_grad():
            F.Wz.weight.copy_(torch.tensor(Fp["Wz"][0], dtype=torch.float32))
            F.Wz.bias.copy_(torch.tensor(Fp["Wz"][1], dtype=torch.float32))
            F.Wv.weight.copy_(torch.tensor(Fp["Wv"], dtype=torch.float32))
            F.W3.weight.copy_(torch.tensor(Fp["W3"], dtype=torch.float32))

    def load_system(self, ps: dict, dst: int) -> None:
        """Copy exported per-system parameters (encoder, decoder, input map, gain, readout) into system dst."""
        torch = self.torch
        net = self.net
        with torch.no_grad():
            V = self.bases[dst].astype(np.float64)
            net.Cp[dst].copy_(torch.tensor(np.asarray(ps["E"]) @ V.T, dtype=torch.float32))
            net.Bp[dst].copy_(torch.tensor(V @ np.asarray(ps["D"]), dtype=torch.float32))
            net.dbias[dst].copy_(torch.tensor(ps["dbias"], dtype=torch.float32))
            if tuple(ps["A"].shape) == tuple(net.A[dst].shape):
                net.A[dst].copy_(torch.tensor(ps["A"], dtype=torch.float32))
            net.lgam[dst].copy_(torch.tensor(np.log(ps["gam"]), dtype=torch.float32))
            G = net.G[dst]
            for name in ("lin", "l1", "l2"):
                m = getattr(G, name)
                m.weight.copy_(torch.tensor(ps["G"][name][0], dtype=torch.float32))
                m.bias.copy_(torch.tensor(ps["G"][name][1], dtype=torch.float32))

    def set_encoder(self, dst: int, E: np.ndarray, D: np.ndarray, dbias: np.ndarray) -> None:
        torch = self.torch
        with torch.no_grad():
            V = self.bases[dst].astype(np.float64)
            self.net.Cp[dst].copy_(torch.tensor(np.asarray(E, np.float64) @ V.T, dtype=torch.float32))
            self.net.Bp[dst].copy_(torch.tensor(V @ np.asarray(D, np.float64), dtype=torch.float32))
            self.net.dbias[dst].copy_(torch.tensor(dbias, dtype=torch.float32))

    def train_loss(self, s: int, n_batches: int = 4, H: int | None = None) -> float:
        """Mean training loss of system s on a few fixed random batches (no gradient), for comparing restarts."""
        torch = self.torch
        sd = self.systems[s]
        H = H or max(4, int(round(self.cfg["horizon_s"] / sd.dt)))
        H = min(H, min(len(sd.X[i]) for i in sd.train_idx) - 2)
        st = window_starts(sd, sd.train_idx, H)
        rng = np.random.default_rng(self.seed + 99)
        tot = 0.0
        with torch.no_grad():
            for _ in range(n_batches):
                b = [st[j] for j in rng.integers(0, len(st), self.cfg["batch"])]
                tot += float(self.losses(s, b, H)[0])
        return tot / n_batches


SCORE_CAP = 2.0

DEFAULT_TRAIN = {"pc_var": 0.995, "n_iter": 300, "batch": 128, "lr": 3e-3, "wd": 1e-6, "horizon_s": 1.0, "h_min_frac": 0.1, "curriculum": 0.6,
                 "w_z": 1.0, "w_x": 0.3, "w_white": 0.1}


# ------------------------------------------------------------------------------------------------------------ numpy engine
def _lin(p, a):
    return a @ p[0].T + p[1]


def F_np(F: dict, z, v):
    k = F["k"]
    p = z @ F["Wz"][0].T + F["Wz"][1] + v @ F["Wv"].T
    return p[..., :k] + np.tanh(p[..., k:]) @ F["W3"].T


def f_sys(P: dict, s: int, z, v):
    ps = P["systems"][s]
    out = F_np(P["F"][ps["F"]], z, v)
    if P["shared"] == "partial":
        out = out + z @ ps["L"].T
    return out


def G_np(G: dict, a):
    return _lin(G["lin"], a) + _lin(G["l2"], np.tanh(_lin(G["l1"], a)))


def encode_np(P: dict, s: int, x):
    ps = P["systems"][s]
    return ((np.asarray(x, np.float64) - ps["mu"]) / ps["sd"]) @ ps["E"].T


def filter_window(alpha: float) -> int:
    """Samples of history the recursive encoder uses: the weight of older samples, (1 - alpha)^W, is below 1e-3."""
    if alpha >= 1.0:
        return 0
    alpha = min(max(float(alpha), 0.01), 0.999)
    return int(np.ceil(np.log(1e-3) / np.log(1.0 - alpha)))


def encode_hist_np(P: dict, s: int, x_hist, u_hist, dt: float, alpha: float | None = None):
    """Causal encoder. alpha = 1: z_t = E xs_t (instantaneous). alpha < 1: a fixed-gain recursive filter that uses the model's own
    transition law, z_t = (1 - alpha) [z_{t-1} + h F(z_{t-1}, A un_{t-1})] + alpha E xs_t, started W samples back at E xs_{t-W}
    (W from filter_window). Its only carried state is z itself (k dimensions); it sees x and u up to t only, never y or events."""
    ps = P["systems"][s]
    a = float(ps.get("alpha", 1.0) if alpha is None else alpha)
    x_hist = np.asarray(x_hist)
    if a >= 1.0 or len(x_hist) < 2:
        return encode_np(P, s, x_hist[-1])
    W = min(len(x_hist) - 1, filter_window(a))
    xs = ((np.asarray(x_hist[-W - 1:], np.float64) - ps["mu"]) / ps["sd"]) @ ps["E"].T
    un = (np.asarray(u_hist[-W - 1:], np.float64) - ps["u_mu"]) / ps["u_sd"]
    v = un @ ps["A"].T
    h = dt / P["Tc"]
    z = xs[0].copy()
    for j in range(W):
        z = (1.0 - a) * (z + h * f_sys(P, s, z, v[j])) + a * xs[j + 1]
    return z


def readout_np(P: dict, s: int, z, u):
    ps = P["systems"][s]
    un = (np.asarray(u, np.float64) - ps["u_mu"]) / ps["u_sd"]
    return G_np(ps["G"], np.concatenate([z, un], -1)) * ps["y_sd"] + ps["y_mu"]


def rollout_np(P: dict, s: int, z0, u_future, parsed_events: list, dt: float, H: int):
    """Open-loop rollout of one trajectory (numpy). parsed_events from sd_core.parse_events (step resolution, relative)."""
    from .sd_core import dense_events
    ps = P["systems"][s]
    E, D, db = ps["E"], ps["D"], ps["dbias"]
    K = ps.get("K_ev", E)            # event map: latent change per unit change of the standardised microstate (kicks, currents)
    Ks = ps.get("K_sil", K)          # silencing map (not gain-calibrated)
    un = (np.asarray(u_future, np.float64) - ps["u_mu"]) / ps["u_sd"]
    v = un @ ps["A"].T
    h = dt / P["Tc"]
    N = E.shape[1]
    has = bool(parsed_events)
    if has:
        kick, cur, sil, edges = dense_events(parsed_events, 0, H, N)
        kick = kick / ps["sd"]
        cur = cur / ps["sd"]
    z = np.asarray(z0, np.float64).copy()
    zs = [z.copy()]
    aux: dict[int, float] = {}                 # silenced units: actual deviation from rest (decays with the unit time constant)
    rho = min(1.0, dt * ps["gam"])
    zeta = z.copy()                            # free-population state (differs from z only while units are silenced)
    for j in range(H):
        if has and kick[j].any():
            kj = kick[j]
            if ps.get("nonneg"):
                nz = np.flatnonzero(kj < 0)
                if len(nz):
                    xr = np.maximum((D[nz] @ zeta + db[nz]) * ps["sd"][nz] + ps["mu"][nz], 0.0) / ps["sd"][nz]
                    kj = kj.copy()
                    kj[nz] = np.maximum(kj[nz], -xr)
            zeta = zeta + K @ kj
            z = zeta if not aux else z + K @ kj
        S = np.flatnonzero(sil[j] > 0) if has else np.zeros(0, int)
        if len(S):
            for u_ in list(aux):
                if u_ not in set(S.tolist()):
                    aux.pop(u_)
            for u_ in S:
                if int(u_) not in aux and ps.get("sil_mode", "split") == "split":
                    aux[int(u_)] = float(D[u_] @ zeta + db[u_] - ps["rest_s"][u_])
            dev = D[S] @ zeta + db[S] - ps["rest_s"][S]
            dzeta = h * f_sys(P, s, zeta - Ks[:, S] @ dev if ps.get("sil_mode", "split") == "split" else zeta, v[j])
        else:
            if aux:
                zeta = z.copy()                # the units rejoin at their actual state
                aux.clear()
            dzeta = h * f_sys(P, s, zeta, v[j])
        if has:
            if cur[j].any():
                dzeta = dzeta + dt * ps["gam"] * (K @ cur[j])
            if edges is not None and edges[j]:
                dzeta = dzeta + h * _edge_effect(P, s, zeta, v[j], edges[j])
        zeta = zeta + dzeta
        if len(S) and ps.get("sil_mode", "split") == "clamp":
            # clamp: the silenced units are held at rest in the latent itself (projection after every step)
            zeta = zeta + Ks[:, S] @ (ps["rest_s"][S] - (D[S] @ zeta + db[S]))
            aux.clear()
            z = zeta
        elif len(S):
            for u_ in S:
                aux[int(u_)] *= (1.0 - rho)
            av = np.array([aux[int(u_)] for u_ in S])
            dev2 = D[S] @ zeta + db[S] - ps["rest_s"][S]
            z = zeta - Ks[:, S] @ (dev2 - av)
        else:
            z = zeta
        if not np.all(np.isfinite(zeta)):
            zeta = np.nan_to_num(zeta, nan=0.0, posinf=1e6, neginf=-1e6)
        if "z_lo" in ps:
            zeta = np.minimum(np.maximum(zeta, ps["z_lo"]), ps["z_hi"])
        if not np.all(np.isfinite(z)):
            z = np.nan_to_num(z, nan=0.0, posinf=1e6, neginf=-1e6)
        if "z_lo" in ps:
            z = np.minimum(np.maximum(z, ps["z_lo"]), ps["z_hi"])
        zs.append(z.copy())
    return np.stack(zs)


def _edge_effect(P: dict, s: int, z, v, edges: list):
    """First-order latent effect of removing the couplings post <- pre: for each distinct pre, the change of the latent drive
    when pre is held at rest, projected through the units post that lose that input."""
    ps = P["systems"][s]
    E, D, db = ps.get("K_ev", ps["E"]), ps["D"], ps["dbias"]
    F0 = f_sys(P, s, z, v)
    by_pre: dict[int, list[int]] = {}
    for post, pre in edges:
        by_pre.setdefault(int(pre), []).append(int(post))
    out = np.zeros_like(z)
    for pre, posts in by_pre.items():
        xh = D[pre] @ z + db[pre]
        zm = z + E[:, pre] * (ps["rest_s"][pre] - xh)
        dF = f_sys(P, s, zm, v) - F0                    # latent drive change if pre were at rest (all its targets)
        dx_units = D[posts] @ dF                        # the part of it carried by the units that actually lose the input
        out = out + E[:, posts] @ dx_units
    return out


# ------------------------------------------------------------------------------------------------------------ validation score
def val_score(P: dict, s: int, sd: SysData, idx: np.ndarray, horizon_s: float, n_starts: int = 4, pcs=None, alpha: float | None = None) -> dict:
    """Open-loop validation error on trajectories idx (events included, as they happened): from n_starts start times spread over
    the first half of each trajectory, roll out horizon_s and measure y NMSE (per readout variance) and the NMSE of the leading
    PCs of the standardised microstate (reconstructed through the decoder). Returns means, per-trajectory values and SEs."""
    from .sd_core import parse_events
    dt = sd.dt
    Hh = max(1, int(round(horizon_s / dt)))
    m, V, lam = pcs if pcs is not None else sd.pca(min(10, sd.N))
    per_y, per_x = [], []
    ps = P["systems"][s]
    for i in idx:
        if not sd.finite[i]:
            continue
        X, U, Y = sd.X[i], sd.U[i], sd.Y[i]
        T = len(X)
        H = min(Hh, T - 2)
        t_starts = np.unique(np.linspace(max(1, T // 8), max(2, T - H - 1), n_starts).astype(int))
        ey, ex = [], []
        for t0 in t_starts:
            if t0 + H >= T:
                continue
            z0 = encode_hist_np(P, s, X[: t0 + 1], U[: t0 + 1], dt, alpha)
            ev = _shift_parsed(sd.EV[i], t0)
            Z = rollout_np(P, s, z0, U[t0: t0 + H + 1], ev, dt, H)
            yp = readout_np(P, s, Z, U[t0: t0 + H + 1])
            ey.append(float(np.mean((yp[1:] - Y[t0 + 1: t0 + H + 1]) ** 2 / sd.y_var)))
            xh = Z[1:] @ ps["D"].T + ps["dbias"]
            xt = sd.xs(X[t0 + 1: t0 + H + 1])
            num = (((xh - xt) @ V.T) ** 2).sum(1).mean()
            den = (((xt - m) @ V.T) ** 2).sum(1).mean() + 1e-9
            ex.append(float(num / max(den, lam.sum() * 0.1)))
        if ey:
            # per-trajectory errors are capped at 2 (twice the error of predicting the mean): one diverging rollout must not
            # decide the model selection alone
            per_y.append(min(SCORE_CAP, float(np.mean(ey))))
            per_x.append(min(SCORE_CAP, float(np.mean(ex))))
    y_m, y_se = se_mean(per_y)
    x_m, x_se = se_mean(per_x)
    tot = [a + b for a, b in zip(per_y, per_x)]
    t_m, t_se = se_mean(tot)
    return {"y": y_m, "x": x_m, "score": t_m, "se": t_se, "per_traj": tot, "per_y": per_y}


def event_score(P: dict, s: int, sd: SysData, horizon_s: float) -> float:
    """Mean readout NMSE over the primary horizon after the first event of every training / validation trajectory with events
    (encoded at the pre-event sample, rolled out with the events). Used to choose the event model; everything else is shared by
    the candidates, so differences come from the event semantics only."""
    Hh = max(1, int(round(horizon_s / sd.dt)))
    errs = []
    for i in range(len(sd.X)):
        if not sd.EV[i] or not sd.finite[i]:
            continue
        t0 = min(a for _, a, _, _ in sd.EV[i])
        X, U, Y = sd.X[i], sd.U[i], sd.Y[i]
        H = min(Hh, len(X) - t0 - 1)
        if t0 < 1 or H < 2:
            continue
        z0 = encode_hist_np(P, s, X[: t0 + 1], U[: t0 + 1], sd.dt)
        Z = rollout_np(P, s, z0, U[t0: t0 + H + 1], _shift_parsed(sd.EV[i], t0), sd.dt, H)
        yp = readout_np(P, s, Z, U[t0: t0 + H + 1])
        errs.append(min(SCORE_CAP, float(np.mean((yp[1:] - Y[t0 + 1: t0 + H + 1]) ** 2 / sd.y_var))))
    return float(np.mean(errs)) if errs else float("nan")


def event_errors(P: dict, s: int, sd: SysData, horizon_s: float, kinds: tuple[str, ...]) -> list[float]:
    """Per-trajectory readout NMSE over the horizon after the first event, for the training / validation trajectories whose events
    are all of the given kinds (encoded at the pre-event sample, rolled out with the events)."""
    Hh = max(1, int(round(horizon_s / sd.dt)))
    errs = []
    for i in range(len(sd.X)):
        if not sd.EV[i] or not sd.finite[i] or not all(e[0] in kinds for e in sd.EV[i]):
            continue
        t0 = min(a for _, a, _, _ in sd.EV[i])
        X, U, Y = sd.X[i], sd.U[i], sd.Y[i]
        H = min(Hh, len(X) - t0 - 1)
        if t0 < 1 or H < 2:
            continue
        z0 = encode_hist_np(P, s, X[: t0 + 1], U[: t0 + 1], sd.dt)
        Z = rollout_np(P, s, z0, U[t0: t0 + H + 1], _shift_parsed(sd.EV[i], t0), sd.dt, H)
        yp = readout_np(P, s, Z, U[t0: t0 + H + 1])
        errs.append(min(SCORE_CAP, float(np.mean((yp[1:] - Y[t0 + 1: t0 + H + 1]) ** 2 / sd.y_var))))
    return errs


EVENT_GAINS = (1.0, 0.7, 1.4, 0.5, 2.0, 0.35, 0.2, 0.1)      # in order of preference (closest to 1 first)


def calibrate_event_gain(P: dict, s: int, sd: SysData, horizon_s: float) -> dict:
    """Scalar gain beta of the kick / current map, K_ev <- beta K_ev, from the training / validation trajectories with kicks or
    currents: the mean post-event readout error for every beta in EVENT_GAINS; beta = the most preferred (closest to 1) value
    within 5 % of the best (a calibration, not a test: with few event trajectories a significance rule would never move beta).
    Needs >= 3 such trajectories; otherwise beta = 1. The direction of a unit perturbation in the latent comes from the geometry
    (K); its magnitude of transmission is what the training perturbations measure."""
    ps = P["systems"][s]
    K0 = ps["K_ev"].copy()
    rows = []
    for j, b in enumerate(EVENT_GAINS):
        ps["K_ev"] = b * K0
        e = event_errors(P, s, sd, horizon_s, ("kick", "current"))
        if len(e) < 3:
            ps["K_ev"] = K0
            return {"beta": 1.0, "n_events": len(e), "note": "too few kick / current trajectories"}
        rows.append({"beta": b, "score": float(np.mean(e)), "n": len(e)})
    best = min(r["score"] for r in rows)
    beta = next(r["beta"] for r in rows if r["score"] <= 1.05 * best + 1e-12)
    ps["K_ev"] = beta * K0
    return {"beta": beta, "n_events": rows[0]["n"], "curve": [{"beta": r["beta"], "score": r["score"]} for r in rows]}


EVENT_MAPS = {"E": lambda ps: ps["E"], "pinvD": lambda ps: event_map_pinv(ps), "pinvDraw": lambda ps: event_map_pinv_raw(ps)}


def set_event_model(P: dict, s: int, silence: str = "split", kmap: str = "pinvDraw") -> dict:
    """Event semantics of system s: silence 'split' (drive without the silenced units, their own decay tracked) or 'clamp';
    event map 'pinvDraw' (least-squares reprojection in raw units: default), 'pinvD' (standardised units) or 'E' (encoder).
    Default chosen on the public dev suite (notes/sd_shared.md: the only variant whose held-out effect-error CI fell below 1;
    selecting by training event windows is biased towards E, which training fits)."""
    ps = P["systems"][s]
    ps["sil_mode"] = silence
    ps["K_ev"] = EVENT_MAPS[kmap](ps)
    ps["K_sil"] = ps["K_ev"].copy()
    return {"silence": silence, "map": kmap}


def event_map_pinv_raw(ps: dict, ridge: float = 1e-3) -> np.ndarray:
    """As event_map_pinv but the least-squares reprojection is done in RAW units (kicks and currents are raw offsets); returned
    as a map of standardised perturbations (K @ (dx / sd))."""
    Dr = ps["D"] * ps["sd"][:, None]
    G = Dr.T @ Dr
    K = np.linalg.solve(G + ridge * np.trace(G) / len(G) * np.eye(len(G)), Dr.T)
    return K * ps["sd"][None, :]


def event_map_pinv(ps: dict, ridge: float = 1e-3) -> np.ndarray:
    """K = (D^T D + r I)^-1 D^T: a unit perturbation moves the state to the latent point whose decoded microstate best matches
    the perturbed one (least squares in standardised units)."""
    D = ps["D"]
    G = D.T @ D
    return np.linalg.solve(G + ridge * np.trace(G) / len(G) * np.eye(len(G)), D.T)


def _shift_parsed(parsed: list, t0: int) -> list:
    out = []
    for kind, a, b, p in parsed:
        if b <= t0:
            continue
        out.append((kind, max(0, a - t0) if kind != "kick" else a - t0, b - t0, p))
    return [e for e in out if not (e[0] == "kick" and e[1] < 0)]
